/**
 * Live energy flow: the house in the middle, the sun above it, the grid to its
 * left, and up to two device bubbles on the far side.
 *
 * Every connection is a straight line. A curve implies a route the electricity
 * does not take, and at a glance it also makes the two halves of the grid link
 * look like different paths -- they are the same wire.
 *
 * The grid is one reversible link rather than two arrows: import and export are
 * the same connection measured in opposite directions, and one of the two meter
 * sensors is always zero. It turns cyan flowing in and purple flowing out.
 *
 * Flow speed tracks power, so the animation already says "a lot" or "barely
 * anything" before any number is read.
 *
 * Two device bubbles, never more. With three or more appliances running, the
 * heaviest keeps its own bubble and the rest are summed into the second one --
 * a diagram that grows a node per appliance stops being readable exactly when
 * the house gets interesting. The summed bubble opens on click to say what is
 * inside it.
 */

import { DacElement, define } from "../base.js";
import { icons } from "../icons.js";
import { power, powerText } from "../format.js";
import { ACTIVE_WATTS, deviceLabel, typeMeta } from "../devices.js";

/** Below this width the wide layout stops being legible and it goes portrait. */
const NARROW_AT = 470;

/**
 * Geometry for both layouts, in each layout's own viewBox units.
 *
 * Spacing is set by the labels, not the circles: every node carries its name
 * below it at `cy + r + 24`, and the halo around the next node starts at
 * `cy - r - 15`. Put two nodes a comfortable-looking distance apart and the
 * label of one lands inside the halo of the other, which is what makes the link
 * between them disappear.
 */
const LAYOUTS = {
  wide: {
    viewBox: "0 0 640 470",
    sun: { x: 320, y: 74, r: 44 },
    grid: { x: 78, y: 254, r: 44 },
    house: { x: 320, y: 254, r: 78 },
    dev1: { x: 562, y: 132, r: 40 },
    dev2: { x: 562, y: 366, r: 40 },
  },
  narrow: {
    viewBox: "0 0 360 590",
    sun: { x: 190, y: 68, r: 38 },
    grid: { x: 56, y: 240, r: 38 },
    house: { x: 190, y: 240, r: 66 },
    // Wide apart on purpose: the two links leave the house downwards, and any
    // closer together they run straight through the "Woning" label.
    dev1: { x: 86, y: 470, r: 36 },
    dev2: { x: 294, y: 470, r: 36 },
  },
};

/** Straight segment between the edges of two circles. */
function segment(a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  return {
    x1: a.x + ux * a.r,
    y1: a.y + uy * a.r,
    x2: b.x - ux * b.r,
    y2: b.y - uy * b.r,
  };
}

const d = (s) => `M${s.x1.toFixed(1)} ${s.y1.toFixed(1)} L${s.x2.toFixed(1)} ${s.y2.toFixed(1)}`;

/**
 * Choose which two bubbles to show.
 *
 * @param {Array<{watts:number|null}>} devices
 * @returns {{slots: Array, rolled: Array}} up to two bubbles, plus whatever got
 *   folded into the second one.
 */
export function chooseBubbles(devices) {
  const active = (devices ?? [])
    .filter((dev) => Number.isFinite(dev.watts) && dev.watts >= ACTIVE_WATTS)
    .sort((a, b) => b.watts - a.watts);

  if (active.length <= 2) return { slots: active, rolled: [] };

  const [heaviest, ...rest] = active;
  const total = rest.reduce((sum, dev) => sum + dev.watts, 0);
  return {
    slots: [heaviest, { id: "__rest__", type: "overig", name: "Overig", watts: total, rolled: rest }],
    rolled: rest,
  };
}

