"""The part of the coach that actually watches and acts.

This runs in Home Assistant, on a timer, whether or not anybody has the panel
open. That is the whole reason it is here rather than in the browser: a car has
to start charging at two in the morning, and at two in the morning nobody is
looking at a dashboard. A restart must not matter either, so nothing is kept
that cannot be read back from the installation itself.

The thinking is next door in planner.py, which knows nothing about Home
Assistant and can therefore be run against a whole day of real history before
anything is switched. This file only reads sensors, calls services and keeps
the two apart.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CHARGER_CONTROL,
    DOMAIN,
    EVENT_DECISION,
    LEVEL_PROPOSE,
    LEVEL_STEER,
)
from .planner import (
    Car,
    Charger,
    Decision,
    Grid,
    Window,
    amps_for,
    decide,
    should_send,
)
from .storage import async_get_store

_LOGGER = logging.getLogger(__name__)

# How often to think. A minute is often enough to catch a kettle before a fuse
# minds, and rare enough that a car is never re-commanded into giving up.
INTERVAL = timedelta(seconds=60)

# How long to wait for the charger to confirm a new limit before starting.
CONFIRM_SECONDS = 15


def _number(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """A sensor read as a plain number, or None when it says nothing useful."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unknown", "unavailable", ""):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _text(hass: HomeAssistant, entity_id: str | None) -> str:
    """A sensor read as its raw state, lower-cased for comparing."""
    if not entity_id:
        return ""
    state = hass.states.get(entity_id)
    return "" if state is None else str(state.state).lower()


def _time(value: str | None) -> time | None:
    """"07:00" as a time, or None."""
    if not value:
        return None
    try:
        hour, minute = value.split(":")
        return time(int(hour), int(minute))
    except (ValueError, AttributeError):
        return None


