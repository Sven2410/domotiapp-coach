# Onderverdeelkasten en groepen

Uit `CLAUDE.md` gehaald op 24-09-2026, zodat dat bestand kort blijft. De eisen
van de eigenaar en de werkafspraken staan daar en gaan boven alles hier.
Komt er bij een uitgave iets bij over dit onderwerp, schrijf het dan hier.

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

**Een batterij op dezelfde groep neemt de ruimte van de paal niet in** (v0.88.2).
In de eerste woning op 23-09-2026 om 17:08 laadde de Anker 3,2 kW zon op L3 van
de garage (14 A) en zei de paal "de groep Garage is te zwaar belast"; bij
ontladen hetzelfde. Een batterij die de coach stuurt wijkt voor de paal
(ontladen stopt, `met_paal`; laden op nul op de meter zakt als de auto de zon
neemt), dus `_batterij_wijkt` in coach.py trekt haar stroom op haar eigen fase
af van elke zekering in haar keten, en van de hoofdaansluiting, bij het lezen
voor de paal. Niet bij `netladen` en `max-laden` (dan wijkt hij niet) en niet als
de coach hem niet stuurt. En zakt een batterij meer dan `BATTERIJ_DALING_W`,
dan zet dat `_daling` net als een paal die omlaag gaat: om 17:09 stond de Anker
stil en L3 op 0 A, en de mediaan van 90 s droeg nog 14 A. De snelle
zekeringcontrole leest de sensor zelf en blijft het vangnet voor de seconden
waarin de batterij nog wijkt. Proef 96 in test_coach.py.

**Onderverdeelkasten en groepen, elk met een vinkje voor de kWh-meter** (v0.101.5).
De eigenaar op 29-09-2026: "Groepen met een eigen zekering moet even anders. Dat
moet heten onderverdeelkast. Bij mij thuis heb ik een hoofdkast 3x25A en dan een
onderverdeelkast in de lounge. Bij de eerste woning is dat hetzelfde, alleen is de
lounge een garage." Met een vinkje "deze onderverdeelkast heeft een eigen
kWh-meter", en pas dan L1, L2 en L3; daaronder een eigen kopje Groepen met "hangt
onder" en hetzelfde vinkje.

Op Installatie staan nu twee blokken, Onderverdeelkasten (`#kasten`) en Groepen
(`#circuits`), uit dezelfde lijst `installation.circuits`. Elke rij heeft er twee
velden bij: `kind` ("kast" of "groep") en `meter` (true of false), in `_CIRCUIT` in
websocket.py. De coach rekent met elke zekering zoals hij deed; `kind` geeft alleen
het woord in een zin ("De onderverdeelkast Lounge is te zwaar belast", `soort` op
`Circuit` en `_soort` in planner.py, de sensorwacht in `_sensoren`). Zonder
eigen kWh-meter gaan er geen sensoren mee bij het opslaan (`payload_` in
views/installation.js); in het klad blijven ze staan, zodat het vinkje per ongeluk
uit en weer aan niets kost. Een kast hangt onder de hoofdkast, of onder een andere
kast als die er is; een groep onder de hoofdkast, een kast of een groep. Bij
Apparaten heet de keuze nu "Hangt aan", met de hoofdkast en elke kast en groep met
zijn soort erbij.

Van voor v0.101.5 staat er geen soort bij, en `kastenIndelen` deelt in: een kast
is wat onder de hoofdkast hangt en zelf iets draagt of een meter heeft. Bij de
eigenaar wordt de lounge (20 A, zonder meter) een kast en laadpaal (20 A, 3 fasen)
en thuisbatterij (16 A, 1 fase) groepen eronder; in de eerste woning wordt de
garage met zijn meter een kast. Dat gebeurt in het klad én in de opgeslagen kopie,
zodat het scherm niet meteen op "niet opgeslagen" staat. Proeven in
test_rapport.mjs (het scherm, het indelen, het opslaan, Apparaten) en proef 117
in test_coach.py (de zinnen).

