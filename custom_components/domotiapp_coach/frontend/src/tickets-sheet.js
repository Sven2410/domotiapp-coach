/**
 * Vraag het Coach Assist (v0.220.0, tot v0.223.0 de DomotiTech Bot): een doorlopend gesprek, en tickets van het huis.
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

import { DacElement, define, openSheet } from "./base.js";
import { icons } from "./icons.js";
import { huisNu, huisTijd, metHoofdletter } from "./format.js";
import { LOGO_URL, sheetCss } from "./theme.js";
import { datum, nt, t } from "./i18n.js";
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

/**
 * Het ticket uit het adres van een pushmelding (`?coach_assist=<id>`, v0.229.0), en de rest van de zoekstring zonder
 * die parameter; `id` is null als er geen (geldige) is.
 */
export function uitAdres(zoekstring) {
  const zoek = new URLSearchParams(zoekstring ?? "");
  const waarde = zoek.get("coach_assist");
  zoek.delete("coach_assist");
  const rest = zoek.toString();
  return { id: waarde != null && /^\d+$/.test(waarde) ? Number(waarde) : null, rest: rest ? `?${rest}` : "" };
}

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

/**
 * Wie een bericht schreef. Een antwoord heet sinds v0.223.0 Coach Assist; wat er tot dan in de opslag kwam, staat er met
 * de naam DomotiTech, en dat is hetzelfde.
 */
export const afzender = (b) =>
  b?.van === "domotitech" && (!b.naam || b.naam === "DomotiTech") ? "Coach Assist" : String(b?.naam ?? "");

/**
 * Of een bericht van de gebruiker zelf is (v0.224.0): rechts, zoals WhatsApp in een groep. Een antwoord en een bericht van
 * een huisgenoot staan links. Een bericht van een bewoner zonder `user_id`, of zonder gebruiker die kijkt, telt als eigen.
 */
export const eigen = (b, userId = "") =>
  b?.van !== "domotitech" && (!userId || !b?.user_id || b.user_id === userId);

