# DomotiApp Coach

Een energiedashboard voor Home Assistant dat niet alleen laat zien wat er
gebeurt, maar je apparaten ook op het gunstigste moment laat draaien.

Het standaard energiedashboard laat zien *wat er gebeurd is*. DomotiApp Coach
laat zien wat er **nu** gebeurt, rekent uit wanneer stroom het goedkoopst is, en
schakelt zelf: de laadpaal, de thuisbatterij, de vaatwasser en de boiler.

De integratie zet een eigen paneel in de zijbalk. Geen Lovelace-dashboard dat
per woning opnieuw ingericht moet worden, maar één dashboard dat overal
hetzelfde werkt zodra de integratie geïnstalleerd is.

---

## Wat de coach doet

**Hij vergelijkt alle manieren om een kilowattuur in een apparaat te krijgen.**
Elk uur tussen nu en het moment waarop iets klaar moet zijn levert twee
mogelijkheden: uit je eigen zon, tegen wat je er anders voor teruggekregen had,
of van het net, tegen de prijs van dat uur. Alle mogelijkheden op een hoop,
sorteren op prijs, van onderaf vullen tot er genoeg in zit. Dat is aantoonbaar
de goedkoopste verdeling, en geen ladder van vuistregels.

Daarboven staan de dingen die niet over geld gaan: de zekering van de woning, de
groep van de laadpaal, een eigen pauze, de avondpiek en het moment waarop iets
klaar moet zijn.

**Hij verzint nooit een getal.** Elk getal op het scherm komt uit een meting, uit
een instelling of uit een som die daarop rust. Weet hij iets niet, dan zegt hij
dat, in plaats van het gat te vullen met iets plausibels.

| Apparaat | Wat de coach doet |
|---|---|
| **Laadpaal** | Kiest het goedkoopste moment, moduleert tussen 6 A en het maximum van de paal, en is op tijd klaar. Wisselt nooit van fasemodus. |
| **Thuisbatterij** | Houdt de meter op nul, laadt van het net op de goedkoopste uren als dat het rendement goedmaakt, en geeft niets af terwijl de laadpaal laadt. Rekent met het gemeten rendement van jouw batterij. |
| **Vaatwasser** | Kiest het goedkoopste startmoment en drukt op de startknop. Bij een machine zonder startknop geeft hij het moment door en meet hij mee. |
| **Boiler** | Schakelt de stroom, en leert zelf hoeveel het element trekt en hoe snel het vat leegloopt. De thermostaat van de boiler bepaalt de temperatuur. |
| **Overig** | Alles met een vermogenssensor wordt gemeten en meegeteld, ook zonder sturing. |

---

## Installeren

### Via HACS (aanbevolen)

1. HACS, menu rechtsboven, **Custom repositories**
2. Repository: `https://github.com/Sven2410/domotiapp-coach`, type: **Integration**
3. Zoek **DomotiApp Coach** in HACS en download hem
4. Home Assistant herstarten
5. **Instellingen, Apparaten & diensten, Integratie toevoegen, DomotiApp Coach**

Het toevoegen vraagt niets: alles stel je daarna in het paneel zelf in. Na het
toevoegen verschijnt **DomotiApp Coach** in de zijbalk.

### Handmatig

Kopieer `custom_components/domotiapp_coach` naar de `custom_components` map van
je Home Assistant configuratie en herstart.

Vereist Home Assistant 2025.6 of nieuwer.

---

## De schermen

Alles staat in het paneel zelf en niet in het configuratiescherm van Home
Assistant. Een bewoner draait dit vaak op een tablet of telefoon achter Kiosk
Mode, waar de instellingen van HA niet bereikbaar zijn.

| Scherm | Wat er staat | Wie |
|---|---|---|
| **Overzicht** | De energiestroom van dit moment, en per aanstuurbaar apparaat een kaart met wat de coach van plan is. | iedereen |
| **Apparaten** | Welke apparaten er zijn, met hun sensoren en wat de coach ermee mag. | beheerder |
| **Strategie** | Hoeveel de coach zelf mag beslissen. | beheerder |
| **Meldingen** | Wie welke melding krijgt, plus alles wat de coach ooit stuurde en besloot. | bewoner ziet zichzelf |
| **Historie** | Wat er verbruikt is, en onder **Bespaard** wat het slimme moment opleverde. | iedereen |
| **Installatie** | Naam van de woning, aantal fasen, hoofdzekering, maximaal netvermogen en het energiecontract. | bewoner leest mee |
| **Instellingen** | Welke sensoren de meetwaarden leveren, de fasen, en de drempels voor de kleuren. | alleen beheerder |

