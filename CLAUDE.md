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
git diff --cached -U0 | sed -n 's/^+//p' | tr -d '\r' | tr '\n' ' ' | tr -s ' ' \
  | grep -ioE ".{30}(<achternaam>|<straat>).{30}"
```

De tweede regel is er sinds 24-09-2026. Een naam met een tussenvoegsel valt
makkelijk over een regeleinde, en dan ziet de eerste regel hem niet; zo stond
er tot die dag twee keer de achternaam van een klant in dit bestand. Zoek je in
een bestand in plaats van in de diff, haal dan ook de `\r` eruit: de werkmap
op Windows heeft CRLF, en daarop liep de eerste poging die dag stuk.

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

## Waar de rest staat

Wat hierboven staat geldt altijd. Waarom een regel is zoals hij is, met de
metingen en de woorden van de eigenaar erbij, staat per onderwerp in `docs/`.
**Lees het bestand van het onderwerp waar je aan werkt voordat je iets
verandert, en schrijf nieuwe uitleg bij een uitgave dáár, niet hier.** Dit
bestand leest Claude Code elke sessie helemaal in, en boven 150.000 tekens
(samen met `C:\dev\CLAUDE.md`) waarschuwt hij; op 24-09-2026 stond het op
143.500 en is het daarom gesplitst. Verwijs er gewoon naar en niet met
`@docs/...`, want zo'n verwijzing wordt alsnog elke sessie ingelezen.

| werk je aan | lees eerst |
|---|---|
| de laadpaal: de zonverwachting per voorspeller (Forecast.Solar telt op het eind van het uur), een herstart midden in een beurt en de zekering van de groep als vast plafond, de modus zonder planning (Snel, Continu, Zon), "laden tot" en de laadlimiet van de planning, het verslag, de zon en de meter, wekken en fasen, het laadtempo, de accustand, de tijdlijn, het gemeten plafond, een slapende omvormer, het merk van de auto en een slapende Tesla | `docs/laadpaal.md` |
| een Alfen, of iets aan de paalsturing | `docs/alfen.md` |
| groepen met een eigen zekering (een onderverdeelkast) | `docs/groepen.md` |
| de thuisbatterij: de standen, de regelaar en zijn geduld, de batterij die zelf nul op de meter doet, de sensor, de volle beurt, de auto helpen, voorrang bij zon en bij planningen, het laadrendement van de auto, een herstart, en hoe de coach prijslijsten leest | `docs/batterij.md` |
| de vaatwasser: Home Connect, Home Connect Local, een domme vaatwasser, de eindtijd, na de klaar-tijd | `docs/vaatwasser.md` |
| de boiler | `docs/boiler.md` |
| Historie en het rapport, meerdere omvormers, gas en water, eerdere contracten, de lekmelding, en de batterij op de kaart en in de pop-up | `docs/eerste-woning.md` |
| het paneel: de apparaatlijst, de volgorde op het overzicht, waar het schema van een apparaat staat | `docs/paneel.md` |

## Wat gelijk moet blijven

Twee plekken die hetzelfde doen en uit elkaar kunnen lopen. Verander je de ene,
dan de andere in dezelfde uitgave.

- **De paalsturing, voor Easee en Alfen.** Elke wijziging wordt voor allebei
  gebouwd en beproefd (`CHARGER_CONTROL` in const.py; `docs/alfen.md`).
- **Elk nieuw veld van `Plan`** hoort ook in `_tijdlijn` in coach.py, anders
  haalt het het paneel niet; proef 69 in test_coach.py (`docs/laadpaal.md`).
- **De vormen van een prijslijst**: `_prijsrijen` in coach.py en
  `readSchedule` in data-source.js lezen dezelfde vier (`docs/batterij.md`).
- **De voorrang**: `zon_regels` en `plan_regels` in planner.py tegenover
  `zonRegels` en `planRegels` in voorrang.js (`docs/batterij.md`).
- **De vaatwasserprogramma's**: `PROGRAMMAS` in planner.py en
  `DISHWASHER_PROGRAMS` in devices.js; test_rapport.mjs legt ze naast elkaar.
- **De typen met een programma**: `PROGRAMMA_TYPES` in const.py en
  `PROGRAM_TYPES`, `RELEASE_TYPES` in devices.js (`docs/paneel.md`).

## Hoe het in elkaar zit

| bestand | wat het doet |
|---|---|
| `planner.py` | alle denkwerk, kent Home Assistant niet, is los te draaien |
| `planner.py`, onderaan | het denkwerk voor een apparaat met een programma: `plan_programma`, `programma_kosten`, `PROGRAMMAS`, en daaronder dat voor een boiler: `plan_boiler`, `boiler_schijven`, `boiler_nodig` |
| `batterij.py` | het denkwerk voor een thuisbatterij, kent Home Assistant ook niet: `plan_batterij` (de stand), `Regelaar` (de snelle lus), `verdiend`, `terugverdiend`, `rendement_uit_tellers` |
| `coach.py` | leest sensoren, stuurt de paal aan, houdt de laadbeurt bij |
| `websocket.py` | wat het paneel mag opvragen en wijzigen |
| `sensor.py` | de eerste eigen entiteiten (v0.100.0): per apparaat met een programma een sensor "start om", met het geplande tijdstip, voor een keukenkaart of een automatisering. Volgt het besluit op de eventbus, rekent zelf niets (`docs/vaatwasser.md`) |
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
python tests/test_planner.py     # 441 controles op het denkwerk
python tests/test_batterij.py    # 126 op het denkwerk van de thuisbatterij en op de regelaar
python tests/test_coach.py       # 692 op de bedrading, met een nagebouwde HA
python tests/test_virtueel.py    # 1977 op hele laadbeurten in het virtuele huis
python tests/test_archive.py     # 41 op de kwartieropslag
node   tests/test_rapport.mjs    # 109 op het rapport en op het paneel
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
python tools/schaduw.py s.log sturen=<id> zelf=1      # de coach van deze map in de schaduw:
                                                     # wat hij zou doen, zonder iets te schrijven
```

`schaduw.py` is er sinds 25-09-2026, toen in de eerste woning een andere sturing de
batterij had: hij draait de coach uit deze map in het nagemaakte Home Assistant van de
proeven, met de echte toestanden, en schrijft per minuut wat hij zou doen naast wat er
gebeurt. De lus is open (zijn opdrachten gaan nergens heen), dus hij vergelijkt het
doel en niet de regeling.

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
uitgecheckt. Zeg dat dan, en vraag om de privérepo `dev` erbij.
