# De smart plug (v0.120.0)

De eigenaar op 15-10-2026: "Heel veel mensen hebben smart plugs om het vermogen te meten
van een apparaat. Ik wil bij apparaten toevoegen dan de optie smart plug. En dan als ik
die heb gekozen een hele lijst met apparaten zoals wasmachine, oven vriezer etc etc.
Allemaal met de naam en icon. Dan de optie energieteller, vermogensteller en een
belangrijke optie, dit apparaat moet altijd aan staan. Als die aan staat moet de coach
dat blijven controleren en als die door wat voor een reden dan uit gegaan is moet de
coach hem weer aan zetten. Lukt dat niet wil ik na 2 min een melding ontvangen. Pas de
melding sturen als je dat hebt ingesteld in meldingen."

## Wat het is

Een type in Apparaten (`smartplug`), naast Overig. In deze volgorde, zoals hij het
opsomde (`plugHtml_` in views/devices.js):

1. **Apparaat**: wat eraan hangt, uit een lijst van 23 met elk een eigen icoon, op naam,
   met "Iets anders" onderaan (`PLUG_APPLIANCES` in devices.js). Dat geeft hem zijn
   naam en zijn icoon, in de lijst, op het overzicht en in de energiestroom
   (`kindLabel`, `deviceIcon`). Een eigen naam wint, zoals bij elk apparaat.
2. **Schakelaar**: de schakelaar van de stekker zelf (`entities.switch`).
3. **Vermogenssensor** en **Energieteller**: dezelfde velden als elk apparaat
   (`entity`, `energy_entity`).
4. **Dit apparaat moet altijd aan staan** (`always_on`).

Daaronder het gewone vinkje "De coach mag dit apparaat noemen", zoals bij Overig: met
dat vinkje staat hij in de tip bij overschot ("Zet de wasmachine aan."). Een smart plug
telt daarvoor bewust niet als stuurbaar (`canSteer`); de schakelaar is daarom een eigen
veld (`PLUG_SWITCH_FIELD`) en geen veld van het type zoals bij de boiler.

De coach plant en stuurt een smart plug niet. Een vaatwasser die hij moet plannen hoort
onder het type Vaatwasser; dat zegt het scherm als je Vaatwasser kiest.

Op de kaart en in de pop-up van de energiestroom staat "Stekker: Aan" of "Uit"
(`deviceDetails` in data-source.js).

## Altijd aan

`_async_altijd_aan` in coach.py, elke ronde:

- Staat de schakelaar uit, dan zet de coach hem aan, en elke ronde opnieuw zolang dat
  niet lukt. De schakelaar wekt de coach zelf (`_watch`), dus dat is binnen een seconde.
- Staat hij na `ALTIJD_AAN_WACHT` (2 minuten) nog niet aan, dan één melding, als
  kritiek. Een klok (`async_call_later`) kijkt precies na die twee minuten, anders werd
  het met de ronde van eens per minuut bijna drie.
  - "De vriezer staat al 2 minuten uit en de coach krijgt hem niet aan."
  - "De vriezer is al 2 minuten niet bereikbaar; de coach weet niet of hij aan staat."
    voor een stekker die niets zegt: die is van het netwerk af en valt niet aan te zetten.
  - "De vriezer staat al 2 minuten uit." bij Alleen uitlezen en Adviseren: daar raakt de
    coach niets aan, net als bij de ventilator van de batterij, maar de melding komt wel.
- Naar de telefoon alleen als **Apparaat staat uit** aan staat in Meldingen
  (`always_on_alert`, standaard uit); in de geschiedenis altijd.
