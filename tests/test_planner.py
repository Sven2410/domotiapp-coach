"""Scenario's langs de rekenkern, zonder Home Assistant.

Elk geval is een situatie die vandaag in die woning had kunnen staan, met de uitkomst
die erbij hoort. Draait tegen planner.py zoals die op schijf staat.
"""

import datetime as dt
import importlib.util
import pathlib
import sys

# Geen absoluut pad: deze repo staat op de ene machine in C:\dev en op de
# andere in ~/dev.
PAD = (pathlib.Path(__file__).resolve().parent.parent
       / "custom_components" / "domotiapp_coach" / "planner.py")
spec = importlib.util.spec_from_file_location("planner", PAD)
planner = importlib.util.module_from_spec(spec)
# Eerst registreren, dan pas draaien: `dataclass` zoekt de module op tijdens het
# uitvoeren van het bestand en struikelt anders over zichzelf.
sys.modules["planner"] = planner
spec.loader.exec_module(planner)

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


from planner import (  # noqa: E402
    Car, Charger, Decision, Forecast, Grid, Sun, Tariff, Window, decide, MIN_AMPS,
)

FOUT = 0
GOED = 0


def controle(naam, gelukt, uitleg=""):
    global FOUT, GOED
    if gelukt:
        GOED += 1
    else:
        FOUT += 1
        print(f"  FOUT  {naam}: {uitleg}")


def middag(uur=14, minuut=0):
    return dt.datetime(2026, 8, 18, uur, minuut)


def venster(now, klaar="06:00"):
    """Een venster met klaar-tijd morgenvroeg, zoals in een echte woning."""
    einde = (now + dt.timedelta(days=1)).replace(
        hour=int(klaar[:2]), minute=int(klaar[3:]), second=0, microsecond=0
    )
    return Window(enabled=True, opens=None, deadline=einde)


def kromme(dag, eerste_uur, waarden, huis=0.0):
    """Een zonverwachting per uur, en wat het huis er zelf van opmaakt."""
    zon = {}
    for i, kwh in enumerate(waarden):
        zon[dag.replace(hour=0, minute=0, second=0, microsecond=0)
            + dt.timedelta(hours=eerste_uur + i)] = kwh
    return Forecast(solar_kwh=zon, house_kwh={u: huis for u in range(24)})


def sven_auto(soc=70.0, capaciteit=19.7):
    return Car(capacity_kwh=capaciteit, phases=1, soc_percent=soc)


def paal(laadt=True, amps=6.0, aangesloten=True):
    return Charger(
        max_amps=14.0,
        connected=aangesloten,
        charging=laadt,
        actual_amps=amps if laadt else 0.05,
        started_at=middag(13, 0) if laadt else None,
    )


NET_LEEG = Grid(surplus_w=0.0, phase_amps=[5.0, 3.0, 2.0], fuse_amps=25.0, charger_amps=5.7)
VAST = Tariff(buy=0.24171, feed_in=0.0721 - 0.052756)
ZON_KRAP = Sun(remaining_kwh=6.3, now_w=1700.0, next_w=1600.0)
ZON_RUIM = Sun(remaining_kwh=20.0, now_w=3000.0, next_w=3200.0)


print("=== 1. vast contract, er komt vanmiddag nog zon ===")
# De klif van 14:37: bij een vast contract sprong de coach naar vol vermogen en
# kocht hij uren in terwijl er die middag nog zon aankwam. Sinds 30-08-2026 is
# er geen sport meer die dat beslist maar een vergelijking: bij een vast tarief
# kost elk uur hetzelfde, dus zijn de zonschijven de goedkoopste van allemaal en
# worden die het eerst gepakt.
nu = middag(14, 37)
# Vanaf 15:00 nog vier uur zon, samen ruim genoeg voor de 6,6 kWh die erin moet.
MIDDAGZON = kromme(nu, 15, [2.5, 2.5, 2.0, 1.5])
d = decide(nu, [], NET_LEEG, sven_auto(), paal(), venster(nu), tariff=VAST,
           sun=ZON_KRAP, forecast=MIDDAGZON)
print(f"  {d.rule}: laden={d.charge} {d.amps} A  {d.reason}")
# Een lopende sessie wordt niet meteen afgebroken: `_keep_alive` houdt hem drie
# ronden op de laagste stand. Waar het om gaat is dat hij niet naar vol vermogen
# springt.
controle("geen vol vermogen meer", d.amps <= 6, f"kreeg {d.rule} met {d.amps} A")

d2 = decide(nu, [], NET_LEEG, sven_auto(), paal(), venster(nu), tariff=VAST,
            sun=ZON_KRAP, forecast=MIDDAGZON, holding=planner.STOP_ROUNDS)
print(f"  na de hysterese (STOP_ROUNDS ronden): {d2.rule} laden={d2.charge}")
controle("stopt na de hysterese", not d2.charge, f"kreeg {d2.rule}")
controle("en zegt wanneer hij dan wel begint", "15:00" in d2.plan or "15:00" in d2.reason,
         f"{d2.reason} / {d2.plan}")

print("=== 2. zonder zon op komst geldt de avondregel ===")
# Is er niets meer van het dak te verwachten, dan is elk uur even duur en valt er
# op prijs niets te kiezen. Dan blijft de afspraak van 20-08-2026 over: wacht
# tot acht uur, want dan zijn de pieken van koken voorbij.
d = decide(nu, [], NET_LEEG, sven_auto(), paal(), venster(nu), tariff=VAST,
           sun=ZON_KRAP, forecast=Forecast(), holding=planner.STOP_ROUNDS)
print(f"  {d.rule}: laden={d.charge} {d.amps} A  {d.reason}")
controle("hij wacht tot de avond", not d.charge, f"kreeg {d.rule} met {d.amps} A")
controle("en zegt waarom", "20:00" in d.reason and "koken" in d.reason, d.reason)

print("=== 3. vast contract zonder accustand: wachten, niet laden ===")
d = decide(nu, [], NET_LEEG, sven_auto(soc=None), paal(laadt=False), venster(nu), tariff=VAST, sun=ZON_KRAP)
print(f"  {d.rule}: laden={d.charge}  needs_soc={d.needs_soc}  {d.reason}")
controle("laadt niet vroeg zonder accustand", not d.charge and d.rule == "no-soc", f"kreeg {d.rule}")
controle("vraagt om de accustand", d.needs_soc)

print("=== 4. zonder accustand, vlak voor het uiterste moment ===")
# 19,7 kWh eenfasig op 14 A is bijna zeven uur, dus met klaar om 06:00 ligt het
# uiterste startmoment even na elven 's avonds.
nu = middag(23, 30)
d = decide(nu, [], NET_LEEG, sven_auto(soc=None), paal(laadt=False), venster(nu),
           tariff=VAST, sun=ZON_KRAP)
print(f"  {d.rule}: laden={d.charge} {d.amps} A  {d.reason}")
controle("vangnet grijpt in", d.charge and d.rule.startswith("deadline"), f"kreeg {d.rule}")
controle("zegt dat het een aanname is", d.needs_soc and "lege accu" in d.reason)

print("=== 5. zonder accustand én zonder klaar-tijd: gewoon laden ===")
nu = middag(14, 37)
d = decide(nu, [], NET_LEEG, sven_auto(soc=None), paal(), Window(enabled=False),
           tariff=VAST, sun=ZON_KRAP)
print(f"  {d.rule}: laden={d.charge} {d.amps} A")
controle("laadt zoals vroeger", d.charge and d.rule == "fixed-tariff", f"kreeg {d.rule}")

print("=== 6. wekstroom: auto hangt eraan maar neemt niets af ===")
zonnig = Grid(surplus_w=1500.0, phase_amps=[2.0, 2.0, 2.0], fuse_amps=25.0, charger_amps=0.0)
# Dit uur duur, vannacht goedkoop. Dan pakt de vergelijking alleen de zon van nu
# en is het aanbod de ondergrens, en dat is de opstelling waarin een wekstroom
# betekenis heeft: op vol vermogen valt er niets te verhogen.
DUUR_NU = []
for _u in range(20):
    _start = middag(14, 0) + dt.timedelta(hours=_u)
    DUUR_NU.append({"start": _start, "end": _start + dt.timedelta(hours=1),
                    "price": 0.40 if _u < 6 else 0.10, "feed_in": 0.05})
d = decide(nu, DUUR_NU, zonnig, sven_auto(), paal(laadt=False), venster(nu),
           tariff=VAST, sun=ZON_RUIM, waking=True)
print(f"  {d.rule}: {d.amps} A  {d.reason}")
# Zestien sinds 17-09-2026, begrensd door wat er onder de zekering past. Hier is
# dat veertien: een huis van 2 A per fase op een zekering van 25. Dat een Easee
# in automatische fasemodus bij tien ampère voor één fase koos is de reden; zie
# `WAKE_AMPS` in planner.py.
controle("biedt zo veel aan als er past", d.charge and d.amps == 14,
         f"kreeg {d.amps} A via {d.rule}")
controle("heet ook zo", d.rule.endswith("+wake"))

ruim = Grid(surplus_w=1500.0, phase_amps=[0.0, 0.0, 0.0], fuse_amps=40.0, charger_amps=0.0)
grote_paal = Charger(max_amps=32.0, connected=True, charging=False, actual_amps=0.05)
d = decide(nu, DUUR_NU, ruim, sven_auto(), grote_paal, venster(nu),
           tariff=VAST, sun=ZON_RUIM, waking=True)
controle("en niet meer dan zestien", d.amps == 16, f"kreeg {d.amps} A")

print("=== 7. wekstroom blijft onder de zekering ===")
krap = Grid(surplus_w=1500.0, phase_amps=[17.0, 3.0, 2.0], fuse_amps=25.0, charger_amps=0.0)
d = decide(nu, [], krap, sven_auto(), paal(laadt=False), venster(nu),
           tariff=VAST, sun=ZON_RUIM, waking=True)
print(f"  {d.rule}: {d.amps} A")
controle("niet meer dan er ruimte is", d.amps <= 8, f"kreeg {d.amps} A")

print("=== 8. wekpoging verbruikt: dan zegt hij dat de auto niets doet ===")
# Eerst de andere kant: drie seconden na het aanbod hoort hij zijn mond te houden.
vroeg = decide(nu, [], zonnig, sven_auto(), paal(laadt=False), venster(nu),
               tariff=VAST, sun=ZON_RUIM, waking=False, asking_seconds=3)
controle("geeft de auto eerst even de tijd", "+waiting-for-car" not in vroeg.rule,
         vroeg.rule)
d = decide(nu, [], zonnig, sven_auto(), paal(laadt=False), venster(nu),
           tariff=VAST, sun=ZON_RUIM, waking=False, asking_seconds=90)
print(f"  {d.rule}: {d.reason}")
controle("wacht op de auto", d.rule.endswith("+waiting-for-car"))
controle("geen loze belofte", "neemt nog niets af" in d.reason)

print("=== 9. een auto die gewoon laadt, wordt niet gewekt ===")
d = decide(nu, [], zonnig, sven_auto(), paal(laadt=True, amps=5.7), venster(nu),
           tariff=VAST, sun=ZON_RUIM, waking=True, asking_seconds=0)
print(f"  {d.rule}: {d.amps} A")
controle("geen wekstroom bij een lopende sessie", "+wake" not in d.rule)

print("=== 10. dynamisch contract zonder accustand: niet elk uur is goedkoop ===")
prijzen = []
begin = dt.datetime(2026, 8, 18, 0, 0)
for u in range(48):
    start = begin + dt.timedelta(hours=u)
    prijzen.append({
        "start": start,
        "end": start + dt.timedelta(hours=1),
        # 's Nachts goedkoop, overdag duur.
        "price": 0.10 if 1 <= start.hour <= 5 else 0.34,
        "feed_in": 0.05,
    })
nu = middag(14, 37)
d = decide(nu, prijzen, NET_LEEG, sven_auto(soc=None), paal(laadt=False), venster(nu),
           tariff=Tariff(buy=0.34, feed_in=0.05), sun=ZON_KRAP)
print(f"  {d.rule}: laden={d.charge}  {d.reason}")
controle("wacht tot de accustand bekend is", not d.charge and d.rule == "no-soc",
         f"kreeg {d.rule}")
controle("weet dat de accustand mist", d.needs_soc)

print("=== 11. onveranderd gedrag: pauze, snelladen, geen kabel ===")
d = decide(nu, [], NET_LEEG, sven_auto(), paal(aangesloten=False, laadt=False), venster(nu),
           tariff=VAST, sun=ZON_RUIM)
controle("geen kabel blijft geen kabel", d.rule == "disconnected" and not d.charge)

p = paal(laadt=True)
p.paused_by_user = True
d = decide(nu, [], NET_LEEG, sven_auto(), p, venster(nu), tariff=VAST, sun=ZON_RUIM)
controle("pauze blijft pauze", d.rule == "user-hold" and not d.charge)

p = paal(laadt=True)
p.boost = True
d = decide(nu, [], NET_LEEG, sven_auto(), p, venster(nu), tariff=VAST, sun=ZON_RUIM)
controle("snelladen blijft snelladen", d.rule == "boost" and d.charge and d.amps == 14,
         f"kreeg {d.rule} {d.amps} A")

print("=== 12. de zon van nu wordt gepakt als het net duurder is ===")
d = decide(nu, DUUR_NU, zonnig, sven_auto(), paal(laadt=True, amps=5.7), venster(nu),
           tariff=VAST, sun=ZON_RUIM)
print(f"  {d.rule}: {d.amps} A  {d.reason}")
controle("laadt op de zon", d.charge and d.rule.startswith("surplus"), f"kreeg {d.rule}")
controle("en niet meer dan het dak geeft", d.amps <= 6, f"{d.amps} A")

print("=== 13. valt de coach weg, dan loopt de pauze af op het laatste startmoment ===")
# De 0 die naar de paal gaat krijgt een houdbaarheid: precies tot het moment
# waarop de coach zelf weer zou beginnen. Valt Home Assistant om, dan laadt de
# paal vanaf dat moment gewoon zelf door. Duurder, maar wel vol.
nu = middag(14, 37)
d = decide(nu, [], NET_LEEG, sven_auto(), paal(laadt=False), venster(nu),
           tariff=VAST, sun=ZON_RUIM, forecast=MIDDAGZON, holding=planner.STOP_ROUNDS)
uren = d.hold_minutes / 60
print(f"  {d.rule}: pauze {d.hold_minutes} minuten ({uren:.2f} uur), begint {d.plan}")
controle("hij wacht op de zon van straks", not d.charge, f"{d.rule}")
controle("en de pauze loopt af op het uur dat hij gekozen heeft",
         d.hold_minutes == 23, f"{d.hold_minutes} minuten")
controle("dus ruim vóór de klaar-tijd", uren < 15.4, f"{uren:.2f} uur")

print("=== 14. zonder accustand hetzelfde, maar met een lege accu gerekend ===")
d = decide(nu, [], NET_LEEG, sven_auto(soc=None), paal(laadt=False), venster(nu),
           tariff=VAST, sun=ZON_KRAP)
uren = d.hold_minutes / 60
print(f"  {d.rule}: pauze {d.hold_minutes} minuten ({uren:.1f} uur)")
controle("een lege accu kost meer tijd, dus korter wachten", 7.5 < uren < 9.5,
         f"{uren:.1f} uur")

print("=== 15. auto zonder ingevulde accucapaciteit: gewoon laden ===")
# Zonder capaciteit valt er niets te berekenen, ook geen slechtste geval. Dan
# mag hij niet blijven wachten op iets wat nooit komt.
kaal = Car(capacity_kwh=0, phases=1, soc_percent=None)
d = decide(nu, [], NET_LEEG, kaal, paal(laadt=False), venster(nu), tariff=VAST, sun=ZON_KRAP)
print(f"  {d.rule}: laden={d.charge} {d.amps} A")
controle("blijft niet eeuwig wachten", d.charge and d.rule == "fixed-tariff",
         f"kreeg {d.rule}")

print("=== 16. auto die volgens zijn accustand vol is ===")
d = decide(nu, prijzen, NET_LEEG, sven_auto(soc=100), paal(laadt=False), venster(nu),
           tariff=Tariff(buy=0.34, feed_in=0.05), sun=ZON_RUIM)
print(f"  {d.rule}: laden={d.charge}  {d.reason}")
controle("laadt een volle auto niet vol", not d.charge and d.rule == "complete",
         f"kreeg {d.rule} met {d.amps} A")

print("=== 17. twee palen op één zekering delen de ruimte ===")
ruim = Grid(surplus_w=6000.0, phase_amps=[6.0, 4.0, 4.0], fuse_amps=25.0, charger_amps=0.0)
eerste = decide(nu, [], ruim, sven_auto(), paal(laadt=False), venster(nu),
                tariff=VAST, sun=ZON_RUIM)
gereserveerd = Grid(surplus_w=6000.0, phase_amps=[6.0, 4.0, 4.0], fuse_amps=25.0,
                    charger_amps=0.0, reserved_amps=float(eerste.amps))
tweede = decide(nu, [], gereserveerd, sven_auto(), paal(laadt=False), venster(nu),
                tariff=VAST, sun=ZON_RUIM)
print(f"  eerste paal {eerste.amps} A, tweede paal {tweede.amps} A, samen "
      f"{eerste.amps + tweede.amps} A onder een zekering van 25 A met 6 A huis")
controle("samen blijven ze onder de zekering",
         eerste.amps + tweede.amps + 6 <= 25 - 3, f"{eerste.amps}+{tweede.amps}")

print("=== 18. een pauze die de klaar-tijd gaat kosten, zegt dat ===")
# 30% van 19,7 kWh op 14 A eenfasig is ruim twee uur werk, dus met nog twee uur
# te gaan haalt hij het niet meer.
laat = middag(22, 0)
krap_venster = Window(enabled=True, opens=None, deadline=laat + dt.timedelta(hours=2))
p = paal(laadt=False)
p.paused_by_user = True
d = decide(laat, [], NET_LEEG, sven_auto(), p, krap_venster, tariff=VAST, sun=ZON_RUIM)
print(f"  {d.rule}: {d.reason}  risico={d.deadline_risk}")
controle("pauze blijft staan", not d.charge and d.rule == "user-hold")
controle("maar hij waarschuwt", d.deadline_risk and "haalt" in d.reason, d.reason)

print("=== 19. en zwijgt als er nog zeeën van tijd zijn ===")
vroeg = middag(14, 0)
p2 = paal(laadt=False)
p2.paused_by_user = True
d = decide(vroeg, [], NET_LEEG, sven_auto(), p2, venster(vroeg), tariff=VAST, sun=ZON_RUIM)
print(f"  {d.rule}: {d.reason}  risico={d.deadline_risk}")
controle("geen loos alarm", not d.deadline_risk, d.reason)

print("=== 20. de eigen rem van de coach is geen bewijs dat de paal niet harder kan ===")
# Wat er op 20-08-2026 om 15:48 in die woning gebeurde. Auto op 12%, klaar om 06:00,
# zonvolgend op 6 A omdat de coach hem daar zelf op zette. Er moet 19,3 kWh in:
# op 6 A is dat 13,96 uur en dus te laat, op 14 A 5,98 uur en dus zeeën van tijd.
zonvolgend = Charger(
    max_amps=14.0, connected=True, charging=True, actual_amps=5.66,
    started_at=dt.datetime(2026, 8, 20, 15, 35),
    limit_amps=6.0, no_current_reason="limited_by_charger_dynamic_limit",
)
morgenvroeg = Window(enabled=True, opens=None,
                     deadline=dt.datetime(2026, 8, 21, 6, 0))
leeg = sven_auto(soc=12.0)
zon = Grid(surplus_w=1400.0, phase_amps=[5.0, 3.0, 2.0], fuse_amps=25.0, charger_amps=5.66)

print(f"  op 6 A duurt het {planner.hours_needed(leeg, 6):.2f} uur, "
      f"op 14 A {planner.hours_needed(leeg, 14):.2f} uur")
controle("de paal wordt door de coach zelf geremd",
         planner.throttled_by_coach(zonvolgend), f"{zonvolgend}")
controle("dus telt het plafond als tempo, niet de gemeten 6 A",
         planner.charging_pace(dt.datetime(2026, 8, 20, 15, 48), zonvolgend, 14) == 14)

kwart_voor_vier = dt.datetime(2026, 8, 20, 15, 48)
d = decide(kwart_voor_vier, [], zon, leeg, zonvolgend, morgenvroeg,
           tariff=VAST, sun=ZON_RUIM)
print(f"  15:48  {d.rule}: laden={d.charge} {d.amps} A")
controle("om kwart voor vier nog niet op vol vermogen",
         d.rule != "deadline" and d.amps < 14, f"{d.rule} met {d.amps} A")

# En op het laatste moment dat nog past wél: 06:00 min 5,98 uur min een kwartier
# marge komt uit op even voor kwart voor twaalf 's avonds.
laat = dt.datetime(2026, 8, 20, 23, 50)
zonvolgend.started_at = dt.datetime(2026, 8, 20, 23, 30)
d = decide(laat, [], Grid(surplus_w=0.0, phase_amps=[5.0, 3.0, 2.0], fuse_amps=25.0,
                          charger_amps=5.66),
           leeg, zonvolgend, morgenvroeg, tariff=VAST, sun=Sun(remaining_kwh=0.0))
print(f"  23:50  {d.rule}: laden={d.charge} {d.amps} A  {d.reason}")
controle("maar 's nachts wel", d.rule == "deadline" and d.amps == 14,
         f"{d.rule} met {d.amps} A")

print("=== 21. een auto die zelf afbouwt telt nog steeds gewoon mee ===")
# Het omgekeerde geval, en dat moet blijven werken: de coach vraagt 14 A en de
# paal levert er 6. Dan is de gemeten stroom wél het echte tempo.
afbouwend = Charger(
    max_amps=14.0, connected=True, charging=True, actual_amps=6.0,
    started_at=dt.datetime(2026, 8, 20, 15, 35),
    limit_amps=14.0, no_current_reason="limited_by_equalizer",
)
controle("dit is niet de coach zijn eigen rem",
         not planner.throttled_by_coach(afbouwend), f"{afbouwend}")
controle("dus telt de gemeten stroom",
         planner.charging_pace(dt.datetime(2026, 8, 20, 15, 48), afbouwend, 14) == 6)

print("=== 22. zonder limietsensor blijft het merk zijn eigen woord ===")
zonder = Charger(
    max_amps=14.0, connected=True, charging=True, actual_amps=5.66,
    started_at=dt.datetime(2026, 8, 20, 15, 35),
    no_current_reason="limited_by_charger_dynamic_limit",
)
controle("de Easee zegt zelf dat het de dynamische limiet is",
         planner.throttled_by_coach(zonder), f"{zonder}")
blind = Charger(
    max_amps=14.0, connected=True, charging=True, actual_amps=5.66,
    started_at=dt.datetime(2026, 8, 20, 15, 35),
)
controle("en zonder allebei blijft het zoals het was",
         not planner.throttled_by_coach(blind)
         and planner.charging_pace(dt.datetime(2026, 8, 20, 15, 48), blind, 14) == 6)

print("=== 23. dynamisch contract: vroeg vol als de dure uren nog moeten komen ===")
# de eigen vraag van 20-08-2026: de klaar-tijd is een moment waarop de auto vol
# moet zijn, niet een moment waarop hij vol moet raken. Komt er een avondpiek
# aan en is de middag spotgoedkoop, dan hoort hij 's middags te laden en om acht
# uur 's avonds al vol te staan, elf uur voor de klaar-tijd.
dag = dt.datetime(2026, 8, 20, 0, 0)


def cent(uur):
    """Goedkope middag, dure avondpiek, gewone nacht."""
    if 12 <= uur < 20:
        return 0.08
    if 20 <= uur < 23:
        return 0.45
    return 0.22


markt = []
for u in range(48):
    start = dag + dt.timedelta(hours=u)
    markt.append({"start": start, "end": start + dt.timedelta(hours=1),
                  "price": cent(start.hour), "feed_in": 0.05})

DYNAMISCH = Tariff(buy=0.22, feed_in=0.05)
halfvol = sven_auto(soc=45.0)
morgenvroeg = Window(enabled=True, opens=None, deadline=dt.datetime(2026, 8, 21, 6, 0))
GEEN_ZON = Grid(surplus_w=0.0, phase_amps=[5.0, 3.0, 2.0], fuse_amps=25.0, charger_amps=5.66)

zonvolgend2 = Charger(
    max_amps=14.0, connected=True, charging=True, actual_amps=5.66,
    started_at=dt.datetime(2026, 8, 20, 15, 35), limit_amps=6.0,
)
middags = dt.datetime(2026, 8, 20, 15, 48)
d = decide(middags, markt, GEEN_ZON, halfvol, zonvolgend2, morgenvroeg,
           tariff=DYNAMISCH, sun=Sun(remaining_kwh=0.0))
print(f"  15:48  {d.rule}: laden={d.charge} {d.amps} A")
print(f"         plan: {d.plan}")
controle("hij pakt het goedkope middaguur meteen",
         d.charge and d.rule == "cheap-hour" and d.amps == 14, f"{d.rule} {d.amps} A")

uren = planner.cheapest_hours(markt, middags, morgenvroeg.deadline,
                              planner.hours_needed(halfvol, 14))
print(f"         geboekt: {len(uren)} uur, duurste erin {max(r['price'] for r in uren):.2f}, "
      f"laatste om {max(r['start'] for r in uren):%H:%M}")
controle("en boekt alleen goedkope uren",
         max(row["price"] for row in uren) == 0.08, f"{[r['price'] for r in uren]}")
controle("dus staat hij ver voor de klaar-tijd vol",
         max(row["start"] for row in uren).hour < 20, f"{[str(r['start']) for r in uren]}")

# En in de avondpiek wacht hij, want de nacht is goedkoper.
avonds = dt.datetime(2026, 8, 20, 20, 30)
stil = Charger(max_amps=14.0, connected=True, charging=False, actual_amps=0.05)
d = decide(avonds, markt, GEEN_ZON, halfvol, stil, morgenvroeg,
           tariff=DYNAMISCH, sun=Sun(remaining_kwh=0.0))
print(f"  20:30  {d.rule}: laden={d.charge}  {d.reason}")
controle("in de avondpiek wacht hij", not d.charge and d.rule.startswith("wait-for-price"),
         f"{d.rule}")

print("=== 24. en de oude rekenwijze maakte juist die planning stuk ===")
# Met het tempo van de eigen rem (6 A) denkt de coach dat er negen uur nodig is
# in plaats van vier, boekt hij negen uur en zitten de dure avonduren er gewoon
# bij. Precies de fout van 20-08, maar dan in de portemonnee van een klant met
# een dynamisch contract.
echt = planner.throttled_by_coach
planner.throttled_by_coach = lambda charger: False
try:
    oud_tempo = planner.charging_pace(middags, zonvolgend2, 14)
    oud_uren = planner.cheapest_hours(markt, middags, morgenvroeg.deadline,
                                      planner.hours_needed(halfvol, oud_tempo))
