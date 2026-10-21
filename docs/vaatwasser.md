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
Proef 60 in test_coach.py. **De schakelaar van de eigen stekker is geen vrijgave** (v0.101.11). In
de eerste woning stond tot 29-09-2026 de schakelaar van de meetstekker onder
de vaatwasser als vrijgaveschakelaar ingevuld, en de bewoner meldde "sinds de
coach is geinstalleerd wordt de smart plug regelmatig uitgeschakeld". Het
logboek gaf vier keer een `turn_off` op de seconde van "is klaar", na de beurt
van 28-09 bleef hij 31 uur zonder stroom, en de stekker weer aanzetten las de
coach als "ingeruimd en dicht", met twee dagen achter elkaar een kritieke
"zet hem nu aan". Een vrijgaveschakelaar (of die van nu starten) op hetzelfde
apparaat in Home Assistant als de vermogenssensor laat de coach nu helemaal
met rust (`_vrijgave_entiteit` in coach.py, één waarschuwing in het log), en
Apparaten zegt het op de ingeklapte regel (`releaseOnOwnPlug` in devices.js,
uit `hass.entities`). De sensor "<apparaat> start" noemt in `release_switch`
nog wel wat er is ingevuld. Proef 120 in test_coach.py en een proef in
test_rapport.mjs.

**Een vrijgaveknop** (v0.102.0, `release_button`, bij allebei de merken). De
eigenaar op 29-09-2026: "een fysieke zigbee knop waar men op kan drukken die
een event detecteert op input press." Wat telt als druk
(`_async_knop_volgen` in coach.py): een event-entiteit (Zigbee via ZHA of
Zigbee2MQTT, Hue, Shelly) of een knop-helper (`input_button`, `button`) krijgt
het tijdstip van de druk als toestand; een actiesensor (Zigbee2MQTT oud) de
soort ("single") en daarna weer leeg. Zijn keuzes: een druk is altijd
vrijgeven en nooit wisselen, want een knop heeft geen lampje; nog een keer
drukken doet niets. De soort druk is te kiezen (`release_press`, uit
`event_types` of `options` van de knop zelf, keuzelijst "Welke druk" in
Apparaten; leeg is elke druk). Na een druk die iets veranderde één melding
naar de telefoon, na het besluit van die ronde: "Vaatwasser is vrijgegeven.
Hij start om 01:00." (of "Zet hem aan om 11:00." bij een domme). Een oude druk
na een herstart of na een knop die even wegviel telt niet. Een knop die Home
Assistant niet als entiteit kent kan via een eigen automatisering een
`input_button` indrukken. "Ingeruimd en nu starten" gaat niet met de knop
(zijn keuze). Proef 121 in test_coach.py.

**Moet eerst vrijgegeven worden** (v0.102.0, `release_required`, standaard
aan). De eigenaar op 29-09-2026: "bij het toevoegen van een vaatwasser: moet
eerst vrijgegeven worden. Als je die aanzet verschijnt er een invulveld voor
je helper of knop, en de kaart toont Ingeruimd en dicht. Staat het vinkje uit,
dan mag de vaatwasser gewoon draaien met de coach als de klep dicht zit, en
dan heb je ook geen knop vrijgeven op de kaart." Alleen bij een merk dat de
klep ziet en zelf kan starten (`canSkipRelease` in devices.js: een deurstand
en een startknop, dus Home Connect); een domme vaatwasser vraagt altijd.
Zonder vrijgave verdwijnen de vrijgavevelden (`brandFields`), de kaart vraagt
nergens om (`needsRelease`), en is de deurstand nodig (`missingForControl`).
De coach (`_async_klep_volgen`): klep dicht is vrij, klep open niet, en ook
niet zolang starten op afstand uit staat (dan zegt de machine zelf nee; Bosch
en Siemens zetten het uit zodra de deur opengaat), na een beurt tot de klep
open en weer dicht is geweest (anders start hij meteen weer met de schone vaat
erin), en als de machine zelf "klaar" zegt (na een herstart het enige teken).
Een lege machine die na het uitruimen dichtgaat herkent hij niet; dat staat
bij het vinkje. Tijdens een beurt blijft alles staan. De reden op de kaart
zegt waar hij op wacht (`door_release` in `Apparaat`, planner.py). Proef 122
in test_coach.py, een proef in test_rapport.mjs, scenario
`vaatwasser-klep-dicht` in het virtuele huis (de deur gaat daar na een beurt
van "finished" naar "ready" zodra hij opengaat, zoals bij Home Connect). **De schakelaar en de status van een
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
door te wachten (de rest). Het verslag zei tot v0.102.1 welk deel wat was;
sindsdien alleen het totaal, omdat het te lang werd voor een telefoon
(`_bespaard_zin`, zie `docs/laadpaal.md`). Bespaard toont ze als tegels en als kolom "Door zon"
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

