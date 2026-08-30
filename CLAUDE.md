# DomotiApp Coach

Een custom integration voor Home Assistant die apparaten in huis op het
gunstigste moment laat draaien: nu de laadpaal, straks de vaatwasser. Hij wordt
via HACS verspreid, dus alleen `custom_components/` gaat mee naar de klant.

Eigenaar en opdrachtgever is Sven. Hij beoordeelt en beslist; ik bouw, test,
commit, tag en breng uit.

## Werkafspraken

- **Nederlands** in het gesprek, in commit messages en in releasenotes.
  Codecommentaar in het Engels of Nederlands, zoals het bestand het al doet.
- **Geen gedachtestreepjes** in teksten die de klant leest.
- **Ik doe git zelf**: feature-branch, één commit, `--no-ff` merge naar `main`,
  tag, push, en een GitHub release. HACS kijkt naar releases en niet naar tags,
  dus zonder release krijgt niemand de update.
- **Testen vóór opleveren.** Sven installeert meteen bij zichzelf; alles wat ik
  zelf had kunnen zien kost hem een ronde. Meld eerlijk wat niet getest is.
- **Nooit verzonnen getallen.** Elk getal in de code of op het scherm komt uit
  een meting, uit een instelling van de klant of uit een som die daarop rust.
  Weet de coach iets niet, dan zegt hij dat in plaats van iets aan te nemen.
- **Lees zijn klacht letterlijk.** Hij beschrijft wat hij zag, niet wat er
  technisch misging. Vraag je af wat hij verwáchtte te zien.
- Niets bouwen zonder zijn seintje. Wat er op de lijst staat betekent niet dat
  het aan mag.

## Hoe het in elkaar zit

| bestand | wat het doet |
|---|---|
| `planner.py` | alle denkwerk, kent Home Assistant niet, is los te draaien |
| `coach.py` | leest sensoren, stuurt de paal aan, houdt de laadbeurt bij |
| `websocket.py` | wat het paneel mag opvragen en wijzigen |
| `storage.py` | de instellingen op schijf |
| `monitor.py` | de zekeringbewaking en de wachthond |
| `report.py` | het pdf-rapport |
| `frontend/src/` | het paneel, ES-modules zonder buildstap |
| `frontend/src/schedule-sheet.js` | het schema van één apparaat, als pop-up achter zijn kaart |

De scheiding tussen `planner.py` en `coach.py` is de kern: het denkwerk is los
te draaien tegen een hele dag echte historie voordat er ook maar iets geschakeld
wordt. Zet daar niets in dat `hass` nodig heeft.

## Proeven draaien

```
python tests/test_planner.py     # 152 controles op het denkwerk
python tests/test_coach.py       # 189 op de bedrading, met een nagebouwde HA
python tests/test_archive.py     # 37 op de kwartieropslag
node   tests/test_rapport.mjs    # 14 op het rapport en op het paneel
node   tools/laadcheck.mjs       # laadt elke paneelmodule echt in
python tools/stijlcheck.py       # backticks in css-commentaar
```

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
`schedule-sheet.js`. Alles gaat langs één commando,
`domotiapp_coach/device/schedule`, dat precies dat ene apparaat aanraakt en de
nieuwe lijst zelf uitrekent.

**Strategie gaat alleen nog over de coach zelf**: hoeveel hij mag doen, waar hij
op mikt, en de meldingen. Zet daar geen apparaten meer in.

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
niet als de module die het is. Sven keek naar een zwart scherm en dacht dat zijn
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
`jansen.txt` en niet `klant-jansen.txt`. Dat is Svens afspraak; hij noemt zijn
klanten bij de achternaam en wil dat terugzien in de bestandsnaam, in
`HA_INSTALLATIE` en in de kop van elk stuk gereedschap. Een tussenvoegsel wordt
een streepje: `van-den-dam`.

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
```

### Eén sessie kijkt naar één installatie

**De installatie waarop de sessie gestart is, is de installatie waar het over
gaat.** Vraagt Sven naar "mijn laadpaal" terwijl de sessie op een klant staat,
dan bedoelt hij de laadpaal van die klant, want daar is hij mee bezig. Ga daar
niet zelf van afwijken, en kijk er nooit "even ook" naast bij een andere
installatie om te vergelijken.

Daar hoort dit bij:

- **Zet `HA_INSTALLATIE` niet zelf om** en gebruik geen `HA_TOKEN_FILE` om er
  omheen te gaan. `start.sh` zet `HA_VAST=1`, en dan weigert `ha.py` allebei met
  een uitleg. Wil Sven uitdrukkelijk twee installaties vergelijken, dan mag
  `HA_VAST=0` ervoor, en zeg er dan bij dat je dat doet.
- **De entiteit-id's in de privénotities zijn die van Svens eigen huis.** Bij een
  klant heten ze anders. Zoek ze op met `/api/states` of via `logboek.py`, die
  het aan het paneel zelf vraagt, in plaats van ze aan te nemen.
- Klopt de installatie niet met wat Sven wil, zeg dat dan en laat hem de sessie
  opnieuw starten. Stiekem omschakelen is erger dan een ronde vertraging.

Dit staat hier omdat het op 27-08-2026 misging: een sessie was op een klant
gestart en las toch Svens eigen laadpaal uit.

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
