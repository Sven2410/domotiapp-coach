/**
 * Instellingen -- everything the dashboard needs to know about this house.
 *
 * It lives in the panel rather than in a Home Assistant options flow because
 * customers reach this on a phone behind Kiosk Mode, where HA's own settings
 * screens are not available to them. Settings are grouped the way they are used:
 * one heading per subject, and every control for that subject under it.
 *
 * Nothing saves as you type. Changes collect until the save bar is used, so a
 * half-typed entity id never becomes the live configuration.
 */

import { DacElement, define } from "../base.js";
import { icons } from "../icons.js";
import { DEVICE_TYPES, typeMeta } from "../devices.js";

/** Units that mark an entity as a power sensor, whatever it calls itself. */
const POWER_UNITS = new Set(["w", "kw", "mw"]);

const uid = () => `dev-${Math.random().toString(36).slice(2, 9)}`;

/** Deep clone that does not need structuredClone to be present. */
const clone = (value) => JSON.parse(JSON.stringify(value));

class DacViewSettings extends DacElement {
  static css = /* css */ `
    :host { display: block; }

    .wrap {
      max-width: 860px;
      margin: 0 auto;
      padding: 24px 22px 140px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .intro h1 { margin: 6px 0 0; font-size: 26px; font-weight: 600; letter-spacing: -0.01em; }
    .intro p { margin: 8px 0 0; font-size: 14px; line-height: 1.6; color: var(--dac-ink-2); max-width: 70ch; }

    section.card { padding: 20px 22px 22px; }
    section h2 {
      margin: 0;
      font-size: 17px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 9px;
    }
    section h2 .icon { width: 18px; height: 18px; color: var(--dac-accent-hi); }
    section .hint { margin: 8px 0 0; font-size: 13px; line-height: 1.55; color: var(--dac-ink-2); }

    .fields { margin-top: 18px; display: grid; gap: 14px; }
    .row { display: grid; gap: 6px; }
    .row > label { font-size: 13px; font-weight: 500; color: var(--dac-ink); }
    .row > .sub { font-size: 12px; color: var(--dac-ink-3); line-height: 1.45; }

    input[type="text"], input[type="number"], select {
      width: 100%;
      padding: 10px 12px;
      border-radius: var(--dac-radius-sm);
      border: 1px solid var(--dac-border-hi);
      background: rgba(255,255,255,0.04);
      color: var(--dac-ink);
      font: inherit;
      font-size: 14px;
      /* 16px on iOS or Safari zooms the page on focus; the transform keeps the
         rendered size at 14 without tripping that. */
      min-height: 42px;
    }
    input:focus, select:focus { border-color: var(--dac-accent-hi); outline: none; }
    select { appearance: none; background-image: none; }
    select option { background: #12120f; color: var(--dac-ink); }

    .two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    @media (max-width: 560px) { .two { grid-template-columns: 1fr; } }

    /* ---- checkbox ---- */
    label.check {
      margin-top: 4px;
      display: flex;
      align-items: flex-start;
      gap: 11px;
      padding: 12px 14px;
      border-radius: var(--dac-radius-sm);
      border: 1px solid var(--dac-border);
      background: rgba(255,255,255,0.022);
      cursor: pointer;
      font-size: 12.5px;
      line-height: 1.5;
      color: var(--dac-ink-2);
    }
    label.check input {
      width: 18px; height: 18px; flex: 0 0 auto; margin: 1px 0 0;
      accent-color: var(--dac-accent-hi);
      cursor: pointer;
    }
    label.check strong { display: block; font-size: 13px; font-weight: 600; color: var(--dac-ink); margin-bottom: 2px; }
    label.check:has(input:checked) { border-color: rgba(25,143,217,0.5); background: var(--dac-accent-soft); }

    /* ---- segmented choice ---- */
    .segmented { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    @media (max-width: 560px) { .segmented { grid-template-columns: 1fr; } }
    .segmented button {
      padding: 12px 14px;
      border-radius: var(--dac-radius-sm);
      border: 1px solid var(--dac-border-hi);
      background: rgba(255,255,255,0.03);
      color: var(--dac-ink-2);
      font: inherit;
      font-size: 13.5px;
      text-align: left;
      cursor: pointer;
      transition: border-color 200ms ease, background 200ms ease, color 200ms ease;
    }
    .segmented button strong { display: block; font-weight: 600; color: var(--dac-ink); margin-bottom: 3px; }
    .segmented button[aria-pressed="true"] {
      border-color: rgba(25,143,217,0.6);
      background: var(--dac-accent-soft);
      color: var(--dac-ink);
    }

    /* ---- devices ---- */
    .device {
      padding: 14px;
      border-radius: var(--dac-radius-sm);
      border: 1px solid var(--dac-border);
      background: rgba(255,255,255,0.022);
      display: grid;
      gap: 12px;
    }
    .device-head { display: flex; align-items: center; gap: 10px; }
    .device-head .chip {
      width: 32px; height: 32px; flex: 0 0 auto;
      display: grid; place-items: center;
      border-radius: 10px;
      color: var(--dac-accent-hi);
      background: var(--dac-accent-soft);
    }
    .device-head .chip .icon { width: 17px; height: 17px; }
    .device-head .name { font-size: 14px; font-weight: 600; }
    .device-head button.remove {
      margin-left: auto;
      padding: 7px;
      border-radius: 9px;
      border: 1px solid var(--dac-border);
      background: transparent;
      color: var(--dac-ink-3);
      cursor: pointer;
      line-height: 0;
    }
    .device-head button.remove:hover { color: var(--dac-bad); border-color: rgba(208,59,59,0.5); }
    .device-head button.remove .icon { width: 15px; height: 15px; }

    button.add {
      margin-top: 14px;
      display: inline-flex; align-items: center; gap: 8px;
      padding: 11px 16px;
      border-radius: var(--dac-radius-pill);
      border: 1px dashed var(--dac-border-hi);
      background: transparent;
      color: var(--dac-ink-2);
      font: inherit; font-size: 13.5px; font-weight: 500;
      cursor: pointer;
    }
    button.add:hover { color: var(--dac-ink); border-color: var(--dac-accent-hi); }
    button.add .icon { width: 16px; height: 16px; }

    .empty { font-size: 13px; color: var(--dac-ink-3); }

    /* ---- save bar ---- */
    .savebar {
      position: fixed;
      left: 0; right: 0; bottom: 0;
      z-index: 30;
      padding: 12px 22px calc(12px + env(safe-area-inset-bottom));
      background: linear-gradient(0deg, rgba(12,12,10,0.98) 60%, rgba(12,12,10,0.0));
      display: flex; align-items: center; gap: 12px; justify-content: flex-end;
      transform: translateY(120%);
      transition: transform 260ms cubic-bezier(0.22,0.61,0.36,1);
    }
    .savebar.on { transform: none; }
    .savebar .status { margin-right: auto; font-size: 13px; color: var(--dac-ink-2); }
    .savebar button {
      padding: 11px 20px;
      border-radius: var(--dac-radius-pill);
      border: 1px solid var(--dac-border-hi);
      background: var(--dac-surface);
      color: var(--dac-ink-2);
      font: inherit; font-size: 14px; font-weight: 500;
      cursor: pointer;
      min-height: 44px;
    }
    .savebar button.primary {
      border-color: transparent;
      background: var(--dac-accent);
      color: #fff;
      font-weight: 600;
    }
    .savebar button.primary:disabled { opacity: 0.55; cursor: default; }

    .notice {
      margin-top: 14px;
      padding: 12px 14px;
      border-radius: var(--dac-radius-sm);
      border: 1px solid rgba(250,178,25,0.35);
      background: rgba(250,178,25,0.10);
      font-size: 13px;
      line-height: 1.5;
      color: var(--dac-ink);
      display: flex; gap: 10px; align-items: flex-start;
    }
    .notice .icon { width: 16px; height: 16px; flex: 0 0 auto; color: var(--dac-warn); margin-top: 1px; }
    .notice[hidden] { display: none; }

    @media (max-width: 640px) {
      .wrap { padding: 16px 12px 150px; }
      section.card { padding: 16px 14px 18px; }
      .savebar { padding: 12px 12px calc(12px + env(safe-area-inset-bottom)); }
    }

    @media (max-width: 560px) {
      /* At phone width the status line and two labels fight for one row and
         all three wrap. The buttons are what has to stay readable. */
      .savebar .status { display: none; }
      .savebar button { flex: 1 1 0; white-space: nowrap; text-align: center; }
    }
  `;