**Installatie** is met opzet leesbaar voor de bewoner en alleen te wijzigen door
een beheerder: die gegevens bepalen wat de coach adviseert, dus iemand die ziet
dat de zekering of het tarief niet klopt en dat meldt is meer waard dan iemand
die het scherm niet mag zien. **Instellingen** wijst rechtstreeks naar
entiteiten en is daarom helemaal verborgen voor niet-beheerders.

---

## Apparaten

Elk apparaat kan een vermogenssensor hebben; dat is wat het op de energiestroom
zet, en waarmee de coach meet wat een beurt gekost heeft. Verplicht is die niet.
Daarnaast geef je per apparaat aan wat de coach ermee mag: **aansturen**,
**adviseren** of alleen **noemen**. Wat hij niet kan, belooft het scherm ook
niet.

### Laadpaal

Kies het merk, want welke gegevens een paal levert verschilt per fabrikant.
**Easee** is uitgewerkt: status, reden geen stroomvraag, levensduurverbruik,
maximale limiet, gemeten stroom, de dynamische laadgrens van de lader en die van
het stroomcircuit. **Alfen** gaat via de integratie alfen_modbus: de coach
schrijft de maximale stroomlimiet van de socket, elke minuut opnieuw omdat de
paal hem na zijn geldigheidsduur vergeet, en leest "auto aangesloten", "auto
laadt" en de modus 3-status. Zet in de paal de geldigheidsduur van de
Modbus-stroomlimiet op minstens drie minuten. Een paal van een ander merk zet
je onder **Overig**: die wordt gemeten en meegeteld, maar niet gestuurd.

Per auto leg je vast wat de accu kan hebben, op hoeveel fasen hij laadt en **tot
hoever hij laadt**. Dat laatste is niet de laadgrens in de auto zelf maar het
doel van de coach: staan ze gelijk, dan weet hij waar de beurt eindigt in plaats
van het achteraf te merken. Staat het doel lager, dan stopt de coach eerder.

