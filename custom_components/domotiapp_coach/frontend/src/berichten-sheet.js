/**
 * De berichtenbox (v0.130.0): wat de bewoner zelf moet doen, met een tellertje
 * in de kop zolang er iets ongelezen is.
 *
 * De eigenaar op 18-10-2026: "ik wil een soort berichtenbox met zo'n 1tje wat
 * optelt en dat je dat kan wegvinken van is gelezen bijvoorbeeld. Berichten zoals
 * denk aan je meterstanden doorgeven en contract loopt bijna af komen daar in."
 *
 * Wat erin komt bepaalt de coach (`berichten.py`, `BerichtenStore` in
 * storage.py); dit toont alleen, en vraagt het paneel om iets als gelezen te
 * markeren (`dac-bericht-gelezen`).
 */

import { DacElement, define } from "./base.js";
import { icons } from "./icons.js";
import { sheetCss } from "./theme.js";

const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

/** Het aantal ongelezen berichten. */
export const ongelezen = (items) => (items ?? []).filter((b) => b && !b.read).length;

/** "vandaag 08:00", "gisteren", of "12 oktober". */
export function wanneerTekst(iso, nu = new Date()) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const dag = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const verschil = Math.round((dag(nu) - dag(d)) / 86400000);
  const klok = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  if (verschil === 0) return `vandaag ${klok}`;
  if (verschil === 1) return `gisteren ${klok}`;
  return d.toLocaleDateString("nl-NL", { day: "numeric", month: "long", ...(d.getFullYear() !== nu.getFullYear() ? { year: "numeric" } : {}) });
}

/** De lijst als html: nieuwste bovenaan, ongelezen met een knop "Gelezen". */
export function berichtenHtml(items, nu = new Date()) {
  const lijst = [...(items ?? [])].sort((a, b) => String(b.at).localeCompare(String(a.at)));
  if (!lijst.length) return `<p class="leeg">Geen berichten. Als je iets moet doen, zoals je meterstanden doorgeven, staat het hier.</p>`;
  return lijst.map((b) => `
    <article class="bericht${b.read ? " gelezen" : ""}">
      <div class="b-kop">
        <strong>${esc(b.title)}</strong>
        <span class="b-wanneer">${esc(wanneerTekst(b.at, nu))}</span>
      </div>
      <p>${esc(b.body)}</p>
      ${b.read ? "" : `<button type="button" class="gelezen-knop" data-gelezen="${esc(b.id)}">${icons.check}<span>Gelezen</span></button>`}
    </article>`).join("");
}

const css = /* css */ `
  ${sheetCss}
  .lijst { display: grid; gap: 10px; }
  .bericht {
    display: grid; gap: 6px; padding: 12px 14px; border-radius: var(--dac-radius-sm);
    border: 1px solid rgba(250,178,25,0.35); background: rgba(250,178,25,0.07);
  }
  .bericht.gelezen { border-color: var(--dac-border); background: rgba(var(--dac-veil),0.02); opacity: 0.75; }
  .b-kop { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
  .b-kop strong { font-size: 14px; color: var(--dac-ink); min-width: 0; overflow-wrap: anywhere; }
  .b-wanneer { font-size: 12px; color: var(--dac-ink-3); white-space: nowrap; }
  .bericht p { margin: 0; font-size: 13px; line-height: 1.5; color: var(--dac-ink-2); }
  .gelezen-knop, .alles {
    justify-self: start; display: inline-flex; align-items: center; gap: 6px;
    font: inherit; font-size: 13px; padding: 7px 12px; border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.04); color: var(--dac-ink); cursor: pointer;
  }
  .gelezen-knop .icon, .alles .icon { width: 14px; height: 14px; flex: 0 0 auto; }
  .alles { margin: 0 0 12px; }
  .alles[hidden] { display: none; }
  .leeg { margin: 0; font-size: 13px; color: var(--dac-ink-2); }
`;

export class DacBerichtenSheet extends DacElement {
  static css = css;

  constructor() {
    super();
    this.items_ = [];
  }

  render() {
    return /* html */ `
      <dialog class="sheet" tabindex="-1" aria-labelledby="berichten-titel">
        <div class="sheet-head">
          <div>
            <div class="eyebrow">Berichten</div>
            <h3 id="berichten-titel">Wat je zelf moet doen</h3>
          </div>
          <button class="sheet-close" type="button" id="berichten-dicht" aria-label="Sluiten">${icons.close}</button>
        </div>
        <button type="button" class="alles" id="alles-gelezen" hidden>${icons.check}<span>Alles gelezen</span></button>
        <div class="lijst" id="lijst"></div>
      </dialog>
    `;
  }

  afterRender() {
    const dialog = this.$("dialog");
    this.$("#berichten-dicht").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    this.$("#alles-gelezen").addEventListener("click", () => this.fire("dac-bericht-gelezen", { id: null }));
    this.$("#lijst").addEventListener("click", (event) => {
      const knop = event.target?.closest?.("[data-gelezen]");
      if (knop) this.fire("dac-bericht-gelezen", { id: knop.dataset.gelezen });
    });
    this.paint_();
  }

  set items(lijst) {
    this.items_ = Array.isArray(lijst) ? lijst : [];
    this.paint_();
  }

  open() {
    this.paint_();
    const dialog = this.$("dialog");
    if (dialog && !dialog.open) dialog.showModal();
  }

  paint_() {
    if (!this.rendered_) return;
    this.$("#lijst").innerHTML = berichtenHtml(this.items_);
    this.$("#alles-gelezen").hidden = ongelezen(this.items_) < 2;
  }
}

define("dac-berichten-sheet", DacBerichtenSheet);
