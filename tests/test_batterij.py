"""Proeven op het denkwerk van de thuisbatterij, zonder Home Assistant.

De strategie (`plan_batterij`), de regelaar (`Regelaar`), wat de batterij
verdient en het rendement uit de tellers. De getallen komen waar het kan uit
de eerste woning, gemeten op 21-09-2026.
"""

import dataclasses
import datetime as dt
import random
import sys

import harnas  # noqa: F401  (zet het pakket klaar)

bat = sys.modules["domotiapp_coach.batterij"]
planner = sys.modules["domotiapp_coach.planner"]

from domotiapp_coach.batterij import (  # noqa: E402
    Batterij, Besluit, Regelaar, plan_batterij,
    NUL, ZONNELADEN, ONTLADEN, NETLADEN, MAX_LADEN, HANDELEN, STANDBY,
)
from domotiapp_coach.planner import Forecast, Tariff  # noqa: E402

FOUT = 0
GOED = 0


def controle(naam, gelukt, uitleg=""):
    global FOUT, GOED
    if gelukt:
        GOED += 1
    else:
        FOUT += 1
        print(f"  FOUT  {naam}: {uitleg}")


DAG = dt.datetime(2026, 9, 21)


def prijzen(per_uur, terug=None, dag=DAG):
    """Een prijslijst vanaf middernacht, een getal per uur."""
    return [
        {
            "start": dag + dt.timedelta(hours=i),
            "end": dag + dt.timedelta(hours=i + 1),
            "price": p,
            "feed_in": (terug[i] if isinstance(terug, list) else terug),
        }
        for i, p in enumerate(per_uur)
    ]


def verwachting(zon=None, huis=0.3, dag=DAG, dagen=2):
    """Het huis vraagt elk uur evenveel; de zon per uur van de dag."""
    zon = zon or {}
    return Forecast(
        solar_kwh={
            dag + dt.timedelta(days=d, hours=u): kwh for d in range(dagen) for u, kwh in zon.items()
        },
        house_kwh={u: huis for u in range(24)},
    )


# De batterij van de eerste woning: 14,6 kWh, 3,5 kW erin, 2,5 kW eruit, grenzen
# 5 en 95%, en 73,6% rendement uit de kWh-meter.
def anker(soc=50.0, **kw):
    basis = dict(soc=soc, capacity_kwh=14.6, max_charge_w=3500.0, max_discharge_w=2500.0,
                 soc_min=5.0, soc_max=95.0, rte=0.736)
    basis.update(kw)
    return Batterij(**basis)


ZON = {9: 1.0, 10: 2.5, 11: 3.5, 12: 4.0, 13: 4.0, 14: 3.5, 15: 2.5, 16: 1.5, 17: 0.5}
VAST = Tariff(buy=0.2417, feed_in=0.0193)

print("1. vast contract met panelen: nul op de meter")
for uur in (3, 12, 21):
    b1 = plan_batterij(DAG.replace(hour=uur), [], VAST, verwachting(ZON), anker())
    print(f"  {uur:02d}:00  {b1.stand:11s} {b1.reason}")
    controle(f"vast, {uur}:00 is nul op de meter", b1.stand == NUL, b1.stand)

print("2. vast contract met volledig salderen: opslaan kost alleen verlies")
b2 = plan_batterij(DAG.replace(hour=12), [], Tariff(buy=0.24, feed_in=0.24), verwachting(ZON), anker())
print(f"  {b2.stand}: {b2.reason}")
controle("met salderen slaat hij geen zon op", b2.grenzen[0] is False, b2.stand)
b2b = plan_batterij(DAG.replace(hour=12), [], Tariff(buy=0.24, feed_in=0.24), verwachting(ZON), anker(soc=5.0))
controle("en is hij leeg, dan staat hij stil", b2b.stand == STANDBY, b2b.stand)

print("3. dynamisch: goedkope nacht, dure avond, geen zon")
# Vijf uur van 13 cent in de nacht, zoals in het voorbeeld van de bewoner.
NACHT = [0.13] * 5 + [0.25] * 12 + [0.42] * 4 + [0.28] * 3
LIJST3 = prijzen(NACHT, terug=0.05) + prijzen(NACHT, terug=0.05, dag=DAG + dt.timedelta(days=1))
b3 = plan_batterij(DAG.replace(hour=0, minute=1), LIJST3, Tariff(), verwachting(huis=0.5), anker(soc=10.0))
print(f"  00:01  {b3.stand}: {b3.reason}")
controle("in de goedkope nacht laadt hij van het net", b3.stand == NETLADEN, b3.stand)
controle("en niet voluit maar uitgesmeerd over de vijf even dure uren",
         0 < b3.power_w < 3500.0, f"{b3.power_w:.0f} W")
geladen3 = sum(u.net_kwh for u in b3.uren if u.start.hour < 5 and u.start.date() == DAG.date())
controle("het vermogen is wat hij wil laden gedeeld door die uren",
         abs(b3.power_w - geladen3 / (5 - 1 / 60) * 1000.0) < 25.0,
         f"{b3.power_w:.0f} W tegen {geladen3:.2f} kWh")
b3b = plan_batterij(DAG.replace(hour=18, minute=30), LIJST3, Tariff(), verwachting(huis=0.5), anker(soc=60.0))
print(f"  18:30  {b3b.stand}: {b3b.reason}")
controle("in het dure uur voedt hij het huis", b3b.stand == NUL, b3b.stand)
b3c = plan_batterij(DAG.replace(hour=9), LIJST3, Tariff(), verwachting(huis=0.5), anker(soc=30.0))
print(f"  09:00  {b3c.stand}: {b3c.reason}")
controle("in een gewoon uur bewaart hij wat er in zit voor de dure avond",
         b3c.stand == ZONNELADEN and b3c.rule == "bewaren", f"{b3c.stand} {b3c.rule}")

print("4. een prijsverschil dat het rendement niet goedmaakt")
KLEIN = [0.20] * 6 + [0.25] * 18
LIJST4 = prijzen(KLEIN, terug=0.05)
b4 = plan_batterij(DAG.replace(hour=1), LIJST4, Tariff(), verwachting(huis=0.5), anker(soc=10.0))
print(f"  {b4.stand}: {b4.reason}")
controle("0,20 tegen 0,25 is bij 73,6% geen reden om van het net te laden",
         b4.stand != NETLADEN, b4.stand)

print("5. een negatieve prijs")
NEG = [0.20] * 12 + [-0.03] * 3 + [0.25] * 9
b5 = plan_batterij(DAG.replace(hour=13), prijzen(NEG, terug=-0.10), Tariff(), verwachting(ZON), anker(soc=40.0))
print(f"  {b5.stand}: {b5.reason}")
controle("negatieve prijs is maximaal laden", b5.stand == MAX_LADEN and b5.power_w == 3500.0, b5.stand)
controle("en dan komt er niets uit", b5.grenzen == (True, False))
b5b = plan_batterij(DAG.replace(hour=13), prijzen(NEG, terug=-0.10), Tariff(), verwachting(ZON), anker(soc=95.0))
controle("een volle batterij laadt ook bij een negatieve prijs niet", b5b.stand != MAX_LADEN, b5b.stand)

print("6. de laadpaal laadt")
b6 = plan_batterij(DAG.replace(hour=21), [], VAST, verwachting(ZON), anker(), paal_laadt=True)
print(f"  {b6.stand}: {b6.reason}")
controle("dan geeft de batterij niets af", b6.stand == ZONNELADEN and b6.grenzen == (True, False), b6.stand)

print("7. de reserve voor noodstroom")
b7 = plan_batterij(DAG.replace(hour=21), [], VAST, verwachting(ZON), anker(soc=30.0, reserve=30.0))
print(f"  {b7.stand}: {b7.reason}")
controle("op de reserve komt er niets meer uit", b7.grenzen[1] is False, b7.stand)
b7b = plan_batterij(DAG.replace(hour=21), [], VAST, verwachting(ZON), anker(soc=31.5, reserve=30.0))
controle("er vlak boven nog wel", b7b.stand == NUL, b7b.stand)

print("8. de wekelijkse volle beurt")
# 0,18 gedeeld door 73,6% is 0,245: duurder dan de 0,23 van overdag, dus uit
# zichzelf laadt hij hier niet.
VLAKKIG = [0.22, 0.21, 0.18, 0.19, 0.22] + [0.23] * 19
MIDDERNACHT = DAG + dt.timedelta(days=1)
b8 = plan_batterij(DAG.replace(hour=2, minute=5), prijzen(VLAKKIG, terug=0.05), Tariff(),
                   verwachting(huis=0.4), anker(soc=50.0, vol_voor=MIDDERNACHT))
print(f"  02:05  {b8.stand}: {b8.reason}")
controle("op het goedkoopste uur laadt hij voor de volle beurt", b8.stand == NETLADEN, b8.stand)
b8b = plan_batterij(DAG.replace(hour=0, minute=5), prijzen(VLAKKIG, terug=0.05), Tariff(),
                    verwachting(huis=0.4), anker(soc=50.0, vol_voor=MIDDERNACHT))
controle("en niet al op een duurder uur ervoor", b8b.stand != NETLADEN, b8b.stand)
eind8 = [u.soc for u in b8.uren if u.end <= MIDDERNACHT]
controle("het plan komt voor middernacht aan zijn laadgrens", max(eind8) >= 94.0, f"{max(eind8):.0f}%")
b8c = plan_batterij(DAG.replace(hour=2, minute=5), prijzen(VLAKKIG, terug=0.05), Tariff(),
                    verwachting(huis=0.4), anker(soc=50.0))
controle("zonder die beurt laadt hij hier niet", b8c.stand != NETLADEN, b8c.stand)
controle("vol_voor: alleen op de gekozen dag",
         bat.vol_voor(DAG.replace(hour=8), True, DAG.weekday(), None) == MIDDERNACHT
         and bat.vol_voor(DAG.replace(hour=8), True, (DAG.weekday() + 1) % 7, None) is None)
controle("vol_voor: niet als hij deze week al vol was",
         bat.vol_voor(DAG.replace(hour=8), True, DAG.weekday(), DAG - dt.timedelta(days=2)) is None)
controle("vol_voor: wel als dat een week geleden was",
         bat.vol_voor(DAG.replace(hour=8), True, DAG.weekday(), DAG - dt.timedelta(days=6, hours=20)) is not None)

print("9. zonder rendement wordt er niet gepland")
b9 = plan_batterij(DAG.replace(hour=1), LIJST3, Tariff(), verwachting(huis=0.5), anker(soc=10.0, rte=None))
print(f"  {b9.stand}: {b9.reason}")
controle("dan alleen nul op de meter", b9.stand == NUL and b9.rule == "rendement-onbekend", b9.rule)

print("10. de avondpiek: bij dynamisch telt de prijs, bij vast blijft hij dicht")
# Sinds v0.79.0 (de bewoner van de eerste woning, 22-09-2026): bij een
# dynamisch contract is de avondpiek een gewoon uur op zijn eigen prijs.
PIEK = [0.30] * 18 + [0.05] * 2 + [0.45] * 4
b10 = plan_batterij(DAG.replace(hour=18, minute=10), prijzen(PIEK, terug=0.02), Tariff(),
                    verwachting(huis=0.5), anker(soc=10.0))
print(f"  {b10.stand}: {b10.reason}")
controle("een spotgoedkoop uur in de avondpiek laadt bij een dynamisch contract wél van het net",
         b10.stand == NETLADEN, b10.stand)
b10b = plan_batterij(DAG.replace(hour=18, minute=10), [], VAST,
                     verwachting(huis=0.5), anker(soc=10.0))
controle("bij een vast contract komt er in de avondpiek niets van het net", b10b.stand != NETLADEN, b10b.stand)
b10c = plan_batterij(DAG.replace(hour=18, minute=10), prijzen([0.30] * 18 + [-0.02] * 2 + [0.45] * 4, terug=0.0),
                     Tariff(), verwachting(huis=0.5), anker(soc=10.0))
controle("en een negatieve prijs om 18:00 is bij dynamisch maximaal laden", b10c.stand == MAX_LADEN, b10c.stand)

print("11. handelen")
HANDEL = [0.10] * 6 + [0.25] * 12 + [0.60] * 3 + [0.25] * 3
TERUG = [p - 0.13 for p in HANDEL]
L11 = prijzen(HANDEL, terug=TERUG) + prijzen(HANDEL, terug=TERUG, dag=DAG + dt.timedelta(days=1))
b11 = plan_batterij(DAG.replace(hour=19), L11, Tariff(), verwachting(huis=0.3), anker(soc=90.0, handelen=True))
print(f"  aan: {b11.stand}: {b11.reason}")
controle("met handelen aan levert hij op het dure uur aan het net", b11.stand == HANDELEN, b11.stand)
b11b = plan_batterij(DAG.replace(hour=19), L11, Tariff(), verwachting(huis=0.3), anker(soc=90.0))
controle("standaard staat het uit en voedt hij alleen het huis",
         b11b.stand in (NUL, ONTLADEN) and b11b.grenzen[1], b11b.stand)
b11c = plan_batterij(DAG.replace(hour=19), L11, Tariff(), verwachting(huis=0.3),
                     anker(soc=90.0, handelen=True), paal_laadt=True)
controle("en niet als de laadpaal laadt", b11c.grenzen[1] is False, b11c.stand)

# Handelen alleen met wat er boven de nacht uitkomt (de eigenaar, 22-09-2026:
# "nul op de meter heeft prioriteit, het overschot verhandelen").
b11c = plan_batterij(DAG.replace(hour=18, minute=10), prijzen(HANDEL, terug=0.02), Tariff(),
                     verwachting(huis=0.6), anker(soc=20.0, handelen=True))
print(f"  bijna leeg om 18:10 met 0,6 kWh per uur huis: {b11c.stand}")
controle("met te weinig voor de nacht handelt hij niet, hoe duur het uur ook is", b11c.stand != HANDELEN, b11c.stand)

print("12. te weinig zon: bijladen voor de dure avond, met de zin erbij")
WINTER = {11: 0.4, 12: 0.6, 13: 0.4}
b12 = plan_batterij(DAG.replace(hour=2), LIJST3, Tariff(), verwachting(WINTER, huis=0.5), anker(soc=8.0))
print(f"  {b12.stand}: {b12.reason}\n  {b12.plan}")
controle("hij laadt bij in de nacht", b12.stand == NETLADEN, b12.stand)
controle("en zegt wat hij verwacht", "zon" in b12.plan and "huis vraagt" in b12.plan, b12.plan)
# De bewoner van de eerste woning op 22-09-2026: tot morgenvroeg, en afsluiten
# met een conclusie: over, of tekort om de nacht te overbruggen.
controle("tot morgenvroeg, niet tot middernacht", "morgenvroeg" in b12.plan and "middernacht" not in b12.plan, b12.plan)
controle("met een bijna lege batterij en weinig zon: een tekort, en hij laadt bij",
         "tekort om de nacht te overbruggen" in b12.plan, b12.plan)
bal12 = bat.balans_kwh(DAG.replace(hour=2), verwachting(WINTER, huis=0.5), anker(soc=8.0))
controle("en de balans is dan negatief", bal12 is not None and bal12 < 0, f"{bal12}")
b12c = plan_batterij(DAG.replace(hour=20), prijzen([0.25] * 24, terug=0.05), Tariff(),
                     verwachting(WINTER, huis=0.3), anker(soc=90.0))
print(f"  's avonds vol: {b12c.plan}")
controle("met een volle batterij 's avonds: over", "over in je accu" in b12c.plan, b12c.plan)
controle("en tot morgenvroeg telt alleen de nacht: zeven uur huis, geen zon",
         bat.balans_kwh(DAG.replace(hour=20), verwachting(WINTER, huis=0.3), anker(soc=90.0)) is not None
         and abs(bat.nachtbalans(DAG.replace(hour=20), verwachting(WINTER, huis=0.3), anker(soc=90.0))[1] - 11 * 0.3) < 1e-6,
         f"{bat.nachtbalans(DAG.replace(hour=20), verwachting(WINTER, huis=0.3), anker(soc=90.0))}")
ZOMER = {u: 4.0 for u in range(8, 19)}
b12b = plan_batterij(DAG.replace(hour=2), prijzen([0.22] * 5 + [0.25] * 19, terug=0.05), Tariff(),
                     verwachting(ZOMER, huis=0.3), anker(soc=40.0))
print(f"  zomer: {b12b.stand}: {b12b.reason}")
controle("met genoeg zon op komst laadt hij niet van het net", b12b.stand != NETLADEN, b12b.stand)

