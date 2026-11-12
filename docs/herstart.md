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
| iets anders stuurt de batterij, hij volgt niet, de Growatt weigert | `GeheugenStore`, `batterij:<id>` | v0.173.0 |
| een ander laadschema in de Growatt: wanneer vervangen, en of hij het laat staan | `GeheugenStore`, `batterij:<id>` (`growatt_vreemd`, `growatt_laat`) | v0.215.0 |
| meldingen die al gedaan zijn | `GeheugenStore`, `meldingen` | v0.173.0 |
| een airco die niet luistert: de pogingen en of het gemeld is | `sessions` (`airco_miss`, `airco_try`, `airco_miss_told`) | v0.205.0 |
| wat een kamer met een airco doet: het geleerde | `airco_learned` in de instellingen | v0.207.0 |
| het venster waarin de kamer gemeten wordt, sinds wanneer de airco uit staat | `GeheugenStore`, `airco-leren:<id>` | v0.207.0 |
| een paal die een auto meldt die zelf zegt dat hij weg is: al gemeld | `GeheugenStore`, `auto-weg:<paal>` | v0.208.0 |
| de auto komt terug na een paal die bleef hangen: een nieuwe beurt, ook na een herstart | `auto-weg:<paal>`, en `laden:<paal>` gaat mee weg | v0.216.0 |
| wanneer de coach de auto voor het laatst dichtbij zag | niet: na een herstart telt weg vanaf de herstart, zoals `last_changed` | v0.213.0 |
| een paal die offline is: sinds wanneer, herladen, gemeld | `GeheugenStore`, `paal-offline:<paal>` | v0.209.0 |
| wat de paal in de storing zei, zodat online na een herstart de storing niet beëindigt | `GeheugenStore`, `paal-offline:<paal>` (`tekens`) | v0.210.0 |
| een paal die deze beurt al klaar meldde, met de ene herstart | `GeheugenStore`, `paal-klaar:<paal>` | v0.209.0 |
| voor welke klaar-tijd er al herinnerd is om de auto aan te sluiten | `GeheugenStore`, `herinnering:<paal>` | v0.212.0 |
| het verbruik van de auto vandaag, en de laatst bekende accustand | `GeheugenStore`, `autoverbruik:<paal>:<auto>` | v0.212.0 |
| het verbruik van de auto per dag, acht weken | `car_usage` in de instellingen | v0.212.0 |

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

- **`batterij:<id>`** (v0.173.0): sinds wanneer iets anders hem stuurt (`vreemd`).
  - Dan laat de coach hem een uur los (`VREEMD_PAUZE`). Zonder dit nam hij hem na een herstart meteen weer
    over, en kwam "Iets anders stuurt" opnieuw.
  - Ook: of hij de coach niet volgt en dat gemeld is, en wat de cloud van een Growatt weigerde
    (`growatt_gemeld`, `growatt_houden_mis`).
  - Ze komen terug zodra de sessie er is (`_batterij_sessie`).
- **`meldingen`** (v0.173.0): de vlaggen van meldingen die één keer horen te komen zolang de toestand
  blijft:
  - een integratie die niet opkomt, met sinds wanneer;
  - een batterij die te warm is;
  - een vriezer of koelkast;
  - een smart plug die uit staat, en sinds v0.178.0 sinds wanneer, of hij ooit bereikbaar was en of hij de
    gewone melding "nog niet bereikbaar" al kreeg;
  - sinds v0.178.0 welke sensoren ooit iets zeiden (voor "het internet thuis weg");
  - de vraag naar de accustand;
  - een tip;
  - de waarschuwing dat de pauze de klaar-tijd kost.

  Is de toestand na de herstart voorbij, dan ruimt de wacht zijn vlag op zoals altijd.

Proef 213 in `test_coach.py` laat het zien:

- **Te laat**: doorladen na 19:00 blijft na een herstart, ook als de coach van 18:55 tot 19:04 weg was.
- **Boiler**: een boilerbeurt van 2 kW met een herstart halverwege wordt een vat van 0,97 kWh, niet van de
  helft. Alleen de minuut zonder coach ontbreekt.
- **Lek**: een lek met drie herstarts wordt na 121 minuten één keer gemeld.
- **Vrijgave**: "Zet Vaatwasser nu aan" komt na een stroomstoring niet nog eens, en de herinnering noemt
  11:00.

Proef 214 (v0.173.0):

- **Iets anders stuurt**: na een stroomstoring blijft de batterij los. De coach schrijft niets en meldt het
  niet opnieuw. Na het uur van voor de herstart neemt hij hem weer over.
- **Te warm**: de temperatuurmelding komt één keer, ook met een herstart terwijl hij te warm blijft.
- **Alle vlaggen**: ze gaan heen en weer naar de opslag, met de momenten in de tijd van het huis.

## Wat er in een apparaat achterblijft (v0.174.0)

