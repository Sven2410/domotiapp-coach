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

## Nog niet

Een melding als de controle omslaat, en de herinnering dat een contract afloopt, komen in
v0.130.0 met de berichtenbox.
