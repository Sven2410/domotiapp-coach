# DomotiApp Coach

Een custom integration voor Home Assistant die apparaten in huis op het
gunstigste moment laat draaien: de laadpaal, de thuisbatterij, de vaatwasser
en de boiler. Hij
wordt via HACS verspreid, dus alleen `custom_components/` gaat mee naar de klant.

De eigenaar beoordeelt en beslist; ik bouw, test, commit, tag en breng uit.

**Deze repo is publiek, en er gaat nooit iets persoonlijks naar GitHub.**
Harde eis van 21-09-2026: "alles moet universeel en niet te linken zijn aan mij
of mijn klanten." Niet in de code, niet in het commentaar, niet in een
commit message, niet in releasenotes, niet in een issue, en niet in een
voorbeeld op het scherm. Dus geen namen van de eigenaar of van klanten, geen
adressen, geen IP-adressen of hostnamen, geen tokens, geen entiteit-id's van
één woning, geen meterstanden en geen schermafdrukken uit een echte
installatie.

Wat uit de praktijk komt hoort er wél in, maar als meting met de datum erbij:
"De eigenaar op 17-09-2026" en "in de klantwoning" zeggen genoeg om te weten
waar een regel vandaan komt. Alles wat herleidbaar is gaat naar de
privénotities ernaast (`../notities/`), die daarvoor bestaan.

**Controleer het vóór elke push**, want daarna staat het er voorgoed:

```
git diff --cached | grep -inE "<achternaam>|<straat>|192\.168|@gmail"
```

Dat één keer overslaan kostte op 21-09-2026 een opruimactie over 36 bestanden
en zeven releasenotes, en de commitgeschiedenis is er nog steeds niet van
schoon.

## Werkafspraken

- **Nederlands** in het gesprek, in commit messages en in releasenotes.
  Codecommentaar in het Engels of Nederlands, zoals het bestand het al doet.
- **Geen gedachtestreepjes** in teksten die de klant leest.
- **Ik doe git zelf**: feature-branch, één commit, `--no-ff` merge naar `main`,
  tag, push, en een GitHub release. HACS kijkt naar releases en niet naar tags,
  dus zonder release krijgt niemand de update.
- **Testen vóór opleveren.** De eigenaar installeert meteen bij zichzelf; alles wat ik
  zelf had kunnen zien kost hem een ronde. Meld eerlijk wat niet getest is.
- **Niets van één installatie in de code.** Elke sensor komt uit de instellingen
  van de klant, nooit uit een naam in de broncode. Proef 42 in `test_coach.py`
  leest de eigen bron en valt om zodra er een entiteitnaam of een merknaam van
  één woning in staat; in een uitleg mag hij wel, want daar is het een bewijsstuk.
  Vraag bij een nieuwe regel altijd welke installatievormen er zijn en dek ze
  allemaal: een gesplitste meter én een meter met een teken, in allebei de
  richtingen, met en zonder zonnepanelen. Proef 43 doet dat voor het huisverbruik.
- **Nooit verzonnen getallen.** Elk getal in de code of op het scherm komt uit
  een meting, uit een instelling van de klant of uit een som die daarop rust.
  Weet de coach iets niet, dan zegt hij dat in plaats van iets aan te nemen.
- **Lees zijn klacht letterlijk.** Hij beschrijft wat hij zag, niet wat er
  technisch misging. Vraag je af wat hij verwáchtte te zien.
- **Koppel alles terug in de chat**, niet alleen de conclusie. De gemeten regels,
  de tijdstippen en de getallen erbij, ook als ze mijn eigen conclusie
  tegenspreken. Draait er een monitor, laat dan zien wat erin staat. Hij
  beoordeelt en beslist, en dat kan alleen met de meting eronder. Gevraagd op
  30-08-2026, nadat ik een monitor aanzette, er zelf uit las en hem alleen de
  uitkomst gaf; diezelfde dag citeerde ik ook een regel van tien minuten oud als
  de stand van nu, en met de hele reeks erbij had hij dat meteen gezien.
- Niets bouwen zonder zijn seintje. Wat er op de lijst staat betekent niet dat
  het aan mag.
- **Meldingen naar de telefoon: per beurt één verslag, plus wat de bewoner
  zelf moet oplossen.** De eigenaar op 06-09-2026: "alleen laden voltooid met een
  kleine samenvatting, en niet telkens onnodig meldingen sturen." Wie wat
  krijgt staat per persoon in het tabje Meldingen (`ontvangers.py`);
  besluiten staan standaard uit, "doet het weer" gaat alleen in de
  geschiedenis (`telefoon=False` bij `_async_tell`).
- **Elke melding is kort, en er staat geen entiteit-id in.** De eigenaar op
  21-09-2026, over "Sinds 14:47 ging er 3,2 kWh in, en toen liep hij al": "ik
  vind dat en toen liep hij al onnodig. Alle meldingen moeten gewoon duidelijk
  en kort zijn." Die bijzin is eruit; "sinds" zegt al dat de coach het begin
  niet zag. En over de sensorwacht, die de hele entiteit-id noemde: "meld zo'n
  sensor niet volledig, zeg gewoon dat er iets mis is met de integratie." De
  naam die de bewoner zelf invulde mag erin, de id gaat naar het log
  (`_LOGGER.warning` in `_async_sensorwacht`). Een bijzin die de bewoner niets
  laat doen en niets laat begrijpen hoort er niet te staan (v0.71.1).

## De eisen van de eigenaar

Vastgelegd op 04-09-2026, in zijn woorden, en hard: elke regel in de coach
hoort hieraan te voldoen en elke nieuwe regel wordt hieraan getoetst. Het
virtuele huis (`tests/test_virtueel.py`) meet ze na.

1. **Zo min mogelijk kosten.** "Als er bespaard kan worden, doe dat." Alle
   manieren om een kilowattuur in de auto te krijgen worden tegen elkaar
   gezet, zon en net, met teruglevering en salderen erin. Bij een vast
   contract is laden op eigen zon goedkoper en hoeft er niet naar een prijs
   gekeken te worden; bij een dynamisch contract telt alles mee.
2. **De klaar-tijd is heilig, en een uur daarvoor is hij klaar.** Het plan
   eindigt een uur vóór de klaar-tijd (`plan_end`), de klaar-tijdregel grijpt
   in zodra er minder dan dat uur over is bovenop wat er nog nodig is, en een
   lopende beurt stopt niet voor een goedkoper uur als er daarna geen uur
   reserve overblijft (`cheap-hour+reserve`).
3. **Geen fasewissel.** Een auto laadt op één fase of op drie, zoals het
   autoprofiel zegt, en de coach wisselt dat nooit: dat beschadigt het relais.
   Hij moduleert van 6 A tot het maximum van de paal, op het aantal fasen dat
   er is. Er staat nergens code die een fasemodus schrijft; dat hoort zo te
   blijven. **De paal zelf wisselt wel**, in de automatische fasemodus van
   een Easee, en die modus blijft: de eigenaar op 06-09-2026, "belangrijk voor
   gastauto's." In de klantwoning koos hij die nacht om 04:17 één fase op een
   driefasig profiel; de Ford trok 16,9 A op een groep van 16 A, de paal
   herstartte op drie fasen en de Ford ging in storing. Sindsdien: laadt de
   paal aantoonbaar op één fase (`_fase_nu` in coach.py, uit de verhouding
   vermogen en stroom, drie ronden stabiel), dan rekent de coach die beurt
   met één fase (`Car.phases_measured`); en trekt de auto meer dan de
   limiet, dan blijft de coach evenveel onder de groep van de paal
   (`circuit_ceiling` in planner.py, met de entiteit `circuit_limit`).
4. **Niets van het net in de avondpiek**, van `EVENING_PEAK_START` (18:00,
   de keuze van 05-09-2026; 17:00 kostte die dag 1,65 euro) tot
   `EVENING_START` (20:00). **Sinds v0.79.0 alleen bij een vast contract**
   (`piek_dicht` in planner.py): bij een dynamisch contract is de avondpiek
   een gewoon uur op zijn eigen prijs, want daar kiest de som hem toch niet
   tenzij hij een keer goedkoop of negatief is. De bewoner van de eerste
   woning op 22-09-2026: "zou geen harde blokkade hoeven zijn als je al met
   laagste prijzen werkt"; de eigenaar: "bouw dat maar." Geldt voor de paal
   (`schijven`, `capaciteit_kwh`, `timeline`, `_keep_alive`), de batterij
   (`_Som.piek`, `_rustig_vermogen`, de negatieve prijs), de boiler
   (`boiler_schijven`) en de vaatwasser (`plan_programma`). Bij een
   vast contract komt er bovendien vóór 20:00 helemaal niets van het net bij
   op de avond die bij de klaar-tijd hoort. Zon blijft altijd beschikbaar,
   want die belast de aansluiting niet. Alleen de klaar-tijdregel en snelladen
   gaan hier overheen.
5. **Het schema van een laadpaal kent alleen "klaar om".** "Niet eerder dan"
   en "uiterlijk starten" zijn er voor een laadpaal uit; de coach kiest zelf
   het goedkoopste moment. Andere apparaten houden alle drie.
6. **Nooit blind laden.** Zonder accustand wacht hij op de bewoner, zonder
   prijzen wacht hij op de prijssensor, allebei met de klaar-tijd als vangnet.
   Reiken de bekende prijzen niet tot een uur vóór de klaar-tijd, dan komt er
   tot ze er zijn alleen zon in: geen geschatte prijzen, geen uur zonder zon
   van het net (`alleen_zon` in planner.py). Een uur mét zon telt wel, ook
   als het dak te weinig geeft om zonder net te laden: dan vult hij aan tot
   de ondergrens van de paal tegen de bekende prijs van dat uur. De eigenaar op
   05-09-2026: "wat zon om 14 uur met een goedkope prijs weegt zwaarder dan
   een iets goedkopere nacht." Met zondag uitgevinkt en klaar-tijd maandag
   06:00 laadt hij dus het hele weekend op zon, en plant hij de nacht zodra
   de prijzen van maandag zondag rond 13:00 binnen zijn. De klaar-tijdregel
   rekent daarbij met wat er fysiek nog in kan (`capaciteit_kwh`), niet met
   wat er aan prijzen bekend is.
7. **Liever iets eerder vol dan niet vol.** De eigenaar op 06-09-2026, na de nacht
   waarin de Ford op 86% in storing bleef staan. Vier dingen horen erbij.
   "Klaar" van de paal is niet "vol": zegt de accustand dat er nog iets in
   moet, dan start de coach de paal één keer opnieuw en gelooft hij "klaar"
   pas als de auto na een kwartier nog niets doet (`_niet_vol`,
   `HERSTART_WACHT` in coach.py); dat geldt ook voor een auto die niet in
   Home Assistant zit, want na een opgegeven stand telt de coach zelf verder
   met de teller van de paal. Zo'n geschatte stand krijgt een uur extra in
   de klaar-tijdsom (`Car.soc_estimated`, `ESTIMATED_SOC_EXTRA_HOURS`). Een
   auto die bovenin gas terugneemt wordt gemeten terwijl hij zelf de rem is,
   per band van tien procent, en de volgende beurt rekent daarmee
   (`car_pace` in de instellingen, `_tempo_leren` in coach.py,
   `_uren_met_afbouw` in planner.py). En is de klaar-tijd voorbij terwijl de
   auto niet vol is, dan laadt hij op vol vermogen door (`overdue`).

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

**Een auto die nog bijkomt is geen auto die afbouwt** (v0.69.0). Bij Van den
Dam in de nacht van 18 op 19-09-2026 zakte de coach een paar keer voor de
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

**Een omvormer die slaapt is geen storing** (v0.69.0). De SolarEdge van Van den
Dam wordt 's nachts onbereikbaar (18-09-2026 om 21:40, zon onder om 20:31), en om
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

**De apparaatlijst noemt alleen wat de coach werkelijk kan** (v0.70.0). De eigenaar op
19-09-2026: bij Apparaten gingen de thuisbatterij, de warmtepomp, de wasmachine,
de droger en de zwembadpomp eruit, en bij een laadpaal het merk "overig". Over
blijven: laadpaal, boiler, vaatwasser, airco en overig. (De thuisbatterij kwam
in v0.73.0 terug, en nu omdat de coach hem werkelijk stuurt.) Hetzelfde argument als
bij de merken van 04-09-2026, een regel in een lijst leest als een belofte. Wat
er niet in staat past onder "overig" met een eigen naam, en wordt gemeten zoals
elk apparaat met een vermogenssensor.

Twee lijsten hangen eraan vast en zijn meegekrompen: `PROGRAM_TYPES` en
`RELEASE_TYPES` in devices.js waren `vaatwasser, wasmachine, droger` en zijn nu
alleen de vaatwasser, net als `PROGRAMMA_TYPES` in const.py altijd al was.

**Wat er bij een klant al stond verandert niet stil.** Een keuzelijst zonder de
opgeslagen waarde toont zijn eerste regel, en bij de volgende opslag zou een
zwembadpomp een laadpaal zijn. `_migrate` in storage.py maakt er daarom
"overig" van, met de oude typenaam als naam wanneer het apparaat er zelf geen
had (`VERVALLEN_TYPES` in const.py); een laadpaal van het merk "overig" blijft
een laadpaal die gemeten wordt, maar verliest zijn merk en de vink "mag sturen",
want sturen kon de coach hem nooit. Autoprofielen en het schema blijven staan.
Proef 24b in test_coach.py.


## De feedback van de eerste woning, 22-09-2026 (v0.77.0)

Vijf punten van de bewoner van de eerste woning, doorgestuurd door de eigenaar,
allemaal gebouwd in v0.77.0.

