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
 *   de batterij   wat ze opleverde: pas als ze ontlaadt, min wat die stroom
 *                 kostte (`Voorraad` in batterij.py, sinds v0.107.0), per dag
 *   de zon        wat je panelen opleverden zonder dat iemand iets stuurde
 *
 * Niets wordt twee keer geteld: wat een apparaat uit de thuisbatterij kreeg telt
 * bij de beurt als netstroom (zie `_herkomst_bij` in coach.py), en de winst
 * daarvan staat in het kasboek van de batterij.
 *
 * Tot v0.101.2 was de zon de rest: bespaard min de batterij min de coach. Maar
 * de meters zien de batterij niet, dus wat zij 's nachts aan het huis gaf zat
 * niet in bespaard en werd toch van de zon afgetrokken: bij de eigenaar op 29-09-2026 om
 * 10:00 "Door je zon € -0,56" naast "Door je thuisbatterij € 0,60". Nu wordt de
 * zon zelf uitgerekend (de eigen zon tegen de inkoopprijs, teruglevering tegen
 * wat die opbracht, min wat de zon die de batterij in ging minder waard was,
 * `zon_in_accu` in batterij.py) en telt het kasboek van de batterij erbij op.
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
 * Wat alle thuisbatterijen samen opleverden in [start, end), en wat er in die
 * periode in ging voor later.
 *
 * `battery_state` in de instellingen houdt per batterij twee dingen per dag bij.
 * Het kasboek (`earned_days`): wat de rekening met de batterij scheelde
 * tegenover zonder, met laden afgerekend op het moment zelf. En wat ze
 * opleverde (`realized_days`, sinds v0.107.0): laden is inkopen, en pas als ze
 * ontlaadt telt wat dat opbracht min wat die stroom kostte (`Voorraad` in
 * batterij.py). Het verschil is wat er die dag aan stroom in de batterij bij
 * kwam, in euro (`voorraad`): positief als er meer in ging dan eruit.
 *
 * Een dag van voor v0.107.0 heeft alleen het kasboek, en telt zoals hij geteld
 * is. Dat kasboek begint pas als de coach de batterij volgt; wat ze daarvoor
 * deed is niet bekend en wordt niet geschat.
 */
export function accuVerdiend(settings, start, end) {
  const van = lokaleDag(start);
  const tot = lokaleDag(end);
  let som = 0;
  let voorraad = 0;
  let dagen = 0;
  for (const rij of settings?.battery_state ?? []) {
    const echt = rij?.realized_days ?? {};
    for (const [dag, bedrag] of Object.entries(rij?.earned_days ?? {})) {
      if (dag >= van && dag < tot) {
        const kasboek = Number(bedrag) || 0;
        const opgeleverd = dag in echt ? Number(echt[dag]) || 0 : kasboek;
        som += opgeleverd;
        voorraad += opgeleverd - kasboek;
        dagen += 1;
      }
    }
  }
  return { euro: som, voorraad, dagen };
}

/**
 * Wat de zon die de thuisbatterijen in ging minder waard was dan zelf gebruikt,
 * in [start, end), zoals de coach het per dag telde (`solar_stored_days`,
 * `zon_in_accu` in batterij.py).
 */
export function accuZon(settings, start, end) {
  const van = lokaleDag(start);
  const tot = lokaleDag(end);
  let som = 0;
  for (const rij of settings?.battery_state ?? []) {
    for (const [dag, bedrag] of Object.entries(rij?.solar_stored_days ?? {})) {
      if (dag >= van && dag < tot) som += Number(bedrag) || 0;
    }
  }
  return { euro: som };
}

/**
 * De hele som voor één periode.
 *
 * @param {object} o
 * @param {{start: Date, own: number, bought: number, sold: number, zonInAccu?: number}[]} o.rijen
 *   de vakken van de periode, zoals Historie ze tekent. `zonInAccu` is de zon
 *   die de batterij in ging in een vak waarover de coach dat nog niet telde
 *   (`huisMetAccu` in views/history.js)
 * @param {(when: Date) => {koop: number|null, terug: number|null}} o.prijs
 * @param {{start: Date, value: number}[]} [o.gas]
 * @param {{start: Date, value: number}[]} [o.water]
 * @param {object} [o.contract]
 * @param {number} [o.accu] wat de thuisbatterij in deze periode opleverde
 * @param {number} [o.accuVoorraad] wat er in deze periode aan stroom in de
 *   batterij bij kwam, in euro (`accuVerdiend`): betaald, en nog niet gebruikt
 * @param {number} [o.accuZon] wat de zon die ze opnam minder waard was, uit de
 *   telling van de coach (`accuZon`)
 * @param {{saved: number, solar_saved: number, wait_saved: number}} [o.coach]
 *   de beurten van deze periode opgeteld (`totalen` in savings.js)
 */
export function balans({ rijen, prijs, gas = [], water = [], contract, accu = 0, accuVoorraad = 0, accuZon = 0, coach = null }) {
  let stroom = 0;
  let terug = 0;
  let eigen = 0;
  let zonInAccu = Number(accuZon) || 0;
  let metTerug = false;
  let onbekend = 0;
  for (const r of rijen ?? []) {
    const p = prijs(r.start);
    if (p.koop === null) {
      onbekend += 1;
      continue;
    }
    stroom += r.bought * p.koop;
    eigen += r.own * p.koop;
    const terugPrijs = p.terug ?? null;
    if (terugPrijs !== null) {
      terug += r.sold * terugPrijs;
      metTerug = true;
    }
    // Van voor de coach het telde: de zon die de batterij in ging, uit het vak zelf.
    zonInAccu += (Number(r.zonInAccu) || 0) * (p.koop - (terugPrijs ?? 0));
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
  // Wat de zon opleverde: de eigen zon tegen de prijs van het net, teruglevering
  // tegen wat die opbracht, min wat de zon in de batterij minder waard was dan
  // zelf gebruikt. Wat de batterij er daarna mee deed staat in haar kasboek.
  const zonWaarde = eigen + terug - zonInAccu;
  const accuEuro = Number(accu) || 0;
  const zon = zonWaarde - coachZon;
  const bespaard = zonWaarde + accuEuro + wachten;
  const uitgegeven = stroom - terug + g.euro + w.euro;
  // Wat er aan stroom in de batterij bij kwam is uitgegeven maar nog niet
  // gebruikt; telt opgeleverd het pas als het eruit gaat, dan hoort het hier
  // van zonder af, anders telt zonder het als verbruik (v0.107.0).
  const voorraad = Number(accuVoorraad) || 0;

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
    voorraad,
    // Wat dezelfde periode gekost had zonder zon, batterij en coach.
    zonder: uitgegeven + bespaard - voorraad,
    onbekend,
  };
}
