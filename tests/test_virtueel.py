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
    over = [r for r in vl.regels if max(r.fase_amps) > s.zekering]
    controle(f"{naam}: de zekering wordt hooguit een minuut overschreden",
             len(over) * vl.stap_uur * 60 <= 1.0, f"{len(over) * vl.stap_uur * 60:.1f} minuten boven "
             f"{s.zekering} A, hoogste {vl.hoogste_fase:.1f} A")
    # Alleen als de auto zijn accustand zelf meldt. Met een opgegeven stand
    # rekent de coach met de teller van de paal, en die loopt bij een Easee
    # tot een uur achter; dan zegt het verslag "staat op 87%" over een auto
    # die vol is. Dat staat open, zie waar-gebleven.md van 04-09-2026.
    if vl.klaar_op is not None and s.auto.laadgrens >= 100 and s.auto.meldt_soc:
        controle(f"{naam}: precies één keer 'is vol' gemeld",
                 len(meldingen(vl, "is vol")) == 1, f"{meldingen(vl, 'is vol')}")
    # Sven op 04-09-2026: "De eindtijd is heel belangrijk. Een uur daarvoor
    # moet hij altijd klaar zijn." Vijf minuten speling voor de aanloop.
    if gehaald(vl) and vl.klaar_tijd is not None and vl.klaar_op is not None:
        controle(f"{naam}: een uur voor de klaar-tijd al vol",
                 vl.klaar_op <= vl.klaar_tijd - virtueel.dt.timedelta(minutes=55),
                 f"vol om {vl.klaar_op:%H:%M}, klaar-tijd {vl.klaar_tijd:%H:%M}")
    # En nooit van het net in de avondpiek, welk contract ook. Alleen snelladen
    # en een klaar-tijd die anders niet gehaald wordt gaan daar overheen. Een
    # halve kilowattuur speling: de coach houdt een lopende beurt drie ronden
    # op de ondergrens aan voordat hij stopt (`_keep_alive`), en dat is bij een
    # driefasige auto 0,4 kWh over de grens heen.
    if naam not in ("snelladen", "vast-onhaalbare-klaar-tijd", "eenfase-krappe-zekering"):
        controle(f"{naam}: niets van het net in de avondpiek",
                 vl.net_kwh_tussen("17:00", "20:00") < 0.6,
                 f"{vl.net_kwh_tussen('17:00', '20:00'):.2f} kWh tussen 17:00 en 20:00")

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
    controle("bewolkt: rustig aan is nooit vol vermogen",
             all(r.amps < 16 for r in vl.regels_met("easy-pace")), "16 A in easy-pace")

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

