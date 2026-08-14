/**
 * Units and number formatting.
 *
 * Two rules drive this module:
 *
 * 1. What a sensor calls itself is not our problem. One customer's meter reports
 *    watts, the next reports kilowatts, and the same installation mixes both --
 *    so every power reading is normalised to watts on the way in, using the
 *    entity's own unit_of_measurement. Nothing downstream ever sees kW.
 * 2. What the customer reads is chosen per value, not per sensor: under a
 *    kilowatt it shows as watts, from a kilowatt up it shows as kW. A house
 *    idling at "0,08 kW" is unreadable; "80 W" is not.
 */

const LOCALE = "nl-NL";

/** Multiplier from a sensor's stated power unit to watts. */
const POWER_TO_WATT = {
  w: 1,
  watt: 1,
  watts: 1,
  kw: 1_000,
  kilowatt: 1_000,
  mw: 1_000_000,
  megawatt: 1_000_000,
};

/** Multiplier from a sensor's stated energy unit to kilowatt-hours. */
const ENERGY_TO_KWH = {
  wh: 0.001,
  kwh: 1,
  mwh: 1_000,
};

const num = (value, digits) =>
  value.toLocaleString(LOCALE, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

/**
 * Convert a raw sensor state to watts.
 *
 * @param {string|number|null|undefined} state raw entity state
 * @param {string|null|undefined} unit the entity's unit_of_measurement
 * @returns {number|null} watts, or null when the sensor has nothing usable
 */
export function toWatts(state, unit) {
  const value = Number(state);
  if (state === null || state === undefined || state === "" || !Number.isFinite(value)) {
    return null;
  }
  // An unknown or missing unit is treated as watts: that is what the great
  // majority of power sensors report, and guessing kW would inflate the reading
  // a thousandfold -- a mistake nobody would spot as a unit problem.
  const factor = POWER_TO_WATT[String(unit ?? "").trim().toLowerCase()] ?? 1;
  return value * factor;
}

/**
 * Convert a raw sensor state to kilowatt-hours.
 *
 * @param {string|number|null|undefined} state
 * @param {string|null|undefined} unit
 * @returns {number|null}
 */
export function toKwh(state, unit) {
  const value = Number(state);
  if (state === null || state === undefined || state === "" || !Number.isFinite(value)) {
    return null;
  }
  const factor = ENERGY_TO_KWH[String(unit ?? "").trim().toLowerCase()] ?? 1;
  return value * factor;
}

/**
 * Format a power reading for display, picking the unit per value.
 *
 * Below a kilowatt it stays in watts with no decimals; from a kilowatt up it
 * switches to kW with two. The sign is dropped -- direction is carried by the
 * label ("Van het net" / "Naar het net"), never by a minus.
 *
 * @param {number|null} watts
 * @returns {{value: string, unit: string}}
 */
export function power(watts) {
  if (watts === null || watts === undefined || !Number.isFinite(watts)) {
    return { value: "—", unit: "" };
  }

  const abs = Math.abs(watts);
  if (abs < 1_000) return { value: num(Math.round(abs), 0), unit: "W" };
  return { value: num(abs / 1_000, 2), unit: "kW" };
}

/** The same reading as one string, for labels and sentences. */
export function powerText(watts) {
  const { value, unit } = power(watts);
  return unit ? `${value} ${unit}` : value;
}

/**
 * Format energy, switching from Wh to kWh at a kilowatt-hour.
 * @param {number|null} kwh
 */
export function energy(kwh) {
  if (kwh === null || kwh === undefined || !Number.isFinite(kwh)) {
    return { value: "—", unit: "" };
  }
  const abs = Math.abs(kwh);
  if (abs < 1) return { value: num(Math.round(abs * 1_000), 0), unit: "Wh" };
  return { value: num(abs, 1), unit: "kWh" };
}

/** Format a price in euro per kWh. */
export function price(value) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return { value: "—", unit: "" };
  }
  return { value: `€ ${num(value, 3)}`, unit: "/ kWh" };
}

/** Format a percentage with no decimals. */
export function percent(value) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return { value: "—", unit: "" };
  }
  return { value: num(Math.round(value), 0), unit: "%" };
}

/** Format euro amounts. */
export function euro(value) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `€ ${num(value, 2)}`;
}

/**
 * Pick a status colour from a value and two thresholds.
 *
 * @param {number|null} value
 * @param {{low:number, high:number}} bounds
 * @param {boolean} lowIsGood true when a small value is the good one (price),
 *   false when a large value is (zelfbenutting)
 * @returns {"good"|"warn"|"bad"|"none"}
 */
export function level(value, bounds, lowIsGood) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "none";
  const { low, high } = bounds;
  if (lowIsGood) {
    if (value <= low) return "good";
    return value <= high ? "warn" : "bad";
  }
  if (value < low) return "bad";
  return value < high ? "warn" : "good";
}

/** CSS variable for a status level. */
export const levelTone = (name) =>
  ({
    good: "var(--dac-good)",
    warn: "var(--dac-warn)",
    bad: "var(--dac-bad)",
    none: "var(--dac-ink-3)",
  })[name] ?? "var(--dac-ink-3)";
