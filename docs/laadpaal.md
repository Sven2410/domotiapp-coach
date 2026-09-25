# De laadpaal

Uit `CLAUDE.md` gehaald op 24-09-2026, zodat dat bestand kort blijft. De eisen
van de eigenaar en de werkafspraken staan daar en gaan boven alles hier.
Komt er bij een uitgave iets bij over dit onderwerp, schrijf het dan hier.

## Na de eisen: wat er per uitgave bij kwam

**Zonder planning bepaalt de modus: Snel, Continu of Zon** (v0.87.0). De
eigenaar op 23-09-2026, naar het voorbeeld van evcc: "de modus is leidend (snel,
continu of zon), tenzij er een planning ingesteld is. Geen planning, standaard
terug naar zon, of welke voorkeursmodus dan ook." En over de namen: "continu is
wellicht een betere benaming; en PV zon noemen."

- **Een planning wint.** Staat het schema aan, dan rekent hij zoals altijd naar
  de klaar-tijd; de modus doet dan niets. Alleen Snel (snelladen) gaat
  daaroverheen, zoals het al deed.
- **Zon** (`zon-modus`, `zon-wacht` in `_modus_zonder_planning`, planner.py):
  alleen op overschot, vanaf `SURPLUS_SLACK` van de ondergrens van de paal; de
  kaart zegt vanaf hoeveel. Een wolk breekt een lopende beurt niet meteen af
  (`_keep_alive`), dus dan kan er een paar minuten wat van het net bijkomen:
  in `modus-zon-bewolkt` 0,2 van 10,9 kWh. Geen accustand nodig, dus ook geen
  melding om de accustand; een bekende accustand stopt hem wel op zijn doel.
- **Continu** (`continu`): altijd op `continuous_amps` (per paal, standaard 6),
  met meer als de zon meer geeft; nooit boven het plafond. **In de avondpiek van
  een vast contract komt er niets van het net bij** (eis 4): dan is het zon.
- **Goedkoopst**: wat de coach zonder schema altijd deed, de goedkoopste
  bekende uren. Alleen als voorkeur, niet als knop.
- **Voorkeur per paal** bij Apparaten (`charge_mode`, "Zonder planning"). Een
  bestaande paal wordt `goedkoopst` (`_migrate` in storage.py, en de standaard
  in `_DEVICE`), zodat er bij een klant niets stil verandert; een nieuwe paal
  krijgt in het paneel `zon`.
- **Per beurt kiezen op de kaart** (`coach/mode`, `async_mode`, `_modus` in
  coach.py): de knoppen Snel, Continu en Zon, alleen zonder planning; nog een
  keer op de actieve modus gaat terug naar de voorkeur. Onthouden over een
  herstart (`mode` in `sessions`), weg zodra de kabel eruit gaat.
- **Geen tijdlijn in de modus zon of continu**: `plan_ahead` is dan None, want
  een lijst met goedkoopste uren zou iets beloven wat hij niet doet.

Proef 61 in test_planner.py, proef 93 in test_coach.py, scenario's
`modus-zon`, `modus-zon-bewolkt` en `modus-continu` (dynamisch, 8 A: vol om
12:42 op dag één, 3,0 kWh van het net en € 0,90, tegen een dag later en € 0,00
in Goedkoopst), en het formulier en de knoppen in test_rapport.mjs.

**"Vol" is wat de bewoner instelt, en een accustand telt pas als hij bezonken
is** (v0.65.0). De eigenaar op 16-09-2026: "ik wil een optie hebben op de kaart dat ik
kan aangeven tot hoever de bus laadt. Mijne laadt tot 80% namelijk maar ik kan
hem ook op 100% instellen." Twee dingen, en ze horen bij elkaar.

Per auto staat er in Apparaten **Laadt tot (%)** (`target_percent`, 10 tot 100,
standaard 100). Alles wat "vol" betekende rekent nu tot dat doel: `doel_van`,
`doel_bereikt` en `klaar_zin` in planner.py, en daarmee `energy_needed_kwh`,
`worst_case_kwh`, `_uren_met_afbouw` en `_niet_vol` in coach.py. Een doel van
100 is precies wat `FULL_PERCENT` altijd deed, dus wie het veld leeg laat merkt
er niets van. Een procent speling (`DOEL_MARGE`), want een accusensor is nooit
fijner dan dat. **Dit is niet de laadgrens in de auto**: die stuurt de auto,
deze stuurt de coach. Staan ze gelijk, dan weet de coach waar de beurt eindigt
in plaats van het achteraf te merken; staat het doel lager, dan stopt de coach
eerder. Daarvoor moest `NO_WRITE_RULES` een uitzondering krijgen
(`_niets_schrijven` in coach.py): laadt de paal nog, dan is "klaar" een besluit
en geen constatering, en gaat die 0 er wél heen, blijvend (zonder houdbaarheid,
anders loopt hij af en laadt de auto door; in het virtuele huis gaf dat honderd-
veertig wissels en 3,2 kWh van het net op een auto die allang op 80% stond).

