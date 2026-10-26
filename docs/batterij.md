# De thuisbatterij

Uit `CLAUDE.md` gehaald op 24-09-2026, zodat dat bestand kort blijft. De eisen
van de eigenaar en de werkafspraken staan daar en gaan boven alles hier.
Komt er bij een uitgave iets bij over dit onderwerp, schrijf het dan hier.

Sinds 22-09-2026 stuurt de coach ook een thuisbatterij (v0.73.0), na de eigen
"Ik wil de coach gaan uitbreiden met een thuisbatterij. Ik wil hem kunnen
aansturen in HA. Laden, ontladen, blokkeren als de laadpaal laadt. Laden op
goedkope tarieven overdag en in de nacht. Laden op overschot zonne-energie. Hij
moet helemaal samenwerken met de energiecoach." En diezelfde avond, toen ik
voorstelde de batterij zijn eigen nul-op-de-meter te laten doen: **"het doel is
om hem volledig third party te sturen, dus via HA."**

**Twee lagen, en dat is de kern.** `batterij.py` kent Home Assistant niet, net
als planner.py.

* `plan_batterij` kiest elke minuut een **stand**. Het is een som over de tijd
  (`_waarde_vooruit`): van achter naar voren over alle blokken met een bekende
  prijs, per inhoud van de batterij wat de rest nog kost, met het verwachte
  huisverbruik en de zon erin (`_netto_huis_kwh`, dezelfde bronnen als
  `overschot_kwh`). Aan het eind is wat er nog in zit waard wat een gemiddeld
  bekend uur kost (`_gemiddeld_bekend`). Dat is dezelfde gedachte als
  `schijven` en `goedkoopste`, alle manieren op een hoop, maar een batterij kan
  twee kanten op en onthoudt wat erin zit.
* `Regelaar` voert die stand uit op het tempo van de meter (`_async_regel` in
  coach.py, gewekt door de netsensor en daarnaast elke `REGEL_TIK`).

**De standen** (de namen zijn van de bewoner van de eerste woning, 21-09-2026):
`nul`, `zonneladen`, `ontladen`, `netladen`, `max-laden`, `handelen`, `standby`.
`Besluit.grenzen` zegt per stand of de regelaar mag laden en mag ontladen; meer
verschil is er voor de regelaar niet.

**Zon opslaan en het huis voeden gaan tegen wat een kilowattuur straks waard
is** (`erbij` en `eraf`, het verschil in de som over een stap van het rooster).
Bij gelijkspel wint wat je in handen hebt: op een zonnige dag komt de batterij
toch vol, en wie dan "straks" kiest rekent op zon die er nog niet is. **Van het
net laden en handelen volgen het plan zelf** (`_rustig_vermogen`): de
vergelijking staat in het randuur precies op gelijkspel en viel in het virtuele
huis elke minuut anders, zeven wissels in een kwartier.

**Rustig laden.** De bewoner van de eerste woning: "als we 5u lang een
energieprijs van 13 cent hebben, heb ik liever dat ie 5u lang laadt op 50%
capaciteit, dan 2,5u op 100%." Wat het plan in de aaneengesloten even dure uren
van het net wil halen wordt over al die uren uitgesmeerd; dezelfde gedachte als
`rustig_tempo` bij de paal. Hij noemde erbij dat een omvormer tussen 30 en 75%
van zijn vermogen het zuinigst is. **Dat getal staat er niet in**: het is een
vuistregel en geen meting van deze batterij. Uitsmeren over even dure uren kost
nooit geld; een duurder uur erbij nemen om rustiger te laden is pas een som als
het rendement per vermogen gemeten is. Dat is het sinds v0.142.0 (hieronder), en
de som rekent nu met het rendement bij het vermogen van elk blok; het uitsmeren
over even dure uren is gebleven zoals het was.

