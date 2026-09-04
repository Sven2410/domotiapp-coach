"""Scenario's langs de rekenkern, zonder Home Assistant.

Elk geval is een situatie die vandaag bij Sven had kunnen staan, met de uitkomst
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
    """Een venster met klaar-tijd morgenvroeg, zoals bij Sven."""
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
            sun=ZON_KRAP, forecast=MIDDAGZON, holding=3)
print(f"  na drie ronden hysterese: {d2.rule} laden={d2.charge}")
controle("stopt na de hysterese", not d2.charge, f"kreeg {d2.rule}")
controle("en zegt wanneer hij dan wel begint", "15:00" in d2.plan or "15:00" in d2.reason,
         f"{d2.reason} / {d2.plan}")

print("=== 2. zonder zon op komst geldt de avondregel ===")
# Is er niets meer van het dak te verwachten, dan is elk uur even duur en valt er
# op prijs niets te kiezen. Dan blijft Svens afspraak van 20-08-2026 over: wacht
# tot acht uur, want dan zijn de pieken van koken voorbij.
d = decide(nu, [], NET_LEEG, sven_auto(), paal(), venster(nu), tariff=VAST,
           sun=ZON_KRAP, forecast=Forecast(), holding=3)
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
controle("biedt 10 A aan", d.charge and d.amps == 10, f"kreeg {d.amps} A via {d.rule}")
controle("heet ook zo", d.rule.endswith("+wake"))

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
           tariff=VAST, sun=ZON_RUIM, forecast=MIDDAGZON, holding=3)
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
# Wat er op 20-08-2026 om 15:48 bij Sven gebeurde. Auto op 12%, klaar om 06:00,
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
# Svens vraag van 20-08-2026: de klaar-tijd is een moment waarop de auto vol
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
# Sven op 20-08-2026, kwart voor zeven 's avonds: "hoezo is de laadpaal gestopt
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
# Sven op 20-08-2026: "op een vast contract is een kwartier speling niet
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
# Sven op 25-08-2026: op een vast contract is de nacht lang genoeg, dus de
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
           tariff=VAST, sun=ZON_RUIM, forecast=MIDDAG_ZON, holding=3)
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
# Sven op 20-08-2026 om 19:18. Hij plugde in, zette snelladen aan, en kreeg 8 A.
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
# Sven op 25-08-2026: "zo goedkoop mogelijk". Om negen uur is 0,9 kW overschot
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

d = ochtend_besluit(voorspeld=DAG_KROMME, holding=3)
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
# in de tekst, en dan valt de hele ronde om met een TypeError. Bij Sven had dat
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
# Sven op 26-08-2026, zijn eigen getal. Een kwartier is te krap bij een
# klaar-tijd overdag, en dat komt doordat de avondregel daar niet bij helpt:
# die zet een auto met een klaar-tijd 's nachts al om acht uur 's avonds aan,
# ruim voor het laatste moment dat nog past. Overdag is er geen avond die
# erbij hoort, en dan is dat kwartier het enige vangnet.
#
# Het is bewust geen nieuw begrip: de vraag "hoort er een avond bij" is
# dezelfde die `_evening_before` al beantwoordde.
# Sinds 04-09-2026 is het overal een uur. Sven: "De eindtijd is heel
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

# Svens eis van 04-09-2026: klaar om 07:00 betekent uiterlijk 06:00 vol. Met
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
# Svens meting van 20-08-2026. Hij zette snelladen aan, de coach schreef 16 A,
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
# Van den Dam op 29-08-2026 om 11:27:06, met de kabel er al uit: regel=no-room.
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
# De bus van Van den Dam, 29-08-2026: 65 kWh, 12,5% vol, aan een paal van 16 A.
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
# onder de 4,1 kW beginnen. Sven op 29-08-2026, gevraagd en akkoord: "het is niet
# erg dan 3 fase op ongeveer 4 kW laden, we moeten gebruikmaken van de zon."
controle("driefasig begint pas bij 4.140 W overschot",
         planner.watts_for(planner.MIN_AMPS, 3) == 4140.0,
         f"{planner.watts_for(planner.MIN_AMPS, 3)}")
controle("en eenfasig al bij 1.380 W",
         planner.watts_for(planner.MIN_AMPS, 1) == 1380.0,
         f"{planner.watts_for(planner.MIN_AMPS, 1)}")

print("=== 34. een volle aansluiting zet een lopende beurt niet meer uit ===")
# Bij Van den Dam meldde de huismeter op 30-08-2026 om 04:28:56 een enkel sample
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
# Nagemeten bij Van den Dam met `sensor.1_equalizer_limiet`. Op 29-08-2026 om
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
# Sven op 30-08-2026: "ik wil zien wat de coach van plan is met hele tijdlijn tot
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
# een uur vóór de klaar-tijd (Sven, 04-09-2026): 02, 03, 04 en 05.
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

print("=== 37. twee getallen uit twee momenten in een zin ===")
# Sven op 30-08-2026, tijdens het herstarten: "de equalizer staat op 18 A maar
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
# Gezien bij Van den Dam op 30-08-2026, met zijn eigen prijzen. Om 12:05 stond de
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
# Sven op 30-08-2026: "de coach zegt je levert nu 0,7 kW terug maar ik lever
# helemaal niks terug." Hij had gelijk, en de meter ook.
#
# De rauwe getallen van dat moment, om 13:11:46 bij Van den Dam:
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
VLOER39 = []
for uur in range(13, 19):
    start = dt.datetime(2026, 8, 18, uur, 0)
    VLOER39.append({"start": start, "end": start + dt.timedelta(hours=1),
                    "price": 0.30 if uur == 13 else 0.28, "feed_in": 0.02})
d39b = decide(nu39, VLOER39, NET39, BUS39, LAADT39, venster(nu39),
              tariff=VAST, sun=ZON_KRAP, holding=planner.STOP_ROUNDS)
print(f"  met 0,7 kW over: {d39b.rule}: {d39b.amps} A  {d39b.reason}")
controle("ook onder de ondergrens van de paal", "zon over" in d39b.reason
         and "levert" not in d39b.reason, f"{d39b.reason}")
controle("en dan op de ondergrens", d39b.amps == MIN_AMPS, f"{d39b.amps} A")

print("=== 40. alle scenario's tegen elkaar, met Van den Dams eigen cijfers ===")
# Sven op 30-08-2026: "lage kosten en zoveel mogelijk zon moet uit de strategie.
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
# Twee keer op 30-08-2026 stond er bij Van den Dam een ronde lang "je aansluiting
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
# die anders op een naijlende meting omhoog zou springen. Svens getallen van
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

print()
print(f"{GOED} goed, {FOUT} fout")
sys.exit(1 if FOUT else 0)