**Het verslag noemt de accustand, het net en de zon** (v0.89.0). De bewoner van
de eerste woning op 23-09-2026: "tijdens deze laadsessie is er X kWh geladen,
en is de accu gestegen van A% naar B%. C kWh is afgenomen van het net met een
totaalprijs van € D; E kWh heb je direct verbruikt van je zonopwek."
`_beurt_cijfers` in coach.py, achter het verslag bij "vol" en bij afkoppelen:
"De accu ging van 30 naar 100%. 6,3 kWh kwam van het net voor € 2,40; 9,0 kWh
kwam direct van je zon." Alleen wat bekend is (`soc_begin` in de sessie, `geld`),
en "(geschat)" bij een opgegeven stand. Op de kaart staat onder "Hoe vol is de
auto nu?" een "%" achter het veld, en na een opgave "Sinds je 59% doorgaf is er
3,4 kWh geladen. De coach verwacht dat de auto nu 63% vol is." (`soc_now` in de
stand). Proef 97 in test_coach.py.

**De laadlimiet van de planning is leidend** (v0.96.0). De bewoner van de eerste
woning op 23-09-2026, naar evcc: "de algemene 90 geldt voor snelladen, continu en
zon. Stel je een planning in, dan is de laadlimiet van de planning leidend."
Met als voorbeeld een maandag met een korte rit (50%) en een dinsdag met een
lange (100%). De eigenaar: akkoord. In het schema van een laadpaal staat onder "Uiterlijk klaar om" nu
"Laden tot" (%), bij elke dag hetzelfde en per dag (`target` in `window` en in
`days`, `_WINDOW` in websocket.py, `kentDoel` en `doelUit` in schedule-sheet.js);
leeg is de algemene limiet. `DayWindow.target` en `Window.target` in planner.py:
het doel van de dag waarvan de klaar-tijd geldt, dus zondagavond inpluggen voor
maandag 07:00 is het doel van maandag. In `_read` (coach.py) wint dat doel zolang
de planning geldt, en niet bij snelladen (dat gaat boven de planning); anders de
algemene limiet, dat is "Laden tot" op de kaart of het doel uit het autoprofiel.
De keuzelijst op de kaart blijft de algemene limiet (`target_general`), met eronder
"Deze beurt laadt tot 50%, volgens je planning van maandag" (`target_plan`,
`target_day`). Een boiler kent geen limiet. Proef 67 in test_planner.py, proef 105
in test_coach.py, het veld en de zin in test_rapport.mjs.

**En per beurt op de kaart** (v0.88.0): "Laden tot", met als eerste keuze
het doel uit het autoprofiel en daarna 50 tot 100%. De bewoner van de eerste
woning op 23-09-2026, over evcc: "in de auto een harde max (100%), en in evcc
een gewenste accustand van bijvoorbeeld 80." `coach/target`, `async_target`,
`_doel` in coach.py: gaat in `Car.target_percent`, dus alles wat met het doel
rekent (plan, klaar, verslag) volgt vanzelf; nooit onder de 10%; onthouden over
een herstart (`target` in `sessions`) en weg zodra de kabel eruit gaat. Proef 95.

En de melding wacht op een accustand die bij het einde hoort. Die ochtend zei de
paal om 10:46:21 "completed" terwijl de Ford-app nog 70% toonde; om 10:47:19
werd dat 80. De coach besloot om 10:46:57, tweeëntwintig seconden te vroeg,
herstartte de paal voor niets en stuurde een kritieke melding over 70%.
`_soc_bezonken` deed dit al voor het verslag en doet het nu ook voor het oordeel
"niet vol" (`_klaar_sinds` en `_soc_op` in coach.py, los van de sessie omdat die
een ronde achterloopt). De herstart komt daarmee hooguit `SOC_SETTLE` later; de
auto staat toch stil. Scenario's `laadgrens-80-ingesteld` (de auto stopt op 80%
en dat staat ook in het profiel: geen herstart, geen alarm) en `doel-80` (de auto
kan tot 100, de bewoner wil tot 80: de coach houdt zelf op), `Auto.doel` in het
virtuele huis, proef 53 in test_planner.py, proef 15c en 18 in test_coach.py.

**Een zonuur moet de zon ook echt dragen, en de meter stelt de verwachting bij**
(v0.67.0). De eigenaar op 17-09-2026 om 16:33: "waarom ging hij niet laden om 16 uur
terwijl hij net zei ik ga laden om 16 uur, nu gaat hij om 17 uur. En om 20 uur
gaat hij meer laden maar dan is er geen zon toch? Dan is het nu toch sowieso met
een beetje eigen zon goedkoper?" In zijn eigen besluitenlog:

```
15:43:14  wait-for-sun  Hij wacht op je eigen zon van 16:00
16:00:14  wait-for-sun  Hij wacht op je eigen zon van 17:00
```

De voorspeller zei 1,552 kWh voor het uur van 16:00 en 1,364 voor 17:00; het dak
deed 0,58 kWh en het huis gebruikte 881 W tegen 748 W van het dak, dus de meter
leverde vanaf 15:41 geen seconde terug. Voor het lópende uur zag de coach dat
(daar telt de meter sinds v0.57.0), voor het uur erna geloofde hij de
voorspelling weer, en zo schoof de belofte elk uur op. Drie dingen erbij.

