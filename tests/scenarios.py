"""De scenario's voor het virtuele huis.

Elk scenario is één laadbeurt in één soort woning. De assen waarlangs ze
verschillen zijn de installatievormen die er bij klanten zijn: het contract,
het weer, het moment dat de kabel erin gaat, de klaar-tijd, de auto, de meter,
en wat er onderweg misgaat. Zie `virtueel.py` voor wat elk veld doet.

Twee afspraken van de eigenaar (04-09-2026) die de controles in `test_virtueel.py`
bewaken:

- **Vast contract:** laden in de zonuren is goedkoper, en naar de prijs hoeft
  niet gekeken te worden, want die is elk uur hetzelfde. Wat er van het net
  bij moet komt na de avondpiek (`EVENING_START` in planner.py).
- **Dynamisch contract:** alles telt mee: zon, prijs, teruglevering, salderen.
"""

from dataclasses import replace

from virtueel import Airco, Auto, Batterij, Boiler, Huis, Paal, Prijzen, Scenario, Vaatwasser, Zon

# Twee auto's die er in het echt hangen: een kleine bus op één fase, en een
# grote op drie.
BUS = Auto(naam="Bus", capaciteit_kwh=19.7, soc=30.0, fasen=1, max_amps=16.0, wek_amps=10.0)
GROTE = Auto(naam="Grote", capaciteit_kwh=77.0, soc=20.0, fasen=3, max_amps=16.0)

# het voorbeeld van 04-09-2026: "de goedkoopste uren zijn vanaf 13 uur tot een
# uurtje of 17 en dan in de nacht weer." Een dag waarop de ochtend duurder is
# dan de middag en de nacht, kaal per uur.
MARKT_VAST = [
    0.070, 0.060, 0.050, 0.050, 0.060, 0.080, 0.100, 0.120,
    0.130, 0.120, 0.110, 0.100, 0.090, 0.030, 0.020, 0.030,
    0.050, 0.140, 0.190, 0.210, 0.150, 0.120, 0.100, 0.090,
]

# --- vast contract -----------------------------------------------------------

vast_zonnig = Scenario(
    "vast-zonnig",
    "vast contract, heldere dag, bus op 30% om 07:00 erin, klaar om 06:00",
    contract="vast", zon=Zon(wolken="helder"), auto=BUS,
)
vast_bewolkt = vast_zonnig.kopie(
    naam="vast-bewolkt", uitleg="vast contract, bewolkt: te weinig zon, dus na de avondpiek van het net",
    zon=Zon(wolken="bewolkt"),
)
vast_geen_zon = vast_zonnig.kopie(
    naam="vast-geen-panelen", uitleg="vast contract, woning zonder zonnepanelen",
    zon=Zon(wolken="geen"), voorspeller="geen",
)
vast_wisselend = vast_zonnig.kopie(
    naam="vast-wisselend", uitleg="vast contract, wolkenvelden: de zon komt en gaat per twintig minuten",
    zon=Zon(wolken="wisselend"),
)
vast_salderen = vast_zonnig.kopie(
    naam="vast-salderen", uitleg="vast contract mét salderen: eigen zon is dan bijna niets waard",
    contract="vast-salderen", vast_terugleverkosten=0.05,
)
vast_avond = vast_zonnig.kopie(
    naam="vast-avond-erin", uitleg="vast contract, kabel om 18:30 erin, klaar om 06:00",
    begin="2026-09-07 18:25", kabel_erin="18:30", duur_uren=13,
)
vast_grote_auto = vast_zonnig.kopie(
    naam="vast-grote-auto", uitleg="vast contract, driefasige auto van 77 kWh op 20%",
    auto=GROTE,
)
vast_zonder_voorspelling = vast_zonnig.kopie(
    naam="vast-zonder-voorspelling", uitleg="vast contract, zonnig, maar geen enkele zonvoorspelling ingevuld",
    voorspeller="geen",
)
vast_sensoren = vast_zonnig.kopie(
    naam="vast-sensor-voorspelling", uitleg="vast contract, alleen de vier losse voorspellingssensoren, geen dashboard",
    voorspeller="sensoren",
)
vast_voorspelling_mis = vast_zonnig.kopie(
    naam="vast-voorspelling-mis", uitleg="voorspeld helder, in werkelijkheid bewolkt",
    zon=Zon(wolken="bewolkt", voorspeld="helder"),
)
vast_geen_klaar_tijd = vast_zonnig.kopie(
    naam="vast-geen-klaar-tijd", uitleg="vast contract, zonnig, schema uit: alleen laden als het loont",
    schema_aan=False, duur_uren=36,
)
vast_krap = vast_zonnig.kopie(
    naam="vast-krappe-klaar-tijd", uitleg="vast contract, bus op 55% om 13:00 erin, klaar om 17:00: past net, met het uur ervoor",
    begin="2026-09-07 12:55", kabel_erin="13:00", klaar_om="17:00", duur_uren=6,
    auto=replace(BUS, soc=55.0),
)
vast_onhaalbaar = vast_zonnig.kopie(
    naam="vast-onhaalbare-klaar-tijd", uitleg="bus op 10% om 13:00 erin, klaar om 17:00: past niet, dus vol vermogen en zeggen",
    begin="2026-09-07 12:55", kabel_erin="13:00", klaar_om="17:00", duur_uren=6,
    auto=replace(BUS, soc=10.0),
)

# --- dynamisch contract ------------------------------------------------------

dyn_zonnig = vast_zonnig.kopie(
    naam="dynamisch-zonnig", uitleg="dynamisch all-in, heldere dag, bus op 30% om 07:00 erin",
    contract="dynamisch",
)
dyn_bewolkt = dyn_zonnig.kopie(
    naam="dynamisch-bewolkt", uitleg="dynamisch, bewolkt: de goedkoopste uren van de nacht",
    zon=Zon(wolken="bewolkt"),
)
dyn_geen_zon = dyn_zonnig.kopie(
    naam="dynamisch-geen-panelen", uitleg="dynamisch, woning zonder panelen",
    zon=Zon(wolken="geen"), voorspeller="geen",
)
dyn_markt = dyn_zonnig.kopie(
    naam="dynamisch-markt", uitleg="dynamisch met kale marktprijs plus belasting, opslag en btw",
    contract="dynamisch-markt",
)
dyn_salderen = dyn_zonnig.kopie(
    naam="dynamisch-salderen", uitleg="dynamisch mét salderen: zon is evenveel waard als inkoop min opslag",
    contract="dynamisch-salderen",
)
dyn_avond = dyn_zonnig.kopie(
    naam="dynamisch-avond-erin", uitleg="dynamisch, kabel om 18:30 erin tijdens de dure uren",
    begin="2026-09-07 18:25", kabel_erin="18:30", duur_uren=13,
)
dyn_grote_auto = dyn_zonnig.kopie(
    naam="dynamisch-grote-auto", uitleg="dynamisch, driefasige auto van 77 kWh op 20%",
    auto=GROTE,
)
dyn_negatief = dyn_zonnig.kopie(
    naam="dynamisch-negatief-middag", uitleg="dynamisch, negatieve prijzen rond het middaguur",
    prijzen=Prijzen(markt=[
        0.070, 0.065, 0.060, 0.060, 0.065, 0.080, 0.095, 0.110,
        0.130, 0.100, 0.020, -0.020, -0.050, -0.060, -0.040, 0.000,
        0.080, 0.140, 0.190, 0.210, 0.160, 0.120, 0.100, 0.085,
    ]),
)
dyn_kwartier_later = dyn_zonnig.kopie(
    naam="dynamisch-prijzen-laat", uitleg="dynamisch, de prijzen van morgen komen pas om 15:00",
    prijzen=Prijzen(bekend_om="15:00"),
)
# Zonder accustand, in de goedkope uren (v0.185.0), bij een dynamisch contract: het goedkoopste uur.
dyn_zonder_accustand = dyn_avond.kopie(
    naam="dynamisch-zonder-accustand",
    uitleg="dynamisch, een bus zonder accustand en het vinkje aan: alleen in het goedkoopste uur van het etmaal",
    auto=Auto(meldt_soc=False), goedkoop_blok=True, duur_uren=36,
)
dyn_zonder_accustand_donker = dyn_zonder_accustand.kopie(
    naam="dynamisch-zonder-accustand-donker",
    uitleg="hetzelfde zonder panelen: van het net, en alleen in het goedkoopste uur",
    zon=dyn_geen_zon.zon, voorspeller=dyn_geen_zon.voorspeller,
)
dyn_geen_klaar_tijd = dyn_zonnig.kopie(
    naam="dynamisch-geen-klaar-tijd", uitleg="dynamisch, schema uit",
    schema_aan=False, duur_uren=36,
)

# --- de laadmodus zonder planning (v0.87.0) -----------------------------------
# De eigenaar op 23-09-2026, naar evcc: "de modus is leidend (snel, continu of zon),
# tenzij er een planning ingesteld is. Geen planning, standaard terug naar zon."
vast_zon_modus = vast_geen_klaar_tijd.kopie(
    naam="modus-zon", uitleg="schema uit, modus zon, heldere dag: alleen op overschot, niets van het net",
    laadmodus="zon",
)
bewolkt_zon_modus = vast_zon_modus.kopie(
    naam="modus-zon-bewolkt", uitleg="schema uit, modus zon, bewolkt: pas laden als het dak de ondergrens haalt",
    zon=Zon(wolken="bewolkt"),
)
# v0.103.0, de eigenaar op 30-09-2026 over evcc: "In evcc kun je nu instellen dat de
# lader al mag starten bij bijv 50% van die 4,1 kW ... en vult 2,1 kW aan uit het net."
half_zon_modus = bewolkt_zon_modus.kopie(
    naam="modus-zon-half", uitleg="modus zon vanaf 50%, bewolkt: eerder beginnen, het net vult aan tot 6 A",
    zon_start=50,
)
dyn_continu = dyn_geen_klaar_tijd.kopie(
    naam="modus-continu", uitleg="schema uit, modus continu op 8 A: meteen laden, met de zon erbovenop",
    laadmodus="continu", continu_amps=8,
)

# --- de meter en de aansluiting ----------------------------------------------

meter_teken = vast_zonnig.kopie(
    naam="meter-met-teken", uitleg="één netsensor met een teken, negatief bij teruglevering",
    net="signed",
)
meter_teken_om = vast_zonnig.kopie(
    naam="meter-teken-omgekeerd", uitleg="één netsensor met een teken, positief bij teruglevering",
    net="signed-omgekeerd",
)
een_fase_krap = vast_zonnig.kopie(
    naam="eenfase-krappe-zekering", uitleg="1x25 A aansluiting, koken van 4 kW terwijl de bus laadt",
    aansluiting_fasen=1, zekering=25.0, huis=Huis(koken_w=4000.0),
    begin="2026-09-07 16:55", kabel_erin="17:00", klaar_om="23:45", duur_uren=7,
    auto=replace(BUS, soc=30.0), stap_seconden=10,
)
oven = vast_zonnig.kopie(
    naam="oven-tijdens-laden", uitleg="dynamisch, geen zon, 1x25 A: om 02:00 gaat er 3 kW bij terwijl de bus op 16 A laadt",
    contract="dynamisch", aansluiting_fasen=1, zekering=25.0, zon=Zon(wolken="geen"), voorspeller="geen",
    huis=Huis(basis_w=1200.0), begin="2026-09-07 22:55", kabel_erin="23:00", duur_uren=8,
    gebeurtenissen=[("02:00", "oven", 30)], stap_seconden=10,
)
lastbewaker = vast_zonnig.kopie(
    naam="met-lastbewaker", uitleg="een installatie met een eigen lastbewaker",
    lastbewaker=True,
)
# De nacht van 09 op 10-09-2026 in de klantwoning: een warmtepomp die om het
# kwartier een paar minuten 22 A op één fase trekt, zonder patroon. De coach
# meet vanaf het inpluggen wat er gemiddeld voor de paal overblijft en rekent
# daarmee (`structural_ceiling` in planner.py). Het zusje zonder warmtepomp
# laat zien dat een rustig huis er niets van merkt.
warmtepomp = dyn_grote_auto.kopie(
    naam="warmtepomp-nacht",
    uitleg="dynamisch, geen zon, 3x25 A met Equalizer: de grote auto om 17:30 erin op 50%, klaar om 06:00; vanaf 17:45 om het kwartier vier minuten 5,5 kW op de zware fase, de hele nacht door",
    zon=Zon(wolken="geen"), voorspeller="geen",
    huis=Huis(basis_w=300.0, verdeling=(0.1, 0.1, 0.8)), oven_w=5500.0,
    begin="2026-09-09 17:25", kabel_erin="17:30", klaar_om="06:00", duur_uren=13,
    auto=replace(GROTE, soc=50.0), equalizer=True, zekering=25.0, aansluiting_fasen=3,
    stap_seconden=10,
    gebeurtenissen=[(f"{h:02d}:{m:02d}", "oven", 4)
                    for h in list(range(17, 24)) + list(range(0, 6))
                    for m in (0, 15, 30, 45) if h < 17 or (h, m) >= (17, 45)],
)
# De nacht van 18 op 19-09-2026 in de klantwoning: de coach zakt een paar keer
# lang voor de zekering, en de Ford komt daarna pas na tien minuten terug. Die
# minuten horen niet als zijn tempo in de opslag; om 03:35 stond er 5,52 kW voor
# band 6 terwijl hij daar 10 kW trok. Zie `TEMPO_HERSTEL` in coach.py.
ford_bijkomen = warmtepomp.kopie(
    naam="ford-bijkomen",
    uitleg="dynamisch, geen zon, 3x25 A met Equalizer, de grote auto om 17:30 erin op 50%; drie keer een kwartier 3 kW op de zware fase, en na zo'n verlaging blijft de auto nog tien minuten op de oude stroom",
    auto=replace(GROTE, soc=50.0, bijkomen_min=10), oven_w=3000.0,
    gebeurtenissen=[("23:15", "oven", 16), ("01:26", "oven", 16), ("03:17", "oven", 16)],
)
# En wat er in de klantwoning op 19-09-2026 al in de opslag stond: 5,52 kW voor
# band 6 en 6,9 voor band 7, rijen zonder accustand. De eerste beurt waarin de
# auto daar gewoon het plafond trekt haalt ze weg.
ford_oude_opslag = ford_bijkomen.kopie(
    naam="ford-oude-opslag",
    uitleg="hetzelfde huis, en de coach heeft van een eerdere nacht nog een te laag tempo voor band 6 en 7 bewaard",
    geleerd_tempo={6: 5.52, 7: 6.9},
)
warmtepomp_uit = warmtepomp.kopie(
    naam="warmtepomp-uit", uitleg="hetzelfde huis, maar de warmtepomp blijft de hele nacht uit",
    gebeurtenissen=[],
)

# --- de auto -----------------------------------------------------------------

geen_soc = vast_zonnig.kopie(
    naam="accustand-onbekend", uitleg="de auto meldt geen accustand en niemand geeft er een op",
    auto=replace(BUS, meldt_soc=False),
)
soc_opgegeven = geen_soc.kopie(
    naam="accustand-opgegeven", uitleg="geen accustand uit de auto, bewoner geeft om 07:30 30% op",
    gebeurtenissen=[("07:30", "soc_opgeven", 30)],
)
soc_traag = vast_zonnig.kopie(
    naam="accustand-traag", uitleg="de app van de auto loopt twee minuten achter",
    auto=replace(BUS, soc_vertraging_min=2),
)
laadgrens = vast_zonnig.kopie(
    naam="laadgrens-80", uitleg="de auto stopt zelf op 80%",
    auto=replace(BUS, laadgrens=80.0),
)
# Dezelfde auto, maar nu staat die 80% ook in het profiel. het gemeten geval,
# 16-09-2026: zonder het doel rekende de coach tot 100, vroeg hij om 10:46 een
# herstart voor een bus die precies deed wat hij moest doen, en stuurde hij een
# kritieke melding over 70% omdat de Ford-app nog niet bijgewerkt was. Met het
# doel erbij stopt hij uit zichzelf, zonder herstart en zonder alarm.
laadgrens_ingesteld = vast_zonnig.kopie(
    naam="laadgrens-80-ingesteld", uitleg="de auto stopt op 80% en dat staat ook in het profiel",
    auto=replace(BUS, laadgrens=80.0, doel=80.0),
)
# En het geval waarin alleen het profiel het zegt: de auto zou tot 100 laden,
# maar de bewoner wil op 80 stoppen. Dan is de coach degene die ophoudt.
doel_onder_auto = vast_zonnig.kopie(
    naam="doel-80", uitleg="de auto kan tot 100, de bewoner wil tot 80",
    auto=replace(BUS, doel=80.0),
)
# de eigen Ford meldt zijn accustand per tien procent, ongeveer elk half uur.
# Tussen twee stappen staat het beeld van de coach stil terwijl de auto voller
# wordt: op 17-09-2026 zei de kaart om 22:26 "nog 2,2 kWh" terwijl er 0,18 kWh
# in ging. Met het doel op 80 is het de coach die hoort op te houden, en dat kan
# hij alleen met een stand die bijgeteld is.
# Krap gezet, want daar kost het geld: zolang de sensor op een oude stap staat
# denkt de coach tot een hele stap meer nodig te hebben dan waar, en dat is bij
# deze bus ruim twee kilowattuur oftewel een half uur op vol vermogen. Dan
# slaat de klaar-tijdregel aan terwijl er zon ligt.
soc_stappen = vast_zonnig.kopie(
    naam="accustand-per-tien",
    uitleg="de auto meldt zijn accustand per tien procent; om 13:00 erin op 55%, klaar om 17:00",
    begin="2026-09-07 12:55", kabel_erin="13:00", klaar_om="17:00", duur_uren=6,
    auto=replace(BUS, soc=55.0, soc_stap=10.0, soc_vertraging_min=3),
)
bijna_vol = vast_zonnig.kopie(
    naam="bijna-vol", uitleg="bus op 95% erin",
    auto=replace(BUS, soc=95.0),
)
auto_slaapt = vast_zonnig.kopie(
    naam="auto-wordt-niet-wakker", uitleg="een auto die helemaal niet op gang komt: zelfs het hele plafond wekt hem niet",
    # Meer dan de paal kan geven (16 A), dus geen wekpoging helpt. Tot
    # 17-09-2026 stond hier 14 A: toen bood de coach er tien aan en was dat
    # genoeg om hem stil te houden. Sinds de wekstroom op zestien staat is dat
    # geen slapende auto meer maar een auto die gewoon wakker wordt, en juist
    # dat moest deze proef niet meten.
    auto=replace(BUS, wek_amps=20.0),
)

