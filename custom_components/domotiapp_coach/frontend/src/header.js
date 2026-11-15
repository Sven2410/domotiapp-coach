/**
 * The panel header.
 *
 * A custom panel replaces Home Assistant's own toolbar, so this header is the
 * only chrome the user gets. Customers run their dashboard behind Kiosk Mode,
 * which hides the HA header and sidebar and takes away tab navigation -- so the
 * header carries both the section navigation and an explicit way back to the
 * home dashboard.
 *
 * Alles past, op elke breedte (v0.226.0). De eigenaar op 15-11-2026, toen de tabbladen van de installateur bij
 * 1200 px gingen schuiven: "Ik wil dat alles past". Daarom geen vaste breekpunten meer maar stappen (`STANDEN`):
 * eerst de knoppen rechts alleen een icoon, dan het abonnement onder COACH, dan de tabbladen kleiner, dan de
 * tabbladen op een eigen rij zoals op een telefoon, en zo verder. Een `ResizeObserver` meet na elke stap of het past
 * en houdt de eerste die past (`kiesStand`); komt er een knop bij, dan klopt het nog steeds.
 *
 * Sinds v0.227.0 zijn de tabbladen altijd allemaal hetzelfde: met tekst ernaast, met de naam klein eronder, of alleen
 * een icoon met het actieve in kleur en een streep eronder; nooit één met tekst en de rest zonder. En elk tabblad heeft
 * een eigen icoon. De eigenaar op 15-11-2026 op zijn telefoon: "je hebt voor home en history hetzelfde icoontje" en
 * "sommige icoontjes hebben wel tekst, sommige niet".
 */

import { DacElement, define } from "./base.js";
import { LOGO_URL } from "./theme.js";
import { icons } from "./icons.js";
import { nt, t } from "./i18n.js";

export const NAV_ITEMS = [
  { id: "overzicht", label: nt("Overzicht"), icon: "tegels" },
  { id: "historie", label: nt("Historie"), icon: "historie" },
  { id: "meldingen", label: nt("Meldingen"), icon: "megafoon" },
  // Heette Strategie tot v0.114.0; het id blijft, zodat een bladwijzer werkt.
  { id: "strategie", label: nt("Voorkeuren"), icon: "compass" },
  // Van de installateur, en de bewoner ziet ze niet, ook niet grijs (v0.114.0).
  // De eigenaar op 08-10-2026: "voorop staat dat de klant geen entiteiten moet
  // kunnen kiezen". Wat hij wel instelt staat achter de kaart (Instellen), onder
  // Voorkeuren en onder Meldingen. Instellingen is opgegaan in Installatie.
  { id: "apparaten", label: nt("Apparaten"), icon: "devices", adminOnly: true },
  { id: "installatie", label: nt("Installatie"), icon: "plug", adminOnly: true },
  // Sinds v0.130.1 ook voor de bewoner, om te lezen en zijn prijs te
  // bevestigen; wijzigen blijft van de installateur (`views/contract.js`).
  { id: "contract", label: nt("Contract"), icon: "euro" },
];

/**
 * De standen van de kop, van ruim naar krap (v0.226.0). Elke stand is een rij attributen op de kop:
 * `ki` knoppen rechts alleen een icoon, `ao` het abonnement onder COACH, `onder` elk tabblad een icoon met de naam
 * klein eronder, `ti` alle tabbladen alleen een icoon, `rijen` de tabbladen op een eigen rij, `krap` minder ruimte rond de
 * tabbladen, `aw` geen abonnement naast COACH (het staat ook bij Coach Assist en op Contract), `zn` alleen het logo.
 */
export const STANDEN = [
  [],
  ["ki"],
  ["ki", "ao"],
  ["ki", "ao", "onder"],
  ["ki", "ao", "ti"],
  ["rijen"],
  ["rijen", "ki"],
  ["rijen", "ki", "ao"],
  ["rijen", "ki", "ao", "onder"],
  ["rijen", "ki", "ao", "onder", "krap"],
  ["rijen", "ki", "ao", "ti"],
  ["rijen", "ki", "ao", "ti", "krap"],
  ["rijen", "ki", "ti", "krap", "aw"],
  ["rijen", "ki", "ti", "krap", "zn"],
];

