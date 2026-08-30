/**
 * Strategie -- what the coach should do on its own, without being watched.
 *
 * The screen is a list, not a form. Every notification is one line that says
 * what it is set to, and its settings live behind that line. There is one
 * notification today and there will be more, and a screen that grows a full
 * block of fields per notification stops being readable at the third one --
 * while a list of one-liners stays scannable at the tenth.
 *
 * The notifications themselves are sent by the integration, not from here, so
 * they also arrive when nobody has the dashboard open.
 */

import { define } from "../base.js";
import { icons } from "../icons.js";
import {
  DacEditorElement,
  adminNoticeHtml,
  editorCss,
  saveBarHtml,
} from "./editor-base.js";

/** Sensible spacings, in minutes. */
const INTERVALS = [5, 10, 15, 30, 60, 120, 240];

/**
 * How long the load has to hold before anything is sent, in seconds.
 *
 * An oven element, a motor starting, an induction hob stepping up: all of them
 * throw a spike of a second or two that no fuse minds and that is over before
 * anyone could act on it. Nothing under five seconds is offered, because
 * everything under five seconds is one of those.
 */
const HOLDS = [5, 10, 30, 60, 120, 300];

/**
 * Hoever de coach mag gaan.
 *
 * Geen strategie maar een mate van vertrouwen, en dat zijn twee vragen: een
 * strategie zegt waar hij op mikt, dit zegt hoeveel hij zelf mag. Voorstellen
 * is de stap die er in de praktijk toe doet: daarmee kun je een week meekijken
 * of de sommen kloppen voordat je hem loslaat.
 */
const LEVELS = [
  {
    key: "read",
    label: "Alleen uitlezen",
    blurb: "Je ziet wat je huis doet. De coach zegt en doet verder niets.",
  },
  {
    key: "advise",
    label: "Adviseren",
    blurb: "Hij vertelt wat er te winnen valt, maar raakt niets aan.",
  },
  {
    key: "propose",
    label: "Voorstellen",
    blurb: "Hij rekent het uit en laat het zien. Pas als jij ja zegt, voert hij het uit.",
  },
  {
    key: "steer",
    label: "Zelf sturen",
    blurb: "Hij doet het en vertelt achteraf wat hij gedaan heeft.",
  },
];

/**
 * The notifications, in the order they are listed.
 *
 * `summary` is what the customer reads instead of opening it, so it has to
 * carry the settings that decide whether the notification does anything at all.
 * Adding a notification means an entry here plus its own pane in `render`.
 */
const ALERTS = [
  {
    id: "belasting",
    icon: "warning",
    title: "Zware belasting",
    blurb: "Een bericht zodra je aansluiting te zwaar belast wordt.",
    summary(view) {
      const alert = view.alert_();
      if (!alert.enabled) return { text: "Uit. Je krijgt hier geen bericht van.", warn: false };

      const parts = [`vanaf ${Number(alert.threshold_percent) || 0}%`];
      const count = (alert.targets ?? []).length;
      parts.push(count ? (count === 1 ? "1 ontvanger" : `${count} ontvangers`) : "niemand geselecteerd");
      parts.push(`na ${holdLabel(alert.min_duration_seconds ?? 60)}`);
      parts.push(`hoogstens eens per ${label(alert.min_interval_minutes)}`);
      return { text: parts.join(" · "), warn: count === 0 };
    },
  },
];

class DacViewStrategy extends DacEditorElement {
  static sections = ["strategy"];

  // Its own command, and one that is not admin-only. When the dishwasher has to
  // be finished and which appliance goes first are decisions of whoever lives
  // in the house, and that is usually not an administrator in Home Assistant.
  static saveCommand = "domotiapp_coach/strategy/set";
  static savePayload = "strategy";

  /** Everyone, hence the command above. */
  canEdit_() {
    return true;
  }

  /**
   * Whether this user can reach Apparaten at all.
   *
   * Customers cannot: that section is hidden for them. So every sentence here
   * that sends somebody to it has to say something else to them, or it points
   * at a screen they will never find.
   */
  isAdmin_() {
    return this.hass_?.user?.is_admin !== false;
  }

  constructor() {
    super();
    this.pane_ = "";
  }

  set hass(value) {
    super.hass = value;
    if (this.rendered_) this.paintTargets_();
  }

