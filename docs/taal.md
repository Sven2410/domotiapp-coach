# Taal: Nederlands en Engels (v0.139.0)

De eigenaar op 19-10-2026: "ik wil ook dat het hele coach in het engels ingesteld kan worden
dus nu is het alleen nederlands maar dan wil ik ook engels." Zijn keuzes die dag:

- **Eén taal per installatie.** Installatie, Taal / Language (`installation.language`):
  automatisch (de taal van Home Assistant, `hass.config.language`), Nederlands of English. Het
  paneel, en vanaf stap 2 ook de meldingen, redenen en kaarten, in dezelfde taal.
- **In stappen**, elk een eigen uitgave, met Nederlands als standaard:
  1. het paneel (v0.139.0);
  2. wat de coach zelf schrijft: meldingen, redenen bij een besluit, het verslag, de berichten;
  3. het rapport (report.js, pdf.js en de teksten daarvoor in views/history.js) en de
     leverancierslijst (leveranciers.js, leveranciers-data.js).

## Hoe het werkt

`i18n.js`. Het Nederlands blijft in de bron staan en is de sleutel:

```js
import { t, tn, nt, getal, datum, locale } from "../i18n.js";

`<h2>${icons.vlam} ${t("Mijn huidige gascontract")}</h2>`
el.textContent = t("{kwh} van het net", { kwh: energie });
tn(aantal, "{n} beurt", "{n} beurten")
```

In het Engels zoekt `t` de zin op in `i18n/en.js`, dat de delen in `i18n/en/` samenvoegt; wat er
niet in staat blijft Nederlands. Daardoor blijft elke proef die Nederlandse tekst narekent gelden.
`node tools/vertaalcheck.mjs` (en de proef "Engels: de taal kiezen, en elke zin heeft een
vertaling" in test_rapport.mjs) zoekt elke `t(`, `tn(` en `nt(` op en zegt welke zin nog geen
Engels heeft, welke in twee delen anders vertaald is, en waar de waarden tussen accolades niet
kloppen.

Het paneel kiest de taal bij het opstarten (de taal van de vorige keer, `dac-taal` in de opslag
van de browser) en na elke wijziging van de instelling; verandert hij, dan bouwt het zijn kop,
schermen en berichtenbox opnieuw op (`herbouw_` in domotiapp-coach-panel.js), want elk scherm
tekent zijn tekst een keer. Het label staat bewust in twee talen, "Taal / Language", zodat wie in
de verkeerde taal zit hem toch vindt.

## Regels bij het vertalen

1. **Alleen wat iemand leest**: tekst in de templates, `textContent`, labels, hints, `placeholder`,
   `title` en `aria-label`, meldingen op het scherm (toast), de namen in een keuzelijst.
2. **De sleutel is precies de Nederlandse tekst**, als string tussen dubbele aanhalingstekens, nooit
   een template literal. Een waarde gaat tussen accolades: `${n} kWh van het net` wordt
   `t("{kwh} kWh van het net", { kwh: n })`. Een getal met alleen een eenheid ("4,2 kW") hoeft niet.
3. **Geen HTML in de sleutel** als het niet hoeft: `${t("Leeg laten als je geen gas hebt.")}` binnen
   de tag. Staat er opmaak midden in een zin (`<strong>`), dan mag die in de sleutel en dezelfde
   opmaak in het Engels.
4. **Meervoud** met `tn`. **Getallen** met `getal(x, decimalen)` of `toLocaleString(locale(), ...)`,
   niet met `String(x).replace(".", ",")`. **Datums** met `datum(d, opties)` of
   `toLocaleDateString(locale(), ...)`, niet met "nl-NL" erin. **Namen van dagen en maanden** uit
   `datum(d, { weekday: "long" })` en `{ month: "long" }`, niet uit een eigen lijst.
5. **Nooit `t()` bij het laden van een module**: dan is de taal nog niet bekend. Een tabel met namen
   houdt het Nederlands, gemerkt met `nt("Laadpaal")`, en vertaalt waar hij getoond wordt:
   `t(soort.label)`.
6. **Niet vertalen**: tekst waarmee vergeleken, gezocht of gerekend wordt (een `===` op een label,
   een reguliere expressie op een melding van de coach zoals in tijdlijn.js), sleutels en id's,
   wat in de instellingen bewaard wordt, CSS, en tekst die van de coach komt (de redenen en
   meldingen: stap 2). Ook niet de namen die de bewoner zelf koos.
7. **Het Nederlands blijft letterlijk hetzelfde.** In het Nederlands moet het paneel precies
   tonen wat het toonde; de proeven zien dat.

## Schrijfwijze van het Engels

Brits Engels (`en-GB`: 24 uur, dag voor maand), kort en duidelijk, zoals het Nederlands: per
regel een ding, geen bijzinnen die niets toevoegen. **Geen gedachtestreepjes** (de proef zoekt ze).
Knoppen in de gebiedende wijs ("Save", "Add device"), koppen met een hoofdletter alleen vooraan
("Grid connection"). De Portugese namen van de tijdvakken blijven tussen haakjes staan, zoals op de
factuur: "Off-peak (vazio)".

## Woordenlijst

| Nederlands | Engels |
|---|---|
| Overzicht, Historie, Meldingen, Voorkeuren, Apparaten, Installatie, Contract | Overview, History, Notifications, Preferences, Devices, Installation, Contract |
| de coach | the coach |
| laadpaal | charger |
| thuisbatterij, accu | home battery, battery |
| accustand (van een auto) | charge level |
| zonnepanelen, zon, opwek | solar panels, solar, generation |
| het net, van het net, naar het net | the grid, from the grid, to the grid |
| afname, inkoop | import |
| teruglevering, terugleveren | export, export to the grid |
| terugleververgoeding | export tariff |
| terugleverkosten | export costs |
| salderen | net metering |
| zelfbenutting | self-consumption |
| verbruik woning | home consumption |
| belastbaarheid, belasting van je aansluiting | load, load on your connection |
| aansluiting, hoofdzekering, fase | grid connection, main fuse, phase |
| vast, variabel, dynamisch contract | fixed, variable, dynamic contract |
| all-in prijs, kale marktprijs | all-in price, bare market price |
| energiebelasting, opslag, btw | energy tax, supplier markup, VAT |
| leverancier | supplier |
| daluren, dal, buiten de daluren | off-peak hours, off-peak, peak hours |
| avondpiek | evening peak |
| klaar-tijd, klaar om | ready time, ready by |
| niet eerder dan, uiterlijk starten | not before, start at the latest |
| goedkoopste moment | cheapest moment |
| snelladen | fast charge |
| vrijgeven, vrijgegeven, ingeruimd | release, released, loaded |
| vaatwasser, wasmachine, droger | dishwasher, washing machine, dryer |
| boiler, warmtepompboiler | water heater, heat pump water heater |
| airco | air conditioner |
| vriezer, koelkast | freezer, fridge |
| smart plug, altijd aan | smart plug, always on |
| berichtenbox, belletje | inbox, bell |
| meterstand, meterstanden doorgeven | meter reading, submit meter readings |
| laadbeurt, beurt, sessie | charging session, session |
| bespaard, uitgegeven | saved, spent |
| vooruitblik | outlook |
| bewoner, installateur | resident, installer |
| Opslaan, Annuleren, Toevoegen, Verwijderen | Save, Cancel, Add, Remove |