- Krijgt de coach hem weer aan, of gaat hij na een melding weer aan, dan staat dat alleen
  in de geschiedenis ("De vriezer stond uit; de coach heeft hem weer aangezet.", "De
  vriezer staat weer aan.").

Het lidwoord ("De vriezer", "Het aquarium") staat in `STEKKER_APPARATEN` in const.py;
dezelfde lijst als in het paneel, test_rapport.mjs legt ze naast elkaar.

Met de melding aan valt het vermogen van zo'n stekker buiten de sensorwacht
(`_sensoren`): anders kwam er na tien minuten nog een bericht over dezelfde stekker die
van het netwerk is. Met de melding uit blijft de sensorwacht hem zeggen zolang de stekker
zelf bereikbaar is; sinds v0.178.0 niet als de stekker zelf weg is, want dan staat hij al
in de geschiedenis.

## Eén melding voor stekkers die samen wegvallen (v0.178.0)

In een klantwoning zette beheer op 29-10-2026 vijf nieuwe stekkers in de coach, met altijd
aan. Ze zaten nog niet in het stopcontact. Twee minuten later kwamen er vijf kritieke
meldingen in dezelfde seconde, een per stekker. Acht minuten later kwam er een zesde van de
sensorwacht over hun vermogen: "Waarschijnlijk is het internet thuis weg." Het internet was
er gewoon.

- **Eén melding** (`_async_stekkers_melden`). Gaat een stekker over `ALTIJD_AAN_WACHT`, dan
  neemt de melding elke stekker mee die al `ALTIJD_AAN_BUNDEL` (een minuut) weg is. De coach
  zet een stekker binnen een seconde aan, dus na een minuut weet hij dat het niet lukte.
  - Per soort is er een zin: niet bereikbaar, uit en niet aan te krijgen, of uit.
  - Het getal is dat van de stekker die over de wachttijd ging.
  - Een eigen naam blijft zoals hij is, en verderop in de zin wordt "De vaatwasser" "de
    vaatwasser". Bijvoorbeeld: "Oven, Warmhoudlade, Quooker, Ledstrips en de vaatwasser zijn
    al 2 minuten niet bereikbaar; de coach weet niet of ze aan staan."
  - Eén stekker geeft de zin van voorheen.
- **Een stekker die nog nooit bereikbaar was** krijgt een gewone melding, geen kritiek: "...
  zijn nog niet bereikbaar. Zodra ze er zijn, houdt de coach ze aan."
  - De eigenaar koos op 29-10-2026 "ja b", want het gebeurt bij elke nieuwe stekker en de
    bewoner kan er niets aan doen.
  - Komt hij er, dan staat "... is nu bereikbaar." in de geschiedenis, en houdt de coach
    hem aan.
  - Valt hij daarna weg, dan is dat wel kritiek.
  - "Bereikbaar" is: de coach zag hem ooit aan of uit (`_stekker_ooit`).
  - Een stekker die al weg was toen v0.178.0 kwam, telt ook als nieuw. Hij krijgt dus een
    gewone melding en geen kritiek.
- **Een herstart** maakt niets dubbel. In `GeheugenStore` (`meldingen`) staan:
  - wat gemeld is (sinds v0.173.0);
  - sinds wanneer elke stekker weg is;
  - welke ooit bereikbaar waren;
  - welke de gewone melding al kregen.

## Ook een vaatwasser (v0.122.0)

De eigenaar op 15-10-2026: "bij het apparaat vaatwasser ook de optie kunnen aanzetten dat
hij nooit uit mag sommige vaatwassers hangen namelijk ook aan een smart plug om alles te
meten." Een vaatwasser krijgt, zodra er een merk gekozen is, onder de programmatabel het
blok Stekker: het veld "Smart plug (optioneel)" (ook in `entities.switch`) en hetzelfde
vinkje.
Welke types het kunnen staat twee keer, `ALTIJD_AAN_TYPES` in coach.py en
`ALWAYS_ON_TYPES` in devices.js; proef 158 legt ze naast elkaar.

Dit bijt de vrijgave niet: een vrijgaveschakelaar die de stekker zelf is gebruikt de
coach al sinds v0.101.11 niet (`_vrijgave_entiteit`), dus de planning van de vaatwasser
zet de stekker nooit uit; proef 158 draait daarvoor een volle ronde. In de sensor van de
vaatwasser voor DomotiApp Lovelace staat de stekker erbij in `entiteiten` als `switch`;
dat is iets toevoegen, het contract blijft 1.

Sinds v0.177.0 heet het veld `plugFieldFor(type)` en het blok `appliancePlugHtml_`, want het
staat niet meer alleen bij de vaatwasser.

## Ook een vriezer, koelkast, wasmachine en droger (v0.177.0)

De eigenaar op 29-10-2026, over een klantwoning waar de Miele-vriezer, -koelkast, -wasmachine
en -droger elk aan een eigen stekker hangen: "De miele apparaten zitten op een smart plug die
altijd aan moet staan. De energy etc wil ik van de smart plug meten maar ik wil ook de
deurstatus etc blijven behouden."

Dus één apparaat, geen losse smart plug ernaast:

- **Het blok Stekker** krijgen nu ook deze vier, net als de vaatwasser: "Smart plug
  (optioneel)" in `entities.switch` en het vinkje altijd aan. `ALTIJD_AAN_TYPES` en
  `ALWAYS_ON_TYPES` zijn uitgebreid. De velden van het merk (de deur, het programma, de
  temperatuur, de storing) blijven waar ze waren.
- **De coach zet zo'n stekker alleen aan, nooit uit.** Alleen `_async_altijd_aan` raakt
  `entities.switch` van deze types aan. Een vriezer stuurt de coach verder niet; de stekker
  aanhouden is geen sturen, dus dat doet hij ook bij een merk dat hij alleen uitleest.
- **Meten met de stekker** gaat met de gewone velden: het vermogen in Vermogenssensor, de
  teller in Energieteller. Bij een Miele-wasmachine of -droger telt de coach een programma
  dan uit het vermogen per ronde (`_programma_tellen`), net als bij een machine van Overig,
  en niet meer uit de teller van Miele. Daarmee komen ook de piek en het verloop van een
  programma erbij. Wat hij eerder met de teller van Miele mat blijft staan. Elke nieuwe beurt
  past de meting aan. Zonder vermogenssensor blijft de energieteller de bron.
- **Een teller die alles telt.** De teller van Miele begint bij elk programma op nul, en de
  coach telde een teller die terugvalt daarom als een nieuw begin: de nieuwe stand was de
  stap. De teller van een stekker telt alles wat er ooit doorging. Zakt die een tikje, dan
  telde zijn hele stand als één stap: in proef 218 werd dat 514,3 kWh voor één wasbeurt van
  1,7. Sinds v0.177.0 is een val tot hooguit de helft een hapering, en dan wacht de coach tot
  de teller weer boven de vorige stand komt (`_teller_tellen`). Een val dieper dan de helft
  blijft een nieuw programma, en dat dekt de nul van Miele.
- De hint bij Energieteller zegt het: de sensor van de machine of de teller van de stekker.
  Met een vermogenssensor erbij staat er "(optioneel)".

In de sensor voor DomotiApp Lovelace staat de stekker in `entiteiten` als `switch`, en de
stekker als `power` en `energy`. Dat is iets toevoegen; het contract blijft 1.

## Proeven

Proef 157, 158, 218 en 219 in test_coach.py (de bewaking, de meldingen, de niveaus, de sensorwacht, een
volle ronde, de vaatwasser; de vriezer, de wasmachine op het vermogen van de stekker en de teller die
zakt; vijf stekkers in één melding, een herstart halverwege, nieuwe stekkers en het internet), en zeven proeven "smart plug" in test_rapport.mjs (de lijst tegen const.py, naam en icoon, de
kaart, Apparaten en Meldingen, het blok Stekker bij alle vijf de types).

## Nog niet in het echt gezien

Thuis of bij een klant: een echte stekker uitzetten en kijken of hij binnen een seconde
weer aan gaat, en een stekker uit het stopcontact trekken voor de melding "niet
bereikbaar".
