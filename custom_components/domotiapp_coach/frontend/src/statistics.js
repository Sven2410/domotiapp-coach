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

/**
 * The average price per bucket, from the same statistics.
 *
 * Home Assistant keeps these for any sensor that calls itself a measurement,
 * and a price sensor does. So there is no need to reckon a whole year with
 * today's tariff: the tariff of that day is on disk.
 *
 * How exact it is depends on the period, and the screen says so. Over a day the
 * buckets are hours and a dynamic price is constant within the hour, so the sum
 * is exact. Over a week or a month a day's average is multiplied by that day's
 * consumption, which misses the fact that a house uses more at expensive hours.
 * Over a year the same applies per month.
 *
 * @returns {Promise<Map<number, number>>} bucket start in milliseconds to price
 */
export async function fetchPrices(hass, entityId, period, start) {
  const out = new Map();
  if (!entityId || !hass) return out;

  const bucket = PERIODS.find((item) => item.id === period)?.bucket ?? "day";

  try {
    const result = await hass.callWS({
      type: "recorder/statistics_during_period",
      start_time: start.toISOString(),
      end_time: periodEnd(period, start).toISOString(),
      statistic_ids: [entityId],
      period: bucket,
      types: ["mean"],
    });

    for (const row of result?.[entityId] ?? []) {
      if (row.mean === null || row.mean === undefined) continue;
      out.set(new Date(row.start).getTime(), Number(row.mean));
    }
  } catch (error) {
    console.warn("[DomotiApp Coach] kon de prijsgeschiedenis niet ophalen", error);
  }

  return out;
}

/**
 * How much a device used per bucket, whichever way it can be told.
 *
 * With an energy counter it is the same `change` as any meter, and exact. With
 * only a power sensor -- which is what every device here has, because that is
 * what puts it on the energy flow -- the average watts over a bucket times the
 * length of that bucket is the energy. That is an approximation: Home Assistant
 * averages the samples it took, so a kettle that was on for four minutes of an
 * hour is caught less precisely than a charger that ran all evening. Good
 * enough to say what a dishwasher costs in a month, not a meter reading, and
 * the report says so.
 *
 * @returns {Promise<Map<string, {rows: Map<number, number>, exact: boolean}>>}
 */
export async function fetchDevices(hass, devices, period, start) {
  const out = new Map();
  if (!hass || !devices.length) return out;

  const bucket = PERIODS.find((item) => item.id === period)?.bucket ?? "day";
  const hours = { hour: 1, day: 24, month: 730 }[bucket] ?? 24;

  const counters = devices.filter((device) => device.energy);
  const meters = devices.filter((device) => !device.energy && device.power);

  const ask = async (ids, types) => {
    if (!ids.length) return {};
    try {
      return (
        (await hass.callWS({
          type: "recorder/statistics_during_period",
          start_time: start.toISOString(),
          end_time: periodEnd(period, start).toISOString(),
          statistic_ids: ids,
          period: bucket,
          types,
          units: { energy: "kWh", power: "W" },
        })) ?? {}
      );
    } catch (error) {
      console.warn("[DomotiApp Coach] kon het verbruik per apparaat niet ophalen", error);
      return {};
    }
  };

  const [sums, means] = await Promise.all([
    ask(counters.map((device) => device.energy), ["change"]),
    ask(meters.map((device) => device.power), ["mean"]),
  ]);

  for (const device of counters) {
    const rows = new Map();
    for (const row of sums[device.energy] ?? []) {
      if (row.change === null || row.change === undefined) continue;
      rows.set(new Date(row.start).getTime(), Number(row.change));
    }
    if (rows.size) out.set(device.id, { rows, exact: true });
  }

  for (const device of meters) {
    const rows = new Map();
    for (const row of means[device.power] ?? []) {
      if (row.mean === null || row.mean === undefined) continue;
      // Gemiddeld vermogen maal de lengte van het vak, van watt naar kWh.
      rows.set(new Date(row.start).getTime(), (Number(row.mean) * hours) / 1000);
    }
    if (rows.size) out.set(device.id, { rows, exact: false });
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

/**
 * Het laagste, de piek en het gemiddelde per kwartier, uit de eigen opslag.
 *
 * De recorder van Home Assistant bewaart fijner dan een uur maar tien dagen.
 * Wat hier uitkomt gaat twee jaar terug, per kwartier, en het is het enige dat
 * over vorig jaar nog vorm heeft. Zie `archive.py` voor wat er bewaard wordt.
 *
 * Waarden zijn watt, ongeacht wat de sensor van de klant zichzelf noemt.
 *
 * @returns {Promise<Map<string, {start: Date, laagste: number, piek: number,
 *   gemiddeld: number, seconden: number}[]>>}
 */
export async function quarters(hass, entityIds, start, end) {
  const uit = new Map();
  const wanted = [...new Set(entityIds.filter(Boolean))];
  if (!wanted.length) return uit;

  try {
    const result = await hass.callWS({
      type: "domotiapp_coach/history/quarters",
      entity_ids: wanted,
      start: start.toISOString(),
      end: end.toISOString(),
    });
    for (const [id, rows] of Object.entries(result ?? {})) {
      uit.set(
        id,
        (rows ?? []).map((row) => ({
          start: new Date(row.start * 1000),
          laagste: Number(row.laagste),
          piek: Number(row.piek),
          gemiddeld: Number(row.gemiddeld),
          seconden: Number(row.seconden),
        }))
      );
    }
  } catch (error) {
    // Een installatie die nog niet bijgewerkt is kent dit commando niet. Dan
    // blijft de piekentabel gewoon weg in plaats van dat het rapport stukloopt.
    console.warn("[DomotiApp Coach] kon de kwartieren niet ophalen", error);
  }

  return uit;
}

/**
 * Eén sensor over een hele periode samenvatten: laagste, piek en gemiddelde.
 *
 * Het gemiddelde weegt naar de tijd die elk kwartier werkelijk gedekt heeft, en
 * niet naar het aantal kwartieren. Een kwartier waarin de sensor tien minuten
 * weg was telt dus voor een derde mee, en niet voor een heel.
 *
 * @returns {{laagste: number, piek: number, gemiddeld: number, piekOp: Date}|null}
 */
export function samenvatting(rows) {
  if (!rows?.length) return null;

  let laagste = Infinity;
  let piek = -Infinity;
  let piekOp = null;
  let gewogen = 0;
  let seconden = 0;

  for (const row of rows) {
    if (!Number.isFinite(row.gemiddeld) || row.seconden <= 0) continue;
    if (row.laagste < laagste) laagste = row.laagste;
    if (row.piek > piek) {
      piek = row.piek;
      piekOp = row.start;
    }
    gewogen += row.gemiddeld * row.seconden;
    seconden += row.seconden;
  }

  if (!seconden) return null;
  return { laagste, piek, gemiddeld: gewogen / seconden, piekOp };
}
