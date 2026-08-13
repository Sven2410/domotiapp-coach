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

**Fase 1 — Uitlezen.** Op dit moment staat de opzet er: de header met navigatie
en het Overzicht met de live meetwaarden.

| Fase | Wat het doet | Status |
|------|--------------|--------|
| 1 | Uitlezen — sensoren tonen, live beeld van de woning | in aanbouw |
| 2 | Adviseren — rekenen met tarieven, opwek en verbruik | gepland |
| 3 | Sturen — apparaten schakelen op zonneoverschot en prijs | gepland |

> De waarden in het Overzicht zijn nu **gesimuleerd** (demomodus), zodat het
> ontwerp beoordeeld kan worden voordat er sensoren gekoppeld zijn. Dat is
> zichtbaar aan het label *Demodata* in het dashboard.

---

## Installeren

### Via HACS (aanbevolen)

1. HACS → menu rechtsboven → **Custom repositories**
2. Repository: `https://github.com/Sven2410/domotiapp-coach`, type: **Integration**
3. Zoek **DomotiApp Coach** in HACS en download hem
4. Home Assistant herstarten
5. **Instellingen → Apparaten & diensten → Integratie toevoegen → DomotiApp Coach**

Na het toevoegen verschijnt **DomotiApp Coach** in de zijbalk.

### Handmatig

Kopieer `custom_components/domotiapp_coach` naar de `custom_components` map van
je Home Assistant configuratie en herstart.

---

## Instellingen

Via **Configureren** op de integratie:

| Optie | Betekenis |
|-------|-----------|
| Pad van het hoofddashboard | Waar de **Home**-knop in de header naartoe gaat. Standaard `/lovelace/0`. |
| Demomodus | Gesimuleerde waarden tonen in plaats van echte sensordata. |

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

Het dashboard volgt de huisstijl van [domotitech.nl](https://domotitech.nl):
een warme, bijna zwarte achtergrond, Cormorant Garamond voor de koppen,
Raleway voor de interface en `#026FA1` als accentkleur.

De vier energiestromen (opwek, verbruik, net, overschot) hebben een vaste
kleurset die getoetst is op kleurcontrast en kleurenblindheid tegen de donkere
achtergrond. Elke stroom heeft daarnaast een eigen icoon en tekstlabel, zodat
kleur nooit de enige drager van betekenis is. Vervang die kleuren niet zonder
opnieuw te toetsen.

Fonts worden meegeleverd (SIL Open Font License), dus het paneel werkt ook
zonder internetverbinding en er gaat geen verkeer naar een externe CDN.

---

## Techniek

- Geen buildstap: het paneel bestaat uit gewone ES-modules en web components.
- De integratie registreert het paneel met `panel_custom.async_register_panel`
  en serveert de frontend vanaf een eigen statisch pad.
- Vereist Home Assistant 2025.6 of nieuwer.

```
custom_components/domotiapp_coach/
├── __init__.py            paneel- en assetregistratie
├── config_flow.py         setup en opties
├── const.py
└── frontend/
    ├── domotiapp-coach-panel.js   entry point, routing
    ├── fonts/
    └── src/
        ├── base.js        mini-basisklasse voor de components
        ├── theme.js       design tokens
        ├── header.js      header met navigatie en Home-knop
        ├── icons.js
        ├── demo-data.js   simulatie voor fase 1
        ├── components/    stat-tile, energy-flow
        └── views/         overzicht, placeholders
```

---

## Licentie

MIT — zie [LICENSE](LICENSE).
