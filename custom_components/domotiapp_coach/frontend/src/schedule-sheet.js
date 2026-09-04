/**
 * Het schema van één apparaat, als pop-up achter zijn eigen kaart.
 *
 * Stond tot 27-08-2026 in Strategie, achter een lijstje apparaten. Sven wilde
 * het bij het apparaat zelf hebben: op de kaart de schuif en de voorrang, en
 * achter de knop Schema dit scherm met de tijden. Strategie houdt daarmee één
 * onderwerp over, namelijk wat de coach uit zichzelf doet.
 *
 * Er is geen opslaanbalk. Elke wijziging gaat meteen naar de server, net als de
 * andere knoppen op die kaart: dit gaat over één apparaat en de coach kan er
 * binnen een minuut iets mee. Een balk die eerst nog bevestigd moet worden zou
 * betekenen dat je hem 's avonds instelt en er 's ochtends achter komt dat het
 * niet bewaard is.
 */

import { DacElement, define } from "./base.js";
import { icons } from "./icons.js";
import { PROGRAM_TYPES, needsRelease, programFor, typeMeta } from "./devices.js";
import { priceForecast } from "./data-source.js";
import { clock, duration } from "./format.js";
import { sheetCss } from "./theme.js";

/** Maandag eerst, zoals een week hier opgeschreven wordt. */
export const DAYS = [
  "Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag",
];
export const DAYS_SHORT = ["ma", "di", "wo", "do", "vr", "za", "zo"];

/**
 * De drie randen van een planvenster, alle drie optioneel.
 *
 * Ze beantwoorden verschillende vragen en meestal gaat het iemand om één ervan:
 * nooit voor bedtijd, gestart voor ik wegga, klaar voor ik opsta. Alle drie
 * eisen zou vragen om antwoorden die niemand heeft.
 */
