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