# --- de bewoner --------------------------------------------------------------

pauze = vast_zonnig.kopie(
    naam="pauze-van-bewoner", uitleg="om 12:00 pauze, om 15:00 weer hervat",
    gebeurtenissen=[("12:00", "pauze", True), ("15:00", "pauze", False)],
)
pauze_vergeten = vast_zonnig.kopie(
    naam="pauze-vergeten", uitleg="om 12:00 pauze en nooit meer hervat",
    gebeurtenissen=[("12:00", "pauze", True)],
)
snelladen = vast_zonnig.kopie(
    naam="snelladen", uitleg="om 09:00 snelladen aan",
    gebeurtenissen=[("09:00", "snelladen", True)],
)
kabel_eruit = vast_zonnig.kopie(
    naam="kabel-eruit-middenin", uitleg="om 13:10 gaat de kabel eruit, om 18:00 weer erin op 60%",
    gebeurtenissen=[("13:10", "kabel_uit", None), ("18:00", "kabel_in", 60)],
)
oude_tijden = vast_zonnig.kopie(
    naam="oude-begintijd-genegeerd",
    uitleg="een laadpaal met nog een 'niet eerder dan 23:00' en 'starten om 22:00' in zijn instellingen: telt niet meer",
    niet_voor="23:00", uiterlijk_starten="22:00",
)

# --- het voorbeeld: om tien uur erin, klaar om zes -------------------------

tien_uur = Scenario(
    "tien-uur-erin-dynamisch",
    "dynamisch, geen panelen, grote auto om 10:00 erin, goedkoop van 13 tot 17 en 's nachts",
    contract="dynamisch", zon=Zon(wolken="geen"), voorspeller="geen", auto=GROTE,
    prijzen=Prijzen(markt=MARKT_VAST), begin="2026-09-07 09:55", kabel_erin="10:00",
    duur_uren=21,
)
tien_uur_zon = tien_uur.kopie(
    naam="tien-uur-erin-zon", uitleg="hetzelfde, maar met een helder dak: de zon van 10 uur is goedkoper dan 13 uur",
    zon=Zon(wolken="helder"), voorspeller="dashboard",
)
tien_uur_valt_tegen = tien_uur.kopie(
    naam="tien-uur-zon-valt-tegen", uitleg="voorspeld helder, in werkelijkheid bewolkt: hij moet 's nachts meer bijkopen",
    zon=Zon(wolken="bewolkt", voorspeld="helder"), voorspeller="dashboard",
)
tien_uur_vast = tien_uur.kopie(
    naam="tien-uur-erin-vast", uitleg="vast contract, grote auto om 10:00 erin, helder dak",
    contract="vast", zon=Zon(wolken="helder"), voorspeller="dashboard",
)
equalizer = tien_uur.kopie(
    naam="equalizer-knijpt", uitleg="3x25 A met een Equalizer; van 13:30 tot 15:00 trekt het huis 7 kW en knijpt hij de paal",
    equalizer=True, huis=Huis(extra=[("13:30", "15:00", 7000.0)]),
)
# het tweede voorbeeld: zondag uitgevinkt, dus klaar op maandag 06:00. Tot
# de prijzen van maandag er zijn (zondag rond 13:00) alleen zon.
weekend = tien_uur.kopie(
    naam="weekend-zondag-uit",
    uitleg="zaterdag 10:00 erin, zondag uitgevinkt, klaar maandag 06:00: tot zondag 13:00 alleen zon",
    zon=Zon(wolken="helder"), voorspeller="dashboard",
    begin="2026-09-12 09:55", kabel_erin="10:00", duur_uren=44, dagen_uit=(6,),
)
weekend_geen_zon = weekend.kopie(
    naam="weekend-zondag-uit-geen-zon", uitleg="hetzelfde zonder panelen: niets tot zondag 13:00, dan plannen",
    zon=Zon(wolken="geen"), voorspeller="geen",
)
# Zaterdag zat de voorspeller er flink naast en zondag klopt hij. Zonder de
# grens van `solar_day` zou de meting van zaterdagavond de hele zondag op een
# derde zetten, en dan plant de coach zaterdagnacht van het net wat hij zondag
# gratis van het dak had kunnen halen. Dynamisch, want daar kost dat geld.
weekend_voorspelling_mis = weekend.kopie(
    naam="weekend-voorspelling-mis",
    uitleg="zaterdag bewolkt terwijl helder voorspeld was, zondag klopt het weer; klaar maandag 06:00",
    contract="dynamisch",
    zon=Zon(wolken="helder", voorspeld="helder", wolken_per_dag={0: "bewolkt"}),
)
prijzen_weg = tien_uur.kopie(
    naam="prijzen-weg-bij-inpluggen", uitleg="de prijssensor zwijgt de eerste twintig minuten na het inpluggen",
    gebeurtenissen=[("10:00", "prijzen_weg", 20)],
)

# --- storingen ---------------------------------------------------------------

p1_weg = vast_zonnig.kopie(
    naam="p1-valt-weg", uitleg="de P1-meter valt om 12:00 drie minuten weg tijdens het laden op zon",
    gebeurtenissen=[("12:00", "p1_weg", 3)],
)
p1_lang_weg = vast_zonnig.kopie(
    naam="p1-lang-weg", uitleg="de P1-meter valt om 12:00 twintig minuten weg",
    gebeurtenissen=[("12:00", "p1_weg", 20)],
)
paal_traag = vast_zonnig.kopie(
    naam="teller-per-uur", uitleg="de teller van de paal werkt maar één keer per uur bij (zoals een Easee)",
    paal=Paal(teller_interval_min=60),
    auto=replace(BUS, meldt_soc=False),
    gebeurtenissen=[("07:05", "soc_opgeven", 30)],
)

# --- de klantwoning, het weekend van 04-09-2026 -----------------------------------
#
# De eerste echte laadbeurt met v0.47.x, nagebouwd met zijn eigen cijfers zoals
# ze vrijdagavond 21:21 in Home Assistant stonden: de all-in prijzen van
# vrijdag en zaterdag, de zonkromme van het energiedashboard voor zaterdag
# (lokale uren), het huisverbruik als mediaan per uur over de week ervoor uit
# de eigen opslag, de Ford op 8,5%, de Equalizer, zaterdag uitgevinkt en
# zondag klaar om 06:00. Zondag zelf kende niemand nog; die staat hier als
# een aanname en er is een variant met een dure zondagnacht.
KLANT_HUIS_W = {
    0: 1138, 1: 1052, 2: 1026, 3: 1355, 4: 949, 5: 723, 6: 640, 7: 972,
    8: 1029, 9: 1048, 10: 970, 11: 986, 12: 972, 13: 1300, 14: 1419, 15: 1263,
    16: 1576, 17: 1589, 18: 1322, 19: 1299, 20: 1507, 21: 1244, 22: 1809, 23: 1085,
}
KLANT_ZON_KWH = {
    7: 0.54, 8: 1.12, 9: 1.56, 10: 1.88, 11: 2.28, 12: 2.64, 13: 2.68,
    14: 2.42, 15: 2.0, 16: 1.64, 17: 1.24, 18: 0.73, 19: 0.34,
}
KLANT_VRIJDAG = [
    0.3018, 0.2790, 0.2694, 0.2690, 0.2600, 0.2609, 0.2899, 0.3133,
    0.3141, 0.2957, 0.2574, 0.2048, 0.1870, 0.1694, 0.1776, 0.1779,
    0.1872, 0.2141, 0.2829, 0.3032, 0.3117, 0.3159, 0.3098, 0.2993,
]
KLANT_ZATERDAG = [
    0.2320, 0.2321, 0.2243, 0.2047, 0.2010, 0.2026, 0.2198, 0.2070,
    0.1835, 0.1320, 0.1287, 0.1244, 0.1182, 0.1123, 0.1137, 0.1210,
    0.1269, 0.1858, 0.3105, 0.3616, 0.3918, 0.4000, 0.3902, 0.3666,
]
# Zondag: een aanname, de zaterdag met een iets duurdere nacht.
KLANT_ZONDAG = [
    0.2500, 0.2450, 0.2400, 0.2300, 0.2250, 0.2280, 0.2350, 0.2200,
    0.1900, 0.1500, 0.1400, 0.1350, 0.1300, 0.1250, 0.1280, 0.1350,
    0.1400, 0.1950, 0.3200, 0.3700, 0.3900, 0.4000, 0.3900, 0.3600,
]
KLANT_ZONDAG_DUUR = [0.31] * 8 + KLANT_ZONDAG[8:]
FORD = Auto(naam="Ford", capaciteit_kwh=65.0, soc=8.5, fasen=3, max_amps=16.0)
KLANT_PRIJZEN = {"2026-09-04": KLANT_VRIJDAG, "2026-09-05": KLANT_ZATERDAG, "2026-09-06": KLANT_ZONDAG}

klantwoning = Scenario(
    "klantwoning",
    "vrijdag 19:01 erin op 8,5%, zaterdag uit, zondag klaar om 06:00, met zijn eigen prijzen, zon en huis",
    contract="dynamisch-salderen",
    zon=Zon(kromme=KLANT_ZON_KWH), huis=Huis(profiel=KLANT_HUIS_W, verdeling=(0.25, 0.15, 0.6)),
    auto=FORD, paal=Paal(teller_interval_min=60),
    prijzen=Prijzen(per_dag=KLANT_PRIJZEN),
    begin="2026-09-04 18:55", kabel_erin="19:01", klaar_om="06:00", dagen_uit=(5,),
    duur_uren=36, equalizer=True, zekering=25.0, aansluiting_fasen=3,
)
klant_bewolkt = klantwoning.kopie(
    naam="klantwoning-bewolkt", uitleg="hetzelfde, maar zaterdag valt de zon tegen: een derde van de verwachting",
    zon=Zon(kromme=KLANT_ZON_KWH, wolken="bewolkt", voorspeld="helder"),
)
klant_geen_zon = klantwoning.kopie(
    naam="klantwoning-geen-zon", uitleg="hetzelfde, zaterdag helemaal dicht terwijl helder voorspeld was",
    zon=Zon(kromme=KLANT_ZON_KWH, wolken="geen", voorspeld="helder"),
)
klant_dure_zondag = klantwoning.kopie(
    naam="klantwoning-dure-zondagnacht", uitleg="hetzelfde, maar de zondagnacht wordt 0,31: dan moet zaterdagmiddag het werk doen",
    prijzen=Prijzen(per_dag={**KLANT_PRIJZEN, "2026-09-06": KLANT_ZONDAG_DUUR}),
)
klant_wekken = klantwoning.kopie(
    naam="klantwoning-ford-wekken", uitleg="hetzelfde, de Ford wil 10 A om wakker te worden en krijgt sinds 17-09-2026 het hele plafond aangeboden",
    auto=replace(FORD, wek_amps=10.0),
)
klant_koken = klantwoning.kopie(
    naam="klantwoning-oven", uitleg="hetzelfde, zaterdag om 12:30 een uur lang 3 kW erbij op de zware fase",
    gebeurtenissen=[("12:30", "oven", 60)],
)
klant_p1_weg = klantwoning.kopie(
    naam="klantwoning-p1-weg", uitleg="hetzelfde, de P1 valt zaterdag om 11:00 een kwartier weg",
    gebeurtenissen=[("11:00", "p1_weg", 15)],
)
klant_prijzen_laat = klantwoning.kopie(
    naam="klantwoning-prijzen-laat", uitleg="hetzelfde, de prijzen van zondag komen pas om 15:30",
    prijzen=Prijzen(bekend_om="15:30", per_dag=KLANT_PRIJZEN),
)
klant_geen_soc = klantwoning.kopie(
    naam="klantwoning-geen-accustand", uitleg="hetzelfde, de Ford meldt zijn accustand niet",
    auto=replace(FORD, meldt_soc=False),
)
# De eigenaar op 04-09-2026, laat: "ook onverwachte herstarten, en wat als een sensor
# ineens niet meer beschikbaar is. Dat moet wel gemeld worden."
klant_herstart = klantwoning.kopie(
    naam="klantwoning-herstart",
    uitleg="Home Assistant herstart vijf keer: vr 23:00, za 04:20, za 10:30 op zon, za 13:05 net na de prijzen, zo 04:20 in het laatste uur",
    gebeurtenissen=[("23:00", "herstart", None), ("04:20", "herstart", None),
                    ("10:30", "herstart", None), ("13:05", "herstart", None),
                    ("+1 04:20", "herstart", None)],
)
klant_soc_weg = klantwoning.kopie(
    naam="klantwoning-accustand-weg",
    uitleg="de accustand van de Ford is zaterdag van 13:30 tot 14:45 niet beschikbaar, midden in het laden",
    # Vijf kwartier, want een auto mag een uur zwijgen voordat dat een melding
    # is (`SENSOR_STIL_AUTO`, de eigenaar op 22-09-2026).
    gebeurtenissen=[("13:30", "sensor_weg", ("soc", 75))],
)
klant_status_weg = klantwoning.kopie(
    naam="klantwoning-status-weg",
    uitleg="de status van de Easee is zaterdag van 11:00 tot 11:20 niet beschikbaar, tijdens het laden op zon",
    gebeurtenissen=[("11:00", "sensor_weg", ("status", 20))],
)
klant_zon_weg = klantwoning.kopie(
    naam="klantwoning-zonsensor-weg",
    uitleg="de zonnesensor is zaterdag van 10:00 tot 10:20 niet beschikbaar",
    gebeurtenissen=[("10:00", "sensor_weg", ("zon", 20))],
)
klant_equalizer_weg = klantwoning.kopie(
    naam="klantwoning-equalizer-weg",
    uitleg="de Equalizer-sensor is zaterdag van 14:00 tot 14:30 niet beschikbaar, tijdens het laden op 16 A",
    gebeurtenissen=[("14:00", "sensor_weg", ("equalizer", 30))],
)
klant_prijzen_weg_13 = klantwoning.kopie(
    naam="klantwoning-prijssensor-weg-om-13",
    uitleg="de prijssensor valt van 12:50 tot 13:40 weg, precies als de prijzen van zondag komen",
    gebeurtenissen=[("12:50", "prijzen_weg", 50)],
)
KLANTWONING = [klantwoning, klant_bewolkt, klant_geen_zon, klant_dure_zondag, klant_wekken,
               klant_koken, klant_p1_weg, klant_prijzen_laat, klant_geen_soc,
               klant_herstart, klant_soc_weg, klant_status_weg, klant_zon_weg, klant_equalizer_weg,
               klant_prijzen_weg_13]

