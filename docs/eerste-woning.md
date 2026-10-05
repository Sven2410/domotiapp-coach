# De feedback van de eerste woning, 22-09-2026 (v0.77.0)

Uit `CLAUDE.md` gehaald op 24-09-2026, zodat dat bestand kort blijft. De eisen
van de eigenaar en de werkafspraken staan daar en gaan boven alles hier.
Komt er bij een uitgave iets bij over dit onderwerp, schrijf het dan hier.

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
(sinds v0.102.3) onder welke prijs bijkopen loont; daaronder per uur de tijd, de prijs, de
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

**Kwartierprijzen in de pop-up** (v0.88.1). De eigenaar op 23-09-2026: "hij moet
kwartierprijzen laten zien als dat is ingesteld, geen uurprijzen." Het rekenen
kon het al: de planner en de batterij werken per prijsblok, en met de uurprijs
op alle vier de kwartieren komt er precies hetzelfde uit als per uur (proef 62
in test_planner.py); met echte kwartierprijzen pakt hij de goedkoopste
kwartieren. Nu ook het scherm: de grafiek tekent een staafje per blok en heet
dan "Prijs per kwartier" (`stap` in `prijsBalken`), en de lijst eronder houdt
een regel per uur (`perUur` in prijsgrafiek.js, `paalPerUur` in
plan-ahead-sheet.js, en in `batterijVooruit`), met "in 2 van de 4 kwartieren"
als hij maar een deel laadt. **De Zonneplan-integratie in Home Assistant geeft
alleen uurprijzen** (de `forecast` van `sensor.zonneplan_current_electricity_tariff`
is een rij per uur); evcc haalt zijn kwartieren zelf. Nord Pool met kwartieren
wordt als kwartieren gelezen (test_coach.py, na de prijslijstproeven).

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
  **Het veld (v0.106.4).** De eigenaar op 05-10-2026, op een iPhone in deze
  woning: "Kan die 50% niet aanpassen. Ik kan er 30 van maken, maar verandert
  hem weer naar 50." Twee fouten: een ander getal ging nooit naar de coach
  zolang hij al leegliep, en het veld keek naar `document.activeElement`,
  dat binnen de shadow root het paneel zelf is (in de preview nagemeten:
  `DOMOTIAPP-COACH-PANEL`) en nooit het veld, dus elke ververs overschreef
  wat er getypt werd. Nu `syncLeegVeld_` (focus in de eigen shadow root, of
  ingetypt en nog niet doorgegeven) en `zetLeegTot_` op de change van het
  veld: loopt hij al leeg, dan gaat het nieuwe getal meteen naar de coach.
  Proef "leegladen: wat de bewoner in het veld zet" in test_rapport.mjs.
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

## In geld (v0.101.0)

De eigenaar op 28-09-2026: "ik wil op het historie overzicht duidelijk hebben wat
ik heb bespaard die dag, totaal uitgegeven en totaal bespaard. Maak een mooi
overzicht, want de klant wil natuurlijk ook zijn investering weten, wanneer hij
het heeft terugverdiend." En: "stel alles goed op elkaar af." Dat laatste deel is
er in v0.101.1 weer uit, zie onderaan.

**In geld** (kaart onder de grafiek, en dezelfde tegels in het rapport): drie
getallen, uitgegeven (stroom van het net, gas en water, min wat teruglevering
opbracht; onder nul heet het verdiend), bespaard, en wat het zonder zon, batterij
en coach gekost had; een balk met die verdeling; en twee kolommen. De som staat
in `geld.js` (`balans`), zodat Historie en het rapport (`reportData_`) hem delen:
bespaard is het verbruik tegen de prijs van het net min wat de stroom werkelijk
kostte, plus wat de coach won door te wachten, in drie delen die samen precies
het geheel zijn: de coach (de beurten onder Bespaard), de thuisbatterij (haar
kasboek, `battery_state.earned_days`, `accuVerdiend`) en de zon (de rest).

**Salderen rekent in het paneel nu zoals in de coach** (`salderen`, `prijsOp` in
geld.js tegenover `_salderen`, `_tariff` en `_prices` in coach.py): tot 1 januari
2027 is een teruggeleverde kWh de inkoopprijs waard min de terugleverkosten (bij
dynamisch ook min de opslag). Tot v0.101.0 rekende Historie met de
terugleververgoeding; bij de eigenaar gaf dat 1,9 cent per kWh waar de coach 18,9 rekende.

