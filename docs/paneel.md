# Het paneel: wat waar staat

Uit `CLAUDE.md` gehaald op 24-09-2026, zodat dat bestand kort blijft. De eisen
van de eigenaar en de werkafspraken staan daar en gaan boven alles hier.
Komt er bij een uitgave iets bij over dit onderwerp, schrijf het dan hier.

## Wie wat ziet: de bewoner en de installateur (v0.114.0)

De eigenaar op 08-10-2026, nadat hij wilde dat een klant zonder beheerrechten
"overal bij kan": "Ik wil inderdaad niet dat een klant iets kan wijzigen wat
kritisch is. [...] Voorop staat dat de klant geen entiteiten moet kunnen kiezen,
alleen bij meldingen de telefoon entiteiten kunnen kiezen." Op 12-10-2026 gaf hij
de antwoorden op de acht vragen (privénotities, `indeling-bewoner-installateur.md`).

| tab | wie | wat |
|---|---|---|
| Overzicht | iedereen | de kaarten, met per apparaat **Instellen** |
| Historie | iedereen | |
| Meldingen | iedereen | personen toevoegen en weghalen, de schuiven, de drempels (zware belasting, lekkage, temperatuur van de batterij) |
| Voorkeuren | iedereen | hoeveel de coach zelf doet, de voorrang, de nacht, en het overzicht (kleurdrempels, de kaart met de fasen) |
| Apparaten | installateur | alleen de hardware: type, merk, entiteiten, mag sturen, fasen wisselen, de technische kant van de batterij, de auto's (merk, accu, stroom, fasen, sensoren, wekknop), de programmatabel, ruimtes |
| Installatie | installateur | woning en aansluiting, kasten en groepen, energiebronnen, fasen, zonverwachting, meterstanden, navigatie |
| Contract | iedereen | het contract van nu en de eerdere; de bewoner leest, en bevestigt zijn stroomprijs met "Ja, dit klopt" |

De bewoner ziet de tabs van de installateur niet, ook niet grijs
(`adminOnly` in header.js). Contract is sinds v0.130.1 de uitzondering: de
eigenaar op 19-10-2026, "je energieprijs staat nu in voorkeuren maar dat moet
onder contract". De bewoner ziet daar per bron wat voor contract, bij wie en van
wanneer tot wanneer, de opbouw van zijn stroomprijs en de eerdere contracten als
regels; elke sensor en elk bedrag staat in een blok met `data-installateur`, en
dat is er in de leesstand niet (`:host([readonly])` in contract.js). "Ja, dit
klopt" heeft de klasse `vrij`, die de leesstand in editor-base.js met rust laat,
want `contract/confirm` is niet alleen voor de beheerder. Voorkeuren heette Strategie; het id `strategie`
bleef, zodat een bladwijzer blijft werken. Instellingen is opgegaan in
Installatie, het contract kreeg een eigen tab (`views/contract.js`).

**Instellen achter de kaart.** De eigenaar koos "A": één pop-up met het schema
erin. Dat is `schedule-sheet.js`, met bovenaan het schema (als het apparaat er
een heeft) en daaronder "Zo wil je het" uit `voorkeur-velden.js`: bij de laadpaal
de modus zonder planning, continu laden op, zon beginnen vanaf, en per auto
laden tot en (bij een Tesla met wekknop) hoe vaak hij gewekt wordt; bij de
thuisbatterij de reserve, handelen, een keer per week vol, de vakantiestand, de
auto helpen en de ventilator (alleen met een ventilator); bij een vaatwasser die
zelf kan starten het vinkje vrijgeven. Op de kaart heet de knop bij het schema
"Instellen"; een apparaat zonder schema met iets in te stellen (de batterij)
krijgt een eigen knop (`data-settings`). Elk veld slaat meteen op.

**De server dwingt het af.** Geen admin-slot gaat open; de bewoner krijgt eigen
commando's die alleen hun eigen velden aannemen:

- `device/preferences`: per type de velden uit `VOORKEUREN`, `VOORKEUREN_AUTO`
  en `VOORKEUREN_ACCU` in storage.py (`voorkeuren_bijwerken`). Een veld dat niet
  bij het type hoort is een fout, geen stille no-op.
- `notifications/household`: de personen en de drempels. De koppeling aan een
  account laat hij staan (`huishouden_bijwerken` in ontvangers.py).
- `display/set`: de kleurdrempels en `sources.phases_on_overview`.
- `strategy/set` neemt geen `schedules` meer aan: wie Voorkeuren opsloeg met
  een oude kopie zette een schema terug dat iemand net op een kaart wijzigde.
  Schema's gaan alleen via `device/schedule`.

