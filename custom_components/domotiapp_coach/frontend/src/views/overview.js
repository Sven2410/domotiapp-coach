/**
 * Overzicht -- the live picture of what the house is doing right now.
 *
 * The coach sits at the top, because the advice is the product; the numbers
 * underneath are what it is reasoning from. Nothing above it competes for the
 * position: no greeting, no clock, no badges.
 *
 * Every value comes from the customer's own sensors. Nothing here invents a
 * number: with no sensors mapped the tiles show dashes and the coach says what
 * is missing, because a dashboard that fills the gap with something plausible
 * is worse than one that admits it does not know.
 */

import { DacElement, define } from "../base.js";
import { icons } from "../icons.js";
import {
  canCommand,
  deviceCommands,
  deviceLabel,
  releaseCopy,
  typeMeta,
} from "../devices.js";
import { LiveSource } from "../data-source.js";
import { level, levelTone, percent, power, powerText, price as fmtPrice } from "../format.js";
import { sheetCss } from "../theme.js";
import "../components/stat-tile.js";
import "../components/energy-flow.js";

/** Heartbeat for the sparklines; live values also arrive on their own events. */
const REFRESH_MS = 2000;

/** Surplus worth acting on, in watts -- roughly a dishwasher. */
const SURPLUS_W = 1500;

/** Import worth mentioning, in watts. */
const HEAVY_IMPORT_W = 2500;

const nl = (value, digits) =>
  value.toLocaleString("nl-NL", { minimumFractionDigits: digits, maximumFractionDigits: digits });

/**
 * Rule-based advice -- the first, deliberately simple version of the coach.
 *
 * The order is the priority order: an opportunity to use free electricity beats
 * a warning about an expensive hour, because acting on it makes the warning
 * moot.
 */
function advise(r, thresholds, configured, alertAt) {
  if (!configured) {
    return {
      tone: "var(--dac-accent-hi)",
      tag: "Instellen",
      title: "Koppel je sensoren",
      body:
        "De coach weet nog niet welke sensoren jouw opwek, verbruik en meterstand meten. Ga naar Instellingen en kies ze onder Energiebronnen — daarna vult dit scherm zich met je eigen cijfers.",
    };
  }

  if (r.solar === null && r.grid === null) {
    return {
      tone: "var(--dac-warn)",
      tag: "Let op",
      title: "Geen meetwaarden",
      body:
        "De gekozen sensoren geven op dit moment niets bruikbaars terug. Controleer onder Instellingen of ze nog bestaan en of ze een waarde hebben.",
    };
  }

  // A connection being pushed towards its fuse outranks anything about money:
  // the others cost you, this one trips the house.
  if (r.load !== null && r.load >= alertAt) {
    return {
      tone: "var(--dac-bad)",
      tag: "Let op",
      title: "Je aansluiting wordt zwaar belast",
      body:
        r.loadBasis === "phase"
          ? `Fase ${r.loadWorstPhase} zit op ${percent(r.load).value}% van je hoofdzekering. Zet iets zwaars uit of wacht ermee, anders loop je kans dat de zekering eruit gaat.`
          : `Je trekt nu ${percent(r.load).value}% van wat je aansluiting aankan. Zet iets zwaars uit of wacht ermee.`,
    };
  }

  if ((r.exportW ?? 0) > SURPLUS_W) {
    return {
      tone: "var(--dac-grid-out)",
      tag: "Kans",
      title: "Gebruik je overschot",
      body: `Je levert nu ${powerText(r.exportW)} terug aan het net. Zet de vaatwasser, de wasmachine of de laadpaal aan — dan gebruik je stroom die je anders voor een lagere prijs weggeeft.`,
    };
  }

  if (r.price !== null && r.price >= thresholds.price.high) {
    return {
      tone: "var(--dac-bad)",
      tag: "Let op",
      title: "Stroom is nu duur",
      body: `Je betaalt op dit moment ${fmtPrice(r.price).value} per kWh. Stel zware apparaten uit tot na de avondpiek, dat scheelt direct op je rekening.`,
    };
  }

  if (r.price !== null && r.price <= thresholds.price.low && (r.importW ?? 0) > 0) {
    return {
      tone: "var(--dac-good)",
      tag: "Kans",
      title: "Goedkoop moment",
      body: `Met ${fmtPrice(r.price).value} per kWh zit je onder je normale tarief. Een goed moment om te laden of alvast voor te verwarmen.`,
    };
  }

  if (r.selfUse !== null && r.selfUse < thresholds.self_use.low) {
    return {
      tone: "var(--dac-warn)",
      tag: "Signaal",
      title: "Je zon gaat het net op",
      body: `Van je eigen opwek gebruik je nu ${percent(r.selfUse).value}% zelf. De rest gaat naar het net, waar je er minder voor terugkrijgt dan het je kost om het later in te kopen.`,
    };
  }

  if ((r.importW ?? 0) > HEAVY_IMPORT_W) {
    return {
      tone: "var(--dac-grid-in)",
      tag: "Signaal",
      title: "Veel vraag uit het net",
      body: `Je woning trekt nu ${powerText(r.importW)} uit het net terwijl de zon weinig levert. Kijk of er iets aan staat dat kan wachten.`,
    };
  }

  return {
    tone: "var(--dac-accent-hi)",
    tag: "Rustig",
    title: "Je woning draait rustig",
    body: "Er is nu niets dat om actie vraagt. De coach kijkt mee en meldt zich zodra er iets te winnen valt.",
  };
}