# --- wat de nacht van 05 op 06-09-2026 in de klantwoning leerde -----------------
#
# Om 04:17 koos de Easee in zijn automatische fasemodus één fase, de Ford trok
# 16,9 A op een groep van 16 A, de paal herstartte de sessie op drie fasen en
# de Ford ging in storing: "completed" op 86%. Pas een start om 05:18 kreeg
# hem om 05:27 weer aan het laden. De eigenaar: de fasemodus blijft (gastauto's), dus
# de coach hoort met de gemeten fase te rekenen, onder de groep te blijven, en
# een auto die niet vol is zelf opnieuw te starten.
ford_storing = dyn_zonnig.kopie(
    naam="ford-storing", uitleg="dynamisch, grote auto op 60%; om 13:00 gaat hij midden in het laden in storing en de paal zegt 'completed'",
    auto=replace(GROTE, soc=60.0, storing_bij_herstart=True),
    gebeurtenissen=[("13:00", "storing", None)],
)
ford_storing_traag = ford_storing.kopie(
    naam="ford-storing-traag",
    uitleg="als ford-storing, maar de auto komt pas 27 minuten na de herstart terug: eerst 'laadt niet verder', en als hij later vol is nog een verslag",
    # De klantwoning op 10-10-2026: storing om 00:51 op 36%, herstart door de
    # coach om 00:55:19, de Ford laadde om 01:22:01 weer en was om 06:48 vol.
    auto=replace(GROTE, soc=60.0, storing_bij_herstart=True, storing_herstel_min=27),
)
# De klantwoning op 23-10-2026 (v0.153.0): de Ford ging bij het inpluggen om
# 19:29 in storing terwijl de coach tot 00:45 wachtte. Om 21:24 kwam er stroom
# met een start (de bewoner zette Snel aan) en binnen een minuut laadde hij.
FORD_INPLUG = replace(GROTE, soc=38.0, storing_bij_inpluggen=True, storing_herstel_min=1, proefladen=True)
ford_inpluggen = dyn_geen_zon.kopie(
    naam="ford-storing-inpluggen",
    uitleg="dynamisch, auto op 38% om 19:30 erin en meteen in storing; het proefladen haalt hem eruit en daarna wacht hij op de nacht",
    auto=FORD_INPLUG, begin="2026-09-07 19:25", kabel_erin="19:30", klaar_om="07:00", duur_uren=13,
)
ford_inpluggen_zonder = ford_inpluggen.kopie(
    naam="ford-storing-inpluggen-zonder-proef",
    uitleg="hetzelfde met proefladen uit: pas de start op het goedkope uur haalt hem eruit",
    auto=replace(FORD_INPLUG, proefladen=False),
)
# Vast contract, kabel om 18:30 erin: de proef wacht tot na de avondpiek (eis 4).
vast_avond_proef = vast_avond.kopie(
    naam="vast-avond-proef", uitleg="vast contract, kabel om 18:30 erin, proefladen aan: de proef komt pas om 20:00",
    auto=replace(vast_avond.auto, proefladen=True),
)
ford_inpluggen_kabel = ford_inpluggen.kopie(
    naam="ford-storing-kabel",
    uitleg="de auto komt met een start niet uit zijn storing, alleen met de kabel: drie pogingen en een melding binnen het uur, de bewoner steekt hem om 21:00 opnieuw in",
    auto=replace(FORD_INPLUG, storing_alleen_kabel=True),
    gebeurtenissen=[("21:00", "kabel_uit", None), ("21:02", "kabel_in", None)],
)
ford_storing_wachtend = ford_inpluggen.kopie(
    naam="ford-storing-wachtend",
    uitleg="de auto meldt zijn laadstatus; de proef bij het inpluggen lukt, om 22:00 gaat hij wachtend in storing en de coach haalt hem eruit",
    auto=replace(GROTE, soc=38.0, storing_herstel_min=1, meldt_status=True, proefladen=True),
    gebeurtenissen=[("22:00", "storing_wachtend", None)],
)
een_fase_groep = dyn_zonnig.kopie(
    naam="easee-een-fase-groep", uitleg="de Easee kiest bij de start één fase, de auto trekt 0,9 A boven de limiet, de groep is 16 A en de coach ziet die",
    auto=replace(GROTE, soc=60.0, overschot_amps=0.9, storing_bij_herstart=True),
    paal=Paal(circuit_amps=16.0, kiest_een_fase=True),
)
een_fase_blind = een_fase_groep.kopie(
    naam="easee-een-fase-blind", uitleg="hetzelfde, maar zonder de sensor van de groep: de paal herstart, de auto gaat in storing, en de coach start hem opnieuw",
    paal=Paal(circuit_amps=16.0, circuit_zichtbaar=False, kiest_een_fase=True),
)
afbouw = dyn_geen_zon.kopie(
    naam="afbouw-boven-80", uitleg="dynamisch zonder panelen, de bus neemt boven 80% nog de helft; de coach leert dat",
    auto=replace(BUS, soc=30.0, afbouw_vanaf=80.0),
)
afbouw_geleerd = afbouw.kopie(
    naam="afbouw-geleerd", uitleg="dezelfde bus, en de coach weet het al van een vorige beurt",
    geleerd_tempo={8: 1.84, 9: 1.84},
)
# Dezelfde bus, maar krap: om 23:30 erin, klaar om 06:00. Zonder te weten dat
# hij bovenin afbouwt rekent de coach 4,2 uur en begint hij te laat; met de
# geleerde banden rekent hij 5,3 uur en begint hij een uur eerder.
afbouw_krap = afbouw.kopie(
    naam="afbouw-krap", uitleg="dezelfde bus om 23:30 erin, klaar om 06:00, en de coach weet nog niet dat hij afbouwt",
    begin="2026-09-07 23:25", kabel_erin="23:30", duur_uren=8,
)
afbouw_krap_geleerd = afbouw_krap.kopie(
    naam="afbouw-krap-geleerd", uitleg="hetzelfde, en de coach weet het van een vorige beurt",
    geleerd_tempo={8: 1.84, 9: 1.84},
)
# Een auto die pas vlak voor vol afremt (v0.128.0). In de eerste woning bleef de
# auto op 10-10-2026 tot 96% op vol vermogen en ging hij van 90 naar 100 in 70
# minuten; de coach had het laagste punt van die band onthouden (1,69 kW, vlak
# voor 100%) en rekende ermee voor de hele band. Op 16-10-2026 liet de
# klaar-tijdregel hem daardoor om 20:17 laden in plaats van om 01:00. `-oud`
# rekent zoals tot v0.128.0: het tempo van bovenin over de hele band.
afbouw_bovenin = dyn_geen_zon.kopie(
    naam="afbouw-bovenin", uitleg="dynamisch zonder panelen, grote auto op 45% om 22:00 erin, klaar om 06:00; vanaf 96% neemt hij nog 6 A, en de coach weet vanaf waar",
    begin="2026-09-07 21:55", kabel_erin="22:00", duur_uren=9,
    auto=replace(GROTE, soc=45.0, afbouw_vanaf=96.0, afbouw_deel=0.375),
    geleerd_tempo={9: (4.14, 96.0)},
)
afbouw_bovenin_oud = afbouw_bovenin.kopie(
    naam="afbouw-bovenin-oud", uitleg="hetzelfde, maar met het tempo van bovenin voor de hele band, zoals tot v0.128.0",
    geleerd_tempo={9: 4.14},
)

# --- wat 17-09-2026 thuis leerde ---------------------------------------------
#
# De coach stopte om 14:10 om op de zon van 15:00 te wachten en wekte om 14:14
# met tien ampère. De Easee staat in automatische fasemodus, koos naar dat
# aanbod, en begon op één fase: 5,875 A bij 1323 W, terwijl het om 14:05 op
# hetzelfde aanbod nog 4070 W was. De eigenaar: "hoe kon de laadpaal opeens op één
# fase gaan laden? Die 10 A wekstroom, doe dat gewoon 16 A maken."
#
# Wisselend weer, want daar stopt en start de coach; een driefasige auto, want
# alleen die heeft er last van; en een paal die onder de twaalf ampère voor één
# fase kiest.
fasekeuze = vast_wisselend.kopie(
    naam="easee-fasekeuze",
    uitleg="wolkenvelden, driefasige auto, en een Easee die onder 12 A voor één fase kiest",
    # Twintig seconden aanloop en een wereld die per twintig seconden tikt,
    # want de paal kiest binnen de minuut: thuis stond hij om 14:14:44 op
    # `ready_to_charge` en om 14:15:03 op `charging`, negentien seconden later.
    # Op een wereld die per minuut tikt zou de wekstroom altijd net voorbij
    # zijn als de auto begint, en dan meet deze proef niets.
    auto=replace(GROTE, soc=40.0, aanloop_s=20),
    paal=Paal(fase_drempel=12.0),
    stap_seconden=20,
)

# --- de zonbelofte die opschoof (17-09-2026 thuis) ---------------------------
#
# De voorspeller zei 1,552 kWh voor het uur van 16:00; het dak deed 0,58 en het
# huis at het op, dus de meter leverde vanaf 15:41 geen seconde terug. De coach
# beloofde om 15:42 "ik laad om 16:00", om 16:03 "ik laad om 17:00", en zou dat
# om 17:00 weer verschoven hebben. De eigenaar: "waarom ging hij niet laden om 16 uur
# terwijl hij net zei ik ga laden om 16 uur? En om 20 uur gaat hij meer laden
# maar dan is er geen zon toch?"
#
# Een driefasige auto (dan is de ondergrens van de paal 4,14 kW en draagt een
# kruimel zon dat uur nooit), een middag die minder geeft dan voorspeld, en een
# huis dat de rest opeet. Allebei de contracten, want de vraag van de eigenaar was
# juist of dit ook bij een dynamisch contract klopt.
BUS_DRIE = Auto(naam="Bus", capaciteit_kwh=19.7, soc=25.0, fasen=3, max_amps=16.0,
                wek_amps=10.0)
zon_belofte = Scenario(
    "zonbelofte-vast",
    "vast contract, kabel om 14:00 erin, driefasige bus; voorspeld helder, in werkelijkheid weinig, en het huis eet het op",
    contract="vast", auto=BUS_DRIE,
    zon=Zon(wolken="bewolkt", voorspeld="helder"),
    huis=Huis(extra=[("13:00", "20:00", 1500.0)]),
    begin="2026-09-07 13:55", kabel_erin="14:00", duur_uren=17,
)
zon_belofte_dyn = zon_belofte.kopie(
    naam="zonbelofte-dynamisch",
    uitleg="hetzelfde op een dynamisch contract: daar houdt het uur zijn eigen netschijf en telt alleen de prijs nog",
    contract="dynamisch",
)