finally:
    planner.throttled_by_coach = echt
print(f"  zoals het was: tempo {oud_tempo} A, {len(oud_uren)} uur geboekt, "
      f"duurste erin {max(r['price'] for r in oud_uren):.2f}")
print(f"  nu:            tempo 14 A, {len(uren)} uur geboekt, "
      f"duurste erin {max(r['price'] for r in uren):.2f}")
controle("de oude manier boekte meer uren dan nodig", len(oud_uren) > len(uren),
         f"{len(oud_uren)} tegen {len(uren)}")
controle("en sleepte de dure uren mee naar binnen",
         max(row["price"] for row in oud_uren) > max(row["price"] for row in uren),
         f"{max(r['price'] for r in oud_uren)}")

print("=== 25. wie wacht, hoort te lezen wanneer hij weer begint ===")
# De eigenaar op 20-08-2026, kwart voor zeven 's avonds: "hoezo is de laadpaal gestopt
# met laden?" De kaart zei alleen dat hij op tijd zou bijvullen, niet wanneer.
avond = dt.datetime(2026, 8, 20, 18, 48)
tot_zes = Window(enabled=True, opens=None, deadline=dt.datetime(2026, 8, 21, 6, 0))
stille_paal = Charger(max_amps=14.0, connected=True, charging=False, actual_amps=0.05)
donker = Grid(surplus_w=0.0, phase_amps=[4.0, 2.0, 2.0], fuse_amps=25.0)
op = Sun(remaining_kwh=1.298, now_w=1217.0, next_w=400.0)
d = decide(avond, [], donker, sven_auto(soc=40.0), stille_paal, tot_zes,
           tariff=VAST, sun=op)
print(f"  {d.rule}: {d.plan}")
controle("hij wacht op de zon", not d.charge and d.rule == "wait-for-sun", d.rule)
controle("en zegt hoe laat hij begint", "20:00" in d.plan, d.plan)
controle("de pauze reikt precies tot dat moment", d.hold_minutes == 72,
         f"{d.hold_minutes}")

# En het moment in de tekst is hetzelfde moment als waarop de regel aanslaat,
# want ze delen dezelfde bron. Loopt dat uit elkaar, dan staat er een tijd op de
# kaart waar niets gebeurt.
genoemd = dt.datetime(2026, 8, 20, 20, 0)
net_ervoor = decide(genoemd - dt.timedelta(minutes=1), [], donker,
                    sven_auto(soc=40.0), stille_paal, tot_zes, tariff=VAST, sun=op)
net_erna = decide(genoemd + dt.timedelta(minutes=1), [], donker,
                  sven_auto(soc=40.0), stille_paal, tot_zes, tariff=VAST, sun=op)
print(f"  {genoemd:%H:%M} min een minuut: {net_ervoor.rule}   "
      f"plus een minuut: {net_erna.rule}")
controle("een minuut ervoor wacht hij nog", net_ervoor.rule == "wait-for-sun",
         net_ervoor.rule)
controle("en een minuut erna gaat hij",
         net_erna.rule == "easy-pace" and net_erna.charge, net_erna.rule)

print("=== 26. vast contract: wachten houdt op om acht uur 's avonds ===")
# De eigenaar op 20-08-2026: "op een vast contract is een kwartier speling niet
# voldoende, ik wil dat je het zo maakt wanneer het niet meer rendabel is van de
# zon dat hij vanaf 20 uur dan gaat laden, dan heb je de grote pieken van het
# koken etc achter de rug en belast je het ook niet zo veel."
STIL = Charger(max_amps=14.0, connected=True, charging=False, actual_amps=0.05)
DONKER = Grid(surplus_w=0.0, phase_amps=[4.0, 2.0, 2.0], fuse_amps=25.0)
ZON_OP = Sun(remaining_kwh=0.4, now_w=200.0, next_w=100.0)
MORGEN_ZES = dt.datetime(2026, 8, 21, 6, 0)


def vast_besluit(nu, eind=MORGEN_ZES, soc=40.0, zon=ZON_OP):
    return decide(nu, [], DONKER, sven_auto(soc=soc), STIL,
                  Window(enabled=True, opens=None, deadline=eind),
                  tariff=VAST, sun=zon)


d = vast_besluit(dt.datetime(2026, 8, 20, 18, 48))
print(f"  18:48  {d.rule}: {d.plan}")
controle("kwart voor zeven wacht hij nog", not d.charge and d.rule == "wait-for-sun", d.rule)
controle("en noemt acht uur, niet half twee", "20:00" in d.plan, d.plan)

d = vast_besluit(dt.datetime(2026, 8, 20, 20, 0))
print(f"  20:00  {d.rule}: {d.amps} A  {d.reason}")
# De eigenaar op 25-08-2026: op een vast contract is de nacht lang genoeg, dus de
# aansluiting hoeft er niet vol voor open. Sinds 04-09-2026 is rustig het
# laagste hele aantal ampère dat een uur vóór de klaar-tijd klaar is: 13,1 kWh
# tussen 20:00 en 05:00 is 6,3 A, dus 7. Op 6 A was hij om 05:00 niet klaar en
# moest de klaar-tijdregel het laatste uur op vol vermogen redden.
controle("om acht uur gaat hij", d.charge and d.rule == "easy-pace" and d.amps == 7,
         f"{d.rule} {d.amps} A")
controle("en dan rustig, niet op vol vermogen", d.amps < 14,
         f"{d.amps} A tegen vol vermogen 14 A")
controle("en hij zegt waarom hij rustig aan doet", "aansluiting" in d.reason, d.reason)

# En het gat dat dit dicht: wie 's nachts inplugt kreeg een kwartier speling.
# Nu laadt hij meteen, want de avondpiek is dan allang voorbij. Om middernacht
# en niet om één uur: om één uur past 13,1 kWh op 14 A niet meer een uur vóór
# 06:00, en dan hoort de klaar-tijdregel te winnen (zie de proef eronder).
d = vast_besluit(dt.datetime(2026, 8, 21, 0, 0))
print(f"  00:00  {d.rule}: {d.amps} A")
controle("'s nachts geen kwartier speling meer",
         d.charge and d.rule == "easy-pace", f"{d.rule}")

# En het vangnet eronder: rustig aan mag alleen zolang het past. Een lege auto
# om vier uur 's nachts haalt zes uur niet op 6 A, dus dan hoort de klaar-tijd te
# winnen en niet de rust.
d = vast_besluit(dt.datetime(2026, 8, 21, 4, 0), soc=10.0)
print(f"  04:00 met een lege auto  {d.rule}: {d.amps} A")
controle("rustig aan wijkt voor de klaar-tijd",
         d.charge and d.rule == "deadline" and d.amps > MIN_AMPS,
         f"{d.rule} {d.amps} A")

print("=== 27. maar een klaar-tijd overdag heeft geen avond ===")
# Klaar om zeven uur 's avonds: tussen de avond ervoor en die klaar-tijd ligt
# een hele dag zon. Dan hoort hij gewoon te wachten, met de klaar-tijd als
# vangnet, en niet om acht uur 's avonds daarvoor al vol te lopen.
MIDDAG_ZON = kromme(dt.datetime(2026, 8, 20), 15, [2.0, 2.0, 1.5, 1.0])
d = decide(dt.datetime(2026, 8, 20, 14, 0), [], DONKER, sven_auto(soc=80.0), STIL,
           Window(enabled=True, opens=None, deadline=dt.datetime(2026, 8, 20, 19, 0)),
           tariff=VAST, sun=ZON_RUIM, forecast=MIDDAG_ZON, holding=planner.STOP_ROUNDS)
print(f"  klaar om 19:00, nu 14:00  {d.rule}: {d.plan}")
controle("overdag wacht hij op de zon", not d.charge and d.rule == "wait-for-sun", d.rule)
controle("en de avondregel bemoeit zich er niet mee", "20:00" not in d.plan, d.plan)
controle("de avond bij 19:00 bestaat niet",
         planner._evening_before(dt.datetime(2026, 8, 20, 19, 0)) is None)
controle("de avond bij 06:00 is de avond ervoor",
         planner._evening_before(MORGEN_ZES) == dt.datetime(2026, 8, 20, 20, 0))

print("=== 28. een regendag is ook een dag om tot acht uur te wachten ===")
d = vast_besluit(dt.datetime(2026, 8, 20, 10, 0))
print(f"  10:00  {d.rule}: {d.plan}  pauze {d.hold_minutes} min")
controle("hij wacht", not d.charge and d.rule == "wait-for-sun", d.rule)
controle("de pauze reikt tot acht uur en niet verder",
         d.hold_minutes == 600, f"{d.hold_minutes}")

print("=== 29. snelladen dat de zekering tegenkomt, zegt dat het de zekering is ===")
# De eigenaar op 20-08-2026 om 19:18. Hij plugde in, zette snelladen aan, en kreeg 8 A.
# Precies nagerekend uit zijn meter: op het moment dat de auto begon te trekken
# stond L1 al op 16 A terwijl de paal zelf nog 2,7 A meldde. Het huis leek dus
# 13,3 A te vragen, en 25 min 13,3 min 3 marge is 8,7 A.
piek = Grid(surplus_w=0.0, phase_amps=[16.0, 0.0, 4.0], fuse_amps=25.0,
            charger_amps=2.688, margin_amps=3.0)
snel = Charger(max_amps=14.0, connected=True, charging=True, actual_amps=2.688,
               started_at=dt.datetime(2026, 8, 20, 19, 18), boost=True)
d = decide(dt.datetime(2026, 8, 20, 19, 18, 19), [], piek, sven_auto(soc=50.0), snel,
           Window(enabled=True, opens=None, deadline=dt.datetime(2026, 8, 21, 6, 0)),
           tariff=VAST, sun=Sun(remaining_kwh=0.0))
print(f"  {d.rule}: {d.amps} A  {d.reason}")
controle("hij komt uit op 8 A, net als in het echt", d.amps == 8, f"{d.amps} A")
controle("en zegt dat de zekering de reden is", "zekering" in d.reason, d.reason)

# Een minuut later staat L1 op 11 met de paal op 7,7, dus het huis vraagt 3,3 A
# en is er ruimte zat. Dan hoort er niets over de zekering te staan.
rustig = Grid(surplus_w=0.0, phase_amps=[11.0, 0.0, 4.0], fuse_amps=25.0,
              charger_amps=7.723, margin_amps=3.0)
snel.actual_amps = 7.723
d = decide(dt.datetime(2026, 8, 20, 19, 19, 19), [], rustig, sven_auto(soc=50.0), snel,
           Window(enabled=True, opens=None, deadline=dt.datetime(2026, 8, 21, 6, 0)),
           tariff=VAST, sun=Sun(remaining_kwh=0.0))
print(f"  {d.rule}: {d.amps} A  {d.reason}")
controle("een minuut later gewoon 14 A", d.amps == 14, f"{d.amps} A")
controle("en dan zwijgt hij over de zekering", "zekering" not in d.reason, d.reason)

print("=== 30. een halve ochtendzon is geen reden om stroom bij te kopen ===")
# De eigenaar op 25-08-2026: "zo goedkoop mogelijk". Om negen uur is 0,9 kW overschot
# genoeg om de coach te laten beginnen, waarna hij ruim 3 kW uit het net bijkoopt
# terwijl diezelfde kilowatturen om één uur gratis van het dak komen.
OCHTEND = dt.datetime(2026, 8, 26, 9, 0)
KLAAR_MORGEN = dt.datetime(2026, 8, 27, 6, 0)
HALVE_ZON = Grid(surplus_w=900.0, phase_amps=[4.0, 3.0, 3.0], fuse_amps=25.0)
VOLLE_ZON = Grid(surplus_w=6000.0, phase_amps=[4.0, 3.0, 3.0], fuse_amps=25.0)
DAG_KOMT = Sun(remaining_kwh=18.0, now_w=2200.0, next_w=2600.0)
DAG_IS_OP = Sun(remaining_kwh=2.0, now_w=2200.0, next_w=2600.0)


def ochtend_besluit(net=HALVE_ZON, zon=DAG_KOMT, soc=30.0, tarief=VAST,
                    klaar=KLAAR_MORGEN, nu=OCHTEND, prijzen=None,
                    voorspeld=None, holding=0):
    venster_ = Window(enabled=True, opens=None, deadline=klaar) if klaar else Window()
    return decide(nu, prijzen or [], net,
                  Car(capacity_kwh=19.7, phases=3, soc_percent=soc),
                  Charger(max_amps=16.0, connected=True, charging=False, actual_amps=0.0),
                  venster_, tariff=tarief, sun=zon,
                  forecast=voorspeld or Forecast(), holding=holding)


# De verwachting is sinds 30-08-2026 een kromme per uur en geen enkel getal
# meer. Achttien kilowattuur over de dag, met de top rond het middaguur.
DAG_KROMME = kromme(OCHTEND, 10, [1.5, 2.2, 2.8, 3.0, 2.8, 2.2, 1.8, 1.2, 0.5], huis=0.3)
DAG_LEEG = kromme(OCHTEND, 10, [0.2, 0.2, 0.2, 0.2], huis=0.3)

d = ochtend_besluit(voorspeld=DAG_KROMME, holding=planner.STOP_ROUNDS)
print(f"  09:00 met 0,9 kW over en een zonnige dag  {d.rule}: {d.reason}")
controle("hij wacht op de zon van vandaag",
         not d.charge and d.rule == "wait-for-sun", f"{d.rule} {d.amps} A")
controle("en zegt hoe laat hij begint", "1" in d.plan and "Van plan" in d.plan, d.plan)

# Belooft de dag te weinig, dan valt er op de zon niets te wachten en pakt hij
# wat er nu is. **Dit is bewust anders dan voor 30-08-2026.** De oude ladder
# wachtte dan tot acht uur; de vergelijking rekent het uit en komt op iets
# anders uit.
#
# Op een vast contract zonder salderen brengt een teruggeleverde kWh 0,019 op en
# kost een ingekochte 0,242. Laden op de ondergrens met 0,9 kW zon erbij kost
# dus (0,9 x 0,019 + 3,2 x 0,242) / 4,1 = 0,19 per kWh, tegen 0,242 vanavond.
# Die 0,9 kW is straks weg, en de 3,2 die je erbij koopt kost vanavond precies
# hetzelfde. Wachten laat dus geld liggen.
d = ochtend_besluit(voorspeld=DAG_LEEG)
print(f"  zelfde ochtend, maar de dag is op  {d.rule}: {d.amps} A  {d.reason}")
controle("te weinig zon op komst: dan pakt hij wat er is",
         d.charge and d.rule == "surplus", f"{d.rule} {d.amps} A")
controle("op de ondergrens, want meer geeft het dak niet", d.amps == MIN_AMPS,
         f"{d.amps} A")
controle("en hij zegt dat de ondergrens meetelt", "ondergrens" in d.reason, d.reason)

# Dekt de zon het laden al, dan valt er niets te wachten.
d = ochtend_besluit(net=VOLLE_ZON)
print(f"  zelfde ochtend met 6 kW over  {d.rule}: {d.amps} A")
controle("genoeg overschot: gewoon laden", d.charge and d.rule == "surplus",
         f"{d.rule} {d.amps} A")

# Zonder verwachting is er niets om op te wachten, en de zon van nu telt gewoon.
d = ochtend_besluit(zon=Sun(remaining_kwh=None, now_w=2200.0, next_w=2600.0))
print(f"  zonder zonverwachting  {d.rule}: {d.amps} A")
controle("zonder verwachting pakt hij de zon van nu", d.charge, f"{d.rule} {d.amps} A")

# En zonder klaar-tijd is er geen vangnet om op terug te vallen.
d = ochtend_besluit(klaar=None)
print(f"  zonder klaar-tijd  {d.rule}: {d.amps} A")
controle("geen klaar-tijd, geen wachten", d.charge, f"{d.rule} {d.amps} A")

# Bij saldering is een teruggeleverde kWh evenveel waard als een gekochte, dus
# dan maakt uitstel niets goedkoper.
# Hij wacht dan nog steeds, maar op de gewone vaste-contractregel en niet op
# deze: er valt met uitstel niets te winnen, dus deze afweging hoort te zwijgen.
d = ochtend_besluit(tarief=Tariff(buy=0.24171, feed_in=0.24171))
print(f"  met saldering  {d.rule}: {d.amps} A")
controle("saldering: deze afweging blijft er buiten",
         d.rule != "wait-for-sun-today", f"{d.rule} {d.amps} A")

# En hij zet een lopende sessie niet stil voor een schijntje. Dekt de zon het
# laden zo goed als helemaal, dan is er niets te winnen: op 18-08-2026 kocht hij
# om kwart voor vijf twintig watt bij, en daarvoor een sessie afbreken kost meer
# dan het opbrengt. Dezelfde marge als waarmee hierboven bepaald wordt of het
# overschot genoeg is om op te laden.
BIJNA_GEDEKT = Grid(surplus_w=4000.0, phase_amps=[4.0, 3.0, 3.0], fuse_amps=25.0)
d = ochtend_besluit(net=BIJNA_GEDEKT)
print(f"  0,1 kW tekort op 4,1 kW  {d.rule}: {d.amps} A")
controle("een schijntje bijkopen is geen reden om te stoppen",
         d.charge and d.rule == "surplus", f"{d.rule} {d.amps} A")

# Krap voor de klaar-tijd wint de klaar-tijd, ook op een zonnige dag.
d = ochtend_besluit(klaar=dt.datetime(2026, 8, 26, 10, 30), soc=10.0)
print(f"  klaar-tijd om 10:30 met een lege auto  {d.rule}: {d.amps} A")
controle("de klaar-tijd gaat voor", d.charge and d.rule == "deadline",
         f"{d.rule} {d.amps} A")

# En het geldt niet alleen bij een vast contract: ook met prijzen is gratis zon
# goedkoper dan het goedkoopste uur van het net.
# Vlakke prijzen, want met een goedkoop nachtuur erbij grijpt `wait-for-price`
# hierboven al in en komt deze afweging niet eens aan de beurt.
dyn = []
for u in range(48):
    start = dt.datetime(2026, 8, 26, 0, 0) + dt.timedelta(hours=u)
    dyn.append({"start": start, "end": start + dt.timedelta(hours=1),
                "price": 0.34, "feed_in": 0.05})
# Met genoeg overschot om er zelf op te laden, want onder de ondergrens van de
# paal bestaat "op de zon laden" niet.
d = ochtend_besluit(net=VOLLE_ZON, tarief=Tariff(buy=0.34, feed_in=0.05), prijzen=dyn)
print(f"  dynamisch contract  {d.rule}: {d.amps} A")
controle("ook met prijzen gaat de zon van nu er in",
         d.charge and d.amps >= 8, f"{d.rule} {d.amps} A")

print("=== 31. wachten op de zon van vandaag zonder te weten hoeveel er in moet ===")
# Gevonden door proef 21 in test_coach.py, in v0.34.0 van 25-08-2026. De poort
# `_zon_verwacht` laat een onbekende accustand er bewust doorheen: "ik weet het
# niet" is geen reden om te laden. Maar de zin eronder zette dat onbekende getal
# in de tekst, en dan valt de hele ronde om met een TypeError. In die woning had dat
# gekund op de avond van 25-08, toen zijn Ford-integratie wegviel.
d = ochtend_besluit(soc=None)
print(f"  zonder accustand  {d.rule}: {d.amps} A  {d.reason}")
controle("hij valt niet om zonder accustand", isinstance(d.reason, str), f"{d!r}")
controle(
    "en verzint geen aantal kWh dat hij niet weet",
    "er moet er" not in d.reason,
    d.reason,
)
# Met een accustand rekent hij gewoon door.
d = ochtend_besluit(soc=30.0, net=VOLLE_ZON)
controle("met accustand noemt hij de zon die er is",
         "6,0 kW zon over" in d.reason, d.reason)

print("=== 32. een klaar-tijd overdag krijgt een uur speling ===")
# De eigenaar op 26-08-2026, zijn eigen getal. Een kwartier is te krap bij een
# klaar-tijd overdag, en dat komt doordat de avondregel daar niet bij helpt:
# die zet een auto met een klaar-tijd 's nachts al om acht uur 's avonds aan,
# ruim voor het laatste moment dat nog past. Overdag is er geen avond die
# erbij hoort, en dan is dat kwartier het enige vangnet.
#
# Het is bewust geen nieuw begrip: de vraag "hoort er een avond bij" is
# dezelfde die `_evening_before` al beantwoordde.
# Sinds 04-09-2026 is het overal een uur. De eigenaar: "De eindtijd is heel
# belangrijk. Een uur daarvoor moet hij altijd klaar zijn." Daarvoor was het
# een half uur 's nachts (zijn getal van 30-08) en een uur overdag.
for uur, verwacht in ((6, 1.0), (8, 1.0), (12, 1.0), (19, 1.0), (21, 1.0), (23, 1.0)):
    eind_ = dt.datetime(2026, 8, 20, uur, 0)
    gekregen = planner._slack_hours(eind_)
    controle(f"klaar om {uur:02d}:00 krijgt {verwacht} uur speling",
             gekregen == verwacht, f"{gekregen} uur")

# En dat komt ook werkelijk in het laatste startmoment terecht.
controle("overdag begint hij een uur voor het krap wordt",
         planner._latest_start(dt.datetime(2026, 8, 20, 19, 0), 2.0)
         == dt.datetime(2026, 8, 20, 16, 0))
controle("'s nachts is het ook een uur",
         planner._latest_start(dt.datetime(2026, 8, 21, 6, 0), 2.0)
         == dt.datetime(2026, 8, 21, 3, 0))

# de eigen eis van 04-09-2026: klaar om 07:00 betekent uiterlijk 06:00 vol. Met
# een auto die er nog niets in hoeft is dat precies de speling.
controle("klaar om 07:00 betekent uiterlijk 06:00 vol",
         planner._latest_start(dt.datetime(2026, 8, 21, 7, 0), 0.0)
         == dt.datetime(2026, 8, 21, 6, 0))

# Zonder klaar-tijd valt er niets te rekenen, en dan hoort de gewone speling te
# blijven staan in plaats van dat er een uur uit de lucht komt vallen.
controle("zonder klaar-tijd blijft de gewone speling",
         planner._slack_hours(None) == planner.DEADLINE_SLACK_HOURS)

# Het vangnet voor het geval Home Assistant niet meer terugkomt hoorde volgens
# zijn eigen uitleg al af te lopen op "het laatste moment dat nog past", maar
# rekende zonder speling. Nu loopt hij gelijk met wat de coach zelf zou doen.
minuten = planner._hold_until_start(
    dt.datetime(2026, 8, 20, 12, 0), dt.datetime(2026, 8, 20, 18, 0), 2.0
)
controle("de pauze bij een onbekende accustand loopt af als de coach zou beginnen",
         minuten == 180, f"{minuten} min")

# En dan de sport zelf. De getallen zijn zo gekozen dat er 27 minuten over
# blijven: meer dan een kwartier, dus onder de oude regel ging hij overdag nog
# wachten, en minder dan een uur, dus nu grijpt de klaar-tijdregel in. Met een
# ruimere marge zou deze proef niets bewijzen, want dan valt hij allebei de
# kanten op hetzelfde uit.
# Eigen net en paal, want die van hierboven geven een ander plafond en dan
# valt de speling net buiten het bereik waar deze proef iets bewijst.
GROTE_AUTO = Car(capacity_kwh=77.0, phases=3, soc_percent=80.0)
RUIM_NET = Grid(surplus_w=0.0, phase_amps=[3.0, 2.0, 2.0], fuse_amps=25.0)
RUIME_PAAL = Charger(max_amps=16.0, connected=True, charging=False, actual_amps=0.0)
d = decide(dt.datetime(2026, 8, 20, 13, 0), [], RUIM_NET, GROTE_AUTO, RUIME_PAAL,
           Window(enabled=True, opens=None, deadline=dt.datetime(2026, 8, 20, 15, 0)),
           tariff=VAST, sun=ZON_RUIM)
print(f"  klaar om 15:00 met 27 min over  {d.rule}: {d.amps} A")
controle("overdag grijpt de klaar-tijd nu een uur eerder in",
         d.charge and d.rule == "deadline", f"{d.rule} {d.amps} A")

# Dezelfde krapte 's nachts verandert niet: daar blijft het kwartier gelden en
# staat de avondregel er al boven.
d = vast_besluit(dt.datetime(2026, 8, 20, 18, 48))
controle("'s avonds is er niets veranderd",
         not d.charge and d.rule == "wait-for-sun", d.rule)

print("=== 33. de trage meter van de paal kost geen ampere meer ===")
# de eigen meting van 20-08-2026. Hij zette snelladen aan, de coach schreef 16 A,
# de paal trok op, en de fasemeting van het huis stond al op 16 terwijl de paal
# zelf nog 2,7 A meldde. Die 13,3 A werd aan het huis toegerekend terwijl het de
# auto zelf was, en er kwam 8 A uit. Een ronde later klopte het.
#
# Goedgekeurd op 26-08-2026 met de voorwaarde erbij: repareren door af te
# trekken wat de coach zelf gevraagd heeft, nooit door de marge te verkleinen.
OPTREKKEN = Grid(surplus_w=0.0, phase_amps=[16.0, 3.0, 3.0], fuse_amps=25.0,
                 charger_amps=2.7, margin_amps=3.0)
VRAAGT_16 = Charger(max_amps=16.0, connected=True, charging=True,
                    actual_amps=2.7, limit_amps=16.0, boost=True)
LEEG = Car(capacity_kwh=77.0, phases=1, soc_percent=20.0)

controle("de coach ziet dat de meter achterloopt",
         planner.meter_loopt_achter(OPTREKKEN, VRAAGT_16))
plafond = planner.ceiling_amps(OPTREKKEN, LEEG, VRAAGT_16)
print(f"  paal meet 2,7 A terwijl L1 op 16 staat  plafond: {plafond} A")
controle("hij zakt niet meer naar 8 A", plafond == 16, f"{plafond} A")
controle("en zegt niet dat het de zekering is",
         not planner.fuse_limited(OPTREKKEN, LEEG, VRAAGT_16))

# De marge is onaangeroerd gebleven. Dat is de voorwaarde, dus die hoort
# vastgelegd te zijn en niet aangenomen.
controle("de marge is niet verkleind",
         planner.fuse_margin(OPTREKKEN) == 3.0, planner.fuse_margin(OPTREKKEN))

# De veiligheidsrail: zolang de meter achterloopt is een deel van de som een
# aanname, en daarop mag er nooit meer gevraagd worden dan er al gevraagd was.
# Hier zou de kale som 22 A toestaan; dat mag niet, want die 22 is nergens op
# gemeten.
KLEIN_GEVRAAGD = Charger(max_amps=32.0, connected=True, charging=True,
                         actual_amps=2.7, limit_amps=10.0)
