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
van het netwerk is. Met de melding uit blijft de sensorwacht hem zeggen, zoals voor elk
apparaat.

Na een herstart van Home Assistant weet de coach niet meer dat hij al gemeld had; staat
de stekker dan nog uit, dan komt er na twee minuten één nieuwe melding.

## Ook een vaatwasser (v0.122.0)

De eigenaar op 15-10-2026: "bij het apparaat vaatwasser ook de optie kunnen aanzetten dat
hij nooit uit mag sommige vaatwassers hangen namelijk ook aan een smart plug om alles te
meten." Een vaatwasser krijgt, zodra er een merk gekozen is, onder de programmatabel het
blok Stekker: het veld "Smart plug (optioneel)" (`DISHWASHER_PLUG_FIELD`, ook in
`entities.switch`) en hetzelfde vinkje (`dishwasherPlugHtml_` in views/devices.js).
Welke types het kunnen staat twee keer, `ALTIJD_AAN_TYPES` in coach.py en
`ALWAYS_ON_TYPES` in devices.js; proef 158 legt ze naast elkaar.

Dit bijt de vrijgave niet: een vrijgaveschakelaar die de stekker zelf is gebruikt de
coach al sinds v0.101.11 niet (`_vrijgave_entiteit`), dus de planning van de vaatwasser
zet de stekker nooit uit; proef 158 draait daarvoor een volle ronde. In de sensor van de
vaatwasser voor DomotiApp Lovelace staat de stekker erbij in `entiteiten` als `switch`;
dat is iets toevoegen, het contract blijft 1.

## Proeven

Proef 157 en 158 in test_coach.py (de bewaking, de meldingen, de niveaus, de sensorwacht, een
volle ronde, de vaatwasser), en zes proeven "smart plug" in test_rapport.mjs (de lijst tegen const.py,
naam en icoon, de kaart, Apparaten en Meldingen).

## Nog niet in het echt gezien

Thuis of bij een klant: een echte stekker uitzetten en kijken of hij binnen een seconde
weer aan gaat, en een stekker uit het stopcontact trekken voor de melding "niet
bereikbaar".
