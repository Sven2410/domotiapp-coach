# DomotiApp Coach

Een eigen energiedashboard voor Home Assistant, met een ingebouwde coach.

Het standaard energiedashboard van Home Assistant laat zien *wat er gebeurd is*.
DomotiApp Coach laat zien wat er **nu** gebeurt, en gaat je vertellen wat je
er het beste mee kunt doen.

De integratie zet een eigen paneel in de zijbalk — geen Lovelace-dashboard dat
per woning opnieuw ingericht moet worden, maar één dashboard dat overal
hetzelfde werkt zodra de integratie geïnstalleerd is.

---

## Status

**Fase 1 — Uitlezen.** De header, het Overzicht en de instellingen staan er, en
het dashboard draait op je eigen sensoren zodra je ze gekoppeld hebt.

| Fase | Wat het doet | Status |
|------|--------------|--------|
| 1 | Uitlezen — sensoren tonen, live beeld van de woning | werkend |
| 2 | Adviseren — rekenen met tarieven, opwek en verbruik | in aanbouw |
| 3 | Sturen — apparaten schakelen op zonneoverschot en prijs | gepland |

> Zonder gekoppelde sensoren toont het Overzicht streepjes en vertelt de coach
> wat er nog ontbreekt. Er worden nooit getallen verzonnen: een dashboard dat
> het gat opvult met iets plausibels is erger dan een dashboard dat toegeeft dat
> het het niet weet.

---

## Installeren

### Via HACS (aanbevolen)

1. HACS → menu rechtsboven → **Custom repositories**
2. Repository: `https://github.com/Sven2410/domotiapp-coach`, type: **Integration**
3. Zoek **DomotiApp Coach** in HACS en download hem
4. Home Assistant herstarten
5. **Instellingen → Apparaten & diensten → Integratie toevoegen → DomotiApp Coach**

Het toevoegen vraagt niets: alles stel je daarna in het paneel zelf in.
Na het toevoegen verschijnt **DomotiApp Coach** in de zijbalk.

### Handmatig

Kopieer `custom_components/domotiapp_coach` naar de `custom_components` map van
je Home Assistant configuratie en herstart.

---

## Instellingen

Alles staat in het paneel onder **Instellingen**, niet in het configuratiescherm
van Home Assistant. Klanten draaien dit op hun telefoon achter Kiosk Mode, waar
de instellingen van HA niet bereikbaar zijn.

De secties in de header verdelen het zo:

| Sectie | Wat je er instelt | Wie |
|--------|-------------------|-----|
| **Apparaten** | Welke apparaten als bol in de energiestroom verschijnen, met hun sensoren en of ze gestuurd mogen worden. Opgeslagen apparaten staan ingeklapt op één regel; tik er een aan om hem te bewerken. | beheerder |
| **Strategie** | Meldingen: waar de coach uit zichzelf voor waarschuwt, en wie dat bericht krijgt. Elke melding is één regel; tik hem aan om hem in te stellen. | beheerder |
| **Installatie** | Naam van de woning, aantal fasen, hoofdzekering, maximaal netvermogen, en het energiecontract. | klant leest mee, beheerder wijzigt |
| **Instellingen** | Waar de Home-knop naartoe gaat, welke sensoren de meetwaarden leveren, de fasen, en de drempelwaarden voor de kleuren. | alleen beheerder |

**Installatie** is met opzet leesbaar voor de klant en alleen te wijzigen door
een beheerder: de gegevens daar bepalen wat de coach adviseert, dus een klant
die ziet dat zijn zekering of tarief niet klopt en dat meldt is meer waard dan
een klant die het scherm niet mag zien. **Instellingen** wijst rechtstreeks naar
entiteiten en is daarom helemaal verborgen voor klanten.

### Aansluiting

Het maximale netvermogen volgt uit fasen × hoofdzekering × 230 V — 3 × 25 A geeft
17,250 kW, 1 × 25 A geeft 5,750 kW — maar is aan te passen voor een begrensde of
verzwaarde aansluiting.

### Belastbaarheid

