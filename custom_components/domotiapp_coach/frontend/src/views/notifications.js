/**
 * Meldingen -- alles wat de coach ooit naar de telefoon stuurde, de nieuwste
 * bovenaan.
 *
 * Een melding op een telefoon is weg zodra hij weggeveegd is, en wie 's ochtends
 * ziet dat de auto niet vol is wil weten wat er 's nachts gezegd is. Sven op
 * 04-09-2026: "daarom wil ik ook een soort geschiedenis meldingen scherm."
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
    });
  }
  return groepen;
}

const css = /* css */ `
  .page { padding: 18px 16px calc(24px + var(--dac-safe-b, 0px)); max-width: 760px; margin: 0 auto; }
  h1 { font-size: 22px; margin: 0 0 4px; display: flex; align-items: center; gap: 10px; }
  h1 svg { width: 22px; height: 22px; color: var(--dac-accent); }
  .sub { margin: 0 0 18px; color: var(--dac-ink-3); font-size: 13.5px; }
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
  .tijd { font-variant-numeric: tabular-nums; color: var(--dac-ink-3); font-size: 13px; padding-top: 1px; }
  .tekst { font-size: 14px; line-height: 1.45; overflow-wrap: anywhere; }
  .leeg { color: var(--dac-ink-3); font-size: 14px; padding: 18px 0; }
  @media (max-width: 320px) {
    .rij { grid-template-columns: 44px 1fr; gap: 8px; padding: 8px 10px; }
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
        <p class="sub">Alles wat de coach gemeld heeft, de nieuwste bovenaan.</p>
        <div id="lijst"></div>
      </section>
    `;
  }

  afterRender() {
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

  paint_() {
    const lijst = this.$("#lijst");
    if (!lijst) return;
    lijst.replaceChildren();
    const groepen = groepeer(this.items_);
    if (!groepen.length) {
      const leeg = document.createElement("div");
      leeg.className = "leeg";
      leeg.textContent = this.geladen_
        ? "De coach heeft nog niets gemeld."
        : "De meldingen worden opgehaald.";
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
        el.className = "rij";
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
