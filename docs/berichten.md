# De berichtenbox en de herinneringen

Uit de eisen van de eigenaar en de werkafspraken in `CLAUDE.md`; die gaan boven alles
hier. Komt er bij een uitgave iets bij over dit onderwerp, schrijf het dan hier.

## Waarom (v0.130.0)

De eigenaar op 18-10-2026: "ik wil een soort berichtenbox met zo'n 1tje wat optelt en dat
je dat kan wegvinken van is gelezen bijvoorbeeld. Berichten zoals denk aan je meterstanden
doorgeven en contract loopt bijna af komen daar in. Ook wil ik een invulveld voor
herinnering meterstanden doorgeven." De bewoner van de eerste woning: "verschillende
looptijden, dus ook een melding van contract bijna verlopen."

## Wat erin komt (`berichten.py`)

Alleen wat de bewoner zelf moet doen; wat de coach meldde en besloot staat onder Meldingen
in de geschiedenis.

- **Meterstanden doorgeven**: de eerste keer op `reminders.meter_date`, daarna elke maand,
  elk kwartaal, elk jaar of eenmalig (`meter_repeat`). De 31e in een kortere maand wordt de
  laatste dag. Het bericht komt op die dag of in de week erna; daarna niet meer.
  **Niet in Portugal** (v0.138.0, `meterstand_bericht` met het land van het contract): daar leest
  de netbeheerder (E-REDES) de slimme meter op afstand, en geeft niemand een stand met laag en
  hoog door. De eigenaar op 19-10-2026: "portugal heeft geen meterstanden dit is iets in
  Nederland." Onder Meldingen staat de groep Herinneringen dan niet, en op het overzicht de kaart
  Je meter niet (`updateMeters_`). Een meter die nog niet op afstand gelezen wordt kan daar wel
  een stand doorgeven, aan E-REDES; daar is de coach niet voor.
- **Een vast contract dat afloopt** (stroom en gas apart): `reminder_days` dagen vooraf
  (standaard 30, `HERINNER_DAGEN`, in te stellen bij de looptijd onder Contract; 0 is
  alleen op de einddatum), en op de einddatum zelf "is afgelopen", tot een week erna.
  Variabel en dynamisch hebben geen einde.
- **De prijscontrole slaat om**: was hij correct en wijkt de opbouw nu af van de all-in
  sensor, dan een bericht, hooguit een per dag. Wie nooit een kloppende opbouw had, ziet
  dat al bij Contract en Voorkeuren.

Elk bericht heeft een sleutel (`meterstanden:2026-11-01`, `contract:stroom:2026-11-10:voor`);
staat die er al, dan komt hij er niet nog eens bij, ook niet na een herstart.

## Hoe

De coach kijkt elke tien minuten (`BERICHTEN_RONDE`) en legt de prijsopbouw eens per uur
naast de all-in sensor (`CONTROLE_RONDE`). Een nieuw bericht gaat in `BerichtenStore`
(storage.py, hooguit `BERICHTEN_MAX`), op de eventbus (`domotiapp_coach_berichten`, te volgen
via `domotiapp_coach/subscribe` met `berichten`), en naar de telefoon en de geschiedenis via
`_async_tell`: het laat iemand iets doen, en dat is wat er naast het verslag naar de
telefoon mag (de eigenaar op 06-09-2026).

Websocket, voor iedereen: `berichten/list`, `berichten/read` (een id, of alles zonder id),
en `reminders/set` voor de herinnering; die zet de bewoner zelf onder Meldingen.

In het paneel een belletje in de kop met het aantal ongelezen berichten (`ongelezen` in
`header.js`, rood bolletje, 9+ boven negen; het getal is een `<i>` omdat de tekst van een
knop in de kop op een smal scherm verdwijnt), en een pop-up met de berichten, nieuwste
bovenaan, met "Gelezen" per bericht en "Alles gelezen" bij twee of meer
(`berichten-sheet.js`).

## Wat gelijk moet blijven

`meterstand_volgende` in berichten.py en `volgendeMeterstand` in views/notifications.js (de
"volgende keer" onder het veld). Proeven: proef 170 in test_coach.py en "de berichtenbox" in
test_rapport.mjs, met dezelfde gevallen.

## Vraag het de DomotiTech Bot: het gesprek, tickets en foto's (v0.220.0)

