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
zonder tekst. Daarna zijn de apparaten te slepen, staan de pijltjes eronder, en
zet "Klaar" of het knopje zelf het weer uit. De eigenaar op 23-09-2026: "waarom kan
ik hier de volgorde niet aanpassen, drag en drop wat ik vroeg toch?" en, na een
versie met lang indrukken: "niet lang indrukken maar het zelfde icoontje als
indeling aanpassen beneden, alleen dan zonder tekst, en dat je dan kan slepen."

De kaarten zijn te verslepen sinds de stand "Indelen" (`layout.js`, per scherm in
de browser en niet per persoon). Sinds v0.91.0 ook de rij met aanstuurbare
apparaten, na de bewoner van de eerste woning op 23-09-2026: "apparaten die ik veel
gebruik wil ik vooraan kunnen zetten." `orderDevices`, `deviceOrder` en
`saveDeviceOrder` in layout.js (`dac-device-order`); een nieuw apparaat komt
achteraan. In de stand Indelen zijn de knoppen zijwaarts te slepen
(`startTabDrag_` in overview.js, pointer events zoals bij de kaarten) en staan er
twee pijltjes die het gekozen apparaat een plek opschuiven, want slepen is nooit
de enige manier. "Standaard terugzetten" zet ook de apparaten terug.

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
