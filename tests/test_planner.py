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
    Car, Charger, Decision, Grid, Sun, Tariff, Window, decide, MIN_AMPS,
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


print("=== 1. vast contract, zon schiet tekort, klaar-tijd morgenvroeg ===")
nu = middag(14, 37)
d = decide(nu, [], NET_LEEG, sven_auto(), paal(), venster(nu), tariff=VAST, sun=ZON_KRAP)
print(f"  {d.rule}: laden={d.charge} {d.amps} A  {d.reason}")
# Een lopende sessie wordt niet meteen afgebroken: drie ronden hysterese op de
# laagste stand hoort erbij. Waar het om gaat is dat hij niet naar vol vermogen
# springt, want dat was de klif van 14:37.
controle("geen vol vermogen meer", "fixed-tariff" not in d.rule and d.amps <= 6,
         f"kreeg {d.rule} met {d.amps} A")
controle("dit was de klif van 14:37", "wait-for-sun" in d.rule)

d2 = decide(nu, [], NET_LEEG, sven_auto(), paal(), venster(nu), tariff=VAST, sun=ZON_KRAP,
            holding=3)
print(f"  na drie ronden hysterese: {d2.rule} laden={d2.charge}")
controle("stopt na de hysterese", not d2.charge and d2.rule == "wait-for-sun",
         f"kreeg {d2.rule}")

print("=== 2. zelfde, maar zon belooft genoeg ===")
d = decide(nu, [], NET_LEEG, sven_auto(), paal(), venster(nu), tariff=VAST, sun=ZON_RUIM)
print(f"  {d.rule}: {d.reason}")
controle("wacht op de zon", d.rule.startswith("wait-for-sun") and d.amps <= 6,
         f"kreeg {d.rule} met {d.amps} A")

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
d = decide(nu, [], zonnig, sven_auto(), paal(laadt=False), venster(nu),
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

print("=== 12. de zonregel doet nog gewoon zijn werk ===")
d = decide(nu, [], zonnig, sven_auto(), paal(laadt=True, amps=5.7), venster(nu),
           tariff=VAST, sun=ZON_RUIM)
print(f"  {d.rule}: {d.amps} A  {d.reason}")
controle("laadt op de zon", d.charge and d.rule.startswith("surplus"), f"kreeg {d.rule}")

print("=== 13. valt de coach weg, dan loopt de pauze af op het laatste startmoment ===")
nu = middag(14, 37)
d = decide(nu, [], NET_LEEG, sven_auto(), paal(laadt=False), venster(nu),
           tariff=VAST, sun=ZON_RUIM)
# De 0 in de laadpaal krijgt precies de houdbaarheid tot het moment waarop de
# coach zelf weer zou beginnen. Valt Home Assistant om, dan gaat de paal vanaf
# dat moment gewoon zelf laden. Sinds de avondregel is dat acht uur 's avonds,
# dus vanaf 14:37 is dat 5,4 uur en niet meer de hele nacht.
uren = d.hold_minutes / 60
print(f"  {d.rule}: pauze {d.hold_minutes} minuten ({uren:.1f} uur)")
controle("loopt af op het moment dat de coach zelf zou beginnen",
         d.hold_minutes == 323, f"{d.hold_minutes} minuten")
controle("en dus ruim vóór de klaar-tijd", uren < 15.4, f"{uren:.1f} uur")

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
         net_erna.rule == "evening" and net_erna.charge, net_erna.rule)

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
controle("om acht uur gaat hij", d.charge and d.rule == "evening" and d.amps == 6,
         f"{d.rule} {d.amps} A")
# Sven op 25-08-2026: op een vast contract is de nacht lang genoeg, dus de
# aansluiting hoeft er niet vol voor open. 6 A driefasig is ruim 4 kW en dat is
# een derde van wat vol vermogen trekt.
controle("en dan op de ondergrens, niet op vol vermogen", d.amps == MIN_AMPS,
         f"{d.amps} A tegen ondergrens {MIN_AMPS} A")
controle("en hij zegt waarom hij rustig aan doet", "aansluiting" in d.reason, d.reason)

# En het gat dat dit dicht: wie om een uur 's nachts inplugt kreeg een kwartier
# speling. Nu laadt hij meteen, want de avondpiek is dan allang voorbij.
d = vast_besluit(dt.datetime(2026, 8, 21, 1, 0))
print(f"  01:00  {d.rule}: {d.amps} A")
controle("'s nachts geen kwartier speling meer",
         d.charge and d.rule == "evening", f"{d.rule}")

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
d = vast_besluit(dt.datetime(2026, 8, 20, 14, 0),
                 eind=dt.datetime(2026, 8, 20, 19, 0), soc=80.0, zon=ZON_RUIM)
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
                    klaar=KLAAR_MORGEN, nu=OCHTEND, prijzen=None):
    venster_ = Window(enabled=True, opens=None, deadline=klaar) if klaar else Window()
    return decide(nu, prijzen or [], net,
                  Car(capacity_kwh=19.7, phases=3, soc_percent=soc),
                  Charger(max_amps=16.0, connected=True, charging=False, actual_amps=0.0),
                  venster_, tariff=tarief, sun=zon)


