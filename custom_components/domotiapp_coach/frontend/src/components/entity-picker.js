/**
 * Pick a Home Assistant entity.
 *
 * This replaces `<input list>` with a real listbox. The native datalist looked
 * like the cheap option but misbehaves badly here: inside a shadow root its
 * popup is positioned against the document rather than the field, so tapping a
 * second field flashes a stray box off to the side, and picking a suggestion
 * gives no visible sign that anything was selected.
 *
 * What "selected" looks like is the point of this component. A bare entity id
 * in a text field tells a customer nothing, so a chosen entity shows its
 * friendly name in the field and its id plus current reading underneath -- which
 * doubles as the check that they picked the right sensor.
 *
 * The `filter` is a ranking, not a restriction. Sensors at customers are named
 * and classified inconsistently enough that a hard filter would eventually hide
 * the one entity someone needs, so unmatched entities stay reachable under a
 * divider instead of being dropped.
 */

import { DacElement, define } from "../base.js";
import { icons } from "../icons.js";
import { power, toWatts } from "../format.js";

/** How many options to render at once -- enough to browse, not enough to lag. */
const MAX_OPTIONS = 60;

const POWER_UNITS = new Set(["w", "kw", "mw"]);

/**
 * The one picker whose list is open, across every shadow root on the page.
 *
 * Each picker lives in its own shadow root and so cannot see the others; without
 * this, moving from one field to the next leaves both lists hanging on screen,
 * overlapping each other and the fields around them.
 */
let openPicker = null;

const MATCHERS = {
  power: (attrs, unit) => POWER_UNITS.has(unit) || attrs.device_class === "power",
  price: (attrs, unit) => attrs.device_class === "monetary" || unit.includes("/kwh"),
  all: () => true,
};

class DacEntityPicker extends DacElement {
  static css = /* css */ `
    :host { display: block; position: relative; }

    .field {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 0 8px 0 12px;
      border-radius: var(--dac-radius-sm);
      border: 1px solid var(--dac-border-hi);
      background: rgba(255,255,255,0.04);
      min-height: 44px;
      transition: border-color 160ms ease, background 160ms ease;
    }
    .field:focus-within { border-color: var(--dac-accent-hi); }
    :host([chosen]) .field { border-color: rgba(25,143,217,0.45); background: var(--dac-accent-soft); }

    input {
      flex: 1 1 auto;
      min-width: 0;
      padding: 10px 0;
      border: 0;
      background: transparent;
      color: var(--dac-ink);
      font: inherit;
      font-size: 14px;
      outline: none;
    }
    input::placeholder { color: var(--dac-ink-3); }

    button {
      flex: 0 0 auto;
      display: grid;
      place-items: center;
      width: 30px; height: 30px;
      padding: 0;
      border: 0;
      border-radius: 8px;
      background: transparent;
      color: var(--dac-ink-3);
      cursor: pointer;
    }
    button:hover { color: var(--dac-ink); background: rgba(255,255,255,0.06); }
    button .icon { width: 15px; height: 15px; }
    button[hidden] { display: none; }

    /* ---- what is currently chosen ---- */
    .chosen {
      margin-top: 6px;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: var(--dac-ink-3);
      min-width: 0;
    }
    .chosen[hidden] { display: none; }
    .chosen .id {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .chosen .now {
      flex: 0 0 auto;
      margin-left: auto;
      padding: 2px 8px;
      border-radius: var(--dac-radius-pill);
      background: rgba(255,255,255,0.06);
      color: var(--dac-ink-2);
      font-variant-numeric: tabular-nums;
    }
    .chosen .now.bad { color: var(--dac-warn); }

    /* ---- the list ---- */
    .options {
      position: absolute;
      left: 0; right: 0;
      z-index: 40;
      margin: 4px 0 0;
      padding: 5px;
      list-style: none;
      max-height: 268px;
      overflow-y: auto;
      overscroll-behavior: contain;
      -webkit-overflow-scrolling: touch;
      border-radius: var(--dac-radius-sm);
      border: 1px solid var(--dac-border-hi);
      background: #161613;
      box-shadow: 0 24px 50px -18px rgba(0,0,0,0.95);
    }
    .options[hidden] { display: none; }
    :host([drop-up]) .options { bottom: 100%; margin: 0 0 4px; }

    li {
      padding: 9px 11px;
      border-radius: 9px;
      cursor: pointer;
      display: grid;
      gap: 1px;
    }
    li .name { font-size: 13.5px; color: var(--dac-ink); }
    li .id {
      font-size: 11.5px;
      color: var(--dac-ink-3);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    li[aria-selected="true"], li:hover { background: var(--dac-accent-soft); }
    li[aria-selected="true"] .id, li:hover .id { color: var(--dac-ink-2); }

    li.divider {
      padding: 10px 11px 4px;
      cursor: default;
      font-size: 10.5px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--dac-ink-3);
    }
    li.divider:hover { background: transparent; }
    li.none { cursor: default; color: var(--dac-ink-3); font-size: 13px; }
    li.none:hover { background: transparent; }
  `;

