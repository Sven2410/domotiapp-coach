/**
 * Meldingen -- alles wat de coach deed en meldde, de nieuwste bovenaan.
 *
 * Een melding op een telefoon is weg zodra hij weggeveegd is, en wie 's ochtends
 * ziet dat de auto niet vol is wil weten wat er 's nachts gezegd is. Sven op
 * 04-09-2026: "daarom wil ik ook een soort geschiedenis meldingen scherm."
 *
 * Drie soorten regels, uit `kind` op de server:
 *   besluit  wat de coach deed en waarom; alleen hier, niet op de telefoon
 *   melding  ging ook naar de telefoon: vol, afgekoppeld, doet het weer
 *   kritiek  idem, en de bewoner moet er iets mee: sensor stil, niet op tijd vol
 * Sven op 05-09-2026: "dat je op normale en kritieke meldingen kan filteren
 * en op de tijd." Vandaar de knoppen boven de lijst en de dagkeuze.
 *
 * De lijst komt van `domotiapp_coach/notifications/list` en groeit live mee via
 * het event `domotiapp_coach_notification`; het scherm bewaart zelf niets.
 */

import { DacElement, define } from "../base.js";
import { icons } from "../icons.js";

const EVENT_NOTIFICATION = "domotiapp_coach_notification";

const DAGEN = ["zondag", "maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag"];
const MAANDEN = [
  "januari", "februari", "maart", "april", "mei", "juni",
  "juli", "augustus", "september", "oktober", "november", "december",
];

const twee = (n) => String(n).padStart(2, "0");

/** De soort van een regel; oudere regels hebben het veld niet en zijn meldingen. */
export function soortVan(item) {
  return item?.kind === "besluit" || item?.kind === "kritiek" ? item.kind : "melding";
}

/** "Vandaag", "Gisteren", of "vrijdag 4 september". */
export function dagkop(moment, nu = new Date()) {
  const dag = new Date(moment.getFullYear(), moment.getMonth(), moment.getDate());
  const vandaag = new Date(nu.getFullYear(), nu.getMonth(), nu.getDate());
  const verschil = Math.round((vandaag - dag) / 86400000);
  if (verschil === 0) return "Vandaag";
  if (verschil === 1) return "Gisteren";
  const kop = `${DAGEN[dag.getDay()]} ${dag.getDate()} ${MAANDEN[dag.getMonth()]}`;
  return dag.getFullYear() === vandaag.getFullYear() ? kop : `${kop} ${dag.getFullYear()}`;
}

/** "2026-09-05": de sleutel van een dag, voor de dagkeuze. */
const dagsleutel = (moment) =>
  `${moment.getFullYear()}-${twee(moment.getMonth() + 1)}-${twee(moment.getDate())}`;

/**
 * Wat er overblijft na het filter. `soort` is "alles", "besluit", "melding"
 * of "kritiek"; "melding" laat ook kritiek zien, want dat is een melding
 * die bovendien dringend is. `dag` is een dagsleutel of leeg voor alle dagen.
 */
export function zeef(items, { soort = "alles", dag = "" } = {}) {
  return (items ?? []).filter((item) => {
    const s = soortVan(item);
    if (soort === "besluit" && s !== "besluit") return false;
    if (soort === "melding" && s === "besluit") return false;
    if (soort === "kritiek" && s !== "kritiek") return false;
    if (dag) {
      const moment = new Date(item?.at ?? "");
      if (Number.isNaN(moment.getTime()) || dagsleutel(moment) !== dag) return false;
    }
    return true;
  });
}

/** De dagen die in de lijst voorkomen, de nieuwste eerst, voor de dagkeuze. */
export function dagen(items, nu = new Date()) {
  const uit = [];
  const gezien = new Set();
  for (const item of items ?? []) {
    const moment = new Date(item?.at ?? "");
    if (Number.isNaN(moment.getTime())) continue;
    const sleutel = dagsleutel(moment);
    if (gezien.has(sleutel)) continue;
    gezien.add(sleutel);
    uit.push({ sleutel, kop: dagkop(moment, nu) });
  }
  return uit;
}