class DacViewOverview extends DacElement {
  static css = /* css */ `
    :host { display: block; }

    .wrap {
      max-width: var(--dac-maxw);
      margin: 0 auto;
      padding: 24px max(22px, var(--dac-safe-r)) calc(64px + var(--dac-safe-b)) max(22px, var(--dac-safe-l));
      display: flex;
      flex-direction: column;
      gap: 18px;
    }

    /* ---- coach ---- */
    .coach { position: relative; overflow: hidden; padding: 22px 24px 24px; }
    .coach::before {
      content: "";
      position: absolute;
      inset: -1px -1px auto -1px;
      height: 3px;
      background: linear-gradient(90deg, var(--coach-tone, var(--dac-accent-hi)), transparent 85%);
      transition: background 500ms ease;
    }
    .coach-top { display: flex; align-items: center; gap: 10px; }
    .coach-mark {
      width: 36px; height: 36px; flex: 0 0 auto;
      display: grid; place-items: center;
      border-radius: 11px;
      color: var(--coach-tone, var(--dac-accent-hi));
      background: color-mix(in srgb, var(--coach-tone, var(--dac-accent-hi)) 13%, transparent);
      border: 1px solid color-mix(in srgb, var(--coach-tone, var(--dac-accent-hi)) 30%, transparent);
      transition: color 500ms ease, background 500ms ease, border-color 500ms ease;
    }
    .coach-mark .icon { width: 19px; height: 19px; }
    .coach-where {
      display: flex; flex-direction: column; gap: 1px; min-width: 0;
    }
    .coach-where .home {
      font-size: 13px; font-weight: 600; color: var(--dac-ink);
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .coach-where .home[hidden] { display: none; }
    .coach-tag {
      margin-left: auto;
      padding: 5px 11px;
      border-radius: var(--dac-radius-pill);
      font-size: 11px; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase;
      color: var(--coach-tone, var(--dac-accent-hi));
      background: color-mix(in srgb, var(--coach-tone, var(--dac-accent-hi)) 12%, transparent);
      transition: color 500ms ease, background 500ms ease;
      white-space: nowrap;
    }
    .coach h1 {
      margin: 16px 0 0;
      font-size: clamp(22px, 3.2vw, 30px);
      font-weight: 600;
      letter-spacing: -0.01em;
      line-height: 1.18;
    }
    .coach p {
      margin: 10px 0 0;
      max-width: 78ch;
      font-size: 14.5px;
      line-height: 1.62;
      color: var(--dac-ink-2);
    }

    /* ---- tiles ---- */
    .tiles {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(206px, 1fr));
      gap: 14px;
    }

    /* ---- flow ---- */
    .panel { padding: 20px 22px 22px; }
    .panel-head h2 {
      margin: 4px 0 0;
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -0.005em;
    }
    /* Block, not flex: an inline SVG in a flex row falls back to its 300px
       intrinsic width instead of filling the card. */
    .flow-holder { margin-top: 12px; display: block; }
    .flow-holder dac-energy-flow { display: block; width: 100%; max-width: 700px; margin: 0 auto; }

    /* ---- per phase ---- */
    .phases[hidden] { display: none; }
    .phase-rows { margin-top: 14px; display: grid; gap: 10px; }
    .phase-row {
      display: grid;
      grid-template-columns: 34px minmax(0, 1fr) auto;
      align-items: center;
      gap: 14px;
    }
    .phase-row .name { font-size: 13px; font-weight: 700; color: var(--dac-ink-2); letter-spacing: 0.06em; }
    .phase-row .bar {
      position: relative;
      height: 8px;
      border-radius: 99px;
      background: rgba(255,255,255,0.07);
      overflow: hidden;
    }
    .phase-row .bar i {
      position: absolute;
      inset: 0 auto 0 0;
      border-radius: 99px;
      background: var(--tone, var(--dac-ink-3));
      transition: width 500ms cubic-bezier(0.22,0.61,0.36,1), background 400ms ease;
    }
    .phase-row .values {
      display: flex;
      gap: 12px;
      font-size: 12.5px;
      color: var(--dac-ink-2);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }
    .phase-row .values b { color: var(--dac-ink); font-weight: 600; }
    .phase-row .values .none { color: var(--dac-ink-3); font-style: italic; }
    @media (max-width: 560px) {
      .phase-row { grid-template-columns: 30px minmax(0, 1fr); row-gap: 4px; }
      .phase-row .values { grid-column: 2; gap: 10px; font-size: 12px; }
    }

    /* ---- steerable devices ---- */
    .panel-sub { margin: 8px 0 0; font-size: 13px; line-height: 1.55; color: var(--dac-ink-2); max-width: 70ch; }

    /*
     * One card at a time, chosen from a row of names.
     *
     * Underneath each other they turned the overview into a column you had to
     * scroll past on a phone before reaching the energy flow -- and the device
     * you wanted was reliably the last one. The row scrolls sideways; the cards
     * do not stack.
     */
    .steer-tabs {
      display: flex;
      gap: 8px;
      margin-top: 14px;
      overflow-x: auto;
      scrollbar-width: none;
      scroll-snap-type: x proximity;
      padding-bottom: 2px;
    }
    .steer-tabs::-webkit-scrollbar { display: none; }
    .steer-tabs[hidden] { display: none; }

    .steer-tab {
      flex: 0 0 auto;
      scroll-snap-align: start;
      display: inline-flex; align-items: center; gap: 8px;
      min-height: 38px;
      padding: 8px 14px;
      border-radius: var(--dac-radius-pill);
      border: 1px solid var(--dac-border);
      background: transparent;
      color: var(--dac-ink-2);
      font: inherit; font-size: 13px; font-weight: 500;
      white-space: nowrap;
      cursor: pointer;
      -webkit-tap-highlight-color: transparent;
      transition: color 180ms ease, border-color 180ms ease, background 180ms ease;
    }
    .steer-tab:hover { color: var(--dac-ink); border-color: var(--dac-border-hi); }
    .steer-tab[aria-selected="true"] {
      color: var(--dac-ink); font-weight: 600;
      border-color: rgba(25,143,217,0.55);
      background: var(--dac-accent-soft);
    }
    /* Released or not, visible without opening the card. */
    .steer-tab .dot {
      width: 7px; height: 7px; flex: 0 0 auto;
      border-radius: 50%;
      background: var(--dac-ink-3);
    }
    .steer-tab .dot.on { background: var(--dac-good); }

    .steer-grid { margin-top: 12px; display: grid; gap: 12px; }
    .steer[hidden] { display: none; }

    .sr {
      position: absolute; width: 1px; height: 1px;
      margin: -1px; padding: 0; overflow: hidden;
      clip-path: inset(50%); white-space: nowrap;
    }

    .steer {
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 14px 15px 15px;
      border-radius: var(--dac-radius-sm);
      border: 1px solid var(--dac-border);
      background: rgba(255,255,255,0.022);
    }

    .steer-head { display: flex; align-items: center; gap: 10px; min-width: 0; }
    .steer-head .chip {
      width: 34px; height: 34px; flex: 0 0 auto;
      display: grid; place-items: center;
      border-radius: 11px;
      color: var(--dac-accent-hi);
      background: var(--dac-accent-soft);
      border: 1px solid rgba(25,143,217,0.28);
    }
    .steer-head .chip .icon { width: 18px; height: 18px; }
    .steer-name {
      flex: 1 1 auto; min-width: 0;
      font-size: 14.5px; font-weight: 600;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .steer-now { flex: 0 0 auto; font-size: 13px; font-weight: 600; color: var(--dac-ink-2); }

    .steer-rows { display: grid; gap: 6px; }
    .steer-rows div { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
    .steer-rows .k { font-size: 12.5px; color: var(--dac-ink-3); }
    .steer-rows .v {
      font-size: 12.5px; font-weight: 500; color: var(--dac-ink);
      font-variant-numeric: tabular-nums; text-align: right;
    }

    .steer-actions {
      margin-top: auto;
      display: flex; flex-wrap: wrap; gap: 8px;
    }
    .steer-actions button { flex: 1 1 170px; }

    button.release, button.manual {
      display: flex; align-items: center; justify-content: center; gap: 8px;
      padding: 11px 16px;
      min-height: 44px;
      border-radius: var(--dac-radius-pill);
      border: 1px solid var(--dac-border-hi);
      background: var(--dac-surface);
      color: var(--dac-ink-2);
      font: inherit; font-size: 13.5px; font-weight: 500;
      cursor: pointer;
      transition: border-color 200ms ease, background 200ms ease, color 200ms ease;
      -webkit-tap-highlight-color: transparent;
    }
    button.release:hover, button.manual:hover { color: var(--dac-ink); border-color: rgba(25,143,217,0.55); }
    button.manual .icon { width: 16px; height: 16px; color: var(--dac-accent-hi); }
    button.manual[hidden] { display: none; }
    button.release[aria-pressed="true"] {
      border-color: rgba(12,163,12,0.5);
      background: rgba(12,163,12,0.14);
      color: var(--dac-ink);
      font-weight: 600;
    }
    button.release .mark { display: grid; color: var(--dac-good); }
    button.release .mark .icon { width: 16px; height: 16px; }

    .steer-hint { margin: 0; font-size: 12px; line-height: 1.45; color: var(--dac-ink-3); }
    .steer-hint:empty { display: none; }

    /* ---- manual control ---- */
    ${sheetCss}

    .cmd-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 16px; }
    .cmd {
      display: flex; align-items: center; gap: 10px;
      min-height: 50px;
      padding: 12px 14px;
      border-radius: var(--dac-radius-sm);
      border: 1px solid var(--dac-border-hi);
      background: var(--dac-surface);
      color: var(--dac-ink);
      font: inherit; font-size: 14px; font-weight: 500;
      text-align: left;
      cursor: pointer;
      -webkit-tap-highlight-color: transparent;
      transition: border-color 180ms ease, background 180ms ease;
    }
    .cmd:hover:not(:disabled) { border-color: rgba(25,143,217,0.55); background: var(--dac-surface-hi); }
    .cmd:disabled { opacity: 0.45; cursor: default; }
    .cmd .icon { width: 18px; height: 18px; flex: 0 0 auto; color: var(--dac-accent-hi); }
    /* Rebooting drops whatever the charger is doing, so it gets its own row and
       its own colour rather than sitting in the grid as a fifth equal. */
    .cmd.care { grid-column: 1 / -1; }
    .cmd.care .icon { color: var(--dac-warn); }
    .cmd-note { grid-column: 1 / -1; margin: -2px 0 0; font-size: 12px; line-height: 1.45; color: var(--dac-ink-3); }

    .legend { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 14px; }
    .legend span { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: var(--dac-ink-2); }
    .legend i { width: 14px; height: 3px; border-radius: 2px; display: inline-block; flex: 0 0 auto; }

    @media (max-width: 640px) {
      .wrap {
        padding: 16px max(12px, var(--dac-safe-r)) calc(48px + var(--dac-safe-b)) max(12px, var(--dac-safe-l));
        gap: 14px;
      }
      .coach { padding: 18px 16px 20px; }
      .coach h1 { font-size: 21px; margin-top: 14px; }
      .coach p { font-size: 14px; }
      .panel { padding: 16px 14px 18px; }
      .tiles { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
    }
  `;

