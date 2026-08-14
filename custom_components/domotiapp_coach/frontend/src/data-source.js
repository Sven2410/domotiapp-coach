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

import { brandFields } from "./devices.js";
import { toWatts } from "./format.js";

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

/** Read a plain numeric entity, in whatever unit it reports. */
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
function deviceDetails(feed, device) {
  const rows = [];

  for (const field of brandFields(device)) {
    const entityId = device.entities?.[field.key];
    if (!entityId) continue;

    const state = feed.get(entityId);
    if (!usable(state)) {
      rows.push({ label: field.label, text: "—" });
      continue;
    }

    const raw = String(state.state);
    const number = Number(raw);
    const unit = state.attributes?.unit_of_measurement;
    // A brand may report words rather than numbers; those are translated where
    // we know them and passed through where we do not.
    const text =
      field.values?.[raw] ??
      (Number.isFinite(number)
        ? `${number.toLocaleString("nl-NL", { maximumFractionDigits: 2 })}${unit ? ` ${unit}` : ""}`
        // A word we have no translation for is still shown -- readable, but
        // recognisably the sensor's own wording rather than something invented.
        : raw.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()));

    rows.push({ label: field.label, text });
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
 * @returns {{percent: number|null, basis: "phase"|"power"|null, worst: string|null}}
 */
export function loadOf(phases, importW, installation) {
  const fuse = Number(installation?.fuse_amps) || 0;

  if (phases && fuse > 0) {
    const loaded = phases.filter((p) => Number.isFinite(p.amps));
    if (loaded.length) {
      const worst = loaded.reduce((a, b) => (b.amps > a.amps ? b : a));
      return {
        percent: clamp((worst.amps / fuse) * 100, 0, 999),
        basis: "phase",
        worst: worst.label,
      };
    }
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

    // Consumption is always derived, never configured: it is exactly generation
    // plus whatever the meter says, so asking for a third sensor only adds a
    // way for the three to disagree.
    const house = solar !== null && grid !== null ? solar + grid : null;

    const devices = (settings?.devices ?? []).map((device) => ({
      ...device,
      watts: readPower(feed, device.entity),
      details: deviceDetails(feed, device),
    }));

    const phases = readPhases(feed, sources);
    const load = loadOf(phases, importW, settings?.installation);

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
    return Boolean(s.solar || grid);
  }
}