1. **Zelfvoorzienend in Historie**, "zoals in het native HA Energie
   dashboard": welk deel van het verbruik niet van het net kwam, `1 - bought /
   used` (`totals.selfSufficient` in views/history.js), naast "Zelf gebruikt"
   (welk deel van de opwek zelf gebruikt is), ook per balk en in de tegels van
   het rapport.
2. **De batterijzin loopt tot morgenvroeg en sluit af met een conclusie.**
   "De meeste consumenten hebben een accu om de nacht te overbruggen." `OCHTEND_UUR`
   (zeven uur), `nachtbalans` en `balans_kwh` in batterij.py: zon, huis en wat er
   bruikbaar in de batterij zit tot morgenvroeg, met het rendement erin ("goed
   voor X kWh na het verlies"), en dan "Je houdt naar verwachting X kWh over in
   je accu" of "Je komt naar verwachting X kWh tekort om de nacht te overbruggen;
   hij laadt bij als de stroom goedkoop genoeg is." De kaart maakt de conclusie
   groen of oranje (`balance_kwh` in de stand, `.says-plan.good/.warn` in
   overview.js). Proef 12 in test_batterij.py.
3. **Meerdere omvormers.** "Steeds meer consumenten hebben meerdere omvormers."
   `sources.solar_extra` (vermogens) en `sources.meters.solar_total_extra`
   (kWh-tellers), lijsten naast de eerste; bij Instellingen "Nog een omvormer"
   en "Nog een opwekteller" (`paintExtra_` in views/settings.js). `zonsensoren`
   in coach.py is de ene lijst voor alle vier de lezers (de sensorwacht, met per
   omvormer een eigen naam; de slapende-omvormer-uitzondering; het huisverbruik
   uit de kwartieropslag; `_zon_bijhouden`), en `_zon_w` telt op maar wordt
   onbekend zodra één omvormer zwijgt: een halve meting zou het dak naar beneden
   rekenen. Het archief volgt ze (`_wat_volgen`). In het paneel `solarEntities`
   en `readSolarAll` in data-source.js (op het scherm telt wat er is), de
   tellers in `meters_()` en "Zon 2", "Zon 3" in het rapport. Proef 83 in
   test_coach.py, test_archive.py en test_rapport.mjs.
4. **Gasprijs en eerdere contracten.** "Gascontract 1: van-tot + prijs,
   gascontract 2: van-tot + prijs; dat kun je ook doen bij de stroomprijzen."
   `contract.gas_price` (euro per m³) en `contract.periods` (van, tot, all-in
   stroomprijs, terugleververgoeding, gasprijs; een leeg veld valt terug op het
   huidige contract). `contractAt(contract, dag)` in data-source.js kiest per
   dag het contract van toen; Historie en het rapport rekenen daar per bucket
   mee (`priceAt`, `feedInAt`, `gasAt` in `paintMoney_` en `reportData_`), met
   de tegel "Gas gekocht voor" zodra er een gasprijs is. **Alleen voor
   terugkijken**: wat de coach nu doet rekent met het huidige contract
   (`_tariff` in coach.py is ongewijzigd), en de laadbeurten in `BeurtenStore`
   hebben hun prijzen al bevroren. Formulier bij Installatie onder Contract:
   "Gasprijs" en "Eerdere contracten" (`paintPeriods_`).
5. **Een kort rapport naast het uitgebreide.** "Omdat ie nu zó uitgebreid is
   downloaden consumenten m straks niet meer." Twee knoppen in Historie: "Kort
   rapport" (`#report-short`, `reportData_(true)`: de tegels van energie, geld
   en bespaard, het verloop en per apparaat; geen regels per beurt, geen
   vermogen, geen "Alle cijfers", kop "Beknopt") en "Uitgebreid rapport". Het
   rapport zelf (report.js) is niet veranderd: elk deel stond er al alleen als er
   gegevens voor zijn.

**Morgenvroeg nooit meer over dan er in de accu past** (v0.86.1). De bewoner
van de eerste woning op 23-09-2026, bij "je houdt naar verwachting 15,9 kWh over
in je accu" onder een accu van 14,6 kWh: "hoe kan je ooit 16 kWh in een accu
hebben van 14 kWh?" `balans_kwh` telde alle zon tot morgenvroeg op bij wat erin
zat (10,8 x 0,736 + 12,4 - 4,5). Nu rekent `nachtverloop` in batterij.py het uur
voor uur: overschot gaat erin tot `soc_max` en de rest naar het net, het huis
haalt eruit met het rendement tot de ondergrens, en wat er dan ontbreekt is
tekort (dat komt 's ochtends niet terug met de zon). De zin noemt de zon die
er niet in past. Handelen rekent met dezelfde balans, en handelt daardoor nu
met minder. Proef 31 in test_batterij.py.

**Het plan op de kaart, en "Nu vol laden"** (v0.78.0). De eigenaar op
22-09-2026: "ik kan nu niet zien wat de coach van plan is met de batterij; want
eigenlijk wil je nu dat de batterij handmatig vol wordt geladen." Twee dingen.
`planRegels` in battery.js voegt de uren van het plan (`hours` in de stand)
samen per stand tot regels als "18:00 tot 21:00: nul op de meter, van 80 naar
60%" en "21:00 tot 23:00: laden van het net, van 60 naar 90%, 4,2 kWh tegen
€ 0,130", onder het kopje "Plan" op de kaart. En de knop "Nu vol laden": dezelfde
knop en hetzelfde commando als snelladen bij de paal (`coach/boost`,
`self._boost`); in `_one_batterij` wordt het besluit dan `MAX_LADEN` op het
laadvermogen tot de laadgrens (`vol-laden`), ook in de avondpiek, en zodra hij
vol is gaat de knop vanzelf uit met een regel in de geschiedenis. Proef 84 in
test_coach.py, `planRegels` in test_rapport.mjs.

**De tip bovenaan noemt nooit wat de coach zelf stuurt of plant, en als de
batterij handelt zegt hij "alles uit"** (v0.79.0). De eigenaar op 22-09-2026,
bij een kaart die "gebruik je overschot, zet de vaatwasser of de Anker aan"
zei terwijl de batterij 2,3 kW aan het net verkocht: "je mag nooit de batterij
adviseren om aan te zetten, dat doet de coach zelf. Ook met een laadpaal die
stuurbaar is. Adviseer alleen apparaten die de coach niet aanstuurt."
`apparatenZin` in devices.js laat de thuisbatterij, elke paal die de coach kan
sturen (`canSteer`) en elk programma-apparaat weg; wat overblijft zit op een
meetstekker. En `advise` in overview.js krijgt de gestuurde batterij mee
(`batterijNu_`): handelt hij, dan is het advies in de woorden van de bewoner
van de eerste woning ("je hebt toegestaan om te handelen met je batterij; de
spread is groot genoeg en je batterij is vol genoeg om de nacht door te komen;
de komende uren ontlaadt hij op X W; je kunt nog Y kWh ontladen en alsnog de
nacht doorkomen", met `balance_kwh`), plus "gebruik nu zo min mogelijk stroom:
stel de wasmachine uit tot de prijs weer zakt", want "in dit geval had ie alle
apparaten juist uit moeten schakelen". Het huis gaat voor ("nul op de meter
heeft prioriteit, het overschot verhandelen"). En wat de batterij afgeeft telt
niet als overschot voor de tip (`echtOverschot`). Proeven in test_rapport.mjs.
De bewoner wees er ook op dat het handelen vanaf 01-01-2027 verandert doordat
bij teruglevering de btw vervalt; dat zit al in `NETTING_ENDS` en in de
terugleverprijs uit de kale marktprijs.

**Het plan van de batterij in een pop-up** (v0.85.0). De eigenaar op
23-09-2026: "ik wil het plan van de accu net als de laadpaal hebben, zo'n
pop-up; nu is de kaart best groot en onoverzichtelijk." De knop "Wat gaat hij
doen" staat nu ook op de batterijkaart zodra er uren in het plan staan, en
opent dezelfde pop-up als bij de paal (`plan-ahead-sheet.js`, tak
`paintAccu_`): bovenaan Accu nu, Morgenvroeg (`balance_kwh`), Van het net en
wat een kWh erin straks waard is; daaronder per uur de tijd, de prijs, de
accustand aan het eind van het uur en wat hij doet, met laden van het net in
groen (`batterijVooruit` in battery.js). Van de kaart zijn "Een kWh erin is
straks waard" en het plan per stand af; van de nachtzin blijft daar alleen
de conclusie (`nachtConclusie`), de hele zin staat onderaan de pop-up.
Proeven in test_rapport.mjs.

**De prijs per uur als staafjes in die pop-up** (v0.86.0), bij de paal en bij
de batterij. De bewoner van de eerste woning op 23-09-2026, over evcc: "met
groene balkjes laat hij precies zien welke (goedkope) uren hij gaat laden, en
wat de gemiddelde prijs wordt; zo heb je als gebruiker een visuele check." De
eigenaar: "ook voor de batterij." `prijsgrafiek.js`: `prijsBalken` rekent (een
staafje per blok, een negatieve prijs onder de nullijn, een tijd onder elk
derde hele uur), `prijsSvg` en `prijsLabels` tekenen, en `paintPrijs_` in
`plan-ahead-sheet.js` zet het boven de uren. Groen is bij de paal `charging`,
bij de batterij `grid_kwh`; het gemiddelde is gewogen naar de kWh **van het
net** (bij de paal `kwh - solar_kwh`), dus een laaduur op zon trekt het niet
omlaag. Bij een vast contract geen grafiek. Proeven in test_rapport.mjs.

**Vakantiestand, handelen met wat de nacht overhoudt, en iets anders dat
stuurt** (v0.80.0, allemaal 22-09-2026).

- **Vakantiestand** (`battery.holiday`, `holiday_max_percent`, standaard 50):
  de bewoner van de eerste woning, "met name in de zomer met veel opwek en
  minimaal verbruik moet de accu regelmatig leeggetrokken worden; slecht voor
  de accucellen als ze te lang op 100% blijven staan." `_vakantie` in coach.py
  verlaagt `Batterij.soc_max` voor de som en de regelaar; de laadgrens van de
  batterij zelf blijft met rust, en de wekelijkse volle beurt vervalt zolang
  de stand aanstaat. Boven de grens gaat er geen zon in, wat erboven zit gaat
  naar het huis of, met handelen, naar het net. Proef 85 in test_coach.py.
- **Handelen alleen met wat er boven de nacht uitkomt** (`balans_kwh` in
  `plan_batterij`): de eigenaar, "nul op de meter heeft prioriteit, het
  overschot verhandelen met hoge tarieven." De som zelf verkocht alles zodra
  terugkopen 's nachts goedkoper was. Proef 11 in test_batterij.py.
- **Iets anders stuurt de batterij** (`VREEMD_RONDEN`, `VREEMD_PAUZE` in
  coach.py): staat de bedrijfsmodus twee ronden op iets anders dan de coach
  zette, dan laat hij los zónder zelf nog iets te schrijven (een 0 W zou de
  ander overschrijven), zegt het één keer op de telefoon, en probeert het na
  een uur opnieuw; de kaart zegt `foreign`. In de eerste woning nam evcc op
  22-09-2026 om 18:17 de Anker over terwijl de coach op voorstellen stond;
  de coach zei toen keurig "zou op nul staan, maar de coach stuurt nu niet",
  en evcc verkocht van 81% naar 19% op 2,5 tot 3,5 kW tot 21:15. Proef 86.
- **Uit een artikel over het einde van het salderen** dat de eigenaar op
  22-09-2026 doorstuurde: `dynamic.feed_in_bonus`, wat de leverancier bovenop
  de marktprijs betaalt per teruggeleverde kWh (het artikel noemt Zonneplan,
  Frank Energie en ANWB 2 cent, Tibber niets, Next Energy 2,19 cent eraf; mag
  negatief), in `_prices`, `_async_terugrekenen` en `tariff()`; bij een vast
  contract de zin dat de vergoeding zonder salderen ongeveer een kwart cent
  is; en de tip "De stroomprijs is negatief" (573 uur in 2025 volgens dat
  artikel): terugleveren kost dan geld, zet aan wat toch moet draaien. Proef
  87 in test_coach.py, de tip in test_rapport.mjs. Niet overgenomen: de btw op
  teruglevering na 2027, want of die er voor een particulier bij komt staat
  niet vast, en de coach rekent niet met wat niet vaststaat.

**Water, de lekmelding, nu leegladen, en de accu die geen kans is** (v0.81.0,
de laatste punten van de eerste woning op 22-09-2026).

- **Water** naast gas: `sources.meters.water_enabled`, `water` (de teller in
  m³, bij de eerste woning de HomeWizard Watermeter) en `water_flow` (L/min,
  optioneel, voor de lekmelding); `contract.water_price` en `water_price` in
  de eerdere contracten (`contractAt` geeft `water`); bij Instellingen onder
  Meterstanden, bij Installatie onder Contract. In Historie een eigen kaart
  (`paintVolume_`, dezelfde tekening als gas), de tegel "Water gekocht voor",
  en in het rapport de kolom en de tegels. "Water toevoegen, incl prijs, dan
  is je nutsrapport compleet."
- **Lekkage of abnormaal verbruik** (`notifications.usage_alert`,
  `_async_verbruikswacht` in coach.py, het blok bij Meldingen). Twee tekenen:
  water dat langer dan `water_flow_minutes` (twee uur) onafgebroken loopt
  volgens de debietsensor, één melding per keer; en een dag die meer dan
  `factor` (drie) keer de mediaan van de dagen ervoor vroeg, na `min_days`
  gemeten dagen, één melding per dag. Het dagverbruik komt uit de tellers
  zelf: de coach bewaart per meter de stand waarmee de dag begon
  (`usage_start`) en schrijft bij de eerste ronde van een nieuwe dag het
  verschil weg (`usage_days`, hooguit dertig dagen per meter). Lijsten, want
  `_prune` laat lijsten met rust. Proef 89 in test_coach.py.
- **Nu leegladen tot X%** (`coach/drain`, `async_drain`, `_drain`, regel
  `leeg-laden`): naast "Nu vol laden" een knop met een veld voor de accustand;
  de batterij levert dan aan het net op zijn ontlaadvermogen tot die stand,
  nooit onder zijn eigen ondergrens, niet zolang de paal laadt, en daarna
  weer het plan. "Nu maximaal ontladen tot 50%, daarna terug naar normale
  modus." Onthouden over een herstart (`drain_to` in `sessions`). Proef 88.
- **Wat de accu afgeeft is nooit een kans**, wie hem ook stuurt: `advise`
  trekt de gemeten afgifte van elke thuisbatterij (`r.devices`) van de
  teruglevering af. Om 23:01 zei de kaart "gebruik je overschot, 1,73 kW"
  terwijl de accu die 1,73 kW afgaf. En het label van de zwaarst belaste fase
  krijgt geen dubbele haakjes meer bij een groep.
- **Historie opent op vandaag** (`period_` in history.js). De eigenaar om
  23:12: "niet logisch, want vaak wil je even kijken wat er vandaag is
  gedaan; dag is het eerste bolletje van de rij, terwijl standaard de tweede
  geselecteerd wordt." Een rij die op de tweede knop opent leest als een
  fout. Proef in test_rapport.mjs leest het uit de bron van de constructor.

**Gemeten in de eerste woning op 22-09-2026 's avonds, vier sturingen naast
elkaar** (uit de toestanden-logger): de coach in een rustig huis 4
opdrachten per uur en 93% van de P1-metingen binnen 50 W, zo goed als
Omnibattery; bij een last die elke 10 tot 60 s aan en uit gaat 144
opdrachten per uur, 15% binnen 50 W en 0,69 kWh van het net in drie kwartier,
terwijl de Anker in eigen verbruik dezelfde last met 89% binnen 50 W en 0,13
kWh in anderhalf uur opving. Een lus via Home Assistant (meter per 5 s,
batterij na 5 s, bevestiging tot 15 s) verliest van de lus in de batterij
zelf. Voorstel aan de eigenaar, nog niet gebouwd: laat een batterij met een
eigen meter nul op de meter zelf doen (eigen verbruik) en laat de coach alleen
de uitzonderingen schakelen. evcc verkocht die avond 6,2 kWh van 81% naar 19%
zonder aan de nacht te denken.

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

## Groepen met een eigen zekering

Sinds 22-09-2026 (v0.75.0) kent de coach onderverdeelkasten, na de vraag van
de bewoner van de eerste woning: een meterkast met 3x25 A achter de P1, en in
de garage een onderverdeelkast van 3x16 A met een eigen kWh-meter, waar de
laadpaal en de thuisbatterij aan hangen. "Voor de load balancing cruciaal,
aangezien de laadpaal aan de 3x16 A hangt, niet aan de 3x25 A." Hij had het
vermogen van fase 2 en 3 al uit de garagemeter gehaald en fase 1 uit de P1, als
noodgreep. Zoals de circuits van evcc, die hij als voorbeeld stuurde: een naam,
een zekering, een meter, en een groep erboven.

**Wat er staat.** `installation.circuits` in de instellingen (const.py,
`_CIRCUIT` in websocket.py): per groep `id`, `name`, `fuse_amps`, `phases` (1
of 3), `parent` (het id van de groep erboven, "" is de hoofdaansluiting) en
`sensors` per fase met `current`, `power` en `voltage`, precies als
`sources.phases`. Een apparaat wijst met `circuit` naar zijn groep. Op het
tabblad Installatie staat het blok "Groepen met een eigen zekering"
(`paintCircuits_`, `circuitHtml_` in views/installation.js); bij Apparaten
krijgt elk apparaat "Hangt op groep" zodra er groepen zijn (views/devices.js).

**Elke zekering telt, en de krapste wint.** `Circuit` in planner.py, en
`Grid.circuits`: de groepen waar déze paal aan hangt, van onder naar boven.
`ruimten` maakt per zekering dezelfde som die er al was voor de
hoofdaansluiting: de zwaarste fase min wat daarvan van de paal zelf is, de
zekering min dat huis min de marge (`fuse_margin_van`) min wat er deze ronde
al aan een ander laadpunt onder dezelfde zekering is toegezegd. `ceiling_amps`,
`nood_ruimte` en `fuse_limited` lopen over die lijst. Een groep zonder meter
heeft geen huis: daar telt alleen de toezegging. De zin op de kaart noemt de
groep (`knelpunt`, `zekering_van`, `_aansluiting`): "De groep Garage is te
zwaar belast om te laden", en bij snelladen "meer past er nu niet onder de
zekering van de groep Garage", want "onder je zekering" zegt bij 25 A niets
over een garage van 16.

In coach.py: `_groepen_keten` (de keten van een apparaat, een kring of een
onbekende groep eindigt hem), `_fase_amps` (dezelfde lezing als de
hoofdaansluiting, met vasthouden en gladstrijken), en de toezeggingen per
zekering: `vergeven` in de ronde is een dict op id, "" voor de
hoofdaansluiting, en een toezegging aan een paal telt onder elke zekering in
zijn keten (`_groep_sleutels`). De batterij krijgt in `_laadruimte_w` de
krapste van alle zekeringen in haar keten. De snelle zekeringcontrole kent
per stroomsensor de grens van zijn eigen zekering (`_urgent_above` is een
dict): een garage van 16 A wekt de coach al bij 14 A. De sensorwacht noemt
"de stroommeting van fase L1 van de groep Garage". `async_current_load` in
monitor.py en `loadOf` in data-source.js kijken naar de zwaarst belaste
zekering als aandeel van haar eigen zekering, en het label zegt welke: "L1
(Garage)"; de kaart met de belasting per fase toont onder de hoofdaansluiting
elke groep met haar eigen zekering (`readCircuits`, `updatePhases_`).

Proef 60 in test_planner.py (16 - 3 - 2 = 11 A; de eigen stroom van de paal
telt op de groep niet als huis; een groep zonder meter; de zinnen), proef 81
in test_coach.py (de keten, de toezeggingen, de batterij op 2760 W, de grenzen
14 en 23 A, de lastwaarschuwing op 75% van de garage), en in test_rapport.mjs
het blok op het scherm en de belasting per groep. **Nog niet aan een echte
onderverdeelkast beproefd**; de eerste woning is de eerste.

## De Alfen-laadpaal

Sinds 23-09-2026 (v0.83.0) is er een tweede paalmerk naast Easee, na de eigen
"ik wil alfen bouwen; check zijn integratie en kijk wat je nodig hebt net als
bij easee." En meteen erachteraan: "we hebben natuurlijk een wekstroom etc
maar ik zou niet weten wat er bij alfen moet gebeuren, dus dat moeten we
testen en checken." **Elke wijziging aan de paalsturing wordt sindsdien voor
allebei gebouwd en beproefd.**

**Wat er bij Alfen anders is**, gelezen uit de integratie `alfen_modbus`
(HACS, Modbus TCP, in de eerste woning aan een Eve Single Pro-line met
firmware 7.4) en uit hoe evcc dezelfde paal stuurt. Drie dingen, alle drie in
`CHARGER_CONTROL["alfen"]` in const.py:

1. **De limiet is een number-entiteit en er is geen woord.** De maximale
   stroomlimiet van de socket (0 tot 32 A) gaat er met `number.set_value` in
   (`_limit` in coach.py, `_stuuradres` kiest tussen het apparaat-id van
   Easee en de limiet-entiteit van Alfen). Starten en stoppen bestaan niet:
   een limiet boven de ondergrens ís de start, een 0 is de pauze (`_command`
   doet niets zonder `command_service`). De wekstroom van 16 A gaat er dus
   gewoon als getal in.
2. **De paal vergeet zijn limiet.** Alfen heeft een "Modbus slave max current
   valid time" (register 1209/1210; in de eerste woning telde de sensor
   "geldigheidsduur maximale stroom" af vanaf ongeveer 300 s); loopt die af
   zonder nieuwe waarde, dan valt de paal terug op zijn veilige stroom bij
   actieve load balancing (daar 16 A). De coach schrijft de limiet daarom
   **elke ronde opnieuw**, ook als het besluit niet verandert (`refresh` in
   de tabel, `_ververst` naast de dode band in `_one`); evcc doet hetzelfde,
   elke 25 seconden. De keerzijde: valt de coach weg met een 0 erin, dan
   laadt de auto na die tijd op de veilige stroom door. Bij Easee is dat
   precies andersom (een 0 zonder houdbaarheid blijft staan), en dat is geen
   keuze maar hoe de twee palen gebouwd zijn.
3. **Er is geen statussensor.** De coach leest "auto aangesloten", "auto
   laadt" en de modus 3-toestand uit IEC 61851 (A geen auto, B1 aangesloten
   zonder aanbod, B2 aangesloten met aanbod maar de auto neemt niets, C2 aan
   het laden, E en F niet beschikbaar of storing) en maakt daar in
   `_status_afgeleid` de woorden van die de rest van de coach al kent:
   disconnected, charging, awaiting_start, ready_to_charge. "Completed" zegt
   een Alfen nooit; een auto die `HERSTART_WACHT` lang aanbod krijgt en niets
   neemt (B2 met een limiet boven de ondergrens) wordt dat, want dat is wat
   "klaar" bij een Easee ook betekent.