**Iedereen ziet alle personen.** Tot v0.114.0 zag een bewoner alleen zichzelf
(de eigenaar op 06-09-2026); op 12-10-2026: "Ja dat mag de bewoner." Daarmee had
de koppeling aan een account geen taak meer op het scherm, en die keuze is uit
het formulier. Wat er al gekoppeld is blijft bewaard, en `notifications/mine`
bestaat nog.

Proef 150 in test_coach.py; in test_rapport.mjs de proeven onder "de indeling
bewoner en installateur".

**Een uitklaplijst krijgt de kleuren van het thema** (v0.114.2). De keuzelijst
"Zonder planning" in Instellen was wit met lichte letters: de browser tekent de
opties zelf. De eigenaar op 12-10-2026: "dit is wit moet ook donker zijn". Op
06-09-2026 gebeurde precies dat bij Meldingen. Nu staat het in een proef: elk
bestand met een uitklaplijst heeft `select option` met `--dac-bg-raise`, of de
stijlen van de bewerkschermen (`editorCss`) waar die regel in zit.

## De apparaatlijst

**De apparaatlijst noemt alleen wat de coach werkelijk kan** (v0.70.0). De eigenaar op
19-09-2026: bij Apparaten gingen de thuisbatterij, de warmtepomp, de wasmachine,
de droger en de zwembadpomp eruit, en bij een laadpaal het merk "overig". Over
blijven: laadpaal, boiler, vaatwasser, airco en overig. (De thuisbatterij kwam
in v0.73.0 terug, en nu omdat de coach hem werkelijk stuurt. De airco stuurt hij
sinds v0.119.0: `docs/airco.md`.) Hetzelfde argument als
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

## De volgorde op het overzicht

**Sinds v0.96.0 ook zonder Indelen, met het knopje rechtsboven in de kaart**
(`#steer-sort`, `startSorteren_` in overview.js): het icoon van "Indeling aanpassen",
zonder tekst. Daarna staan de pijltjes onder de rij, en zet "Klaar" of het
knopje zelf het weer uit. De eigenaar op 23-09-2026: "waarom kan ik hier de
volgorde niet aanpassen, drag en drop wat ik vroeg toch?" en, na een versie met
lang indrukken: "niet lang indrukken maar het zelfde icoontje als indeling
aanpassen beneden, alleen dan zonder tekst, en dat je dan kan slepen."

**Sinds v0.102.1 wordt er nergens meer gesleept, alleen nog met pijltjes.** De
eigenaar op 30-09-2026: "ook werkt de indeling aanpassen drag en drop niet. Dat
moet weg en wel de pijltjes behouden om dat aan te passen." De greep op de
kaarten (`startDrag_`) en het slepen van de apparaten (`startTabDrag_`) zijn uit
overview.js; de kaarten houden omhoog en omlaag (`moveCard_`), de apparaten
links en rechts (`moveDevice_`). Niet opnieuw voorstellen.

De kaarten zijn te verplaatsen in de stand "Indelen" (`layout.js`, per scherm in
de browser en niet per persoon). Sinds v0.91.0 ook de rij met aanstuurbare
apparaten, na de bewoner van de eerste woning op 23-09-2026: "apparaten die ik veel
gebruik wil ik vooraan kunnen zetten." `orderDevices`, `deviceOrder` en
`saveDeviceOrder` in layout.js (`dac-device-order`); een nieuw apparaat komt
achteraan. "Standaard terugzetten" zet ook de apparaten terug.

## De volgorde in Apparaten

Sinds v0.103.0 met pijltjes omhoog en omlaag naast de prullenbak, zodra er meer
dan één apparaat is. De bewoner van de eerste woning op 30-09-2026, bij de lijst van
negen apparaten: "Deze zou ik ook customizable maken. Zelf slepen op de volgorde
die je wil." Pijltjes en geen slepen, om dezelfde reden als hierboven. Het is de
volgorde van `devices` in de instellingen, dus voor iedereen, en pas na Opslaan.
De pijlen staan in één knop van 36 bij 36 px, even hoog als de prullenbak; op een
scherm tot 360 px valt het pijltje naar rechts weg en wordt het icoon 30 px,
anders hield de naam op 280 px 45 px over (nu 83).

## Ruimtes in Apparaten

Sinds v0.105.0. De bewoner van de eerste woning op 30-09-2026: "Verder kun je er nog
over denken om apparaten in een ruimte te zetten. Stel dat iemand 25 apparaten
heeft, dan is ie snel het overzicht kwijt." De eigenaar op 01-10-2026, op de vraag of
dat de ruimtes van Home Assistant moesten zijn: "eigen ruimtes in de coach. Alleen in
lijst apparaten."

