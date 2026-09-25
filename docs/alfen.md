# De Alfen-laadpaal

Uit `CLAUDE.md` gehaald op 24-09-2026, zodat dat bestand kort blijft. De eisen
van de eigenaar en de werkafspraken staan daar en gaan boven alles hier.
Komt er bij een uitgave iets bij over dit onderwerp, schrijf het dan hier.

Sinds 23-09-2026 (v0.83.0) is er een tweede paalmerk naast Easee, na de eigen
"ik wil alfen bouwen; check zijn integratie en kijk wat je nodig hebt net als
bij easee." En meteen erachteraan: "we hebben natuurlijk een wekstroom etc
maar ik zou niet weten wat er bij alfen moet gebeuren, dus dat moeten we
testen en checken." **Elke wijziging aan de paalsturing wordt sindsdien voor
allebei gebouwd en beproefd.**

**Wat er bij Alfen anders is**, gelezen uit de integratie `alfen_modbus`
(HACS, Modbus TCP, in de eerste woning aan een Eve Single Pro-line met
firmware 7.4) en uit hoe evcc dezelfde paal stuurt. Drie dingen, alle drie in
`CHARGER_CONTROL["alfen"]` in const.py:

1. **De limiet is een number-entiteit en er is geen woord.** De maximale
   stroomlimiet van de socket (0 tot 32 A) gaat er met `number.set_value` in
   (`_limit` in coach.py, `_stuuradres` kiest tussen het apparaat-id van
   Easee en de limiet-entiteit van Alfen). Starten en stoppen bestaan niet:
   een limiet boven de ondergrens ís de start, een 0 is de pauze (`_command`
   doet niets zonder `command_service`). De wekstroom van 16 A gaat er dus
   gewoon als getal in.
2. **De paal vergeet zijn limiet.** Alfen heeft een "Modbus slave max current
   valid time" (register 1209/1210; in de eerste woning telde de sensor
   "geldigheidsduur maximale stroom" af vanaf ongeveer 300 s); loopt die af
   zonder nieuwe waarde, dan valt de paal terug op zijn veilige stroom bij
   actieve load balancing (daar 16 A). De coach schrijft de limiet daarom
   **elke ronde opnieuw**, ook als het besluit niet verandert (`refresh` in
   de tabel, `_ververst` naast de dode band in `_one`); evcc doet hetzelfde,
   elke 25 seconden. De keerzijde: valt de coach weg met een 0 erin, dan
   laadt de auto na die tijd op de veilige stroom door. Bij Easee is dat
   precies andersom (een 0 zonder houdbaarheid blijft staan), en dat is geen
   keuze maar hoe de twee palen gebouwd zijn.
3. **Er is geen statussensor.** De coach leest "auto aangesloten", "auto
   laadt" en de modus 3-toestand uit IEC 61851 (A geen auto, B1 aangesloten
   zonder aanbod, B2 aangesloten met aanbod maar de auto neemt niets, C2 aan
   het laden, E en F niet beschikbaar of storing) en maakt daar in
   `_status_afgeleid` de woorden van die de rest van de coach al kent:
   disconnected, charging, awaiting_start, ready_to_charge. "Completed" zegt
   een Alfen nooit; een auto die `HERSTART_WACHT` lang aanbod krijgt en niets
   neemt (B2 met een limiet boven de ondergrens) wordt dat, want dat is wat
   "klaar" bij een Easee ook betekent.

De velden staan in `CHARGER_BRANDS` in devices.js (`limit`, `connected`,
`charging`, `mode3`, `max_limit`, `dynamic_limit` als de teruggelezen
"maximale stroom", `current` als stroom L1); geen `device` en geen `service`,
dus geen handmatige knoppen, en `canSteer` telt hem gewoon mee. De
sensorwacht kent de kabelmelding, de laadmelding en de stroomlimiet
(`_sensoren`), en een wissel van "auto aangesloten" of "auto laadt" wekt de
coach meteen (`_watch`). `tools/toestanden.py` en `tools/live.py` kennen de
`translation_key`s van alfen_modbus.