  constructor() {
    super();
    this.draft_ = null;
    this.saved_ = null;
  }

  set hass(value) {
    this.hass_ = value;
    if (this.rendered_) this.fillDatalists_();
  }

  set settings(value) {
    if (!value) return;
    this.saved_ = clone(value);
    // A save that came from another device should not overwrite what is being
    // typed here; only adopt it when there is nothing unsaved.
    if (!this.dirty_()) {
      this.draft_ = clone(value);
      if (this.rendered_) this.paint_();
    }
  }

  dirty_() {
    return this.draft_ && JSON.stringify(this.draft_) !== JSON.stringify(this.saved_);
  }

  // --- entity lists ------------------------------------------------------

  /** Entity ids whose unit marks them as power, plus anything already chosen. */
  powerEntities_() {
    const states = this.hass_?.states ?? {};
    return Object.keys(states).filter((id) => {
      const attrs = states[id].attributes ?? {};
      const unit = String(attrs.unit_of_measurement ?? "").toLowerCase();
      return POWER_UNITS.has(unit) || attrs.device_class === "power";
    });
  }

  /** Entity ids that look like a tariff. */
  priceEntities_() {
    const states = this.hass_?.states ?? {};
    return Object.keys(states).filter((id) => {
      const attrs = states[id].attributes ?? {};
      const unit = String(attrs.unit_of_measurement ?? "").toLowerCase();
      return attrs.device_class === "monetary" || unit.includes("/kwh");
    });
  }

