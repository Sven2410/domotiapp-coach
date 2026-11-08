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

**Geen thermostaat** (v0.119.1). v0.119.0 zette hem standaard ook aan op een
goedkoop uur, en de eigenaar zei die avond: "de airco moet alleen bijverwarmen
of koelen bij overschot he! niet gewoon aan om de temperatuur te regelen", en
meteen daarna: "goedkoop uur mag de bewoner zelf kiezen dus 3 opties of op zon
of goedkope uren of beide." Dus een keuze `run_on` (`AIRCO_AAN_OP` in
planner.py): zon (de standaard), goedkoop of beide. Zonder zon over gaat hij
standaard nooit aan, hoe koud of warm het ook is; het scenario `airco-geen-zon`
laat dat zien. En: "Bij apparaten toevoegen alleen nog de optie Mitsubishi
Electric kunnen kiezen." Een airco heeft sinds v0.119.1 een merk (`AIRCO_BRANDS` in
devices.js); zonder merk geen velden en geen sturing.

**Fujitsu (Atlantic Cozytouch)** kwam erbij in v0.205.0. Een bewoner met twee
Fujitsu-airco's had Mitsubishi Electric gekozen, want dat had dezelfde velden: "Maar
voor de netheid mag die er wel aan toegevoegd worden." Zelfde velden, een eigen
uitleg, en de kamertemperatuur verplicht. Wat er anders is aan die integratie, de
stand alleen via `set_hvac_mode`, geldt sindsdien voor elk merk (Een airco die niet
luistert, hieronder).

**De coach verzint geen temperatuur.** Hij zet de temperatuur die de bewoner
koos op de airco, kiest verwarmen of koelen, en zet hem aan of uit. Hij schuift
niet met het doel, en ventilator, swing en lamellen raakt hij nooit aan. Hoe hard
de airco draait en wanneer hij op temperatuur stilvalt, is aan de airco zelf;
dezelfde afspraak als bij de boiler (`docs/boiler.md`). Een eerder voorstel van
13-10-2026, het doel binnen een band verschuiven om zon in de kamer te stoppen
of dure uren te ontwijken, is daarmee van tafel.

## Velden

Van de installateur, onder Apparaten (`AIRCO_BRANDS` en `AIRCO_FIELDS` in
devices.js, `_AIRCO` in websocket.py), na het merk Mitsubishi Electric of, sinds
v0.205.0, Fujitsu (Atlantic Cozytouch):

- **Airco**: de climate-entiteit, verplicht. De kiezer toont alles met
  `hvac_modes` (`climate` in entity-picker.js).
- **Kamertemperatuur**: een eigen sensor, optioneel. Leeg is de
  `current_temperature` van de airco. Bij Fujitsu verplicht: Atlantic Cozytouch
  geeft `current_temperature` niet door (in een klantwoning op 07-11-2026 leeg),
  en zonder kamertemperatuur doet de coach niets.
- **Vermogenssensor** (het gewone veld van elk apparaat) en/of **het vermogen
  van het typeplaatje** (`airco.power_w`). Een van de twee is nodig
  (`missingForControl`).

Van de bewoner, in Instellen achter de kaart (`airco()` in voorkeur-velden.js,
`VOORKEUREN_AIRCO` in storage.py): de gewenste temperatuur (`target_c`, leeg is
wat er op de airco staat), waarop hij aan mag (`run_on`: zon, goedkoop of beide,
standaard zon) en de pauze (`paused`). Een airco heeft geen schema en geen
klaar-tijd.

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
- **Goedkoop** (`airco_goedkoop`), alleen als de bewoner goedkoop of beide koos:
  het uur van nu ligt onder het gemiddelde van alle uren van vandaag in de
  prijslijst. Alleen bij een dynamisch contract: een vast contract heeft geen
  prijslijst, en een dag waarop elk uur even duur is heeft geen uur onder het
  gemiddelde. Koos de bewoner goedkoop bij een vast contract, dan zegt de reden
  dat hij beter zon of beide kan kiezen.
