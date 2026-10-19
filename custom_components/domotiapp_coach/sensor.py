"""Wanneer de coach een apparaat met een programma wil starten, als sensor.

De eigenaar op 26-09-2026. Thuis werd de vaatwasser om 12:16 vrijgegeven met
de schakelaar op de keukenkaart, de coach plande 14:00, en om 13:12 ging hij
met de hand aan: op die kaart stond nergens dat er een plan was. "Dan wil ik
dat er op de vaatwasser kaart komt te staan wanneer de coach van plan is om
de vaatwasser aan te zetten." Op de keuze tussen een sensor en een kaart die
het de coach zelf vraagt koos hij de sensor: die werkt in elke kaart en in
een automatisering.

Eén sensor per apparaat met een programma (`PROGRAMMA_TYPES`), bij elke
klant die er een heeft, met de naam die hij het apparaat gaf. De toestand is
wanneer de coach hem start, zoals het op de kaart staat: "om 14:00", "morgen
om 09:00", "zondag om 09:00", of "nu". De eigenaar op 26-09-2026, na v0.100.0,
waar de toestand een tijdstempel was die Home Assistant als "over 2 uur"
toont: "de coach beslist toch immers zelf wanneer hij gaat starten en dat moet
de sensor laten zien, dus een tijd, en is het morgen dan morgen om." Leeg als er
niets gepland is: niet vrijgegeven, of hij draait al. Het tijdstip zelf staat
in het attribuut `start`, voor een automatisering of een kaart die zelf wil
rekenen. Wat de coach erbij zegt staat ook in de attributen, en de
vrijgaveschakelaar zoals de klant hem bij Apparaten invulde (of niets), zodat
een kaart die die schakelaar al kent de sensor zelf kan vinden.

De sensor rekent niets; hij volgt het besluit dat de coach elke ronde op de
eventbus zet (`EVENT_DECISION`, `_besluit_melden` in coach.py).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import EVENT_DECISION, EVENT_SETTINGS_UPDATED, HOLIDAY_MAX_DEFAULT, PROGRAMMA_TYPES
from .entiteit import (
    CONTRACT, CoachEntiteit, apparaat_info, async_per_apparaat, entiteiten_van, met_zone,
    oude_coach_opruimen, paal_apparaat, paal_blokken, paal_modus_actief, paal_modus_keuzes, paal_schema, paal_sessie,
    paal_stand, paal_tekst, accu_alleen_lezen, accu_apparaat, accu_capaciteit, accu_opgeleverd, accu_plan,
    accu_stand, programma_alleen_lezen,
    AIRCO_STAND_NAMEN, airco_stand, ruimte_naam,
)
from .planner import _dag_om
from .storage import async_get_store
from .taal import t

# Besluiten waarin de coach nu start: het moment is er, dus geen klok.
NU_STARTEN = frozenset({"cheapest-start", "start-now", "start-by", "deadline"})


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


def start_tekst(stand: dict[str, Any] | None, now: datetime) -> str | None:
    """Wanneer hij start, in de woorden van de kaart, of None.

    `now` is de lokale klok zonder tijdzone, zoals de coach rekent: "morgen"
    hangt ervan af, en na middernacht wordt "morgen om 09:00" vanzelf "om
    09:00", want het besluit komt elke ronde langs.
    """
    if not stand or stand.get("running"):
        return None
    if stand.get("rule") in NU_STARTEN and stand.get("charge"):
        # Precies "now" in het Engels: de programmakaart van DomotiApp Lovelace
        # herkende tot 0.80.2 het moment aan deze toestand (`/^(nu|now)$/i`).
        return t("nu")
    moment = gepland_om(stand)
    if moment is None:
        return None
    return _dag_om(moment.replace(tzinfo=None), now)


def programma_stand(stand: dict[str, Any] | None) -> str:
    """De stand van een apparaat met een programma, als vaste sleutel voor een kaart (v0.110.0)."""
    if not stand:
        return "niet_vrijgegeven"
    if stand.get("running"):
        return "draait"
    if stand.get("rule") == "finished":
        return "klaar"
    if not stand.get("released"):
        return "niet_vrijgegeven"
    if stand.get("rule") in NU_STARTEN and stand.get("charge"):
        return "start_nu"
    return "gepland"


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
    oude_coach_opruimen(hass, entry.entry_id)

    # De laadpaal (v0.111.0): de sensor van de coach voor de laadpaalkaart.
    await async_per_apparaat(
        hass, entry, async_add_entities,
        lambda device: device.get("type") == "laadpaal",
        lambda device, stand, settings: [LaadpaalCoachSensor(device, stand, settings)],
    )

    # De thuisbatterij (v0.112.0): de sensor van de coach voor de batterijkaart.
    await async_per_apparaat(
        hass, entry, async_add_entities,
        lambda device: device.get("type") == "thuisbatterij",
        lambda device, stand, settings: [BatterijCoachSensor(device, stand, settings)],
    )

    # De airco (v0.119.0): de sensor van de coach voor de airco-kaart.
    await async_per_apparaat(
        hass, entry, async_add_entities,
        lambda device: device.get("type") == "airco",
        lambda device, stand, settings: [AircoCoachSensor(device, stand, settings)],
    )


class StartOmSensor(SensorEntity):
    """Wanneer de coach dit apparaat wil starten.

    Sinds v0.110.0 op een eigen apparaat in Home Assistant (`apparaat_info`), en
    de sensor van de coach voor dat apparaat in het contract met de kaarten:
    zie `entiteit.py`.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "start"
    _attr_icon = "mdi:clock-start"
    # De zinnen van de coach veranderen soms per ronde (wat nu starten zou
    # kosten); die horen niet elke minuut in de recorder.
    _unrecorded_attributes = frozenset({"reason", "plan", "entiteiten"})

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None) -> None:
        self._device_id = device["id"]
        # "_start_om" uit v0.100.0, toen de naam nog "start om" was. Blijft zo:
        # een andere unique_id is een nieuwe entiteit en een verweesde oude.
        self._attr_unique_id = f"{device['id']}_start_om"
        self._attr_device_info = apparaat_info(device)
        self._stand: dict[str, Any] = dict(stand or {})
        self._schakelaar: str | None = None
        self._soort = ""
        self._entiteiten: dict[str, str] = {}
        self._alleen_lezen = False
        self._zet_apparaat(device)

    def _zet_apparaat(self, device: dict[str, Any]) -> None:
        self._schakelaar = (device.get("entities") or {}).get("release_switch") or None
        self._soort = str(device.get("type") or "")
        self._entiteiten = entiteiten_van(device)
        self._alleen_lezen = programma_alleen_lezen(device)

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
    def native_value(self) -> str | None:
        return start_tekst(self._stand, dt_util.as_local(dt_util.utcnow()).replace(tzinfo=None))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        start = gepland_om(self._stand)
        return {
            "start": start.isoformat() if start is not None else None,
            "reason": self._stand.get("reason") or "",
            "plan": self._stand.get("plan") or "",
            "rule": self._stand.get("rule") or "",
            "released": bool(self._stand.get("released")),
            "running": bool(self._stand.get("running")),
            "release_switch": self._schakelaar,
            # Het contract met de kaarten (v0.110.0), zie entiteit.py.
            "contract": CONTRACT,
            "type": self._soort,
            "stand": programma_stand(self._stand),
            "vrijgegeven": bool(self._stand.get("released")),
            "nu": bool(self._stand.get("start_now")),
            "klaar_om": met_zone(self._stand.get("deadline")),
            # Is de klaar-tijd van vandaag voorbij, dan de dag waar hij naar
            # opschuift ("morgen"): het paneel zegt dan "Ingeruimd, morgen starten".
            "later": self._stand.get("later") or None,
            "entiteiten": dict(self._entiteiten),
            # Volgt de coach hem alleen (v0.127.0): dan start hij hem nooit, zijn
            # de knoppen en `vrijgegeven` niet beschikbaar, en zegt `stand`
            # alleen draait, klaar of niet_vrijgegeven.
            "alleen_lezen": self._alleen_lezen,
        }


