# Het contract: leveranciers, de prijsopbouw en de controle

Uit de eisen van de eigenaar en de werkafspraken in `CLAUDE.md`; die gaan boven alles
hier. Komt er bij een uitgave iets bij over dit onderwerp, schrijf het dan hier.

## Waarom (v0.129.0)

In de eerste woning rekende de coach een maand met een terugleverprijs van niets: in beide
prijsvelden stond dezelfde all-in sensor, salderen stond uit, en Handelen kon daardoor nooit
(v0.128.2 zegt dat sindsdien op de kaart). Historie telde in die weken 319,3 kWh teruglevering
als € 0; met salderen was dat € 93,24 geweest, zonder € 48,92. De energiebelasting stond nog
op € 0,1088, het bedrag van 2024, omdat dat de standaard was.

De bewoner van de eerste woning op 18-10-2026: "Eigenlijk zou coach op de achtergrond
ingeregeld moeten hebben hoe de prijsopbouw is per energieleverancier", en "idealiter een
all-in prijs én kale sensor + additionele kosten/vergoedingen laten invullen. Indien het
resultaat overeen komt, krijg je automatisch de melding: de ingevoerde gegevens zijn
correct." De eigenaar: "ik wil dat je alle leveranciers uitzoekt", "ik laat de coach alles
vooraf invullen en de eindgebruiker moet de Ja-klap geven", en "Invullen, laten zien hoe de
prijs tot stand is gekomen in woord én cijfers, en het all-in resultaat tonen."

## De catalogus (`frontend/src/leveranciers.js`)

Per leverancier wat hij voor stroom en gas heeft (vast, variabel, dynamisch), en per soort
de velden die Contract voorinvult, de woorden voor de opbouw (de een zegt inkoopvergoeding,
de ander opslag), een zin over hoe de prijs en de teruglevering zijn opgebouwd, de bronnen,
de peildatum, en wat er onzeker bleef. Uitgezocht op 18-10-2026 van de sites, tarievenkaarten
en voorwaarden van de leveranciers zelf; waar alleen een vergelijker iets noemt staat dat bij
het bedrag. Gestopte leveranciers staan er niet in.

Sinds v0.129.1 de hele lijst: Zonneplan met de hand in leveranciers.js, de andere 44 in
leveranciers-data.js, omgezet uit het onderzoek van zeven groepen. Weggelaten: 16 gestopte
leveranciers, 5 die waarschijnlijk niet meer leveren, 9 die alleen zakelijk leveren,
coöperaties die doorverwijzen, en 2 zonder gegevens. Voorzichtig ingevuld: een opslag waarvan
niet zeker is of hij met of zonder btw is, of waarover bronnen elkaar tegenspreken, staat niet
in `velden` maar in `onzeker`, en Contract laat dat zien ("Niet zeker: ..."). Kiezen zet de
soort contract niet om: de lijst kan een soort missen, en dan zou hij een goede keuze
overschrijven.

**Het is een voorstel, geen rekenregel.** Kiezen vult de velden; wat er daarna staat is van
de klant, en de coach rekent alleen met die velden. Daarmee blijft de regel "nooit verzonnen
getallen" heel: elk bedrag is een instelling die de klant bevestigde, en de controle meet
elk uur of hij klopt.

`BELASTING` heeft de energiebelasting per jaar (Belastingdienst): stroom 2024 € 0,10880,
2025 € 0,10154, 2026 € 0,09161; gas 2026 € 0,60066 per m³, alles zonder btw. 2027 is
voorlopig (€ 0,08802 en € 0,61628, de Fiscale sleuteltabel 2027 na de tabelcorrectie van
1,026); definitief pas met de regeling van december.

## De opbouw en de controle (`prijsopbouw.py`)

`inkoop`: (kale marktprijs + energiebelasting + opslag) maal de btw. Een leverancier die zijn
opslag na de btw optelt (Zonneplan: "(EB + EPEX) x 1,21 + 0,02", Frank Energie net zo) is
rekenkundig hetzelfde met de opslag zonder btw (0,02 / 1,21 = 0,016529). De uitwerking zet
sinds v0.129.1 alles zonder btw en dan een regel btw, bij inkoop en bij teruglevering; de
eigenaar op 19-10-2026: "Doe alles mét, of alles zónder btw. Alles op dezelfde manier is
eenvoudiger vergelijken en checken." En de bewoner van de eerste woning: teruglevering
"identiek opbouwen als het overzicht van de afnameprijs", dus ook daar de kale prijs en de
energiebelasting en btw als eigen regel. Staat salderen uit voor 2027, dan zegt het blok
teruglevering dat het nog geldt (`salderenNoot` in opbouw.js).

`controleer`: die opbouw naast de all-in sensor, over alle blokken die allebei kennen (een
dag terug en wat er vooruit bekend is). Op de grofste van de twee: een leverancier per uur
tegenover Nord Pool per kwartier krijgt het uurgemiddelde. In de eerste woning op 18-10-2026
klopte dat in elk uur tot op een honderdste cent: Zonneplan = (gemiddelde van de vier
kwartieren + 0,10814) x 1,21. Tolerantie een tiende cent (`TOLERANTIE`). Bij een afwijking
zegt `vast` of het verschil elk uur even groot is: dan zit het in een bedrag per kWh. Met de
belasting van 2024 was dat in die woning 2,5 cent per kWh.

