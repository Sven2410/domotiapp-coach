/**
 * The panel header.
 *
 * A custom panel replaces Home Assistant's own toolbar, so this header is the
 * only chrome the user gets. Customers run their dashboard behind Kiosk Mode,
 * which hides the HA header and sidebar and takes away tab navigation -- so the
 * header carries both the section navigation and an explicit way back to the
 * home dashboard.
 *
 * On a phone the five sections do not fit side by side, so the navigation drops
 * to its own scrollable row under the brand and the active pill is scrolled into
 * view. Most customers open this on a phone, so that row is the layout that
 * matters, not the desktop one.
 */

import { DacElement, define } from "./base.js";
import { icons } from "./icons.js";

export const NAV_ITEMS = [
  { id: "overzicht", label: "Overzicht", icon: "gauge" },
  { id: "historie", label: "Historie", icon: "gauge" },
  { id: "apparaten", label: "Apparaten", icon: "devices", adminOnly: true },
  { id: "strategie", label: "Strategie", icon: "compass" },
  { id: "installatie", label: "Installatie", icon: "plug" },
  // Points straight at raw entities, so it is for the installer only. Customers
  // do get Installatie, where the same configuration is shown in their terms.
  { id: "instellingen", label: "Instellingen", icon: "sliders", adminOnly: true },
];

/** The sections this user may open. */
export const navItemsFor = (isAdmin) =>
  NAV_ITEMS.filter((item) => isAdmin || !item.adminOnly);

const LOGO_URL = new URL("../img/domotitech-mark.png", import.meta.url).href;

class DacHeader extends DacElement {
  static css = /* css */ `
    :host {
      position: sticky;
      top: 0;
      z-index: 20;
      /* Behind a Dynamic Island or a notch there is no room for anything
         readable, so the header's own background fills that strip and the bar
         starts below it. Zero everywhere that has no cutout. */
      padding-top: var(--dac-safe-t);
      background: linear-gradient(180deg, rgba(12,12,10,0.96) 0%, rgba(12,12,10,0.82) 100%);
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
      /* In landscape the island eats a strip down one side of the screen. */
      padding: 0 max(20px, var(--dac-safe-r)) 0 max(20px, var(--dac-safe-l));
      display: flex;
      align-items: center;
      gap: 16px;
    }

    /* ---- brand ---- */
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      flex: 0 0 auto;
      user-select: none;
      min-width: 0;
    }
    .brand img {
      width: 34px;
      height: 34px;
      flex: 0 0 auto;
      object-fit: contain;
      display: block;
    }
    .brand-text {
      display: flex;
      align-items: baseline;
      gap: 5px;
      line-height: 1.1;
      white-space: nowrap;
      min-width: 0;
    }
    .brand-1 {
      font-size: 15px;
      font-weight: 600;
      letter-spacing: 0.01em;
      color: var(--dac-ink);
    }
    .brand-2 {
      font-size: 15px;
      font-weight: 600;
      letter-spacing: 0.01em;
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
      overscroll-behavior-x: contain;
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
      color: var(--dac-ink-2);
      cursor: pointer;
      white-space: nowrap;
      transition: color 200ms ease;
      -webkit-tap-highlight-color: transparent;
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
      -webkit-tap-highlight-color: transparent;
    }
    button.ghost .icon { width: 18px; height: 18px; }
    button.ghost:hover {
      color: var(--dac-ink);
      border-color: rgba(25,143,217,0.55);
      background: var(--dac-accent-soft);
    }

    /* ---- responsive ---- */
    @media (max-width: 1080px) {
      .bar {
        flex-wrap: wrap;
        padding: 10px max(16px, var(--dac-safe-r)) 0 max(16px, var(--dac-safe-l));
        gap: 10px;
      }
      .brand { order: 1; margin-right: auto; }
      .actions { order: 2; }
      nav { order: 3; flex-basis: 100%; justify-content: flex-start; }
    }

    @media (max-width: 640px) {
      .bar { padding: 8px max(12px, var(--dac-safe-r)) 0 max(12px, var(--dac-safe-l)); }
      .brand img { width: 30px; height: 30px; }
      .brand-1, .brand-2 { font-size: 14px; }
      button.ghost span { display: none; }
      button.ghost { padding: 9px; }
      button.pill { padding: 8px 12px; font-size: 13px; }
      /* Fade the right edge so it reads as "more sections that way". */
      nav {
        padding-right: 14px;
        mask-image: linear-gradient(90deg, #000 calc(100% - 22px), transparent 100%);
        -webkit-mask-image: linear-gradient(90deg, #000 calc(100% - 22px), transparent 100%);
      }
    }

    @media (max-width: 380px) {
      .brand-text { display: none; }
    }
  `;

  constructor() {
    super();
    this.isAdmin_ = true;
  }

  set active(value) {
    if (this.active_ === value) return;
    this.active_ = value;
    this.syncActive_();
  }

  get active() {
    return this.active_;
  }

  /** Rebuild the bar when the user's rights become known. */
  set isAdmin(value) {
    const next = value !== false;
    if (next === this.isAdmin_ && this.rendered_) return;
    this.isAdmin_ = next;
    if (!this.rendered_) return;

    // Rebuilt rather than hidden, so the sliding highlight measures against the
    // pills that are actually there.
    this.observer_?.disconnect();
    this.shadowRoot.replaceChildren();
    this.rendered_ = false;
    this.connectedCallback();
    this.syncActive_();
  }

  render() {
    const pills = navItemsFor(this.isAdmin_).map(
      (item) => `
        <button class="pill" type="button" data-id="${item.id}">
          ${icons[item.icon]}<span>${item.label}</span>
        </button>`
    ).join("");

    return `
      <div class="bar">
        <div class="brand">
          <img src="${LOGO_URL}" alt="DomotiTech" draggable="false">
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

    for (const pill of this.$$("button.pill")) {
      pill.addEventListener("click", () =>
        this.fire("dac-navigate", { id: pill.dataset.id })
      );
    }

    this.syncActive_();
  }

  onConnect() {
    // The sliding highlight is measured, so it has to be re-measured whenever
    // the bar reflows (window resize, sidebar collapse, orientation change).
    this.observer_ ??= new ResizeObserver(() => this.syncActive_());
    this.observer_.observe(this.$("nav"));
    this.syncActive_();
  }

  onDisconnect() {
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

    // On a phone the row scrolls, so the active section has to be brought into
    // view or navigating can leave the highlight off screen.
    const nav = this.$("nav");
    if (nav.scrollWidth > nav.clientWidth) {
      const left = target.offsetLeft - (nav.clientWidth - target.offsetWidth) / 2;
      nav.scrollTo({ left: Math.max(0, left), behavior: "smooth" });
    }
  }
}

define("dac-header", DacHeader);
