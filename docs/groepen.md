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
