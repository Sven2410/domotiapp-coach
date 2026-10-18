/**
 * Contract -- wat de stroom kost, nu en vroeger.
 *
 * Stond tot v0.114.0 onder Installatie. De eigenaar op 08-10-2026: "sommige
 * dingen kunnen van installatie naar instellingen of andersom, het moet beter
 * gecategoriseerd worden." Installatie is nu hoe het huis gemeten wordt en wat
 * het aankan; wat het kost is een eigen onderwerp, en alleen de installateur
 * ziet het.
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
import { salderen } from "../geld.js";

const euro = (v) =>
  Number(v ?? 0).toLocaleString("nl-NL", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

class DacViewContract extends DacEditorElement {
  static sections = ["contract"];

  render() {
    return `
      <div class="wrap">
        <header class="intro">
          <div class="eyebrow">Contract</div>
          <h1>Wat je stroom kost</h1>
          <p>Hier staat met welke prijzen de coach rekent: je contract van nu, en wat je eerder had voor de historie en het rapport.</p>
        </header>

        ${adminNoticeHtml}

        <section class="card">
          <h2>${icons.euro} Contract en prijzen</h2>
          <p class="hint">Waar de energieprijs op het overzicht vandaan komt.</p>
          <div class="fields">
            <div class="row">
              <label>Soort contract</label>
              <div class="segmented" id="contract-type">
                <button type="button" data-type="fixed" aria-pressed="false">
                  <strong>Vast</strong>
                  Eén prijs die je hele contractperiode geldt.
                </button>
                <button type="button" data-type="dynamic" aria-pressed="false">
                  <strong>Dynamisch</strong>
                  Een prijs die per uur of per kwartier meebeweegt met de markt.
                </button>
              </div>
            </div>

            <label class="check" for="netting">
              <input type="checkbox" id="netting">
              <span>
                <strong>Je levert nog gesaldeerd terug</strong>
                Dan streept elke teruggeleverde kWh weg tegen een ingekochte, en is hij dus
                precies je inkoopprijs waard in plaats van je terugleververgoeding. De coach
                rekent daar dan mee, en dat verandert wat het waard is om je eigen zon te
                gebruiken. De regeling loopt af op 1 januari 2027.
              </span>
            </label>

            <div class="two">
              <div class="row">
                <label for="gas-price">Gasprijs (€ per m³)</label>
                <input type="number" id="gas-price" min="0" step="0.001" inputmode="decimal">
                <span class="sub">All-in, voor de historie en het rapport. Leeg laten als je geen gas hebt.</span>
              </div>
              <div class="row">
                <label for="water-price">Waterprijs (€ per m³)</label>
                <input type="number" id="water-price" min="0" step="0.001" inputmode="decimal">
                <span class="sub">All-in, inclusief belasting. Leeg laten zonder watermeter.</span>
              </div>
            </div>

            <!-- vast -->
            <div id="fixed-fields" class="fields">
              <div class="two">
                <div class="row">
                  <label for="fx-price">All-in prijs (€ per kWh)</label>
                  <input type="number" id="fx-price" min="0" step="0.001" inputmode="decimal">
                  <span class="sub">Inclusief energiebelasting, opslag en btw.</span>
                </div>
                <div class="row">
                  <label for="fx-feedin">Terugleververgoeding (€ per kWh)</label>
                  <input type="number" id="fx-feedin" min="0" step="0.001" inputmode="decimal">
                  <span class="sub">Wat je krijgt voor wat je teruglevert. Zonder salderen (vanaf 2027) is dat bij de grote leveranciers ongeveer een kwart cent: 0,0025.</span>
                </div>
              </div>
              <div class="row">
                <label for="fx-feedcost">Terugleverkosten (€ per kWh)</label>
                <input type="number" id="fx-feedcost" min="0" step="0.001" inputmode="decimal">
                <span class="sub">Wat je leverancier rekent over wat je teruglevert.</span>
              </div>
            </div>

            <!-- dynamisch -->
            <div id="dynamic-fields" class="fields">
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
                <span class="sub">Kijk op je contract of in de app van je leverancier. Dit is de lengte van de blokken waarin de coach straks plant. Met kwartieren komt hij dichter bij het goedkoopste moment, maar alleen als je leverancier ook zo afrekent.</span>
              </div>

              <div class="row">
                <label>Waar komt de prijs vandaan?</label>
                <div class="segmented" id="dynamic-source">
                  <button type="button" data-source="all_in" aria-pressed="false">
                    <strong>All-in prijs als entiteit</strong>
                    Eén sensor die de prijs al compleet levert.
                  </button>
                  <button type="button" data-source="market" aria-pressed="false">
                    <strong>Zelf opbouwen</strong>
                    Marktprijs uit een sensor, de rest vul je hier in.
                  </button>
                </div>
              </div>

              <div id="dyn-allin-row">
                <div class="row">
                  <label>All-in prijssensor</label>
                  <dac-entity-picker id="dyn-allin"></dac-entity-picker>
                  <span class="sub">Deze prijs wordt ongewijzigd overgenomen.</span>
                </div>
                <div class="row">
                  <label>Marktprijssensor (voor teruglevering)</label>
                  <dac-entity-picker id="dyn-market-feed"></dac-entity-picker>
                  <span class="sub">
                    De kale marktprijs, zonder belasting en btw. Dit is wat teruglevering
                    opbrengt, en in een all-in prijs zit die niet meer. Vul je hem in, dan
                    kan de coach uitrekenen wanneer het goedkoper is om je eigen zon te
                    gebruiken dan om op een goedkoop uur te wachten. Laat je hem leeg, dan
                    laadt hij op zon alleen als de zon het grotendeels zelf dekt. Het moet
                    een andere sensor zijn dan de all-in sensor: dezelfde sensor twee keer
                    telt niet, want een all-in prijs is geen marktprijs.
                  </span>
                </div>
                <div class="notice" id="dyn-same" hidden>
                  ${icons.warning}
                  <span id="dyn-same-text"></span>
                </div>
              </div>

              <div class="notice" id="dyn-missing" hidden>
                ${icons.warning}
                <span id="dyn-missing-text"></span>
              </div>

              <div id="dyn-market-fields" class="fields">
                <div class="row">
                  <label>Marktprijssensor</label>
                  <dac-entity-picker id="dyn-market"></dac-entity-picker>
                  <span class="sub">De kale marktprijs, zonder belasting en btw.</span>
                </div>
                <div class="row">
                  <span class="sub" id="dyn-formula"></span>
                </div>
              </div>

              <!-- De reserve (v0.101.3). De eigenaar op 29-09-2026, toen Frank
                   Energie eruit lag: "ik heb ook Nord Pool draaien, dat wil ik
                   als fallback hebben." Zie _prijsbron in coach.py. -->
              <div class="row">
                <label>Reserveprijssensor</label>
                <dac-entity-picker id="dyn-reserve"></dac-entity-picker>
                <span class="sub">
                  Optioneel. Geeft je prijssensor geen prijs, bijvoorbeeld omdat de integratie van je
                  leverancier stuk is, dan rekent de coach met deze. Zodra je eigen sensor weer
                  prijzen heeft, rekent hij weer daarmee. De ingebouwde Nord Pool van Home Assistant
                  kan hier ook: die prijzen haalt de coach zelf op.
                </span>
              </div>
              <div class="row" id="dyn-reserve-soort-row">
                <label>Wat geeft de reserve?</label>
                <div class="segmented" id="dyn-reserve-soort">
                  <button type="button" data-reserve="market" aria-pressed="false">
                    <strong>Kale marktprijs</strong>
                    Zoals Nord Pool. De coach rekent er belasting, opslag en btw bij.
                  </button>
                  <button type="button" data-reserve="all_in" aria-pressed="false">
                    <strong>All-in prijs</strong>
                    Al compleet, zoals de sensor van een leverancier.
                  </button>
                </div>
              </div>

              <div class="row" id="dyn-tax-row">
                <label for="dyn-tax">Energiebelasting (€ per kWh)</label>
                <input type="number" id="dyn-tax" min="0" step="0.0001" inputmode="decimal">
                <span class="sub">Wat de overheid per kWh heft. Dit tarief verandert elk jaar op 1 januari, dus kijk het na op je jaarnota.</span>
              </div>

              <!-- De opslag en de btw staan buiten dat blok, want ze zijn ook
                   nodig bij een all-in sensor. Salderen streept de
                   energiebelasting weg tegen die bij afname, maar de opslag
                   niet: die betaal je per ingekochte kWh en krijg je nergens
                   terug. Zonder dit veld zou daar een standaardwaarde voor
                   gebruikt worden die niemand heeft ingevuld. -->
              <div class="two">
                <div class="row">
                  <label for="dyn-markup">Opslag leverancier (€ per kWh)</label>
                  <input type="number" id="dyn-markup" min="0" step="0.0001" inputmode="decimal">
                  <span class="sub" id="dyn-markup-hint"></span>
                </div>
                <div class="row">
                  <label for="dyn-vat">Btw (%)</label>
                  <input type="number" id="dyn-vat" min="0" max="100" step="1" inputmode="numeric">
                </div>
              </div>

              <div class="two">
                <div class="row">
                  <label for="dyn-feedcost">Terugleverkosten (€ per kWh)</label>
                  <input type="number" id="dyn-feedcost" min="0" step="0.001" inputmode="decimal">
                  <span class="sub">Wat je leverancier rekent over wat je teruglevert.</span>
                </div>
                <div class="row">
                  <label for="dyn-feedbonus">Verkoopvergoeding (€ per kWh)</label>
                  <input type="number" id="dyn-feedbonus" step="0.001" inputmode="decimal">
                  <span class="sub">Wat je leverancier bovenop de marktprijs betaalt voor wat je teruglevert. Verschilt per leverancier: de een geeft 2 cent, de ander niets, en er zijn er die er 2 cent afhalen; dan vul je een negatief getal in.</span>
                </div>
              </div>
            </div>

            <div class="row">
              <label>Eerdere contracten</label>
              <span class="sub">
                Ben je van leverancier of van contract gewisseld? Zet hier per contract van wanneer
                tot wanneer het gold en wat het kostte. Historie en rapport rekenen dan elke dag
                met de prijs van toen. Wat de coach nu doet rekent altijd met het contract hierboven.
              </span>
            </div>
            <div id="periods"></div>
            <div class="circuit-actions">
              <button type="button" id="period-add">Eerder contract toevoegen</button>
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

    bind("gas-price", (v) => (this.draft_.contract.gas_price = Number(v) || 0));
    bind("water-price", (v) => (this.draft_.contract.water_price = Number(v) || 0));
    bind("fx-price", (v) => (this.draft_.contract.fixed.all_in_price = Number(v)));
    bind("fx-feedin", (v) => (this.draft_.contract.fixed.feed_in_tariff = Number(v)));
    bind("fx-feedcost", (v) => (this.draft_.contract.fixed.feed_in_costs = Number(v)));
    bind("dyn-tax", (v) => (this.draft_.contract.dynamic.energy_tax = Number(v)));
    bind("dyn-markup", (v) => (this.draft_.contract.dynamic.supplier_markup = Number(v)));
    bind("dyn-vat", (v) => (this.draft_.contract.dynamic.vat_percent = Number(v)));
    bind("dyn-feedcost", (v) => (this.draft_.contract.dynamic.feed_in_costs = Number(v)));
    bind("dyn-feedbonus", (v) => (this.draft_.contract.dynamic.feed_in_bonus = Number(v) || 0));

    this.$("#period-add").addEventListener("click", () => {
      this.periods_().push({ from: "", to: "", all_in_price: 0, feed_in_tariff: 0, gas_price: 0, water_price: 0 });
      this.paintPeriods_();
      this.afterChange_();
    });

    this.$("#netting").addEventListener("change", (ev) => {
      this.draft_.contract.netting = ev.target.checked;
      // De waarschuwing bij het marktveld hangt ervan af.
      this.paintContract_();
      this.afterChange_();
    });

    for (const button of this.$$("#contract-type button")) {
      button.addEventListener("click", () => {
        this.draft_.contract.type = button.dataset.type;
        this.paintContract_();
        this.afterChange_();
      });
    }

    for (const button of this.$$("#dynamic-source button")) {
      button.addEventListener("click", () => {
        this.draft_.contract.dynamic.source = button.dataset.source;
        this.paintContract_();
        this.afterChange_();
      });
    }

    for (const button of this.$$("#dyn-reserve-soort button")) {
      button.addEventListener("click", () => {
        this.draft_.contract.dynamic.fallback_source = button.dataset.reserve;
        this.paintContract_();
        this.afterChange_();
      });
    }

    for (const button of this.$$("#dynamic-interval button")) {
      button.addEventListener("click", () => {
        this.draft_.contract.dynamic.interval = button.dataset.interval;
        this.paintContract_();
        this.afterChange_();
      });
    }

    for (const [id, key] of [
      ["dyn-allin", "all_in_entity"],
      ["dyn-market", "market_entity"],
      ["dyn-market-feed", "market_entity"],
      ["dyn-reserve", "fallback_entity"],
    ]) {
      const picker = this.$(`#${id}`);
      picker.filter = "price";
      picker.placeholder = "Zoek een prijssensor…";
      picker.addEventListener("dac-entity-change", (ev) => {
        this.draft_.contract.dynamic[key] = ev.detail.value;
        this.paintContract_();
        this.afterChange_();
      });
    }

    this.wireSaveBar_();
    this.paint_();
  }

  afterChange_() {
    this.paintHints_();
    this.syncSaveBar_();
  }

  paint_() {
    if (!this.draft_ || !this.rendered_) return;
    // Zoals in Installatie: de lijst die dit scherm tekent ook in wat er
    // opgeslagen staat, anders staat de balk aan zonder dat er iets veranderde.
    for (const d of [this.draft_, this.saved_]) if (d?.contract) d.contract.periods ??= [];
    const contract = this.draft_.contract;

    this.$("#netting").checked = Boolean(this.draft_.contract.netting);
    this.$("#gas-price").value = contract.gas_price || "";
    this.$("#water-price").value = contract.water_price || "";
    this.$("#fx-price").value = contract.fixed.all_in_price;
    this.$("#fx-feedin").value = contract.fixed.feed_in_tariff;
    this.$("#fx-feedcost").value = contract.fixed.feed_in_costs;
    this.$("#dyn-tax").value = contract.dynamic.energy_tax;
    this.$("#dyn-markup").value = contract.dynamic.supplier_markup;
    this.$("#dyn-vat").value = contract.dynamic.vat_percent;
    this.$("#dyn-feedcost").value = contract.dynamic.feed_in_costs;
    this.$("#dyn-feedbonus").value = contract.dynamic.feed_in_bonus ?? 0;
    this.$("#dyn-allin").value = contract.dynamic.all_in_entity ?? "";
    this.$("#dyn-market").value = contract.dynamic.market_entity ?? "";
    this.$("#dyn-reserve").value = contract.dynamic.fallback_entity ?? "";
    this.onFeed_();

    this.paintPeriods_();
    this.paintContract_();
    this.paintHints_();
    this.syncSaveBar_();
  }

  /** De eerdere contracten in het klad, altijd als lijst. */
  periods_() {
    const contract = this.draft_.contract;
    if (!Array.isArray(contract.periods)) contract.periods = [];
    return contract.periods;
  }

  /** Eén eerder contract per rij: van, tot, stroom, teruglevering, gas. */
  paintPeriods_() {
    const host = this.$("#periods");
    if (!host) return;
    const lijst = this.periods_();
    const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
    const veld = (i, key, type, extra, waarde) =>
      `<input type="${type}" data-period-field="${key}" data-index="${i}" ${extra} value="${esc(waarde)}">`;
    host.innerHTML = lijst
      .map(
        (p, i) => `
      <div class="circuit period" data-period="${i}">
        <div class="two">
          <div class="row"><label>Van</label>${veld(i, "from", "date", "", p.from)}</div>
          <div class="row"><label>Tot</label>${veld(i, "to", "date", "", p.to)}</div>
        </div>
        <div class="two">
          <div class="row"><label>Stroom, all-in (€ per kWh)</label>${veld(i, "all_in_price", "number", 'min="0" step="0.001" inputmode="decimal"', p.all_in_price || "")}</div>
          <div class="row"><label>Terugleververgoeding (€ per kWh)</label>${veld(i, "feed_in_tariff", "number", 'min="0" step="0.001" inputmode="decimal"', p.feed_in_tariff || "")}</div>
        </div>
        <div class="two">
          <div class="row"><label>Gas (€ per m³)</label>${veld(i, "gas_price", "number", 'min="0" step="0.001" inputmode="decimal"', p.gas_price || "")}</div>
          <div class="row"><label>Water (€ per m³)</label>${veld(i, "water_price", "number", 'min="0" step="0.001" inputmode="decimal"', p.water_price || "")}</div>
        </div>
        <div class="circuit-actions">
          <button type="button" class="remove" data-period-remove="${i}">Contract weghalen</button>
        </div>
      </div>`
      )
      .join("");
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
        this.paintPeriods_();
        this.afterChange_();
      });
    }
  }

  paintContract_() {
    const contract = this.draft_.contract;
    const dynamic = contract.type === "dynamic";

    this.$("#fixed-fields").style.display = dynamic ? "none" : "";
    this.$("#dynamic-fields").style.display = dynamic ? "" : "none";
    for (const button of this.$$("#contract-type button")) {
      button.setAttribute("aria-pressed", String(button.dataset.type === contract.type));
    }

    const source = contract.dynamic.source;
    for (const button of this.$$("#dynamic-source button")) {
      button.setAttribute("aria-pressed", String(button.dataset.source === source));
    }

    const interval = contract.dynamic.interval ?? "hour";
    for (const button of this.$$("#dynamic-interval button")) {
      button.setAttribute("aria-pressed", String(button.dataset.interval === interval));
    }
    // With an all-in entity the tax, markup and VAT fields are not just unused,
    // they are misleading: the price already contains them.
    this.$("#dyn-allin-row").style.display = source === "all_in" ? "" : "none";
    this.$("#dyn-market-feed").value = contract.dynamic.market_entity ?? "";
    // Dezelfde sensor twee keer laat de coach het marktveld leeg (`_prices` in
    // coach.py), en tot v0.128.2 stond dat alleen in de kleine letters erboven.
    // In de eerste woning op 18-10-2026 stond hij zo, met salderen uit, en
    // handelde de batterij nooit.
    const zelfde = source === "all_in" && Boolean(contract.dynamic.market_entity)
      && contract.dynamic.market_entity === contract.dynamic.all_in_entity;
    this.$("#dyn-same").hidden = !zelfde;
    this.$("#dyn-same-text").textContent = !zelfde ? "" : salderen(contract, new Date())
      ? "Dit is dezelfde sensor als de all-in prijs, en die telt niet als marktprijs. Zolang je saldeert rekent de coach de terugleverprijs uit de all-in prijs; daarna heeft hij een kale marktprijs nodig, zoals de ingebouwde Nord Pool."
      : "Dit is dezelfde sensor als de all-in prijs, en die telt niet als marktprijs. Zo kent de coach je terugleverprijs niet, en kan een thuisbatterij niet handelen. Kies een kale marktprijs, zoals de ingebouwde Nord Pool.";
    this.$("#dyn-market-fields").style.display = source === "market" ? "" : "none";
    // De reserve: wat voor prijs hij geeft, alleen als er een is. De
    // energiebelasting is nodig bij een marktprijs, van de eigen bron of van de
    // reserve.
    const reserve = contract.dynamic.fallback_entity ?? "";
    const reserveSoort = contract.dynamic.fallback_source === "all_in" ? "all_in" : "market";
    this.$("#dyn-reserve-soort-row").style.display = reserve ? "" : "none";
    for (const button of this.$$("#dyn-reserve-soort button")) {
      button.setAttribute("aria-pressed", String(button.dataset.reserve === reserveSoort));
    }
    this.$("#dyn-tax-row").style.display =
      source === "market" || (reserve && reserveSoort === "market") ? "" : "none";
    // De opslag doet er bij allebei de bronnen toe, maar om een andere reden.
    this.$("#dyn-markup-hint").textContent =
      source === "market"
        ? "Wat je leverancier per kWh bovenop de marktprijs rekent. Zit in je inkoopprijs, en telt niet mee in wat teruglevering opbrengt."
        : "Wat je leverancier per kWh bovenop de marktprijs rekent. Je all-in sensor kent dit bedrag al; de coach heeft het los nodig om uit te rekenen wat teruglevering je oplevert als je saldeert.";

    // A dynamic contract without the sensor it is supposed to read leaves the
    // price tile on a dash forever, and nothing on this screen would say why.
    const entity =
      source === "all_in" ? contract.dynamic.all_in_entity : contract.dynamic.market_entity;
    const notice = this.$("#dyn-missing");
    notice.hidden = !dynamic || Boolean(entity);
    if (!notice.hidden) {
      this.$("#dyn-missing-text").textContent =
        source === "all_in"
          ? "Er is nog geen all-in prijssensor gekozen, dus de energieprijs blijft leeg op het overzicht."
          : "Er is nog geen marktprijssensor gekozen, dus de energieprijs blijft leeg op het overzicht.";
    }
  }

  /** De som achter een zelf opgebouwde prijs, zodat hij na te rekenen is. */
  paintHints_() {
    const d = this.draft_.contract.dynamic;
    const vat = Number(d.vat_percent) || 0;
    this.$("#dyn-formula").textContent =
      `Berekening: (marktprijs + € ${euro(d.energy_tax)} + € ${euro(d.supplier_markup)}) × ${(1 + vat / 100).toLocaleString("nl-NL", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
}

DacViewContract.css = /* css */ `
  ${editorCss}

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