class ChargerCoach:
    """Watches every steerable charging point and acts on what it sees."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up without touching anything yet."""
        self.hass = hass
        self._cancel = None
        # What we last decided per device, so a charger is not re-commanded for
        # a fraction of an amp.
        self._last: dict[str, Decision] = {}
        # When the session we started began. Not persisted on purpose: after a
        # restart the charger itself says whether it is charging, and treating
        # that as "just started" only costs a few minutes of patience.
        self._since: dict[str, datetime] = {}
        # The latest decision per device, for the panel to ask after.
        self.state: dict[str, dict[str, Any]] = {}
        # Devices the customer said yes to. Only meaningful at "propose", and
        # it lasts exactly one session: pull the cable and the coach is back to
        # asking. Somebody who agreed to one charge did not agree to every
        # charge from now on.
        self._approved: set[str] = set()

    @callback
    def async_start(self) -> None:
        """Begin the minute-by-minute round."""
        if self._cancel is None:
            self._cancel = async_track_time_interval(self.hass, self._tick, INTERVAL)

    @callback
    def async_stop(self) -> None:
        """Stop, leaving the charger on whatever limit it was given.

        Deliberately nothing is sent here. A limit set with an unlimited
        time-to-live stays put, and it is always at or under what the charging
        point allows, so a coach that goes away leaves a car charging safely
        rather than at full tilt.
        """
        if self._cancel is not None:
            self._cancel()
            self._cancel = None

    async def _tick(self, now: datetime | None = None) -> None:
        """One round: look, think, act."""
        try:
            settings = await async_get_store(self.hass).async_load()
        except Exception:  # noqa: BLE001 - never let a bad read stop the timer
            _LOGGER.exception("kon de instellingen niet lezen")
            return

        level = (settings.get("strategy") or {}).get("level", LEVEL_PROPOSE)
        moment = dt_util.as_local(now or dt_util.utcnow()).replace(tzinfo=None)

        for device in settings.get("devices") or []:
            if device.get("type") != "laadpaal" or not device.get("controllable"):
                continue
            try:
                await self._one(moment, settings, device, level)
            except Exception:  # noqa: BLE001 - one broken device is not all of them
                _LOGGER.exception("kon %s niet beoordelen", device.get("id"))

    async def _one(
        self,
        now: datetime,
        settings: dict[str, Any],
        device: dict[str, Any],
        level: str,
    ) -> None:
        """Look at one charging point and act on what the planner says."""
        device_id = device.get("id", "")
        grid, car, charger, window = self._read(now, settings, device)
        goal = (settings.get("strategy") or {}).get("goal", "cost")

        decision = decide(now, self._prices(settings), grid, car, charger, window, goal)

        # Remembered before anything is sent, so the panel can show what the
        # coach would do even at a level where it does nothing.
        self.state[device_id] = {
            **asdict(decision),
            "at": now.isoformat(),
            "level": level,
            "applied": level == LEVEL_STEER,
        }
        may_act = level == LEVEL_STEER or (
            level == LEVEL_PROPOSE and device_id in self._approved
        )
        self.state[device_id]["applied"] = may_act
        self.state[device_id]["approved"] = device_id in self._approved
        self.hass.bus.async_fire(
            EVENT_DECISION, {"device": device_id, **self.state[device_id]}
        )

        # An agreement lasts as long as the car is on the cable.
        if not charger.connected:
            self._approved.discard(device_id)

        if not may_act:
            return
        if not should_send(self._last.get(device_id), decision):
            return

        if await self._apply(device, charger, decision):
            self._last[device_id] = decision
            if decision.charge:
                self._since.setdefault(device_id, now)
            else:
                self._since.pop(device_id, None)

    def _prices(self, settings: dict[str, Any]) -> list[dict]:
        """The published price list, in the shape the planner wants.

        Read from the same entity the panel charts, so the two can never
        disagree about what an hour costs.
        """
        contract = settings.get("contract") or {}
        if contract.get("type") != "dynamic":
            return []

        dynamic = contract.get("dynamic") or {}
        all_in = dynamic.get("source") == "all_in"
        entity_id = dynamic.get("all_in_entity") if all_in else dynamic.get("market_entity")
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            return []

        rows: list[dict] = []
        for row in state.attributes.get("prices") or []:
            try:
                start = dt_util.parse_datetime(row["from"])
                end = dt_util.parse_datetime(row["till"])
                price = float(row["price"])
            except (KeyError, TypeError, ValueError):
                continue
            if start is None or end is None:
                continue
            if not all_in:
                price = self._all_in(price, dynamic)
            rows.append(
                {
                    "start": dt_util.as_local(start).replace(tzinfo=None),
                    "end": dt_util.as_local(end).replace(tzinfo=None),
                    "price": price,
                }
            )
        return sorted(rows, key=lambda item: item["start"])

    @staticmethod
    def _all_in(market: float, dynamic: dict[str, Any]) -> float:
        """A bare market price with tax, markup and VAT, the Dutch way round."""
        tax = float(dynamic.get("energy_tax") or 0)
        markup = float(dynamic.get("supplier_markup") or 0)
        vat = float(dynamic.get("vat_percent") or 0)
        return (market + tax + markup) * (1 + vat / 100)

    def _read(
        self, now: datetime, settings: dict[str, Any], device: dict[str, Any]
    ) -> tuple[Grid, Car, Charger, Window]:
        """Everything the planner needs, gathered from the installation."""
        sources = settings.get("sources") or {}
        installation = settings.get("installation") or {}
        entities = device.get("entities") or {}

        # --- what the grid is doing ---
        if sources.get("grid_mode") == "signed":
            signed = _number(self.hass, sources.get("grid_signed")) or 0.0
            if sources.get("grid_signed_invert"):
                signed = -signed
            surplus = max(0.0, -signed)
        else:
            surplus = _number(self.hass, sources.get("grid_export")) or 0.0

        phases = []
        for key in ("l1", "l2", "l3"):
            phase = (sources.get("phases") or {}).get(key) or {}
            amps = _number(self.hass, phase.get("current"))
            if amps is None:
                watts = _number(self.hass, phase.get("power"))
                volts = _number(self.hass, phase.get("voltage")) or 230
                amps = watts / volts if watts is not None and volts else None
            if amps is not None:
                phases.append(amps)

        charger_amps = _number(self.hass, entities.get("current")) or 0.0

        grid = Grid(
            surplus_w=surplus,
            phase_amps=phases,
            fuse_amps=float(installation.get("fuse_amps") or 25),
            charger_amps=charger_amps,
        )

        # --- the charging point ---
        status = _text(self.hass, entities.get("status"))
        charger = Charger(
            max_amps=_number(self.hass, entities.get("max_limit")) or 16.0,
            connected=bool(status) and "disconnect" not in status,
            charging="charging" in status,
            started_at=self._since.get(device.get("id", "")),
        )
        # After a restart nothing is known about when this session began. Taking
        # it as "just now" only means waiting out the minimum run once.
        if charger.charging and charger.started_at is None:
            charger.started_at = self._since.setdefault(device.get("id", ""), now)

        # --- which car ---
        car = self._car(settings, device, charger)

        # --- when it may run ---
        window = Window()
        for entry in (settings.get("strategy") or {}).get("schedules") or []:
            if entry.get("device") != device.get("id"):
                continue
            times = entry.get("window") or {}
            if entry.get("per_day"):
                for day in entry.get("days") or []:
                    if day.get("day") == now.weekday() and day.get("enabled"):
                        times = day
                        break
            window = Window(
                enabled=bool(entry.get("enabled")),
                not_before=_time(times.get("not_before")),
                start_by=_time(times.get("start_by")),
                done_by=_time(times.get("done_by")),
            )
            break

        return grid, car, charger, window

    def _car(
        self, settings: dict[str, Any], device: dict[str, Any], charger: Charger
    ) -> Car:
        """The car that is plugged in, as far as anybody has said."""
        chosen = ""
        for entry in settings.get("active_cars") or []:
            if entry.get("device") == device.get("id"):
                chosen = entry.get("car", "")
                break

        if chosen == "__guest__":
            return Car(guest=True, phases=3)

        cars = device.get("cars") or []
        profile = next((car for car in cars if car.get("id") == chosen), None)
        if profile is None and len(cars) == 1:
            # One car and nobody ever chose: that is the one.
            profile = cars[0]
        if profile is None:
            return Car(phases=3)

        phases = {"one": 1, "three": 3}.get(profile.get("phases"), 3)
        if profile.get("phases") == "both":
            # A car that switches phases tells on itself: power divided by
            # current is roughly one phase or roughly three.
            phases = self._measured_phases(device) or 3

        return Car(
            capacity_kwh=float(profile.get("capacity_kwh") or 0),
            phases=phases,
            max_amps=float(profile.get("max_amps") or 0),
            soc_percent=_number(self.hass, profile.get("soc_entity")),
        )

    def _measured_phases(self, device: dict[str, Any]) -> int | None:
        """One phase or three, worked out from what the charger reports."""
        entities = device.get("entities") or {}
        watts = _number(self.hass, device.get("entity"))
        amps = _number(self.hass, entities.get("current"))
        if not watts or not amps or amps < 1:
            return None
        return 3 if amps_for(watts, 1) / amps > 2 else 1

    @callback
    def async_approve(self, device_id: str) -> None:
        """The customer agreed to this charging session."""
        self._approved.add(device_id)

    @callback
    def async_withdraw(self, device_id: str) -> None:
        """And can take that back."""
        self._approved.discard(device_id)

    async def _apply(
        self, device: dict[str, Any], charger: Charger, decision: Decision
    ) -> bool:
        """Send it, in the order the hardware wants.

        The limit goes first and the start second, with a check in between that
        the charger really took the new limit. Blindly waiting a fixed second or
        two is either too short on a slow evening or wasted the rest of the
        time, and the panel already reads the limit back anyway.
        """
        control = CHARGER_CONTROL.get(device.get("brand", ""))
        if not control or not device.get("device_id"):
            return False

        if not decision.charge:
            if charger.charging:
                await self._command(device, control, "stop")
            return True

        limit_domain, limit_service = control["limit_service"]
        await self.hass.services.async_call(
            limit_domain,
            limit_service,
            {
                "device_id": device["device_id"],
                control["limit_field"]: decision.amps,
                **control.get("limit_extra", {}),
            },
            blocking=True,
        )

        if not charger.charging:
            if not await self._confirmed(device, decision.amps):
                # Toch starten. De limiet die er dan staat is er een die de paal
                # eerder heeft aangenomen en ligt dus altijd onder zijn eigen
                # maximum, dus het is veilig. Niet starten zou betekenen dat een
                # auto de hele nacht leeg blijft omdat één sensor een andere
                # naam of een andere eenheid heeft dan verwacht, en dat is de
                # ene fout die een klant nooit vergeeft.
                _LOGGER.warning(
                    "laadpaal %s bevestigde de limiet van %s A niet; toch gestart",
                    device.get("id"),
                    decision.amps,
                )
            await self._command(device, control, "start")

        return True

    async def _confirmed(self, device: dict[str, Any], amps: int) -> bool:
        """Wait until the charger reports the limit we just set."""
        entity_id = (device.get("entities") or {}).get("dynamic_limit")
        if not entity_id:
            # Nothing to check against, so fall back to giving it a moment.
            await self._sleep(2)
            return True

        for _ in range(CONFIRM_SECONDS):
            if (_number(self.hass, entity_id) or -1) >= amps - 0.5:
                return True
            await self._sleep(1)
        return False

    async def _sleep(self, seconds: float) -> None:
        """Waiting that a test can shortcut."""
        import asyncio

        await asyncio.sleep(seconds)

    async def _command(
        self, device: dict[str, Any], control: dict[str, Any], action: str
    ) -> None:
        """Start, stop or pause, in the word this installation uses."""
        domain, service = control["command_service"]
        word = (device.get("actions") or {}).get(action) or control["words"][action]
        await self.hass.services.async_call(
            domain,
            service,
            {"device_id": device["device_id"], control["command_field"]: word},
            blocking=True,
        )


@callback
def async_get_coach(hass: HomeAssistant) -> ChargerCoach:
    """The one coach for this Home Assistant."""
    data = hass.data.setdefault(DOMAIN, {})
    if "coach" not in data:
        data["coach"] = ChargerCoach(hass)
    return data["coach"]