**En de 0 blijft komen zolang er een auto hangt, ook bij "klaar".** Het
virtuele huis haalde dit er meteen uit: na "complete" schrijft de coach bij
een Easee niets meer (`_niets_schrijven`, zodat een blijvende 0 de volgende
auto niet in de weg zit), en aan een Alfen viel de paal daardoor vijf minuten
na het doel terug op 16 A. Bij een volle auto is dat onschuldig, bij een doel
van 80% laadt hij door. `_pause` schrijft bij een `refresh`-paal de 0 dus
elke ronde zolang `charger.connected`; zonder auto schrijft hij niets, en dan
is de veilige stroom precies wat de volgende auto hoort te krijgen.

Het virtuele huis kent `Paal(merk="alfen")`: een number zonder houdbaarheid,
geen startwoord, een paal die na `geldig_s` terugvalt op `veilig_amps` (geteld
in `Verloop.paal_terugvallen`, hoort nul te zijn), en de drie statussensoren.
Scenario's `alfen-vast-zonnig`, `alfen-dynamisch-zonnig` en `alfen-doel-80`:
dezelfde kilowatturen en kosten als aan een Easee, geen Easee-dienst, nooit
een gat van meer dan een minuut tussen twee schrijfopdrachten, en nooit een
terugval. Proef 90 in
test_coach.py (de wekstroom als getal, elke ronde opnieuw terwijl een Easee
de tweede ronde niets krijgt, de afgeleide status in alle vier de toestanden,
de sensorwacht), en de merkproef in test_rapport.mjs.

**Klaar blijft klaar** (v0.99.0). In de eerste woning op 25-09-2026 stopte de Tesla om
05:51:42 zelf, bij een geschatte 92 tot 95% (de accustand was ingetypt). Na een kwartier B2
noemde de coach het klaar en schreef hij 0 A; de paal ging naar B1, "wacht op start", en daarmee
was de auto voor de coach weer niet klaar. Van 06:06 tot in de ochtend: elke zestien minuten een
kwartier 13 A aanbieden en een minuut 0, en de kaart sprong mee. `_afgeleid_klaar` in coach.py
onthoudt het afgeleide "completed" tot de auto weer stroom neemt of de kabel eruit gaat; alleen
de ene herstart (`_niet_vol` in `_read`) maakt het los, en dan begint ook het kwartier
(`_stil_sinds`) en de klok van "neemt al twintig minuten niets" (`_asking_since`) opnieuw. De
schaduw liet die nacht zien dat die melding ("trek de kabel er even uit") anders onterecht was
gekomen. Klaar en de herstart gaan mee in de bewaarde beurt (`klaar`, `herstart_op`), zodat een
herstart van Home Assistant de lus niet opnieuw begint. Scenario `alfen-laadgrens-80` (de bus
stopt zelf op 80%): met v0.98.0 de hele nacht de lus en geen herstartmelding, nu een kwartier,
één herstart, het verslag, en klaar tot de ochtend, net als `laadgrens-80` aan een Easee.
Proef 90 in test_coach.py.

**Nog nooit aan een echte Alfen gestuurd.** Wat er in het echt gemeten moet
worden, in de eerste woning, met de toestanden-logger erbij (`plus=alfen`):

- Welke modus 3-toestand een gepauzeerde paal met een auto eraan meldt (B1 of
  E), en of de auto daarna weer wakker wordt van een limiet van 16 A. In de
  eerste woning stond de paal zonder auto en met 0 A op "E".
- Of de number de nieuwe waarde binnen `CONFIRM_SECONDS` terugleest, en of de
  sensor "maximale stroom" hem volgt (`dynamic_limit`).
- Hoe lang de geldigheidsduur in die paal staat. Staat hij onder twee ronden,
  dan valt de paal tussen twee ronden terug; zet hem dan op minstens 180 s.
- Of de Tesla op één of drie fasen begint en of `_fase_nu` dat uit vermogen
  en stroom L1 goed ziet.
- Wat "auto aangesloten" en "auto laadt" doen bij een auto die zelf stopt
  (laadgrens in de auto) tegenover een auto die vol is.

In de eerste woning stuurt evcc op dit moment de Alfen; nooit allebei tegelijk,
net als bij de batterij (zie `VREEMD_RONDEN`).
