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
