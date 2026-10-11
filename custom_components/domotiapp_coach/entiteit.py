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

from homeassistant.core import HomeAssistant, callback
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

    def __init__(
        self, device: dict[str, Any], stand: dict[str, Any] | None, sleutel: str,
        settings: dict[str, Any] | None = None,
    ) -> None:
        self._device_id = str(device.get("id") or "")
        self._device = device
        self._settings: dict[str, Any] = settings or {}
        self._stand: dict[str, Any] = dict(stand or {})
        self._attr_unique_id = f"{self._device_id}_{sleutel}"
        self._attr_translation_key = sleutel
        self._attr_device_info = apparaat_info(device)

    def _kern(self) -> Any:
        return None

    def _schrijf(self) -> None:
        if getattr(self, "hass", None) is not None:
            self.async_write_ha_state()

    def bijwerken_apparaat(self, device: dict[str, Any], settings: dict[str, Any] | None = None) -> None:
        self._device = device
        if settings is not None:
            self._settings = settings
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
                    entiteit.bijwerken_apparaat(device, settings)
                continue
            entiteiten = list(maak(device, async_get_coach(hass).state.get(device_id), settings))
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

    # Een callback, want anders draait Home Assistant hem in een eigen draad, en
    # daar mag het apparatenregister niet aangeraakt worden. Zo faalde het in
    # v0.110.0 bij de eigenaar op 11-10-2026: het oude apparaat bleef staan.
    @callback
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


# --- De laadpaal (v0.111.0) ----------------------------------------------------
#
# De eigenaar op 11-10-2026: een laadpaalkaart "met een afbeelding van de laadpaal
# en de noodzakelijke sensoren en aansturingsknoppen en instellingen zoals
# schema", en "in de laadpaal kaart moet ook de batterij % komen van de auto".

PAAL_ZON = frozenset({"surplus", "zon-modus"})
PAAL_STORING = frozenset({"fault", "error", "storing"})
PAAL_TEKST = {
    "laadt_zon": "Laadt op zon",
    "laadt": "Laadt",
    "wacht": "Wacht",
    "vol": "Vol",
    "geen_auto": "Geen auto",
    "pauze": "Pauze",
    "storing": "Storing",
}
# De modus van een beurt op de kaart, en hoe de coach hem kent (`async_mode`).
PAAL_MODI = {"planning": "goedkoopst", "snel": "snel", "continu": "continu", "zon": "zon"}


def met_zone(rauw: Any) -> str | None:
    """Een tijd van de coach (lokaal, zonder zone) als ISO met de zone van het huis."""
    if not rauw:
        return None
    from datetime import datetime

    from homeassistant.util import dt as dt_util

    try:
        moment = datetime.fromisoformat(str(rauw))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt_util.get_default_time_zone())
    return moment.isoformat()


def paal_stand(stand: dict[str, Any] | None) -> str:
    """De stand van een laadpaal als vaste sleutel voor een kaart."""
    if not stand:
        return "geen_auto"
    regel = str(stand.get("rule") or "").split("+")[0]
    if stand.get("paused"):
        return "pauze"
    if regel == "disconnected":
        return "geen_auto"
    if regel in PAAL_STORING:
        return "storing"
    if regel == "complete":
        return "vol"
    if stand.get("charge"):
        return "laadt_zon" if regel in PAAL_ZON else "laadt"
    return "wacht"


def paal_modus_actief(stand: dict[str, Any] | None) -> str:
    """Welke modus er deze beurt echt geldt, als sleutel van de select (v0.111.1).

    Een planning wint van Continu en Zon; alleen Snel gaat erboven (docs/laadpaal.md,
    "Een planning wint"). Of er deze beurt een planning geldt staat in `planned`
    (het venster van vandaag), niet in "schema aan": een weekschema kan vandaag uit
    staan, en dan geldt de modus wel. De lovelace-sessie op 11-10-2026: bij de
    eigenaar stond de paal op zon terwijl het schema won; welke knop is dan aan?
    """
    st = stand or {}
    modus = str(st.get("mode") or "goedkoopst")
    if modus == "snel":
        return "snel"
    if st.get("planned"):
        return "planning"
    return modus if modus in ("continu", "zon") else "planning"


