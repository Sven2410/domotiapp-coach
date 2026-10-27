/**
 * Where the dashboard gets its numbers.
 *
 * Only real ones. There used to be a simulated house here so a fresh install
 * showed something moving; it is gone. Two sources feeding the same views made
 * it impossible to tell "the sensor is not updating" from "you are looking at
 * the simulation", which is exactly the confusion it caused. An unconfigured
 * dashboard now shows dashes and says so.
 *
 * All power is in watts inside this module and everywhere downstream. Sensors
 * arrive in whatever unit they please -- the same installation mixes W and kW --
 * and normalising once, here, is what keeps a factor of a thousand from leaking
 * into the diagram.
 *
 * Sign convention for the grid: positive is import (van het net), negative is
 * export (naar het net).
 */

import { brandFields, canAlwaysOn, carsFor, programOf, valueLabel } from "./devices.js";
import { countdown, duration, huisNu, huisTijd, toKwh, toWatts } from "./format.js";
import { ptPrijsOp } from "./tarifas.js";
import { locale, nt, t } from "./i18n.js";

/** Een woord uit een tabel van devices.js, in de taal van nu (v0.139.0). */
const vertaald = (woord) => (woord === null || woord === undefined ? woord : t(woord));

const PHASES = ["l1", "l2", "l3"];

/** Nominal voltage, used when a phase reports power but not volts. */
const NOMINAL_VOLTS = 230;

const HISTORY = 60;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

const usable = (state) =>
  state && state.state !== "unavailable" && state.state !== "unknown" && state.state !== "";

/** Read one entity as watts, or null when it is missing or unusable. */
function readPower(feed, entityId) {
  if (!entityId) return null;
  const state = feed.get(entityId);
  if (!usable(state)) return null;
  return toWatts(state.state, state.attributes?.unit_of_measurement);
}

/**
 * What the roof delivers, in watts.
 *
 * A SolarEdge goes to sleep at night and its sensor turns `unavailable`. With
 * the sun below the horizon that is not a missing number but zero, and saying
 * so keeps the house on the diagram: at de klantwoning on 19-09-2026 it read a
 * dash all night, because consumption is solar plus grid. Only below the
 * horizon, and only with `sun.sun` present: in daylight an unreachable
 * inverter may well be producing, and then a dash is the honest answer.
 */
function readSolar(feed, entityId) {
  const watts = readPower(feed, entityId);
  if (watts !== null || !entityId) return watts;
  return feed.get("sun.sun")?.state === "below_horizon" ? 0 : null;
}

/** Alle omvormers samen: de eerste plus `solar_extra`. */
export function solarEntities(sources) {
  return [sources?.solar, ...(Array.isArray(sources?.solar_extra) ? sources.solar_extra : [])].filter(Boolean);
}

/**
 * Wat alle omvormers samen geven. Zwijgt er een terwijl een ander wel iets
 * zegt, dan telt wat er is: op het scherm is een dak dat half meet beter dan
 * een streepje. (De coach zelf is strenger; zie `_zon_w` in coach.py.)
 */
function readSolarAll(feed, sources) {
  const waarden = solarEntities(sources).map((id) => readSolar(feed, id));
  if (!waarden.length || waarden.every((w) => w === null)) return waarden.length ? null : readSolar(feed, sources?.solar);
  return waarden.reduce((som, w) => som + (w ?? 0), 0);
}

/**
 * Read a price entity as euro per kWh.
 *
 * Suppliers publish in both euro and cents, so the unit decides -- a tariff read
 * as 0.24 when it is really 24 cents would have the coach calling the evening
 * peak cheap.
 */
function readPrice(feed, entityId) {
  if (!entityId) return null;
  const state = feed.get(entityId);
  if (!usable(state)) return null;

  const value = Number(state.state);
  if (!Number.isFinite(value)) return null;

  const unit = String(state.attributes?.unit_of_measurement ?? "").toLowerCase();
  if (unit.includes("ct") || unit.includes("cent")) return value / 100;
  return value;
}

/**
 * A bare market price turned into what it actually costs.
 *
 * Energy tax and the supplier's markup are added first and VAT goes over the
 * lot, which is the order the Dutch bill uses. Getting it wrong is a couple of
 * cents per kWh in every piece of advice the coach gives.
 *
 * Both figures are entered without VAT, the way they are quoted on a contract.
 */
export function allInFrom(market, dynamic) {
  const tax = Number(dynamic?.energy_tax) || 0;
  const markup = Number(dynamic?.supplier_markup) || 0;
  const vat = Number(dynamic?.vat_percent) || 0;
  return (market + tax + markup) * (1 + vat / 100);
}

/**
 * What a kWh costs right now, from the contract rather than from a single
 * sensor.
 *
 * A fixed contract is a number the installer typed in. A dynamic one is either
 * an entity that already carries the all-in price, or a bare market price that
 * still has to be worked out.
 *
 * @returns {number|null} euro per kWh
 */
export function priceNow(feed, contract) {
  if (!contract) return null;

  // Portugal (v0.138.0): de prijs van het tijdvak van nu, zoals `tariff` hem rekent.
  // Tot dan las de tegel hier de vaste all-in prijs van een Nederlands contract.
  if (contract.country === "PT") {
    return ptPrijsOp(contract.pt, new Date(), 900000).koop ?? priceAt(coachRijen())?.price ?? null;
  }

  if (contract.type !== "dynamic") {
    const value = Number(contract.fixed?.all_in_price);
    return Number.isFinite(value) ? value : null;
  }

  // Valt de reserve in, dan de prijs waar de coach mee rekent (v0.101.3).
  const vanCoach = priceAt(coachRijen())?.price ?? null;
  if (coachPrijzen.reserve && vanCoach !== null) return vanCoach;

  const dynamic = contract.dynamic ?? {};
  if (dynamic.source === "all_in") return readPrice(feed, dynamic.all_in_entity) ?? vanCoach;

  const market = readPrice(feed, dynamic.market_entity);
  return market === null ? vanCoach : allInFrom(market, dynamic);
}

/**
 * De prijslijst waar de coach mee rekent (v0.101.3), voor als de sensor zelf
 * geen lijst meegeeft of de reserveprijssensor invalt.
 *
 * Van de ingebouwde Nord Pool van Home Assistant staat er geen lijst in de
 * attributen; die haalt de coach via een dienst op (`_async_nordpool` in
 * coach.py). En valt de reserve in omdat de eigen sensor niets geeft, dan
 * hoort het paneel dezelfde prijzen te tekenen als de coach gebruikt. Eén
 * lijst voor het hele paneel, bijgewerkt door `laadCoachPrijzen`.
 */
let coachPrijzen = { reserve: false, rows: [], at: 0 };

/** Onder welk event de coach elk van deze op de bus van Home Assistant zet. */
const COACH_EVENTS = {
  decision: "domotiapp_coach_decision",
  notification: "domotiapp_coach_notification",
  settings: "domotiapp_coach_settings_updated",
  berichten: "domotiapp_coach_berichten",
};