De velden staan in `CHARGER_BRANDS` in devices.js (`limit`, `connected`,
`charging`, `mode3`, `max_limit`, `dynamic_limit` als de teruggelezen
"maximale stroom", `current` als stroom L1); geen `device` en geen `service`,
dus geen handmatige knoppen, en `canSteer` telt hem gewoon mee. De
sensorwacht kent de kabelmelding, de laadmelding en de stroomlimiet
(`_sensoren`), en een wissel van "auto aangesloten" of "auto laadt" wekt de
coach meteen (`_watch`). `tools/toestanden.py` en `tools/live.py` kennen de
`translation_key`s van alfen_modbus.

**En de 0 blijft komen zolang er een auto hangt, ook bij "klaar".** Het
virtuele huis haalde dit er meteen uit: na "complete" schrijft de coach bij
een Easee niets meer (`_niets_schrijven`, zodat een blijvende 0 de volgende
auto niet in de weg zit), en aan een Alfen viel de paal daardoor vijf minuten
na het doel terug op 16 A. Bij een volle auto is dat onschuldig, bij een doel
van 80% laadt hij door. `_pause` schrijft bij een `refresh`-paal de 0 dus
elke ronde zolang `charger.connected`; zonder auto schrijft hij niets, en dan
is de veilige stroom precies wat de volgende auto hoort te krijgen.

Het virtuele huis kent `Paal(merk="alfen")`: een number zonder houdbaarheid,
geen startwoord, een paal die na `geldig_s` terugvalt op `veilig_amps` (geteld
in `Verloop.paal_terugvallen`, hoort nul te zijn), en de drie statussensoren.
Scenario's `alfen-vast-zonnig`, `alfen-dynamisch-zonnig` en `alfen-doel-80`:
dezelfde kilowatturen en kosten als aan een Easee, geen Easee-dienst, nooit
een gat van meer dan een minuut tussen twee schrijfopdrachten, en nooit een
terugval. Proef 90 in
test_coach.py (de wekstroom als getal, elke ronde opnieuw terwijl een Easee
de tweede ronde niets krijgt, de afgeleide status in alle vier de toestanden,
de sensorwacht), en de merkproef in test_rapport.mjs.

**Nog nooit aan een echte Alfen gestuurd.** Wat er in het echt gemeten moet
worden, in de eerste woning, met de toestanden-logger erbij (`plus=alfen`):

- Welke modus 3-toestand een gepauzeerde paal met een auto eraan meldt (B1 of
  E), en of de auto daarna weer wakker wordt van een limiet van 16 A. In de
  eerste woning stond de paal zonder auto en met 0 A op "E".
- Of de number de nieuwe waarde binnen `CONFIRM_SECONDS` terugleest, en of de
  sensor "maximale stroom" hem volgt (`dynamic_limit`).
- Hoe lang de geldigheidsduur in die paal staat. Staat hij onder twee ronden,
  dan valt de paal tussen twee ronden terug; zet hem dan op minstens 180 s.
- Of de Tesla op één of drie fasen begint en of `_fase_nu` dat uit vermogen
  en stroom L1 goed ziet.
- Wat "auto aangesloten" en "auto laadt" doen bij een auto die zelf stopt
  (laadgrens in de auto) tegenover een auto die vol is.

In de eerste woning stuurt evcc op dit moment de Alfen; nooit allebei tegelijk,
net als bij de batterij (zie `VREEMD_RONDEN`).

## De vaatwasser

Sinds 06-09-2026 stuurt de coach ook een vaatwasser (Home Connect), na de eigen
"omdat de bus vol zit gaan we de laadpaal even parkeren en nu verder met de
vaatwasser sturing." Eerst alleen de vaatwasser (`PROGRAMMA_TYPES` in
coach.py); de wasmachine en de droger komen erbij als dit werkt.

Een programma-apparaat start één keer en draait dan af, dus de enige vraag
is wanneer. `plan_programma` in planner.py zet elk startmoment tussen nu en
de klaar-tijd tegen elkaar (per kwartier), met de prijs per uur en wat er
dan aan eigen zon over is, en kiest het goedkoopste; de avondpiek blijft
dicht, en zonder bekende prijzen wordt er niet geraden. De duur en het
verbruik komen uit `PROGRAMMAS`, dezelfde tabel als `DISHWASHER_PROGRAMS`
in devices.js (opgaven van de fabrikant; `test_rapport.mjs` legt ze naast
elkaar). Eis 2 geldt hier als een half uur speling (`PROGRAMMA_SPELING`).

