"""Proeven op het denkwerk van de thuisbatterij, zonder Home Assistant.

De strategie (`plan_batterij`), de regelaar (`Regelaar`), wat de batterij
verdient en het rendement uit de tellers. De getallen komen waar het kan uit
de eerste woning, gemeten op 21-09-2026.
"""

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
          sensor_na=0, sensor_aanloop=False, sensor_echo=0, geen_sensor=False, volgt_niet=False):
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
    regelaar = Regelaar()
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

print("24. terugverdiend")
dagen24 = {(DAG - dt.timedelta(days=i)).date().isoformat(): 1.50 for i in range(30)}
t24 = bat.terugverdiend(dagen24, 4500.0, DAG)
print(f"  {t24}")
controle("het totaal klopt", t24["earned"] == 45.0)
controle("na dertig dagen komt er een datum", t24["date"] is not None and t24["date"] > "2034")
kort24 = bat.terugverdiend({k: v for k, v in list(dagen24.items())[:10]}, 4500.0, DAG)
controle("na tien dagen nog niet", kort24["date"] is None and kort24["earned"] == 15.0, f"{kort24}")
controle("zonder aankoopprijs alleen het bedrag", bat.terugverdiend(dagen24, None, DAG)["date"] is None)

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
         nacht31 is not None and nacht31 < 0 and abs(nacht31 - (-(11.0 - (0.15 * 14.6) * 0.736))) < 0.05,
         f"{nacht31}")

print()
print(f"{GOED} goed, {FOUT} fout")
sys.exit(1 if FOUT else 0)