plafond = planner.ceiling_amps(OPTREKKEN, Car(capacity_kwh=77.0, phases=1), KLEIN_GEVRAAGD)
print(f"  gevraagd 10 A, kale som zou 22 A geven  plafond: {plafond} A")
controle("de correctie schroeft nooit op", plafond == 10, f"{plafond} A")

# Zodra de meter bij is verandert er niets meer: dan is het weer de gewone som,
# en een huis dat werkelijk zwaarder wordt drukt het plafond gewoon omlaag.
BIJ = Grid(surplus_w=0.0, phase_amps=[16.0, 3.0, 3.0], fuse_amps=25.0,
           charger_amps=16.0, margin_amps=3.0)
MEET_16 = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=16.0,
                  limit_amps=16.0)
controle("bijgelopen meter geeft geen correctie meer",
         not planner.meter_loopt_achter(BIJ, MEET_16))
controle("en dan is het plafond weer de gewone som",
         planner.ceiling_amps(BIJ, LEEG, MEET_16) == 16)

ZWAARDER = Grid(surplus_w=0.0, phase_amps=[28.0, 3.0, 3.0], fuse_amps=25.0,
                charger_amps=16.0, margin_amps=3.0)
zakt = planner.ceiling_amps(ZWAARDER, LEEG, MEET_16)
print(f"  huis trekt er 12 A bij, paal meet mee  plafond: {zakt} A")
controle("een zwaarder huis drukt het plafond nog steeds omlaag", zakt == 10, f"{zakt} A")

# Zonder de sensor die de staande limiet teruggeeft is er niets om mee te
# vergelijken, en dan blijft het precies zoals het was. Geen stilzwijgende
# aanname bij een merk dat dit niet meldt.
GEEN_SENSOR = Charger(max_amps=16.0, connected=True, charging=True,
                      actual_amps=2.7, limit_amps=None)
controle("zonder de limietsensor verandert er niets, dus 8 A zoals op 20-08",
         planner.ceiling_amps(OPTREKKEN, LEEG, GEEN_SENSOR) == 8,
         f"{planner.ceiling_amps(OPTREKKEN, LEEG, GEEN_SENSOR)} A")

# En een paal die stilstaat trekt niet op, dus daar valt niets te corrigeren.
STILSTAAND = Charger(max_amps=16.0, connected=True, charging=False,
                     actual_amps=0.0, limit_amps=16.0)
controle("een stilstaande paal die net niets trok krijgt geen correctie",
         not planner.meter_loopt_achter(OPTREKKEN, STILSTAAND))

# En dezelfde na-ijl de andere kant op, die er niet in zat. Stopt de paal, dan
# staat zijn eigen meter meteen op nul terwijl de fasemeting van het huis zijn
# stroom nog even meedraagt. Dat werd aan het huis toegerekend, en de coach
# meldde dat de aansluiting te zwaar belast was terwijl er niets liep. Gezien bij
# de klantwoning op 29-08-2026 om 11:27:06, met de kabel er al uit: regel=no-room.
AFBOUWEND = Grid(surplus_w=0.0, phase_amps=[16.0, 3.0, 3.0], fuse_amps=25.0,
                 charger_amps=0.0, margin_amps=3.0, recent_charger_amps=16.0)
NET_GESTOPT = Charger(max_amps=16.0, connected=True, charging=False,
                      actual_amps=0.0, limit_amps=0.0)
controle("een paal die net gestopt is krijgt de correctie wel",
         planner.meter_loopt_achter(AFBOUWEND, NET_GESTOPT))
print(f"  16 A op de zwaarste fase, paal net gestopt: "
      f"plafond {planner.ceiling_amps(AFBOUWEND, LEEG, NET_GESTOPT)} A")
controle("en dan zakt het plafond niet naar nul",
         planner.ceiling_amps(AFBOUWEND, LEEG, NET_GESTOPT) > 0,
         f"{planner.ceiling_amps(AFBOUWEND, LEEG, NET_GESTOPT)} A")
controle("de aansluiting heet dan ook niet vol",
         not planner.fuse_limited(AFBOUWEND, LEEG, NET_GESTOPT))

# Maar een huis dat werkelijk zwaar belast is, blijft zwaar belast: zonder een
# paal die net stroom trok valt er niets te corrigeren.
ZWAAR_HUIS = Grid(surplus_w=0.0, phase_amps=[16.0, 3.0, 3.0], fuse_amps=25.0,
                  charger_amps=0.0, margin_amps=3.0, recent_charger_amps=0.0)
controle("een huis dat echt vol zit wordt niet weggepoetst",
         planner.ceiling_amps(ZWAAR_HUIS, LEEG, NET_GESTOPT) == 6,
         f"{planner.ceiling_amps(ZWAAR_HUIS, LEEG, NET_GESTOPT)} A")

print()
print("=== het aantal fasen staat vast en wordt niet meer aangenomen ===")
# De bus van de klantwoning, 29-08-2026: 65 kWh, 12,5% vol, aan een paal van 16 A.
# Zolang de keuze "allebei" bestond rekende deze som met een fase, want een auto
# die kan wisselen verraadt zich pas als hij laadt. Dat gaf 17,2 uur, waarna de
# klaar-tijdregel om 11:13 aansloeg en de coach op 16 A van het net laadde
# terwijl er zon lag. Driefasig is het 5,7 uur en had hij tot 01:07 de tijd.
BUS_3F = Car(capacity_kwh=65.0, phases=3, soc_percent=12.5)
BUS_1F = Car(capacity_kwh=65.0, phases=1, soc_percent=12.5)
drie = planner.hours_needed(BUS_3F, 16)
een = planner.hours_needed(BUS_1F, 16)
print(f"  65 kWh op 12,5%, 16 A: driefasig {drie:.2f} uur, eenfasig {een:.2f} uur")
controle("driefasig rekent met drie fasen", abs(drie - 5.72) < 0.01, f"{drie}")
controle("eenfasig met een", abs(een - 17.17) < 0.01, f"{een}")
controle("en dat scheelt precies een factor drie", abs(een / drie - 3.0) < 1e-6,
         f"{een / drie}")

# En de ondergrens van de zonregel hangt aan hetzelfde getal: driefasig kan niet
# onder de 4,1 kW beginnen. De eigenaar op 29-08-2026, gevraagd en akkoord: "het is niet
# erg dan 3 fase op ongeveer 4 kW laden, we moeten gebruikmaken van de zon."
controle("driefasig begint pas bij 4.140 W overschot",
         planner.watts_for(planner.MIN_AMPS, 3) == 4140.0,
         f"{planner.watts_for(planner.MIN_AMPS, 3)}")
controle("en eenfasig al bij 1.380 W",
         planner.watts_for(planner.MIN_AMPS, 1) == 1380.0,
         f"{planner.watts_for(planner.MIN_AMPS, 1)}")

print("=== 34. een volle aansluiting zet een lopende beurt niet meer uit ===")
# In de klantwoning meldde de huismeter op 30-08-2026 om 04:28:56 een enkel sample
# van 27 A op L3. De coach schreef 0 A, de paal stond achtenzeventig seconden
# uit, en de Ford beeindigde zijn laadbeurt en kwam er die hele dag niet meer
# uit: om 09:37 stond de auto nog op 69,5%.
#
# De marge is comfort en geen natuurkunde. Een beurt afbreken om die marge te
# sparen kost meer dan hij oplevert, dus zolang `MIN_AMPS` er ook zonder marge
# nog bij past laadt hij door op de laagste stand. De grens zelf blijft heilig.
nu34 = middag(4, 28)
KRAP = Grid(surplus_w=0.0, phase_amps=[3.0, 3.0, 30.0], fuse_amps=25.0,
            charger_amps=12.0, margin_amps=3.0)
LAADT = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=12.0,
                started_at=middag(3, 0), limit_amps=12.0)
print(f"  huis 18 A eigen last: plafond {planner.ceiling_amps(KRAP, LEEG, LAADT)} A, "
      f"zonder marge {planner.nood_ruimte(KRAP, LAADT):.0f} A")
controle("onder de marge past er niets meer",
         planner.ceiling_amps(KRAP, LEEG, LAADT) < MIN_AMPS,
         f"{planner.ceiling_amps(KRAP, LEEG, LAADT)}")
controle("zonder de marge nog wel",
         planner.nood_ruimte(KRAP, LAADT) >= MIN_AMPS,
         f"{planner.nood_ruimte(KRAP, LAADT)}")

krap = decide(nu34, [], KRAP, LEEG, LAADT, venster(nu34), tariff=VAST, sun=ZON_KRAP)
print(f"  {krap.rule}: laden={krap.charge} {krap.amps} A  {krap.reason}")
controle("dus hij blijft laden op de laagste stand",
         krap.charge and krap.amps == MIN_AMPS, f"{krap.rule} {krap.amps}")
controle("met een eigen regel, zodat het logboek het verschil laat zien",
         krap.rule == "tight", f"{krap.rule}")

# Maar een huis dat er zelf overheen gaat wint nog steeds: 22 A eigen last plus
# zes ampere past niet onder 25.
VOL = Grid(surplus_w=0.0, phase_amps=[3.0, 3.0, 34.0], fuse_amps=25.0,
           charger_amps=12.0, margin_amps=3.0)
vol = decide(nu34, [], VOL, LEEG, LAADT, venster(nu34), tariff=VAST, sun=ZON_KRAP)
print(f"  huis 22 A eigen last: {vol.rule}: {vol.amps} A")
controle("een huis dat er zelf overheen gaat zet hem wel uit",
         not vol.charge and vol.amps == 0, f"{vol.rule} {vol.amps}")
controle("en heet dan gewoon no-room", vol.rule == "no-room", f"{vol.rule}")

# En een paal die nog niet laadt begint er niet aan. De uitzondering gaat over
# een auto die je niet wilt laten stoppen, niet over een auto die stilstaat.
STAAT_STIL = Charger(max_amps=16.0, connected=True, charging=False,
                     actual_amps=0.05, limit_amps=0.0)
stil = decide(nu34, [], KRAP, LEEG, STAAT_STIL, venster(nu34), tariff=VAST, sun=ZON_KRAP)
print(f"  paal die stilstaat: {stil.rule}: {stil.amps} A")
controle("een paal die stilstaat begint er niet aan", not stil.charge,
         f"{stil.rule} {stil.amps}")

print("=== 35. wat de lastbewaker vrijgeeft is een restwaarde, geen tweede zekering ===")
# Nagemeten in de klantwoning met `sensor.1_equalizer_limiet`. Op 29-08-2026 om
# 16:50 meldde die 18 A terwijl de paal 15 A trok en het huis er zelf ongeveer 5
# bijhad; om 17:20 met een leeg huis stond hij op 20. Het getal beweegt dus mee
# met het huis, en de paal zelf telt er niet in mee.
#
# v0.44.0 behandelde dit als een tweede zekering en trok het huisverbruik er
# daarmee twee keer vanaf. Het is een eigen plafond naast de som over de fasen.
RUSTIG = Grid(surplus_w=0.0, phase_amps=[1.0, 2.0, 10.0], fuse_amps=25.0,
              charger_amps=0.0, margin_amps=3.0)
MET_BEWAKER = Grid(surplus_w=0.0, phase_amps=[1.0, 2.0, 10.0], fuse_amps=25.0,
                   charger_amps=0.0, margin_amps=3.0, balancer_amps=8.0)
STAAT_STIL = Charger(max_amps=16.0, connected=True, charging=False,
                     actual_amps=0.05, limit_amps=0.0)
zonder = planner.ceiling_amps(RUSTIG, LEEG, STAAT_STIL)
met = planner.ceiling_amps(MET_BEWAKER, LEEG, STAAT_STIL)
print(f"  huis 10 A op de zwaarste fase: zonder bewaker {zonder} A, met een die 8 vrijgeeft {met} A")
controle("zonder bewakersensor verandert er niets", zonder == 12, f"{zonder}")
controle("wat de bewaker vrijgeeft is het plafond", met == 8, f"{met}")

# En het huisverbruik gaat er niet nog eens vanaf. Dat was de fout: 8 min 10 min
# marge is niets, en dan had de coach hier helemaal niet meer geladen.
controle("het huisverbruik wordt niet twee keer afgetrokken", met >= planner.MIN_AMPS,
         f"{met}")

# Geeft de bewaker meer vrij dan er onder de zekering past, dan blijft de eigen
# som van de coach leidend. De laagste van alle plafonds wint, zoals altijd.
RUIM = Grid(surplus_w=0.0, phase_amps=[1.0, 2.0, 10.0], fuse_amps=25.0,
            charger_amps=0.0, margin_amps=3.0, balancer_amps=40.0)
controle("een bewaker die ruim vrijgeeft verandert niets",
         planner.ceiling_amps(RUIM, LEEG, STAAT_STIL) == 12,
         f"{planner.ceiling_amps(RUIM, LEEG, STAAT_STIL)}")

# En de marge onder de zekering hangt aan de zekering en niet aan de bewaker:
# die twee gaan over verschillende dingen.
GROOT = Grid(surplus_w=0.0, phase_amps=[10.0], fuse_amps=80.0, charger_amps=0.0,
             margin_amps=3.0, balancer_amps=10.0)
controle("de marge blijft over de zekering rekenen",
         abs(planner.fuse_margin(GROOT) - 6.4) < 1e-9, f"{planner.fuse_margin(GROOT)}")

# Zegt de bewaker dat er niets meer in kan, dan valt er ook niets aan te houden:
# dan is `tight` niet aan de orde en gaat de paal gewoon uit.
DICHT = Grid(surplus_w=0.0, phase_amps=[3.0, 3.0, 30.0], fuse_amps=25.0,
             charger_amps=12.0, margin_amps=3.0, balancer_amps=2.0)
LAADT_NOG = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=12.0,
                    started_at=middag(3, 0), limit_amps=12.0)
nu35 = middag(4, 28)
dicht = decide(nu35, [], DICHT, LEEG, LAADT_NOG, venster(nu35), tariff=VAST, sun=ZON_KRAP)
print(f"  bewaker geeft 2 A vrij: {dicht.rule}: {dicht.amps} A")
controle("een bewaker die niets vrijgeeft houdt hem niet op de laagste stand",
         not dicht.charge, f"{dicht.rule} {dicht.amps}")


print("=== 36. de tijdlijn tot de auto vol moet zijn ===")
# De eigenaar op 30-08-2026: "ik wil zien wat de coach van plan is met hele tijdlijn tot
# dat hij vol moet zijn." De opzet hieronder is zijn eigen nacht van 29 op 30
# augustus: een bus van 65 kWh op 48,5%, driefasig, klaar om 07:00, met de
# echte prijzen van die nacht.
NACHT = [
    (20, 0.3563), (21, 0.3350), (22, 0.3106), (23, 0.2811),
    (0, 0.2599), (1, 0.2451), (2, 0.2333), (3, 0.2215),
    (4, 0.2113), (5, 0.2154), (6, 0.2155),
]
prijzen36 = []
for uur, prijs in NACHT:
    dag = 29 if uur >= 20 else 30
    start = dt.datetime(2026, 8, dag, uur, 0)
    prijzen36.append({"start": start, "end": start + dt.timedelta(hours=1), "price": prijs})

BUS = Car(capacity_kwh=65.0, phases=3, soc_percent=48.5)
PAAL36 = Charger(max_amps=16.0, connected=True, charging=False, actual_amps=0.05,
                 limit_amps=0.0)
VENSTER36 = Window(enabled=True, opens=None, deadline=dt.datetime(2026, 8, 30, 7, 0))
nu36 = dt.datetime(2026, 8, 29, 20, 30)

plan36 = planner.timeline(nu36, prijzen36, NET_LEEG, BUS, PAAL36, VENSTER36, 16)
print(f"  nog {plan36.kwh_needed:.1f} kWh, {plan36.hours_needed:.2f} uur op "
      f"{plan36.amps} A, uiterlijk beginnen {plan36.latest_start:%H:%M}, "
      f"vol rond {plan36.expected_done:%H:%M}")
for blok in plan36.blocks:
    print(f"    {blok.start:%H:%M}  {blok.price:.4f}  "
          f"{'laden ' if blok.charging else '      '} {blok.why}")

controle("hij weet hoeveel er nog in moet", abs(plan36.kwh_needed - 37.2) < 0.5,
         f"{plan36.kwh_needed}")
controle("en hoe lang dat duurt", abs(plan36.hours_needed - 3.37) < 0.05,
         f"{plan36.hours_needed}")

# Vier uur nodig, dus de vier goedkoopste vóór 06:00, want het plan eindigt
# een uur vóór de klaar-tijd (de eigenaar, 04-09-2026): 02, 03, 04 en 05.
laadt = [blok.start.hour for blok in plan36.blocks if blok.charging]
print(f"  laadt in de uren: {laadt}")
controle("hij pakt de vier goedkoopste uren voor de klaar-tijd",
         laadt == [2, 3, 4, 5], f"{laadt}")
controle("en slaat de dure avond over",
         not any(blok.charging for blok in plan36.blocks if blok.start.hour >= 20),
         f"{[b.start.hour for b in plan36.blocks if b.charging]}")

# De speling van een uur zit erin: 07:00 min 3,37 uur laden min een uur is
# 02:37.
controle("uiterlijk beginnen heeft de speling er al af",
         abs((plan36.latest_start - dt.datetime(2026, 8, 30, 2, 37)).total_seconds()) < 60,
         f"{plan36.latest_start}")
controle("en hij verwacht vol te zijn voor de klaar-tijd",
         plan36.expected_done <= plan36.deadline, f"{plan36.expected_done}")

# De tijdlijn moet hetzelfde zeggen als het besluit van dat moment, anders gaat
# de bewoner op het verkeerde wachten. Om 20:30 wacht de coach, om 03:30 laadt
# hij, en de tijdlijn hoort dat allebei te weten.
besluit36 = decide(nu36, prijzen36, NET_LEEG, BUS, PAAL36, VENSTER36,
                   tariff=VAST, sun=ZON_KRAP)
nu36b = dt.datetime(2026, 8, 30, 3, 30)
besluit36b = decide(nu36b, prijzen36, NET_LEEG, BUS, PAAL36, VENSTER36,
                    tariff=VAST, sun=ZON_KRAP)
plan36b = planner.timeline(nu36b, prijzen36, NET_LEEG, BUS, PAAL36, VENSTER36, 16)
nu_blok = [blok for blok in plan36b.blocks if blok.start.hour == 3]
nu_blok20 = [blok for blok in plan36.blocks if blok.start.hour == 20]
print(f"  om 20:30: {besluit36.rule} laden={besluit36.charge};  "
      f"om 03:30: {besluit36b.rule} laden={besluit36b.charge}")
# Waar het om gaat is niet welke regel het wordt maar of de tijdlijn en het
# besluit het eens zijn over laden of niet. Om 03:30 is de coach al voorbij zijn
# uiterste startmoment, dus dan wint de klaar-tijdregel van de prijsregel; de
# tijdlijn hoort daar hetzelfde te zeggen.
controle("om 20:30 zegt de tijdlijn hetzelfde als het besluit",
         nu_blok20 and nu_blok20[0].charging == besluit36.charge,
         f"{besluit36.rule} / {nu_blok20}")
controle("en om 03:30 ook",
         nu_blok and nu_blok[0].charging == besluit36b.charge,
         f"{besluit36b.rule} / {nu_blok}")

# Een uur dat al voorbij is hoort er niet meer in te staan.
controle("voorbije uren staan er niet meer in",
         all(blok.end > nu36b for blok in plan36b.blocks),
         f"{[b.start.hour for b in plan36b.blocks]}")

# Een begintijd knipt de uren ervoor eruit, en dat hoort er te staan in plaats
# van dat ze zomaar ontbreken.
VENSTER36C = Window(enabled=True, opens=dt.datetime(2026, 8, 30, 1, 0),
                    deadline=dt.datetime(2026, 8, 30, 7, 0))
plan36c = planner.timeline(nu36, prijzen36, NET_LEEG, BUS, PAAL36, VENSTER36C, 16)
vroeg = [blok for blok in plan36c.blocks if blok.start.hour in (21, 22, 23, 0)]
print(f"  met een begintijd van 01:00: {vroeg[0].why if vroeg else 'geen'}")
controle("uren voor de begintijd staan erin met hun reden",
         vroeg and all(b.why == "voor je begintijd" and not b.charging for b in vroeg),
         f"{[(b.start.hour, b.why) for b in vroeg]}")

# Zonder accustand valt er niets te rekenen, en dan zegt hij dat in plaats van
# een tijdlijn te verzinnen.
GEEN_SOC = Car(capacity_kwh=65.0, phases=3, soc_percent=None)
plan36d = planner.timeline(nu36, prijzen36, NET_LEEG, GEEN_SOC, PAAL36, VENSTER36, 16)
print(f"  zonder accustand: {plan36d.note}")
controle("zonder accustand zegt hij waarom de lijst zo lang is",
         "accustand" in plan36d.note, f"{plan36d.note}")

# En bij een vast contract staat er sinds 30-08-2026 ook een tijdlijn. Elk uur
# kost hetzelfde, dus wat er te kiezen valt is wannéér, en dat is precies wat de
# lijst laat zien.
plan36e = planner.timeline(nu36, [], NET_LEEG, BUS, PAAL36, VENSTER36, 16, VAST)
uren36e = [blok for blok in plan36e.blocks if blok.charging]
print(f"  vast tarief: {len(plan36e.blocks)} uren, laadt in "
      f"{[b.start.hour for b in uren36e]}")
controle("bij een vast tarief staat er ook een tijdlijn", bool(plan36e.blocks),
         f"{plan36e.note}")
controle("en alle uren kosten hetzelfde",
         len({round(b.price, 6) for b in plan36e.blocks}) == 1,
         f"{ {b.price for b in plan36e.blocks} }")
controle("en de sommen staan er nog steeds",
         plan36e.hours_needed is not None and plan36e.latest_start is not None,
         f"{plan36e}")

# Wat er gepland staat hoort het tekort te dekken, anders is "vol rond" geen
# belofte. In de klantwoning stond op 04-09-2026 "Vol rond 17:00" boven acht
# zonblokken van samen 33 van de 66 kWh: de prijzen tot zondag 06:00 waren er
# nog niet, dus alleen zon. De eigenaar las het als een belofte. Het plan telt sinds
# v0.47.3 mee wat het gepland heeft, en zegt of dat alleen zon is.
controle("het volledige plan dekt wat er nog in moet",
         abs(plan36.planned_kwh - plan36.kwh_needed) < 0.1,
         f"{plan36.planned_kwh} van {plan36.kwh_needed}")
controle("en is dan niet alleen zon", not plan36.solar_only)
# De prijzen lopen tot zondagavond, de klaar-tijd is maandag 07:00. Met een
# terugleverprijs erbij, want zonder die valt er niets te mengen en bestaat er
# geen zonschijf.
# Alle bekende uren even duur, want sinds 05-09-2026 mag een bekend uur dat
# goedkoper is dan het gemiddelde wél meedoen (zie proef 46); hier gaat het
# om de vloer-uren, en die bestaan alleen als er geen goedkoop netuur is.
prijzen36f = [dict(rij, price=0.25, feed_in=0.02) for rij in prijzen36]
for uur in range(7, 24):
    start = dt.datetime(2026, 8, 30, uur, 0)
    prijzen36f.append({"start": start, "end": start + dt.timedelta(hours=1),
                       "price": 0.25, "feed_in": 0.02})
VENSTER36F = Window(enabled=True, opens=None, deadline=dt.datetime(2026, 8, 31, 7, 0))
plan36f = planner.timeline(nu36, prijzen36f, NET_LEEG, BUS, PAAL36, VENSTER36F, 16,
                           forecast=kromme(dt.datetime(2026, 8, 30), 9,
                                           [1.0, 3.0, 5.0, 5.0, 4.0, 2.0]))
uren36f = [b.start.hour for b in plan36f.blocks if b.charging]
print(f"  klaar-tijd voorbij de prijzen: {plan36f.planned_kwh:.1f} van "
      f"{plan36f.kwh_needed:.1f} kWh gepland, in {uren36f}")
controle("reiken de prijzen niet tot de klaar-tijd, dan is het plan alleen zon",
         plan36f.solar_only, f"{plan36f.note}")
controle("en dekt het minder dan het tekort",
         0 < plan36f.planned_kwh < plan36f.kwh_needed - 1,
         f"{plan36f.planned_kwh} van {plan36f.kwh_needed}")
controle("terwijl expected_done wel het einde van het laatste zonuur is",
         plan36f.expected_done is not None and plan36f.expected_done.hour == max(uren36f) + 1,
         f"{plan36f.expected_done}")

# De eigenaar op 04-09-2026, over een rij "4,1 kWh zon" bij een dak van 2,4 kWh: "dat
# weet je toch niet. Laat sowieso zien hoeveel ampère hij laadt en kW." Het
# zonaandeel is wat het dak geeft, het totaal is wat er in de auto gaat, en
# de stroom en het vermogen staan erbij.
laadt36f = [b for b in plan36f.blocks if b.charging]
for b in laadt36f:
    print(f"    {b.start:%H:%M}  {b.solar_kwh:.1f} zon van {b.kwh:.1f} kWh  "
          f"{b.amps} A  {b.kw:.1f} kW  {b.why}")
vloer36f = [b for b in laadt36f if b.solar_kwh + 0.05 < b.kwh]
controle("in een vloer-uur is het zonaandeel kleiner dan wat er in gaat",
         vloer36f and all(0 < b.solar_kwh < b.kwh for b in vloer36f),
         f"{[(b.solar_kwh, b.kwh) for b in laadt36f]}")
# Het uur van 09:00 met 1,0 kWh zon valt sinds 17-09-2026 af: dat is 24% van de
# 4,14 kWh die er in dat uur in gaat, net onder `ZON_AANDEEL`. Wat de controle
# meet blijft hetzelfde: in een vloer-uur staat er hoeveel het dák geeft (3,0)
# en niet hoeveel de paal laadt (4,1).
controle("en het zonaandeel is wat het dak geeft, niet de vloer",
         any(abs(b.solar_kwh - 3.0) < 0.05 for b in laadt36f),
         f"{[round(b.solar_kwh, 2) for b in laadt36f]}")
controle("een uur dat voor minder dan een kwart op zon draait is geen zonuur",
         not any(b.start.hour == 9 for b in laadt36f),
         f"{[b.start.hour for b in laadt36f]}")
controle("een vloer-uur is 6 A op driefasig 4,1 kW",
         all(b.amps == MIN_AMPS and abs(b.kw - 4.14) < 0.05 for b in vloer36f),
         f"{[(b.amps, b.kw) for b in vloer36f]}")
controle("en zegt dat het aangevuld wordt",
         all("aangevuld" in b.why for b in vloer36f), f"{[b.why for b in vloer36f]}")
