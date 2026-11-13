/**
 * Vraag het de DomotiTech Bot (v0.220.0): een doorlopend gesprek met de bot, en tickets van het huis.
 *
 * De eigenaar op 12-11-2026: "Ik wil het centraal houden dus het moet in een popup komen zoals Vraag het de
 * DomotiTech Bot snap je? Alles in HA". En op 13-11-2026: "Gewoon een vraag stellen over de installatie en echt een
 * ticket aan maken zijn aparte dingen": de vragen als één chat, een ticket met een soort (storing of aanvraag) en
 * een foto. Hetzelfde venster als de kaart van DomotiApp Lovelace.
 *
 * Wat erin staat bewaart de coach (tickets.py, `TicketsStore`); dit toont, en vraagt het paneel iets te versturen
 * (`dac-ticket-nieuw`, `dac-ticket-reageer`) of als gelezen te markeren (`dac-ticket-gelezen`). Foto's uploadt en
 * ondertekent het paneel (`uploader`, `fotoAdres`). Tekst is altijd tekst, nooit html.
 */

import { DacElement, define } from "./base.js";
import { icons } from "./icons.js";
import { huisNu } from "./format.js";
import { sheetCss } from "./theme.js";
import { nt, t } from "./i18n.js";
import { wanneerTekst } from "./berichten-sheet.js";

const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

export const GESPREK = 0;
export const TICKET_SOORTEN = [
  { id: "storing", label: nt("Storing") },
  { id: "aanvraag", label: nt("Aanvraag") },
];
const STANDEN = {
  nieuw: nt("Ontvangen"),
  in_behandeling: nt("In behandeling"),
  bij_beheerder: nt("Wacht op een beslissing"),
  klaar: nt("Klaar"),
};
const FOTOS_MAX = 4;
const soortLabel = (id) => t(TICKET_SOORTEN.find((s) => s.id === id)?.label ?? id);

/** Of er in dit ticket of het gesprek een antwoord van DomotiTech staat dat deze gebruiker nog niet zag. */
export function ticketNieuw(ticket, userId) {
  const gezien = Number((ticket?.gelezen ?? {})[userId] ?? 0);
  return (ticket?.berichten ?? []).some((b) => b?.van === "domotitech" && Number(b.id) > gezien);
}

/** De stip op de knop: het gesprek en de tickets samen, elk één keer. */
export const ongelezenTickets = (tickets, userId, gesprek = null) =>
  (tickets ?? []).filter((tk) => ticketNieuw(tk, userId)).length + (gesprek && ticketNieuw(gesprek, userId) ? 1 : 0);

/** De lijst met tickets als html: nieuwste eerst, met nummer, soort, stand en tijd. */
export function ticketsHtml(tickets, userId, nu = huisNu()) {
  const lijst = [...(tickets ?? [])].sort((a, b) => String(b.bijgewerkt).localeCompare(String(a.bijgewerkt)));
  if (!lijst.length) return `<p class="leeg">${t("Nog geen tickets. Een storing of een aanvraag maak je met Nieuw ticket.")}</p>`;
  return lijst.map((tk) => `
    <button type="button" class="ticket${ticketNieuw(tk, userId) ? " nieuw" : ""}" data-ticket="${esc(tk.id)}">
      <span class="t-kop"><strong>#${esc(tk.id)} ${esc(tk.onderwerp)}</strong><span class="t-wanneer">${esc(wanneerTekst(tk.bijgewerkt, nu))}</span></span>
      <span class="t-sub">${esc(soortLabel(tk.soort))} · ${esc(t(STANDEN[tk.stand] ?? tk.stand))}${ticketNieuw(tk, userId) ? ` · <b>${t("nieuw antwoord")}</b>` : ""}</span>
    </button>`).join("");
}

