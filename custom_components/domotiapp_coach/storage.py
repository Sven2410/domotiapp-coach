"""Persisted settings for DomotiApp Coach.

The panel owns its own settings screen, so the values live in HA's storage
rather than in the config entry: a customer changing a threshold on their phone
should not reload the integration, and the config entry stays empty enough that
adding the integration asks nothing at all.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import copy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .ontvangers import migreer_load_alert
from .const import (
    CHARGER_BRANDS,
    DEVICE_TYPES,
    VERVALLEN_TYPES,
    PROGRAMMA_TYPES,
    TEMPO_ONDERGRENS,
    BEURTEN_KEY,
    BEURTEN_MAX,
    BEURTEN_VERSION,
    DEFAULT_SETTINGS,
    DOMAIN,
    BERICHTEN_KEY,
    BERICHTEN_MAX,
    BERICHTEN_VERSION,
    ZON_BEWAAR_DAGEN,
    ZON_KEY,
    ZON_VERSION,
    MELDINGEN_KEY,
    MELDINGEN_MAX,
    MELDINGEN_VERSION,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .taal import t


def schema_bijwerken(
    strategy: dict[str, Any] | None,
    device_id: str,
    *,
    enabled: bool | None = None,
    priority: str | None = None,
    per_day: bool | None = None,
    window: dict[str, str] | None = None,
    days: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Het schema van één apparaat bijwerken, en verder niets aanraken.

    Sinds 27-08-2026 staat het schema van een apparaat niet meer in Strategie
    maar op zijn eigen kaart: de schuif en de voorrang op de kaart zelf, de
    tijden in een pop-up erachter. Alles wat over één apparaat gaat komt dus
    langs hier.

    Los van de handler in websocket.py zodat er een proef op kan zonder een
    draaiende Home Assistant. Wat hier telt is wat er níét gebeurt: alleen het
    genoemde apparaat verandert, alleen de meegestuurde velden veranderen, en
    het meegegeven `strategy` blijft zoals het was.

    `window` en `days` staan bewust naast elkaar in de opslag, ook als er maar
    één van de twee gebruikt wordt. Wie overstapt naar per dag en zich bedenkt,
    vindt zijn oude tijden dan nog staan; weggooien wat er niet gebruikt wordt
    zou dat kosten zonder dat het iets oplevert.
    """
    uit = dict(strategy or {})
    schedules = [
        dict(entry) for entry in (uit.get("schedules") or []) if isinstance(entry, dict)
    ]

    entry = next((row for row in schedules if row.get("device") == device_id), None)
    if entry is None:
        # Nog nooit iets ingesteld voor dit apparaat. Dan is de schuif of de
        # pop-up het eerste wat eraan gebeurt, en hoort er een schema te
        # ontstaan.
        entry = {"device": device_id, "enabled": False, "per_day": False}
        schedules.append(entry)

    if enabled is not None:
        entry["enabled"] = bool(enabled)
    if priority is not None:
        entry["priority"] = priority
    if per_day is not None:
        entry["per_day"] = bool(per_day)
    if window is not None:
        entry["window"] = dict(window)
    if days is not None:
        entry["days"] = [dict(day) for day in days]

    uit["schedules"] = schedules
    return uit


# Wat de bewoner zelf aan een apparaat mag instellen, per type (de eigenaar op
# 08-10 en 12-10-2026: "voorop staat dat de klant geen entiteiten moet kunnen
# kiezen"). Geen entiteit, geen merk, geen zekering of stroomgrens van de
# hardware: alleen hoe hij het wil hebben. Alles daarbuiten blijft van de
# installateur, via `settings/set`.
VOORKEUREN: dict[str, frozenset[str]] = {
    "laadpaal": frozenset({"charge_mode", "continuous_amps", "solar_start_percent"}),
    "vaatwasser": frozenset({"release_required"}),
}
VOORKEUREN_AUTO = frozenset({"target_percent", "wake_mode"})
# Een airco (v0.119.0): de temperatuur, waarop hij aan mag (v0.119.1), en de
# pauze. Het typeplaatje is van de installateur.
VOORKEUREN_AIRCO = frozenset({"target_c", "run_on", "paused"})
VOORKEUREN_ACCU = frozenset({
    "reserve_enabled", "reserve_percent", "trade", "grid_charge", "grid_charge_below", "trade_above",
    "weekly_full", "weekly_full_day",
    "holiday", "holiday_max_percent", "car_above", "fan_above_c",
    "wear_per_kwh", "wear_price", "wear_cycles",
})