zon36f = [b for b in laadt36f if b.solar_kwh + 0.05 >= b.kwh]
controle("een echt zonuur laadt op wat het dak geeft en zegt dat",
         zon36f and all(b.amps >= MIN_AMPS and "eigen zon" in b.why for b in zon36f),
         f"{[(b.amps, b.why) for b in zon36f]}")
controle("een wachtuur heeft geen stroom",
         all(b.amps == 0 and b.kw == 0 for b in plan36f.blocks if not b.charging))

# In de klantwoning op 04-09-2026 om 21:21 trok fase 3 zestien ampère door het
# huis, en de kop zei "op vol vermogen 15 u 58 m op 6 A, uiterlijk beginnen
# zaterdag 13:02". De klaar-tijdregel rekent met wat paal en auto kunnen, en
# de kop hoort hetzelfde te zeggen. Het uur van nu houdt wel het plafond van nu.
plan36g = planner.timeline(nu36, prijzen36, NET_LEEG, BUS, PAAL36, VENSTER36, 6)
print(f"  krap plafond van nu (6 A): kop {plan36g.amps} A, {plan36g.hours_needed:.2f} uur, "
      f"uiterlijk {plan36g.latest_start:%H:%M}")
controle("de kop rekent met wat paal en auto kunnen, niet met dit moment",
         plan36g.amps == 16 and abs(plan36g.hours_needed - plan36.hours_needed) < 0.01,
         f"{plan36g.amps} A, {plan36g.hours_needed}")
controle("dus uiterlijk beginnen verschuift niet door een piek in het huis",
         plan36g.latest_start == plan36.latest_start, f"{plan36g.latest_start}")

print("=== 37. twee getallen uit twee momenten in een zin ===")
# De eigenaar op 30-08-2026, tijdens het herstarten: "de equalizer staat op 18 A maar
# de coach zegt dat de lastbewaking op 7 A zit?" Allebei waar en toch onzin. De
# 7 was de gemeten stroom van dat moment; de reden `limited_by_equalizer` kwam
# van `sensor.1_reden_geen_stroom`, en die was op dat moment vijf minuten oud.
# De Easee meldt zijn sensoren niet allemaal tegelijk.
nu37 = middag(12, 10)
KNIJPT = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=7.3,
                 started_at=middag(11, 0), limit_amps=10.0,
                 no_current_reason="limited_by_equalizer")
NET37 = Grid(surplus_w=0.0, phase_amps=[5.0, 6.0, 10.0], fuse_amps=25.0,
             charger_amps=7.3, margin_amps=3.0)

# Zonder de sensor van de bewaker is de gemeten stroom het enige dat er is, en
# dan blijft het zoals het was.
zonder37 = decide(nu37, [], NET37, LEEG, KNIJPT, venster(nu37), tariff=VAST, sun=ZON_RUIM)
print(f"  zonder bewakersensor: {zonder37.rule}: {zonder37.reason}")
controle("zonder bewakersensor blijft de melding staan",
         zonder37.rule.endswith("+held-back"), f"{zonder37.rule}")

# Maar zegt de bewaker zelf dat hij 18 A vrijgeeft terwijl de coach er 10 vraagt,
# dan kan hij niet degene zijn die knijpt.
RUIM37 = Grid(surplus_w=0.0, phase_amps=[5.0, 6.0, 10.0], fuse_amps=25.0,
              charger_amps=7.3, margin_amps=3.0, balancer_amps=18.0)
ruim37 = decide(nu37, [], RUIM37, LEEG, KNIJPT, venster(nu37), tariff=VAST, sun=ZON_RUIM)
print(f"  bewaker geeft 18 A vrij: {ruim37.rule}: {ruim37.reason}")
controle("een bewaker die ruim vrijgeeft krijgt de schuld niet",
         not ruim37.rule.endswith("+held-back"), f"{ruim37.rule}")
controle("en er staat geen getal in dat van een ander moment komt",
         "7 A" not in ruim37.reason, f"{ruim37.reason}")

# Een groep die vol zit is iets anders dan de bewaker, en daar zegt die sensor
# niets over. Die melding blijft dus gewoon staan.
GROEP = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=7.3,
                started_at=middag(11, 0), limit_amps=10.0,
                no_current_reason="limited_by_circuit_fuse")
groep37 = decide(nu37, [], RUIM37, LEEG, GROEP, venster(nu37), tariff=VAST, sun=ZON_RUIM)
print(f"  groep vol, bewaker ruim: {groep37.rule}")
controle("een volle groep wordt nog steeds gemeld",
         groep37.rule.endswith("+held-back"), f"{groep37.rule}")

# En met de sensor erbij is de bewaker sowieso geen verrassing meer: de coach
# vraagt nooit meer dan er vrij is, dus knijpt hij ook nooit meer. Dat is precies
# waar die sensor voor is. Wat er dan overblijft is een paal die minder trekt dan
# er gevraagd is, en daar heeft de bewaker geen schuld aan.
KRAP37 = Grid(surplus_w=0.0, phase_amps=[5.0, 6.0, 10.0], fuse_amps=25.0,
              charger_amps=7.3, margin_amps=3.0, balancer_amps=8.0)
krap37 = decide(nu37, [], KRAP37, LEEG, KNIJPT, venster(nu37), tariff=VAST, sun=ZON_RUIM)
print(f"  bewaker geeft 8 A vrij: {krap37.rule}: {krap37.amps} A")
controle("de coach vraagt niet meer dan de bewaker vrijgeeft",
         krap37.amps <= 8, f"{krap37.amps}")
controle("en geeft de bewaker dus ook de schuld niet",
         not krap37.rule.endswith("+held-back"), f"{krap37.rule}")

print("=== 38. een lopende beurt stopt niet voor een verschil dat er niet is ===")
# Gezien in de klantwoning op 30-08-2026, met zijn eigen prijzen. Om 12:05 stond de
# accu op 70% en waren er drie uur nodig: 12, 13 en 14 uur zaten in de lijst en
# hij begon te laden. Tien minuten later stond hij op 72%, waren er nog maar twee
# uur nodig, en viel het uur van dat moment eruit. Verschil met het duurste uur
# dat er nog wel in stond: 0,1281 tegen 0,1278.
MIDDAG = [(30, 12, 0.1281), (30, 13, 0.1277), (30, 14, 0.1278), (30, 15, 0.1288),
          (30, 16, 0.1296), (30, 17, 0.1976), (30, 18, 0.3190), (30, 19, 0.3517),
          (30, 23, 0.2600), (31, 3, 0.1500), (31, 4, 0.1450), (31, 5, 0.1480)]
prijzen38 = []
for dag, uur, prijs in MIDDAG:
    start = dt.datetime(2026, 8, dag, uur, 0)
    prijzen38.append({"start": start, "end": start + dt.timedelta(hours=1), "price": prijs})

BUS38 = Car(capacity_kwh=65.0, phases=3, soc_percent=72.0)
VENSTER38 = Window(enabled=True, opens=None, deadline=dt.datetime(2026, 8, 31, 7, 0))
nu38 = dt.datetime(2026, 8, 30, 12, 15)
NET38 = Grid(surplus_w=0.0, phase_amps=[5.0, 6.0, 7.0], fuse_amps=25.0, charger_amps=6.3)

LAADT38 = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=6.3,
                  started_at=dt.datetime(2026, 8, 30, 12, 5), limit_amps=6.0)
loopt = decide(nu38, prijzen38, NET38, BUS38, LAADT38, VENSTER38,
               tariff=VAST, sun=ZON_KRAP)
print(f"  paal laadt al: {loopt.rule}: {loopt.charge} {loopt.amps} A")
print(f"    {loopt.reason}")
controle("een lopende beurt gaat door op een uur dat niets duurder is",
         loopt.charge, f"{loopt.rule} {loopt.amps}")
controle("en zegt waarom", "scheelt niets" in loopt.reason, f"{loopt.reason}")

# Maar hij begint er niet aan. Starten kost niets, dus daar mag de prijs gewoon
# de doorslag geven.
STAAT_STIL38 = Charger(max_amps=16.0, connected=True, charging=False,
                       actual_amps=0.05, limit_amps=0.0)
stil38 = decide(nu38, prijzen38, NET38, BUS38, STAAT_STIL38, VENSTER38,
                tariff=VAST, sun=ZON_KRAP)
print(f"  paal staat stil: {stil38.rule}: {stil38.charge}")
controle("maar een paal die stilstaat begint er niet aan",
         not stil38.charge, f"{stil38.rule}")

# En een uur dat werkelijk duurder is stopt hem nog steeds. Dat is het deelladen
# dat op 29-08 voor het eerst in het echt gezien is: een deel rond de goedkope
# middagprijzen, stoppen zodra het duur wordt, de rest 's nachts.
# De paal loopt dan al ruim langer dan `MIN_RUN_MINUTES` en de hysterese is op,
# anders zou die hem alsnog even aanhouden en meet de proef iets anders.
nu38b = dt.datetime(2026, 8, 30, 17, 15)
LAADT38B = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=13.0,
                   started_at=dt.datetime(2026, 8, 30, 16, 0), limit_amps=16.0)
duur = decide(nu38b, prijzen38, NET38, BUS38, LAADT38B, VENSTER38,
              tariff=VAST, sun=ZON_KRAP, holding=planner.STOP_ROUNDS)
print(f"  om 17:00 op 0,1976 tegen 0,145 's nachts: {duur.rule}: {duur.charge}")
controle("een uur dat werkelijk duurder is stopt hem wel",
         not duur.charge, f"{duur.rule} {duur.amps}")

# De grens is dezelfde als waarmee de zonregel al werkt, en die is klein: een
# cent per kWh is wel een reden om te stoppen.
CENT = [dict(rij) for rij in prijzen38]
CENT[0]["price"] = 0.1378
LANG38 = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=6.3,
                 started_at=dt.datetime(2026, 8, 30, 11, 0), limit_amps=6.0)
merkbaar = decide(nu38, CENT, NET38, BUS38, LANG38, VENSTER38,
                  tariff=VAST, sun=ZON_KRAP, holding=planner.STOP_ROUNDS)
print(f"  een cent duurder: {merkbaar.rule}: {merkbaar.charge}")
controle("een cent duurder is wel een reden om te stoppen",
         not merkbaar.charge, f"{merkbaar.rule}")

print("=== 39. de coach zegt niet dat je teruglevert terwijl je inkoopt ===")
# De eigenaar op 30-08-2026: "de coach zegt je levert nu 0,7 kW terug maar ik lever
# helemaal niks terug." Hij had gelijk, en de meter ook.
#
# De rauwe getallen van dat moment, om 13:11:46 in de klantwoning:
#
#   afname          3.683 W
#   teruglevering       0 W
#   zon             1.157 W
#   laadpaal        4.338 W
#
# Het overschot dat de coach gebruikt is 0 - 3683 + 4338 = 655 W. Dat is wat er
# teruggeleverd zou worden als de paal uit stond, en dat getal is met opzet zo:
# zonder de paal eruit te rekenen ziet de coach zijn eigen laden aan voor
# huisverbruik en praat hij zichzelf uit zijn eigen zon. Zie `_read` in coach.py.
#
# Maar dan mag er niet "je levert 0,7 kW terug" op de kaart staan, want dat is
# iets anders dan er gebeurt.
nu39 = middag(13, 11)
NET39 = Grid(surplus_w=655.0, phase_amps=[5.0, 6.0, 6.0], fuse_amps=25.0,
             charger_amps=6.3)
LAADT39 = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=6.3,
                  started_at=middag(13, 0), limit_amps=6.0)
prijzen39 = []
for uur, prijs in ((13, 0.1277), (14, 0.1278), (15, 0.1288), (16, 0.1296),
                   (17, 0.1976), (18, 0.3190)):
    start = dt.datetime(2026, 8, 18, uur, 0)
    prijzen39.append({"start": start, "end": start + dt.timedelta(hours=1),
                      "price": prijs, "feed_in": prijs - 0.0242})

# Met dit uur duur en de nacht goedkoop pakt de vergelijking alleen de zon van
# nu, en dat is de zin waar het hier om gaat.
DUUR39 = [dict(rij, price=0.40, feed_in=0.05) if rij["start"].hour == 13 else rij
          for rij in prijzen39]
BUS39 = Car(capacity_kwh=65.0, phases=3, soc_percent=76.5)
RUIM39 = Grid(surplus_w=5000.0, phase_amps=[5.0, 6.0, 6.0], fuse_amps=25.0,
              charger_amps=6.3)
d39 = decide(nu39, DUUR39, RUIM39, BUS39, LAADT39, venster(nu39),
             tariff=VAST, sun=ZON_KRAP, holding=planner.STOP_ROUNDS)
print(f"  {d39.rule}: {d39.reason}")
controle("hij zegt dat er zon over is", "zon over" in d39.reason, f"{d39.reason}")
controle("en niet dat je teruglevert terwijl je inkoopt",
         "levert" not in d39.reason, f"{d39.reason}")

# En met te weinig zon om zelf op te laden is het nog steeds dezelfde zin, want
# het is nog steeds hetzelfde getal. Dan zit het bijkopen in de prijs: 0,7 kW
# zon a 0,02 plus 3,5 kW net a 0,30 is 0,256 per kWh. Dit uur is dus te duur om
# vol te laden (0,30 tegen 0,28 straks) en tegelijk goedkoop genoeg om er op de
# ondergrens doorheen te gaan, want die 0,7 kW is straks weg.
# De lijst loopt door tot de klaar-tijd, want sinds 04-09-2026 komt er zonder
# de prijzen tot een uur voor de klaar-tijd alleen zon in, en dus ook geen
# bijmenging tot de ondergrens.
VLOER39 = []
for stap in range(17):
    start = dt.datetime(2026, 8, 18, 13, 0) + dt.timedelta(hours=stap)
    VLOER39.append({"start": start, "end": start + dt.timedelta(hours=1),
                    "price": 0.30 if stap == 0 else 0.28, "feed_in": 0.02})
d39b = decide(nu39, VLOER39, NET39, BUS39, LAADT39, venster(nu39),
              tariff=VAST, sun=ZON_KRAP, holding=planner.STOP_ROUNDS)
print(f"  met 0,7 kW over: {d39b.rule}: {d39b.amps} A  {d39b.reason}")
controle("ook onder de ondergrens van de paal", "zon over" in d39b.reason
         and "levert" not in d39b.reason, f"{d39b.reason}")
controle("en dan op de ondergrens", d39b.amps == MIN_AMPS, f"{d39b.amps} A")

print("=== 40. alle scenario's tegen elkaar, met de klantwoning zijn eigen cijfers ===")
# De eigenaar op 30-08-2026: "lage kosten en zoveel mogelijk zon moet uit de strategie.
# Het eindoel is altijd lage kosten. Dus alle scenario's moeten vergeleken worden
# met elkaar: lage prijs met zon, hoge prijs met zon, laden op een later tijdstip
# als de prijs gunstiger is. Belangrijk is kijken naar forecast."
#
# De prijzen en de zonverwachting hieronder zijn die van zijn installatie op
# 30-08-2026 om 13:30, uit `sensor.current_electricity_price_all_in` en uit de
# uurkromme van het energiedashboard. Het huisverbruik is de mediaan over drie
# dagen uit zijn eigen meters.
MIDDAG40 = [
    (13, 0.1277, 2.47), (14, 0.1278, 2.38), (15, 0.1288, 1.83), (16, 0.1296, 1.55),
    (17, 0.1976, 1.28), (18, 0.3190, 0.96), (19, 0.3517, 0.59), (20, 0.3629, 0.31),
    (21, 0.3626, 0.0), (22, 0.3486, 0.0), (23, 0.3323, 0.0),
]
NACHT40 = [
    (0, 0.3384), (1, 0.3197), (2, 0.3017), (3, 0.2870), (4, 0.2801),
    (5, 0.2842), (6, 0.3106),
]
OPSLAG40 = 0.0242  # wat de leverancier houdt; bij salderen is dit het hele verschil

prijzen40, zon40 = [], {}
for uur, prijs, zon in MIDDAG40:
    start = dt.datetime(2026, 8, 30, uur, 0)
    prijzen40.append({"start": start, "end": start + dt.timedelta(hours=1),
                      "price": prijs, "feed_in": prijs - OPSLAG40})
    zon40[start] = zon
for uur, prijs in NACHT40:
    start = dt.datetime(2026, 8, 31, uur, 0)
    prijzen40.append({"start": start, "end": start + dt.timedelta(hours=1),
                      "price": prijs, "feed_in": prijs - OPSLAG40})

HUIS40 = {0: 1.5, 1: 1.3, 2: 1.2, 3: 1.1, 4: 1.0, 5: 1.1, 6: 1.3, 7: 1.0, 8: 0.8,
          9: 1.0, 10: 1.2, 11: 1.3, 12: 1.2, 13: 1.63, 14: 3.09, 15: 2.59,
          16: 2.54, 17: 1.39, 18: 1.31, 19: 1.63, 20: 1.10, 21: 1.58, 22: 1.76,
          23: 1.35}
VOORSPELD40 = Forecast(solar_kwh=zon40, house_kwh=HUIS40)

nu40 = dt.datetime(2026, 8, 30, 13, 30)
KLAAR40 = Window(enabled=True, opens=None, deadline=dt.datetime(2026, 8, 31, 7, 0))
BUS40 = Car(capacity_kwh=65.0, phases=3, soc_percent=77.5)
NET40 = Grid(surplus_w=900.0, phase_amps=[5.0, 6.0, 6.0], fuse_amps=25.0,
             charger_amps=15.0)
LAADT40 = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=15.0,
                  started_at=dt.datetime(2026, 8, 30, 13, 0), limit_amps=16.0)

d40 = decide(nu40, prijzen40, NET40, BUS40, LAADT40, KLAAR40,
             tariff=VAST, sun=ZON_KRAP, forecast=VOORSPELD40)
print(f"  13:30  {d40.rule}: laden={d40.charge} {d40.amps} A")
print(f"    {d40.reason}")
print(f"    {d40.plan}")
controle("hij laadt nu, want dit is een van de goedkoopste uren",
         d40.charge and d40.rule == "cheap-hour", f"{d40.rule} {d40.amps} A")
controle("en op vol vermogen, want elk uur dat hij hier laat liggen kost meer",
         d40.amps == 16, f"{d40.amps} A")

# De tijdlijn hoort hetzelfde te zeggen, want hij rekent met dezelfde schijven.
plan40 = planner.timeline(nu40, prijzen40, NET40, BUS40, LAADT40, KLAAR40, 16,
                          VAST, VOORSPELD40)
laadt40 = [blok.start.hour for blok in plan40.blocks if blok.charging]
print(f"  de tijdlijn laadt in de uren: {laadt40}")
controle("de tijdlijn zegt hetzelfde als het besluit", 13 in laadt40, f"{laadt40}")
controle("en pakt de goedkoopste uren van de middag",
         set(laadt40) <= {13, 14, 15, 16}, f"{laadt40}")
controle("dus niet de dure avond", not any(u in laadt40 for u in (18, 19, 20, 21)),
         f"{laadt40}")
controle("en ook niet de nacht, die is duurder dan de middag",
         not any(u in laadt40 for u in (2, 3, 4, 5)), f"{laadt40}")

print("--- hoge prijs met zon: alleen de zon, niet bijkopen ---")
# Om half zeven 's avonds kost stroom 0,319 en ligt er nog 5 kW op het dak.
# Bijkopen op dat uur is de duurste manier die er is; die 5 kW zelf gebruiken is
# de goedkoopste. Dan hoort hij precies dat te doen en niet meer.
#
# **Zonder salderen**, want dat verandert de uitkomst volledig en dat is precies
# wat de vergelijking laat zien. Met salderen is een teruggeleverde kWh bijna de
# inkoopprijs waard, en dan is je eigen zon om zes uur 's avonds duurder dan een
# nachtuur: dan hoort hij hem terug te leveren en 's nachts te laden. Zonder
# salderen brengt teruglevering een fractie op en wint eigen gebruik altijd.
ZONDER_SALDEREN = [dict(rij, feed_in=0.05) for rij in prijzen40]
avond40 = dt.datetime(2026, 8, 30, 18, 30)
ZONNIG40 = Grid(surplus_w=5000.0, phase_amps=[5.0, 6.0, 6.0], fuse_amps=25.0,
                charger_amps=6.0)
d40b = decide(avond40, ZONDER_SALDEREN, ZONNIG40, BUS40, LAADT40, KLAAR40,
              tariff=VAST, sun=ZON_KRAP, forecast=VOORSPELD40,
              holding=planner.STOP_ROUNDS)
print(f"  18:30 met 5 kW over, zonder salderen  {d40b.rule}: {d40b.amps} A")
print(f"    {d40b.reason}")
controle("op een duur uur pakt hij alleen de zon",
         d40b.charge and d40b.rule == "surplus", f"{d40b.rule} {d40b.amps} A")
controle("en niet het volle plafond", d40b.amps < 16, f"{d40b.amps} A")

# En met salderen komt er iets anders uit, en dat is geen fout maar de som.
d40b2 = decide(avond40, prijzen40, ZONNIG40, BUS40, LAADT40, KLAAR40,
               tariff=VAST, sun=ZON_KRAP, forecast=VOORSPELD40,
               holding=planner.STOP_ROUNDS)
print(f"  zelfde moment mét salderen: {d40b2.rule}")
controle("met salderen is je eigen avondzon duurder dan een nachtuur",
         not d40b2.charge, f"{d40b2.rule}")

print("--- laden op een later tijdstip als de prijs gunstiger is ---")
# Om acht uur 's avonds is er geen zon meer en kost stroom 0,363, terwijl de
# nacht op 0,28 zit. Dan hoort hij te wachten en te zeggen tot wanneer.
laat40 = dt.datetime(2026, 8, 30, 20, 30)
DONKER40 = Grid(surplus_w=0.0, phase_amps=[5.0, 6.0, 6.0], fuse_amps=25.0,
                charger_amps=0.0)
STIL40 = Charger(max_amps=16.0, connected=True, charging=False, actual_amps=0.05)
d40c = decide(laat40, prijzen40, DONKER40, BUS40, STIL40, KLAAR40,
              tariff=VAST, sun=ZON_KRAP, forecast=VOORSPELD40)
print(f"  20:30  {d40c.rule}: {d40c.reason}")
controle("hij wacht op de goedkope nacht", not d40c.charge, f"{d40c.rule}")
controle("en zegt tot wanneer", "04:00" in d40c.reason or "0" in d40c.reason,
         d40c.reason)
controle("de pauze loopt af op dat moment, niet later",
         d40c.hold_minutes is not None and d40c.hold_minutes <= 8 * 60,
         f"{d40c.hold_minutes}")

print("--- en de klaar-tijd wint nog steeds van elke som ---")
krap40 = dt.datetime(2026, 8, 31, 5, 30)
LEEG40 = Car(capacity_kwh=65.0, phases=3, soc_percent=20.0)
d40d = decide(krap40, prijzen40, DONKER40, LEEG40, STIL40, KLAAR40,
              tariff=VAST, sun=ZON_KRAP, forecast=VOORSPELD40)
print(f"  05:30 met een lege auto  {d40d.rule}: {d40d.amps} A")
controle("de klaar-tijd gaat voor de prijs", d40d.charge and d40d.rule == "deadline",
         f"{d40d.rule} {d40d.amps} A")

print("=== 41. de schijven zelf ===")
# De opzet van de vergelijking, los. Twee schijven per uur: wat het dak geeft en
# wat je daarboven van het net moet halen.
schijven41 = planner.schijven(nu40, prijzen40, NET40, BUS40, 16, None,
                              KLAAR40.deadline, VAST, VOORSPELD40)
dit_uur = [s for s in schijven41 if s.start.hour == 13 and s.start.day == 30]
print(f"  13:00 levert {len(dit_uur)} schijven: "
      + ", ".join(f"{s.kind} {s.kwh:.2f} kWh a {s.price:.4f}" for s in dit_uur))
# Het uur waar we middenin zitten telt maar een half uur, en 0,9 kW zon is te
# weinig voor de ondergrens van een driefasige paal. Dan is het een vloerschijf:
# de ondergrens, met het bijkopen in de prijs verwerkt.
controle("een uur levert een zonschijf en een netschijf",
         {s.kind for s in dit_uur} == {"vloer", "net"}, f"{[s.kind for s in dit_uur]}")
controle("de zonschijf is goedkoper dan de netschijf",
         min(s.price for s in dit_uur if s.solar)
         < min(s.price for s in dit_uur if not s.solar))
controle("en samen zijn ze het plafond van het halve uur dat er nog van over is",
         abs(sum(s.kwh for s in dit_uur) - planner.watts_for(16, 3) / 1000 / 2) < 0.01,
         f"{sum(s.kwh for s in dit_uur)}")

# En een uur dat nog moet komen met echt overschot levert een gewone zonschijf.
RUIM41 = Forecast(solar_kwh={dt.datetime(2026, 8, 30, 15, 0): 9.0},
                  house_kwh={15: 1.0})
schijven41b = planner.schijven(nu40, prijzen40, NET40, BUS40, 16, None,
                               KLAAR40.deadline, VAST, RUIM41)
straks = [s for s in schijven41b if s.start.hour == 15 and s.start.day == 30]
print(f"  15:00 met 8 kWh over: "
      + ", ".join(f"{s.kind} {s.kwh:.2f} kWh a {s.price:.4f}" for s in straks))
controle("een uur met genoeg zon levert een echte zonschijf",
         {s.kind for s in straks} == {"zon", "net"}, f"{[s.kind for s in straks]}")
controle("en die is zo groot als het dak geeft",
         abs(next(s.kwh for s in straks if s.kind == "zon") - 8.0) < 0.01,
         f"{[s.kwh for s in straks]}")

# Na de klaar-tijd bestaat er niets meer, en voor de begintijd ook niet.
VANAF41 = dt.datetime(2026, 8, 30, 23, 0)
met_begin = planner.schijven(nu40, prijzen40, NET40, BUS40, 16, VANAF41,
                             KLAAR40.deadline, VAST, VOORSPELD40)
controle("voor de begintijd bestaat er geen enkele schijf",
         all(s.end > VANAF41 for s in met_begin),
         f"{[s.start for s in met_begin if s.end <= VANAF41]}")
controle("en na de klaar-tijd ook niet",
         all(s.start < KLAAR40.deadline for s in schijven41))

# En de kern: van goedkoop naar duur vullen tot er genoeg in zit.
gekozen41 = planner.goedkoopste(schijven41, 10.0)
totaal41 = sum(kwh for _, kwh in gekozen41)
kosten41 = sum(schijf.price * kwh for schijf, kwh in gekozen41)
print(f"  10 kWh kost EUR {kosten41:.2f}, oftewel {kosten41 / totaal41:.4f} per kWh")
controle("hij pakt precies wat er nodig is", abs(totaal41 - 10.0) < 0.02, f"{totaal41}")
controle("en niets duurders dan nodig",
         kosten41 / totaal41 < 0.13, f"{kosten41 / totaal41}")