class DacEnergyFlow extends DacElement {
  static css = /* css */ `
    :host { display: block; position: relative; }

    svg { width: 100%; height: auto; display: block; overflow: visible; }

    .track { fill: none; stroke: var(--dac-border); stroke-width: 2; }

    .flow {
      fill: none;
      stroke-width: 3;
      stroke-linecap: round;
      stroke-dasharray: 1 15;
      animation: dash var(--speed, 2s) linear infinite;
      transition: stroke 400ms ease, opacity 400ms ease;
    }
    .flow.idle { opacity: 0; }
    .flow.reverse { animation-direction: reverse; }
    @keyframes dash { to { stroke-dashoffset: -16; } }

    .node .halo { fill: var(--tone); opacity: 0.10; transition: opacity 500ms ease; }
    .node .disc {
      fill: rgba(18, 18, 15, 0.94);
      stroke: color-mix(in srgb, var(--tone) 48%, transparent);
      stroke-width: 1.5;
      transition: stroke 400ms ease;
    }
    .node .icon-wrap { color: var(--tone); display: grid; place-items: center; }
    .node.hidden { display: none; }
    .node.clickable { cursor: pointer; }
    .node.clickable .disc { stroke-dasharray: 4 3; }

    text { font-family: var(--dac-font); }
    .n-value { font-size: 20px; font-weight: 500; fill: var(--dac-ink); font-variant-numeric: tabular-nums; }
    .n-unit  { font-size: 11px; font-weight: 600; fill: var(--dac-ink-3); }
    .n-name  {
      font-size: 11.5px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      fill: var(--dac-ink-3);
    }
    .h-value { font-size: 32px; font-weight: 400; fill: var(--dac-ink); font-variant-numeric: tabular-nums; }
    .h-unit  { font-size: 13px; font-weight: 600; fill: var(--dac-ink-3); }

    .icon { width: 22px; height: 22px; }

    /* ---- roll-up detail ---- */
    .detail {
      position: absolute;
      inset: auto 0 0 0;
      margin: 0 auto;
      max-width: 320px;
      padding: 14px 16px;
      border-radius: var(--dac-radius-sm);
      background: rgba(18, 18, 15, 0.97);
      border: 1px solid var(--dac-border-hi);
      box-shadow: 0 20px 44px -20px rgba(0,0,0,0.95);
      font-size: 13px;
    }
    .detail[hidden] { display: none; }
    .detail-head {
      display: flex; align-items: center; gap: 8px;
      margin-bottom: 10px;
      font-size: 11px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
      color: var(--dac-ink-3);
    }
    .detail-head button {
      margin-left: auto; padding: 2px; border: 0; background: transparent;
      color: var(--dac-ink-3); cursor: pointer; line-height: 0;
    }
    .detail-head .icon { width: 15px; height: 15px; }
    .detail ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 7px; }
    .detail li { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .detail .k { color: var(--dac-ink-2); }
    .detail .v { color: var(--dac-ink); font-weight: 500; font-variant-numeric: tabular-nums; }
  `;

  constructor() {
    super();
    this.mode_ = "wide";
    this.reading_ = null;
  }

  render() {
    return `
      <div id="stage"></div>
      <div class="detail" id="detail" hidden>
        <div class="detail-head">
          <span>Ook aan</span>
          <button type="button" id="detail-close" aria-label="Sluiten">${icons.close}</button>
        </div>
        <ul id="detail-list"></ul>
      </div>
    `;
  }

  afterRender() {
    this.build_();

    // The two layouts are different drawings, not one drawing scaled: at phone
    // width the wide one puts 11px labels under 20px circles.
    this.observer_ = new ResizeObserver(([entry]) => {
      const next = entry.contentRect.width < NARROW_AT ? "narrow" : "wide";
      if (next === this.mode_) return;
      this.mode_ = next;
      this.build_();
      if (this.reading_) this.update(this.reading_);
    });
    this.observer_.observe(this);

    this.$("#detail-close").addEventListener("click", () => {
      this.$("#detail").hidden = true;
    });
  }

  disconnectedCallback() {
    this.observer_?.disconnect();
  }

  /** Draw the SVG for the current layout. */
  build_() {
    const L = LAYOUTS[this.mode_];

    // The sun sits directly above the house, so its name goes above it: below,
    // it would land on the very line it is describing.
    const node = (id, pos, tone, iconKey, { big = false, labelAbove = false } = {}) => `
      <g class="node" id="node-${id}" style="--tone: ${tone}">
        <circle class="halo" cx="${pos.x}" cy="${pos.y}" r="${pos.r + 15}"/>
        <circle class="disc" cx="${pos.x}" cy="${pos.y}" r="${pos.r}"/>
        <foreignObject x="${pos.x - 14}" y="${pos.y - pos.r + 12}" width="28" height="28">
          <div xmlns="http://www.w3.org/1999/xhtml" class="icon-wrap" data-icon>${icons[iconKey]}</div>
        </foreignObject>
        <text class="${big ? "h-value" : "n-value"}" x="${pos.x}" y="${pos.y + (big ? 14 : 11)}" text-anchor="middle">—</text>
        <text class="${big ? "h-unit" : "n-unit"}" x="${pos.x}" y="${pos.y + (big ? 33 : 26)}" text-anchor="middle"></text>
        <text class="n-name" x="${pos.x}"
              y="${labelAbove ? pos.y - pos.r - 16 : pos.y + pos.r + 24}" text-anchor="middle"></text>
      </g>
    `;

    const link = (id, from, to, tone) => {
      const s = segment(from, to);
      return `
        <path class="track" d="${d(s)}"/>
        <path class="flow" id="flow-${id}" d="${d(s)}" stroke="${tone}"/>
      `;
    };

    this.$("#stage").innerHTML = `
      <svg viewBox="${L.viewBox}" role="img"
           aria-label="Live energiestroom tussen zon, net, woning en apparaten">
        <g id="links">
          ${link("solar", L.sun, L.house, "var(--dac-solar)")}
          ${link("grid", L.grid, L.house, "var(--dac-grid-in)")}
          ${link("dev1", L.house, L.dev1, "var(--dac-device-1)")}
          ${link("dev2", L.house, L.dev2, "var(--dac-device-2)")}
        </g>
        ${node("solar", L.sun, "var(--dac-solar)", "sun", { labelAbove: true })}
        ${node("grid", L.grid, "var(--dac-grid-in)", "grid")}
        ${node("house", L.house, "var(--dac-house)", "house", { big: true })}
        ${node("dev1", L.dev1, "var(--dac-device-1)", "overig")}
        ${node("dev2", L.dev2, "var(--dac-device-2)", "overig")}
      </svg>
    `;

    this.nodes_ = {
      solar: this.$("#node-solar"),
      grid: this.$("#node-grid"),
      house: this.$("#node-house"),
      dev1: this.$("#node-dev1"),
      dev2: this.$("#node-dev2"),
    };
    this.flows_ = {
      solar: this.$("#flow-solar"),
      grid: this.$("#flow-grid"),
      dev1: this.$("#flow-dev1"),
      dev2: this.$("#flow-dev2"),
    };
    this.links_ = {
      dev1: this.flows_.dev1.previousElementSibling,
      dev2: this.flows_.dev2.previousElementSibling,
    };

    for (const slot of ["dev1", "dev2"]) {
      this.nodes_[slot].addEventListener("click", () => this.openDetail_(slot));
    }
  }

