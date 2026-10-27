/**
 * Installatie -- hoe dit huis gemeten wordt en wat het aankan: de aansluiting,
 * de kasten en groepen, de sensoren van de meter en de zon, de meterstanden.
 *
 * Sinds v0.114.0 alleen voor de installateur, en met Instellingen erin. De
 * eigenaar op 08-10-2026: "voorop staat dat de klant geen entiteiten moet kunnen
 * kiezen", en "het moet beter gecategoriseerd worden". Wat het kost staat onder
 * Contract, hoe het overzicht eruitziet onder Voorkeuren.
 */

import { define } from "../base.js";
import { locale, t } from "../i18n.js";
import { icons } from "../icons.js";
import {
  DacEditorElement,
  adminNoticeHtml,
  editorCss,
  saveBarHtml,
} from "./editor-base.js";
import "../components/entity-picker.js";

/** Nominal voltage per phase: 3 x 25 A -> 17250 W, 1 x 25 A -> 5750 W. */
const VOLTAGE = 230;

/**
 * Elke kast en groep krijgt zijn soort en of hij een eigen kWh-meter heeft (v0.101.5).
 *
 * Van voor v0.101.5 staat er geen soort bij. Een kast is dan wat onder de
 * hoofdkast hangt en zelf groepen draagt of een meter heeft: bij de eigenaar de
 * lounge met de laadpaal en de batterij eronder, in de eerste woning de garage
 * met zijn meter. Een meter heeft wie sensoren heeft.
 */
export function kastenIndelen(circuits) {
  if (!Array.isArray(circuits)) return circuits;
  for (const g of circuits) {
    if (!g || typeof g !== "object") continue;
    const heeftSensor = Object.values(g.sensors ?? {}).some((fase) => Object.values(fase ?? {}).some(Boolean));
    if (typeof g.meter !== "boolean") g.meter = heeftSensor;
    if (g.kind !== "kast" && g.kind !== "groep") {
      const draagt = circuits.some((o) => o !== g && o?.parent === g.id);
      g.kind = !g.parent && (draagt || heeftSensor) ? "kast" : "groep";
    }
  }
  return circuits;
}

class DacViewInstallation extends DacEditorElement {
  static sections = ["installation", "navigation", "sources"];