/** De eerste stand waarin `past(stand)` waar is, anders de laatste. */
export function kiesStand(standen, past) {
  for (const stand of standen) if (past(stand)) return stand;
  return standen[standen.length - 1];
}

/** The sections this user may open. */
export const navItemsFor = (isAdmin) =>
  NAV_ITEMS.filter((item) => isAdmin || !item.adminOnly);


class DacHeader extends DacElement {
  static css = /* css */ `
    :host {
      position: sticky;
      top: 0;
      z-index: 20;
      /* Behind a Dynamic Island or a notch there is no room for anything
         readable, so the header's own background fills that strip and the bar
         starts below it. Zero everywhere that has no cutout. */
      padding-top: var(--dac-safe-t);
      background: linear-gradient(180deg, rgba(var(--dac-bg-rgb),0.96) 0%, rgba(var(--dac-bg-rgb),0.82) 100%);
      backdrop-filter: blur(22px) saturate(150%);
      -webkit-backdrop-filter: blur(22px) saturate(150%);
      border-bottom: 1px solid var(--dac-border);
    }

    /* Hairline of brand colour under the header. */
    :host::after {
      content: "";
      position: absolute;
      inset: auto 0 -1px 0;
      height: 1px;
      background: linear-gradient(90deg,
        transparent 0%, var(--dac-accent) 22%, var(--dac-accent-hi) 50%,
        var(--dac-accent) 78%, transparent 100%);
      opacity: 0.55;
    }

    .bar {
      max-width: var(--dac-maxw);
      margin: 0 auto;
      min-height: var(--dac-header-h);
      /* In landscape the island eats a strip down one side of the screen. */
      padding: 0 max(20px, var(--dac-safe-r)) 0 max(20px, var(--dac-safe-l));
      display: flex;
      align-items: center;
      gap: 16px;
    }

    /* ---- brand ---- */
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      flex: 0 0 auto;
      user-select: none;
      min-width: 0;
    }
    .brand img {
      width: 34px;
      height: 34px;
      flex: 0 0 auto;
      object-fit: contain;
      display: block;
    }
    .brand-text {
      display: flex;
      align-items: baseline;
      gap: 5px;
      line-height: 1.1;
      white-space: nowrap;
      min-width: 0;
    }
    /* COACH, de naam van het systeem (v0.223.0; daarvoor DomotiApp Coach, in twee kleuren). */
    .brand-2 {
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.06em;
      color: var(--dac-accent-hi);
    }
    /* Het abonnement naast COACH (v0.225.0), alleen als er een is. */
    .abo {
      align-self: center; font-size: 11px; font-weight: 600; letter-spacing: 0.02em; padding: 2px 8px;
      border-radius: 999px; color: var(--dac-accent-hi); background: var(--dac-accent-soft);
      border: 1px solid rgba(25,143,217,0.35); white-space: nowrap;
    }
    .abo[hidden], #bot[hidden] { display: none; }

    /* ---- nav ---- */
    nav {
      position: relative;
      flex: 1 1 auto;
      display: flex;
      justify-content: center;
      gap: 2px;
      overflow-x: auto;
      overscroll-behavior-x: contain;
      scrollbar-width: none;
      -webkit-overflow-scrolling: touch;
      padding: 4px 0;
    }
    nav::-webkit-scrollbar { display: none; }

    .pill-bg {
      position: absolute;
      top: 4px;
      left: 0;
      height: calc(100% - 8px);
      border-radius: var(--dac-radius-pill);
      background: var(--dac-accent-soft);
      border: 1px solid rgba(25,143,217,0.38);
      box-shadow: 0 0 22px -6px var(--dac-accent-glow);
      transition: transform 380ms cubic-bezier(0.22,0.61,0.36,1),
                  width 380ms cubic-bezier(0.22,0.61,0.36,1),
                  opacity 200ms ease;
      opacity: 0;
      pointer-events: none;
    }
    .pill-bg.on { opacity: 1; }

    button.pill {
      position: relative;
      z-index: 1;
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 15px;
      border: 0;
      background: transparent;
      border-radius: var(--dac-radius-pill);
      font: inherit;
      font-size: 13.5px;
      font-weight: 500;
      color: var(--dac-ink-2);
      cursor: pointer;
      white-space: nowrap;
      transition: color 200ms ease;
      -webkit-tap-highlight-color: transparent;
    }
    button.pill .icon { width: 17px; height: 17px; opacity: 0.75; transition: opacity 200ms ease; }
    button.pill:hover { color: var(--dac-ink); }
    button.pill:hover .icon { opacity: 1; }
    button.pill[aria-current="page"] { color: var(--dac-ink); font-weight: 600; }
    button.pill[aria-current="page"] .icon { opacity: 1; color: var(--dac-accent-hi); }

    /* ---- actions ---- */
    .actions { flex: 0 0 auto; display: flex; align-items: center; gap: 8px; }

    button.ghost {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 15px 9px 12px;
      border-radius: var(--dac-radius-pill);
      border: 1px solid var(--dac-border-hi);
      background: var(--dac-surface);
      color: var(--dac-ink-2);
      font: inherit;
      font-size: 13.5px;
      font-weight: 500;
      cursor: pointer;
      transition: border-color 200ms ease, color 200ms ease, background 200ms ease;
      -webkit-tap-highlight-color: transparent;
    }
    button.ghost .icon { width: 18px; height: 18px; }
    button.bel { position: relative; }
    button.bel .teller {
      position: absolute; top: -5px; right: -5px; min-width: 18px; height: 18px; padding: 0 5px;
      border-radius: 9px; background: rgb(229,72,77); color: #fff; font-style: normal;
      font-size: 11px; font-weight: 700; line-height: 18px; text-align: center; box-sizing: border-box;
    }
    button.bel .teller[hidden] { display: none; }
    button.ghost:hover {
      color: var(--dac-ink);
      border-color: rgba(25,143,217,0.55);
      background: var(--dac-accent-soft);
    }

    /* ---- de standen (v0.226.0, zie STANDEN) ---- */
    :host([ki]) button.ghost > span { display: none; }
    :host([ki]) button.ghost { padding: 9px; }
    :host([ao]) .brand-text { flex-direction: column; align-items: flex-start; gap: 2px; }
    :host([ao]) .abo { align-self: flex-start; font-size: 10px; padding: 1px 6px; }
    :host([ti]) button.pill > span { display: none; }
    :host([ti]) button.pill { padding: 9px 12px; }
    /* Icoon met de naam klein eronder, zoals een tabbalk in een app (v0.227.0). */
    :host([onder]) button.pill { flex-direction: column; gap: 2px; padding: 6px 8px 5px; font-size: 11px; line-height: 1.1; }
    :host([onder]) button.pill .icon { width: 18px; height: 18px; }
    :host([rijen][onder]) button.pill, :host([rijen][ti]) button.pill { flex: 1 1 0; justify-content: center; }
    /* Zonder tekst ernaast geen pil maar kleur en een streep eronder bij het actieve tabblad. */
    :host([onder]) .pill-bg, :host([ti]) .pill-bg { display: none; }
    :host([onder]) button.pill[aria-current="page"], :host([ti]) button.pill[aria-current="page"] { color: var(--dac-accent-hi); }
    :host([onder]) button.pill[aria-current="page"]::after, :host([ti]) button.pill[aria-current="page"]::after {
      content: ""; position: absolute; left: 22%; right: 22%; bottom: 0; height: 2px; border-radius: 1px;
      background: var(--dac-accent-hi);
    }
    :host([rijen]) .bar {
      flex-wrap: wrap;
      padding: 10px max(16px, var(--dac-safe-r)) 0 max(16px, var(--dac-safe-l));
      gap: 10px;
    }
    :host([rijen]) .brand { order: 1; margin-right: auto; }
    :host([rijen]) .actions { order: 2; }
    :host([rijen]) nav { order: 3; flex-basis: 100%; }
    :host([krap]) .bar { padding-left: max(12px, var(--dac-safe-l)); padding-right: max(12px, var(--dac-safe-r)); }
    :host([krap]) nav { gap: 0; }
    :host([krap]) button.pill { padding: 8px 10px; }
    :host([krap]) .brand img { width: 30px; height: 30px; }
    :host([aw]) .abo { display: none; }
    :host([zn]) .brand-text { display: none; }
  `;

