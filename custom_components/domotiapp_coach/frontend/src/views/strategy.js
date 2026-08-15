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
import { canHaveDeadline, deviceLabel, programFor, typeMeta } from "../devices.js";
import { duration } from "../format.js";
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
      parts.push(`na ${holdLabel(alert.min_duration_seconds ?? 60)}`);
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
    this.paneDevice_ = "";
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
    const path = String(value ?? "");
    const [head, rest] = [path.split("/")[0], path.split("/").slice(1).join("/")];

    let pane = "";
    let device = "";
    if (ALERTS.some((alert) => alert.id === head)) pane = head;
    else if (head === "klaar" && rest) {
      pane = "klaar";
      device = rest;
    }

    if (pane === this.pane_ && device === this.paneDevice_) return;
    this.pane_ = pane;
    this.paneDevice_ = device;
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

        <section class="card" id="devices-card" hidden>
          <h2>${icons.devices} Apparaten</h2>
          <p class="hint">Wanneer een apparaat uiterlijk klaar moet zijn. Daarbinnen zoekt de coach het goedkoopste moment om te starten — zonder zo'n tijd is later altijd goedkoper en zou hij nooit beginnen.</p>
          <div class="links" id="device-links"></div>
        </section>
      </div>

      <div class="wrap pane" data-pane="klaar" hidden>
        <button class="back" type="button">${icons.arrowLeft}<span>Strategie</span></button>

        ${adminNoticeHtml}

        <header class="intro">
          <div class="eyebrow" id="klaar-eyebrow">Apparaat</div>
          <h1 id="klaar-title"></h1>
          <p id="klaar-intro"></p>
        </header>

        <section class="card">
          <div class="fields first">
            <label class="check" for="klaar-enabled">
              <input type="checkbox" id="klaar-enabled">
              <span>
                <strong>Uiterlijk klaar op een vaste tijd</strong>
                Zonder dit heeft de coach geen reden om te beginnen: er komt altijd nog een goedkoper moment.
              </span>
            </label>

            <div id="klaar-fields" class="fields">
              <div class="row">
                <label for="klaar-time">Klaar om</label>
                <input type="time" id="klaar-time" step="300">
                <span class="sub" id="klaar-hint"></span>
              </div>

              <div class="notice">
                ${icons.warning}
                <span>Vrijgeven blijft nodig. De coach start dit apparaat alleen als je op het overzicht hebt aangegeven dat het mag draaien — een tijd instellen is niet hetzelfde als toestemming geven.</span>
              </div>
            </div>
          </div>
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

    this.$("#klaar-enabled").addEventListener("change", (ev) => {
      const deadline = this.deadlineFor_(this.paneDevice_, true);
      deadline.enabled = ev.target.checked;
      // Switching it on with no time set would leave the coach with a rule it
      // cannot act on, so it starts at a time somebody would plausibly pick.
      if (deadline.enabled && !deadline.time) deadline.time = "07:00";
      this.paintKlaar_();
      this.afterChange_();
    });

    this.$("#klaar-time").addEventListener("input", (ev) => {
      this.deadlineFor_(this.paneDevice_, true).time = ev.target.value;
      this.paintKlaarHint_();
      this.afterChange_();
    });

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

  /** The devices that can have a time by which they must be finished. */
  deadlineDevices_() {
    return (this.draft_?.devices ?? []).filter(canHaveDeadline);
  }

  /**
   * The deadline for one device.
   *
   * A list rather than a map keyed by device id, because the storage prunes
   * dictionaries against its defaults and would empty a free-form map on every
   * load. `create` is false while only reading: adding an empty entry just
   * because a screen was opened would light up the save bar for nothing.
   */
  deadlineFor_(deviceId, create = false) {
    const strategy = this.draft_.strategy;
    if (!Array.isArray(strategy.deadlines)) strategy.deadlines = [];

    const found = strategy.deadlines.find((entry) => entry.device === deviceId);
    if (found || !create) return found ?? { device: deviceId, enabled: false, time: "" };

    const fresh = { device: deviceId, enabled: false, time: "" };
    strategy.deadlines.push(fresh);
    return fresh;
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
    if (this.pane_ === "klaar") this.paintKlaar_();
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

    this.paintEnabled_();
    this.paintTargets_();
    this.paintHint_();
    this.paintDeviceLinks_();
    this.paintSummaries_();
    if (this.pane_ === "klaar") this.paintKlaar_();
    this.syncSaveBar_();
  }

  /** One line per appliance that can be planned, with what it is set to. */
  paintDeviceLinks_() {
    const devices = this.deadlineDevices_();
    this.$("#devices-card").hidden = !devices.length;
    if (!devices.length) return;

    const holder = this.$("#device-links");
    holder.innerHTML = devices
      .map(
        (device, index) => `
        <button class="link" type="button" data-device="${index}">
          <span class="mark">${icons[typeMeta(device.type).icon]}</span>
          <span class="body">
            <span class="head">
              <span class="title" data-device-name="${index}"></span>
              <span class="state" data-device-state="${index}"></span>
            </span>
            <span class="sum" data-device-sum="${index}"></span>
          </span>
          <span class="chev">${icons.chevronRight}</span>
        </button>`
      )
      .join("");

    devices.forEach((device, index) => {
      const deadline = this.deadlineFor_(device.id);
      const on = Boolean(deadline.enabled && deadline.time);

      // Names are the customer's own text, so they go in as text.
      holder.querySelector(`[data-device-name="${index}"]`).textContent = deviceLabel(device);

      const state = holder.querySelector(`[data-device-state="${index}"]`);
      state.textContent = on ? "Aan" : "Uit";
      state.classList.toggle("on", on);

      holder.querySelector(`[data-device-sum="${index}"]`).textContent = on
        ? `Uiterlijk klaar om ${deadline.time}`
        : "Geen tijd ingesteld — de coach laat dit apparaat met rust.";
    });

    for (const link of holder.querySelectorAll("[data-device]")) {
      const device = devices[Number(link.dataset.device)];
      link.addEventListener("click", () => this.open_(`klaar/${device.id}`));
    }
  }

  /** The deadline sub-screen, for whichever appliance it was opened for. */
  paintKlaar_() {
    if (!this.draft_ || !this.rendered_) return;

    const device = this.deadlineDevices_().find((item) => item.id === this.paneDevice_);
    // The device may be gone, or the draft may not be in yet; either way there
    // is nothing to edit, so the list is the honest place to be.
    if (!device) {
      if (this.draft_) this.open_("");
      return;
    }

    const deadline = this.deadlineFor_(device.id);
    this.$("#klaar-eyebrow").textContent = typeMeta(device.type).label;
    this.$("#klaar-title").textContent = deviceLabel(device);
    this.$("#klaar-intro").textContent =
      "Zeg tot wanneer de coach de tijd heeft. Binnen die ruimte kiest hij zelf het goedkoopste moment om te starten — bij zon op het dak, of bij een laag tarief.";

    this.$("#klaar-enabled").checked = Boolean(deadline.enabled);
    this.$("#klaar-time").value = deadline.time || "";
    this.$("#klaar-fields").style.display = deadline.enabled ? "" : "none";
    this.paintKlaarHint_();
  }

  /**
   * What the chosen time means for the appliance in front of you.
   *
   * The program's length comes from the panel's own table of specifications, so
   * it is spelled out as an estimate -- the point is that "klaar om 07:00"
   * turns into a moment the machine has to be started, which is the thing that
   * decides whether the time is realistic at all.
   */
  paintKlaarHint_() {
    const hint = this.$("#klaar-hint");
    const device = this.deadlineDevices_().find((item) => item.id === this.paneDevice_);
    const deadline = device ? this.deadlineFor_(device.id) : null;

    if (!deadline?.time) {
      hint.textContent = "Kies een tijd. De coach zorgt dat het programma dan afgelopen is.";
      return;
    }

    const program = this.selectedProgram_(device);
    if (!program) {
      hint.textContent = `Het programma is dan afgelopen, niet pas begonnen. Hoe lang het duurt leest de coach van het apparaat af.`;
      return;
    }

    const [hours, minutes] = deadline.time.split(":").map(Number);
    const start = new Date();
    start.setHours(hours, minutes - program.minutes, 0, 0);
    const clockText = start.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" });

    hint.textContent =
      `${program.label} duurt ongeveer ${duration(program.minutes)}, dus starten moet uiterlijk om ${clockText}.`;
  }

  /** The program the appliance has standing by, if the panel knows it. */
  selectedProgram_(device) {
    const entityId = device?.entities?.program;
    if (!entityId || !this.feed_) return undefined;
    return programFor(this.feed_.get(entityId)?.state);
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

  label.check.target span { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11.5px; }
  label.check.target strong { font-family: var(--dac-font); font-size: 13.5px; }

  #targets { display: grid; gap: 8px; }
  .empty { margin: 0; font-size: 13px; color: var(--dac-ink-3); line-height: 1.55; }

  /* A clock is four characters wide; a field the width of the card invites the
     idea that something longer belongs in it. */
  #klaar-time { max-width: 190px; }
`;

define("dac-view-strategy", DacViewStrategy);
