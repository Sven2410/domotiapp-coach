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
import { deviceLabel, releaseCopy, typeMeta } from "../devices.js";
import { LiveSource } from "../data-source.js";
import { level, levelTone, percent, power, powerText, price as fmtPrice } from "../format.js";
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

    .steer-grid {
      margin-top: 16px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
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

    button.release {
      margin-top: auto;
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
    button.release:hover { color: var(--dac-ink); border-color: rgba(25,143,217,0.55); }
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
          <p class="panel-sub">Wat de coach straks zelf mag inschakelen. Een apparaat draait alleen mee als je het hier vrijgeeft — een lege vaatwasser is niets waard, hoeveel zon er ook is.</p>
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
    this.$("#steer-grid").innerHTML = list
      .map(
        (device, slot) => `
        <article class="steer" data-slot="${slot}">
          <div class="steer-head">
            <span class="chip">${icons[typeMeta(device.type).icon]}</span>
            <span class="steer-name" data-name="${slot}"></span>
            <span class="steer-now tnum" data-now="${slot}"></span>
          </div>
          <div class="steer-rows" data-rows="${slot}"></div>
          <button class="release" type="button" data-release="${slot}" aria-pressed="false">
            <span class="mark" data-mark="${slot}"></span>
            <span data-release-text="${slot}"></span>
          </button>
          <p class="steer-hint" data-hint="${slot}"></p>
        </article>`
      )
      .join("");

    for (const button of this.$$("[data-release]")) {
      button.addEventListener("click", () => this.toggleReady_(Number(button.dataset.release)));
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
    });
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