# Het bewijs dat gulzig hier optimaal is: elke andere keuze van dezelfde
# hoeveelheid kost meer. Hier nagerekend tegen de duurste tien kilowattuur.
duurste41 = sorted(schijven41, key=lambda s: -s.price)
rest, slechtst = 10.0, 0.0
for schijf in duurste41:
    if rest <= 0:
        break
    pak = min(schijf.kwh, rest)
    rest -= pak
    slechtst += pak * schijf.price
controle("en dat is aantoonbaar minder dan de duurste manier",
         kosten41 < slechtst, f"{kosten41:.2f} tegen {slechtst:.2f}")

print("=== 44. de veiligheidsrail mag afremmen maar niet stoppen ===")
# Twee keer op 30-08-2026 stond er in de klantwoning een ronde lang "je aansluiting
# is te zwaar belast om te laden", om 12:47:36 en om 15:02:58. De fasen stonden
# op dat moment op 5, 5 en 7 ampere en de zekering is 25. Ik heb er die dag twee
# keer naar gezocht in de meting; het was de rail zelf.
#
# De paal was net gestopt op 5,5 A. Zolang de fasemeting nog naijlt, knijpt de
# rail het plafond af op wat er al gevraagd wás, en dat is dan 5,5. Dat is onder
# de ondergrens van een paal, dus kwam er `no-room` uit: stoppen, terwijl de
# rail alleen bedoeld is om niet omhóóg te gaan.
nu44 = middag(15, 3)
RUSTIG44 = Grid(surplus_w=0.0, phase_amps=[5.0, 5.0, 7.0], fuse_amps=25.0,
                charger_amps=0.167, recent_charger_amps=5.556, margin_amps=3.0)
NET_GESTOPT = Charger(max_amps=16.0, connected=True, charging=False,
                      actual_amps=0.167, limit_amps=6.0)

controle("de meter loopt inderdaad na", planner.meter_loopt_achter(RUSTIG44, NET_GESTOPT))
plafond44 = planner.ceiling_amps(RUSTIG44, LEEG, NET_GESTOPT)
print(f"  huis 7 A op de zwaarste fase, paal net gestopt op 5,5 A: plafond {plafond44} A")
controle("de rail duwt het plafond niet onder de ondergrens",
         plafond44 >= MIN_AMPS, f"{plafond44} A")

d44 = decide(nu44, [], RUSTIG44, LEEG, NET_GESTOPT, venster(nu44),
             tariff=VAST, sun=ZON_KRAP)
print(f"  {d44.rule}: laden={d44.charge} {d44.amps} A")
controle("dus geen 'te zwaar belast' meer bij een rustig huis",
         d44.rule != "no-room", f"{d44.rule}")

# En de rail doet nog wel waar hij voor is: hij houdt een optrekkende paal tegen
# die anders op een naijlende meting omhoog zou springen. de eigen getallen van
# 20-08-2026: de paal meldt 2,7 A terwijl L1 al op 16 staat.
OPTREKKEND = Grid(surplus_w=0.0, phase_amps=[16.0, 3.0, 2.0], fuse_amps=25.0,
                  charger_amps=2.7, margin_amps=2.0)
TREKT_OP = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=2.7,
                   limit_amps=10.0)
plafond44b = planner.ceiling_amps(OPTREKKEND, LEEG, TREKT_OP)
print(f"  paal trekt op naar 10 A, meter loopt na: plafond {plafond44b} A")
controle("hij blijft afremmen op wat er al gevraagd was", plafond44b == 10,
         f"{plafond44b} A")

# En een huis dat werkelijk vol zit wint nog steeds van de rail.
VOL44 = Grid(surplus_w=0.0, phase_amps=[5.0, 5.0, 24.0], fuse_amps=25.0,
             charger_amps=0.167, recent_charger_amps=5.556, margin_amps=3.0)
plafond44c = planner.ceiling_amps(VOL44, LEEG, NET_GESTOPT)
print(f"  huis 24 A op de zwaarste fase: plafond {plafond44c} A")
controle("een huis dat er zelf overheen gaat wint van de rail",
         plafond44c < MIN_AMPS, f"{plafond44c} A")

print("=== 45. een klaar-tijd die verder weg is dan morgen krijgt zijn dag ===")
# De eigenaar op vrijdagavond 04-09-2026, met zaterdag uitgevinkt en zondag klaar om
# 06:00: "er staat prijzen tot 06:00 zijn nog niet bekend maar dat is wel zo,
# want morgen is het zaterdag en dan is 06:00 al wel bekend. Er moet iets komen
# staan dat zaterdag niet ingepland staat en dan zondag pas vol moet."
vrijdag = dt.datetime(2026, 9, 4, 20, 34)
zes = dt.time(6, 0)
dagen45 = {d: planner.DayWindow(enabled=(d != 5), done_by=zes) for d in range(7)}
venster45 = planner.resolve_window(vrijdag, dagen45)
print(f"  klaar-tijd {venster45.deadline}, overgeslagen {venster45.skipped}")
controle("de klaar-tijd is zondag 06:00",
         venster45.deadline == dt.datetime(2026, 9, 6, 6, 0), f"{venster45.deadline}")
controle("en het venster weet dat zaterdag uit staat",
         venster45.skipped == ("zaterdag",), f"{venster45.skipped}")
controle("een dag die gewoon voorbij is telt niet als overgeslagen",
         planner.resolve_window(vrijdag, {d: planner.DayWindow(done_by=zes) for d in range(7)}).skipped == (),
         "vrijdag 06:00 is al geweest en is geen uitgezette dag")

controle("vandaag en morgen krijgen alleen de klok",
         planner._wanneer(dt.datetime(2026, 9, 5, 6, 0), vrijdag) == "06:00"
         and planner._wanneer(dt.datetime(2026, 9, 4, 23, 0), vrijdag) == "23:00")
controle("overmorgen krijgt de dag erbij",
         planner._wanneer(dt.datetime(2026, 9, 6, 6, 0), vrijdag) == "zondag 06:00",
         planner._wanneer(dt.datetime(2026, 9, 6, 6, 0), vrijdag))

# De prijzen lopen tot zaterdagavond, dus niet tot zondag 06:00: alleen zon.
prijzen45 = []
for stap in range(28):
    start = dt.datetime(2026, 9, 4, 20, 0) + dt.timedelta(hours=stap)
    prijzen45.append({"start": start, "end": start + dt.timedelta(hours=1),
                      "price": 0.25, "feed_in": 0.02})
d45 = decide(vrijdag, prijzen45, NET_LEEG, Car(capacity_kwh=65.0, phases=3, soc_percent=8.5),
             paal(laadt=False, amps=0.0), venster45,
             forecast=kromme(dt.datetime(2026, 9, 5), 9, [1.0, 3.0, 5.0, 5.0, 4.0, 2.0]))
print(f"  {d45.rule}: {d45.reason} | {d45.plan}")
controle("hij wacht op de prijzen", d45.rule == "wait-for-prices", d45.rule)
controle("en zegt eerst dat zaterdag uit staat en hij zondag vol moet zijn",
         d45.reason.startswith("Zaterdag staat in je schema uit, dus hij moet zondag om 06:00 vol zijn."),
         d45.reason)
controle("en zegt niet nog een keer zondag 06:00 in dezelfde adem",
         "De prijzen tot dan zijn nog niet bekend" in d45.reason
         and d45.reason.count("zondag") == 1, d45.reason)
# Zonder zonverwachting is er niets te plannen, en dan zegt hij wanneer de
# prijzen komen: de middag vóór de klaar-tijd, dus zaterdag, dus morgen.
d45b = decide(vrijdag, prijzen45, NET_LEEG, Car(capacity_kwh=65.0, phases=3, soc_percent=8.5),
              paal(laadt=False, amps=0.0), venster45)
print(f"  zonder zon: {d45b.rule}: {d45b.reason} | {d45b.plan}")
controle("zonder zon wacht hij ook", d45b.rule == "wait-for-prices", d45b.rule)
controle("en zegt wanneer die prijzen komen: de middag ervoor",
         "meestal morgen tussen 13:00 en 15:00" in d45b.plan, d45b.plan)
# Zonder uitgezette dag staat de klaar-tijd gewoon met zijn dag in de zin.
d45c = decide(vrijdag, prijzen45, NET_LEEG, Car(capacity_kwh=65.0, phases=3, soc_percent=8.5),
              paal(laadt=False, amps=0.0), Window(enabled=True, deadline=venster45.deadline))
controle("zonder uitgezette dag noemt hij de klaar-tijd met zijn dag",
         d45c.reason.startswith("De prijzen tot zondag 06:00 zijn nog niet bekend"), d45c.reason)

plan45 = planner.timeline(vrijdag, prijzen45, NET_LEEG,
                          Car(capacity_kwh=65.0, phases=3, soc_percent=8.5),
                          paal(laadt=False, amps=0.0), venster45, 16,
                          forecast=kromme(dt.datetime(2026, 9, 5), 9, [1.0, 3.0, 5.0, 5.0, 4.0, 2.0]))
print(f"  tijdlijn: {plan45.note}")
controle("de tijdlijn zegt hetzelfde",
         plan45.note.startswith("Zaterdag staat in je schema uit")
         and "zondag om 06:00" in plan45.note and "morgen tussen 13:00 en 15:00" in plan45.note,
         plan45.note)

print("=== 46. een bekend uur onder het gemiddelde mag, ook zonder de prijzen van morgen ===")
# De eigenaar op 05-09-2026, na een ochtend waarin de coach in de klantwoning van 08:00
# (0,184) tot 13:24 op de prijzen van zondag wachtte en de laatste 11 kWh
# daardoor 's nachts tegen 0,304 moest halen: "nu hebben we dus niks bespaard."
# Een bekend uur van vandaag is geen gok: ligt het onder het gemiddelde van
# wat hij kent, dan mag het mee. Erboven wacht hij nog steeds.
prijzen46 = [dict(rij) for rij in prijzen45]
for rij in prijzen46:
    if rij["start"] == dt.datetime(2026, 9, 5, 8, 0):
        rij["price"] = 0.18
PAAL46 = Charger(max_amps=16.0, connected=True, charging=False, actual_amps=0.05)
FORD46 = Car(capacity_kwh=65.0, phases=3, soc_percent=8.5)
d46 = decide(dt.datetime(2026, 9, 5, 8, 30), prijzen46, NET_LEEG, FORD46, PAAL46, venster45)
print(f"  za 08:30 op 0,18: {d46.rule} {d46.amps} A  {d46.reason}")
controle("een bekend uur onder het gemiddelde laadt, op vol vermogen",
         d46.rule == "cheap-hour" and d46.amps == 16, f"{d46.rule} {d46.amps}")
d46b = decide(dt.datetime(2026, 9, 4, 22, 30), prijzen46, NET_LEEG, FORD46, PAAL46, venster45)
print(f"  vr 22:30 op 0,25: {d46b.rule}  {d46b.reason}")
controle("een uur op of boven het gemiddelde wacht op de prijzen",
         d46b.rule == "wait-for-prices" and not d46b.charge, d46b.rule)
controle("en zegt dat goedkope bekende uren wel meedoen, en welk dat is",
         "goedkoper zijn dan het gemiddelde" in d46b.reason and "08:00" in d46b.reason,
         d46b.reason)
plan46 = planner.timeline(dt.datetime(2026, 9, 4, 22, 30), prijzen46, NET_LEEG, FORD46,
                          PAAL46, venster45, 16)
acht = next((b for b in plan46.blocks if b.start == dt.datetime(2026, 9, 5, 8, 0)), None)
controle("de tijdlijn plant dat uur op vol vermogen",
         acht is not None and acht.charging and acht.amps == 16, f"{acht}")
controle("en de andere bekende uren niet",
         [b.start.hour for b in plan46.blocks if b.charging] == [8],
         f"{[b.start.hour for b in plan46.blocks if b.charging]}")
controle("en het plan heet nog steeds alleen-zon, want de rest komt met de prijzen",
         plan46.solar_only, f"{plan46.solar_only}")

print("=== 47. een restje vóór een vol uur: het uur gaat vol, het staartje zegt wanneer hij klaar is ===")
# De eigenaar op 05-09-2026 over de tijdlijn van zaterdag: "waarom staat er bij 3 uur
# geen A maar is wel groen", en later "nu staat er ineens 2 A, dat is helemaal
# niet de bedoeling, hij mag niet onder de 6 A." De knapzak had 0,5 kWh in het
# uur van 03:00 gelegd naast een vol uur om 04:00, en de kaart deelde dat door
# een uur. Wat de coach werkelijk doet: om 03:00 op vol vermogen beginnen en
# doorladen, want stoppen laat te weinig speling over (cheap-hour+reserve, en
# De eigenaar op 04-09-2026: "een uur daarvoor moet hij altijd klaar zijn"). Dus vol
# rond 04:03, en dat hoort de kaart te zeggen.
prijzen47 = []
for stap, prijs in enumerate([0.38, 0.38, 0.38, 0.38, 0.34, 0.34, 0.34, 0.328, 0.304, 0.3039]):
    start = dt.datetime(2026, 9, 5, 20, 0) + dt.timedelta(hours=stap)
    prijzen47.append({"start": start, "end": start + dt.timedelta(hours=1),
                      "price": prijs, "feed_in": 0.02})
venster47 = Window(enabled=True, deadline=dt.datetime(2026, 9, 6, 6, 0))
# Zo'n 11,5 kWh nodig (de som rekent verliezen mee): een vol uur en een restje
# van een halve kWh.
FORD47 = Car(capacity_kwh=65.0, phases=3, soc_percent=84.08)
nodig47 = planner.energy_needed_kwh(FORD47)
print(f"  nodig: {nodig47:.2f} kWh")
d47 = decide(dt.datetime(2026, 9, 6, 3, 0, 30), prijzen47, NET_LEEG, FORD47, PAAL46, venster47)
print(f"  zo 03:00: {d47.rule} {d47.amps} A")
controle("om 03:00 begint hij op vol vermogen", d47.charge and d47.amps == 16 and d47.rule == "cheap-hour",
         f"{d47.rule} {d47.amps}")
PAAL47 = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=15.8,
                 started_at=dt.datetime(2026, 9, 6, 3, 0), limit_amps=16.0)
FORD47B = Car(capacity_kwh=65.0, phases=3, soc_percent=85.0)
d47b = decide(dt.datetime(2026, 9, 6, 3, 6), prijzen47, NET_LEEG, FORD47B, PAAL47, venster47)
print(f"  zo 03:06, het restje is binnen: {d47b.rule} {d47b.amps} A  {d47b.reason}")
controle("en stopt daarna niet voor het uur speling",
         d47b.charge and d47b.amps == 16 and d47b.rule.startswith("cheap-hour"), f"{d47b.rule}")
plan47 = planner.timeline(dt.datetime(2026, 9, 6, 2, 30), prijzen47, NET_LEEG, FORD47,
                          PAAL46, venster47, 16)
for b in plan47.blocks:
    if b.charging:
        print(f"    {b.start:%H:%M}  {b.amps} A  {b.kw:.1f} kW  {b.kwh:.2f} kWh  {b.why}")
drie = next((b for b in plan47.blocks if b.start.hour == 3), None)
vier = next((b for b in plan47.blocks if b.start.hour == 4), None)
controle("het blok van 03:00 gaat vol, op vol vermogen",
         drie is not None and drie.charging and drie.amps == 16 and abs(drie.kwh - 11.04) < 0.05,
         f"{drie}")
controle("het blok van 04:00 is het staartje en zegt wanneer hij vol is",
         vier is not None and vier.charging and vier.amps == 16 and vier.why.startswith("nog 0,5 kWh, vol rond 04:0"),
         f"{vier}")
controle("en het plan verwacht hem dan ook op dat moment vol",
         plan47.expected_done is not None and plan47.expected_done.hour == 4 and plan47.expected_done.minute < 5,
         f"{plan47.expected_done}")
controle("geen enkel laadblok staat onder de ondergrens",
         all(b.amps >= MIN_AMPS for b in plan47.blocks if b.charging),
         f"{[(b.start.hour, b.amps) for b in plan47.blocks if b.charging]}")
controle("en het plan dekt nog steeds precies wat er in moet",
         abs(plan47.planned_kwh - nodig47) < 0.1, f"{plan47.planned_kwh} van {nodig47}")

print("=== 48. een auto die bovenin gas terugneemt, en een geschatte accustand ===")
# De eigenaar op 06-09-2026: "bepaalde auto's schroeven vanaf een bepaald procent zelf
# hun doorlaatbaarheid in ampère terug." Wat zo'n auto per band van tien
# procent aankan komt uit eerdere beurten (`car_pace`); de som rekent per band
# met het laagste van paal en auto. En: "een auto die niet in HA kan moet
# langer speling hebben": een opgegeven stand krijgt een uur extra.
glad48 = Car(capacity_kwh=66.0, phases=3, soc_percent=70.0)
uren48 = planner.hours_needed(glad48, 16)
# 30% van 66 kWh is 19,8 kWh in de accu, 22,0 aan de stekker, op 11,04 kW.
controle("zonder afbouw: energie gedeeld door vermogen",
         abs(uren48 - (0.3 * 66 / 0.9) / 11.04) < 0.01, f"{uren48:.3f}")
afbouw48 = Car(capacity_kwh=66.0, phases=3, soc_percent=70.0,
               tempo_per_band={8: 5.5, 9: 2.75})
uren48b = planner.hours_needed(afbouw48, 16)
# 70-80 op 11,04 kW, 80-90 op 5,5, 90-100 op 2,75: 0,66 + 1,33 + 2,67 uur.
verwacht48 = (6.6 / 0.9) / 11.04 + (6.6 / 0.9) / 5.5 + (6.6 / 0.9) / 2.75
controle("met afbouw telt elke band met zijn eigen tempo",
         abs(uren48b - verwacht48) < 0.01, f"{uren48b:.3f} tegen {verwacht48:.3f}")
controle("en dat is meer dan zonder", uren48b > uren48 * 2, f"{uren48b:.2f} tegen {uren48:.2f}")
halve48 = Car(capacity_kwh=66.0, phases=3, soc_percent=85.0, tempo_per_band={8: 5.5, 9: 2.75})
uren48c = planner.hours_needed(halve48, 16)
verwacht48c = (3.3 / 0.9) / 5.5 + (6.6 / 0.9) / 2.75
controle("halverwege een band telt alleen de rest van die band",
         abs(uren48c - verwacht48c) < 0.01, f"{uren48c:.3f} tegen {verwacht48c:.3f}")
traag48 = Car(capacity_kwh=66.0, phases=3, soc_percent=70.0, tempo_per_band={7: 20.0})
controle("een auto die meer kan dan de paal wordt niet sneller dan de paal",
         abs(planner.hours_needed(traag48, 16) - uren48) < 0.001, "")
geschat48 = Car(capacity_kwh=66.0, phases=3, soc_percent=70.0, soc_estimated=True)
controle("een opgegeven stand krijgt precies een uur extra",
         abs(planner.hours_needed(geschat48, 16) - uren48 - 1.0) < 0.001,
         f"{planner.hours_needed(geschat48, 16):.3f}")
leeg48 = Car(capacity_kwh=66.0, phases=3, soc_percent=None, soc_estimated=True)
controle("maar een lege accu aannemen krijgt dat uur niet nog eens",
         abs(planner.hours_needed(leeg48, 16, assume_empty=True) - (66 / 0.9) / 11.04) < 0.01, "")

print("=== 49. de auto trekt meer dan gevraagd: onder de groep van de paal ===")
# de klantwoning 06-09-2026 04:18:30: limiet 16 A, de Ford trok 16,9 A op één
# fase, groep 16 A. De coach blijft er zoveel onder als de auto erboven zit.
rustig49 = Grid(phase_amps=[2.0, 18.0, 3.0], fuse_amps=25.0, charger_amps=16.88, margin_amps=3.0)
teveel49 = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=16.88,
                   limit_amps=16.0, circuit_amps=16.0, started_at=middag(3, 0))
controle("16,9 A op een limiet van 16 en een groep van 16: plafond 15",
         planner.ceiling_amps(rustig49, Car(phases=3), teveel49) == 15,
         f"{planner.ceiling_amps(rustig49, Car(phases=3), teveel49)}")
netjes49 = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=14.4,
                   limit_amps=16.0, circuit_amps=16.0, started_at=middag(3, 0))
controle("14,4 A op 16: de groep knijpt niet",
         planner.ceiling_amps(Grid(phase_amps=[15.0, 16.0, 16.0], fuse_amps=25.0, charger_amps=14.4,
                                   margin_amps=3.0), Car(phases=3), netjes49) == 16, "")
zonder49 = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=16.88, limit_amps=16.0)
controle("zonder de sensor van de groep verandert er niets",
         planner.ceiling_amps(rustig49, Car(phases=3), zonder49) == 16, "")

print("=== 50. de vaatwasser: het goedkoopste startmoment binnen het schema ===")
# De eigenaar op 06-09-2026: "nu verder met de vaatwasser sturing." Een programma
# start één keer; de vraag is wanneer. Alle startmomenten tegen elkaar, de
# avondpiek dicht, de klaar-tijd heilig, en zonder prijzen geen gok.
def prijzen50(dag):
    rijen = []
    for i in range(48):
        start = dt.datetime(2026, 9, dag, 0, 0) + dt.timedelta(hours=i)
        prijs = 0.30 if 17 <= start.hour < 21 else (0.18 if 1 <= start.hour < 6 else 0.25)
        rijen.append({"start": start, "end": start + dt.timedelta(hours=1), "price": prijs, "feed_in": 0.07})
    return rijen
eco = planner.programma_van("dishcare_dishwasher_program_eco_50")
controle("het programma wordt herkend in de spelling van Home Assistant", eco is not None and eco.minutes == 225, f"{eco}")
controle("en in die van de andere integratie", planner.programma_van("Dishcare.Dishwasher.Program.Eco50") is eco, "")
controle("een onbekend programma is None", planner.programma_van("iets_anders") is None, "")
venster50 = planner.Window(enabled=True, deadline=dt.datetime(2026, 9, 8, 7, 0))
vrij = planner.Apparaat(status="ready", released=True, program=eco)
avond = planner.plan_programma(dt.datetime(2026, 9, 7, 19, 0), prijzen50(7), Tariff(), Forecast(), venster50, vrij)
print(f"  19:00: {avond.rule} {avond.starts_at}  {avond.reason}")
controle("om 19:00 vrijgegeven met klaar om 07:00: start om 01:00, het goedkoopste blok",
         avond.rule == "wait-for-start" and avond.starts_at == "2026-09-08T01:00:00" and not avond.charge, f"{avond}")
controle("en de reden noemt wat nu starten gekost had", "Nu starten zou" in avond.reason, avond.reason)
nacht = planner.plan_programma(dt.datetime(2026, 9, 8, 1, 0), prijzen50(7), Tariff(), Forecast(), venster50, vrij)
controle("om 01:00 start hij", nacht.rule == "cheapest-start" and nacht.charge, f"{nacht.rule}")
krap = planner.plan_programma(dt.datetime(2026, 9, 8, 3, 30), prijzen50(7), Tariff(), Forecast(), venster50, vrij)
controle("om 03:30 past het niet meer voor 07:00: meteen starten", krap.rule == "deadline" and krap.charge, f"{krap.reason}")
controle("niet vrijgegeven: niets", planner.plan_programma(dt.datetime(2026, 9, 7, 19, 0), prijzen50(7), Tariff(), Forecast(), venster50,
         planner.Apparaat(status="ready", released=False, program=eco)).rule == "not-released", "")
controle("draait al: running", planner.plan_programma(dt.datetime(2026, 9, 7, 19, 0), prijzen50(7), Tariff(), Forecast(), venster50,
         planner.Apparaat(status="run", released=True, program=eco)).rule == "running", "")
vast = planner.plan_programma(dt.datetime(2026, 9, 7, 19, 0), [], Tariff(buy=0.28, feed_in=0.07), Forecast(), venster50, vrij)
controle("vast contract om 19:00: na de avondpiek, om 20:00, en zo heet het ook",
         vast.rule == "wait-for-start" and vast.starts_at == "2026-09-07T20:00:00" and "na de avondpiek" in vast.reason, f"{vast}")
geen = planner.plan_programma(dt.datetime(2026, 9, 7, 19, 0), prijzen50(6), Tariff(), Forecast(), venster50, vrij)
controle("prijzen die niet tot de klaar-tijd reiken: wachten, geen gok",
         geen.rule == "wait-for-prices" and not geen.charge, f"{geen.rule}")
uiterlijk = planner.Window(enabled=True, start_by=dt.datetime(2026, 9, 7, 22, 0), deadline=dt.datetime(2026, 9, 8, 7, 0))
controle("uiterlijk starten om 22:00 bereikt: starten",
         planner.plan_programma(dt.datetime(2026, 9, 7, 22, 0), prijzen50(7), Tariff(), Forecast(), uiterlijk, vrij).rule == "start-by", "")
controle("en daarvoor kiest hij niets na 22:00",
         planner.plan_programma(dt.datetime(2026, 9, 7, 19, 0), prijzen50(7), Tariff(), Forecast(), uiterlijk, vrij).starts_at <= "2026-09-07T22:00:00", "")
# 2,5 kWh per uur over: meer dan de piek van 2,1 kW, dus het opwarmen past er in.
zon = Forecast(solar_kwh={dt.datetime(2026, 9, 7, 12, 0) + dt.timedelta(hours=i): 2.5 for i in range(4)}, house_kwh={})
dag = planner.Window(enabled=True, deadline=dt.datetime(2026, 9, 7, 18, 0))
middag = planner.plan_programma(dt.datetime(2026, 9, 7, 8, 0), prijzen50(7), Tariff(), zon, dag, vrij)
controle("met zon verwacht vanaf 12:00 en klaar om 18:00 start hij om 12:00",
         middag.starts_at == "2026-09-07T12:00:00", f"{middag.starts_at} {middag.reason}")
kosten_zon = planner.programma_kosten(dt.datetime(2026, 9, 7, 12, 0), eco, prijzen50(7), Tariff(), zon)
controle("op zon kost Eco 50 de terugleverprijs: 0,8 kWh maal 0,07",
         abs(kosten_zon - 0.8 * 0.07) < 0.001, f"{kosten_zon:.4f}")
# De eigenaar op 06-09-2026 's avonds: "elk programma is gewoon te verschuiven."
controle("ook voorspoelen wacht op het goedkoopste moment",
         planner.plan_programma(dt.datetime(2026, 9, 7, 19, 0), prijzen50(7), Tariff(), Forecast(), venster50,
                                planner.Apparaat(status="ready", released=True, program=planner.programma_van("pre_rinse"))).rule == "wait-for-start", "")
controle("zonder herkend programma en zonder haast: uitleg, geen start",
         planner.plan_programma(dt.datetime(2026, 9, 7, 19, 0), prijzen50(7), Tariff(), Forecast(), venster50,
                                planner.Apparaat(status="ready", released=True, program=None)).rule == "no-program", "")
