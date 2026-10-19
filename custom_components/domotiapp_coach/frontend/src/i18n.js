/**
 * De taal van het paneel (v0.139.0).
 *
 * De eigenaar op 19-10-2026: "ik wil ook dat het hele coach in het engels ingesteld kan
 * worden". Eén taal per installatie: Installatie, Taal (`installation.language`):
 * automatisch (de taal van Home Assistant), Nederlands of English.
 *
 * Het Nederlands blijft in de bron staan en is de sleutel: `t("Opgeslagen")`. In het
 * Engels zoekt `t` de zin op in `EN` (i18n/en.js); wat daar (nog) niet staat blijft
 * Nederlands. Een waarde in de zin gaat tussen accolades: `t("{n} beurten", { n })`. Zo
 * blijft elke proef die Nederlandse tekst narekent gelden, en is een ontbrekende vertaling
 * te vinden met een zoektocht naar `t(` in de bron (proef "elke zin heeft een vertaling" in
 * test_rapport.mjs).
 *
 * Alleen wat iemand leest. Niet: tekst die de coach schrijft (de redenen en meldingen,
 * stap 2), tekst waarmee gerekend of vergeleken wordt, en namen die de bewoner zelf koos.
 */

import { EN } from "./i18n/en.js";

let taal_ = "nl";

/** De taal van nu: "nl" of "en". */
export const taal = () => taal_;

/** De notatie van getallen en datums bij de taal. Engels als in Groot-Brittannië: 24 uur. */
export const locale = () => (taal_ === "en" ? "en-GB" : "nl-NL");

/**
 * De taal uit de instelling, of bij automatisch uit die van Home Assistant. Geeft true
 * als hij veranderde.
 */
export function kiesTaal(instelling, haTaal) {
  const nieuw = instelling === "nl" || instelling === "en"
    ? instelling
    : String(haTaal ?? "").toLowerCase().startsWith("en") ? "en" : "nl";
  const anders = nieuw !== taal_;
  taal_ = nieuw;
  return anders;
}

/** Een zin in de taal van nu, met de waarden tussen accolades ingevuld. */
export function t(nl, waarden) {
  const zin = taal_ === "en" ? (EN[nl] ?? nl) : nl;
  if (!waarden) return zin;
  return zin.replace(/\{(\w+)\}/g, (heel, naam) => (naam in waarden ? String(waarden[naam]) : heel));
}

/**
 * Een naam in een tabel die bij het laden van de module al vastligt (een soort apparaat,
 * een tabblad): `nt` laat hem Nederlands en merkt hem voor de proef; vertaald wordt hij waar
 * hij getoond wordt, met `t(item.label)`. Want bij het laden is de taal nog niet bekend.
 */
export const nt = (nl) => nl;

/** Enkelvoud of meervoud: `tn(n, "{n} beurt", "{n} beurten")`. */
export const tn = (n, een, meer, waarden = {}) => t(Number(n) === 1 ? een : meer, { n, ...waarden });

/** Een getal met de decimalen en het scheidingsteken van de taal: 1,5 of 1.5. */
export function getal(waarde, decimalen = 1) {
  const n = Number(waarde);
  if (!Number.isFinite(n)) return "";
  // Zonder punt of komma bij duizendtallen, zoals het paneel getallen schreef met
  // replace(".", ","): het Nederlands blijft zo letterlijk wat het was.
  return n.toLocaleString(locale(), { minimumFractionDigits: decimalen, maximumFractionDigits: decimalen, useGrouping: false });
}

/** Een datum of tijd in de notatie van de taal, met dezelfde opties als toLocaleDateString. */
export const datum = (d, opties) => new Date(d).toLocaleDateString(locale(), opties);
export const tijd = (d, opties) => new Date(d).toLocaleTimeString(locale(), opties);
