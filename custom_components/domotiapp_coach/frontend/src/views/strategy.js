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
      if (!alert.enabled) return { text: "Uit — je krijgt hier geen bericht van.", warn: false };

      const parts = [`vanaf ${Number(alert.threshold_percent) || 0}%`];
      const count = (alert.targets ?? []).length;
      parts.push(count ? (count === 1 ? "1 ontvanger" : `${count} ontvangers`) : "niemand geselecteerd");
      parts.push(`hoogstens eens per ${label(alert.min_interval_minutes)}`);
      return { text: parts.join(" · "), warn: count === 0 };
    },
  },
];

class DacViewStrategy extends DacEditorElement {
  static sections = ["strategy"];

  constructor() {
    super();
    this.pane_ = "";
  }

  set hass(value) {
    super.hass = value;
    if (this.rendered_) this.paintTargets_();
  }

  /**
   * Which notification is open, from the path.
   *
   * Routing it rather than keeping it in a variable is what makes the phone's
   * own back gesture close the sub-screen. Customers run Kiosk Mode and have no
   * browser chrome, so back is the only way out they always have.
   */
  set subroute(value) {
    const next = ALERTS.some((alert) => alert.id === value) ? value : "";
    if (next === this.pane_) return;
    this.pane_ = next;
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

    this.$("#alert-interval").addEventListener("change", (ev) => {
      this.alert_().min_interval_minutes = Number(ev.target.value);
      this.afterChange_();
    });

    this.wireSaveBar_();
    this.paintPane_();
    this.paint_();
  }

  /** Open a notification, or the list when the id is empty. */
  open_(id) {
    this.fire("dac-navigate", { id: id ? `strategie/${id}` : "strategie" });
  }

  alert_() {
    return this.draft_.strategy.load_alert;
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
    this.$("#alert-interval").value = String(alert.min_interval_minutes);

    this.paintEnabled_();
    this.paintTargets_();
    this.paintHint_();
    this.paintSummaries_();
    this.syncSaveBar_();
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
    const available = this.targets_();
    const chosen = new Set(this.alert_().targets ?? []);

    if (!available.length) {
      holder.innerHTML = `<p class="empty">Er zijn nog geen notify-diensten in Home Assistant. Die verschijnen zodra de mobiele app op een telefoon is ingelogd.</p>`;
      this.$("#targets-hint").textContent = "";
      return;
    }

    holder.innerHTML = available
      .map(
        (name) => `
        <label class="check target" for="tgt-${name}">
          <input type="checkbox" id="tgt-${name}" data-target="${name}"${chosen.has(name) ? " checked" : ""}>
          <span>
            <strong>${this.prettyTarget_(name)}</strong>
            notify.${name}
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
    const count = (this.alert_().targets ?? []).length;
    if (!count) return "Niemand geselecteerd — er wordt dan niets verstuurd.";
    return count === 1 ? "1 ontvanger" : `${count} ontvangers`;
  }
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

  /* The settings pane opens on its own card, so the first block sits straight
     under the heading rather than under a hint that is no longer there. */
  .fields.first { margin-top: 0; }

  label.check {
    display: flex;
    align-items: flex-start;
    gap: 11px;
    padding: 12px 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(255,255,255,0.022);
    cursor: pointer;
    font-size: 12.5px;
    line-height: 1.5;
    color: var(--dac-ink-2);
  }
  label.check input {
    width: 18px; height: 18px; flex: 0 0 auto; margin: 1px 0 0;
    accent-color: var(--dac-accent-hi);
    cursor: pointer;
  }
  label.check strong { display: block; font-size: 13px; font-weight: 600; color: var(--dac-ink); margin-bottom: 2px; }
  label.check:has(input:checked) { border-color: rgba(25,143,217,0.5); background: var(--dac-accent-soft); }

  label.check.target span { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11.5px; }
  label.check.target strong { font-family: var(--dac-font); font-size: 13.5px; }

  #targets { display: grid; gap: 8px; }
  .empty { margin: 0; font-size: 13px; color: var(--dac-ink-3); line-height: 1.55; }
`;

define("dac-view-strategy", DacViewStrategy);
