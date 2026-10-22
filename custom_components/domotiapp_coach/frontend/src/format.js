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

import { locale, t } from "./i18n.js";


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
  value.toLocaleString(locale(), {
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
  return rest ? t("{u} u {m} min", { u: hours, m: rest }) : t("{u} u", { u: hours });
}

/** A time of day from a Date, as "21:30". */
export const clock = (date) =>
  date.toLocaleTimeString(locale(), { hour: "2-digit", minute: "2-digit" });

/*
 * De klok van het huis (v0.138.1). De coach schrijft elke tijd in de tijd van Home
 * Assistant en zonder tijdzone ("2026-10-19T15:45:00"); de browser leest zo'n tijd als
 * zijn eigen tijd. Dat klopt zolang de browser in dezelfde tijdzone staat als het huis.
 * Bij een woning in Portugal, bekeken vanaf een pc in Nederland, stond "nu" in de
 * prijsgrafiek daardoor een uur verder dan de vooruitblik erboven. Daarom rekent het
 * paneel "nu" in de tijd van het huis: een Date waarvan uur en dag die van het huis zijn,
 * zoals de tijden van de coach ook binnenkomen. Wat uit Home Assistant zelf komt met een
 * tijdzone erbij (een prijssensor) gaat door `alsHuis`. Zonder tijdzone (de preview, de
 * proeven) is het gewoon de klok van de browser.
 */
let huisZone_ = null;
let huisKlok_ = null;

/** De tijdzone van het huis, uit `hass.config.time_zone`; de panel-module zet hem. */
export function zetHuisZone(zone) {
  const nieuw = typeof zone === "string" && zone ? zone : null;
  if (nieuw === huisZone_) return;
  huisZone_ = nieuw;
  try {
    huisKlok_ = nieuw ? new Intl.DateTimeFormat("en-CA", {
      timeZone: nieuw, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
    }) : null;
  } catch {
    // Een tijdzone die de browser niet kent: dan de klok van de browser.
    huisZone_ = null;
    huisKlok_ = null;
  }
}

/** De velden van een Date in de tijd van de browser, als één getal om te vergelijken. */
const veld_ = (x) => Date.UTC(x.getFullYear(), x.getMonth(), x.getDate(), x.getHours(), x.getMinutes(), x.getSeconds(), x.getMilliseconds());

/**
 * Een echt moment zoals de klok van het huis het aanwijst, als Date in de tijd van de browser.
 *
 * Wijst de browser op dat moment hetzelfde aan als het huis, dan het moment zelf (v0.138.2).
 * Anders vielen bij het ingaan van de wintertijd de twee uren van 02:00 samen, ook bij een
 * Nederlands huis vanuit Nederland, en verloor Historie zo een uur verbruik.
 */
export function alsHuis(moment) {
  const echt = moment instanceof Date ? moment : new Date(moment);
  if (!huisKlok_ || Number.isNaN(echt.getTime())) return echt;
  const d = Object.fromEntries(huisKlok_.formatToParts(echt).map((deel) => [deel.type, deel.value]));
  const huis = new Date(Number(d.year), Number(d.month) - 1, Number(d.day), Number(d.hour), Number(d.minute), Number(d.second), echt.getMilliseconds());
  return veld_(huis) === veld_(echt) ? echt : huis;
}

/**
 * Het omgekeerde van `alsHuis` (v0.138.2): een Date op de klok van het huis terug naar het
 * echte moment, voor wat Home Assistant om echte momenten vraagt (de recorder, de
 * kwartieropslag) of ermee rekent (`ptPrijsOp`). Twee of drie stappen, omdat het verschil
 * tussen de twee klokken zelf van het moment afhangt (zomertijd).
 */
export function vanHuis(huis) {
  const d = huis instanceof Date ? huis : new Date(huis);
  if (!huisKlok_ || Number.isNaN(d.getTime())) return d;
  // Dezelfde klok als de browser: het moment is er al.
  if (alsHuis(d) === d) return d;
  const doel = veld_(d);
  let t = doel;
  for (let stap = 0; stap < 3; stap += 1) {
    const afwijking = doel - veld_(alsHuis(new Date(t)));
    if (!afwijking) break;
    t += afwijking;
  }
  return new Date(t);
}

/** Nu, op de klok van het huis. Vergelijk tijden van de coach hiermee, niet met `new Date()`. */
export const huisNu = () => alsHuis(new Date());

/**
 * Een tijd uit Home Assistant op de klok van het huis: met een tijdzone erbij ("Z",
 * "+02:00") omgerekend, zonder (zoals de coach ze schrijft) zoals hij is.
 */
export function huisTijd(raw) {
  if (raw instanceof Date) return raw;
  // Milliseconden sinds 1970 zijn een echt moment.
  if (typeof raw === "number") return alsHuis(new Date(raw));
  const tekst = String(raw ?? "");
  return /(?:Z|[+-]\d{2}:?\d{2})$/.test(tekst.trim()) ? alsHuis(new Date(tekst)) : new Date(tekst);
}

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
    // Home Connect Local telt in seconden en Home Assistant toont dat als
    // uren (1,4833 h thuis op 23-09-2026); zonder eenheid zijn het minuten.
    const eenheid = String(unit ?? "").toLowerCase();
    const minutes =
      eenheid === "s" || eenheid === "sec" || eenheid === "seconds" ? number / 60
      : eenheid === "h" || eenheid === "hr" || eenheid === "hrs" || eenheid === "hours" || eenheid === "uur" || eenheid === "u" ? number * 60
      : eenheid === "d" || eenheid === "days" || eenheid === "dagen" ? number * 1440
      : number;
    return minutes <= 0 ? t("Klaar") : t("nog {duur}", { duur: duration(minutes) });
  }

  const end = asDate(raw);
  if (!end) return null;

  const minutes = (end.getTime() - Date.now()) / 60_000;
  if (minutes <= 0) return t("Klaar");
  return t("nog {duur} (klaar om {klok})", { duur: duration(minutes), klok: clock(end) });
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

  if (sameDay) return t("vandaag {klok}", { klok: clock(date) });
  return `${date.toLocaleDateString(locale(), { day: "2-digit", month: "2-digit" })} ${clock(date)}`;
}

