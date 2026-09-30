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
         nacht31 is not None and nacht31 < 0 and abs(nacht31 - (-(11.0 - (0.15 * 14.6) * 0.736))) < 0.05,
         f"{nacht31}")

print("32. de batterij helpt de auto alleen met wat er echt over is (v0.90.0)")
# De bewoner van de eerste woning op 23-09-2026, naar evcc: "bij laden van de auto
# mag alle batterijcapaciteit boven X% gebruikt worden." De eigenaar: de
# nachtbalans gaat voor, "auto laden vanuit de batterij doe je echt alleen als er
# te veel capaciteit over is; drie keer verlies."
a32 = anker(soc=80.0, auto_boven=40.0)
# 14,6 kWh, rendement 0,736: morgenvroeg 3,0 kWh over is 3,0 / 0,736 = 4,08 kWh
# aan de accukant, 27,9 procentpunt: de nacht heeft 52,1% nodig.
controle("de nacht gaat voor: grens 52% en niet de 40% van de bewoner",
         abs(bat.auto_grens(a32, 3.0) - (80.0 - 3.0 / 0.736 / 14.6 * 100)) < 0.01, f"{bat.auto_grens(a32, 3.0)}")
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
         abs(kort33[0] - 0.5 / 0.736 * eta33) < 1e-6, f"{kort33}")
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


print()
print(f"{GOED} goed, {FOUT} fout")
sys.exit(1 if FOUT else 0)
