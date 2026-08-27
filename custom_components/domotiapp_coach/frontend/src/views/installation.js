/**
 * Installatie -- the facts about this house that do not change from minute to
 * minute: the connection it has, and the contract it runs on.
 *
 * Customers may read this page and cannot change it. That is deliberate: the
 * numbers here decide what the coach advises, so a customer spotting that their
 * fuse or their tariff is wrong and saying so is worth more than protecting them
 * from the sight of it. Instellingen, which points at raw entities, they do not
 * see at all.
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

/** Nominal voltage per phase: 3 x 25 A -> 17250 W, 1 x 25 A -> 5750 W. */
const VOLTAGE = 230;

const euro = (v) =>
  Number(v ?? 0).toLocaleString("nl-NL", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

class DacViewInstallation extends DacEditorElement {
  static sections = ["installation", "contract"];

  render() {
    return `
      <div class="wrap">
        <header class="intro">
          <div class="eyebrow">Installatie</div>
          <h1>Je woning, je aansluiting, je contract</h1>
          <p>Hier staat waar de coach mee rekent. Klopt er iets niet, geef het dan door aan je installateur. Wijzigen kan alleen een beheerder.</p>
        </header>

        ${adminNoticeHtml}

        <section class="card">
          <h2>${icons.house} Woning en aansluiting</h2>
          <p class="hint">De naam van de woning komt ook boven het overzicht te staan.</p>
          <div class="fields">
            <div class="row">
              <label for="home-name">Naam van de woning</label>
              <input type="text" id="home-name" placeholder="Bijvoorbeeld: Dorpsstraat 12" autocomplete="off">
            </div>

            <div class="row">
              <label>Aantal fasen</label>
              <div class="segmented" id="phases">
                <button type="button" data-phases="1" aria-pressed="false">
                  <strong>1 fase</strong>
                  Eén fase van 230 V.
                </button>
                <button type="button" data-phases="3" aria-pressed="false">
                  <strong>3 fasen</strong>
                  Drie fasen van 230 V.
                </button>
              </div>
            </div>

            <div class="two">
              <div class="row">
                <label for="fuse">Hoofdzekering per fase (A)</label>
                <input type="number" id="fuse" min="1" max="1000" step="1" inputmode="numeric">
              </div>
              <div class="row">
                <label for="max-grid">Maximaal netvermogen (W)</label>
                <input type="number" id="max-grid" min="0" step="50" inputmode="numeric">
                <span class="sub" id="max-grid-hint"></span>
              </div>
            </div>

            <label class="check" for="max-auto">
              <input type="checkbox" id="max-auto">
              <span>
                <strong>Automatisch berekenen</strong>
                Uit fasen × zekering × 230 V. Zet dit uit als je aansluiting begrensd of juist verzwaard is.
              </span>
            </label>

            <label class="check" for="balancer">
              <input type="checkbox" id="balancer">
              <span>
                <strong>Er zit een lastbewaker op de aansluiting</strong>
                Zoals een Easee Equalizer. Die bewaakt dezelfde zekering en kan het laden zelf
                terugschroeven. Staat dit aan, dan houdt de coach een ruimere marge aan en stapt
                hij als eerste terug, zodat de lastbewaker een vangnet blijft dat niet hoeft in
                te grijpen. Meet je lastbewaker de fasen, kies die sensoren dan hieronder bij de
                stroom per fase; dat is de zuiverste meting die je hebt.
              </span>
            </label>
          </div>
        </section>

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
                  <span class="sub">Wat je krijgt voor wat je teruglevert.</span>
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
                    laadt hij op zon alleen als de zon het grotendeels zelf dekt.
                  </span>
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
                  <label for="dyn-tax">Energiebelasting (€ per kWh)</label>
                  <input type="number" id="dyn-tax" min="0" step="0.0001" inputmode="decimal">
                  <span class="sub">Wat de overheid per kWh heft. Dit tarief verandert elk jaar op 1 januari, dus kijk het na op je jaarnota.</span>
                </div>
                <div class="row">
                  <span class="sub" id="dyn-formula"></span>
                </div>
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

              <div class="row">
                <label for="dyn-feedcost">Terugleverkosten (€ per kWh)</label>
                <input type="number" id="dyn-feedcost" min="0" step="0.001" inputmode="decimal">
                <span class="sub">Wat je leverancier rekent over wat je teruglevert.</span>
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
        this.afterChange_();
      });
    };

    bind("home-name", (v) => (this.draft_.installation.home_name = v));
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

    bind("fx-price", (v) => (this.draft_.contract.fixed.all_in_price = Number(v)));
    bind("fx-feedin", (v) => (this.draft_.contract.fixed.feed_in_tariff = Number(v)));
    bind("fx-feedcost", (v) => (this.draft_.contract.fixed.feed_in_costs = Number(v)));

    bind("dyn-tax", (v) => (this.draft_.contract.dynamic.energy_tax = Number(v)));
    bind("dyn-markup", (v) => (this.draft_.contract.dynamic.supplier_markup = Number(v)));
    bind("dyn-vat", (v) => (this.draft_.contract.dynamic.vat_percent = Number(v)));
    bind("dyn-feedcost", (v) => (this.draft_.contract.dynamic.feed_in_costs = Number(v)));

    this.$("#max-auto").addEventListener("change", (ev) => {
      this.draft_.installation.max_grid_auto = ev.target.checked;
      this.recalculate_();
      this.afterChange_();
    });

    this.$("#netting").addEventListener("change", (ev) => {
      this.draft_.contract.netting = ev.target.checked;
      this.afterChange_();
    });

    this.$("#balancer").addEventListener("change", (ev) => {
      this.draft_.installation.load_balancer = ev.target.checked;
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

  /** Keep the power ceiling in step with the fuse while it is automatic. */
  recalculate_() {
    const inst = this.draft_.installation;
    if (!inst.max_grid_auto) return;
    inst.max_grid_watts = Math.round((Number(inst.phases) || 1) * (Number(inst.fuse_amps) || 0) * VOLTAGE);
    this.$("#max-grid").value = inst.max_grid_watts;
  }

  paint_() {
    if (!this.draft_ || !this.rendered_) return;
    const inst = this.draft_.installation;
    const contract = this.draft_.contract;

    this.$("#home-name").value = inst.home_name ?? "";
    this.$("#fuse").value = inst.fuse_amps;
    this.$("#max-grid").value = inst.max_grid_watts;
    this.$("#max-auto").checked = Boolean(inst.max_grid_auto);
    this.$("#balancer").checked = Boolean(inst.load_balancer);
    this.$("#netting").checked = Boolean(this.draft_.contract.netting);

    this.$("#fx-price").value = contract.fixed.all_in_price;
    this.$("#fx-feedin").value = contract.fixed.feed_in_tariff;
    this.$("#fx-feedcost").value = contract.fixed.feed_in_costs;

    this.$("#dyn-tax").value = contract.dynamic.energy_tax;
    this.$("#dyn-markup").value = contract.dynamic.supplier_markup;
    this.$("#dyn-vat").value = contract.dynamic.vat_percent;
    this.$("#dyn-feedcost").value = contract.dynamic.feed_in_costs;

    this.$("#dyn-allin").value = contract.dynamic.all_in_entity ?? "";
    this.$("#dyn-market").value = contract.dynamic.market_entity ?? "";
    this.onFeed_();

    this.paintPhases_();
    this.paintContract_();
    this.paintHints_();
    this.syncSaveBar_();
  }

  paintPhases_() {
    const phases = Number(this.draft_.installation.phases) || 1;
    for (const button of this.$$("#phases button")) {
      button.setAttribute("aria-pressed", String(Number(button.dataset.phases) === phases));
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
    this.$("#dyn-market-fields").style.display = source === "market" ? "" : "none";
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

  /** The two places the arithmetic is spelled out, so it can be checked. */
  paintHints_() {
    const inst = this.draft_.installation;
    const phases = Number(inst.phases) || 1;
    const fuse = Number(inst.fuse_amps) || 0;
    const kw = (watts) =>
      (watts / 1000).toLocaleString("nl-NL", { minimumFractionDigits: 3, maximumFractionDigits: 3 });

    const computed = phases * fuse * VOLTAGE;
    // Once it has been overridden, showing the formula would claim an arithmetic
    // the number no longer follows.
    this.$("#max-grid-hint").textContent = inst.max_grid_auto
      ? `${phases} × ${fuse} A × ${VOLTAGE} V = ${kw(computed)} kW`
      : `Handmatig ingesteld op ${kw(Number(inst.max_grid_watts) || 0)} kW; berekend zou ${kw(computed)} kW zijn`;

    const d = this.draft_.contract.dynamic;
    const vat = Number(d.vat_percent) || 0;
    this.$("#dyn-formula").textContent =
      `Berekening: (marktprijs + € ${euro(d.energy_tax)} + € ${euro(d.supplier_markup)}) × ${(1 + vat / 100).toLocaleString("nl-NL", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
}

DacViewInstallation.css = /* css */ `
  ${editorCss}


`;

define("dac-view-installation", DacViewInstallation);