  /**
   * Which sub-screen is open, from the path.
   *
   * Routing it rather than keeping it in a variable is what makes the phone's
   * own back gesture close the sub-screen. Customers run Kiosk Mode and have no
   * browser chrome, so back is the only way out they always have.
   *
   * Two shapes: a notification by name, and a device's deadline as
   * `klaar/<device id>` -- one pane serving every appliance, because the
   * appliances are the customer's and there is no static markup for them.
   */
  set subroute(value) {
    // Alleen nog de meldingen. De schema's van apparaten zijn op 27-08-2026
    // naar de kaart van het apparaat zelf verhuisd, dus `klaar/<apparaat>`
    // bestaat hier niet meer.
    const head = String(value ?? "").split("/")[0];
    const pane = ALERTS.some((alert) => alert.id === head) ? head : "";

    if (pane === this.pane_) return;
    this.pane_ = pane;
    if (this.rendered_) this.paintPane_();
  }

  render() {
    const rows = ALERTS.map(
      (alert) => `
      <button class="link" type="button" data-open="${alert.id}">
        <span class="mark">${icons[alert.icon]}</span>
        <span class="body">
          <span class="head">
            <span class="title">${alert.title}</span>
            <span class="state" data-state="${alert.id}"></span>
          </span>
          <span class="sum" data-sum="${alert.id}"></span>
        </span>
        <span class="chev">${icons.chevronRight}</span>
      </button>`
    ).join("");

    return `
      <div class="wrap" id="pane-list">
        <header class="intro">
          <div class="eyebrow">Strategie</div>
          <h1>Wat de coach uit zichzelf doet</h1>
          <p>Hier bepaal je waar de coach je actief voor waarschuwt. De rest van de tijd kijkt hij mee zonder iets te zeggen.</p>
        </header>

        ${adminNoticeHtml}

        <section class="card">
          <h2>${icons.compass} Hoeveel doet de coach zelf?</h2>
          <p class="hint">Van alleen meekijken tot zelf schakelen. Begin gerust bij Voorstellen: dan zie je precies wat hij zou doen en gebeurt er niets zonder jouw akkoord.</p>
          <div class="fields">
            <div class="segmented levels" id="level">
              ${LEVELS.map(
                (item) => `
                <button type="button" data-level="${item.key}" aria-pressed="false">
                  <strong>${item.label}</strong>
                  ${item.blurb}
                </button>`
              ).join("")}
            </div>

            <p class="hint">
              Waar hij op mikt staat vast: zo min mogelijk geld uitgeven. De coach legt
              alle manieren om je auto vol te krijgen naast elkaar, van je eigen zon tot
              elk uur tussen nu en je klaar-tijd, en kiest de goedkoopste. Je eigen zon
              wint daarbij vanzelf zodra hij goedkoper is dan het net.
            </p>
          </div>
        </section>

        <section class="card">
          <h2>${icons.bell} Meldingen</h2>
          <p class="hint">Berichten die je op je telefoon krijgt, ook als het dashboard dicht staat. Tik een melding aan om hem in te stellen.</p>
          <div class="links">${rows}</div>
        </section>

      </div>

      <div class="wrap pane" data-pane="belasting" hidden>
        <button class="back" type="button">${icons.arrowLeft}<span>Meldingen</span></button>

        ${adminNoticeHtml}

        <header class="intro">
          <div class="eyebrow">Melding</div>
          <h1>Zware belasting</h1>
          <p>Krijg een bericht zodra je aansluiting te zwaar belast wordt. De coach kijkt naar de zwaarst belaste fase als die bekend is, anders naar je totale netvermogen.</p>
        </header>

        <section class="card">
          <div class="fields first">
            <label class="check" for="alert-enabled">
              <input type="checkbox" id="alert-enabled">
              <span>
                <strong>Melding aanzetten</strong>
                Zonder dit blijft de belastbaarheid gewoon op het overzicht staan, maar krijg je er geen bericht over.
              </span>
            </label>

            <div id="alert-fields" class="fields">
              <div class="row">
                <label for="alert-threshold">Waarschuw vanaf (%)</label>
                <input type="number" id="alert-threshold" min="1" max="200" step="1" inputmode="numeric">
                <span class="sub" id="alert-threshold-hint"></span>
              </div>

              <div class="row">
                <label for="alert-hold">Pas melden als het aanhoudt</label>
                <select id="alert-hold">
                  ${HOLDS.map((s) => `<option value="${s}">${holdLabel(s)}</option>`).join("")}
                </select>
                <span class="sub">Een oven of een motor die aanslaat geeft een piek van een seconde waar geen zekering van uit gaat en waar je niets aan kunt doen. Pas als de belasting zo lang boven de grens blijft, krijg je bericht.</span>
              </div>

              <div class="row">
                <label for="alert-interval">Niet vaker dan eens per</label>
                <select id="alert-interval">
                  ${INTERVALS.map((m) => `<option value="${m}">${label(m)}</option>`).join("")}
                </select>
                <span class="sub">De belasting schommelt heen en weer over de grens; zonder tussentijd zou je een reeks berichten krijgen voor één druk uur.</span>
              </div>

              <div class="row">
                <label>Wie krijgt de melding?</label>
                <div id="targets"></div>
                <span class="sub" id="targets-hint"></span>
              </div>
            </div>
          </div>
        </section>
      </div>

      ${saveBarHtml}
    `;
  }