  constructor() {
    super();
    this.isAdmin_ = true;
  }

  set active(value) {
    if (this.active_ === value) return;
    this.active_ = value;
    this.syncActive_();
  }

  get active() {
    return this.active_;
  }

  /** Hoeveel berichten er ongelezen zijn (v0.130.0); het belletje laat het zien. */
  set ongelezen(aantal) {
    this.ongelezen_ = Number(aantal) || 0;
    this.paintTeller_();
  }

  paintTeller_() {
    const teller = this.rendered_ ? this.$("#teller") : null;
    if (!teller) return;
    teller.hidden = !this.ongelezen_;
    teller.textContent = this.ongelezen_ > 9 ? "9+" : String(this.ongelezen_ || "");
    this.$("#berichten").setAttribute("aria-label", this.ongelezen_ ? t("Berichten, {n} ongelezen", { n: this.ongelezen_ }) : t("Berichten"));
  }

  /** Hoeveel tickets een antwoord hebben dat je nog niet las (v0.220.0). */
  set botOngelezen(aantal) {
    this.botOngelezen_ = Number(aantal) || 0;
    this.paintBot_();
  }

  /**
   * Het abonnement van dit huis (v0.225.0), uit de coach (`pakket` bij de tickets), of null: de naam als etiket naast
   * COACH, en zonder Coach Assist in het abonnement heet de knop Meld een storing. De eigenaar op 15-11-2026: "ja maar
   * ook in de coach zelf", "Dan moet er geen AI assistant in zitten etc", en "Ja zonder care wel een storing melden".
   */
  set pakket(pakket) {
    this.pakket_ = pakket && typeof pakket === "object" ? pakket : null;
    this.paintBot_();
  }

