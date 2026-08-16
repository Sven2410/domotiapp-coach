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
  PROGRAM_TYPES,
  SCHEDULABLE_TYPES,
  brandsFor,
  canHaveDeadline,
  deviceLabel,
  deviceLabelMap,
  programFor,
  typeMeta,
} from "../devices.js";
import { priceForecast } from "../data-source.js";
import { clock, duration } from "../format.js";
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

/** Monday first, the way a week is written down here. */
const DAYS = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"];
const DAYS_SHORT = ["ma", "di", "wo", "do", "vr", "za", "zo"];

/**
 * The three edges of a planning window, all optional.
 *
 * They answer different questions and a customer usually cares about one of
 * them: never before bedtime, started before I leave, finished before I get
 * up. Insisting on all three would be asking for answers nobody has.
 */
const TIMES = [
  {
    key: "not_before",
    label: "Niet eerder dan",
    short: "Niet eerder dan",
    hint: "Vóór deze tijd begint de coach er niet aan, hoe goedkoop de stroom ook is.",
  },
  {
    key: "start_by",
    label: "Uiterlijk starten om",
    short: "Starten vóór",
    hint: "Op deze tijd start hij hoe dan ook, ook als het dan een duur moment is.",
  },
  {
    key: "done_by",
    label: "Uiterlijk klaar om",
    short: "Klaar om",
    hint: "Hier rekent de coach van terug wanneer hij moet beginnen. Bij een programma gebruikt hij de duur die eronder staat.",
  },
];

/**
 * Who goes first when the connection cannot carry everything at once.
 *
 * Three steps and no more. A number from one to ten reads as precision that is
 * not there, and in a house with four steerable appliances the only question
 * that ever comes up is which one waits.
 */
const PRIORITIES = [
  { key: "high", label: "Hoog", blurb: "Gaat voor de rest." },
  { key: "mid", label: "Middel", blurb: "De gewone stand." },
  { key: "low", label: "Laag", blurb: "Wacht op de anderen." },
];

const priorityLabel = (key) =>
  PRIORITIES.find((item) => item.key === key)?.label ?? "Middel";

/** The one line under a device's name on the list. */
function planSummary_(plan, on) {
  if (!on) return "Niet ingepland. De coach laat dit apparaat met rust.";

  // Priority is only worth a word when it is not the ordinary one; on a list
  // where every row says "middel" the word stops carrying anything.
  const voorrang = plan.priority && plan.priority !== "mid"
    ? ` · voorrang ${priorityLabel(plan.priority).toLowerCase()}`
    : "";

  if (plan.per_day) {
    const days = plan.days
      .filter((day) => day.enabled && (day.not_before || day.start_by || day.done_by))
      .map((day) => DAYS_SHORT[day.day]);
    return `Per dag · ${days.join(", ")}${voorrang}`;
  }

  const parts = TIMES.filter((time) => plan.window[time.key]).map(
    (time) => `${time.short.toLowerCase()} ${plan.window[time.key]}`
  );
  return `Elke dag · ${parts.join(" · ")}${voorrang}`;
}

/** The next moment the clock reads this time, today or tomorrow. */
function nextAt(time, from = new Date()) {
  const [hours, minutes] = String(time).split(":").map(Number);
  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return null;

  const at = new Date(from);
  at.setHours(hours, minutes, 0, 0);
  if (at <= from) at.setDate(at.getDate() + 1);
  return at;
}

