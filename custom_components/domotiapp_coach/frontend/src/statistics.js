/**
 * Looking back, without keeping a shred of history ourselves.
 *
 * Home Assistant already stores this. Next to the raw history it keeps
 * long-term statistics: one summary row per entity per hour, and those are
 * never purged. That is exactly what the energy dashboard draws, and asking for
 * it costs nothing -- ten energy entities come to some 88.000 rows a year, a
 * few megabyte. Keeping a second copy in this integration would be larger,
 * slower and wrong the first time somebody corrected a meter reading.
 *
 * Every counter is asked for as `change`: how much went through it during that
 * hour, day or month. That is the figure a customer means by "what did I use
 * yesterday", and it is the only one that survives a meter that resets or an
 * entity that gets replaced.
 *
 * Units are converted by Home Assistant rather than here. One customer's meter
 * counts in Wh and the next in MWh, and asking for kWh means never finding out
 * the hard way which one this is.
 */

/** How a period is cut into bars. */
export const PERIODS = [
  { id: "day", label: "Dag", bucket: "hour" },
  { id: "week", label: "Week", bucket: "day" },
  { id: "month", label: "Maand", bucket: "day" },
  { id: "year", label: "Jaar", bucket: "month" },
];

/** The first moment of the period `offset` steps back from today. */
export function periodStart(period, offset) {
  const at = new Date();
  at.setHours(0, 0, 0, 0);

  switch (period) {
    case "day":
      at.setDate(at.getDate() + offset);
      return at;
    case "week": {
      // Monday, the way a week is written down here.
      const weekday = (at.getDay() + 6) % 7;
      at.setDate(at.getDate() - weekday + offset * 7);
      return at;
    }
    case "month":
      at.setDate(1);
      at.setMonth(at.getMonth() + offset);
      return at;
    default:
      at.setMonth(0, 1);
      at.setFullYear(at.getFullYear() + offset);
      return at;
  }
}

/** The first moment after the period that starts at `start`. */
export function periodEnd(period, start) {
  const at = new Date(start);
  switch (period) {
    case "day":
      at.setDate(at.getDate() + 1);
      return at;
    case "week":
      at.setDate(at.getDate() + 7);
      return at;
    case "month":
      at.setMonth(at.getMonth() + 1);
      return at;
    default:
      at.setFullYear(at.getFullYear() + 1);
      return at;
  }
}

/** What the period is called on screen. */
export function periodLabel(period, start) {
  const opts = {
    day: { weekday: "long", day: "numeric", month: "long" },
    week: { day: "numeric", month: "long" },
    month: { month: "long", year: "numeric" },
    year: { year: "numeric" },
  }[period];

  if (period === "week") {
    const end = new Date(periodEnd(period, start).getTime() - 1);
    return `${start.toLocaleDateString("nl-NL", opts)} tot ${end.toLocaleDateString("nl-NL", opts)}`;
  }
  return start.toLocaleDateString("nl-NL", opts);
}

/**
 * Which of these entities Home Assistant actually keeps statistics for.
 *
 * A sensor only gets them when it declares itself a total; plenty of energy
 * sensors do not, and asking for one that has none simply returns nothing.
 * Knowing which is which is what lets the screen say "this meter has no
 * history" instead of drawing an empty chart.
 *
 * @returns {Promise<Set<string>>}
 */
export async function withStatistics(hass, ids) {
  const wanted = ids.filter(Boolean);
  if (!wanted.length || !hass) return new Set();

  try {
    const rows = await hass.callWS({
      type: "recorder/list_statistic_ids",
      statistic_type: "sum",
    });
    const known = new Set(rows.map((row) => row.statistic_id));
    return new Set(wanted.filter((id) => known.has(id)));
  } catch (error) {
    console.warn("[DomotiApp Coach] kon de statistieken niet opvragen", error);
    return new Set();
  }
}

/**
 * How much went through each counter, per bucket, over one period.
 *
 * @returns {Promise<Map<string, Array<{start: Date, change: number}>>>}
 */
export async function fetchPeriod(hass, ids, period, start) {
  const wanted = [...new Set(ids.filter(Boolean))];
  const out = new Map();
  if (!wanted.length || !hass) return out;

  const bucket = PERIODS.find((item) => item.id === period)?.bucket ?? "day";

  try {
    const result = await hass.callWS({
      type: "recorder/statistics_during_period",
      start_time: start.toISOString(),
      end_time: periodEnd(period, start).toISOString(),
      statistic_ids: wanted,
      period: bucket,
      types: ["change"],
      // Converted by Home Assistant, because one customer's meter counts in Wh
      // and the next in MWh.
      units: { energy: "kWh", volume: "m³" },
    });

    for (const [id, rows] of Object.entries(result ?? {})) {
      out.set(
        id,
        (rows ?? [])
          .filter((row) => row.change !== null && row.change !== undefined)
          // `start` arrives as milliseconds since the epoch, not as a string.
          .map((row) => ({ start: new Date(row.start), change: Number(row.change) }))
      );
    }
  } catch (error) {
    console.warn("[DomotiApp Coach] kon de historie niet ophalen", error);
  }

  return out;
}

/** Add up several counters into one series, bucket by bucket. */
export function combine(series, ids) {
  const total = new Map();

  for (const id of ids) {
    for (const row of series.get(id) ?? []) {
      const key = row.start.getTime();
      total.set(key, (total.get(key) ?? 0) + row.change);
    }
  }

  return [...total.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([time, value]) => ({ start: new Date(time), value }));
}