/**
 * De besluiten, meldingen of instellingen van de coach volgen (v0.108.1).
 *
 * Via het eigen commando `domotiapp_coach/subscribe`, en niet rechtstreeks op
 * de events: Home Assistant laat een gebruiker zonder beheerdersrechten zich
 * daar niet op abonneren. In de klantwoning werkte het overzicht van een
 * bewoner daardoor na het openen nooit meer bij, en stond het log vol met
 * "Refusing to allow ... to subscribe". De terugval op de events is er voor
 * een omgeving die het commando niet kent, zoals de preview.
 *
 * @param {object} hass
 * @param {"decision"|"notification"|"settings"} soort
 * @param {(data: object) => void} terug krijgt wat het event meedraagt
 * @returns {Promise<(() => void) | null>} om af te melden
 */
export async function volgCoach(hass, soort, terug) {
  const verbinding = hass?.connection;
  if (verbinding?.subscribeMessage) {
    try {
      return await verbinding.subscribeMessage((data) => terug(data), {
        type: "domotiapp_coach/subscribe",
        event: soort,
      });
    } catch (error) {
      // Dan de events zelf, zoals voor v0.108.1.
    }
  }
  if (!verbinding?.subscribeEvents) return null;
  return verbinding.subscribeEvents((event) => terug(event?.data), COACH_EVENTS[soort]);
}

/** De lijst van de coach opnieuw ophalen, hooguit eens per minuut. */
export async function laadCoachPrijzen(hass, nu = Date.now()) {
  if (!hass?.callWS || nu - coachPrijzen.at < 60_000) return coachPrijzen;
  coachPrijzen = { ...coachPrijzen, at: nu };
  try {
    const antwoord = await hass.callWS({ type: "domotiapp_coach/prices" });
    coachPrijzen = {
      reserve: Boolean(antwoord?.reserve),
      // Of de opbouw bevestigd is (v0.129.0); undefined bij een oudere coach.
      bevestigd: antwoord?.bevestigd,
      rows: (antwoord?.rows ?? [])
        .map((rij) => ({
          start: huisTijd(rij.start),
          end: huisTijd(rij.end),
          price: Number(rij.price),
          feedIn: rij.feed_in === null || rij.feed_in === undefined ? null : Number(rij.feed_in),
        }))
        .filter((rij) => !Number.isNaN(rij.start.getTime()) && !Number.isNaN(rij.end.getTime()) && Number.isFinite(rij.price)),
      at: nu,
    };
  } catch (error) {
    // Een coach van voor v0.101.3 kent dit commando niet; dan leest het paneel
    // de sensor zoals altijd.
  }
  return coachPrijzen;
}

/**
 * Met welk rendement heen en terug de coach een thuisbatterij rekent, in dezelfde
 * volgorde als `_rendement_bron` in coach.py (v0.145.0): een kWh-meter op de batterij,
 * het zelf geleerde, de eigen tellers, wat er is ingevuld. `bron` zegt welke het is.
 */
export function accuRendementBron(device, batteryState) {
  const rij = (batteryState ?? []).find((r) => r?.device === device?.id) ?? {};
  if (device?.entities?.energy_in && device?.entities?.energy_out && rij.rte) return { rte: Number(rij.rte), bron: "meter" };
  if (rij.rte_power?.rte) return { rte: Number(rij.rte_power.rte), bron: "geleerd" };
  if (rij.rte_accu) return { rte: Number(rij.rte_accu), bron: "accu" };
  const opgave = Number(device?.battery?.rte_percent);
  if (opgave > 0) return { rte: opgave / 100, bron: "opgave" };
  return { rte: null, bron: null };
}

/** Het rendement heen en terug van `accuRendementBron`, of null. */
export const accuRendement = (device, batteryState) => accuRendementBron(device, batteryState).rte;

/**
 * De prijs per vak uit de statistieken, all-in (v0.101.3).
 *
 * Een marktprijssensor geeft de kale beursprijs; tot v0.101.3 rekende Historie
 * die als inkoopprijs, zonder belasting, opslag en btw. En een vak waarin de
 * eigen sensor niets gaf krijgt de prijs van de reserveprijssensor, op
 * dezelfde manier omgerekend als de coach dat doet (`_prijsbron`).
 *
 * @param {Map<number, number>} eigen de gemiddelde prijs per vak van de eigen sensor
 * @param {Map<number, number>} reserve die van de reserveprijssensor
 */
export function allInPrijzen(eigen, reserve, contract) {
  const d = contract?.dynamic ?? {};
  const uit = new Map();
  for (const [tijd, prijs] of eigen ?? new Map()) {
    uit.set(tijd, d.source === "market" ? allInFrom(prijs, d) : prijs);
  }
  // Een reservesensor kan all-in zijn; de kale marktprijs die sinds v0.129.0
  // vanzelf de reserve is (`reserveEntity_` in views/history.js) niet.
  const reserveAllIn = Boolean(d.fallback_entity) && d.fallback_source === "all_in";
  for (const [tijd, prijs] of reserve ?? new Map()) {
    if (!uit.has(tijd)) uit.set(tijd, reserveAllIn ? prijs : allInFrom(prijs, d));
  }
  return uit;
}

/** Voor de proeven: de lijst van de coach zetten zonder Home Assistant. */
export function zetCoachPrijzen(waarde) {
  coachPrijzen = { reserve: false, rows: [], at: 0, ...waarde };
}

/** Of de reserveprijssensor nu invalt, volgens de coach. */
export const reserveValtIn = () => coachPrijzen.reserve;
/** False als de bewoner de prijsopbouw nog niet bevestigde (v0.129.0). */
export const prijsBevestigd = () => coachPrijzen.bevestigd;

export function coachRijen() {
  return coachPrijzen.rows.map((rij) => ({ start: rij.start, end: rij.end, price: rij.price }));
}

/**
 * The price list a dynamic-tariff entity carries in its attributes.
 *
 * Suppliers publish tomorrow's prices in the early afternoon and every
 * integration hangs them off the entity in its own shape. There is no standard
 * at all, so the shapes seen in the wild are all tried in turn:
 *
 * - `prices: [{from, till, price}]`      Frank Energie
 * - `raw_today` + `raw_tomorrow`         Nord Pool: `[{start, end, value}]`
 * - `data: [{startsAt, total}]`          Tibber, EnergyZero and friends
 * - `forecast: [{datetime, electricity_price}]`  Zonneplan, in ten-millionths of
 *   a euro (3355224 next to a state of 0.3355224 €/kWh, measured 22-09-2026)
 * - `today` + `tomorrow: [number]`       one bare number per hour from midnight
 *
 * The coach reads the same shapes in `_prijsrijen` (coach.py); keep the two
 * lists the same, or the chart and the decision disagree about what an hour
 * costs.
 *
 * Anything else yields nothing, and the panel says it has no forecast rather
 * than inventing one.
 *
 * @returns {Array<{start: Date, end: Date|null, value: number}>}
 */