- **Opslag**: `rooms` bovenaan in de instellingen (`{id, name}`, in de volgorde van
  het scherm) en `room` per apparaat (het id, of leeg). Het scherm Apparaten bewaart
  beide (`sections = ["devices", "rooms"]`). Het schema in websocket.py gooit
  onbekende velden weg en de opslag snoeit onbekende sleutels, dus allebei staan ze
  in het schema en in `DEFAULT_SETTINGS`. De coach zelf leest ze niet (proef 131).
- **Op het scherm**: zonder ruimtes is de lijst zoals hij was. Met ruimtes een
  tussenkop per ruimte (de naam is een invulveld, het aantal, pijltjes, prullenbak),
  en onderaan "Zonder ruimte" als daar iets in staat. Bij een apparaat een keuzelijst
  Ruimte. "Ruimte toevoegen" naast "Apparaat toevoegen" zet een lege ruimte onderaan
  met de cursor in de naam; opslaan kan pas als elke ruimte een naam heeft.
- **De pijltjes van een apparaat schuiven binnen zijn ruimte**: het ruilt met de
  buur in dezelfde groep (`buur` in `paintDevices_`). Een ruimte weg: de apparaten
  erin blijven, zonder ruimte; niets te bevestigen, want Ongedaan maken zet het terug.
- **Smal**: tot 360 px valt het aantal weg. Gemeten met "Keuken en bijkeuken": op 390
  en 320 px past de naam (194 en 189 px), op 280 px valt het eind weg (149 px).

## Waar het schema van een apparaat staat

Sinds 27-08-2026 staat dat bij het apparaat zelf en niet meer in Strategie (nu
Voorkeuren). Op de kaart in Overzicht: de schuif die het schema aan en uit zet.
Wie er voorgaat staat sinds v0.93.0 op Voorkeuren ("Voorrang bij planningen").
Achter de knop Instellen (tot v0.114.0 Schema): de tijden en het per-dag-werk, in
`schedule-sheet.js`. Voor een laadpaal is dat sinds 04-09-2026 alleen nog
"klaar om" (`timesFor` in dat bestand); `_days` in coach.py negeert de andere
twee voor een laadpaal, ook als ze nog in oude instellingen staan. Alles gaat langs één commando,
`domotiapp_coach/device/schedule`, dat precies dat ene apparaat aanraakt en de
nieuwe lijst zelf uitrekent.

**Voorkeuren gaat over hoeveel de coach zelf mag, de voorrang, de nacht en het
overzicht.** De meldingen staan sinds 06-09-2026 onder Meldingen, en de
apparaten op hun eigen kaart.

Het schuifje is geen apart begrip: het is de `enabled` die elk schema al had.
Staat hij uit, dan slaat `_days` in `coach.py` het schema over en vervalt in
`planner.py` de hele klaar-tijdtak.

## Het bolletje op de tabbladen

**Groen is vrijgegeven, of aan het draaien** (v0.100.0). Tot dan betekende het
alleen "vrijgegeven". De eigenaar op 26-09-2026, met een schermafdruk: "bij
aanstuurbare apparaten in het overzicht draait de vaatwasser maar het bolletje
is niet groen." Thuis was hij met de hand gestart en de vrijgave stond uit.
Alleen bij apparaten die een vrijgave kennen (`needsRelease`); de schermlezer
hoort " (draait)" of " (vrijgegeven)". Proef in test_rapport.mjs.

**En elk apparaat dat aan staat** (v0.101.0). De eigenaar op 28-09-2026: "bolletje
van de batterij is niet groen. Als die laadt of ontlaadt moet hij groen zijn. Staat
hij echt niks te doen dan moet hij uit zijn." En: "laadpaal moet ook groen worden.
Eigenlijk elk apparaat als die aan staat." Gemeten aan het vermogen, met dezelfde
grens als "Doet nu" op de kaart (`ACTIVE_WATTS`); de schermlezer hoort " (laadt)",
" (ontlaadt)", " (verwarmt)" of " (aan)". De vrijgave blijft ook groen. Proeven in
test_rapport.mjs.

**Een tab is het anker van zijn onzichtbare woord** (v0.102.2). In elke tab van
de rij apparaten staat een woord voor de schermlezer (`.sr`, absoluut
geplaatst). Zonder `position: relative` op `.steer-tab` hing dat woord aan de
pagina en schoof het niet mee met de rij: met meer apparaten dan er naast elkaar
passen werd de hele pagina zo breed als de rij, en schoof het paneel op een
telefoon zijwaarts. Gemeten op 30-09-2026 met twaalf tabs: op 390 px breed een
pagina van 1.227 px, met het anker 375; op 320 en 280 px net zo (305 en 265).
Proef in test_rapport.mjs.

