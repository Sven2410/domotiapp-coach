/**
 * Where the dashboard gets its numbers.
 *
 * Two sources behind one shape: `LiveSource` reads the entities the customer
 * mapped under Instellingen, `DemoSource` simulates a house so a fresh install
 * still shows a working dashboard before anything is wired up. Every view reads
 * the same reading object and neither knows which one it got.
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
import { ACTIVE_WATTS } from "./devices.js";

const HISTORY = 60;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** Read one entity as watts, or null when it is missing or unusable. */
function readPower(hass, entityId) {
  if (!entityId) return null;
  const state = hass?.states?.[entityId];
  if (!state || state.state === "unavailable" || state.state === "unknown") return null;
  return toWatts(state.state, state.attributes?.unit_of_measurement);
}

/**
 * Read a price sensor as euro per kWh.
 *
 * Suppliers publish in both euro and cents, so the unit decides -- a tariff read
 * as 0.24 when it is really 24 cents would have the coach calling the evening
 * peak cheap.
 */
function readPrice(hass, entityId) {
  if (!entityId) return null;
  const state = hass?.states?.[entityId];
  if (!state || state.state === "unavailable" || state.state === "unknown") return null;

  const value = Number(state.state);
  if (!Number.isFinite(value)) return null;

  const unit = String(state.attributes?.unit_of_measurement ?? "").toLowerCase();
  if (unit.includes("ct") || unit.includes("cent")) return value / 100;
  return value;
}

/** Shared history buffer, so both sources feed the sparklines the same way. */
class History {
  constructor() {
    this.rows_ = [];
  }

  push(reading) {
    this.rows_.push(reading);
    if (this.rows_.length > HISTORY) this.rows_.shift();
  }

  /** Recent absolute values for one key, for a sparkline. */
  series(key, length = 40) {
    return this.rows_
      .slice(-length)
      .map((r) => (Number.isFinite(r[key]) ? Math.abs(r[key]) : 0));
  }
}

/**
 * Turn solar, grid and export into the self-consumption share.
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
    this.live = true;
  }

  /**
   * @param {object} hass Home Assistant state object
   * @param {object} settings the panel's settings document
   */
  sample(hass, settings) {
    const sources = settings?.sources ?? {};

    const solar = readPower(hass, sources.solar);

    let importW = null;
    let exportW = null;
    if (sources.grid_mode === "signed") {
      // One sensor that swings negative while feeding back -- unless the meter
      // has it the other way round, which some do.
      const signed = readPower(hass, sources.grid_signed);
      if (signed !== null) {
        const value = sources.grid_signed_invert ? -signed : signed;
        importW = Math.max(0, value);
        exportW = Math.max(0, -value);
      }
    } else {
      // Two sensors, of which one is always zero.
      const a = readPower(hass, sources.grid_import);
      const b = readPower(hass, sources.grid_export);
      if (a !== null || b !== null) {
        importW = Math.max(0, a ?? 0);
        exportW = Math.max(0, b ?? 0);
      }
    }

    const grid = importW === null ? null : importW - exportW;

    // The house sensor is optional: with solar and the grid known, consumption
    // follows from them, and one less mandatory sensor is one less thing to get
    // wrong at a customer.
    let house = readPower(hass, sources.house);
    if (house === null && solar !== null && grid !== null) house = solar + grid;

    const devices = (settings?.devices ?? []).map((device) => ({
      ...device,
      watts: readPower(hass, device.entity),
    }));

    const reading = {
      solar,
      house,
      grid,
      importW,
      exportW,
      selfUse: selfUseOf(solar, exportW),
      price: readPrice(hass, sources.price),
      devices,
      live: true,
    };

    this.history_.push(reading);
    return reading;
  }

  series(key, length) {
    return this.history_.series(key, length);
  }

  /** True once at least one of the core sources resolves to a number. */
  static isConfigured(settings) {
    const s = settings?.sources ?? {};
    const grid =
      s.grid_mode === "signed" ? s.grid_signed : s.grid_import || s.grid_export;
    return Boolean(s.solar || s.house || grid);
  }
}