def voorkeuren_bijwerken(
    devices: list[dict[str, Any]] | None, device_id: str, wijziging: dict[str, Any]
) -> list[dict[str, Any]]:
    """De voorkeuren van één apparaat bijwerken, en verder niets aanraken.

    Voor de pop-up "Instellen" achter de kaart (v0.114.0), die ook een bewoner
    zonder beheerrechten opent. Zoals `schema_bijwerken`: alleen het genoemde
    apparaat, alleen de meegestuurde velden, en de lijst die erin gaat blijft
    zoals hij was. Een veld dat niet bij dit type hoort is een fout en geen
    stille no-op: dan klopt het paneel niet, en dat moet je zien.
    """
    lijst = [dict(rij) for rij in (devices or []) if isinstance(rij, dict)]
    apparaat = next((rij for rij in lijst if rij.get("id") == device_id), None)
    if apparaat is None:
        raise KeyError(device_id)
    soort = apparaat.get("type")
    mag = VOORKEUREN.get(soort, frozenset())
    for veld, waarde in wijziging.items():
        if veld == "battery":
            if soort != "thuisbatterij" or not set(waarde) <= VOORKEUREN_ACCU:
                raise ValueError(t("{veld} hoort niet bij een {soort}", veld=veld, soort=soort))
            apparaat["battery"] = {**(apparaat.get("battery") or {}), **waarde}
        elif veld == "airco":
            if soort != "airco" or not set(waarde) <= VOORKEUREN_AIRCO:
                raise ValueError(t("{veld} hoort niet bij een {soort}", veld=veld, soort=soort))
            apparaat["airco"] = {**(apparaat.get("airco") or {}), **waarde}
        elif veld == "cars":
            if soort != "laadpaal":
                raise ValueError(t("{veld} hoort niet bij een {soort}", veld=veld, soort=soort))
            autos = [dict(auto) for auto in (apparaat.get("cars") or []) if isinstance(auto, dict)]
            for rij in waarde:
                velden = {k: v for k, v in rij.items() if k != "id"}
                if not set(velden) <= VOORKEUREN_AUTO:
                    raise ValueError(t("alleen laden tot en wekken horen bij de auto"))
                auto = next((a for a in autos if a.get("id") == rij.get("id")), None)
                if auto is None:
                    raise KeyError(rij.get("id"))
                auto.update(velden)
            apparaat["cars"] = autos
        elif veld in mag:
            apparaat[veld] = waarde
        else:
            raise ValueError(t("{veld} hoort niet bij een {soort}", veld=veld, soort=soort))
    return lijst