const sameDayAsToday = (date) => date.toDateString() === new Date().toDateString();

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
          <p class="hint">Binnen welke grenzen een apparaat mag draaien. Daarbinnen zoekt de coach het goedkoopste moment om te starten. Zonder enige grens is later altijd goedkoper en zou hij nooit beginnen. Inplannen kan zodra de coach het apparaat mag aansturen; dat zet je aan bij Apparaten.</p>
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
                <strong>Plan dit apparaat in</strong>
                Zonder dit laat de coach het apparaat met rust; je bedient het dan zelf.
              </span>
            </label>

            <div id="klaar-fields" class="fields">
              <div class="row">
                <label>Wie gaat voor?</label>
                <div class="segmented three" id="klaar-priority">
                  ${PRIORITIES.map(
                    (item) => `
                    <button type="button" data-priority="${item.key}" aria-pressed="false">
                      <strong>${item.label}</strong>
                      ${item.blurb}
                    </button>`
                  ).join("")}
                </div>
                <span class="sub">Past niet alles tegelijk binnen je aansluiting, dan begint de coach met wat het hoogst staat. Twee apparaten met dezelfde voorrang gaan op volgorde van hun eigen tijden.</span>
              </div>

              <div class="row">
                <label>Voor welke dagen?</label>
                <div class="segmented" id="klaar-mode">
                  <button type="button" data-mode="same" aria-pressed="false">
                    <strong>Elke dag hetzelfde</strong>
                    Eén stel tijden voor de hele week.
                  </button>
                  <button type="button" data-mode="per-day" aria-pressed="false">
                    <strong>Per dag</strong>
                    In het weekend andere tijden dan doordeweeks.
                  </button>
                </div>
              </div>

              <div id="klaar-same" class="fields"></div>
              <div id="klaar-days" class="plan-days"></div>

              <p class="sub" id="klaar-hint"></p>

              <div class="notice" id="klaar-horizon" hidden>
                ${icons.warning}
                <span id="klaar-horizon-text"></span>
              </div>

              <div class="notice">
                ${icons.warning}
                <span>Vrijgeven blijft nodig. De coach start dit apparaat alleen als je op het overzicht hebt aangegeven dat het mag draaien. Een tijd instellen is niet hetzelfde als toestemming geven.</span>
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
      const plan = this.planFor_(this.paneDevice_, true);
      plan.enabled = ev.target.checked;
      // Switching it on with nothing filled in would leave the coach with a
      // rule it cannot act on, so one time is offered to start from.
      if (plan.enabled && !this.planTimes_(plan).length) plan.window.done_by = "07:00";
      this.paintKlaar_();
      this.afterChange_();
    });

    for (const button of this.$$("#klaar-mode button")) {
      button.addEventListener("click", () => {
        const plan = this.planFor_(this.paneDevice_, true);
        plan.per_day = button.dataset.mode === "per-day";
        // Moving to per-day starts from what was already set for every day, so
        // the switch is a starting point rather than an empty form.
        if (plan.per_day && !plan.days.length) {
          plan.days = DAYS.map((_, day) => ({ day, enabled: true, ...plan.window }));
        }
        this.paintKlaar_();
        this.afterChange_();
      });
    }

    for (const button of this.$$("#klaar-priority button")) {
      button.addEventListener("click", () => {
        this.planFor_(this.paneDevice_, true).priority = button.dataset.priority;
        this.paintKlaar_();
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

  /** The devices that can be planned. */
  deadlineDevices_() {
    return (this.draft_?.devices ?? []).filter(canHaveDeadline);
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
   * The schedule for one device.
   *
   * A list rather than a map keyed by device id, because the storage prunes
   * dictionaries against its defaults and would empty a free-form map on every
   * load. `create` is false while only reading: adding an empty entry just
   * because a screen was opened would light up the save bar for nothing.
   */
  planFor_(deviceId, create = false) {
    const strategy = this.draft_.strategy;
    const blank = () => ({
      device: deviceId,
      enabled: false,
      per_day: false,
      priority: "mid",
      window: { not_before: "", start_by: "", done_by: "" },
      days: [],
    });

    const found = (strategy.schedules ?? []).find((entry) => entry.device === deviceId);

    // Reading must not write. Filling in a missing half, or creating the list
    // itself, would count as an unsaved change -- so merely opening the screen
    // would raise the save bar and, worse, stop it accepting settings saved
    // anywhere else.
    if (!create) {
      if (!found) return blank();
      const base = blank();
      return { ...base, ...found, window: { ...base.window, ...(found.window ?? {}) }, days: found.days ?? [] };
    }

    if (!Array.isArray(strategy.schedules)) strategy.schedules = [];
    if (!found) {
      const created = blank();
      strategy.schedules.push(created);
      return created;
    }

    // Settings written by an older version, or by hand, may be missing a half.
    found.window ??= { not_before: "", start_by: "", done_by: "" };
    found.days ??= [];
    found.priority ??= "mid";
    return found;
  }

  /** The windows a schedule actually uses: one, or one per active day. */
  planWindows_(plan) {
    if (!plan.per_day) return [plan.window];
    return plan.days.filter((day) => day.enabled);
  }

  /** Every time that is filled in, across the whole schedule. */
  planTimes_(plan) {
    return this.planWindows_(plan)
      .flatMap((window) => [window?.not_before, window?.start_by, window?.done_by])
      .filter(Boolean);
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

    for (const device of this.deadlineDevices_()) {
      const plan = this.planFor_(device.id);
      if (plan.enabled && !this.planTimes_(plan).length) {
        const label = deviceLabelMap(this.draft_?.devices).get(device.id) ?? deviceLabel(device);
        out.push(`${label} is ingepland, maar er staat geen enkele tijd in.`);
      }
    }
    return out;
  }

  /** The summary on the list is part of the same edit, so it follows along. */
  afterChange_() {
    this.paintSummaries_();
    // The device list carries the same settings in one line, so it has to
    // follow along: change a time in the sub-screen, step back, and the row
    // would otherwise still describe what it said before.
    this.paintDeviceLinks_();
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

  /**
   * One line per appliance that runs a programme, planned or not yet.
   *
   * The ones that cannot be planned yet are listed too, greyed out and with the
   * reason. Leaving them out was worse: you add a dishwasher under Apparaten,
   * come here, and the whole card is missing with nothing to say why.
   */
  paintDeviceLinks_() {
    const devices = this.planCandidates_();
    const holder = this.$("#device-links");
    this.$("#devices-card").hidden = !devices.length;
    if (!devices.length) {
      // Emptied rather than just hidden: a row left behind here is a device
      // that no longer exists, waiting to reappear the moment another one is
      // added.
      holder.replaceChildren();
      return;
    }

    holder.innerHTML = devices
      .map((device, index) => {
        const ready = canHaveDeadline(device);
        const body = `
          <span class="mark">${icons[typeMeta(device.type).icon]}</span>
          <span class="body">
            <span class="head">
              <span class="title" data-device-name="${index}"></span>
              <span class="state" data-device-state="${index}"></span>
            </span>
            <span class="sum" data-device-sum="${index}"></span>
          </span>`;

        return ready
          ? `<button class="link" type="button" data-device="${index}">${body}<span class="chev">${icons.chevronRight}</span></button>`
          : `<div class="link off">${body}</div>`;
      })
      .join("");

    // Numbered over the whole device list, not just the plannable ones, so
    // "Vaatwasser 2" means the same thing here as on the overview.
    const labels = deviceLabelMap(this.draft_?.devices);

    devices.forEach((device, index) => {
      const ready = canHaveDeadline(device);
      const plan = this.planFor_(device.id);
      const on = ready && Boolean(plan.enabled && this.planTimes_(plan).length);

      // Names are the customer's own text, so they go in as text.
      holder.querySelector(`[data-device-name="${index}"]`).textContent =
        labels.get(device.id) ?? deviceLabel(device);

      const state = holder.querySelector(`[data-device-state="${index}"]`);
      state.textContent = ready ? (on ? "Aan" : "Uit") : "Kan nog niet";
      state.classList.toggle("on", on);

      holder.querySelector(`[data-device-sum="${index}"]`).textContent = ready
        ? planSummary_(plan, on)
        : this.whyNot_(device);
    });

    for (const link of holder.querySelectorAll("[data-device]")) {
      const device = devices[Number(link.dataset.device)];
      link.addEventListener("click", () => this.open_(`klaar/${device.id}`));
    }
  }

  /** Every device that can be given a time window, steerable yet or not. */
  planCandidates_() {
    return (this.draft_?.devices ?? []).filter((device) =>
      SCHEDULABLE_TYPES.includes(device.type)
    );
  }

  /** What is standing between this appliance and being planned. */
  whyNot_(device) {
    if (brandsFor(device.type).length && !device.brand) {
      return "Kies eerst een merk bij Apparaten.";
    }
    return "Zet bij Apparaten aan dat de coach dit apparaat mag aansturen.";
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

    const plan = this.planFor_(device.id);
    this.$("#klaar-eyebrow").textContent = typeMeta(device.type).label;
    this.$("#klaar-title").textContent =
      deviceLabelMap(this.draft_?.devices).get(device.id) ?? deviceLabel(device);
    this.$("#klaar-intro").textContent =
      "Zeg binnen welke grenzen de coach mag werken. Vul alleen in wat je belangrijk vindt, want elk van de drie tijden mag leeg blijven.";

    this.$("#klaar-enabled").checked = Boolean(plan.enabled);
    this.$("#klaar-fields").style.display = plan.enabled ? "" : "none";

    for (const button of this.$$("#klaar-mode button")) {
      button.setAttribute(
        "aria-pressed",
        String((button.dataset.mode === "per-day") === Boolean(plan.per_day))
      );
    }

    for (const button of this.$$("#klaar-priority button")) {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.priority === (plan.priority ?? "mid"))
      );
    }

    this.$("#klaar-same").hidden = Boolean(plan.per_day);
    this.$("#klaar-days").hidden = !plan.per_day;

    if (plan.per_day) this.paintPlanDays_(plan);
    else this.paintPlanWindow_(plan);

    this.paintKlaarNotes_();
  }

  /** Both explanations under the times: the sum, and the price horizon. */
  paintKlaarNotes_() {
    this.paintKlaarHint_();
    this.paintHorizon_();
  }

  /**
   * Warn when the deadline lies past the last price the supplier has published.
   *
   * A dynamic tariff is only known a day ahead: today's prices in full and
   * tomorrow's from somewhere in the afternoon. Ask to be finished by seven
   * tomorrow evening and there is simply no price for the hours the coach would
   * be choosing between, so it can only plan on what it has. That is worth
   * saying out loud -- from the settings screen it looks like a plan that is
   * complete.
   *
   * It corrects itself: the moment tomorrow's prices land the warning goes.
   */
  paintHorizon_() {
    const notice = this.$("#klaar-horizon");
    notice.hidden = true;
    if (!this.feed_) return;

    const device = this.deadlineDevices_().find((item) => item.id === this.paneDevice_);
    if (!device) return;

    const plan = this.planFor_(device.id);
    if (!plan.enabled) return;

    const deadlines = plan.per_day
      ? plan.days.filter((day) => day.enabled && day.done_by).map((day) => day.done_by)
      : [plan.window.done_by].filter(Boolean);
    if (!deadlines.length) return;

    const forecast = priceForecast(this.feed_, this.draft_?.contract);
    const horizon = forecast[forecast.length - 1]?.end;
    if (!horizon) return;

    const beyond = deadlines.filter((time) => {
      const at = nextAt(time);
      return at && at > horizon;
    });
    if (!beyond.length) return;

    // A list that runs to midnight ends *on* the next day at 00:00, which reads
    // as "known until tomorrow" when it means the opposite. The last moment
    // actually covered is what the sentence is about.
    const last = new Date(horizon.getTime() - 1);
    const day = sameDayAsToday(last) ? "vandaag" : "morgen";
    const when =
      horizon.getHours() === 0 && horizon.getMinutes() === 0
        ? `het einde van ${day}`
        : `${day} ${clock(horizon)}`;
    notice.hidden = false;
    this.$("#klaar-horizon-text").textContent =
      `De prijzen zijn bekend tot ${when}. Een klaar-tijd daarna kan de coach niet doorrekenen. ` +
      "hij plant dan met wat hij weet, en dat is zelden het goedkoopste moment. " +
      "De prijzen voor de volgende dag komen meestal in de loop van de middag binnen; daarna klopt de planning weer.";
  }

  /** The three times, for a schedule that is the same every day. */
  paintPlanWindow_(plan) {
    const holder = this.$("#klaar-same");
    holder.innerHTML = TIMES.map(
      (time) => `
      <div class="row">
        <label for="w-${time.key}">${time.label}</label>
        <div class="time-field">
          <input type="time" id="w-${time.key}" step="300" data-window="${time.key}">
          <button type="button" class="wipe" data-wipe="${time.key}" aria-label="${time.label} leegmaken">${icons.close}</button>
        </div>
        <span class="sub">${time.hint}</span>
      </div>`
    ).join("");

    for (const time of TIMES) {
      const input = holder.querySelector(`[data-window="${time.key}"]`);
      input.value = plan.window[time.key] || "";
      input.addEventListener("input", () => {
        this.planFor_(this.paneDevice_, true).window[time.key] = input.value;
        this.paintKlaarNotes_();
        this.afterChange_();
      });
      holder.querySelector(`[data-wipe="${time.key}"]`).addEventListener("click", () => {
        this.planFor_(this.paneDevice_, true).window[time.key] = "";
        input.value = "";
        this.paintKlaarNotes_();
        this.afterChange_();
      });
    }
  }

  /** The same three times, once per weekday. */
  paintPlanDays_(plan) {
    const holder = this.$("#klaar-days");
    holder.innerHTML = DAYS.map(
      (name, day) => `
      <div class="plan-day">
        <label class="check day" for="d-${day}">
          <input type="checkbox" id="d-${day}" data-day="${day}">
          <span><strong>${name}</strong></span>
        </label>
        <div class="day-times" data-times="${day}">
          ${TIMES.map(
            (time) => `
            <div class="row">
              <label for="d-${day}-${time.key}">${time.short}</label>
              <div class="time-field">
                <input type="time" id="d-${day}-${time.key}" step="300" data-day-time="${day}:${time.key}">
                <button type="button" class="wipe" data-day-wipe="${day}:${time.key}" aria-label="${time.label} leegmaken">${icons.close}</button>
              </div>
            </div>`
          ).join("")}
        </div>
      </div>`
    ).join("");

    for (let day = 0; day < DAYS.length; day += 1) {
      const entry = this.planDay_(plan, day);
      const box = holder.querySelector(`[data-day="${day}"]`);
      box.checked = Boolean(entry.enabled);
      holder.querySelector(`[data-times="${day}"]`).style.display = entry.enabled ? "" : "none";

      box.addEventListener("change", () => {
        this.planDay_(this.planFor_(this.paneDevice_, true), day).enabled = box.checked;
        this.paintKlaar_();
        this.afterChange_();
      });

      for (const time of TIMES) {
        const input = holder.querySelector(`[data-day-time="${day}:${time.key}"]`);
        input.value = entry[time.key] || "";
        input.addEventListener("input", () => {
          this.planDay_(this.planFor_(this.paneDevice_, true), day)[time.key] = input.value;
          this.paintKlaarNotes_();
          this.afterChange_();
        });
        holder
          .querySelector(`[data-day-wipe="${day}:${time.key}"]`)
          .addEventListener("click", () => {
            this.planDay_(this.planFor_(this.paneDevice_, true), day)[time.key] = "";
            input.value = "";
            this.paintKlaarNotes_();
            this.afterChange_();
          });
      }
    }
  }

  /** One weekday of a schedule, added on demand. */
  planDay_(plan, day) {
    let entry = plan.days.find((item) => item.day === day);
    if (!entry) {
      entry = { day, enabled: true, not_before: "", start_by: "", done_by: "" };
      plan.days.push(entry);
      plan.days.sort((a, b) => a.day - b.day);
    }
    return entry;
  }

  /**
   * What the chosen times mean for the appliance in front of you.
   *
   * The program's length comes from the panel's own table of specifications, so
   * it is spelled out as an estimate -- the point is that "klaar om 07:00"
   * turns into a moment the machine has to be started, which is the thing that
   * decides whether the time is realistic at all.
   */
  paintKlaarHint_() {
    const hint = this.$("#klaar-hint");
    const device = this.deadlineDevices_().find((item) => item.id === this.paneDevice_);
    if (!device) return;

    const plan = this.planFor_(device.id);
    if (!this.planTimes_(plan).length) {
      hint.textContent =
        "Nog geen tijd ingevuld. Zolang er geen enkele grens staat, is later altijd goedkoper en begint de coach nooit.";
      return;
    }

    const program = this.selectedProgram_(device);
    const doneBy = plan.per_day
      ? plan.days.find((day) => day.enabled && day.done_by)?.done_by
      : plan.window.done_by;

    if (!doneBy) {
      hint.textContent =
        "De coach kiest binnen deze grenzen het goedkoopste moment om te starten.";
      return;
    }
    // A charger has no programme to work back from: how long a car takes
    // depends on the car, how empty it is and what the charger may deliver.
    // Promising a start time here would be a number nobody can stand behind.
    if (!PROGRAM_TYPES.includes(device.type)) {
      hint.textContent = `De auto moet om ${doneBy} opgeladen zijn. Hoe lang dat duurt hangt van de auto af, dus de coach begint zo vroeg als nodig is en laadt bij voorkeur op de goedkoopste uren daarvoor.`;
      return;
    }
    if (!program) {
      hint.textContent =
        "Klaar om is het einde van het programma, niet het begin. Hoe lang het duurt leest de coach van het apparaat af.";
      return;
    }

    const [hours, minutes] = doneBy.split(":").map(Number);
    const start = new Date();
    start.setHours(hours, minutes - program.minutes, 0, 0);

    hint.textContent = `${program.label} duurt ongeveer ${duration(program.minutes)}, dus starten moet uiterlijk om ${clock(start)}.`;
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
  .plan-days[hidden], #klaar-same[hidden] { display: none; }
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
