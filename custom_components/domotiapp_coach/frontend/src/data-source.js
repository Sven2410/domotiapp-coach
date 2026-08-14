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

import { toWatts } from "./format.js";

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
 * What a kWh costs right now, from the contract rather than from a single
 * sensor.
 *
 * A fixed contract is a number the installer typed in. A dynamic one is either
 * an entity that already carries the all-in price, or a bare market price that
 * still needs energy tax and the supplier's markup added and VAT applied over
 * the lot -- which is the order the Dutch bill uses, and getting it wrong is a
 * couple of cents per kWh in the coach's advice.
 *
 * @returns {number|null} euro per kWh
 */
export function priceNow(feed, contract) {
  if (!contract) return null;

  if (contract.type === "fixed") {
    const value = Number(contract.fixed?.all_in_price);
    return Number.isFinite(value) ? value : null;
  }

  const dynamic = contract.dynamic ?? {};
  if (dynamic.source === "all_in") return readPrice(feed, dynamic.all_in_entity);

  const market = readPrice(feed, dynamic.market_entity);
  if (market === null) return null;

  const tax = Number(dynamic.energy_tax) || 0;
  const markup = Number(dynamic.supplier_markup) || 0;
  const vat = Number(dynamic.vat_percent) || 0;
  return (market + tax + markup) * (1 + vat / 100);
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

    const solar = readPower(feed, sources.solar);

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

    // The house sensor is optional: with solar and the grid known, consumption
    // follows from them, and one less mandatory sensor is one less thing to get
    // wrong at a customer.
    let house = readPower(feed, sources.house);
    if (house === null && solar !== null && grid !== null) house = solar + grid;

    const devices = (settings?.devices ?? []).map((device) => ({
      ...device,
      watts: readPower(feed, device.entity),
    }));

    const reading = {
      solar,
      house,
      grid,
      importW,
      exportW,
      selfUse: selfUseOf(solar, exportW),
      price: priceNow(feed, settings?.contract),
      devices,
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
    return Boolean(s.solar || s.house || grid);
  }
}