/** De berichten als html; een foto als plaatje met `data-foto`, het adres zet het paneel erin. */
export function gesprekHtml(ticket, nu = huisNu()) {
  const berichten = ticket?.berichten ?? [];
  if (!berichten.length && ticket?.id === GESPREK) {
    return `<p class="leeg">${t("Stel hier je vraag over je installatie, bijvoorbeeld hoe vol je accu is.")}</p>`;
  }
  return berichten.map((b) => `
    <div class="bericht ${b.van === "domotitech" ? "zij" : "wij"}">
      <div class="b-kop"><strong>${esc(b.naam || (b.van === "domotitech" ? "DomotiTech" : ""))}</strong><span>${esc(wanneerTekst(b.at, nu))}</span></div>
      ${b.tekst ? `<p>${esc(b.tekst)}</p>` : ""}
      ${(b.bijlagen ?? []).length ? `<div class="fotos">${b.bijlagen.map((f) => `<img alt="${t("Foto")}" data-foto="${esc(f.id)}">`).join("")}</div>` : ""}
    </div>`).join("");
}

/** Een foto verkleind tot een JPEG van hoogstens 2000 px, zoals de kaart; lukt dat niet, dan het bestand zelf. */
async function verklein(bestand) {
  try {
    const beeld = await createImageBitmap(bestand);
    const schaal = Math.min(1, 2000 / Math.max(beeld.width, beeld.height));
    const doek = document.createElement("canvas");
    doek.width = Math.round(beeld.width * schaal);
    doek.height = Math.round(beeld.height * schaal);
    doek.getContext("2d").drawImage(beeld, 0, 0, doek.width, doek.height);
    return await new Promise((klaar) => doek.toBlob((blob) => klaar(blob ?? bestand), "image/jpeg", 0.85));
  } catch {
    return bestand;
  }
}

const css = /* css */ `
  ${sheetCss}
  .tabs { display: flex; gap: 6px; margin: 0 0 12px; }
  .tabs button[aria-selected="true"] { border-color: rgba(250,178,25,0.7); background: rgba(250,178,25,0.18); }
  .lijst, .gesprek { display: grid; gap: 8px; }
  .gesprek { max-height: 52vh; overflow-y: auto; }
  .balk { display: flex; gap: 8px; align-items: center; margin: 0 0 12px; flex-wrap: wrap; }
  .knop {
    display: inline-flex; align-items: center; gap: 6px; font: inherit; font-size: 13px; padding: 8px 12px;
    border-radius: var(--dac-radius-sm); border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.04);
    color: var(--dac-ink); cursor: pointer;
  }
  .knop.hoofd { border-color: rgba(250,178,25,0.6); background: rgba(250,178,25,0.14); }
  .knop .icon { width: 14px; height: 14px; flex: 0 0 auto; }
  .knop[hidden], .balk[hidden] { display: none; }
  .ticket {
    display: grid; gap: 4px; text-align: left; font: inherit; padding: 12px 14px; border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.02); color: var(--dac-ink); cursor: pointer;
  }
  .ticket.nieuw { border-color: rgba(250,178,25,0.5); background: rgba(250,178,25,0.07); }
  .t-kop { display: flex; justify-content: space-between; gap: 10px; align-items: baseline; }
  .t-kop strong { font-size: 14px; min-width: 0; overflow-wrap: anywhere; }
  .t-wanneer, .t-sub { font-size: 12px; color: var(--dac-ink-3); }
  .bericht { padding: 10px 12px; border-radius: var(--dac-radius-sm); border: 1px solid var(--dac-border); }
  .bericht.zij { background: rgba(250,178,25,0.07); border-color: rgba(250,178,25,0.35); margin-right: 24px; }
  .bericht.wij { background: rgba(var(--dac-veil),0.03); margin-left: 24px; }
  .b-kop { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; color: var(--dac-ink-3); }
  .b-kop strong { color: var(--dac-ink); font-size: 13px; }
  .bericht p { margin: 4px 0 0; font-size: 13px; line-height: 1.5; color: var(--dac-ink-2); white-space: pre-wrap; overflow-wrap: anywhere; }
  .fotos { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
  .fotos img { width: 96px; height: 96px; object-fit: cover; border-radius: var(--dac-radius-sm); background: rgba(var(--dac-veil),0.06); }
  .soorten { display: flex; gap: 6px; flex-wrap: wrap; margin: 0 0 10px; }
  .soorten button[aria-pressed="true"] { border-color: rgba(250,178,25,0.7); background: rgba(250,178,25,0.18); }
  textarea {
    width: 100%; box-sizing: border-box; min-height: 80px; font: inherit; font-size: 14px; padding: 10px;
    border-radius: var(--dac-radius-sm); border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.03);
    color: var(--dac-ink); resize: vertical;
  }
  .schrijf { display: grid; gap: 8px; margin-top: 12px; }
  .schrijf[hidden], .scherm[hidden] { display: none; }
  .gekozen { font-size: 12px; color: var(--dac-ink-3); }
  .melding { margin: 0 0 10px; font-size: 13px; color: var(--dac-ink-2); }
  .melding.fout { color: rgb(229,72,77); }
  .melding[hidden] { display: none; }
  .leeg { margin: 0; font-size: 13px; color: var(--dac-ink-2); }
  input[type="file"] { display: none; }
`;

