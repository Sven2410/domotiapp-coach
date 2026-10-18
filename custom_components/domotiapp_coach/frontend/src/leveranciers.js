/**
 * De energieleveranciers van Nederland en hoe hun prijs is opgebouwd (v0.129.0).
 *
 * De eigenaar op 18-10-2026: "ik wil dat je alle leveranciers uitzoekt en niet
 * alleen Zonneplan en Frank. Alles moet zo gedetailleerd mogelijk en de klant en
 * de installateur geven de klap op de vuurpijl door te zeggen ja dit klopt.
 * Later achteraf wel nog kunnen aanpassen." En: "ik laat de coach alles vooraf
 * invullen en de eindgebruiker moet de Ja-klap geven en het bevestigen."
 *
 * Elk bedrag hier komt van de site, de tarievenkaart of de voorwaarden van de
 * leverancier zelf (of, waar dat zo staat, van een vergelijker), met de bron en
 * de datum waarop het is nagekeken. Het is een voorstel: kiezen vult de velden
 * van Contract, en wat er daarna staat is van de klant. De coach rekent alleen
 * met die velden, nooit met deze lijst. De controle bij Contract
 * (`prijsopbouw.controleer`) legt de velden elk uur naast de all-in sensor, dus
 * een bedrag dat hier verouderd is valt daar op.
 *
 * Bedragen per kWh in `velden` staan zoals de coach ze leest: de opslag zonder
 * btw (`supplier_markup`), de rest zoals de leverancier ze uitbetaalt of rekent.
 */

/**
 * Energiebelasting per kalenderjaar, zonder btw, eerste schijf (tot 10.000 kWh
 * stroom, tot 1.000 m³ gas). Verandert elk jaar op 1 januari.
 */
import { LEVERANCIERS_DATA } from "./leveranciers-data.js";

const BELASTINGDIENST = "https://www.belastingdienst.nl/wps/wcm/connect/bldcontentnl/belastingdienst/zakelijk/overige_belastingen/belastingen_op_milieugrondslag/energiebelasting/";
export const BELASTING = {
  2024: { stroom: 0.1088, gas: 0.58301, bron: BELASTINGDIENST },
  2025: { stroom: 0.10154, gas: 0.57816, bron: BELASTINGDIENST },
  2026: { stroom: 0.09161, gas: 0.60066, bron: BELASTINGDIENST },
  // Voorlopig: de wet noemt 0,08579 en 0,60066 in het prijspeil van 2026; per
  // 1 januari komt daar de tabelcorrectie van 1,026 overheen (Belastingplan
  // 2027), en de Fiscale sleuteltabel 2027 noemt 8,80 en 61,63 cent. Definitief
  // pas met de regeling van december; de controle bij Contract ziet het als
  // het anders uitvalt.
  2027: {
    stroom: 0.08802,
    gas: 0.61628,
    voorlopig: true,
    bron: "https://www.rijksoverheid.nl/site/binaries/site-content/collections/documents/2026/09/15/fiscale-sleuteltabel-2027/fiscale-sleuteltabel-2027.pdf",
  },
};

/** De energiebelasting op stroom van dat jaar, of null als die niet in de lijst staat. */
export function belastingStroom(jaar = new Date().getFullYear()) {
  return BELASTING[jaar]?.stroom ?? null;
}

/** De energiebelasting op gas van dat jaar, of null. */
export function belastingGas(jaar = new Date().getFullYear()) {
  return BELASTING[jaar]?.gas ?? null;
}

/** De soorten contract, zoals Contract ze aanbiedt. */
export const SOORTEN = [
  { key: "fixed", label: "Vast", uitleg: "Eén prijs voor de hele looptijd." },
  { key: "variable", label: "Variabel", uitleg: "De leverancier past de prijs aan, maandelijks opzegbaar." },
  { key: "dynamic", label: "Dynamisch", uitleg: "Per uur of kwartier de marktprijs, maandelijks opzegbaar." },
];

const SLEUTEL = { fixed: "vast", variable: "variabel", dynamic: "dynamisch" };