  friendly_(id) {
    return this.hass_?.states?.[id]?.attributes?.friendly_name ?? id;
  }

  fillDatalists_() {
    const fill = (node, ids) => {
      if (!node) return;
      node.innerHTML = ids
        .sort()
        .map((id) => `<option value="${id}">${this.friendly_(id)}</option>`)
        .join("");
    };
    fill(this.$("#list-power"), this.powerEntities_());
    fill(this.$("#list-price"), this.priceEntities_());
  }

  // --- rendering ---------------------------------------------------------

  render() {
    return `
      <div class="wrap">
        <header class="intro">
          <div class="eyebrow">Instellingen</div>
          <h1>Zo weet de coach wat je huis doet</h1>
          <p>Alles wat hier staat, bepaalt waar de cijfers op het overzicht vandaan komen. Je hoeft niet alles in te vullen — zonder gekoppelde sensoren blijft het dashboard voorbeeldwaarden tonen.</p>
        </header>

        <div class="notice" id="admin-notice" hidden>
          ${icons.warning}
          <span>Je bent geen beheerder in Home Assistant, dus je kunt deze instellingen wel bekijken maar niet opslaan.</span>
        </div>

        <section class="card">
          <h2>${icons.home} Navigatie</h2>
          <p class="hint">De Home-knop rechtsboven brengt je terug naar je eigen dashboard. Draai je Kiosk Mode, dan is dat de enige weg terug.</p>
          <div class="fields">
            <div class="row">
              <label for="home-path">Pad van je thuisdashboard</label>
              <input type="text" id="home-path" inputmode="url" placeholder="/lovelace/0" autocomplete="off">
              <span class="sub">Bijvoorbeeld <code>/lovelace/0</code> of <code>/dashboard-woning/overzicht</code>.</span>
            </div>
          </div>
        </section>

        <section class="card">
          <h2>${icons.grid} Energiebronnen</h2>
          <p class="hint">Welke sensoren meten je opwek, je verbruik en je meterstand. Of de sensor in watt of kilowatt meet maakt niet uit — dat rekent de coach zelf om.</p>
          <div class="fields">
            <div class="row">
              <label for="src-solar">Opwek zonnepanelen</label>
              <input type="text" id="src-solar" list="list-power" placeholder="sensor.…" autocomplete="off" spellcheck="false">
            </div>
            <div class="row">
              <label for="src-house">Verbruik woning</label>
              <input type="text" id="src-house" list="list-power" placeholder="sensor.… (optioneel)" autocomplete="off" spellcheck="false">
              <span class="sub">Laat je dit leeg, dan rekent de coach het verbruik uit je opwek en je meterstand.</span>
            </div>

            <div class="row">
              <label>Hoe meet je slimme meter?</label>
              <div class="segmented" id="grid-mode">
                <button type="button" data-mode="split" aria-pressed="false">
                  <strong>Afzonderlijk</strong>
                  Twee sensoren: verbruik en productie. Eén van de twee staat altijd op nul.
                </button>
                <button type="button" data-mode="signed" aria-pressed="false">
                  <strong>Gecombineerd</strong>
                  Eén sensor die negatief wordt zodra je teruglevert.
                </button>
              </div>
            </div>

            <div id="grid-split" class="two">
              <div class="row">
                <label for="src-import">Energieverbruik (van het net)</label>
                <input type="text" id="src-import" list="list-power" placeholder="sensor.…" autocomplete="off" spellcheck="false">
              </div>
              <div class="row">
                <label for="src-export">Energieproductie (naar het net)</label>
                <input type="text" id="src-export" list="list-power" placeholder="sensor.…" autocomplete="off" spellcheck="false">
              </div>
            </div>

            <div class="row" id="grid-signed">
              <label for="src-signed">Netvermogen</label>
              <input type="text" id="src-signed" list="list-power" placeholder="sensor.…" autocomplete="off" spellcheck="false">
              <span class="sub">Normaal is positief inkoop en negatief teruglevering.</span>
              <label class="check" for="src-invert">
                <input type="checkbox" id="src-invert">
                <span>
                  <strong>Meting omgekeerd</strong>
                  Aanvinken als je meter het andersom doet: positief bij teruglevering.
                  Herken je aan een diagram dat precies verkeerd om staat.
                </span>
              </label>
            </div>

            <div class="row">
              <label for="src-price">Energieprijs</label>
              <input type="text" id="src-price" list="list-price" placeholder="sensor.… (optioneel)" autocomplete="off" spellcheck="false">
              <span class="sub">In euro of centen per kWh — de coach leest de eenheid van de sensor.</span>
            </div>
          </div>
        </section>

        <section class="card">
          <h2>${icons.devices} Apparaten</h2>
          <p class="hint">Deze verschijnen als bollen in de energiestroom. Er staan er altijd hoogstens twee in beeld: draaien er meer, dan krijgt de zwaarste zijn eigen bol en worden de rest bij elkaar opgeteld.</p>
          <div class="fields" id="device-list"></div>
          <button class="add" type="button" id="add-device">${icons.plus} Apparaat toevoegen</button>
        </section>

        <section class="card">
          <h2>${icons.gauge} Drempelwaarden</h2>
          <p class="hint">Waar de kleuren omslaan van groen naar oranje naar rood.</p>
          <div class="fields">
            <div class="row">
              <label>Zelfbenutting (%)</label>
              <div class="two">
                <div class="row">
                  <span class="sub">Onder deze waarde rood</span>
                  <input type="number" id="self-low" min="0" max="100" step="1" inputmode="numeric">
                </div>
                <div class="row">
                  <span class="sub">Vanaf deze waarde groen</span>
                  <input type="number" id="self-high" min="0" max="100" step="1" inputmode="numeric">
                </div>
              </div>
            </div>
            <div class="row">
              <label>Energieprijs (€ per kWh)</label>
              <div class="two">
                <div class="row">
                  <span class="sub">Tot deze prijs groen</span>
                  <input type="number" id="price-low" min="0" max="10" step="0.01" inputmode="decimal">
                </div>
                <div class="row">
                  <span class="sub">Boven deze prijs rood</span>
                  <input type="number" id="price-high" min="0" max="10" step="0.01" inputmode="decimal">
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <datalist id="list-power"></datalist>
      <datalist id="list-price"></datalist>

      <div class="savebar" id="savebar">
        <span class="status" id="save-status"></span>
        <button type="button" id="revert">Ongedaan maken</button>
        <button type="button" class="primary" id="save">Opslaan</button>
      </div>
    `;
  }