Sinds v0.144.3 telt de afronding van de lijsten mee (`afronding`): een halve laatste decimaal
van de all-in lijst, plus die van de marktprijs maal de btw, bovenop de tiende cent. De lijst
zegt zelf op hoeveel decimalen hij staat. Frank Energie geeft zijn toestand op vijf decimalen
en zijn lijst `prices` op drie; bij een klant op 20-10-2026 kwam de opbouw daardoor
€ 0,00103 naast de lijst uit (gemiddeld € 0,00003 over 192 kwartieren), en stond er
"Je energieprijs klopt niet meer" over een opbouw die op de toestand tot op de vijfde
decimaal klopte (0,25818 + 0,09161 + 0,015, maal 1,21, is 0,44140). De grens is daar nu
€ 0,0021; een energiebelasting van een ander jaar (2,2 cent) en een opslag die 0,2 cent te
hoog staat (0,35 cent) vallen er op dezelfde lijsten nog steeds uit.

`terug`: met salderen de all-in prijs min de opslag (die hangt aan de afname en komt niet
terug; uit een energienota van 27-08-2026), min de terugleverkosten, plus de vergoeding. Of,
met `netting_full` (v0.129.1), de hele all-in prijs: Essent en Energiedirect geven binnen
salderen "per uur hetzelfde tarief terug als je betaalt, inclusief btw, energiebelasting en
inkoopvergoeding", en ANWB, Oxxio en Zonneplan ook; hun aftrek of vergoeding geldt dan alleen
daarbuiten; zonder salderen de kale prijs (met btw
als `feed_in_vat`: Zonneplan betaalt in 2026 "de geldende stroomprijs exclusief
energiebelasting") min de kosten plus de vergoeding. In allebei een bonus in procenten
(`feed_in_bonus_percent`), over de marktprijs of over marktprijs plus vergoeding
(`bonus_base`), en eventueel alleen overdag (`bonus_daytime`, `zon_op_onder` met de ligging
van Home Assistant) en alleen als dat bedrag positief is. Het rekenvoorbeeld van Zonneplan
komt precies uit: € 0,08 + € 0,02 + 10% = € 0,11. De grens van 7.500 kWh per jaar telt de
coach niet.

Tot v0.129.0 rekende de terugleverprijs bij een all-in prijs per uur met het marktkwartier
dat op het hele uur begon; nu met het gemiddelde van de vier (`gemiddeld`).

**De kale marktprijs is vanzelf de reserve** (`_prijsbron` in coach.py): geeft de all-in
sensor geen prijs, dan rekent de coach met Nord Pool plus de velden, en omdat de controle
zegt of die velden kloppen is dat dan dezelfde prijs. Een oude reserve die een kale prijs
was wordt bij het laden het marktveld (`_migrate` in storage.py).

## Bevestigen

`contract/check` (websocket) geeft de opbouw van nu en de controle; Contract stuurt zijn
concept mee als de installateur kijkt, en zonder concept als de bewoner kijkt. `contract/confirm` legt vast wie
bevestigde, wanneer, en een vingerafdruk van de waarden (`vingerafdruk`): verandert er
daarna een bedrag, een sensor, salderen of de leverancier, dan geldt de bevestiging niet
meer. Eerdere contracten tellen niet mee, en 21 en 21.0 zijn hetzelfde. Iedereen mag
bevestigen; het verandert geen bedrag.

Wie wat ziet: de installateur kiest bij Contract de sensoren en ziet de opbouw met "Ja, dit
klopt". Sinds v0.130.1 ziet de bewoner dezelfde pagina, alleen lezen: de samenvatting per
bron, de opbouw met dezelfde knop, en de eerdere contracten als regels (`periodesLezen`).
Tot dan stond zijn kopie onder Voorkeuren; de eigenaar op 19-10-2026: "je energieprijs staat
nu in voorkeuren maar dat moet onder contract." Tot er bevestigd is staat er op het overzicht
"Klopt je energieprijs?" (`bevestigd` bij `domotiapp_coach/prices`), en die melding is zelf de
knop naar Contract. Er staat geen tabblad meer in de tekst: bij "Kijk onder Voorkeuren" zei de
bewoner van de eerste woning "voorkeuren ken ik niet", want op een telefoon staat dat tabblad
half buiten beeld. Om dezelfde reden heeft een prijsbericht in de berichtenbox een knop
"Bekijk je energieprijs" (`NAAR` in berichten-sheet.js).

## Contract per energiebron

De bewoner van de eerste woning: "Eerst álles uitvragen over elektriciteit (incl historische
contracten), dán pas alles over gas, en daarna pas water." De eigenaar: stroom dynamisch en
gas vast kan, en andersom, en "verschillende leveranciers zoals Vattenfall alleen stroom en
dan Frank gas". Dus `contract.gas` (soort, leverancier, prijs of sensor, looptijd, eerdere
contracten) en `contract.water` (prijs, eerdere) los van stroom. Wat er stond zet `_migrate`
over: `gas_price` en `water_price` worden de prijs van nu, en een gas- of waterprijs in een
eerder contract een eigen eerder contract met dezelfde datums.