// Zonneplan staat hier met de hand, als voorbeeld van een volledig nagerekende
// leverancier (het eigen rekenvoorbeeld komt precies uit, en de controle tegen
// hun sensor klopte in de eerste woning tot op een honderdste cent). De rest
// staat in leveranciers-data.js.
const ZONNEPLAN = {
    id: "zonneplan",
    naam: "Zonneplan",
    website: "https://www.zonneplan.nl/energie",
    peildatum: "2026-10-18",
    stroom: {
      dynamisch: {
        interval: "quarter",
        velden: {
          supplier_markup: 0.016529,
          feed_in_costs: 0,
          feed_in_bonus: 0.02,
          feed_in_vat: true,
          netting_full: true,
          feed_in_bonus_percent: 10,
          bonus_daytime: true,
          bonus_base: "market_plus_fee",
        },
        namen: { opslag: "Inkoopvergoeding", vergoeding: "Inkoopvergoeding, terug", bonus: "Zonnebonus", opslagNaBtw: true },
        uitleg: "Je betaalt per kWh (marktprijs per kwartier + energiebelasting) × 1,21, plus € 0,02 inkoopvergoeding met btw. Vaste leveringskosten € 6,25 per maand.",
        terug: "Je krijgt de marktprijs met btw plus de € 0,02 inkoopvergoeding terug, zonder energiebelasting. Overdag, van zonsopkomst tot zonsondergang en als marktprijs + € 0,02 positief is, komt er 10% Zonnebonus bij over (marktprijs + € 0,02), tot 7.500 kWh per jaar. Niet over teruglevering uit de thuisbatterij van Zonneplan. Geen terugleverkosten.",
        bronnen: [
          "https://www.zonneplan.nl/energie/dynamisch-energiecontract",
          "https://www.zonneplan.nl/energie/zonnebonus/",
          "https://www.zonneplan.nl/blog/kwartierprijzen-bij-zonneplan",
        ],
      },
    },
    gas: {},
    ha: { stroom: ["zonneplan_current_electricity_tariff"], gas: ["zonneplan_current_gas_tariff"] },
    onzeker: ["Of de vaste leveringskosten van € 6,25 per maand met of zonder btw zijn, zeggen alleen vergelijkers."],
};

export const LEVERANCIERS = [ZONNEPLAN, ...LEVERANCIERS_DATA];

/** De leverancier met dit id, of null. */
export function leverancier(id) {
  return LEVERANCIERS.find((l) => l.id === id) ?? null;
}

/** Welke soorten stroomcontract (of gascontract) deze leverancier heeft. */
export function soortenVan(id, bron = "stroom") {
  const l = leverancier(id);
  if (!l) return SOORTEN.map((s) => s.key);
  return SOORTEN.map((s) => s.key).filter((k) => l[bron]?.[SLEUTEL[k]]);
}

/** De leveranciers die iets van deze bron leveren, op naam. */
export function leveranciersVoor(bron = "stroom") {
  return LEVERANCIERS.filter((l) => l[bron] && Object.keys(l[bron]).length)
    .sort((a, b) => a.naam.localeCompare(b.naam, "nl"));
}

/**
 * Het voorstel voor een contract: de velden om in te vullen, de woorden voor de
 * opbouw, en waar het vandaan komt. Null als de leverancier dit niet heeft.
 */
export function voorstel(id, soort, bron = "stroom", jaar = new Date().getFullYear()) {
  const l = leverancier(id);
  const deel = l?.[bron]?.[SLEUTEL[soort]];
  if (!deel) return null;
  const velden = { ...(deel.velden ?? {}) };
  if (bron === "stroom" && soort === "dynamic") {
    const eb = belastingStroom(jaar);
    if (eb !== null && velden.energy_tax === undefined) velden.energy_tax = eb;
    if (velden.vat_percent === undefined) velden.vat_percent = 21;
  }
  return {
    leverancier: l.naam,
    interval: deel.interval ?? null,
    velden,
    namen: { ...(deel.namen ?? {}), leverancier: l.naam },
    uitleg: deel.uitleg ?? "",
    terug: deel.terug ?? "",
    bronnen: deel.bronnen ?? [],
    peildatum: l.peildatum,
    onzeker: l.onzeker ?? [],
  };
}

/** De woorden voor de opbouw van deze leverancier (`opbouwHtml` in opbouw.js). */
export function namenVan(id, soort = "dynamic") {
  const v = voorstel(id, soort);
  const l = leverancier(id);
  return v ? v.namen : (l ? { leverancier: l.naam } : {});
}

/**
 * De sensor van deze leverancier in Home Assistant, als die er is: de eerste
 * entiteit die een van de bekende stukken naam heeft.
 */
export function sensorVan(id, staten, bron = "stroom") {
  const stukken = leverancier(id)?.ha?.[bron] ?? [];
  if (!stukken.length || !staten) return null;
  const ids = Object.keys(staten).filter((e) => e.startsWith("sensor."));
  for (const stuk of stukken) {
    const gevonden = ids.find((e) => e.includes(stuk));
    if (gevonden) return gevonden;
  }
  return null;
}

/** Een sensor van de ingebouwde Nord Pool, voor de kale marktprijs. */
export function nordPoolVan(staten) {
  if (!staten) return null;
  return Object.keys(staten).find((e) => e.startsWith("sensor.") && /nord_?pool/.test(e)
    && /(current|huidige)/.test(e)) ?? null;
}