1. **De voorspelling wordt bijgesteld met wat het dak gaf** (`overschot_kwh` in
   planner.py, `Forecast.solar_factor`). De coach legt per ronde de belofte van
   de zonverwachting naast de zonnesensor (`_zon_bijhouden`, `_zon_gemeten` in
   coach.py, `ZON_VENSTER` twee uur, `ZON_MEETTIJD_MIN` een half uur,
   `ZON_MIN_VOORSPELD` 0,5 kWh) en vermenigvuldigt de verwachte opbrengst van
   de uren die komen daarmee; pas dáárna gaat het huisverbruik eraf. **Het dak
   en niet het overschot**, want in de ochtend liggen opbrengst en huisverbruik
   vlak bij elkaar en is de verhouding tussen voorspeld en gemeten overschot
   wilde onzin: op het overschot gemeten kostte dit `dynamisch-zonnig` vijf cent
   op een dag waarop de voorspelling gewoon klopte. **Nooit boven één**: meer
   zon verwachten dan voorspeld is een gok, en dit hoort een correctie te zijn.
   Geldt ook voor de vaatwasser (`programma_kosten`) en voor de klaar-tijdsom
   (`capaciteit_kwh`).
2. **De zon moet een kwart van het uur dragen** (`ZON_AANDEEL`, de keuze van
   17-09-2026). Daarvoor was `SCHIJF_MINIMUM` genoeg: tien wattuur verwacht
   overschot maakte een heel uur tot zonuur en kocht tot de ondergrens van de
   paal bij. In die woning was dat 0,24 kWh zon die 3,90 kWh van het net meesleepte,
   vóór 20:00, terwijl eis 4 juist zegt dat er bij een vast contract voor de
   avond niets van het net bij hoort te komen. **Alleen voor de uren die nog
   komen**: voor het uur waar de coach in zit meet de meter het overschot, en
   een meting is nooit een gok; 0,9 kW echte zon onder de ondergrens van een
   driefasige paal maakt dat uur nog steeds goedkoper dan een avonduur, en dat
   is de som van 30-08-2026.

   Dat laatste is op 17-09-2026 nog een keer tegen het licht gehouden en
   bevestigd. Die middag startte de coach om 16:56 op 230 W gemeten overschot
   en trok hij daarna elf minuten 4,06 kW van het net, vóór 20:00; ik stelde
   voor de kwartregel ook op het lopende uur te zetten. De eigenaar: **"bij een vast
   contract is het wel beter om met overschot te laden."** En dat klopt: een
   teruggeleverde kilowattuur brengt hem € 0,0193 op en een ingekochte kost
   € 0,2417, dus elke gemeten watt overschot maakt dat uur goedkoper dan de
   avond (bij 230 W € 0,2294 tegen € 0,2417, bij 2 kW € 0,1343). Een drempel
   op een meting gooit dat weg. **Geen drempel op het lopende uur, in geen
   enkel contract.**
3. **De kaart zegt het** (`solar_measured_note`, `Plan.solar_note`,
   `plan-ahead-sheet.js`): "Je dak gaf de afgelopen uren X% minder dan de
   zonverwachting zei, dus hij rekent verder met wat hij mat."

**De correctie geldt alleen voor uren van de dag waarop gemeten is**
(`Forecast.solar_day`, v0.67.2). In die woning liep de zin diezelfde avond tussen
17:46 en 20:00 op van "50% minder" naar "86% minder", en dat klopte voor die
uren: de voorspeller zei 769 Wh voor 19:00 en 406 voor 20:00 terwijl het dak op
nul stond. Maar zonder deze grens zou een meting bij zonsondergang ook de uren
van de volgende dag inkrimpen, en dat is geen meting meer maar een
weersvoorspelling. Het gaat mis bij een klaar-tijd die over een dag heen loopt:
zaterdagavond om 20:00 met klaar-tijd maandag 06:00 kwam zondagmiddag op 14% te
staan. Scenario `weekend-voorspelling-mis` (zaterdag bewolkt terwijl helder
voorspeld was, zondag klopt het): oud 23,0 kWh zon en € 10,80, nieuw 37,6 kWh
zon en € 9,35 bij een optimum van € 8,00. Het virtuele huis kent daarvoor
`Zon.wolken_per_dag`.

   In v0.67.0 haalde die zin de tijdlijn niet: `_tijdlijn` in coach.py bouwt de
   lijst voor het paneel veld voor veld op en `solar_note` stond er niet bij,
   terwijl `plan-ahead-sheet.js` er wel naar keek. In de reden op de kaart
   stond hij wel. Gerepareerd in v0.67.1, met een proef die elk veld dat het
   scherm leest langs die lijst houdt (proef 69 in test_coach.py). **Elk nieuw
   veld van `Plan` hoort in die twee lijsten tegelijk.**

**Bij allebei de contracten, en het bijt verschillend.** De eigenaar vroeg ernaar: "je
weet ook dat dit thuis een vast contract is, dus ik weet niet hoe het met een
dynamisch moet." Bij een vast contract is de zonvloer vóór 20:00 de enige deur
naar dat uur (`netto_vanaf`), dus daar sluit regel 2 het uur en wacht hij tot
20:00. Bij een dynamisch contract houdt datzelfde uur gewoon zijn eigen
netschijf tegen de prijs van dat uur; wat verdwijnt is alleen de korting die op
een voorspelling rustte, en dat maakt het goedkoper in plaats van duurder.
Scenario's `zonbelofte-vast` (oud: 15:05 "zon van 16:00", 16:05 "zon van 17:00";
nieuw: meteen "wacht tot 20:00" met de meterzin erbij, € 4,60 = het optimum) en
`zonbelofte-dynamisch` (oud € 3,12 en vol om 02:18, nieuw € 2,99 bij een optimum
van € 2,95). Proef 56 in test_planner.py, proef 69 in test_coach.py.

