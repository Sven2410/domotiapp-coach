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
      padding: 24px 22px 64px;
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
    @media (max-width: 560px) {
      .phase-row { grid-template-columns: 30px minmax(0, 1fr); row-gap: 4px; }
      .phase-row .values { grid-column: 2; gap: 10px; font-size: 12px; }
    }

    .legend { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 14px; }
    .legend span { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: var(--dac-ink-2); }
    .legend i { width: 14px; height: 3px; border-radius: 2px; display: inline-block; flex: 0 0 auto; }

    @media (max-width: 640px) {
      .wrap { padding: 16px 12px 48px; gap: 14px; }
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

        <article class="card panel">
          <div class="panel-head">
            <div class="eyebrow">Realtime</div>
            <h2>Energiestroom</h2>
          </div>
          <div class="flow-holder"><dac-energy-flow id="flow"></dac-energy-flow></div>
          <div class="legend">
            <span><i style="background: var(--dac-solar)"></i> Zon</span>
            <span><i style="background: var(--dac-house)"></i> Woning</span>
            <span><i style="background: var(--dac-grid-in)"></i> Van het net</span>
            <span><i style="background: var(--dac-grid-out)"></i> Naar het net</span>
            <span><i style="background: var(--dac-device-1)"></i> Apparaat</span>
            <span><i style="background: var(--dac-device-2)"></i> Apparaat</span>
          </div>
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
    this.flow_.update(r);
    this.updateCoach_(advise(r, thresholds, configured, alertAt));
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

    this.$("#phase-rows").innerHTML = r.phases
      .map((phase) => {
        const pct =
          fuse > 0 && Number.isFinite(phase.current)
            ? Math.min((phase.current / fuse) * 100, 100)
            : 0;
        const tone = levelTone(
          level(fuse > 0 && Number.isFinite(phase.current) ? (phase.current / fuse) * 100 : null,
            { low: Math.round(alertAt * 0.75), high: alertAt }, true)
        );
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
            <span class="values">${bits.join("") || "—"}</span>
          </div>`;
      })
      .join("");
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
