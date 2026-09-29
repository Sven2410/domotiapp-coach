/**
 * In geld: wat een periode kostte, wat hij opleverde, en waardoor (v0.101.0).
 *
 * De eigenaar op 28-09-2026: "ik wil op het historie overzicht duidelijk hebben
 * wat ik heb bespaard die dag, totaal uitgegeven en totaal bespaard. Maak een
 * mooi overzicht." En: "stel alles goed op elkaar af." Een terugverdientijd
 * stond er één uitgave bij en is er in v0.101.1 weer uit: de eigenaar op
 * 29-09-2026 kan geen datum in het paneel verdedigen die afwijkt van wat een
 * installateur de klant voorrekende.
 *
 * Eén som voor het scherm en het rapport, zodat die het nooit oneens zijn:
 *
 *   uitgegeven = stroom van het net + gas + water, min wat teruglevering opbracht
 *   bespaard   = wat hetzelfde verbruik gekost had met alles van het net, tegen
 *                de prijs van dat moment, min wat de stroom werkelijk kostte,
 *                plus wat de coach won door op een goedkoper moment te wachten
 *
 * en bespaard in drie delen die samen precies het geheel zijn:
 *
 *   de coach      wat de beurten onder Bespaard bespaarden: de zon die hij naar
 *                 een apparaat stuurde en het wachten op een goedkoper uur
 *   de batterij   haar eigen kasboek (`verdiend` in batterij.py), per dag
 *   de zon        de rest: wat je panelen deden zonder dat iemand iets stuurde
 *
 * Niets wordt twee keer geteld: wat een apparaat uit de thuisbatterij kreeg telt
 * bij de beurt als netstroom (zie `_herkomst_bij` in coach.py), en de winst
 * daarvan staat in het kasboek van de batterij.
 */

import { contractAt } from "./data-source.js";

/**
 * De dag waarop salderen ophoudt. Gelijk aan `NETTING_ENDS` in const.py: de
 * coach en het paneel rekenen dezelfde teruglevering, anders zegt Historie iets
 * anders dan een verslag.
 */
export const SALDEREN_TOT = "2027-01-01";

function lokaleDag(when) {
  const dag = when instanceof Date ? when : new Date(when);
  if (Number.isNaN(dag.getTime())) return "";
  return `${dag.getFullYear()}-${String(dag.getMonth() + 1).padStart(2, "0")}-${String(dag.getDate()).padStart(2, "0")}`;
}

/** Of er op die dag nog gesaldeerd wordt: het vinkje én de datum, zoals `_salderen` in coach.py. */
export function salderen(contract, when) {
  const dag = lokaleDag(when);
  return Boolean(contract?.netting) && dag !== "" && dag < SALDEREN_TOT;
}

/**
 * Wat een kWh op dat moment kost en wat een teruggeleverde opbrengt.
 *
 * Dezelfde regels als `_tariff` en `_prices` in coach.py. Bij salderen streept
 * een teruggeleverde kWh weg tegen een ingekochte: hij is de inkoopprijs waard,
 * min de terugleverkosten, en bij een dynamisch contract ook min de opslag van
 * de leverancier, want die hangt aan de afname. Tot v0.101.0 rekende Historie
 * hier altijd met de terugleververgoeding, en die geldt bij salderen pas boven
 * wat je zelf verbruikt: bij de eigenaar stond "teruglevering leverde" daardoor een
 * factor tien te laag.
 *
 * @param {object} contract de instellingen van het contract
 * @param {{buy: number|null, feedIn: number|null}} rate het huidige tarief (`tariff`)
 * @param {Map<number, number>} prijzen de prijs per vak uit de geschiedenis
 * @param {Date} when het begin van het vak
 * @returns {{koop: number|null, terug: number|null}}
 */