  afterRender() {
    for (const link of this.$$("button.link")) {
      link.addEventListener("click", () => this.open_(link.dataset.open));
    }
    for (const back of this.$$("button.back")) {
      back.addEventListener("click", () => this.open_(""));
    }

    this.$("#alert-enabled").addEventListener("change", (ev) => {
      this.alert_().enabled = ev.target.checked;
      this.paintEnabled_();
      this.afterChange_();
    });

    this.$("#alert-threshold").addEventListener("input", (ev) => {
      this.alert_().threshold_percent = Number(ev.target.value);
      this.paintHint_();
      this.afterChange_();
    });

    this.$("#alert-hold").addEventListener("change", (ev) => {
      this.alert_().min_duration_seconds = Number(ev.target.value);
      this.afterChange_();
    });

    this.$("#alert-interval").addEventListener("change", (ev) => {
      this.alert_().min_interval_minutes = Number(ev.target.value);
      this.afterChange_();
    });

    for (const button of this.$$("#level button")) {
      button.addEventListener("click", () => {
        this.draft_.strategy.level = button.dataset.level;
        this.paintLevel_();
        this.afterChange_();
      });
    }
    this.wireSaveBar_();
    this.paintPane_();
    this.paint_();
  }

  /** Open a sub-screen, or the list when the id is empty. */
  open_(id) {
    this.fire("dac-navigate", { id: id ? `strategie/${id}` : "strategie" });
  }

  alert_() {
    return this.draft_.strategy.load_alert;
  }

  /** A schedule for a device that no longer exists is nothing but a leftover. */
  reconcile_() {
    const schedules = this.draft_?.strategy?.schedules;
    if (!Array.isArray(schedules)) return;

    const known = new Set((this.draft_?.devices ?? []).map((device) => device.id));
    const kept = schedules.filter((entry) => known.has(entry.device));
    if (kept.length !== schedules.length) this.draft_.strategy.schedules = kept;
  }

  /**
   * Two settings here promise something and then do nothing.
   *
   * A notification with nobody to send it to is switched on and silent. A
   * schedule with no times in it has no window to plan inside, so the coach
   * would never pick a moment. Both look arranged on screen and are not.
   */
  blockers_() {
    const out = [];
    const alert = this.draft_?.strategy?.load_alert;
    if (alert?.enabled && !(alert.targets ?? []).length) {
      out.push("Zware belasting staat aan, maar er is niemand geselecteerd om het bericht naar te sturen.");
    }

    return out;
  }

  /** The summary on the list is part of the same edit, so it follows along. */
  afterChange_() {
    this.paintSummaries_();
    this.syncSaveBar_();
  }

  /**
   * Every notify service Home Assistant knows about.
   *
   * These are what the mobile app registers itself as, which is how a
   * notification reaches a specific person's phone.
   */
  targets_() {
    return Object.keys(this.hass_?.services?.notify ?? {})
      .filter((name) => name !== "persistent_notification")
      .sort();
  }

  prettyTarget_(name) {
    return name
      .replace(/^mobile_app_/, "")
      .replace(/_/g, " ")
      .replace(/^\w/, (c) => c.toUpperCase());
  }