export class DacTicketsSheet extends DacElement {
  static css = css;

  constructor() {
    super();
    this.tickets_ = [];
    this.gesprek_ = null;
    this.userId_ = "";
    this.open_ = null;
    this.soort_ = "storing";
    this.tab_ = "vragen";
    this.scherm_ = "lijst";
    this.fotos_ = [];
    this.uploader = null;
    this.fotoAdres = null;
  }

  render() {
    return /* html */ `
      <dialog class="sheet" tabindex="-1" aria-labelledby="bot-titel">
        <div class="sheet-head">
          <div>
            <div class="eyebrow">DomotiTech</div>
            <h3 id="bot-titel">${t("Vraag het de DomotiTech Bot")}</h3>
          </div>
          <button class="sheet-close" type="button" id="bot-dicht" aria-label="${t("Sluiten")}">${icons.close}</button>
        </div>
        <div class="tabs" role="tablist">
          <button type="button" class="knop" role="tab" data-tab="vragen">${t("Vragen")}</button>
          <button type="button" class="knop" role="tab" data-tab="tickets">${t("Tickets")}</button>
        </div>
        <p class="melding" id="melding" role="status" hidden></p>
        <div class="scherm" id="s-vragen">
          <div class="gesprek" id="gesprek-vragen"></div>
          <div class="schrijf">
            <textarea id="vraag" maxlength="4000" aria-label="${t("Je vraag")}" placeholder="${t("Waar kunnen we je mee helpen?")}"></textarea>
            <button type="button" class="knop hoofd" id="stuur-vraag">${t("Versturen")}</button>
          </div>
        </div>
        <div class="scherm" id="s-tickets" hidden>
          <div class="balk">
            <button type="button" class="knop" id="terug" hidden>${icons.arrowLeft}<span>${t("Alle tickets")}</span></button>
            <button type="button" class="knop hoofd" id="nieuw">${icons.plus}<span>${t("Nieuw ticket")}</span></button>
          </div>
          <div id="t-lijst"><div class="lijst" id="lijst"></div></div>
          <div id="t-gesprek" hidden>
            <div class="gesprek" id="gesprek-ticket"></div>
            <div class="schrijf">
              <textarea id="reactie" maxlength="4000" aria-label="${t("Reageren")}" placeholder="${t("Reageren")}"></textarea>
              <button type="button" class="knop" data-foto-kies>${icons.plus}<span>${t("Foto toevoegen")}</span></button>
              <span class="gekozen" data-gekozen></span>
              <button type="button" class="knop hoofd" id="stuur-reactie">${t("Versturen")}</button>
            </div>
          </div>
          <div id="t-nieuw" hidden>
            <div class="soorten" role="group" aria-label="${t("Soort")}">
              ${TICKET_SOORTEN.map((s) => `<button type="button" class="knop" data-soort="${s.id}" aria-pressed="false">${t(s.label)}</button>`).join("")}
            </div>
            <textarea id="ticket-tekst" maxlength="4000" aria-label="${t("Wat is er aan de hand?")}" placeholder="${t("Wat is er aan de hand?")}"></textarea>
            <div class="schrijf">
              <button type="button" class="knop" data-foto-kies>${icons.plus}<span>${t("Foto toevoegen")}</span></button>
              <span class="gekozen" data-gekozen></span>
              <button type="button" class="knop hoofd" id="stuur-nieuw">${t("Versturen")}</button>
            </div>
          </div>
        </div>
        <input type="file" id="foto" accept="image/jpeg,image/png,image/webp" capture="environment" multiple>
      </dialog>
    `;
  }