  /** @param {object} reading from LiveSource or DemoSource */
  update(reading) {
    if (!this.rendered_) this.connectedCallback();
    this.reading_ = reading;

    const exporting = (reading.grid ?? 0) < 0;
    const gridPower = reading.grid === null ? null : Math.abs(reading.grid);
    const gridTone = exporting ? "var(--dac-grid-out)" : "var(--dac-grid-in)";

    this.setNode_("solar", reading.solar, "Opwek");
    this.setNode_("house", reading.house, "Woning");
    this.setNode_(
      "grid",
      gridPower,
      exporting ? "Naar het net" : "Van het net",
      gridTone,
      exporting ? "grid" : "grid"
    );

    this.setFlow_(this.flows_.solar, reading.solar, false);
    this.setFlow_(this.flows_.grid, gridPower, exporting);
    this.flows_.grid.setAttribute("stroke", gridTone);

    this.updateDevices_(reading.devices);
  }

  /** Fill the two device slots and hide whatever is left over. */
  updateDevices_(devices) {
    const { slots } = chooseBubbles(devices);
    this.slots_ = slots;

    for (const [index, slot] of ["dev1", "dev2"].entries()) {
      const device = slots[index];
      const node = this.nodes_[slot];
      const shown = Boolean(device);

      node.classList.toggle("hidden", !shown);
      this.flows_[slot].classList.toggle("idle", !shown);
      this.links_[slot].style.display = shown ? "" : "none";

      if (!shown) {
        if (this.openSlot_ === slot) this.$("#detail").hidden = true;
        continue;
      }

      const rolled = device.rolled?.length ?? 0;
      const label = rolled ? `+ ${rolled} andere` : deviceLabel(device);
      const iconKey = rolled ? "overig" : typeMeta(device.type).icon;

      node.querySelector("[data-icon]").innerHTML = icons[iconKey];
      node.classList.toggle("clickable", rolled > 0);
      this.setNode_(slot, device.watts, label);
      this.setFlow_(this.flows_[slot], device.watts, false);
    }

    // Keep an open roll-up in step with the numbers behind it.
    if (this.openSlot_ && !this.$("#detail").hidden) this.openDetail_(this.openSlot_, true);
  }

  setNode_(id, value, name, tone) {
    const node = this.nodes_[id];
    if (tone) node.style.setProperty("--tone", tone);

    const { value: text, unit } = power(value);
    node.querySelector("text.n-value, text.h-value").textContent = text;
    node.querySelector("text.n-unit, text.h-unit").textContent = unit;
    node.querySelector("text.n-name").textContent = name;

    // The halo brightens with activity, so an idle node visibly goes quiet.
    const level = Number.isFinite(value) ? Math.min(Math.abs(value) / 7000, 1) : 0;
    node.querySelector(".halo").style.opacity = (0.05 + level * 0.16).toFixed(3);
  }

  setFlow_(path, watts, reverse) {
    const idle = !Number.isFinite(watts) || Math.abs(watts) < 50;
    path.classList.toggle("idle", idle);
    path.classList.toggle("reverse", !!reverse);
    if (idle) return;
    // 200 W crawls at ~3.1s per dash cycle, 7 kW races at ~0.45s.
    const speed = Math.max(0.45, 3.2 - Math.min(Math.abs(watts), 7000) * 0.0004);
    path.style.setProperty("--speed", `${speed.toFixed(2)}s`);
  }

  /** Show what got folded into a summed bubble. */
  openDetail_(slot, keepOpen = false) {
    const index = slot === "dev1" ? 0 : 1;
    const device = this.slots_?.[index];
    const rolled = device?.rolled;
    if (!rolled?.length) return;

    const detail = this.$("#detail");
    this.openSlot_ = slot;
    this.$("#detail-list").innerHTML = rolled
      .map(
        (dev) =>
          `<li><span class="k">${deviceLabel(dev)}</span><span class="v">${powerText(dev.watts)}</span></li>`
      )
      .join("");
    if (!keepOpen) detail.hidden = false;
  }
}

define("dac-energy-flow", DacEnergyFlow);