/**
 * Een waarde op een apparaatkaart begint met een hoofdletter (v0.119.2). De
 * eigenaar op 14-10-2026, bij "ontlaadt" en "ongeveer 89%, gemeten in de accu"
 * op de batterijkaart: "even alles met een hoofdletter beginnen." Op één plek
 * en niet in elke tekst, zodat dezelfde tekst midden in een zin klein blijft.
 * Een getal of een teken vooraan ("58 %", "€ 4,26") blijft zoals het is.
 */
export const metHoofdletter = (tekst) => String(tekst ?? "").replace(/^\p{Ll}/u, (c) => c.toUpperCase());

/** Format euro amounts. */
export function euro(value) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `€ ${num(value, 2)}`;
}

/**
 * Een bedrag in In geld (v0.147.1): een tekort met het minteken vooraan, zoals bij
 * teruglevering ("− € 0,05"), en wat op nul afrondt als "€ 0,00", niet "€ -0,00".
 * Thuis stond er op 22-10-2026 "€ -0,05" en "€ -0,00" naast "− € 0,09".
 */
export function geldBedrag(value) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value <= -0.005 ? `− ${euro(-value)}` : euro(Math.max(0, value));
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

/**
 * De grenzen waarmee een prijs zijn kleur krijgt (v0.133.1).
 *
 * Vast zijn het die van Voorkeuren. Met `relative` aan schalen ze mee met alle
 * prijzen die bekend zijn, van het lopende uur af: het goedkoopste derde van
 * het verschil tussen de goedkoopste en de duurste is groen, het duurste derde
 * rood. De bewoner van de eerste woning op 19-10-2026: "elke app kiest ervoor om
 * de kleurstelling van de kolommen aan te passen, relatief gezien naar de spread
 * op de dag", "Als je namelijk móet laden (ev) wil je dat op het goedkoopste
 * moment doen", en "Worden de nieuwe prijzen om 14u bekend, dan past ie zijn
 * kleurstelling aan. Het kán dan zo zijn dat een kolom die om 13.59 nog groen
 * was, rood wordt, omdat de prijzen morgen veel lager zijn." Een uur dat voorbij
 * is telt niet mee: daar valt niets meer te kiezen. Zonder bekende prijzen
 * gelden de vaste grenzen.
 *
 * Een functie per moment, zodat wie hem gebruikt niet hoeft te weten welke van
 * de twee het is.
 *
 * @param {{low:number, high:number, relative?:boolean}} bounds
 * @param {Array<{start: Date|string, end?: Date|string, price: number|null}>} rijen
 * @param {Date} [nu]
 * @returns {(moment?: Date|string) => {low:number, high:number}}
 */
export function prijsGrenzen(bounds, rijen, nu = huisNu()) {
  const vast = { low: Number(bounds?.low ?? 0.2), high: Number(bounds?.high ?? 0.3) };
  if (!bounds?.relative) return () => vast;
  const uur = new Date(nu);
  uur.setMinutes(0, 0, 0);
  let laag = Infinity;
  let hoog = -Infinity;
  for (const rij of rijen ?? []) {
    const prijs = Number(rij?.price);
    if (rij?.price === null || rij?.price === undefined || !Number.isFinite(prijs)) continue;
    const eind = rij.end !== undefined ? new Date(rij.end) : null;
    if ((eind && eind <= uur) || (!eind && new Date(rij.start) < uur)) continue;
    laag = Math.min(laag, prijs);
    hoog = Math.max(hoog, prijs);
  }
  if (!Number.isFinite(laag)) return () => vast;
  const derde = (hoog - laag) / 3;
  const grens = { low: laag + derde, high: laag + 2 * derde };
  return () => grens;
}

/** CSS variable for a status level. */
export const levelTone = (name) =>
  ({
    good: "var(--dac-good)",
    warn: "var(--dac-warn)",
    bad: "var(--dac-bad)",
    none: "var(--dac-ink-3)",
  })[name] ?? "var(--dac-ink-3)";
