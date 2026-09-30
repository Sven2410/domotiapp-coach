# Het paneel: wat waar staat

Uit `CLAUDE.md` gehaald op 24-09-2026, zodat dat bestand kort blijft. De eisen
van de eigenaar en de werkafspraken staan daar en gaan boven alles hier.
Komt er bij een uitgave iets bij over dit onderwerp, schrijf het dan hier.

## De apparaatlijst

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

Sinds 27-08-2026 staat dat bij het apparaat zelf en niet meer in Strategie. Op de
kaart in Overzicht: de schuif die het schema aan en uit zet. Wie er voorgaat
staat sinds v0.93.0 op Strategie ("Voorrang bij planningen"). Achter de knop Schema: de tijden en het per-dag-werk, in
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
