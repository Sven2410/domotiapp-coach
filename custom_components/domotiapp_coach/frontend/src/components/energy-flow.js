/**
 * Live energy flow: the house in the middle, with four arms off it -- the sun
 * above, the grid to the left, and up to two device bubbles to the right and
 * below.
 *
 * The four satellites sit on the house's own axes, at the same distance and the
 * same size, so the drawing reads as a cross rather than as nodes scattered
 * around a circle. Anything off-axis looks like a mistake at a glance, which is
 * how it was reported.
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
import { ACTIVE_WATTS, deviceLabel, deviceLabelMap, typeMeta } from "../devices.js";

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
 *
 * `width` is what the drawing needs; `height` is what it needs with the fourth
 * arm in use and `heightShort` without. The house keeps its own name inside its
 * circle -- the arm pointing down would otherwise run straight through a label
 * sitting under it.
 */
const LAYOUTS = {
  wide: {
    width: 560,
    height: 566,
    heightShort: 382,
    sun: { x: 280, y: 80, r: 42 },
    grid: { x: 80, y: 278, r: 42 },
    house: { x: 280, y: 278, r: 76 },
    dev1: { x: 480, y: 278, r: 42 },
    dev2: { x: 280, y: 476, r: 42 },
  },
  narrow: {
    width: 366,
    height: 486,
    heightShort: 336,
    sun: { x: 183, y: 80, r: 34 },
    grid: { x: 53, y: 244, r: 34 },
    house: { x: 183, y: 244, r: 62 },
    dev1: { x: 313, y: 244, r: 34 },
    dev2: { x: 183, y: 408, r: 34 },
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

    /* Which way the energy goes is information, not decoration, so it is drawn
       as well as animated. Without this the diagram is unreadable for anyone
       with animations turned off -- which on Windows is a single accessibility
       setting away, and is how it reached us. */
    .arrow { stroke: none; transition: fill 400ms ease, opacity 300ms ease; }
    .arrow.idle { opacity: 0; }

    @media (prefers-reduced-motion: reduce) {
      /* The blanket rule in base.css freezes every animation on the page. Here
         that would stop the only moving thing that carries meaning, so the flow
         keeps going -- just calmly. */
      .flow {
        animation-duration: var(--speed-calm, 6s) !important;
        animation-iteration-count: infinite !important;
      }
    }

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
          <span id="detail-title">Ook aan</span>
          <button type="button" id="detail-close" aria-label="Sluiten">${icons.close}</button>
        </div>
        <ul id="detail-list"></ul>
      </div>
    `;
  }

  afterRender() {
    this.build_();

    this.$("#detail-close").addEventListener("click", () => {
      this.$("#detail").hidden = true;
    });
  }

  onConnect() {
    // The two layouts are different drawings, not one drawing scaled: at phone
    // width the wide one puts 11px labels under 20px circles.
    this.observer_ ??= new ResizeObserver(([entry]) => {
      const next = entry.contentRect.width < NARROW_AT ? "narrow" : "wide";
      if (next === this.mode_) return;
      this.mode_ = next;
      this.build_();
      if (this.reading_) this.update(this.reading_);
    });
    this.observer_.observe(this);
  }

  onDisconnect() {
    this.observer_?.disconnect();
  }

  /** Draw the SVG for the current layout. */
  build_() {
    const L = LAYOUTS[this.mode_];

    // The sun sits directly above the house, so its name goes above it: below,
    // it would land on the very line it is describing. The house names itself
    // inside its circle for the same reason, one arm further round.
    const node = (
      id,
      pos,
      tone,
      iconKey,
      { big = false, labelAbove = false, labelInside = false } = {}
    ) => `
      <g class="node" id="node-${id}" style="--tone: ${tone}">
        <circle class="halo" cx="${pos.x}" cy="${pos.y}" r="${pos.r + 15}"/>
        <circle class="disc" cx="${pos.x}" cy="${pos.y}" r="${pos.r}"/>
        <foreignObject x="${pos.x - 14}" y="${pos.y - pos.r + 12}" width="28" height="28">
          <div xmlns="http://www.w3.org/1999/xhtml" class="icon-wrap" data-icon>${icons[iconKey]}</div>
        </foreignObject>
        <text class="${big ? "h-value" : "n-value"}" x="${pos.x}" y="${pos.y + (big ? 14 : 11)}" text-anchor="middle">—</text>
        <text class="${big ? "h-unit" : "n-unit"}" x="${pos.x}" y="${pos.y + (big ? 33 : 26)}" text-anchor="middle"></text>
        <text class="n-name" x="${pos.x}"
              y="${
                labelInside
                  ? pos.y + 50
                  : labelAbove
                    ? pos.y - pos.r - 16
                    : pos.y + pos.r + 24
              }" text-anchor="middle"></text>
      </g>
    `;

    const link = (id, from, to, tone) => {
      const s = segment(from, to);
      return `
        <path class="track" d="${d(s)}"/>
        <path class="flow" id="flow-${id}" d="${d(s)}" stroke="${tone}"/>
        <path class="arrow" id="arrow-${id}" d="M-5.5 -5 L5.5 0 L-5.5 5 Z" fill="${tone}"/>
      `;
    };

    this.$("#stage").innerHTML = `
      <svg viewBox="0 0 ${L.width} ${L.height}" role="img"
           aria-label="Live energiestroom tussen zon, net, woning en apparaten">
        <g id="links">
          ${link("solar", L.sun, L.house, "var(--dac-solar)")}
          ${link("grid", L.grid, L.house, "var(--dac-grid-in)")}
          ${link("dev1", L.house, L.dev1, "var(--dac-device-1)")}
          ${link("dev2", L.house, L.dev2, "var(--dac-device-2)")}
        </g>
        ${node("solar", L.sun, "var(--dac-solar)", "sun", { labelAbove: true })}
        ${node("grid", L.grid, "var(--dac-grid-in)", "grid")}
        ${node("house", L.house, "var(--dac-house)", "house", { big: true, labelInside: true })}
        ${node("dev1", L.dev1, "var(--dac-device-1)", "overig")}
        ${node("dev2", L.dev2, "var(--dac-device-2)", "overig")}
      </svg>
    `;
    this.svg_ = this.$("svg");

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
    this.arrows_ = {
      solar: this.$("#arrow-solar"),
      grid: this.$("#arrow-grid"),
      dev1: this.$("#arrow-dev1"),
      dev2: this.$("#arrow-dev2"),
    };
    // Kept so the arrowheads can be placed and rotated along each link.
    this.segments_ = {
      solar: segment(L.sun, L.house),
      grid: segment(L.grid, L.house),
      dev1: segment(L.house, L.dev1),
      dev2: segment(L.house, L.dev2),
    };
    this.links_ = {
      dev1: this.flows_.dev1.previousElementSibling,
      dev2: this.flows_.dev2.previousElementSibling,
    };
    this.height_ = L.height;

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

    this.setFlow_("solar", reading.solar, false);
    this.setFlow_("grid", gridPower, exporting, gridTone);

    this.updateDevices_(reading.devices);
  }

  /** This device's name, with two of a kind told apart. */
  labelFor_(device) {
    return this.labels_?.get(device.id) ?? deviceLabel(device);
  }

  /** Fill the two device slots and hide whatever is left over. */
  updateDevices_(devices) {
    // Numbered over the whole list before anything is filtered or summed, so a
    // bubble carries the same name as the card it opens.
    this.labels_ = deviceLabelMap(devices);
    const { slots } = chooseBubbles(devices);
    this.slots_ = slots;

    for (const [index, slot] of ["dev1", "dev2"].entries()) {
      const device = slots[index];
      const node = this.nodes_[slot];
      const shown = Boolean(device);

      node.classList.toggle("hidden", !shown);
      this.flows_[slot].classList.toggle("idle", !shown);
      this.arrows_[slot].classList.toggle("idle", !shown);
      this.links_[slot].style.display = shown ? "" : "none";

      if (!shown) {
        if (this.openSlot_ === slot) this.$("#detail").hidden = true;
        continue;
      }

      const rolled = device.rolled?.length ?? 0;
      const label = rolled ? `+ ${rolled} andere` : this.labelFor_(device);
      const iconKey = rolled ? "overig" : typeMeta(device.type).icon;

      node.querySelector("[data-icon]").innerHTML = icons[iconKey];
      // Openable when there is more to say: what got folded into a summed
      // bubble, or the extra readings a brand offers.
      node.classList.toggle("clickable", rolled > 0 || (device.details?.length ?? 0) > 0);
      this.setNode_(slot, device.watts, label);
      this.setFlow_(slot, device.watts, false);
    }

    this.fitHeight_(Boolean(slots[1]));

    // Keep an open roll-up in step with the numbers behind it.
    if (this.openSlot_ && !this.$("#detail").hidden) this.openDetail_(this.openSlot_, true);
  }

  /**
   * Trim the drawing to the arms that are in use.
   *
   * The arm pointing down only fills when a second appliance is running, which
   * for most houses is most of the time it is not. Leaving its space reserved
   * would put a permanent hole under the house. The width is untouched, so the
   * drawing never changes size -- only the empty space below it goes.
   */
  fitHeight_(hasDown) {
    const L = LAYOUTS[this.mode_];
    const height = hasDown ? L.height : L.heightShort;
    if (this.height_ === height) return;

    this.height_ = height;
    this.svg_.setAttribute("viewBox", `0 0 ${L.width} ${height}`);
  }

  /**
   * What the device bubbles are showing right now, in slot order.
   *
   * The key printed under the diagram has to describe the diagram, so it asks
   * rather than deciding for a second time which appliances made it in.
   *
   * @returns {Array<{tone: string, label: string}>} empty when nothing is running
   */
  get bubbles() {
    return (this.slots_ ?? []).map((device, index) => ({
      tone: index === 0 ? "var(--dac-device-1)" : "var(--dac-device-2)",
      label: device.rolled?.length ? `+ ${device.rolled.length} andere` : this.labelFor_(device),
    }));
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

  /**
   * @param {string} id which link
   * @param {number|null} watts
   * @param {boolean} reverse true when the energy runs against the drawn path
   * @param {string} [tone] stroke colour, when the link changes colour
   */
  setFlow_(id, watts, reverse, tone) {
    const path = this.flows_[id];
    const arrow = this.arrows_[id];
    // The same threshold that decides a bubble exists at all. They used to
    // differ -- a bubble from 20 W, a flow from 50 -- which drew an appliance
    // hanging off the house with nothing running to it, and that reads as a
    // fault rather than as a small load.
    const idle = !Number.isFinite(watts) || Math.abs(watts) < ACTIVE_WATTS;

    path.classList.toggle("idle", idle);
    path.classList.toggle("reverse", !!reverse);
    arrow.classList.toggle("idle", idle);
    if (tone) {
      path.setAttribute("stroke", tone);
      arrow.setAttribute("fill", tone);
    }
    if (idle) return;

    // 200 W crawls at ~3.1s per dash cycle, 7 kW races at ~0.45s.
    const speed = Math.max(0.45, 3.2 - Math.min(Math.abs(watts), 7000) * 0.0004);

    // Rewriting animation-duration restarts the animation in Chrome. The power
    // wobbles a little on every meter reading, so writing this on every tick
    // meant the dashes reset before they had moved -- the animation reported
    // itself as running with its currentTime pinned at zero, and the flow sat
    // still. Quantised, and only written when the bucket actually changes.
    const bucket = (Math.round(speed * 4) / 4).toFixed(2);
    if (path.dataset.speed !== bucket) {
      path.dataset.speed = bucket;
      path.style.setProperty("--speed", `${bucket}s`);
      // With animations turned down the same movement is kept, slowed to
      // something that reads as a drift rather than a stream.
      path.style.setProperty("--speed-calm", `${Math.max(2.5, Number(bucket) * 2.6).toFixed(2)}s`);
    }

    this.placeArrow_(id, reverse);
  }

  /** Put the arrowhead along the link, pointing the way the energy goes. */
  placeArrow_(id, reverse) {
    const s = this.segments_[id];
    const arrow = this.arrows_[id];
    // Just past the middle, so it does not collide with either node's label.
    const t = 0.56;
    const x = s.x1 + (s.x2 - s.x1) * t;
    const y = s.y1 + (s.y2 - s.y1) * t;
    let angle = (Math.atan2(s.y2 - s.y1, s.x2 - s.x1) * 180) / Math.PI;
    if (reverse) angle += 180;
    arrow.setAttribute("transform", `translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${angle.toFixed(1)})`);
  }

  /**
   * Open a bubble.
   *
   * Two different things live behind one tap. A summed bubble says what got
   * folded into it. A real device shows what it is doing beyond the watts --
   * for a charger that is its status, its limit and what it has delivered,
   * which is the part a customer actually wants to see while the car is on it.
   */
  openDetail_(slot, keepOpen = false) {
    const index = slot === "dev1" ? 0 : 1;
    const device = this.slots_?.[index];
    if (!device) return;

    const rolled = device.rolled ?? [];
    const rows = rolled.length
      ? rolled.map((dev) => ({ k: this.labelFor_(dev), v: powerText(dev.watts) }))
      : [
          { k: "Vermogen", v: powerText(device.watts) },
          ...(device.details ?? []).map((row) => ({ k: row.label, v: row.text })),
        ];

    // One row would just be the number already printed inside the bubble.
    if (rows.length < 2) return;

    const detail = this.$("#detail");
    this.openSlot_ = slot;
    this.$("#detail-title").textContent = rolled.length ? "Ook aan" : this.labelFor_(device);

    // Values come from the customer's own sensors, so they go in as text.
    this.$("#detail-list").replaceChildren(
      ...rows.map((row) => {
        const item = document.createElement("li");
        const key = document.createElement("span");
        key.className = "k";
        key.textContent = row.k;
        const value = document.createElement("span");
        value.className = "v";
        value.textContent = row.v;
        item.append(key, value);
        return item;
      })
    );
    if (!keepOpen) detail.hidden = false;
  }
}

define("dac-energy-flow", DacEnergyFlow);