In coach.py: `_one_programma` leest status, programma en deur, drukt op de
startknop (`_async_druk`, een button-entiteit), wacht drie minuten op "run"
en zegt het als dat niet komt (starten op afstand uit, deur open), probeert
één keer opnieuw, telt kWh en kosten mee terwijl hij draait
(`_programma_tellen`, met dezelfde maat als een laadbeurt: wat meteen
starten bij het vrijgeven met alles van het net gekost had), en meldt één
keer dat hij klaar is
(`_async_programma_klaar`), schrijft de beurt in `BeurtenStore` zodat hij
onder Bespaard staat, en haalt de vrijgave eraf. Zonder vrijgave
(`ready_devices`, de knop "Ingeruimd en dicht" op de kaart) doet hij niets.

Het virtuele huis heeft een `Vaatwasser` (tests/virtueel.py) met een
verbruiksprofiel in twee bulten, "starten op afstand" dat uit kan staan, en
de gebeurtenissen `vaatwasser_vrijgeven` en `vaatwasser_deur`. Vijf
scenario's `vaatwasser-*` in scenarios.py.

**De tabel is van de klant, en de meting wint.** De eigenaar op 06-09-2026 's
avonds: "ik wil dat kunnen aanpassen, wel moet hij dit als uitgangspunt
hebben." `PROGRAMMAS` is dus alleen nog het uitgangspunt: per apparaat staat
in Apparaten een bewerkbare tabel (`device.programs`, leeg is de opgave;
`tabel_van` in planner.py), en wat de coach bij een echte beurt meet komt
eroverheen (`program_measured` in de instellingen, `_async_meting_bewaren`
in coach.py, `met_metingen` in planner.py): duur, kWh, piek en het verloop
als watt per vijf minuten (`profiel_van`). `programma_kosten` rekent met
dat profiel, zodat de opwarmpiek in het zonnigste uur valt; zonder profiel
smeert hij het verbruik uit. Lopend gemiddelde over de laatste vijf beurten
(`METING_MAX_N`); per rij te wissen in Apparaten
(`device/measurements/clear`).

**Een domme vaatwasser** (merk "overig", op een meetstekker) plant de coach
ook, maar hij drukt niet: "smart plug als starten doen we niet, wel
adviseren en meten." `Apparaat.manual` maakt de teksten "zet hem aan"; op
het moment zelf gaat er één melding naar de telefoon, en na drie kwartier
één herinnering (`HERINNERING`). Of hij draait leest de coach van het
vermogen (`_status_uit_vermogen`: boven `DRAAI_W` draait hij, na
`STIL_KLAAR` stilte is hij klaar). Het programma kiest de bewoner op de kaart
uit de eigen tabel (`device.program`, commando `device/program`); bij Home
Connect uit de select-entiteit. **De coach kiest nooit zelf een programma.**
Zes scenario's `vaatwasser-dom-*`, `vaatwasser-eigen-tabel` en
`vaatwasser-gemeten` in scenarios.py; proef 58 en 59 in test_coach.py.