/** De dag van een bericht in de tijd van het huis, als "2026-11-13", of "" zonder tijd. */
function dagVan(iso) {
  const d = huisTijd(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const middag = (dag) => new Date(`${dag}T12:00:00`);
const dagenTussen = (van, tot) => Math.round((middag(tot) - middag(van)) / 86400000);

/** "Vandaag", "Gisteren", binnen een week "Vrijdag 13 november", daarna de datum, met het jaar als dat een ander is. */
export function dagTekst(dag, nu = huisNu()) {
  const vandaag = `${nu.getFullYear()}-${String(nu.getMonth() + 1).padStart(2, "0")}-${String(nu.getDate()).padStart(2, "0")}`;
  const verschil = dagenTussen(dag, vandaag);
  const d = middag(dag);
  if (verschil === 0) return t("Vandaag");
  if (verschil === 1) return t("Gisteren");
  const jaar = d.getFullYear() !== nu.getFullYear() ? { year: "numeric" } : {};
  return metHoofdletter(datum(d, { ...(verschil < 7 ? { weekday: "long" } : {}), day: "numeric", month: "long", ...jaar }));
}

const aantal = (n) => (n === 1 ? t("1 bericht") : t("{n} berichten", { n }));
// Hoeveel dagen voor het laatste bericht het gesprek nog per dag laat zien; wat ouder is staat achter één knop.
const GESPREK_DAGEN = 7;

function berichtHtml(b, userId) {
  const zelf = eigen(b, userId);
  const coach = b.van === "domotitech";
  const d = huisTijd(b.at);
  const klok = Number.isNaN(d.getTime()) ? "" : `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  return `
    <div class="bericht ${coach ? "zij" : zelf ? "wij" : "ander"}">
      <div class="b-naam">${coach ? `<img class="b-logo" src="${LOGO_URL}" alt="" draggable="false">` : ""}<strong>${esc(afzender(b))}</strong></div>
      ${b.tekst ? `<p>${esc(b.tekst)}</p>` : ""}
      ${(b.bijlagen ?? []).length ? `<div class="fotos">${b.bijlagen.map((f) => `<img alt="${t("Foto")}" data-foto="${esc(f.id)}">`).join("")}</div>` : ""}
      ${klok ? `<span class="b-tijd">${klok}</span>` : ""}
    </div>`;
}

/**
 * De berichten als html, zoals WhatsApp (v0.224.0): de eigen rechts, Coach Assist en huisgenoten links, elk met de naam
 * erboven, en per dag een scheiding. De eigenaar op 15-11-2026: "kijk even goed hoe whatsapp het doet. Blokken rechts van
 * je eigen tekst, blokken links van de antwoorden. En duidelijk aangeven of het de gebruiker is met de naam of de coach",
 * en "Evt de historische dagen ingevouwen? Tot een week max".
 *
 * Alleen in het gesprek (id 0) gaan dagen dicht: de laatste dag met berichten staat open, net als elke dag met een
 * antwoord dat de gebruiker nog niet zag. De eerdere dagen staan in één keuzelijst bovenaan, met het aantal berichten;
 * wat meer dan `GESPREK_DAGEN` voor het laatste bericht ligt is daarin één keuze "Oudere berichten". De eigenaar op
 * 15-11-2026: "Bij datum een dropdown niet zo veel datums laten zien ivm ruimtegebrek". `gekozen` is de dag (of "ouder")
 * die de gebruiker koos; die staat dan op zijn plek in het gesprek. Een ticket is kort: daar alleen de scheiding.
 * Een foto als plaatje met `data-foto`, het adres zet het paneel erin.
 */
export function gesprekHtml(ticket, nu = huisNu(), { userId = "", gekozen = "" } = {}) {
  const berichten = ticket?.berichten ?? [];
  if (!berichten.length && ticket?.id === GESPREK) {
    return `<p class="leeg">${t("Stel hier je vraag over je installatie, bijvoorbeeld hoe vol je accu is.")}</p>`;
  }
  const dagen = [];
  for (const b of berichten) {
    const dag = dagVan(b.at);
    if (!dagen.length || dagen[dagen.length - 1].dag !== dag) dagen.push({ dag, berichten: [] });
    dagen[dagen.length - 1].berichten.push(b);
  }
  const scheiding = (dag) => (dag ? `<div class="dag" data-dag="${esc(dag)}"><span>${esc(dagTekst(dag, nu))}</span></div>` : "");
  const blok = (d) => `<div class="dag-berichten">${d.berichten.map((b) => berichtHtml(b, userId)).join("")}</div>`;
  if (ticket?.id !== GESPREK) return dagen.map((d) => scheiding(d.dag) + blok(d)).join("");

  const gezien = Number((ticket?.gelezen ?? {})[userId] ?? 0);
  const laatste = dagen[dagen.length - 1].dag;
  const oud = (d) => Boolean(d.dag && laatste && dagenTussen(d.dag, laatste) > GESPREK_DAGEN);
  const vast = (d) => d.dag === laatste || !d.dag
    || d.berichten.some((b) => b?.van === "domotitech" && Number(b.id) > gezien);
  const toon = (d) => vast(d) || (oud(d) ? gekozen === "ouder" : gekozen === d.dag);
  // De keuzelijst: de dagen die dicht zijn, nieuwste eerst, en alles van voor de week als één keuze.
  const keuzes = [];
  for (const d of [...dagen].reverse()) {
    if (vast(d)) continue;
    if (oud(d)) {
      const rij = keuzes.find((k) => k.waarde === "ouder");
      if (rij) rij.n += d.berichten.length;
      else keuzes.push({ waarde: "ouder", tekst: t("Oudere berichten"), n: d.berichten.length });
    } else {
      keuzes.push({ waarde: d.dag, tekst: dagTekst(d.dag, nu), n: d.berichten.length });
    }
  }
  const lijst = keuzes.length ? `<label class="dagkeuze"><select data-dagkeuze aria-label="${t("Eerdere dagen")}">
      <option value="">${t("Eerdere dagen")}</option>
      ${keuzes.map((k) => `<option value="${esc(k.waarde)}"${k.waarde === gekozen ? " selected" : ""}>${esc(k.tekst)} · ${esc(aantal(k.n))}</option>`).join("")}
    </select></label>` : "";
  return lijst + dagen.filter(toon).map((d) => scheiding(d.dag) + blok(d)).join("");
}

/**
 * Hoeveel vragen of nieuwe tickets (`soort`) er vandaag nog over zijn (v0.225.0), of null zonder grens. Na `opnieuw`
 * (middernacht in het huis) staat het weer op het hele pakket, ook als de coach dat nog niet liet weten.
 */
export function pakketOver(pakket, soort, nu = Date.now()) {
  const grens = pakket?.[`${soort}_per_dag`];
  if (grens == null) return null;
  const opnieuw = Date.parse(pakket.opnieuw ?? "");
  if (!Number.isNaN(opnieuw) && nu >= opnieuw) return Number(grens);
  return Math.max(0, Number(pakket[`${soort}_over`] ?? grens));
}

export const vragenOver = (pakket, nu = Date.now()) => pakketOver(pakket, "vragen", nu);

/** "Nog 7 vragen vandaag", of "" zonder grens. */
export const vragenOverTekst = (over) =>
  over == null ? "" : over === 1 ? t("Nog 1 vraag vandaag") : t("Nog {n} vragen vandaag", { n: over });

/** "Nog 1 ticket vandaag", alleen bij `TICKETS_WEINIG` of minder; anders "". */
export const ticketsOverTekst = (over) =>
  over == null || over > TICKETS_WEINIG ? "" : over === 1 ? t("Nog 1 ticket vandaag") : t("Nog {n} tickets vandaag", { n: over });

const PAKKET_OP = nt("Je hebt je vragen voor vandaag gesteld. Morgen kun je weer vragen stellen. Is er iets kapot? Meld dan een storing.");
const TICKETS_OP = nt("Je hebt vandaag al het maximum aantal tickets gemaakt. Morgen kan het weer. Is het dringend? Neem dan contact op met je installateur.");
// Vanaf hoeveel vragen over de regel opvalt, en vanaf hoeveel tickets over hij er staat.
const WEINIG = 3;
const TICKETS_WEINIG = 2;

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

/** Of een gesprek (bijna) onderaan staat; een verborgen vak staat dat altijd. */
const onderaan = (vak) => vak.scrollHeight - vak.scrollTop - vak.clientHeight < 40;

const css = /* css */ `
  ${sheetCss}
  .sheet-head .logo { width: 38px; height: 38px; flex: 0 0 auto; object-fit: contain; }
  .tabs { display: flex; gap: 6px; margin: 14px 0 12px; }
  .tabs[hidden], .soorten [hidden] { display: none; }
  /* Zonder Coach Assist alleen tickets (v0.226.0): wat de tabbladen innamen, als ruimte boven de lijst. */
  .zonder-care .balk { margin-top: 14px; }
  .tabs button[aria-selected="true"] { border-color: rgba(25,143,217,0.55); background: var(--dac-accent-soft); }
  .lijst { display: grid; gap: 8px; }
  .gesprek, .dag-berichten { display: grid; gap: 6px; align-content: start; }
  .gesprek { max-height: 52vh; overflow-y: auto; overscroll-behavior: contain; }
  .balk { display: flex; gap: 8px; align-items: center; margin: 0 0 12px; flex-wrap: wrap; }
  .knop {
    display: inline-flex; align-items: center; gap: 6px; font: inherit; font-size: 13px; padding: 8px 12px;
    border-radius: var(--dac-radius-sm); border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.04);
    color: var(--dac-ink); cursor: pointer;
  }
  .knop.hoofd { border-color: rgba(25,143,217,0.55); background: var(--dac-accent-soft); }
  .knop .icon { width: 14px; height: 14px; flex: 0 0 auto; }
  .knop[hidden], .balk[hidden] { display: none; }
  .ticket {
    display: grid; gap: 4px; text-align: left; font: inherit; padding: 12px 14px; border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.02); color: var(--dac-ink); cursor: pointer;
  }
  .ticket.nieuw { border-color: rgba(25,143,217,0.45); background: rgba(2,111,161,0.08); }
  .t-kop { display: flex; justify-content: space-between; gap: 10px; align-items: baseline; }
  .t-kop strong { font-size: 14px; min-width: 0; overflow-wrap: anywhere; }
  .t-wanneer, .t-sub { font-size: 12px; color: var(--dac-ink-3); }
  /* Zoals WhatsApp (v0.224.0): de eigen berichten rechts in de accenttint, Coach Assist en huisgenoten links. */
  .bericht {
    max-width: 80%; min-width: 0; box-sizing: border-box; padding: 7px 10px 5px; border-radius: 12px;
    border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.04); justify-self: start;
    border-bottom-left-radius: 4px;
  }
  .bericht.wij {
    justify-self: end; background: var(--dac-accent-soft); border-color: rgba(25,143,217,0.35);
    border-bottom-left-radius: 12px; border-bottom-right-radius: 4px;
  }
  .b-naam { display: flex; align-items: center; gap: 5px; font-size: 12px; color: var(--dac-ink-3); }
  .b-naam strong { color: var(--dac-ink); font-size: 12px; font-weight: 600; overflow-wrap: anywhere; }
  .bericht.zij .b-naam strong { color: rgb(25,143,217); }
  .b-logo { width: 16px; height: 16px; flex: 0 0 auto; object-fit: contain; }
  .bericht p { margin: 2px 0 0; font-size: 13px; line-height: 1.45; color: var(--dac-ink); white-space: pre-wrap; overflow-wrap: anywhere; }
  .b-tijd { display: block; text-align: right; font-size: 11px; color: var(--dac-ink-3); margin-top: 2px; }
  .dag { display: flex; justify-content: center; margin: 6px 0 2px; }
  .dag span {
    font-size: 12px; color: var(--dac-ink-3); padding: 3px 10px; border-radius: 999px; background: rgba(var(--dac-veil),0.07);
  }
  .dagkeuze { display: flex; justify-content: center; }
  .dagkeuze select {
    /* 16px: met minder zoomt Safari op iOS in zodra je hem aantikt, net als bij een tekstvak. */
    font: inherit; font-size: 16px; color: var(--dac-ink-2); padding: 4px 12px; max-width: 100%;
    border-radius: 999px; border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.07); cursor: pointer;
    color-scheme: var(--dac-scheme);
  }
  select option { background: var(--dac-bg-raise); color: var(--dac-ink); }
  .fotos { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
  .fotos img { width: 96px; height: 96px; object-fit: cover; border-radius: var(--dac-radius-sm); background: rgba(var(--dac-veil),0.06); }
  .soorten { display: flex; gap: 6px; flex-wrap: wrap; margin: 0 0 10px; }
  .soorten button[aria-pressed="true"] { border-color: rgba(25,143,217,0.55); background: var(--dac-accent-soft); }
  textarea {
    width: 100%; box-sizing: border-box; min-height: 80px; font: inherit; font-size: 16px; padding: 10px;
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
  /* Het pakket (v0.225.0): de naam als etiket in het bovenschrift, wat er vandaag over is onder het veld. De eigenaar
     op 15-11-2026: "ik wil bij de coach assist ook zien welk abbo je hebt". */
  .pakket {
    display: inline-block; text-transform: none;
    font-size: 11px; font-weight: 600; letter-spacing: 0.02em; padding: 2px 8px; border-radius: 999px;
    color: rgb(25,143,217); background: var(--dac-accent-soft); border: 1px solid rgba(25,143,217,0.35); white-space: nowrap;
  }
  .over { margin: 0; font-size: 12px; color: var(--dac-ink-3); }
  .over.weinig { color: rgb(25,143,217); font-weight: 600; }
  .op { display: grid; gap: 8px; margin-top: 12px; }
  .op p { margin: 0; font-size: 13px; line-height: 1.5; color: var(--dac-ink-2); }
  .over[hidden], .op[hidden] { display: none; }
  textarea:disabled { opacity: 0.6; }
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
    // Welke eerdere dag de gebruiker in de keuzelijst koos, zodat een nieuw bericht hem niet weer weghaalt.
    this.gekozenDag_ = "";
    this.uploader = null;
    this.fotoAdres = null;
    this.pakket_ = null;
    this.opnieuwKlok_ = null;
    this.laatsteVraag_ = "";
    this.laatsteTicket_ = "";
  }

  render() {
    return /* html */ `
      <dialog class="sheet" tabindex="-1" aria-labelledby="bot-titel">
        <div class="sheet-head">
          <img class="logo" src="${LOGO_URL}" alt="" draggable="false">
          <div>
            <!-- Het bovenschrift: de naam van het abonnement als etiket, zonder abonnement COACH (v0.225.0). De
                 eigenaar op 15-11-2026: "de coach staat los snap je? Dus niks van domotiapp namen in de coach". -->
            <div class="eyebrow" id="bovenschrift">COACH</div>
            <h3 id="bot-titel">${t("Vraag het Coach Assist")}</h3>
          </div>
          <button class="sheet-close" type="button" id="bot-dicht" aria-label="${t("Sluiten")}">${icons.close}</button>
        </div>
        <div class="tabs" id="tabs" role="tablist">
          <button type="button" class="knop" role="tab" data-tab="vragen">${t("Vragen")}</button>
          <button type="button" class="knop" role="tab" data-tab="tickets">${t("Tickets")}</button>
        </div>
        <p class="melding" id="melding" role="status" hidden></p>
        <div class="scherm" id="s-vragen">
          <div class="gesprek" id="gesprek-vragen"></div>
          <div class="schrijf">
            <textarea id="vraag" maxlength="4000" aria-label="${t("Je vraag")}" placeholder="${t("Waar kunnen we je mee helpen?")}"></textarea>
            <button type="button" class="knop hoofd" id="stuur-vraag">${t("Versturen")}</button>
            <p class="over" id="over" hidden></p>
          </div>
          <div class="op" id="op" hidden>
            <p>${t(PAKKET_OP)}</p>
            <button type="button" class="knop hoofd" id="meld-storing">${t("Meld een storing")}</button>
          </div>
        </div>
        <div class="scherm" id="s-tickets" hidden>
          <div class="balk">
            <button type="button" class="knop" id="terug" hidden>${icons.arrowLeft}<span>${t("Alle tickets")}</span></button>
            <button type="button" class="knop hoofd" id="nieuw">${icons.plus}<span>${t("Nieuw ticket")}</span></button>
            <span class="over" id="tickets-over" hidden></span>
          </div>
          <p class="melding" id="tickets-op" hidden>${t(TICKETS_OP)}</p>
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
    // Een eerdere dag kiezen: die komt op zijn plek in het gesprek, en het gesprek gaat naar het begin ervan. Hij blijft
    // staan tot het venster weer opengaat.
    this.$("#gesprek-vragen").addEventListener("change", (event) => {
      if (!event.target?.matches?.("[data-dagkeuze]")) return;
      this.gekozenDag_ = event.target.value;
      this.paint_();
      const vak = this.$("#gesprek-vragen");
      const eerste = vak.querySelector(this.gekozenDag_ === "ouder" ? ".dag" : `.dag[data-dag="${this.gekozenDag_}"]`);
      vak.scrollTop = this.gekozenDag_ && eerste ? eerste.offsetTop - vak.offsetTop - 4 : vak.scrollHeight;
    });
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
    this.$("#meld-storing").addEventListener("click", () => {
      // De vraag die niet meer kon gaat mee naar de storing.
      const tekst = this.$("#vraag").value.trim();
      this.soort_ = "storing";
      this.tab_ = "tickets";
      this.toon_("nieuw");
      if (tekst && !this.$("#ticket-tekst").value.trim()) this.$("#ticket-tekst").value = tekst;
    });
    this.$("#stuur-vraag").addEventListener("click", () => {
      const tekst = this.$("#vraag").value.trim();
      if (!tekst || vragenOver(this.pakket_) === 0) return;
      this.laatsteVraag_ = tekst;
      this.fire("dac-ticket-reageer", { id: GESPREK, tekst, bijlagen: [] });
      this.$("#vraag").value = "";
      this.naarOnder_();
    });
    this.$("#stuur-nieuw").addEventListener("click", () => {
      const tekst = this.$("#ticket-tekst").value.trim();
      if ((!tekst && !this.fotos_.length) || pakketOver(this.pakket_, "tickets") === 0) return;
      this.laatsteTicket_ = tekst;
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
      this.naarOnder_();
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

  /** Het pakket uit de coach (v0.225.0), of null. Om middernacht gaat het veld vanzelf weer open. */
  set pakket(pakket) {
    this.pakket_ = pakket && typeof pakket === "object" ? pakket : null;
    clearTimeout(this.opnieuwKlok_);
    const over = Date.parse(this.pakket_?.opnieuw ?? "") - Date.now();
    if (over > 0 && over < 26 * 3600 * 1000) this.opnieuwKlok_ = setTimeout(() => this.paint_(), over + 1000);
    this.paint_();
  }

  /**
   * De coach weigerde een vraag (`reply`) of een nieuw ticket (`new`): de grens is bereikt (v0.225.0). Wat er getypt
   * was blijft staan.
   */
  pakketOp(tekst, soort = "reply") {
    const ticket = soort === "new";
    if (this.pakket_) this.pakket_ = { ...this.pakket_, [ticket ? "tickets_over" : "vragen_over"]: 0 };
    if (!this.rendered_) return;
    const veld = this.$(ticket ? "#ticket-tekst" : "#vraag");
    if (!veld.value.trim()) veld.value = ticket ? this.laatsteTicket_ : this.laatsteVraag_;
    this.$("#melding").hidden = true;
    this.paint_();
    if (!this.pakket_) this.meld_(String(tekst || t(ticket ? TICKETS_OP : PAKKET_OP)), true);
  }

  /** Een fout van de coach, met zijn eigen zin. */
  set fout(tekst) {
    if (tekst) this.meld_(String(tekst), true);
  }

  open() {
    this.gekozenDag_ = "";
    this.kiesTab_(this.tab_);
    const dialog = this.$("dialog");
    openSheet(dialog);
    // Pas nu staat het gesprek in beeld; zolang het verborgen was, kon het niet naar onderen (v0.224.0).
    this.naarOnder_();
    if (this.tab_ === "vragen") this.leesGesprek_();
  }

  /**
   * Openen op één ticket, vanuit een pushmelding (v0.229.0): 0 is het vragengesprek, een ander nummer dat ticket onder
   * Tickets, ook zonder Coach Assist in het abonnement (een storing). Het gesprek valt dan terug op de tickets
   * (`kiesTab_`). Zijn de tickets er nog niet, dan komt het ticket in beeld zodra ze er zijn (`paint_`).
   */
  openOp(id) {
    this.tab_ = id === GESPREK ? "vragen" : "tickets";
    this.open();
    if (id !== GESPREK) {
      this.openTicket_(id);
      this.naarOnder_();
    }
  }

  kiesTab_(tab) {
    // Zonder Coach Assist alleen Tickets (v0.226.0).
    this.tab_ = this.zonderCare_() ? "tickets" : tab;
    this.toon_("lijst");
    this.naarOnder_();
    if (this.tab_ === "vragen") this.leesGesprek_();
  }

  /**
   * Of het abonnement geen Coach Assist heeft (v0.226.0). De eigenaar op 15-11-2026: "Ja zonder care wel een storing
   * melden". Dan alleen Tickets, en een nieuw ticket alleen als storing; vragen en aanvragen kunnen niet.
   */
  zonderCare_() {
    return this.pakket_?.coach_assist === false;
  }

  /** Elk gesprek dat in beeld staat naar het laatste bericht, zoals WhatsApp opent (v0.224.0). */
  naarOnder_() {
    if (!this.rendered_) return;
    for (const vak of this.$$(".gesprek")) vak.scrollTop = vak.scrollHeight;
  }

  leesGesprek_() {
    if (this.gesprek_ && ticketNieuw(this.gesprek_, this.userId_)) this.fire("dac-ticket-gelezen", { id: GESPREK });
  }

  openTicket_(id) {
    this.open_ = id;
    this.toon_("gesprek");
    this.naarOnder_();
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
        const adres = await this.fotoAdres(img.dataset.foto);
        // Een plaatje dat laadt maakt het gesprek langer; stond hij onderaan, dan blijft hij daar.
        if (onderaan(houder)) img.addEventListener("load", () => { houder.scrollTop = houder.scrollHeight; }, { once: true });
        img.src = adres;
      } catch {
        // Zonder adres blijft het vlak leeg; de rest van het gesprek staat er gewoon.
      }
    }
  }

  paint_() {
    if (!this.rendered_) return;
    const zonderCare = this.zonderCare_();
    if (zonderCare) {
      this.tab_ = "tickets";
      this.soort_ = "storing";
    }
    this.$("dialog").classList.toggle("zonder-care", zonderCare);
    this.$("#tabs").hidden = zonderCare;
    this.$("#bot-titel").textContent = zonderCare ? t("Meld een storing") : t("Vraag het Coach Assist");
    for (const knop of this.$$("[data-soort]")) knop.hidden = zonderCare && knop.dataset.soort !== "storing";
    for (const knop of this.$$("[data-tab]")) knop.setAttribute("aria-selected", String(knop.dataset.tab === this.tab_));
    this.$("#s-vragen").hidden = this.tab_ !== "vragen";
    this.$("#s-tickets").hidden = this.tab_ !== "tickets";
    this.$("#t-lijst").hidden = this.scherm_ !== "lijst";
    this.$("#t-gesprek").hidden = this.scherm_ !== "gesprek";
    this.$("#t-nieuw").hidden = this.scherm_ !== "nieuw";
    this.$("#terug").hidden = this.scherm_ === "lijst";
    this.$("#nieuw").hidden = this.scherm_ === "nieuw";
    // Een antwoord dat binnenkomt: alleen naar onderen als hij daar al (bijna) stond.
    const vragen = this.$("#gesprek-vragen");
    const vragenOnder = onderaan(vragen);
    vragen.innerHTML = gesprekHtml(this.gesprek_ ?? { id: GESPREK, berichten: [] }, huisNu(),
      { userId: this.userId_, gekozen: this.gekozenDag_ });
    if (vragenOnder) vragen.scrollTop = vragen.scrollHeight;
    this.$("#lijst").innerHTML = ticketsHtml(this.tickets_, this.userId_);
    const ticket = this.tickets_.find((tk) => tk.id === this.open_);
    const vak = this.$("#gesprek-ticket");
    const ticketOnder = onderaan(vak);
    vak.innerHTML = ticket ? gesprekHtml(ticket, huisNu(), { userId: this.userId_ }) : "";
    if (ticketOnder) vak.scrollTop = vak.scrollHeight;
    this.vulFotos_(vak);
    for (const knop of this.$$("[data-soort]")) knop.setAttribute("aria-pressed", String(knop.dataset.soort === this.soort_));
    // Het pakket: de naam, wat er vandaag over is, en op nul het veld dicht met de weg naar een storing.
    const over = vragenOver(this.pakket_);
    const boven = this.$("#bovenschrift");
    boven.innerHTML = this.pakket_?.naam && !zonderCare ? `<span class="pakket">${esc(this.pakket_.naam)}</span>` : "COACH";
    const regel = this.$("#over");
    regel.textContent = vragenOverTekst(over);
    regel.hidden = !over;
    regel.classList.toggle("weinig", over != null && over <= WEINIG);
    this.$("#vraag").disabled = over === 0;
    this.$("#stuur-vraag").hidden = over === 0;
    this.$("#op").hidden = over !== 0;
    // Tickets: op nul geen Nieuw ticket en geen Meld een storing, met de reden; bij weinig over hoeveel nog.
    const tickets = pakketOver(this.pakket_, "tickets");
    const ticketsRegel = this.$("#tickets-over");
    ticketsRegel.textContent = ticketsOverTekst(tickets);
    ticketsRegel.hidden = !tickets || !ticketsRegel.textContent;
    ticketsRegel.classList.toggle("weinig", !ticketsRegel.hidden);
    this.$("#tickets-op").hidden = tickets !== 0 || this.scherm_ === "gesprek";
    if (tickets === 0) this.$("#nieuw").hidden = true;
    this.$("#stuur-nieuw").hidden = tickets === 0;
    this.$("#meld-storing").hidden = tickets === 0;
    const gekozen = this.fotos_.length ? t("{n} foto('s) erbij", { n: this.fotos_.length }) : "";
    for (const plek of this.$$("[data-gekozen]")) plek.textContent = gekozen;
    for (const knop of this.$$("[data-foto-kies]")) knop.hidden = !this.uploader || this.fotos_.length >= FOTOS_MAX;
  }
}

define("dac-tickets-sheet", DacTicketsSheet);
