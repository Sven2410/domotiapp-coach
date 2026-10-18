/**
 * Contract -- wat stroom, gas en water kosten, nu en vroeger.
 *
 * Stond tot v0.114.0 onder Installatie. De eigenaar op 08-10-2026: "sommige
 * dingen kunnen van installatie naar instellingen of andersom, het moet beter
 * gecategoriseerd worden." Installatie is nu hoe het huis gemeten wordt en wat
 * het aankan; wat het kost is een eigen onderwerp, en alleen de installateur
 * ziet het.
 *
 * Sinds v0.129.0 per energiebron. De bewoner van de eerste woning op
 * 18-10-2026: "Eerst álles uitvragen over elektriciteit (incl historische
 * contracten), dán pas alles over gas (en mogelijk ook te kiezen tussen vast en
 * dynamisch), en daarna pas water." Per bron een leverancier uit de catalogus
 * (`leveranciers.js`) die de velden voorinvult, de looptijd, en de knop "Ik heb
 * een nieuw contract afgesloten" die het huidige contract bij de eerdere zet.
 * Bij stroom de opbouw in woorden en cijfers (`opbouw.js`), nagerekend door de
 * coach tegen de all-in sensor, en "Ja, dit klopt".
 *
 * Sinds v0.130.1 ziet de bewoner dit scherm ook, alleen om te lezen: per bron
 * wat voor contract, bij wie, van wanneer tot wanneer, de opbouw van zijn
 * stroomprijs en "Ja, dit klopt". Die prijs stond tot dan onder Voorkeuren; de
 * eigenaar op 19-10-2026: "je energieprijs staat nu in voorkeuren maar dat moet
 * onder contract." Wat met `data-installateur` gemerkt is ziet hij niet, want
 * daar staan sensoren en bedragen die de installateur kiest.
 */

import { define } from "../base.js";
import { icons } from "../icons.js";
import {
  DacEditorElement,
  editorCss,
  saveBarHtml,
} from "./editor-base.js";
import "../components/entity-picker.js";
import { salderen } from "../geld.js";
import { bevestigdZin, opbouwCss, opbouwHtml } from "../opbouw.js";
import {
  SOORTEN,
  belastingStroom,
  leverancier,
  leveranciersVoor,
  namenVan,
  nordPoolVan,
  sensorVan,
  voorstel,
} from "../leveranciers.js";

const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

const SOORT_NAAM = { fixed: "vast", variable: "variabel", dynamic: "dynamisch" };

/** Een datum als "18-10-2026", voor een naam. */
const kortDatum = (tekst) => (tekst ? tekst.split("-").reverse().join("-") : "");

/**
 * De naam die een eerder contract voorgesteld krijgt (v0.129.0): leverancier,
 * soort en de datums. De bewoner van de eerste woning op 19-10-2026: "ook
 * handmatig een naam kunnen ingeven van dat contract", zoals "Zonneplan Elektra
 * 2026"; dit is alleen het begin, hij past hem aan.
 */
function voorgesteldeNaam(bron, supplier, soort, van, tot) {
  const naam = leverancier(supplier)?.naam ?? "";
  const wat = { stroom: "stroom", gas: "gas", water: "water" }[bron];
  const datums = van || tot ? `${kortDatum(van) || "?"} tot ${kortDatum(tot) || "nu"}` : "";
  return [naam, soort ? `${wat}, ${SOORT_NAAM[soort] ?? ""}` : wat, datums].filter(Boolean).join(" ");
}

