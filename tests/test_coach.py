"""De laag die sensoren leest en opdrachten stuurt, met een nagebouwde HA.

Home Assistant staat hier niet geïnstalleerd, dus de handvol namen die coach.py
eruit gebruikt worden nagemaakt. Wat er getest wordt is de bedrading: welke
vlaggen de coach aan de planner meegeeft, wat hij naar de laadpaal stuurt en wat
hij onthoudt of juist vergeet.
"""

import asyncio
import datetime as dt
import importlib.util
import pathlib
import sys
import types

# Home Assistant draait op een verse Python en `coach.py` gebruikt dingen die
# daarbij horen, zoals `asyncio.timeout` (3.11). Apple levert bij zijn
# ontwikkelaarsgereedschappen nog een 3.9 mee, en die geeft midden in een proef
# een AttributeError die eruitziet als een bug in de coach. Dat is het niet.
if sys.version_info < (3, 11):
    raise SystemExit(
        "Deze proeven willen Python 3.11 of nieuwer; hier draait "
        f"{sys.version_info.major}.{sys.version_info.minor} "
        f"vanuit {sys.executable}. "
        "Op macOS: `brew install python`, daarna een nieuw terminalvenster. "
        "Home Assistant zelf draait op 3.13, dus de coach ziet een 3.9 nooit."
    )


# De code die beproefd wordt, gevonden vanaf dit bestand. Geen absoluut pad,
# want deze repo staat op de ene machine in C:\dev en op de andere in ~/dev.
BRON = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "domotiapp_coach"

# --- Home Assistant, net genoeg om te draaien ------------------------------

ha = types.ModuleType("homeassistant")
core = types.ModuleType("homeassistant.core")


class HomeAssistant:  # noqa: D101
    pass


core.HomeAssistant = HomeAssistant
core.callback = lambda func: func

excepties = types.ModuleType("homeassistant.exceptions")


class ServiceNotFound(Exception):  # noqa: D101
    pass


excepties.ServiceNotFound = ServiceNotFound

helpers = types.ModuleType("homeassistant.helpers")
gebeurtenis = types.ModuleType("homeassistant.helpers.event")
gebeurtenis.async_track_state_change_event = lambda *a, **k: (lambda: None)
gebeurtenis.async_track_time_interval = lambda *a, **k: (lambda: None)
opslag = types.ModuleType("homeassistant.helpers.storage")


class Store:  # noqa: D101
    def __init__(self, *a, **k):
        self._data = None

    async def async_load(self):
        return self._data

    async def async_save(self, data):
        self._data = data


opslag.Store = Store

util = types.ModuleType("homeassistant.util")
dtutil = types.ModuleType("homeassistant.util.dt")
dtutil.now = lambda: dt.datetime.now()
dtutil.utcnow = lambda: dt.datetime.now(dt.timezone.utc)
dtutil.as_local = lambda moment: moment


def _lees_tijd(waarde):
    try:
        return dt.datetime.fromisoformat(waarde)
    except (TypeError, ValueError):
        return None


dtutil.parse_datetime = _lees_tijd
util.dt = dtutil

sys.modules.update({
    "homeassistant": ha,
    "homeassistant.core": core,
    "homeassistant.exceptions": excepties,
    "homeassistant.helpers": helpers,
    "homeassistant.helpers.event": gebeurtenis,
    "homeassistant.helpers.storage": opslag,
    "homeassistant.util": util,
    "homeassistant.util.dt": dtutil,
})

# --- het pakket zelf, zonder __init__.py te draaien ------------------------

pakket = types.ModuleType("domotiapp_coach")
pakket.__path__ = [str(BRON)]
sys.modules["domotiapp_coach"] = pakket


