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
  DISHWASHER_PROGRAM_VALUES,
  canCommand,
  carsFor,
  deviceCommands,
  deviceLabel,
  deviceLabelMap,
  needsRelease,
  programChooser,
  releaseCopy,
  typeMeta,
  valueLabel,
} from "../devices.js";
import { LiveSource, meterReadings, priceForecast, solarForecast } from "../data-source.js";
import {
  OVERVIEW_CARDS,
  defaultLayout,
  effectiveLayout,
  resetLayout,
  saveLayout,
} from "../layout.js";
import { clock, level, levelTone, percent, power, powerText, price as fmtPrice } from "../format.js";
import { sheetCss } from "../theme.js";
import "../components/stat-tile.js";
import "../components/energy-flow.js";
import "../components/price-chart.js";

/** Heartbeat for the sparklines; live values also arrive on their own events. */
const REFRESH_MS = 2000;

/** Surplus worth acting on, in watts -- roughly a dishwasher. */
const SURPLUS_W = 1500;

// Waaronder teruglevering ruis is en geen overschot. Een meter die om nul heen
// wiebelt hoort geen zin op te leveren.
const TRICKLE_W = 100;

// Na hoeveel minuten stilte de kaart zegt dat de coach niet meer denkt. Hij
// hoort elke minuut te beslissen, dus tien minuten is geen drukte maar stilte.
const COACH_SILENT_MINUTES = 10;

/** Hoe lang geleden een beslissing genomen is, in hele minuten. */
function minutenGeleden(stempel) {
  if (!stempel) return null;
  const toen = new Date(stempel).getTime();
  if (Number.isNaN(toen)) return null;
  return Math.max(0, Math.round((Date.now() - toen) / 60000));
}

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
/** Wat er op dit moment met het net gebeurt, in één zin achter een advies. */
function netZin(r) {
  if ((r.exportW ?? 0) > TRICKLE_W) return `Er gaat nog ${powerText(r.exportW)} naar het net.`;
  if ((r.importW ?? 0) > TRICKLE_W) return `Je haalt er ${powerText(r.importW)} bij uit het net.`;
  return "Je gebruikt vrijwel precies wat je zelf opwekt.";
}