/**
 * De meldingen per dag, de nieuwste dag en de nieuwste melding eerst. Een
 * melding zonder leesbaar tijdstip valt weg: liever een regel minder dan een
 * streepje in de tijdkolom.
 */
export function groepeer(items, nu = new Date()) {
  const groepen = [];
  for (const item of items ?? []) {
    const moment = new Date(item?.at ?? "");
    if (Number.isNaN(moment.getTime()) || !item?.message) continue;
    const kop = dagkop(moment, nu);
    let groep = groepen[groepen.length - 1];
    if (!groep || groep.kop !== kop) {
      groep = { kop, rijen: [] };
      groepen.push(groep);
    }
    groep.rijen.push({
      tijd: `${twee(moment.getHours())}:${twee(moment.getMinutes())}`,
      tekst: item.message,
      soort: soortVan(item),
    });
  }
  return groepen;
}

const SOORTEN = [
  ["alles", "Alles"],
  ["besluit", "Besluiten"],
  ["melding", "Meldingen"],
  ["kritiek", "Kritiek"],
];

const css = /* css */ `
  .page { padding: 18px 16px calc(24px + var(--dac-safe-b, 0px)); max-width: 760px; margin: 0 auto; }
  h1 { font-size: 22px; margin: 0 0 4px; display: flex; align-items: center; gap: 10px; }
  h1 svg { width: 22px; height: 22px; color: var(--dac-accent); }
  .sub { margin: 0 0 14px; color: var(--dac-ink-3); font-size: 13.5px; }
  .filter { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 0 0 16px; }
  .filter button {
    font: inherit; font-size: 13px; padding: 6px 12px; border-radius: 999px; cursor: pointer;
    border: 1px solid var(--dac-border); background: transparent; color: var(--dac-ink-2, inherit);
  }
  .filter button.aan { border-color: var(--dac-accent); background: var(--dac-accent-soft); color: var(--dac-ink); }
  .filter select {
    font: inherit; font-size: 13px; padding: 6px 10px; border-radius: 999px; margin-left: auto;
    border: 1px solid var(--dac-border); background: transparent; color: var(--dac-ink); max-width: 100%;
  }
  .dag {
    font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; font-weight: 700;
    color: var(--dac-ink-3); margin: 18px 0 6px;
  }
  .dag:first-child { margin-top: 0; }
  .rij {
    display: grid; grid-template-columns: 52px 1fr; gap: 10px; align-items: start;
    padding: 10px 12px; border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border); background: rgba(255,255,255,0.03);
    margin-bottom: 6px;
  }
  /* Een besluit is wat de coach deed; een melding ging ook naar de telefoon
     en mag daarom opvallen; kritiek is een melding waar je iets mee moet. */
  .rij.besluit { background: transparent; border-color: transparent; padding-top: 6px; padding-bottom: 6px; margin-bottom: 2px; }
  .rij.besluit .tekst { color: var(--dac-ink-2, inherit); font-size: 13.5px; }
  .rij.kritiek { border-color: var(--dac-warn); border-left-width: 4px; }
  .tijd { font-variant-numeric: tabular-nums; color: var(--dac-ink-3); font-size: 13px; padding-top: 1px; }
  .tekst { font-size: 14px; line-height: 1.45; overflow-wrap: anywhere; }
  .leeg { color: var(--dac-ink-3); font-size: 14px; padding: 18px 0; }
  @media (max-width: 320px) {
    .rij { grid-template-columns: 44px 1fr; gap: 8px; padding: 8px 10px; }
    .filter select { margin-left: 0; }
  }
`;

class DacViewNotifications extends DacElement {
  static css = css;

  constructor() {
    super();
    this.hass_ = null;
    this.items_ = [];
    this.geladen_ = false;
    this.off_ = null;
    this.filter_ = { soort: "alles", dag: "" };
  }

  set hass(value) {
    this.hass_ = value;
    if (this.rendered_ && !this.geladen_) this.laad_();
  }

  get hass() {
    return this.hass_;
  }

  /** Het paneel zet de instellingen op elke weergave; dit scherm heeft ze niet nodig. */
  set settings(value) {
    this.settings_ = value;
  }