Het overzicht laat zien hoe hard je aansluiting wordt gewerkt. Zijn er
sensoren per fase ingevuld, dan rekent de coach met de **zwaarst belaste fase**
tegen de hoofdzekering — een zekering gaat eruit op de fase die overbelast is,
en een gemiddelde verbergt precies dat geval. Zonder fasesensoren wordt het
totale netvermogen tegen het maximum gelegd.

Onder **Strategie** kun je daar een melding aan hangen: vanaf welk percentage,
hoe lang dat moet aanhouden, naar welke `notify`-diensten (dat zijn de telefoons
waarop de HA-app is ingelogd) en hoe vaak dat hoogstens mag. Die melding wordt
door de integratie zelf verstuurd, dus ook als niemand het dashboard open heeft.

De aanhoudtijd is er tegen valse meldingen: een oven die aanslaat of een motor
die start geeft een piek van een seconde waar geen zekering van uit gaat en waar
je niets aan kunt doen. Standaard staat hij op een minuut — een zekering die net
boven zijn waarde belast wordt, houdt dat het grootste deel van een uur vol, dus
je bent nog ruim op tijd.

### Apparaten

Een apparaat kan een vermogenssensor hebben; dat is wat het op de energiestroom
zet. Verplicht is die niet — lang niet elke vaatwasser meet zijn eigen verbruik,
en zonder sensor valt er nog steeds prima mee te plannen. Daarnaast geef je per
apparaat aan of de coach het straks mag **aansturen** — veel apparaten hangen
alleen aan een meetstekker en zijn wel te volgen maar niet te bedienen.

Bij een **laadpaal** kies je eerst het merk, want welke gegevens een paal levert
verschilt per fabrikant en lang niet elke paal kan gestart of gepauzeerd worden.
Easee is uitgewerkt: de Easee-integratie zelf (daar komt het `device_id` uit dat
`easee.action_command` nodig heeft), status, reden geen stroomvraag,
levensduurverbruik, maximale limiet en stroom, plus de woorden voor starten,
stoppen, pauzeren, hervatten en herstarten. Die woorden staan voorgevuld op wat
Easee vandaag gebruikt en zijn aan te passen. Zaptec, Wallbox, Zappi en Peblar staan in de
lijst maar hebben nog geen eigen velden. Draait een apparaat, dan is zijn bol op
het overzicht aan te klikken voor precies die gegevens.

Bij een **vaatwasser** gaat het net zo. **Home Connect** is uitgewerkt — dat is
wat Bosch, Siemens, Neff, Gaggenau en Constructa allemaal gebruiken — met de
status, het geselecteerde programma, de resterende tijd en de deurstand, plus de
knoppen waarmee gestart en gestopt wordt. Miele en LG staan in de lijst maar
hebben nog geen velden.

Integraties spellen dezelfde waarde niet hetzelfde. Home Assistant's eigen Home
Connect-integratie meldt `ready`; de alternatieve meldt
`BSH.Common.EnumType.OperationState.Ready`. Het paneel herkent beide vormen —
per merk hoeven alleen de woorden zelf te worden opgegeven, niet elke spelling
ervan.

De deurstand is er **alleen om te laten zien**. Of de vaatwasser mag draaien,
zegt de klant zelf met de vrijgaveknop: een deur die dichtvalt betekent niet dat
de machine ingeruimd is.

Van de Home Connect-programma's kent het paneel de duur, het verbruik, het
piekvermogen en of ze te verschuiven zijn — Eco 50 °C duurt ruim 3,5 uur en kost
0,80 kWh, Voorspoelen is 15 minuten en heeft geen zin om te plannen. Dat zijn
opgaven van de fabrikant, geen metingen; ze staan erbij zodat de coach straks kan
uitrekenen wanneer een programma moet beginnen om op tijd klaar te zijn.

Een apparaat verwijderen vraagt om een bevestiging. De opslagbalk kan het ook
nog terugdraaien, maar de prullenbak zit naast de regel die je aantikt om een
apparaat te openen — en daar hangt een scherm vol entiteiten achter.

### Aanstuurbare apparaten

