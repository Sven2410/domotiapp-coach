/**
 * DomotiApp Coach -- Home Assistant sidebar panel.
 *
 * A custom panel takes over the whole content area, so this component owns its
 * own chrome: header, navigation and routing. Home Assistant passes in `hass`,
 * `narrow`, `route` and `panel` (with the config set in __init__.py).
 *
 * Everything is plain ES modules and standard web components -- no build step,
 * which is what keeps the repository installable straight from HACS.
 */

import { DacElement, define } from "./src/base.js";
import { ensureFonts } from "./src/theme.js";
import { NAV_ITEMS } from "./src/header.js";
import { SECTIONS } from "./src/views/placeholder.js";
import "./src/header.js";
import "./src/views/overview.js";
import "./src/views/placeholder.js";

ensureFonts();

const DEFAULT_VIEW = "overzicht";
const VIEW_IDS = NAV_ITEMS.map((item) => item.id);

class DomotiAppCoachPanel extends DacElement {
  static css = /* css */ `
    :host {
      display: block;
      position: relative;
      min-height: 100vh;
      background: var(--dac-bg);
      color: var(--dac-ink);
    }

    /* Ambient brand light, behind everything. */
    .bg {
      position: fixed;
      inset: 0;
      z-index: 0;
      pointer-events: none;
      background:
        radial-gradient(880px 520px at 10% -8%, rgba(2, 111, 161, 0.18), transparent 62%),
        radial-gradient(720px 440px at 92% 4%, rgba(25, 143, 217, 0.10), transparent 64%),
        radial-gradient(600px 600px at 50% 108%, rgba(2, 111, 161, 0.07), transparent 60%);
    }

    .shell { position: relative; z-index: 1; }

    main { display: block; }

    .enter { animation: enter 340ms cubic-bezier(0.22, 0.61, 0.36, 1) both; }
    @keyframes enter {
      from { opacity: 0; transform: translateY(10px); }
      to   { opacity: 1; transform: none; }
    }
  `;

  constructor() {
    super();
    this.views_ = new Map();
    this.active_ = DEFAULT_VIEW;
  }

  // --- properties set by Home Assistant ---------------------------------

  set hass(value) {
    this.hass_ = value;
  }

  get hass() {
    return this.hass_;
  }

  set narrow(value) {
    this.narrow_ = !!value;
    if (this.rendered_) this.$("dac-header").toggleAttribute("narrow", this.narrow_);
  }

  set route(value) {
    this.route_ = value;
    this.syncRoute_();
  }

  set panel(value) {
    this.panel_ = value;
    this.config_ = value?.config ?? {};
  }

  // --- rendering ---------------------------------------------------------

  render() {
    return `
      <div class="bg"></div>
      <div class="shell">
        <dac-header></dac-header>
        <main id="main"></main>
      </div>
    `;
  }

  afterRender() {
    const header = this.$("dac-header");
    header.toggleAttribute("narrow", !!this.narrow_);
    header.addEventListener("dac-navigate", (ev) => this.navigate_(ev.detail.id));
    header.addEventListener("dac-home", () => this.goHome_());
    header.addEventListener("dac-menu", () => this.fire("hass-toggle-menu"));

    this.syncRoute_();
  }

  /** Read the active section from the panel route and show it. */
  syncRoute_() {
    const segment = (this.route_?.path || "").replace(/^\/+|\/+$/g, "");
    const next = VIEW_IDS.includes(segment) ? segment : DEFAULT_VIEW;
    if (this.rendered_ && next === this.shown_) return;

    this.active_ = next;
    if (!this.rendered_) return;

    this.$("dac-header").active = next;
    this.showView_(next);
  }

  showView_(id) {
    const main = this.$("#main");
    const view = this.viewFor_(id);

    main.replaceChildren(view);
    view.classList.remove("enter");
    // Restart the entry animation on every switch.
    void view.offsetWidth;
    view.classList.add("enter");

    this.shown_ = id;
  }

  /** Views are cached so returning to a section keeps its state. */
  viewFor_(id) {
    if (this.views_.has(id)) return this.views_.get(id);

    let el;
    if (id === "overzicht") {
      el = document.createElement("dac-view-overview");
      el.demo = this.config_?.demo_mode !== false;
    } else {
      el = document.createElement("dac-view-placeholder");
      el.section = SECTIONS[id] ? id : "instellingen";
    }

    this.views_.set(id, el);
    return el;
  }

  // --- navigation --------------------------------------------------------

  /**
   * Navigate inside the panel.
   *
   * Customers run Kiosk Mode, which strips the sidebar and the tab bar, so the
   * header is the only navigation they have. Pushing state and firing
   * `location-changed` is the same mechanism Home Assistant's own panels use,
   * so the browser back button keeps working.
   */
  navigate_(id) {
    const base = this.route_?.prefix || `/${location.pathname.split("/")[1]}`;
    const path = id === DEFAULT_VIEW ? base : `${base}/${id}`;
    if (location.pathname === path) return;

    history.pushState(null, "", path);
    this.fire("location-changed");
  }

  /** Leave the panel for the customer's own dashboard. */
  goHome_() {
    let target = this.config_?.home_path || "/lovelace/0";
    if (!target.startsWith("/")) target = `/${target}`;

    history.pushState(null, "", target);
    this.fire("location-changed");
  }
}

define("domotiapp-coach-panel", DomotiAppCoachPanel);
