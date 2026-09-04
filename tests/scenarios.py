"""De scenario's voor het virtuele huis.

Elk scenario is één laadbeurt in één soort woning. De assen waarlangs ze
verschillen zijn de installatievormen die er bij klanten zijn: het contract,
het weer, het moment dat de kabel erin gaat, de klaar-tijd, de auto, de meter,
en wat er onderweg misgaat. Zie `virtueel.py` voor wat elk veld doet.

Twee afspraken van Sven (04-09-2026) die de controles in `test_virtueel.py`
bewaken:

- **Vast contract:** laden in de zonuren is goedkoper, en naar de prijs hoeft
  niet gekeken te worden, want die is elk uur hetzelfde. Wat er van het net
  bij moet komt na de avondpiek (`EVENING_START` in planner.py).
- **Dynamisch contract:** alles telt mee: zon, prijs, teruglevering, salderen.
"""

from dataclasses import replace

from virtueel import Auto, Huis, Paal, Prijzen, Scenario, Zon

# Twee auto's die er in het echt hangen: een kleine bus op één fase, en een
# grote op drie.
BUS = Auto(naam="Bus", capaciteit_kwh=19.7, soc=30.0, fasen=1, max_amps=16.0, wek_amps=10.0)
GROTE = Auto(naam="Grote", capaciteit_kwh=77.0, soc=20.0, fasen=3, max_amps=16.0)