  render() {
    return `
      <div class="wrap">
        <header class="intro">
          <div class="eyebrow">${t("Installatie")}</div>
          <h1>${t("Hoe je huis gemeten wordt")}</h1>
          <p>${t("Je aansluiting, je kasten en groepen, en welke sensoren meten wat er gebeurt. Hierop rekent de coach. Je hoeft niet alles in te vullen; zonder gekoppelde sensoren blijven de cijfers leeg.")}</p>
        </header>

        ${adminNoticeHtml}

        <section class="card">
          <h2>${icons.house} ${t("Woning")}</h2>
          <p class="hint">${t("De naam van de woning komt ook boven het overzicht te staan.")}</p>
          <div class="fields">
            <div class="row">
              <label for="home-name">${t("Naam van de woning")}</label>
              <input type="text" id="home-name" placeholder="${t("Bijvoorbeeld: Dorpsstraat 12")}" autocomplete="off">
            </div>

            <!-- De taal (v0.139.0). De eigenaar op 19-10-2026: "ik wil ook dat het hele coach in
                 het engels ingesteld kan worden", een taal voor de hele installatie. -->
            <div class="row">
              <label for="taal">Taal / Language</label>
              <select id="taal">
                <option value="auto">Automatisch / Automatic</option>
                <option value="nl">Nederlands</option>
                <option value="en">English</option>
              </select>
              <span class="sub">Automatisch volgt de taal van Home Assistant. / Automatic follows the language of Home Assistant.</span>
            </div>

            <!-- Terugverdiend (v0.148.0): de installateur ziet het altijd op de kaart van de
                 thuisbatterij, de bewoner alleen als dit aan staat. -->
            <label class="check" for="terug-bewoner">
              <input type="checkbox" id="terug-bewoner">
              <span>
                <strong>${t("Terugverdiend ook aan de bewoner tonen")}</strong>
                ${t("Op de kaart van de thuisbatterij: hoeveel van de aanschafprijs er al terug is, uit wat ze opleverde sinds de coach haar volgt. Zonder datum. De aanschafprijs vul je in bij de batterij, onder Afschrijving.")}
              </span>
            </label>
          </div>
        </section>

        <section class="card">
          <h2>${icons.plug} ${t("Aansluiting")}</h2>
          <div class="fields">
            <div class="block">
            <div class="block-title">${t("Zekering")}</div>
            <div class="row">
              <label>${t("Aantal fasen")}</label>
              <div class="segmented" id="phases">
                <button type="button" data-phases="1" aria-pressed="false">
                  <strong>${t("1 fase")}</strong>
                  ${t("Eén fase van 230 V.")}
                </button>
                <button type="button" data-phases="3" aria-pressed="false">
                  <strong>${t("3 fasen")}</strong>
                  ${t("Drie fasen van 230 V.")}
                </button>
              </div>
            </div>

            <div class="two">
              <div class="row">
                <label for="fuse">${t("Hoofdzekering per fase (A)")}</label>
                <input type="number" id="fuse" min="1" max="1000" step="1" inputmode="numeric">
              </div>
              <div class="row">
                <label for="max-grid">${t("Maximaal netvermogen (W)")}</label>
                <input type="number" id="max-grid" min="0" step="50" inputmode="numeric">
                <span class="sub" id="max-grid-hint"></span>
              </div>
            </div>

            <label class="check" for="max-auto">
              <input type="checkbox" id="max-auto">
              <span>
                <strong>${t("Automatisch berekenen")}</strong>
                ${t("Uit fasen × zekering × 230 V. Zet dit uit als je aansluiting begrensd of juist verzwaard is.")}
              </span>
            </label>

            </div>
            <div class="block">
            <div class="block-title">${t("Lastbewaker")}</div>
            <label class="check" for="balancer">
              <input type="checkbox" id="balancer">
              <span>
                <strong>${t("Er zit een lastbewaker op de aansluiting")}</strong>
                ${t("Zoals een Easee Equalizer. Die bewaakt dezelfde zekering en kan het laden zelf terugschroeven. Staat dit aan, dan houdt de coach een ruimere marge aan en stapt hij als eerste terug, zodat de lastbewaker een vangnet blijft dat niet hoeft in te grijpen. Meet je lastbewaker de fasen, kies die sensoren dan hieronder bij de stroom per fase; dat is de zuiverste meting die je hebt.")}
              </span>
            </label>

            <div class="row" id="balancer-row">
              <label>${t("Sensor: wat je lastbewaker vrijgeeft")}</label>
              <dac-entity-picker id="balancer-limit"></dac-entity-picker>
              <span class="sub">
                ${t("Optioneel, en alleen als je bewaker meldt hoeveel hij op dit moment vrijgeeft voor het laden. Bij een Easee Equalizer heet die sensor \"Equalizer limiet\". Dat getal beweegt mee met wat de rest van je huis gebruikt: het is wat er overblijft, niet je hoofdzekering. Vul je hem in, dan vraagt de coach er nooit meer overheen en hoeft je bewaker niet in te grijpen.")}
              </span>
            </div>
            </div>
          </div>
        </section>

        <!-- Onderverdeelkasten en groepen (v0.101.5). De eigenaar op 29-09-2026:
             "Dat moet heten onderverdeelkast. Bij mij thuis heb ik een hoofdkast
             3x25A en dan een onderverdeelkast in de lounge", en de sensoren per
             fase pas als de kast of groep een eigen kWh-meter heeft. -->
        <section class="card">
          <h2>${icons.plug} ${t("Onderverdeelkasten")}</h2>
          <p class="hint">
            ${t("Heb je naast je hoofdkast een onderverdeelkast, bijvoorbeeld in de garage, met een eigen zekering? Zet hem hier neer. De coach blijft dan onder de zekering van die kast én onder die van je hoofdkast. Heeft de kast een eigen kWh-meter, dan weet de coach ook wat er de rest van de kast gebruikt wordt; zonder meter telt hij alleen wat hij er zelf naartoe stuurt.")}
          </p>
          <div class="fields">
            <div id="kasten"></div>
            <div class="circuit-actions">
              <button type="button" id="kast-add">${t("Onderverdeelkast toevoegen")}</button>
            </div>
          </div>
        </section>

        <section class="card">
          <h2>${icons.plug} ${t("Groepen")}</h2>
          <p class="hint">
            ${t("Een groep met een eigen zekering, in je hoofdkast of in een onderverdeelkast, bijvoorbeeld een laadpaal op een eigen B20. Kies bij Apparaten welke apparaten eraan hangen. Een groep zonder eigen kWh-meter telt alleen wat de coach er zelf naartoe stuurt.")}
          </p>
          <div class="fields">
            <div id="circuits"></div>
            <div class="circuit-actions">
              <button type="button" id="circuit-add">${t("Groep toevoegen")}</button>
            </div>
          </div>
        </section>

        <section class="card">
          <h2>${icons.grid} ${t("Energiebronnen")}</h2>
          <p class="hint">${t("Welke sensoren meten je opwek en je meterstand. Of de sensor in watt of kilowatt meet maakt niet uit, dat rekent de coach zelf om. Het verbruik van de woning wordt hieruit berekend.")}</p>
          <div class="fields">
            <div class="block fields">
            <div class="block-title">${t("Zonnepanelen")}</div>
            <div class="row">
              <label>${t("Opwek zonnepanelen")}</label>
              <dac-entity-picker id="src-solar" data-key="solar"></dac-entity-picker>
            </div>
            <div id="solar-extra"></div>
            <div class="row">
              <button type="button" class="add" id="solar-extra-add">${t("Nog een omvormer")}</button>
              <span class="sub">${t("Heb je meer omvormers, zet ze hier erbij; de coach telt ze op.")}</span>
            </div>
            </div>
            <div class="block fields">
            <div class="block-title">${t("Slimme meter")}</div>
            <div class="row">
              <label>${t("Hoe meet je slimme meter?")}</label>
              <div class="segmented" id="grid-mode">
                <button type="button" data-mode="split" aria-pressed="false">
                  <strong>${t("Afzonderlijk")}</strong>
                  ${t("Twee sensoren: verbruik en productie. Eén van de twee staat altijd op nul.")}
                </button>
                <button type="button" data-mode="signed" aria-pressed="false">
                  <strong>${t("Gecombineerd")}</strong>
                  ${t("Eén sensor die negatief wordt zodra je teruglevert.")}
                </button>
              </div>
            </div>

            <div id="grid-split" class="two">
              <div class="row">
                <label>${t("Energieverbruik (van het net)")}</label>
                <dac-entity-picker id="src-import" data-key="grid_import"></dac-entity-picker>
              </div>
              <div class="row">
                <label>${t("Energieproductie (naar het net)")}</label>
                <dac-entity-picker id="src-export" data-key="grid_export"></dac-entity-picker>
              </div>
            </div>

            <div class="row" id="grid-signed">
              <label>${t("Netvermogen")}</label>
              <dac-entity-picker id="src-signed" data-key="grid_signed"></dac-entity-picker>
              <span class="sub">${t("Normaal is positief inkoop en negatief teruglevering.")}</span>
              <label class="check" for="src-invert">
                <input type="checkbox" id="src-invert">
                <span>
                  <strong>${t("Meting omgekeerd")}</strong>
                  ${t("Aanvinken als je meter het andersom doet: positief bij teruglevering. Herken je aan een diagram dat precies verkeerd om staat.")}
                </span>
              </label>
            </div>
            </div>

          </div>
        </section>

        <section class="card">
          <h2>${icons.plug} ${t("Fasen")}</h2>
          <p class="hint">${t("Heeft de meter van deze woning losse waarden per fase, vul ze dan hier in. Daarmee wordt de belastbaarheid per fase berekend in plaats van op het totaal. Een zekering gaat er immers uit op de zwaarste fase en niet op het gemiddelde.")}</p>
          <div class="fields">
            <label class="check" for="phases-enabled">
              <input type="checkbox" id="phases-enabled">
              <span>
                <strong>${t("Fasen beschikbaar")}</strong>
                ${t("Aanzetten als deze woning per fase meet.")}
              </span>
            </label>

            <div id="phase-fields" class="fields">
              ${["l1", "l2", "l3"]
                .map(
                  (phase) => `
                <div class="phase-block">
                  <div class="phase-title">${phase.toUpperCase()}</div>
                  <div class="row">
                    <label>${t("Stroom (A)")}</label>
                    <dac-entity-picker data-phase="${phase}" data-kind="current"></dac-entity-picker>
                  </div>
                  <div class="row">
                    <label>${t("Vermogen")}</label>
                    <dac-entity-picker data-phase="${phase}" data-kind="power"></dac-entity-picker>
                  </div>
                  <div class="row">
                    <label>${t("Spanning (V)")}</label>
                    <dac-entity-picker data-phase="${phase}" data-kind="voltage"></dac-entity-picker>
                  </div>
                </div>`
                )
                .join("")}
            </div>
          </div>
        </section>

        <section class="card">
          <h2>${icons.sun} ${t("Zonverwachting")}</h2>
          <p class="hint">${t("Wat er vandaag en morgen aan zon verwacht wordt. Daarmee kan de coach besluiten of het de moeite is om te wachten, of dat hij beter vannacht op de goedkope uren kan draaien. Integraties als Forecast.Solar en Solcast leveren deze waarden als sensoren; vul in wat je hebt.")}</p>
          <div class="fields">
            <div class="block fields">
              <div class="block-title">${t("Per uur")}</div>
              <div class="two">
                <div class="row">
                  <label>${t("Verwacht dit uur")}</label>
                  <dac-entity-picker data-forecast="this_hour"></dac-entity-picker>
                </div>
                <div class="row">
                  <label>${t("Verwacht volgend uur")}</label>
                  <dac-entity-picker data-forecast="next_hour"></dac-entity-picker>
                </div>
              </div>
              <p class="sub">${t("In kWh over dat uur. Dit zijn de twee die de coach echt gebruikt om te beslissen: moet hij nu stroom bijkopen om op de zon te laden terwijl er volgend uur veel meer aankomt, dan wacht hij dat uur af. Met alleen dagtotalen kan hij dat niet weten.")}</p>
            </div>
            <div class="block fields">
              <div class="block-title">${t("Per dag")}</div>
              <div class="two">
                <div class="row">
                  <label>${t("Verwacht vandaag nog")}</label>
                  <dac-entity-picker data-forecast="remaining_today"></dac-entity-picker>
                </div>
                <div class="row">
                  <label>${t("Verwacht morgen")}</label>
                  <dac-entity-picker data-forecast="tomorrow"></dac-entity-picker>
                </div>
              </div>
              <div class="row">
                <label>${t("Tijdstip hoogste opwek vandaag")}</label>
                <dac-entity-picker data-forecast="peak_today"></dac-entity-picker>
                <span class="sub">${t("Optioneel. Hiermee kan de coach zeggen rond welk uur het overschot het grootst is.")}</span>
              </div>
            </div>
          </div>
        </section>

        <section class="card">
          <h2>${icons.gauge} ${t("Meterstanden")}</h2>
          <p class="hint">${t("De tellers van je slimme meter, zoals ze op de meter zelf staan. Vul in wat je hebt; alleen de ingevulde standen komen op het overzicht te staan. Dit zijn totalen in kWh en m³, dus geen vermogens.")}</p>
          <div class="fields">
            <div class="block fields">
            <div class="block-title">${t("Stroom")}</div>
            <div class="row">
              <label>${t("Opwek totaal (teller)")}</label>
              <dac-entity-picker data-meter="solar_total"></dac-entity-picker>
              <span class="sub">${t("De teller van je omvormer in kWh, niet het vermogen. Zonder deze kan het paneel niet terugkijken op wat je hebt opgewekt.")}</span>
            </div>
            <div id="solar-total-extra"></div>
            <div class="row">
              <button type="button" class="add" id="solar-total-extra-add">${t("Nog een opwekteller")}</button>
              <span class="sub">${t("De teller van elke andere omvormer; het paneel telt ze op.")}</span>
            </div>
            <div class="two">
              <div class="row">
                <label>${t("Geleverd, laag tarief")}</label>
                <dac-entity-picker data-meter="import_low"></dac-entity-picker>
              </div>
              <div class="row">
                <label>${t("Geleverd, hoog tarief")}</label>
                <dac-entity-picker data-meter="import_high"></dac-entity-picker>
              </div>
              <div class="row">
                <label>${t("Teruggeleverd, laag tarief")}</label>
                <dac-entity-picker data-meter="export_low"></dac-entity-picker>
              </div>
              <div class="row">
                <label>${t("Teruggeleverd, hoog tarief")}</label>
                <dac-entity-picker data-meter="export_high"></dac-entity-picker>
              </div>
            </div>
            </div>

            <div class="block fields">
            <div class="block-title">${t("Gas")}</div>
            <label class="check" for="gas-enabled">
              <input type="checkbox" id="gas-enabled">
              <span>
                <strong>${t("Deze woning gebruikt gas")}</strong>
                ${t("Staat dit uit, dan blijft gas van het overzicht weg.")}
              </span>
            </label>

            <div class="row" id="gas-field">
              <label>${t("Gasmeter (m³)")}</label>
              <dac-entity-picker data-meter="gas"></dac-entity-picker>
            </div>
            </div>

            <div class="block fields">
            <div class="block-title">${t("Water")}</div>
            <label class="check" for="water-enabled">
              <input type="checkbox" id="water-enabled">
              <span>
                <strong>${t("Deze woning heeft een watermeter in Home Assistant")}</strong>
                ${t("Bijvoorbeeld de HomeWizard Watermeter. Dan staat water bij de standen, in de historie en in het rapport.")}
              </span>
            </label>

            <div class="fields" id="water-field">
              <div class="row">
                <label>${t("Watermeter (m³)")}</label>
                <dac-entity-picker data-meter="water"></dac-entity-picker>
                <span class="sub">${t("De teller, in m³.")}</span>
              </div>
              <div class="row">
                <label>${t("Waterverbruik nu (L/min)")}</label>
                <dac-entity-picker data-meter="water_flow"></dac-entity-picker>
                <span class="sub">${t("Optioneel. Met deze sensor kan de coach melden als er te lang onafgebroken water loopt; zie Meldingen.")}</span>
              </div>
            </div>
            </div>
          </div>
        </section>

        <section class="card">
          <h2>${icons.home} ${t("Navigatie")}</h2>
          <p class="hint">${t("De Home-knop rechtsboven brengt je terug naar je eigen dashboard. Draai je Kiosk Mode, dan is dat de enige weg terug.")}</p>
          <div class="fields">
            <div class="row">
              <label for="home-path">${t("Pad van je thuisdashboard")}</label>
              <input type="text" id="home-path" inputmode="url" placeholder="/lovelace/0" autocomplete="off">
              <span class="sub">${t("Bijvoorbeeld {a} of {b}.", { a: "<code>/lovelace/0</code>", b: "<code>/dashboard-woning/overzicht</code>" })}</span>
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
        this.afterChange_();
      });
    };

    bind("home-name", (v) => (this.draft_.installation.home_name = v));
    bind("taal", (v) => (this.draft_.installation.language = v));
    bind("fuse", (v) => {
      this.draft_.installation.fuse_amps = Number(v);
      this.recalculate_();
    });
    bind("max-grid", (v) => {
      this.draft_.installation.max_grid_watts = Number(v);
      // Typing a ceiling by hand is the whole point of overriding it.
      this.draft_.installation.max_grid_auto = false;
      this.$("#max-auto").checked = false;
    });

    bind("home-path", (v) => (this.draft_.navigation.home_path = v));

    for (const picker of this.$$("dac-entity-picker[data-key]")) {
      picker.filter = "power";
      picker.placeholder = t("Zoek een vermogenssensor…");
      picker.addEventListener("dac-entity-change", (ev) => {
        this.draft_.sources[picker.dataset.key] = ev.detail.value;
        this.afterChange_();
      });
    }

    for (const picker of this.$$("#phase-fields dac-entity-picker[data-phase]")) {
      const { phase, kind } = picker.dataset;
      picker.filter = kind === "power" ? "power" : "all";
      picker.placeholder =
        kind === "current" ? t("Zoek een stroomsensor…")
        : kind === "voltage" ? t("Zoek een spanningssensor…")
        : t("Zoek een vermogenssensor…");
      picker.addEventListener("dac-entity-change", (ev) => {
        this.draft_.sources.phases[phase][kind] = ev.detail.value;
        this.afterChange_();
      });
    }

    // Meter readings are counters in kWh or m3, so the picker looks for energy
    // rather than power: a customer searching "verbruik" otherwise gets the
    // watts they already mapped above.
    for (const picker of this.$$("dac-entity-picker[data-forecast]")) {
      picker.filter = "all";
      picker.placeholder =
        picker.dataset.forecast === "peak_today" ? t("Zoek een tijdstip…") : t("Zoek een verwachting in kWh…");
      picker.addEventListener("dac-entity-change", (ev) => {
        (this.draft_.sources.solar_forecast ??= {})[picker.dataset.forecast] = ev.detail.value;
        this.afterChange_();
      });
    }

    this.$("#solar-extra-add").addEventListener("click", () => {
      (this.draft_.sources.solar_extra ??= []).push("");
      this.paintExtra_();
      this.afterChange_();
    });
    this.$("#solar-total-extra-add").addEventListener("click", () => {
      ((this.draft_.sources.meters ??= {}).solar_total_extra ??= []).push("");
      this.paintExtra_();
      this.afterChange_();
    });

    for (const picker of this.$$("dac-entity-picker[data-meter]")) {
      picker.filter = "all";
      picker.placeholder =
        picker.dataset.meter === "gas" ? t("Zoek je gasmeter…") : t("Zoek een meterstand…");
      picker.addEventListener("dac-entity-change", (ev) => {
        // Created on demand: settings written before this section existed have
        // no `meters` at all until the server merges its defaults in.
        (this.draft_.sources.meters ??= {})[picker.dataset.meter] = ev.detail.value;
        this.afterChange_();
      });
    }

    for (const [id, apply] of [
      ["phases-enabled", (on) => (this.draft_.sources.phases_enabled = on)],
      ["gas-enabled", (on) => ((this.draft_.sources.meters ??= {}).gas_enabled = on)],
      ["water-enabled", (on) => ((this.draft_.sources.meters ??= {}).water_enabled = on)],
    ]) {
      const box = this.$(`#${id}`);
      box.addEventListener("change", () => {
        apply(box.checked);
        this.paintFaseVelden_();
        this.paintGas_();
        this.afterChange_();
      });
    }