**Het rendement per vermogen, zelf geleerd** (v0.142.0). De eigenaar op
19-10-2026, bij een grafiek van een thuisbatterij die bij 200 W ongeveer 70% haalt
en vanaf 1.200 W 92 tot 93%: "RTE is dramatisch op lage vermogens.. NoM in de
nacht niet bevorderlijk dus." Eerst gemeten in de eerste woning, tien dagen, 896
schone stappen van een procent (de scripts en de uitkomst staan in de
privénotities): laden 92% boven 1,2 kW; ontladen 88% bij gemiddeld 0,58 kW (vooral
's nachts nul op de meter), 93% bij 0,7 tot 1,2 kW en 96% daarboven; een vast
verlies bij ontladen van ongeveer 68 W. Heen en terug over die tien dagen 83,2%.
De eigenaar: "ja, bouwen" (21-10-2026).

De coach doet die som nu zelf (`Rendementmeter` in batterij.py), in de regelaar
(`_async_regel`), dus alleen bij een batterij die hij stuurt. Een stap begint als
de accustand een procent omslaat en eindigt bij de volgende omslag dezelfde kant
op: dan ging er een procent van de capaciteit in of uit de cellen. Daartegenover
wat er aan de wisselstroomkant doorheen ging, uit de tellers van een kWh-meter op
de batterij als die er is en anders uit het vermogen van de batterij zelf (de
sensor, niet de opdracht). Niet geteld: een sprong van twee procent, een
omkering, een gat van meer dan 90 seconden in de metingen, meer dan 2% de andere
kant op (`RTE_TEGEN`), onder 10 of boven 90% (`RTE_SOC_LAAG`, `RTE_SOC_HOOG`; daar
kalibreert de batterij zich en kwamen er in de meting waarden boven 100% uit), en
een stap waarvan niet de helft van de tijd in één vermogensband lag. De banden
(`RTE_BANDEN`): onder 300 W, 300 tot 700, 700 tot 1.200, 1.200 tot 2.000 en
daarboven. Per band per richting gaan de sommen naar `rte_steps` in
`battery_state`; boven 400 stappen in een band telt alles voor de helft, zodat
een batterij die ouder wordt meegenomen wordt.

`rendement_uit_stappen` maakt daar per richting punten van (het gemiddelde
vermogen aan de accukant, het rendement over de band), zodra een band tien
stappen heeft en een richting dertig. Tussen twee punten recht getrokken, buiten
de punten het dichtstbijzijnde: verder dan de metingen reiken neemt de coach
niets aan, ook niet bij 100 W als hij alleen vanaf 300 W gemeten heeft. **Het
gaat voor alles**: voor de kWh-meter heen en terug, en voor wat de bewoner
invulde, want het is een meting en per richting. In het virtuele huis
(`batterij-rendement-leren`, een batterij met 68 W vast verlies en 92% laden,
zonder kWh-meter) leert hij in zestig uur 79% bij 0,33 kW, 90% bij 0,68, 93% bij
0,97 en 96% bij 1,83 kW, en laden 92%, op een procent na wat de batterij doet.

Waar het meetelt (`eta_in`, `eta_uit`, `_ac`, `_cel_in`, `_cel_uit`): in de som
over de tijd per blok, bij het vermogen dat de batterij in dat blok zou draaien;
in het besluit van het moment of zon opslaan en het huis voeden lonen, bij wat het
huis nu vraagt of er nu over is; en in de nachtbalans per uur, bij wat het huis in
dat uur vraagt. Wat geen vermogen kent (wat een kWh in de batterij straks waard is,
onder welke prijs inkopen loont) rekent met het gemiddelde per richting. Zonder
rendement per vermogen is het per richting de wortel van het rendement heen en
terug, zoals altijd. **Daarbij rechtgezet:** de nachtbalans, de grens voor de auto
en de hulp aan de auto rekenden het hele verlies heen en terug als ontlaadverlies,
en hielden dus te veel over (in `batterij-helpt-auto-nacht` 6% om 07:00 in plaats
van ruim 8; de accu haalt de ochtend nog steeds zonder de bodem te raken).

In de pop-up staat het als "83% gemeten", met per richting de punten ("Laden 92%
bij 2,3 kW", "Ontladen 88% bij 0,6 kW, 96% bij 2,1 kW"), uit `rte_power` in
`battery_state`. Wissen van de metingen (`device/measurements/clear`) haalt
`rte_steps` en `rte_power` weg, en de regelaar begint opnieuw. Wat er bij een
batterij die zelf nul doet uit komt, kan hij alleen als hij hem stuurt: stilstaan
mag daar niet (de eigenaar op 21-10-2026), dus 's nachts op 300 W het huis voeden
blijft wat die batterij doet; het rendement maakt dan vooral de sommen en de
nachtbalans eerlijker.

**Het rendement is een meting of een opgave, nooit een aanname.** In de eerste
woning kwam van elke kilowattuur die de kWh-meter op de batterij erin zag gaan
73,6% er weer uit.
De eigen tellers van die batterij telden meer eruit dan erin,
want die meten aan de accukant. `rendement_uit_tellers` wil tien keer de inhoud
aan doorzet (`RTE_MIN_DOORZET`) en weigert alles buiten 30 tot 100%. Zonder
kWh-meter geldt wat de bewoner invult, en alleen dat: tot v0.101.2 ging een
ingevuld rendement ook de opslag in (`rte` in `battery_state`) en won die daarna
van het veld, zodat aanpassen of leegmaken niets deed. Nu staat daar alleen een
meting, en telt die alleen met een kWh-meter (`_batterij_van`, proef 114). Sinds
v0.142.0 gaat het rendement per vermogen daar nog boven, ook zonder kWh-meter (zie
hierboven). De
eigenaar op 29-09-2026: "ik wil wel het rendement erin zetten als ik geen kWh
meter heb." Zolang er gesaldeerd wordt levert opslaan niet meer op dan de
terugleverkosten: onder (prijs min terugleverkosten) gedeeld door de prijs, bij
de eigenaar 78,2%, laat de coach de zon liever naar het net gaan. Zonder
rendement wordt er niet gepland: alleen nul op de meter (`rendement-onbekend`),
en met volledig salderen standby, want dan verliest opslaan altijd.

**Op de kaart: ongeveer, uit de tellers van de batterij zelf** (v0.118.0). Zonder
kWh-meter en zonder opgave stond er "Rendement: nog niet bekend", terwijl de
meeste batterijen zelf tellen wat erin en eruit gaat. Twee optionele velden
onder de kWh-meter, "Batterij zelf: geladen" en "Batterij zelf: ontladen"
(`accu_in`, `accu_out`), geven dan op de kaart "ongeveer 88%, gemeten in de
accu". Met dezelfde toets als de kWh-meter (`rendement_uit_tellers`: tien keer
de inhoud aan doorzet, 30 tot 100%), maar in een eigen sleutel `rte_accu` in
`battery_state`, die `_batterij_van` nooit leest. **De coach rekent er niet
mee**, want die tellers zien het verlies in de omvormer niet: in de eerste
woning telden ze 102,6% tegen 73,6% op de kWh-meter, en bij salderen begint
opslaan pas boven ongeveer 78% iets op te leveren. Een te hoog rendement laat
laden van het net en handelen lonen terwijl het geld kost. De eigenaar op
14-10-2026: "ja alleen op de kaart". Volgorde op de kaart: gemeten, opgegeven,
ongeveer uit de accu, nog niet bekend; het wissen van de metingen (`device/measurements/clear`) haalt `rte_accu` ook
weg. Proef 154 in test_coach.py. Historie telt er sinds v0.126.1 wel geladen en
ontladen mee, na een kWh-meter en voor de vermogenssensoren (`fetchBattery`,
`docs/eerste-woning.md`); dat raakt geen besluit van de coach.

**Kost stroom elk uur hetzelfde, dan zegt de coach dat inkopen nooit loont**
(v0.101.10, `_vlak` in batterij.py). Bij de eigenaar stond op 29-09-2026 met een
vast contract "het rendement van de batterij is nog niet bekend, dus van het net
laden doet hij nog niet", met de oproep het rendement in te vullen. De eigenaar:
"waarom zegt de coach dit terwijl ik een vast contract heb? Inkopen is niet
rendabel en heeft alleen maar verlies." Zijn alle bekende prijzen gelijk, dan is
het besluit gewoon nul op de meter met "stroom kost bij je contract elk uur
hetzelfde, dus van het net laden levert nooit iets op", en eindigt de nachtbalans
met "dat komt van het net" in plaats van "hij laadt bij als de stroom goedkoop
genoeg is". Het gaat om de prijzen en niet om het soort contract: een vast
contract met dal- en piektarief houdt de oude uitleg, want daar kan bijladen
lonen. Proef 36 in test_batterij.py.

**Wat niet over geld gaat staat erboven**, zoals bij de paal: geen accustand is
standby; een negatieve prijs (de prijs die de bewoner betaalt, en de eigenaar op
21-09-2026: "dit jaar een paar keer voorgekomen") is maximaal laden met
ontladen dicht; de avondpiek blijft dicht voor het net (eis 4); onder de reserve
voor noodstroom komt er niets uit; en **laadt er een paal, dan geeft de batterij
niets af** (`_met_paal`, `_paal_laadt` in coach.py: gemeten aan het vermogen
van de paal en niet aan het besluit van de coach, want in de eerste woning
stuurde iets anders de paal). Sinds v0.87.1 ook aan wat de paal zelf zegt ("auto laadt" bij een
Alfen, "charging" bij een Easee), want het vermogen van een Alfen komt eens per
30 s; en de snelle regelaar past het elke stap toe (`met_paal` in
`_async_regel`) in plaats van op de besluitronde te wachten. In de eerste
woning op 23-09-2026 om 15:59 gaf de batterij daardoor 25 s lang 3,45 kW aan
de auto. Proef 94 in test_coach.py.

**De laadgrens van de batterij is van de batterij.** De eigenaar: "die instelling
van 95% is belangrijk, daar blijft hij continu op staan. Dit is een waarde waar
niet aan gekomen moet worden." De coach leest `charge_limit` en
`discharge_limit` en schrijft ze niet, **met één uitzondering** (v0.74.0, de
keuze van de eigenaar op 22-09-2026): de wekelijkse volle beurt voor het
balanceren (`vol_voor`, `VOL_GEWICHT`) is er voor de cellen, en tot 95%
balanceert niets. Op de dag van die beurt zet de coach de laadgrens op het
maximum van de entiteit (`_async_laadgrens_omhoog`), en zodra de batterij vol
is, de dag om is, de coach niet meer stuurt of stopt, zet hij hem terug op
wat er stond (`_async_laadgrens_terug`, ook vanuit
`_async_batterij_loslaten`). Wat er stond staat in `battery_state` als
`limit_restore`, zodat een herstart het niet vergeet. Alleen op het niveau
sturen; op adviseren blijft de grens met rust. "Vol" voor de opslag
(`full_at`) is dan ook 100 en niet de eigen grens, anders is een batterij die
in de zomer elke middag op 95% staat nooit aan een volle beurt toe. Proef 79
in test_coach.py; scenario `batterij-volle-beurt` (grens om 00:05 naar 100,
om 23:56 op 98,8% terug naar 95).

In het echt gezien in de eerste woning op zondag 27-09-2026: de grens om
00:00:05 van 95 naar 100, de accu om 14:47 op 95%, om 15:07:01 op 100%, en op
diezelfde seconde de grens terug op 95. **Het paneel zei tot v0.103.0 het
omgekeerde** ("Vol is de laadgrens van de batterij zelf; daar komt de coach niet
aan", en bij het veld Laadgrens "verandert het nooit"), en de eigenaar las het
zo op 30-09-2026: "Die moet juist tot 100% voor het balanceren van de cellen,
niet tot de ingestelde max van de accu." Dat deed hij al; alleen de tekst klopte
niet.

**De regelaar**, na de eigen "als je realistisch kijkt verbruik je nooit steady
350 W, hoe zorgen we dat we niet gaan pendelen?" Gemeten in de eerste woning,
waar een andere sturing de batterij toen regelde: 1.713 opdrachten en 233
statuswissels per dag, een dode band van 40 W die de meter 98,9% van de tijd
binnen 50 W hield, een sprong van 2,1 kW die na tien seconden weg was, de meter
elke vijf seconden in Home Assistant en de batterij die een opdracht binnen
vijf seconden volgde. Het pendelen zat rond nul: standby en ontladen om de tien
tot vijftien seconden. Daaruit:

- **Een som en geen versterkingsfactor**: het huis vraagt wat de meter zegt plus
  wat de batterij nu doet, en dat is de nieuwe opdracht.
- **Niet opnieuw corrigeren voordat de vorige te zien is** (`bezonken`,
  `WACHT_OP_BATTERIJ`). Hier komt pendelen vandaan. Te zien is: de batterij
  heeft `VOLGT_NA` gehad om hem uit te voeren, de sensor meldt hem, en de
  meter heeft daarna nog gemeten; hooguit vijftien seconden wachten, de
  keuze van de eigenaar op 22-09-2026.
- **Een dode band** (`DODE_BAND_W`), **groot meteen en klein pas als het blijft**
  (`GROOT_W`, `KLEIN_METINGEN`), **rond nul twee grenzen** (`BEGIN_W`, `STOP_W`)
  en een kleine wens die de richting niet binnen een minuut omkeert
  (`RICHTING_WACHT`).
- **Mikken op de goedkope kant van nul** (`doel_w`): waar terugleveren minder
  opbrengt dan inkopen kost, een halve dode band onder nul.
- **Zwijgt de meter `METER_STIL`, dan gaat de batterij naar 0 W.** Een enkele
  gemiste meting niet: veel integraties melden tussendoor even "niet
  beschikbaar".
- De officiele stuurentiteit van de eerste woning **leest niet terug** wat erin
  geschreven is (hij stond op 0 W terwijl de batterij 2250 W ontlaadde). De
  regelaar leest dus nooit uit die entiteit; hij onthoudt zijn opdracht zelf.

**De sensor is de bevestiging en niet de bron** (v0.74.0). Op 22-09-2026 een
etmaal meegekeken in de eerste woning, waar toen nog een andere sturing de
batterij regelde, met een kWh-meter op de batterij als meetlat. Die sturing
schreef 1.713 opdrachten per dag en slingerde bij elke korte last: zeven
slingers in zes minuten, vijf keer 3.500 W laden met 1 tot 1,9 kW inkoop op
een zonnige ochtend, drie keer ontladen met 1,4 tot 1,7 kW teruglevering. De
oorzaak zat niet in die sturing maar in de sensor: het vermogen dat de
Anker-integratie meldt loopt vijf tot tien seconden achter op de kWh-meter,
toont onderweg een aanloop die er niet is (1040, 1020, 1010, 1000, 940 en dan
pas 2500, terwijl de meter meteen 2580 zag) en vlak na een opdracht soms de
opdracht zelf (0 W terwijl er aantoonbaar 2215 W liep). Wie de sensor bij de
meter optelt telt zijn eigen opdracht dubbel. Drie dingen, alle drie in de
`Regelaar`:

1. **De som rekent met de eigen opdracht** (`vermogen_w`): nieuwe opdracht is
   vorige opdracht plus wat de meter zegt. De sensor telt pas als hij de
   opdracht `AFWIJK_METINGEN` keer achter elkaar tegenspreekt buiten het
   venster na een opdracht, want een batterij die blijvend niet doet wat er
   gevraagd is (vol, leeg, te warm) moet wel gezien worden.
2. **Een aanloop is geen bevestiging.** Alleen een sensorwaarde binnen de dode
   band van de opdracht telt als aangekomen, en pas na `VOLGT_NA`; een sensor
   die twee seconden na de opdracht al "klopt" toont de opdracht en niet de
   meting. Zonder sensor is de meter het bewijs, en dan met dubbele tijd.
3. **Het overschot voor de andere apparaten rekent ook zo**
   (`_batterij_geregeld_w` in coach.py, in `_batterijen_w` en dus in
   `_netto_export_w`): anders ziet de paalplanner bij elke omslag een
   schijnoverschot van de sensor die nog op de oude stand staat.

Het virtuele huis kent daarvoor de sensor van de Anker (`sensor_na_s`,
`sensor_aanloop`, `sensor_echo_s` op `Batterij`, samen `ANKER_SENSOR` in
scenarios.py) en de uurlast van die woning (`Huis.puls`: elk uur veertig
seconden 2,5 kW, een boiler of een warmtepomp zei de eigenaar). Scenario
`batterij-anker-sensor` (de sprong van 3 kW; oud: 241 opdrachten en 118
richtingwissels in een uur, 0,87 kWh van het net; nieuw: 3 en 0, 0,39 kWh,
gelijk aan de eerlijke sensor) en `batterij-uurlast` (oud: 180 opdrachten in
drie uur, slingerend tussen 357 en 3.500 W; nieuw: twee per puls en 0,17 kWh
van het net op een hele dag, de tien seconden aanloop van elke puls). Proef
26 tot 29 in test_batterij.py, proef 80 in test_coach.py.

**"Daarna" is na de bevestiging, niet na de opdracht plus vijf seconden**
(v0.81.1). De eerste nacht met de coach aan het stuur in de eerste woning,
22-09-2026 vanaf 23:21: een last van 2,1 kW die vijf seconden aanstond, een
batterij die de opdracht pas na tien seconden uitvoerde, en toen om :08 de
meter met de oude stand (−2141 W) en om :09 de sensor met de nieuwe (228 W).
`meter_na` eiste alleen een meting van na de opdracht plus `VOLGT_NA`, en
:08 was dat; de regelaar telde −2141 bij 230 op en vroeg 966 W laden, op 12%
midden in de nacht. Daarna elke tien seconden de andere kant op: 1155
ontladen, 195, 1781, 220. De `Regelaar` onthoudt nu wanneer de sensor de
opdracht voor het eerst bevestigde (`bevestigd_op`) en telt alleen een meting
van daarná; zonder sensor blijft het de opdracht plus tweemaal `VOLGT_NA`. De
meter meldt eens per vijf seconden, dus dit kost hooguit één tik. Het virtuele
huis kan dit sinds die nacht nadoen: `Batterij.meter_tik_s` en `meter_fase_s`
(een P1 die om :03 en :08 meldt en daartussen vasthoudt) met stappen van een
seconde. Scenario `batterij-klapperlast` (oud: 286 opdrachten, 143 wissels,
0,86 kWh van het net in een uur op 30%; nieuw: 181, 0, 0,25), proef 30 in
test_batterij.py met de getallen van die nacht. Wat er overblijft is één
opdracht per puls en één terug: de batterij reageert op een puls die allang
voorbij is, en dat is geen slinger maar de vertraging van de batterij zelf.

**Geduld met een last die korter duurt dan de lus** (v0.97.0). In de nacht van
23 op 24-09-2026 ging in de eerste woning om de dertig seconden een last van
490 W tien seconden aan (een broodbakmachine, denkt de bewoner), van 03:50 tot
08:20. De lus via Home Assistant is daar te traag voor: de P1 komt eens per vijf
seconden binnen, de coach schrijft in dezelfde seconde, en de batterij voert
het drie tot acht seconden later uit (de kWh-meter op de accu: 07:44:06 de meter
+468 W en de opdracht 688, 07:44:14 de accu op 681, 07:44:16 de last weg en de
meter -511 W, opdracht 197, 07:44:19 nog 681, 07:44:24 op 194). De regelaar stond
in tegenfase: tot 210 opdrachten per uur, de P1 43% van de tijd binnen 50 W, en
een derde van wat de accu gaf ging naar het net. De bewoner: "je zou ervoor
kunnen kiezen om de accu pas bij te laten springen als een load minimaal 30 of
60 seconden boven een bepaalde waarde komt." De eigenaar: "ja bouw."

Niet altijd wachten, want dat meet slechter: `_geduld` in de `Regelaar` gaat pas
aan als de regelaar net een grote last achterna ging die binnen `KORTE_LAST`
(30 s) alweer weg was (`_tegenfase`), houdt het `GEDULD_DUUR` (een kwartier) vol,
en verlengt het zolang er grote lasten komen en gaan die korter duren. Met
geduld volgt hij van een grote sprong (boven `GROOT_W`) alleen wat er
`VOLG_WACHT` (30 s) lang de hele tijd was; een kleine stap en terug naar nul gaan
zoals altijd. In het virtuele huis, oud tegen altijd wachten tegen geduld na
tegenfase:

| scenario | oud | altijd 30 s wachten | geduld na tegenfase |
|---|---|---|---|
| `batterij-wisselende-last` (490 W, 10 s per 30 s) | 240 opdr/h, P1 43%, 0,20 kWh accu naar net | 1 opdr/h, 66%, 0,01 | 2 opdr/h, 67%, 0,02 |
| `batterij-klapperlast` (2 kW, 5 s per 20 s) | 181 opdr/h, 0,51 kWh accu naar net | 2, 0,02 | 3, 0,02 |
| `batterij-sprong` (oven 3 kW, 20 min) | 0,387 kWh van het net | 0,407 | 0,387 |
| `batterij-uurlast` (2,5 kW, 40 s per uur, een dag) | 0,174 kWh van het net | 0,467 | 0,174 |
| `batterij-vast-zon` (een gewone dag) | 0,076 kWh van het net | 0,084 | 0,076 |

Altijd wachten kost bij elke lange last de eerste halve minuut, en maakt het bij
een last net boven de wachttijd erger: 1000 W, 25 s per minuut, met 20 s wachten
gaf 120 opdrachten en 0,26 kWh accu naar het net, meer dan zonder wachten. Een oven
op zijn thermostaat (45 s aan, 45 s uit) volgt hij met geduld na tegenfase nog
precies zoals vroeger. In geld is het dicht bij quitte: in de wisselende last
gaf de accu 0,25 kWh meer voor 0,065 kWh minder inkoop, dus volgen loont alleen
als een kWh in de accu minder dan acht cent waard is. Het gaat vooral om de
tweehonderd opdrachten per uur. Proef 34 in test_batterij.py, scenario
`batterij-wisselende-last` (`Huis(puls=(490, 10, 0.5))`).

**De batterij doet zelf nul op de meter** (v0.97.0). De eigenaar op 24-09-2026:
"anker mag zelf nul op de meter doen", en erbij: "ook goed voor een vast
contract, want dan heb je niks aan het strategisch inkopen." De Anker van de
eerste woning heeft een eigen P1 die alleen met de batterij praat; in zijn eigen
stand stond hij op 22-09-2026 om 21:24:39 binnen vier seconden op 812 W na een
sprong van 1438 W, en een piek van minder dan vijf seconden liet hij liggen. Dat
kan geen lus via Home Assistant.

Per batterij het vinkje "De batterij doet zelf nul op de meter" (`self_zero` in
`_BATTERY`, websocket.py), alleen bruikbaar met een modus-entiteit en allebei de
modi ingevuld (`_zelf_instelling`). Is het plan gewoon nul op de meter (ook
`auto-helpen`), dan zet de coach hem in `idle_mode` en schrijft hij verder niets
(`_async_zelf_wissel` in coach.py, vanuit `_async_regel`, dus op het tempo van de
meter). Hij neemt het meteen over, op 0 W in `control_mode`, zodra
`_zelf_niet` een reden heeft: een andere stand (laden van het net, handelen,
standby, de paal die laadt), de vakantiestand, geen accustand, de reserve voor
noodstroom als die boven de eigen ondergrens van de batterij ligt, of minder dan
`ZELF_ZEKERING_W` (500 W) ruimte op de krapste zekering in zijn keten. Teruggeven
doet hij pas als dat `ZELF_WACHT` zo bleef: twee minuten sinds v0.102.1, daarvoor
vijf (de eigenaar op 30-09-2026: "zet die 5 min terug naar 2 min"). Allebei de kanten op
eerst 0 W in het register, zodat een overname nooit op een oude opdracht begint.
Elke wissel gaat in de geschiedenis ("doet zelf nul op de meter", "de coach
neemt het over, want de laadpaal laadt"). Iets anders dat stuurt herkent hij
zoals altijd, met de eigen stand als wat de coach zette. Het kasboek en de
rest van de coach (`_batterij_geregeld_w`) rekenen dan met de sensor, want er is
geen opdracht. Bij een herstart gaat hij ook uit zijn eigen stand naar 0 W in de
externe stand, "bij herstart accu op 0 en dan pas kijken". Op de kaart "Wie
regelt: de batterij zelf" (`self_zero` in de stand, `batteryRows`).

**De reden van een overname is wat de bewoner ziet gebeuren** (v0.102.2). De
eigenaar op 30-09-2026 om 12:01:42: "de coach neemt het over, want de zekering
wordt krap", terwijl de fase van de batterij op 4 A stond. De paal had zestien
seconden eerder 16 A toegezegd en nam die nog niet (`_hogere_toezeggingen`), en
daarmee bleef er minder dan `ZELF_ZEKERING_W` over. Is het alleen krap door zo'n
toezegging, dan zegt `_zelf_niet` nu "want de laadpaal gaat laden", of bij een
ander apparaat "want een ander apparaat krijgt de ruimte" (`kaal_w`,
`_paal_belooft`). En de kaart zegt "De batterij doet dat zelf, met zijn eigen
meter" alleen nog als het plan ook nul op de meter is: terwijl de coach op de
stuurknop wachtte stond het die dag een ronde lang achter "De laadpaal laadt,
dus de batterij geeft niets af". Proef 106 en 126.

**Met het vinkje plant de coach ook niets anders** (v0.101.9). In de klantwoning
nam de coach een Anker op 29-09-2026 zelf in handen, zonder het vinkje, met een
dynamisch contract en een P1 die eens per tien seconden meldt. De batterij liet
een opdracht pas na mediaan tien seconden zien (tot 27), en de regelaar hield de
meter maar 6 tot 22% van de tijd binnen 50 W, met ruim honderd opdrachten per
uur; de Anker zelf had die ochtend 4 tot 13% gehaald. Het plan koos daar ook
's middags stilstaan ("vanavond is een kWh meer waard"), en met het vinkje had de
coach hem daarvoor overgenomen. De eigenaar: "de coach moet de batterij niet zelf
sturen ... alleen goedkoop inkopen en de anker stoppen als de laadpaal aan gaat."

Met het vinkje (`Batterij.zelf_nul`) mag de som per blok alleen nog wat de
batterij in zijn eigen stand doet (precies het huis voeden of precies het
overschot opslaan), van het net laden daarboven, en met handelen aan ontladen
daaronder (`_zelf_toegestaan` in `_waarde_vooruit` en `_beste_stap`). Het besluit
van nu is dan nul, van het net laden, handelen of de paal; stilstaan, alleen zon
opslaan en alleen ontladen komen niet meer voor, ook de salderen-standby zonder
rendement niet. De overnames voor de vakantiestand, de reserve, de zekering en een
ontbrekende accustand blijven. In het virtuele huis: `batterij-dynamisch-zelf`
(bewolkt) € 1,49 met 14 opdrachten tegen € 1,48 met 161 als de coach alles stuurt,
twee keer overgenomen om goedkoop bij te laden; `batterij-dynamisch-zon-zelf`
€ -0,54 tegen € -1,01, want hij slaat alle zon op waar terugleveren soms meer
oplevert, en eindigt op 48% in plaats van 39%. Proef 35 in test_batterij.py.

**En het vinkje staat standaard aan** (v0.101.10). De eigenaar op 29-09-2026: "de
coach moet niet meer de batterij sturen, dat vinkje moet theoretisch gewoon
standaard aan staan." Een batterij zonder `self_zero` in de opslag telt als aan
(`_zelf_instelling`), de server vult `True` in (`_BATTERY` in websocket.py) en het
paneel geeft een nieuwe batterij `self_zero: true` mee (`defaultBattery`). Uit is
voor een batterij zonder eigen meter in de meterkast; dan regelt de coach de meter
via Home Assistant, met de `Regelaar` hierboven. Zonder modus-entiteit kan het
vinkje niets en regelt de coach ook. Wat al in de opslag stond blijft staan: in de
eerste woning staat het nog uit (daar stuurt een andere sturing en is "mag sturen"
uit). Proef 119 in test_coach.py (de proeven met de regelaar zetten het vinkje
nu zelf uit) en een proef in test_rapport.mjs.

Het virtuele huis kent `Batterij.eigen_nul` (een eigen lus van 2 s plus 2 s; een
opdracht aan de knop doet hij in die stand niet) en `zelf_nul` (het vinkje).
Scenario `batterij-zelf-nul` (de avond van `batterij-paal-laadt`): de paal begint
om 20:01:15 en de coach neemt het in diezelfde ronde over, de auto is om 04:21
vol en om 04:26 doet de batterij het weer zelf; € 5,21 en 53% aan het eind, net
als wanneer de coach alles regelt, met 4 opdrachten in plaats van 14. Scenario
`batterij-zelf-wisselend`: stond hij nog in de externe stand, dan zet de coach
hem om en schrijft daarna niets meer. Proef 106 in test_coach.py.

**In zijn eigen stand is de stuurknop weg** (v0.100.2). Bij de Anker van de
eigenaar op 28-09-2026: om 11:07:55 naar `self_consumption`, en om 11:07:56 waren
het stuurgetal en de richting `unavailable`. Home Assistant slaat een dienst aan
een onbereikbare entiteit zonder melding over, dus de 0 W die de coach vóór het
overnemen schreef kwam nooit aan: de batterij begon in de externe stand op wat er
nog in het register stond. In het virtuele huis (`Batterij.knop_weg`, scenario
`batterij-zelf-knop-weg`, met 2500 W ontladen van een vorige sturing in het
register) gaf dat de hele nacht 2500 W aan de auto, van 80 naar 5%, met nul
opdrachten: de regelaar dacht dat hij op 0 W stond en had niets te veranderen.
`_async_overnemen_op_nul` in coach.py zet nu bij een weggevallen knop eerst de
stand om, wacht tot de knop er weer is (`KNOP_WACHT_STAPPEN` keer
`KNOP_WACHT_STAP`, samen tien seconden) en schrijft dan de 0 W; met een knop die
er gewoon is blijft het eerst 0 W en dan de stand. Bij het overnemen en bij een
herstart. Proef 112 in test_coach.py.

**En de knop kan langer wegblijven dan de coach wacht** (v0.101.8). In de
klantwoning begon de coach op 29-09-2026 een Anker (Solarbank Max AC, firmware
1.0.1.14) te sturen zonder "zelf nul op de meter": om 15:51:42 naar
`third_party_control`, om 15:51:51 van 1310 W laden naar 0 W en `standby` (in het
register stond 0), en pas om 15:51:56 waren het stuurgetal en de richting er weer,
na veertien seconden. Het wachten van `_async_overnemen_op_nul` hield na tien op, en
het beginnen met sturen zonder dat vinkje zette alleen de modus en schreef de eerste
opdracht meteen naar de onbereikbare knop; Home Assistant meldde "Referenced
entities ... are missing or not currently available" en sloeg hem over. In allebei
de gevallen dacht de regelaar daarna dat zijn opdracht stond. Nu:

- `_async_batterij_zetten` schrijft niets naar een onbereikbare knop en zegt dat
  terug; `_async_overnemen_op_nul` zegt of de 0 W erin staat.
- Kwam een opdracht niet aan, of is de knop na het wachten nog weg, dan onthoudt de
  sessie dat (`nul_open`). De regelaar stuurt dan niets, en zodra de knop er is
  schrijft hij eerst 0 W en begint opnieuw, want wat er intussen in het register
  staat weet hij niet.
- Beginnen met sturen gaat bij een weggevallen knop via dezelfde weg als het
  overnemen; met een knop die er gewoon is schrijft de regelaar in dezelfde ronde
  meteen zijn opdracht, zoals altijd.

In het virtuele huis (`Batterij.knop_terug_s`): `batterij-zelf-knop-traag` gaf met
v0.101.7 160 minuten 2500 W uit de batterij in de bus (6,67 kWh, eindigt op 5%), nu
0,3 minuut en 53%, gelijk aan `batterij-zelf-nul`. `batterij-knop-traag-start` is
het beginnen met sturen. Proef 118 in test_coach.py (acht van de elf controles
vallen om met v0.101.7).

**De batterij helpt de auto met wat er echt over is, en de nachtstrategie**
(v0.90.0). De bewoner van de eerste woning op 23-09-2026, naar evcc: "bij laden van
de auto mag alle batterijcapaciteit boven X% gebruikt worden." De eigenaar: de
nachtbalans gaat voor, want "auto laden vanuit de batterij doe je echt alleen als
er te veel capaciteit over is; in het kader van efficiëntie is het niet top,
namelijk drie keer verlies." Per batterij `battery.car_above` ("De auto mag de
accu gebruiken boven (%)", leeg is nooit); op Strategie `strategy.night_strategy`
(standaard aan): "Coach moet rekening houden met een nachtstrategie, zodat je de
nacht door komt met opgeslagen energie"; uit mag de batterij voor de auto en voor
handelen leeg tot zijn eigen ondergrens. `auto_grens` in batterij.py is de hoogste
van de grens van de bewoner, `bodem` en (met de nachtstrategie aan) de accustand
die de nacht nog nodig heeft (`balans_kwh` terug naar de accukant); weet hij de
nacht niet, dan helpt hij niet. Boven die grens maakt `_met_paal` er nul op de
meter van (`auto-helpen`), en dan komt wat de auto vraagt uit de batterij.
**De grens wordt eens per minuut vastgesteld** (`auto_grens` in de sessie) en de
snelle regelaar gebruikt die, met hysterese: al aan het helpen, dan tot de grens;
opnieuw beginnen pas `AUTO_MARGE` (5%) erboven. Zonder dat schoof de grens met
elke tik mee en zakte hij 's nachts vanzelf, en hielp de batterij in het virtuele
huis zeventien keer een paar minuten (34 wissels, nu 6). Scenario's
`batterij-helpt-auto` (grens 40%: eindigt op 35% in plaats van 53%, de dag
€ 4,07 in plaats van € 5,21), `batterij-helpt-auto-nacht` en
`-zonder-nacht` (grens 10%: 9% met de nachtstrategie, 5% zonder). Proef 32 in
test_batterij.py, proef 98 in test_coach.py.

**Voorrang bij zonoverschot** (v0.92.0). De bewoner van de eerste woning op
23-09-2026, naar evcc: "bepalen prioriteit auto of accu; wie moet als eerste vol
zijn, of tot hoeveel procent. Bijvoorbeeld eerst moet de accu 40% vol zijn, daarna
mag het zonoverschot naar de auto. Niet automatisch de auto voorrang geven op alles
dus." De eigenaar: "helemaal juist", met slepen zoals de kaarten op het overzicht,
en onder Strategie (strategieën zijn een eenmalige instelling, planningen horen
bij de apparaten).

- `strategy.solar_priority`: regels `{device, limit}`, van boven naar beneden.
  `zon_regels` in planner.py (en `zonRegels` in voorrang.js, dezelfde regels)
  vult aan: een apparaat zonder regel komt achteraan zonder grens, in de volgorde
  auto, boiler, batterij, en dat is ook de standaard bij een lege lijst: zo deed
  de coach het. Een boiler heeft nooit een grens (geen temperatuur).
- `zon_rang`: een apparaat staat op de eerste regel waarvan de grens nog niet
  gehaald is (de accustand van de auto, `_auto_soc`, of van de batterij).
- `_zon_correctie` in coach.py is wat de paal (in `_read`) en de boiler (op de
  meter van tien minuten) bij de teruglevering optellen: een batterij die
  ontlaadt is nooit zon; een lagere batterij die laadt wijkt (zoals altijd); een
  hogere batterij onder haar grens die mag laden wijkt niet en haar ruimte gaat
  eraf, zodat de paal wijkt; een lagere paal of boiler wijkt met zijn zondeel
  (verbruik, maar niet meer dan er aan zon was, dus een paal die volgens planning
  van het net laadt maakt voor de boiler geen zon). Een apparaat dat niet in de
  voorrang staat houdt het oude gedrag.
- Het scherm: de kaart "Voorrang bij zonoverschot" op Strategie (`paintZon_`,
  `sleepZon_` in views/strategy.js), met een greep om te slepen, pijltjes, een
  grens per regel, "regel toevoegen" (een tweede regel voor een auto of batterij)
  en "standaard terugzetten".
- **De grens is voorrang, geen eindpunt** (v0.114.1). Het veld heet "eerst tot
  __ %" en de regel zegt "eerst tot 40%, daarna wat er over is" (`regelUitleg` in
  voorrang.js). Ik had op 08-10-2026 voorgesteld hem samen te voegen met "Laden
  tot" van de auto, en trok dat op 12-10-2026 in: dan kan "eerst de accu tot 40%,
  daarna de auto" niet meer. De eigenaar koos "A": allebei houden, met een naam
  die zegt wat hij doet. Waar het laden stopt staat op de kaart, onder Instellen.

Scenario's `voorrang-auto-eerst` en `voorrang-accu-eerst` (heldere dag, bus op
30%, accu op 20%): om 11:00 standaard auto 56% en accu 17%, met de accu eerst tot
50% auto 30% en accu 48%; de bus is in beide gevallen dezelfde dag vol op zon (om
13:38 en 15:18). Die twee scenario's mogen 15 opdrachten per uur aan de batterij
in plaats van 10: de batterij volgt de auto die met de zon meeloopt, met en
zonder de voorrang precies evenveel (171 in veertien uur). Proef 63 in
test_planner.py, proef 99 in test_coach.py, de voorrang in test_rapport.mjs.

**Voorrang bij planningen** (v0.93.0). De bewoner van de eerste woning op
23-09-2026: "stel, er is geen zonoverschot. Eerst de auto (volgens laadplanning);
dan kijk ik naar de accu volgens laadplanning; laadt de accu maar met 3500 W en heb
ik nog ruimte op mijn aansluiting, dan kan ik ook mijn boiler nog vol laden." De
eigenaar: standaard auto, accu, boiler, en het keuzelijstje "wie gaat voor" op de
paalkaart vervalt. Tot dan ging in de praktijk de batterij voor: hij werd eerst
behandeld en laden van het net wijkt niet, en de boiler keek niet naar de
aansluiting.

- `strategy.plan_priority`: apparaat-ids van eerst naar laatst. `plan_regels` in
  planner.py (en `planRegels` in voorrang.js) vult aan in de volgorde auto, accu,
  boiler, palen onderling in hun oude hoog/midden/laag.
- **Toezeggingen** (`_toezeggingen`, `_hogere_toezeggingen` in coach.py): wat elk
  apparaat er de komende minuut bij neemt bovenop wat de meter ziet (een paal zijn
  claim, een batterij die van het net laadt het verschil tot haar vermogen, een
  boiler die aangaat zijn element). Elk apparaat krijgt de ruimte onder de
  zekeringen min wat apparaten **hoger** toezegden: de palen in de ronde via
  `vergeven` plus de batterij en boiler, de batterij in `_laadruimte_w`, de boiler
  ook (die gaat pas aan als zijn element past; zonder gemeten vermogen wordt er
  niet gegokt).
- Een batterij die van het net laadt **wijkt** voor een paal die hoger staat
  (`_batterij_wijkt` met `voor`), en telt dus niet als belasting voor die paal.
- **De klaar-tijd gaat boven de volgorde** (eis 2): een paal in de klaar-tijdregel
  (`_deadline_for`) of te laat (`_te_laat`) krijgt plek -1 in `_plan_voorrang`.
  Zonder dat haalde de auto met de accu bovenaan 96% om 07:00.
- Op Strategie de kaart "Voorrang bij planningen" (`paintPlan_`, `sleepIn_` gedeeld
  met de zonlijst).
- **De warmtepomp en de rest van het huis gaan altijd voor.** De eigenaar op
  23-09-2026: "warmtepomp moet prio 1 zijn, net als in de tweede woning, waar de
  paal geknepen werd omdat de warmtepomp 's nachts aanging; je wilt 's ochtends
  niet in de kou zitten." Dat was het al: wat de coach niet stuurt meet hij als
  huis op de fasen, en hij verdeelt alleen wat er daarna onder de zekering over
  is. Boven beide lijsten staat het nu als vaste regel 0.
- **In de energiestroom staat de thuisbatterij altijd rechts** (`chooseBubbles` in
  components/energy-flow.js), ook als hij stilstaat, met de pijl naar hem toe als
  hij laadt en naar het huis als hij levert; de draaiende apparaten komen onder,
  één met zijn naam of opgeteld. De eigenaar: "die kan bidirectioneel; nu staat de
  accu onder meerdere die verbruiken, maar hij levert."

Scenario's `planning-auto-eerst` en `planning-accu-eerst` (twee goedkope uren, een
grote auto op 50% en een accu op 10%, 3x25 A): om 00:30 laadt de auto 16 A of 7 A,
om 02:00 staat de accu op 23% of 39%, de auto is in beide gevallen op tijd vol en
fase 3 blijft op 23 A. Proef 64 in test_planner.py, proef 100 in test_coach.py
(proef 96 aangepast: standaard wijkt ook een batterij die van het net laadt voor de
auto), de lijst in test_rapport.mjs.

