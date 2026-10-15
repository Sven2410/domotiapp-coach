# De vriezer

Komt er bij een uitgave iets bij over dit onderwerp, schrijf het dan hier. De eisen van de
eigenaar en de werkafspraken staan in `CLAUDE.md` en gaan boven alles hier.

## Uitlezen en melden (v0.125.0)

De eigenaar op 15-10-2026: "Ik wil dat de coach wel weer de apparaten aanmaakt: Wasmachine
droger en vriezer." Voor de vriezer koos hij "Uitlezen en melden": temperatuur en deur
bijhouden, en een melding als de deur te lang openstaat, de temperatuur oploopt of de vriezer
een storing meldt. **De coach stuurt de vriezer niet.** Aanleiding was een klantwoning met een
Miele-vriezer aan de integratie `miele` van Home Assistant.

**De keuzes van de eigenaar** (15-10-2026, uit drie voorstellen elk):

| melding | wanneer | constante in coach.py |
|---|---|---|
| de deur staat open | na 3 minuten | `VRIEZER_DEUR` |
| de vriezer is te warm | een half uur warmer dan -15 °C | `VRIEZER_GRENS_C`, `VRIEZER_WARM` |
| de vriezer meldt een storing | meteen | |

Elke melding komt één keer, kritiek, want het is iets wat de bewoner zelf moet oplossen (zie
de afspraak over meldingen in CLAUDE.md); wie hem krijgt staat per persoon onder Meldingen.
Weer goed (de deur dicht, een graad onder de grens, geen storing meer) staat alleen in de
geschiedenis. Tussen de grens en een graad eronder blijft het zoals het was (`TEMP_TERUG`),
zodat een vriezer op -15 °C niet heen en weer meldt. `_async_vriezerwacht` en `_vriezer_stand`
in coach.py, elke ronde; wat er gemeld is staat in het geheugen, dus na een herstart begint de
klok opnieuw.

**De velden** (`VRIEZER_BRANDS` in devices.js en const.py, merken Miele en Overig, allebei
`readOnly`): Temperatuur (een sensor, of de climate van de vriezer zelf: dan
`current_temperature`, `_vriezer_temp`), Deur en Storing, die laatste twee optioneel. Bij Miele
zijn dat de sensor Temperatuur, de binary_sensor Deur en de binary_sensor Probleem. Miele
zet er twee climate-zones bij (`zone_2`, `zone_3`) met een temperatuur van niets en een bereik van
7 tot 35 graden: die bestaan bij een vriezer niet echt, en de hint bij het veld zegt het. Een
vermogenssensor mag (een vriezer op een meetstekker), een vinkje om te sturen is er niet; op die
plek staat wat de coach wel doet. Op het overzicht staat hij niet, want daar staan alleen
apparaten die de coach stuurt (`updateSteerable_` in overview.js laat `isReadOnly` weg, ook met
een oud vinkje). De sensorwacht kijkt mee naar de temperatuursensor (`_temp_nodig`).

**De kaart** van DomotiApp Lovelace (`domotiapp-vriezer-card`, lovelace 0.70.0) leest alles uit
Miele zelf; een entiteit van de coach is er niet voor nodig, en die is er dus ook niet.

Proef 161 in test_coach.py, een proef in test_rapport.mjs. Geen scenario in het virtuele huis:
de vriezer heeft geen energie, prijs of planning, en de meldingen zijn per ronde volledig na te
bootsen in de proef.
