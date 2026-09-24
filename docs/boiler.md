# De boiler

Uit `CLAUDE.md` gehaald op 24-09-2026, zodat dat bestand kort blijft. De eisen
van de eigenaar en de werkafspraken staan daar en gaan boven alles hier.
Komt er bij een uitgave iets bij over dit onderwerp, schrijf het dan hier.

Sinds 19-09-2026 stuurt de coach ook een boiler, na de eigen "ik wil gewoon een
sturing maken op een boiler waar je alleen stroom op moet zetten, met een smart
plug bijvoorbeeld. Als je er stroom op zet en de boiler is warm moet de coach
detecteren dat hij warm genoeg is omdat de boiler dan onder een bepaald
vermogen zit. Ik wil dit zelflerend hebben. Alleen de switch invullen en power
invullen."

**Twee velden, en verder niets.** De schakelaar (`switch` in `entities`, een
smart plug, een switch of een input_boolean) en de vermogenssensor die elk
apparaat al heeft. Geen merk, geen temperatuur, geen tabel: `FIELDS_BY_TYPE` in
devices.js geeft een type zijn eigen velden zonder dat er een merk aan te pas
komt, en `canSteer` telt een boiler met een schakelaar gewoon mee.

**De coach schakelt, de thermostaat beslist hoe warm.** Dezelfde afspraak als
"geen fasewissel" en "de coach kiest nooit zelf een programma": wij kiezen het
moment, het apparaat kiest de temperatuur. Daardoor kan dit niets kapotmaken en
niets onveiligs doen, en blijft de legionellaronde van de boiler zelf staan.

**Een boiler is geen programma-apparaat maar een buffer**, en staat daarmee
dichter bij de auto dan bij de vaatwasser: er moet een hoeveelheid energie in
vóór een moment, hij mag onderbroken worden, en de goedkoopste blokken mogen er
zelf uit gekozen worden. `boiler_schijven` in planner.py zet elk blok tussen nu
en de klaar-tijd op een prijs per kWh (eigen zon tegen de terugleverprijs, de
rest tegen de prijs van dat uur, precies zoals `charge_cost` bij de paal), en
`goedkoopste` pakt daar de goedkoopste uit. Eén schijf per blok en niet twee,
want een boiler moduleert niet: hij staat aan op zijn eigen vermogen of hij
staat uit. In de avondpiek telt alleen een blok dat de zon helemaal draagt
(eis 4). De eigenaar koos "klaar om, zoals de auto" (`DEADLINE_ONLY_TYPES`), en
zonoverschot mag hij pakken: staat er meer overschot dan het element trekt, dan
gaat hij aan, want het vat is de goedkoopste plek om overschot in te stoppen.

**Wat hij zelf leert** staat per apparaat in `boiler_learned` in de
instellingen, als lopend gemiddelde over de laatste beurten (`METING_MAX_N`):
het vermogen van het element, hoeveel er in een vol vat gaat (de grootste volle
beurt die hij zag, want dat is een grens uit de natuurkunde), wat er per uur uit
het vat gaat (afkoelen en douchen samen, over de tijd tussen twee volle beurten),
wanneer het vat voor het laatst vol was en wanneer er voor het laatst
werkelijk stroom liep. Te wissen met `device/measurements/clear`, hetzelfde
commando als bij de vaatwasser. Zolang er nog niets gemeten is rekent de coach
niet maar meet hij: aanzetten en kijken (`leren`).

**"Vol" is een meting.** Er staat stroom op, de aanloop is voorbij
(`BOILER_AANLOOP`), en hij trekt `BOILER_STIL` lang niets meer: dan is het vat
vol. De grens waaronder "niets" begint is een vijfde van het gemeten
elementvermogen, met `BOILER_DRAAI_W` als bodem. Gaat de stroom eraf, dan weet
de coach niets meer; daarom gelooft hij een verse meting `BOILER_KIJKEN` lang
(drie uur) en kijkt hij daarna opnieuw door even aan te zetten (`proef`). Dat
kost niets zolang het vat vol is, want dan vraagt de boiler geen stroom.

**Drie valkuilen die het virtuele huis eruit haalde**, alle drie op 19-09-2026:

1. *Aan en uit, elke minuut.* Een proef die na één ronde alweer door het gewone
   plan werd afgebroken. Een proef loopt nu af (`proef_sinds`), en pas als hij
   iets opgeleverd heeft telt het plan weer mee.
2. *De boiler at zijn eigen overschot op.* Zodra hij aanging zakte de
   teruglevering onder zijn eigen vermogen en zette de zonregel hem weer uit.
   Het overschot dat de coach gebruikt is daarom wat er naar het net zou gaan
   als deze boiler níet liep, net als bij de paal.
3. *Bijvullen wat een thermostaat niet aanneemt.* Vlak na een volle beurt zegt
   de som "er kan nog 0,8 kWh bij", vraagt de boiler niets, noemt de coach dat
   vol, en begint hij opnieuw. Een verse volmeting gaat daarom vóór de som
   (`boiler_nodig`), en onder `BOILER_KRUIMEL` van het vat valt er sowieso
   niets te verwarmen.

**Vol of een stekker die niets doet**, dat is het lastigste onderscheid van
deze sturing: allebei leveren ze nul watt. Wat ze uit elkaar houdt is de tijd.
Een vat loopt leeg, dus na `vol_kwh / verbruik` uur moet elke werkende boiler
een keer warmte gevraagd hebben; is er in die hele tijd geen watt gelopen, dan
is het de stekker (`BOILER_VERDACHT`). Geteld vanaf de laatste keer dat hij
werkelijk iets trok (`getrokken_op`) en niet vanaf de laatste keer dat de coach
"vol" concludeerde, want dat laatste schuift bij elke vergeefse poging mee op.
Na `BOILER_VERGEEFS` vergeefse pogingen zegt hij het één keer op de telefoon en
houdt hij op met schakelen (`geen-stroom`), tot het volgende kijkmoment.

**Meldingen: alleen als er iets aan de hand is.** Dat een boiler om drie uur
's nachts weer warm is hoeft niemand te wekken; dat verslag gaat wel de
geschiedenis in (`telefoon=False`). Op de telefoon komt alleen de stekker die
niets doet. De beurt zelf staat onder Bespaard (`kind` is `boiler`), gemeten
tegen wat hij gekost had als hij meteen was gaan verwarmen toen er warm water
bij moest.

**Gaat de coach weg, dan gaat de stroom erop.** `async_stop` zet elke gestuurde
boiler aan. Een auto die blijft staan is een ongemak, een koud vat merk je
onder de douche, en zonder coach hoort de thermostaat gewoon weer de baas te
zijn. Hetzelfde geldt als het schema uitstaat (`schema-uit`).

Vier scenario's in het virtuele huis: `boiler-leert` (de coach kent hem nog
niet), `boiler-nacht` (de goedkope nacht en warm om 07:00), `boiler-zon` (op
eigen zon) en `boiler-stekker-stuk`. Proef 73, 74 in test_coach.py en de
boilerproeven in test_planner.py. **Nog nooit aan een echte boiler gehangen**,
dus wat er in het echt anders kan zijn: hoe snel een meetstekker zijn vermogen
meldt, hoeveel speling de thermostaat heeft, en of een boiler bovenin
terugregelt in plaats van hard af te slaan.