// ---------------------------------------------------------------------------
// Demo
// ---------------------------------------------------------------------------

/** Smooth random walk that stays inside [lo, hi]. */
class Drift {
  constructor(value, step, lo, hi) {
    this.value = value;
    this.step = step;
    this.lo = lo;
    this.hi = hi;
  }

  next() {
    this.value = clamp(this.value + (Math.random() - 0.5) * this.step * 2, this.lo, this.hi);
    return this.value;
  }
}

/** Bell-shaped solar yield over the day, peaking around 13:30. */
function solarPotential(hours) {
  const value = Math.exp(-((hours - 13.5) ** 2) / (2 * 3.1 ** 2));
  return value < 0.02 ? 0 : value;
}

/** Rough day-ahead price shape: cheap at night and midday, expensive at 18:00. */
function priceShape(hours) {
  const evening = Math.exp(-((hours - 18.5) ** 2) / 5.5);
  const morning = Math.exp(-((hours - 8) ** 2) / 6.0);
  const midday = Math.exp(-((hours - 13.5) ** 2) / 7.0);
  return 0.11 + evening * 0.26 + morning * 0.1 - midday * 0.07;
}

/**
 * A simulated house, used until the customer maps their sensors.
 *
 * The values stay physically consistent (grid = house - solar) because
 * independent random numbers would make it impossible to tell a wrong diagram
 * from wrong data. It runs an accelerated day rather than the wall clock, so a
 * dashboard opened at night still shows something happening.
 */
export class DemoSource {
  constructor({ peakPower = 6400, startHour = 10.5, hoursPerTick = 0.08 } = {}) {
    this.peakPower = peakPower;
    this.hoursPerTick = hoursPerTick;
    this.hours = startHour;
    this.clouds = new Drift(0.85, 0.09, 0.15, 1);
    this.base = new Drift(420, 50, 240, 750);
    this.history_ = new History();
    this.live = false;

    // Three plausible devices so the two bubbles and the "meer" roll-up can be
    // judged before a customer has any of their own.
    this.devices_ = [
      { id: "demo-1", type: "laadpaal", name: "", entity: "", duty: 0.30, watts: 0, left: 0, load: 5200 },
      { id: "demo-2", type: "vaatwasser", name: "", entity: "", duty: 0.22, watts: 0, left: 0, load: 1900 },
      { id: "demo-3", type: "boiler", name: "", entity: "", duty: 0.26, watts: 0, left: 0, load: 1400 },
    ];
  }

  tickDevices_() {
    for (const device of this.devices_) {
      if (device.left > 0) {
        device.left -= 1;
        device.watts = device.load * (0.85 + Math.random() * 0.3);
      } else if (Math.random() < device.duty * 0.12) {
        device.left = 6 + Math.floor(Math.random() * 14);
        device.watts = device.load;
      } else {
        device.watts = Math.random() * ACTIVE_WATTS * 0.4;
      }
    }
    return this.devices_.map(({ id, type, name, entity, watts }) => ({
      id,
      type,
      name,
      entity,
      watts,
    }));
  }

  sample() {
    this.hours = (this.hours + this.hoursPerTick) % 24;

    const solar = solarPotential(this.hours) * this.peakPower * this.clouds.next();
    const devices = this.tickDevices_();
    const deviceLoad = devices.reduce((sum, d) => sum + d.watts, 0);
    const house = this.base.next() + deviceLoad;

    const grid = house - solar;
    const importW = Math.max(0, grid);
    const exportW = Math.max(0, -grid);
    const price = clamp(priceShape(this.hours) + (Math.random() - 0.5) * 0.012, 0.04, 0.55);

    const reading = {
      solar,
      house,
      grid,
      importW,
      exportW,
      selfUse: selfUseOf(solar, exportW),
      price,
      devices,
      live: false,
    };

    this.history_.push(reading);
    return reading;
  }

  series(key, length) {
    return this.history_.series(key, length);
  }
}