**Wekken doet de coach op het plafond, want de paal kiest daarop zijn fasen**
(v0.66.0). Thuis op 17-09-2026: om 14:10 stopte de coach om op de zon van 15:00
te wachten, om 14:14 wekte hij met tien ampère, en de Easee begon op één fase.
Te zien aan de verhouding vermogen en stroom: 5,900 A bij 4070 W om 14:05 is
690 V per ampère, 5,875 A bij 1323 W om 14:15 is 225, en 15,498 A bij 10652 W
om 14:26 weer 687. De eigenaar: "hoe kon de laadpaal opeens op één fase gaan laden?
Die 10 A wekstroom, doe dat gewoon 16 A maken." De automatische fasemodus
blijft (eis 3), de coach schrijft nog steeds geen fasemodus, maar hij zorgt dat
de paal bij elke start genoeg aangeboden krijgt om er drie te kiezen.
`WAKE_AMPS` staat dus op 16 en blijft begrensd door `ceiling_amps`. Het
virtuele huis kent daarvoor `Paal.fase_drempel`; scenario `easee-fasekeuze`
(oud: één fase vanaf 08:31, vol pas dinsdag 04:47, € 10,30; nieuw: drie fasen,
vol maandag 22:50, € 9,60 bij een optimum van € 9,59). Een auto die pas boven
het plafond wakker wordt bestaat daarmee niet meer als scenario;
`auto-wordt-niet-wakker` meet nu wat de coach zegt en niet meer of hij wakker
wordt.

**Een halve meting wordt geen laadtempo, en de klaar-tijdregel laat weer los**
(v0.66.0). Dezelfde middag om 14:24:58 herstartte de paal voor snelladen en
meldde "charging" terwijl de stroomsensor nog op 0,152 A van de vorige stand
stond. `_tempo_leren` zag een sessie die al tien minuten liep, rekende 0,152 A
maal 690 V naar 0,1 kW en schreef dat op als het tempo van de bus tussen 0 en
10 procent. De ronde erna stond er 21,41 uur nodig waar het er 1,93 waren, de
klaar-tijdregel sloeg aan, en die bleef staan: 11,2 kW van het net bij 452 W
zon, terwijl `latest_start` 03:24 die nacht zei. Vier dingen erbij:

- **De aanloop hoort bij de paal en niet bij het besluit.** `_since` in coach.py
  begint opnieuw zodra de paal uit `charging` valt en terugkomt (`_laadde`).
  Zolang het aan het besluit hing liep de klok door, want de coach wilde al die
  tijd laden.
- **Twee ronden hetzelfde voordat een band telt** (`_tempo_vorig`,
  `TEMPO_SPELING`), zoals `_eindtijd_vast` bij de vaatwasser en
  `_fasen_stabiel` bij de fasen.
- **Onder `TEMPO_ONDERGRENS` (6 A op één fase, 1,38 kW) is het geen tempo.** Een
  paal levert daar niets onder, dus wat lager gemeten wordt komt van een auto
  die stilstaat. `_tempo_uit` gooit zulke rijen ook bij het lézen weg, want ze
  staan al in de opslag van klanten en een herstart haalt ze er niet uit.
- **`must_finish` vervalt zodra er weer ruim tijd is** (`DEADLINE_RELEASE_HOURS`,
  drie uur bovenop de speling). Grijpen bij een uur, loslaten bij vier: dat
  verschil is er tegen het pendelen van 18-08-2026, maar het vasthouden vroeg
  nooit meer of de reden er nog was.

Proef 53b in test_coach.py, proef 54 in test_planner.py.

**Een accustand die met stappen meldt wordt bijgeteld** (v0.68.0). de eigen Ford
meldt per tien procent, ongeveer elk half uur: op 17-09-2026 stond hij van
21:58:43 tot 22:30:37 op zeventig terwijl de paal 4.072 W leverde, dus 1,90 kWh
aan de stekker en bijna negen procentpunt in de accu. Om 22:26 zei de kaart
"nog 2,2 kWh, vol rond 23:00" terwijl er 0,18 kWh in ging en de bus om 22:29 op
zijn doel stond. De eigenaar: "dat hoeft helemaal niet en is onzin." Het was ook de
bús die stopte en niet de coach, want die wachtte nog tot de sensor 79 zou
zeggen.

`_soc_bijgeteld` in coach.py doet voor een auto mét sensor wat `_typed_soc` al
voor een opgegeven stand deed: de laatste meting plus wat de paal sindsdien
geleverd heeft, uit de eigen meting per ronde (`_eigen`, zie `_geladen`) en niet
uit de teller van de paal, want die stapt zelf ook maar eens per uur. Drie
grenzen, allemaal de veilige kant op:

- **Nooit meer dan één stap van de sensor.** De correctie kan niet groter worden
  dan de onnauwkeurigheid die hij repareert.
- **Die stap wordt geleerd** uit de sprongen die de sensor zelf maakt, en begint
  op `SOC_STAP_START` (één procent). Een sensor die per procent meldt merkt er
  dus niets van; te hoog rekenen laat de coach te vroeg stoppen en dat is de
  richting die ertoe doet. Een sprong boven `SOC_STAP_MAX` telt niet mee.
- **De kale meting blijft apart staan** (`_soc_ruw`), want `_soc_op`,
  `sessie["soc_gezien"]` en daarmee `_soc_bezonken` horen tot rust te komen
  zodra de sénsor stilstaat. Zonder dat ging het verslag van `ford-storing` in
  het virtuele huis meteen bij de storing de deur uit in plaats van te wachten
  tot de auto zich meldde.

