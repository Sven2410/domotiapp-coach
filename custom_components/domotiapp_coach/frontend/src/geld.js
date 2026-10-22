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
import { ptPrijsOp } from "./tarifas.js";
import { huisNu, vanHuis } from "./format.js";

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
  // Portugal kent geen salderen (v0.137.0).
  return Boolean(contract?.netting) && contract?.country !== "PT" && dag !== "" && dag < SALDEREN_TOT;
}

/**
 * Wat een extra teruggeleverde kWh aan terugleverkosten kost (v0.135.0), zoals
 * `kosten_per_kwh` in prijsopbouw.py: per kWh over alles (`kwh`), alleen als hij
 * niet wegstreept (`overschot`), of niets per kWh (`schalen`, `geen`).
 */
export function kostenPerKwh(velden, saldeert) {
  const vorm = velden?.feed_in_costs_mode || "kwh";
  if (vorm === "schalen" || vorm === "geen") return 0;
  if (vorm === "overschot" && saldeert) return 0;
  return Number(velden?.feed_in_costs) || 0;
}

/**
 * Het jaarbedrag van de schaal waar `kwh` teruglevering in valt (v0.135.0), zoals
 * `schaal_per_jaar` in prijsopbouw.py. Null zonder tabel.
 */
export function schaalPerJaar(schalen, kwh) {
  const rijen = (schalen ?? [])
    .filter((r) => r && typeof r === "object")
    .map((r) => [Number(r.vanaf) || 0, Number(r.per_jaar) || 0])
    .sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (!rijen.length) return null;
  let bedrag = 0;
  for (const [vanaf, perJaar] of rijen) {
    if (kwh < vanaf) break;
    bedrag = perJaar;
  }
  return bedrag;
}

/**
 * De vergoeding en de kosten per kWh van een vast contract op die dag (v0.134.0),
 * zoals `_teruglevering` in coach.py: vanaf `SALDEREN_TOT` wat het contract voor na
 * salderen zegt, en een leeg veld houdt het bedrag van ervoor. De kosten in de
 * vorm van het contract (v0.135.0, `kostenPerKwh`).
 */
export function vasteTeruglevering(fixed, when, saldeert = false) {
  let vergoeding = Number(fixed?.feed_in_tariff) || 0;
  let kosten = kostenPerKwh(fixed, saldeert);
  const dag = lokaleDag(when);
  const ingevuld = (v) => v !== null && v !== undefined && v !== "";
  if (dag !== "" && dag >= SALDEREN_TOT) {
    if (ingevuld(fixed?.feed_in_tariff_after)) vergoeding = Number(fixed.feed_in_tariff_after) || 0;
    if (ingevuld(fixed?.feed_in_costs_after)) kosten = Number(fixed.feed_in_costs_after) || 0;
  }
  return { vergoeding, kosten };
}

/**
 * Of de coach weet wat teruglevering opbrengt, zoals `_prices` en `_tariff` in
 * coach.py (v0.128.2). Een vast contract heeft een terugleververgoeding, bij
 * salderen volgt hij uit de inkoopprijs, en een zelf opgebouwde prijs heeft de
 * marktprijs al. Alleen een all-in prijs zonder een andere marktprijssensor
 * laat hem open: dezelfde sensor twee keer telt niet. Zonder kan een
 * thuisbatterij niet handelen (`_mag_handelen` in batterij.py).
 */
export function terugleverBekend(contract, when = huisNu()) {
  if (contract?.type !== "dynamic") return true;
  if (salderen(contract, when)) return true;
  const d = contract.dynamic ?? {};
  // Een vaste terugleververgoeding (v0.132.0) is altijd bekend.
  if (d.feed_in_mode === "fixed") return true;
  if (d.source !== "all_in") return Boolean(d.market_entity);
  return Boolean(d.market_entity) && d.market_entity !== d.all_in_entity;
}

