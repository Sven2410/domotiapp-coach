/**
 * Overzicht -- the live picture of what the house is doing right now.
 *
 * The coach sits at the top, because the advice is the product; the numbers
 * underneath are what it is reasoning from. Nothing above it competes for the
 * position: no greeting, no clock, no badges.
 *
 * Values come from the customer's own sensors once they are mapped under
 * Instellingen, and from a simulated house until then.
 */

import { DacElement, define } from "../base.js";
import { icons } from "../icons.js";
import { DemoSource, LiveSource } from "../data-source.js";
import { level, levelTone, percent, power, powerText, price as fmtPrice } from "../format.js";
import "../components/stat-tile.js";
import "../components/energy-flow.js";

const REFRESH_MS = 2000;

/** Surplus worth acting on, in watts -- roughly a dishwasher. */
const SURPLUS_W = 1500;

/** Import worth mentioning, in watts. */
const HEAVY_IMPORT_W = 2500;

/**
 * Rule-based advice -- the first, deliberately simple version of the coach.
 *
 * The order is the priority order: an opportunity to use free electricity beats
 * a warning about an expensive hour, because acting on it makes the warning
 * moot.
 */
function advise(r, thresholds, configured) {
  if (!configured) {
    return {
      tone: "var(--dac-accent-hi)",
      tag: "Instellen",
      title: "Koppel je sensoren",
      body:
        "Je ziet nu voorbeeldwaarden van een gesimuleerde woning. Ga naar Instellingen en kies onder Energiebronnen welke sensoren je opwek, verbruik en meterstand meten — daarna rekent de coach op je eigen huis.",
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
    .coach .demo-note {
      margin-top: 14px;
      display: inline-flex; align-items: center; gap: 7px;
      font-size: 12px; color: var(--dac-ink-3);
    }
    .coach .demo-note .icon { width: 14px; height: 14px; }
    .coach .demo-note[hidden] { display: none; }

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
    this.demo_ = new DemoSource();
    this.live_ = new LiveSource();
    this.settings_ = null;
  }

  set hass(value) {
    this.hass_ = value;
  }

  set settings(value) {
    this.settings_ = value;
  }

  render() {
    const tile = (id) => `<dac-stat-tile id="${id}"></dac-stat-tile>`;

    return `
      <div class="wrap">
        <article class="card coach" id="coach">
          <div class="coach-top">
            <div class="coach-mark">${icons.spark}</div>
            <div class="eyebrow">Energiecoach</div>
            <span class="coach-tag" id="coach-tag">Rustig</span>
          </div>
          <h1 id="coach-title">Je woning draait rustig</h1>
          <p id="coach-body"></p>
          <span class="demo-note" id="demo-note" hidden>
            ${icons.warning}<span>Voorbeeldwaarden — er zijn nog geen sensoren gekoppeld</span>
          </span>
        </article>

        <section class="tiles" aria-label="Live meetwaarden">
          ${tile("t-solar")}${tile("t-house")}${tile("t-grid")}${tile("t-self")}${tile("t-price")}
        </section>

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
    };
    this.flow_ = this.$("#flow");

    this.tick_();
    this.timer_ = setInterval(() => this.tick_(), REFRESH_MS);
  }

  disconnectedCallback() {
    clearInterval(this.timer_);
  }

  tick_() {
    const configured = LiveSource.isConfigured(this.settings_);
    const source = configured ? this.live_ : this.demo_;
    const r = configured ? source.sample(this.hass_, this.settings_) : source.sample();
    const thresholds = this.settings_?.thresholds ?? {
      self_use: { low: 30, high: 70 },
      price: { low: 0.2, high: 0.3 },
    };

    this.$("#demo-note").hidden = configured;

    const exporting = (r.grid ?? 0) < 0;

    this.tiles_.solar.update({
      tone: "var(--dac-solar)",
      icon: "sun",
      label: "Opwek zon",
      ...power(r.solar),
      sub: (r.solar ?? 0) > 50 ? "Zonnepanelen leveren nu" : "Geen opbrengst",
      series: source.series("solar"),
    });

    this.tiles_.house.update({
      tone: "var(--dac-house)",
      icon: "house",
      label: "Verbruik woning",
      ...power(r.house),
      sub: (r.house ?? 0) > 2000 ? "Zware verbruiker actief" : "Basisverbruik",
      series: source.series("house"),
    });

    this.tiles_.grid.update({
      tone: exporting ? "var(--dac-grid-out)" : "var(--dac-grid-in)",
      icon: "grid",
      label: exporting ? "Naar het net" : "Van het net",
      ...power(r.grid),
      sub: exporting ? "Je levert terug" : "Je koopt in",
      series: source.series("grid"),
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
          ? "Geen opwek op dit moment"
          : { good: "Je gebruikt je zon goed", warn: "Een deel gaat naar het net", bad: "Het meeste gaat naar het net" }[selfLevel],
      series: source.series("selfUse"),
    });

    const priceLevel = level(r.price, thresholds.price, true);
    this.tiles_.price.update({
      tone: levelTone(priceLevel),
      icon: "euro",
      label: "Energieprijs",
      ...fmtPrice(r.price),
      sub:
        r.price === null
          ? "Geen prijssensor gekoppeld"
          : { good: "Laag tarief", warn: "Gemiddeld tarief", bad: "Hoog tarief" }[priceLevel],
      series: source.series("price"),
    });

    this.flow_.update(r);
    this.updateCoach_(advise(r, thresholds, configured));
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