## De batterij plant mee met de paal op haar groep (v0.164.0)

Tot nu toe kende alleen de regelaar de zekeringen van een batterij (`_laadruimte_w`): op het moment
zelf krijgt ze wat de paal en de groep overlaten. Het uurplan van de batterij rekende met haar volle
laadvermogen. In een klantwoning plande ze op 26-10-2026 voor 02:00-05:00 2,5 kW van het net op L3,
terwijl de paal op dezelfde kast van 3x16 A dan 13 A per fase plande. De regelaar gaf haar daar hooguit
200 W, dus het plan beloofde goedkope kWh die niet kwamen, en de bewoner zag 11,5 kW op een kast van 16 A.

Nu geeft de coach het uurplan per blok van het plan van een paal mee hoeveel watt de zekeringen nog
laten (`_laadruimte_plan` in coach.py, `laadruimte` en `_met_laadruimte` in batterij.py). De regels zijn
die van de regelaar: alleen een paal die voor gaat in de voorrang bij planningen, alleen een zekering
die ze delen, alleen een zekering die de coach meet (de hoofdaansluiting met fasesensoren, een groep met
een meter), met dezelfde marges. De paal telt met de stroom van zijn plan op elke fase; bij één fase
weet de coach niet welke, dus telt hij die van de batterij. Het huis op die groep telt niet mee, want
dat is vooraf niet bekend. De som kiest dan zelf: de batterij schuift naar de goedkope uren die de paal
overlaat. De paal houdt zijn voorrang; hem omlaag zetten als dat samen goedkoper is, doet de coach nog niet.

Proef 60 in test_batterij.py, 205 in test_coach.py, en in het virtuele huis `groep-paal-en-batterij`
(de batterij nu ook in de kast, `batterij_in_groep`). Daar scheelde het 2 cent en vijf opdrachten,
omdat de regelaar het al opving; het verschil zit vooral in een plan dat klopt.

## Ook zonder meter, en twee palen samen (v0.164.1)

Sven, 26-10-2026, na v0.164.0: "Ik wil dat het ook universeel is he. Dat is een harde afspraak." Bij het
nalezen bleek de batterij een groep zonder kWh-meter over te slaan (`_laadruimte_w`, `_laadruimte_plan`):
daar laadde ze op haar volle vermogen naast een paal die voor ging, 13 + 10,9 A op 16 A, en niemand
greep in. Twee dingen speelden mee:

- Een groep zonder meter telt nu met wat er bekend is, zoals `ruimten` in planner.py het voor een paal
  al deed: de zekering min de marge min wat wie voor gaat trekt, geen huis.
- Een toezegging is wat er bovenop de meting bijkomt. Zonder meter is dat niet genoeg: een paal die al
  op 13 A loopt zegt 0 toe. Daarom houdt de coach per paal ook bij wat hij in totaal trekt
  (`_paal_stroom`, `totaal` in `_toezeggingen`), en rekent een groep zonder meter daarmee
  (`_hogere_toezeggingen(..., totaal=True)`). Wat de batterij zelf laadt komt er alleen bij een meting
  weer bij, want alleen daar zat het in.

In het plan tellen twee palen op dezelfde zekering samen: tot dan nam de coach de laagste ruimte per
paal apart, en lieten twee palen van 6 A op 16 A de batterij 8 A in plaats van 2.

Proef 206 in test_coach.py (zonder meter, twee palen, de batterij op L1, L2, L3 en drie fasen, kast onder
kast), en `groep-paal-en-batterij-zonder-meter` in het virtuele huis: op de oude code 22,6 A op de kast,
nu hoogstens 14,9.

Nog niet: het plan van een paal die na een batterij komt kent haar uurplan niet, en boiler en airco
plannen vooruit nog zonder de paal.

## Een groep zonder meter, gemeten via de apparaten die erop hangen (v0.165.0)

