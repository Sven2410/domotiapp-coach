/**
 * Het Engels van de leverancierscatalogus (v0.140.0, stap 3); zie docs/taal.md.
 *
 * De tekst die Contract uit leveranciers.js en leveranciers-data.js toont, per leverancier: de
 * woorden voor de opbouw (`namen`), de uitleg (`uitleg`), de teruglevering (`terug`) en wat er
 * onzeker bleef (`onzeker`); `voorstel` vertaalt ze. Namen van leveranciers, producten (zoals
 * Zonnebonus en Dynamische Stroom) en sites blijven zoals ze zijn. De drie soorten (SOORTEN)
 * staan in contract.js, want het zijn de knoppen van dat scherm.
 */
export const LEVERANCIERS = {
  // Zonneplan
  "Inkoopvergoeding": "Purchasing fee",
  "Inkoopvergoeding, terug": "Purchasing fee, back",
  "Zonnebonus": "Zonnebonus",
  "Je betaalt per kWh (marktprijs per kwartier + energiebelasting) × 1,21, plus € 0,02 inkoopvergoeding met btw. Vaste leveringskosten € 6,25 per maand.":
    "Per kWh you pay (market price per quarter hour + energy tax) × 1.21, plus a € 0.02 purchasing fee including VAT. Fixed supply costs € 6.25 per month.",
  "Je krijgt de marktprijs met btw plus de € 0,02 inkoopvergoeding terug, zonder energiebelasting. Overdag, van zonsopkomst tot zonsondergang en als marktprijs + € 0,02 positief is, komt er 10% Zonnebonus bij over (marktprijs + € 0,02), tot 7.500 kWh per jaar. Niet over teruglevering uit de thuisbatterij van Zonneplan. Geen terugleverkosten.":
    "You get the market price including VAT plus the € 0.02 purchasing fee back, without energy tax. During the day, from sunrise to sunset and when the market price + € 0.02 is positive, a 10% Zonnebonus on (market price + € 0.02) is added, up to 7,500 kWh per year. Not on export from the Zonneplan home battery. No export costs.",
  "Of de vaste leveringskosten van € 6,25 per maand met of zonder btw zijn, zeggen alleen vergelijkers.":
    "Only comparison sites say whether the fixed supply costs of € 6.25 per month include VAT.",

  // ANWB Energie
  "Inkoopkosten": "Purchasing costs",
  "ANWB: de prijs per kWh bestaat uit de kale energieprijs van het uur, de energiebelasting en € 0,018 inkoopkosten. Vaste leveringskosten € 8,50 per maand.":
    "ANWB: the price per kWh is made up of the bare energy price of the hour, the energy tax and € 0.018 purchasing costs. Fixed supply costs € 8.50 per month.",
  "Je krijgt de kale energieprijs van het uur, zonder terugleverkosten. Tot 2027 krijg je over het deel tot je jaarverbruik de all-in prijs terug (salderen). Bij een negatieve prijs betaal je voor teruglevering.":
    "You get the bare energy price of the hour, without export costs. Until 2027 you get the all-in price back on the part up to your annual consumption (net metering). With a negative price you pay for export.",
  "Gasprijs per dag: kale prijs, energiebelasting en inkoopkosten, sinds 1 september 2026 € 0,0768 per m³ (ANWB zet '(incl. btw)' achter die zin).":
    "Gas price per day: bare price, energy tax and purchasing costs, since 1 September 2026 € 0.0768 per m³ (ANWB puts '(incl. btw)', including VAT, after that sentence).",
  "Inkoopkosten niet ingevuld: ANWB schrijft € 0,018 met '(incl. btw)' dubbelzinnig achter de zin over gas, Gaslicht.com rekent € 0,0218 met btw. De prijs-API van ANWB past het best bij € 0,018 met btw, maar rondt af op hele centen.":
    "Purchasing costs not filled in: ANWB writes € 0.018 with an ambiguous '(incl. btw)', including VAT, after the sentence about gas, and Gaslicht.com uses € 0.0218 including VAT. The ANWB price API fits € 0.018 including VAT best, but rounds to whole cents.",
  "Vaste leveringskosten € 8,50: ANWB zegt niet of dat met of zonder btw is.":
    "Fixed supply costs € 8.50: ANWB does not say whether that includes VAT.",
  "Of ANWB het overschot boven je jaarverbruik met of zonder btw vergoedt, staat er niet.":
    "It does not say whether ANWB pays for the surplus above your annual consumption with or without VAT.",
  "De site en de prijs-API zeggen per uur; één vergelijker noemt kwartier.":
    "The site and the price API say per hour; one comparison site says per quarter hour.",
  "De HACS-integratie van vinnie1234 geeft de prijs standaard in cent per kWh (euro is een optie).":
    "The HACS integration by vinnie1234 gives the price in cents per kWh by default (euros are an option).",

  // Budget Thuis
  "Budget Thuis: (beursprijs + inkoopvergoeding + energiebelasting) + btw, per uur. De inkoopvergoeding publiceert Budget niet; volgens Gaslicht.com € 0,0168 met btw, en vaste leveringskosten € 6,49 per maand met btw.":
    "Budget Thuis: (exchange price + purchasing fee + energy tax) + VAT, per hour. Budget does not publish the purchasing fee; according to Gaslicht.com it is € 0.0168 including VAT, with fixed supply costs of € 6.49 per month including VAT.",
  "Je krijgt de beursprijs van het uur, zonder terugleverkosten. Tot 2027 saldeert Budget tegen de leveringsprijs van dat uur; over een jaaroverschot alleen de beursprijs. Vanaf 2027 een ZonneBonus van 30% over de beursprijs (hooguit € 0,06 per kWh) binnen een tijdvak per maand, over de eerste 5.000 kWh; die staat niet in de velden omdat hij pas dan ingaat.":
    "You get the exchange price of the hour, without export costs. Until 2027 Budget nets against the supply price of that hour; on an annual surplus only the exchange price. From 2027 a ZonneBonus of 30% on the exchange price (at most € 0.06 per kWh) within one time window per month, on the first 5,000 kWh; it is not in the fields because it only starts then.",
  "Terugleverkosten in 26 schalen: een vast bedrag per dag naar je teruglevering (nooit boven je jaarverbruik), van € 0 tot € 7,73 per dag met btw; de tabel staat op de pagina terugleverkosten. Vanaf 2027 een bedrag per kWh. De terugleververgoeding boven salderen staat in het tariefblad bij je contract en is niet openbaar.":
    "Export costs in 26 bands: a fixed amount per day based on your export (never above your annual consumption), from € 0 to € 7.73 per day including VAT; the table is on the export costs page. From 2027 an amount per kWh. The export tariff above net metering is in the tariff sheet with your contract and is not public.",
  "Terugleverkosten in dezelfde 26 schalen als bij vast, per dag naar je teruglevering. Vanaf 2027 een bedrag per kWh. De terugleververgoeding boven salderen wordt maandelijks herzien en staat in het tariefblad bij je contract.":
    "Export costs in the same 26 bands as for fixed, per day based on your export. From 2027 an amount per kWh. The export tariff above net metering is reviewed monthly and is in the tariff sheet with your contract.",
  "Gas dynamisch: (beursprijs + inkoopvergoeding + energiebelasting) + btw.":
    "Dynamic gas: (exchange price + purchasing fee + energy tax) + VAT.",
  "Gas vast, ook als Dynamisch + Gas Vast: dynamische stroom met een jaar vast gas.":
    "Fixed gas, also as Dynamisch + Gas Vast: dynamic electricity with gas fixed for a year.",
  "Gas variabel; de prijs per m³ staat in je contract.":
    "Variable gas; the price per m³ is in your contract.",
  "De inkoopvergoeding (€ 0,0168 met btw) en de vaste leveringskosten (€ 6,49 per maand) komen alleen van Gaslicht.com (14-10-2026); Budget publiceert ze niet.":
    "The purchasing fee (€ 0.0168 including VAT) and the fixed supply costs (€ 6.49 per month) only come from Gaslicht.com (14-10-2026); Budget does not publish them.",
  "Negatieve prijzen: de productvoorwaarden zeggen dat de terugleververgoeding sinds 2026 niet negatief mag zijn, de pagina over salderen zegt dat je dan betaalt.":
    "Negative prices: the product terms say the export tariff may not be negative since 2026, the page about net metering says you pay in that case.",
  "Of de beursprijs bij teruglevering met of zonder btw wordt vergoed, staat er niet.":
    "It does not say whether the exchange price for export is paid with or without VAT.",
  "Geen sensor: de HACS-integraties rekenen de all-in prijs zelf uit met een inkoopvergoeding die je instelt, of hebben geen vaste entiteitnaam.":
    "No sensor: the HACS integrations work out the all-in price themselves with a purchasing fee you set, or have no fixed entity name.",

  // Clean Energy
  "Terugleverkosten volgens de productvoorwaarden € 0,14 per kWh met btw, over elke teruggeleverde kWh in 2026; vanaf 2027 de terugleververgoeding min € 0,01. Boven salderen € 0,15 per kWh met btw. Vaste leveringskosten € 0,24863 per dag met btw.":
    "According to the product terms, export costs are € 0.14 per kWh including VAT, on every exported kWh in 2026; from 2027 the export tariff minus € 0.01. Above net metering € 0.15 per kWh including VAT. Fixed supply costs € 0.24863 per day including VAT.",
  "Terugleverkosten volgens de productvoorwaarden € 0,14 per kWh met btw, over elke teruggeleverde kWh in 2026; vanaf 2027 de terugleververgoeding min € 0,01. Boven salderen € 0,15 per kWh met btw.":
    "According to the product terms, export costs are € 0.14 per kWh including VAT, on every exported kWh in 2026; from 2027 the export tariff minus € 0.01. Above net metering € 0.15 per kWh including VAT.",
  "Gas vast, 1 tot 5 jaar; de prijs per m³ staat in je contract.":
    "Fixed gas, 1 to 5 years; the price per m³ is in your contract.",
  "Terugleverkosten niet ingevuld: de productvoorwaarden en de rekenvoorbeelden zeggen € 0,14 per kWh, één zin op de pagina terugleveren zegt € 0,15.":
    "Export costs not filled in: the product terms and the worked examples say € 0.14 per kWh, one sentence on the export page says € 0.15.",
  "Geen dynamisch contract gevonden.": "No dynamic contract found.",

  // Coolblue Energie
  "Inkoopvergoeding, bij teruglevering": "Purchasing fee, on export",
  "Coolblue Energie levert op de vergunning van ServiceHouse. De kwartierprijs is de EPEX-beursprijs plus inkoopvergoeding, energiebelasting en btw. Het bedrag staat in je persoonlijke aanbod; volgens Keuze.nl € 0,02 per kWh, zonder dat duidelijk is of dat met of zonder btw is.":
    "Coolblue Energie supplies under the licence of ServiceHouse. The quarter-hour price is the EPEX exchange price plus purchasing fee, energy tax and VAT. The amount is in your personal offer; according to Keuze.nl € 0.02 per kWh, without it being clear whether that includes VAT.",
  "Je krijgt de actuele kwartierprijs min de inkoopvergoeding; aparte terugleverkosten rekent Coolblue niet. Tot 2027 saldeert Coolblue per telwerk op jaarbasis.":
    "You get the current quarter-hour price minus the purchasing fee; Coolblue charges no separate export costs. Until 2027 Coolblue nets per register on an annual basis.",
  "Terugleverkosten per kWh over alle teruglevering; het bedrag staat in je contract, volgens Keuze.nl € 0,115 in 2026. Over de terugleververgoeding boven salderen wordt geen btw gerekend; volgens Keuze.nl € 0,06017 per kWh.":
    "Export costs per kWh on all export; the amount is in your contract, according to Keuze.nl € 0.115 in 2026. No VAT is charged on the export tariff above net metering; according to Keuze.nl € 0.06017 per kWh.",
  "Gas alleen vast, ook naast Dynamische Stroom; de prijs per m³ staat in je contract.":
    "Gas only fixed, also alongside Dynamische Stroom; the price per m³ is in your contract.",
  "Inkoopvergoeding (€ 0,02) alleen van vergelijkers, zonder btw-vermelding; daarom niet ingevuld. De vaste leveringskosten van Dynamische Stroom zijn niet gevonden.":
    "Purchasing fee (€ 0.02) only from comparison sites, without mention of VAT; so not filled in. The fixed supply costs of Dynamische Stroom were not found.",
  "Hoeveel er bij teruglevering afgaat hangt aan diezelfde inkoopvergoeding; wanneer de regel 'Teruggave inkoopvergoeding' uit het aanbod geldt, legt Coolblue niet uit.":
    "How much is deducted on export depends on that same purchasing fee; Coolblue does not explain when the line 'Teruggave inkoopvergoeding' (refund of the purchasing fee) in the offer applies.",
  "Wat er bij een negatieve kwartierprijs met teruglevering gebeurt: niet gevonden.":
    "What happens with export at a negative quarter-hour price: not found.",
  "De bedragen bij vast komen alleen van Keuze.nl.": "The amounts for fixed only come from Keuze.nl.",
  "Geen sensor: de HACS-integratie rekent de all-in prijs uit met een inkoopvergoeding die je zelf instelt.":
    "No sensor: the HACS integration works out the all-in price with a purchasing fee you set yourself.",

  // DELTA Energie
  "Verkoopvergoeding": "Selling fee",
  "DELTA: totale prijs = beursprijs (het uurgemiddelde van de kwartierprijzen) + inkoopvergoeding + energiebelasting, alles met 21% btw. Inkoopvergoeding € 0,012548 met btw (prijsblad 23 april 2026). Vaste leveringskosten € 8,49 per maand met btw.":
    "DELTA: total price = exchange price (the hourly average of the quarter-hour prices) + purchasing fee + energy tax, all with 21% VAT. Purchasing fee € 0.012548 including VAT (price sheet 23 April 2026). Fixed supply costs € 8.49 per month including VAT.",
  "Je krijgt de beursprijs van het uur; wat na saldering netto teruggaat is btw-vrij. Per teruggeleverde kWh rekent DELTA een verkoopvergoeding met btw, ook als die gesaldeerd wordt; het bedrag staat alleen in MijnDELTA en kan nul zijn. Van 2027 tot 2030 minstens 50% van beursprijs plus inkoopvergoeding.":
    "You get the exchange price of the hour; what goes back net after net metering is VAT-free. Per exported kWh DELTA charges a selling fee including VAT, also when it is netted; the amount is only shown in MijnDELTA and can be zero. From 2027 to 2030 at least 50% of the exchange price plus purchasing fee.",
  "Terugleverkosten in 45 schalen, een bedrag per jaar naar je teruglevering (tabel 'vanaf 12 juni 2025'). Boven salderen € 0,165 per kWh, btw-vrij. Vanaf 2027 per kWh: bij 3 jaar vast € 0,06743 kosten met btw en € 0,06993 vergoeding, bij 1 jaar vast € 0,07703 en € 0,07953.":
    "Export costs in 45 bands, an amount per year based on your export (table 'from 12 June 2025'). Above net metering € 0.165 per kWh, VAT-free. From 2027 per kWh: with 3 years fixed € 0.06743 costs including VAT and € 0.06993 tariff, with 1 year fixed € 0.07703 and € 0.07953.",
  "Terugleverkosten in dezelfde 45 schalen als bij vast. Boven salderen € 0,165 per kWh, btw-vrij (prijsblad 1 april 2026). Het bedrag per kWh vanaf 2027 komt bij de variabele prijzen van dan.":
    "Export costs in the same 45 bands as for fixed. Above net metering € 0.165 per kWh, VAT-free (price sheet 1 April 2026). The amount per kWh from 2027 comes with the variable prices of that time.",
  "DELTA Gas Dynamisch, in dezelfde productvoorwaarden en op hetzelfde prijsblad als de dynamische stroom.":
    "DELTA Gas Dynamisch, in the same product terms and on the same price sheet as the dynamic electricity.",
  "DELTA MixGroen Gas vast; de prijs per m³ staat op het prijsblad met de vaste prijzen.":
    "DELTA MixGroen Gas vast; the price per m³ is on the price sheet with the fixed prices.",
  "Hoogte van de verkoopvergoeding bij dynamisch: alleen in MijnDELTA, en volgens de voorwaarden kan hij ook nul zijn.":
    "Size of the selling fee with dynamic: only in MijnDELTA, and according to the terms it can also be zero.",
  "De site linkt op 18-10-2026 nog naar het dynamische prijsblad van 23 april 2026, en naar het variabele van 1 april 2026; een nieuwer blad is niet gevonden.":
    "On 18-10-2026 the site still links to the dynamic price sheet of 23 April 2026, and to the variable one of 1 April 2026; no newer sheet was found.",
  "Negatieve prijzen: de productpagina zegt dat je dan betaalt voor terugleveren, de voorwaarden zetten het netto overschot en het maandtotaal op minimaal € 0.":
    "Negative prices: the product page says you then pay for export, the terms set the net surplus and the monthly total to at least € 0.",

  // Dynamiq
  "Dynamiq Energy Services levert op de vergunning van Kikker Energie. Je betaalt de inkoopprijs per uur, plus vaste kosten en belastingen. De site zegt 'geen opslag', de FAQ noemt 'meestal een kleine marge per kWh'; er zijn geen bedragen gepubliceerd.":
    "Dynamiq Energy Services supplies under the licence of Kikker Energie. You pay the purchase price per hour, plus fixed costs and taxes. The site says 'no markup', the FAQ mentions 'usually a small margin per kWh'; no amounts are published.",
  "Alleen 'een eerlijke terugleververgoeding', zonder bedragen.":
    "Only 'a fair export tariff', without amounts.",
  "Gas dynamisch, inkoopprijs per dag.": "Dynamic gas, purchase price per day.",
  "Geen tarieven gepubliceerd; de site spreekt zichzelf tegen over een opslag.":
    "No tariffs published; the site contradicts itself about a markup.",
  "Of het merk werkelijk nieuwe klanten aanneemt.": "Whether the brand actually takes on new customers.",
  "De ACM legde Kikker Energie in 2026 een bindende aanwijzing op.":
    "In 2026 the ACM imposed a binding instruction on Kikker Energie.",

  // easyEnergy
  "easyEnergy: leveringstarief = kwartiertarief EPEX + inkoopvergoeding + 21% btw, plus energiebelasting. Inkoopvergoeding € 0,02178 per kWh met btw (€ 0,018 zonder). Lidmaatschap € 7 per maand voor stroom.":
    "easyEnergy: supply rate = EPEX quarter-hour rate + purchasing fee + 21% VAT, plus energy tax. Purchasing fee € 0.02178 per kWh including VAT (€ 0.018 excluding). Membership € 7 per month for electricity.",
  "Je krijgt de beursprijs van het kwartier, zonder aparte terugleverkosten. De inkoopvergoeding rekent easyEnergy alleen over het maandsaldo van verbruik min teruglevering. Tot 2027 volledig gesaldeerd, de energiebelasting op jaarbasis.":
    "You get the exchange price of the quarter hour, without separate export costs. easyEnergy only charges the purchasing fee on the monthly balance of consumption minus export. Fully netted until 2027, the energy tax on an annual basis.",
  "Alleen het wettelijke modelcontract: teruglevertarief € 0,00 per kWh, en over teruglevering boven je verbruik geen energiebelasting. Terugleverkosten noemt het tarievenblad niet.":
    "Only the statutory model contract: export rate € 0.00 per kWh, and no energy tax on export above your consumption. The tariff sheet does not mention export costs.",
  "Gas: dagtarief LEBA + inkoopvergoeding + 21% btw, plus energiebelasting. Lidmaatschap € 7 per maand voor gas.":
    "Gas: LEBA daily rate + purchasing fee + 21% VAT, plus energy tax. Membership € 7 per month for gas.",
  "Lidmaatschap € 7 per maand: of dat met of zonder btw is, staat er niet letterlijk.":
    "Membership € 7 per month: it does not literally say whether that includes VAT.",
  "Of de inkoopvergoeding in een maand met netto teruglevering van de vergoeding afgaat: een blog zegt van wel, de pagina terugleveren van niet. Daarom geen vergoeding ingevuld.":
    "Whether the purchasing fee is deducted from the tariff in a month with net export: a blog says yes, the export page says no. So no tariff filled in.",
  "Of teruglevering de beursprijs met of zonder btw krijgt, zegt easyEnergy niet; de HA-bibliotheek gebruikt de prijs met btw.":
    "easyEnergy does not say whether export gets the exchange price with or without VAT; the Home Assistant library uses the price including VAT.",
  "De core-integratie easyEnergy geeft de kale prijs met btw, zonder energiebelasting en inkoopvergoeding; de all-in prijs alleen via een actie, niet als sensor.":
    "The easyEnergy core integration gives the bare price including VAT, without energy tax and purchasing fee; the all-in price only through an action, not as a sensor.",

  // Eneco
  "Eneco: (EPEX-uurprijs + inkoopvergoeding + energiebelasting) × 1,21. Inkoopvergoeding € 0,01898 zonder btw (€ 0,02297 met), uit de prijs-API achter de tarievenpagina van Eneco. De vaste leveringskosten staan niet op de site.":
    "Eneco: (EPEX hourly price + purchasing fee + energy tax) × 1.21. Purchasing fee € 0.01898 excluding VAT (€ 0.02297 including), from the price API behind the Eneco tariff page. The fixed supply costs are not on the site.",
  "Tot 2027 krijg je tot je jaarverbruik per uur hetzelfde tarief terug als je betaalt, inclusief inkoopvergoeding. Over een jaaroverschot de marktprijs van het uur min een verkoopvergoeding, zonder btw; dat bedrag publiceert Eneco niet. Geen terugleverkosten. Bij een negatieve uurprijs is de vergoeding ook negatief.":
    "Until 2027 you get the same rate back per hour as you pay, including the purchasing fee, up to your annual consumption. On an annual surplus the market price of the hour minus a selling fee, without VAT; Eneco does not publish that amount. No export costs. With a negative hourly price the tariff is negative too.",
  "Terugleverkosten sinds 1 juni 2024 een vast bedrag per kWh over alle teruglevering; het bedrag staat in je contract. De terugleververgoeding boven salderen staat ook in je contract, zonder btw.":
    "Since 1 June 2024 export costs are a fixed amount per kWh on all export; the amount is in your contract. The export tariff above net metering is also in your contract, excluding VAT.",
  "Terugleverkosten een vast bedrag per kWh over alle teruglevering; het bedrag staat in je contract. De terugleververgoeding boven salderen staat ook in je contract, zonder btw.":
    "Export costs are a fixed amount per kWh on all export; the amount is in your contract. The export tariff above net metering is also in your contract, excluding VAT.",
  "Gas vast, ook naast Eneco Dynamisch: dynamische stroom met een jaar vast gas.":
    "Fixed gas, also alongside Eneco Dynamisch: dynamic electricity with gas fixed for a year.",
  "Verkoopvergoeding bij dynamisch: Eneco publiceert hem niet; vergelijkers noemen € 0,0292 (Keuze.nl) en € 0,0241 met btw.":
    "Selling fee with dynamic: Eneco does not publish it; comparison sites mention € 0.0292 (Keuze.nl) and € 0.0241 including VAT.",
  "Vaste leveringskosten bij dynamisch alleen van vergelijkers, en die verschillen: € 8,99 met btw (Gaslicht.com) tegen € 7 (Keuze.nl).":
    "Fixed supply costs with dynamic only from comparison sites, and they differ: € 8.99 including VAT (Gaslicht.com) against € 7 (Keuze.nl).",
  "De HACS-integratie Dynamic Energy Prices haalt onder 'eneco' de prijzen van EnergyZero op, niet die van Eneco.":
    "The HACS integration Dynamic Energy Prices fetches the EnergyZero prices under 'eneco', not those of Eneco.",

  // Energie VanOns
  "Opslag levering": "Supply markup",
  "Afslag teruglevering": "Export deduction",
  "Energie VanOns: uurprijs EPEX Day Ahead (het gemiddelde van de vier kwartieren) + opslag levering, vermeerderd met energiebelasting en btw. De opslag staat niet op de site; vergelijkers noemen € 0,029 per kWh. Vaste leveringskosten € 6,99 per maand.":
    "Energie VanOns: EPEX Day Ahead hourly price (the average of the four quarter hours) + supply markup, plus energy tax and VAT. The markup is not on the site; comparison sites mention € 0.029 per kWh. Fixed supply costs € 6.99 per month.",
  "Je krijgt de uurprijs zonder btw, min een afslag teruglevering per kWh; dat bedrag is niet gepubliceerd. Geen vaste terugleverkosten. Levering en teruglevering worden per uur gesaldeerd, de energiebelasting op jaarbasis tot je jaarverbruik.":
    "You get the hourly price excluding VAT, minus an export deduction per kWh; that amount is not published. No fixed export costs. Supply and export are netted per hour, the energy tax on an annual basis up to your annual consumption.",
  "Terugleverkosten per jaar in schalen: tot 999 kWh € 0, vanaf 1.000 kWh € 166,31 en per 500 kWh daarboven € 66,55 extra, met btw. Een vast contract uit 2026 betaalt per kWh (rekenvoorbeeld 3 jaar vast: € 0,07 met btw). De terugleververgoeding boven salderen staat per looptijd op de tarievenpagina.":
    "Export costs per year in bands: up to 999 kWh € 0, from 1,000 kWh € 166.31 and € 66.55 extra per 500 kWh above that, including VAT. A fixed contract from 2026 pays per kWh (worked example 3 years fixed: € 0.07 including VAT). The export tariff above net metering is on the tariff page per term.",
  "Terugleverkosten in dezelfde schalen als bij vast. Terugleververgoeding boven salderen bij variabel € 0,053981 per kWh met btw (tarievenblad); het coöperatieve contract heeft een eigen bedrag.":
    "Export costs in the same bands as for fixed. Export tariff above net metering with variable € 0.053981 per kWh including VAT (tariff sheet); the cooperative contract has its own amount.",
  "Opslag levering (€ 0,029) alleen van vergelijkers, en niet eenduidig met of zonder btw; daarom niet ingevuld.":
    "Supply markup (€ 0.029) only from comparison sites, and not clearly with or without VAT; so not filled in.",
  "Afslag teruglevering bij dynamisch: bedrag nergens gevonden.":
    "Export deduction with dynamic: amount not found anywhere.",
  "Of de vaste leveringskosten van € 6,99 met of zonder btw zijn, staat er niet.":
    "It does not say whether the fixed supply costs of € 6.99 include VAT.",
  "Terugleververgoeding bij vast en variabel verschilt per product; daarom niet ingevuld. De bedragen voor 1 en 3 jaar vast op de tarievenpagina lijken op die van om | nieuwe energie (de fusiepartner) en zijn daarom niet overgenomen.":
    "The export tariff with fixed and variable differs per product; so not filled in. The amounts for 1 and 3 years fixed on the tariff page look like those of om | nieuwe energie (the merger partner) and have therefore not been copied.",
  "De schalen boven 1.999 kWh volgen uit de regel van € 66,55 per 500 kWh; een maximum is niet gevonden.":
    "The bands above 1,999 kWh follow from the rule of € 66.55 per 500 kWh; no maximum was found.",

  // Energiebesteding
  "Opslag inkoopkosten": "Purchasing costs markup",
  "Energiebesteding (gericht op senioren) werkt met Hezelaer Energy, waarmee je het contract sluit. Dynamisch: ieder uur de marktprijs plus een opslag inkoopkosten; het bedrag is niet gepubliceerd.":
    "Energiebesteding (aimed at older people) works with Hezelaer Energy, with whom you sign the contract. Dynamic: the market price every hour plus a purchasing costs markup; the amount is not published.",
  "Geen regeling voor teruglevering gepubliceerd; Hezelaer rekent terugleveringskosten per kWh over je hele teruglevering, het bedrag staat in je contract. Energiebesteding raadt met zonnepanelen een vast contract aan.":
    "No arrangement for export published; Hezelaer charges export costs per kWh on all your export, the amount is in your contract. With solar panels Energiebesteding recommends a fixed contract.",
  "Vast 1 tot en met 5 jaar, en ZekerVoordeel (april tot en met september dynamisch, oktober tot en met maart vast). Bij vast krijg je voor teruglevering dezelfde prijs als voor levering, min terugleverkosten (bedrag niet gepubliceerd). Vaste leveringskosten € 8,99 per product per maand met btw.":
    "Fixed for 1 up to and including 5 years, and ZekerVoordeel (dynamic from April to September, fixed from October to March). With fixed you get the same price for export as for supply, minus export costs (amount not published). Fixed supply costs € 8.99 per product per month including VAT.",
  "Variabel; de bedragen staan in je contract.": "Variable; the amounts are in your contract.",
  "Gas dynamisch, prijs per dag.": "Dynamic gas, price per day.",
  "Gas vast, 1 tot en met 5 jaar; de prijs staat in je contract.":
    "Fixed gas, 1 up to and including 5 years; the price is in your contract.",
  "Gas variabel; de prijs staat in je contract.": "Variable gas; the price is in your contract.",
  "Opslag van het dynamische contract niet gepubliceerd.": "Markup of the dynamic contract not published.",
  "Of de vaste leveringskosten van € 8,99 ook bij dynamisch gelden.":
    "Whether the fixed supply costs of € 8.99 also apply with dynamic.",
  "Hoogte van de terugleverkosten bij vast.": "Size of the export costs with fixed.",
  "Uur of kwartier: de pagina's spreken elkaar tegen.":
    "Hour or quarter hour: the pages contradict each other.",

  // Energiedirect
  "Energiedirect, een merk van Essent op hetzelfde platform: (beursprijs + inkoopvergoeding + energiebelasting) × 1,21, per uur met het gemiddelde van de vier kwartierprijzen. Inkoopvergoeding € 0,01694 zonder btw (€ 0,0205 met), uit de prijs-API van Energiedirect.":
    "Energiedirect, a brand of Essent on the same platform: (exchange price + purchasing fee + energy tax) × 1.21, per hour with the average of the four quarter-hour prices. Purchasing fee € 0.01694 excluding VAT (€ 0.0205 including), from the Energiedirect price API.",
  "Tot 2027 krijg je tot je jaarverbruik per uur hetzelfde tarief terug als je betaalt, inclusief btw, energiebelasting en inkoopvergoeding. Over een jaaroverschot de beursprijs zonder btw min € 0,01694 verkoopvergoeding; komt dat negatief uit, dan wordt het € 0. Geen terugleverkosten.":
    "Until 2027 you get the same rate back per hour as you pay, including VAT, energy tax and purchasing fee, up to your annual consumption. On an annual surplus the exchange price excluding VAT minus a € 0.01694 selling fee; if that comes out negative, it becomes € 0. No export costs.",
  "Terugleverkosten in 42 schalen: een vast bedrag per dag naar je teruglevering, met btw ('geldig per 1 januari 2025'); de tabel staat op de pagina terugleverkosten. Boven salderen € 0,15 per kWh. Vanaf 2027 per kWh in plaats van schalen.":
    "Export costs in 42 bands: a fixed amount per day based on your export, including VAT (valid from 1 January 2025); the table is on the export costs page. Above net metering € 0.15 per kWh. From 2027 per kWh instead of bands.",
  "Terugleverkosten in dezelfde 42 schalen als bij vast, per dag. Boven salderen € 0,15 per kWh. Vanaf 2027 per kWh in plaats van schalen.":
    "Export costs in the same 42 bands as for fixed, per day. Above net metering € 0.15 per kWh. From 2027 per kWh instead of bands.",
  "Gas dynamisch; de prijs-API van Energiedirect geeft de gasprijs naast die van stroom.":
    "Dynamic gas; the Energiedirect price API gives the gas price alongside the electricity price.",
  "Gas vast, 1, 2 of 3 jaar; de prijs per m³ staat in je contract.":
    "Fixed gas, 1, 2 or 3 years; the price per m³ is in your contract.",
  "Vaste leveringskosten bij dynamisch: niet gevonden.": "Fixed supply costs with dynamic: not found.",
  "De schalen voor terugleverkosten staan er als 'geldig per 1 januari 2025'; of ze in 2026 gelijk zijn, staat er niet.":
    "The bands for export costs are listed as valid from 1 January 2025; it does not say whether they are the same in 2026.",
  "Of de € 0,15 boven salderen met of zonder btw is, staat er niet; daarom niet ingevuld.":
    "It does not say whether the € 0.15 above net metering includes VAT; so not filled in.",

  // Energiek
  "Beursprijs-afslag": "Exchange price deduction",
  "Energiek: kwartierprijs EPEX Day Ahead + inkoopvergoeding, vermeerderd met energiebelasting en btw. Inkoopvergoeding € 0,0149 zonder btw (€ 0,018029 met). Vaste leveringskosten € 5,99 per maand met btw.":
    "Energiek: EPEX Day Ahead quarter-hour price + purchasing fee, plus energy tax and VAT. Purchasing fee € 0.0149 excluding VAT (€ 0.018029 including). Fixed supply costs € 5.99 per month including VAT.",
  "Je krijgt de beursprijs van het kwartier zonder btw, min de beursprijs-afslag van € 0,0149 per kWh. Geen vaste terugleverkosten. Saldering per kwartier, en op jaarbasis opnieuw voor de energiebelasting.":
    "You get the exchange price of the quarter hour excluding VAT, minus the exchange price deduction of € 0.0149 per kWh. No fixed export costs. Netting per quarter hour, and again on an annual basis for the energy tax.",
  "Terugleverkosten € 0,0605 per kWh met btw over alle teruglevering, zonder schalen, bij 1 en 3 jaar vast. Terugleververgoeding boven salderen, zonder btw: 1 jaar vast € 0,075, 3 jaar vast € 0,07.":
    "Export costs € 0.0605 per kWh including VAT on all export, without bands, with 1 and 3 years fixed. Export tariff above net metering, excluding VAT: 1 year fixed € 0.075, 3 years fixed € 0.07.",
  "Terugleverkosten € 0,069 per kWh met btw over alle teruglevering, zonder schalen. Terugleververgoeding boven salderen € 0,075 per kWh, zonder btw.":
    "Export costs € 0.069 per kWh including VAT on all export, without bands. Export tariff above net metering € 0.075 per kWh, excluding VAT.",
  "Gas vast, 1 of 3 jaar; de prijs per m³ staat in je contract.":
    "Fixed gas, 1 or 3 years; the price per m³ is in your contract.",
  "Gas variabel, ook als Energiek Duo: dynamische stroom met variabel gas.":
    "Variable gas, also as Energiek Duo: dynamic electricity with variable gas.",
  "De beursprijs-afslag, de terugleverkosten en de terugleververgoeding komen uit velden van de product-API van Energiek; wat elk veld betekent is afgeleid uit die API en de tekst op de site, niet letterlijk zo gezegd.":
    "The exchange price deduction, the export costs and the export tariff come from fields in the Energiek product API; what each field means is derived from that API and the text on the site, not stated literally.",
  "Of de beursprijs-afslag tot 2027 alleen over het netto overschot gaat of over alle teruglevering, staat er niet.":
    "It does not say whether the exchange price deduction until 2027 only applies to the net surplus or to all export.",
  "Wat er bij een negatieve prijs met teruglevering gebeurt: niet beschreven.":
    "What happens with export at a negative price: not described.",

  // EnergyZero
  "EnergyZero: kwartierprijs EPEX + inkoopvergoeding, met energiebelasting en 21% btw over alles. De prijs-API van EnergyZero gaf op 18-10-2026 € 0,01853 inkoopvergoeding zonder btw (€ 0,02242 met); de kennisbank noemt € 0,028 zonder btw voor 2026. Vaste leveringskosten volgens Gaslicht.com € 7,49 per maand met btw.":
    "EnergyZero: EPEX quarter-hour price + purchasing fee, with energy tax and 21% VAT on everything. On 18-10-2026 the EnergyZero price API gave a purchasing fee of € 0.01853 excluding VAT (€ 0.02242 including); the knowledge base mentions € 0.028 excluding VAT for 2026. Fixed supply costs according to Gaslicht.com € 7.49 per month including VAT.",
  "Je krijgt de beursprijs min een verkoopvergoeding van € 0,02242 per kWh. Geen vaste terugleverkosten. Met de gratis module ZonOptimaal tot eind 2026 € 0,01 korting op die verkoopvergoeding, en compensatie als de all-in kwartierprijs negatief is.":
    "You get the exchange price minus a selling fee of € 0.02242 per kWh. No fixed export costs. With the free ZonOptimaal module a € 0.01 discount on that selling fee until the end of 2026, and compensation when the all-in quarter-hour price is negative.",
  "Alleen het wettelijke modelcontract: een verkoopvergoeding van € 0,02242 met btw per teruggeleverde kWh, en over een jaaroverschot € 0,045 per kWh terug.":
    "Only the statutory model contract: a selling fee of € 0.02242 including VAT per exported kWh, and € 0.045 per kWh back on an annual surplus.",
  "Inkoopvergoeding niet ingevuld: de prijs-API (18-10-2026) en Gaslicht.com (prijswijziging 14-10-2026) zeggen € 0,01853 zonder btw, de kennisbank van EnergyZero € 0,028 zonder btw voor 2026, en Overstappen.nl rekent bij merken op dit platform met € 0,03388 met btw. Omdat de core-integratie de inkoopvergoeding niet bevat, kan de controle het niet nagaan.":
    "Purchasing fee not filled in: the price API (18-10-2026) and Gaslicht.com (price change 14-10-2026) say € 0.01853 excluding VAT, the EnergyZero knowledge base € 0.028 excluding VAT for 2026, and Overstappen.nl uses € 0.03388 including VAT for brands on this platform. Because the core integration does not include the purchasing fee, the check cannot verify it.",
  "Verkoopvergoeding bij dynamisch niet ingevuld: € 0,02242 staat bij het modelcontract met btw en in de ZonOptimaal-voorwaarden zonder btw-vermelding, en of hij tot 2027 over alle teruglevering of alleen over het overschot gaat, zegt EnergyZero niet eenduidig.":
    "Selling fee with dynamic not filled in: € 0.02242 is listed with VAT for the model contract and without mention of VAT in the ZonOptimaal terms, and EnergyZero does not say clearly whether until 2027 it applies to all export or only to the surplus.",
  "Vaste leveringskosten alleen van Gaslicht.com.": "Fixed supply costs only from Gaslicht.com.",
  "Hoe saldering in 2026 precies rekent: de productvoorwaarden noemen de gemiddelde kwartierprijs van het jaar, het kenniscentrum de all-in prijs.":
    "How netting works exactly in 2026: the product terms mention the average quarter-hour price of the year, the knowledge centre the all-in price.",
  "Of de € 0,045 bij het modelcontract met of zonder btw is, staat er niet; daarom niet ingevuld.":
    "It does not say whether the € 0.045 for the model contract includes VAT; so not filled in.",
  "De core-integratie EnergyZero noemt een prijs all-in, maar daar zit de inkoopvergoeding niet in; hij ligt € 0,0224 per kWh onder je echte prijs.":
    "The EnergyZero core integration calls a price all-in, but the purchasing fee is not in it; it is € 0.0224 per kWh below your real price.",

  // ENGIE
  "ENGIE: beursprijs per uur (EPEX Day Ahead) + inkoopvergoeding + energiebelasting, met btw. Inkoopvergoeding € 0,0157 zonder btw (€ 0,018997 met), uit het aanbod voor nieuwe klanten. Vaste leveringskosten € 0,2285 per dag met btw, ongeveer € 6,95 per maand.":
    "ENGIE: exchange price per hour (EPEX Day Ahead) + purchasing fee + energy tax, including VAT. Purchasing fee € 0.0157 excluding VAT (€ 0.018997 including), from the offer for new customers. Fixed supply costs € 0.2285 per day including VAT, about € 6.95 per month.",
  "Tot je jaarverbruik krijg je de marktprijs en daarbovenop de verkoopvergoeding van 1,9 cent terug, dus het leveringstarief van dat uur (salderen tot 2027). Boven je verbruik de beursprijs zonder btw min € 0,0157 verkoopvergoeding. Geen terugleverkosten; de vergoeding kan negatief zijn.":
    "Up to your annual consumption you get the market price back plus the selling fee of 1.9 cents on top, so the supply rate of that hour (net metering until 2027). Above your consumption the exchange price excluding VAT minus a € 0.0157 selling fee. No export costs; the tariff can be negative.",
  "Terugleverkosten per kWh over alle teruglevering, zonder schalen, met btw: 1 jaar vast € 0,1668, 2 jaar € 0,1464, 3 jaar € 0,1335. Terugleververgoeding boven salderen, zonder btw: € 0,1768, € 0,1564 en € 0,14345. Uit het aanbod voor nieuwe klanten op 18-10-2026.":
    "Export costs per kWh on all export, without bands, including VAT: 1 year fixed € 0.1668, 2 years € 0.1464, 3 years € 0.1335. Export tariff above net metering, excluding VAT: € 0.1768, € 0.1564 and € 0.14345. From the offer for new customers on 18-10-2026.",
  "ENGIE Open: terugleverkosten € 0,1902 per kWh met btw over alle teruglevering, zonder schalen; terugleververgoeding boven salderen € 0,2002 per kWh, zonder btw. Uit het aanbod voor nieuwe klanten op 18-10-2026.":
    "ENGIE Open: export costs € 0.1902 per kWh including VAT on all export, without bands; export tariff above net metering € 0.2002 per kWh, excluding VAT. From the offer for new customers on 18-10-2026.",
  "Gas vast; de prijs per m³ staat in je contract.": "Fixed gas; the price per m³ is in your contract.",
  "Gas variabel (ENGIE Open); de prijs per m³ staat in je contract.":
    "Variable gas (ENGIE Open); the price per m³ is in your contract.",
  "Alle bedragen komen uit het aanbod voor nieuwe klanten op 18-10-2026 (start rond half november); ze kunnen per klant en startdatum verschillen.":
    "All amounts come from the offer for new customers on 18-10-2026 (starting around mid November); they can differ per customer and start date.",
  "ENGIE gaat naar kwartierprijzen 'vanaf dat en/of enig moment', zonder datum.":
    "ENGIE is moving to quarter-hour prices 'from that and/or any moment', without a date.",
  "De verkoopvergoeding bij dynamisch na 2027 is 'nog te bepalen'.":
    "The selling fee with dynamic after 2027 is 'yet to be determined'.",
  "De HACS-integratie van ENGIE geeft de kale day-ahead-prijs, zonder energiebelasting en inkoopvergoeding.":
    "The ENGIE HACS integration gives the bare day-ahead price, without energy tax and purchasing fee.",

  // Essent
  "Essent: (beursprijs + inkoopvergoeding + energiebelasting) × 1,21, per uur met het gemiddelde van de vier kwartierprijzen. Inkoopvergoeding € 0,02089 zonder btw (€ 0,02528 met), uit de prijs-API van Essent.":
    "Essent: (exchange price + purchasing fee + energy tax) × 1.21, per hour with the average of the four quarter-hour prices. Purchasing fee € 0.02089 excluding VAT (€ 0.02528 including), from the Essent price API.",
  "Tot 2027 krijg je tot je jaarverbruik per uur hetzelfde tarief terug als je betaalt, inclusief btw, energiebelasting en inkoopvergoeding. Over een jaaroverschot de beursprijs zonder btw min € 0,02089 verkoopvergoeding; komt dat negatief uit, dan wordt het € 0. Geen terugleverkosten.":
    "Until 2027 you get the same rate back per hour as you pay, including VAT, energy tax and purchasing fee, up to your annual consumption. On an annual surplus the exchange price excluding VAT minus a € 0.02089 selling fee; if that comes out negative, it becomes € 0. No export costs.",
  "Gas dynamisch; de prijs-API van Essent en de core-integratie geven de gasprijs met inkoopvergoeding en energiebelasting.":
    "Dynamic gas; the Essent price API and the core integration give the gas price with purchasing fee and energy tax.",
  "Vaste leveringskosten bij dynamisch alleen van vergelijkers, en die spreken elkaar tegen (€ 7,49 tegen € 10,49 tot € 10,99).":
    "Fixed supply costs with dynamic only from comparison sites, and they contradict each other (€ 7.49 against € 10.49 to € 10.99).",
  "De core-integratie Essent is waarschijnlijk stuk sinds juni 2026: de prijs-API vraagt een extra header die de bibliotheek niet meestuurt.":
    "The Essent core integration has probably been broken since June 2026: the price API asks for an extra header that the library does not send.",

  // Frank Energie
  "Inkoopvergoeding teruglevering": "Purchasing fee on export",
  "Terugleverbonus": "Export bonus",
  "Frank Energie: (marktprijs + energiebelasting) × 1,21, plus € 0,01815 inkoopvergoeding met btw (€ 0,015 zonder), uit de prijs-API van Frank. In de app kies je zelf tussen kwartier- en uurprijzen.":
    "Frank Energie: (market price + energy tax) × 1.21, plus a € 0.01815 purchasing fee including VAT (€ 0.015 excluding), from the Frank price API. In the app you choose between quarter-hour and hourly prices yourself.",
  "Je krijgt de EPEX-marktprijs van het uur of kwartier van teruglevering. Terugleverkosten zijn er niet, behalve de inkoopvergoeding teruglevering; of die erbij komt of eraf gaat, zegt Frank niet eenduidig. Met de dienst Slim Terugleveren komt er overdag, bij een positieve prijs, een terugleverbonus van ongeveer 15% over de marktprijs bij, tot 7.500 kWh per jaar; de hoogte bepaalt Frank zelf.":
    "You get the EPEX market price of the hour or quarter hour of export. There are no export costs, apart from the purchasing fee on export; Frank does not say clearly whether it is added or deducted. With the Slim Terugleveren service, an export bonus of about 15% on the market price is added during the day when the price is positive, up to 7,500 kWh per year; Frank decides the amount itself.",
  "Vaste terugleveringskosten: een vast bedrag per dag naar je opgewekte stroom per jaar, in schalen die op het tarievenblad bij je overeenkomst staan. De terugleververgoeding na salderen staat ook in je overeenkomst.":
    "Fixed export costs: a fixed amount per day based on the electricity you generate per year, in bands listed on the tariff sheet with your agreement. The export tariff after net metering is also in your agreement.",
  "Vaste terugleveringskosten: een vast bedrag per dag naar je opgewekte stroom per jaar, in schalen die op het tarievenblad bij je overeenkomst staan. De terugleververgoeding na salderen staat ook in je overeenkomst en kan met elke tariefwijziging veranderen.":
    "Fixed export costs: a fixed amount per day based on the electricity you generate per year, in bands listed on the tariff sheet with your agreement. The export tariff after net metering is also in your agreement and can change with every tariff change.",
  "Gas dynamisch.": "Dynamic gas.",
  "Gas vast, ook naast dynamische stroom (Dynamisch Product met Vaste Gasprijs) en als wintervast contract.":
    "Fixed gas, also alongside dynamic electricity (Dynamisch Product met Vaste Gasprijs) and as a winter-fixed contract.",
  "Inkoopvergoeding teruglevering niet ingevuld: de kennisbank zegt € 0,0182 bovenop de marktprijs, de productvoorwaarden noemen hem als enige terugleverkosten, Gaslicht.com zegt 'in mindering', Keuze.nl € 0,0127 eraf zonder Slim Terugleveren.":
    "Purchasing fee on export not filled in: the knowledge base says € 0.0182 on top of the market price, the product terms name it as the only export costs, Gaslicht.com says 'deducted', Keuze.nl € 0.0127 off without Slim Terugleveren.",
  "Of de marktprijs bij teruglevering met of zonder btw wordt vergoed, staat er niet.":
    "It does not say whether the market price for export is paid with or without VAT.",
  "Terugleverbonus: Frank zegt ongeveer 15%, de voorwaarden zeggen variabel en naar eigen inzicht; daarom geen percentage ingevuld.":
    "Export bonus: Frank says about 15%, the terms say variable and at its own discretion; so no percentage filled in.",
  "Uur of kwartier kies je zelf in de app; hier staat kwartier, de standaard van de HACS-integratie.":
    "You choose hour or quarter hour yourself in the app; quarter hour is set here, the default of the HACS integration.",
  "Vaste leveringskosten alleen van vergelijkers, en die verschillen: € 6,00 (Gaslicht.com) tegen € 7,00 (Overstappen.nl).":
    "Fixed supply costs only from comparison sites, and they differ: € 6.00 (Gaslicht.com) against € 7.00 (Overstappen.nl).",
  "De bedragen van de schalen bij vast en variabel zijn niet openbaar.":
    "The amounts of the bands with fixed and variable are not public.",

  // Gewoon Energie
  "Gewoon Energie is een handelsnaam van Innova Energie. Vast 1 of 3 jaar: de terugleverkosten en de terugleververgoeding staan in je persoonlijke aanbod; een openbaar tariefblad is er niet.":
    "Gewoon Energie is a trade name of Innova Energie. Fixed 1 or 3 years: the export costs and the export tariff are in your personal offer; there is no public tariff sheet.",
  "Gewoon Energie is een handelsnaam van Innova Energie. Terugleverkosten € 0,1331 per kWh met btw over elke teruggeleverde kWh (tariefblad 1 november 2026). Boven salderen € 0,05 per kWh, voor een huishouden zonder btw; vanaf 2027 50% van het normaaltarief. Vaste leveringskosten € 101,64 per jaar met btw.":
    "Gewoon Energie is a trade name of Innova Energie. Export costs € 0.1331 per kWh including VAT on every exported kWh (tariff sheet 1 November 2026). Above net metering € 0.05 per kWh, for a household excluding VAT; from 2027 50% of the normal rate. Fixed supply costs € 101.64 per year including VAT.",
  "Gas vast, 1 of 3 jaar; de prijs per m³ staat in je aanbod.":
    "Fixed gas, 1 or 3 years; the price per m³ is in your offer.",
  "Gas variabel; de prijs per m³ staat op het variabele tariefblad.":
    "Variable gas; the price per m³ is on the variable tariff sheet.",
  "Terugleverkosten en terugleververgoeding bij vast: alleen in het persoonlijke aanbod.":
    "Export costs and export tariff with fixed: only in the personal offer.",
  "Of het variabele tarief nog voor nieuwe klanten geldt; de site verkoopt vooral vast.":
    "Whether the variable rate still applies to new customers; the site mainly sells fixed.",

  // Gezinsenergie
  "Gezinsenergie is tussenpersoon; je contract sluit je met Hezelaer Energy. Bij dynamisch betaal je de beursprijs plus een inkoopvergoeding. Er zijn geen bedragen gepubliceerd; het aanbod gaat op maat.":
    "Gezinsenergie is an intermediary; you sign your contract with Hezelaer Energy. With dynamic you pay the exchange price plus a purchasing fee. No amounts are published; the offer is tailored.",
  "Tot 2027 krijg je voor elke teruggeleverde kWh het tarief van dat uur, inclusief energiebelasting; over een jaaroverschot geen energiebelasting. Hezelaer rekent terugleveringskosten per kWh over je hele teruglevering; het bedrag staat in je contract.":
    "Until 2027 you get the rate of that hour for every exported kWh, including energy tax; no energy tax on an annual surplus. Hezelaer charges export costs per kWh on all your export; the amount is in your contract.",
  "Vast 1 of 3 jaar, en dynamisch-vast (zomer dynamisch, winter 6 maanden vast). Bedragen voor levering en teruglevering op maat; Hezelaer rekent terugleveringskosten per kWh, het bedrag staat in je contract.":
    "Fixed 1 or 3 years, and dynamic-fixed (dynamic in summer, fixed for 6 months in winter). Amounts for supply and export are tailored; Hezelaer charges export costs per kWh, the amount is in your contract.",
  "Variabel, op maat; Hezelaer rekent terugleveringskosten per kWh, het bedrag staat in je contract.":
    "Variable, tailored; Hezelaer charges export costs per kWh, the amount is in your contract.",
  "Gas vast, via Hezelaer Energy; de prijs staat in je contract.":
    "Fixed gas, through Hezelaer Energy; the price is in your contract.",
  "Gas variabel, via Hezelaer Energy; de prijs staat in je contract.":
    "Variable gas, through Hezelaer Energy; the price is in your contract.",
  "Geen enkel tarief gepubliceerd; het aanbod gaat op maat.":
    "Not a single tariff published; the offer is tailored.",
  "Uur of kwartier: de FAQ zegt uur, de pagina dynamisch-vast kwartierprijzen, en Hezelaer rekent af op de kleinste beschikbare meetgegevens.":
    "Hour or quarter hour: the FAQ says hour, the dynamic-fixed page quarter-hour prices, and Hezelaer bills on the smallest available metering data.",
  "Of de inkoopvergoeding van Hezelaer ook over teruglevering gaat (de voorwaarden zeggen 'verbruikte én/of teruggeleverde hoeveelheid').":
    "Whether the Hezelaer purchasing fee also applies to export (the terms say 'consumed and/or exported quantity').",
  "De privacyverklaring noemt nog VanHelder als vergunninghouder.":
    "The privacy statement still names VanHelder as licence holder.",

  // Greenchoice
  "Het dynamische contract van Greenchoice draait op het platform van EnergyZero, dat dan je leverancier is. De prijs per kwartier is de EPEX-marktprijs plus inkoopvergoeding, energiebelasting en btw; Greenchoice noemt de inkoopvergoeding en de vaste leveringskosten zonder bedrag.":
    "The Greenchoice dynamic contract runs on the EnergyZero platform, which is then your supplier. The price per quarter hour is the EPEX market price plus purchasing fee, energy tax and VAT; Greenchoice names the purchasing fee and the fixed supply costs without an amount.",
  "Tot 2027 krijg je voor teruglevering hetzelfde tarief als je op dat moment betaalt, inclusief belasting. Greenchoice rekent een vast bedrag per teruggeleverde kWh; volgens Keuze.nl € 0,0224, net als bij EnergyZero. Bij een negatieve prijs betaal je voor teruglevering.":
    "Until 2027 you get the same rate for export as you pay at that moment, including tax. Greenchoice charges a fixed amount per exported kWh; according to Keuze.nl € 0.0224, the same as EnergyZero. With a negative price you pay for export.",
  "Terugleverkosten per kWh over alle teruglevering, op het tarievenblad bij je contract (volgens Keuze.nl 13,6 cent); ook na 2027 per kWh. De netto terugleververgoeding geldt alleen voor wat na salderen overblijft, zonder belastingen.":
    "Export costs per kWh on all export, on the tariff sheet with your contract (according to Keuze.nl 13.6 cents); also per kWh after 2027. The net export tariff only applies to what is left after net metering, excluding taxes.",
  "Terugleverkosten per kWh over alle teruglevering, op het tarievenblad bij je contract. Bij het modelcontract variabel (18 mei 2026): € 0,13099 per kWh met btw, en een netto terugleververgoeding van € 0,141 per kWh, zonder btw.":
    "Export costs per kWh on all export, on the tariff sheet with your contract. With the variable model contract (18 May 2026): € 0.13099 per kWh including VAT, and a net export tariff of € 0.141 per kWh, excluding VAT.",
  "Gas dynamisch, prijs per dag, met inkoopvergoeding, energiebelasting en btw.":
    "Dynamic gas, price per day, with purchasing fee, energy tax and VAT.",
  "Gas variabel; de prijs per m³ staat op het tarievenblad bij je contract.":
    "Variable gas; the price per m³ is on the tariff sheet with your contract.",
  "Inkoopvergoeding en vaste leveringskosten van het dynamische contract staan niet op de site van Greenchoice; of de bedragen van EnergyZero zelf gelden, is niet bevestigd.":
    "The purchasing fee and fixed supply costs of the dynamic contract are not on the Greenchoice site; it is not confirmed whether the amounts of EnergyZero itself apply.",
  "De verkoopvergoeding van € 0,0224 komt van Keuze.nl en klopt met EnergyZero, maar Greenchoice noemt zelf geen bedrag.":
    "The selling fee of € 0.0224 comes from Keuze.nl and matches EnergyZero, but Greenchoice does not state an amount itself.",
  "Terugleververgoeding bij vast: Keuze.nl € 0,15 en Overstappen.nl € 0,0846 spreken elkaar tegen.":
    "Export tariff with fixed: Keuze.nl € 0.15 and Overstappen.nl € 0.0846 contradict each other.",
  "De HACS-integratie van Greenchoice geeft de tarieven van een vast of variabel contract, geen dynamische prijs. De core-integratie EnergyZero geeft een all-in prijs zonder inkoopvergoeding.":
    "The Greenchoice HACS integration gives the tariffs of a fixed or variable contract, no dynamic price. The EnergyZero core integration gives an all-in price without purchasing fee.",

  // GroeneStroomLokaal
  "GroeneStroomLokaal is een wederverkoper van EnergyZero, zonder eigen vergunning. Flexcontract (voorwaarden april 2021): EPEX-prijs + inkoopkosten, vermeerderd met energiebelasting en btw. Op de eigen site staan geen bedragen; Overstappen.nl noemt € 0,03388 opslag en € 5 vaste kosten per maand.":
    "GroeneStroomLokaal is a reseller of EnergyZero, without its own licence. Flexcontract (terms April 2021): EPEX price + purchasing costs, plus energy tax and VAT. Its own site shows no amounts; Overstappen.nl mentions € 0.03388 markup and € 5 fixed costs per month.",
  "Kennisbank (2020): binnen salderen krijg je het actuele uurtarief inclusief belastingen en inkoopkosten; voor netto teruglevering op de jaarrekening alleen het overeengekomen tarief.":
    "Knowledge base (2020): within net metering you get the current hourly rate including taxes and purchasing costs; for net export on the annual statement only the agreed rate.",
  "Tot 3 jaar vast. Kennisbank (2020): teruglevering tegen hetzelfde tarief als afname, inclusief inkoopkosten en belastingen; netto teruglevering tegen het overeengekomen tarief. Over terugleverkosten is niets gevonden.":
    "Fixed for up to 3 years. Knowledge base (2020): export at the same rate as import, including purchasing costs and taxes; net export at the agreed rate. Nothing was found about export costs.",
  "Of GroeneStroomLokaal nog nieuwe klanten aanneemt: het certificaat van de site was verlopen en de voorwaarden en kennisbank zijn van 2020 en 2021.":
    "Whether GroeneStroomLokaal still takes on new customers: the site's certificate had expired and the terms and knowledge base date from 2020 and 2021.",
  "Opslag en vaste kosten alleen van Overstappen.nl, zonder btw-vermelding; daarom niet ingevuld.":
    "Markup and fixed costs only from Overstappen.nl, without mention of VAT; so not filled in.",
  "Uur of kwartier: de voorwaarden van 2021 zeggen uur, de huidige stand is niet gevonden.":
    "Hour or quarter hour: the 2021 terms say hour, the current situation was not found.",
  "Verkoopvergoeding, negatieve prijzen en de regeling na 2027: niets gevonden; mogelijk gelden die van EnergyZero.":
    "Selling fee, negative prices and the arrangement after 2027: nothing found; those of EnergyZero may apply.",
  "De core-integratie EnergyZero geeft een all-in prijs zonder inkoopkosten.":
    "The EnergyZero core integration gives an all-in price without purchasing costs.",

  // Groenmij
  "Groenmij levert op de vergunning van ServiceHouse (onderdeel van Coolblue). Vast 1, 3 of 5 jaar; tarieven en terugleverkosten zijn niet gepubliceerd.":
    "Groenmij supplies under the licence of ServiceHouse (part of Coolblue). Fixed 1, 3 or 5 years; tariffs and export costs are not published.",
  "Of Groenmij nog nieuwe klanten aanneemt: de aanmeldsite was op 18-10-2026 onbereikbaar.":
    "Whether Groenmij still takes on new customers: the sign-up site could not be reached on 18-10-2026.",
  "Terugleverkosten en terugleververgoeding: niet gepubliceerd.":
    "Export costs and export tariff: not published.",

  // Groenpand Energie
  "Opslag": "Markup",
  "Groenpand Energie (handelsnaam van Chiriqui B.V., eigen vergunning): marktprijs + opslag van € 0,02 zonder btw (€ 0,0242 met), plus energiebelasting en 21% btw, volgens de tariefwidget op de site. Vastrecht € 8,47 per maand.":
    "Groenpand Energie (trade name of Chiriqui B.V., own licence): market price + markup of € 0.02 excluding VAT (€ 0.0242 including), plus energy tax and 21% VAT, according to the tariff widget on the site. Standing charge € 8.47 per month.",
  "Volgens de gegevens achter de tariefwidget krijg je de kale marktprijs min een afslag van € 0,02 per kWh zonder btw (€ 0,0242 met). Bij negatieve prijzen betaal je zelf voor teruglevering.":
    "According to the data behind the tariff widget you get the bare market price minus a deduction of € 0.02 per kWh excluding VAT (€ 0.0242 including). With negative prices you pay for export yourself.",
  "Nieuwe klanten: alleen het modelcontract 1 jaar vast (per 1 april 2026), andere vaste tarieven op aanvraag. Netto terugleververgoeding € 0,02 per kWh met btw, voor wat je op jaarbasis meer teruglevert dan afneemt. Vastrecht € 22,99 per maand met btw.":
    "New customers: only the 1 year fixed model contract (from 1 April 2026), other fixed tariffs on request. Net export tariff € 0.02 per kWh including VAT, for what you export beyond what you import on an annual basis. Standing charge € 22.99 per month including VAT.",
  "Nieuwe klanten: alleen het modelcontract variabel (per 1 april 2026). Netto terugleververgoeding € 0,02 per kWh met btw, voor wat je op jaarbasis meer teruglevert dan afneemt. Bestaande variabele tarieven wijzigen maandelijks.":
    "New customers: only the variable model contract (from 1 April 2026). Net export tariff € 0.02 per kWh including VAT, for what you export beyond what you import on an annual basis. Existing variable tariffs change monthly.",
  "Gas variabel; de prijs staat in de tariefwidget op de site.":
    "Variable gas; the price is in the tariff widget on the site.",
  "Uur of kwartier: de eigen pagina zegt per uur (met voorbeelden uit 2024), de voorwaarden laten het open.":
    "Hour or quarter hour: its own page says per hour (with examples from 2024), the terms leave it open.",
  "Of het vastrecht van € 8,47 met of zonder btw is, staat er niet (8,47 is precies 7,00 × 1,21).":
    "It does not say whether the standing charge of € 8.47 includes VAT (8.47 is exactly 7.00 × 1.21).",
  "De afslag bij teruglevering staat alleen in de gegevens achter de widget, en of Groenpand teruglevering met of zonder btw vergoedt, zegt het niet; daarom niet ingevuld.":
    "The deduction on export is only in the data behind the widget, and it does not say whether Groenpand pays for export with or without VAT; so not filled in.",
  "De modelcontracttarieven zijn van 1 april 2026; het variabele modelcontract wijzigt per kwartaal.":
    "The model contract tariffs date from 1 April 2026; the variable model contract changes every quarter.",
  "Terugleverkosten bij vast en variabel: 'geen terugleverboetes' op de site, maar de bevestigingsbrieven hebben een veld voor terugleverkosten.":
    "Export costs with fixed and variable: 'no export penalties' on the site, but the confirmation letters have a field for export costs.",

  // Hegg Energy
  "Hegg Energie Diensten is een handelsnaam van EnergyZero en draait op dat platform. Kwartierprijs EPEX + inkoopvergoeding, vermeerderd met energiebelasting en btw. Inkoopvergoeding € 0,02242 per kWh (bij de varianten Batterij sturing en V2G € 0,017), zonder btw-vermelding. Vaste leveringskosten € 7,50 per maand per aansluiting.":
    "Hegg Energie Diensten is a trade name of EnergyZero and runs on that platform. EPEX quarter-hour price + purchasing fee, plus energy tax and VAT. Purchasing fee € 0.02242 per kWh (€ 0.017 for the Batterij sturing and V2G variants), without mention of VAT. Fixed supply costs € 7.50 per month per connection.",
  "Je krijgt de kwartierprijs min een verkoopvergoeding van € 0,02242 per kWh (bij Batterij sturing en V2G € 0), ook over teruglevering uit een batterij of auto. Hegg rekent geen terugleverkosten. Tot 2027 telt een gesaldeerde kWh volgens Hegg evenveel als een verbruikte.":
    "You get the quarter-hour price minus a selling fee of € 0.02242 per kWh (€ 0 with Batterij sturing and V2G), also on export from a battery or car. Hegg charges no export costs. According to Hegg, until 2027 a netted kWh counts the same as a consumed one.",
  "Gas dynamisch (variant Alleen gas/stroom); vaste leveringskosten € 7,50 per maand per aansluiting.":
    "Dynamic gas (Alleen gas/stroom variant); fixed supply costs € 7.50 per month per connection.",
  "Of de inkoopvergoeding, de verkoopvergoeding en de vaste kosten met of zonder btw zijn, zegt Hegg niet: de eigen tabel met eerdere inkoopvergoedingen is zonder btw, EnergyZero noemt hetzelfde bedrag als verkoopvergoeding met btw. Daarom niet ingevuld.":
    "Hegg does not say whether the purchasing fee, the selling fee and the fixed costs include VAT: its own table of earlier purchasing fees is excluding VAT, EnergyZero names the same amount as a selling fee including VAT. So not filled in.",
  "Overstappen.nl noemt voor Hegg € 0,03388 per kWh, Hegg zelf € 0,02242.":
    "Overstappen.nl mentions € 0.03388 per kWh for Hegg, Hegg itself € 0.02242.",
  "Hoe salderen precies rekent: de productvoorwaarden noemen het jaargemiddelde van de kwartierprijzen, de kennisbank de prijs van het moment.":
    "How netting works exactly: the product terms mention the annual average of the quarter-hour prices, the knowledge base the price at the moment.",
  "Of de verkoopvergoeding na 2027 blijft.": "Whether the selling fee remains after 2027.",
  "De core-integratie EnergyZero geeft een all-in prijs zonder de inkoopvergoeding van Hegg.":
    "The EnergyZero core integration gives an all-in price without the Hegg purchasing fee.",

  // Holland Energie
  "Holland Energie (Nieuw-Hollands Energiebedrijf, vooral zakelijk): de EPEX-kwartierprijs plus een inkoopvergoeding, met btw over alle kosten en heffingen. De link naar de tarieven op de site geeft 'pagina niet gevonden'.":
    "Holland Energie (Nieuw-Hollands Energiebedrijf, mainly business): the EPEX quarter-hour price plus a purchasing fee, with VAT on all costs and levies. The link to the tariffs on the site gives 'page not found'.",
  "Volgens de pagina dynamische energie krijg je de marktprijs per kwartier min een lage terugleververgoeding; de energiebelasting wordt op jaarbasis gesaldeerd tot je verbruik.":
    "According to the dynamic energy page you get the market price per quarter hour minus a low export tariff; the energy tax is netted on an annual basis up to your consumption.",
  "Modelcontract vast (per 1 juli 2026): terugleverkosten € 0,01 per kWh en een terugleververgoeding van € 0,026 per kWh, met btw; vanaf 2027 dezelfde bedragen. Vaste leveringskosten € 9,99 per maand.":
    "Fixed model contract (from 1 July 2026): export costs € 0.01 per kWh and an export tariff of € 0.026 per kWh, including VAT; the same amounts from 2027. Fixed supply costs € 9.99 per month.",
  "Modelcontract variabel (per 1 juli 2026): terugleverkosten € 0,01 per kWh en een terugleververgoeding van € 0,026 per kWh, met btw. Vaste leveringskosten € 9,99 per maand.":
    "Variable model contract (from 1 July 2026): export costs € 0.01 per kWh and an export tariff of € 0.026 per kWh, including VAT. Fixed supply costs € 9.99 per month.",
  "Gas vast, in hetzelfde modelcontract als stroom.": "Fixed gas, in the same model contract as electricity.",
  "Gas variabel, in hetzelfde modelcontract als stroom.":
    "Variable gas, in the same model contract as electricity.",
  "Inkoopvergoeding en vaste leveringskosten van het dynamische contract niet gevonden.":
    "Purchasing fee and fixed supply costs of the dynamic contract not found.",
  "Teruglevering bij dynamisch: de eigen pagina's spreken elkaar tegen (marktprijs min een afslag, tegenover het leveringstarief inclusief belastingen).":
    "Export with dynamic: its own pages contradict each other (market price minus a deduction, against the supply rate including taxes).",
  "De pagina's over salderen zijn voor zakelijke klanten geschreven.":
    "The pages about net metering are written for business customers.",
  "De bedragen bij vast en variabel gelden voor het modelcontract; of huishoudens andere vaste of variabele contracten kunnen kiezen, staat er niet.":
    "The amounts for fixed and variable apply to the model contract; it does not say whether households can choose other fixed or variable contracts.",

  // Innova Energie
  "Afslag": "Deduction",
  "Innova: de spotprijs per uur (EPEX Day Ahead) plus een opslag per kWh, daarover btw en daarna de energiebelasting. Volgens de voorwaarden staat de opslag op de website, maar daar is hij niet te vinden; vergelijkers noemen € 0,01243 en € 0,018.":
    "Innova: the spot price per hour (EPEX Day Ahead) plus a markup per kWh, VAT on top of that and then the energy tax. According to the terms the markup is on the website, but it cannot be found there; comparison sites mention € 0.01243 and € 0.018.",
  "Per uur gesaldeerd: lever je in een uur meer terug dan je verbruikt, dan krijg je de gewogen gemiddelde spotprijs min een afslag per kWh (bedrag niet gevonden). De energiebelasting wordt op jaarbasis gesaldeerd. De site noemt een 'hoge terugleverbonus' zonder bedrag of voorwaarden.":
    "Netted per hour: if you export more than you consume in an hour, you get the weighted average spot price minus a deduction per kWh (amount not found). The energy tax is netted on an annual basis. The site mentions a 'high export bonus' without an amount or conditions.",
  "Vast 1 of 3 jaar: terugleverkosten en vergoeding staan in je persoonlijke aanbod. Bij het modelcontract vast 1 jaar (16 oktober 2026): terugleverkosten € 0,1331 per kWh met btw tot 2027 en € 0,10692 daarna, terugleververgoeding € 0,10962 zonder btw.":
    "Fixed 1 or 3 years: export costs and tariff are in your personal offer. With the 1 year fixed model contract (16 October 2026): export costs € 0.1331 per kWh including VAT until 2027 and € 0.10692 after that, export tariff € 0.10962 excluding VAT.",
  "Terugleverkosten € 0,1331 per kWh met btw over elke teruggeleverde kWh (tariefblad 1 november 2026). Boven salderen € 0,05 per kWh, voor een huishouden zonder btw; vanaf 2027 50% van het normaaltarief. Vaste leveringskosten € 101,64 per jaar met btw.":
    "Export costs € 0.1331 per kWh including VAT on every exported kWh (tariff sheet 1 November 2026). Above net metering € 0.05 per kWh, for a household excluding VAT; from 2027 50% of the normal rate. Fixed supply costs € 101.64 per year including VAT.",
  "Gas vast, ook als Hybride: dynamische stroom met vast gas.":
    "Fixed gas, also as Hybride: dynamic electricity with fixed gas.",
  "Opslag, afslag en vaste leveringskosten van het dynamische contract: niet op de site, en vergelijkers spreken elkaar tegen (€ 0,01243 en € 0,018 per kWh).":
    "Markup, deduction and fixed supply costs of the dynamic contract: not on the site, and comparison sites contradict each other (€ 0.01243 and € 0.018 per kWh).",
  "Hoogte en voorwaarden van de 'hoge terugleverbonus'.": "Size and conditions of the 'high export bonus'.",
  "Of en wanneer Innova naar kwartierprijzen gaat ('voorlopig uurprijzen', 'verwacht in 2026').":
    "Whether and when Innova moves to quarter-hour prices ('hourly prices for now', 'expected in 2026').",
  "Terugleverkosten bij de gewone vaste contracten, vooral vanaf 2027: Keuze.nl € 0,06398, Energievergelijk.nl € 0,133.":
    "Export costs with the regular fixed contracts, especially from 2027: Keuze.nl € 0.06398, Energievergelijk.nl € 0.133.",
  "Of het variabele contract nog voor nieuwe klanten openstaat.":
    "Whether the variable contract is still open to new customers.",

  // Kikker Energie
  "Kikker levert vooral via wederverkopers onder hun eigen naam (zoals Noord Dynamic, Dynamiq en Volti); openbaar is alleen het modelcontract (vanaf 1 oktober 2026). Terugleverkosten in schalen naar je teruglevering per jaar; je schaal staat in je bevestigingsbrief (schatting € 0,67 per dag bij 2.350 kWh). Boven salderen € 0,0242 per kWh, met btw.":
    "Kikker mainly supplies through resellers under their own name (such as Noord Dynamic, Dynamiq and Volti); only the model contract is public (from 1 October 2026). Export costs in bands based on your export per year; your band is in your confirmation letter (estimate € 0.67 per day at 2,350 kWh). Above net metering € 0.0242 per kWh, including VAT.",
  "Of Kikker zelf nog nieuwe klanten aanneemt buiten wederverkopers om; alleen het modelcontract is openbaar.":
    "Whether Kikker itself still takes on new customers outside its resellers; only the model contract is public.",
  "De schalen van de terugleverkosten zijn niet gepubliceerd.":
    "The bands of the export costs are not published.",
  "De ACM legde Kikker in 2026 een bindende aanwijzing op; het beroep loopt nog.":
    "In 2026 the ACM imposed a binding instruction on Kikker; the appeal is still ongoing.",

  // Live Energy
  "Live Energy, een handelsnaam van OpenSource Energie: leveringstarief zonder btw = EPEX-kwartierprijs + inkoopvergoeding (bij groene stroom ook de kosten van garanties van oorsprong), vermeerderd met energiebelasting en btw. Het bedrag staat in je klantportaal; volgens Selectra € 0,0242 per kWh.":
    "Live Energy, a trade name of OpenSource Energie: supply rate excluding VAT = EPEX quarter-hour price + purchasing fee (for green electricity also the cost of guarantees of origin), plus energy tax and VAT. The amount is in your customer portal; according to Selectra € 0.0242 per kWh.",
  "Per kwartier verrekend met je verbruik: voor een overschot krijg je de marktprijs min de inkoopvergoeding. De energiebelasting wordt op jaarbasis gesaldeerd. Bij een negatieve prijs betaal je voor teruglevering.":
    "Settled against your consumption per quarter hour: for a surplus you get the market price minus the purchasing fee. The energy tax is netted on an annual basis. With a negative price you pay for export.",
  "Inkoopvergoeding € 0,0242 alleen van Selectra, zonder btw-vermelding; daarom niet ingevuld.":
    "Purchasing fee € 0.0242 only from Selectra, without mention of VAT; so not filled in.",
  "Vaste leveringskosten en het bedrag dat bij teruglevering afgaat: niet gepubliceerd.":
    "Fixed supply costs and the amount deducted on export: not published.",

  // Mega
  "Verbruiksopslag": "Consumption markup",
  "Inkooptoeslag": "Purchasing surcharge",
  "Mega: de kwartierprijs bestaat uit de EPEX-prijs, een vaste verbruiksopslag per kWh en de overheidsheffingen (energiebelasting en btw). Mega publiceert de opslag niet; volgens Gaslicht.com € 0,0182 met btw (Keuze.nl € 0,01815), en vaste leveringskosten € 6,05 per maand met btw.":
    "Mega: the quarter-hour price is made up of the EPEX price, a fixed consumption markup per kWh and the government levies (energy tax and VAT). Mega does not publish the markup; according to Gaslicht.com € 0.0182 including VAT (Keuze.nl € 0.01815), and fixed supply costs € 6.05 per month including VAT.",
  "Per kwartier verrekend: voor netto teruglevering de kale kwartierprijs min een inkooptoeslag; volgens Keuze.nl € 0,03025 per kWh. De energiebelasting wordt op jaarbasis gesaldeerd. Bij een negatieve prijs betaal je voor teruglevering.":
    "Settled per quarter hour: for net export the bare quarter-hour price minus a purchasing surcharge; according to Keuze.nl € 0.03025 per kWh. The energy tax is netted on an annual basis. With a negative price you pay for export.",
  "Contracten van na 9 januari 2026 betalen een vast bedrag per teruggeleverde kWh, oudere vaste contracten schalen. Terugleverkosten en vergoeding zijn volgens Mega zonder btw en staan in je overeenkomst; Keuze.nl noemt 17,2 cent terugleverkosten.":
    "Contracts from after 9 January 2026 pay a fixed amount per exported kWh, older fixed contracts pay in bands. According to Mega, export costs and tariff are excluding VAT and are in your agreement; Keuze.nl mentions 17.2 cents export costs.",
  "Terugleverkosten een vast bedrag per teruggeleverde kWh, geleidelijk ingevoerd sinds 9 januari 2026. Terugleverkosten en vergoeding zijn volgens Mega zonder btw en staan in je overeenkomst.":
    "Export costs are a fixed amount per exported kWh, introduced gradually since 9 January 2026. According to Mega, export costs and tariff are excluding VAT and are in your agreement.",
  "De verbruiksopslag en de vaste leveringskosten komen alleen van vergelijkers (Gaslicht.com, Keuze.nl).":
    "The consumption markup and the fixed supply costs only come from comparison sites (Gaslicht.com, Keuze.nl).",
  "Inkooptoeslag bij teruglevering (€ 0,03025) alleen van Keuze.nl, zonder btw-vermelding; daarom niet ingevuld.":
    "Purchasing surcharge on export (€ 0.03025) only from Keuze.nl, without mention of VAT; so not filled in.",
  "Of Mega de kale kwartierprijs bij teruglevering met of zonder btw vergoedt, staat er niet.":
    "It does not say whether Mega pays the bare quarter-hour price for export with or without VAT.",
  "Terugleverkosten bij vast (17,2 cent) alleen van Keuze.nl.":
    "Export costs with fixed (17.2 cents) only from Keuze.nl.",

  // NextEnergy
  "NextEnergy: leveringsprijs = beursprijs (het uurgemiddelde van de kwartierprijzen) + inkoopvergoeding, totaalprijs = leveringsprijs + energiebelasting, en btw over alles. Inkoopvergoeding 2,1 cent per kWh met btw voor nieuwe klanten (bestaande klanten naar het moment waarop ze klant werden). Vaste kosten € 5,99 per maand per aansluiting. NextBattery heeft geen inkoopvergoeding.":
    "NextEnergy: supply price = exchange price (the hourly average of the quarter-hour prices) + purchasing fee, total price = supply price + energy tax, and VAT on everything. Purchasing fee 2.1 cents per kWh including VAT for new customers (existing customers according to when they became a customer). Fixed costs € 5.99 per month per connection. NextBattery has no purchasing fee.",
  "Terugleveringsprijs = beursprijs min verkoopvergoeding, en voor nieuwe contracten is dat de beursprijs. Geen vaste terugleverkosten. Zonnebonus: 50% over de beursprijs, voor zonnestroom tussen 06:00 en 22:00 en alleen bij een positieve prijs, naar rato boven 6.000 kWh per jaar. Tot 2027 wordt de energiebelasting op jaarbasis gesaldeerd.":
    "Export price = exchange price minus selling fee, and for new contracts that is the exchange price. No fixed export costs. Zonnebonus: 50% on the exchange price, for solar power between 06:00 and 22:00 and only with a positive price, pro rata above 6,000 kWh per year. Until 2027 the energy tax is netted on an annual basis.",
  "Gas dynamisch, met 7,9 cent per m³ inkoopvergoeding met btw.":
    "Dynamic gas, with a purchasing fee of 7.9 cents per m³ including VAT.",
  "Gas vast of met een prijsplafond (ook als Wintervast).":
    "Gas fixed or with a price cap (also as Wintervast).",
  "Inkoopvergoeding niet ingevuld: NextEnergy zegt 2,1 cent met btw (de btw-vermelding staat direct na het gasbedrag), Gaslicht.com en Keuze.nl zeggen 2,19 cent, en bestaande klanten kunnen een ander bedrag hebben.":
    "Purchasing fee not filled in: NextEnergy says 2.1 cents including VAT (the mention of VAT comes right after the gas amount), Gaslicht.com and Keuze.nl say 2.19 cents, and existing customers may have a different amount.",
  "Verkoopvergoeding niet ingevuld: NextEnergy zegt dat nieuwe contracten de beursprijs krijgen, Keuze.nl noemt € 0,01.":
    "Selling fee not filled in: NextEnergy says new contracts get the exchange price, Keuze.nl mentions € 0.01.",
  "Of de beursprijs bij teruglevering, en de Zonnebonus daarover, met of zonder btw is, staat er niet.":
    "It does not say whether the exchange price for export, and the Zonnebonus on it, include VAT.",
  "De Zonnebonus geldt van 06:00 tot 22:00; de coach rekent hem van zonsopkomst tot zonsondergang, en telt de grens van 6.000 kWh niet.":
    "The Zonnebonus applies from 06:00 to 22:00; the coach calculates it from sunrise to sunset, and does not count the 6,000 kWh limit.",
  "De HACS-integratie van larsjuhw leest de anonieme prijzen van het klantportaal, met twee decimalen en zonder je eigen inkoopvergoeding; de entiteitnaam is afgeleid uit de code.":
    "The HACS integration by larsjuhw reads the anonymous prices from the customer portal, with two decimals and without your own purchasing fee; the entity name is derived from the code.",
  "ANWB kondigde op 16-10-2026 aan NextEnergy over te nemen (ACM-goedkeuring nodig); prijzen en voorwaarden kunnen in 2027 veranderen.":
    "On 16-10-2026 ANWB announced it would take over NextEnergy (ACM approval needed); prices and terms may change in 2027.",

  // Noord Dynamic
  "Variabele vergoeding": "Variable fee",
  "Noord Dynamic is een merk op de vergunning van Kikker Energie (niet hetzelfde als Noord Energie). Je betaalt de beursprijs plus een variabele vergoeding; er zijn geen bedragen gepubliceerd.":
    "Noord Dynamic is a brand under the licence of Kikker Energie (not the same as Noord Energie). You pay the exchange price plus a variable fee; no amounts are published.",
  "Niets over teruglevering gepubliceerd.": "Nothing published about export.",
  "Geen tarieven, geen interval en niets over teruglevering gepubliceerd.":
    "No tariffs, no interval and nothing about export published.",
  "Of het merk nog nieuwe klanten aanneemt.": "Whether the brand still takes on new customers.",

  // Noord Energie
  "Variabele leveringsvergoeding": "Variable supply fee",
  "Noord Energie: leveringstarief = beursprijs per kwartier (EPEX Spot Power NL Day Ahead) + inkoopvergoeding, met energiebelasting en btw daarover. De inkoopvergoeding staat in je bevestigingsbrief; volgens Keuze.nl € 0,01936 per kWh. Niet te verwarren met Noord Dynamic, dat via Kikker levert.":
    "Noord Energie: supply rate = exchange price per quarter hour (EPEX Spot Power NL Day Ahead) + purchasing fee, with energy tax and VAT on top. The purchasing fee is in your confirmation letter; according to Keuze.nl € 0.01936 per kWh. Not to be confused with Noord Dynamic, which supplies through Kikker.",
  "Wat niet gesaldeerd wordt krijgt de gerealiseerde beursprijs min de overeengekomen variabele leveringsvergoeding (volgens Keuze.nl € 0,0194). Tot en met 2026 wordt de energiebelasting gesaldeerd.":
    "What is not netted gets the realised exchange price minus the agreed variable supply fee (according to Keuze.nl € 0.0194). Up to and including 2026 the energy tax is netted.",
  "Terugleverkosten € 0,121 per kWh met btw, tot en met 2026, voor teruglevering op momenten dat je opwek hoger is dan je verbruik. Vanaf 2027 de terugleververgoeding (50% van het leveringstarief) min € 0,01. De terugleververgoeding na salderen staat in je bevestiging.":
    "Export costs € 0.121 per kWh including VAT, up to and including 2026, for export at moments when your generation is higher than your consumption. From 2027 the export tariff (50% of the supply rate) minus € 0.01. The export tariff after net metering is in your confirmation.",
  "Flexibel, maandelijks opzegbaar. Bij het modelcontract variabel (1 oktober 2026): terugleverkosten € 0,14 en terugleververgoeding € 0,15 per kWh, met btw.":
    "Flexible, cancellable monthly. With the variable model contract (1 October 2026): export costs € 0.14 and export tariff € 0.15 per kWh, including VAT.",
  "Gas vast, ook als hybride: dynamische stroom met vast gas.":
    "Fixed gas, also as hybrid: dynamic electricity with fixed gas.",
  "Inkoop- en verkoopvergoeding bij dynamisch alleen van Keuze.nl, zonder btw-vermelding; daarom niet ingevuld.":
    "Purchasing fee and selling fee with dynamic only from Keuze.nl, without mention of VAT; so not filled in.",
  "Of de terugleverkosten van € 0,121 per kWh ook bij dynamisch gelden: Keuze.nl zegt ja, de dynamische voorwaarden 2026 noemen ze niet.":
    "Whether the export costs of € 0.121 per kWh also apply with dynamic: Keuze.nl says yes, the 2026 dynamic terms do not mention them.",
  "Terugleverkosten bij het gewone variabele contract (Flexibel): niet gevonden.":
    "Export costs with the regular variable contract (Flexibel): not found.",

  // om | nieuwe energie
  "Inkoopvergoeding levering": "Purchasing fee on supply",
  "om | nieuwe energie: het leveringstarief per kwartier (EPEX Spot Power NL Day Ahead) + inkoopvergoeding levering, daarover energiebelasting en btw. Inkoopvergoeding € 0,020661 zonder btw; voor consumenten staat hij als € 0,13585 per kWh met btw en energiebelasting. Vaste leveringskosten € 0,281781 per dag met btw.":
    "om | nieuwe energie: the supply rate per quarter hour (EPEX Spot Power NL Day Ahead) + purchasing fee on supply, with energy tax and VAT on top. Purchasing fee € 0.020661 excluding VAT; for consumers it is listed as € 0.13585 per kWh including VAT and energy tax. Fixed supply costs € 0.281781 per day including VAT.",
  "Per kwartier gesaldeerd: voor wat je in een kwartier meer teruglevert dan je afneemt, krijg je de marktprijs min de inkoopvergoeding teruglevering (€ 0,025 met btw, € 0,020661 zonder). De energiebelasting wordt op jaarbasis gesaldeerd. Die aftrek blijft ook na 2027.":
    "Netted per quarter hour: for what you export beyond what you import in a quarter hour, you get the market price minus the purchasing fee on export (€ 0.025 including VAT, € 0.020661 excluding). The energy tax is netted on an annual basis. That deduction also remains after 2027.",
  "Een 1 of 3 Jaar Vast uit 2026 betaalt vaste terugleverkosten per kWh, gepubliceerd per maand van afsluiten (oktober 2026: 1 jaar € 0,073801, 3 jaar € 0,054648, met btw). Terugleververgoeding na salderen oktober 2026: 1 jaar € 0,094093, 3 jaar € 0,07452. Vaste contracten uit 2024 en 2025 betalen in schalen, zoals bij variabel.":
    "A 1 or 3 Jaar Vast from 2026 pays fixed export costs per kWh, published per month of signing (October 2026: 1 year € 0.073801, 3 years € 0.054648, including VAT). Export tariff after net metering October 2026: 1 year € 0.094093, 3 years € 0.07452. Fixed contracts from 2024 and 2025 pay in bands, as with variable.",
  "Flex en Variabel: vaste terugleveringskosten per dag in schalen naar je totale teruglevering vóór salderen; tot 1.000 kWh niets, daarboven € 151,25 per jaar en € 60,50 per 500 kWh extra, met btw. Terugleververgoeding na salderen bij Flex in november 2026 € 0,064861 per kWh met btw.":
    "Flex and Variabel: fixed export costs per day in bands based on your total export before net metering; nothing up to 1,000 kWh, above that € 151.25 per year and € 60.50 per 500 kWh extra, including VAT. Export tariff after net metering with Flex in November 2026 € 0.064861 per kWh including VAT.",
  "De inkoopvergoeding teruglevering is niet ingevuld: de voorwaarden zeggen dat de contractprijs voor teruglevering zonder btw is, de tarievenpagina geeft de aftrek als € 0,025 met btw.":
    "The purchasing fee on export is not filled in: the terms say the contract price for export is excluding VAT, the tariff page gives the deduction as € 0.025 including VAT.",
  "Kwartier of uur: voorwaarden en tarievenpagina zeggen kwartier, de productpagina nog per uur.":
    "Quarter hour or hour: terms and tariff page say quarter hour, the product page still per hour.",
  "Bij het ophalen meldde de tarievenpagina een storing bij de dynamische tarieven.":
    "When it was fetched, the tariff page reported a fault with the dynamic tariffs.",
  "om fuseert met Energie VanOns en gaat op termijn verder als Energie VanOns; naam, voorwaarden en platform kunnen veranderen.":
    "om is merging with Energie VanOns and will eventually continue as Energie VanOns; name, terms and platform may change.",

  // OpenSource Energie
  "Vergoeding voor afhandeling": "Handling fee",
  "OpenSource Energie is vooral een platform voor partners die onder eigen naam leveren. Zelf: (marktprijs per kwartier + inkoopvergoeding + energiebelasting) × 1,21, met € 0,02 inkoopvergoeding zonder btw volgens de prijswidget op de site; bij groene stroom komen de kosten van garanties van oorsprong erbij. Wie een batterij of laadpaal laat sturen, moet dat vooraf melden (SMART-contract).":
    "OpenSource Energie is mainly a platform for partners who supply under their own name. Itself: (market price per quarter hour + purchasing fee + energy tax) × 1.21, with a € 0.02 purchasing fee excluding VAT according to the price widget on the site; for green electricity the cost of guarantees of origin is added. If you have a battery or charger controlled, you must report that in advance (SMART contract).",
  "Voor wat je meer opwekt dan je verbruikt krijg je de marktprijs per tijdseenheid, aangevuld of verminderd met een vergoeding per kWh voor afhandeling; dat bedrag staat nergens.":
    "For what you generate beyond what you consume you get the market price per time unit, increased or reduced by a handling fee per kWh; that amount is not stated anywhere.",
  "Alleen het wettelijke modelcontract (vanaf 1 oktober 2026): tot 2027 € 0,015 per kWh met btw voor wat na salderen overblijft; tot dan noemt de tabel geen terugleverkosten. Vanaf 2027 terugleverkosten € 0,06 en een vergoeding van € 0,1193 per kWh, met btw. Vaste leveringskosten € 8,50 per maand.":
    "Only the statutory model contract (from 1 October 2026): until 2027 € 0.015 per kWh including VAT for what is left after net metering; until then the table mentions no export costs. From 2027 export costs € 0.06 and a tariff of € 0.1193 per kWh, including VAT. Fixed supply costs € 8.50 per month.",
  "Alleen het wettelijke modelcontract (1 oktober 2026 tot 1 januari 2027): € 0,015 per kWh met btw voor wat na salderen overblijft; tot 2027 noemt de tabel geen terugleverkosten. Vanaf 2027 terugleverkosten € 0,0605 en een vergoeding van € 0,13085 per kWh, met btw.":
    "Only the statutory model contract (1 October 2026 to 1 January 2027): € 0.015 per kWh including VAT for what is left after net metering; until 2027 the table mentions no export costs. From 2027 export costs € 0.0605 and a tariff of € 0.13085 per kWh, including VAT.",
  "Gas dynamisch; de prijswidget rekent € 0,09 per m³ inkoop zonder btw, met de transportkosten erbij.":
    "Dynamic gas; the price widget uses € 0.09 per m³ purchasing excluding VAT, with the transport costs added.",
  "De inkoopvergoeding van € 0,02 komt uit de prijswidget (het standaardmerk), niet uit een tariefblad; volgens de voorwaarden staat het bedrag in de offerte, en merken op het platform kunnen een eigen opslag hebben.":
    "The € 0.02 purchasing fee comes from the price widget (the default brand), not from a tariff sheet; according to the terms the amount is in the quote, and brands on the platform may have their own markup.",
  "De kosten van garanties van oorsprong bij groene stroom: geen bedrag gevonden.":
    "The cost of guarantees of origin for green electricity: no amount found.",
  "Teruglevering bij dynamisch: bedrag en richting van de vergoeding voor afhandeling, en of de marktprijs met of zonder btw wordt vergoed, staan nergens.":
    "Export with dynamic: the amount and direction of the handling fee, and whether the market price is paid with or without VAT, are not stated anywhere.",
  "Vaste leveringskosten van het dynamische contract: niet op de site.":
    "Fixed supply costs of the dynamic contract: not on the site.",
  "Of je als particulier zonder partnermerk een contract kunt afsluiten: alleen via een offerte of contact.":
    "Whether you can sign a contract as a private customer without a partner brand: only through a quote or by contacting them.",

  // Oxxio
  "Oxxio (op het platform van Eneco Group): de marktprijs per uur (EPEX Spot Power NL Hourly) + een kleine inkoopvergoeding + energiebelasting en btw. Oxxio publiceert de inkoopvergoeding niet; Gaslicht.com noemt 2,30 cent met btw, Keuze.nl € 0,02237.":
    "Oxxio (on the Eneco Group platform): the market price per hour (EPEX Spot Power NL Hourly) + a small purchasing fee + energy tax and VAT. Oxxio does not publish the purchasing fee; Gaslicht.com mentions 2.30 cents including VAT, Keuze.nl € 0.02237.",
  "Tot 2027 krijg je tot je jaarverbruik per uur hetzelfde tarief terug als je betaalt, inclusief inkoopvergoeding. Over een jaaroverschot de marktprijs van het uur zonder btw, min een vaste verkoopvergoeding per kWh (volgens Keuze.nl € 0,02237). Geen terugleverkosten. Bij een negatieve prijs betaal je voor teruglevering.":
    "Until 2027 you get the same rate back per hour as you pay, including the purchasing fee, up to your annual consumption. On an annual surplus the market price of the hour excluding VAT, minus a fixed selling fee per kWh (according to Keuze.nl € 0.02237). No export costs. With a negative price you pay for export.",
  "Terugleverkosten een bedrag per kWh over alle teruglevering, in je contract (volgens Keuze.nl 14,2 cent). Over de terugleververgoeding betaal je geen btw; tot 2027 alleen over wat na salderen overblijft.":
    "Export costs are an amount per kWh on all export, in your contract (according to Keuze.nl 14.2 cents). You pay no VAT on the export tariff; until 2027 only on what is left after net metering.",
  "Gas dynamisch: de marktprijs op het moment van verbruik, plus een kleine inkoopvergoeding per m³, energiebelasting en btw.":
    "Dynamic gas: the market price at the moment of consumption, plus a small purchasing fee per m³, energy tax and VAT.",
  "Gas vast, 1 of 3 jaar, ook als Oxxio Hybride: dynamische stroom met vast gas.":
    "Fixed gas, 1 or 3 years, also as Oxxio Hybride: dynamic electricity with fixed gas.",
  "Inkoopvergoeding niet ingevuld: Gaslicht.com zegt 2,30 cent met btw, Keuze.nl € 0,02237 zonder btw-vermelding.":
    "Purchasing fee not filled in: Gaslicht.com says 2.30 cents including VAT, Keuze.nl € 0.02237 without mention of VAT.",
  "Verkoopvergoeding (€ 0,02237) alleen van Keuze.nl, zonder btw-vermelding.":
    "Selling fee (€ 0.02237) only from Keuze.nl, without mention of VAT.",
  "Vaste leveringskosten alleen van Gaslicht.com (€ 6,49 per maand met btw).":
    "Fixed supply costs only from Gaslicht.com (€ 6.49 per month including VAT).",
  "Bij vast komen de bedragen alleen van Keuze.nl, dat zelf twee verschillende terugleververgoedingen noemt (€ 0,15156 en € 0,060). Oxxio prijst vast aan voor huizen zonder zonnepanelen.":
    "With fixed, the amounts only come from Keuze.nl, which itself mentions two different export tariffs (€ 0.15156 and € 0.060). Oxxio recommends fixed for homes without solar panels.",

  // Powerpeers
  "Powerpeers Helemaal Dynamisch: de kwartierprijs op de beurs (EPEX NL Day Ahead) plus een inkoopvergoeding, daarbovenop energiebelasting en btw. Powerpeers noemt € 0,01 inkoopvergoeding, zonder te zeggen of dat met of zonder btw is.":
    "Powerpeers Helemaal Dynamisch: the quarter-hour price on the exchange (EPEX NL Day Ahead) plus a purchasing fee, with energy tax and VAT on top. Powerpeers mentions a € 0.01 purchasing fee, without saying whether that includes VAT.",
  "Je krijgt de beursprijs per kwartier zonder btw, min een verkoopvergoeding met btw over elke teruggeleverde kWh, ook gesaldeerde; volgens Keuze.nl € 0,01. Geen terugleverkosten. Van 2027 tot 2030 per kwartier minstens 50% van beursprijs plus inkoopvergoeding; het maandtotaal gaat niet onder € 0.":
    "You get the exchange price per quarter hour excluding VAT, minus a selling fee including VAT on every exported kWh, netted ones too; according to Keuze.nl € 0.01. No export costs. From 2027 to 2030 per quarter hour at least 50% of the exchange price plus purchasing fee; the monthly total does not go below € 0.",
  "Vast (voorwaarden 1 augustus 2026): terugleverkosten per teruggeleverde kWh, het bedrag staat in je contract. Oudere vaste contracten kunnen nog de schalen per jaar hebben (tabel 'versie 24 december 2025', € 0 tot 999 kWh).":
    "Fixed (terms 1 August 2026): export costs per exported kWh, the amount is in your contract. Older fixed contracts may still have the bands per year (table 'version 24 December 2025', € 0 up to 999 kWh).",
  "Tot 2027 vaste terugleverkosten in 40 schalen per jaar, € 0 tot 999 kWh (tabel 'versie 24 december 2025'); vanaf 2027 per kWh. De terugleververgoeding na salderen staat in je contract.":
    "Until 2027 fixed export costs in 40 bands per year, € 0 up to 999 kWh (table 'version 24 December 2025'); from 2027 per kWh. The export tariff after net metering is in your contract.",
  "Gas vast, ook als Half Dynamisch: dynamische stroom met een vaste gasprijs.":
    "Fixed gas, also as Half Dynamisch: dynamic electricity with a fixed gas price.",
  "Gas variabel (Maandelijks Wisselend).": "Variable gas (Maandelijks Wisselend).",
  "Inkoopvergoeding niet ingevuld: Powerpeers zegt niet of € 0,01 met of zonder btw is; Gaslicht.com zegt met btw, Energievergelijk.nl noemde in juni € 0,0085.":
    "Purchasing fee not filled in: Powerpeers does not say whether € 0.01 includes VAT; Gaslicht.com says including VAT, Energievergelijk.nl mentioned € 0.0085 in June.",
  "Verkoopvergoeding (€ 0,01) alleen van Keuze.nl; daarom niet ingevuld.":
    "Selling fee (€ 0.01) only from Keuze.nl; so not filled in.",
  "Vaste kosten stroom alleen van Gaslicht.com (€ 6,26 per maand met btw).":
    "Fixed electricity costs only from Gaslicht.com (€ 6.26 per month including VAT).",
  "Terugleverkosten per kWh bij vast en bij variabel vanaf 2027: bedrag niet gevonden.":
    "Export costs per kWh with fixed and with variable from 2027: amount not found.",

  // Pure Energie
  "Pure Energie: bij netto levering in een tariefperiode betaal je de beursprijs plus inkoopvergoeding, met btw; de energiebelasting komt erbovenop. Pure Energie noemt geen bedrag; volgens Keuze.nl € 0,01799 per kWh.":
    "Pure Energie: with net supply in a tariff period you pay the exchange price plus purchasing fee, including VAT; the energy tax comes on top. Pure Energie does not state an amount; according to Keuze.nl € 0.01799 per kWh.",
  "Per tariefperiode (nu per uur) verrekend: bij netto teruglevering de beursprijs zonder btw min een verkoopvergoeding per kWh (volgens Keuze.nl € 0,01499). Geen terugleverbijdrage bij dynamisch. De energiebelasting wordt tot 2027 op jaarbasis gesaldeerd.":
    "Settled per tariff period (currently per hour): with net export the exchange price excluding VAT minus a selling fee per kWh (according to Keuze.nl € 0.01499). No export contribution with dynamic. Until 2027 the energy tax is netted on an annual basis.",
  "Contract afgesloten na 1 april 2026: terugleverkosten per kWh, het bedrag staat in je contract (volgens Keuze.nl € 0,139). Daarvoor: een terugleverbijdrage in schalen, per maand in het termijnbedrag. Netto teruglevering heeft 0% btw.":
    "Contract signed after 1 April 2026: export costs per kWh, the amount is in your contract (according to Keuze.nl € 0.139). Before that: an export contribution in bands, per month in the instalment amount. Net export has 0% VAT.",
  "Contract afgesloten na 1 april 2026: terugleverkosten per kWh, het bedrag staat in je contract. Daarvoor: een terugleverbijdrage in schalen, per maand in het termijnbedrag. Netto teruglevering heeft 0% btw; normaal en dal worden apart gesaldeerd.":
    "Contract signed after 1 April 2026: export costs per kWh, the amount is in your contract. Before that: an export contribution in bands, per month in the instalment amount. Net export has 0% VAT; normal and off-peak are netted separately.",
  "Gas vast, ook als Hybride: dynamische stroom met een vast tarief voor gas.":
    "Fixed gas, also as Hybride: dynamic electricity with a fixed rate for gas.",
  "Alle dynamische bedragen (inkoopvergoeding € 0,01799, verkoopvergoeding € 0,01499, abonnement € 12,10) komen alleen van Keuze.nl, zonder btw-vermelding.":
    "All dynamic amounts (purchasing fee € 0.01799, selling fee € 0.01499, subscription € 12.10) only come from Keuze.nl, without mention of VAT.",
  "Uur of kwartier: de website zegt uur, de voorwaarden laten 'ieder uur of ieder kwartier' open.":
    "Hour or quarter hour: the website says hour, the terms leave 'every hour or every quarter hour' open.",
  "Terugleverkosten per kWh voor contracten na 1 april 2026: Keuze.nl noemt € 0,139, niet bevestigd.":
    "Export costs per kWh for contracts after 1 April 2026: Keuze.nl mentions € 0.139, not confirmed.",
  "Terugleververgoeding bij vast en variabel: Keuze.nl spreekt zichzelf tegen (€ 0,11 tegenover € 0,060).":
    "Export tariff with fixed and variable: Keuze.nl contradicts itself (€ 0.11 against € 0.060).",
  "De core-integratie Pure Energie is voor hun energiemeter en geeft geen prijzen.":
    "The Pure Energie core integration is for their energy meter and gives no prices.",

  // SamSam Energie
  "SamSam levert via EnergyZero (en voor een deel via Kikker Energie). Bovenop de kale uurprijs komen 21% btw, een inkoopvergoeding van € 0,021118 per kWh met btw (de FAQ zegt € 0,02118) en de energiebelasting. Vaste leveringskosten € 7,99 per maand per aansluiting.":
    "SamSam supplies through EnergyZero (and partly through Kikker Energie). On top of the bare hourly price come 21% VAT, a purchasing fee of € 0.021118 per kWh including VAT (the FAQ says € 0.02118) and the energy tax. Fixed supply costs € 7.99 per month per connection.",
  "Je krijgt de marktprijs voor elke teruggeleverde kWh; binnen salderen streep je per uur weg tegen de prijs met btw, de energiebelasting op jaarbasis. Een verkoopvergoeding of terugleverkosten noemt SamSam niet.":
    "You get the market price for every exported kWh; within net metering you net per hour against the price including VAT, the energy tax on an annual basis. SamSam does not mention a selling fee or export costs.",
  "Gas dynamisch, prijs per dag, met een inkoopvergoeding van € 0,08275 per m³ met btw.":
    "Dynamic gas, price per day, with a purchasing fee of € 0.08275 per m³ including VAT.",
  "Inkoopvergoeding niet ingevuld: de site noemt € 0,021118 met btw, de FAQ € 0,02118.":
    "Purchasing fee not filled in: the site mentions € 0.021118 including VAT, the FAQ € 0.02118.",
  "Uur of kwartier: SamSam zegt uur, EnergyZero rekent volgens een nieuwsbericht sinds 2026 per kwartier.":
    "Hour or quarter hour: SamSam says hour, according to a news item EnergyZero has charged per quarter hour since 2026.",
  "Of de vaste kosten met of zonder btw zijn.": "Whether the fixed costs include VAT.",
  "Verkoopvergoeding of terugleverkosten: niet genoemd, dus onbekend of ze er zijn.":
    "Selling fee or export costs: not mentioned, so it is unknown whether there are any.",
  "Home Assistant verwijst voor SamSam naar de core-integratie EnergyZero; die geeft een all-in prijs zonder de inkoopvergoeding van SamSam.":
    "For SamSam, Home Assistant refers to the EnergyZero core integration; it gives an all-in price without the SamSam purchasing fee.",

  // Shave Energy
  "Shave Energy is een handelsnaam van OpenSource Energie en levert op diens vergunning. Leveringstarief zonder btw = EPEX-kwartierprijs + inkoopvergoeding (bij groene stroom ook garanties van oorsprong), vermeerderd met energiebelasting en btw. De prijswidget op de site rekent met € 0,02 zonder btw. Wie een batterij of laadpaal laat sturen, moet dat vooraf melden (SMART-contract).":
    "Shave Energy is a trade name of OpenSource Energie and supplies under its licence. Supply rate excluding VAT = EPEX quarter-hour price + purchasing fee (for green electricity also guarantees of origin), plus energy tax and VAT. The price widget on the site uses € 0.02 excluding VAT. If you have a battery or charger controlled, you must report that in advance (SMART contract).",
  "Inkoopvergoeding niet ingevuld: de prijswidget geeft € 0,02 zonder btw voor elk merk, dus misschien niet het bedrag van Shave; een vergelijker noemde op 10-12-2025 € 0,0303.":
    "Purchasing fee not filled in: the price widget gives € 0.02 excluding VAT for every brand, so perhaps not the Shave amount; a comparison site mentioned € 0.0303 on 10-12-2025.",
  "Vaste leveringskosten (€ 6,05 per maand) alleen van een vergelijker, zonder btw-vermelding.":
    "Fixed supply costs (€ 6.05 per month) only from a comparison site, without mention of VAT.",
  "Bedrag en richting van de vergoeding voor afhandeling bij teruglevering.":
    "Amount and direction of the handling fee on export.",
  "Negatieve prijzen en de regeling na 2027: niet gevonden.":
    "Negative prices and the arrangement after 2027: not found.",

  // Tibber
  "Tibber: de kwartierprijs zonder btw is de EPEX Day Ahead-prijs plus een inkoopvergoeding van € 0,018 per kWh, verhoogd met energiebelasting en btw. Tibber zegt niet of die € 0,018 met of zonder btw is. Vaste kosten € 6,99 per maand voor stroom, sinds 1 september 2026.":
    "Tibber: the quarter-hour price excluding VAT is the EPEX Day Ahead price plus a purchasing fee of € 0.018 per kWh, increased by energy tax and VAT. Tibber does not say whether that € 0.018 includes VAT. Fixed costs € 6.99 per month for electricity, since 1 September 2026.",
  "Je krijgt de gewogen gemiddelde EPEX-kwartierprijs, min een verkoopvergoeding van € 0,018 per kWh met btw (sinds 1 september 2026). Tot 2027 wordt de energiebelasting op jaarbasis gesaldeerd.":
    "You get the weighted average EPEX quarter-hour price, minus a selling fee of € 0.018 per kWh including VAT (since 1 September 2026). Until 2027 the energy tax is netted on an annual basis.",
  "Alleen het wettelijke modelcontract 1 jaar vast (vanaf 1 april 2026), met afschrikprijzen: terugleverkosten € 0,10 per kWh en een terugleververgoeding van € 0,12 per kWh over overproductie op jaarbasis, met btw.":
    "Only the statutory 1 year fixed model contract (from 1 April 2026), with deterrent prices: export costs € 0.10 per kWh and an export tariff of € 0.12 per kWh on overproduction on an annual basis, including VAT.",
  "Alleen het wettelijke modelcontract variabel, met afschrikprijzen: een terugleververgoeding van € 0,01 per kWh over overproductie op jaarbasis, met btw.":
    "Only the statutory variable model contract, with deterrent prices: an export tariff of € 0.01 per kWh on overproduction on an annual basis, including VAT.",
  "Gas dynamisch, prijs per dag; vaste kosten € 5,99 per maand voor gas.":
    "Dynamic gas, price per day; fixed costs € 5.99 per month for gas.",
  "Of de inkoopvergoeding (€ 0,018) en de vaste kosten (€ 6,99) met of zonder btw zijn, zegt Tibber niet; daarom geen opslag ingevuld.":
    "Tibber does not say whether the purchasing fee (€ 0.018) and the fixed costs (€ 6.99) include VAT; so no markup filled in.",
  "Verkoopvergoeding niet ingevuld: Tibber noemt hem met btw, maar zegt niet of de kwartierprijs bij teruglevering met of zonder btw wordt vergoed. Keuze.nl noemt nog het oude bedrag van € 0,0248.":
    "Selling fee not filled in: Tibber states it including VAT, but does not say whether the quarter-hour price for export is paid with or without VAT. Keuze.nl still mentions the old amount of € 0.0248.",
  "Wat er bij een negatieve prijs met teruglevering gebeurt, en wat teruglevering boven je jaarverbruik tot 2027 krijgt: niet beschreven.":
    "What happens with export at a negative price, and what export above your annual consumption gets until 2027: not described.",
  "De core-integratie Tibber geeft de all-in prijs als sensor.<huisnaam>_electricity_price; die naam hangt van je huis af en staat hier daarom niet bij. Of die prijs precies die van de app is, is niet nagerekend.":
    "The Tibber core integration gives the all-in price as sensor.<homename>_electricity_price; that name depends on your home and is therefore not listed here. Whether that price is exactly the one in the app has not been checked.",

  // UnitedConsumers
  "Terugleverkosten een vast tarief per teruggeleverde kWh, op de jaarnota (volgens Keuze.nl 15,4 cent). Terugleververgoeding boven salderen zonder btw en energiebelasting; volgens Keuze.nl € 0,17411 bij 1 jaar en € 0,14171 bij 3 jaar vast. De afgesproken bedragen blijven na 2027 gelijk zolang je contract loopt.":
    "Export costs are a fixed rate per exported kWh, on the annual statement (according to Keuze.nl 15.4 cents). Export tariff above net metering excluding VAT and energy tax; according to Keuze.nl € 0.17411 with 1 year and € 0.14171 with 3 years fixed. The agreed amounts stay the same after 2027 as long as your contract runs.",
  "Terugleverkosten een tarief per teruggeleverde kWh, op de jaarnota; tarieven kunnen op 1 januari, 1 april, 1 juli en 1 oktober wijzigen. De bedragen staan in Mijn UnitedConsumers.":
    "Export costs are a rate per exported kWh, on the annual statement; rates can change on 1 January, 1 April, 1 July and 1 October. The amounts are in Mijn UnitedConsumers.",
  "Terugleverkosten en terugleververgoeding komen alleen van Keuze.nl; UnitedConsumers publiceert ze niet openbaar.":
    "Export costs and export tariff only come from Keuze.nl; UnitedConsumers does not publish them.",
  "Terugleververgoeding bij variabel: niet gevonden.": "Export tariff with variable: not found.",

  // Vandebron
  "Vandebron: je betaalt de marktprijs van het uur (het gemiddelde van vier kwartieren), met energiebelasting en btw, plus een inkoopvergoeding. Vandebron noemt geen bedrag; Keuze.nl noemt € 0,02208, Energievergelijk.nl eerder € 0,0257.":
    "Vandebron: you pay the market price of the hour (the average of four quarter hours), with energy tax and VAT, plus a purchasing fee. Vandebron does not state an amount; Keuze.nl mentions € 0.02208, Energievergelijk.nl earlier € 0.0257.",
  "Tot je jaarverbruik krijg je de marktprijs met energiebelasting en btw plus de inkoopvergoeding (salderen per uur). Boven die grens alleen de marktprijs zonder energiebelasting en btw, min een verkoopvergoeding (volgens Keuze.nl € 0,01361). Geen vaste terugleverkosten.":
    "Up to your annual consumption you get the market price with energy tax and VAT plus the purchasing fee (net metering per hour). Above that limit only the market price without energy tax and VAT, minus a selling fee (according to Keuze.nl € 0.01361). No fixed export costs.",
  "Terugleverkosten in schalen of per kWh, afhankelijk van je contract: contracten van na 15 juli 2024 hebben 51 schalen, oudere 6. De tabel staat in je contract. De terugleververgoeding na salderen staat ook in je contract; vanaf 2027 minstens 50% van het kale leveringstarief.":
    "Export costs in bands or per kWh, depending on your contract: contracts from after 15 July 2024 have 51 bands, older ones 6. The table is in your contract. The export tariff after net metering is also in your contract; from 2027 at least 50% of the bare supply rate.",
  "Terugleverkosten in schalen of per kWh, afhankelijk van je contract; de tabel en de terugleververgoeding na salderen staan in je contract.":
    "Export costs in bands or per kWh, depending on your contract; the table and the export tariff after net metering are in your contract.",
  "Inkoopvergoeding niet ingevuld: Keuze.nl € 0,02208 (18-10-2026) tegen Energievergelijk.nl € 0,0257 (30-06-2026), allebei zonder btw-vermelding.":
    "Purchasing fee not filled in: Keuze.nl € 0.02208 (18-10-2026) against Energievergelijk.nl € 0.0257 (30-06-2026), both without mention of VAT.",
  "Verkoopvergoeding (€ 0,01361) alleen van Keuze.nl, zonder btw-vermelding.":
    "Selling fee (€ 0.01361) only from Keuze.nl, without mention of VAT.",
  "Vaste kosten: alleen € 14 per maand voor stroom en gas samen gevonden.":
    "Fixed costs: only € 14 per month for electricity and gas together was found.",
  "Terugleverkosten bij vast en variabel: de schalen bij Overstappen.nl zijn van mei 2025, Keuze.nl noemt 15,0 cent en ook € 0,053 per kWh.":
    "Export costs with fixed and variable: the bands at Overstappen.nl date from May 2025, Keuze.nl mentions 15.0 cents and also € 0.053 per kWh.",

  // Vattenfall
  "Vattenfall FlexPrijs: de beursprijs per uur (het gemiddelde van de vier EPEX-kwartierprijzen) plus inkoopvergoeding, daarbovenop energiebelasting en btw. Vattenfall publiceert de inkoopvergoeding niet openbaar; volgens Keuze.nl € 0,0255 per kWh en vaste kosten € 7,95 per maand, zonder btw-vermelding.":
    "Vattenfall FlexPrijs: the exchange price per hour (the average of the four EPEX quarter-hour prices) plus purchasing fee, with energy tax and VAT on top. Vattenfall does not publish the purchasing fee; according to Keuze.nl € 0.0255 per kWh and fixed costs € 7.95 per month, without mention of VAT.",
  "Je krijgt de beursprijs van het uur zonder btw. De verkoopvergoeding (met btw, over elke teruggeleverde kWh) is volgens Vattenfall nu € 0. Tot 2027 gesaldeerd op volume; een negatief netto overschot wordt € 0. Van 2027 tot 2030 per uur minstens 50% van beursprijs plus inkoopvergoeding. Geen vaste terugleverkosten.":
    "You get the exchange price of the hour excluding VAT. According to Vattenfall the selling fee (including VAT, on every exported kWh) is currently € 0. Until 2027 netted by volume; a negative net surplus becomes € 0. From 2027 to 2030 per hour at least 50% of the exchange price plus purchasing fee. No fixed export costs.",
  "Tot 2027 vaste terugleverkosten per schaal, naar je totale teruglevering; onder 500 kWh niets. De tabel staat in je aanbod en in Mijn Vattenfall (Keuze.nl noemt 60 schalen). Vanaf 2027 terugleverkosten per kWh. De terugleververgoeding na salderen staat in je contract. Bij Groen met ZonBonus een bonus per teruggeleverde kWh, tot 10.000 kWh per jaar; het bedrag is niet gevonden.":
    "Until 2027 fixed export costs per band, based on your total export; nothing below 500 kWh. The table is in your offer and in Mijn Vattenfall (Keuze.nl mentions 60 bands). From 2027 export costs per kWh. The export tariff after net metering is in your contract. With Groen met ZonBonus a bonus per exported kWh, up to 10,000 kWh per year; the amount was not found.",
  "Tot 2027 vaste terugleverkosten per schaal, naar je totale teruglevering; onder 500 kWh niets. De tabel staat in je aanbod en in Mijn Vattenfall. Vanaf 2027 terugleverkosten per kWh. De terugleververgoeding na salderen staat in je contract.":
    "Until 2027 fixed export costs per band, based on your total export; nothing below 500 kWh. The table is in your offer and in Mijn Vattenfall. From 2027 export costs per kWh. The export tariff after net metering is in your contract.",
  "Inkoopvergoeding (€ 0,0255) en vaste kosten (€ 7,95 per maand) alleen van Keuze.nl, zonder btw-vermelding; daarom niet ingevuld.":
    "Purchasing fee (€ 0.0255) and fixed costs (€ 7.95 per month) only from Keuze.nl, without mention of VAT; so not filled in.",
  "Verkoopvergoeding niet ingevuld: Vattenfall zegt nu € 0, de leverancierspagina van Keuze.nl noemt € 0,02549.":
    "Selling fee not filled in: Vattenfall currently says € 0, the Keuze.nl supplier page mentions € 0.02549.",
  "De schalen komen alleen van vergelijkers; volgens Overstappen.nl kan Vattenfall de bedragen per week wijzigen.":
    "The bands only come from comparison sites; according to Overstappen.nl Vattenfall can change the amounts every week.",
  "Terugleverkosten per kWh vanaf 2027, de terugleververgoeding bij vast en variabel, en het bedrag van de ZonBonus: niet gevonden.":
    "Export costs per kWh from 2027, the export tariff with fixed and variable, and the amount of the ZonBonus: not found.",

  // Ventum
  "Ventum: de kale marktprijs per uur, met daarop energiebelasting en btw. Een opslag per kWh en de vaste kosten staan alleen in je persoonlijke aanbod.":
    "Ventum: the bare market price per hour, with energy tax and VAT on top. A markup per kWh and the fixed costs are only in your personal offer.",
  "Met zonnepanelen reken je bij dynamisch je teruglevering per uur af. Tegen welke prijs, en hoe salderen werkt, legt Ventum volgens de site later uit.":
    "With solar panels and dynamic, your export is settled per hour. According to the site, Ventum will explain later at what price, and how net metering works.",
  "Alleen het wettelijke modelcontract: terugleverkosten € 0,00 per kWh met btw, en een teruglevertarief van € 0,05 per kWh voor wat na salderen overblijft. Vastrecht € 145,20 per jaar met btw.":
    "Only the statutory model contract: export costs € 0.00 per kWh including VAT, and an export rate of € 0.05 per kWh for what is left after net metering. Standing charge € 145.20 per year including VAT.",
  "Alleen het wettelijke modelcontract: terugleverkosten € 0,00 per kWh met btw, en een teruglevertarief van € 0,05 per kWh voor wat na salderen overblijft. Vastrecht € 72,60 per jaar met btw; tarieven kunnen op 1 januari, 1 april, 1 juli en 1 oktober wijzigen.":
    "Only the statutory model contract: export costs € 0.00 per kWh including VAT, and an export rate of € 0.05 per kWh for what is left after net metering. Standing charge € 72.60 per year including VAT; rates can change on 1 January, 1 April, 1 July and 1 October.",
  "Opslag per kWh en vaste leveringskosten van het dynamische contract staan alleen in het persoonlijke aanbod.":
    "Markup per kWh and fixed supply costs of the dynamic contract are only in the personal offer.",
  "Teruglevering bij dynamisch: niet tegen welke prijs, en niets over terugleverkosten, negatieve prijzen of salderen.":
    "Export with dynamic: not at what price, and nothing about export costs, negative prices or net metering.",
  "Teruglevertarief van het modelcontract (€ 0,05): bij de regel zelf staat niet of het met of zonder btw is; daarom niet ingevuld.":
    "Export rate of the model contract (€ 0.05): the line itself does not say whether it includes VAT; so not filled in.",
  "Of 'per uur' het uurgemiddelde van de kwartierprijzen is, staat er niet.":
    "It does not say whether 'per hour' is the hourly average of the quarter-hour prices.",

  // Zonopnaam Energie (voorheen Vrijopnaam)
  "Zonopnaam Energie (tot 22 juni 2026 Vrijopnaam): (EPEX-uurprijs + inkoopvergoeding + energiebelasting) × 1,21. Inkoopvergoeding € 0,0165 zonder btw (tariefblad oktober 2026). Vaste leveringskosten € 0,263 per dag met btw.":
    "Zonopnaam Energie (Vrijopnaam until 22 June 2026): (EPEX hourly price + purchasing fee + energy tax) × 1.21. Purchasing fee € 0.0165 excluding VAT (tariff sheet October 2026). Fixed supply costs € 0.263 per day including VAT.",
  "Met eigen zonnepanelen kan dynamisch (nog) niet: levert je aansluiting terug, dan wordt het contract omgezet naar variabel.":
    "Dynamic is not possible (yet) with your own solar panels: if your connection exports, the contract is switched to variable.",
  "Terugleverkosten per kWh over alle teruglevering, met btw, en een terugleververgoeding per kWh; bij een vast contract geldt het tariefblad van de dag van aanmelden (oktober 2026: allebei € 0,10). Tot 2027 krijg je de vergoeding alleen voor wat na salderen overblijft.":
    "Export costs per kWh on all export, including VAT, and an export tariff per kWh; with a fixed contract the tariff sheet of the day you signed up applies (October 2026: both € 0.10). Until 2027 you only get the tariff for what is left after net metering.",
  "Variabel energiezuinig (tariefblad oktober 2026): terugleverkosten € 0,10 per kWh met btw over alle teruglevering, en een terugleververgoeding van € 0,10 per kWh voor wat na salderen overblijft.":
    "Variabel energiezuinig (tariff sheet October 2026): export costs € 0.10 per kWh including VAT on all export, and an export tariff of € 0.10 per kWh for what is left after net metering.",
  "Gasprijs per dag (TTF day-ahead, bepaald om 06:00) + inkoopvergoeding € 0,066 per m³ zonder btw + energiebelasting, met 21% btw.":
    "Gas price per day (TTF day-ahead, set at 06:00) + purchasing fee € 0.066 per m³ excluding VAT + energy tax, with 21% VAT.",
  "Gas vast; de prijs staat op het tariefblad.": "Fixed gas; the price is on the tariff sheet.",
  "Gas variabel; de prijs staat op het tariefblad.": "Variable gas; the price is on the tariff sheet.",
  "Terugleverkosten en vergoeding bij variabel niet ingevuld: het variabele tariefblad van oktober 2026 zegt € 0,10 en € 0,10, het dynamische tariefblad noemt voor hetzelfde variabele contract nog € 0,152 en € 0,134.":
    "Export costs and tariff with variable not filled in: the variable tariff sheet of October 2026 says € 0.10 and € 0.10, the dynamic tariff sheet still mentions € 0.152 and € 0.134 for the same variable contract.",
  "Bij vast hangen de bedragen af van de maand van aanmelden (augustus € 0,089, september € 0,078, oktober € 0,10).":
    "With fixed the amounts depend on the month you signed up (August € 0.089, September € 0.078, October € 0.10).",
  "Of de terugleververgoeding met of zonder btw is, staat op geen tariefblad.":
    "No tariff sheet says whether the export tariff includes VAT.",
  "Hoe Zonopnaam van vier kwartierprijzen één uurprijs maakt, staat er niet.":
    "It does not say how Zonopnaam turns four quarter-hour prices into one hourly price.",
  "De HACS-integratie van groninge01 geeft de prijs die je in de app hebt gekozen (all-in, Marktprijs+ of Marktprijs) en heeft geen vaste entiteitnaam; daarom geen sensor.":
    "The HACS integration by groninge01 gives the price you chose in the app (all-in, Marktprijs+ or Marktprijs) and has no fixed entity name; so no sensor.",
};