def laad(naam):
    spec = importlib.util.spec_from_file_location(
        f"domotiapp_coach.{naam}", BRON / f"{naam}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"domotiapp_coach.{naam}"] = module
    spec.loader.exec_module(module)
    return module


laad("const")
planner = laad("planner")
storage = laad("storage")
coachmod = laad("coach")

# --- een huis om in te meten ------------------------------------------------

FOUT = 0
GOED = 0


def controle(naam, gelukt, uitleg=""):
    global FOUT, GOED
    if gelukt:
        GOED += 1
    else:
        FOUT += 1
        print(f"  FOUT  {naam}: {uitleg}")


class Staat:
    def __init__(self, waarde):
        self.state = waarde


class Staten:
    def __init__(self, waarden):
        self.waarden = dict(waarden)

    def get(self, entity_id):
        waarde = self.waarden.get(entity_id)
        return None if waarde is None else Staat(waarde)

    def zet(self, entity_id, waarde):
        self.waarden[entity_id] = waarde


class Diensten:
    def __init__(self):
        self.verstuurd = []

    async def async_call(self, domein, dienst, data, blocking=False):
        self.verstuurd.append((domein, dienst, dict(data)))


class Bus:
    def __init__(self):
        self.gebeurtenissen = []

    def async_fire(self, soort, data):
        self.gebeurtenissen.append((soort, data))


class NepHass:
    def __init__(self, waarden):
        self.states = Staten(waarden)
        self.services = Diensten()
        self.bus = Bus()
        self.data = {}
        self.taken = []

    def async_create_task(self, coro):
        """Zoals HA het doet: erbij zetten en doorgaan.

        In Home Assistant draait er altijd een lus; hier soms niet, want ik roep
        een knop ook wel eens buiten een ronde aan. Dan wordt het werk bewaard
        en bij de volgende ronde alsnog gedaan.
        """
        try:
            taak = asyncio.ensure_future(coro)
        except RuntimeError:
            self.taken.append(coro)
            return None
        self.taken.append(taak)
        return taak

    async def afmaken(self):
        """Het uitgestelde werk alsnog doen."""
        wachtend, self.taken = self.taken, []
        for werk in wachtend:
            await werk


class NepStore:
    """De instellingen, zoals storage.py ze zou bewaren."""

    def __init__(self, instellingen):
        self.instellingen = instellingen

    async def async_load(self):
        return self.instellingen

    async def async_save(self, changes):
        self.instellingen.update(changes)
        return self.instellingen


LAADPAAL = {
    "id": "dev-laadpaal",
    "type": "laadpaal",
    "name": "Laadpaal",
    "brand": "easee",
    "controllable": True,
    "device_id": "abc",
    "entity": "sensor.laadpaal_vermogen",
    "entities": {
        "status": "sensor.laadpaal_status",
        "current": "sensor.laadpaal_stroom",
        "max_limit": "sensor.laadpaal_max",
        "dynamic_limit": "sensor.laadpaal_dyn",
        "lifetime_energy": "sensor.laadpaal_teller",
    },
    "cars": [
        {
            "id": "car-1",
            "name": "Ford",
            "capacity_kwh": 19.7,
            "phases": "one",
            "max_amps": 0,
            "soc_entity": "",
        }
    ],
}


def instellingen(**extra):
    basis = {
        "devices": [LAADPAAL],
        "installation": {"phases": 3, "fuse_amps": 25, "load_balancer": True},
        "sources": {
            "grid_mode": "split",
            "grid_import": "sensor.afname",
            "grid_export": "sensor.teruglevering",
            "phases_enabled": True,
            "phases": {
                "l1": {"current": "sensor.l1"},
                "l2": {"current": "sensor.l2"},
                "l3": {"current": "sensor.l3"},
            },
            "solar_forecast": {"remaining_today": "sensor.zon_rest"},
        },
        "contract": {
            "type": "fixed",
            "netting": False,
            "fixed": {
                "all_in_price": 0.24171,
                "feed_in_tariff": 0.0721,
                "feed_in_costs": 0.052756,
            },
        },
        "strategy": {
            "level": "steer",
            "goal": "cost",
            "load_alert": {"targets": ["mobile_app_iphone"]},
            "schedules": [
                {
                    "device": "dev-laadpaal",
                    "enabled": True,
                    "priority": "high",
                    "window": {"not_before": "", "start_by": "", "done_by": "06:00"},
                    "days": [],
                }
            ],
        },
        "active_cars": [{"device": "dev-laadpaal", "car": "car-1"}],
        "car_soc": [],
        "ready_devices": [],
    }
    basis.update(extra)
    return basis


def huis(status="awaiting_start", stroom=0.05, vermogen=0.0, teller=100.0,
         afname=0.0, teruglevering=1500.0, zon_rest=20.0):
    return {
        "sensor.laadpaal_status": status,
        "sensor.laadpaal_stroom": str(stroom),
        "sensor.laadpaal_vermogen": str(vermogen),
        "sensor.laadpaal_max": "14",
        "sensor.laadpaal_dyn": "6",
        "sensor.laadpaal_teller": str(teller),
        "sensor.afname": str(afname),
        "sensor.teruglevering": str(teruglevering),
        "sensor.l1": "3", "sensor.l2": "2", "sensor.l3": "2",
        "sensor.zon_rest": str(zon_rest),
    }


def bouw(waarden, inst):
    hass = NepHass(waarden)
    store = NepStore(inst)
    hass.data["domotiapp_coach"] = {"store": store}
    coach = coachmod.ChargerCoach(hass)
    return hass, store, coach


async def ronde(coach, inst, nu=None, paal=None):
    hass = coach.hass
    # Per ronde schoon beginnen, anders lees ik de opdrachten van vorige ronden
    # terug en denk ik dat er iets tweemaal verstuurd is.
    hass.services.verstuurd.clear()
    await hass.afmaken()
    await coach._one(nu or dt.datetime(2026, 8, 18, 14, 37), inst, paal or LAADPAAL,
                     "steer")
    # De echte Easee meldt binnen een seconde terug welke limiet erop staat, en
    # de coach leest die terug om te zien of hij zelf de rem is. Zonder deze
    # spiegel staat er in de proef eeuwig 6 en klopt die som niet.
    for _, dienst, gegevens in hass.services.verstuurd:
        if dienst == "set_charger_dynamic_limit":
            hass.states.zet("sensor.laadpaal_dyn", str(gegevens.get("current")))
    return coach.state["dev-laadpaal"], hass.services.verstuurd


print("=== 1. kabel erin, auto doet niets: eerst wekken ===")
inst = instellingen()
hass, store, coach = bouw(huis(), inst)
besluit, verstuurd = asyncio.run(ronde(coach, inst))
print(f"  {besluit['rule']}: {besluit['amps']} A -> {verstuurd}")
controle("wekstroom van 10 A", besluit["amps"] == 10 and besluit["rule"].endswith("+wake"),
         f"kreeg {besluit['rule']} met {besluit['amps']} A")
controle("gaat ook echt naar de paal",
         any(d[1] == "set_charger_dynamic_limit" and d[2].get("current") == 10 for d in verstuurd),
         f"verstuurd: {verstuurd}")

print("=== 2. een ronde drie seconden later: nog geen paniek op de kaart ===")
besluit, verstuurd = asyncio.run(ronde(coach, inst, dt.datetime(2026, 8, 18, 14, 37, 3)))
print(f"  {besluit['rule']}: {besluit['amps']} A")
controle("wekstroom blijft staan binnen de minuut", besluit["amps"] == 10,
         f"{besluit['rule']} met {besluit['amps']} A")
controle("nog niet klagen over de auto", "+waiting-for-car" not in besluit["rule"],
         besluit["rule"])

print("=== 2b. een minuut later: geen tweede wekpoging, wel de waarheid ===")
besluit, verstuurd = asyncio.run(ronde(coach, inst, dt.datetime(2026, 8, 18, 14, 38)))
print(f"  {besluit['rule']}: {besluit['amps']} A")
controle("geen tweede wekpoging", "+wake" not in besluit["rule"], besluit["rule"])
controle("zegt dat de auto niets doet", besluit["rule"].endswith("+waiting-for-car"),
         besluit["rule"])

print("=== 3. de auto begint te laden: terug naar het zuinige tempo ===")
hass.states.zet("sensor.laadpaal_status", "charging")
hass.states.zet("sensor.laadpaal_stroom", "5.7")
hass.states.zet("sensor.laadpaal_vermogen", "1290")
besluit, verstuurd = asyncio.run(ronde(coach, inst, dt.datetime(2026, 8, 18, 14, 39)))
print(f"  {besluit['rule']}: {besluit['amps']} A")
controle("volgt de zon weer", besluit["rule"] == "surplus" and besluit["amps"] <= 8,
         f"kreeg {besluit['rule']} met {besluit['amps']} A")

print("=== 4. zonder accustand vraagt hij erom en laadt hij niet uit het net ===")
inst = instellingen()
hass, store, coach = bouw(huis(teruglevering=0.0, afname=1200.0), inst)
besluit, verstuurd = asyncio.run(ronde(coach, inst))
meldingen = [d for d in verstuurd if d[0] == "notify"]
print(f"  {besluit['rule']}: laden={besluit['charge']}  melding={bool(meldingen)}")
controle("wacht op de accustand", besluit["rule"] == "no-soc" and not besluit["charge"],
         besluit["rule"])
controle("stuurt één melding", len(meldingen) == 1, f"{meldingen}")

print("=== 5. en zeurt niet elke minuut ===")
besluit, verstuurd = asyncio.run(ronde(coach, inst, dt.datetime(2026, 8, 18, 14, 38)))
controle("geen tweede melding", not [d for d in verstuurd if d[0] == "notify"],
         f"{verstuurd}")

print("=== 6. accustand ingevuld: hij telt zelf verder ===")
inst = instellingen(car_soc=[{"device": "dev-laadpaal", "car": "car-1",
                             "percent": 50.0, "meter": 100.0}])
hass, store, coach = bouw(huis(teruglevering=0.0, afname=1200.0, teller=104.93), inst)
_, car, _, _ = coach._read(dt.datetime(2026, 8, 18, 14, 37), inst, LAADPAAL)
print(f"  opgegeven 50%, teller 4,93 kWh verder -> {car.soc_percent:.1f}%")
controle("telt de geladen kWh erbij", 71 < car.soc_percent < 74, f"{car.soc_percent}")

print("=== 7. kabel eruit: de opgave vervalt ===")
hass, store, coach = bouw(huis(status="disconnected"), inst)
besluit, verstuurd = asyncio.run(ronde(coach, inst))
print(f"  {besluit['rule']}, car_soc nu {store.instellingen['car_soc']}")
controle("geen kabel", besluit["rule"] == "disconnected")
controle("percentage vergeten", store.instellingen["car_soc"] == [])
controle("er gaat niets naar de paal", not verstuurd, f"{verstuurd}")

print("=== 8. een auto die zijn accustand zelf meldt, wordt niets gevraagd ===")
auto = dict(LAADPAAL["cars"][0], soc_entity="sensor.auto_soc")
paal = dict(LAADPAAL, cars=[auto])
inst = instellingen(devices=[paal])
waarden = huis(teruglevering=0.0, afname=1200.0)
waarden["sensor.auto_soc"] = "70"
hass, store, coach = bouw(waarden, inst)
await_besluit = coachmod.ChargerCoach._one
asyncio.run(coach._one(dt.datetime(2026, 8, 18, 14, 37), inst, paal, "steer"))
besluit = coach.state["dev-laadpaal"]
print(f"  {besluit['rule']}: needs_soc={besluit['needs_soc']}")
controle("niets te vragen", not besluit["needs_soc"], f"{besluit}")

print("=== 9. een herstart van HA verliest de knoppen niet ===")
inst = instellingen()
hass, store, coach = bouw(huis(status="charging", stroom=5.7, vermogen=1290.0), inst)


async def knop_en_ronde():
    coach.async_boost("dev-laadpaal", True)
    # De coach zet het wegschrijven als taak weg; die even laten landen.
    await hass.afmaken()
    return await ronde(coach, inst)


besluit, _ = asyncio.run(knop_en_ronde())
print(f"  {besluit['rule']} {besluit['amps']} A, opgeslagen: {store.instellingen['sessions']}")
controle("snelladen staat aan", besluit["rule"] == "boost")
controle("en is vastgelegd",
         store.instellingen["sessions"] == [dict(store.instellingen["sessions"][0])]
         and store.instellingen["sessions"][0]["boost"] is True,
         f"{store.instellingen['sessions']}")

# En nu de herstart: een verse coach op dezelfde installatie en dezelfde opslag.
hass2, store2, coach2 = bouw(huis(status="charging", stroom=5.7, vermogen=1290.0),
                             store.instellingen)


async def na_herstart():
    coach2._restore(store2.instellingen)
    return await ronde(coach2, store2.instellingen)


besluit2, _ = asyncio.run(na_herstart())
print(f"  na herstart: {besluit2['rule']} {besluit2['amps']} A")
controle("snelladen leeft de herstart door", besluit2["rule"] == "boost",
         f"kreeg {besluit2['rule']}")

print("=== 10. maar niet als de opdracht van gisteren is ===")
oud = dict(store.instellingen["sessions"][0])
oud["at"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=13)).isoformat()
inst3 = dict(store.instellingen, sessions=[oud])
hass3, store3, coach3 = bouw(huis(status="charging", stroom=5.7, vermogen=1290.0), inst3)
coach3._restore(inst3)
besluit3, _ = asyncio.run(ronde(coach3, inst3))
print(f"  {besluit3['rule']} {besluit3['amps']} A")
controle("verlopen opdracht telt niet meer", besluit3["rule"] != "boost",
         f"kreeg {besluit3['rule']}")

