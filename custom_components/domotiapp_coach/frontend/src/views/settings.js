/**
 * Instellingen -- how the dashboard reads this house, and where it draws its
 * lines.
 *
 * It lives in the panel rather than in a Home Assistant options flow because
 * customers reach this on a phone behind Kiosk Mode, where HA's own settings
 * screens are not available to them. Settings are grouped the way they are used:
 * one heading per subject, and every control for that subject under it.
 *
 * Devices are deliberately *not* here -- they have their own section in the
 * header, and having them in two places invites editing the wrong copy.
 */

import { define } from "../base.js";
import { icons } from "../icons.js";
import {
  DacEditorElement,
  adminNoticeHtml,
  editorCss,
  saveBarHtml,
} from "./editor-base.js";
import "../components/entity-picker.js";

class DacViewSettings extends DacEditorElement {
  static sections = ["navigation", "sources", "thresholds"];

  render() {
    return `
      <div class="wrap">
        <header class="intro">
          <div class="eyebrow">Instellingen</div>
          <h1>Zo weet de coach wat je huis doet</h1>
          <p>Alles wat hier staat, bepaalt waar de cijfers op het overzicht vandaan komen. Je hoeft niet alles in te vullen — zonder gekoppelde sensoren blijft het dashboard voorbeeldwaarden tonen.</p>
        </header>

        ${adminNoticeHtml}

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
              <label>Opwek zonnepanelen</label>
              <dac-entity-picker id="src-solar" data-key="solar"></dac-entity-picker>
            </div>
            <div class="row">
              <label>Verbruik woning</label>
              <dac-entity-picker id="src-house" data-key="house"></dac-entity-picker>
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
                <label>Energieverbruik (van het net)</label>
                <dac-entity-picker id="src-import" data-key="grid_import"></dac-entity-picker>
              </div>
              <div class="row">
                <label>Energieproductie (naar het net)</label>
                <dac-entity-picker id="src-export" data-key="grid_export"></dac-entity-picker>
              </div>
            </div>

            <div class="row" id="grid-signed">
              <label>Netvermogen</label>
              <dac-entity-picker id="src-signed" data-key="grid_signed"></dac-entity-picker>
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
              <label>Energieprijs</label>
              <dac-entity-picker id="src-price" data-key="price"></dac-entity-picker>
              <span class="sub">In euro of centen per kWh — de coach leest de eenheid van de sensor.</span>
            </div>
          </div>
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

      ${saveBarHtml}
    `;
  }

  afterRender() {
    const bind = (id, apply) => {
      const el = this.$(`#${id}`);
      el.addEventListener("input", () => {
        apply(el.value);
        this.syncSaveBar_();
      });
    };

    bind("home-path", (v) => (this.draft_.navigation.home_path = v));
    bind("self-low", (v) => (this.draft_.thresholds.self_use.low = Number(v)));
    bind("self-high", (v) => (this.draft_.thresholds.self_use.high = Number(v)));
    bind("price-low", (v) => (this.draft_.thresholds.price.low = Number(v)));
    bind("price-high", (v) => (this.draft_.thresholds.price.high = Number(v)));

    for (const picker of this.pickers_()) {
      picker.filter = picker.dataset.key === "price" ? "price" : "power";
      picker.placeholder =
        picker.dataset.key === "price" ? "Zoek een prijssensor…" : "Zoek een vermogenssensor…";
      picker.addEventListener("dac-entity-change", (ev) => {
        this.draft_.sources[picker.dataset.key] = ev.detail.value;
        this.syncSaveBar_();
      });
    }

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

    this.wireSaveBar_();
    this.onHass_();
    this.paint_();
  }

  pickers_() {
    return this.$$("dac-entity-picker");
  }

  onHass_() {
    for (const picker of this.pickers_()) picker.hass = this.hass_;
  }

  paint_() {
    if (!this.draft_ || !this.rendered_) return;
    const d = this.draft_;

    this.$("#home-path").value = d.navigation.home_path ?? "";
    this.$("#src-invert").checked = Boolean(d.sources.grid_signed_invert);
    this.$("#self-low").value = d.thresholds.self_use.low;
    this.$("#self-high").value = d.thresholds.self_use.high;
    this.$("#price-low").value = d.thresholds.price.low;
    this.$("#price-high").value = d.thresholds.price.high;

    for (const picker of this.pickers_()) {
      picker.hass = this.hass_;
      picker.value = d.sources[picker.dataset.key] ?? "";
    }

    this.paintGridMode_();
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
}

DacViewSettings.css = /* css */ `
  ${editorCss}

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
`;

define("dac-view-settings", DacViewSettings);