**Het laadrendement is een meting per auto** (v0.94.0). De bewoner van de eerste
woning op 23-09-2026: 78 kWh van 60 naar 90% is 23,4 kWh, "nog te laden is 23,4 in
plaats van 26." De 26 was 23,4 gedeeld door `CHARGE_EFFICIENCY` (90%), en dat is
een aanname. `Car.efficiency` en `rendement_van` in planner.py; in coach.py meet
`_rendement_meten` bij elke nieuwe stand van de accusensor hoeveel procentpunt er
bijkwam tegenover wat de paal in die tijd leverde (`_eigen`), over minstens
`REND_MIN_PROCENT` (tien) en `REND_MIN_KWH` (drie), en alleen een uitkomst tussen
`REND_LAAGST` en `REND_HOOGST`. `_async_rendement_bewaren` houdt per paal en auto
een lopend gemiddelde bij in `car_efficiency` (hooguit vijf beurten). Zolang er
niets gemeten is blijft het 90%, en de pop-up zegt dat: "23,4 kWh in de accu, 10%
laadverlies (aangenomen, nog niet gemeten)". Het bijtellen van een accustand
(`_soc_bijgeteld`, `_typed_soc`) rekent met hetzelfde rendement. Proef 65 in
test_planner.py, proef 101 in test_coach.py.

Dezelfde avond, bij het meekijken, nog twee fouten die met de kaart te maken hadden:

- **Een opgegeven accustand telde niet door aan een Alfen.** Het paneel bewaarde de
  teller van de paal als kale toestand (`coach/soc` in websocket.py), en die telt
  bij een Alfen in Wh: een factor duizend boven wat `_teller` in kWh leest. Het verschil was
  onder nul, dus de proefauto bleef de hele beurt op 60% en "nog te laden" op 26
  kWh. Nu in kWh met de eenheid van de sensor (`to_kwh`), en `_typed_soc` herstelt
  een oude stand die een factor duizend te hoog ligt. Bij een Easee (teller in kWh)
  viel het nooit op. Proef 102.
- **Alleen de paal stuurde zijn besluit naar het paneel.** `EVENT_DECISION` ging
  alleen in `_one` af; een batterij, boiler of vaatwasser kreeg zijn besluit alleen
  bij het openen van het paneel. De accukaart zei daardoor om 23:15 "de coach heeft
  43 minuten niets beslist" en "accu nu 79%" terwijl de accu op 71% stond.
  `_besluit_melden` na elke `_one_batterij`, `_one_programma` en `_one_boiler`.
  Proef 103.

**De batterij en het plan van de auto kennen elkaar** (v0.95.0). De bewoner van de
eerste woning op 23-09-2026 om 22:40: "'wat gaat hij doen' zou nu moeten kijken naar
de EV-laadplanning, en zien dat hij om 23 uur mee moet gaan helpen laden à 3500 W. Aan
de andere kant zou de EV-laadplanning moeten weten dat de accu mee gaat helpen,
mogelijk van invloed op de laadstrategie." Die avond hielp de Anker van 23:00:48 tot
23:17:43 op 3,45 kW, van 78 naar de 70% die de grens was, en geen van de twee
pop-ups wist ervan.

- **Het uurplan van de batterij** (`auto_hulp`, `_met_auto` in batterij.py): het plan
  van de paal gaat mee in `plan_batterij` (`auto_laden`, uit de stand van de vorige
  ronde via `_auto_laden` in coach.py, want de batterij wordt eerst behandeld). Per
  blok dezelfde regels als `_met_paal`: niet als hij zelf van het net laadt, boven
  `auto_grens` (eerst plus `AUTO_MARGE`), op wat er naast het huis over is van het
  ontlaadvermogen, en met de nachtstrategie nooit meer dan wat er morgenvroeg over
  is. `Uur.auto_kwh`, de accustand van de uren daarna zakt mee, `Besluit.auto_weg`,
  en de nachtbalans op de kaart en in de zin rekent ermee ("de auto krijgt er 1,0
  kWh uit"). De grens voor de auto zelf (`nacht_over`, `car_floor`) rekent zonder,
  anders telt de hulp dubbel. Een uur op standby telt ook: bij gelijke prijzen kiest
  het uurplan standby waar de coach die minuut nul op de meter kiest.
- **Het plan van de auto** (`accu_in_plan` in planner.py, `_accu_hulp` in
  coach.py): wat de batterij per blok geeft komt als `accu_kwh` bij de blokken van
  de paal, nooit meer dan wat er van het net zou komen. De pop-up zegt "Laden op
  9,0 kW, waarvan 1,0 kWh uit je thuisbatterij", een vak "Uit je thuisbatterij, tot
  hij op 70% staat", en de prijsgrafiek telt het niet als net. "Nog te laden" zegt
  nu "in de auto" in plaats van "in de accu", want die pop-up kent nu twee accu's.
- **Welke uren de auto kiest verandert niet.** De batterij maakt geen uur goedkoper
  dan een ander; wat verandert is hoeveel er van het net komt. Dat is het antwoord op
  "mogelijk van invloed op de laadstrategie".
- **Op de duurste laaduren eerst** (v0.104.1). Tot dan hielp hij zodra de paal laadde,
  tot zijn grens, dus op het eerste laaduur. De eigenaar op 30-09-2026 om 23:48, bij het
  plan van de eerste woning (laden om 00:00 voor € 0,319, 02:00 voor € 0,326, 04:00 voor
  € 0,325, en 2,3 kWh uit de batterij om 00:00): "hij pakt het goedkoopste uur om te
  ondersteunen. Eigenlijk moet hij meehelpen op de duurste momenten, om daar de
  financiële pijn het meest te verzachten." Nu verdeelt `auto_hulp` de hulp over de
  laaduren van duur naar goedkoop: elk krijgt wat er naast het huis van het
  ontlaadvermogen over is en wat de batterij aan het eind van dat blok boven de grens
  heeft, zonder dat een later blok dat al hulp kreeg eronder zakt. Het huis mag daarna
  gewoon verder uit de batterij; de grens is er voor de auto. Beginnen pas `AUTO_MARGE`
  boven de grens, bij gelijke prijzen het vroegste eerst, zoals het was.
  **En de regelaar volgt het plan** (`Besluit.auto_hulp_nu`, `_met_paal`): laadt de paal
  volgens zijn plan in een blok zonder hulp, dan geeft de batterij niets af, en de kaart
  zegt "De batterij helpt de auto om 02:00, op een duurder laaduur, en geeft nu niets
  af" (`auto_hulp_om`). Laadt de paal buiten zijn plan (Snel, of een andere sturing zoals
  evcc in de eerste woning), dan helpt hij zoals altijd boven de grens. De vier
  hulpscenario's in het virtuele huis (vast contract, overal dezelfde prijs) geven
  precies hetzelfde als daarvoor. Een dynamisch scenario lukte niet: de accu laadt dan
  's nachts zelf goedkoop bij, en in zo'n uur helpt hij terecht niet. Proef 39 in
  test_batterij.py (de nacht van de schermafdruk: alles om 02:00, en 1,91 kWh is precies
  wat er boven 50% over is).

Gemeten in het virtuele huis, plan vlak voor het laden tegen wat de auto kreeg:
`batterij-helpt-auto` 2,90 tegen 3,01 kWh, `-zonder-nacht` 5,78 tegen 5,83. Met de
nachtstrategie (`-nacht`) 4,05 tegen 5,60: de grens zakt 's nachts als het huis minder
vraagt dan verwacht, en dan belooft het plan minder dan er komt, nooit meer. Proef 33
in test_batterij.py, proef 66 in test_planner.py, proef 104 in test_coach.py, de
teksten in test_rapport.mjs, `accu_plan_kwh` en `bat_auto_plan_kwh` in de `Regel` van
het virtuele huis.

**Gaat de coach weg, dan gaat de batterij terug** (`_async_batterij_loslaten`):
vermogen op nul en `idle_mode` in de modus. Ook als het vinkje "mag sturen" eraf
gaat of het niveau naar adviseren. Dezelfde gedachte als de stroom terug op de
boiler.

**Ook bij een herstart van Home Assistant** (v0.82.0). Bij een herstart roept
Home Assistant `async_unload_entry` niet aan, dus `async_stop` ook niet; er
komt alleen het event `homeassistant_stop`, en daar bewaarde `_async_bij_stop`
tot 23-09-2026 alleen de lopende beurten. In de eerste woning bleef de batterij
daardoor bij de herstart voor v0.81.1 (23-09-2026 om 00:44) gewoon 235 W
ontladen in de externe modus tot de coach twee minuten later terug was, en een
boiler was zonder stroom gebleven. `_async_bij_stop` geeft nu zelf de
batterijen terug en zet de boilers aan, en wacht daarop, want een taak die bij
het afsluiten nog in de wachtrij staat wordt niet meer gedraaid. Proef 79d in
test_coach.py. **In het echt nog niet gezien**: of de integratie van de
batterij op dat moment de opdracht nog aanneemt blijkt bij de volgende
herstart in de eerste woning.

**Maar bij een herstart blijft hij in de externe modus, op 0 W** (v0.96.0). In de
eerste woning ging de batterij bij de herstart van 23-09-2026 om 23:53 netjes naar
eigen verbruik, en daar doet de Anker zelf nul op de meter: met een Tesla die 9 kW
trok gaf hij 3,45 kW aan de auto, tot de coach om 23:55:13 terug was (70 naar 69%).
De eigenaar: "bij herstart accu op 0 en dan pas kijken." `_async_bij_stop` zet hem
dus op 0 W en laat de modus staan (`herstart` in `_async_batterijen_los` en
`_async_batterij_loslaten`); na de herstart neemt de coach het gewoon weer over.
Het uitzetten van de integratie (`async_stop`) geeft hem wel terug aan zijn eigen
stand, want dan komt de coach niet terug. Proef 79d.

**Na een herstart houdt de coach een ladende auto nog tien minuten vast.** Dezelfde
nacht om 00:02 vroeg de eigenaar "waarom laadt hij nu 6 A terwijl hij later
goedkoper is": de coach zag na de herstart een auto die al laadde, en `_keep_alive`
in planner.py houdt een beurt die net begonnen is `MIN_RUN_MINUTES` op de ondergrens,
en stopt pas na `STOP_ROUNDS` ronden "stop" achter elkaar. De coach weet na een
herstart niet hoe lang de auto al laadde (`_since` begint opnieuw), dus telt hij hem
als net begonnen. Zo bedoeld: een auto die aan en uit gaat stopt soms helemaal met
luisteren.

**De knoppen van de batterij hebben eigen iconen** (v0.82.0): "Nu vol laden"
een accu met een pijl erin (`accuVol`), "Nu leegladen" een accu met een pijl
eruit (`accuLeeg`), en de paal houdt de bliksem (`data-boost-icon` in
overview.js). De eigenaar op 23-09-2026: het pauzeteken bij leegladen klopte
niet.

**De batterij vervalst de meter voor de andere apparaten.** Wat hij opslokt is
geen huisverbruik maar zon die ook naar de auto had gekund, en wat hij afgeeft
is geen zon. `_batterijen_w` telt het terug in `_netto_export_w` en in `_read`;
`_async_huisverbruik` trekt een batterij met zijn teken van het huis af, en het
paneel doet dat in `data-source.js` (`batteryWatts`). De auto laadt op zon
zonder verlies en de batterij verliest een kwart, dus de andere apparaten gaan
voor; de batterij krijgt vanzelf wat er daarna over is.

**Het kasboek.** `verdiend` is per stap het verschil tussen de rekening zoals
hij loopt en zoals hij zonder batterij gelopen had (de meter min wat de batterij
doet); het rendement zit er vanzelf in. Het gaat per dag naar `battery_state` in
de instellingen, en staat als "Opgeleverd" op de kaart (`earned` in de stand van
de coach) en als "Door je thuisbatterij" onder In geld in Historie. Wat de
batterij verdiende voordat de coach erbij kwam wordt niet geschat. Naast het
kasboek telt de coach sinds v0.101.2 wat de zon die erin ging minder waard was
dan zelf gebruikt (`zon_in_accu`, `solar_stored_days`), zodat Historie de zon
niet meer als rest hoeft te rekenen; zie `docs/eerste-woning.md` onder In geld. Een
aankoopprijs en een terugverdientijd stonden er van v0.73.0 tot v0.101.1; zie
`docs/eerste-woning.md` onder In geld waarom ze eruit zijn.