# --- de vaatwasser (06-09-2026) ----------------------------------------------
#
# De eigenaar: "omdat de bus vol zit gaan we de laadpaal even parkeren en nu verder
# met de vaatwasser sturing." De bewoner geeft vrij, de coach kiest het
# goedkoopste startmoment binnen het schema en drukt op de knop. De auto
# staat in deze scenario's al vol, zodat het alleen over de vaatwasser gaat.
VOL = replace(BUS, soc=100.0)
vaatwasser_avond = dyn_geen_zon.kopie(
    naam="vaatwasser-avond", uitleg="dynamisch, om 19:00 vrijgegeven, klaar om 07:00: hij hoort in de goedkope nacht te draaien, niet in de avondpiek",
    auto=VOL, vaatwasser=Vaatwasser(), vaatwasser_klaar_om="07:00",
    begin="2026-09-07 18:25", kabel_erin=None, duur_uren=14,
    gebeurtenissen=[("19:00", "vaatwasser_vrijgeven", None)],
)
vaatwasser_zon = vast_zonnig.kopie(
    naam="vaatwasser-zon", uitleg="vast contract, heldere dag, om 08:00 vrijgegeven, klaar om 18:00: op eigen zon rond het middaguur",
    auto=VOL, vaatwasser=Vaatwasser(), vaatwasser_klaar_om="18:00",
    begin="2026-09-07 07:55", kabel_erin=None, duur_uren=12,
    gebeurtenissen=[("08:00", "vaatwasser_vrijgeven", None)],
)
vaatwasser_krap = vaatwasser_avond.kopie(
    naam="vaatwasser-krap", uitleg="om 03:00 vrijgegeven, klaar om 07:00: Eco duurt 3 uur 45, dus meteen starten",
    begin="2026-09-08 02:55", gebeurtenissen=[("03:00", "vaatwasser_vrijgeven", None)], duur_uren=6,
)
vaatwasser_afstand_uit = vaatwasser_avond.kopie(
    naam="vaatwasser-afstand-uit", uitleg="hetzelfde, maar starten op afstand staat uit op het apparaat: de coach drukt, er gebeurt niets, en hij zegt dat",
    vaatwasser=Vaatwasser(afstand_aan=False),
)
# Home Connect Local (thuis sinds 23-09-2026): de startknop is er alleen als
# de machine een start aanneemt, het programma zit in twee entiteiten die
# elkaar afwisselen, en de resterende tijd staat in uren. Met de spelling
# van die integratie (`eco50` in plaats van `eco_50`).
LOKAAL = Vaatwasser(lokaal=True, programma="dishcare_dishwasher_program_eco50")
vaatwasser_lokaal = vaatwasser_zon.kopie(
    naam="vaatwasser-lokaal", uitleg="Home Connect Local in plaats van de cloud: dezelfde beurt als vaatwasser-zon, met de resterende tijd in uren en het programma uit de select zolang hij stilstaat",
    vaatwasser=LOKAAL,
)
vaatwasser_lokaal_deur = vaatwasser_krap.kopie(
    naam="vaatwasser-lokaal-deur-open", uitleg="Home Connect Local, om 03:00 vrijgegeven met de deur nog open: de startknop is er niet, dus de coach drukt niet, zegt na drie minuten dat de deur open staat, en start zodra de deur om 03:08 dichtgaat",
    vaatwasser=replace(LOKAAL, deur_open=True),
    gebeurtenissen=[("03:00", "vaatwasser_vrijgeven", None), ("03:08", "vaatwasser_deur", False)],
)
# Zonder vrijgave (v0.102.0). De eigenaar op 29-09-2026: "staat dat vinkje uit dan mag
# de vaatwasser gewoon draaien met de coach als de klep dicht zit." Om 19:00 gaat de
# klep dicht na het inruimen; na de beurt blijft hij dicht tot het uitruimen om 07:30,
# en om 07:40 gaat hij na het inruimen weer dicht.
vaatwasser_klep_dicht = vaatwasser_avond.kopie(
    naam="vaatwasser-klep-dicht", uitleg="zonder vrijgave: om 19:00 gaat de klep dicht en dat is de vrijgave; hij draait in de goedkope nacht, start niet opnieuw met de schone vaat erin, en is na uitruimen en inruimen om 07:40 weer vrij",
    vaatwasser=Vaatwasser(vrijgave=False, deur_open=True),
    duur_uren=14,
    gebeurtenissen=[("19:00", "vaatwasser_deur", False), ("07:30", "vaatwasser_deur", True),
                    ("07:40", "vaatwasser_deur", False)],
)
# Een Miele-wasmachine (v0.124.0). De eigenaar op 15-10-2026: "Starten, zoals
# vaatwasser", en voor een programma dat de coach nog niet gemeten heeft "de
# duur van de machine": Miele geeft die zolang het programma klaarstaat, en een
# vermogen heeft hij niet, alleen een teller per programma.
wasmachine_miele = vaatwasser_avond.kopie(
    naam="wasmachine-miele", uitleg="Miele-wasmachine, om 19:00 vrijgegeven, klaar om 07:00, programma nog niet gemeten: hij plant op de duur van de machine, zonder kWh en zonder bedrag, in de goedkope nacht, en meet de beurt uit de teller",
    vaatwasser=Vaatwasser(miele=True, programma="cottons"),
)
wasmachine_miele_gemeten = wasmachine_miele.kopie(
    naam="wasmachine-miele-gemeten", uitleg="dezelfde wasmachine, nu met een eerdere meting van het programma: dan rekent hij met de kWh en noemt hij een bedrag",
    vaatwasser_gemeten=[{"device": "vaatwasser", "key": "cottons", "label": "Katoen", "minutes": 225, "kwh": 0.8,
                         "peak_w": 0, "profile": [], "runs": 1}],
)
# Een onderbreking midden in de beurt (v0.127.0). In de klantwoning op 16-10-2026:
# 08:59:26 in_use, 08:59:42 program_interrupted, 09:00:16 weer in_use. De coach las
# dat als klaar: een valse melding, een beurt van 16 seconden, en de vrijgave eraf.
wasmachine_miele_onderbroken = wasmachine_miele.kopie(
    naam="wasmachine-miele-onderbroken", uitleg="dezelfde wasmachine, om 02:00 een minuut onderbroken: dat is een pauze, de beurt loopt door, één verslag en een meting over de hele beurt",
    gebeurtenissen=list(wasmachine_miele.gebeurtenissen) + [("02:00", "vaatwasser_onderbreek", 1)],
)
vaatwasser_lokaal_afstand_uit = vaatwasser_avond.kopie(
    naam="vaatwasser-lokaal-afstand-uit", uitleg="Home Connect Local met starten op afstand uit: de sensor zegt het, dus de coach drukt niet één keer en zegt wat er aan moet",
    vaatwasser=replace(LOKAAL, afstand_aan=False),
)
# Een domme vaatwasser op een meetstekker (06-09-2026 's avonds). De eigenaar: "smart
# plug als starten doen we niet, wel adviseren en meten, met zet hem aan." En
# zijn eigen schema: niet in de nacht, vanaf 08:00, uiterlijk klaar om 16:30.
DOM = Vaatwasser(slim=False)
vaatwasser_dom_zon = vast_zonnig.kopie(
    naam="vaatwasser-dom-zon", uitleg="domme vaatwasser op een meetstekker, vast contract, zonnig, 's avonds vrijgegeven met vanaf 08:00 en klaar om 16:30: de coach vraagt om hem in de zon aan te zetten, de bewoner doet dat, en de coach meet de beurt",
    auto=VOL, vaatwasser=DOM, vaatwasser_klaar_om="16:30", vaatwasser_niet_eerder="08:00",
    begin="2026-09-07 19:25", kabel_erin=None, duur_uren=22,
    gebeurtenissen=[("20:00", "vaatwasser_vrijgeven", None)],
)
vaatwasser_dom_leert = vaatwasser_dom_zon.kopie(
    naam="vaatwasser-dom-leert", uitleg="dezelfde domme vaatwasser twee dagen achter elkaar: de tweede beurt plant hij met wat hij de eerste dag mat",
    duur_uren=46, gebeurtenissen=[("20:00", "vaatwasser_vrijgeven", None), ("+1 20:00", "vaatwasser_vrijgeven", None)],
)
vaatwasser_dom_negeert = vaatwasser_dom_zon.kopie(
    naam="vaatwasser-dom-negeert", uitleg="de bewoner zet hem niet aan als de coach het vraagt: één herinnering na drie kwartier, en geen verslag",
    vaatwasser=Vaatwasser(slim=False, bewoner_reageert_min=None),
)
vaatwasser_dom_zelf = vaatwasser_dom_zon.kopie(
    naam="vaatwasser-dom-zelf", uitleg="de bewoner zet hem om 06:30 zelf aan, voor het schema en zonder vrijgave: de coach meet de beurt en meldt hem, maar vraagt niets",
    gebeurtenissen=[("06:30", "vaatwasser_aan", None)],
)
vaatwasser_eigen_tabel = vaatwasser_avond.kopie(
    naam="vaatwasser-eigen-tabel", uitleg="de klant heeft Eco op 150 minuten en 0,6 kWh gezet: om 03:30 vrijgegeven met klaar om 07:00 past het nog, dus geen paniekstart",
    begin="2026-09-08 03:25", gebeurtenissen=[("03:30", "vaatwasser_vrijgeven", None)], duur_uren=6,
    vaatwasser=Vaatwasser(minuten=150, kwh=0.6),
    vaatwasser_tabel=[{"key": "eco_50", "label": "Eco 50 °C", "minutes": 150, "kwh": 0.6, "peak_w": 2000}],
)
vaatwasser_gemeten = vaatwasser_zon.kopie(
    naam="vaatwasser-gemeten", uitleg="Home Connect met een eerdere meting van Eco: de coach plant met het gemeten profiel en zet de opwarmpiek in de zon",
    vaatwasser=Vaatwasser(minuten=200, kwh=0.95, piek_w=2000.0, piek_minuten=40),
    vaatwasser_gemeten=[{"device": "vaatwasser", "key": "eco_50", "minutes": 200, "kwh": 0.95, "peak_w": 2000,
                         "profile": [2000.0] * 4 + [60.0] * 32 + [2000.0] * 4, "runs": 1, "at": ""}],
)
# De eigenaar op 07-09-2026 om 10:22 thuis: de coach wachtte op 11:00 terwijl zijn
# meter 3,5 kW teruglevering zag. "Je weet niet hoeveel je om 11 uur terug gaat
# leveren." De voorspeller zei bewolkt, het dak deed helder: in het lopende
# uur hoort de meter te winnen.
vaatwasser_meter_wint = vast_zonnig.kopie(
    naam="vaatwasser-meter-wint", uitleg="vast contract met salderen, de voorspeller zei bewolkt maar het is helder: om 10:20 vrijgegeven met 3 kW op de meter hoort Express 60 meteen te starten, niet op de verwachting van 12:00 te wachten",
    auto=VOL, contract="vast-salderen", vast_terugleverkosten=0.05, zon=Zon(wolken="helder", voorspeld="bewolkt"),
    vaatwasser=Vaatwasser(programma="dishcare_dishwasher_program_kurz_60", minuten=60, kwh=1.05, piek_w=2200.0, piek_minuten=20),
    vaatwasser_klaar_om="16:30", vaatwasser_niet_eerder="08:00",
    gebeurtenissen=[("10:20", "vaatwasser_vrijgeven", None)],
)
# In een echte woning op 08-09-2026. Om 09:12 vrijgegeven, Eco 50 zonder meting, het
# dak gaf 0,9 kWh in dat uur en de meter zag 250 W over; de voorspeller zei
# voor de middag ongeveer de helft van wat het dak deed. De coach startte
# meteen, want uitgesmeerd was Eco 213 W en dat paste; de opwarmpiek van
# 2,2 kW kwam van het net. De eigenaar: "waarom startte hij terwijl bekend is dat de
# zon later meer schijnt?" De zon is de gemeten opbrengst per uur van die dag
# (tot 15:00 gemeten; daarna de vorm van de voorspeller, 2,6 keer, zoals om
# 14:00), het huis de mediaan per uur uit zijn kwartieropslag.
SVEN_ZON_KWH = {
    7: 0.1, 8: 0.5, 9: 0.92, 10: 1.93, 11: 2.25, 12: 3.78, 13: 3.83, 14: 4.41,
    15: 3.4, 16: 3.7, 17: 3.1, 18: 2.2, 19: 1.3, 20: 0.5,
}
SVEN_HUIS_W = {
    0: 685, 1: 598, 2: 581, 3: 566, 4: 572, 5: 573, 6: 572, 7: 564, 8: 533, 9: 753,
    10: 855, 11: 813, 12: 841, 13: 851, 14: 1068, 15: 962, 16: 1014, 17: 1081,
    18: 2019, 19: 1113, 20: 1127, 21: 1087, 22: 951, 23: 796,
}
vaatwasser_vroeg = vast_zonnig.kopie(
    naam="vaatwasser-vroeg", uitleg="de eigenaar op 08-09-2026: vast contract met salderen, om 09:12 vrijgegeven met 250 W over en een voorspeller die de helft zag; Eco zonder meting hoort niet te starten voor de zon de opwarmpiek draagt",
    auto=VOL, contract="vast-salderen", vast_terugleverkosten=0.052756,
    begin="2026-09-08 07:55", kabel_erin=None, duur_uren=10,
    zon=Zon(kromme=SVEN_ZON_KWH, voorspeld="half"), huis=Huis(profiel=SVEN_HUIS_W, verdeling=(0.4, 0.3, 0.3)),
    vaatwasser=Vaatwasser(minuten=225, kwh=0.8, piek_w=2200.0, piek_minuten=20),
    vaatwasser_klaar_om="16:30", vaatwasser_niet_eerder="08:00",
    gebeurtenissen=[("09:12", "vaatwasser_vrijgeven", None)],
)
# Dezelfde dag met een voorspeller die het wél goed zag: dan wacht hij op het
# uur waarvan de zon de piek draagt. Het verschil tussen de twee is wat een
# verwachting die de helft zegt kost, en dat is geen fout van de coach.
vaatwasser_vroeg_verwacht = vaatwasser_vroeg.kopie(
    naam="vaatwasser-vroeg-verwacht", uitleg="dezelfde dag, maar de voorspeller zag het dak goed: dan wacht hij tot de zon de opwarmpiek draagt, rond 12:00",
    zon=Zon(kromme=SVEN_ZON_KWH),
)
# Een herstart van Home Assistant midden in de beurt (07-09-2026, de eigenaar: "ja,
# reken terug"). De coach bewaart de lopende beurt elke vijf minuten en pakt
# hem na de herstart daar op: geen tweede "is gestart", en één verslag over
# de hele beurt.
vaatwasser_herstart = vaatwasser_avond.kopie(
    naam="vaatwasser-herstart", uitleg="dynamisch, om 19:00 vrijgegeven, en om 03:00 herstart Home Assistant midden in de beurt: de telling gaat door en het verslag gaat over de hele beurt",
    gebeurtenissen=[("19:00", "vaatwasser_vrijgeven", None), ("+1 03:00", "herstart", None)],
)
vaatwasser_uiterlijk = vaatwasser_avond.kopie(
    naam="vaatwasser-uiterlijk-starten", uitleg="om 19:00 vrijgegeven met uiterlijk starten om 22:00: dan gaat hij om 22:00, ook al is de nacht goedkoper",
    vaatwasser_uiterlijk="22:00",
)
# In een echte woning op 11-09-2026. Om 09:29 vrijgegeven, Express 60 met een meting
# (piek 2264 W). Om 09:35 klaarde het een paar minuten op: het dak ging van
# 1,1 naar 3,0 kW en de meter zag 2694 W teruglevering, meer dan de piek. De
# coach startte, en om 09:37 was het 721 W; de drie opwarmpieken kregen 1,1
# tot 1,8 kW zon, 0,2 van de 1,0 kWh. Om 12:00 gaf het dak 3,4 kW. De zon is
# die van 08-09 (in de ochtend binnen een paar honderd watt van 11-09), de
# opklaring die van 11-09, en de meting is de rij zoals hij na die beurt in
# zijn instellingen stond.
KURZ_60_GEMETEN = {
    "device": "vaatwasser", "key": "kurz_60", "minutes": 98, "kwh": 0.911, "peak_w": 2264,
    "profile": [463.1, 2203.6, 1471.1, 61.4, 1313.1, 932.3, 64.3, 14.0, 11.9, 44.3, 1034.2, 2134.7,
                1157.1, 21.5, 2.5, 0.5, 0.0, 0.8, 0.0, 0.0, 0.0, 0.0, 0.0],
    "runs": 3, "at": "",
}
vaatwasser_zonpiek = vaatwasser_vroeg_verwacht.kopie(
    naam="vaatwasser-zonpiek", uitleg="de eigenaar op 11-09-2026: om 09:29 vrijgegeven, om 09:31 klaart het zes minuten op tot 3,2 kW; op zo'n opklaring hoort Express 60 niet te starten, want de opwarmpieken komen dan van het net",
    begin="2026-09-11 07:55", vast_prijs=0.24171,
    zon=Zon(kromme=SVEN_ZON_KWH, pieken=[("09:31", "09:37", 3.2)]),
    vaatwasser=Vaatwasser(programma="dishcare_dishwasher_program_kurz_60", minuten=98, kwh=0.91,
                          piek_w=2200.0, piek_minuten=22),
    vaatwasser_gemeten=[KURZ_60_GEMETEN],
    gebeurtenissen=[("09:29", "vaatwasser_vrijgeven", None)],
)
# Dezelfde dag, en toen zei de melding "klaar rond 10:56": dat was de eindtijd
# die Home Connect om 09:01 bij het kiezen had gezet. Hier om 09:45 gekozen en
# om 10:20 gestart op de meter; de melding hoort de echte eindtijd te noemen.
vaatwasser_eindtijd = vaatwasser_meter_wint.kopie(
    naam="vaatwasser-eindtijd", uitleg="Home Connect met een eindtijd die al om 09:45 bij het kiezen gezet werd en pas een minuut na de start klopt: de melding 'is gestart' hoort de echte eindtijd te noemen",
    vaatwasser=Vaatwasser(programma="dishcare_dishwasher_program_kurz_60", minuten=60, kwh=1.05, piek_w=2200.0,
                          piek_minuten=20, eindtijd_tijdstip=True, gekozen="09:45"),
)

# En op 15-09-2026 zei de melding "klaar rond 11:33", terwijl hij om 11:45
# klaar was. Dat was geen eindtijd van het kiezen: Home Connect zette hem bij
# Run (10:11:56, Run 10:11:57) en rekende hem om 10:13:02 opnieuw uit op
# 11:41. De melding ging om 10:12:53, negen seconden voor de correctie. Een
# eindtijd telt daarom pas als hij twee ronden stilstaat.
vaatwasser_eindtijd_bijstellen = vaatwasser_eindtijd.kopie(
    naam="vaatwasser-eindtijd-bijstellen", uitleg="Home Connect zet bij de start meteen een eindtijd die er twaalf minuten naast zit en stelt hem een minuut later bij (oud: 10:21 'klaar rond 11:09'; nieuw: 10:23 'klaar rond 11:21', en dat werd het)",
    vaatwasser=Vaatwasser(programma="dishcare_dishwasher_program_kurz_60", minuten=60, kwh=1.05, piek_w=2200.0,
                          piek_minuten=20, eindtijd_tijdstip=True, gekozen="09:45", eindtijd_eerst_min=48),
)

# De eigenaar op 12-09-2026 om 16:33: vrijgegeven bij vanaf 08:00 en klaar om 16:30.
# De coach plande de volgende middag en zei "hij start om 13:00"; de eigenaar zette
# hem zelf aan. Op 13-09: "de keuze ingeruimd en morgen starten of ingeruimd
# en nu starten."
vaatwasser_na_klaartijd = vaatwasser_zon.kopie(
    naam="vaatwasser-na-klaartijd", uitleg="vast contract, zonnig, om 16:33 vrijgegeven bij vanaf 08:00 en klaar om 16:30: ingeruimd en morgen starten, dus de volgende middag op zon (dat deed hij al, alleen zei hij niet dat het morgen werd)",
    vaatwasser_klaar_om="16:30", vaatwasser_niet_eerder="08:00",
    begin="2026-09-07 16:25", duur_uren=24,
    gebeurtenissen=[("16:33", "vaatwasser_vrijgeven", None)],
)
vaatwasser_na_klaartijd_nu = vaatwasser_na_klaartijd.kopie(
    naam="vaatwasser-na-klaartijd-nu", uitleg="hetzelfde, maar ingeruimd en nu starten: hij start om 16:33 en is dezelfde avond klaar (oud: die keuze was er niet)",
    gebeurtenissen=[("16:33", "vaatwasser_nu_starten", None)],
)

# --- de boiler ---------------------------------------------------------------
#
# De eigenaar op 19-09-2026: "een boiler waar je alleen stroom op moet zetten, met een
# smart plug. Als je er stroom op zet en de boiler is warm moet de coach
# detecteren dat hij warm genoeg is omdat hij dan onder een bepaald vermogen
# zit. Zelflerend." Klaar om 07:00, en overschot mag hij pakken.
#
# De eerste nacht weet de coach niets: hij zet hem aan, ziet 2 kW, ziet het
# wegvallen, en heeft dan zijn eerste twee getallen. De tweede nacht plant hij
# met wat hij toen mat.
boiler_leert = dyn_geen_zon.kopie(
    naam="boiler-leert",
    uitleg="dynamisch, geen zon: een boiler van 2 kW die de coach nog nooit gezien heeft, klaar om 07:00",
    auto=VOL, kabel_erin=None,
    boiler=Boiler(), boiler_klaar_om="07:00",
    begin="2026-09-07 18:00", duur_uren=14,
)
# En dezelfde nacht met wat hij de vorige nacht leerde: 2 kW, een vat van 6 kWh
# en 0,25 kWh per uur eruit. Dan hoeft hij niet meer te leren en kan hij kiezen,
# en dan hoort hij in de goedkope nacht te zitten en niet in de avondpiek.
boiler_nacht = boiler_leert.kopie(
    naam="boiler-nacht",
    uitleg="dezelfde boiler, maar de coach weet al wat hij trekt: hij hoort de goedkoopste nachturen te pakken en om 07:00 warm te zijn",
    boiler=Boiler(inhoud_kwh=3.0),
    boiler_geleerd={"heat_w": 2000.0, "vol_kwh": 6.0, "verbruik_kwh_h": 0.25,
                    "kwh_sinds_vol": 0.0, "vol_sinds": "2026-09-07T06:00:00",
                    "getrokken_op": "2026-09-07T06:00:00", "runs": 3},
)
# Een zonnige dag: het vat is de goedkoopste plek om overschot in te stoppen.
boiler_zon = vast_zonnig.kopie(
    naam="boiler-zon",
    uitleg="vast contract, heldere dag: de boiler hoort op eigen zon te verwarmen en niet van het net",
    auto=VOL, kabel_erin=None,
    boiler=Boiler(inhoud_kwh=3.0), boiler_klaar_om="18:00",
    boiler_geleerd={"heat_w": 2000.0, "vol_kwh": 6.0, "verbruik_kwh_h": 0.25,
                    "kwh_sinds_vol": 0.0, "vol_sinds": "2026-09-07T06:00:00",
                    "getrokken_op": "2026-09-07T06:00:00", "runs": 3},
    begin="2026-09-07 07:55", duur_uren=12,
)
# En een stekker die het niet doet: er staat stroom op volgens Home Assistant,
# maar er loopt niets. Dat hoort niemand pas onder de douche te merken.
boiler_stekker_stuk = boiler_nacht.kopie(
    naam="boiler-stekker-stuk",
    uitleg="dezelfde nacht, maar de smart plug schakelt niet werkelijk: na een etmaal zonder één watt hoort de coach te zeggen dat er geen stroom loopt",
    boiler=Boiler(inhoud_kwh=3.0, stekker_werkt=False),
    # Gisterochtend trok hij voor het laatst; een vat van 6 kWh dat 0,25 kWh
    # per uur verliest is daarna in een dag leeg.
    boiler_geleerd={"heat_w": 2000.0, "vol_kwh": 6.0, "verbruik_kwh_h": 0.25,
                    "kwh_sinds_vol": 0.0, "vol_sinds": "2026-09-07T06:00:00",
                    "getrokken_op": "2026-09-07T06:00:00", "runs": 3},
)

# --- de airco (v0.119.0) ------------------------------------------------------
#
# De eigenaar op 14-10-2026: "hij moet de airco aan zetten als er overschot is en als
# de temperatuur nog niet bereikt is. Hij mag trouwens wel de temperatuur instellen
# en de modus wijzigen van verwarmen en koelen." Na v0.119.0: "de airco moet alleen
# bijverwarmen of koelen bij overschot he! niet gewoon aan om de temperatuur te
# regelen", en "goedkoop uur mag de bewoner zelf kiezen dus 3 opties of op zon of
# goedkope uren of beide." Goedkoop is elk uur onder het gemiddelde van die dag, en
# zet de bewoner hem zelf aan of uit, dan blijft de coach er de rest van de dag vanaf.
airco_zon = vast_zonnig.kopie(
    naam="airco-zon",
    uitleg="vast contract, heldere warme dag, kamer 26,5 graden, de bewoner wil 23: koelen op eigen zon, niet van het net",
    auto=VOL, kabel_erin=None,
    airco=Airco(), airco_doel=23.0,
    begin="2026-09-07 07:55", duur_uren=14,
)
airco_plaatje = airco_zon.kopie(
    naam="airco-plaatje",
    uitleg="dezelfde dag, maar zonder vermogenssensor: de coach rekent alleen met het typeplaatje (1200 W)",
    airco_plaatje=True,
)
airco_bewoner = airco_zon.kopie(
    naam="airco-bewoner",
    uitleg="dezelfde dag, maar om 13:30 zet de bewoner hem zelf uit: de coach blijft er de rest van de dag vanaf",
    gebeurtenissen=[("13:30", "airco_bewoner", "off")],
)
airco_goedkoop = dyn_geen_zon.kopie(
    naam="airco-goedkoop",
    uitleg="dynamisch, geen panelen, koude kamer (17 graden), de bewoner wil 20 en koos goedkope uren: verwarmen op de uren onder het daggemiddelde",
    auto=VOL, kabel_erin=None,
    airco=Airco(kamer_c=17.0, buiten={0: 6.0, 6: 4.0, 12: 9.0, 16: 10.0, 20: 7.0}), airco_doel=20.0,
    airco_aan_op="goedkoop",
    begin="2026-09-07 00:05", duur_uren=23,
)
# En dezelfde dag zoals hij standaard staat, op zon: geen zon, dus nooit aan, hoe
# koud het ook is. Hij is geen thermostaat.
airco_geen_zon = airco_goedkoop.kopie(
    naam="airco-geen-zon",
    uitleg="dezelfde koude dag zonder panelen, maar standaard op zon: de coach zet hem niet aan",
    airco_aan_op="zon",
)

