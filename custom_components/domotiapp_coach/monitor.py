"""Watch the load on the connection and warn when it gets close to the fuse.

This lives in the integration rather than in the panel because the warning has
to arrive when nobody is looking at the dashboard -- which is most of the time,
and exactly when a heavy load goes unnoticed.

The interval the customer sets is what keeps it from becoming noise: load swings
across any threshold dozens of times an hour, and a warning that repeats itself
is one people switch off. It is deliberately *only* the interval and not a
"fires once on the way in" rule -- a connection that stays overloaded for an
hour is still worth a second word about.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import EVENT_SETTINGS_UPDATED, GRID_MODE_SIGNED
from .storage import async_get_store

_LOGGER = logging.getLogger(__name__)

# Same normalisation as the frontend: what a sensor calls itself is not our
# problem, and guessing kW where it means W is a factor of a thousand.
_POWER_TO_WATT = {"w": 1.0, "kw": 1_000.0, "mw": 1_000_000.0}

# Used when a phase reports power but not volts.
_NOMINAL_VOLTS = 230.0


def _number(state: State | None) -> float | None:
    """Read a state as a plain float, or None when it says nothing useful."""
    if state is None or state.state in ("unknown", "unavailable", ""):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _watts(state: State | None) -> float | None:
    """Read a state as watts, whatever unit it reports."""
    value = _number(state)
    if value is None:
        return None
    unit = str(state.attributes.get("unit_of_measurement", "")).strip().lower()
    return value * _POWER_TO_WATT.get(unit, 1.0)


@dataclass
class LoadReading:
    """What the connection is doing, and how that was worked out."""

    percent: float | None = None
    basis: str | None = None
    worst_phase: str | None = None
    amps: float | None = None
    watts: float | None = None
    entities: list[str] = field(default_factory=list)


class LoadMonitor:
    """Track the load on the connection and send the alert."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up without touching state yet."""
        self.hass = hass
        self._settings: dict[str, Any] = {}
        self._unsubscribe_states = None
        self._unsubscribe_settings = None
        self._last_sent: datetime | None = None

    async def async_start(self) -> None:
        """Load the settings and begin watching."""
        self._settings = await async_get_store(self.hass).async_load()
        self._unsubscribe_settings = self.hass.bus.async_listen(
            EVENT_SETTINGS_UPDATED, self._async_settings_changed
        )
        self._resubscribe()

    @callback
    def async_stop(self) -> None:
        """Stop watching."""
        if self._unsubscribe_states:
            self._unsubscribe_states()
            self._unsubscribe_states = None
        if self._unsubscribe_settings:
            self._unsubscribe_settings()
            self._unsubscribe_settings = None

    @callback
    def _async_settings_changed(self, event: Event) -> None:
        """Adopt new settings and re-point the state subscription."""
        settings = event.data.get("settings")
        if not settings:
            return
        self._settings = settings
        # A changed sensor list means the old subscription is watching the wrong
        # entities.
        self._resubscribe()

    @callback
    def _resubscribe(self) -> None:
        """Watch exactly the entities the current settings depend on."""
        if self._unsubscribe_states:
            self._unsubscribe_states()
            self._unsubscribe_states = None

        entities = self._watched_entities()
        if not entities:
            return

        self._unsubscribe_states = async_track_state_change_event(
            self.hass, entities, self._async_state_changed
        )

    def _watched_entities(self) -> list[str]:
        """Entity ids that feed the load calculation."""
        sources = self._settings.get("sources", {})
        entities: list[str] = []

        if sources.get("phases_enabled"):
            for phase in ("l1", "l2", "l3"):
                config = sources.get("phases", {}).get(phase, {}) or {}
                # Power and voltage matter too: a phase mapped with only power
                # still drives the calculation.
                for kind in ("current", "power", "voltage"):
                    if config.get(kind):
                        entities.append(config[kind])

        if sources.get("grid_mode") == GRID_MODE_SIGNED:
            if sources.get("grid_signed"):
                entities.append(sources["grid_signed"])
        elif sources.get("grid_import"):
            entities.append(sources["grid_import"])

        return entities

    @callback
    def _async_state_changed(self, event: Event) -> None:
        """Recompute the load and decide whether to say something."""
        alert = self._settings.get("strategy", {}).get("load_alert", {})
        if not alert.get("enabled"):
            return

        reading = self.async_current_load()
        if reading.percent is None:
            return

        threshold = float(alert.get("threshold_percent") or 0)
        if threshold <= 0:
            return

        if reading.percent < threshold:
            return

        now = dt_util.utcnow()
        interval = timedelta(minutes=int(alert.get("min_interval_minutes") or 30))
        if self._last_sent is not None and now - self._last_sent < interval:
            return

        self._last_sent = now
        self.hass.async_create_task(self._async_notify(reading, threshold, alert))

    def _phase_amps(self, config: dict[str, Any]) -> float | None:
        """What a phase is drawing, in amps.

        Each of the three fields is optional -- a customer may have mapped only
        power per phase, or only current. With power but no current the amps
        follow from P/U, using the measured voltage when there is one. Kept in
        step with `phaseAmps` in data-source.js, which does the same sum for the
        dashboard.
        """
        states = self.hass.states

        amps = _number(states.get(config.get("current", ""))) if config.get("current") else None
        if amps is not None:
            return amps

        watts = _watts(states.get(config.get("power", ""))) if config.get("power") else None
        if watts is None:
            return None

        volts = _number(states.get(config.get("voltage", ""))) if config.get("voltage") else None
        if volts is None or volts <= 0:
            volts = _NOMINAL_VOLTS
        return watts / volts

    @callback
    def async_current_load(self) -> LoadReading:
        """Work out how hard the connection is being worked.

        With per-phase currents this is the *heaviest* phase against the main
        fuse, not the average: a fuse blows on the phase that is overloaded, and
        averaging three phases hides exactly the case worth warning about.

        Without them it falls back to import against the connection's ceiling.
        Only import counts -- feeding back loads the connection too, but the
        limit a customer runs into is what they draw.
        """
        sources = self._settings.get("sources", {})
        installation = self._settings.get("installation", {})
        states = self.hass.states

        fuse = float(installation.get("fuse_amps") or 0)
        if sources.get("phases_enabled") and fuse > 0:
            worst_label: str | None = None
            worst_amps: float | None = None
            for phase in ("l1", "l2", "l3"):
                config = sources.get("phases", {}).get(phase, {}) or {}
                amps = self._phase_amps(config)
                if amps is None:
                    continue
                if worst_amps is None or amps > worst_amps:
                    worst_amps = amps
                    worst_label = phase.upper()

            if worst_amps is not None:
                return LoadReading(
                    percent=(worst_amps / fuse) * 100,
                    basis="phase",
                    worst_phase=worst_label,
                    amps=worst_amps,
                )

        ceiling = float(installation.get("max_grid_watts") or 0)
        if ceiling <= 0:
            return LoadReading()

        if sources.get("grid_mode") == GRID_MODE_SIGNED:
            signed = _watts(states.get(sources.get("grid_signed", "")))
            if signed is None:
                return LoadReading()
            if sources.get("grid_signed_invert"):
                signed = -signed
            import_w = max(0.0, signed)
        else:
            import_w = max(0.0, _watts(states.get(sources.get("grid_import", ""))) or 0.0)

        return LoadReading(percent=(import_w / ceiling) * 100, basis="power", watts=import_w)

    async def _async_notify(
        self, reading: LoadReading, threshold: float, alert: dict[str, Any]
    ) -> None:
        """Send the warning to everyone the customer picked."""
        targets = alert.get("targets") or []
        if not targets:
            return

        home = (self._settings.get("installation", {}).get("home_name") or "").strip()
        where = f"{home}: " if home else ""

        if reading.basis == "phase":
            detail = f"Fase {reading.worst_phase} trekt {reading.amps:.1f} A"
        else:
            detail = f"Je trekt {reading.watts / 1000:.2f} kW uit het net".replace(".", ",")

        message = (
            f"{where}je aansluiting zit op {reading.percent:.0f}% "
            f"(waarschuwing vanaf {threshold:.0f}%). {detail}. "
            "Zet iets zwaars uit of wacht ermee."
        )

        for target in targets:
            try:
                await self.hass.services.async_call(
                    "notify",
                    target,
                    {"title": "DomotiApp Coach", "message": message},
                    blocking=False,
                )
            except Exception:  # noqa: BLE001 - one bad target must not stop the rest
                _LOGGER.exception("Kon melding niet versturen naar notify.%s", target)