Soorten: vast, variabel (de leverancier past de prijs aan, maandelijks opzegbaar; voor de
coach een vaste prijs tot de klant hem bijwerkt) en dynamisch. De looptijd (ingangs- en
einddatum) alleen bij vast. "Ik heb een nieuw contract afgesloten" zet het huidige bij de
eerdere, van de ingangsdatum tot gisteren, met de soort en de leverancier erbij, en begint
een leeg formulier dat vandaag ingaat. Een eerder dynamisch contract heeft geen vaste prijs:
Historie neemt die uit de prijssensor.

Dynamisch gas is een sensor met de all-in gasprijs; Historie neemt de prijs van elk vak uit
de statistieken ervan (`gasPrijzen` in `balans`).

## Historie

`prijsOp` in geld.js rekent bij een dynamisch contract de kale prijs van het vak terug uit
de all-in prijs en de velden, en daarmee teruglevering zonder salderen en de bonus overdag,
per vak in plaats van met het gemiddelde van vandaag. Alleen als de coach de terugleverprijs
kent (`terugleverBekend`). `tariff()` neemt de terugleverprijs van de coach over zodra die er
is, ook zonder reserve.

## Wat gelijk moet blijven

`prijsopbouw.py` tegenover geld.js: `zon_op_onder` en `zonOpOnder`, `overdag` en `overdag`,
`bonus` en `bonusOp`, `markt_terug` en `marktTerug`, `terug` en `terugOp`. Proeven:
test_prijsopbouw.py, proef 166 tot 168 in test_coach.py, en "geld.js rekent teruglevering en
de bonus zoals prijsopbouw.py" in test_rapport.mjs.

## Teruglevering apart: marktprijs of vast bedrag (v0.132.0)

Sommige leveranciers combineren een dynamische inkoop met een vaste terugleververgoeding. Uit
de voorbeelden die de eigenaar op 19-10-2026 stuurde (een andere energie-app, waar je inkoop
en teruglevering los kiest). Bij een dynamisch contract staat daarom onder Contract de keuze
**Teruglevering: Marktprijs of Vast bedrag** (`feed_in_mode`, `feed_in_fixed`).

- **Buiten salderen** is een teruggeleverde kWh dan het vaste bedrag min de terugleverkosten
  waard, wat de markt ook doet (`terug` in prijsopbouw.py, `terugOp` in geld.js). Een vergoeding
  bovenop de markt, een bonus in procenten en teruglevering met btw gaan over de marktprijs en
  staan dan niet op het scherm (`alleen-markt` in contract.js).
- **Binnen salderen** blijft het de inkoopprijs, zoals altijd: salderen is een regel van de wet en
  niet van de leverancier.
- Een vaste vergoeding is altijd bekend, dus een batterij kan handelen zonder kale marktprijs
  (`terugleverBekend` in geld.js; `_prices` in coach.py rekent hem zonder marktsensor).
- De opbouw toont "Vaste terugleververgoeding" en de kosten, met "Het vaste bedrag uit je
  contract" eronder (`terugRegels` in opbouw.js).

De twee nieuwe velden tellen pas mee in de vingerafdruk van "Ja, dit klopt" als ze iets anders
zeggen dan hun standaard (`LATER` in prijsopbouw.py). Anders gold na de update elke bevestiging
niet meer, terwijl er aan de prijs niets veranderde.

Proef 173 in test_coach.py, de vaste teruglevering in test_prijsopbouw.py, en twee proeven in
test_rapport.mjs.

## Teruglevering voor en na 1-1-2027, en salderen per afrekenperiode (v0.134.0)

De eigenaar op 19-10-2026, bij een vast contract met salderen aan (all-in € 0,24171,
vergoeding € 0,0721, terugleverkosten € 0,052756) en "Teruglevering (je saldeert: je
inkoopprijs min de kosten) € 0,1890": "ik had verwacht dat mijn teruglevering is:
0,0721-0,052756". Daarna liet hij de prijsopbouw van zijn leverancier zien en twee
jaarafrekeningen. Daarin stonden drie dingen die de coach niet kende.