function advise(r, thresholds, configured, alertAt, sturing) {
  if (!configured) {
    return {
      tone: "var(--dac-accent-hi)",
      tag: "Instellen",
      title: "Koppel je sensoren",
      body:
        "De coach weet nog niet welke sensoren jouw opwek, verbruik en meterstand meten. Ga naar Instellingen en kies ze onder Energiebronnen. Daarna vult dit scherm zich met je eigen cijfers.",
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

  // Wat de coach zélf doet gaat voor op wat de meter zegt. Wie ziet dat de auto
  // laadt en leest dat de coach "het zo laat", gelooft de kaart niet meer: het
  // getal op de meter is dan wat er ná het laden nog overblijft, en dat leest
  // als een coach die niets doet terwijl hij juist aan het werk is.
  // Ook een paal die stroom aanbiedt terwijl de auto niets afneemt hoort hier:
  // "gebruik je overschot, zet de laadpaal aan" is dan onuitvoerbaar advies,
  // want hij staat al aan.
  // En een coach die iets van de bewoner nodig heeft ook: dat is het enige
  // waar die op dat moment iets aan kan doen.
  if (sturing?.wants || sturing?.needsSoc) {
    const titel = sturing.charging
      ? `${sturing.name} laadt op ${sturing.amps} A`
      : sturing.needsSoc
        ? `${sturing.name} wacht op je accustand`
        : `${sturing.name} wacht op de auto`;
    return {
      tone: sturing.needsSoc ? "var(--dac-warn)" : "var(--dac-accent-hi)",
      tag: sturing.needsSoc ? "Doe iets" : "Aan het werk",
      title: titel,
      body: sturing.charging
        ? `${sturing.reason} ${netZin(r)}`.trim()
        : `${sturing.reason} ${sturing.plan}`.trim(),
    };
  }

  if ((r.exportW ?? 0) > SURPLUS_W) {
    return {
      tone: "var(--dac-grid-out)",
      tag: "Kans",
      title: "Gebruik je overschot",
      body: `Je levert nu ${powerText(r.exportW)} terug aan het net. Zet de vaatwasser, de wasmachine of de laadpaal aan. Dan gebruik je stroom die je anders voor een lagere prijs weggeeft.`,
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

  // Er hangt een auto aan de lader en de coach houdt hem bewust in. Dat is een
  // besluit en geen stilte, dus het hoort hier te staan in plaats van "er is
  // niets dat om actie vraagt".
  if (sturing) {
    return {
      tone: "var(--dac-accent-hi)",
      tag: "Aan het werk",
      title: `${sturing.name} staat klaar`,
      body: `${sturing.reason} ${sturing.plan}`.trim(),
    };
  }

  // Wel overschot, maar te weinig om iets mee te doen. Dat is geen "er gebeurt
  // niets": er gaat stroom naar het net waar je minder voor krijgt dan hij je
  // kost. Zeggen dat er niets aan de hand is terwijl de klant ziet dat hij
  // teruglevert, is precies waarvan iemand denkt dat de coach niet oplet.
  if ((r.exportW ?? 0) > TRICKLE_W) {
    return {
      tone: "var(--dac-accent-hi)",
      tag: "Rustig",
      title: "Je levert een beetje terug",
      body: `Je levert nu ${powerText(r.exportW)} terug. Dat is te weinig om iets zwaars mee te draaien, dus de coach laat het zo.`,
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
    /* De verwachting staat apart van het advies: het advies gaat over nu, dit
       gaat over straks, en door elkaar heen lezen ze als één zin die zichzelf
       tegenspreekt. */
    .coach-sun {
      margin: 12px 0 0;
      padding-top: 12px;
      border-top: 1px solid var(--dac-border);
      font-size: 13.5px;
      line-height: 1.55;
      color: var(--dac-ink-3);
      display: flex;
      align-items: flex-start;
      gap: 9px;
    }
    .coach-sun[hidden] { display: none; }
    .coach-sun .icon { width: 16px; height: 16px; flex: 0 0 auto; color: var(--dac-solar); margin-top: 2px; }

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
      overscroll-behavior-x: contain;
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

    /* Voor de eigen display-regel hieronder uit, anders wint die van het
       hidden-attribuut en blijft een verborgen knop gewoon staan. Dat is wat
       een laadpaal een vrijgaveknop gaf die er niet hoort te zijn. */
    button.release[hidden], button.manual[hidden] { display: none; }

    button.release, button.manual, button.boost {
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
    button.boost[hidden] { display: none; }
    /* Aan is een stand en geen actie, dus die is te zien zonder de tekst te lezen. */
    button.boost[aria-pressed="true"] {
      border-color: var(--dac-accent-hi);
      color: var(--dac-accent-hi);
    }
    button.release:hover, button.manual:hover { color: var(--dac-ink); border-color: rgba(25,143,217,0.55); }
    /* Een icoon zonder maat is geen klein icoon maar een enorm icoon: het svg
       rekt zich uit tot alles wat de knop hem geeft. Vandaar dat alle drie de
       knoppen hier staan en niet alleen degene waar het is opgevallen. */
    button.manual .icon, button.boost .icon { width: 16px; height: 16px; color: var(--dac-accent-hi); }
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

    .cmd-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 8px; margin-top: 16px; }
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

    /* Wat de coach doet of van plan is. Boven de knoppen, want het is het
       antwoord op de vraag waarmee iemand naar deze kaart komt. */
    .coach-says {
      flex: 1 1 100%;
      margin: 14px 0 0;
      padding: 12px 14px;
      border-radius: var(--dac-radius-sm);
      border: 1px solid rgba(25,143,217,0.35);
      background: var(--dac-accent-soft);
      display: grid;
      gap: 6px;
    }
    .coach-says[hidden] { display: none; }
    .says-head { display: flex; align-items: flex-start; gap: 9px; font-size: 13.5px; color: var(--dac-ink); }
    .says-mark { line-height: 0; margin-top: 2px; color: var(--dac-accent-hi); flex: 0 0 auto; }
    .says-mark .icon { width: 16px; height: 16px; }
    .says-plan { margin: 0 0 0 25px; font-size: 12.5px; line-height: 1.5; color: var(--dac-ink-2); }
    .says-plan:empty { display: none; }
    .says-yes {
      justify-self: start;
      margin: 4px 0 0 25px;
      padding: 9px 18px;
      border-radius: var(--dac-radius-pill);
      border: 0;
      background: var(--dac-accent);
      color: #fff;
      font: inherit; font-size: 13.5px; font-weight: 600;
      cursor: pointer;
      -webkit-tap-highlight-color: transparent;
    }
    .says-yes[hidden] { display: none; }

    /* De autokeuze staat boven de knoppen: eerst zeggen wat er hangt, dan pas
       wat ermee moet gebeuren. */
    /* Op een eigen regel boven de knoppen: eerst zeggen welke auto er hangt,
       dan pas wat ermee moet gebeuren. flex-basis 100% haalt hem uit de rij. */
    .car-pick { display: grid; gap: 6px; margin: 14px 0 0; flex: 1 1 100%; }
    .car-pick[hidden] { display: none; }
    .car-pick label { font-size: 12.5px; color: var(--dac-ink-2); }
    .car-pick select {
      padding: 10px 12px;
      border-radius: var(--dac-radius-sm);
      border: 1px solid var(--dac-border-hi);
      background: rgba(255,255,255,0.04);
      color: var(--dac-ink);
      font: inherit; font-size: 14px;
      min-height: 44px;
      width: 100%;
    }
    .car-pick select option { background: #12120f; color: var(--dac-ink); }
    @media (pointer: coarse) { .car-pick select { font-size: 16px; } }
    @supports (-webkit-touch-callout: none) { .car-pick select { font-size: 16px; } }

    .soc-row { display: flex; gap: 8px; align-items: stretch; flex-wrap: wrap; }
    .soc-input {
      flex: 1 1 90px;
      min-width: 0;
      min-height: 44px;
      padding: 10px 12px;
      border-radius: var(--dac-radius-sm);
      border: 1px solid var(--dac-border-hi);
      background: rgba(255,255,255,0.04);
      color: var(--dac-ink);
      font: inherit; font-size: 14px;
    }
    /* Twee klassen diep, anders wint de regel voor knoppen in steer-actions
       met zijn flex 1 1 170px en wordt de knop net zo breed als het veld. */
    .soc-row .soc-save {
      flex: 0 0 auto;
      min-height: 44px;
      padding: 10px 16px;
      border-radius: var(--dac-radius-pill);
      border: 1px solid var(--dac-border-hi);
      background: var(--dac-surface-hi);
      color: var(--dac-ink);
      font: inherit; font-size: 14px; font-weight: 500;
      cursor: pointer;
    }
    .soc-row .soc-save:hover { border-color: var(--dac-accent-hi); }
    .soc-hint { margin: 0; font-size: 12px; color: var(--dac-ink-2); }
    @media (pointer: coarse) { .soc-input { font-size: 16px; } }
    @supports (-webkit-touch-callout: none) { .soc-input { font-size: 16px; } }

    .cmd-pick { display: grid; gap: 6px; margin-top: 16px; min-width: 0; }
    .cmd-pick[hidden] { display: none; }
    .cmd-pick label { font-size: 13px; font-weight: 500; color: var(--dac-ink); }
    .cmd-pick select {
      width: 100%;
      min-width: 0;
      min-height: 46px;
      padding: 11px 12px;
      border-radius: var(--dac-radius-sm);
      border: 1px solid var(--dac-border-hi);
      background: rgba(255,255,255,0.04);
      color: var(--dac-ink);
      font: inherit; font-size: 14px;
      appearance: none;
    }
    .cmd-pick select:disabled { opacity: 0.45; }
    .cmd-pick select option { background: #12120f; color: var(--dac-ink); }
    .cmd-pick .cmd-note { margin: 0; }
    @media (pointer: coarse) { .cmd-pick select { font-size: 16px; } }
    @supports (-webkit-touch-callout: none) { .cmd-pick select { font-size: 16px; } }

    /* The panel draws a blue ring around whatever has the keyboard focus, and
       Safari on iOS counts an ordinary tap as keyboard focus. On the tiles that
       left a heavy blue rectangle behind after every tap. They mark themselves
       in their own colour instead. It has to be switched off here rather than
       inside the tile: a rule from the outer tree beats :host, however specific
       that one is. */
    dac-stat-tile:focus-visible { outline: none; }

    /* The price chart needs the room: 48 bars in a 430px sheet is a comb.
       On a phone it must hand that width back, because a sheet there is not a
       floating card but a page sliding up from the bottom edge. Being more
       specific than the shared rule, this one also won inside its media query,
       and the sheet came out narrow and stuck against the left edge -- which is
       what a customer sees as "the card is not in the middle". */
    dialog.sheet.wide { width: min(760px, calc(100vw - 24px)); }
    @media (max-width: 560px) {
      dialog.sheet.wide { width: 100vw; }
    }

    /* ---- arranging the overview ----
       The whole mode is off to one side of normal use: a quiet link under the
       last card, and while it is on the cards themselves grow a handle. */
    .arrange-link {
      /* Behind every card. The cards are ordered from 1 upwards, and anything
         without an order of its own sits at 0 -- which put this link above the
         coach card instead of under the last one. */
      order: 100;
      align-self: center;
      margin-top: 4px;
      padding: 9px 16px;
      border-radius: var(--dac-radius-pill);
      border: 1px solid var(--dac-border);
      background: transparent;
      color: var(--dac-ink-3);
      font: inherit; font-size: 13px;
      display: inline-flex; align-items: center; gap: 8px;
      cursor: pointer;
      -webkit-tap-highlight-color: transparent;
      transition: color 200ms ease, border-color 200ms ease;
    }
    .arrange-link:hover { color: var(--dac-ink-2); border-color: var(--dac-border-hi); }
    .arrange-link .icon { width: 15px; height: 15px; }
    :host([arranging]) .arrange-link { display: none; }

    /* Cards keep their own look while being arranged; only a bar is added on
       top of them, so you are moving the thing you recognise. */
    :host([arranging]) [data-card] { position: relative; }
    :host([arranging]) [data-card].dragging {
      z-index: 5;
      cursor: grabbing;
      box-shadow: 0 24px 50px -18px rgba(0,0,0,0.9);
    }
    /* A card the customer switched off stays in view while arranging, faded,
       so it can be switched back on. Outside this mode it is simply gone.
       Written as "not while arranging" rather than switching display on and
       off: these cards do not agree on what display they have (the tiles are a
       grid), and handing them all "block" would flatten that one. */
    :host(:not([arranging])) [data-card][data-off] { display: none; }
    :host([arranging]) [data-card][data-off] { opacity: 0.4; }

    .card-edit {
      position: absolute;
      inset: 0 0 auto 0;
      z-index: 2;
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 8px 10px;
      border-radius: var(--dac-radius) var(--dac-radius) 0 0;
      background: linear-gradient(180deg, rgba(12,12,10,0.96), rgba(12,12,10,0.72) 70%, transparent);
      backdrop-filter: blur(2px);
    }
    .card-edit .name {
      font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
      color: var(--dac-ink-2);
      margin-right: auto;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .card-edit button {
      width: 34px; height: 34px; flex: 0 0 auto;
      display: grid; place-items: center;
      border-radius: 10px;
      border: 1px solid var(--dac-border-hi);
      background: rgba(18,18,15,0.9);
      color: var(--dac-ink-2);
      cursor: pointer;
      -webkit-tap-highlight-color: transparent;
    }
    .card-edit button:hover:not(:disabled) { color: var(--dac-ink); border-color: var(--dac-accent-hi); }
    .card-edit button:disabled { opacity: 0.3; cursor: default; }
    .card-edit button.grip { cursor: grab; touch-action: none; }
    .card-edit button.off { border-color: rgba(250,178,25,0.45); color: var(--dac-warn); }
    .card-edit .icon { width: 16px; height: 16px; }

    /* Room for the bar, so it never sits on top of a card's own heading. The
       cards carry different padding, so this is added on the card itself
       rather than as a margin on whatever happens to be first inside it. */
    :host([arranging]) [data-card] { padding-top: 54px; }

    .arrange-bar {
      position: fixed;
      left: 0; right: 0; bottom: 0;
      z-index: 30;
      padding: 12px max(22px, var(--dac-safe-r)) calc(12px + var(--dac-safe-b)) max(22px, var(--dac-safe-l));
      background: linear-gradient(0deg, rgba(12,12,10,0.98) 60%, rgba(12,12,10,0));
      display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    }
    .arrange-bar[hidden] { display: none; }
    /* Room to scroll past the bar, so the last card is not stuck behind it. */
    :host([arranging]) .wrap { padding-bottom: calc(150px + var(--dac-safe-b)); }
    .arrange-bar .where {
      margin-right: auto;
      display: flex; align-items: center; gap: 8px;
      font-size: 12.5px; color: var(--dac-ink-2);
      min-width: 0;
    }
    .arrange-bar button {
      padding: 11px 20px;
      border-radius: var(--dac-radius-pill);
      border: 1px solid var(--dac-border-hi);
      background: var(--dac-surface);
      color: var(--dac-ink-2);
      font: inherit; font-size: 14px; font-weight: 500;
      cursor: pointer;
      min-height: 44px;
    }
    .arrange-bar button.primary {
      border-color: transparent;
      background: var(--dac-accent);
      color: #fff;
      font-weight: 600;
    }
    @media (max-width: 560px) {
      .arrange-bar .where { flex-basis: 100%; margin: 0 0 2px; }
      .arrange-bar button { flex: 1 1 0; padding: 11px 12px; }
    }

    /* ---- meter readings ----
       Five counters at most, so they get a row each rather than a tile: the
       number is long, it is read digit by digit against the meter itself, and
       tabular figures under one another are what makes that possible. */
    .meter-rows {
      margin-top: 16px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 10px;
    }
    .meter-row {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-radius: var(--dac-radius-sm);
      border: 1px solid var(--dac-border);
      background: rgba(255,255,255,0.022);
      min-width: 0;
    }
    .meter-row .k { font-size: 12.5px; color: var(--dac-ink-2); min-width: 0; }
    .meter-row .v {
      font-size: 16px;
      font-weight: 500;
      color: var(--dac-ink);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }
    .meter-row .u { font-size: 11.5px; font-weight: 600; color: var(--dac-ink-3); margin-left: 5px; }

    .legend { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 14px; }
    .legend span { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: var(--dac-ink-2); }
    .legend i { width: 14px; height: 3px; border-radius: 2px; display: inline-block; flex: 0 0 auto; }

    @media (max-width: 640px) {
      .wrap {
        padding: 16px max(12px, var(--dac-safe-r)) calc(48px + var(--dac-safe-b)) max(12px, var(--dac-safe-l));
        gap: 14px;
      }
      .coach { padding: 18px 16px 20px; }
      /* De verwachting staat apart van het advies: het advies gaat over nu, dit
       gaat over straks, en door elkaar heen lezen ze als één zin die zichzelf
       tegenspreekt. */
    .coach-sun {
      margin: 12px 0 0;
      padding-top: 12px;
      border-top: 1px solid var(--dac-border);
      font-size: 13.5px;
      line-height: 1.55;
      color: var(--dac-ink-3);
      display: flex;
      align-items: flex-start;
      gap: 9px;
    }
    .coach-sun[hidden] { display: none; }
    .coach-sun .icon { width: 16px; height: 16px; flex: 0 0 auto; color: var(--dac-solar); margin-top: 2px; }

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
    if (!this.rendered_) return;
    // The arrangement travels with the settings, so a change made on a phone
    // reaches the tablet in the hall without a reload.
    this.applyLayout_();
    this.tick_();
  }

  render() {
    const tile = (id) => `<dac-stat-tile id="${id}"></dac-stat-tile>`;

    return `
      <div class="wrap">
        <article class="card coach" id="coach" data-card="coach">
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
          <p class="coach-sun" id="coach-sun" hidden></p>
        </article>

        <section class="tiles" aria-label="Live meetwaarden" data-card="tiles">
          ${tile("t-solar")}${tile("t-house")}${tile("t-grid")}${tile("t-load")}${tile("t-self")}${tile("t-price")}
        </section>

        <article class="card panel phases" id="phases" data-card="phases" hidden>
          <div class="panel-head">
            <div class="eyebrow">Per fase</div>
            <h2 id="phases-title">Belasting van je aansluiting</h2>
          </div>
          <div class="phase-rows" id="phase-rows"></div>
        </article>

        <article class="card panel meters" id="meters" data-card="meters" hidden>
          <div class="panel-head">
            <div class="eyebrow">Standen</div>
            <h2>Je meter</h2>
          </div>
          <p class="panel-sub">De tellers zoals ze op je meter staan.</p>
          <div class="meter-rows" id="meter-rows"></div>
        </article>

        <article class="card panel steerable" id="steerable" data-card="steerable" hidden>
          <div class="panel-head">
            <div class="eyebrow">Sturing</div>
            <h2>Aanstuurbare apparaten</h2>
          </div>
          <p class="panel-sub">Wat de coach straks zelf mag inschakelen.</p>
          <div class="steer-tabs" id="steer-tabs" role="tablist" aria-label="Aanstuurbare apparaten" hidden></div>
          <div class="steer-grid" id="steer-grid"></div>
        </article>

        <article class="card panel" id="flow-card" data-card="flow">
          <div class="panel-head">
            <div class="eyebrow">Realtime</div>
            <h2>Energiestroom</h2>
          </div>
          <div class="flow-holder"><dac-energy-flow id="flow"></dac-energy-flow></div>
          <div class="legend" id="legend"></div>
        </article>

        <button class="arrange-link" type="button" id="arrange-open">
          ${icons.sliders} Indeling aanpassen
        </button>

        <div class="arrange-bar" id="arrange-bar" hidden>
          <span class="where">Deze indeling geldt op dit scherm.</span>
          <button type="button" id="arrange-reset">Standaard terugzetten</button>
          <button type="button" class="primary" id="arrange-done">Klaar</button>
        </div>

        <dialog class="sheet" id="manual" tabindex="-1" aria-labelledby="manual-title">
          <div class="sheet-head">
            <div>
              <div class="eyebrow">Handmatige besturing</div>
              <h3 id="manual-title"></h3>
            </div>
            <button class="sheet-close" type="button" id="manual-close" aria-label="Sluiten">${icons.close}</button>
          </div>
          <p class="sheet-sub" id="manual-sub"></p>
          <div class="cmd-pick" id="manual-pick" hidden>
            <label for="manual-program">Programma</label>
            <select id="manual-program"></select>
            <p class="cmd-note" id="manual-program-note"></p>
          </div>
          <div class="cmd-grid" id="manual-grid"></div>
          <p class="sheet-status" id="manual-status" role="status" aria-live="polite"></p>
        </dialog>

        <dialog class="sheet wide" id="prices" tabindex="-1" aria-labelledby="prices-title">
          <div class="sheet-head">
            <div>
              <div class="eyebrow">Dynamisch tarief</div>
              <h3 id="prices-title">Wat stroom kost</h3>
            </div>
            <button class="sheet-close" type="button" id="prices-close" aria-label="Sluiten">${icons.close}</button>
          </div>
          <dac-price-chart id="price-chart"></dac-price-chart>
          <p class="sheet-sub" id="prices-note"></p>
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
    this.$("#manual-program").addEventListener("change", (event) =>
      this.chooseProgram_(event.target.value)
    );
    this.closeOnBackdrop_(sheet);

    const prices = this.$("#prices");
    this.$("#prices-close").addEventListener("click", () => prices.close());
    this.closeOnBackdrop_(prices);

    this.$("#arrange-open").addEventListener("click", () => this.startArranging_());
    this.$("#arrange-done").addEventListener("click", () => this.stopArranging_());
    this.$("#arrange-reset").addEventListener("click", () => this.resetArrangement_());

    this.applyLayout_();
  }

  // --- arranging the overview -------------------------------------------

  /** Put the cards in the order this person chose, and hide what they hid. */
  applyLayout_() {
    // Not while somebody is rearranging: adopting a stored arrangement mid-drag
    // would pull the cards out from under the finger holding them.
    if (this.arranging_) return;

    this.layout_ = effectiveLayout();
    this.paintLayout_();
  }

  paintLayout_() {
    this.layout_.forEach((card, index) => {
      const el = this.$(`[data-card="${card.id}"]`);
      if (!el) return;
      // Order rather than moving nodes: the cards are live and hold their own
      // state, and reordering the DOM under them means rebuilding a diagram
      // and a set of tabs every time somebody drags something.
      el.style.order = String(index + 1);
      el.toggleAttribute("data-off", card.hidden);
    });

    if (this.arranging_) this.paintCardBars_();
  }

  startArranging_() {
    this.arranging_ = true;
    this.toggleAttribute("arranging", true);
    this.$("#arrange-bar").hidden = false;
    this.paintCardBars_();
  }

  stopArranging_() {
    this.arranging_ = false;
    this.toggleAttribute("arranging", false);
    this.$("#arrange-bar").hidden = true;
    for (const bar of this.$$(".card-edit")) bar.remove();
  }

  /**
   * The handle on each card.
   *
   * Dragging is offered but never the only way: it is the one interaction that
   * fails silently for anyone using a keyboard, and on a phone it competes with
   * the scroll. The arrows do the same job and always work.
   */
  paintCardBars_() {
    const order = this.layout_;

    order.forEach((card, index) => {
      const el = this.$(`[data-card="${card.id}"]`);
      if (!el) return;

      const meta = OVERVIEW_CARDS.find((item) => item.id === card.id);
      let bar = el.querySelector(":scope > .card-edit");
      if (!bar) {
        bar = document.createElement("div");
        bar.className = "card-edit";
        bar.innerHTML = `
          <button type="button" class="grip" aria-label="Verslepen" title="Verslepen">${icons.menu}</button>
          <span class="name"></span>
          <button type="button" data-move="-1" aria-label="Omhoog">${icons.arrowLeft}</button>
          <button type="button" data-move="1" aria-label="Omlaag">${icons.arrowRight}</button>
          <button type="button" data-toggle-card aria-label="Tonen of verbergen">${icons.check}</button>
        `;
        // The arrows are the horizontal icons turned a quarter, which keeps one
        // pair of icons rather than two that have to stay in step.
        bar.querySelector('[data-move="-1"]').style.transform = "rotate(90deg)";
        bar.querySelector('[data-move="1"]').style.transform = "rotate(90deg)";
        el.prepend(bar);

        bar.querySelector(".grip").addEventListener("pointerdown", (ev) =>
          this.startDrag_(ev, card.id)
        );
        for (const button of bar.querySelectorAll("[data-move]")) {
          button.addEventListener("click", () =>
            this.moveCard_(card.id, Number(button.dataset.move))
          );
        }
        bar.querySelector("[data-toggle-card]").addEventListener("click", () =>
          this.toggleCard_(card.id)
        );
      }

      bar.querySelector(".name").textContent = meta?.label ?? card.id;
      bar.querySelector('[data-move="-1"]').disabled = index === 0;
      bar.querySelector('[data-move="1"]').disabled = index === order.length - 1;

      const eye = bar.querySelector("[data-toggle-card]");
      eye.classList.toggle("off", card.hidden);
      eye.innerHTML = card.hidden ? icons.close : icons.check;
      eye.title = card.hidden ? "Verborgen, tik om te tonen" : "Zichtbaar, tik om te verbergen";
    });
  }

  moveCard_(id, delta) {
    const from = this.layout_.findIndex((card) => card.id === id);
    const to = from + delta;
    if (from < 0 || to < 0 || to >= this.layout_.length) return;

    const [moved] = this.layout_.splice(from, 1);
    this.layout_.splice(to, 0, moved);
    this.paintLayout_();
    this.storeArrangement_();
  }

  toggleCard_(id) {
    const card = this.layout_.find((item) => item.id === id);
    if (!card) return;
    card.hidden = !card.hidden;
    this.paintLayout_();
    this.storeArrangement_();
  }

  /**
   * Drag a card to a new place.
   *
   * Pointer events rather than HTML5 drag and drop, which does not exist on a
   * touch screen at all. The card follows the finger; the others stay put until
   * it passes the middle of one, and then the two swap.
   */
  startDrag_(event, id) {
    event.preventDefault();
    const el = this.$(`[data-card="${id}"]`);
    if (!el) return;

    const grip = event.currentTarget;
    grip.setPointerCapture(event.pointerId);

    const startY = event.clientY;
    el.classList.add("dragging");

    // Every swap moves the card's own resting place, so the offset it is drawn
    // with has to be corrected by exactly the distance it just jumped. Kept
    // across moves: recomputing it from the pointer alone would snap the card
    // back to where it started the moment the finger moved again.
    let settled = 0;

    const move = (ev) => {
      const dy = ev.clientY - startY;
      el.style.transform = `translateY(${dy + settled}px)`;

      // Keep swapping while the card is past the next neighbour, rather than
      // one place per event: a quick flick delivers few move events, and one
      // step each would leave the card lagging behind the finger.
      for (;;) {
        const index = this.layout_.findIndex((card) => card.id === id);
        const step = dy + settled < 0 ? -1 : 1;
        const other = this.layout_[index + step];
        if (!other) break;

        const box = this.$(`[data-card="${other.id}"]`)?.getBoundingClientRect();
        if (!box) break;

        const self = el.getBoundingClientRect();
        const passed =
          step < 0
            ? self.top < box.top + box.height / 2
            : self.bottom > box.bottom - box.height / 2;
        if (!passed) break;

        const before = el.getBoundingClientRect().top;
        const [moved] = this.layout_.splice(index, 1);
        this.layout_.splice(index + step, 0, moved);
        this.paintLayout_();
        settled += before - el.getBoundingClientRect().top;
        el.style.transform = `translateY(${dy + settled}px)`;
      }
    };

    const stop = () => {
      grip.removeEventListener("pointermove", move);
      grip.removeEventListener("pointerup", stop);
      grip.removeEventListener("pointercancel", stop);
      el.classList.remove("dragging");
      el.style.transform = "";
      this.paintLayout_();
      this.storeArrangement_();
    };

    grip.addEventListener("pointermove", move);
    grip.addEventListener("pointerup", stop);
    grip.addEventListener("pointercancel", stop);
  }

  storeArrangement_() {
    saveLayout(this.layout_);
  }

  resetArrangement_() {
    resetLayout();
    this.layout_ = defaultLayout();
    this.paintLayout_();
  }

  /**
   * Tapping the darkened area closes a sheet.
   *
   * The hit test is on coordinates rather than on the target alone, because a
   * click on the dialog's own padding also reports the dialog as its target.
   */
  closeOnBackdrop_(sheet) {
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
    this.followCoach_();
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
    this.$("#prices")?.close();
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

    // What the supplier has published ahead. Only worth opening when there is
    // more than one price in it: on a fixed contract the chart would be one
    // flat line saying what the tile already says.
    this.forecast_ = priceForecast(this.feed_, this.settings_?.contract);
    this.priceBounds_ = thresholds.price;
    this.tiles_.price.action = this.forecast_.length > 1 ? () => this.openPrices_() : null;
    if (this.$("#prices").open) this.drawPrices_();

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

    this.updateSun_();
    this.updateMeters_();
    this.updatePhases_(r, alertAt);
    this.updateSteerable_(r.devices);
    this.flow_.update(r);
    this.updateLegend_();
    this.updateCoach_(advise(r, thresholds, configured, alertAt, this.steeringNow_()));
  }

  /**
   * What the sun is expected to bring, under the advice.
   *
   * Its own line rather than part of the advice, because it answers a different
   * question: the advice is about now, this is about later, and read as one
   * paragraph they contradict each other on any afternoon with a cloud in it.
   */
  updateSun_() {
    const line = this.$("#coach-sun");
    const sun = solarForecast(this.feed_, this.settings_?.sources);
    if (!sun.has) {
      line.hidden = true;
      return;
    }

    const parts = [];
    if (sun.remainingToday !== null) {
      // Drie gevallen en niet twee. "Vrijwel niets meer" stond er ook nog om
      // elf uur 's avonds, en dan is het niet vrijwel niets maar helemaal
      // niets: de zon is onder. Een zin die op dat moment doet alsof er nog
      // iets aankomt, klopt gewoon niet.
      if (sun.remainingToday < 0.05) {
        parts.push("Vandaag levert de zon niets meer op");
      } else if (sun.remainingToday < 0.2) {
        parts.push("Vandaag komt er nog maar weinig bij");
      } else {
        parts.push(`Vandaag komt er nog ongeveer ${nl(sun.remainingToday, 1)} kWh bij`);
      }
    }
    // Only worth naming while it is still ahead: at eight in the evening
    // "the peak is at 13:00" is a fact about this afternoon.
    if (sun.peakToday && sun.peakToday > new Date()) {
      parts.push(`met de meeste zon rond ${clock(sun.peakToday)}`);
    }
    if (sun.tomorrow !== null) {
      parts.push(`morgen ongeveer ${nl(sun.tomorrow, 1)} kWh`);
    }

    const mark = document.createElement("span");
    mark.innerHTML = icons.sun;
    const text = document.createElement("span");
    text.textContent = `${parts.join(", ")}.`;

    line.hidden = false;
    line.replaceChildren(mark, text);
  }


  /**
   * Volgen wat de coach besluit.
   *
   * Twee wegen naar hetzelfde: eenmalig ophalen wat er al besloten is, en
   * daarna meeluisteren op de gebeurtenis die na elke ronde afgaat. Zonder dat
   * eerste zou een net geopend dashboard tot een minuut lang niets te zeggen
   * hebben, en zonder dat tweede zou het daarna nooit meer bijwerken.
   */
  async followCoach_() {
    if (!this.hass || this.coachWired_) return;
    this.coachWired_ = true;

    try {
      this.coach_ = await this.hass.callWS({ type: "domotiapp_coach/coach/state" });
      if (this.rendered_) this.updateSteerable_(this.lastDevices_ ?? []);
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de stand van de coach niet ophalen", error);
    }

    try {
      this.coachOff_ = await this.hass.connection.subscribeEvents((event) => {
        const data = event?.data;
        if (!data?.device) return;
        this.coach_ = { ...(this.coach_ ?? {}), [data.device]: data };
        if (this.rendered_) this.updateSteerable_(this.lastDevices_ ?? []);
      }, "domotiapp_coach_decision");
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de coach niet volgen", error);
    }
  }

  /** Ja zeggen tegen wat de coach voorstelt, voor deze laadbeurt. */
  async approve_(slot) {
    const device = this.steerDevices_?.[slot];
    if (!device || !this.hass) return;

    try {
      this.coach_ = await this.hass.callWS({
        type: "domotiapp_coach/coach/approve",
        device_id: device.id,
        approve: true,
      });
      this.updateSteerable_(this.lastDevices_ ?? []);
    } catch (error) {
      console.warn("[DomotiApp Coach] kon het akkoord niet doorgeven", error);
    }
  }

  /**
   * Snelladen aan of uit.
   *
   * Voor wie eerder weg moet dan gepland. Dat is makkelijker dan het schema
   * omgooien en daarna niet vergeten het terug te zetten: dit gaat vanzelf uit
   * zodra de kabel eruit gaat.
   */
  async toggleBoost_(slot) {
    const device = this.steerDevices_?.[slot];
    if (!device || !this.hass) return;

    const aan = !this.coach_?.[device.id]?.boost;
    try {
      await this.hass.callWS({
        type: "domotiapp_coach/coach/boost",
        device_id: device.id,
        boost: aan,
      });
      this.coach_ = await this.hass.callWS({ type: "domotiapp_coach/coach/state" });
      this.updateSteerable_(this.lastDevices_ ?? []);
    } catch (error) {
      console.warn("[DomotiApp Coach] kon snelladen niet omzetten", error);
    }
  }

  /**
   * Het laden stilzetten of hervatten.
   *
   * Dit gaat via de coach en niet rechtstreeks naar de paal, en dat is het hele
   * punt: zet je het laden zelf stil, dan hoort de coach het een minuut later
   * niet weer aan te zetten. Hij schrijft er een nul voor in de laderlimiet en
   * laat die staan, dus de goedkeuring van de sessie blijft intact en hervatten
   * is niet meer dan een gewoon getal terugschrijven.
   */
  async togglePause_(slot) {
    const device = this.steerDevices_?.[slot];
    if (!device || !this.hass) return;

    const aan = !this.coach_?.[device.id]?.paused;
    try {
      await this.hass.callWS({
        type: "domotiapp_coach/coach/pause",
        device_id: device.id,
        paused: aan,
      });
      this.coach_ = await this.hass.callWS({ type: "domotiapp_coach/coach/state" });
      this.updateSteerable_(this.lastDevices_ ?? []);
    } catch (error) {
      console.warn("[DomotiApp Coach] kon het pauzeren niet omzetten", error);
    }
  }

  /**
   * Wat de coach van dit apparaat zegt, op zijn kaart.
   *
   * Alleen waar hij ook echt iets te zeggen heeft. Bij "alleen uitlezen" staat
   * er niets, want dan is er niets besloten; bij "voorstellen" staat er een
   * knop, want dan wacht hij op je.
   */
  paintCoach_(slot, device) {
    const blok = this.$(`[data-coach="${slot}"]`);
    const besluit = this.coach_?.[device.id];

    if (!besluit || besluit.level === "read") {
      blok.hidden = true;
      return;
    }

    blok.hidden = false;
    this.$(`[data-coach-mark="${slot}"]`).innerHTML = besluit.charge
      ? icons.spark
      : icons.compass;
    // Een coach die stilvalt levert niets op wat opvalt: wat er op de laadpaal
    // staat blijft staan, en dat ziet er precies zo uit als een coach die zijn
    // werk doet. Dus zegt de kaart het, en blijft zijn laatste besluit erbij
    // staan zodat je ziet waar hij was toen het stilviel.
    const stil = minutenGeleden(besluit.at);
    this.$(`[data-coach-reason="${slot}"]`).textContent =
      stil !== null && stil >= COACH_SILENT_MINUTES
        ? `De coach heeft ${stil} minuten niets beslist. Dit vond hij het laatst: ${besluit.reason ?? ""}`
        : (besluit.reason ?? "");
    this.$(`[data-coach-plan="${slot}"]`).textContent = besluit.plan ?? "";

    // Wat de knop doet is niet "begin met laden" maar "de coach mag dit
    // apparaat sturen". Zolang er niets gebeurt komt dat op hetzelfde neer.
    // Laadt de auto al, dan valt er niets te beginnen en leest "Ja, doe maar"
    // als een vraag over iets dat allang aan de gang is.
    const knop = this.$(`[data-coach-yes="${slot}"]`);
    const vraagt = besluit.level === "propose" && !besluit.approved && besluit.charge;
    knop.hidden = !vraagt;
    knop.textContent = vraagt
      ? (besluit.charging ? "Ja, neem het over" : "Ja, doe maar")
      : "";

    // Snelladen alleen aanbieden waar de coach ook echt kan sturen en er een
    // auto aan hangt. Een knop die niets kan doen is erger dan geen knop.
    const boost = this.$(`[data-boost="${slot}"]`);
    const kan = besluit.rule !== "disconnected" && besluit.level !== "advise";
    boost.hidden = !kan;
    boost.setAttribute("aria-pressed", String(Boolean(besluit.boost)));
    this.$(`[data-boost-text="${slot}"]`).textContent = besluit.boost
      ? "Snelladen staat aan"
      : "Snelladen";

    const pauze = this.$(`[data-pause="${slot}"]`);
    pauze.hidden = !kan;
    pauze.setAttribute("aria-pressed", String(Boolean(besluit.paused)));
    this.$(`[data-pause-text="${slot}"]`).textContent = besluit.paused
      ? "Gepauzeerd"
      : "Pauzeren";
  }

  /** Which car this charging point is set to, if any. */
  activeCar_(deviceId) {
    return (this.settings_?.active_cars ?? []).find((entry) => entry.device === deviceId)?.car;
  }

  /**
   * Wat de coach op dit moment zelf stuurt, of null als hij niets onderhanden
   * heeft.
   *
   * Alleen besluiten die ook werkelijk uitgevoerd worden tellen mee. Op het
   * niveau "adviseren" zonder akkoord doet de coach niets, en dan zou het
   * bovenaan zetten dat hij aan het werk is precies de loze belofte zijn die
   * hier nergens hoort te staan.
   */
  steeringNow_() {
    for (const device of this.lastDevices_ ?? []) {
      const besluit = this.coach_?.[device.id];
      if (!besluit || !besluit.applied) continue;
      if (besluit.rule === "disconnected" || besluit.rule === "complete") continue;
      if (besluit.paused) continue;
      return {
        name: this.labelFor_(device),
        amps: besluit.amps,
        // Of hij stroom vráágt, en of die ook werkelijk loopt. Dat verschil is
        // precies wat er op de kaart hoort te staan.
        wants: Boolean(besluit.charge),
        needsSoc: Boolean(besluit.needs_soc),
        charging: Boolean(besluit.charge && besluit.charging),
        reason: besluit.reason ?? "",
        plan: besluit.plan ?? "",
      };
    }
    return null;
  }

  /** Remember which car is plugged in, for everybody looking at this house. */
  async chooseCar_(slot, carId) {
    const device = this.steerDevices_?.[slot];
    if (!device || !this.hass) return;

    try {
      const settings = await this.hass.callWS({
        type: "domotiapp_coach/device/car",
        device_id: device.id,
        car: carId,
      });
      this.fire("dac-settings-saved", { settings });
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de auto niet onthouden", error);
    }
  }

  /**
   * Doorgeven hoe vol de auto is die eraan hangt.
   *
   * Alleen nodig bij auto's die het zelf niet aan Home Assistant vertellen. Het
   * staat hier op de kaart en niet bij de instellingen, want het verandert elke
   * dag en degene die het weet staat naast de auto.
   */
  async saveSoc_(slot) {
    const device = this.steerDevices_?.[slot];
    if (!device || !this.hass) return;

    const field = this.$(`[data-soc-input="${slot}"]`);
    const cars = carsFor(device);
    const car = this.activeCar_(device.id) ?? cars[0]?.id ?? "";
    const raw = String(field.value ?? "").trim();
    const percent = raw === "" ? null : Math.min(100, Math.max(0, Number(raw)));
    if (percent !== null && !Number.isFinite(percent)) return;

    try {
      const settings = await this.hass.callWS({
        type: "domotiapp_coach/device/soc",
        device_id: device.id,
        car,
        percent,
      });
      field.dataset.stand = String(percent ?? "");
      this.fire("dac-settings-saved", { settings });
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de accustand niet doorgeven", error);
    }
  }

  /**
   * The meter counters, when there are any to show.
   *
   * The whole card disappears when nothing is mapped: a house with no meter
   * sensors gets no empty frame, and one without gas gets four rows rather than
   * five with a hole where gas would be.
   */
  updateMeters_() {
    const rows = meterReadings(this.feed_, this.settings_?.sources);
    this.$("#meters").hidden = !rows.length;
    if (!rows.length) return;

    // The frame is rebuilt only when the set of counters changes; the numbers
    // themselves are written into the cells that are already there, several
    // times a second.
    const key = rows.map((row) => row.key).join("|");
    if (key !== this.meterKey_) {
      this.meterKey_ = key;
      this.$("#meter-rows").replaceChildren(
        ...rows.map((row) => {
          const item = document.createElement("div");
          item.className = "meter-row";

          const label = document.createElement("span");
          label.className = "k";
          label.textContent = row.label;

          const value = document.createElement("span");
          value.className = "v";
          value.dataset.meter = row.key;

          item.append(label, value);
          return item;
        })
      );
    }

    for (const row of rows) {
      const cell = this.$(`[data-meter="${row.key}"]`);
      cell.textContent = row.value;

      const unit = document.createElement("span");
      unit.className = "u";
      unit.textContent = row.unit;
      cell.append(unit);
    }
  }

  /**
   * Open the price forecast behind the Energieprijs tile.
   *
   * Shown before it is drawn, deliberately: the chart measures itself, and a
   * dialog that is still closed measures zero.
   */
  openPrices_() {
    const sheet = this.$("#prices");
    sheet.showModal();
    // Away from the close button, which is what a dialog focuses by default
    // and what iOS then rings in blue.
    sheet.focus();
    this.drawPrices_();
  }

  drawPrices_() {
    const forecast = this.forecast_ ?? [];
    this.$("#price-chart").update({ forecast, thresholds: this.priceBounds_ });

    const last = forecast[forecast.length - 1]?.end;
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(23, 0, 0, 0);

    // Suppliers publish the next day somewhere in the afternoon, so a list that
    // stops tonight is normal rather than broken -- and saying so beats leaving
    // somebody wondering why tomorrow is missing.
    this.$("#prices-note").textContent = !last
      ? ""
      : last >= tomorrow
        ? "De prijzen van je leverancier voor vandaag en morgen."
        : "Alleen vandaag is bekend. De prijzen voor morgen komen meestal in de loop van de middag binnen.";
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
    // Numbered over every device, not just the steerable ones, so two
    // dishwashers keep the same numbers here as under Strategie.
    this.labels_ = deviceLabelMap(devices);
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

  /** This device's name, with two of a kind told apart. */
  labelFor_(device) {
    return this.labels_?.get(device.id) ?? deviceLabel(device);
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
            <div class="coach-says" data-coach="${slot}" hidden>
              <div class="says-head">
                <span class="says-mark" data-coach-mark="${slot}"></span>
                <span data-coach-reason="${slot}"></span>
              </div>
              <p class="says-plan" data-coach-plan="${slot}"></p>
              <button type="button" class="says-yes" data-coach-yes="${slot}" hidden></button>
            </div>
            <div class="car-pick" data-car-pick="${slot}" hidden>
              <label for="car-${slot}">Welke auto hangt eraan?</label>
              <select id="car-${slot}" data-car-select="${slot}"></select>
            </div>
            <div class="car-pick soc-pick" data-soc-pick="${slot}" hidden>
              <label for="soc-${slot}">Hoe vol is de auto nu?</label>
              <div class="soc-row">
                <input id="soc-${slot}" class="soc-input tnum" type="number" min="0" max="100"
                       step="1" inputmode="numeric" enterkeyhint="done"
                       data-soc-input="${slot}" placeholder="%">
                <button type="button" class="soc-save" data-soc-save="${slot}">Doorgeven</button>
              </div>
              <p class="soc-hint" data-soc-hint="${slot}"></p>
            </div>
            <button class="release" type="button" data-release="${slot}" aria-pressed="false">
              <span class="mark" data-mark="${slot}"></span>
              <span data-release-text="${slot}"></span>
            </button>
            <button class="boost" type="button" data-boost="${slot}" aria-pressed="false" hidden>
              ${icons.bolt}<span data-boost-text="${slot}">Snelladen</span>
            </button>
            <button class="boost" type="button" data-pause="${slot}" aria-pressed="false" hidden>
              ${icons.pause}<span data-pause-text="${slot}">Pauzeren</span>
            </button>
            <button class="manual" type="button" data-manual="${slot}" hidden>
              ${icons.sliders}<span>Handmatige besturing</span>
            </button>
          </div>
          <p class="steer-hint" data-hint="${slot}"></p>
        </article>`
      )
      .join("");

    for (const button of this.$$("[data-coach-yes]")) {
      button.addEventListener("click", () => this.approve_(Number(button.dataset.coachYes)));
    }
    for (const button of this.$$("[data-pause]")) {
      button.addEventListener("click", () => this.togglePause_(Number(button.dataset.pause)));
    }
    for (const button of this.$$("[data-boost]")) {
      button.addEventListener("click", () => this.toggleBoost_(Number(button.dataset.boost)));
    }
    for (const select of this.$$("[data-car-select]")) {
      select.addEventListener("change", () =>
        this.chooseCar_(Number(select.dataset.carSelect), select.value)
      );
    }
    for (const button of this.$$("[data-soc-save]")) {
      button.addEventListener("click", () => this.saveSoc_(Number(button.dataset.socSave)));
    }
    for (const field of this.$$("[data-soc-input]")) {
      field.addEventListener("keydown", (event) => {
        if (event.key === "Enter") this.saveSoc_(Number(field.dataset.socInput));
      });
    }
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
    this.lastDevices_ = list;
    const ready = new Set(this.settings_?.ready_devices ?? []);

    list.forEach((device, slot) => {
      const copy = releaseCopy(device);
      const on = ready.has(device.id);

      // Names and readings are the customer's own, so they go in as text.
      this.$(`[data-name="${slot}"]`).textContent = this.labelFor_(device);
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

      this.paintCoach_(slot, device);

      // Welke auto er hangt. De coach rekent met de accu en het aantal fasen
      // van die auto, en een gast staat er altijd bij zonder instellen.
      const cars = carsFor(device);
      const pick = this.$(`[data-car-pick="${slot}"]`);
      pick.hidden = cars.length < 2;
      if (!pick.hidden) {
        const select = this.$(`[data-car-select="${slot}"]`);
        const chosen = this.activeCar_(device.id);
        const key = cars.map((car) => `${car.id}:${car.name}`).join("|");
        if (select.dataset.key !== key) {
          select.dataset.key = key;
          select.replaceChildren(
            ...cars.map((car) => {
              const option = document.createElement("option");
              option.value = car.id;
              option.textContent = car.name?.trim() || (car.guest ? "Gast" : "Naamloze auto");
              return option;
            })
          );
        }
        select.value = chosen ?? cars[0]?.id ?? "";
      }

      // Hoe vol die auto is. Alleen vragen waar de auto het zelf niet vertelt,
      // waar de capaciteit bekend is (anders zegt een percentage niets) en
      // terwijl er werkelijk een kabel in zit.
      const socPick = this.$(`[data-soc-pick="${slot}"]`);
      const gekozen = cars.find((car) => car.id === (this.activeCar_(device.id) ?? cars[0]?.id));
      const oordeel = this.coach_?.[device.id];
      const hangt = Boolean(oordeel) && oordeel.rule !== "disconnected";
      socPick.hidden = !(
        hangt &&
        gekozen &&
        !gekozen.guest &&
        !gekozen.soc_entity &&
        Number(gekozen.capacity_kwh) > 0
      );
      if (!socPick.hidden) {
        const opgave = (this.settings_?.car_soc ?? []).find((row) => row?.device === device.id);
        const field = this.$(`[data-soc-input="${slot}"]`);
        const stand = opgave?.percent ?? "";
        // Niet overschrijven terwijl iemand aan het typen is.
        if (this.shadowRoot?.activeElement !== field && field.dataset.stand !== String(stand)) {
          field.dataset.stand = String(stand);
          field.value = stand;
        }
        this.$(`[data-soc-hint="${slot}"]`).textContent = opgave
          ? "De coach telt zelf verder met wat de paal erin doet."
          : oordeel?.needs_soc
            ? "Hier wacht de coach op. Zonder dit gaat hij uit van een lege accu."
            : "Geef dit door, dan kan de coach het gunstigste moment kiezen.";
      }

      // Only where somebody has to say so. A charger is released by plugging
      // the cable in, and asking again on the dashboard added a step without
      // adding a decision.
      const asks = needsRelease(device);
      const button = this.$(`[data-release="${slot}"]`);
      button.hidden = !asks;
      button.setAttribute("aria-pressed", String(on));
      this.$(`[data-mark="${slot}"]`).innerHTML = on ? icons.check : "";
      this.$(`[data-release-text="${slot}"]`).textContent = on ? "Vrijgegeven" : copy.label;
      this.$(`[data-hint="${slot}"]`).textContent = asks ? (on ? "" : copy.hint) : "";

      // Only where there is something to send to: a brand that takes commands,
      // and the Home Assistant device to send them to.
      this.$(`[data-manual="${slot}"]`).hidden = !canCommand(device);

      const name = this.$(`[data-tab-name="${slot}"]`);
      if (name) {
        name.textContent = this.labelFor_(device);
        // The dot says "released", so it only means anything on the devices
        // that are waiting for that.
        this.$(`[data-tab-dot="${slot}"]`).classList.toggle("on", asks && on);
        this.$(`[data-tab-state="${slot}"]`).textContent = asks && on ? " (vrijgegeven)" : "";
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
    // Met een lezer erbij, want hervatten schrijft de maximale limiet van de
    // lader zelf terug en dat getal staat in een sensor.
    this.manualActions_ = deviceCommands(device, (entityId) => {
      const value = Number(this.feed_?.get(entityId)?.state);
      return Number.isFinite(value) && value > 0 ? value : undefined;
    });

    this.$("#manual-title").textContent = this.labelFor_(device);
    this.$("#manual-sub").textContent =
      "Deze opdrachten gaan rechtstreeks naar het apparaat, langs de coach om. "
      + "Pauzeren blijft staan tot je hervat, maar stuurt de coach wel, dus die "
      + "kan het binnen een minuut weer overnemen.";
    this.setManualStatus_("", "");
    this.paintProgramPicker_(device);

    // Labels and hints are the panel's own text, not the customer's, so they go
    // in as markup along with their icons.
    this.$("#manual-grid").innerHTML = this.manualActions_
      .map(
        (action, index) => `
        <button class="cmd${action.care ? " care" : ""}" type="button" data-cmd="${index}">
          ${icons[action.icon] ?? ""}<span>${action.label}</span>
        </button>
        ${action.note ? `<p class="cmd-note">${action.note}</p>` : ""}`
      )
      .join("");

    for (const button of this.$$("#manual-grid .cmd")) {
      button.addEventListener("click", () =>
        this.sendCommand_(this.manualActions_[Number(button.dataset.cmd)])
      );
    }

    const sheet = this.$("#manual");
    sheet.showModal();
    sheet.focus();
  }

  /**
   * The program dropdown, when the appliance has one that can be written to.
   *
   * The options are the machine's own -- read off the entity rather than out of
   * the panel's table, because what a particular dishwasher offers is a fact
   * about that dishwasher. The table only supplies the names, and anything not
   * in it keeps the wording the appliance used.
   */
  paintProgramPicker_(device) {
    const holder = this.$("#manual-pick");
    const select = this.$("#manual-program");
    const chooser = programChooser(device);

    holder.hidden = !chooser;
    if (!chooser) return;

    const state = this.feed_?.get(chooser.entityId);
    const options = state?.attributes?.options ?? [];
    this.programEntity_ = chooser.entityId;

    select.replaceChildren(
      ...options.map((value) => {
        const option = document.createElement("option");
        option.value = value;
        // Names come from the appliance, so they go in as text.
        option.textContent = valueLabel(DISHWASHER_PROGRAM_VALUES, value) ?? value;
        option.selected = value === state?.state;
        return option;
      })
    );

    select.disabled = !options.length;
    this.$("#manual-program-note").textContent = options.length
      ? "Kiezen zet het programma klaar; starten doe je met de knop eronder."
      : "Deze entiteit geeft geen keuzes terug, dus er valt hier niets te kiezen.";
  }

  /** Put the chosen program on the machine. */
  async chooseProgram_(value) {
    if (!this.programEntity_ || !this.hass || this.sending_) return;

    this.sending_ = true;
    this.setManualButtons_(true);
    this.setManualStatus_("Programma instellen…", "");

    const [domain] = this.programEntity_.split(".");
    try {
      await this.hass.callService(domain, "select_option", {
        entity_id: this.programEntity_,
        option: value,
      });
      this.setManualStatus_("Programma ingesteld.", "good");
    } catch (error) {
      console.warn("[DomotiApp Coach] programma instellen mislukt", error);
      this.setManualStatus_(
        `Het programma instellen is niet gelukt: ${error?.message || "het apparaat gaf geen antwoord"}.`,
        "bad"
      );
      // Back to what the machine actually has, so the dropdown never shows a
      // program that was never set.
      this.paintProgramPicker_(this.manualDevice_);
    } finally {
      this.sending_ = false;
      this.setManualButtons_(false);
    }
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
    const select = this.$("#manual-program");
    if (!this.$("#manual-pick").hidden) select.disabled = busy || !select.options.length;
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