def _prune(defaults: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Drop keys that the current version no longer knows about.

    Settings written by an older version keep their old fields forever
    otherwise, and the panel hands the whole section back when it saves -- so a
    field that was removed here turns into "extra keys not allowed" on the next
    save, and the customer cannot save anything at all. Pruning on load is what
    makes removing a setting a safe thing to do.

    Only dictionaries are walked. Lists (the device list) are the caller's own
    shape and are validated on the way in instead.
    """
    out: dict[str, Any] = {}
    for key, default in defaults.items():
        if key not in data:
            out[key] = copy.deepcopy(default)
        elif isinstance(default, dict) and isinstance(data[key], dict):
            out[key] = _prune(default, data[key])
        else:
            out[key] = copy.deepcopy(data[key])
    return out


def _merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge `incoming` onto `base`, returning a new dict.

    Nested sections are merged key by key so the panel can save one section
    without having to send the whole document back. Lists (the device list) are
    replaced wholesale -- merging them by index would make removing a device
    impossible.
    """
    out = copy.deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _tempo_klopt(entry: dict[str, Any]) -> bool:
    """Of deze `car_pace`-rij een tempo is dat een paal kan leveren.

    Tot v0.66.0 kon er een tussenstand van een stroomsensor in belanden: thuis
    stond er op 17-09-2026 0,1 kW voor de band van 0 tot 10 procent, en daarmee
    rekende de klaar-tijdregel bijna twintig uur voor die ene band. Zo'n rij
    gaat er bij de eerstvolgende opslag uit; `_tempo_uit` in coach.py negeert
    hem tot het zover is.

    Net als een rij zonder `van` (v0.128.0): dat is het laagste punt van een
    band, dat tot dan voor de hele band gold. In de eerste woning stond zo 1,69
    kW voor 90 tot 100 procent, en de klaar-tijdregel rekende daarmee 4,85 uur
    waar het er 1,14 waren. De volgende beurt door die band meet het opnieuw.
    """
    try:
        float(entry["van"])
        return float(entry["kw"]) >= TEMPO_ONDERGRENS
    except (KeyError, TypeError, ValueError):
        return False


def _forget_removed_devices(data: dict[str, Any]) -> dict[str, Any]:
    """Drop everything that points at a device that no longer exists.

    Several settings name a device rather than containing it: the list of
    devices released for steering, the schedules that say when an appliance may
    run, and what is remembered about the session at a charging point. Delete
    the dishwasher under Apparaten and they would all stay behind -- invisible, because every screen only lists what is still
    there, and quietly back in force the day a new device happened to be given
    the same id.

    Done here rather than in the panel because the panel saves one section at a
    time: the screen that removes a device is not the screen that owns the
    schedules, and it must not send that section along.
    """
    known = {device.get("id") for device in data.get("devices", []) if isinstance(device, dict)}

    data["ready_devices"] = [item for item in data.get("ready_devices", []) if item in known]
    data["ready_now"] = [item for item in data.get("ready_now", []) if item in data["ready_devices"]]

    # Hetzelfde geldt voor wat er per laadpunt over de lopende sessie bewaard
    # is: welke auto eraan hangt, wat de bewoner over de accustand zei en welke
    # knoppen aanstonden. Verdwijnt het apparaat, dan hoort dat mee weg.
    for sleutel in ("active_cars", "car_soc", "car_pace", "car_efficiency", "sessions", "program_measured",
                    "boiler_learned", "battery_state"):
        data[sleutel] = [
            entry
            for entry in data.get(sleutel, [])
            if isinstance(entry, dict) and entry.get("device") in known
        ]

    # En een laadtempo onder wat een paal überhaupt kan leveren is geen meting
    # maar een ongeluk; tot v0.66.0 kon dat erin komen. Zie `TEMPO_ONDERGRENS`.
    data["car_pace"] = [
        entry for entry in data["car_pace"] if _tempo_klopt(entry)
    ]

    strategy = data.get("strategy")
    if isinstance(strategy, dict):
        strategy["schedules"] = [
            entry
            for entry in strategy.get("schedules", [])
            if isinstance(entry, dict) and entry.get("device") in known
        ]

    return data


def _migrate(stored: dict[str, Any]) -> dict[str, Any]:
    """Bring a settings file written by an older version up to date.

    Runs before the defaults are merged in, so it works on exactly what was on
    disk. Without this the rename below would simply drop the customer's
    setting on the floor: pruning removes keys the current version does not
    know, and it cannot tell a removed setting from a renamed one.
    """
    # v0.129.0: gas en water hebben elk een eigen onderdeel in het contract, met
    # eigen eerdere contracten. De prijs van nu en de prijzen in de eerdere
    # contracten gaan mee; zonder deze stap snoeit `_prune` ze weg.
    contract = stored.get("contract")
    if isinstance(contract, dict):
        for bron in ("gas", "water"):
            oud = contract.pop(f"{bron}_price", None)
            deel = contract.get(bron)
            if not isinstance(deel, dict):
                deel = contract[bron] = {}
            if oud and not deel.get("price"):
                deel["price"] = oud
            perioden = deel.setdefault("periods", [])
            for periode in contract.get("periods") or []:
                if not isinstance(periode, dict):
                    continue
                prijs = periode.pop(f"{bron}_price", None)
                if prijs:
                    perioden.append({"from": periode.get("from", ""), "to": periode.get("to", ""), "price": prijs})

        # Een reserve die een kale marktprijs was en geen marktprijs ernaast: die
        # wordt het marktveld, dat sinds v0.129.0 vanzelf de reserve is
        # (`_prijsbron` in coach.py) en daarnaast de controle en de teruglevering.
        dyn = contract.get("dynamic")
        if (isinstance(dyn, dict) and dyn.get("fallback_entity") and not dyn.get("market_entity")
                and dyn.get("fallback_source", "market") == "market" and dyn.get("source") == "all_in"):
            dyn["market_entity"] = dyn.pop("fallback_entity")

    # v0.43.0 kent nog maar twee fasekeuzes. "Allebei" bestond omdat een auto
    # die kan wisselen zich pas verraadt als hij laadt, maar dat maakte elke
    # voorspelling het traagste geval: 17 uur waar er 6 nodig waren. De eigenaar op
    # 29-08-2026: "het is gewoon 1 of 3 fase, dat is beter." Ze worden driefasig,
    # want dat is wat er aan een driefasige paal gebeurt. Klopt dat niet, dan
    # zegt `_fasetip` het zodra er een keer stroom loopt.
    for device in stored.get("devices") or []:
        if not isinstance(device, dict):
            continue
        for car in device.get("cars") or []:
            if isinstance(car, dict) and car.get("phases") == "both":
                car["phases"] = "three"

    # v0.70.0: de apparaatlijst en de merken van een laadpaal zijn korter
    # geworden. Een apparaat dat er al stond mag daar niet stil van veranderen:
    # zonder deze stap toont de keuzelijst in het paneel de eerste regel
    # ("Laadpaal") voor een type dat er niet meer in staat, en bij de volgende
    # opslag is een zwembadpomp een laadpaal. Het wordt dus "overig", met de
    # oude naam erbij zodat op het overzicht blijft staan wat het was.
    for device in stored.get("devices") or []:
        if not isinstance(device, dict):
            continue
        soort = device.get("type")
        if soort not in DEVICE_TYPES and soort in VERVALLEN_TYPES:
            device["type"] = "overig"
            if not (device.get("name") or "").strip():
                device["name"] = VERVALLEN_TYPES[soort]
        # En een laadpaal van het merk "overig": die kon de coach nooit sturen,
        # dat was juist wat het merk betekende. Hij blijft een laadpaal die
        # gemeten wordt; alleen het merk en de vink "mag sturen" gaan eraf,
        # zodat er niets beloofd wordt wat er niet is. Zijn autoprofielen en
        # zijn schema blijven staan.
        if device.get("type") == "laadpaal" and device.get("brand") not in ("", *CHARGER_BRANDS):
            device["brand"] = ""
            device["controllable"] = False

    # v0.87.0: een laadpaal kent een modus voor als er geen planning is. Wat
    # er al stond laadde zonder schema op de goedkoopste bekende uren, en dat
    # blijft zo; alleen een nieuwe paal begint op zon (het paneel geeft dat mee).
    for device in stored.get("devices") or []:
        if isinstance(device, dict) and device.get("type") == "laadpaal" and not device.get("charge_mode"):
            device["charge_mode"] = "goedkoopst"

    # v0.52.0: de zekeringmelding en haar ontvangers gaan naar Meldingen.
    migreer_load_alert(stored)

    strategy = stored.get("strategy")
    if not isinstance(strategy, dict):
        return stored

    # v0.9.0 had a single "klaar om" time per device; v0.10.0 has a window of
    # three times, of which that one is `done_by`.
    if "deadlines" in strategy and "schedules" not in strategy:
        strategy["schedules"] = [
            {
                "device": entry.get("device", ""),
                "enabled": bool(entry.get("enabled")),
                "per_day": False,
                "window": {"not_before": "", "start_by": "", "done_by": entry.get("time", "")},
                "days": [],
            }
            for entry in strategy.get("deadlines", [])
            if isinstance(entry, dict) and entry.get("device")
        ]

    return stored


class SettingsStore:
    """Load, cache and save the panel's settings."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up the store without touching disk yet."""
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] | None = None

    async def async_load(self) -> dict[str, Any]:
        """Return the settings, filling in anything a newer version added."""
        if self._data is None:
            stored = _migrate(await self._store.async_load() or {})
            # Defaults are merged in on every load, so a settings file written by
            # an older version still gains the keys a newer one expects -- and
            # pruned afterwards, so it loses the ones that are gone.
            self._data = _forget_removed_devices(
                _prune(DEFAULT_SETTINGS, _merge(DEFAULT_SETTINGS, stored))
            )
        return copy.deepcopy(self._data)

    async def async_save(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Merge `changes` into the settings, persist them and return the result."""
        current = await self.async_load()
        self._data = _forget_removed_devices(_prune(DEFAULT_SETTINGS, _merge(current, changes)))
        await self._store.async_save(self._data)
        return copy.deepcopy(self._data)


def async_get_store(hass: HomeAssistant) -> SettingsStore:
    """Return the one store for this Home Assistant instance."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "store" not in domain_data:
        domain_data["store"] = SettingsStore(hass)
    return domain_data["store"]


class MeldingenStore:
    """De meldingen die de coach verstuurd heeft, op volgorde, de laatste achteraan.

    Los van de instellingen, want die gaan bij elke wijziging in hun geheel over
    de websocket en driehonderd meldingen horen daar niet in mee. Eén bestand,
    nooit groter dan `MELDINGEN_MAX` regels; de oudste valt eraf.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, MELDINGEN_VERSION, MELDINGEN_KEY)
        self._items: list[dict[str, Any]] | None = None

    async def async_list(self) -> list[dict[str, Any]]:
        if self._items is None:
            data = await self._store.async_load()
            items = (data or {}).get("items") if isinstance(data, dict) else None
            self._items = [
                item for item in (items or []) if isinstance(item, dict) and item.get("message")
            ]
        return list(self._items)

    async def async_add(
        self, message: str, at: datetime, kind: str = "melding",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Een regel erbij. `kind` is "melding" (ging ook naar de telefoon),
        "kritiek" (idem, en de bewoner moet er iets mee) of "besluit" (alleen
        hier: wat de coach deed en waarom).

        `extra` is bij een besluit wat de tijdlijn in Historie nodig heeft
        (v0.115.0): het apparaat, de regel, de stand, of het laadt. De tekst
        alleen is daar te los voor; zie `tijdlijn.js`.
        """
        items = await self.async_list()
        entry = {"at": at.replace(microsecond=0).isoformat(), "message": message, "kind": kind}
        entry.update({sleutel: waarde for sleutel, waarde in (extra or {}).items() if waarde is not None})
        items.append(entry)
        self._items = items[-MELDINGEN_MAX:]
        await self._store.async_save({"items": self._items})
        return entry


class BerichtenStore:
    """De berichtenbox (v0.130.0): wat de bewoner zelf moet doen, gelezen of niet.

    Los van de geschiedenis onder Meldingen: daar staat alles wat de coach
    meldde en besloot, hier alleen wat iemand iets laat doen, met een vinkje
    gelezen. Op `sleutel` uniek: een herinnering die al eens kwam, komt niet
    nog eens, ook niet na een herstart. Nooit meer dan `BERICHTEN_MAX`.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, BERICHTEN_VERSION, BERICHTEN_KEY)
        self._items: list[dict[str, Any]] | None = None

    async def async_list(self) -> list[dict[str, Any]]:
        if self._items is None:
            data = await self._store.async_load()
            items = (data or {}).get("items") if isinstance(data, dict) else None
            self._items = [item for item in (items or []) if isinstance(item, dict) and item.get("id")]
        return [dict(item) for item in self._items]

    async def async_add(self, bericht: dict[str, Any], at: datetime) -> dict[str, Any] | None:
        """Een bericht erbij, of None als er al een met deze sleutel is."""
        items = await self.async_list()
        sleutel = bericht.get("sleutel") or ""
        if sleutel and any(item.get("key") == sleutel for item in items):
            return None
        entry = {
            "id": f"{int(at.timestamp())}-{len(items)}",
            "at": at.replace(microsecond=0).isoformat(),
            "key": sleutel,
            "kind": bericht.get("soort") or "",
            "title": bericht.get("titel") or "",
            "body": bericht.get("tekst") or "",
            "read": False,
        }
        items.append(entry)
        self._items = items[-BERICHTEN_MAX:]
        await self._store.async_save({"items": self._items})
        return entry

    async def async_read(self, bericht_id: str | None) -> list[dict[str, Any]]:
        """Als gelezen markeren: dat ene bericht, of alles bij None."""
        items = await self.async_list()
        for item in items:
            if bericht_id is None or item.get("id") == bericht_id:
                item["read"] = True
        self._items = items
        await self._store.async_save({"items": self._items})
        return [dict(item) for item in items]


class BeurtenStore:
    """Elke laadbeurt, met wat hij kostte en wat hij bespaarde.

    De eigenaar op 05-09-2026: "Kunnen we ergens een overzichtje maken wat we hebben
    bespaard? Per dag, week, maand, jaar, van elk apparaat. Dat is natuurlijk
    het belangrijkste voor de klant." Het ijkpunt is de prijs op het moment
    van inpluggen: "bereken die prijs wanneer die gestopt is en gewacht heeft
    met laden op een goedkoop moment. Dus de prijs vanaf het inpluggen."

    Eén regel per beurt, op `id` (apparaat plus inplugmoment). Een lopende
    beurt staat er ook al in, met `complete` op false, zodat een herstart hem
    niet kwijtraakt. De coach werkt hem elke paar minuten bij.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, BEURTEN_VERSION, BEURTEN_KEY)
        self._items: list[dict[str, Any]] | None = None

    async def async_list(self) -> list[dict[str, Any]]:
        if self._items is None:
            data = await self._store.async_load()
            items = (data or {}).get("items") if isinstance(data, dict) else None
            self._items = [
                item for item in (items or []) if isinstance(item, dict) and item.get("id")
            ]
        return list(self._items)

    async def async_upsert(self, entry: dict[str, Any]) -> dict[str, Any]:
        items = await self.async_list()
        items = [item for item in items if item.get("id") != entry["id"]]
        items.append(entry)
        items.sort(key=lambda item: str(item.get("plugged_at") or ""))
        self._items = items[-BEURTEN_MAX:]
        await self._store.async_save({"items": self._items})
        return entry

    async def async_open(self) -> list[dict[str, Any]]:
        """De beurten die nog lopen, voor na een herstart."""
        return [item for item in await self.async_list() if not item.get("complete")]

    async def async_remove(self, entry_id: str) -> None:
        """Een regel weghalen, bijvoorbeeld als het terugrekenen het
        inplugmoment en dus de sleutel van een lopende beurt verandert."""
        items = await self.async_list()
        rest = [item for item in items if item.get("id") != entry_id]
        if len(rest) != len(items):
            self._items = rest
            await self._store.async_save({"items": self._items})


