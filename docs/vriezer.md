# De vriezer en de koelkast

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

## De koelkast (v0.131.0)

Uit een beheersessie in een klantwoning met een Miele-koelkast aan de integratie `miele`
(18-10-2026). De eigenaar koos daar "ja, meldingen voor de koelkast ook": alleen uitlezen en
melden, net als de vriezer. De grens koos hij op 19-10-2026: "boven de 10 graden". Met die van
de vriezer zou een koelkast op 5 °C na een half uur elke keer melden.

| melding | wanneer | constante in coach.py |
|---|---|---|
| de deur staat open | na 3 minuten, net als de vriezer | `VRIEZER_DEUR` |
| de koelkast is te warm | een half uur warmer dan 10 °C | `KOELKAST_GRENS_C`, `VRIEZER_WARM` |
| de koelkast meldt een storing | meteen | |

Het is dezelfde wacht (`_async_vriezerwacht`), met per soort de naam en de grens in
`KOELWAREN`; `KOELWAREN` in devices.js zegt hetzelfde in het paneel (de hints en de zin onder
het apparaat, `koelUitleg`). Weer goed is een graad onder de grens, dus 9 °C. De merken zijn die
van de vriezer (`KOELKAST_BRANDS` in const.py), allebei `readOnly`. Bij Miele zijn het de
sensor Temperatuur (of de climate van de koelkast zelf), de binary_sensor Deur en de
binary_sensor Probleem; ook hier zet Miele er twee spookzones bij (`zone_2`, `zone_3`).

Een koelkast aan een smart plug blijft ook kunnen (`STEKKER_APPARATEN`): dan meet de coach het
verbruik en kan hij hem altijd aan houden, maar meldt hij niets over de temperatuur.

Proef 172 in test_coach.py, de proef "de koelkast" in test_rapport.mjs.

## Miele komt terug met 0,0 (v0.141.1)

Een klantwoning op 21-10-2026: de cloud van Miele viel weg van 15:51:08 tot 16:29:53 UTC, en
bij het terugkomen meldden vriezer en koelkast ruim twintig seconden 0,0 voor de echte -18 en
5; de koelkast deed hetzelfde om 10:21:57 (16 seconden). Een melding gaf dat niet, want "te
warm" wacht een half uur, maar de wacht begon wel te lopen. Nu telt een 0,0 binnen twee minuten
nadat de temperatuur niets zei (`KOEL_NUL`) niet als meting. Blijft hij 0,0, dan wel. Proef 186
in test_coach.py.
