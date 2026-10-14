# De airco

Sinds v0.119.0 stuurt de coach ook een airco. Komt er bij een uitgave iets bij
over dit onderwerp, schrijf het dan hier. De eisen van de eigenaar en de
werkafspraken staan in `CLAUDE.md` en gaan boven alles hier.

De eigenaar op 14-10-2026, eerst: "de coach mag nooit temperatuur regelen. de
coach moet gewoon de airco aan en uit kunnen zetten." En daarna, preciezer: "hij
moet de airco aan zetten als er overschot is en als de temperatuur nog niet
bereikt is. Hij mag trouwens wel de temperatuur instellen en de modus wijzigen
van verwarmen en koelen. De klant stelt gewoon op de kaart in welke temperatuur
het moet zijn en kan instellen alleen op zon aan zetten." Daarbij koos hij: de
goedkoopste uren zijn elk uur onder het gemiddelde van die dag, en zet de bewoner
hem zelf aan of uit, dan blijft de coach er de rest van de dag vanaf. Zonder
vermogenssensor geldt het vermogen van het typeplaatje.

**De coach verzint geen temperatuur.** Hij zet de temperatuur die de bewoner
koos op de airco, kiest verwarmen of koelen, en zet hem aan of uit. Hij schuift
niet met het doel, en ventilator, swing en lamellen raakt hij nooit aan. Hoe hard
de airco draait en wanneer hij op temperatuur stilvalt, is aan de airco zelf;
dezelfde afspraak als bij de boiler (`docs/boiler.md`). Een eerder voorstel van
13-10-2026, het doel binnen een band verschuiven om zon in de kamer te stoppen
of dure uren te ontwijken, is daarmee van tafel.

## Velden

Van de installateur, onder Apparaten (`AIRCO_FIELDS` in devices.js, `_AIRCO` in
websocket.py):

- **Airco**: de climate-entiteit, verplicht. De kiezer toont alles met
  `hvac_modes` (`climate` in entity-picker.js).
- **Kamertemperatuur**: een eigen sensor, optioneel. Leeg is de
  `current_temperature` van de airco.
- **Vermogenssensor** (het gewone veld van elk apparaat) en/of **het vermogen
  van het typeplaatje** (`airco.power_w`). Een van de twee is nodig
  (`missingForControl`).

Van de bewoner, in Instellen achter de kaart (`airco()` in voorkeur-velden.js,
`VOORKEUREN_AIRCO` in storage.py): de gewenste temperatuur (`target_c`, leeg is
wat er op de airco staat), alleen op zon (`solar_only`) en de pauze (`paused`).
Een airco heeft geen schema en geen klaar-tijd.

## Wanneer aan, wanneer uit

Het denkwerk staat in `plan_airco` in planner.py; wat er gebeurde (wie hem
aanzette, wat de bewoner deed, de opdrachten) in `_one_airco` in coach.py.

- **Nodig** (`airco_nodig`): kouder dan gewenst is verwarmen, warmer is koelen,
  pas buiten een marge van één stap van de airco zelf (`target_temp_step`, en
  zonder die de halve graad die Home Assistant voor een thermostaat in graden
  neemt, `AIRCO_STAP_C`). Een airco die niet kan verwarmen wordt niet aangezet
  om te verwarmen. Loopt hij al, dan geldt zijn eigen stand en wisselt de coach
  nooit tussen verwarmen en koelen.
- **Zon**: wat er naar het net zou gaan als deze airco uit stond, minstens zijn
  vermogen. Valkuil 2 van de boiler: zonder die correctie eet hij zijn eigen
  overschot op en zet hij zichzelf uit. De meter telt pas na acht minuten
  (`METER_DEKKING`) en neemt het minste van tien minuten (`_meter_zeker`), dus
  hij gaat aan op zon die blijft.
- **Goedkoop** (`airco_goedkoop`): het uur van nu ligt onder het gemiddelde van
  alle uren van vandaag in de prijslijst. Alleen bij een dynamisch contract: een
  vast contract heeft geen prijslijst, en een dag waarop elk uur even duur is
  heeft geen uur onder het gemiddelde. "Alleen op zon" zet dit uit.
- **Uit** zet de coach alleen wat hij zelf aanzette: als de zon op is of het
  goedkope uur voorbij, maar niet binnen tien minuten na het aanzetten
  (`MIN_RUN_MINUTES`, dezelfde als de paal bij een wolk). Op temperatuur doet de
  airco zelf niets meer; daar schakelt de coach niet voor.

Aanzetten is één opdracht, `climate.set_temperature` met `hvac_mode` erin, want
een airco in de cloud doet over elke opdracht een minuut. Uit is
`climate.set_hvac_mode` naar `off`. Past het vermogen niet onder de zekering na
wie hoger staat in de voorrang, dan wacht hij (`no-room`), net als de boiler.

**Zon delen.** Een airco staat niet in de voorrang bij zon (`zon_regels`), en
wijkt dus voor de paal en de boiler die er wel in staan: zij zien zijn verbruik
als zon die vrij is (`_zon_correctie`, met het typeplaatje als er geen sensor is,
`_airco_neemt_w`). De batterij wijkt wel voor de airco, zoals voor de boiler.