# De eigenaar op 07-09-2026 om 10:22, met 3,5 kW teruglevering op de meter terwijl de
# coach op 11:00 wachtte: "ik lever nu 3,5 kW terug, dat is toch gunstig? Je
# weet niet hoeveel je om 11 uur terug gaat leveren." In het lopende uur wint
# de meter van de verwachting, net als bij de paal.
kurz = planner.programma_van("kurz_60")
salderen = Tariff(buy=0.24171, feed_in=0.24171 - 0.052756)
# De verwachting van die ochtend, ruwweg: te weinig voor 10:00, genoeg vanaf 11:00.
ochtend = Forecast(solar_kwh={dt.datetime(2026, 9, 7, 10, 0): 2.2, dt.datetime(2026, 9, 7, 11, 0): 3.5,
                              dt.datetime(2026, 9, 7, 12, 0): 4.7, dt.datetime(2026, 9, 7, 13, 0): 4.9},
                   house_kwh={u: 1.4 for u in range(24)})
thuis = planner.Window(enabled=True, opens=dt.datetime(2026, 9, 7, 8, 0), deadline=dt.datetime(2026, 9, 7, 16, 30))
kort = planner.Apparaat(status="ready", released=True, program=kurz)
zonder = planner.plan_programma(dt.datetime(2026, 9, 7, 10, 22), [], salderen, ochtend, thuis, kort)
print(f"  zonder meting: {zonder.rule} {zonder.starts_at}  {zonder.reason}")
# Tot 08-09-2026 was dat 11:00: uitgesmeerd is Express 1,05 kW, en 11:00 had
# 2,1 kW over. Sinds het verbruik op de piek van 2,2 kW gerekend wordt is
# 11:00 net te weinig en 12:00 (3,3 kW over) het eerste uur dat hem draagt.
controle("zonder meting gelooft hij de verwachting en wacht hij op het eerste uur dat de piek draagt, 12:00",
         zonder.rule == "wait-for-start" and zonder.starts_at == "2026-09-07T12:00:00", f"{zonder}")
met = planner.plan_programma(dt.datetime(2026, 9, 7, 10, 22), [], salderen, ochtend, thuis, kort, surplus_w=3460.0)
print(f"  met 3,46 kW teruglevering: {met.rule} {met.starts_at}  {met.reason}")
controle("met 3,46 kW op de meter start hij nu: een meting wint van een even goede verwachting",
         met.rule == "cheapest-start" and met.charge, f"{met}")
k_nu = planner.programma_kosten(dt.datetime(2026, 9, 7, 10, 22), kurz, [], salderen, ochtend,
                                now=dt.datetime(2026, 9, 7, 10, 22), surplus_w=3460.0)
controle("en die beurt kost dan de zonprijs: 1,05 kWh maal de inkoop min de terugleverkosten",
         abs(k_nu - 1.05 * (0.24171 - 0.052756)) < 0.001, f"{k_nu:.4f}")
niets = planner.plan_programma(dt.datetime(2026, 9, 7, 10, 22), [], salderen, ochtend, thuis, kort, surplus_w=0.0)
controle("meet de meter niets, dan telt dat ook: hij wacht op de zon van 12:00",
         niets.rule == "wait-for-start" and niets.starts_at == "2026-09-07T12:00:00", f"{niets}")
# 10:51, na de herstart: de verwachting was ververst en nog lager, nu starten
# liep 51 minuten het uur van 11:00 in dat op de verwachting net te weinig zon
# had, en hij wachtte tot 12:00 voor minder dan een halve cent.
laat = Forecast(solar_kwh={dt.datetime(2026, 9, 7, 10, 0): 1.26, dt.datetime(2026, 9, 7, 11, 0): 1.84,
                           dt.datetime(2026, 9, 7, 12, 0): 2.78, dt.datetime(2026, 9, 7, 13, 0): 3.59},
                house_kwh={u: 0.85 for u in range(24)})
k_1051 = planner.programma_kosten(dt.datetime(2026, 9, 7, 10, 51), kurz, [], salderen, laat,
                                  now=dt.datetime(2026, 9, 7, 10, 51), surplus_w=3360.0)
k_1200 = planner.programma_kosten(dt.datetime(2026, 9, 7, 12, 0), kurz, [], salderen, laat)
print(f"  10:51 kost {k_1051:.4f}, 12:00 kost {k_1200:.4f}")
# Op de som van toen (uitgesmeerd) was dat een halve cent; met de piek aan het
# begin valt het opwarmen in het uur van 11:00, waarvan de verwachting te
# weinig zei, en is het verschil groter. De meter hieronder weet beter.
controle("om 10:51 is nu starten op de som duurder dan 12:00",
         0 < k_1051 - k_1200 < 0.03, f"{k_1051 - k_1200:.4f}")
halve = planner.plan_programma(dt.datetime(2026, 9, 7, 10, 51), [], salderen, laat, thuis, kort, surplus_w=3360.0)
controle("maar de meter ziet genoeg voor het hele programma en later is zon niet goedkoper: hij start nu",
         halve.rule == "cheapest-start" and halve.charge, f"{halve}")
weinig = planner.plan_programma(dt.datetime(2026, 9, 7, 10, 51), [], salderen, laat, thuis, kort, surplus_w=600.0)
controle("met 600 W op de meter, te weinig voor de piek van 2,2 kW, wacht hij op het uur dat die draagt: 13:00",
         weinig.rule == "wait-for-start" and weinig.starts_at == "2026-09-07T13:00:00", f"{weinig}")
# Genoeg voor het gemiddelde is niet genoeg: 1,5 kW op de meter is meer dan
# 1,05 kW uitgesmeerd, maar minder dan de piek van 2,2 kW. Zie 08-09-2026.
gemiddeld = planner.plan_programma(dt.datetime(2026, 9, 7, 10, 51), [], salderen, laat, thuis, kort, surplus_w=1500.0)
controle("1,5 kW op de meter, boven het gemiddelde maar onder de piek: de meterregel grijpt niet in",
         gemiddeld.rule == "wait-for-start", f"{gemiddeld}")
echt = planner.plan_programma(dt.datetime(2026, 9, 7, 10, 51), [], salderen, laat, thuis, kort, surplus_w=0.0)
controle("en zonder zon op de meter ook, met het verschil erbij",
         echt.rule == "wait-for-start" and "Nu starten zou" in echt.reason, f"{echt}")
# Dynamisch: zon nu, maar vannacht is de stroom goedkoper dan wat de zon
# oplevert. Dan is de nacht een prijs en geen gok, en die wint.
nachtprijs = [{**rij, "price": 0.05 if 1 <= rij["start"].hour < 6 else 0.25} for rij in prijzen50(7)]
nacht_wint = planner.plan_programma(dt.datetime(2026, 9, 7, 10, 51), nachtprijs, Tariff(), laat, venster50, kort, surplus_w=3360.0)
controle("dynamisch met een nacht onder de terugleverprijs: de nacht wint van de zon van nu",
         nacht_wint.rule == "wait-for-start" and nacht_wint.starts_at >= "2026-09-08T01:00:00", f"{nacht_wint}")
piek = planner.plan_programma(dt.datetime(2026, 9, 7, 18, 30), [], Tariff(buy=0.28, feed_in=0.07), Forecast(),
                              planner.Window(enabled=True, deadline=dt.datetime(2026, 9, 8, 7, 0)), kort, surplus_w=3000.0)
controle("in de avondpiek geldt dit niet: zon op de meter en toch wachten tot 20:00",
         piek.rule == "wait-for-start" and piek.starts_at == "2026-09-07T20:00:00", f"{piek}")
controle("de meting geldt alleen voor het lopende uur; om 11:00 rekent hij weer met de verwachting",
         abs(planner.programma_kosten(dt.datetime(2026, 9, 7, 11, 0), kurz, [], salderen, ochtend,
                                      now=dt.datetime(2026, 9, 7, 10, 22), surplus_w=0.0)
             - planner.programma_kosten(dt.datetime(2026, 9, 7, 11, 0), kurz, [], salderen, ochtend)) < 1e-9, "")

# In een echte woning op 08-09-2026 om 09:12: Eco 50 zonder meting (225 min, 0,8 kWh,
# piek 2100 W), de meter zag 250 W teruglevering, Forecast.Solar zei 1,0 tot
# 1,7 kWh per uur voor de middag, het huis 0,75 tot 0,85 kWh. De coach
# startte: uitgesmeerd was Eco 213 W en dat paste in 250 W. De opwarmpiek van
# 2,2 kW kwam van het net, en om 12:00 gaf het dak 3,8 kW. De eigenaar: "waarom
# startte hij terwijl bekend is dat de zon later meer schijnt?"
vandaag = dt.datetime(2026, 9, 8)
sven_zon = Forecast(
    solar_kwh={vandaag.replace(hour=h): k for h, k in [(9, 0.65), (10, 1.002), (11, 1.299), (12, 1.521), (13, 1.66),
                                                       (14, 1.696), (15, 1.617), (16, 1.437), (17, 1.184), (18, 0.865)]},
    house_kwh={9: 0.753, 10: 0.855, 11: 0.813, 12: 0.841, 13: 0.851, 14: 1.068, 15: 0.962, 16: 1.014, 17: 1.081, 18: 2.019},
)
sven_venster = planner.Window(enabled=True, opens=vandaag.replace(hour=8), deadline=vandaag.replace(hour=16, minute=30))
sven_eco = planner.Apparaat(status="ready", released=True, program=eco)
stukken = planner._programma_stukken(vandaag.replace(hour=9, minute=12), vandaag.replace(hour=12, minute=57), eco)
print(f"  stukken zonder profiel: {[(a.strftime('%H:%M'), b.strftime('%H:%M'), round(k, 3)) for a, b, k in stukken]}")
controle("zonder profiel gaan de 0,8 kWh op 2100 W vanaf de start, in 23 minuten, en trekt de staart niets",
         abs(sum(k for _, _, k in stukken) - 0.8) < 1e-6 and stukken[0][2] > 0.7 and all(k == 0 for _, _, k in stukken[1:])
         and stukken[-1][1] == vandaag.replace(hour=12, minute=57), f"{stukken}")
controle("voorspoelen heeft geen piek in de opgave en blijft gelijkmatig",
         abs(sum(k for _, _, k in planner._programma_stukken(vandaag.replace(hour=9), vandaag.replace(hour=9, minute=15),
                                                              planner.programma_van("pre_rinse"))) - 0.05) < 1e-6, "")
sven_250 = planner.plan_programma(vandaag.replace(hour=9, minute=12, second=9), [], salderen, sven_zon, sven_venster, sven_eco, surplus_w=250.0)
print(f"  09:12 met 250 W: {sven_250.rule} {sven_250.starts_at}  {sven_250.reason}")
controle("08-09 om 09:12 met 250 W op de meter start hij niet, want de piek van 2,1 kW past daar niet in",
         sven_250.rule == "wait-for-start" and not sven_250.charge, f"{sven_250}")
# 13:00 belooft het meest maar past niet meer voor 16:30 (225 minuten plus
# een half uur speling), dus 12:00.
controle("en hij wacht op het laatste uur dat nog past en het meest belooft, 12:00",
         sven_250.starts_at == "2026-09-08T12:00:00", f"{sven_250.starts_at}")
sven_300 = planner.plan_programma(vandaag.replace(hour=10, minute=0), [], salderen, sven_zon, sven_venster, sven_eco, surplus_w=300.0)
controle("om 10:00 met 300 W op de meter ook niet",
         sven_300.rule == "wait-for-start", f"{sven_300}")
# Met 1 kW op de meter om 10:00 start hij wel, maar niet via de meterregel:
# de piek past er niet in. Het is de gewone som, met de meter voor het
# lopende uur (de eigenaar op 07-09-2026): 1 kW zon nu is op de som goedkoper dan
# de 0,7 kW die de verwachting voor 12:00 belooft. Zegt de verwachting te
# weinig, dan is dat een verwachting; de eigenaar op 07-09: daar is niets aan te
# schaven.
sven_1000 = planner.plan_programma(vandaag.replace(hour=10, minute=0), [], salderen, sven_zon, sven_venster, sven_eco, surplus_w=1000.0)
controle("om 10:00 met 1 kW op de meter start hij op de gewone som: de meter van nu wint van een magere verwachting",
         sven_1000.rule == "cheapest-start" and sven_1000.charge, f"{sven_1000}")
sven_3000 = planner.plan_programma(vandaag.replace(hour=12, minute=0), [], salderen, sven_zon, sven_venster, sven_eco, surplus_w=3000.0)
controle("om 12:00 met 3 kW op de meter wel: de meter draagt de piek en zon is later niet goedkoper",
         sven_3000.rule == "cheapest-start" and sven_3000.charge and abs(sven_3000.cost_hint - 0.8 * salderen.feed_in) < 0.001
         if hasattr(sven_3000, "cost_hint") else sven_3000.rule == "cheapest-start" and sven_3000.charge, f"{sven_3000}")

print("=== 51. de programmatabel van de klant, de metingen en het profiel ===")
# De eigenaar op 06-09-2026: "we hebben nu een hard coded tabel maar ik wil dat
# kunnen aanpassen, wel moet hij dit als uitgangspunt hebben", en "het
# verbruik is in het begin heel hoog vanwege het opwarmen, dus dat wil ik
# gaan meten en die waardes in kunnen vullen."
controle("een lege tabel is de opgave van de fabrikant", planner.tabel_van([]) is planner.PROGRAMMAS
         and planner.tabel_van(None) is planner.PROGRAMMAS, "")
eigen = planner.tabel_van([
    {"key": "eco_50", "label": "Eco 50 °C", "minutes": 180, "kwh": 0.6, "peak_w": 2000},
    {"label": "Glas 40 °C", "minutes": "90", "kwh": "0.5", "peak_w": 1800},
    {"label": "", "minutes": 60, "kwh": 1.0},          # zonder naam telt niet
    {"label": "Kapot", "minutes": 0, "kwh": 1.0},      # zonder duur telt niet
    {"label": "Raar", "minutes": "x", "kwh": 1.0},     # onbruikbaar telt niet
])
controle("de eigen tabel: twee bruikbare rijen, de rest valt af", len(eigen) == 2, f"{eigen}")
controle("een eigen rij zonder sleutel krijgt er een uit zijn naam",
         eigen[1].key == "glas_40_c" and eigen[1].minutes == 90 and eigen[1].kwh == 0.5, f"{eigen[1]}")
controle("sleutel_van: letters en cijfers, de rest wordt een streepje",
         planner.sleutel_van("Auto 45 tot 65 °C") == "auto_45_tot_65_c" and planner.sleutel_van("") == "programma", "")
controle("de aangepaste Eco is 180 minuten en 0,6 kWh",
         planner.programma_van("dishcare_dishwasher_program_eco_50", eigen).minutes == 180
         and planner.programma_van("dishcare_dishwasher_program_eco_50", eigen).kwh == 0.6, "")
controle("een eigen programma wordt gevonden op zijn sleutel en op zijn naam",
         planner.programma_van("glas_40_c", eigen) is eigen[1] and planner.programma_van("Glas 40 °C", eigen) is eigen[1], "")
controle("en niet in de fabriekstabel", planner.programma_van("glas_40_c") is None, "")

metingen = [
    {"device": "vw", "key": "eco_50", "minutes": 200, "kwh": 0.95, "peak_w": 2050,
     "profile": [2000.0] * 4 + [60.0] * 30 + [1500.0] * 6, "runs": 2},
    {"device": "ander", "key": "eco_50", "minutes": 999, "kwh": 9.0, "peak_w": 1, "profile": [], "runs": 1},
]
gemeten = planner.met_metingen(planner.PROGRAMMAS, metingen, "vw")
eco_gemeten = planner.programma_van("dishcare_dishwasher_program_eco_50", gemeten)
controle("een meting wint van de opgave: 200 minuten, 0,95 kWh, en het profiel erbij",
         eco_gemeten.measured and eco_gemeten.minutes == 200 and eco_gemeten.kwh == 0.95
         and eco_gemeten.peak_w == 2050 and len(eco_gemeten.profile) == 40, f"{eco_gemeten}")
controle("de meting van een ander apparaat telt niet", planner.met_metingen(planner.PROGRAMMAS, metingen, "nogeen")[0].measured is False, "")
controle("de naam blijft van de tabel", eco_gemeten.label == "Eco 50 °C", "")
controle("zonder metingen dezelfde tabel terug", planner.met_metingen(planner.PROGRAMMAS, [], "vw") is planner.PROGRAMMAS, "")

# Het profiel: eerst de opwarmpiek, dan de pomp, dan het drogen. Met zon van
# 12:00 tot 14:00 hoort de piek in de zon te vallen, dus een start om 11:40
# (piek om 11:40 tot 12:00, buiten de zon) is duurder dan een start om 12:00.
punten = [(m, 2000.0 if m < 20 else (1500.0 if m >= 170 else 60.0)) for m in range(0, 200)]
profiel = planner.profiel_van(punten)
controle("profiel_van: veertig stappen van vijf minuten, hoog aan het begin en het eind, laag ertussen",
         len(profiel) == 40 and profiel[0] == 2000.0 and profiel[3] == 2000.0 and profiel[4] == 60.0
         and profiel[20] == 60.0 and profiel[-1] == 1500.0, f"{profiel[:6]} ... {profiel[-3:]}")
controle("een stap zonder meting neemt de vorige over",
         planner.profiel_van([(0, 1000.0), (12, 500.0)]) == (1000.0, 1000.0, 500.0), f"{planner.profiel_van([(0, 1000.0), (12, 500.0)])}")
controle("profiel_gemiddeld: gewogen met het aantal beurten, en de langere staart blijft",
         planner.profiel_gemiddeld((1000.0, 1000.0), 1, (2000.0, 2000.0, 300.0)) == (1500.0, 1500.0, 150.0)
         and planner.profiel_gemiddeld((), 0, (5.0,)) == (5.0,), f"{planner.profiel_gemiddeld((1000.0, 1000.0), 1, (2000.0, 2000.0, 300.0))}")
eco_profiel = planner.Programma("eco_50", "Eco 50 °C", 200, 0.95, 2000, profile=profiel, measured=True)
zon2 = Forecast(solar_kwh={dt.datetime(2026, 9, 7, 12, 0): 3.0, dt.datetime(2026, 9, 7, 13, 0): 3.0}, house_kwh={})
vast = Tariff(buy=0.28, feed_in=0.07)
k_1140 = planner.programma_kosten(dt.datetime(2026, 9, 7, 11, 40), eco_profiel, [], vast, zon2)
k_1200 = planner.programma_kosten(dt.datetime(2026, 9, 7, 12, 0), eco_profiel, [], vast, zon2)
print(f"  met profiel: start 11:40 kost {k_1140:.3f}, start 12:00 kost {k_1200:.3f}")
controle("met het profiel is starten in de zon goedkoper dan de opwarmpiek er net voor",
         k_1200 < k_1140 - 0.05, f"{k_1200:.3f} < {k_1140:.3f}")
eco_plat = planner.Programma("eco_50", "Eco 50 °C", 200, 0.95, 2000)
p_1140 = planner.programma_kosten(dt.datetime(2026, 9, 7, 11, 40), eco_plat, [], vast, zon2)
p_1200 = planner.programma_kosten(dt.datetime(2026, 9, 7, 12, 0), eco_plat, [], vast, zon2)
controle("zonder profiel gaat alles op de piek aan het begin, dus ook dan is 12:00 goedkoper dan 11:40",
         p_1200 < p_1140 - 0.05 and abs(p_1200 - 0.95 * 0.07) < 0.001, f"{p_1140:.3f} {p_1200:.3f}")
controle("zonder zon telt het profiel precies zijn eigen kilowatturen tegen de inkoopprijs",
         abs(planner.programma_kosten(dt.datetime(2026, 9, 7, 2, 0), eco_profiel, [], vast, Forecast()) - 0.28 * sum(w / 1000 * 5 / 60 for w in profiel)) < 0.001, "")
dom = planner.Apparaat(status="ready", released=True, program=eco, manual=True)
d_wacht = planner.plan_programma(dt.datetime(2026, 9, 7, 19, 0), prijzen50(7), Tariff(), Forecast(), venster50, dom)
d_nu = planner.plan_programma(dt.datetime(2026, 9, 8, 1, 0), prijzen50(7), Tariff(), Forecast(), venster50, dom)
d_krap = planner.plan_programma(dt.datetime(2026, 9, 8, 3, 30), prijzen50(7), Tariff(), Forecast(), venster50, dom)
print(f"  dom: {d_wacht.reason} | {d_nu.reason} | {d_krap.reason}")
controle("zonder startknop zegt hij 'zet hem aan' in plaats van 'hij start'",
         d_wacht.reason.startswith("Zet hem aan morgen om 01:00") and d_nu.reason.startswith("Zet hem nu aan")
         and "zet hem meteen aan" in d_krap.reason and "hij start" not in (d_wacht.reason + d_nu.reason + d_krap.reason), "")
controle("en de regels zijn dezelfde als met een knop",
         (d_wacht.rule, d_nu.rule, d_krap.rule) == ("wait-for-start", "cheapest-start", "deadline"), "")

print("=== 51. het gemeten plafond van deze beurt (de klantwoning, nacht van 09 op 10-09-2026) ===")
# Een warmtepomp op één fase ging om het kwartier aan, de paal kreeg 8 A waar
# het plan met 16 rekende. De eigenaar: "er zit geen patroon in", dus geen
# voorspelling; wel de meting van de afgelopen uren in `Charger.expected_amps`.
bus3 = Car(capacity_kwh=77.0, phases=3, soc_percent=50.0, max_amps=16.0)
stil = Charger(max_amps=16.0, connected=True)
druk = Charger(max_amps=16.0, connected=True, expected_amps=9.6)
ruim = Charger(max_amps=16.0, connected=True, expected_amps=20.0)
controle("zonder meting is het plafond wat paal en auto kunnen",
         planner.structural_ceiling(bus3, stil) == 16 and planner.physical_ceiling(bus3, druk) == 16, "")
controle("met een meting van 9,6 A rekent hij met 9, naar beneden afgerond",
         planner.structural_ceiling(bus3, druk) == 9, f"{planner.structural_ceiling(bus3, druk)}")
controle("een meting boven het fysieke plafond verandert niets en krijgt geen zin",
         planner.structural_ceiling(bus3, ruim) == 16 and planner.measured_ceiling_note(bus3, ruim) == "", "")
u16 = planner.hours_needed(bus3, planner.structural_ceiling(bus3, stil))
u9 = planner.hours_needed(bus3, planner.structural_ceiling(bus3, druk))
controle("en dan duurt het naar verhouding langer", abs(u9 / u16 - 16 / 9) < 0.01, f"{u16:.2f} {u9:.2f}")
controle("de zin noemt het gemeten getal",
         planner.measured_ceiling_note(bus3, druk)
         == "De afgelopen uren bleef er gemiddeld 9 A over voor de paal, en daarmee rekent hij voor de uren die komen.",
         planner.measured_ceiling_note(bus3, druk))
nu51 = dt.datetime(2026, 9, 9, 22, 0)
w51 = venster(nu51)
net51 = Grid(surplus_w=0.0, phase_amps=[2.0, 2.0, 2.0], fuse_amps=25.0, charger_amps=0.0)
p_stil = planner.timeline(nu51, prijzen50(9), net51, bus3, stil, w51, 16)
p_druk = planner.timeline(nu51, prijzen50(9), net51, bus3, druk, w51, 16)
print(f"  uiterlijk beginnen: rustig {p_stil.latest_start:%H:%M}, druk {p_druk.latest_start:%H:%M}")
controle("de tijdlijn begint eerder, rekent met 9 A en zegt dat het een meting is",
         p_druk.latest_start < p_stil.latest_start - dt.timedelta(hours=2)
         and p_druk.measured and not p_stil.measured and p_druk.amps == 9 and p_stil.amps == 16,
         f"{p_stil.latest_start} {p_druk.latest_start}")
d_stil = decide(nu51, prijzen50(9), net51, bus3, stil, w51)
d_druk = decide(nu51, prijzen50(9), net51, bus3, druk, w51)
laat51 = nu51.replace(hour=23)
d_laat = decide(laat51, prijzen50(9), net51, bus3, druk, venster(laat51))
print(f"  22:00 rustig: {d_stil.rule} | druk: {d_druk.rule} | 23:00 druk: {d_laat.rule}: {d_laat.reason}")
controle("om 22:00 wacht een rustig huis op de nacht; het drukke huis laadt al, want op 9 A zijn bijna alle uren nodig",
         not d_stil.charge and d_druk.charge and d_druk.rule == "cheap-hour", f"{d_stil.rule} | {d_druk.rule}")
controle("om 23:00 past het op 9 A niet meer met een uur speling: de klaar-tijdregel, met de meting in de reden",
         d_laat.charge and d_laat.rule == "deadline" and "gemiddeld 9 A" in d_laat.reason, f"{d_laat.rule}: {d_laat.reason}")

from dataclasses import replace  # noqa: E402

print("=== 52. na de klaar-tijd: morgen starten of nu starten (12 en 13-09-2026) ===")
# De eigenaar gaf de vaatwasser op 12-09-2026 om 16:33 vrij, bij vanaf 08:00 en klaar
# om 16:30. De coach plande de volgende middag en zei "hij start om 13:00", en
# "nu starten" was de prijs van 08:00 de volgende ochtend; de eigenaar zette hem zelf
# aan. Op 13-09: "de keuze ingeruimd en morgen starten of ingeruimd en nu
# starten."
dagen52 = {d: planner.DayWindow(not_before=dt.time(8, 0), done_by=dt.time(16, 30)) for d in range(7)}
voor52 = planner.resolve_window(dt.datetime(2026, 9, 13, 15, 30), dagen52)
na52 = planner.resolve_window(dt.datetime(2026, 9, 12, 16, 33), dagen52)
controle("om 15:30 is er niets gemist en is de klaar-tijd vandaag",
         voor52.missed is None and voor52.deadline == dt.datetime(2026, 9, 13, 16, 30), f"{voor52}")
controle("om 16:33 is 16:30 van vandaag gemist, en het venster is morgen van 08:00 tot 16:30",
         na52.missed == dt.datetime(2026, 9, 12, 16, 30) and na52.opens == dt.datetime(2026, 9, 13, 8, 0)
         and na52.deadline == dt.datetime(2026, 9, 13, 16, 30), f"{na52}")
express52 = planner.programma_van("dishcare_dishwasher_program_kurz_60")
vrij52 = planner.Apparaat(status="ready", released=True, program=express52)
# Een beetje zon nu, veel zon morgen rond het middaguur, niets om 08:00.
zon52 = Forecast(solar_kwh={dt.datetime(2026, 9, 12, 16, 0): 0.6,
                            **{dt.datetime(2026, 9, 13, 11, 0) + dt.timedelta(hours=i): 3.0 for i in range(4)}},
                 house_kwh={})