- **Uit** zet de coach alleen wat hij zelf aanzette: als de zon op is of het
  goedkope uur voorbij, maar niet binnen tien minuten na het aanzetten
  (`MIN_RUN_MINUTES`, dezelfde als de paal bij een wolk). Op temperatuur doet de
  airco zelf niets meer; daar schakelt de coach niet voor.

Aanzetten is sinds v0.205.0 twee opdrachten: eerst `climate.set_hvac_mode` met
de stand, dan `climate.set_temperature` zonder stand (zie hieronder, Een airco
die niet luistert). Uit is `climate.set_hvac_mode` naar `off`. Past het vermogen niet onder de zekering na
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

## Een airco die niet luistert (v0.205.0)

In een klantwoning op 06-11-2026 zei de kaart om 23:47 "Hij gaat verwarmen naar
20 °C; het is nu 18,2 °C", en de airco bleef de hele nacht uit. De bewoner: "Zegt
dat ie gaat verwarmen, maar doet uiteindelijk niks." Tot dan zette de coach een
airco aan met één opdracht, `set_temperature` met `hvac_mode` erin. Home Assistant
geeft die stand alleen als argument door aan de integratie, en de integratie daar
(Atlantic Cozytouch) leest hem niet: de temperatuur ging naar een airco die uit
stond, zonder fout, en het besluit zei `applied`. Na `AIRCO_VOLGT` stuurde de coach
dezelfde opdracht opnieuw, elke vijf minuten, en niemand hoorde het. MELCloud leest
de stand wel, daarom kwam het niet eerder boven.

- **Eerst de stand, dan de temperatuur** (`_async_airco_zetten`). De stand gaat bij
  elke integratie via `set_hvac_mode`. Bij een cloudkoppeling kost dat een
  opdracht meer, en dat is beter dan een airco die niet aangaat.
- **De kaart zegt "De coach zet hem aan om te verwarmen naar 20 °C"** en niet meer
  "Hij gaat verwarmen" (`plan_airco`): dat klopt pas als hij aan is.
- **Na twee pogingen die niet aankwamen** (`AIRCO_MISLUKT`, alleen aanzetten; uit
  laat de coach los) één kritieke melding: "{naam} reageert niet op de coach. Kijk
  of de integratie werkt." Het besluit is dan niet meer `applied`, de stand is
  `uit` met regel `geen-gehoor`, en hij probeert het een half uur na de laatste
  poging opnieuw (`AIRCO_OPNIEUW`) in plaats van elke vijf minuten. Komt een poging
  wel aan, dan staat "{naam} reageert weer op de coach." in de geschiedenis, niet op
  de telefoon.
- De telling, de laatste poging en of het gemeld is overleven een herstart
  (`airco_miss`, `airco_try`, `airco_miss_told` in `sessions`). Een poging die een
  herstart onderbrak telt niet; de coach stuurt hem dan opnieuw.

Het scenario `airco-cozytouch` in het virtuele huis is `airco-goedkoop` met een
airco die de stand in `set_temperature` negeert: hij verwarmt net zo. Proef 246 in
test_coach.py doet de rest.

## Wat de kamer doet: leren (v0.207.0)

Een bewoner op 07-11-2026: "Hoe snel koelt een woning af bij een bepaalde
buitentemperatuur, en hoe snel warmt een woning weer op om op een gewenste
temperatuur te komen. Dit gekoppeld aan de verbruikte energie. Op die manier kan
coach super goed plannen wanneer hij het beste kan gaan verwarmen, hoeveel kWh aan
energie in de woning moet, en wat dit gaat kosten." Dit is **stap 1: alleen leren
en laten zien**. De coach stuurt er niets anders door. Stap 2, plannen met "warm
om", komt pas als er een paar weken echte getallen zijn.

Het rekenwerk staat in `kamer.py` (kent Home Assistant niet), de metingen en de
opslag in `_async_airco_leren` in coach.py. Hij leert bij elke airco met een
climate, ook een die hij niet mag sturen.

