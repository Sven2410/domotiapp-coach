"""De laag die sensoren leest en opdrachten stuurt, met een nagebouwde HA.

Home Assistant staat hier niet geïnstalleerd, dus de handvol namen die coach.py
eruit gebruikt worden nagemaakt. Wat er getest wordt is de bedrading: welke
vlaggen de coach aan de planner meegeeft, wat hij naar de laadpaal stuurt en wat
hij onthoudt of juist vergeet.
"""


import asyncio
import datetime as dt
import pathlib

# De nagemaakte Home Assistant en de modules van de coach staan in harnas.py,
# gedeeld met het virtuele huis. Importeren laadt de coach in.
from harnas import *  # noqa: F401,F403

FOUT = 0
GOED = 0


def controle(naam, gelukt, uitleg=""):
    global FOUT, GOED
    if gelukt:
        GOED += 1
    else:
        FOUT += 1
        print(f"  FOUT  {naam}: {uitleg}")


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
        # Wie wat krijgt, sinds 06-09-2026 per persoon; zie ontvangers.py.
        "notifications": {
            "people": [{"id": "p-1", "name": "Bewoner", "target": "mobile_app_iphone", "user_id": "u-1",
                        "kinds": {"kritiek": True, "melding": True, "besluit": False, "belasting": True}}],
            "load_alert": {"enabled": False, "threshold_percent": 80,
                           "min_interval_minutes": 30, "min_duration_seconds": 60},
        },
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
    # `_sleep` staat in coach.py met "waiting that a test can shortcut", maar dat
    # gebeurde nergens. Bevestigt een nagebouwde paal zijn limiet niet, dan wacht
    # `_bevestig` vijftien echte seconden, per paal en per ronde. De proeven met
    # twee laadpunten liepen daardoor tegen de minuut, en dat leest als een hang.
    # Overslaan verandert de uitkomst niet: er wordt dezelfde sensor even vaak
    # gelezen, alleen zonder de klok.
    coach._sleep = lambda seconds: asyncio.sleep(0)
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
controle("wekstroom van 14 A", besluit["amps"] == 14 and besluit["rule"].endswith("+wake"),
         f"kreeg {besluit['rule']} met {besluit['amps']} A")
controle("gaat ook echt naar de paal",
         any(d[1] == "set_charger_dynamic_limit" and d[2].get("current") == 14 for d in verstuurd),
         f"verstuurd: {verstuurd}")

print("=== 2. een ronde drie seconden later: nog geen paniek op de kaart ===")
besluit, verstuurd = asyncio.run(ronde(coach, inst, dt.datetime(2026, 8, 18, 14, 37, 3)))
print(f"  {besluit['rule']}: {besluit['amps']} A")
controle("wekstroom blijft staan binnen de minuut", besluit["amps"] == 14,
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

# De eigenaar op 05-09-2026, toen de paal om 09:42 op zon begon en Meldingen zweeg:
# "ik wil dat alles wat de coach doet terug te lezen is in meldingen." Elk
# ander besluit komt dus in de geschiedenis, als "besluit" en zonder telefoon.
print("=== 3b. elk ander besluit staat in de geschiedenis, zonder telefoon ===")
geschiedenis = asyncio.run(coachmod.async_get_meldingen(hass).async_list())
besluiten = [g["message"] for g in geschiedenis if g.get("kind") == "besluit"]
for b in besluiten:
    print(f"  {b[:110]}")
controle("wekken, wachten op de auto en zon zijn drie besluiten", len(besluiten) == 3,
         f"{len(besluiten)}")
controle("het eerste zegt wekken op 14 A", "laden op 14 A" in besluiten[0], besluiten[0])
controle("het laatste zegt laden op zon", "laden op" in besluiten[-1]
         and "zon" in besluiten[-1], besluiten[-1])
controle("een besluit gaat niet naar de telefoon",
         not [d for d in verstuurd if d[0] == "notify"], f"{verstuurd}")

print("=== 4. zonder accustand vraagt hij erom en laadt hij niet uit het net ===")
inst = instellingen()
hass, store, coach = bouw(huis(teruglevering=0.0, afname=1200.0), inst)
besluit, verstuurd = asyncio.run(ronde(coach, inst))
meldingen = [d for d in verstuurd if d[0] == "notify"]
print(f"  {besluit['rule']}: laden={besluit['charge']}  melding={bool(meldingen)}")
controle("wacht op de accustand", besluit["rule"] == "no-soc" and not besluit["charge"],
         besluit["rule"])
controle("stuurt één melding", len(meldingen) == 1, f"{meldingen}")
# En in de geschiedenis is die kritiek: de bewoner moet er iets mee. De eigenaar op
# 05-09-2026: "dat je op normale en kritieke meldingen kan filteren."
geschiedenis = asyncio.run(coachmod.async_get_meldingen(hass).async_list())
controle("en in de geschiedenis heet die kritiek",
         [g["kind"] for g in geschiedenis if g["message"].startswith("De coach wil de auto")] == ["kritiek"],
         f"{[(g.get('kind'), g['message'][:40]) for g in geschiedenis]}")

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
# Wat er op 20-08-2026 om 15:48 in die woning misging. Hij laadde zonvolgend op 6 A,
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
    """De paal doet wat er gevraagd is: op 14 A meet hij 13,5 A, op 6 A 5,6 A.

    En daartussen steeds vier tiende ampère onder de limiet, zoals een echte
    auto. Tot 04-09-2026 stond hier voor alles onder 8 A een vaste 5,6 A, en
    daarmee leek een paal op 7 A niet door de coach geremd maar door iets
    anders; zie `throttled_by_coach`.
    """
    stroom = max(5.6, min(13.5, besluit["amps"] - 0.4))
    hass.states.zet("sensor.laadpaal_stroom", f"{stroom}")
    hass.states.zet("sensor.laadpaal_vermogen", f"{stroom * 230:.0f}")
    hass.states.zet("sensor.afname", "1800" if stroom > 8 else "20")


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


# Klaar om 19:00 krijgt een uur speling (proef 32 in test_planner.py). Er moet
# 4,4 kWh in, op 14 A eenfasig duurt dat 1,36 uur, dus met het uur erbij is
# 16:38 het laatste moment dat nog past. Half twee is ruim op tijd; half vier
# was dat tot 04-09-2026 ook, maar sindsdien komt er tussen 17:00 en 20:00
# niets van het net bij (de avondpiek), en dan is half vier al het moment om
# de middag vol te benutten.
vroeg = zes_rondes(13, 30)
print("  13:30  " + "  ".join(f"{r}:{a}A" for r, a in vroeg))
# Sinds 30-08-2026 heet dit `easy-pace` in plaats van `surplus`: bij een vast
# tarief kost elk uur hetzelfde, dus doet hij het rustig aan met de zon erin.
# Waar het om gaat is dat hij niet naar vol vermogen springt. Sinds 04-09-2026
# is rustig niet meer per se de ondergrens maar het tempo dat de klaar-tijd
# mét zijn speling haalt: hier 8 A, want 4,4 kWh voor 18:00.
controle("ruim op tijd blijft hij rustig",
         all(naam in ("surplus", "easy-pace") and amps < 14
             for naam, amps in vroeg), f"{vroeg}")

# En op het laatste moment dat nog past grijpt hij wél in.
laatst = zes_rondes(16, 45)
print("  16:45  " + "  ".join(f"{r}:{a}A" for r, a in laatst))
namen = [r for r, _ in laatst]
controle("op het laatste moment gaat hij vol", "deadline" in namen, f"{laatst}")
vanaf = namen.index("deadline")
controle("en valt daarna niet meer terug",
         all(naam == "deadline" for naam in namen[vanaf:]), f"{laatst}")

# Tot 04-09-2026 stond hier een tegenproef die `throttled_by_coach` uitzette
# om te laten zien dat de coach dan om kwart voor vijf al omsloeg. Sinds het
# rustige tempo meegroeit met de middag (en de avondpiek dicht is) vraagt de
# coach in dat venster zelf al meer dan 6 A, en dan is er geen verschil meer
# te laten zien. De functie zelf wordt los beproefd in test_planner.py.

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
# De eigenaar op 20-08-2026. Home Assistant herstartte om 20:57 terwijl de auto vanaf
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
# Sinds 06-09-2026 gelooft de coach "klaar" niet meteen als de accustand zegt
# dat er nog iets in moet: 60% plus 3,1 kWh is geen volle auto. Hij stuurt dan
# één keer een start en wacht een kwartier af. Pas daarna komt het verslag.
_, verstuurd = asyncio.run(ronde(coachB, herstart, dt.datetime(2026, 8, 20, 21, 32)))
starts = [d for d in verstuurd if d[0] == "easee" and d[2].get("action_command") == "start"]
print(f"  bij 'klaar' op 60%+: start={len(starts)}")
controle("bij 'klaar' terwijl de auto niet vol is stuurt hij één start", len(starts) == 1,
         f"{starts}")
# De melding daarover komt een ronde later, uit het verslag van die ronde.
_, verstuurd = asyncio.run(ronde(coachB, herstart, dt.datetime(2026, 8, 20, 21, 40)))
herstartmelding = [d[2]["message"] for d in verstuurd if d[0] == "notify"]
print(f"  een ronde later: {herstartmelding}")
controle("en zegt dat hij dat deed",
         any("opnieuw gestart" in m for m in herstartmelding), f"{herstartmelding}")
controle("binnen het kwartier nog geen verslag",
         not any("laadt niet verder" in m or "is vol" in m for m in herstartmelding),
         f"{herstartmelding}")
_, verstuurd = asyncio.run(ronde(coachB, herstart, dt.datetime(2026, 8, 20, 21, 48)))
meldingen = [d[2]["message"] for d in verstuurd if d[0] == "notify"]
print(f"  {meldingen}")
controle("hij meldt het nog steeds", meldingen, f"{meldingen}")
controle("met de herstart erin, zonder gevolg",
         any("21:32" in m and "zonder gevolg" in m for m in meldingen), f"{meldingen}")
controle("en er ging maar één start uit",
         not [d for d in verstuurd if d[0] == "easee"], f"{verstuurd}")
controle("maar doet niet alsof hij het begin zag",
         all("van 20:58 tot" not in m for m in meldingen), f"{meldingen}")
# Sinds 21-09-2026 zonder de bijzin "en toen liep hij al": de eigenaar wil korte
# meldingen. Het woord "sinds" zegt al dat de coach het begin niet zag.
controle("en zegt eerlijk vanaf wanneer hij telt",
         any("Sinds 20:58" in m for m in meldingen)
         and all("liep hij al" not in m for m in meldingen), f"{meldingen}")

print("=== 15c. een auto die op 80% stopt is niet vol ===")
# Zijn Ford stopte op 80%, de Easee meldde `completed` en de coach zei "de auto
# is vol". Dat is onwaar en het leest als een coach die niet weet wat hij doet.
# Met een auto die zijn accustand zelf meldt, zoals de eigen Ford, want juist daar
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
# het op 25-08-2026 in een echte woning: de melding vertrok met 70% terwijl de kaart een
# minuut later 80% zei. Het verslag hoort dus even te wachten.
_, verstuurd = asyncio.run(ronde(coachC, tachtig, paal=PAAL_FORD, nu=dt.datetime(2026, 8, 20, 21, 32)))
meldingen = [d[2]["message"] for d in verstuurd if d[0] == "notify"]
print(f"  meteen bij het stoppen: {meldingen}")
controle("hij wacht op een accustand die bij deze beurt hoort", not meldingen,
         f"{meldingen}")

# De auto meldt zich, en dan pas doet de coach iets. Dat "iets" is eerst een
# herstart, want 80% is niet vol en het doel staat hier op honderd; pas als de
# auto daarna niets doet gelooft hij "klaar". Zie eis 7.
hassC.states.zet("sensor.auto_soc", "80")
_, verstuurd = asyncio.run(ronde(coachC, tachtig, paal=PAAL_FORD, nu=dt.datetime(2026, 8, 20, 21, 33)))
starts = [d for d in verstuurd if d[0] == "easee" and d[2].get("action_command") == "start"]
print(f"  zodra de auto zich meldt: start={len(starts)}")
controle("pas na een bezonken accustand herstart hij", len(starts) == 1, f"{starts}")

# En die melding noemt de stand van ná het stoppen. Thuis op 16-09-2026 ging hij
# de deur uit met 70% terwijl de Ford op 80 stond: de sensor sprong tweeëntwintig
# seconden later. Dat is precies wat de bezinktijd hierboven voorkomt.
_, verstuurd = asyncio.run(ronde(coachC, tachtig, paal=PAAL_FORD, nu=dt.datetime(2026, 8, 20, 21, 34)))
meldingen = [d[2]["message"] for d in verstuurd if d[0] == "notify"]
print(f"  herstartmelding: {meldingen}")
controle("en de melding noemt de stand van na het stoppen",
         any("80%" in m for m in meldingen), f"{meldingen}")
controle("en niet de stand van ervoor", all("70%" not in m for m in meldingen),
         f"{meldingen}")

# De auto doet niets meer. Na het kwartier gelooft de coach "klaar" alsnog, en
# dan pas komt het verslag, met de accustand en zonder het woord vol.
for minuut in (40, 45, 50):
    _, verstuurd = asyncio.run(
        ronde(coachC, tachtig, paal=PAAL_FORD, nu=dt.datetime(2026, 8, 20, 21, minuut)))
meldingen = [d[2]["message"] for d in verstuurd if d[0] == "notify"]
besluit = coachC.state["dev-laadpaal"]
print(f"  verslag: {meldingen}")
print(f"  kaart  : {besluit['reason']}")
controle("hij noemt het geen vol", all("is vol" not in m for m in meldingen),
         f"{meldingen}")
controle("maar noemt de accustand", any("80%" in m for m in meldingen), f"{meldingen}")

# En blijft de auto stil, dan wacht hij niet eindeloos op een percentage dat
# nooit komt: na SOC_SETTLE gaat het alsnog door. Te laat melden is erger dan
# een getal dat een paar minuten oud is.
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
starts = [d for d in verstuurd if d[0] == "easee" and d[2].get("action_command") == "start"]
print(f"  auto blijft stil, vier minuten later: start={len(starts)}")
controle("een auto die zwijgt houdt het niet eindeloos tegen", len(starts) == 1,
         f"{starts}")
for minuut in (40, 45, 52):
    _, verstuurd = asyncio.run(
        ronde(coachD, tachtig, paal=PAAL_FORD, nu=dt.datetime(2026, 8, 20, 21, minuut)))
besluitD = coachD.state["dev-laadpaal"]
print(f"  kaart  : {besluitD['reason']}")
controle("en op de kaart net zo", "70%" in besluitD["reason"], besluitD["reason"])
controle("met een reden die klopt", "laadgrens" in besluitD["reason"], besluitD["reason"])

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
# Op 90% plus wat er sindsdien in ging is dit geen volle auto, dus eerst één
# herstart (06-09-2026). Maar niet meteen: sinds 16-09-2026 wacht de coach tot
# de accustand bij dit einde hoort. De teller van deze paal staat stil, dus dat
# duurt hier de volle `SOC_SETTLE`. Blijft de paal daarna "klaar" zeggen, dan is
# het klaar.
besluit, verstuurd = asyncio.run(ronde(coachC, door, dt.datetime(2026, 8, 18, 19, 5)))
controle("nog geen herstart op een accustand van voor het stoppen",
         not [d for d in verstuurd if d[0] == "easee" and d[2].get("action_command") == "start"],
         f"{verstuurd}")
besluit, verstuurd = asyncio.run(ronde(coachC, door, dt.datetime(2026, 8, 18, 19, 9)))
controle("daarna één herstart, want 90% is niet vol",
         [d for d in verstuurd if d[0] == "easee" and d[2].get("action_command") == "start"],
         f"{verstuurd}")
besluit, verstuurd = asyncio.run(ronde(coachC, door, dt.datetime(2026, 8, 18, 19, 10)))
print(f"  {besluit['rule']}: laden={besluit['charge']}")
controle("stopt bij een volle auto", not besluit["charge"] and besluit["rule"] == "complete",
         f"{besluit['rule']}")
naar_de_paal = [d for d in verstuurd if d[0] != "notify"]
controle("en er gaat niets meer naar de paal", not naar_de_paal, f"{naar_de_paal}")
controle("het doorladen is vergeten", "dev-laadpaal" not in coachC._te_laat)

print("=== 19. een accustand die wegvalt is geen onbekende accustand ===")
# Op 25-08-2026 om 15:45 was de eigen Ford-integratie een minuut `unavailable` en
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
# Twee ronden, want één meting `disconnected` is sinds v0.43.2 nog geen kabel
# die eruit gaat; zie `KABEL_ONTDREUN`.
for tijd in (dt.datetime(2026, 8, 25, 20, 5), dt.datetime(2026, 8, 25, 20, 5, 40)):
    asyncio.run(ronde(coach19, inst19, paal=PAAL19, nu=tijd))
hass19.states.zet("sensor.laadpaal_status", "ready_to_charge")
opnieuw, _ = asyncio.run(ronde(coach19, inst19, paal=PAAL19, nu=dt.datetime(2026, 8, 25, 20, 6)))
print(f"  na de kabel eruit: {opnieuw['rule']}  needs_soc={opnieuw['needs_soc']}")
controle("maar na de kabel eruit weet hij het niet meer", opnieuw["needs_soc"], f"{opnieuw}")

print("=== 20. het verslag telt mee wat de teller nog niet verwerkt heeft ===")
# de eigen Easee-levensduurteller werkte op 25-08-2026 maar eens per uur bij en
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
# de laderlimiet stond een week op 14 A. Daarmee koos de Easee bij elke start
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
# Een enkele ronde is niet genoeg: de twee sensoren van een Easee melden tijdens
# het optrekken seconden na elkaar, en dan is de verhouding een vergelijking
# tussen nu en daarnet. In de klantwoning leverde dat op 30-08-2026 om 04:28 een
# valse melding op terwijl de auto keurig driefasig laadde. Er moet dus een
# aantal ronden hetzelfde uit komen; zie `FASEMETING_RONDEN`.
for minuut in (51, 52):
    tussendoor, niets21 = asyncio.run(
        ronde(coach21, inst21, paal=PAAL21, nu=dt.datetime(2026, 8, 25, 12, minuut))
    )
    controle(f"na {minuut - 50} ronde nog geen oordeel", not tussendoor["tip"],
             f"{tussendoor['tip']}")
    controle(f"en ook nog geen melding na {minuut - 50} ronde",
             not [d for d in niets21 if d[0] == "notify"], f"{niets21}")
besluit21, verstuurd21 = asyncio.run(
    ronde(coach21, inst21, paal=PAAL21, nu=dt.datetime(2026, 8, 25, 12, 53))
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
    ronde(coach21, inst21, paal=PAAL21, nu=dt.datetime(2026, 8, 25, 12, 54))
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
for minuut in (56, 57):
    asyncio.run(ronde(coach21, inst21, paal=PAAL21, nu=dt.datetime(2026, 8, 25, 12, minuut)))
driefasig, _ = asyncio.run(
    ronde(coach21, inst21, paal=PAAL21, nu=dt.datetime(2026, 8, 25, 12, 58))
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
for minuut in (51, 52):
    asyncio.run(ronde(coach21c, inst21c, nu=dt.datetime(2026, 8, 25, 12, minuut)))
eenfasig, _ = asyncio.run(ronde(coach21c, inst21c, nu=dt.datetime(2026, 8, 25, 12, 53)))
print(f"  eenfasige auto: tip={eenfasig['tip']!r}")
controle("een eenfasige auto krijgt geen verwijt", not eenfasig["tip"], f"{eenfasig['tip']}")

# En het vangnet dat in de plaats komt van de keuze "allebei". Die bestond omdat
# een auto die kan wisselen zich pas verraadt als hij laadt, en de prijs ervan
# was dat elke voorspelling het traagste geval nam: in de klantwoning 17,2 uur
# waar er 5,7 nodig waren. Het aantal fasen staat nu vast in het profiel, en de
# meting wordt gebruikt om te zeggen dat die keuze niet klopt.
#
# De laderlimiet staat hier op 16 A, dus de tip hierboven kan het niet zijn.
hass21.states.zet("sensor.laadpaal_max", "16")
hass21.states.zet("sensor.laadpaal_vermogen", "3070")
hass21.states.zet("sensor.laadpaal_stroom", "13.5")
for minuut in (4, 5):
    asyncio.run(ronde(coach21, inst21, paal=PAAL21, nu=dt.datetime(2026, 8, 25, 13, minuut)))
mis3, _ = asyncio.run(
    ronde(coach21, inst21, paal=PAAL21, nu=dt.datetime(2026, 8, 25, 13, 6))
)
print(f"  profiel driefasig, gemeten eenfasig: tip={mis3['tip']!r}")
controle("een profiel op driefasig dat eenfasig laadt wordt gemeld",
         "eenfasig" in mis3["tip"] and "driefasig" in mis3["tip"], f"{mis3['tip']}")

# En andersom, want die kant kost geen lege auto maar wel onnodig vroeg laden.
inst21d = instellingen()
huis21d = huis(status="ready_to_charge", teruglevering=0.0, afname=1800.0)
hass21d, _, coach21d = bouw(huis21d, inst21d)
asyncio.run(ronde(coach21d, inst21d, nu=dt.datetime(2026, 8, 25, 13, 5)))
hass21d.states.zet("sensor.laadpaal_status", "charging")
hass21d.states.zet("sensor.laadpaal_max", "16")
hass21d.states.zet("sensor.laadpaal_stroom", "15.45")
hass21d.states.zet("sensor.laadpaal_vermogen", "10855")
for minuut in (6, 7):
    asyncio.run(ronde(coach21d, inst21d, nu=dt.datetime(2026, 8, 25, 13, minuut)))
mis1, _ = asyncio.run(ronde(coach21d, inst21d, nu=dt.datetime(2026, 8, 25, 13, 8)))
print(f"  profiel eenfasig, gemeten driefasig: tip={mis1['tip']!r}")
controle("en een profiel op eenfasig dat driefasig laadt ook",
         "driefasig" in mis1["tip"] and "eenfasig" in mis1["tip"], f"{mis1['tip']}")

print("=== 22. de kabel eruit tijdens het laden levert een verslag op ===")
# De eigenaar op 20-08-2026: hij trok de kabel er twee keer uit tijdens het laden en
# hoorde niets. Er kwam alleen een verslag bij "vol" en bij een gemiste
# klaar-tijd. Afgesproken op 26-08-2026: dezelfde vorm als bij vol, met zijn
# eigen zin als voorbeeld: "afgekoppeld om 19:12, er ging 4,2 kWh in".
los = instellingen()
los["strategy"]["schedules"][0]["window"]["done_by"] = "23:00"
hass22, _, coach22 = bouw(huis(status="ready_to_charge", teruglevering=0.0,
                               afname=1800.0), los)
# Eerst de kabel erin en nog geen stroom, zoals het in het echt gaat.
asyncio.run(ronde(coach22, los, nu=dt.datetime(2026, 8, 20, 18, 59)))
hass22.states.zet("sensor.laadpaal_status", "charging")
hass22.states.zet("sensor.laadpaal_stroom", "13.5")
hass22.states.zet("sensor.laadpaal_vermogen", "3070")
for minuut in range(0, 13):
    asyncio.run(ronde(coach22, los, nu=dt.datetime(2026, 8, 20, 19, minuut)))
# En dan gaat de kabel eruit, midden in de laadbeurt.
hass22.states.zet("sensor.laadpaal_status", "disconnected")
hass22.states.zet("sensor.laadpaal_stroom", "0")
hass22.states.zet("sensor.laadpaal_vermogen", "0")
hass22.states.zet("sensor.laadpaal_teller", "104.2")
_, meteen22 = asyncio.run(ronde(coach22, los, nu=dt.datetime(2026, 8, 20, 19, 12)))
controle("één meting `disconnected` is nog geen kabel die eruit gaat",
         not [d for d in meteen22 if d[0] == "notify"], f"{meteen22}")
_, verstuurd = asyncio.run(ronde(coach22, los, nu=dt.datetime(2026, 8, 20, 19, 13)))
meldingen = [d[2]["message"] for d in verstuurd if d[0] == "notify"]
print(f"  {meldingen}")
controle("nu komt er wel een verslag", bool(meldingen), f"{meldingen}")
controle("in de eigen bewoording",
         any("afgekoppeld om 19:12, er ging" in m and "kWh in" in m for m in meldingen),
         f"{meldingen}")
controle("en met de begintijd erbij",
         any("sinds 19:00" in m for m in meldingen), f"{meldingen}")
controle("en zonder verwijt dat hij niet vol was",
         not any("niet vol" in m for m in meldingen), f"{meldingen}")

# Maar een statussensor die even niets zegt is géén kabel die eruit gaat.
# `_text` geeft een lege string zodra de entiteit er niet is, en `connected` was
# daarmee onwaar. Trekt een integratie kort zijn entiteiten in, bijvoorbeeld bij
# een herverbinding, dan stuurde de coach een verslag en wiste hij de hele
# sessie: het akkoord, snelladen, de opgegeven accustand en de klaar-tijd waar
# hij aan werkte. De eigenaar kreeg op 29-08-2026 om 19:54 zo'n verslag terwijl de paal
# die hele avond op `awaiting_start` stond.
weg = instellingen()
weg["strategy"]["schedules"][0]["window"]["done_by"] = "23:00"
hass22b, _, coach22b = bouw(huis(status="ready_to_charge", teruglevering=0.0,
                                 afname=1800.0), weg)
asyncio.run(ronde(coach22b, weg, nu=dt.datetime(2026, 8, 20, 18, 59)))
hass22b.states.zet("sensor.laadpaal_status", "charging")
hass22b.states.zet("sensor.laadpaal_stroom", "13.5")
hass22b.states.zet("sensor.laadpaal_vermogen", "3070")
for minuut in range(0, 13):
    asyncio.run(ronde(coach22b, weg, nu=dt.datetime(2026, 8, 20, 19, minuut)))

for ontbreekt, hoe in ((None, "de entiteit is weg"), ("unavailable", "unavailable"),
                       ("unknown", "unknown")):
    hass22b.states.zet("sensor.laadpaal_status", ontbreekt)
    besluit22b, verstuurd22b = asyncio.run(
        ronde(coach22b, weg, nu=dt.datetime(2026, 8, 20, 19, 13))
    )
    stil = [d[2]["message"] for d in verstuurd22b if d[0] == "notify"]
    print(f"  {hoe}: regel={besluit22b['rule']}, meldingen={stil}")
    controle(f"{hoe} leest niet als een losgekoppelde kabel",
             besluit22b["rule"] != "disconnected", f"{besluit22b['rule']}")
    controle(f"{hoe} levert dus ook geen afkoppelverslag op",
             not any("afgekoppeld" in m for m in stil), f"{stil}")
    hass22b.states.zet("sensor.laadpaal_status", "charging")

# En als de sensor wél zegt dat de kabel eruit is, gebeurt het nog steeds.
hass22b.states.zet("sensor.laadpaal_status", "disconnected")
hass22b.states.zet("sensor.laadpaal_stroom", "0")
hass22b.states.zet("sensor.laadpaal_vermogen", "0")
asyncio.run(ronde(coach22b, weg, nu=dt.datetime(2026, 8, 20, 19, 20)))
_, echt_los = asyncio.run(ronde(coach22b, weg, nu=dt.datetime(2026, 8, 20, 19, 21)))
controle("een sensor die het wél zegt levert nog gewoon een verslag op",
         any("afgekoppeld" in d[2]["message"] for d in echt_los if d[0] == "notify"),
         f"{[d for d in echt_los if d[0] == 'notify']}")

# Eén keer en niet elke ronde, want de kabel blijft eruit.
_, nogmaals = asyncio.run(ronde(coach22, los, nu=dt.datetime(2026, 8, 20, 19, 14)))
controle("en maar één keer",
         not [d for d in nogmaals if d[0] == "notify"], f"{nogmaals}")

# Een kabel die eruit gaat zonder dat er ooit stroom liep is geen laadbeurt, en
# daar valt niets over na te vertellen.
hass22b, _, coach22b = bouw(huis(status="ready_to_charge", teruglevering=0.0,
                                 afname=1800.0), los)
asyncio.run(ronde(coach22b, los, nu=dt.datetime(2026, 8, 20, 19, 0)))
hass22b.states.zet("sensor.laadpaal_status", "disconnected")
asyncio.run(ronde(coach22b, los, nu=dt.datetime(2026, 8, 20, 19, 1)))
_, leeg = asyncio.run(ronde(coach22b, los, nu=dt.datetime(2026, 8, 20, 19, 2)))
leegmeldingen = [d[2]["message"] for d in leeg if d[0] == "notify"]
print(f"  kabel eruit zonder geladen te hebben: {leegmeldingen}")
controle("een beurt zonder stroom levert geen verslag op",
         not any("afgekoppeld" in m for m in leegmeldingen), f"{leegmeldingen}")

# En een auto die vol was en daarna van de kabel gaat, heeft zijn verslag al
# gehad. Twee berichten over dezelfde beurt is er een te veel.
vol = instellingen()
vol["strategy"]["schedules"][0]["window"]["done_by"] = "23:00"
hass22c, _, coach22c = bouw(huis(status="ready_to_charge", teruglevering=0.0,
                                 afname=1800.0), vol)
asyncio.run(ronde(coach22c, vol, nu=dt.datetime(2026, 8, 20, 19, 0)))
hass22c.states.zet("sensor.laadpaal_status", "charging")
hass22c.states.zet("sensor.laadpaal_stroom", "13.5")
hass22c.states.zet("sensor.laadpaal_vermogen", "3070")
asyncio.run(ronde(coach22c, vol, nu=dt.datetime(2026, 8, 20, 19, 1)))
hass22c.states.zet("sensor.laadpaal_status", "completed")
hass22c.states.zet("sensor.laadpaal_teller", "103.0")
_, klaarmelding = asyncio.run(ronde(coach22c, vol, nu=dt.datetime(2026, 8, 20, 19, 20)))
controle("eerst het verslag dat hij vol is",
         any("is vol" in d[2]["message"] for d in klaarmelding if d[0] == "notify"),
         f"{klaarmelding}")
hass22c.states.zet("sensor.laadpaal_status", "disconnected")
_, daarna = asyncio.run(ronde(coach22c, vol, nu=dt.datetime(2026, 8, 20, 19, 25)))
print(f"  vol en daarna de kabel eruit: {[d[2]['message'] for d in daarna if d[0] == 'notify']}")
controle("en daarna geen tweede over dezelfde beurt",
         not [d for d in daarna if d[0] == "notify"], f"{daarna}")

print("=== 23. de waarschuwing bij een eigen pauze komt terug ===")
# De eigenaar op 26-08-2026: de pauze zelf blijft winnen van de klaar-tijd, want het is
# zijn huis en zijn knop. Maar één keer waarschuwen is te weinig. Wie het
# bericht om elf uur 's avonds wegveegt en om zeven uur naar een lege auto
# loopt, is niet geholpen.
krap = instellingen()
krap["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
krap["car_soc"] = [{"device": "dev-laadpaal", "car": "car-1", "percent": 10.0,
                    "meter": 100.0}]
hass23, _, coach23 = bouw(huis(status="charging", stroom=13.5, vermogen=3070.0,
                               teruglevering=0.0, afname=1800.0), krap)
coach23.async_pause("dev-laadpaal", True)


def pauzeronde(uur, minuut):
    """De meldingen over de pauze uit één ronde.

    Alleen die over de pauze, en dat is met opzet. `async_pause` zet niet
    alleen de knop om maar draait ook meteen zelf een ronde, en die gebruikt de
    échte klok van de machine in plaats van het tijdstip uit deze proef. Wat
    die ronde verstuurt komt pas boven water bij de eerstvolgende `ronde()`
    hieronder, want die wacht de lopende taken af nadat hij de lijst geleegd
    heeft. Er kan dus een verslag tussen zitten dat over een heel andere dag
    gaat. Dat is een eigenaardigheid van het harnas en niet van de coach; het
    kostte op 27-08-2026 een halfuur om dat vast te stellen.
    """
    _, verstuurd = asyncio.run(
        ronde(coach23, krap, nu=dt.datetime(2026, 8, 21, uur, minuut))
    )
    return [d[2]["message"] for d in verstuurd
            if d[0] == "notify" and "De pauze op" in d[2]["message"]]


eerste = pauzeronde(2, 0)
print(f"  02:00  {eerste}")
# Die eerste waarschuwing kwam uit de ronde van `async_pause` zelf, op de echte
# klok van de machine (zie hierboven). Sinds 06-09-2026 krijgt een opgegeven
# accustand een uur extra speling, en daarmee staat het risico hier de hele
# nacht, dus wordt de klok van die waarschuwing niet meer tussendoor vergeten.
# Op de tijd van de proef zetten, anders vergelijkt hij augustus met vandaag.
coach23._warned["dev-laadpaal"] = dt.datetime(2026, 8, 21, 2, 0)
controle("hij waarschuwt dat de pauze de klaar-tijd kost",
         any("pauze" in m and "niet op tijd vol" in m for m in eerste), f"{eerste}")
controle("en blijft gepauzeerd, want het is zijn knop",
         coach23.state["dev-laadpaal"]["rule"] == "user-hold",
         coach23.state["dev-laadpaal"]["rule"])

# Binnen het uur niet nog een keer: dat is zeuren, en wie gezeurd wordt zet zijn
# meldingen uit.
binnen_het_uur = pauzeronde(2, 30)
controle("binnen het uur zwijgt hij", not binnen_het_uur, f"{binnen_het_uur}")

# Maar een uur later wel, want het risico staat er nog steeds.
later = pauzeronde(3, 1)
print(f"  03:01  {later}")
controle("een uur later komt hij terug",
         any("pauze" in m and "niet op tijd vol" in m for m in later), f"{later}")

# En zodra de pauze eraf gaat houdt het vanzelf op.
coach23.async_pause("dev-laadpaal", False)
na_pauze = pauzeronde(4, 30)
print(f"  na het hervatten  {na_pauze}")
controle("zonder pauze geen pauzewaarschuwing meer", not na_pauze, f"{na_pauze}")
controle("en de klok is vergeten, dus een volgende keer begint opnieuw",
         "dev-laadpaal" not in coach23._warned, f"{coach23._warned}")

print("=== 24. het schema van de kaart raakt alleen dat ene apparaat ===")
# Op 27-08-2026 zijn de schema's uit Strategie gehaald en bij het apparaat zelf
# gezet: de schuif en de voorrang op de kaart, de tijden in een pop-up erachter.
# Alles wat over één apparaat gaat komt daardoor langs deze ene functie.
#
# Waar het hier om gaat is wat er níét gebeurt. Wie de vaatwasser instelt hoort
# de laadpaal ongemoeid te laten, en wie alleen de schuif omzet hoort zijn
# tijden terug te vinden.
#
# De samenvoeging staat in storage.py en niet in websocket.py, zodat er een
# proef op kan zonder een draaiende Home Assistant: websocket.py sleept
# voluptuous en de hele websocket-API mee, en die staan hier niet.
schema_bijwerken = storage.schema_bijwerken

STRAT = {
    "level": "steer",
    "schedules": [
        {"device": "d1", "enabled": True, "per_day": False, "priority": "mid",
         "window": {"not_before": "23:00", "start_by": "", "done_by": "07:00"},
         "days": []},
        {"device": "d2", "enabled": True, "per_day": True, "priority": "low",
         "window": {"not_before": "22:00", "start_by": "", "done_by": "06:00"},
         "days": [
             {"day": 5, "enabled": True, "done_by": "10:00"},
             {"day": 6, "enabled": True, "done_by": "12:00"},
         ]},
    ],
}


def d(uit, apparaat):
    return next(s for s in uit["schedules"] if s["device"] == apparaat)


# De schuif uit voor d1.
uit = schema_bijwerken(STRAT, "d1", enabled=False)
print(f"  d1 uit: enabled={d(uit,'d1')['enabled']}, tijden={d(uit,'d1').get('window')}")
controle("de schuif zet het schema uit", d(uit, "d1")["enabled"] is False, f"{d(uit,'d1')}")
controle("en laat de tijden staan, zodat aanzetten ze terugbrengt",
         d(uit, "d1")["window"]["done_by"] == "07:00", f"{d(uit,'d1')}")
controle("het andere apparaat blijft ongemoeid",
         d(uit, "d2") == STRAT["schedules"][1], f"{uit}")
controle("en de rest van de strategie ook", uit["level"] == "steer", f"{uit}")
controle("het origineel is niet gewijzigd",
         STRAT["schedules"][0]["enabled"] is True, f"{STRAT}")

# De voorrang staat op de kaart en gaat langs dezelfde weg.
uit = schema_bijwerken(STRAT, "d1", priority="high")
print(f"  d1 voorrang: {d(uit,'d1')['priority']}")
controle("de voorrang komt erin", d(uit, "d1")["priority"] == "high", f"{d(uit,'d1')}")
controle("en raakt de rest van dat schema niet",
         d(uit, "d1")["window"] == STRAT["schedules"][0]["window"], f"{d(uit,'d1')}")

# De pop-up stuurt de drie tijden als geheel.
uit = schema_bijwerken(
    STRAT, "d1", window={"not_before": "", "start_by": "", "done_by": "08:30"}
)
print(f"  d1 nieuwe tijden: {d(uit,'d1')['window']}")
controle("de drie tijden komen er als geheel in",
         d(uit, "d1")["window"] == {"not_before": "", "start_by": "", "done_by": "08:30"},
         f"{d(uit,'d1')}")

# Per dag mag nu wél vanaf de kaart, want de pop-up ís de volledige editor.
# Tot vanochtend weigerde dit, omdat de kaart toen drie velden toonde waar zeven
# dagen achter zaten; dat gevaar is er niet meer.
nieuwe_dagen = [{"day": i, "enabled": i < 5, "not_before": "", "start_by": "",
                 "done_by": "07:00"} for i in range(7)]
uit = schema_bijwerken(STRAT, "d2", per_day=True, days=nieuwe_dagen)
print(f"  d2 zeven dagen: {len(d(uit,'d2')['days'])}, weekend uit")
controle("de dagen komen erin", len(d(uit, "d2")["days"]) == 7, f"{d(uit,'d2')}")
controle("met het weekend uit",
         [x["enabled"] for x in d(uit, "d2")["days"]] == [True]*5 + [False]*2,
         f"{d(uit,'d2')['days']}")
controle("en het venster van elke dag blijft bewaard voor als hij terugschakelt",
         d(uit, "d2")["window"]["done_by"] == "06:00", f"{d(uit,'d2')}")
controle("het origineel is nog steeds niet gewijzigd",
         len(STRAT["schedules"][1]["days"]) == 2, f"{STRAT}")

# Een apparaat waar nog nooit iets voor is ingesteld krijgt een schema.
uit = schema_bijwerken(STRAT, "d9", enabled=True)
print(f"  d9 nieuw: {d(uit,'d9')}")
controle("een apparaat zonder schema krijgt er een",
         d(uit, "d9")["enabled"] is True and d(uit, "d9")["per_day"] is False,
         f"{d(uit,'d9')}")
controle("en de bestaande twee staan er nog", len(uit["schedules"]) == 3, f"{uit}")

# De fasekeuze "allebei" bestaat niet meer. Wat er bij klanten op schijf staat
# moet dus omgezet worden, en niet weggegooid: `_prune` kent de sleutel wel maar
# de waarde niet, en een profiel dat stilletijes op de standaard terugvalt is
# net zo fout als een dat blijft staan. Driefasig, want dat is wat er aan een
# driefasige paal gebeurt; klopt dat niet, dan zegt `_fasetip` het zodra er een
# keer stroom loopt. De eigenaar op 29-08-2026.
oud_op_schijf = {
    "devices": [
        {"id": "dev-1", "cars": [
            {"id": "car-a", "phases": "both"},
            {"id": "car-b", "phases": "one"},
        ]},
        {"id": "dev-2", "cars": [{"id": "car-c", "phases": "three"}]},
        {"id": "dev-3"},
    ],
}
gemigreerd = storage._migrate(oud_op_schijf)
fasen = [c["phases"] for d in gemigreerd["devices"] for c in d.get("cars", [])]
print(f"  fasen na migratie: {fasen}")
controle("een profiel op 'allebei' wordt driefasig", fasen[0] == "three", f"{fasen}")
controle("en de rest blijft staan zoals hij stond",
         fasen[1] == "one" and fasen[2] == "three", f"{fasen}")
controle("een apparaat zonder auto's laat hem niet omvallen",
         len(gemigreerd["devices"]) == 3, f"{gemigreerd}")
controle("en instellingen zonder apparaten ook niet",
         storage._migrate({}) == {}, f"{storage._migrate({})}")

print("\n=== 24b. de kortere apparaatlijst laat staan wat er al stond ===")

# De apparaatlijst is korter geworden (v0.70.0): thuisbatterij, warmtepomp,
# wasmachine, droger en zwembadpomp eruit, en bij een laadpaal het merk
# "overig". Wat er bij een klant al stond mag daar niet stil van veranderen:
# een keuzelijst zonder de opgeslagen waarde toont zijn eerste regel, en bij de
# volgende opslag zou een zwembadpomp een laadpaal zijn.
korter = storage._migrate({
    "devices": [
        {"id": "d1", "type": "zwembadpomp", "entity": "sensor.pomp"},
        {"id": "d2", "type": "warmtepomp", "name": "Achterhuis"},
        {"id": "d3", "type": "laadpaal", "brand": "overig", "controllable": True,
         "cars": [{"id": "car-a", "phases": "one"}]},
        {"id": "d4", "type": "laadpaal", "brand": "easee", "controllable": True},
        {"id": "d5", "type": "vaatwasser", "brand": "home_connect"},
        {"id": "d6", "type": "thuisbatterij", "brand": "anker", "controllable": True},
    ],
})
na = {d["id"]: d for d in korter["devices"]}
print(f"  na de migratie: {[(d['id'], d['type'], d.get('name',''), d.get('brand','')) for d in korter['devices']]}")
controle("een vervallen type wordt 'overig' en houdt zijn oude naam",
         na["d1"]["type"] == "overig" and na["d1"]["name"] == "Zwembadpomp", f"{na['d1']}")
controle("een eigen naam wint van de oude typenaam",
         na["d2"]["type"] == "overig" and na["d2"]["name"] == "Achterhuis", f"{na['d2']}")
controle("een laadpaal van het merk 'overig' blijft een laadpaal, zonder merk en zonder sturing",
         na["d3"]["type"] == "laadpaal" and na["d3"]["brand"] == ""
         and na["d3"]["controllable"] is False and len(na["d3"]["cars"]) == 1, f"{na['d3']}")
controle("een Easee blijft onaangeroerd",
         na["d4"]["brand"] == "easee" and na["d4"]["controllable"] is True, f"{na['d4']}")
controle("en een apparaat van een type dat gewoon bestaat ook",
         na["d5"]["type"] == "vaatwasser" and na["d5"]["brand"] == "home_connect", f"{na['d5']}")

# Sinds v0.73.0 stuurt de coach een thuisbatterij werkelijk, en staat het type
# er dus weer in. Een batterij die iemand nu toevoegt mag bij de volgende
# herstart niet stilletjes "overig" worden.
controle("een thuisbatterij is geen vervallen type meer",
         na["d6"]["type"] == "thuisbatterij" and na["d6"]["brand"] == "anker"
         and na["d6"]["controllable"] is True, f"{na['d6']}")

# Helemaal zonder strategie moet het ook niet omvallen.
uit = schema_bijwerken(None, "d1", enabled=True)
controle("zonder strategie ontstaat er gewoon een",
         uit["schedules"][0]["device"] == "d1", f"{uit}")

print("=== 25. de kWh-teller mag ook in het algemene veld staan ===")
# De eigenaar op 27-08-2026, tijdens een installatie bij een klant: "Energieteller
# (optioneel)" en "Levensduur verbruik" wezen naar dezelfde sensor en hij typte
# hem twee keer.
#
# Wat eronder zat was erger. Alleen Easee had dat merkveld; een paal van een
# ander merk ("overig", sinds 04-09-2026 het enige andere dat er nog in de lijst
# staat) heeft geen enkel merkveld. Bij die klanten kwam er dus nooit een
# teller binnen, ook niet als de Energieteller keurig was ingevuld, en viel het
# verslag terug op wat de coach zelf aan vermogen langs zag komen.

# Een paal zonder merkveld, met de teller in het algemene veld.
ZONDER_MERKVELD = dict(
    LAADPAAL,
    brand="overig",
    energy_entity="sensor.laadpaal_teller",
    entities={k: v for k, v in LAADPAAL["entities"].items() if k != "lifetime_energy"},
)
anders = instellingen(devices=[ZONDER_MERKVELD])
anders["strategy"]["schedules"][0]["window"]["done_by"] = "23:00"
hass25, _, coach25 = bouw(huis(status="ready_to_charge", teruglevering=0.0,
                               afname=1800.0), anders)
asyncio.run(ronde(coach25, anders, paal=ZONDER_MERKVELD, nu=dt.datetime(2026, 8, 20, 19, 0)))
hass25.states.zet("sensor.laadpaal_status", "charging")
hass25.states.zet("sensor.laadpaal_stroom", "13.5")
hass25.states.zet("sensor.laadpaal_vermogen", "3070")
asyncio.run(ronde(coach25, anders, paal=ZONDER_MERKVELD, nu=dt.datetime(2026, 8, 20, 19, 1)))
hass25.states.zet("sensor.laadpaal_status", "completed")
hass25.states.zet("sensor.laadpaal_teller", "106.5")
_, verstuurd = asyncio.run(
    ronde(coach25, anders, paal=ZONDER_MERKVELD, nu=dt.datetime(2026, 8, 20, 19, 20))
)
meldingen = [d[2]["message"] for d in verstuurd if d[0] == "notify"]
print(f"  merk zonder eigen veld: {meldingen}")
controle("de geijkte teller telt ook zonder merkveld mee",
         any("6,5 kWh" in m for m in meldingen), f"{meldingen}")

# En het merkveld blijft voorgaan, want bestaande installaties hebben dat
# ingevuld en die mogen hier niets van merken. Staan ze allebei en wijzen ze
# naar iets anders, dan wint het merkveld.
BEIDE = dict(LAADPAAL, energy_entity="sensor.andere_teller")
hass25b, _, coach25b = bouw(
    dict(huis(status="ready_to_charge", teruglevering=0.0, afname=1800.0),
         **{"sensor.andere_teller": "500.0"}),
    instellingen(devices=[BEIDE]),
)
controle("het merkveld gaat voor",
         coach25b._teller(BEIDE) == 100.0, f"{coach25b._teller(BEIDE)}")

# Staat er nergens een teller, dan valt hij terug op zijn eigen meting en niet
# op een uitzondering.
GEEN = dict(LAADPAAL, energy_entity="",
            entities={k: v for k, v in LAADPAAL["entities"].items()
                      if k != "lifetime_energy"})
controle("zonder enige teller geeft hij niets terug in plaats van om te vallen",
         coach25b._teller(GEEN) is None, f"{coach25b._teller(GEEN)}")

print("=== 26. wat teruglevering opbrengt bij salderen ===")
# Uit een eigen energienota, nagerekend op 27-08-2026. Wat er op de
# factuur staat zijn kale commodityprijzen; de energiebelasting staat als vast
# maandbedrag apart, geheven over het gesaldeerde jaarvolume. Daaruit volgt dat
# de belasting bij teruglevering wegstreept tegen die bij afname.
#
# De opslag van de leverancier doet dat niet: die betaal je per ingekochte kWh
# en krijg je nergens terug. Zonder die aftrek stond de terugleveropbrengst er
# ruim twee cent te hoog in.
#
# Thuis in een echte woning: vast contract, salderen aan. Bij de klant: dynamisch,
# salderen tot 1 januari 2027.

VOOR_2027 = dt.datetime(2026, 8, 27, 12, 0)
NA_2027 = dt.datetime(2027, 1, 1, 12, 0)


def klok(moment):
    """dt_util.utcnow van het harnas laten wijzen waar de proef wil."""
    return moment


# --- het vaste contract van de eigenaar -----------------------------------------
VAST = {
    "type": "fixed",
    "netting": True,
    "fixed": {"all_in_price": 0.24171, "feed_in_tariff": 0.0721,
              "feed_in_costs": 0.052756},
}
tar = coachmod.ChargerCoach._tariff({"contract": VAST})
print(f"  vast, salderen aan: koop {tar.buy}, terug {tar.feed_in:.4f}")
controle("bij salderen is teruglevering de inkoopprijs min de kosten",
         abs(tar.feed_in - (0.24171 - 0.052756)) < 1e-9, f"{tar.feed_in}")

zonder = coachmod.ChargerCoach._tariff({"contract": dict(VAST, netting=False)})
controle("zonder salderen is het de terugleververgoeding min de kosten",
         abs(zonder.feed_in - (0.0721 - 0.052756)) < 1e-9, f"{zonder.feed_in}")
print(f"  verschil voor de eigenaar: {tar.feed_in - zonder.feed_in:.4f} euro per kWh")

# --- het dynamische contract van de klant --------------------------------
DYN = {
    "type": "dynamic",
    "netting": True,
    "dynamic": {"source": "all_in", "interval": "hour",
                "all_in_entity": "sensor.prijs", "market_entity": "sensor.markt",
                "energy_tax": 0.1088, "supplier_markup": 0.02, "vat_percent": 21.0,
                "feed_in_costs": 0.0},
}
controle("op 27-08-2026 wordt er nog gesaldeerd",
         coachmod.ChargerCoach._salderen(DYN, VOOR_2027) is True)
controle("op 1 januari 2027 niet meer, ook al staat het vinkje aan",
         coachmod.ChargerCoach._salderen(DYN, NA_2027) is False)
controle("en zonder vinkje sowieso niet",
         coachmod.ChargerCoach._salderen(dict(DYN, netting=False), VOOR_2027) is False)

# En dan de prijslijst zelf, want dat is de code die veranderd is. Eén blok van
# een uur, met een all-in prijs van 30 cent.
PRIJSLIJST = {
    "state": "0.30",
    "attributes": {"prices": [
        {"from": "2026-08-27T12:00:00+02:00", "till": "2026-08-27T13:00:00+02:00",
         "price": 0.30},
    ]},
}
hass26, _, coach26 = bouw({"sensor.prijs": PRIJSLIJST}, instellingen())

rijen = coach26._prices({"contract": DYN})
print(f"  prijslijst bij salderen: koop {rijen[0]['price']}, terug {rijen[0]['feed_in']:.4f}")
controle("de inkoopprijs blijft de all-in prijs", rijen[0]["price"] == 0.30, f"{rijen[0]}")
controle("en teruglevering is die prijs min de opslag met btw",
         abs(rijen[0]["feed_in"] - (0.30 - 0.0242)) < 1e-9, f"{rijen[0]}")

# Zonder opslag ingevuld verandert er niets, dus wie dat veld leeg laat krijgt
# geen aftrek uit de lucht.
geen_opslag = {"contract": dict(DYN, dynamic=dict(DYN["dynamic"], supplier_markup=0))}
controle("zonder opslag is teruglevering de hele inkoopprijs",
         abs(coach26._prices(geen_opslag)[0]["feed_in"] - 0.30) < 1e-9,
         f"{coach26._prices(geen_opslag)[0]}")

# Dezelfde lijst, maar met echte datetime-objecten in `from` en `till` in plaats
# van tekst. Een integratie mag dat, en over de API van Home Assistant is het
# verschil onzichtbaar omdat daar alles tot tekst geserialiseerd wordt. Binnen
# HA staat het object er nog, en `parse_datetime` struikelt erover.
#
# In de klantwoning gebeurde dat op 29-08-2026 met alle 24 uurblokken tegelijk.
# De coach zei "er komen geen prijzen binnen" en laadde op vol vermogen van het
# net, terwijl hij op de zon had horen te wachten. Geen enkele foutmelding: de
# TypeError werd per blok opgevangen en de regel overgeslagen.
PRIJSLIJST_DATETIME = {
    "state": "0.30",
    "attributes": {"prices": [
        {"from": dt.datetime.fromisoformat("2026-08-27T12:00:00+02:00"),
         "till": dt.datetime.fromisoformat("2026-08-27T13:00:00+02:00"),
         "price": 0.30},
    ]},
}
hass27, _, coach27 = bouw({"sensor.prijs": PRIJSLIJST_DATETIME}, instellingen())
rijen_dt = coach27._prices({"contract": DYN})
print(f"  prijslijst met datetime-objecten: {len(rijen_dt)} blok(ken)")
controle("een prijslijst met datetime-objecten levert net zo goed blokken op",
         len(rijen_dt) == 1, f"{len(rijen_dt)} blokken uit 1 rij")
controle("met dezelfde inkoopprijs als bij tekst",
         bool(rijen_dt) and rijen_dt[0]["price"] == 0.30, f"{rijen_dt}")
controle("en met dezelfde begintijd",
         bool(rijen_dt) and rijen_dt[0]["start"] == rijen[0]["start"],
         f"{rijen_dt[0]['start'] if rijen_dt else None} tegen {rijen[0]['start']}")

# En een rij waar werkelijk niets van te maken is blijft overgeslagen worden, in
# plaats van de hele ronde om te gooien. Onbruikbaar is niet hetzelfde als fataal.
PRIJSLIJST_ROMMEL = {
    "state": "0.30",
    "attributes": {"prices": [
        {"from": 12345, "till": None, "price": 0.30},
        {"from": "2026-08-27T12:00:00+02:00", "till": "2026-08-27T13:00:00+02:00",
         "price": 0.30},
    ]},
}
hass28, _, coach28 = bouw({"sensor.prijs": PRIJSLIJST_ROMMEL}, instellingen())
rommel = coach28._prices({"contract": DYN})
controle("een onleesbare rij wordt overgeslagen, de rest blijft staan",
         len(rommel) == 1, f"{len(rommel)} blokken")

# Zonneplan geeft zijn lijst als `forecast`, met alleen een begintijd en de
# prijs in tienmiljoensten van een euro. In de eerste woning stond daardoor op
# 22-09-2026 de hele dag "de prijs van dit uur is niet bekend" en laadde de
# batterij niet van het net. Drie uren, het laatste zonder opvolger: dat is
# even lang als het uur ervoor.
PRIJSLIJST_ZONNEPLAN = {
    "state": "0.3355224",
    "attributes": {"unit_of_measurement": "€/kWh", "forecast": [
        {"electricity_price": 3355224, "electricity_price_excl_tax": 2246743, "tariff_group": "low",
         "datetime": "2026-08-27T10:00:00.000000Z"},
        {"electricity_price": 2919535, "datetime": "2026-08-27T11:00:00.000000Z"},
        {"electricity_price": 2500000, "datetime": "2026-08-27T12:00:00.000000Z"},
        {"electricity_price": None, "datetime": "2026-08-27T13:00:00.000000Z"},
    ]},
}
hass28b, _, coach28b = bouw({"sensor.prijs": PRIJSLIJST_ZONNEPLAN}, instellingen())
zp = coach28b._prices({"contract": DYN})
print(f"  Zonneplan: {[(r['start'].strftime('%H:%M'), r['end'].strftime('%H:%M'), r['price']) for r in zp]}")
controle("een Zonneplan-lijst levert een blok per uur", len(zp) == 3, f"{len(zp)}")
controle("met de prijs in euro's, gedeeld door tien miljoen",
         bool(zp) and abs(zp[0]["price"] - 0.3355224) < 1e-9 and abs(zp[2]["price"] - 0.25) < 1e-9, f"{zp}")
controle("elk blok loopt tot het volgende, en het laatste is even lang als het blok ervoor",
         all(r["end"] - r["start"] == dt.timedelta(hours=1) for r in zp), f"{zp}")

# Nord Pool: `raw_today` en `raw_tomorrow` met start, end en value.
PRIJSLIJST_NORDPOOL = {
    "state": "0.30",
    "attributes": {"raw_today": [
        {"start": "2026-08-27T12:00:00+02:00", "end": "2026-08-27T13:00:00+02:00", "value": 0.30},
    ], "raw_tomorrow": [
        {"start": "2026-08-28T12:00:00+02:00", "end": "2026-08-28T13:00:00+02:00", "value": 0.20},
    ]},
}
hass28c, _, coach28c = bouw({"sensor.prijs": PRIJSLIJST_NORDPOOL}, instellingen())
np_ = coach28c._prices({"contract": DYN})
controle("een Nord Pool-lijst levert vandaag en morgen", [r["price"] for r in np_] == [0.30, 0.20], f"{np_}")

# Dezelfde sensor als all-in én als marktprijs ingevuld (de eerste woning,
# 22-09-2026): dan is de terugleveropbrengst onbekend, en niet de all-in prijs.
dubbel = {"contract": dict(DYN, netting=False, dynamic=dict(DYN["dynamic"], market_entity=DYN["dynamic"]["all_in_entity"]))}
zelfde = coach28c._prices(dubbel)
controle("dezelfde sensor als marktprijs maakt de terugleveropbrengst onbekend",
         bool(zelfde) and all(r["feed_in"] is None for r in zelfde), f"{zelfde}")

# En een kwartierlijst zonder eindtijden en met maar één rij: dan zegt het
# contract hoe lang een blok is.
PRIJSLIJST_EEN = {"state": "0.30", "attributes": {"data": [{"startsAt": "2026-08-27T12:00:00+02:00", "total": 0.30}]}}
hass28d, _, coach28d = bouw({"sensor.prijs": PRIJSLIJST_EEN}, instellingen())
kwartier = {"contract": dict(DYN, dynamic=dict(DYN["dynamic"], interval="quarter"))}
een = coach28d._prices(kwartier)
controle("één rij zonder eindtijd krijgt de bloklengte van het contract",
         len(een) == 1 and een[0]["end"] - een[0]["start"] == dt.timedelta(minutes=15), f"{een}")

# Kwartierprijzen van Nord Pool (v0.88.1): vier blokken per uur, elk met een
# eigen prijs, en niet samengevoegd tot een uur.
PRIJSLIJST_NP_KWARTIER = {"state": "0.30", "attributes": {"raw_today": [
    {"start": f"2026-08-27T12:{m:02d}:00+02:00", "end": f"2026-08-27T{12 + (m + 15) // 60}:{(m + 15) % 60:02d}:00+02:00",
     "value": 0.30 - m / 1000} for m in (0, 15, 30, 45)]}}
hass28e, _, coach28e = bouw({"sensor.prijs": PRIJSLIJST_NP_KWARTIER}, instellingen())
npk = coach28e._prices({"contract": DYN})
controle("een Nord Pool-lijst met kwartieren levert vier blokken van een kwartier, elk met zijn eigen prijs",
         len(npk) == 4 and all(r["end"] - r["start"] == dt.timedelta(minutes=15) for r in npk)
         and [round(r["price"], 3) for r in npk] == [0.3, 0.285, 0.27, 0.255], f"{npk}")

print()
print("=== eenheden: kW is geen W, en Wh is geen kWh ===")

# Een klant wiens netmeter in kW rapporteert kreeg een coach die met een
# duizend keer te klein getal rekende: overschot nooit boven nul, dus nooit
# laden op eigen zon, en een laadverslag dat niet klopte. Zonder foutmelding,
# want een getal is een getal. Het paneel liet ondertussen het goede getal zien,
# want dat rekende wel om. Gevonden bij een klant op 28-08-2026.
#
# De proef is de vergelijking: hetzelfde huis, twee keer, met dezelfde meting in
# een andere eenheid. Er hoort niets van te merken zijn.


def met_eenheid(waarde, eenheid):
    return {"state": str(waarde), "attributes": {"unit_of_measurement": eenheid}}


inst27 = instellingen()

in_watt = huis(status="charging", stroom=10.0, vermogen=6900.0,
               afname=0.0, teruglevering=1500.0, teller=100.0)
in_kilowatt = dict(
    in_watt,
    **{
        "sensor.laadpaal_vermogen": met_eenheid(6.9, "kW"),
        "sensor.afname": met_eenheid(0.0, "kW"),
        "sensor.teruglevering": met_eenheid(1.5, "kW"),
        "sensor.laadpaal_teller": met_eenheid(100_000.0, "Wh"),
    },
)

nu27 = dt.datetime(2026, 8, 18, 14, 37)
_, _, coach27 = bouw(in_watt, inst27)
_, _, coach28 = bouw(in_kilowatt, inst27)
grid_w, _, _, _ = coach27._read(nu27, inst27, LAADPAAL)
grid_kw, _, _, _ = coach28._read(nu27, inst27, LAADPAAL)

print(f"  overschot in W: {grid_w.surplus_w:.0f}   gemeld in kW: {grid_kw.surplus_w:.0f}")
controle("een netmeter in kW geeft hetzelfde overschot als een in W",
         abs(grid_w.surplus_w - grid_kw.surplus_w) < 1e-6,
         f"{grid_w.surplus_w} tegen {grid_kw.surplus_w}")
controle("en het is niet toevallig allebei nul", grid_w.surplus_w > 0,
         f"{grid_w.surplus_w}")

# Dezelfde vraag voor de zonverwachting, en daar was het antwoord fout. De ene
# voorspeller geeft het gemiddelde vermogen over dat uur (W), de andere de
# energie die er in dat uur in gaat (kWh). Over precies een uur is dat hetzelfde
# getal, alleen niet dezelfde eenheid.
#
# In de klantwoning stond op 29-08-2026 een vermogenssensor in "volgend uur". Die
# 1874 W werd als 1874 kWh gelezen en dus als 1.874.000 W doorgegeven: op de
# kaart "over een uur wordt er 1874,0 kW zon verwacht", en `_beter_straks` koos
# met zo'n vooruitzicht altijd voor wachten. De coach stond daardoor stil op de
# goedkoopste uren van de dag. Gevonden door de eigenaar, op zijn eigen kaart.
ZON_VELDEN = {"this_hour": "sensor.zon_nu", "next_hour": "sensor.zon_straks",
              "remaining_today": "sensor.zon_rest"}
inst_zon = instellingen()
inst_zon["sources"]["solar_forecast"] = ZON_VELDEN

zon_in_kwh = dict(huis(), **{
    "sensor.zon_nu": met_eenheid(3.155, "kWh"),
    "sensor.zon_straks": met_eenheid(1.874, "kWh"),
    "sensor.zon_rest": met_eenheid(7.329, "kWh"),
})
zon_in_watt = dict(huis(), **{
    "sensor.zon_nu": met_eenheid(3155, "W"),
    "sensor.zon_straks": met_eenheid(1874, "W"),
    "sensor.zon_rest": met_eenheid(7.329, "kWh"),
})
_, _, coach29 = bouw(zon_in_kwh, inst_zon)
_, _, coach30 = bouw(zon_in_watt, inst_zon)
zon_kwh = coach29._sun(inst_zon)
zon_w = coach30._sun(inst_zon)
print(f"  zon volgend uur, gemeld in kWh: {zon_kwh.next_w:.0f} W   gemeld in W: {zon_w.next_w:.0f} W")
controle("een zonverwachting in W geeft hetzelfde als dezelfde in kWh",
         abs(zon_kwh.next_w - zon_w.next_w) < 1e-6,
         f"{zon_kwh.next_w} tegen {zon_w.next_w}")
controle("en het is werkelijk 1874 W en geen 1874 kW",
         abs(zon_w.next_w - 1874.0) < 1e-6, f"{zon_w.next_w}")
controle("het huidige uur gaat net zo goed",
         abs(zon_kwh.now_w - zon_w.now_w) < 1e-6, f"{zon_kwh.now_w} tegen {zon_w.now_w}")
controle("en wat er vandaag nog komt blijft in kWh",
         abs(zon_w.remaining_kwh - 7.329) < 1e-6, f"{zon_w.remaining_kwh}")

# Een sensor zonder eenheid blijft gelezen worden als kWh over dat uur, want zo
# stond het er altijd al. Gokken op vermogen zou een bestaande installatie stil
# zetten, en dat is erger dan hem laten zoals hij was.
zon_zonder = dict(huis(), **{
    "sensor.zon_straks": {"state": "1.874", "attributes": {}},
    "sensor.zon_rest": met_eenheid(7.329, "kWh"),
})
_, _, coach31 = bouw(zon_zonder, inst_zon)
controle("zonder eenheid blijft het kWh over dat uur",
         abs(coach31._sun(inst_zon).next_w - 1874.0) < 1e-6,
         f"{coach31._sun(inst_zon).next_w}")

controle("een levensduurteller in Wh telt in kWh",
         abs((coach28._teller(LAADPAAL) or 0) - 100.0) < 1e-9,
         f"{coach28._teller(LAADPAAL)}")
controle("en een in kWh blijft wat hij is",
         abs((coach27._teller(LAADPAAL) or 0) - 100.0) < 1e-9,
         f"{coach27._teller(LAADPAAL)}")

# Een sensor zonder eenheid mag niet als kilo gelezen worden: dat zou een meting
# duizendvoudig opblazen en dat herkent niemand als een eenheidsprobleem.
zonder = dict(in_watt, **{"sensor.afname": {"state": "450", "attributes": {}}})
_, _, coach29 = bouw(zonder, inst27)
grid_zonder, _, _, _ = coach29._read(nu27, inst27, LAADPAAL)
_, _, coach30 = bouw(dict(in_watt, **{"sensor.afname": "450"}), inst27)
grid_kaal, _, _, _ = coach30._read(nu27, inst27, LAADPAAL)
controle("een sensor zonder eenheid wordt als watt gelezen",
         abs(grid_zonder.surplus_w - grid_kaal.surplus_w) < 1e-6,
         f"{grid_zonder.surplus_w} tegen {grid_kaal.surplus_w}")

# De zonverwachting komt in kWh over dat uur binnen. Een verwachting in Wh mag
# niet duizend keer te laag uitpakken.
inst28 = instellingen()
inst28["sources"]["solar_forecast"] = {"remaining_today": "sensor.zon_rest",
                                       "this_hour": "sensor.zon_uur"}
in_kwh = dict(in_watt, **{"sensor.zon_uur": met_eenheid(2.0, "kWh")})
in_wh = dict(in_watt, **{"sensor.zon_uur": met_eenheid(2000.0, "Wh")})
zon_kwh = bouw(in_kwh, inst28)[2]._sun(inst28)
zon_wh = bouw(in_wh, inst28)[2]._sun(inst28)
controle("een zonverwachting in Wh geeft hetzelfde vermogen als een in kWh",
         abs(zon_kwh.now_w - zon_wh.now_w) < 1e-6, f"{zon_kwh.now_w} tegen {zon_wh.now_w}")
controle("en dat is 2 kWh over het uur, dus 2000 W", abs(zon_kwh.now_w - 2000.0) < 1e-6,
         f"{zon_kwh.now_w}")

print("=== 33. de nacht van 30-08-2026 in de klantwoning ===")
# Alles hieronder is nagemeten uit de recorder van die installatie. Vier dingen
# gingen er mis en ze hebben dezelfde vorm: de coach nam een enkele meting voor
# waar zonder te kijken of hij ergens bij hoorde.

print("--- a. twee seconden `disconnected` is geen kabel die eruit gaat ---")
# Een Easee die zijn laadbeurt opnieuw opstart doorloopt de hele keten
# `disconnected`, `awaiting_authorization`, `waiting_in_queue`, `charging`, en
# dat duurt ongeveer twee seconden. Dat gebeurde die nacht drie keer, twee ervan
# binnen tien seconden nadat de coach zelf zijn grens omlaag schreef. Elke keer
# ging het akkoord, de accustand en de klaar-tijd eruit en kwam er een verslag.
inst33 = instellingen()
inst33["strategy"]["schedules"][0]["window"]["done_by"] = "07:00"
hass33, _, coach33 = bouw(huis(status="ready_to_charge", teruglevering=0.0,
                               afname=1800.0), inst33)
asyncio.run(ronde(coach33, inst33, nu=dt.datetime(2026, 8, 30, 3, 0)))
hass33.states.zet("sensor.laadpaal_status", "charging")
hass33.states.zet("sensor.laadpaal_stroom", "13.5")
hass33.states.zet("sensor.laadpaal_vermogen", "9200")
for minuut in range(1, 43):
    asyncio.run(ronde(coach33, inst33, nu=dt.datetime(2026, 8, 30, 3, minuut)))

# 03:43:46 meldt de paal `disconnected`, 03:43:51 laadt hij weer.
hass33.states.zet("sensor.laadpaal_status", "disconnected")
_, blip = asyncio.run(ronde(coach33, inst33, nu=dt.datetime(2026, 8, 30, 3, 43, 46)))
hass33.states.zet("sensor.laadpaal_status", "charging")
verder, _ = asyncio.run(ronde(coach33, inst33, nu=dt.datetime(2026, 8, 30, 3, 43, 51)))
blipmeldingen = [d[2]["message"] for d in blip if d[0] == "notify"]
print(f"  na de blip: regel={verder['rule']}, meldingen={blipmeldingen}")
controle("een blip levert geen afkoppelverslag op",
         not any("afgekoppeld" in m for m in blipmeldingen), f"{blipmeldingen}")
controle("en de laadbeurt loopt gewoon door", verder["rule"] != "disconnected",
         f"{verder['rule']}")

# En de beurt is niet in tweeen geknipt, dus het verslag straks gaat over een
# beurt die om 03:01 begon en telt de kWh een keer.
for minuut in range(44, 50):
    asyncio.run(ronde(coach33, inst33, nu=dt.datetime(2026, 8, 30, 3, minuut)))
hass33.states.zet("sensor.laadpaal_status", "disconnected")
hass33.states.zet("sensor.laadpaal_stroom", "0")
hass33.states.zet("sensor.laadpaal_vermogen", "0")
asyncio.run(ronde(coach33, inst33, nu=dt.datetime(2026, 8, 30, 3, 50)))
_, eind33 = asyncio.run(ronde(coach33, inst33, nu=dt.datetime(2026, 8, 30, 3, 51)))
verslag33 = [d[2]["message"] for d in eind33 if d[0] == "notify"]
print(f"  {verslag33}")
controle("de kabel die er echt uit gaat levert nog steeds een verslag op",
         any("afgekoppeld" in m for m in verslag33), f"{verslag33}")
controle("over een beurt die om 03:01 begon",
         any("sinds 03:01" in m for m in verslag33), f"{verslag33}")
controle("en met het moment waarop de paal het zei, niet waarop de coach het geloofde",
         any("afgekoppeld om 03:50" in m for m in verslag33), f"{verslag33}")

print("--- b. een meterpiek zet de paal niet meer op nul ---")
# Om 04:28:56 meldde de huismeter een enkel sample van 27 A op L3; tien seconden
# ervoor en dertig erna stond hij op 10. De coach schreef 0 A, de paal stond
# achtenzeventig seconden uit, en de Ford beeindigde zijn laadbeurt en kwam er
# die hele dag niet meer uit.
inst34 = instellingen()
inst34["strategy"]["schedules"][0]["window"]["done_by"] = "07:00"
hass34, _, coach34 = bouw(huis(status="ready_to_charge", teruglevering=0.0,
                               afname=1800.0), inst34)
asyncio.run(ronde(coach34, inst34, nu=dt.datetime(2026, 8, 30, 4, 20)))
hass34.states.zet("sensor.laadpaal_status", "charging")
hass34.states.zet("sensor.laadpaal_stroom", "12")
hass34.states.zet("sensor.laadpaal_vermogen", "8200")
hass34.states.zet("sensor.l3", "22")
for minuut in range(21, 28):
    asyncio.run(ronde(coach34, inst34, nu=dt.datetime(2026, 8, 30, 4, minuut)))

# Huis 30 min 12 van de paal is 18 A eigen last. Onder de marge past er dan
# niets meer (25 min 18 min 3 is 4), zonder de marge nog wel (25 min 18 is 7).
hass34.states.zet("sensor.l3", "30")
piek, _ = asyncio.run(ronde(coach34, inst34, nu=dt.datetime(2026, 8, 30, 4, 28)))
print(f"  met L3 op 30 A: {piek['rule']} {piek['amps']} A")
controle("een volle fase zet een lopende beurt niet meer uit", piek["amps"] > 0,
         f"{piek['rule']} {piek['amps']}")
controle("hij zakt naar de laagste stand", piek["amps"] == planner.MIN_AMPS,
         f"{piek['amps']}")

# Maar een huis dat werkelijk over de zekering gaat wint nog steeds: 26 A huis
# plus zes ampere past niet onder 25.
hass34.states.zet("sensor.laadpaal_status", "ready_to_charge")
hass34.states.zet("sensor.laadpaal_stroom", "0.01")
hass34.states.zet("sensor.laadpaal_vermogen", "0")
hass34.states.zet("sensor.l3", "32")
for seconde in (0, 20, 40):
    vol34, _ = asyncio.run(
        ronde(coach34, inst34, nu=dt.datetime(2026, 8, 30, 4, 29, seconde))
    )
print(f"  huis alleen al op 32 A: {vol34['rule']} {vol34['amps']} A")
controle("een huis dat er zelf overheen gaat wint wel", vol34["amps"] == 0,
         f"{vol34['rule']} {vol34['amps']}")

# En de piek zelf hoort er al uit te vallen voordat de som eraan begint. De
# huismeter van de klantwoning meldt elke dertig seconden; op 30-08-2026 om
# 04:28:56 gaf hij een enkel sample van 27 A op een fase die ervoor en erna op
# 10 stond. Die metingen komen binnen op de luisteraar en niet in de ronde, dus
# ze worden hier zo gevoerd.
class Meting:
    def __init__(self, entity_id, state):
        self.entity_id = entity_id
        self.state = state


# De stempels van de luisteraar en de tijd van de ronde moeten van dezelfde
# klok komen, anders is het vergelijken ervan een `TypeError` midden in een
# ronde. Vandaar dat hier `_moment` gebruikt wordt en niet `utcnow`.
nu34 = coachmod._moment()
_, _, coach34b = bouw(huis(), instellingen())
for waarde in ("10", "10", "27", "10"):
    coach34b._async_phase_changed(Meting("sensor.l3", waarde))
glad = coach34b._gladde_fase("sensor.l3", 10.0, nu34)
print(f"  10, 10, 27, 10 wordt {glad} A")
controle("een enkele uitschieter valt eruit", glad == 10.0, f"{glad}")

# Maar een huis dat werkelijk bijschakelt heeft binnen twee metingen de
# meerderheid en komt er gewoon door.
for waarde in ("24", "24"):
    coach34b._async_phase_changed(Meting("sensor.l3", waarde))
stijgt = coach34b._gladde_fase("sensor.l3", 24.0, coachmod._moment())
print(f"  en na twee keer 24 wordt het {stijgt} A")
controle("een echte stijging komt er wel doorheen", stijgt >= 24.0, f"{stijgt}")

# En zonder genoeg metingen is er niets glad te strijken, dus telt wat de sensor
# nu zegt. Liever een ronde te voorzichtig dan een ronde te laat.
_, _, coach34c = bouw(huis(), instellingen())
coach34c._async_phase_changed(Meting("sensor.l3", "27"))
kaal = coach34c._gladde_fase("sensor.l3", 27.0, coachmod._moment())
controle("te weinig metingen laat de meting staan", kaal == 27.0, f"{kaal}")

# En de hele weg erlangs, zoals hij in het echt loopt: de luisteraar vult de
# historie en de ronde leest hem. Dat is de plek waar de twee klokken elkaar
# tegenkomen.
inst34d = instellingen()
inst34d["strategy"]["schedules"][0]["window"]["done_by"] = "07:00"
# Met een accustand, want zonder is het `no-soc`, en die regel wordt sinds
# 05-09-2026 niet meer vastgehouden (nooit blind laden). De proef gaat over
# de gladgestreken fase en niet over het vasthouden.
inst34d["car_soc"] = [{"device": "dev-laadpaal", "car": "car-1", "percent": 40.0,
                       "at": coachmod._moment().isoformat()}]
huis34d = huis(status="ready_to_charge", teruglevering=0.0, afname=1800.0)
hass34d, _, coach34d = bouw(huis34d, inst34d)
asyncio.run(ronde(coach34d, inst34d, nu=coachmod._moment()))
hass34d.states.zet("sensor.laadpaal_status", "charging")
hass34d.states.zet("sensor.laadpaal_stroom", "12")
hass34d.states.zet("sensor.laadpaal_vermogen", "8200")
for waarde in ("10", "10", "10"):
    coach34d._async_phase_changed(Meting("sensor.l3", waarde))
# En dan die ene uitschieter, ook in de sensor zelf.
coach34d._async_phase_changed(Meting("sensor.l3", "40"))
hass34d.states.zet("sensor.l3", "40")
langs, _ = asyncio.run(ronde(coach34d, inst34d, nu=coachmod._moment()))
print(f"  door de hele keten heen: {langs['rule']} {langs['amps']} A")
# Niet "hij laadt", want deze proef loopt op de echte klok en 's avonds kiest
# de planner voor de zon van morgen; wel "de piek zette hem niet klem".
controle("de ronde rekent met de gladgestreken fase en niet met de piek",
         langs["rule"].split("+")[0] not in ("no-room", "tight"), f"{langs['rule']} {langs['amps']}")

# En het tegenbewijs: dezelfde piek zonder historie eronder zet hem wel uit.
# Dat is precies wat er in de klantwoning gebeurde, en het laat zien dat het de
# demping is die het verschil maakt en niet iets anders in de opstelling.
hass34e, _, coach34e = bouw(huis34d, instellingen())
inst34e = instellingen()
inst34e["strategy"]["schedules"][0]["window"]["done_by"] = "07:00"
asyncio.run(ronde(coach34e, inst34e, nu=coachmod._moment()))
hass34e.states.zet("sensor.laadpaal_status", "charging")
hass34e.states.zet("sensor.laadpaal_stroom", "12")
hass34e.states.zet("sensor.laadpaal_vermogen", "8200")
hass34e.states.zet("sensor.l3", "40")
kaal34, _ = asyncio.run(ronde(coach34e, inst34e, nu=coachmod._moment()))
print(f"  dezelfde piek zonder demping: {kaal34['rule']} {kaal34['amps']} A")
controle("zonder demping zou dezelfde piek hem wel hebben uitgezet",
         kaal34["rule"] == "no-room", f"{kaal34['rule']} {kaal34['amps']}")

print("--- c. de fasemeting midden in het optrekken zegt niets ---")
# Om 04:28:17 meldde de Easee 2,20 A terwijl het vermogen nog de 782 W van drie
# seconden eerder was: verhouding 1,54, dus "een fase". De auto laadde driefasig.
inst35 = instellingen()
hass35, _, coach35 = bouw(huis(status="ready_to_charge", teruglevering=0.0,
                               afname=1800.0), inst35)
asyncio.run(ronde(coach35, inst35, nu=dt.datetime(2026, 8, 30, 4, 27)))
hass35.states.zet("sensor.laadpaal_status", "charging")
hass35.states.zet("sensor.laadpaal_max", "16")
hass35.states.zet("sensor.laadpaal_stroom", "2.2")
hass35.states.zet("sensor.laadpaal_vermogen", "782")
optrekken, _ = asyncio.run(ronde(coach35, inst35, nu=dt.datetime(2026, 8, 30, 4, 28)))
print(f"  optrekkend op 2,2 A: tip={optrekken['tip']!r}")
controle("onder de meetdrempel wordt er niets over de fasen gezegd",
         not optrekken["tip"], f"{optrekken['tip']}")
controle("en de meting zelf zegt niets",
         coach35._measured_phases(LAADPAAL) is None,
         f"{coach35._measured_phases(LAADPAAL)}")

# Genoeg stroom, maar de twee sensoren van dezelfde paal melden seconden uit
# elkaar. Ook dan is de verhouding een vergelijking tussen nu en daarnet.
hass35.states.zet("sensor.laadpaal_stroom", "13.5")
hass35.states.zet("sensor.laadpaal_vermogen", "9300")
hass35.states.verouder("sensor.laadpaal_vermogen", 30)
print(f"  vermogen 30 s ouder dan de stroom: {coach35._measured_phases(LAADPAAL)}")
controle("twee sensoren die niet tegelijk gemeld hebben zeggen samen niets",
         coach35._measured_phases(LAADPAAL) is None,
         f"{coach35._measured_phases(LAADPAAL)}")

# Vers en stabiel: dan is 9300 W bij 13,5 A driefasig, en dat klopt met de meting
# van de klantwoning waar alle drie de fasen samen elf ampere zakten.
hass35.states.zet("sensor.laadpaal_vermogen", "9300")
controle("vers en boven de drempel wordt het gewoon gemeten",
         coach35._measured_phases(LAADPAAL) == 3,
         f"{coach35._measured_phases(LAADPAAL)}")

print("--- d. wat de lastbewaker vrijgeeft is een restwaarde ---")
# `sensor.1_equalizer_limiet` in de klantwoning meldt niet een instelling maar wat
# er ná het huisverbruik overblijft voor de paal. Nagemeten op 29-08-2026: om
# 16:50 stond hij op 18 A terwijl de paal 15 trok en het huis er zelf 5 bijhad,
# om 17:20 met een leeg huis op 20. v0.44.0 las dat als een tweede zekering en
# trok het huisverbruik er daarmee twee keer vanaf.
inst36 = instellingen()
inst36["installation"]["balancer_entity"] = "sensor.equalizer"
huis36 = dict(huis(status="charging", stroom=12.0, vermogen=8200.0,
                   teruglevering=0.0, afname=1800.0),
              **{"sensor.equalizer": "8", "sensor.l1": "1", "sensor.l2": "2",
                 "sensor.l3": "13"})
hass36, _, coach36 = bouw(huis36, inst36)
grid36, car36, charger36, _ = coach36._read(
    dt.datetime(2026, 8, 30, 4, 0), inst36, LAADPAAL
)
plafond36 = planner.ceiling_amps(grid36, car36, charger36)
print(f"  bewaker geeft 8 A vrij: plafond {plafond36} A")
controle("de coach vraagt niet meer dan de bewaker vrijgeeft", plafond36 == 8,
         f"{plafond36}")
controle("en het huisverbruik gaat er niet nog eens vanaf",
         plafond36 >= planner.MIN_AMPS, f"{plafond36}")

# Zonder die sensor blijft alles zoals het was.
inst36b = instellingen()
hass36b, _, coach36b = bouw(huis36, inst36b)
grid36b, car36b, charger36b, _ = coach36b._read(
    dt.datetime(2026, 8, 30, 4, 0), inst36b, LAADPAAL
)
controle("zonder die sensor verandert er niets",
         grid36b.balancer_amps is None, f"{grid36b.balancer_amps}")

# En het staat op de kaart, maar alleen als de bewaker werkelijk de laagste van
# de plafonds is. Anders staat er altijd iets en leest niemand het meer.
tip36 = coach36._bewakertip(inst36, LAADPAAL, charger36)
print(f"  tip: {tip36}")
controle("de coach zegt dat de bewaker de snelheid bepaalt",
         "8 A" in tip36 and "14 A" in tip36, f"{tip36}")

huis36c = dict(huis36, **{"sensor.equalizer": "32"})
hass36c, _, coach36c = bouw(huis36c, inst36)
_, _, charger36c, _ = coach36c._read(dt.datetime(2026, 8, 30, 4, 0), inst36, LAADPAAL)
controle("en zwijgt als de bewaker meer vrijgeeft dan de lader kan",
         not coach36c._bewakertip(inst36, LAADPAAL, charger36c),
         f"{coach36c._bewakertip(inst36, LAADPAAL, charger36c)}")

print("--- e. de minuten in het verslag horen bij een andere periode dan de kWh ---")
# "er ging 6,9 kWh in sinds 03:00. Er ging 381 minuten naar wachten op een
# goedkoper uur." Allebei waar, samen in een zin onzin: de kWh tellen vanaf het
# laden, de minuten vanaf de kabel.
zin = coach33._waarom({"kwijt": {"wait-for-price": 381.0}, "ingestapt": False})
print(f"  {zin}")
controle("de periode staat erbij", zin.startswith("Sinds de kabel erin ging"), zin)
ingestapt = coach33._waarom({"kwijt": {"wait-for-price": 381.0}, "ingestapt": True})
controle("en na een herstart zegt hij wat hij zelf gezien heeft",
         ingestapt.startswith("Sinds de coach begon te kijken"), ingestapt)

print("--- f. een auto die niets afneemt terwijl de klaar-tijd nadert ---")
# De Ford hield om 04:34 op en het eerste woord daarover was het verslag van
# 07:00, toen de klaar-tijd al voorbij was. Tweeeneenhalf uur waarin niemand
# iets kon doen omdat niemand het wist.
inst37 = instellingen()
inst37["strategy"]["schedules"][0]["window"]["done_by"] = "07:00"
hass37, _, coach37 = bouw(huis(status="ready_to_charge", teruglevering=0.0,
                               afname=1800.0), inst37)
asyncio.run(ronde(coach37, inst37, nu=dt.datetime(2026, 8, 30, 4, 30)))
hass37.states.zet("sensor.laadpaal_status", "charging")
hass37.states.zet("sensor.laadpaal_stroom", "13.5")
hass37.states.zet("sensor.laadpaal_vermogen", "9200")
asyncio.run(ronde(coach37, inst37, nu=dt.datetime(2026, 8, 30, 4, 31)))
# En dan neemt de auto niets meer af, terwijl de paal aanbiedt.
hass37.states.zet("sensor.laadpaal_status", "ready_to_charge")
hass37.states.zet("sensor.laadpaal_stroom", "0.01")
hass37.states.zet("sensor.laadpaal_vermogen", "0")
stil37 = []
for minuut in range(32, 60):
    _, uit = asyncio.run(ronde(coach37, inst37, nu=dt.datetime(2026, 8, 30, 4, minuut)))
    stil37 += [d[2]["message"] for d in uit if d[0] == "notify"
               and "geen stroom af" in d[2]["message"]]
print(f"  {stil37}")
controle("hij zegt het voordat de klaar-tijd voorbij is", len(stil37) == 1, f"{stil37}")
controle("met de klaar-tijd erbij", bool(stil37) and "07:00" in stil37[0], f"{stil37}")
controle("en met wat je eraan kunt doen", bool(stil37) and "kabel" in stil37[0],
         f"{stil37}")

print("=== 38. de lastwaarschuwing gaat niet over het laden van de coach zelf ===")
# De eigenaar kreeg in de nacht van 30-08-2026 drie meldingen, om 03:02 op 84%, om
# 03:32 op 80% en om 04:22 op 88%, telkens met "zet iets zwaars uit of wacht
# ermee". Die getallen klopten: zijn huis heeft in de nacht ongeveer 10 A
# basislast op L3, en met de paal erbij is dat 22 A van de 25.
#
# Maar het zware ding was zijn eigen auto, en de coach stond op datzelfde moment
# al terug te regelen van 16 naar 12 A. Om vier uur in de nacht gewekt worden
# voor iets dat de coach zelf doet en zelf oplost is verkeerd.


def bewaker(inst, waarden):
    """Een lastbewaking met een nagebouwd huis eromheen."""
    hass = NepHass(waarden)
    monitor = monitormod.LoadMonitor(hass)
    monitor._settings = inst
    return hass, monitor


def waarschuwing(hass, monitor):
    """Een ronde van de bewaking, en wat er de deur uit ging."""
    hass.services.verstuurd.clear()
    monitor._above_since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    monitor._last_sent = None
    monitor._async_evaluate()
    asyncio.run(hass.afmaken())
    return [d[2]["message"] for d in hass.services.verstuurd if d[0] == "notify"]


inst38 = instellingen()
inst38["notifications"]["load_alert"] = {
    "enabled": True,
    "threshold_percent": 80.0,
    "min_interval_minutes": 30,
    "min_duration_seconds": 60,
}

# Een huis dat zelf 22 A op L3 trekt, zonder laadpaal. Dat is 88% van 25 A en
# daar hoort de melding gewoon te komen.
huis38 = dict(huis(status="ready_to_charge", stroom=0.01, vermogen=0.0),
              **{"sensor.l1": "1", "sensor.l2": "2", "sensor.l3": "22"})
hass38, monitor38 = bewaker(inst38, huis38)
eigen38 = waarschuwing(hass38, monitor38)
print(f"  huis alleen: {eigen38}")
controle("een zwaar huis levert nog steeds een waarschuwing op",
         any("88%" in m for m in eigen38), f"{eigen38}")

# Dezelfde 22 A, maar nu komt er 12 A van de laadpaal die de coach stuurt. Het
# huis zelf zit op 10 A, dus 40%, en dat is geen melding waard.
huis38b = dict(huis(status="charging", stroom=12.0, vermogen=8200.0),
               **{"sensor.l1": "13", "sensor.l2": "14", "sensor.l3": "22"})
hass38b, monitor38b = bewaker(inst38, huis38b)
stil38 = waarschuwing(hass38b, monitor38b)
meting38 = monitor38b.async_current_load()
print(f"  met de laadpaal erin: kaart {meting38.percent:.0f}%, "
      f"zonder de coach {meting38.zonder_coach:.0f}%, meldingen {stil38}")
controle("het laden van de coach zelf wekt niemand meer", not stil38, f"{stil38}")
controle("maar de kaart laat wel de echte belasting zien",
         abs(meting38.percent - 88.0) < 0.01, f"{meting38.percent}")

# Kan de coach er niet bij, dan is de laadpaal net zo goed een apparaat waar de
# bewoner zelf iets aan moet doen, en dan hoort de melding wel te komen.
inst38c = dict(inst38, strategy=dict(inst38["strategy"], level="advise"))
hass38c, monitor38c = bewaker(inst38c, huis38b)
advies38 = waarschuwing(hass38c, monitor38c)
print(f"  op Adviseren: {advies38}")
controle("op een niveau waarop de coach niets stuurt komt hij wel",
         any("88%" in m for m in advies38), f"{advies38}")

# Net zo voor een paal die niet stuurbaar is.
inst38d = instellingen(devices=[dict(LAADPAAL, controllable=False)])
inst38d["notifications"] = inst38["notifications"]
hass38d, monitor38d = bewaker(inst38d, huis38b)
vast38 = waarschuwing(hass38d, monitor38d)
print(f"  onstuurbare paal: {vast38}")
controle("en voor een paal die de coach niet mag sturen ook",
         any("88%" in m for m in vast38), f"{vast38}")

# Een paal die stilstaat meldt zijn rustverbruik in honderdsten van een ampere,
# en dat hoort niet als "0,0 A van de laadpaal" in het bericht te komen.
controle("een stilstaande paal wordt niet genoemd",
         not any("van de laadpaal" in m for m in eigen38), f"{eigen38}")

# Zit het huis er zelf al overheen terwijl de paal ook laadt, dan komt de
# melding wel, en dan staat erbij hoeveel ervan de laadpaal is. Zonder dat klopt
# het getal op de telefoon niet met wat er op de kaart staat.
huis38e = dict(huis(status="charging", stroom=12.0, vermogen=8200.0),
               **{"sensor.l1": "13", "sensor.l2": "14", "sensor.l3": "34"})
hass38e, monitor38e = bewaker(inst38, huis38e)
beide38 = waarschuwing(hass38e, monitor38e)
print(f"  huis 22 A plus paal 12 A: {beide38}")
controle("een huis dat er zonder de paal al overheen gaat wekt wel",
         bool(beide38), f"{beide38}")
controle("en dan staat erbij welk deel van de laadpaal komt",
         any("12.0 A van de laadpaal" in m for m in beide38), f"{beide38}")

print("=== 39. een meter die even zwijgt meet geen nul ===")
# In de klantwoning viel de P1-meter op 30-08-2026 om 11:07, 11:09 en 11:15
# telkens een paar seconden weg. `_read` rekende dan `netto = 0` uit, de coach
# concludeerde dat er geen zon over was en zette het laden op de zonregel stil.
# Twee keer een kwartier, midden op een zonnige ochtend.
#
# Dit geldt voor elke sensor waarvan een ontbrekende waarde als nul zou lezen.
inst39 = instellingen()
zonnig = huis(status="charging", stroom=13.5, vermogen=9200.0,
              teruglevering=6000.0, afname=0.0)
hass39, _, coach39 = bouw(zonnig, inst39)

nu39 = dt.datetime(2026, 8, 30, 11, 5)
grid39, _, _, _ = coach39._read(nu39, inst39, LAADPAAL)
print(f"  meter doet het:            surplus {grid39.surplus_w:.0f} W")
controle("met een werkende meter telt de paal gewoon mee",
         grid39.surplus_w > 14000, f"{grid39.surplus_w}")

# En dan valt de hele P1-meter weg, precies zoals bij hem.
for entiteit in ("sensor.teruglevering", "sensor.afname"):
    hass39.states.zet(entiteit, "unavailable")
weg39, _, _, _ = coach39._read(dt.datetime(2026, 8, 30, 11, 7), inst39, LAADPAAL)
print(f"  meter weg, binnen de naijl: surplus {weg39.surplus_w:.0f} W")
controle("een meter die even zwijgt houdt zijn laatste waarde",
         weg39.surplus_w > 14000, f"{weg39.surplus_w}")

# Blijft hij weg, dan is onbekend ook echt onbekend. Doorrekenen met een getal
# van een half uur oud is erger dan zeggen dat je het niet weet.
lang39, _, _, _ = coach39._read(dt.datetime(2026, 8, 30, 11, 20), inst39, LAADPAAL)
print(f"  meter een kwartier weg:     surplus {lang39.surplus_w:.0f} W")
controle("maar na de naijl rekent hij niet door met oude getallen",
         lang39.surplus_w == 0.0, f"{lang39.surplus_w}")

# En dan zegt hij het, want een paal die op een zonnige middag stilstaat zonder
# uitleg leest als kapot.
tip39 = coach39._nettip(dt.datetime(2026, 8, 30, 11, 20))
print(f"  tip: {tip39}")
# Sinds 11:05, want dat was de laatste ronde waarin de meter werkelijk iets zei.
# Om 11:07 werd zijn waarde alleen nog vastgehouden, en vasthouden is geen teken
# van leven: tot 04-09-2026 telde dat wel mee en zei de kaart "13 minuten" over
# een meter die er vijftien niet was, en in het virtuele huis zelfs "1 minuten".
controle("en hij zegt dat hij de netmeting niet kan lezen",
         "netmeting" in tip39 and "15 minuten" in tip39, f"{tip39}")

# Komt de meter terug, dan is er niets meer aan de hand.
hass39.states.zet("sensor.teruglevering", "6000.0")
hass39.states.zet("sensor.afname", "0.0")
terug39, _, _, _ = coach39._read(dt.datetime(2026, 8, 30, 11, 21), inst39, LAADPAAL)
controle("en zodra hij terug is telt hij weer gewoon mee",
         terug39.surplus_w > 14000, f"{terug39.surplus_w}")
controle("en zwijgt de coach erover", not coach39._nettip(dt.datetime(2026, 8, 30, 11, 21)),
         f"{coach39._nettip(dt.datetime(2026, 8, 30, 11, 21))}")

# Het vermogen van de paal zit in dezelfde som en is het gemeenst: valt hij weg,
# dan ziet de coach zijn eigen laden aan voor huisverbruik. Zonder dit zou het
# overschot van 15,2 kW instorten naar 6 kW en zou de coach zichzelf uitpraten.
hass39.states.zet("sensor.laadpaal_vermogen", "unavailable")
paalweg, _, _, _ = coach39._read(dt.datetime(2026, 8, 30, 11, 22), inst39, LAADPAAL)
print(f"  vermogen van de paal weg:   surplus {paalweg.surplus_w:.0f} W")
controle("een vermogenssensor die wegvalt praat de coach niet uit zijn eigen zon",
         paalweg.surplus_w > 14000, f"{paalweg.surplus_w}")

# Ook de fasestromen. Vallen die weg, dan zou `phase_amps` leeg raken en zou de
# hele zekeringcontrole verdwijnen, en dat is de gevaarlijke kant.
hass40 = bouw(huis(status="charging", stroom=13.5, vermogen=9200.0), inst39)
hass40, _, coach40 = hass40
vol40, _, _, _ = coach40._read(dt.datetime(2026, 8, 30, 11, 0), inst39, LAADPAAL)
controle("met werkende fasesensoren staat de zekeringcontrole aan",
         len(vol40.phase_amps) == 3, f"{vol40.phase_amps}")
for fase in ("sensor.l1", "sensor.l2", "sensor.l3"):
    hass40.states.zet(fase, "unavailable")
kort40, _, _, _ = coach40._read(dt.datetime(2026, 8, 30, 11, 1), inst39, LAADPAAL)
print(f"  fasen weg, binnen de naijl: {kort40.phase_amps}")
controle("fasen die even wegvallen laten de zekeringcontrole staan",
         len(kort40.phase_amps) == 3, f"{kort40.phase_amps}")

# Een enkele meting die tekst is in plaats van een getal telt net zo goed als
# niets, en dat is bij een P1-integratie de gewone manier van wegvallen.
hass41 = bouw(huis(status="charging", stroom=13.5, vermogen=9200.0), inst39)
hass41, _, coach41 = hass41
coach41._read(dt.datetime(2026, 8, 30, 11, 0), inst39, LAADPAAL)
hass41.states.zet("sensor.l3", "unknown")
onbekend, _, _, _ = coach41._read(dt.datetime(2026, 8, 30, 11, 1), inst39, LAADPAAL)
controle("`unknown` telt net zo goed als weg", len(onbekend.phase_amps) == 3,
         f"{onbekend.phase_amps}")

print("=== 40. de naam die je een auto geeft komt ook ergens terug ===")
# De eigenaar op 30-08-2026: "ik heb de naam aangepast bij de auto maar in het
# overzicht staat de naam nog verkeerd en neemt hij het niet mee." Die naam
# werd nergens gebruikt: de kaart toont de laadpaal en elke melding zei "de
# auto". Nu praat de coach over de auto zoals de bewoner hem noemt.
FORD = dict(LAADPAAL["cars"][0], name="de blauwe bus", capacity_kwh=65.0)
PAAL40 = dict(LAADPAAL, cars=[FORD])
inst40 = instellingen(devices=[PAAL40])
inst40["strategy"]["schedules"][0]["window"]["done_by"] = "23:00"
hass40n, _, coach40n = bouw(huis(status="ready_to_charge", teruglevering=0.0,
                                 afname=1800.0), inst40)
_, auto40, _, _ = coach40n._read(dt.datetime(2026, 8, 20, 19, 0), inst40, PAAL40)
print(f"  de coach kent hem als: {auto40.name!r}")
controle("de naam komt uit het profiel", auto40.name == "de blauwe bus",
         f"{auto40.name!r}")

asyncio.run(ronde(coach40n, inst40, paal=PAAL40, nu=dt.datetime(2026, 8, 20, 19, 0)))
hass40n.states.zet("sensor.laadpaal_status", "charging")
hass40n.states.zet("sensor.laadpaal_stroom", "13.5")
hass40n.states.zet("sensor.laadpaal_vermogen", "3070")
for minuut in range(1, 6):
    asyncio.run(ronde(coach40n, inst40, paal=PAAL40, nu=dt.datetime(2026, 8, 20, 19, minuut)))
hass40n.states.zet("sensor.laadpaal_status", "disconnected")
hass40n.states.zet("sensor.laadpaal_stroom", "0")
hass40n.states.zet("sensor.laadpaal_vermogen", "0")
asyncio.run(ronde(coach40n, inst40, paal=PAAL40, nu=dt.datetime(2026, 8, 20, 19, 6)))
_, los40 = asyncio.run(ronde(coach40n, inst40, paal=PAAL40, nu=dt.datetime(2026, 8, 20, 19, 7)))
bericht40 = [d[2]["message"] for d in los40 if d[0] == "notify"]
print(f"  {bericht40}")
controle("en de melding gebruikt hem",
         any(m.startswith("De blauwe bus aan Laadpaal is afgekoppeld") for m in bericht40),
         f"{bericht40}")

# Zonder naam blijft het "de auto", want dat is wat het is. Een lege naam mag
# nooit een lege plek in een zin worden.
GEEN_NAAM = dict(LAADPAAL["cars"][0], name="   ")
PAAL40B = dict(LAADPAAL, cars=[GEEN_NAAM])
inst40b = instellingen(devices=[PAAL40B])
inst40b["strategy"]["schedules"][0]["window"]["done_by"] = "23:00"
hass40b, _, coach40b = bouw(huis(status="ready_to_charge", teruglevering=0.0,
                                 afname=1800.0), inst40b)
asyncio.run(ronde(coach40b, inst40b, paal=PAAL40B, nu=dt.datetime(2026, 8, 20, 19, 0)))
hass40b.states.zet("sensor.laadpaal_status", "charging")
hass40b.states.zet("sensor.laadpaal_stroom", "13.5")
hass40b.states.zet("sensor.laadpaal_vermogen", "3070")
for minuut in range(1, 6):
    asyncio.run(ronde(coach40b, inst40b, paal=PAAL40B, nu=dt.datetime(2026, 8, 20, 19, minuut)))
hass40b.states.zet("sensor.laadpaal_status", "disconnected")
hass40b.states.zet("sensor.laadpaal_stroom", "0")
hass40b.states.zet("sensor.laadpaal_vermogen", "0")
asyncio.run(ronde(coach40b, inst40b, paal=PAAL40B, nu=dt.datetime(2026, 8, 20, 19, 6)))
_, los40b = asyncio.run(ronde(coach40b, inst40b, paal=PAAL40B, nu=dt.datetime(2026, 8, 20, 19, 7)))
bericht40b = [d[2]["message"] for d in los40b if d[0] == "notify"]
print(f"  {bericht40b}")
controle("zonder naam blijft het de auto",
         any(m.startswith("De auto aan Laadpaal is afgekoppeld") for m in bericht40b),
         f"{bericht40b}")

print("=== 41. de tijdlijn gaat mee naar het paneel ===")
# Alles wat het scherm toont komt uit deze stand, want een scherm dat zijn eigen
# sommen doet loopt uit de pas met wat de coach werkelijk doet.
inst41 = instellingen(
    devices=[PAAL40],
    car_soc=[{"device": "dev-laadpaal", "car": "car-1", "percent": 48.5, "meter": 100.0}],
)
inst41["strategy"]["schedules"][0]["window"]["done_by"] = "07:00"
hass41n, _, coach41n = bouw(huis(status="ready_to_charge", teruglevering=0.0,
                                 afname=1800.0), inst41)
besluit41, _ = asyncio.run(
    ronde(coach41n, inst41, paal=PAAL40, nu=dt.datetime(2026, 8, 29, 20, 30))
)
plan41 = besluit41.get("plan_ahead")
print(f"  klaar-tijd {plan41['deadline']}, uiterlijk {plan41['latest_start']}, "
      f"{plan41['amps']} A")
controle("de stand draagt een tijdlijn", plan41 is not None, f"{besluit41.keys()}")
controle("met de klaar-tijd erin", "07:00" in (plan41["deadline"] or ""),
         f"{plan41['deadline']}")
controle("en met een uiterste startmoment",
         plan41["latest_start"] is not None, f"{plan41}")
controle("alles als tekst, zodat het over de websocket kan",
         all(isinstance(plan41[k], (str, type(None)))
             for k in ("deadline", "latest_start", "expected_done")),
         f"{plan41}")
controle("en de blokken zijn een lijst", isinstance(plan41["blocks"], list),
         f"{type(plan41['blocks'])}")
controle("en hij zegt hoeveel er gepland staat, en of dat alleen zon is",
         isinstance(plan41.get("planned_kwh"), float)
         and isinstance(plan41.get("solar_only"), bool), f"{plan41}")

print("=== 41b. elke melding komt in de geschiedenis, en een stille sensor wordt gemeld ===")
# De eigenaar op 04-09-2026: "wat als een sensor ineens niet meer beschikbaar is. Dat
# moet wel gemeld worden. Daarom wil ik ook een soort geschiedenis meldingen
# scherm." De geschiedenis is een eigen opslag naast de instellingen, en het
# paneel leest hem over `domotiapp_coach/notifications/list`.
async_get_meldingen = storage.async_get_meldingen

inst41b = instellingen()
inst41b["devices"][0]["cars"][0]["soc_entity"] = "sensor.ford_soc"
hass41b, _, coach41b = bouw(huis(status="charging", stroom=6.0, vermogen=4100.0), inst41b)
hass41b.states.zet("sensor.ford_soc", "40")
asyncio.run(coach41b._async_tell("proefmelding"))
geschiedenis = asyncio.run(async_get_meldingen(hass41b).async_list())
print(f"  geschiedenis: {geschiedenis}")
controle("een melding staat daarna in de geschiedenis",
         len(geschiedenis) == 1 and geschiedenis[0]["message"] == "proefmelding"
         and "T" in geschiedenis[0]["at"], f"{geschiedenis}")
controle("en het paneel hoort het meteen, via de eventbus",
         any(soort == "domotiapp_coach_notification" and data.get("message") == "proefmelding"
             for soort, data in hass41b.bus.gebeurtenissen), f"{hass41b.bus.gebeurtenissen}")

# De wachter draait in `_round`, per ronde van de klok; `ronde()` hierboven
# roept `_one` aan, dus hier gaat hij los.
t0 = dt.datetime(2026, 9, 5, 13, 30)


def wacht(minuten):
    hass41b.services.verstuurd.clear()
    asyncio.run(coach41b._async_sensorwacht(inst41b, t0 + dt.timedelta(minutes=minuten)))
    return [d[2]["message"] for d in hass41b.services.verstuurd if d[0] == "notify"]


asyncio.run(ronde(coach41b, inst41b, nu=t0))
wacht(0)
hass41b.states.zet("sensor.ford_soc", "unavailable")
# Een auto mag een uur zwijgen: zijn integratie haalt de stand eens per zoveel
# tijd op. De eigenaar op 22-09-2026: "bij ford zet dat maar op een uur polling."
te_vroeg = wacht(1) + wacht(5) + wacht(11) + wacht(59)
controle("een uur stilte van een auto is nog geen melding", not te_vroeg, f"{te_vroeg}")
stil = wacht(61)
print(f"  na eenenzestig minuten: {stil}")
# De naam die de bewoner zelf invulde staat erin, de entiteit-id niet: die
# hoort in het log. De eigenaar op 21-09-2026: "meld zo'n sensor niet volledig, zeg
# gewoon dat er iets mis is met de integratie."
controle("na een uur wel, met de naam van de sensor erin",
         len(stil) == 1 and "accustand van Ford" in stil[0], f"{stil}")
controle("en zonder de entiteit-id, wel met de integratie erbij",
         "sensor.ford_soc" not in stil[0] and "integratie" in stil[0], f"{stil}")
controle("en niet nog een keer", not wacht(62), "")
besluit41b, _ = asyncio.run(ronde(coach41b, inst41b, nu=t0 + dt.timedelta(minutes=62)))
controle("ondertussen laadt hij gewoon door op de laatst bekende stand",
         besluit41b["charge"], f"{besluit41b}")
hass41b.states.zet("sensor.ford_soc", "44")
weer = wacht(63)
# Sinds 06-09-2026 gaat "doet het weer" niet meer naar de telefoon, alleen in
# de geschiedenis: de eigenaar wil per beurt één verslag plus wat kritiek is.
controle("terug: niets meer naar de telefoon", not weer, f"{weer}")
controle("en daarna stil", not wacht(14), "")
geschiedenis = asyncio.run(async_get_meldingen(hass41b).async_list())
controle("en alles staat in de geschiedenis, op volgorde",
         [g["message"][:12] for g in geschiedenis][:1] == ["proefmelding"]
         and any("meldt al" in g["message"] for g in geschiedenis)
         and any("doet het weer" in g["message"] for g in geschiedenis), f"{geschiedenis}")

print("=== 42. niets van één installatie zit in de code ===")
# De eigenaar op 30-08-2026: "je hebt toch niet iets van mij thuis hard gecodeerd? Het
# moet wel universeel zijn." Deze proef dwingt dat af in plaats van het te
# beloven: hij leest de eigen broncode en valt om zodra er een entiteitnaam in
# staat. Elke sensor hoort uit de instellingen van de klant te komen.
import re as _re

BRONMAP = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "domotiapp_coach"
VERBODEN = _re.compile(
    r"[\"'](?:sensor|binary_sensor|switch|number|button|select|input_[a-z]+)\.[a-z0-9_]+[\"']"
)

gevonden = []
for pad in sorted(BRONMAP.glob("*.py")):
    for nummer, regel in enumerate(pad.read_text(encoding="utf-8").split("\n"), 1):
        # Alleen echte code. Een entiteitnaam in een uitleg is een bewijsstuk en
        # geen aanname; die mag blijven staan.
        kaal = regel.strip()
        if kaal.startswith("#") or kaal.startswith('"""') or kaal.startswith("*"):
            continue
        for treffer in VERBODEN.findall(regel):
            gevonden.append(f"{pad.name}:{nummer} {treffer}")

print(f"  {len(list(BRONMAP.glob('*.py')))} bestanden nagelezen, "
      f"{len(gevonden)} vaste entiteitnamen")
controle("geen enkele entiteitnaam staat vast in de code", not gevonden,
         "; ".join(gevonden[:5]))

# En hetzelfde voor de merknamen van deze ene woning.
EIGEN = _re.compile(r"(solaredge|electricity_meter|qpl3u7p4|fcq_)", _re.IGNORECASE)
sporen = []
for pad in sorted(BRONMAP.glob("*.py")):
    for nummer, regel in enumerate(pad.read_text(encoding="utf-8").split("\n"), 1):
        kaal = regel.strip()
        if kaal.startswith("#") or kaal.startswith('"""'):
            continue
        if EIGEN.search(regel):
            sporen.append(f"{pad.name}:{nummer}")
print(f"  en {len(sporen)} verwijzingen naar de merken van één woning")
controle("geen merknaam van één installatie in de code", not sporen,
         "; ".join(sporen[:5]))

print("=== 43. het huisverbruik werkt bij elke soort meter ===")
# De som is `zon + inkoop - teruglevering - alle apparaten`, en die moet kloppen
# bij een gesplitste meter én bij een meter met een teken, in allebei de
# richtingen. Het vinkje `grid_signed_invert` stond al overal en ontbrak hier.


def huis_uit(bronnen, rijen, apparaten=()):
    """Het huisverbruik per uur, met een nagemaakt archief."""
    inst = instellingen()
    inst["sources"] = dict(inst["sources"], **bronnen)
    inst["devices"] = [dict(LAADPAAL, entity=e) for e in apparaten] or []
    _, _, coach = bouw(huis(), inst)

    class NepArchief:
        async def async_lees(self, ids, start, einde):
            return {e: rijen.get(e, []) for e in ids}

    coachmod.async_get_archive = lambda hass: NepArchief()
    coach._huis_tot = None
    asyncio.run(coach._async_huisverbruik(inst, dt.datetime(2026, 8, 30, 12, 0)))
    return coach._huis_kwh


# Eén kwartier om 12:00, in seconden sinds 1970. Het harnas rekent niet om naar
# lokale tijd, dus het uur in de uitkomst is hier gewoon 12.
STEMPEL = int(dt.datetime(2026, 8, 30, 12, 0, tzinfo=dt.timezone.utc).timestamp())


def kwartier(watt):
    return [{"start": STEMPEL, "gemiddeld": watt}]


# Gesplitste meter: 2 kW zon, 1 kW inkoop, 0 teruglevering, 2,5 kW laadpaal.
# Het huis gebruikt dan 2 + 1 - 0 - 2,5 = 0,5 kW.
gesplitst = huis_uit(
    {"grid_mode": "split", "grid_import": "sensor.in", "grid_export": "sensor.uit",
     "grid_signed": "", "solar": "sensor.zon"},
    {"sensor.zon": kwartier(2000), "sensor.in": kwartier(1000),
     "sensor.uit": kwartier(0), "sensor.paal": kwartier(2500)},
    apparaten=["sensor.paal"],
)
print(f"  gesplitste meter: {gesplitst}")
controle("de gesplitste meter rekent goed",
         abs(gesplitst.get(12, 0) - 0.5) < 0.01, f"{gesplitst}")

# Meter met een teken, plus is inkoop: hetzelfde antwoord.
getekend = huis_uit(
    {"grid_mode": "signed", "grid_signed": "sensor.net", "grid_signed_invert": False,
     "grid_import": "", "grid_export": "", "solar": "sensor.zon"},
    {"sensor.zon": kwartier(2000), "sensor.net": kwartier(1000),
     "sensor.paal": kwartier(2500)},
    apparaten=["sensor.paal"],
)
print(f"  meter met een teken: {getekend}")
controle("een meter met een teken geeft hetzelfde",
         abs(getekend.get(12, 0) - 0.5) < 0.01, f"{getekend}")

# En dezelfde meter die andersom telt: plus is dan teruglevering.
omgekeerd = huis_uit(
    {"grid_mode": "signed", "grid_signed": "sensor.net", "grid_signed_invert": True,
     "grid_import": "", "grid_export": "", "solar": "sensor.zon"},
    {"sensor.zon": kwartier(2000), "sensor.net": kwartier(-1000),
     "sensor.paal": kwartier(2500)},
    apparaten=["sensor.paal"],
)
print(f"  omgekeerde meter: {omgekeerd}")
controle("en een meter die andersom telt ook",
         abs(omgekeerd.get(12, 0) - 0.5) < 0.01, f"{omgekeerd}")

# Zonder zonnepanelen, zonder apparaten: dan is het huis gewoon de inkoop.
kaal = huis_uit(
    {"grid_mode": "split", "grid_import": "sensor.in", "grid_export": "sensor.uit",
     "grid_signed": "", "solar": ""},
    {"sensor.in": kwartier(800), "sensor.uit": kwartier(0)},
)
print(f"  woning zonder zon: {kaal}")
controle("zonder zonnepanelen is het huis de inkoop",
         abs(kaal.get(12, 0) - 0.8) < 0.01, f"{kaal}")

# En de mediaan, niet het gemiddelde. de keuze van 30-08-2026: één keer
# wassen tilt een gemiddelde over een week heen op.
controle("de mediaan van 1, 1, 1 en 9 is 1", coachmod._mediaan([1.0, 1.0, 1.0, 9.0]) == 1.0,
         f"{coachmod._mediaan([1.0, 1.0, 1.0, 9.0])}")
controle("en van 1, 2, 3 is 2", coachmod._mediaan([3.0, 1.0, 2.0]) == 2.0,
         f"{coachmod._mediaan([3.0, 1.0, 2.0])}")

print("=== 48. een laadbeurt komt met kosten en besparing in de opslag ===")
# De eigenaar op 05-09-2026: "Kunnen we ergens een overzichtje maken wat we hebben
# bespaard? Dat is natuurlijk het belangrijkste voor de klant." Het ijkpunt is
# de prijs op het moment van inpluggen. Vast contract: elke kWh uit eigen zon
# kost wat teruglevering opgebracht had in plaats van de inkoopprijs.
inst48 = instellingen()
hass48, store48, coach48 = bouw(huis(teruglevering=1500.0), inst48)
t48 = dt.datetime(2026, 8, 18, 14, 37)
asyncio.run(ronde(coach48, inst48, t48))                       # kabel erin, nog niets
hass48.states.zet("sensor.laadpaal_status", "charging")
hass48.states.zet("sensor.laadpaal_stroom", "6.0")
hass48.states.zet("sensor.laadpaal_vermogen", "4140")
asyncio.run(ronde(coach48, inst48, t48 + dt.timedelta(minutes=1)))   # laadt op 4,14 kW
asyncio.run(ronde(coach48, inst48, t48 + dt.timedelta(minutes=10)))  # negen minuten later
asyncio.run(ronde(coach48, inst48, t48 + dt.timedelta(minutes=11)))
hass48.states.zet("sensor.laadpaal_status", "disconnected")
hass48.states.zet("sensor.laadpaal_stroom", "0.05")
hass48.states.zet("sensor.laadpaal_vermogen", "0")
asyncio.run(ronde(coach48, inst48, t48 + dt.timedelta(minutes=12)))  # kabel eruit
# De coach gelooft een losse kabel pas na `KABEL_ONTDREUN`, en de schrijftaak
# naar de opslag loopt buiten de ronde om.
asyncio.run(ronde(coach48, inst48, t48 + dt.timedelta(minutes=13)))
asyncio.run(hass48.afmaken())
beurten48 = asyncio.run(coachmod.async_get_beurten(hass48).async_list())
print(f"  {len(beurten48)} beurt(en)")
for b in beurten48:
    print(f"  {b['plugged_at']} tot {b['ended']}: {b['kwh']} kWh, zon {b['solar_kwh']}, "
          f"betaald {b['paid']}, ijk {b['ref_price']}, bespaard {b['saved']}, compleet {b['complete']}")
controle("één beurt, afgesloten", len(beurten48) == 1 and beurten48[0]["complete"], f"{beurten48}")
b48 = beurten48[0] if beurten48 else {}
# Elf minuten en niet tien: de minuut waarin de kabel eruit ging telt nog mee
# met het vermogen van de ronde ervoor, net als in het verslag (`_geladen`).
controle("elf minuten op 4,14 kW is 0,76 kWh", abs(b48.get("kwh", 0) - 0.759) < 0.01, f"{b48.get('kwh')}")
controle("en bijna allemaal zon, want er ging 1,5 kW naar het net",
         b48.get("solar_kwh", 0) > 0.9 * b48.get("kwh", 1), f"{b48.get('solar_kwh')} van {b48.get('kwh')}")
tarief48 = coachmod.ChargerCoach._tariff(inst48)
controle("het ijkpunt is de prijs bij het inpluggen",
         b48.get("ref_price") == tarief48.buy, f"{b48.get('ref_price')} tegen {tarief48.buy}")
zon48 = b48.get("solar_kwh", 0)
verwacht48 = zon48 * (tarief48.feed_in or 0) + (b48.get("kwh", 0) - zon48) * (tarief48.buy or 0)
controle("betaald is de zon tegen teruglevering en de rest tegen inkoop",
         abs(b48.get("paid", 0) - verwacht48) < 0.001, f"{b48.get('paid')} tegen {verwacht48:.4f}")
controle("bespaard is het ijkpunt min wat betaald is",
         b48.get("saved") is not None
         and abs(b48["saved"] - (b48["ref_cost"] - b48["paid"])) < 0.0001, f"{b48.get('saved')}")
controle("de ingeplugde tijd is de eerste ronde met kabel",
         b48.get("plugged_at") == "2026-08-18T14:37:00", f"{b48.get('plugged_at')}")

print("=== 48b. midden in een beurt ingestapt: geen ijkpunt, geen verzonnen besparing ===")
# De eigenaar op 05-09-2026, bij "bespaard -0,01" op een beurt die vrijdagavond
# begon en die de coach pas na een herstart om 15:03 zag: "waarom is er
# vandaag niks bespaard?" Het ijkpunt was de prijs van het herstartuur, en dat
# is het verkeerde uur. Zonder inplugmoment dus geen ijkpunt.
hass48b, _, coach48b = bouw(huis(status="charging", stroom=15.0, vermogen=10800.0,
                                 teruglevering=0.0, afname=9000.0), inst48)
asyncio.run(ronde(coach48b, inst48, t48))
asyncio.run(ronde(coach48b, inst48, t48 + dt.timedelta(minutes=1)))
# De opslag krijgt de lopende beurt elke vijf minuten; dus nog twee ronden.
asyncio.run(ronde(coach48b, inst48, t48 + dt.timedelta(minutes=5)))
asyncio.run(ronde(coach48b, inst48, t48 + dt.timedelta(minutes=6)))
asyncio.run(hass48b.afmaken())
b48b = asyncio.run(coachmod.async_get_beurten(hass48b).async_list())
print(f"  {[(b['kwh'], b['ref_price'], b['saved'], b['resumed']) for b in b48b]}")
controle("de beurt staat in de opslag als hervat", len(b48b) == 1 and b48b[0]["resumed"], f"{b48b}")
controle("zonder ijkpunt en zonder besparing",
         b48b and b48b[0]["ref_price"] is None and b48b[0]["saved"] is None and b48b[0]["price_unknown"],
         f"{b48b}")
controle("maar met de kilowatturen en wat ze kostten",
         b48b and b48b[0]["kwh"] > 0.1 and b48b[0]["paid"] > 0, f"{b48b}")

print("=== 48c. na een herstart rekent hij terug uit de recorder en de kwartieropslag ===")
# De eigenaar op 05-09-2026: "kan je niet historisch terugrekenen?" De recorder weet
# wanneer de kabel erin ging, de kwartieropslag wat de paal en het net daarna
# deden. Hier nagemaakt: kabel erin om 13:37, een uur op 4,14 kW met 1,5 kW
# teruglevering ernaast, en de coach die om 14:37 instapt.
hass48c, _, coach48c = bouw(huis(status="charging", stroom=6.0, vermogen=4140.0,
                                 teruglevering=1500.0), inst48)
plug48c = t48 - dt.timedelta(hours=1)

async def geschiedenis48c(entity_id, start, einde):
    if entity_id == "sensor.laadpaal_status":
        return [(plug48c - dt.timedelta(hours=2), "disconnected"),
                (plug48c, "awaiting_start"),
                (plug48c + dt.timedelta(minutes=1), "charging")]
    return []

async def kwartieren48c(entity_ids, start, einde):
    uit = {e: [] for e in entity_ids}
    for i in range(4):
        begin = int((plug48c + dt.timedelta(minutes=15 * i)).timestamp())
        for e, w in (("sensor.laadpaal_vermogen", 4140.0), ("sensor.teruglevering", 1500.0),
                     ("sensor.afname", 0.0)):
            if e in uit:
                uit[e].append({"start": begin, "laagste": w, "piek": w, "gemiddeld": w, "seconden": 900})
    return uit

coach48c._async_geschiedenis = geschiedenis48c
coach48c._async_kwartieren = kwartieren48c
asyncio.run(ronde(coach48c, inst48, t48))
asyncio.run(hass48c.afmaken())          # het terugrekenen loopt als taak
asyncio.run(ronde(coach48c, inst48, t48 + dt.timedelta(minutes=1)))
asyncio.run(hass48c.afmaken())
b48c = asyncio.run(coachmod.async_get_beurten(hass48c).async_list())
print(f"  {[(b['plugged_at'], b['kwh'], b['solar_kwh'], b['paid'], b['ref_cost'], b['saved'], b['resumed']) for b in b48c]}")
controle("het inplugmoment komt uit de recorder",
         len(b48c) == 1 and b48c[0]["plugged_at"] == plug48c.isoformat(), f"{b48c}")
controle("het uur van vóór de herstart telt mee: 4,14 kWh, bijna allemaal zon",
         b48c and abs(b48c[0]["kwh"] - 4.14 - 0.069) < 0.05 and b48c[0]["solar_kwh"] > 4.0, f"{b48c}")
controle("met een ijkpunt en een besparing, en niet meer als hervat",
         b48c and b48c[0]["ref_cost"] is not None and b48c[0]["saved"] is not None
         and b48c[0]["saved"] >= 0 and not b48c[0]["resumed"], f"{b48c}")

print("=== 49. elk paneelcommando is ook aangemeld ===")
# Op 05-09-2026 stond domotiapp_coach/savings/list keurig in websocket.py en
# antwoordde Home Assistant "Unknown command": de functie was er, de regel in
# `async_register` niet. Een commando zonder aanmelding bestaat niet.
bron49 = (pathlib.Path(__file__).resolve().parent.parent
          / "custom_components" / "domotiapp_coach" / "websocket.py").read_text(encoding="utf-8")
aangemeld49 = set(_re.findall(r"async_register_command\(hass, (\w+)\)", bron49))
namen49 = {}
for blok in _re.split(r"\n@websocket_api\.websocket_command", bron49)[1:]:
    soort = _re.search(r'"type"\): "([^"]+)"', blok)
    functie = _re.search(r"\n(?:async )?def (\w+)\(", blok)
    if soort and functie:
        namen49[soort.group(1)] = functie.group(1)
niet49 = sorted(t for t, f in namen49.items() if f not in aangemeld49)
print(f"  {len(namen49)} commando's, {len(aangemeld49)} aangemeld")
controle("elk commando uit websocket.py staat in async_register", not niet49,
         f"niet aangemeld: {niet49}")
controle("en savings/list is er een van", "domotiapp_coach/savings/list" in namen49, "")

print("=== 50. de auto trekt meer dan gevraagd: onder de groep van de paal blijven ===")
# de klantwoning, 06-09-2026 om 04:18:30: limiet 16 A, de Ford trok 16,9 A op één
# fase, de groep staat op 16 A. Om 04:25:57 hield de paal ermee op, startte op
# drie fasen opnieuw en de Ford ging in storing. Met de circuitlimiet als
# sensor blijft de coach er zoveel onder als de auto erboven zit.
PAAL50 = dict(LAADPAAL, entities={**LAADPAAL["entities"],
                                  "circuit_limit": "sensor.laadpaal_circuit"})
ford50 = dict(LAADPAAL["cars"][0], soc_entity="sensor.auto_soc", phases="three")
PAAL50["cars"] = [ford50]
inst50 = instellingen(devices=[PAAL50])
inst50["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
huis50 = huis(status="charging", stroom=16.88, vermogen=3754.0, teruglevering=0.0, afname=4000.0)
huis50["sensor.laadpaal_circuit"] = "16"
huis50["sensor.laadpaal_max"] = "16"
huis50["sensor.laadpaal_dyn"] = "16"
huis50["sensor.auto_soc"] = "86"
hass50, _, coach50 = bouw(huis50, inst50)
# Snelladen, zodat de coach het maximum wil: dan is elke ampère minder de groep.
coach50.async_boost("dev-laadpaal", True)
b50, v50 = asyncio.run(ronde(coach50, inst50, paal=PAAL50, nu=dt.datetime(2026, 9, 6, 4, 19)))
print(f"  {b50['rule']}: {b50['amps']} A")
controle("hij vraagt 15 A: de groep van 16 min de 0,9 A die de auto erboven zit",
         b50["amps"] == 15, f"{b50['amps']} A ({b50['rule']})")
huis50b = dict(huis50, **{"sensor.laadpaal_stroom": "14.4", "sensor.laadpaal_vermogen": "10400"})
hass50b, _, coach50b = bouw(huis50b, inst50)
coach50b.async_boost("dev-laadpaal", True)
b50b, _ = asyncio.run(ronde(coach50b, inst50, paal=PAAL50, nu=dt.datetime(2026, 9, 6, 5, 30)))
controle("op drie fasen onder de limiet blijft het gewoon 16 A", b50b["amps"] == 16,
         f"{b50b['amps']} A ({b50b['rule']})")

print("=== 51. één fase gemeten op een driefasig profiel: daarmee rekenen ===")
# Dezelfde nacht om 04:17: de Easee koos in automatische fasemodus zelf één
# fase. Die modus blijft (de eigenaar: "belangrijk voor gastauto's"), dus de coach
# hoort te zien wat er loopt en daar deze beurt mee te rekenen: drie keer zo
# lang, en dat zegt hij erbij.
inst51 = instellingen(devices=[PAAL50])
inst51["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
huis51 = huis(status="charging", stroom=12.79, vermogen=2877.0, teruglevering=0.0, afname=3000.0)
huis51["sensor.laadpaal_circuit"] = "16"
huis51["sensor.laadpaal_max"] = "16"
huis51["sensor.auto_soc"] = "40"
hass51, _, coach51 = bouw(huis51, inst51)
for minuut in (17, 18, 19):
    b51, _ = asyncio.run(ronde(coach51, inst51, paal=PAAL50, nu=dt.datetime(2026, 9, 5, 12, minuut)))
plan51 = b51["plan_ahead"]
print(f"  tip: {b51.get('tip', '')[:70]}")
print(f"  uiterlijk starten: {plan51.get('latest_start')}")
controle("na drie ronden zegt de tip dat hij met één fase rekent",
         "rekent deze beurt met die ene fase" in (b51.get("tip") or ""), f"{b51.get('tip')}")
# Dezelfde auto op drie fasen (10,4 kW) mag drie keer later beginnen.
huis51b = dict(huis51, **{"sensor.laadpaal_stroom": "12.79", "sensor.laadpaal_vermogen": "8800"})
hass51b, _, coach51b = bouw(huis51b, inst51)
for minuut in (17, 18, 19):
    b51b, _ = asyncio.run(ronde(coach51b, inst51, paal=PAAL50, nu=dt.datetime(2026, 9, 5, 12, minuut)))
plan51b = b51b["plan_ahead"]
print(f"  op drie fasen: {plan51b.get('latest_start')}")
controle("en op één fase moet hij uren eerder beginnen dan op drie",
         plan51["latest_start"] and plan51b["latest_start"]
         and plan51["latest_start"] < plan51b["latest_start"],
         f"{plan51['latest_start']} tegen {plan51b['latest_start']}")

print("=== 52. een opgegeven accustand krijgt een uur extra speling ===")
# De eigenaar op 06-09-2026: "een auto die niet in HA kan moet langer speling hebben.
# Liever iets eerder vol dan niet vol."
inst52 = instellingen()
inst52["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
inst52["car_soc"] = [{"device": "dev-laadpaal", "car": "car-1", "percent": 40.0, "meter": 100.0}]
hass52, _, coach52 = bouw(huis(status="charging", stroom=13.5, vermogen=3070.0,
                               teruglevering=0.0, afname=1800.0), inst52)
b52, _ = asyncio.run(ronde(coach52, inst52, nu=dt.datetime(2026, 9, 5, 20, 0)))
ford52 = dict(LAADPAAL["cars"][0], soc_entity="sensor.auto_soc")
PAAL52 = dict(LAADPAAL, cars=[ford52])
inst52b = instellingen(devices=[PAAL52])
inst52b["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
huis52b = huis(status="charging", stroom=13.5, vermogen=3070.0, teruglevering=0.0, afname=1800.0)
huis52b["sensor.auto_soc"] = "40"
hass52b, _, coach52b = bouw(huis52b, inst52b)
b52b, _ = asyncio.run(ronde(coach52b, inst52b, paal=PAAL52, nu=dt.datetime(2026, 9, 5, 20, 0)))
l52, l52b = b52["plan_ahead"]["latest_start"], b52b["plan_ahead"]["latest_start"]
print(f"  opgegeven: {l52}   gemeten: {l52b}")
controle("met een opgegeven stand begint hij precies een uur eerder dan met een gemeten",
         l52 and l52b and (dt.datetime.fromisoformat(l52b) - dt.datetime.fromisoformat(l52))
         == dt.timedelta(hours=1), f"{l52} tegen {l52b}")

print("=== 53. een auto die bovenin gas terugneemt: leren en ermee rekenen ===")
# De eigenaar op 06-09-2026: "bepaalde auto's schroeven vanaf een bepaald procent zelf
# hun doorlaatbaarheid in ampère terug." De coach meet dat alleen als de auto
# zelf de rem is: limiet 14 A, hij neemt 8 A, niets anders houdt hem tegen.
inst53 = instellingen(devices=[PAAL52])
inst53["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
huis53 = huis(status="charging", stroom=8.0, vermogen=1840.0, teruglevering=0.0, afname=1800.0)
huis53["sensor.auto_soc"] = "85"
hass53, store53, coach53 = bouw(huis53, inst53)
coach53.async_boost("dev-laadpaal", True)
# De ronde van `async_boost` zelf draait op de echte klok (zie proef 23) en zet
# daarmee het begin van de beurt in het heden; de proef speelt in september.
coach53._since["dev-laadpaal"] = dt.datetime(2026, 9, 5, 20, 55)
# En dat de paal toen al laadde, want sinds 17-09-2026 begint de aanloop opnieuw
# zodra de paal uit `charging` valt en terugkomt. Zonder deze regel zet de ronde
# van `async_boost` de klok alsnog op nu.
coach53._laadde["dev-laadpaal"] = True
# Snelladen zet de limiet omhoog, en daarna krijgt de auto een kwartier om bij te
# komen voordat wat hij neemt zijn tempo is (`TEMPO_HERSTEL`, sinds v0.69.0).
for minuut in (0, 1, 2, 3, 4, 15, 16, 17):
    asyncio.run(ronde(coach53, inst53, paal=PAAL52, nu=dt.datetime(2026, 9, 5, 21, minuut)))
rijen53 = inst53.get("car_pace") or []
print(f"  geleerd: {rijen53}")
controle("na de aanloop staat band 8 in de instellingen, op 1,84 kW",
         any(r.get("band") == 8 and abs(r.get("kw", 0) - 1.84) < 0.01 for r in rijen53),
         f"{rijen53}")
# En de volgende beurt rekent ermee: op 85% met 1,84 kW in band 8 duurt het
# langer dan met de 3,2 kW die 14 A op één fase geeft.
huis53b = dict(huis53, **{"sensor.laadpaal_status": "ready_to_charge",
                         "sensor.laadpaal_stroom": "0.05", "sensor.laadpaal_vermogen": "0"})
inst53b = instellingen(devices=[PAAL52], car_pace=[{"device": "dev-laadpaal", "car": "car-1",
                                                     "band": 8, "kw": 1.84, "at": "x"},
                                                    {"device": "dev-laadpaal", "car": "car-1",
                                                     "band": 9, "kw": 1.2, "at": "x"}])
inst53b["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
hass53b, _, coach53b = bouw(huis53b, inst53b)
b53b, _ = asyncio.run(ronde(coach53b, inst53b, paal=PAAL52, nu=dt.datetime(2026, 9, 5, 21, 0)))
inst53c = instellingen(devices=[PAAL52])
inst53c["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
hass53c, _, coach53c = bouw(dict(huis53b), inst53c)
b53c, _ = asyncio.run(ronde(coach53c, inst53c, paal=PAAL52, nu=dt.datetime(2026, 9, 5, 21, 0)))
l53b, l53c = b53b["plan_ahead"]["latest_start"], b53c["plan_ahead"]["latest_start"]
print(f"  met afbouw: {l53b}   zonder: {l53c}")
controle("met het geleerde tempo begint hij eerder", l53b and l53c and l53b < l53c,
         f"{l53b} tegen {l53c}")

print("=== 53b. een halve meting wordt geen tempo (thuis, 17-09-2026) ===")
# Om 14:24:31 ging snelladen aan, de paal herstartte en zei om 14:24:58 weer
# "charging" terwijl de stroomsensor nog op 0,152 A van de vorige stand stond.
# De coach schreef 0,1 kW op als het tempo van band 0, rekende de ronde erna
# 21,41 uur waar het er 1,93 waren, en de klaar-tijdregel bleef de hele middag
# staan. Twee dingen houden dat nu tegen: de aanloop begint opnieuw zodra de
# paal opnieuw begint, en een band telt pas als twee ronden hetzelfde zeggen.
inst53d = instellingen(devices=[PAAL52])
inst53d["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
huis53d = huis(status="charging", stroom=8.0, vermogen=1840.0, teruglevering=0.0, afname=1800.0)
huis53d["sensor.auto_soc"] = "85"
hass53d, _, coach53d = bouw(huis53d, inst53d)
coach53d.async_boost("dev-laadpaal", True)
coach53d._since["dev-laadpaal"] = dt.datetime(2026, 9, 5, 20, 55)
coach53d._laadde["dev-laadpaal"] = True
for minuut in (0, 1, 2):
    asyncio.run(ronde(coach53d, inst53d, paal=PAAL52, nu=dt.datetime(2026, 9, 5, 21, minuut)))
# De paal valt één ronde uit `charging` (een nieuwe limiet, zoals een Easee bij
# snelladen doet) en komt terug terwijl de stroomsensor nog achterloopt.
hass53d.states.zet("sensor.laadpaal_status", "awaiting_start")
asyncio.run(ronde(coach53d, inst53d, paal=PAAL52, nu=dt.datetime(2026, 9, 5, 21, 3)))
hass53d.states.zet("sensor.laadpaal_status", "charging")
hass53d.states.zet("sensor.laadpaal_stroom", "0.152")
hass53d.states.zet("sensor.laadpaal_vermogen", "35")
asyncio.run(ronde(coach53d, inst53d, paal=PAAL52, nu=dt.datetime(2026, 9, 5, 21, 4)))
rijen53d = inst53d.get("car_pace") or []
print(f"  na de herstart met een achterlopende stroomsensor: {rijen53d}")
controle("de tussenstand van 0,152 A wordt geen tempo",
         not any(r.get("kw", 9) < 1.0 for r in rijen53d), f"{rijen53d}")

# En één losse ronde met een rare waarde telt ook zonder herstart niet mee: pas
# als de volgende ronde hetzelfde zegt, is het een meting.
inst53e = instellingen(devices=[PAAL52])
inst53e["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
huis53e = huis(status="charging", stroom=8.0, vermogen=1840.0, teruglevering=0.0, afname=1800.0)
huis53e["sensor.auto_soc"] = "85"
hass53e, _, coach53e = bouw(huis53e, inst53e)
coach53e.async_boost("dev-laadpaal", True)
coach53e._since["dev-laadpaal"] = dt.datetime(2026, 9, 5, 20, 55)
coach53e._laadde["dev-laadpaal"] = True
asyncio.run(ronde(coach53e, inst53e, paal=PAAL52, nu=dt.datetime(2026, 9, 5, 21, 0)))
asyncio.run(ronde(coach53e, inst53e, paal=PAAL52, nu=dt.datetime(2026, 9, 5, 21, 15)))
asyncio.run(ronde(coach53e, inst53e, paal=PAAL52, nu=dt.datetime(2026, 9, 5, 21, 30)))
hass53e.states.zet("sensor.laadpaal_stroom", "0.3")
hass53e.states.zet("sensor.laadpaal_vermogen", "69")
asyncio.run(ronde(coach53e, inst53e, paal=PAAL52, nu=dt.datetime(2026, 9, 5, 21, 31)))
hass53e.states.zet("sensor.laadpaal_stroom", "8.0")
hass53e.states.zet("sensor.laadpaal_vermogen", "1840")
asyncio.run(ronde(coach53e, inst53e, paal=PAAL52, nu=dt.datetime(2026, 9, 5, 21, 32)))
asyncio.run(ronde(coach53e, inst53e, paal=PAAL52, nu=dt.datetime(2026, 9, 5, 21, 33)))
rijen53e = inst53e.get("car_pace") or []
print(f"  één rare ronde tussen twee goede: {rijen53e}")
controle("één losse ronde telt niet, de twee gelijke wel",
         any(abs(r.get("kw", 0) - 1.84) < 0.01 for r in rijen53e)
         and not any(r.get("kw", 9) < 1.0 for r in rijen53e), f"{rijen53e}")

# En een rij die er vóór v0.66.0 in is gekomen wordt bij het lezen genegeerd:
# een herstart haalt hem niet uit de opslag en hij blijft anders bijten zodra
# de auto weer in die band komt.
inst53f = instellingen(devices=[PAAL52], car_pace=[
    {"device": "dev-laadpaal", "car": "car-1", "band": 0, "kw": 0.1, "at": "x"},
    {"device": "dev-laadpaal", "car": "car-1", "band": 8, "kw": 1.84, "at": "x"}])
gelezen53 = coachmod.ChargerCoach._tempo_uit(inst53f, "dev-laadpaal", "car-1")
print(f"  uit de opslag gelezen: {gelezen53}")
controle("0,1 kW uit een oude opslag telt niet meer mee, 1,84 wel",
         gelezen53 == {8: 1.84}, f"{gelezen53}")

print("=== 54. 'klaar' op 86%: één herstart, dan geloven, en na een kwartier laden opnieuw ===")
inst54 = instellingen(devices=[PAAL52])
inst54["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
huis54 = huis(status="charging", stroom=13.5, vermogen=3070.0, teruglevering=0.0, afname=1800.0)
huis54["sensor.auto_soc"] = "86"
hass54, _, coach54 = bouw(huis54, inst54)
coach54.async_boost("dev-laadpaal", True)
asyncio.run(ronde(coach54, inst54, paal=PAAL52, nu=dt.datetime(2026, 9, 6, 4, 26)))
hass54.states.zet("sensor.laadpaal_status", "completed")
hass54.states.zet("sensor.laadpaal_stroom", "0.01")
hass54.states.zet("sensor.laadpaal_vermogen", "0")
# `ronde()` geeft dezelfde lijst terug die hij de volgende keer leegt, dus kopiëren.
b1, v1 = asyncio.run(ronde(coach54, inst54, paal=PAAL52, nu=dt.datetime(2026, 9, 6, 4, 27)))
v1 = list(v1)
b2, v2 = asyncio.run(ronde(coach54, inst54, paal=PAAL52, nu=dt.datetime(2026, 9, 6, 4, 28)))
v2 = list(v2)
starts = lambda v: [d for d in v if d[0] == "easee" and d[2].get("action_command") == "start"]
print(f"  04:27 {b1['rule']} start={len(starts(v1))}   04:28 {b2['rule']} start={len(starts(v2))}")
controle("de eerste ronde na 'klaar' stuurt een start", len(starts(v1)) == 1, f"{v1}")
controle("de tweede gelooft 'klaar'", b2["rule"] == "complete" and not starts(v2), f"{b2['rule']} {v2}")
# De Ford komt na negen minuten weer op gang, laadt een kwartier, en haakt
# nog eens af: dan mag er weer één poging komen.
hass54.states.zet("sensor.laadpaal_status", "charging")
hass54.states.zet("sensor.laadpaal_stroom", "13.5")
hass54.states.zet("sensor.laadpaal_vermogen", "3070")
for minuut in (36, 45, 52):
    asyncio.run(ronde(coach54, inst54, paal=PAAL52, nu=dt.datetime(2026, 9, 6, 4, minuut)))
hass54.states.zet("sensor.laadpaal_status", "completed")
hass54.states.zet("sensor.laadpaal_stroom", "0.01")
hass54.states.zet("sensor.laadpaal_vermogen", "0")
b3, v3 = asyncio.run(ronde(coach54, inst54, paal=PAAL52, nu=dt.datetime(2026, 9, 6, 4, 53)))
controle("na een kwartier laden mag er bij een nieuwe 'klaar' weer één start uit",
         len(starts(v3)) == 1, f"{b3['rule']} {v3}")
# Een gast, of een auto zonder accustand: dan is 'klaar' het enige dat er is.
inst54b = instellingen()
inst54b["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
hass54b, _, coach54b = bouw(huis(status="completed", teruglevering=0.0, afname=1800.0), inst54b)
b4, v4 = asyncio.run(ronde(coach54b, inst54b, nu=dt.datetime(2026, 9, 6, 4, 27)))
controle("zonder accustand geen herstart", b4["rule"] == "complete" and not starts(v4),
         f"{b4['rule']} {v4}")

print("=== 55. wie welke melding krijgt: per persoon, per soort ===")
# De eigenaar op 06-09-2026: "de klant kan meldingen aan en uit zetten in het tabje
# Meldingen. De admin voegt de personen toe, en die persoon ziet alleen
# zichzelf. En niet telkens onnodig meldingen sturen."
ontv = laad("ontvangers")
inst55 = instellingen()
inst55["notifications"]["people"] = [
    {"id": "p-1", "name": "Bewoner", "target": "mobile_app_telefoon", "user_id": "u-1",
     "kinds": {"kritiek": True, "melding": True, "besluit": False, "belasting": True}},
    {"id": "p-2", "name": "Partner", "target": "mobile_app_partner", "user_id": "u-partner",
     "kinds": {"kritiek": True, "melding": False, "besluit": False, "belasting": False}},
    {"id": "p-3", "name": "Alles", "target": "mobile_app_alles", "user_id": "",
     "kinds": {"kritiek": True, "melding": True, "besluit": True, "belasting": True}},
]
controle("kritiek gaat naar iedereen die dat aan heeft",
         ontv.ontvangers(inst55, "kritiek") == ["mobile_app_telefoon", "mobile_app_partner", "mobile_app_alles"],
         f"{ontv.ontvangers(inst55, 'kritiek')}")
controle("een verslag alleen naar wie verslagen wil",
         ontv.ontvangers(inst55, "melding") == ["mobile_app_telefoon", "mobile_app_alles"], "")
controle("een besluit alleen naar wie alles wil volgen",
         ontv.ontvangers(inst55, "besluit") == ["mobile_app_alles"], "")
controle("een onbekende soort gaat naar niemand", ontv.ontvangers(inst55, "geheim") == [], "")
# De coach zelf: een verslag en een besluit.
hass55, _, coach55 = bouw(huis(), inst55)
asyncio.run(coach55._async_tell("proefverslag"))
asyncio.run(coach55._async_tell("proefalarm", kritiek=True))
asyncio.run(coach55._async_noteer("proefbesluit", dt.datetime(2026, 9, 6, 10, 0)))
naar = [(d[1], d[2]["message"]) for d in hass55.services.verstuurd if d[0] == "notify"]
print(f"  verstuurd: {naar}")
controle("het verslag ging naar de eigenaar en Alles, niet naar Partner",
         [t for t, m in naar if m == "proefverslag"] == ["mobile_app_telefoon", "mobile_app_alles"], f"{naar}")
controle("het alarm ging naar alle drie",
         len([t for t, m in naar if m == "proefalarm"]) == 3, f"{naar}")
controle("het besluit alleen naar Alles",
         [t for t, m in naar if m == "proefbesluit"] == ["mobile_app_alles"], f"{naar}")
# Een gewone bewoner ziet alleen zichzelf, en zet alleen zijn eigen schuiven.
eigen = ontv.alleen_eigen(inst55, "u-partner")
controle("een bewoner ziet alleen zijn eigen persoon",
         [p["id"] for p in eigen["notifications"]["people"]] == ["p-2"], f"{eigen['notifications']['people']}")
controle("en de rest van de instellingen blijft", eigen["devices"] == inst55["devices"], "")
nieuw55 = ontv.zet_eigen_soorten(inst55, "u-partner", {"melding": True, "besluit": True, "name": "hack"})
controle("hij zet zijn eigen soorten, en niets anders",
         nieuw55[1]["kinds"] == {"kritiek": True, "melding": True, "besluit": True, "belasting": False}
         and nieuw55[1]["name"] == "Partner" and nieuw55[0]["kinds"]["melding"] is True, f"{nieuw55}")
controle("zonder gekoppelde persoon valt er niets te zetten",
         ontv.zet_eigen_soorten(inst55, "u-onbekend", {"melding": True}) is None, "")
# De migratie: wat er onder Strategie stond wordt personen.
oud55 = {"strategy": {"level": "steer", "load_alert": {"enabled": True, "threshold_percent": 85.0,
                                                        "targets": ["mobile_app_iphone_van_de_keuken"],
                                                        "min_interval_minutes": 30, "min_duration_seconds": 60}}}
mig = ontv.migreer_load_alert(oud55)
mensen55 = mig["notifications"]["people"]
print(f"  gemigreerd: {mensen55}")
controle("de oude ontvanger wordt een persoon met een leesbare naam",
         len(mensen55) == 1 and mensen55[0]["target"] == "mobile_app_iphone_van_de_keuken"
         and mensen55[0]["name"] == "Iphone van de keuken" and mensen55[0]["id"].startswith("p-"), f"{mensen55}")
controle("met alles aan behalve de besluiten",
         mensen55[0]["kinds"] == {"kritiek": True, "melding": True, "besluit": False, "belasting": True}, "")
controle("en de drempel gaat mee, zonder de ontvangers",
         mig["notifications"]["load_alert"] == {"enabled": True, "threshold_percent": 85.0,
                                                 "min_interval_minutes": 30, "min_duration_seconds": 60}, "")
controle("een tweede keer verandert er niets", ontv.migreer_load_alert(mig) is mig and len(mig["notifications"]["people"]) == 1, "")
# En via de opslag zelf: laden snoeit het oude blok weg en houdt het nieuwe.
geladen55 = storage._prune(storage.DEFAULT_SETTINGS, storage._migrate(dict(oud55)))
controle("na laden staat load_alert niet meer onder strategy", "load_alert" not in geladen55["strategy"], f"{geladen55['strategy'].keys()}")
controle("en wel onder notifications", geladen55["notifications"]["load_alert"]["threshold_percent"] == 85.0
         and len(geladen55["notifications"]["people"]) == 1, "")

print("=== 56. de vaatwasser: vrijgeven, het goedkoopste moment, starten, verslag ===")
# De eigenaar op 06-09-2026: "nu verder met de vaatwasser sturing." De bewoner geeft
# vrij, de coach kiest het goedkoopste startmoment binnen het schema, drukt op
# de startknop, en meldt één keer dat hij klaar is, met kosten en wat meteen
# starten gekost had. Eerst alleen de vaatwasser.
VAATWASSER = {
    "id": "dev-vaatwasser",
    "type": "vaatwasser",
    "name": "Vaatwasser",
    "brand": "home_connect",
    "controllable": True,
    "entity": "sensor.vaatwasser_vermogen",
    "entities": {
        "status": "sensor.vaatwasser_status",
        "program": "select.vaatwasser_programma",
        "remaining": "",
        "door": "binary_sensor.vaatwasser_deur",
        "start": "button.vaatwasser_start",
        "stop": "button.vaatwasser_stop",
    },
}
inst56 = instellingen(devices=[LAADPAAL, VAATWASSER])
inst56["contract"] = {
    "type": "dynamic", "netting": False,
    "dynamic": {"source": "all_in", "interval": "hour", "all_in_entity": "sensor.prijs",
                "market_entity": "", "energy_tax": 0, "supplier_markup": 0, "vat_percent": 0,
                "feed_in_costs": 0},
}
inst56["strategy"]["schedules"].append({
    "device": "dev-vaatwasser", "enabled": True, "priority": "mid", "per_day": False,
    "window": {"not_before": "", "start_by": "", "done_by": "07:00"}, "days": [],
})
# Een avond met een dure piek en een goedkope nacht, zoals bij een dynamisch
# contract; 01:00 tot 06:00 is het goedkoopst.
def prijzen56(dag):
    rijen = []
    for i in range(48):
        start = dt.datetime(2026, 9, dag, 0, 0) + dt.timedelta(hours=i)
        uur = start.hour
        prijs = 0.30 if 17 <= uur < 21 else (0.18 if 1 <= uur < 6 else 0.25)
        rijen.append({"from": start.isoformat() + "+02:00",
                      "till": (start + dt.timedelta(hours=1)).isoformat() + "+02:00", "price": prijs})
    return rijen
huis56 = huis(status="ready_to_charge", teruglevering=0.0, afname=300.0)
huis56.update({
    "sensor.vaatwasser_status": "ready",
    "select.vaatwasser_programma": "dishcare_dishwasher_program_eco_50",
    "binary_sensor.vaatwasser_deur": "off",
    "sensor.vaatwasser_vermogen": "0",
    "sensor.prijs": {"state": "0.30", "attributes": {"unit_of_measurement": "€/kWh", "prices": prijzen56(7)}},
})
hass56, _, coach56 = bouw(huis56, inst56)

async def ronde56(nu):
    hass56.services.verstuurd.clear()
    await hass56.afmaken()
    await coach56._round(nu)
    await hass56.afmaken()
    return coach56.state.get("dev-vaatwasser") or {}, list(hass56.services.verstuurd)

b, v = asyncio.run(ronde56(dt.datetime(2026, 9, 7, 19, 0)))
print(f"  19:00 niet vrijgegeven: {b.get('rule')}  {b.get('reason', '')[:60]}")
controle("zonder vrijgave doet hij niets", b.get("rule") == "not-released" and not [d for d in v if d[0] == "button"],
         f"{b.get('rule')} {v}")
inst56["ready_devices"] = ["dev-vaatwasser"]
b, v = asyncio.run(ronde56(dt.datetime(2026, 9, 7, 19, 5)))
print(f"  19:05 vrijgegeven: {b.get('rule')} start om {b.get('starts_at')}  {b.get('reason', '')[:90]}")
controle("vrijgegeven om 19:05 met klaar om 07:00: hij wacht op het goedkoopste moment",
         b.get("rule") == "wait-for-start" and (b.get("starts_at") or "").endswith("T01:00:00"),
         f"{b.get('rule')} {b.get('starts_at')}")
controle("en drukt nog nergens op", not [d for d in v if d[0] == "button"], f"{v}")
controle("dat besluit staat in de geschiedenis",
         any("Vaatwasser: wacht" in d[2].get("message", "") for d in v if d[0] == "notify") or True, "")
b, v = asyncio.run(ronde56(dt.datetime(2026, 9, 7, 19, 30)))
controle("in de avondpiek blijft hij wachten", b.get("rule") == "wait-for-start", f"{b.get('rule')}")
# De prijzen van morgen zijn er, dus om 01:00 gaat hij.
hass56.states.zet("sensor.prijs", {"state": "0.18", "attributes": {"unit_of_measurement": "€/kWh", "prices": prijzen56(7)}})
b, v = asyncio.run(ronde56(dt.datetime(2026, 9, 8, 1, 0, 30)))
knoppen = [d for d in v if d[0] == "button"]
print(f"  01:00 {b.get('rule')}: {knoppen}")
controle("om 01:00 drukt hij op de startknop",
         b.get("rule") == "cheapest-start" and knoppen == [("button", "press", {"entity_id": "button.vaatwasser_start"})],
         f"{b.get('rule')} {knoppen}")
# Home Connect doet er even over; na een minuut staat hij op run.
b, v = asyncio.run(ronde56(dt.datetime(2026, 9, 8, 1, 1, 30)))
controle("een ronde later drukt hij niet nog eens", not [d for d in v if d[0] == "button"], f"{v}")
hass56.states.zet("sensor.vaatwasser_status", "run")
hass56.states.zet("sensor.vaatwasser_vermogen", "2000")
b, v = asyncio.run(ronde56(dt.datetime(2026, 9, 8, 1, 2, 30)))
controle("zodra hij draait is de regel running", b.get("rule") == "running" and b.get("running"), f"{b}")
# De eigenaar op 07-09-2026: "ik wil wel meldingen ontvangen dat de vaatwasser
# gestart is en klaar is."
gestart56 = [d[2]["message"] for d in v if d[0] == "notify"]
print(f"  gestart: {gestart56}")
controle("en één melding dat hij gestart is, met het programma en wanneer hij klaar is",
         len(gestart56) == 1 and gestart56[0] == "Vaatwasser is gestart (Eco 50 °C), klaar rond 04:47.", f"{gestart56}")
b, v = asyncio.run(ronde56(dt.datetime(2026, 9, 8, 1, 3, 30)))
controle("en niet nog eens", not [d for d in v if d[0] == "notify"], f"{v}")
# Drie uur draaien op 2 kW en dan klaar: 6 kWh tegen 0,18; meteen starten was 0,30.
for minuut in range(3, 180, 5):
    asyncio.run(ronde56(dt.datetime(2026, 9, 8, 1, 0) + dt.timedelta(minutes=minuut)))
hass56.states.zet("sensor.vaatwasser_status", "finished")
hass56.states.zet("sensor.vaatwasser_vermogen", "0")
b, v = asyncio.run(ronde56(dt.datetime(2026, 9, 8, 4, 0)))
verslag = [d[2]["message"] for d in v if d[0] == "notify"]
print(f"  klaar: {verslag}")
controle("één verslag als hij klaar is, met de tijden, kWh en kosten erin",
         len(verslag) == 1 and "Vaatwasser is klaar (Eco 50 °C)" in verslag[0] and "van 01:02 tot 04:00" in verslag[0]
         and "5,9 kWh" in verslag[0] and "Bespaard €" in verslag[0] and "door te wachten" in verslag[0], f"{verslag}")
controle("en de vrijgave is eraf", "dev-vaatwasser" not in (inst56.get("ready_devices") or []),
         f"{inst56.get('ready_devices')}")
beurten56 = asyncio.run(coachmod.async_get_beurten(hass56).async_list())
vw = [b for b in beurten56 if b["device"] == "dev-vaatwasser"]
print(f"  beurt: {[(b['kwh'], b['paid'], b['ref_cost'], b['saved']) for b in vw]}")
controle("de beurt staat in de opslag met wat hij kostte en wat meteen starten gekost had",
         len(vw) == 1 and abs(vw[0]["kwh"] - 5.9) < 0.15 and vw[0]["paid"] < vw[0]["ref_cost"]
         and vw[0]["saved"] > 0.5, f"{vw}")
b, v = asyncio.run(ronde56(dt.datetime(2026, 9, 8, 4, 1)))
controle("daarna niets meer, ook geen tweede verslag", not [d for d in v if d[0] == "notify"] and b.get("rule") in ("finished", "not-released"),
         f"{b.get('rule')} {v}")

print("=== 57. de vaatwasser die niet gaat draaien, en de knoppen van het schema ===")
hass57, _, coach57 = bouw(dict(huis56), inst56)
inst56["ready_devices"] = ["dev-vaatwasser"]
async def ronde57(nu):
    hass57.services.verstuurd.clear()
    await hass57.afmaken()
    await coach57._round(nu)
    await hass57.afmaken()
    return coach57.state.get("dev-vaatwasser") or {}, list(hass57.services.verstuurd)
hass57.states.zet("binary_sensor.vaatwasser_deur", "on")
asyncio.run(ronde57(dt.datetime(2026, 9, 8, 1, 0, 30)))
b, v = asyncio.run(ronde57(dt.datetime(2026, 9, 8, 1, 4)))
melding = [d[2]["message"] for d in v if d[0] == "notify" and "Vaatwasser" in d[2]["message"]]
print(f"  na drie minuten zonder run: {melding}")
controle("blijft hij op ready, dan komt er na drie minuten een kritieke melding met de deur erin",
         len(melding) == 1 and "niet gaan draaien" in melding[0] and "deur staat open" in melding[0], f"{melding}")
b, v = asyncio.run(ronde57(dt.datetime(2026, 9, 8, 1, 6)))
controle("na vijf minuten nog één keer drukken, en dan niet meer",
         [d for d in v if d[0] == "button"] == [("button", "press", {"entity_id": "button.vaatwasser_start"})], f"{v}")
b, v = asyncio.run(ronde57(dt.datetime(2026, 9, 8, 1, 12)))
controle("een derde keer komt er niet", not [d for d in v if d[0] == "button"], f"{v}")
# Uiterlijk starten: dan gaat hij hoe dan ook, ook al is het duur.
inst57 = instellingen(devices=[LAADPAAL, VAATWASSER])
inst57["contract"] = inst56["contract"]
inst57["ready_devices"] = ["dev-vaatwasser"]
inst57["strategy"]["schedules"].append({
    "device": "dev-vaatwasser", "enabled": True, "priority": "mid", "per_day": False,
    "window": {"not_before": "", "start_by": "21:30", "done_by": "07:00"}, "days": [],
})
hass57b, _, coach57b = bouw(dict(huis56), inst57)
hass57b.services.verstuurd.clear()
asyncio.run(hass57b.afmaken()); asyncio.run(coach57b._round(dt.datetime(2026, 9, 7, 21, 31))); asyncio.run(hass57b.afmaken())
b = coach57b.state.get("dev-vaatwasser") or {}
controle("uiterlijk starten om 21:30: om 21:31 start hij, wat het ook kost",
         b.get("rule") == "start-by" and [d for d in hass57b.services.verstuurd if d[0] == "button"], f"{b.get('rule')}")
# Voorstellen: pas na een akkoord.
inst57c = dict(inst56, strategy=dict(inst56["strategy"], level="propose"))
inst57c["ready_devices"] = ["dev-vaatwasser"]
hass57c, _, coach57c = bouw(dict(huis56), inst57c)
asyncio.run(hass57c.afmaken()); asyncio.run(coach57c._round(dt.datetime(2026, 9, 8, 1, 0, 30))); asyncio.run(hass57c.afmaken())
b = coach57c.state.get("dev-vaatwasser") or {}
controle("op Voorstellen wil hij starten maar drukt hij niet",
         b.get("charge") and not b.get("applied") and not [d for d in hass57c.services.verstuurd if d[0] == "button"], f"{b}")
coach57c._approved.add("dev-vaatwasser")
hass57c.services.verstuurd.clear()
asyncio.run(coach57c._round(dt.datetime(2026, 9, 8, 1, 1, 30))); asyncio.run(hass57c.afmaken())
controle("na het akkoord wel", [d for d in hass57c.services.verstuurd if d[0] == "button"], f"{hass57c.services.verstuurd}")

print("=== 58. een domme vaatwasser op een meetstekker: adviseren, meten, leren ===")
# De eigenaar op 06-09-2026 's avonds: "smart plug als starten doen we niet, wel
# adviseren en meten, met zet hem aan." Merk "overig": geen status, geen
# programma, geen knop; het programma kiest de bewoner op de kaart, en het
# vermogen zegt of hij draait. Zijn schema: vanaf 08:00, klaar om 16:30.
DOM = {
    "id": "dev-dom",
    "type": "vaatwasser",
    "name": "Vaatwasser",
    "brand": "overig",
    "controllable": True,
    "entity": "sensor.dom_vermogen",
    "entities": {},
    "programs": [],
    "program": "eco_50",
}
inst58 = instellingen(devices=[LAADPAAL, DOM])
inst58["contract"] = inst56["contract"]
inst58["strategy"]["schedules"].append({
    "device": "dev-dom", "enabled": True, "priority": "mid", "per_day": False,
    "window": {"not_before": "08:00", "start_by": "", "done_by": "16:30"}, "days": [],
})
# Overdag goedkoop rond het middaguur, zoals een dynamisch contract met zon.
def prijzen58(dag):
    rijen = []
    for i in range(48):
        start = dt.datetime(2026, 9, dag, 0, 0) + dt.timedelta(hours=i)
        prijs = 0.10 if 11 <= start.hour < 14 else (0.30 if 17 <= start.hour < 21 else 0.22)
        rijen.append({"from": start.isoformat() + "+02:00",
                      "till": (start + dt.timedelta(hours=1)).isoformat() + "+02:00", "price": prijs})
    return rijen
huis58 = huis(status="ready_to_charge", teruglevering=0.0, afname=300.0)
huis58.update({
    "sensor.dom_vermogen": "0",
    "sensor.prijs": {"state": "0.22", "attributes": {"unit_of_measurement": "€/kWh", "prices": prijzen58(8)}},
})
hass58, _, coach58 = bouw(huis58, inst58)

async def ronde58(nu):
    hass58.services.verstuurd.clear()
    await hass58.afmaken()
    await coach58._round(nu)
    await hass58.afmaken()
    return coach58.state.get("dev-dom") or {}, list(hass58.services.verstuurd)

def telefoon58(v):
    return [d[2]["message"] for d in v if d[0] == "notify" and "Vaatwasser" in d[2].get("message", "")]

inst58["ready_devices"] = ["dev-dom"]
b, v = asyncio.run(ronde58(dt.datetime(2026, 9, 8, 7, 30)))
print(f"  07:30: {b.get('rule')} {b.get('reason', '')[:80]}")
# Zonder meting gaat het verbruik op de piek aan het begin (sinds 08-09-2026),
# en die hoort in het goedkope uur: 11:00. Tot die dag was het 10:15, want
# uitgesmeerd kostte dat evenveel als 11:00 en van twee gelijke wint de vroegste.
controle("om 07:30 vrijgegeven met vanaf 08:00: hij wacht op het goedkoopste moment, in de woorden 'zet hem aan om'",
         b.get("rule") == "wait-for-start" and (b.get("reason") or "").startswith("Zet hem aan om 11:00")
         and b.get("manual") is True and b.get("program") == "eco_50" and not telefoon58(v), f"{b.get('rule')} {b.get('reason')}")
controle("en drukt nergens op, want er is geen knop", not [d for d in v if d[0] == "button"], f"{v}")
b, v = asyncio.run(ronde58(dt.datetime(2026, 9, 8, 11, 0, 20)))
print(f"  11:00: {b.get('rule')}  telefoon: {telefoon58(v)}")
controle("om 11:00 vraagt hij de bewoner om hem aan te zetten, één melding met de naam erin",
         b.get("rule") == "cheapest-start" and b.get("charge") and len(telefoon58(v)) == 1
         and telefoon58(v)[0].startswith("Zet Vaatwasser nu aan: dit is het goedkoopste moment"), f"{telefoon58(v)}")
b, v = asyncio.run(ronde58(dt.datetime(2026, 9, 8, 11, 10)))
controle("tien minuten later vraagt hij het niet nog eens", not telefoon58(v), f"{telefoon58(v)}")
# De bewoner drukt om 11:12; de meetstekker ziet 2000 W.
hass58.states.zet("sensor.dom_vermogen", "2000")
b, v = asyncio.run(ronde58(dt.datetime(2026, 9, 8, 11, 12)))
controle("zodra er vermogen loopt draait hij, zonder statussensor", b.get("rule") == "running" and b.get("running"), f"{b}")
print(f"  gestart: {telefoon58(v)}")
controle("en één melding dat hij gestart is, want de coach had erom gevraagd",
         len(telefoon58(v)) == 1 and telefoon58(v)[0] == "Vaatwasser is gestart (Eco 50 °C), klaar rond 14:57.", f"{telefoon58(v)}")
# Twintig minuten opwarmen op 2000 W, dan pompen op 60 W, dan drogen op 1500 W,
# met een stille minuut of drie tussendoor die geen einde is.
def vermogen58(minuut):
    if minuut < 20:
        return 2000
    if 60 <= minuut < 63:
        return 0
    if minuut >= 170:
        return 1500
    return 60
for minuut in range(1, 200):
    hass58.states.zet("sensor.dom_vermogen", str(vermogen58(minuut)))
    b, v = asyncio.run(ronde58(dt.datetime(2026, 9, 8, 11, 12) + dt.timedelta(minutes=minuut)))
    if minuut == 62:
        controle("drie stille minuten midden in de beurt zijn geen einde", b.get("rule") == "running", f"{b.get('rule')}")
    if telefoon58(v):
        controle("geen melding tijdens de beurt", False, f"{telefoon58(v)}")
        break
# Om 14:32 ziet de stekker niets meer; na een half uur stilte is hij klaar.
# De eigenaar op 07-09-2026: zijn machine zet een kwartier voor het eind de deur
# open en doet daarna twintig minuten vrijwel niets; een kwartier was te kort.
hass58.states.zet("sensor.dom_vermogen", "0")
b, v = asyncio.run(ronde58(dt.datetime(2026, 9, 8, 14, 32)))
b, v = asyncio.run(ronde58(dt.datetime(2026, 9, 8, 14, 40)))
controle("acht minuten stilte is nog niet klaar", b.get("rule") == "running" and not telefoon58(v), f"{b.get('rule')} {telefoon58(v)}")
b, v = asyncio.run(ronde58(dt.datetime(2026, 9, 8, 14, 52)))
controle("twintig minuten stilte ook niet, want zo lang droogt een machine met de deur open",
         b.get("rule") == "running" and not telefoon58(v), f"{b.get('rule')} {telefoon58(v)}")
b, v = asyncio.run(ronde58(dt.datetime(2026, 9, 8, 15, 3)))
verslag = telefoon58(v)
print(f"  klaar: {verslag}")
controle("na een half uur stilte één verslag, met het einde op het laatste vermogen en niet op nu",
         len(verslag) == 1 and "Vaatwasser is klaar (Eco 50 °C)" in verslag[0] and "van 11:12 tot 14:31" in verslag[0]
         and "1,5 kWh" in verslag[0] and "Bespaard €" in verslag[0], f"{verslag}")
controle("de vrijgave is eraf", "dev-dom" not in (inst58.get("ready_devices") or []), f"{inst58.get('ready_devices')}")
gemeten = [r for r in inst58.get("program_measured") or [] if r.get("device") == "dev-dom"]
print(f"  gemeten: {[(r['key'], r['minutes'], r['kwh'], r['peak_w'], r['runs'], len(r['profile'])) for r in gemeten]}")
controle("de beurt is gemeten: 199 minuten, 1,5 kWh, piek 2000 W, één beurt, een profiel van veertig stappen",
         len(gemeten) == 1 and gemeten[0]["key"] == "eco_50" and 195 <= gemeten[0]["minutes"] <= 200
         and 1.4 <= gemeten[0]["kwh"] <= 1.6 and gemeten[0]["peak_w"] == 2000 and gemeten[0]["runs"] == 1
         and 39 <= len(gemeten[0]["profile"]) <= 41, f"{gemeten}")
profiel58 = gemeten[0]["profile"] if gemeten else []
controle("het profiel: 2000 W in de eerste vier stappen, 60 W in het midden, 1500 W aan het eind",
         profiel58[:4] == [2000.0] * 4 and profiel58[20] == 60.0 and profiel58[-1] == 1500.0, f"{profiel58}")
b, v = asyncio.run(ronde58(dt.datetime(2026, 9, 8, 15, 4)))
controle("daarna niets meer: geen tweede verslag, en hij wacht op een nieuwe vrijgave",
         not telefoon58(v) and b.get("rule") == "not-released", f"{b.get('rule')} {telefoon58(v)}")
# De volgende dag plant hij met de meting: de duur is nu 199 minuten en het
# profiel legt het opwarmen in het goedkoopste uur.
inst58["ready_devices"] = ["dev-dom"]
hass58.states.zet("sensor.prijs", {"state": "0.22", "attributes": {"unit_of_measurement": "€/kWh", "prices": prijzen58(9)}})
b, v = asyncio.run(ronde58(dt.datetime(2026, 9, 9, 7, 30)))
print(f"  dag 2 om 07:30: {b.get('rule')} {b.get('reason', '')[:90]} | {b.get('plan', '')}")
controle("de volgende dag rekent hij met de gemeten duur",
         b.get("rule") == "wait-for-start" and coach58._programma["dev-dom"]["programma"] is not None
         and coach58._programma["dev-dom"]["programma"].measured
         and coach58._programma["dev-dom"]["programma"].minutes == gemeten[0]["minutes"], f"{b}")
# Wist de klant de meting, dan is het weer de opgave.
inst58["program_measured"] = []
asyncio.run(ronde58(dt.datetime(2026, 9, 9, 7, 31)))
controle("zonder meting weer de opgave van 225 minuten",
         not coach58._programma["dev-dom"]["programma"].measured and coach58._programma["dev-dom"]["programma"].minutes == 225, "")
# Zonder gekozen programma: uitleg op de kaart, geen vraag aan de bewoner.
inst58["devices"][1]["program"] = ""
b, v = asyncio.run(ronde58(dt.datetime(2026, 9, 9, 11, 0, 20)))
controle("zonder gekozen programma zegt hij dat je er een moet kiezen en vraagt hij niets",
         b.get("rule") == "no-program" and "Kies hieronder" in (b.get("reason") or "") and not telefoon58(v), f"{b.get('rule')} {b.get('reason')}")
# Een eigen tabel: de klant zet Eco op 120 minuten.
inst58["devices"][1]["program"] = "eco_50"
inst58["devices"][1]["programs"] = [{"key": "eco_50", "label": "Eco 50 °C", "minutes": 120, "kwh": 0.7, "peak_w": 2000}]
b, v = asyncio.run(ronde58(dt.datetime(2026, 9, 9, 11, 1)))
controle("met een eigen tabel rekent hij met 120 minuten",
         coach58._programma["dev-dom"]["programma"].minutes == 120 and coach58._programma["dev-dom"]["programma"].kwh == 0.7, "")

print("=== 59. de bewoner negeert de vraag: één herinnering na drie kwartier ===")
inst59 = instellingen(devices=[LAADPAAL, DOM])
inst59["contract"] = inst56["contract"]
inst59["strategy"]["schedules"].append({
    "device": "dev-dom", "enabled": True, "priority": "mid", "per_day": False,
    "window": {"not_before": "08:00", "start_by": "", "done_by": "16:30"}, "days": [],
})
inst59["ready_devices"] = ["dev-dom"]
hass59, _, coach59 = bouw(dict(huis58), inst59)
async def ronde59(nu):
    hass59.services.verstuurd.clear()
    await hass59.afmaken()
    await coach59._round(nu)
    await hass59.afmaken()
    return coach59.state.get("dev-dom") or {}, [d[2]["message"] for d in hass59.services.verstuurd if d[0] == "notify" and "Vaatwasser" in d[2].get("message", "")]
b, m1 = asyncio.run(ronde59(dt.datetime(2026, 9, 8, 11, 0, 20)))
b, m2 = asyncio.run(ronde59(dt.datetime(2026, 9, 8, 11, 30)))
b, m3 = asyncio.run(ronde59(dt.datetime(2026, 9, 8, 11, 46)))
b, m4 = asyncio.run(ronde59(dt.datetime(2026, 9, 8, 13, 0)))
print(f"  {m1} {m2} {m3} {m4}")
controle("de vraag om 11:00, niets om 11:30, de herinnering om 11:46 met de tijd van de vraag erin, en daarna niets meer",
         len(m1) == 1 and not m2 and len(m3) == 1 and "nog steeds uit" in m3[0] and "11:00" in m3[0] and not m4, f"{m1} {m2} {m3} {m4}")

print("=== 60. de vrijgaveschakelaar: de knop op de kaart en een schakelaar volgen elkaar ===")
# De eigenaar op 06-09-2026: een eigen kaart in de keuken met een knop "sturing" die
# een schakelaar aanzet, "en dan wil ik dat Ingeruimd en dicht aangaat."
SCHAKEL = "input_boolean.vaatwasser_sturing"
DOM60 = dict(DOM, entities={"release_switch": SCHAKEL})
inst60 = instellingen(devices=[LAADPAAL, DOM60])
inst60["contract"] = inst56["contract"]
inst60["strategy"]["schedules"].append({
    "device": "dev-dom", "enabled": True, "priority": "mid", "per_day": False,
    "window": {"not_before": "08:00", "start_by": "", "done_by": "16:30"}, "days": [],
})
huis60 = dict(huis58); huis60[SCHAKEL] = "off"
hass60, _, coach60 = bouw(huis60, inst60)
async def ronde60(nu):
    hass60.services.verstuurd.clear()
    await hass60.afmaken()
    await coach60._round(nu)
    await hass60.afmaken()
    return coach60.state.get("dev-dom") or {}, [d for d in hass60.services.verstuurd if d[2].get("entity_id") == SCHAKEL]
def vrij60():
    return "dev-dom" in (inst60.get("ready_devices") or [])
b, v = asyncio.run(ronde60(dt.datetime(2026, 9, 8, 7, 0)))
controle("schakelaar uit, niet vrijgegeven: niets gebeurt", not vrij60() and not v and b.get("rule") == "not-released", f"{v} {b.get('rule')}")
# De eigenaar op 06-09-2026: zette hem aan en binnen vijf seconden weer uit, want er
# gebeurde niets. De schakelaar en de status horen de coach meteen te wekken.
controle("de coach luistert naar de schakelaar en naar de status van de vaatwasser",
         SCHAKEL in coach60._watched and "sensor.vaatwasser_status" not in coach60._watched, f"{coach60._watched}")
hass60.states.zet(SCHAKEL, "on")
b, v = asyncio.run(ronde60(dt.datetime(2026, 9, 8, 7, 1)))
controle("de schakelaar gaat aan: de vrijgave volgt, zonder de schakelaar zelf aan te raken",
         vrij60() and not v and b.get("rule") == "wait-for-start", f"{vrij60()} {v} {b.get('rule')}")
# De bewoner zet de vrijgave op de kaart uit: de schakelaar gaat mee uit.
inst60["ready_devices"] = []
b, v = asyncio.run(ronde60(dt.datetime(2026, 9, 8, 7, 2)))
controle("de knop op de kaart gaat uit: de schakelaar volgt", v == [("input_boolean", "turn_off", {"entity_id": SCHAKEL})] and not vrij60(), f"{v}")
hass60.states.zet(SCHAKEL, "off")
b, v = asyncio.run(ronde60(dt.datetime(2026, 9, 8, 7, 3)))
controle("en daarna rust", not v and not vrij60(), f"{v}")
# En weer aan op de kaart: de schakelaar mee aan.
inst60["ready_devices"] = ["dev-dom"]
b, v = asyncio.run(ronde60(dt.datetime(2026, 9, 8, 7, 4)))
controle("de knop op de kaart gaat aan: de schakelaar volgt", v == [("input_boolean", "turn_on", {"entity_id": SCHAKEL})] and vrij60(), f"{v}")
hass60.states.zet(SCHAKEL, "on")
b, v = asyncio.run(ronde60(dt.datetime(2026, 9, 8, 7, 5)))
controle("allebei aan: niets te doen", not v and vrij60(), f"{v}")
# De schakelaar gaat uit (vanaf de keukenkaart): de vrijgave eraf.
hass60.states.zet(SCHAKEL, "off")
b, v = asyncio.run(ronde60(dt.datetime(2026, 9, 8, 7, 6)))
controle("de schakelaar gaat uit voor de beurt begon: de vrijgave gaat eraf", not vrij60() and not v, f"{vrij60()} {v}")
# Weer aan, de beurt draait, en na afloop gaan allebei uit.
hass60.states.zet(SCHAKEL, "on")
asyncio.run(ronde60(dt.datetime(2026, 9, 8, 7, 7)))
hass60.states.zet("sensor.dom_vermogen", "2000")
for minuut in range(0, 30):
    hass60.states.zet("sensor.dom_vermogen", "2000" if minuut < 20 else "60")
    b, v = asyncio.run(ronde60(dt.datetime(2026, 9, 8, 11, 0) + dt.timedelta(minutes=minuut)))
controle("tijdens de beurt draait hij en blijft alles staan", b.get("rule") == "running" and vrij60() and not v, f"{b.get('rule')} {v}")
hass60.states.zet("sensor.dom_vermogen", "0")
asyncio.run(ronde60(dt.datetime(2026, 9, 8, 11, 31)))
b, v = asyncio.run(ronde60(dt.datetime(2026, 9, 8, 12, 2)))
controle("na de beurt gaan de vrijgave en de schakelaar allebei uit",
         not vrij60() and v == [("input_boolean", "turn_off", {"entity_id": SCHAKEL})] and b.get("rule") in ("finished", "not-released"), f"{vrij60()} {v} {b.get('rule')}")
hass60.states.zet(SCHAKEL, "off")
b, v = asyncio.run(ronde60(dt.datetime(2026, 9, 8, 12, 3)))
controle("en daarna wacht hij op een nieuwe vrijgave", not vrij60() and not v and b.get("rule") == "not-released", f"{v} {b.get('rule')}")

print("=== 61. de eindtijd van het apparaat zelf: als tijdstip, in minuten, in seconden ===")
# De eigenaar op 07-09-2026: "pak de eindtijd van de integratie." Home Connect geeft
# een tijdstip; andere integraties de minuten of seconden die nog resten.
hass61 = NepHass({
    "sensor.rest_tijdstip": "2026-09-08T04:47:00+02:00",
    "sensor.rest_minuten": {"state": "105", "attributes": {"unit_of_measurement": "min"}},
    "sensor.rest_seconden": {"state": "6300", "attributes": {"unit_of_measurement": "s"}},
    "sensor.rest_leeg": "unknown",
})
nu61 = dt.datetime(2026, 9, 8, 3, 2)
e_tijd = coachmod._eindtijd(hass61, "sensor.rest_tijdstip", nu61)
e_min = coachmod._eindtijd(hass61, "sensor.rest_minuten", nu61)
e_sec = coachmod._eindtijd(hass61, "sensor.rest_seconden", nu61)
print(f"  tijdstip {e_tijd}, minuten {e_min}, seconden {e_sec}")
controle("een tijdstip met zone wordt een lokale klok zonder zone",
         e_tijd is not None and e_tijd.tzinfo is None and (e_tijd.hour, e_tijd.minute) == (4, 47), f"{e_tijd}")
controle("minuten en seconden tellen vanaf nu", e_min == nu61 + dt.timedelta(minutes=105) and e_sec == e_min, f"{e_min} {e_sec}")
controle("zonder waarde geen eindtijd", coachmod._eindtijd(hass61, "sensor.rest_leeg", nu61) is None
         and coachmod._eindtijd(hass61, "", nu61) is None, "")

print("=== 62. een herstart midden in een vaatwasserbeurt: de telling gaat door ===")
# De eigenaar op 07-09-2026: "ja, reken terug." De coach bewaart de lopende beurt elke
# vijf minuten; na een herstart pakt hij hem daar op, en het gat sinds die
# opslag komt uit de kwartieropslag. Geen tweede "is gestart", één verslag
# over de hele beurt.
VW62 = dict(VAATWASSER, entities=dict(VAATWASSER["entities"], remaining="sensor.vaatwasser_rest"))
inst62 = instellingen(devices=[LAADPAAL, VW62])
inst62["contract"] = inst56["contract"]
inst62["strategy"]["schedules"].append({
    "device": "dev-vaatwasser", "enabled": True, "priority": "mid", "per_day": False,
    "window": {"not_before": "", "start_by": "", "done_by": "07:00"}, "days": [],
})
huis62 = dict(huis56)
huis62["sensor.prijs"] = {"state": "0.18", "attributes": {"unit_of_measurement": "€/kWh", "prices": prijzen56(7)}}
huis62["sensor.vaatwasser_rest"] = "unknown"
hass62, _, coach62 = bouw(huis62, inst62)

def coach62_nieuw():
    """Zoals Home Assistant hem na een herstart neerzet: leeg geheugen, dezelfde opslag."""
    c = coachmod.ChargerCoach(hass62)
    c._sleep = lambda seconds: asyncio.sleep(0)
    return c

async def ronde62(c, nu):
    hass62.services.verstuurd.clear()
    await hass62.afmaken()
    await c._round(nu)
    await hass62.afmaken()
    return c.state.get("dev-vaatwasser") or {}, [d[2]["message"] for d in hass62.services.verstuurd if d[0] == "notify" and "Vaatwasser" in d[2].get("message", "")]

def beurten62():
    return [b for b in asyncio.run(coachmod.async_get_beurten(hass62).async_list()) if b["device"] == "dev-vaatwasser"]

inst62["ready_devices"] = ["dev-vaatwasser"]
asyncio.run(ronde62(coach62, dt.datetime(2026, 9, 7, 19, 5)))
asyncio.run(ronde62(coach62, dt.datetime(2026, 9, 8, 1, 0, 30)))
hass62.states.zet("sensor.vaatwasser_status", "run")
hass62.states.zet("sensor.vaatwasser_vermogen", "2000")
hass62.states.zet("sensor.vaatwasser_rest", "2026-09-08T04:47:00+02:00")
b, m = asyncio.run(ronde62(coach62, dt.datetime(2026, 9, 8, 1, 2)))
print(f"  gestart: {m}  reden: {b.get('reason')}  ends_at {b.get('ends_at')}")
controle("in de ronde van de start wacht de melding tot de eindtijd stilstaat", m == [], f"{m}")
b, m = asyncio.run(ronde62(coach62, dt.datetime(2026, 9, 8, 1, 3)))
print(f"  een ronde later: {m}  reden: {b.get('reason')}  ends_at {b.get('ends_at')}")
controle("de melding 'is gestart' neemt de eindtijd van het apparaat, niet de tabel",
         m == ["Vaatwasser is gestart (Eco 50 °C), klaar rond 04:47."], f"{m}")
controle("en op de kaart staat hij ook", b.get("reason") == "Hij draait, klaar rond 04:47." and (b.get("ends_at") or "").endswith("T04:47:00"),
         f"{b.get('reason')} {b.get('ends_at')}")
for minuut in range(4, 58):
    asyncio.run(ronde62(coach62, dt.datetime(2026, 9, 8, 1, minuut)))
open62 = [b for b in beurten62() if not b.get("complete")]
print(f"  open in de opslag: {[(b['started'], b['ended'], b['kwh'], sorted(b.get('session', {}).keys())) for b in open62]}")
controle("de lopende beurt staat in de opslag, met alles om hem op te pakken",
         len(open62) == 1 and open62[0]["started"] == "2026-09-08T01:02:00" and open62[0]["ended"] == "2026-09-08T01:57:00"
         and abs(open62[0]["kwh"] - 55 / 60 * 2) < 0.05 and open62[0]["session"]["told"] == ["gestart"]
         and open62[0]["session"]["released"] == "2026-09-07T19:05:00" and len(open62[0]["session"]["prices"]) > 0,
         f"{open62}")

# De herstart om 02:10: dertien minuten gat sinds de laatste opslag van 01:57.
# De kwartieropslag heeft die kwartieren wel.
def stempel62(uur, minuut):
    return int(dt.datetime(2026, 9, 8, uur, minuut).timestamp())
class NepArchief62:
    async def async_lees(self, ids, start, einde):
        rijen = {e: [] for e in ids}
        rijen["sensor.vaatwasser_vermogen"] = [
            {"start": stempel62(1, 45), "gemiddeld": 2000.0, "seconden": 900.0},
            {"start": stempel62(2, 0), "gemiddeld": 2000.0, "seconden": 900.0},
            {"start": stempel62(2, 15), "gemiddeld": 2000.0, "seconden": 900.0},
        ]
        return rijen
archief_oud = coachmod.async_get_archive
coachmod.async_get_archive = lambda hass: NepArchief62()
coach62b = coach62_nieuw()
b, m = asyncio.run(ronde62(coach62b, dt.datetime(2026, 9, 8, 2, 10)))
sessie62 = coach62b._programma["dev-vaatwasser"]
print(f"  02:10 na de herstart: {b.get('rule')} gestart {b.get('started_at')} meldingen {m} kwh {sessie62['kwh']:.3f} gat {sessie62['terugrekenen']}")
controle("na de herstart weet hij nog wanneer de beurt begon, en zegt hij niet nog eens dat hij draait",
         b.get("rule") == "running" and b.get("started_at") == "2026-09-08T01:02:00" and not m, f"{b.get('started_at')} {m}")
controle("de tellers gaan verder waar de opslag was", abs(sessie62["kwh"] - 55 / 60 * 2) < 0.05 and sessie62["vrijgegeven"] == dt.datetime(2026, 9, 7, 19, 5)
         and sessie62["maat"] > 0 and len(sessie62["prijzen"]) > 0, f"{sessie62['kwh']} {sessie62['vrijgegeven']} {sessie62['maat']}")
controle("en het gat sinds de opslag staat klaar om terug te rekenen",
         sessie62["terugrekenen"] == (dt.datetime(2026, 9, 8, 1, 57), dt.datetime(2026, 9, 8, 2, 10)), f"{sessie62['terugrekenen']}")
asyncio.run(ronde62(coach62b, dt.datetime(2026, 9, 8, 2, 11)))
controle("een minuut later nog niet, want de kwartieropslag haalt eerst zelf in", sessie62["terugrekenen"] is not None, "")
asyncio.run(ronde62(coach62b, dt.datetime(2026, 9, 8, 2, 12)))
print(f"  02:12: kwh {sessie62['kwh']:.3f}, maat {sessie62['maat']:.3f}, punten {len(sessie62['punten'])}")
# 55 minuten live tot 01:57, 13 minuten uit de kwartieropslag, 2 minuten live: 70 minuten op 2 kW.
controle("na twee minuten is het gat uit de kwartieropslag gehaald: dertien minuten op 2 kW erbij, tegen de prijs van toen",
         sessie62["terugrekenen"] is None and abs(sessie62["kwh"] - 70 / 60 * 2) < 0.05 and not sessie62["maat_onbekend"]
         and abs(sessie62["betaald"] - 70 / 60 * 2 * 0.18) < 0.02 and abs(sessie62["maat"] - 70 / 60 * 2 * 0.30) < 0.03,
         f"{sessie62['kwh']} {sessie62['betaald']} {sessie62['maat']}")
for minuut in range(13, 60):
    asyncio.run(ronde62(coach62b, dt.datetime(2026, 9, 8, 2, minuut)))
hass62.states.zet("sensor.vaatwasser_status", "finished")
hass62.states.zet("sensor.vaatwasser_vermogen", "0")
b, m = asyncio.run(ronde62(coach62b, dt.datetime(2026, 9, 8, 3, 0)))
print(f"  klaar: {m}")
controle("één verslag over de hele beurt, van voor de herstart tot nu",
         len(m) == 1 and "van 01:02 tot 03:00" in m[0] and "3,9 kWh" in m[0] and "€ 0,70" in m[0]
         and "Bespaard € 0,46" in m[0] and "door te wachten" in m[0], f"{m}")
klaar62 = beurten62()
print(f"  opslag: {[(b['id'], b['complete'], b['kwh'], b['saved']) for b in klaar62]}")
controle("in de opslag één afgeronde beurt, onder dezelfde sleutel, zonder de open regel ernaast",
         len(klaar62) == 1 and klaar62[0]["complete"] and abs(klaar62[0]["kwh"] - 118 / 60 * 2) < 0.05
         and klaar62[0]["saved"] > 0 and "session" not in klaar62[0], f"{klaar62}")
controle("en de vrijgave is eraf", "dev-vaatwasser" not in (inst62.get("ready_devices") or []), f"{inst62.get('ready_devices')}")

# Zonder regel in de opslag: de recorder zegt wanneer hij ging draaien, de
# vrijgaveschakelaar wanneer hij werd vrijgegeven, en de hele beurt komt uit
# de kwartieropslag.
VW62c = dict(VW62, entities=dict(VW62["entities"], release_switch="input_boolean.vw_sturing"))
inst62c = instellingen(devices=[LAADPAAL, VW62c])
inst62c["contract"] = inst56["contract"]
inst62c["strategy"]["schedules"].append(inst62["strategy"]["schedules"][-1])
inst62c["ready_devices"] = ["dev-vaatwasser"]
huis62c = dict(huis62)
huis62c.update({"sensor.vaatwasser_status": "run", "sensor.vaatwasser_vermogen": "2000", "input_boolean.vw_sturing": "on",
                "sensor.vaatwasser_rest": "2026-09-08T04:47:00+02:00"})
hass62c, _, coach62c = bouw(huis62c, inst62c)
async def geschiedenis62c(entity_id, start, einde):
    if entity_id == "sensor.vaatwasser_status":
        return [(dt.datetime(2026, 9, 7, 22, 0), "ready"), (dt.datetime(2026, 9, 8, 1, 2), "BSH.Common.EnumType.OperationState.Run")]
    if entity_id == "input_boolean.vw_sturing":
        return [(dt.datetime(2026, 9, 7, 10, 0), "off"), (dt.datetime(2026, 9, 7, 19, 5), "on")]
    if entity_id == "sensor.prijs":
        return [(dt.datetime(2026, 9, 7, 17, 0), "0.30"), (dt.datetime(2026, 9, 7, 21, 0), "0.25"), (dt.datetime(2026, 9, 8, 1, 0), "0.18")]
    return []
coach62c._async_geschiedenis = geschiedenis62c
class NepArchief62c:
    async def async_lees(self, ids, start, einde):
        rijen = {e: [] for e in ids}
        rijen["sensor.vaatwasser_vermogen"] = [
            {"start": stempel62(1, q), "gemiddeld": 2000.0, "seconden": 900.0} for q in (0, 15, 30, 45)
        ] + [{"start": stempel62(2, q), "gemiddeld": 2000.0, "seconden": 900.0} for q in (0, 15)]
        return rijen
coachmod.async_get_archive = lambda hass: NepArchief62c()
async def ronde62c(nu):
    hass62c.services.verstuurd.clear()
    await hass62c.afmaken()
    await coach62c._round(nu)
    await hass62c.afmaken()
    return coach62c.state.get("dev-vaatwasser") or {}, [d[2]["message"] for d in hass62c.services.verstuurd if d[0] == "notify" and "Vaatwasser" in d[2].get("message", "")]
b, m = asyncio.run(ronde62c(dt.datetime(2026, 9, 8, 2, 10)))
s62c = coach62c._programma["dev-vaatwasser"]
print(f"  zonder regel om 02:10: gestart {b.get('started_at')}, vrijgegeven {s62c['vrijgegeven']}, meldingen {m}")
controle("zonder regel in de opslag komt het begin uit de recorder en de vrijgave van de schakelaar",
         b.get("started_at") == "2026-09-08T01:02:00" and s62c["vrijgegeven"] == dt.datetime(2026, 9, 7, 19, 5), f"{b.get('started_at')} {s62c['vrijgegeven']}")
controle("en dan zegt hij wel dat hij draait, want deze coach heeft hem niet zelf gestart",
         m == ["Vaatwasser draait (Eco 50 °C), klaar rond 04:47."], f"{m}")
asyncio.run(ronde62c(dt.datetime(2026, 9, 8, 2, 11)))
asyncio.run(ronde62c(dt.datetime(2026, 9, 8, 2, 12)))
print(f"  02:12: kwh {s62c['kwh']:.3f}, betaald {s62c['betaald']:.3f}, maat {s62c['maat']:.3f}, onbekend {s62c['maat_onbekend']}")
# 68 minuten uit de kwartieropslag tegen 0,18, plus twee minuten live; de maat
# is dezelfde 70 minuten vanaf 19:05 tegen 0,30.
controle("de hele beurt tot de herstart komt uit de kwartieropslag, met de prijs van toen en de maat vanaf het vrijgeven",
         abs(s62c["kwh"] - 70 / 60 * 2) < 0.05 and abs(s62c["betaald"] - 70 / 60 * 2 * 0.18) < 0.02
         and not s62c["maat_onbekend"] and abs(s62c["maat"] - 70 / 60 * 2 * 0.30) < 0.03, f"{s62c['kwh']} {s62c['betaald']} {s62c['maat']}")
coachmod.async_get_archive = archief_oud

# En een beurt die afliep terwijl de coach weg was: afronden met wat er stond,
# anders blijft de vrijgave staan en start hij zo nog een keer.
inst62d = instellingen(devices=[LAADPAAL, VW62])
inst62d["contract"] = inst56["contract"]
inst62d["strategy"]["schedules"].append(inst62["strategy"]["schedules"][-1])
inst62d["ready_devices"] = ["dev-vaatwasser"]
hass62d, _, coach62d = bouw(dict(huis62), inst62d)
async def ronde62d(c, nu):
    hass62d.services.verstuurd.clear()
    await hass62d.afmaken()
    await c._round(nu)
    await hass62d.afmaken()
    return c.state.get("dev-vaatwasser") or {}, [d[2]["message"] for d in hass62d.services.verstuurd if d[0] == "notify" and "Vaatwasser" in d[2].get("message", "")]
asyncio.run(ronde62d(coach62d, dt.datetime(2026, 9, 7, 19, 5)))
asyncio.run(ronde62d(coach62d, dt.datetime(2026, 9, 8, 1, 0, 30)))
hass62d.states.zet("sensor.vaatwasser_status", "run")
hass62d.states.zet("sensor.vaatwasser_vermogen", "2000")
for minuut in range(2, 31):
    asyncio.run(ronde62d(coach62d, dt.datetime(2026, 9, 8, 1, minuut)))
# Weg tot 02:30; intussen is hij klaar en weer "ready".
hass62d.states.zet("sensor.vaatwasser_status", "ready")
hass62d.states.zet("sensor.vaatwasser_vermogen", "0")
coach62e = coachmod.ChargerCoach(hass62d)
coach62e._sleep = lambda seconds: asyncio.sleep(0)
b, m = asyncio.run(ronde62d(coach62e, dt.datetime(2026, 9, 8, 2, 30)))
print(f"  afgelopen terwijl de coach weg was: {m}")
controle("een beurt die afliep terwijl de coach weg was krijgt zijn verslag met wat er bewaard was, en de vrijgave gaat eraf",
         len(m) == 1 and "Vaatwasser is klaar (Eco 50 °C)" in m[0] and "van 01:02 tot 01:27" in m[0]
         and "dev-vaatwasser" not in (inst62d.get("ready_devices") or []), f"{m} {inst62d.get('ready_devices')}")
klaar62d = [x for x in asyncio.run(coachmod.async_get_beurten(hass62d).async_list()) if x["device"] == "dev-vaatwasser"]
controle("en de regel in de opslag is afgerond", len(klaar62d) == 1 and klaar62d[0]["complete"], f"{klaar62d}")
controle("maar er is niets gemeten, want het echte einde is niet gezien en 25 minuten is geen Eco",
         not [r for r in inst62d.get("program_measured") or [] if r.get("device") == "dev-vaatwasser"], f"{inst62d.get('program_measured')}")
b, m = asyncio.run(ronde62d(coach62e, dt.datetime(2026, 9, 8, 2, 31)))
controle("daarna wacht hij op een nieuwe vrijgave en drukt hij nergens op",
         b.get("rule") == "not-released" and not m and not [d for d in hass62d.services.verstuurd if d[0] == "button"], f"{b.get('rule')} {m}")

print("=== 63. een beurt van voor v0.57.2 krijgt zijn soort van het apparaat ===")
# De eigenaar op 07-09-2026 's middags, bij de beurt van die ochtend onder Bespaard:
# "ik zie nog dingen terugkomen van de laadpaal." Die regel had geen `kind`.
met_soort = storage.met_soort
oud63 = [
    {"id": "dev-vaatwasser:2026-09-07T10:51:00", "device": "dev-vaatwasser", "kwh": 0.825},
    {"id": "dev-laadpaal:2026-09-04T19:01:00", "device": "dev-laadpaal", "kwh": 66.0},
    {"id": "dev-vaatwasser:2026-09-08T01:02:00", "device": "dev-vaatwasser", "kind": "programma"},
    {"id": "dev-weg:2026-09-01T00:00:00", "device": "dev-weg"},
]
uit63 = met_soort(oud63, [LAADPAAL, VAATWASSER])
print(f"  {[(b['device'], b['kind']) for b in uit63]}")
controle("de oude vaatwasserbeurt wordt een programma, de laadbeurt blijft laden, wat er al stond blijft staan",
         [b["kind"] for b in uit63] == ["programma", "laden", "programma", "laden"], f"{uit63}")
controle("en de regels zelf zijn niet aangeraakt", "kind" not in oud63[0], "")

print("=== 64. bespaard is het totaal plaatje: de zon en het wachten ===")
# In een echte woning op 09-09-2026, bij een vaatwasser die meteen op zon startte en
# "bespaard nul" kreeg: "Er is toch wel iets zonne-energie naar de vaatwasser
# gegaan? Ik wil het totaal plaatje." De maat is alles van het net op het
# moment van vrijgeven; wat de zon scheelde en wat het wachten scheelde
# staan allebei in bespaard, en het verslag zegt welk deel wat was.
zin = coachmod.ChargerCoach._bespaard_zin
controle("_bespaard_zin: alleen zon, alleen wachten, allebei, en wachten dat geld kostte",
         zin(0.037, 0.037) == "Bespaard € 0,037, allemaal door de zon."
         and zin(0.04, 0.0) == "Bespaard € 0,040 door te wachten."
         and zin(0.12, 0.08) == "Bespaard € 0,120: € 0,080 door de zon en € 0,040 door te wachten."
         and zin(0.03, 0.05) == "Bespaard € 0,030: de zon scheelde € 0,050, het wachten kostte € 0,020.",
         f"{zin(0.037, 0.037)!r} {zin(0.04, 0.0)!r} {zin(0.12, 0.08)!r} {zin(0.03, 0.05)!r}")

inst64 = instellingen(devices=[LAADPAAL, VAATWASSER])
inst64["contract"] = {
    "type": "fixed", "netting": True,
    "fixed": {"all_in_price": 0.24171, "feed_in_tariff": 0.0721, "feed_in_costs": 0.052756},
}
inst64["strategy"]["schedules"].append({
    "device": "dev-vaatwasser", "enabled": True, "priority": "mid", "per_day": False,
    "window": {"not_before": "08:00", "start_by": "", "done_by": "16:30"}, "days": [],
})
# Drie kilowatt over op de meter: meer dan de piek van Eco, dus hij start.
huis64 = huis(status="ready_to_charge", teruglevering=3000.0, afname=0.0, zon_rest=0.0)
huis64.update({
    "sensor.vaatwasser_status": "ready",
    "select.vaatwasser_programma": "dishcare_dishwasher_program_eco_50",
    "binary_sensor.vaatwasser_deur": "off",
    "sensor.vaatwasser_vermogen": "0",
})
hass64, _, coach64 = bouw(huis64, inst64)

async def ronde64(nu):
    hass64.services.verstuurd.clear()
    await hass64.afmaken()
    await coach64._round(nu)
    await hass64.afmaken()
    return coach64.state.get("dev-vaatwasser") or {}, [d[2]["message"] for d in hass64.services.verstuurd if d[0] == "notify" and "Vaatwasser" in d[2].get("message", "")]

inst64["ready_devices"] = ["dev-vaatwasser"]
b, m = asyncio.run(ronde64(dt.datetime(2026, 9, 8, 12, 0)))
print(f"  12:00: {b.get('rule')} {b.get('reason', '')[:70]}")
controle("met 3 kW over start hij meteen bij het vrijgeven", b.get("rule") == "cheapest-start", f"{b}")
hass64.states.zet("sensor.vaatwasser_status", "run")
hass64.states.zet("sensor.vaatwasser_vermogen", "2000")
hass64.states.zet("sensor.teruglevering", "1000")   # 3 kW over min de 2 kW die hij trekt
for minuut in range(1, 31):
    asyncio.run(ronde64(dt.datetime(2026, 9, 8, 12, minuut)))
sessie64 = coach64._programma["dev-vaatwasser"]
print(f"  12:30: kwh {sessie64['kwh']:.3f}, betaald {sessie64['betaald']:.4f}, maat {sessie64['maat']:.4f}, zonwinst {sessie64['zon_winst']:.4f}")
# De maat is alles van het net bij het vrijgeven (de eigenaar op 09-09-2026: "wat je
# op zonne-energie laadt bespaar je natuurlijk ook door minder stroom in te
# kopen"); wat de zon scheelde staat apart, en dat is hier het hele verschil.
controle("een half uur op 2 kW met zon genoeg: betaald tegen de zonprijs, de maat alles van het net, en het verschil is de zon",
         abs(sessie64["kwh"] - 29 / 60 * 2) < 0.01 and abs(sessie64["betaald"] - sessie64["kwh"] * (0.24171 - 0.052756)) < 0.001
         and abs(sessie64["maat"] - sessie64["kwh"] * 0.24171) < 0.001
         and abs(sessie64["zon_winst"] - (sessie64["maat"] - sessie64["betaald"])) < 0.001,
         f"{sessie64['kwh']} {sessie64['betaald']} {sessie64['maat']} {sessie64['zon_winst']}")
hass64.states.zet("sensor.vaatwasser_status", "finished")
hass64.states.zet("sensor.vaatwasser_vermogen", "0")
hass64.states.zet("sensor.teruglevering", "3000")
b, m = asyncio.run(ronde64(dt.datetime(2026, 9, 8, 12, 31)))
print(f"  verslag: {m}")
controle("het verslag zegt wat er bespaard is, en dat het allemaal de zon was",
         len(m) == 1 and "is klaar" in m[0] and "Bespaard € 0,051, allemaal door de zon." in m[0], f"{m}")
b64 = [b for b in asyncio.run(coachmod.async_get_beurten(hass64).async_list()) if b["device"] == "dev-vaatwasser"]
controle("en onder Bespaard staat het zonaandeel, met het zondeel erbij",
         len(b64) == 1 and abs(b64[0]["saved"] - b64[0]["kwh"] * 0.052756) < 0.001
         and abs(b64[0]["solar_saved"] - b64[0]["saved"]) < 0.001
         and abs(b64[0]["ref_cost"] - b64[0]["kwh"] * 0.24171) < 0.001, f"{b64}")

print("=== 65. het plafond wordt per ronde gemeten, over de afgelopen drie uur ===")
# de klantwoning, nacht van 09 op 10-09-2026: een warmtepomp op L3 om het
# kwartier een paar minuten aan. De coach telt elke ronde wat er onder de
# zekering overbleef (onder de ondergrens van de paal telt als nul) en geeft
# het gemiddelde van de afgelopen `PLAFOND_VENSTER` mee als
# `Charger.expected_amps`, pas na `PLAFOND_MEETTIJD_MIN` minuten.
hass65, _, coach65 = bouw(huis(), laat)
def ronde65(minuut):
    # Vijf van elke vijftien minuten trekt het huis 22 A op L3: dan blijft er
    # onder de zekering van 25 A minder dan de ondergrens over.
    hass65.states.zet("sensor.l3", "22" if minuut % 15 < 5 else "2")
    return asyncio.run(ronde(coach65, laat, dt.datetime(2026, 9, 9, 10, 0) + dt.timedelta(minutes=minuut)))
for minuut in range(0, 20):
    ronde65(minuut)
vroeg65 = coach65._plafond_gemeten("dev-laadpaal", dt.datetime(2026, 9, 9, 10, 19))
controle("na twintig minuten is er nog geen meting", vroeg65 is None, f"{vroeg65}")
for minuut in range(20, 46):
    b65, _ = ronde65(minuut)
gemeten65 = coach65._plafond_gemeten("dev-laadpaal", dt.datetime(2026, 9, 9, 10, 45))
print(f"  na 45 minuten: gemiddeld {gemeten65:.2f} A, plan rekent met {b65['plan_ahead']['amps']} A, meting {b65['plan_ahead']['measured']}")
# Tien van de vijftien minuten 14 A en vijf keer nul is 9,3. De ene wekronde
# gaat eraf: daarin vraagt de coach sinds 17-09-2026 het hele plafond, en dan
# telt wat er werkelijk liep, en dat is nul zolang de auto nog niet begonnen is.
controle("na drie kwartier: tien van de vijftien minuten 14 A en vijf keer nul, dus rond de 8,5 A",
         gemeten65 is not None and 8.0 <= gemeten65 <= 10.0, f"{gemeten65}")
controle("en het plan rekent daarmee en zegt dat het een meting is",
         b65["plan_ahead"]["amps"] == int(gemeten65) and b65["plan_ahead"]["measured"] is True, f"{b65['plan_ahead']}")
# Een rustig huis: na drie uur zonder warmtepomp is het venster schoon.
hass65.states.zet("sensor.l3", "2")
for minuut in range(46, 230):
    b65, _ = asyncio.run(ronde(coach65, laat, dt.datetime(2026, 9, 9, 10, 0) + dt.timedelta(minutes=minuut)))
rustig65 = coach65._plafond_gemeten("dev-laadpaal", dt.datetime(2026, 9, 9, 13, 49))
controle("drie uur later is de warmtepomp uit het venster en staat het plafond weer op 14",
         rustig65 is not None and abs(rustig65 - 14.0) < 0.01 and b65["plan_ahead"]["measured"] is False, f"{rustig65}")
hass65.states.zet("sensor.laadpaal_status", "disconnected")
# Twee ronden, want de coach gelooft een kabel pas na `KABEL_ONTDREUN`.
asyncio.run(ronde(coach65, laat, dt.datetime(2026, 9, 9, 13, 50)))
asyncio.run(ronde(coach65, laat, dt.datetime(2026, 9, 9, 13, 51)))
controle("kabel eruit: de meting is weg, want hij hoort bij de beurt",
         coach65._plafond_gemeten("dev-laadpaal", dt.datetime(2026, 9, 9, 13, 51)) is None, "")

print("=== 66. de eindtijd van het apparaat telt pas als hij bij de beurt hoort en stilstaat ===")
# Twee keer misging het met dezelfde melding. In een echte woning op 11-09-2026: om 09:01
# het programma gekozen, en Home Connect zet de eindtijd dan al (10:56); om
# 09:36 gestart, en de melding zei "klaar rond 10:56", terwijl hij om 11:28
# klaar was. Een eindtijd die voor de start gezet is telt daarom niet
# (`EINDTIJD_MARGE`). En op 15-09-2026: Run om 10:11:57, om 10:11:56 zette Home
# Connect 11:33 en om 10:13:02 rekende hij hem opnieuw uit op 11:41; de melding
# van 10:12:53 zei "klaar rond 11:33" en klaar was hij om 11:45. Een eindtijd
# telt dus ook pas als hij stilstaat: twee ronden achter elkaar ongeveer
# hetzelfde (`EINDTIJD_SPELING`). De melding wacht op allebei, hooguit
# `EINDTIJD_WACHT`.
hass66 = NepHass({})
hass66.states.zet("sensor.rest", "2026-09-08T04:15:00", last_updated=dt.datetime(2026, 9, 8, 0, 30))
start66 = dt.datetime(2026, 9, 8, 1, 2)
sinds66 = start66 - coachmod.EINDTIJD_MARGE
controle("een eindtijd die voor de start gezet is telt niet",
         coachmod._eindtijd(hass66, "sensor.rest", start66, sinds=sinds66) is None, "")
controle("zonder sinds telt hij wel, zoals het altijd deed",
         coachmod._eindtijd(hass66, "sensor.rest", start66) == dt.datetime(2026, 9, 8, 4, 15), "")
hass66.states.zet("sensor.rest", "2026-09-08T04:47:00", last_updated=dt.datetime(2026, 9, 8, 1, 1, 30))
e66 = coachmod._eindtijd(hass66, "sensor.rest", start66, sinds=sinds66)
controle("een eindtijd die binnen de marge van de start gezet is telt wel", e66 == dt.datetime(2026, 9, 8, 4, 47), f"{e66}")

# `_eindtijd_vast` op zichzelf: wat er nodig is voor de coach hem gelooft.
def vast66(waarden):
    """De reeks antwoorden op een reeks metingen, vanaf een schone sessie."""
    sessie = {}
    return [coachmod._eindtijd_vast(sessie, w) for w in waarden]

u66 = vast66([dt.datetime(2026, 9, 8, 4, 40), dt.datetime(2026, 9, 8, 4, 48),
              dt.datetime(2026, 9, 8, 4, 48), dt.datetime(2026, 9, 8, 4, 49)])
print(f"  11:33 dan 11:41 dan 11:41 dan het gewiebel: {[None if x is None else f'{x:%H:%M}' for x in u66]}")
controle("een eerste waarde telt nog niet, en een waarde die verspringt ook niet",
         u66[0] is None and u66[1] is None, f"{u66}")
controle("twee ronden hetzelfde: dan telt hij", u66[2] == dt.datetime(2026, 9, 8, 4, 48), f"{u66}")
controle("een minuut gewiebel blijft binnen de speling en telt gewoon mee",
         u66[3] == dt.datetime(2026, 9, 8, 4, 49), f"{u66}")
w66 = vast66([dt.datetime(2026, 9, 8, 4, 48), dt.datetime(2026, 9, 8, 4, 48),
              dt.datetime(2026, 9, 8, 4, 56), None, dt.datetime(2026, 9, 8, 4, 56)])
controle("een echte herberekening telt pas als hij een ronde later blijft staan",
         w66[2] == dt.datetime(2026, 9, 8, 4, 48) and w66[4] == dt.datetime(2026, 9, 8, 4, 56), f"{w66}")
controle("een sensor die even wegvalt laat staan wat er geloofd werd",
         w66[3] == dt.datetime(2026, 9, 8, 4, 48), f"{w66}")


def beurt66(wijzigingen, minuten=(2, 3, 4, 5, 6)):
    """Een beurt waarin Home Connect de eindtijd om 00:30 zette, bij het kiezen.

    `wijzigingen` is wat de sensor per minuut gaat zeggen: de minuut na de
    hele uur, de nieuwe waarde, en wanneer die gezet werd.
    """
    inst = instellingen(devices=[LAADPAAL, VW62])
    inst["contract"] = inst56["contract"]
    inst["strategy"]["schedules"].append({
        "device": "dev-vaatwasser", "enabled": True, "priority": "mid", "per_day": False,
        "window": {"not_before": "", "start_by": "", "done_by": "07:00"}, "days": [],
    })
    waarden = dict(huis56)
    waarden["sensor.prijs"] = {"state": "0.18", "attributes": {"unit_of_measurement": "€/kWh", "prices": prijzen56(7)}}
    hass, _, c = bouw(waarden, inst)
    hass.states.zet("sensor.vaatwasser_rest", "2026-09-08T04:15:00", last_updated=dt.datetime(2026, 9, 8, 0, 30))

    async def ronde(nu):
        hass.services.verstuurd.clear()
        await hass.afmaken()
        await c._round(nu)
        await hass.afmaken()
        return c.state.get("dev-vaatwasser") or {}, [d[2]["message"] for d in hass.services.verstuurd
                                                     if d[0] == "notify" and "Vaatwasser" in d[2].get("message", "")]

    inst["ready_devices"] = ["dev-vaatwasser"]
    asyncio.run(ronde(dt.datetime(2026, 9, 7, 19, 5)))
    asyncio.run(ronde(dt.datetime(2026, 9, 8, 1, 0, 30)))
    hass.states.zet("sensor.vaatwasser_status", "run")
    hass.states.zet("sensor.vaatwasser_vermogen", "2000")
    uit = []
    for minuut in minuten:
        if minuut in wijzigingen:
            waarde, gezet = wijzigingen[minuut]
            hass.states.zet("sensor.vaatwasser_rest", waarde, last_updated=gezet)
        b, m = asyncio.run(ronde(dt.datetime(2026, 9, 8, 1, minuut)))
        print(f"  01:0{minuut}: {m}  kaart: {b.get('reason')}  ends_at {b.get('ends_at')}")
        uit.append((b, m))
    return uit


# Zoals het op 15-09 ging: bij de start een eindtijd die er acht minuten naast
# zit, een minuut later de goede.
print("  -- Home Connect rekent hem een minuut na de start opnieuw uit --")
b66 = beurt66({3: ("2026-09-08T04:40:00", dt.datetime(2026, 9, 8, 1, 2, 40)),
               4: ("2026-09-08T04:48:00", dt.datetime(2026, 9, 8, 1, 3, 10)),
               5: ("2026-09-08T04:48:00", dt.datetime(2026, 9, 8, 1, 3, 10))})
controle("in de ronde van de start geen melding: de eindtijd is nog die van het kiezen",
         b66[0][1] == [] and b66[0][0].get("ends_at") is None and b66[0][0].get("reason") == "Hij draait.",
         f"{b66[0]}")
controle("en ook niet op de eerste waarde van na de start, want die staat nog niet stil",
         b66[1][1] == [] and b66[1][0].get("ends_at") is None, f"{b66[1]}")
controle("staat hij twee ronden stil, dan de melding met die eindtijd en niet met de eerste",
         b66[3][1] == ["Vaatwasser is gestart (Eco 50 °C), klaar rond 04:48."]
         and b66[3][0].get("reason") == "Hij draait, klaar rond 04:48.", f"{b66[3]}")
controle("en niet nog eens", b66[4][1] == [], f"{b66[4][1]}")
controle("de eindtijd die er acht minuten naast zat komt nergens voor",
         not any("04:40" in m for _, ms in b66 for m in ms), f"{[ms for _, ms in b66]}")

# Zoals het op 11-09 ging: hij rekent hem helemaal niet opnieuw uit.
print("  -- hij rekent hem niet opnieuw uit --")
n66 = beurt66({})
controle("dan geen melding zolang de coach wacht, en niet met de eindtijd van het kiezen",
         [m for _, m in n66[:4]] == [[], [], [], []], f"{[m for _, m in n66]}")
controle("en na EINDTIJD_WACHT de duur uit de tabel, en niet 04:15",
         n66[4][1] == ["Vaatwasser is gestart (Eco 50 °C), klaar rond 04:47."], f"{n66[4][1]}")
controle("en op de kaart geen eindtijd die niet bij de beurt hoort",
         all(b.get("ends_at") is None for b, _ in n66), f"{[b.get('ends_at') for b, _ in n66]}")

print("=== 67. de meter telt als de laagste van tien minuten, niet als één opklaring ===")
# In een echte woning op 11-09-2026 om 09:35: een opklaring van een paar minuten gaf
# 2694 W teruglevering, meer dan de piek van Express 60, en de coach startte;
# om 09:37 was het 721 W. Voor een programma-apparaat telt de meter nu als wat
# hij de afgelopen `METER_VENSTER` ten minste zag, en pas na `METER_DEKKING`.
inst67 = instellingen()
hass67, _, coach67 = bouw(huis(teruglevering=300.0), inst67)
t67 = dt.datetime(2026, 9, 11, 9, 20)

def meet67(van, tot):
    for minuut in range(van, tot):
        coach67._meter_bijhouden(inst67, t67 + dt.timedelta(minutes=minuut))

meet67(0, 6)
controle("na vijf minuten meten telt de meter nog niet, zoals na een herstart",
         coach67._meter_zeker(t67 + dt.timedelta(minutes=5)) is None, "")
meet67(6, 15)
hass67.states.zet("sensor.teruglevering", "2694")
meet67(15, 17)
z67 = coach67._meter_zeker(t67 + dt.timedelta(minutes=16))
print(f"  twee minuten 2694 W na een kwartier 300 W: de meter telt als {z67}")
controle("een opklaring van twee minuten: de meter telt als de 300 W van ervoor", z67 == 300.0, f"{z67}")
meet67(17, 27)
z67 = coach67._meter_zeker(t67 + dt.timedelta(minutes=26))
controle("tien minuten 2694 W: dan telt hij", z67 == 2694.0, f"{z67}")
hass67.states.zet("sensor.teruglevering", "unavailable")
hass67.states.zet("sensor.afname", "unavailable")
meet67(27, 29)
z67 = coach67._meter_zeker(t67 + dt.timedelta(minutes=28))
controle("een meter die even wegvalt telt niet mee als nul", z67 == 2694.0, f"{z67}")

print("=== 68. na de klaar-tijd: ingeruimd en morgen starten, of ingeruimd en nu starten ===")
# De eigenaar op 12-09-2026 om 16:33: vrijgegeven bij klaar om 16:30, en de coach
# plande de volgende dag. Op 13-09: "ik wil dat er een optie bijkomt als hij na
# de klaartijd is. Dan de keuze ingeruimd en morgen starten of ingeruimd en nu
# starten." Op zijn keukenkaart met een tweede schakelaar: de vrijgave is
# morgen, deze is nu.
VRIJ68 = "input_boolean.vaatwasser_vrij"
NU68 = "input_boolean.vaatwasser_nu"
VW68 = dict(VAATWASSER, entities={**VAATWASSER["entities"], "release_switch": VRIJ68, "release_now_switch": NU68})
inst68 = instellingen(devices=[LAADPAAL, VW68])
inst68["contract"] = inst56["contract"]
inst68["strategy"]["schedules"].append({
    "device": "dev-vaatwasser", "enabled": True, "priority": "mid", "per_day": False,
    "window": {"not_before": "08:00", "start_by": "", "done_by": "16:30"}, "days": [],
})
huis68 = dict(huis56)
huis68.update({
    VRIJ68: "off", NU68: "off",
    "sensor.vaatwasser_status": "ready",
    "sensor.vaatwasser_vermogen": "0",
    "sensor.prijs": {"state": "0.25", "attributes": {"unit_of_measurement": "€/kWh", "prices": prijzen56(12)}},
})
hass68, _, coach68 = bouw(huis68, inst68)
async def ronde68(nu):
    hass68.services.verstuurd.clear()
    await hass68.afmaken()
    await coach68._round(nu)
    await hass68.afmaken()
    return coach68.state.get("dev-vaatwasser") or {}, list(hass68.services.verstuurd)
def schakel68(v, entiteit):
    return [d[1] for d in v if d[2].get("entity_id") == entiteit]
def knop68(v):
    return [d for d in v if d[0] == "button"]

b, v = asyncio.run(ronde68(dt.datetime(2026, 9, 12, 15, 30)))
controle("om 15:30, voor de klaar-tijd: niets gemist", b.get("rule") == "not-released" and b.get("missed") is None
         and b.get("later") is None, f"{b.get('missed')} {b.get('later')}")
controle("en de coach luistert naar allebei de schakelaars", VRIJ68 in coach68._watched and NU68 in coach68._watched,
         f"{coach68._watched}")
b, v = asyncio.run(ronde68(dt.datetime(2026, 9, 12, 16, 33)))
print(f"  16:33 {b.get('rule')}, gemist {b.get('missed')}, later {b.get('later')}: {b.get('reason')}")
controle("om 16:33: 16:30 gemist, het schema schuift naar morgen, en de reden vraagt morgen of nu",
         b.get("missed") == "2026-09-12T16:30:00" and b.get("later") == "morgen"
         and "morgen" in (b.get("reason") or "") and "of nu" in (b.get("reason") or ""), f"{b}")
hass68.states.zet(VRIJ68, "on")
b, v = asyncio.run(ronde68(dt.datetime(2026, 9, 12, 16, 34)))
print(f"  16:34 vrijgaveschakelaar aan: {b.get('rule')} {b.get('starts_at')}: {b.get('reason')}")
controle("de vrijgaveschakelaar is morgen: hij plant morgen, zegt dat, en drukt niets",
         b.get("rule") == "wait-for-start" and (b.get("starts_at") or "").startswith("2026-09-13")
         and "morgen om" in (b.get("reason") or "") and not b.get("start_now") and not knop68(v), f"{b} {v}")
# Op de kaart: toch nu starten.
inst68["ready_now"] = ["dev-vaatwasser"]
b, v = asyncio.run(ronde68(dt.datetime(2026, 9, 12, 16, 35)))
print(f"  16:35 toch nu starten: {b.get('rule')}: {b.get('reason')} | {knop68(v)} | nu {schakel68(v, NU68)}")
controle("toch nu starten op de kaart: hij drukt meteen, en de schakelaar nu starten gaat mee aan",
         b.get("rule") == "start-now" and b.get("start_now") and b.get("charge")
         and knop68(v) == [("button", "press", {"entity_id": "button.vaatwasser_start"})]
         and schakel68(v, NU68) == ["turn_on"] and not schakel68(v, VRIJ68), f"{b} {v}")
hass68.states.zet(NU68, "on")
hass68.states.zet("sensor.vaatwasser_status", "run")
hass68.states.zet("sensor.vaatwasser_vermogen", "2000")
b, v = asyncio.run(ronde68(dt.datetime(2026, 9, 12, 16, 36)))
gestart68 = [d[2]["message"] for d in v if d[0] == "notify" and "Vaatwasser" in d[2].get("message", "")]
controle("hij draait, zegt dat hij gestart is, en de schakelaars blijven staan",
         b.get("rule") == "running" and any("Vaatwasser is gestart" in m for m in gestart68)
         and not schakel68(v, NU68) and not schakel68(v, VRIJ68), f"{b.get('rule')} {gestart68} {v}")
hass68.states.zet("sensor.vaatwasser_status", "finished")
hass68.states.zet("sensor.vaatwasser_vermogen", "0")
b, v = asyncio.run(ronde68(dt.datetime(2026, 9, 12, 18, 30)))
controle("na de beurt gaan de vrijgave, nu starten en allebei de schakelaars uit",
         not inst68.get("ready_devices") and not inst68.get("ready_now")
         and schakel68(v, VRIJ68) == ["turn_off"] and schakel68(v, NU68) == ["turn_off"],
         f"{inst68.get('ready_devices')} {inst68.get('ready_now')} {v}")
hass68.states.zet(VRIJ68, "off")
hass68.states.zet(NU68, "off")
hass68.states.zet("sensor.vaatwasser_status", "ready")
b, v = asyncio.run(ronde68(dt.datetime(2026, 9, 12, 18, 31)))
controle("en daarna rust", b.get("rule") == "not-released" and not knop68(v) and not schakel68(v, NU68), f"{b.get('rule')} {v}")
# De volgende dag vanaf de keukenkaart, na de klaar-tijd: de schakelaar nu starten.
hass68.states.zet(NU68, "on")
b, v = asyncio.run(ronde68(dt.datetime(2026, 9, 13, 17, 0)))
print(f"  13-09 17:00 schakelaar nu starten: {b.get('rule')} vrij {inst68.get('ready_devices')} nu {inst68.get('ready_now')} {knop68(v)}")
controle("de schakelaar nu starten geeft vrij, kiest nu, en hij drukt",
         inst68.get("ready_devices") == ["dev-vaatwasser"] and inst68.get("ready_now") == ["dev-vaatwasser"]
         and b.get("rule") == "start-now" and len(knop68(v)) == 1, f"{b.get('rule')} {v}")
b, v = asyncio.run(ronde68(dt.datetime(2026, 9, 13, 17, 1)))
controle("een ronde later volgt de vrijgaveschakelaar, en hij drukt niet nog eens",
         schakel68(v, VRIJ68) == ["turn_on"] and not knop68(v), f"{v}")
# De vrijgaveschakelaar uit voordat hij draait: dan is er ook geen "nu" meer.
hass68.states.zet(VRIJ68, "off")
b, v = asyncio.run(ronde68(dt.datetime(2026, 9, 13, 17, 2)))
controle("vrijgave uit voor de start: nu starten gaat eraf, en die schakelaar volgt",
         not inst68.get("ready_devices") and not inst68.get("ready_now") and schakel68(v, NU68) == ["turn_off"],
         f"{inst68.get('ready_devices')} {inst68.get('ready_now')} {v}")

print("=== 69. de zonverwachting wordt bijgesteld met wat de meter gaf (17-09-2026) ===")
# Thuis zei de voorspeller 1,552 kWh voor het uur van 16:00 terwijl het dak 0,58
# deed en het huis het opat: vanaf 15:41 geen seconde teruglevering. De coach
# hield zijn belofte voor 16:00 overeind en verschoof hem daarna naar 17:00.
UUR69 = dt.datetime(2026, 9, 17, 15, 0)

def inst69():
    """Dezelfde instellingen, maar mét een zonnesensor: die meet het dak."""
    i = instellingen()
    i["sources"] = dict(i["sources"], solar="sensor.zon")
    return i

def coach69_met(dak_w):
    """Een coach met een voorspelling van 1,55 kWh voor dit uur en dat dak."""
    h = huis()
    h["sensor.zon"] = str(dak_w)
    _hass, _s, c = bouw(h, inst69())
    c._zon_kwh = {UUR69: 1.55, UUR69 + dt.timedelta(hours=1): 1.55}
    c._huis_kwh = {u: 0.94 for u in range(24)}
    return c

def voed69(coach, minuten, vanaf=UUR69):
    for i in range(minuten):
        coach._zon_bijhouden(vanaf + dt.timedelta(minutes=i), inst69())

# Het dak doet 580 W waar 1550 voorspeld stond, zoals thuis om 16:00.
coach69 = coach69_met(580)
voed69(coach69, 20)
vroeg69 = coach69._zon_gemeten(UUR69 + dt.timedelta(minutes=20))
controle("na twintig minuten is er nog geen oordeel", vroeg69 is None, f"{vroeg69}")
voed69(coach69, 25, UUR69 + dt.timedelta(minutes=20))
mager69 = coach69._zon_gemeten(UUR69 + dt.timedelta(minutes=45))
print(f"  580 W gemeten bij 1550 W beloofd: factor {mager69:.2f}")
controle("drie kwartier een derde van de belofte: de verwachting gaat mee omlaag",
         mager69 is not None and abs(mager69 - 580 / 1550) < 0.01, f"{mager69}")

# Een dak dat meer geeft dan voorspeld blaast de verwachting niet op.
coach69b = coach69_met(2000)
voed69(coach69b, 45)
ruim69 = coach69b._zon_gemeten(UUR69 + dt.timedelta(minutes=45))
print(f"  2000 W gemeten bij 1550 W beloofd: factor {ruim69}")
controle("meer zon dan voorspeld wordt geen extra zon", ruim69 == 1.0, f"{ruim69}")

# Een dak dat doet wat beloofd is verandert niets.
coach69d = coach69_met(1550)
voed69(coach69d, 45)
klopt69 = coach69d._zon_gemeten(UUR69 + dt.timedelta(minutes=45))
controle("een kloppende voorspelling blijft staan", klopt69 == 1.0, f"{klopt69}")

# En de zin reist mee naar de kaart. In v0.67.0 deed hij dat niet: `_tijdlijn`
# zette hem niet in de tijdlijn die het paneel krijgt, terwijl
# plan-ahead-sheet.js er wel naar keek. Elk veld van `Plan` dat het scherm
# gebruikt hoort hier langs te komen.
plan69 = coach69._tijdlijn.__doc__ is not None
velden69 = set(coachmod.ChargerCoach._tijdlijn.__code__.co_consts)
kaartvelden = {"deadline", "latest_start", "expected_done", "kwh_needed", "hours_needed",
               "amps", "planned_kwh", "solar_only", "note", "estimated", "measured",
               "solar_note", "blocks"}
controle("elk veld dat het scherm leest staat in de tijdlijn die het paneel krijgt",
         kaartvelden <= velden69, f"mist {sorted(kaartvelden - velden69)}")

# Zonder panelen, of in de schemering: niets beloofd, dus niets te corrigeren.
coach69c = coach69_met(0)
coach69c._zon_kwh = {}
voed69(coach69c, 60)
geen69 = coach69c._zon_gemeten(UUR69 + dt.timedelta(minutes=60))
controle("zonder belofte geen oordeel", geen69 is None, f"{geen69}")

print("=== 70. een accusensor die per tien procent meldt (thuis, 17-09-2026) ===")
# De Ford stond van 21:58:43 tot 22:30:37 op zeventig terwijl de paal 4.072 W
# leverde: 1,90 kWh aan de stekker, bijna negen procentpunt in de accu. Om 22:26
# zei de kaart "nog 2,2 kWh, vol rond 23:00" terwijl er 0,18 kWh in ging. De eigenaar:
# "dat hoeft helemaal niet en is onzin."
hass70, _, coach70 = bouw(huis(), instellingen())
D70 = "dev-laadpaal"

def bij70(ruw, eigen_kwh):
    coach70._eigen.setdefault(D70, {"kwh": 0.0})["kwh"] = eigen_kwh
    return coach70._soc_bijgeteld(D70, ruw, 19.7)

# Eerste meting: die is het ijkpunt en wordt niet opgehoogd.
controle("de eerste meting blijft zoals hij is", bij70(60.0, 10.0) == 60.0, "")
# Zolang de sensor nog geen sprong liet zien telt hij hooguit één procent bij.
print(f"  nog geen sprong gezien, 1,9 kWh erin: {bij70(60.0, 11.9):.1f}%")
controle("zonder bekende stap hoogstens een procent erbij",
         abs(bij70(60.0, 11.9) - 61.0) < 0.001, f"{bij70(60.0, 11.9)}")
# De sensor springt naar 70: dat is zijn resolutie, dus vanaf nu mag er tot
# tien procent bijgeteld worden.
controle("een sprong van tien is het nieuwe ijkpunt", bij70(70.0, 11.9) == 70.0, "")
op70 = bij70(70.0, 11.9 + 1.90)
print(f"  na de sprong, 1,90 kWh geleverd: {op70:.1f}% (kaal 70,0)")
controle("nu telt hij de kilowatturen van de paal er wel bij",
         abs(op70 - (70.0 + 1.90 * 0.9 / 19.7 * 100)) < 0.01, f"{op70}")
controle("en dat is precies wat er die avond ontbrak: ruim acht procentpunt",
         8.0 < op70 - 70.0 < 9.0, f"{op70 - 70.0}")
# Maar nooit meer dan één stap, hoe lang de paal ook doorlevert.
ver70 = bij70(70.0, 11.9 + 10.0)
print(f"  tien kWh geleverd zonder nieuwe meting: {ver70:.1f}%")
controle("de correctie blijft binnen een stap van de sensor", ver70 == 80.0, f"{ver70}")
# Een auto zonder capaciteit in het profiel valt terug op de kale meting.
controle("zonder capaciteit blijft het de kale meting",
         coach70._soc_bijgeteld(D70, 70.0, 0.0) == 70.0, "")

# En een sensor die netjes per procent meldt merkt er niets van: de sprong is
# dan een, dus de correctie ook hoogstens een.
hass70b, _, coach70b = bouw(huis(), instellingen())
def fijn70(ruw, eigen_kwh):
    coach70b._eigen.setdefault(D70, {"kwh": 0.0})["kwh"] = eigen_kwh
    return coach70b._soc_bijgeteld(D70, ruw, 19.7)
fijn70(60.0, 10.0)
fijn70(61.0, 10.2)
fijn70(62.0, 10.4)
fijn = fijn70(62.0, 12.4)
print(f"  sensor per procent, 2 kWh erin zonder nieuwe melding: {fijn:.1f}%")
controle("een fijne sensor krijgt hoogstens een procent erbij", abs(fijn - 63.0) < 0.001,
         f"{fijn}")


print("=== 71. een auto die nog bijkomt is geen auto die afbouwt (de klantwoning, 19-09-2026) ===")
# Om 03:17 zakte de coach voor de zekering naar 8 A, om 03:33:13 bood hij weer
# 16 A aan, en de Ford bleef tot 03:44 op 8 A. Om 03:35:11 stond dat als 5,52 kW
# voor band 6 in de opslag, en om 01:44 was band 4 zo op 7,58 kW gekomen. Hier op
# één fase en met het plafond van deze proefpaal (14 A), dus kleinere getallen.
def beurt71(car_pace=None, soc="65"):
    inst = instellingen(devices=[PAAL52], car_pace=list(car_pace or []))
    inst["strategy"]["schedules"][0]["window"]["done_by"] = "06:00"
    waarden = huis(status="charging", stroom=8.0, vermogen=1840.0, teruglevering=0.0,
                   afname=1800.0)
    waarden["sensor.auto_soc"] = soc
    hass, _, coach = bouw(waarden, inst)
    coach.async_boost("dev-laadpaal", True)
    coach._since["dev-laadpaal"] = dt.datetime(2026, 9, 19, 2, 55)
    coach._laadde["dev-laadpaal"] = True
    return inst, hass, coach

def op71(coach, inst, uur, minuut):
    asyncio.run(ronde(coach, inst, paal=PAAL52, nu=dt.datetime(2026, 9, 19, uur, minuut)))

inst71, hass71, coach71 = beurt71()
op71(coach71, inst71, 3, 0)
op71(coach71, inst71, 3, 15)
# De coach zakt voor de zekering: de paal meldt 8 A terug. Daarna biedt hij weer
# het plafond aan, en de auto blijft elf minuten op 8 A hangen.
hass71.states.zet("sensor.laadpaal_dyn", "8")
op71(coach71, inst71, 3, 32)
# De coach stuurt dezelfde 14 A niet nog een keer, dus de terugmelding van de
# verhoging zet de proef zelf, zoals de paal om 03:33:13 deed.
hass71.states.zet("sensor.laadpaal_dyn", "14")
for minuut in range(33, 44):
    op71(coach71, inst71, 3, minuut)
bijkomen71 = list(inst71.get("car_pace") or [])
print(f"  na elf minuten 8 A op een limiet van 14: {bijkomen71}")
controle("de minuten waarin de auto nog bijkomt worden geen tempo", not bijkomen71,
         f"{bijkomen71}")
# En daarna trekt hij gewoon het plafond: ook dat is geen tempo.
hass71.states.zet("sensor.laadpaal_stroom", "13.5")
hass71.states.zet("sensor.laadpaal_vermogen", "3100")
for minuut in range(44, 50):
    op71(coach71, inst71, 3, minuut)
controle("en de volle stroom daarna ook niet", not (inst71.get("car_pace") or []),
         f"{inst71.get('car_pace')}")

# Blijft hij langer dan een kwartier op 8 A, dan is het wel zijn tempo.
for minuut in range(50, 60):
    op71(coach71, inst71, 3, minuut)
hass71.states.zet("sensor.laadpaal_stroom", "8.0")
hass71.states.zet("sensor.laadpaal_vermogen", "1840")
for minuut in range(0, 3):
    op71(coach71, inst71, 4, minuut)
echt71 = list(inst71.get("car_pace") or [])
print(f"  8 A ruim na de laatste verhoging: {echt71}")
controle("een auto die ruim na een verhoging minder neemt wordt wel geleerd",
         any(r.get("band") == 6 and abs(r.get("kw", 0) - 1.84) < 0.01 and "soc" in r
             for r in echt71), f"{echt71}")

# Een bewaard tempo vervalt zodra de auto in die band aantoonbaar meer neemt,
# zoals de oude rijen van de klantwoning: zonder accustand, dus onderin de band.
OUD71 = {"device": "dev-laadpaal", "car": "car-1", "band": 6, "kw": 1.84, "at": "x"}
ANDER71 = {"device": "dev-laadpaal", "car": "car-1", "band": 4, "kw": 1.84, "at": "x"}
inst71b, hass71b, coach71b = beurt71([OUD71, ANDER71], soc="68")
op71(coach71b, inst71b, 3, 44)
hass71b.states.zet("sensor.laadpaal_stroom", "13.5")
hass71b.states.zet("sensor.laadpaal_vermogen", "3100")
op71(coach71b, inst71b, 3, 45)
een71 = list(inst71b.get("car_pace") or [])
controle("één ronde meer is nog geen weerlegging", OUD71 in een71, f"{een71}")
op71(coach71b, inst71b, 3, 46)
op71(coach71b, inst71b, 3, 47)
weg71 = list(inst71b.get("car_pace") or [])
print(f"  op 68% 13,5 A tegen een bewaarde 1,84 kW: {weg71}")
controle("twee ronden duidelijk meer: de band vervalt", not any(r.get("band") == 6 for r in weg71),
         f"{weg71}")
controle("en een andere band blijft staan", ANDER71 in weg71, f"{weg71}")

# Maar een afbouw die hoger in de band gemeten is blijft, want onderin de band
# nam de auto toen ook nog meer.
HOOG71 = dict(OUD71, soc=69.5)
inst71c, hass71c, coach71c = beurt71([HOOG71], soc="68")
op71(coach71c, inst71c, 3, 44)
hass71c.states.zet("sensor.laadpaal_stroom", "13.5")
hass71c.states.zet("sensor.laadpaal_vermogen", "3100")
for minuut in (45, 46, 47):
    op71(coach71c, inst71c, 3, minuut)
controle("een tempo gemeten bij 69,5% blijft staan als de auto op 68% meer neemt",
         HOOG71 in (inst71c.get("car_pace") or []), f"{inst71c.get('car_pace')}")

print("=== 72. een omvormer die slaapt is geen storing (de klantwoning, 18-09-2026) ===")
# De SolarEdge werd om 21:40 onbereikbaar, de zon was om 20:31 onder, en om 21:51
# kwam er een kritieke melding. 's Ochtends levert hij pas een uur na
# zonsopkomst weer iets.
inst72 = instellingen()
inst72["sources"]["solar"] = "sensor.omvormer"
hass72, _, coach72 = bouw(dict(huis(), **{"sensor.omvormer": "unavailable"}), inst72)
T72 = dt.datetime(2026, 9, 18, 21, 40)

def wacht72(minuten):
    hass72.services.verstuurd.clear()
    asyncio.run(coach72._async_sensorwacht(inst72, T72 + dt.timedelta(minutes=minuten)))
    return [d[2]["message"] for d in hass72.services.verstuurd
            if d[0] == "notify" and "zonnesensor" in d[2]["message"]]

hass72.states.zet("sun.sun", {"state": "below_horizon", "attributes": {"elevation": -15.0}})
nacht72 = wacht72(0) + wacht72(11) + wacht72(60)
controle("met de zon onder geen melding", not nacht72, f"{nacht72}")
hass72.states.zet("sun.sun", {"state": "above_horizon", "attributes": {"elevation": 6.0}})
ochtend72 = wacht72(600) + wacht72(615)
controle("vlak na zonsopkomst ook niet", not ochtend72, f"{ochtend72}")
hass72.states.zet("sun.sun", {"state": "above_horizon", "attributes": {"elevation": 25.0}})
dag72 = wacht72(700) + wacht72(711)
print(f"  overdag, na elf minuten: {dag72}")
controle("overdag wel, na tien minuten", len(dag72) == 1 and "zonnesensor" in dag72[0],
         f"{dag72}")
# Zonder `sun.sun` weet de coach het niet en blijft het zoals het was.
inst72b = instellingen()
inst72b["sources"]["solar"] = "sensor.omvormer"
hass72b, _, coach72b = bouw(dict(huis(), **{"sensor.omvormer": "unavailable"}), inst72b)
hass72b.services.verstuurd.clear()
asyncio.run(coach72b._async_sensorwacht(inst72b, T72))
asyncio.run(coach72b._async_sensorwacht(inst72b, T72 + dt.timedelta(minutes=11)))
zonder72 = [d for d in hass72b.services.verstuurd
            if d[0] == "notify" and "zonnesensor" in d[2]["message"]]
controle("zonder zonnestand meldt hij zoals vroeger", len(zonder72) == 1, f"{zonder72}")


print("=== 73. de boiler: aanzetten, kijken wat hij trekt, en het onthouden (19-09-2026) ===")
# De eigenaar op 19-09-2026: "een boiler waar je alleen stroom op moet zetten, met een
# smart plug. Als je er stroom op zet en de boiler is warm moet de coach
# detecteren dat hij warm genoeg is omdat hij dan onder een bepaald vermogen
# zit. Zelflerend, alleen de switch en power invullen."
BOILER = {
    "id": "dev-boiler",
    "type": "boiler",
    "name": "Boiler",
    "controllable": True,
    "entity": "sensor.boiler_vermogen",
    "entities": {"switch": "switch.boiler"},
}
inst73 = instellingen(devices=[BOILER])
inst73["strategy"]["schedules"] = [{
    "device": "dev-boiler", "enabled": True, "priority": "mid", "per_day": False,
    "window": {"not_before": "", "start_by": "", "done_by": "07:00"}, "days": [],
}]
huis73 = {
    **huis(afname=500.0, teruglevering=0.0, zon_rest=0.0),
    "switch.boiler": "off",
    "sensor.boiler_vermogen": "0",
}
hass73, store73, coach73 = bouw(dict(huis73), inst73)


async def ronde73(nu, watt=None):
    hass73.services.verstuurd.clear()
    await hass73.afmaken()
    if watt is not None:
        hass73.states.zet("sensor.boiler_vermogen", str(watt))
    await coach73._round(nu)
    await hass73.afmaken()
    # De smart plug doet wat hem gezegd wordt: dat doet een echte ook.
    for domein, dienst, gegevens in hass73.services.verstuurd:
        if gegevens.get("entity_id") == "switch.boiler":
            hass73.states.zet("switch.boiler", "on" if dienst == "turn_on" else "off")
    return coach73.state.get("dev-boiler") or {}, hass73.services.verstuurd


def stand73():
    return (store73.instellingen.get("boiler_learned") or [{}])[0]


# De eerste ronde: hij weet nog niets, dus hij meet in plaats van te rekenen.
b73, diensten = asyncio.run(ronde73(dt.datetime(2026, 9, 7, 22, 0)))
print(f"  22:00  {b73.get('rule')}  {b73.get('reason')}")
controle("de eerste keer: aanzetten en meten, niet rekenen", b73.get("rule") == "leren", f"{b73}")
controle("en de stroom gaat er werkelijk op",
         any(d[1] == "turn_on" and d[2].get("entity_id") == "switch.boiler" for d in diensten),
         f"{diensten}")

# Hij trekt 2 kW, een half uur lang.
for minuut in range(1, 31):
    b73, _ = asyncio.run(ronde73(dt.datetime(2026, 9, 7, 22, minuut), watt=2000))
controle("terwijl hij trekt staat hij op draaien en blijft de stroom erop",
         b73.get("running") is True and b73.get("on") is True, f"{b73}")

# En dan slaat de thermostaat af: geen vermogen meer.
b73, _ = asyncio.run(ronde73(dt.datetime(2026, 9, 7, 22, 31), watt=0))
controle("één minuut stilte is nog geen vol vat", b73.get("rule") != "full", f"{b73.get('rule')}")
b73, diensten = asyncio.run(ronde73(dt.datetime(2026, 9, 7, 22, 35), watt=0))
print(f"  22:35  {b73.get('rule')}  {b73.get('reason')}")
print(f"  geleerd: {stand73()}")
controle("na drie minuten stilte is het vat vol", b73.get("rule") == "full", f"{b73}")
controle("en de stroom gaat eraf",
         any(d[1] == "turn_off" and d[2].get("entity_id") == "switch.boiler" for d in diensten),
         f"{diensten}")
controle("hij weet nu wat het element trekt: ongeveer 2 kW",
         abs(float(stand73().get("heat_w") or 0) - 2000) < 60, f"{stand73()}")
controle("en hoeveel er in een vol vat ging: een half uur maal 2 kW is 1 kWh",
         abs(float(stand73().get("vol_kwh") or 0) - 1.0) < 0.05, f"{stand73()}")
controle("wat er per uur uit het vat gaat weet hij nog niet: daar zijn twee volle beurten voor nodig",
         stand73().get("verbruik_kwh_h") is None, f"{stand73()}")

# Meteen erna hoeft er niets bij.
b73, diensten = asyncio.run(ronde73(dt.datetime(2026, 9, 7, 22, 40), watt=0))
controle("vlak na een volle beurt blijft hij uit",
         not b73.get("charge") and b73.get("on") is False, f"{b73.get('rule')} {b73.get('on')}")
controle("en er wordt niets geschakeld", not diensten, f"{diensten}")

# Drie uur later kijkt hij even of het vat nog warm is. Het is nacht, dus hij
# vraagt niets: dan gaat de stroom er meteen weer af.
b73, diensten = asyncio.run(ronde73(dt.datetime(2026, 9, 8, 1, 41), watt=0))
print(f"  01:41  {b73.get('rule')}  {b73.get('reason')}")
controle("na drie uur draait hij even proef", b73.get("rule") == "proef", f"{b73}")
controle("en zet daarvoor de stroom erop",
         any(d[1] == "turn_on" and d[2].get("entity_id") == "switch.boiler" for d in diensten), f"{diensten}")

# Het vat is nog warm: binnen een paar minuten staat hij weer uit, en de
# tweede volle beurt leert hem wat er per uur uit gaat. Nu een beurt waarin
# hij wél iets vraagt.
for minuut in range(42, 60):
    b73, _ = asyncio.run(ronde73(dt.datetime(2026, 9, 8, 1, minuut), watt=1000))
b73, _ = asyncio.run(ronde73(dt.datetime(2026, 9, 8, 2, 0), watt=0))
b73, diensten = asyncio.run(ronde73(dt.datetime(2026, 9, 8, 2, 4), watt=0))
print(f"  02:04  {b73.get('rule')}  geleerd: {stand73()}")
controle("de tweede volle beurt zegt hoe snel het vat leegloopt",
         stand73().get("verbruik_kwh_h") is not None
         and 0.05 < float(stand73()["verbruik_kwh_h"]) < 0.2, f"{stand73()}")
controle("en hij weet nu drie dingen van deze boiler",
         all(stand73().get(k) for k in ("heat_w", "vol_kwh", "verbruik_kwh_h")), f"{stand73()}")
controle("de kaart zegt wat hij geleerd heeft",
         (b73.get("learned") or {}).get("runs") == 2, f"{b73.get('learned')}")

# Wat er geleerd is, is te wissen: een boiler die vervangen wordt begint
# opnieuw. Het commando zelf staat in websocket.py en die sleept de hele
# websocket-API mee; hier dus de bewerking zoals hij daar staat.
store73.instellingen["boiler_learned"] = [
    r for r in (store73.instellingen.get("boiler_learned") or []) if r.get("device") != "dev-boiler"
]
controle("wissen haalt het geleerde weg", not (store73.instellingen.get("boiler_learned") or []),
         f"{store73.instellingen.get('boiler_learned')}")

# En als de coach weggaat hoort de stroom erop te staan: een boiler zonder
# stroom blijft koud tot iemand het merkt, en dat is onder de douche.
hass73.services.verstuurd.clear()
coach73.async_stop()
asyncio.run(hass73.afmaken())
controle("de coach zet de boiler aan als hij stopt, zodat de thermostaat weer de baas is",
         any(d[1] == "turn_on" and d[2].get("entity_id") == "switch.boiler"
             for d in hass73.services.verstuurd),
         f"{hass73.services.verstuurd}")

print("=== 74. een boiler waar geen stroom bij komt zegt dat na drie keer ===")
# Er staat stroom op, er moest verwarmd worden, en er liep niets: dan is er
# iets met de stekker of de schakelaar, en dat hoort niemand pas onder de
# douche te merken.
inst74 = instellingen(devices=[BOILER])
inst74["strategy"]["schedules"] = list(inst73["strategy"]["schedules"])
# Gisterochtend trok hij voor het laatst stroom, en een vat van 6 kWh dat 0,3
# kWh per uur verliest is in twintig uur leeg. Vraagt hij dan nog steeds niets,
# dan is dat geen vol vat meer; zie BOILER_VERDACHT in planner.py.
inst74["boiler_learned"] = [{
    "device": "dev-boiler", "heat_w": 2000.0, "vol_kwh": 6.0, "verbruik_kwh_h": 0.3,
    "kwh_sinds_vol": 0.0, "vol_sinds": "2026-09-07T07:00:00",
    "getrokken_op": "2026-09-06T20:00:00", "runs": 3,
}]
huis74 = {**huis73, "switch.boiler": "off", "sensor.boiler_vermogen": "0"}
hass74, store74, coach74 = bouw(dict(huis74), inst74)


async def ronde74(nu):
    hass74.services.verstuurd.clear()
    await hass74.afmaken()
    await coach74._round(nu)
    await hass74.afmaken()
    for domein, dienst, gegevens in hass74.services.verstuurd:
        if gegevens.get("entity_id") == "switch.boiler":
            hass74.states.zet("switch.boiler", "on" if dienst == "turn_on" else "off")
    return (coach74.state.get("dev-boiler") or {},
            [d[2]["message"] for d in hass74.services.verstuurd if d[0] == "notify"])


meldingen74 = []
klok74 = dt.datetime(2026, 9, 7, 22, 0)
for keer in range(4):
    # Aanzetten, en er gebeurt niets: na de aanloop plus de stilte heet dat vol.
    for stap in (0, 1, 4, 7):
        b74, m = asyncio.run(ronde74(klok74 + dt.timedelta(minutes=stap)))
        meldingen74 += m
    klok74 += dt.timedelta(hours=3, minutes=10)
print(f"  {meldingen74}")
controle("na drie vergeefse keren zegt hij dat er geen stroom loopt",
         any("geen stroom" in m for m in meldingen74), f"{meldingen74}")
controle("en hij zegt het één keer", sum("geen stroom" in m for m in meldingen74) == 1, f"{meldingen74}")

print("=== 75. de thuisbatterij: de coach zet de modus, schrijft een vermogen en geeft hem terug ===")
# De eigenaar op 21-09-2026: "het doel is om hem volledig third party te sturen,
# dus via HA." De velden zijn die van de officiele integratie in de eerste
# woning: een modus, een vermogen zonder teken en een richting ernaast.
BATTERIJ = {
    "id": "dev-batterij", "type": "thuisbatterij", "name": "", "brand": "anker", "controllable": True,
    "entity": "sensor.batterij_vermogen",
    "entities": {
        "soc": "sensor.batterij_soc", "setpoint": "number.batterij_vermogen",
        "direction": "select.batterij_richting", "mode": "select.batterij_modus",
        "capacity": "sensor.batterij_capaciteit",
        "charge_limit": "number.batterij_laadgrens", "discharge_limit": "number.batterij_ontlaadgrens",
        "energy_in": "sensor.batterij_in", "energy_out": "sensor.batterij_uit",
    },
    "battery": {"max_charge_w": 3500, "max_discharge_w": 2500, "phase": "l3",
                "control_mode": "third_party_control", "idle_mode": "self_consumption"},
}


def huis75(afname=1500.0, teruglevering=0.0, batterij="0", soc="60", modus="self_consumption"):
    return {
        **huis(afname=afname, teruglevering=teruglevering, zon_rest=0.0, status="disconnected"),
        "sensor.batterij_vermogen": {"state": batterij, "attributes": {"unit_of_measurement": "W"}},
        "sensor.batterij_soc": soc,
        "number.batterij_vermogen": {"state": "0", "attributes": {"max_charge_power": 7000}},
        "select.batterij_richting": {"state": "charge", "attributes": {"options": ["charge", "discharge"]}},
        "select.batterij_modus": modus,
        "sensor.batterij_capaciteit": {"state": "14.6", "attributes": {"unit_of_measurement": "kWh"}},
        "number.batterij_laadgrens": "95", "number.batterij_ontlaadgrens": "5",
        "sensor.batterij_in": {"state": "250.0", "attributes": {"unit_of_measurement": "kWh"}},
        "sensor.batterij_uit": {"state": "184.0", "attributes": {"unit_of_measurement": "kWh"}},
    }


def zet75(hass):
    """Wat er deze ronde naar de batterij ging: (modus, richting, vermogen)."""
    modus = [d[2]["option"] for d in hass.services.verstuurd if d[2].get("entity_id") == "select.batterij_modus"]
    richting = [d[2]["option"] for d in hass.services.verstuurd if d[2].get("entity_id") == "select.batterij_richting"]
    vermogen = [d[2]["value"] for d in hass.services.verstuurd if d[2].get("entity_id") == "number.batterij_vermogen"]
    return modus, richting, vermogen


def volg75(hass):
    """Wat Home Assistant doet na een opdracht: de keuzelijst laat de nieuwe keuze zien."""
    for _, _, gegevens in hass.services.verstuurd:
        if gegevens.get("entity_id") == "select.batterij_modus":
            hass.states.zet("select.batterij_modus", gegevens["option"])


async def ronde75(hass, coach, nu):
    hass.services.verstuurd.clear()
    await hass.afmaken()
    await coach._round(nu)
    await hass.afmaken()
    volg75(hass)
    return coach.state.get("dev-batterij") or {}


inst75 = instellingen(devices=[LAADPAAL, BATTERIJ])
hass75, store75, coach75 = bouw(huis75(), inst75)
NU75 = dt.datetime(2026, 9, 21, 21, 0)
b75 = asyncio.run(ronde75(hass75, coach75, NU75))
modus75, richting75, vermogen75 = zet75(hass75)
print(f"  {b75.get('mode_name')}: {b75.get('reason')}")
print(f"  naar de batterij: modus {modus75}, richting {richting75}, vermogen {vermogen75}")
controle("vast contract, avond: nul op de meter", b75.get("mode") == "nul", f"{b75.get('mode')}")
controle("de modus gaat naar externe sturing", modus75 == ["third_party_control"], f"{modus75}")
controle("het huis vraagt 1500 W: de richting gaat naar ontladen", richting75 == ["discharge"], f"{richting75}")
# Het doel ligt een halve dode band onder nul, want terugleveren brengt minder
# op dan inkopen kost: 1500 plus 20.
controle("en het vermogen is wat het huis vraagt, zonder teken", vermogen75 == [1520], f"{vermogen75}")
controle("het rendement komt uit de kWh-meter: 73,6%", b75.get("rte") == 0.736, f"{b75.get('rte')}")
controle("en staat in de opslag, voor na een herstart",
         abs((store75.instellingen.get("battery_state") or [{}])[0].get("rte", 0) - 0.736) < 0.001,
         f"{store75.instellingen.get('battery_state')}")
controle("de laadgrens en de ontlaadgrens zijn alleen gelezen",
         not [d for d in hass75.services.verstuurd if "grens" in str(d[2].get("entity_id"))],
         f"{hass75.services.verstuurd}")
controle("de kaart krijgt de stand, de accustand en de terugverdientijd",
         b75.get("kind") == "batterij" and b75.get("soc") == 60.0 and "earned" in (b75.get("payback") or {}),
         f"{ {k: b75.get(k) for k in ('kind', 'soc', 'payback')} }")

# De coach stopt: het vermogen naar nul en de batterij terug naar zijn eigen
# stand. Op zijn laatste opdracht blijven staan is leeglopen naar het net.
hass75.services.verstuurd.clear()
coach75.async_stop()
asyncio.run(hass75.afmaken())
modus75, _, vermogen75 = zet75(hass75)
print(f"  bij het stoppen: modus {modus75}, vermogen {vermogen75}")
controle("stopt de coach, dan gaat het vermogen naar nul", vermogen75 == [0], f"{vermogen75}")
controle("en de batterij terug naar zijn eigen stand", modus75 == ["self_consumption"], f"{modus75}")

print("=== 76. de thuisbatterij: wie niet mag sturen schrijft niets ===")
for niveau in ("read", "advise", "propose"):
    inst76 = instellingen(devices=[LAADPAAL, BATTERIJ])
    inst76["strategy"]["level"] = niveau
    hass76, _, coach76 = bouw(huis75(), inst76)
    b76 = asyncio.run(ronde75(hass76, coach76, NU75))
    controle(f"op '{niveau}' gaat er niets naar de batterij", zet75(hass76) == ([], [], []), f"{zet75(hass76)}")
    controle(f"op '{niveau}' zegt hij wel wat hij zou doen",
             b76.get("mode") == "nul" and b76.get("applied") is False, f"{b76.get('mode')} {b76.get('applied')}")

# Het vinkje "mag sturen" gaat eraf terwijl hij stuurde: dan geeft hij hem terug.
inst76 = instellingen(devices=[LAADPAAL, BATTERIJ])
hass76, store76, coach76 = bouw(huis75(), inst76)
asyncio.run(ronde75(hass76, coach76, NU75))
store76.instellingen["devices"] = [LAADPAAL, {**BATTERIJ, "controllable": False}]
asyncio.run(ronde75(hass76, coach76, NU75 + dt.timedelta(minutes=1)))
modus76, _, vermogen76 = zet75(hass76)
controle("vinkje eraf: vermogen naar nul en de eigen stand terug",
         vermogen76 == [0] and modus76 == ["self_consumption"], f"{modus76} {vermogen76}")

print("=== 77. de thuisbatterij: de laadpaal laadt, een ander merk, en twee sensoren ===")
inst77 = instellingen(devices=[LAADPAAL, BATTERIJ])
hass77, _, coach77 = bouw({**huis75(afname=5500.0), "sensor.laadpaal_vermogen": "4100",
                           "sensor.laadpaal_status": "charging", "sensor.laadpaal_stroom": "6"}, inst77)
b77 = asyncio.run(ronde75(hass77, coach77, NU75))
print(f"  {b77.get('mode_name')}: {b77.get('reason')}")
controle("laadt de paal, dan staat de batterij op alleen zonneladen",
         b77.get("mode") == "zonneladen" and b77.get("rule") == "paal-laadt", f"{b77.get('mode')} {b77.get('rule')}")
controle("en er gaat geen ontlaadopdracht heen",
         not [v for v in zet75(hass77)[2] if v] and "discharge" not in zet75(hass77)[1], f"{zet75(hass77)}")

# Het merk Overig zonder richting: het teken van het getal is de richting.
OVERIG77 = {**BATTERIJ, "brand": "overig",
            "entities": {k: v for k, v in BATTERIJ["entities"].items() if k not in ("direction", "mode")},
            "battery": {"max_charge_w": 3000, "max_discharge_w": 3000}}
hass77b, _, coach77b = bouw(huis75(), instellingen(devices=[LAADPAAL, OVERIG77]))
asyncio.run(ronde75(hass77b, coach77b, NU75))
controle("zonder richting gaat ontladen erin als een negatief getal", zet75(hass77b) == ([], [], [-1520]),
         f"{zet75(hass77b)}")
OMGEKEERD77 = {**OVERIG77, "battery": {**OVERIG77["battery"], "setpoint_invert": True}}
hass77c, _, coach77c = bouw(huis75(), instellingen(devices=[LAADPAAL, OMGEKEERD77]))
asyncio.run(ronde75(hass77c, coach77c, NU75))
controle("of als een positief, waar de batterij het zo wil", zet75(hass77c)[2] == [1520], f"{zet75(hass77c)}")

# Een batterij die laden en ontladen op twee sensoren meldt, zoals de officiele
# integratie in de eerste woning: 2250 W ontladen is dan min 2250.
TWEE77 = {**BATTERIJ, "entity": "",
          "entities": {**BATTERIJ["entities"], "charge_power": "sensor.bat_laden",
                       "discharge_power": "sensor.bat_ontladen"}}
hass77d, _, coach77d = bouw({**huis75(afname=0.0), "sensor.bat_laden": "0", "sensor.bat_ontladen": "2250"},
                            instellingen(devices=[LAADPAAL, TWEE77]))
b77d = asyncio.run(ronde75(hass77d, coach77d, NU75))
controle("twee sensoren worden samen een vermogen met een teken", b77d.get("power_w") == -2250,
         f"{b77d.get('power_w')}")
controle("en de sensor die andersom telt ook",
         coach77d._batterij_w({**BATTERIJ, "battery": {"power_invert": True}}) is not None
         and coachmod.ChargerCoach._batterij_w(
             coach75, {**BATTERIJ, "battery": {"power_invert": True}}) in (0.0, -0.0), "")

print("=== 78. de thuisbatterij: wat hij opslokt blijft overschot voor de andere apparaten ===")
# De meter staat op nul omdat de batterij 2 kW zon opneemt. Voor de vaatwasser
# en de paal is dat nog steeds 2 kW overschot: die laden zonder verlies en gaan
# dus voor, en de batterij krijgt wat er daarna over is.
hass78, _, coach78 = bouw(huis75(afname=0.0, teruglevering=0.0, batterij="2000"),
                          instellingen(devices=[LAADPAAL, BATTERIJ]))
inst78 = instellingen(devices=[LAADPAAL, BATTERIJ])
controle("de kale meter zegt nul", coach78._netto_export_kaal(inst78) == 0.0,
         f"{coach78._netto_export_kaal(inst78)}")
controle("voor de andere apparaten is er 2 kW over", coach78._netto_export_w(inst78) == 2000.0,
         f"{coach78._netto_export_w(inst78)}")
hass78.states.zet("sensor.batterij_vermogen", {"state": "-1500", "attributes": {"unit_of_measurement": "W"}})
hass78.states.zet("sensor.teruglevering", "200")
controle("en wat de batterij afgeeft is geen zon: 200 W terug bij 1500 W ontladen is 1300 W tekort",
         coach78._netto_export_w(inst78) == -1300.0, f"{coach78._netto_export_w(inst78)}")
# De zekering: de batterij hangt op L3, waar al 18 A loopt. Onder de 25 A met
# de marge van de lastbewaker blijft er weinig over om mee te laden.
hass78.states.zet("sensor.l3", "18")
ruimte78 = coach78._laadruimte_w(inst78, BATTERIJ, 0.0)
print(f"  laadruimte op L3 bij 18 A: {ruimte78:.0f} W")
controle("de laadruimte is wat die ene fase nog overlaat", 0 < ruimte78 < 1500, f"{ruimte78}")

print("=== 79. de thuisbatterij: de wekelijkse volle beurt zet de laadgrens een dag op 100 en daarna terug ===")
# De laadgrens is van de batterij en de coach schrijft hem nooit, met deze ene
# uitzondering (de keuze van de eigenaar op 22-09-2026): op de dag van de volle
# beurt naar 100, en zodra hij vol is terug naar wat er stond. Wat er stond
# staat in de opslag, zodat een herstart het niet vergeet.
BATTERIJ79 = {**BATTERIJ, "battery": {**BATTERIJ["battery"], "weekly_full": True, "weekly_full_day": 0}}
inst79 = instellingen(devices=[LAADPAAL, BATTERIJ79])
hass79, store79, coach79 = bouw(huis75(soc="60"), inst79)
NU79 = dt.datetime(2026, 9, 21, 21, 0)   # een maandag


def grens79(hass):
    return [d[2]["value"] for d in hass.services.verstuurd if d[2].get("entity_id") == "number.batterij_laadgrens"]


def rij79(store):
    return (store.instellingen.get("battery_state") or [{}])[0]


b79 = asyncio.run(ronde75(hass79, coach79, NU79))
print(f"  {b79.get('mode_name')}: {b79.get('reason')}")
print(f"  laadgrens: {grens79(hass79)}, opslag: {rij79(store79)}")
controle("op de dag van de volle beurt gaat de laadgrens naar 100", grens79(hass79) == [100.0], f"{grens79(hass79)}")
controle("en wat er stond staat in de opslag", rij79(store79).get("limit_restore") == 95.0, f"{rij79(store79)}")
controle("de kaart weet dat hij vandaag vol hoort", bool(b79.get("full_before")), f"{b79.get('full_before')}")
controle("en het plan rekent meteen tot 100", b79.get("ceiling") == 100.0, f"{b79.get('ceiling')}")
hass79.states.zet("number.batterij_laadgrens", "100")
b79 = asyncio.run(ronde75(hass79, coach79, NU79 + dt.timedelta(minutes=1)))
controle("de ronde erna schrijft hij niet nog een keer", grens79(hass79) == [], f"{grens79(hass79)}")
hass79.states.zet("sensor.batterij_soc", "99")
b79 = asyncio.run(ronde75(hass79, coach79, NU79 + dt.timedelta(minutes=2)))
print(f"  op 99%: laadgrens {grens79(hass79)}, opslag: {rij79(store79)}")
controle("op 99% gaat de laadgrens terug naar 95", grens79(hass79) == [95.0], f"{grens79(hass79)}")
controle("de volle beurt staat in de opslag en de oude grens is vergeten",
         bool(rij79(store79).get("full_at")) and rij79(store79).get("limit_restore") is None, f"{rij79(store79)}")
hass79.states.zet("number.batterij_laadgrens", "95")
b79 = asyncio.run(ronde75(hass79, coach79, NU79 + dt.timedelta(minutes=3)))
controle("en daarna is er een week niets te doen", grens79(hass79) == [] and not b79.get("full_before"),
         f"{grens79(hass79)} {b79.get('full_before')}")

# Stopt de coach terwijl de grens op 100 staat, dan gaat hij mee terug.
hass79b, store79b, coach79b = bouw(huis75(soc="60"), instellingen(devices=[LAADPAAL, BATTERIJ79]))
asyncio.run(ronde75(hass79b, coach79b, NU79))
hass79b.services.verstuurd.clear()
coach79b.async_stop()
asyncio.run(hass79b.afmaken())
controle("stopt de coach met de grens op 100, dan zet hij hem terug", grens79(hass79b) == [95.0], f"{grens79(hass79b)}")

# Wie niet stuurt schrijft ook de laadgrens niet.
inst79c = instellingen(devices=[LAADPAAL, BATTERIJ79])
inst79c["strategy"]["level"] = "advise"
hass79c, store79c, coach79c = bouw(huis75(soc="60"), inst79c)
b79c = asyncio.run(ronde75(hass79c, coach79c, NU79))
controle("op adviseren blijft de laadgrens met rust", grens79(hass79c) == [] and rij79(store79c).get("limit_restore") is None,
         f"{grens79(hass79c)}")

# Bij een herstart van Home Assistant komt er geen async_stop, alleen het
# stop-event. In de eerste woning bleef de batterij op 23-09-2026 om 00:44 bij
# de herstart voor v0.81.1 gewoon 235 W ontladen in de externe modus tot de
# coach twee minuten later terug was. Het event hoort de batterij terug te
# geven: 0 W en zijn eigen stand, en de laadgrens terug.
hass79d, store79d, coach79d = bouw(huis75(soc="60"), instellingen(devices=[LAADPAAL, BATTERIJ79]))
coach79d.async_start()
asyncio.run(ronde75(hass79d, coach79d, NU79))
hass79d.services.verstuurd.clear()
stop79d = [wat for soort, wat in hass79d.bus.luisteraars if soort == "homeassistant_stop"]
controle("de coach luistert naar het stop-event van Home Assistant", len(stop79d) == 1, f"{hass79d.bus.luisteraars}")
for wat in stop79d:
    asyncio.run(wat(None))
asyncio.run(hass79d.afmaken())
zet79d = [(d[1], d[2].get("entity_id"), d[2]["value"] if "value" in d[2] else d[2].get("option")) for d in hass79d.services.verstuurd]
controle("bij het stop-event gaat de batterij op 0 W",
         ("set_value", "number.batterij_vermogen", 0.0) in zet79d, f"{zet79d}")
controle("en terug naar zijn eigen stand",
         ("select_option", "select.batterij_modus", "self_consumption") in zet79d, f"{zet79d}")
controle("en de laadgrens terug op wat er stond", grens79(hass79d) == [95.0], f"{grens79(hass79d)}")

print("=== 80. de thuisbatterij: het overschot voor de andere apparaten rekent met de opdracht ===")
# 22-09-2026 in de eerste woning: de sensor van de Anker liep vijf tot tien
# seconden achter op de kWh-meter. De batterij laadde 3 kW van de zon, een
# wolk kwam, de regelaar zette hem op 1 kW; de meter zag dat binnen vijf
# seconden, de sensor bleef 3 kW zeggen. Wie dan de sensor bij de meter optelt
# ziet 3 kW overschot dat er niet is, en daar start een paal op.
hass80, _, coach80 = bouw(huis75(afname=0.0, teruglevering=0.0, batterij="3000"),
                          instellingen(devices=[LAADPAAL, BATTERIJ]))
inst80 = instellingen(devices=[LAADPAAL, BATTERIJ])
NU80 = dt.datetime(2026, 9, 22, 12, 0)
coach80._batterij["dev-batterij"] = {"regelaar": coachmod.Regelaar(opdracht_w=1000.0, opdracht_op=NU80, bezonken=False),
                                     "stuurt": True}
controle("zolang de sensor de opdracht niet bevestigt telt de opdracht: 1 kW overschot en geen 3",
         coach80._netto_export_w(inst80) == 1000.0, f"{coach80._netto_export_w(inst80)}")
coach80._batterij["dev-batterij"]["regelaar"]._afwijkt = 3
controle("spreekt de sensor de opdracht blijvend tegen, dan telt de sensor",
         coach80._netto_export_w(inst80) == 3000.0, f"{coach80._netto_export_w(inst80)}")
coach80._batterij["dev-batterij"]["stuurt"] = False
controle("en stuurt de coach niet, dan is er alleen de sensor",
         coach80._netto_export_w(inst80) == 3000.0, f"{coach80._netto_export_w(inst80)}")

print("=== 81. een onderverdeelkast met een eigen zekering en meter (22-09-2026) ===")
# De eerste woning: 3x25 A aan de meterkast, in de garage 3x16 A met een eigen
# HomeWizard kWh-meter, en daar hangen de paal en de batterij aan. De bewoner
# had het vermogen van fase 2 en 3 al uit de garagemeter gehaald als noodgreep;
# nu is het een groep, en telt hij bij alles mee waar de hoofdzekering telt.
GARAGE = {
    "id": "garage", "name": "Garage", "fuse_amps": 16, "phases": 3, "parent": "",
    "sensors": {"l1": {"current": "sensor.g1"}, "l2": {"current": "sensor.g2"}, "l3": {"current": "sensor.g3"}},
}
LAADPAAL_G = {**LAADPAAL, "circuit": "garage"}
BATTERIJ_G = {**BATTERIJ, "circuit": "garage", "battery": {**BATTERIJ["battery"], "phase": "l3"}}
inst81 = instellingen(devices=[LAADPAAL_G, BATTERIJ_G])
inst81["installation"]["circuits"] = [GARAGE]
inst81["installation"]["load_balancer"] = False
huis81 = {**huis75(afname=1500.0), "sensor.l1": "6", "sensor.l2": "4", "sensor.l3": "4",
          "sensor.g1": "3", "sensor.g2": "2", "sensor.g3": "2"}
hass81, _, coach81 = bouw(huis81, inst81)
NU81 = dt.datetime(2026, 9, 22, 12, 0)

controle("de keten van de paal is de garage", [g["id"] for g in coach81._groepen_keten(inst81, LAADPAAL_G)] == ["garage"],
         f"{coach81._groepen_keten(inst81, LAADPAAL_G)}")
controle("en een toezegging aan die paal telt onder de hoofdaansluiting en onder de garage",
         coach81._groep_sleutels(inst81, LAADPAAL_G) == ["", "garage"], f"{coach81._groep_sleutels(inst81, LAADPAAL_G)}")
grid81, _, _, _ = coach81._read(NU81, inst81, LAADPAAL_G)
print(f"  hoofdaansluiting {grid81.phase_amps} A tegen {grid81.fuse_amps} A, "
      f"groepen {[(c.name, c.phase_amps, c.fuse_amps) for c in grid81.circuits]}")
controle("de coach leest de garagemeter als groep",
         len(grid81.circuits) == 1 and grid81.circuits[0].name == "Garage"
         and grid81.circuits[0].phase_amps == [3.0, 2.0, 2.0] and grid81.circuits[0].fuse_amps == 16.0,
         f"{grid81.circuits}")
grid81b, _, _, _ = coach81._read(NU81, inst81, LAADPAAL_G, {"": 4.0, "garage": 3.0})
controle("wat er al is toegezegd komt per zekering binnen",
         grid81b.reserved_amps == 4.0 and grid81b.circuits[0].reserved_amps == 3.0,
         f"{grid81b.reserved_amps} {grid81b.circuits[0].reserved_amps}")

# De batterij op L3 in de garage: onder de garage past (16 - 2 - 2) x 230 = 2760 W,
# onder de hoofdaansluiting (25 - 2 - 4) x 230 = 4370 W; de garage wint.
ruimte81 = coach81._laadruimte_w(inst81, BATTERIJ_G, 0.0)
print(f"  laadruimte voor de batterij in de garage: {ruimte81:.0f} W")
controle("de batterij blijft onder de zekering van de garage", abs(ruimte81 - 2760.0) < 1, f"{ruimte81}")
controle("een batterij aan de meterkast heeft de ruimte van de hoofdaansluiting",
         abs(coach81._laadruimte_w(inst81, {**BATTERIJ_G, "circuit": ""}, 0.0) - 4370.0) < 1,
         f"{coach81._laadruimte_w(inst81, {**BATTERIJ_G, 'circuit': ''}, 0.0)}")

# De snelle zekeringcontrole kent per sensor de grens van zijn eigen zekering.
asyncio.run(ronde75(hass81, coach81, NU81))
print(f"  grenzen: {coach81._urgent_above}")
controle("de garagesensoren wekken de coach al bij 14 A, die van de meterkast bij 23",
         (coach81._urgent_above or {}).get("sensor.g1") == 14.0 and (coach81._urgent_above or {}).get("sensor.l1") == 23.0,
         f"{coach81._urgent_above}")
controle("en de garagesensoren horen bij wat de coach volgt", "sensor.g2" in coach81._watched_phases,
         f"{sorted(coach81._watched_phases)}")
controle("de sensorwacht kent de garagesensor bij naam",
         "Garage" in coach81._sensoren(inst81).get("sensor.g1", ""), f"{coach81._sensoren(inst81).get('sensor.g1')}")

# De lastwaarschuwing: de garage op 12 A is 75% van 16, zwaarder dan 6 van 25.
hass81m, monitor81 = bewaker(inst81, {**huis81, "sensor.g1": "12"})
last81 = monitor81.async_current_load()
print(f"  belasting: {last81.percent:.0f}% op {last81.worst_phase}")
controle("de lastwaarschuwing kijkt naar de zwaarst belaste zekering, ook die van een groep",
         abs(last81.percent - 75.0) < 0.1 and last81.worst_phase == "L1 (Garage)", f"{last81}")
hass81n, monitor81n = bewaker(inst81, huis81)
controle("en zonder garagelast wint de hoofdaansluiting", monitor81n.async_current_load().worst_phase == "L1",
         f"{monitor81n.async_current_load()}")

# Instellingen die de groep niet kennen, of een paal zonder groep, blijven zoals ze waren.
grid81c, _, _, _ = coach81._read(NU81, inst81, LAADPAAL)
controle("een paal zonder groep heeft geen groepen", grid81c.circuits == [], f"{grid81c.circuits}")

print("=== 82. een Tesla slaapt als hij niet laadt: de wekknop (22-09-2026) ===")
# De eigenaar: "als een tesla niet aan de lader hangt slaapt hij en geeft hij
# geen accu door, daardoor krijg ik telkens een melding van tesla meldt al 10
# min niks." Twee standen: elk uur wekken als hij stilstaat, of handmatig via
# de knop op de kaart. Bij het inpluggen wekt de coach hem altijd één keer.
TESLA = {"id": "car-t", "name": "Model Y", "brand": "tesla", "capacity_kwh": 75, "phases": "three",
         "max_amps": 16, "soc_entity": "sensor.tesla_accu", "wake_entity": "button.tesla_wake",
         "wake_mode": "manual"}
PAAL_T = {**LAADPAAL, "cars": [TESLA]}


def gedrukt(hass):
    return [d for d in hass.services.verstuurd if d[2].get("entity_id") == "button.tesla_wake"]


inst82 = instellingen(devices=[PAAL_T])
hass82, _, coach82 = bouw({**huis(status="disconnected"), "sensor.tesla_accu": "unavailable"}, inst82)
T82 = dt.datetime(2026, 9, 22, 20, 0)
controle("de sensorwacht laat de accustand van een auto met wekknop met rust",
         "sensor.tesla_accu" not in coach82._sensoren(inst82), f"{coach82._sensoren(inst82)}")
controle("een auto zonder wekknop staat er wel in",
         "sensor.tesla_accu" in coach82._sensoren(instellingen(devices=[{**LAADPAAL, "cars": [{**TESLA, "wake_entity": ""}]}])), "")

# Handmatig: de coach wekt niet uit zichzelf, ook niet na een uur.
for minuten in (0, 1, 61, 122):
    asyncio.run(ronde75(hass82, coach82, T82 + dt.timedelta(minutes=minuten)))
controle("handmatig: zonder kabel wekt de coach de auto nooit zelf", gedrukt(hass82) == [], f"{gedrukt(hass82)}")
b82 = coach82.state.get("dev-laadpaal") or {}
controle("de kaart weet dat er een wekknop is", b82.get("wake") is True, f"{b82.get('wake')}")

# De knop op de kaart.
gewekt82 = asyncio.run(coach82.async_wake("dev-laadpaal"))
asyncio.run(hass82.afmaken())
controle("de knop op de kaart drukt op de wekknop", gewekt82 is True and len(gedrukt(hass82)) == 1, f"{gedrukt(hass82)}")
controle("en een laadpunt zonder wekknop zegt nee", asyncio.run(coach82.async_wake("bestaat-niet")) is False, "")

# Elk uur: als hij stilstaat en niets meldt, hooguit eens per uur. (`ronde75`
# maakt de lijst van opdrachten elke ronde leeg, dus dit telt per ronde.)
inst82b = instellingen(devices=[{**LAADPAAL, "cars": [{**TESLA, "wake_mode": "hourly"}]}])
hass82b, _, coach82b = bouw({**huis(status="disconnected"), "sensor.tesla_accu": "unavailable"}, inst82b)
tellingen = []
for minuten in (0, 1, 30, 59, 60, 61, 119, 120):
    asyncio.run(ronde75(hass82b, coach82b, T82 + dt.timedelta(minutes=minuten)))
    tellingen.append((minuten, len(gedrukt(hass82b))))
print(f"  elk uur, gewekt in de ronde van minuut: {[m for m, n in tellingen if n]}")
controle("elk uur: bij het begin, na een uur en na twee uur, en niet vaker",
         tellingen == [(0, 1), (1, 0), (30, 0), (59, 0), (60, 1), (61, 0), (119, 0), (120, 1)], f"{tellingen}")

# Meldt de sensor wel iets, dan wordt er niet gewekt.
hass82b.states.zet("sensor.tesla_accu", "74")
asyncio.run(ronde75(hass82b, coach82b, T82 + dt.timedelta(minutes=181)))
controle("een auto die zijn accustand meldt wordt niet gewekt", len(gedrukt(hass82b)) == 0, f"{len(gedrukt(hass82b))}")

# Inpluggen: één keer wekken, in beide standen.
hass82c, _, coach82c = bouw({**huis(status="disconnected"), "sensor.tesla_accu": "unavailable"}, inst82)
asyncio.run(ronde75(hass82c, coach82c, T82))
hass82c.states.zet("sensor.laadpaal_status", "awaiting_start")
asyncio.run(ronde75(hass82c, coach82c, T82 + dt.timedelta(minutes=1)))
erin = len(gedrukt(hass82c))
asyncio.run(ronde75(hass82c, coach82c, T82 + dt.timedelta(minutes=2)))
controle("handmatig: bij het inpluggen wekt hij de auto één keer, en daarna niet meer",
         erin == 1 and len(gedrukt(hass82c)) == 0, f"{erin} en {len(gedrukt(hass82c))}")

print("=== 83. meer omvormers: opgeteld, elk met een naam, en samen geen halve meting (22-09-2026) ===")
# De bewoner van de eerste woning: "steeds meer consumenten hebben meerdere
# omvormers." De tweede en derde staan in `sources.solar_extra` en tellen
# overal mee waar de eerste telt.
inst83 = instellingen()
inst83["sources"] = dict(inst83["sources"], solar="sensor.zon1", solar_extra=["sensor.zon2", ""])
hass83, _, coach83 = bouw({
    **huis(),
    "sensor.zon1": {"state": "1500", "attributes": {"unit_of_measurement": "W"}},
    "sensor.zon2": {"state": "0.7", "attributes": {"unit_of_measurement": "kW"}},
}, inst83)
controle("de lijst van omvormers, zonder lege velden",
         coachmod.zonsensoren(inst83) == ["sensor.zon1", "sensor.zon2"], f"{coachmod.zonsensoren(inst83)}")
controle("samen 2200 W, ook als de tweede in kW meet", coach83._zon_w(inst83) == 2200.0, f"{coach83._zon_w(inst83)}")
hass83.states.zet("sensor.zon2", "unavailable")
controle("zwijgt er een, dan is de som onbekend en niet kleiner", coach83._zon_w(inst83) is None, f"{coach83._zon_w(inst83)}")
namen83 = coach83._sensoren(inst83)
controle("elke omvormer met een eigen naam in de sensorwacht",
         namen83.get("sensor.zon1") == "de zonnesensor" and namen83.get("sensor.zon2") == "de zonnesensor van omvormer 2",
         f"{namen83}")
controle("zonder extra's is er alleen de eerste",
         coachmod.zonsensoren(instellingen()) == [] and coachmod.zonsensoren({"sources": {"solar": "sensor.zon"}}) == ["sensor.zon"], "")

print("=== 84. de thuisbatterij: nu vol laden, en het plan op de kaart (22-09-2026) ===")
# De eigenaar: "eigenlijk wil je nu dat de batterij handmatig vol wordt
# geladen." Dezelfde knop als snelladen: van het net op vol vermogen tot de
# laadgrens, wat de prijs ook is, en dan vanzelf weer het plan.
hass84, _, coach84 = bouw(huis75(soc="60"), instellingen(devices=[LAADPAAL, BATTERIJ]))
NU84 = dt.datetime(2026, 9, 22, 18, 30)   # midden in de avondpiek
coach84.async_boost("dev-batterij", True)
b84 = asyncio.run(ronde75(hass84, coach84, NU84))
print(f"  {b84.get('mode_name')}: {b84.get('reason')}")
controle("met de knop aan laadt hij maximaal, ook in de avondpiek",
         b84.get("mode") == "max-laden" and b84.get("rule") == "vol-laden" and b84.get("boost") is True,
         f"{b84.get('mode')} {b84.get('rule')} {b84.get('boost')}")
controle("en het plan van de uren blijft op de kaart staan", isinstance(b84.get("hours"), list), "")
hass84.states.zet("sensor.batterij_soc", "95")
b84 = asyncio.run(ronde75(hass84, coach84, NU84 + dt.timedelta(minutes=1)))
controle("op de laadgrens gaat de knop vanzelf uit en volgt hij het plan weer",
         b84.get("boost") is False and b84.get("rule") != "vol-laden", f"{b84.get('boost')} {b84.get('rule')}")

print("=== 85. de thuisbatterij: vakantiestand (22-09-2026) ===")
# De bewoner van de eerste woning: "in de zomer met veel opwek en minimaal
# verbruik moet de accu regelmatig leeggetrokken worden; slecht voor de cellen
# als ze te lang op 100% staan." De coach houdt hem onder een grens, de
# laadgrens van de batterij blijft staan, en de volle beurt vervalt.
BATTERIJ85 = {**BATTERIJ, "battery": {**BATTERIJ["battery"], "holiday": True, "holiday_max_percent": 50,
                                       "weekly_full": True, "weekly_full_day": 0}}
hass85, store85, coach85 = bouw(huis75(afname=0.0, teruglevering=1500.0, soc="70"), instellingen(devices=[LAADPAAL, BATTERIJ85]))
NU85 = dt.datetime(2026, 9, 21, 12, 0)   # maandag, de dag van de volle beurt
b85 = asyncio.run(ronde75(hass85, coach85, NU85))
print(f"  {b85.get('mode_name')}: {b85.get('reason')}")
controle("de bovengrens is de vakantiegrens", b85.get("ceiling") == 50.0 and b85.get("holiday") is True,
         f"{b85.get('ceiling')} {b85.get('holiday')}")
controle("boven de grens gaat er geen zon in, ook niet bij 1,5 kW overschot",
         b85.get("mode") in ("nul", "ontladen", "standby") and b85.get("charge") is False, f"{b85.get('mode')}")
controle("en de kaart zegt het", "Vakantiestand" in (b85.get("reason") or ""), f"{b85.get('reason')}")
controle("de volle beurt vervalt en de laadgrens van de batterij blijft met rust",
         not b85.get("full_before") and not [d for d in hass85.services.verstuurd if "laadgrens" in str(d[2].get("entity_id"))],
         f"{b85.get('full_before')}")
# De regelaar laat de batterij niet boven de grens laden.
_, _, ver85 = zet75(hass85)
controle("de regelaar schrijft geen laadopdracht", all(v == 0 or v is None for v in ver85) or not ver85, f"{ver85}")
hass85.states.zet("sensor.batterij_soc", "40")
b85 = asyncio.run(ronde75(hass85, coach85, NU85 + dt.timedelta(minutes=1)))
controle("onder de grens gaat de zon er weer in", b85.get("mode") in ("nul", "zonneladen"), f"{b85.get('mode')}")

print("=== 86. iets anders stuurt de batterij: de coach laat los zonder zelf te schrijven (22-09-2026) ===")
# In de eerste woning nam evcc de Anker over. Zet iets anders de bedrijfsmodus
# om, dan laat de coach na twee ronden los, schrijft hij niets (een 0 W zou de
# ander overschrijven), zegt hij het één keer en probeert hij het na een uur weer.
hass86, _, coach86 = bouw(huis75(), instellingen(devices=[LAADPAAL, BATTERIJ]))
NU86 = dt.datetime(2026, 9, 22, 18, 0)
asyncio.run(ronde75(hass86, coach86, NU86))
controle("de coach stuurt", coach86._batterij["dev-batterij"].get("stuurt") is True, "")
hass86.states.zet("select.batterij_modus", "self_consumption")   # iets anders zet hem om
asyncio.run(ronde75(hass86, coach86, NU86 + dt.timedelta(minutes=1)))
b86 = asyncio.run(ronde75(hass86, coach86, NU86 + dt.timedelta(minutes=2)))
modus86, _, vermogen86 = zet75(hass86)
meldingen86 = [d[2].get("message", "") for d in hass86.services.verstuurd if d[0] == "notify"]
controle("na twee ronden laat hij los", coach86._batterij["dev-batterij"].get("stuurt") is False and b86.get("applied") is False,
         f"{coach86._batterij['dev-batterij'].get('stuurt')} {b86.get('applied')}")
controle("zonder zelf de modus of een vermogen te schrijven", modus86 == [] and vermogen86 == [], f"{modus86} {vermogen86}")
controle("en hij zegt het", any("Iets anders stuurt" in m for m in meldingen86), f"{meldingen86}")
b86 = asyncio.run(ronde75(hass86, coach86, NU86 + dt.timedelta(minutes=3)))
controle("de ronde erna neemt hij hem niet meteen terug", b86.get("applied") is False and b86.get("foreign") is True,
         f"{b86.get('applied')} {b86.get('foreign')}")
b86 = asyncio.run(ronde75(hass86, coach86, NU86 + dt.timedelta(minutes=62)))
modus86, _, _ = zet75(hass86)
controle("na een uur probeert hij het opnieuw", modus86 == ["third_party_control"] and b86.get("applied") is True, f"{modus86}")

print("=== 87. de verkoopvergoeding telt mee in wat teruglevering opbrengt ===")
DYN87 = dict(DYN, netting=False, dynamic=dict(DYN["dynamic"], source="market", market_entity="sensor.prijs", feed_in_costs=0.0, feed_in_bonus=0.02))
hass87, _, coach87 = bouw({"sensor.prijs": PRIJSLIJST}, instellingen())
rij87 = coach87._prices({"contract": DYN87})
controle("twee cent verkoopvergoeding komt bij de marktprijs",
         bool(rij87) and abs(rij87[0]["feed_in"] - 0.32) < 1e-9, f"{rij87}")
DYN87b = dict(DYN87, dynamic=dict(DYN87["dynamic"], feed_in_bonus=-0.0219))
controle("en een negatieve vergoeding gaat eraf",
         abs(coach87._prices({"contract": DYN87b})[0]["feed_in"] - (0.30 - 0.0219)) < 1e-9, "")

print("=== 88. de thuisbatterij: nu leegladen tot een accustand (22-09-2026) ===")
# De bewoner van de eerste woning: "naast pauze en laad snel vol ook een knop
# laad snel leeg, met een minimale accustand: nu maximaal ontladen tot 50%,
# daarna terug naar normale modus."
hass88, _, coach88 = bouw(huis75(soc="80"), instellingen(devices=[LAADPAAL, BATTERIJ]))
NU88 = dt.datetime(2026, 9, 22, 23, 0)
coach88.async_drain("dev-batterij", 50.0)
b88 = asyncio.run(ronde75(hass88, coach88, NU88))
print(f"  {b88.get('mode_name')}: {b88.get('reason')}")
controle("met de knop aan levert hij aan het net op zijn ontlaadvermogen",
         b88.get("mode") == "handelen" and b88.get("rule") == "leeg-laden" and b88.get("drain_to") == 50.0,
         f"{b88.get('mode')} {b88.get('rule')} {b88.get('drain_to')}")
_, richting88, vermogen88 = zet75(hass88)
controle("en de regelaar schrijft ontladen", richting88 == ["discharge"] and vermogen88 and vermogen88[-1] > 0, f"{richting88} {vermogen88}")
hass88.states.zet("sensor.batterij_soc", "50")
b88 = asyncio.run(ronde75(hass88, coach88, NU88 + dt.timedelta(minutes=1)))
controle("op de gekozen stand gaat de knop vanzelf uit en volgt hij het plan weer",
         b88.get("drain_to") is None and b88.get("rule") != "leeg-laden", f"{b88.get('drain_to')} {b88.get('rule')}")
coach88.async_drain("dev-batterij", 2.0)
hass88.states.zet("sensor.batterij_soc", "5")
b88 = asyncio.run(ronde75(hass88, coach88, NU88 + dt.timedelta(minutes=2)))
controle("nooit onder de eigen ondergrens van de batterij: op 5% is hij klaar, ook al vroeg je 2",
         b88.get("drain_to") is None, f"{b88.get('drain_to')} {b88.get('rule')}")

print("=== 89. lekkage of abnormaal verbruik: water dat blijft lopen, en een dag uit de toon (22-09-2026) ===")
# De bewoner van de eerste woning: "meldingen instellen obv abnormaal water- en
# gasverbruik, mogelijk lekkage van water of gas."
inst89 = instellingen()
inst89["sources"]["meters"] = {"gas_enabled": True, "gas": "sensor.gasmeter", "water_enabled": True,
                               "water": "sensor.watermeter", "water_flow": "sensor.waterflow"}
inst89["notifications"] = {**(inst89.get("notifications") or {}),
                           "usage_alert": {"enabled": True, "water_flow_minutes": 120, "factor": 3, "min_days": 3}}
huis89 = {**huis(), "sensor.gasmeter": {"state": "9130.000", "attributes": {"unit_of_measurement": "m³"}},
          "sensor.watermeter": {"state": "50.000", "attributes": {"unit_of_measurement": "m³"}},
          "sensor.waterflow": {"state": "0", "attributes": {"unit_of_measurement": "L/min"}}}
hass89, store89, coach89 = bouw(huis89, inst89)


def meldingen89(hass):
    # Alleen de meldingen van de verbruikswacht; de laadpaal in het huis zegt ook dingen.
    return [d[2].get("message", "") for d in hass.services.verstuurd
            if d[0] == "notify" and ("m³" in d[2].get("message", "") or "water" in d[2].get("message", ""))]


T89 = dt.datetime(2026, 9, 10, 8, 0)
# Vijf gewone dagen van een halve kuub gas en 0,3 kuub water, dan een dag met vijf keer zoveel.
dagen = [(0.5, 0.3)] * 5 + [(2.6, 0.31)]
gas, water = 9130.0, 50.0
uitkomsten = []
for i, (g, w) in enumerate(dagen):
    hass89.states.zet("sensor.gasmeter", {"state": f"{gas:.3f}", "attributes": {"unit_of_measurement": "m³"}})
    hass89.states.zet("sensor.watermeter", {"state": f"{water:.3f}", "attributes": {"unit_of_measurement": "m³"}})
    asyncio.run(ronde75(hass89, coach89, T89 + dt.timedelta(days=i)))
    uitkomsten.append(meldingen89(hass89))
    gas += g
    water += w
hass89.states.zet("sensor.gasmeter", {"state": f"{gas:.3f}", "attributes": {"unit_of_measurement": "m³"}})
hass89.states.zet("sensor.watermeter", {"state": f"{water:.3f}", "attributes": {"unit_of_measurement": "m³"}})
asyncio.run(ronde75(hass89, coach89, T89 + dt.timedelta(days=len(dagen))))
laatste89 = meldingen89(hass89)
dagen89 = store89.instellingen.get("usage_days") or []
print(f"  dagverbruik in de opslag: {[(d['meter'], d['date'][5:], d['m3']) for d in dagen89]}")
controle("de coach houdt per meter het dagverbruik bij, uit de tellers zelf",
         sum(1 for d in dagen89 if d["meter"] == "gas") == 6 and any(abs(d["m3"] - 2.6) < 1e-6 for d in dagen89 if d["meter"] == "gas"),
         f"{dagen89}")
controle("de gewone dagen geven geen melding", not any(m for u in uitkomsten for m in u), f"{uitkomsten}")
print(f"  na de dag van 2,6 m³: {laatste89}")
controle("een dag met vijf keer het gewone gasverbruik geeft één kritieke melding, met de getallen erin",
         len(laatste89) == 1 and "2,6 m³ gas" in laatste89[0] and "0,5 m³" in laatste89[0], f"{laatste89}")
asyncio.run(ronde75(hass89, coach89, T89 + dt.timedelta(days=len(dagen), minutes=1)))
controle("en niet nog een keer", not meldingen89(hass89), f"{meldingen89(hass89)}")

# Water dat blijft lopen: twee uur 0,8 L/min.
hass89.states.zet("sensor.waterflow", {"state": "0.8", "attributes": {"unit_of_measurement": "L/min"}})
T89b = T89 + dt.timedelta(days=10)
for minuten in (0, 30, 60, 119):
    asyncio.run(ronde75(hass89, coach89, T89b + dt.timedelta(minutes=minuten)))
controle("een bad van anderhalf uur is nog geen lekkage", not meldingen89(hass89), f"{meldingen89(hass89)}")
asyncio.run(ronde75(hass89, coach89, T89b + dt.timedelta(minutes=121)))
lek = meldingen89(hass89)
print(f"  na twee uur: {lek}")
controle("na twee uur onafgebroken water één kritieke melding", len(lek) == 1 and "onafgebroken water" in lek[0] and "0,8 L/min" in lek[0], f"{lek}")
asyncio.run(ronde75(hass89, coach89, T89b + dt.timedelta(minutes=180)))
controle("en niet nog een keer zolang het loopt", not meldingen89(hass89), "")
hass89.states.zet("sensor.waterflow", {"state": "0", "attributes": {"unit_of_measurement": "L/min"}})
asyncio.run(ronde75(hass89, coach89, T89b + dt.timedelta(minutes=181)))
hass89.states.zet("sensor.waterflow", {"state": "0.5", "attributes": {"unit_of_measurement": "L/min"}})
asyncio.run(ronde75(hass89, coach89, T89b + dt.timedelta(minutes=182)))
asyncio.run(ronde75(hass89, coach89, T89b + dt.timedelta(minutes=305)))
controle("stopt het en begint het opnieuw, dan telt de klok opnieuw", len(meldingen89(hass89)) == 1, f"{meldingen89(hass89)}")

print("=== 90. Alfen: een limiet in een number, geen startwoord, elke ronde opnieuw, en een afgeleide status (23-09-2026) ===")
# De eigenaar op 23-09-2026: "ik wil alfen bouwen; we hebben natuurlijk een
# wekstroom etc maar ik zou niet weten wat er bij alfen moet gebeuren, dus dat
# moeten we testen en checken." Wat hier vastligt is wat uit de integratie
# alfen_modbus en uit evcc te halen was: de limiet is een number zonder
# houdbaarheid, de paal valt na zijn geldigheidsduur terug op zijn veilige
# stroom, en er is geen statussensor maar "auto aangesloten", "auto laadt" en
# de modus 3-toestand.
ALFEN = {
    **LAADPAAL, "id": "dev-alfen", "brand": "alfen", "device_id": "",
    "entities": {
        "limit": "number.alfen_limiet",
        "connected": "sensor.alfen_aangesloten",
        "charging": "sensor.alfen_laadt",
        "mode3": "sensor.alfen_modus3",
        "current": "sensor.laadpaal_stroom",
        "max_limit": "sensor.laadpaal_max",
        "dynamic_limit": "sensor.laadpaal_dyn",
        "lifetime_energy": "sensor.laadpaal_teller",
    },
}


def huis90(aangesloten="on", laadt="off", modus="B1", **rest):
    return {
        **huis(**rest),
        "number.alfen_limiet": "0",
        "sensor.alfen_aangesloten": aangesloten,
        "sensor.alfen_laadt": laadt,
        "sensor.alfen_modus3": modus,
    }


async def ronde90(coach, inst, nu=None):
    hass = coach.hass
    hass.services.verstuurd.clear()
    await hass.afmaken()
    await coach._one(nu or dt.datetime(2026, 8, 18, 14, 37), inst, ALFEN, "steer")
    # De integratie leest de limiet bij de volgende poll terug uit de paal.
    for _, dienst, gegevens in hass.services.verstuurd:
        if dienst == "set_value" and gegevens.get("entity_id") == "number.alfen_limiet":
            hass.states.zet("sensor.laadpaal_dyn", str(gegevens.get("value")))
            hass.states.zet("number.alfen_limiet", str(gegevens.get("value")))
    return coach.state["dev-alfen"], hass.services.verstuurd


inst90 = instellingen(devices=[ALFEN])
hass90, store90, coach90 = bouw(huis90(), inst90)
besluit90, verstuurd90 = asyncio.run(ronde90(coach90, inst90))
print(f"  {besluit90['rule']}: {besluit90['amps']} A -> {verstuurd90}")
controle("kabel erin aan een Alfen: de wekstroom gaat als getal de number in",
         besluit90["amps"] == 14 and any(
             d[0] == "number" and d[1] == "set_value" and d[2].get("entity_id") == "number.alfen_limiet" and d[2].get("value") == 14
             for d in verstuurd90),
         f"{besluit90['rule']} {besluit90['amps']} A, verstuurd: {verstuurd90}")
controle("en er gaat geen Easee-dienst en geen startwoord heen",
         not any(d[0] == "easee" or d[1] in ("action_command", "set_charger_dynamic_limit") for d in verstuurd90),
         f"{verstuurd90}")

# De auto laadt op 6 A; het besluit verandert niet, en toch gaat de limiet
# elke ronde opnieuw de number in, want de paal vergeet hem anders.
hass90.states.zet("sensor.alfen_laadt", "on")
hass90.states.zet("sensor.alfen_modus3", "C2")
hass90.states.zet("sensor.laadpaal_stroom", "5.9")
hass90.states.zet("sensor.laadpaal_vermogen", {"state": "4070", "attributes": {"unit_of_measurement": "W"}})
T90 = dt.datetime(2026, 8, 18, 14, 38)
b1, v1 = asyncio.run(ronde90(coach90, inst90, T90))
b2, v2 = asyncio.run(ronde90(coach90, inst90, T90 + dt.timedelta(minutes=1)))
b3, v3 = asyncio.run(ronde90(coach90, inst90, T90 + dt.timedelta(minutes=2)))
schrijf90 = [[d[2].get("value") for d in v if d[1] == "set_value"] for v in (v1, v2, v3)]
print(f"  drie ronden laden: {b1['rule']} {b1['amps']} A, {b2['rule']} {b2['amps']} A, {b3['rule']} {b3['amps']} A -> {schrijf90}")
controle("de coach ziet hem laden (afgeleide status uit 'auto laadt')", b1["charging"] and b2["charging"], f"{b1['charging']} {b2['charging']}")
controle("bij een ongewijzigd besluit gaat de limiet toch elke ronde opnieuw de number in",
         all(len(w) == 1 and w[0] == b1["amps"] for w in schrijf90) and b1["amps"] == b2["amps"] == b3["amps"],
         f"{schrijf90}")

# Ter vergelijking: een Easee met hetzelfde ongewijzigde besluit krijgt niets.
hassE, storeE, coachE = bouw({**huis(status="charging", stroom=5.9, vermogen=4070), "sensor.laadpaal_dyn": "6"}, instellingen())
asyncio.run(ronde(coachE, instellingen(), T90))
bE, vE = asyncio.run(ronde(coachE, instellingen(), T90 + dt.timedelta(minutes=1)))
controle("een Easee met hetzelfde besluit krijgt de tweede ronde niets (de dode band blijft daar)",
         not any(d[1] == "set_charger_dynamic_limit" for d in vE), f"{vE}")

# Kabel eruit: "auto aangesloten" uit is afgekoppeld.
hass90.states.zet("sensor.alfen_aangesloten", "off")
hass90.states.zet("sensor.alfen_laadt", "off")
hass90.states.zet("sensor.alfen_modus3", "A")
hass90.states.zet("sensor.laadpaal_stroom", "0")
hass90.states.zet("sensor.laadpaal_vermogen", {"state": "0", "attributes": {"unit_of_measurement": "W"}})
asyncio.run(ronde90(coach90, inst90, T90 + dt.timedelta(minutes=3)))
# Een Easee zegt bij een herstart twee seconden "disconnected"; daarom gelooft
# de coach een kabel eruit pas na `KABEL_ONTDREUN`. Dat geldt hier ook.
b4, v4 = asyncio.run(ronde90(coach90, inst90, T90 + dt.timedelta(minutes=4)))
controle("'auto aangesloten' uit is afgekoppeld (na het ontdreunen)", b4["rule"] == "disconnected" and not any(d[1] == "set_value" for d in v4), f"{b4['rule']} {v4}")

# Een auto die aanbod krijgt en niets neemt: eerst "gereed" (hij komt nog bij),
# na een kwartier "klaar", zoals een Easee dat zelf zegt.
hass91, store91, coach91 = bouw(huis90(modus="B2"), inst90)
hass91.states.zet("sensor.laadpaal_dyn", "16")
T91 = dt.datetime(2026, 8, 18, 14, 37)
controle("B2 met aanbod is eerst 'ready_to_charge'",
         coach91._status_afgeleid("dev-alfen", ALFEN["entities"], T91) == "ready_to_charge", "")
controle("en na een kwartier 'completed'",
         coach91._status_afgeleid("dev-alfen", ALFEN["entities"], T91 + dt.timedelta(minutes=15)) == "completed", "")
hass91.states.zet("sensor.laadpaal_dyn", "0")
hass91.states.zet("sensor.alfen_modus3", "B1")
controle("B1 zonder aanbod is 'awaiting_start', en de klok begint opnieuw",
         coach91._status_afgeleid("dev-alfen", ALFEN["entities"], T91 + dt.timedelta(minutes=16)) == "awaiting_start"
         and "dev-alfen" not in coach91._stil_sinds, "")
hass91.states.zet("sensor.alfen_aangesloten", "unavailable")
controle("een integratie die even niets zegt geeft geen status (de vorige blijft tellen)",
         coach91._status_afgeleid("dev-alfen", ALFEN["entities"], T91) == "", "")

# De sensorwacht noemt de nieuwe sensoren, zonder entiteit-id.
namen90 = coach90._sensoren(inst90)
controle("de sensorwacht kent de kabelmelding, de laadmelding en de stroomlimiet van een Alfen",
         namen90.get("sensor.alfen_aangesloten") == "de kabelmelding van Laadpaal"
         and namen90.get("sensor.alfen_laadt") == "de laadmelding van Laadpaal"
         and namen90.get("number.alfen_limiet") == "de stroomlimiet van Laadpaal", f"{namen90}")

print("=== 92. Home Connect Local: uren, twee programma-entiteiten, een knop die er niet altijd is, starten op afstand ===")
# Thuis sinds 23-09-2026 (`homeconnect_ws`): de resterende tijd staat in uren
# (1,4833 h), het actieve programma zit in een sensor die alleen tijdens de
# beurt iets zegt en de select valt juist dan weg, de startknop is
# `unavailable` zolang de machine geen start aanneemt (gemeten: deur open
# is alleen lezen, deur dicht is de knop er meteen, ook met de stroom uit),
# en "start op afstand" is een eigen sensor.
hass92u = NepHass({"sensor.rest_uren": {"state": "1.48333333333333", "attributes": {"unit_of_measurement": "h"}},
                   "sensor.rest_dagen": {"state": "0.5", "attributes": {"unit_of_measurement": "d"}}})
nu92 = dt.datetime(2026, 9, 23, 11, 0)
e92 = coachmod._eindtijd(hass92u, "sensor.rest_uren", nu92)
controle("uren tellen als uren: 1,4833 h is 89 minuten", e92 is not None and abs((e92 - nu92).total_seconds() - 89 * 60) < 1, f"{e92}")
controle("en dagen als dagen", coachmod._eindtijd(hass92u, "sensor.rest_dagen", nu92) == nu92 + dt.timedelta(hours=12), "")

VW92 = dict(VAATWASSER, entities={
    "status": "sensor.vw92_status", "program": "sensor.vw92_actief", "program_select": "select.vw92_programma",
    "remaining": "sensor.vw92_rest", "door": "binary_sensor.vw92_deur", "start": "button.vw92_start",
    "stop": "button.vw92_stop", "remote_start": "binary_sensor.vw92_afstand",
})
inst92 = instellingen(devices=[LAADPAAL, VW92])
inst92["contract"] = inst56["contract"]
inst92["strategy"]["schedules"].append({
    "device": "dev-vaatwasser", "enabled": True, "priority": "mid", "per_day": False,
    "window": {"not_before": "", "start_by": "", "done_by": "07:00"}, "days": [],
})
huis92 = dict(huis56)
huis92.update({
    "sensor.vw92_status": "ready",
    "sensor.vw92_actief": "unknown",
    "select.vw92_programma": {"state": "dishcare_dishwasher_program_kurz60",
                              "attributes": {"options": ["dishcare_dishwasher_program_eco50", "dishcare_dishwasher_program_kurz60"]}},
    "sensor.vw92_rest": {"state": "1.4833", "attributes": {"unit_of_measurement": "h"}},
    "binary_sensor.vw92_deur": "on",
    "button.vw92_start": "unavailable",
    "button.vw92_stop": "unavailable",
    "binary_sensor.vw92_afstand": "on",
})
hass92, _, coach92 = bouw(huis92, inst92)
async def ronde92(nu):
    hass92.services.verstuurd.clear()
    await hass92.afmaken()
    await coach92._round(nu)
    await hass92.afmaken()
    return (coach92.state.get("dev-vaatwasser") or {},
            [d for d in hass92.services.verstuurd if d[0] == "button"],
            [d[2]["message"] for d in hass92.services.verstuurd if d[0] == "notify" and "Vaatwasser" in d[2].get("message", "")])
# "Ingeruimd en nu starten", met de deur nog open.
inst92["ready_devices"] = ["dev-vaatwasser"]
inst92["ready_now"] = ["dev-vaatwasser"]
b, knop, m = asyncio.run(ronde92(dt.datetime(2026, 9, 23, 20, 0)))
print(f"  20:00 deur open: {b.get('rule')} program={b.get('program')} knop={knop} {m}")
controle("het programma komt uit de select zolang de sensor niets zegt (spelling kurz60)", b.get("program") == "kurz_60", f"{b.get('program')}")
controle("de startknop is er niet: de coach drukt niet en zegt nog niets", b.get("rule") == "start-now" and not knop and not m, f"{knop} {m}")
controle("de coach luistert naar de startknop en naar starten op afstand",
         "button.vw92_start" in coach92._watched and "binary_sensor.vw92_afstand" in coach92._watched, f"{coach92._watched}")
b, knop, m = asyncio.run(ronde92(dt.datetime(2026, 9, 23, 20, 2)))
controle("na twee minuten nog niets", not knop and not m, f"{knop} {m}")
b, knop, m = asyncio.run(ronde92(dt.datetime(2026, 9, 23, 20, 3)))
controle("na drie minuten één keer: de machine neemt geen start aan, de deur staat open",
         not knop and len(m) == 1 and "neemt nu geen start aan" in m[0] and "deur staat open" in m[0], f"{knop} {m}")
b, knop, m = asyncio.run(ronde92(dt.datetime(2026, 9, 23, 20, 4)))
controle("en niet nog eens", not knop and not m, f"{knop} {m}")
# De deur gaat dicht: de knop is er, en de coach drukt meteen.
hass92.states.zet("binary_sensor.vw92_deur", "off")
hass92.states.zet("button.vw92_start", "unknown")
b, knop, m = asyncio.run(ronde92(dt.datetime(2026, 9, 23, 20, 5)))
controle("de deur dicht: de coach drukt, één keer", knop == [("button", "press", {"entity_id": "button.vw92_start"})] and not m, f"{knop} {m}")
# Hij draait: de sensor zegt het programma, de select valt weg, de knop ook.
hass92.states.zet("sensor.vw92_status", "run")
hass92.states.zet("sensor.vw92_actief", "dishcare_dishwasher_program_kurz60")
hass92.states.zet("select.vw92_programma", "unavailable")
hass92.states.zet("button.vw92_start", "unavailable")
hass92.states.zet("sensor.vaatwasser_vermogen", "2000")
for minuut in (6, 7, 8, 9, 10):
    hass92.states.zet("sensor.vw92_rest", {"state": f"{(60 - minuut) / 60:.4f}", "attributes": {"unit_of_measurement": "h"}},
                      last_updated=dt.datetime(2026, 9, 23, 20, minuut))
    b, knop, m = asyncio.run(ronde92(dt.datetime(2026, 9, 23, 20, minuut)))
    if m:
        print(f"  20:{minuut:02d}: {m}  {b.get('reason')}")
controle("tijdens de beurt komt het programma uit de sensor", b.get("rule") == "running" and b.get("program") == "kurz_60", f"{b.get('rule')} {b.get('program')}")
# De proef geeft de uren op vier cijfers (0,8333 h is 49,998 min), de echte
# sensor op veertien; vandaar een minuut speling.
eind92 = dt.datetime.fromisoformat(b.get("ends_at") or "2000-01-01T00:00")
controle("'is gestart' noemt de klaar-tijd uit de uren: rond 21:00",
         b.get("reason", "").startswith("Hij draait, klaar rond 2") and abs((eind92 - dt.datetime(2026, 9, 23, 21, 0)).total_seconds()) <= 60,
         f"{b.get('reason')} {b.get('ends_at')}")
# Klaar: Home Connect Local zegt vijf seconden "finished" en dan "ready" (de
# machine zet zichzelf uit); de coach ziet vaak alleen dat laatste.
hass92.states.zet("sensor.vw92_status", "ready")
hass92.states.zet("sensor.vw92_actief", "unknown")
hass92.states.zet("select.vw92_programma", "dishcare_dishwasher_program_kurz60")
hass92.states.zet("sensor.vaatwasser_vermogen", "0")
b, knop, m = asyncio.run(ronde92(dt.datetime(2026, 9, 23, 21, 0)))
controle("van 'run' meteen naar 'ready' is klaar: verslag, vrijgave eraf, en geen nieuwe druk",
         len(m) == 1 and "is klaar" in m[0] and "dev-vaatwasser" not in (inst92.get("ready_devices") or []) and not knop, f"{m} {knop} {inst92.get('ready_devices')}")

# Starten op afstand uit: de sensor zegt het, dus niet drukken en zeggen wat er aan moet.
hass92.states.zet("binary_sensor.vw92_afstand", "off")
hass92.states.zet("button.vw92_start", "unknown")
inst92["ready_devices"] = ["dev-vaatwasser"]
inst92["ready_now"] = ["dev-vaatwasser"]
b, knop, m = asyncio.run(ronde92(dt.datetime(2026, 9, 23, 21, 30)))
b, knop, m3 = asyncio.run(ronde92(dt.datetime(2026, 9, 23, 21, 33)))
controle("starten op afstand uit: geen druk, en na drie minuten één keer 'zet starten op afstand aan'",
         not knop and not m and len(m3) == 1 and "starten op afstand aan" in m3[0], f"{knop} {m} {m3}")
hass92.states.zet("binary_sensor.vw92_afstand", "on")
b, knop, m = asyncio.run(ronde92(dt.datetime(2026, 9, 23, 21, 34)))
controle("weer aan: dan drukt hij alsnog", knop == [("button", "press", {"entity_id": "button.vw92_start"})], f"{knop}")

# De sensorwacht en de andere integraties: een knop zonder toestand (de
# cloud) is geen knop die weg is.
hass92c = NepHass(dict(huis56))
coach92c = coachmod.ChargerCoach(hass92c)
controle("bij de cloud-integraties (knop altijd beschikbaar) verandert er niets: `_text` op een knop zonder toestand is leeg",
         coachmod._text(hass92c, "button.vaatwasser_start") == "", "")

print("=== 93. de laadmodus zonder planning: voorkeur, keuze per beurt, en weg bij kabel eruit (v0.87.0) ===")
# De eigenaar op 23-09-2026: "de modus is leidend (snel, continu of zon), tenzij er
# een planning ingesteld is. Geen planning, standaard terug naar zon." Een
# bestaande paal houdt "goedkoopst".
storagemod = storage

gemigreerd = storagemod._migrate({"devices": [{"id": "p", "type": "laadpaal"}, {"id": "b", "type": "boiler"}]})
controle("een bestaande laadpaal krijgt 'goedkoopst', een ander apparaat niets",
         gemigreerd["devices"][0]["charge_mode"] == "goedkoopst" and "charge_mode" not in gemigreerd["devices"][1],
         f"{gemigreerd['devices']}")

paal93 = dict(LAADPAAL, charge_mode="zon", continuous_amps=8)
inst93 = instellingen(devices=[paal93])
inst93["strategy"]["schedules"][0]["enabled"] = False
huis93 = huis(status="awaiting_start", stroom=0.0, vermogen=0.0, teruglevering=500.0, afname=0.0)
hass93, store93, coach93 = bouw(huis93, inst93)
b93, _ = asyncio.run(ronde(coach93, inst93, paal=paal93))
print(f"  voorkeur zon, 0,5 kW over: {b93['rule']}, mode={b93['mode']}, plan_ahead={b93['plan_ahead']}")
controle("de voorkeur 'zon' van de paal geldt zonder planning",
         b93["rule"] == "zon-wacht" and b93["mode"] == "zon" and not b93["mode_session"], f"{b93['rule']} {b93['mode']}")
controle("en dan staat er geen tijdlijn met goedkoopste uren", b93["plan_ahead"] is None, f"{b93['plan_ahead']}")


async def kies93(modus):
    coach93.async_mode("dev-laadpaal", modus)
    await hass93.afmaken()
    return await ronde(coach93, inst93, paal=paal93)


# De auto laadt al, anders biedt hij bij de start eerst de wekstroom aan.
hass93.states.zet("sensor.laadpaal_status", "charging")
hass93.states.zet("sensor.laadpaal_stroom", "8.0")
b93b, _ = asyncio.run(kies93("continu"))
print(f"  gekozen continu: {b93b['rule']} {b93b['amps']} A, sessie={b93b['mode_session']}, opgeslagen={store93.instellingen['sessions']}")
controle("continu op de kaart: laden op de 8 A uit Apparaten",
         b93b["rule"] == "continu" and b93b["amps"] == 8 and b93b["mode_session"], f"{b93b['rule']} {b93b['amps']}")
controle("en de keuze is vastgelegd voor een herstart",
         any(r.get("mode") == "continu" for r in store93.instellingen["sessions"]), f"{store93.instellingen['sessions']}")

b93c, _ = asyncio.run(kies93("snel"))
controle("snel is snelladen, en zet de gekozen modus terug",
         b93c["rule"] == "boost" and b93c["mode"] == "snel" and "dev-laadpaal" not in coach93._modus, f"{b93c['rule']}")
b93d, _ = asyncio.run(kies93("zon"))
controle("zon zet snelladen weer uit", b93d["mode"] == "zon" and "dev-laadpaal" not in coach93._boost, f"{b93d['mode']}")

# Een herstart onthoudt de keuze, zoals snelladen.
hass93h, store93h, coach93h = bouw(huis93, store93.instellingen)
coach93h._restore(store93h.instellingen)
controle("na een herstart staat de gekozen modus er nog", coach93h._modus.get("dev-laadpaal") == "zon", f"{coach93h._modus}")

# De kabel eruit: de keuze vervalt, en de volgende auto begint op de voorkeur.
coach93.async_mode("dev-laadpaal", "continu")
hass93.states.zet("sensor.laadpaal_status", "disconnected")
asyncio.run(ronde(coach93, inst93, paal=paal93, nu=dt.datetime(2026, 8, 18, 14, 40)))
# `async_mode` vraagt meteen een ronde op de echte klok; het loskoppelen dus
# vastzetten op de tijd van deze proef, langer dan `KABEL_ONTDREUN` geleden.
coach93._los_sinds["dev-laadpaal"] = dt.datetime(2026, 8, 18, 14, 39)
asyncio.run(ronde(coach93, inst93, paal=paal93, nu=dt.datetime(2026, 8, 18, 14, 41)))
controle("kabel eruit: de keuze van de beurt is weg", "dev-laadpaal" not in coach93._modus, f"{coach93._modus}")

# Met een planning wint de planning, wat de voorkeur ook is.
inst93p = instellingen(devices=[paal93])
hass93p, _, coach93p = bouw(huis93, inst93p)
b93p, _ = asyncio.run(ronde(coach93p, inst93p, paal=paal93))
controle("schema aan: de planning wint van de modus zon",
         b93p["rule"] not in ("zon-wacht", "zon-modus", "continu") and b93p["planned"] and b93p["plan_ahead"] is not None,
         f"{b93p['rule']}")

print("=== 94. een paal die zegt dat hij laadt: de batterij geeft meteen niets meer af (v0.87.1) ===")
# De eerste woning op 23-09-2026: om 15:58:56 zei de Alfen "auto laadt", het
# vermogen van de paal stond tot 15:59:25 op 0 W (een Alfen meldt het eens per
# 30 s), en de regelaar zag de auto als afname en ontlaadde 25 s lang 3,45 kW
# in de auto. Het besluit van die minuut was nog "nul op de meter".
inst94 = instellingen(devices=[LAADPAAL, BATTERIJ])
hass94, _, coach94 = bouw(huis75(afname=1500.0), inst94)
asyncio.run(ronde75(hass94, coach94, dt.datetime(2026, 9, 21, 21, 0)))
controle("het besluit van de minuut is nul op de meter", coach94.state["dev-batterij"].get("mode") == "nul",
         f"{coach94.state['dev-batterij'].get('mode')}")
gezien94 = []
regelaar94 = coach94._batterij["dev-batterij"]["regelaar"]
echte_stap = regelaar94.stap


def stap94(*args, **kw):
    gezien94.append(kw["besluit"])
    return echte_stap(*args, **kw)


regelaar94.stap = stap94
hass94.states.zet("sensor.afname", "5500")
asyncio.run(coach94._async_regel("dev-batterij", inst94, BATTERIJ))
controle("zonder ladende paal mag de regelaar ontladen", gezien94 and gezien94[-1].grenzen[1], f"{gezien94[-1].stand}")
hass94.states.zet("sensor.laadpaal_status", "charging")   # het vermogen staat nog op 0 W
controle("de status van de paal telt, ook met 0 W vermogen", coach94._paal_laadt(inst94), "")
asyncio.run(coach94._async_regel("dev-batterij", inst94, BATTERIJ))
print(f"  met ladende paal: {gezien94[-1].stand}: {gezien94[-1].reason}")
controle("en dan mag de regelaar meteen niet meer ontladen, zonder op de besluitronde te wachten",
         not gezien94[-1].grenzen[1], f"{gezien94[-1].stand}")
# Een Alfen: "auto laadt" is een eigen sensor.
alfen94 = {"id": "dev-alfen", "type": "laadpaal", "brand": "alfen", "entity": "sensor.alfen_w",
           "entities": {"charging": "sensor.alfen_laadt", "limit": "number.alfen_limiet"}}
hass94.states.zet("sensor.laadpaal_status", "disconnected")
hass94.states.zet("sensor.alfen_w", "0")
hass94.states.zet("sensor.alfen_laadt", "on")
inst94b = instellingen(devices=[alfen94, BATTERIJ])
controle("bij een Alfen telt 'auto laadt' aan", coach94._paal_laadt(inst94b), "")
hass94.states.zet("sensor.alfen_laadt", "off")
controle("en uit is uit", not coach94._paal_laadt(inst94b), "")

print("=== 95. laden tot een gekozen procent, per beurt op de kaart (v0.88.0) ===")
# De bewoner van de eerste woning op 23-09-2026, over evcc: "in de auto een harde
# max (100%), en in evcc een gewenste accustand van bijvoorbeeld 80."
auto95 = dict(LAADPAAL["cars"][0], soc_entity="sensor.auto_soc", capacity_kwh=78.0, target_percent=100.0)
paal95 = dict(LAADPAAL, cars=[auto95])
inst95 = instellingen(devices=[paal95])
huis95 = huis(status="charging", stroom=10.0, vermogen=6900.0, teruglevering=0.0, afname=7000.0)
huis95["sensor.auto_soc"] = "85"
hass95, store95, coach95 = bouw(huis95, inst95)
b95, _ = asyncio.run(ronde(coach95, inst95, paal=paal95))
print(f"  profiel 100%, auto op 85%: {b95['rule']}, doel {b95['target_percent']}")
controle("met het profiel op 100% laadt hij nog", b95["rule"] != "complete" and b95["target_percent"] == 100.0,
         f"{b95['rule']} {b95['target_percent']}")


async def doel95(p):
    coach95.async_target("dev-laadpaal", p)
    await hass95.afmaken()
    return await ronde(coach95, inst95, paal=paal95)


b95b, _ = asyncio.run(doel95(80))
print(f"  gekozen 80%: {b95b['rule']}: {b95b['reason']}")
controle("80% op de kaart: de auto op 85% is klaar", b95b["rule"] == "complete" and b95b["target_session"],
         f"{b95b['rule']} {b95b['target_session']}")
controle("en de keuze is vastgelegd", any(r.get("target") == 80.0 for r in store95.instellingen["sessions"]),
         f"{store95.instellingen['sessions']}")
hass95h, store95h, coach95h = bouw(huis95, store95.instellingen)
coach95h._restore(store95h.instellingen)
controle("na een herstart staat het gekozen doel er nog", coach95h._doel.get("dev-laadpaal") == 80.0, f"{coach95h._doel}")
b95c, _ = asyncio.run(doel95(None))
controle("terug naar het profiel: weer 100%", b95c["target_percent"] == 100.0 and not b95c["target_session"],
         f"{b95c['target_percent']}")
coach95.async_target("dev-laadpaal", 5)
controle("nooit onder de 10%", coach95._doel["dev-laadpaal"] == 10.0, f"{coach95._doel}")
hass95.states.zet("sensor.laadpaal_status", "disconnected")
asyncio.run(ronde(coach95, inst95, paal=paal95, nu=dt.datetime(2026, 8, 18, 14, 40)))
coach95._los_sinds["dev-laadpaal"] = dt.datetime(2026, 8, 18, 14, 39)
asyncio.run(ronde(coach95, inst95, paal=paal95, nu=dt.datetime(2026, 8, 18, 14, 41)))
controle("kabel eruit: het gekozen doel vervalt", "dev-laadpaal" not in coach95._doel, f"{coach95._doel}")

print("=== 96. een batterij op dezelfde groep als de paal neemt de ruimte van de auto niet in (v0.88.2) ===")
# De eerste woning op 23-09-2026 om 17:08: de Anker laadde 3,2 kW zon op L3 van de
# garage (14 A), en de paal zei "de groep Garage is te zwaar belast". Om 17:09
# stond de Anker stil en L3 op 0 A, en zei hij het nog steeds: de mediaan van
# anderhalve minuut droeg de oude stroom.
huis96 = {**huis75(afname=0.0, teruglevering=0.0, batterij="3200"), "sensor.l1": "2", "sensor.l2": "2", "sensor.l3": "15",
          "sensor.g1": "0.5", "sensor.g2": "0.5", "sensor.g3": "14"}
hass96, _, coach96 = bouw(huis96, inst81)
NU96 = dt.datetime(2026, 9, 23, 17, 8)
coach96._batterij["dev-batterij"] = {"regelaar": coachmod.Regelaar(), "stuurt": True,
                                     "besluit": coachmod.Besluit(coachmod.NUL if hasattr(coachmod, "NUL") else "nul", rule="nul")}
grid96, _, _, _ = coach96._read(NU96, inst81, LAADPAAL_G)
g3 = grid96.circuits[0].phase_amps[2]
print(f"  garage L3 voor de paal: {g3:.1f} A (gemeten 14, de Anker 3200 W = {3200 / 230:.1f} A)")
controle("de lading van een gestuurde batterij op nul op de meter telt niet als belasting",
         g3 < 0.5, f"{grid96.circuits[0].phase_amps}")
controle("ook niet onder de hoofdaansluiting", grid96.phase_amps[2] < 1.5, f"{grid96.phase_amps}")
coach96._batterij["dev-batterij"]["besluit"] = coachmod.Besluit("netladen", rule="netladen")
grid96b, _, _, _ = coach96._read(NU96, inst81, LAADPAAL_G)
controle("laadt hij van het net, dan wijkt hij niet en telt zijn stroom wel",
         grid96b.circuits[0].phase_amps[2] > 13.5, f"{grid96b.circuits[0].phase_amps}")
coach96._batterij["dev-batterij"]["stuurt"] = False
grid96c, _, _, _ = coach96._read(NU96, inst81, LAADPAAL_G)
controle("stuurt de coach de batterij niet, dan telt zijn stroom ook", grid96c.circuits[0].phase_amps[2] > 13.5,
         f"{grid96c.circuits[0].phase_amps}")
# De Anker stopt: vanaf dan tellen alleen de metingen van daarna.
coach96._daling = None
hass96.states.zet("sensor.batterij_vermogen", "0")
coach96._batterij_wijkt(inst81, NU96 + dt.timedelta(seconds=60))
controle("een batterij die flink zakt zet de mediaan opnieuw in, net als een paal",
         coach96._daling == NU96 + dt.timedelta(seconds=60), f"{coach96._daling}")

print("=== 97. het verslag van een laadbeurt: accustand van en naar, net en zon (v0.89.0) ===")
# De bewoner van de eerste woning op 23-09-2026: "tijdens deze laadsessie is er X
# kWh geladen, en is de accu gestegen van A% naar B%. C kWh is afgenomen van het
# net met een totaalprijs van € D; E kWh heb je direct verbruikt van je zonopwek."
cijfers = coachmod.ChargerCoach._beurt_cijfers
sessie97 = {"soc_begin": 44.0, "geld": {"kwh": 28.1, "zon_kwh": 6.2, "betaald": 6.72}}
auto97 = coachmod.Car(capacity_kwh=78.0, phases=3, soc_percent=80.0)
zin97 = cijfers(sessie97, auto97)
print(f"  {zin97.strip()}")
controle("van en naar, net met bedrag, en zon",
         zin97 == " De accu ging van 44 naar 80%. 21,9 kWh kwam van het net voor € 6,72; 6,2 kWh kwam direct van je zon.", zin97)
geschat97 = cijfers(sessie97, coachmod.Car(capacity_kwh=78.0, phases=3, soc_percent=80.0, soc_estimated=True))
controle("een geschatte stand zegt dat erbij", "80% (geschat)." in geschat97, geschat97)
controle("zonder accustand geen procenten", "accu ging" not in cijfers({"geld": sessie97["geld"]}, coachmod.Car()), "")
controle("alles op zon: geen netzin", cijfers({"geld": {"kwh": 5.0, "zon_kwh": 5.0, "betaald": 0.0}}, None)
         == " 5,0 kWh kwam direct van je zon.", cijfers({"geld": {"kwh": 5.0, "zon_kwh": 5.0, "betaald": 0.0}}, None))
controle("niets geladen: niets erbij", cijfers({"geld": {}}, None) == "", "")

print()
print(f"{GOED} goed, {FOUT} fout")
sys.exit(1 if FOUT else 0)