const ZONNEPLAN_DIVISOR = 10_000_000;

function readSchedule(attributes) {
  const rows = [];

  const push = (start, end, value) => {
    // Op de klok van het huis, net als de lijst van de coach (v0.138.1).
    const from = huisTijd(start);
    const till = end === null || end === undefined ? null : huisTijd(end);
    const number = Number(value);
    if (Number.isNaN(from.getTime()) || !Number.isFinite(number)) return;
    rows.push({ start: from, end: till && !Number.isNaN(till.getTime()) ? till : null, value: number });
  };

  const list = (raw) => (Array.isArray(raw) ? raw : []);

  for (const entry of list(attributes?.prices)) {
    push(entry?.from ?? entry?.start, entry?.till ?? entry?.end, entry?.price ?? entry?.value);
  }

  for (const entry of [...list(attributes?.raw_today), ...list(attributes?.raw_tomorrow)]) {
    push(entry?.start, entry?.end, entry?.value ?? entry?.price);
  }

  for (const entry of list(attributes?.data)) {
    push(
      entry?.startsAt ?? entry?.start ?? entry?.from ?? entry?.datetime,
      entry?.endsAt ?? entry?.end ?? entry?.till,
      entry?.total ?? entry?.price ?? entry?.value
    );
  }

  for (const entry of list(attributes?.forecast)) {
    if (entry?.electricity_price === undefined || entry?.electricity_price === null) continue;
    push(entry?.datetime, null, Number(entry.electricity_price) / ZONNEPLAN_DIVISOR);
  }

  // Bare hourly numbers carry no timestamps of their own: they are 24 values
  // starting at local midnight, and tomorrow's list follows on from today's.
  if (!rows.length) {
    const midnight = huisNu();
    midnight.setHours(0, 0, 0, 0);
    const bare = [...list(attributes?.today), ...list(attributes?.tomorrow)];
    bare.forEach((value, index) => {
      if (value === null) return;
      push(new Date(midnight.getTime() + index * 3_600_000), null, value);
    });
  }

  return rows.sort((a, b) => a.start - b.start);
}

/**
 * The price per interval for as far ahead as the supplier publishes.
 *
 * The same conversion the current price goes through is applied to every entry,
 * so a chart of the forecast and the number on the tile cannot disagree: cents
 * become euros, and a bare market price gets tax, markup and VAT.
 *
 * Entries without an end time inherit the gap to the next one; the last one is
 * as long as the one before it, falling back to the interval the customer said
 * their contract uses. The same rule as `_slots` in coach.py.
 *
 * @returns {Array<{start: Date, end: Date, price: number}>} empty when the
 *   contract is fixed or the entity publishes nothing.
 */
export function priceForecast(feed, contract) {
  // Portugal (v0.138.0): twee of drie prijzen per dag, dus wel een lijst. Die van de
  // coach (`_pt_rijen` in coach.py), dezelfde als in de vooruitblik. De eigenaar op
  // 19-10-2026: "hier heb je 2 prijzen dus dan moet je kunnen zien in de grafiek wanneer
  // hij goedkoper is."
  if (contract?.country === "PT") return coachRijen();
  if (contract?.type !== "dynamic") return [];
  // Valt de reserve in, of geeft de sensor zelf geen lijst (de ingebouwde Nord
  // Pool), dan de lijst van de coach (v0.101.3).
  if (coachPrijzen.reserve) return coachRijen();

  const dynamic = contract.dynamic ?? {};
  const allIn = dynamic.source === "all_in";
  const state = feed.get(allIn ? dynamic.all_in_entity : dynamic.market_entity);
  if (!usable(state)) return coachRijen();

  const rows = readSchedule(state.attributes);
  if (!rows.length) return coachRijen();

  const unit = String(state.attributes?.unit_of_measurement ?? "").toLowerCase();
  const scale = unit.includes("ct") || unit.includes("cent") ? 0.01 : 1;
  const fallback = dynamic.interval === "quarter" ? 900_000 : 3_600_000;

  return rows.map((row, index) => {
    const next = rows[index + 1];
    const prev = rows[index - 1];
    const length = prev ? row.start.getTime() - prev.start.getTime() : fallback;
    const end =
      row.end ?? (next ? next.start : new Date(row.start.getTime() + length));
    const value = row.value * scale;
    return { start: row.start, end, price: allIn ? value : allInFrom(value, dynamic) };
  });
}

/** The entry covering a moment, or undefined when the forecast does not reach it. */
export const priceAt = (forecast, when = huisNu()) =>
  forecast.find((row) => when >= row.start && when < row.end);

/**
 * What the sun is expected to bring, from whichever forecast is mapped.
 *
 * Deliberately three plain numbers and no hour-by-hour curve. Forecast.Solar
 * and Solcast publish day totals, a peak time and the current and next hour as
 * separate sensors; there is no list per hour to read. That turns out not to
 * matter, because a forecast answers a different question than a measurement
 * does. "Is it worth waiting" is a question about today and tomorrow as a
 * whole, and while the coach is actually regulating it uses the meter, not the
 * forecast: what the panels really produce is a fact, and the forecast is an
 * estimate that was made this morning.
 *
 * Deriving a curve from the day total and the peak time would be inventing
 * numbers, which this panel does not do.
 *
 * @returns {{remainingToday: number|null, tomorrow: number|null,
 *            peakToday: Date|null, has: boolean}}
 */
export function solarForecast(feed, sources) {
  const config = sources?.solar_forecast ?? {};

  const kwh = (entityId) => {
    const state = feed.get(entityId);
    if (!usable(state)) return null;
    return toKwh(state.state, state.attributes?.unit_of_measurement);
  };

  const peakState = feed.get(config.peak_today);
  const peak = usable(peakState) ? new Date(peakState.state) : null;

  const out = {
    remainingToday: kwh(config.remaining_today),
    tomorrow: kwh(config.tomorrow),
    peakToday: peak && !Number.isNaN(peak.getTime()) ? peak : null,
  };
  out.has = out.remainingToday !== null || out.tomorrow !== null;
  return out;
}

/**
 * Het contract dat op een dag gold: een eerder contract als de dag erin valt,
 * anders het huidige. Per energiebron (v0.129.0): stroom uit `contract.periods`,
 * gas uit `contract.gas.periods`, water uit `contract.water.periods`, want wie
 * van stroomleverancier wisselde hoeft dat niet ook van gas te doen.
 *
 * De bewoner van de eerste woning op 22-09-2026: van-tot met een prijs, per
 * contract, voor stroom en voor gas, "dan kun je een goede weergave bieden van
 * kosten, ook bij wijzigen van aanbieder." Een prijs van nul in een periode
 * betekent "niet ingevuld" en valt terug op het huidige contract. Een dynamisch
 * contract heeft geen vaste inkoopprijs: `buy` (of `gas`) is dan null en de
 * historie pakt de prijs uit de geschiedenis van de prijsentiteit.
 *
 * @returns {{buy: number|null, feedIn: number|null, gas: number|null, water: number|null, period: object|null}}
 */