**Laden is inkopen (v0.107.0).** De eigenaar op 05-10-2026, bij "Opgeleverd € 0,74
in 8 dagen" op de kaart thuis: "dat geld fluctueert telkens en klopt niet, waar
wordt dat vandaan gehaald? Komt ook niet overeen met de historie." Het kasboek
rekent laden af op het moment zelf (van het net de inkoop, uit de zon wat
terugleveren had opgebracht, met salderen bijna de hele prijs) en ontladen
levert het later terug, dus zakte "Opgeleverd" elke dag terwijl de batterij
laadde. In het virtuele huis (`batterij-dynamisch-winter`, dinsdag): 09:00
€ 1,39, 17:00 € 0,85, 23:00 € 2,69, voor een dag die € 1,45 opleverde. En de
kaart telde alle dagen plus vandaag tot nu, Historie alleen de gekozen periode.
Op de schermafdruk van de eigenaar was het deel van de batterij in de week
ongeveer € 1,9 (afgelezen van de balk), tegen € 0,74 op de kaart.

Nu houdt de coach naast het kasboek een voorraad bij (`Voorraad` in
batterij.py): wat laden kostte gaat erin, en bij ontladen gaat er een deel uit,
zoveel als wat eruit komt van wat er boven de ondergrens nog uit kan
(gemiddelde kostprijs). Wat er nog uit kan komt bij elke nieuwe accustand uit
die stand en de inhoud, met het rendement voor het verlies; daartussen telt hij
de kWh zelf. Niet per procent afrekenen: de accustand komt in hele procenten, en
zo gerekend zakte het bedrag op proef 41 bij de eerste stap na het laden 2,7
cent onder nul. Wat ze opleverde staat per dag in `realized_days` (en
`realized_total`), wat er nog in zit in `stock_euro`, allebei in
`battery_state`, naast het kasboek. Opgeleverd min wat er nog in zit is altijd
het kasboek; leeg is het precies het kasboek. Een dag van voor v0.107.0 telt
zoals hij geteld is (`_opgeleverd_dagen`), en wat er al in zat toen de coach
begon te tellen kostte niets, net als in het kasboek.

Op de kaart: "Opgeleverd" uit `realized_total` (`opgeleverdTekst` in
battery.js). Tot v0.118.1 stond eronder "Wat erin zit: ingekocht voor € 0,55"
(`stock_euro` in `earned`); de eigenaar op 14-10-2026, bij "ingekocht voor
€ 2,02" met een vast contract waarin alles zon was: "snap ik nog niet
helemaal", en daarna weghalen. `stock_euro` blijft in `earned` en in de
opslag, want Historie en de sommen hebben hem nodig. In
Historie telt Door je thuisbatterij wat ze opleverde, en staat wat er in de
periode in de batterij bij kwam onder Uitgegeven ("Waarvan nog in je batterij",
of "En uit je batterij, eerder betaald"); zonder trekt het eraf, zodat dat
blijft wat het gekost had zonder batterij (`accuVerdiend` en `balans` in
geld.js). Met salderen laat opgeleverd thuis na het ontladen eerlijk een klein
min zien: zon erin kost bijna de hele prijs, en het verlies is er echt.

Nagemeten in het virtuele huis: dinsdag blijft de kaart de hele laaddag (09:00
tot 17:00) op € 1,40 staan terwijl de voorraad van € 0,01 naar € 0,55 loopt, en
om 23:00 staat er € 2,88 met € 0,19 in de batterij (kasboek € 2,69). Elk
batterijscenario in test_virtueel.py controleert nu dat opgeleverd min de
voorraad het kasboek is, en dat de kaart niet zakt terwijl de batterij laadt.

In het paneel: het type thuisbatterij staat er weer in (`DEVICE_TYPES`; het is
uit `VERVALLEN_TYPES`), merken Anker en Overig met dezelfde velden
(`BATTERY_FIELDS` in devices.js), de instellingen van de bewoner in
`batteryHtml_` (views/devices.js, `battery` op het apparaat, `_BATTERY` in
websocket.py), en de regels op de kaart in `battery.js`.

Het virtuele huis heeft een `Batterij` die een opdracht na vijf seconden
uitvoert en daarna vasthoudt, zoals een batterij in externe sturing doet.
Zestien scenario's `batterij-*` in scenarios.py, met per scenario het aantal
opdrachten, de richtingwissels, en de kosten van de dag met en zonder batterij.
Wat eruit kwam en gerepareerd is: het klapperen in het randuur, en een waarde
die vlak onder de laadgrens een achtste te laag uitkwam, waardoor de batterij op
een zonnige dag op 93% bleef staan. test_batterij.py, proef 75 tot 80 in
test_coach.py, en de batterijproeven in test_rapport.mjs.

**Nog nooit aan een echte batterij gehangen.** Wat er in het echt anders kan
zijn: in welke volgorde vermogen en richting geschreven moeten worden (ze delen
bij Anker een register), wat de batterij doet als Home Assistant zelf vastloopt
terwijl er een opdracht staat, of `BEGIN_W` en `STOP_W` bij de echte omvormer
passen, en of het opgegeven laadvermogen klopt. Eerst meekijkend installeren
(niveau adviseren), dan pas sturen. Wat wél al aan de echte woning gemeten is
(22-09-2026): de P1 elke vijf seconden, de batterij die een opdracht binnen
vijf seconden volgt, de sensor die vijf tot tien seconden achterloopt, de
accustand per procent om de vijf minuten, een nette herstart van Home
Assistant (de andere sturing zette eerst 0 W, dertig seconden stil, daarna
weer verder), en de omvormer van de zon die 's nachts onbereikbaar is
(`_zon_slaapt` geldt daar ook).

**De coach leest elke vorm van prijslijst die het paneel ook leest** (v0.74.1).
De eerste dag op sturen in de eerste woning (22-09-2026) stond er de hele dag
"de prijs van dit uur is niet bekend": het contract was dynamisch met Zonneplan,
en die integratie geeft zijn lijst als `forecast` met alleen een `datetime` en
een `electricity_price` in tienmiljoensten van een euro (3355224 naast een
toestand van 0,3355224 €/kWh), terwijl `_slots` alleen `prices` met `from`,
`till` en `price` kende (Frank Energie). `_prijsrijen` in coach.py leest nu
dezelfde vier vormen als `readSchedule` in data-source.js: Frank Energie, Nord
Pool (`raw_today`/`raw_tomorrow`), Tibber en EnergyZero (`data`) en Zonneplan
(`ZONNEPLAN_DELER`). Een blok zonder eindtijd loopt tot het volgende blok, het
laatste blok is even lang als het blok ervoor, en zonder blok ervoor zo lang
als het contract zegt; paneel en coach houden daar dezelfde regel voor. **Houd
die twee lijsten gelijk.** En dezelfde sensor als all-in én als marktprijs
ingevuld maakt de terugleveropbrengst onbekend in plaats van gelijk aan de
inkoopprijs; het formulier zegt dat erbij. In de energiestroom wijst de pijl
van een ontladende batterij nu naar het huis (`batteryWatts < 0` in
energy-flow.js); de bewoner zette er een rode kring om. Proeven bij de
prijslijst in test_coach.py (na de datetime-proef) en in test_rapport.mjs.

**Een reserveprijssensor, en de ingebouwde Nord Pool** (v0.101.3). Bij de
eigenaar op 29-09-2026 gaf de integratie van Frank Energie "Graphql validation
error" (Frank had iets aan zijn kant veranderd) en stonden al zijn sensoren op
`unavailable`. De eigenaar: "Ik heb ook Nord Pool draaien. Dat wil ik als
fallback hebben, zodat als Frank eruit ligt dat hij dat oppakt, en is Frank weer
terug dat hij dat weer pakt." Onder het dynamische contract staan daarvoor twee
velden: `fallback_entity` en `fallback_source` (marktprijs of all-in). De eigen
prijsbron telt zolang hij een prijs voor dit moment heeft; anders de reserve,
en een marktprijs krijgt dezelfde belasting, opslag en btw als altijd. Er wordt
niet gemengd. Zie `_prijsbron` in coach.py; de sensorwacht zegt dan "de coach
rekent zolang met je reserveprijzen" in plaats van "zonder", en bewaakt de
reserve zelf ook. Na een herstart valt de terugrekening op de reserve terug als
de eigen sensor in dat venster niets gaf (`_async_reserveverloop`).

De ingebouwde Nord Pool van Home Assistant hangt geen lijst aan zijn sensoren,
anders dan de Nord Pool uit HACS (`raw_today`). Hij geeft hem alleen via de
dienst `nordpool.get_prices_for_date`: bij de eigenaar 96 kwartieren per dag,
in euro per MWh (195,3 voor € 0,1953 per kWh), en morgen pas rond 13:00.
`_async_nordpool` haalt vandaag één keer op en morgen vanaf 12:00 tot hij er is,
hooguit eens per tien minuten; config entry, gebied en munt uit de
entiteitregistratie (`platform` nordpool, unieke id "NL-current_price"). Dat
werkt voor Nord Pool als eigen marktprijs én als reserve.

Het paneel leest een lijst uit de attributen, en daar staat van de ingebouwde
Nord Pool niets. Daarom geeft de coach zijn lijst via `domotiapp_coach/prices`
(`_prijzen_voor_paneel`), en tekent het paneel die zodra de reserve invalt of de
sensor zelf geen lijst heeft (`laadCoachPrijzen`, `priceForecast`, `priceNow`
en `tariff` in data-source.js). Historie vult een uur zonder prijs van de eigen
sensor aan met de statistieken van de reserve (`allInPrijzen`); daarbij bleek
dat Historie bij een marktprijssensor de kale beursprijs als inkoopprijs nam,
zonder belasting, opslag en btw. Dat is in dezelfde uitgave rechtgezet.
Proef 115 in test_coach.py, drie proeven in test_rapport.mjs.

**Wat een apparaat uit de batterij kreeg staat in zijn verslag** (v0.101.0). Bij de eigenaar
op 28-09-2026: een vaatwasser van 0,908 kWh kreeg 0,329 van de zon, 0,553 uit de
Anker en 0,026 van het net, en het verslag zei "ongeveer € 0,199, bespaard € 0,018,
allemaal door de zon". De eigenaar: "moet daar niet iets van de batterij bij? er is
niks van het net af gehaald." `_uit_accu` in coach.py verdeelt wat niet van de zon
kwam over batterij en net naar rato (afgifte tegen inkoop op de meter),
`_herkomst_bij` telt het per ronde bij elke paal, vaatwasser en boiler, en de beurt
bewaart `battery_kwh` en `grid_cost`. **Het geld verandert niet**: het deel uit de
batterij telt in de beurt als netstroom, want de winst ervan staat in het kasboek
van de batterij, en In geld in Historie telt ze samen zonder iets twee keer.
Onder salderen levert dat deel weinig op: een kWh uit de batterij is eerder
opgeslagen zon die anders voor de prijs min de terugleverkosten was teruggekomen.

**Waarom eigen zon zo weinig scheelt, staat erbij zolang je saldeert** (v0.101.4).
Bij de eigenaar op 29-09-2026: "0,9 kWh. 0,7 kWh kwam van je zon en 0,2 kWh uit je
thuisbatterij. Bespaard € 0,036, allemaal door de zon." De eigenaar: "hoe kan je dan
uitkomen op 0,036 bespaard, je hebt dan toch alles bespaard? 0,24171 betaal ik per
kWh." Nagerekend: maat 0,906 × 0,24171 = € 0,2189, betaald 0,678 × 0,188954 (zon,
teruggeleverd waard) + 0,215 × 0,24171 (batterij, telt als net) + 0,013 × 0,24171 =
€ 0,1832, bespaard € 0,0357 = 0,678 × 0,052756. Klopt dus, maar de zin legde het
niet uit. Nu: "Bespaard € 0,036 door de zon: zolang je saldeert scheelt een eigen
kWh alleen de terugleverkosten." Bij een dynamisch contract "de opslag en de
terugleverkosten", na het salderen niets erbij (`_zon_scheelt`, `_bespaard_zin`
in coach.py, voor paal, vaatwasser en boiler; proef 116). Vanaf 1-1-2027 bespaart
dezelfde beurt 0,678 × (0,24171 − 0,0193) = ongeveer € 0,15 door de zon.

**Die uitleg is er sinds v0.102.1 weer uit, met de hele uitsplitsing.** De
eigenaar op 30-09-2026, over een laadverslag van vijf zinnen: "deze tekst is veel
te lang, moet korter en overzichtelijker. Op de telefoon past die melding niet."
Een verslag is nu een paar korte regels (`_verslag` in coach.py) en de laatste is
alleen het bedrag: "Bespaard € 0,036." `_zon_scheelt` bestaat niet meer. De som
hierboven klopt nog steeds; wat de zon scheelde staat in het paneel onder Bespaard
("Door zon"). Zie `docs/laadpaal.md`, "Het verslag is vier korte regels".

## De paal stopt: wachten op een meting van daarna

v0.102.2. De eigenaar op 30-09-2026, met de batterij door de coach overgenomen
zolang de auto laadde. Om 13:39:53 zei de meter 7.338 W afname, midden in het
afbouwen van de auto; om 13:39:54 meldde de paal "completed" en 0 W, en in
diezelfde seconde draaide de ronde. Het besluit werd weer nul op de meter, de
regelaar rekende met de meterwaarde van een seconde eerder en zette de batterij
op ontladen op vol vermogen (3.500 W), terwijl er 1 kW zon over was. De meter
van 13:39:55 zei al 1.020 W teruglevering. De batterij volgde om 13:40:02, van
13:40:04 tot 13:40:08 ging er 4,2 kW het net op, en daarna hield ze er zelf mee
op. De regelaar zakte in stappen van een kwartminuut terug (2.033, 782, 0 W),
zag zijn eigen sprong aan voor een korte last en kreeg er geduld van
(`_tegenfase`); laden op de zon begon pas om 13:41:10.

Stopt een paal, dan telt hij voor de batterij nog als ladend tot de meter een
waarde gaf van meer dan `PAAL_UIT_WACHT` (vijf seconden, de `VOLGT_NA` van een
batterij) na het laatste moment waarop hij laadde (`_paal_net_uit` in coach.py,
vanuit `_async_regel`). Op een kopie van het besluit, zodat het besluit van de
ronde blijft wat het is. Een meter die zwijgt houdt dat niet vast: na
`PAAL_UIT_LANGST` (een halve minuut) geldt het besluit weer, en dan zet de
regelaar de batterij zelf op nul (`METER_STIL`). Geldt net zo voor een paal die
de coach zelf stillegt of die een lastbewaker pauzeert, en voor een batterij die
zelf nul op de meter doet: die krijgt haar eigen stand dan vijf seconden later
terug.

In het virtuele huis (`batterij-paal-stopt`, een meter die eens per vijf
seconden meldt en een ronde in de seconde dat de paal stopt,
`Scenario.ronde_bij_status`): acht seconden 2,25 kW het net op werd niets, en
acht seconden na het stoppen voedt de batterij het huis. Proef 125 in
test_coach.py.

## Een beurt van het net loopt door, en een kleine is geen overname

v0.102.3. In de klantwoning op 30-09-2026, een Anker die zelf nul op de meter
doet en een dynamisch contract in kwartieren. Twee dingen uit de recorder:

- **Overdag laadde hij elk kwartier twaalf minuten en drie niet.** Van 10:45 tot
  14:27 steeds "laadt op 3,5 kW" op :x0:40 en "nul op de meter" op :x2:40.
  `_rustig_vermogen` begon niet aan wat er in dit blok nog bij moest als dat
  minder was dan een procent van de batterij (0,145 kWh), en 3,5 kW maal de
  laatste 2:20 van een kwartier is 0,136. Met uurprijzen speelde dat een paar
  minuten per uur, met kwartierprijzen elk kwartier.
- **'s Nachts laden en ontladen door elkaar.** Van 03:15 tot 06:00 ging er per
  uur 1,40/1,97/0,50 kWh in en 0,37/0,17/0,45 uit. De accustand liep sneller
  op dan het plan dacht, het restje van het kwartier zakte onder de procent,
  en het besluit werd nul op de meter. De coach had de batterij in handen, en
  zijn eigen regelaar dekte toen de warmtepomp (2,4 kW) uit de batterij: om
  03:26:30 3.500 W eruit, om 03:27:25 weer 3.500 W erin. Elke tik van de
  accustand (8 ↔ 9%) wisselde het.

En met `ZELF_WACHT` van twee minuten (v0.102.1) werd dat erger: drie rondes
"nul" aan het eind van een kwartier (met rondes op :40) is teruggeven en een
minuut later weer overnemen, elk kwartier.

Nu:

- **Of hij begint gaat over de hele beurt** (`_rustig_vermogen`): deze even dure
  blokken plus de blokken erna waarin het plan ook van het net laadt, wat ze ook
  kosten. De procent blijft, maar dan over die beurt.
