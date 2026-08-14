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

> Zolang er geen sensoren gekoppeld zijn draait het Overzicht op een
> gesimuleerde woning, zodat het dashboard meteen iets laat zien. Dat staat er
> dan bij op de coachkaart.

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

| Kopje | Wat je er instelt |
|-------|-------------------|
| **Navigatie** | Waar de **Home**-knop naartoe gaat. Standaard `/lovelace/0`. |
| **Energiebronnen** | De sensoren voor opwek, verbruik, meterstand en prijs. |
| **Drempelwaarden** | Waar de kleuren omslaan voor zelfbenutting en energieprijs. |

Apparaten hebben hun eigen sectie **Apparaten** in de header, niet een kopje
onder Instellingen: ze krijgen er gaandeweg meer instellingen bij dan in één
kopje passen.

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
- Vereist Home Assistant 2025.6 of nieuwer.

```
custom_components/domotiapp_coach/
├── __init__.py            paneel- en assetregistratie
├── config_flow.py         setup (vraagt niets)
├── const.py
├── storage.py             opslag van de instellingen
├── websocket.py           lezen en schrijven vanuit het paneel
├── brand/                 icon.png, logo.png
└── frontend/
    ├── domotiapp-coach-panel.js   entry point, routing
    ├── img/               logo in de header
    └── src/
        ├── base.js        mini-basisklasse voor de components
        ├── theme.js       design tokens
        ├── format.js      eenheden en getalweergave
        ├── data-source.js live bron plus simulatie
        ├── devices.js     apparaattypes
        ├── header.js      header met navigatie en Home-knop
        ├── icons.js
        ├── components/    stat-tile, energy-flow, entity-picker
        └── views/         overzicht, apparaten, instellingen, placeholders
```

---

## Licentie

MIT — zie [LICENSE](LICENSE).
