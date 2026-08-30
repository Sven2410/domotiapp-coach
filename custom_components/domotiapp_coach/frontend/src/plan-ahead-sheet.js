/**
 * Wat de coach van plan is, uur voor uur, tot de auto vol moet zijn.
 *
 * Sven op 30-08-2026: "ik wil een knop op de laadpaalkaart dat ik kan zien wat
 * de coach van plan is met hele tijdlijn tot dat hij vol moet zijn." Dat is de
 * vraag die een coach die uren stilstaat oproept, en het antwoord stond tot nu
 * toe in één zin op de kaart: "wacht op een goedkoper uur." Dat klopt, maar het
 * zegt niet wélke uren, en dus ook niet of er iets misgaat.
 *
 * **Alles hier komt uit de coach zelf en wordt hier niets uitgerekend.** Dat is
 * met opzet. Een scherm dat zijn eigen sommen doet loopt vroeg of laat uit de
 * pas met wat er werkelijk gebeurt, en dan wacht de bewoner op een uur dat de
 * coach niet gekozen heeft. `timeline()` in planner.py maakt de lijst, met
 * precies dezelfde aanroep van `cheapest_hours` als het besluit van die minuut.
 */

import { DacElement, define } from "./base.js";
import { icons } from "./icons.js";
import { sheetCss } from "./theme.js";

const css = /* css */ `
  ${sheetCss}

  .kop {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 10px;
    margin-bottom: 14px;
  }
  .kop .vak {
    padding: 10px 12px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(255,255,255,0.03);
  }
  .kop .label {
    font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase;
    color: var(--dac-ink-3); font-weight: 700;
  }
  .kop .waarde {
    font-size: 17px; font-weight: 700; color: var(--dac-ink-1);
    font-variant-numeric: tabular-nums; margin-top: 2px;
  }
  .kop .bij { font-size: 11.5px; color: var(--dac-ink-3); }

  .uren { display: flex; flex-direction: column; gap: 4px; }

  .uur {
    display: grid;
    grid-template-columns: 56px 74px 1fr;
    align-items: center;
    gap: 10px;
    padding: 9px 11px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(255,255,255,0.02);
    font-size: 13px;
  }
  /* Een uur waarin geladen wordt is het nieuws, dus dat is het enige dat kleur
     krijgt. Alles kleuren is hetzelfde als niets kleuren. */
  .uur.laadt {
    border-color: rgba(56,189,124,0.45);
    background: rgba(56,189,124,0.10);
  }
  .uur.nu { outline: 2px solid var(--dac-accent-hi); outline-offset: 1px; }

  .uur .tijd { font-weight: 700; font-variant-numeric: tabular-nums; color: var(--dac-ink-1); }
  .uur .prijs { font-variant-numeric: tabular-nums; color: var(--dac-ink-2); }
  .uur .wat { color: var(--dac-ink-3); font-size: 12.5px; }
  .uur.laadt .wat { color: var(--dac-ink-2); }

  .leeg {
    padding: 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px dashed var(--dac-border-hi);
    color: var(--dac-ink-3);
    font-size: 13px; line-height: 1.5;
  }

  .voet { margin-top: 12px; font-size: 12px; line-height: 1.55; color: var(--dac-ink-3); }

  /* Onder de 360 px vallen drie kolommen om. De reden mag dan onder de tijd
     staan; wat er niet mag is dat de kaart zijwaarts gaat schuiven. */
  @media (max-width: 360px) {
    .uur { grid-template-columns: 52px 1fr; }
    .uur .wat { grid-column: 1 / -1; }
  }
`;

/** Een tijdstip uit de coach als kloktijd, of een streepje. */
const klok = (iso) => {
  if (!iso) return "–";
  const moment = new Date(iso);
  return Number.isNaN(moment.getTime())
    ? "–"
    : `${String(moment.getHours()).padStart(2, "0")}:${String(moment.getMinutes()).padStart(2, "0")}`;
};

const euro = (value) =>
  value === null || value === undefined
    ? ""
    : `€ ${Number(value).toFixed(3)}`.replace(".", ",");

const uren = (value) => {
  if (value === null || value === undefined) return "–";
  const totaal = Math.round(Number(value) * 60);
  const u = Math.floor(totaal / 60);
  const m = totaal % 60;
  return u ? `${u} u ${String(m).padStart(2, "0")} m` : `${m} min`;
};

export class DacPlanAheadSheet extends DacElement {
  static css = css;

  constructor() {
    super();
    this.plan_ = null;
    this.label_ = "";
    this.reason_ = "";
  }