**Geen terugverdientijd (v0.101.1).** In v0.101.0 stond onder In geld een kaart
Terugverdiend: per investering een balk en een datum, met de aankoopprijs van de
thuisbatterij bij Apparaten (sinds v0.73.0 op haar kaart) en de prijs van de
zonnepanelen en de coach op Installatie onder Investeringen. De eigenaar op
29-09-2026: "haal het invullen van de kosten van de panelen weg en de batterij.
Dat is niet verdedigbaar voor mij als ik een terugverdientijd heb opgegeven bij
klanten en die wordt niet gehaald." Alles is eruit: de velden, de kaart, de
tabel in het rapport en de regels "Terugverdiend" op de kaart van de batterij.
Wat blijft is wat gemeten is, zonder belofte: In geld, en "Opgeleverd" op de
kaart van de batterij (`earned` in de stand van de coach, `opgeleverdTekst` in
battery.js). Een oude `investments` valt bij het laden weg (`_prune` in
storage.py), een oude `purchase_price` bij de volgende opslag (`REMOVE_EXTRA`).
Proef "geen terugverdientijd" in test_rapport.mjs houdt de woorden uit de bron.

**De thuisbatterij in Historie (v0.101.2).** Bij de eigenaar op 29-09-2026 om 10:00 stond er
onder In geld "Door je zon € -0,56" naast "Door je thuisbatterij € 0,60". Alle
zeven bedragen op het scherm zijn nagerekend en kwamen precies terug: net 2,506
kWh (€ 0,6057), gas € 0,0971, uitgegeven € 0,6998, bespaard € 0,0388, zonder
€ 0,7386. Twee fouten. Verbruik was opwek plus inkoop min teruglevering, dus de
nacht op de batterij (0,77, 0,57, 0,56, 0,57 en 0,15 kWh per uur, om 04:00 op
5%) zat er niet in: 2,65 kWh verbruikt waar het huis er 5,26 gebruikte. En de
zon was de rest (bespaard min het kasboek), dus kreeg hij het hele kasboek als
min. De eigenaar: "repareer alles."

Nu haalt `fetchBattery` (statistics.js) per batterij wat ze netto opnam: de twee
tellers van een kWh-meter, anders het gemiddelde van de vermogenssensor met een
teken, anders van de losse sensoren voor laden en ontladen; per uur, over een
jaar per dag met van vandaag alleen de verstreken uren. `huisMetAccu`
(views/history.js) maakt daar per vak verbruik van (eigen zon plus inkoop min
wat de batterij opnam), en van het net naar het huis (de batterij laadt eerst
uit de zon, zoals het energiedashboard het verdeelt). Verbruikt, zelfvoorzienend
en de balken rekenen daarmee; de legenda zegt "Eigen zon en batterij".

In geld rekent de zon nu zelf uit (`balans` in geld.js): de eigen zon tegen de
inkoopprijs, teruglevering tegen wat die opbracht, min wat de zon die de
batterij in ging minder waard was dan zelf gebruikt; het kasboek komt erbij in
plaats van eraf. Dat laatste telt de coach per stap naast het kasboek
(`zon_in_accu` in batterij.py, `solar_stored_days` en `solar_stored_from` in
`battery_state`). Voor de uren van voor die telling schat Historie het uit het
vak zelf: wat de batterij opnam, hooguit de eigen zon (`zonInAccu`). Met de uren
van 29-09 tot 10:00: verbruikt 4,37 wordt 6,85 kWh, zelfvoorzienend 22,8 wordt
50,7%, "Door je zon" € -0,28 wordt € 0,24, bespaard € 0,25 wordt € 0,77.

Wat blijft: het kasboek telt alleen sinds de coach de batterij stuurt. Een
batterij die hij niet stuurt telt in het verbruik wel mee, maar wat ze bespaarde
niet. En "Zonder" in geld en verbruikt maal de prijs kunnen een paar cent
verschillen: het kasboek rekent met de metingen van de coach, het verbruik met
de uurgemiddelden van Home Assistant (op 29-09 2,48 tegen 2,61 kWh ontladen).