/** Vandaag en gisteren als "2026-10-18", in de tijd van het huis. */
function dagTekst(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const euroTekst = (n) => `€ ${Number(n).toLocaleString("nl-NL", { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`;

function datumLang(tekst) {
  if (!tekst) return "";
  const d = new Date(`${tekst}T12:00:00`);
  return Number.isNaN(d.getTime()) ? tekst : d.toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric" });
}

const soortKnoppen = (id) => `
  <div class="segmented drie" id="${id}">
    ${SOORTEN.map((s) => `
      <button type="button" data-soort="${s.key}" aria-pressed="false">
        <strong>${s.label}</strong>
        ${s.uitleg}
      </button>`).join("")}
  </div>`;

const levKeuze = (id, bron) => `
  <select id="${id}">
    <option value="">Andere leverancier</option>
    ${leveranciersVoor(bron).map((l) => `<option value="${esc(l.id)}">${esc(l.naam)}</option>`).join("")}
  </select>`;

/**
 * De eerdere contracten voor de bewoner (v0.130.1): een regel per contract met
 * de naam, de datums en de prijs, zonder velden.
 */
export function periodesLezen(bron, lijst) {
  if (!lijst?.length) return `<p class="sub geen">Geen eerdere contracten.</p>`;
  return lijst.map((p) => {
    const titel = p.name || leverancier(p.supplier)?.naam || "Eerder contract";
    const wanneer = p.from || p.to ? `${kortDatum(p.from) || "?"} tot ${kortDatum(p.to) || "nu"}` : "";
    let prijs = "";
    if (bron === "stroom") {
      prijs = p.type === "dynamic" ? "Dynamisch" : Number(p.all_in_price) > 0 ? `${euroTekst(p.all_in_price)} per kWh` : "";
    } else if (Number(p.price) > 0) {
      prijs = `${euroTekst(p.price)} per m³`;
    }
    return `
      <div class="circuit period lezen">
        <div class="p-kop"><span class="p-naam">${esc(titel)}</span><span class="p-wanneer">${esc(wanneer)}</span></div>
        ${prijs ? `<span class="sub">${esc(prijs)}</span>` : ""}
      </div>`;
  }).join("");
}

class DacViewContract extends DacEditorElement {
  static sections = ["contract"];

  constructor() {
    super();
    this.check_ = null;
    this.checkTimer_ = null;
    this.checkRun_ = 0;
  }

  render() {
    return `
      <div class="wrap">
        <header class="intro">
          <div class="eyebrow">Contract</div>
          <h1>Wat je energie kost</h1>
          <p>Per energiebron je contract van nu en wat je eerder had. De coach rekent met je stroomcontract; gas en water zijn voor de historie en het rapport.</p>
          <p class="bewoner-uitleg">Je installateur vult je contract in. Kijk hieronder of je stroomprijs klopt met de app of site van je leverancier, en bevestig hem. Klopt er iets niet, laat het je installateur dan weten.</p>
        </header>

        <!-- ================= stroom ================= -->
        <section class="card" id="stroom">
          <h2>${icons.bolt} Mijn huidige stroomcontract</h2>
          <p class="hint" id="stroom-samenvatting"></p>
          <div class="fields">
            <div class="row" data-installateur>
              <label>Soort contract</label>
              ${soortKnoppen("stroom-soort")}
            </div>

            <div class="row" data-installateur>
              <label for="stroom-lev">Leverancier</label>
              ${levKeuze("stroom-lev", "stroom")}
              <span class="sub" id="stroom-lev-hint"></span>
            </div>

            <div class="two" data-installateur>
              <div class="row">
                <label for="stroom-start">Mijn contract is ingegaan op</label>
                <input type="date" id="stroom-start">
              </div>
              <div class="row" id="stroom-eind-rij">
                <label for="stroom-end">Mijn contract loopt af op</label>
                <input type="date" id="stroom-end">
                <span class="sub">Alleen bij een vast contract. Variabel en dynamisch zijn maandelijks opzegbaar.</span>
                <label for="stroom-dagen" class="klein">Herinner me zoveel dagen vooraf</label>
                <input type="number" id="stroom-dagen" min="0" max="365" step="1" inputmode="numeric">
              </div>
            </div>

            <!-- vast en variabel -->
            <div id="fixed-fields" class="fields" data-installateur>
              <div class="two">
                <div class="row">
                  <label for="fx-price">All-in prijs (€ per kWh)</label>
                  <input type="number" id="fx-price" min="0" step="0.0001" inputmode="decimal">
                  <span class="sub">Inclusief energiebelasting, opslag en btw, zoals op je contract.</span>
                </div>
                <div class="row">
                  <label for="fx-feedin">Terugleververgoeding (€ per kWh)</label>
                  <input type="number" id="fx-feedin" min="0" step="0.0001" inputmode="decimal">
                  <span class="sub">Wat je krijgt voor wat je teruglevert boven je eigen verbruik.</span>
                </div>
              </div>
              <div class="row">
                <label for="fx-feedcost">Terugleverkosten (€ per kWh)</label>
                <input type="number" id="fx-feedcost" min="0" step="0.0001" inputmode="decimal">
                <span class="sub" id="fx-feedcost-hint">Wat je leverancier per teruggeleverde kWh rekent. Een vast bedrag per maand (een staffel) hoort hier niet: dat verandert niet met wat je teruglevert.</span>
              </div>
            </div>

            <!-- dynamisch -->
            <div id="dynamic-fields" class="fields" data-installateur>
              <div class="row">
                <label>Hoe vaak verandert de prijs?</label>
                <div class="segmented" id="dynamic-interval">
                  <button type="button" data-interval="hour" aria-pressed="false">
                    <strong>Per uur</strong>
                    Eén prijs per klokuur.
                  </button>
                  <button type="button" data-interval="quarter" aria-pressed="false">
                    <strong>Per kwartier</strong>
                    Vier prijzen per uur.
                  </button>
                </div>
                <span class="sub">De lengte van de blokken waarin de coach plant. Met kwartieren komt hij dichter bij het goedkoopste moment, als je leverancier ook zo afrekent.</span>
              </div>

              <div class="row">
                <label>All-in prijssensor van je leverancier</label>
                <dac-entity-picker id="dyn-allin"></dac-entity-picker>
                <span class="sub">De prijs zoals je hem betaalt. Dit is de prijs waar de coach mee rekent.</span>
              </div>
              <div class="row">
                <label>Kale marktprijs</label>
                <dac-entity-picker id="dyn-market"></dac-entity-picker>
                <span class="sub">Zonder belasting en btw, zoals de ingebouwde Nord Pool van Home Assistant. Hiermee rekent de coach je prijs na, weet hij wat teruglevering opbrengt, en neemt hij het over als je leverancier geen prijs geeft. Zonder all-in sensor rekent hij er je prijs mee uit.</span>
              </div>
              <div class="notice" id="dyn-same" hidden>
                ${icons.warning}
                <span id="dyn-same-text"></span>
              </div>
              <div class="row" id="dyn-reserve-row">
                <label>Reserveprijssensor</label>
                <dac-entity-picker id="dyn-reserve"></dac-entity-picker>
                <span class="sub">Een tweede all-in prijs voor als die van je leverancier wegvalt. Meestal niet nodig: de kale marktprijs neemt het dan al over.</span>
              </div>

              <div class="two">
                <div class="row">
                  <label for="dyn-tax">Energiebelasting (€ per kWh, zonder btw)</label>
                  <input type="number" id="dyn-tax" min="0" step="0.00001" inputmode="decimal">
                  <span class="sub" id="dyn-tax-hint"></span>
                </div>
                <div class="row">
                  <label for="dyn-vat">Btw (%)</label>
                  <input type="number" id="dyn-vat" min="0" max="100" step="1" inputmode="numeric">
                </div>
              </div>
              <div class="row">
                <label for="dyn-markup" id="dyn-markup-label">Opslag van je leverancier (€ per kWh, zonder btw)</label>
                <input type="number" id="dyn-markup" min="0" step="0.000001" inputmode="decimal">
                <span class="sub" id="dyn-markup-hint"></span>
              </div>
              <div class="two">
                <div class="row">
                  <label for="dyn-feedcost">Terugleverkosten (€ per kWh)</label>
                  <input type="number" id="dyn-feedcost" min="0" step="0.0001" inputmode="decimal">
                </div>
                <div class="row">
                  <label for="dyn-feedbonus">Vergoeding bij teruglevering (€ per kWh)</label>
                  <input type="number" id="dyn-feedbonus" step="0.0001" inputmode="decimal">
                  <span class="sub">Wat je leverancier per teruggeleverde kWh bovenop de marktprijs betaalt. Haalt hij er iets af, dan een negatief getal.</span>
                </div>
              </div>
              <label class="check" for="dyn-nettingfull">
                <input type="checkbox" id="dyn-nettingfull">
                <span><strong>Binnen salderen de hele all-in prijs terug</strong> Ook de opslag. Anders rekent de coach binnen salderen met de all-in prijs min de opslag.</span>
              </label>
              <label class="check" for="dyn-feedvat">
                <input type="checkbox" id="dyn-feedvat">
                <span><strong>Teruglevering met btw</strong> De leverancier betaalt de marktprijs voor teruglevering inclusief btw.</span>
              </label>
              <div class="two">
                <div class="row">
                  <label for="dyn-bonuspct">Bonus op teruglevering (%)</label>
                  <input type="number" id="dyn-bonuspct" min="0" max="100" step="0.1" inputmode="decimal">
                  <span class="sub">Een bonus in procenten, zoals de Zonnebonus. Leeg of 0 is geen bonus.</span>
                </div>
                <div class="row">
                  <label for="dyn-bonusbase">Over</label>
                  <select id="dyn-bonusbase">
                    <option value="market">de marktprijs</option>
                    <option value="market_plus_fee">de marktprijs plus de vergoeding</option>
                  </select>
                </div>
              </div>
              <label class="check" for="dyn-bonusdag">
                <input type="checkbox" id="dyn-bonusdag">
                <span><strong>Bonus alleen overdag</strong> Van zonsopkomst tot zonsondergang, uitgerekend voor waar het huis staat.</span>
              </label>
            </div>

            <label class="check" for="netting" data-installateur>
              <input type="checkbox" id="netting">
              <span>
                <strong>Je levert nog gesaldeerd terug</strong>
                Dan streept elke teruggeleverde kWh weg tegen een ingekochte, tot aan wat je zelf
                verbruikt, en is hij je inkoopprijs waard in plaats van je terugleververgoeding. De
                regeling loopt af op 1 januari 2027.
              </span>
            </label>

            <div class="row">
              <label>Zo komt je prijs tot stand</label>
              <div class="ob" id="opbouw"></div>
            </div>
            <div class="bevestig">
              <button type="button" class="primary vrij" id="bevestig">Ja, dit klopt</button>
              <span class="sub" id="bevestigd-zin"></span>
            </div>

            <div class="nieuw" data-installateur>
              <button type="button" data-nieuw="stroom">Ik heb een nieuw stroomcontract afgesloten</button>
              <span class="sub">Zet dit contract bij de eerdere, en begin een nieuw formulier.</span>
            </div>

            <div class="row">
              <label>Eerdere stroomcontracten</label>
              <span class="sub">Historie en rapport rekenen elke dag met de prijs van toen. Wat de coach nu doet rekent altijd met het contract hierboven.</span>
            </div>
            <div id="periods-stroom"></div>
            <div class="circuit-actions" data-installateur>
              <button type="button" data-period-add="stroom">Eerder stroomcontract toevoegen</button>
            </div>
          </div>
        </section>

        <!-- ================= gas ================= -->
        <section class="card" id="gas">
          <h2>${icons.vlam} Mijn huidige gascontract</h2>
          <p class="hint" id="gas-samenvatting"></p>
          <div class="fields">
            <div class="row" data-installateur>
              <label>Soort contract</label>
              ${soortKnoppen("gas-soort")}
            </div>
            <div class="row" data-installateur>
              <label for="gas-lev">Leverancier</label>
              ${levKeuze("gas-lev", "gas")}
              <span class="sub" id="gas-lev-hint">Mag een andere zijn dan die van je stroom.</span>
            </div>
            <div class="two" data-installateur>
              <div class="row">
                <label for="gas-start">Mijn contract is ingegaan op</label>
                <input type="date" id="gas-start">
              </div>
              <div class="row" id="gas-eind-rij">
                <label for="gas-end">Mijn contract loopt af op</label>
                <input type="date" id="gas-end">
                <label for="gas-dagen" class="klein">Herinner me zoveel dagen vooraf</label>
                <input type="number" id="gas-dagen" min="0" max="365" step="1" inputmode="numeric">
              </div>
            </div>
            <div class="row" id="gas-prijs-rij" data-installateur>
              <label for="gas-price">Gasprijs, all-in (€ per m³)</label>
              <input type="number" id="gas-price" min="0" step="0.0001" inputmode="decimal">
              <span class="sub">Inclusief energiebelasting, opslag en btw. Leeg laten als je geen gas hebt.</span>
            </div>
            <div class="row" id="gas-sensor-rij" data-installateur>
              <label>Sensor met de all-in gasprijs</label>
              <dac-entity-picker id="gas-entity"></dac-entity-picker>
              <span class="sub" id="gas-sensor-hint">Een dynamische gasprijs verandert per dag. Historie neemt de prijs van elke dag uit deze sensor.</span>
            </div>
            <div class="nieuw" data-installateur>
              <button type="button" data-nieuw="gas">Ik heb een nieuw gascontract afgesloten</button>
            </div>
            <div class="row">
              <label>Eerdere gascontracten</label>
            </div>
            <div id="periods-gas"></div>
            <div class="circuit-actions" data-installateur>
              <button type="button" data-period-add="gas">Eerder gascontract toevoegen</button>
            </div>
          </div>
        </section>

        <!-- ================= water ================= -->
        <section class="card" id="water">
          <h2>${icons.druppel} Mijn huidige waterprijs</h2>
          <p class="hint" id="water-samenvatting"></p>
          <div class="fields">
            <div class="row" data-installateur>
              <label for="water-lev">Waterbedrijf</label>
              <input type="text" id="water-lev" maxlength="60" placeholder="Bijvoorbeeld Vitens">
            </div>
            <div class="row" data-installateur>
              <label for="water-price">Waterprijs, all-in (€ per m³)</label>
              <input type="number" id="water-price" min="0" step="0.0001" inputmode="decimal">
              <span class="sub">Inclusief belasting. Leeg laten zonder watermeter.</span>
            </div>
            <div class="row">
              <label>Eerdere waterprijzen</label>
            </div>
            <div id="periods-water"></div>
            <div class="circuit-actions" data-installateur>
              <button type="button" data-period-add="water">Eerdere waterprijs toevoegen</button>
            </div>
          </div>
        </section>
      </div>

      ${saveBarHtml}
    `;
  }

  afterRender() {
    const c = () => this.draft_.contract;
    const bind = (id, apply) => {
      const el = this.$(`#${id}`);
      el.addEventListener("input", () => {
        apply(el.type === "checkbox" ? el.checked : el.value);
        this.wijziging_();
      });
      if (el.type === "checkbox" || el.tagName === "SELECT") {
        el.addEventListener("change", () => {
          apply(el.type === "checkbox" ? el.checked : el.value);
          this.wijziging_();
        });
      }
    };
    const getal = (v) => (v === "" ? 0 : Number(v) || 0);

    bind("stroom-start", (v) => (c().start = v));
    bind("stroom-end", (v) => (c().end = v));
    bind("stroom-dagen", (v) => (c().reminder_days = v === "" ? 30 : Math.max(0, Math.round(Number(v) || 0))));
    bind("gas-dagen", (v) => (this.gas_().reminder_days = v === "" ? 30 : Math.max(0, Math.round(Number(v) || 0))));
    bind("fx-price", (v) => (c().fixed.all_in_price = getal(v)));
    bind("fx-feedin", (v) => (c().fixed.feed_in_tariff = getal(v)));
    bind("fx-feedcost", (v) => (c().fixed.feed_in_costs = getal(v)));
    bind("dyn-tax", (v) => (c().dynamic.energy_tax = getal(v)));
    bind("dyn-markup", (v) => (c().dynamic.supplier_markup = getal(v)));
    bind("dyn-vat", (v) => (c().dynamic.vat_percent = getal(v)));
    bind("dyn-feedcost", (v) => (c().dynamic.feed_in_costs = getal(v)));
    bind("dyn-feedbonus", (v) => (c().dynamic.feed_in_bonus = getal(v)));
    bind("dyn-feedvat", (v) => (c().dynamic.feed_in_vat = Boolean(v)));
    bind("dyn-nettingfull", (v) => (c().dynamic.netting_full = Boolean(v)));
    bind("dyn-bonuspct", (v) => (c().dynamic.feed_in_bonus_percent = getal(v)));
    bind("dyn-bonusbase", (v) => (c().dynamic.bonus_base = v));
    bind("dyn-bonusdag", (v) => (c().dynamic.bonus_daytime = Boolean(v)));
    bind("netting", (v) => (c().netting = Boolean(v)));
    bind("gas-start", (v) => (this.gas_().start = v));
    bind("gas-end", (v) => (this.gas_().end = v));
    bind("gas-price", (v) => (this.gas_().price = getal(v)));
    bind("water-price", (v) => (this.water_().price = getal(v)));
    bind("water-lev", (v) => (this.water_().supplier = v));

    this.$("#stroom-lev").addEventListener("change", (ev) => this.kiesLeverancier_("stroom", ev.target.value));
    this.$("#gas-lev").addEventListener("change", (ev) => this.kiesLeverancier_("gas", ev.target.value));

    for (const [id, zet] of [["stroom-soort", (s) => (c().type = s)], ["gas-soort", (s) => (this.gas_().type = s)]]) {
      for (const button of this.$$(`#${id} button`)) {
        button.addEventListener("click", () => {
          zet(button.dataset.soort);
          this.wijziging_();
        });
      }
    }
    for (const button of this.$$("#dynamic-interval button")) {
      button.addEventListener("click", () => {
        c().dynamic.interval = button.dataset.interval;
        this.wijziging_();
      });
    }

    for (const [id, key] of [["dyn-allin", "all_in_entity"], ["dyn-market", "market_entity"], ["dyn-reserve", "fallback_entity"]]) {
      const picker = this.$(`#${id}`);
      picker.filter = "price";
      picker.placeholder = "Zoek een prijssensor…";
      picker.addEventListener("dac-entity-change", (ev) => {
        const d = c().dynamic;
        d[key] = ev.detail.value;
        // Met een all-in sensor is die de prijs; zonder bouwt de coach hem op
        // uit de kale marktprijs (v0.129.0: geen aparte keuze meer).
        d.source = d.all_in_entity ? "all_in" : "market";
        if (key === "fallback_entity" && ev.detail.value) d.fallback_source = "all_in";
        this.wijziging_();
      });
    }
    const gasPicker = this.$("#gas-entity");
    gasPicker.filter = "price";
    gasPicker.placeholder = "Zoek een gasprijssensor…";
    gasPicker.addEventListener("dac-entity-change", (ev) => {
      this.gas_().entity = ev.detail.value;
      this.wijziging_();
    });

    for (const knop of this.$$("[data-period-add]")) {
      knop.addEventListener("click", () => {
        const bron = knop.dataset.periodAdd;
        const lijst = this.periodsVan_(bron);
        lijst.push(bron === "stroom"
          ? { name: "", from: "", to: "", type: "fixed", supplier: "", all_in_price: 0, feed_in_tariff: 0 }
          : { name: "", from: "", to: "", price: 0 });
        this.openPeriode_ = `${bron}:${lijst.length - 1}`;
        this.paintPeriods_(bron);
        this.afterChange_();
      });
    }
    for (const knop of this.$$("[data-nieuw]")) {
      knop.addEventListener("click", () => this.nieuwContract_(knop.dataset.nieuw));
    }
    this.$("#bevestig").addEventListener("click", () => this.bevestig_());

    this.wireSaveBar_();
    this.paint_();
  }

  gas_() {
    const contract = this.draft_.contract;
    contract.gas ??= { type: "fixed", supplier: "", price: 0, entity: "", start: "", end: "", periods: [] };
    return contract.gas;
  }

  water_() {
    const contract = this.draft_.contract;
    contract.water ??= { price: 0, periods: [] };
    return contract.water;
  }

  periodsVan_(bron) {
    if (bron === "stroom") {
      const contract = this.draft_.contract;
      if (!Array.isArray(contract.periods)) contract.periods = [];
      return contract.periods;
    }
    const deel = bron === "gas" ? this.gas_() : this.water_();
    if (!Array.isArray(deel.periods)) deel.periods = [];
    return deel.periods;
  }

  /** Na elke wijziging: tekenen, de opslagbalk, en de controle opnieuw vragen. */
  wijziging_() {
    this.paintContract_();
    this.afterChange_();
    this.vraagControle_();
  }

  afterChange_() {
    this.syncSaveBar_();
  }

  /**
   * Een leverancier kiezen vult de velden voor (v0.129.0). Wat er staat wordt
   * overschreven door wat de catalogus van die leverancier weet; wat hij niet
   * weet blijft staan. Bij een dynamisch contract zoekt hij ook de sensoren op.
   */
  kiesLeverancier_(bron, id) {
    const deel = bron === "stroom" ? this.draft_.contract : this.gas_();
    deel.supplier = id;
    const l = leverancier(id);
    if (l) {
      // De soort blijft wat de klant koos: de catalogus kan een soort missen, en
      // dan zou hij een goede keuze overschrijven. Heeft de leverancier die soort
      // niet in de lijst, dan zegt de hint dat.
      const v = voorstel(id, deel.type, bron);
      if (v && bron === "stroom") {
        const doel = deel.type === "dynamic" ? deel.dynamic : deel.fixed;
        Object.assign(doel, v.velden);
        if (deel.type === "dynamic" && v.interval) deel.dynamic.interval = v.interval;
      }
      if (v && bron === "gas" && v.velden?.price !== undefined) deel.price = v.velden.price;
      const staten = this.hass_?.states;
      if (bron === "stroom" && deel.type === "dynamic") {
        const d = deel.dynamic;
        d.all_in_entity = d.all_in_entity || sensorVan(id, staten, "stroom") || "";
        d.market_entity = d.market_entity && d.market_entity !== d.all_in_entity ? d.market_entity : (nordPoolVan(staten) || "");
        d.source = d.all_in_entity ? "all_in" : "market";
      }
      if (bron === "gas" && deel.type === "dynamic") {
        deel.entity = deel.entity || sensorVan(id, staten, "gas") || "";
      }
    }
    this.paint_();
    this.afterChange_();
    this.vraagControle_();
  }

  /**
   * "Ik heb een nieuw contract afgesloten": het huidige contract bij de eerdere,
   * van de ingangsdatum tot gisteren, en een leeg formulier dat vandaag ingaat.
   * De bewoner van de eerste woning op 18-10-2026: "waarmee je het huidige
   * contract automatisch archiveert en er een nieuw (leeg) formulier komt voor
   * het nieuwe contract."
   */
  nieuwContract_(bron) {
    const nu = new Date();
    const gisteren = new Date(nu.getTime() - 86400000);
    const contract = this.draft_.contract;
    if (bron === "stroom") {
      const vast = contract.type !== "dynamic";
      this.periodsVan_("stroom").unshift({
        name: voorgesteldeNaam("stroom", contract.supplier, contract.type, contract.start, dagTekst(gisteren)),
        from: contract.start || "",
        to: dagTekst(gisteren),
        type: contract.type || "fixed",
        supplier: contract.supplier || "",
        all_in_price: vast ? Number(contract.fixed?.all_in_price) || 0 : 0,
        feed_in_tariff: vast ? Number(contract.fixed?.feed_in_tariff) || 0 : 0,
      });
      contract.supplier = "";
      contract.start = dagTekst(nu);
      contract.end = "";
      contract.fixed = { ...contract.fixed, all_in_price: 0, feed_in_tariff: 0, feed_in_costs: 0 };
      contract.dynamic = { ...contract.dynamic, supplier_markup: 0, feed_in_costs: 0, feed_in_bonus: 0,
        feed_in_bonus_percent: 0, bonus_daytime: false, feed_in_vat: false };
    } else if (bron === "gas") {
      const gas = this.gas_();
      this.periodsVan_("gas").unshift({
        name: voorgesteldeNaam("gas", gas.supplier, gas.type, gas.start, dagTekst(gisteren)),
        from: gas.start || "", to: dagTekst(gisteren), price: Number(gas.price) || 0,
      });
      Object.assign(gas, { supplier: "", start: dagTekst(nu), end: "", price: 0 });
    }
    this.paint_();
    this.afterChange_();
    this.vraagControle_();
  }

  /** De opbouw opnieuw laten uitrekenen door de coach, met het concept erbij. */
  vraagControle_() {
    clearTimeout(this.checkTimer_);
    this.checkTimer_ = setTimeout(() => this.haalControle_(), 350);
  }

  async haalControle_() {
    if (!this.hass_?.callWS || !this.draft_) return;
    const run = ++this.checkRun_;
    try {
      const vraag = { type: "domotiapp_coach/contract/check" };
      if (this.canEdit_()) vraag.contract = this.draft_.contract;
      const antwoord = await this.hass_.callWS(vraag);
      if (run !== this.checkRun_) return;
      this.check_ = antwoord;
    } catch (error) {
      if (run !== this.checkRun_) return;
      this.check_ = null;
      console.warn("[DomotiApp Coach] de opbouw kon niet worden opgehaald", error);
    }
    this.paintOpbouw_();
  }

  /** "Ja, dit klopt": eerst opslaan wat er veranderde, dan bevestigen. */
  async bevestig_() {
    if (!this.hass_?.callWS) return;
    if (this.dirty_()) {
      await this.save_();
      if (this.dirty_()) return;
    }
    try {
      const settings = await this.hass_.callWS({ type: "domotiapp_coach/contract/confirm" });
      this.saved_ = JSON.parse(JSON.stringify(settings));
      this.draft_ = JSON.parse(JSON.stringify(settings));
      this.fire("dac-settings-saved", { settings });
      this.toast_("Bevestigd", true);
    } catch (error) {
      this.toast_(`Bevestigen mislukt: ${error?.message ?? error}`, false);
    }
    this.paint_();
    this.vraagControle_();
  }

  afterSave_() {
    this.vraagControle_();
  }

  /** Wie het scherm bekijkt kan veranderen; de eerdere contracten tekenen dan opnieuw. */
  applyPermissions_() {
    super.applyPermissions_();
    if (this.draft_) for (const bron of ["stroom", "gas", "water"]) this.paintPeriods_(bron);
  }

  paint_() {
    if (!this.draft_ || !this.rendered_) return;
    for (const d of [this.draft_, this.saved_]) if (d?.contract) d.contract.periods ??= [];
    const contract = this.draft_.contract;
    contract.dynamic ??= {};
    contract.fixed ??= {};

    this.$("#stroom-lev").value = leverancier(contract.supplier) ? contract.supplier : "";
    this.$("#stroom-start").value = contract.start || "";
    this.$("#stroom-end").value = contract.end || "";
    this.$("#stroom-dagen").value = contract.reminder_days ?? 30;
    this.$("#netting").checked = Boolean(contract.netting);
    this.$("#fx-price").value = contract.fixed.all_in_price || "";
    this.$("#fx-feedin").value = contract.fixed.feed_in_tariff || "";
    this.$("#fx-feedcost").value = contract.fixed.feed_in_costs || "";
    const d = contract.dynamic;
    this.$("#dyn-allin").value = d.source === "all_in" ? d.all_in_entity ?? "" : (d.all_in_entity ?? "");
    this.$("#dyn-market").value = d.market_entity ?? "";
    this.$("#dyn-reserve").value = d.fallback_entity ?? "";
    this.$("#dyn-tax").value = d.energy_tax ?? "";
    this.$("#dyn-markup").value = d.supplier_markup ?? "";
    this.$("#dyn-vat").value = d.vat_percent ?? "";
    this.$("#dyn-feedcost").value = d.feed_in_costs ?? "";
    this.$("#dyn-feedbonus").value = d.feed_in_bonus ?? "";
    this.$("#dyn-feedvat").checked = Boolean(d.feed_in_vat);
    this.$("#dyn-nettingfull").checked = Boolean(d.netting_full);
    this.$("#dyn-bonuspct").value = d.feed_in_bonus_percent || "";
    this.$("#dyn-bonusbase").value = d.bonus_base === "market_plus_fee" ? "market_plus_fee" : "market";
    this.$("#dyn-bonusdag").checked = Boolean(d.bonus_daytime);

    const gas = this.gas_();
    this.$("#gas-lev").value = leverancier(gas.supplier) ? gas.supplier : "";
    this.$("#gas-start").value = gas.start || "";
    this.$("#gas-end").value = gas.end || "";
    this.$("#gas-dagen").value = gas.reminder_days ?? 30;
    this.$("#gas-price").value = gas.price || "";
    this.$("#gas-entity").value = gas.entity || "";
    this.$("#water-price").value = this.water_().price || "";
    this.$("#water-lev").value = this.water_().supplier || "";

    this.paintContract_();
    for (const bron of ["stroom", "gas", "water"]) this.paintPeriods_(bron);
    this.paintOpbouw_();
    if (!this.check_) this.vraagControle_();
  }

  /** Wat er zichtbaar is hangt af van de soort, en de hints van de leverancier. */
  paintContract_() {
    const contract = this.draft_.contract;
    const d = contract.dynamic ?? {};
    const dynamic = contract.type === "dynamic";
    const vast = contract.type === "fixed";

    for (const button of this.$$("#stroom-soort button")) {
      button.setAttribute("aria-pressed", String(button.dataset.soort === (contract.type || "fixed")));
    }
    this.$("#fixed-fields").style.display = dynamic ? "none" : "";
    this.$("#dynamic-fields").style.display = dynamic ? "" : "none";
    this.$("#stroom-eind-rij").style.display = vast ? "" : "none";
    for (const button of this.$$("#dynamic-interval button")) {
      button.setAttribute("aria-pressed", String(button.dataset.interval === (d.interval ?? "hour")));
    }
    this.$("#dyn-reserve-row").style.display = d.fallback_entity ? "" : "none";

    // De samenvatting bovenaan: wat voor contract, bij wie, sinds wanneer, tot wanneer.
    const l = leverancier(contract.supplier);
    const delen = [`${(SOORT_NAAM[contract.type] ?? "vast").replace(/^./, (x) => x.toUpperCase())} contract`];
    if (l) delen[0] += ` bij ${l.naam}`;
    if (contract.start) delen.push(`ingegaan op ${datumLang(contract.start)}`);
    if (vast && contract.end) delen.push(`loopt af op ${datumLang(contract.end)}`);
    this.$("#stroom-samenvatting").textContent = `${delen.join(", ")}.`;

    // Waar het voorstel vandaan kwam.
    const v = l ? voorstel(l.id, contract.type, "stroom") : null;
    const hint = this.$("#stroom-lev-hint");
    if (l && v) {
      hint.innerHTML = `${esc(v.uitleg)}${v.terug ? ` ${esc(v.terug)}` : ""} Ingevuld uit de gegevens van ${esc(l.naam)}, nagekeken op ${esc(datumLang(v.peildatum))}${
        v.bronnen.length ? ` (<a href="${esc(v.bronnen[0])}" target="_blank" rel="noopener">bron</a>)` : ""}. Kijk ze na en bevestig onderaan.${
        v.onzeker.length ? ` <strong>Niet zeker:</strong> ${v.onzeker.map(esc).join(" ")}` : ""}`;
    } else if (l) {
      hint.textContent = `${l.naam} heeft geen ${SOORT_NAAM[contract.type] ?? ""} stroomcontract in de lijst. Vul de bedragen van je contract zelf in.`;
    } else {
      hint.textContent = "Staat je leverancier er niet tussen? Vul de bedragen van je contract zelf in.";
    }

    const namen = namenVan(contract.supplier, contract.type);
    this.$("#dyn-markup-label").textContent = `${namen.opslag || "Opslag van je leverancier"} (€ per kWh, zonder btw)`;
    const markup = Number(d.supplier_markup) || 0;
    const vat = Number(d.vat_percent) || 0;
    this.$("#dyn-markup-hint").textContent = markup
      ? `Met btw € ${(markup * (1 + vat / 100)).toLocaleString("nl-NL", { minimumFractionDigits: 4, maximumFractionDigits: 4 })} per kWh. Bij salderen komt dit bedrag niet terug: het hangt aan wat je afneemt.`
      : "Wat je leverancier per kWh bovenop de marktprijs rekent, zonder btw.";
    const jaar = new Date().getFullYear();
    const eb = belastingStroom(jaar);
    this.$("#dyn-tax-hint").textContent = eb !== null
      ? `In ${jaar} € ${eb.toLocaleString("nl-NL", { minimumFractionDigits: 5 })} zonder btw. Verandert elk jaar op 1 januari.`
      : "Verandert elk jaar op 1 januari; kijk het na op je jaarnota.";

    // Dezelfde sensor twee keer laat de coach het marktveld leeg (`_prices` in
    // coach.py), en tot v0.128.2 stond dat alleen in de kleine letters erboven.
    // In de eerste woning op 18-10-2026 stond hij zo, met salderen uit, en
    // handelde de batterij nooit.
    const zelfde = Boolean(d.market_entity) && d.market_entity === d.all_in_entity;
    this.$("#dyn-same").hidden = !zelfde;
    this.$("#dyn-same-text").textContent = !zelfde ? "" : salderen(contract, new Date())
      ? "Dit is dezelfde sensor als de all-in prijs, en die telt niet als marktprijs. Zolang je saldeert rekent de coach de terugleverprijs uit de all-in prijs; daarna heeft hij een kale marktprijs nodig, zoals de ingebouwde Nord Pool."
      : "Dit is dezelfde sensor als de all-in prijs, en die telt niet als marktprijs. Zo kent de coach je terugleverprijs niet, en kan een thuisbatterij niet handelen. Kies een kale marktprijs, zoals de ingebouwde Nord Pool.";

    // Gas.
    const gas = this.gas_();
    const gasType = gas.type || "fixed";
    for (const button of this.$$("#gas-soort button")) {
      button.setAttribute("aria-pressed", String(button.dataset.soort === gasType));
    }
    this.$("#gas-eind-rij").style.display = gasType === "fixed" ? "" : "none";
    this.$("#gas-prijs-rij").style.display = gasType === "dynamic" ? "none" : "";
    this.$("#gas-sensor-rij").style.display = gasType === "dynamic" ? "" : "none";
    const gl = leverancier(gas.supplier);
    const gdelen = [`${(SOORT_NAAM[gasType] ?? "vast").replace(/^./, (x) => x.toUpperCase())} contract`];
    if (gl) gdelen[0] += ` bij ${gl.naam}`;
    if (gas.start) gdelen.push(`ingegaan op ${datumLang(gas.start)}`);
    if (gasType === "fixed" && gas.end) gdelen.push(`loopt af op ${datumLang(gas.end)}`);
    if (gasType !== "dynamic" && Number(gas.price) > 0) gdelen.push(`${euroTekst(gas.price)} per m³`);
    this.$("#gas-samenvatting").textContent = `${gdelen.join(", ")}.`;
    // Water (v0.130.1): het waterbedrijf en de prijs in een zin, voor wie de
    // velden niet ziet.
    const water = this.water_();
    const wdelen = [water.supplier ? `Bij ${water.supplier}` : "", Number(water.price) > 0 ? `${euroTekst(water.price)} per m³` : ""].filter(Boolean);
    this.$("#water-samenvatting").textContent = wdelen.length ? `${wdelen.join(", ")}.` : "Nog geen waterprijs ingevuld.";
    const gv = gl ? voorstel(gl.id, gasType, "gas") : null;
    this.$("#gas-lev-hint").textContent = gv
      ? `${gv.uitleg} Uit de gegevens van ${gl.naam}, nagekeken op ${datumLang(gv.peildatum)}.`
      : "Mag een andere zijn dan die van je stroom.";
  }

  /** De eerdere contracten van een bron, een per rij. */
  paintPeriods_(bron) {
    const host = this.$(`#periods-${bron}`);
    if (!host) return;
    const lijst = this.periodsVan_(bron);
    if (!this.canEdit_()) {
      host.innerHTML = periodesLezen(bron, lijst);
      return;
    }
    const veld = (i, key, type, extra, waarde) =>
      `<input type="${type}" data-period-field="${key}" data-index="${i}" ${extra} value="${esc(waarde)}">`;
    const getal = 'min="0" step="0.0001" inputmode="decimal"';
    host.innerHTML = lijst.map((p, i) => {
      const voorbeeld = { stroom: "Bijvoorbeeld Zonneplan Elektra 2026", gas: "Bijvoorbeeld Delta Gas 07/26 tot 06/27", water: "Bijvoorbeeld Waterbedrijf 2025" }[bron];
      const kop = `
        <div class="row"><label>Naam</label>${veld(i, "name", "text", `maxlength="80" placeholder="${voorbeeld}"`, p.name ?? "")}</div>
        <div class="two">
          <div class="row"><label>Van</label>${veld(i, "from", "date", "", p.from)}</div>
          <div class="row"><label>Tot</label>${veld(i, "to", "date", "", p.to)}</div>
        </div>`;
      let prijzen;
      if (bron === "stroom") {
        const naam = leverancier(p.supplier)?.naam;
        const wat = `${(SOORT_NAAM[p.type] ?? "vast").replace(/^./, (x) => x.toUpperCase())}${naam ? ` bij ${esc(naam)}` : ""}`;
        prijzen = p.type === "dynamic"
          ? `<p class="sub">${wat}: Historie neemt de prijzen van toen uit de prijssensor.</p>`
          : `<p class="sub">${wat}</p>
            <div class="two">
              <div class="row"><label>Stroom, all-in (€ per kWh)</label>${veld(i, "all_in_price", "number", getal, p.all_in_price || "")}</div>
              <div class="row"><label>Terugleververgoeding (€ per kWh)</label>${veld(i, "feed_in_tariff", "number", getal, p.feed_in_tariff || "")}</div>
            </div>`;
      } else {
        prijzen = `<div class="row"><label>${bron === "gas" ? "Gas" : "Water"}, all-in (€ per m³)</label>${veld(i, "price", "number", getal, p.price || "")}</div>`;
      }
      // Ingeklapt een regel, zoals een lijst van contracten in de app van een
      // meter (19-10-2026): naam of leverancier, en van wanneer tot wanneer.
      const titel = p.name || leverancier(p.supplier)?.naam || "Eerder contract";
      const wanneer = p.from || p.to ? `${kortDatum(p.from) || "?"} tot ${kortDatum(p.to) || "nu"}` : "nog geen datums";
      const open = this.openPeriode_ === `${bron}:${i}` ? " open" : "";
      return `
        <details class="circuit period" data-period="${i}"${open}>
          <summary><span class="p-naam">${esc(titel)}</span><span class="p-wanneer">${esc(wanneer)}</span></summary>
          ${kop}
          ${prijzen}
          <div class="circuit-actions">
            <button type="button" class="remove" data-period-remove="${i}">Weghalen</button>
          </div>
        </details>`;
    }).join("");
    // Wat openstaat blijft open als er opnieuw getekend wordt.
    for (const blok of host.querySelectorAll("details[data-period]")) {
      blok.addEventListener("toggle", () => {
        if (blok.open) this.openPeriode_ = `${bron}:${blok.dataset.period}`;
        else if (this.openPeriode_ === `${bron}:${blok.dataset.period}`) this.openPeriode_ = null;
      });
    }
    for (const el of host.querySelectorAll("[data-period-field]")) {
      const p = lijst[Number(el.dataset.index)];
      const key = el.dataset.periodField;
      el.addEventListener("input", () => {
        p[key] = el.type === "number" ? Number(el.value) || 0 : el.value;
        this.afterChange_();
      });
    }
    for (const knop of host.querySelectorAll("[data-period-remove]")) {
      knop.addEventListener("click", () => {
        lijst.splice(Number(knop.dataset.periodRemove), 1);
        this.paintPeriods_(bron);
        this.afterChange_();
      });
    }
  }

  /** De opbouw van de coach, en of hij bevestigd is. */
  paintOpbouw_() {
    if (!this.rendered_ || !this.draft_) return;
    const contract = this.draft_.contract;
    this.$("#opbouw").innerHTML = opbouwHtml(this.check_, namenVan(contract.supplier, contract.type));
    const zin = bevestigdZin(this.check_);
    this.$("#bevestigd-zin").textContent = this.dirty_() ? "Je wijzigingen worden eerst opgeslagen." : zin;
    this.$("#bevestig").hidden = Boolean(this.check_?.bevestigd) && !this.dirty_();
  }
}

DacViewContract.css = /* css */ `
  ${editorCss}
  ${opbouwCss}

  .segmented.drie { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  @media (max-width: 720px) { .segmented.drie { grid-template-columns: minmax(0, 1fr); } }
  select {
    width: 100%; min-height: 44px; padding: 10px 12px; border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border-hi); background: rgba(var(--dac-veil),0.04); color: var(--dac-ink);
    font: inherit; font-size: 14px; color-scheme: var(--dac-scheme);
  }
  select option { background: var(--dac-bg-raise); color: var(--dac-ink); }
  .sub a { color: var(--dac-accent-hi); }

  /* De bewoner leest (v0.130.1): wat de installateur kiest is er niet. */
  :host([readonly]) [data-installateur] { display: none !important; }
  .bewoner-uitleg { display: none; }
  :host([readonly]) .bewoner-uitleg { display: block; }
  .period.lezen { gap: 4px; }
  .period.lezen .p-kop { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; font-size: 14px; color: var(--dac-ink); }
  .period.lezen .p-naam { font-weight: 600; min-width: 0; overflow-wrap: anywhere; }
  .period.lezen .p-wanneer { margin-left: auto; font-size: 12.5px; color: var(--dac-ink-2); white-space: nowrap; }
  .sub.geen { margin: 0 0 12px; }
  label.klein { margin-top: 6px; font-size: 12.5px; font-weight: 500; color: var(--dac-ink-2); }

  .bevestig, .nieuw { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px; }
  .bevestig[hidden], .nieuw[hidden] { display: none; }
  .bevestig button, .nieuw button {
    font: inherit; font-size: 14px; padding: 10px 16px; border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.04); color: var(--dac-ink); cursor: pointer;
  }
  .bevestig button.primary { background: var(--dac-accent); border-color: var(--dac-accent); color: var(--dac-on-accent, #fff); font-weight: 600; }
  .bevestig button[hidden] { display: none; }

  /* ---- eerdere contracten ---- */
  .circuit {
    padding: 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(var(--dac-veil),0.022);
    display: grid;
    gap: 12px;
    margin-bottom: 12px;
  }
  .circuit .sub { margin: 0; }
  details.period > summary {
    display: flex; justify-content: space-between; align-items: baseline; gap: 10px; cursor: pointer;
    list-style: none; font-size: 14px; color: var(--dac-ink);
  }
  details.period > summary::-webkit-details-marker { display: none; }
  details.period > summary::after { content: "›"; color: var(--dac-ink-3); margin-left: 6px; transition: transform 150ms ease; }
  details.period[open] > summary::after { transform: rotate(90deg); }
  details.period > summary .p-naam { font-weight: 600; min-width: 0; overflow-wrap: anywhere; }
  details.period > summary .p-wanneer { margin-left: auto; font-size: 12.5px; color: var(--dac-ink-2); white-space: nowrap; }
  details.period:not([open]) { gap: 0; }
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
`;

define("dac-view-contract", DacViewContract);