  paintPane_() {
    if (!this.rendered_) return;
    this.$("#pane-list").hidden = Boolean(this.pane_);
    for (const pane of this.$$(".pane")) pane.hidden = pane.dataset.pane !== this.pane_;
    // Opening a notification from halfway down the list would otherwise start
    // halfway down its settings.
    window.scrollTo({ top: 0 });
  }

  paint_() {
    if (!this.draft_ || !this.rendered_) return;
    const alert = this.alert_();

    this.$("#alert-enabled").checked = Boolean(alert.enabled);
    this.$("#alert-threshold").value = alert.threshold_percent;
    this.$("#alert-hold").value = String(alert.min_duration_seconds ?? 60);
    this.$("#alert-interval").value = String(alert.min_interval_minutes);

    // Hoort hier en niet alleen in de klikafhandelaars. Stond hij daar alleen,
    // dan waren het niveau en het doel na een herlaadbeurt allebei nergens
    // aangevinkt: opgeslagen was het wel, maar het scherm liet niet zien wat er
    // stond. Dat is niet te onderscheiden van instellingen die verdwenen zijn,
    // en zo is het ook gemeld.
    this.paintLevel_();
    this.paintEnabled_();
    this.paintTargets_();
    this.paintHint_();
    this.paintSummaries_();
    this.syncSaveBar_();
  }


  /**
   * Het niveau: hoeveel de coach zelf mag doen.
   *
   * De keuze tussen laagste kosten en zoveel mogelijk zon stond hier ook, en die
   * is weg. Sven op 30-08-2026: "het eindoel is altijd lage kosten." Sindsdien
   * legt de coach alle manieren naast elkaar en wint zon vanzelf zodra hij
   * goedkoper is; een knop die dat overrulet zou alleen maar geld kosten.
   */
  paintLevel_() {
    const level = this.draft_?.strategy?.level ?? "propose";
    for (const button of this.$$("#level button")) {
      button.setAttribute("aria-pressed", String(button.dataset.level === level));
    }
  }

  paintSummaries_() {
    if (!this.draft_ || !this.rendered_) return;
    for (const alert of ALERTS) {
      const { text, warn } = alert.summary(this);
      const line = this.$(`[data-sum="${alert.id}"]`);
      line.textContent = text;
      line.classList.toggle("warn", warn);

      const state = this.$(`[data-state="${alert.id}"]`);
      const on = Boolean(this.alert_().enabled);
      state.textContent = on ? "Aan" : "Uit";
      state.classList.toggle("on", on);
    }
  }

  paintEnabled_() {
    this.$("#alert-fields").style.display = this.alert_().enabled ? "" : "none";
  }

  paintHint_() {
    // The draft holds the whole settings document, not just this screen's
    // sections, so the connection is available here without a second fetch.
    const fuse = Number(this.draft_?.installation?.fuse_amps) || 0;
    const phases = Number(this.draft_?.installation?.phases) || 1;
    const percent = Number(this.alert_().threshold_percent) || 0;
    const hint = this.$("#alert-threshold-hint");

    if (!fuse) {
      hint.textContent = "Vul eerst je aansluiting in onder Installatie.";
      return;
    }
    const amps = ((fuse * percent) / 100).toLocaleString("nl-NL", { maximumFractionDigits: 1 });
    hint.textContent = `Bij ${phases} × ${fuse} A komt dat neer op ${amps} A per fase.`;
  }

  paintTargets_() {
    if (!this.rendered_ || !this.draft_) return;

    const holder = this.$("#targets");
    const chosen = new Set(this.alert_().targets ?? []);
    // A phone that was reinstalled, renamed or removed leaves its notify
    // service behind in the settings and nowhere else. The notification then
    // fails in the integration's log and nobody ever finds out, so the stale
    // name is listed here rather than quietly kept: it is checked, it says
    // what is wrong with it, and unchecking is how you get rid of it.
    const known = this.targets_();
    const stale = [...chosen].filter((name) => !known.includes(name));
    const available = [...known, ...stale];

    if (!available.length) {
      holder.innerHTML = `<p class="empty">Er zijn nog geen notify-diensten in Home Assistant. Die verschijnen zodra de mobiele app op een telefoon is ingelogd.</p>`;
      this.$("#targets-hint").textContent = "";
      return;
    }

    holder.innerHTML = available
      .map(
        (name) => `
        <label class="check target${stale.includes(name) ? " gone" : ""}" for="tgt-${name}">
          <input type="checkbox" id="tgt-${name}" data-target="${name}"${chosen.has(name) ? " checked" : ""}>
          <span>
            <strong>${this.prettyTarget_(name)}</strong>
            notify.${name}${stale.includes(name) ? " (bestaat niet meer in Home Assistant)" : ""}
          </span>
        </label>`
      )
      .join("");

    for (const box of holder.querySelectorAll("[data-target]")) {
      box.addEventListener("change", () => {
        const targets = new Set(this.alert_().targets ?? []);
        if (box.checked) targets.add(box.dataset.target);
        else targets.delete(box.dataset.target);
        this.alert_().targets = [...targets].sort();
        this.$("#targets-hint").textContent = this.targetsHint_();
        this.afterChange_();
      });
    }

    this.$("#targets-hint").textContent = this.targetsHint_();
  }