## Volgen zonder beheerder te zijn (v0.108.1)

Home Assistant laat een gebruiker zonder beheerdersrechten zich niet abonneren op de
events van een integratie. In de klantwoning stond het log sinds 08-10-2026 23 keer
vol met "Refusing to allow ... to subscribe to event domotiapp_coach_settings_updated",
en het overzicht van een bewoner haalde de stand van de coach één keer op en werkte
daarna nooit meer bij. Het paneel volgt de coach nu via een eigen commando,
`domotiapp_coach/subscribe` (`async_subscribe` in websocket.py, `volgCoach` in
data-source.js), voor besluiten, meldingen en instellingen. Het geeft door wat zo
iemand al mag opvragen, en van de instellingen net als `settings/get` alleen zijn
eigen persoon. Proef 139 in test_coach.py en een proef in test_rapport.mjs, die ook
nagaat dat er buiten `state-feed.js` en `data-source.js` geen `subscribeEvents` meer
staat.

## Licht en donker (v0.113.0)

De eigenaar op 11-10-2026, bij de lichte kaarten van DomotiApp Lovelace: "alles moet ook goed
licht zijn. Ook de coach." Het paneel volgt nu Home Assistant zelf: staat dat licht
(`hass.themes.darkMode` false), dan is het paneel licht (`setLight` in theme.js, vanuit `set hass`
in domotiapp-coach-panel.js).

- **Twee sets in theme.js.** `tokens` is het donkere thema zoals het was, `lightTokens` zet alleen
  wat in het licht anders moet. Elk element zet de tokens op zijn eigen `:host`, dus een eigenschap
  op het paneel alleen bereikt ze niet; elk element krijgt daarom het attribuut `light`
  (`followTheme` in `DacElement`), ook een element dat later bijkomt, en `:host([light])` zet de
  lichte set.
- **Tinten over de achtergrond** zijn `rgba(var(--dac-veil), a)`: wit in het donker, zwart in het
  licht. Net zo `--dac-ink-rgb`, `--dac-bg-rgb` en `--dac-raise-rgb` voor de verlopen onder de kop
  en de balk onderaan, `--dac-popover` voor uitklaplijsten, `--dac-knob` voor de schuifjes en
  `--dac-shadow-deep` voor zware schaduwen. `color-scheme` volgt mee (`--dac-scheme`), zodat de
  browser een uitklaplijst of een datumveld in hetzelfde thema tekent.
- **De stroomkleuren blijven**: het zijn vlakken met een eigen icoon en naam, en op wit houden ze
  hun volgorde. De statuskleuren en de blauwe tekst gaan in het licht donkerder, want ze zijn ook
  tekst: gemeten in de preview (`?licht=1`) over alle zeven schermen was het laagste contrast eerst
  3,05 (blauwe tekst op een blauw labeltje bij Meldingen) en 3,1 (oranje waarschuwing bij
  Apparaten). Daarna is het laagste 4,08 (datzelfde labeltje), en de lichtste grijze tekst 4,33.
- Het rapport en de pdf zijn papier en houden hun eigen kleuren.

Proef "licht en donker" in test_rapport.mjs leest elk scherm en valt om zodra er weer een kleur van
alleen het donkere thema in staat (wit over donker, `#12120f`, `color-scheme: dark`). In de preview
op de pc staat `?licht=1` (preview.html staat niet in git).

## Hoofdletters op de kaart (v0.119.2)

Elke waarde in de regels van een apparaatkaart begint met een hoofdletter. De
eigenaar op 14-10-2026, bij de batterijkaart met "ontlaadt", "ongeveer 89%,
gemeten in de accu" en "de batterij zelf, met zijn eigen meter; de coach kijkt
mee": "even alles met een hoofdletter beginnen." Dat gebeurt op één plek, waar
de kaart de regel neerzet (`metHoofdletter` in format.js, in `views/overview.js`),
en niet in de teksten zelf: dezelfde woorden staan elders midden in een zin. Een
getal of een teken vooraan ("58 %", "€ 4,26") blijft zoals het is.

Sinds v0.119.3 ook in de pop-up van een bel in de energiestroom (`openDetail_` in
`components/energy-flow.js`), want daar staan dezelfde regels. De eigenaar op
15-10-2026, bij de pop-up van de batterij met "laadt" en "ongeveer 93%, gemeten in
de accu": "hier ook hoofdletters toepassen."

## De vooruitblik (v0.133.0)

