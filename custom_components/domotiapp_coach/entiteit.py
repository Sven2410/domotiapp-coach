"""Wat de entiteiten van de coach per apparaat delen (v0.110.0).

De eigenaar op 11-10-2026: kaarten voor de vaatwasser, de laadpaal en de
thuisbatterij die met de coach werken, in een pop-up, "dan hoeven klanten niet
telkens naar de coach toe". De kaarten komen uit DomotiApp Lovelace; de coach
levert per apparaat gewone entiteiten, zodat ze ook in een gewone kaart en in
een automatisering werken.

De afspraak met de kaarten heet het contract (`CONTRACT`), en staat in
docs/vaatwasser.md. Kort: per coach-apparaat één apparaat in Home Assistant
(fabrikant "DomotiApp Coach", model de soort), elke entiteit met een vaste
`translation_key`, en op de sensor van de coach de attributen `contract`,
`type`, `stand` (vaste sleutels) en `entiteiten` (wat de klant bij de coach
invulde). De toestand is tekst voor mensen en mag veranderen; de attributen
zijn het contract. De vaatwasserkaart is ooit gebouwd tegen een toestand die
een uur later tekst werd, en zag daarna niets meer.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, EVENT_SETTINGS_UPDATED
from .storage import async_get_store

_LOGGER = logging.getLogger(__name__)

# Hoger zodra een kaart iets nieuws nodig heeft. Een kaart die een hoger
# contract verwacht dan er staat, zegt "werk DomotiApp Coach bij".
CONTRACT = 1

MODELLEN = {
    "vaatwasser": "Vaatwasser",
    "wasmachine": "Wasmachine",
    "droger": "Droger",
    "boiler": "Boiler",
    "laadpaal": "Laadpaal",
    "thuisbatterij": "Thuisbatterij",
}


def apparaat_info(device: dict[str, Any]) -> DeviceInfo:
    """Het apparaat in Home Assistant voor één apparaat van de coach."""
    soort = str(device.get("type") or "")
    return DeviceInfo(
        identifiers={(DOMAIN, str(device.get("id") or ""))},
        name=device.get("name") or MODELLEN.get(soort, "Apparaat"),
        manufacturer="DomotiApp Coach",
        model=MODELLEN.get(soort, "Apparaat"),
    )


def entiteiten_van(device: dict[str, Any]) -> dict[str, str]:
    """Wat de klant bij de coach invulde, voor de kaart: niet twee keer invullen."""
    uit = {sleutel: str(waarde) for sleutel, waarde in (device.get("entities") or {}).items() if waarde}
    if device.get("entity"):
        uit.setdefault("power", str(device["entity"]))
    if device.get("energy_entity"):
        uit.setdefault("energy", str(device["energy_entity"]))
    return uit


async def async_vrijgave(
    hass: HomeAssistant, device_id: str, ready: bool, now: bool | None = None
) -> dict[str, Any]:
    """Een apparaat vrijgeven of de vrijgave intrekken; `now` is "en nu starten".

    Dezelfde som als de knop in het paneel (`domotiapp_coach/device/ready`): de
    nieuwe lijst wordt hier uitgerekend, zodat een oud scherm niet de vrijgave
    van een ander terugdraait. De vrijgaveschakelaar van de klant volgt in de
    ronde erna (`_async_schakelaar_volgen` in coach.py: wie het laatst bewoog
    wint).
    """
    store = async_get_store(hass)
    settings = await store.async_load()
    ready_set = set(settings.get("ready_devices") or [])
    nu_set = set(settings.get("ready_now") or [])
    if ready:
        ready_set.add(device_id)
        if now:
            nu_set.add(device_id)
        elif now is not None:
            nu_set.discard(device_id)
    else:
        ready_set.discard(device_id)
        nu_set.discard(device_id)
    settings = await store.async_save(
        {"ready_devices": sorted(ready_set), "ready_now": sorted(nu_set & ready_set)}
    )
    hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": settings})
    return settings


def coach_verversen(hass: HomeAssistant) -> None:
    """Meteen een ronde, zodat een knop op de kaart niet een minuut niets lijkt te doen."""
    coach = (hass.data.get(DOMAIN) or {}).get("coach")
    if coach is not None:
        try:
            coach.async_refresh()
        except Exception:  # noqa: BLE001 - dan pakt de volgende ronde het op
            _LOGGER.exception("kon de coach niet meteen laten kijken")


class CoachEntiteit:
    """Wat elke entiteit van een coach-apparaat gemeen heeft.

    Hij volgt het besluit dat de coach elke ronde op de eventbus zet
    (`EVENT_DECISION`) en de instellingen; hij rekent zelf niets. Schrijven
    alleen als `_kern` veranderde, anders staat de recorder elke minuut vol.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None, sleutel: str) -> None:
        self._device_id = str(device.get("id") or "")
        self._device = device
        self._stand: dict[str, Any] = dict(stand or {})
        self._attr_unique_id = f"{self._device_id}_{sleutel}"
        self._attr_translation_key = sleutel
        self._attr_device_info = apparaat_info(device)

    def _kern(self) -> Any:
        return None

    def _schrijf(self) -> None:
        if getattr(self, "hass", None) is not None:
            self.async_write_ha_state()

    def bijwerken_apparaat(self, device: dict[str, Any]) -> None:
        self._device = device
        self._schrijf()

    def bijwerken(self, stand: dict[str, Any]) -> None:
        oud = self._kern()
        self._stand = dict(stand)
        if self._kern() != oud:
            self._schrijf()