class LaadpaalCoachSensor(CoachEntiteit, SensorEntity):
    """Wat de coach met deze laadpaal doet, voor de laadpaalkaart (v0.111.0).

    De toestand is een korte zin ("Laadt op zon", "Wacht tot 20:00"); de kaart
    leest de attributen. Zie entiteit.py en docs/laadpaal.md voor het contract.
    """

    _attr_icon = "mdi:ev-station"
    _unrecorded_attributes = frozenset({"reason", "plan", "schema_dagen", "entiteiten", "sessie"})

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None, settings: dict[str, Any]) -> None:
        super().__init__(device, stand, "coach", settings)

    def _kern(self) -> Any:
        return (self.native_value, repr(self.extra_state_attributes))

    @property
    def native_value(self) -> str:
        return paal_tekst(self._stand)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        st = self._stand
        modus = str(st.get("mode") or "goedkoopst")
        plan = st.get("plan_ahead") or {}
        schema = paal_schema(self._settings, self._device_id)
        fabrikant, model = paal_apparaat(self.hass, self._device) if self.hass is not None else ("", "")
        return {
            "contract": CONTRACT,
            "type": "laadpaal",
            "stand": paal_stand(st),
            "rule": st.get("rule") or "",
            "amps": st.get("amps"),
            "reason": st.get("reason") or "",
            "brand": str(self._device.get("brand") or ""),
            # Wat de integratie van de paal zelf zegt, voor de foto (v0.112.0).
            "paal_fabrikant": fabrikant,
            "paal_model": model,
            "soc": st.get("soc_now"),
            "soc_geschat": bool(st.get("soc_estimated")),
            "actieradius_km": st.get("range_km"),
            "target_percent": st.get("target_percent"),
            "doel_beurt": bool(st.get("target_session")),
            "modus": "planning" if modus == "goedkoopst" else modus,
            "modus_beurt": bool(st.get("mode_session")) or modus == "snel",
            # Welke modus er echt geldt en welke knoppen iets doen (v0.111.1): een
            # planning wint van Continu en Zon.
            "modus_actief": paal_modus_actief(st),
            "modus_keuzes": paal_modus_keuzes(st),
            "planning_nu": bool(st.get("planned")),
            "pauze": bool(st.get("paused")),
            "expected_done": met_zone(plan.get("expected_done")),
            "kwh_needed": plan.get("kwh_needed"),
            "plan": paal_blokken(st),
            "sessie": paal_sessie(st),
            "schema_aan": schema["schema_aan"],
            "per_dag": schema["per_dag"],
            "schema_dagen": schema["schema_dagen"],
            "klaar_om_volgende": met_zone(plan.get("deadline")),
            "entiteiten": {**entiteiten_van(self._device), **self._auto_entiteiten()},
        }

    def _auto_entiteiten(self) -> dict[str, str]:
        """De accusensor en de actieradius van de auto, uit het autoprofiel."""
        auto = next(iter(self._device.get("cars") or []), None) or {}
        uit = {}
        if auto.get("soc_entity"):
            uit["soc"] = str(auto["soc_entity"])
        if auto.get("range_entity"):
            uit["range"] = str(auto["range_entity"])
        return uit


