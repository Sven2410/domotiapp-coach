/**
 * A single live value: icon chip, label, hero number, supporting line and a
 * sparkline of the recent history.
 *
 * The number itself always wears the neutral ink colour -- identity is carried
 * by the icon chip and the sparkline, never by the digits. That keeps the row
 * readable for colour-blind users and stops the tiles turning into a rainbow.
 */

import { DacElement, define } from "../base.js";
import { icons } from "../icons.js";

class DacStatTile extends DacElement {
  static css = /* css */ `
    :host { display: block; }

    .tile {
      position: relative;
      height: 100%;
      padding: 18px 20px 20px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      background: var(--dac-surface);
      border: 1px solid var(--dac-border);
      border-radius: var(--dac-radius);
      box-shadow: var(--dac-shadow);
      overflow: hidden;
      transition: border-color 260ms ease, transform 260ms ease;
    }
    .tile:hover { border-color: var(--dac-border-hi); transform: translateY(-2px); }

    /* Faint wash of the stream colour, top-right. */
    .tile::before {
      content: "";
      position: absolute;
      top: -60px;
      right: -50px;
      width: 180px;
      height: 180px;
      border-radius: 50%;
      background: radial-gradient(circle, var(--tone) 0%, transparent 70%);
      opacity: 0.13;
      pointer-events: none;
    }

    .top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }

    .chip {
      width: 38px;
      height: 38px;
      flex: 0 0 auto;
      display: grid;
      place-items: center;
      border-radius: 12px;
      color: var(--tone);
      background: color-mix(in srgb, var(--tone) 14%, transparent);
      border: 1px solid color-mix(in srgb, var(--tone) 32%, transparent);
    }
    .chip .icon { width: 20px; height: 20px; }

    .spark { width: 100px; height: 36px; flex: 0 0 auto; overflow: visible; }
    .spark path.line { fill: none; stroke: var(--tone); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    .spark path.area { stroke: none; fill: url(#spark-fade); }
    .spark circle.head { fill: var(--tone); r: 2.6; }
    .spark stop.top { stop-color: var(--tone); stop-opacity: 0.28; }
    .spark stop.bottom { stop-color: var(--tone); stop-opacity: 0; }

    .label {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      color: var(--dac-ink-3);
    }

    .value {
      display: flex;
      align-items: baseline;
      gap: 7px;
      margin-top: 6px;
    }
    .num {
      font-size: 40px;
      font-weight: 300;
      line-height: 1;
      letter-spacing: -0.02em;
      color: var(--dac-ink);
      font-variant-numeric: tabular-nums;
    }
    .unit { font-size: 14px; font-weight: 500; color: var(--dac-ink-2); }

    .sub {
      margin-top: 10px;
      font-size: 12.5px;
      line-height: 1.45;
      color: var(--dac-ink-2);
      display: flex;
      align-items: center;
      gap: 7px;
      min-height: 18px;
    }
    .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--tone); flex: 0 0 auto; }

    .body { margin-top: auto; }

    @media (max-width: 520px) {
      .num { font-size: 34px; }
      .spark { width: 78px; }
    }
  `;

  render() {
    return `
      <div class="tile" part="tile">
        <div class="top">
          <div class="chip"></div>
          <svg class="spark" viewBox="0 0 100 36" aria-hidden="true">
            <defs>
              <linearGradient id="spark-fade" x1="0" y1="0" x2="0" y2="1">
                <stop class="top" offset="0"></stop>
                <stop class="bottom" offset="1"></stop>
              </linearGradient>
            </defs>
            <path class="area" d=""></path>
            <path class="line" d=""></path>
            <circle class="head" cx="0" cy="0"></circle>
          </svg>
        </div>
        <div class="body">
          <div class="label"></div>
          <div class="value">
            <span class="num tnum">--</span>
            <span class="unit"></span>
          </div>
          <div class="sub"><span class="dot"></span><span class="sub-text"></span></div>
        </div>
      </div>
    `;
  }

  /**
   * @param {{tone?:string, icon?:string, label?:string, value?:string,
   *          unit?:string, sub?:string, series?:number[]}} data
   */
  update(data) {
    if (!this.rendered_) this.connectedCallback();

    if (data.tone) this.$(".tile").style.setProperty("--tone", data.tone);
    if (data.icon) this.$(".chip").innerHTML = icons[data.icon];
    if (data.label !== undefined) this.$(".label").textContent = data.label;
    if (data.value !== undefined) this.$(".num").textContent = data.value;
    if (data.unit !== undefined) this.$(".unit").textContent = data.unit;
    if (data.sub !== undefined) this.$(".sub-text").textContent = data.sub;
    if (data.series) this.drawSpark_(data.series);
  }

  /** Draw the recent history as a 92x34 sparkline. */
  drawSpark_(series) {
    const w = 100;
    const h = 36;
    const pad = 3;
    const line = this.$(".spark path.line");
    const area = this.$(".spark path.area");
    const head = this.$(".spark circle.head");

    if (series.length < 2) {
      line.setAttribute("d", "");
      area.setAttribute("d", "");
      return;
    }

    const max = Math.max(...series, 0.001);
    const min = Math.min(...series, 0);
    const span = max - min || 1;
    const points = series.map((v, i) => [
      (i / (series.length - 1)) * w,
      h - pad - ((v - min) / span) * (h - pad * 2),
    ]);

    const d = points
      .map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`)
      .join(" ");

    line.setAttribute("d", d);
    area.setAttribute("d", `${d} L${w} ${h} L0 ${h} Z`);

    const [hx, hy] = points[points.length - 1];
    head.setAttribute("cx", hx.toFixed(1));
    head.setAttribute("cy", hy.toFixed(1));
  }
}

define("dac-stat-tile", DacStatTile);
