"""Controles op hele laadbeurten in het virtuele huis.

Elk scenario uit `scenarios.py` draait één keer helemaal door, en daarna wordt
er gekeken of de coach deed wat er van hem verwacht wordt: op tijd vol, geen
zekering over de kop, zon vóór net bij een vast contract, de goedkoopste uren
bij een dynamisch contract, en de juiste meldingen op het juiste moment.

Wat hier gemeten wordt is wat de bewoner merkt. Niet welke regel er in de
planner won, maar hoeveel kilowattuur er wanneer uit welk bron kwam, en of de
klaar-tijd gehaald is.

    python tests/test_virtueel.py             # alles, met de samenvatting per scenario
    python tests/test_virtueel.py vast        # alleen de scenario's met "vast" in de naam
"""

import sys

import scenarios
import virtueel
from virtueel import draai, samenvatting

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FOUT = 0
GOED = 0


def controle(naam, gelukt, uitleg=""):
    global FOUT, GOED
    if gelukt:
        GOED += 1
    else:
        FOUT += 1
        print(f"  FOUT  {naam}: {uitleg}")


filter_ = sys.argv[1] if len(sys.argv) > 1 else ""
V = {}
for sc in scenarios.ALLE:
    if filter_ and filter_ not in sc.naam:
        continue
    V[sc.naam] = draai(sc)
    print(samenvatting(V[sc.naam]))
print()


def v(naam):
    return V.get(naam)


def gehaald(verloop):
    if verloop.klaar_tijd is None:
        return True
    grens = min(verloop.scenario.auto.laadgrens, virtueel.planner.FULL_PERCENT)
    return verloop.soc_bij_klaar_tijd is not None and verloop.soc_bij_klaar_tijd >= grens


def meldingen(verloop, tekst):
    return [m for _, m in verloop.meldingen if tekst in m]


def regels_in(verloop, van, tot):
    """De regels tussen twee kloktijden, elke dag van de proef."""
    return [
        r for r in verloop.regels
        if virtueel._uur(van) <= r.tijd.hour + r.tijd.minute / 60 < virtueel._uur(tot)
    ]


def laadt_tussen(verloop, van, tot):
    return any(r.paal_w > 0 for r in regels_in(verloop, van, tot))


# Sinds 05-09-2026 mag een bekend uur dat goedkoper is dan het gemiddelde van
# alle bekende uren ook van het net, zolang de prijzen tot de klaar-tijd er nog
# niet zijn. De eigenaar, na een ochtend wachten in de klantwoning: "nu hebben we dus
# niks bespaard." De coach middelt over alles wat hij kent; hier benaderd als
# alle uren tot en met de dag van de regel.
def gemiddelde_tot(verloop, datum):
    per_uur = {}
    for r in verloop.regels:
        if r.tijd.date() <= datum and r.prijs is not None:
            per_uur.setdefault((r.tijd.date(), r.tijd.hour), r.prijs)
    return sum(per_uur.values()) / len(per_uur) if per_uur else None


def onder_gemiddelde(verloop, r):
    g = gemiddelde_tot(verloop, r.tijd.date())
    return g is not None and r.prijs is not None and r.prijs < g


def net_onder_gemiddelde(verloop, regels):
    """Meer van het net dan de ondergrens alleen in uren onder het gemiddelde."""
    return all(onder_gemiddelde(verloop, r) for r in regels
               if r.paal_w > r.over_w + 50 and r.paal_amps > 6.01)


# --- voor elk scenario --------------------------------------------------------

print("=== elk scenario: geen valse meldingen, geen onbekende regel, zekering heel ===")
for naam, vl in V.items():
    s = vl.scenario
    controle(f"{naam}: elke ronde gaf een besluit",
             not [r for r in vl.regels if r.regel in ("?", "")], "")
    controle(f"{naam}: geen fouten in het harnas", not vl.fouten, "; ".join(vl.fouten))
    # Een auto die vol is, is niet te laat. Tot 04-09-2026 kwam er elke ochtend
    # "was om 06:00 nog niet vol, hij staat nu op 100%".
    if gehaald(vl) and vl.klaar_tijd is not None:
        controle(f"{naam}: geen 'nog niet vol' over een auto die op tijd vol was",
                 not meldingen(vl, "nog niet vol"), f"{meldingen(vl, 'nog niet vol')}")
    # Hooguit een minuut boven de zekering. Dat is wat de coach nodig heeft:
    # de fasemeting wordt over anderhalve minuut gladgestreken (zie
    # `_gladde_fase` in coach.py), dus een echte sprong in het huisverbruik
    # heeft daar pas na een halve minuut de meerderheid. Een zekering houdt
    # dat; een coach die het langer laat lopen is fout.
    # Elke beurt staat in de opslag met wat hij kostte en bespaarde (de eigenaar op
    # 05-09-2026: "het belangrijkste voor de klant"). De kilowatturen erin
    # zijn dezelfde als het huis mat, en het geld is nooit verzonnen: zonder
    # prijs staat er geen besparing.
    if vl.geladen_kwh > 1:
        kwh_beurten = sum(b["kwh"] for b in vl.beurten)
        controle(f"{naam}: de beurten in de opslag tellen op tot wat er geladen is",
                 vl.beurten and abs(kwh_beurten - vl.geladen_kwh) <= max(0.5, 0.03 * vl.geladen_kwh),
                 f"{kwh_beurten:.1f} in {len(vl.beurten)} beurt(en) tegen {vl.geladen_kwh:.1f} geladen")
        controle(f"{naam}: zon in de beurten is niet meer dan het huis aan zon zag",
                 sum(b["solar_kwh"] for b in vl.beurten) <= vl.uit_zon_kwh + max(0.5, 0.05 * vl.geladen_kwh),
                 f"{sum(b['solar_kwh'] for b in vl.beurten):.1f} tegen {vl.uit_zon_kwh:.1f}")
        # Bespaard is de maat (vanaf het inpluggen op vol vermogen) min wat er
        # betaald is, en nooit onder nul. De eigenaar: "een min getal bij besparen
        # kan helemaal niet."
        controle(f"{naam}: bespaard is de maat min betaald, nooit onder nul, of onbekend",
                 all((b["saved"] is None and b["ref_cost"] is None)
                     or abs(b["saved"] - max(0.0, b["ref_cost"] - b["paid"])) < 0.001 for b in vl.beurten), "")
        # Het zondeel is wat de eigen zon scheelde tegenover inkopen: nooit meer
        # dan de zon-kilowatturen maal het verschil tussen inkoop en teruglevering.
        controle(f"{naam}: het zondeel van bespaard past bij de zon-kilowatturen",
                 all(0.0 <= b["solar_saved"] <= b["solar_kwh"] * 1.0 + 0.001 for b in vl.beurten),
                 f"{[(b['device'], b['solar_kwh'], b['solar_saved']) for b in vl.beurten]}")
    # Een minuut per keer dat er iets groots aangaat: `warmtepomp-nacht` zet
    # negenenveertig keer 22 A op één fase, en elke keer volgt de auto de
    # lagere limiet met zijn eigen aanloop van een halve minuut.
    over = [r for r in vl.regels if max(r.fase_amps) > s.zekering]
    sprongen = max(1, sum(1 for g in s.gebeurtenissen if g[1] == "oven"))
    controle(f"{naam}: de zekering wordt hooguit een minuut per sprong overschreden",
             len(over) * vl.stap_uur * 60 <= 1.0 * sprongen, f"{len(over) * vl.stap_uur * 60:.1f} minuten boven "
             f"{s.zekering} A, hoogste {vl.hoogste_fase:.1f} A, {sprongen} sprongen")
    # Alleen als de auto zijn accustand zelf meldt. Met een opgegeven stand
    # rekent de coach met de teller van de paal, en die loopt bij een Easee
    # tot een uur achter; dan zegt het verslag "staat op 87%" over een auto
    # die vol is. Dat staat open, zie waar-gebleven.md van 04-09-2026.
    # Een auto die al vol was toen de proef begon heeft geen beurt en dus geen
    # verslag; dat zijn de vaatwasserscenario's.
    if vl.klaar_op is not None and s.auto.laadgrens >= 100 and s.auto.meldt_soc and vl.geladen_kwh > 0.1:
        controle(f"{naam}: precies één keer 'is vol' gemeld",
                 len(meldingen(vl, "is vol")) == 1, f"{meldingen(vl, 'is vol')}")
    # De eigenaar op 04-09-2026: "De eindtijd is heel belangrijk. Een uur daarvoor
    # moet hij altijd klaar zijn." Vijf minuten speling voor de aanloop.
    # `afbouw-krap` is met opzet de beurt waarin de coach nog niet weet dat de
    # auto bovenin afbouwt: hij wordt vol in het laatste uur, en juist daarom
    # leert hij het; zie `afbouw-krap-geleerd`. `warmtepomp-nacht` is het huis
    # waar dat uur voor bedoeld is: een warmtepomp zonder patroon eet er een
    # deel van op, en het gemeten plafond (v0.61.0) ziet het opnieuw aanlopen
    # na elke onderbreking niet voordat er geladen wordt. Vol vóór de
    # klaar-tijd, en dat staat in zijn eigen controle.
    if (gehaald(vl) and vl.klaar_tijd is not None and vl.klaar_op is not None
            and naam not in ("afbouw-krap", "warmtepomp-nacht")):
        controle(f"{naam}: een uur voor de klaar-tijd al vol",
                 vl.klaar_op <= vl.klaar_tijd - virtueel.dt.timedelta(minutes=55),
                 f"vol om {vl.klaar_op:%H:%M}, klaar-tijd {vl.klaar_tijd:%H:%M}")
    # En nooit van het net in de avondpiek, welk contract ook. Alleen snelladen
    # en een klaar-tijd die anders niet gehaald wordt gaan daar overheen. Een
    # halve kilowattuur speling: de coach houdt een lopende beurt drie ronden
    # op de ondergrens aan voordat hij stopt (`_keep_alive`), en dat is bij een
    # driefasige auto 0,4 kWh over de grens heen.
    # Sinds v0.79.0 alleen bij een vast contract: bij dynamisch is de piek een
    # gewoon uur op zijn prijs (de bewoner van de eerste woning, 22-09-2026).
    if (naam not in ("snelladen", "vast-onhaalbare-klaar-tijd", "eenfase-krappe-zekering")
            and vl.scenario.contract.startswith("vast")):
        controle(f"{naam}: niets van het net in de avondpiek",
                 vl.net_kwh_tussen("18:00", "20:00") < 0.6,
                 f"{vl.net_kwh_tussen('18:00', '20:00'):.2f} kWh tussen 18:00 en 20:00")

# --- vast contract: zon voor net, net pas na de avondpiek ---------------------