  constructor() {
    super();
    this.source_ = new LiveSource();
    this.settings_ = null;
  }

  /** @param {import("../state-feed.js").StateFeed} feed */
  set stateFeed(feed) {
    this.feed_ = feed;
    // Values arrive on their own events, so the dashboard follows the house
    // rather than waiting for the next beat of a timer.
    if (this.isConnected) this.listen_();
  }

  set settings(value) {
    this.settings_ = value;
    if (this.rendered_) this.tick_();
  }

  render() {
    const tile = (id) => `<dac-stat-tile id="${id}"></dac-stat-tile>`;

    return `
      <div class="wrap">
        <article class="card coach" id="coach">
          <div class="coach-top">
            <div class="coach-mark">${icons.spark}</div>
            <div class="coach-where">
              <span class="home" id="home-name" hidden></span>
              <span class="eyebrow">Energiecoach</span>
            </div>
            <span class="coach-tag" id="coach-tag">Rustig</span>
          </div>
          <h1 id="coach-title">Je woning draait rustig</h1>
          <p id="coach-body"></p>
        </article>

        <section class="tiles" aria-label="Live meetwaarden">
          ${tile("t-solar")}${tile("t-house")}${tile("t-grid")}${tile("t-load")}${tile("t-self")}${tile("t-price")}
        </section>

        <article class="card panel phases" id="phases" hidden>
          <div class="panel-head">
            <div class="eyebrow">Per fase</div>
            <h2 id="phases-title">Belasting van je aansluiting</h2>
          </div>
          <div class="phase-rows" id="phase-rows"></div>
        </article>

        <article class="card panel steerable" id="steerable" hidden>
          <div class="panel-head">
            <div class="eyebrow">Sturing</div>
            <h2>Aanstuurbare apparaten</h2>
          </div>
          <p class="panel-sub">Wat de coach straks zelf mag inschakelen.</p>
          <div class="steer-tabs" id="steer-tabs" role="tablist" aria-label="Aanstuurbare apparaten" hidden></div>
          <div class="steer-grid" id="steer-grid"></div>
        </article>

        <article class="card panel">
          <div class="panel-head">
            <div class="eyebrow">Realtime</div>
            <h2>Energiestroom</h2>
          </div>
          <div class="flow-holder"><dac-energy-flow id="flow"></dac-energy-flow></div>
          <div class="legend" id="legend"></div>
        </article>

        <dialog class="sheet" id="manual" aria-labelledby="manual-title">
          <div class="sheet-head">
            <div>
              <div class="eyebrow">Handmatige besturing</div>
              <h3 id="manual-title"></h3>
            </div>
            <button class="sheet-close" type="button" id="manual-close" aria-label="Sluiten">${icons.close}</button>
          </div>
          <p class="sheet-sub" id="manual-sub"></p>
          <div class="cmd-grid" id="manual-grid"></div>
          <p class="sheet-status" id="manual-status" role="status" aria-live="polite"></p>
        </dialog>
      </div>
    `;
  }