  afterRender() {
    const dialog = this.$("dialog");
    this.$("#bot-dicht").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    for (const knop of this.$$("[data-tab]")) knop.addEventListener("click", () => this.kiesTab_(knop.dataset.tab));
    this.$("#terug").addEventListener("click", () => this.toon_("lijst"));
    this.$("#nieuw").addEventListener("click", () => this.toon_("nieuw"));
    this.$("#lijst").addEventListener("click", (event) => {
      const knop = event.target?.closest?.("[data-ticket]");
      if (knop) this.openTicket_(Number(knop.dataset.ticket));
    });
    for (const knop of this.$$("[data-soort]")) {
      knop.addEventListener("click", () => {
        this.soort_ = knop.dataset.soort;
        this.paint_();
      });
    }
    for (const knop of this.$$("[data-foto-kies]")) knop.addEventListener("click", () => this.$("#foto").click());
    this.$("#foto").addEventListener("change", (event) => this.fotosErbij_(event.target.files));
    this.$("#stuur-vraag").addEventListener("click", () => {
      const tekst = this.$("#vraag").value.trim();
      if (!tekst) return;
      this.fire("dac-ticket-reageer", { id: GESPREK, tekst, bijlagen: [] });
      this.$("#vraag").value = "";
    });
    this.$("#stuur-nieuw").addEventListener("click", () => {
      const tekst = this.$("#ticket-tekst").value.trim();
      if (!tekst && !this.fotos_.length) return;
      this.fire("dac-ticket-nieuw", { soort: this.soort_, tekst, bijlagen: this.fotos_.map((f) => f.id) });
      this.$("#ticket-tekst").value = "";
      this.fotos_ = [];
      this.toon_("lijst");
      this.meld_(t("Ontvangen, we kijken ernaar."));
    });
    this.$("#stuur-reactie").addEventListener("click", () => {
      const tekst = this.$("#reactie").value.trim();
      if ((!tekst && !this.fotos_.length) || this.open_ == null) return;
      this.fire("dac-ticket-reageer", { id: this.open_, tekst, bijlagen: this.fotos_.map((f) => f.id) });
      this.$("#reactie").value = "";
      this.fotos_ = [];
      this.paint_();
    });
    this.paint_();
  }

  set tickets(lijst) {
    this.tickets_ = Array.isArray(lijst) ? lijst : [];
    this.paint_();
  }

  set gesprek(gesprek) {
    this.gesprek_ = gesprek && typeof gesprek === "object" ? gesprek : null;
    this.paint_();
    if (this.tab_ === "vragen" && this.$("dialog")?.open) this.leesGesprek_();
  }

  set userId(id) {
    this.userId_ = String(id ?? "");
    this.paint_();
  }

  /** Een fout van de coach, met zijn eigen zin. */
  set fout(tekst) {
    if (tekst) this.meld_(String(tekst), true);
  }

  open() {
    this.kiesTab_(this.tab_);
    const dialog = this.$("dialog");
    if (dialog && !dialog.open) dialog.showModal();
    if (this.tab_ === "vragen") this.leesGesprek_();
  }