- **Een beurt die loopt maakt hij af** (`Batterij.vorige_stand`): zolang het plan
  in dit blok nog iets van het net wil, hoe weinig ook. Dan houdt hij de
  batterij vast en neemt het huis van het net ("Hij maakt het laden van het net
  af tot 05:45 en geeft tot dan niets af").
- **Met het vinkje zelf nul is van het net laden minstens één stap van het
  rooster, of zoveel als er in het blok nog kan** (`_zelf_toegestaan`). De som
  kent daar geen stilstaan, en koos voor stilstaan het eerstvolgende
  roosterpunt erboven: "laden van het net, 0,01 kWh" om 21:45 midden in een
  avond ontladen. Dat is een overname om stil te staan, en die wil de eigenaar
  niet ("de coach moet de batterij niet zelf sturen ... alleen goedkoop
  inkopen"). In het blok waarin hij al laadt mag het restje kleiner
  (`_loopt_al`), want een procent is 0,145 kWh en een stap 0,33: anders stopte
  hij na elke tik. In het blok erna weer niet, zodat hij hem niet blok na blok
  vasthoudt.
- **Voor een kleine beurt neemt hij een batterij die het zelf doet niet over**
  (`_overname_drempel`, `Batterij.overgenomen`): minstens één stap van het
  rooster aan de wisselstroomkant, bij 14,5 kWh 0,38 kWh. Die dag nam hij hem om
  16:00:41 over voor drie minuten op 1,2 kW, en om 15:00:41 voor een plan van
  0,35 kWh. Heeft de coach hem al, dan geldt de procent.

In het virtuele huis (`batterij-kwartier-zelf`, de kwartierprijzen van die dag,
rondes op :40, een warmtepomp van 1,6 kW van 03:00 tot 06:00): met v0.102.2
44 wissels van de modus, 160 opdrachten en tien kwartieren met laden én
ontladen; nu 8 wissels (vier echte beurten: 04:15:40, 10:45:40, 11:15:40 en
14:00:40), 73 opdrachten en één zo'n kwartier, aan het eind van de nachtbeurt.
Het virtuele huis kent daarvoor dagen met 96 prijzen (`Prijzen.per_dag`).
`batterij-dynamisch-zelf` (uurprijzen) kost nu € 1,51 met 11 opdrachten, was
€ 1,49 met 14, tegen € 1,50 als de coach alles stuurt.
Proef 37 in test_batterij.py, proef 129 in test_coach.py.

**Ook niet vlak onder de bovengrens** (v0.103.0). De eigenaar op 30-09-2026 om
22:42, bij de uurlijst van de eerste woning (77%, overal "nul op de meter" en om
02:00 "laden van het net, 0,1 kWh"): "Waarom koopt de accu heel iets van het net?"
Nagebouwd met de echte prijzen: de som waardeert wat er aan het eind van de
bekende prijzen nog in zit tegen hun gemiddelde (€ 0,368), de nacht kost
€ 0,319-0,335, dus hij staat 's nachts liever stil dan dat hij het huis voedt.
Stilstaan kan niet met zelf nul, en v0.102.2 koos het eerstvolgende
roosterpunt: om 02:00 lag dat 0,097 kWh boven de inhoud, € 0,0037 goedkoper in
de som. v0.102.3 vroeg een stap, "of zoveel als er in het blok nog kan", en dat
laatste gold ook voor de 95%: over 1.320 plannen (accu 30-95%, vier tijdstippen)
tien keer 0,14-0,20 kWh bijvullen, allemaal op 94 of 95%. Nu telt alleen de tijd
in het blok als "wat er nog kan" (`op_blok` in `_zelf_toegestaan`), niet de
grens van de accustand: nul keer. Het restje van een kwartier dat bijna om is
mag wel, anders stopt een beurt elk kwartier te vroeg (proef 37). Proef 38 in
test_batterij.py doet de 264 plannen van die avond na; op v0.102.3 valt hij om
op 94 en 95%.
Wat het elders deed, gemeten over de negen batterijscenario's met zelf nul of
handelen: alleen `batterij-kwartier-zelf` verandert. De nachtbeurt begint om
03:45 op 1,6 à 2 kW in plaats van om 04:15 op 3,5 kW en haalt 10,1 in plaats van
9,5 kWh; de dag kost € 2,48 tegen € 2,35 en hij eindigt op 13 in plaats van 10%
(0,44 kWh meer over). 9 wissels van de modus, net als eerst; de opdrachten
(100 tegen 73) zijn de vermogensstappen van het rustige laden.

**Wat er overblijft:** slaat het plan één kwartier over (13:45 in dat scenario,
€ 0,257 tussen € 0,230 en € 0,236), dan geeft hij hem na `ZELF_WACHT` terug en
een kwartier later weer over. Dat is het plan zelf, en twee minuten is de keuze
van de eigenaar.

## Bijkopen loont onder, op de kaart en in de nachtzin

v0.102.3. De eigenaar op 30-09-2026 om 19:45, met "Een kWh erin € 0,301, is
straks waard", 8,1 kWh tekort voor de nacht en "Van het net: niets": "hij komt
te kort, is het niet goedkoper om iets bij te kopen?" Die € 0,301 was `eraf`:
wat een kWh **in** de batterij waard is. Naast de prijslijst hoort die min het
verlies bij het laden, maal √0,736: € 0,259 (`Besluit.inkoop_tot`, `erbij`
maal `eta`, dezelfde grens als waar hij zon opslaat). Het vak in de pop-up
heet nu "Bijkopen loont, onder € 0,259, nu € 0,446" (`buy_below` in de stand,
`batterijVooruit` in battery.js). Bij een volle batterij staat het er niet.

En de nachtzin eindigde bij een tekort altijd met "hij laadt bij als de stroom
goedkoop genoeg is". Nu zegt hij wat het plan tot morgenvroeg van het net haalt
("hij laadt er 3,1 kWh van op de goedkoopste momenten van het net bij, de rest
komt rechtstreeks van het net"), of waarom niet: "dat komt van het net, want
bijladen kost via de batterij minstens € 0,425 per kWh (€ 0,313 om 00:15, plus
het verlies)", de goedkoopste prijs tot morgenvroeg gedeeld door het rendement
(`_bijladen_zin`). Reiken de prijzen niet tot morgenvroeg, dan staat er "in de
bekende uren" bij. Eén zin, want de kaart toont alleen de laatste
(`nachtConclusie`).

## Geen handelen zonder terugleverprijs (v0.106.2)

In de eerste woning op 03-10-2026 stond de batterij van 09:00 tot 12:01 drie keer op
"handelen. Terugleveren brengt nu € 0,000 op". De marktsensor is daar de all-in sensor,
dus wat teruglevering oplevert is onbekend (`_prices` in coach.py geeft dan `feed_in`
None), en `_kosten` telt het als nul. De dag had meer zon dan er in de batterij paste
("van die zon past 6,7 kWh niet meer in de accu"), dus voor de som was zon nu opslaan
even veel waard als straks. Stilstaan mag niet als de batterij zelf nul doet
(`_zelf_toegestaan`), en bij gelijke kosten wint in `_beste_stap` het kleinste gebaar:
één stap naar het net (0,33 kWh) was kleiner dan de ochtendzon opslaan.

Gemeten: 4,57 kWh zon naar het net (P1 export 09:00 tot 12:00), de batterij bleef op
21% en gaf er 0,48 kWh aan het net bij. Om 12:16 kwam de auto en die gaat voor, dus die
zon kwam er die dag niet meer in. Om 13:22 nog eens: de kabel was een minuut uit de
auto, en meteen leverde de batterij 200 W aan het net terwijl er 3,8 kW zon heen ging.

Nu mag de batterij alleen aan het net leveren in een blok met een bekende
terugleverprijs (`_mag_handelen`, in `_mogelijk` en `_zelf_toegestaan`). Zonder valt hij
terug op nul op de meter en slaat hij de zon op. Met een bekende terugleverprijs
verandert er niets: met € 0,05 koos dezelfde som de ochtendzon al op te slaan, en een
avond met een prijs die hoger is dan de nacht wordt nog gewoon verhandeld. Proef 40 in
test_batterij.py (valt om met v0.106.1). Een echte terugleverprijs krijgt de coach met
een marktsensor die niet de all-in sensor is; het paneel zegt dat bij de prijsbron.

## Handelen zonder terugleverprijs: het scherm zegt het (v0.128.2)

De bewoner van de eerste woning op 18-10-2026, met de batterij op 95%, "7,1 kWh over" tot
morgenvroeg en een avond van 17:45 tot 20:15 boven de 45 cent: "Het enige waar ik op dit
moment nog niet echt tevreden over ben is het handelen (of eigenlijk het ontbreken ervan)."
Handelen stond aan, maar in beide prijsvelden stond dezelfde all-in sensor en salderen stond
uit. Dus was `feed_in` None in alle 50 blokken, liet `_mag_handelen` nooit iets naar het net
gaan (v0.106.2), en zei de kaart alleen "Hij houdt de meter op nul". Dat het marktveld niet
telde stond in de kleine letters erboven, en verder nergens.

Nu zegt het scherm het op drie plekken, elk voor wie daar kijkt:

- **De kaart van de batterij**, als tip naast de reden (`tip` in de toestand, zoals de tips
  van de laadpaal): "Handelen staat aan, maar kan nu niet: de coach kent je terugleverprijs
  niet. Daarvoor is bij Contract een marktprijssensor nodig, of salderen." Uit de prijzen
  zelf (`handelen_kan_niet` in batterij.py): handelen aan en geen enkel komend blok met een
  terugleverprijs. Zonder prijzen staat er al een andere reden, en een vast contract heeft
  altijd een vergoeding. Niet naar de telefoon: het is een instelling, geen gebeurtenis.
- **Het vinkje Handelen in Instellen**: zonder terugleverprijs kan het niet aan, wel uit, en
  eronder staat waarom. Uit het contract (`terugleverBekend` in geld.js, dezelfde regels als
  `_prices` en `_tariff`): een vast contract, salderen tot 2027, of een marktprijs die niet
  de all-in sensor is.
- **Contract**, bij het marktveld: een melding zodra daar dezelfde sensor staat als bij de
  all-in prijs. Met salderen zegt die dat het tot 2027 niets uitmaakt.

Proef 43 in test_batterij.py, 165 in test_coach.py, en de proef "handelen zonder
terugleverprijs" in test_rapport.mjs.

Wat de coach vanavond met een terugleverprijs had gedaan, nagerekend met de instellingen
van de woning (rendement 74%, per richting 0,86): de batterij kwam de volgende dag om 14:00
toch vol van de zon, dus een kWh die om 19:00 (€ 0,464) naar het net ging was vervangen
door zon van 13:00 (€ 0,326). Met salderen en de verkoopvergoeding gelijk aan de opslag
scheelt dat ongeveer 2 cent per kWh; met de Zonnebonus van die leverancier erbij (10% van
de kale prijs overdag, die de coach niet kent) ongeveer niets. Handelen tegen eigen zon
levert bij salderen weinig op: een teruggeleverde kWh is dan bijna de inkoopprijs waard.

## Het plan houdt de nacht vast (v0.133.1)

De bewoner van de eerste woning op 19-10-2026, bij de vooruitblik, met de nachtstrategie aan,
een volle batterij en de prijzen tot middernacht: "Ondanks dat handelen aan staat (volle bak
vandaag!), zou ik verwachten dat ie om 19u nog zo'n 20 a 30% over heeft om de nacht door te
komen." Het plan liet hem om 17:00 tot 21:00 handelen en om 23:00 op 5% staan.

Het besluit van het moment hield zich al aan de nacht: handelen alleen zolang er morgenvroeg
nog iets over is (`balans_kwh` in `plan_batterij`, sinds 22-09-2026). De som niet. Die gaf
wat er aan het eind van de bekende prijzen nog in zat de gemiddelde prijs als waarde, en een
kWh die om 18:00 € 0,469 opbrengt is dan meer waard dan een die om middernacht blijft zitten.
Dus verkocht de som alles, en dat stond in het uurplan en in de vooruitblik. Nagebouwd met de
prijzen van die dag: in het plan 5% om 23:00, terwijl het besluit om 18:05 op 40% al nul op de
meter deed ("morgenvroeg 0,74 kWh tekort").

Nu heeft de som dezelfde grens. Per blok de inhoud waaronder hij aan het eind niet aan het
net levert (`_nacht_vloer`): de ondergrens plus wat er nodig is tot morgenvroeg 07:00
(`_nacht_nodig`, dezelfde som als `nachtverloop` maar achterstevoren, met de zon die
onderweg nog komt). Het huis voeden mag eronder; handelen niet (`vloer` in `_mogelijk`).
Zonder nachtstrategie of zonder handelen verandert er niets. Met de prijzen van die dag zegt
het plan nu: handelen van 17:00 tot 19:00 tot 41%, daarna nul op de meter, 29% om 23:00.
Proef 45 in test_batterij.py. In het virtuele huis levert `batterij-handelen` daardoor € 1,01 op
in plaats van € 1,33: de prijs van de nacht vasthouden op een avond van tachtig cent.

## De optimizer in het virtuele huis (v0.132.0)

De bewoner van de eerste woning stuurde op 18-10-2026 het plan van de optimizer van evcc
(bèta): per kwartier wat de batterij doet, met de verwachting van zon, huis en prijzen, en de
ruwe gegevens die erin gaan. De afspraak met de eigenaar: hun aanpak als vergelijking in het
virtuele huis, geen afhankelijkheid. evcc rekende daar met 90% rendement per richting (de coach
mat 74% heen en terug) en een terugleverprijs gelijk aan de inkoopprijs, dus die getallen zijn
niet over te nemen; de aanpak wel.

`bat_optimizer` in virtueel.py is zo'n optimizer, met alles vooraf bekend: dynamisch
programmeren over wat er in de batterij zit (stappen van 0,05 kWh), per kwartier één vermogen,
met hetzelfde huis, dezelfde zon, dezelfde prijzen en dezelfde grenzen als de coach had. Een
kwartier kost wat het per minuut kost, zoals `bat_kosten_met`. Hij eindigt minstens op de
accustand waar de coach eindigde. Hij kent geen reserve, geen volle beurt en geen voorrang voor
de auto. Er is geen solver geïnstalleerd en de proeven horen zonder downloads te draaien; daarom
dit en geen lineair programma.

Gemeten op 19-10-2026, 36 scenario's met een batterij (coach, optimizer, zonder batterij):

| scenario | coach | optimizer | verschil |
|---|---|---|---|
| batterij-kwartier-zelf | € 2,48 | € 1,77 | € 0,70 |
| batterij-volle-beurt | € 3,12 | € 2,73 | € 0,40 (de volle beurt, bewust) |
| batterij-dynamisch-zon-zelf | € -0,54 | € -0,93 | € 0,38 |
| batterij-kwartier-voorloper | € 2,91 | € 2,53 | € 0,38 |
| batterij-handelen | € -1,01 | € -1,30 | € 0,29 (sinds v0.133.1; met de nacht in de som, daarvoor € -1,33 tegen € -1,62) |
| planning-auto-eerst | € 10,88 | € 10,67 | € 0,20 |
| batterij-dynamisch-zon | € -1,01 | € -1,16 | € 0,15 |
| batterij-rendement-onbekend | € 1,29 | € 1,14 | € 0,15 (de coach kent het rendement niet) |

De andere 28 zitten binnen € 0,06, of de coach doet het beter, tot € 0,15 in
batterij-uurlast. Dat kan, want de coach volgt het huis per minuut en de optimizer rekent per
kwartier. `test_virtueel.py` print per scenario de drie bedragen en valt om zodra de coach
meer dan € 0,75 boven de optimizer zit (de volle beurt niet meegeteld).

**Wat er te vinden is**, en nog open staat: de drie scenario's waarin de batterij zelf nul op de
meter doet (`-zelf`) en het kwartierscenario. Daar zit de coach het verst van het optimum. Het
verschil is deels de verwachting: de coach kent de zon van morgen alleen als verwachting, de
optimizer weet hem precies.

## Opgeleverd opnieuw uitrekenen (v0.130.1)

In de eerste woning telde het kasboek van 22-09 tot 19-10-2026 teruglevering als € 0: de
terugleverprijs was onbekend (zie hierboven). Dan lijkt zon in de batterij opslaan gratis en
levert elke ontlading de volle prijs op, en stond "Opgeleverd" te hoog. Die dagen komen niet
vanzelf goed, want het kasboek telt per ronde en kijkt niet terug.

Onder de batterij in Apparaten (alleen de installateur) staat daarom "Opgeleverd opnieuw
uitrekenen": een dag kiezen, Uitrekenen, en dan pas Overnemen. `battery/recalculate`
(websocket) roept `async_herreken_batterij` in coach.py aan, eerst zonder `apply`.

- **De metingen**: per kwartier het net en de batterij uit de eigen kwartieropslag
  (`_async_kwartieren`), de accustand per uur uit de statistiek van Home Assistant
  (`_async_uurgemiddelden`).
- **De prijzen van toen**: de kale marktprijs per kwartier bij de ingebouwde Nord Pool, die
  met zijn dienst ook voorbije dagen geeft (`_async_marktprijzen`); een prijssensor heeft niet
  altijd een statistiek. Lukt dat niet, dan de statistiek van de sensoren. De all-in prijs uit
  de statistiek van de all-in sensor, en anders opgebouwd uit de marktprijs met het contract
  zoals het nu is (`prijsopbouw.inkoop`); de terugleverprijs met `prijsopbouw.terug`, met
  salderen zoals het op die dag gold. Een kwartier zonder prijs telt niet mee, en het paneel
  zegt hoeveel.
- **De som**: `herreken` in batterij.py, met `verdiend`, `Voorraad` en `zon_in_accu` zoals de
  ronde ze gebruikt, en dezelfde grenzen voor laden en ontladen. Wat er op de gekozen dag al
  in zat telt als gratis, net als bij de eerste ronde van de coach.
- **Overnemen** vervangt de dagen vanaf de gekozen dag in `earned_days`, `realized_days` en
  `solar_stored_days`, zet de totalen opnieuw en de voorraad op wat eruit kwam, en begint de
  lopende tellingen van vandaag opnieuw. Wat ervoor ligt blijft staan.

Per kwartier en niet per minuut, dus het is de beste schatting achteraf. Proef 44 in
test_batterij.py (de som) en 171 in test_coach.py (laten zien, overnemen, Nord Pool), en de
proef "Opgeleverd opnieuw uitrekenen" in test_rapport.mjs.

## De temperatuur, de melding en de ventilator (v0.108.0)

De eigenaar op 10-10-2026, met een schermafdruk van de batterijtemperatuur van zijn
Anker: "ik wil dat ik die kan invullen en dat je die toont op de batterijkaart." En
daarna, in hetzelfde gesprek: "ook wil ik een melding kunnen laten sturen wanneer de
temperatuur te hoog is en dat je zelf een doel kan instellen zoals boven x dan
melding", en "ik wil de mogelijkheid om een smart plug in te schakelen om een
ventilator aan te sturen als de batterij te heet wordt."

Drie dingen, voor elk merk (`BATTERY_FIELDS` in devices.js), en de coach stuurt de
batterij er niet anders door:

- **Twee velden bij de batterij**: Temperatuur (`temperature`) en Ventilator (`fan`),
  allebei optioneel. De kaart toont ze onder de accustand, de temperatuur met één
  cijfer achter de komma (`decimals` in het veld, `deviceDetails` in data-source.js).
  De keuzelijst zet temperatuursensoren bovenaan (`temperature` in de `MATCHERS` van
  entity-picker.js; zonder die regel werd een onbekend filter stil `all`).
- **De melding** staat in Meldingen onder "Thuisbatterij te warm" (`temp_alert` in
  const.py: `enabled` en `max_c`), naast lekkage en zware belasting. Geen
  standaardgrens: welke temperatuur te hoog is weet de fabrikant, niet de coach. Eén
  bericht als hij er `TEMP_AANHOUDEND` (twee minuten) boven blijft, zodat één
  verkeerde meting niemand wekt, als kritiek. Weer gewoon is hij `TEMP_TERUG` (een
  graad) onder de grens, en dat staat alleen in de geschiedenis. Een sensor in
  Fahrenheit rekent de coach om (`_celsius`). Na een herstart van Home Assistant
  terwijl hij nog warm is komt het bericht één keer opnieuw: wat al gemeld is staat
  in het geheugen, niet op schijf.
- **De ventilator**: een plug bij de batterij en een grens onder Wat jij wilt
  (`fan_above_c`, leeg is nooit). Boven de grens gaat hij aan, een graad eronder uit,
  ertussen blijft hij staan zoals hij staat (`_async_ventilator` in coach.py). Een
  plug die `unavailable` is laat de coach met rust. Niet bij Alleen uitlezen en
  Adviseren, want daar belooft de coach niets aan te raken; wel bij Voorstellen, want
  wie een plug en een grens invult heeft ja gezegd. Elke keer dat hij schakelt staat
  in de geschiedenis, niet op de telefoon. Wie de ventilator met de hand aanzet
  terwijl de batterij koeler is dan de grens min een graad, ziet hem de volgende
  minuut weer uitgaan: de coach bedient hem.

Hangt er een melding of een ventilator aan de temperatuur, dan bewaakt de
sensorwacht de sensor ook (`_temp_nodig`), met als slotzin "Zolang weet de coach niet
of hij te warm wordt." Dat is er voor het geval bij de eigenaar: de Anker-integratie
heeft de temperatuur (nog) niet zelf, hij zette hem er met de hand in, en na elke
update van die integratie is hij weg.

Proef 135 in test_coach.py (de melding, de ventilator, de niveaus, Fahrenheit, de
sensorwacht en een gewone ronde), en vier in test_rapport.mjs (de kaart, de
keuzelijst, het blok in Meldingen, de velden). In het virtuele huis zit geen
temperatuur, dus daar is geen scenario voor.

## Een tik voor op het plan: vasthouden tot het blok om is (v0.108.1)

In de klantwoning in de nacht van 05 op 06-10-2026 laadde de coach rustig van het net
in kwartieren van € 0,309 tot € 0,322. Elke keer dat de accustand een procent
voorliep op het plan (23:42 naar 46%, 00:25, 00:42, 01:28) wilde het plan in de rest
van het kwartier niets meer, gaf `_rustig_vermogen` 0, en viel `plan_batterij` met
zelf nul naar nul op de meter: de Anker dekte de warmtepomp uit wat hij net gekocht
had, en na `ZELF_WACHT` gaf de coach hem terug. Tussen 22:45 en 05:30 7,68 kWh erin
en 2,36 kWh eruit. Op 10-10-2026 tussen 15:46 en 16:00 tikte de stand elke minuut
tussen 83 en 84%, met vier moduswissels.

Het besluit om dit blok te laden is aan het begin van het blok genomen. Loopt de
beurt al in dit blok (`_houden_tot`, met `_loopt_al`), dan houdt hij de batterij nu
vast tot het blok om is: laden van het net op één watt (`HOUD_W`), niets eruit, zon
er nog wel in, met "Hij maakt het laden van het net af tot HH:MM en geeft tot dan
niets af." Het volgende blok besluit opnieuw. Dit was voorstel (1) van 30-09-2026;
v0.102.3 bouwde het doorladen, niet het vasthouden.

Scenario `batterij-kwartier-voorloper`, met de echte kwartierprijzen van die nacht
(`KWARTIER_05_10`): v0.108.0 12 keer de modus om en laden en ontladen in zes
kwartieren, nu 8 keer en alleen aan het eind van de nachtbeurt. De kosten tot
10:30 bleven gelijk (€ 2,89 en € 2,91, met een procent meer in de batterij): het
scheelt moduswissels, geen geld. Proef 42 in test_batterij.py.

**Open, in hetzelfde scenario gezien:** rustig verdeeld laden met een accustand in hele
procenten geeft een zaagtand. `_rustig_vermogen` rekent elke ronde wat er in de rest
van de even dure blokken nog bij moet, de stand blijft een paar minuten op hetzelfde
procent staan terwijl de batterij laadt, dus het vermogen loopt elke minuut op tot de
stand tikt en zakt dan terug: 03:00 tot 05:30 zo'n 50 opdrachten per uur, met v0.108.0
precies zo. In de eerste woning gezien als twee à drie nieuwe opdrachten per minuut
(03-10-2026). Bijtellen zoals bij de auto (`_soc_bijgeteld`) zou het rustiger maken;
niet gebouwd. Het scenario valt daarom buiten de algemene controles op opdrachten,
wissels en kosten per dag in test_virtueel.py.

## Het kasboek telt niet meer dan de batterij kan (v0.108.1)

De ontlaadsensor van de Anker gaf tussen 30-09 en 10-10-2026 2.856 keer meer dan
3.600 W, tot 7.000 W, bij een batterij van 3.500 W. Op 02-10-2026 om 15:52:30 zag de
meter op L1 5,1 kW teruglevering bij 6,0 kW zon over drie fasen; dat past bij 3,5 kW
uit de batterij, niet bij 7. In zijn eigen stand telde de coach de sensor zoals hij
was, en elke tik ging in het kasboek als stroom die het huis niet hoefde te kopen:
tot ongeveer € 2,35 van de € 19,81 "Opgeleverd" van die dagen (een bovengrens; dat
deel is niet teruggerekend). Nu begrenst het kasboek op het hoogste laad- en
ontlaadvermogen uit Apparaten (`_async_regel`).

**Niet veranderd, wel gezien:** van de negen overnames "want de zekering wordt krap"
zonder auto waren er zeven bij teruglevering op L1 (18 tot 23 A), niet bij afname.
De fasestromen van een DSMR-meter zijn hele ampères zonder teken, en `_laadruimte_w`
neemt `abs()`. Voor de zekering zelf klopt dat, maar laden verlaagt de stroom bij
teruglevering. Om dat te onderscheiden is de richting per fase nodig, en een fout
daarin haalt een beveiliging weg; voorgelegd, niet gebouwd.

## Overnemen terwijl er rondes lopen (v0.108.2)

Bij de eigenaar op 11-10-2026 om 12:08:04 ging de kabel van de bus erin. De batterij
deed zelf nul op de meter, en de regelaar (een tik van de meter, die naast de ronde
loopt) nam hem over voor de paal: om 12:08:05 de modus naar de externe stand, en dan
wachten op de stuurknop, die in de eigen stand van deze Anker weg is en pas om
12:08:08 terugkwam (`_async_overnemen_op_nul`). Pas daarna zet `_async_zelf_wissel`
de sessie op "niet zelf". Intussen kwamen er rondes, want elke wissel van de paal
geeft er een (`awaiting_authorization`, `awaiting_start`). Die vergeleken de modus
met de eigen stand, want de sessie stond nog op "zelf", zagen twee keer iets anders
(`VREEMD_RONDEN`), en om 12:08:08 kwam de kritieke melding "Iets anders stuurt
Batterij: de bedrijfsmodus staat niet meer op wat de coach zette." De coach liet de
batterij een uur los (`VREEMD_PAUZE`), in de externe stand op 0 W. In de logboeken
staat de melding van het overnemen ("de coach neemt het over, want de laadpaal gaat
laden", met de tijd 12:08:04) ná die van 12:08:08: het overnemen was nog niet klaar.

Nu telt een ronde de modus niet zolang de regelaar bezig is (`bezig` in de sessie),
en zet hij de teller dan ook niet terug. Een echte andere sturing houdt de modus
langer dan één stap van de regelaar om, en die ziet hij nog steeds. Proef 140 in
test_coach.py draait twee rondes in het wachten op de knop: met v0.108.1 de melding
en een uur los, nu niets, en een omgezette modus daarna wordt nog gezien.

## De batterijkaart en de coach: entiteiten per batterij (v0.112.0)

Voor de batterijkaart van DomotiApp Lovelace, met hetzelfde contract als de vaatwasser en de
laadpaal (contract 1, `entiteit.py`, docs/vaatwasser.md): een eigen apparaat per batterij
(model "Thuisbatterij"), vaste `translation_key`s, en de kaart leest de attributen.

| entiteit | translation_key | wat |
|---|---|---|
| sensor | `coach` | state de naam van de stand ("Nul op de meter"); de rest in de attributen |
| button | `vol_laden` | nu vol laden (`async_boost`), gaat vanzelf uit als hij vol is |
| button | `leegladen` | nu leegladen tot `leeg_tot` (`async_drain`), nooit onder de ondergrens |
| button | `terug_naar_plan` | vol en leeg eraf |
| number | `leeg_tot` | tot welk % leegladen gaat; staat in het geheugen, na een herstart weer de ondergrens |
| number | `vol_tot` | tot welk % vol laden gaat (v0.141.0); leeg is de laadgrens, nooit erboven |
| switch | `vakantiestand` | `battery.holiday` in Apparaten; de grens blijft een instelling van de installateur |

Attributen van de sensor: `contract`, `type`, `stand` (`nul_op_de_meter`, `zonneladen`,
`laden`, `ontladen`, `stil`; `accu_stand`), `zelf` (doet hij zelf nul op de meter), `soc`,
`reason`, `temperatuur` (uit de temperatuursensor van Apparaten), `plan` (per uur: `start`,
`end`, `actie` uit `nul`, `laden`, `ontladen`, `stil`, `kw` positief laden en negatief
ontladen, `price`, `soc_eind`), `opgeleverd_vandaag`, `opgeleverd_maand` (uit
`realized_days`), `opgeleverd_totaal`, `opgeleverd_sinds`, `override` (`vol`, `leeg` of
niets), `leeg_tot`, `vakantie`, `vakantie_max`, `reserve` (alleen als die aan staat),
`ondergrens` en `entiteiten`. Proef 146 in test_coach.py. Sinds v0.123.0 ook `capaciteit`,
`brand` en `alleen_lezen` (zie Growatt, onderaan).

Sinds v0.112.1 ook `accu_fabrikant` en `accu_model`, zoals `paal_fabrikant` en `paal_model` bij de
laadpaal: wat de integratie van de batterij in het apparatenregister zet, zodat de kaart
"Automatisch" de juiste foto kiest. Eerst het apparaat dat bij de coach is ingevuld, anders dat
van de accustand, de modus, het vermogen (`accu_apparaat`, `register_apparaat` in entiteit.py);
een lege tekst als er niets te vinden is. Gevraagd door de lovelace-sessie op 11-10-2026. Proef 147.

En `vakantie_max` is sindsdien altijd een getal, ook als de vakantiestand uit staat: zonder ingevulde
grens 50, waar de coach al mee rekende (`HOLIDAY_MAX_DEFAULT` in const.py, voor `_vakantie` en de
sensor allebei). In v0.112.0 gaf de sensor dan niets, en zag de kaart geen grens terwijl de coach
de batterij onder de helft hield.

Wat er in dezelfde uitgave voor de laadpaalkaart bij kwam, en de reparatie van het verslag
na een herstart, staat in docs/laadpaal.md.

## Zelf nul op de meter zonder vermogenssensor (v0.112.2)

Doet de batterij zelf nul op de meter, dan is haar vermogenssensor de enige bron voor het
kasboek (`verdiend` in `_async_regel`). Was die sensor onbekend, dan viel het kasboek om met
een TypeError, en daarmee de rest van de stap van de regelaar: ook `_zelf_niet`, dat de
batterij uit haar eigen stand haalt als de paal gaat laden, de zekering krap wordt of de
vakantiestand aan gaat. De schaduw zag het bij de eigenaar op 11-10-2026 tussen 22:34 en 22:36,
toen de integratie van de batterij onbekend was: 47 keer "de regelaar struikelde". Nu telt
het kasboek die stap niet (er valt niets te weten) en loopt de rest gewoon door. Proef 148
bouwt het na: sensor weg, paal gaat laden, en de coach neemt de batterij meteen over op 0 W.
Daarvoor bleef ze in haar eigen stand.

## Growatt: alleen uitlezen (v0.123.0)

*Sinds v0.150.0 stuurt de coach een Growatt die dat kan met een laadschema; zie "Growatt sturen
met een laadschema" hieronder. Wat hier staat geldt nog voor een Growatt die het niet kan (een MIX,
de klassieke inlog).*

De eigenaar op 15-10-2026: "nee sturen niet voor growatt alleen uitlezen", en "dat ik dus
alleen invulvelden krijg die noodzakelijk zijn voor growatt". De Growatt-integratie van Home
Assistant (`growatt_server`) haalt alles eens per vijf minuten uit de cloud, en heeft voor
een MIX alleen sensoren: laden en ontladen in kW, de accustand, en tellers per dag en voor
levenslang. Een stuurgetal in watt, waar de regelaar van de coach op draait, is er niet.

**Wat er in Apparaten staat.** Bij het merk Growatt vijf velden: Accustand, Laadvermogen,
Ontlaadvermogen, Batterij zelf: geladen en Batterij zelf: ontladen. Geen vermogenssensor
met een teken, geen stuurgetal, richting of modus, geen grenzen, temperatuur, ventilator of
kWh-meter. Onder De batterij alleen de capaciteit als getal, want een sensor daarvoor heeft
de integratie niet. Waar bij een ander merk het vinkje "De coach mag dit apparaat aansturen"
staat, staat hier dat de coach hem alleen uitleest (`readOnly` in `BATTERY_BRANDS`,
`isReadOnly` in devices.js; `canSteer` is dan onwaar). Wie van een ander merk naar Growatt
gaat, verliest het vinkje en alles wat hier geen veld heeft (`alleenUitlezen`), want de coach
zou zo'n sensor nog lezen: een vermogenssensor met een teken gaat bij `_batterij_w` voor.

**Vanzelf invullen.** Kies je de accustand van een Growatt, dan vult het paneel de andere
vier in uit hetzelfde apparaat, op hun `translation_key` in `hass.entities`
(`growattVanzelf`). Alleen de vorm `mix_*`, die een MIX en een SPH allebei hebben:
`mix_battery_charge`, `mix_battery_discharge_kw` (een SPH heeft die niet, dan
`mix_battery_discharge_w`), `mix_battery_charge_lifetime` en `mix_battery_discharge_lifetime`.
Zo staan ze in de bron van de integratie, en zo stonden ze op 15-10-2026 in een klantwoning.
De tellers voor levenslang en niet die van vandaag: een dagteller begint om middernacht
opnieuw. Een MIN (`tlx_*`) en een opslag (`storage_*`) heten anders, en een MIN kan twee
accu's hebben; daar kiest de installateur zelf. Wat er al staat blijft staan.

**De coach stuurt hem nooit**, ook niet met het vinkje aan of een stuurgetal van vroeger:
`BATTERIJ_ALLEEN_LEZEN` in const.py haalt hem uit de lijst die `_one_batterij` krijgt. Dus geen
stand, geen plan, geen kasboek. Wat hij wel doet, voor elke batterij die hij niet stuurt:
het rendement uit de eigen tellers voor de pop-up ("ongeveer 90%, gemeten in de accu",
`_async_batterij_uitlezen`, net als `rte_accu` in `_one_batterij` sinds v0.118.0). Laden en
ontladen tellen mee in de energiestroom, in het overschot (`_batterijen_w`) en in Historie;
kW of W maakt niet uit (`to_watts`). Op het overzicht staat hij niet als kaart: daar staan
alleen apparaten die de coach mag sturen.

In de klantwoning gaf de datasheet 15,3 kWh, en kwam er op 15-10-2026 ongeveer 12 kWh uit
per 100% van de accustand. De installateur vult in wat hij wil; het paneel zegt er niets over.

Proef 159 in test_coach.py (een Growatt met het vinkje aan en een stuurgetal: niets naar de
batterij, 5,4 kW ontladen is -5400 W, het rendement uit de twee tellers), en vier
proeven in test_rapport.mjs (de velden, van een ander merk naar Growatt, het vanzelf invullen,
kW en het rendement in de pop-up).

Voor de batterijkaart van DomotiApp Lovelace komen er drie attributen bij op de sensor
`coach`, zonder dat het contract verandert (alleen toegevoegd, contract 1): `capaciteit` (in
kWh, de sensor uit Apparaten en anders wat er ingetypt is, of null; `accu_capaciteit` in
entiteit.py, waarmee de kaart bij een Growatt het type kiest), `brand` (hoe de
coach hem kent, `growatt`, zoals `brand` bij de laadpaal) en `alleen_lezen` (waar bij een
Growatt altijd, en bij elke batterij die de coach niet mag sturen). Dan is er geen stand
(`stil`), geen plan en geen accustand in de attributen, want `_one_batterij` draait voor hem
niet; de kaart leest de accustand, het laden en het ontladen zelf uit `entiteiten`. Het merk
voor de foto komt zoals bij elke batterij uit het register (`accu_fabrikant`): de
Growatt-integratie zet daar "Growatt", en bij een MIX geen model. Proef 159.

**Sinds v0.123.1** zegt die sensor dan "Alleen uitlezen" in plaats van niets, en staan vol
laden, leegladen, terug naar het plan, de vakantiestand en leegladen tot op niet beschikbaar
(`AccuBediening`, `accu_alleen_lezen` in entiteit.py). De beheersessie zag ze op 15-10-2026 bij
een Growatt en vroeg: "Die doen bij een Growatt niets." Niet weggehaald, want dan blijven ze
als wees in het register staan, en bij een batterij die de coach later wel mag sturen komen
ze vanzelf terug. De accustand blijft bewust leeg op de sensor: die wordt alleen bij een
besluit of een wijziging in Apparaten opnieuw geschreven, en zou dus een oude waarde tonen.

## Handelen in twee, met een grens per richting (v0.141.0)

De eigenaar op 19-10-2026, bij de pop-up van een batterij met Handelen aan: "ik zou van
Handelen een kop maken, en vervolgens 2 opties eronder hangen: Batterij mag laden van het net
tijdens lage tarieven / Batterij mag ontladen naar het net tijdens hoge tarieven. Ik wil bijv
NIET dat ie gaat laden, maar WEL dat ie overschot in de accu dat ik niet meer nodig heb bovenop
mijn nachtverbruik, gaat verkopen." En op 21-10-2026, per richting: "laat coach de beste
strategie bepalen, óf laad uitsluitend uit het net als de energieprijs onder x is", hetzelfde
voor ontladen boven x, "in alle gevallen met de all-in energieprijs". Een bewoner wil wel van
het net laden "als de prijs bijv. <15 cent is".

In Instellen van de batterij staat nu een kop Handelen met twee vinkjes, elk met een veld voor
de grens in euro per kWh; leeg is "de coach bepaalt":

| instelling | standaard | in batterij.py |
|---|---|---|
| `grid_charge` Laden uit het net tijdens lage tarieven | aan, zoals het altijd was | `Batterij.net_laden` |
| `grid_charge_below` Alleen als de prijs onder | leeg | `Batterij.net_laden_onder` |
| `trade` Ontladen naar het net tijdens hoge tarieven | uit, zoals het altijd was | `Batterij.handelen` |
| `trade_above` Alleen als de prijs boven | leeg | `Batterij.handelen_boven` |

`_mag_netladen` zegt per blok of er iets van het net bij mag; mag het niet, dan rekent
`_mogelijk` net als in de avondpiek: alleen zon erin. Ook de negatieve prijs (`max-laden`) volgt
het. `_mag_handelen` zegt hetzelfde voor naar het net, met de grens erbij. Beide vergelijken
met `price` van het blok, de all-in inkoopprijs; ook bij ontladen, zoals gevraagd, en niet de
terugleverprijs. Er hoeft niets omgezet te worden: een batterij zonder de nieuwe velden laadt
van het net en handelt zoals voorheen.

Proef 47 in test_batterij.py, de scenario's `batterij-netladen-onder` (grens 0,16 bij prijzen
van 0,156 tot 0,41: alleen het uur van 0,156) en `batterij-netladen-uit` in het virtuele huis.

## Vol laden tot een doel, met de schuif (v0.141.0)

De eigenaar op 19-10-2026: "Nu vol laden" en "Nu leegladen" openen een pop-up met een schuif
tussen de ondergrens en het plafond (`floor` en `ceiling` in de stand), het vak "tot 50 %" naast
de knop is weg, en zolang het loopt draait er een blauwe ring om de knop (`accu-doel-sheet.js`,
`openDoel_` en `kiesDoel_` in overview.js). Vol laden kreeg daarvoor een doel:
`domotiapp_coach/coach/boost` neemt een optionele `to_percent`, de coach houdt het bij in
`_vol_tot` en bewaart het over een herstart (`boost_to`), en stopt op de laagste van het doel en
de laadgrens ("{naam} is geladen tot 80%; hij volgt het plan weer."). Voor de kaarten van
DomotiApp Lovelace: de number `vol_tot` en het attribuut `vol_tot` op de sensor; het contract
blijft 1, want er komt alleen iets bij. Proef 185 in test_coach.py.


## Met welk rendement de coach rekent (v0.145.0)

De eigenaar op 22-10-2026: "ik zou bij rendement altijd het gemeten rendement hanteren uit de aparte
kwh meter, mits die aanwezig is. Is er geen aparte meter aanwezig, dan moet je de interne RTE
hanteren", en die interne "zouden de eigen tellers moeten zijn, of het zelf geleerde mits dat
betrouwbaarder is". Aanleiding: in een klantwoning leerde de coach uit stappen van een procent 85%
rond 2 kW, terwijl de kWh-meter op de batterij over alles samen 76% telde. Bij een verkoop op 0,353
na laden op 0,296 rekende hij met 85% winst (omslag 0,348); met 76% ligt de omslag rond 0,39.

`_rendement_bron` in coach.py, in deze volgorde:

1. een kWh-meter op de batterij (`energy_in`, `energy_out`): wat die over alles samen meet
   (`rendement_uit_tellers`, na tien keer de inhoud aan doorzet), of de laatste meting (`rte` in
   `battery_state`). Geen rendement per vermogen: de meter telt ook wat de batterij stil verbruikt
   en wat er buiten 10 tot 90% gebeurt, het zelf geleerde niet;
2. zonder meter het zelf geleerde per vermogen (`rte_steps`, v0.142.0), als het genoeg stappen heeft.
   Dat gaat voor de eigen tellers, omdat het aan de wisselstroomkant meet, met het verlies in de
   omvormer erbij;
3. de eigen tellers van de batterij (`accu_in`, `accu_out`, of de laatste `rte_accu`); tot v0.145.0
   stonden die alleen in de pop-up;
4. wat de bewoner invulde (`rte_percent`); zonder dat is het onbekend en plant hij niet.

Een meting gaat dus altijd voor wat er ingevuld is; tot v0.145.0 ging een ingevuld rendement voor
de eigen tellers. De pop-up volgt dezelfde volgorde ("gemeten met de kWh-meter", "zelf geleerd",
"gemeten in de accu", "opgegeven"; `data-source.js`). Proef 154 en 190 in test_coach.py.

## De afschrijving in de minimale spread (v0.146.0)

De eigenaar op 22-10-2026: "Nu rekent coach alleen met het rendementsverlies. Maar ook afschrijving
moet meegerekend worden om de minimale prijsspread te bepalen", met een veld dat de bewoner invult en
een hulp: "wil je dat ik je help met het berekenen van je afschrijving? Bij klik, verschijnen extra
velden waar je de aanschafprijs en minimum laadcycli (door leverancier) kunt invullen." En: "Voor de
eenvoud.. aanschafprijs/minimaal aantal cycli. Zou restwaarde oid niet meenemen, die weet je toch
niet."

In Instellen van de batterij staat een vak Afschrijving: `wear_per_kwh` (euro per kWh uit de
batterij, leeg is geen), en onder het vinkje "Help me dit uit te rekenen." `wear_price` (de
aanschafprijs) en `wear_cycles` (de laadcycli volgens de leverancier). Met beide ingevuld rekent de
coach aanschafprijs / (cycli × capaciteit) en gaat dat voor het veld (`_slijtage` in coach.py; het
paneel toont het bedrag als het de capaciteit kent, `afschrijvingPerKwh` in voorkeur-velden.js). Een
cyclus is de hele inhoud er een keer uit, dus het bedrag geldt per kWh die uit de cellen komt. De
namen zijn bewust niet `purchase_price`: dat was de aankoopprijs voor een terugverdientijd, en die
blijft weg (v0.101.1).

In de som (`Batterij.slijtage`): `_blok_kosten` telt de slijtage op voor elke kWh die uit de cellen
gaat, en wat er aan het eind van de bekende uren nog in zit is waard wat het ontladen oplevert min
die slijtage. Laden en later ontladen loont dus pas als het verschil in prijs het verlies in de
batterij én de afschrijving dekt; dat geldt voor van het net laden, handelen en zon die eerst in de
batterij gaat. Het voorbeeld van de eigenaar (laden op 0,290 tot 0,296, ontladen op 0,353 tot
0,379, 85%): zonder afschrijving laadt hij 's nachts, met 4 cent per kWh niet meer; bij een ochtend
van 0,45 wel. Proef 49 in test_batterij.py, 191 in test_coach.py. Het kasboek boekt de afschrijving
(nog) niet.

## Terugverdiend op de kaart, zonder datum (v0.148.0)

De eigenaar op 22-10-2026, na de afschrijving: "ja ik wil hem toch terug hebben", over de
terugverdientijd die in v0.101.1 verdween. Gekozen: alleen voor de thuisbatterij, alleen wat er al
terug is, en per installatie een vinkje of de bewoner het ziet. De reden van 29-09-2026 blijft
staan: een datum is een belofte, en een datum die afwijkt van wat een installateur de klant
voorrekende is niet te verdedigen. Er komt dus geen datum, geen "klaar", en niets in Historie of
het rapport.

Op de kaart van de batterij staat onder Opgeleverd de regel Terugverdiend, "€ 45,00 van € 4.500",
met een balk eronder (`terugverdiendRegel` in battery.js, `aanschaf_` in views/overview.js). Het
bedrag is Opgeleverd zelf, dus wat de batterij opleverde sinds de coach haar volgt; wat ze daarvoor
verdiende weet de coach niet en schat hij niet. Het kasboek boekt de afschrijving niet (v0.146.0),
dus die gaat er niet twee keer af. Kostte de batterij tot nu toe geld, dan staat er "€ 0,00" en
blijft de balk leeg (v0.148.1, zie hieronder).

De aanschafprijs is die van de afschrijving (`wear_price`, onder "Help me dit uit te rekenen"), zodat
hij maar op één plek staat. Zonder laadcycli (`wear_cycles`) telt hij niet mee in de afschrijving
(`_slijtage` in coach.py), dus wie alleen Terugverdiend wil hoeft de coach niet anders te laten
sturen. De installateur ziet de regel altijd (`hass.user.is_admin`), de bewoner alleen met
"Terugverdiend ook aan de bewoner tonen" bij Installatie, onder Woning
(`installation.payback_resident`, standaard uit). De proef "geen datum, geen investeringen" in
test_rapport.mjs houdt investeringen, een datum en Terugverdiend in Historie en het rapport buiten
de bron.

**Geen min op de kaart (v0.148.1).** Thuis stond er na de eerste installatie "Opgeleverd € -7,46 in
25 dagen" en "Terugverdiend − € 7,46 van € 3.682": bij een vast contract met salderen levert
opslaan niets op en kost het het verlies in de batterij. De eigenaar op 22-10-2026: "min getal wil
ik niet, zet dan nul tot dat hij boven de nul is." Opgeleverd en Terugverdiend op de kaart tonen
daarom nooit minder dan € 0,00 (`nietOnderNul` in battery.js). Het kasboek houdt het echte bedrag:
een tekort moet eerst ingelopen worden voor er iets boven nul verschijnt. Opgeleverd opnieuw
uitrekenen (Apparaten) toont wel het echte bedrag, want daar kijkt de installateur na.

## Growatt sturen met een laadschema (v0.150.0)

De eigenaar op 22-10-2026, via de beheersessie: de Growatt-thuisbatterij sturen vanuit de coach,
universeel voor elke klant met een Growatt, en zelflerend. Zijn keuze van 15-10-2026 ("nee sturen
niet voor growatt alleen uitlezen") vervalt waar sturen kan. In twee stappen (zijn keuze): eerst
sturen, met de inhoud en het vermogen zelf geleerd; daarna de zon zelf leren zonder paneelgegevens
en na elke nacht nakijken of er te veel of te weinig geladen is. En bij de klantwoning eerst in de
schaduw: zonder het vinkje rekent de coach en zegt hij wat hij zou schrijven.

**Wat er kan.** De integratie `growatt_server` heeft voor een SPH op het API-token geen stuurgetal en
geen number of switch, wel acties: `write_ac_charge_times` (laadvermogen in procent, de accustand
waar hij stopt, `mains_enabled` voor laden van het net, drie vakken met een begin- en eindtijd) en
`read_ac_charge_times`, dat alleen met `return_response` antwoord geeft. Bewezen in de klantwoning
op 22-10-2026 (beheer): mains aan, 20%, vakken 23:40-23:59 en 00:00-00:30; om 23:41 had de omvormer
het, en de volgende meting laadde hij met 1.570 W. Daarbij gezien: de sensoren lopen vijf tot tien
minuten achter, een tweede schrijfactie vlak na de eerste faalt ("Error during writing ...") en lukt
een minuut later wel, het schema herhaalt zich elke dag, en het teruglezen gaf als stopgrens 100
terwijl er 25 in stond (de omvormer heeft er twee velden voor). Een MIN heeft tijdsegmenten
(`read_time_segments`, `update_time_segment`); die stuurt de coach nog niet.

**Herkennen** (`_async_growatt_soort` in coach.py). Niet uit een naam of model, want dat geeft de
integratie niet: de coach vraagt het laadschema op, op het apparaat van de accustand in het
register (`_growatt_apparaat`). Geeft de omvormer zijn vakken terug, dan is het een SPH die hij kan
sturen; anders een uur later opnieuw. Een MIX of de klassieke inlog heeft de acties niet en blijft
alleen uitlezen. In const.py staat Growatt daarom niet meer in `BATTERIJ_ALLEEN_LEZEN` maar in
`BATTERIJ_SCHEMA`; in devices.js `schema` in plaats van `readOnly`, met het vinkje.

**Het plan** is dezelfde som als bij een batterij die zelf nul op de meter doet (`zelf_nul`),
zonder handelen: een schema kan niet op een prijs naar het net ontladen. Van het plan neemt
`growatt_schema` (batterij.py) alleen de blokken van het net, en dan alleen het eerstvolgende stuk
even dure uren waar ze in vallen: de Growatt heeft één stopgrens voor alle vakken, en het schema
herhaalt zich elke dag. Sinds v0.152.0 aan het eind van dat stuk, zo laat als het kan: de eigenaar op
23-10-2026, "de laatste 2 uur van de goedkope uren de accu vol laden", en "je wilt uiteindelijk gewoon
dat je de goedkope uren en de zon zoveel mogelijk gebruikt". Het vak eindigt met het stuk en duurt
minstens `GROWATT_LAAT_MIN` (twee uur), en langer als hij anders boven `GROWATT_LAAT_DEEL` (de helft)
van zijn vermogen moet: die marge vangt een opdracht op die een keer niet aankomt, en een accu die
trager laadt dan gedacht. Past het er zo niet in, dan begint het vak waar het stuk begint. De duur is
in echte uren (`echt_verder`): in de nacht van de wintertijd begint zeven uur voor 08:00 om 02:00, niet
om 01:00. Zo laat mogelijk betekent ook dat hij over de hoeveelheid beslist met de verste
zonverwachting, een half uur voor het vak (`GROWATT_VOORAF`), en binnen het stuk kost het niets extra.
Tot v0.152.0 was het uitgesmeerd over het hele stuk. Loopt het vak dat de coach schreef al
(`loopt`), dan blijft het lopen tot het eind, met wat er nog moet over de rest: terwijl hij laadt
schuift het berekende begin anders voorbij nu, en dan stond de batterij tot dat nieuwe begin buiten een
vak en voedde hij het huis in de goedkope uren. Om dezelfde reden kijkt `_growatt_vroeg` naar het vak
dat in de Growatt staat, niet naar het nieuwe; zonder dat bleef in het virtuele huis een hogere
stopgrens liggen en stond hij om 09:00 op 76% in plaats van vol. Het vermogen is wat erin moet over wat er van het
vak over is, naar boven afgerond op een procent van wat hij kan, en de stopgrens waar het plan na het
stuk zit. Een vak over middernacht wordt er twee (23:00-23:59 en 00:00-09:00), want een
vak loopt van een kloktijd naar een latere. Een vak reikt hooguit een etmaal vooruit, behalve als nu
even goedkoop is; het begin staat op het kwartier.

**Vasthouden** (v0.155.0). De eigenaar op 23-10-2026: "kunnen we de accu net als anker ook op hold
zetten? Dus pas als het dure uur in gaat dan pas ontladen?", en over bi-horário: "Bij [de klantwoning] moet de
accu vanwege de 2 prijzen weer op nul op de meter op de dure prijs". Een Growatt heeft geen stand om
stil te staan, maar in een vak van zijn laadschema ontlaadt hij niet; met de stopgrens op de accustand
staat hij daar stil en haalt het huis van het net. Dus:

* de som mag bij een Growatt (`kan_vasthouden`, gezet in `_growatt_batterij`) stilstaan als het huis
  vraagt (`_zelf_toegestaan`), maar alleen in een blok waarna nog een duurder blok komt
  (`_duurder_later`). Zonder die regel koos de som bij gelijke kosten stilstaan ook op de dure prijs,
  omdat morgen even duur was, en hield hij in het virtuele huis de hele dure dag vast (€ 1,93 tegen
  € 1,82). Bij twee prijzen is dat precies vazio; bij een dynamisch contract kiest de som per uur, en
  kiest hij niet voor vasthouden als het goedkoper is nu te gebruiken en straks bij te laden;
* `Uur.vast` zegt welke blokken dat zijn: het huis vraagt, er zit iets in, en hij geeft niets. Stilstaan
  omdat het huis niets vraagt of omdat hij leeg is, is iets anders;
* `growatt_schema` begint het vak waar het vasthouden begint, met `houden`, de stopgrens op wat er dan
  in zit (niet de stand van nu: een vak dat om 18:00 geschreven wordt begint om 22:00) en 10% vermogen
  (`GROWATT_HOUDEN_PCT`, sinds v0.156.1; 1% nam de Growatt niet aan).
  Moet er later bij, dan wordt het op het late moment een schema om te laden in hetzelfde vak; van
  `houden` naar laden is altijd een nieuw schema (`wijkt_af`), terug niet als de oude stopgrens niet
  hoger ligt (na vol laden tot 100% staat hij al stil);
* vanaf `GROWATT_HOUDEN_KWH` (0,5 kWh) boven de vloer, want minder is een schrijfopdracht niet waard;
* `growatt_vol` zet een vasthoudschema niet uit, en na een laadschema op de stopgrens houdt de coach
  hem vast als het plan dat wil, in plaats van het schema uit te zetten;
* het besluit heet dan "vasthouden" (`STANDBY`, regel `vasthouden`);
* komt het laden in het plan vóór het vasthouden (een beetje bij, dan vast), dan eerst een schema om te
  laden; op de stopgrens houdt de coach hem daarna vast;
* een vak dat later begint mag op de klok nu niet al lopen, want een vak herhaalt zich elke dag. In het
  virtuele huis schreef hij om 05:50 het vasthouden van morgen vanaf 05:15, en hield hij hem meteen vast.

Alleen voor een Growatt: elke andere batterij die zelf nul doet rekent als voorheen (proef 53 in
test_batterij.py). In het virtuele huis (`growatt-vasthouden`, de batterij om 21:30 op 50%): in vazio
0,0 kWh uit de batterij tegen 2,3 kWh, € 1,75 tegen € 1,82. Het virtuele huis staat in een vak op de
stopgrens nu stil (`schema_vak` in virtueel.py), en niet meer op nul op de meter. In het echt nog niet
gezien: dat de SPH op de stopgrens in zijn vak echt stilstaat.

**Schrijven** (`_async_growatt`). Eén schema per goedkoop stuk:

* over het volgende stuk beslist hij pas `GROWATT_VOORAF` (30 minuten) voordat het begint
  (`_growatt_wacht`), want het plan schuift overdag mee met de zon en de prijzen;
* daarvoor alleen als de vakken of aan en uit veranderen, binnen het vak ook als er meer vermogen of
  een hogere stopgrens nodig is (`wijkt_af`, vanaf 5 procentpunt en 3%); lager schrijft hij niet,
  want dan zet het plan het schema zelf uit zodra er genoeg in zit;
* aan of uit pas als het plan dat vijf minuten wil (`GROWATT_BESTENDIG`);
* nooit twee keer binnen vijf minuten (`GROWATT_PAUZE`), en na zes minuten teruglezen (`GROWATT_TERUG`;
  `gelijk` vergelijkt aan, vermogen en vakken, niet de stopgrens). Uitgezocht op 23-10-2026 in de bron
  van `growatt_server` en `growattServer` 2.2.0: Growatt neemt per onderdeel van zijn API één vraag per
  vijf minuten aan (fout 10012, "Access Frequency Limitation of 5 Minutes/Time"); Home Assistant vraagt
  elke vijf minuten (`SCAN_INTERVAL`) vier dingen op, plus elk uur drie voor een scan.
  `read_ac_charge_times` vraagt Growatt niets, maar leest wat Home Assistant onthield, en na een
  schrijfopdracht zet Home Assistant daar zelf in wat er geschreven werd. Wat de omvormer echt heeft,
  staat er pas na de volgende ronde; tot v0.152.0 las de coach na 90 seconden dus zijn eigen opdracht
  terug. Schrijven is één aanroep (`mixSet`). Een daggrens voor een token is niet gevonden; de blokkade
  van 24 uur geldt alleen voor de oude inlog met wachtwoord;
* na drie keer niet aangenomen één melding, kritiek als het laden van het net er niet uit wil.

**De stopgrens bewaakt hij zelf** (`growatt_vol`): zit de accustand erop, dan zet hij het schema uit
en in dat stuk niet opnieuw aan. Behalve bij een stopgrens van 100%: vol stopt hij zelf, en zolang het
vak loopt staat hij stil terwijl het huis goedkoop van het net haalt. Zou de coach het schema dan
uitzetten, dan voedde de batterij het huis in de goedkope uren en laadde de coach hem daarna weer bij,
met het verlies twee keer; zo ging het in het virtuele huis zeventien keer aan en uit in een nacht.

**Het vinkje eraf** zet het laden van het net eruit, en daarna schrijft hij niets meer. Bij een herstart
van Home Assistant niet: daarna schrijft de coach meteen opnieuw, en twee opdrachten vlak na elkaar
faalt de tweede. Zonder het vinkje (de schaduw) schrijft hij niets en noteert hij op dezelfde momenten
"zou dit schrijven" met het schema erbij, alleen bij andere vakken of aan en uit.

**Zelf geleerd** (`_async_growatt_leren`, bewaard in `battery_state`; een meting gaat voor een opgave,
net als bij het rendement):

* de inhoud: per stuk alleen laden van minstens 10% wat de eigen teller "geladen" per procent opliep
  (`growatt_kwh_pct`, `growatt_inhoud`, de mediaan na drie stukken). In de klantwoning ongeveer 12 kWh
  per 100% tegen 15,3 op het typeplaatje;
* het laadvermogen bij 100%: in een vak dat de coach schreef en dat teruggelezen klopte, zonder zon,
  wat hij laadt gedeeld door het deel in het schema (`growatt_w_pct`, `growatt_max_w`, de mediaan na
  zes metingen). Tot dan wat de installateur invulde, of anders het hoogste dat de coach hem ooit zag
  laden (`growatt_in_w`): een ondergrens, dus eerder te snel dan te langzaam. Zonder dat laadt hij niet
  van het net en zegt de kaart het;
* wat hij eruit kan: ingevuld, of het hoogste dat de coach hem zag ontladen (`growatt_uit_w`), en
  zolang hij dat nog niet zag het hoogste uur uit de statistiek van Home Assistant (v0.161.0);
* zijn vloer: de accustand waarop hij stil staat terwijl het huis van het net haalt, buiten een vak
  (`growatt_vloer`). Die staat in geen entiteit; in de klantwoning 15%, terwijl het ontlaadschema 10
  zei.

Het kasboek ("Opgeleverd") boekt hij eens per ronde met de sensor van de batterij (`_kasboek`, sinds
v0.150.0 uit de regelaar gehaald). Vol laden, leegladen en de vakantiestand op de kaart blijven bij een
Growatt niet beschikbaar; `alleen_lezen` op de sensor voor DomotiApp Lovelace is waar tot de coach er
een schema in schrijft.

**In het virtuele huis** (`growatt-bihorario`, `growatt-zon`, `growatt-schaduw`; een Growatt met een
schema, sensoren eens per vijf minuten, en een tweede schrijfactie binnen een minuut die faalt): op een
donkere dag met bi-horário sinds v0.152.0 drie schrijfacties in 29 uur, laden vanaf 02:30 tot 09:00 (de
coach rekent de eerste nacht met het laadvermogen dat hij op zon zag, een ondergrens, dus de echte
Growatt laadt sneller), om 09:00 op 97%, in vazio 0,08 kWh uit de batterij, en € 2,91 tegen € 4,13
zonder batterij (v0.151.0: uitgesmeerd over vazio, € 2,98). Op een bewolkte dag vult de
zon hem en laadt hij de eerste nacht niet van het net. Proef 50 in test_batterij.py, 192 in
test_coach.py.

**Nog niet:** een MIN (blijft alleen uitlezen tot iemand er een gezien heeft). Vol laden en leegladen
vanaf de kaart komen er bij een Growatt bewust niet (v0.156.0, zie onder). Ontladen stuurt de coach bewust niet: de eigenaar op 23-10-2026, "ontladen gaat zoals
de omvormer het nu zelf doet"; in de uurdata van de klantwoning kostte 's nachts vasthouden precies
hetzelfde, want daar is de accu aan het begin van vazio al leeg. In het echt nog niet
beproefd: of de omvormer zelf op de stopgrens stopt, en of hij met mains uit toch van het net bijlaadt
bij zijn vloer (in de klantwoning stond `acChargeEnergyToday` vóór de test al op 2 kWh).

## Growatt, stap 2: de zon en het schema na elke nacht bijstellen (v0.151.0)

De eigenaar op 23-10-2026, via de beheersessie: "Sven wil alles: bouw stap 2 ook, niet wachten op de
schaduw van stap 1." De zon zonder paneelgegevens staat in `docs/laadpaal.md` (het geldt voor de paal
net zo goed). Hier het bijstellen.

**Na elke nacht nakijken** (`_async_growatt_nacht` in coach.py). Vanaf het eind van een vak dat de coach
schreef tot het begin van het volgende telt hij, elke ronde:

* in het vak: wat er van het net de batterij in ging;
* erna: zon die naar het net gaat terwijl de batterij vol is (te veel van het net geladen, want die zon
  had erin gekund), en wat het huis van het net haalt terwijl de batterij op zijn vloer staat (te weinig).

Begint het volgende vak, dan gaat `growatt_nacht` (te weinig min te veel, waarbij te veel nooit meer is
dan wat er van het net in ging) als één getal in `growatt_nachten` (14 bewaard). `growatt_bijstelling`
neemt daar de mediaan van de laatste zeven van, vanaf drie nachten en nooit meer dan de inhoud, en
`growatt_schema` laadt zoveel meer of minder dan het plan: het vermogen en de stopgrens schuiven mee,
de vakken niet. Eén nacht met een feest of een dag zonder zon bepaalt het dus niet. Proef 51 (de som) en
193 (het tellen).

## Growatt: de eerste echte nacht, en wat daaruit kwam (v0.156.0)

De klantwoning stuurde vanaf 23-10-2026 23:53 echt. Geschreven: laden van het net 06:00-08:00, 15%, tot
32%. Gemeten: tot 06:00 op de vloer (15%), van 06:00 tot 07:57 laden op ~1,2 kW tot 35% (2,4 kWh), van
08:00 tot 08:55 1,0 kWh ontladen voor het huis, vol om 13:31 en daarna teruglevering. Het schema deed
wat het moest. Vijf dingen klopten niet; alle vijf zijn in v0.156.0 opgelost.

**De nacht telde het tekort ook in de goedkope uren.** Na die eerste nacht stond er +11 kWh in
`growatt_nachten`: het huis haalde van 23:53 tot 06:00 op de vloer van het net, in vazio, en dat telde
als "te weinig". Na drie nachten had de mediaan het schema elke nacht ruim 10 kWh extra laten laden.
Nu telt het tekort alleen in een uur dat duurder is dan het goedkoopste van het komende etmaal
(`growatt_duur`), en tellen de nachten van voor v0.156.0 niet mee (`growatt_nachten`, met
`growatt_nachten_v` in `battery_state`).

**Het besluit wisselde elk kwartier.** Van 06:15 tot 07:45 twaalf besluiten: in de laatste minuut van
elk kwartier zag het plan laden, daarna weer vasthouden, terwijl de Growatt gewoon zijn schema afwerkte.
Nu komt het besluit uit het schema (`growatt_besluit` in batterij.py): in een vak om te laden "laden van
het net" met de stopgrens en het eind in de reden, in een vak om vast te houden "standby", daarbuiten
nul op de meter. Met de coach aan het stuur is dat het schema dat erin staat, in de schaduw wat hij zou
schrijven. Het plan per kwartier blijft de som erachter (`sessie["besluit"]`). Een vak tot 23:59 dat om
00:00 doorgaat telt in die laatste minuut mee. In het virtuele huis van twaalf naar drie à vijf
besluiten per nacht.

**De conclusie zei "tekort, dat komt van het net".** Bij een schema zegt de laatste zin van de nachtzin
wat het schema doet ("In de goedkope uren laadt hij 2,3 kWh van het net bij (06:00-08:00), tot 32%"),
zonder oranje, en staat "Morgenvroeg" niet in de pop-up: dat tekort telde de goedkope uren mee
(`conclusie` in `_vooruitkijk_zin`). Zonder schema blijft de gewone conclusie.

**De Growatt-API weigerde elk vasthouden.** Om 07:45 (1%, stopgrens 32, het laatste kwartier van vazio)
en om 21:31 en 21:36 (1%, stopgrens 27, 22:00-08:00): "Growatt API error: Error during writing AC charge
time periods". De schema's om te laden (15% en 22%, stopgrens boven de accustand) kwamen wel aan.
Het is het vermogen (v0.156.1): de beheersessie schreef om 22:37 hetzelfde vasthouden met 10% en de
stopgrens op de accustand (22%), en dat nam hij meteen aan, 53 seconden na een geslaagde opdracht van de
coach. Een grens van één opdracht per vijf minuten is het dus niet; van de schema's zonder 1% werd er die
dag één van de vijf geweigerd (22:31), wat een hapering van de cloud lijkt. Vasthouden gaat sindsdien op
`GROWATT_HOUDEN_PCT` (10%). De twee vangnetten blijven: van laden naar
vasthouden in hetzelfde vak schrijft de coach niet meer voor minder dan `GROWATT_HOUDEN_KWH`, of als hij
op de stopgrens al stilstaat (en sinds v0.156.1 andersom: van vasthouden naar laden in hetzelfde vak ook
pas vanaf een halve kWh; met 10% schreef hij in het virtuele huis om 08:57 nog laden op 100% voor de
laatste drie minuten, en ging de zekering eroverheen); en drie keer geweigerd vasthouden laat de coach voor dat goedkope stuk
weg (`growatt_houden_mis`, `vasthouden` in `growatt_schema`), met een regel in de geschiedenis.

**De melding "hij laadt vannacht niet van het net"** kwam om 07:55 op de telefoon, terwijl hij al
geladen had. Een geweigerd schema gaat nu alleen naar de telefoon als wat er nog in staat anders van
het net laadt dan wat de coach wilde; anders alleen in de geschiedenis. En zonder "vannacht".

**De kaart** (de eigenaar op 23-10-2026, met een schermafdruk): de stand in de taal van het paneel
(`standNaam` in plaats van `mode_name`, het Nederlands van de coach), het schema in plaats van de
blokken van het plan ("Laadt van het net 06:00-08:00, tot 32%, ongeveer 2,3 kWh" of "Houdt vast
22:00-08:00, op 24%"; `schedule.hold` is nieuw), en geen "Opdracht van de coach" (`setpoint_w` is bij
een Growatt leeg). In een lopend vak toont de kaart het schema dat in de Growatt staat, daarbuiten wat
de coach erin gaat zetten.

**Geen vol laden en leegladen.** De eigenaar op 24-10-2026: "knoppen weg want ik wil niet kunnen
handmatig laden en ontladen bij growatt". De knoppen staan er niet bij een Growatt (`isSchema` in
overview.js), en een opdracht die toch binnenkomt laat de coach meteen vallen.