**Twee terugleverprijzen in één contract.** "Terugleververgoeding na saldering tot 1-1-2027
€ 0,124000", "Terugleververgoeding vanaf 1-1-2027 € 0,072100" en "Terugleverkosten vanaf
1-1-2027 € 0,052756 per kWh"; tot dan waren de terugleverkosten een vast bedrag per schaal.
De bedragen die hij had ingevuld waren die van na 1-1-2027, en met één veld rekende de coach
óf nu met de kosten van 2027, óf in 2027 met de vergoeding van nu. Een vast contract heeft
daarom bij Contract een blok "Vanaf 1 januari 2027" (`feed_in_tariff_after`,
`feed_in_costs_after`); leeg is hetzelfde als erboven. Vanaf `NETTING_ENDS` rekent de coach
daarmee (`_teruglevering` in coach.py), en Historie ook (`vasteTeruglevering` in geld.js). De
opbouw laat het als eigen blok zien (`na_salderen` bij `contract/check`, `naSalderenBlok` in
opbouw.js), zolang het contract na die datum nog loopt. Alleen bij vast en variabel: een
dynamisch contract volgt de markt, en wat de leverancier daar per 2027 verandert vult de klant
dan in. "Ik heb een nieuw contract afgesloten" maakt het blok leeg.

**Vaste terugleverkosten per schaal horen niet in de kosten per kWh.** Een vast bedrag per jaar
naar de schaal van de teruglevering (de tabel van de leverancier: 0 tot 500 kWh niets, daarboven
stappen van 250 of 500 kWh) verandert niet met elke kWh. Op de jaarafrekening werd de schaal
bepaald op wat er in het stuk van de afrekenperiode onder het nieuwe contract terugging, niet
omgerekend naar een jaar: 235 kWh in veertien dagen was schaal 1, € 0. Tot 1-1-2027 is dat stuk
voor de meeste huizen een najaar, onder de 500 kWh. Dus 0 per kWh tot 1-1-2027, en de hint bij
het veld zegt dat.

**Salderen telt per afrekenperiode, ook over een nieuw contract heen.** De jaarafrekening liep
van half september tot half september; het contract wisselde op 1 september, en de saldering
ging over de twee samen. Pas wat er aan het eind van die periode meer terugging dan er werd
afgenomen kreeg de vergoeding, verdeeld over de twee contracten. De begindatum staat bij Contract
(`billing_start`, "Je afrekenperiode begon op", alleen met salderen aan en voor 1-1-2027). Een
datum van langer dan een jaar geleden schuift per jaar op (`_afrekenstart`).

De coach rekent eens per dag (`_async_jaarsaldo`): wat er sinds die datum van het net kwam en
terugging, uit de kWh-tellers van de meter (`meters` onder Installatie) via de statistiek van
Home Assistant, plus wat er tot `NETTING_ENDS` nog bij komt, gemeten op dezelfde dagen een jaar
eerder. Levert het huis zo over de periode netto terug, dan saldeert een teruggeleverde kWh niet
meer (`_saldeert`), en rekent hij met de vergoeding na saldering min de kosten (vast, `_tarief`)
of met de marktprijs (dynamisch, `prijsopbouw.terug` zonder salderen). Zonder begindatum, zonder
tellers of zonder metingen van vorig jaar is het onbekend, en telt het vinkje.

In v0.133.3 (niet uitgebracht) was dit het afgelopen jaar. In de woning van de eigenaar
scheelden afname en teruglevering daarover op 19-10-2026 nog geen 0,2 procent, met de zomer van
het vorige contract erin: een schakelaar die elke dag kon omslaan, over een periode die niet
telt. Met de afrekenperiode en de verwachting voor de rest beweegt de balans per dag alleen met
wat die dag anders ging dan vorig jaar. Er zit geen marge op: wie er precies op de rand zit, voor
die zijn beide prijzen even goed.

Het vinkje zelf blijft wat het is (`salderen` in `contract/check`): de opbouw zegt erbij waarom,
met de kWh van de periode en van de verwachting (`jaarNoot` in opbouw.js). De inkoopprijs blijft de
all-in prijs.

Wat nog niet: Historie rekent per uur met het vinkje en niet met de afrekenperiode, en een schaal
als vast bedrag per dag staat niet in Historie.

Proef 175 in test_coach.py; in test_rapport.mjs "de opbouw zegt of je over je afrekenperiode
netto teruglevert" en "Historie: een vast contract rekent na 1-1-2027 met wat het contract voor
daarna zegt"; in het virtuele huis `vast-na-salderen` en `vast-na-salderen-leeg`, op 4 januari
2027: de zon in de bus kost € 0,30 (15,4 kWh maal 0,0193) en zonder de bedragen voor na
salderen € 1,91 (maal 0,124).

## Terugleverkosten in vier vormen, en Historie per afrekenperiode (v0.135.0)

De eigenaar op 19-10-2026, na v0.134.0: "je mag alles maken, ik wil het zo goed mogelijk
hebben". Drie dingen die toen nog openstonden.

**Terugleverkosten in vier vormen** (`feed_in_costs_mode`, bij vast en bij dynamisch). De catalogus
kent ze alle vier:

| vorm | wat een kWh extra kost | voorbeelden in de catalogus |
|---|---|---|
| `kwh` | het bedrag, over alle teruglevering (de standaard, en tot v0.135.0 de enige) | Eneco sinds juni 2024 |
| `overschot` | het bedrag alleen als hij niet wegstreept tegen afname | |
| `schalen` | niets; een vast bedrag per jaar naar de schaal van de teruglevering | Budget (26), Energiedirect (42), Vattenfall (73) |
| `geen` | niets | ANWB, Coolblue, easyEnergy |