Scenario `accustand-per-tien` (`Auto.soc_stap` in het virtuele huis, en
`Regel.nodig_kwh` om het te kunnen meten): over de hele beurt zat "nog te laden"
er gemiddeld 0,63 kWh naast, nu 0,19. Proef 70 in test_coach.py, met de eigen
getallen: 70% plus 1,90 kWh geleverd wordt 78,7%.

**Een auto die nog bijkomt is geen auto die afbouwt** (v0.69.0). In de
klantwoning in de nacht van 18 op 19-09-2026 zakte de coach een paar keer voor de
zekering; om 03:17 naar 8 A, om 03:33:13 bood hij weer 16 A aan, en de Ford
bleef tot 03:44 op 8 A en 5,49 kW hangen. De meter bevestigde het (afname 6,8 kW
tot 03:42, 10,7 kW om 03:44). Om 01:35 duurde dat negen minuten; na een dip van
een minuut kwam hij binnen een halve minuut terug. De eigenaar zag "16 A op maar 5,49
kW". `_tempo_leren` zag een auto die zelf de rem was en schreef 5,52 kW op voor
band 6 en 7,58 voor band 4, terwijl hij daar 10 kW trok. Twee dingen erbij:

- **Na een verhoging van de limiet krijgt de auto `TEMPO_HERSTEL` (een kwartier)**
  voordat wat hij neemt zijn tempo is (`_limiet_vorig`, `_limiet_omhoog`).
- **Een bewaard tempo vervalt zodra de auto het weerlegt** (`_tempo_weerleggen`):
  twee ronden duidelijk meer (`TEMPO_SPELING`) in dezelfde band, bij dezelfde of
  een hogere accustand. Een rij weet sinds v0.69.0 bij welke stand hij gemeten is
  (`soc` in `car_pace`); een oudere telt als gemeten onderin zijn band. Zo gaan
  de rijen die al bij klanten staan er bij de volgende beurt vanzelf uit.

Het virtuele huis kent daarvoor `Auto.bijkomen_min`; scenario's `ford-bijkomen`
(oud leerde {7: 6,9, 9: 6,9} bij een auto die 11 kW kan, nieuw niets) en
`ford-oude-opslag` (oud hield {6: 5,52, 7: 6,9} en voegde band 9 toe, nieuw ruimt
ze op). Proef 71 in test_coach.py. `afbouw-boven-80` leert zijn echte afbouw nog
precies zo.

**Een omvormer die slaapt is geen storing** (v0.69.0). De SolarEdge in de
klantwoning wordt 's nachts onbereikbaar (18-09-2026 om 21:40, zon onder om 20:31), en om
21:51 kwam er een kritieke melding; zo elke nacht. Onder `ZON_SLAAPT_ONDER` (tien
graden zonshoogte, uit `sun.sun`) telt een zonnesensor die niets zegt niet als
stilte (`_zon_slaapt` in coach.py): 's ochtends leverde hij op 17 en 18-09-2026
pas 64 en 55 minuten na zonsopkomst iets. En het paneel toonde de hele nacht een
streepje bij Woning, want verbruik is zon plus net: met de zon onder de horizon is
een onbereikbare omvormer nu 0 W (`readSolar` in data-source.js). Overdag blijft
het een streepje, want dan kan hij best leveren. Zonder `sun.sun` blijft alles
zoals het was. Proef 72 in test_coach.py, vier proeven in test_rapport.mjs.

**Een laaduur op de kaart staat nooit onder de ondergrens van de paal**
(v0.67.3). De eigenaar op 17-09-2026 om 22:10, met 2,5 kWh te gaan: "dit klopt niet,
4 A laden." Het restje werd uitgesmeerd over de vijftig minuten die nog van dat
uur over waren, 2,94 kW, en dat is 4 A; zijn paal trok 5,92 A en 4,08 kW en was
om 22:45 klaar in plaats van om 23:00. De regel die dit sinds 05-09-2026 al
oploste ("nu staat er ineens 2 A, dat is helemaal niet de bedoeling") eist een
vol uur ervóór, en bij het uur waar de coach ín zit ligt dat in het verleden,
dus er bestaat geen schijf van. Een netblok toont nu minstens `MIN_AMPS`, en is
het het laatste laaduur dan staat er "nog X kWh, vol rond HH:MM" bij, waar ook
`expected_done` mee rekent. Zonuren blijven zoals ze waren: daar is de
ondergrens al het antwoord. **Getoetst op het vermogen en niet op de afgeronde
stroom** (v0.67.4): 2,19 kWh over vierendertig minuten is 3,86 kW en dat rondt
af naar 6 A, dus op de stroom getoetst glipte het er later in het uur alsnog
doorheen terwijl het vermogen en "vol rond" nog fout stonden. Proef 57 in
test_planner.py dekt allebei.

**De tijdlijn viel om bij een uur dat hij zelf had gewist** (v0.66.0). De
crash in `_restje_naar_achteren` die op 15-09-2026 gevonden en niet gerepareerd
werd: `sorted(uit)` is een momentopname en de lus wist er zelf uren uit, en een
gewist uur gaf daarna een `KeyError`. Dan stond er niets op de kaart, dertien
keer in één nacht in `warmtepomp-nacht`. Eén regel (`start not in uit`), proef
55 in test_planner.py.