/**
 * Zonsopkomst en zonsondergang op die dag, in UTC, of null als de zon niet op
 * of onder gaat (v0.129.0). De vergelijking van de NOAA, zoals `zon_op_onder`
 * in prijsopbouw.py: dezelfde uren voor een bonus die alleen overdag geldt.
 *
 * @param {Date} dag een moment op die dag (UTC telt)
 * @returns {[Date, Date]|null}
 */
export function zonOpOnder(dag, lat, lon) {
  const jaarBegin = Date.UTC(dag.getUTCFullYear(), 0, 1);
  const n = Math.floor((Date.UTC(dag.getUTCFullYear(), dag.getUTCMonth(), dag.getUTCDate()) - jaarBegin) / 86400000) + 1;
  const hoek = (2 * Math.PI / 365) * (n - 1);
  const vereffening = 229.18 * (0.000075 + 0.001868 * Math.cos(hoek) - 0.032077 * Math.sin(hoek)
    - 0.014615 * Math.cos(2 * hoek) - 0.040849 * Math.sin(2 * hoek));
  const declinatie = 0.006918 - 0.399912 * Math.cos(hoek) + 0.070257 * Math.sin(hoek) - 0.006758 * Math.cos(2 * hoek)
    + 0.000907 * Math.sin(2 * hoek) - 0.002697 * Math.cos(3 * hoek) + 0.00148 * Math.sin(3 * hoek);
  const breedte = (lat * Math.PI) / 180;
  const x = Math.cos((90.833 * Math.PI) / 180) / (Math.cos(breedte) * Math.cos(declinatie))
    - Math.tan(breedte) * Math.tan(declinatie);
  if (x < -1 || x > 1) return null;
  const uurhoek = (Math.acos(x) * 180) / Math.PI;
  const middag = 720 - 4 * lon - vereffening;
  const middernacht = Date.UTC(dag.getUTCFullYear(), dag.getUTCMonth(), dag.getUTCDate());
  return [new Date(middernacht + (middag - 4 * uurhoek) * 60000), new Date(middernacht + (middag + 4 * uurhoek) * 60000)];
}

/** Of het midden van [start, einde) tussen zonsopkomst en zonsondergang valt, zoals `overdag` in prijsopbouw.py. */
export function overdag(start, einde, ligging) {
  if (!ligging || !Number.isFinite(ligging.lat) || !Number.isFinite(ligging.lon)) return false;
  const midden = new Date((start.getTime() + einde.getTime()) / 2);
  const zon = zonOpOnder(midden, ligging.lat, ligging.lon);
  return zon !== null && zon[0] <= midden && midden < zon[1];
}

/** De marktprijs voor teruglevering, met of zonder btw, zoals `markt_terug` in prijsopbouw.py. */
export function marktTerug(markt, d) {
  return d?.feed_in_vat ? markt * (1 + (Number(d?.vat_percent) || 0) / 100) : markt;
}

/** De terugleverbonus in procenten, per kWh, zoals `bonus` in prijsopbouw.py. */
export function bonusOp(markt, d, isOverdag) {
  const procent = Number(d?.feed_in_bonus_percent) || 0;
  if (procent <= 0 || (d?.bonus_daytime && !isOverdag)) return 0;
  const basis = marktTerug(markt, d);
  const over = d?.bonus_base === "market_plus_fee" ? basis + (Number(d?.feed_in_bonus) || 0) : basis;
  return over > 0 ? (procent / 100) * over : 0;
}

/**
 * Wat een teruggeleverde kWh opbrengt bij een dynamisch contract, zoals
 * `terug` in prijsopbouw.py (v0.129.0). Met salderen de all-in prijs min de
 * opslag en de kosten, plus de vergoeding; zonder de kale prijs min de kosten
 * plus de vergoeding; en in allebei een bonus in procenten.
 */