De eigenaar op 19-10-2026, bij voorbeelden van andere apps (een dynamisch-contract-app, een
energie-app met een prijsgrafiek en de bèta van een optimizer): "Wat helemaal vet zou zijn is als
er nog een overall predictive modus komt op je hoofd dashboard", en "Dan zie je in één oogopslag
wat er toekomstig gaat gebeuren, en krijg je een visuele bevestiging of je ingestelde
prioriteiten ook kloppen."

Een kaart op het overzicht, direct onder de coach (`vooruit` in `OVERVIEW_CARDS`). Wie de
volgorde al eens veranderde krijgt hem ook daar, na zijn voorganger, en niet achteraan:
`reconcile` in layout.js zet een nieuwe kaart sindsdien op zijn plek.

- **De gegevens** komen van de coach: `domotiapp_coach/forecast` (websocket.py) roept
  `vooruitblik` in coach.py aan. De prijzen, de zonverwachting per uur (`_zon_kwh`) en het
  huisverbruik per uur (`_huis_kwh`, de mediaan van de afgelopen week) waar de coach zelf mee
  plant, en per apparaat het plan dat hij al had: de blokken van de laadpaal (`plan_ahead`), het
  hele uurplan van de batterij (`uren` in het geheugen, de toestand neemt er maar 48 van), de
  blokken die de boiler koos (`blokken` op `Decision`, uit `plan_boiler`), de start en de duur
  van een programma, en van een airco alleen wat hij nu doet. Van nu tot het eind van de bekende
  prijzen, minstens twaalf uur, hooguit tot morgen 24:00. Plus de volgorde van de voorrang bij
  zon en bij planningen.
