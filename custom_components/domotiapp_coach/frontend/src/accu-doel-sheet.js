/**
 * "Nu vol laden" en "Nu leegladen" met een doel (v0.141.0): een pop-up met een
 * schuif tussen de ondergrens en het plafond van de batterij.
 *
 * De eigenaar op 19-10-2026: "Nu vol laden" en "Nu leegladen" openen een pop-up
 * met een schuif, het vak "tot 50 %" naast de knop gaat weg, en zolang het loopt
 * draait er een blauwe ring om de knop (die staat in overview.js).
 *
 * Rekent zelf niets; zegt het paneel wat er gekozen is (`dac-accu-doel`, met
 * `pct` null voor stoppen).
 */

import { DacElement, define } from "./base.js";
import { icons } from "./icons.js";
import { sheetCss } from "./theme.js";
import { t } from "./i18n.js";

/** Een waarde op de schuif: een veelvoud van 5 tussen de grenzen, de grenzen zelf mogen ook. */
export function opSchuif(waarde, laag, hoog) {
  const lo = Math.ceil(Number(laag) || 0);
  const hi = Math.floor(Number.isFinite(Number(hoog)) ? Number(hoog) : 100);
  const n = Math.round((Number(waarde) || 0) / 5) * 5;
  return Math.min(hi, Math.max(lo, n));
}

const css = /* css */ `
  ${sheetCss}
  .doel { margin: 22px 0 6px; text-align: center; }
  .doel strong { font-size: 34px; font-weight: 500; font-variant-numeric: tabular-nums; color: var(--dac-ink); }
  .doel span { font-size: 15px; color: var(--dac-ink-3); margin-left: 2px; }
  input[type="range"] { width: 100%; margin: 8px 0 0; accent-color: var(--dac-accent-hi); min-height: 32px; }
  .grenzen { display: flex; justify-content: space-between; font-size: 12px; color: var(--dac-ink-3); font-variant-numeric: tabular-nums; }
  .sheet-buttons button.go {
    border-color: var(--dac-accent-hi);
    background: rgba(25,143,217,0.16);
    color: var(--dac-ink);
    font-weight: 600;
  }
  .sheet-buttons button[hidden] { display: none; }
`;

export class DacAccuDoelSheet extends DacElement {
  static css = css;

  constructor() {
    super();
    this.keuze_ = null;
  }

  render() {
    return /* html */ `
      <dialog class="sheet" tabindex="-1" aria-labelledby="doel-titel">
        <div class="sheet-head">
          <div>
            <div class="eyebrow" id="doel-naam"></div>
            <h3 id="doel-titel"></h3>
          </div>
          <button class="sheet-close" type="button" id="doel-dicht" aria-label="${t("Sluiten")}">${icons.close}</button>
        </div>
        <p class="sheet-sub" id="doel-uitleg"></p>
        <div class="doel"><strong id="doel-pct">50</strong><span>%</span></div>
        <input type="range" id="doel-schuif" min="0" max="100" step="5" aria-labelledby="doel-titel">
        <div class="grenzen"><span id="doel-laag"></span><span id="doel-hoog"></span></div>
        <div class="sheet-buttons">
          <button type="button" id="doel-stop" hidden></button>
          <button type="button" class="go" id="doel-start"></button>
        </div>
      </dialog>
    `;
  }

  afterRender() {
    const dialog = this.$("dialog");
    this.$("#doel-dicht").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    const schuif = this.$("#doel-schuif");
    schuif.addEventListener("input", () => { this.$("#doel-pct").textContent = schuif.value; });
    this.$("#doel-start").addEventListener("click", () => {
      this.fire("dac-accu-doel", { slot: this.keuze_?.slot, soort: this.keuze_?.soort, pct: Number(schuif.value) });
      dialog.close();
    });
    this.$("#doel-stop").addEventListener("click", () => {
      this.fire("dac-accu-doel", { slot: this.keuze_?.slot, soort: this.keuze_?.soort, pct: null });
      dialog.close();
    });
  }

  /**
   * @param {{slot: number, soort: "vol"|"leeg", naam: string, laag: number, hoog: number,
   *          soc: number|null, waarde: number|null, actief: boolean}} keuze
   */
  open(keuze) {
    if (!this.rendered_) return;
    this.keuze_ = keuze;
    const vol = keuze.soort === "vol";
    const laag = Math.ceil(keuze.laag ?? 0);
    const hoog = Math.floor(keuze.hoog ?? 100);
    const schuif = this.$("#doel-schuif");
    schuif.min = String(laag);
    schuif.max = String(hoog);
    // Een veelvoud van 5, en de grenzen zelf ook, ook als die geen veelvoud zijn.
    schuif.step = laag % 5 || hoog % 5 ? "1" : "5";
    const begin = keuze.waarde ?? (vol ? hoog : Math.max(laag, 50));
    schuif.value = String(opSchuif(begin, laag, hoog));
    this.$("#doel-pct").textContent = schuif.value;
    this.$("#doel-naam").textContent = keuze.naam ?? "";
    this.$("#doel-titel").textContent = vol ? t("Nu vol laden") : t("Nu leegladen");
    const nu = Number.isFinite(keuze.soc) ? t("Nu {pct}%.", { pct: Math.round(keuze.soc) }) + " " : "";
    this.$("#doel-uitleg").textContent = nu + (vol
      ? t("Hij laadt van het net op vol vermogen tot deze accustand, wat de prijs ook is, en volgt daarna het plan weer.")
      : t("Hij levert aan het net op vol vermogen tot deze accustand, wat de prijs ook is, en volgt daarna het plan weer."));
    this.$("#doel-laag").textContent = `${laag}%`;
    this.$("#doel-hoog").textContent = `${hoog}%`;
    this.$("#doel-start").textContent = keuze.actief ? t("Aanpassen") : t("Starten");
    const stop = this.$("#doel-stop");
    stop.hidden = !keuze.actief;
    stop.textContent = t("Stoppen");
    const dialog = this.$("dialog");
    if (dialog && !dialog.open) dialog.showModal();
  }
}

define("dac-accu-doel-sheet", DacAccuDoelSheet);
