"""Watch the load on the connection and warn when it gets close to the fuse.

This lives in the integration rather than in the panel because the warning has
to arrive when nobody is looking at the dashboard -- which is most of the time,
and exactly when a heavy load goes unnoticed.

Two settings keep it from becoming noise, and they answer different questions.

The hold time answers "is this real": switching on an oven, a motor starting,
an induction hob stepping up -- all of them throw a spike of a second or two
that no fuse minds and that is over before anyone could act on it. Nothing is
sent until the load has stayed over the line for the configured time.

The interval answers "have I said this already": load swings across any
threshold dozens of times an hour. It is deliberately *only* an interval and
not a "fires once on the way in" rule -- a connection that stays overloaded for
an hour is still worth a second word about.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import EVENT_SETTINGS_UPDATED, GRID_MODE_SIGNED, LEVEL_STEER
from .storage import async_get_store
from .units import to_watts

_LOGGER = logging.getLogger(__name__)

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
    """Read a state as watts, whatever unit it reports.

    Dezelfde omrekening als de coach en het paneel, uit `units.py`, zodat de
    drie het nooit oneens kunnen worden over wat een kilowatt is.
    """
    if state is None:
        return None
    return to_watts(_number(state), state.attributes.get("unit_of_measurement"))


@dataclass
class LoadReading:
    """What the connection is doing, and how that was worked out."""

    percent: float | None = None
    basis: str | None = None
    worst_phase: str | None = None
    amps: float | None = None
    watts: float | None = None
    entities: list[str] = field(default_factory=list)
    # Wat de coach op dit moment zelf aan het laden is, in dezelfde eenheid als
    # `amps` of `watts`, en wat de aansluiting zonder dat zou doen. Zie
    # `_coach_aandeel`.
    eigen: float = 0.0
    zonder_coach: float | None = None


class LoadMonitor:
    """Track the load on the connection and send the alert."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up without touching state yet."""
        self.hass = hass
        self._settings: dict[str, Any] = {}
        self._unsubscribe_states = None
        self._unsubscribe_settings = None
        self._last_sent: datetime | None = None
        # When the load first went over the line and stayed there. Cleared the
        # moment it drops back below, which is what makes a spike a spike.
        self._above_since: datetime | None = None
        self._cancel_recheck = None

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
        self._async_cancel_recheck()

    @callback
    def _async_settings_changed(self, event: Event) -> None:
        """Adopt new settings and re-point the state subscription."""
        settings = event.data.get("settings")
        if not settings:
            return
        self._settings = settings
        # A threshold that just moved says nothing about how long the load has
        # been over the *new* line, so the clock starts again.
        self._above_since = None
        self._async_cancel_recheck()
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
        """A watched sensor moved; look again."""
        self._async_evaluate()

    @callback
    def _async_cancel_recheck(self) -> None:
        """Drop a pending look-again."""
        if self._cancel_recheck:
            self._cancel_recheck()
            self._cancel_recheck = None

    @callback
    def _async_evaluate(self, _now: datetime | None = None) -> None:
        """Recompute the load and decide whether to say something."""
        self._async_cancel_recheck()

        alert = self._settings.get("strategy", {}).get("load_alert", {})
        threshold = float(alert.get("threshold_percent") or 0)
        reading = self.async_current_load()

        if not alert.get("enabled") or threshold <= 0 or reading.percent is None:
            self._above_since = None
            return

        # Getoetst wordt de belasting zónder wat de coach zelf aan het laden en
        # aan het terugregelen is; zie `_coach_aandeel`. De melding noemt straks
        # wel het echte getal, want dat is wat er op de kaart staat.
        gemeten = reading.zonder_coach
        if gemeten is None:
            gemeten = reading.percent

        if gemeten < threshold:
            # Back under the line: whatever was building up did not last.
            self._above_since = None
            return

        now = dt_util.utcnow()
        if self._above_since is None:
            self._above_since = now

        hold = timedelta(seconds=int(alert.get("min_duration_seconds") or 0))
        waited = now - self._above_since
        if waited < hold:
            # A load that sits still produces no state changes, so waiting for
            # the next event could mean waiting forever. Come back by the clock
            # instead, at the moment the hold time is up.
            self._cancel_recheck = async_call_later(
                self.hass, (hold - waited).total_seconds(), self._async_evaluate
            )
            return

        interval = timedelta(minutes=int(alert.get("min_interval_minutes") or 30))
        if self._last_sent is not None and now - self._last_sent < interval:
            return

        self._last_sent = now
        self.hass.async_create_task(self._async_notify(reading, threshold, alert))

    def _coach_aandeel(self, in_watt: bool) -> float:
        """Wat er van deze belasting van de coach zelf is.

        De waarschuwing bestaat om te zeggen dat er iets zwaars aanstaat waar je
        niets van weet. Een laadpaal die de coach op ditzelfde moment aan het
        terugregelen is, is precies dat niet.

        Bij Van den Dam kreeg Sven in de nacht van 30-08-2026 drie meldingen,
        om 03:02, 03:32 en 04:22, telkens met "zet iets zwaars uit of wacht
        ermee". Het zware ding was zijn eigen auto, en de coach stond op dat
        moment al op 12 A in plaats van 16. Om vier uur 's nachts gewekt worden
        voor iets dat de coach zelf doet en zelf oplost is verkeerd.

        Alleen op Sturen, en alleen voor palen die de coach mag sturen. Kan hij
        er niet bij, dan is de laadpaal net zo goed een apparaat waar de bewoner
        zelf iets aan moet doen, en dan hoort de melding gewoon te komen.

        Een driefasige paal meldt zijn stroom per fase, dus dat getal hoort er
        op elke fase net zo hard af; een eenfasige belast er één. Van de
        zwaarste fase aftrekken klopt dus in beide gevallen. Dezelfde redenering
        als `charger_share` in planner.py.
        """
        if (self._settings.get("strategy") or {}).get("level") != LEVEL_STEER:
            return 0.0

        states = self.hass.states
        totaal = 0.0
        for device in self._settings.get("devices") or []:
            if device.get("type") != "laadpaal" or not device.get("controllable"):
                continue
            if in_watt:
                waarde = _watts(states.get(device.get("entity") or ""))
            else:
                entity = (device.get("entities") or {}).get("current")
                waarde = _number(states.get(entity)) if entity else None
            if waarde and waarde > 0:
                totaal += waarde
        return totaal

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
                eigen = min(self._coach_aandeel(in_watt=False), worst_amps)
                return LoadReading(
                    percent=(worst_amps / fuse) * 100,
                    basis="phase",
                    worst_phase=worst_label,
                    amps=worst_amps,
                    eigen=eigen,
                    zonder_coach=((worst_amps - eigen) / fuse) * 100,
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

        eigen = min(self._coach_aandeel(in_watt=True), import_w)
        return LoadReading(
            percent=(import_w / ceiling) * 100,
            basis="power",
            watts=import_w,
            eigen=eigen,
            zonder_coach=((import_w - eigen) / ceiling) * 100,
        )

    async def _async_notify(
        self, reading: LoadReading, threshold: float, alert: dict[str, Any]
    ) -> None:
        """Send the warning to everyone the customer picked."""
        targets = alert.get("targets") or []
        if not targets:
            return

        home = (self._settings.get("installation", {}).get("home_name") or "").strip()
        where = f"{home}: " if home else ""

        # Komt er een deel van de laadpaal, dan staat dat erbij. Zonder dat
        # klopt het getal op de telefoon niet met wat er op de kaart staat, en
        # dan is de eerste gedachte "wat staat er in vredesnaam aan". Een paal
        # die niets doet meldt zijn rustverbruik in honderdsten en die hoort
        # hier niet als "0,0 A van de laadpaal" te verschijnen.
        if reading.basis == "phase":
            detail = f"Fase {reading.worst_phase} trekt {reading.amps:.1f} A"
            if reading.eigen >= 0.5:
                detail += f", waarvan {reading.eigen:.1f} A van de laadpaal"
        else:
            detail = f"Je trekt {reading.watts / 1000:.2f} kW uit het net".replace(".", ",")
            if reading.eigen >= 50:
                detail += (
                    f", waarvan {reading.eigen / 1000:.2f} kW van de laadpaal"
                ).replace(".", ",")

        # How long it has been going on is the difference between "act on this"
        # and "you missed a spike", so it goes in the message.
        held = ""
        if self._above_since is not None:
            seconds = int((dt_util.utcnow() - self._above_since).total_seconds())
            held = (
                f" en dat al {seconds} seconden"
                if seconds < 90
                else f" en dat al {round(seconds / 60)} minuten"
            )

        message = (
            f"{where}je aansluiting zit op {reading.percent:.0f}%{held} "
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