# Svens voorbeeld van 04-09-2026: "de goedkoopste uren zijn vanaf 13 uur tot een
# uurtje of 17 en dan in de nacht weer." Een dag waarop de ochtend duurder is
# dan de middag en de nacht, kaal per uur.
MARKT_SVEN = [
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
dyn_geen_klaar_tijd = dyn_zonnig.kopie(
    naam="dynamisch-geen-klaar-tijd", uitleg="dynamisch, schema uit",
    schema_aan=False, duur_uren=36,
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
bijna_vol = vast_zonnig.kopie(
    naam="bijna-vol", uitleg="bus op 95% erin",
    auto=replace(BUS, soc=95.0),
)
auto_slaapt = vast_zonnig.kopie(
    naam="auto-wordt-niet-wakker", uitleg="een auto die pas op 14 A op gang komt",
    auto=replace(BUS, wek_amps=14.0),
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

# --- Svens voorbeeld: om tien uur erin, klaar om zes -------------------------

tien_uur = Scenario(
    "tien-uur-erin-dynamisch",
    "dynamisch, geen panelen, grote auto om 10:00 erin, goedkoop van 13 tot 17 en 's nachts",
    contract="dynamisch", zon=Zon(wolken="geen"), voorspeller="geen", auto=GROTE,
    prijzen=Prijzen(markt=MARKT_SVEN), begin="2026-09-07 09:55", kabel_erin="10:00",
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
# Svens tweede voorbeeld: zondag uitgevinkt, dus klaar op maandag 06:00. Tot
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

# --- Van den Dam, het weekend van 04-09-2026 -----------------------------------
#
# De eerste echte laadbeurt met v0.47.x, nagebouwd met zijn eigen cijfers zoals
# ze vrijdagavond 21:21 in Home Assistant stonden: de all-in prijzen van
# vrijdag en zaterdag, de zonkromme van het energiedashboard voor zaterdag
# (lokale uren), het huisverbruik als mediaan per uur over de week ervoor uit
# de eigen opslag, de Ford op 8,5%, de Equalizer, zaterdag uitgevinkt en
# zondag klaar om 06:00. Zondag zelf kende niemand nog; die staat hier als
# een aanname en er is een variant met een dure zondagnacht.
VDD_HUIS_W = {
    0: 1138, 1: 1052, 2: 1026, 3: 1355, 4: 949, 5: 723, 6: 640, 7: 972,
    8: 1029, 9: 1048, 10: 970, 11: 986, 12: 972, 13: 1300, 14: 1419, 15: 1263,
    16: 1576, 17: 1589, 18: 1322, 19: 1299, 20: 1507, 21: 1244, 22: 1809, 23: 1085,
}
VDD_ZON_KWH = {
    7: 0.54, 8: 1.12, 9: 1.56, 10: 1.88, 11: 2.28, 12: 2.64, 13: 2.68,
    14: 2.42, 15: 2.0, 16: 1.64, 17: 1.24, 18: 0.73, 19: 0.34,
}
VDD_VRIJDAG = [
    0.3018, 0.2790, 0.2694, 0.2690, 0.2600, 0.2609, 0.2899, 0.3133,
    0.3141, 0.2957, 0.2574, 0.2048, 0.1870, 0.1694, 0.1776, 0.1779,
    0.1872, 0.2141, 0.2829, 0.3032, 0.3117, 0.3159, 0.3098, 0.2993,
]
VDD_ZATERDAG = [
    0.2320, 0.2321, 0.2243, 0.2047, 0.2010, 0.2026, 0.2198, 0.2070,
    0.1835, 0.1320, 0.1287, 0.1244, 0.1182, 0.1123, 0.1137, 0.1210,
    0.1269, 0.1858, 0.3105, 0.3616, 0.3918, 0.4000, 0.3902, 0.3666,
]
# Zondag: een aanname, de zaterdag met een iets duurdere nacht.
VDD_ZONDAG = [
    0.2500, 0.2450, 0.2400, 0.2300, 0.2250, 0.2280, 0.2350, 0.2200,
    0.1900, 0.1500, 0.1400, 0.1350, 0.1300, 0.1250, 0.1280, 0.1350,
    0.1400, 0.1950, 0.3200, 0.3700, 0.3900, 0.4000, 0.3900, 0.3600,
]
VDD_ZONDAG_DUUR = [0.31] * 8 + VDD_ZONDAG[8:]
FORD = Auto(naam="Ford", capaciteit_kwh=65.0, soc=8.5, fasen=3, max_amps=16.0)
VDD_PRIJZEN = {"2026-09-04": VDD_VRIJDAG, "2026-09-05": VDD_ZATERDAG, "2026-09-06": VDD_ZONDAG}

van_den_dam = Scenario(
    "van-den-dam",
    "vrijdag 19:01 erin op 8,5%, zaterdag uit, zondag klaar om 06:00, met zijn eigen prijzen, zon en huis",
    contract="dynamisch-salderen",
    zon=Zon(kromme=VDD_ZON_KWH), huis=Huis(profiel=VDD_HUIS_W, verdeling=(0.25, 0.15, 0.6)),
    auto=FORD, paal=Paal(teller_interval_min=60),
    prijzen=Prijzen(per_dag=VDD_PRIJZEN),
    begin="2026-09-04 18:55", kabel_erin="19:01", klaar_om="06:00", dagen_uit=(5,),
    duur_uren=36, equalizer=True, zekering=25.0, aansluiting_fasen=3,
)
vdd_bewolkt = van_den_dam.kopie(
    naam="van-den-dam-bewolkt", uitleg="hetzelfde, maar zaterdag valt de zon tegen: een derde van de verwachting",
    zon=Zon(kromme=VDD_ZON_KWH, wolken="bewolkt", voorspeld="helder"),
)
vdd_geen_zon = van_den_dam.kopie(
    naam="van-den-dam-geen-zon", uitleg="hetzelfde, zaterdag helemaal dicht terwijl helder voorspeld was",
    zon=Zon(kromme=VDD_ZON_KWH, wolken="geen", voorspeld="helder"),
)
vdd_dure_zondag = van_den_dam.kopie(
    naam="van-den-dam-dure-zondagnacht", uitleg="hetzelfde, maar de zondagnacht wordt 0,31: dan moet zaterdagmiddag het werk doen",
    prijzen=Prijzen(per_dag={**VDD_PRIJZEN, "2026-09-06": VDD_ZONDAG_DUUR}),
)
vdd_wekken = van_den_dam.kopie(
    naam="van-den-dam-ford-wekken", uitleg="hetzelfde, de Ford wil 10 A om wakker te worden",
    auto=replace(FORD, wek_amps=10.0),
)
vdd_koken = van_den_dam.kopie(
    naam="van-den-dam-oven", uitleg="hetzelfde, zaterdag om 12:30 een uur lang 3 kW erbij op de zware fase",
    gebeurtenissen=[("12:30", "oven", 60)],
)
vdd_p1_weg = van_den_dam.kopie(
    naam="van-den-dam-p1-weg", uitleg="hetzelfde, de P1 valt zaterdag om 11:00 een kwartier weg",
    gebeurtenissen=[("11:00", "p1_weg", 15)],
)
vdd_prijzen_laat = van_den_dam.kopie(
    naam="van-den-dam-prijzen-laat", uitleg="hetzelfde, de prijzen van zondag komen pas om 15:30",
    prijzen=Prijzen(bekend_om="15:30", per_dag=VDD_PRIJZEN),
)
vdd_geen_soc = van_den_dam.kopie(
    naam="van-den-dam-geen-accustand", uitleg="hetzelfde, de Ford meldt zijn accustand niet",
    auto=replace(FORD, meldt_soc=False),
)
VAN_DEN_DAM = [van_den_dam, vdd_bewolkt, vdd_geen_zon, vdd_dure_zondag, vdd_wekken,
               vdd_koken, vdd_p1_weg, vdd_prijzen_laat, vdd_geen_soc]

ALLE = [
    vast_zonnig, vast_bewolkt, vast_geen_zon, vast_wisselend, vast_salderen, vast_avond,
    vast_grote_auto, vast_zonder_voorspelling, vast_sensoren, vast_voorspelling_mis,
    vast_geen_klaar_tijd, vast_krap, vast_onhaalbaar,
    dyn_zonnig, dyn_bewolkt, dyn_geen_zon, dyn_markt, dyn_salderen, dyn_avond, dyn_grote_auto,
    dyn_negatief, dyn_kwartier_later, dyn_geen_klaar_tijd,
    meter_teken, meter_teken_om, een_fase_krap, oven, lastbewaker,
    geen_soc, soc_opgegeven, soc_traag, laadgrens, bijna_vol, auto_slaapt,
    pauze, pauze_vergeten, snelladen, kabel_eruit, oude_tijden,
    p1_weg, p1_lang_weg, paal_traag,
    tien_uur, tien_uur_zon, tien_uur_valt_tegen, tien_uur_vast, equalizer, prijzen_weg,
    weekend, weekend_geen_zon,
    *VAN_DEN_DAM,
]


def zoek(naam: str) -> Scenario:
    for s in ALLE:
        if s.naam == naam:
            return s
    raise KeyError(naam)