  afterRender() {
    this.tiles_ = {
      solar: this.$("#t-solar"),
      house: this.$("#t-house"),
      grid: this.$("#t-grid"),
      self: this.$("#t-self"),
      price: this.$("#t-price"),
      load: this.$("#t-load"),
    };
    this.flow_ = this.$("#flow");

    const sheet = this.$("#manual");
    this.$("#manual-close").addEventListener("click", () => sheet.close());
    // Tapping the darkened area closes it. The hit test is on coordinates
    // rather than the target alone, because a click on the dialog's own padding
    // also reports the dialog as its target.
    sheet.addEventListener("click", (event) => {
      if (event.target !== sheet) return;
      const box = sheet.getBoundingClientRect();
      const inside =
        event.clientX >= box.left &&
        event.clientX <= box.right &&
        event.clientY >= box.top &&
        event.clientY <= box.bottom;
      if (!inside) sheet.close();
    });
  }

  onConnect() {
    // Both of these have to come back on every attach. The view is cached and
    // swapped in and out of the panel, and starting them once meant the
    // dashboard stopped updating the first time it was navigated away from.
    this.listen_();
    this.tick_();
    clearInterval(this.timer_);
    this.timer_ = setInterval(() => this.tick_(), REFRESH_MS);
  }

  onDisconnect() {
    clearInterval(this.timer_);
    this.timer_ = null;
    this.unsubscribe_?.();
    this.unsubscribe_ = null;
    // A modal that is detached loses its place in the top layer, so it would
    // come back as a panel stuck in the middle of the page.
    this.$("#manual")?.close();
  }