  constructor() {
    super();
    this.value_ = "";
    this.filter_ = "all";
    this.open_ = false;
    this.active_ = -1;
    this.rows_ = [];
  }

  /**
   * The live state feed. Preferred over `hass` for the same reason the rest of
   * the panel uses it: the reading shown under a chosen entity is the check
   * that it is the right sensor, so it has to be the current one.
   *
   * @param {import("../state-feed.js").StateFeed} value
   */
  set stateFeed(value) {
    this.feed_ = value;
    this.listen_();
    if (this.rendered_) this.paintChosen_();
  }

  /** (Re)attach to the feed. Safe to call repeatedly. */
  listen_() {
    this.unsubscribe_?.();
    this.unsubscribe_ = this.feed_?.subscribe((id) => {
      if (id === this.value_ && this.rendered_) this.paintChosen_();
    });
  }

  set hass(value) {
    this.hass_ = value;
    if (this.rendered_) this.paintChosen_();
  }

  /** State object for an entity, from the feed when there is one. */
  state_(entityId) {
    if (!entityId) return undefined;
    return this.feed_ ? this.feed_.get(entityId) : this.hass_?.states?.[entityId];
  }

  /** Every entity id we can offer. */
  allIds_() {
    if (this.feed_) return this.feed_.ids();
    return Object.keys(this.hass_?.states ?? {});
  }

  /** @param {"power"|"price"|"all"} value */
  set filter(value) {
    this.filter_ = value in MATCHERS ? value : "all";
  }

  set placeholder(value) {
    this.placeholder_ = value;
    if (this.rendered_) this.$("input").placeholder = value;
  }

  set value(next) {
    this.value_ = next ?? "";
    if (this.rendered_) this.paint_();
  }

  get value() {
    return this.value_;
  }

  render() {
    return `
      <div class="field">
        <input type="text" role="combobox" aria-expanded="false" aria-autocomplete="list"
               autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"
               placeholder="${this.placeholder_ ?? "Zoek een sensor…"}">
        <button type="button" id="clear" aria-label="Wissen" hidden>${icons.close}</button>
        <button type="button" id="open" aria-label="Toon lijst" tabindex="-1">${icons.search}</button>
      </div>
      <div class="chosen" id="chosen" hidden>
        <span class="id" id="chosen-id"></span>
        <span class="now" id="chosen-now"></span>
      </div>
      <ul class="options" id="options" role="listbox" hidden></ul>
    `;
  }

  afterRender() {
    const input = this.$("input");

    input.addEventListener("focus", () => {
      input.select();
      this.openList_("");
    });
    input.addEventListener("input", () => this.openList_(input.value));
    input.addEventListener("keydown", (ev) => this.onKey_(ev));
    // Leaving without picking must not look like it cleared the field, so the
    // input is put back to whatever is actually selected.
    input.addEventListener("blur", () => {
      setTimeout(() => {
        if (this.shadowRoot.activeElement === input) return;
        this.closeList_();
        this.paint_();
      }, 0);
    });

    this.$("#clear").addEventListener("click", () => {
      this.commit_("");
      input.focus();
    });
    this.$("#open").addEventListener("click", () => {
      input.focus();
      this.openList_("");
    });

    // mousedown, not click: click fires after blur, by which time the list is
    // already gone and the tap lands on nothing.
    this.$("#options").addEventListener("mousedown", (ev) => {
      const li = ev.target.closest("li[data-id]");
      if (!li) return;
      ev.preventDefault();
      this.commit_(li.dataset.id);
      this.closeList_();
    });

    this.paint_();
  }

  onConnect() {
    // Reattached elements have to pick their subscription back up, or the
    // reading under a chosen entity quietly stops following it.
    this.listen_();
    if (this.rendered_) this.paintChosen_();
  }

  onDisconnect() {
    this.closeList_();
    this.unsubscribe_?.();
    this.unsubscribe_ = null;
  }

  // --- data --------------------------------------------------------------

  friendly_(id) {
    return this.state_(id)?.attributes?.friendly_name || id;
  }

  /** Entities split into preferred (matching the filter) and the rest. */
  candidates_(query) {
    const match = MATCHERS[this.filter_];
    const q = query.trim().toLowerCase();

    const preferred = [];
    const other = [];

    for (const id of this.allIds_()) {
      const attrs = this.state_(id)?.attributes ?? {};
      const name = attrs.friendly_name || "";
      if (q && !id.toLowerCase().includes(q) && !name.toLowerCase().includes(q)) continue;

      const unit = String(attrs.unit_of_measurement ?? "").toLowerCase();
      (match(attrs, unit) ? preferred : other).push(id);
    }

    preferred.sort();
    other.sort();
    return { preferred, other };
  }