Sinds v0.223.0 heet dit **Coach Assist** ("Vraag het Coach Assist"). Zie de sectie over de namen hieronder; wat hier
over de bot staat, geldt nu voor Coach Assist.

De eigenaar op 12-11-2026: "Kunnen we niet een soort ticket systeem maken dat klanten aanvraag kunnen doen en ook
gewoon normale vragen kunnen stellen [...] Ik wil het centraal houden dus het moet in een popup komen zoals Vraag het de
DomotiTech Bot snap je? Alles in HA". En: "Lovelace moet een eigen kaart hebben en dat moet hetzelfde zijn in de
coach". Op 13-11-2026, nog voor de uitgave: "Gewoon een vraag stellen over de installatie en echt een ticket aan maken
zijn aparte dingen", met de vragen als één doorlopende chat en een ticket met een soort en een foto.

- **De knop** Vraag het de bot staat in de kop van het paneel, naast Berichten, met een stip zolang er een antwoord
  is dat je nog niet las, in het gesprek en de tickets samen (`ongelezenTickets` in tickets-sheet.js). Het venster
  heeft twee tabbladen: **Vragen**, het gesprek met onderaan het veld, en **Tickets**, de lijst (nieuwste eerst,
  met nummer, soort, stand en tijd), een gesprek per ticket, en Nieuw ticket: Storing of Aanvraag, tekst, en tot vier
  foto's. Tekst is altijd tekst.
- **Het gesprek** is één doorlopende chat per huis, met de vorm van een ticket: `id` 0, soort `vraag`, zonder stand
  of onderwerp. Het bestaat altijd. Een vraag is `reply` op 0, een antwoord `answer` op 0; hoogstens 60 berichten per
  uur per gebruiker. `list` en `subscribe` geven het apart, als `gesprek`, met de laatste 100 berichten.
- **Een ticket** is een storing of een aanvraag, met een nummer per huis dat nooit terugkomt, een onderwerp uit de
  eerste regel (80 tekens), 1 tot 4000 tekens (leeg mag met een foto), hoogstens 20 nieuwe per uur per gebruiker; een
  reactie op een ticket dat klaar was zet het terug op nieuw.
- **Foto's** gaan over HTTP (bijlagen.py): `POST /api/domotiapp_coach/tickets/bijlage` (ingelogd, veld `bestand`,
  jpeg, png of webp, gekeurd op de eerste bytes, hoogstens 10 MB) en `GET .../bijlage/<id>`. Het paneel verkleint vooraf
  tot een JPEG van hoogstens 2000 px en bekijkt ze met een ondertekend pad (`auth/sign_path`). Ze staan in
  `.storage/domotiapp_coach_bijlagen/`, dus ze overleven een herstart en zitten in de back-up; wat na een uur nog aan
  geen bericht hangt gaat weg. Alleen bij tickets, niet in het gesprek.
- **De opslag**: `TicketsStore` in storage.py (`domotiapp_coach.tickets`), na elke wijziging weggeschreven, één
  wijziging tegelijk. Wat een wijziging is staat in tickets.py, dat Home Assistant niet kent.
- **De websocket**, `domotiapp_coach/tickets/`: `list`, `subscribe`, `new`, `reply`, `read` voor elke gebruiker
  (`new` en `reply` niet voor een systeemgebruiker), `answer` en `set_state` alleen voor een beheerder. `subscribe`
  stuurt eerst het gesprek en de tickets met het contract als event, daarna elk ticket dat verandert (het gesprek met
  `id` 0). Een fout komt met een code en een zin in de taal van de installatie.