  listen_() {
    this.unsubscribe_?.();
    this.unsubscribe_ = this.feed_?.subscribe(() => this.requestTick_());
  }

  /**
   * Coalesce the burst of events a single meter reading produces.
   *
   * A three-phase meter fires several state_changed events within milliseconds;
   * redrawing per event would recompute the whole view five times for one
   * change and stutter the sparklines.
   */
  requestTick_() {
    if (this.pending_) return;
    this.pending_ = true;
    setTimeout(() => {
      this.pending_ = false;
      if (this.rendered_) this.tick_();
    }, 250);
  }

  tick_() {
    if (!this.feed_) return;

    const configured = LiveSource.isConfigured(this.settings_);
    const r = this.source_.sample(this.feed_, this.settings_);
    const thresholds = this.settings_?.thresholds ?? {
      self_use: { low: 30, high: 70 },
      price: { low: 0.2, high: 0.3 },
    };

    const homeName = (this.settings_?.installation?.home_name ?? "").trim();
    const nameEl = this.$("#home-name");
    nameEl.textContent = homeName;
    nameEl.hidden = !homeName;

    const exporting = (r.grid ?? 0) < 0;

    this.tiles_.solar.update({
      tone: "var(--dac-solar)",
      icon: "sun",
      label: "Opwek zon",
      ...power(r.solar),
      sub: this.sub_(r.solar, (v) => (v > 50 ? "Zonnepanelen leveren nu" : "Geen opbrengst")),
      series: this.source_.series("solar"),
    });

    this.tiles_.house.update({
      tone: "var(--dac-house)",
      icon: "house",
      label: "Verbruik woning",
      ...power(r.house),
      sub: this.sub_(r.house, (v) => (v > 2000 ? "Zware verbruiker actief" : "Basisverbruik")),
      series: this.source_.series("house"),
    });

    this.tiles_.grid.update({
      tone: exporting ? "var(--dac-grid-out)" : "var(--dac-grid-in)",
      icon: "grid",
      label: r.grid === null ? "Net" : exporting ? "Naar het net" : "Van het net",
      ...power(r.grid),
      sub: this.sub_(r.grid, () => (exporting ? "Je levert terug" : "Je koopt in")),
      series: this.source_.series("grid"),
    });

    // Zelfbenutting is a share, not a rate, so it wears the status scale rather
    // than a stream colour: below 30% red, up to 70% amber, above that green.
    const selfLevel = level(r.selfUse, thresholds.self_use, false);
    this.tiles_.self.update({
      tone: levelTone(selfLevel),
      icon: "leaf",
      label: "Zelfbenutting",
      ...percent(r.selfUse),
      sub:
        r.selfUse === null
          ? configured
            ? "Geen opwek op dit moment"
            : "Nog niet ingesteld"
          : {
              good: "Je gebruikt je zon goed",
              warn: "Een deel gaat naar het net",
              bad: "Het meeste gaat naar het net",
            }[selfLevel],
      series: this.source_.series("selfUse"),
    });

    const priceLevel = level(r.price, thresholds.price, true);
    this.tiles_.price.update({
      tone: levelTone(priceLevel),
      icon: "euro",
      label: "Energieprijs",
      ...fmtPrice(r.price),
      sub:
        r.price === null
          ? "Nog geen contract ingevuld"
          : { good: "Laag tarief", warn: "Gemiddeld tarief", bad: "Hoog tarief" }[priceLevel],
      series: this.source_.series("price"),
    });

    // The alert threshold is the one number that says "too much" here, so the
    // tile turns on the same boundary the notification uses rather than a
    // second, quietly different one.
    const alertAt = Number(this.settings_?.strategy?.load_alert?.threshold_percent) || 80;
    const loadBounds = { low: Math.round(alertAt * 0.75), high: alertAt };
    const loadLevel = level(r.load, loadBounds, true);
    this.tiles_.load.update({
      tone: levelTone(loadLevel),
      icon: "plug",
      label: "Belastbaarheid",
      ...percent(r.load),
      sub:
        r.load === null
          ? "Aansluiting nog niet ingevuld"
          : r.loadBasis === "phase"
            ? `Zwaarst belaste fase (${r.loadWorstPhase})`
            : "Van het maximale netvermogen",
      series: this.source_.series("load"),
    });

    this.updatePhases_(r, alertAt);
    this.updateSteerable_(r.devices);
    this.flow_.update(r);
    this.updateLegend_();
    this.updateCoach_(advise(r, thresholds, configured, alertAt));
  }

