/**
 * The panel header.
 *
 * A custom panel replaces Home Assistant's own toolbar, so this header is the
 * only chrome the user gets. Customers run their dashboard behind Kiosk Mode,
 * which hides the HA header and sidebar and takes away tab navigation -- so the
 * header carries both the section navigation and an explicit way back to the
 * home dashboard.
 */

import { DacElement, define } from "./base.js";
import { icons } from "./icons.js";

export const NAV_ITEMS = [
  { id: "overzicht", label: "Overzicht", icon: "gauge" },
  { id: "apparaten", label: "Apparaten", icon: "devices" },
  { id: "strategie", label: "Strategie", icon: "compass" },
  { id: "installatie", label: "Installatie", icon: "plug" },
  { id: "instellingen", label: "Instellingen", icon: "sliders" },
];

class DacHeader extends DacElement {
  static css = /* css */ `
    :host {
      position: sticky;
      top: 0;
      z-index: 20;
      background: linear-gradient(180deg, rgba(12,12,10,0.94) 0%, rgba(12,12,10,0.76) 100%);
      backdrop-filter: blur(22px) saturate(150%);
      -webkit-backdrop-filter: blur(22px) saturate(150%);
      border-bottom: 1px solid var(--dac-border);
    }

    /* Hairline of brand colour under the header. */
    :host::after {
      content: "";
      position: absolute;
      inset: auto 0 -1px 0;
      height: 1px;
      background: linear-gradient(90deg,
        transparent 0%, var(--dac-accent) 22%, var(--dac-accent-hi) 50%,
        var(--dac-accent) 78%, transparent 100%);
      opacity: 0.55;
    }

    .bar {
      max-width: var(--dac-maxw);
      margin: 0 auto;
      min-height: var(--dac-header-h);
      padding: 0 22px;
      display: flex;
      align-items: center;
      gap: 18px;
    }

    /* ---- brand ---- */
    .brand {
      display: flex;
      align-items: center;
      gap: 11px;
      flex: 0 0 auto;
      user-select: none;
    }
    .mark {
      width: 34px;
      height: 34px;
      display: grid;
      place-items: center;
      border-radius: 11px;
      color: #fff;
      background: linear-gradient(145deg, var(--dac-accent-hi), var(--dac-accent) 70%, #01507a);
      box-shadow: 0 0 0 1px rgba(25,143,217,0.35), 0 6px 18px -6px var(--dac-accent-glow);
    }
    .mark .icon { width: 19px; height: 19px; }
    .brand-text { display: flex; align-items: baseline; gap: 6px; line-height: 1; }
    .brand-1 {
      font-size: 15px;
      font-weight: 600;
      letter-spacing: 0.015em;
      color: var(--dac-ink);
    }
    .brand-2 {
      font-family: var(--dac-display);
      font-style: italic;
      font-weight: 400;
      font-size: 21px;
      color: var(--dac-accent-hi);
    }

    /* ---- nav ---- */
    nav {
      position: relative;
      flex: 1 1 auto;
      display: flex;
      justify-content: center;
      gap: 2px;
      overflow-x: auto;
      scrollbar-width: none;
      -webkit-overflow-scrolling: touch;
      padding: 4px 0;
    }
    nav::-webkit-scrollbar { display: none; }

    .pill-bg {
      position: absolute;
      top: 4px;
      left: 0;
      height: calc(100% - 8px);
      border-radius: var(--dac-radius-pill);
      background: var(--dac-accent-soft);
      border: 1px solid rgba(25,143,217,0.38);
      box-shadow: 0 0 22px -6px var(--dac-accent-glow);
      transition: transform 380ms cubic-bezier(0.22,0.61,0.36,1),
                  width 380ms cubic-bezier(0.22,0.61,0.36,1),
                  opacity 200ms ease;
      opacity: 0;
      pointer-events: none;
    }
    .pill-bg.on { opacity: 1; }

    button.pill {
      position: relative;
      z-index: 1;
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 15px;
      border: 0;
      background: transparent;
      border-radius: var(--dac-radius-pill);
      font: inherit;
      font-size: 13.5px;
      font-weight: 500;
      letter-spacing: 0.005em;
      color: var(--dac-ink-2);
      cursor: pointer;
      white-space: nowrap;
      transition: color 200ms ease;
    }
    button.pill .icon { width: 17px; height: 17px; opacity: 0.75; transition: opacity 200ms ease; }
    button.pill:hover { color: var(--dac-ink); }
    button.pill:hover .icon { opacity: 1; }
    button.pill[aria-current="page"] { color: var(--dac-ink); font-weight: 600; }
    button.pill[aria-current="page"] .icon { opacity: 1; color: var(--dac-accent-hi); }

    /* ---- actions ---- */
    .actions { flex: 0 0 auto; display: flex; align-items: center; gap: 8px; }

    button.ghost {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 15px 9px 12px;
      border-radius: var(--dac-radius-pill);
      border: 1px solid var(--dac-border-hi);
      background: var(--dac-surface);
      color: var(--dac-ink-2);
      font: inherit;
      font-size: 13.5px;
      font-weight: 500;
      cursor: pointer;
      transition: border-color 200ms ease, color 200ms ease, background 200ms ease;
    }
    button.ghost .icon { width: 18px; height: 18px; }
    button.ghost:hover {
      color: var(--dac-ink);
      border-color: rgba(25,143,217,0.55);
      background: var(--dac-accent-soft);
    }

    button.icon-only {
      display: none;
      padding: 9px;
      border-radius: 12px;
      border: 1px solid var(--dac-border);
      background: transparent;
      color: var(--dac-ink-2);
      cursor: pointer;
    }
    button.icon-only .icon { width: 20px; height: 20px; }

    /* ---- responsive ---- */
    @media (max-width: 1080px) {
      .bar { flex-wrap: wrap; padding: 10px 16px 0; gap: 12px; }
      .brand { order: 1; margin-right: auto; }
      .actions { order: 2; }
      nav { order: 3; flex-basis: 100%; justify-content: flex-start; }
    }
    @media (max-width: 640px) {
      :host([narrow]) button.icon-only { display: inline-flex; }
      .brand-1 { font-size: 14px; }
      .brand-2 { font-size: 19px; }
      button.ghost span { display: none; }
      button.ghost { padding: 9px; }
    }
  `;