def met_soort(items: list[dict[str, Any]], devices: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Elke beurt met zijn soort: "laden" of "programma".

    Een beurt van voor v0.57.2 zegt het niet zelf, maar het apparaat wel:
    een vaatwasser draait programma's. De eigenaar op 07-09-2026, bij de beurt
    van die ochtend onder Bespaard: "ik zie nog dingen terugkomen van de
    laadpaal." Zonder deze aanvulling kreeg die beurt de woorden van de
    paal, ingeplugd en geladen.
    """
    typen = {
        d.get("id"): d.get("type") for d in (devices or []) if isinstance(d, dict) and d.get("id")
    }
    uit = []
    for item in items:
        if item.get("kind"):
            uit.append(item)
            continue
        soort = "programma" if typen.get(item.get("device")) in PROGRAMMA_TYPES else "laden"
        uit.append({**item, "kind": soort})
    return uit


def async_get_beurten(hass: HomeAssistant) -> BeurtenStore:
    """De ene lijst laadbeurten van deze installatie."""
    data = hass.data.setdefault(DOMAIN, {})
    if "beurten" not in data:
        data["beurten"] = BeurtenStore(hass)
    return data["beurten"]


def async_get_berichten(hass: HomeAssistant) -> BerichtenStore:
    """De ene berichtenbox van deze installatie (v0.130.0)."""
    data = hass.data.setdefault(DOMAIN, {})
    if "berichten" not in data:
        data["berichten"] = BerichtenStore(hass)
    return data["berichten"]


def async_get_meldingen(hass: HomeAssistant) -> MeldingenStore:
    """De ene geschiedenis van deze installatie, net als `async_get_store`."""
    data = hass.data.setdefault(DOMAIN, {})
    if "meldingen" not in data:
        data["meldingen"] = MeldingenStore(hass)
    return data["meldingen"]


class ZonStore:
    """Wat het weerbericht per uur over de bewolking zei (v0.151.0), voor de zon zonder panelen.

    Per uur in UTC de bewolking in procent, zoals het weer van Home Assistant die op dat
    uur gaf. Daaruit leert de coach welk deel van een heldere dag er bij welke bewolking
    komt (`zonfactor` in zon.py). Los van de instellingen, want die gaan bij elke wijziging
    over de websocket. Nooit ouder dan `ZON_BEWAAR_DAGEN`.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, ZON_VERSION, ZON_KEY)
        self._uren: dict[str, float] | None = None

    async def async_bewolking(self) -> dict[str, float]:
        if self._uren is None:
            data = await self._store.async_load()
            uren = (data or {}).get("bewolking") if isinstance(data, dict) else None
            self._uren = {
                str(k): float(v) for k, v in (uren or {}).items() if isinstance(v, (int, float))
            }
        return dict(self._uren)

    async def async_noteer(self, uur: datetime, bewolking: float) -> None:
        """De bewolking van dit uur (UTC); een uur dat er al staat blijft staan."""
        uren = await self.async_bewolking()
        sleutel = uur.isoformat()
        if sleutel in uren:
            return
        uren[sleutel] = round(float(bewolking), 1)
        grens = (uur - timedelta(days=ZON_BEWAAR_DAGEN)).isoformat()
        self._uren = {k: v for k, v in uren.items() if k >= grens}
        await self._store.async_save({"bewolking": self._uren})


def async_get_zon(hass: HomeAssistant) -> ZonStore:
    """De ene bewolkingsgeschiedenis van deze installatie (v0.151.0)."""
    data = hass.data.setdefault(DOMAIN, {})
    if "zon" not in data:
        data["zon"] = ZonStore(hass)
    return data["zon"]