**De tijdlijn zegt waarom een uur leeg is** (v0.66.0). De eigenaar diezelfde dag: "hij
zegt nu 14:00 wachten buiten je tijden, maar dat klopt ook niet." Klopte ook
niet: zijn tijden lopen tot 06:00. Een uur zonder enkele schijf kreeg altijd
"buiten je tijden", ook als het gewoon de avondpiek was of de avondregel van een
vast contract (`netto_vanaf` in `schijven`). `timeline` rekent die grens nu zelf
uit en zegt "de avondpiek, daar komt niets van het net bij" of "geen zon over,
en voor 20:00 geen net". Sinds v0.68.1 ook de derde grens: reiken de prijzen
niet tot de klaar-tijd, dan zegt een leeg uur boven het gemiddelde van de
bekende prijzen "duurder dan gemiddeld, dus hij wacht eerst op de nieuwe
prijzen" (`_gemiddeld_bekend`, dezelfde som als in `schijven`). In de klantwoning
stond op 18-09-2026 de hele vrijdagavond "buiten je tijden" bij een klaar-tijd
op zondag 06:00. Proef 58 in test_planner.py.

**De tijdlijn rekent met dezelfde som als het besluit** (v0.72.0). De eigenaar
op 21-09-2026, met twee schermafdrukken erbij: "die 14 A klopt totaal niet, dat
moet toch gewoon 6 A zijn?" Op de kaart stond bij het lopende uur "14 A, laden
op 9,4 kW" en een kwartier later "16 A, 11,0 kW", terwijl de paal de hele beurt
op 6 A liep (dynamische laadgrens 6 vanaf 14:31:22, gemeten 5,85 tot 5,90 A) en
het besluit ook 6 A zei. De kop beloofde "vol rond 15:00"; het werd 15:32.

De oorzaak: bij gelijke prijzen spreidt `_decide` het laden over alle uren die
er zijn (`easy-pace`), en `timeline` riep gewoon `goedkoopste` aan. Die knapzak
is bij gelijke prijzen onverschillig en propt de vroegste uren vol, dus 4,4 kWh
over de achtentwintig minuten die van dat uur over waren: 9,4 kW, oftewel 14 A.
Twee sommen die hetzelfde hoorden te doen en uit elkaar gelopen waren; de
docstring van `timeline` beloofde het tegenovergestelde.

Nu delen ze de som: `vlakke_prijzen` en `rustig_tempo` in planner.py, gebruikt
door allebei, en `_rustig_spreiden` legt de kilowatturen per uur neer op dat
tempo in plaats van de knapzak te volgen. Het laatste (deel)uur zegt dan
vanzelf "nog X kWh, vol rond HH:MM", want daar valt het tempo onder de
ondergrens van de paal. Een uur dat niets krijgt heet bij gelijke prijzen niet
meer "duurder dan wat hij nodig heeft" (drie uren van € 0,242 naast een uur van
€ 0,242) maar "hij is dan al klaar". Bij verschillende prijzen verandert er
niets: daar is haasten wél iets waard en hoort de knapzak de goedkoopste uren
vol te pakken. Proef 59 in test_planner.py zet de twee sommen naast elkaar;
**die proef ontbrak, en daarom kon dit erin blijven zitten.**

**Het plafond voor de uren die komen is een meting van deze beurt** (v0.61.0).
In de nacht van 09 op 10-09-2026 ging in de klantwoning om het kwartier een
warmtepomp aan op één fase, tot 22 A; de paal kreeg 8 A waar het plan met 16
rekende, en de klaar-tijdregel zag dat pas om 03:01. De eigenaar: "er zit geen
patroon in, en dat kan bij andere woningen ook zo zijn", dus voorspellen mag
niet en een verlaagd plafond aannemen ook niet. Wat wel mag is meten: sinds
het inpluggen telt de coach elke ronde wat er voor de paal overbleef
(`ceiling_amps`, onder de ondergrens telt als nul; vroeg hij het volle
plafond, dan wat er werkelijk liep), en het gemiddelde van de afgelopen drie
uur (`PLAFOND_VENSTER`, `_plafond_gemeten` in coach.py) gaat als
`Charger.expected_amps` naar `structural_ceiling` in planner.py. Daar rekenen
het plan, "uiterlijk beginnen" en de klaar-tijdregel mee. Een rustig huis
meet het volle plafond en merkt er niets van; een huis met een warmtepomp
begint eerder, en de kaart en de reden zeggen erbij dat het een meting is
(`Plan.measured`, `measured_ceiling_note`). Drie uur en niet de hele beurt,
want de kookpiek van de avond hoort niet in de nacht mee te tellen. Na een
herstart begint de meting opnieuw. Scenario's `warmtepomp-nacht` (oud: 85% om
06:00, nieuw: vol om 05:25) en `warmtepomp-uit` (hetzelfde als zonder de
regel); proef 51 in test_planner.py, proef 65 in test_coach.py.

## Een herstart midden in een beurt, en de zekering van de groep (v0.98.0)

De eigenaar op 25-09-2026 om 00:45, bij een auto die laadde terwijl de pop-up "van
plan te laden tussen 01:00 en 06:00" zei: "laadde hij op het juiste moment en is de
visualisatie niet goed, of is de visualisatie wel goed maar het sturen niet?" En
daarna: "onthoudt de coach de accu % die handmatig is ingevuld, werkt hij die
tijdens het laden bij, en weet hij na een herstart alles nog? Repareer alles als
dat nodig is."