  set active(value) {
    if (this.active_ === value) return;
    this.active_ = value;
    this.syncActive_();
  }

  get active() {
    return this.active_;
  }

  render() {
    const pills = NAV_ITEMS.map(
      (item) => `
        <button class="pill" type="button" data-id="${item.id}">
          ${icons[item.icon]}<span>${item.label}</span>
        </button>`
    ).join("");

    return `
      <div class="bar">
        <button class="icon-only" type="button" id="menu" title="Menu" aria-label="Menu">
          ${icons.menu}
        </button>
        <div class="brand">
          <div class="mark">${icons.bolt}</div>
          <div class="brand-text">
            <span class="brand-1">DomotiApp</span>
            <span class="brand-2">Coach</span>
          </div>
        </div>
        <nav aria-label="Dashboardsecties">
          <div class="pill-bg" aria-hidden="true"></div>
          ${pills}
        </nav>
        <div class="actions">
          <button class="ghost" type="button" id="home" title="Terug naar je eigen dashboard">
            ${icons.home}<span>Home</span>
          </button>
        </div>
      </div>
    `;
  }

  afterRender() {
    this.$("#home").addEventListener("click", () => this.fire("dac-home"));
    this.$("#menu").addEventListener("click", () => this.fire("dac-menu"));

    for (const pill of this.$$("button.pill")) {
      pill.addEventListener("click", () =>
        this.fire("dac-navigate", { id: pill.dataset.id })
      );
    }

    // The sliding highlight is measured, so it has to be re-measured whenever
    // the bar reflows (window resize, sidebar collapse, font swap).
    this.observer_ = new ResizeObserver(() => this.syncActive_());
    this.observer_.observe(this.$("nav"));
    document.fonts?.ready.then(() => this.syncActive_());

    this.syncActive_();
  }

  disconnectedCallback() {
    this.observer_?.disconnect();
  }

  /** Move the highlight under the active pill and update ARIA state. */
  syncActive_() {
    if (!this.rendered_) return;
    const bg = this.$(".pill-bg");
    let target = null;

    for (const pill of this.$$("button.pill")) {
      const on = pill.dataset.id === this.active_;
      if (on) {
        pill.setAttribute("aria-current", "page");
        target = pill;
      } else {
        pill.removeAttribute("aria-current");
      }
    }

    if (!target) {
      bg.classList.remove("on");
      return;
    }
    bg.classList.add("on");
    bg.style.width = `${target.offsetWidth}px`;
    bg.style.transform = `translateX(${target.offsetLeft}px)`;
  }
}

define("dac-header", DacHeader);