Alles wat op "mag aangestuurd worden" staat, komt op het overzicht in een eigen
kaart met dezelfde gegevens. Boven de kaarten staan de namen op een rij: je kiest
er één en die kaart staat er, in plaats van alle kaarten onder elkaar — op een
telefoon scrol je anders langs het hele rijtje voordat je bij de energiestroom
bent.

Elke kaart heeft een knop **vrijgeven**. Daarmee zegt de klant dat het apparaat
nú mee mag doen — de vaatwasser is ingeruimd en de klep zit dicht, de auto hangt
eraan. Zonder die knop zou de coach straks een lege vaatwasser laten spoelen
omdat de zon toevallig schijnt, en dat is de enige informatie die geen sensor kan
leveren. Vrijgeven mag iedereen die in Home Assistant is ingelogd, ook een
niet-beheerder: degene die in de keuken staat is nooit de installateur.

Kan een apparaat opdrachten aan, dan staat er ook **Handmatige besturing**. Die
opent een venster met de opdrachten van dat merk — bij Easee starten, stoppen,
pauzeren, hervatten en herstarten; bij een vaatwasser starten en stoppen, met
een keuzelijst voor het programma — en verstuurt de opdracht meteen. Herstarten
staat apart: dat breekt een lopende laadsessie af en de paal is daarna even niet
bereikbaar.

> De coach stuurt nog niet uit zichzelf. Handmatige besturing is een mens op de
> knop; wanneer de coach zelf mag ingrijpen is de volgende stap.

### Wanneer een apparaat mag draaien

Onder **Strategie** staat per aanstuurbaar apparaat binnen welke grenzen de
coach mag werken. Drie tijden, elk apart en elk optioneel:

- **Niet eerder dan** — hiervóór begint hij er niet aan, hoe goedkoop de stroom
  ook is.
- **Uiterlijk starten om** — op deze tijd start hij hoe dan ook.
- **Uiterlijk klaar om** — hier rekent hij de starttijd van terug.

Alleen invullen wat je belangrijk vindt. Wie alleen wil dat de vaatwasser vóór
het ontbijt klaar is, vult één tijd in en laat de rest leeg. Minstens één van de
drie is wel nodig: zonder enige grens is later altijd goedkoper en begint de
coach nooit.

Dat kan **elke dag hetzelfde** of **per dag**, want een zaterdag is geen
dinsdag. Per dag zijn het dezelfde drie tijden, en dagen die je uitvinkt slaat
hij over.

Het scherm rekent meteen terug: staat Eco 50 °C klaar en moet de vaatwasser om
07:00 klaar zijn, dan staat eronder dat starten uiterlijk om 03:15 moet. Zo zie
je op de plek waar je de tijd invult of hij haalbaar is.

Vrijgeven blijft daarnaast nodig. Een tijd instellen is niet hetzelfde als
toestemming geven.

### Wat niet opgeslagen kan worden

Instellingen die iets beloven wat niet kan gebeuren, blokkeren het opslaan; de
reden staat in de balk onderin. Dat zijn er twee: een apparaat dat op
"aansturen" staat zonder de entiteiten die daarvoor nodig zijn, en de melding
Zware belasting zonder ontvanger. Allebei sloegen ze eerder gewoon op en deden
daarna niets.

Wat alleen nog niet af is, blokkeert niets. Een installatie moet over twee
avonden ingevuld kunnen worden.

### Contract

Een **vast** contract is een all-in prijs, een terugleververgoeding en
terugleverkosten. Bij een **dynamisch** contract kies je tussen één sensor die de
all-in prijs al levert, of de kale marktprijs waarbij de coach zelf
energiebelasting en leveranciersopslag optelt en er btw overheen rekent.

Bij dynamisch geef je er ook bij of de prijs **per uur of per kwartier**
verandert. Dat is niet uit de sensor af te leiden — een uurprijs ziet er precies
hetzelfde uit als een kwartierprijs die een uur lang gelijk blijft — en het is de
blokgrootte waarin de coach straks plant.

Wijzigen mag alleen een beheerder; meekijken mag iedereen. Een wijziging op de
ene telefoon komt vanzelf door op een tablet die openstaat.

### Slimme meter