  /**
   * The key under the diagram, listing only what the diagram is drawing.
   *
   * The device bubbles come and go with what is switched on, so a fixed
   * "Apparaat / Apparaat" pair described two circles that are usually not there
   * and named neither of them when they were. The two grid entries do stay:
   * they are the two states of one link, and which of them applies flips within
   * seconds -- a key that flickers along with it is harder to read than one that
   * explains both colours.
   */
  updateLegend_() {
    const entries = [
      { tone: "var(--dac-solar)", label: "Zon" },
      { tone: "var(--dac-house)", label: "Woning" },
      { tone: "var(--dac-grid-in)", label: "Van het net" },
      { tone: "var(--dac-grid-out)", label: "Naar het net" },
      ...this.flow_.bubbles,
    ];

    // Rebuilt only when it would actually read differently: this runs on every
    // meter reading.
    const key = entries.map((entry) => entry.label).join("|");
    if (key === this.legendKey_) return;
    this.legendKey_ = key;

    this.$("#legend").replaceChildren(
      ...entries.map((entry) => {
        const item = document.createElement("span");
        const swatch = document.createElement("i");
        swatch.style.background = entry.tone;
        // Device names are the customer's own text, so it goes in as text.
        item.append(swatch, document.createTextNode(` ${entry.label}`));
        return item;
      })
    );
  }

  /** The per-phase card, when the customer has phase sensors and wants them. */
  updatePhases_(r, alertAt) {
    const card = this.$("#phases");
    const show = Boolean(r.phases) && this.settings_?.sources?.phases_on_overview;
    card.hidden = !show;
    if (!show) return;

    const fuse = Number(this.settings_?.installation?.fuse_amps) || 0;
    this.$("#phases-title").textContent = fuse
      ? `Belasting per fase, tegen ${fuse} A`
      : "Belasting per fase";

    const bounds = { low: Math.round(alertAt * 0.75), high: alertAt };

    this.$("#phase-rows").innerHTML = r.phases
      .map((phase) => {
        // The bar follows the amps, measured or worked out from the power, so a
        // customer who mapped only one of the two still gets a reading.
        const share =
          fuse > 0 && Number.isFinite(phase.amps) ? (phase.amps / fuse) * 100 : null;
        const pct = share === null ? 0 : Math.min(share, 100);
        const tone = levelTone(level(share, bounds, true));

        // Only what is actually measured is printed. A derived value would look
        // like a reading from a sensor that is not there.
        const bits = [];
        if (Number.isFinite(phase.current)) bits.push(`<b>${nl(phase.current, 1)}</b> A`);
        if (Number.isFinite(phase.power)) {
          const { value, unit } = power(phase.power);
          bits.push(`<b>${value}</b> ${unit}`);
        }
        if (Number.isFinite(phase.voltage)) bits.push(`<b>${nl(phase.voltage, 0)}</b> V`);

        return `
          <div class="phase-row" style="--tone: ${tone}">
            <span class="name">${phase.label}</span>
            <span class="bar"><i style="width: ${pct.toFixed(1)}%"></i></span>
            <span class="values">${bits.join("") || "<span class=\"none\">geen meetwaarde</span>"}</span>
          </div>`;
      })
      .join("");
  }

  /**
   * The devices the coach may steer, and whether they are released for it.
   *
   * Same card as the one behind a bubble on the diagram, but standing still:
   * the bubbles only exist while something is running, and a dishwasher has to
   * be releasable exactly when it is *not* running yet.
   *
   * Steering itself does not exist yet. What does exist is the customer's half
   * of it: nobody but the person in the kitchen knows the machine is loaded and
   * shut.
   */
  updateSteerable_(devices) {
    const card = this.$("#steerable");
    const list = (devices ?? []).filter((device) => device.controllable);

    card.hidden = !list.length;
    if (!list.length) return;

    // Rebuilt only when the set of devices changes: the button in each card
    // must survive the two-second refresh, and a control that is replaced under
    // a finger is a control that misses the tap.
    const key = list.map((device) => device.id).join("|");
    if (key !== this.steerKey_) {
      this.steerKey_ = key;
      this.buildSteerable_(list);
    }
    this.fillSteerable_(list);
  }