Drie dingen doet hij bewust niet: van fasemodus wisselen (dat beschadigt het
relais van sommige auto's), blind laden zonder accustand of zonder prijzen, en
doorladen als de groep van de paal dat niet aankan.

### Vaatwasser

**Home Connect** is uitgewerkt, de integratie achter Bosch, Siemens, Neff,
Gaggenau en Constructa: de status, het geselecteerde programma, de resterende
tijd, de deurstand, en de knoppen waarmee gestart en gestopt wordt. Een machine
van een ander merk zet je onder **Overig** met een meetstekker: dan plant de
coach hem wel en drukt hij niet, maar krijg je op het juiste moment een bericht
dat je hem aan kunt zetten.

De tabel met programma's (duur, verbruik, piekvermogen) is het uitgangspunt en
is bewerkbaar. Wat de coach bij een echte beurt meet komt daaroverheen, als
lopend gemiddelde over de laatste beurten. Zo klopt de planning na een paar keer
met jouw machine en jouw programma's, en niet met een folder.

De deurstand is er alleen om te laten zien. Of de machine mag draaien zeg je met
de knop **Ingeruimd en dicht**: een deur die dichtvalt betekent niet dat hij
ingeruimd is. Die knop is ook aan een schakelaar te koppelen, voor wie hem liever
op een eigen keukendashboard heeft.

De coach kiest nooit zelf een programma. Dat doe jij.

### Thuisbatterij

De coach stuurt de batterij helemaal zelf, lokaal via Home Assistant. Hij heeft
daarvoor drie dingen nodig: een **getal waarmee het vermogen gezet wordt**, de
**accustand**, en wat de batterij nu doet (een vermogenssensor met een teken, of
twee losse sensoren voor laden en ontladen). Ondersteund is **Anker SOLIX** via
de officiele integratie; onder **Overig** past elke batterij met dezelfde
knoppen.

Twee lagen. Elke minuut kijkt de coach vooruit over alle uren waarvan de prijs
bekend is, met wat het huis gaat verbruiken en wat de zon gaat geven, en kiest
hij een stand:

| Stand | Wat er gebeurt |
|---|---|
| **Nul op de meter** | Overschot gaat erin, wat het huis vraagt komt eruit. |
| **Alleen zonneladen** | Zonoverschot gaat erin, er komt niets uit: de laadpaal laadt, of de stroom in de batterij is straks meer waard. |
| **Laden van het net** | Op de goedkoopste uren, en niet voluit maar rustig verdeeld over de uren die even duur zijn. |
| **Maximaal laden** | De prijs die je betaalt is negatief: vol vermogen, en er komt niets uit. |
| **Handelen** | Terugleveren op dure uren. Staat standaard uit. |
| **Standby** | Opslaan zou geld kosten, of de meter zwijgt. |

Daaronder draait een regelaar op het tempo van je meter, die de stand uitvoert.
Hij rekent in een keer uit wat het huis vraagt, corrigeert pas opnieuw als de
vorige opdracht in het vermogen te zien is, en doet niets binnen een dode band
rond nul. Zo stuurt hij een paar keer per uur bij in plaats van een paar keer
per minuut.

**Het rendement is een meting.** Met een kWh-meter op de batterij meet de coach
zelf wat erin gaat en wat eruit komt; zonder vul je het in. Zonder rendement
houdt hij alleen de meter op nul en laadt hij niet van het net, want dan valt er
niets te vergelijken. De tellers van een batterij zelf zijn hier meestal niet
goed voor: die meten aan de accukant en tellen de omzetverliezen niet mee.

Per batterij stel je in: een **reserve voor noodstroom** waaronder niets meer
ontladen wordt, of er **gehandeld** mag worden, een **wekelijkse volle beurt** voor
het balanceren van de cellen, en de **aankoopprijs**. Met dat laatste laat de
kaart zien hoeveel de batterij al heeft terugverdiend, en na vier weken meten
ook wanneer de rest er ongeveer is. De laadgrens en de ontlaadgrens van de
batterij leest de coach alleen; hij verandert ze nooit.

Stopt de integratie, valt de meter weg of gaat het vinkje "mag sturen" eraf, dan
gaat het vermogen naar nul en krijgt de batterij zijn eigen modus terug. Een
batterij die op zijn laatste opdracht blijft staan loopt leeg naar het net.

### Boiler

Twee velden en verder niets: de **schakelaar** (een smart plug, een switch of een
relais) en de **vermogenssensor**. Geen merk, geen temperatuursensor, geen tabel.

De coach zet de stroom erop of eraf; hoe warm het water wordt blijft aan de
thermostaat van de boiler zelf. Staat er stroom op en vraagt de boiler niets
meer, dan is het vat vol. Zo leert hij in een paar beurten hoeveel het element
trekt, hoeveel er in een vol vat gaat, en hoe snel dat vat weer leegloopt.
Zonoverschot dat het element kan dragen pakt hij meteen: een vat is de
goedkoopste plek om overschot in te stoppen.

Gaat de integratie uit of staat het schema uit, dan zet hij de stroom erop. Een
auto die blijft staan is een ongemak, een koud vat merk je onder de douche.

---

## Wanneer een apparaat klaar moet zijn

Op de kaart van elk apparaat zit een knop **Schema**. Daarachter staan de tijden
en het werk per dag.

Voor een **laadpaal** is er één tijd: **klaar om**. Wanneer hij begint zoekt de
coach zelf uit, en daar is hij voor. Andere apparaten houden alle drie de
tijden:

- **Niet eerder dan** — hiervoor begint hij er niet aan, hoe goedkoop de stroom
  ook is.
- **Uiterlijk starten om** — op deze tijd start hij hoe dan ook.
- **Uiterlijk klaar om** — hier rekent hij de starttijd van terug.

Vul alleen in wat je belangrijk vindt. Dat kan **elke dag hetzelfde** of **per
dag**, want een zaterdag is geen dinsdag; dagen die je uitvinkt slaat hij over.
Met de schuif ernaast zet je het hele schema uit.

Bij een programma-apparaat blijft vrijgeven daarnaast nodig. Een tijd instellen
is niet hetzelfde als toestemming geven.

---

## Aansluiting en belastbaarheid

Het maximale netvermogen volgt uit fasen maal hoofdzekering maal 230 V. Drie keer
25 A geeft 17,250 kW, één keer 25 A geeft 5,750 kW, en het is aan te passen voor
een begrensde of verzwaarde aansluiting.

Zijn er sensoren per fase ingevuld, dan rekent de coach met de **zwaarst belaste
fase** tegen de hoofdzekering. Een zekering gaat eruit op de fase die overbelast
is, en een gemiddelde verbergt precies dat geval. Zonder fasesensoren wordt het
totale netvermogen tegen het maximum gelegd.

Daar hangt onder **Meldingen** een waarschuwing aan: vanaf welk percentage, hoe
lang dat moet aanhouden, naar wie, en hoe vaak dat hoogstens mag. Die melding
verstuurt de integratie zelf, dus ook als niemand het dashboard open heeft.

De aanhoudtijd is er tegen valse meldingen: een oven die aanslaat of een motor
die start geeft een piek van een seconde waar geen zekering van uit gaat.
Standaard een minuut, want een zekering die net boven zijn waarde belast wordt
houdt dat het grootste deel van een uur vol. Je bent dan nog ruim op tijd.

---

## Contract

Een **vast** contract is een all-in prijs, een terugleververgoeding en
terugleverkosten. Bij een **dynamisch** contract kies je tussen één sensor die de
all-in prijs al levert, of de kale marktprijs, waarbij de coach zelf
energiebelasting en leveranciersopslag optelt en er btw overheen rekent. Geef er
bij dynamisch ook bij of de prijs **per uur of per kwartier** verandert: dat is
niet uit de sensor af te leiden, en het is de blokgrootte waarin de coach plant.

Bij een vast contract kost elk uur hetzelfde. Dan valt er met haasten niets te
winnen en laadt de coach in het rustigste tempo dat de klaar-tijd nog haalt; dat
belast de aansluiting het minst. Eigen zon is ook dan goedkoper dan het net, dus
die wint vanzelf.

---

## Slimme meter en eenheden

Twee patronen worden ondersteund, in te stellen onder Energiebronnen:

- **Afzonderlijk** — twee sensoren, verbruik en teruglevering, waarvan er altijd
  één op nul staat.
- **Gecombineerd** — één sensor die negatief wordt zodra je teruglevert.

Of een sensor in W, kW of MW meet maakt niet uit: de integratie leest de eenheid
van de entiteit en rekent alles om. In beeld wordt per waarde gekozen: onder een
kilowatt in watt, daarboven in kW.

---

## Meldingen

Per persoon staat er welke soort hij krijgt: kritiek, gewone meldingen,
besluiten, en de belastingwaarschuwing. Een bewoner ziet zichzelf en zet zijn
eigen schuiven; de beheerder voegt mensen toe.

De regel is: **per beurt één verslag, plus wat je zelf moet oplossen.** Besluiten
staan standaard uit en komen alleen in de geschiedenis. Dat een boiler om drie
uur 's nachts weer warm is hoeft niemand te wekken.

Op hetzelfde scherm staat alles wat de coach ooit stuurde, en elk besluit dat hij
nam, met het moment erbij. Daarmee is achteraf na te gaan waarom hij deed wat hij
deed.

---

## Bespaard

Onder Historie staat wat het slimme moment opleverde, per periode en per
apparaat. De maat is eerlijk: wat dezelfde beurt gekost zou hebben als hij meteen
bij het inpluggen of vrijgeven op vol vermogen van het net was gegaan, min wat er
werkelijk betaald is. Dat verschil valt uiteen in twee delen: wat de zon
bespaarde, en wat het wachten bespaarde.

Start de integratie midden in een beurt opnieuw op, dan rekent hij het begin
terug uit de recorder en de eigen kwartieropslag, zodat er geen beurt wegvalt.

---

## Kiosk Mode

Wie het dashboard draait met de HACS-integratie
[Kiosk Mode](https://github.com/NemesisRE/kiosk-mode) verbergt de header en de
zijbalk van Home Assistant. Daar is in het ontwerp rekening mee gehouden:

- De header van DomotiApp Coach hoort **bij het paneel zelf** en blijft dus
  zichtbaar.
- De **Home**-knop rechtsboven brengt je terug naar het eigen dashboard.

Voeg op dat eigen dashboard een knop toe die de andere kant op gaat:

```yaml
type: button
name: DomotiApp Coach
icon: mdi:home-lightning-bolt
tap_action:
  action: navigate
  navigation_path: /domotiapp-coach
```

---

## Ontwerp

Donkere achtergrond met `#026FA1` als accentkleur, en het eigen lettertype van
Home Assistant. Er worden geen fonts meegeleverd en er gaat geen verkeer naar een
externe CDN.

De kleuren van de energiestromen zijn niet met de hand gekozen maar doorgerekend
tegen de donkere achtergrond, op lichtheid, verzadiging, contrast en
onderscheidbaarheid bij kleurenblindheid, en getoetst in beide netstanden, omdat
inkoop en teruglevering nooit tegelijk in beeld zijn.

| Rol | Kleur |
|-----|-------|
| Zon | `#dc7300` oranje |
| Verbruik woning | `#235efa` blauw |
| Van het net | `#129be4` lichter blauw |
| Naar het net | `#bc10c8` paars |
| Apparaatbol 1 | `#fd0774` roze |
| Apparaatbol 2 | `#039580` teal |

Rood en groen zijn bewust geen stroomkleur: die zijn gereserveerd voor status
(duur of kritiek, en goed). Elke stroom heeft daarnaast een eigen icoon en
tekstlabel, zodat kleur nooit de enige drager van betekenis is.

**Vervang deze kleuren niet zonder opnieuw te toetsen.** De marges zijn krap en
twee van de zes paren zitten dicht op hun ondergrens.

---

## Techniek

- Geen buildstap: het paneel bestaat uit gewone ES-modules en web components.
- Het denkwerk (`planner.py`) kent Home Assistant niet en is los te draaien tegen
  een hele dag echte historie voordat er iets geschakeld wordt. De bedrading
  (`coach.py`) leest de sensoren en stuurt de apparaten.
- Instellingen staan in HA-storage en gaan over een eigen websocket-API.
- Live waarden komen **niet** uit de `hass`-property die het paneel krijgt
  aangereikt, maar uit een eigen abonnement op `state_changed`
  (`state-feed.js`).

```
custom_components/domotiapp_coach/
├── __init__.py            paneel- en assetregistratie
├── config_flow.py         setup (vraagt niets)
├── planner.py             al het denkwerk, zonder Home Assistant
├── coach.py               sensoren lezen, apparaten sturen, beurten bijhouden
├── storage.py             opslag van instellingen, beurten en meldingen
├── websocket.py           lezen en schrijven vanuit het paneel
├── monitor.py             bewaakt de belasting en stuurt de melding
├── ontvangers.py          wie welke melding krijgt
├── report.py              het pdf-rapport
├── brand/                 icon.png, logo.png
└── frontend/
    ├── domotiapp-coach-panel.js   entry point, routing, rechten
    └── src/
        ├── base.js        mini-basisklasse voor de components
        ├── theme.js       design tokens
        ├── format.js      eenheden en getalweergave
        ├── state-feed.js  eigen abonnement op statuswijzigingen
        ├── data-source.js meetwaarden en prijsberekening
        ├── devices.js     apparaattypes en hun velden
        ├── savings.js     Bespaard
        ├── schedule-sheet.js    het schema van één apparaat
        ├── plan-ahead-sheet.js  wat de coach van plan is, per uur
        ├── components/    stat-tile, energy-flow, entity-picker
        └── views/         overzicht, apparaten, strategie, meldingen,
                           historie, installatie, instellingen
```

De proeven draaien zonder Home Assistant: een nagebouwde HA, en een virtueel huis
met een zon die opkomt, een huis dat kookt, een auto die voller wordt en een
meter die dat ziet. Een hele nacht laden duurt daarin een seconde.

```
python tests/test_planner.py     het denkwerk
python tests/test_coach.py       de bedrading
python tests/test_virtueel.py    hele beurten in het virtuele huis
python tests/test_archive.py     de kwartieropslag
node   tests/test_rapport.mjs    het rapport en het paneel
```

---

## Licentie

MIT — zie [LICENSE](LICENSE).
