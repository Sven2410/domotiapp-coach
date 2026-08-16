/**
 * What a kWh costs per interval, for as far ahead as the supplier publishes.
 *
 * Bars rather than a line: a dynamic tariff is not a continuous curve, it is a
 * price that holds for an hour and then jumps. And bars start at zero, always --
 * cutting the axis to make the difference look bigger is the one thing that
 * turns "the evening is dearer" into "the evening is impossible".
 *
 * Height carries the price. Colour repeats it against the customer's own
 * thresholds -- the same ones that colour the tile -- so the chart and the tile
 * can never disagree, and no meaning is left to colour alone.
 *
 * There is no floating tooltip. Instead one read-out above the chart always says
 * what is being pointed at, starting at the current interval. On a phone a
 * tooltip that follows a finger is under the finger, and this is a chart people
 * read while standing in the kitchen.
 */

import { DacElement, define } from "../base.js";
import { clock, price as fmtPrice, level, levelTone } from "../format.js";

/**
 * The drawing is measured in real pixels, not in an abstract grid.
 *
 * A viewBox that scales is fine for a diagram of circles and useless for a
 * chart: at phone width a 720-unit box shrinks to about a third, which takes
 * the 11px hour labels down to 3px. So the box is whatever the element is
 * actually wide, and a redraw follows a resize.
 */
const MIN_W = 240;
const TOP = 30;
/** Right-hand margin, kept clear so the threshold prices have somewhere to go. */
const GUTTER = 54;

/** Below this many pixels per bar the chart drops the part of the day already
 *  spent, which is the half nobody can act on anyway. */
const CRAMPED = 7;

/**
 * Which hours get a label under them: the finest round step whose labels still
 * fit side by side.
 */
function labelStep(maxLabels, count) {
  for (const step of [1, 2, 3, 6, 12]) {
    if (count / step <= maxLabels) return step;
  }
  return 24;
}

const sameDay = (a, b) =>
  a.getDate() === b.getDate() && a.getMonth() === b.getMonth() && a.getFullYear() === b.getFullYear();

class DacPriceChart extends DacElement {
  static css = /* css */ `
    :host { display: block; }

    .head {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }

    .read-when {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--dac-ink-3);
    }
    .read-price {
      display: flex;
      align-items: baseline;
      gap: 7px;
      margin-top: 5px;
      white-space: nowrap;
    }
    .read-num {
      font-size: 30px;
      font-weight: 400;
      line-height: 1.05;
      letter-spacing: -0.02em;
      color: var(--dac-ink);
      font-variant-numeric: tabular-nums;
    }
    .read-unit { font-size: 13px; font-weight: 500; color: var(--dac-ink-2); }

    .legend { display: flex; gap: 14px; flex-wrap: wrap; }
    .legend span { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: var(--dac-ink-2); }
    .legend i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; flex: 0 0 auto; }

    svg { width: 100%; height: auto; display: block; touch-action: pan-y; }

    .bar { transition: opacity 200ms ease; }
    /* What is already behind us cannot be planned around any more, so it steps
       back rather than competing with the part that can still be used. */
    .bar.past { opacity: 0.26; }
    .bar.picked { stroke: var(--dac-ink); stroke-width: 1.5; }

    .zero { stroke: var(--dac-border-hi); stroke-width: 1; }
    .day-split { stroke: var(--dac-border-hi); stroke-width: 1; stroke-dasharray: 3 4; }
    .rule { stroke: var(--dac-ink-3); stroke-width: 1; stroke-dasharray: 2 5; opacity: 0.7; }
    .rule-label {
      font-family: var(--dac-font);
      font-size: 10.5px;
      fill: var(--dac-ink-3);
      font-variant-numeric: tabular-nums;
    }

    .tick {
      font-family: var(--dac-font);
      font-size: 11px;
      fill: var(--dac-ink-3);
      font-variant-numeric: tabular-nums;
    }
    .day-name {
      font-family: var(--dac-font);
      font-size: 10.5px;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      fill: var(--dac-ink-3);
    }
    .flag {
      font-family: var(--dac-font);
      font-size: 10.5px;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      fill: var(--dac-ink-2);
    }
    .now-line { stroke: var(--dac-ink-2); stroke-width: 1.5; }

    .hit { fill: transparent; cursor: pointer; }

    .note {
      margin: 12px 0 0;
      font-size: 13px;
      line-height: 1.5;
      color: var(--dac-ink-2);
    }
    .note:empty { display: none; }

    .empty {
      margin: 0;
      padding: 26px 0;
      text-align: center;
      font-size: 13.5px;
      color: var(--dac-ink-2);
    }
    [hidden] { display: none !important; }

    @media (max-width: 520px) {
      .read-num { font-size: 25px; }
      .legend { gap: 10px; }
      .legend span { font-size: 11.5px; }
    }
  `;