vast52 = Tariff(buy=0.24, feed_in=0.07)
nu52 = dt.datetime(2026, 9, 12, 16, 33)
d52 = planner.plan_programma(nu52, [], vast52, zon52, na52, vrij52)
print(f"  16:33 vrijgegeven: {d52.rule} {d52.starts_at}  {d52.reason} | {d52.plan}")
controle("om 16:33 vrijgegeven: hij plant morgen, en zegt dat met zoveel woorden",
         d52.rule == "wait-for-start" and (d52.starts_at or "").startswith("2026-09-13T1")
         and d52.reason.startswith("16:30 is vandaag voorbij, dus hij start morgen om ")
         and d52.plan.startswith("Klaar rond morgen ") and "nu starten" in d52.plan, f"{d52}")
echt_nu52 = planner.programma_kosten(nu52, express52, [], vast52, zon52, now=nu52)
morgen_acht52 = planner.programma_kosten(dt.datetime(2026, 9, 13, 8, 0), express52, [], vast52, zon52, now=nu52)
print(f"  nu starten {echt_nu52:.4f}, morgen 08:00 {morgen_acht52:.4f}")
controle("'nu starten zou' is de prijs van nu, niet van morgen 08:00",
         round(echt_nu52, 2) != round(morgen_acht52, 2)
         and f"Nu starten zou ongeveer {planner._euro(echt_nu52)} kosten" in d52.reason, d52.reason)
hand52 = planner.plan_programma(nu52, [], vast52, zon52, na52, replace(vrij52, manual=True))
controle("zonder startknop: zet hem aan morgen om",
         hand52.reason.startswith("16:30 is vandaag voorbij, dus zet hem aan morgen om "), hand52.reason)
wacht52 = planner.plan_programma(nu52, [], vast52, zon52, na52, replace(vrij52, released=False))
controle("nog niet vrijgegeven na de klaar-tijd: hij vraagt morgen of nu",
         wacht52.rule == "not-released" and "16:30 is vandaag voorbij" in wacht52.reason
         and "morgen" in wacht52.reason and "of nu" in wacht52.reason, wacht52.reason)
ochtend52 = planner.plan_programma(dt.datetime(2026, 9, 13, 8, 0), [], vast52, zon52,
                                   planner.resolve_window(dt.datetime(2026, 9, 13, 8, 0), dagen52), vrij52)
controle("voor de klaar-tijd blijft het zoals het was: geen 'morgen', geen 'voorbij'",
         ochtend52.reason.startswith("Hij start om 1") and "voorbij" not in ochtend52.reason
         and "morgen" not in ochtend52.plan, f"{ochtend52.reason} | {ochtend52.plan}")
avond52 = dt.datetime(2026, 9, 12, 18, 30)
nu_start52 = planner.plan_programma(avond52, [], vast52, zon52, planner.resolve_window(avond52, dagen52),
                                    replace(vrij52, start_now=True))
controle("ingeruimd en nu starten: meteen, ook in de avondpiek",
         nu_start52.charge and nu_start52.rule == "start-now" and nu_start52.plan.startswith("Klaar rond "), f"{nu_start52}")
controle("zonder startknop: zet hem nu aan",
         planner.plan_programma(avond52, [], vast52, zon52, planner.resolve_window(avond52, dagen52),
                                replace(vrij52, start_now=True, manual=True)).reason.startswith("Zet hem nu aan"), "")
controle("nu starten zonder vrijgave is geen vrijgave",
         planner.plan_programma(avond52, [], vast52, zon52, na52, replace(vrij52, released=False, start_now=True)).rule
         == "not-released", "")

print("=== 53. tot hoever de auto laadt (de eigenaar, 16-09-2026) ===")
# "Ik wil een optie hebben op de kaart dat ik kan aangeven tot hoever de bus
# laadt. Mijne laadt tot 80% namelijk maar ik kan hem ook op 100% instellen."
# Zijn bus van 19,7 kWh stond die ochtend op 32% en stopte zelf op 80.
bus53 = planner.Car(capacity_kwh=19.7, phases=3, soc_percent=32.0)
tot80 = replace(bus53, target_percent=80.0)
heel53 = planner.energy_needed_kwh(bus53)
deel53 = planner.energy_needed_kwh(tot80)
print(f"  tot 100%: {heel53:.2f} kWh   tot 80%: {deel53:.2f} kWh")
controle("tot 100% is de hele accu vanaf 32%", abs(heel53 - 14.87) < 0.05, f"{heel53:.2f}")
controle("tot 80% is minder", abs(deel53 - 10.51) < 0.05, f"{deel53:.2f}")
controle("en dat is precies wat er die ochtend in ging", abs(deel53 - 10.33) < 0.25,
         f"{deel53:.2f} tegenover 10,33 gemeten")

# Op zijn doel is hij klaar, en een procent eronder telt mee: de accusensor van
# een Ford springt per tien procent en is nooit fijner dan dat.
op80 = replace(tot80, soc_percent=80.0)
controle("op 80% met doel 80 is hij waar hij wezen moet", planner.doel_bereikt(op80), "")
controle("79,5% telt ook mee", planner.doel_bereikt(replace(op80, soc_percent=79.5)), "")
controle("78% niet", not planner.doel_bereikt(replace(op80, soc_percent=78.0)), "")
controle("met doel 100 blijft 80% gewoon niet vol",
         not planner.doel_bereikt(replace(op80, target_percent=100.0)), "")
controle("en 99,5% wel, zoals FULL_PERCENT altijd deed",
         planner.doel_bereikt(replace(op80, target_percent=100.0, soc_percent=99.5)), "")

# Een doel dat nergens op slaat leest als "gewoon vol". Een oude instelling
# zonder het veld heeft een nul, en een auto die daarop nooit laadt is de ene
# fout die een klant niet vergeeft.
for raar in (0.0, -5.0, 120.0):
    controle(f"een doel van {raar:g} leest als 100",
             planner.doel_van(replace(bus53, target_percent=raar)) == 100.0, "")
controle("een doel van 5 wordt 10", planner.doel_van(replace(bus53, target_percent=5.0)) == 10.0, "")

# En de zinnen die erbij horen. Wie 80% instelt hoort niet elke beurt te lezen
# dat zijn auto niet vol is.
print(f"  op doel, 80 : {planner.klaar_zin(op80)}")
print(f"  op doel, 100: {planner.klaar_zin(replace(op80, target_percent=100.0, soc_percent=99.5))}")
print(f"  eronder     : {planner.klaar_zin(replace(op80, soc_percent=70.0))}")
controle("op het doel van 80: geen woord over vol en geen gok over een laadgrens",
         "vol" not in planner.klaar_zin(op80) and "laadgrens" not in planner.klaar_zin(op80),
         planner.klaar_zin(op80))
controle("op het doel van 80: noemt de stand",
         "80%" in planner.klaar_zin(op80), planner.klaar_zin(op80))
controle("op een doel van 100: gewoon vol",
         planner.klaar_zin(replace(op80, target_percent=100.0, soc_percent=99.5))
         == "De auto is vol.", "")
controle("onder het doel: de laadgrens blijft de gok",
         "laadgrens" in planner.klaar_zin(replace(op80, soc_percent=70.0)), "")

# Het slechtste geval en de afbouw lopen ook tot het doel. Een auto die bovenin
# gas terugneemt hoeft de klaar-tijd niet naar voren te halen voor banden die
# nooit geladen worden.
controle("leeg tot 80% is minder dan leeg tot vol",
         planner.worst_case_kwh(tot80) < planner.worst_case_kwh(bus53), "")
traag = {8: 1.0, 9: 0.5}   # boven de 80% wordt hij traag
uren80 = planner._uren_met_afbouw(replace(tot80, tempo_per_band=traag), 11.0, deel53)
uren100 = planner._uren_met_afbouw(replace(bus53, tempo_per_band=traag), 11.0, heel53)
print(f"  met afbouw: tot 80% {uren80:.2f} uur, tot 100% {uren100:.2f} uur")
controle("de trage banden boven het doel tellen niet mee", uren80 < uren100 - 1.0,
         f"{uren80:.2f} tegenover {uren100:.2f}")

print("=== 54. de klaar-tijdregel laat weer los zodra er ruim tijd is (17-09-2026) ===")
# Thuis om 14:26: de coach had geleerd dat de bus tussen 0 en 10% maar 0,1 kW
# aanneemt (een halve meting, zie `_tempo_leren` in coach.py), rekende daarmee
# 21,41 uur waar het er 1,93 waren, en de klaar-tijdregel sloeg aan. Daarna
# bleef `must_finish` staan en trok de paal de hele middag 11 kW van het net
# terwijl hij tot 03:24 die nacht had kunnen wachten. Grijpen bij een uur
# speling, loslaten bij vier: zie `DEADLINE_RELEASE_HOURS`.
nu54 = dt.datetime(2026, 8, 18, 14, 26)
bus54 = Car(capacity_kwh=19.7, phases=3, soc_percent=10.0, target_percent=80.0)
paal54 = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=15.7,
                 limit_amps=16.0, started_at=dt.datetime(2026, 8, 18, 13, 0))
uren54 = planner.hours_needed(bus54, 13)
print(f"  op 10% met 13 A: {uren54:.2f} uur nodig, {(venster(nu54).deadline - nu54).total_seconds()/3600:.2f} uur tot 06:00")
d54 = decide(nu54, [], NET_LEEG, bus54, paal54, venster(nu54), tariff=VAST, sun=ZON_KRAP,
             must_finish=True)
print(f"  vastgehouden besluit met ruim tijd: {d54.rule} {d54.amps} A")
controle("met ruim vijftien uur speling laat hij los", not d54.rule.startswith("deadline"),
         f"kreeg {d54.rule}: {d54.reason}")

# En hij houdt wél vast zolang het krap is: dezelfde auto, klaar over drie uur.
krap54 = Window(enabled=True, opens=None, deadline=nu54 + dt.timedelta(hours=3))
d54b = decide(nu54, [], NET_LEEG, bus54, paal54, krap54, tariff=VAST, sun=ZON_KRAP,
              must_finish=True)
print(f"  met drie uur tot de klaar-tijd: {d54b.rule} {d54b.amps} A")
controle("bij drie uur blijft hij op vol vermogen staan", d54b.rule == "deadline",
         f"kreeg {d54b.rule}")
# Zonder het vasthouden zou dat uur op zichzelf geen klaar-tijdregel opleveren:
# 1,93 uur nodig en 3 uur tot de klaar-tijd is meer dan het uur speling.
d54c = decide(nu54, [], NET_LEEG, bus54, paal54, krap54, tariff=VAST, sun=ZON_KRAP,
              must_finish=False)
controle("en dat is juist het vasthouden, niet de som zelf", d54c.rule != "deadline",
         f"kreeg {d54c.rule}")

print("=== 55. het restje naar achteren schuiven valt niet meer om ===")
# `sorted(uit)` is een momentopname en de lus wist er zelf uren uit. Kwam er
# later zo'n gewist uur langs, dan viel de hele tijdlijn om met een KeyError en
# stond er niets op de kaart. Gezien op 15-09-2026 in `warmtepomp-nacht`; drie
# reeksen achter elkaar is genoeg om het uit te lokken.
u0 = dt.datetime(2026, 9, 9, 22, 0)
def blok55(i, kwh):
    return planner.Schijf(u0 + dt.timedelta(hours=i), u0 + dt.timedelta(hours=i + 1),
                          0.20, kwh)
alle55 = [blok55(i, 11.0) for i in range(8)]
genomen55 = {blok55(i, 0).start: kwh for i, kwh in
             enumerate([0.2, 11.0, 11.0, 0.3, 11.0, 0.4, 11.0, 11.0])}
uit55 = planner._restje_naar_achteren(genomen55, alle55)
print(f"  {len(genomen55)} uren in, {len(uit55)} uit, samen {sum(uit55.values()):.1f} kWh")
controle("hij valt niet om en houdt dezelfde hoeveelheid vast",
         abs(sum(uit55.values()) - sum(genomen55.values())) < 0.01,
         f"{sum(uit55.values()):.2f} tegen {sum(genomen55.values()):.2f}")

print("=== 56. een zonuur moet de zon ook echt dragen (17-09-2026) ===")
# de eigen middag, met zijn eigen getallen: de voorspeller zei 1,552 kWh voor het
# uur van 16:00 en 1,364 voor 17:00, het huisprofiel stond op 0,94 kWh, dus er
# bleef 0,61 respectievelijk 0,42 kWh over op papier. Zijn meter leverde vanaf
# 15:41 niets meer terug.
nu56 = dt.datetime(2026, 9, 17, 15, 42)
w56 = Window(enabled=True, opens=None, deadline=dt.datetime(2026, 9, 18, 6, 0))
net56 = Grid(surplus_w=0.0, phase_amps=[2.0, 0.0, 1.0], fuse_amps=25.0, charger_amps=0.0)
zon56 = {nu56.replace(hour=h, minute=0, second=0, microsecond=0): kwh
         for h, kwh in [(15, 0.95), (16, 1.552), (17, 1.364), (18, 0.5), (19, 0.1)]}
paal56 = Charger(max_amps=16.0, connected=True, charging=False, actual_amps=0.05)

def uren56(fasen, factor, dag=None):
    auto = Car(capacity_kwh=19.7, phases=fasen, soc_percent=25.0, target_percent=80.0)
    plan = planner.timeline(
        nu56, [], net56, auto, paal56, w56, 16, tariff=VAST,
        forecast=Forecast(solar_kwh=zon56, house_kwh={u: 0.94 for u in range(24)},
                          solar_factor=factor,
                          solar_day=nu56.date() if dag is None else dag),
    )
    return [b.start.hour for b in plan.blocks if b.charging], plan

# Driefasig: er gaat 4,14 kWh in zo'n uur en de zon draagt er 0,61 van, vijftien
# procent. Dat is geen zonuur meer, dus vóór 20:00 gaat er niets van het net bij
# (eis 4). Op v0.66.0 stonden 16:00 en 17:00 hier nog wél in.
drie, plan56 = uren56(3, None)
print(f"  driefasig, zonder meting: laadt in {drie}")
controle("driefasig: 0,61 kWh zon opent geen uur van 4,14 kWh meer",
         16 not in drie and 17 not in drie and 20 in drie, f"{drie}")

# Eenfasig gaat er 1,38 kWh in en is diezelfde 0,61 kWh wél bijna de helft: dat
# blijft een zonuur, en dan is de meting het enige dat het nog tegenhoudt.
een, _ = uren56(1, None)
print(f"  eenfasig, zonder meting:  laadt in {een}")
controle("eenfasig: daar draagt de zon bijna de helft, dus dat blijft een zonuur",
         16 in een, f"{een}")
een_gemeten, plan56b = uren56(1, 0.0)
print(f"  eenfasig, meter gaf niets: laadt in {een_gemeten}")
controle("eenfasig: maar niet als de meter twee uur lang niets teruglegde",
         16 not in een_gemeten and 17 not in een_gemeten, f"{een_gemeten}")
controle("en dan staat er op de kaart waarom", "Je dak gaf" in plan56b.solar_note,
         plan56b.solar_note)
controle("zonder meting staat er niets", plan56.solar_note == "", plan56.solar_note)

# De correctie zit op de opbrengst en pas daarna gaat het huis eraf: voorspeld
# 1,552 kWh maal 0,5 is 0,776, min 0,94 huis is niets meer over. Andersom (het
# overschot halveren) zou er 0,306 uitkomen, en dat is niet wat er gemeten is.
uur16 = nu56.replace(hour=16, minute=0, second=0, microsecond=0)
def fc56(**extra):
    return Forecast(solar_kwh=zon56, house_kwh={16: 0.94}, **extra)
kaal = planner.overschot_kwh(fc56(), uur16)
half = planner.overschot_kwh(fc56(solar_factor=0.5, solar_day=uur16.date()), uur16)
driekwart = planner.overschot_kwh(fc56(solar_factor=0.75, solar_day=uur16.date()), uur16)
print(f"  overschot zonder factor {kaal:.3f}, met 0,75 {driekwart:.3f}, met 0,5 {half:.3f} kWh")
controle("de factor zit op de opbrengst en niet op het overschot",
         abs(kaal - 0.612) < 0.001 and abs(driekwart - (1.552 * 0.75 - 0.94)) < 0.001
         and half == 0.0, f"{kaal}, {driekwart}, {half}")

# En alleen voor uren van de dag waarop gemeten is. Een meting bij zonsondergang
# zegt niets over morgenmiddag; zonder deze grens zou een klaar-tijd die over
# een dag heen loopt (weekend) de zon van de volgende dag wegstrepen.
morgen56 = planner.overschot_kwh(
    fc56(solar_factor=0.5, solar_day=(uur16 - dt.timedelta(days=1)).date()), uur16)
print(f"  gemeten op een andere dag: {morgen56:.3f} kWh (ongecorrigeerd {kaal:.3f})")
controle("een meting van gisteren raakt de zon van vandaag niet",
         abs(morgen56 - kaal) < 0.001, f"{morgen56} tegen {kaal}")
controle("en zonder dag telt de factor helemaal niet",
         abs(planner.overschot_kwh(fc56(solar_factor=0.5), uur16) - kaal) < 0.001, "")

print("=== 57. het laatste uur toont nooit minder dan de ondergrens (17-09-2026) ===")
# de eigen scherm om 22:10, met 2,5 kWh te gaan: "4 A, laden op 2,8 kW, vol rond
# 23:00", terwijl zijn paal 5,92 A en 4,08 kW trok. 2,5 kWh uitgesmeerd over de
# vijftig minuten die nog van dat uur over zijn is 2,94 kW, en dat is 4 A; maar
# een paal levert niets onder 6 A, dus hij loopt op 4,14 kW en is om 22:45
# klaar. De eigenaar: "dit klopt niet, 4 A laden." Dezelfde klacht als op 05-09-2026.
#
# De restant-regel erboven kon er niet bij: die vraagt een vol uur ervóór en dat
# ligt in het verleden, dus er bestaat geen schijf van.
nu57 = dt.datetime(2026, 9, 17, 22, 10)
w57 = Window(enabled=True, opens=None, deadline=dt.datetime(2026, 9, 18, 6, 0))
auto57 = Car(capacity_kwh=19.7, phases=3, soc_percent=68.8, target_percent=80.0)
paal57 = Charger(max_amps=16.0, connected=True, charging=True, actual_amps=5.92,
                 limit_amps=6.0, started_at=dt.datetime(2026, 9, 17, 20, 0))
net57 = Grid(surplus_w=0.0, phase_amps=[9.0, 6.0, 7.0], fuse_amps=25.0, charger_amps=5.92)
plan57 = planner.timeline(nu57, [], net57, auto57, paal57, w57, 16, tariff=VAST,
                          forecast=Forecast())
blok57 = plan57.blocks[0]
print(f"  {blok57.start:%H:%M}  {blok57.amps} A  {blok57.kw:.2f} kW  {blok57.why}")
print(f"  vol rond {plan57.expected_done:%H:%M}")
controle("het laatste uur staat op de ondergrens en niet op het gemiddelde",
         blok57.amps == MIN_AMPS and abs(blok57.kw - 4.14) < 0.01,
         f"{blok57.amps} A, {blok57.kw} kW")
controle("en zegt wanneer hij vol is in plaats van het uur vol te maken",
         "vol rond 22:45" in blok57.why, blok57.why)
controle("vol rond klopt met die ondergrens, niet met het einde van het uur",
         plan57.expected_done is not None and plan57.expected_done.hour == 22
         and plan57.expected_done.minute == 45, f"{plan57.expected_done}")

# En ook als de afronding het verbergt. Om 22:26 met 2,19 kWh over vierendertig
# minuten is het gemiddelde 3,86 kW, en dat rondt af naar 6 A; de stroom klopte
# dan toevallig maar het vermogen (3,89 in plaats van 4,14) en "vol rond 23:00"
# niet. Daarom toetst de regel op het vermogen en niet op de afgeronde stroom.
laat57 = planner.timeline(
    dt.datetime(2026, 9, 17, 22, 26), [], net57,
    Car(capacity_kwh=19.7, phases=3, soc_percent=70.0, target_percent=80.0),
    paal57, w57, 16, tariff=VAST, forecast=Forecast())
b57 = laat57.blocks[0]
print(f"  22:26 -> {b57.amps} A  {b57.kw:.2f} kW  {b57.why}")
controle("de afronding verbergt het niet: vermogen en vol-rond kloppen ook",
         b57.amps == MIN_AMPS and abs(b57.kw - 4.14) < 0.01 and "vol rond" in b57.why,
         f"{b57.amps} A, {b57.kw} kW, {b57.why}")

# Maar een uur dat wél vol benut wordt blijft gewoon staan, en een zonuur ook:
# daar is de ondergrens al het antwoord en het gemiddelde klopt.
vol57 = planner.timeline(
    nu57.replace(hour=20, minute=0), [], net57,
    Car(capacity_kwh=77.0, phases=3, soc_percent=20.0, target_percent=100.0),
    paal57, w57, 16, tariff=VAST, forecast=Forecast())
laadt57 = [b for b in vol57.blocks if b.charging]
print(f"  een volle nacht: {[(b.start.hour, b.amps) for b in laadt57][:4]}")
controle("een uur dat helemaal gebruikt wordt houdt zijn eigen stroom",
         laadt57 and all(b.amps >= MIN_AMPS for b in laadt57),
         f"{[(b.start.hour, b.amps) for b in laadt57]}")

print("=== 58. een leeg uur boven het gemiddelde zegt waarom (18-09-2026) ===")
# de klantwoning, vrijdag 19:55: de Ford op 18%, zaterdag uitgevinkt, dus klaar
# zondag 06:00, en de prijzen reiken tot zaterdag 23:00. Dan komt er van het
# net alleen iets bij in een uur onder het gemiddelde van wat bekend is
# (`alleen_zon`). De uren van 20:00 tot 02:00 lagen daarboven en de kaart zei
# "buiten je tijden", terwijl ze gewoon in het schema vielen.
prijzen58_lijst = [
    0.3709, 0.3722, 0.3509, 0.3333, 0.2986,          # vrijdag 19:00 tot 24:00
    0.2609, 0.2332, 0.2074, 0.1682, 0.1727, 0.1724,  # zaterdag 00:00 tot 06:00
    0.1849, 0.1848, 0.1688, 0.1409, 0.1291, 0.1288,
    0.1283, 0.1276, 0.1275, 0.1279, 0.1289, 0.1394,
    0.2146, 0.2885, 0.2739, 0.2556, 0.2485, 0.2405,  # tot zaterdag 24:00
]
begin58 = dt.datetime(2026, 9, 18, 19, 0)
prijzen58 = [
    {"start": begin58 + dt.timedelta(hours=i),
     "end": begin58 + dt.timedelta(hours=i + 1), "price": p}
    for i, p in enumerate(prijzen58_lijst)
]
gem58 = sum(prijzen58_lijst) / len(prijzen58_lijst)
nu58 = dt.datetime(2026, 9, 18, 19, 55)
w58 = Window(enabled=True, opens=None, deadline=dt.datetime(2026, 9, 20, 6, 0))
auto58 = Car(capacity_kwh=65.0, phases=3, soc_percent=18.0)
paal58 = Charger(max_amps=16.0, connected=True, charging=False)
plan58 = planner.timeline(nu58, prijzen58, NET_LEEG, auto58, paal58, w58, 16,
                          forecast=Forecast())
print(f"  gemiddelde {gem58:.4f}, alleen zon: {plan58.solar_only}")
for b in plan58.blocks[:9]:
    print(f"  {b.start:%a %H:%M}  {b.price:.4f}  {b.why}")
controle("de prijzen reiken niet tot de klaar-tijd", plan58.solar_only, "")
controle("nergens staat nog 'buiten je tijden'",
         not any(b.why == "buiten je tijden" for b in plan58.blocks),
         f"{[(b.start.hour, b.why) for b in plan58.blocks if b.why == 'buiten je tijden']}")
duur58 = [b for b in plan58.blocks
          if not b.charging and b.price >= gem58 and not planner.in_evening_peak(b.start)]
controle("een uur boven het gemiddelde zegt dat hij op de nieuwe prijzen wacht",
         duur58 and all("wacht eerst op de nieuwe prijzen" in b.why for b in duur58),
         f"{[(b.start.hour, b.why) for b in duur58]}")
# Sinds v0.79.0 is de avondpiek bij een dynamisch contract een gewoon uur op
# zijn prijs, dus ook het blok van 20:00 krijgt een prijsreden.
controle("de avondpiek heeft bij een dynamisch contract geen eigen reden meer",
         "avondpiek" not in plan58.blocks[0].why, plan58.blocks[0].why)
goedkoop58 = [b for b in plan58.blocks if not b.charging and b.price < gem58]
controle("een uur onder het gemiddelde dat niet gekozen is blijft 'duurder dan wat hij nodig heeft'",
         goedkoop58 and all(b.why == "duurder dan wat hij nodig heeft" for b in goedkoop58),
         f"{[(b.start.hour, b.why) for b in goedkoop58]}")
controle("het plan zelf verandert niet: zaterdag 11:00 tot 16:00",
         [b.start.hour for b in plan58.blocks if b.charging] == [11, 12, 13, 14, 15, 16],
         f"{[b.start.hour for b in plan58.blocks if b.charging]}")

# --- De boiler ---------------------------------------------------------------
#
# De eigenaar op 19-09-2026: een boiler waar je alleen stroom op hoeft te zetten, met
# een smart plug. Alleen de schakelaar en het vermogen invullen, de rest leert
# hij zelf. Klaar om 07:00, zonoverschot mag hij pakken, en af en toe even
# proefdraaien om te zien of het vat nog warm is.

print()
print("=== de boiler ===")

def prijzen_boiler(dag=7):
    """Twee etmalen: nacht goedkoop (0,18), avondpiek duur (0,30), rest 0,25."""
    rijen = []
    for i in range(48):
        start = dt.datetime(2026, 9, dag, 0, 0) + dt.timedelta(hours=i)
        prijs = 0.30 if 17 <= start.hour < 21 else (0.18 if 1 <= start.hour < 6 else 0.25)
        rijen.append({"start": start, "end": start + dt.timedelta(hours=1), "price": prijs, "feed_in": 0.07})
    return rijen


def geleerde_boiler(**kw):
    """Een boiler die al gemeten is: 2 kW, een vat van 6 kWh, 0,25 kWh per uur eruit."""
    velden = dict(heat_w=2000.0, vol_kwh=6.0, verbruik_kwh_h=0.25)
    velden.update(kw)
    return planner.Boiler(**velden)


venster_b = planner.Window(enabled=True, deadline=dt.datetime(2026, 9, 8, 7, 0))
prijzen_b = prijzen_boiler()