# --- de thuisbatterij --------------------------------------------------------
#
# De eigenaar op 21-09-2026: "Ik wil de coach gaan uitbreiden met een
# thuisbatterij." De batterij is die van de eerste woning (14,6 kWh, 3,5 kW
# erin, 2,5 kW eruit, 5 tot 95%, 73,6% rendement uit de kWh-meter, een opdracht
# is na vijf seconden te zien). Er hangt geen auto aan de paal, tenzij het
# scenario daarover gaat: `kabel_erin` ligt dan voorbij het einde.
#
# De wereld tikt hier elke vijftien seconden, en in de scenario's die over de
# regelaar gaan elke vijf, want zo vaak kreeg Home Assistant daar de meter.

ZONDER_AUTO = dict(kabel_erin="+9 07:00", schema_aan=False, stap_seconden=15)

batterij_vast_zon = Scenario(
    "batterij-vast-zon",
    "vast contract, heldere dag, batterij op 20%: overschot erin, de avond en de nacht eruit",
    contract="vast", zon=Zon(wolken="helder"), batterij=Batterij(soc=20.0), **ZONDER_AUTO,
)
# De eerste woning op 03-10-2026: de marktsensor is daar de all-in sensor, dus wat
# teruglevering oplevert is onbekend. Met handelen aan en zelf nul stond de batterij
# tot v0.106.2 de hele ochtend op "handelen, terugleveren brengt nu € 0,000 op": 4,57
# kWh zon naar het net, de batterij bleef op 21% en gaf er 0,48 kWh bij.
batterij_zonder_terug = batterij_vast_zon.kopie(
    naam="batterij-zonder-terugleverprijs",
    uitleg="dynamisch, de marktsensor is de all-in sensor, handelen aan, zelf nul, heldere dag, batterij op 21%: de ochtendzon gaat erin",
    contract="dynamisch", markt_is_all_in=True,
    batterij=Batterij(soc=21.0, eigen_nul=True, zelf_nul=True, handelen=True),
)
batterij_vast_salderen = batterij_vast_zon.kopie(
    naam="batterij-vast-salderen",
    uitleg="vast contract met salderen: opslaan kost alleen het verlies, dus wat erin zit gaat eruit en er komt niets bij",
    contract="vast-salderen",
)
batterij_winter = Scenario(
    "batterij-dynamisch-winter",
    "dynamisch, bewolkt: te weinig zon, dus bijladen op de goedkoopste uren voor de dure avond",
    contract="dynamisch", zon=Zon(wolken="bewolkt"), batterij=Batterij(soc=8.0),
    begin="2026-09-07 13:05", duur_uren=34, **ZONDER_AUTO,
)
batterij_zomer = batterij_winter.kopie(
    naam="batterij-dynamisch-zon",
    uitleg="dynamisch, heldere dag: de zon vult hem, van het net laden hoeft niet",
    zon=Zon(wolken="helder"), begin="2026-09-07 06:55", duur_uren=24,
)
batterij_handelen = batterij_winter.kopie(
    naam="batterij-handelen",
    uitleg="dynamisch met handelen aan en een avond van tachtig cent: dan levert hij ook aan het net",
    batterij=Batterij(soc=85.0, handelen=True),
    # Met de gewone prijzen gebeurt hier niets, en dat hoort zo: 0,21 terug
    # tegen 0,16 gedeeld door 73,6% om het weer bij te laden is geen winst. De
    # bewoner van de eerste woning zei het al: "de spread is dan te klein."
    prijzen=Prijzen(per_dag={
        "2026-09-07": [0.23] * 12 + [0.16] * 4 + [0.25] * 3 + [0.80] * 2 + [0.30] * 3,
        "2026-09-08": [0.22] * 12 + [0.15] * 4 + [0.25] * 8,
    }),
    begin="2026-09-07 17:55", duur_uren=8,
)
# Handelen alleen als de beurt na alle kosten iets oplevert (v0.162.0). Een avond van veertig
# cent levert terug € 0,20 op; wat er dan uit gaat koopt het huis 's nachts en 's ochtends terug
# voor € 0,22 tot € 0,25. Onder de streep een paar cent, en de eigenaar: "onder aan de streep
# moet het geld opleveren en niet gaan pendelen."
batterij_handelen_krap = batterij_handelen.kopie(
    naam="batterij-handelen-krap",
    uitleg="handelen aan, een avond van veertig cent: onder de streep minder dan de ondergrens, dus hij levert niet aan het net",
    prijzen=Prijzen(per_dag={
        "2026-09-07": [0.23] * 12 + [0.16] * 4 + [0.25] * 3 + [0.40] * 2 + [0.30] * 3,
        "2026-09-08": [0.22] * 12 + [0.15] * 4 + [0.25] * 8,
    }),
)
batterij_handelen_krap_zonder = batterij_handelen_krap.kopie(
    naam="batterij-handelen-krap-zonder-grens",
    uitleg="dezelfde avond met de ondergrens op nul: dan levert hij voor die paar cent wel",
    batterij=Batterij(soc=85.0, handelen=True, min_winst=0.0),
)
batterij_reserve = batterij_vast_zon.kopie(
    naam="batterij-reserve",
    uitleg="vast contract, reserve van 40% voor noodstroom: daaronder komt er niets uit",
    batterij=Batterij(soc=55.0, reserve=40.0), begin="2026-09-07 17:55", duur_uren=14,
)
batterij_negatief = Scenario(
    "batterij-negatieve-prijs",
    "dynamisch, midden op de dag een negatieve all-in prijs: vol vermogen laden, niets eruit",
    contract="dynamisch", zon=Zon(wolken="bewolkt"), batterij=Batterij(soc=30.0),
    prijzen=Prijzen(per_dag={"2026-09-07": [0.24] * 12 + [-0.02, -0.04, -0.01] + [0.26] * 9}),
    begin="2026-09-07 10:55", duur_uren=6, **ZONDER_AUTO,
)
batterij_volle_beurt = Scenario(
    "batterij-volle-beurt",
    "dynamisch, bewolkte maandag met de wekelijkse volle beurt: voor middernacht een keer aan de laadgrens",
    contract="dynamisch", zon=Zon(wolken="bewolkt"),
    batterij=Batterij(soc=35.0, wekelijks_vol_dag=0),
    begin="2026-09-07 00:05", duur_uren=24, **ZONDER_AUTO,
)
batterij_paal = Scenario(
    "batterij-paal-laadt",
    "vast contract, de bus laadt na 20:00 van het net: de batterij geeft dan niets af",
    contract="vast", zon=Zon(wolken="bewolkt"), auto=BUS, batterij=Batterij(soc=80.0),
    begin="2026-09-07 17:55", kabel_erin="18:00", duur_uren=13, stap_seconden=15,
)
# De batterij helpt de auto met wat er boven de nacht over is (v0.90.0). De bewoner
# van de eerste woning op 23-09-2026, naar evcc; de eigenaar: de nacht gaat voor.
batterij_helpt_auto = Scenario(
    "batterij-helpt-auto",
    "vast contract, de bus laadt na 20:00, de accu op 95% mag helpen boven 40%: alleen wat de nacht niet nodig heeft",
    contract="vast", zon=Zon(wolken="bewolkt"), auto=BUS, batterij=Batterij(soc=95.0, auto_boven=40.0),
    begin="2026-09-07 17:55", kabel_erin="18:00", duur_uren=13, stap_seconden=15,
)
batterij_helpt_auto_nacht = batterij_helpt_auto.kopie(
    naam="batterij-helpt-auto-nacht",
    uitleg="grens 10%, nachtstrategie aan: de accu houdt over wat de nacht nodig heeft",
    batterij=Batterij(soc=95.0, auto_boven=10.0),
)
batterij_helpt_auto_zonder_nacht = batterij_helpt_auto_nacht.kopie(
    naam="batterij-helpt-auto-zonder-nacht",
    uitleg="grens 10%, nachtstrategie uit: de accu mag tot 10% in de auto",
    nachtstrategie=False,
)
# De voorrang bij zonoverschot (v0.92.0). De bewoner van de eerste woning op
# 23-09-2026: "eerst moet de accu 40% vol zijn, daarna mag het zonoverschot naar de
# auto. Niet automatisch de auto voorrang geven op alles dus."
voorrang_auto_eerst = Scenario(
    "voorrang-auto-eerst",
    "vast contract, heldere dag, bus op 30% om 07:00, accu op 20%: de standaard, de auto krijgt de zon eerst",
    contract="vast", zon=Zon(wolken="helder"), auto=BUS, batterij=Batterij(soc=20.0),
    begin="2026-09-07 06:55", duur_uren=14, stap_seconden=15,
)
voorrang_accu_eerst = voorrang_auto_eerst.kopie(
    naam="voorrang-accu-eerst",
    uitleg="hetzelfde met eerst de accu tot 50%, dan de auto, dan de accu tot vol",
    zon_voorrang=[{"device": "batterij", "limit": 50}, {"device": "paal"}, {"device": "batterij"}],
)
# De voorrang bij planningen (v0.93.0). De bewoner van de eerste woning op
# 23-09-2026: "eerst de auto volgens laadplanning, dan de accu volgens laadplanning;
# laadt de accu maar met 3500 W en heb ik nog ruimte op mijn aansluiting?" Een
# grote auto die de hele nacht nodig heeft en een lege accu die de goedkope nacht
# wil, op 3x25 A: op fase 3 passen 16 A auto en 15 A accu niet samen.
planning_auto_eerst = Scenario(
    "planning-auto-eerst",
    "dynamisch, 's nachts: een grote auto op 50% en een accu op 10% willen dezelfde goedkope uren, samen passen ze niet: de auto gaat voor",
    contract="dynamisch", zon=Zon(wolken="geen"), auto=replace(GROTE, soc=50.0), batterij=Batterij(soc=10.0),
    begin="2026-09-07 20:55", kabel_erin="21:00", klaar_om="07:00", duur_uren=14, stap_seconden=15,
    # Een nacht met genoeg verschil: dan wil de lege accu de goedkope uren in
    # voor de dure ochtend, en de auto heeft ze ook nodig.
    prijzen=Prijzen(per_dag={
        "2026-09-07": [0.30] * 17 + [0.40] * 7,
        "2026-09-08": [0.15] * 2 + [0.30] * 5 + [0.45] * 4 + [0.30] * 13,
    }),
)
planning_accu_eerst = planning_auto_eerst.kopie(
    naam="planning-accu-eerst",
    uitleg="hetzelfde met de accu bovenaan: de auto krijgt wat de accu overlaat",
    plan_voorrang=["batterij", "paal"],
)
batterij_sprong = Scenario(
    "batterij-sprong",
    "de regelaar: om 19:00 gaat er drie kilowatt aan, om 19:20 weer uit",
    contract="vast", zon=Zon(wolken="geen"), voorspeller="geen", batterij=Batterij(soc=70.0),
    begin="2026-09-07 18:40", duur_uren=1, gebeurtenissen=[("19:00", "oven", 20)],
    kabel_erin="+9 07:00", schema_aan=False, stap_seconden=5,
)
batterij_meter_weg = batterij_sprong.kopie(
    naam="batterij-meter-weg",
    uitleg="de meter valt om 19:00 vier minuten weg terwijl de batterij het huis voedt: hij gaat naar nul",
    gebeurtenissen=[("19:00", "p1_weg", 4)],
)
batterij_herstart = batterij_sprong.kopie(
    naam="batterij-herstart",
    uitleg="Home Assistant herstart om 19:05 midden in het ontladen: de coach pakt de batterij weer op",
    gebeurtenissen=[("19:00", "oven", 20), ("19:05", "herstart", None)],
)
# De sensor van de Anker, zoals hij op 22-09-2026 in de eerste woning gemeten
# is naast een kWh-meter: acht seconden achter, een aanloop die er niet is, en
# twee seconden lang de opdracht zelf. Zie `Batterij` in virtueel.py.
ANKER_SENSOR = dict(sensor_na_s=8.0, sensor_aanloop=True, sensor_echo_s=2.0)

batterij_anker_sensor = batterij_sprong.kopie(
    naam="batterij-anker-sensor",
    uitleg="dezelfde sprong, maar de vermogenssensor van de batterij loopt acht seconden achter en toont onderweg een aanloop en de opdracht zelf, zoals de Anker in de eerste woning",
    batterij=Batterij(soc=70.0, **ANKER_SENSOR),
)
batterij_uurlast = Scenario(
    "batterij-uurlast",
    "vast contract, zonnige ochtend, en elk uur veertig seconden 2,5 kW erbij (een boiler): de batterij schiet daar niet op door en er komt niets van het net in",
    contract="vast", zon=Zon(wolken="helder"), huis=Huis(puls=(2500.0, 40.0, 54.0)),
    batterij=Batterij(soc=60.0, **ANKER_SENSOR),
    begin="2026-09-07 09:55", duur_uren=24, kabel_erin="+9 07:00", schema_aan=False, stap_seconden=5,
)
# De nacht van 22-09-2026 in de eerste woning, met de coach aan het stuur: een
# last die vijf seconden aan en vijftien seconden uit staat, een batterij die
# een opdracht pas na tien seconden uitvoert, en een sensor die dat vrijwel
# meteen meldt. De meter van 5 s na de opdracht toont dan nog de oude stand.
batterij_klapperlast = Scenario(
    "batterij-klapperlast",
    "nacht, vast contract, en elke twintig seconden vijf seconden 2 kW: de batterij volgt pas na tien seconden, en de regelaar hoort daar niet op door te schieten",
    contract="vast", zon=Zon(wolken="geen"), voorspeller="geen",
    huis=Huis(puls=(2000.0, 5.0, 1 / 3)),
    batterij=Batterij(soc=30.0, volgt_na_s=10.5, sensor_na_s=1.0, meter_tik_s=5.0, meter_fase_s=3.0),
    begin="2026-09-07 22:55", duur_uren=1, kabel_erin="+9 07:00", schema_aan=False, stap_seconden=1,
)
# De nacht van 23 op 24-09-2026 in de eerste woning: een last van 490 W die om
# de dertig seconden tien seconden aanstaat (een broodbakmachine, denkt de
# bewoner), een batterij die een opdracht na drie tot acht seconden uitvoert, de
# sensor van de Anker, en een P1 die om :01 en :06 meldt. De regelaar van
# v0.96.0 stond daar in tegenfase, tot 210 opdrachten per uur.
batterij_wisselende_last = Scenario(
    "batterij-wisselende-last",
    "nacht, vast contract, en om de dertig seconden tien seconden 490 W: de batterij dekt de basis en laat de last gaan",
    contract="vast", zon=Zon(wolken="geen"), voorspeller="geen",
    huis=Huis(puls=(490.0, 10.0, 0.5)),
    batterij=Batterij(soc=60.0, volgt_na_s=5.0, meter_tik_s=5.0, meter_fase_s=1.0, **ANKER_SENSOR),
    begin="2026-09-07 04:55", duur_uren=1, kabel_erin="+9 07:00", schema_aan=False, stap_seconden=1,
)
# De nacht van 24 op 25-09-2026 in de eerste woning: een grote auto met een
# opgegeven accustand aan een paal op een groep van 3x16 A, klaar om 08:00, en twee
# herstarts van Home Assistant. Tot v0.98.0 vergat de coach bij elke herstart het
# gemeten plafond (12 A) en rekende hij met 16 A: om 22:59 "wacht tot 01:00", om
# 23:20 weer "nu doorladen", en na elke herstart tien minuten 6 A vast, "net
# begonnen met laden". Na de tweede herstart zegt de status van de paal twee
# minuten niets, zoals een integratie die nog laadt.
herstart_groep = Scenario(
    "herstart-groep",
    "dynamisch, een grote auto op 40% (opgegeven) aan een paal op een groep van 3x16 A, klaar om 08:00, twee herstarts in de nacht",
    contract="dynamisch", zon=Zon(wolken="geen"), auto=replace(GROTE, soc=40.0, meldt_soc=False),
    groep_amps=16.0, groep_last_w=400.0,
    begin="2026-09-07 21:55", kabel_erin="22:00", klaar_om="08:00", duur_uren=11, stap_seconden=15,
    prijzen=Prijzen(per_dag={
        "2026-09-07": [0.30] * 22 + [0.35, 0.351],
        "2026-09-08": [0.351, 0.339, 0.330, 0.330, 0.326, 0.328, 0.345, 0.36] + [0.30] * 16,
    }),
    gebeurtenissen=[("22:05", "soc_opgeven", 40), ("23:30", "herstart", None),
                    ("+1 00:40", "herstart", None), ("+1 00:40", "sensor_weg", ("status", 2))],
)
herstart_groep_zonder = herstart_groep.kopie(
    naam="herstart-groep-zonder", uitleg="dezelfde nacht zonder herstarts: zo hoort het te gaan",
    gebeurtenissen=[("22:05", "soc_opgeven", 40)],
)