print("=== 11. kabel eruit wist de knoppen ook ===")
inst4 = dict(store.instellingen)
hass4, store4, coach4 = bouw(huis(status="disconnected"), inst4)
coach4._restore(inst4)
asyncio.run(ronde(coach4, inst4))
print(f"  sessions nu {store4.instellingen['sessions']}")
controle("niets meer bewaard", store4.instellingen["sessions"] == [],
         f"{store4.instellingen['sessions']}")

print("=== 12. twee laadpunten in één ronde delen de ruimte onder de zekering ===")
TWEEDE = dict(LAADPAAL, id="dev-tweede", name="Laadpaal 2")
inst5 = instellingen(devices=[LAADPAAL, TWEEDE])
inst5["strategy"]["schedules"].append(dict(inst5["strategy"]["schedules"][0], device="dev-tweede"))
inst5["active_cars"].append({"device": "dev-tweede", "car": "car-1"})
inst5["car_soc"] = [
    {"device": "dev-laadpaal", "car": "car-1", "percent": 50.0, "meter": 100.0},
    {"device": "dev-tweede", "car": "car-1", "percent": 50.0, "meter": 100.0},
]
# Veel zon en een rustig huis: allebei zouden ze het volle plafond willen.
waarden = huis(teruglevering=8000.0)
hass5, store5, coach5 = bouw(waarden, inst5)
asyncio.run(coach5._round(dt.datetime(2026, 8, 18, 14, 37)))
een = coach5.state["dev-laadpaal"]
twee = coach5.state["dev-tweede"]
huisstroom = 3  # de zwaarste fase in `huis()`
print(f"  paal 1: {een['amps']} A, paal 2: {twee['amps']} A, huis {huisstroom} A, zekering 25 A")
controle("samen onder de zekering",
         een["amps"] + twee["amps"] + huisstroom <= 25 - 3,
         f"{een['amps']} + {twee['amps']} + {huisstroom} A")