  render() {
    return /* html */ `
      <section class="page">
        <h1>${icons.bell} Meldingen</h1>
        <p class="sub">Alles wat de coach deed en meldde, de nieuwste bovenaan. Wat ook naar je telefoon ging staat in een kader; kritiek is wat je zelf moet oplossen.</p>
        <div class="filter" id="filter">
          ${SOORTEN.map(([id, label]) =>
            `<button type="button" data-soort="${id}"${id === "alles" ? ' class="aan"' : ""}>${label}</button>`).join("")}
          <select id="dag" aria-label="Dag"><option value="">Alle dagen</option></select>
        </div>
        <div id="lijst"></div>
      </section>
    `;
  }

  afterRender() {
    this.$("#filter")?.addEventListener("click", (e) => {
      const knop = e.target?.closest?.("button[data-soort]");
      if (!knop) return;
      this.filter_ = { ...this.filter_, soort: knop.dataset.soort };
      this.paint_();
    });
    this.$("#dag")?.addEventListener("change", (e) => {
      this.filter_ = { ...this.filter_, dag: e.target.value };
      this.paint_();
    });
    this.paint_();
  }

  onConnect() {
    this.laad_();
    this.volg_();
  }

  onDisconnect() {
    if (this.off_) {
      this.off_();
      this.off_ = null;
    }
  }

  async laad_() {
    if (!this.hass_?.callWS) return;
    try {
      this.items_ = await this.hass_.callWS({ type: "domotiapp_coach/notifications/list" });
      this.geladen_ = true;
      this.paint_();
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de meldingen niet laden", error);
    }
  }

  async volg_() {
    if (!this.hass_?.connection?.subscribeEvents || this.off_) return;
    try {
      this.off_ = await this.hass_.connection.subscribeEvents((event) => {
        const item = event?.data;
        if (!item?.message) return;
        this.items_ = [item, ...this.items_];
        this.paint_();
      }, EVENT_NOTIFICATION);
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de meldingen niet volgen", error);
    }
  }

  /** De dagkeuze bijwerken zonder de gekozen dag kwijt te raken. */
  dagen_() {
    const keuze = this.$("#dag");
    if (!keuze) return;
    const gekozen = this.filter_.dag;
    const opties = dagen(this.items_);
    if (gekozen && !opties.some((d) => d.sleutel === gekozen)) this.filter_ = { ...this.filter_, dag: "" };
    keuze.replaceChildren();
    const alle = document.createElement("option");
    alle.value = "";
    alle.textContent = "Alle dagen";
    keuze.append(alle);
    for (const d of opties) {
      const optie = document.createElement("option");
      optie.value = d.sleutel;
      optie.textContent = d.kop;
      keuze.append(optie);
    }
    keuze.value = this.filter_.dag;
  }

  paint_() {
    const lijst = this.$("#lijst");
    if (!lijst) return;
    for (const knop of this.$$("#filter button[data-soort]") ?? []) {
      knop.classList.toggle("aan", knop.dataset.soort === this.filter_.soort);
    }
    this.dagen_();
    lijst.replaceChildren();
    const groepen = groepeer(zeef(this.items_, this.filter_));
    if (!groepen.length) {
      const leeg = document.createElement("div");
      leeg.className = "leeg";
      leeg.textContent = !this.geladen_
        ? "De meldingen worden opgehaald."
        : this.items_.length
          ? "Niets dat aan dit filter voldoet."
          : "De coach heeft nog niets gemeld.";
      lijst.append(leeg);
      return;
    }
    for (const groep of groepen) {
      const kop = document.createElement("div");
      kop.className = "dag";
      kop.textContent = groep.kop;
      lijst.append(kop);
      for (const rij of groep.rijen) {
        const el = document.createElement("div");
        el.className = `rij ${rij.soort}`;
        const tijd = document.createElement("span");
        tijd.className = "tijd";
        tijd.textContent = rij.tijd;
        const tekst = document.createElement("span");
        tekst.className = "tekst";
        tekst.textContent = rij.tekst;
        el.append(tijd, tekst);
        lijst.append(el);
      }
    }
  }
}

define("dac-view-notifications", DacViewNotifications);
