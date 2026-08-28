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

/**
 * Hetzelfde vermogen, maar met het teken erbij.
 *
 * `power` laat het teken weg, en op de meeste plekken in het paneel klopt dat:
 * daar zegt een kleur of een pijl al welke kant het op gaat. Op de fasekaart
 * staat het getal alleen, en dan is het teken het enige dat de richting nog
 * vertelt.
 *
 * Het teken komt er alleen bij als er na afronden ook werkelijk iets staat. Een
 * meting van -0,4 W is "0 W" en niet "-0 W": een min voor een nul leest als een
 * fout terwijl er niets fout is.
 */
export function signedPower(watts) {
  const uit = power(watts);
  if (!Number.isFinite(watts) || watts > -0.5) return uit;
  return { value: `-${uit.value}`, unit: uit.unit };
}

/**
 * Afronden zonder dat er een negatieve nul overblijft.
 *
 * Een stroom van -0,017 A wordt op een decimaal "-0,0", en dat is precies zo'n
 * getal waar een klant over belt. Gevonden bij de eerste woning met een P1 die
 * per fase een teken meegeeft.
 */
export function zonderMinNul(value, digits = 1) {
  if (!Number.isFinite(value)) return value;
  const factor = 10 ** digits;
  const afgerond = Math.round(value * factor) / factor;
  return afgerond === 0 ? 0 : afgerond;
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

/**
 * A length of time in words: "45 min", "1 u 45 min", "3 u".
 *
 * Minutes rather than seconds throughout, because everything measured in these
 * terms -- a wash programme, a charge, the time until something is done -- is
 * planned in minutes and a ticking second count reads as more precision than
 * the appliance actually has.
 */
export function duration(minutes) {
  const total = Math.round(Number(minutes));
  if (!Number.isFinite(total) || total < 0) return "—";
  if (total < 60) return `${total} min`;

  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return rest ? `${hours} u ${rest} min` : `${hours} u`;
}

/** A time of day from a Date, as "21:30". */
export const clock = (date) =>
  date.toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" });

/**
 * An ISO timestamp, or null for anything else.
 *
 * Matched on the shape rather than handed to `new Date` on spec: that
 * constructor accepts far more than it should -- "16" becomes a date -- and a
 * sensor reading that happens to be a bare number must never be mistaken for a
 * moment in time.
 */
function asDate(raw) {
  if (!/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(String(raw))) return null;
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * "nog 1 u 45 min (klaar om 21:30)" from whatever the appliance reports.
 *
 * Home Connect gives the moment the program finishes, as a timestamp; other
 * integrations give the minutes or seconds left. Both are the same question,
 * and the answer people want is how long they still have to wait.
 *
 * Returns null when the value is neither, so the caller can fall back to
 * showing it as it came.
 */
export function countdown(raw, unit) {
  const number = Number(raw);
  if (raw !== "" && Number.isFinite(number)) {
    const minutes = unit === "s" || unit === "sec" ? number / 60 : number;
    return minutes <= 0 ? "Klaar" : `nog ${duration(minutes)}`;
  }

  const end = asDate(raw);
  if (!end) return null;

  const minutes = (end.getTime() - Date.now()) / 60_000;
  if (minutes <= 0) return "Klaar";
  return `nog ${duration(minutes)} (klaar om ${clock(end)})`;
}

/**
 * A moment in words: "vandaag 08:00", "14-08 21:30".
 *
 * Entities whose state is a timestamp are common -- every button reports when
 * it was last pressed -- and a raw ISO string in a badge is unreadable at
 * exactly the moment it is meant to help: checking you picked the right one.
 */
export function moment(raw) {
  const date = asDate(raw);
  if (!date) return null;

  const today = new Date();
  const sameDay =
    date.getDate() === today.getDate() &&
    date.getMonth() === today.getMonth() &&
    date.getFullYear() === today.getFullYear();

  if (sameDay) return `vandaag ${clock(date)}`;
  return `${date.toLocaleDateString(LOCALE, { day: "2-digit", month: "2-digit" })} ${clock(date)}`;
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