Twee patronen worden ondersteund, in te stellen onder Energiebronnen:

- **Afzonderlijk** — twee sensoren, energieverbruik en energieproductie, waarvan
  er altijd één op nul staat.
- **Gecombineerd** — één sensor die negatief wordt zodra je teruglevert.

### Eenheden

Of een sensor in W, kW of MW meet maakt niet uit: de integratie leest de eenheid
van de entiteit en rekent alles om. In beeld wordt per waarde gekozen — onder
een kilowatt in watt, daarboven in kW.

---

## Kiosk Mode

Klanten draaien hun dashboard vaak met de HACS-integratie
[Kiosk Mode](https://github.com/NemesisRE/kiosk-mode), die de header en de
zijbalk verbergt. Daardoor kunnen ze niet meer zelf tussen dashboards
navigeren.

Daar is in het ontwerp rekening mee gehouden:

- De header van DomotiApp Coach hoort **bij het paneel zelf** en blijft dus
  zichtbaar in Kiosk Mode.
- De **Home**-knop rechtsboven brengt de klant terug naar het eigen dashboard.

Voeg op het eigen dashboard van de klant een knop toe die de andere kant op
gaat:

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
Home Assistant — er worden geen fonts meegeleverd en er gaat geen verkeer naar
een externe CDN.

De kleuren van de energiestromen zijn niet met de hand gekozen maar doorgerekend
tegen de donkere achtergrond, op lichtheid, verzadiging, contrast en
onderscheidbaarheid bij kleurenblindheid — en getoetst in beide netstanden,
omdat inkoop en teruglevering nooit tegelijk in beeld zijn.

| Rol | Kleur |
|-----|-------|
| Zon | `#dc7300` oranje |
| Verbruik woning | `#235efa` blauw |
| Van het net | `#129be4` lichter blauw |
| Naar het net | `#bc10c8` paars |
| Apparaatbol 1 | `#fd0774` roze |
| Apparaatbol 2 | `#039580` teal |

Rood en groen zijn bewust géén stroomkleur: die zijn gereserveerd voor status
(duur/kritiek en goed). Elke stroom heeft daarnaast een eigen icoon en
tekstlabel, zodat kleur nooit de enige drager van betekenis is.

**Vervang deze kleuren niet zonder opnieuw te toetsen** — de marges zijn krap en
twee van de zes paren zitten dicht op hun ondergrens.

---

## Techniek

- Geen buildstap: het paneel bestaat uit gewone ES-modules en web components.
- De integratie registreert het paneel met `panel_custom.async_register_panel`
  en serveert de frontend vanaf een eigen statisch pad.
- Instellingen staan in HA-storage en gaan over een eigen websocket-API.
- Live waarden komen **niet** uit de `hass`-property die het paneel krijgt
  aangereikt, maar uit een eigen abonnement op `state_changed` (`state-feed.js`).
  Zie de toelichting in dat bestand.
- Vereist Home Assistant 2025.6 of nieuwer.

```
custom_components/domotiapp_coach/
├── __init__.py            paneel- en assetregistratie
├── config_flow.py         setup (vraagt niets)
├── const.py
├── storage.py             opslag van de instellingen
├── websocket.py           lezen en schrijven vanuit het paneel
├── monitor.py             bewaakt de belasting en stuurt de melding
├── brand/                 icon.png, logo.png
└── frontend/
    ├── domotiapp-coach-panel.js   entry point, routing, rechten
    ├── img/               logo in de header
    └── src/
        ├── base.js        mini-basisklasse voor de components
        ├── theme.js       design tokens
        ├── format.js      eenheden en getalweergave
        ├── state-feed.js  eigen abonnement op statuswijzigingen
        ├── data-source.js meetwaarden en prijsberekening
        ├── devices.js     apparaattypes
        ├── header.js      header met navigatie en Home-knop
        ├── icons.js
        ├── components/    stat-tile, energy-flow, entity-picker
        └── views/         overzicht, apparaten, strategie, installatie,
                           instellingen (editor-base deelt hun opslaglogica)
```

---

## Licentie

MIT — zie [LICENSE](LICENSE).