    const invert = this.$("#src-invert");
    invert.addEventListener("change", () => {
      this.draft_.sources.grid_signed_invert = invert.checked;
      this.afterChange_();
    });

    for (const button of this.$$("#grid-mode button")) {
      button.addEventListener("click", () => {
        this.draft_.sources.grid_mode = button.dataset.mode;
        this.paintGridMode_();
        this.afterChange_();
      });
    }

    this.$("#max-auto").addEventListener("change", (ev) => {
      this.draft_.installation.max_grid_auto = ev.target.checked;
      this.recalculate_();
      this.afterChange_();
    });


    const nieuw = (kind) => () => {
      this.circuits_().push({
        id: `g-${Date.now().toString(36)}`,
        kind,
        name: "",
        fuse_amps: kind === "kast" ? 25 : 16,
        phases: 3,
        parent: kind === "groep" ? (this.circuits_().find((g) => g.kind === "kast")?.id ?? "") : "",
        meter: false,
        sensors: { l1: {}, l2: {}, l3: {} },
      });
      this.paintCircuits_();
      this.afterChange_();
    };
    this.$("#kast-add").addEventListener("click", nieuw("kast"));
    this.$("#circuit-add").addEventListener("click", nieuw("groep"));

    this.$("#terug-bewoner").addEventListener("change", (ev) => {
      this.draft_.installation.payback_resident = ev.target.checked;
      this.afterChange_();
    });