# Er is geen ruimte voor twee keer 14 A onder een zekering van 25 A, dus de
# tweede hoort niets te krijgen en dat ook te zeggen.
controle("de tweede weet waarom hij niets krijgt", twee["rule"] == "no-room",
         f"{twee['rule']} met {twee['amps']} A")

# En de voorrang bepaalt wie de ruimte krijgt, niet de volgorde van toevoegen.
inst6 = instellingen(devices=[LAADPAAL, TWEEDE])
inst6["strategy"]["schedules"] = [
    dict(inst6["strategy"]["schedules"][0], device="dev-laadpaal", priority="low"),
    dict(inst6["strategy"]["schedules"][0], device="dev-tweede", priority="high"),
]
inst6["active_cars"].append({"device": "dev-tweede", "car": "car-1"})
inst6["car_soc"] = list(inst5["car_soc"])
hass7, store7, coach7 = bouw(huis(teruglevering=8000.0), inst6)
asyncio.run(coach7._round(dt.datetime(2026, 8, 18, 14, 37)))
print(f"  met voorrang op paal 2: paal 1 {coach7.state['dev-laadpaal']['amps']} A, "
      f"paal 2 {coach7.state['dev-tweede']['amps']} A")
controle("de belangrijkste gaat voor", coach7.state["dev-tweede"]["amps"] > 0,
         f"{coach7.state['dev-tweede']}")

print("=== 13. een ronde die zijn instellingen niet kan lezen telt niet als leven ===")


class StukkeStore:
    async def async_load(self):
        raise RuntimeError("opslag stuk")

    async def async_save(self, changes):
        raise RuntimeError("opslag stuk")


hass6 = NepHass(huis())
hass6.data["domotiapp_coach"] = {"store": StukkeStore()}
coach6 = coachmod.ChargerCoach(hass6)
asyncio.run(coach6._tick(dt.datetime(2026, 8, 18, 14, 37)))
print(f"  laatste ronde: {coach6._last_round}")
controle("de wachthond blijft dus wakker", coach6._last_round is None,
         f"{coach6._last_round}")

print("=== 14. de klaar-tijd grijpt pas op het laatste moment in ===")
# Wat er op 20-08-2026 om 15:48 bij Sven misging. Hij laadde zonvolgend op 6 A,
# de klaar-tijdsom rekende met die gemeten 6 A in plaats van met wat de paal kan,
# en zette hem acht uur te vroeg op vol vermogen. Op 14 A had hij pas veel later
# hoeven beginnen.
laat = instellingen()
laat["strategy"]["schedules"][0]["window"]["done_by"] = "19:00"
laat["car_soc"] = [{"device": "dev-laadpaal", "car": "car-1", "percent": 80.0,
                    "meter": 100.0}]
# Weinig zon: het overschot is net genoeg voor zes ampère, dus de zonregel wil
# zuinig laden. Op zes ampère haalt hij 19:00 niet, op veertien ruimschoots.
BEGINSTAND = dict(status="charging", stroom=13.5, vermogen=3070.0,
                  teruglevering=0.0, afname=1800.0)


def volgt(hass, besluit):
    """De paal doet wat er gevraagd is: op 14 A meet hij 13,5 A, op 6 A 5,6 A."""
    vol = besluit["amps"] > 8
    hass.states.zet("sensor.laadpaal_stroom", "13.5" if vol else "5.6")
    hass.states.zet("sensor.laadpaal_vermogen", "3070" if vol else "1290")
    hass.states.zet("sensor.afname", "1800" if vol else "20")


def zes_rondes(vanaf_uur, vanaf_minuut):
    hass, _, coach = bouw(huis(**BEGINSTAND), laat)
    regels = []
    for stap in range(6):
        moment = dt.datetime(2026, 8, 18, vanaf_uur, vanaf_minuut + stap)
        asyncio.run(ronde(coach, laat, moment))
        besluit = coach.state["dev-laadpaal"]
        regels.append((besluit["rule"], besluit["amps"]))
        volgt(hass, besluit)
    return regels


# Klaar om 19:00 is een klaar-tijd overdag, en die krijgt sinds 27-08-2026 een
# uur speling in plaats van een kwartier (proef 32 in test_planner.py). De
# tijden hieronder zijn daarop gezet: er moet 4,4 kWh in, op 14 A eenfasig duurt
# dat 1,36 uur, dus met het uur erbij is 16:38 het laatste moment dat nog past.
vroeg = zes_rondes(15, 30)
print("  15:30  " + "  ".join(f"{r}:{a}A" for r, a in vroeg))
controle("ruim op tijd blijft hij op de zon",
         all(naam == "surplus" for naam, _ in vroeg), f"{vroeg}")

# En op het laatste moment dat nog past grijpt hij wél in.
laatst = zes_rondes(16, 45)
print("  16:45  " + "  ".join(f"{r}:{a}A" for r, a in laatst))
namen = [r for r, _ in laatst]
controle("op het laatste moment gaat hij vol", "deadline" in namen, f"{laatst}")
vanaf = namen.index("deadline")
controle("en valt daarna niet meer terug",
         all(naam == "deadline" for naam in namen[vanaf:]), f"{laatst}")

# Het bewijs dat deze proef de fout ook echt vangt: met de rekenwijze van vóór
# de reparatie, die de eigen rem van de coach aanziet voor het maximum van de
# paal, slaat hij om kwart voor vijf wel om.
echte = planner.throttled_by_coach
planner.throttled_by_coach = lambda charger: False
try:
    oud = zes_rondes(15, 30)
