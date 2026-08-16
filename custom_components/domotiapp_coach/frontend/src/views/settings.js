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
          <p>Alles wat hier staat, bepaalt waar de cijfers op het overzicht vandaan komen. Je hoeft niet alles in te vullen. Zonder gekoppelde sensoren blijven de cijfers leeg.</p>
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
          <p class="hint">Welke sensoren meten je opwek en je meterstand. Of de sensor in watt of kilowatt meet maakt niet uit, dat rekent de coach zelf om. Het verbruik van de woning wordt hieruit berekend.</p>
          <div class="fields">
            <div class="row">
              <label>Opwek zonnepanelen</label>
              <dac-entity-picker id="src-solar" data-key="solar"></dac-entity-picker>
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

          </div>
        </section>

        <section class="card">
          <h2>${icons.sun} Zonverwachting</h2>
          <p class="hint">Wat er vandaag en morgen aan zon verwacht wordt. Daarmee kan de coach besluiten of het de moeite is om te wachten, of dat hij beter vannacht op de goedkope uren kan draaien. Integraties als Forecast.Solar en Solcast leveren deze waarden als sensoren; vul in wat je hebt.</p>
          <div class="fields">
            <div class="two">
              <div class="row">
                <label>Verwacht vandaag nog</label>
                <dac-entity-picker data-forecast="remaining_today"></dac-entity-picker>
              </div>
              <div class="row">
                <label>Verwacht morgen</label>
                <dac-entity-picker data-forecast="tomorrow"></dac-entity-picker>
              </div>
            </div>
            <div class="row">
              <label>Tijdstip hoogste opwek vandaag</label>
              <dac-entity-picker data-forecast="peak_today"></dac-entity-picker>
              <span class="sub">Optioneel. Hiermee kan de coach zeggen rond welk uur het overschot het grootst is.</span>
            </div>
          </div>
        </section>

        <section class="card">
          <h2>${icons.plug} Fasen</h2>
          <p class="hint">Heeft de meter van deze klant losse waarden per fase, vul ze dan hier in. Daarmee wordt de belastbaarheid per fase berekend in plaats van op het totaal. Een zekering gaat er immers uit op de zwaarste fase en niet op het gemiddelde.</p>
          <div class="fields">
            <label class="check" for="phases-enabled">
              <input type="checkbox" id="phases-enabled">
              <span>
                <strong>Fasen beschikbaar</strong>
                Aanzetten als deze woning per fase meet.
              </span>
            </label>

            <div id="phase-fields" class="fields">
              ${["l1", "l2", "l3"]
                .map(
                  (phase) => `
                <div class="phase-block">
                  <div class="phase-title">${phase.toUpperCase()}</div>
                  <div class="row">
                    <label>Stroom (A)</label>
                    <dac-entity-picker data-phase="${phase}" data-kind="current"></dac-entity-picker>
                  </div>
                  <div class="row">
                    <label>Vermogen</label>
                    <dac-entity-picker data-phase="${phase}" data-kind="power"></dac-entity-picker>
                  </div>
                  <div class="row">
                    <label>Spanning (V)</label>
                    <dac-entity-picker data-phase="${phase}" data-kind="voltage"></dac-entity-picker>
                  </div>
                </div>`
                )
                .join("")}

              <label class="check" for="phases-overview">
                <input type="checkbox" id="phases-overview">
                <span>
                  <strong>Tonen op het overzicht</strong>
                  Zet er een kaart bij met de belasting per fase.
                </span>
              </label>
            </div>
          </div>
        </section>

        <section class="card">
          <h2>${icons.gauge} Meterstanden</h2>
          <p class="hint">De tellers van je slimme meter, zoals ze op de meter zelf staan. Vul in wat je hebt; alleen de ingevulde standen komen op het overzicht te staan. Dit zijn totalen in kWh en m³, dus geen vermogens.</p>
          <div class="fields">
            <div class="two">
              <div class="row">
                <label>Geleverd, laag tarief</label>
                <dac-entity-picker data-meter="import_low"></dac-entity-picker>
              </div>
              <div class="row">
                <label>Geleverd, hoog tarief</label>
                <dac-entity-picker data-meter="import_high"></dac-entity-picker>
              </div>
              <div class="row">
                <label>Teruggeleverd, laag tarief</label>
                <dac-entity-picker data-meter="export_low"></dac-entity-picker>
              </div>
              <div class="row">
                <label>Teruggeleverd, hoog tarief</label>
                <dac-entity-picker data-meter="export_high"></dac-entity-picker>
              </div>
            </div>

            <label class="check" for="gas-enabled">
              <input type="checkbox" id="gas-enabled">
              <span>
                <strong>Deze woning gebruikt gas</strong>
                Staat dit uit, dan blijft gas van het overzicht weg.
              </span>
            </label>

            <div class="row" id="gas-field">
              <label>Gasmeter (m³)</label>
              <dac-entity-picker data-meter="gas"></dac-entity-picker>
            </div>
          </div>
        </section>

        <section class="card">
          <h2>${icons.sliders} Drempelwaarden</h2>
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

    for (const picker of this.$$("dac-entity-picker[data-key]")) {
      picker.filter = "power";
      picker.placeholder = "Zoek een vermogenssensor…";
      picker.addEventListener("dac-entity-change", (ev) => {
        this.draft_.sources[picker.dataset.key] = ev.detail.value;
        this.syncSaveBar_();
      });
    }

    for (const picker of this.$$("dac-entity-picker[data-phase]")) {
      const { phase, kind } = picker.dataset;
      picker.filter = kind === "power" ? "power" : "all";
      picker.placeholder =
        kind === "current" ? "Zoek een stroomsensor…"
        : kind === "voltage" ? "Zoek een spanningssensor…"
        : "Zoek een vermogenssensor…";
      picker.addEventListener("dac-entity-change", (ev) => {
        this.draft_.sources.phases[phase][kind] = ev.detail.value;
        this.syncSaveBar_();
      });
    }

    // Meter readings are counters in kWh or m3, so the picker looks for energy
    // rather than power: a customer searching "verbruik" otherwise gets the
    // watts they already mapped above.
    for (const picker of this.$$("dac-entity-picker[data-forecast]")) {
      picker.filter = "all";
      picker.placeholder =
        picker.dataset.forecast === "peak_today" ? "Zoek een tijdstip…" : "Zoek een verwachting in kWh…";
      picker.addEventListener("dac-entity-change", (ev) => {
        (this.draft_.sources.solar_forecast ??= {})[picker.dataset.forecast] = ev.detail.value;
        this.syncSaveBar_();
      });
    }

    for (const picker of this.$$("dac-entity-picker[data-meter]")) {
      picker.filter = "all";
      picker.placeholder =
        picker.dataset.meter === "gas" ? "Zoek je gasmeter…" : "Zoek een meterstand…";
      picker.addEventListener("dac-entity-change", (ev) => {
        // Created on demand: settings written before this section existed have
        // no `meters` at all until the server merges its defaults in.
        (this.draft_.sources.meters ??= {})[picker.dataset.meter] = ev.detail.value;
        this.syncSaveBar_();
      });
    }

    for (const [id, apply] of [
      ["phases-enabled", (on) => (this.draft_.sources.phases_enabled = on)],
      ["phases-overview", (on) => (this.draft_.sources.phases_on_overview = on)],
      ["gas-enabled", (on) => ((this.draft_.sources.meters ??= {}).gas_enabled = on)],
    ]) {
      const box = this.$(`#${id}`);
      box.addEventListener("change", () => {
        apply(box.checked);
        this.paintPhases_();
        this.paintGas_();
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
    this.paint_();
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

    for (const picker of this.$$("dac-entity-picker[data-key]")) {
      picker.value = d.sources[picker.dataset.key] ?? "";
    }
    for (const picker of this.$$("dac-entity-picker[data-phase]")) {
      const { phase, kind } = picker.dataset;
      picker.value = d.sources.phases?.[phase]?.[kind] ?? "";
    }
    this.$("#phases-enabled").checked = Boolean(d.sources.phases_enabled);
    this.$("#phases-overview").checked = Boolean(d.sources.phases_on_overview);

    for (const picker of this.$$("dac-entity-picker[data-forecast]")) {
      picker.filter = "all";
      picker.placeholder =
        picker.dataset.forecast === "peak_today" ? "Zoek een tijdstip…" : "Zoek een verwachting in kWh…";
      picker.addEventListener("dac-entity-change", (ev) => {
        (this.draft_.sources.solar_forecast ??= {})[picker.dataset.forecast] = ev.detail.value;
        this.syncSaveBar_();
      });
    }

    for (const picker of this.$$("dac-entity-picker[data-forecast]")) {
      picker.value = d.sources.solar_forecast?.[picker.dataset.forecast] ?? "";
    }
    for (const picker of this.$$("dac-entity-picker[data-meter]")) {
      picker.value = d.sources.meters?.[picker.dataset.meter] ?? "";
    }
    this.$("#gas-enabled").checked = Boolean(d.sources.meters?.gas_enabled);
    this.onFeed_();

    this.paintGridMode_();
    this.paintPhases_();
    this.paintGas_();
    this.syncSaveBar_();
  }

  paintPhases_() {
    this.$("#phase-fields").style.display = this.draft_.sources.phases_enabled ? "" : "none";
  }

  paintGas_() {
    this.$("#gas-field").style.display = this.draft_.sources.meters?.gas_enabled ? "" : "none";
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

  /* ---- phases ---- */
  .phase-block {
    padding: 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(255,255,255,0.022);
    display: grid;
    gap: 12px;
  }
  .phase-title {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.12em;
    color: var(--dac-accent-hi);
  }
`;

define("dac-view-settings", DacViewSettings);