d = ochtend_besluit()
print(f"  09:00 met 0,9 kW over en een zonnige dag  {d.rule}: {d.plan}")
controle("hij wacht op de zon van vandaag",
         not d.charge and d.rule == "wait-for-sun-today", f"{d.rule} {d.amps} A")
controle("en noemt beide getallen", "18,0 kWh" in d.reason and "15,3" in d.reason, d.reason)
controle("en zegt wanneer hij uiterlijk begint", "20:00" in d.plan, d.plan)

# Maar alleen als er iets te wachten valt. Zakt de verwachting onder wat er nog
# in moet, dan is elke kWh die nu niet gebruikt wordt teruggeleverd voor een
# fractie van wat hij kost, en dan hoort hij te pakken wat er is.
d = ochtend_besluit(zon=DAG_IS_OP)
print(f"  zelfde ochtend, maar de dag is op  {d.rule}: {d.amps} A")
controle("te weinig zon op komst: dan wel bijkopen",
         d.charge and d.rule == "surplus", f"{d.rule} {d.amps} A")

# Dekt de zon het laden al, dan valt er niets te wachten.
d = ochtend_besluit(net=VOLLE_ZON)
print(f"  zelfde ochtend met 6 kW over  {d.rule}: {d.amps} A")
controle("genoeg overschot: gewoon laden", d.charge and d.rule == "surplus",
         f"{d.rule} {d.amps} A")

# Zonder verwachting is er niets om op te wachten.
d = ochtend_besluit(zon=Sun(remaining_kwh=None, now_w=2200.0, next_w=2600.0))
print(f"  zonder zonverwachting  {d.rule}: {d.amps} A")
controle("geen verwachting, geen wachten", d.charge, f"{d.rule} {d.amps} A")

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
d = ochtend_besluit(tarief=Tariff(buy=0.34, feed_in=0.05), prijzen=dyn)
print(f"  dynamisch contract  {d.rule}: {d.amps} A")
controle("ook met prijzen wacht hij op eigen zon",
         not d.charge and d.rule == "wait-for-sun-today", f"{d.rule} {d.amps} A")

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
controle("maar zegt wel wat er aan zon komt", "18,0 kWh" in d.reason, d.reason)

# Met een accustand blijft de zin staan zoals hij was.
d = ochtend_besluit(soc=30.0)
controle("met accustand noemt hij beide getallen",
         "18,0 kWh" in d.reason and "15,3" in d.reason, d.reason)

print("=== 32. een klaar-tijd overdag krijgt een uur speling ===")
# Sven op 26-08-2026, zijn eigen getal. Een kwartier is te krap bij een
# klaar-tijd overdag, en dat komt doordat de avondregel daar niet bij helpt:
# die zet een auto met een klaar-tijd 's nachts al om acht uur 's avonds aan,
# ruim voor het laatste moment dat nog past. Overdag is er geen avond die
# erbij hoort, en dan is dat kwartier het enige vangnet.
#
# Het is bewust geen nieuw begrip: de vraag "hoort er een avond bij" is
# dezelfde die `_evening_before` al beantwoordde.
for uur, verwacht in ((6, 0.25), (8, 0.25), (12, 1.0), (19, 1.0), (21, 0.25), (23, 0.25)):
    eind_ = dt.datetime(2026, 8, 20, uur, 0)
    gekregen = planner._slack_hours(eind_)
    controle(f"klaar om {uur:02d}:00 krijgt {verwacht} uur speling",
             gekregen == verwacht, f"{gekregen} uur")

# En dat komt ook werkelijk in het laatste startmoment terecht.
controle("overdag begint hij een uur voor het krap wordt",
         planner._latest_start(dt.datetime(2026, 8, 20, 19, 0), 2.0)
         == dt.datetime(2026, 8, 20, 16, 0))
controle("'s nachts blijft het een kwartier",
         planner._latest_start(dt.datetime(2026, 8, 21, 6, 0), 2.0)
         == dt.datetime(2026, 8, 21, 3, 45))

# Zonder klaar-tijd valt er niets te rekenen, en dan hoort het kwartier te
# blijven staan in plaats van dat er een uur uit de lucht komt vallen.
controle("zonder klaar-tijd blijft het kwartier",
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

print()
print(f"{GOED} goed, {FOUT} fout")
sys.exit(1 if FOUT else 0)