# De marge op het optimum is wat Svens regel "alleen zon tot de prijzen bekend
# zijn" kost: om 07:00 kent de coach alleen vandaag, dus het goedkope uur van
# 12:00 laat hij liggen en hij plant pas om 13:00. Het optimum kent alles. Bij
# de bus is dat drie dubbeltjes, bij de grote auto anderhalve euro. Sven kent
# die getallen (notities 04-09-2026) en koos de regel.
for naam, marge in (("dynamisch-bewolkt", 0.35), ("dynamisch-geen-panelen", 0.35),
                    ("dynamisch-avond-erin", 0.10), ("dynamisch-grote-auto", 1.50)):
    if (vl := v(naam)):
        controle(f"{naam}: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
        controle(f"{naam}: niets van het net in de dure avonduren",
                 vl.net_kwh_tussen("17:00", "21:00") < 0.6, f"{vl.net_kwh_tussen('17:00', '21:00'):.2f} kWh")
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

if (vl := v("bijna-vol")):
    controle("bijna vol: laadt het restje", 0.5 < vl.geladen_kwh < 2.0, f"{vl.geladen_kwh:.2f}")
    controle("bijna vol: één melding", len(meldingen(vl, "is vol")) == 1, "")

if (vl := v("auto-wordt-niet-wakker")):
    controle("slapende auto: meldt dat hij geen stroom afneemt",
             bool(meldingen(vl, "geen stroom af")), "")
    controle("slapende auto: komt alsnog vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

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

# --- Svens voorbeeld van 04-09-2026 ----------------------------------------------

print("=== om tien uur erin, klaar om zes ===")
if (vl := v("tien-uur-erin-dynamisch")):
    controle("tien uur: niet meteen laden bij het inpluggen",
             not laadt_tussen(vl, "10:00", "13:00"), "laadde tussen 10:00 en 13:00")
    controle("tien uur: de goedkope middag pakken", laadt_tussen(vl, "13:05", "17:00"), "")
    controle("tien uur: stoppen voor de avondpiek", not laadt_tussen(vl, "17:05", "20:00"), "")
    controle("tien uur: en 's nachts de rest", laadt_tussen(vl, "00:00", "05:00"), "")
    controle("tien uur: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    controle("tien uur: binnen een dubbeltje van het optimum",
             vl.optimum is not None and vl.kosten <= vl.optimum + 0.10,
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
    # uur waarin het dak iets geeft. Sven op 05-09-2026: een uur met wat zon en
    # een goedkope prijs weegt zwaarder dan een iets goedkopere nacht.
    controle("weekend: zaterdag alleen zon, net hooguit als aanvulling tot 6 A",
             all(r.paal_amps <= 6.01 and r.over_w > 50 for r in zaterdag if r.paal_w > r.over_w + 50),
             "net zonder zon of boven de ondergrens op zaterdag")
    controle("weekend: 's nachts niets", not any(r.paal_w > 0 for r in zaterdag if r.tijd.hour >= 20), "")
    controle("weekend: tot zondag 13:00 geen uur zonder zon van het net",
             all(r.paal_amps <= 6.01 and r.over_w > 50 for r in voor_de_prijzen if r.paal_w > r.over_w + 50),
             "net zonder zon voor zondag 13:00")
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
    controle("weekend zonder zon: niets tot zondag 13:00",
             not any(r.paal_w > 0 for r in vl.regels if r.tijd < ZONDAG_13), "laadde voor zondag 13:00")
    controle("weekend zonder zon: daarna de goedkope uren", vl.geladen_kwh > 60, f"{vl.geladen_kwh:.1f}")
    controle("weekend zonder zon: op tijd vol", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")
    # Een euro: het optimum kent zaterdagmiddag al, de coach mag die van Sven
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

# --- Van den Dam, het weekend van 04-09-2026 -----------------------------------
#
# De eerste echte laadbeurt met v0.47.x, nagebouwd met zijn eigen cijfers (zie
# scenarios.py). Dit zijn de vijf dingen die in de notities staan om in het
# echt vast te stellen, plus wat de varianten laten zien.

VDD_ZATERDAG = virtueel.dt.date(2026, 9, 5)
VDD_ZATERDAG_13 = virtueel.dt.datetime(2026, 9, 5, 13, 0)
VDD_ZONDAG_05 = virtueel.dt.datetime(2026, 9, 6, 5, 0)


def vdd_basis(vl, naam):
    """Wat in elke Van den Dam-variant hoort te gelden."""
    vrijdagnacht = [r for r in vl.regels if r.tijd < virtueel.dt.datetime(2026, 9, 5, 7, 0)]
    controle(f"{naam}: vrijdagnacht 0 A", not any(r.paal_w > 0 for r in vrijdagnacht),
             f"{[r.tijd.strftime('%H:%M') for r in vrijdagnacht if r.paal_w > 0][:3]}")
    controle(f"{naam}: en zegt waarom, met zaterdag en zondag erin",
             any(r.regel == "wait-for-prices" and "Zaterdag staat in je schema uit" in r.reden
                 and "zondag om 06:00" in r.reden for r in vrijdagnacht),
             f"{next((r.reden for r in vrijdagnacht if r.regel == 'wait-for-prices'), '')}")
    # Een paar minuten nalopen na 17:00 hoort erbij: de auto volgt de limiet
    # met een minuut vertraging. Sinds 05-09-2026 houdt de coach een lopende
    # beurt in de avondpiek niet meer vast (`_keep_alive`), want met tien
    # ronden `STOP_ROUNDS` was dat een kilowattuur uit de piek.
    controle(f"{naam}: niets van het net in de avondpiek",
             vl.net_kwh_tussen("17:03", "20:00") < 0.1,
             f"{vl.net_kwh_tussen('17:03', '20:00'):.2f} kWh tussen 17:03 en 20:00")
    controle(f"{naam}: onder de zekering", vl.hoogste_fase <= 25.0, f"{vl.hoogste_fase:.1f} A")
    controle(f"{naam}: een uur voor zondag 06:00 vol",
             gehaald(vl) and vl.klaar_op is not None and vl.klaar_op <= VDD_ZONDAG_05,
             f"vol om {vl.klaar_op}, {vl.soc_bij_klaar_tijd}")
    controle(f"{naam}: geen valse 'nog niet vol'", not meldingen(vl, "nog niet vol"),
             f"{meldingen(vl, 'nog niet vol')}")
    controle(f"{naam}: precies een verslag", len(meldingen(vl, "is vol")) == 1,
             f"{meldingen(vl, 'is vol')}")


if (vl := v("van-den-dam")):
    vdd_basis(vl, "vdd")
    zaterdag = [r for r in vl.regels if r.tijd.date() == VDD_ZATERDAG]
    ochtend = [r for r in zaterdag if r.tijd < VDD_ZATERDAG_13]
    controle("vdd: zaterdagochtend begint pas als het dak iets overhoudt",
             all(r.over_w > 0 for r in ochtend if r.paal_w > 0), "laadde zonder overschot")
    controle("vdd: en dan op de ondergrens van 6 A",
             ochtend and max(r.paal_amps for r in ochtend) <= 10.01 and
             sum(1 for r in ochtend if 5.9 <= r.paal_amps <= 6.1) > 200,
             f"hoogste {max((r.paal_amps for r in ochtend), default=0):.0f} A")
    controle("vdd: om 13:00 komen de prijzen en gaat hij vol",
             any(r.regel == "cheap-hour" and r.paal_amps >= 15
                 for r in zaterdag if 13 <= r.tijd.hour < 17),
             f"{sorted({r.regel for r in zaterdag if 13 <= r.tijd.hour < 17})}")
    # Sven op 04-09-2026: "check inderdaad of na 13 uur de coach de prijzen
    # binnenhaalt." De prijssensor krijgt om 13:00 de dag van morgen, en de
    # eerstvolgende ronde hoort er al naar te handelen.
    eerste_net = next((r for r in zaterdag if r.regel == "cheap-hour"), None)
    controle("vdd: en handelt binnen een minuut na 13:00 naar de nieuwe prijzen",
             eerste_net is not None and eerste_net.tijd <= VDD_ZATERDAG_13 + virtueel.dt.timedelta(minutes=1),
             f"{eerste_net.tijd if eerste_net else None}")
    controle("vdd: de coach vraagt nooit meer dan de Equalizer vrijgeeft",
             all(r.amps <= 16 for r in vl.regels), f"{max(r.amps for r in vl.regels)} A")
    controle("vdd: nooit in no-room gevallen", not any(r.regel.startswith("no-room") for r in vl.regels), "")
    controle("vdd: een handvol opdrachten, geen gehamer op de Easee",
             len(vl.opdrachten) <= 25, f"{len(vl.opdrachten)} opdrachten")
    controle("vdd: niet ver van het optimum",
             vl.optimum is not None and vl.kosten <= vl.optimum + 0.60,
             f"kosten {vl.kosten:.2f}, optimum {vl.optimum}")

for naam in ("van-den-dam-bewolkt", "van-den-dam-geen-zon"):
    if (vl := v(naam)):
        vdd_basis(vl, naam[12:])
        controle(f"{naam[12:]}: zonder overschot niets voor 13:00",
                 not any(r.paal_w > 0 for r in vl.regels if r.tijd < VDD_ZATERDAG_13), "")
        controle(f"{naam[12:]}: daarna de goedkope middag en nacht", vl.geladen_kwh > 60,
                 f"{vl.geladen_kwh:.1f} kWh")

if (vl := v("van-den-dam-dure-zondagnacht")):
    vdd_basis(vl, "dure zondag")
    zaterdag = [r for r in vl.regels if r.tijd.date() == VDD_ZATERDAG]
    controle("dure zondag: zaterdagmiddag doet het werk",
             sum(r.paal_w for r in zaterdag if 13 <= r.tijd.hour < 17) * vl.stap_uur / 1000 > 40,
             f"{sum(r.paal_w for r in zaterdag if 13 <= r.tijd.hour < 17) * vl.stap_uur / 1000:.1f} kWh")
    controle("dure zondag: en de dure nacht wordt niet gebruikt",
             sum(r.paal_w for r in vl.regels if r.tijd.date() > VDD_ZATERDAG and r.tijd.hour >= 1) * vl.stap_uur / 1000 < 1,
             "laadde in de dure zondagnacht")

if (vl := v("van-den-dam-ford-wekken")):
    vdd_basis(vl, "wekken")
    controle("wekken: op 10 A gewekt en daarna terug naar 6 A",
             any(r.regel.endswith("+wake") and r.amps == 10 for r in vl.regels)
             and any(r.regel == "surplus" and r.amps == 6 for r in vl.regels), "")

if (vl := v("van-den-dam-oven")):
    vdd_basis(vl, "oven")
    # De oven gaat om 12:30 aan; de coach houdt de beurt eerst `STOP_ROUNDS`
    # ronden op de ondergrens vast (tien sinds 05-09-2026, Svens "wekken doe
    # maar per 10 min") en de auto volgt met een minuut. Daarna niets meer.
    controle("oven: tijdens de oven op zaterdagochtend geen net zonder zon",
             vl.net_kwh_tussen("12:42", "13:00") < 0.05, f"{vl.net_kwh_tussen('12:42', '13:00'):.2f} kWh")
    controle("oven: de Equalizer wordt gemeld, niet bevochten",
             meldingen(vl, "lastbewaker") and len(vl.opdrachten) <= 60, f"{len(vl.opdrachten)} opdrachten")

if (vl := v("van-den-dam-p1-weg")):
    vdd_basis(vl, "p1 weg")
    controle("p1 weg: melding over de netmeting", bool(meldingen(vl, "netmeting")), "")
    controle("p1 weg: en daarna gewoon verder op zon",
             any(r.regel == "surplus" for r in regels_in(vl, "11:15", "12:00")), "")

if (vl := v("van-den-dam-prijzen-laat")):
    vdd_basis(vl, "prijzen laat")
    controle("prijzen laat: tot 15:30 alleen zon",
             all(r.paal_amps <= 6.01 for r in vl.regels
                 if r.tijd.date() == VDD_ZATERDAG and r.tijd < virtueel.dt.datetime(2026, 9, 5, 15, 30)), "")
    controle("prijzen laat: daarna vol tot de avondpiek",
             any(r.paal_amps >= 15 for r in regels_in(vl, "15:30", "17:00")), "")
    # Het laatste uur, zondag 04:00 tot 05:00, moet op een rustig tempo en niet
    # met een opdracht per minuut. Gezien op 04-09-2026: 33 opdrachten in dat
    # uur, 14 en 15 A om en om, omdat de auto een minuut achterloopt op de
    # limiet en het tempo elke ronde opnieuw uit de meting werd uitgerekend.
    laatste_uur = [o for o in vl.opdrachten if o[0] >= virtueel.dt.datetime(2026, 9, 6, 4, 0)]
    controle("prijzen laat: geen opdracht per minuut in het laatste uur",
             len(laatste_uur) <= 8, f"{len(laatste_uur)} opdrachten na 04:00")

if (vl := v("van-den-dam-geen-accustand")):
    controle("geen accustand: vraagt erom", bool(meldingen(vl, "weet niet hoe vol")), "")
    controle("geen accustand: en laadt op tijd toch vol via het vangnet", gehaald(vl), f"{vl.soc_bij_klaar_tijd}")

# Onverwachte herstarten van Home Assistant. De coach begint elke keer met een
# leeg geheugen en dezelfde opslag, en de laadbeurt hoort daar niets van te
# merken: geen dubbele meldingen, geen andere beslissing, op tijd vol.
if (vl := v("van-den-dam-herstart")) and (basis := v("van-den-dam")):
    vdd_basis(vl, "herstart")
    controle("herstart: dezelfde laadbeurt als zonder herstarts",
             abs(vl.kosten - basis.kosten) < 0.10 and abs(vl.geladen_kwh - basis.geladen_kwh) < 0.5,
             f"kosten {vl.kosten:.2f} tegen {basis.kosten:.2f}, {vl.geladen_kwh:.1f} tegen {basis.geladen_kwh:.1f} kWh")
    na_10_30 = regels_in(vl, "10:30", "10:34")
    controle("herstart tijdens het laden op zon: binnen drie minuten weer op 6 A",
             any(r.regel == "surplus" and r.amps == 6 for r in na_10_30 if r.tijd.date() == VDD_ZATERDAG),
             f"{[(r.tijd.strftime('%H:%M'), r.regel, r.amps) for r in na_10_30]}")
    na_13_05 = regels_in(vl, "13:05", "13:08")
    controle("herstart net na de prijzen: meteen weer op de goedkope middag",
             any(r.regel == "cheap-hour" and r.amps >= 15 for r in na_13_05 if r.tijd.date() == VDD_ZATERDAG),
             f"{[(r.tijd.strftime('%H:%M'), r.regel, r.amps) for r in na_13_05]}")
    controle("herstart: geen enkele valse melding",
             not meldingen(vl, "niet lezen") and not meldingen(vl, "meldt al") and not meldingen(vl, "niets meer beslist"),
             f"{[m for _, m in vl.meldingen]}")
    # Bekend en niet verholpen: na de herstart om 04:20 kent de coach het begin
    # van de beurt niet meer en zegt het verslag "sinds 04:20 ... en toen liep
    # hij al". Eerlijk, maar onvolledig. Zie de notities van 04-09-2026.
    controle("herstart: het verslag zegt eerlijk dat hij midden in de beurt instapte",
             any("liep hij al" in m for m in meldingen(vl, "is vol")), f"{meldingen(vl, 'is vol')}")

# Een sensor die wegvalt wordt na tien minuten gemeld, en als hij terug is ook.
# Sven op 04-09-2026: "wat als een sensor ineens niet meer beschikbaar is. Dat
# moet wel gemeld worden." Ondertussen laadt de coach gewoon door op wat hij
# het laatst wist.
for naam, sensor, wat, van, tot in (
    ("van-den-dam-accustand-weg", "accustand van Ford", "cheap-hour", "13:30", "14:15"),
    ("van-den-dam-status-weg", "status van Laadpaal", "surplus", "11:00", "11:20"),
    ("van-den-dam-zonsensor-weg", "zonnesensor", "surplus", "10:00", "10:20"),
    ("van-den-dam-equalizer-weg", "lastbewaker", "cheap-hour", "14:00", "14:30"),
):
    if not (vl := v(naam)):
        continue
    kort = naam[12:]
    vdd_basis(vl, kort)
    stil = meldingen(vl, "meldt al 10 minuten niets")
    controle(f"{kort}: na tien minuten één melding dat de sensor niets zegt",
             len(stil) == 1 and sensor in stil[0], f"{stil}")
    weer = meldingen(vl, "doet het weer")
    controle(f"{kort}: en één als hij terug is", len(weer) == 1 and sensor in weer[0], f"{weer}")
    tijdens = [r for r in regels_in(vl, van, tot) if r.tijd.date() == VDD_ZATERDAG]
    controle(f"{kort}: ondertussen laadt hij gewoon door",
             tijdens and all(r.paal_w > 0 for r in tijdens[3:]) and any(r.regel == wat for r in tijdens),
             f"{sorted({r.regel for r in tijdens})}, laagste {min((r.paal_w for r in tijdens), default=0):.0f} W")
    controle(f"{kort}: en is even goedkoop uit als zonder storing",
             (basis := v("van-den-dam")) is not None and abs(vl.kosten - basis.kosten) < 0.10,
             f"{vl.kosten:.2f}")

if (vl := v("van-den-dam-prijssensor-weg-om-13")):
    vdd_basis(vl, "prijssensor weg om 13")
    controle("prijssensor weg: gemeld na tien minuten, om 13:00",
             any(t.time() == virtueel.dt.time(13, 0) and "prijssensor" in m for t, m in vl.meldingen),
             f"{[(t.strftime('%H:%M'), m[:40]) for t, m in vl.meldingen]}")
    controle("prijssensor weg: zonder prijzen niets van het net",
             not laadt_tussen(vl, "12:54", "13:39"), "laadde zonder prijzen")
    na = [r for r in regels_in(vl, "13:40", "13:43") if r.tijd.date() == VDD_ZATERDAG]
    controle("prijssensor weg: zodra hij terug is, meteen de prijzen van zondag en vol",
             any(r.regel == "cheap-hour" and r.amps >= 15 for r in na),
             f"{[(r.tijd.strftime('%H:%M'), r.regel, r.amps) for r in na]}")
    controle("prijssensor weg: en gemeld dat hij het weer doet",
             any("prijssensor doet het weer" in m for _, m in vl.meldingen), "")

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

print(f"\n{GOED} goed, {FOUT} fout")
sys.exit(1 if FOUT else 0)