**Sinds v0.100.1 is de toestand de tekst van de kaart.** In v0.100.0 was het een
tijdstempel, en die toont Home Assistant als "over 2 uur" of "unknown". De
eigenaar, met de sensor in zijn eigen installatie voor zich: "de coach beslist toch
immers zelf wanneer hij gaat starten en dat moet de sensor laten zien, dus een
tijd, en is het morgen dan morgen om." Nu `start_tekst`: "om 14:00", "morgen om
09:00", "zondag om 09:00" (`_dag_om`, dezelfde woorden als het besluit), of
"nu"; leeg als er niets gepland is. Het tijdstip staat in het attribuut `start`.
De naam werd "<apparaat> start"; de `unique_id` bleef `_start_om`, zodat een
bestaande entiteit niet verweesd raakt. Hij vroeg ook of dit op zijn systeem
gebouwd was, want hij zag zijn eigen `input_boolean` erin: dat is wat hij bij
Apparaten als vrijgaveschakelaar invulde, en bij een ander staat daar het zijne
of niets. Er staat geen entiteitnaam in de code (proef 42).

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

**Het verslag zegt waar de stroom vandaan kwam** (v0.101.0), voor elk apparaat met
dezelfde regel (`_herkomst_zin` in coach.py): "0,3 kWh zon, 0,6 kWh
thuisbatterij." (tot v0.102.1 een hele zin: "0,3 kWh kwam van je zon en 0,6 kWh
uit je thuisbatterij."), met het bedrag alleen bij het net, want dat is wat er aan de
leverancier betaald is. "Ongeveer € 0,199" is eruit: de eigenaar las dat bij een
beurt die vrijwel niets van het net haalde. Bedragen onder een euro in drie
decimalen, daarboven in twee, per zin gelijk (`_bedrag`). Proef 113.


## De vaatwasserkaart en de coach: een eigen apparaat en drie knoppen (v0.110.0)

De eigenaar op 11-10-2026, over de knoppen "Ingeruimd, morgen starten" en "Ingeruimd, nu
starten" in het paneel: "Dat moet ook op de vaatwasser kaart komen." En: kaarten voor de
vaatwasser, de laadpaal en de thuisbatterij in een pop-up, "dan hoeven klanten niet
telkens naar de coach toe". De kaarten bouwt DomotiApp Lovelace; de coach levert gewone
entiteiten, zodat ze ook in een gewone kaart, een bubble-card en een automatisering werken.
De afspraak tussen die twee heet het contract; dit is versie 1 (`CONTRACT` in entiteit.py).

**Algemeen.** Per apparaat van de coach één apparaat in Home Assistant: identifiers
`(domotiapp_coach, <id bij de coach>)`, de naam van de klant, fabrikant "DomotiApp Coach",
model de soort (Vaatwasser, Wasmachine, Droger, Boiler, Laadpaal, Thuisbatterij;
`apparaat_info`). Elke entiteit heeft `has_entity_name` en een vaste `translation_key`; een
kaart vindt de entiteiten aan het apparaat en die sleutel, dus hernoemen breekt niets. De
toestand is tekst voor mensen en mag veranderen; **de attributen zijn het contract.** De
vaatwasserkaart werd ooit gebouwd tegen een toestand die een avond later tekst werd
(v0.100.0 en v0.100.1), en zag daarna niets meer.

**Een apparaat met een programma** (`PROGRAMMA_TYPES`):