print("=== vast contract ===")
if (vl := v("vast-zonnig")):
    controle("zonnig: alles uit de zon", vl.uit_net_kwh < 0.3, f"net {vl.uit_net_kwh:.2f} kWh")
    controle("zonnig: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    controle("zonnig: één keer aan, één keer uit", vl.wissels() <= 2, f"{vl.wissels()} wissels")
    controle("zonnig: niet duurder dan het optimum plus een cent",
             vl.optimum is not None and vl.kosten <= vl.optimum + 0.02,
             f"kosten {vl.kosten:.2f}, optimum {vl.optimum}")
    controle("zonnig: de coach begint zodra er genoeg zon over is, zonder eerst bij te kopen",
             not laadt_tussen(vl, "07:00", "08:30"), "laadde al voor 08:30")

# Dezelfde dag aan een Alfen (23-09-2026): dezelfde uitkomst, maar via een
# number zonder houdbaarheid en zonder startwoord. Wat hier bewaakt wordt is
# dat de coach de limiet elke minuut opnieuw schrijft, want anders valt de
# paal na zijn geldigheidsduur terug op zijn veilige stroom en laadt de auto
# op 16 A door terwijl de coach 0 zei.
if (va := v("alfen-vast-zonnig")) and (vz := v("vast-zonnig")):
    controle("alfen: dezelfde kilowatturen als aan een Easee",
             abs(va.geladen_kwh - vz.geladen_kwh) < 0.3, f"alfen {va.geladen_kwh:.2f}, easee {vz.geladen_kwh:.2f}")
    controle("alfen: dezelfde kosten als aan een Easee",
             abs(va.kosten - vz.kosten) < 0.03, f"alfen {va.kosten:.2f}, easee {vz.kosten:.2f}")
    controle("alfen: op tijd vol", gehaald(va), f"{va.soc_bij_klaar_tijd}")
    controle("alfen: er gaat nooit een startwoord of een Easee-dienst heen",
             not any(d in ("action_command", "set_charger_dynamic_limit") for _, d, _ in va.opdrachten),
             f"{sorted({d for _, d, _ in va.opdrachten})}")
    controle("alfen: de paal viel nooit terug op zijn veilige stroom", va.paal_terugvallen == 0, f"{va.paal_terugvallen} keer")
    schrijf = [t for t, d, _ in va.opdrachten if d == "set_value"]
    gaten = [(b - a).total_seconds() for a, b in zip(schrijf, schrijf[1:])]
    controle("alfen: zolang er een auto hangt gaat de limiet elke minuut opnieuw de number in",
             schrijf and max(gaten) <= 61, f"grootste gat {max(gaten) if gaten else None} s over {len(schrijf)} opdrachten")

if (va := v("alfen-dynamisch-zonnig")) and (vz := v("dynamisch-zonnig")):
    controle("alfen dynamisch: dezelfde kosten als aan een Easee",
             abs(va.kosten - vz.kosten) < 0.03, f"alfen {va.kosten:.2f}, easee {vz.kosten:.2f}")
    controle("alfen dynamisch: de pauze op 0 A wordt elke minuut opnieuw geschreven en de paal valt niet terug",
             va.paal_terugvallen == 0 and not laadt_tussen(va, "07:00", "10:59"),
             f"{va.paal_terugvallen} keer teruggevallen")

if (va := v("alfen-doel-80")) and (vz := v("doel-80")):
    controle("alfen doel 80: stopt rond 80% en blijft daar, want de 0 wordt elke minuut opnieuw geschreven",
             va.soc_bij_klaar_tijd is not None and 79 <= va.soc_bij_klaar_tijd <= 84 and va.paal_terugvallen == 0,
             f"soc {va.soc_bij_klaar_tijd}, {va.paal_terugvallen} keer teruggevallen")
    controle("alfen doel 80: evenveel geladen als aan een Easee",
             abs(va.geladen_kwh - vz.geladen_kwh) < 0.3, f"alfen {va.geladen_kwh:.2f}, easee {vz.geladen_kwh:.2f}")

if (vl := v("vast-bewolkt")):
    controle("bewolkt: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    # Vóór acht uur komt er alleen net bij als aanvulling onder de ondergrens
    # van de paal: er is zon, alleen niet genoeg voor 6 A, en dan is bijkopen
    # tot die 6 A goedkoper dan die zon weggeven en 's nachts alles kopen. Zie
    # `charge_cost` en de "vloer" in `schijven`. Nooit méér dan dat.
    controle("bewolkt: vóór de avondpiek hooguit de ondergrens bijgekocht",
             all(r.paal_amps <= 6.01 for r in regels_in(vl, "00:00", "20:00") if r.paal_w > r.over_w + 50),
             f"{vl.net_kwh_tussen('00:00', '20:00'):.2f} kWh van het net voor acht uur")
    controle("bewolkt: de zon die er was is gebruikt", vl.uit_zon_kwh > 5, f"{vl.uit_zon_kwh:.1f}")
    controle("bewolkt: na acht uur rustig aan", bool(vl.regels_met("easy-pace")), "geen easy-pace")
    # De wekronde telt niet mee: die biedt met opzet het hele plafond aan en
    # duurt één ronde, zie `WAKE_AMPS` in planner.py.
    controle("bewolkt: rustig aan is nooit vol vermogen",
             all(r.amps < 16 for r in vl.regels_met("easy-pace") if "+wake" not in r.regel),
             "16 A in easy-pace")

if (vl := v("vast-geen-panelen")):
    controle("geen panelen: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    controle("geen panelen: niets voor acht uur 's avonds",
             not laadt_tussen(vl, "07:00", "20:00"), "laadde overdag")
    controle("geen panelen: rustig tempo", bool(vl.regels_met("easy-pace")), "geen easy-pace")
    controle("geen panelen: rustig aan haalt de klaar-tijd zonder sprint",
             not vl.regels_met("deadline"), "de klaar-tijdregel moest het redden")

if (vl := v("vast-wisselend")):
    controle("wisselend: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    controle("wisselend: niet elke wolk een stop", vl.wissels() <= 8, f"{vl.wissels()} wissels")
    controle("wisselend: nauwelijks van het net", vl.uit_net_kwh < 1.5, f"{vl.uit_net_kwh:.2f}")

if (vl := v("vast-salderen")):
    controle("salderen: eigen zon blijft goedkoper dan het net", vl.uit_net_kwh < 0.3,
             f"net {vl.uit_net_kwh:.2f}")
    controle("salderen: op tijd vol", gehaald(vl), "")

if (vl := v("vast-avond-erin")):
    controle("avond erin: wacht tot acht uur", not laadt_tussen(vl, "18:30", "20:00"), "")
    controle("avond erin: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

if (vl := v("vast-grote-auto")):
    controle("grote auto: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    controle("grote auto: de zon van de hele dag gebruikt", vl.uit_zon_kwh > 30, f"{vl.uit_zon_kwh:.1f}")
    controle("grote auto: vóór de avond hooguit de ondergrens bijgekocht",
             all(r.paal_amps <= 6.01 for r in regels_in(vl, "00:00", "20:00") if r.paal_w > r.over_w + 50),
             f"{vl.net_kwh_tussen('00:00', '20:00'):.2f} kWh van het net voor acht uur")

for naam in ("vast-zonder-voorspelling", "vast-sensor-voorspelling"):
    if (vl := v(naam)):
        controle(f"{naam}: alles uit de zon", vl.uit_net_kwh < 0.3, f"net {vl.uit_net_kwh:.2f}")
        controle(f"{naam}: op tijd vol", gehaald(vl), "")

if (vl := v("vast-voorspelling-mis")):
    controle("voorspelling mis: de klaar-tijd wordt toch gehaald", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

if (vl := v("vast-geen-klaar-tijd")):
    controle("geen klaar-tijd: toch vol op zon", vl.klaar_op is not None and vl.uit_net_kwh < 0.3,
             f"vol {vl.klaar_op}, net {vl.uit_net_kwh:.2f}")

if (vl := v("vast-krappe-klaar-tijd")):
    controle("krap: meteen vol vermogen", vl.regels[6].amps == 16, f"{vl.regels[6].regel} {vl.regels[6].amps} A")
    controle("krap: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

if (vl := v("vast-onhaalbare-klaar-tijd")):
    controle("onhaalbaar: laadt door na de klaar-tijd", bool(vl.regels_met("overdue")), "")
    controle("onhaalbaar: zegt één keer dat het niet gehaald is",
             len(meldingen(vl, "17:00 nog niet vol")) == 1, f"{meldingen(vl, 'nog niet vol')}")
    controle("onhaalbaar: en daarna dat hij vol is", len(meldingen(vl, "is vol")) == 1, "")

# --- dynamisch contract: zon, prijs, teruglevering en salderen tegen elkaar ---

print("=== dynamisch contract ===")
for naam in ("dynamisch-zonnig", "dynamisch-markt", "dynamisch-negatief-middag",
             "dynamisch-prijzen-laat", "dynamisch-salderen"):
    if (vl := v(naam)):
        controle(f"{naam}: alles uit de zon", vl.uit_net_kwh < 0.3, f"net {vl.uit_net_kwh:.2f}")
        controle(f"{naam}: op tijd vol", gehaald(vl), "")
        controle(f"{naam}: binnen twee cent van het optimum",
                 vl.optimum is not None and vl.kosten <= vl.optimum + 0.02,
                 f"kosten {vl.kosten:.2f}, optimum {vl.optimum}")

if (vl := v("dynamisch-zonnig")) and (vm := v("dynamisch-markt")):
    controle("kale marktprijs en all-in geven hetzelfde besluit",
             abs(vl.kosten - vm.kosten) < 0.01, f"{vl.kosten:.3f} tegen {vm.kosten:.3f}")

# De marge op het optimum is wat de regel "alleen zon tot de prijzen bekend
# zijn" kost: om 07:00 kent de coach alleen vandaag, dus het goedkope uur van
# 12:00 laat hij liggen en hij plant pas om 13:00. Het optimum kent alles. Bij
# de bus is dat drie dubbeltjes, bij de grote auto anderhalve euro. De eigenaar kent
# die getallen (notities 04-09-2026) en koos de regel.
for naam, marge in (("dynamisch-bewolkt", 0.35), ("dynamisch-geen-panelen", 0.35),
                    ("dynamisch-avond-erin", 0.10), ("dynamisch-grote-auto", 1.50)):
    if (vl := v(naam)):
        controle(f"{naam}: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
        controle(f"{naam}: niets van het net in de dure avonduren",
                 vl.net_kwh_tussen("18:00", "21:00") < 0.6, f"{vl.net_kwh_tussen('18:00', '21:00'):.2f} kWh")
        controle(f"{naam}: niet duurder dan het optimum plus wat de prijsregel kost",
                 vl.optimum is not None and vl.kosten <= vl.optimum + marge,
                 f"kosten {vl.kosten:.2f}, optimum {vl.optimum}")

if (vl := v("dynamisch-bewolkt")):
    controle("dynamisch bewolkt: de zon die er was is gebruikt", vl.uit_zon_kwh > 5, f"{vl.uit_zon_kwh:.1f}")

if (vl := v("dynamisch-geen-klaar-tijd")):
    controle("dynamisch zonder klaar-tijd: wordt uiteindelijk vol op zon",
             vl.klaar_op is not None and vl.uit_net_kwh < 0.3, f"vol {vl.klaar_op}")

# --- de meter en de aansluiting ----------------------------------------------

print("=== meter en aansluiting ===")
if (vz := v("vast-zonnig")):
    for naam in ("meter-met-teken", "meter-teken-omgekeerd", "met-lastbewaker"):
        if (vl := v(naam)):
            controle(f"{naam}: zelfde uitkomst als met een gesplitste meter",
                     abs(vl.geladen_kwh - vz.geladen_kwh) < 0.2 and vl.uit_net_kwh < 0.3,
                     f"{vl.geladen_kwh:.1f} tegen {vz.geladen_kwh:.1f}, net {vl.uit_net_kwh:.2f}")

if (vl := v("eenfase-krappe-zekering")):
    controle("krappe zekering: tijdens het koken terug naar de laagste stand",
             all(r.paal_amps <= 6.01 for r in regels_in(vl, "17:35", "19:00")),
             f"hoogste {max(r.paal_amps for r in regels_in(vl, '17:35', '19:00')):.0f} A")
    controle("krappe zekering: maar niet uit", any(r.paal_amps > 0 for r in regels_in(vl, "18:00", "19:00")), "")
    controle("krappe zekering: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

if (vl := v("oven-tijdens-laden")):
    controle("oven: binnen een meetstap terug",
             all(max(r.fase_amps) <= vl.scenario.zekering for r in regels_in(vl, "02:01", "02:30")),
             f"hoogste {max(max(r.fase_amps) for r in regels_in(vl, '02:01', '02:30')):.1f} A")
    controle("oven: na de oven weer verder", laadt_tussen(vl, "02:35", "04:00"), "")
    controle("oven: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

# de klantwoning, nacht van 09 op 10-09-2026: een warmtepomp die om het kwartier
# aangaat. Zonder de meting van het plafond (v0.61.0) begon de coach om 01:02
# op de goedkoopste uren en stond de auto om 06:00 op 84%.
if (vl := v("warmtepomp-nacht")):
    controle("warmtepomp: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    controle("warmtepomp: begint vóór 23:00 en zegt dat er gemeten minder overbleef",
             laadt_tussen(vl, "22:00", "23:00")
             and any("gemiddeld" in r.reden and "A over voor de paal" in r.reden
                     for r in regels_in(vl, "22:00", "23:30")), "")
# de klantwoning, nacht van 18 op 19-09-2026: na een verlaging voor de zekering
# bleef de Ford nog tien minuten op de oude stroom, en de coach schreef dat op
# als zijn tempo (5,52 kW voor band 6 waar hij 10 kW trok). Tot v0.69.0 leerde
# hij hier {7: 6,9, 9: 6,9}, en bleven de oude rijen staan.
if (vl := v("ford-bijkomen")):
    controle("ford bijkomen: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    controle("ford bijkomen: de minuten na een verlaging worden geen tempo", not vl.geleerd,
             f"{vl.geleerd}")
if (vl := v("ford-oude-opslag")):
    controle("ford oude opslag: een te laag bewaard tempo vervalt zodra hij meer trekt",
             not vl.geleerd, f"{vl.geleerd}")
if (vl := v("warmtepomp-uit")):
    controle("warmtepomp uit: een rustig huis wacht gewoon op de nacht",
             not laadt_tussen(vl, "20:00", "00:30") and gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    controle("warmtepomp uit: en betaalt het optimum",
             vl.optimum is not None and vl.betaald <= vl.optimum + 0.02, f"{vl.betaald:.2f} tegen {vl.optimum:.2f}")

# --- de auto -----------------------------------------------------------------

print("=== de auto ===")
if (vl := v("accustand-onbekend")):
    controle("accustand onbekend: vraagt er één keer om",
             len(meldingen(vl, "Geef de accustand door")) == 1, f"{meldingen(vl, 'accustand')}")
    controle("accustand onbekend: koopt niets van het net zonder te weten",
             vl.uit_net_kwh < 0.3, f"{vl.uit_net_kwh:.2f}")
    controle("accustand onbekend: zon gaat er wel in", vl.uit_zon_kwh > 10, f"{vl.uit_zon_kwh:.1f}")

if (vl := v("accustand-opgegeven")):
    controle("accustand opgegeven: daarna geen no-soc meer",
             not [r for r in regels_in(vl, "07:31", "23:59") if "no-soc" in r.regel], "")
    controle("accustand opgegeven: op tijd vol", gehaald(vl), "")

if (vl := v("accustand-traag")):
    controle("trage app: geen extra wissels", vl.wissels() <= 2, f"{vl.wissels()}")
    controle("trage app: op tijd vol", gehaald(vl), "")

if (vl := v("laadgrens-80")):
    controle("laadgrens: zegt dat de auto niet verder laadt op 80%",
             bool(meldingen(vl, "staat op 80%")), f"{[m for _, m in vl.meldingen]}")
    controle("laadgrens: zegt niet dat hij vol is", not meldingen(vl, "is vol"), "")
    controle("laadgrens: geen 'nog niet vol' in de ochtend", not meldingen(vl, "nog niet vol"), "")

# Dezelfde auto met de 80% ook in het profiel. het gemeten geval van
# 16-09-2026: de coach hoort zelf op te houden, zonder herstart en zonder
# kritieke melding over een auto die precies deed wat hem gevraagd was.
if (vl := v("laadgrens-80-ingesteld")):
    controle("doel gelijk aan de laadgrens: zegt dat verder niet hoeft",
             bool(meldingen(vl, "verder hoefde hij niet")), f"{[m for _, m in vl.meldingen]}")
    controle("doel gelijk aan de laadgrens: geen laadgrens-gok",
             not meldingen(vl, "Mogelijk staat er een laadgrens"), "")
    controle("doel gelijk aan de laadgrens: geen herstart",
             not meldingen(vl, "opnieuw gestart"), "")
    controle("doel gelijk aan de laadgrens: zegt niet dat hij vol is",
             not meldingen(vl, "is vol"), "")
    controle("doel gelijk aan de laadgrens: stopt rond 80%",
             vl.soc_bij_klaar_tijd is not None and 79 <= vl.soc_bij_klaar_tijd <= 82,
             f"{vl.soc_bij_klaar_tijd}")

# En het omgekeerde: de auto zou doorladen, de bewoner wil op 80 stoppen. Dan is
# de coach degene die ophoudt, en hij laadt dus minder dan tot vol.
if (vl := v("doel-80")):
    controle("doel onder de auto: stopt rond 80%",
             vl.soc_bij_klaar_tijd is not None and 79 <= vl.soc_bij_klaar_tijd <= 84,
             f"{vl.soc_bij_klaar_tijd}")
    controle("doel onder de auto: geen herstart",
             not meldingen(vl, "opnieuw gestart"), "")
    controle("doel onder de auto: laadt minder dan tot vol",
             vl.geladen_kwh < 11.5, f"{vl.geladen_kwh:.2f}")

# de eigen Ford meldt zijn accustand per tien procent, ongeveer elk half uur.
# Tussen twee stappen stond het beeld van de coach stil terwijl de bus voller
# werd: op 17-09-2026 om 22:26 zei de kaart "nog 2,2 kWh, vol rond 23:00"
# terwijl er 0,18 kWh in ging en de bus om 22:29 op zijn doel stond. Sinds
# v0.68.0 telt hij op wat de paal sinds die stap geleverd heeft. Gemiddeld over
# de beurt zat hij er 0,63 kWh naast, nu 0,19.
if (vl := v("accustand-per-tien")):
    auto70 = vl.scenario.auto
    fouten = [
        r.nodig_kwh - max(0.0, (auto70.doel - r.soc) / 100 * auto70.capaciteit_kwh / 0.9)
        for r in vl.regels if r.nodig_kwh is not None
    ]
    gemiddeld = sum(fouten) / len(fouten) if fouten else 0.0
    controle("accustand per tien: 'nog te laden' klopt gemiddeld binnen 0,3 kWh",
             fouten and gemiddeld < 0.3, f"gemiddeld {gemiddeld:+.2f} kWh ernaast")
    controle("accustand per tien: en hij rekent nooit te laag",
             all(f > -0.5 for f in fouten), f"laagste {min(fouten):+.2f} kWh")
    controle("accustand per tien: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

if (vl := v("bijna-vol")):
    controle("bijna vol: laadt het restje", 0.5 < vl.geladen_kwh < 2.0, f"{vl.geladen_kwh:.2f}")
    controle("bijna vol: één melding", len(meldingen(vl, "is vol")) == 1, "")

if (vl := v("auto-wordt-niet-wakker")):
    controle("slapende auto: meldt dat hij geen stroom afneemt",
             bool(meldingen(vl, "geen stroom af")), "")
    # Sinds 17-09-2026 biedt de coach het hele plafond aan om te wekken, dus een
    # auto die hier nog stilstaat wordt door niets meer wakker. Dan is het enige
    # dat telt dat de bewoner het weet en dat de coach het blijft proberen.
    controle("slapende auto: hij blijft stroom aanbieden tot het laatst",
             vl.regels and vl.regels[-1].amps >= 6, f"{vl.regels[-1].amps if vl.regels else None}")
    controle("slapende auto: en hij meldt dat de klaar-tijd gemist is",
             bool(meldingen(vl, "nog niet vol")), "")

# --- de nacht van 05 op 06-09-2026 in de klantwoning ---------------------------
#
# De Easee koos één fase, de Ford trok 16,9 A op een groep van 16 A, de paal
# herstartte, de Ford ging in storing en bleef op 86% staan tot een start met
# de hand. De eigenaar: de fasemodus blijft, dus de coach rekent met wat er loopt,
# blijft onder de groep, en start een auto die niet vol is zelf opnieuw.

print("=== storing, één fase, de groep, en een auto die bovenin afbouwt ===")
if (vl := v("ford-storing")):
    controle("storing: de coach start de paal één keer opnieuw en zegt dat",
             len(meldingen(vl, "opnieuw gestart")) == 1, f"{[m for _, m in vl.meldingen]}")
    controle("storing: de auto komt daarna gewoon vol", gehaald(vl) and vl.klaar_op is not None,
             f"{vl.klaar_op}")
    controle("storing: geen 'laadt niet verder' over een auto die weer ging",
             not meldingen(vl, "laadt niet verder"), f"{meldingen(vl, 'laadt niet verder')}")
    controle("storing: precies een verslag", len(meldingen(vl, "is vol")) == 1, "")

if (vl := v("easee-een-fase-groep")):
    controle("één fase, groep zichtbaar: de paal hoeft nooit zelf te herstarten",
             vl.paal_herstarts == 0, f"{vl.paal_herstarts}")
    controle("één fase, groep zichtbaar: geen storing en geen herstart door de coach",
             not meldingen(vl, "opnieuw gestart"), f"{meldingen(vl, 'opnieuw gestart')}")
    # De eerste minuten vraagt hij 16, tot hij ziet dat de auto 16,9 trekt. De
    # nachtsessie begint de paal weer op drie fasen, en daar is 16 gewoon goed.
    een_fase = [r for r in vl.regels if r.paal_w > 0 and r.paal_w / (r.paal_amps * 230) < 1.5]
    controle("één fase, groep zichtbaar: op één fase vraagt hij daarna hooguit 15 A, de groep min het overschot",
             len([r for r in een_fase if r.amps > 15]) <= 5,
             f"{len([r for r in een_fase if r.amps > 15])} ronden boven 15 A op één fase")
    controle("één fase, groep zichtbaar: de tip zegt dat hij met één fase rekent",
             bool(meldingen(vl, "rekent deze beurt met die ene fase")), "")
    controle("één fase, groep zichtbaar: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

if (vl := v("easee-een-fase-blind")):
    controle("één fase, groep onzichtbaar: de paal herstart zelf, zoals in de klantwoning",
             vl.paal_herstarts >= 1, f"{vl.paal_herstarts}")
    controle("één fase, groep onzichtbaar: de auto gaat in storing en de coach start hem opnieuw",
             len(meldingen(vl, "opnieuw gestart")) >= 1, f"{[m for _, m in vl.meldingen]}")
    controle("één fase, groep onzichtbaar: en zo komt hij alsnog vol", gehaald(vl),
             f"{vl.soc_bij_klaar_tijd}")

if (vl := v("afbouw-boven-80")):
    controle("afbouw: de coach leert wat de bus boven 80% aanneemt, 8 A op één fase",
             all(abs(vl.geleerd.get(b, 0) - 1.84) < 0.05 for b in (8, 9)), f"{vl.geleerd}")
    controle("afbouw: en niets over de banden waar de paal de rem was",
             not [b for b in vl.geleerd if b < 8], f"{vl.geleerd}")

if (vk := v("afbouw-krap")) and (vg := v("afbouw-krap-geleerd")):
    eerste = lambda vl: next((r.tijd for r in vl.regels if r.paal_w > 0), None)
    controle("afbouw krap: zonder te weten pas na middernacht begonnen en tot in het laatste uur bezig",
             eerste(vk) is not None and eerste(vk).hour == 0 and vk.klaar_op is not None
             and vk.klaar_op.hour == 5 and vk.klaar_op.minute > 5,
             f"begin {eerste(vk)}, vol {vk.klaar_op}")
    controle("afbouw krap: met de geleerde banden begint hij meteen en is hij voor 05:00 vol",
             eerste(vg) is not None and eerste(vg) < eerste(vk) and vg.klaar_op is not None
             and vg.klaar_op <= vg.klaar_tijd - virtueel.dt.timedelta(hours=1) + virtueel.dt.timedelta(minutes=5),
             f"begin {eerste(vg)}, vol {vg.klaar_op}, klaar-tijd {vg.klaar_tijd}")
    controle("afbouw krap: allebei op tijd vol", gehaald(vk) and gehaald(vg), "")

# --- 17-09-2026 thuis: de wekstroom en de fasekeuze van de paal ---------------
#
# De Easee koos bij een wekstroom van tien ampère één fase. Sinds de wekstroom
# op zestien staat kiest hij er drie, en dan is er niets aan de hand: geen
# melding, geen klaar-tijdregel, en een beurt die vlak tegen het optimum aan
# zit. Oud: één fase vanaf 08:31, vol pas dinsdag 04:47, € 10,30. Nieuw: vol
# maandag 22:50, € 9,60, optimum € 9,59.
if (vl := v("easee-fasekeuze")):
    controle("fasekeuze: de paal begint op drie fasen, dus geen fasemelding",
             not meldingen(vl, "op één fase geladen"), "")
    controle("fasekeuze: de wekstroom is het hele plafond",
             any(r.regel.endswith("+wake") and r.amps == 16 for r in vl.regels),
             f"{[r.amps for r in vl.regels if r.regel.endswith('+wake')]}")
    controle("fasekeuze: de klaar-tijdregel hoeft er niet aan te pas te komen",
             not any(r.regel.startswith("deadline") for r in vl.regels),
             f"{[r.regel for r in vl.regels if r.regel.startswith('deadline')][:3]}")
    controle("fasekeuze: vol ruim voor de klaar-tijd, en dicht bij het optimum",
             gehaald(vl) and vl.kosten <= vl.optimum * 1.02,
             f"{vl.kosten:.2f} tegen optimum {vl.optimum:.2f}")

# --- 17-09-2026 thuis: de zonbelofte die opschoof ----------------------------
#
# De voorspeller beloofde 1,552 kWh voor het uur van 16:00, het dak deed 0,58 en
# het huis at het op. De coach zei om 15:42 "ik laad om 16:00", om 16:03 "ik
# laad om 17:00", en zou dat om 17:00 weer verschoven hebben. De eigenaar: "waarom ging
# hij niet laden om 16 uur terwijl hij net zei ik ga laden om 16 uur?"
#
# Allebei de contracten, want dat was zijn tweede vraag: "je weet ook dat dit
# thuis een vast contract is, dus ik weet niet hoe het met een dynamisch moet."
if (vl := v("zonbelofte-vast")):
    na15 = [r for r in vl.regels if r.tijd.hour >= 15 and r.tijd.hour < 20]
    # Oud: 15:05 "wacht op je eigen zon van 16:00", 16:05 "van 17:00".
    controle("zonbelofte vast: hij belooft geen zonuur meer dat zijn meter tegenspreekt",
             not any("eigen zon van" in r.reden for r in na15),
             f"{next((r.reden[:80] for r in na15 if 'eigen zon van' in r.reden), '')}")
    controle("zonbelofte vast: en hij zegt erbij dat hij de verwachting bijgesteld heeft",
             any("Je dak gaf" in r.reden for r in na15), "")
    controle("zonbelofte vast: het kost hem niets, hij zit op het optimum",
             vl.optimum is not None and vl.kosten <= vl.optimum * 1.02,
             f"{vl.kosten:.2f} tegen optimum {vl.optimum:.2f}")
    controle("zonbelofte vast: en op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

if (vl := v("zonbelofte-dynamisch")):
    # Bij een dynamisch contract houdt zo'n uur zijn eigen netschijf, dus er
    # gaat niets verloren; wat verdwijnt is de korting die op een voorspelling
    # rustte. Oud: € 3,12 en vol om 02:18. Nieuw: € 2,99, optimum € 2,95.
    controle("zonbelofte dynamisch: dichter bij het optimum dan de 3,12 van v0.66.0",
             vl.optimum is not None and vl.kosten <= vl.optimum * 1.02,
             f"{vl.kosten:.2f} tegen optimum {vl.optimum:.2f}")
    controle("zonbelofte dynamisch: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

# Een meting van zaterdag hoort zondag met rust te laten. In die woning liep de zin
# op 17-09-2026 tussen 17:46 en 20:00 op van "50% minder" naar "86% minder", en
# dat klopte voor die uren: de voorspeller zei 769 Wh voor 19:00 en 406 voor
# 20:00 terwijl het dak op nul stond. Zonder `solar_day` zou zo'n meting bij
# zonsondergang ook de volgende dag inkrimpen, en bij een klaar-tijd die over
# een dag heen loopt is dat duur. Oud: 23,0 kWh zon en € 10,80. Nieuw: 37,6 kWh
# zon en € 9,35, bij een optimum van € 8,00.
if (vl := v("weekend-voorspelling-mis")):
    controle("weekend: de zon van zondag wordt niet weggestreept door zaterdag",
             vl.uit_zon_kwh > 30, f"{vl.uit_zon_kwh:.1f} kWh uit zon")
    controle("weekend: en dat scheelt tegenover de 10,80 van v0.67.1",
             vl.kosten < 10.0, f"{vl.kosten:.2f}")
    controle("weekend: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

# --- de vaatwasser (06-09-2026) ----------------------------------------------
#
# De eigenaar: "nu verder met de vaatwasser sturing." De bewoner geeft vrij, de coach
# kiest het goedkoopste startmoment binnen het schema, drukt op de knop en
# meldt één keer dat hij klaar is.

print("=== de vaatwasser ===")
def vw_klok(moment):
    return None if moment is None else moment.strftime("%a %H:%M")

if (vl := v("vaatwasser-avond")):
    # Het goedkoopste uur van de nacht is 02:00 (0,060, gelijk aan 03:00, en
    # van twee gelijke wint de vroegste). Tot 08-09-2026 was het 01:00, want
    # uitgesmeerd over 225 minuten telde het gemiddelde van vier uur.
    controle("vaatwasser avond: om 19:00 vrijgegeven, gestart om 02:00, het goedkoopste uur van de nacht",
             vl.vw_gestart is not None and vl.vw_gestart.hour == 2 and vl.vw_gestart.minute <= 1,
             f"gestart {vw_klok(vl.vw_gestart)}")
    controle("vaatwasser avond: niets in de avondpiek", not (vl.vw_gestart and 17 <= vl.vw_gestart.hour < 20), "")
    controle("vaatwasser avond: klaar voor 07:00", vl.vw_klaar is not None and vl.vw_klaar.hour < 7,
             f"klaar {vw_klok(vl.vw_klaar)}")
    controle("vaatwasser avond: één keer gedrukt", len(vl.vw_gedrukt) == 1, f"{vl.vw_gedrukt}")
    controle("vaatwasser avond: precies een verslag, met kWh en wat er bespaard is",
             len(meldingen(vl, "Vaatwasser is klaar")) == 1 and "Bespaard €" in meldingen(vl, "Vaatwasser is klaar")[0],
             f"{[m for _, m in vl.meldingen]}")
    controle("vaatwasser avond: geen kritieke melding", not meldingen(vl, "niet gaan draaien"), "")
    controle("vaatwasser avond: de beurt staat in de opslag met een besparing",
             any(b["device"] == "vaatwasser" and (b["saved"] or 0) > 0 for b in vl.beurten),
             f"{[(b['device'], b['kwh'], b['paid'], b['saved']) for b in vl.beurten]}")

if (vl := v("vaatwasser-zon")):
    # Om 08:00 belooft de verwachting 0,5 kW over, om 09:00 2,2 kW: het eerste
    # uur dat de opwarmpiek van 2,1 kW draagt. Tot 08-09-2026 startte hij om
    # 08:00, want uitgesmeerd paste Eco (213 W) in die 0,5 kW.
    controle("vaatwasser zon: bij een vast contract start hij op het eerste uur waarvan de zon de piek draagt, 09:00",
             vl.vw_gestart is not None and virtueel.dt.time(8, 58) <= vl.vw_gestart.time() <= virtueel.dt.time(9, 1),
             f"gestart {vw_klok(vl.vw_gestart)}")
    controle("vaatwasser zon: klaar voor 18:00", vl.vw_klaar is not None and vl.vw_klaar.hour < 18, f"{vw_klok(vl.vw_klaar)}")
    controle("vaatwasser zon: een verslag", len(meldingen(vl, "Vaatwasser is klaar")) == 1, "")

if (vl := v("vaatwasser-krap")):
    controle("vaatwasser krap: om 03:00 vrijgegeven met klaar om 07:00 start hij meteen",
             vl.vw_gestart is not None and vl.vw_gestart.hour == 3 and vl.vw_gestart.minute <= 2,
             f"gestart {vw_klok(vl.vw_gestart)}")
    controle("vaatwasser krap: en is nog net op tijd klaar", vl.vw_klaar is not None and vl.vw_klaar.hour < 7,
             f"{vw_klok(vl.vw_klaar)}")

if (vl := v("vaatwasser-afstand-uit")):
    controle("afstand uit: de coach drukt twee keer, niet vaker", len(vl.vw_gedrukt) == 2, f"{vl.vw_gedrukt}")
    controle("afstand uit: en zegt na drie minuten dat hij niet gaat draaien",
             len(meldingen(vl, "niet gaan draaien")) == 1 and "starten op afstand" in meldingen(vl, "niet gaan draaien")[0],
             f"{[m for _, m in vl.meldingen]}")
    controle("afstand uit: hij draait niet en er komt geen verslag",
             vl.vw_gestart is None and not meldingen(vl, "is klaar"), "")

# Home Connect Local (thuis sinds 23-09-2026): een knop die er niet altijd
# is, het programma in twee entiteiten, de resterende tijd in uren.
if (vl := v("vaatwasser-lokaal")) and (vz := v("vaatwasser-zon")):
    controle("lokaal: dezelfde start als aan de cloud (09:00 op zon)",
             vl.vw_gestart is not None and vz.vw_gestart is not None and abs((vl.vw_gestart - vz.vw_gestart).total_seconds()) <= 60,
             f"lokaal {vw_klok(vl.vw_gestart)}, cloud {vw_klok(vz.vw_gestart)}")
    controle("lokaal: dezelfde kilowatturen en kosten", abs(vl.vw_kwh - vz.vw_kwh) < 0.01 and abs(vl.vw_betaald - vz.vw_betaald) < 0.005,
             f"lokaal {vl.vw_kwh:.2f} kWh €{vl.vw_betaald:.3f}, cloud {vz.vw_kwh:.2f} kWh €{vz.vw_betaald:.3f}")
    controle("lokaal: één druk, en het programma herkend aan de spelling eco50",
             len(vl.vw_gedrukt) == 1 and any("Eco 50" in m for _, m in vl.meldingen), f"{vl.vw_gedrukt} {[m for _, m in vl.meldingen]}")
    controle("lokaal: 'is gestart' met een klaar-tijd uit de uren van de sensor",
             any("is gestart" in m and "klaar rond" in m for _, m in vl.meldingen), f"{[m for _, m in vl.meldingen]}")

if (vl := v("vaatwasser-lokaal-deur-open")):
    controle("lokaal, deur open: de coach drukt niet op een knop die er niet is",
             not [t for t in vl.vw_gedrukt if t.hour == 3 and t.minute < 8], f"{[vw_klok(t) for t in vl.vw_gedrukt]}")
    controle("lokaal, deur open: na drie minuten één keer dat de deur open staat",
             len(meldingen(vl, "neemt nu geen start aan")) == 1 and "deur staat open" in meldingen(vl, "neemt nu geen start aan")[0],
             f"{[m for _, m in vl.meldingen]}")
    controle("lokaal, deur open: zodra de deur dichtgaat drukt hij, één keer, en de beurt loopt",
             len(vl.vw_gedrukt) == 1 and vl.vw_gestart is not None and vl.vw_gestart.hour == 3 and 8 <= vl.vw_gestart.minute <= 10,
             f"gedrukt {[vw_klok(t) for t in vl.vw_gedrukt]}, gestart {vw_klok(vl.vw_gestart)}")
    controle("lokaal, deur open: geen 'niet gaan draaien', wel een verslag",
             not meldingen(vl, "niet gaan draaien") and len(meldingen(vl, "is klaar")) == 1, f"{[m for _, m in vl.meldingen]}")

if (vl := v("vaatwasser-lokaal-afstand-uit")):
    controle("lokaal, afstand uit: de coach drukt geen enkele keer", not vl.vw_gedrukt, f"{vl.vw_gedrukt}")
    controle("lokaal, afstand uit: en zegt één keer wat er aan moet",
             len(meldingen(vl, "starten op afstand")) == 1 and not meldingen(vl, "niet gaan draaien"), f"{[m for _, m in vl.meldingen]}")

if (vl := v("vaatwasser-uiterlijk-starten")):
    controle("uiterlijk starten om 22:00: hij start om 22:00, ook al is de nacht goedkoper",
             vl.vw_gestart is not None and vl.vw_gestart.hour == 22 and vl.vw_gestart.minute <= 1,
             f"gestart {vw_klok(vl.vw_gestart)}")

# De domme vaatwasser op een meetstekker (06-09-2026 's avonds). De eigenaar: "wel
# adviseren en meten, met zet hem aan", en zijn schema: vanaf 08:00, klaar
# om 16:30, nooit in de nacht.
if (vl := v("vaatwasser-dom-zon")):
    vraag = vl.vw_gevraagd[0] if vl.vw_gevraagd else None
    print(f"  dom zon: gevraagd {vw_klok(vraag)}, aangezet {[vw_klok(t) for t in vl.vw_gedrukt]}, klaar {vw_klok(vl.vw_klaar)}")
    controle("dom zon: 's avonds vrijgegeven, en de coach vraagt niets in de nacht",
             vraag is not None and vraag.date() > virtueel.dt.date(2026, 9, 7), f"{vw_klok(vraag)}")
    controle("dom zon: hij vraagt tussen 08:00 en 12:15, in de zon",
             vraag is not None and virtueel.dt.time(8, 0) <= vraag.time() <= virtueel.dt.time(12, 15), f"{vw_klok(vraag)}")
    controle("dom zon: de vraag komt op de telefoon, één keer",
             len(meldingen(vl, "Zet Vaatwasser nu aan")) == 1, f"{meldingen(vl, 'Zet Vaatwasser')}")
    controle("dom zon: de bewoner zet hem vijf minuten later aan en de coach ziet dat aan het vermogen",
             len(vl.vw_gedrukt) == 1 and vl.vw_gestart is not None and vl.vw_gestart == vl.vw_gedrukt[0], f"{vl.vw_gedrukt} {vl.vw_gestart}")
    controle("dom zon: klaar voor 16:30", vl.vw_klaar is not None and vl.vw_klaar.time() < virtueel.dt.time(16, 30), f"{vw_klok(vl.vw_klaar)}")
    controle("dom zon: één verslag, met de tijden erin", len(meldingen(vl, "Vaatwasser is klaar")) == 1
             and "Eco 50" in meldingen(vl, "Vaatwasser is klaar")[0], f"{meldingen(vl, 'is klaar')}")
    controle("dom zon: geen herinnering nodig", not meldingen(vl, "nog steeds uit"), "")
    m = vl.vw_gemeten[0] if vl.vw_gemeten else {}
    print(f"  dom zon: gemeten {m.get('minutes')} min, {m.get('kwh')} kWh, piek {m.get('peak_w')} W, profiel {len(m.get('profile') or [])} stappen: {(m.get('profile') or [])[:5]} ... {(m.get('profile') or [])[-3:]}")
    controle("dom zon: de beurt is gemeten: duur, verbruik, piek",
             len(vl.vw_gemeten) == 1 and 215 <= m.get("minutes", 0) <= 240 and 0.9 <= m.get("kwh", 0) <= 1.1
             and 1100 <= m.get("peak_w", 0) <= 1300 and m.get("runs") == 1, f"{m}")
    profiel = m.get("profile") or []
    controle("dom zon: het profiel laat de opwarmpiek aan het begin en het drogen aan het eind zien",
             40 <= len(profiel) <= 48 and profiel[0] >= 1000 and profiel[2] >= 1000 and profiel[len(profiel) // 2] < 100
             and profiel[-2] >= 1000, f"{profiel}")

if (vl := v("vaatwasser-dom-leert")):
    print(f"  dom leert: beurten {[(vw_klok(a), vw_klok(b), g) for a, b, g in vl.vw_beurten]}")
    controle("dom leert: twee beurten, elk op zijn eigen dag", len(vl.vw_beurten) == 2
             and vl.vw_beurten[0][0].date() != vl.vw_beurten[1][0].date(), f"{vl.vw_beurten}")
    controle("dom leert: de eerste met de opgave, de tweede met de meting",
             len(vl.vw_beurten) == 2 and vl.vw_beurten[0][2] is False and vl.vw_beurten[1][2] is True, f"{vl.vw_beurten}")
    controle("dom leert: na twee beurten telt de meting twee beurten",
             vl.vw_gemeten and vl.vw_gemeten[0].get("runs") == 2, f"{vl.vw_gemeten}")
    controle("dom leert: allebei klaar voor 16:30 en allebei na 08:00 gevraagd",
             all(b[1] is not None and b[1].time() < virtueel.dt.time(16, 30) for b in vl.vw_beurten)
             and all(virtueel.dt.time(8, 0) <= t.time() for t in vl.vw_gevraagd), f"{vl.vw_gevraagd}")

if (vl := v("vaatwasser-dom-negeert")):
    print(f"  dom negeert: {[m for _, m in vl.meldingen]}")
    controle("dom negeert: één vraag en één herinnering, en verder niets",
             len(meldingen(vl, "Zet Vaatwasser nu aan")) == 1 and len(meldingen(vl, "nog steeds uit")) == 1
             and vl.vw_gestart is None and not meldingen(vl, "is klaar"), f"{[m for _, m in vl.meldingen]}")
    controle("dom negeert: de herinnering komt drie kwartier na de vraag",
             len(vl.meldingen) >= 2 and (vl.meldingen[1][0] - vl.meldingen[0][0]) == virtueel.dt.timedelta(minutes=45),
             f"{[t for t, _ in vl.meldingen]}")

if (vl := v("vaatwasser-dom-zelf")):
    print(f"  dom zelf: gestart {vw_klok(vl.vw_gestart)}, klaar {vw_klok(vl.vw_klaar)}, meldingen {[m for _, m in vl.meldingen]}")
    controle("dom zelf: zonder vrijgave vraagt de coach niets", not vl.vw_gevraagd and not meldingen(vl, "Zet Vaatwasser"), "")
    controle("dom zelf: maar hij ziet de beurt aan het vermogen, meldt hem en meet hem",
             vl.vw_gestart is not None and vl.vw_gestart.hour == 6 and len(meldingen(vl, "Vaatwasser is klaar")) == 1
             and len(vl.vw_gemeten) == 1, f"{vl.vw_gemeten}")

if (vl := v("vaatwasser-eigen-tabel")):
    print(f"  eigen tabel: gestart {vw_klok(vl.vw_gestart)}, klaar {vw_klok(vl.vw_klaar)}")
    controle("eigen tabel: met Eco op 150 minuten past 03:30 nog voor 07:00, dus de gewone regel en geen paniekstart",
             vl.vw_gestart is not None and vl.vw_klaar is not None and vl.vw_klaar.time() < virtueel.dt.time(7, 0)
             and not any("niet klaar" in m or "haalt" in m for _, m in vl.meldingen), f"{[m for _, m in vl.meldingen]}")
    controle("eigen tabel: de beurt is gemeten met de echte 150 minuten",
             vl.vw_gemeten and 140 <= vl.vw_gemeten[0].get("minutes", 0) <= 160, f"{vl.vw_gemeten}")

if (vl := v("vaatwasser-gemeten")):
    print(f"  gemeten: gestart {vw_klok(vl.vw_gestart)}, beurten {[(vw_klok(a), vw_klok(b), g) for a, b, g in vl.vw_beurten]}")
    controle("gemeten: de coach plant met het gemeten programma", vl.vw_beurten and vl.vw_beurten[0][2] is True, f"{vl.vw_beurten}")
    controle("gemeten: hij start pas als de zon er is, niet om 08:00 op het net",
             vl.vw_gestart is not None and vl.vw_gestart.hour >= 9, f"{vw_klok(vl.vw_gestart)}")
    controle("gemeten: na de beurt telt de meting twee beurten", vl.vw_gemeten and vl.vw_gemeten[0].get("runs") == 2, f"{vl.vw_gemeten}")

if (vl := v("vaatwasser-meter-wint")):
    print(f"  meter wint: gestart {vw_klok(vl.vw_gestart)}, klaar {vw_klok(vl.vw_klaar)}")
    controle("meter wint: met 3 kW teruglevering op de meter start hij om 10:20, niet op de verwachting van later",
             vl.vw_gestart is not None and (vl.vw_gestart.hour, vl.vw_gestart.minute) <= (10, 22), f"gestart {vw_klok(vl.vw_gestart)}")
    controle("meter wint: klaar rond 11:20, ruim voor 16:30",
             vl.vw_klaar is not None and (vl.vw_klaar.hour, vl.vw_klaar.minute) <= (11, 30), f"{vw_klok(vl.vw_klaar)}")

if (vl := v("vaatwasser-vroeg")):
    vw_beurt = [b for b in vl.beurten if b["device"] == "vaatwasser"]
    print(f"  vroeg: gestart {vw_klok(vl.vw_gestart)}, klaar {vw_klok(vl.vw_klaar)}, beurt {[(b['kwh'], b['solar_kwh'], b['paid'], b['ref_cost'], b['saved']) for b in vw_beurt]}")
    # Hij start pas als de meter van het lopende uur op de som wint van wat de
    # voorspeller (de helft) voor de middag belooft, na 10:00. Tot 08-09-2026
    # startte hij om 09:12: uitgesmeerd paste Eco in 250 W.
    controle("vroeg (08-09): met 250 W over om 09:12 start hij niet, want de opwarmpiek past daar niet in",
             vl.vw_gestart is not None and vl.vw_gestart.hour >= 10, f"gestart {vw_klok(vl.vw_gestart)}")
    controle("vroeg: en hij is voor 16:30 klaar", vl.vw_klaar is not None and vl.vw_klaar < vl.vw_klaar.replace(hour=16, minute=30), f"{vw_klok(vl.vw_klaar)}")
    # Om 10:22 zag de meter 1,2 kW en droeg de eerste opwarmpiek voor de helft;
    # de rest van de beurt is zon. Met een kloppende verwachting (hieronder)
    # wacht hij tot 12:00 en is het alles.
    controle("vroeg: de beurt draait grotendeels op eigen zon",
             len(vw_beurt) == 1 and vw_beurt[0]["solar_kwh"] >= 0.75 * vw_beurt[0]["kwh"], f"{vw_beurt}")
    # De maat is alles van het net bij het vrijgeven (de eigenaar op 09-09-2026), en
    # wat de zon scheelde staat apart in het zondeel van bespaard.
    controle("vroeg: de maat is alles van het net bij het vrijgeven, en het zondeel is de zon tegen het verschil",
             len(vw_beurt) == 1 and vw_beurt[0]["ref_cost"] is not None
             and abs(vw_beurt[0]["ref_cost"] - vw_beurt[0]["kwh"] * vl.scenario.vast_prijs) < 0.01 * vw_beurt[0]["ref_cost"]
             and vw_beurt[0]["solar_saved"] > 0
             and vw_beurt[0]["solar_saved"] <= vw_beurt[0]["saved"] + 0.001, f"{vw_beurt}")

if (vl := v("vaatwasser-vroeg-verwacht")):
    vw_beurt = [b for b in vl.beurten if b["device"] == "vaatwasser"]
    print(f"  vroeg, verwachting klopt: gestart {vw_klok(vl.vw_gestart)}, klaar {vw_klok(vl.vw_klaar)}, beurt {[(b['kwh'], b['solar_kwh'], b['paid'], b['saved']) for b in vw_beurt]}")
    controle("vroeg met een kloppende verwachting: hij wacht tot de zon de piek draagt, niet voor 11:30",
             vl.vw_gestart is not None and (vl.vw_gestart.hour, vl.vw_gestart.minute) >= (11, 30), f"gestart {vw_klok(vl.vw_gestart)}")
    controle("vroeg met een kloppende verwachting: klaar voor 16:30 en helemaal op zon",
             vl.vw_klaar is not None and vl.vw_klaar < vl.vw_klaar.replace(hour=16, minute=30)
             and len(vw_beurt) == 1 and vw_beurt[0]["solar_kwh"] >= 0.95 * vw_beurt[0]["kwh"], f"{vw_klok(vl.vw_klaar)} {vw_beurt}")

if (vl := v("vaatwasser-zonpiek")):
    vw_beurt = [b for b in vl.beurten if b["device"] == "vaatwasser"]
    print(f"  zonpiek: gestart {vw_klok(vl.vw_gestart)}, klaar {vw_klok(vl.vw_klaar)}, beurt {[(b['kwh'], b['solar_kwh'], b['paid'], b['saved']) for b in vw_beurt]}")
    # Tot 11-09-2026 startte hij om 09:32, op de opklaring: 2,4 kW over was
    # meer dan de piek van 2264 W, en de opwarmpieken kwamen daarna van het
    # net. Nu telt de laagste teruglevering van tien minuten (METER_VENSTER).
    controle("zonpiek (11-09): op een opklaring van zes minuten start hij niet",
             vl.vw_gestart is not None and not (9 <= vl.vw_gestart.hour < 10), f"gestart {vw_klok(vl.vw_gestart)}")
    controle("zonpiek: hij start op zon die blijft, en de beurt is grotendeels zon",
             len(vw_beurt) == 1 and vw_beurt[0]["solar_kwh"] >= 0.9 * vw_beurt[0]["kwh"], f"{vw_beurt}")
    controle("zonpiek: en hij is voor 16:30 klaar",
             vl.vw_klaar is not None and (vl.vw_klaar.hour, vl.vw_klaar.minute) < (16, 30), f"{vw_klok(vl.vw_klaar)}")

if (vl := v("vaatwasser-eindtijd")):
    gestart_m = [(t, m) for t, m in vl.meldingen if "Vaatwasser is gestart" in m]
    print(f"  eindtijd: gestart {vw_klok(vl.vw_gestart)}, klaar {vw_klok(vl.vw_klaar)}, melding {[(f'{t:%H:%M}', m) for t, m in gestart_m]}")
    # Tot 11-09-2026 zei de melding "klaar rond 10:45": de eindtijd die Home
    # Connect om 09:45 bij het kiezen zette.
    controle("eindtijd (11-09): de melding noemt de eindtijd van de beurt, niet die van het kiezen",
             len(gestart_m) == 1 and vl.vw_klaar is not None and f"klaar rond {vl.vw_klaar:%H:%M}." in gestart_m[0][1],
             f"{gestart_m} klaar {vw_klok(vl.vw_klaar)}")
    controle("eindtijd: en de melding komt binnen twee minuten na de start",
             len(gestart_m) == 1 and vl.vw_gestart is not None
             and (gestart_m[0][0] - vl.vw_gestart).total_seconds() <= 120, f"{gestart_m} gestart {vw_klok(vl.vw_gestart)}")

if (vl := v("vaatwasser-eindtijd-bijstellen")):
    gestart_m = [(t, m) for t, m in vl.meldingen if "Vaatwasser is gestart" in m]
    print(f"  eindtijd bijstellen: gestart {vw_klok(vl.vw_gestart)}, klaar {vw_klok(vl.vw_klaar)}, melding {[(f'{t:%H:%M}', m) for t, m in gestart_m]}")
    # Tot 15-09-2026 zei de melding de eindtijd die Home Connect bij de start
    # neerzette, en die stelde hij een minuut later twaalf minuten bij.
    controle("eindtijd bijstellen (15-09): de melding noemt de bijgestelde eindtijd, niet die van de start",
             len(gestart_m) == 1 and vl.vw_klaar is not None and f"klaar rond {vl.vw_klaar:%H:%M}." in gestart_m[0][1],
             f"{gestart_m} klaar {vw_klok(vl.vw_klaar)}")
    controle("eindtijd bijstellen: en hij wacht daar hooguit EINDTIJD_WACHT op",
             len(gestart_m) == 1 and vl.vw_gestart is not None
             and (gestart_m[0][0] - vl.vw_gestart).total_seconds() <= 240, f"{gestart_m} gestart {vw_klok(vl.vw_gestart)}")

if (vl := v("vaatwasser-na-klaartijd")):
    print(f"  na de klaar-tijd, morgen: gestart {vw_klok(vl.vw_gestart)}, klaar {vw_klok(vl.vw_klaar)}, {vl.vw_kwh:.2f} kWh, {len(vl.vw_gedrukt)} keer gedrukt")
    # De eigenaar op 12-09-2026: om 16:33 vrijgegeven bij klaar om 16:30.
    controle("na de klaar-tijd (12-09): ingeruimd en morgen starten start niet meer vandaag, maar morgen tussen 08:00 en 15:00",
             vl.vw_gestart is not None and "2026-09-08 08:00" <= f"{vl.vw_gestart:%Y-%m-%d %H:%M}" < "2026-09-08 15:00",
             f"{vl.vw_gestart}")
    controle("na de klaar-tijd: en morgen klaar voor 16:30",
             vl.vw_klaar is not None and f"{vl.vw_klaar:%Y-%m-%d %H:%M}" <= "2026-09-08 16:30", f"{vl.vw_klaar}")
    controle("na de klaar-tijd: één keer gedrukt en één verslag",
             len(vl.vw_gedrukt) == 1 and len(meldingen(vl, "Vaatwasser is klaar")) == 1, f"{vl.vw_gedrukt}")

if (vl := v("vaatwasser-na-klaartijd-nu")):
    print(f"  na de klaar-tijd, nu: gestart {vw_klok(vl.vw_gestart)}, klaar {vw_klok(vl.vw_klaar)}, {vl.vw_kwh:.2f} kWh, meldingen {[m for _, m in vl.meldingen if 'Vaatwasser' in m]}")
    # De eigenaar op 13-09-2026: "of ingeruimd en nu starten."
    controle("nu starten (13-09): hij start binnen twee minuten na 16:33, dezelfde dag",
             vl.vw_gestart is not None and "2026-09-07 16:33" <= f"{vl.vw_gestart:%Y-%m-%d %H:%M}" <= "2026-09-07 16:35",
             f"{vl.vw_gestart}")
    controle("nu starten: één keer gedrukt, één keer 'is gestart' en één verslag",
             len(vl.vw_gedrukt) == 1 and len(meldingen(vl, "Vaatwasser is gestart")) == 1
             and len(meldingen(vl, "Vaatwasser is klaar")) == 1, f"{vl.vw_gedrukt} {[m for _, m in vl.meldingen]}")

if (vl := v("vaatwasser-herstart")):
    print(f"  herstart: gestart {vw_klok(vl.vw_gestart)}, klaar {vw_klok(vl.vw_klaar)}, {vl.vw_kwh:.2f} kWh, meldingen {[m for _, m in vl.meldingen if 'Vaatwasser' in m]}")
    controle("herstart: gestart om 02:00, en na de herstart om 03:00 zegt hij niet nog eens dat hij draait",
             vl.vw_gestart is not None and vl.vw_gestart.hour == 2 and len(meldingen(vl, "Vaatwasser is gestart")) == 1
             and not meldingen(vl, "Vaatwasser draait"), f"{[m for _, m in vl.meldingen]}")
    controle("herstart: één verslag, over de hele beurt vanaf 02:00",
             len(meldingen(vl, "Vaatwasser is klaar")) == 1 and "van 02:0" in meldingen(vl, "Vaatwasser is klaar")[0]
             and "Bespaard €" in meldingen(vl, "Vaatwasser is klaar")[0], f"{meldingen(vl, 'is klaar')}")
    controle("herstart: de beurt staat één keer in de opslag, afgerond, met bijna alle kWh en een besparing",
             len([b for b in vl.beurten if b["device"] == "vaatwasser"]) == 1
             and all(b["complete"] and 0.9 <= b["kwh"] <= 1.1 and (b["saved"] or 0) > 0 for b in vl.beurten if b["device"] == "vaatwasser"),
             f"{[(b['device'], b['complete'], b['kwh'], b['saved']) for b in vl.beurten]}")

# --- de bewoner --------------------------------------------------------------

print("=== de bewoner ===")
if (vl := v("pauze-van-bewoner")):
    controle("pauze: niets tussen twaalf en drie", not laadt_tussen(vl, "12:01", "15:00"), "")
    controle("pauze: daarna weer verder", laadt_tussen(vl, "15:02", "17:00"), "")
    controle("pauze: op tijd vol", gehaald(vl), "")

if (vl := v("pauze-vergeten")):
    controle("pauze vergeten: blijft staan", not laadt_tussen(vl, "12:01", "23:59"), "")
    controle("pauze vergeten: waarschuwt dat de klaar-tijd in gevaar komt",
             len(meldingen(vl, "pauze")) >= 1, f"{meldingen(vl, 'pauze')}")
    controle("pauze vergeten: en meldt om zes uur dat hij niet vol is",
             len(meldingen(vl, "06:00 nog niet vol")) == 1, f"{meldingen(vl, 'nog niet vol')}")

if (vl := v("snelladen")):
    controle("snelladen: vanaf negen uur vol vermogen",
             all(r.amps == 16 for r in regels_in(vl, "09:02", "12:00") if r.status != "completed"), "")
    controle("snelladen: ongeacht de zon", vl.uit_net_kwh > 0.5, f"{vl.uit_net_kwh:.2f}")

if (vl := v("kabel-eruit-middenin")):
    controle("kabel eruit: verslag met wat er in ging",
             bool(meldingen(vl, "afgekoppeld om 13:10")), f"{[m for _, m in vl.meldingen]}")
    controle("kabel eruit: de tweede beurt telt alleen zichzelf",
             any("8," in m for m in meldingen(vl, "is vol")), f"{meldingen(vl, 'is vol')}")
    controle("kabel eruit: op tijd vol", gehaald(vl), "")

if (vl := v("oude-begintijd-genegeerd")) and (vz := v("vast-zonnig")):
    controle("oude tijden: een laadpaal kent alleen 'klaar om', dus zelfde dag als zonder",
             abs(vl.geladen_kwh - vz.geladen_kwh) < 0.2 and vl.klaar_op == vz.klaar_op,
             f"vol om {vl.klaar_op}, zonder oude tijden {vz.klaar_op}")
    controle("oude tijden: geen too-early of start-by",
             not vl.regels_met("too-early") and not vl.regels_met("start-by"), "")

# --- het voorbeeld van 04-09-2026 ----------------------------------------------

print("=== om tien uur erin, klaar om zes ===")
if (vl := v("tien-uur-erin-dynamisch")):
    # 10:00 en 11:00 liggen boven het gemiddelde van de dag, 12:00 eronder.
    controle("tien uur: niet meteen laden bij het inpluggen",
             not laadt_tussen(vl, "10:00", "12:00"), "laadde tussen 10:00 en 12:00")
    controle("tien uur: voor de prijzen alleen uren onder het gemiddelde",
             net_onder_gemiddelde(vl, [r for r in vl.regels if r.tijd.hour < 13]), "")
    controle("tien uur: de goedkope middag pakken", laadt_tussen(vl, "13:05", "17:00"), "")
    controle("tien uur: stoppen voor de avondpiek", not laadt_tussen(vl, "18:05", "20:00"), "")
    controle("tien uur: en 's nachts de rest", laadt_tussen(vl, "00:00", "05:00"), "")
    controle("tien uur: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    # Zestig cent: het uur van 12:00 ligt onder het gemiddelde van de dag maar
    # boven de nacht die hij nog niet kende. Dat is de prijs van de regel; bij
    # de klantwoning bespaarde dezelfde regel op 05-09-2026 twee euro.
    # Zeventig sinds de avondpiek om 18:00 begint (05-09-2026): het uur van
    # 17:00 mag nu mee en ligt onder het daggemiddelde, maar boven de nacht.
    controle("tien uur: binnen zeventig cent van het optimum",
             vl.optimum is not None and vl.kosten <= vl.optimum + 0.70,
             f"kosten {vl.kosten:.2f}, optimum {vl.optimum}")

if (vl := v("tien-uur-erin-zon")):
    controle("tien uur met zon: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    controle("tien uur met zon: de zon van de middag gebruikt", vl.uit_zon_kwh > 25, f"{vl.uit_zon_kwh:.1f}")
    # Vijftien cent op 68 kWh: de ochtendzon gaat er op de ondergrens in, met
    # een beetje dure ochtendstroom erbij; het optimum weet dat de middag alles
    # gedekt had.
    controle("tien uur met zon: binnen veertig cent van het optimum",
             vl.optimum is not None and vl.kosten <= vl.optimum + 0.40,
             f"kosten {vl.kosten:.2f}, optimum {vl.optimum}")

if (vl := v("tien-uur-zon-valt-tegen")) and (vz := v("tien-uur-erin-zon")):
    controle("zon valt tegen: toch op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    controle("zon valt tegen: meer van het net dan bij een dak dat het wel doet",
             vl.uit_net_kwh > vz.uit_net_kwh + 5, f"{vl.uit_net_kwh:.1f} tegen {vz.uit_net_kwh:.1f}")

if (vl := v("tien-uur-erin-vast")):
    controle("tien uur vast: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    controle("tien uur vast: de zon gebruikt", vl.uit_zon_kwh > 25, f"{vl.uit_zon_kwh:.1f}")
    controle("tien uur vast: vóór acht uur hooguit de ondergrens bijgekocht",
             all(r.paal_amps <= 6.01 for r in regels_in(vl, "00:00", "20:00") if r.paal_w > r.over_w + 50),
             f"{vl.net_kwh_tussen('10:00', '20:00'):.2f} kWh van het net voor acht uur")

if (vl := v("equalizer-knijpt")):
    geknepen = regels_in(vl, "13:35", "15:00")
    # De bewaker meldt wat hij vrijgeeft, en de coach vraagt niet meer dan dat:
    # dan valt er niets als "geknepen" te melden, want de coach knijpt zelf mee.
    controle("equalizer: de coach vraagt niet meer dan de bewaker vrijgeeft",
             all(r.amps <= 10 for r in geknepen), f"hoogste vraag {max(r.amps for r in geknepen)} A")
    controle("equalizer: de paal blijft onder wat de bewaker vrijgeeft",
             all(r.paal_amps <= 10 for r in geknepen), f"hoogste {max(r.paal_amps for r in geknepen):.0f} A")
    controle("equalizer: en daarna weer vol",
             any(r.paal_amps >= 15 for r in regels_in(vl, "15:05", "16:00")), "")
    controle("equalizer: de coach vecht er niet tegen",
             len([o for o in vl.opdrachten if virtueel.dt.time(13, 35) <= o[0].time() < virtueel.dt.time(15, 0)]) <= 6,
             f"{len(vl.opdrachten)} opdrachten")
    controle("equalizer: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

ZATERDAG = virtueel.dt.date(2026, 9, 12)
ZONDAG_13 = virtueel.dt.datetime(2026, 9, 13, 13, 0)
if (vl := v("weekend-zondag-uit")):
    zaterdag = [r for r in vl.regels if r.tijd.date() == ZATERDAG]
    voor_de_prijzen = [r for r in vl.regels if r.tijd < ZONDAG_13]
    # Zon, en net alleen als aanvulling tot de ondergrens van de paal in een
    # uur waarin het dak iets geeft. De eigenaar op 05-09-2026: een uur met wat zon en
    # een goedkope prijs weegt zwaarder dan een iets goedkopere nacht.
    controle("weekend: zaterdag zon, net als aanvulling tot 6 A of in een uur onder het gemiddelde",
             all((r.paal_amps <= 6.01 and r.over_w > 50) or onder_gemiddelde(vl, r)
                 for r in zaterdag if r.paal_w > r.over_w + 50),
             "net zonder zon of boven de ondergrens in een uur boven het gemiddelde")
    controle("weekend: 's nachts niets", not any(r.paal_w > 0 for r in zaterdag if r.tijd.hour >= 20), "")
    controle("weekend: tot zondag 13:00 van het net alleen als aanvulling of onder het gemiddelde",
             all((r.paal_amps <= 6.01 and r.over_w > 50) or onder_gemiddelde(vl, r)
                 for r in voor_de_prijzen if r.paal_w > r.over_w + 50),
             "net zonder zon voor zondag 13:00 in een uur boven het gemiddelde")
    controle("weekend: de zon van zaterdag is wel gebruikt",
             sum(min(r.paal_w, r.over_w) for r in zaterdag) * vl.stap_uur / 1000 > 20,
             f"{sum(min(r.paal_w, r.over_w) for r in zaterdag) * vl.stap_uur / 1000:.1f} kWh zon op zaterdag")
    controle("weekend: zegt 's avonds dat hij op de prijzen wacht",
             any(r.regel == "wait-for-prices" for r in zaterdag), f"{sorted({r.regel for r in zaterdag})}")
    # Acht wissels: hij stopt op zondagochtend twee keer voor een zonuur dat
    # vier cent goedkoper is (09:36 en 10:47, een half uur elk). Dat is de
    # kostenregel; een stop voor minder dan een halve cent doet hij niet meer.
    controle("weekend: niet steeds aan en uit", vl.wissels() <= 8, f"{vl.wissels()} wissels")
    controle("weekend: maandag een uur voor zes vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

if (vl := v("weekend-zondag-uit-geen-zon")):
    controle("weekend zonder zon: voor zondag 13:00 alleen uren onder het gemiddelde",
             net_onder_gemiddelde(vl, [r for r in vl.regels if r.tijd < ZONDAG_13]), "")
    controle("weekend zonder zon: daarna de goedkope uren", vl.geladen_kwh > 60, f"{vl.geladen_kwh:.1f}")
    controle("weekend zonder zon: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    # Een euro: het optimum kent zaterdagmiddag al, de coach mag die van de eigenaar
    # niet gebruiken zolang de prijzen van maandag er niet zijn.
    controle("weekend zonder zon: het optimum plus wat de prijsregel kost",
             vl.optimum is not None and vl.kosten <= vl.optimum + 1.10,
             f"kosten {vl.kosten:.2f}, optimum {vl.optimum}")

if (vl := v("prijzen-weg-bij-inpluggen")):
    controle("prijzen weg: niet blind gaan laden", not laadt_tussen(vl, "10:00", "10:20"), "")
    controle("prijzen weg: zegt dat hij wacht op prijzen",
             any(r.regel == "no-prices" for r in regels_in(vl, "10:00", "10:20")),
             f"{sorted({r.regel for r in regels_in(vl, '10:00', '10:20')})}")
    controle("prijzen weg: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

# --- de klantwoning, het weekend van 04-09-2026 -----------------------------------
#
# De eerste echte laadbeurt met v0.47.x, nagebouwd met zijn eigen cijfers (zie
# scenarios.py). Dit zijn de vijf dingen die in de notities staan om in het
# echt vast te stellen, plus wat de varianten laten zien.

KLANT_ZATERDAG = virtueel.dt.date(2026, 9, 5)
KLANT_ZATERDAG_13 = virtueel.dt.datetime(2026, 9, 5, 13, 0)
KLANT_ZONDAG_05 = virtueel.dt.datetime(2026, 9, 6, 5, 0)


def klant_basis(vl, naam):
    """Wat in elke de klantwoning-variant hoort te gelden."""
    # Eén beurt, ingeplugd vrijdag 19:00 tegen de avondprijs, en die bespaart:
    # de middag en de zon zijn goedkoper dan het ijkpunt.
    controle(f"{naam}: één laadbeurt in de opslag, afgesloten of nog lopend",
             len(vl.beurten) == 1, f"{len(vl.beurten)}")
    if vl.beurten:
        b = vl.beurten[0]
        controle(f"{naam}: ingeplugd vrijdagavond tegen de prijs van dat uur",
                 b["plugged_at"].startswith("2026-09-04T19:0") and b["ref_price"] is not None
                 and b["ref_price"] > 0.3, f"{b['plugged_at']} op {b['ref_price']}")
        controle(f"{naam}: en bespaart tegen dat ijkpunt",
                 b["saved"] is not None and b["saved"] > 5, f"bespaard {b['saved']}, betaald {b['paid']}")
    vrijdagnacht = [r for r in vl.regels if r.tijd < virtueel.dt.datetime(2026, 9, 5, 7, 0)]
    controle(f"{naam}: vrijdagnacht 0 A", not any(r.paal_w > 0 for r in vrijdagnacht),
             f"{[r.tijd.strftime('%H:%M') for r in vrijdagnacht if r.paal_w > 0][:3]}")
    controle(f"{naam}: en zegt waarom, met zaterdag en zondag erin",
             any(r.regel == "wait-for-prices" and "Zaterdag staat in je schema uit" in r.reden
                 and "zondag om 06:00" in r.reden for r in vrijdagnacht),
             f"{next((r.reden for r in vrijdagnacht if r.regel == 'wait-for-prices'), '')}")
    # De avondpiek begint sinds 05-09-2026 om 18:00 (de keuze, 17:00 kostte
    # die dag 1,65 euro). Een paar minuten nalopen hoort erbij: de auto volgt de limiet
    # met een minuut vertraging. Sinds 05-09-2026 houdt de coach een lopende
    # beurt in de avondpiek niet meer vast (`_keep_alive`), want met tien
    # ronden `STOP_ROUNDS` was dat een kilowattuur uit de piek.
    controle(f"{naam}: niets van het net in de avondpiek",
             vl.net_kwh_tussen("18:03", "20:00") < 0.1,
             f"{vl.net_kwh_tussen('18:03', '20:00'):.2f} kWh tussen 18:03 en 20:00")
    controle(f"{naam}: onder de zekering", vl.hoogste_fase <= 25.0, f"{vl.hoogste_fase:.1f} A")
    controle(f"{naam}: een uur voor zondag 06:00 vol",
             gehaald(vl) and vl.klaar_op is not None and vl.klaar_op <= KLANT_ZONDAG_05,
             f"vol om {vl.klaar_op}, {vl.soc_bij_klaar_tijd}")
    controle(f"{naam}: geen valse 'nog niet vol'", not meldingen(vl, "nog niet vol"),
             f"{meldingen(vl, 'nog niet vol')}")
    controle(f"{naam}: precies een verslag", len(meldingen(vl, "is vol")) == 1,
             f"{meldingen(vl, 'is vol')}")


if (vl := v("klantwoning")):
    klant_basis(vl, "klantwoning")
    zaterdag = [r for r in vl.regels if r.tijd.date() == KLANT_ZATERDAG]
    ochtend = [r for r in zaterdag if r.tijd < KLANT_ZATERDAG_13]
    controle("klantwoning: zaterdagochtend begint pas als het dak iets overhoudt",
             all(r.over_w > 0 for r in ochtend if r.paal_w > 0), "laadde zonder overschot")
    controle("klantwoning: en dan op de ondergrens van 6 A, of vol in een uur onder het gemiddelde",
             ochtend and all(r.paal_amps <= 10.01 or onder_gemiddelde(vl, r) for r in ochtend),
             f"hoogste {max((r.paal_amps for r in ochtend), default=0):.0f} A")
    controle("klantwoning: om 13:00 komen de prijzen en gaat hij vol",
             any(r.regel == "cheap-hour" and r.paal_amps >= 15
                 for r in zaterdag if 13 <= r.tijd.hour < 17),
             f"{sorted({r.regel for r in zaterdag if 13 <= r.tijd.hour < 17})}")
    # De eigenaar op 04-09-2026: "check inderdaad of na 13 uur de coach de prijzen
    # binnenhaalt." De prijssensor krijgt om 13:00 de dag van morgen, en de
    # eerstvolgende ronde hoort er al naar te handelen.
    eerste_net = next((r for r in zaterdag if r.regel == "cheap-hour"), None)
    controle("klantwoning: en handelt binnen een minuut na 13:00 naar de nieuwe prijzen",
             eerste_net is not None and eerste_net.tijd <= KLANT_ZATERDAG_13 + virtueel.dt.timedelta(minutes=1),
             f"{eerste_net.tijd if eerste_net else None}")
    controle("klantwoning: de coach vraagt nooit meer dan de Equalizer vrijgeeft",
             all(r.amps <= 16 for r in vl.regels), f"{max(r.amps for r in vl.regels)} A")
    controle("klantwoning: nooit in no-room gevallen", not any(r.regel.startswith("no-room") for r in vl.regels), "")
    controle("klantwoning: een handvol opdrachten, geen gehamer op de Easee",
             len(vl.opdrachten) <= 25, f"{len(vl.opdrachten)} opdrachten")
    controle("klantwoning: niet ver van het optimum",
             vl.optimum is not None and vl.kosten <= vl.optimum + 0.60,
             f"kosten {vl.kosten:.2f}, optimum {vl.optimum}")

for naam in ("klantwoning-bewolkt", "klantwoning-geen-zon"):
    if (vl := v(naam)):
        klant_basis(vl, naam[12:])
        controle(f"{naam[12:]}: zonder overschot voor 13:00 alleen uren onder het gemiddelde",
                 net_onder_gemiddelde(vl, [r for r in vl.regels if r.tijd < KLANT_ZATERDAG_13]), "")
        controle(f"{naam[12:]}: daarna de goedkope middag en nacht", vl.geladen_kwh > 60,
                 f"{vl.geladen_kwh:.1f} kWh")

if (vl := v("klantwoning-dure-zondagnacht")):
    klant_basis(vl, "dure zondag")
    zaterdag = [r for r in vl.regels if r.tijd.date() == KLANT_ZATERDAG]
    controle("dure zondag: zaterdag doet het werk",
             sum(r.paal_w for r in zaterdag if 8 <= r.tijd.hour < 17) * vl.stap_uur / 1000 > 40,
             f"{sum(r.paal_w for r in zaterdag if 8 <= r.tijd.hour < 17) * vl.stap_uur / 1000:.1f} kWh")
    controle("dure zondag: en de dure nacht wordt niet gebruikt",
             sum(r.paal_w for r in vl.regels if r.tijd.date() > KLANT_ZATERDAG and r.tijd.hour >= 1) * vl.stap_uur / 1000 < 1,
             "laadde in de dure zondagnacht")

if (vl := v("klantwoning-ford-wekken")):
    klant_basis(vl, "wekken")
    # Zestien sinds 17-09-2026, en niet tien: een Easee in automatische
    # fasemodus kiest bij elke start naar wat er aangeboden wordt. Zie
    # `WAKE_AMPS` in planner.py en het scenario `easee-fasekeuze`.
    controle("wekken: op 16 A gewekt en daarna terug naar 6 A",
             any(r.regel.endswith("+wake") and r.amps == 16 for r in vl.regels)
             and any(r.regel == "surplus" and r.amps == 6 for r in vl.regels), "")

if (vl := v("klantwoning-oven")):
    klant_basis(vl, "oven")
    # De oven gaat om 12:30 aan; de coach houdt de beurt eerst `STOP_ROUNDS`
    # ronden op de ondergrens vast (tien sinds 05-09-2026, de eigen "wekken doe
    # maar per 10 min") en de auto volgt met een minuut. Daarna niets meer.
    # Het uur van 12:00 ligt onder het gemiddelde van de dag, dus sinds
    # 05-09-2026 mag hij daar gewoon van het net; de oven maakt dat niet anders.
    controle("oven: tijdens de oven van het net alleen in een uur onder het gemiddelde",
             net_onder_gemiddelde(vl, [r for r in regels_in(vl, "12:42", "13:00")
                                       if r.tijd.date() == KLANT_ZATERDAG]),
             f"{vl.net_kwh_tussen('12:42', '13:00'):.2f} kWh")
    controle("oven: de Equalizer wordt gemeld, niet bevochten",
             meldingen(vl, "lastbewaker") and len(vl.opdrachten) <= 60, f"{len(vl.opdrachten)} opdrachten")

if (vl := v("klantwoning-p1-weg")):
    klant_basis(vl, "p1 weg")
    controle("p1 weg: melding over de netmeting", bool(meldingen(vl, "netmeting")), "")
    controle("p1 weg: en daarna gewoon verder",
             any(r.paal_w > 0 and r.regel.split("+")[0] in ("surplus", "cheap-hour")
                 for r in regels_in(vl, "11:15", "12:00")), "")

if (vl := v("klantwoning-prijzen-laat")):
    klant_basis(vl, "prijzen laat")
    controle("prijzen laat: tot 15:30 alleen zon en uren onder het gemiddelde",
             all(r.paal_amps <= 6.01 or onder_gemiddelde(vl, r) for r in vl.regels
                 if r.tijd.date() == KLANT_ZATERDAG and r.tijd < virtueel.dt.datetime(2026, 9, 5, 15, 30)), "")
    controle("prijzen laat: daarna vol tot de avondpiek",
             any(r.paal_amps >= 15 for r in regels_in(vl, "15:30", "17:00")), "")
    # Het laatste uur, zondag 04:00 tot 05:00, moet op een rustig tempo en niet
    # met een opdracht per minuut. Gezien op 04-09-2026: 33 opdrachten in dat
    # uur, 14 en 15 A om en om, omdat de auto een minuut achterloopt op de
    # limiet en het tempo elke ronde opnieuw uit de meting werd uitgerekend.
    laatste_uur = [o for o in vl.opdrachten if o[0] >= virtueel.dt.datetime(2026, 9, 6, 4, 0)]
    controle("prijzen laat: geen opdracht per minuut in het laatste uur",
             len(laatste_uur) <= 8, f"{len(laatste_uur)} opdrachten na 04:00")

if (vl := v("klantwoning-geen-accustand")):
    controle("geen accustand: vraagt erom", bool(meldingen(vl, "weet niet hoe vol")), "")
    controle("geen accustand: en laadt op tijd toch vol via het vangnet", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

# Onverwachte herstarten van Home Assistant. De coach begint elke keer met een
# leeg geheugen en dezelfde opslag, en de laadbeurt hoort daar niets van te
# merken: geen dubbele meldingen, geen andere beslissing, op tijd vol.
if (vl := v("klantwoning-herstart")) and (basis := v("klantwoning")):
    klant_basis(vl, "herstart")
    controle("herstart: dezelfde laadbeurt als zonder herstarts",
             abs(vl.kosten - basis.kosten) < 0.10 and abs(vl.geladen_kwh - basis.geladen_kwh) < 0.5,
             f"kosten {vl.kosten:.2f} tegen {basis.kosten:.2f}, {vl.geladen_kwh:.1f} tegen {basis.geladen_kwh:.1f} kWh")
    na_10_30 = regels_in(vl, "10:30", "10:34")
    controle("herstart tijdens het laden: binnen drie minuten weer aan het laden",
             any(r.paal_w > 0 and r.amps >= 6 for r in na_10_30 if r.tijd.date() == KLANT_ZATERDAG),
             f"{[(r.tijd.strftime('%H:%M'), r.regel, r.amps) for r in na_10_30]}")
    na_13_05 = regels_in(vl, "13:05", "13:08")
    controle("herstart net na de prijzen: meteen weer op de goedkope middag",
             any(r.regel == "cheap-hour" and r.amps >= 15 for r in na_13_05 if r.tijd.date() == KLANT_ZATERDAG),
             f"{[(r.tijd.strftime('%H:%M'), r.regel, r.amps) for r in na_13_05]}")
    controle("herstart: geen enkele valse melding",
             not meldingen(vl, "niet lezen") and not meldingen(vl, "meldt al") and not meldingen(vl, "niets meer beslist"),
             f"{[m for _, m in vl.meldingen]}")
    # Bekend en niet verholpen: na de herstart om 04:20 kent de coach het begin
    # van de beurt niet meer en telt het verslag vanaf dat moment. Eerlijk, maar
    # onvolledig. Zie de notities van 04-09-2026. De bijzin "en toen liep hij
    # al" is er op 21-09-2026 uit gegaan; "sinds" doet hetzelfde werk.
    controle("herstart: het verslag telt eerlijk vanaf het moment van instappen",
             any("Sinds " in m for m in meldingen(vl, "is vol"))
             and all("liep hij al" not in m and "Geladen van" not in m
                     for m in meldingen(vl, "is vol")),
             f"{meldingen(vl, 'is vol')}")

# Een sensor die wegvalt wordt na tien minuten gemeld, en als hij terug is ook.
# De eigenaar op 04-09-2026: "wat als een sensor ineens niet meer beschikbaar is. Dat
# moet wel gemeld worden." Ondertussen laadt de coach gewoon door op wat hij
# het laatst wist. De accustand van een auto krijgt een uur (22-09-2026: "bij
# ford zet dat maar op een uur polling").
for naam, sensor, wat, van, tot in (
    ("klantwoning-accustand-weg", "accustand van Ford", "cheap-hour", "13:30", "14:45"),
    ("klantwoning-status-weg", "status van Laadpaal", "cheap-hour", "11:00", "11:20"),
    ("klantwoning-zonsensor-weg", "zonnesensor", "cheap-hour", "10:03", "10:20"),
    ("klantwoning-equalizer-weg", "lastbewaker", "cheap-hour", "14:00", "14:30"),
):
    if not (vl := v(naam)):
        continue
    kort = naam[12:]
    klant_basis(vl, kort)
    stil = meldingen(vl, "meldt al 10 minuten niets") + meldingen(vl, "meldt al 60 minuten niets")
    controle(f"{kort}: na tien minuten (een uur voor een auto) één melding dat de sensor niets zegt",
             len(stil) == 1 and sensor in stil[0], f"{stil}")
    # Sinds 06-09-2026 gaat "doet het weer" alleen nog in de geschiedenis en
    # niet naar de telefoon: per beurt één verslag plus wat kritiek is.
    weer = meldingen(vl, "doet het weer")
    controle(f"{kort}: en niets op de telefoon als hij terug is", not weer, f"{weer}")
    tijdens = [r for r in regels_in(vl, van, tot) if r.tijd.date() == KLANT_ZATERDAG]
    controle(f"{kort}: ondertussen laadt hij gewoon door",
             tijdens and all(r.paal_w > 0 for r in tijdens[3:])
             and any(r.regel.split("+")[0] == wat for r in tijdens),
             f"{sorted({r.regel for r in tijdens})}, laagste {min((r.paal_w for r in tijdens), default=0):.0f} W")
    controle(f"{kort}: en is even goedkoop uit als zonder storing",
             (basis := v("klantwoning")) is not None and abs(vl.kosten - basis.kosten) < 0.10,
             f"{vl.kosten:.2f}")

if (vl := v("klantwoning-prijssensor-weg-om-13")):
    klant_basis(vl, "prijssensor weg om 13")
    controle("prijssensor weg: gemeld na tien minuten, om 13:00",
             any(t.time() == virtueel.dt.time(13, 0) and "prijssensor" in m for t, m in vl.meldingen),
             f"{[(t.strftime('%H:%M'), m[:40]) for t, m in vl.meldingen]}")
    controle("prijssensor weg: zonder prijzen niets van het net",
             not laadt_tussen(vl, "12:54", "13:39"), "laadde zonder prijzen")
    na = [r for r in regels_in(vl, "13:40", "13:43") if r.tijd.date() == KLANT_ZATERDAG]
    controle("prijssensor weg: zodra hij terug is, meteen de prijzen van zondag en vol",
             any(r.regel == "cheap-hour" and r.amps >= 15 for r in na),
             f"{[(r.tijd.strftime('%H:%M'), r.regel, r.amps) for r in na]}")
    controle("prijssensor weg: en niets op de telefoon als hij het weer doet",
             not any("prijssensor doet het weer" in m for _, m in vl.meldingen), "")

# --- storingen ---------------------------------------------------------------

print("=== storingen ===")
if (vl := v("p1-valt-weg")):
    controle("P1 drie minuten weg: laadt gewoon door", vl.wissels() <= 2, f"{vl.wissels()} wissels")
    controle("P1 drie minuten weg: geen melding", not meldingen(vl, "netmeting"), "")

if (vl := v("p1-lang-weg")):
    controle("P1 lang weg: zegt het, met de juiste duur",
             any("6 minuten" in m for m in meldingen(vl, "netmeting")), f"{meldingen(vl, 'netmeting')}")
    controle("P1 lang weg: gaat verder zodra de meter terug is", laadt_tussen(vl, "12:25", "13:30"), "")
    controle("P1 lang weg: op tijd vol", gehaald(vl), "")

if (vl := v("teller-per-uur")):
    controle("teller per uur: op tijd vol", gehaald(vl), "")
    controle("teller per uur: het verslag noemt de echte hoeveelheid",
             any("15," in m for m in meldingen(vl, "Geladen van")), f"{[m for _, m in vl.meldingen]}")


# --- de boiler ---------------------------------------------------------------
#
# De eigenaar op 19-09-2026: een boiler op een smart plug, zelflerend, klaar om 07:00.
# Wat de bewoner ervan merkt is dit: er is warm water als hij onder de douche
# stapt, en het is op de goedkoopste uren verwarmd.

print("=== de boiler ===")

if (vl := v("boiler-leert")):
    geleerd = vl.boiler_geleerd
    print(f"  boiler-leert: {vl.boiler_kwh:.2f} kWh, geleerd {geleerd}")
    controle("boiler leert: na één nacht weet hij wat het element trekt",
             geleerd.get("heat_w") is not None and abs(float(geleerd["heat_w"]) - 2000) < 100,
             f"{geleerd}")
    controle("boiler leert: en hoeveel er in een volle beurt ging",
             (geleerd.get("vol_kwh") or 0) > 0.5, f"{geleerd}")
    controle("boiler leert: geen valse melding over de stekker",
             not any("geen stroom" in m for _, m in vl.meldingen),
             f"{[m for _, m in vl.meldingen]}")
    controle("boiler leert: en er is warm water om 07:00",
             (vl.boiler_bij_klaar or 0) > 2.0, f"{vl.boiler_bij_klaar}")

if (vl := v("boiler-nacht")):
    aan = [t for t, a in vl.boiler_schakels if a]
    lang = [(t, e) for t, e in zip(aan, [e for e, a in vl.boiler_schakels if not a])
            if (e - t).total_seconds() > 900]
    print(f"  boiler-nacht: {vl.boiler_kwh:.2f} kWh €{vl.boiler_betaald:.2f}, "
          f"aan om {[t.strftime('%H:%M') for t in aan]}, vat {vl.boiler_bij_klaar:.1f} kWh om 07:00")
    controle("boiler nacht: er is warm water om 07:00", (vl.boiler_bij_klaar or 0) > 4.0,
             f"{vl.boiler_bij_klaar}")
    controle("boiler nacht: het vat raakt onderweg niet leeg", (vl.boiler_laagste or 0) > 0.5,
             f"{vl.boiler_laagste}")
    controle("boiler nacht: hij verwarmt in de goedkope nacht en niet in de avondpiek",
             lang and all(t.hour < 6 or t.hour >= 23 for t, _ in lang),
             f"{[(t.strftime('%H:%M'), e.strftime('%H:%M')) for t, e in lang]}")
    controle("boiler nacht: niet in de avondpiek van het net",
             not any(18 <= t.hour < 20 for t, _ in lang),
             f"{[t.strftime('%H:%M') for t, _ in lang]}")
    controle("boiler nacht: hij schakelt een handvol keren, niet honderd",
             len(vl.boiler_schakels) <= 20, f"{len(vl.boiler_schakels)} schakelingen")
    beurt = next((b for b in vl.beurten if b.get("device") == "boiler"), None)
    controle("boiler nacht: de beurt staat onder Bespaard, met wat het wachten opleverde",
             beurt is not None and beurt.get("kind") == "boiler" and (beurt.get("saved") or 0) > 0,
             f"{beurt}")

if (vl := v("boiler-zon")):
    print(f"  boiler-zon: {vl.boiler_kwh:.2f} kWh waarvan {vl.boiler_zon_kwh:.2f} uit eigen zon")
    controle("boiler zon: het grootste deel komt uit eigen zon",
             vl.boiler_zon_kwh >= 0.4 * vl.boiler_kwh,
             f"{vl.boiler_zon_kwh:.2f} van {vl.boiler_kwh:.2f}")
    controle("boiler zon: hij verwarmt overdag en niet 's nachts",
             all(8 <= t.hour < 20 for t, a in vl.boiler_schakels if a),
             f"{[t.strftime('%H:%M') for t, a in vl.boiler_schakels if a]}")

if (vl := v("boiler-stekker-stuk")):
    print(f"  boiler-stekker-stuk: {len(vl.boiler_schakels)} schakelingen, "
          f"meldingen {[m[:40] for _, m in vl.meldingen]}")
    controle("stekker stuk: na een etmaal zonder één watt zegt hij het",
             any("geen stroom" in m for _, m in vl.meldingen),
             f"{[m for _, m in vl.meldingen]}")
    controle("stekker stuk: en hij zegt het één keer",
             sum("geen stroom" in m for _, m in vl.meldingen) == 1,
             f"{[m for _, m in vl.meldingen]}")
    controle("stekker stuk: hij blijft niet eindeloos schakelen",
             len(vl.boiler_schakels) <= 20, f"{len(vl.boiler_schakels)} schakelingen")

print("=== de thuisbatterij ===")
# De eigenaar op 21-09-2026: "Laden, ontladen, blokkeren als de laadpaal laadt.
# Laden op goedkope tarieven. Laden op overschot zonne-energie." En over de
# regelaar: "Hoe zorgen we dat we niet gaan pendelen?"


def bat_moment(vl, tijd, dag=0):
    """Een tijdstip in dit scenario; met seconden erbij mag ook ("19:00:45")."""
    delen = tijd.split(":")
    moment = virtueel._moment_op(vl.regels[0].tijd, ":".join(delen[:2]))
    seconden = int(delen[2]) if len(delen) > 2 else 0
    return moment + virtueel.dt.timedelta(days=dag, seconds=seconden)


def bat_stand_om(vl, tijd, dag=0):
    doel = bat_moment(vl, tijd, dag)
    return next((r[4] for r in vl.bat_verloop if r[0] >= doel), None)


def bat_tussen(vl, van, tot, dag=0):
    a, b = bat_moment(vl, van, dag), bat_moment(vl, tot, dag)
    return [r for r in vl.bat_verloop if a <= r[0] < b]


for naam, vl in V.items():
    if vl.scenario.batterij is None:
        continue
    bat = vl.scenario.batterij
    print(f"  {naam}: {len(vl.bat_opdrachten)} opdrachten, {vl.bat_wissels()} wissels, "
          f"net {vl.bat_afname_kwh:.1f} kWh erin en {vl.bat_levering_kwh:.1f} eruit, "
          f"kosten {vl.bat_kosten_met:.2f} tegen {vl.bat_kosten_zonder:.2f} zonder")
    uren = max(1.0, len(vl.bat_verloop) * vl.stap_uur)
    controle(f"{naam}: de coach zette de batterij in de modus voor externe sturing",
             bool(vl.bat_modi) and vl.bat_modi[0][1] == "third_party_control", f"{vl.bat_modi}")
    # Het antwoord op "hoe zorgen we dat we niet gaan pendelen": in de eerste
    # woning stuurde de oude regelaar 1.700 keer per dag bij en wisselde de
    # batterij 233 keer van toestand.
    # Een last die elke twintig seconden klappert vraagt per puls een opdracht
    # en een terug; dat scenario meet zijn eigen grens hieronder.
    if naam != "batterij-klapperlast":
        controle(f"{naam}: hooguit tien opdrachten per uur",
                 len(vl.bat_opdrachten) / uren <= 10, f"{len(vl.bat_opdrachten) / uren:.1f} per uur")
    # Zes mag altijd: ontladen, laden bij een negatieve prijs, vol, en weer
    # ontladen is er al drie, en dat is geen pendelen.
    controle(f"{naam}: hooguit een richtingwissel per twee uur",
             vl.bat_wissels() <= max(6, uren / 2), f"{vl.bat_wissels()} in {uren:.0f} uur")
    # De laadgrens mag hoger staan als de coach hem voor de volle beurt schreef.
    hoogste = max([bat.soc_max] + [g for _, g in vl.bat_grenzen])
    controle(f"{naam}: de accustand blijft tussen zijn eigen grenzen",
             all(bat.soc_min - 0.5 <= r[3] <= hoogste + 0.5 for r in vl.bat_verloop),
             f"{min(r[3] for r in vl.bat_verloop):.1f} tot {max(r[3] for r in vl.bat_verloop):.1f}%")
    # De wekelijkse volle beurt is de uitzondering: die is er voor de cellen en
    # niet voor de rekening, en kost dus geld.
    if bat.wekelijks_vol_dag is None:
        controle(f"{naam}: de batterij maakt de dag niet duurder",
                 vl.bat_kosten_met <= vl.bat_kosten_zonder + 0.02,
                 f"{vl.bat_kosten_met:.2f} tegen {vl.bat_kosten_zonder:.2f}")
    # Wat de coach in zijn kasboek schreef is wat het huis werkelijk scheelde.
    # De laatste minuten staan nog niet in de opslag: die gaat om de vijf minuten.
    geboekt = float(vl.bat_stand.get("earned_total") or 0.0)
    controle(f"{naam}: het kasboek klopt met wat de dag werkelijk scheelde",
             abs(geboekt - (vl.bat_kosten_zonder - vl.bat_kosten_met)) <= 0.10,
             f"geboekt {geboekt:.2f}, werkelijk {vl.bat_kosten_zonder - vl.bat_kosten_met:.2f}")

if (vl := v("batterij-vast-zon")):
    controle("vast met zon: de hele dag nul op de meter, of vol",
             all(r[4] in ("nul", "ontladen") for r in vl.bat_verloop[5:]),
             f"{sorted({r[4] for r in vl.bat_verloop})}")
    controle("vast met zon: overdag komt hij vol", max(r[3] for r in vl.bat_verloop) >= 93.0,
             f"{max(r[3] for r in vl.bat_verloop):.0f}%")
    controle("vast met zon: er komt bijna niets meer van het net",
             vl.bat_afname_kwh <= 0.5, f"{vl.bat_afname_kwh:.2f} kWh")
    avond = bat_tussen(vl, "21:00", "23:00")
    controle("vast met zon: 's avonds staat de meter rond nul",
             sum(abs(r[1]) <= 60 for r in avond) / len(avond) >= 0.95,
             f"{sum(abs(r[1]) <= 60 for r in avond) / len(avond):.2f}")

if (vl := v("batterij-vast-salderen")):
    controle("salderen: er gaat geen zon in de batterij",
             all(r[2] <= 1 for r in vl.bat_verloop), f"{max(r[2] for r in vl.bat_verloop):.0f} W")
    controle("salderen: eenmaal leeg staat hij stil", bat_stand_om(vl, "22:00") == "standby",
             bat_stand_om(vl, "22:00"))

if (vl := v("batterij-dynamisch-winter")):
    net = [r for r in vl.bat_verloop if r[4] == "netladen"]
    controle("winter: hij laadt bij van het net", len(net) * vl.stap_uur >= 1.0,
             f"{len(net) * vl.stap_uur:.1f} uur")
    prijzen = vl.scenario.prijzen
    # De dure avond is 0,41; met 73,6% rendement loont alles onder de 0,30.
    # Hij pakt daarvan de goedkoopste: de middag, niet de nacht van 0,23.
    controle("winter: en alleen in de goedkoopste uren van de dag",
             all(prijzen.all_in(r[0]) <= 0.21 for r in net),
             f"{sorted({round(prijzen.all_in(r[0]), 3) for r in net})}")
    controle("winter: niet in de avondpiek", not [r for r in net if 18 <= r[0].hour < 20], "")
    duur = bat_tussen(vl, "18:00", "20:00")
    controle("winter: op de dure avond voedt hij het huis",
             sum(r[2] < -100 for r in duur) / len(duur) >= 0.9, "")
    # In de nacht van maandag op dinsdag is 0,228 gedeeld door 73,6% duurder
    # dan wat hij dinsdagmiddag voor 0,156 kan kopen: dan laadt hij 's nachts
    # niet, ook al is de batterij leeg.
    nacht = bat_tussen(vl, "00:00", "05:00")
    controle("winter: een nacht die het rendement niet goedmaakt laat hij liggen",
             not [r for r in nacht if r[4] == "netladen"], "")

if (vl := v("batterij-dynamisch-zon")):
    controle("zomer: van het net laden hoeft niet",
             not [r for r in vl.bat_verloop if r[4] == "netladen"], "")
    controle("zomer: de zon vult hem", max(r[3] for r in vl.bat_verloop) >= 85.0,
             f"{max(r[3] for r in vl.bat_verloop):.0f}%")
    # De ochtendzon levert elf tot dertien cent op en de middagzon bijna niets:
    # hij wacht met opslaan tot de middag, want vol komt hij toch.
    ochtend = bat_tussen(vl, "08:00", "10:30")
    controle("zomer: dure ochtendzon gaat naar het net, goedkope middagzon de batterij in",
             sum(r[2] for r in ochtend) / len(ochtend) < 100,
             f"{sum(r[2] for r in ochtend) / len(ochtend):.0f} W gemiddeld")

if (vl := v("batterij-handelen")):
    piek = bat_tussen(vl, "19:00", "21:00")
    controle("handelen: op de avond van tachtig cent levert hij aan het net",
             sum(r[1] < -500 for r in piek) / len(piek) >= 0.8,
             f"{sum(r[1] for r in piek) / len(piek):.0f} W gemiddeld op de meter")
    # Twee metingen mag: een huis dat minder gaat vragen wordt een stap later
    # gevolgd, en dat is geen handelen.
    controle("handelen: en daarbuiten niet",
             len([r for r in bat_tussen(vl, "21:05", "23:55") if r[1] < -200]) <= 2, "")

if (vl := v("batterij-reserve")):
    controle("reserve: onder de veertig procent komt er niets uit",
             min(r[3] for r in vl.bat_verloop) >= 39.0, f"{min(r[3] for r in vl.bat_verloop):.1f}%")
    controle("reserve: en daarna staat hij op alleen zonneladen",
             bat_stand_om(vl, "03:00") == "zonneladen", bat_stand_om(vl, "03:00"))

if (vl := v("batterij-negatieve-prijs")):
    neg = bat_tussen(vl, "12:02", "14:30")
    controle("negatieve prijs: maximaal laden", all(r[4] == "max-laden" for r in neg),
             f"{sorted({r[4] for r in neg})}")
    controle("negatieve prijs: op vol vermogen",
             sum(r[2] >= 3400 for r in neg) / len(neg) >= 0.95, "")
    controle("negatieve prijs: ervoor laadt hij niet van het net",
             not [r for r in bat_tussen(vl, "11:00", "11:59") if r[4] in ("netladen", "max-laden")], "")

if (vl := v("batterij-volle-beurt")):
    # De keuze van de eigenaar op 22-09-2026: de coach zet de laadgrens die dag
    # zelf op 100 en daarna terug, want een volle beurt tot 95% balanceert niets.
    print(f"  volle beurt: laadgrens {[(t.strftime('%H:%M'), g) for t, g in vl.bat_grenzen]}, "
          f"hoogste stand {max(r[3] for r in vl.bat_verloop):.1f}%")
    controle("volle beurt: de laadgrens gaat aan het begin van de dag naar 100",
             bool(vl.bat_grenzen) and vl.bat_grenzen[0][1] == 100.0, f"{vl.bat_grenzen}")
    controle("volle beurt: voor middernacht een keer echt vol",
             max(r[3] for r in vl.bat_verloop) >= 98.0, f"{max(r[3] for r in vl.bat_verloop):.0f}%")
    controle("volle beurt: en dan gaat de laadgrens terug naar 95",
             len(vl.bat_grenzen) == 2 and vl.bat_grenzen[-1][1] == 95.0, f"{vl.bat_grenzen}")
    controle("volle beurt: dat staat in de opslag, zodat hij morgen niet opnieuw begint",
             bool(vl.bat_stand.get("full_at")) and vl.bat_stand.get("limit_restore") is None, f"{vl.bat_stand}")

if (vl := v("batterij-paal-laadt")):
    laadt = [r for r, regel in zip(vl.bat_verloop, vl.regels) if regel.paal_w > 1000]
    controle("paal laadt: er is werkelijk geladen", len(laadt) * vl.stap_uur > 3, "")
    # De eerste minuut na het begin mag hij nog ontladen: de coach ziet de paal
    # pas bij zijn volgende ronde.
    controle("paal laadt: de batterij geeft dan niets af",
             sum(r[2] < -50 for r in laadt) * vl.stap_uur * 60 <= 2.0,
             f"{sum(r[2] < -50 for r in laadt) * vl.stap_uur * 60:.1f} minuten")
    controle("paal laadt: daarvoor en daarna voedt hij het huis wel",
             bat_stand_om(vl, "19:00") == "nul" and bat_stand_om(vl, "05:30") == "nul",
             f"{bat_stand_om(vl, '19:00')} en {bat_stand_om(vl, '05:30')}")
    controle("paal laadt: de auto haalt zijn klaar-tijd", gehaald(vl), "")

if (vl := v("batterij-sprong")):
    na = bat_tussen(vl, "19:00", "19:01")
    controle("sprong: binnen tien seconden levert de batterij wat hij kan",
             any(r[2] <= -2490 for r in na[:3]), f"{[round(r[2]) for r in na[:4]]}")
    uit = bat_tussen(vl, "19:20", "19:22")
    controle("sprong: gaat het weer uit, dan schiet hij niet door naar terugleveren",
             sum(r[1] < -100 for r in uit) <= 3, f"{[round(r[1]) for r in uit[:6]]}")
    controle("sprong: een handvol opdrachten in het hele uur", len(vl.bat_opdrachten) <= 8,
             f"{len(vl.bat_opdrachten)}")

if (vl := v("batterij-meter-weg")):
    stil = bat_tussen(vl, "19:00:45", "19:03:55")
    controle("meter weg: binnen drie kwartier van een minuut staat de batterij op nul",
             bool(stil) and all(abs(r[2]) < 1 for r in stil), f"{[round(r[2]) for r in stil[:4]]}")
    terug = bat_tussen(vl, "19:04:30", "19:06:00")
    controle("meter weg: is hij terug, dan pakt hij het weer op",
             bool(terug) and all(r[2] < -100 for r in terug), f"{[round(r[2]) for r in terug[:4]]}")

if (vl := v("batterij-herstart")):
    na = bat_tussen(vl, "19:06", "19:15")
    controle("herstart: de nieuwe coach neemt de batterij over zonder hem los te laten",
             bool(na) and all(r[2] <= -2400 for r in na), f"{sorted({round(r[2]) for r in na})}")

# Gemeten op 22-09-2026 in de eerste woning: de vermogenssensor van de Anker
# loopt vijf tot tien seconden achter op de kWh-meter, toont onderweg een
# aanloop die er niet is en vlak na een opdracht de opdracht zelf. De sturing
# die daar draaide slingerde daarop, en de regelaar van v0.73.0 deed dat in dit
# scenario ook: 241 opdrachten en 118 wissels in een uur, tegen 3 en 0 met een
# eerlijke sensor. Sinds v0.74.0 rekent hij met zijn eigen opdracht.
if (vl := v("batterij-anker-sensor")):
    na = bat_tussen(vl, "19:00", "19:01")
    controle("anker-sensor: binnen tien seconden levert de batterij wat hij kan",
             any(r[2] <= -2490 for r in na[:3]), f"{[round(r[2]) for r in na[:4]]}")
    uit = bat_tussen(vl, "19:20", "19:22")
    controle("anker-sensor: gaat het weer uit, dan schiet hij niet door naar terugleveren",
             sum(r[1] < -100 for r in uit) <= 3, f"{[round(r[1]) for r in uit[:6]]}")
    controle("anker-sensor: een handvol opdrachten, net als met een eerlijke sensor",
             len(vl.bat_opdrachten) <= 8, f"{len(vl.bat_opdrachten)}")
    controle("anker-sensor: en geen enkele richtingwissel", vl.bat_wissels() == 0, f"{vl.bat_wissels()}")

# Elk uur veertig seconden 2,5 kW, dag en nacht (de eerste woning, 22-09-2026;
# een boiler of een warmtepomp, zei de eigenaar). Met de regelaar van v0.73.0
# en de sensor van de Anker: 180 opdrachten in drie uur, slingerend tussen 357
# en 3.500 W. Wat er van het net komt is de aanloop van elke puls: tien
# seconden voordat de batterij hem opvangt.
if (vl := v("batterij-uurlast")):
    pulsen = [t for t, *_ in vl.bat_verloop if (t.hour * 60 + t.minute) % 54 == 0 and t.second == 0]
    per_puls = [sum(1 for o, _ in vl.bat_opdrachten if t <= o < t + virtueel.dt.timedelta(seconds=90))
                for t in pulsen]
    print(f"  uurlast: {len(pulsen)} pulsen, opdrachten per puls {per_puls}, "
          f"net {vl.bat_afname_kwh:.3f} kWh erin over de dag")
    controle("uurlast: per puls hooguit drie opdrachten (omlaag, en weer omhoog)",
             pulsen and max(per_puls) <= 3, f"{per_puls}")
    controle("uurlast: over de hele dag komt er hooguit een kwart kWh van het net",
             vl.bat_afname_kwh <= 0.25, f"{vl.bat_afname_kwh:.3f}")
    controle("uurlast: overdag nul op de meter en niet meer dan een handvol richtingwissels",
             vl.bat_wissels() <= 8, f"{vl.bat_wissels()}")

# De nacht van 22-09-2026 in de eerste woning, met de coach aan het stuur: een
# last van vijf seconden elke twintig seconden, een batterij die pas na tien
# seconden volgt, en een P1 die om :03 en :08 meldt terwijl de sensor van de
# batterij om :09 al de nieuwe stand toont. Met de regelaar van v0.81.0: 286
# opdrachten en 143 richtingwissels in een uur, 0,86 kWh van het net op 30%
# midden in de nacht. Nu: één opdracht per puls en terug, geen enkele wissel.
if (vl := v("batterij-klapperlast")):
    print(f"  klapperlast: {len(vl.bat_opdrachten)} opdrachten, {vl.bat_wissels()} wissels, "
          f"net {vl.bat_afname_kwh:.3f} kWh erin, {vl.bat_levering_kwh:.3f} eruit")
    controle("klapperlast: 's nachts op 30% gaat er geen enkele opdracht de laadkant op",
             vl.bat_wissels() == 0 and all(w <= 0 for _, w in vl.bat_opdrachten), f"{vl.bat_wissels()}")
    controle("klapperlast: hooguit twee opdrachten per puls (omlaag en weer omhoog)",
             len(vl.bat_opdrachten) <= 2 * 181, f"{len(vl.bat_opdrachten)}")
    controle("klapperlast: er komt in dat uur niet meer dan een derde kWh van het net",
             vl.bat_afname_kwh <= 0.35, f"{vl.bat_afname_kwh:.3f}")

if (vl := v("batterij-rendement-onbekend")):
    controle("rendement onbekend: alleen nul op de meter",
             {r[4] for r in vl.bat_verloop[5:]} <= {"nul"}, f"{sorted({r[4] for r in vl.bat_verloop})}")
    controle("rendement onbekend: en er staat geen rendement in de opslag",
             not vl.bat_stand.get("rte"), f"{vl.bat_stand}")

# --- de laadmodus zonder planning (v0.87.0) ---------------------------------
# De eigenaar op 23-09-2026: "de modus is leidend (snel, continu of zon), tenzij er
# een planning ingesteld is. Geen planning, standaard terug naar zon."
if (vl := v("modus-zon")):
    controle("modus zon, helder: vol op zon en niets van het net", vl.klaar_op is not None and vl.uit_net_kwh < 0.1,
             f"vol {vl.klaar_op}, net {vl.uit_net_kwh:.2f}")
    controle("modus zon: nooit een besluit om van het net te laden",
             not any(r.regel.split("+")[0] in ("cheap-hour", "cheapest-hour", "fixed-tariff", "continu")
                     for r in vl.regels if r.amps > 0),
             f"{sorted({r.regel for r in vl.regels if r.amps > 0})}")
if (vl := v("modus-zon-bewolkt")):
    controle("modus zon, bewolkt: hooguit het korte doorladen bij een wolk van het net",
             vl.uit_net_kwh < 0.5, f"net {vl.uit_net_kwh:.2f}")
    controle("modus zon, bewolkt: hij zegt vanaf hoeveel zon hij begint",
             any("Hij begint vanaf" in (r.reden or "") for r in vl.regels), "")
    controle("modus zon: geen melding om de accustand, want er valt niets te plannen",
             not meldingen(vl, "hoe vol hij is"), f"{meldingen(vl, 'hoe vol')}")
if (vl := v("modus-continu")):
    eerste = next((r for r in vl.regels if r.amps > 0), None)
    controle("modus continu: meteen bij het inpluggen laden", eerste is not None and eerste.tijd.hour == 7,
             f"{eerste.tijd if eerste else None}")
    controle("modus continu: vol op de eerste dag, met de zon erbovenop",
             vl.klaar_op is not None and vl.klaar_op.day == 7 and vl.uit_zon_kwh > 10,
             f"vol {vl.klaar_op}, zon {vl.uit_zon_kwh:.1f}")

print(f"\n{GOED} goed, {FOUT} fout")
sys.exit(1 if FOUT else 0)