export function contractAt(contract, when) {
  const dag = when instanceof Date ? when : new Date(when);
  const key = Number.isNaN(dag.getTime()) ? null : dag.toISOString().slice(0, 10);
  const lokaal = key === null ? null
    : `${dag.getFullYear()}-${String(dag.getMonth() + 1).padStart(2, "0")}-${String(dag.getDate()).padStart(2, "0")}`;
  const binnen = (lijst) => (lokaal === null || !Array.isArray(lijst) ? null
    : lijst.find((p) => p && (!p.from || p.from <= lokaal) && (!p.to || lokaal <= p.to)) ?? null);
  const period = binnen(contract?.periods);
  const gasPeriode = binnen(contract?.gas?.periods);
  const waterPeriode = binnen(contract?.water?.periods);
  const fixed = contract?.type !== "dynamic";
  const huidig = Number(contract?.fixed?.all_in_price);
  const huidigTerug = fixed
    ? (Number(contract?.fixed?.feed_in_tariff) || 0) - (Number(contract?.fixed?.feed_in_costs) || 0)
    : null;
  // Dynamisch gas heeft geen vaste prijs: die komt uit de sensor (`gasPrijzen` in balans).
  const gasVast = (contract?.gas?.type ?? "fixed") !== "dynamic";
  const huidigGas = gasVast && Number(contract?.gas?.price) > 0 ? Number(contract.gas.price) : null;
  const huidigWater = Number(contract?.water?.price) > 0 ? Number(contract.water.price) : null;
  const getal = (v) => (Number(v) > 0 ? Number(v) : null);
  return {
    // Een eerder dynamisch contract heeft geen vaste prijs: die komt uit de sensor.
    buy: period?.type === "dynamic" ? null : getal(period?.all_in_price) ?? (fixed && Number.isFinite(huidig) ? huidig : null),
    feedIn: getal(period?.feed_in_tariff) ?? huidigTerug,
    gas: getal(gasPeriode?.price) ?? huidigGas,
    water: getal(waterPeriode?.price) ?? huidigWater,
    period,
  };
}

/**
 * What a kWh is worth in both directions, as far as this panel can know it.
 *
 * A fixed contract is exact: the customer typed the number in. A dynamic one is
 * an average over the prices that happen to be published, which is today and
 * sometimes tomorrow -- so it is honest about being an average of today rather
 * than of the period being looked at. Nobody keeps a year of tariffs, and
 * pretending otherwise would put a precise-looking figure on a guess.
 *
 * `feedIn` is what actually lands: the tariff minus the costs the supplier
 * charges over what is fed back. On plenty of contracts that is close to zero,
 * and that is exactly why using your own sun is worth so much more than
 * exporting it.
 *
 * @returns {{buy: number|null, feedIn: number, basis: string}}
 */
export function tariff(feed, contract) {
  // Portugal (v0.137.0): de prijs van het tijdvak van nu.
  if (contract?.country === "PT") {
    const nu = ptPrijsOp(contract.pt, new Date(), 900000);
    return { buy: nu.koop, feedIn: nu.terug, basis: nt("je tarief van nu") };
  }
  const fixed = contract?.type !== "dynamic";

  if (fixed) {
    const value = Number(contract?.fixed?.all_in_price);
    return {
      buy: Number.isFinite(value) ? value : null,
      feedIn:
        (Number(contract?.fixed?.feed_in_tariff) || 0) -
        (Number(contract?.fixed?.feed_in_costs) || 0),
      basis: nt("je vaste tarief"),
    };
  }

  const mean = (rows) => {
    const vandaag = huisNu().toDateString();
    const today = rows.filter((row) => row.start.toDateString() === vandaag);
    const used = today.length ? today : rows;
    return used.length ? used.reduce((total, row) => total + row.price, 0) / used.length : null;
  };

  const dynamic = contract?.dynamic ?? {};

  // What a dynamic contract pays for export is the bare market price, so it is
  // only known when the market price is what was mapped. With an all-in entity
  // there is no way to get back to it, and a number is left out rather than
  // guessed at.
  let feedIn = null;
  // Wat de coach als terugleverprijs rekent, ook met een all-in sensor en een
  // kale marktprijs ernaast (v0.129.0); tot dan alleen als de reserve inviel.
  if (coachPrijzen.rows.some((rij) => rij.feedIn !== null)) {
    // De reserve: wat teruglevering volgens de coach opbrengt.
    const terug = coachPrijzen.rows.filter((rij) => rij.feedIn !== null).map((rij) => ({ start: rij.start, price: rij.feedIn }));
    feedIn = mean(terug);
  } else if (dynamic.source === "market") {
    const market = mean(
      readSchedule(feed.get(dynamic.market_entity)?.attributes ?? {}).map((row) => ({
        start: row.start,
        price: row.value,
      }))
    );
    if (market !== null) feedIn = market - (Number(dynamic.feed_in_costs) || 0) + (Number(dynamic.feed_in_bonus) || 0);
  }

  return { buy: mean(priceForecast(feed, contract)), feedIn, basis: nt("het gemiddelde tarief van vandaag") };
}

/** The meter counters, in the order a Dutch meter lists them. */
const METERS = [
  { key: "import_low", label: nt("Geleverd laag") },
  { key: "import_high", label: nt("Geleverd hoog") },
  { key: "export_low", label: nt("Teruggeleverd laag") },
  { key: "export_high", label: nt("Teruggeleverd hoog") },
  { key: "gas", label: nt("Gas") },
  { key: "water", label: nt("Water") },
];

/**
 * The meter readings, exactly as the meter reports them.
 *
 * Deliberately not converted. Everywhere else in this panel a reading is
 * normalised, because a diagram has to add watts to watts. A meter reading is
 * not a measurement to compute with: it is the number a customer copies onto a
 * supplier's website, and it has to match the meter digit for digit. Rounding
 * 12345,678 to 12346 kWh would make it useless for the one job it has.
 *
 * Only entities that are filled in and reporting something appear. A counter
 * that is missing is left out rather than shown as a dash, because the card is
 * a list of what this meter has rather than of what it might have.
 *
 * @returns {Array<{key: string, label: string, value: string, unit: string}>}
 */
export function meterReadings(feed, sources) {
  const config = sources?.meters ?? {};

  return METERS.filter((meter) => (meter.key !== "gas" || config.gas_enabled) && (meter.key !== "water" || config.water_enabled))
    .map((meter) => {
      const state = feed.get(config[meter.key]);
      if (!usable(state)) return null;

      const number = Number(state.state);
      if (!Number.isFinite(number)) return null;

      // Kept at the meter's own precision, up to three decimals: gas runs to
      // three and electricity to three on most Dutch meters.
      return {
        ...meter,
        label: t(meter.label),
        value: number.toLocaleString(locale(), { maximumFractionDigits: 3 }),
        unit: state.attributes?.unit_of_measurement ?? "",
      };
    })
    .filter(Boolean);
}