- **Het verlies** `k`: °C per uur per °C verschil met buiten. Zonder airco zakt een
  kamer naar buiten toe, `dT/dt = -k (binnen - buiten)`. Uit vensters van twee uur
  (`VERLIES_DUUR`), en alleen als:
  - de zon onder is (geen zon op het raam; uit de plek van Home Assistant, anders
    `sun.sun`);
  - de airco al een uur uit staat (`NA_UIT`) en minder dan 30 W trekt;
  - binnen en buiten minstens drie graden verschillen (`MIN_VERSCHIL_C`);
  - er geen sprong in zit van meer dan een halve graad tussen twee metingen (een raam,
    `SPRONG_C`) en geen gat van meer dan vijf minuten (`GAT`).
- **De winst**: °C per kWh, per stand (`heat`, `cool`). Uit vensters van een uur
  (`WINST_DUUR`) waarin hij in die stand stond. Wat de airco deed is wat de kamer
  deed plus wat hij in die tijd verloor: `(eind - begin) + k * gemiddeld verschil *
  uren`, gedeeld door de kWh van de vermogenssensor. Op temperatuur klopt dat ook:
  dan houdt hij precies het verlies bij. Pas als het verlies vijf keer gemeten is,
  en alleen met een vermogenssensor.
- **Een lopend gemiddelde** (`leer_erbij`), waarin een nieuw venster nooit minder dan
  1 op 20 weegt (`GEWICHT`): een kamer die anders wordt (een ander seizoen, een
  nieuw raam) leert hij bij. Wat geen kamer is (`k` boven 0,5, of meer dan 20 °C per
  kWh) telt niet.
- **De buitentemperatuur**: een eigen sensor bij de airco (het veld
  Buitentemperatuur, `outdoor` in `entities`), anders de `temperature` van de eerste
  weerentiteit in Home Assistant (in Fahrenheit omgerekend). De werkbon vroeg een
  veld in Installatie; het werd een veld bij de airco, naast zijn kamersensor. Het
  is optioneel, en het weer van Home Assistant is er bijna altijd.

**Wat een herstart overleeft**: het geleerde staat in de instellingen
(`airco_learned`: `k`, `heat`, `cool`, elk met `_n`), weggeschreven zodra er een
venster af is. Het lopende venster en sinds wanneer hij uit staat staan in het
geheugen (`airco-leren:<id>`, `docs/herstart.md`), zodat een venster dwars door een
herstart loopt. "Vergeet wat er gemeten is" bij het apparaat wist het ook.

**Op de kaart** (`aircoRegels` in airco.js), pas vanaf vijf vensters
(`GENOEG`); daarvoor "nog aan het leren (2 van 5 metingen)". Nooit een getal dat
hij niet mat:

- Zonder airco: "zakt ongeveer 0,7 °C per uur, bij 20,0 °C binnen en 6,0 °C buiten"
  (in de zomer "stijgt").
- Verwarmen of Koelen: "1 °C kost ongeveer 0,40 kWh", alleen voor een stand waarin
  hij gemeten heeft.

Voor de airco-kaart van DomotiApp Lovelace kwamen er vier attributen bij op de
sensor `coach` (contract blijft 1): `verlies_per_graad`, `kwh_per_graad_verwarmen`,
`kwh_per_graad_koelen` (allebei None tot vijf vensters) en `buiten`.

Het scenario `airco-leren` in het virtuele huis is acht koude dagen op goedkope
uren met een kamer van 0,12 per uur per graad en een airco van 2,5 graad per uur
op 1,2 kW. De coach leerde `k` 0,1198 (acht vensters) en 2,078 °C per kWh (37
vensters, nagebouwd 2,083). Daarvoor regelt de nagebouwde airco sinds v0.207.0 bij
zijn doel terug zoals een inverter; tot dan trok hij de hele stap vol en verloor hij
wat boven het doel uitkwam, en dan kwam de coach op 1,85 uit.

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
  `aan_op` (zon, goedkoop of beide), `pauze`, `dynamisch` (bij false is er geen
  goedkoper uur, en zegt de keuze weinig), `bewoner_tot`, `entiteiten`.