De bewoner van een klantwoning op 26-10-2026: wasmachine en droger zitten samen op één groep, elk op
een eigen plug, en een eigen meter voor die groep past niet meer in de kast. Sven: "Onder Groepen laat
je het vinkje van aparte kWh-meter dan uit, maar voeg je per groep een of meerdere apparaten toe."

Zo staat het nu. Een groep of kast zonder eigen meter krijgt een lijst `devices`: per apparaat met een
vermogenssensor (geen laadpaal en geen thuisbatterij, die rekent de coach al zelf) de fase waar het op
hangt. Een apparaat hoort bij hooguit één groep (`_apparaat_in_een_groep` in websocket.py). De som
(`groep_apparaten_amps` in planner.py, `readCircuits` in data-source.js) telt overal waar een meter
telt, als het deel van het huis dat de coach kent:

- de belasting per fase op het overzicht, met "Gemeten via Wasmachine en Droger; wat er verder op deze
  groep hangt ziet de coach niet.", en de lastbewaking (`async_current_load` in monitor.py);
- een paal op die groep (`known_amps` op `Circuit`), en een batterij, boiler of airco (`_laadruimte_w`);
- een eigen melding (`_async_groep_vol`): staat de som `GROEP_VOL_DUUR` (3 minuten) boven
  `GROEP_VOL_DEEL` (90%) van de zekering, dan één melding, en pas weer na een keer onder
  `GROEP_VOL_WEER` (80%).

Zegt één van de sensoren niets, dan is er geen som: een som zonder een van de apparaten zou de groep
leger laten lijken dan hij is. Een meter wint altijd van de apparaten.

De coach schakelt niets uit. Sven: "je wilt niet dat je wasmachine ineens uitschakelt toch?" Uitschakelen
is een vraag voor later.

Gemeten in die woning van 16-10 tot 26-10-2026: wasmachine hoogstens 2260 W, droger 912 W, samen
hoogstens 2954 W (12,8 A op 16 A). Daar komt de groep dus niet aan de grens.