Wat er die nacht in de eerste woning gebeurde, uit de eigen geschiedenis van de
coach: om 22:30 "nu doorladen, anders is de auto om 08:00 niet vol; de afgelopen
uren bleef er gemiddeld 12 A over" (de paal hangt op een groep van 3x16 A); om
22:49 een herstart en tien minuten 6 A, "net begonnen met laden"; om 22:59 "wacht
tot 01:00", want na de herstart was de meting weg en rekende hij met 16 A; om
23:20 weer "nu doorladen"; om 00:39 een herstart en weer 6 A. Het sturen volgde
de regels, maar de coach vergat bij elke herstart wat hij over de beurt wist.

**De opgegeven accustand zelf ging goed**: die staat in `car_soc` met de
meterstand van de paal erbij, en `_typed_soc` telt live verder met de teller;
dat overleeft een herstart. Wat er misging en nu gerepareerd is:

1. **Het vaste plafond van de zekeringen.** `zekering_plafond` in planner.py:
   de krapste zekering in de keten van de paal min haar marge, zonder het huis.
   Op een groep van 16 A is dat 14 A. `Charger.zekering_amps` en
   `zekering_naam`, gezet in `_read`; `vast_plafond` is paal, auto en zekering
   samen, en `structural_ceiling` begint daar in plaats van bij wat paal en auto
   kunnen. Daarmee rekent het plan ook direct na een herstart niet meer met
   16 A. `Plan.fuse_name` gaat naar de pop-up: "14 A, meer past er niet onder de
   zekering van de groep Garage".
2. **De beurt over een herstart** (`_sessie_bewaren`, `_hervat_uit`,
   `HERVAT_MAX` een half uur). Bij de beurt in `BeurtenStore` staat nu ook
   `session`: het begin, de meterstand en het ijkpunt, de begin-accustand,
   sinds wanneer de paal laadt, het gemeten plafond van de afgelopen drie uur,
   de verloren tijd en wat er al gemeld is. `_async_beurten_laden` zet het in
   `_hervat`; `_plafond_gemeten` en het zetten van `_since` in `_read` lezen het
   in de eerste ronde, `_bijhouden` neemt het over. Wat er tijdens de herstart
   geladen werd komt er bij de eerste stap van de teller bij (`gat_vullen`):
   het verschil tussen de teller voor de hele beurt en het geld, zodat het
   verslag niet "51,3 kWh geladen" naast "50,6 kWh van het net" zegt.
3. **"Zegt niets" is geen "kabel eruit".** Na een herstart kent de coach de
   laatste status van de paal nog niet (`_laatste_status`), en een paal
   waarvan de integratie nog laadt zegt eerst niets. Dat telde als kabel eruit,
   en dan wiste `_async_forget` de opgegeven accustand en de knoppen, en sloot
   `_bijhouden` de open beurt af. Nu alleen als de paal zelf "disconnected" zegt
   (`_echt_los`).
4. **De sensorwacht onthoudt wat hij meldde** (`sensor_quiet` in de
   instellingen). In de eerste woning kwam "Airco F&R meldt al 10 minuten niets"
   na elke herstart opnieuw als kritieke melding.
5. **De naam van de auto houdt zijn hoofdletters** (`_hoofdletter`):
   `str.capitalize` maakte van "Proefauto zonder HA" in het verslag "Proefauto
   zonder ha".
6. **"Hoe vol is de auto nu?" loopt live mee.** De eigenaar diezelfde nacht:
   "ik wil dat je hoe vol is de auto nu live mee laat lopen en dat de bewoner
   hem kan bijstellen waar nodig." Het veld op de kaart toont na een opgave de
   stand die de coach nu verwacht (`socVeld` in devices.js, uit `soc_now`), en
   niet meer de opgave van toen; elke ronde bij. Wat de bewoner intypt blijft
   staan tot hij het doorgeeft (`dataset.bewerkt`), Escape zet de stand van de
   coach terug, en doorgeven legt een nieuw beginpunt vast bij de meterstand van
   dat moment. Eronder: "Dit loopt mee met wat de paal erin doet: sinds je 32%
   doorgaf is er 12,2 kWh geladen. Zegt de auto iets anders, vul dat in en druk
   op Doorgeven."

Het virtuele huis kent daarvoor groepen (`Scenario.groep_amps`, `groep_last_w`;
de groep in `installation.circuits` met een meter per fase). Scenario
`herstart-groep` (de nacht van de eerste woning: een grote auto op 40%
opgegeven, een groep van 3x16 A met 400 W van de rest van de garage, klaar om
08:00, herstarts om 23:30 en 00:40, en na de tweede zegt de status van de paal
twee minuten niets) tegen `herstart-groep-zonder`:

| | v0.97.0 | v0.98.0 | zonder herstarts |
|---|---|---|---|
| na de herstart van 23:30 | tien minuten 6 A, dan van 23:40 tot 00:22 niets | laadt door op 12 A | laadt door op 12 A |
| vol | 05:33 | 04:44 | 04:44 |
| verslag | "sinds 23:30 ging er 48,3 kWh in, van 44 naar 94%", en "mogelijk staat er een laadgrens in de auto" | "geladen van 22:33 tot 05:03, 51,3 kWh, van 40 naar 100%; 51,4 kWh van het net" | "51,3 kWh; 51,3 van het net" |
| kosten | € 17,26 | € 17,42 | € 17,42 |