# De laadbeurt van de eigenaar op 30-09-2026: snelladen op 3x25 A met een
# lastbewaker, en een apparaat van 10 A op één fase dat om de 35 seconden een
# kwartminuut aanstaat (geen deler van een minuut, zodat de ronde van de coach
# de ene keer op een top valt en de andere keer in een dal). De coach zakte
# voor de zekering en ging een minuut later op één meting in een dal terug
# naar 16 A, vier keer in een kwartier (v0.102.2: omhoog alleen als de hoogste
# meting van het venster ook past).
puls_snelladen = Scenario(
    "puls-tijdens-snelladen",
    "snelladen op 3x25 A met een lastbewaker; van 12:20 tot 12:40 staat er om de 35 seconden een kwartminuut 2 kW op één fase, en de meter meldt hele ampères",
    contract="vast", zon=Zon(wolken="geen"), voorspeller="geen",
    huis=Huis(basis_w=350.0, verdeling=(1.0, 0.0, 0.0), puls=(2000.0, 15.0, 35 / 60),
              puls_venster=("12:20", "12:40")),
    auto=replace(GROTE, soc=88.0, tekort_amps=0.8), lastbewaker=True, zekering=25.0, aansluiting_fasen=3,
    fase_hele_amps=True,
    begin="2026-09-07 11:55", kabel_erin="12:00", schema_aan=False, duur_uren=1.75, stap_seconden=5,
    gebeurtenissen=[("12:01", "snelladen", True)],
)
# Een auto die blijvend meer dan een ampère minder neemt dan de limiet. Bij de
# eigenaar op 30-09-2026 gaf de Easee 13 A door op een limiet van 14, en dan
# hield de rail van `ceiling_amps` hem tien minuten op 14 terwijl er ruimte was.
# Hier zakt hij voor een oven, en daarna moet hij weer omhoog kunnen.
auto_neemt_minder = Scenario(
    "auto-neemt-minder",
    "snelladen op 3x25 A; de auto neemt 1,5 A minder dan de limiet, van 12:15 tot 12:30 staat er een oven op de eerste fase, om 13:05 gaat de kabel eruit",
    contract="vast", zon=Zon(wolken="geen"), voorspeller="geen",
    huis=Huis(basis_w=350.0, verdeling=(1.0, 0.0, 0.0)), oven_w=2500.0,
    auto=replace(GROTE, soc=40.0, tekort_amps=1.5), zekering=25.0, aansluiting_fasen=3,
    begin="2026-09-07 11:55", kabel_erin="12:00", schema_aan=False, duur_uren=1.25, stap_seconden=5,
    gebeurtenissen=[("12:01", "snelladen", True), ("12:15", "oven", 15), ("13:05", "kabel_uit", None)],
)
# Dezelfde dag om 13:39:54: de auto is klaar, de laatste meterwaarde is van een
# paar seconden eerder en zegt nog de afname van de auto. De regelaar zette de
# batterij daarop in dezelfde seconde op ontladen op vol vermogen (v0.102.2: de
# batterij wacht op een meting van na het stoppen).
batterij_paal_stopt = Scenario(
    "batterij-paal-stopt",
    "nacht, vast contract, de coach regelt de batterij zelf en de meter meldt eens per vijf seconden; de bus is om 23:30 vol",
    contract="vast", zon=Zon(wolken="geen"), voorspeller="geen", auto=replace(BUS, soc=90.0),
    batterij=Batterij(soc=80.0, volgt_na_s=5.0, meter_tik_s=5.0, meter_fase_s=1.0),
    begin="2026-09-07 22:55", kabel_erin="23:00", schema_aan=False, duur_uren=1.0, stap_seconden=1,
    gebeurtenissen=[("23:01", "snelladen", True)], ronde_bij_status=True,
)

# "Anker mag zelf nul op de meter doen" (de eigenaar, 24-09-2026). De batterij heeft
# een eigen meter en houdt in zijn eigen stand zelf de meter op nul; de coach
# neemt het over als de paal laadt en geeft hem daarna terug (v0.97.0).
batterij_zelf_nul = batterij_paal.kopie(
    naam="batterij-zelf-nul",
    uitleg="vast contract, de accu doet zelf nul op de meter; de bus laadt na 20:00: dan neemt de coach het over, daarna weer zelf",
    batterij=Batterij(soc=80.0, eigen_nul=True, zelf_nul=True),
)
# De Anker van de eigenaar (28-09-2026): in zijn eigen stand is de stuurknop weg,
# dus de 0 W van vóór het overnemen kwam nooit aan. In het register staat nog de
# laatste opdracht van de sturing die er daarvoor was: 2500 W ontladen (v0.100.2).
batterij_zelf_knop_weg = batterij_zelf_nul.kopie(
    naam="batterij-zelf-knop-weg",
    uitleg="als batterij-zelf-nul, maar de knop is weg in de eigen stand en er staat nog 2500 W ontladen in het register",
    batterij=Batterij(soc=80.0, eigen_nul=True, zelf_nul=True, knop_weg=True, opdracht_w=-2500.0),
)
# In de klantwoning op 29-09-2026 kwam de knop pas veertien seconden na het omzetten
# terug. Het overnemen van v0.100.2 wachtte tien seconden en gaf het dan op; de
# regelaar dacht daarna dat de batterij op 0 W stond (v0.101.8).
batterij_zelf_knop_traag = batterij_zelf_knop_weg.kopie(
    naam="batterij-zelf-knop-traag",
    uitleg="als batterij-zelf-knop-weg, maar de knop komt pas veertien seconden na het omzetten terug",
    batterij=Batterij(soc=80.0, eigen_nul=True, zelf_nul=True, knop_weg=True, opdracht_w=-2500.0,
                      knop_terug_s=14.0),
    stap_seconden=5,
)
# Dezelfde avond, maar de coach doet de nul zelf: hij begint te sturen terwijl de
# batterij nog in zijn eigen stand staat, zoals in de klantwoning om 15:51:42.
batterij_knop_traag_start = batterij_paal.kopie(
    naam="batterij-knop-traag-start",
    uitleg="de coach begint te sturen (niet zelf nul); de batterij staat in zijn eigen stand, de knop komt pas na veertien seconden, en in het register staat 2500 W ontladen",
    batterij=Batterij(soc=80.0, knop_weg=True, opdracht_w=-2500.0, knop_terug_s=14.0),
    stap_seconden=5,
)
# "De coach moet de batterij niet zelf sturen ... alleen goedkoop inkopen en de anker
# stoppen als de laadpaal aan gaat" (de eigenaar, 29-09-2026, v0.101.9). Dezelfde twee
# dynamische dagen, met een batterij die zelf nul op de meter doet.
batterij_dynamisch_zelf = batterij_winter.kopie(
    naam="batterij-dynamisch-zelf",
    uitleg="dynamisch, bewolkt, de accu doet zelf nul op de meter: de coach neemt hem alleen over om goedkoop bij te laden",
    batterij=Batterij(soc=8.0, eigen_nul=True, zelf_nul=True),
)
# Handelen in twee (v0.141.0). Een bewoner op 21-10-2026: van het net laden mag, "als de
# prijs bijv. <15 cent is". Dezelfde bewolkte dagen, met een grens onder de goedkoopste
# uren van het scenario hierboven, en een met laden van het net helemaal uit.
batterij_netladen_onder = batterij_winter.kopie(
    naam="batterij-netladen-onder",
    uitleg="dynamisch, bewolkt, zelf nul, en van het net laden alleen onder een prijs",
    batterij=Batterij(soc=8.0, eigen_nul=True, zelf_nul=True, net_laden_onder=0.16),
)
batterij_netladen_uit = batterij_winter.kopie(
    naam="batterij-netladen-uit",
    uitleg="dynamisch, bewolkt, zelf nul, en van het net laden uit: alleen zon",
    batterij=Batterij(soc=8.0, eigen_nul=True, zelf_nul=True, net_laden=False),
)
batterij_dynamisch_zon_zelf = batterij_zomer.kopie(
    naam="batterij-dynamisch-zon-zelf",
    uitleg="dynamisch, heldere dag, de accu doet zelf nul op de meter",
    batterij=Batterij(soc=8.0, eigen_nul=True, zelf_nul=True),
)
batterij_zelf_wisselend = batterij_wisselende_last.kopie(
    naam="batterij-zelf-wisselend",
    uitleg="de wisselende last van 490 W, met een accu die zelf nul op de meter doet: de coach geeft geen enkele opdracht",
    # Hij staat nog in de externe stand van een vorige versie: de coach zet hem om.
    batterij=Batterij(soc=60.0, volgt_na_s=5.0, meter_tik_s=5.0, meter_fase_s=1.0,
                      eigen_nul=True, zelf_nul=True, modus="third_party_control", **ANKER_SENSOR),
)
# De klantwoning op 30-09-2026: een Anker die zelf nul op de meter doet, een
# dynamisch contract in kwartieren, en 's nachts een warmtepomp. Om 03:25:39 zei
# de coach midden in het laden van het net "nul op de meter", en omdat hij de
# batterij in handen had dekte hij toen het huis eruit: tot 06:00 elke paar
# minuten laden en ontladen door elkaar, 0,99 kWh eruit terwijl er 3,87 kWh
# in ging. Overdag laadde hij elk kwartier twaalf minuten en drie niet. Allebei
# `_rustig_vermogen`: moest er in dit kwartier nog minder dan 1% van de batterij
# bij, dan stopte hij (v0.102.3). De rondes vallen op :40, zoals die dag; dan
# zijn er aan het eind van elk kwartier drie rondes "nul", en met `ZELF_WACHT`
# van twee minuten gaf v0.102.2 de batterij dan elk kwartier terug.
KWARTIER_30_09 = {
    "2026-09-30": [
        0.269, 0.252, 0.257, 0.239, 0.256, 0.248, 0.249, 0.251, 0.245, 0.251, 0.243, 0.246, 0.247, 0.244, 0.246, 0.245,
        0.248, 0.240, 0.244, 0.254, 0.255, 0.262, 0.267, 0.284, 0.305, 0.323, 0.331, 0.332, 0.362, 0.379, 0.383, 0.377,
        0.398, 0.381, 0.360, 0.332, 0.366, 0.337, 0.313, 0.298, 0.284, 0.273, 0.264, 0.229, 0.268, 0.242, 0.230, 0.178,
        0.206, 0.180, 0.171, 0.170, 0.195, 0.211, 0.230, 0.257, 0.236, 0.246, 0.266, 0.279, 0.257, 0.285, 0.294, 0.286,
        0.284, 0.295, 0.336, 0.360, 0.340, 0.368, 0.388, 0.411, 0.389, 0.406, 0.413, 0.435, 0.425, 0.432, 0.445, 0.446,
        0.433, 0.431, 0.411, 0.398, 0.425, 0.386, 0.378, 0.339, 0.367, 0.360, 0.364, 0.345, 0.359, 0.339, 0.352, 0.327,
    ],
    "2026-10-01": [
        0.317, 0.313, 0.319, 0.319, 0.327, 0.328, 0.327, 0.322, 0.323, 0.325, 0.325, 0.322, 0.328, 0.328, 0.325, 0.322,
        0.323, 0.323, 0.320, 0.325, 0.323, 0.324, 0.336, 0.351, 0.346, 0.369, 0.386, 0.401, 0.392, 0.411, 0.423, 0.415,
        0.446, 0.416, 0.404, 0.390, 0.417, 0.395, 0.385, 0.365, 0.402, 0.376, 0.355, 0.339, 0.336, 0.330, 0.327, 0.319,
        0.323, 0.327, 0.319, 0.322, 0.323, 0.322, 0.320, 0.319, 0.323, 0.317, 0.321, 0.321, 0.315, 0.315, 0.319, 0.335,
        0.310, 0.331, 0.367, 0.424, 0.347, 0.399, 0.431, 0.462, 0.427, 0.450, 0.464, 0.505, 0.480, 0.492, 0.510, 0.489,
        0.468, 0.453, 0.434, 0.407, 0.432, 0.407, 0.397, 0.376, 0.397, 0.380, 0.376, 0.355, 0.373, 0.359, 0.350, 0.336,
    ],
}
# De klantwoning op zondag 25-10-2026, de dag van de wekelijkse volle beurt (v0.158.0): een
# Anker die zelf nul doet, om 09:40 op 5%, van het net naar 95% om 14:00, en daarna tot 16:00
# acht wissels tussen nul op de meter en laden van het net. De uurprijzen van die middag en
# avond, all-in; de ochtend (tot 16:00) is in de proef 0,15, zoals in proef 55 van
# test_batterij.py. Het huis op 1,5 kW. Tot 22:00: daarna laadt hij in de goedkope nacht
# rustig in kleine stapjes, en dat pendelen staat los hiervan open (batterij-kwartier-voorloper).
UREN_25_10 = [0.15] * 16 + [0.15, 0.235, 0.291, 0.26, 0.236, 0.22, 0.194, 0.169]
UREN_26_10 = [0.179, 0.168, 0.155, 0.15, 0.165, 0.192, 0.324, 0.467, 0.43, 0.371, 0.314, 0.264,
              0.241, 0.273, 0.306, 0.341, 0.375, 0.421, 0.438, 0.411, 0.365, 0.322, 0.285, 0.256]
batterij_volle_beurt_zelf = Scenario(
    "batterij-volle-beurt-zelf",
    "dynamisch, de zondag van de volle beurt met een accu die zelf nul doet: eenmaal bovenin blijft hij vol tot de beurt geboekt is, in plaats van elk kwartier om te slaan",
    contract="dynamisch", zon=Zon(wolken="geen"),
    huis=Huis(profiel={u: 1500.0 for u in range(24)}),
    batterij=Batterij(soc=5.0, capaciteit_kwh=14.5, max_laden_w=3500.0, max_ontladen_w=3500.0, soc_max=100.0,
                      meter=False, rte_opgegeven=0.736, eigen_nul=True, zelf_nul=True, knop_weg=True,
                      knop_terug_s=14.0, wekelijks_vol_dag=6, **ANKER_SENSOR),
    prijzen=Prijzen(per_dag={"2026-10-25": UREN_25_10, "2026-10-26": UREN_26_10}),
    begin="2026-10-25 09:30:40", duur_uren=12.5, **ZONDER_AUTO,
)
batterij_kwartier_zelf = Scenario(
    "batterij-kwartier-zelf",
    "dynamisch in kwartieren, de accu doet zelf nul en 's nachts draait een warmtepomp: de coach laadt goedkoop bij zonder tussendoor te ontladen, en houdt hem het hele laadvenster vast",
    contract="dynamisch-salderen", zon=Zon(piek_kw=2.4, wolken="helder"),
    huis=Huis(profiel={**{u: 600.0 for u in range(24)}, 3: 1600.0, 4: 1600.0, 5: 1600.0,
                       7: 900.0, 8: 900.0, 17: 1800.0, 18: 1800.0, 19: 1800.0, 20: 1200.0, 21: 1200.0}),
    # Zonder de ondergrens van v0.160.0: dit scenario is er voor de nachtbeurt zelf, en die
    # levert hier € 0,022 op. Met de grens slaat hij hem over (€ 2,15 tegen € 2,45 met de beurt).
    batterij=Batterij(soc=5.0, capaciteit_kwh=14.5, max_ontladen_w=3500.0, meter=False, rte_opgegeven=0.736,
                      eigen_nul=True, zelf_nul=True, knop_weg=True, knop_terug_s=14.0, min_winst=0.0, **ANKER_SENSOR),
    prijzen=Prijzen(per_dag=KWARTIER_30_09),
    begin="2026-09-30 02:30:40", duur_uren=22, **{**ZONDER_AUTO, "stap_seconden": 5},
)
# De klantwoning in de nacht van 05 op 06-10-2026, all-in per kwartier (één
# ontbrekend kwartier, 05-10 03:30, is het gemiddelde van de twee ernaast). De
# nacht ligt tussen € 0,309 en € 0,322; de coach laadde rustig verdeeld van het
# net, en elke keer dat de accustand een procent voorliep op het plan viel hij
# midden in een kwartier naar nul op de meter: 7,68 kWh erin, 2,36 kWh eruit.
KWARTIER_05_10 = {
    "2026-10-05": [
        0.339, 0.333, 0.340, 0.335, 0.335, 0.322, 0.331, 0.325, 0.328, 0.319, 0.321, 0.317, 0.316, 0.315, 0.315, 0.315,
        0.317, 0.317, 0.311, 0.315, 0.315, 0.318, 0.320, 0.332, 0.338, 0.355, 0.358, 0.374, 0.374, 0.392, 0.410, 0.421,
        0.449, 0.421, 0.401, 0.378, 0.391, 0.369, 0.327, 0.311, 0.361, 0.335, 0.313, 0.283, 0.304, 0.282, 0.255, 0.239,
        0.266, 0.225, 0.208, 0.184, 0.174, 0.167, 0.161, 0.160, 0.148, 0.160, 0.184, 0.208, 0.187, 0.226, 0.245, 0.271,
        0.219, 0.285, 0.317, 0.339, 0.317, 0.347, 0.378, 0.398, 0.374, 0.400, 0.415, 0.442, 0.426, 0.438, 0.458, 0.446,
        0.447, 0.408, 0.399, 0.379, 0.397, 0.383, 0.385, 0.353, 0.374, 0.360, 0.343, 0.310, 0.368, 0.336, 0.328, 0.311,
    ],
    "2026-10-06": [
        0.329, 0.320, 0.313, 0.309, 0.314, 0.312, 0.311, 0.317, 0.320, 0.315, 0.315, 0.313, 0.315, 0.315, 0.315, 0.317,
        0.314, 0.322, 0.318, 0.321, 0.309, 0.320, 0.338, 0.369, 0.362, 0.376, 0.384, 0.397, 0.398, 0.421, 0.430, 0.435,
        0.475, 0.439, 0.425, 0.387, 0.442, 0.398, 0.375, 0.322, 0.371, 0.339, 0.334, 0.316, 0.330, 0.333, 0.312, 0.302,
        0.320, 0.310, 0.311, 0.296, 0.302, 0.293, 0.287, 0.290, 0.297, 0.305, 0.310, 0.313, 0.304, 0.314, 0.317, 0.331,
        0.317, 0.334, 0.368, 0.403, 0.362, 0.400, 0.436, 0.517, 0.465, 0.499, 0.559, 0.620, 0.606, 0.588, 0.601, 0.554,
        0.545, 0.488, 0.468, 0.448, 0.461, 0.436, 0.428, 0.400, 0.409, 0.403, 0.403, 0.394, 0.392, 0.385, 0.380, 0.373,
    ],
}
batterij_kwartier_voorloper = batterij_kwartier_zelf.kopie(
    naam="batterij-kwartier-voorloper",
    uitleg="de nacht van 05 op 06-10-2026: rustig bijladen in kwartieren met een accu die zelf nul doet; loopt zijn stand een tik voor op het plan, dan houdt de coach hem vast tot het kwartier om is in plaats van nul op de meter",
    batterij=Batterij(soc=47.0, capaciteit_kwh=14.5, max_ontladen_w=3500.0, meter=False, rte_opgegeven=0.736,
                      eigen_nul=True, zelf_nul=True, knop_weg=True, knop_terug_s=14.0, min_winst=0.0, **ANKER_SENSOR),
    prijzen=Prijzen(per_dag=KWARTIER_05_10),
    begin="2026-10-05 22:30:40", duur_uren=12,
)
batterij_zonder_rendement = batterij_winter.kopie(
    naam="batterij-rendement-onbekend",
    uitleg="geen kWh-meter en niets opgegeven: alleen nul op de meter, niet van het net laden",
    batterij=Batterij(soc=8.0, meter=False), duur_uren=20,
)
# Het rendement per vermogen (v0.142.0): geen kWh-meter en niets opgegeven, een batterij
# met een vast verlies van 68 W bij ontladen en 92% bij laden, zoals gemeten in de
# eerste woning op 19-10-2026. De coach leert het zelf uit het vermogen en de accustand.
batterij_rendement_leren = batterij_winter.kopie(
    naam="batterij-rendement-leren",
    uitleg="dynamisch, wisselend, zelf nul, geen kWh-meter: de coach leert het rendement per vermogen uit de accustand",
    zon=Zon(wolken="wisselend"),
    batterij=Batterij(soc=30.0, meter=False, eigen_nul=True, zelf_nul=True, vast_ontladen_w=68.0),
    begin="2026-09-07 06:55", duur_uren=60,
)