Proef 54 in test_batterij.py, 196 in test_coach.py, de proef "de kaart van een Growatt" in
test_rapport.mjs, en "het besluit wisselt niet elk kwartier" in test_virtueel.py.

## Het setpoint binnen het bereik van de knop van dat moment (v0.157.0)

Een Anker Solix maakt het bereik van zijn vermogensknop kleiner als hij bijna vol is. In
een klantwoning op 25-10-2026 om 14:55, op 99%, ging de `max` van 10000 naar 1428 W; de
regelaar schreef 2376 W, Home Assistant weigerde dat met een `ServiceValidationError`, en de
regelaar struikelde. Een uur later stond er weer 10000.

`_async_batterij_zetten` leest nu vlak voor het schrijven `min` en `max` van de knop en
houdt het getal daartussen, met een richting-entiteit (zonder teken) en met een teken
(ook `setpoint_invert`). Een knop zonder `min` en `max` krijgt het getal zoals het was.
Het lage `max` wordt nergens onthouden: `max_charge_w` komt elke ronde opnieuw uit de knop
(`uit_knop` in `_batterij_van`), dus alleen de som van die ene ronde rekent met minder.
Proef 198 in test_coach.py.

## Een volle batterij die zelf nul doet blijft vol zolang de volle beurt open staat (v0.158.0)