Eén regel, `kosten_per_kwh` in prijsopbouw.py, met de tweeling `kostenPerKwh` in geld.js; de coach
gebruikt hem in `_teruglevering`, `prijsopbouw.terug` en het geld van een laadbeurt. Bij Contract
kies je de vorm; bij schalen staat er een tabel (`feed_in_scales`: vanaf hoeveel kWh, het bedrag per
jaar met btw; onder de eerste rij niets) en een einddatum (`feed_in_scales_until`; leeg is de hele
afrekenperiode). De catalogus vult bij Budget, Energiedirect en Vattenfall, vast en variabel,
"schalen" tot 1-1-2027 voor: alle zes de beschrijvingen zeggen dat het vanaf 2027 per kWh gaat. De
tabel zelf vult de klant of de installateur in. De opbouw zegt wat de vorm betekent (`kostenNoot` in
opbouw.js). Na 1-1-2027 gaan de kosten van na salderen (`feed_in_costs_after`) per kWh over alles.

**De schaal.** Uit de productvoorwaarden van een vast contract van Vattenfall (Groen uit Nederland
Vast, 6127_013), die de sessie op thuis op 19-10-2026 in de contractbevestiging van de eigenaar las:
een afrekening over een periode die deels vóór 1-1-2027 ligt saldeert "vanaf uw vorige jaarafrekening
tot 1 januari 2027", en "In welke terugleverschaal u valt, wordt dan vastgesteld op basis van de door
u in deze periode teruggeleverde elektriciteit"; "De vaste terugleverkosten komen vanaf dat moment
te vervallen." En de schaal gaat over alle teruglevering, ook wat saldeert (bruto). Dus de schaal
naar de teruglevering van het begin van de afrekenperiode onder dit contract (het laatste van
`billing_start` en de ingangsdatum) tot de einddatum van de schalen: gemeten tot vandaag, plus
dezelfde dagen een jaar eerder (`async_afrekening` in coach.py, `schaal_per_jaar`). Mijn Vattenfall
schatte op dezelfde dag "Schaal 20 (6500 t/m 7000 kWh) € 833,00" over de hele afrekenperiode; dat
rekent daar nog niet mee.

**Wat niet vaststaat:** of een leverancier het jaarbedrag van een schaal voor een kortere periode
naar rato rekent. De voorwaarden zeggen alleen dat de schaal op de teruglevering in die periode
wordt bepaald. Historie rekent het jaarbedrag per dag (gedeeld door 365, `schaalKosten` in geld.js),
over de dagen die voorbij zijn, zoals Budget en Energiedirect hun schalen per dag rekenen. Een kWh
extra kost voor de coach hoe dan ook niets.

**Historie per afrekenperiode.** Tot v0.135.0 telde Historie met salderen aan elke teruggeleverde
kWh als gesaldeerd. Op de jaarafrekening van de eigenaar ging het per afrekenperiode: de
teruglevering streept weg tegen de afname, en wat er overblijft krijgt de vergoeding na saldering,
naar rato over de contracten in die periode (29 kWh werd 27 maal de oude en 2 maal de nieuwe
vergoeding, naar wat er onder elk contract terugging). `domotiapp_coach/afrekening` (websocket.py,
`async_afrekening`) geeft per afrekenperiode die het getoonde stuk raakt het deel dat wegstreept
(`gesaldeerd`: afname gedeeld door teruglevering, hooguit één), voor de periode van nu met de
verwachting tot 1-1-2027. Historie rekent elke teruggeleverde kWh voor dat deel als de inkoopprijs
en voor de rest als de vergoeding na saldering (`aandeelOp`, `prijsOp` met `aandeel` in geld.js), en
trekt de schaal per dag af van wat teruglevering opleverde (`vasteKosten` in `balans`). Zonder
begindatum, tellers of metingen van het begin: het vinkje, zoals tot nu. Onder In geld staat het in
een zin, met het percentage en de schaal.

**Het virtuele huis** prijst een moment nu met `_tarief` en niet `_tariff` (`_prijs_nu`), zodat het
rekent zoals de coach het ziet, ook met de jaarbalans (`netto_terug` als scenarioveld, `jaarbalans`
in virtueel.py). Scenario's: `vast-kosten-per-kwh` (de zon in de bus kost 0,25 min 0,05),
`vast-kosten-schalen` en `vast-kosten-overschot` (0,25), `vast-kosten-overschot-netto-terug` (0,12
min 0,05), en `dynamisch-salderen-vol` naast `dynamisch-salderen` (de hele all-in prijs terug is
meer waard). Proef 176 in test_coach.py, de vormen en de schaal in test_prijsopbouw.py, en
"terugleverkosten in vier vormen, en Historie per afrekenperiode" in test_rapport.mjs.

## Opnieuw uitrekenen met het contract van toen (v0.136.0)

