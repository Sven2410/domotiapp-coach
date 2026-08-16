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

    /* A tile that opens something says so with an arrow rather than by moving
       under the cursor: half these tiles are read on a wall tablet, where there
       is no cursor to hover with. */
    /* The browser's own focus ring is switched off unconditionally, not just
       for :focus-visible. On iOS a tap leaves the tile focused and Safari draws
       a heavy blue rectangle around it that stays there after the sheet is
       closed again. Keyboard users are not left without: the tile marks itself
       with its own colour below. */
    :host([actionable]) {
      cursor: pointer;
      outline: none;
      -webkit-tap-highlight-color: transparent;
    }
    :host([actionable]:focus-visible) .tile {
      border-color: var(--tone);
      box-shadow: var(--dac-shadow), 0 0 0 2px color-mix(in srgb, var(--tone) 55%, transparent);
    }
    .go {
      position: absolute;
      right: 12px;
      bottom: 12px;
      color: var(--dac-ink-3);
      line-height: 0;
      opacity: 0;
      transition: opacity 200ms ease, color 200ms ease;
    }
    :host([actionable]) .go { opacity: 0.75; }
    :host([actionable]) .tile:hover .go { color: var(--tone); opacity: 1; }
    .go .icon { width: 15px; height: 15px; }

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
      /* "€ 0,264 / kWh" breaks over two lines in a phone-width tile and reads
         as a rendering fault. The number scales down instead of wrapping. */
      white-space: nowrap;
    }
    .num {
      font-size: clamp(24px, 6.5vw, 40px);
      font-weight: 400;
      line-height: 1.05;
      letter-spacing: -0.02em;
      color: var(--dac-ink);
      font-variant-numeric: tabular-nums;
    }
    .unit { font-size: 14px; font-weight: 500; color: var(--dac-ink-2); white-space: nowrap; }

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
      .tile { padding: 14px 14px 16px; gap: 10px; }
      .spark { width: 64px; height: 30px; }
      .chip { width: 34px; height: 34px; }
      .chip .icon { width: 18px; height: 18px; }
      .sub { font-size: 12px; }
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
        <span class="go" aria-hidden="true">${icons.chevronRight}</span>
      </div>
    `;
  }

  /**
   * Make the whole tile open something.
   *
   * Passing null takes it back to being a read-out -- which is what happens the
   * moment the thing behind it stops existing, such as a supplier that has not
   * published tomorrow's prices yet.
   *
   * @param {(() => void)|null} handler
   */
  set action(handler) {
    this.action_ = handler ?? null;
    this.toggleAttribute("actionable", Boolean(handler));

    if (handler) {
      // Announced and reachable as a button, without wrapping the tile in one:
      // the value inside it is the button's own name.
      this.setAttribute("role", "button");
      this.setAttribute("tabindex", "0");
    } else {
      this.removeAttribute("role");
      this.removeAttribute("tabindex");
    }

    if (this.wired_) return;
    this.wired_ = true;
    this.addEventListener("click", () => this.action_?.());
    this.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      this.action_?.();
    });
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

    // Under a handful of samples the "line" is a flat bar spanning the whole
    // box, which reads as a broken graphic rather than as a young one.
    if (series.length < 5) {
      line.setAttribute("d", "");
      area.setAttribute("d", "");
      head.setAttribute("cx", "-10");
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