Een batterij die zelf nul op de meter doet kan in zijn eigen stand niet stilstaan, en
daarom liet de som voor hem stilstaan nooit toe (`_zelf_toegestaan`). Op het bovenste
punt van de som bleef er dan maar één ding over als het huis stroom vroeg: ontladen. Op
de dag van de wekelijkse volle beurt moest hij daarna weer bijladen, en zo sloeg hij om.

In een klantwoning op zondag 25-10-2026: om 09:40 van het net van 5 naar 95% om 14:00, en
daarna van 14:30 tot 16:00 acht wissels tussen nul op de meter en laden van het net, elke
keer met de Anker naar zijn eigen stand en terug, en kort ontladen van 1 tot 2,8 kW. Van
95 naar 98% duurde ruim twee uur.

Nu mag een batterij met een stuurgetal (`vol_vasthouden`; de coach neemt hem over en zet
0 W) op het bovenste punt van de som stilstaan als het huis stroom vraagt, zolang de volle
beurt nog open staat (`_vol_open`: er is een `vol_voor` en die komt nog). Het besluit is
dan `vasthouden`. Is de beurt geboekt, dan voedt hij het huis weer gewoon. Een Growatt
houdt zijn eigen regel (`vol_vasthouden` staat daar uit).

Eerst stond het vol blijven open voor elk duurder blok verderop, zoals bij een Growatt.
Dat brak batterij-kwartier-zelf: bovenin staan werd elk middaguur waard, hij laadde 's
middags vol van het net en hield dat vast door de dure avond, voor de nog duurdere uren
van de volgende dag (21,2 kWh erin, € 6,62 tegen € 2,94 zonder batterij, eindigend op 95%).