De eigenaar op 19-10-2026, nadat zijn contract was rechtgezet: "Kan je dan ook de prijzen die
eerder genoemd werden in de coach aanpassen de historie want ik denk dat dat dan ook niet meer
klopt?" Historie In geld rekent elke keer opnieuw met het contract, ook met de eerdere contracten.
Twee dingen bewaren een bedrag van toen: elke beurt in Sessies (`BeurtenStore`) en het kasboek van
een thuisbatterij (`battery_state`).

**De beurten.** Contract heeft onder de eerdere stroomcontracten "Laadbeurten en programma's
opnieuw uitrekenen", vanaf een dag, eerst als voorbeeld en dan Overnemen (`savings/recalculate`,
`async_herreken_beurten` in coach.py). Alleen bij een vaste prijs, van nu of van een eerder contract
van die dag: dan is de prijs over de hele beurt dezelfde, en volgt alles uit de kilowatturen die de
beurt al telde (`_herreken_beurt`): wat niet van de zon kwam tegen de inkoopprijs, de zon tegen wat
teruglevering had opgebracht, de maat alles van het net. Een beurt bij een dynamische prijs blijft
zoals hij was, want een beurt bewaart niet wanneer hij welke kWh nam. Lopende beurten ook.

**De prijs van toen** komt uit `_vast_op` in coach.py: een eerder contract van die dag gaat voor,
anders het contract van nu met salderen naar het vinkje en de datum (in de lopende afrekenperiode
zoals `_saldeert`), en na 1-1-2027 de bedragen van na salderen. Dat volgt `prijsOp` in geld.js,
zonder de verdeling per afrekenperiode. Bij salderen trekt hij de kosten per kWh van het contract
van nu af (`kosten_per_kwh`), net als `prijsOp`.

**De batterij.** "Opgeleverd opnieuw uitrekenen" (v0.130.1) rekende bij een vast contract elk
kwartier met het tarief van nu, ook van voor een contractwissel. Nu ook met `_vast_op`.

In de woning van de eigenaar zag het er na het rechtzetten zo uit: met salderen is eigen zon
precies de inkoopprijs waard, dus bespaarde een beurt op zon niets meer, en verdiende de batterij
niets aan het verschuiven; alleen haar verliezen kosten geld. Opgeleverd ging van 28-09 tot
19-10-2026 van € 4,58 naar min € 6,27.

Proef 177 in test_coach.py, en "de eerdere contracten hebben hun inhoud in een eigen raster, en de
beurten zijn opnieuw uit te rekenen" in test_rapport.mjs. Die proef gaat ook over de eerdere
contracten zelf: een `<details>` legt zijn kinderen niet als raster uit, dus kwamen Van, Tot, de
prijs en Weghalen tegen elkaar aan te staan (de eigenaar: "weghalen staat niet lekker uitgelijnd",
"ook van tot etc staat niet mooi"). De inhoud staat nu in `.p-inhoud`.

## De schaal in de coach, met en zonder thuisbatterij (v0.137.0)

De eigenaar op 19-10-2026, toen bleek dat zijn batterij met salderen per kWh niets opbracht: "Dus je
zegt nu eigenlijk dat iedereen die een batterij heeft gekocht het voor niks heeft gekocht?" Per kWh
niet, zolang je saldeert en minder teruglevert dan je afneemt: een kWh zon opsparen is dan evenveel
waard als hem terugleveren, en de verliezen kosten geld. Maar een schaal hangt aan wat er terugging,
en wat de batterij opnam ging niet terug.

**Wat de coach uitrekent** (`_async_schaal`, eens per dag): de teruglevering van het stuk van de
afrekenperiode tot de einddatum van de schalen (`async_afrekening`: gemeten plus dezelfde dagen
vorig jaar), de schaal waar die in valt (`prijsopbouw.schaal_rij`, met de grenzen), en wat de
thuisbatterijen in die tijd tegenhielden (`_async_accu_vermeden`): per kwartier het net met en zonder
wat de batterijen deden, uit de eigen kwartieropslag. Contract zegt het onder de opbouw (`schaalNoot`
in opbouw.js): "Tot 1 januari 2027 naar verwachting 336 kWh teruglevering: de schaal van 0 tot 500
kWh, € 0 per jaar. Zonder je thuisbatterij 509 kWh: 500 tot 750 kWh, € 70 per jaar."

**Wat een kWh teruglevering dan kost** (`kosten_per_kwh`): komt het huis volgens die verwachting in
een duurdere schaal dan waar het nu staat, dan is dat verschil het werk van wat er nog teruggaat:
naar rato over de dagen van de periode, zoals Historie het jaarbedrag telt, en verdeeld over de
teruglevering die nog verwacht wordt. Blijft het huis in dezelfde schaal, dan kost een kWh niets.
`_tarief` (vast) en `_prices` (dynamisch) trekken het van de terugleverprijs af (`_minder`: een
positieve prijs niet onder nul), zodat de coach de zon dan liever zelf gebruikt. Historie rekent de
schaal zelf als jaarbedrag per dag (v0.135.0); dit is alleen wat de coach beslist.