  render() {
    return `
      <div class="head" id="head">
        <div>
          <div class="read-when" id="read-when"></div>
          <div class="read-price">
            <span class="read-num" id="read-num">—</span>
            <span class="read-unit" id="read-unit"></span>
          </div>
        </div>
        <div class="legend" id="legend"></div>
      </div>
      <div id="stage"></div>
      <p class="note" id="note"></p>
      <p class="empty" id="empty" hidden></p>
    `;
  }

  /**
   * @param {{forecast: Array<{start: Date, end: Date, price: number}>,
   *          thresholds: {low:number, high:number}}} data
   */
  update({ forecast, thresholds }) {
    if (!this.rendered_) this.connectedCallback();

    this.rows_ = forecast ?? [];
    this.bounds_ = thresholds ?? { low: 0.2, high: 0.3 };

    // Redrawn only when something in the picture actually changed. The panel
    // ticks several times a second, and rebuilding the bars under a finger
    // that is resting on one would throw the read-out away mid-read. The clock
    // is in here at five-minute resolution so the "Nu" marker still moves.
    const signature = [
      Math.floor(Date.now() / 300_000),
      // A sheet that was measured while closed had no width at all, so the
      // first draw after opening has to count as a change.
      Math.round(this.getBoundingClientRect().width),
      this.bounds_.low,
      this.bounds_.high,
      this.rows_.length,
      this.rows_[0]?.start.getTime(),
      this.rows_.map((row) => row.price).join(","),
    ].join("|");
    if (signature === this.signature_) return;
    this.signature_ = signature;

    const empty = this.$("#empty");
    const has = this.rows_.length > 1;
    this.$("#head").hidden = !has;
    this.$("#stage").hidden = !has;
    empty.hidden = has;

    if (!has) {
      empty.textContent =
        "Je leverancier publiceert (nog) geen prijslijst bij deze entiteit. Zodra dat gebeurt, staat het verloop hier.";
      this.$("#stage").innerHTML = "";
      this.$("#note").textContent = "";
      return;
    }

    this.drawLegend_();
    this.draw_();
    // Opens on the interval that is running: the price you are paying right now
    // is the one question this chart is opened with.
    this.pick_(this.shown_.findIndex((row) => this.now_ >= row.start && this.now_ < row.end));
  }

  onConnect() {
    // Redrawn on a resize because the drawing is in pixels: rotating a phone
    // or opening the sheet at another width is a different chart, not the same
    // one scaled.
    this.observer_ ??= new ResizeObserver(() => {
      const width = Math.round(this.getBoundingClientRect().width);
      if (!width || width === this.width_) return;
      this.width_ = width;
      if (!this.rows_?.length) return;
      this.draw_();
      this.pick_(this.shown_.findIndex((row) => this.now_ >= row.start && this.now_ < row.end));
    });
    this.observer_.observe(this);
  }

  onDisconnect() {
    this.observer_?.disconnect();
  }

  drawLegend_() {
    const { low, high } = this.bounds_;
    const rows = [
      { name: "good", text: `Laag (tot ${fmtPrice(low).value})` },
      { name: "warn", text: `Gemiddeld (tot ${fmtPrice(high).value})` },
      { name: "bad", text: `Hoog (boven ${fmtPrice(high).value})` },
    ];

    this.$("#legend").replaceChildren(
      ...rows.map(({ name, text }) => {
        const item = document.createElement("span");
        const swatch = document.createElement("i");
        swatch.style.background = levelTone(name);
        const label = document.createElement("span");
        label.textContent = text;
        item.append(swatch, label);
        return item;
      })
    );
  }

