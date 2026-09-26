# De vaatwasser

Uit `CLAUDE.md` gehaald op 24-09-2026, zodat dat bestand kort blijft. De eisen
van de eigenaar en de werkafspraken staan daar en gaan boven alles hier.
Komt er bij een uitgave iets bij over dit onderwerp, schrijf het dan hier.

Sinds 06-09-2026 stuurt de coach ook een vaatwasser (Home Connect), na de eigen
"omdat de bus vol zit gaan we de laadpaal even parkeren en nu verder met de
vaatwasser sturing." Eerst alleen de vaatwasser (`PROGRAMMA_TYPES` in
coach.py); de wasmachine en de droger komen erbij als dit werkt.

Een programma-apparaat start één keer en draait dan af, dus de enige vraag
is wanneer. `plan_programma` in planner.py zet elk startmoment tussen nu en
de klaar-tijd tegen elkaar (per kwartier), met de prijs per uur en wat er
dan aan eigen zon over is, en kiest het goedkoopste; de avondpiek blijft
dicht, en zonder bekende prijzen wordt er niet geraden. De duur en het
verbruik komen uit `PROGRAMMAS`, dezelfde tabel als `DISHWASHER_PROGRAMS`
in devices.js (opgaven van de fabrikant; `test_rapport.mjs` legt ze naast
elkaar). Eis 2 geldt hier als een half uur speling (`PROGRAMMA_SPELING`).

In coach.py: `_one_programma` leest status, programma en deur, drukt op de
startknop (`_async_druk`, een button-entiteit), wacht drie minuten op "run"
en zegt het als dat niet komt (starten op afstand uit, deur open), probeert
één keer opnieuw, telt kWh en kosten mee terwijl hij draait
(`_programma_tellen`, met dezelfde maat als een laadbeurt: wat meteen
starten bij het vrijgeven met alles van het net gekost had), en meldt één
keer dat hij klaar is
(`_async_programma_klaar`), schrijft de beurt in `BeurtenStore` zodat hij
onder Bespaard staat, en haalt de vrijgave eraf. Zonder vrijgave
(`ready_devices`, de knop "Ingeruimd en dicht" op de kaart) doet hij niets.

Het virtuele huis heeft een `Vaatwasser` (tests/virtueel.py) met een
verbruiksprofiel in twee bulten, "starten op afstand" dat uit kan staan, en
de gebeurtenissen `vaatwasser_vrijgeven` en `vaatwasser_deur`. Vijf
scenario's `vaatwasser-*` in scenarios.py.

**De tabel is van de klant, en de meting wint.** De eigenaar op 06-09-2026 's
avonds: "ik wil dat kunnen aanpassen, wel moet hij dit als uitgangspunt
hebben." `PROGRAMMAS` is dus alleen nog het uitgangspunt: per apparaat staat
in Apparaten een bewerkbare tabel (`device.programs`, leeg is de opgave;
`tabel_van` in planner.py), en wat de coach bij een echte beurt meet komt
eroverheen (`program_measured` in de instellingen, `_async_meting_bewaren`
in coach.py, `met_metingen` in planner.py): duur, kWh, piek en het verloop
als watt per vijf minuten (`profiel_van`). `programma_kosten` rekent met
dat profiel, zodat de opwarmpiek in het zonnigste uur valt; zonder profiel
smeert hij het verbruik uit. Lopend gemiddelde over de laatste vijf beurten
(`METING_MAX_N`); per rij te wissen in Apparaten
(`device/measurements/clear`).

**Een domme vaatwasser** (merk "overig", op een meetstekker) plant de coach
ook, maar hij drukt niet: "smart plug als starten doen we niet, wel
adviseren en meten." `Apparaat.manual` maakt de teksten "zet hem aan"; op
het moment zelf gaat er één melding naar de telefoon, en na drie kwartier
één herinnering (`HERINNERING`). Of hij draait leest de coach van het
vermogen (`_status_uit_vermogen`: boven `DRAAI_W` draait hij, na
`STIL_KLAAR` stilte is hij klaar). Het programma kiest de bewoner op de kaart
uit de eigen tabel (`device.program`, commando `device/program`); bij Home
Connect uit de select-entiteit. **De coach kiest nooit zelf een programma.**
Zes scenario's `vaatwasser-dom-*`, `vaatwasser-eigen-tabel` en
`vaatwasser-gemeten` in scenarios.py; proef 58 en 59 in test_coach.py.

