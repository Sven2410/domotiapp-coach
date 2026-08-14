/**
 * Placeholder for the sections that are not built yet.
 *
 * It exists so the navigation can be judged as a whole, and it doubles as the
 * roadmap: every section states which phase it belongs to -- 1 uitlezen,
 * 2 adviseren, 3 sturen.
 */

import { DacElement, define } from "../base.js";
import { icons } from "../icons.js";

export const SECTIONS = {
  strategie: {
    icon: "compass",
    title: "Strategie",
    lead: "Hier bepaal je waar de coach op stuurt.",
    body: "Kies wat voor jou telt: de laagste rekening, zoveel mogelijk eigen zon gebruiken, of je accu sparen. De coach rekent je keuzes door en legt uit waarom hij iets adviseert.",
    phase: 2,
  },
  installatie: {
    icon: "plug",
    title: "Installatie",
    lead: "Je woning, je meterkast, je opwek.",
    body: "Hier koppel je de sensoren aan de coach en leg je vast wat er in huis staat: panelen, accu, warmtepomp, laadpaal en je contract. Zonder deze gegevens kan de coach niet rekenen.",
    phase: 1,
  },
};

const PHASES = [
  { n: 1, label: "Uitlezen" },
  { n: 2, label: "Adviseren" },
  { n: 3, label: "Sturen" },
];

class DacViewPlaceholder extends DacElement {
  static css = /* css */ `
    :host { display: block; }

    .wrap {
      max-width: 760px;
      margin: 0 auto;
      padding: clamp(40px, 9vh, 96px) 22px 64px;
      text-align: center;
    }

    .mark {
      width: 62px; height: 62px; margin: 0 auto;
      display: grid; place-items: center;
      border-radius: 20px;
      color: var(--dac-accent-hi);
      background: var(--dac-accent-soft);
      border: 1px solid rgba(25,143,217,0.30);
      box-shadow: 0 18px 40px -20px var(--dac-accent-glow);
    }
    .mark .icon { width: 30px; height: 30px; }

    h1 {
      margin: 26px 0 0;
      font-weight: 600;
      font-size: clamp(24px, 4vw, 34px);
      letter-spacing: -0.01em;
      line-height: 1.15;
    }
    .lead {
      margin: 14px auto 0;
      max-width: 46ch;
      font-size: clamp(15px, 2vw, 17px);
      font-weight: 500;
      line-height: 1.45;
      color: var(--dac-accent-hi);
    }
    .body {
      margin: 20px auto 0;
      max-width: 56ch;
      font-size: 14.5px;
      line-height: 1.68;
      color: var(--dac-ink-2);
    }

    .rail {
      margin: 44px auto 0;
      display: flex;
      align-items: stretch;
      gap: 10px;
      max-width: 560px;
    }
    .step {
      flex: 1;
      padding: 14px 12px;
      border-radius: var(--dac-radius-sm);
      border: 1px solid var(--dac-border);
      background: var(--dac-surface);
      text-align: left;
    }
    .step .n {
      font-size: 11px; font-weight: 700; letter-spacing: 0.12em;
      color: var(--dac-ink-3);
    }
    .step .l { margin-top: 4px; font-size: 13.5px; font-weight: 500; color: var(--dac-ink-2); }
    .step[data-state="done"] { border-color: rgba(12,163,12,0.38); }
    .step[data-state="done"] .n { color: var(--dac-good); }
    .step[data-state="here"] {
      border-color: rgba(25,143,217,0.45);
      background: var(--dac-accent-soft);
      box-shadow: 0 0 28px -12px var(--dac-accent-glow);
    }
    .step[data-state="here"] .n { color: var(--dac-accent-hi); }
    .step[data-state="here"] .l { color: var(--dac-ink); }

    .note { margin-top: 22px; font-size: 12px; color: var(--dac-ink-3); }

    @media (max-width: 560px) { .rail { flex-direction: column; } }
  `;

  /** @param {string} id key of SECTIONS */
  set section(id) {
    this.section_ = SECTIONS[id];
    if (this.rendered_) this.fill_();
  }

  render() {
    return `
      <div class="wrap">
        <div class="mark" id="mark"></div>
        <h1 id="title"></h1>
        <p class="lead" id="lead"></p>
        <p class="body" id="body"></p>
        <div class="rail" id="rail"></div>
        <p class="note">Deze sectie is nog in aanbouw. De navigatie werkt al, zodat het geheel te beoordelen is.</p>
      </div>
    `;
  }

  afterRender() {
    this.fill_();
  }

  fill_() {
    const s = this.section_;
    if (!s) return;

    this.$("#mark").innerHTML = icons[s.icon];
    this.$("#title").textContent = s.title;
    this.$("#lead").textContent = s.lead;
    this.$("#body").textContent = s.body;

    this.$("#rail").innerHTML = PHASES.map((p) => {
      const state = p.n < s.phase ? "done" : p.n === s.phase ? "here" : "next";
      return `<div class="step" data-state="${state}">
        <div class="n">FASE ${p.n}</div><div class="l">${p.label}</div>
      </div>`;
    }).join("");
  }
}

define("dac-view-placeholder", DacViewPlaceholder);
