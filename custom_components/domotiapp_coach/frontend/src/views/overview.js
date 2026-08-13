/**
 * Overzicht -- the live picture of what the house is doing right now.
 *
 * Phase 1 is read-only and runs on simulated values (see demo-data.js), so the
 * layout, hierarchy and colour system can be judged before a single sensor is
 * wired up. The coach panel already runs real rules against those values; it is
 * the seed of phase 2, where the advice starts using history and tariffs.
 */

import { DacElement, define } from "../base.js";
import { icons } from "../icons.js";
import { DemoSource } from "../demo-data.js";
import "../components/stat-tile.js";
import "../components/energy-flow.js";

const REFRESH_MS = 2000;

const kw = (v) =>
  Math.abs(v).toLocaleString("nl-NL", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

const euro = (v) =>
  v.toLocaleString("nl-NL", { minimumFractionDigits: 3, maximumFractionDigits: 3 });

function greeting(hours) {
  if (hours < 6) return "Goedenacht";
  if (hours < 12) return "Goedemorgen";
  if (hours < 18) return "Goedemiddag";
  return "Goedenavond";
}

/** Rule-based advice -- the first, deliberately simple version of the coach. */
function advise(r) {
  if (r.surplus > 1.5) {
    return {
      tone: "var(--dac-surplus)",
      title: "Gebruik je overschot",
      body: `Je hebt op dit moment ${kw(r.surplus)} kW over. Zet nu de vaatwasser, wasmachine of de laadpaal aan — dan gebruik je stroom die je anders voor een lagere prijs teruglevert.`,
      tag: "Kans",
    };
  }
  if (r.price >= 0.3) {
    return {
      tone: "var(--dac-bad)",
      title: "Stroom is nu duur",
      body: `Je betaalt nu € ${euro(r.price)} per kWh. Stel zware apparaten uit tot na de avondpiek, dan scheelt dat direct op je rekening.`,
      tag: "Let op",
    };
  }
  if (r.price <= 0.1 && r.grid > 0) {
    return {
      tone: "var(--dac-house)",
      title: "Goedkoop moment",
      body: `Met € ${euro(r.price)} per kWh zit je onder je gemiddelde tarief. Een goed moment om te laden of voor te verwarmen.`,
      tag: "Kans",
    };
  }
  if (r.grid > 2.5) {
    return {
      tone: "var(--dac-grid)",
      title: "Veel vraag uit het net",
      body: `Je woning trekt nu ${kw(r.grid)} kW uit het net terwijl de zon weinig levert. Kijk of er iets aan staat dat kan wachten.`,
      tag: "Signaal",
    };
  }
  return {
    tone: "var(--dac-accent-hi)",
    title: "Je woning draait rustig",
    body: "Er is nu niets dat om actie vraagt. De coach kijkt mee en meldt zich zodra er iets te winnen valt.",
    tag: "Rustig",
  };
}

class DacViewOverview extends DacElement {
  static css = /* css */ `
    :host { display: block; }

    .wrap {
      max-width: var(--dac-maxw);
      margin: 0 auto;
      padding: 30px 22px 64px;
      display: flex;
      flex-direction: column;
      gap: 26px;
    }

    /* ---- intro ---- */
    .intro { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; flex-wrap: wrap; }
    .intro h1 {
      margin: 6px 0 0;
      font-family: var(--dac-display);
      font-weight: 300;
      font-size: clamp(30px, 4vw, 46px);
      line-height: 1.05;
      letter-spacing: -0.01em;
    }
    .intro h1 em { font-style: italic; color: var(--dac-accent-hi); }
    .intro .meta { font-size: 13px; color: var(--dac-ink-2); margin-top: 10px; }

    .badges { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 13px;
      border-radius: var(--dac-radius-pill);
      border: 1px solid var(--dac-border);
      background: var(--dac-surface);
      font-size: 12px;
      font-weight: 500;
      color: var(--dac-ink-2);
      white-space: nowrap;
    }
    .live-dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: var(--dac-surplus);
      box-shadow: 0 0 0 0 rgba(5,168,105,0.6);
      animation: pulse 2.2s ease-out infinite;
    }
    @keyframes pulse {
      0%   { box-shadow: 0 0 0 0 rgba(5,168,105,0.55); }
      70%  { box-shadow: 0 0 0 7px rgba(5,168,105,0); }
      100% { box-shadow: 0 0 0 0 rgba(5,168,105,0); }
    }

    /* ---- tiles ---- */
    .tiles {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(212px, 1fr));
      gap: 16px;
    }

    /* ---- lower grid ---- */
    .lower {
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
      gap: 16px;
      align-items: stretch;
    }
    @media (max-width: 980px) { .lower { grid-template-columns: 1fr; } }

    .panel { padding: 22px 24px 24px; display: flex; flex-direction: column; }
    .panel-head { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 6px; }
    .panel-head h2 {
      margin: 4px 0 0;
      font-family: var(--dac-display);
      font-weight: 300;
      font-size: 27px;
      line-height: 1.1;
    }
    /* Block, not flex: an inline SVG in a flex row falls back to its 300px
       intrinsic width instead of filling the card. */
    .flow-holder { margin-top: 14px; flex: 1 1 auto; display: block; }
    .flow-holder dac-energy-flow { display: block; width: 100%; max-width: 540px; margin: 0 auto; }

    .legend { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 8px; }
    .legend span { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: var(--dac-ink-2); }
    .legend i { width: 16px; height: 3px; border-radius: 2px; display: inline-block; }

    /* ---- coach ---- */
    .coach { position: relative; overflow: hidden; }
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
      width: 34px; height: 34px; display: grid; place-items: center;
      border-radius: 11px;
      color: var(--coach-tone, var(--dac-accent-hi));
      background: color-mix(in srgb, var(--coach-tone, var(--dac-accent-hi)) 13%, transparent);
      border: 1px solid color-mix(in srgb, var(--coach-tone, var(--dac-accent-hi)) 30%, transparent);
      transition: color 500ms ease, background 500ms ease, border-color 500ms ease;
    }
    .coach-mark .icon { width: 18px; height: 18px; }
    .coach-tag {
      margin-left: auto;
      padding: 5px 11px;
      border-radius: var(--dac-radius-pill);
      font-size: 11px; font-weight: 600; letter-spacing: 0.09em; text-transform: uppercase;
      color: var(--coach-tone, var(--dac-accent-hi));
      background: color-mix(in srgb, var(--coach-tone, var(--dac-accent-hi)) 12%, transparent);
      transition: color 500ms ease, background 500ms ease;
    }
    .coach h3 {
      margin: 18px 0 0;
      font-family: var(--dac-display);
      font-weight: 400;
      font-size: 28px;
      line-height: 1.12;
    }
    .coach p { margin: 12px 0 0; font-size: 14px; line-height: 1.6; color: var(--dac-ink-2); }
    .day { margin-top: 26px; }
    .day .eyebrow { display: block; margin-bottom: 10px; }
    .day-list {
      display: grid;
      gap: 1px;
      background: var(--dac-border);
      border: 1px solid var(--dac-border);
      border-radius: 14px;
      overflow: hidden;
    }
    .day-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 11px 14px;
      background: rgba(255, 255, 255, 0.022);
      font-size: 13px;
    }
    .day-row .k { color: var(--dac-ink-2); }
    .day-row .v { color: var(--dac-ink); font-weight: 500; font-variant-numeric: tabular-nums; }

    .coach-foot {
      margin-top: auto;
      padding-top: 22px;
      display: flex; align-items: center; gap: 8px;
      font-size: 11.5px; color: var(--dac-ink-3);
    }
    .coach-foot .icon { width: 14px; height: 14px; }

    @media (max-width: 640px) {
      .wrap { padding: 22px 14px 48px; gap: 20px; }
      .panel { padding: 18px 16px 20px; }
    }
  `;

  constructor() {
    super();
    this.source_ = new DemoSource();
  }

  render() {
    const tile = (id) => `<dac-stat-tile id="${id}"></dac-stat-tile>`;

    return `
      <div class="wrap">
        <header class="intro">
          <div>
            <div class="eyebrow">Overzicht</div>
            <h1 id="greeting">Goedemiddag<em>.</em></h1>
            <div class="meta" id="meta"></div>
          </div>
          <div class="badges">
            <span class="badge" id="demo-badge" hidden>Demodata</span>
            <span class="badge" id="clock-badge" hidden></span>
            <span class="badge"><i class="live-dot"></i> Live · ververst elke 2 s</span>
          </div>
        </header>

        <section class="tiles" aria-label="Live meetwaarden">
          ${tile("t-solar")}${tile("t-house")}${tile("t-grid")}${tile("t-surplus")}${tile("t-price")}
        </section>

        <section class="lower">
          <article class="card panel">
            <div class="panel-head">
              <div>
                <div class="eyebrow">Realtime</div>
                <h2>Energiestroom</h2>
              </div>
            </div>
            <div class="flow-holder"><dac-energy-flow id="flow"></dac-energy-flow></div>
            <div class="legend">
              <span><i style="background: var(--dac-solar)"></i> Zon naar woning</span>
              <span><i style="background: var(--dac-grid)"></i> Net naar woning</span>
              <span><i style="background: var(--dac-surplus)"></i> Woning naar net</span>
            </div>
          </article>

          <article class="card panel coach" id="coach">
            <div class="coach-top">
              <div class="coach-mark">${icons.spark}</div>
              <div class="eyebrow">Coach</div>
              <span class="coach-tag" id="coach-tag">Rustig</span>
            </div>
            <h3 id="coach-title">Je woning draait rustig</h3>
            <p id="coach-body"></p>
            <div class="day">
              <span class="eyebrow">Vandaag tot nu toe</span>
              <div class="day-list">
                <div class="day-row"><span class="k">Eigen zon direct gebruikt</span><span class="v" id="d-self">—</span></div>
                <div class="day-row"><span class="k">Teruggeleverd aan het net</span><span class="v" id="d-export">—</span></div>
                <div class="day-row"><span class="k">Ingekocht van het net</span><span class="v" id="d-import">—</span></div>
                <div class="day-row"><span class="k">Kosten inkoop</span><span class="v" id="d-cost">—</span></div>
              </div>
            </div>
            <div class="coach-foot">
              ${icons.gauge} <span>Advies op basis van je live meetwaarden</span>
            </div>
          </article>
        </section>
      </div>
    `;
  }

  afterRender() {
    this.tiles_ = {
      solar: this.$("#t-solar"),
      house: this.$("#t-house"),
      grid: this.$("#t-grid"),
      surplus: this.$("#t-surplus"),
      price: this.$("#t-price"),
    };
    this.flow_ = this.$("#flow");

    const now = new Date();
    this.$("#greeting").innerHTML = `${greeting(now.getHours())}<em>.</em>`;
    this.$("#meta").textContent = now.toLocaleDateString("nl-NL", {
      weekday: "long",
      day: "numeric",
      month: "long",
    });

    // `demo` is set before the element is connected, so re-apply it here.
    this.demo = this.demo_ ?? true;

    this.tick_();
    this.timer_ = setInterval(() => this.tick_(), REFRESH_MS);
  }

  disconnectedCallback() {
    clearInterval(this.timer_);
  }

  /** @param {boolean} value */
  set demo(value) {
    this.demo_ = value;
    if (!this.rendered_) return;
    this.$("#demo-badge").hidden = !value;
    this.$("#clock-badge").hidden = !value;
  }

  tick_() {
    const r = this.source_.sample();
    const exporting = r.grid < 0;

    if (this.demo_) {
      // Demo mode runs an accelerated day, so say which hour is on screen.
      const h = Math.floor(r.hours);
      const m = Math.floor((r.hours - h) * 60);
      this.$("#clock-badge").textContent =
        `Gesimuleerde tijd ${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
    }

    this.tiles_.solar.update({
      tone: "var(--dac-solar)",
      icon: "sun",
      label: "Opwek zon",
      value: kw(r.solar),
      unit: "kW",
      sub: r.solar > 0.05 ? "Zonnepanelen leveren nu" : "Geen opbrengst",
      series: this.source_.series("solar"),
    });

    this.tiles_.house.update({
      tone: "var(--dac-house)",
      icon: "house",
      label: "Verbruik woning",
      value: kw(r.house),
      unit: "kW",
      sub: r.house > 2 ? "Zwaar verbruiker actief" : "Basisverbruik",
      series: this.source_.series("house"),
    });

    this.tiles_.grid.update({
      tone: exporting ? "var(--dac-surplus)" : "var(--dac-grid)",
      icon: "grid",
      label: exporting ? "Naar het net" : "Van het net",
      value: kw(r.grid),
      unit: "kW",
      sub: exporting ? "Je levert terug" : "Je koopt in",
      series: this.source_.series("grid"),
    });

    this.tiles_.surplus.update({
      tone: "var(--dac-surplus)",
      icon: "leaf",
      label: "Zonneoverschot",
      value: kw(r.surplus),
      unit: "kW",
      sub: r.surplus > 0.05 ? "Beschikbaar om te gebruiken" : "Alles wordt zelf verbruikt",
      series: this.source_.series("surplus"),
    });

    const priceTone =
      r.price >= 0.3 ? "var(--dac-bad)" : r.price <= 0.12 ? "var(--dac-good)" : "var(--dac-warn)";
    this.tiles_.price.update({
      tone: priceTone,
      icon: "euro",
      label: "Energieprijs",
      value: `€ ${euro(r.price)}`,
      unit: "/ kWh",
      sub: r.price >= 0.3 ? "Hoog tarief" : r.price <= 0.12 ? "Laag tarief" : "Gemiddeld tarief",
      series: this.source_.series("price"),
    });

    this.flow_.update(r);
    this.updateCoach_(advise(r));
    this.updateDay_(this.source_.day());

    if (this.demo_) this.$("#greeting").innerHTML = `${greeting(r.hours)}<em>.</em>`;
  }

  updateDay_(day) {
    const kwh = (v) =>
      `${v.toLocaleString("nl-NL", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} kWh`;

    this.$("#d-self").textContent = `${Math.round(day.selfUse * 100)} %`;
    this.$("#d-export").textContent = kwh(day.exportKwh);
    this.$("#d-import").textContent = kwh(day.importKwh);
    this.$("#d-cost").textContent = `€ ${day.cost.toLocaleString("nl-NL", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
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