  buildSteerable_(list) {
    // Whatever the sheet was pointing at may be exactly what just changed, so
    // it closes rather than keeping a device that no longer exists on screen.
    this.$("#manual").close();

    // The chooser is only worth its space from two devices on; with one, the
    // card underneath already says which device this is.
    const tabs = this.$("#steer-tabs");
    tabs.hidden = list.length < 2;
    tabs.innerHTML = list
      .map(
        (device, slot) => `
        <button class="steer-tab" type="button" role="tab" id="steer-tab-${slot}"
                data-tab="${slot}" aria-controls="steer-panel-${slot}" aria-selected="false">
          <span class="dot" data-tab-dot="${slot}"></span>
          <span data-tab-name="${slot}"></span>
          <span class="sr" data-tab-state="${slot}"></span>
        </button>`
      )
      .join("");

    this.$("#steer-grid").innerHTML = list
      .map(
        (device, slot) => `
        <article class="steer" data-slot="${slot}" id="steer-panel-${slot}"
                 role="tabpanel" aria-labelledby="steer-tab-${slot}">
          <div class="steer-head">
            <span class="chip">${icons[typeMeta(device.type).icon]}</span>
            <span class="steer-name" data-name="${slot}"></span>
            <span class="steer-now tnum" data-now="${slot}"></span>
          </div>
          <div class="steer-rows" data-rows="${slot}"></div>
          <div class="steer-actions">
            <button class="release" type="button" data-release="${slot}" aria-pressed="false">
              <span class="mark" data-mark="${slot}"></span>
              <span data-release-text="${slot}"></span>
            </button>
            <button class="manual" type="button" data-manual="${slot}" hidden>
              ${icons.sliders}<span>Handmatige besturing</span>
            </button>
          </div>
          <p class="steer-hint" data-hint="${slot}"></p>
        </article>`
      )
      .join("");

    for (const button of this.$$("[data-release]")) {
      button.addEventListener("click", () => this.toggleReady_(Number(button.dataset.release)));
    }
    for (const button of this.$$("[data-manual]")) {
      button.addEventListener("click", () => this.openManual_(Number(button.dataset.manual)));
    }
    for (const tab of this.$$("[data-tab]")) {
      tab.addEventListener("click", () => this.selectSteer_(Number(tab.dataset.tab)));
      tab.addEventListener("keydown", (event) => this.stepSteer_(event, Number(tab.dataset.tab)));
    }
  }

  fillSteerable_(list) {
    this.steerDevices_ = list;
    const ready = new Set(this.settings_?.ready_devices ?? []);

    list.forEach((device, slot) => {
      const copy = releaseCopy(device);
      const on = ready.has(device.id);

      // Names and readings are the customer's own, so they go in as text.
      this.$(`[data-name="${slot}"]`).textContent = deviceLabel(device);
      this.$(`[data-now="${slot}"]`).textContent = powerText(device.watts);

      const rows = this.$(`[data-rows="${slot}"]`);
      rows.replaceChildren(
        ...(device.details ?? []).map((row) => {
          const line = document.createElement("div");
          const key = document.createElement("span");
          key.className = "k";
          key.textContent = row.label;
          const value = document.createElement("span");
          value.className = "v";
          value.textContent = row.text;
          line.append(key, value);
          return line;
        })
      );

      const button = this.$(`[data-release="${slot}"]`);
      button.setAttribute("aria-pressed", String(on));
      this.$(`[data-mark="${slot}"]`).innerHTML = on ? icons.check : "";
      this.$(`[data-release-text="${slot}"]`).textContent = on ? "Vrijgegeven" : copy.label;
      this.$(`[data-hint="${slot}"]`).textContent = on ? "" : copy.hint;

      // Only where there is something to send to: a brand that takes commands,
      // and the Home Assistant device to send them to.
      this.$(`[data-manual="${slot}"]`).hidden = !canCommand(device);

      const name = this.$(`[data-tab-name="${slot}"]`);
      if (name) {
        name.textContent = deviceLabel(device);
        this.$(`[data-tab-dot="${slot}"]`).classList.toggle("on", on);
        this.$(`[data-tab-state="${slot}"]`).textContent = on ? " — vrijgegeven" : "";
      }
    });

    this.paintSteerChoice_();
  }

  /** Show the chosen device, remembering it across the refresh. */
  paintSteerChoice_() {
    const list = this.steerDevices_ ?? [];
    if (!list.length) return;

    let index = list.findIndex((device) => device.id === this.steerActive_);
    if (index < 0) index = 0;
    this.steerActive_ = list[index].id;

    list.forEach((_, slot) => {
      const chosen = slot === index;
      this.$(`[data-slot="${slot}"]`).hidden = !chosen;
      const tab = this.$(`[data-tab="${slot}"]`);
      if (tab) {
        tab.setAttribute("aria-selected", String(chosen));
        tab.tabIndex = chosen ? 0 : -1;
      }
    });
  }

  selectSteer_(slot) {
    const device = this.steerDevices_?.[slot];
    if (!device) return;
    this.steerActive_ = device.id;
    this.paintSteerChoice_();
  }