  draw_() {
    this.now_ = new Date();

    const W = Math.max(MIN_W, Math.round(this.getBoundingClientRect().width) || MIN_W);
    // Taller in proportion when there is less width to work with, so a phone
    // gets a chart with a shape rather than a strip.
    const H = W < 420 ? 210 : 250;
    const BOTTOM = H - 24;
    const PLOT = W - GUTTER;

    // On a narrow screen the hours already gone are dropped rather than drawn
    // at three pixels each. What is left is the part the coach plans in.
    const all = this.rows_;
    const rows =
      PLOT / all.length >= CRAMPED
        ? all
        : all.filter((row) => row.end > this.now_);
    this.shown_ = rows;

    // Bars are measured from zero. A negative price is a real thing on a
    // dynamic tariff, so the baseline sits wherever zero falls rather than at
    // the bottom of the box.
    const values = rows.map((row) => row.price);
    const top = Math.max(0, ...values) * 1.08 || 1;
    const bottom = Math.min(0, ...values) * 1.15;
    const span = top - bottom || 1;
    const y = (value) => BOTTOM - ((value - bottom) / span) * (BOTTOM - TOP);
    const zero = y(0);

    const colW = PLOT / rows.length;
    const gap = colW < 9 ? 1 : 2;
    const barW = Math.max(1.5, colW - gap);
    const radius = Math.min(4, barW / 2);

    // The cheapest interval still to come, not the cheapest of the day: a
    // bargain at eight this morning is not something anyone can act on.
    const ahead = rows
      .map((row, index) => ({ index, price: row.price, over: row.end <= this.now_ }))
      .filter((row) => !row.over);
    const cheapest = ahead.length
      ? ahead.reduce((a, b) => (b.price < a.price ? b : a)).index
      : -1;

    const step = labelStep(Math.round(PLOT / 46), rows.length);

    const bars = rows
      .map((row, index) => {
        const x = index * colW + (colW - barW) / 2;
        const value = y(row.price);
        const up = row.price >= 0;
        const height = Math.abs(value - zero);
        const past = row.end <= this.now_;
        const tone = levelTone(level(row.price, this.bounds_, true));
        return `<path class="bar${past ? " past" : ""}" data-index="${index}" fill="${tone}"
                      d="${barPath(x, barW, zero, height, up, radius)}"/>`;
      })
      .join("");

    // A dashed rule wherever the calendar day turns over, so "tomorrow" is
    // something you can see rather than something you have to work out.
    const splits = rows
      .map((row, index) =>
        index > 0 && !sameDay(row.start, rows[index - 1].start)
          ? `<line class="day-split" x1="${index * colW}" y1="${TOP - 16}" x2="${index * colW}" y2="${BOTTOM}"/>
             <text class="day-name" x="${index * colW + 6}" y="${TOP - 18}">${dayName(row.start)}</text>`
          : ""
      )
      .join("");

    const ticks = rows
      .map((row, index) =>
        row.start.getHours() % step === 0 && row.start.getMinutes() === 0
          ? `<text class="tick" x="${index * colW + colW / 2}" y="${H - 8}" text-anchor="middle">${row.start
              .getHours()
              .toString()
              .padStart(2, "0")}</text>`
          : ""
      )
      .join("");

    const nowIndex = rows.findIndex((row) => this.now_ >= row.start && this.now_ < row.end);
    const nowX = nowIndex * colW + colW / 2;
    // Anchored away from whichever edge it is near, so "Nu" is never half a
    // word -- on a phone the current hour is the very first bar.
    const nowAnchor = nowX < 18 ? "start" : nowX > PLOT - 18 ? "end" : "middle";
    const nowMark =
      nowIndex < 0
        ? ""
        : `<line class="now-line" x1="${nowX}" y1="${TOP - 14}" x2="${nowX}" y2="${BOTTOM}"/>
           <text class="flag" x="${nowX}" y="${TOP - 18}" text-anchor="${nowAnchor}">Nu</text>`;

    // The two boundaries the colours turn on, drawn where they fall. They are
    // the only scale this chart has -- and the pair of numbers somebody would
    // otherwise have to guess at from the legend.
    const rule = (value, text) =>
      value <= bottom || value >= top
        ? ""
        : `<line class="rule" x1="0" y1="${y(value)}" x2="${PLOT + 4}" y2="${y(value)}"/>
           <text class="rule-label" x="${PLOT + 10}" y="${y(value) + 3.5}">${text}</text>`;
    const rules =
      rule(this.bounds_.low, fmtPrice(this.bounds_.low).value) +
      rule(this.bounds_.high, fmtPrice(this.bounds_.high).value);

    const hits = rows
      .map(
        (row, index) =>
          `<rect class="hit" data-index="${index}" x="${index * colW}" y="${TOP - 20}"
                 width="${colW}" height="${BOTTOM - TOP + 20}"/>`
      )
      .join("");

    this.$("#stage").innerHTML = `
      <svg viewBox="0 0 ${W} ${H}" role="img"
           aria-label="Energieprijs per uur, voor vandaag en zover bekend morgen">
        ${splits}
        <line class="zero" x1="0" y1="${zero}" x2="${PLOT}" y2="${zero}"/>
        ${bars}
        <!-- Over the bars, not behind them: these are the two prices the advice
             turns on, and behind a dense afternoon they would be invisible. -->
        ${rules}
        ${nowMark}
        ${ticks}
        ${hits}
      </svg>
    `;

    // Where the coach would put a programme, in words. It was a label on the
    // bar itself first, which collides with everything: the cheapest hour is
    // often the one running, and a short bar puts its label in the middle of
    // the field.
    const best = rows[cheapest];
    this.$("#note").textContent = !best
      ? ""
      : `Goedkoopst${cheapest === nowIndex ? " is nu" : ` ${whenText(best.start, this.now_)}`}: ${
          fmtPrice(best.price).value
        } per kWh.`;

    const svg = this.$("svg");
    for (const hit of svg.querySelectorAll(".hit")) {
      const index = Number(hit.dataset.index);
      hit.addEventListener("pointerenter", () => this.pick_(index));
      hit.addEventListener("pointerdown", () => this.pick_(index));
    }

    // Only a mouse puts the read-out back on the current interval when it
    // leaves. A finger fires pointerleave the instant it lifts off, which threw
    // away the very price the customer had just tapped on -- the tap looked
    // like it did nothing at all. A tapped bar therefore stays selected until
    // another one is tapped.
    svg.addEventListener("pointerleave", (event) => {
      if (event.pointerType === "mouse") this.pick_(nowIndex);
    });

    // Slide along the chart to read it off. On a phone a bar is about ten
    // pixels wide, which is a third of what a fingertip can reliably hit, so
    // hitting one exactly must not be the only way in: put a finger down
    // anywhere and drag, and the read-out follows.
    const at = (event) => {
      const box = svg.getBoundingClientRect();
      const x = ((event.clientX - box.left) / box.width) * W;
      return Math.min(rows.length - 1, Math.max(0, Math.floor(x / colW)));
    };

    svg.addEventListener("pointerdown", (event) => {
      // Reading comes first and capturing second, inside a try: capture throws
      // for a pointer the browser no longer considers active, and doing it the
      // other way round meant one failed call swallowed the tap entirely.
      this.scrubbing_ = true;
      this.pick_(at(event));
      try {
        svg.setPointerCapture(event.pointerId);
      } catch {
        // Without capture the chart still follows a finger that stays on it.
      }
    });
    svg.addEventListener("pointermove", (event) => {
      if (this.scrubbing_) this.pick_(at(event));
    });
    for (const done of ["pointerup", "pointercancel"]) {
      svg.addEventListener(done, () => {
        this.scrubbing_ = false;
      });
    }
  }

