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
   het rapport. Sinds v0.116.0 staat op het scherm alleen Zelfvoorzienend;
   Zelf gebruikt staat nog in het rapport (zie "Historie overzichtelijk").
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
getallen (sinds v0.116.0 twee, zie "Historie overzichtelijk"), uitgegeven (stroom van het net, gas en water, min wat teruglevering
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

**Laden is inkopen (v0.107.0).** Door je thuisbatterij is sindsdien wat ze
opleverde: pas als ze ontlaadt, min wat die stroom kostte (`realized_days`). Wat
er in de periode aan stroom in de batterij bij kwam is wel uitgegeven, staat onder
Uitgegeven als "Waarvan nog in je batterij" (of "En uit je batterij, eerder
betaald" als er meer uit ging dan in), en gaat van zonder af; de balk begint met
wat je uitgaf aan wat je gebruikte, zodat hij op zonder uitkomt. Zie
`docs/batterij.md` onder Het kasboek. Dezelfde uitgave: de twee kolommen onder In
geld waren minstens 240 px breed en liepen op 280 px 14 px over de kaart
(`minmax(min(240px, 100%), 1fr)`).

Wat blijft: het kasboek telt alleen sinds de coach de batterij stuurt. Een
batterij die hij niet stuurt telt in het verbruik wel mee, maar wat ze bespaarde
niet. En "Zonder" in geld en verbruikt maal de prijs kunnen een paar cent
verschillen: het kasboek rekent met de metingen van de coach, het verbruik met
de uurgemiddelden van Home Assistant (op 29-09 2,48 tegen 2,61 kWh ontladen).

**Batterij geladen en ontladen (v0.126.0).** De eigenaar op 16-10-2026: "bij
historie zie ik nu niet de thuisbatterij van zoveel geladen en zoveel
ontladen kan dat er ook nog in?" Twee tegels onder Energie, na Naar het net en
voor Zelfvoorzienend, en dezelfde twee vakjes in het rapport; bij het
aanwijzen van een balk die van dat uur of die dag. Ze staan er alleen als de
batterij in de periode samen minstens 0,05 kWh deed (`accuTegels_`), en tellen
nergens bij op: wat erin ging kwam van de zon of van het net.

De bron is dezelfde als die van het verbruik (`fetchBattery`), die nu per uur
ook `erin` en `eruit` apart geeft, zodat geladen min ontladen precies is wat
Verbruikt eraf haalt. Tellers en losse sensoren voor laden en ontladen meten
dat apart. Eén vermogenssensor met een teken geeft per uur alleen netto, en
wordt daarom ook over een jaar per uur gevraagd: per dag valt middag laden en
avond ontladen tegen elkaar weg. Laden en ontladen binnen één uur ziet die nog
steeds niet.

Het energiedashboard van Home Assistant kan andere getallen geven, want daar
kiest de bewoner zelf welke sensoren erin staan, vaak de tellers van de
batterij zelf. Bij de eigenaar op 14-10-2026: het energiedashboard (de
tellers van de Anker) 12,5 kWh geladen en 5,9 ontladen, het gemiddelde van de
twee vermogenssensoren waarmee Historie rekent 13,4 en 5,7; op 15-10 11,2 en
13,2 tegen 12,4 en 14,6. De tellers van de batterij zelf (`accu_in`,
`accu_out`) gebruikt Historie niet: die meten aan de accukant.

## De tijdlijn (v0.115.0)

De eigenaar op 11-10-2026: "Ik wil kunnen zien wat de coach en de aanstuurbare
apparaten hebben gedaan ... de geschiedenis kort en krachtig", en over de vorm:
"een tijdlijn inderdaad en als je op de tijdlijn klikt een korte tekst. Het moet
visueel sterk zijn. Niet teveel tekst, alles heel overzichtelijk." Twee weken
terug is genoeg. Op 12-10-2026 nog eens: "zoals de verloop van wat hij heeft
gedaan".

**Waar hij staat.** Een kaart onder de energiegrafiek in Historie, alleen bij
Dag: een week aan balken leest niemand meer in één oogopslag. Een baan per
apparaat dat de coach stuurt (laadpaal, thuisbatterij, vaatwasser, wasmachine,
droger, boiler; `balkSoort` in tijdlijn.js), de uren eronder, een streep op nu,
en de meldingen en verslagen van die dag als stippen erboven (kritiek rood).
Een tik op een stuk of een stip zet een korte tekst eronder: wanneer, wat,
hoeveel, en waarom. Wie de coach niets laat sturen ziet de kaart niet.

**Wat er gebeurde komt uit Meldingen.** Elk besluit staat daar al op het moment
dat het veranderde (`_async_noteer` in coach.py), en daar bouwt `tijdlijn` de
stukken uit: een stand loopt tot het volgende besluit dat iets anders zegt, de
stand van gisteravond loopt door in de ochtend, en vandaag houdt op bij nu. De
tekst alleen is te los om op te bouwen, dus staan bij een besluit sinds v0.115.0
ook het apparaat, de regel, de stand en of er geladen wordt (`extra` in
`MeldingenStore.async_add`). Een regel van daarvoor wordt herkend aan de naam
vooraan, zodat de weken van voor de update er meteen staan. Proef 151 in
test_coach.py houdt bij dat elke plek die een besluit noteert het apparaat
meegeeft.

**De kleur is een meting.** Oranje is eigen stroom, blauw het net, net als in de
grafiek erboven. De eerste opzet (tak `historie-tijdlijn`, 11-10-2026) kleurde
een laadbeurt naar de regel van de coach, en dat loog: bij de eigenaar stond
12:08 tot 13:47 als "vooral op zon" (82% van de tijd een zonregel), terwijl de
meter per kwartier 3,7 van de 6,6 kWh van het net zag. Nu komt de kleur van een
stuk waar stroom door liep (laden, een programma, een boiler met stroom erop)
uit de kwartieren van de eigen opslag (`history/quarters`): per kwartier wat
het apparaat trok en wat er van het net kwam, tot wat het apparaat trok. Dat is
dezelfde som als de coach per ronde maakt (`_geld_bij`: het huis krijgt eerst de
zon). Meer dan de helft van het net is blauw. Met een thuisbatterij is wat niet
van het net kwam zon of batterij, want de meter ziet het verschil niet, en zo
heet het dan ook ("Eigen zon en batterij", zoals in de grafiek). Een gesplitste
meter en een meter met een teken, in beide richtingen: `netReeks`.

Nagerekend op de beurt van de eigenaar van 11-10-2026: de kwartieren zeggen
15,57 kWh, waarvan 12,23 van het net; het eigen kasboek van de coach zei
15,53 kWh met 13,19 van het net. Bij de vaatwasser op 10, 11 en 12-10: 10%, 65%
en 60% van het net tegen 3%, 60% en 56% in het kasboek. Binnen een kwartier
middelen afname en zon uit, dus de tekst zegt "ongeveer", op vijf procent.

Aan zonder dat er iets liep (een auto die niet wakker werd, een vol vat) is geen
zon en geen net: een gestippelde rand, "er liep niets". Zonder kwartieren valt
de kleur terug op de regel en zegt de tekst "vooral op zon".

**De reden bij een klik is de reden die het langst gold.** Wekken en nog even
doorladen op de laagste stand (`+wake`, `+hold`) zijn bijzaken; anders stond
"hij biedt even 16 A aan om hem wakker te maken" bij elke laadbeurt als de
reden. Een stuk korter dan drie minuten tussen twee stukken van dezelfde stand
gaat erin op (`samenvoegen`).

**Niet in het echt gezien:** de kaart met de eigen gegevens van een installatie;
de preview draait op een verzonnen dag (`?licht=1` en `?phone=390` gemeten, 280
px zonder overloop). Met de gegevens van de eigenaar van 10 tot 12-10 is de som
in node nagerekend, niet op het scherm.

## Historie overzichtelijk (v0.116.0)

De eigenaar op 13-10-2026, bij een batterij op € 0,00 bespaard waarvan de uitleg
in een alinea van zes zinnen stond: "ik wil alles zo duidelijk mogelijk hebben en
zo kort mogelijk", en daarna: "kijk ook waar verbeterpunten liggen het moet
overzichtelijk zijn. Het moet niet zo zijn dat het gigantisch veel wordt alle
datat dat mensen het niet meer snappen." En: "periode onderwerp en verloop moet
een drop down worden wat je kiest". Hij koos alle vier de voorstellen:

- **Bovenaan.** De inleiding is één zin. Onderwerp, Periode en Verloop in het
  rapport zijn uitklaplijsten in plaats van rijen knoppen. Een verloop dat bij de
  periode niet kan is uitgegrijsd, en een eerdere keuze valt terug op wat bij de
  periode past (`korrel_id`). De regel "ongeveer 768 regels over 8 apparaten" is
  weg. Kort en uitgebreid rapport zitten achter één knop Rapport.
- **Energie.** Vier tegels en één percentage: Zelfvoorzienend. "Zelf gebruikt"
  leek er te veel op en staat alleen nog in het rapport. "Hele periode" boven de
  tegels is weg.
- **In geld.** Twee getallen: "Zonder zon, batterij en coach" was Uitgegeven plus
  Bespaard, en is weg van het scherm en uit het rapport. De uitleg is per zin één
  ding. Met salderen staat erbij wat zelf gebruiken of opslaan per kWh scheelt:
  de stroomprijs min wat terugleveren opbrengt (`prijsOp`), bij de eigenaar
  € 0,05. Dat is het antwoord op de vraag waarom de batterij zo weinig bespaart.
- **Beurten** (heette Bespaard; botste met Bespaard in In geld). Drie tegels:
  Bespaard (met zon en wachten eronder), Betaald, en Geladen of Verbruikt (met zon
  en batterij eronder). Eén zin uitleg (`woorden` in savings.js), en één lijst met
  Wanneer, Apparaat, kWh, Betaald, Bespaard. De tabel per apparaat en de kolommen
  zon, accu, ijkpunt en door zon staan alleen nog in het uitgebreide rapport.

Wat de batterij bij de eigenaar opleverde, nagerekend op 13-10-2026. De kWh komen
uit de kwartieren van de vermogenssensoren van de batterij, de bedragen uit
`realized_days`:

| dag | erin | eruit | opgeleverd |
|---|---|---|---|
| 10-10 | 9,65 kWh | 8,28 kWh | € 0,13 |
| 11-10 | 2,21 kWh | 1,55 kWh | € 0,005 |
| 12-10 | 14,29 kWh | 7,98 kWh | € 0,22 |

Op 11-10 nam de auto de zon (15,6 kWh), en zolang de paal laadde stond de
batterij op alleen zonneladen. Met salderen verdient een batterij pas als er meer
dan 78% terugkomt (€ 0,1890 / € 0,2417 bij dat contract). Over 12 en 13-10 samen
ging er 16,0 kWh in en kwam er 13,0 uit, voor € 0,07.

**v0.116.1, dezelfde avond.** De eigenaar, bij Week: "waarom is de tijdlijn weg die
wil ik wel behouden", "check pijltje bij verloop die komt er buiten" en "leg eens
beurten uit dat snap ik niet".

- **De tijdlijn staat ook bij Week**: zeven dagen naast elkaar, de dag langs de as
  en een lijntje per dag (`TIJDLIJN_PERIODES` in history.js, `meerDagen` in
  tijdlijn.js). De tekst bij een klik noemt dan de dag: "za 10 22:30 tot zo 11
  01:40". Bij Maand en Jaar staat er "De tijdlijn staat bij Dag en Week."; zonder
  die regel leek hij weg.
- **Het pijltje van een uitklaplijst** stond naast de lijst, omdat het omhulsel zo
  breed werd als het opschrift erboven. Nu is het zo breed als de lijst.
- **Beurten** begint met wat een beurt is: "Een beurt is één keer dat de coach een
  apparaat liet draaien, zoals de auto laden of de vaatwasser."

## Per apparaat (v0.121.0)

De eigenaar op 15-10-2026: "ik wil ook het energieverbruik per apparaat kunnen zien in
historie zoals het HA energy dashboard snap je? En dat per dag per jaar etc moet op die
pagina's er bij komen."

Onder de grafiek van Energie staat bij elke periode de kaart **Per apparaat**, zoals
"Afzonderlijke apparaten" in het energiedashboard van Home Assistant (`paintApparaten_`
in views/history.js):

- **Gestapelde balken** over dezelfde vakken als de grafiek erboven: bij Dag per uur, bij
  Week en Maand per dag, bij Jaar per maand. Elk apparaat houdt zijn kleur op de volgorde
  van Apparaten en niet op grootte (`--dac-app-1` tot en met 6 in theme.js, de reeks van
  de dataviz-richtlijn zonder rood en groen, die zijn van de status). Vanaf het zevende
  apparaat is het grijs: "Overige apparaten" (`apparaatReeksen`).
- **Een lijst** eronder, van groot naar klein: per apparaat zijn kWh en zijn deel van wat
  het huis verbruikte, en onderaan "Rest van het huis", wat de apparaten samen niet
  verklaren. Aanwijzen of tikken zet de lijst en de kop op dat ene uur, die dag of die
  maand, zoals bij gas (`paintAppLijst_`).
- De thuisbatterij staat er niet in: die verbruikt niet, die schuift op.
- Het deel en de rest staan er alleen als het huisverbruik bekend is (met een
  opwekteller) en de apparaten samen niet meer dan 2% boven het huis uitkomen; dezelfde
  regel als in het rapport. Anders staat er waarom.
- Een apparaat zonder energieteller wordt geschat uit zijn vermogen en krijgt een ≈.

**De schatting zelf is rechtgezet.** `fetchDevices` in statistics.js nam het gemiddelde
vermogen van een heel vak maal 24 uur, of maal 730 voor een maand. Een dag die nog liep
telde daardoor alsof hij om was, en het rapport zag apparaten die samen meer
verbruikten dan het huis. Nu komt het gemiddelde per uur (over een jaar per dag, en van
vandaag alleen de uren die voorbij zijn), net als bij de batterij, en legt `perVak` het
in de vakken van de grafiek. Het rapport rekent daarmee ook per vak met de prijs van dat
vak (`deviceRows_`).

Proeven: vier "per apparaat" in test_rapport.mjs.
