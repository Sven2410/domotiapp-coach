# Wat een herstart overleeft

De eigenaar op 28-10-2026: "überhaupt alles wat we maken moet een herstart overleven", en "het moet
universeel zijn voor iedereen". In de klantwoning herstartte Home Assistant op 27-10-2026 zes keer: vier
uitgaven en twee stroomstoringen. Wat de coach van een lopende sessie alleen in het geheugen had, begon
daarna opnieuw.

**De regel**: wat de coach telt, leert of al meldde hoort in de opslag, niet alleen in het geheugen. Bij elke
nieuwe regel hoort een proef met een herstart halverwege: een nieuwe coach op dezelfde Home Assistant,
met wat er op schijf stond. Doe hem met een stop (`_async_bij_stop`) en zonder, want een stroomstoring
stopt niets.

## Waar het staat

| wat | waar | sinds |
|---|---|---|
| een lopende laadbeurt (geld, het begin) | de beurten (`BeurtenStore`), `_hervat_uit` | v0.98.0 |
| de knoppen: akkoord, snelladen, pauze, de stand | `sessions` in de instellingen, `_restore` | v0.98.0 |
| een draaiend programma | de beurten, `_async_programma_hervatten` | v0.98.0 |
| de nachttelling van een Growatt | `growatt_dag` bij de batterijrij | v0.171.0 |
| doorladen na een gemiste klaar-tijd, het mikpunt | `GeheugenStore`, `laden:<id>` | v0.172.0 |
| een opwarmbeurt van de boiler | `GeheugenStore`, `boiler:<id>` | v0.172.0 |
| water dat blijft lopen | `GeheugenStore`, `water` | v0.172.0 |
| een programma dat vrijgegeven is maar nog niet draait, en uitruimen | `GeheugenStore`, `programma:<id>` | v0.172.0 |

## GeheugenStore (v0.172.0)

`GeheugenStore` in storage.py is een eigen bestand (`domotiapp_coach.geheugen`), los van de instellingen.
De instellingen gaan bij elke wijziging in hun geheel over de websocket, en een boilerbeurt verandert elke
minuut.

- **Een sleutel per stuk**: `zet(sleutel, data)` werkt alleen het geheugen bij. Is er niets meer te
  onthouden, dan haalt None de sleutel weg.
- **Naar schijf**: `_tick` schrijft na elke ronde, hooguit elke `GEHEUGEN_ELKE` (vijf minuten).
  - Een vraag aan de bewoner, een vrijgave en "te laat" gaan meteen (`meteen=True`).
  - `_async_bij_stop` schrijft altijd.
- **Momenten**: in UTC (`_naar_geheugen`), en terug naar de klok van de coach met `_uit_geheugen`. Zo
  botst het uur dat in de wintertijd twee keer komt niet.
- **Te oud**: een sleutel die langer dan `GEHEUGEN_MAX_UREN` (48) niet bijgewerkt werd, telt niet meer.
- **Teruglezen**: bij de eerste ronde, in `_async_geheugen_laden`, met de beurten.
  - "Te laat", het mikpunt en de lekklok gaan meteen terug.
  - Een boiler en een programma krijgen hun stuk zodra hun sessie er is (`_boiler_terug`,
    `_programma_terug`).

Wat er per sleutel in staat:

- **`laden:<id>`**: of de klaar-tijd voorbij is terwijl de auto niet vol is, en het mikpunt.
  - Gaat de klaar-tijd voorbij terwijl de coach weg is, dan zag hij dat eerder nooit, want de nieuwe sessie
    kende alleen de klaar-tijd van morgen. Nu neemt de eerste ronde het oude mikpunt (`_mikpunt_terug`).
    De auto laadt dan door tot vol, en wacht niet tot morgen op goedkope uren (eis 7).
- **`boiler:<id>`**: wat er in de beurt ging en wat het kostte, de maat voor Bespaard met de prijzen vanaf
  het ijkpunt, `vergeefs` en de meldingen.
  - Of de stroom erop staat en sinds wanneer meet hij opnieuw: `_async_boilers_aan` zet hem bij het stoppen
    aan, en een herstart is geen bewijs dat hij vol is.
- **`water`**: sinds wanneer het water loopt, en of dat al gemeld is.
- **`programma:<id>`**: de vrijgave, de pogingen, de vraag aan de bewoner, de meldingen, uitruimen na een
  beurt, en de prijzen vanaf de vrijgave.
  - Een draaiende beurt staat hier niet, want die staat al in de beurten.
  - De vrijgave zelf blijft van `ready_devices`: staat die er niet meer, dan begint de ronde schoon.
  - Het onthouden gebeurt na de hele ronde van het apparaat (in `_round`), want de vraag aan de bewoner
    komt pas aan het eind.

Proef 213 in `test_coach.py` laat het zien:

- **Te laat**: doorladen na 19:00 blijft na een herstart, ook als de coach van 18:55 tot 19:04 weg was.
- **Boiler**: een boilerbeurt van 2 kW met een herstart halverwege wordt een vat van 0,97 kWh, niet van de
  helft. Alleen de minuut zonder coach ontbreekt.
- **Lek**: een lek met drie herstarts wordt na 121 minuten één keer gemeld.
- **Vrijgave**: "Zet Vaatwasser nu aan" komt na een stroomstoring niet nog eens, en de herinnering noemt
  11:00.

## Wat er nog open staat

Zie de werkbon van 28-10-2026 in de privénotities:

- meldingen die na een herstart nog een keer komen (iets anders stuurt de batterij, de cloud van een
  Growatt, een sensor die stil is);
- een laadbeurt die langer dan een half uur uit stond;
- het kasboek van de batterij tussen twee opslagen;
- leren dat halverwege was (het laadrendement, de stap van de accustand).