export function terugOp(markt, allIn, d, metSalderen, isOverdag) {
  const kosten = kostenPerKwh(d, metSalderen);
  const vergoeding = Number(d?.feed_in_bonus) || 0;
  const opslag = (Number(d?.supplier_markup) || 0) * (1 + (Number(d?.vat_percent) || 0) / 100);
  const extra = markt === null || markt === undefined ? 0 : bonusOp(markt, d, isOverdag);
  if (metSalderen) {
    if (allIn === null || allIn === undefined) return null;
    // De hele all-in prijs terug, ook de opslag, zoals `terug` in prijsopbouw.py (v0.129.1).
    return d?.netting_full ? allIn + extra : allIn - opslag - kosten + vergoeding + extra;
  }
  // Een vaste terugleververgoeding (v0.132.0), zoals `terug` in prijsopbouw.py.
  if (d?.feed_in_mode === "fixed") return (Number(d?.feed_in_fixed) || 0) - kosten;
  return markt === null || markt === undefined ? null : marktTerug(markt, d) - kosten + vergoeding + extra;
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
 * Bij een dynamisch contract (v0.129.0) volgt de kale prijs van het vak uit de
 * all-in prijs en de velden (de som van `inkoop` in prijsopbouw.py
 * achterstevoren), zodat een bonus in procenten en teruglevering zonder
 * salderen per vak kloppen in plaats van met het gemiddelde van vandaag. Dat
 * alleen als de coach de terugleverprijs kent (`terugleverBekend`); de
 * controle bij Contract zegt of die velden kloppen.
 *
 * @param {Date} when het begin van het vak
 * @param {{lat: number, lon: number}} [ligging] waar de woning ligt, voor een bonus die alleen overdag geldt
 * @param {number} [lengte] hoe lang het vak duurt, in ms; standaard een uur
 * @returns {{koop: number|null, terug: number|null}}
 */
/**
 * Het deel van de teruglevering dat in de afrekenperiode van dat moment wegstreept
 * tegen afname (v0.135.0), van `async_afrekening` in coach.py, of null als dat
 * niet bekend is. Dan telt het vinkje: alles gesaldeerd.
 */
export function aandeelOp(afrekening, when) {
  const dag = lokaleDag(when);
  if (!dag) return null;
  for (const p of afrekening?.perioden ?? []) {
    if (p.van <= dag && dag < p.tot) return p.gesaldeerd ?? null;
  }
  return null;
}

/**
 * Wat de schaal van de terugleverkosten kost in [start, end) (v0.135.0): het
 * jaarbedrag per dag, over de dagen van de schaal die al voorbij zijn.
 */
export function schaalKosten(afrekening, start, end, nu = huisNu()) {
  const s = afrekening?.schaal;
  if (!s || !(Number(s.per_dag) > 0)) return 0;
  const van = Math.max(new Date(`${s.van}T00:00:00`).getTime(), new Date(start).getTime());
  const tot = Math.min(new Date(`${s.tot}T00:00:00`).getTime(), new Date(end).getTime(), new Date(nu).getTime());
  return tot > van ? ((tot - van) / 86400000) * Number(s.per_dag) : 0;
}

/**
 * `aandeel` (v0.135.0) is het deel dat in die afrekenperiode wegstreept
 * (`aandeelOp`): met salderen is een teruggeleverde kWh dan voor dat deel de
 * inkoopprijs waard en voor de rest wat er na salderen geldt, naar rato over
 * elke kWh, zoals de jaarafrekening het overschot over de contracten verdeelt.
 * Null of 1 is alles gesaldeerd.
 */
export function prijsOp(contract, rate, prijzen, when, ligging = null, lengte = 3600000, aandeel = null) {
  const c = contractAt(contract, when);
  const t = new Date(when).getTime();
  // Portugal (v0.137.0): de tijdvakken van de ERSE, zoals `_pt_rijen` in coach.py.
  // Historie rekent op de klok van het huis; de tijdvakken willen het echte moment (v0.138.2).
  if (contract?.country === "PT" && !c.period) return ptPrijsOp(contract.pt, vanHuis(new Date(when)), lengte);
  const koop = c.period?.all_in_price > 0 ? c.buy : (prijzen?.get(t) ?? rate?.buy ?? null);
  if (koop === null || koop === undefined) return { koop: null, terug: null };
  const metSalderen = salderen(contract, when);
  if (contract?.type === "dynamic" && !(c.period?.all_in_price > 0)) {
    const d = contract.dynamic ?? {};
    if (!terugleverBekend(contract, when)) return { koop, terug: c.feedIn ?? rate?.feedIn ?? null };
    const markt = koop / (1 + (Number(d.vat_percent) || 0) / 100) - (Number(d.energy_tax) || 0) - (Number(d.supplier_markup) || 0);
    // Zon op en onder rekent met het echte moment (v0.138.2).
    const begin = vanHuis(new Date(when));
    const dag = overdag(begin, new Date(begin.getTime() + lengte), ligging);
    if (metSalderen && aandeel !== null && aandeel < 1) {
      const gesaldeerd = terugOp(markt, koop, d, true, dag);
      const overschot = terugOp(markt, koop, d, false, dag);
      if (gesaldeerd !== null && overschot !== null) return { koop, terug: aandeel * gesaldeerd + (1 - aandeel) * overschot };
    }
    return { koop, terug: terugOp(markt, koop, d, metSalderen, dag) };
  }
  if (metSalderen) {
    const gesaldeerd = koop - kostenPerKwh(contract?.fixed, true);
    if (aandeel !== null && aandeel < 1) {
      // Het overschot: de vergoeding na saldering van dit contract, of van een eerder.
      const overschot = c.period
        ? (c.feedIn ?? null)
        : (() => { const { vergoeding, kosten } = vasteTeruglevering(contract?.fixed, when, false); return vergoeding - kosten; })();
      if (overschot !== null) return { koop, terug: aandeel * gesaldeerd + (1 - aandeel) * overschot };
    }
    return { koop, terug: gesaldeerd };
  }
  if (contract?.type !== "dynamic" && !c.period) {
    const { vergoeding, kosten } = vasteTeruglevering(contract?.fixed, when);
    return { koop, terug: vergoeding - kosten };
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
 * De hele som voor één periode: wat het kostte, en los daarvan wat er bespaard werd.
 *
 * Twee aparte sommen sinds v0.147.0. De bewoner van een klantwoning op 22-10-2026:
 * "Het zijn twee opzichzelfstaande berekeningen, terwijl je het n de huidige versie
 * mogelijk denkt dat ze met elkaar te maken hebben." Kosten (`uitgegeven`) is wat je
 * betaalde: stroom, gas en water, min wat alle teruglevering opbracht, ook wat de
 * batterij verkocht. Bespaard is wat zon, batterij en coach scheelden tegenover inkopen
 * op hetzelfde moment: de zon die meteen het huis in ging tegen de prijs van dat uur,
 * de zon die via de batterij het huis in ging tegen die prijs min wat terugleveren had
 * opgeleverd, en bij de coach wat hij met de batterij verdiende door goedkoop in te
 * kopen en duur te gebruiken of te verkopen, naast de beurten. Met een thuisbatterij
 * komt dat per vak uit `herkomst` in views/history.js (`zonEuro`, `accuEuro`,
 * `handelEuro`); zonder is de zon de eigen zon tegen de prijs van het vak. Tot
 * v0.147.0 telde alle teruglevering bij de zon, ook wat de batterij verkocht, terwijl
 * dat ook al in het kasboek van de batterij stond: in die klantwoning stond er die dag
 * "Door je zon € 7,54" bij 10,7 kWh. De afschrijving telt hier niet mee, alleen in de
 * keuze wanneer de batterij laadt (de bewoner: "Want je rekent je afschrijving van
 * zonnepanelen etc ook niet mee").
 *
 * @param {object} o
 * @param {{start: Date, own: number, bought: number, sold: number, zonInAccu?: number}[]} o.rijen
 *   de vakken van de periode, zoals Historie ze tekent. `zonInAccu` is de zon
 *   die de batterij in ging in een vak waarover de coach dat nog niet telde
 *   (`huisMetAccu` in views/history.js)
 * @param {(when: Date) => {koop: number|null, terug: number|null}} o.prijs
 * @param {{start: Date, value: number}[]} [o.gas]
 * @param {Map<number, number>} [o.gasPrijzen] de gasprijs per vak uit de sensor, bij dynamisch gas (v0.129.0)
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
export function balans({ rijen, prijs, gas = [], gasPrijzen = null, water = [], contract, accu = 0, accuVoorraad = 0, accuZon = 0, coach = null, vasteKosten = 0 }) {
  let stroom = 0;
  let terug = 0;
  let zon = 0;
  let accuUitHerkomst = 0;
  let handel = 0;
  let metHerkomst = false;
  let metTerug = false;
  let onbekend = 0;
  for (const r of rijen ?? []) {
    const p = prijs(r.start);
    if (p.koop === null) {
      onbekend += 1;
      continue;
    }
    stroom += r.bought * p.koop;
    const terugPrijs = p.terug ?? null;
    if (terugPrijs !== null) {
      terug += r.sold * terugPrijs;
      metTerug = true;
    }
    if (r.zonEuro !== undefined) {
      zon += r.zonEuro;
      accuUitHerkomst += r.accuEuro ?? 0;
      handel += r.handelEuro ?? 0;
      metHerkomst = true;
    } else {
      // Zonder herkomst: de eigen zon, min wat de zon die de batterij in ging minder
      // waard was dan zelf gebruikt (`zonInAccu`, uit het vak zelf).
      zon += r.own * p.koop - (Number(r.zonInAccu) || 0) * (p.koop - (terugPrijs ?? 0));
    }
  }
  // En daarna uit de telling van de coach (`accuZon`), als er geen herkomst is.
  if (!metHerkomst) zon -= Number(accuZon) || 0;
  // Terugleverkosten in schalen (v0.135.0): een vast bedrag per dag, van wat
  // teruglevering opleverde af (`schaalKosten`).
  const vast = Number(vasteKosten) || 0;
  terug -= vast;
  const volume = (rijenVan, sleutel, perVak = null) => {
    let euro = 0;
    let met = false;
    for (const r of rijenVan ?? []) {
      // Een eerder contract gaat voor; anders bij dynamisch gas de sensor.
      const vast = contractAt(contract, r.start)[sleutel];
      const prijsM3 = vast ?? perVak?.get(new Date(r.start).getTime()) ?? null;
      if (prijsM3 === null || prijsM3 === undefined) continue;
      euro += r.value * prijsM3;
      met = true;
    }
    return { euro, met };
  };
  const g = volume(gas, "gas", gasPrijzen);
  const w = volume(water, "water");

  // De beurten: wat er op zon ging staat al bij de zon, de coach houdt het wachten
  // op een goedkoper moment.
  const wachten = (Number(coach?.saved) || 0) - (Number(coach?.solar_saved) || 0);
  // Zonder uren van de herkomst (de statistiek ontbrak) het kasboek van de coach.
  const accuEuro = metHerkomst ? accuUitHerkomst : Number(accu) || 0;
  const coachEuro = wachten + (metHerkomst ? handel : 0);
  const bespaard = zon + accuEuro + coachEuro;
  const uitgegeven = stroom - terug + g.euro + w.euro;
  // Wat er aan stroom in de batterij bij kwam is uitgegeven maar nog niet
  // gebruikt; telt opgeleverd het pas als het eruit gaat, dan hoort het hier
  // van zonder af, anders telt zonder het als verbruik (v0.107.0).
  const voorraad = Number(accuVoorraad) || 0;

  return {
    stroom,
    terug,
    metTerug,
    vasteKosten: vast,
    gas: g.euro,
    metGas: g.met,
    water: w.euro,
    metWater: w.met,
    uitgegeven,
    bespaard,
    delen: { zon, accu: accuEuro, coach: coachEuro },
    voorraad,
    onbekend,
  };
}