- number `doeltemperatuur` (`DoeltemperatuurNumber`): de wens van de bewoner,
  met min, max en stap van de airco zelf (anders 7, 35 en 0,5: de standaard van
  Home Assistant). Vóór de eerste keuze wat er op de airco staat. De kaart
  schrijft hierheen en niet naar de climate: één schrijver, de coach, en meteen
  (`async_airco_doel`) als de airco aan staat.
- select `aan_op` (`AanOpSelect`, v0.119.1): zon, goedkoop of beide.
- switch `pauze` (`AircoSchakelaar`).

**Weggehaald in v0.119.1: de switch `alleen_zon` en het attribuut `alleen_zon`**,
een uur na v0.119.0, toen er nog nergens een airco aan de coach hing. De kaart van
lovelace 0.65.0 toonde die schakelaar alleen bij `dynamisch` en met de
schakelaar erbij; zonder schakelaar laat ze hem weg. De select komt ervoor in de
plaats. Gezegd tegen de lovelace-sessie in dezelfde sessie.

Aan, uit en de stand stuurt de kaart gewoon naar de climate; voor de coach is dat
de bewoner.

## Proeven

- test_planner.py proef 75: aan op zon en op een goedkoop uur, de marge, nooit
  wisselen, de wolk, alleen wat de coach aanzette uit, zonder meting niets.
- test_coach.py proef 247 (v0.207.0): het verlies dwars door een herstart, wat
  geen venster is (overdag, het eerste uur na uit, een sprong, een gat, te weinig
  verschil, zonder buiten), verwarmen pas met een bekend verlies en een
  vermogenssensor, het lopende gemiddelde, wat de kaart en Lovelace zien, en het weer
  in Fahrenheit.
- test_coach.py proef 246 (v0.205.0): een integratie die de stand alleen via
  `set_hvac_mode` leest, twee pogingen en één melding, een half uur tussen de
  pogingen daarna, een herstart, en weer luisteren.
- test_coach.py proef 156: de opdrachten, de wolk, de cloud die een minuut doet,
  de bewoner tot middernacht, de temperatuur van de afstandsbediening, de number
  die meteen doorschrijft, de pauze, de entiteiten, wat de bewoner mag zetten, en
  een herstart.
- test_rapport.mjs: de velden, wat er nog mist, Instellen.
- Het virtuele huis (`Airco` in virtueel.py): `airco-zon` en `airco-plaatje`
  (koelen op eigen zon, met en zonder vermogenssensor), `airco-bewoner` (om 13:30
  zelf uit, daarna niets meer), `airco-goedkoop` (de bewoner koos goedkope uren:
  verwarmen op de uren onder het daggemiddelde, en niet in de avondpiek) en
  `airco-geen-zon` (dezelfde koude dag standaard op zon: geen enkele opdracht).

## Niet gebouwd

- Stap 2 van het leren (v0.207.0): een tijd "warm om" per airco, achteruit rekenen
  wat het huis tot dan verliest en de kWh op de goedkoopste uren leggen. Pas als
  stap 1 een paar weken echte getallen heeft.

- Een airco in de voorrang bij zon en bij planningen; nu wijkt hij voor iedereen
  die erin staat.
- Sessies en Bespaard voor een airco.
- Een airco die alleen met `target_temp_high` en `target_temp_low` werkt
  (`heat_cool`); de coach zet alleen `temperature`.
- Twee airco's in één ruimte gelijk laten lopen; elk volgt zijn eigen wens.
- Nog niet beproefd tegen een echte airco: alles hierboven is nagebouwd. Atlantic
  Cozytouch is bekeken in de bron (1.4.0) en in de recorder van een klantwoning,
  niet met een echte opdracht van de coach.