finally:
    planner.throttled_by_coach = echte
print("  zoals het was: " + "  ".join(f"{r}:{a}A" for r, a in oud))
controle("de proef vangt de fout ook echt",
         any(naam == "deadline" for naam, _ in oud), f"{oud}")

print("=== 15. hij vertelt hoe het afliep als de auto vol is ===")
klaar = instellingen()
# Klaar om elf uur 's avonds en niet om zeven uur: het gaat hier om de zin die
# vertelt waar de tijd bleef, en dan moet hij om vijf uur ook werkelijk staan te
# wachten op de zon. Bij een klaar-tijd overdag valt vijf uur binnen het uur
# speling en gaat hij vol vermogen, en dan is er geen wachttijd te melden.
klaar["strategy"]["schedules"][0]["window"]["done_by"] = "23:00"
klaar["car_soc"] = [{"device": "dev-laadpaal", "car": "car-1", "percent": 80.0,
                     "meter": 100.0}]
waarden = huis(status="charging", stroom=13.5, vermogen=3070.0, teruglevering=0.0,
               afname=1800.0)
hassA, storeA, coachA = bouw(huis(status="ready_to_charge", teruglevering=0.0,
                                  afname=1800.0), klaar)
# Eerst een ronde met de kabel erin en nog geen stroom, zoals het in het echt
# gaat. Ziet de coach bij zijn allereerste ronde al stroom lopen, dan is hij
# midden in een laadbeurt ingestapt en zegt hij dat ook; dat staat in proef 15b.
asyncio.run(ronde(coachA, klaar, dt.datetime(2026, 8, 18, 16, 59)))
for entiteit, waarde in waarden.items():
    hassA.states.zet(entiteit, waarde)
asyncio.run(ronde(coachA, klaar, dt.datetime(2026, 8, 18, 17, 0)))
# Even een ronde waarin de auto niets afneemt, dat moet in het verslag terugkomen.
hassA.states.zet("sensor.laadpaal_status", "awaiting_start")
hassA.states.zet("sensor.laadpaal_stroom", "0.05")
hassA.states.zet("sensor.laadpaal_vermogen", "0")
for minuut in range(1, 16):
    asyncio.run(ronde(coachA, klaar, dt.datetime(2026, 8, 18, 17, minuut)))
# En dan meldt de paal dat de auto vol is.
hassA.states.zet("sensor.laadpaal_status", "completed")
hassA.states.zet("sensor.laadpaal_teller", "106.5")
_, verstuurd = asyncio.run(ronde(coachA, klaar, dt.datetime(2026, 8, 18, 17, 20)))
meldingen = [d[2]["message"] for d in verstuurd if d[0] == "notify"]
print(f"  {meldingen}")
controle("meldt dat de auto vol is", any("is vol" in m for m in meldingen), f"{meldingen}")
controle("met begintijd en eindtijd", any("17:00 tot 17:20" in m for m in meldingen),
         f"{meldingen}")
controle("en met de geladen kWh", any("6,5 kWh" in m for m in meldingen), f"{meldingen}")
# Er lag geen zon en er was geen krappe klaar-tijd meer, dus hij stond te wachten
# op de zon. Dat hoort er dan ook zo in te staan.
controle("en vertelt waar de tijd bleef",
         any("minuten naar wachten op je eigen zon" in m for m in meldingen), f"{meldingen}")

