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

# Sven op 05-09-2026, toen de paal om 09:42 op zon begon en Meldingen zweeg:
# "ik wil dat alles wat de coach doet terug te lezen is in meldingen." Elk
# ander besluit komt dus in de geschiedenis, als "besluit" en zonder telefoon.
print("=== 3b. elk ander besluit staat in de geschiedenis, zonder telefoon ===")
geschiedenis = asyncio.run(coachmod.async_get_meldingen(hass).async_list())
besluiten = [g["message"] for g in geschiedenis if g.get("kind") == "besluit"]
for b in besluiten:
    print(f"  {b[:110]}")
controle("wekken, wachten op de auto en zon zijn drie besluiten", len(besluiten) == 3,
         f"{len(besluiten)}")
controle("het eerste zegt wekken op 10 A", "laden op 10 A" in besluiten[0], besluiten[0])
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
# En in de geschiedenis is die kritiek: de bewoner moet er iets mee. Sven op
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
# Twee ronden, want één meting `disconnected` is sinds v0.43.2 nog geen kabel
# die eruit gaat; zie `KABEL_ONTDREUN`.
for tijd in (dt.datetime(2026, 8, 25, 20, 5), dt.datetime(2026, 8, 25, 20, 5, 40)):
    asyncio.run(ronde(coach19, inst19, paal=PAAL19, nu=tijd))
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
# Een enkele ronde is niet genoeg: de twee sensoren van een Easee melden tijdens
# het optrekken seconden na elkaar, en dan is de verhouding een vergelijking
# tussen nu en daarnet. Bij Van den Dam leverde dat op 30-08-2026 om 04:28 een
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
# was dat elke voorspelling het traagste geval nam: bij Van den Dam 17,2 uur
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
# Sven op 20-08-2026: hij trok de kabel er twee keer uit tijdens het laden en
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
controle("in Svens eigen bewoording",
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
# hij aan werkte. Sven kreeg op 29-08-2026 om 19:54 zo'n verslag terwijl de paal
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
# Sven op 26-08-2026: de pauze zelf blijft winnen van de klaar-tijd, want het is
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
# keer stroom loopt. Sven op 29-08-2026.
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

# Helemaal zonder strategie moet het ook niet omvallen.
uit = schema_bijwerken(None, "d1", enabled=True)
controle("zonder strategie ontstaat er gewoon een",
         uit["schedules"][0]["device"] == "d1", f"{uit}")

print("=== 25. de kWh-teller mag ook in het algemene veld staan ===")
# Sven op 27-08-2026, tijdens een installatie bij een klant: "Energieteller
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
# Uit Svens eigen nota van Frank, nagerekend op 27-08-2026. Wat er op de
# factuur staat zijn kale commodityprijzen; de energiebelasting staat als vast
# maandbedrag apart, geheven over het gesaldeerde jaarvolume. Daaruit volgt dat
# de belasting bij teruglevering wegstreept tegen die bij afname.
#
# De opslag van de leverancier doet dat niet: die betaal je per ingekochte kWh
# en krijg je nergens terug. Zonder die aftrek stond de terugleveropbrengst er
# ruim twee cent te hoog in.
#
# Thuis bij Sven: vast contract, salderen aan. Bij de klant: dynamisch,
# salderen tot 1 januari 2027.

VOOR_2027 = dt.datetime(2026, 8, 27, 12, 0)
NA_2027 = dt.datetime(2027, 1, 1, 12, 0)


def klok(moment):
    """dt_util.utcnow van het harnas laten wijzen waar de proef wil."""
    return moment


# --- het vaste contract van Sven -----------------------------------------
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
print(f"  verschil voor Sven: {tar.feed_in - zonder.feed_in:.4f} euro per kWh")

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
# Bij Van den Dam gebeurde dat op 29-08-2026 met alle 24 uurblokken tegelijk.
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
# Bij Van den Dam stond op 29-08-2026 een vermogenssensor in "volgend uur". Die
# 1874 W werd als 1874 kWh gelezen en dus als 1.874.000 W doorgegeven: op de
# kaart "over een uur wordt er 1874,0 kW zon verwacht", en `_beter_straks` koos
# met zo'n vooruitzicht altijd voor wachten. De coach stond daardoor stil op de
# goedkoopste uren van de dag. Gevonden door Sven, op zijn eigen kaart.
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

print("=== 33. de nacht van 30-08-2026 bij Van den Dam ===")
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
# huismeter van Van den Dam meldt elke dertig seconden; op 30-08-2026 om
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
# Dat is precies wat er bij Van den Dam gebeurde, en het laat zien dat het de
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
# van Van den Dam waar alle drie de fasen samen elf ampere zakten.
hass35.states.zet("sensor.laadpaal_vermogen", "9300")
controle("vers en boven de drempel wordt het gewoon gemeten",
         coach35._measured_phases(LAADPAAL) == 3,
         f"{coach35._measured_phases(LAADPAAL)}")

print("--- d. wat de lastbewaker vrijgeeft is een restwaarde ---")
# `sensor.1_equalizer_limiet` bij Van den Dam meldt niet een instelling maar wat
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
# Sven kreeg in de nacht van 30-08-2026 drie meldingen, om 03:02 op 84%, om
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
inst38["strategy"]["load_alert"] = {
    "enabled": True,
    "threshold_percent": 80.0,
    "targets": ["mobile_app_iphone"],
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
inst38d["strategy"]["load_alert"] = inst38["strategy"]["load_alert"]
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
# Bij Van den Dam viel de P1-meter op 30-08-2026 om 11:07, 11:09 en 11:15
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
# Sven op 30-08-2026: "ik heb de naam aangepast bij de auto maar in het
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
# Sven op 04-09-2026: "wat als een sensor ineens niet meer beschikbaar is. Dat
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
te_vroeg = wacht(1) + wacht(5)
controle("vijf minuten stilte is nog geen melding", not te_vroeg, f"{te_vroeg}")
stil = wacht(11)
print(f"  na elf minuten: {stil}")
controle("na tien minuten wel, met de naam van de sensor erin",
         len(stil) == 1 and "accustand van Ford" in stil[0] and "sensor.ford_soc" in stil[0], f"{stil}")
controle("en niet nog een keer", not wacht(12), "")
besluit41b, _ = asyncio.run(ronde(coach41b, inst41b, nu=t0 + dt.timedelta(minutes=12)))
controle("ondertussen laadt hij gewoon door op de laatst bekende stand",
         besluit41b["charge"], f"{besluit41b}")
hass41b.states.zet("sensor.ford_soc", "44")
weer = wacht(13)
controle("terug: één melding dat hij het weer doet",
         len(weer) == 1 and "accustand van Ford" in weer[0], f"{weer}")
controle("en daarna stil", not wacht(14), "")
geschiedenis = asyncio.run(async_get_meldingen(hass41b).async_list())
controle("en alles staat in de geschiedenis, op volgorde",
         [g["message"][:12] for g in geschiedenis][:1] == ["proefmelding"]
         and any("meldt al" in g["message"] for g in geschiedenis)
         and any("doet het weer" in g["message"] for g in geschiedenis), f"{geschiedenis}")

print("=== 42. niets van één installatie zit in de code ===")
# Sven op 30-08-2026: "je hebt toch niet iets van mij thuis hard gecodeerd? Het
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

# En de mediaan, niet het gemiddelde. Svens keuze van 30-08-2026: één keer
# wassen tilt een gemiddelde over een week heen op.
controle("de mediaan van 1, 1, 1 en 9 is 1", coachmod._mediaan([1.0, 1.0, 1.0, 9.0]) == 1.0,
         f"{coachmod._mediaan([1.0, 1.0, 1.0, 9.0])}")
controle("en van 1, 2, 3 is 2", coachmod._mediaan([3.0, 1.0, 2.0]) == 2.0,
         f"{coachmod._mediaan([3.0, 1.0, 2.0])}")

print("=== 48. een laadbeurt komt met kosten en besparing in de opslag ===")
# Sven op 05-09-2026: "Kunnen we ergens een overzichtje maken wat we hebben
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
# Sven op 05-09-2026, bij "bespaard -0,01" op een beurt die vrijdagavond
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

print()
print(f"{GOED} goed, {FOUT} fout")
sys.exit(1 if FOUT else 0)