In de woning van de eigenaar op 19-10-2026: 193 kWh terug sinds 15-09, 143 verwacht tot 1 januari,
samen 336: de schaal tot 500 kWh, dus niets per kWh. De batterij nam sinds 28-09 173,5 kWh op (haar
eigen teller); zonder haar had het huis de grens van 500 kWh gehaald.

**Twee metingen van de batterij die niet overeenkomen.** Haar vermogenssensoren gaven van 28-09 tot
19-10-2026 190,6 kWh laden en 163,8 ontladen, haar eigen kWh-tellers 173,5 en 161,2. De coach rekent
met de vermogens (Opgeleverd min € 6,27, ruim 26 kWh verlies); de tellers zeggen 12,3 kWh. Welke de
kant van de meter meet, is uit deze gegevens niet te halen.

Proef 178 in test_coach.py, de proef "de schaal met en zonder thuisbatterij" in test_rapport.mjs.

## Portugal (v0.137.0)

De eigenaar op 19-10-2026: "Hun wonen in portugal dus bij contract bovenaan wil ik dat je een land
kan kiezen dus Nederland en Portugal. Als je Nederland kiest dan heb je gewoon de invulvelden van nu
en Portugal gaat het even wat anders." Hun contract (een foto): EDP Comercial, bi-horário, met 6%
korting vazio 0,1340 en fora do vazio 0,2198 per kWh, potência 0,8543 per dag, EDP Smart 8,89 per
maand, en "Aos preços indicados acrescem quaisquer outros custos, encargos, impostos, taxas e
contribuições": de prijzen zijn zonder belastingen.

**Wat er anders is dan in Nederland** (uitgezocht op 19-10-2026; bronnen hieronder):
- **Geen salderen.** Wat je teruglevert brengt alleen iets op met een verkoopcontract: EDP betaalt
  de OMIE-prijs van het uur maal 75% ("OMIE x (1 - 25%)"), andere kopers een vaste prijs van een
  paar cent. Zonder contract gaat het gratis het net op.
- **Tijdvakken van de ERSE**, in de wettelijke tijd van het vasteland. Bi-horário: vazio en fora do
  vazio (alles daarbuiten). Tri-horário: vazio, cheias en ponta. Ciclo diário is elke dag hetzelfde
  (vazio van 22:00 tot 08:00); ciclo semanal heeft werkdagen (vazio 00:00 tot 07:00), zaterdag (cheias
  in twee blokken, de rest vazio) en zondag (vazio). Cheias en ponta schuiven met winter- en
  zomertijd. Super vazio (02:00 tot 06:00) valt voor een huishouden onder vazio.
- **Belastingen:** IVA 23%, behalve op de eerste 200 kWh per 30 dagen (300 bij vijf of meer
  personen) bij hooguit 6,9 kVA: 6% (Lei 38/2024, sinds 1-1-2025). IEC 0,001 per kWh, met IVA. Vaste
  bedragen per maand (CAV 2,85 plus 6%, DGEG 0,07 plus 23%) en de potência rekent de coach niet.
- De nettarieven zitten al in de energieprijs van de leverancier.

**Hoe de coach het doet.** Contract heeft bovenaan **Land**: Nederland of Portugal (`country`). Bij
Portugal verdwijnen de soort, de leverancierslijst, de all-in prijs, salderen en de afrekenperiode,
en komen de velden van `contract.pt`: de leverancier (vrij), de opção horária, de ciclo, per
tijdvak de prijs na korting zonder belastingen, de IVA (standaard 23) en de IEC, wat er met
teruglevering gebeurt (niet verkocht, vaste prijs, of OMIE maal een percentage met een
prijssensor), en voor het overzicht de kVA, de potência per dag en de diensten per maand.

`tarifas.py` deelt een moment in (`periodo`) in de tijd van Lissabon, zelf uitgerekend (UTC, met
een uur erbij in de EU-zomertijd), zodat het ook klopt als Home Assistant op een andere tijdzone
staat en op een machine zonder tzdata. De prijs per kWh is (energie + IEC) maal (1 + IVA)
(`preco`). `_pt_rijen` in coach.py maakt er per kwartier een prijslijst van, twee dagen vooruit,
want bij tri-horário en ciclo semanal begint een tijdvak soms op een kwart of een half uur; zonder
prijs voor een tijdvak is er geen lijst, en geen verzonnen bedrag. Daarmee plant de coach zoals bij
een dynamisch contract: de daluren zijn goedkoper, dus daar laadt hij (de avondpiek is dan geen
harde grens, `piek_dicht`). `_salderen` is in Portugal altijd uit. Historie rekent met de tweeling
`tarifas.js` (`ptPrijsOp` in `prijsOp`, het gemiddelde van de vier kwartieren van een uur), Contract
toont per tijdvak de opbouw (`ptBlok` in opbouw.js), en "Ja, dit klopt" telt het land en het
Portugese contract alleen mee in Portugal (`vingerafdruk`).