- **De gebeurtenis** `domotiapp_coach_ticket` bij een vraag, een nieuw ticket, een reactie en een antwoord, met
  `ticket_id`, `bericht_id`, `van`, `soort`, `stand` (leeg bij het gesprek) en `bijlagen` (het aantal foto's).
- **Na een antwoord** een pushmelding naar wie de soort Antwoorden van DomotiTech aan heeft (`tickets` in
  ontvangers.py, standaard aan): "DomotiTech heeft je vraag beantwoord" in het gesprek, "DomotiTech heeft geantwoord op
  je vraag #12" bij een ticket. Tikken opent het dashboard.
- **Het contract** met de kaart van DomotiApp Lovelace is `CONTRACT` in tickets.py (1): toevoegen mag, hernoemen of
  weghalen alleen met een hoger getal. De standen zijn `nieuw`, `in_behandeling`, `bij_beheerder` en `klaar`.

Proef 264 en 265 in test_coach.py; de stip, de lijst, het gesprek en de foto in test_rapport.mjs.

## De namen: COACH en Coach Assist (v0.223.0)

De eigenaar op 13-11-2026 over zijn bedrijfsstructuur: DomotiTech is het bedrijf, DomotiApp de app, **COACH** het
energiemanagementsysteem en **Coach Assist** de digitale hulp. Over de meldingen na een antwoord: "Meldingen boven
moeten niet DomotiTech zijn maar DomotiApp en dan de coach. Niet meer bot". COACH in hoofdletters als naam en titel;
in een gewone zin blijft het "de coach".

- **COACH**: de zijbalk (`PANEL_TITLE`), de kop van het paneel, de naam bij Integraties en in HACS (`manifest.json`,
  `hacs.json`, `strings.json` en de vertalingen), de titel van elke melding van het systeem (`coach.py`, `monitor.py`),
  het rapport en de bestandsnaam van het rapport en het bestand voor Excel.
- **Coach Assist**: de knop en het venster ("Vraag het Coach Assist", Engels "Ask Coach Assist"), de soort in Meldingen
  (Antwoorden van Coach Assist), de afzender van een antwoord, en de pushmelding na een antwoord: titel Coach Assist,
  "Coach Assist heeft je vraag beantwoord" of "Coach Assist heeft geantwoord op ticket #12". Boven het venster staat
  DomotiApp.
- **Een oud antwoord** staat in de opslag met de naam DomotiTech. Het veld blijft zoals het is (`CONTRACT` 1); het
  paneel toont een antwoord met die naam of zonder naam als Coach Assist (`afzender` in tickets-sheet.js). Een nieuw
  antwoord krijgt de naam Coach Assist (`antwoord` in tickets.py).
- **Wat niet verandert**: het domein `domotiapp_coach`, de entiteit-id's, de opdrachten, het event
  `domotiapp_coach_ticket`, de repo en de bestandsnamen. Dat zou installaties breken.
- **De fabrikant van de apparaten bleef tot v0.225.0 DomotiApp Coach.** De kaarten van DomotiApp Lovelace zoeken de
  apparaten van de coach op die naam (`COACH_FABRIKANT`), ook in de apparaatkiezer van hun editors. De uitrol
  installeert coach en lovelace los van elkaar, dus een klant met een oudere lovelace zou die kaarten kwijtraken.
  Omzetten kon pas als elke klant een lovelace had die beide namen kent (0.125.0 of nieuwer); zie hieronder, v0.225.0.
- **Het logo van COACH** (dezelfde dag, "Dat logo moet op alles komen te staan"): een blauwe zeshoekige C met een
  bliksem. Het staat in `frontend/img/coach.png` (`LOGO_URL` in theme.js) voor de kop van het paneel, het venster van
  Coach Assist en het rapport (daar op wit, `jpegVan`), en in `brand/` (`icon.png` en `logo.png` op 256,
  `@2x` op 512) voor Integraties in Home Assistant. Ook bovenaan de README en als `hacs-icon.png`. Het merkteken
  van DomotiTech is uit het paneel. De zijbalk van Home Assistant kent alleen een mdi-icoon; dat blijft
  `mdi:home-lightning-bolt`, al een bliksem.

## Het gesprek zoals WhatsApp (v0.224.0)

De eigenaar op 15-11-2026, nadat een bewoner het vragengesprek een paar keer gebruikte: "kijk even goed hoe whatsapp het
doet. Blokken rechts van je eigen tekst, blokken links van de antwoorden. En duidelijk aangeven of het de gebruiker is met
de naam of de coach snap je", "standaard naar het laatste bericht scrollen, ipv bovenaan beginnen", en "Evt de
historische dagen ingevouwen? Tot een week max".

- **Rechts** staat wat de gebruiker die kijkt zelf schreef (`eigen` in tickets-sheet.js: `user_id` gelijk aan de zijne).
  Een bericht van een bewoner zonder `user_id`, of zonder gebruiker die kijkt, telt als eigen, zoals tot dan.
  **Links** staan Coach Assist en elke huisgenoot, zoals WhatsApp in een groep.
- **De naam** staat boven elk blok, ook boven het eigen. Een antwoord heet Coach Assist (`afzender`), met het logo klein
  ervoor; Coach Assist is wie praat, niet COACH.
- **Een blok** is hoogstens 80% breed: het eigen in de accenttint, links het gewone vlak. De tijd staat klein onderaan in
  het blok (alleen uu:mm); de dag staat in de scheiding.
- **Per dag een scheiding** in het midden (`dagTekst`): "Vandaag", "Gisteren", binnen een week de weekdag met de datum
  ("Vrijdag 13 november"), daarna de datum, met het jaar als dat een ander is.
- **Eerdere dagen in een keuzelijst, alleen in het gesprek (id 0)**. Eerst waren het knoppen per dag; de eigenaar op
  15-11-2026: "Bij datum een dropdown niet zo veel datums laten zien ivm ruimtegebrek".
  - De laatste dag met berichten staat open. Dat is niet per se vandaag: anders zag je bij een stil gesprek niets.
  - Elke dag met een antwoord dat de gebruiker nog niet zag staat ook open.
  - De andere dagen staan bovenaan in één keuzelijst "Eerdere dagen", nieuwste eerst, met het aantal berichten
    ("Gisteren · 3 berichten"). Wat meer dan een week (`GESPREK_DAGEN`) voor het laatste bericht ligt, is daarin één
    keuze "Oudere berichten". Weg is het niet.
  - Een gekozen dag komt op zijn plek in het gesprek, en het gesprek schuift naar het begin ervan. Hij blijft staan tot
    het venster weer opengaat (`gekozenDag_`), ook als er intussen een bericht bijkomt. Alleen vandaag: geen lijst.
  - De keuzelijst en het tekstvak staan op 16 px: met minder zoomt Safari op iOS in zodra je ze aantikt (de
    lovelace-sessie op 15-11-2026).
  - Een ticket is kort: daar alleen de scheiding.
- **Naar onderen** (`naarOnder_`): bij openen, bij een ander tabblad of ticket, en na het eigen bericht. Een antwoord dat
  binnenkomt alleen als het gesprek al (bijna, 40 px) onderaan stond, en na het laden van een foto ook.
  - Tot v0.224.0 opende het venster bovenaan. `paint_` zette `scrollTop` terwijl het gesprek nog verborgen was, en dan
    doet dat niets. Nu scrolt `open()` pas na `openSheet`.

**Gelijk aan de kaart van DomotiApp Lovelace** (`bot-scherm.js`, `bot-logica.js`, lovelace 0.127.0): de zijden, de namen,
de scheiding, wat open staat, de keuzelijst en wanneer hij naar onderen gaat, zoals op 15-11-2026 met die sessie
afgesproken. Het
contract met de kaart verandert er niet door.

Op het scherm nagemeten op 390, 320 en 280 px. De proef "het gesprek zoals WhatsApp" in test_rapport.mjs.

## Het pakket: een grens op vragen en tickets per dag (v0.225.0)

De eigenaar op 15-11-2026: klanten krijgen een abonnement met een grens per dag, "Zo wordt het ook niet overvol en kan
ik alles managen", en "nee elk abbo heeft geen maandlimiet". Voor nieuwe tickets ook: "ook om spammen te voorkomen max
aantal per dag snap je?". En: "ik wil bij de coach assist ook zien welk abbo je hebt". Welke pakketten er zijn en wie
wat heeft, beheert de mini-pc. De coach kent alleen wat hem met `set_plan` gezegd wordt. Er staat geen naam van een
pakket in de code. De afspraak staat in de privénotities, bij de afspraak over de tickets.

- **Wat telt**, per kalenderdag in de tijdzone van Home Assistant:
  - een vraag in het gesprek (`reply` op 0, `van: "klant"`);
  - een nieuw ticket (`new`, storing en aanvraag samen).
  - Een reactie op een ticket telt niet. Er is geen grens per maand.
- **Geteld uit wat er bewaard is** (`pakket_stand` in tickets.py): de berichten in het hele gesprek, niet alleen de
  laatste `GESPREK_MAX`, en `gemaakt` van de tickets. Er is geen eigen teller, dus na een herstart klopt het vanzelf.
  Een tijd in UTC telt op de dag van het huis.
- **`set_plan`**, alleen een beheerder:
  - `naam` (1 tot 40 tekens, of `null`: geen pakket);
  - `vragen_per_dag` en `tickets_per_dag` (1 tot 1000, of `null` voor onbeperkt; `tickets_per_dag` mag ontbreken).
  - Bewaard in `TicketsStore`, onder `pakket`.
- **`list` en `subscribe`** hebben altijd `pakket`: `null`, of `naam`, `vragen_per_dag`, `vragen_vandaag`, `vragen_over`,
  `tickets_per_dag`, `tickets_vandaag`, `tickets_over` en `opnieuw` (de volgende middernacht, met de juiste offset op
  een dag van 23 of 25 uur).
- **Events:** na een vraag en na een nieuw ticket gaat het pakket mee in het event van `subscribe`
  (`{"ticket", "pakket"}`). Na `set_plan` komt een event met alleen `{"pakket"}`. Na een antwoord, gelezen of een stand
  komt er geen pakket mee.
- **Op de grens: de fout `pakket_op`**, met een eigen zin voor vragen en voor tickets. Er is dan niets bewaard (ook
  geen foto vastgemaakt) en er gaat geen gebeurtenis af. Zonder pakket is er geen grens; de 60 berichten en 20 tickets
  per uur per gebruiker blijven.
- **Geen Coach Assist** (`coach_assist` onwaar; de eigenaar: "Dan moet er geen AI assistant in
  zitten etc"): een vraag, een nieuw ticket en een reactie geven de fout `geen_coach_assist`. Er wordt niets bewaard.
  Wat er al was blijft in `list` staan. `coach_assist` mag ontbreken,
  dan is hij waar. **Sinds v0.226.0 wel een storing** (de eigenaar: "Ja zonder care wel een storing melden"): een
  nieuw ticket als storing en een reactie op een ticket kunnen, met de grens `tickets_per_dag` (de mini-pc stuurt er
  dan 3). Een vraag en een aanvraag niet, met de zin "Coach Assist zit niet in je abonnement. Een storing melden kan
  altijd." De knop in de kop heet dan Meld een storing. Het venster heeft dan alleen Tickets, en Nieuw ticket alleen
  Storing, zonder etiket. Contract laat de grens op tickets zien.
- **Het abonnement in het paneel** (de eigenaar: "ja maar ook in de coach zelf"), alleen als er een pakket is:
  - het bovenschrift van het venster wordt de naam als etiket (zonder pakket staat er COACH);
  - een klein etiket naast COACH in de kop, dat op een telefoon net als COACH zelf wegvalt;
  - op Contract een kaart Abonnement, met vragen en tickets per dag en wat er vandaag over is.
- **Het venster:**
  - Onder het veld staat "Nog 7 vragen vandaag", opvallender bij 3 of minder.
  - Op 0 vragen gaat het veld dicht. Eronder komen de zin en een knop "Meld een storing" die Nieuw ticket opent met
    Storing gekozen en de getypte vraag erin.
  - Bij tickets staat "Nog 2 tickets vandaag" naast Nieuw ticket, alleen bij 2 of minder.
  - Op 0 tickets is Nieuw ticket weg, met de zin, en ook "Meld een storing" en Versturen.
  - Na `opnieuw` gaat alles vanzelf weer open, ook zonder bericht van de coach.
  - Gelijk aan de kaart van DomotiApp Lovelace.

Proef 268 in test_coach.py, met een herstart halverwege de dag en middernacht. De proef "het pakket" in
test_rapport.mjs.

## De fabrikant COACH, en nergens meer DomotiApp (v0.225.0)

De eigenaar op 15-11-2026: "de coach staat los snap je? Dus niks van domotiapp namen in de coach".

- **De fabrikant** van de apparaten is nu COACH (tot dan "DomotiApp Coach"). Op 15-11 had elke klant met een coach
  lovelace 0.126.0 of 0.127.0, en lovelace kent sinds 0.125.0 allebei de namen. De identifiers zijn dezelfde, dus het
  blijft hetzelfde apparaat met een nieuwe fabrikant.
- **Het log en de console** zeggen COACH of `[COACH]`.
- **Het bovenschrift** van Coach Assist zegt COACH, of de naam van het abonnement.
- **De technische namen blijven** (`domotiapp_coach`, de repo, id's, events, bestandsnamen), net als het commentaar
  dat over de geschiedenis gaat.
- **De proef** "nergens DomotiApp" in test_rapport.mjs leest elke .js, .py en .json van de integratie zonder
  commentaar. Hij valt om op elke DomotiApp in tekst, behalve een klassenaam.