**Home Connect heeft twee programma-entiteiten** (v0.55.0, na de eigen "ik heb
selected program in plaats van select"): de sensor `program` die zegt wat
erop staat, en de select `program_select` waarmee het gezet wordt. De
keuzelijst op de kaart en de namen in de tabel komen uit de opties van die
select (`programOptions`, `programRows` in devices.js); de namen zijn daar
niet te typen. Zonder select zegt de kaart wat er mist (`programPicker` geeft
`missing`). **Geen verschuifbeleid per programma meer**: de eigenaar, "elk programma
is gewoon te verschuiven; het clean programma doe je toch handmatig."
Snelladen en Pauzeren staan alleen op een laadpaal (`kind !== "programma"`).

**Een vrijgaveschakelaar** (v0.56.0, `release_switch` bij allebei de
vaatwassermerken): een switch of input_boolean die hetzelfde betekent als
"Ingeruimd en dicht", voor een eigen keukendashboard. `_async_schakelaar_volgen`
in coach.py houdt de twee gelijk: beweegt de schakelaar, dan volgt de
vrijgave; beweegt de knop op de kaart, dan volgt de schakelaar; na een beurt
gaan ze allebei uit. Uit tijdens een lopende beurt laat de beurt met rust.
Proef 60 in test_coach.py. **De schakelaar en de status van een
programma-apparaat wekken de coach meteen** (v0.56.1, `_watch`): de eigenaar zette
de schakelaar aan en binnen vijf seconden weer uit omdat er niets gebeurde,
terwijl de coach pas bij de volgende minuut keek.

**In het lopende uur wint de meter van de zonverwachting** (v0.57.0). De eigenaar
op 07-09-2026 om 10:22: de coach wachtte op 11:00 terwijl zijn meter 3,5 kW
teruglevering zag; "je weet niet hoeveel je om 11 uur terug gaat leveren."
De verwachting zei 2,2 kW, het dak gaf 4,3. `programma_kosten` rekent voor
elk stuk in het lopende uur met `surplus_w` (de netto-export van nu,
`_netto_export_w` in coach.py), net als `schijven` bij de paal; bij gelijke
kosten wint het vroegste moment, dus een meting van nu wint van een even
goede verwachting van straks. Scenario `vaatwasser-meter-wint`. En laat de
meter nu genoeg zon zien voor het hele programma, en is dat op geen later
moment goedkoper (`meter_overal` in `programma_kosten`), dan start hij nu
(v0.57.1, na 10:51 die ochtend: hij wachtte tot 12:00 omdat de verwachting
voor 11:00 net te weinig zei, terwijl de meter 3,4 kW zag). Een goedkoper
uur bij een dynamisch contract blijft winnen, want dat is een prijs en geen
gok. Niet in de avondpiek. Sinds v0.62.0 is "de meter" hier de laagste
teruglevering van de afgelopen tien minuten; zie hieronder.

**Twee meldingen per beurt**, gestart en klaar (v0.57.0, de eigenaar: "ik wil wel
meldingen ontvangen dat de vaatwasser gestart is en klaar is"). "Is gestart"
als de coach drukte of erom vroeg, "draait" als de bewoner hem zelf aanzette.

**Het vinkje bij Apparaten heet naar wat de coach kan** (v0.57.0, de eigenaar: "er
is een verschil tussen aansturen en adviseren"): "aansturen" bij een merk met
knoppen (`canSteer` in devices.js), "adviseren" bij een programma-apparaat
zonder startknop, "noemen" bij alles wat alleen op een meetstekker zit. Staat
het uit, dan noemt de overschottip het apparaat ook niet (`apparatenZin`).

**Een gemeten rij staat op slot** (v0.57.2, de eigenaar na de eerste beurt: "er
staan nog wel mijn dingen in; geblokkeerd tot je het wist, en dat je het
zelf kan invullen of toch overschrijven"): de velden tonen de meting en zijn
niet te bewerken; "wissen" geeft de eigen getallen terug, "overnemen"
(`takeMeasurement_`) maakt de meting de eigen opgave en haalt hem weg (het
verloop per vijf minuten gaat daarbij verloren). **Bespaard kiest zijn
woorden naar de beurten** (`woorden` in savings.js, `kind` in het
beurtrecord): een auto wordt ingeplugd en geladen, een vaatwasser
vrijgegeven en verbruikt. Een beurt van vóór v0.57.2 heeft geen `kind`;
`met_soort` in storage.py leidt hem dan af uit het type van het apparaat
(`PROGRAMMA_TYPES` in const.py), bij het opvragen van de lijst (v0.58.1,
De eigenaar: "ik zie nog dingen terugkomen van de laadpaal").

**Eén keer echt gezien aan Home Connect, 07-09-2026 om 11:00 in een echte woning:**
knop, Run na twee seconden, tellen op de meetstekker, Finished, verslag,
meting (Express 60: 90 min, 0,825 kWh, piek 2264 W), vrijgave eraf. Zijn
machine zet de deur een kwartier voor het eind vanzelf open voor de stoom
en trekt de laatste twintig minuten vrijwel niets; voor een domme
vaatwasser was `STIL_KLAAR` (een kwartier) daarmee te kort. Sinds v0.58.0
een half uur.

**Een herstart midden in een beurt verliest de telling niet** (v0.58.0,
De eigenaar: "ja, reken terug"). De lopende beurt gaat elke vijf minuten naar de
`BeurtenStore`, met `complete` op false en een `session` met alles wat de
coach nodig heeft (vrijgavemoment, prijzen van toen, verloop, wat er al
gemeld is). In de eerste ronde na een herstart (`eerste` in
`_one_programma`) pakt `_async_programma_hervatten` hem daar op; het gat
sinds die opslag komt twee minuten later uit de kwartieropslag
(`_async_programma_terugrekenen`, want die haalt na een herstart zelf
eerst in). Staat er niets in de opslag, dan zegt de recorder wanneer hij
ging draaien en de vrijgaveschakelaar wanneer hij werd vrijgegeven
(`_async_programma_begin`), en komt de hele beurt tot nu uit de
kwartieropslag. Is hij afgelopen terwijl de coach weg was, dan krijgt de
beurt zijn verslag met wat er bewaard stond en gaat de vrijgave eraf,
anders start hij zo nog een keer. Proef 62 in test_coach.py, scenario
`vaatwasser-herstart`.

**De eindtijd van het apparaat zelf** (v0.58.0, de eigenaar: "pak de eindtijd van
de integratie"): het veld Resterende tijd (`remaining`) mag een tijdstip
zijn (Home Connect) of minuten of seconden (`_eindtijd` in coach.py). "Klaar
rond" in de melding en op de kaart komt daarvandaan; zonder die sensor uit
de tabel. Proef 61. Een eindtijd die al voor de start stond telt niet
(v0.62.0; zie hieronder).

**Zonder meting gaat het verbruik op de piek, en de meterregel eist de
piek** (v0.59.0). De eigenaar op 08-09-2026 om 09:12: Eco 50 zonder meting startte
met 250 W op de meter, "waarom, terwijl bekend is dat de zon later meer
schijnt?" Uitgesmeerd was Eco (225 min, 0,8 kWh) 213 W, en dat paste; de
opwarmpiek van 2,2 kW kwam van het net terwijl het dak om 12:00 3,8 kW gaf.
Sinds die dag zet `_programma_stukken` zonder profiel alle kilowatturen op
`peak_w` vanaf de start (23 minuten voor Eco) en daarna niets, en grijpt
`meter_overal` in `plan_programma` alleen in als de meter ten minste de piek
laat zien. De gewone som met de meter voor het lopende uur blijft: zegt de
voorspeller de helft (zoals die dag), dan start hij zodra de meter van nu op
de som wint, en dat is een verwachting waar niets aan te schaven is (de eigenaar,
07-09). Scenario's `vaatwasser-vroeg` en `vaatwasser-vroeg-verwacht`, proef
50 in test_planner.py.

**Bespaard is het totaal plaatje** (v0.60.0). De eigenaar op 09-09-2026, bij een
vaatwasser die meteen op zon startte en "bespaard nul" kreeg: "Er is toch
wel iets zonne-energie naar de vaatwasser gegaan? Ik wil het totaal plaatje.
Wat het heeft gekost nu tegenover een duurder moment van het vrijgeven, en
wat je op zonne-energie laadt bespaar je natuurlijk ook door minder stroom
in te kopen." De maat is dus alles van het net op het moment van vrijgeven
of inpluggen (`_basis_bij` en `_programma_tellen` in coach.py), en bespaard
is maat min betaald, in twee delen: door de zon (`zon_winst`, `solar_saved`
in het beurtrecord: de zon-kilowatturen maal inkoop min teruglevering) en
door te wachten (de rest). Het verslag zegt welk deel wat was
(`_bespaard_zin`); Bespaard toont ze als tegels en als kolom "Door zon"
(`delen` in savings.js). Een beurt van vóór v0.60.0 heeft geen zondeel:
bij die beurten zat de zon in de maat en was bespaard alleen het wachten.
v0.59.0 had het één dag andersom (de zon van het vrijgavemoment in de maat,
`zon_toen`), en dat gaf precies de nul waar de eigenaar over viel. Proef 64.

**De meter is tien minuten zon, en de eindtijd hoort bij de beurt**
(v0.62.0). In een echte woning op 11-09-2026: om 09:29 vrijgegeven, en om 09:35
klaarde het een paar minuten op; de meter zag 2694 W teruglevering, meer dan
de piek van Express 60 (2264 W), en de coach startte. Om 09:37 was het 721 W;
de drie opwarmpieken kregen 1,1 tot 1,8 kW zon, 0,2 van de 1,0 kWh, en de
beurt kostte € 0,234 waar hij € 0,180 voorspelde. Sinds die dag krijgt
`plan_programma` als `surplus_w` de laagste teruglevering van de afgelopen
tien minuten (`METER_VENSTER`, `_meter_bijhouden` en `_meter_zeker` in
coach.py), voor het lopende uur én voor `meter_overal`; zolang er nog geen
acht minuten gemeten zijn (`METER_DEKKING`, na een herstart) telt de meter
niet en rekent hij met de verwachting. De paal houdt de meting van nu, want
die past zich elke ronde aan. De keerzijde: in een opkomende ochtendzon loopt
de meter tien minuten achter, en vier scenario's starten 3 tot 10 minuten
later, zonder dat het duurder wordt. En de melding zei "klaar rond 10:56":
dat was de eindtijd die Home Connect om 09:01 bij het kiezen van het
programma zette; om 09:37:05 rekende hij hem opnieuw uit (11:31), klaar was
hij om 11:28. `_eindtijd` neemt met `sinds` alleen een waarde die niet
eerder dan `EINDTIJD_MARGE` voor de start gezet is (`last_changed`), en de
melding "is gestart" wacht daar hooguit `EINDTIJD_WACHT` op; daarna de duur
uit de tabel, vanaf de start. Scenario's `vaatwasser-zonpiek` (oud: start
09:32 op de opklaring; nieuw: 11:56, 0,84 van 0,85 kWh zon) en
`vaatwasser-eindtijd` (oud: "klaar rond 10:45", nieuw: 11:21, zoals het
ging), proef 66 en 67 in test_coach.py. Het virtuele huis kent daarvoor
`Zon.pieken` (een opklaring die de voorspeller niet ziet) en
`Vaatwasser.eindtijd_tijdstip` (een eindtijd die al bij het kiezen staat en
pas een minuut na de start klopt).

**Een eindtijd telt pas als hij stilstaat** (v0.64.0). In een echte woning op
15-09-2026: om 09:33 vrijgegeven, om 10:11 startte de coach op de meter, en
de melding zei "klaar rond 11:33" terwijl hij om 11:45 klaar was. Deze keer
was het geen eindtijd van het kiezen: Home Connect zette hem om 10:11:56,
een seconde voor Run, en rekende hem om 10:13:02 opnieuw uit op 11:41. De
melding ging om 10:12:53, negen seconden voor die correctie. Sinds die dag
gelooft de coach een eindtijd pas als hij hem twee ronden achter elkaar
ongeveer hetzelfde zag (`_eindtijd_vast` in coach.py, `EINDTIJD_SPELING`);
ongeveer, want de sensor wiebelt een minuut heen en weer (11:41:02 en
11:42:02 om de minuut). Tot dan blijft staan wat er al geloofd werd, dus een
eindtijd die verspringt verdwijnt niet van de kaart. `EINDTIJD_WACHT` ging
van twee naar vier minuten: twee ronden zijn er nodig en de eerste waarde
komt soms pas een ronde na de start. De melding komt daarmee een tot twee
minuten later dan vroeger. Scenario `vaatwasser-eindtijd-bijstellen` (oud:
10:21 "klaar rond 11:09"; nieuw: 10:23 "klaar rond 11:21", en dat werd het),
`Vaatwasser.eindtijd_eerst_min` in het virtuele huis, proef 66 in
test_coach.py.

**Na de klaar-tijd: morgen of nu** (v0.63.0). De eigenaar gaf de vaatwasser op
12-09-2026 om 16:33 vrij, bij vanaf 08:00 en klaar om 16:30. De coach plande
de volgende middag, zei "hij start om 13:00" zonder "morgen", en noemde bij
"nu starten" de prijs van 08:00 de volgende ochtend; de eigenaar zette hem zelf aan.
Op 13-09: "ik wil dat er een optie bijkomt als hij na de klaartijd is. Dan de
keuze ingeruimd en morgen starten of ingeruimd en nu starten." Sindsdien geeft
`resolve_window` de klaar-tijd van vandaag mee als die voorbij is
(`Window.missed`), en staan er dan twee knoppen op de kaart: "Ingeruimd,
morgen starten" (de gewone vrijgave, het schema van de volgende dag; `later`
in het besluit zegt welke dag) en "Ingeruimd, nu starten" (`ready_now` in de
instellingen, `Apparaat.start_now`, regel `start-now`: meteen, ook in de
avondpiek, net als snelladen). Na een vrijgave voor morgen blijft "Toch nu
starten" staan. Voor de keukenkaart een tweede schakelaar, `release_now_switch`
(`_async_nu_volgen` in coach.py, keuze van de eigenaar): aan is ingeruimd én nu, uit
voordat hij draait haalt alleen "nu" eraf, de vrijgave uit haalt ook "nu"
eraf, en na de beurt gaan beide schakelaars uit. De teksten van een programma
zeggen "morgen om" (`_dag_om`, `_dag_klok` in planner.py), en "nu starten zou"
rekent met echt nu. Vóór de klaar-tijd verandert er niets. Proef 52 in
test_planner.py, proef 68 in test_coach.py, scenario's
`vaatwasser-na-klaartijd` (morgen 09:00 op zon, zoals het al ging) en
`vaatwasser-na-klaartijd-nu` (16:34, oud: die keuze was er niet).

**Home Connect Local** (v0.84.0). De eigenaar op 23-09-2026: "ik heb thuis
problemen gehad met mijn Home Connect vaatwasser integratie, ik had er 2
lopen en heb nu een derde, Home Connect Local. Die lijkt beter te werken."
Dat is `homeconnect_ws` (chris-mc1/homeconnect_local_hass, HACS): lokaal
over een websocket naar de machine zelf, geen cloud, en de statuswissels
komen meteen. Hetzelfde merk "Home Connect" in Apparaten; wat er anders is
zit in de entiteiten, en de coach leest alle drie de integraties met
dezelfde velden. Vier dingen, alle vier thuis gemeten op 23-09-2026:

1. **De startknop is er alleen als de machine een start aanneemt.** De
   knop hangt aan `BSH.Common.Root.ActiveProgram`, en die is met de deur
   open alleen leesbaar: de knop staat dan op `unavailable`. Met de deur
   dicht is hij er meteen, ook met de stroom uit (de machine zet zichzelf na
   elke beurt uit; de stroom aanzetten hielp niets, de deur dichtdoen wel).
   Home Assistant slaat een dienst op een onbeschikbare entiteit stilzwijgend
   over, dus drukken kost dan een poging zonder dat er iets gebeurt. De
   coach drukt daarom niet zolang de knop `unavailable` is, zegt na
   `START_WACHT` één keer waar het aan ligt ("de deur staat open", of "zet de
   machine aan en kijk of starten op afstand aan staat"), en drukt zodra de
   knop terug is; de knop staat daarvoor in `_watch`. Bij de twee
   cloud-integraties heeft de knop altijd een toestand en verandert er niets.
2. **Het programma zit in twee entiteiten die elkaar afwisselen**: de sensor
   "Actief programma" zegt alleen tijdens de beurt iets, de select
   "Geselecteerd programma" valt juist tijdens de beurt weg. `_one_programma`
   leest eerst `program` en dan `program_select`, tot er een programma uit
   komt; het paneel doet hetzelfde voor de rij op de kaart (`deviceDetails`
   in data-source.js). De spelling is `dishcare_dishwasher_program_kurz60`,
   zonder het streepje voor het getal; `programma_van` en `valueLabel` gooien
   alles wat geen letter of cijfer is toch al weg.
3. **De resterende tijd staat in uren** (de machine telt in seconden, Home
   Assistant toont het als 1,4833 h). `_eindtijd` en `countdown` in format.js
   kennen nu seconden, minuten, uren en dagen; zonder eenheid minuten.
4. **"Start op afstand" is een eigen sensor**, en dat hebben de andere twee
   ook. Optioneel veld `remote_start` bij het merk: staat hij uit, dan drukt
   de coach niet en zegt hij na `START_WACHT` één keer "zet starten op
   afstand aan op het apparaat". Zonder die sensor blijft het zoals het was:
   drukken, en na drie minuten zeggen dat hij niet is gaan draaien.

Na een beurt zegt Local vijf seconden "finished" en dan "ready" (de machine
gaat uit); de coach ziet vaak alleen dat laatste, en dat was al klaar (de
tak `status in ("ready", "inactive", "")` met een lopende beurt). De
sensorwacht kent de status al; een herverbinding van twee seconden
(`unavailable`, thuis om 08:37 en 08:46) blijft onder `SENSOR_STIL`.

Het virtuele huis kent `Vaatwasser(lokaal=True)`: de knop `unavailable` bij
een open deur of tijdens de beurt, en een druk daarop doet niets (zoals Home
Assistant), de sensor en de select die elkaar afwisselen, de uren, en de
sensor voor starten op afstand. Scenario's `vaatwasser-lokaal` (dezelfde
beurt als `vaatwasser-zon`, tot op de cent), `vaatwasser-lokaal-deur-open`
(om 03:00 vrijgegeven met de deur open: geen druk, om 03:03 de melding,
om 03:08 gaat de deur dicht en om 03:09 draait hij) en
`vaatwasser-lokaal-afstand-uit` (geen enkele druk, één melding). Proef 92 in
test_coach.py, twee proeven in test_rapport.mjs. **Nog geen echte beurt aan
Home Connect Local gestuurd**: de eerste is de vrijgave thuis na v0.84.0.

## De boiler

Sinds 19-09-2026 stuurt de coach ook een boiler, na de eigen "ik wil gewoon een
sturing maken op een boiler waar je alleen stroom op moet zetten, met een smart
plug bijvoorbeeld. Als je er stroom op zet en de boiler is warm moet de coach
detecteren dat hij warm genoeg is omdat de boiler dan onder een bepaald
vermogen zit. Ik wil dit zelflerend hebben. Alleen de switch invullen en power
invullen."

**Twee velden, en verder niets.** De schakelaar (`switch` in `entities`, een
smart plug, een switch of een input_boolean) en de vermogenssensor die elk
apparaat al heeft. Geen merk, geen temperatuur, geen tabel: `FIELDS_BY_TYPE` in
devices.js geeft een type zijn eigen velden zonder dat er een merk aan te pas
komt, en `canSteer` telt een boiler met een schakelaar gewoon mee.

**De coach schakelt, de thermostaat beslist hoe warm.** Dezelfde afspraak als
"geen fasewissel" en "de coach kiest nooit zelf een programma": wij kiezen het
moment, het apparaat kiest de temperatuur. Daardoor kan dit niets kapotmaken en
niets onveiligs doen, en blijft de legionellaronde van de boiler zelf staan.

**Een boiler is geen programma-apparaat maar een buffer**, en staat daarmee
dichter bij de auto dan bij de vaatwasser: er moet een hoeveelheid energie in
vóór een moment, hij mag onderbroken worden, en de goedkoopste blokken mogen er
zelf uit gekozen worden. `boiler_schijven` in planner.py zet elk blok tussen nu
en de klaar-tijd op een prijs per kWh (eigen zon tegen de terugleverprijs, de
rest tegen de prijs van dat uur, precies zoals `charge_cost` bij de paal), en
`goedkoopste` pakt daar de goedkoopste uit. Eén schijf per blok en niet twee,
want een boiler moduleert niet: hij staat aan op zijn eigen vermogen of hij
staat uit. In de avondpiek telt alleen een blok dat de zon helemaal draagt
(eis 4). De eigenaar koos "klaar om, zoals de auto" (`DEADLINE_ONLY_TYPES`), en
zonoverschot mag hij pakken: staat er meer overschot dan het element trekt, dan
gaat hij aan, want het vat is de goedkoopste plek om overschot in te stoppen.

**Wat hij zelf leert** staat per apparaat in `boiler_learned` in de
instellingen, als lopend gemiddelde over de laatste beurten (`METING_MAX_N`):
het vermogen van het element, hoeveel er in een vol vat gaat (de grootste volle
beurt die hij zag, want dat is een grens uit de natuurkunde), wat er per uur uit
het vat gaat (afkoelen en douchen samen, over de tijd tussen twee volle beurten),
wanneer het vat voor het laatst vol was en wanneer er voor het laatst
werkelijk stroom liep. Te wissen met `device/measurements/clear`, hetzelfde
commando als bij de vaatwasser. Zolang er nog niets gemeten is rekent de coach
niet maar meet hij: aanzetten en kijken (`leren`).

**"Vol" is een meting.** Er staat stroom op, de aanloop is voorbij
(`BOILER_AANLOOP`), en hij trekt `BOILER_STIL` lang niets meer: dan is het vat
vol. De grens waaronder "niets" begint is een vijfde van het gemeten
elementvermogen, met `BOILER_DRAAI_W` als bodem. Gaat de stroom eraf, dan weet
de coach niets meer; daarom gelooft hij een verse meting `BOILER_KIJKEN` lang
(drie uur) en kijkt hij daarna opnieuw door even aan te zetten (`proef`). Dat
kost niets zolang het vat vol is, want dan vraagt de boiler geen stroom.

**Drie valkuilen die het virtuele huis eruit haalde**, alle drie op 19-09-2026:

1. *Aan en uit, elke minuut.* Een proef die na één ronde alweer door het gewone
   plan werd afgebroken. Een proef loopt nu af (`proef_sinds`), en pas als hij
   iets opgeleverd heeft telt het plan weer mee.
2. *De boiler at zijn eigen overschot op.* Zodra hij aanging zakte de
   teruglevering onder zijn eigen vermogen en zette de zonregel hem weer uit.
   Het overschot dat de coach gebruikt is daarom wat er naar het net zou gaan
   als deze boiler níet liep, net als bij de paal.
3. *Bijvullen wat een thermostaat niet aanneemt.* Vlak na een volle beurt zegt
   de som "er kan nog 0,8 kWh bij", vraagt de boiler niets, noemt de coach dat
   vol, en begint hij opnieuw. Een verse volmeting gaat daarom vóór de som
   (`boiler_nodig`), en onder `BOILER_KRUIMEL` van het vat valt er sowieso
   niets te verwarmen.

**Vol of een stekker die niets doet**, dat is het lastigste onderscheid van
deze sturing: allebei leveren ze nul watt. Wat ze uit elkaar houdt is de tijd.
Een vat loopt leeg, dus na `vol_kwh / verbruik` uur moet elke werkende boiler
een keer warmte gevraagd hebben; is er in die hele tijd geen watt gelopen, dan
is het de stekker (`BOILER_VERDACHT`). Geteld vanaf de laatste keer dat hij
werkelijk iets trok (`getrokken_op`) en niet vanaf de laatste keer dat de coach
"vol" concludeerde, want dat laatste schuift bij elke vergeefse poging mee op.
Na `BOILER_VERGEEFS` vergeefse pogingen zegt hij het één keer op de telefoon en
houdt hij op met schakelen (`geen-stroom`), tot het volgende kijkmoment.

**Meldingen: alleen als er iets aan de hand is.** Dat een boiler om drie uur
's nachts weer warm is hoeft niemand te wekken; dat verslag gaat wel de
geschiedenis in (`telefoon=False`). Op de telefoon komt alleen de stekker die
niets doet. De beurt zelf staat onder Bespaard (`kind` is `boiler`), gemeten
tegen wat hij gekost had als hij meteen was gaan verwarmen toen er warm water
bij moest.

**Gaat de coach weg, dan gaat de stroom erop.** `async_stop` zet elke gestuurde
boiler aan. Een auto die blijft staan is een ongemak, een koud vat merk je
onder de douche, en zonder coach hoort de thermostaat gewoon weer de baas te
zijn. Hetzelfde geldt als het schema uitstaat (`schema-uit`).

Vier scenario's in het virtuele huis: `boiler-leert` (de coach kent hem nog
niet), `boiler-nacht` (de goedkope nacht en warm om 07:00), `boiler-zon` (op
eigen zon) en `boiler-stekker-stuk`. Proef 73, 74 in test_coach.py en de
boilerproeven in test_planner.py. **Nog nooit aan een echte boiler gehangen**,
dus wat er in het echt anders kan zijn: hoe snel een meetstekker zijn vermogen
meldt, hoeveel speling de thermostaat heeft, en of een boiler bovenin
terugregelt in plaats van hard af te slaan.


## De thuisbatterij

Sinds 22-09-2026 stuurt de coach ook een thuisbatterij (v0.73.0), na de eigen
"Ik wil de coach gaan uitbreiden met een thuisbatterij. Ik wil hem kunnen
aansturen in HA. Laden, ontladen, blokkeren als de laadpaal laadt. Laden op
goedkope tarieven overdag en in de nacht. Laden op overschot zonne-energie. Hij
moet helemaal samenwerken met de energiecoach." En diezelfde avond, toen ik
voorstelde de batterij zijn eigen nul-op-de-meter te laten doen: **"het doel is
om hem volledig third party te sturen, dus via HA."**

**Twee lagen, en dat is de kern.** `batterij.py` kent Home Assistant niet, net
als planner.py.

* `plan_batterij` kiest elke minuut een **stand**. Het is een som over de tijd
  (`_waarde_vooruit`): van achter naar voren over alle blokken met een bekende
  prijs, per inhoud van de batterij wat de rest nog kost, met het verwachte
  huisverbruik en de zon erin (`_netto_huis_kwh`, dezelfde bronnen als
  `overschot_kwh`). Aan het eind is wat er nog in zit waard wat een gemiddeld
  bekend uur kost (`_gemiddeld_bekend`). Dat is dezelfde gedachte als
  `schijven` en `goedkoopste`, alle manieren op een hoop, maar een batterij kan
  twee kanten op en onthoudt wat erin zit.
* `Regelaar` voert die stand uit op het tempo van de meter (`_async_regel` in
  coach.py, gewekt door de netsensor en daarnaast elke `REGEL_TIK`).

**De standen** (de namen zijn van de bewoner van de eerste woning, 21-09-2026):
`nul`, `zonneladen`, `ontladen`, `netladen`, `max-laden`, `handelen`, `standby`.
`Besluit.grenzen` zegt per stand of de regelaar mag laden en mag ontladen; meer
verschil is er voor de regelaar niet.

**Zon opslaan en het huis voeden gaan tegen wat een kilowattuur straks waard
is** (`erbij` en `eraf`, het verschil in de som over een stap van het rooster).
Bij gelijkspel wint wat je in handen hebt: op een zonnige dag komt de batterij
toch vol, en wie dan "straks" kiest rekent op zon die er nog niet is. **Van het
net laden en handelen volgen het plan zelf** (`_rustig_vermogen`): de
vergelijking staat in het randuur precies op gelijkspel en viel in het virtuele
huis elke minuut anders, zeven wissels in een kwartier.

**Rustig laden.** De bewoner van de eerste woning: "als we 5u lang een
energieprijs van 13 cent hebben, heb ik liever dat ie 5u lang laadt op 50%
capaciteit, dan 2,5u op 100%." Wat het plan in de aaneengesloten even dure uren
van het net wil halen wordt over al die uren uitgesmeerd; dezelfde gedachte als
`rustig_tempo` bij de paal. Hij noemde erbij dat een omvormer tussen 30 en 75%
van zijn vermogen het zuinigst is. **Dat getal staat er niet in**: het is een
vuistregel en geen meting van deze batterij. Uitsmeren over even dure uren kost
nooit geld; een duurder uur erbij nemen om rustiger te laden is pas een som als
het rendement per vermogen gemeten is, en dat is het nog niet.

**Het rendement is een meting of een opgave, nooit een aanname.** In de eerste
woning kwam van elke kilowattuur die de kWh-meter op de batterij erin zag gaan
73,6% er weer uit.
De eigen tellers van die batterij telden meer eruit dan erin,
want die meten aan de accukant. `rendement_uit_tellers` wil tien keer de inhoud
aan doorzet (`RTE_MIN_DOORZET`) en weigert alles buiten 30 tot 100%. Zonder
rendement wordt er niet gepland: alleen nul op de meter (`rendement-onbekend`),
en met volledig salderen standby, want dan verliest opslaan altijd.

**Wat niet over geld gaat staat erboven**, zoals bij de paal: geen accustand is
standby; een negatieve prijs (de prijs die de bewoner betaalt, en de eigenaar op
21-09-2026: "dit jaar een paar keer voorgekomen") is maximaal laden met
ontladen dicht; de avondpiek blijft dicht voor het net (eis 4); onder de reserve
voor noodstroom komt er niets uit; en **laadt er een paal, dan geeft de batterij
niets af** (`_met_paal`, `_paal_laadt` in coach.py: gemeten aan het vermogen
van de paal en niet aan het besluit van de coach, want in de eerste woning
stuurde iets anders de paal). Sinds v0.87.1 ook aan wat de paal zelf zegt ("auto laadt" bij een
Alfen, "charging" bij een Easee), want het vermogen van een Alfen komt eens per
30 s; en de snelle regelaar past het elke stap toe (`met_paal` in
`_async_regel`) in plaats van op de besluitronde te wachten. In de eerste
woning op 23-09-2026 om 15:59 gaf de batterij daardoor 25 s lang 3,45 kW aan
de auto. Proef 94 in test_coach.py.

**De laadgrens van de batterij is van de batterij.** De eigenaar: "die instelling
van 95% is belangrijk, daar blijft hij continu op staan. Dit is een waarde waar
niet aan gekomen moet worden." De coach leest `charge_limit` en
`discharge_limit` en schrijft ze niet, **met één uitzondering** (v0.74.0, de
keuze van de eigenaar op 22-09-2026): de wekelijkse volle beurt voor het
balanceren (`vol_voor`, `VOL_GEWICHT`) is er voor de cellen, en tot 95%
balanceert niets. Op de dag van die beurt zet de coach de laadgrens op het
maximum van de entiteit (`_async_laadgrens_omhoog`), en zodra de batterij vol
is, de dag om is, de coach niet meer stuurt of stopt, zet hij hem terug op
wat er stond (`_async_laadgrens_terug`, ook vanuit
`_async_batterij_loslaten`). Wat er stond staat in `battery_state` als
`limit_restore`, zodat een herstart het niet vergeet. Alleen op het niveau
sturen; op adviseren blijft de grens met rust. "Vol" voor de opslag
(`full_at`) is dan ook 100 en niet de eigen grens, anders is een batterij die
in de zomer elke middag op 95% staat nooit aan een volle beurt toe. Proef 79
in test_coach.py; scenario `batterij-volle-beurt` (grens om 00:05 naar 100,
om 23:56 op 98,8% terug naar 95).

**De regelaar**, na de eigen "als je realistisch kijkt verbruik je nooit steady
350 W, hoe zorgen we dat we niet gaan pendelen?" Gemeten in de eerste woning,
waar een andere sturing de batterij toen regelde: 1.713 opdrachten en 233
statuswissels per dag, een dode band van 40 W die de meter 98,9% van de tijd
binnen 50 W hield, een sprong van 2,1 kW die na tien seconden weg was, de meter
elke vijf seconden in Home Assistant en de batterij die een opdracht binnen
vijf seconden volgde. Het pendelen zat rond nul: standby en ontladen om de tien
tot vijftien seconden. Daaruit:

- **Een som en geen versterkingsfactor**: het huis vraagt wat de meter zegt plus
  wat de batterij nu doet, en dat is de nieuwe opdracht.
- **Niet opnieuw corrigeren voordat de vorige te zien is** (`bezonken`,
  `WACHT_OP_BATTERIJ`). Hier komt pendelen vandaan. Te zien is: de batterij
  heeft `VOLGT_NA` gehad om hem uit te voeren, de sensor meldt hem, en de
  meter heeft daarna nog gemeten; hooguit vijftien seconden wachten, de
  keuze van de eigenaar op 22-09-2026.
- **Een dode band** (`DODE_BAND_W`), **groot meteen en klein pas als het blijft**
  (`GROOT_W`, `KLEIN_METINGEN`), **rond nul twee grenzen** (`BEGIN_W`, `STOP_W`)
  en een kleine wens die de richting niet binnen een minuut omkeert
  (`RICHTING_WACHT`).
- **Mikken op de goedkope kant van nul** (`doel_w`): waar terugleveren minder
  opbrengt dan inkopen kost, een halve dode band onder nul.
- **Zwijgt de meter `METER_STIL`, dan gaat de batterij naar 0 W.** Een enkele
  gemiste meting niet: veel integraties melden tussendoor even "niet
  beschikbaar".
- De officiele stuurentiteit van de eerste woning **leest niet terug** wat erin
  geschreven is (hij stond op 0 W terwijl de batterij 2250 W ontlaadde). De
  regelaar leest dus nooit uit die entiteit; hij onthoudt zijn opdracht zelf.

**De sensor is de bevestiging en niet de bron** (v0.74.0). Op 22-09-2026 een
etmaal meegekeken in de eerste woning, waar toen nog een andere sturing de
batterij regelde, met een kWh-meter op de batterij als meetlat. Die sturing
schreef 1.713 opdrachten per dag en slingerde bij elke korte last: zeven
slingers in zes minuten, vijf keer 3.500 W laden met 1 tot 1,9 kW inkoop op
een zonnige ochtend, drie keer ontladen met 1,4 tot 1,7 kW teruglevering. De
oorzaak zat niet in die sturing maar in de sensor: het vermogen dat de
Anker-integratie meldt loopt vijf tot tien seconden achter op de kWh-meter,
toont onderweg een aanloop die er niet is (1040, 1020, 1010, 1000, 940 en dan
pas 2500, terwijl de meter meteen 2580 zag) en vlak na een opdracht soms de
opdracht zelf (0 W terwijl er aantoonbaar 2215 W liep). Wie de sensor bij de
meter optelt telt zijn eigen opdracht dubbel. Drie dingen, alle drie in de
`Regelaar`:

1. **De som rekent met de eigen opdracht** (`vermogen_w`): nieuwe opdracht is
   vorige opdracht plus wat de meter zegt. De sensor telt pas als hij de
   opdracht `AFWIJK_METINGEN` keer achter elkaar tegenspreekt buiten het
   venster na een opdracht, want een batterij die blijvend niet doet wat er
   gevraagd is (vol, leeg, te warm) moet wel gezien worden.
2. **Een aanloop is geen bevestiging.** Alleen een sensorwaarde binnen de dode
   band van de opdracht telt als aangekomen, en pas na `VOLGT_NA`; een sensor
   die twee seconden na de opdracht al "klopt" toont de opdracht en niet de
   meting. Zonder sensor is de meter het bewijs, en dan met dubbele tijd.
3. **Het overschot voor de andere apparaten rekent ook zo**
   (`_batterij_geregeld_w` in coach.py, in `_batterijen_w` en dus in
   `_netto_export_w`): anders ziet de paalplanner bij elke omslag een
   schijnoverschot van de sensor die nog op de oude stand staat.

Het virtuele huis kent daarvoor de sensor van de Anker (`sensor_na_s`,
`sensor_aanloop`, `sensor_echo_s` op `Batterij`, samen `ANKER_SENSOR` in
scenarios.py) en de uurlast van die woning (`Huis.puls`: elk uur veertig
seconden 2,5 kW, een boiler of een warmtepomp zei de eigenaar). Scenario
`batterij-anker-sensor` (de sprong van 3 kW; oud: 241 opdrachten en 118
richtingwissels in een uur, 0,87 kWh van het net; nieuw: 3 en 0, 0,39 kWh,
gelijk aan de eerlijke sensor) en `batterij-uurlast` (oud: 180 opdrachten in
drie uur, slingerend tussen 357 en 3.500 W; nieuw: twee per puls en 0,17 kWh
van het net op een hele dag, de tien seconden aanloop van elke puls). Proef
26 tot 29 in test_batterij.py, proef 80 in test_coach.py.

**"Daarna" is na de bevestiging, niet na de opdracht plus vijf seconden**
(v0.81.1). De eerste nacht met de coach aan het stuur in de eerste woning,
22-09-2026 vanaf 23:21: een last van 2,1 kW die vijf seconden aanstond, een
batterij die de opdracht pas na tien seconden uitvoerde, en toen om :08 de
meter met de oude stand (−2141 W) en om :09 de sensor met de nieuwe (228 W).
`meter_na` eiste alleen een meting van na de opdracht plus `VOLGT_NA`, en
:08 was dat; de regelaar telde −2141 bij 230 op en vroeg 966 W laden, op 12%
midden in de nacht. Daarna elke tien seconden de andere kant op: 1155
ontladen, 195, 1781, 220. De `Regelaar` onthoudt nu wanneer de sensor de
opdracht voor het eerst bevestigde (`bevestigd_op`) en telt alleen een meting
van daarná; zonder sensor blijft het de opdracht plus tweemaal `VOLGT_NA`. De
meter meldt eens per vijf seconden, dus dit kost hooguit één tik. Het virtuele
huis kan dit sinds die nacht nadoen: `Batterij.meter_tik_s` en `meter_fase_s`
(een P1 die om :03 en :08 meldt en daartussen vasthoudt) met stappen van een
seconde. Scenario `batterij-klapperlast` (oud: 286 opdrachten, 143 wissels,
0,86 kWh van het net in een uur op 30%; nieuw: 181, 0, 0,25), proef 30 in
test_batterij.py met de getallen van die nacht. Wat er overblijft is één
opdracht per puls en één terug: de batterij reageert op een puls die allang
voorbij is, en dat is geen slinger maar de vertraging van de batterij zelf.

**Gaat de coach weg, dan gaat de batterij terug** (`_async_batterij_loslaten`):
vermogen op nul en `idle_mode` in de modus. Ook als het vinkje "mag sturen" eraf
gaat of het niveau naar adviseren. Dezelfde gedachte als de stroom terug op de
boiler.

**Ook bij een herstart van Home Assistant** (v0.82.0). Bij een herstart roept
Home Assistant `async_unload_entry` niet aan, dus `async_stop` ook niet; er
komt alleen het event `homeassistant_stop`, en daar bewaarde `_async_bij_stop`
tot 23-09-2026 alleen de lopende beurten. In de eerste woning bleef de batterij
daardoor bij de herstart voor v0.81.1 (23-09-2026 om 00:44) gewoon 235 W
ontladen in de externe modus tot de coach twee minuten later terug was, en een
boiler was zonder stroom gebleven. `_async_bij_stop` geeft nu zelf de
batterijen terug en zet de boilers aan, en wacht daarop, want een taak die bij
het afsluiten nog in de wachtrij staat wordt niet meer gedraaid. Proef 79d in
test_coach.py. **In het echt nog niet gezien**: of de integratie van de
batterij op dat moment de opdracht nog aanneemt blijkt bij de volgende
herstart in de eerste woning.

**De knoppen van de batterij hebben eigen iconen** (v0.82.0): "Nu vol laden"
een accu met een pijl erin (`accuVol`), "Nu leegladen" een accu met een pijl
eruit (`accuLeeg`), en de paal houdt de bliksem (`data-boost-icon` in
overview.js). De eigenaar op 23-09-2026: het pauzeteken bij leegladen klopte
niet.

**De batterij vervalst de meter voor de andere apparaten.** Wat hij opslokt is
geen huisverbruik maar zon die ook naar de auto had gekund, en wat hij afgeeft
is geen zon. `_batterijen_w` telt het terug in `_netto_export_w` en in `_read`;
`_async_huisverbruik` trekt een batterij met zijn teken van het huis af, en het
paneel doet dat in `data-source.js` (`batteryWatts`). De auto laadt op zon
zonder verlies en de batterij verliest een kwart, dus de andere apparaten gaan
voor; de batterij krijgt vanzelf wat er daarna over is.

**Het kasboek en de terugverdientijd.** `verdiend` is per stap het verschil
tussen de rekening zoals hij loopt en zoals hij zonder batterij gelopen had (de
meter min wat de batterij doet); het rendement zit er vanzelf in. Het gaat per
dag naar `battery_state` in de instellingen. `terugverdiend` noemt pas een datum
na `TERUGVERDIEN_MIN_DAGEN` en zegt over hoeveel dagen hij gemeten heeft. Wat de
batterij verdiende voordat de coach erbij kwam wordt niet geschat.

In het paneel: het type thuisbatterij staat er weer in (`DEVICE_TYPES`; het is
uit `VERVALLEN_TYPES`), merken Anker en Overig met dezelfde velden
(`BATTERY_FIELDS` in devices.js), de instellingen van de bewoner in
`batteryHtml_` (views/devices.js, `battery` op het apparaat, `_BATTERY` in
websocket.py), en de regels op de kaart in `battery.js`.

Het virtuele huis heeft een `Batterij` die een opdracht na vijf seconden
uitvoert en daarna vasthoudt, zoals een batterij in externe sturing doet.
Zestien scenario's `batterij-*` in scenarios.py, met per scenario het aantal
opdrachten, de richtingwissels, en de kosten van de dag met en zonder batterij.
Wat eruit kwam en gerepareerd is: het klapperen in het randuur, en een waarde
die vlak onder de laadgrens een achtste te laag uitkwam, waardoor de batterij op
een zonnige dag op 93% bleef staan. test_batterij.py, proef 75 tot 80 in
test_coach.py, en de batterijproeven in test_rapport.mjs.

**Nog nooit aan een echte batterij gehangen.** Wat er in het echt anders kan
zijn: in welke volgorde vermogen en richting geschreven moeten worden (ze delen
bij Anker een register), wat de batterij doet als Home Assistant zelf vastloopt
terwijl er een opdracht staat, of `BEGIN_W` en `STOP_W` bij de echte omvormer
passen, en of het opgegeven laadvermogen klopt. Eerst meekijkend installeren
(niveau adviseren), dan pas sturen. Wat wél al aan de echte woning gemeten is
(22-09-2026): de P1 elke vijf seconden, de batterij die een opdracht binnen
vijf seconden volgt, de sensor die vijf tot tien seconden achterloopt, de
accustand per procent om de vijf minuten, een nette herstart van Home
Assistant (de andere sturing zette eerst 0 W, dertig seconden stil, daarna
weer verder), en de omvormer van de zon die 's nachts onbereikbaar is
(`_zon_slaapt` geldt daar ook).

**De coach leest elke vorm van prijslijst die het paneel ook leest** (v0.74.1).
De eerste dag op sturen in de eerste woning (22-09-2026) stond er de hele dag
"de prijs van dit uur is niet bekend": het contract was dynamisch met Zonneplan,
en die integratie geeft zijn lijst als `forecast` met alleen een `datetime` en
een `electricity_price` in tienmiljoensten van een euro (3355224 naast een
toestand van 0,3355224 €/kWh), terwijl `_slots` alleen `prices` met `from`,
`till` en `price` kende (Frank Energie). `_prijsrijen` in coach.py leest nu
dezelfde vier vormen als `readSchedule` in data-source.js: Frank Energie, Nord
Pool (`raw_today`/`raw_tomorrow`), Tibber en EnergyZero (`data`) en Zonneplan
(`ZONNEPLAN_DELER`). Een blok zonder eindtijd loopt tot het volgende blok, het
laatste blok is even lang als het blok ervoor, en zonder blok ervoor zo lang
als het contract zegt; paneel en coach houden daar dezelfde regel voor. **Houd
die twee lijsten gelijk.** En dezelfde sensor als all-in én als marktprijs
ingevuld maakt de terugleveropbrengst onbekend in plaats van gelijk aan de
inkoopprijs; het formulier zegt dat erbij. In de energiestroom wijst de pijl
van een ontladende batterij nu naar het huis (`batteryWatts < 0` in
energy-flow.js); de bewoner zette er een rode kring om. Proeven bij de
prijslijst in test_coach.py (na de datetime-proef) en in test_rapport.mjs.


## Hoe het in elkaar zit

| bestand | wat het doet |
|---|---|
| `planner.py` | alle denkwerk, kent Home Assistant niet, is los te draaien |
| `planner.py`, onderaan | het denkwerk voor een apparaat met een programma: `plan_programma`, `programma_kosten`, `PROGRAMMAS`, en daaronder dat voor een boiler: `plan_boiler`, `boiler_schijven`, `boiler_nodig` |
| `batterij.py` | het denkwerk voor een thuisbatterij, kent Home Assistant ook niet: `plan_batterij` (de stand), `Regelaar` (de snelle lus), `verdiend`, `terugverdiend`, `rendement_uit_tellers` |
| `coach.py` | leest sensoren, stuurt de paal aan, houdt de laadbeurt bij |
| `websocket.py` | wat het paneel mag opvragen en wijzigen |
| `storage.py` | de instellingen op schijf |
| `monitor.py` | de zekeringbewaking en de wachthond |
| `report.py` | het pdf-rapport |
| `frontend/src/` | het paneel, ES-modules zonder buildstap |
| `frontend/src/schedule-sheet.js` | het schema van één apparaat, als pop-up achter zijn kaart |
| `ontvangers.py` | wie welke melding krijgt: personen (een telefoon, een naam, eventueel een gebruiker van Home Assistant) met een schakelaar per soort: kritiek, melding, besluit, belasting. Kent Home Assistant niet |
| `frontend/src/views/notifications.js` | Meldingen, twee in een sinds 06-09-2026: bovenaan de personen (de admin voegt toe, een bewoner ziet alleen zichzelf en zet zijn eigen schuiven via `notifications/mine`), de zekeringmelding "Zware belasting" (uit Strategie verhuisd), en daaronder alles wat de coach ooit stuurde én elk besluit dat hij nam (`_async_noteer_besluit`), uit `MeldingenStore` in storage.py |
| `frontend/src/savings.js` | Bespaard, onder Historie: de laadbeurten uit `BeurtenStore` (storage.py) opgeteld per periode en per apparaat. De coach telt per ronde wat een beurt kost (`_geld_bij`) en wat dezelfde tijd op vol vermogen vanaf het inpluggen met alles van het net gekost had (`_basis_bij`, de maat); bespaard is maat min betaald, nooit onder nul, in twee delen: door de zon (`zon_winst`) en door te wachten. Stapt hij midden in een beurt in, dan rekent `_async_terugrekenen` het begin terug uit de recorder en de kwartieropslag |

De scheiding tussen `planner.py` en `coach.py` is de kern: het denkwerk is los
te draaien tegen een hele dag echte historie voordat er ook maar iets geschakeld
wordt. Zet daar niets in dat `hass` nodig heeft.

**Sinds 30-08-2026 is er geen ladder van regels meer maar een vergelijking.**
Elk uur tussen nu en de klaar-tijd levert twee manieren om een kilowattuur in de
auto te krijgen: uit je eigen zon, tegen wat je er anders voor gekregen had, of
van het net, tegen de prijs van dat uur. Alle manieren op een hoop, sorteren op
prijs, van onder af vullen tot er genoeg in zit. Zie `schijven` en `goedkoopste`
in planner.py; dat laatste is het gebroken-knapzakprobleem en dus aantoonbaar
optimaal.

Wat daar niet in zit zijn de dingen die niet over geld gaan, en die staan er nog
gewoon boven: de kabel, de zekering, de lastbewaker, een eigen pauze, snelladen,
de klaar-tijd en de avondregel. Zie de opsomming in `_decide`.

De eigenaar op 30-08-2026: "het eindoel is altijd lage kosten, zo min mogelijk geld
uitgeven, en dat moet optimaal gestuurd worden. Dus alle scenario's moeten
vergeleken worden met elkaar." De keuze tussen laagste kosten en zoveel mogelijk
zon is daarmee uit Strategie verdwenen: zon wint vanzelf zodra hij goedkoper is.

## Proeven draaien

```
python tests/test_planner.py     # 400 controles op het denkwerk
python tests/test_batterij.py    # 93 op het denkwerk van de thuisbatterij en op de regelaar
python tests/test_coach.py       # 581 op de bedrading, met een nagebouwde HA
python tests/test_virtueel.py    # 1731 op hele laadbeurten in het virtuele huis
python tests/test_archive.py     # 41 op de kwartieropslag
node   tests/test_rapport.mjs    # 91 op het rapport en op het paneel
node   tools/laadcheck.mjs       # laadt elke paneelmodule echt in
python tools/stijlcheck.py       # backticks in css-commentaar
```

De nagebouwde Home Assistant staat in `tests/harnas.py` en wordt door
`test_coach.py` en het virtuele huis gedeeld.

### Het virtuele huis

Sinds 04-09-2026 hoeft er geen lege bus meer aan een echte paal te hangen om
een laadbeurt te beproeven. `tests/virtueel.py` is een huis met een zon die
opkomt en ondergaat, een huis dat kookt, een auto die voller wordt van wat de
paal hem geeft, een meter die dat ziet, en een prijslijst die om 13:00 de dag
van morgen leert. De echte `coach.py` draait er elke minuut een ronde in en
krijgt alleen terug wat zijn eigen opdrachten teweegbrengen. Een nacht duurt
een seconde.

```
python tests/virtueel.py                   # de lijst van scenario's
python tests/virtueel.py vast-zonnig       # één scenario, per minuut, met de reden erbij
python tests/virtueel.py vast-zonnig kort  # dezelfde dag in blokken
python tests/virtueel.py alles             # alle scenario's, één regel per stuk
```

De scenario's staan in `tests/scenarios.py`, langs de assen die er bij klanten
zijn: vast of dynamisch, met of zonder salderen, zonnig, bewolkt, wisselend of
zonder panelen, een gesplitste meter of een meter met een teken, een krappe
zekering, een auto die niet wakker wordt, een bewoner die pauzeert, een P1 die
wegvalt. **Voeg bij elke nieuwe regel een scenario toe** dat laat zien waarom
die regel bestaat, en een controle in `test_virtueel.py` op wat de bewoner ervan
merkt: kilowattuur, kosten, of de klaar-tijd gehaald is, en welke meldingen er
kwamen.

**Een echte woning nabouwen** kan sinds 04-09-2026 met drie velden: `Zon(kromme=...)`
met de uurkromme van het energiedashboard in kWh per lokaal uur, `Huis(profiel=...)`
met de mediaan van het huisverbruik in watt per uur uit de eigen opslag
(`domotiapp_coach/history/quarters`), en `Prijzen(per_dag={"2026-09-05": [...]})`
met de all-in prijzen zoals de klant ze zag. Let op: het energiedashboard en de
prijssensor geven hun uren in UTC; twee uur erbij voor de lokale lijst. De negen
`klantwoning-*`-scenario's zijn zo gebouwd, uit de stand van vrijdagavond
04-09-2026, en `test_virtueel.py` meet er de vijf controlepunten van die
laadbeurt op na.

Twee gebeurtenissen die er sinds 04-09-2026 's avonds bij horen: `("10:30",
"herstart", None)` zet een nieuwe coach neer met een leeg geheugen en dezelfde
opslag, zoals Home Assistant dat na een herstart doet; `("13:30", "sensor_weg",
("soc", 45))` maakt één sensor zoveel minuten `unavailable` (namen: de sleutels
van `E` in virtueel.py). Een tijd mag een dag vooruit: `"+1 04:20"`. De coach
meldt elke sensor die hij gebruikt na tien minuten stilte één keer, en één keer
als hij terug is (`_async_sensorwacht` in coach.py, `SENSOR_STIL`); de slimme
meter heeft zijn eigen melding na vijf minuten (`_nettip`). Elke melding gaat
ook in de geschiedenis (`domotiapp_coach/notifications/list`, tab Meldingen).

Elk scenario meldt ook een **optimum**: wat dezelfde laadbeurt gekost had als
de coach de hele dag vooraf had gekend. Dezelfde som als `goedkoopste`, met de
werkelijke zon en alle prijzen. Zit de coach daar ver boven, dan is er iets te
vinden.

Wat er op de eerste dag uit kwam: een valse melding "nog niet vol" over een
auto die vol was, een tip die de verkeerde minuten telde, en een rustig tempo
dat door het uur heen zakte en met een sprint eindigde. Alle drie in v0.46.3.
Wat er nog open staat: zie de notities van 04-09-2026.

Het huis is nagemaakt en dus niet de waarheid over een echte Easee of een echte
Ford: wekken, de minimale stroom, faseomschakeling en netwerkhaperingen blijven
dingen om aan een echte paal te zien. Wel is de teller van de paal er even traag
als in het echt (eens per uur), en volgt de auto een limiet met een minuut
aanloop.

Die laatste draait het paneel in node, met een nagemaakte browser eromheen: de
module registreert zich als custom element en de proef pakt de prototype. Zo is
het rapport na te meten zonder scherm.

Home Assistant hoeft er niet voor te draaien; de handvol namen die `coach.py`
eruit gebruikt worden nagemaakt. **Draai ze allemaal voor elke uitgave.**

**Python 3.11 of nieuwer.** `coach.py` gebruikt `asyncio.timeout`, dat pas in
3.11 bestaat. Op macOS levert Apple bij zijn ontwikkelaarsgereedschappen nog een
3.9 mee, en die viel op 26-08-2026 midden in proef 9 om met een `AttributeError`
die eruitzag als een bug in de coach. Dat is het niet: Home Assistant zelf draait
op 3.13. Oplossing daar is `brew install python`, en dan **een nieuw
terminalvenster**, want een venster dat al openstond kent de nieuwe Python niet.
De proeven controleren dit nu zelf en zeggen het in één zin.

Bij een rode proef: verdenk eerst de proef en dan pas de code. Van de zeventien
"fouten" die de scenario's ooit opleverden waren er vijftien van het harnas.

Een proefopzet die begint met een paal die al laadt is geen gewone laadbeurt maar
een herstart middenin, en daar gedraagt de coach zich bewust anders. Doe eerst
één ronde met de kabel erin en nog geen stroom.

### Waar het schema van een apparaat staat

Sinds 27-08-2026 staat dat bij het apparaat zelf en niet meer in Strategie. Op de
kaart in Overzicht: de schuif die het schema aan en uit zet, en de keuzelijst
wie er voorgaat. Achter de knop Schema: de tijden en het per-dag-werk, in
`schedule-sheet.js`. Voor een laadpaal is dat sinds 04-09-2026 alleen nog
"klaar om" (`timesFor` in dat bestand); `_days` in coach.py negeert de andere
twee voor een laadpaal, ook als ze nog in oude instellingen staan. Alles gaat langs één commando,
`domotiapp_coach/device/schedule`, dat precies dat ene apparaat aanraakt en de
nieuwe lijst zelf uitrekent.

**Strategie gaat alleen nog over hoeveel de coach zelf mag.** De meldingen
staan sinds 06-09-2026 onder Meldingen, en de apparaten op hun eigen kaart.

Het schuifje is geen apart begrip: het is de `enabled` die elk schema al had.
Staat hij uit, dan slaat `_days` in `coach.py` het schema over en vervalt in
`planner.py` de hele klaar-tijdtak.

## Het paneel bekijken

```
python tools/serve.py            # http://127.0.0.1:8899/preview.html
```

`preview.html` staat in `.gitignore`: het is een lokaal harnas dat de serverkant
nabootst. Handige parameters: `?empty=1`, `?klant=1`, `?phone=390&h=700`,
`?coach=fase`, `?stuurfout=1`.

Serveer altijd met `Cache-Control: no-store` (dat doet `serve.py`), want Chrome
houdt ES-modules anders vast en dan meet je een oude versie. Ververs met een
unieke querystring (`?v=2`) als het in een iframe draait.

**Meten of iets verborgen is: kijk naar `getComputedStyle(el).display`, niet
naar `el.hidden`.** Het attribuut `hidden` is niets meer dan een regel van de
browser zelf en verliest van elke `display` die in de eigen stijlen staat. Elke
klasse die een `display` krijgt hoort dus een eigen `[hidden]`-regel te hebben.
Op 27-08-2026 kostte dat een ronde: de nieuwe pop-up had er geen, en `el.hidden`
stond keurig op `true` terwijl het blok gewoon in beeld stond.

Meet smalle schermen op **320 én 280 px**, niet alleen 390: zodra iOS inzoomt op
een invoerveld wordt de viewport smaller en komt echte overflow er alsnog uit.

**`node --check` is niet genoeg, en twee keer heeft dat een zwart paneel
gekost.** Draai deze twee erbij, altijd, voor je iets aan het paneel oplevert:

```
node   tools/laadcheck.mjs     # laadt elke module in zoals de browser dat doet
python tools/stijlcheck.py     # backticks in css-commentaar
```

`laadcheck.mjs` is de belangrijkste van de drie. Op 30-08-2026 stond er een
tweede `const device` in een functie die er al een in zijn parameters had. Dat is
een `SyntaxError`, dus een module die niet laadt, dus een paneel dat helemaal
zwart blijft. `node --check` gaf groen: die leest een bestand met `import` erin
niet als de module die het is. De eigenaar keek naar een zwart scherm en dacht dat zijn
herstart mislukt was.

`stijlcheck.py` gaat over iets anders. De stijlen staan in een template literal
en een backtick sluit de string af; op 27-08-2026 gaf `node --check` daar ook
groen op een bestand dat de browser weigerde met "Unexpected identifier". Die
zoekt het echte kenmerk op: een stijlblok dat middenin een commentaar ophoudt.

Drie controles die elkaar niet vervangen. `node --check` blijft nuttig voor
gewone tikfouten.

### Klikken in de browser: eerst een schermafdruk, dan de coordinaten daarvan

Nagemeten op 26-08-2026, met een knop op een bekende plek en een luisteraar die
opschreef waar de klik landde.

1. **Stel eerst vast of er iets is aangekomen, voor je iets over een knop
   concludeert.** Hang een luisteraar op en lees `composedPath()`:

   ```js
   window.__kliks = [];
   document.addEventListener("click", (e) =>
     window.__kliks.push({x: e.clientX, y: e.clientY, op: e.composedPath()[0]?.tagName,
                          echt: e.isTrusted}), true);
   ```

   Nul kliks betekent iets anders dan een klik die ergens anders landde, en dat
   verschil bepaalt wat je repareert. In mijn meting van 26-08-2026 kwam er
   zonder schermafdruk vooraf **geen enkel** event door (`visibilityState:
   hidden`), en landde dezelfde klik na een schermafdruk wel. De lovelace-sessie
   mat op diezelfde dag het tegenovergestelde: bij haar kwam er wél een echt
   event door, alleen op `HTML` in plaats van op de knop. Het is dus geen
   algemene regel maar iets om per geval vast te stellen. Een schermafdruk nemen
   is hoe dan ook verstandig: die maakt het tabblad wakker en geeft je meteen de
   coordinaten van punt 2.
2. **Klik in de coordinaten van die schermafdruk, niet in CSS-pixels.** De
   viewport was 1920 breed en de schermafdruk 1456; een klik op (531, 25) raakte
   de knop die op de schermafdruk op (531, 25) staat, niet die op CSS (531, 25).
3. **Die verhouding is geen vast getal.** In dezelfde sessie was hij eerst 0,817
   (1568 van 1920) en daarna 0,758 (1456 van 1920), want het venster was
   veranderd. Reken hem uit als schermafdrukbreedte gedeeld door
   `window.innerWidth`, of lees de plek gewoon van de verse schermafdruk af.

**Meet daarom bij voorkeur met `getBoundingClientRect` en `getComputedStyle` via
`javascript_tool`**, want die geven CSS-pixels en zijn niet van dit alles
afhankelijk. Klikken alleen waar het echt om de klik gaat.

De lovelace-sessie liep hier op dezelfde dag twee keer in, beide keren met de
conclusie "die knop doet niets".

## Meekijken in een echte installatie

`tools/ha.py` leest alleen. Hij zoekt een tokenbestand in `~/dev/tokens/` of
`C:\dev\tokens\`, met een bestand per installatie:

```
tokens/thuis.txt
tokens/jansen.txt
```

**Een installatie heet naar de achternaam, zonder voorvoegsel.** Dus
`jansen.txt` en niet `klant-jansen.txt`, en dat terugzien in de bestandsnaam, in
`HA_INSTALLATIE` en in de kop van elk stuk gereedschap. Een tussenvoegsel wordt
een streepje: `van-der-berg.txt`.

Adres op de ene regel, het long-lived token op de andere. **Die bestanden horen
op geen enkele remote, ook niet op een privérepo.** Maak op een nieuwe machine
gewoon een nieuw token aan in Home Assistant (Profiel → Beveiliging), of laat
`dev/tokens/nieuw.sh` het bestand aanleggen.

Er mogen **twee adressen** in: dat op het eigen netwerk en dat van buitenaf.
`ha.py` probeert ze in die volgorde en houdt het eerste dat antwoord geeft, vier
seconden per poging. Zo werkt hetzelfde bestand op locatie en op afstand. Let op
de poort: een kaal IP krijgt 8123 en http, een hostnaam krijgt https en zonder
poort erbij is dat 443, wat Nabu Casa gebruikt.

```
python tools/ha.py                                   # werkt de verbinding?
HA_INSTALLATIE=jansen python tools/ha.py         # een andere installatie
python tools/logboek.py 2026-08-29T06:00             # tijdlijn uit de recorder
python tools/besluiten.py                            # live meeluisteren
python tools/toestanden.py t.log plus=solix,p1_meter # elke toestandswissel, ook van
                                                     # entiteiten die het paneel niet kent
```

`plus=` bij `toestanden.py` is er sinds 23-09-2026: een batterij die door iets
anders gestuurd wordt laat dat alleen in haar eigen entiteiten zien, en het
paneel kent daar maar een handvol van. In de nacht van 22 op 23-09-2026 stonden
er daardoor geen sporen van de andere sturing in het log.

### Eén sessie kijkt naar één installatie

**De installatie waarop de sessie gestart is, is de installatie waar het over
gaat.** Vraagt de eigenaar naar "mijn laadpaal" terwijl de sessie op een klant staat,
dan bedoelt hij de laadpaal van die klant, want daar is hij mee bezig. Ga daar
niet zelf van afwijken, en kijk er nooit "even ook" naast bij een andere
installatie om te vergelijken.

Daar hoort dit bij:

- **Zet `HA_INSTALLATIE` niet zelf om** en gebruik geen `HA_TOKEN_FILE` om er
  omheen te gaan. `start.sh` zet `HA_VAST=1`, en dan weigert `ha.py` allebei met
  een uitleg. Wil de eigenaar uitdrukkelijk twee installaties vergelijken, dan mag
  `HA_VAST=0` ervoor, en zeg er dan bij dat je dat doet.
- **De entiteit-id's in de privénotities zijn die van de eigen woning.** Bij een
  klant heten ze anders. Zoek ze op met `/api/states` of via `logboek.py`, die
  het aan het paneel zelf vraagt, in plaats van ze aan te nemen.
- Klopt de installatie niet met wat de eigenaar wil, zeg dat dan en laat hem de sessie
  opnieuw starten. Stiekem omschakelen is erger dan een ronde vertraging.

Dit staat hier omdat het op 27-08-2026 misging: een sessie was op een klant
gestart en las toch de laadpaal van de eigen woning uit.

**Welke installatie het is, moet altijd zichtbaar zijn.** Elk stuk gereedschap
dat `ha` importeert schrijft daarom één regel naar stderr:

```
[ha] installatie: jansen (uit HA_INSTALLATIE)
```

Zonder dat schrijft een logger die een uur meeloopt stilzwijgend de verkeerde
installatie mee, en dat merk je pas achteraf. `HA_STIL=1` zet die regel uit voor
een script met een eigen kop. Voor een hele sessie kies je de installatie bij
het opstarten, in plaats van bij elk commando:

```
./start.sh coach jansen      # macOS
start.cmd coach jansen       # Windows
```

`logboek.py` vraagt aan het paneel zelf welke entiteiten erbij horen, dus hij
werkt bij een klant net zo goed als thuis. Geef de history-API altijd een
`end_time` mee, anders krijg je maar één dag vanaf de starttijd terug.

De besluiten van de coach staan **niet** in de recorder; die gaan over de
eventbus. Wil je die van een laadbeurt hebben, laat dan `tools/besluiten.py`
meelopen terwijl het gebeurt.

## Waar we staan

De lopende stand, de openstaande vragen en wat er in het echt nog beproefd moet
worden staan in de privérepo ernaast: `../notities/domotiapp-coach/`. Die staat
er niet in deze publieke repo omdat er IP-adressen, klantgegevens en
meterstanden in staan. **Lees dat bestand aan het begin van een sessie.**

Staat die map er niet, dan werk je op een machine waar alleen deze repo is
uitgecheckt. Zeg dat dan, en vraag om `Sven2410/dev` erbij.