| entiteit | translation_key | wat |
|---|---|---|
| sensor | `start` | bestond al (v0.100.0); state "om 14:00", "morgen om 09:00", "nu" of leeg |
| binary_sensor | `vrijgegeven` | de vrijgave in de coach (`ready_devices`): de waarheid |
| button | `ingeruimd_morgen` | vrijgeven, starten op het goedkoopste moment (heet "Ingeruimd, goedkoopste moment": wie 's ochtends drukt start vandaag) |
| button | `ingeruimd_nu` | vrijgeven en nu starten |
| button | `vrijgave_intrekken` | vrijgave en "nu" eraf |

Op de startsensor, naast `start` (ISO met zone) en `release_switch` die bestaande kaarten
al lezen: `contract` (1), `type`, `stand` (`niet_vrijgegeven`, `gepland`, `start_nu`,
`draait`, `klaar`; `programma_stand`), `vrijgegeven`, `nu`, `klaar_om` (de klaar-tijd uit het
schema, ISO met zone), `later` (de dag waar hij naar opschuift als de klaar-tijd van vandaag
voorbij is: dan zegt het paneel "Ingeruimd, morgen starten"), `entiteiten` (wat de klant bij
de coach invulde, zodat de kaart het niet nog eens vraagt) en sinds v0.127.0 `alleen_lezen`
(zie "Alleen uitlezen" onder Miele).

Sinds v0.140.2 staat op alle vier de sensoren van de coach (programma, laadpaal, thuisbatterij,
airco) ook `taal`: `nl` of `en`, de taal waarin de coach schrijft (Installatie > Taal, bij
automatisch die van Home Assistant). Een kaart die Automatisch staat volgt die; zonder `taal`
(een coach van daarvoor) neemt hij die van Home Assistant. Het contract blijft 1: het is
alleen iets erbij.

De knoppen doen dezelfde som als de knop in het paneel (`async_vrijgave`, dat
`domotiapp_coach/device/ready` nu ook gebruikt) en laten de coach meteen kijken. De
vrijgaveschakelaar van de klant volgt in de ronde erna, zoals altijd: wie het laatst bewoog
wint (`_async_schakelaar_volgen`).

Het oude apparaat "DomotiApp Coach", waar de startsensor tot nu aan hing, haalt de coach een
minuut na het opstarten weg zodra er niets meer aan hangt (`oude_coach_opruimen`); de
entity_id van de startsensor blijft, want de unique_id blijft.

De laadpaal en de thuisbatterij volgen in een eigen uitgave, met hetzelfde contract (sleutels
staan in het bericht aan de lovelace-sessie van 11-10-2026 en komen hier bij die uitgave).
Proef 143 in test_coach.py.

## Wasmachine en droger, met Miele (v0.124.0)

De eigenaar op 15-10-2026: "Ik wil dat de coach wel weer de apparaten aanmaakt: Wasmachine
droger en vriezer." Aanleiding was een klantwoning met een Miele-wasmachine, -droger en
-vriezer aan de integratie `miele` van Home Assistant (via de cloud). Voor de wasmachine en de
droger koos hij "Starten, zoals vaatwasser", met de merken **Miele en Overig**. De vriezer komt
in een eigen uitgave.

Wasmachine en droger zijn dus weer types (`DEVICE_TYPES`, niet meer in `VERVALLEN_TYPES`) en
programma-apparaten (`PROGRAMMA_TYPES` in const.py, `PROGRAM_TYPES` en `RELEASE_TYPES` in
devices.js; test_rapport.mjs legt die twee naast elkaar). Alles van hierboven geldt: de
vrijgave, het goedkoopste moment, de knop, de melding als hij niet gaat draaien, de klaar-tijd,
zonder vrijgave deur dicht, het verslag, Beurten, de meting, en de kaarten van DomotiApp
Lovelace (dezelfde entiteiten, `type` "wasmachine" of "droger").

**De vrijgave heet "Mag meedraaien".** "Ingeruimd en dicht" is een vaatwasserwoord. De andere
types hadden al "Mag meedraaien" (`releaseCopy`), en de kaart van DomotiApp Lovelace zegt
hetzelfde (0.70.0). In de teksten van de coach staat dan "Wacht tot je hem vrijgeeft." en "Je
koos nu starten" (`VRIJGAVE_WOORD`, `Apparaat.vrijgave` in planner.py). Zonder vrijgave zegt
Apparaten "deur dicht" en "de schone was" (`vaatwasser` in voorkeur-velden.js).

**Miele.** Wat de integratie geeft en wat de coach ermee doet:

| veld | Miele | wat de coach ermee doet |
|---|---|---|
| Status | de sensor met de naam van de machine (`status`, een enum van 19) | vertaald naar de woorden van Home Connect (`MIELE_STATUS` in coach.py): `programmed` en `waiting_to_start` zijn "ready", `in_use` is "run", `pause` en `rinse_hold` zijn "pause", `program_ended` is "finished"; `program_interrupted` is midden in een beurt een pauze en anders "finished" (v0.127.0) |
| Programma | de sensor Programma (`program_id`), een sleutel als `cottons` | precies op de sleutel opgezocht, niet zoals `programma_van` (bij Miele is "denim" het eind van "gentle_denim") |
| Resterende tijd | `remaining_time`, minuten | zolang het programma klaarstaat de duur waarmee hij plant; tijdens de beurt "klaar rond" |
| Start op afstand | `mobile_start` | uit: niet drukken, en één keer zeggen dat het aan moet |
| Deur | `door` | zoals bij de vaatwasser |
| Starten, Stoppen | buttons `start`, `stop` | staan in Home Assistant standaard uit, de installateur zet ze aan; ze zijn er alleen als de machine een start aanneemt, en dan wacht de coach zoals bij Home Connect Local |
| Energieteller | `energy_consumption`, kWh per programma, in stappen van een tiende | `energy_entity`; daar telt hij de beurt uit (zie hieronder) |

Er is geen vermogenssensor, en geen tabel vooraf (`programOnMachine`, `energyCounter` in
devices.js). Het programma kies je op de machine; de kaart toont welk (`programPicker` geeft
`machine`) met de naam zoals Home Assistant hem vertaalt: het paneel via `formatEntityState`
(`label` in state-feed.js), de coach via de vertalingen van de integratie
(`_async_staat_naam`, "cottons" wordt "Katoen"), en anders de sleutel netjes.

**Een programma dat de coach nog niet gemeten heeft** plant hij op de duur die de machine geeft,
alsof het verbruik gelijk over die duur valt, zonder kWh: de keuze van de eigenaar op 15-10-2026
uit drie (`_async_machine_programma`, `Programma.kwh_bekend`). In `programma_kosten` telt een
stuk met verwacht overschot dan als zon en een stuk zonder als net; de uitkomst is een gewicht en
geen bedrag, dus noemt de coach er geen (`plan_programma`). Na de beurt staat de meting in
`program_measured` met de naam erbij (`label`), en komt hij de volgende keer in de tabel ook
zonder rij (`met_metingen` met `ook_nieuw`); dan rekent hij met de kWh, gelijk over de duur,
want een teller heeft geen verloop (geen piek, geen profiel). In Apparaten staan bij Miele alleen
de gemeten programma's, per stuk te wissen (`machineProgramsHtml_`).

**Tellen op een teller** (`_teller_tellen`). Elke ronde gaat in een buffer met de prijs en wat
de meter naar het net zag gaan; zet de teller een stap, dan wordt die over de ronden sinds de
vorige stap verdeeld, en het zondeel komt uit de meter over diezelfde ronden (netto terug plus
de stap). Een eerste versie rekende een vermogen uit de teller en legde dat per minuut naast de
meter; in het virtuele huis zei het verslag van een nachtelijke beurt toen "0,5 kWh zon", want
dat vermogen loopt een stap achter. Bij "afgelopen" telt de laatste stap nog mee
(`_teller_afronden`). Wat er onder een tiende overblijft ziet de coach niet: het verslag zegt
wat de teller zegt.

**Overig** is een machine op een meetstekker, zoals de domme vaatwasser: de coach zegt wanneer,
de bewoner drukt. Zonder opgave van de fabrikant begint de tabel leeg (`tabel_van` met
`standaard`, `defaultPrograms(device)`); de bewoner voegt de programma's toe die hij gebruikt.

**Niet in het echt gezien.** Nog open bij Miele: of `remaining_time` de duur al geeft zolang het
programma klaarstaat (zonder duur zegt de coach dat hij het programma niet kent), en wat de
teller doet tussen twee programma's. De beheersessie stuurt een dump van een draaiend programma.

**Een onderbreking is een pauze (v0.127.0).** In de klantwoning op 16-10-2026, gemeten door de
beheersessie: 08:59:26 `in_use`, 08:59:42 `program_interrupted`, 09:00:16 weer `in_use`; 16
seconden, waarin de temperatuur werd bijgesteld. De coach las "afgebroken" als klaar,
en bij een machine die hij stuurt had dat een valse melding "is klaar" gegeven, een beurt van 16
seconden en een vrijgave die eraf ging. Nu telt `program_interrupted` midden in een beurt als een
pauze (`sessie["afgebroken"]` in `_one_programma`): gaat hij weer draaien, dan loopt de beurt
door; gaat hij daarna uit of staat hij weer klaar, dan is de beurt voorbij, zegt het verslag "is
afgebroken" en komt er geen meting (`_async_programma_klaar`), want de duur zegt dan niets over
het programma. Zonder lopende beurt blijft het "finished", zoals eerst. Geen tijdslimiet: die
zou verzonnen zijn.

**Het verslag van een afgebroken programma is compleet (v0.128.1).** Tot dan stond er "19:05 tot
21:10": van de start tot het uitgaan, en je zag niet dat hij het grootste deel daarvan stillag. De
eigenaar op 16-10-2026: "ik wil een compleet verslag". Nu: "0,4 kWh, gestart om 19:05, onderbroken
om 19:30, uit om 21:10." (`sessie["onderbroken_om"]`, gezet bij de eerste ronde van een
onderbreking en gewist als hij weer draait). Staat er na de onderbreking een nieuw programma klaar
in plaats van uit, dan "afgebroken om" (`uit` in `_async_programma_klaar`). Wordt hij meer dan een
keer onderbroken, dan noemt het verslag de laatste. Een programma dat na een onderbreking gewoon
afmaakt houdt het gewone verslag.