print("13. geen accustand, of de sturing uit")
controle("zonder accustand staat hij stil",
         plan_batterij(DAG, [], VAST, verwachting(), anker(soc=None)).stand == STANDBY)
controle("met de sturing uit ook",
         plan_batterij(DAG, [], VAST, verwachting(), anker(), enabled=False).rule == "uit")

print("14. de som is snel genoeg voor elke minuut")
import time  # noqa: E402
KWARTIER = []
for k in range(36 * 4):
    start = DAG + dt.timedelta(minutes=15 * k)
    KWARTIER.append({"start": start, "end": start + dt.timedelta(minutes=15),
                     "price": 0.20 + 0.1 * ((k * 7) % 11) / 11, "feed_in": 0.05})
t0 = time.perf_counter()
plan_batterij(DAG.replace(hour=0, minute=1), KWARTIER, Tariff(), verwachting(ZON), anker())
duur = time.perf_counter() - t0
print(f"  144 kwartierblokken: {duur * 1000:.0f} ms")
controle("anderhalve dag kwartierprijzen binnen een seconde", duur < 1.0, f"{duur:.2f} s")


# --- de regelaar ---------------------------------------------------------------

def draai(huis_w, stand=NUL, seconden=600, meter_elke=5, volgt_na=5, power_w=0.0,
          soc=50.0, meter_valt_weg=None, ruis=0.0, zaad=1,
          sensor_na=0, sensor_aanloop=False, sensor_echo=0, geen_sensor=False, volgt_niet=False,
          regelaar=None):
    """Een huis, een meter en een batterij, per seconde.

    De meter meldt elke `meter_elke` seconden, de batterij voert een opdracht
    `volgt_na` seconden later uit: de twee getallen die op 21-09-2026 gemeten
    zijn. Geeft de opdrachten, het verloop van de meter en de kWh van het net.

    De sensor van de batterij is standaard eerlijk. Met `sensor_na` loopt hij
    zoveel seconden achter, met `sensor_aanloop` toont hij onderweg een waarde
    tussen oud en nieuw, en met `sensor_echo` zoveel seconden lang de opdracht
    zelf: de Anker van 22-09-2026. `geen_sensor` is een batterij zonder
    vermogenssensor, `volgt_niet` een batterij die niets met een opdracht doet.
    """
    rnd = random.Random(zaad)
    regelaar = regelaar or Regelaar()
    b = anker(soc=soc)
    besluit = Besluit(stand, power_w=power_w)
    nu = DAG.replace(hour=12)
    batterij_w, wachtrij = 0.0, []
    opdrachten, meter, afname, levering = [], [], 0.0, 0.0
    net_w, net_op = None, None
    verloop = []

    def sensor(s):
        if geen_sensor:
            return None
        if sensor_echo and opdrachten and s - opdrachten[-1][0] < sensor_echo:
            return opdrachten[-1][1]
        oud = next((w for t, w in reversed(verloop) if t <= s - sensor_na), 0.0)
        if sensor_aanloop and abs(batterij_w - oud) > 1.0:
            return oud + 0.4 * (batterij_w - oud)
        return oud

    for s in range(seconden):
        nu += dt.timedelta(seconds=1)
        vraag = huis_w(s) + (rnd.uniform(-ruis, ruis) if ruis else 0.0)
        echt = vraag + batterij_w
        verloop.append((s, batterij_w))
        afname += max(0.0, echt) / 3_600_000
        levering += max(0.0, -echt) / 3_600_000
        if s % meter_elke == 0 and not (meter_valt_weg and meter_valt_weg[0] <= s < meter_valt_weg[1]):
            net_w, net_op = echt, nu
            meter.append((s, echt))
        if s % meter_elke == 0 or s % 5 == 0:
            uit = regelaar.stap(nu, net_w=net_w, net_op=net_op, batterij_w=sensor(s),
                                besluit=besluit, b=b, doel_w=0.0)
            if uit is not None:
                opdrachten.append((s, uit))
                if not volgt_niet:
                    wachtrij.append((s + volgt_na, uit))
        klaar = [w for t, w in wachtrij if t <= s]
        if klaar:
            batterij_w = klaar[-1]
            wachtrij = [(t, w) for t, w in wachtrij if t > s]
    return opdrachten, meter, afname, levering


print("15. de sprong van 19:19:47: 2,1 kW erbij")
op15, meter15, _, _ = draai(lambda s: 300.0 if s < 60 else 2400.0, seconden=180)
print(f"  opdrachten: {op15}")
na15 = [w for s, w in meter15 if s >= 80]
controle("binnen twintig seconden staat de meter weer rond nul",
         all(abs(w) <= 60 for w in na15), f"{[round(w) for w in na15[:6]]}")
controle("zonder doorschot: de batterij levert nooit meer dan het huis vraagt",
         all(w >= -60 for s, w in meter15), f"{min(w for s, w in meter15):.0f} W")
controle("en met een handvol opdrachten", len(op15) <= 4, f"{len(op15)}")

print("16. een rustig huis dat nooit stilstaat")
op16, meter16, af16, _ = draai(lambda s: 320.0, seconden=1800, ruis=35.0)
binnen16 = sum(abs(w) <= 50 for s, w in meter16 if s > 30) / max(1, len([1 for s, w in meter16 if s > 30]))
print(f"  {len(op16)} opdrachten in een half uur, {binnen16 * 100:.1f}% binnen 50 W")
controle("hij zit niet elke meting aan de knop", len(op16) <= 10, f"{len(op16)}")
controle("en de meter blijft rond nul", binnen16 >= 0.95, f"{binnen16:.2f}")