Proef 55 in test_batterij.py, en het scenario batterij-volle-beurt-zelf (de prijzen van
die middag): zonder 13 richtingwissels, vijf keer de modus om en bovenin blijven hangen op
98,3%; met 3 wissels, om 17:00 op 99% en daarna het huis voeden in de dure avond.


## De nachtzin zegt waarom hij niet bijlaadt (v0.159.0)

In de klantwoning op 25-10-2026 om 21:33 (Growatt, een nacht van € 0,166 tot 08:00 en daarna
€ 0,272) stond de batterij op de vloer en eindigde de kaart met "bijladen kost via de batterij
minstens € 0,184 per kWh". De eigenaar: "waarom gaat hij niet laden en houdt hij de batterij niet
vast tot het dure uur dat om 8 uur begint?" Die € 0,184 stond naast niets, en naast € 0,272 leest
hij als een fout. Het plan had een goede reden: het tekort viel in de nacht zelf, die goedkoper was
dan dezelfde stroom via de batterij, en vanaf 09:00 laadde hij op zon tot 100% om 14:00. De som
zette een kWh erbij op € 0,150 (`buy_below`), onder de € 0,166 van de nacht.

Nu zegt `_bijladen_zin` dat zelf, met de grens van de som (`inkoop_tot`) erbij, in één zin:

- valt het tekort vanaf het goedkoopste uur alleen in uren die niet duurder zijn dan dat uur
  gedeeld door het rendement: "dat komt van het net tegen € 0,166, goedkoper dan via de batterij
  (€ 0,184 met het verlies)";
- anders, als de grens van de som onder de goedkoopste prijs ligt: "dat komt van het net tegen
  € 0,200, want een kWh erbij loont pas onder € 0,150";
- en komt hij morgen op zon aan zijn laadgrens, dan het moment erbij: "en om 14:00 is hij op zon
  vol (100%)", of na de grens ": om 14:00 is hij op zon vol (100%)";
- zegt de som dat bijladen wel loont en laadt hij toch niet (een stap van het rooster, een grens
  van de batterij), of is er geen grens, dan blijft de zin van v0.102.3.

Wat voor het goedkoopste uur valt telt niet mee: dat haalt bijladen toch niet meer in. Voor elke
batterij, ook een Growatt zonder schema voor vannacht (`growatt_besluit`), en met vaste tijdvakken of
dynamische prijzen. Proef 37 in test_batterij.py.

## De zon binnen het uur, en een ondergrens aan bijladen (v0.160.0)

In de klantwoning op 26-10-2026 (Growatt, tijdvakken: nacht € 0,166 tot 08:00, daarna € 0,272,
rendement 0,901) was de batterij om 21:28 leeg. De coach laadde 's nachts niet bij voor het dure uur
van 08:00, want hij zag daar 0,1 kWh tekort (zon 2,95, huis 3,06 kWh). Er kwam 0,8 kWh van het net;
vanaf 08:45 draaide er een apparaat, en zonder dat was het ongeveer 0,3.

**De zon binnen het uur.** Tot v0.160.0 kreeg elk kwartier een kwart van de zon van zijn uur
(`_netto_huis_kwh`). In het eerste zonuur loopt de zon op, dus het tekort aan het begin van de dag
leek kleiner dan het was, en aan het eind van de middag net zo. Nu loopt het vermogen binnen een uur
recht op of af, met de helling van het uur ervoor naar het uur erna (`zon_tussen` in planner.py); een
heel uur houdt zijn eigen opbrengst, en het vermogen komt nooit onder nul. Voor dat uur van 08:00
geeft dat 0,53, 0,67, 0,81 en 0,95 kWh per kwartier, en 0,34 kWh tekort in plaats van 0,11. De paal
rekent met dezelfde verdeling (`overschot_tussen`). Met kwartierprijzen kreeg die tot dan de hele zon
van het uur in het eerste kwartier, omdat de verwachting per uur staat en hij die op het begin van
het kwartier opzocht.

**Een ondergrens aan bijladen.** De eigenaar op 26-10-2026: bijladen van het net pas als het verwacht
meer dan € 0,05 oplevert, tegen een verwachting die net niet uitkomt. Een keuze, geen meting. Het is
een instelling van de batterij (Instellen, Handelen: "Alleen als het minstens oplevert", leeg is
€ 0,05, nul is geen grens; `grid_charge_min_gain`, `BIJLADEN_MIN_WINST` in const.py).

De som toetst het per laadbeurt en niet per kwartier (`_bijladen_loont`): vanaf het eerste blok
waarin het plan van het net laadt tot het plan de batterij weer laat leveren, de som zonder laden van
het net in die tijd naast die met. Levert dat minder op dan de grens, dan rekent hij verder alsof hij
daar niet van het net mag laden (`net_laden_vanaf`), en zegt de kaart waarom: "dat komt van het net,
want bijladen zou € 0,026 opleveren, minder dan de ondergrens van € 0,050." Een latere beurt toetst
hij als hij aan de beurt is; zo telt een beurt aan het eind van de bekende prijzen niet mee bij de
ochtend van nu. Een beurt die al loopt maakt hij af (de vorige ronde laadde hij van het net, of hij
laadt nu zonder zon over), want aan het eind levert de rest altijd weinig op: zonder dat schreef de
Growatt in `growatt-bihorario` vanaf 04:10 elk half uur een nieuw schema. Laden om terug te leveren is
ook laden van het net, dus de grens geldt daar evengoed.

In het virtuele huis: `growatt-ochtend` (de ochtend van 26-10, met de grens) laadt 's nachts niets en
schrijft twee keer een schema, voor € 0,775; `growatt-ochtend-zonder-grens` laadt 1,03 kWh bij,
schrijft vijf keer, voor € 0,748. In `batterij-kwartier-zelf` levert de nachtbeurt € 0,022 op; met de
grens slaat hij hem over en kost de dag € 2,15 in plaats van € 2,45, met 21 opdrachten in plaats van
108. Dat scenario en `batterij-kwartier-voorloper` staan op nul, want ze zijn er voor de nachtbeurt
zelf. Proef 56 in test_batterij.py.

## Een Growatt die de coach nog nooit zag ontladen (v0.161.0)

Wat een Growatt eruit kan leert de coach door te kijken (`growatt_uit_w`). Zolang hij dat niet
zag, rekende de som met 0 W eruit: de batterij kon in het plan niets leveren, dus laden van het
net leverde ook niets op, en sinds de ondergrens aan bijladen (v0.160.0) laadde hij dan nooit van
het net. Bij een nieuwe klant die 's avonds leeg begint kan dat dagen duren, want zonder bijladen
ontlaadt hij pas na een dag met genoeg zon. Gevonden bij het bouwen van v0.160.0; in de klantwoning
was het ontlaadvermogen al geleerd.

Nu kijkt de coach zolang er geen meting is eens per dag in de statistiek van Home Assistant
(`_async_hoogste_ontladen`): het hoogste uur van de sensor voor ontladen over de laatste dertig
dagen (`GROWATT_TERUGKIJK_DAGEN`), of het laagste van een sensor met een teken. Dat is wat de
batterij vóór de coach deed, dus een meting en net als `growatt_uit_w` een ondergrens. Staat het er
ook niet in, dan blijft het 0 W en zegt de kaart waarom hij niet van het net laadt, zoals bij een
onbekend laadvermogen. Proef 200 in test_coach.py.