## De bewoner wint

Zet de bewoner de airco zelf aan, uit of op een andere stand (afstandsbediening,
app, de kaart), dan blijft de coach er tot middernacht vanaf (`bewoner_tot`,
stand `bewoner`). Een airco die aan staat en die de coach niet aanzette, laat hij
ook met rust. Een andere temperatuur op de afstandsbediening is geen schakelen
maar de nieuwe wens: die gaat in `target_c`.

Om de coach zelf niet voor de bewoner aan te zien, onthoudt hij wat hij vroeg
(`verwacht`, `temp_verwacht`). Ziet hij dat terug, dan is dat de nieuwe maat.
Ziet hij het na `AIRCO_VOLGT` (vijf minuten) nog niet, dan ging de opdracht niet
door, en blijft de maat wat er daarvoor stond. Een cloud wordt eens per minuut
gelezen; in de klantwoning op 13-10-2026 gemeten. Zolang een opdracht onderweg
is, stuurt hij hem niet nog eens.

**Twee fouten die proef 156 eruit haalde**, allebei voor de uitgave: de eigen
opdracht van de coach telde in de ronde erna als iets van de bewoner (de
vergelijking keek naar de stand van vóór de opdracht), en zolang de cloud de
opdracht nog niet liet zien stuurde hij hem elke minuut opnieuw.

## Het vermogen

Het typeplaatje gaat voor. Zonder typeplaatje telt het meeste dat de
vermogenssensor zag terwijl de airco draaide (`gemeten_w`), want een airco
begint hard en regelt terug als hij bijna op temperatuur is. Tot hij een keer
gedraaid heeft weet de coach dan niet wanneer er genoeg zon is, en zegt hij dat
(`geen-vermogen`). Het virtuele huis vond dat gat: met alleen een sensor ging hij
nooit aan op zon.

## Pauze, herstart, en de coach die weggaat

Pauze: de coach zet uit wat hij zelf aanzette, en doet verder niets. Na een
herstart weet hij nog dat hij hem aanzette, tot wanneer de bewoner wint en wat
hij mat (`airco_on`, `resident_until`, `airco_w` in `sessions`, via
`_remember`); anders zou een airco die hij op zon aanzette voor altijd van de
bewoner lijken. Gaat de coach weg, dan blijft de airco zoals hij is.

## Het contract met de airco-kaart van DomotiApp Lovelace

Afgesproken met de lovelace-sessie op 14-10-2026; contract blijft 1, er kwam
alleen iets bij (model "Airco" in `MODELLEN`).

- sensor `coach` (`AircoCoachSensor`): toestand de stand in woorden;
  attributen `contract`, `type` "airco", `stand` (zon, goedkoop, op_temperatuur,
  uit, bewoner, pauze, geen_meting), `modus` ("heat" of "cool": wat de coach
  koos of zou kiezen), `reason` (tekst), `klimaat` (de entity_id van de climate:
  zo vindt de kaart de coach bij een airco), `ruimte`, `kamer`, `doel`,
  `alleen_zon`, `pauze`, `dynamisch` (bij false verbergt de kaart "alleen op
  zon"), `bewoner_tot`, `entiteiten`.
- number `doeltemperatuur` (`DoeltemperatuurNumber`): de wens van de bewoner,
  met min, max en stap van de airco zelf (anders 7, 35 en 0,5: de standaard van
  Home Assistant). Vóór de eerste keuze wat er op de airco staat. De kaart
  schrijft hierheen en niet naar de climate: één schrijver, de coach, en meteen
  (`async_airco_doel`) als de airco aan staat.
- switch `alleen_zon` en switch `pauze` (`AircoSchakelaar`).

Aan, uit en de stand stuurt de kaart gewoon naar de climate; voor de coach is dat
de bewoner.

## Proeven

- test_planner.py proef 75: aan op zon en op een goedkoop uur, de marge, nooit
  wisselen, de wolk, alleen wat de coach aanzette uit, zonder meting niets.
- test_coach.py proef 156: de opdrachten, de wolk, de cloud die een minuut doet,
  de bewoner tot middernacht, de temperatuur van de afstandsbediening, de number
  die meteen doorschrijft, de pauze, de entiteiten, wat de bewoner mag zetten, en
  een herstart.
- test_rapport.mjs: de velden, wat er nog mist, Instellen.
- Het virtuele huis (`Airco` in virtueel.py): `airco-zon` en `airco-plaatje`
  (koelen op eigen zon, met en zonder vermogenssensor), `airco-bewoner` (om 13:30
  zelf uit, daarna niets meer), `airco-goedkoop` (verwarmen op de uren onder het
  daggemiddelde, en niet in de avondpiek).

## Niet gebouwd

- Een airco in de voorrang bij zon en bij planningen; nu wijkt hij voor iedereen
  die erin staat.
- Beurten en Bespaard voor een airco.
- Een airco die alleen met `target_temp_high` en `target_temp_low` werkt
  (`heat_cool`); de coach zet alleen `temperature`.
- Twee airco's in één ruimte gelijk laten lopen; elk volgt zijn eigen wens.
- Nog niet beproefd tegen een echte airco: alles hierboven is nagebouwd.