class BatterijCoachSensor(CoachEntiteit, SensorEntity):
    """Wat de coach met deze thuisbatterij doet, voor de batterijkaart (v0.112.0).

    De toestand is de naam van de stand ("Nul op de meter"); de kaart leest de
    attributen. Zie entiteit.py en docs/batterij.md voor het contract.
    """

    _attr_icon = "mdi:home-battery"
    _unrecorded_attributes = frozenset({"reason", "plan", "entiteiten"})

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None, settings: dict[str, Any]) -> None:
        super().__init__(device, stand, "coach", settings)

    def _kern(self) -> Any:
        return (self.native_value, repr(self.extra_state_attributes))

    @property
    def native_value(self) -> str:
        # Een batterij die de coach alleen uitleest heeft geen stand (v0.123.1);
        # leeg las als een fout.
        if not self._stand.get("mode_name") and accu_alleen_lezen(self._device):
            return t("Alleen uitlezen")
        # De naam uit `STAND_NAMEN`, in de taal van nu; een naam die al vertaald
        # is komt er ongewijzigd door.
        return t(str(self._stand.get("mode_name") or ""))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        st = self._stand
        eigen = self._device.get("battery") or {}
        temperatuur = None
        entiteit = (self._device.get("entities") or {}).get("temperature")
        staat = self.hass.states.get(entiteit) if self.hass is not None and entiteit else None
        try:
            temperatuur = float(staat.state) if staat is not None else None
        except (TypeError, ValueError):
            temperatuur = None
        override = "vol" if st.get("boost") else ("leeg" if st.get("drain_to") is not None else None)
        fabrikant, model = accu_apparaat(self.hass, self._device) if self.hass is not None else ("", "")
        return {
            "contract": CONTRACT,
            "type": "thuisbatterij",
            "stand": accu_stand(st),
            # Wat de integratie van de batterij zelf zegt, voor de foto (v0.112.1).
            "accu_fabrikant": fabrikant,
            "accu_model": model,
            # Hoe de coach hem kent (v0.123.0), zoals `brand` bij de laadpaal, en of
            # hij hem alleen uitleest: een Growatt altijd, een ander merk als hij
            # niet mag sturen. Dan is er geen stand, geen plan en geen accustand
            # hierin; de kaart leest die uit `entiteiten`, en de knoppen doen niets.
            "brand": str(self._device.get("brand") or ""),
            "alleen_lezen": accu_alleen_lezen(self._device),
            # De capaciteit in kWh (v0.123.0): de sensor, anders wat er ingetypt is.
            "capaciteit": accu_capaciteit(self.hass, self._device),
            "zelf": bool(st.get("self_zero")),
            "soc": st.get("soc"),
            "reason": st.get("reason") or "",
            "temperatuur": temperatuur,
            "plan": accu_plan(st),
            **accu_opgeleverd(self._settings, self._device_id, st),
            "override": override,
            "leeg_tot": st.get("drain_to"),
            "vakantie": bool(eigen.get("holiday")),
            # Ook als hij uit staat, en met de grens waarmee de coach rekent als
            # de installateur er geen invulde (v0.112.1).
            "vakantie_max": vakantie_max(eigen),
            "reserve": eigen.get("reserve_percent") if eigen.get("reserve_enabled") else None,
            "ondergrens": st.get("floor"),
            "entiteiten": entiteiten_van(self._device),
        }