BATTERIJ = [
    batterij_vast_zon, batterij_zonder_terug, batterij_vast_salderen, batterij_winter, batterij_zomer, batterij_handelen, batterij_handelen_krap, batterij_handelen_krap_zonder,
    batterij_reserve, batterij_negatief, batterij_volle_beurt, batterij_volle_beurt_zelf, batterij_paal, batterij_paal_stopt, batterij_sprong,
    batterij_meter_weg, batterij_herstart, batterij_anker_sensor, batterij_uurlast,
    batterij_klapperlast, batterij_wisselende_last, batterij_zonder_rendement,
    batterij_zelf_nul, batterij_zelf_knop_weg, batterij_zelf_knop_traag, batterij_knop_traag_start,
    batterij_dynamisch_zelf, batterij_netladen_onder, batterij_netladen_uit,
    batterij_dynamisch_zon_zelf, batterij_zelf_wisselend,
    batterij_kwartier_zelf, batterij_kwartier_voorloper, batterij_rendement_leren,
]
HERSTART = [herstart_groep, herstart_groep_zonder]

# Dezelfde dagen aan een Alfen (23-09-2026). Wat er anders is staat bij
# `Paal.merk`; wat er hetzelfde hoort te zijn meet test_virtueel.py: dezelfde
# kilowatturen en dezelfde kosten als aan een Easee, geen startwoord, en een
# limiet die elke minuut opnieuw geschreven wordt zodat de paal nooit op zijn
# veilige stroom terugvalt.
alfen_zonnig = vast_zonnig.kopie(
    naam="alfen-vast-zonnig", uitleg="vast-zonnig aan een Alfen: de limiet gaat elke minuut opnieuw de number in",
    paal=Paal(merk="alfen"),
)
alfen_dyn = dyn_zonnig.kopie(
    naam="alfen-dynamisch-zonnig", uitleg="dynamisch-zonnig aan een Alfen: de pauze op 0 A blijft staan tot het goedkope uur",
    paal=Paal(merk="alfen"),
)

# De auto stopt zelf op 80% aan een Alfen (25-09-2026 in de eerste woning, bij 92%
# geschat). Een Alfen zegt nooit "completed"; de coach leidt het af, en tot v0.99.0
# begon hij na zijn eigen 0 A (modus 3 B1, "wacht op start") gewoon weer: elke zestien
# minuten een kwartier 13 A aanbieden en een minuut 0.
alfen_laadgrens = laadgrens.kopie(
    naam="alfen-laadgrens-80", uitleg="laadgrens-80 aan een Alfen: klaar blijft klaar, en één herstart",
    paal=Paal(merk="alfen"),
)
# De fasewissel van een Alfen (v0.104.0). De eigenaar op 30-09-2026: "op die
# manier kan ik wel al op 1,4 kW zon beginnen met laden iig." Een driefasige auto,
# de modus zon, een bewolkte dag: zonder wisselen begint hij pas bij 3,7 kW, met
# wisselen op één fase vanaf 1,2 kW. Telkens hetzelfde huis zonder wissel ernaast.
alfen_drie_zon = vast_geen_klaar_tijd.kopie(
    naam="alfen-drie-zon-bewolkt", uitleg="modus zon, bewolkt, driefasige auto aan een Alfen die niet wisselt",
    laadmodus="zon", zon=Zon(wolken="bewolkt"), auto=replace(GROTE, soc=60.0), duur_uren=36,
    paal=Paal(merk="alfen"),
)
alfen_fasen_zon = alfen_drie_zon.kopie(
    naam="alfen-fasen-zon-bewolkt", uitleg="dezelfde dag, de Alfen mag wisselen: op één fase vanaf 1,2 kW zon",
    paal=Paal(merk="alfen", fasen_keuze=3), fasen_wisselen=True,
)
alfen_fasen_wisselend = alfen_fasen_zon.kopie(
    naam="alfen-fasen-wisselend", uitleg="wolkenvelden per twintig minuten: wisselen, maar niet heen en weer",
    zon=Zon(wolken="wisselend"),
)
alfen_fasen_helder = alfen_fasen_zon.kopie(
    naam="alfen-fasen-helder", uitleg="heldere dag: 's ochtends op één fase, midden op de dag op drie",
    zon=Zon(wolken="helder"),
)
# Met een planning en een dynamisch contract: de nacht van het net op drie fasen.
alfen_drie_dyn = dyn_zonnig.kopie(
    naam="alfen-drie-dynamisch", uitleg="dynamisch, planning, driefasige auto aan een Alfen die niet wisselt",
    auto=GROTE, paal=Paal(merk="alfen"),
)
alfen_fasen_dyn = alfen_drie_dyn.kopie(
    naam="alfen-fasen-dynamisch", uitleg="dezelfde dag, de Alfen mag wisselen: het net op drie fasen, zon op één",
    paal=Paal(merk="alfen", fasen_keuze=1), fasen_wisselen=True,
)
# Een driefasig profiel aan een Alfen die op "1 Phase" staat en niet wisselt, in de
# modus zon, zoals in de eerste woning op 03-10-2026. De stroom meldt alleen als hij
# verandert; tot v0.106.1 wiste een ronde zonder fasemeting de gemeten fase, en dan
# ging de paal met 4,3 kW zon van 13 naar 6 A, drie keer in twintig minuten.
alfen_een_fase = alfen_drie_zon.kopie(
    naam="alfen-een-fase-zon", uitleg="driefasige auto aan een Alfen op 1 Phase, helder, de stroom meldt alleen een wissel",
    zon=Zon(wolken="helder"), paal=Paal(merk="alfen", fasen_keuze=1, stroom_meldt_wissel=True),
)
alfen_een_fase_vers = alfen_een_fase.kopie(
    naam="alfen-een-fase-zon-vers", uitleg="dezelfde dag, de stroom meldt elke ronde",
    paal=Paal(merk="alfen", fasen_keuze=1),
)
alfen_doel_80 = doel_onder_auto.kopie(
    naam="alfen-doel-80", uitleg="doel-80 aan een Alfen: de 0 blijft elke minuut komen, anders laadt de paal na zijn geldigheidsduur op 16 A door",
    paal=Paal(merk="alfen"),
)

# Forecast.Solar zet een uurwaarde op het EIND van zijn periode (v0.100.0). De
# coach las tot dan alles als begin, en dan stond de zon een uur te laat. In
# de eigen woning op 26-09-2026 aan de kromme zelf gezien. Dezelfde dag met de
# sleutels zoals Forecast.Solar ze zet hoort precies hetzelfde te lopen.
# Oud: bij vast-voorspelling-mis € 2,68 (zon 7,7 kWh) tegen € 2,38 (zon 9,1),
# de vaatwasser om 09:35 in plaats van 09:00.
forecast_solar_vast = vast_voorspelling_mis.kopie(
    naam="forecast-solar-vast", uitleg="vast-voorspelling-mis met de uurkromme zoals Forecast.Solar hem levert: de waarde op het eind van het uur",
    voorspeller="forecast_solar",
)
# Forecast.Solar zonder energiedashboard (v0.100.1): de coach haalt dezelfde
# kromme bij de integratie achter de ingevulde sensoren, in plaats van te
# rekenen met sensoren die een uur achterlopen.
forecast_solar_sensoren = vast_voorspelling_mis.kopie(
    naam="forecast-solar-sensoren", uitleg="vast-voorspelling-mis met Forecast.Solar alleen als sensoren, niet in het energiedashboard: dezelfde kromme via de integratie van die sensoren",
    voorspeller="forecast_solar_sensoren",
)
forecast_solar_vaatwasser = vaatwasser_zon.kopie(
    naam="vaatwasser-forecast-solar", uitleg="vaatwasser-zon met de uurkromme zoals Forecast.Solar hem levert: dezelfde start om 09:00",
    voorspeller="forecast_solar",
)


# Bij de eigenaar op 11-10-2026: vast contract met salderen, een middag met weinig
# zon, de thuisbatterij doet zelf nul op de meter en laadt in zijn eigen stand een
# paar honderd watt van het dak. Die telde voor de coach als zon voor de auto (de
# auto gaat voor), en elke kruimel zon maakte bij een vast contract het lopende uur
# goedkoper dan 20:00: om 15:22 en 17:05 de bus wekken op 16 A en een uur van het net,
# en na het overnemen van de batterij was die zon weg. Sinds v0.109.0 opent pas een
# kwart van de ondergrens dat uur (`ZON_AANDEEL`).
vast_kruimelzon = Scenario(
    "vast-kruimelzon",
    "vast contract met salderen, zwakke middagzon, accu doet zelf nul op 10%, "
    "driefasige bus op 40% om 15:00 erin, klaar 06:00",
    contract="vast-salderen", vast_terugleverkosten=0.05,
    zon=Zon(kromme={15: 0.8, 16: 0.75, 17: 0.6, 18: 0.2, 19: 0.05}),
    auto=replace(BUS, soc=40.0, fasen=3),
    batterij=Batterij(soc=10.0, eigen_nul=True, zelf_nul=True),
    begin="2026-09-07 14:55", kabel_erin="15:00", duur_uren=16, stap_seconden=15,
)
# Een vast contract dat over 1 januari 2027 heen loopt (v0.134.0). De eigenaar op
# 19-10-2026: tot dan "Terugleververgoeding na saldering € 0,124000" met vaste
# terugleverkosten per schaal, vanaf 1-1-2027 "€ 0,072100" en "Terugleverkosten
# vanaf 1-1-2027 € 0,052756 per kWh". Op 4 januari 2027 saldeert niemand meer, ook
# met het vinkje aan: de zon die de bus in gaat kost wat hij anders had opgebracht,
# en dat is wat het contract voor na salderen zegt.
vast_na_salderen = vast_zonnig.kopie(
    naam="vast-na-salderen",
    uitleg="vast contract, salderen aangevinkt, op 4 januari 2027: de terugleverprijs van na salderen",
    contract="vast-salderen", vast_prijs=0.24171, vast_teruglevering=0.124, vast_terugleverkosten=0.0,
    vast_teruglevering_na=0.0721, vast_terugleverkosten_na=0.052756,
    begin="2027-01-04 06:55",
)
vast_na_salderen_leeg = vast_na_salderen.kopie(
    naam="vast-na-salderen-leeg",
    uitleg="hetzelfde zonder bedragen voor na salderen: dan de vergoeding en de kosten van ervoor",
    vast_teruglevering_na=None, vast_terugleverkosten_na=None,
)
# Terugleverkosten in vier vormen (v0.135.0). De eigenaar op 19-10-2026: "ik wil het zo goed
# mogelijk hebben". Een vast contract met salderen, inkoop € 0,25, vergoeding € 0,12 en
# kosten € 0,05. Wat de zon in de bus kost is wat hij anders had opgebracht: met salderen
# de inkoopprijs min de kosten van een kWh extra, en bij een huis dat over de
# afrekenperiode netto teruglevert de vergoeding min de kosten.
vast_kosten_kwh = vast_zonnig.kopie(
    naam="vast-kosten-per-kwh",
    uitleg="vast, salderen, terugleverkosten per kWh over alles: de zon kost 0,25 min 0,05",
    contract="vast-salderen", vast_prijs=0.25, vast_teruglevering=0.12, vast_terugleverkosten=0.05,
    netto_terug=False,
)
vast_kosten_schalen = vast_kosten_kwh.kopie(
    naam="vast-kosten-schalen",
    uitleg="hetzelfde met terugleverkosten in schalen: een kWh extra kost niets, de zon kost 0,25",
    kosten_vorm="schalen",
)
vast_kosten_overschot = vast_kosten_kwh.kopie(
    naam="vast-kosten-overschot",
    uitleg="kosten alleen over het overschot, een huis dat netto afneemt: alles saldeert, de zon kost 0,25",
    kosten_vorm="overschot",
)
vast_kosten_overschot_netto = vast_kosten_overschot.kopie(
    naam="vast-kosten-overschot-netto-terug",
    uitleg="kosten alleen over het overschot, een huis dat netto teruglevert: de zon kost 0,12 min 0,05",
    netto_terug=True,
)
dyn_salderen_vol = dyn_salderen.kopie(
    naam="dynamisch-salderen-vol",
    uitleg="dynamisch mét salderen en de hele all-in prijs terug: zon is evenveel waard als inkoop",
    salderen_vol=True,
)
# Portugal (v0.137.0): een contract met tijdvakken en zonder salderen, zoals bij een klant
# daar (EDP Comercial, bi-horário, ciclo diário). Daluren van 22:00 tot 08:00 in Lissabon;
# het virtuele huis staat op UTC+2, dus hier van 23:00 tot 09:00. De bus gaat om 18:00 aan
# de paal en moet om 07:00 klaar zijn: laden in de daluren, niet ervoor.
PT_EDP = {"tarifa": "bi", "ciclo": "diario", "fornecedor": "EDP Comercial",
          "energia": {"vazio": 0.1340, "fora_vazio": 0.2198}, "iec": 0.001, "iva": 23.0,
          "excedente": {"modo": "nenhum", "preco": 0.0, "fator": 75.0, "omie_entity": ""}}
pt_bihorario = vast_avond.kopie(
    naam="pt-bihorario",
    uitleg="Portugal, bi-horário ciclo diário, kabel om 18:30 erin, klaar om 06:00: in de daluren laden",
    pt=PT_EDP,
)
# Zonder accustand, in de goedkope uren (v0.185.0). De eigenaar op 30-10-2026, over een klant in
# Portugal met een auto die zijn accustand niet doorgeeft: "gewoon vol vermogen laden in de goedkope
# uren. Dat moet een instelling worden in de coach." En: "het zou kunnen dat de auto niet vol is in de
# ochtend maar dat is dan aan de klant." Een eigen vinkje bij de paal, standaard uit; `pt-bihorario`
# hierboven is dezelfde avond zonder.
pt_zonder_accustand = pt_bihorario.kopie(
    naam="pt-bi-zonder-accustand",
    uitleg="Portugal, bi-horário, een bus zonder accustand en het vinkje aan: vanaf 23:00 op vol vermogen, "
           "en een herstart om 23:30",
    auto=Auto(meldt_soc=False), goedkoop_blok=True,
    gebeurtenissen=[("23:30", "herstart", None)],
)
pt_zonder_accustand_groot = pt_zonder_accustand.kopie(
    naam="pt-bi-zonder-accustand-groot",
    uitleg="hetzelfde vinkje, een auto van 77 kWh op één fase, geen klaar-tijd, kabel om 20:30: alleen in de "
           "daluren, 's ochtends niet vol, en de volgende nacht verder",
    auto=Auto(naam="Grote", capaciteit_kwh=77.0, soc=20.0, fasen=1, max_amps=16.0, meldt_soc=False),
    schema_aan=False, begin="2026-09-07 20:25", kabel_erin="20:30", duur_uren=31, gebeurtenissen=[],
)