  /** Arrow keys walk the row, the way a tablist is expected to behave. */
  stepSteer_(event, slot) {
    const step = { ArrowRight: 1, ArrowLeft: -1, Home: -Infinity, End: Infinity }[event.key];
    if (step === undefined) return;
    event.preventDefault();

    const count = this.steerDevices_?.length ?? 0;
    const next =
      step === -Infinity ? 0 : step === Infinity ? count - 1 : (slot + step + count) % count;
    this.selectSteer_(next);
    this.$(`[data-tab="${next}"]`)?.focus();
  }

  /**
   * Release a device, or take that back.
   *
   * Written through its own websocket command, which is the one thing here a
   * customer may change without being an administrator.
   */
  async toggleReady_(slot) {
    const device = this.steerDevices_?.[slot];
    if (!device || !this.hass) return;

    const ready = new Set(this.settings_?.ready_devices ?? []);
    const next = !ready.has(device.id);

    // Shown straight away rather than after the round trip: a button that waits
    // for the server before it moves reads as a button that did not work.
    if (next) ready.add(device.id);
    else ready.delete(device.id);
    this.settings_ = { ...this.settings_, ready_devices: [...ready] };
    this.fillSteerable_(this.steerDevices_);

    try {
      await this.hass.callWS({
        type: "domotiapp_coach/device/ready",
        device_id: device.id,
        ready: next,
      });
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de vrijgave niet opslaan", error);
      // Put it back: pretending it worked would have the customer believe the
      // machine is released when it is not.
      if (next) ready.delete(device.id);
      else ready.add(device.id);
      this.settings_ = { ...this.settings_, ready_devices: [...ready] };
      this.fillSteerable_(this.steerDevices_);
    }
  }

  /**
   * Manual control: the same commands the coach will use, with a person on the
   * button.
   *
   * It lives behind a press rather than on the card, because these are the only
   * controls in the panel that change something in the house -- and a row of
   * them under a live reading is a row you hit while scrolling.
   */
  openManual_(slot) {
    const device = this.steerDevices_?.[slot];
    if (!device || !canCommand(device)) return;

    this.manualDevice_ = device;
    this.manualActions_ = deviceCommands(device);

    this.$("#manual-title").textContent = deviceLabel(device);
    this.$("#manual-sub").textContent =
      "Deze opdrachten gaan rechtstreeks naar het apparaat. De coach stuurt nog niets uit zichzelf.";
    this.setManualStatus_("", "");

    // Labels and hints are the panel's own text, not the customer's, so they go
    // in as markup along with their icons.
    this.$("#manual-grid").innerHTML = this.manualActions_
      .map(
        (action, index) => `
        <button class="cmd${action.care ? " care" : ""}" type="button" data-cmd="${index}">
          ${icons[action.icon] ?? ""}<span>${action.label}</span>
        </button>
        ${action.hint ? `<p class="cmd-note">${action.hint}</p>` : ""}`
      )
      .join("");

    for (const button of this.$$("#manual-grid .cmd")) {
      button.addEventListener("click", () =>
        this.sendCommand_(this.manualActions_[Number(button.dataset.cmd)])
      );
    }

    this.$("#manual").showModal();
  }

  /**
   * Send one command, and say what came of it.
   *
   * Nothing is assumed to have worked: the charger is the only one who knows,
   * and a failed call has to read as failed rather than as silence.
   */
  async sendCommand_(action) {
    const device = this.manualDevice_;
    if (!action || !device || !this.hass || this.sending_) return;

    const { domain, service, data } = action.call;

    this.sending_ = true;
    this.setManualButtons_(true);
    this.setManualStatus_(`${action.label}…`, "");

    try {
      await this.hass.callService(domain, service, data);
      this.setManualStatus_(`${action.label} verstuurd.`, "good");
    } catch (error) {
      console.warn("[DomotiApp Coach] opdracht mislukt", error);
      this.setManualStatus_(
        `${action.label} is niet gelukt: ${error?.message || "het apparaat gaf geen antwoord"}.`,
        "bad"
      );
    } finally {
      this.sending_ = false;
      this.setManualButtons_(false);
    }
  }

  setManualStatus_(text, tone) {
    const line = this.$("#manual-status");
    line.textContent = text;
    line.className = `sheet-status${tone ? ` ${tone}` : ""}`;
  }

  /** One command at a time -- two in flight would race in the charger. */
  setManualButtons_(busy) {
    for (const button of this.$$("#manual-grid .cmd")) button.disabled = busy;
  }

  /** Supporting line for a tile, or an honest blank when there is no reading. */
  sub_(value, describe) {
    if (value === null || !Number.isFinite(value)) return "Geen meetwaarde";
    return describe(value);
  }

  updateCoach_(advice) {
    const coach = this.$("#coach");
    coach.style.setProperty("--coach-tone", advice.tone);
    this.$("#coach-tag").textContent = advice.tag;
    this.$("#coach-title").textContent = advice.title;
    this.$("#coach-body").textContent = advice.body;
  }
}

define("dac-view-overview", DacViewOverview);