/** Read a plain numeric entity, in whatever unit it reports. */
/**
 * Wat een thuisbatterij nu doet, in watt, laden positief, of null.
 *
 * Een sensor met een teken, of twee losse sensoren voor laden en ontladen:
 * dezelfde twee vormen als `_batterij_w` in coach.py.
 */
export function batteryWatts(feed, device) {
  const getekend = readPower(feed, device?.entity);
  if (getekend !== null) return device?.battery?.power_invert ? -getekend : getekend;
  const laden = readPower(feed, device?.entities?.charge_power);
  const ontladen = readPower(feed, device?.entities?.discharge_power);
  if (laden === null && ontladen === null) return null;
  return (laden ?? 0) - (ontladen ?? 0);
}

function readNumber(feed, entityId) {
  if (!entityId) return null;
  const state = feed.get(entityId);
  if (!usable(state)) return null;
  const value = Number(state.state);
  return Number.isFinite(value) ? value : null;
}

/**
 * The extra readings a device carries, ready to be shown.
 *
 * These are the brand's own entities -- a charger's status, its limit, what it
 * has ever delivered. They are read here rather than in the diagram so that the
 * bubble stays something that only draws what it is handed.
 *
 * A sensor that says nothing gets a dash, never a plausible-looking number.
 */
/**
 * Een accustand met wat er in kWh in zit: "39 % · 5,7 van 14,5 kWh" (v0.101.6).
 *
 * De eigenaar op 29-09-2026: "de accu kWh van de batterij, nu zie ik alleen het
 * percentage." Zonder bekende inhoud blijft het bij het percentage; een
 * geschatte kWh op een onbekende accu zou een verzonnen getal zijn.
 */