  // --- list --------------------------------------------------------------

  openList_(query) {
    if (openPicker && openPicker !== this) openPicker.closeList_();
    openPicker = this;

    const { preferred, other } = this.candidates_(query);
    const list = this.$("#options");

    this.rows_ = [];
    let html = "";

    const section = (ids, label) => {
      if (!ids.length) return;
      if (label) html += `<li class="divider">${label}</li>`;
      for (const id of ids.slice(0, MAX_OPTIONS)) {
        this.rows_.push(id);
        html += `<li role="option" data-id="${id}" aria-selected="false">
          <span class="name">${this.friendly_(id)}</span>
          <span class="id">${id}</span>
        </li>`;
      }
    };

    section(preferred, "");
    // Only worth offering the rest once the customer has narrowed things down;
    // unfiltered it is thousands of entities and no help at all.
    if (query.trim() && other.length) section(other, "Overige entiteiten");

    if (!html) html = `<li class="none">Niets gevonden voor “${query}”</li>`;

    list.innerHTML = html;
    list.hidden = false;
    this.open_ = true;
    this.active_ = -1;
    this.$("input").setAttribute("aria-expanded", "true");
    this.placeList_();
  }

  /**
   * Flip the list above the field when there is no room below it.
   *
   * Measured against the visual viewport, not the layout one: on a phone the
   * on-screen keyboard takes half the screen without changing innerHeight, so a
   * list that "fits below" would open straight behind the keyboard.
   */
  placeList_() {
    const rect = this.getBoundingClientRect();
    const viewport = window.visualViewport?.height ?? window.innerHeight;
    const below = viewport - rect.bottom;
    this.toggleAttribute("drop-up", below < 240 && rect.top > below);
  }

  closeList_() {
    this.open_ = false;
    this.active_ = -1;
    if (openPicker === this) openPicker = null;
    if (!this.rendered_) return;
    this.$("#options").hidden = true;
    this.$("input").setAttribute("aria-expanded", "false");
  }

  onKey_(ev) {
    if (ev.key === "Escape") {
      this.closeList_();
      this.paint_();
      return;
    }

    if (ev.key === "Enter") {
      if (this.open_ && this.active_ >= 0) {
        ev.preventDefault();
        this.commit_(this.rows_[this.active_]);
        this.closeList_();
      }
      return;
    }

    if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
    ev.preventDefault();
    if (!this.open_) {
      this.openList_(this.$("input").value);
      return;
    }
    if (!this.rows_.length) return;

    const step = ev.key === "ArrowDown" ? 1 : -1;
    this.active_ = (this.active_ + step + this.rows_.length) % this.rows_.length;
    this.highlight_();
  }

  highlight_() {
    const items = this.$$("#options li[data-id]");
    items.forEach((li, index) => {
      const on = index === this.active_;
      li.setAttribute("aria-selected", String(on));
      if (on) li.scrollIntoView({ block: "nearest" });
    });
  }

  // --- selection ---------------------------------------------------------

  commit_(id) {
    if (id === this.value_) {
      this.paint_();
      return;
    }
    this.value_ = id;
    this.paint_();
    this.fire("dac-entity-change", { value: id });
  }

  paint_() {
    if (!this.rendered_) return;
    const has = Boolean(this.value_);

    this.toggleAttribute("chosen", has);
    this.$("input").value = has ? this.friendly_(this.value_) : "";
    this.$("#clear").hidden = !has;
    this.paintChosen_();
  }

  /** The line under the field: the id, and what the sensor says right now. */
  paintChosen_() {
    if (!this.rendered_) return;
    const chosen = this.$("#chosen");
    if (!this.value_) {
      chosen.hidden = true;
      return;
    }

    chosen.hidden = false;
    this.$("#chosen-id").textContent = this.value_;

    const now = this.$("#chosen-now");
    const state = this.state_(this.value_);

    if (!state) {
      now.textContent = "bestaat niet";
      now.classList.add("bad");
      return;
    }
    if (state.state === "unavailable" || state.state === "unknown") {
      now.textContent = "niet beschikbaar";
      now.classList.add("bad");
      return;
    }

    now.classList.remove("bad");
    const unit = state.attributes?.unit_of_measurement;
    const watts = toWatts(state.state, unit);
    // Power sensors get the same treatment as the dashboard so the customer can
    // see at a glance that the unit was understood.
    if (this.filter_ === "power" && watts !== null) {
      const { value, unit: shown } = power(watts);
      now.textContent = `${value} ${shown}`;
    } else {
      now.textContent = unit ? `${state.state} ${unit}` : state.state;
    }
  }
}

define("dac-entity-picker", DacEntityPicker);