  targetsHint_() {
    const chosen = this.alert_().targets ?? [];
    if (!chosen.length) return "Niemand geselecteerd, er wordt dan niets verstuurd.";

    const known = this.targets_();
    const stale = chosen.filter((name) => !known.includes(name)).length;
    const base = chosen.length === 1 ? "1 ontvanger" : `${chosen.length} ontvangers`;
    if (!stale) return base;
    return `${base}, waarvan ${stale === 1 ? "één die niet meer bestaat" : `${stale} die niet meer bestaan`}. Vink die uit, anders mislukt de melding.`;
  }
}

/** "na ..." in words. */
function holdLabel(seconds) {
  const value = Number(seconds) || 0;
  if (value < 60) return `${value} seconden`;
  const minutes = value / 60;
  return minutes === 1 ? "1 minuut" : `${minutes} minuten`;
}

/** "eens per ..." in words. */
function label(minutes) {
  const value = Number(minutes) || 0;
  if (value < 60) return `${value} minuten`;
  const hours = value / 60;
  return hours === 1 ? "uur" : `${hours} uur`;
}

DacViewStrategy.css = /* css */ `
  ${editorCss}

  .pane[hidden], #pane-list[hidden] { display: none; }

  /* Vier keuzes onder elkaar: het zijn zinnen, geen knoppen, en naast elkaar
     wordt elke zin een kolom van drie woorden breed. */
  .segmented.levels { grid-template-columns: minmax(0, 1fr); }
  @media (min-width: 720px) { .segmented.levels { grid-template-columns: repeat(2, minmax(0, 1fr)); } }

  /* Three choices side by side rather than the usual two. On a phone they go
     under each other, like every other segmented choice here. */
  .segmented.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  @media (max-width: 560px) { .segmented.three { grid-template-columns: minmax(0, 1fr); } }

  /* ---- back to the list ---- */
  button.back {
    align-self: flex-start;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    margin: 0 0 2px -8px;
    padding: 8px 14px 8px 8px;
    border: 0;
    border-radius: var(--dac-radius-pill);
    background: transparent;
    color: var(--dac-ink-2);
    font: inherit;
    font-size: 13.5px;
    font-weight: 500;
    cursor: pointer;
    min-height: 40px;
  }
  button.back:hover { color: var(--dac-ink); background: rgba(255,255,255,0.05); }
  button.back .icon { width: 18px; height: 18px; }

  /* ---- the list of notifications ---- */
  .links { margin-top: 16px; display: grid; gap: 10px; }

  button.link {
    display: flex;
    align-items: center;
    gap: 13px;
    width: 100%;
    padding: 13px 12px 13px 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(255,255,255,0.022);
    color: var(--dac-ink);
    font: inherit;
    text-align: left;
    cursor: pointer;
    transition: border-color 180ms ease, background 180ms ease;
    -webkit-tap-highlight-color: transparent;
  }
  button.link:hover { border-color: rgba(25,143,217,0.5); background: var(--dac-accent-soft); }

  button.link .mark {
    flex: 0 0 auto;
    width: 36px; height: 36px;
    display: grid; place-items: center;
    border-radius: 11px;
    color: var(--dac-accent-hi);
    background: var(--dac-accent-soft);
    border: 1px solid rgba(25,143,217,0.28);
  }
  button.link .mark .icon { width: 19px; height: 19px; }

  /* min-width:0 is what lets the summary be cut off instead of stretching the
     row -- the whole point of the list is one line per notification. */
  button.link .body { flex: 1 1 auto; min-width: 0; display: grid; gap: 3px; }
  button.link .head { display: flex; align-items: center; gap: 8px; min-width: 0; }
  button.link .title {
    font-size: 14.5px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  button.link .sum {
    font-size: 12.5px;
    color: var(--dac-ink-2);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  button.link .sum.warn { color: var(--dac-warn); }

  button.link .state {
    flex: 0 0 auto;
    padding: 2px 9px;
    border-radius: var(--dac-radius-pill);
    border: 1px solid var(--dac-border);
    background: rgba(255,255,255,0.04);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    color: var(--dac-ink-3);
  }
  button.link .state.on {
    border-color: rgba(25,143,217,0.45);
    background: var(--dac-accent-soft);
    color: var(--dac-accent-hi);
  }

  button.link .chev { flex: 0 0 auto; display: grid; color: var(--dac-ink-3); }
  button.link .chev .icon { width: 18px; height: 18px; }
  button.link:hover .chev { color: var(--dac-ink-2); }

  /* An appliance that cannot be planned yet is still listed -- greyed out, not
     clickable, with the reason where the settings would have been. */
  .link.off {
    display: flex; align-items: center; gap: 13px;
    width: 100%;
    padding: 13px 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px dashed var(--dac-border);
    background: transparent;
    color: var(--dac-ink-3);
  }
  .link.off .mark {
    flex: 0 0 auto;
    width: 36px; height: 36px;
    display: grid; place-items: center;
    border-radius: 11px;
    color: var(--dac-ink-3);
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--dac-border);
  }
  .link.off .mark .icon { width: 19px; height: 19px; }
  .link.off .body { flex: 1 1 auto; min-width: 0; display: grid; gap: 3px; }
  .link.off .head { display: flex; align-items: center; gap: 8px; min-width: 0; }
  .link.off .title { font-size: 14.5px; font-weight: 600; color: var(--dac-ink-2); }
  .link.off .sum { font-size: 12.5px; line-height: 1.4; }
  .link.off .state {
    flex: 0 0 auto;
    padding: 2px 9px;
    border-radius: var(--dac-radius-pill);
    border: 1px solid var(--dac-border);
    font-size: 11px; font-weight: 600; letter-spacing: 0.04em;
    color: var(--dac-ink-3);
  }

  /* The settings pane opens on its own card, so the first block sits straight
     under the heading rather than under a hint that is no longer there. */
  .fields.first { margin-top: 0; }

  label.check.target span { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11.5px; }
  label.check.target strong { font-family: var(--dac-font); font-size: 13.5px; }
  label.check.target.gone { border-color: rgba(250,178,25,0.45); background: rgba(250,178,25,0.08); }
  label.check.target.gone:has(input:checked) { border-color: rgba(250,178,25,0.45); background: rgba(250,178,25,0.08); }
  label.check.target.gone span { color: var(--dac-warn); }

  #targets { display: grid; gap: 8px; }
  .empty { margin: 0; font-size: 13px; color: var(--dac-ink-3); line-height: 1.55; }

  /* ---- planning ---- */
  /* A clock is four characters wide; a field the width of the card invites the
     idea that something longer belongs in it. */
  .time-field { display: flex; align-items: center; gap: 6px; min-width: 0; }
  .time-field input[type="time"] { max-width: 170px; }
  .time-field .wipe {
    flex: 0 0 auto;
    width: 34px; height: 34px;
    display: grid; place-items: center;
    padding: 0;
    border: 1px solid var(--dac-border);
    border-radius: var(--dac-radius-pill);
    background: transparent;
    color: var(--dac-ink-3);
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }
  .time-field .wipe:hover { color: var(--dac-ink); border-color: var(--dac-border-hi); }
  .time-field .wipe .icon { width: 13px; height: 13px; }

  .plan-days { display: grid; gap: 10px; }
  .plan-day {
    padding: 12px 14px 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(255,255,255,0.022);
    min-width: 0;
  }
  .plan-day label.check.day {
    padding: 0;
    border: 0;
    background: transparent;
    margin-bottom: 10px;
  }
  .plan-day label.check.day:has(input:checked) { background: transparent; border: 0; }
  .plan-day .day-times {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(0, 210px));
    gap: 10px;
  }
  .plan-day .day-times label { font-size: 12px; color: var(--dac-ink-3); font-weight: 500; }
`;

define("dac-view-strategy", DacViewStrategy);