  paintBot_() {
    const teller = this.rendered_ ? this.$("#bot-teller") : null;
    if (!teller) return;
    const abo = this.$("#abo");
    const naam = this.pakket_?.naam ?? "";
    if (abo.textContent !== naam || abo.hidden !== !naam) {
      abo.textContent = naam;
      abo.hidden = !naam;
      this.pas_();
    }
    // Zonder Coach Assist blijft de knop, voor een storing (v0.226.0: "Ja zonder care wel een storing melden").
    const knop = this.$("#bot");
    const naamKnop = this.pakket_?.coach_assist === false ? t("Meld een storing") : t("Vraag het Coach Assist");
    if (knop.title !== naamKnop) {
      knop.title = naamKnop;
      knop.setAttribute("aria-label", naamKnop);
      knop.querySelector("span").textContent = this.pakket_?.coach_assist === false ? naamKnop : "Coach Assist";
      this.pas_();
    }
    teller.hidden = !this.botOngelezen_;
    teller.textContent = this.botOngelezen_ > 9 ? "9+" : String(this.botOngelezen_ || "");
  }

  /** Rebuild the bar when the user's rights become known. */
  set isAdmin(value) {
    const next = value !== false;
    if (next === this.isAdmin_ && this.rendered_) return;
    this.isAdmin_ = next;
    if (!this.rendered_) return;

    // Rebuilt rather than hidden, so the sliding highlight measures against the
    // pills that are actually there.
    this.observer_?.disconnect();
    this.shadowRoot.replaceChildren();
    this.rendered_ = false;
    this.connectedCallback();
    this.syncActive_();
  }

  render() {
    const pills = navItemsFor(this.isAdmin_).map(
      (item) => `
        <button class="pill" type="button" data-id="${item.id}" title="${t(item.label)}" aria-label="${t(item.label)}">
          ${icons[item.icon]}<span>${t(item.label)}</span>
        </button>`
    ).join("");

    return `
      <div class="bar">
        <div class="brand">
          <img src="${LOGO_URL}" alt="" draggable="false">
          <div class="brand-text">
            <span class="brand-2">COACH</span>
            <span class="abo" id="abo" hidden></span>
          </div>
        </div>
        <nav aria-label="${t("Dashboardsecties")}">
          <div class="pill-bg" aria-hidden="true"></div>
          ${pills}
        </nav>
        <div class="actions">
          <!-- De berichtenbox (v0.130.0). Het getal is een <i> en geen <span>:
               op een smal scherm verdwijnt de tekst van een knop hier. -->
          <!-- Coach Assist (v0.220.0; de naam sinds v0.223.0), met een stip zolang er een antwoord is dat je nog niet las. -->
          <button class="ghost bel" type="button" id="bot" title="${t("Vraag het Coach Assist")}" aria-label="${t("Vraag het Coach Assist")}">
            ${icons.chat}<span>Coach Assist</span><i class="teller" id="bot-teller" hidden></i>
          </button>
          <button class="ghost bel" type="button" id="berichten" title="${t("Berichten")}" aria-label="${t("Berichten")}">
            ${icons.bell}<span>${t("Berichten")}</span><i class="teller" id="teller" hidden></i>
          </button>
          <button class="ghost" type="button" id="home" title="${t("Terug naar je eigen dashboard")}">
            ${icons.home}<span>Home</span>
          </button>
        </div>
      </div>
    `;
  }