Wat de coach in een apparaat zet, hoort veilig te zijn als hij wegvalt. Het laadschema van een Growatt
herhaalt zich elke dag, en bleef na een vak staan als de accu de stopgrens niet haalde. Nu gaat het er na
het vak uit, en schrijft de coach het volgende vak pas een half uur vooraf. En een dag die een herstart
de nachttelling kostte, rekent hij achteraf na uit de kwartieropslag en de recorder, in plaats van hem
weg te laten (`docs/batterij.md`, v0.174.0).

Sinds v0.179.0 bewaart `growatt_dag` altijd een begin, ook na een nacht zonder vak. Een telling van een
eerdere coach zonder begin zoekt het laatste vak in de kwartieren op (`docs/batterij.md`, v0.179.0).

## Eerst herstellen, dan sturen (v0.217.0)

In een klantwoning startte Home Assistant op 12-11-2026 om 11:21 opnieuw. De zonvoorspeller was er om
11:23:20, een paar seconden na de eerste ronde van de coach. Die had toen al de schatting uit de eigen
opwek en het weer genomen (6,3 kWh zon) en hield die een half uur vast (`ZON_VERVERSEN`). Met die zon
plande de batterij laden van het net, en om 11:43 stond dat als vak in de Growatt. Om 11:53 kwam de echte
kromme (31,2 kWh), en pas om 13:14 ging het vak eruit. De eigenaar: "laat dit dan ook alle andere fouten
oplossen [...] We moeten het zo bouwen dat hij leert van alle verschillende merken en installaties."

**De regel**: een reserve of een lege uitkomst houdt de coach niet vast als de echte bron er weer is. Wat
hij niet uit de bron kreeg, vraagt hij na `OPSTART_OPNIEUW` (een minuut) opnieuw, en niet pas na de
gewone verversing. Een goede uitkomst houdt hij zo lang als altijd. Eén hulpfunctie, `_ververs_om`:

| bron | gewoon | wat er niet lukte | nu |
|---|---|---|---|
| de zon (`_async_zonkromme`) | 30 min | een schatting terwijl er een voorspeller is ingesteld (energiedashboard of de integratie achter de zonsensoren, `_async_voorspeller`) | elke minuut de voorspeller opnieuw; de schatting uit de opwek (een databaselezing) blijft eens per half uur |
| het huisverbruik (`_async_huisverbruik`) | 1 uur | de eigen opslag gaf een fout | over een minuut |
| het jaarsaldo voor salderen (`_async_jaarsaldo`) | 24 uur | de recorder gaf een fout; tot nu was het saldo dan een dag weg | het vorige blijft, over een minuut |
| de schaal van de terugleverkosten (`_async_schaal`) | 24 uur | hetzelfde | het vorige blijft, over een minuut |
| Nord Pool (`_async_nordpool`) | 10 min | vandaag leeg: de dienst is er nog niet | over een minuut; morgen leeg blijft tien minuten, want die komt pas rond 13:00 |
| het soort Growatt (`_async_growatt_soort`) | 1 uur | geen acties vlak na de opstart (`INTEGRATIE_OPSTART`) | over een minuut; daarna een uur, zoals een Growatt die het niet kan |

Zonder voorspeller verandert er niets. Wat er vóór v0.217.0 al zo was: de accustand van een Growatt
(v0.162.0, elke ronde) en de dagen zon van voor de coach (v0.196.0, een kwartier, want dat zijn dagen
van vroeger en geen bron voor nu).

**Leren hoe lang een integratie nodig heeft** (`_async_opstart_meten`). Per integratie achter de
entiteiten van de coach, dus per merk (de paal, de batterij, de auto, de meter, de prijzen), de seconden
tussen de eerste ronde van de coach en het moment dat er iets van terugkwam: de vroegste `last_changed`
van wat niet `unavailable` is. Wat er bij de eerste ronde al was telt als 0. Voor de zonvoorspeller de
eerste ronde met een echte kromme (`zon:<integratie>`), dus op de minuut. Zodra alles er is, of na een
kwartier, één regel in het log:

```
na de opstart: accumerk na 150 s, paalmerk na 0 s, zon:forecast_solar na 120 s
```

Als info, en als waarschuwing als er iets niet binnen het kwartier kwam. De uitkomst staat in de
instellingen (`startup_learned`, de laatste vijf per integratie, `None` voor niet gekomen), dus ook na de
volgende herstart. Na een herladen door de coach (v0.166.0, v0.188.0) hetzelfde, vanaf het herladen,
onder `reload`.

Proef 259 in test_coach.py; `growatt-opstart` en `growatt-opstart-nooit` in het virtuele huis.

## Wat er nog open staat

Zie de werkbon van 28-10-2026 in de privénotities:

- een wekpoging en een proefladen die na een herstart opnieuw beginnen (`_woken`, `_proef`);
- een laadbeurt die langer dan een half uur uit stond;
- het kasboek van de batterij tussen twee opslagen;
- leren dat halverwege was (het laadrendement, de stap van de accustand).