Dat v0.97.0 hier goedkoper uitkwam is toeval: zijn gat na de herstart viel in
een duurder uur, en het plan had ruimte genoeg om het daarna nog te halen. De
klaar-tijdregel is dezelfde. Met de controles van v0.98.0 vallen er zes om op
v0.97.0. Proef 68 in test_planner.py, proef 107 in test_coach.py, de kop van de
pop-up in test_rapport.mjs.

## Na de nacht van 25-09-2026 (v0.99.0)

Vier dingen die de nacht met de schaduw liet zien, en de eigenaar: "bouw alles maar."

- **Zo weer verder** (`DOORLADEN_BINNEN`, vijf minuten, in `_keep_alive`). Het vasthouden liep
  om 01:58:57 af, een minuut voor het blok van 02:00; de auto stond die minuut stil en moest
  daarna weer gewekt worden. Begint het volgende laadblok zo, dan laadt hij tot dan door op de
  laagste stand ("Om 02:00 begint het volgende laaduur, dus hij laadt tot dan door"). Daarvoor
  draagt een besluit om te wachten nu het begin van dat blok (`starts_at`, net als de vaatwasser).
- **Een rest van niets is klaar**: onder `SCHIJF_MINIMUM` (tien wattuur) kiest `goedkoopste`
  niets meer, en dan hield hij op 24-09-2026 om 02:48 een minuut 6 A vast met "het is nu niet
  het goedkoopste moment" voor een auto die op zijn doel stond (`_decide`).
- **Afronden en niet afkappen**: "staat op 92%" en "ging naar 93%" stonden in één verslag.
  `klaar_zin` en de meldingen in coach.py ronden nu af, net als `_beurt_cijfers`.
- **Het plafond telt de zekering bij een auto die niets neemt** (`_bijhouden`). Vroeg de coach
  het volle plafond, dan telde wat er liep; bij een auto die klaar is of niets neemt was dat nul,
  en na "klaar" zakte het van 12 naar "gemiddeld 7 A over". Een paal die tegengehouden wordt
  (de Equalizer) telt nog steeds wat er liep.

Proef 69 in test_planner.py, proef 108 in test_coach.py.

## Het merk van de auto, en een Tesla die slaapt

Sinds 22-09-2026 (v0.76.0) heeft een autoprofiel een merk: Ford of Tesla
(`CAR_BRANDS` in devices.js, `brand` in `_CAR` in websocket.py). De eigenaar:
"als je 1 van die selecteert kan je de naam invullen en komen de juiste
invulvelden tevoorschijn." Een nieuwe auto begint dus met alleen de keuzelijst;
een profiel van voor er merken waren (leeg merk, wel een naam of een accu)
houdt zijn velden. Een Ford heeft de velden die er al waren; een Tesla krijgt
er twee dingen bij.

**Een Tesla slaapt als hij niet laadt en meldt dan geen accustand.** De
eigenaar: "daardoor krijg ik telkens een melding van tesla meldt al 10 min
niks." De Tesla-integratie heeft een knop "Wake up"; die staat in het profiel
als `wake_entity`, en de accustand van een auto mét wekknop staat niet in de
sensorwacht (`_sensoren`): slapen is zijn aard, geen storing. Hoe de coach
aan de accustand komt kiest de bewoner (`wake_mode`, `WAKE_MODES`):

- **Handmatig opvragen** (standaard, het zuinigst): op de laadpaalkaart staat
  de knop "Accustand opvragen" (`data-wake` in overview.js,
  `domotiapp_coach/coach/wake`, `async_wake` in coach.py), die op de wekknop
  drukt; de sensor komt daarna vanzelf binnen.
- **Elk uur wakker maken**: staat hij stil en meldt hij niets, dan wekt de
  coach hem hooguit eens per `WEK_INTERVAL` (`_async_auto_wekken`). Met de
  waarschuwing erbij dat elke keer wakker worden accu kost en de auto uit zijn
  diepe slaap houdt.

**Bij het inpluggen wekt hij hem altijd één keer**, in beide standen
(`_kabel_erin`): zonder accustand laadt de coach niet blind (eis 6) en wacht
hij op de bewoner, en dat is precies het moment waarop de auto het zelf kan
zeggen. Daarna niet meer, tot de kabel er weer uit en in gaat. De eigenaar:
"wekken bij inpluggen is goed."

**Een Ford houdt zijn melding, maar pas na een uur.** De eigenaar: "alleen wil
ik wel een melding ontvangen bij de ford als ik niks krijg; bij ford zet dat
maar op een uur polling." De accustand van elke auto zonder wekknop staat dus
gewoon in de sensorwacht, met `SENSOR_STIL_AUTO` (een uur) in plaats van
`SENSOR_STIL` (tien minuten): een auto-integratie haalt zijn stand eens per
zoveel tijd op, en een auto die stilstaat verandert niet. Proef 41 in
test_coach.py meet dat (59 minuten niets, 61 wel), scenario
`klantwoning-accustand-weg` is daarvoor vijf kwartier geworden. Proef 82 in
test_coach.py (de sensorwacht, handmatig nooit uit zichzelf, elk uur op 0, 60
en 120 minuten en niet vaker, niet als de sensor iets zegt, één keer bij het
inpluggen, de knop), en het formulier in test_rapport.mjs. **Nog niet aan een
echte Tesla gehangen.**
