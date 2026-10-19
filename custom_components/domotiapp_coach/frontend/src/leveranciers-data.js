/**
 * De leveranciers van de catalogus behalve Zonneplan, die in leveranciers.js staat
 * (v0.129.0). Uitgezocht op 18-10-2026; zie leveranciers.js voor wat erin hoort en
 * waarom het een voorstel is en geen rekenregel.
 *
 * De tekst die Contract toont (`uitleg`, `terug`, `onzeker` en de woorden in `namen`) staat
 * gemerkt met `nt`, en `voorstel` in leveranciers.js vertaalt hem (v0.140.0, docs/taal.md).
 */

import { nt } from "./i18n.js";

export const LEVERANCIERS_DATA = [
  {
    id: "anwb-energie",
    naam: "ANWB Energie",
    website: "https://www.anwb.nl/energie",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: { netting_full: true, feed_in_costs: 0, feed_in_bonus: 0 },
        namen: { opslag: nt("Inkoopkosten") },
        uitleg: nt("ANWB: de prijs per kWh bestaat uit de kale energieprijs van het uur, de energiebelasting en € 0,018 inkoopkosten. Vaste leveringskosten € 8,50 per maand."),
        terug: nt("Je krijgt de kale energieprijs van het uur, zonder terugleverkosten. Tot 2027 krijg je over het deel tot je jaarverbruik de all-in prijs terug (salderen). Bij een negatieve prijs betaal je voor teruglevering."),
        bronnen: [
          "https://www.anwb.nl/energie/actuele-tarieven",
          "https://www.anwb.nl/energie/dynamisch-energiecontract-zonnepanelen",
          "https://www.anwb.nl/energie/negatieve-stroomprijzen",
          "https://www.anwb.nl/energie/vaste-leveringskosten-energie",
        ],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gasprijs per dag: kale prijs, energiebelasting en inkoopkosten, sinds 1 september 2026 € 0,0768 per m³ (ANWB zet '(incl. btw)' achter die zin)."),
        bronnen: ["https://www.anwb.nl/energie/actuele-tarieven"],
      },
    },
    ha: {
      stroom: ["anwb_electricity_all_in_price_current"],
      gas: [],
    },
    onzeker: [
      nt("Inkoopkosten niet ingevuld: ANWB schrijft € 0,018 met '(incl. btw)' dubbelzinnig achter de zin over gas, Gaslicht.com rekent € 0,0218 met btw. De prijs-API van ANWB past het best bij € 0,018 met btw, maar rondt af op hele centen."),
      nt("Vaste leveringskosten € 8,50: ANWB zegt niet of dat met of zonder btw is."),
      nt("Of ANWB het overschot boven je jaarverbruik met of zonder btw vergoedt, staat er niet."),
      nt("De site en de prijs-API zeggen per uur; één vergelijker noemt kwartier."),
      nt("De HACS-integratie van vinnie1234 geeft de prijs standaard in cent per kWh (euro is een optie)."),
    ],
  },
  {
    id: "budget-thuis",
    naam: "Budget Thuis",
    website: "https://www.budgetthuis.nl/energie",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: { supplier_markup: 0.013884, feed_in_costs: 0, feed_in_bonus: 0 },
        namen: { opslag: nt("Inkoopvergoeding") },
        uitleg: nt("Budget Thuis: (beursprijs + inkoopvergoeding + energiebelasting) + btw, per uur. De inkoopvergoeding publiceert Budget niet; volgens Gaslicht.com € 0,0168 met btw, en vaste leveringskosten € 6,49 per maand met btw."),
        terug: nt("Je krijgt de beursprijs van het uur, zonder terugleverkosten. Tot 2027 saldeert Budget tegen de leveringsprijs van dat uur; over een jaaroverschot alleen de beursprijs. Vanaf 2027 een ZonneBonus van 30% over de beursprijs (hooguit € 0,06 per kWh) binnen een tijdvak per maand, over de eerste 5.000 kWh; die staat niet in de velden omdat hij pas dan ingaat."),
        bronnen: [
          "https://www.budgetthuis.nl/energie/dynamisch-energiecontract",
          "https://www.budgetthuis.nl/docs/productvoorwaarden_dynamisch_contract.pdf",
          "https://www.budgetthuis.nl/docs/Actievoorwaarden_ZonneBonus.pdf",
          "https://www.gaslicht.com/stroom-vergelijken/budgetenergie/nederlandse-groene-stroom-dynamisch-5130",
        ],
      },
      vast: {
        velden: { feed_in_costs_mode: "schalen", feed_in_scales_until: "2027-01-01" },
        uitleg: nt("Terugleverkosten in 26 schalen: een vast bedrag per dag naar je teruglevering (nooit boven je jaarverbruik), van € 0 tot € 7,73 per dag met btw; de tabel staat op de pagina terugleverkosten. Vanaf 2027 een bedrag per kWh. De terugleververgoeding boven salderen staat in het tariefblad bij je contract en is niet openbaar."),
        bronnen: [
          "https://www.budgetthuis.nl/energie/terugleverkosten",
          "https://www.budgetthuis.nl/docs/productvoorwaarden.pdf",
        ],
      },
      variabel: {
        velden: { feed_in_costs_mode: "schalen", feed_in_scales_until: "2027-01-01" },
        uitleg: nt("Terugleverkosten in dezelfde 26 schalen als bij vast, per dag naar je teruglevering. Vanaf 2027 een bedrag per kWh. De terugleververgoeding boven salderen wordt maandelijks herzien en staat in het tariefblad bij je contract."),
        bronnen: [
          "https://www.budgetthuis.nl/energie/terugleverkosten",
          "https://www.budgetthuis.nl/docs/productvoorwaarden.pdf",
        ],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch: (beursprijs + inkoopvergoeding + energiebelasting) + btw."),
        bronnen: ["https://www.budgetthuis.nl/energie/dynamisch-energiecontract"],
      },
      vast: {
        velden: {},
        uitleg: nt("Gas vast, ook als Dynamisch + Gas Vast: dynamische stroom met een jaar vast gas."),
        bronnen: ["https://www.budgetthuis.nl/energie/stroom-en-gas"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel; de prijs per m³ staat in je contract."),
        bronnen: ["https://www.budgetthuis.nl/energie/stroom-en-gas"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("De inkoopvergoeding (€ 0,0168 met btw) en de vaste leveringskosten (€ 6,49 per maand) komen alleen van Gaslicht.com (14-10-2026); Budget publiceert ze niet."),
      nt("Negatieve prijzen: de productvoorwaarden zeggen dat de terugleververgoeding sinds 2026 niet negatief mag zijn, de pagina over salderen zegt dat je dan betaalt."),
      nt("Of de beursprijs bij teruglevering met of zonder btw wordt vergoed, staat er niet."),
      nt("Geen sensor: de HACS-integraties rekenen de all-in prijs zelf uit met een inkoopvergoeding die je instelt, of hebben geen vaste entiteitnaam."),
    ],
  },
  {
    id: "clean-energy",
    naam: "Clean Energy",
    website: "https://www.cleanenergy.nl",
    peildatum: "2026-10-18",
    stroom: {
      vast: {
        velden: { feed_in_tariff: 0.15 },
        uitleg: nt("Terugleverkosten volgens de productvoorwaarden € 0,14 per kWh met btw, over elke teruggeleverde kWh in 2026; vanaf 2027 de terugleververgoeding min € 0,01. Boven salderen € 0,15 per kWh met btw. Vaste leveringskosten € 0,24863 per dag met btw."),
        bronnen: [
          "https://www.cleanenergy.nl/downloads",
          "https://www.cleanenergy.nl/terugleveren",
          "https://www.cleanenergy.nl/files/2026-10/Tarievenblad%20referentieproducten%20%284%29.pdf",
        ],
      },
      variabel: {
        velden: { feed_in_tariff: 0.15 },
        uitleg: nt("Terugleverkosten volgens de productvoorwaarden € 0,14 per kWh met btw, over elke teruggeleverde kWh in 2026; vanaf 2027 de terugleververgoeding min € 0,01. Boven salderen € 0,15 per kWh met btw."),
        bronnen: [
          "https://www.cleanenergy.nl/files/2026-09/Productvoorwaarden%20Huishoudelijk%20variabel.pdf",
          "https://www.cleanenergy.nl/terugleveren",
        ],
      },
    },
    gas: {
      vast: {
        velden: {},
        uitleg: nt("Gas vast, 1 tot 5 jaar; de prijs per m³ staat in je contract."),
        bronnen: ["https://www.cleanenergy.nl/downloads"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel; de prijs per m³ staat in je contract."),
        bronnen: ["https://www.cleanenergy.nl/downloads"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Terugleverkosten niet ingevuld: de productvoorwaarden en de rekenvoorbeelden zeggen € 0,14 per kWh, één zin op de pagina terugleveren zegt € 0,15."),
      nt("Geen dynamisch contract gevonden."),
    ],
  },
  {
    id: "coolblue-energie",
    naam: "Coolblue Energie",
    website: "https://www.coolblue.nl/energie",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: {},
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Inkoopvergoeding, bij teruglevering") },
        uitleg: nt("Coolblue Energie levert op de vergunning van ServiceHouse. De kwartierprijs is de EPEX-beursprijs plus inkoopvergoeding, energiebelasting en btw. Het bedrag staat in je persoonlijke aanbod; volgens Keuze.nl € 0,02 per kWh, zonder dat duidelijk is of dat met of zonder btw is."),
        terug: nt("Je krijgt de actuele kwartierprijs min de inkoopvergoeding; aparte terugleverkosten rekent Coolblue niet. Tot 2027 saldeert Coolblue per telwerk op jaarbasis."),
        bronnen: [
          "https://www.coolblue.nl/energiecontracten/dynamischestroom",
          "https://www.coolblue.nl/energiecontracten/dynamische-energie",
          "https://www.keuze.nl/energie/energieleveranciers/coolblue",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Terugleverkosten per kWh over alle teruglevering; het bedrag staat in je contract, volgens Keuze.nl € 0,115 in 2026. Over de terugleververgoeding boven salderen wordt geen btw gerekend; volgens Keuze.nl € 0,06017 per kWh."),
        bronnen: [
          "https://www.gaslicht.com/stroom-vergelijken/coolblue-energie/nederlandse-groene-stroom-1-jaar-vast-5196",
          "https://www.gaslicht.com/userfiles/pdf/energie/coolblue-energie/pakketten/pakket-voorwaarden/PV260108-Contractvoorwaarden-Coolblue-Energie.pdf",
        ],
      },
    },
    gas: {
      vast: {
        velden: {},
        uitleg: nt("Gas alleen vast, ook naast Dynamische Stroom; de prijs per m³ staat in je contract."),
        bronnen: ["https://www.coolblue.nl/energiecontracten/dynamischestroom"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Inkoopvergoeding (€ 0,02) alleen van vergelijkers, zonder btw-vermelding; daarom niet ingevuld. De vaste leveringskosten van Dynamische Stroom zijn niet gevonden."),
      nt("Hoeveel er bij teruglevering afgaat hangt aan diezelfde inkoopvergoeding; wanneer de regel 'Teruggave inkoopvergoeding' uit het aanbod geldt, legt Coolblue niet uit."),
      nt("Wat er bij een negatieve kwartierprijs met teruglevering gebeurt: niet gevonden."),
      nt("De bedragen bij vast komen alleen van Keuze.nl."),
      nt("Geen sensor: de HACS-integratie rekent de all-in prijs uit met een inkoopvergoeding die je zelf instelt."),
    ],
  },
  {
    id: "delta-energie",
    naam: "DELTA Energie",
    website: "https://www.deltaenergie.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: { supplier_markup: 0.01037, feed_in_vat: false },
        namen: { opslag: nt("Inkoopvergoeding"), kosten: nt("Verkoopvergoeding") },
        uitleg: nt("DELTA: totale prijs = beursprijs (het uurgemiddelde van de kwartierprijzen) + inkoopvergoeding + energiebelasting, alles met 21% btw. Inkoopvergoeding € 0,012548 met btw (prijsblad 23 april 2026). Vaste leveringskosten € 8,49 per maand met btw."),
        terug: nt("Je krijgt de beursprijs van het uur; wat na saldering netto teruggaat is btw-vrij. Per teruggeleverde kWh rekent DELTA een verkoopvergoeding met btw, ook als die gesaldeerd wordt; het bedrag staat alleen in MijnDELTA en kan nul zijn. Van 2027 tot 2030 minstens 50% van beursprijs plus inkoopvergoeding."),
        bronnen: [
          "https://www.deltaenergie.nl/media/ohjb20ah/dynamisch-delta-groene-stroom-delta-gas-consumenten-23-april-2026.pdf",
          "https://files.deltaenergie.nl/media/productvoorwaarden/E1_19C_10_PV-DELTA-Groene-Stroom-en-DELTA-Gas-Dynamisch-februari-2026.pdf",
          "https://www.deltaenergie.nl/stroom-gas/dynamisch-energiecontract/",
        ],
      },
      vast: {
        velden: { feed_in_tariff: 0.165 },
        uitleg: nt("Terugleverkosten in 45 schalen, een bedrag per jaar naar je teruglevering (tabel 'vanaf 12 juni 2025'). Boven salderen € 0,165 per kWh, btw-vrij. Vanaf 2027 per kWh: bij 3 jaar vast € 0,06743 kosten met btw en € 0,06993 vergoeding, bij 1 jaar vast € 0,07703 en € 0,07953."),
        bronnen: [
          "https://www.deltaenergie.nl/media/czudzzj2/vaste-prijzen-delta-groene-stroom-en-delta-mixgroen-gas-consument-16-september-2026.pdf",
          "https://www.deltaenergie.nl/media/ggkoalbt/prijzenfolder_vaste-terugleveringskosten_tabel_versie-26-feb-2026.pdf",
          "https://www.deltaenergie.nl/service/info/terugleverkosten/",
        ],
      },
      variabel: {
        velden: { feed_in_tariff: 0.165 },
        uitleg: nt("Terugleverkosten in dezelfde 45 schalen als bij vast. Boven salderen € 0,165 per kWh, btw-vrij (prijsblad 1 april 2026). Het bedrag per kWh vanaf 2027 komt bij de variabele prijzen van dan."),
        bronnen: [
          "https://www.deltaenergie.nl/media/ggkoalbt/prijzenfolder_vaste-terugleveringskosten_tabel_versie-26-feb-2026.pdf",
          "https://www.deltaenergie.nl/service/info/terugleverkosten/",
        ],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("DELTA Gas Dynamisch, in dezelfde productvoorwaarden en op hetzelfde prijsblad als de dynamische stroom."),
        bronnen: [
          "https://www.deltaenergie.nl/media/ohjb20ah/dynamisch-delta-groene-stroom-delta-gas-consumenten-23-april-2026.pdf",
          "https://files.deltaenergie.nl/media/productvoorwaarden/E1_19C_10_PV-DELTA-Groene-Stroom-en-DELTA-Gas-Dynamisch-februari-2026.pdf",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("DELTA MixGroen Gas vast; de prijs per m³ staat op het prijsblad met de vaste prijzen."),
        bronnen: [
          "https://www.deltaenergie.nl/media/czudzzj2/vaste-prijzen-delta-groene-stroom-en-delta-mixgroen-gas-consument-16-september-2026.pdf",
        ],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Hoogte van de verkoopvergoeding bij dynamisch: alleen in MijnDELTA, en volgens de voorwaarden kan hij ook nul zijn."),
      nt("De site linkt op 18-10-2026 nog naar het dynamische prijsblad van 23 april 2026, en naar het variabele van 1 april 2026; een nieuwer blad is niet gevonden."),
      nt("Negatieve prijzen: de productpagina zegt dat je dan betaalt voor terugleveren, de voorwaarden zetten het netto overschot en het maandtotaal op minimaal € 0."),
    ],
  },
  {
    id: "dynamiq",
    naam: "Dynamiq",
    website: "https://dynamiq.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: {},
        uitleg: nt("Dynamiq Energy Services levert op de vergunning van Kikker Energie. Je betaalt de inkoopprijs per uur, plus vaste kosten en belastingen. De site zegt 'geen opslag', de FAQ noemt 'meestal een kleine marge per kWh'; er zijn geen bedragen gepubliceerd."),
        terug: nt("Alleen 'een eerlijke terugleververgoeding', zonder bedragen."),
        bronnen: [
          "https://dynamiq.nl/",
          "https://dynamiq.nl/combineer-met-zonnepanelen/",
          "https://dynamiq.nl/wp-content/uploads/2025/12/Bijlage_A_Productvoorwaarden.pdf",
        ],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch, inkoopprijs per dag."),
        bronnen: ["https://dynamiq.nl/"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Geen tarieven gepubliceerd; de site spreekt zichzelf tegen over een opslag."),
      nt("Of het merk werkelijk nieuwe klanten aanneemt."),
      nt("De ACM legde Kikker Energie in 2026 een bindende aanwijzing op."),
    ],
  },
  {
    id: "easyenergy",
    naam: "easyEnergy",
    website: "https://www.easyenergy.com",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: { supplier_markup: 0.018, feed_in_costs: 0 },
        namen: { opslag: nt("Inkoopvergoeding") },
        uitleg: nt("easyEnergy: leveringstarief = kwartiertarief EPEX + inkoopvergoeding + 21% btw, plus energiebelasting. Inkoopvergoeding € 0,02178 per kWh met btw (€ 0,018 zonder). Lidmaatschap € 7 per maand voor stroom."),
        terug: nt("Je krijgt de beursprijs van het kwartier, zonder aparte terugleverkosten. De inkoopvergoeding rekent easyEnergy alleen over het maandsaldo van verbruik min teruglevering. Tot 2027 volledig gesaldeerd, de energiebelasting op jaarbasis."),
        bronnen: [
          "https://www.easyenergy.com/dynamische-energie/prijzen",
          "https://www.easyenergy.com/media/nsfhjtjd/tarievenblad.pdf",
          "https://www.easyenergy.com/media/hdgd2moo/productvoorwaarden-dynamische-elektriciteit-kleine-aansluiting.pdf",
          "https://www.easyenergy.com/terugleveren-dynamische-energie",
        ],
      },
      vast: {
        velden: { feed_in_tariff: 0 },
        uitleg: nt("Alleen het wettelijke modelcontract: teruglevertarief € 0,00 per kWh, en over teruglevering boven je verbruik geen energiebelasting. Terugleverkosten noemt het tarievenblad niet."),
        bronnen: ["https://www.easyenergy.com/media/rqsnhjri/easyenergy-modelcontracttarieven-2026.pdf"],
      },
      variabel: {
        velden: { feed_in_tariff: 0 },
        uitleg: nt("Alleen het wettelijke modelcontract: teruglevertarief € 0,00 per kWh, en over teruglevering boven je verbruik geen energiebelasting. Terugleverkosten noemt het tarievenblad niet."),
        bronnen: [
          "https://www.easyenergy.com/media/rqsnhjri/easyenergy-modelcontracttarieven-2026.pdf",
          "https://www.easyenergy.com/media/4vyhds13/easyenergy-modelcontractvoorwaarden-variabel-2026.pdf",
        ],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas: dagtarief LEBA + inkoopvergoeding + 21% btw, plus energiebelasting. Lidmaatschap € 7 per maand voor gas."),
        bronnen: ["https://www.easyenergy.com/media/nsfhjtjd/tarievenblad.pdf"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Lidmaatschap € 7 per maand: of dat met of zonder btw is, staat er niet letterlijk."),
      nt("Of de inkoopvergoeding in een maand met netto teruglevering van de vergoeding afgaat: een blog zegt van wel, de pagina terugleveren van niet. Daarom geen vergoeding ingevuld."),
      nt("Of teruglevering de beursprijs met of zonder btw krijgt, zegt easyEnergy niet; de HA-bibliotheek gebruikt de prijs met btw."),
      nt("De core-integratie easyEnergy geeft de kale prijs met btw, zonder energiebelasting en inkoopvergoeding; de all-in prijs alleen via een actie, niet als sensor."),
    ],
  },
  {
    id: "eneco",
    naam: "Eneco",
    website: "https://www.eneco.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: { supplier_markup: 0.01898, feed_in_costs: 0, feed_in_vat: false },
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Verkoopvergoeding") },
        uitleg: nt("Eneco: (EPEX-uurprijs + inkoopvergoeding + energiebelasting) × 1,21. Inkoopvergoeding € 0,01898 zonder btw (€ 0,02297 met), uit de prijs-API achter de tarievenpagina van Eneco. De vaste leveringskosten staan niet op de site."),
        terug: nt("Tot 2027 krijg je tot je jaarverbruik per uur hetzelfde tarief terug als je betaalt, inclusief inkoopvergoeding. Over een jaaroverschot de marktprijs van het uur min een verkoopvergoeding, zonder btw; dat bedrag publiceert Eneco niet. Geen terugleverkosten. Bij een negatieve uurprijs is de vergoeding ook negatief."),
        bronnen: [
          "https://www.eneco.nl/duurzame-energie/dynamisch-energiecontract/dynamische-tarieven/",
          "https://www.eneco.nl/klantenservice/dynamisch-energiecontract/dynamisch-en-terugleveren/",
          "https://www.gaslicht.com/userfiles/pdf/energie/eneco/pakketten/pakket-voorwaarden/PV260518-Voorwaarden-Eneco-Dynamisch-HollandseWind-Zon.pdf",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Terugleverkosten sinds 1 juni 2024 een vast bedrag per kWh over alle teruglevering; het bedrag staat in je contract. De terugleververgoeding boven salderen staat ook in je contract, zonder btw."),
        bronnen: [
          "https://www.eneco.nl/klantenservice/terugleverkosten/",
          "https://www.eneco.nl/-/media/eneco-nl/files/voorwaarden/345voorwaardenoverzicht2026.pdf",
        ],
      },
      variabel: {
        velden: {},
        uitleg: nt("Terugleverkosten een vast bedrag per kWh over alle teruglevering; het bedrag staat in je contract. De terugleververgoeding boven salderen staat ook in je contract, zonder btw."),
        bronnen: [
          "https://www.eneco.nl/klantenservice/terugleverkosten/",
          "https://www.eneco.nl/-/media/eneco-nl/files/voorwaarden/345voorwaardenoverzicht2026.pdf",
        ],
      },
    },
    gas: {
      vast: {
        velden: {},
        uitleg: nt("Gas vast, ook naast Eneco Dynamisch: dynamische stroom met een jaar vast gas."),
        bronnen: [
          "https://www.gaslicht.com/energie-vergelijken/eneco/hollandse-wind-en-zon-dynamisch-en-gas-1-jaar-vast-5244",
        ],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel; de prijs per m³ staat in je contract."),
        bronnen: ["https://www.eneco.nl/duurzame-energie/energieprijzen/"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Verkoopvergoeding bij dynamisch: Eneco publiceert hem niet; vergelijkers noemen € 0,0292 (Keuze.nl) en € 0,0241 met btw."),
      nt("Vaste leveringskosten bij dynamisch alleen van vergelijkers, en die verschillen: € 8,99 met btw (Gaslicht.com) tegen € 7 (Keuze.nl)."),
      nt("De HACS-integratie Dynamic Energy Prices haalt onder 'eneco' de prijzen van EnergyZero op, niet die van Eneco."),
    ],
  },
  {
    id: "energie-vanons",
    naam: "Energie VanOns",
    website: "https://energie.vanons.org",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: { feed_in_costs: 0, feed_in_vat: false },
        namen: { opslag: nt("Opslag levering"), vergoeding: nt("Afslag teruglevering") },
        uitleg: nt("Energie VanOns: uurprijs EPEX Day Ahead (het gemiddelde van de vier kwartieren) + opslag levering, vermeerderd met energiebelasting en btw. De opslag staat niet op de site; vergelijkers noemen € 0,029 per kWh. Vaste leveringskosten € 6,99 per maand."),
        terug: nt("Je krijgt de uurprijs zonder btw, min een afslag teruglevering per kWh; dat bedrag is niet gepubliceerd. Geen vaste terugleverkosten. Levering en teruglevering worden per uur gesaldeerd, de energiebelasting op jaarbasis tot je jaarverbruik."),
        bronnen: [
          "https://energie.vanons.org/dynamisch-contract/",
          "https://energie.vanons.org/wp-content/uploads/2026/08/Aanvullende-voorwaarden-dynamisch-contract.pdf",
          "https://energie.vanons.org/salderingsregeling/",
          "https://www.overstappen.nl/energie/leveranciers/energie-vanons/",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Terugleverkosten per jaar in schalen: tot 999 kWh € 0, vanaf 1.000 kWh € 166,31 en per 500 kWh daarboven € 66,55 extra, met btw. Een vast contract uit 2026 betaalt per kWh (rekenvoorbeeld 3 jaar vast: € 0,07 met btw). De terugleververgoeding boven salderen staat per looptijd op de tarievenpagina."),
        bronnen: [
          "https://energie.vanons.org/tarieven/",
          "https://energie.vanons.org/vaste-kosten-teruglevering/",
          "https://energie.vanons.org/einde-salderingsregeling-2027/",
        ],
      },
      variabel: {
        velden: {},
        uitleg: nt("Terugleverkosten in dezelfde schalen als bij vast. Terugleververgoeding boven salderen bij variabel € 0,053981 per kWh met btw (tarievenblad); het coöperatieve contract heeft een eigen bedrag."),
        bronnen: [
          "https://energie.vanons.org/tarieven/",
          "https://energie.vanons.org/tarievenblad-variabel-contract/",
          "https://energie.vanons.org/vaste-kosten-teruglevering/",
        ],
      },
    },
    gas: {},
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Opslag levering (€ 0,029) alleen van vergelijkers, en niet eenduidig met of zonder btw; daarom niet ingevuld."),
      nt("Afslag teruglevering bij dynamisch: bedrag nergens gevonden."),
      nt("Of de vaste leveringskosten van € 6,99 met of zonder btw zijn, staat er niet."),
      nt("Terugleververgoeding bij vast en variabel verschilt per product; daarom niet ingevuld. De bedragen voor 1 en 3 jaar vast op de tarievenpagina lijken op die van om | nieuwe energie (de fusiepartner) en zijn daarom niet overgenomen."),
      nt("De schalen boven 1.999 kWh volgen uit de regel van € 66,55 per 500 kWh; een maximum is niet gevonden."),
    ],
  },
  {
    id: "energiebesteding",
    naam: "Energiebesteding",
    website: "https://www.energiebesteding.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        velden: {},
        namen: { opslag: nt("Opslag inkoopkosten") },
        uitleg: nt("Energiebesteding (gericht op senioren) werkt met Hezelaer Energy, waarmee je het contract sluit. Dynamisch: ieder uur de marktprijs plus een opslag inkoopkosten; het bedrag is niet gepubliceerd."),
        terug: nt("Geen regeling voor teruglevering gepubliceerd; Hezelaer rekent terugleveringskosten per kWh over je hele teruglevering, het bedrag staat in je contract. Energiebesteding raadt met zonnepanelen een vast contract aan."),
        bronnen: [
          "https://www.energiebesteding.nl/onze-contracten/",
          "https://www.energiebesteding.nl/welzp/",
          "https://www.hezelaer.nl/assets/pdf/aanvullend-voorwaardenoverzicht-kleinverbruik-aansluitingen-v30.pdf",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Vast 1 tot en met 5 jaar, en ZekerVoordeel (april tot en met september dynamisch, oktober tot en met maart vast). Bij vast krijg je voor teruglevering dezelfde prijs als voor levering, min terugleverkosten (bedrag niet gepubliceerd). Vaste leveringskosten € 8,99 per product per maand met btw."),
        bronnen: ["https://www.energiebesteding.nl/welzp/", "https://www.energiebesteding.nl/onze-contracten/"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Variabel; de bedragen staan in je contract."),
        bronnen: ["https://www.energiebesteding.nl/onze-contracten/"],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch, prijs per dag."),
        bronnen: ["https://www.energiebesteding.nl/onze-contracten/"],
      },
      vast: {
        velden: {},
        uitleg: nt("Gas vast, 1 tot en met 5 jaar; de prijs staat in je contract."),
        bronnen: ["https://www.energiebesteding.nl/onze-contracten/"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel; de prijs staat in je contract."),
        bronnen: ["https://www.energiebesteding.nl/onze-contracten/"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Opslag van het dynamische contract niet gepubliceerd."),
      nt("Of de vaste leveringskosten van € 8,99 ook bij dynamisch gelden."),
      nt("Hoogte van de terugleverkosten bij vast."),
      nt("Uur of kwartier: de pagina's spreken elkaar tegen."),
    ],
  },
  {
    id: "energiedirect",
    naam: "Energiedirect",
    website: "https://www.energiedirect.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: { netting_full: true, supplier_markup: 0.01694, feed_in_costs: 0, feed_in_bonus: -0.01694, feed_in_vat: false },
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Verkoopvergoeding") },
        uitleg: nt("Energiedirect, een merk van Essent op hetzelfde platform: (beursprijs + inkoopvergoeding + energiebelasting) × 1,21, per uur met het gemiddelde van de vier kwartierprijzen. Inkoopvergoeding € 0,01694 zonder btw (€ 0,0205 met), uit de prijs-API van Energiedirect."),
        terug: nt("Tot 2027 krijg je tot je jaarverbruik per uur hetzelfde tarief terug als je betaalt, inclusief btw, energiebelasting en inkoopvergoeding. Over een jaaroverschot de beursprijs zonder btw min € 0,01694 verkoopvergoeding; komt dat negatief uit, dan wordt het € 0. Geen terugleverkosten."),
        bronnen: [
          "https://www.energiedirect.nl/energie/energiecontract/dynamisch",
          "https://www.energiedirect.nl/-/media/energiedirect/documenten/productvoorwaarden/202601_energiedirect_productvoorwaarden_dynamisch.pdf",
          "https://www.energiedirect.nl/api/public/dynamicpricing/dynamic-prices/v1",
        ],
      },
      vast: {
        velden: { feed_in_costs_mode: "schalen", feed_in_scales_until: "2027-01-01" },
        uitleg: nt("Terugleverkosten in 42 schalen: een vast bedrag per dag naar je teruglevering, met btw ('geldig per 1 januari 2025'); de tabel staat op de pagina terugleverkosten. Boven salderen € 0,15 per kWh. Vanaf 2027 per kWh in plaats van schalen."),
        bronnen: ["https://www.energiedirect.nl/zonnepanelen/kosten/terugleverkosten"],
      },
      variabel: {
        velden: { feed_in_costs_mode: "schalen", feed_in_scales_until: "2027-01-01" },
        uitleg: nt("Terugleverkosten in dezelfde 42 schalen als bij vast, per dag. Boven salderen € 0,15 per kWh. Vanaf 2027 per kWh in plaats van schalen."),
        bronnen: ["https://www.energiedirect.nl/zonnepanelen/kosten/terugleverkosten"],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch; de prijs-API van Energiedirect geeft de gasprijs naast die van stroom."),
        bronnen: ["https://www.energiedirect.nl/energie/energiecontract/dynamisch"],
      },
      vast: {
        velden: {},
        uitleg: nt("Gas vast, 1, 2 of 3 jaar; de prijs per m³ staat in je contract."),
        bronnen: ["https://www.energiedirect.nl/energie/energiecontract/dynamisch"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel; de prijs per m³ staat in je contract."),
        bronnen: ["https://www.energiedirect.nl/energie/energiecontract/dynamisch"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Vaste leveringskosten bij dynamisch: niet gevonden."),
      nt("De schalen voor terugleverkosten staan er als 'geldig per 1 januari 2025'; of ze in 2026 gelijk zijn, staat er niet."),
      nt("Of de € 0,15 boven salderen met of zonder btw is, staat er niet; daarom niet ingevuld."),
    ],
  },
  {
    id: "energiek",
    naam: "Energiek",
    website: "https://www.energiek.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: { supplier_markup: 0.0149, feed_in_costs: 0, feed_in_bonus: -0.0149, feed_in_vat: false },
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Beursprijs-afslag") },
        uitleg: nt("Energiek: kwartierprijs EPEX Day Ahead + inkoopvergoeding, vermeerderd met energiebelasting en btw. Inkoopvergoeding € 0,0149 zonder btw (€ 0,018029 met). Vaste leveringskosten € 5,99 per maand met btw."),
        terug: nt("Je krijgt de beursprijs van het kwartier zonder btw, min de beursprijs-afslag van € 0,0149 per kWh. Geen vaste terugleverkosten. Saldering per kwartier, en op jaarbasis opnieuw voor de energiebelasting."),
        bronnen: [
          "https://www.energiek.nl/energie/dynamisch",
          "https://www.energiek.nl/api/products/dynamic_contract",
          "https://www.gaslicht.com/userfiles/pdf/energie/energiek/pakketten/pakket-voorwaarden/PV260219-Energiek-Voorwaarden-Dynamisch.pdf",
        ],
      },
      vast: {
        velden: { feed_in_costs: 0.0605 },
        uitleg: nt("Terugleverkosten € 0,0605 per kWh met btw over alle teruglevering, zonder schalen, bij 1 en 3 jaar vast. Terugleververgoeding boven salderen, zonder btw: 1 jaar vast € 0,075, 3 jaar vast € 0,07."),
        bronnen: [
          "https://www.energiek.nl/api/products",
          "https://www.energiek.nl/klantenservice/terugleverkost-vs-terugleververgoeding",
        ],
      },
      variabel: {
        velden: { feed_in_costs: 0.069, feed_in_tariff: 0.075 },
        uitleg: nt("Terugleverkosten € 0,069 per kWh met btw over alle teruglevering, zonder schalen. Terugleververgoeding boven salderen € 0,075 per kWh, zonder btw."),
        bronnen: [
          "https://www.energiek.nl/api/products",
          "https://www.energiek.nl/klantenservice/terugleverkost-vs-terugleververgoeding",
        ],
      },
    },
    gas: {
      vast: {
        velden: {},
        uitleg: nt("Gas vast, 1 of 3 jaar; de prijs per m³ staat in je contract."),
        bronnen: ["https://www.energiek.nl/api/products"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel, ook als Energiek Duo: dynamische stroom met variabel gas."),
        bronnen: ["https://www.energiek.nl/api/products"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("De beursprijs-afslag, de terugleverkosten en de terugleververgoeding komen uit velden van de product-API van Energiek; wat elk veld betekent is afgeleid uit die API en de tekst op de site, niet letterlijk zo gezegd."),
      nt("Of de beursprijs-afslag tot 2027 alleen over het netto overschot gaat of over alle teruglevering, staat er niet."),
      nt("Wat er bij een negatieve prijs met teruglevering gebeurt: niet beschreven."),
    ],
  },
  {
    id: "energyzero",
    naam: "EnergyZero",
    website: "https://www.energyzero.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: { feed_in_costs: 0 },
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Verkoopvergoeding") },
        uitleg: nt("EnergyZero: kwartierprijs EPEX + inkoopvergoeding, met energiebelasting en 21% btw over alles. De prijs-API van EnergyZero gaf op 18-10-2026 € 0,01853 inkoopvergoeding zonder btw (€ 0,02242 met); de kennisbank noemt € 0,028 zonder btw voor 2026. Vaste leveringskosten volgens Gaslicht.com € 7,49 per maand met btw."),
        terug: nt("Je krijgt de beursprijs min een verkoopvergoeding van € 0,02242 per kWh. Geen vaste terugleverkosten. Met de gratis module ZonOptimaal tot eind 2026 € 0,01 korting op die verkoopvergoeding, en compensatie als de all-in kwartierprijs negatief is."),
        bronnen: [
          "https://www.energyzero.nl/dynamisch-contract",
          "https://cdn.prod.website-files.com/69d612cef209b014c2f5b1be/69d8a8a9ec56af8d1051de78_productvoorwaarden_dynamische_prijs_stroom_bijlage_d1.pdf",
          "https://www.energyzero.nl/kenniscentrum/salderen",
          "https://storage.googleapis.com/energyzero-terms-and-conditions/5e94edf4-a182-4c7b-99c7-0bfb08c587c5/aanvullende_voorwaarden_zonoptimaal.pdf",
        ],
      },
      vast: {
        velden: { feed_in_costs: 0.02242 },
        uitleg: nt("Alleen het wettelijke modelcontract: een verkoopvergoeding van € 0,02242 met btw per teruggeleverde kWh, en over een jaaroverschot € 0,045 per kWh terug."),
        bronnen: ["https://www.energyzero.nl/modelcontract"],
      },
      variabel: {
        velden: { feed_in_costs: 0.02242 },
        uitleg: nt("Alleen het wettelijke modelcontract: een verkoopvergoeding van € 0,02242 met btw per teruggeleverde kWh, en over een jaaroverschot € 0,045 per kWh terug."),
        bronnen: ["https://www.energyzero.nl/modelcontract"],
      },
    },
    gas: {},
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Inkoopvergoeding niet ingevuld: de prijs-API (18-10-2026) en Gaslicht.com (prijswijziging 14-10-2026) zeggen € 0,01853 zonder btw, de kennisbank van EnergyZero € 0,028 zonder btw voor 2026, en Overstappen.nl rekent bij merken op dit platform met € 0,03388 met btw. Omdat de core-integratie de inkoopvergoeding niet bevat, kan de controle het niet nagaan."),
      nt("Verkoopvergoeding bij dynamisch niet ingevuld: € 0,02242 staat bij het modelcontract met btw en in de ZonOptimaal-voorwaarden zonder btw-vermelding, en of hij tot 2027 over alle teruglevering of alleen over het overschot gaat, zegt EnergyZero niet eenduidig."),
      nt("Vaste leveringskosten alleen van Gaslicht.com."),
      nt("Hoe saldering in 2026 precies rekent: de productvoorwaarden noemen de gemiddelde kwartierprijs van het jaar, het kenniscentrum de all-in prijs."),
      nt("Of de € 0,045 bij het modelcontract met of zonder btw is, staat er niet; daarom niet ingevuld."),
      nt("De core-integratie EnergyZero noemt een prijs all-in, maar daar zit de inkoopvergoeding niet in; hij ligt € 0,0224 per kWh onder je echte prijs."),
    ],
  },
  {
    id: "engie",
    naam: "ENGIE",
    website: "https://www.engie.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: { supplier_markup: 0.0157, feed_in_costs: 0, feed_in_bonus: -0.0157, feed_in_vat: false },
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Verkoopvergoeding") },
        uitleg: nt("ENGIE: beursprijs per uur (EPEX Day Ahead) + inkoopvergoeding + energiebelasting, met btw. Inkoopvergoeding € 0,0157 zonder btw (€ 0,018997 met), uit het aanbod voor nieuwe klanten. Vaste leveringskosten € 0,2285 per dag met btw, ongeveer € 6,95 per maand."),
        terug: nt("Tot je jaarverbruik krijg je de marktprijs en daarbovenop de verkoopvergoeding van 1,9 cent terug, dus het leveringstarief van dat uur (salderen tot 2027). Boven je verbruik de beursprijs zonder btw min € 0,0157 verkoopvergoeding. Geen terugleverkosten; de vergoeding kan negatief zijn."),
        bronnen: [
          "https://www.engie.nl/energie/dynamisch-energiecontract",
          "https://www.engie.nl/energie/dynamisch-energiecontract/zonnepanelen",
          "https://www.engie.nl/-/media/engie/over/_downloads/voorwaarden/engie-energie-b2c/productvoorwaarden-engie-dynamisch-20261-10.pdf",
          "https://energie.engie.nl/api/propositions",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Terugleverkosten per kWh over alle teruglevering, zonder schalen, met btw: 1 jaar vast € 0,1668, 2 jaar € 0,1464, 3 jaar € 0,1335. Terugleververgoeding boven salderen, zonder btw: € 0,1768, € 0,1564 en € 0,14345. Uit het aanbod voor nieuwe klanten op 18-10-2026."),
        bronnen: ["https://energie.engie.nl/consument", "https://energie.engie.nl/api/propositions"],
      },
      variabel: {
        velden: { feed_in_costs: 0.1901999, feed_in_tariff: 0.2001999 },
        uitleg: nt("ENGIE Open: terugleverkosten € 0,1902 per kWh met btw over alle teruglevering, zonder schalen; terugleververgoeding boven salderen € 0,2002 per kWh, zonder btw. Uit het aanbod voor nieuwe klanten op 18-10-2026."),
        bronnen: ["https://energie.engie.nl/consument", "https://energie.engie.nl/api/propositions"],
      },
    },
    gas: {
      vast: {
        velden: {},
        uitleg: nt("Gas vast; de prijs per m³ staat in je contract."),
        bronnen: ["https://energie.engie.nl/consument"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel (ENGIE Open); de prijs per m³ staat in je contract."),
        bronnen: ["https://energie.engie.nl/consument"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Alle bedragen komen uit het aanbod voor nieuwe klanten op 18-10-2026 (start rond half november); ze kunnen per klant en startdatum verschillen."),
      nt("ENGIE gaat naar kwartierprijzen 'vanaf dat en/of enig moment', zonder datum."),
      nt("De verkoopvergoeding bij dynamisch na 2027 is 'nog te bepalen'."),
      nt("De HACS-integratie van ENGIE geeft de kale day-ahead-prijs, zonder energiebelasting en inkoopvergoeding."),
    ],
  },
  {
    id: "essent",
    naam: "Essent",
    website: "https://www.essent.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: { netting_full: true, supplier_markup: 0.02089, feed_in_costs: 0, feed_in_bonus: -0.02089, feed_in_vat: false },
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Verkoopvergoeding") },
        uitleg: nt("Essent: (beursprijs + inkoopvergoeding + energiebelasting) × 1,21, per uur met het gemiddelde van de vier kwartierprijzen. Inkoopvergoeding € 0,02089 zonder btw (€ 0,02528 met), uit de prijs-API van Essent."),
        terug: nt("Tot 2027 krijg je tot je jaarverbruik per uur hetzelfde tarief terug als je betaalt, inclusief btw, energiebelasting en inkoopvergoeding. Over een jaaroverschot de beursprijs zonder btw min € 0,02089 verkoopvergoeding; komt dat negatief uit, dan wordt het € 0. Geen terugleverkosten."),
        bronnen: [
          "https://www.essent.nl/energie/energiecontract/dynamisch",
          "https://www.essent.nl/-/media/essent/documenten/productvoorwaarden/202601_essent_productvoorwaarden_dynamisch.pdf",
          "https://www.essent.nl/api/public/dynamicpricing/dynamic-prices/v1",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Terugleverkosten in 42 schalen: een vast bedrag per dag naar je teruglevering, met btw ('geldig per 1 januari 2025'); de tabel staat op de pagina terugleverkosten. Boven salderen € 0,15 per kWh. Vanaf 2027 per kWh in plaats van schalen."),
        bronnen: ["https://www.essent.nl/zonnepanelen/kosten/terugleverkosten"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Terugleverkosten in dezelfde 42 schalen als bij vast, per dag. Boven salderen € 0,15 per kWh. Vanaf 2027 per kWh in plaats van schalen."),
        bronnen: ["https://www.essent.nl/zonnepanelen/kosten/terugleverkosten"],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch; de prijs-API van Essent en de core-integratie geven de gasprijs met inkoopvergoeding en energiebelasting."),
        bronnen: ["https://www.essent.nl/energie/energiecontract/dynamisch"],
      },
      vast: {
        velden: {},
        uitleg: nt("Gas vast; de prijs per m³ staat in je contract."),
        bronnen: ["https://www.essent.nl/energie/energiecontract/dynamisch"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel; de prijs per m³ staat in je contract."),
        bronnen: ["https://www.essent.nl/energie/energiecontract/dynamisch"],
      },
    },
    ha: {
      stroom: ["essent_current_electricity_price"],
      gas: [],
    },
    onzeker: [
      nt("Vaste leveringskosten bij dynamisch alleen van vergelijkers, en die spreken elkaar tegen (€ 7,49 tegen € 10,49 tot € 10,99)."),
      nt("De schalen voor terugleverkosten staan er als 'geldig per 1 januari 2025'; of ze in 2026 gelijk zijn, staat er niet."),
      nt("Of de € 0,15 boven salderen met of zonder btw is, staat er niet; daarom niet ingevuld."),
      nt("De core-integratie Essent is waarschijnlijk stuk sinds juni 2026: de prijs-API vraagt een extra header die de bibliotheek niet meestuurt."),
    ],
  },
  {
    id: "frank-energie",
    naam: "Frank Energie",
    website: "https://www.frankenergie.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: { supplier_markup: 0.015 },
        namen: {
          opslag: nt("Inkoopvergoeding"),
          vergoeding: nt("Inkoopvergoeding teruglevering"),
          bonus: nt("Terugleverbonus"),
          opslagNaBtw: true,
        },
        uitleg: nt("Frank Energie: (marktprijs + energiebelasting) × 1,21, plus € 0,01815 inkoopvergoeding met btw (€ 0,015 zonder), uit de prijs-API van Frank. In de app kies je zelf tussen kwartier- en uurprijzen."),
        terug: nt("Je krijgt de EPEX-marktprijs van het uur of kwartier van teruglevering. Terugleverkosten zijn er niet, behalve de inkoopvergoeding teruglevering; of die erbij komt of eraf gaat, zegt Frank niet eenduidig. Met de dienst Slim Terugleveren komt er overdag, bij een positieve prijs, een terugleverbonus van ongeveer 15% over de marktprijs bij, tot 7.500 kWh per jaar; de hoogte bepaalt Frank zelf."),
        bronnen: [
          "https://www.frankenergie.nl/dynamisch-energiecontract",
          "https://cdn.sanity.io/files/8navd656/production/5203395e7d743fded9f20a73d723132aae1d3db0.pdf",
          "https://www.frankenergie.nl/nl/kennisbank/zonnepanelen/terugleververgoeding",
          "https://www.frankenergie.nl/nl/slimme-diensten/slim-terugleveren",
          "https://cdn.sanity.io/files/8navd656/production/5b225d016ecef83b057f6f8c24e48ca01d1057bb.pdf",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Vaste terugleveringskosten: een vast bedrag per dag naar je opgewekte stroom per jaar, in schalen die op het tarievenblad bij je overeenkomst staan. De terugleververgoeding na salderen staat ook in je overeenkomst."),
        bronnen: [
          "https://cdn.sanity.io/files/8navd656/production/fc4e470a5a76202a07f99589299e225429db35ae.pdf",
          "https://www.frankenergie.nl/nl/voorwaarden",
        ],
      },
      variabel: {
        velden: {},
        uitleg: nt("Vaste terugleveringskosten: een vast bedrag per dag naar je opgewekte stroom per jaar, in schalen die op het tarievenblad bij je overeenkomst staan. De terugleververgoeding na salderen staat ook in je overeenkomst en kan met elke tariefwijziging veranderen."),
        bronnen: [
          "https://cdn.sanity.io/files/8navd656/production/4875797579c53d37796e65e275525833f0bdd31d.pdf",
          "https://www.frankenergie.nl/nl/voorwaarden",
        ],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch."),
        bronnen: ["https://www.frankenergie.nl/nl/voorwaarden"],
      },
      vast: {
        velden: {},
        uitleg: nt("Gas vast, ook naast dynamische stroom (Dynamisch Product met Vaste Gasprijs) en als wintervast contract."),
        bronnen: ["https://www.frankenergie.nl/nl/voorwaarden"],
      },
    },
    ha: {
      stroom: ["frank_energie_stroomprijzen_huidige_elektriciteitsprijs_all_in", "huidige_elektriciteitsprijs_all_in"],
      gas: [],
    },
    onzeker: [
      nt("Inkoopvergoeding teruglevering niet ingevuld: de kennisbank zegt € 0,0182 bovenop de marktprijs, de productvoorwaarden noemen hem als enige terugleverkosten, Gaslicht.com zegt 'in mindering', Keuze.nl € 0,0127 eraf zonder Slim Terugleveren."),
      nt("Of de marktprijs bij teruglevering met of zonder btw wordt vergoed, staat er niet."),
      nt("Terugleverbonus: Frank zegt ongeveer 15%, de voorwaarden zeggen variabel en naar eigen inzicht; daarom geen percentage ingevuld."),
      nt("Uur of kwartier kies je zelf in de app; hier staat kwartier, de standaard van de HACS-integratie."),
      nt("Vaste leveringskosten alleen van vergelijkers, en die verschillen: € 6,00 (Gaslicht.com) tegen € 7,00 (Overstappen.nl)."),
      nt("De bedragen van de schalen bij vast en variabel zijn niet openbaar."),
    ],
  },
  {
    id: "gewoon-energie",
    naam: "Gewoon Energie",
    website: "https://gewoonenergie.nl",
    peildatum: "2026-10-18",
    stroom: {
      vast: {
        velden: {},
        uitleg: nt("Gewoon Energie is een handelsnaam van Innova Energie. Vast 1 of 3 jaar: de terugleverkosten en de terugleververgoeding staan in je persoonlijke aanbod; een openbaar tariefblad is er niet."),
        bronnen: ["https://gewoonenergie.nl/stroom-en-gas/", "https://gewoonenergie.nl/tarieven/"],
      },
      variabel: {
        velden: { feed_in_costs: 0.1331, feed_in_tariff: 0.05 },
        uitleg: nt("Gewoon Energie is een handelsnaam van Innova Energie. Terugleverkosten € 0,1331 per kWh met btw over elke teruggeleverde kWh (tariefblad 1 november 2026). Boven salderen € 0,05 per kWh, voor een huishouden zonder btw; vanaf 2027 50% van het normaaltarief. Vaste leveringskosten € 101,64 per jaar met btw."),
        bronnen: [
          "https://gewoonenergie.nl/wp-content/uploads/2026/09/Tariefblad-Var-Var-01-11-2026-Gewoon-Energie.pdf",
          "https://gewoonenergie.nl/tarieven/",
        ],
      },
    },
    gas: {
      vast: {
        velden: {},
        uitleg: nt("Gas vast, 1 of 3 jaar; de prijs per m³ staat in je aanbod."),
        bronnen: ["https://gewoonenergie.nl/stroom-en-gas/"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel; de prijs per m³ staat op het variabele tariefblad."),
        bronnen: ["https://gewoonenergie.nl/tarieven/"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Terugleverkosten en terugleververgoeding bij vast: alleen in het persoonlijke aanbod."),
      nt("Of het variabele tarief nog voor nieuwe klanten geldt; de site verkoopt vooral vast."),
    ],
  },
  {
    id: "gezinsenergie",
    naam: "Gezinsenergie",
    website: "https://www.gezinsenergie.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        velden: {},
        namen: { opslag: nt("Inkoopvergoeding") },
        uitleg: nt("Gezinsenergie is tussenpersoon; je contract sluit je met Hezelaer Energy. Bij dynamisch betaal je de beursprijs plus een inkoopvergoeding. Er zijn geen bedragen gepubliceerd; het aanbod gaat op maat."),
        terug: nt("Tot 2027 krijg je voor elke teruggeleverde kWh het tarief van dat uur, inclusief energiebelasting; over een jaaroverschot geen energiebelasting. Hezelaer rekent terugleveringskosten per kWh over je hele teruglevering; het bedrag staat in je contract."),
        bronnen: [
          "https://www.gezinsenergie.nl/faq/",
          "https://www.hezelaer.nl/assets/pdf/aanvullend-voorwaardenoverzicht-kleinverbruik-aansluitingen-v30.pdf",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Vast 1 of 3 jaar, en dynamisch-vast (zomer dynamisch, winter 6 maanden vast). Bedragen voor levering en teruglevering op maat; Hezelaer rekent terugleveringskosten per kWh, het bedrag staat in je contract."),
        bronnen: [
          "https://www.gezinsenergie.nl/particulier-aanbod/",
          "https://www.hezelaer.nl/assets/pdf/aanvullend-voorwaardenoverzicht-kleinverbruik-aansluitingen-v30.pdf",
        ],
      },
      variabel: {
        velden: {},
        uitleg: nt("Variabel, op maat; Hezelaer rekent terugleveringskosten per kWh, het bedrag staat in je contract."),
        bronnen: [
          "https://www.gezinsenergie.nl/particulier-aanbod/",
          "https://www.hezelaer.nl/assets/pdf/aanvullend-voorwaardenoverzicht-kleinverbruik-aansluitingen-v30.pdf",
        ],
      },
    },
    gas: {
      vast: {
        velden: {},
        uitleg: nt("Gas vast, via Hezelaer Energy; de prijs staat in je contract."),
        bronnen: ["https://www.gezinsenergie.nl/over-ons/"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel, via Hezelaer Energy; de prijs staat in je contract."),
        bronnen: ["https://www.gezinsenergie.nl/over-ons/"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Geen enkel tarief gepubliceerd; het aanbod gaat op maat."),
      nt("Uur of kwartier: de FAQ zegt uur, de pagina dynamisch-vast kwartierprijzen, en Hezelaer rekent af op de kleinste beschikbare meetgegevens."),
      nt("Of de inkoopvergoeding van Hezelaer ook over teruglevering gaat (de voorwaarden zeggen 'verbruikte én/of teruggeleverde hoeveelheid')."),
      nt("De privacyverklaring noemt nog VanHelder als vergunninghouder."),
    ],
  },
  {
    id: "greenchoice",
    naam: "Greenchoice",
    website: "https://www.greenchoice.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: {},
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Verkoopvergoeding") },
        uitleg: nt("Het dynamische contract van Greenchoice draait op het platform van EnergyZero, dat dan je leverancier is. De prijs per kwartier is de EPEX-marktprijs plus inkoopvergoeding, energiebelasting en btw; Greenchoice noemt de inkoopvergoeding en de vaste leveringskosten zonder bedrag."),
        terug: nt("Tot 2027 krijg je voor teruglevering hetzelfde tarief als je op dat moment betaalt, inclusief belasting. Greenchoice rekent een vast bedrag per teruggeleverde kWh; volgens Keuze.nl € 0,0224, net als bij EnergyZero. Bij een negatieve prijs betaal je voor teruglevering."),
        bronnen: [
          "https://www.greenchoice.nl/dynamisch-energiecontract/",
          "https://support.energyzero.nl/hc/nl/articles/34692105423773-Hoe-hoog-is-de-verkoopvergoeding",
          "https://www.keuze.nl/nieuws/zo-anders-gaan-dynamische-leveranciers-om-met-terugleveren-bij-zonnepanelen",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Terugleverkosten per kWh over alle teruglevering, op het tarievenblad bij je contract (volgens Keuze.nl 13,6 cent); ook na 2027 per kWh. De netto terugleververgoeding geldt alleen voor wat na salderen overblijft, zonder belastingen."),
        bronnen: ["https://media.greenchoice.nl/media/iume2iab/voorwaarden-teruglevering.pdf"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Terugleverkosten per kWh over alle teruglevering, op het tarievenblad bij je contract. Bij het modelcontract variabel (18 mei 2026): € 0,13099 per kWh met btw, en een netto terugleververgoeding van € 0,141 per kWh, zonder btw."),
        bronnen: [
          "https://media.greenchoice.nl/media/5bmlwlh3/tarieven-modelcontract-20260518.pdf",
          "https://media.greenchoice.nl/media/iume2iab/voorwaarden-teruglevering.pdf",
        ],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch, prijs per dag, met inkoopvergoeding, energiebelasting en btw."),
        bronnen: ["https://www.greenchoice.nl/dynamisch-energiecontract/"],
      },
      vast: {
        velden: {},
        uitleg: nt("Gas vast; de prijs per m³ staat in je contract."),
        bronnen: ["https://www.greenchoice.nl"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel; de prijs per m³ staat op het tarievenblad bij je contract."),
        bronnen: ["https://media.greenchoice.nl/media/5bmlwlh3/tarieven-modelcontract-20260518.pdf"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Inkoopvergoeding en vaste leveringskosten van het dynamische contract staan niet op de site van Greenchoice; of de bedragen van EnergyZero zelf gelden, is niet bevestigd."),
      nt("De verkoopvergoeding van € 0,0224 komt van Keuze.nl en klopt met EnergyZero, maar Greenchoice noemt zelf geen bedrag."),
      nt("Terugleververgoeding bij vast: Keuze.nl € 0,15 en Overstappen.nl € 0,0846 spreken elkaar tegen."),
      nt("De HACS-integratie van Greenchoice geeft de tarieven van een vast of variabel contract, geen dynamische prijs. De core-integratie EnergyZero geeft een all-in prijs zonder inkoopvergoeding."),
    ],
  },
  {
    id: "groenestroomlokaal",
    naam: "GroeneStroomLokaal",
    website: "https://groenestroomlokaal.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        velden: {},
        namen: { opslag: nt("Inkoopkosten") },
        uitleg: nt("GroeneStroomLokaal is een wederverkoper van EnergyZero, zonder eigen vergunning. Flexcontract (voorwaarden april 2021): EPEX-prijs + inkoopkosten, vermeerderd met energiebelasting en btw. Op de eigen site staan geen bedragen; Overstappen.nl noemt € 0,03388 opslag en € 5 vaste kosten per maand."),
        terug: nt("Kennisbank (2020): binnen salderen krijg je het actuele uurtarief inclusief belastingen en inkoopkosten; voor netto teruglevering op de jaarrekening alleen het overeengekomen tarief."),
        bronnen: [
          "https://groenestroomlokaal.nl",
          "https://groenestroomlokaal.nl/assets/Voorwaarden/gsl-flexcontract-leveringsvoorwaarden-uurprijs-elektriciteit-bijlage-d1-april-2021.pdf",
          "https://groenestroomlokaal.zendesk.com/hc/nl/articles/360013413778-Welke-terugleververgoeding-ontvang-ik",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Tot 3 jaar vast. Kennisbank (2020): teruglevering tegen hetzelfde tarief als afname, inclusief inkoopkosten en belastingen; netto teruglevering tegen het overeengekomen tarief. Over terugleverkosten is niets gevonden."),
        bronnen: [
          "https://groenestroomlokaal.nl",
          "https://groenestroomlokaal.zendesk.com/hc/nl/articles/360013413778-Welke-terugleververgoeding-ontvang-ik",
        ],
      },
    },
    gas: {},
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Of GroeneStroomLokaal nog nieuwe klanten aanneemt: het certificaat van de site was verlopen en de voorwaarden en kennisbank zijn van 2020 en 2021."),
      nt("Opslag en vaste kosten alleen van Overstappen.nl, zonder btw-vermelding; daarom niet ingevuld."),
      nt("Uur of kwartier: de voorwaarden van 2021 zeggen uur, de huidige stand is niet gevonden."),
      nt("Verkoopvergoeding, negatieve prijzen en de regeling na 2027: niets gevonden; mogelijk gelden die van EnergyZero."),
      nt("De core-integratie EnergyZero geeft een all-in prijs zonder inkoopkosten."),
    ],
  },
  {
    id: "groenmij",
    naam: "Groenmij",
    website: "https://groenmij.nl",
    peildatum: "2026-10-18",
    stroom: {
      vast: {
        velden: {},
        uitleg: nt("Groenmij levert op de vergunning van ServiceHouse (onderdeel van Coolblue). Vast 1, 3 of 5 jaar; tarieven en terugleverkosten zijn niet gepubliceerd."),
        bronnen: [
          "https://groenmij.nl",
          "https://docs.servicehouse.nl/groenmij/energie_algemene_leveringsvoorwaarden_kleinverbruikers.pdf",
        ],
      },
    },
    gas: {},
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Of Groenmij nog nieuwe klanten aanneemt: de aanmeldsite was op 18-10-2026 onbereikbaar."),
      nt("Terugleverkosten en terugleververgoeding: niet gepubliceerd."),
    ],
  },
  {
    id: "groenpand-energie",
    naam: "Groenpand Energie",
    website: "https://www.groenpand.nl/groene-stroom-en-gas",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        velden: { supplier_markup: 0.02 },
        namen: { opslag: nt("Opslag"), vergoeding: nt("Afslag teruglevering") },
        uitleg: nt("Groenpand Energie (handelsnaam van Chiriqui B.V., eigen vergunning): marktprijs + opslag van € 0,02 zonder btw (€ 0,0242 met), plus energiebelasting en 21% btw, volgens de tariefwidget op de site. Vastrecht € 8,47 per maand."),
        terug: nt("Volgens de gegevens achter de tariefwidget krijg je de kale marktprijs min een afslag van € 0,02 per kWh zonder btw (€ 0,0242 met). Bij negatieve prijzen betaal je zelf voor teruglevering."),
        bronnen: [
          "https://www.groenpand.nl/groene-stroom-en-gas/tarieven",
          "https://kwp.eabo.nl/kwp/system/products/product.php?suppid=53&name=groen&type=historic",
          "https://www.groenpand.nl/groene-stroom-en-gas/dynamisch-contract",
        ],
      },
      vast: {
        velden: { feed_in_tariff: 0.02 },
        uitleg: nt("Nieuwe klanten: alleen het modelcontract 1 jaar vast (per 1 april 2026), andere vaste tarieven op aanvraag. Netto terugleververgoeding € 0,02 per kWh met btw, voor wat je op jaarbasis meer teruglevert dan afneemt. Vastrecht € 22,99 per maand met btw."),
        bronnen: ["https://www.groenpand.nl/groene-stroom-en-gas/modelcontract"],
      },
      variabel: {
        velden: { feed_in_tariff: 0.02 },
        uitleg: nt("Nieuwe klanten: alleen het modelcontract variabel (per 1 april 2026). Netto terugleververgoeding € 0,02 per kWh met btw, voor wat je op jaarbasis meer teruglevert dan afneemt. Bestaande variabele tarieven wijzigen maandelijks."),
        bronnen: [
          "https://www.groenpand.nl/groene-stroom-en-gas/modelcontract",
          "https://www.groenpand.nl/groene-stroom-en-gas/tarieven",
        ],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch, prijs per dag."),
        bronnen: ["https://www.groenpand.nl/groene-stroom-en-gas/dynamisch-contract"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel; de prijs staat in de tariefwidget op de site."),
        bronnen: ["https://www.groenpand.nl/groene-stroom-en-gas/tarieven"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Uur of kwartier: de eigen pagina zegt per uur (met voorbeelden uit 2024), de voorwaarden laten het open."),
      nt("Of het vastrecht van € 8,47 met of zonder btw is, staat er niet (8,47 is precies 7,00 × 1,21)."),
      nt("De afslag bij teruglevering staat alleen in de gegevens achter de widget, en of Groenpand teruglevering met of zonder btw vergoedt, zegt het niet; daarom niet ingevuld."),
      nt("De modelcontracttarieven zijn van 1 april 2026; het variabele modelcontract wijzigt per kwartaal."),
      nt("Terugleverkosten bij vast en variabel: 'geen terugleverboetes' op de site, maar de bevestigingsbrieven hebben een veld voor terugleverkosten."),
    ],
  },
  {
    id: "hegg-energy",
    naam: "Hegg Energy",
    website: "https://www.hegg.energy",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: { feed_in_costs: 0 },
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Verkoopvergoeding") },
        uitleg: nt("Hegg Energie Diensten is een handelsnaam van EnergyZero en draait op dat platform. Kwartierprijs EPEX + inkoopvergoeding, vermeerderd met energiebelasting en btw. Inkoopvergoeding € 0,02242 per kWh (bij de varianten Batterij sturing en V2G € 0,017), zonder btw-vermelding. Vaste leveringskosten € 7,50 per maand per aansluiting."),
        terug: nt("Je krijgt de kwartierprijs min een verkoopvergoeding van € 0,02242 per kWh (bij Batterij sturing en V2G € 0), ook over teruglevering uit een batterij of auto. Hegg rekent geen terugleverkosten. Tot 2027 telt een gesaldeerde kWh volgens Hegg evenveel als een verbruikte."),
        bronnen: [
          "https://support.hegg.energy/hc/nl/articles/30235431043612-Onze-tarieven-bij-dynamische-energie-wat-betaal-je-per-variant",
          "https://storage.googleapis.com/energyzero-terms-and-conditions/0c9cfcd4-591c-471a-8be4-bdd52b306d48/productvoorwaarden_dynamische_prijs_stroom_bijlage_d1.pdf",
          "https://support.hegg.energy/hc/nl/articles/16909701981340-Hoe-werkt-het-salderen-en-wat-veranderd-er-in-2027",
        ],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch (variant Alleen gas/stroom); vaste leveringskosten € 7,50 per maand per aansluiting."),
        bronnen: [
          "https://support.hegg.energy/hc/nl/articles/30235431043612-Onze-tarieven-bij-dynamische-energie-wat-betaal-je-per-variant",
        ],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Of de inkoopvergoeding, de verkoopvergoeding en de vaste kosten met of zonder btw zijn, zegt Hegg niet: de eigen tabel met eerdere inkoopvergoedingen is zonder btw, EnergyZero noemt hetzelfde bedrag als verkoopvergoeding met btw. Daarom niet ingevuld."),
      nt("Overstappen.nl noemt voor Hegg € 0,03388 per kWh, Hegg zelf € 0,02242."),
      nt("Hoe salderen precies rekent: de productvoorwaarden noemen het jaargemiddelde van de kwartierprijzen, de kennisbank de prijs van het moment."),
      nt("Of de verkoopvergoeding na 2027 blijft."),
      nt("De core-integratie EnergyZero geeft een all-in prijs zonder de inkoopvergoeding van Hegg."),
    ],
  },
  {
    id: "holland-energie",
    naam: "Holland Energie",
    website: "https://holland-energie.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: {},
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Afslag teruglevering") },
        uitleg: nt("Holland Energie (Nieuw-Hollands Energiebedrijf, vooral zakelijk): de EPEX-kwartierprijs plus een inkoopvergoeding, met btw over alle kosten en heffingen. De link naar de tarieven op de site geeft 'pagina niet gevonden'."),
        terug: nt("Volgens de pagina dynamische energie krijg je de marktprijs per kwartier min een lage terugleververgoeding; de energiebelasting wordt op jaarbasis gesaldeerd tot je verbruik."),
        bronnen: [
          "https://holland-energie.nl/dynamische-energie/",
          "https://holland-energie.nl/teruglevertarief-en-salderingsregeling/",
        ],
      },
      vast: {
        velden: { feed_in_costs: 0.01, feed_in_tariff: 0.026 },
        uitleg: nt("Modelcontract vast (per 1 juli 2026): terugleverkosten € 0,01 per kWh en een terugleververgoeding van € 0,026 per kWh, met btw; vanaf 2027 dezelfde bedragen. Vaste leveringskosten € 9,99 per maand."),
        bronnen: [
          "https://holland-energie.nl/wp-content/uploads/2026/06/modelcontract-tarieven-stroom-en-gas-vast-vanaf-1-juli-2026.pdf",
        ],
      },
      variabel: {
        velden: { feed_in_costs: 0.01, feed_in_tariff: 0.026 },
        uitleg: nt("Modelcontract variabel (per 1 juli 2026): terugleverkosten € 0,01 per kWh en een terugleververgoeding van € 0,026 per kWh, met btw. Vaste leveringskosten € 9,99 per maand."),
        bronnen: [
          "https://holland-energie.nl/wp-content/uploads/2026/06/Modelcontract-tarieven-stroom-en-gas-variabel-vanaf-1-juli-2026.pdf",
        ],
      },
    },
    gas: {
      vast: {
        velden: {},
        uitleg: nt("Gas vast, in hetzelfde modelcontract als stroom."),
        bronnen: [
          "https://holland-energie.nl/wp-content/uploads/2026/06/modelcontract-tarieven-stroom-en-gas-vast-vanaf-1-juli-2026.pdf",
        ],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel, in hetzelfde modelcontract als stroom."),
        bronnen: [
          "https://holland-energie.nl/wp-content/uploads/2026/06/Modelcontract-tarieven-stroom-en-gas-variabel-vanaf-1-juli-2026.pdf",
        ],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Inkoopvergoeding en vaste leveringskosten van het dynamische contract niet gevonden."),
      nt("Teruglevering bij dynamisch: de eigen pagina's spreken elkaar tegen (marktprijs min een afslag, tegenover het leveringstarief inclusief belastingen)."),
      nt("De pagina's over salderen zijn voor zakelijke klanten geschreven."),
      nt("De bedragen bij vast en variabel gelden voor het modelcontract; of huishoudens andere vaste of variabele contracten kunnen kiezen, staat er niet."),
    ],
  },
  {
    id: "innova-energie",
    naam: "Innova Energie",
    website: "https://www.innovaenergie.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: {},
        namen: { opslag: nt("Opslag"), vergoeding: nt("Afslag") },
        uitleg: nt("Innova: de spotprijs per uur (EPEX Day Ahead) plus een opslag per kWh, daarover btw en daarna de energiebelasting. Volgens de voorwaarden staat de opslag op de website, maar daar is hij niet te vinden; vergelijkers noemen € 0,01243 en € 0,018."),
        terug: nt("Per uur gesaldeerd: lever je in een uur meer terug dan je verbruikt, dan krijg je de gewogen gemiddelde spotprijs min een afslag per kWh (bedrag niet gevonden). De energiebelasting wordt op jaarbasis gesaldeerd. De site noemt een 'hoge terugleverbonus' zonder bedrag of voorwaarden."),
        bronnen: [
          "https://www.innovaenergie.nl/innova-dynamisch/",
          "https://www.innovaenergie.nl/wp-content/uploads/2026/06/Contract-en-Productvw-DP-Particulier-KV-CL-2025.12.30-v.3.0-IE.pdf",
          "https://www.innovaenergie.nl/dynamisch-energiecontract/",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Vast 1 of 3 jaar: terugleverkosten en vergoeding staan in je persoonlijke aanbod. Bij het modelcontract vast 1 jaar (16 oktober 2026): terugleverkosten € 0,1331 per kWh met btw tot 2027 en € 0,10692 daarna, terugleververgoeding € 0,10962 zonder btw."),
        bronnen: [
          "https://www.innovaenergie.nl/wp-content/uploads/2026/10/Innova-Tariefblad_MODELCONTRACT_VAST-per-16-10-2026-.pdf",
        ],
      },
      variabel: {
        velden: { feed_in_costs: 0.1331, feed_in_tariff: 0.05 },
        uitleg: nt("Terugleverkosten € 0,1331 per kWh met btw over elke teruggeleverde kWh (tariefblad 1 november 2026). Boven salderen € 0,05 per kWh, voor een huishouden zonder btw; vanaf 2027 50% van het normaaltarief. Vaste leveringskosten € 101,64 per jaar met btw."),
        bronnen: [
          "https://www.innovaenergie.nl/wp-content/uploads/2026/09/Tariefblad-Var-Var-01-11-2026-Innova-Energie.pdf",
        ],
      },
    },
    gas: {
      vast: {
        velden: {},
        uitleg: nt("Gas vast, ook als Hybride: dynamische stroom met vast gas."),
        bronnen: ["https://www.innovaenergie.nl/dynamische-stroom-en-vast-gas/"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel; de prijs per m³ staat op het variabele tariefblad."),
        bronnen: [
          "https://www.innovaenergie.nl/wp-content/uploads/2026/09/Tariefblad-Var-Var-01-11-2026-Innova-Energie.pdf",
        ],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Opslag, afslag en vaste leveringskosten van het dynamische contract: niet op de site, en vergelijkers spreken elkaar tegen (€ 0,01243 en € 0,018 per kWh)."),
      nt("Hoogte en voorwaarden van de 'hoge terugleverbonus'."),
      nt("Of en wanneer Innova naar kwartierprijzen gaat ('voorlopig uurprijzen', 'verwacht in 2026')."),
      nt("Terugleverkosten bij de gewone vaste contracten, vooral vanaf 2027: Keuze.nl € 0,06398, Energievergelijk.nl € 0,133."),
      nt("Of het variabele contract nog voor nieuwe klanten openstaat."),
    ],
  },
  {
    id: "kikker-energie",
    naam: "Kikker Energie",
    website: "https://www.kikker.nl",
    peildatum: "2026-10-18",
    stroom: {
      variabel: {
        velden: { feed_in_tariff: 0.0242 },
        uitleg: nt("Kikker levert vooral via wederverkopers onder hun eigen naam (zoals Noord Dynamic, Dynamiq en Volti); openbaar is alleen het modelcontract (vanaf 1 oktober 2026). Terugleverkosten in schalen naar je teruglevering per jaar; je schaal staat in je bevestigingsbrief (schatting € 0,67 per dag bij 2.350 kWh). Boven salderen € 0,0242 per kWh, met btw."),
        bronnen: [
          "https://www.kikker.nl/intro/model-contract",
          "https://storage.googleapis.com/kikkerprodbucket/static-files/model-contract-tariffs.json",
        ],
      },
    },
    gas: {},
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Of Kikker zelf nog nieuwe klanten aanneemt buiten wederverkopers om; alleen het modelcontract is openbaar."),
      nt("De schalen van de terugleverkosten zijn niet gepubliceerd."),
      nt("De ACM legde Kikker in 2026 een bindende aanwijzing op; het beroep loopt nog."),
    ],
  },
  {
    id: "live-energy",
    naam: "Live Energy",
    website: "https://www.liveenergy.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: {},
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Inkoopvergoeding, bij teruglevering") },
        uitleg: nt("Live Energy, een handelsnaam van OpenSource Energie: leveringstarief zonder btw = EPEX-kwartierprijs + inkoopvergoeding (bij groene stroom ook de kosten van garanties van oorsprong), vermeerderd met energiebelasting en btw. Het bedrag staat in je klantportaal; volgens Selectra € 0,0242 per kWh."),
        terug: nt("Per kwartier verrekend met je verbruik: voor een overschot krijg je de marktprijs min de inkoopvergoeding. De energiebelasting wordt op jaarbasis gesaldeerd. Bij een negatieve prijs betaal je voor teruglevering."),
        bronnen: [
          "https://www.liveenergy.nl/dynamisch-energiecontract-1",
          "https://bestanden.liveenergy.nl/productvoorwaarden-kvb.pdf",
          "https://selectra.nl/energie/energieleverancier/live-energy/tarieven",
        ],
      },
    },
    gas: {},
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Inkoopvergoeding € 0,0242 alleen van Selectra, zonder btw-vermelding; daarom niet ingevuld."),
      nt("Vaste leveringskosten en het bedrag dat bij teruglevering afgaat: niet gepubliceerd."),
    ],
  },
  {
    id: "mega",
    naam: "Mega",
    website: "https://www.mega.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: { supplier_markup: 0.015041 },
        namen: { opslag: nt("Verbruiksopslag"), vergoeding: nt("Inkooptoeslag") },
        uitleg: nt("Mega: de kwartierprijs bestaat uit de EPEX-prijs, een vaste verbruiksopslag per kWh en de overheidsheffingen (energiebelasting en btw). Mega publiceert de opslag niet; volgens Gaslicht.com € 0,0182 met btw (Keuze.nl € 0,01815), en vaste leveringskosten € 6,05 per maand met btw."),
        terug: nt("Per kwartier verrekend: voor netto teruglevering de kale kwartierprijs min een inkooptoeslag; volgens Keuze.nl € 0,03025 per kWh. De energiebelasting wordt op jaarbasis gesaldeerd. Bij een negatieve prijs betaal je voor teruglevering."),
        bronnen: [
          "https://s3.eu-west-3.amazonaws.com/mega.nl/files/MegaDynamisch+productvoorwaarden.pdf",
          "https://www.gaslicht.com/stroom-vergelijken/mega/stroom-dynamisch-5324",
          "https://www.keuze.nl/energie/energieleveranciers/mega",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Contracten van na 9 januari 2026 betalen een vast bedrag per teruggeleverde kWh, oudere vaste contracten schalen. Terugleverkosten en vergoeding zijn volgens Mega zonder btw en staan in je overeenkomst; Keuze.nl noemt 17,2 cent terugleverkosten."),
        bronnen: [
          "https://www.mega.nl/veelgestelde-vragen-top-10-vragen/",
          "https://s3.eu-west-3.amazonaws.com/mega.nl/files/Mega+Consument+Productvoorwaarden+Vast+01012026.pdf",
        ],
      },
      variabel: {
        velden: {},
        uitleg: nt("Terugleverkosten een vast bedrag per teruggeleverde kWh, geleidelijk ingevoerd sinds 9 januari 2026. Terugleverkosten en vergoeding zijn volgens Mega zonder btw en staan in je overeenkomst."),
        bronnen: ["https://www.mega.nl/veelgestelde-vragen-top-10-vragen/"],
      },
    },
    gas: {},
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("De verbruiksopslag en de vaste leveringskosten komen alleen van vergelijkers (Gaslicht.com, Keuze.nl)."),
      nt("Inkooptoeslag bij teruglevering (€ 0,03025) alleen van Keuze.nl, zonder btw-vermelding; daarom niet ingevuld."),
      nt("Of Mega de kale kwartierprijs bij teruglevering met of zonder btw vergoedt, staat er niet."),
      nt("Terugleverkosten bij vast (17,2 cent) alleen van Keuze.nl."),
    ],
  },
  {
    id: "nextenergy",
    naam: "NextEnergy",
    website: "https://www.nextenergy.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: { feed_in_costs: 0, feed_in_bonus_percent: 50, bonus_daytime: true, bonus_base: "market" },
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Verkoopvergoeding"), bonus: nt("Zonnebonus") },
        uitleg: nt("NextEnergy: leveringsprijs = beursprijs (het uurgemiddelde van de kwartierprijzen) + inkoopvergoeding, totaalprijs = leveringsprijs + energiebelasting, en btw over alles. Inkoopvergoeding 2,1 cent per kWh met btw voor nieuwe klanten (bestaande klanten naar het moment waarop ze klant werden). Vaste kosten € 5,99 per maand per aansluiting. NextBattery heeft geen inkoopvergoeding."),
        terug: nt("Terugleveringsprijs = beursprijs min verkoopvergoeding, en voor nieuwe contracten is dat de beursprijs. Geen vaste terugleverkosten. Zonnebonus: 50% over de beursprijs, voor zonnestroom tussen 06:00 en 22:00 en alleen bij een positieve prijs, naar rato boven 6.000 kWh per jaar. Tot 2027 wordt de energiebelasting op jaarbasis gesaldeerd."),
        bronnen: [
          "https://www.nextenergy.nl/actuele-energieprijzen",
          "https://www.nextenergy.nl/dynamische-energie",
          "https://www.nextenergy.nl/zonnebonus",
          "https://cdn.prod.website-files.com/63ff1dfc0c5b730bcd39d3fd/6a6080bbdb39bcae5d0e3e08_NE-Aanvullende-Voorwaarden-per-Energieproduct-2026-07-22.pdf",
        ],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch, met 7,9 cent per m³ inkoopvergoeding met btw."),
        bronnen: ["https://www.nextenergy.nl/dynamische-energie"],
      },
      vast: {
        velden: {},
        uitleg: nt("Gas vast of met een prijsplafond (ook als Wintervast)."),
        bronnen: [
          "https://cdn.prod.website-files.com/63ff1dfc0c5b730bcd39d3fd/6a6080bbdb39bcae5d0e3e08_NE-Aanvullende-Voorwaarden-per-Energieproduct-2026-07-22.pdf",
        ],
      },
    },
    ha: {
      stroom: ["nextenergy_current_all_in_price"],
      gas: [],
    },
    onzeker: [
      nt("Inkoopvergoeding niet ingevuld: NextEnergy zegt 2,1 cent met btw (de btw-vermelding staat direct na het gasbedrag), Gaslicht.com en Keuze.nl zeggen 2,19 cent, en bestaande klanten kunnen een ander bedrag hebben."),
      nt("Verkoopvergoeding niet ingevuld: NextEnergy zegt dat nieuwe contracten de beursprijs krijgen, Keuze.nl noemt € 0,01."),
      nt("Of de beursprijs bij teruglevering, en de Zonnebonus daarover, met of zonder btw is, staat er niet."),
      nt("De Zonnebonus geldt van 06:00 tot 22:00; de coach rekent hem van zonsopkomst tot zonsondergang, en telt de grens van 6.000 kWh niet."),
      nt("De HACS-integratie van larsjuhw leest de anonieme prijzen van het klantportaal, met twee decimalen en zonder je eigen inkoopvergoeding; de entiteitnaam is afgeleid uit de code."),
      nt("ANWB kondigde op 16-10-2026 aan NextEnergy over te nemen (ACM-goedkeuring nodig); prijzen en voorwaarden kunnen in 2027 veranderen."),
    ],
  },
  {
    id: "noord-dynamic",
    naam: "Noord Dynamic",
    website: "https://www.noorddynamic.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        velden: {},
        namen: { opslag: nt("Variabele vergoeding") },
        uitleg: nt("Noord Dynamic is een merk op de vergunning van Kikker Energie (niet hetzelfde als Noord Energie). Je betaalt de beursprijs plus een variabele vergoeding; er zijn geen bedragen gepubliceerd."),
        terug: nt("Niets over teruglevering gepubliceerd."),
        bronnen: ["https://www.noorddynamic.nl/"],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch."),
        bronnen: ["https://www.noorddynamic.nl/"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Geen tarieven, geen interval en niets over teruglevering gepubliceerd."),
      nt("Of het merk nog nieuwe klanten aanneemt."),
      nt("De ACM legde Kikker Energie in 2026 een bindende aanwijzing op."),
    ],
  },
  {
    id: "noord-energie",
    naam: "Noord Energie",
    website: "https://noordenergie.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: {},
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Variabele leveringsvergoeding") },
        uitleg: nt("Noord Energie: leveringstarief = beursprijs per kwartier (EPEX Spot Power NL Day Ahead) + inkoopvergoeding, met energiebelasting en btw daarover. De inkoopvergoeding staat in je bevestigingsbrief; volgens Keuze.nl € 0,01936 per kWh. Niet te verwarren met Noord Dynamic, dat via Kikker levert."),
        terug: nt("Wat niet gesaldeerd wordt krijgt de gerealiseerde beursprijs min de overeengekomen variabele leveringsvergoeding (volgens Keuze.nl € 0,0194). Tot en met 2026 wordt de energiebelasting gesaldeerd."),
        bronnen: [
          "https://noordenergie.nl/documents/cms/aanvullende-productvoorwaarden-dynamisch-2026-33ae3319b099.pdf",
          "https://noordenergie.nl/marktprijzen",
          "https://www.keuze.nl/energie/energieleveranciers/noord-energie",
        ],
      },
      vast: {
        velden: { feed_in_costs: 0.121 },
        uitleg: nt("Terugleverkosten € 0,121 per kWh met btw, tot en met 2026, voor teruglevering op momenten dat je opwek hoger is dan je verbruik. Vanaf 2027 de terugleververgoeding (50% van het leveringstarief) min € 0,01. De terugleververgoeding na salderen staat in je bevestiging."),
        bronnen: [
          "https://noordenergie.nl/documents/cms/aanvullende-product-voorwaarden-vaste-looptijd-huishoudelijk-2026-v1-1-7d083c80c3a3.pdf",
        ],
      },
      variabel: {
        velden: {},
        uitleg: nt("Flexibel, maandelijks opzegbaar. Bij het modelcontract variabel (1 oktober 2026): terugleverkosten € 0,14 en terugleververgoeding € 0,15 per kWh, met btw."),
        bronnen: ["https://noordenergie.nl/documents/modelcontract-variabel-1-10-2026.pdf"],
      },
    },
    gas: {
      vast: {
        velden: {},
        uitleg: nt("Gas vast, ook als hybride: dynamische stroom met vast gas."),
        bronnen: ["https://noordenergie.nl/marktprijzen"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Inkoop- en verkoopvergoeding bij dynamisch alleen van Keuze.nl, zonder btw-vermelding; daarom niet ingevuld."),
      nt("Of de terugleverkosten van € 0,121 per kWh ook bij dynamisch gelden: Keuze.nl zegt ja, de dynamische voorwaarden 2026 noemen ze niet."),
      nt("Vaste leveringskosten bij dynamisch: niet gevonden."),
      nt("Terugleverkosten bij het gewone variabele contract (Flexibel): niet gevonden."),
    ],
  },
  {
    id: "om-nieuwe-energie",
    naam: "om | nieuwe energie",
    website: "https://www.samenom.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: { supplier_markup: 0.020661 },
        namen: { opslag: nt("Inkoopvergoeding levering"), vergoeding: nt("Inkoopvergoeding teruglevering") },
        uitleg: nt("om | nieuwe energie: het leveringstarief per kwartier (EPEX Spot Power NL Day Ahead) + inkoopvergoeding levering, daarover energiebelasting en btw. Inkoopvergoeding € 0,020661 zonder btw; voor consumenten staat hij als € 0,13585 per kWh met btw en energiebelasting. Vaste leveringskosten € 0,281781 per dag met btw."),
        terug: nt("Per kwartier gesaldeerd: voor wat je in een kwartier meer teruglevert dan je afneemt, krijg je de marktprijs min de inkoopvergoeding teruglevering (€ 0,025 met btw, € 0,020661 zonder). De energiebelasting wordt op jaarbasis gesaldeerd. Die aftrek blijft ook na 2027."),
        bronnen: [
          "https://www.samenom.nl/tarieven/",
          "https://www.samenom.nl/wp-content/uploads/2026/08/20260814-Overeenkomstvoorwaarden-Consument-Dynamisch.pdf",
          "https://www.samenom.nl/einde-salderingsregeling-2027/",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Een 1 of 3 Jaar Vast uit 2026 betaalt vaste terugleverkosten per kWh, gepubliceerd per maand van afsluiten (oktober 2026: 1 jaar € 0,073801, 3 jaar € 0,054648, met btw). Terugleververgoeding na salderen oktober 2026: 1 jaar € 0,094093, 3 jaar € 0,07452. Vaste contracten uit 2024 en 2025 betalen in schalen, zoals bij variabel."),
        bronnen: ["https://www.samenom.nl/tarieven/", "https://www.samenom.nl/faq-vaste-terugleveringskosten/"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Flex en Variabel: vaste terugleveringskosten per dag in schalen naar je totale teruglevering vóór salderen; tot 1.000 kWh niets, daarboven € 151,25 per jaar en € 60,50 per 500 kWh extra, met btw. Terugleververgoeding na salderen bij Flex in november 2026 € 0,064861 per kWh met btw."),
        bronnen: [
          "https://www.samenom.nl/tarieven/",
          "https://www.samenom.nl/wp-content/uploads/tarieven/terugleveringskosten-2026.pdf",
          "https://www.samenom.nl/vasteterugleveringskosten/",
        ],
      },
    },
    gas: {},
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("De inkoopvergoeding teruglevering is niet ingevuld: de voorwaarden zeggen dat de contractprijs voor teruglevering zonder btw is, de tarievenpagina geeft de aftrek als € 0,025 met btw."),
      nt("Kwartier of uur: voorwaarden en tarievenpagina zeggen kwartier, de productpagina nog per uur."),
      nt("Bij het ophalen meldde de tarievenpagina een storing bij de dynamische tarieven."),
      nt("om fuseert met Energie VanOns en gaat op termijn verder als Energie VanOns; naam, voorwaarden en platform kunnen veranderen."),
    ],
  },
  {
    id: "opensource-energie",
    naam: "OpenSource Energie",
    website: "https://www.opensourceenergie.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: { supplier_markup: 0.02 },
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Vergoeding voor afhandeling") },
        uitleg: nt("OpenSource Energie is vooral een platform voor partners die onder eigen naam leveren. Zelf: (marktprijs per kwartier + inkoopvergoeding + energiebelasting) × 1,21, met € 0,02 inkoopvergoeding zonder btw volgens de prijswidget op de site; bij groene stroom komen de kosten van garanties van oorsprong erbij. Wie een batterij of laadpaal laat sturen, moet dat vooraf melden (SMART-contract)."),
        terug: nt("Voor wat je meer opwekt dan je verbruikt krijg je de marktprijs per tijdseenheid, aangevuld of verminderd met een vergoeding per kWh voor afhandeling; dat bedrag staat nergens."),
        bronnen: [
          "https://www.opensourceenergie.nl/actuele-energieprijzen",
          "https://widget.opensourceenergie.net/api/v2/prices/epex/2026-10-18?brand=default",
          "https://bestanden.opensourceenergie.nl/productvoorwaarden-kvb.pdf",
        ],
      },
      vast: {
        velden: { feed_in_tariff: 0.015 },
        uitleg: nt("Alleen het wettelijke modelcontract (vanaf 1 oktober 2026): tot 2027 € 0,015 per kWh met btw voor wat na salderen overblijft; tot dan noemt de tabel geen terugleverkosten. Vanaf 2027 terugleverkosten € 0,06 en een vergoeding van € 0,1193 per kWh, met btw. Vaste leveringskosten € 8,50 per maand."),
        bronnen: ["https://www.opensourceenergie.nl/nl/modelcontract-vast"],
      },
      variabel: {
        velden: { feed_in_tariff: 0.015 },
        uitleg: nt("Alleen het wettelijke modelcontract (1 oktober 2026 tot 1 januari 2027): € 0,015 per kWh met btw voor wat na salderen overblijft; tot 2027 noemt de tabel geen terugleverkosten. Vanaf 2027 terugleverkosten € 0,0605 en een vergoeding van € 0,13085 per kWh, met btw."),
        bronnen: ["https://www.opensourceenergie.nl/nl/modelcontract-variabel"],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch; de prijswidget rekent € 0,09 per m³ inkoop zonder btw, met de transportkosten erbij."),
        bronnen: ["https://www.opensourceenergie.nl/actuele-energieprijzen"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("De inkoopvergoeding van € 0,02 komt uit de prijswidget (het standaardmerk), niet uit een tariefblad; volgens de voorwaarden staat het bedrag in de offerte, en merken op het platform kunnen een eigen opslag hebben."),
      nt("De kosten van garanties van oorsprong bij groene stroom: geen bedrag gevonden."),
      nt("Teruglevering bij dynamisch: bedrag en richting van de vergoeding voor afhandeling, en of de marktprijs met of zonder btw wordt vergoed, staan nergens."),
      nt("Vaste leveringskosten van het dynamische contract: niet op de site."),
      nt("Of je als particulier zonder partnermerk een contract kunt afsluiten: alleen via een offerte of contact."),
    ],
  },
  {
    id: "oxxio",
    naam: "Oxxio",
    website: "https://www.oxxio.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: { netting_full: true, feed_in_costs: 0, feed_in_vat: false },
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Verkoopvergoeding") },
        uitleg: nt("Oxxio (op het platform van Eneco Group): de marktprijs per uur (EPEX Spot Power NL Hourly) + een kleine inkoopvergoeding + energiebelasting en btw. Oxxio publiceert de inkoopvergoeding niet; Gaslicht.com noemt 2,30 cent met btw, Keuze.nl € 0,02237."),
        terug: nt("Tot 2027 krijg je tot je jaarverbruik per uur hetzelfde tarief terug als je betaalt, inclusief inkoopvergoeding. Over een jaaroverschot de marktprijs van het uur zonder btw, min een vaste verkoopvergoeding per kWh (volgens Keuze.nl € 0,02237). Geen terugleverkosten. Bij een negatieve prijs betaal je voor teruglevering."),
        bronnen: [
          "https://www.oxxio.nl/energiecontract-afsluiten/dynamisch-energiecontract/",
          "https://www.gaslicht.com/userfiles/pdf/energie/oxxio/pakketten/pakket-voorwaarden/PV260923-Oxxio-Productvoorwaarden-Dynamisch.pdf",
          "https://www.gaslicht.com/stroom-vergelijken/oxxio/oxxio-nederlandse-windstroom-dynamisch-5437",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Terugleverkosten een bedrag per kWh over alle teruglevering, in je contract (volgens Keuze.nl 14,2 cent). Over de terugleververgoeding betaal je geen btw; tot 2027 alleen over wat na salderen overblijft."),
        bronnen: ["https://www.oxxio.nl/-/media/oxxio-nl/files/voorwaarden/oxxiovoorwaardenoverzicht2026.pdf"],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch: de marktprijs op het moment van verbruik, plus een kleine inkoopvergoeding per m³, energiebelasting en btw."),
        bronnen: ["https://www.oxxio.nl/energiecontract-afsluiten/dynamisch-energiecontract/"],
      },
      vast: {
        velden: {},
        uitleg: nt("Gas vast, 1 of 3 jaar, ook als Oxxio Hybride: dynamische stroom met vast gas."),
        bronnen: ["https://www.oxxio.nl/energiecontract-afsluiten/dynamisch-energiecontract/"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Inkoopvergoeding niet ingevuld: Gaslicht.com zegt 2,30 cent met btw, Keuze.nl € 0,02237 zonder btw-vermelding."),
      nt("Verkoopvergoeding (€ 0,02237) alleen van Keuze.nl, zonder btw-vermelding."),
      nt("Vaste leveringskosten alleen van Gaslicht.com (€ 6,49 per maand met btw)."),
      nt("Bij vast komen de bedragen alleen van Keuze.nl, dat zelf twee verschillende terugleververgoedingen noemt (€ 0,15156 en € 0,060). Oxxio prijst vast aan voor huizen zonder zonnepanelen."),
    ],
  },
  {
    id: "powerpeers",
    naam: "Powerpeers",
    website: "https://powerpeers.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: { feed_in_costs: 0, feed_in_vat: false },
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Verkoopvergoeding") },
        uitleg: nt("Powerpeers Helemaal Dynamisch: de kwartierprijs op de beurs (EPEX NL Day Ahead) plus een inkoopvergoeding, daarbovenop energiebelasting en btw. Powerpeers noemt € 0,01 inkoopvergoeding, zonder te zeggen of dat met of zonder btw is."),
        terug: nt("Je krijgt de beursprijs per kwartier zonder btw, min een verkoopvergoeding met btw over elke teruggeleverde kWh, ook gesaldeerde; volgens Keuze.nl € 0,01. Geen terugleverkosten. Van 2027 tot 2030 per kwartier minstens 50% van beursprijs plus inkoopvergoeding; het maandtotaal gaat niet onder € 0."),
        bronnen: [
          "https://powerpeers.nl/tarieven/tarieven-helemaal-dynamisch-energiecontract/",
          "https://powerpeers.eu/assets/website/uploads/Powerpeers-contractvoorwaarden_Dynamisch_Stroom.pdf",
          "https://powerpeers.nl/dynamische-energie/terugleverkosten-en-dynamische-energie/",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Vast (voorwaarden 1 augustus 2026): terugleverkosten per teruggeleverde kWh, het bedrag staat in je contract. Oudere vaste contracten kunnen nog de schalen per jaar hebben (tabel 'versie 24 december 2025', € 0 tot 999 kWh)."),
        bronnen: [
          "https://powerpeers.eu/assets/website/uploads/Powerpeers-contractvoorwaarden-vaste-prijs-100_-Groene-Stroom.pdf",
          "https://powerpeers.eu/assets/website/uploads/Powerpeers-vaste-terugleverkosten.pdf",
        ],
      },
      variabel: {
        velden: {},
        uitleg: nt("Tot 2027 vaste terugleverkosten in 40 schalen per jaar, € 0 tot 999 kWh (tabel 'versie 24 december 2025'); vanaf 2027 per kWh. De terugleververgoeding na salderen staat in je contract."),
        bronnen: [
          "https://powerpeers.eu/assets/website/uploads/Powerpeers-contractvoorwaarden-variabel-100-Groene-Stroom.pdf",
          "https://powerpeers.eu/assets/website/uploads/Powerpeers-vaste-terugleverkosten.pdf",
        ],
      },
    },
    gas: {
      vast: {
        velden: {},
        uitleg: nt("Gas vast, ook als Half Dynamisch: dynamische stroom met een vaste gasprijs."),
        bronnen: ["https://powerpeers.nl/voorwaarden/"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel (Maandelijks Wisselend)."),
        bronnen: ["https://powerpeers.nl/voorwaarden/"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Inkoopvergoeding niet ingevuld: Powerpeers zegt niet of € 0,01 met of zonder btw is; Gaslicht.com zegt met btw, Energievergelijk.nl noemde in juni € 0,0085."),
      nt("Verkoopvergoeding (€ 0,01) alleen van Keuze.nl; daarom niet ingevuld."),
      nt("Vaste kosten stroom alleen van Gaslicht.com (€ 6,26 per maand met btw)."),
      nt("Terugleverkosten per kWh bij vast en bij variabel vanaf 2027: bedrag niet gevonden."),
    ],
  },
  {
    id: "pure-energie",
    naam: "Pure Energie",
    website: "https://pure-energie.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: { feed_in_costs: 0, feed_in_vat: false },
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Verkoopvergoeding") },
        uitleg: nt("Pure Energie: bij netto levering in een tariefperiode betaal je de beursprijs plus inkoopvergoeding, met btw; de energiebelasting komt erbovenop. Pure Energie noemt geen bedrag; volgens Keuze.nl € 0,01799 per kWh."),
        terug: nt("Per tariefperiode (nu per uur) verrekend: bij netto teruglevering de beursprijs zonder btw min een verkoopvergoeding per kWh (volgens Keuze.nl € 0,01499). Geen terugleverbijdrage bij dynamisch. De energiebelasting wordt tot 2027 op jaarbasis gesaldeerd."),
        bronnen: [
          "https://pure-energie.nl/groene-stroom/dynamisch-energiecontract/",
          "https://pure-energie.nl/assets/Uploads/Documenten/Voorwaarden/20260501-Aanvullende-voorwaarden-netto-terugleververgoeding-elektriciteit.pdf",
          "https://pure-energie.nl/kennisbank/inkoop-en-verkoopvergoeding-dynamisch-contract/",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Contract afgesloten na 1 april 2026: terugleverkosten per kWh, het bedrag staat in je contract (volgens Keuze.nl € 0,139). Daarvoor: een terugleverbijdrage in schalen, per maand in het termijnbedrag. Netto teruglevering heeft 0% btw."),
        bronnen: [
          "https://pure-energie.nl/groene-stroom/tarieven/terugleverkosten/",
          "https://pure-energie.nl/assets/Productvoorwaarden-Pure-Energie-Elektriciteit-en-Gas-voor-Huishoudelijke-Eindafnemers-20260501.pdf",
        ],
      },
      variabel: {
        velden: {},
        uitleg: nt("Contract afgesloten na 1 april 2026: terugleverkosten per kWh, het bedrag staat in je contract. Daarvoor: een terugleverbijdrage in schalen, per maand in het termijnbedrag. Netto teruglevering heeft 0% btw; normaal en dal worden apart gesaldeerd."),
        bronnen: [
          "https://pure-energie.nl/groene-stroom/tarieven/terugleverkosten/",
          "https://pure-energie.nl/assets/Uploads/Documenten/Voorwaarden/20260501-Aanvullende-voorwaarden-netto-terugleververgoeding-elektriciteit.pdf",
        ],
      },
    },
    gas: {
      vast: {
        velden: {},
        uitleg: nt("Gas vast, ook als Hybride: dynamische stroom met een vast tarief voor gas."),
        bronnen: [
          "https://pure-energie.nl/assets/Productvoorwaarden-Pure-Energie-Elektriciteit-en-Gas-voor-Huishoudelijke-Eindafnemers-20260501.pdf",
        ],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel; de prijs per m³ staat in je contract."),
        bronnen: [
          "https://pure-energie.nl/assets/Productvoorwaarden-Pure-Energie-Elektriciteit-en-Gas-voor-Huishoudelijke-Eindafnemers-20260501.pdf",
        ],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Alle dynamische bedragen (inkoopvergoeding € 0,01799, verkoopvergoeding € 0,01499, abonnement € 12,10) komen alleen van Keuze.nl, zonder btw-vermelding."),
      nt("Uur of kwartier: de website zegt uur, de voorwaarden laten 'ieder uur of ieder kwartier' open."),
      nt("Terugleverkosten per kWh voor contracten na 1 april 2026: Keuze.nl noemt € 0,139, niet bevestigd."),
      nt("Terugleververgoeding bij vast en variabel: Keuze.nl spreekt zichzelf tegen (€ 0,11 tegenover € 0,060)."),
      nt("De core-integratie Pure Energie is voor hun energiemeter en geeft geen prijzen."),
    ],
  },
  {
    id: "samsam-energie",
    naam: "SamSam Energie",
    website: "https://samsam.nu",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: {},
        namen: { opslag: nt("Inkoopvergoeding") },
        uitleg: nt("SamSam levert via EnergyZero (en voor een deel via Kikker Energie). Bovenop de kale uurprijs komen 21% btw, een inkoopvergoeding van € 0,021118 per kWh met btw (de FAQ zegt € 0,02118) en de energiebelasting. Vaste leveringskosten € 7,99 per maand per aansluiting."),
        terug: nt("Je krijgt de marktprijs voor elke teruggeleverde kWh; binnen salderen streep je per uur weg tegen de prijs met btw, de energiebelasting op jaarbasis. Een verkoopvergoeding of terugleverkosten noemt SamSam niet."),
        bronnen: ["https://samsam.nu/groene-energie", "https://samsam.nu/vraag-antwoord"],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch, prijs per dag, met een inkoopvergoeding van € 0,08275 per m³ met btw."),
        bronnen: ["https://samsam.nu/groene-energie"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Inkoopvergoeding niet ingevuld: de site noemt € 0,021118 met btw, de FAQ € 0,02118."),
      nt("Uur of kwartier: SamSam zegt uur, EnergyZero rekent volgens een nieuwsbericht sinds 2026 per kwartier."),
      nt("Of de vaste kosten met of zonder btw zijn."),
      nt("Verkoopvergoeding of terugleverkosten: niet genoemd, dus onbekend of ze er zijn."),
      nt("Home Assistant verwijst voor SamSam naar de core-integratie EnergyZero; die geeft een all-in prijs zonder de inkoopvergoeding van SamSam."),
    ],
  },
  {
    id: "shave-energy",
    naam: "Shave Energy",
    website: "https://www.shave-energy.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: {},
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Vergoeding voor afhandeling") },
        uitleg: nt("Shave Energy is een handelsnaam van OpenSource Energie en levert op diens vergunning. Leveringstarief zonder btw = EPEX-kwartierprijs + inkoopvergoeding (bij groene stroom ook garanties van oorsprong), vermeerderd met energiebelasting en btw. De prijswidget op de site rekent met € 0,02 zonder btw. Wie een batterij of laadpaal laat sturen, moet dat vooraf melden (SMART-contract)."),
        terug: nt("Voor wat je meer opwekt dan je verbruikt krijg je de marktprijs per tijdseenheid, aangevuld of verminderd met een vergoeding per kWh voor afhandeling; dat bedrag staat nergens."),
        bronnen: [
          "https://www.shave-energy.nl/actuele-energieprijzen",
          "https://bestanden.shave-energy.nl/productvoorwaarden-kvb.pdf",
          "https://bestanden.shave-energy.nl/productvoorwaarden-kvb-smart.pdf",
        ],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch."),
        bronnen: ["https://www.shave-energy.nl/stroom-gas"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Inkoopvergoeding niet ingevuld: de prijswidget geeft € 0,02 zonder btw voor elk merk, dus misschien niet het bedrag van Shave; een vergelijker noemde op 10-12-2025 € 0,0303."),
      nt("Vaste leveringskosten (€ 6,05 per maand) alleen van een vergelijker, zonder btw-vermelding."),
      nt("Bedrag en richting van de vergoeding voor afhandeling bij teruglevering."),
      nt("Negatieve prijzen en de regeling na 2027: niet gevonden."),
    ],
  },
  {
    id: "tibber",
    naam: "Tibber",
    website: "https://tibber.com/nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: {},
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Verkoopvergoeding") },
        uitleg: nt("Tibber: de kwartierprijs zonder btw is de EPEX Day Ahead-prijs plus een inkoopvergoeding van € 0,018 per kWh, verhoogd met energiebelasting en btw. Tibber zegt niet of die € 0,018 met of zonder btw is. Vaste kosten € 6,99 per maand voor stroom, sinds 1 september 2026."),
        terug: nt("Je krijgt de gewogen gemiddelde EPEX-kwartierprijs, min een verkoopvergoeding van € 0,018 per kWh met btw (sinds 1 september 2026). Tot 2027 wordt de energiebelasting op jaarbasis gesaldeerd."),
        bronnen: [
          "https://tibber.com/nl/energiecontract",
          "https://tibber.com/nl/stroomprijs",
          "https://tibber.com/nl/voorwaarden/contractvoorwaarden",
        ],
      },
      vast: {
        velden: { feed_in_costs: 0.1, feed_in_tariff: 0.12 },
        uitleg: nt("Alleen het wettelijke modelcontract 1 jaar vast (vanaf 1 april 2026), met afschrikprijzen: terugleverkosten € 0,10 per kWh en een terugleververgoeding van € 0,12 per kWh over overproductie op jaarbasis, met btw."),
        bronnen: ["https://tibber.com/nl/modelcontract"],
      },
      variabel: {
        velden: { feed_in_tariff: 0.01 },
        uitleg: nt("Alleen het wettelijke modelcontract variabel, met afschrikprijzen: een terugleververgoeding van € 0,01 per kWh over overproductie op jaarbasis, met btw."),
        bronnen: ["https://tibber.com/nl/modelcontract"],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch, prijs per dag; vaste kosten € 5,99 per maand voor gas."),
        bronnen: ["https://tibber.com/nl/energiecontract"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Of de inkoopvergoeding (€ 0,018) en de vaste kosten (€ 6,99) met of zonder btw zijn, zegt Tibber niet; daarom geen opslag ingevuld."),
      nt("Verkoopvergoeding niet ingevuld: Tibber noemt hem met btw, maar zegt niet of de kwartierprijs bij teruglevering met of zonder btw wordt vergoed. Keuze.nl noemt nog het oude bedrag van € 0,0248."),
      nt("Wat er bij een negatieve prijs met teruglevering gebeurt, en wat teruglevering boven je jaarverbruik tot 2027 krijgt: niet beschreven."),
      nt("De core-integratie Tibber geeft de all-in prijs als sensor.<huisnaam>_electricity_price; die naam hangt van je huis af en staat hier daarom niet bij. Of die prijs precies die van de app is, is niet nagerekend."),
    ],
  },
  {
    id: "unitedconsumers",
    naam: "UnitedConsumers",
    website: "https://www.unitedconsumers.com/energie",
    peildatum: "2026-10-18",
    stroom: {
      vast: {
        velden: {},
        uitleg: nt("Terugleverkosten een vast tarief per teruggeleverde kWh, op de jaarnota (volgens Keuze.nl 15,4 cent). Terugleververgoeding boven salderen zonder btw en energiebelasting; volgens Keuze.nl € 0,17411 bij 1 jaar en € 0,14171 bij 3 jaar vast. De afgesproken bedragen blijven na 2027 gelijk zolang je contract loopt."),
        bronnen: [
          "https://www.unitedconsumers.com/energie",
          "https://www.keuze.nl/energie/energieleveranciers/unitedconsumers",
        ],
      },
      variabel: {
        velden: {},
        uitleg: nt("Terugleverkosten een tarief per teruggeleverde kWh, op de jaarnota; tarieven kunnen op 1 januari, 1 april, 1 juli en 1 oktober wijzigen. De bedragen staan in Mijn UnitedConsumers."),
        bronnen: [
          "https://www.unitedconsumers.com/downloads/energie/UnitedConsumers-Energie-Productvoorwaarden-variabel-onbepaalde-tijd-versie-3-maart-2026.pdf",
        ],
      },
    },
    gas: {},
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Terugleverkosten en terugleververgoeding komen alleen van Keuze.nl; UnitedConsumers publiceert ze niet openbaar."),
      nt("Terugleververgoeding bij variabel: niet gevonden."),
      nt("Geen dynamisch contract gevonden."),
    ],
  },
  {
    id: "vandebron",
    naam: "Vandebron",
    website: "https://vandebron.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: { feed_in_costs: 0, feed_in_vat: false },
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Verkoopvergoeding") },
        uitleg: nt("Vandebron: je betaalt de marktprijs van het uur (het gemiddelde van vier kwartieren), met energiebelasting en btw, plus een inkoopvergoeding. Vandebron noemt geen bedrag; Keuze.nl noemt € 0,02208, Energievergelijk.nl eerder € 0,0257."),
        terug: nt("Tot je jaarverbruik krijg je de marktprijs met energiebelasting en btw plus de inkoopvergoeding (salderen per uur). Boven die grens alleen de marktprijs zonder energiebelasting en btw, min een verkoopvergoeding (volgens Keuze.nl € 0,01361). Geen vaste terugleverkosten."),
        bronnen: [
          "https://vandebron.nl/energie/energiecontract/dynamisch",
          "https://vandebron.nl/blog/salderen-dynamisch-contract",
          "https://www.gaslicht.com/userfiles/pdf/energie/vandebron/pakketten/pakket-voorwaarden/PV260106-Vandebron-Leveringsvoorwaarden-Dynamisch.pdf",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Terugleverkosten in schalen of per kWh, afhankelijk van je contract: contracten van na 15 juli 2024 hebben 51 schalen, oudere 6. De tabel staat in je contract. De terugleververgoeding na salderen staat ook in je contract; vanaf 2027 minstens 50% van het kale leveringstarief."),
        bronnen: [
          "https://vandebron.nl/energie/energiecontract/vast/met-zonnepanelen",
          "https://vandebron.nl/blog/nieuwe-schaalverdeling-vaste-terugleveringskosten",
        ],
      },
      variabel: {
        velden: {},
        uitleg: nt("Terugleverkosten in schalen of per kWh, afhankelijk van je contract; de tabel en de terugleververgoeding na salderen staan in je contract."),
        bronnen: ["https://vandebron.nl/blog/nieuwe-schaalverdeling-vaste-terugleveringskosten"],
      },
    },
    gas: {
      vast: {
        velden: {},
        uitleg: nt("Gas vast; de prijs per m³ staat in je contract."),
        bronnen: ["https://vandebron.nl"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel; de prijs per m³ staat in je contract."),
        bronnen: ["https://vandebron.nl"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Inkoopvergoeding niet ingevuld: Keuze.nl € 0,02208 (18-10-2026) tegen Energievergelijk.nl € 0,0257 (30-06-2026), allebei zonder btw-vermelding."),
      nt("Verkoopvergoeding (€ 0,01361) alleen van Keuze.nl, zonder btw-vermelding."),
      nt("Vaste kosten: alleen € 14 per maand voor stroom en gas samen gevonden."),
      nt("Terugleverkosten bij vast en variabel: de schalen bij Overstappen.nl zijn van mei 2025, Keuze.nl noemt 15,0 cent en ook € 0,053 per kWh."),
    ],
  },
  {
    id: "vattenfall",
    naam: "Vattenfall",
    website: "https://www.vattenfall.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: { feed_in_costs: 0, feed_in_vat: false },
        namen: { opslag: nt("Inkoopvergoeding"), vergoeding: nt("Verkoopvergoeding") },
        uitleg: nt("Vattenfall FlexPrijs: de beursprijs per uur (het gemiddelde van de vier EPEX-kwartierprijzen) plus inkoopvergoeding, daarbovenop energiebelasting en btw. Vattenfall publiceert de inkoopvergoeding niet openbaar; volgens Keuze.nl € 0,0255 per kWh en vaste kosten € 7,95 per maand, zonder btw-vermelding."),
        terug: nt("Je krijgt de beursprijs van het uur zonder btw. De verkoopvergoeding (met btw, over elke teruggeleverde kWh) is volgens Vattenfall nu € 0. Tot 2027 gesaldeerd op volume; een negatief netto overschot wordt € 0. Van 2027 tot 2030 per uur minstens 50% van beursprijs plus inkoopvergoeding. Geen vaste terugleverkosten."),
        bronnen: [
          "https://www.vattenfall.nl/energie/dynamisch-energiecontract/",
          "https://www.vattenfall.nl/energie/dynamisch-energiecontract/zonnepanelen/",
          "https://www.vattenfall.nl/media/_0vattenfall/voorwaarden/productvoorwaarden/2026_02_19/6373_005-pvw-flexprijsstroom.pdf",
          "https://www.keuze.nl/energie/energieleveranciers/vattenfall/dynamisch-contract",
        ],
      },
      vast: {
        velden: { feed_in_costs_mode: "schalen", feed_in_scales_until: "2027-01-01" },
        uitleg: nt("Tot 2027 vaste terugleverkosten per schaal, naar je totale teruglevering; onder 500 kWh niets. De tabel staat in je aanbod en in Mijn Vattenfall (Keuze.nl noemt 60 schalen). Vanaf 2027 terugleverkosten per kWh. De terugleververgoeding na salderen staat in je contract. Bij Groen met ZonBonus een bonus per teruggeleverde kWh, tot 10.000 kWh per jaar; het bedrag is niet gevonden."),
        bronnen: [
          "https://www.vattenfall.nl/zonnepanelen/vaste-terugleverkosten/",
          "https://www.vattenfall.nl/media/_0vattenfall/voorwaarden/productvoorwaarden/2026_08_01/6124_010-pvw-stroom.pdf",
          "https://www.vattenfall.nl/media/_0vattenfall/voorwaarden/productvoorwaarden/2026_08_01/6176_008-pvw-groen-met-zonbonus.pdf",
        ],
      },
      variabel: {
        velden: { feed_in_costs_mode: "schalen", feed_in_scales_until: "2027-01-01" },
        uitleg: nt("Tot 2027 vaste terugleverkosten per schaal, naar je totale teruglevering; onder 500 kWh niets. De tabel staat in je aanbod en in Mijn Vattenfall. Vanaf 2027 terugleverkosten per kWh. De terugleververgoeding na salderen staat in je contract."),
        bronnen: [
          "https://www.vattenfall.nl/zonnepanelen/vaste-terugleverkosten/",
          "https://www.vattenfall.nl/media/_0vattenfall/voorwaarden/productvoorwaarden/2026_08_01/6124_010-pvw-stroom.pdf",
        ],
      },
    },
    gas: {
      vast: {
        velden: {},
        uitleg: nt("Gas vast; de prijs per m³ staat in je contract."),
        bronnen: ["https://www.vattenfall.nl/voorwaarden/"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel; de prijs per m³ staat in je contract."),
        bronnen: ["https://www.vattenfall.nl/voorwaarden/"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Inkoopvergoeding (€ 0,0255) en vaste kosten (€ 7,95 per maand) alleen van Keuze.nl, zonder btw-vermelding; daarom niet ingevuld."),
      nt("Verkoopvergoeding niet ingevuld: Vattenfall zegt nu € 0, de leverancierspagina van Keuze.nl noemt € 0,02549."),
      nt("De schalen komen alleen van vergelijkers; volgens Overstappen.nl kan Vattenfall de bedragen per week wijzigen."),
      nt("Terugleverkosten per kWh vanaf 2027, de terugleververgoeding bij vast en variabel, en het bedrag van de ZonBonus: niet gevonden."),
    ],
  },
  {
    id: "ventum",
    naam: "Ventum",
    website: "https://ventum.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: {},
        uitleg: nt("Ventum: de kale marktprijs per uur, met daarop energiebelasting en btw. Een opslag per kWh en de vaste kosten staan alleen in je persoonlijke aanbod."),
        terug: nt("Met zonnepanelen reken je bij dynamisch je teruglevering per uur af. Tegen welke prijs, en hoe salderen werkt, legt Ventum volgens de site later uit."),
        bronnen: ["https://ventum.nl/dynamisch-energiecontract/", "https://ventum.nl/aanbod/"],
      },
      vast: {
        velden: { feed_in_costs: 0 },
        uitleg: nt("Alleen het wettelijke modelcontract: terugleverkosten € 0,00 per kWh met btw, en een teruglevertarief van € 0,05 per kWh voor wat na salderen overblijft. Vastrecht € 145,20 per jaar met btw."),
        bronnen: ["https://ventum.nl/modelcontract/"],
      },
      variabel: {
        velden: { feed_in_costs: 0 },
        uitleg: nt("Alleen het wettelijke modelcontract: terugleverkosten € 0,00 per kWh met btw, en een teruglevertarief van € 0,05 per kWh voor wat na salderen overblijft. Vastrecht € 72,60 per jaar met btw; tarieven kunnen op 1 januari, 1 april, 1 juli en 1 oktober wijzigen."),
        bronnen: ["https://ventum.nl/modelcontract/"],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gas dynamisch, prijs per dag."),
        bronnen: ["https://ventum.nl/dynamisch-energiecontract/"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Opslag per kWh en vaste leveringskosten van het dynamische contract staan alleen in het persoonlijke aanbod."),
      nt("Teruglevering bij dynamisch: niet tegen welke prijs, en niets over terugleverkosten, negatieve prijzen of salderen."),
      nt("Teruglevertarief van het modelcontract (€ 0,05): bij de regel zelf staat niet of het met of zonder btw is; daarom niet ingevuld."),
      nt("Of 'per uur' het uurgemiddelde van de kwartierprijzen is, staat er niet."),
    ],
  },
  {
    id: "zonopnaam-energie",
    naam: "Zonopnaam Energie (voorheen Vrijopnaam)",
    website: "https://www.zonopnaam.nl",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "hour",
        velden: { supplier_markup: 0.0165 },
        namen: { opslag: nt("Inkoopvergoeding") },
        uitleg: nt("Zonopnaam Energie (tot 22 juni 2026 Vrijopnaam): (EPEX-uurprijs + inkoopvergoeding + energiebelasting) × 1,21. Inkoopvergoeding € 0,0165 zonder btw (tariefblad oktober 2026). Vaste leveringskosten € 0,263 per dag met btw."),
        terug: nt("Met eigen zonnepanelen kan dynamisch (nog) niet: levert je aansluiting terug, dan wordt het contract omgezet naar variabel."),
        bronnen: [
          "https://www.zonopnaam.nl/files/pdf/ZON_Tarievenblad_2026M10_Dynamisch_V01.pdf",
          "https://www.zonopnaam.nl/files/pdf/V_0626-Contractvoorwaarden-Zonopnaam-Energie-stroom-en-gas-dynamisch-tarief.pdf",
          "https://www.zonopnaam.nl/dynamisch-contract",
        ],
      },
      vast: {
        velden: {},
        uitleg: nt("Terugleverkosten per kWh over alle teruglevering, met btw, en een terugleververgoeding per kWh; bij een vast contract geldt het tariefblad van de dag van aanmelden (oktober 2026: allebei € 0,10). Tot 2027 krijg je de vergoeding alleen voor wat na salderen overblijft."),
        bronnen: [
          "https://www.zonopnaam.nl/files/pdf/ZON_Tarievenblad_2026M10_Vast_V02.pdf",
          "https://www.zonopnaam.nl/files/pdf/ZON_Tarievenblad_2026M10_VoordeelVast_V02.pdf",
          "https://www.zonopnaam.nl/terugleverkosten",
        ],
      },
      variabel: {
        velden: {},
        uitleg: nt("Variabel energiezuinig (tariefblad oktober 2026): terugleverkosten € 0,10 per kWh met btw over alle teruglevering, en een terugleververgoeding van € 0,10 per kWh voor wat na salderen overblijft."),
        bronnen: [
          "https://www.zonopnaam.nl/files/pdf/ZON_Tarievenblad_2026M10_energiezuinig-Variabel_V03.pdf",
          "https://www.zonopnaam.nl/terugleverkosten",
        ],
      },
    },
    gas: {
      dynamisch: {
        velden: {},
        uitleg: nt("Gasprijs per dag (TTF day-ahead, bepaald om 06:00) + inkoopvergoeding € 0,066 per m³ zonder btw + energiebelasting, met 21% btw."),
        bronnen: ["https://www.zonopnaam.nl/files/pdf/ZON_Tarievenblad_2026M10_Dynamisch_V01.pdf"],
      },
      vast: {
        velden: {},
        uitleg: nt("Gas vast; de prijs staat op het tariefblad."),
        bronnen: ["https://www.zonopnaam.nl/tarieven"],
      },
      variabel: {
        velden: {},
        uitleg: nt("Gas variabel; de prijs staat op het tariefblad."),
        bronnen: ["https://www.zonopnaam.nl/tarieven"],
      },
    },
    ha: {
      stroom: [],
      gas: [],
    },
    onzeker: [
      nt("Terugleverkosten en vergoeding bij variabel niet ingevuld: het variabele tariefblad van oktober 2026 zegt € 0,10 en € 0,10, het dynamische tariefblad noemt voor hetzelfde variabele contract nog € 0,152 en € 0,134."),
      nt("Bij vast hangen de bedragen af van de maand van aanmelden (augustus € 0,089, september € 0,078, oktober € 0,10)."),
      nt("Of de terugleververgoeding met of zonder btw is, staat op geen tariefblad."),
      nt("Hoe Zonopnaam van vier kwartierprijzen één uurprijs maakt, staat er niet."),
      nt("De HACS-integratie van groninge01 geeft de prijs die je in de app hebt gekozen (all-in, Marktprijs+ of Marktprijs) en heeft geen vaste entiteitnaam; daarom geen sensor."),
    ],
  },
];