  kiesTab_(tab) {
    this.tab_ = tab;
    this.toon_("lijst");
    if (tab === "vragen") this.leesGesprek_();
  }

  leesGesprek_() {
    if (this.gesprek_ && ticketNieuw(this.gesprek_, this.userId_)) this.fire("dac-ticket-gelezen", { id: GESPREK });
  }

  openTicket_(id) {
    this.open_ = id;
    this.toon_("gesprek");
    if (ticketNieuw(this.tickets_.find((tk) => tk.id === id), this.userId_)) this.fire("dac-ticket-gelezen", { id });
  }

  async fotosErbij_(bestanden) {
    for (const bestand of [...(bestanden ?? [])].slice(0, FOTOS_MAX - this.fotos_.length)) {
      if (!this.uploader) break;
      try {
        this.fotos_.push(await this.uploader(await verklein(bestand)));
      } catch (error) {
        this.meld_(error?.message || t("De foto kon niet mee."), true);
      }
    }
    this.$("#foto").value = "";
    this.paint_();
  }

  meld_(tekst, fout = false) {
    if (!this.rendered_) return;
    const melding = this.$("#melding");
    melding.textContent = tekst;
    melding.classList.toggle("fout", fout);
    melding.hidden = false;
  }

  toon_(scherm) {
    this.scherm_ = scherm;
    if (this.rendered_) this.$("#melding").hidden = true;
    this.fotos_ = scherm === "lijst" ? [] : this.fotos_;
    this.paint_();
  }

  async vulFotos_(houder) {
    for (const img of houder.querySelectorAll("img[data-foto]")) {
      if (img.src || !this.fotoAdres) continue;
      try {
        img.src = await this.fotoAdres(img.dataset.foto);
      } catch {
        // Zonder adres blijft het vlak leeg; de rest van het gesprek staat er gewoon.
      }
    }
  }

  paint_() {
    if (!this.rendered_) return;
    for (const knop of this.$$("[data-tab]")) knop.setAttribute("aria-selected", String(knop.dataset.tab === this.tab_));
    this.$("#s-vragen").hidden = this.tab_ !== "vragen";
    this.$("#s-tickets").hidden = this.tab_ !== "tickets";
    this.$("#t-lijst").hidden = this.scherm_ !== "lijst";
    this.$("#t-gesprek").hidden = this.scherm_ !== "gesprek";
    this.$("#t-nieuw").hidden = this.scherm_ !== "nieuw";
    this.$("#terug").hidden = this.scherm_ === "lijst";
    this.$("#nieuw").hidden = this.scherm_ === "nieuw";
    const vragen = this.$("#gesprek-vragen");
    const onderaan = vragen.scrollHeight - vragen.scrollTop - vragen.clientHeight < 40;
    vragen.innerHTML = gesprekHtml(this.gesprek_ ?? { id: GESPREK, berichten: [] });
    if (onderaan) vragen.scrollTop = vragen.scrollHeight;
    this.$("#lijst").innerHTML = ticketsHtml(this.tickets_, this.userId_);
    const ticket = this.tickets_.find((tk) => tk.id === this.open_);
    this.$("#gesprek-ticket").innerHTML = ticket ? gesprekHtml(ticket) : "";
    this.vulFotos_(this.$("#gesprek-ticket"));
    for (const knop of this.$$("[data-soort]")) knop.setAttribute("aria-pressed", String(knop.dataset.soort === this.soort_));
    const gekozen = this.fotos_.length ? t("{n} foto('s) erbij", { n: this.fotos_.length }) : "";
    for (const plek of this.$$("[data-gekozen]")) plek.textContent = gekozen;
    for (const knop of this.$$("[data-foto-kies]")) knop.hidden = !this.uploader || this.fotos_.length >= FOTOS_MAX;
  }
}

define("dac-tickets-sheet", DacTicketsSheet);