export function accuTekst(procent, inhoudKwh) {
  const kwh = (v) => v.toLocaleString(locale(), { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const pct = `${procent.toLocaleString(locale(), { maximumFractionDigits: 0 })} %`;
  return Number.isFinite(inhoudKwh) && inhoudKwh > 0
    ? t("{pct} · {kwh} van {totaal} kWh", { pct, kwh: kwh((procent / 100) * inhoudKwh), totaal: kwh(inhoudKwh) })
    : pct;
}

/**
 * De auto die op de kaart gekozen staat, als zijn accustand in Home Assistant
 * staat; anders niets (v0.101.7).
 *
 * Dezelfde keuze als de kaart zelf maakt: de gekozen auto, en zonder keuze de
 * eerste (`carsFor`, met de gast erbij). Tot v0.101.7 bleef de Ford op de kaart
 * staan als de gast gekozen was; de eigenaar op 29-09-2026: "hij moet de accu
 * tonen van de auto die geselecteerd is."
 */
function gekozenAutoMetStand(device, settings) {
  const autos = carsFor(device);
  const gekozen = (settings?.active_cars ?? []).find((rij) => rij?.device === device?.id)?.car;
  const auto = autos.find((car) => car.id === gekozen) ?? autos[0];
  return auto && !auto.guest && auto.soc_entity ? auto : null;
}

/** Kilometers per eenheid van een afstandsensor; een onbekende eenheid telt niet. */
const KM_PER = { km: 1, mi: 1.609344, m: 0.001 };

/** Onder deze stand reken je de volle actieradius niet meer na (v0.106.0). */
const RADIUS_MIN_PROCENT = 10;

/**
 * Wat de auto zelf zegt over zijn actieradius: de kilometers van nu, en hoeveel
 * kilometer één procent waard is. Allebei uit zijn eigen sensoren, of niets.
 *
 * De bewoner van de eerste woning op 01-10-2026, bij "Accu auto 28 % · 21,8 van
 * 78,0 kWh": "Ik denk dat de meeste consumenten dat niets zegt. Persoonlijk zou
 * ik daar de range in km's zetten. Omdat je het percentage en de beschikbare
 * range weet, kun je de max range laten berekenen." Dat is een deling van twee
 * metingen. Alleen vanaf `RADIUS_MIN_PROCENT`: een accustand komt in hele
 * procenten, en op 5% kan dat de volle radius tien procent laten schuiven.
 */
export function actieradius(feed, car) {
  if (!car?.range_entity || !car?.soc_entity) return null;
  const bereik = feed.get(car.range_entity);
  if (!usable(bereik)) return null;
  const per = KM_PER[String(bereik.attributes?.unit_of_measurement ?? "").trim().toLowerCase()];
  const km = Number(bereik.state) * per;
  if (!per || !Number.isFinite(km) || km < 0) return null;
  const stand = feed.get(car.soc_entity);
  const procent = usable(stand) ? Number(stand.state) : NaN;
  return {
    km,
    perProcent: Number.isFinite(procent) && procent >= RADIUS_MIN_PROCENT ? km / procent : null,
  };
}

/** "28% · 138 van 493 km", of "6% · 30 km" als de volle radius niet na te rekenen is. */
export function radiusTekst(procent, radius) {
  const pct = `${Math.round(procent)}%`;
  const km = Math.round(radius.km).toLocaleString(locale());
  return radius.perProcent
    ? t("{pct} · {km} van {max} km", { pct, km, max: Math.round(radius.perProcent * 100).toLocaleString(locale()) })
    : `${pct} · ${km} km`;
}

/**
 * Wat er in deze laadbeurt al in ging, of in de laatste als de kabel eruit is
 * (v0.106.0). De coach telt het (`session` in zijn besluit, uit `_geladen`).
 *
 * De bewoner van de eerste woning op 01-10-2026: "'Deze sessie - x kWh', of
 * 'geladen deze laadbeurt' ... Evt + x% of + x km als extra toevoeging. Op die
 * manier weet je dat er tijdens de huidige sessie al daadwerkelijk is gebeurd."
 * En meteen erna: "Of 'laatste sessie' oid. De waardes zouden kunnen blijven
 * staan, totdat een nieuwe laadbeurt wordt gestart."
 *
 * De procenten alleen als de auto ze zelf meldt; een opgegeven stand plus de
 * teller van de paal is een schatting, en de kWh zegt dan al alles. De
 * kilometers uit de procenten, tegen wat één procent nu waard is.
 */
export function laadbeurtRegels(feed, device, settings, besluit) {
  const beurt = besluit?.session;
  if (device?.type !== "laadpaal" || !beurt || !Number.isFinite(beurt.kwh)) return [];
  const label = beurt.active ? t("Deze laadbeurt") : t("Laatste laadbeurt");
  if (beurt.kwh < 0.05) return [{ label, text: t("nog niets") }];
  const delen = [`${beurt.kwh.toLocaleString(locale(), { minimumFractionDigits: 1, maximumFractionDigits: 1 })} kWh`];
  const erbij = Number.isFinite(beurt.soc_start) && Number.isFinite(beurt.soc_end) && !beurt.soc_estimated
    ? Math.round(beurt.soc_end) - Math.round(beurt.soc_start)
    : 0;
  if (erbij >= 1) {
    delen.push(`+${erbij}%`);
    const radius = actieradius(feed, gekozenAutoMetStand(device, settings));
    if (radius?.perProcent) delen.push(`+${Math.round(erbij * radius.perProcent).toLocaleString(locale())} km`);
  }
  return [{ label, text: delen.join(" · ") }];
}

function deviceDetails(feed, device, settings) {
  const rows = [];

  for (const field of brandFields(device)) {
    const entityId = device.entities?.[field.key];
    if (!entityId || field.hideRow) continue;

    let state = feed.get(entityId);
    // Het programma: zegt de sensor niets, dan de select waarmee het gezet
    // wordt. Bij Home Connect Local zegt de sensor alleen tijdens de beurt
    // iets en valt de select juist dan weg; dezelfde afspraak als in
    // `_one_programma` in coach.py.
    if (field.key === "program" && !usable(state) && device.entities?.program_select) {
      state = feed.get(device.entities.program_select);
    }
    if (!usable(state)) {
      rows.push({ label: vertaald(field.label), text: "—" });
      continue;
    }

    const raw = String(state.state);
    const number = Number(raw);
    const unit = state.attributes?.unit_of_measurement;
    // A brand may report words rather than numbers; those are translated where
    // we know them and passed through where we do not.
    const text =
      (field.format === "countdown" ? countdown(raw, unit) : null) ??
      vertaald(valueLabel(field.values, raw)) ??
      // Een woord dat Home Assistant zelf vertaalt, zoals de standen van Miele (v0.124.0).
      (!Number.isFinite(number) ? feed.label?.(state.entity_id ?? entityId) : undefined) ??
      (Number.isFinite(number)
        ? `${number.toLocaleString(locale(), { maximumFractionDigits: field.decimals ?? 2 })}${unit ? ` ${unit}` : ""}`
        // A word we have no translation for is still shown -- readable, but
        // recognisably the sensor's own wording rather than something invented.
        : raw.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()));

    // Een thuisbatterij: naast het percentage wat erin zit (v0.101.6), met de
    // inhoud uit haar sensor of zoals ingevuld.
    if (field.key === "soc" && device?.type === "thuisbatterij" && Number.isFinite(number)) {
      const cap = feed.get(device.entities?.capacity);
      const inhoud = usable(cap)
        ? toKwh(cap.state, cap.attributes?.unit_of_measurement)
        : Number(device.battery?.capacity_kwh);
      rows.push({ label: vertaald(field.label), text: accuTekst(number, Number(inhoud)) });
      continue;
    }

    rows.push({ label: vertaald(field.label), text });

    // What the selected program costs to run comes from the panel's own table
    // rather than from a sensor, so it is spelled out as an estimate. It is the
    // number the coach will plan with, and seeing it is how you catch it being
    // the wrong program.
    if (field.key === "program") {
      const program = programOf(device, raw, settings);
      if (program) {
        rows.push({
          label: program.measured ? t("Duurt gemeten") : t("Duurt ongeveer"),
          text: `${duration(program.minutes)} · ${Number(program.kwh).toLocaleString(locale(), {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })} kWh`,
        });
      }
    }
  }

  // De accustand van de auto, als die in Home Assistant staat (v0.101.6). De
  // eigenaar op 29-09-2026: "op de laadpaalkaart de batterijstand van de auto
  // zien als die in HA staat." Een auto zonder sensor vraagt zijn stand al op
  // de kaart zelf, en daar staat hij dan ook.
  // Met een sensor voor de actieradius in kilometers in plaats van kWh (v0.106.0);
  // zie `actieradius`.
  if (device?.type === "laadpaal") {
    const car = gekozenAutoMetStand(device, settings);
    // Zegt de sensor niets, dan geen regel met een streepje: de kaart vraagt de
    // stand dan zelf, net als bij een auto zonder sensor (v0.116.2,
    // `vraagAccustand` in devices.js).
    const state = car ? feed.get(car.soc_entity) : undefined;
    const procent = usable(state) ? Number(state.state) : NaN;
    if (car && Number.isFinite(procent)) {
      const radius = actieradius(feed, car);
      rows.push({
        label: t("Accu auto"),
        text: radius ? radiusTekst(procent, radius) : accuTekst(procent, Number(car.capacity_kwh)),
      });
    }
  }

  // Een smart plug (v0.120.0), of een vaatwasser aan een smart plug (v0.122.0):
  // of de stekker aan staat. Dat is wat "altijd aan" bewaakt, en een stekker
  // die uit staat meet ook niets.
  if (canAlwaysOn(device) && device.entities?.switch) {
    const stand = feed.get(device.entities.switch);
    const tekst = usable(stand) ? valueLabel({ on: t("Aan"), off: t("Uit") }, String(stand.state)) : null;
    rows.push({ label: t("Stekker"), text: tekst ?? "—" });
  }

  // Een thuisbatterij: wat de coach zelf bijhoudt. Het rendement is een meting
  // of een opgave, nooit een aanname; zonder staat er dat het niet bekend is.
  // Dezelfde volgorde als `_rendement_bron` in coach.py (v0.145.0): een kWh-meter
  // op de batterij, dan het zelf geleerde, dan de eigen tellers, dan de opgave.
  if (device?.type === "thuisbatterij") {
    const rij = (settings?.battery_state ?? []).find((r) => r?.device === device.id) ?? {};
    const opgave = device.battery?.rte_percent;
    const metMeter = accuRendementBron(device, settings?.battery_state).bron === "meter";
    // Per vermogen (v0.142.0): heen en terug, en per richting het rendement bij
    // elk vermogen dat de coach gemeten heeft, als de coach ermee rekent.
    const macht = metMeter ? null : rij.rte_power;
    const pct = (x) => Math.round(x * 100);
    const kw = (x) => x.toLocaleString(locale(), { maximumFractionDigits: 1 });
    const precies = (x) => (x * 100).toLocaleString(locale(), { maximumFractionDigits: 1 });
    const punten = (lijst) => (lijst ?? []).map(([k, e]) => t("{pct}% bij {kw} kW", { pct: pct(e), kw: kw(k) })).join(", ");
    rows.push({
      label: t("Rendement"),
      text: metMeter
        ? t("{pct}% gemeten met de kWh-meter", { pct: precies(rij.rte) })
        : macht?.rte
          ? t("{pct}% zelf geleerd", { pct: precies(macht.rte) })
          : rij.rte_accu
            ? t("ongeveer {pct}%, gemeten in de accu", { pct: pct(rij.rte_accu) })
            : opgave
              ? t("{pct}% opgegeven", { pct: Number(opgave).toLocaleString(locale(), { maximumFractionDigits: 1 }) })
              : t("nog niet bekend"),
    });
    if (macht?.rte) {
      rows.push({ label: t("Laden"), text: punten(macht.in) });
      rows.push({ label: t("Ontladen"), text: punten(macht.out) });
    }
  }

  // Een boiler heeft geen tabel en geen programma: wat de coach van hem weet
  // heeft hij zelf gemeten. Dat hoort op de kaart te staan, want het is het
  // enige waaraan te zien is dat het leren werkt. De eigenaar op 19-09-2026: "ik wil
  // dit zelflerend hebben." Nog niets gemeten is een eerlijk antwoord.
  if (device?.type === "boiler") {
    const geleerd = (settings?.boiler_learned ?? []).find((rij) => rij?.device === device.id) ?? {};
    const getal = (waarde, eenheid, cijfers = 1) =>
      waarde === null || waarde === undefined || waarde === ""
        ? t("nog niet gemeten")
        : `${Number(waarde).toLocaleString(locale(), { maximumFractionDigits: cijfers })} ${eenheid}`;
    rows.push({ label: t("Element"), text: getal(geleerd.heat_w ? geleerd.heat_w / 1000 : null, "kW", 1) });
    rows.push({ label: t("Vol vat"), text: getal(geleerd.vol_kwh, "kWh", 1) });
    rows.push({ label: t("Eruit per uur"), text: getal(geleerd.verbruik_kwh_h, "kWh", 2) });
  }

  return rows;
}

/**
 * What a phase is drawing, in amps.
 *
 * Every one of the three fields is optional -- a customer may have only power
 * per phase, or only current. With power but no current the amps follow from
 * P/U, using the measured voltage when there is one and the nominal 230 V when
 * there is not. That keeps a partly-filled installation useful instead of
 * showing an empty bar.
 */
export function phaseAmps(phase) {
  if (Number.isFinite(phase?.current)) return phase.current;
  if (!Number.isFinite(phase?.power)) return null;
  const volts = Number.isFinite(phase.voltage) && phase.voltage > 0 ? phase.voltage : NOMINAL_VOLTS;
  return phase.power / volts;
}

/** Per-phase current, power and voltage, whichever of them are mapped. */
function readPhases(feed, sources) {
  if (!sources.phases_enabled) return null;
  const config = sources.phases ?? {};

  const rows = PHASES.map((key) => {
    const row = {
      key,
      label: key.toUpperCase(),
      current: readNumber(feed, config[key]?.current),
      power: readPower(feed, config[key]?.power),
      voltage: readNumber(feed, config[key]?.voltage),
    };
    row.amps = phaseAmps(row);
    // True when the amps were worked out rather than measured, so the display
    // can be honest about it.
    row.ampsDerived = row.amps !== null && !Number.isFinite(row.current);
    return row;
  });

  return rows.some((row) => row.current !== null || row.power !== null || row.voltage !== null)
    ? rows
    : null;
}

/**
 * De onderverdeelkasten en groepen met een eigen zekering, met per fase wat er loopt.
 *
 * Dezelfde rijen als `readPhases`, per kast of groep. Sinds v0.168.0 blijft een kast of groep zonder
 * meetwaarde staan, met `measured: false`: de bewoner hoort zijn groep terug te zien, met "niet
 * gemeten" erbij. Een groep van één fase heet naar zijn fase (`phase`), niet altijd L1; de sensoren
 * staan onder "l1". Zie `installation.circuits`.
 *
 * Een groep zonder meter met gekozen apparaten (v0.165.0) telt hun vermogen op, en sinds v0.168.0
 * hun stroom en spanning als die er zijn (`entities.current`, `entities.voltage`): de ampères zijn
 * de gemeten stroom, of het vermogen gedeeld door de gemeten spanning van de groep. Zonder enige
 * spanning en niet bij elk apparaat een stroom: alleen het vermogen, en de balk op 230 V. Dezelfde som
 * als `groep_apparaten_amps` in planner.py.
 *
 * @returns {Array<{id: string, name: string, kind: string, parent: string, fuse: number, count: number,
 *   phases: Array, via?: string[], measured: boolean}>}
 */
export function readCircuits(feed, installation, devices = []) {
  const groepen = Array.isArray(installation?.circuits) ? installation.circuits : [];
  const opId = new Map((devices ?? []).filter((d) => d?.id).map((d) => [d.id, d]));
  const heeft = (row) => row.current !== null || row.power !== null || row.voltage !== null;
  return groepen
    .filter((g) => g?.id)
    .map((g) => {
      const een = Number(g.phases) === 1;
      const keys = een ? ["l1"] : PHASES;
      // Zonder keuze de fase van de batterij die eraan hangt, zoals Installatie hem voorstelt.
      const fase = g.phase || (devices ?? []).find((d) => d?.circuit === g.id && d.battery?.phase)?.battery.phase || "l1";
      const label = (key) => (een ? String(fase) : key).toUpperCase();
      const basis = {
        id: g.id, name: g.name || g.id, kind: g.kind === "kast" ? "kast" : "groep", parent: g.parent || "",
        fuse: Number(g.fuse_amps) || 0, count: een ? 1 : 3,
      };
      const gekozen = g.meter === false && Array.isArray(g.devices) ? g.devices.filter((r) => opId.get(r?.device)?.entity) : [];
      if (gekozen.length) {
        const apparaat = (r) => opId.get(r.device);
        const watt = gekozen.map((r) => readPower(feed, apparaat(r).entity));
        const stroom = gekozen.map((r) => readNumber(feed, apparaat(r).entities?.current));
        const volt = gekozen.map((r) => readNumber(feed, apparaat(r).entities?.voltage)).find((v) => Number.isFinite(v) && v > 0) ?? null;
        const compleet = watt.every((w) => Number.isFinite(w));
        const phases = keys.map((key) => {
          const hier = gekozen.map((r, i) => i).filter((i) => (een ? "l1" : gekozen[i].phase || "l1") === key);
          const power = compleet ? hier.reduce((som, i) => som + Math.max(0, watt[i]), 0) : null;
          const stroomBekend = hier.every((i) => Number.isFinite(stroom[i]));
          // De balk rekent zoals de coach: een gemeten stroom, anders het vermogen door de gemeten
          // spanning, en zonder spanning door 230 V. Een getal in ampère staat er alleen als het gemeten is.
          const amps = compleet
            ? hier.reduce((som, i) => som + (Number.isFinite(stroom[i]) ? Math.abs(stroom[i]) : Math.max(0, watt[i]) / (volt ?? NOMINAL_VOLTS)), 0)
            : null;
          const current = amps !== null && hier.length && (stroomBekend || volt !== null) ? amps : null;
          const voltage = hier.length ? volt : null;
          return { key, label: label(key), current, power, voltage, amps, ampsDerived: current === null && amps !== null };
        });
        // Gemeten via apparaten is gemeten, ook als een plug even niets zegt: dan "geen meetwaarde".
        return { ...basis, phases, via: gekozen.map((r) => apparaat(r).name || r.device), measured: true };
      }
      const phases = keys.map((key) => {
        const config = g.sensors?.[key] ?? {};
        const row = {
          key,
          label: label(key),
          current: readNumber(feed, config.current),
          power: readPower(feed, config.power),
          voltage: readNumber(feed, config.voltage),
        };
        row.amps = phaseAmps(row);
        row.ampsDerived = row.amps !== null && !Number.isFinite(row.current);
        return row;
      });
      return { ...basis, phases, measured: phases.some(heeft) };
    });
}

/**
 * How hard the connection is being worked, as a percentage.
 *
 * With per-phase currents this is the *heaviest* phase against the main fuse,
 * not the average: a fuse blows on the phase that is overloaded, and averaging
 * three phases hides exactly the case worth warning about.
 *
 * Without phase sensors it falls back to total grid power against the
 * connection's ceiling, which is the same question at lower resolution.
 *
 * Only import counts. Feeding back also loads the connection, but the ceiling a
 * customer cares about -- and the one their fuse enforces -- is what they draw.
 *
 * Sinds v0.75.0 telt elke groep met een eigen zekering mee, tegen haar eigen
 * zekering: een garage van 16 A op 14 A is zwaarder belast dan een aansluiting
 * van 25 A op 15. Dezelfde som als `async_current_load` in monitor.py.
 *
 * @returns {{percent: number|null, basis: "phase"|"power"|null, worst: string|null}}
 */
export function loadOf(phases, importW, installation, circuits = []) {
  const fuse = Number(installation?.fuse_amps) || 0;

  const kandidaten = [];
  if (phases && fuse > 0) kandidaten.push({ fuse, label: "", phases });
  for (const g of circuits ?? []) {
    if (g?.fuse > 0 && Array.isArray(g.phases)) kandidaten.push({ fuse: g.fuse, label: g.name, phases: g.phases });
  }
  let zwaarste = null;
  for (const k of kandidaten) {
    for (const p of k.phases) {
      if (!Number.isFinite(p.amps)) continue;
      const share = (p.amps / k.fuse) * 100;
      if (!zwaarste || share > zwaarste.share) {
        zwaarste = { share, worst: k.label ? `${p.label} (${k.label})` : p.label };
      }
    }
  }
  if (zwaarste) {
    return { percent: clamp(zwaarste.share, 0, 999), basis: "phase", worst: zwaarste.worst };
  }

  const ceiling = Number(installation?.max_grid_watts) || 0;
  if (ceiling > 0 && Number.isFinite(importW)) {
    return { percent: clamp((importW / ceiling) * 100, 0, 999), basis: "power", worst: null };
  }

  return { percent: null, basis: null, worst: null };
}

/** Rolling history, for the sparklines. */
class History {
  constructor() {
    this.rows_ = [];
  }

  push(reading) {
    this.rows_.push(reading);
    if (this.rows_.length > HISTORY) this.rows_.shift();
  }

  series(key, length = 40) {
    return this.rows_
      .slice(-length)
      .map((r) => (Number.isFinite(r[key]) ? Math.abs(r[key]) : 0));
  }
}

/**
 * Turn solar and export into the self-consumption share.
 *
 * Zelfbenutting is the part of your own production you use yourself, so it only
 * means anything while the panels are producing. At night it is not zero, it is
 * undefined -- and showing 0% then would read as a failing grade for doing
 * nothing wrong.
 */
function selfUseOf(solar, exportW) {
  if (solar === null || solar <= 0) return null;
  const used = solar - Math.max(0, exportW ?? 0);
  return clamp((used / solar) * 100, 0, 100);
}

export class LiveSource {
  constructor() {
    this.history_ = new History();
  }

  /**
   * @param {import("./state-feed.js").StateFeed} feed
   * @param {object} settings the panel's settings document
   */
  sample(feed, settings) {
    const sources = settings?.sources ?? {};

    const solar = readSolarAll(feed, sources);

    let importW = null;
    let exportW = null;
    if (sources.grid_mode === "signed") {
      // One sensor that swings negative while feeding back -- unless the meter
      // has it the other way round, which some do.
      const signed = readPower(feed, sources.grid_signed);
      if (signed !== null) {
        const value = sources.grid_signed_invert ? -signed : signed;
        importW = Math.max(0, value);
        exportW = Math.max(0, -value);
      }
    } else {
      // Two sensors, of which one is always zero.
      const a = readPower(feed, sources.grid_import);
      const b = readPower(feed, sources.grid_export);
      if (a !== null || b !== null) {
        importW = Math.max(0, a ?? 0);
        exportW = Math.max(0, b ?? 0);
      }
    }

    const grid = importW === null ? null : importW - exportW;

    // Consumption is always derived, never configured: it is exactly generation
    // plus whatever the meter says, so asking for a third sensor only adds a
    // way for the three to disagree.
    // Een thuisbatterij is geen verbruiker: wat hij afgeeft heeft het huis
    // gebruikt en wat hij opneemt niet. Zonder deze som stond er bij Woning
    // nul terwijl de batterij het hele huis voedde.
    const batterijen = (settings?.devices ?? [])
      .filter((device) => device.type === "thuisbatterij")
      .map((device) => batteryWatts(feed, device));
    const batterij = batterijen.reduce((som, w) => som + (w ?? 0), 0);
    const house = solar !== null && grid !== null ? Math.max(0, solar + grid - batterij) : null;

    const devices = (settings?.devices ?? []).map((device) => {
      if (device.type !== "thuisbatterij") {
        return {
          ...device,
          watts: readPower(feed, device.entity),
          details: deviceDetails(feed, device, settings),
        };
      }
      // Op de kaart het vermogen zonder teken, met erbij welke kant het op
      // gaat: een bolletje met een minteken leest als een storing.
      const w = batteryWatts(feed, device);
      const richting = w === null ? null : w > 3 ? t("laadt") : w < -3 ? t("ontlaadt") : t("staat stil");
      return {
        ...device,
        watts: w === null ? null : Math.abs(w),
        batteryWatts: w,
        details: [
          ...(richting ? [{ label: t("Doet nu"), text: richting }] : []),
          ...deviceDetails(feed, device, settings),
        ],
      };
    });

    const phases = readPhases(feed, sources);
    const circuits = readCircuits(feed, settings?.installation, settings?.devices);
    const load = loadOf(phases, importW, settings?.installation, circuits);

    const reading = {
      solar,
      house,
      grid,
      importW,
      exportW,
      selfUse: selfUseOf(solar, exportW),
      price: priceNow(feed, settings?.contract),
      devices,
      phases,
      circuits,
      load: load.percent,
      loadBasis: load.basis,
      loadWorstPhase: load.worst,
    };

    this.history_.push(reading);
    return reading;
  }

  series(key, length) {
    return this.history_.series(key, length);
  }

  /** True once at least one of the core sources is set. */
  static isConfigured(settings) {
    const s = settings?.sources ?? {};
    const grid =
      s.grid_mode === "signed" ? s.grid_signed : s.grid_import || s.grid_export;
    return Boolean(solarEntities(s).length || grid);
  }
}