# Een Growatt (v0.150.0). De eigenaar op 22-10-2026: de Growatt sturen vanuit de coach, voor
# elke klant met een Growatt. Zoals in de klantwoning: bi-horário, een SPH met een
# laadschema, ongeveer 12,5 kWh per 100%, de vloer op 15%, ongeveer 7,8 kW bij 100% laden
# (1,6 kW bij 20%), 90% uit de eigen tellers. De coach weet van tevoren niet wat hij eruit kan;
# dat ziet hij 's avonds. Op een bewolkte dag vult de zon hem en laadt hij niet van het net;
# `growatt-zon` laat zien dat hij dan ook niets schrijft.
GROWATT_SPH = dict(growatt=True, soc=45.0, capaciteit_kwh=12.5, max_laden_w=7800.0, max_ontladen_w=6000.0,
                   soc_min=15.0, soc_max=100.0, rte=0.81, meter=False, teller_in=311.9, teller_uit=280.7,
                   growatt_min_pct=10)
growatt_bihorario = batterij_winter.kopie(
    naam="growatt-bihorario",
    uitleg="Portugal, bi-horário, een Growatt met een laadschema: in vazio rustig van het net, overdag het huis",
    pt=PT_EDP, batterij=Batterij(**GROWATT_SPH), begin="2026-10-22 18:00", duur_uren=29,
    # Een donkere dag, zoals er in de winter een paar zijn: dan loont vazio.
    zon=Zon(wolken="geen"), voorspeller="geen",
    # Wat de coach op eerdere dagen zag: hij laadde op zon met 3,2 kW. Meer weet hij niet van
    # het laadvermogen; dat het 7,8 kW is meet hij in het eerste vak.
    batterij_stand={"growatt_in_w": 3200},
)
# Een herstart waarbij de Growatt-integratie later klaar is dan de coach (v0.162.0). In een
# klantwoning op 26-10-2026 stond de batterij daarna een uur buiten de coach.
growatt_herstart = growatt_bihorario.kopie(
    naam="growatt-herstart",
    uitleg="dezelfde Growatt, Home Assistant herstart om 21:00 en de Growatt-integratie is er pas drie minuten later",
    gebeurtenissen=[("21:00", "sensor_weg", ("bat_soc", 3)), ("21:00", "herstart", None)],
)
growatt_zon = growatt_bihorario.kopie(
    naam="growatt-zon",
    uitleg="dezelfde Growatt op een bewolkte dag: de zon van morgen vult hem, dus geen laden van het net",
    zon=Zon(wolken="bewolkt"), voorspeller=batterij_winter.voorspeller,
)
# Zonder zonvoorspeller, met alleen het weer van Home Assistant (v0.151.0): de coach haalt de
# zon van morgen uit zijn eigen opwek van de dagen ervoor. De eigenaar op 22-10-2026: "Sven wil
# niet afhangen van kWp/helling/richting."
growatt_eigen_zon = growatt_zon.kopie(
    naam="growatt-eigen-zon",
    uitleg="dezelfde Growatt zonder zonvoorspeller: de zon van morgen uit de eigen opwek en het weer",
    zon=Zon(wolken="helder"), voorspeller="geen", weer=True,
)
growatt_schaduw = growatt_bihorario.kopie(
    naam="growatt-schaduw",
    uitleg="dezelfde Growatt zonder het vinkje: de coach rekent en zegt wat hij zou schrijven, maar schrijft niets",
    batterij=Batterij(**GROWATT_SPH, growatt_vinkje=False),
)

# Vasthouden (v0.155.0). De eigenaar op 23-10-2026: "kunnen we de accu net als anker ook op
# hold zetten? Dus pas als het dure uur in gaat dan pas ontladen?" Een avond die de batterij
# niet leegtrekt: om 21:30 zit hij nog op 50%. In vazio houdt de coach dat vast met een vak
# op de stopgrens, en laadt hij aan het eind alleen bij wat er dan nog mist. Deze Growatt
# stopt zelf op de stopgrens en staat daar stil zolang het vak loopt.
growatt_vasthouden = growatt_bihorario.kopie(
    naam="growatt-vasthouden",
    uitleg="dezelfde Growatt met nog 50% om 21:30: in vazio vasthouden, en pas in de dure uren ontladen",
    batterij=Batterij(**{**GROWATT_SPH, "soc": 50.0}, growatt_stopt_zelf=True),
    begin="2026-10-22 21:30", duur_uren=26,
)

# De zon binnen het uur en een ondergrens aan bijladen (v0.160.0). In de klantwoning op
# 26-10-2026 was de Growatt om 21:30 leeg, en in het eerste dure uur (08:00 in de tijd van het huis daar, hier
# 09:00) kwam de zon op: 2,95 kWh in dat uur tegen 3,06 van het huis. De coach zag 0,1 kWh
# tekort omdat elk kwartier een kwart van de zon kreeg; het was meer, want de zon loopt op.
# Bijladen levert dan een paar cent op, en de eigenaar wil een ondergrens van € 0,05.
OCHTEND_ZON = {9: 2.95, 10: 4.5, 11: 5.5, 12: 6.0, 13: 6.0, 14: 5.5, 15: 4.5, 16: 3.0, 17: 1.5, 18: 0.4}
growatt_ochtend = growatt_bihorario.kopie(
    naam="growatt-ochtend",
    uitleg="dezelfde Growatt leeg om 21:30 en een zonnige ochtend die het dure uur bijna dekt: bijladen levert minder op dan € 0,05",
    batterij=Batterij(**{**GROWATT_SPH, "soc": 15.0}),
    zon=Zon(kromme=OCHTEND_ZON), voorspeller=batterij_winter.voorspeller,
    huis=Huis(profiel={**{u: 300.0 for u in range(24)}, 9: 3600.0}),
    begin="2026-10-22 21:30", duur_uren=14,
    # Wat hij op eerdere avonden zag: 3,2 kW erin en 2,25 kW eruit. Zonder dat laatste weet
    # de coach niet dat de batterij het huis kan voeden, en dan is bijladen niets waard.
    batterij_stand={"growatt_in_w": 3200, "growatt_uit_w": 2250},
)
growatt_ochtend_zonder_grens = growatt_ochtend.kopie(
    naam="growatt-ochtend-zonder-grens",
    uitleg="dezelfde ochtend met de ondergrens op nul: dan laadt hij voor die paar cent wel bij",
    batterij=Batterij(**{**GROWATT_SPH, "soc": 15.0}, min_winst=0.0),
)
# Een Growatt die ook de 10% van de coach weigert (v0.163.0). In de klantwoning op 26-10-2026 nam de
# API 8% niet aan, hield hij 100 en zette hij de rest wel; de coach schreef daarna om de paar minuten
# weer 8. Hier weigert hij alles onder 30%: de coach leert het na één keer teruglezen.
growatt_weigert = growatt_ochtend_zonder_grens.kopie(
    naam="growatt-weigert",
    uitleg="dezelfde ochtend, en een Growatt die een laag laadvermogen niet aanneemt: de coach leert het en herhaalt niet",
    batterij=Batterij(**{**GROWATT_SPH, "soc": 15.0, "growatt_min_pct": 30}, min_winst=0.0),
)
# Een Growatt die na zijn eigen ronde 100/100 teruggeeft voor een vermogen dat er wel stond (v0.165.1).
# In de klantwoning las 48% op 26-10-2026 drie uur lang goed terug, en daarna telkens 100; v0.163.0 telde
# dat als geweigerd en klom in één nacht naar 100%. Hier geeft hij het vanaf een half uur na het schrijven.
growatt_terug_100 = growatt_ochtend_zonder_grens.kopie(
    naam="growatt-terug-100",
    uitleg="dezelfde ochtend, en een Growatt die later 100% teruggeeft: de coach blijft bij zijn eigen vermogen",
    batterij=Batterij(**{**GROWATT_SPH, "soc": 15.0, "growatt_terug_100": 30}, min_winst=0.0),
)
# Een batterij die de coach een tijd niet volgt (v0.167.0). In een klantwoning laadde de batterij op
# 27-10-2026 zeventien minuten 2,5 kW van het net terwijl de coach nul op de meter wilde, en niemand zag
# het. Hier 25 minuten, extern gestuurd en in zijn eigen stand; en twee minuten, wat geen melding geeft.
batterij_volgt_niet = batterij_vast_zon.kopie(
    naam="batterij-volgt-niet",
    uitleg="vast, heldere dag; 's avonds laadt de batterij 25 minuten van het net, wat de coach ook zegt",
    batterij=Batterij(soc=20.0, eigenwijs=("19:00", "19:25")),
)
batterij_volgt_niet_zelf = batterij_vast_zon.kopie(
    naam="batterij-volgt-niet-zelf",
    uitleg="hetzelfde, met een batterij die zelf nul op de meter doet: de coach neemt hem over",
    batterij=Batterij(soc=20.0, eigen_nul=True, zelf_nul=True, eigenwijs=("19:00", "19:25")),
)
batterij_volgt_even_niet = batterij_vast_zon.kopie(
    naam="batterij-volgt-even-niet",
    uitleg="hetzelfde, twee minuten: dat is geen storing",
    batterij=Batterij(soc=20.0, eigen_nul=True, zelf_nul=True, eigenwijs=("19:00", "19:02")),
)
# Een paal die zichzelf herstart (v0.163.3): in een klantwoning nam een Alfen op 26-10-2026 zes
# minuten lang geen opdracht aan, en elke ronde gaf een fout met traceback. Nu een waarschuwing, en
# pas na tien minuten een melding; wat de paal deed blijft hij doen.
klant_paal_weg = vast_zonnig.kopie(
    naam="vast-zonnig-paal-weg",
    uitleg="vast-zonnig, en de Easee neemt van 09:03 tot 09:09 geen opdrachten aan, terwijl hij de zon volgt",
    gebeurtenissen=[("09:03", "paal_onbereikbaar", 6)],
)
alfen_paal_weg = alfen_dyn.kopie(
    naam="alfen-paal-weg",
    uitleg="alfen-dynamisch-zonnig, en de Alfen neemt van 18:56 tot 19:08 geen opdrachten aan, in de pauze",
    gebeurtenissen=[("18:56", "paal_onbereikbaar", 12)],
)
# Een paal en een batterij op dezelfde kast (v0.164.0). In een klantwoning plande de batterij op 26-10-2026
# 2,5 kW van het net in de uren dat de paal er 13 A per fase op zette, op een kast van 3x16 A. De regelaar
# hield de zekering heel, maar het uurplan rekende met goedkope kWh die niet kwamen.
groep_paal_batterij = Scenario(
    "groep-paal-en-batterij",
    "dynamisch, een grote auto en een batterij op L3 aan dezelfde kast van 3x16 A, een goedkope nacht",
    contract="dynamisch", zon=Zon(wolken="geen"), auto=replace(GROTE, soc=40.0, meldt_soc=False),
    batterij=Batterij(soc=10.0, max_laden_w=2500.0, max_ontladen_w=2500.0, fase=2),
    groep_amps=16.0, groep_last_w=200.0, batterij_in_groep=True,
    begin="2026-09-07 21:55", kabel_erin="22:00", klaar_om="08:00", duur_uren=24, stap_seconden=15,
    prijzen=Prijzen(per_dag={
        "2026-09-07": [0.30] * 22 + [0.32, 0.32],
        "2026-09-08": [0.30, 0.30, 0.18, 0.18, 0.18, 0.22, 0.22, 0.30] + [0.32] * 9 + [0.45] * 4 + [0.32] * 3,
    }),
    gebeurtenissen=[("22:05", "soc_opgeven", 40)],
)
groep_paal_batterij_los = groep_paal_batterij.kopie(
    naam="groep-paal-en-batterij-los", uitleg="dezelfde nacht met de batterij buiten de kast",
    batterij_in_groep=False,
)
# Dezelfde kast zonder eigen meter (v0.164.1). Tot dan sloeg de coach zo'n kast over, en laadde de
# batterij er naast de paal op haar volle vermogen: 13 + 10,9 A op 16 A.
groep_paal_batterij_zonder_meter = groep_paal_batterij.kopie(
    naam="groep-paal-en-batterij-zonder-meter", uitleg="dezelfde nacht, en de kast heeft geen eigen meter",
    groep_meter=False,
)

ALLE = [
    groep_paal_batterij, groep_paal_batterij_los, groep_paal_batterij_zonder_meter,
    alfen_zonnig, alfen_dyn, alfen_paal_weg, klant_paal_weg, alfen_doel_80, alfen_laadgrens,
    alfen_drie_zon, alfen_fasen_zon, alfen_fasen_wisselend, alfen_fasen_helder, alfen_drie_dyn, alfen_fasen_dyn,
    alfen_een_fase, alfen_een_fase_vers,
    vast_zonnig, vast_bewolkt, vast_geen_zon, vast_wisselend, vast_salderen, vast_avond,
    vast_grote_auto, vast_zonder_voorspelling, vast_sensoren, vast_voorspelling_mis,
    vast_geen_klaar_tijd, vast_krap, vast_onhaalbaar,
    dyn_zonnig, dyn_bewolkt, dyn_geen_zon, dyn_markt, dyn_salderen, dyn_avond, dyn_grote_auto,
    dyn_negatief, dyn_kwartier_later, dyn_geen_klaar_tijd,
    meter_teken, meter_teken_om, een_fase_krap, oven, puls_snelladen, auto_neemt_minder, lastbewaker, warmtepomp, ford_bijkomen, ford_oude_opslag, warmtepomp_uit,
    geen_soc, soc_opgegeven, soc_traag, laadgrens, laadgrens_ingesteld,
    doel_onder_auto, soc_stappen, bijna_vol, auto_slaapt,
    pauze, pauze_vergeten, snelladen, kabel_eruit, oude_tijden,
    p1_weg, p1_lang_weg, paal_traag,
    tien_uur, tien_uur_zon, tien_uur_valt_tegen, tien_uur_vast, equalizer, prijzen_weg,
    weekend, weekend_geen_zon, weekend_voorspelling_mis,
    ford_storing, ford_storing_traag, ford_inpluggen, ford_inpluggen_zonder, ford_inpluggen_kabel,
    ford_storing_wachtend, vast_avond_proef, een_fase_groep, een_fase_blind, afbouw, afbouw_geleerd,
    afbouw_krap, afbouw_krap_geleerd, afbouw_bovenin, afbouw_bovenin_oud, fasekeuze, zon_belofte, zon_belofte_dyn,
    vaatwasser_avond, vaatwasser_zon, vaatwasser_krap, vaatwasser_afstand_uit, vaatwasser_uiterlijk,
    vaatwasser_dom_zon, vaatwasser_dom_leert, vaatwasser_dom_negeert, vaatwasser_dom_zelf,
    vaatwasser_eigen_tabel, vaatwasser_gemeten, vaatwasser_meter_wint, vaatwasser_vroeg, vaatwasser_vroeg_verwacht, vaatwasser_herstart,
    vaatwasser_zonpiek, vaatwasser_eindtijd, vaatwasser_eindtijd_bijstellen, vaatwasser_na_klaartijd, vaatwasser_na_klaartijd_nu,
    vaatwasser_lokaal, vaatwasser_lokaal_deur, vaatwasser_lokaal_afstand_uit, vaatwasser_klep_dicht,
    wasmachine_miele, wasmachine_miele_gemeten, wasmachine_miele_onderbroken,
    forecast_solar_vast, forecast_solar_vaatwasser, forecast_solar_sensoren,
    boiler_leert, boiler_nacht, boiler_zon, boiler_stekker_stuk,
    airco_zon, airco_plaatje, airco_bewoner, airco_goedkoop, airco_geen_zon,
    *KLANTWONING,
    *BATTERIJ,
    vast_zon_modus, bewolkt_zon_modus, half_zon_modus, dyn_continu,
    batterij_helpt_auto, batterij_helpt_auto_nacht, batterij_helpt_auto_zonder_nacht,
    voorrang_auto_eerst, voorrang_accu_eerst, vast_kruimelzon, vast_na_salderen, vast_na_salderen_leeg, pt_bihorario,
    pt_zonder_accustand, pt_zonder_accustand_groot, dyn_zonder_accustand, dyn_zonder_accustand_donker,
    vast_kosten_kwh, vast_kosten_schalen, vast_kosten_overschot, vast_kosten_overschot_netto, dyn_salderen_vol,
    planning_auto_eerst, planning_accu_eerst,
    *HERSTART,
    growatt_bihorario, growatt_zon, growatt_eigen_zon, growatt_schaduw, growatt_vasthouden,
    growatt_ochtend, growatt_ochtend_zonder_grens, growatt_herstart, growatt_weigert, growatt_terug_100,
    batterij_volgt_niet, batterij_volgt_niet_zelf, batterij_volgt_even_niet,
]


def zoek(naam: str) -> Scenario:
    for s in ALLE:
        if s.naam == naam:
            return s
    raise KeyError(naam)