**Home Connect heeft twee programma-entiteiten** (v0.55.0, na de eigen "ik heb
selected program in plaats van select"): de sensor `program` die zegt wat
erop staat, en de select `program_select` waarmee het gezet wordt. De
keuzelijst op de kaart en de namen in de tabel komen uit de opties van die
select (`programOptions`, `programRows` in devices.js); de namen zijn daar
niet te typen. Zonder select zegt de kaart wat er mist (`programPicker` geeft
`missing`). **Geen verschuifbeleid per programma meer**: de eigenaar, "elk programma
is gewoon te verschuiven; het clean programma doe je toch handmatig."
Snelladen en Pauzeren staan alleen op een laadpaal (`kind !== "programma"`).

**Een vrijgaveschakelaar** (v0.56.0, `release_switch` bij allebei de
vaatwassermerken): een switch of input_boolean die hetzelfde betekent als
"Ingeruimd en dicht", voor een eigen keukendashboard. `_async_schakelaar_volgen`
in coach.py houdt de twee gelijk: beweegt de schakelaar, dan volgt de
vrijgave; beweegt de knop op de kaart, dan volgt de schakelaar; na een beurt
gaan ze allebei uit. Uit tijdens een lopende beurt laat de beurt met rust.
Proef 60 in test_coach.py. **De schakelaar en de status van een
programma-apparaat wekken de coach meteen** (v0.56.1, `_watch`): de eigenaar zette
de schakelaar aan en binnen vijf seconden weer uit omdat er niets gebeurde,
terwijl de coach pas bij de volgende minuut keek.

**In het lopende uur wint de meter van de zonverwachting** (v0.57.0). De eigenaar
op 07-09-2026 om 10:22: de coach wachtte op 11:00 terwijl zijn meter 3,5 kW
teruglevering zag; "je weet niet hoeveel je om 11 uur terug gaat leveren."
De verwachting zei 2,2 kW, het dak gaf 4,3. `programma_kosten` rekent voor
elk stuk in het lopende uur met `surplus_w` (de netto-export van nu,
`_netto_export_w` in coach.py), net als `schijven` bij de paal; bij gelijke
kosten wint het vroegste moment, dus een meting van nu wint van een even
goede verwachting van straks. Scenario `vaatwasser-meter-wint`. En laat de
meter nu genoeg zon zien voor het hele programma, en is dat op geen later
moment goedkoper (`meter_overal` in `programma_kosten`), dan start hij nu
(v0.57.1, na 10:51 die ochtend: hij wachtte tot 12:00 omdat de verwachting
voor 11:00 net te weinig zei, terwijl de meter 3,4 kW zag). Een goedkoper
uur bij een dynamisch contract blijft winnen, want dat is een prijs en geen
gok. Niet in de avondpiek. Sinds v0.62.0 is "de meter" hier de laagste
teruglevering van de afgelopen tien minuten; zie hieronder.

**Twee meldingen per beurt**, gestart en klaar (v0.57.0, de eigenaar: "ik wil wel
meldingen ontvangen dat de vaatwasser gestart is en klaar is"). "Is gestart"
als de coach drukte of erom vroeg, "draait" als de bewoner hem zelf aanzette.

**Het vinkje bij Apparaten heet naar wat de coach kan** (v0.57.0, de eigenaar: "er
is een verschil tussen aansturen en adviseren"): "aansturen" bij een merk met
knoppen (`canSteer` in devices.js), "adviseren" bij een programma-apparaat
zonder startknop, "noemen" bij alles wat alleen op een meetstekker zit. Staat
het uit, dan noemt de overschottip het apparaat ook niet (`apparatenZin`).

**Een gemeten rij staat op slot** (v0.57.2, de eigenaar na de eerste beurt: "er
staan nog wel mijn dingen in; geblokkeerd tot je het wist, en dat je het
zelf kan invullen of toch overschrijven"): de velden tonen de meting en zijn
niet te bewerken; "wissen" geeft de eigen getallen terug, "overnemen"
(`takeMeasurement_`) maakt de meting de eigen opgave en haalt hem weg (het
verloop per vijf minuten gaat daarbij verloren). **Bespaard kiest zijn
woorden naar de beurten** (`woorden` in savings.js, `kind` in het
beurtrecord): een auto wordt ingeplugd en geladen, een vaatwasser
vrijgegeven en verbruikt. Een beurt van vóór v0.57.2 heeft geen `kind`;
`met_soort` in storage.py leidt hem dan af uit het type van het apparaat
(`PROGRAMMA_TYPES` in const.py), bij het opvragen van de lijst (v0.58.1,
De eigenaar: "ik zie nog dingen terugkomen van de laadpaal").

**Eén keer echt gezien aan Home Connect, 07-09-2026 om 11:00 in een echte woning:**
knop, Run na twee seconden, tellen op de meetstekker, Finished, verslag,
meting (Express 60: 90 min, 0,825 kWh, piek 2264 W), vrijgave eraf. Zijn
machine zet de deur een kwartier voor het eind vanzelf open voor de stoom
en trekt de laatste twintig minuten vrijwel niets; voor een domme
vaatwasser was `STIL_KLAAR` (een kwartier) daarmee te kort. Sinds v0.58.0
een half uur.

**Een herstart midden in een beurt verliest de telling niet** (v0.58.0,
De eigenaar: "ja, reken terug"). De lopende beurt gaat elke vijf minuten naar de
`BeurtenStore`, met `complete` op false en een `session` met alles wat de
coach nodig heeft (vrijgavemoment, prijzen van toen, verloop, wat er al
gemeld is). In de eerste ronde na een herstart (`eerste` in
`_one_programma`) pakt `_async_programma_hervatten` hem daar op; het gat
sinds die opslag komt twee minuten later uit de kwartieropslag
(`_async_programma_terugrekenen`, want die haalt na een herstart zelf
eerst in). Staat er niets in de opslag, dan zegt de recorder wanneer hij
ging draaien en de vrijgaveschakelaar wanneer hij werd vrijgegeven
(`_async_programma_begin`), en komt de hele beurt tot nu uit de
kwartieropslag. Is hij afgelopen terwijl de coach weg was, dan krijgt de
beurt zijn verslag met wat er bewaard stond en gaat de vrijgave eraf,
anders start hij zo nog een keer. Proef 62 in test_coach.py, scenario
`vaatwasser-herstart`.

**De eindtijd van het apparaat zelf** (v0.58.0, de eigenaar: "pak de eindtijd van
de integratie"): het veld Resterende tijd (`remaining`) mag een tijdstip
zijn (Home Connect) of minuten of seconden (`_eindtijd` in coach.py). "Klaar
rond" in de melding en op de kaart komt daarvandaan; zonder die sensor uit
de tabel. Proef 61. Een eindtijd die al voor de start stond telt niet
(v0.62.0; zie hieronder).

**Zonder meting gaat het verbruik op de piek, en de meterregel eist de
piek** (v0.59.0). De eigenaar op 08-09-2026 om 09:12: Eco 50 zonder meting startte
met 250 W op de meter, "waarom, terwijl bekend is dat de zon later meer
schijnt?" Uitgesmeerd was Eco (225 min, 0,8 kWh) 213 W, en dat paste; de
opwarmpiek van 2,2 kW kwam van het net terwijl het dak om 12:00 3,8 kW gaf.
Sinds die dag zet `_programma_stukken` zonder profiel alle kilowatturen op
`peak_w` vanaf de start (23 minuten voor Eco) en daarna niets, en grijpt
`meter_overal` in `plan_programma` alleen in als de meter ten minste de piek
laat zien. De gewone som met de meter voor het lopende uur blijft: zegt de
voorspeller de helft (zoals die dag), dan start hij zodra de meter van nu op
de som wint, en dat is een verwachting waar niets aan te schaven is (de eigenaar,
07-09). Scenario's `vaatwasser-vroeg` en `vaatwasser-vroeg-verwacht`, proef
50 in test_planner.py.

**Bespaard is het totaal plaatje** (v0.60.0). De eigenaar op 09-09-2026, bij een
vaatwasser die meteen op zon startte en "bespaard nul" kreeg: "Er is toch
wel iets zonne-energie naar de vaatwasser gegaan? Ik wil het totaal plaatje.
Wat het heeft gekost nu tegenover een duurder moment van het vrijgeven, en
wat je op zonne-energie laadt bespaar je natuurlijk ook door minder stroom
in te kopen." De maat is dus alles van het net op het moment van vrijgeven
of inpluggen (`_basis_bij` en `_programma_tellen` in coach.py), en bespaard
is maat min betaald, in twee delen: door de zon (`zon_winst`, `solar_saved`
in het beurtrecord: de zon-kilowatturen maal inkoop min teruglevering) en
door te wachten (de rest). Het verslag zegt welk deel wat was
(`_bespaard_zin`); Bespaard toont ze als tegels en als kolom "Door zon"
(`delen` in savings.js). Een beurt van vóór v0.60.0 heeft geen zondeel:
bij die beurten zat de zon in de maat en was bespaard alleen het wachten.
v0.59.0 had het één dag andersom (de zon van het vrijgavemoment in de maat,
`zon_toen`), en dat gaf precies de nul waar de eigenaar over viel. Proef 64.

**De meter is tien minuten zon, en de eindtijd hoort bij de beurt**
(v0.62.0). In een echte woning op 11-09-2026: om 09:29 vrijgegeven, en om 09:35
klaarde het een paar minuten op; de meter zag 2694 W teruglevering, meer dan
de piek van Express 60 (2264 W), en de coach startte. Om 09:37 was het 721 W;
de drie opwarmpieken kregen 1,1 tot 1,8 kW zon, 0,2 van de 1,0 kWh, en de
beurt kostte € 0,234 waar hij € 0,180 voorspelde. Sinds die dag krijgt
`plan_programma` als `surplus_w` de laagste teruglevering van de afgelopen
tien minuten (`METER_VENSTER`, `_meter_bijhouden` en `_meter_zeker` in
coach.py), voor het lopende uur én voor `meter_overal`; zolang er nog geen
acht minuten gemeten zijn (`METER_DEKKING`, na een herstart) telt de meter
niet en rekent hij met de verwachting. De paal houdt de meting van nu, want
die past zich elke ronde aan. De keerzijde: in een opkomende ochtendzon loopt
de meter tien minuten achter, en vier scenario's starten 3 tot 10 minuten
later, zonder dat het duurder wordt. En de melding zei "klaar rond 10:56":
dat was de eindtijd die Home Connect om 09:01 bij het kiezen van het
programma zette; om 09:37:05 rekende hij hem opnieuw uit (11:31), klaar was
hij om 11:28. `_eindtijd` neemt met `sinds` alleen een waarde die niet
eerder dan `EINDTIJD_MARGE` voor de start gezet is (`last_changed`), en de
melding "is gestart" wacht daar hooguit `EINDTIJD_WACHT` op; daarna de duur
uit de tabel, vanaf de start. Scenario's `vaatwasser-zonpiek` (oud: start
09:32 op de opklaring; nieuw: 11:56, 0,84 van 0,85 kWh zon) en
`vaatwasser-eindtijd` (oud: "klaar rond 10:45", nieuw: 11:21, zoals het
ging), proef 66 en 67 in test_coach.py. Het virtuele huis kent daarvoor
`Zon.pieken` (een opklaring die de voorspeller niet ziet) en
`Vaatwasser.eindtijd_tijdstip` (een eindtijd die al bij het kiezen staat en
pas een minuut na de start klopt).

**Een eindtijd telt pas als hij stilstaat** (v0.64.0). In een echte woning op
15-09-2026: om 09:33 vrijgegeven, om 10:11 startte de coach op de meter, en
de melding zei "klaar rond 11:33" terwijl hij om 11:45 klaar was. Deze keer
was het geen eindtijd van het kiezen: Home Connect zette hem om 10:11:56,
een seconde voor Run, en rekende hem om 10:13:02 opnieuw uit op 11:41. De
melding ging om 10:12:53, negen seconden voor die correctie. Sinds die dag
gelooft de coach een eindtijd pas als hij hem twee ronden achter elkaar
ongeveer hetzelfde zag (`_eindtijd_vast` in coach.py, `EINDTIJD_SPELING`);
ongeveer, want de sensor wiebelt een minuut heen en weer (11:41:02 en
11:42:02 om de minuut). Tot dan blijft staan wat er al geloofd werd, dus een
eindtijd die verspringt verdwijnt niet van de kaart. `EINDTIJD_WACHT` ging
van twee naar vier minuten: twee ronden zijn er nodig en de eerste waarde
komt soms pas een ronde na de start. De melding komt daarmee een tot twee
minuten later dan vroeger. Scenario `vaatwasser-eindtijd-bijstellen` (oud:
10:21 "klaar rond 11:09"; nieuw: 10:23 "klaar rond 11:21", en dat werd het),
`Vaatwasser.eindtijd_eerst_min` in het virtuele huis, proef 66 in
test_coach.py.

**Na de klaar-tijd: morgen of nu** (v0.63.0). De eigenaar gaf de vaatwasser op
12-09-2026 om 16:33 vrij, bij vanaf 08:00 en klaar om 16:30. De coach plande
de volgende middag, zei "hij start om 13:00" zonder "morgen", en noemde bij
"nu starten" de prijs van 08:00 de volgende ochtend; de eigenaar zette hem zelf aan.
Op 13-09: "ik wil dat er een optie bijkomt als hij na de klaartijd is. Dan de
keuze ingeruimd en morgen starten of ingeruimd en nu starten." Sindsdien geeft
`resolve_window` de klaar-tijd van vandaag mee als die voorbij is
(`Window.missed`), en staan er dan twee knoppen op de kaart: "Ingeruimd,
morgen starten" (de gewone vrijgave, het schema van de volgende dag; `later`
in het besluit zegt welke dag) en "Ingeruimd, nu starten" (`ready_now` in de
instellingen, `Apparaat.start_now`, regel `start-now`: meteen, ook in de
avondpiek, net als snelladen). Na een vrijgave voor morgen blijft "Toch nu
starten" staan. Voor de keukenkaart een tweede schakelaar, `release_now_switch`
(`_async_nu_volgen` in coach.py, keuze van de eigenaar): aan is ingeruimd én nu, uit
voordat hij draait haalt alleen "nu" eraf, de vrijgave uit haalt ook "nu"
eraf, en na de beurt gaan beide schakelaars uit. De teksten van een programma
zeggen "morgen om" (`_dag_om`, `_dag_klok` in planner.py), en "nu starten zou"
rekent met echt nu. Vóór de klaar-tijd verandert er niets. Proef 52 in
test_planner.py, proef 68 in test_coach.py, scenario's
`vaatwasser-na-klaartijd` (morgen 09:00 op zon, zoals het al ging) en
`vaatwasser-na-klaartijd-nu` (16:34, oud: die keuze was er niet).

**Home Connect Local** (v0.84.0). De eigenaar op 23-09-2026: "ik heb thuis
problemen gehad met mijn Home Connect vaatwasser integratie, ik had er 2
lopen en heb nu een derde, Home Connect Local. Die lijkt beter te werken."
Dat is `homeconnect_ws` (chris-mc1/homeconnect_local_hass, HACS): lokaal
over een websocket naar de machine zelf, geen cloud, en de statuswissels
komen meteen. Hetzelfde merk "Home Connect" in Apparaten; wat er anders is
zit in de entiteiten, en de coach leest alle drie de integraties met
dezelfde velden. Vier dingen, alle vier thuis gemeten op 23-09-2026:

1. **De startknop is er alleen als de machine een start aanneemt.** De
   knop hangt aan `BSH.Common.Root.ActiveProgram`, en die is met de deur
   open alleen leesbaar: de knop staat dan op `unavailable`. Met de deur
   dicht is hij er meteen, ook met de stroom uit (de machine zet zichzelf na
   elke beurt uit; de stroom aanzetten hielp niets, de deur dichtdoen wel).
   Home Assistant slaat een dienst op een onbeschikbare entiteit stilzwijgend
   over, dus drukken kost dan een poging zonder dat er iets gebeurt. De
   coach drukt daarom niet zolang de knop `unavailable` is, zegt na
   `START_WACHT` één keer waar het aan ligt ("de deur staat open", of "zet de
   machine aan en kijk of starten op afstand aan staat"), en drukt zodra de
   knop terug is; de knop staat daarvoor in `_watch`. Bij de twee
   cloud-integraties heeft de knop altijd een toestand en verandert er niets.
2. **Het programma zit in twee entiteiten die elkaar afwisselen**: de sensor
   "Actief programma" zegt alleen tijdens de beurt iets, de select
   "Geselecteerd programma" valt juist tijdens de beurt weg. `_one_programma`
   leest eerst `program` en dan `program_select`, tot er een programma uit
   komt; het paneel doet hetzelfde voor de rij op de kaart (`deviceDetails`
   in data-source.js). De spelling is `dishcare_dishwasher_program_kurz60`,
   zonder het streepje voor het getal; `programma_van` en `valueLabel` gooien
   alles wat geen letter of cijfer is toch al weg.
3. **De resterende tijd staat in uren** (de machine telt in seconden, Home
   Assistant toont het als 1,4833 h). `_eindtijd` en `countdown` in format.js
   kennen nu seconden, minuten, uren en dagen; zonder eenheid minuten.
4. **"Start op afstand" is een eigen sensor**, en dat hebben de andere twee
   ook. Optioneel veld `remote_start` bij het merk: staat hij uit, dan drukt
   de coach niet en zegt hij na `START_WACHT` één keer "zet starten op
   afstand aan op het apparaat". Zonder die sensor blijft het zoals het was:
   drukken, en na drie minuten zeggen dat hij niet is gaan draaien.

Na een beurt zegt Local vijf seconden "finished" en dan "ready" (de machine
gaat uit); de coach ziet vaak alleen dat laatste, en dat was al klaar (de
tak `status in ("ready", "inactive", "")` met een lopende beurt). De
sensorwacht kent de status al; een herverbinding van twee seconden
(`unavailable`, thuis om 08:37 en 08:46) blijft onder `SENSOR_STIL`.

Het virtuele huis kent `Vaatwasser(lokaal=True)`: de knop `unavailable` bij
een open deur of tijdens de beurt, en een druk daarop doet niets (zoals Home
Assistant), de sensor en de select die elkaar afwisselen, de uren, en de
sensor voor starten op afstand. Scenario's `vaatwasser-lokaal` (dezelfde
beurt als `vaatwasser-zon`, tot op de cent), `vaatwasser-lokaal-deur-open`
(om 03:00 vrijgegeven met de deur open: geen druk, om 03:03 de melding,
om 03:08 gaat de deur dicht en om 03:09 draait hij) en
`vaatwasser-lokaal-afstand-uit` (geen enkele druk, één melding). Proef 92 in
test_coach.py, twee proeven in test_rapport.mjs. **Nog geen echte beurt aan
Home Connect Local gestuurd**: de eerste is de vrijgave thuis na v0.84.0.

**Een sensor zegt wanneer hij start** (v0.100.0). Thuis op 26-09-2026: om
12:16 vrijgegeven met de schakelaar op de keukenkaart (een Lovelace-kaart die
alleen entiteiten kent), de coach plande 14:00, en om 13:12 ging hij met de hand
aan. Op het paneel stond "Hij start om 14:00", op de keukenkaart niets. De
eigenaar: "dan wil ik dat er op de vaatwasser kaart komt te staan wanneer de coach
van plan is om de vaatwasser aan te zetten." Gekozen boven een kaart die het de
coach zelf vraagt: een sensor werkt in elke kaart en in een automatisering.
`sensor.py`: één `StartOmSensor` per apparaat met een programma, onder een
apparaat "DomotiApp Coach", met het tijdstip als toestand (`gepland_om`: alleen
bij `wait-for-start`), en leeg als hij niet vrijgegeven is, nu start of draait.
In de attributen de zin van de coach (`reason`, `plan`, niet in de recorder),
`rule`, `released`, `running` en de vrijgaveschakelaar (`release_switch`), zodat
een kaart die die schakelaar kent de sensor zelf kan vinden. Hij rekent niets:
hij volgt `EVENT_DECISION` en `EVENT_SETTINGS_UPDATED`. Proef 110 in
test_coach.py; het harnas kent daarvoor een nagebouwde `SensorEntity`.

Wat er thuis gebeurde, voor wie het later naleest: de meter zag tussen 12:16 en
13:12 op zijn laagste 940 W teruglevering over tien minuten (`METER_VENSTER`),
de opwarmpiek van Express 60 is 2277 W gemeten, dus `meter_overal` greep niet in
en de verwachting won. Met wolken zakte de teruglevering af en toe naar nul;
de 3 kW die de eigenaar zag waren pieken van een paar minuten. De beurt kostte
€ 0,190; nagerekend met de werkelijke zon en het echte verloop van de machine
had 12:17 € 0,198 gekost en 14:00 € 0,203, alles van het net € 0,238. De
verwachting stond bovendien een uur te laat (Forecast.Solar, zie
`docs/laadpaal.md`), en die van 12:16 is niet bewaard: nagespeeld met de kromme
van die avond en met die uit de sensoren van 11:48 kwam 13:00 à 13:15 eruit, niet
14:00.