# Wat er nog in moet: sinds het vat vol was tot aan de klaar-tijd, begrensd op
# een heel vat, min wat er al in ging.
nodig = planner.boiler_nodig(
    dt.datetime(2026, 9, 7, 19, 0),
    geleerde_boiler(vol_sinds=dt.datetime(2026, 9, 7, 7, 0)),
    venster_b.deadline,
)
controle("twaalf uur geleden vol en nog twaalf te gaan: 24 maal 0,25 is 6, en het vat is 6",
         abs(nodig - 6.0) < 0.001, f"{nodig}")
nodig_kort = planner.boiler_nodig(
    dt.datetime(2026, 9, 7, 19, 0),
    geleerde_boiler(vol_sinds=dt.datetime(2026, 9, 7, 17, 0)),
    venster_b.deadline,
)
controle("twee uur geleden gemeten dat hij vol was: dan hoeft er niets bij, wat de som ook zegt",
         nodig_kort == 0.0, f"{nodig_kort}")
nodig_al = planner.boiler_nodig(
    dt.datetime(2026, 9, 7, 19, 0),
    geleerde_boiler(vol_sinds=dt.datetime(2026, 9, 7, 14, 0), kwh_sinds_vol=1.0),
    venster_b.deadline,
)
controle("wat er al in ging gaat eraf: zeventien uur maal 0,25 is 4,25, min 1 is 3,25",
         abs(nodig_al - 3.25) < 0.001, f"{nodig_al}")
controle("zonder meting is er niets te zeggen",
         planner.boiler_nodig(dt.datetime(2026, 9, 7, 19, 0), planner.Boiler(), venster_b.deadline) is None, "")

# Het gewone geval: 's avonds om 19:00, klaar om 07:00. De nacht is goedkoop.
avond_b = planner.plan_boiler(
    dt.datetime(2026, 9, 7, 19, 0), prijzen_b, Tariff(), Forecast(), venster_b,
    geleerde_boiler(vol_sinds=dt.datetime(2026, 9, 7, 12, 0)),
)
print(f"  19:00: {avond_b.rule} {avond_b.starts_at}  {avond_b.reason}")
controle("om 19:00 wacht hij op de nacht en zegt wanneer",
         avond_b.rule == "wait-for-cheap" and not avond_b.charge
         and avond_b.starts_at == "2026-09-08T01:00:00", f"{avond_b}")

nacht_b = planner.plan_boiler(
    dt.datetime(2026, 9, 8, 1, 0), prijzen_b, Tariff(), Forecast(), venster_b,
    geleerde_boiler(vol_sinds=dt.datetime(2026, 9, 7, 12, 0)),
)
controle("om 01:00 zet hij hem aan", nacht_b.rule == "cheapest-hour" and nacht_b.charge, f"{nacht_b}")

# De klaar-tijd is heilig, ook als het dan duur is.
krap_b = planner.plan_boiler(
    dt.datetime(2026, 9, 8, 6, 0), prijzen_b, Tariff(), Forecast(), venster_b,
    geleerde_boiler(vol_sinds=dt.datetime(2026, 9, 7, 7, 0)),
)
controle("een uur voor de klaar-tijd met een leeg vat: meteen aan",
         krap_b.rule == "deadline" and krap_b.charge, f"{krap_b.reason}")

# Vol gemeten: de stroom gaat eraf, wat de prijs ook is.
vol_b = planner.plan_boiler(
    dt.datetime(2026, 9, 8, 1, 0), prijzen_b, Tariff(), Forecast(), venster_b,
    geleerde_boiler(on=True, full=True, vol_sinds=dt.datetime(2026, 9, 8, 1, 0)),
)
controle("vol gemeten: uit, ook in het goedkoopste uur",
         vol_b.rule == "full" and not vol_b.charge, f"{vol_b}")

# Nog niets geleerd: aanzetten en meten, niet rekenen.
leeg_b = planner.plan_boiler(
    dt.datetime(2026, 9, 7, 19, 0), prijzen_b, Tariff(), Forecast(), venster_b, planner.Boiler(),
)
controle("de eerste keer zet hij hem aan om te meten",
         leeg_b.rule == "leren" and leeg_b.charge, f"{leeg_b}")

# Schema uit: de coach stuurt niet en laat de stroom erop staan.
uit_b = planner.plan_boiler(
    dt.datetime(2026, 9, 7, 19, 0), prijzen_b, Tariff(), Forecast(),
    planner.Window(enabled=False), geleerde_boiler(),
)
controle("zonder schema blijft de stroom erop staan",
         uit_b.rule == "schema-uit" and uit_b.charge, f"{uit_b}")

# Zon van nu wint van elk uur van straks.
zon_b = planner.plan_boiler(
    dt.datetime(2026, 9, 7, 13, 0), prijzen_b, Tariff(), Forecast(), venster_b,
    geleerde_boiler(vol_sinds=dt.datetime(2026, 9, 7, 8, 0)), surplus_w=2400.0,
)
controle("2,4 kW overschot op een boiler van 2 kW: aan",
         zon_b.rule == "zon" and zon_b.charge, f"{zon_b.reason}")
zon_te_weinig = planner.plan_boiler(
    dt.datetime(2026, 9, 7, 13, 0), prijzen_b, Tariff(), Forecast(), venster_b,
    geleerde_boiler(vol_sinds=dt.datetime(2026, 9, 7, 8, 0)), surplus_w=900.0,
)
controle("900 W overschot draagt hem niet: dan telt de prijs weer",
         zon_te_weinig.rule in ("wait-for-cheap", "cheapest-hour"), f"{zon_te_weinig.rule}")

# De avondpiek zit dicht voor het net, maar niet voor de zon.
schijven_piek = planner.boiler_schijven(
    dt.datetime(2026, 9, 7, 12, 0), prijzen_b, Tariff(), Forecast(), geleerde_boiler(),
    tot=dt.datetime(2026, 9, 7, 23, 0),
)
# Bij een dynamisch contract (een prijslijst) telt de avondpiek gewoon mee op
# zijn prijs (v0.79.0); bij een vast contract staat er zonder zon geen blok.
controle("bij een dynamisch contract staat de avondpiek gewoon in de lijst, op zijn eigen prijs",
         any(planner.in_evening_peak(s.start) and s.kind == "net" for s in schijven_piek),
         f"{[s.start.hour for s in schijven_piek if planner.in_evening_peak(s.start)]}")
schijven_vast = planner.boiler_schijven(
    dt.datetime(2026, 9, 7, 12, 0), [], Tariff(buy=0.25, feed_in=0.07), Forecast(), geleerde_boiler(),
    tot=dt.datetime(2026, 9, 7, 23, 0),
)
controle("bij een vast contract staat er in de avondpiek geen enkel blok als er geen zon is",
         not any(planner.in_evening_peak(s.start) for s in schijven_vast),
         f"{[s.start.hour for s in schijven_vast if planner.in_evening_peak(s.start)]}")
zonnig = kromme(dt.datetime(2026, 9, 7), 18, [3.0, 3.0])
schijven_zon = planner.boiler_schijven(
    dt.datetime(2026, 9, 7, 12, 0), prijzen_b, Tariff(), zonnig, geleerde_boiler(),
    tot=dt.datetime(2026, 9, 7, 23, 0),
)
piek_zon = [s for s in schijven_zon if planner.in_evening_peak(s.start)]
controle("met een dak dat 3 kW geeft mag de boiler wel in de avondpiek, tegen de terugleverprijs",
         len(piek_zon) == 2 and all(abs(s.price - 0.07) < 0.001 for s in piek_zon),
         f"{[(s.start.hour, round(s.price, 3)) for s in piek_zon]}")

# Zonder prijzen tot de klaar-tijd wordt er niets geraden (eis 6).
geen_prijzen = planner.plan_boiler(
    dt.datetime(2026, 9, 7, 19, 0), [], Tariff(), Forecast(), venster_b,
    geleerde_boiler(vol_sinds=dt.datetime(2026, 9, 7, 12, 0)),
)
controle("zonder prijzen en zonder vast tarief wacht hij",
         geen_prijzen.rule == "wait-for-prices" and not geen_prijzen.charge, f"{geen_prijzen}")

# Genoeg warm water: niets doen.
genoeg = planner.plan_boiler(
    dt.datetime(2026, 9, 8, 6, 45), prijzen_b, Tariff(), Forecast(),
    planner.Window(enabled=True, deadline=dt.datetime(2026, 9, 8, 7, 0)),
    geleerde_boiler(vol_sinds=dt.datetime(2026, 9, 8, 6, 40)),
)
# En een vat dat een dag geleden vol was, met een stekker die niets doet.
geen_stroom = planner.plan_boiler(
    dt.datetime(2026, 9, 8, 1, 0), prijzen_b, Tariff(), Forecast(), venster_b,
    geleerde_boiler(vol_sinds=dt.datetime(2026, 9, 7, 12, 0), vergeefs=3),
)
controle("na drie keer vergeefs stroom geven houdt hij ermee op en zegt waarom",
         geen_stroom.rule == "geen-stroom" and not geen_stroom.charge
         and "geen stroom" in geen_stroom.reason, f"{geen_stroom}")
controle("vlak na een volle beurt hoeft er niets bij",
         genoeg.rule == "genoeg" and not genoeg.charge, f"{genoeg}")

# Proefdraaien: even kijken of het vat nog warm is.
proef = planner.plan_boiler(
    dt.datetime(2026, 9, 7, 19, 0), prijzen_b, Tariff(), Forecast(), venster_b,
    geleerde_boiler(vol_sinds=dt.datetime(2026, 9, 7, 12, 0), proef_nodig=True),
)
controle("met proef_nodig zet hij hem even aan om te kijken",
         proef.rule == "proef" and proef.charge, f"{proef.reason}")

# Een vast contract heeft geen prijslijst en moet toch werken.
vast_b = planner.plan_boiler(
    dt.datetime(2026, 9, 7, 19, 0), [], Tariff(buy=0.28, feed_in=0.07), Forecast(), venster_b,
    geleerde_boiler(vol_sinds=dt.datetime(2026, 9, 7, 12, 0)),
)
controle("bij een vast tarief kiest hij gewoon een blok buiten de avondpiek",
         vast_b.rule in ("wait-for-cheap", "cheapest-hour")
         and (vast_b.starts_at is None or not planner.in_evening_peak(dt.datetime.fromisoformat(vast_b.starts_at))),
         f"{vast_b.rule} {vast_b.starts_at}")

print("=== 59. de tijdlijn zegt wat de paal doet, ook bij gelijke prijzen ===")
# Op de kaart stond bij een vast contract "14 A, laden op 9,4 kW" boven een paal
# die op 6 A liep, en "vol rond 15:00" terwijl het 15:32 werd. De oorzaak:
# `_decide` spreidt bij gelijke prijzen over alle uren (`easy-pace`) en
# `timeline` riep gewoon de knapzak aan, die de vroegste uren volpropt. Deze
# proef bewaakt dat de twee hetzelfde zeggen; die ontbrak, en daarom kon het
# erin blijven zitten.
NU59 = dt.datetime(2026, 9, 21, 14, 32)
KLAAR59 = Window(enabled=True, opens=None, deadline=dt.datetime(2026, 9, 22, 13, 0))
BUS59 = Car(capacity_kwh=65.0, phases=3, soc_percent=73.0, target_percent=80)
PAAL59 = Charger(max_amps=16.0, connected=True, charging=False, actual_amps=0.05)
NET59 = Grid(surplus_w=0.0, phase_amps=[4.0, 2.0, 2.0], fuse_amps=25.0)
# Hetzelfde plafond als het besluit ziet; anders vergelijk je twee sommen die
# van iets anders uitgaan.
PLAFOND59 = planner.ceiling_amps(NET59, BUS59, PAAL59)

besluit59 = decide(NU59, [], NET59, BUS59, PAAL59, KLAAR59, tariff=VAST)
plan59 = planner.timeline(NU59, [], NET59, BUS59, PAAL59, KLAAR59, PLAFOND59, VAST)
nu_blok = next((b for b in plan59.blocks if b.start <= NU59 < b.end), None)
print(f"  besluit: {besluit59.rule} {besluit59.amps} A     "
      f"tijdlijn nu: {nu_blok and nu_blok.amps} A, {nu_blok and nu_blok.kw} kW")
controle("bij gelijke prijzen doet hij rustig aan", besluit59.rule == "easy-pace",
         f"{besluit59.rule}")
controle("en de tijdlijn zegt dezelfde ampères als het besluit",
         nu_blok is not None and nu_blok.amps == besluit59.amps,
         f"tijdlijn {nu_blok and nu_blok.amps} A tegen besluit {besluit59.amps} A")
controle("dus niet het volle plafond in het eerste uur",
         nu_blok is not None and nu_blok.amps < PLAFOND59,
         f"{nu_blok and nu_blok.amps} A van {PLAFOND59}")

# En dan klopt "vol rond" ook: op dit tempo duurt het langer dan tot het hele uur.
print(f"  vol rond {plan59.expected_done:%H:%M}, gepland {plan59.planned_kwh:.1f} kWh "
      f"over {len([b for b in plan59.blocks if b.charging])} uren")
controle("wat er nodig is staat er ook helemaal in",
         abs(plan59.planned_kwh - planner.energy_needed_kwh(BUS59)) < 0.1,
         f"{plan59.planned_kwh:.2f} tegen {planner.energy_needed_kwh(BUS59):.2f}")
controle("en hij is niet binnen het eerste uur klaar",
         plan59.expected_done > dt.datetime(2026, 9, 21, 15, 0), f"{plan59.expected_done}")

# Een uur dat niets krijgt is bij gelijke prijzen niet duurder maar overbodig.
leeg59 = [b for b in plan59.blocks
          if not b.charging and not planner.in_evening_peak(b.start)]
redenen59 = {b.why for b in leeg59}
print(f"  redenen van de lege uren: {sorted(redenen59)[:3]}")
controle("een leeg uur heet niet duurder als alles even duur is",
         all("duurder dan wat hij nodig heeft" not in reden for reden in redenen59),
         f"{sorted(redenen59)}")

# Bij verschillende prijzen verandert er niets: dan is haasten wél wat waard en
# hoort de knapzak de goedkoopste uren vol te pakken.
prijzen59 = [
    {"start": dt.datetime(2026, 9, 21, 14 + i), "end": dt.datetime(2026, 9, 21, 15 + i),
     "price": 0.30 if i < 2 else 0.10}
    for i in range(9)
]
plan59b = planner.timeline(NU59, prijzen59, NET59, BUS59, PAAL59,
                           Window(enabled=True, opens=None,
                                  deadline=dt.datetime(2026, 9, 21, 23, 0)), PLAFOND59)
laadt59b = [b for b in plan59b.blocks if b.charging]
print(f"  met verschillende prijzen laadt hij in {[b.start.hour for b in laadt59b]} "
      f"op {[b.amps for b in laadt59b]} A")
controle("met verschillende prijzen laat hij de dure uren staan",
         bool(laadt59b) and all(b.price < 0.2 for b in laadt59b),
         f"{[(b.start.hour, b.price) for b in laadt59b]}")
controle("en spreidt hij niet, want daar is dan wel iets mee te winnen",
         len(laadt59b) <= 2, f"{[(b.start.hour, b.amps) for b in laadt59b]}")


print()
print("=== 60. een groep onder de aansluiting met een eigen zekering (22-09-2026) ===")
# De eerste woning: 3x25 A aan de meterkast achter de P1, en in de garage een
# onderverdeelkast van 3x16 A met een eigen meter, waar de paal aan hangt. Het
# huis trekt 6 A aan de meterkast en de garage 3 A: onder de hoofdzekering past
# 25 - 6 - 2 = 17, onder de garage 16 - 3 - 2 = 11. De paal kan 14.
Circuit, knelpunt, ruimten, ceiling_amps = planner.Circuit, planner.knelpunt, planner.ruimten, planner.ceiling_amps

garage = Circuit(name="Garage", phase_amps=[3.0, 2.0, 2.0], fuse_amps=16.0)
g60 = Grid(surplus_w=0.0, phase_amps=[6.0, 4.0, 4.0], fuse_amps=25.0, charger_amps=0.0, circuits=[garage])
zonder60 = Grid(surplus_w=0.0, phase_amps=[6.0, 4.0, 4.0], fuse_amps=25.0, charger_amps=0.0)
print(f"  ruimten: {ruimten(g60, paal(laadt=False))}")
controle("zonder groep begrenst de paal zelf: 14 A",
         ceiling_amps(zonder60, sven_auto(), paal(laadt=False)) == 14,
         f"{ceiling_amps(zonder60, sven_auto(), paal(laadt=False))}")
controle("met de garage van 16 A: 16 - 3 - 2 = 11 A",
         ceiling_amps(g60, sven_auto(), paal(laadt=False)) == 11,
         f"{ceiling_amps(g60, sven_auto(), paal(laadt=False))}")
controle("en de garage is de zekering die knelt",
         knelpunt(g60, sven_auto(), paal(laadt=False)) == "Garage",
         f"{knelpunt(g60, sven_auto(), paal(laadt=False))}")
controle("zonder groep knelt niets, want de paal zelf is de grens",
         knelpunt(zonder60, sven_auto(), paal(laadt=False)) is None,
         f"{knelpunt(zonder60, sven_auto(), paal(laadt=False))}")

# De paal laadt zelf op 10 A: die tien zitten in de meterkast én in de garage,
# en gaan er bij allebei af. De garage staat dan op 13 A en de coach mag nog
# steeds 11.
laadt60 = Grid(surplus_w=0.0, phase_amps=[16.0, 4.0, 4.0], fuse_amps=25.0, charger_amps=10.0,
               circuits=[Circuit(name="Garage", phase_amps=[13.0, 2.0, 2.0], fuse_amps=16.0)])
# (`paal(laadt=True)` kan hier niet meer: `middag` is verderop in dit bestand
# een besluit geworden.)
laadpaal60 = Charger(max_amps=14.0, connected=True, charging=True, actual_amps=10.0, limit_amps=10.0,
                     started_at=nu - dt.timedelta(hours=1))
controle("de eigen stroom van de paal telt op de groep niet als huis",
         ceiling_amps(laadt60, sven_auto(), laadpaal60) == 11,
         f"{ceiling_amps(laadt60, sven_auto(), laadpaal60)}")

# Een groep zonder meter: geen huis bekend, dus de zekering min de marge, en
# min wat er deze ronde al aan een andere paal op dezelfde groep is toegezegd.
blind60 = Grid(surplus_w=0.0, phase_amps=[6.0, 4.0, 4.0], fuse_amps=25.0, charger_amps=0.0,
               circuits=[Circuit(name="Carport", phase_amps=[], fuse_amps=16.0, reserved_amps=6.0)])
controle("een groep zonder meter: 16 - 2 - 6 toegezegd = 8 A",
         ceiling_amps(blind60, sven_auto(), paal(laadt=False)) == 8,
         f"{ceiling_amps(blind60, sven_auto(), paal(laadt=False))}")

# De zin op de kaart noemt de groep, want "onder je zekering" zegt bij een
# hoofdzekering van 25 A niets over een garage van 16.
vol60 = Grid(surplus_w=0.0, phase_amps=[6.0, 4.0, 4.0], fuse_amps=25.0, charger_amps=0.0,
             circuits=[Circuit(name="Garage", phase_amps=[13.0, 2.0, 2.0], fuse_amps=16.0)])
besluit60 = decide(nu, [], vol60, sven_auto(), paal(laadt=False), venster(nu), tariff=VAST, sun=ZON_RUIM)
print(f"  garage vol: {besluit60.rule} {besluit60.amps} A: {besluit60.reason}")
controle("is de garage vol, dan zegt de kaart dat het de garage is",
         besluit60.rule == "no-room" and "De groep Garage" in besluit60.reason, f"{besluit60.reason}")
import dataclasses as _dc  # noqa: E402
boost60 = decide(nu, [], g60, sven_auto(), _dc.replace(paal(laadt=False), boost=True), venster(nu),
                 tariff=VAST, sun=ZON_RUIM)
print(f"  snelladen: {boost60.amps} A: {boost60.reason}")
controle("bij snelladen noemt hij de zekering van de garage",
         boost60.amps == 11 and "de zekering van de groep Garage" in boost60.reason, f"{boost60.reason}")

print()
print("=== 61. zonder planning: de modus zon, continu of goedkoopst (v0.87.0) ===")
# De eigenaar op 23-09-2026, naar evcc: "de modus is leidend (snel, continu of
# zon), tenzij er een planning ingesteld is. Geen planning, standaard terug naar
# zon." Een eenfasige auto: de ondergrens is 6 A = 1,38 kW, en de zonregel
# begint op 90% daarvan.
nu = dt.datetime(2026, 8, 18, 13, 10)   # `middag` is hierboven een besluit geworden
geen_planning = Window(enabled=False)


def met_modus(modus, laadt=False, amps=6.0, continu=6):
    return Charger(max_amps=14.0, connected=True, charging=laadt, actual_amps=amps if laadt else 0.05,
                   started_at=nu - dt.timedelta(minutes=30) if laadt else None,
                   modus=modus, continu_amps=continu)


def zon_net(w, laadt_amps=0.0):
    return Grid(surplus_w=w, phase_amps=[4.0, 3.0, 2.0], fuse_amps=25.0, charger_amps=laadt_amps)


d61a = decide(nu, [], zon_net(800.0), sven_auto(), met_modus("zon"), geen_planning, tariff=VAST, sun=ZON_RUIM)
print(f"  zon, 0,8 kW: {d61a.rule} {d61a.amps} A: {d61a.reason}")
controle("zon: onder de ondergrens laadt hij niet, en zegt vanaf hoeveel",
         not d61a.charge and d61a.rule == "zon-wacht" and "1,4 kW" in d61a.reason, d61a.reason)

d61b = decide(nu, [], zon_net(2500.0), sven_auto(), met_modus("zon"), geen_planning, tariff=VAST, sun=ZON_RUIM)
print(f"  zon, 2,5 kW: {d61b.rule} {d61b.amps} A: {d61b.reason}")
controle("zon: met 2,5 kW overschot laadt hij op wat het dak geeft (10 A op een fase)",
         d61b.charge and d61b.rule == "zon-modus" and d61b.amps == 10, f"{d61b.amps} {d61b.rule}")

d61c = decide(nu, [], zon_net(800.0), sven_auto(soc=None), met_modus("zon"), geen_planning, tariff=VAST, sun=ZON_RUIM)
controle("zon: zonder accustand vraagt hij er niet om, want er valt niets te plannen",
         not d61c.needs_soc and d61c.rule == "zon-wacht", f"{d61c.rule} needs_soc={d61c.needs_soc}")

d61d = decide(nu, [], zon_net(0.0), sven_auto(), met_modus("continu", continu=8), geen_planning, tariff=VAST, sun=ZON_RUIM)
d61e = decide(nu, [], zon_net(3000.0), sven_auto(), met_modus("continu", continu=8), geen_planning, tariff=VAST, sun=ZON_RUIM)
print(f"  continu 8 A zonder zon: {d61d.amps} A; met 3 kW zon: {d61e.amps} A: {d61e.reason}")
controle("continu: zonder zon op het ingestelde vermogen",
         d61d.charge and d61d.amps == 8 and d61d.rule == "continu", f"{d61d.amps} {d61d.rule}")
controle("continu: met meer zon dan dat gaat hij mee omhoog (3 kW is 13 A)",
         d61e.charge and d61e.amps == 13 and "zon geeft meer" in d61e.reason, f"{d61e.amps} {d61e.reason}")
d61f = decide(nu, [], zon_net(0.0), sven_auto(), met_modus("continu", continu=32), geen_planning, tariff=VAST, sun=ZON_RUIM)
controle("continu: nooit boven wat paal en zekering toestaan (14 A)", d61f.amps == 14, f"{d61f.amps}")

piekuur = dt.datetime(2026, 8, 18, 18, 30)
d61g = decide(piekuur, [], zon_net(0.0), sven_auto(), met_modus("continu", continu=8), geen_planning, tariff=VAST, sun=ZON_RUIM)
print(f"  continu in de avondpiek, vast contract: {d61g.rule}: {d61g.reason}")
controle("continu bij een vast contract: in de avondpiek niets van het net (eis 4)",
         not d61g.charge and "avondpiek" in d61g.reason, d61g.reason)
dyn_prijzen = [{"start": piekuur.replace(minute=0) + dt.timedelta(hours=i),
                "end": piekuur.replace(minute=0) + dt.timedelta(hours=i + 1), "price": 0.30} for i in range(6)]
d61h = decide(piekuur, dyn_prijzen, zon_net(0.0), sven_auto(), met_modus("continu", continu=8), geen_planning,
              tariff=Tariff(), sun=ZON_RUIM)
controle("continu bij een dynamisch contract: de avondpiek is een gewoon uur",
         d61h.charge and d61h.amps == 8, f"{d61h.rule} {d61h.amps}")

d61i = decide(nu, [], zon_net(800.0), sven_auto(), met_modus("zon"), venster(nu), tariff=VAST, sun=ZON_RUIM)
print(f"  zon met schema aan: {d61i.rule}: {d61i.reason}")
controle("een planning wint: met het schema aan rekent hij naar de klaar-tijd en niet in de modus",
         d61i.rule not in ("zon-modus", "zon-wacht", "continu"), d61i.rule)

d61j = decide(nu, [], zon_net(800.0), sven_auto(), met_modus("goedkoopst"), geen_planning, tariff=VAST, sun=ZON_RUIM)
d61k = decide(nu, [], zon_net(800.0), sven_auto(), paal(laadt=False), geen_planning, tariff=VAST, sun=ZON_RUIM)
controle("goedkoopst is precies wat hij zonder schema altijd deed",
         (d61j.charge, d61j.amps, d61j.rule) == (d61k.charge, d61k.amps, d61k.rule) and d61j.rule not in ("zon-wacht", "zon-modus"),
         f"{d61j.rule} / {d61k.rule}")

d61l = decide(nu, [], zon_net(2500.0), sven_auto(soc=100.0), met_modus("zon"), geen_planning, tariff=VAST, sun=ZON_RUIM)
controle("zon: een auto op zijn doel laadt niet, ook niet op zon", not d61l.charge and d61l.rule == "complete", d61l.rule)

d61m = decide(nu, [], zon_net(300.0, laadt_amps=6.0), sven_auto(), met_modus("zon", laadt=True), geen_planning,
              tariff=VAST, sun=ZON_RUIM, holding=0)
print(f"  zon, wolk terwijl hij laadt: {d61m.rule} {d61m.amps} A")
controle("zon: een wolk breekt een lopende beurt niet meteen af (keep-alive op de ondergrens)",
         d61m.charge and d61m.amps == 6 and d61m.rule.endswith("+hold"), f"{d61m.rule} {d61m.amps}")

d61n = decide(nu, [], zon_net(800.0), sven_auto(), _dc.replace(met_modus("zon"), boost=True), geen_planning,
              tariff=VAST, sun=ZON_RUIM)
controle("snel gaat boven de modus", d61n.charge and d61n.rule == "boost", d61n.rule)

print()
print(f"{GOED} goed, {FOUT} fout")
sys.exit(1 if FOUT else 0)
