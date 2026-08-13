/**
 * Simulated house data for phase 1.
 *
 * Nothing here talks to Home Assistant yet -- the point is to review the design
 * with numbers that move and stay physically consistent (grid = house - solar,
 * surplus = whatever solar the house does not use). Phase 1 of the project is
 * "read only": once the real sensors are mapped, this module gets replaced by a
 * live data source behind the same shape, and every view keeps working.
 */

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** Smooth random walk that stays inside [lo, hi]. */
class Drift {
  constructor(value, step, lo, hi) {
    this.value = value;
    this.step = step;
    this.lo = lo;
    this.hi = hi;
  }

  next() {
    this.value = clamp(
      this.value + (Math.random() - 0.5) * this.step * 2,
      this.lo,
      this.hi
    );
    return this.value;
  }
}

/** Bell-shaped solar yield over the day, peaking around 13:30. */
function solarPotential(hours) {
  const spread = 3.1;
  const peak = 13.5;
  const value = Math.exp(-((hours - peak) ** 2) / (2 * spread ** 2));
  return value < 0.02 ? 0 : value;
}

/** Rough day-ahead price shape: cheap at night and midday, expensive at 18:00. */
function priceShape(hours) {
  const evening = Math.exp(-((hours - 18.5) ** 2) / 5.5);
  const morning = Math.exp(-((hours - 8) ** 2) / 6.0);
  const midday = Math.exp(-((hours - 13.5) ** 2) / 7.0);
  return 0.11 + evening * 0.26 + morning * 0.1 - midday * 0.07;
}

export class DemoSource {
  /**
   * @param {object} [options]
   * @param {number} [options.peakPower] installed peak power in kW
   * @param {boolean} [options.fastClock] run an accelerated day instead of
   *   following the wall clock. Without it a demo opened at night would show
   *   nothing but zeroes; with it the whole solar curve plays out in minutes.
   * @param {number} [options.startHour] where the accelerated day starts
   * @param {number} [options.hoursPerTick] how far the clock jumps per sample
   */
  constructor({
    peakPower = 6.4,
    fastClock = true,
    startHour = 10.5,
    hoursPerTick = 0.08,
  } = {}) {
    this.peakPower = peakPower;
    this.fastClock = fastClock;
    this.hoursPerTick = hoursPerTick;
    this.virtualHours = startHour;
    this.clouds = new Drift(0.85, 0.09, 0.15, 1);
    this.base = new Drift(0.42, 0.05, 0.24, 0.75);
    this.appliance = 0;
    this.applianceLeft = 0;
    this.history = [];
    this.previousHours = startHour;
    this.totals = this.emptyTotals_();
  }

  emptyTotals_() {
    return { solarKwh: 0, importKwh: 0, exportKwh: 0, usedOwnKwh: 0, cost: 0, priceSum: 0, samples: 0 };
  }

  /** Running day totals, reset when the simulated clock passes midnight. */
  day() {
    const t = this.totals;
    const selfUse = t.solarKwh > 0.01 ? t.usedOwnKwh / t.solarKwh : 0;
    return {
      solarKwh: t.solarKwh,
      importKwh: t.importKwh,
      exportKwh: t.exportKwh,
      cost: t.cost,
      selfUse,
      averagePrice: t.samples ? t.priceSum / t.samples : 0,
    };
  }

  /** Hour of day the simulation is currently at, 0-24. */
  clock() {
    if (!this.fastClock) {
      const now = new Date();
      return now.getHours() + now.getMinutes() / 60;
    }
    this.virtualHours = (this.virtualHours + this.hoursPerTick) % 24;
    return this.virtualHours;
  }

  /** @returns {{solar:number, house:number, grid:number, surplus:number, price:number, at:Date, hours:number}} */
  sample() {
    const now = new Date();
    const hours = this.clock();

    const solar = +(solarPotential(hours) * this.peakPower * this.clouds.next()).toFixed(2);

    // Occasionally switch on something big (kettle, oven, EV charger).
    if (this.applianceLeft > 0) {
      this.applianceLeft -= 1;
    } else if (Math.random() < 0.08) {
      this.appliance = [1.1, 2.2, 3.6][Math.floor(Math.random() * 3)];
      this.applianceLeft = 4 + Math.floor(Math.random() * 10);
    } else {
      this.appliance = 0;
    }

    const house = +(this.base.next() + this.appliance).toFixed(2);
    const grid = +(house - solar).toFixed(2); // > 0 import, < 0 export
    const surplus = +Math.max(0, solar - house).toFixed(2);
    const price = +clamp(priceShape(hours) + (Math.random() - 0.5) * 0.012, 0.04, 0.55).toFixed(3);

    // Day totals. One sample stands for `dt` hours, so kW becomes kWh.
    if (hours < this.previousHours) this.totals = this.emptyTotals_();
    this.previousHours = hours;

    const dt = this.fastClock ? this.hoursPerTick : 2 / 3600;
    const t = this.totals;
    t.solarKwh += solar * dt;
    t.usedOwnKwh += Math.min(solar, house) * dt;
    if (grid > 0) {
      t.importKwh += grid * dt;
      t.cost += grid * dt * price;
    } else {
      t.exportKwh += -grid * dt;
    }
    t.priceSum += price;
    t.samples += 1;

    const reading = { solar, house, grid, surplus, price, at: now, hours };

    this.history.push(reading);
    if (this.history.length > 90) this.history.shift();

    return reading;
  }

  /** Recent values for one key, for the sparklines. */
  series(key, length = 40) {
    return this.history.slice(-length).map((r) => Math.abs(r[key]));
  }
}