def vakantie_max(eigen: dict[str, Any]) -> float:
    """De bovengrens van de vakantiestand, zoals de coach hem gebruikt (`_vakantie`)."""
    try:
        return float(eigen.get("holiday_max_percent") or HOLIDAY_MAX_DEFAULT)
    except (TypeError, ValueError):
        return float(HOLIDAY_MAX_DEFAULT)


class AircoCoachSensor(CoachEntiteit, SensorEntity):
    """Wat de coach met deze airco doet, voor de airco-kaart (v0.119.0).

    De toestand is de stand in woorden ("Aan op zon"); de kaart leest de
    attributen, en vindt dit apparaat bij zijn climate via `klimaat`. Zie
    entiteit.py en docs/airco.md voor het contract.
    """

    _attr_icon = "mdi:air-conditioner"
    _unrecorded_attributes = frozenset({"reason", "entiteiten"})

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None, settings: dict[str, Any]) -> None:
        super().__init__(device, stand, "coach", settings)

    def _kern(self) -> Any:
        return (self.native_value, repr(self.extra_state_attributes))

    @property
    def native_value(self) -> str:
        return t(AIRCO_STAND_NAMEN[airco_stand(self._stand)])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        st = self._stand
        eigen = self._device.get("airco") or {}
        return {
            "contract": CONTRACT,
            "type": "airco",
            "stand": airco_stand(st),
            # De stand die de coach koos of zou kiezen: "heat" of "cool".
            "modus": st.get("modus"),
            "reason": st.get("reason") or "",
            "klimaat": (self._device.get("entities") or {}).get("climate"),
            "ruimte": ruimte_naam(self._settings, self._device),
            "kamer": st.get("room_c"),
            "doel": st.get("target_c"),
            # Waarop hij aan mag: "zon", "goedkoop" of "beide" (v0.119.1), de
            # select `aan_op`.
            "aan_op": st.get("run_on") or "zon",
            "pauze": bool(eigen.get("paused")),
            # Bij een vast contract is er geen goedkoper uur, en zegt de keuze
            # niets: de kaart kan de select dan verbergen.
            "dynamisch": bool(st.get("dynamic")),
            "bewoner_tot": met_zone(st.get("resident_until")),
            "entiteiten": entiteiten_van(self._device),
        }