    this.$("#balancer").addEventListener("change", (ev) => {
      this.draft_.installation.load_balancer = ev.target.checked;
      this.paintBalancer_();
      this.afterChange_();
    });

    for (const button of this.$$("#phases button")) {
      button.addEventListener("click", () => {
        this.draft_.installation.phases = Number(button.dataset.phases);
        this.recalculate_();
        this.paintPhases_();
        this.afterChange_();
      });
    }

    const balancer = this.$("#balancer-limit");
    balancer.filter = "current";
    balancer.placeholder = t("Zoek een stroomsensor…");
    balancer.addEventListener("dac-entity-change", (ev) => {
      this.draft_.installation.balancer_entity = ev.detail.value;
      this.paintBalancer_();
      this.afterChange_();
    });

    this.wireSaveBar_();
    this.paint_();
  }

  afterChange_() {
    this.paintHints_();
    this.syncSaveBar_();
  }

  /**
   * De grenssensor hoort alleen bij een installatie die een lastbewaker heeft.
   *
   * Verborgen met een klasse en niet met `hidden` alleen: het attribuut is een
   * regel van de browser zelf en verliest van elke `display` in de eigen
   * stijlen. Zie de regel voor `.row` hierboven.
   */
  paintBalancer_() {
    const row = this.$("#balancer-row");
    row.hidden = !this.draft_.installation.load_balancer;
    row.style.display = this.draft_.installation.load_balancer ? "" : "none";
  }

  /** Keep the power ceiling in step with the fuse while it is automatic. */
  recalculate_() {
    const inst = this.draft_.installation;
    if (!inst.max_grid_auto) return;
    inst.max_grid_watts = Math.round((Number(inst.phases) || 1) * (Number(inst.fuse_amps) || 0) * VOLTAGE);
    this.$("#max-grid").value = inst.max_grid_watts;
  }

  paint_() {
    if (!this.draft_ || !this.rendered_) return;
    // De lijsten die dit scherm tekent bestaan in het klad én in wat er
    // opgeslagen staat, anders staat de balk op "niet opgeslagen" zonder dat er
    // iets veranderde. De server geeft ze standaard mee; dit is voor oudere
    // instellingen zonder.
    for (const d of [this.draft_, this.saved_]) {
      if (!d?.sources) continue;
      d.sources.solar_extra ??= [];
      (d.sources.meters ??= {}).solar_total_extra ??= [];
      if (d.installation) d.installation.circuits ??= [];
    }
    const inst = this.draft_.installation;

    this.$("#home-name").value = inst.home_name ?? "";
    this.$("#taal").value = inst.language ?? "auto";
    this.$("#fuse").value = inst.fuse_amps;
    this.$("#max-grid").value = inst.max_grid_watts;
    this.$("#max-auto").checked = Boolean(inst.max_grid_auto);
    this.$("#terug-bewoner").checked = Boolean(inst.payback_resident);
    this.$("#balancer").checked = Boolean(inst.load_balancer);
    this.$("#balancer-limit").value = inst.balancer_entity ?? "";
    this.paintBalancer_();
    // Hoe het huis gemeten wordt, uit Instellingen (tot v0.114.0).
    const d = this.draft_;
    this.$("#home-path").value = d.navigation.home_path ?? "";
    this.$("#src-invert").checked = Boolean(d.sources.grid_signed_invert);
    for (const picker of this.$$("dac-entity-picker[data-key]")) {
      picker.value = d.sources[picker.dataset.key] ?? "";
    }
    for (const picker of this.$$("#phase-fields dac-entity-picker[data-phase]")) {
      const { phase, kind } = picker.dataset;
      picker.value = d.sources.phases?.[phase]?.[kind] ?? "";
    }
    this.$("#phases-enabled").checked = Boolean(d.sources.phases_enabled);
    for (const picker of this.$$("dac-entity-picker[data-forecast]")) {
      picker.value = d.sources.solar_forecast?.[picker.dataset.forecast] ?? "";
    }
    for (const picker of this.$$("dac-entity-picker[data-meter]")) {
      picker.value = d.sources.meters?.[picker.dataset.meter] ?? "";
    }
    this.$("#gas-enabled").checked = Boolean(d.sources.meters?.gas_enabled);
    this.$("#water-enabled").checked = Boolean(d.sources.meters?.water_enabled);
    this.paintExtra_();
    this.paintGridMode_();
    this.paintFaseVelden_();
    this.paintGas_();
    this.onFeed_();

    this.paintPhases_();
    this.paintCircuits_();
    this.paintHints_();
    this.syncSaveBar_();
  }


  /**
   * De onderverdeelkasten en groepen in het klad, altijd als lijst, en elk met
   * zijn soort en of hij een eigen kWh-meter heeft (v0.101.5).
   *
   * Van voor v0.101.5 staat er geen soort bij. Een kast is dan wat onder de
   * hoofdkast hangt en zelf groepen draagt of een meter heeft: bij de eigenaar de
   * lounge met de laadpaal en de batterij eronder, in de eerste woning de garage
   * met zijn meter. En een meter heeft wie sensoren heeft.
   */
  circuits_() {
    const inst = this.draft_.installation;
    if (!Array.isArray(inst.circuits)) inst.circuits = [];
    // Ook in wat er opgeslagen staat, anders staat het scherm meteen op "niet
    // opgeslagen" terwijl er niets veranderd is.
    kastenIndelen(this.saved_?.installation?.circuits);
    return kastenIndelen(inst.circuits);
  }

  /**
   * Eén onderverdeelkast of groep als blok: naam, zekering, fasen, waar hij onder
   * hangt, of hij een eigen kWh-meter heeft, en alleen dan per fase de sensoren.
   * Zelfde velden als de fasen van de hoofdaansluiting bij Instellingen.
   */
  /**
   * Zonder eigen meter: de apparaten met een vermogenssensor die op deze groep hangen (v0.165.0).
   * Sven, 26-10-2026: "Onder Groepen laat je het vinkje van aparte kWh-meter dan uit, maar voeg je
   * per groep een of meerdere apparaten toe." Hun som is wat de coach van de groep weet. Een laadpaal
   * en een thuisbatterij niet: die rekent de coach al zelf mee. Een apparaat hoort bij één groep.
   */
  circuitDevicesHtml_(g, index, groepen, esc) {
    const apparaten = (this.draft_?.devices ?? []).filter(
      (d) => d?.id && d.entity && d.type !== "laadpaal" && d.type !== "thuisbatterij"
    );
    const naam = (id) => apparaten.find((d) => d.id === id)?.name || id;
    const elders = new Set(groepen.filter((o) => o !== g).flatMap((o) => (o.devices ?? []).map((r) => r.device)));
    const gekozen = (g.devices ?? []).filter((r) => apparaten.some((d) => d.id === r.device));
    const vrij = apparaten.filter((d) => !elders.has(d.id) && !gekozen.some((r) => r.device === d.id));
    const drie = Number(g.phases) !== 1;
    const rijen = gekozen
      .map(
        (r) => `
          <div class="extra-line circuit-device">
            <span class="circuit-device-name">${esc(naam(r.device))}</span>
            ${drie ? `<select data-circuit-device-phase="${index}:${esc(r.device)}" aria-label="${t("Fase")}">
              ${["l1", "l2", "l3"].map((f) => `<option value="${f}"${(r.phase || "l1") === f ? " selected" : ""}>${f.toUpperCase()}</option>`).join("")}
            </select>` : ""}
            <button type="button" class="remove" data-circuit-device-remove="${index}:${esc(r.device)}" aria-label="${t("Weghalen")}">${icons.trash}</button>
          </div>`
      )
      .join("");
    const kiezen = vrij.length
      ? `<select data-circuit-device-add="${index}" aria-label="${t("Apparaat toevoegen")}">
          <option value="">${t("Apparaat toevoegen…")}</option>
          ${vrij.map((d) => `<option value="${esc(d.id)}">${esc(d.name || d.id)}</option>`).join("")}
        </select>`
      : "";
    return `
        <div class="row circuit-devices">
          <label>${t("Gemeten via apparaten")}</label>
          <p class="hint">${t("Kies de apparaten met een vermogenssensor die op deze groep hangen. Hun som is wat de coach van de groep weet; wat er verder op hangt ziet hij niet. Zit de groep bijna aan zijn zekering, dan krijg je een melding.")}</p>
          ${rijen}
          ${kiezen}
        </div>`;
  }

  /**
   * De fase van een groep van één fase (v0.168.0). Tot dan heette zo'n groep altijd L1, ook als de
   * batterij erop op L3 zat (een klantwoning, 27-10-2026). Zonder keuze de fase van de batterij die
   * eraan hangt, anders L1. De sensoren blijven onder "l1" staan.
   */
  groepFase_(g) {
    if (["l1", "l2", "l3"].includes(g.phase)) return g.phase;
    const batterij = (this.draft_?.devices ?? []).find((d) => d?.circuit === g.id && ["l1", "l2", "l3"].includes(d.battery?.phase));
    return batterij?.battery.phase ?? "l1";
  }

  circuitHtml_(g, index, groepen) {
    const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
    const fasen = Number(g.phases) === 1 ? ["l1"] : ["l1", "l2", "l3"];
    const kast = g.kind === "kast";
    // Een kast hangt onder de hoofdkast of een andere kast, een groep ook onder een groep.
    const anderen = groepen.filter((o) => o !== g && o.id !== g.id && (!kast || o.kind === "kast"));
    const soortVan = (o) => (o.kind === "kast" ? "" : ` (${t("groep")})`);
    const onder = kast && !anderen.length
      ? ""
      : `
          <div class="row">
            <label for="circuit-parent-${index}">${t("Hangt onder")}</label>
            <select id="circuit-parent-${index}" data-circuit-field="parent" data-index="${index}">
              <option value=""${g.parent ? "" : " selected"}>${t("Hoofdkast")}</option>
              ${anderen
                .map((o) => `<option value="${esc(o.id)}"${g.parent === o.id ? " selected" : ""}>${esc(o.name || (o.kind === "kast" ? t("Nieuwe onderverdeelkast") : t("Nieuwe groep")))}${o.name ? soortVan(o) : ""}</option>`)
                .join("")}
            </select>
          </div>`;
    return `
      <div class="circuit" data-circuit="${index}">
        <div class="two">
          <div class="row">
            <label for="circuit-name-${index}">${t("Naam")}</label>
            <input type="text" id="circuit-name-${index}" data-circuit-field="name" data-index="${index}"
                   value="${esc(g.name)}" placeholder="${kast ? t("Bijvoorbeeld: Garage") : t("Bijvoorbeeld: Laadpaal")}" autocomplete="off">
          </div>
          <div class="row">
            <label for="circuit-fuse-${index}">${t("Zekering per fase (A)")}</label>
            <input type="number" id="circuit-fuse-${index}" data-circuit-field="fuse_amps" data-index="${index}"
                   min="1" max="1000" step="1" inputmode="numeric" value="${esc(g.fuse_amps)}">
          </div>
        </div>
        <div class="two">
          <div class="row">
            <label for="circuit-phases-${index}">${t("Aantal fasen")}</label>
            <select id="circuit-phases-${index}" data-circuit-field="phases" data-index="${index}">
              <option value="1"${Number(g.phases) === 1 ? " selected" : ""}>${t("1 fase")}</option>
              <option value="3"${Number(g.phases) !== 1 ? " selected" : ""}>${t("3 fasen")}</option>
            </select>
          </div>
          ${onder}
        </div>
        ${Number(g.phases) === 1 ? `
        <div class="row">
          <label for="circuit-phase-${index}">${t("Op fase")}</label>
          <select id="circuit-phase-${index}" data-circuit-field="phase" data-index="${index}">
            ${["l1", "l2", "l3"].map((f) => `<option value="${f}"${this.groepFase_(g) === f ? " selected" : ""}>${f.toUpperCase()}</option>`).join("")}
          </select>
          <span class="sub">${t("Op welke fase van de hoofdaansluiting deze groep zit. Alles wat erop hangt zit op dezelfde fase.")}</span>
        </div>` : ""}
        <label class="check">
          <input type="checkbox" data-circuit-meter="${index}"${g.meter ? " checked" : ""}>
          <span><strong>${kast ? t("Deze onderverdeelkast heeft een eigen kWh-meter") : t("Deze groep heeft een eigen kWh-meter")}</strong> ${t("Dan vul je hieronder per fase de sensoren in.")}</span>
        </label>
        ${(g.meter ? fasen : [])
          .map(
            (phase) => `
        <div class="phase-block">
          <div class="phase-title">${(Number(g.phases) === 1 ? this.groepFase_(g) : phase).toUpperCase()}</div>
          <div class="row">
            <label>${t("Stroom (A)")}</label>
            <dac-entity-picker data-circuit="${index}" data-phase="${phase}" data-kind="current"></dac-entity-picker>
          </div>
          <div class="row">
            <label>${t("Vermogen")}</label>
            <dac-entity-picker data-circuit="${index}" data-phase="${phase}" data-kind="power"></dac-entity-picker>
          </div>
          <div class="row">
            <label>${t("Spanning (V)")}</label>
            <dac-entity-picker data-circuit="${index}" data-phase="${phase}" data-kind="voltage"></dac-entity-picker>
          </div>
        </div>`
          )
          .join("")}
        ${g.meter ? "" : this.circuitDevicesHtml_(g, index, groepen, esc)}
        <div class="circuit-actions">
          <button type="button" class="remove" data-circuit-remove="${index}">${kast ? t("Onderverdeelkast verwijderen") : t("Groep verwijderen")}</button>
        </div>
      </div>`;
  }

  /**
   * Wat er opgeslagen wordt: zonder eigen kWh-meter geen sensoren, zodat de
   * coach er niet op rekent (v0.101.5). In het klad blijven ze staan, zodat het
   * vinkje per ongeluk uit en weer aan niets kost.
   */
  payload_(sections) {
    const uit = { ...super.payload_(sections) };
    // "Fasen tonen op het overzicht" staat sinds v0.114.0 onder Voorkeuren, en
    // de bewoner zet hem daar. Een oude kopie hier mag hem niet terugzetten; de
    // opslag voegt samen, dus wat niet meekomt blijft staan.
    if (uit.sources && "phases_on_overview" in uit.sources) {
      const { phases_on_overview: _weg, ...bronnen } = uit.sources;
      uit.sources = bronnen;
    }
    const inst = uit?.installation;
    if (!inst || !Array.isArray(inst.circuits)) return uit;
    return {
      ...uit,
      installation: {
        ...inst,
        // Met een eigen meter tellen de sensoren en niet de apparaten (v0.165.0); zonder andersom.
        // Een groep van één fase krijgt zijn fase mee, ook als de bewoner de voorgestelde liet staan (v0.168.0).
        circuits: inst.circuits.map((g) => ({
          ...(g?.meter === false ? { ...g, sensors: {} } : { ...g, devices: [] }),
          ...(g && Number(g.phases) === 1 ? { phase: this.groepFase_(g) } : {}),
        })),
      },
    };
  }

  paintCircuits_() {
    const host = this.$("#circuits");
    const kastHost = this.$("#kasten");
    if (!host || !kastHost) return;
    const groepen = this.circuits_();
    const blok = (soort) => groepen.map((g, i) => (g.kind === soort ? this.circuitHtml_(g, i, groepen) : "")).join("");
    kastHost.innerHTML = blok("kast");
    host.innerHTML = blok("groep");
    this.wireCircuits_(kastHost, groepen);
    this.wireCircuits_(host, groepen);
  }

  wireCircuits_(host, groepen) {
    for (const el of host.querySelectorAll("[data-circuit-field]")) {
      const g = groepen[Number(el.dataset.index)];
      const field = el.dataset.circuitField;
      el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => {
        if (field === "fuse_amps" || field === "phases") g[field] = Number(el.value);
        else g[field] = el.value;
        if (field === "phases" && g.phases === 1 && !g.phase) g.phase = this.groepFase_(g);
        // Een ander aantal fasen is een ander aantal sensorrijen, en een
        // andere naam hoort meteen in de keuzelijst van de andere groepen.
        if (field === "phases" || field === "parent") this.paintCircuits_();
        this.afterChange_();
      });
    }
    for (const vink of host.querySelectorAll("[data-circuit-meter]")) {
      vink.addEventListener("change", () => {
        groepen[Number(vink.dataset.circuitMeter)].meter = vink.checked;
        this.paintCircuits_();
        this.afterChange_();
      });
    }
    for (const picker of host.querySelectorAll("dac-entity-picker[data-circuit]")) {
      const g = groepen[Number(picker.dataset.circuit)];
      const { phase, kind } = picker.dataset;
      picker.filter = kind === "power" ? "power" : kind === "current" ? "current" : "all";
      picker.placeholder =
        kind === "current" ? t("Zoek een stroomsensor…")
        : kind === "voltage" ? t("Zoek een spanningssensor…")
        : t("Zoek een vermogenssensor…");
      if (this.feed_) picker.stateFeed = this.feed_;
      picker.value = g.sensors?.[phase]?.[kind] ?? "";
      picker.addEventListener("dac-entity-change", (ev) => {
        if (!g.sensors) g.sensors = {};
        if (!g.sensors[phase]) g.sensors[phase] = {};
        g.sensors[phase][kind] = ev.detail.value;
        this.afterChange_();
      });
    }
    for (const keuze of host.querySelectorAll("[data-circuit-device-add]")) {
      keuze.addEventListener("change", () => {
        if (!keuze.value) return;
        const g = groepen[Number(keuze.dataset.circuitDeviceAdd)];
        (g.devices ??= []).push({ device: keuze.value, phase: "l1" });
        this.paintCircuits_();
        this.afterChange_();
      });
    }
    for (const keuze of host.querySelectorAll("[data-circuit-device-phase]")) {
      keuze.addEventListener("change", () => {
        const [i, id] = keuze.dataset.circuitDevicePhase.split(/:(.*)/s);
        const rij = (groepen[Number(i)].devices ?? []).find((r) => r.device === id);
        if (rij) rij.phase = keuze.value;
        this.afterChange_();
      });
    }
    for (const knop of host.querySelectorAll("[data-circuit-device-remove]")) {
      knop.addEventListener("click", () => {
        const [i, id] = knop.dataset.circuitDeviceRemove.split(/:(.*)/s);
        const g = groepen[Number(i)];
        g.devices = (g.devices ?? []).filter((r) => r.device !== id);
        this.paintCircuits_();
        this.afterChange_();
      });
    }
    for (const knop of host.querySelectorAll("[data-circuit-remove]")) {
      knop.addEventListener("click", () => {
        const weg = groepen[Number(knop.dataset.circuitRemove)];
        groepen.splice(groepen.indexOf(weg), 1);
        // Wie onder de verwijderde kast of groep hing, hangt weer aan de hoofdkast.
        for (const o of groepen) if (o.parent === weg.id) o.parent = "";
        this.paintCircuits_();
        this.afterChange_();
      });
    }
  }

  paintPhases_() {
    const phases = Number(this.draft_.installation.phases) || 1;
    for (const button of this.$$("#phases button")) {
      button.setAttribute("aria-pressed", String(Number(button.dataset.phases) === phases));
    }
  }


  /**
   * De extra omvormers en hun tellers: een kiezer per stuk, met een kruisje.
   *
   * Meer omvormers: de bewoner van de eerste woning op 22-09-2026, "steeds
   * meer consumenten hebben meerdere omvormers." Een lijst en niet een tweede
   * en derde vast veld, want drie is niet het einde.
   */
  paintExtra_() {
    const d = this.draft_;
    if (!d) return;
    const teken = (host, lijst, kind, placeholder) => {
      host.innerHTML = lijst
        .map(
          (_, i) => `
          <div class="row extra-row">
            <label>${kind === "solar" ? t("Omvormer {n}", { n: i + 2 }) : t("Opwekteller {n}", { n: i + 2 })}</label>
            <div class="extra-line">
              <dac-entity-picker data-extra="${kind}" data-index="${i}"></dac-entity-picker>
              <button type="button" class="remove" data-extra-remove="${kind}:${i}" aria-label="${t("Weghalen")}">${icons.trash}</button>
            </div>
          </div>`
        )
        .join("");
      for (const picker of host.querySelectorAll("dac-entity-picker[data-extra]")) {
        const i = Number(picker.dataset.index);
        picker.filter = kind === "solar" ? "power" : "all";
        picker.placeholder = placeholder;
        picker.stateFeed = this.feed_;
        picker.value = lijst[i] ?? "";
        picker.addEventListener("dac-entity-change", (ev) => {
          lijst[i] = ev.detail.value;
          this.afterChange_();
        });
      }
      for (const knop of host.querySelectorAll("[data-extra-remove]")) {
        knop.addEventListener("click", () => {
          lijst.splice(Number(knop.dataset.extraRemove.split(":")[1]), 1);
          this.paintExtra_();
          this.afterChange_();
        });
      }
    };
    teken(this.$("#solar-extra"), (d.sources.solar_extra ??= []), "solar", t("Zoek een vermogenssensor…"));
    teken(this.$("#solar-total-extra"), ((d.sources.meters ??= {}).solar_total_extra ??= []), "meter", t("Zoek een meterstand…"));
  }


  paintFaseVelden_() {
    this.$("#phase-fields").style.display = this.draft_.sources.phases_enabled ? "" : "none";
  }


  paintGas_() {
    this.$("#gas-field").style.display = this.draft_.sources.meters?.gas_enabled ? "" : "none";
    this.$("#water-field").style.display = this.draft_.sources.meters?.water_enabled ? "" : "none";
  }


  paintGridMode_() {
    const mode = this.draft_.sources.grid_mode ?? "split";
    for (const button of this.$$("#grid-mode button")) {
      button.setAttribute("aria-pressed", String(button.dataset.mode === mode));
    }
    this.$("#grid-split").style.display = mode === "split" ? "" : "none";
    this.$("#grid-signed").style.display = mode === "signed" ? "" : "none";
  }


  /** Where the arithmetic is spelled out, so it can be checked. */
  paintHints_() {
    const inst = this.draft_.installation;
    const phases = Number(inst.phases) || 1;
    const fuse = Number(inst.fuse_amps) || 0;
    const kw = (watts) =>
      (watts / 1000).toLocaleString(locale(), { minimumFractionDigits: 3, maximumFractionDigits: 3 });

    const computed = phases * fuse * VOLTAGE;
    // Once it has been overridden, showing the formula would claim an arithmetic
    // the number no longer follows.
    this.$("#max-grid-hint").textContent = inst.max_grid_auto
      ? `${phases} × ${fuse} A × ${VOLTAGE} V = ${kw(computed)} kW`
      : t("Handmatig ingesteld op {kw} kW; berekend zou {berekend} kW zijn", { kw: kw(Number(inst.max_grid_watts) || 0), berekend: kw(computed) });
  }
}

