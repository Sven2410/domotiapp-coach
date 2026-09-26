"""Wanneer de coach een apparaat met een programma wil starten, als sensor.

De eigenaar op 26-09-2026. Thuis werd de vaatwasser om 12:16 vrijgegeven met
de schakelaar op de keukenkaart, de coach plande 14:00, en om 13:12 ging hij
met de hand aan: op die kaart stond nergens dat er een plan was. "Dan wil ik
dat er op de vaatwasser kaart komt te staan wanneer de coach van plan is om
de vaatwasser aan te zetten." Op de keuze tussen een sensor en een kaart die
het de coach zelf vraagt koos hij de sensor: die werkt in elke kaart en in
een automatisering.

Eén sensor per apparaat met een programma (`PROGRAMMA_TYPES`), met het
tijdstip als toestand zolang hij vrijgegeven is en wacht, en leeg in elk
ander geval: niet vrijgegeven, hij start nu, hij draait. Wat de coach erbij
zegt staat in de attributen, en ook de vrijgaveschakelaar, zodat een kaart
die die schakelaar al kent de sensor zelf kan vinden.

De sensor rekent niets; hij volgt het besluit dat de coach elke ronde op de
eventbus zet (`EVENT_DECISION`, `_besluit_melden` in coach.py).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_DECISION, EVENT_SETTINGS_UPDATED, PROGRAMMA_TYPES
from .storage import async_get_store


def gepland_om(stand: dict[str, Any] | None) -> datetime | None:
    """Het geplande startmoment uit een besluit, met tijdzone, of None.

    Alleen bij wachten op het gekozen moment (`wait-for-start`): dan heeft het
    besluit een `starts_at`. De coach rekent in lokale tijd zonder tijdzone
    (`_moment`); een sensor met een tijdstip hoort er een te hebben.
    """
    if not stand or stand.get("rule") != "wait-for-start" or stand.get("running"):
        return None
    rauw = stand.get("starts_at")
    if not rauw:
        return None
    try:
        moment = datetime.fromisoformat(str(rauw))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt_util.get_default_time_zone())
    return moment


def _coach_apparaat() -> DeviceInfo:
    """Eén apparaat voor de coach zelf, zodat zijn sensoren bij elkaar staan."""
    return DeviceInfo(
        identifiers={(DOMAIN, "coach")},
        name="DomotiApp Coach",
        manufacturer="DomotiApp",
        entry_type=DeviceEntryType.SERVICE,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Een sensor per apparaat met een programma, en later bijkomers ook."""
    from .coach import async_get_coach

    bekend: dict[str, StartOmSensor] = {}

    async def toevoegen() -> None:
        settings = await async_get_store(hass).async_load()
        nieuw = []
        for device in settings.get("devices") or []:
            device_id = device.get("id")
            if not device_id or device.get("type") not in PROGRAMMA_TYPES:
                continue
            if device_id in bekend:
                bekend[device_id].bijwerken_apparaat(device)
                continue
            sensor = StartOmSensor(device, async_get_coach(hass).state.get(device_id))
            bekend[device_id] = sensor
            nieuw.append(sensor)
        if nieuw:
            async_add_entities(nieuw)

    await toevoegen()

    @callback
    def besluit(event: Any) -> None:
        data = dict(event.data or {})
        device_id = data.get("device")
        sensor = bekend.get(device_id)
        if sensor is not None:
            sensor.bijwerken(data)
        elif data.get("kind") == "programma":
            # Een apparaat dat na het opstarten is toegevoegd.
            hass.async_create_task(toevoegen())

    @callback
    def instellingen(event: Any) -> None:
        # Een nieuw apparaat, een andere naam of een andere schakelaar.
        hass.async_create_task(toevoegen())

    entry.async_on_unload(hass.bus.async_listen(EVENT_DECISION, besluit))
    entry.async_on_unload(hass.bus.async_listen(EVENT_SETTINGS_UPDATED, instellingen))


class StartOmSensor(SensorEntity):
    """Wanneer de coach dit apparaat wil starten."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-start"
    # De zinnen van de coach veranderen soms per ronde (wat nu starten zou
    # kosten); die horen niet elke minuut in de recorder.
    _unrecorded_attributes = frozenset({"reason", "plan"})

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None) -> None:
        self._device_id = device["id"]
        self._attr_unique_id = f"{device['id']}_start_om"
        self._attr_device_info = _coach_apparaat()
        self._stand: dict[str, Any] = dict(stand or {})
        self._schakelaar: str | None = None
        self._zet_apparaat(device)

    def _zet_apparaat(self, device: dict[str, Any]) -> None:
        self._attr_name = f"{device.get('name') or 'Apparaat'} start om"
        self._schakelaar = (device.get("entities") or {}).get("release_switch") or None

    @callback
    def bijwerken_apparaat(self, device: dict[str, Any]) -> None:
        """Naam en schakelaar na een wijziging in de instellingen."""
        self._zet_apparaat(device)
        if self.hass is not None:
            self.async_write_ha_state()

    @callback
    def bijwerken(self, stand: dict[str, Any]) -> None:
        """Het besluit van deze ronde; alleen schrijven als er iets veranderde."""
        oud = (self.native_value, self.extra_state_attributes)
        self._stand = stand
        if (self.native_value, self.extra_state_attributes) != oud and self.hass is not None:
            self.async_write_ha_state()

    @property
    def native_value(self) -> datetime | None:
        return gepland_om(self._stand)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "reason": self._stand.get("reason") or "",
            "plan": self._stand.get("plan") or "",
            "rule": self._stand.get("rule") or "",
            "released": bool(self._stand.get("released")),
            "running": bool(self._stand.get("running")),
            "release_switch": self._schakelaar,
        }
