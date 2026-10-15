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
| Contract | installateur | het contract van nu en de eerdere |

De bewoner ziet de tabs van de installateur niet, ook niet grijs
(`adminOnly` in header.js). Voorkeuren heette Strategie; het id `strategie`
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