  afterRender() {
    this.fillDatalists_();

    const bind = (id, apply) => {
      const el = this.$(`#${id}`);
      el.addEventListener("input", () => {
        apply(el.value);
        this.syncSaveBar_();
      });
    };

    bind("home-path", (v) => (this.draft_.navigation.home_path = v));
    bind("src-solar", (v) => (this.draft_.sources.solar = v.trim()));
    bind("src-house", (v) => (this.draft_.sources.house = v.trim()));
    bind("src-import", (v) => (this.draft_.sources.grid_import = v.trim()));
    bind("src-export", (v) => (this.draft_.sources.grid_export = v.trim()));
    bind("src-signed", (v) => (this.draft_.sources.grid_signed = v.trim()));
    bind("src-price", (v) => (this.draft_.sources.price = v.trim()));
    bind("self-low", (v) => (this.draft_.thresholds.self_use.low = Number(v)));
    bind("self-high", (v) => (this.draft_.thresholds.self_use.high = Number(v)));
    bind("price-low", (v) => (this.draft_.thresholds.price.low = Number(v)));
    bind("price-high", (v) => (this.draft_.thresholds.price.high = Number(v)));

    const invert = this.$("#src-invert");
    invert.addEventListener("change", () => {
      this.draft_.sources.grid_signed_invert = invert.checked;
      this.syncSaveBar_();
    });

    for (const button of this.$$("#grid-mode button")) {
      button.addEventListener("click", () => {
        this.draft_.sources.grid_mode = button.dataset.mode;
        this.paintGridMode_();
        this.syncSaveBar_();
      });
    }

    this.$("#add-device").addEventListener("click", () => {
      this.draft_.devices.push({ id: uid(), type: "laadpaal", name: "", entity: "" });
      this.paintDevices_();
      this.syncSaveBar_();
    });

    this.$("#save").addEventListener("click", () => this.save_());
    this.$("#revert").addEventListener("click", () => {
      this.draft_ = clone(this.saved_);
      this.paint_();
      this.syncSaveBar_();
    });

    this.paint_();
  }