async def async_per_apparaat(hass: HomeAssistant, entry: Any, async_add_entities: Any, past: Any, maak: Any) -> None:
    """Voor elk apparaat waar `past(device)` op klopt de entiteiten van `maak(device, stand)`.

    Ook voor apparaten die later bijkomen: een nieuw apparaat in de instellingen
    of een eerste besluit over een apparaat dat er nog niet was.
    """
    from homeassistant.core import callback

    from .coach import async_get_coach
    from .const import EVENT_DECISION

    bekend: dict[str, list[Any]] = {}

    async def toevoegen() -> None:
        settings = await async_get_store(hass).async_load()
        nieuw: list[Any] = []
        for device in settings.get("devices") or []:
            device_id = device.get("id")
            if not device_id or not past(device):
                continue
            if device_id in bekend:
                for entiteit in bekend[device_id]:
                    entiteit.bijwerken_apparaat(device)
                continue
            entiteiten = list(maak(device, async_get_coach(hass).state.get(device_id)))
            bekend[device_id] = entiteiten
            nieuw.extend(entiteiten)
        if nieuw:
            async_add_entities(nieuw)

    await toevoegen()

    @callback
    def besluit(event: Any) -> None:
        data = dict(event.data or {})
        device_id = data.get("device")
        if device_id in bekend:
            for entiteit in bekend[device_id]:
                entiteit.bijwerken(data)
        else:
            hass.async_create_task(toevoegen())

    @callback
    def instellingen(_event: Any) -> None:
        hass.async_create_task(toevoegen())

    entry.async_on_unload(hass.bus.async_listen(EVENT_DECISION, besluit))
    entry.async_on_unload(hass.bus.async_listen(EVENT_SETTINGS_UPDATED, instellingen))


def oude_coach_opruimen(hass: HomeAssistant) -> None:
    """Het apparaat "DomotiApp Coach" van v0.100.0 weghalen zodra er niets meer aan hangt.

    Tot v0.110.0 hing de startsensor van elke vaatwasser aan één apparaat voor de
    coach zelf. Nu heeft elk apparaat zijn eigen; het oude bleef leeg achter in
    de lijst Apparaten. Een minuut na het opstarten, als de sensoren verhuisd
    zijn, en alleen als er werkelijk geen entiteit meer aan hangt.
    """
    try:
        from homeassistant.helpers import device_registry as dr, entity_registry as er
        from homeassistant.helpers.event import async_call_later
    except ImportError:  # pragma: no cover - het nagebouwde Home Assistant van de proeven
        return

    def opruimen(_now: Any) -> None:
        try:
            apparaten = dr.async_get(hass)
            oud = apparaten.async_get_device(identifiers={(DOMAIN, "coach")})
            if oud is None:
                return
            if er.async_entries_for_device(er.async_get(hass), oud.id, include_disabled_entities=True):
                return
            apparaten.async_remove_device(oud.id)
            _LOGGER.info("het lege apparaat DomotiApp Coach van voor v0.110.0 is weggehaald")
        except Exception:  # noqa: BLE001 - een leeg apparaat in de lijst is geen reden om te stoppen
            _LOGGER.exception("kon het oude apparaat DomotiApp Coach niet weghalen")

    async_call_later(hass, 60, opruimen)