print("17. rond nul: een vraag die om de honderd watt schommelt")
op17, _, _, _ = draai(lambda s: 60.0 + 80.0 * ((s // 12) % 2), seconden=1800)
wissels17 = sum(1 for (_, a), (_, c) in zip(op17, op17[1:]) if (a == 0) != (c == 0))
print(f"  {len(op17)} opdrachten, {wissels17} keer aan of uit")
controle("hij klappert niet tussen standby en ontladen", wissels17 <= 2, f"{wissels17}")

print("18. een oven die op zijn thermostaat klikt")
op18, meter18, af18, lev18 = draai(lambda s: 300.0 + (2000.0 if (s // 45) % 2 == 0 else 0.0), seconden=1800)
zonder18 = sum(300.0 + (2000.0 if (s // 45) % 2 == 0 else 0.0) for s in range(1800)) / 3_600_000
print(f"  {len(op18)} opdrachten, {af18:.3f} kWh van het net tegen {zonder18:.3f} zonder batterij, {lev18:.3f} kWh terug")
controle("hij volgt de oven: het meeste komt uit de batterij", af18 < zonder18 * 0.35, f"{af18:.3f}")
controle("en schiet niet door naar terugleveren", lev18 < zonder18 * 0.25, f"{lev18:.3f}")

print("19. de meter valt weg")
op19, _, _, _ = draai(lambda s: 1500.0, seconden=300, meter_valt_weg=(100, 300))
print(f"  opdrachten: {op19}")
controle("dan gaat de batterij naar nul", op19[-1][1] == 0.0 and 100 < op19[-1][0] <= 140, f"{op19[-1]}")

print("20. de standen begrenzen de regelaar")
op20, _, _, _ = draai(lambda s: 1500.0, stand=ZONNELADEN, seconden=120)
controle("alleen zonneladen: bij een tekort komt er niets uit", all(w >= 0 for s, w in op20), f"{op20}")
op20b, _, _, _ = draai(lambda s: -1800.0, stand=ZONNELADEN, seconden=120)
controle("maar overschot gaat erin", op20b and op20b[-1][1] > 1500, f"{op20b}")
op20c, _, _, _ = draai(lambda s: -1800.0, stand=ONTLADEN, seconden=120)
controle("alleen ontladen: overschot gaat er niet in", all(w <= 0 for s, w in op20c), f"{op20c}")
op20d, _, _, _ = draai(lambda s: 400.0, stand=NETLADEN, power_w=1750.0, seconden=120)
controle("laden van het net: het rustige vermogen, ook als het huis iets vraagt",
         op20d and abs(op20d[-1][1] - 1750.0) <= 1, f"{op20d}")
op20e, _, _, _ = draai(lambda s: -3000.0, stand=NETLADEN, power_w=1750.0, seconden=120)
controle("en is er meer zon dan dat, dan gaat die erin", op20e and op20e[-1][1] > 2800, f"{op20e}")
op20f, _, _, _ = draai(lambda s: -3000.0, stand=STANDBY, seconden=60)
controle("standby is nul", all(w == 0 for s, w in op20f), f"{op20f}")
op20g, _, _, _ = draai(lambda s: 1500.0, soc=5.0, seconden=60)
controle("op de ontlaadgrens komt er niets uit", all(w >= 0 for s, w in op20g), f"{op20g}")
op20h, _, _, _ = draai(lambda s: -1500.0, soc=95.0, seconden=60)
controle("op de laadgrens gaat er niets in", all(w <= 0 for s, w in op20h), f"{op20h}")

print("21. de zekering begrenst het laden")
r21 = Regelaar()
nu21 = DAG.replace(hour=3)
uit21 = r21.stap(nu21, net_w=200.0, net_op=nu21, batterij_w=0.0,
                 besluit=Besluit(MAX_LADEN, power_w=3500.0), b=anker(), ruimte_w=1200.0)
controle("maximaal laden blijft onder wat de zekering overlaat", uit21 == 1200.0, f"{uit21}")

print("22. mikken op de goedkope kant van nul")
controle("bij een lage terugleverprijs iets onder nul", Regelaar().doel_w(0.2417, 0.0193) == -20.0)
controle("bij salderen precies op nul", Regelaar().doel_w(0.24, 0.24) == 0.0)

# Gemeten op 22-09-2026 in de eerste woning, naast een kWh-meter op dezelfde
# batterij: de vermogenssensor van de Anker loopt vijf tot tien seconden
# achter, toont onderweg een aanloop die er niet is en vlak na een opdracht de
# opdracht zelf. De sturing die daar toen draaide rekende daarmee en slingerde:
# vijf keer 3.500 W en drie keer ontladen in zes minuten. De regelaar rekent
# daarom met zijn eigen opdracht en gebruikt de sensor alleen als bevestiging.
ANKER = dict(sensor_na=8, sensor_aanloop=True, sensor_echo=2)

print("26. dezelfde sprong, gezien door de sensor van de Anker")
op26, meter26, _, lev26 = draai(lambda s: 300.0 if s < 60 else 2400.0, seconden=180, **ANKER)
print(f"  opdrachten: {op26}")
na26 = [w for s, w in meter26 if s >= 80]
controle("hij slingert niet: een handvol opdrachten", len(op26) <= 4, f"{len(op26)}")
controle("en de meter staat na twintig seconden rond nul",
         all(abs(w) <= 60 for w in na26), f"{[round(w) for w in na26[:6]]}")
controle("zonder doorschot naar terugleveren", all(w >= -60 for s, w in meter26),
         f"{min(w for s, w in meter26):.0f} W")

print("27. de oven op zijn thermostaat, gezien door de sensor van de Anker")
op27, _, af27, lev27 = draai(lambda s: 300.0 + (2000.0 if (s // 45) % 2 == 0 else 0.0), seconden=1800, **ANKER)
print(f"  {len(op27)} opdrachten, {af27:.3f} kWh van het net, {lev27:.3f} kWh terug")
controle("evenveel opdrachten als met een eerlijke sensor", len(op27) <= len(op18) + 2, f"{len(op27)} tegen {len(op18)}")
controle("en niet meer terugleveren dan met een eerlijke sensor", lev27 <= lev18 + 0.005, f"{lev27:.3f} tegen {lev18:.3f}")

print("28. een batterij zonder vermogenssensor")
op28, meter28, _, _ = draai(lambda s: 300.0 if s < 60 else 2400.0, seconden=180, geen_sensor=True)
print(f"  opdrachten: {op28}")
controle("de sprong wordt gevolgd zodra de meter hem na de opdracht gezien heeft",
         len(op28) <= 4 and all(abs(w) <= 60 for s, w in meter28 if s >= 80), f"{[round(w) for s, w in meter28[10:18]]}")

print("29. een batterij die niets doet met een opdracht")
# Vol, leeg, te warm: de sensor blijft op nul terwijl de opdracht iets anders
# zegt. Na `AFWIJK_METINGEN` gelooft de regelaar de sensor en houdt hij op met
# aandringen, in plaats van elke vijftien seconden een nieuwe opdracht.
op29, _, _, _ = draai(lambda s: 1500.0, seconden=300, volgt_niet=True)
print(f"  opdrachten: {op29}")
controle("hij dringt niet elke vijftien seconden opnieuw aan", len(op29) <= 3, f"{len(op29)}")
controle("en de laatste opdracht is wat het huis vraagt", op29 and abs(op29[-1][1] + 1500.0) <= 60, f"{op29}")


# --- geld en rendement ------------------------------------------------------------

print("23. wat de batterij verdient")
v1 = bat.verdiend(0.0, -1000.0, 0.2417, 0.0193, 3600.0)
controle("een uur 1 kW ontladen naar het huis bespaart een kWh inkoop", abs(v1 - 0.2417) < 1e-9, f"{v1}")
v2 = bat.verdiend(0.0, 1000.0, 0.2417, 0.0193, 3600.0)
controle("een uur 1 kW zon opslaan kost wat terugleveren had opgebracht", abs(v2 + 0.0193) < 1e-9, f"{v2}")
v3 = bat.verdiend(1000.0, 1000.0, 0.13, 0.05, 3600.0)
controle("een uur 1 kW van het net laden kost de prijs van dat uur", abs(v3 + 0.13) < 1e-9, f"{v3}")
controle("zonder prijs geen bedrag", bat.verdiend(0.0, -1000.0, None, None, 60.0) is None)
# Wat de zon die erin ging minder waard was dan zelf gebruikt (v0.101.2), met
# salderen: koop 0,24171 en terug 0,24171 min 0,052756 terugleverkosten.
K, T = 0.24171, 0.24171 - 0.052756
z1 = bat.zon_in_accu(0.0, 1000.0, K, T, 3600.0)
controle("een uur 1 kW zon de batterij in, meter op nul: een kWh maal koop min terug",
         abs(z1 - 0.052756) < 1e-9, f"{z1}")
controle("van het net laden is geen zon", bat.zon_in_accu(1000.0, 1000.0, K, T, 3600.0) == 0.0)
controle("ontladen naar het huis ook niet", bat.zon_in_accu(0.0, -1000.0, K, T, 3600.0) == 0.0)
z4 = bat.zon_in_accu(-1000.0, -1000.0, K, T, 3600.0)
controle("ontladen naar het net telt terug: de teruglevering kwam uit de batterij",
         abs(z4 + 0.052756) < 1e-9, f"{z4}")
z5 = bat.zon_in_accu(-500.0, 1000.0, K, T, 3600.0)
controle("half opgeslagen, half teruggeleverd: alleen wat erin ging", abs(z5 - 0.052756) < 1e-9, f"{z5}")
controle("zonder prijs niets", bat.zon_in_accu(0.0, 1000.0, None, None, 60.0) is None)

print("24. geen terugverdientijd (v0.101.1)")
# De eigenaar op 29-09-2026: een datum in het paneel die afwijkt van wat een
# installateur de klant voorrekende is niet te verdedigen. Het kasboek blijft.
controle("batterij.py rekent geen terugverdientijd meer uit",
         not hasattr(bat, "terugverdiend") and not hasattr(bat, "TERUGVERDIEN_MIN_DAGEN"))

print("25. het rendement uit de tellers van de eerste woning")
r25 = bat.rendement_uit_tellers(250.0, 184.0, 14.6)
print(f"  {r25 * 100:.1f}%")
controle("250 erin en 184 eruit is 73,6%", abs(r25 - 0.736) < 0.0005, f"{r25}")
controle("met te weinig doorzet nog geen rendement", bat.rendement_uit_tellers(40.0, 30.0, 14.6) is None)
controle("de tellers van de batterij zelf (meer eruit dan erin) worden geweigerd",
         bat.rendement_uit_tellers(200.0, 205.0, 14.6) is None)

print("=== 30. een meting van vóór de bevestiging telt niet (22-09-2026, 's nachts in de eerste woning) ===")
# De batterij volgde pas na tien seconden. De meter van :08 toonde nog de oude
# stand, de sensor van :09 al de nieuwe, en de regelaar telde die oude meting
# bij de nieuwe stand op: 230 W ontladen bevestigd, meter -2141 W, en dan 966 W
# láden op 12% midden in de nacht. Elke tien seconden de andere kant op.
r30 = Regelaar()
b30 = anker(soc=12.0)
t0 = DAG.replace(hour=23, minute=21, second=48)
# De last gaat aan: de meter zegt 2139 W afname, de batterij deed 190 W ontladen.
uit30 = r30.stap(t0, net_w=2139.0, net_op=t0, batterij_w=-188.0, besluit=Besluit(NUL), b=b30)
controle("de last gaat aan: meteen ontladen", uit30 is not None and uit30 < -2000, f"{uit30}")
# Vijf seconden later is de last alweer uit; de batterij doet nog het oude.
controle("vijf seconden later nog niet bezonken: de sensor toont nog de oude stand",
         r30.stap(t0 + dt.timedelta(seconds=5), net_w=-22.0, net_op=t0 + dt.timedelta(seconds=5),
                  batterij_w=-188.0, besluit=Besluit(NUL), b=b30) is None, "")
# Om :58 zegt de sensor dat de batterij ontlaadt (het huis vraagt 190 W); de meter van datzelfde moment
# telt nog niet, want die kan van vlak vóór de omslag zijn.
t1 = t0 + dt.timedelta(seconds=10)
controle("de sensor bevestigt: de meter van datzelfde moment telt nog niet",
         r30.stap(t1, net_w=-1949.0, net_op=t1, batterij_w=-2150.0, besluit=Besluit(NUL), b=b30) is None
         and r30.bevestigd_op == t1, f"{r30.bevestigd_op}")
uit30b = r30.stap(t1 + dt.timedelta(seconds=5), net_w=-1949.0, net_op=t1 + dt.timedelta(seconds=5),
                  batterij_w=-2150.0, besluit=Besluit(NUL), b=b30)
controle("de tik daarna wel: terug naar wat het huis vraagt",
         uit30b is not None and -300 < uit30b < -150, f"{uit30b}")
# Nu het geval van die nacht: om :08 meet de meter nog -1949 (de batterij doet nog
# 2150), om :09 zegt de sensor 200 (de nieuwe stand). De meter is van vóór die
# bevestiging en telt dus niet: geen opdracht, laat staan 966 W laden.
t2 = t1 + dt.timedelta(seconds=10)
controle("een meter van vóór de bevestiging telt niet", r30.stap(
    t2 + dt.timedelta(seconds=1), net_w=-1949.0, net_op=t2, batterij_w=-200.0,
    besluit=Besluit(NUL), b=b30) is None, f"{r30.opdracht_w}")
controle("en de bevestiging is onthouden", r30.bevestigd_op == t2 + dt.timedelta(seconds=1), f"{r30.bevestigd_op}")
# De volgende metertik, :13, meet -10: dat is het huis met de nieuwe stand erin.
t3 = t2 + dt.timedelta(seconds=5)
uit30c = r30.stap(t3, net_w=-10.0, net_op=t3, batterij_w=-200.0, besluit=Besluit(NUL), b=b30)
controle("de tik daarna telt wel, en die vraagt hooguit een kleine bijstelling",
         uit30c is None or -300 < uit30c < -100, f"{uit30c}")
controle("na vijftien seconden gaat hij hoe dan ook verder", (lambda r: (
    r._zet(t0, -2000.0) or True) and r.stap(t0 + dt.timedelta(seconds=15), net_w=-1800.0,
    net_op=t0 + dt.timedelta(seconds=14), batterij_w=-500.0, besluit=Besluit(NUL), b=b30) is not None
)(Regelaar()), "")

print("31. morgenvroeg nooit meer over dan er in de accu past")
# De bewoner van de eerste woning op 23-09-2026 om 14:10, bij "je houdt naar
# verwachting 15,9 kWh over in je accu" onder een accu van 14,6 kWh: "hoe kan je
# ooit 16 kWh in een accu hebben van 14 kWh?" Die middag: 79%, 12,4 kWh zon tot
# de avond, 4,5 kWh huis tot morgenvroeg. De oude som: 10,8 x 0,736 + 12,4 - 4,5
# = 15,9.
middag31 = DAG.replace(hour=14, minute=10)
zon31 = {14: 3.1, 15: 3.1, 16: 2.8, 17: 2.2, 18: 1.2}
huis31 = 4.5 / 17  # 17 uur tot 07:00, gelijk verdeeld
v31 = verwachting(zon31, huis=huis31)
a31 = anker(soc=79.0)
bal31 = bat.balans_kwh(middag31, v31, a31)
vol31 = (95.0 - 5.0) / 100.0 * 14.6 * 0.736
print(f"  balans {bal31:.2f} kWh, hooguit {vol31:.2f}: {bat.plan_batterij(middag31, [], Tariff(), v31, a31).plan}")
controle("wat er over is past in de accu: tot de laadgrens, na het verlies", 0 < bal31 <= vol31 + 1e-9, f"{bal31:.2f}")
inhoud31, tekort31, weg31 = bat.nachtverloop(middag31, v31, a31)
controle("de zon die er niet in past gaat naar het net en wordt genoemd",
         weg31 > 5 and "niet meer in de accu" in bat._vooruitkijk_zin(middag31, v31, a31), f"weg {weg31:.2f}")
# De nacht erna: de accu loopt leeg, en wat er dan nog ontbreekt is tekort,
# ook als de zon morgenvroeg weer komt.
nacht31 = bat.balans_kwh(DAG.replace(hour=20), verwachting({}, huis=1.0), anker(soc=20.0))
controle("een lege accu in de nacht: tekort, uitgerekend uur voor uur",
         # Sinds v0.142.0 het verlies van het ontladen alleen, de helft heen en terug.
         nacht31 is not None and nacht31 < 0 and abs(nacht31 - (-(11.0 - (0.15 * 14.6) * 0.736 ** 0.5))) < 0.05,
         f"{nacht31}")

print("32. de batterij helpt de auto alleen met wat er echt over is (v0.90.0)")
# De bewoner van de eerste woning op 23-09-2026, naar evcc: "bij laden van de auto
# mag alle batterijcapaciteit boven X% gebruikt worden." De eigenaar: de
# nachtbalans gaat voor, "auto laden vanuit de batterij doe je echt alleen als er
# te veel capaciteit over is; drie keer verlies."
a32 = anker(soc=80.0, auto_boven=40.0)
# 14,6 kWh, rendement 0,736: morgenvroeg 3,0 kWh over is 3,0 / 0,858 = 3,50 kWh
# aan de accukant (sinds v0.142.0 met het verlies van het ontladen alleen, tot dan
# met het hele verlies heen en terug), 24,0 procentpunt: de nacht heeft 56,0% nodig.
controle("de nacht gaat voor: grens 56% en niet de 40% van de bewoner",
         abs(bat.auto_grens(a32, 3.0) - (80.0 - 3.0 / 0.736 ** 0.5 / 14.6 * 100)) < 0.01, f"{bat.auto_grens(a32, 3.0)}")
controle("is er ruim genoeg over, dan is de grens van de bewoner de ondergrens",
         bat.auto_grens(a32, 20.0) == 40.0, f"{bat.auto_grens(a32, 20.0)}")
controle("weet hij de nacht niet, dan helpt hij niet", bat.auto_grens(a32, None) is None, "")
controle("zonder grens van de bewoner helpt hij nooit", bat.auto_grens(anker(soc=80.0), 20.0) is None, "")
uit32 = anker(soc=80.0, auto_boven=40.0, nacht=False)
controle("nachtstrategie uit: de grens van de bewoner", bat.auto_grens(uit32, None) == 40.0, f"{bat.auto_grens(uit32, None)}")
controle("en nooit onder de eigen ondergrens", bat.auto_grens(anker(soc=80.0, auto_boven=0.0, nacht=False), None) == 5.0,
         f"{bat.auto_grens(anker(soc=80.0, auto_boven=0.0, nacht=False), None)}")

nul32 = bat.Besluit(bat.NUL, reason="nul", rule="nul")
helpt = bat.met_paal(nul32, True, a32, 20.0)
print(f"  {helpt.stand}: {helpt.reason}")
controle("boven de grens: nul op de meter, dus de auto krijgt uit de batterij",
         helpt.stand == bat.NUL and helpt.rule == "auto-helpen" and helpt.grenzen[1], f"{helpt.stand} {helpt.rule}")
niet = bat.met_paal(bat.Besluit(bat.NUL, reason="nul", rule="nul"), True, anker(soc=40.5, auto_boven=40.0), 20.0)
controle("op de grens (binnen de marge): niets afgeven", niet.rule == "paal-laadt" and not niet.grenzen[1], f"{niet.rule}")
# Hysterese: al aan het helpen, dan tot de grens; opnieuw beginnen pas 5% erboven.
dicht = anker(soc=43.0, auto_boven=40.0)
controle("net boven de grens: niet opnieuw beginnen",
         bat.met_paal(bat.Besluit(bat.NUL, reason="nul", rule="nul"), True, dicht, 20.0).rule == "paal-laadt", "")
controle("maar wel doorgaan als hij al hielp",
         bat.met_paal(bat.Besluit(bat.NUL, reason="nul", rule="nul"), True, dicht, 20.0, helpt=True).rule == "auto-helpen", "")
controle("een vaste grens uit de besluitronde gaat voor de eigen som",
         bat.met_paal(bat.Besluit(bat.NUL, reason="nul", rule="nul"), True, dicht, 20.0, grens=30.0).rule == "auto-helpen", "")
controle("zonder batterijgegevens zoals altijd: niets afgeven",
         bat.met_paal(bat.Besluit(bat.NUL, reason="nul", rule="nul"), True).rule == "paal-laadt", "")


print("=== 33. het uurplan weet welke uren de batterij de auto helpt (v0.95.0) ===")
# De bewoner van de eerste woning op 23-09-2026 om 22:40: "theoretisch zou 'wat gaat
# hij doen' nu moeten kijken naar de EV-laadplanning, en zien dat hij om 23 uur mee
# moet gaan helpen laden." Die avond: van 23:00:48 tot 23:17:43 op 3,45 kW, van 78
# naar de 70% die de grens was.
N33 = dt.datetime(2026, 9, 23, 23, 0)
a33 = anker(soc=78.0, auto_boven=70.0, nacht=False, max_discharge_w=3500.0)
eta33 = 0.736 ** 0.5
per_uur33 = 0.2 / eta33 / 14.6 * 100.0          # wat het huis per uur aan de accukant kost
uren33 = [
    bat.Uur(N33 + dt.timedelta(hours=i), N33 + dt.timedelta(hours=i + 1), bat.NUL, -0.2, 0.0,
            78.0 - (i + 1) * per_uur33, 0.30)
    for i in range(3)
]
laden33 = [(N33, N33 + dt.timedelta(hours=1), 5.9), (N33 + dt.timedelta(hours=2), N33 + dt.timedelta(hours=3), 8.3)]
hulp33 = bat.auto_hulp(uren33, a33, None, laden33)
# Boven 70%: 8 procentpunt van 14,6 kWh, min wat het huis in dat uur neemt, na het verlies.
verwacht33 = ((78.0 - 70.0) / 100.0 * 14.6 - 0.2 / eta33) * eta33
print(f"  per uur naar de auto: {[round(x, 3) for x in hulp33]} (verwacht {verwacht33:.3f} in het eerste uur)")
controle("om 23:00 helpt hij, tot de grens van de bewoner, na het huis en het verlies",
         abs(hulp33[0] - verwacht33) < 1e-6, f"{hulp33}")
controle("om 01:00 is er niets meer boven de grens", hulp33[2] == 0.0 and hulp33[1] == 0.0, f"{hulp33}")
weg33 = bat._met_auto(uren33, a33, hulp33)
controle("het uurplan zegt het: naar de auto, en de accustand zakt naar de grens",
         uren33[0].auto_kwh == hulp33[0] and abs(uren33[0].soc - 70.0) < 0.01 and abs(weg33 - hulp33[0]) < 1e-9,
         f"{uren33[0]}")
controle("en de uren daarna schuiven mee omlaag", uren33[2].soc < 70.0, f"{uren33[2].soc}")

nacht33 = anker(soc=78.0, auto_boven=50.0, nacht=True, max_discharge_w=3500.0)
uren33b = [bat.Uur(N33, N33 + dt.timedelta(hours=1), bat.NUL, 0.0, 0.0, 78.0, 0.30)]
kort33 = bat.auto_hulp(uren33b, nacht33, 0.5, [(N33, N33 + dt.timedelta(hours=1), 9.0)])
controle("met de nachtstrategie nooit meer dan wat er morgenvroeg over zou zijn",
         abs(kort33[0] - 0.5) < 1e-6, f"{kort33}")
controle("weet hij de nacht niet, dan helpt hij in het plan ook niet",
         bat.auto_hulp(uren33b, nacht33, None, [(N33, N33 + dt.timedelta(hours=1), 9.0)]) == [0.0], "")
dicht33 = anker(soc=74.0, auto_boven=70.0, nacht=False, max_discharge_w=3500.0)
uren33c = [bat.Uur(N33, N33 + dt.timedelta(hours=1), bat.NUL, 0.0, 0.0, 74.0, 0.30)]
controle("binnen de marge boven de grens begint hij niet, zoals de regelaar",
         bat.auto_hulp(uren33c, dicht33, None, laden33) == [0.0], "")
controle("maar hielp hij al, dan wel", bat.auto_hulp(uren33c, dicht33, None, laden33, helpt=True)[0] > 0, "")
laadt33 = [bat.Uur(N33, N33 + dt.timedelta(hours=1), bat.NETLADEN, 2.0, 2.0, 88.0, 0.10)]
controle("een uur waarin hij zelf van het net laadt helpt hij niet",
         bat.auto_hulp(laadt33, a33, None, laden33) == [0.0], "")

# En het hele plan: een vast contract om 23:00, de auto laadt van 23:00 tot 00:00.
b33 = anker(soc=78.0, auto_boven=70.0, nacht=False, max_discharge_w=3500.0)
plan33 = bat.plan_batterij(N33, [], VAST, verwachting(huis=0.2, dag=DAG.replace(day=23)), b33,
                           auto_laden=[(N33, N33 + dt.timedelta(hours=1), 5.9)])
print(f"  {plan33.stand}: {plan33.plan}")
controle("het besluit draagt de hulp in zijn uren, en wat er aan de accukant uit gaat",
         plan33.uren and plan33.uren[0].auto_kwh > 0.5 and plan33.auto_weg > 0.5,
         f"{[(u.start.hour, u.stand, round(u.auto_kwh, 2)) for u in plan33.uren[:3]]} {plan33.auto_weg}")
controle("en de zin tot morgenvroeg noemt de auto", "de auto krijgt er" in plan33.plan, plan33.plan)
zonder33 = bat.plan_batterij(N33, [], VAST, verwachting(huis=0.2, dag=DAG.replace(day=23)), anker(soc=78.0, auto_boven=70.0, nacht=False, max_discharge_w=3500.0))
controle("zonder plan van de paal verandert er niets", zonder33.auto_weg == 0.0 and all(u.auto_kwh == 0 for u in zonder33.uren), "")


print("34. geduld met een last die korter duurt dan de lus (24-09-2026, de eerste woning)")
# Om de dertig seconden tien seconden 490 W bovenop 250 W, de sensor van de Anker, en
# een batterij die na vijf seconden volgt. De regelaar van v0.96.0 stond daar in
# tegenfase: 07:44:06 opdracht 688, 07:44:14 de batterij op 681, 07:44:16 de last weg.
def wissel34(s):
    return 250.0 + (490.0 if s % 30 < 10 else 0.0)


r34 = Regelaar()
op34, meter34, af34, lev34 = draai(wissel34, seconden=1800, regelaar=r34, **ANKER)
print(f"  {len(op34)} opdrachten in een half uur, {af34:.3f} kWh van het net, {lev34:.3f} kWh terug")
eigen34 = bat.Regelaar.geduldig
bat.Regelaar.geduldig = lambda self, now: False
oud34, _, oudaf34, oudlev34 = draai(wissel34, seconden=1800, **ANKER)
bat.Regelaar.geduldig = eigen34
print(f"  zonder geduld: {len(oud34)} opdrachten, {oudaf34:.3f} kWh van het net, {oudlev34:.3f} kWh terug")
controle("zonder geduld stond hij in tegenfase, zoals die nacht", len(oud34) >= 60, f"{len(oud34)}")
controle("met geduld een handvol opdrachten in een half uur", len(op34) <= 6, f"{op34}")
controle("hij dekt de basis en laat de last gaan", op34 and abs(op34[-1][1] + 250.0) <= 60, f"{op34}")
controle("en er gaat bijna niets meer naar het net", lev34 <= 0.01, f"{lev34:.3f} tegen {oudlev34:.3f}")
controle("aan het eind heeft hij nog steeds geduld", r34.geduldig(DAG.replace(hour=12) + dt.timedelta(seconds=1800)), f"{r34.geduldig_tot}")


def ketel34(s):
    if s < 600:
        return wissel34(s)
    return 250.0 + (2000.0 if 600 <= s < 780 else 0.0)


op34b, _, _, _ = draai(ketel34, seconden=900, regelaar=Regelaar(), **ANKER)
na34b = [(s, w) for s, w in op34b if s >= 600]
print(f"  een waterkoker van 2 kW met geduld: {na34b}")
controle("een waterkoker die blijft volgt hij na een halve minuut, niet eerder",
         na34b and 630 <= na34b[0][0] <= 650 and na34b[0][1] <= -2000, f"{na34b}")
controle("en als hij uitgaat meteen terug", any(780 <= s <= 800 and w > -300 for s, w in na34b), f"{na34b}")


def later34(s):
    if s < 300:
        return wissel34(s)
    return 250.0 + (2000.0 if s >= 1500 else 0.0)


op34c, _, _, _ = draai(later34, seconden=1560, regelaar=Regelaar(), **ANKER)
na34c = [(s, w) for s, w in op34c if s >= 1500]
controle("een kwartier zonder korte lasten en het geduld is op: de waterkoker meteen",
         na34c and na34c[0][0] <= 1505 and na34c[0][1] <= -2000, f"{na34c}")
controle("een oven op zijn thermostaat (45 s) volgt hij zonder geduld, zoals altijd",
         af18 < zonder18 * 0.35, f"{af18:.3f}")


print("=== 35. doet de batterij zelf nul, dan grijpt de coach alleen in om in te kopen (v0.101.9) ===")
# De eigenaar op 29-09-2026, in de klantwoning: "de coach moet de batterij niet zelf
# sturen. Eigenlijk is de nul op de meter bij anker zelf beter toch? Dus ik stel voor
# dat de coach alleen goedkoop inkoopt en de anker stopt als de laadpaal aan gaat."
# Die middag koos de coach om 15:51 standby: vanavond was een kWh meer waard dan nu.
# Een dynamisch contract met salderen: teruglevering is de prijs min de opslag.
UUR35 = [0.24, 0.24, 0.24, 0.24, 0.24, 0.27, 0.31, 0.36, 0.40, 0.33, 0.28, 0.25,
         0.22, 0.21, 0.22, 0.285, 0.27, 0.35, 0.40, 0.42, 0.36, 0.34, 0.33, 0.30]
MORGEN35 = [0.24, 0.239, 0.243, 0.244, 0.24, 0.27, 0.31, 0.36, 0.40, 0.33, 0.28, 0.25,
            0.21, 0.20, 0.22, 0.28, 0.29, 0.37, 0.41, 0.43, 0.37, 0.35, 0.34, 0.31]
LIJST35 = prijzen(UUR35 + MORGEN35, terug=[p - 0.0242 for p in UUR35 + MORGEN35])
NU35 = DAG.replace(hour=15, minute=51)
V35 = verwachting({8: 0.3, 9: 0.8, 10: 1.5, 11: 2.0, 12: 2.2, 13: 2.0, 14: 1.5, 15: 1.0, 16: 0.5}, huis=0.6)
b35 = plan_batterij(NU35, LIJST35, Tariff(), V35, anker(soc=58.0))
z35 = plan_batterij(NU35, LIJST35, Tariff(), V35, anker(soc=58.0, zelf_nul=True))
print(f"  gewoon:    {b35.stand:10s} {b35.rule:12s} {b35.reason}")
print(f"  zelf nul:  {z35.stand:10s} {z35.rule:12s} {z35.reason}")
controle("zonder het vinkje kiest de coach die middag stilstaan", b35.stand == STANDBY, f"{b35.stand} {b35.rule}")
controle("met het vinkje: nul op de meter, en dat doet de batterij zelf", z35.stand == NUL, f"{z35.stand} {z35.rule}")
standen35 = {u.stand for u in z35.uren}
controle("in het uurplan staat niets wat de batterij in zijn eigen stand niet kan",
         standen35 <= {NUL, NETLADEN, STANDBY} and not [u for u in z35.uren if u.stand == STANDBY and u.kwh != 0.0],
         f"{sorted(standen35)}")
net35 = [u for u in z35.uren if u.stand == NETLADEN]
print(f"  van het net: {[(u.start.strftime('%d %H:%M'), round(u.kwh, 2)) for u in net35]}")
later35 = lambda u: max(v.price for v in z35.uren if v.start > u.start)  # noqa: E731
controle("goedkoop inkopen doet hij nog wel: 's nachts, en elk inkoopuur loont na het verlies",
         net35 and any(u.start.hour < 6 for u in net35) and all(u.price <= 0.736 * later35(u) for u in net35),
         f"{[(u.start, round(u.kwh, 2), u.price, later35(u)) for u in net35]}")
# Een nacht rond het goedkoopste kwartier: laden van het net blijft een besluit van de coach.
z35n = plan_batterij(DAG.replace(day=22, hour=1, minute=5), LIJST35, Tariff(), V35, anker(soc=12.0, zelf_nul=True))
print(f"  01:05 op 12%: {z35n.stand} {z35n.rule} {z35n.power_w}")
controle("om 01:05 op 12% laadt hij van het net, en dat doet de coach", z35n.stand == NETLADEN, f"{z35n.stand} {z35n.rule}")
p35 = plan_batterij(NU35, LIJST35, Tariff(), V35, anker(soc=58.0, zelf_nul=True), paal_laadt=True)
controle("laadt de paal, dan stopt de coach hem, ook met het vinkje",
         p35.rule == "paal-laadt" and p35.stand in (ZONNELADEN, STANDBY), f"{p35.stand} {p35.rule}")
# Zonder rendement en met volledig salderen stond hij stil; met het vinkje doet hij het zelf.
s35 = plan_batterij(DAG.replace(hour=12), [], Tariff(buy=0.24, feed_in=0.24), verwachting(ZON),
                    anker(rte=None, zelf_nul=True))
controle("volledig salderen zonder rendement: de batterij doet het zelf in plaats van stilstaan",
         s35.stand == NUL, f"{s35.stand} {s35.rule}")
# De eerste proef van dit bestand, een vast contract met zon: met of zonder vinkje hetzelfde.
for uur in (3, 12, 21):
    a35, c35 = (plan_batterij(DAG.replace(hour=uur), [], VAST, verwachting(ZON), anker(zelf_nul=z)) for z in (False, True))
    controle(f"vast contract om {uur}:00: met het vinkje hetzelfde besluit", a35.stand == c35.stand, f"{a35.stand} {c35.stand}")



print("=== 36. een vast contract: van het net laden loont nooit, en dat zegt hij ook (v0.101.10) ===")
# De eigenaar op 29-09-2026, bij zijn eigen batterij: "Hij houdt de meter op nul. Het
# rendement van de batterij is nog niet bekend, dus van het net laden doet hij nog niet."
# "Waarom zegt de coach dit terwijl ik een vast contract heb? Inkopen is niet rendabel
# en heeft alleen maar verlies."
v36 = plan_batterij(DAG.replace(hour=21), [], VAST, verwachting(ZON), anker(rte=None))
print(f"  vast, geen rendement: {v36.stand} {v36.rule} | {v36.reason} | {v36.plan}")
controle("vast contract zonder rendement: nul op de meter, zonder te beloven dat hij gaat inkopen",
         v36.stand == NUL and "rendement" not in v36.reason and "van het net laden doet hij nog niet" not in v36.reason,
         v36.reason)
controle("en hij zegt waarom inkopen hier nooit loont", "nooit" in (v36.plan or ""), f"{v36.plan}")
v36z = plan_batterij(DAG.replace(hour=21), [], VAST, verwachting(ZON), anker(rte=None, zelf_nul=True))
controle("ook als de batterij het zelf doet", v36z.stand == NUL and "nooit" in (v36z.plan or ""), f"{v36z.plan}")
m36 = plan_batterij(DAG.replace(hour=21), [], VAST, verwachting(ZON, huis=1.0), anker(soc=20.0))
print(f"  vast, met rendement, tekort: {m36.plan}")
controle("met rendement en een tekort voor de nacht: geen 'hij laadt bij als de stroom goedkoop genoeg is'",
         "goedkoop genoeg" not in (m36.plan or "") and "van het net" in (m36.plan or ""), f"{m36.plan}")
d36 = plan_batterij(DAG.replace(hour=21), LIJST35, Tariff(), V35, anker(rte=None))
controle("een dynamisch contract zonder rendement: daar kan inkopen wel lonen, dus die uitleg blijft",
         d36.rule == "rendement-onbekend", f"{d36.rule}")
DAL36 = prijzen([0.20] * 7 + [0.26] * 16 + [0.20] + [0.20] * 7 + [0.26] * 16 + [0.20])
p36 = plan_batterij(DAG.replace(hour=21), DAL36, Tariff(), verwachting(ZON, huis=1.0), anker(soc=20.0))
# Sinds v0.102.3 zegt hij daar waarom het vannacht niet loont, met de prijs erbij.
controle("een vast contract met dal- en piektarief: bijladen kan lonen, dus hij rekent het voor",
         p36.stand == NETLADEN or ("via de batterij" in (p36.plan or "") and "nooit" not in (p36.plan or "")),
         f"{p36.stand} {p36.plan}")


print("=== 37. een beurt van het net loopt door tot het eind, en een kleine is geen overname (v0.102.3) ===")
# De klantwoning op 30-09-2026: een Anker die zelf nul doet, prijzen per kwartier.
# Overdag laadde hij elk kwartier twaalf minuten en drie niet (3,5 kW maal 2:20 is
# 0,136 kWh, onder de procent van de batterij), en 's nachts zei hij midden in het
# laden "nul op de meter" en dekte hij de warmtepomp uit de batterij.
import re  # noqa: E402

from scenarios import KWARTIER_30_09  # noqa: E402


def kwartieren(dagen=("2026-09-30", "2026-10-01")):
    uit = []
    for dag in dagen:
        begin = dt.datetime.fromisoformat(dag)
        for i, p in enumerate(KWARTIER_30_09[dag]):
            uit.append({"start": begin + dt.timedelta(minutes=15 * i),
                        "end": begin + dt.timedelta(minutes=15 * (i + 1)),
                        "price": p, "feed_in": round(p - 0.01815, 5)})
    return uit


K37 = kwartieren()
DAG37 = dt.datetime(2026, 9, 30)
V37 = verwachting(huis=0.6, dag=DAG37)


def klant37(soc, **kw):
    return anker(soc, capacity_kwh=14.5, max_discharge_w=3500.0, zelf_nul=True, **kw)


# Midden op de dag, 2:20 voor het eind van een goedkoop kwartier (€ 0,180), met
# nog goedkope kwartieren erna.
NU37 = dt.datetime(2026, 9, 30, 12, 27, 40)
a37 = plan_batterij(NU37, K37, Tariff(), V37, klant37(40.0, overgenomen=True, vorige_stand=NETLADEN))
f37 = plan_batterij(NU37, K37, Tariff(), V37, klant37(40.0))
print(f"  12:27:40, beurt loopt: {a37.stand} {a37.power_w:.0f} W | {a37.reason}")
print(f"  12:27:40, vers:        {f37.stand} {f37.power_w:.0f} W")
controle("de laatste minuten van een goedkoop kwartier laadt hij gewoon door",
         a37.stand == NETLADEN and a37.power_w > 3000, f"{a37.stand} {a37.power_w:.0f}")
controle("ook als hij nog niet laadde: de hele beurt telt, niet de rest van dit kwartier",
         f37.stand == NETLADEN, f"{f37.stand} {f37.power_w:.0f}")

# Het eind van een beurt, in een nagemaakte dag: vier goedkope kwartieren
# (€ 0,150-0,153) om 12:00, verder € 0,36 en 's avonds € 0,45. Hij wil in alle
# vier voluit laden, dus om 12:57:40 moet er nog 3,5 kW maal 2:20 bij: 0,136 kWh,
# minder dan de procent (0,145). En een stap van het rooster is hier
# (95 - 5)% van 14,5 kWh gedeeld door 40, aan de wisselstroomkant 0,38 kWh.
def kw37(dag, avond=0.45):
    uit = []
    for i in range(96):
        van = dag + dt.timedelta(minutes=15 * i)
        p = 0.150 + 0.001 * (i - 48) if 48 <= i < 52 else (avond if i >= 68 else 0.36)
        uit.append({"start": van, "end": van + dt.timedelta(minutes=15), "price": p, "feed_in": p - 0.01815})
    return uit


S37 = kw37(DAG37) + kw37(DAG37 + dt.timedelta(days=1), avond=0.36)
W37 = verwachting(huis=1.0, dag=DAG37)


def op37(uur, minuut, seconde=0, **kw):
    return plan_batterij(DAG37.replace(hour=uur, minute=minuut, second=seconde), S37, Tariff(), W37, klant37(40.0, **kw))


loopt = op37(12, 57, 40, overgenomen=True, vorige_stand=NETLADEN)
vers = op37(12, 57, 40, overgenomen=True)
zelf = op37(12, 57, 40)
print(f"  12:57:40, rest {loopt.uren[0].net_kwh:.3f} kWh: loopt {loopt.stand} {loopt.power_w:.0f} W, "
      f"vers {vers.stand}, zelf {zelf.stand}")
controle("het eind van een beurt die loopt maakt hij af, ook onder de procent",
         loopt.stand == NETLADEN and loopt.power_w > 3000, f"{loopt.stand} {loopt.power_w:.0f}")
controle("maar voor zo'n restje begint hij niet", vers.stand == NUL, f"{vers.stand}")
controle("en een batterij die het zelf doet neemt hij er ook niet voor over", zelf.stand == NUL, f"{zelf.stand}")
midden = op37(12, 27, 40)
controle("halverwege de beurt, 2:20 voor het eind van een kwartier: laden, want de beurt loopt door",
         midden.stand == NETLADEN and midden.power_w > 3000, f"{midden.stand} {midden.power_w:.0f}")
vijf_zelf, vijf_over = op37(12, 55), op37(12, 55, overgenomen=True)
print(f"  12:55, rest {vijf_over.uren[0].net_kwh:.3f} kWh: zelf {vijf_zelf.stand}, overgenomen {vijf_over.stand}")
controle("een beurt onder één stap van het rooster: een batterij die het zelf doet niet overnemen",
         vijf_zelf.stand == NUL, f"{vijf_zelf.stand}")
controle("heeft hij hem al, dan laadt hij wel", vijf_over.stand == NETLADEN, f"{vijf_over.stand}")
tien_zelf = op37(12, 50)
controle("een beurt van meer dan een stap (0,58 kWh): dan neemt hij hem wel over",
         tien_zelf.stand == NETLADEN, f"{tien_zelf.stand} {tien_zelf.uren[0].net_kwh:.3f}")
klein = next((u for u in loopt.uren if u.start >= DAG37.replace(hour=13)), None)
controle("en na het goedkope uur laadt het plan niet meer", klein is not None and klein.stand != NETLADEN,
         f"{klein}")

# 's Avonds om 19:47, zoals de eigenaar het zag: 42%, een tekort voor de nacht,
# en niets van het net. De zin zegt nu waarom: de goedkoopste stroom tot
# morgenvroeg is € 0,313 om 00:15, via de batterij € 0,313 / 0,736 = € 0,425.
avond = plan_batterij(dt.datetime(2026, 9, 30, 19, 47, 23), K37, Tariff(),
                      verwachting(huis=1.2, dag=DAG37), klant37(42.0))
slot = re.split(r"(?<=\.)\s+(?=[A-Z])", avond.plan)[-1]
print(f"  19:47 {avond.stand}, bijkopen loont onder {avond.inkoop_tot:.3f} (waarde {avond.waarde:.3f})")
print(f"    {slot}")
netuur = [u for u in avond.uren if u.stand == NETLADEN and u.net_kwh > 0.05
          and u.start < dt.datetime(2026, 10, 1, 7)]
if not netuur:
    controle("geen bijladen vannacht: de zin zegt wat een kWh via de batterij minstens kost",
             "via de batterij minstens € 0,425" in slot and "€ 0,313 om 00:15" in slot, slot)
else:
    controle("bijladen vannacht: de zin zegt hoeveel", "van het net bij" in slot, slot)
controle("de conclusie op de kaart is één zin met het tekort erin", "tekort" in slot, slot)
controle("bijkopen loont onder de waarde in de batterij min het laadverlies",
         avond.inkoop_tot is not None and 0 < avond.inkoop_tot < avond.waarde, f"{avond.inkoop_tot} {avond.waarde}")
vol37 = plan_batterij(dt.datetime(2026, 9, 30, 14, 0), K37, Tariff(), V37, klant37(95.0))
controle("een volle batterij: geen prijs om onder bij te kopen", vol37.inkoop_tot is None, f"{vol37.inkoop_tot}")

print("=== 38. zelf nul: geen restje van het net bij, ook niet onder de bovengrens (v0.103.0) ===")
# De eerste woning op 30-09-2026 om 22:43, uurprijzen tot morgen 23:00. De nacht
# (€ 0,319-0,335) is goedkoper dan het gemiddelde van de bekende uren (€ 0,368),
# dus de som staat 's nachts liever stil dan dat hij het huis uit de batterij
# voedt. Stilstaan kan niet met zelf nul, en v0.102.2 koos het eerstvolgende
# roosterpunt: om 02:00 "laden van het net, 0,11 kWh". v0.102.3 vroeg een stap,
# maar liet op 94-95% nog 0,14-0,20 kWh toe, want dat was "alles wat er nog kan".
P38 = [0.3608, 0.3460, 0.3188, 0.3278, 0.3255, 0.3274, 0.3246, 0.3351, 0.3772, 0.4121,
       0.4158, 0.3925, 0.3698, 0.3297, 0.3247, 0.3227, 0.3222, 0.3230, 0.3598, 0.4116,
       0.4632, 0.4945, 0.4424, 0.4048, 0.3789, 0.3564]
BEGIN38 = dt.datetime(2026, 9, 30, 22)
R38 = [{"start": BEGIN38 + dt.timedelta(hours=i), "end": BEGIN38 + dt.timedelta(hours=i + 1),
        "price": p, "feed_in": None} for i, p in enumerate(P38)]
HUIS38 = {0: 0.21, 1: 0.22, 2: 0.22, 3: 0.23, 4: 0.23, 5: 0.21, 6: 0.23, 7: 0.29, 8: 0.16, 9: -0.04,
          10: 0.25, 11: 0.25, 12: 0.04, 13: 0.02, 14: -0.2, 15: -0.03, 16: -0.16, 17: -0.05, 18: 0.2,
          19: 0.32, 20: 0.31, 21: 0.28, 22: 0.29, 23: 0.27}
W38 = Forecast(solar_kwh={}, house_kwh=HUIS38)
klein38, groot38 = [], []
for soc38 in range(30, 96):
    for nu38 in (dt.datetime(2026, 9, 30, 22, 43, 46), dt.datetime(2026, 10, 1, 0, 30, 40),
                 dt.datetime(2026, 10, 1, 2, 0, 40), dt.datetime(2026, 10, 1, 5, 10, 40)):
        p38 = plan_batterij(nu38, R38, Tariff(), W38,
                            anker(float(soc38), max_charge_w=2500.0, rte=0.748, handelen=True, zelf_nul=True))
        for u in p38.uren:
            if u.stand == NETLADEN:
                (klein38 if u.kwh < 0.38 else groot38).append((soc38, f"{nu38:%H:%M}", f"{u.start:%H:%M}", round(u.kwh, 3)))
print(f"  264 plannen: {len(klein38)} kleine inkopen, {len(groot38)} echte: {groot38[:3]}")
controle("geen inkoop onder één stap van het rooster, op geen enkele accustand", not klein38, f"{klein38[:6]}")
controle("wel een echte inkoop als hij anders leeg is voor de dure avond (30-32%)",
         groot38 and all(s <= 35 for s, *_ in groot38), f"{groot38[:6]}")
# Het restje van een kwartier dat bijna om is mag wel, anders stopt een beurt elk
# kwartier te vroeg; dat meet proef 37 hierboven.

print("=== 39. de batterij helpt de auto op de duurste laaduren (v0.104.1) ===")
# De eigenaar op 30-09-2026 om 23:48, bij het plan van de eerste woning: laden om
# 00:00 (€ 0,319), 02:00 (€ 0,326) en 04:00 (€ 0,325), en de 2,3 kWh uit de batterij
# om 00:00. "Eigenlijk moet hij meehelpen op de duurste momenten, om daar de
# financiële pijn het meest te verzachten."
N39 = dt.datetime(2026, 10, 1, 0, 0)
P39 = [0.319, 0.328, 0.326, 0.327, 0.325, 0.335]
a39 = anker(soc=70.0, auto_boven=50.0, nacht=False, max_discharge_w=2500.0)
eta39 = 0.736 ** 0.5
per_uur39 = 0.2 / eta39 / 14.6 * 100.0
uren39 = [bat.Uur(N39 + dt.timedelta(hours=i), N39 + dt.timedelta(hours=i + 1), bat.NUL, -0.2, 0.0,
                  70.0 - (i + 1) * per_uur39, P39[i]) for i in range(6)]
laden39 = [(N39 + dt.timedelta(hours=u), N39 + dt.timedelta(hours=u + 1), 8.0) for u in (0, 2, 4)]
hulp39 = bat.auto_hulp(uren39, a39, None, laden39)
print(f"  per uur naar de auto: {[round(x, 2) for x in hulp39]}")
# Om 03:00 zit hij op 70% min drie uur huis; alles daarboven tot 50% gaat om 02:00 in de auto.
verwacht39 = (70.0 - 3 * per_uur39 - 50.0) / 100.0 * 14.6 * eta39
controle("het duurste laaduur (02:00, € 0,326) krijgt alles wat er boven de grens is",
         abs(hulp39[2] - verwacht39) < 0.01, f"{hulp39} (verwacht {verwacht39:.3f})")
controle("het goedkoopste laaduur (00:00, € 0,319) krijgt pas iets als er dan nog over is",
         hulp39[0] < hulp39[2], f"{hulp39}")
controle("nooit hulp in een uur waarin de auto niet laadt", hulp39[1] == hulp39[3] == hulp39[5] == 0.0, f"{hulp39}")
# Na alle hulp zakt de batterij in een blok met hulp nooit onder de grens.
cap39, weg39 = 14.6, 0.0
laagst39 = []
for u, h in zip(uren39, hulp39):
    weg39 += h / eta39
    if h > 0:
        laagst39.append(u.soc - weg39 / cap39 * 100.0)
controle("in elk blok met hulp blijft hij boven de grens van 50%", all(s >= 50.0 - 1e-6 for s in laagst39),
         f"{[round(s, 1) for s in laagst39]}")
# Evenveel als vroeger bij gelijke prijzen: dan het vroegste eerst.
vlak39 = [bat.Uur(u.start, u.end, u.stand, u.kwh, u.net_kwh, u.soc, 0.30) for u in uren39]
hulp39v = bat.auto_hulp(vlak39, a39, None, laden39)
controle("bij gelijke prijzen het vroegste laaduur eerst, zoals het was",
         hulp39v[0] > 0 and hulp39v[0] >= hulp39v[2], f"{hulp39v}")

# En de regelaar: om 00:00 laadt de paal volgens zijn plan, maar de hulp is voor 02:00.
b39 = anker(soc=70.0, auto_boven=50.0, nacht=False, max_discharge_w=2500.0)
nu39 = bat.Besluit(bat.NUL, reason="nul", rule="nul", auto_hulp_nu=False, auto_hulp_om=N39 + dt.timedelta(hours=2))
wacht39 = bat.met_paal(nu39, True, b39, None, grens=50.0)
print(f"  00:00, paal laadt: {wacht39.rule}: {wacht39.reason}")
controle("om 00:00 geeft de batterij niets af, en zegt dat de hulp om 02:00 komt",
         wacht39.rule == "paal-laadt" and "om 02:00" in wacht39.reason and not wacht39.grenzen[1], f"{wacht39.reason}")
straks39 = bat.met_paal(bat.Besluit(bat.NUL, reason="nul", rule="nul", auto_hulp_nu=True), True, b39, None, grens=50.0)
controle("om 02:00 helpt hij", straks39.rule == "auto-helpen", f"{straks39.rule}")
buiten39 = bat.met_paal(bat.Besluit(bat.NUL, reason="nul", rule="nul"), True, b39, None, grens=50.0)
controle("laadt de paal buiten zijn plan (Snel, een andere sturing), dan helpt hij zoals altijd",
         buiten39.rule == "auto-helpen", f"{buiten39.rule}")

print("=== 40. geen handelen zonder terugleverprijs (v0.106.2) ===")
# De eerste woning op 03-10-2026, 09:00 tot 12:01: drie keer "handelen. Terugleveren
# brengt nu € 0,000 op". De marktsensor is daar de all-in sensor, dus de opbrengst van
# teruglevering is onbekend en telt als nul. De dag had meer zon dan er in de batterij
# past, dus de som vond zon nu opslaan even veel waard als straks; stilstaan mag niet
# met zelf nul, en bij gelijke kosten won het kleinste gebaar: één stap naar het net.
# Gemeten: 4,57 kWh zon naar het net, de batterij bleef op 21% en gaf er 0,48 kWh aan
# het net bij. Om 12:16 kwam de auto, en die gaat voor.
P40 = [0.30] * 7 + [0.33, 0.30, 0.24, 0.24, 0.23, 0.21, 0.22, 0.27, 0.32, 0.37, 0.40, 0.41, 0.40,
                    0.36, 0.33, 0.31, 0.30]
ZON40 = {8: 0.5, 9: 1.5, 10: 2.5, 11: 3.5, 12: 4.5, 13: 4.5, 14: 4.0, 15: 3.5, 16: 2.5, 17: 1.0}
N40 = DAG + dt.timedelta(hours=9)
for naam40, terug40 in (("onbekend", None), ("bekend, 0,05", 0.05)):
    b40 = anker(21.0, handelen=True, zelf_nul=True)
    p40 = plan_batterij(N40, prijzen(P40, terug=terug40), Tariff(), verwachting(ZON40, huis=0.3, dagen=1), b40)
    ochtend40 = [(f"{u.start:%H:%M}", u.stand, round(u.kwh, 2)) for u in p40.uren if u.start.hour < 12]
    print(f"  terugleverprijs {naam40}: {p40.rule}, ochtend {ochtend40}")
    if terug40 is None:
        controle("zonder terugleverprijs geen handelen, nu niet en niet in het plan",
                 p40.stand != HANDELEN and not any(u.stand == HANDELEN for u in p40.uren), f"{p40.rule} {ochtend40}")
        controle("en de ochtendzon gaat erin: nul op de meter", p40.stand == NUL and all(k > 0 for *_, k in ochtend40),
                 f"{p40.rule} {ochtend40}")
# Met een bekende terugleverprijs mag de som nog altijd handelen: dat is een echte som.
b40h = anker(80.0, handelen=True)
avond40 = plan_batterij(DAG + dt.timedelta(hours=17), prijzen(P40, terug=[p - 0.02 for p in P40]), Tariff(),
                        verwachting({}, huis=0.3, dagen=1), b40h)
controle("met een bekende terugleverprijs kan hij nog handelen", any(u.stand == HANDELEN for u in avond40.uren),
         f"{[(f'{u.start:%H:%M}', u.stand) for u in avond40.uren]}")


print("=== 41. laden is inkopen: opgeleverd telt pas bij ontladen (v0.107.0) ===")
# De eigenaar op 05-10-2026, bij "Opgeleverd € 0,74 in 8 dagen": "dat geld fluctueert
# telkens en klopt niet." Het kasboek rekende laden af op het moment zelf.


def cyclus41(laad_prijs, terug, ontlaad_prijs, uit_zon=False, cap=14.6, rte=0.75, echt_rte=0.75):
    """Een batterij op 10% (de ondergrens): drie uur laden op 2 kW, dan op 1 kW het
    huis voeden tot ze leeg is. De accustand in hele procenten, zoals een Anker hem
    meldt. `rte` is wat de coach weet, `echt_rte` wat de batterij doet. Per minuut:
    (kasboek, opgeleverd, voorraad, fase)."""
    v = bat.Voorraad()
    eta = echt_rte ** 0.5
    inhoud = 0.10 * cap
    rij = []
    for _ in range(180):
        # Uit de zon: 2 kW die anders het net op ging, de meter op nul. Van het
        # net: het huis 300 W, de batterij er 2 kW bovenop.
        net_w = 0.0 if uit_zon else 2300.0
        e = bat.verdiend(net_w, 2000.0, laad_prijs, terug, 60.0)
        inhoud += 2.0 / 60 * eta
        rij.append((e, v.stap(e, 2.0 / 60, round(inhoud / cap * 100), 10.0, cap, rte), v.euro, "laden"))
    while inhoud > 0.10 * cap:
        e = bat.verdiend(0.0, -1000.0, ontlaad_prijs, terug, 60.0)
        inhoud -= 1.0 / 60 / eta
        rij.append((e, v.stap(e, -1.0 / 60, round(inhoud / cap * 100), 10.0, cap, rte), v.euro, "ontladen"))
    return v, rij


v41, rij41 = cyclus41(0.20, 0.05, 0.40)
kasboek41 = sum(r[0] for r in rij41)
echt41 = sum(r[1] for r in rij41)
laden41 = [r for r in rij41 if r[3] == "laden"]
kosten41 = -sum(r[0] for r in laden41)
print(f"  van het net op 0,20, het huis op 0,40: kasboek {kasboek41:.4f}, opgeleverd {echt41:.4f}, "
      f"voorraad na het laden {laden41[-1][2]:.4f}, aan het eind {v41.euro:.6f}, "
      f"kleinste stap {min(r[1] for r in rij41):.6f}")
controle("terwijl ze laadt levert ze niets op en kost ze niets: het bedrag blijft staan",
         all(r[1] == 0.0 for r in laden41), f"{[r[1] for r in laden41 if r[1] != 0.0][:3]}")
controle("wat het laden kostte zit in de voorraad", abs(laden41[-1][2] - kosten41) < 1e-9,
         f"{laden41[-1][2]} {kosten41}")
controle("opgeleverd min wat er nog in zit is altijd precies het kasboek",
         abs(echt41 - v41.euro - kasboek41) < 1e-9, f"{echt41} {v41.euro} {kasboek41}")
controle("leeg is de voorraad (op een cent na) op", abs(v41.euro) < 0.01, f"{v41.euro}")
# Per procent afrekenen gaf hier bij de eerste stap na het laden 2,7 cent onder nul.
controle("met een goedkope nacht en een dure avond stijgt opgeleverd tijdens ontladen alleen",
         all(r[1] >= 0.0 for r in rij41), f"kleinste stap {min(r[1] for r in rij41):.6f}")

# Met salderen: zon erin kost bijna de hele prijs, en met het verlies erbij levert
# opslaan niets op. Dat hoort opgeleverd dan ook te zeggen, en pas bij ontladen.
v41s, rij41s = cyclus41(0.30, 0.25, 0.30, uit_zon=True)
kasboek41s = sum(r[0] for r in rij41s)
echt41s = sum(r[1] for r in rij41s)
print(f"  zon erin met salderen (0,30 en 0,25 terug): kasboek {kasboek41s:.4f}, opgeleverd {echt41s:.4f}, "
      f"aan het eind {v41s.euro:.6f}")
controle("met salderen zegt opgeleverd eerlijk dat opslaan verlies is, maar niet tijdens het laden",
         echt41s < 0 and abs(echt41s - v41s.euro - kasboek41s) < 1e-9
         and all(r[1] == 0.0 for r in rij41s if r[3] == "laden"), f"{echt41s} {kasboek41s}")

# Zonder bekend rendement rekent hij met wat er aan accustand uit gaat: wat leeg is
# blijft leeg, op een paar cent na.
v41z, rij41z = cyclus41(0.20, 0.05, 0.40, rte=None)
print(f"  rendement onbekend: aan het eind {v41z.euro:.6f}, kleinste stap {min(r[1] for r in rij41z):.6f}")
controle("zonder rendement is hij leeg ook (bijna) op", abs(v41z.euro) < 0.05, f"{v41z.euro}")

# Wat er al in zat toen de coach begon te tellen kostte niets: dat telt voluit.
v41o = bat.Voorraad()
controle("wat er al in zat telt voluit", v41o.stap(0.10, -0.5, 60.0, 10.0, 14.6, 0.75) == 0.10, f"{v41o}")
# Zonder accustand of inhoud is er niets om naar te rekenen: dan het kasboek.
controle("zonder accustand telt het kasboek",
         bat.Voorraad(euro=1.0).stap(-0.05, 0.25, None, 10.0, 14.6, 0.75) == -0.05, "")
controle("stilstand verandert niets", bat.Voorraad(euro=1.0).stap(0.0, 0.0, 50.0, 10.0, 14.6, 0.75) == 0.0, "")
# Bij een negatieve prijs kreeg ze geld toe om te laden: een voorraad onder nul.
v41m = bat.Voorraad()
v41m.stap(bat.verdiend(2300.0, 2000.0, -0.05, -0.07, 60.0), 2.0 / 60, 20.0, 10.0, 14.6, 0.75)
controle("laden bij een negatieve prijs geeft een voorraad onder nul", v41m.euro < 0, f"{v41m}")

print("=== 42. een tik voor op het plan: vasthouden tot het blok om is, niet nul op de meter (v0.108.1) ===")
# De klantwoning in de nacht van 05 op 06-10-2026: prijzen per kwartier van € 0,309
# tot € 0,320, een Anker die zelf nul doet, rustig laden van het net. Tikte de
# accustand een procent voor op het plan, dan wilde het plan in de rest van het
# kwartier niets meer, viel het besluit naar nul op de meter en dekte de Anker de
# warmtepomp uit wat hij net gekocht had: 7,68 kWh erin, 2,36 kWh eruit.
DAG42 = dt.datetime(2026, 10, 5)


def nacht42(dag):
    uit = []
    for i in range(96):
        van, u = dag + dt.timedelta(minutes=15 * i), i // 4
        if u >= 22 or u < 6:
            p = 0.309 + 0.002 * ((i * 5) % 7)
        else:
            p = 0.40 if 7 <= u < 10 else (0.45 if 17 <= u < 22 else 0.36)
        uit.append({"start": van, "end": van + dt.timedelta(minutes=15), "price": round(p, 3),
                    "feed_in": round(p - 0.01815, 5)})
    return uit


S42 = sum((nacht42(DAG42 + dt.timedelta(days=d)) for d in range(3)), [])
W42 = verwachting(huis=0.6, dag=DAG42)


def op42(uur, minuut, soc, **kw):
    nu = DAG42.replace(hour=uur, minute=minuut)
    return plan_batterij(nu, S42, Tariff(), W42, anker(
        float(soc), capacity_kwh=14.5, max_discharge_w=3500.0, zelf_nul=True, **kw))


laadt42 = op42(22, 46, 38, overgenomen=True, vorige_stand=NETLADEN,
               vorige_op=DAG42.replace(hour=22, minute=45))
tik42 = op42(22, 46, 39, overgenomen=True, vorige_stand=NETLADEN,
             vorige_op=DAG42.replace(hour=22, minute=45))
vers42 = op42(22, 46, 39)
print(f"  22:46 op 38%: {laadt42.stand} {laadt42.power_w:.0f} W; op 39% {tik42.stand} {tik42.power_w:.0f} W: "
      f"{tik42.reason}")
controle("op 38% laadt hij van het net", laadt42.stand == NETLADEN and laadt42.power_w > 100,
         f"{laadt42.stand} {laadt42.power_w:.0f}")
controle("een tik verder houdt hij vast tot het kwartier om is, in plaats van nul op de meter",
         tik42.stand == NETLADEN and tik42.power_w < 5 and "af tot 23:00" in tik42.reason,
         f"{tik42.stand} {tik42.power_w:.0f} {tik42.reason}")
controle("zonder lopende beurt begint hij daar niet aan", vers42.stand == NUL, f"{vers42.stand}")
# In het volgende kwartier geldt een nieuw besluit: vasthouden hoort bij het blok
# waarin hij laadde, anders kon hij een batterij blok na blok vasthouden.
volgend42 = op42(23, 1, 39, overgenomen=True, vorige_stand=NETLADEN,
                 vorige_op=DAG42.replace(hour=22, minute=59))
volgend42b = op42(23, 1, 39, overgenomen=True, vorige_stand=NETLADEN,
                  vorige_op=DAG42.replace(hour=23, minute=0))
print(f"  23:01 op 39%: na een ronde in het vorige kwartier {volgend42.stand} {volgend42.power_w:.0f} W, "
      f"na een in dit kwartier {volgend42b.stand} {volgend42b.power_w:.0f} W")
controle("na een ronde in het vorige kwartier geen vasthouden",
         not (volgend42.stand == NETLADEN and volgend42.power_w < 5), f"{volgend42.stand} {volgend42.power_w:.0f}")

print()
print("=== 43. handelen aan zonder terugleverprijs: de kaart zegt het (v0.128.2) ===")
# De eerste woning op 18-10-2026: handelen aan, in beide prijsvelden dezelfde
# all-in sensor en salderen uit, dus in alle blokken `feed_in` None. De batterij
# handelde nooit (`_mag_handelen`), en niets op het scherm zei waarom.
NU43 = dt.datetime(2026, 10, 18, 18, 10)
R43 = [{"start": dt.datetime(2026, 10, 18, 17) + dt.timedelta(hours=i),
        "end": dt.datetime(2026, 10, 18, 18) + dt.timedelta(hours=i),
        "price": p, "feed_in": None} for i, p in enumerate([0.409, 0.460, 0.464, 0.448, 0.409])]
met_terug43 = [dict(r, feed_in=round(r["price"] - 0.0242, 4)) for r in R43]
een_terug43 = [dict(r) for r in R43]
een_terug43[3]["feed_in"] = 0.42
verleden43 = [dict(R43[0], feed_in=0.38)] + R43[1:]
kan_niet43 = bat.handelen_kan_niet(anker(95.0, handelen=True), R43, NU43)
controle("handelen aan, geen enkel blok met een terugleverprijs: de kaart zegt het", kan_niet43)
controle("de zin noemt waar het aan ligt en wat er nodig is",
         "terugleverprijs" in bat.HANDELEN_KAN_NIET and "Contract" in bat.HANDELEN_KAN_NIET
         and "salderen" in bat.HANDELEN_KAN_NIET, bat.HANDELEN_KAN_NIET)
controle("handelen uit: niets te zeggen", not bat.handelen_kan_niet(anker(95.0), R43, NU43))
controle("met een terugleverprijs: niets te zeggen",
         not bat.handelen_kan_niet(anker(95.0, handelen=True), met_terug43, NU43))
controle("één komend blok met een terugleverprijs is genoeg",
         not bat.handelen_kan_niet(anker(95.0, handelen=True), een_terug43, NU43))
controle("een blok dat voorbij is telt niet",
         bat.handelen_kan_niet(anker(95.0, handelen=True), verleden43, NU43))
controle("zonder prijzen staat er al een andere reden, dus hier niets",
         not bat.handelen_kan_niet(anker(95.0, handelen=True), [], NU43))
# En het besluit zelf blijft wat het was: nooit naar het net zonder terugleverprijs.
b43 = plan_batterij(NU43, R43, Tariff(), Forecast(solar_kwh={}, house_kwh={h: 0.25 for h in range(24)}),
                    anker(95.0, handelen=True, zelf_nul=True, rte=0.7395))
print(f"  18:10 op 95%: {b43.stand} ({b43.rule}): {b43.reason}")
controle("zonder terugleverprijs handelt hij niet", b43.stand != HANDELEN, b43.stand)

print()
print("=== 44. Opgeleverd opnieuw uitrekenen uit de kwartieren (v0.130.1) ===")
# De eerste woning, 22-09 tot 19-10-2026: teruglevering telde als € 0, dus zon opslaan
# leek gratis. Twee kwartieren: overdag gaat er 2 kW zon in de batterij die anders
# naar het net was gegaan (de meter levert 1 kW terug in plaats van 3), 's avonds
# komt er 1,5 kW uit en neemt het huis 0,5 kW in plaats van 2 van het net.
D44 = dt.datetime(2026, 10, 1, 12, 0)
stappen44 = [
    (D44, 900.0, -1000.0, 2000.0, 50.0),
    (D44.replace(hour=20), 900.0, 500.0, -1500.0, 52.0),
    (D44.replace(hour=21), 900.0, None, -1500.0, 52.0),  # zonder meter: telt niet
]
def prijs44(terug):
    return lambda moment: (0.40, terug)
oud44, _ = bat.herreken(stappen44, prijs44(0.0), bodem=5.0, capacity_kwh=14.6, rte=0.74)
nieuw44, voorraad44 = bat.herreken(stappen44, prijs44(0.30), bodem=5.0, capacity_kwh=14.6, rte=0.74)
dag44 = "2026-10-01"
print(f"  kasboek met teruglevering 0: {oud44[dag44]['earned']:.4f}, met 0,30: {nieuw44[dag44]['earned']:.4f}")
controle("met een terugleverprijs van niets kost zon opslaan niets",
         abs(oud44[dag44]["earned"] - 0.375 * 0.40) < 1e-9, f"{oud44}")
controle("met 0,30 kost hij wat het terugleveren had opgebracht: 0,5 kWh maal 0,30",
         abs(nieuw44[dag44]["earned"] - (0.375 * 0.40 - 0.5 * 0.30)) < 1e-9, f"{nieuw44}")
controle("een kwartier zonder netmeting telt niet", abs(nieuw44[dag44]["earned"] - (0.15 - 0.15)) < 1e-9)
controle("de zon die erin ging telt mee voor Historie", nieuw44[dag44]["solar"] != 0.0, f"{nieuw44}")
controle("en de voorraad komt eruit", voorraad44 is not None)

print()
print("=== 45. Het plan houdt de nacht vast, net als het besluit (v0.133.1) ===")
# De bewoner van de eerste woning op 19-10-2026, met de nachtstrategie aan, een volle
# batterij en de prijzen tot middernacht: "Ondanks dat handelen aan staat, zou ik
# verwachten dat ie om 19u nog zo'n 20 a 30% over heeft om de nacht door te komen."
# Het plan liet de batterij om 23:00 op 5% staan; het besluit van het moment stopte wel
# op tijd. Nagebouwd: de prijzen van die dag ongeveer, terugleveren tegen de
# inkoopprijs (salderen), het huis 0,35 kWh per uur.
D45 = dt.datetime(2026, 10, 20)
P45 = [0.36, 0.35, 0.35, 0.35, 0.36, 0.38, 0.40, 0.44, 0.469, 0.45, 0.42, 0.40, 0.38, 0.38, 0.39, 0.40,
       0.42, 0.45, 0.469, 0.45, 0.44, 0.43, 0.43, 0.43]
L45 = [{"start": D45 + dt.timedelta(hours=i), "end": D45 + dt.timedelta(hours=i + 1), "price": p, "feed_in": p}
       for i, p in enumerate(P45)]
Z45 = {9: 0.6, 10: 1.6, 11: 2.4, 12: 3.0, 13: 3.3, 14: 2.8, 15: 1.8, 16: 1.0, 17: 0.4}
V45 = verwachting(Z45, huis=0.35, dag=D45)
A45 = anker(95.0, rte=0.74, handelen=True, zelf_nul=True)
plan45 = plan_batterij(D45.replace(hour=8, minute=56), L45, Tariff(), V45, A45)
soc45 = {u.start.hour: round(u.soc) for u in plan45.uren}
print(f"  accustand in het plan: 17:00 {soc45.get(17)}%, 19:00 {soc45.get(19)}%, 23:00 {soc45.get(23)}%")
controle("hij handelt op de dure avond", any(u.stand == HANDELEN for u in plan45.uren if 17 <= u.start.hour <= 19),
         f"{[(u.start.hour, u.stand) for u in plan45.uren]}")
nacht45 = bat._nacht_nodig(D45 + dt.timedelta(hours=24), V45, A45)
controle("en om middernacht zit er nog genoeg in tot morgenvroeg",
         plan45.uren[-1].soc / 100 * 14.6 >= 0.05 * 14.6 + nacht45 - 0.15,
         f"{plan45.uren[-1].soc:.0f}% tegen {(0.05 * 14.6 + nacht45) / 14.6 * 100:.0f}% nodig")
controle("na het handelen geen handelen meer: de rest is voor het huis",
         all(u.stand != HANDELEN for u in plan45.uren if u.start.hour >= 20), f"{[(u.start.hour, u.stand) for u in plan45.uren]}")
# Het besluit van het moment en het plan zeggen hetzelfde: op 40% om 18:05 geen handelen meer.
nu45 = plan_batterij(D45.replace(hour=18, minute=5), L45, Tariff(), V45, dataclasses.replace(A45, soc=40.0))
controle("op 40% om 18:05 levert hij niet meer aan het net", nu45.stand != HANDELEN, nu45.stand)
controle("en ook zijn plan niet", all(u.stand != HANDELEN for u in nu45.uren), f"{[(u.start.hour, u.stand) for u in nu45.uren]}")
# Zonder nachtstrategie mag de som alles verkopen, zoals voorheen.
vrij45 = plan_batterij(D45.replace(hour=8, minute=56), L45, Tariff(), V45, dataclasses.replace(A45, nacht=False))
controle("zonder nachtstrategie mag hij verder leeg", vrij45.uren[-1].soc < plan45.uren[-1].soc - 5,
         f"{vrij45.uren[-1].soc:.0f}% tegen {plan45.uren[-1].soc:.0f}%")

print("=== 46. de zomertijd: de nacht van 28-03-2027 heeft een uur minder (v0.140.1) ===")
# De eigenaar op 19-10-2026: "ik wil dat je sowieso rekening houd met de zomer en
# wintertijd. Dat moet allemaal vanzelf gaan." Op 28-03-2027 gaat de klok om 02:00 naar
# 03:00: de nacht tot morgenvroeg heeft een uur minder huisverbruik, en het goedkope blok
# van 01:00 tot 03:00 is maar een uur laden. Op 25-10-2026 is het omgekeerd. De zone van
# het huis zet de coach bij elke ronde (`zet_zone` in planner.py).
from zomertijd import AMSTERDAM, UTC as UTC46  # noqa: E402


def uurlijst46(dag, prijs, terug=0.05, uren=48):
    """Uurprijzen zoals de coach ze uit een prijssensor maakt: per uur in UTC, naar de klok
    van het huis, en het uur dat twee keer komt samen (`_naast_elkaar` in coach.py)."""
    begin = dt.datetime.combine(dag, dt.time(0), AMSTERDAM).astimezone(UTC46)
    uit = {}
    for i in range(uren):
        van = (begin + dt.timedelta(hours=i)).astimezone(AMSTERDAM).replace(tzinfo=None)
        tot = (begin + dt.timedelta(hours=i + 1)).astimezone(AMSTERDAM).replace(tzinfo=None)
        if van in uit:
            uit[van]["end"] = tot
        else:
            uit[van] = {"start": van, "end": tot, "price": prijs(van.hour), "feed_in": terug}
    return sorted(uit.values(), key=lambda r: r["start"])


def prijs46(uur):
    return 0.13 if uur < 5 else 0.25 if uur < 17 else 0.42 if uur < 21 else 0.28


Z46 = dt.date(2027, 3, 28)
W46 = dt.date(2026, 10, 25)
LIJST46 = uurlijst46(Z46, prijs46)
try:
    planner.zet_zone(AMSTERDAM)
    # Tot morgenvroeg (07:00): van 22:00 is dat op 28-03-2027 acht echte uren, op 25-10-2026 tien.
    huis46 = sum(h for _z, h, _d in bat._nacht_uren(dt.datetime(2027, 3, 27, 22, 0), verwachting(huis=0.3, dag=dt.datetime(2027, 3, 27))))
    huis46w = sum(h for _z, h, _d in bat._nacht_uren(dt.datetime(2026, 10, 24, 22, 0), verwachting(huis=0.3, dag=dt.datetime(2026, 10, 24))))
    print(f"  het huis vraagt tot morgenvroeg {huis46:.2f} kWh (zomertijd) en {huis46w:.2f} kWh (wintertijd)")
    controle("de nacht van de zomertijd heeft acht uur huisverbruik", abs(huis46 - 8 * 0.3) < 1e-9, f"{huis46}")
    controle("die van de wintertijd tien", abs(huis46w - 10 * 0.3) < 1e-9, f"{huis46w}")
    # De som over de tijd: het blok van 01:00 tot 03:00 is een uur.
    nu46 = dt.datetime(2027, 3, 28, 0, 1)
    V46 = verwachting(huis=0.5, dag=dt.datetime(2027, 3, 28))
    som46 = bat._waarde_vooruit(nu46, [r for r in LIJST46 if r["end"] > nu46], V46, anker(soc=10.0))
    deel46 = next(d for r, d in zip(som46.blokken, som46.delen) if r["start"] == dt.datetime(2027, 3, 28, 1))
    controle("in de som duurt het blok van 01:00 tot 03:00 een uur", abs(deel46 - 1.0) < 1e-9, f"{deel46}")
    # En van het net laden smeert hij uit over de echte uren van de goedkope nacht.
    b46 = plan_batterij(nu46, LIJST46, Tariff(), V46, anker(soc=10.0))
    geladen46 = sum(u.net_kwh for u in b46.uren if u.start < dt.datetime(2027, 3, 28, 5))
    print(f"  00:01  {b46.stand} op {b46.power_w:.0f} W, {geladen46:.2f} kWh van het net voor 05:00")
    controle("in de goedkope nacht laadt hij van het net", b46.stand == NETLADEN, b46.stand)
    controle("uitgesmeerd over vier echte uren, niet over vijf op de klok",
             abs(b46.power_w - geladen46 / (4 - 1 / 60) * 1000.0) < 25.0,
             f"{b46.power_w:.0f} W tegen {geladen46:.2f} kWh")
    controle("en geen blok in het plan krijgt meer dan de batterij in zijn echte uren kan",
             all(u.kwh <= 3.5 * planner.echte_uren(u.start, u.end) + 1e-6 for u in b46.uren), "")
    # De wintertijd: het blok van 02:00 tot 03:00 is twee uur.
    LIJST46W = uurlijst46(W46, prijs46)
    nu46w = dt.datetime(2026, 10, 25, 0, 1)
    som46w = bat._waarde_vooruit(nu46w, [r for r in LIJST46W if r["end"] > nu46w], verwachting(huis=0.5, dag=dt.datetime(2026, 10, 25)), anker(soc=10.0))
    deel46w = next(d for r, d in zip(som46w.blokken, som46w.delen) if r["start"] == dt.datetime(2026, 10, 25, 2))
    controle("bij de wintertijd duurt het blok van 02:00 tot 03:00 twee uur", abs(deel46w - 2.0) < 1e-9, f"{deel46w}")
finally:
    planner.zet_zone(None)

# Zonder zone, zoals elke proef hierboven: alles op de klok, zoals het altijd was.
huis46n = sum(h for _z, h, _d in bat._nacht_uren(dt.datetime(2027, 3, 27, 22, 0), verwachting(huis=0.3, dag=dt.datetime(2027, 3, 27))))
controle("zonder zone telt de nacht negen uur op de klok, zoals voorheen", abs(huis46n - 9 * 0.3) < 1e-9, f"{huis46n}")

print()
print("=== 47. handelen in twee: laden van het net en ontladen naar het net, met een grens (v0.141.0) ===")
# De eigenaar op 19-10-2026: "Batterij mag laden van het net tijdens lage tarieven / Batterij
# mag ontladen naar het net tijdens hoge tarieven." En op 21-10-2026 per richting "laat coach
# de beste strategie bepalen, of" alleen onder of boven een prijs, met de all-in prijs.
UUR47 = [0.12, 0.12, 0.13, 0.14, 0.18, 0.22, 0.30, 0.38, 0.40, 0.33, 0.28, 0.25,
         0.22, 0.21, 0.22, 0.26, 0.30, 0.42, 0.45, 0.44, 0.36, 0.30, 0.25, 0.20]
L47 = prijzen(UUR47 + UUR47, terug=[p - 0.02 for p in UUR47 + UUR47])
V47 = verwachting(huis=0.4)
NU47 = DAG.replace(hour=0, minute=5)


def plan47(**kw):
    return plan_batterij(NU47, L47, Tariff(), V47, anker(20.0, **kw))


vrij47 = plan47()
geladen47 = [(u.start.hour, u.price) for u in vrij47.uren if u.stand == NETLADEN]
print(f"  de coach bepaalt: {vrij47.stand}, van het net in {geladen47}")
controle("zonder grens laadt hij 's nachts van het net, zoals altijd",
         vrij47.stand == NETLADEN and geladen47, f"{vrij47.stand} {geladen47}")
uit47 = plan47(net_laden=False)
controle("laden van het net uit: nergens in het plan van het net",
         uit47.stand != NETLADEN and not [u for u in uit47.uren if u.stand == NETLADEN],
         f"{uit47.stand} {[(u.start.hour, u.stand) for u in uit47.uren if u.stand == NETLADEN]}")
onder47 = plan47(net_laden_onder=0.13)
geladen47b = [(u.start.hour, u.price) for u in onder47.uren if u.stand == NETLADEN]
print(f"  alleen onder 0,13: {onder47.stand}, van het net in {geladen47b}")
controle("met een grens van 0,13 alleen in de uren daaronder",
         geladen47b and all(p < 0.13 for _, p in geladen47b), f"{geladen47b}")
neg47 = plan_batterij(NU47, prijzen([-0.05] * 24 + UUR47, terug=-0.07), Tariff(), V47, anker(20.0, net_laden=False))
controle("ook bij een negatieve prijs niet, als het uit staat", neg47.stand != "max-laden", neg47.stand)
# Ontladen naar het net: alleen boven de grens, en zonder grens bepaalt de som het.
vol47 = dict(handelen=True, nacht=False)
h47 = plan_batterij(DAG.replace(hour=17, minute=5), L47, Tariff(), V47, anker(90.0, **vol47))
h47b = plan_batterij(DAG.replace(hour=17, minute=5), L47, Tariff(), V47, anker(90.0, handelen_boven=0.43, **vol47))
weg47 = [(u.start.hour, u.price) for u in h47b.uren if u.stand == HANDELEN]
print(f"  17:05 op 90%: zonder grens {h47.stand}; boven 0,43 {h47b.stand}, naar het net in {weg47}")
controle("zonder grens handelt hij op de dure avond", h47.stand == HANDELEN, h47.stand)
controle("met een grens van 0,43 niet om 17:00 (0,42), wel in de uren erboven",
         h47b.stand != HANDELEN and weg47 and all(p > 0.43 for _, p in weg47), f"{h47b.stand} {weg47}")

print("=== 48. het rendement per vermogen: leren en rekenen (v0.142.0) ===")
# De eigenaar op 19-10-2026: "RTE is dramatisch op lage vermogens.. NoM in de nacht
# niet bevorderlijk dus." Gemeten in de eerste woning: ontladen een vast verlies van
# ongeveer 68 W, dan 81% bij 300 W en 96% bij 2 kW; laden 92% boven 1,2 kW.
Rendementmeter, rendement_uit_stappen, Rendement = bat.Rendementmeter, bat.rendement_uit_stappen, bat.Rendement


def accu48(meter, soc, stappen, ac_w, cap=14.3, elke=5, start=None, tegen_w=0.0):
    """Een batterij met 68 W vast verlies bij ontladen en 92% bij laden, de accustand in hele procenten."""
    t = start or dt.datetime(2026, 10, 20, 0, 0)
    echt = soc + 0.5
    doel = soc + stappen if ac_w > 0 else soc - stappen
    n = 0
    while (echt < doel + 0.5) if ac_w > 0 else (echt > doel + 0.5):
        cel_kw = ac_w / 1000 * 0.92 if ac_w > 0 else -(abs(ac_w) / 1000 + 0.068)
        echt += cel_kw * elke / 3600 / cap * 100
        w = ac_w + (tegen_w if n % 10 == 0 else 0.0)
        meter.tik(t, float(int(echt)), w, cap)
        t += dt.timedelta(seconds=elke)
        n += 1
    return t, int(echt)


m48 = Rendementmeter()
t48, s48 = accu48(m48, 20, 50, 2500.0)
t48, s48 = accu48(m48, s48, 25, -500.0, start=t48)
t48, s48 = accu48(m48, s48, 20, -2000.0, start=t48)
som48 = m48.sommen
print(f"  stappen: laden {sum(b['n'] for b in som48['in'].values())}, ontladen "
      f"{ {k: b['n'] for k, b in som48['uit'].items()} }")
r48 = rendement_uit_stappen(som48)
print(f"  laden {r48.laden}, ontladen {[(round(k, 3), round(e, 3)) for k, e in r48.ontladen]}")
controle("laden: 92% geleerd", r48 is not None and abs(r48.gem_laden - 0.92) < 0.01, f"{r48}")
controle("ontladen op 500 W: 500 / 568 = 88%",
         abs(r48.ontladen[0][1] - 0.5 / 0.568) < 0.012, f"{r48.ontladen}")
controle("ontladen op 2 kW: 2000 / 2068 = 96,7%",
         abs(r48.ontladen[-1][1] - 2.0 / 2.068) < 0.012, f"{r48.ontladen}")
controle("bij een lager vermogen een lager rendement, en ertussen recht getrokken",
         r48.ontladen[0][1] < bat._op_vermogen(r48.ontladen, 1.0) < r48.ontladen[-1][1], "")
controle("buiten de metingen het dichtstbijzijnde punt, niets aangenomen",
         bat._op_vermogen(r48.ontladen, 0.1) == r48.ontladen[0][1]
         and bat._op_vermogen(r48.ontladen, 5.0) == r48.ontladen[-1][1], "")
# Wat niet telt: boven 90%, een sprong, een omkering, tegenstroom, een gat.
m48b = Rendementmeter()
accu48(m48b, 88, 7, 2500.0)
controle("boven de 90% telt geen stap", not m48b.sommen or sum(b["n"] for b in m48b.sommen["in"].values()) <= 1,
         f"{m48b.sommen}")
m48c = Rendementmeter()
nu48 = dt.datetime(2026, 10, 20, 3, 0)
for i, soc in enumerate([50, 51, 52, 54, 55, 54, 55, 56]):
    m48c.tik(nu48 + dt.timedelta(seconds=60 * i), float(soc), 2500.0, 14.3)
controle("een sprong van twee procent en een omkering tellen niet", not m48c.sommen, f"{m48c.sommen}")
m48d = Rendementmeter()
accu48(m48d, 40, 20, -1000.0, tegen_w=1500.0)
controle("te veel de andere kant op is geen stap", not m48d.sommen, f"{m48d.sommen}")
m48e = Rendementmeter()
m48e.tik(nu48, 50.0, -1000.0, 14.3)
m48e.tik(nu48 + dt.timedelta(seconds=30), 49.0, -1000.0, 14.3)
m48e.tik(nu48 + dt.timedelta(minutes=10), 48.0, -1000.0, 14.3)
controle("een gat van tien minuten zonder metingen telt niet", not m48e.sommen, f"{m48e.sommen}")
weinig48 = Rendementmeter()
accu48(weinig48, 20, 50, 2500.0)
controle("met alleen laden gemeten rekent hij er nog niet mee", rendement_uit_stappen(weinig48.sommen) is None, "")

# Rekenen: van cellen naar wisselstroom en terug komt op hetzelfde uit.
b48 = anker(soc=60.0, rendement=r48, rte=r48.rte)
for ac48 in (0.2, 0.6, 2.4):
    cel = bat._cel_uit(b48, ac48, 1.0)
    controle(f"ontladen {ac48} kWh in een uur: heen en terug gelijk", abs(-bat._ac(b48, 10.0, 10.0 - cel, 1.0) - ac48) < 1e-4,
             f"{bat._ac(b48, 10.0, 10.0 - cel, 1.0)}")
# De som, zonder handelen: 's nachts 0,30, morgenvroeg 0,25. Met de helft van het
# verlies heen en terug voedt hij 's nachts het huis; met het rendement per
# vermogen ziet hij dat 300 W uit de batterij maar 70% oplevert, en bewaart hij het.
sterk48 = Rendement([(2.3, 0.92)], [(0.15, 0.70), (0.6, 0.88), (2.0, 0.96)], 0.92, 0.90)
nacht48 = [0.25] * 20 + [0.30] * 11 + [0.25] * 17
lijst48 = prijzen(nacht48, terug=0.02)
nu48b = DAG.replace(hour=21, minute=5)
vast48 = plan_batterij(nu48b, lijst48, Tariff(), verwachting(huis=0.3), anker(70.0, nacht=False, rte=0.828))
per48 = plan_batterij(nu48b, lijst48, Tariff(), verwachting(huis=0.3),
                      anker(70.0, nacht=False, rte=sterk48.rte, rendement=sterk48))
print(f"  21:05, 's nachts 0,30 en morgen 0,25: vast rendement {vast48.stand}, per vermogen {per48.stand}")
controle("vast rendement: 's nachts het huis voeden", vast48.stand in (NUL, ONTLADEN), vast48.stand)
controle("per vermogen: 300 W uit de batterij loont dan niet", per48.stand not in (NUL, ONTLADEN, HANDELEN), per48.stand)
# De nachtbalans rekent met het ontladen op het vermogen van het huis.
nb48 = bat.balans_kwh(DAG.replace(hour=20), verwachting({}, huis=0.3), anker(50.0, rte=sterk48.rte, rendement=sterk48))
nbv48 = bat.balans_kwh(DAG.replace(hour=20), verwachting({}, huis=0.3), anker(50.0, rte=sterk48.rte))
print(f"  nachtbalans op 300 W: per vermogen {nb48:.2f}, met de helft heen en terug {nbv48:.2f}")
controle("'s nachts op 300 W houdt hij minder over dan het gemiddelde zegt", nb48 < nbv48 - 0.2, f"{nb48} {nbv48}")

print("=== 49. de afschrijving hoort bij de minimale spread (v0.146.0) ===")
# De eigenaar op 22-10-2026: "Nu rekent coach alleen met het rendementsverlies. Maar ook
# afschrijving moet meegerekend worden om de minimale prijsspread te bepalen." Zijn voorbeeld
# uit een klantwoning: 's nachts laden op 0,290 tot 0,296, 's ochtends ontladen op 0,353 tot
# 0,379, met salderen (teruglevering tegen dezelfde prijs).
UUR49 = [0.296, 0.294, 0.292, 0.290, 0.291, 0.293, 0.330, 0.353, 0.379, 0.365, 0.340, 0.320,
         0.300, 0.300, 0.305, 0.310, 0.320, 0.330, 0.330, 0.325, 0.320, 0.310, 0.300, 0.298]
L49 = prijzen(UUR49 + UUR49, terug=UUR49 + UUR49)
NU49 = DAG.replace(hour=0, minute=5)


def plan49(**kw):
    return plan_batterij(NU49, L49, Tariff(), verwachting(huis=0.3), anker(20.0, rte=0.85, handelen=True, nacht=False, **kw))


zonder49 = plan49()
met49 = plan49(slijtage=0.04)
net49 = lambda p: [(u.start.hour, u.price) for u in p.uren if u.stand == NETLADEN]  # noqa: E731
print(f"  zonder afschrijving: {zonder49.stand}, van het net in {net49(zonder49)}")
print(f"  met 4 cent per kWh: {met49.stand}, van het net in {net49(met49)}")
controle("zonder afschrijving laadt hij 's nachts van het net: 0,296 / 0,85 = 0,348 < 0,379",
         bool(net49(zonder49)), f"{zonder49.stand} {net49(zonder49)}")
controle("met 4 cent per kWh niet meer: 0,348 + 0,04 boven 0,379",
         met49.stand != NETLADEN and not net49(met49), f"{met49.stand} {net49(met49)}")
# Een spread die het wel dekt: 's ochtends 0,45, dan laadt hij ook met afschrijving.
L49b = prijzen([p if i not in (7, 8, 9) else 0.45 for i, p in enumerate(UUR49)] * 2,
               terug=[p if i not in (7, 8, 9) else 0.45 for i, p in enumerate(UUR49)] * 2)
ruim49 = plan_batterij(NU49, L49b, Tariff(), verwachting(huis=0.3),
                       anker(20.0, rte=0.85, handelen=True, nacht=False, slijtage=0.04))
controle("bij een ochtend van 0,45 dekt de spread het wel, en laadt hij toch",
         bool(net49(ruim49)), f"{ruim49.stand} {net49(ruim49)}")

print("=== 50. Growatt: het plan als laadschema, drie vakken per dag (v0.150.0) ===")
# De eigenaar op 22-10-2026: de Growatt sturen, voor elke klant met een Growatt. Een SPH
# neemt een laadschema: drie vakken, een vermogen in procent, een accustand om te stoppen.
# Zoals in de klantwoning: bi-horário, vazio van 22:00 tot 08:00 op 0,166 en
# daarbuiten 0,272, geen teruglevering; 12,5 kWh per 100%, de vloer op 15%, 1,6 kW bij 20%.
VAZIO50 = [0.166] * 8 + [0.272] * 14 + [0.166] * 2
L50 = prijzen(VAZIO50 * 2, terug=0.0)
NU50 = DAG.replace(hour=21, minute=30)


def growatt50(soc=16.0, **kw):
    basis = dict(soc=soc, capacity_kwh=12.5, max_charge_w=7800.0, max_discharge_w=7800.0,
                 soc_min=15.0, soc_max=100.0, rte=0.90, zelf_nul=True)
    basis.update(kw)
    return Batterij(**basis)


b50 = growatt50()
p50 = plan_batterij(NU50, L50, Tariff(), verwachting(huis=0.7), b50)
s50 = bat.growatt_schema(p50.uren, NU50, b50)
net50 = [(u.start.strftime("%d %H:%M"), round(u.net_kwh, 2), round(u.soc)) for u in p50.uren if u.net_kwh > 0.05]
print(f"  plan van het net: {net50}")
print(f"  schema: net {s50.net}, {s50.vermogen_pct}%, tot {s50.stop_soc}%, vakken {s50.vakken}, {s50.kwh:.1f} kWh")
controle("zonder zon laadt hij in de nacht van het net voor de dure dag", s50.net and s50.kwh > 3.0,
         f"{s50}")
controle("de vakken liggen in vazio en het schema telt hooguit drie",
         0 < len(s50.vakken) <= 3 and all(a >= "22:00" or b <= "08:00" for a, b in s50.vakken), f"{s50.vakken}")
# De eigenaar op 23-10-2026: "de laatste 2 uur van de goedkope uren de accu vol laden"
# (v0.152.0). Het vak eindigt met vazio, duurt minstens twee uur, en zo lang dat hij op
# hooguit de helft van zijn vermogen laadt: ruim 11 kWh op 3,9 kW is drie uur.
uren50 = -(-s50.kwh / 3.9 * 4 // 1) / 4
controle("aan het eind van vazio: tot 08:00, en zo laat als het op de helft van zijn vermogen kan",
         s50.vakken == [((dt.datetime(2026, 9, 22, 8) - dt.timedelta(hours=uren50)).strftime("%H:%M"), "08:00")],
         f"{s50.vakken} tegen {uren50} uur")
watt50 = s50.kwh / uren50 * 1000
controle("het vermogen is wat erin moet gedeeld door die uren, naar boven afgerond op een procent, hooguit de helft",
         s50.vermogen_pct >= watt50 / 7800 * 100 > s50.vermogen_pct - 1 and s50.vermogen_pct <= 50,
         f"{s50.vermogen_pct}% tegen {watt50:.0f} W")
weinig50 = bat.growatt_schema(p50.uren, NU50, b50, bijstel_kwh=2.0 - s50.kwh)
controle("2 kWh: toch twee uur, van 06:00 tot 08:00", weinig50.vakken == [("06:00", "08:00")], f"{weinig50}")
# Te weinig tijd voor de helft: dan begint het vak waar het goedkope stuk begint, over middernacht in tweeën.
traag50 = bat.growatt_schema(p50.uren, NU50, growatt50(max_charge_w=1500.0))
controle("bij 1,5 kW past het niet aan het eind: over het hele stuk, 22:00 tot 23:59 en 00:00 tot 08:00",
         traag50.vakken == [("22:00", "23:59"), ("00:00", "08:00")], f"{traag50}")
# Binnen het vak, met minder dan het vak nog vraagt: het vermogen over wat er over is.
binnen50 = bat.growatt_schema(p50.uren, DAG.replace(day=22, hour=7, minute=0), b50)
controle("om 07:00 in het vak: nog hooguit een uur, dus een hoger vermogen of geen schema",
         not binnen50.net or binnen50.vakken[-1][1] == "08:00", f"{binnen50}")
laatste50 = max((u for u in p50.uren if u.net_kwh > 0.05), key=lambda u: u.end)
controle("hij stopt waar het plan aan het eind van het laatste vak zit",
         s50.stop_soc == int(-(-laatste50.soc // 1)), f"{s50.stop_soc} tegen {laatste50.soc:.1f}")
velden50 = s50.velden()
controle("de velden voor write_ac_charge_times: mains aan, drie vakken, de lege uit",
         velden50["mains_enabled"] is True and velden50["charge_power"] == s50.vermogen_pct
         and sum(velden50[f"period_{i}_enabled"] for i in (1, 2, 3)) == len(s50.vakken), f"{velden50}")

# Zonder dal- en piektarief valt er niets te halen: geen laden van het net, mains uit.
vlak50 = plan_batterij(NU50, prijzen([0.25] * 48, terug=0.0), Tariff(), verwachting(huis=0.7), growatt50())
s50b = bat.growatt_schema(vlak50.uren, NU50, growatt50())
controle("bij één prijs: geen vakken en mains uit", not s50b.net and s50b.velden()["mains_enabled"] is False
         and not any(s50b.velden()[f"period_{i}_enabled"] for i in (1, 2, 3)), f"{s50b}")
controle("zonder laadvermogen of inhoud geen schema", not bat.growatt_schema(p50.uren, NU50, growatt50(max_charge_w=0.0)).net)

# Wat de Growatt teruggeeft: de stopgrens telt niet mee (twee velden in de omvormer, de
# klantwoning 22-10-2026), het vermogen en de vakken wel.
gelezen50 = {"charge_power": s50.vermogen_pct, "charge_stop_soc": 100, "mains_enabled": True,
             "periods": [{"period_id": i + 1, "start_time": a, "end_time": b, "enabled": True}
                         for i, (a, b) in enumerate(s50.vakken)]}
controle("teruggelezen met een andere stopgrens is toch gelijk", s50.gelijk(gelezen50))
controle("met mains uit niet", not s50.gelijk({**gelezen50, "mains_enabled": False}))
controle("met een ander vermogen niet", not s50.gelijk({**gelezen50, "charge_power": s50.vermogen_pct + 1}))

# Niet elke minuut schrijven: een procent verschil is geen nieuw schema, een vak dat al loopt
# en korter wordt ook niet; ander vak of uit wel.
eerst50 = bat.GrowattSchema(net=True, vermogen_pct=20, stop_soc=60, vakken=[("22:00", "23:59"), ("00:00", "05:00")])
controle("een procent meer vermogen of stopgrens: niet opnieuw schrijven",
         not dataclasses.replace(eerst50, vermogen_pct=21, stop_soc=61).wijkt_af(eerst50))
controle("na middernacht valt het eerste vak weg en begint het tweede later: niet opnieuw",
         not dataclasses.replace(eerst50, vakken=[("01:00", "05:00")]).wijkt_af(eerst50))
controle("een ander eind wel", dataclasses.replace(eerst50, vakken=[("00:00", "06:00")]).wijkt_af(eerst50))
controle("uit wel", bat.GrowattSchema().wijkt_af(eerst50))
controle("vijf procent vermogen wel", dataclasses.replace(eerst50, vermogen_pct=25).wijkt_af(eerst50))

# Op de stopgrens zet de coach het zelf uit, gemeten en niet teruggelezen.
controle("op 60% bij een stop op 60: vol", bat.growatt_vol(eerst50, 60.0))
controle("op 58%: nog niet", not bat.growatt_vol(eerst50, 58.0))
controle("tot vol niet: dan stopt hij zelf en staat hij stil tot het vak om is",
         not bat.growatt_vol(dataclasses.replace(eerst50, stop_soc=100), 100.0))

# Zelf leren: de inhoud uit de eigen teller per procent, het vermogen uit wat hij haalt.
controle("de inhoud pas na drie stukken", bat.growatt_inhoud([0.125, 0.12]) is None
         and abs(bat.growatt_inhoud([0.125, 0.12, 0.13]) - 12.5) < 1e-9)
controle("een stuk waarin de teller sprong telt niet zwaar: de mediaan",
         abs(bat.growatt_inhoud([0.12, 0.125, 0.9, 0.124]) - 12.5) < 1e-9)
controle("het laadvermogen pas na zes metingen, en dan de mediaan: 1570 W bij 20% is 7850 W",
         bat.growatt_max_w([7850] * 5) is None and bat.growatt_max_w([7850, 7800, 7900, 7850, 7700, 7850]) == 7850)

print("=== 51. de zon zonder paneelgegevens, en het schema bijstellen na elke nacht (v0.151.0) ===")
# De eigenaar op 22-10-2026: "Zon ZONDER paneelgegevens. Leer per uur van de dag een
# helderhemel-omhullende uit de eigen opwek, meegeschoven met de zonnestand, en schaal die met
# de weersverwachting die HA al heeft." Een dak in Nederland (52 N, 5 O), in UTC.
zon = sys.modules["domotiapp_coach.zon"] if "domotiapp_coach.zon" in sys.modules else __import__(
    "domotiapp_coach.zon", fromlist=["zon"])
import math as _m
UTC = dt.timezone.utc
hoog = lambda t: _m.degrees(_m.asin(zon.zonhoogte(t, 52.0, 5.0)))  # noqa: E731
print(f"  zonnestand 23-10 11:30 UTC {hoog(dt.datetime(2026, 10, 23, 11, 30, tzinfo=UTC)):.1f} graden, "
      f"21-06 11:40 {hoog(dt.datetime(2026, 6, 21, 11, 40, tzinfo=UTC)):.1f}")
controle("de zon staat eind oktober 's middags rond 26 graden en in juni rond 61",
         abs(hoog(dt.datetime(2026, 10, 23, 11, 30, tzinfo=UTC)) - 26.2) < 1.0
         and abs(hoog(dt.datetime(2026, 6, 21, 11, 40, tzinfo=UTC)) - 61.5) < 1.0)


def dak51(dag, factor):
    """Een dak van 4 kWp: wat het per uur deed, evenredig met de zonnestand, maal het weer."""
    uit = {}
    for h in range(24):
        t = dt.datetime(2026, 10, dag, h, tzinfo=UTC)
        s = zon.zonhoogte(t + dt.timedelta(minutes=30), 52.0, 5.0)
        uit[t] = round(max(0.0, 4.0 * s) * factor(dag, h), 3)
    return uit


# Twee weken: elke derde dag helder, de rest half bewolkt (de helft).
opwek51 = {}
for d in range(8, 22):
    opwek51.update(dak51(d, lambda dag, h: 1.0 if dag % 3 == 0 else 0.5))
uren51 = [dt.datetime(2026, 10, 22, h, tzinfo=UTC) for h in range(24)]
helder51 = zon.heldere_kromme(opwek51, uren51, 52.0, 5.0)
echt51 = dak51(22, lambda dag, h: 1.0)
print(f"  heldere dag 22-10 om 12 UTC: {helder51[uren51[12]]:.3f} kWh, het dak helder {echt51[uren51[12]]:.3f}")
controle("de heldere dag is de hoogste opwek van de laatste weken, meegeschoven met de zonnestand",
         all(abs(helder51[u] - echt51[u]) < 0.01 for u in uren51 if echt51[u] > 0.2), "")
controle("'s nachts nul", helder51[uren51[2]] == 0.0)

# Het weer: helder (10%) gaf de hele dag, half bewolkt (60%) de helft.
bewolking51 = {u: (10.0 if u.day % 3 == 0 else 60.0) for u in opwek51}
nu51 = dt.datetime(2026, 10, 22, 0, tzinfo=UTC)
straks51 = {u: 60.0 for u in uren51}
v51 = zon.zon_uit_opwek(opwek51, uren51, 52.0, 5.0, bewolking51, straks51, nu51)
print(f"  morgen 60% bewolkt: {sum(v51.values()):.2f} kWh, helder {sum(echt51.values()):.2f}")
controle("bij 60% bewolking verwacht hij wat het dak bij 60% deed: de helft",
         abs(sum(v51.values()) - sum(echt51.values()) / 2) < 0.2, f"{sum(v51.values()):.2f}")
v51b = zon.zon_uit_opwek(opwek51, uren51, 52.0, 5.0, bewolking51, {u: 5.0 for u in uren51}, nu51)
controle("en bij helder weer de hele heldere dag", abs(sum(v51b.values()) - sum(echt51.values())) < 0.2,
         f"{sum(v51b.values()):.2f}")
# Zonder weerbericht: zoals de laatste dagen ging (19, 20 en 21 oktober: 0,5, 0,5 en 1,0).
v51c = zon.zon_uit_opwek(opwek51, uren51, 52.0, 5.0, None, None, nu51)
controle("zonder weer: de mediaan van de laatste drie dagen, de helft",
         abs(sum(v51c.values()) - sum(echt51.values()) / 2) < 0.2, f"{sum(v51c.values()):.2f}")
controle("zonder eigen opwek: niets", zon.zon_uit_opwek({}, uren51, 52.0, 5.0) == {})

# Na elke nacht: te veel van het net als de zon de volgende dag naar het net ging terwijl hij
# vol zat (nooit meer dan er van het net in ging), te weinig als hij op zijn vloer stond.
controle("een nacht met 6 kWh van het net en 2 kWh zon naar het net bij een volle batterij: 2 te veel",
         bat.growatt_nacht(2.0, 0.0, 6.0) == -2.0)
controle("meer zon naar het net dan er van het net in ging telt tot wat er in ging",
         bat.growatt_nacht(9.0, 0.0, 6.0) == -6.0)
controle("1,5 kWh van het net op de vloer: 1,5 te weinig", bat.growatt_nacht(0.0, 1.5, 6.0) == 1.5)
controle("bijstellen pas na drie nachten", bat.growatt_bijstelling([-2.0, -2.0], 12.5) == 0.0
         and bat.growatt_bijstelling([-2.0, -2.0, 5.0], 12.5) == -2.0)
controle("nooit meer dan de inhoud", bat.growatt_bijstelling([20.0] * 3, 12.5) == 12.5)
s51 = bat.growatt_schema(p50.uren, NU50, b50)
s51b = bat.growatt_schema(p50.uren, NU50, b50, bijstel_kwh=-2.0)
print(f"  zonder bijstelling {s51.kwh:.1f} kWh tot {s51.stop_soc}%, met -2 kWh {s51b.kwh:.1f} kWh tot {s51b.stop_soc}%")
controle("2 kWh minder: een lagere stopgrens, en een vak dat even laat of later begint en ook om 08:00 eindigt",
         abs(s51b.kwh - (s51.kwh - 2.0)) < 0.01 and s51b.stop_soc < s51.stop_soc
         and s51b.vermogen_pct <= 50 and s51b.vakken[-1][1] == "08:00"
         and s51b.vakken[0][0] >= s51.vakken[0][0] and not s51b.wijkt_af(s51, alleen_vakken=True), f"{s51} {s51b}")
controle("zoveel minder dat er niets overblijft: geen schema",
         not bat.growatt_schema(p50.uren, NU50, b50, bijstel_kwh=-50.0).net)

print("=== 52. Growatt: het vak aan het eind van vazio, ook in de nacht van de wintertijd (v0.152.0) ===")
# Op 25-10-2026 komt 02:00 twee keer. Zeven echte uren voor 08:00 is dan 02:00 op de klok, niet 01:00.
try:
    planner.zet_zone(AMSTERDAM)
    NU52 = dt.datetime(2026, 10, 24, 21, 30)
    L52 = prijzen(VAZIO50 * 2, terug=0.0, dag=dt.datetime(2026, 10, 24))
    b52 = growatt50(max_charge_w=3000.0)
    p52 = plan_batterij(NU52, L52, Tariff(), verwachting(huis=0.7, dag=dt.datetime(2026, 10, 24)), b52)
    s52 = bat.growatt_schema(p52.uren, NU52, b52)
    duur52 = dt.timedelta(minutes=-(-s52.kwh / 1.5 * 4 // 1) * 15)
    acht52 = dt.datetime(2026, 10, 25, 8, 0)
    echt52 = planner.echt_verder(acht52, -duur52)
    print(f"  {s52.kwh:.1f} kWh, {duur52}, schema {s52.vakken}; op de klok zou het {(acht52 - duur52):%H:%M} zijn")
    controle("het vak begint de echte duur voor 08:00", s52.vakken == [(echt52.strftime("%H:%M"), "08:00")],
             f"{s52.vakken} tegen {echt52}")
    controle("en dat is een uur later dan op de klok", echt52 - (acht52 - duur52) == dt.timedelta(hours=1), f"{echt52}")
finally:
    planner.zet_zone(None)

print()
print(f"{GOED} goed, {FOUT} fout")
sys.exit(1 if FOUT else 0)