  // --- painting ----------------------------------------------------------

  paint_() {
    if (!this.draft_ || !this.rendered_) return;
    const d = this.draft_;

    this.$("#admin-notice").hidden = this.hass_?.user?.is_admin !== false;

    this.$("#home-path").value = d.navigation.home_path ?? "";
    this.$("#src-solar").value = d.sources.solar ?? "";
    this.$("#src-house").value = d.sources.house ?? "";
    this.$("#src-import").value = d.sources.grid_import ?? "";
    this.$("#src-export").value = d.sources.grid_export ?? "";
    this.$("#src-signed").value = d.sources.grid_signed ?? "";
    this.$("#src-invert").checked = Boolean(d.sources.grid_signed_invert);
    this.$("#src-price").value = d.sources.price ?? "";
    this.$("#self-low").value = d.thresholds.self_use.low;
    this.$("#self-high").value = d.thresholds.self_use.high;
    this.$("#price-low").value = d.thresholds.price.low;
    this.$("#price-high").value = d.thresholds.price.high;

    this.paintGridMode_();
    this.paintDevices_();
    this.syncSaveBar_();
  }

  paintGridMode_() {
    const mode = this.draft_.sources.grid_mode ?? "split";
    for (const button of this.$$("#grid-mode button")) {
      button.setAttribute("aria-pressed", String(button.dataset.mode === mode));
    }
    this.$("#grid-split").style.display = mode === "split" ? "" : "none";
    this.$("#grid-signed").style.display = mode === "signed" ? "" : "none";
  }