Proeven: test_planner.py (de som, op één en drie fasen, een plug die niets zegt, een paal op zo'n groep),
207 in test_coach.py (de melding onder en boven de grens, de batterij, de lastbewaking), en
test_rapport.mjs (het overzicht en het scherm Groepen).

## Belastingen in je huis, per kast en groep (v0.168.0)

Sven op 27-10-2026, met een tekening erbij: "Hoofdaansluiting 3x25A, Groepen onder hoofdaansluiting
(inklapbaar) ... Onderverdeelkast Garage 3x16A, Groepen onder onderverdeelkast Garage (inklapbaar)". Tot dan
heette de kaart "Belasting per fase" en stonden de hoofdaansluiting en elke kast en groep plat onder elkaar.

- **De kaart** (`updatePhases_` in views/overview.js): de hoofdaansluiting met zijn fasen en "3x25 A", en
  inklapbaar de groepen die eronder hangen. Daaronder de kop Onderverdeelkast(en), per kast zijn fasen en
  inklapbaar zijn groepen. Een groep hoort bij de eerste kast boven hem; een kast onder een kast staat als eigen
  blok, met "onder Garage". Ingeklapt is de standaard; wat de kijker openklapt onthoudt zijn browser
  (`dac-belasting-open`), en een blok met een groep boven de waarschuwingsgrens gaat vanzelf open.
- **Niet gemeten**: een kast of groep zonder meter en zonder apparaten blijft staan, met "Niet gemeten"
  (`measured` in `readCircuits`). Hij telt niet mee in de belasting.
- **Stroom en spanning van een apparaat** (`entities.current`, `entities.voltage`, Apparaten, onder de
  vermogenssensor; voorgesteld uit hetzelfde apparaat in Home Assistant, `meetVanzelf`). Op een groep zonder
  meter: de gemeten stroom, of het vermogen gedeeld door de gemeten spanning van de groep. Zonder spanning en
  niet bij elk apparaat een stroom staat er geen ampère en geen volt, alleen het vermogen, en rekent de balk op
  230 V. Dezelfde som in `groep_apparaten_amps` (planner.py), zodat de melding bij 90% en `_laadruimte_w`
  hetzelfde getal hebben.
- **De fase van een groep van één fase** (`phase`, Installatie): tot dan heette zo'n groep altijd L1, ook de
  groep van een batterij op L3. Zonder keuze de fase van de batterij die eraan hangt. De sensoren blijven onder
  "l1" staan; alleen het label verandert. Sinds v0.169.0 zonder stille L1, zie hieronder.
- **Het teken**: een stroom zonder teken op een regel met een negatief vermogen krijgt het teken van het
  vermogen. Er stond "4,9 A, -1,15 kW".
- **Hangt aan**: staat een apparaat bij een groep onder Groepen, dan hangt het daaraan, ook voor de
  zekeringbewaking (`_groepen_keten`), en staat dat bij het apparaat zonder keuzelijst. Tot dan zei "Hangt aan"
  Hoofdkast voor de droger in de groep Wasmachine & Droger.

Gemeten op 390, 320 en 280 px zonder overloop.

## Een fase per apparaat, gekozen en niet aangenomen (v0.169.0)

Na v0.168.0 stond in een klantwoning de groep Wasmachine & Droger op L1, en de groep van de batterij ook,
terwijl die batterij op L3 zat. Sven op 27-10-2026: "hoe weet de coach dat dit fase 1 is? Die heb ik bij mijn
apparaten namelijk nooit ingevuld. Zou bij álle apparaten er dus voor kiezen om handmatig de betreffende fase in
te vullen." De coach vulde het zelf in, op vier plekken: bij Installatie, bij het toevoegen van een apparaat aan
een groep, op de kaart en in de som. De batterij in die woning hing bovendien aan de kast (`circuit`), niet aan
haar groep, en dan vond de regel van v0.168.0 haar niet.

- **Hangt op fase bij elk apparaat** (`phase`, onder Sturen naast Hangt aan; `faseHtml_` in views/devices.js):
  L1, L2, L3, Drie fasen of Weet ik niet, standaard Weet ik niet. Niet bij een laadpaal: die laadt op de fasen
  van de auto. De batterij had dit veld al (`battery.phase`); dat blijft gelden tot de bewoner hier iets kiest,
  en volgt dan mee.
- **Eén regel** voor wat een apparaat is: `apparaat_fase` in planner.py en `apparaatFase` in devices.js. De
  keuze bij het apparaat, anders `battery.phase`, anders de fase bij een groep van drie fasen (daar was een
  keuzelijst, dus die was gekozen). Die bij een groep van één fase was nooit te kiezen en telt niet. Bij
  Groepen staat de fase van een apparaat alleen nog te zien.
- **De fase van een groep van één fase** (`groep_fase` in planner.py, `groepFase` in devices.js): Op fase bij
  de groep, en zonder keuze de fase van de apparaten waarvan de keten door de groep loopt (`groepen_keten`), als
  ze het eens zijn. Anders onbekend: op de kaart "L?" met "Fase onbekend", in de melding van de lastbewaking
  "onbekend (Was)". Spreken de apparaten elkaar of Op fase tegen, dan zegt Installatie wie.
- **De som op een groep van drie fasen** (`groep_apparaten_amps`, `readCircuits`): een apparaat op zijn fase,
  op drie fasen een derde van zijn vermogen op elke fase (of zijn gemeten stroom), en onbekend op de zwaarste
  fase van de rest. Zo deed de batterij het al.
- **Nagegaan**: een groepsom telt nergens bij een fase van de kast of de hoofdaansluiting op. De lastbewaking
  (`async_current_load`), `_laadruimte_w` en `ruimten` nemen elke zekering apart, met zijn eigen meting of som.