export function prijsOp(contract, rate, prijzen, when) {
  const c = contractAt(contract, when);
  const t = new Date(when).getTime();
  const koop = c.period?.all_in_price > 0 ? c.buy : (prijzen?.get(t) ?? rate?.buy ?? null);
  if (koop === null || koop === undefined) return { koop: null, terug: null };
  if (salderen(contract, when)) {
    if (contract?.type === "dynamic") {
      const d = contract.dynamic ?? {};
      const opslag = (Number(d.supplier_markup) || 0) * (1 + (Number(d.vat_percent) || 0) / 100);
      const kosten = (Number(d.feed_in_costs) || 0) - (Number(d.feed_in_bonus) || 0);
      return { koop, terug: koop - opslag - kosten };
    }
    return { koop, terug: koop - (Number(contract?.fixed?.feed_in_costs) || 0) };
  }
  return { koop, terug: c.feedIn ?? rate?.feedIn ?? null };
}

/**
 * Wat alle thuisbatterijen samen verdienden in [start, end), uit hun kasboek.
 *
 * `battery_state` in de instellingen houdt per batterij `earned_days` bij: per
 * dag wat de rekening met de batterij scheelde tegenover zonder. Dat kasboek
 * begint pas als de coach de batterij volgt; wat ze daarvoor deed is niet
 * bekend en wordt niet geschat.
 */
export function accuVerdiend(settings, start, end) {
  const van = lokaleDag(start);
  const tot = lokaleDag(end);
  let som = 0;
  let dagen = 0;
  for (const rij of settings?.battery_state ?? []) {
    for (const [dag, bedrag] of Object.entries(rij?.earned_days ?? {})) {
      if (dag >= van && dag < tot) {
        som += Number(bedrag) || 0;
        dagen += 1;
      }
    }
  }
  return { euro: som, dagen };
}

/**
 * De hele som voor één periode.
 *
 * @param {object} o
 * @param {{start: Date, own: number, bought: number, sold: number, used: number}[]} o.rijen
 *   de vakken van de periode, zoals Historie ze tekent
 * @param {(when: Date) => {koop: number|null, terug: number|null}} o.prijs
 * @param {{start: Date, value: number}[]} [o.gas]
 * @param {{start: Date, value: number}[]} [o.water]
 * @param {object} [o.contract]
 * @param {number} [o.accu] wat de thuisbatterij in deze periode verdiende
 * @param {{saved: number, solar_saved: number, wait_saved: number}} [o.coach]
 *   de beurten van deze periode opgeteld (`totalen` in savings.js)
 */
export function balans({ rijen, prijs, gas = [], water = [], contract, accu = 0, coach = null }) {
  let stroom = 0;
  let terug = 0;
  let zonder = 0;
  let metTerug = false;
  let onbekend = 0;
  for (const r of rijen ?? []) {
    const p = prijs(r.start);
    if (p.koop === null) {
      onbekend += 1;
      continue;
    }
    stroom += r.bought * p.koop;
    zonder += r.used * p.koop;
    if (p.terug !== null && p.terug !== undefined) {
      terug += r.sold * p.terug;
      metTerug = true;
    }
  }
  const volume = (rijenVan, sleutel) => {
    let euro = 0;
    let met = false;
    for (const r of rijenVan ?? []) {
      const prijsM3 = contractAt(contract, r.start)[sleutel];
      if (prijsM3 === null || prijsM3 === undefined) continue;
      euro += r.value * prijsM3;
      met = true;
    }
    return { euro, met };
  };
  const g = volume(gas, "gas");
  const w = volume(water, "water");

  const coachTotaal = Number(coach?.saved) || 0;
  const coachZon = Number(coach?.solar_saved) || 0;
  const wachten = coachTotaal - coachZon;
  // Wat de zon en de batterij samen deden: het verbruik tegen de prijs van het
  // net, min wat de stroom werkelijk kostte. Gelijk aan eigen zon maal de prijs
  // plus teruglevering maal wat die opbracht.
  const energie = zonder - (stroom - terug);
  const accuEuro = Number(accu) || 0;
  const zon = energie - accuEuro - coachZon;
  const bespaard = energie + wachten;
  const uitgegeven = stroom - terug + g.euro + w.euro;

  return {
    stroom,
    terug,
    metTerug,
    gas: g.euro,
    metGas: g.met,
    water: w.euro,
    metWater: w.met,
    uitgegeven,
    bespaard,
    delen: { zon, accu: accuEuro, coach: coachTotaal },
    // Wat dezelfde periode gekost had zonder zon, batterij en coach.
    zonder: uitgegeven + bespaard,
    onbekend,
  };
}