**Alleen uitlezen (v0.127.0).** Zonder het vinkje "mag sturen" sloeg de coach een apparaat met
een programma helemaal over. In dezelfde klantwoning zette de eigenaar de wasmachine en de droger
die middag op alleen uitlezen; de startsensor bleef staan op "Wacht tot je hem vrijgeeft.", de
knoppen bleven er, en er was geen draait, klaar of meting meer. Nu volgt hij zo'n apparaat zoals
bij Alleen uitlezen in Strategie (`LEVEL_READ` voor dat ene apparaat): draait en klaar op de
kaart, de meldingen en het verslag, en de meting, maar hij start hem nooit. Hij leest de vrijgave
niet en komt niet aan de knop, de vrijgaveschakelaar of de klep (`_programma_alleen_lezen`), en
zolang hij niet draait is het besluit `read-only`, "Alleen uitlezen: de coach start hem niet."
Het is geen sessie: Sessies in Historie is wat de coach liet draaien. Voor de kaarten:
`alleen_lezen` op de startsensor, en de drie knoppen en `vrijgegeven` op niet beschikbaar
(`ProgrammaBediening` in entiteit.py, zoals `AccuBediening` bij een batterij); ze komen terug
zodra het vinkje weer aan staat. `stand` blijft een van de bestaande sleutels. Proef 162 in
test_coach.py.

Proef 160 in test_coach.py; scenario's `wasmachine-miele` en `wasmachine-miele-gemeten` in het
virtuele huis (`Vaatwasser(miele=True)`: de standen, de sleutel, de duur, de teller in tienden,
geen vermogenssensor); vijf proeven in test_rapport.mjs.

**Ook in deze uitgave:** het airco-merk Mitsubishi Electric (v0.119.1) stond alleen in het
paneel, en het schema van de websocket weigerde een airco met dat merk bij het opslaan.
`AIRCO_BRANDS` staat nu in const.py, en test_rapport.mjs legt elke merkenlijst van het paneel
naast const.py.
