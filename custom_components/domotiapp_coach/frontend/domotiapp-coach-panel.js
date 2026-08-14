/**
 * DomotiApp Coach -- Home Assistant sidebar panel.
 *
 * A custom panel takes over the whole content area, so this component owns its
 * own chrome: header, navigation and routing. Home Assistant passes in `hass`,
 * `narrow`, `route` and `panel`.
 *
 * Live values do not come from that `hass` object. The panel subscribes to
 * `state_changed` itself and keeps its own feed -- see state-feed.js for why.
 *
 * Settings live in HA storage, fetched once over the websocket API and
 * refreshed whenever another device saves, so a wall tablet picks up a change
 * made on a phone without a reload.
 *
 * Everything is plain ES modules and standard web components -- no build step,
 * which is what keeps the repository installable straight from HACS.
 */

import { DacElement, define } from "./src/base.js";
import { StateFeed } from "./src/state-feed.js";
import { navItemsFor } from "./src/header.js";
import { SECTIONS } from "./src/views/placeholder.js";
import "./src/header.js";
import "./src/views/overview.js";
import "./src/views/devices.js";
import "./src/views/installation.js";
import "./src/views/settings.js";
import "./src/views/placeholder.js";

const DEFAULT_VIEW = "overzicht";
const EVENT_SETTINGS_UPDATED = "domotiapp_coach_settings_updated";

/** Sections that are built; anything else falls back to the placeholder. */
const BUILT = {
  overzicht: "dac-view-overview",
  apparaten: "dac-view-devices",
  installatie: "dac-view-installation",
  instellingen: "dac-view-settings",
};

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

    .enter { animation: enter 320ms cubic-bezier(0.22, 0.61, 0.36, 1) both; }
    @keyframes enter {
      from { opacity: 0; transform: translateY(10px); }
      to   { opacity: 1; transform: none; }
    }
  `;

  constructor() {
    super();
    this.views_ = new Map();
    this.active_ = DEFAULT_VIEW;
    this.settings_ = null;
    this.feed_ = new StateFeed();
  }

  // --- properties set by Home Assistant ---------------------------------

  set hass(value) {
    this.hass_ = value;
    // Seeds the feed and, the first time, starts the subscription that keeps it
    // current regardless of whether this property is ever set again.
    this.feed_.connect(value);

    for (const view of this.views_.values()) view.hass = value;
    if (this.rendered_) this.$("dac-header").isAdmin = this.isAdmin_();

    this.loadSettings_();
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

  /** Unknown rights are treated as admin: HA itself gates the panel. */
  isAdmin_() {
    return this.hass_?.user?.is_admin !== false;
  }

  // --- settings ----------------------------------------------------------

  /** Fetch the settings once, then follow them over the event bus. */
  async loadSettings_() {
    if (!this.hass_ || this.settingsRequested_) return;
    this.settingsRequested_ = true;

    try {
      this.applySettings_(await this.hass_.callWS({ type: "domotiapp_coach/settings/get" }));
    } catch (error) {
      console.warn("[DomotiApp Coach] kon instellingen niet laden", error);
    }

    try {
      this.unsubscribe_ = await this.hass_.connection.subscribeEvents(
        (event) => this.applySettings_(event?.data?.settings),
        EVENT_SETTINGS_UPDATED
      );
    } catch (error) {
      console.warn("[DomotiApp Coach] kon instellingen niet volgen", error);
    }
  }

  applySettings_(settings) {
    if (!settings) return;
    this.settings_ = settings;
    for (const view of this.views_.values()) view.settings = settings;
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
    header.isAdmin = this.isAdmin_();
    header.addEventListener("dac-navigate", (ev) => this.navigate_(ev.detail.id));
    header.addEventListener("dac-home", () => this.goHome_());
    header.addEventListener("dac-menu", () => this.fire("hass-toggle-menu"));

    // A save from an editor is applied straight away rather than waiting for the
    // round trip over the event bus.
    this.addEventListener("dac-settings-saved", (ev) => this.applySettings_(ev.detail.settings));

    this.loadSettings_();
    this.syncRoute_();
  }

  disconnectedCallback() {
    this.unsubscribe_?.();
    this.feed_.disconnect();
  }

  /** Read the active section from the panel route and show it. */
  syncRoute_() {
    const segment = (this.route_?.path || "").replace(/^\/+|\/+$/g, "");
    const allowed = navItemsFor(this.isAdmin_()).map((item) => item.id);
    // A customer who types or bookmarks the settings path lands on Overzicht
    // rather than on a screen they are not meant to have.
    const next = allowed.includes(segment) ? segment : DEFAULT_VIEW;

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

    // The class has to come off once it has played. A filling animation leaves
    // an identity `transform` behind rather than `none`, and any transform --
    // identity included -- makes the element a containing block for `position:
    // fixed`. That silently pins a save bar to the bottom of the document
    // instead of the bottom of the screen.
    view.addEventListener("animationend", () => view.classList.remove("enter"), { once: true });

    // Views are cached, so without this a section opened from halfway down the
    // previous one starts halfway down itself.
    if (this.shown_ && this.shown_ !== id) window.scrollTo({ top: 0 });

    this.shown_ = id;
  }

  /** Views are cached so returning to a section keeps its state. */
  viewFor_(id) {
    if (this.views_.has(id)) return this.views_.get(id);

    let el;
    if (BUILT[id]) {
      el = document.createElement(BUILT[id]);
    } else {
      el = document.createElement("dac-view-placeholder");
      el.section = SECTIONS[id] ? id : "strategie";
    }

    el.hass = this.hass_;
    el.stateFeed = this.feed_;
    el.settings = this.settings_;

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
    let target = this.settings_?.navigation?.home_path || "/lovelace/0";
    if (!target.startsWith("/")) target = `/${target}`;

    history.pushState(null, "", target);
    this.fire("location-changed");
  }
}

define("domotiapp-coach-panel", DomotiAppCoachPanel);
