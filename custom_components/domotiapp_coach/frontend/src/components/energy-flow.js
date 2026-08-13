/**
 * Live energy flow between the sun, the grid and the house.
 *
 * The grid connection is drawn as one path with two states: red flowing towards
 * the house while importing, green flowing away from it while exporting. Export
 * *is* the solar surplus leaving the building, so showing them as one reversible
 * stream is both simpler and more honest than two separate arrows.
 *
 * Flow speed tracks power, so a glance at the animation already says "a lot" or
 * "barely anything" before any number is read.
 */

import { DacElement, define } from "../base.js";
import { icons } from "../icons.js";

const fmt = (v, digits = 2) =>
  v.toLocaleString("nl-NL", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

class DacEnergyFlow extends DacElement {
  static css = /* css */ `
    :host { display: block; }

    svg { width: 100%; height: auto; display: block; overflow: visible; }

    .track {
      fill: none;
      stroke: var(--dac-border);
      stroke-width: 2;
    }

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

    .halo { fill: var(--tone); opacity: 0.10; transition: opacity 500ms ease; }
    .disc {
      fill: rgba(18, 18, 16, 0.92);
      stroke: color-mix(in srgb, var(--tone) 45%, transparent);
      stroke-width: 1.5;
    }
    .node .icon-wrap { color: var(--tone); }

    text { font-family: var(--dac-font); }
    .n-value {
      font-size: 21px;
      font-weight: 400;
      fill: var(--dac-ink);
      font-variant-numeric: tabular-nums;
    }
    .n-unit { font-size: 11px; font-weight: 600; fill: var(--dac-ink-3); }
    .n-name {
      font-size: 11.5px;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      fill: var(--dac-ink-3);
    }
    .h-value { font-size: 34px; font-weight: 300; fill: var(--dac-ink); font-variant-numeric: tabular-nums; }
    .h-unit { font-size: 13px; font-weight: 600; fill: var(--dac-ink-3); }

    .icon { width: 22px; height: 22px; }
    #house .icon { width: 26px; height: 26px; }
  `;

  render() {
    const node = (id, cx, cy, r, tone, name) => `
      <g class="node" id="${id}" style="--tone: ${tone}">
        <circle class="halo" cx="${cx}" cy="${cy}" r="${r + 16}"/>
        <circle class="disc" cx="${cx}" cy="${cy}" r="${r}"/>
        <foreignObject x="${cx - 14}" y="${cy - r + 12}" width="28" height="28">
          <div xmlns="http://www.w3.org/1999/xhtml" class="icon-wrap">${icons[id === "house" ? "house" : id === "solar" ? "sun" : "grid"]}</div>
        </foreignObject>
        <text class="${id === "house" ? "h-value" : "n-value"}" x="${cx}" y="${cy + (id === "house" ? 16 : 12)}" text-anchor="middle">0,00</text>
        <text class="${id === "house" ? "h-unit" : "n-unit"}" x="${cx}" y="${cy + (id === "house" ? 36 : 28)}" text-anchor="middle">kW</text>
        <text class="n-name" x="${cx}" y="${cy + r + 26}" text-anchor="middle">${name}</text>
      </g>
    `;

    return `
      <svg viewBox="0 0 640 340" role="img" aria-label="Live energiestroom tussen zon, net en woning">
        <g id="paths">
          <path class="track" d="M146 92 C 260 118, 300 140, 406 162"/>
          <path class="flow" id="flow-solar" d="M146 92 C 260 118, 300 140, 406 162" stroke="var(--dac-solar)"/>
          <path class="track" d="M146 248 C 260 224, 300 202, 406 180"/>
          <path class="flow" id="flow-grid" d="M146 248 C 260 224, 300 202, 406 180" stroke="var(--dac-grid)"/>
        </g>
        ${node("solar", 100, 92, 46, "var(--dac-solar)", "Opwek")}
        ${node("grid", 100, 248, 46, "var(--dac-grid)", "Net")}
        ${node("house", 470, 170, 74, "var(--dac-house)", "Woning")}
      </svg>
    `;
  }

  afterRender() {
    this.nodes_ = {
      solar: this.$("#solar"),
      grid: this.$("#grid"),
      house: this.$("#house"),
    };
    this.flows_ = {
      solar: this.$("#flow-solar"),
      grid: this.$("#flow-grid"),
    };
  }

  /** @param {{solar:number, house:number, grid:number, surplus:number}} reading */
  update(reading) {
    if (!this.rendered_) this.connectedCallback();

    const exporting = reading.grid < 0;
    const gridPower = Math.abs(reading.grid);

    this.setNode_("solar", reading.solar, "Opwek");
    this.setNode_("house", reading.house, "Woning");
    this.setNode_(
      "grid",
      gridPower,
      exporting ? "Naar het net" : "Van het net",
      exporting ? "var(--dac-surplus)" : "var(--dac-grid)"
    );

    this.setFlow_(this.flows_.solar, reading.solar, false);
    this.setFlow_(this.flows_.grid, gridPower, exporting);
    this.flows_.grid.setAttribute(
      "stroke",
      exporting ? "var(--dac-surplus)" : "var(--dac-grid)"
    );
  }

  setNode_(id, value, name, tone) {
    const node = this.nodes_[id];
    if (tone) node.style.setProperty("--tone", tone);
    node.querySelector("text.n-value, text.h-value").textContent = fmt(value);
    node.querySelector("text.n-name").textContent = name;
    // Halo brightens with activity, so an idle node visibly goes quiet.
    node.querySelector(".halo").style.opacity = (0.05 + Math.min(value / 7, 1) * 0.16).toFixed(3);
  }

  setFlow_(path, power, reverse) {
    const idle = power < 0.05;
    path.classList.toggle("idle", idle);
    path.classList.toggle("reverse", !!reverse);
    if (idle) return;
    // 0.2 kW crawls at ~3.2s per dash cycle, 7 kW races at ~0.45s.
    const speed = Math.max(0.45, 3.2 - Math.min(power, 7) * 0.4);
    path.style.setProperty("--speed", `${speed.toFixed(2)}s`);
  }
}

define("dac-energy-flow", DacEnergyFlow);