DacViewInstallation.css = /* css */ `
  ${editorCss}

  /* ---- groepen ---- */
  .circuit {
    padding: 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(var(--dac-veil),0.022);
    display: grid;
    gap: 12px;
    margin-bottom: 12px;
  }
  .phase-block {
    padding: 12px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    display: grid;
    gap: 10px;
  }
  .phase-title {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.12em;
    color: var(--dac-accent-hi);
  }
  .circuit-actions { display: flex; justify-content: flex-end; }
  .circuit-actions button {
    font: inherit;
    font-size: 13px;
    padding: 8px 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(var(--dac-veil),0.04);
    color: var(--dac-ink);
    cursor: pointer;
  }
  .circuit-actions button.remove { color: var(--dac-danger, #e5484d); }

  /* ---- extra omvormers ---- */
  .extra-line { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; }
  .circuit-devices { display: grid; gap: 8px; }
  .circuit-device { grid-template-columns: minmax(0, 1fr) auto auto; }
  .circuit-device-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .extra-line .remove, button.add {
    font: inherit; font-size: 13px; padding: 8px 12px;
    border-radius: var(--dac-radius-sm); border: 1px solid var(--dac-border);
    background: rgba(var(--dac-veil),0.04); color: var(--dac-ink); cursor: pointer;
  }
  .extra-line .remove { padding: 6px 8px; display: inline-flex; }
  .extra-line .remove svg { width: 16px; height: 16px; }
  button.add { justify-self: start; }
`;

define("dac-view-installation", DacViewInstallation);