  paintDevices_() {
    const list = this.$("#device-list");
    const devices = this.draft_.devices ?? [];

    if (!devices.length) {
      list.innerHTML = `<p class="empty">Nog geen apparaten. Voeg er een toe om het in de energiestroom te zien.</p>`;
      return;
    }

    list.innerHTML = devices
      .map(
        (device, index) => `
        <div class="device" data-index="${index}">
          <div class="device-head">
            <span class="chip">${icons[typeMeta(device.type).icon]}</span>
            <span class="name">${typeMeta(device.type).label}</span>
            <button class="remove" type="button" data-remove="${index}" aria-label="Verwijderen">${icons.trash}</button>
          </div>
          <div class="two">
            <div class="row">
              <label>Type</label>
              <select data-field="type" data-index="${index}">
                ${DEVICE_TYPES.map(
                  (t) => `<option value="${t.id}"${t.id === device.type ? " selected" : ""}>${t.label}</option>`
                ).join("")}
              </select>
            </div>
            <div class="row">
              <label>Eigen naam</label>
              <input type="text" data-field="name" data-index="${index}"
                     value="${(device.name ?? "").replace(/"/g, "&quot;")}"
                     placeholder="${device.type === "overig" ? "Bijvoorbeeld: serverkast" : "optioneel"}"
                     autocomplete="off">
            </div>
          </div>
          <div class="row">
            <label>Vermogenssensor</label>
            <input type="text" data-field="entity" data-index="${index}" list="list-power"
                   value="${device.entity ?? ""}" placeholder="sensor.…" autocomplete="off" spellcheck="false">
          </div>
        </div>`
      )
      .join("");

    for (const el of list.querySelectorAll("[data-field]")) {
      const index = Number(el.dataset.index);
      const field = el.dataset.field;
      const handler = () => {
        this.draft_.devices[index][field] = field === "entity" ? el.value.trim() : el.value;
        // Changing the type changes the icon and the heading, so redraw -- but
        // only for the type, or every keystroke in a name would lose focus.
        if (field === "type") this.paintDevices_();
        this.syncSaveBar_();
      };
      el.addEventListener(el.tagName === "SELECT" ? "change" : "input", handler);
    }

    for (const button of list.querySelectorAll("[data-remove]")) {
      button.addEventListener("click", () => {
        this.draft_.devices.splice(Number(button.dataset.remove), 1);
        this.paintDevices_();
        this.syncSaveBar_();
      });
    }
  }

  syncSaveBar_() {
    const dirty = this.dirty_();
    const canSave = this.hass_?.user?.is_admin !== false;
    this.$("#savebar").classList.toggle("on", dirty);
    this.$("#save").disabled = !canSave;
    this.$("#save-status").textContent = dirty ? "Niet-opgeslagen wijzigingen" : "";
  }

  // --- saving ------------------------------------------------------------

  async save_() {
    const status = this.$("#save-status");
    const button = this.$("#save");
    button.disabled = true;
    status.textContent = "Opslaan…";

    try {
      const saved = await this.hass_.callWS({
        type: "domotiapp_coach/settings/set",
        settings: this.draft_,
      });
      this.saved_ = clone(saved);
      this.draft_ = clone(saved);
      this.fire("dac-settings-saved", { settings: saved });
      status.textContent = "Opgeslagen";
      setTimeout(() => this.syncSaveBar_(), 1600);
    } catch (error) {
      status.textContent = `Opslaan mislukt: ${error?.message ?? error}`;
    } finally {
      button.disabled = false;
      this.$("#savebar").classList.toggle("on", this.dirty_());
    }
  }
}

define("dac-view-settings", DacViewSettings);