- **De kaart** (`vooruitblik.js`, element `dac-vooruitblik`): bovenaan de prijs per uur in de
  kleuren van Voorkeuren, daaronder de vermogens. De apparaten staan gestapeld in de volgorde
  van de voorrang, ontladen van de batterij onder de lijn, de zon als geel vlak, het huis als
  stippellijn en de accustand als lijn op zijn eigen schaal (0 tot 100%). Een programma waarvan
  het verbruik niet bekend is krijgt een streepje en geen hoogte. Vegen gaat vooruit, tikken op
  een uur zet het in het vlak erboven: de prijs en per laag wat er gebeurt ("Thuisbatterij:
  Handelen, 2,5 kW eruit, naar 55%"). Met de keuzeknoppen zet je lagen aan en uit; dat onthoudt
  het scherm (`dac-vooruitblik` in localStorage), want het is een voorkeur van wie kijkt.
  Onderaan de voorrang in woorden.
- **Haalt op** bij het openen, bij een besluit van de coach hooguit eens per minuut, en anders
  eens per vijf minuten (`haalVooruit_` in overview.js). Een coach van voor v0.133.0 kent het
  commando niet: dan blijft de kaart weg.

**Wat gaat hij doen** bestond voor de laadpaal en de batterij. Sinds v0.133.0 ook voor de boiler
en een apparaat met een programma: dezelfde pop-up met de prijsgrafiek, groen waar hij draait,
en de vakken en de uren eronder (`apparaatVooruit` en `paintAnder_` in plan-ahead-sheet.js). De
prijzen zijn die van de coach (`coachRijen` in data-source.js); de duur van een programma
staat sinds deze uitgave in de toestand (`program_minutes`). De eigenaar op 18-10-2026: "Zou bij
zowel batterij, als ev laden, als boiler, etc op dezelfde manier weergegeven mogen worden." Een
airco heeft geen plan en dus geen knop.

Proef 174 in test_coach.py, de boiler in test_planner.py, en in test_rapport.mjs "de
vooruitblik" en "Wat gaat hij doen: de boiler en een programma".

## Prijskleuren naar de bekende prijzen (v0.133.1)

De bewoner van de eerste woning op 19-10-2026, bij de vooruitblik waarin alle staven rood
waren: "elke app kiest ervoor om de kleurstelling van de kolommen aan te passen, relatief gezien
naar de spread op de dag. In de huidige versie is alles oranje omdat de prijs inderdaad hoog is.
Sommige mensen vinden dit misschien fijn!" en "Als je namelijk móet laden (ev) wil je dat op het
goedkoopste moment doen van de dag." En meteen daarna: "Worden de nieuwe prijzen om 14u bekend,
dan past ie zijn kleurstelling aan. Het kán dan zo zijn dat een kolom die om 13.59 nog groen
was, rood wordt, omdat de prijzen morgen veel lager zijn."

Onder Voorkeuren, bij Het overzicht, het vinkje **Prijskleuren naar de bekende prijzen**
(`thresholds.price.relative`, via `display/set`, dus ook voor de bewoner). Aan: het goedkoopste
derde van het verschil tussen de goedkoopste en de duurste bekende prijs is groen, het duurste
derde rood, van het lopende uur af (`prijsGrenzen` in format.js). Een uur dat voorbij is telt
niet mee. De vaste grenzen verdwijnen dan van het scherm. Uit: de vaste grenzen, zoals altijd.

Het geldt overal waar een prijs een kleur heeft: de vooruitblik, de prijsgrafiek achter het
tegeltje, het tegeltje Energieprijs zelf, en de zin van de coach ("Stroom is nu duur",
"Goedkoop moment"). De legenda van de prijsgrafiek noemt dan geen bedragen maar derden. Proef
"prijskleuren naar de bekende prijzen" in test_rapport.mjs.

In Portugal (v0.138.0) krijgen het tegeltje en de prijsgrafiek de lijst van de coach, dezelfde als
de vooruitblik, en is het tegeltje klikbaar zoals bij een dynamisch contract: daar zijn twee of
drie prijzen per dag. De kaart Je meter staat er dan niet. Zie `docs/contract.md`, Portugal op het
overzicht.

## Meldingen in groepen die uitklappen (v0.133.2)

De eigenaar op 19-10-2026: "ik wil wel bij meldingen dat je alles groepeert en alles kan
uitklappen, nu staat alles op een vaste positie onder elkaar en wordt het onoverzichtelijk."

Meldingen bestaat nu uit vier groepen (`details.groep` in views/notifications.js), elk met een
korte stand in de kop, zodat je niet hoeft uit te klappen om te zien hoe het staat
(`paintStanden_`):

| groep | stand in de kop |
|---|---|
| Wie krijgt wat | hoeveel personen |
| Herinneringen | wanneer de meterstanden weer aan de beurt zijn |
| Waarschuwingen | hoeveel van de waarschuwingen aan staan; daarbinnen zware belasting, lekkage, batterij te warm en apparaat staat uit elk apart uit te klappen, met aan of uit |
| Geschiedenis | hoeveel meldingen er vandaag waren, en hoeveel kritiek (`geschiedenisStand`); daarbinnen elke dag apart, met het aantal |

Standaard staat alleen de geschiedenis open, en daarin vandaag (of de eerste dag als er vandaag
niets was, of de dag die je koos). Wat je open- of dichtklapt onthoudt het scherm
(`dac-meldingen-open` in localStorage), want het is een voorkeur van wie kijkt. Een waarschuwing
die in dit huis niet kan (geen batterij, niets dat altijd aan moet) staat er niet, en zijn er
geen, dan ook de groep niet. Proeven "Meldingen: vier groepen die uitklappen" en "het scherm
tekent een kop per dag en een rij per melding" in test_rapport.mjs.

## De accustand boven de 0-lijn (v0.137.0)

De eigenaar op 19-10-2026, bij een schermafdruk van de vooruitblik: "Er is nu een 0-lijn, maar hier
kijkt de soc niet naar." De accustand liep van 0 tot 100% over de hele hoogte van de vermogens, dus
ook onder de lijn, en 20% leek dan ontladen. Nu staat 0% op de 0-lijn en 100% bovenaan (`vooruitSvg`
in vooruitblik.js), en krijgt de ruimte boven de lijn minstens evenveel hoogte als die eronder zodra
er een accustand te tekenen is (`schalen`). De legenda zegt "Accustand: 0% op de lijn, 100%
bovenaan". Proef in test_rapport.mjs.

## De klok van het huis (v0.138.1)

De coach schrijft elke tijd in de tijd van Home Assistant en zonder tijdzone: een prijsrij,
de vooruitblik, een besluit, een melding ("2026-10-19T15:45:00"). De browser leest zo'n tijd als
zijn eigen tijd. Dat ging goed zolang huis en browser in hetzelfde land stonden. Gemeten op
19-10-2026 bij de woning in Portugal, vanaf een pc op Nederlandse tijd: de vooruitblik zei "15:00
tot 16:00", de prijsgrafiek eronder "Nu 16:45 tot 17:00" en "Duurst: vandaag 15:45". De eigenaar:
"bouw inderdaad een reparatie voor een installatie niet in NL."

Sindsdien rekent het paneel "nu" op de klok van het huis: `huisNu()` in format.js, een Date
waarvan dag en uur die van Home Assistant zijn, net als de tijden van de coach. De tijdzone komt
uit `hass.config.time_zone` (`zetHuisZone` in domotiapp-coach-panel.js). Een tijd uit Home
Assistant met een tijdzone erbij, zoals de lijst van een prijssensor (Nord Pool, Frank), gaat door
`huisTijd`/`alsHuis` naar dezelfde klok (`readSchedule` in data-source.js). Zonder tijdzone (de
preview, de proeven) is het de klok van de browser, dus bij een Nederlands huis vanuit Nederland
verandert er niets.

Waar het gebruikt wordt: `priceAt` en het daggemiddelde in data-source.js, `prijsGrenzen`, de
prijsgrafiek ("Nu", wat voorbij is, Morgen), de vooruitblik ("morgen"), Wat gaat hij doen, het
schema, de zin "De coach heeft N minuten niets beslist" (`minutenGeleden`, die met een uur
verschil altijd in beeld stond), de dag bij de batterij (`dagKlok` in battery.js, die de dag in
UTC nam), de tijdlijn in Historie en wat er per kwartier van het net kwam (`herkomst`), de lijsten
onder Meldingen en in de berichtenbox, en de schaal in geld.js.

Wat er niet onder valt: `ptPrijsOp` (tarifas.js) rekent zelf vanuit UTC in de tijd van Lissabon en
krijgt dus het echte moment.

**Historie sinds v0.138.2.** De eigenaar op 19-10-2026: "waarom is er nog iets niet opgelost kan dat
niet of?", en daarna "ja bouw het maar". Historie werkt nu ook op de klok van het huis, en zet om aan
de randen. Een dag, week, maand of jaar begint om middernacht in het huis (`periodStart` met
`huisNu`). Wat het paneel aan Home Assistant vraagt gaat met het echte moment (`vanHuis(...)
.toISOString()` bij de recorder en de kwartieropslag), en wat terugkomt gaat weer naar de klok van
het huis (`alsHuis` op `row.start`). `prijsOp` in geld.js geeft `ptPrijsOp` en zon op en onder het
echte moment. De afrekening (`domotiapp_coach/afrekening`) krijgt gewoon de dag van het huis.

**De wintertijd.** Een Date op de klok van het huis kan het uur dat bij het ingaan van de wintertijd
twee keer komt (02:00 tot 03:00 in Nederland) maar één keer aanwijzen. Zou het paneel altijd omzetten,
dan vielen die twee uren samen en verloor Historie een uur verbruik, ook bij een Nederlands huis vanuit
Nederland. Daarom geeft `alsHuis` het moment zelf terug zolang de klok van de browser op dat moment
hetzelfde aanwijst als die van het huis (v0.138.2). Alleen wie vanuit een andere tijdzone kijkt ziet
op die dag twee uren als één.

**Een nieuwe vergelijking met een tijd van de coach gaat tegen `huisNu()`, niet tegen
`new Date()`.** Proef "de klok van het huis" in test_rapport.mjs rekent het na in Lissabon en
Kiritimati, wat de tijdzone van de machine ook is (en "Historie op de klok van het huis" de
perioden, de vragen aan de recorder en de wintertijd), en kijkt of de bekende plekken geen
`new Date()` meer hebben. In de preview: `?pt=1&tz=Europe/Lisbon`.

## Lange namen in de energiestroom (v0.141.0)

De eigenaar op 19-10-2026: "Anker Solix Solarbank Max AC" liep bij een bol over de rand. Een naam
staat nu op hooguit twee regels van 18 tekens (12 op een smal scherm), op woorden gebroken, en
wat er dan nog overblijft wordt afgekapt met "…" (`naamRegels` in components/energy-flow.js). Boven
de zon groeit de naam omhoog. En het vermogen van de woning staat op één regel, "178 W", zoals bij
de andere bollen.

## Datum en tijd op een iPhone (v0.141.2)

De eigenaar op 21-10-2026, met schermafdrukken van Contract op zijn iPhone: "op telefoon zien de
velden er heel raar uit". De datumvelden ("ingegaan op", "loopt af op", "opnieuw uitrekenen
vanaf") liepen rechts buiten de kaart, een leeg datumveld was hoger dan de rest, en de datum stond
in het midden. iOS geeft een datumveld een eigen minimale breedte en zet de waarde neer met de
flexbox van het veld zelf, en die centreert; Chrome laat daar niets van zien. Nu staat in
`baseCss` (theme.js) voor elk datum- en tijdveld in het paneel `appearance: none`, `min-width: 0`,
`max-width: 100%` en een flexbox die links begint, en `::-webkit-date-and-time-value` zonder marge
en links; de velden onder Contract en Apparaten zijn 44 px hoog, ook leeg. Dezelfde oplossing als
de laadpaalkaart van DomotiApp Lovelace (valkuil 78 daar). Op een iPhone niet nagemeten: er staat
op de Mac geen Simulator. Proef "datum en tijd op een iPhone" in test_rapport.mjs.

Daarbij nagemeten in Chrome op 390, 320 en 280 px, alle tabbladen met elke groep opengeklapt:
niets breder dan het scherm. De pop-up met de schuif en Instellen van een batterij ook; daar viel
"de coach bepaalt" in de prijsvelden af, die zijn nu 190 px. En de ring om vol of leeg laden had
een doorschijnend binnenvlak, waardoor het draaiende verloop door de knop scheen.

## Koppen en blokken per onderwerp (21-10-2026)

De eigenaar op 21-10-2026: "alle menus dan maar eens door lopen, en een beetje herstructureren
met koppen en aparte blokken per onderwerp", en na de eerste ronde, bij Onderverdeelkasten: "Ik
vind de opzet zoals je bij installatie gebruikt wel echt duidelijk", "daar zou over de hele app
meer uniformiteit in mogen komen."

**Eén vorm.** Een kaart (`section.card` met een `h2` en een korte uitleg) per onderwerp, en
daarbinnen per deelonderwerp een omkaderd blok met de kop erin: `.block` en `.block-title` in
`baseCss` (theme.js), hetzelfde vak als een kast of groep bij Installatie (`.circuit`). Elk element
heeft hem, ook de pop-up Instellen. Een kaart met maar één onderwerp houdt zijn velden los. Een
vinkje in een blok heeft geen eigen kader (editorCss): het blok is het kader.

**Elke functie een vinkje.** Wat aan of uit kan is een vinkje met een vette titel en uitleg; een
getal dat erbij hoort staat in hetzelfde blok en verschijnt pas als het vinkje aan staat. De
eigenaar: "Vakantiestand is een optie, maar accu inzetten bij auto is ook een optie. Ene is een
checkbox (bold font), ander is gewoon een regel." Zo nu ook "De accu mag de auto helpen"
(`car_above`) en "De coach zet de ventilator aan" (`fan_above_c`), die tot dan een veld waren met
"leeg is nooit". Het vinkje bewaart niets eigens (`data-vk-aan` in voorkeur-velden.js): aan is een
getal, uit is null, zoals altijd. Aanzetten zet alleen het veld neer; zonder getal blijft het uit,
want de coach verzint geen grens. Net zo de herinnering voor de meterstanden in Meldingen: een
schuif zoals de waarschuwingen, en de datum pas als hij aan staat; uit wist de datum.

- **Voorkeuren**: Hoeveel doet de coach zelf, de twee voorrangen en de nacht los; Weergave met de
  blokken Kleuren, Kaarten (weg zonder fasen) en Historie.
- **Installatie**: Woning (los), Aansluiting (Zekering, Lastbewaker), Onderverdeelkasten, Groepen,
  Energiebronnen (Zonnepanelen, Slimme meter), Fasen, Zonverwachting (Per uur, Per dag),
  Meterstanden (Stroom, Gas, Water), Navigatie (los).
- **Contract**: stroom begint met Leverancier en looptijd (het land, de soort, de leverancier of
  die van Portugal, de datums). Dan bij vast of variabel Prijs, Teruglevering en Vanaf 1 januari
  2027; bij dynamisch Prijssensoren, Belasting en opslag en Teruglevering; in Portugal Prijs per
  tijdvak, Teruglevering en Vaste kosten. Daarna Salderen (in Portugal weg, `#salderen-blok`), Zo
  komt je prijs tot stand, Eerdere stroomcontracten en het opnieuw uitrekenen. Gas: Leverancier en
  looptijd, Prijs, Eerdere gascontracten. Water: Prijs, Eerdere waterprijzen.
- **Apparaten**: per apparaat Apparaat (type, naam, ruimte, energieteller, merk; `brandHtml_` met
  `deel` "kop"), dan Koppeling of Stekker, Bediening, Opdrachten, Programma's, Auto's, De batterij,
  Hoe de coach hem aanstuurt, Opgeleverd opnieuw uitrekenen, De airco en als laatste Sturen.
- **Instellen**: Schema; bij de laadpaal Zonder planning en Auto's; bij de thuisbatterij
  Noodstroom, Handelen, Balanceren, Vakantiestand, De auto en Ventilator; bij een vaatwasser
  Vrijgeven, bij een airco Zo wil je het.
- **Meldingen**: de groepen die uitklappen bleven (v0.133.2); elke waarschuwing staat nu in een
  eigen vak. Elke `.velden[hidden]` is echt weg: bij Lekkage en Thuisbatterij te warm bleven de
  velden staan met de melding uit.