  render() {
    return /* html */ `
      <dialog class="sheet wide" tabindex="-1" aria-labelledby="vooruit-title">
        <div class="sheet-head">
          <div>
            <div class="eyebrow">Wat gaat hij doen</div>
            <h3 id="vooruit-title"></h3>
          </div>
          <button class="sheet-close" type="button" id="vooruit-close" aria-label="Sluiten">
            ${icons.close}
          </button>
        </div>
        <p class="sheet-sub" id="vooruit-nu"></p>

        <div class="kop" id="vooruit-kop"></div>
        <div class="uren" id="vooruit-uren"></div>
        <p class="voet" id="vooruit-voet"></p>
      </dialog>
    `;
  }

  afterRender() {
    const dialog = this.$("dialog");
    this.$("#vooruit-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  }

  /** Openen met de tijdlijn zoals de coach hem net heeft uitgerekend. */
  open(label, besluit) {
    this.label_ = label || "";
    this.plan_ = besluit?.plan_ahead ?? null;
    this.reason_ = [besluit?.reason, besluit?.plan].filter(Boolean).join(" ");
    this.paint_();
    const dialog = this.$("dialog");
    if (!dialog.open) dialog.showModal();
  }

  /** Bijwerken terwijl hij openstaat, want de coach denkt elke minuut opnieuw. */
  update(besluit) {
    if (!this.rendered_ || !this.$("dialog")?.open) return;
    this.plan_ = besluit?.plan_ahead ?? null;
    this.reason_ = [besluit?.reason, besluit?.plan].filter(Boolean).join(" ");
    this.paint_();
  }

  close() {
    this.$("dialog")?.close();
  }

  paint_() {
    this.$("#vooruit-title").textContent = this.label_;
    this.$("#vooruit-nu").textContent = this.reason_;

    const plan = this.plan_;
    const kop = this.$("#vooruit-kop");
    const uurlijst = this.$("#vooruit-uren");
    kop.replaceChildren();
    uurlijst.replaceChildren();

    if (!plan) {
      this.$("#vooruit-voet").textContent = "";
      const leeg = document.createElement("div");
      leeg.className = "leeg";
      leeg.textContent =
        "De coach heeft nog geen plan. Dat komt zodra hij een ronde gedraaid heeft.";
      uurlijst.append(leeg);
      return;
    }

    for (const [label, waarde, bij] of [
      ["Nog te laden", plan.kwh_needed === null || plan.kwh_needed === undefined
        ? "–"
        : `${Number(plan.kwh_needed).toFixed(1).replace(".", ",")} kWh`,
        plan.amps ? `op ${plan.amps} A` : ""],
      ["Laadtijd", uren(plan.hours_needed), ""],
      ["Uiterlijk beginnen", klok(plan.latest_start), "speling zit erin"],
      ["Vol rond", klok(plan.expected_done),
        plan.deadline ? `klaar om ${klok(plan.deadline)}` : "geen klaar-tijd"],
    ]) {
      const vak = document.createElement("div");
      vak.className = "vak";
      const kl = document.createElement("div");
      kl.className = "label";
      kl.textContent = label;
      const wa = document.createElement("div");
      wa.className = "waarde";
      wa.textContent = waarde;
      vak.append(kl, wa);
      if (bij) {
        const bj = document.createElement("div");
        bj.className = "bij";
        bj.textContent = bij;
        vak.append(bj);
      }
      kop.append(vak);
    }

    const nu = Date.now();
    for (const blok of plan.blocks ?? []) {
      const rij = document.createElement("div");
      rij.className = "uur";
      if (blok.charging) rij.classList.add("laadt");
      const start = new Date(blok.start).getTime();
      const eind = new Date(blok.end).getTime();
      if (start <= nu && nu < eind) rij.classList.add("nu");

      const tijd = document.createElement("span");
      tijd.className = "tijd";
      tijd.textContent = klok(blok.start);
      const prijs = document.createElement("span");
      prijs.className = "prijs";
      prijs.textContent = euro(blok.price);
      const wat = document.createElement("span");
      wat.className = "wat";
      wat.textContent = blok.charging ? `Laden, ${blok.why}` : `Wachten, ${blok.why}`;

      rij.append(tijd, prijs, wat);
      uurlijst.append(rij);
    }

    if (!(plan.blocks ?? []).length) {
      const leeg = document.createElement("div");
      leeg.className = "leeg";
      leeg.textContent =
        plan.note || "Er is niets te plannen: er hangt geen auto of er zijn geen prijzen.";
      uurlijst.append(leeg);
      this.$("#vooruit-voet").textContent = "";
      return;
    }

    this.$("#vooruit-voet").textContent =
      plan.note ||
      "Dit is wat de coach nu van plan is. Verandert je accustand of de prijs, dan " +
        "rekent hij het bij de volgende ronde opnieuw uit.";
  }
}

define("dac-plan-ahead-sheet", DacPlanAheadSheet);
