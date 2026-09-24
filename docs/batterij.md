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
het rendement per vermogen gemeten is, en dat is het nog niet.

**Het rendement is een meting of een opgave, nooit een aanname.** In de eerste
woning kwam van elke kilowattuur die de kWh-meter op de batterij erin zag gaan
73,6% er weer uit.
De eigen tellers van die batterij telden meer eruit dan erin,
want die meten aan de accukant. `rendement_uit_tellers` wil tien keer de inhoud
aan doorzet (`RTE_MIN_DOORZET`) en weigert alles buiten 30 tot 100%. Zonder
rendement wordt er niet gepland: alleen nul op de meter (`rendement-onbekend`),
en met volledig salderen standby, want dan verliest opslaan altijd.

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
- **Welke uren de auto kiest verandert niet.** De batterij helpt zodra de paal laadt,
  tot zijn grens, in welk uur dat ook is; hij maakt geen uur goedkoper dan een ander.
  Wat verandert is hoeveel er van het net komt. Dat is het antwoord op "mogelijk van
  invloed op de laadstrategie".

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

**Het kasboek en de terugverdientijd.** `verdiend` is per stap het verschil
tussen de rekening zoals hij loopt en zoals hij zonder batterij gelopen had (de
meter min wat de batterij doet); het rendement zit er vanzelf in. Het gaat per
dag naar `battery_state` in de instellingen. `terugverdiend` noemt pas een datum
na `TERUGVERDIEN_MIN_DAGEN` en zegt over hoeveel dagen hij gemeten heeft. Wat de
batterij verdiende voordat de coach erbij kwam wordt niet geschat.

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