  afterRender() {
    this.$("#home").addEventListener("click", () => this.fire("dac-home"));
    this.$("#berichten").addEventListener("click", () => this.fire("dac-berichten"));
    this.$("#bot").addEventListener("click", () => this.fire("dac-bot"));
    this.paintTeller_();
    this.paintBot_();

    for (const pill of this.$$("button.pill")) {
      pill.addEventListener("click", () =>
        this.fire("dac-navigate", { id: pill.dataset.id })
      );
    }

    this.syncActive_();
  }

  onConnect() {
    // The sliding highlight is measured, so it has to be re-measured whenever
    // the bar reflows (window resize, sidebar collapse, orientation change).
    // En of alles past (v0.226.0): op de breedte van de kop zelf, want de stand verandert de hoogte, niet de breedte.
    this.observer_ ??= new ResizeObserver(() => this.pas_());
    this.observer_.observe(this);
    this.observer_.observe(this.$("nav"));
    // De letters komen soms pas na de eerste meting binnen, en dan worden de knoppen breder of smaller.
    document.fonts?.ready?.then(() => this.pas_());
    this.pas_();
  }

  /** De eerste stand waarin de kop past (`STANDEN`), en daarna de markering onder het actieve tabblad. */
  pas_() {
    if (!this.rendered_ || !this.isConnected) return;
    const zet = (stand) => {
      for (const naam of ["ki", "ao", "onder", "ti", "rijen", "krap", "aw", "zn"]) this.toggleAttribute(naam, stand.includes(naam));
    };
    const bar = this.$(".bar");
    const nav = this.$("nav");
    const brand = this.$(".brand");
    const acties = this.$(".actions");
    const tekst = this.$(".brand-text");
    const past = (stand) => {
      zet(stand);
      if (!bar.clientWidth) return true;
      if (bar.scrollWidth > bar.clientWidth + 1 || nav.scrollWidth > nav.clientWidth + 1) return false;
      // COACH en het abonnement afgeknipt naast het logo telt ook als niet passen.
      if (tekst.scrollWidth > tekst.clientWidth + 1) return false;
      // Het logo en de knoppen horen op één rij; staan ze onder elkaar, dan past het niet.
      return Math.abs(brand.getBoundingClientRect().top - acties.getBoundingClientRect().top) < 12;
    };
    this.stand_ = kiesStand(STANDEN, past);
    zet(this.stand_);
    this.syncActive_();
  }

  onDisconnect() {
    this.observer_?.disconnect();
  }

  /** Move the highlight under the active pill and update ARIA state. */
  syncActive_() {
    if (!this.rendered_) return;
    const bg = this.$(".pill-bg");
    let target = null;

    for (const pill of this.$$("button.pill")) {
      const on = pill.dataset.id === this.active_;
      if (on) {
        pill.setAttribute("aria-current", "page");
        target = pill;
      } else {
        pill.removeAttribute("aria-current");
      }
    }

    if (!target) {
      bg.classList.remove("on");
      return;
    }
    bg.classList.add("on");
    bg.style.width = `${target.offsetWidth}px`;
    bg.style.transform = `translateX(${target.offsetLeft}px)`;

    // On a phone the row scrolls, so the active section has to be brought into
    // view or navigating can leave the highlight off screen.
    const nav = this.$("nav");
    if (nav.scrollWidth > nav.clientWidth) {
      const left = target.offsetLeft - (nav.clientWidth - target.offsetWidth) / 2;
      nav.scrollTo({ left: Math.max(0, left), behavior: "smooth" });
    }
  }
}

define("dac-header", DacHeader);