def paal_modus_keuzes(stand: dict[str, Any] | None) -> list[str]:
    """Welke knoppen er deze beurt iets doen: met een planning alleen Planning en Snel."""
    if (stand or {}).get("planned"):
        return ["planning", "snel"]
    return list(PAAL_MODI)


def paal_blokken(stand: dict[str, Any] | None) -> list[dict[str, Any]]:
    """De tijdlijn van de coachkaart, met tijden met zone."""
    blokken = ((stand or {}).get("plan_ahead") or {}).get("blocks") or []
    return [
        {
            "start": met_zone(blok.get("start")),
            "end": met_zone(blok.get("end")),
            "charging": bool(blok.get("charging")),
            "kw": blok.get("kw"),
            "kwh": None if blok.get("kwh") is None else round(float(blok["kwh"]), 2),
            "solar_kwh": None if blok.get("solar_kwh") is None else round(float(blok["solar_kwh"]), 2),
            "price": blok.get("price"),
            "why": blok.get("why") or "",
        }
        for blok in blokken
    ]


def paal_tekst(stand: dict[str, Any] | None) -> str:
    """Wat de coach doet, kort, voor mensen. De kaart leest `stand`, niet dit."""
    sleutel = paal_stand(stand)
    tekst = PAAL_TEKST[sleutel]
    if sleutel == "wacht":
        volgende = next((b for b in ((stand or {}).get("plan_ahead") or {}).get("blocks") or []
                         if b.get("charging")), None)
        if volgende and volgende.get("start"):
            tekst = f"Wacht tot {str(volgende['start'])[11:16]}"
    return tekst


def paal_schema(settings: dict[str, Any], device_id: str) -> dict[str, Any]:
    """Het schema van een paal zoals de kaart het toont: aan, per dag, zeven dagen.

    Index 0 is maandag, zoals `weekday()` in Python en `days[].day` in de opslag.
    """
    entry = next(
        (e for e in (settings.get("strategy") or {}).get("schedules") or []
         if isinstance(e, dict) and e.get("device") == device_id),
        None,
    ) or {}
    per_dag = bool(entry.get("per_day"))
    elke_dag = str((entry.get("window") or {}).get("done_by") or "") or None
    dagen = [{"aan": not per_dag, "klaar_om": elke_dag} for _ in range(7)]
    if per_dag:
        for dag in entry.get("days") or []:
            nummer = dag.get("day")
            if isinstance(nummer, int) and 0 <= nummer <= 6:
                dagen[nummer] = {"aan": bool(dag.get("enabled")), "klaar_om": str(dag.get("done_by") or "") or None}
    return {"schema_aan": bool(entry.get("enabled")), "per_dag": per_dag, "klaar_om": elke_dag, "schema_dagen": dagen}


def paal_sessie(stand: dict[str, Any] | None) -> dict[str, Any] | None:
    """De lopende of de laatste laadbeurt, zoals op de coachkaart."""
    beurt = (stand or {}).get("session")
    if not beurt:
        return None
    return {
        "actief": bool(beurt.get("active")),
        "begin": met_zone(beurt.get("plugged_at")),
        "einde": None if beurt.get("active") else met_zone(beurt.get("ended")),
        "kwh": beurt.get("kwh"),
        "kosten": beurt.get("paid"),
        "zon_kwh": beurt.get("solar_kwh"),
        "soc_begin": beurt.get("soc_start"),
        "soc_eind": beurt.get("soc_end"),
    }


async def async_schema(hass: HomeAssistant, device_id: str, **velden: Any) -> None:
    """Eén veld van het schema van één apparaat, zoals `domotiapp_coach/device/schedule`."""
    from .storage import schema_bijwerken

    store = async_get_store(hass)
    settings = await store.async_load()
    strategy = schema_bijwerken(settings.get("strategy"), device_id, **velden)
    settings = await store.async_save({"strategy": strategy})
    hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": settings})
    coach_verversen(hass)