export const TIMES = [
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
 * Wie er voorgaat als de aansluiting niet alles tegelijk kan dragen.
 *
 * Drie standen en niet meer. Een getal van een tot tien leest als een precisie
 * die er niet is, en in een huis met vier stuurbare apparaten is de enige vraag
 * die ooit opkomt welke er wacht.
 */
export const PRIORITIES = [
  { key: "high", label: "Hoog", blurb: "Gaat voor de rest." },
  { key: "mid", label: "Middel", blurb: "De gewone stand." },
  { key: "low", label: "Laag", blurb: "Wacht op de anderen." },
];

/**
 * Welke van de drie tijden dit apparaat kent.
 *
 * Een laadpaal alleen "klaar om". Sven op 04-09-2026: "niet eerder dan en
 * starten voor moet er helemaal uit." De coach zoekt zelf het goedkoopste
 * moment tussen nu en de klaar-tijd; een begintijd houdt hem alleen van de zon
 * af en een starttijd laat hem laden terwijl het duur is. Andere apparaten
 * houden alle drie.
 */
export const timesFor = (device) =>
  device?.type === "laadpaal" ? TIMES.filter((time) => time.key === "done_by") : TIMES;

export const priorityLabel = (key) =>
  PRIORITIES.find((item) => item.key === key)?.label ?? "Middel";

/** Een leeg schema, met alle helften ingevuld zodat er nergens op None gerekend wordt. */
export const blankPlan = (deviceId) => ({
  device: deviceId,
  enabled: false,
  per_day: false,
  priority: "mid",
  window: { not_before: "", start_by: "", done_by: "" },
  days: [],
});

/**
 * Het schema van dit apparaat uit de instellingen, altijd compleet.
 *
 * Instellingen van een oudere versie, of met de hand geschreven, missen weleens
 * een helft. Lezen mag nooit schrijven, dus dit levert een kopie op en raakt
 * het origineel niet aan.
 */
export function planFor(settings, deviceId) {
  const found = (settings?.strategy?.schedules ?? []).find(
    (entry) => entry?.device === deviceId
  );
  const base = blankPlan(deviceId);
  if (!found) return base;
  return {
    ...base,
    ...found,
    window: { ...base.window, ...(found.window ?? {}) },
    days: (found.days ?? []).map((day) => ({ ...day })),
  };
}

/** De vensters die een schema werkelijk gebruikt: één, of één per actieve dag. */
export const planWindows = (plan) =>
  plan.per_day ? plan.days.filter((day) => day.enabled) : [plan.window];

/** Elke tijd die ingevuld is, over het hele schema. */
export const planTimes = (plan) =>
  planWindows(plan)
    .flatMap((window) => [window?.not_before, window?.start_by, window?.done_by])
    .filter(Boolean);

/** Eén regel die zegt wat er staat, voor onder de schuif op de kaart. */
export function planSummary(plan) {
  if (!plan.enabled) {
    return "Uit. De coach bepaalt zelf wanneer en kijkt puur naar het gunstigste moment.";
  }
  if (!planTimes(plan).length) {
    return "Aan, maar er staat nog geen enkele tijd in.";
  }
  if (plan.per_day) {
    const days = plan.days
      .filter((day) => day.enabled && (day.not_before || day.start_by || day.done_by))
      .map((day) => DAYS_SHORT[day.day]);
    return `Per dag · ${days.join(", ")}`;
  }
  const parts = TIMES.filter((time) => plan.window[time.key]).map(
    (time) => `${time.short.toLowerCase()} ${plan.window[time.key]}`
  );
  return `Elke dag · ${parts.join(" · ")}`;
}

/** Het eerstvolgende moment dat de klok deze tijd aanwijst, vandaag of morgen. */
function nextAt(time, from = new Date()) {
  const [hours, minutes] = String(time).split(":").map(Number);
  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return null;
  const at = new Date(from);
  at.setHours(hours, minutes, 0, 0);
  if (at <= from) at.setDate(at.getDate() + 1);
  return at;
}

const sameDayAsToday = (date) => date.toDateString() === new Date().toDateString();

const css = /* css */ `
  :host { display: contents; }

  /* De opmaak van een pop-up is opt-in en zit niet in de basis: baseCss heeft
     hem niet, sheetCss wel. Zonder deze regel kreeg deze dialoog de witte
     achtergrond en zwarte letters van de browser zelf, midden in een donker
     paneel. Nagemeten op 27-08-2026. */
  ${sheetCss}
  /* Breed, zoals de twee andere pop-ups van het overzicht. Die regel staat in
     hun eigen opmaak en niet in sheetCss, dus hij hoort hier ook te staan. */
  dialog.sheet.wide { width: min(760px, calc(100vw - 24px)); }
  @media (max-width: 560px) { dialog.sheet.wide { width: 100vw; } }
  /* Een pop-up die langer is dan het scherm hoort te schuiven in plaats van
     onder de rand door te lopen. */
  dialog.sheet { max-height: calc(100vh - 24px); overflow-y: auto; }

  /* Het attribuut hidden is niets meer dan een regel van de browser zelf, en
     die verliest van elke display die hier staat. Zonder deze regels bleef de
     lege waarschuwing staan en stonden de tijden van elke dag én die per dag
     tegelijk in beeld. Sven zag dat op 27-08-2026. Elke klasse hieronder die
     een display krijgt, hoort er dus eentje te hebben. */
  [hidden] { display: none !important; }

  .fields { display: grid; gap: 16px; margin-top: 16px; }
  .row { display: grid; gap: 7px; }
  .row > label { font-size: 13px; font-weight: 500; color: var(--dac-ink); }
  .sub { font-size: 12px; line-height: 1.5; color: var(--dac-ink-2); }

  .segmented { display: grid; gap: 8px; grid-template-columns: 1fr 1fr; }
  /* Onder de 380 px past twee naast elkaar niet meer zonder dat de tekst in
     losse letters afbreekt. Dan onder elkaar. */
  @media (max-width: 380px) { .segmented { grid-template-columns: 1fr; } }
  .segmented button {
    display: grid; gap: 3px;
    padding: 11px 13px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(255,255,255,0.03);
    color: var(--dac-ink-2);
    font: inherit; font-size: 12px; line-height: 1.45;
    text-align: left; cursor: pointer;
  }
  .segmented button strong { font-size: 13.5px; font-weight: 600; color: var(--dac-ink); }
  .segmented button:hover { border-color: var(--dac-border-hi); }
  .segmented button[aria-pressed="true"] {
    border-color: rgba(25,143,217,0.55);
    background: var(--dac-accent-soft);
  }

  .time-field { display: flex; align-items: center; gap: 8px; }
  .time-field input[type="time"] {
    flex: 1 1 auto; min-width: 0; max-width: 190px;
    min-height: 44px;
    padding: 10px 12px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border-hi);
    background: rgba(255,255,255,0.04);
    color: var(--dac-ink);
    font: inherit; font-size: 14px;
    font-variant-numeric: tabular-nums;
  }
  @media (pointer: coarse) { .time-field input[type="time"] { font-size: 16px; } }
  @supports (-webkit-touch-callout: none) {
    .time-field input[type="time"] { font-size: 16px; }
  }
  .time-field .wipe {
    flex: 0 0 auto;
    width: 36px; height: 36px; padding: 0;
    display: grid; place-items: center;
    border-radius: 50%;
    border: 1px solid var(--dac-border);
    background: transparent;
    color: var(--dac-ink-3);
    cursor: pointer;
  }
  .time-field .wipe:hover { color: var(--dac-ink); border-color: var(--dac-border-hi); }
  .time-field .wipe .icon { width: 14px; height: 14px; }

  .plan-days { display: grid; gap: 10px; }
  .plan-day {
    padding: 12px 13px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(255,255,255,0.022);
  }
  .check { display: flex; align-items: flex-start; gap: 10px; cursor: pointer; }
  .check input { margin: 2px 0 0; width: 18px; height: 18px; flex: 0 0 auto; accent-color: var(--dac-accent-hi); }
  .check span { display: grid; gap: 2px; font-size: 12.5px; color: var(--dac-ink-2); }
  .check strong { font-size: 13.5px; font-weight: 600; color: var(--dac-ink); }
  .day-times { display: grid; gap: 8px; margin: 10px 0 0 28px; }
  /* Op een smal scherm is die inspringing 28 px die niets doet behalve de
     tijdvelden krap maken. */
  @media (max-width: 380px) { .day-times { margin-left: 0; } }
  .day-times .row { grid-template-columns: 1fr; }

  .notice {
    display: flex; gap: 10px; align-items: flex-start;
    padding: 11px 13px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid rgba(250,178,25,0.35);
    background: rgba(250,178,25,0.08);
    font-size: 12.5px; line-height: 1.5; color: var(--dac-ink-2);
  }
  .notice .icon { width: 16px; height: 16px; flex: 0 0 auto; color: var(--dac-warn); }
`;

export class DacScheduleSheet extends DacElement {
  static css = css;

  constructor() {
    super();
    this.device_ = null;
    this.settings_ = null;
    this.feed_ = null;
    this.hass = null;
    this.label_ = "";
  }

  set settings(value) {
    this.settings_ = value;
    // Ververst terwijl hij openstaat: iemand anders kan op zijn telefoon iets
    // veranderd hebben. Niet terwijl er getypt wordt, dat regelt `paint_`.
    if (this.rendered_ && this.$("dialog")?.open) this.paint_();
  }

  set feed(value) {
    this.feed_ = value;
    if (this.rendered_ && this.$("dialog")?.open) this.paintNotes_();
  }

  render() {
    return /* html */ `
      <dialog class="sheet wide" tabindex="-1" aria-labelledby="plan-title">
        <div class="sheet-head">
          <div>
            <div class="eyebrow" id="plan-eyebrow">Apparaat</div>
            <h3 id="plan-title"></h3>
          </div>
          <button class="sheet-close" type="button" id="plan-close" aria-label="Sluiten">
            ${icons.close}
          </button>
        </div>
        <p class="sheet-sub">Zeg binnen welke grenzen de coach mag werken. Vul alleen in wat je belangrijk vindt, want elk van de drie tijden mag leeg blijven.</p>

        <div class="fields">
          <div class="row">
            <label>Voor welke dagen?</label>
            <div class="segmented" id="plan-mode">
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

          <div id="plan-same" class="fields"></div>
          <div id="plan-days" class="plan-days"></div>

          <p class="sub" id="plan-hint"></p>

          <div class="notice" id="plan-horizon" hidden>
            ${icons.warning}
            <span id="plan-horizon-text"></span>
          </div>

          <div class="notice" id="plan-release" hidden>
            ${icons.warning}
            <span>Vrijgeven blijft nodig. De coach start dit apparaat alleen als je op het overzicht hebt aangegeven dat het mag draaien. Een tijd instellen is niet hetzelfde als toestemming geven.</span>
          </div>
        </div>

        <p class="sheet-status" id="plan-status" role="status" aria-live="polite"></p>
      </dialog>
    `;
  }

  afterRender() {
    const dialog = this.$("dialog");
    this.$("#plan-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
      // Op de achtergrond tikken sluit hem. `event.target` is de dialoog zelf
      // alleen als de tik buiten zijn eigen doos landde.
      if (event.target === dialog) dialog.close();
    });
    for (const button of this.$$("#plan-mode button")) {
      button.addEventListener("click", () => this.setMode_(button.dataset.mode === "per-day"));
    }
  }

  /** Openen voor dit apparaat. */
  open(device, label) {
    this.device_ = device;
    this.label_ = label || "";
    this.paint_();
    const dialog = this.$("dialog");
    if (!dialog.open) dialog.showModal();
  }

  close() {
    this.$("dialog")?.close();
  }

  plan_() {
    return planFor(this.settings_, this.device_?.id ?? "");
  }

  paint_() {
    if (!this.device_) return;
    const plan = this.plan_();

    this.$("#plan-eyebrow").textContent = typeMeta(this.device_.type).label;
    this.$("#plan-title").textContent = this.label_;

    for (const button of this.$$("#plan-mode button")) {
      button.setAttribute(
        "aria-pressed",
        String((button.dataset.mode === "per-day") === Boolean(plan.per_day))
      );
    }

    this.$("#plan-same").hidden = Boolean(plan.per_day);
    this.$("#plan-days").hidden = !plan.per_day;
    if (plan.per_day) this.paintDays_(plan);
    else this.paintWindow_(plan);

    // Alleen waar iemand het apparaat nog moet vrijgeven. Een laadpaal niet: de
    // kabel erin steken is daar de toestemming.
    this.$("#plan-release").hidden = !needsRelease(this.device_);
    this.paintNotes_();
  }

  /** De tijden die dit apparaat kent, voor een schema dat elke dag hetzelfde is. */
  paintWindow_(plan) {
    const holder = this.$("#plan-same");
    const TIMES = timesFor(this.device_);
    // Eén keer bouwen per soort apparaat: een laadpaal heeft één veld, de rest
    // drie, en hetzelfde scherm gaat voor allebei open.
    if (holder.dataset.built !== this.device_.type) {
      holder.innerHTML = TIMES.map(
        (time) => `
        <div class="row">
          <label for="w-${time.key}">${time.label}</label>
          <div class="time-field">
            <input type="time" id="w-${time.key}" step="300" data-window="${time.key}">
            <button type="button" class="wipe" data-wipe="${time.key}"
                    aria-label="${time.label} leegmaken">${icons.close}</button>
          </div>
          <span class="sub">${time.hint}</span>
        </div>`
      ).join("");
      holder.dataset.built = this.device_.type;

      for (const time of TIMES) {
        const input = holder.querySelector(`[data-window="${time.key}"]`);
        // `change` en niet `input`: dat vuurt al zodra het eerste cijfer van
        // het uur getypt is, en dan gaat er een halve tijd naar de server.
        input.addEventListener("change", () => this.saveWindow_());
        holder.querySelector(`[data-wipe="${time.key}"]`).addEventListener("click", () => {
          input.value = "";
          this.saveWindow_();
        });
      }
    }

    for (const time of TIMES) {
      const input = holder.querySelector(`[data-window="${time.key}"]`);
      const staat = plan.window[time.key] || "";
      if (this.shadowRoot.activeElement === input) continue;
      if (input.value !== staat) input.value = staat;
    }
  }

  /** Dezelfde tijden, één keer per weekdag. */
  paintDays_(plan) {
    const holder = this.$("#plan-days");
    const TIMES = timesFor(this.device_);
    if (holder.dataset.built !== this.device_.type) {
      holder.innerHTML = DAYS.map(
        (name, day) => `
        <div class="plan-day">
          <label class="check" for="d-${day}">
            <input type="checkbox" id="d-${day}" data-day="${day}">
            <span><strong>${name}</strong></span>
          </label>
          <div class="day-times" data-times="${day}">
            ${TIMES.map(
              (time) => `
              <div class="row">
                <label for="d-${day}-${time.key}">${time.short}</label>
                <div class="time-field">
                  <input type="time" id="d-${day}-${time.key}" step="300"
                         data-day-time="${day}:${time.key}">
                  <button type="button" class="wipe" data-day-wipe="${day}:${time.key}"
                          aria-label="${time.label} leegmaken">${icons.close}</button>
                </div>
              </div>`
            ).join("")}
          </div>
        </div>`
      ).join("");
      holder.dataset.built = this.device_.type;

      for (let day = 0; day < DAYS.length; day += 1) {
        holder.querySelector(`[data-day="${day}"]`).addEventListener("change", () =>
          this.saveDays_()
        );
        for (const time of TIMES) {
          const input = holder.querySelector(`[data-day-time="${day}:${time.key}"]`);
          input.addEventListener("change", () => this.saveDays_());
          holder
            .querySelector(`[data-day-wipe="${day}:${time.key}"]`)
            .addEventListener("click", () => {
              input.value = "";
              this.saveDays_();
            });
        }
      }
    }

    for (let day = 0; day < DAYS.length; day += 1) {
      const entry = plan.days.find((item) => item.day === day);
      const box = holder.querySelector(`[data-day="${day}"]`);
      const aan = Boolean(entry?.enabled);
      box.checked = aan;
      holder.querySelector(`[data-times="${day}"]`).hidden = !aan;
      for (const time of TIMES) {
        const input = holder.querySelector(`[data-day-time="${day}:${time.key}"]`);
        const staat = entry?.[time.key] || "";
        if (this.shadowRoot.activeElement === input) continue;
        if (input.value !== staat) input.value = staat;
      }
    }
  }

  /** De twee uitleggen onder de tijden: de som, en de prijshorizon. */
  paintNotes_() {
    this.paintHint_();
    this.paintHorizon_();
  }

  /**
   * Wat de gekozen tijden betekenen voor het apparaat dat voor je staat.
   *
   * De duur van een programma komt uit de eigen tabel van het paneel, dus die
   * staat er als schatting bij. Waar het om gaat is dat "klaar om 07:00" een
   * moment wordt waarop de machine moet starten, want dat is wat bepaalt of die
   * tijd überhaupt haalbaar is.
   */
  paintHint_() {
    const hint = this.$("#plan-hint");
    const plan = this.plan_();

    if (!planTimes(plan).length) {
      hint.textContent =
        "Nog geen tijd ingevuld. Zolang er geen enkele grens staat, is later altijd goedkoper en begint de coach nooit.";
      return;
    }

    const doneBy = plan.per_day
      ? plan.days.find((day) => day.enabled && day.done_by)?.done_by
      : plan.window.done_by;

    if (!doneBy) {
      hint.textContent =
        "De coach kiest binnen deze grenzen het goedkoopste moment om te starten.";
      return;
    }
    // Een laadpaal heeft geen programma om van terug te rekenen: hoe lang een
    // auto erover doet hangt van de auto af, van hoe leeg hij is en van wat de
    // paal mag leveren. Hier een starttijd beloven zou een getal zijn waar
    // niemand achter kan staan.
    if (!PROGRAM_TYPES.includes(this.device_.type)) {
      hint.textContent = `De auto moet om ${doneBy} opgeladen zijn. Hoe lang dat duurt hangt van de auto af, dus de coach begint zo vroeg als nodig is en laadt bij voorkeur op de goedkoopste uren daarvoor.`;
      return;
    }

    const program = this.program_();
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

  /** Het programma dat het apparaat klaar heeft staan, als het paneel het kent. */
  program_() {
    const entityId = this.device_?.entities?.program;
    if (!entityId || !this.feed_) return undefined;
    return programFor(this.feed_.get(entityId)?.state);
  }

  /**
   * Waarschuwen als de klaar-tijd voorbij de laatst bekende prijs ligt.
   *
   * Een dynamisch tarief is maar een dag vooruit bekend: die van vandaag
   * helemaal en die van morgen ergens in de middag. Vraag je om klaar te zijn
   * om zeven uur morgenavond, dan is er simpelweg geen prijs voor de uren waar
   * de coach uit zou kiezen. Dat is het zeggen waard, want vanaf dit scherm
   * ziet zo'n plan er compleet uit.
   *
   * Hij herstelt zichzelf: zodra de prijzen van morgen binnen zijn is de
   * waarschuwing weg.
   */
  paintHorizon_() {
    const notice = this.$("#plan-horizon");
    notice.hidden = true;
    if (!this.feed_ || !this.device_) return;

    const plan = this.plan_();
    if (!plan.enabled) return;

    const deadlines = plan.per_day
      ? plan.days.filter((day) => day.enabled && day.done_by).map((day) => day.done_by)
      : [plan.window.done_by].filter(Boolean);
    if (!deadlines.length) return;

    const forecast = priceForecast(this.feed_, this.settings_?.contract);
    const horizon = forecast[forecast.length - 1]?.end;
    if (!horizon) return;

    const beyond = deadlines.filter((time) => {
      const at = nextAt(time);
      return at && at > horizon;
    });
    if (!beyond.length) return;

    // Een lijst die tot middernacht loopt eindigt óp de volgende dag om 00:00,
    // en dat leest als "bekend tot morgen" terwijl het het omgekeerde betekent.
    // Het laatste moment dat werkelijk gedekt is, is waar de zin over gaat.
    const last = new Date(horizon.getTime() - 1);
    const day = sameDayAsToday(last) ? "vandaag" : "morgen";
    const when =
      horizon.getHours() === 0 && horizon.getMinutes() === 0
        ? `het einde van ${day}`
        : `${day} ${clock(horizon)}`;
    notice.hidden = false;
    this.$("#plan-horizon-text").textContent =
      `De prijzen zijn bekend tot ${when}. Een klaar-tijd daarna kan de coach niet doorrekenen. ` +
      "Hij plant dan met wat hij weet, en dat is zelden het goedkoopste moment. " +
      "De prijzen voor de volgende dag komen meestal in de loop van de middag binnen; daarna klopt de planning weer.";
  }

  /**
   * Wisselen tussen één stel tijden en één per dag.
   *
   * Overstappen naar per dag begint bij wat er al voor elke dag stond, zodat de
   * knop een vertrekpunt is en geen leeg formulier. Alleen de eerste keer: wie
   * al dagen heeft ingevuld en heen en weer klikt, wil die niet overschreven
   * zien. Kwam mee uit Strategie op 27-08-2026.
   */
  setMode_(perDag) {
    const plan = this.plan_();
    const patch = { per_day: perDag };
    if (perDag && !plan.days.length) {
      patch.days = DAYS.map((_, day) => ({ day, enabled: true, ...plan.window }));
    }
    this.save_(patch);
  }

  saveWindow_() {
    const holder = this.$("#plan-same");
    // Alle drie de sleutels gaan mee, en wat dit apparaat niet kent gaat leeg:
    // zo raakt een laadpaal een oude begintijd kwijt zodra er iets bewaard wordt.
    const window_ = { not_before: "", start_by: "", done_by: "" };
    for (const time of timesFor(this.device_)) {
      window_[time.key] = holder.querySelector(`[data-window="${time.key}"]`).value || "";
    }
    this.save_({ window: window_ });
  }

  saveDays_() {
    const holder = this.$("#plan-days");
    const days = [];
    for (let day = 0; day < DAYS.length; day += 1) {
      const entry = {
        day,
        enabled: holder.querySelector(`[data-day="${day}"]`).checked,
        not_before: "",
        start_by: "",
        done_by: "",
      };
      for (const time of timesFor(this.device_)) {
        entry[time.key] =
          holder.querySelector(`[data-day-time="${day}:${time.key}"]`).value || "";
      }
      days.push(entry);
    }
    this.save_({ days });
  }

  async save_(patch) {
    if (!this.device_ || !this.hass) return;
    const status = this.$("#plan-status");
    try {
      const settings = await this.hass.callWS({
        type: "domotiapp_coach/device/schedule",
        device_id: this.device_.id,
        ...patch,
      });
      this.settings_ = settings;
      status.textContent = "";
      status.classList.remove("bad");
      this.fire("dac-settings-saved", { settings });
      this.paint_();
    } catch (error) {
      console.warn("[DomotiApp Coach] kon het schema niet opslaan", error);
      status.textContent = "Dit is niet opgeslagen. Probeer het nog een keer.";
      status.classList.add("bad");
      // Terugzetten wat er op het scherm al veranderd was, anders staat er iets
      // dat nergens is opgeschreven.
      this.paint_();
    }
  }
}

define("dac-schedule-sheet", DacScheduleSheet);