Bij de klant in Portugal: 20,7 kVA (dus alles tegen 23%), ciclo diário. Vazio kost dan
(0,1340 + 0,001) x 1,23 = 0,1661 per kWh, fora do vazio 0,2716.

**Wat nog niet.** De nieuwe tijden van de ERSE (Diretiva 3/2026) gaan per meter in tussen 1-7 en
31-12-2027 (bi diário: vazio 22:30 tot 08:30); de coach kent nog alleen de huidige. Zaterdag in
ciclo semanal komt uit de ERSE van 2025 (een folder van 2018 tekent hem anders): kijk het na tegen
een echte meter. De 6% IVA op de eerste 200 kWh rekent de coach niet; wie daaronder blijft zet de
IVA lager. Feestdagen gelden als een gewone dag.

Bronnen: ERSE, "ERSExplica: perguntas e respostas, períodos horários" (14-11-2025), en de diretiva
3/2026; Lei 38/2024 en DL 60/2019 (Portal das Finanças); EDP, FAQ over belastingen op de factuur en
over de verkoop van overschot; DECO Proteste over de factuur (13-07-2026); ERSE, FAQ autoconsumo.

Proeven: Portugal in test_prijsopbouw.py (22 gevallen van tijdvakken), proef 179 in test_coach.py,
"Portugal: dezelfde tijdvakken als de coach" in test_rapport.mjs (dezelfde 22 gevallen met
tarifas.js), en het scenario `pt-bihorario` in het virtuele huis: de bus gaat om 18:30 aan de paal
en laadt in de daluren, alles tegen 0,1661.

## Portugal op het overzicht, de keuzelijst en gas uit (v0.138.0)

De eigenaar op 19-10-2026, bij de klant in Portugal, vijf dingen in een middag:

- **"ik wil een dropdown menu van het land hebben nu staat er 2 velden groot in beeld."** Het
  land is een keuzelijst (`#land`), met de zin van het gekozen land eronder (`#land-hint`).
  Portugal kiezen zet nog steeds type fixed en salderen uit, zoals de knop deed. De keuzelijsten
  op Contract hebben sindsdien een pijltje: de gedeelde stijl van de bewerkschermen haalt dat van
  de browser weg (`appearance: none` in editor-base.js), en zonder pijltje leek het land op een
  gewoon veld.
- **"ook onder contract staat gas etc maar dat heeft deze klant niet je moet het kunnen
  uitzetten."** Gas en water hebben op Contract hetzelfde vinkje als bij Installatie
  (`sources.meters.gas_enabled` en `water_enabled`). Uit: alleen het vinkje en "Geen gas." of
  "Geen watermeter.", en de velden weg. Contract slaat daarvoor naast `contract` alleen die twee
  vlaggen op (`slice_` in contract.js), zodat opslaan de sensoren van Installatie niet terugzet;
  de server voegt ze samen. De velden van gas en water blijven bewaard, dus de vingerafdruk van
  "Ja, dit klopt" verandert er niet door.
- **"hij zegt gemiddeld tarief maar de grafiek is rood."** De tegel Energieprijs las bij elk
  contract dat niet dynamisch is `fixed.all_in_price`, en bij een Portugees contract stond daar
  nog de Nederlandse standaard van 0,28: "€ 0,280, Gemiddeld tarief" naast een rode balk van
  0,272. Nu geeft `priceNow` het tijdvak van nu (`ptPrijsOp`, dezelfde som als `tariff`), en
  `priceForecast` de lijst van de coach (`_pt_rijen`), dezelfde als de vooruitblik. De kleur komt
  dan uit dezelfde `prijsGrenzen` als de balken. Na het binnenkomen van die lijst tekent het
  overzicht de tegels opnieuw (`followCoach_`), anders bleef de eerste kleur staan tot de
  volgende meting.
- **"ik wil op de prijs kunnen klikken. In nederland is een vast contract gewoon 1 prijs maar
  hier heb je 2 prijzen."** De tegel opent de prijsgrafiek zodra de lijst meer dan een prijs
  heeft (niet meer dan een rij: simples heeft ook een lijst, met een rechte lijn). In Portugal
  heet de pop-up "Tarief per tijdvak", en staat eronder wanneer de daluren zijn (`ptTijden` in
  opbouw.js, dezelfde zin als op Contract).
- **"portugal heeft geen meterstanden dit is iets in Nederland."** Zie `docs/berichten.md`: geen
  kaart Je meter en geen herinnering om standen door te geven.

Wat niet veranderd is: de coach rekent overal in de lokale tijd van Home Assistant, en het paneel
leest die tijden als de tijd van de browser. Staat de browser op een andere tijdzone dan Home
Assistant (de installateur in Nederland die naar een woning in Portugal kijkt), dan schuiven de
vooruitblik en de prijsgrafiek een uur ten opzichte van "nu". De prijs op de tegel niet, want die
rekent `ptPrijsOp` in de tijd van Lissabon.

Proef 180 in test_coach.py en "Portugal op het overzicht en op Contract" in test_rapport.mjs.