print("=== 15b. herstart midden in de laadbeurt: geen verzonnen begintijd ===")
# Sven op 20-08-2026. Home Assistant herstartte om 20:57 terwijl de auto vanaf
# 19:18 laadde, en het verslag meldde daarna "Geladen van 20:58 tot 21:32,
# 3,1 kWh" terwijl er 5,2 kWh in was gegaan. De coach kán die begintijd niet
# weten, dus hoort hij hem ook niet te noemen.
herstart = instellingen()
herstart["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
herstart["car_soc"] = [{"device": "dev-laadpaal", "car": "car-1", "percent": 60.0,
                        "meter": 100.0}]
hassB, storeB, coachB = bouw(huis(status="charging", stroom=13.5, vermogen=3070.0,
                                  teruglevering=0.0, afname=1800.0), herstart)
asyncio.run(ronde(coachB, herstart, dt.datetime(2026, 8, 20, 20, 58)))
hassB.states.zet("sensor.laadpaal_status", "completed")
hassB.states.zet("sensor.laadpaal_teller", "103.1")
_, verstuurd = asyncio.run(ronde(coachB, herstart, dt.datetime(2026, 8, 20, 21, 32)))
meldingen = [d[2]["message"] for d in verstuurd if d[0] == "notify"]
print(f"  {meldingen}")
controle("hij meldt het nog steeds", meldingen, f"{meldingen}")
controle("maar doet niet alsof hij het begin zag",
         all("van 20:58 tot" not in m for m in meldingen), f"{meldingen}")
controle("en zegt dat hij al liep",
         any("toen liep hij al" in m for m in meldingen), f"{meldingen}")

print("=== 15c. een auto die op 80% stopt is niet vol ===")
# Zijn Ford stopte op 80%, de Easee meldde `completed` en de coach zei "de auto
# is vol". Dat is onwaar en het leest als een coach die niet weet wat hij doet.
# Met een auto die zijn accustand zelf meldt, zoals Svens Ford, want juist daar
# loopt het percentage achter op wat de paal doet.
ford = dict(LAADPAAL["cars"][0], soc_entity="sensor.auto_soc")
PAAL_FORD = dict(LAADPAAL, cars=[ford])
tachtig = instellingen(devices=[PAAL_FORD])
tachtig["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
huisC = huis(status="ready_to_charge", teruglevering=0.0, afname=1800.0)
huisC["sensor.auto_soc"] = "70"
hassC, storeC, coachC = bouw(huisC, tachtig)
asyncio.run(ronde(coachC, tachtig, paal=PAAL_FORD, nu=dt.datetime(2026, 8, 20, 20, 57)))
hassC.states.zet("sensor.laadpaal_status", "charging")
hassC.states.zet("sensor.laadpaal_stroom", "13.5")
hassC.states.zet("sensor.laadpaal_vermogen", "3070")
asyncio.run(ronde(coachC, tachtig, paal=PAAL_FORD, nu=dt.datetime(2026, 8, 20, 20, 58)))
hassC.states.zet("sensor.laadpaal_status", "completed")
# De auto stopt, maar zijn app hangt nog op het percentage van daarvoor. Zo ging
# het op 25-08-2026 bij Sven: de melding vertrok met 70% terwijl de kaart een
# minuut later 80% zei. Het verslag hoort dus even te wachten.
_, verstuurd = asyncio.run(ronde(coachC, tachtig, paal=PAAL_FORD, nu=dt.datetime(2026, 8, 20, 21, 32)))
meldingen = [d[2]["message"] for d in verstuurd if d[0] == "notify"]
print(f"  meteen bij het stoppen: {meldingen}")
controle("hij wacht op een accustand die bij deze beurt hoort", not meldingen,
         f"{meldingen}")

# De auto meldt zich, en dan pas gaat het bericht de deur uit.
hassC.states.zet("sensor.auto_soc", "80")
_, verstuurd = asyncio.run(ronde(coachC, tachtig, paal=PAAL_FORD, nu=dt.datetime(2026, 8, 20, 21, 33)))
meldingen = [d[2]["message"] for d in verstuurd if d[0] == "notify"]
besluit = coachC.state["dev-laadpaal"]
print(f"  melding: {meldingen}")
print(f"  kaart  : {besluit['reason']}")
controle("hij noemt het geen vol", all("is vol" not in m for m in meldingen),
         f"{meldingen}")
controle("maar noemt de accustand", any("80%" in m for m in meldingen), f"{meldingen}")

# En blijft de auto stil, dan komt het bericht alsnog: te laat melden is erger
# dan een getal dat een ronde oud is.
huisD = huis(status="ready_to_charge", teruglevering=0.0, afname=1800.0)
huisD["sensor.auto_soc"] = "70"
hassD, _, coachD = bouw(huisD, tachtig)
asyncio.run(ronde(coachD, tachtig, paal=PAAL_FORD, nu=dt.datetime(2026, 8, 20, 20, 57)))
hassD.states.zet("sensor.laadpaal_status", "charging")
hassD.states.zet("sensor.laadpaal_stroom", "13.5")
hassD.states.zet("sensor.laadpaal_vermogen", "3070")
asyncio.run(ronde(coachD, tachtig, paal=PAAL_FORD, nu=dt.datetime(2026, 8, 20, 20, 58)))
hassD.states.zet("sensor.laadpaal_status", "completed")
asyncio.run(ronde(coachD, tachtig, paal=PAAL_FORD, nu=dt.datetime(2026, 8, 20, 21, 32)))
_, verstuurd = asyncio.run(ronde(coachD, tachtig, paal=PAAL_FORD, nu=dt.datetime(2026, 8, 20, 21, 36)))
meldingen = [d[2]["message"] for d in verstuurd if d[0] == "notify"]
print(f"  auto blijft stil, vier minuten later: {meldingen}")
controle("een auto die zwijgt houdt het bericht niet tegen", meldingen,
         f"{meldingen}")
controle("en op de kaart net zo", "80%" in besluit["reason"], besluit["reason"])
controle("met een reden die klopt", "laadgrens" in besluit["reason"], besluit["reason"])

print("=== 16. en waarom hij de klaar-tijd niet gehaald heeft ===")
laat2 = instellingen()
laat2["strategy"]["schedules"][0]["window"]["done_by"] = "19:00"
laat2["car_soc"] = [{"device": "dev-laadpaal", "car": "car-1", "percent": 90.0,
                     "meter": 100.0}]
hassB, storeB, coachB = bouw(huis(status="charging", stroom=13.5, vermogen=3070.0,
                                  teruglevering=0.0, afname=1800.0), laat2)
# Een paar ronden waarin de bewoner zelf gepauzeerd had.
coachB.async_pause("dev-laadpaal", True)
for minuut in range(30, 51):
    asyncio.run(ronde(coachB, laat2, dt.datetime(2026, 8, 18, 18, minuut)))
coachB.async_pause("dev-laadpaal", False)
# En dan is het negen over zeven: de klaar-tijd van vandaag is voorbij.
_, verstuurd = asyncio.run(ronde(coachB, laat2, dt.datetime(2026, 8, 18, 19, 9)))
meldingen = [d[2]["message"] for d in verstuurd if d[0] == "notify"]
print(f"  {meldingen}")
controle("meldt dat 19:00 niet gehaald is",
         any("19:00 nog niet vol" in m for m in meldingen), f"{meldingen}")
controle("noemt de accustand", any("90%" in m for m in meldingen), f"{meldingen}")
controle("en noemt de pauze als reden",
         any("naar de pauze die je zelf aanzette" in m for m in meldingen), f"{meldingen}")
controle("en dat hij doorlaadt tot de auto vol is",
         any("laadt door tot hij vol is" in m for m in meldingen), f"{meldingen}")

print("=== 17. de klaar-tijd voorbij en niet vol: doorladen tot hij vol is ===")
door = instellingen()
door["strategy"]["schedules"][0]["window"]["done_by"] = "19:00"
door["car_soc"] = [{"device": "dev-laadpaal", "car": "car-1", "percent": 90.0,
                    "meter": 100.0}]
# Geen zon meer en een rustig huis: de zonregel zou hem stilzetten.
hassC, storeC, coachC = bouw(huis(status="charging", stroom=13.5, vermogen=3070.0,
                                  teruglevering=0.0, afname=1800.0), door)
asyncio.run(ronde(coachC, door, dt.datetime(2026, 8, 18, 18, 55)))
voor = coachC.state["dev-laadpaal"]
na = []
for minuut in (1, 2, 3):
    besluit, verstuurd = asyncio.run(ronde(coachC, door, dt.datetime(2026, 8, 18, 19, minuut)))
    na.append((besluit["rule"], besluit["amps"]))
print(f"  voor 19:00: {voor['rule']} {voor['amps']} A   daarna: " +
      "  ".join(f"{r}:{a}A" for r, a in na))
controle("hij stopt niet om 19:00", all(a > 0 for _, a in na), f"{na}")
controle("en zegt waarom hij doorlaadt", all(r == "overdue" for r, _ in na), f"{na}")

print("=== 18. en hij houdt op zodra de auto vol is ===")
hassC.states.zet("sensor.laadpaal_status", "completed")
besluit, verstuurd = asyncio.run(ronde(coachC, door, dt.datetime(2026, 8, 18, 19, 5)))
print(f"  {besluit['rule']}: laden={besluit['charge']}")
controle("stopt bij een volle auto", not besluit["charge"] and besluit["rule"] == "complete",
         f"{besluit['rule']}")
naar_de_paal = [d for d in verstuurd if d[0] != "notify"]
controle("en er gaat niets meer naar de paal", not naar_de_paal, f"{naar_de_paal}")
controle("het doorladen is vergeten", "dev-laadpaal" not in coachC._te_laat)

print("=== 19. een accustand die wegvalt is geen onbekende accustand ===")
# Op 25-08-2026 om 15:45 was Svens Ford-integratie een minuut `unavailable` en
# zei de kaart "De auto is vol" terwijl de bus op 80% stond. Diezelfde avond om
# 20:04 vroeg de coach op zijn telefoon om een accustand die hij eerder die
# avond gewoon gezien had. De auto hangt dan nog aan dezelfde kabel, dus er is
# niets onbekends aan.
ford19 = dict(LAADPAAL["cars"][0], soc_entity="sensor.auto_soc", phases="three")
PAAL19 = dict(LAADPAAL, cars=[ford19])
inst19 = instellingen(devices=[PAAL19])
huis19 = huis(status="ready_to_charge", teruglevering=0.0, afname=1800.0)
huis19["sensor.auto_soc"] = "62"
hass19, _, coach19 = bouw(huis19, inst19)
zag, _ = asyncio.run(ronde(coach19, inst19, paal=PAAL19, nu=dt.datetime(2026, 8, 25, 20, 3)))
hass19.states.zet("sensor.auto_soc", "unavailable")
kwijt, verstuurd19 = asyncio.run(ronde(coach19, inst19, paal=PAAL19, nu=dt.datetime(2026, 8, 25, 20, 4)))

# Een tweeling die precies dezelfde ronden draait, maar waar de auto zich niet
# wegdraait. De ladder hangt van meer af dan de accustand alleen (een wekpoging
# is na een ronde op), dus zonder deze tweeling zou ik gedrag vergelijken dat
# niet te vergelijken is.
huis19b = huis(status="ready_to_charge", teruglevering=0.0, afname=1800.0)
huis19b["sensor.auto_soc"] = "62"
hass19b, _, coach19b = bouw(huis19b, inst19)
asyncio.run(ronde(coach19b, inst19, paal=PAAL19, nu=dt.datetime(2026, 8, 25, 20, 3)))
zelfde, _ = asyncio.run(ronde(coach19b, inst19, paal=PAAL19, nu=dt.datetime(2026, 8, 25, 20, 4)))

print(f"  eerste ronde met accustand: {zag['rule']} {zag['amps']} A")
print(f"  auto valt weg             : {kwijt['rule']} {kwijt['amps']} A  needs_soc={kwijt['needs_soc']}")
print(f"  auto blijft melden        : {zelfde['rule']} {zelfde['amps']} A  needs_soc={zelfde['needs_soc']}")
controle("hij vraagt niet om wat hij al gezien heeft", not kwijt["needs_soc"], f"{kwijt}")
controle(
    "en neemt hetzelfde besluit als toen de auto zich nog meldde",
    kwijt["rule"] == zelfde["rule"] and kwijt["amps"] == zelfde["amps"],
    f"{zelfde['rule']}/{zelfde['amps']} tegen {kwijt['rule']}/{kwijt['amps']}",
)
vraag19 = [d[2]["message"] for d in verstuurd19 if d[0] == "notify"]
controle("en er gaat niets de deur uit om een accustand", not vraag19, f"{vraag19}")

# De kabel eruit wist het wel, want morgen hangt er misschien een andere auto.
hass19.states.zet("sensor.laadpaal_status", "disconnected")
asyncio.run(ronde(coach19, inst19, paal=PAAL19, nu=dt.datetime(2026, 8, 25, 20, 5)))
hass19.states.zet("sensor.laadpaal_status", "ready_to_charge")
opnieuw, _ = asyncio.run(ronde(coach19, inst19, paal=PAAL19, nu=dt.datetime(2026, 8, 25, 20, 6)))
print(f"  na de kabel eruit: {opnieuw['rule']}  needs_soc={opnieuw['needs_soc']}")
controle("maar na de kabel eruit weet hij het niet meer", opnieuw["needs_soc"], f"{opnieuw}")

print("=== 20. het verslag telt mee wat de teller nog niet verwerkt heeft ===")
# Svens Easee-levensduurteller werkte op 25-08-2026 maar eens per uur bij en
# sprong toen met 3,5 kWh ineens. Het verslag miste daardoor het laatste half
# uur: het meldde 5,8 kWh waar de som op de vermogens op ruim 6 uitkwam. Hier
# staat de teller de hele beurt stil, dus alles moet uit de eigen meting komen.
inst20 = instellingen()
huis20 = huis(status="ready_to_charge", teruglevering=0.0, afname=1800.0)
hass20, _, coach20 = bouw(huis20, inst20)
asyncio.run(ronde(coach20, inst20, nu=dt.datetime(2026, 8, 25, 20, 57)))
hass20.states.zet("sensor.laadpaal_status", "charging")
hass20.states.zet("sensor.laadpaal_stroom", "13.5")
hass20.states.zet("sensor.laadpaal_vermogen", "6000")
for minuut in range(58, 60):
    asyncio.run(ronde(coach20, inst20, nu=dt.datetime(2026, 8, 25, 20, minuut)))
for minuut in range(0, 8):
    asyncio.run(ronde(coach20, inst20, nu=dt.datetime(2026, 8, 25, 21, minuut)))
hass20.states.zet("sensor.laadpaal_status", "completed")
hass20.states.zet("sensor.laadpaal_vermogen", "0")
_, verstuurd20 = asyncio.run(ronde(coach20, inst20, nu=dt.datetime(2026, 8, 25, 21, 8)))
melding20 = [d[2]["message"] for d in verstuurd20 if d[0] == "notify"]
print(f"  {melding20}")
# Tien minuten laden op 6 kW is 1,0 kWh, terwijl de teller op 100,0 blijft staan.
controle(
    "de stilstaande teller houdt het verslag niet leeg",
    any("kWh" in m for m in melding20),
    f"{melding20}",
)
controle(
    "en het getal is wat er gemeten is",
    any("1,0 kWh" in m for m in melding20),
    f"{melding20}",
)

# Springt de teller alsnog, dan is dat deel van hem en telt het niet dubbel.
huis20b = huis(status="ready_to_charge", teruglevering=0.0, afname=1800.0)
hass20b, _, coach20b = bouw(huis20b, inst20)
asyncio.run(ronde(coach20b, inst20, nu=dt.datetime(2026, 8, 25, 20, 57)))
hass20b.states.zet("sensor.laadpaal_status", "charging")
hass20b.states.zet("sensor.laadpaal_stroom", "13.5")
hass20b.states.zet("sensor.laadpaal_vermogen", "6000")
for minuut in range(58, 60):
    asyncio.run(ronde(coach20b, inst20, nu=dt.datetime(2026, 8, 25, 20, minuut)))
for minuut in range(0, 5):
    asyncio.run(ronde(coach20b, inst20, nu=dt.datetime(2026, 8, 25, 21, minuut)))
# De teller doet na zes minuten laden zijn sprong: 0,6 kWh ineens.
hass20b.states.zet("sensor.laadpaal_teller", "100.6")
for minuut in range(5, 8):
    asyncio.run(ronde(coach20b, inst20, nu=dt.datetime(2026, 8, 25, 21, minuut)))
hass20b.states.zet("sensor.laadpaal_status", "completed")
hass20b.states.zet("sensor.laadpaal_vermogen", "0")
_, verstuurd20b = asyncio.run(ronde(coach20b, inst20, nu=dt.datetime(2026, 8, 25, 21, 8)))
melding20b = [d[2]["message"] for d in verstuurd20b if d[0] == "notify"]
print(f"  met een teller die springt: {melding20b}")
# De teller zelf loopt achter op het moment dat hij springt: om 21:05 was er
# zeven minuten geladen (0,7 kWh) en zei hij 0,6. Dat verschil blijft staan,
# want de geijkte teller is de maat voor het stuk dat hij dekt. Wat telt is dat
# de staart erbij komt en niets dubbel geteld wordt: 0,6 van de teller plus de
# 0,3 die erna gemeten is.
controle(
    "de sprong van de teller telt niet dubbel",
    any("0,9 kWh" in m for m in melding20b),
    f"{melding20b}",
)

print("=== 21. een laderlimiet die elke beurt op een fase zet, wordt gezegd ===")
# Svens laderlimiet stond een week op 14 A. Daarmee koos de Easee bij elke start
# een enkele fase: 3.125 W waar op 16 A 10.855 W ging. Het paneel zei er niets
# over, en de coach kan het met sturen niet oplossen.
ford21 = dict(LAADPAAL["cars"][0], phases="three")
PAAL21 = dict(LAADPAAL, cars=[ford21])
inst21 = instellingen(devices=[PAAL21])
# Eerst een ronde met de kabel erin en nog geen stroom, zoals het in het echt
# gaat: een opstelling die meteen laadt speelt een herstart midden in een
# laadbeurt na en gedraagt zich sinds v0.32.2 bewust anders.
huis21 = huis(status="ready_to_charge", teruglevering=0.0, afname=1800.0)
hass21, _, coach21 = bouw(huis21, inst21)
asyncio.run(ronde(coach21, inst21, paal=PAAL21, nu=dt.datetime(2026, 8, 25, 12, 50)))
hass21.states.zet("sensor.laadpaal_status", "charging")
hass21.states.zet("sensor.laadpaal_stroom", "13.5")
hass21.states.zet("sensor.laadpaal_vermogen", "3070")
besluit21, verstuurd21 = asyncio.run(
    ronde(coach21, inst21, paal=PAAL21, nu=dt.datetime(2026, 8, 25, 12, 51))
)
tips21 = [d[2]["message"] for d in verstuurd21 if d[0] == "notify"]
print(f"  kaart: {besluit21['tip']}")
controle(
    "hij zegt het op de kaart",
    "14 A" in besluit21["tip"] and "16 A" in besluit21["tip"],
    f"{besluit21['tip']}",
)
controle("en een keer op de telefoon", len(tips21) == 1 and "16 A" in tips21[0], f"{tips21}")
_, nogmaals21 = asyncio.run(
    ronde(coach21, inst21, paal=PAAL21, nu=dt.datetime(2026, 8, 25, 12, 52))
)
controle(
    "maar niet elke minuut opnieuw",
    not [d for d in nogmaals21 if d[0] == "notify"],
    f"{nogmaals21}",
)

# Op 16 A koos dezelfde paal drie fasen, en dan valt er niets te zeggen.
hass21.states.zet("sensor.laadpaal_max", "16")
hass21.states.zet("sensor.laadpaal_vermogen", "10855")
hass21.states.zet("sensor.laadpaal_stroom", "15.45")
driefasig, _ = asyncio.run(
    ronde(coach21, inst21, paal=PAAL21, nu=dt.datetime(2026, 8, 25, 12, 56))
)
print(f"  op 16 A driefasig: tip={driefasig['tip']!r}")
controle("driefasig zegt hij niets", not driefasig["tip"], f"{driefasig['tip']}")

# En een auto die zelf maar een fase kan, kan er niets aan doen.
inst21c = instellingen()
huis21c = huis(status="ready_to_charge", teruglevering=0.0, afname=1800.0)
hass21c, _, coach21c = bouw(huis21c, inst21c)
asyncio.run(ronde(coach21c, inst21c, nu=dt.datetime(2026, 8, 25, 12, 50)))
hass21c.states.zet("sensor.laadpaal_status", "charging")
hass21c.states.zet("sensor.laadpaal_stroom", "13.5")
hass21c.states.zet("sensor.laadpaal_vermogen", "3070")
eenfasig, _ = asyncio.run(ronde(coach21c, inst21c, nu=dt.datetime(2026, 8, 25, 12, 51)))
print(f"  eenfasige auto: tip={eenfasig['tip']!r}")
controle("een eenfasige auto krijgt geen verwijt", not eenfasig["tip"], f"{eenfasig['tip']}")

print()
print(f"{GOED} goed, {FOUT} fout")
sys.exit(1 if FOUT else 0)