  /** Show one interval in the read-out and outline its bar. */
  pick_(index) {
    const row = this.shown_?.[index];
    const svg = this.$("svg");
    if (!svg) return;

    for (const bar of svg.querySelectorAll(".bar")) {
      bar.classList.toggle("picked", Number(bar.dataset.index) === index);
    }

    if (!row) {
      this.$("#read-when").textContent = "Geen prijs voor dit moment";
      this.$("#read-num").textContent = "—";
      this.$("#read-unit").textContent = "";
      return;
    }

    const running = this.now_ >= row.start && this.now_ < row.end;
    const day = sameDay(row.start, this.now_) ? "" : `${dayName(row.start)} `;
    const { value, unit } = fmtPrice(row.price);

    this.$("#read-when").textContent = `${running ? "Nu · " : ""}${day}${clock(row.start)} tot ${clock(row.end)}`;
    this.$("#read-num").textContent = value;
    this.$("#read-unit").textContent = unit;
  }
}

/** A bar with its data-end rounded and its base square on the zero line. */
function barPath(x, w, base, height, up, r) {
  const h = Math.max(height, 1.5);
  const radius = Math.min(r, h);
  const end = up ? base - h : base + h;
  const sign = up ? 1 : -1;

  return [
    `M${x.toFixed(1)} ${base.toFixed(1)}`,
    `L${x.toFixed(1)} ${(end + sign * radius).toFixed(1)}`,
    `Q${x.toFixed(1)} ${end.toFixed(1)} ${(x + radius).toFixed(1)} ${end.toFixed(1)}`,
    `L${(x + w - radius).toFixed(1)} ${end.toFixed(1)}`,
    `Q${(x + w).toFixed(1)} ${end.toFixed(1)} ${(x + w).toFixed(1)} ${(end + sign * radius).toFixed(1)}`,
    `L${(x + w).toFixed(1)} ${base.toFixed(1)}`,
    "Z",
  ].join(" ");
}

/** "om 14:00" for today, "morgen om 12:00" for anything else. */
function whenText(date, now) {
  const day = sameDay(date, now) ? "" : `${dayName(date).toLowerCase()} `;
  return `${day}om ${clock(date)}`;
}

const DAYS = ["zondag", "maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag"];

/** "Morgen" when it is, the weekday when it is not. */
function dayName(date) {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  return sameDay(date, tomorrow) ? "Morgen" : DAYS[date.getDay()];
}

define("dac-price-chart", DacPriceChart);
