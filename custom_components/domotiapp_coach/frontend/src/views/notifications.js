/**
 * Meldingen -- wie welke melding krijgt, en alles wat de coach deed en meldde.
 *
 * Twee dingen op één scherm, en dat is met opzet. De eigenaar op 06-09-2026: "ik wil
 * dat de klant meldingen kan aan en uit zetten in het meldingen tabje. Twee in
 * een: de admin voegt de personen toe, en die persoon ziet alleen zichzelf,
 * met welke soorten meldingen hij of zij krijgt."
 *
 * Bovenaan staan de personen. Een persoon is een telefoon (een notify-dienst
 * van Home Assistant) met een naam en per soort melding een schuif. Sinds
 * v0.114.0 voegt de bewoner ze zelf toe en haalt ze weg, en ziet hij iedereen;
 * de eigenaar op 12-10-2026: "Ja dat mag de bewoner." Daaronder de meldingen
 * met een drempel, ook van de bewoner: "Zware belasting", lekkage en de
 * temperatuur van de batterij. En daaronder de geschiedenis.
 *
 * Vier soorten, dezelfde als `kind` in de geschiedenis op de server, plus de
 * zekeringmelding van monitor.py:
 *   kritiek    wat je zelf moet oplossen: sensor stil, niet op tijd vol, herstart
 *   melding    de verslagen: vol, kabel eruit, een sensor die het weer doet
 *   besluit    elk besluit van de coach; standaard uit, want dat zijn er veel
 *   belasting  je aansluiting wordt te zwaar belast
 * De eigenaar op 05-09-2026: "dat je op normale en kritieke meldingen kan filteren
 * en op de tijd." Vandaar de knoppen boven de lijst en de dagkeuze.
 *
 * De lijst komt van `domotiapp_coach/notifications/list` en groeit live mee via
 * het event `domotiapp_coach_notification`, sinds v0.108.1 via
 * `domotiapp_coach/subscribe` (`volgCoach`), zodat ook een bewoner zonder
 * beheerdersrechten hem ziet groeien. Wie wat krijgt staat in de
 * instellingen onder `notifications` en gaat via `notifications/set` (admin)
 * of `notifications/household` (iedereen, zonder de koppeling aan een account).
 */

import { DacElement, define } from "../base.js";
import { volgCoach } from "../data-source.js";
import { deviceLabel, deviceLabelMap } from "../devices.js";
import { icons } from "../icons.js";

const DAGEN = ["zondag", "maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag"];
const MAANDEN = [
  "januari", "februari", "maart", "april", "mei", "juni",
  "juli", "augustus", "september", "oktober", "november", "december",
];

const twee = (n) => String(n).padStart(2, "0");

/** De soorten, in de volgorde op de kaart van een persoon. */
export const SOORTEN_INFO = [
  {
    id: "kritiek",
    label: "Kritiek",
    uitleg: "Wat je zelf moet oplossen: een sensor die zwijgt, een auto die niet op tijd vol raakt, een paal die opnieuw gestart is, een thuisbatterij die te warm wordt.",
  },
  {
    id: "melding",
    label: "Verslagen",
    uitleg: "Als een laadbeurt klaar is, de kabel eruit gaat, of een sensor het weer doet.",
  },
  {
    id: "belasting",
    label: "Zware belasting",
    uitleg: "Als je aansluiting te zwaar belast wordt, zodat je iets uit kunt zetten voor de zekering eruit gaat.",
  },
  {
    id: "besluit",
    label: "Elk besluit",
    uitleg: "Elke keer dat de coach iets anders gaat doen. Dat zijn er veel; alleen als je alles wilt volgen.",
  },
];

/** Wat een nieuwe persoon krijgt; dezelfde keuze als ontvangers.py op de server. */
export const STANDAARD_SOORTEN = { kritiek: true, melding: true, besluit: false, belasting: true };

/** Tussentijden, in minuten. */
const INTERVALS = [5, 10, 15, 30, 60, 120, 240];

/** Hoe lang de belasting moet aanhouden, in seconden; onder de vijf is een piek. */
const HOLDS = [5, 10, 30, 60, 120, 300];

/** "mobile_app_iphone_van_de_keuken" leest als "Iphone van de keuken". */
export function naamVanTelefoon(target) {
  const naam = String(target ?? "").replace(/^mobile_app_/, "").replace(/_/g, " ").trim();
  return naam ? naam[0].toUpperCase() + naam.slice(1) : String(target ?? "");
}

/**
 * Welke personen deze gebruiker ziet: iedereen, sinds v0.114.0.
 *
 * Tot dan zag een bewoner alleen de persoon die aan zijn account hing (de
 * eigenaar op 06-09-2026). Op 12-10-2026, op de vraag of de bewoner zelf
 * personen toevoegt en weghaalt en iedereen ziet: "Ja dat mag de bewoner."
 * Daarmee had de koppeling aan een account geen taak meer op dit scherm.
 */
export function zichtbaar(people, _user) {
  return (people ?? []).filter((p) => p && p.target);
}

/** De soort van een regel; oudere regels hebben het veld niet en zijn meldingen. */
export function soortVan(item) {
  return item?.kind === "besluit" || item?.kind === "kritiek" ? item.kind : "melding";
}

/** "Vandaag", "Gisteren", of "vrijdag 4 september". */
export function dagkop(moment, nu = new Date()) {
  const dag = new Date(moment.getFullYear(), moment.getMonth(), moment.getDate());
  const vandaag = new Date(nu.getFullYear(), nu.getMonth(), nu.getDate());
  const verschil = Math.round((vandaag - dag) / 86400000);
  if (verschil === 0) return "Vandaag";
  if (verschil === 1) return "Gisteren";
  const kop = `${DAGEN[dag.getDay()]} ${dag.getDate()} ${MAANDEN[dag.getMonth()]}`;
  return dag.getFullYear() === vandaag.getFullYear() ? kop : `${kop} ${dag.getFullYear()}`;
}

/** "2026-09-05": de sleutel van een dag, voor de dagkeuze. */
const dagsleutel = (moment) =>
  `${moment.getFullYear()}-${twee(moment.getMonth() + 1)}-${twee(moment.getDate())}`;

/**
 * Wat er overblijft na het filter. `soort` is "alles", "besluit", "melding"
 * of "kritiek"; "melding" laat ook kritiek zien, want dat is een melding
 * die bovendien dringend is. `dag` is een dagsleutel of leeg voor alle dagen.
 */
export function zeef(items, { soort = "alles", dag = "" } = {}) {
  return (items ?? []).filter((item) => {
    const s = soortVan(item);
    if (soort === "besluit" && s !== "besluit") return false;
    if (soort === "melding" && s === "besluit") return false;
    if (soort === "kritiek" && s !== "kritiek") return false;
    if (dag) {
      const moment = new Date(item?.at ?? "");
      if (Number.isNaN(moment.getTime()) || dagsleutel(moment) !== dag) return false;
    }
    return true;
  });
}

/**
 * Hoeveel dagen de geschiedenis laat zien (v0.101.5). De eigenaar op
 * 29-09-2026: "ik wil dat de geschiedenis onder meldingen max 2 weken toont,
 * anders teveel scrollen." Vandaag en de dertien dagen ervoor; de opslag houdt
 * er meer, maar die staan hier niet.
 */
export const GESCHIEDENIS_DAGEN = 14;

/** Alleen wat binnen `GESCHIEDENIS_DAGEN` valt, gerekend vanaf middernacht. */
export function recent(items, nu = new Date(), aantal = GESCHIEDENIS_DAGEN) {
  const grens = new Date(nu);
  grens.setHours(0, 0, 0, 0);
  grens.setDate(grens.getDate() - (aantal - 1));
  return (items ?? []).filter((item) => {
    const moment = new Date(item?.at ?? "");
    return !Number.isNaN(moment.getTime()) && moment >= grens;
  });
}

/** De dagen die in de lijst voorkomen, de nieuwste eerst, voor de dagkeuze. */
export function dagen(items, nu = new Date()) {
  const uit = [];
  const gezien = new Set();
  for (const item of items ?? []) {
    const moment = new Date(item?.at ?? "");
    if (Number.isNaN(moment.getTime())) continue;
    const sleutel = dagsleutel(moment);
    if (gezien.has(sleutel)) continue;
    gezien.add(sleutel);
    uit.push({ sleutel, kop: dagkop(moment, nu) });
  }
  return uit;
}

/**
 * De meldingen per dag, de nieuwste dag en de nieuwste melding eerst. Een
 * melding zonder leesbaar tijdstip valt weg: liever een regel minder dan een
 * streepje in de tijdkolom.
 */
export function groepeer(items, nu = new Date()) {
  const groepen = [];
  for (const item of items ?? []) {
    const moment = new Date(item?.at ?? "");
    if (Number.isNaN(moment.getTime()) || !item?.message) continue;
    const kop = dagkop(moment, nu);
    let groep = groepen[groepen.length - 1];
    if (!groep || groep.kop !== kop) {
      groep = { kop, rijen: [] };
      groepen.push(groep);
    }
    groep.rijen.push({
      tijd: `${twee(moment.getHours())}:${twee(moment.getMinutes())}`,
      tekst: item.message,
      soort: soortVan(item),
    });
  }
  return groepen;
}

const SOORTEN = [
  ["alles", "Alles"],
  ["besluit", "Besluiten"],
  ["melding", "Meldingen"],
  ["kritiek", "Kritiek"],
];

/** "na ..." in woorden. */
function wachtLabel(seconds) {
  const value = Number(seconds) || 0;
  if (value < 60) return `${value} seconden`;
  const minutes = value / 60;
  return minutes === 1 ? "1 minuut" : `${minutes} minuten`;
}

/** "eens per ..." in woorden. */
function tussenLabel(minutes) {
  const value = Number(minutes) || 0;
  if (value < 60) return `${value} minuten`;
  const hours = value / 60;
  return hours === 1 ? "uur" : `${hours} uur`;
}

const css = /* css */ `
  .page { padding: 18px 16px calc(24px + var(--dac-safe-b, 0px)); max-width: 760px; margin: 0 auto; }
  h1 { font-size: 22px; margin: 0 0 4px; display: flex; align-items: center; gap: 10px; }
  h1 svg { width: 22px; height: 22px; color: var(--dac-accent); }
  h2 { font-size: 15px; margin: 0 0 4px; display: flex; align-items: center; gap: 8px; }
  h2 svg { width: 17px; height: 17px; color: var(--dac-accent-hi); }
  .sub, .hint { margin: 0 0 14px; color: var(--dac-ink-3); font-size: 13.5px; line-height: 1.5; }
  .blok { margin: 0 0 26px; }
  .blok[hidden] { display: none; }

  /* ---- de personen ---- */
  .personen { display: grid; gap: 12px; }
  .persoon {
    border: 1px solid var(--dac-border); border-radius: var(--dac-radius-sm);
    background: rgba(var(--dac-veil),0.03); padding: 12px 14px 6px;
  }
  .persoon .kop { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin-bottom: 6px; }
  .persoon .naam { font-size: 15px; font-weight: 600; }
  .persoon .tel {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11.5px;
    color: var(--dac-ink-3); overflow-wrap: anywhere;
  }
  .persoon .tel.weg { color: var(--dac-warn); }
  .soort {
    display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: center;
    padding: 9px 0; border-top: 1px solid var(--dac-border);
  }
  .soort strong { display: block; font-size: 13.5px; font-weight: 600; }
  .soort span { display: block; font-size: 12.5px; color: var(--dac-ink-3); line-height: 1.45; margin-top: 2px; }
  /* Een knop en geen checkbox: een echte checkbox is per browser anders
     opgemaakt en die van iOS negeert de helft van wat hier staat. Zelfde
     schuif als op de kaart van een apparaat. */
  /* Aan is een gevulde blauwe baan met een witte knop rechts, uit een grijze
     baan met een doffe knop links. De zachte variant van eerst was van een
     afstand niet van uit te onderscheiden; de eigenaar op 06-09-2026. */
  /* box-sizing en line-height staan er met opzet: in het echte paneel erft
     een knop een regelhoogte en groeit hij, en dan hangt de knop boven het
     midden. De eigenaar op 06-09-2026: "het witte bolletje is niet in het midden."
     De knop staat daarom op 50% en niet op een vaste 3px. */
  .schuif {
    flex: 0 0 auto; box-sizing: border-box; display: inline-block; vertical-align: middle;
    width: 46px; min-width: 46px; height: 27px; padding: 0; margin: 0; line-height: 0; font-size: 0;
    border-radius: var(--dac-radius-pill); border: 1px solid transparent;
    background: rgba(var(--dac-ink-rgb),0.16); cursor: pointer; position: relative;
    transition: background 120ms linear, border-color 120ms linear;
  }
  .schuif .knob {
    position: absolute; top: 0; bottom: 0; margin: auto 0; left: 3px; width: 19px; height: 19px; border-radius: 50%;
    transform: translate(0, 0);
    background: var(--dac-knob); transition: transform 120ms linear, background 120ms linear;
    box-shadow: 0 1px 2px rgba(0,0,0,0.35);
  }
  .schuif[aria-checked="true"] { background: var(--dac-accent-hi); }
  .schuif[aria-checked="true"] .knob { transform: translate(19px, 0); background: #fff; }
  .schuif:focus-visible { outline: 2px solid var(--dac-accent-hi); outline-offset: 2px; }
  .schuif:disabled { opacity: 0.4; cursor: default; }
  .persoon .voet { display: flex; justify-content: flex-end; padding: 6px 0 4px; border-top: 1px solid var(--dac-border); }
  .knop {
    font: inherit; font-size: 13px; padding: 7px 14px; border-radius: var(--dac-radius-pill); cursor: pointer;
    border: 1px solid var(--dac-border); background: transparent; color: var(--dac-ink-2, inherit);
    display: inline-flex; align-items: center; gap: 6px; min-height: 36px;
  }
  .knop svg { width: 15px; height: 15px; }
  .knop:hover { border-color: var(--dac-border-hi); color: var(--dac-ink); }
  .knop.primair { border-color: var(--dac-accent); background: var(--dac-accent-soft); color: var(--dac-ink); }
  .knop.weg { color: var(--dac-ink-3); }
  .knop.weg.zeker { border-color: var(--dac-warn); color: var(--dac-warn); }
  .knop:disabled { opacity: 0.5; cursor: default; }
  .leeg { color: var(--dac-ink-3); font-size: 14px; padding: 12px 0; line-height: 1.5; }

  /* ---- toevoegen en de zekeringmelding: velden ---- */
  /* align-content: start, anders rekt het ene veld zich op tot de hoogte van
     zijn buurman met uitleg eronder en wordt het invoervak twee keer zo hoog.
     De eigenaar op 06-09-2026: "de uitlijning van naam en telefoon staat versprongen." */
  .velden { display: grid; gap: 10px; margin-top: 12px; align-items: start; }
  .veld { display: grid; gap: 4px; align-content: start; }
  .veld label { font-size: 12px; color: var(--dac-ink-3); font-weight: 500; }
  .veld .uitleg { font-size: 12px; color: var(--dac-ink-3); line-height: 1.45; }
  input, select {
    font: inherit; font-size: 14px; padding: 8px 10px; border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.04); color: var(--dac-ink);
    min-height: 40px; width: 100%; box-sizing: border-box;
  }
  input:focus, select:focus { outline: 2px solid var(--dac-accent); outline-offset: 1px; }
  /* De uitklaplijst tekent de browser zelf, buiten onze stijlen om. Zonder
     color-scheme kwam hij wit met onze lichte letters erin: onleesbaar. De eigenaar
     op 06-09-2026, met een schermafdruk waarop hij "amper wat kon lezen". */
  select { color-scheme: var(--dac-scheme); }
  select option { background: var(--dac-bg-raise); color: var(--dac-ink); }
  @media (pointer: coarse) { input, select { font-size: 16px; } }
  .rij-knoppen { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  .status { font-size: 12.5px; color: var(--dac-ink-3); min-height: 18px; margin-top: 6px; }
  .status.fout { color: var(--dac-warn); }
  .aanzet { display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: center; margin-top: 6px; }
  .aanzet strong { font-size: 13.5px; }
  .aanzet span { display: block; font-size: 12.5px; color: var(--dac-ink-3); margin-top: 2px; line-height: 1.45; }
  #belasting-velden[hidden] { display: none; }
  @media (min-width: 620px) { .velden.twee { grid-template-columns: 1fr 1fr; } }

  /* ---- de geschiedenis ---- */
  .filter { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 0 0 16px; }
  .filter button {
    font: inherit; font-size: 13px; padding: 6px 12px; border-radius: 999px; cursor: pointer;
    border: 1px solid var(--dac-border); background: transparent; color: var(--dac-ink-2, inherit);
  }
  .filter button.aan { border-color: var(--dac-accent); background: var(--dac-accent-soft); color: var(--dac-ink); }
  .filter select {
    font: inherit; font-size: 13px; padding: 6px 10px; border-radius: 999px; margin-left: auto;
    border: 1px solid var(--dac-border); background: transparent; color: var(--dac-ink); max-width: 100%;
    width: auto; min-height: 0;
  }
  .dag {
    font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; font-weight: 700;
    color: var(--dac-ink-3); margin: 18px 0 6px;
  }
  .dag:first-child { margin-top: 0; }
  .rij {
    display: grid; grid-template-columns: 52px 1fr; gap: 10px; align-items: start;
    padding: 10px 12px; border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.03);
    margin-bottom: 6px;
  }
  /* Een besluit is wat de coach deed; een melding ging ook naar de telefoon
     en mag daarom opvallen; kritiek is een melding waar je iets mee moet. */
  .rij.besluit { background: transparent; border-color: transparent; padding-top: 6px; padding-bottom: 6px; margin-bottom: 2px; }
  .rij.besluit .tekst { color: var(--dac-ink-2, inherit); font-size: 13.5px; }
  .rij.kritiek { border-color: var(--dac-warn); border-left-width: 4px; }
  .tijd { font-variant-numeric: tabular-nums; color: var(--dac-ink-3); font-size: 13px; padding-top: 1px; }
  /* Een verslag is sinds v0.102.1 een paar korte regels onder elkaar; het
     regeleinde hoort hier ook te zien te zijn. */
  .tekst { font-size: 14px; line-height: 1.45; overflow-wrap: anywhere; white-space: pre-line; }
  @media (max-width: 320px) {
    .rij { grid-template-columns: 44px 1fr; gap: 8px; padding: 8px 10px; }
    .filter select { margin-left: 0; }
    .soort { grid-template-columns: 1fr; }
  }
`;

class DacViewNotifications extends DacElement {
  static css = css;

  constructor() {
    super();
    this.hass_ = null;
    this.settings_ = null;
    this.items_ = [];
    this.geladen_ = false;
    this.off_ = null;
    this.filter_ = { soort: "alles", dag: "" };
    this.bezig_ = false;
    this.zekerWeg_ = "";
  }

  set hass(value) {
    const eerste = !this.hass_;
    this.hass_ = value;
    if (this.rendered_ && !this.geladen_) this.laad_();
    if (this.rendered_ && eerste) this.paintAlles_();
  }

  get hass() {
    return this.hass_;
  }

  set settings(value) {
    this.settings_ = value;
    if (this.rendered_) this.paintAlles_();
  }

  isAdmin_() {
    return this.hass_?.user?.is_admin !== false;
  }

  meldingen_() {
    return this.settings_?.notifications ?? { people: [], load_alert: {} };
  }

  render() {
    return /* html */ `
      <section class="page">
        <h1>${icons.bell} Meldingen</h1>
        <p class="sub">Wie welke berichten op zijn telefoon krijgt, en alles wat de coach deed en meldde.</p>

        <section class="blok" id="wie">
          <h2>${icons.devices} Wie krijgt wat</h2>
          <p class="hint" id="wie-hint"></p>
          <div class="personen" id="personen"></div>
          <div id="toevoegen" hidden>
            <div class="velden twee">
              <div class="veld">
                <label for="nieuw-naam">Naam</label>
                <input id="nieuw-naam" type="text" maxlength="40" placeholder="Naam van de bewoner" autocomplete="off">
              </div>
              <div class="veld">
                <label for="nieuw-telefoon">Telefoon</label>
                <select id="nieuw-telefoon"></select>
                <span class="uitleg">Elke telefoon met de Home Assistant-app staat hier, zodra de app erop ingelogd is.</span>
              </div>
            </div>
            <div class="rij-knoppen" style="margin-top: 10px;">
              <button type="button" class="knop primair" id="nieuw-knop">${icons.plus} Persoon toevoegen</button>
              <span class="status" id="wie-status"></span>
            </div>
          </div>
          <div class="status" id="mijn-status"></div>
        </section>

        <section class="blok" id="belasting" hidden>
          <h2>${icons.warning} Zware belasting</h2>
          <p class="hint">Een bericht zodra je aansluiting te zwaar belast wordt. De coach kijkt naar de zwaarst belaste fase als die bekend is, anders naar je totale netvermogen. Wie het krijgt staat hierboven per persoon.</p>
          <div class="aanzet">
            <div>
              <strong>Melding aanzetten</strong>
              <span>Zonder dit blijft de belastbaarheid gewoon op het overzicht staan, maar krijgt niemand er bericht van.</span>
            </div>
            <button type="button" class="schuif" role="switch" aria-checked="false" id="belasting-aan" aria-label="Zware belasting aan"><span class="knob"></span></button>
          </div>
          <div class="velden" id="belasting-velden" hidden>
            <div class="veld">
              <label for="belasting-grens">Waarschuw vanaf (%)</label>
              <input type="number" id="belasting-grens" min="1" max="200" step="1" inputmode="numeric">
              <span class="uitleg" id="belasting-grens-hint"></span>
            </div>
            <div class="veld">
              <label for="belasting-wacht">Pas melden als het aanhoudt</label>
              <select id="belasting-wacht">${HOLDS.map((s) => `<option value="${s}">${wachtLabel(s)}</option>`).join("")}</select>
              <span class="uitleg">Een oven of een motor die aanslaat geeft een piek van een seconde waar geen zekering van uit gaat. Pas als de belasting zo lang boven de grens blijft, gaat er bericht uit.</span>
            </div>
            <div class="veld">
              <label for="belasting-tussen">Niet vaker dan eens per</label>
              <select id="belasting-tussen">${INTERVALS.map((m) => `<option value="${m}">${tussenLabel(m)}</option>`).join("")}</select>
              <span class="uitleg">De belasting schommelt heen en weer over de grens; zonder tussentijd zou je een reeks berichten krijgen voor één druk uur.</span>
            </div>
          </div>
          <div class="status" id="belasting-status"></div>
        </section>

        <section class="blok" id="verbruik" hidden>
          <h2>${icons.warning} Lekkage of abnormaal verbruik</h2>
          <p class="hint">Een bericht als er te lang onafgebroken water loopt, of als een dag veel meer gas of water vraagt dan gewoon. Water vraagt een watermeter onder Installatie; voor het lopende water ook de sensor van het verbruik nu.</p>
          <div class="aanzet">
            <div>
              <strong>Melding aanzetten</strong>
              <span>De coach houdt het dagverbruik van gas en water sowieso bij; met dit aan zegt hij het als een dag uit de toon valt.</span>
            </div>
            <button type="button" class="schuif" role="switch" aria-checked="false" id="verbruik-aan" aria-label="Lekkage of abnormaal verbruik aan"><span class="knob"></span></button>
          </div>
          <div class="velden" id="verbruik-velden" hidden>
            <div class="veld">
              <label for="verbruik-water">Water dat blijft lopen, langer dan</label>
              <select id="verbruik-water">${[30, 60, 120, 240, 480].map((m) => `<option value="${m}">${m < 60 ? `${m} minuten` : `${m / 60} uur`}</option>`).join("")}</select>
              <span class="uitleg">Een bad of een wasmachine loopt een half uur; een kraan die openstaat of een lekkende leiding loopt de hele nacht.</span>
            </div>
            <div class="veld">
              <label for="verbruik-factor">Een dag valt uit de toon vanaf</label>
              <select id="verbruik-factor">${[2, 3, 4, 5].map((f) => `<option value="${f}">${f} keer het gewone dagverbruik</option>`).join("")}</select>
              <span class="uitleg">Gewoon is de middelste dag van de laatste dertig. Een wasdag of een koude dag komt daar niet zomaar overheen; een lekkage wel.</span>
            </div>
          </div>
          <div class="status" id="verbruik-status"></div>
        </section>

        <section class="blok" id="warmte" hidden>
          <h2>${icons.warning} Thuisbatterij te warm</h2>
          <p class="hint">Een bericht als de temperatuur van de thuisbatterij boven je grens komt, en blijft. Welke temperatuur te hoog is staat in de handleiding van de batterij. Het gaat naar wie Kritiek aan heeft staan.</p>
          <div class="aanzet">
            <div>
              <strong>Melding aanzetten</strong>
              <span>Zakt hij weer een graad onder de grens, dan staat dat alleen in de geschiedenis hieronder.</span>
            </div>
            <button type="button" class="schuif" role="switch" aria-checked="false" id="warmte-aan" aria-label="Thuisbatterij te warm aan"><span class="knob"></span></button>
          </div>
          <div class="velden" id="warmte-velden" hidden>
            <div class="veld">
              <label for="warmte-grens">Bericht boven (°C)</label>
              <input type="number" id="warmte-grens" min="0" max="100" step="0.5" inputmode="decimal">
              <span class="uitleg" id="warmte-grens-hint"></span>
            </div>
          </div>
          <div class="status" id="warmte-status"></div>
        </section>

        <section class="blok" id="stekker" hidden>
          <h2>${icons.warning} Apparaat staat uit</h2>
          <p class="hint">Een bericht als een apparaat dat altijd aan moet staan uit gaat en de coach het na 2 minuten nog niet weer aan heeft gekregen. Het gaat naar wie Kritiek aan heeft staan.</p>
          <div class="aanzet">
            <div>
              <strong>Melding aanzetten</strong>
              <span id="stekker-wie"></span>
            </div>
            <button type="button" class="schuif" role="switch" aria-checked="false" id="stekker-aan" aria-label="Apparaat staat uit aan"><span class="knob"></span></button>
          </div>
          <div class="status" id="stekker-status"></div>
        </section>

        <section class="blok">
          <h2>${icons.bell} Geschiedenis</h2>
          <p class="hint">Alles wat de coach deed en meldde in de afgelopen twee weken, de nieuwste bovenaan. Wat ook naar een telefoon ging staat in een kader; kritiek is wat je zelf moet oplossen.</p>
          <div class="filter" id="filter">
            ${SOORTEN.map(([id, label]) =>
              `<button type="button" data-soort="${id}"${id === "alles" ? ' class="aan"' : ""}>${label}</button>`).join("")}
            <select id="dag" aria-label="Dag"><option value="">Alle dagen</option></select>
          </div>
          <div id="lijst"></div>
        </section>
      </section>
    `;
  }

  afterRender() {
    this.$("#filter")?.addEventListener("click", (e) => {
      const knop = e.target?.closest?.("button[data-soort]");
      if (!knop) return;
      this.filter_ = { ...this.filter_, soort: knop.dataset.soort };
      this.paint_();
    });
    this.$("#dag")?.addEventListener("change", (e) => {
      this.filter_ = { ...this.filter_, dag: e.target.value };
      this.paint_();
    });
    this.$("#nieuw-knop")?.addEventListener("click", () => this.toevoegen_());
    this.$("#belasting-aan")?.addEventListener("click", () => {
      const aan = this.$("#belasting-aan").getAttribute("aria-checked") !== "true";
      this.bewaarBelasting_({ enabled: aan });
    });
    this.$("#belasting-grens")?.addEventListener("change", (e) => {
      const waarde = Number(e.target.value);
      if (waarde >= 1 && waarde <= 200) this.bewaarBelasting_({ threshold_percent: waarde });
    });
    this.$("#belasting-wacht")?.addEventListener("change", (e) =>
      this.bewaarBelasting_({ min_duration_seconds: Number(e.target.value) }));
    this.$("#belasting-tussen")?.addEventListener("change", (e) =>
      this.bewaarBelasting_({ min_interval_minutes: Number(e.target.value) }));
    this.$("#verbruik-aan")?.addEventListener("click", () => {
      const aan = this.$("#verbruik-aan").getAttribute("aria-checked") !== "true";
      this.bewaarVerbruik_({ enabled: aan });
    });
    this.$("#verbruik-water")?.addEventListener("change", (e) =>
      this.bewaarVerbruik_({ water_flow_minutes: Number(e.target.value) }));
    this.$("#verbruik-factor")?.addEventListener("change", (e) =>
      this.bewaarVerbruik_({ factor: Number(e.target.value) }));
    this.$("#warmte-aan")?.addEventListener("click", () => {
      const aan = this.$("#warmte-aan").getAttribute("aria-checked") !== "true";
      this.bewaarWarmte_({ enabled: aan });
    });
    this.$("#stekker-aan")?.addEventListener("click", () => {
      const aan = this.$("#stekker-aan").getAttribute("aria-checked") !== "true";
      this.bewaarStekker_({ enabled: aan });
    });
    this.$("#warmte-grens")?.addEventListener("change", (e) => {
      const tekst = String(e.target.value).trim();
      const waarde = Number(tekst);
      if (!tekst) this.bewaarWarmte_({ max_c: null });
      else if (waarde >= 0 && waarde <= 100) this.bewaarWarmte_({ max_c: waarde });
    });
    this.paintAlles_();
  }

  onConnect() {
    this.laad_();
    this.volg_();
  }

  onDisconnect() {
    if (this.off_) {
      this.off_();
      this.off_ = null;
    }
  }

  paintAlles_() {
    this.paintPersonen_();
    this.paintBelasting_();
    this.paintVerbruik_();
    this.paintWarmte_();
    this.paintStekker_();
    this.paint_();
  }

  // ------------------------------------------------------------------
  // wie krijgt wat

  /** Elke notify-dienst die Home Assistant kent, zonder de eigen meldingenbalk. */
  telefoons_() {
    return Object.keys(this.hass_?.services?.notify ?? {})
      .filter((name) => name !== "persistent_notification")
      .sort();
  }

  paintPersonen_() {
    const holder = this.$("#personen");
    if (!holder) return;
    const mensen = zichtbaar(this.meldingen_().people, this.hass_?.user);
    const hint = this.$("#wie-hint");
    if (hint) {
      hint.textContent = "Per persoon welke berichten er naar zijn telefoon gaan. Voeg hieronder iemand toe met de telefoon waarop de Home Assistant-app staat.";
    }
    holder.replaceChildren();
    if (!mensen.length) {
      const leeg = document.createElement("div");
      leeg.className = "leeg";
      leeg.textContent = "Er is nog niemand toegevoegd. Zonder personen gaat er niets naar een telefoon; de geschiedenis hieronder vult zich wel.";
      holder.append(leeg);
    }
    const bekend = this.telefoons_();
    for (const persoon of mensen) {
      holder.append(this.kaart_(persoon, bekend));
    }
    // Toevoegen kan iedereen (v0.114.0). Een account koppelen staat er niet
    // meer bij: dat diende alleen om een bewoner hier zichzelf te laten zien.
    const toevoegen = this.$("#toevoegen");
    if (toevoegen) {
      toevoegen.hidden = false;
      this.paintToevoegen_();
    }
  }

  /** De kaart van één persoon: naam, telefoon, en een schuif per soort. */
  kaart_(persoon, bekend) {
    const el = document.createElement("div");
    el.className = "persoon";
    el.dataset.persoon = persoon.id;

    const kop = document.createElement("div");
    kop.className = "kop";
    const naam = document.createElement("span");
    naam.className = "naam";
    naam.textContent = persoon.name || naamVanTelefoon(persoon.target);
    const tel = document.createElement("span");
    const weg = bekend.length && !bekend.includes(persoon.target);
    tel.className = `tel${weg ? " weg" : ""}`;
    tel.textContent = `notify.${persoon.target}${weg ? " (bestaat niet meer in Home Assistant)" : ""}`;
    kop.append(naam, tel);
    el.append(kop);

    for (const soort of SOORTEN_INFO) {
      const rij = document.createElement("div");
      rij.className = "soort";
      const tekst = document.createElement("div");
      const label = document.createElement("strong");
      label.textContent = soort.label;
      label.id = `soort-${persoon.id}-${soort.id}`;
      const uitleg = document.createElement("span");
      uitleg.textContent = soort.uitleg;
      tekst.append(label, uitleg);
      const schuif = document.createElement("button");
      schuif.type = "button";
      schuif.className = "schuif";
      schuif.setAttribute("role", "switch");
      schuif.setAttribute("aria-labelledby", label.id);
      schuif.setAttribute("aria-checked", String(Boolean((persoon.kinds ?? {})[soort.id])));
      schuif.dataset.soort = soort.id;
      const knob = document.createElement("span");
      knob.className = "knob";
      schuif.append(knob);
      schuif.addEventListener("click", () => this.zetSoort_(persoon.id, soort.id, schuif));
      rij.append(tekst, schuif);
      el.append(rij);
    }

    {
      const voet = document.createElement("div");
      voet.className = "voet";
      const knop = document.createElement("button");
      knop.type = "button";
      const zeker = this.zekerWeg_ === persoon.id;
      knop.className = `knop weg${zeker ? " zeker" : ""}`;
      knop.innerHTML = `${icons.trash} <span>${zeker ? "Echt verwijderen?" : "Verwijderen"}</span>`;
      knop.addEventListener("click", () => this.verwijderen_(persoon.id));
      voet.append(knop);
      el.append(voet);
    }
    return el;
  }

  paintToevoegen_() {
    const telefoon = this.$("#nieuw-telefoon");
    if (!telefoon) return;
    const gekozen = telefoon.value;
    telefoon.replaceChildren();
    const bekend = this.telefoons_();
    if (!bekend.length) {
      const optie = document.createElement("option");
      optie.value = "";
      optie.textContent = "Nog geen telefoon met de app ingelogd";
      telefoon.append(optie);
    }
    for (const name of bekend) {
      const optie = document.createElement("option");
      optie.value = name;
      optie.textContent = `${naamVanTelefoon(name)} (notify.${name})`;
      telefoon.append(optie);
    }
    if (gekozen && bekend.includes(gekozen)) telefoon.value = gekozen;

    const knop = this.$("#nieuw-knop");
    if (knop) knop.disabled = !bekend.length || this.bezig_;
  }

  async toevoegen_() {
    const naam = this.$("#nieuw-naam")?.value?.trim() ?? "";
    const target = this.$("#nieuw-telefoon")?.value ?? "";
    if (!target) return;
    const mensen = [...(this.meldingen_().people ?? [])];
    if (mensen.some((p) => p.target === target)) {
      this.status_("#wie-status", "Die telefoon staat er al.", true);
      return;
    }
    mensen.push({
      name: naam || naamVanTelefoon(target),
      target,
      kinds: { ...STANDAARD_SOORTEN },
    });
    const gelukt = await this.bewaarPersonen_(mensen, "#wie-status");
    if (gelukt) {
      const veld = this.$("#nieuw-naam");
      if (veld) veld.value = "";
    }
  }

  async verwijderen_(id) {
    // Twee keer tikken, want een verwijderde persoon krijgt niets meer en
    // een echte bevestigingsdialoog is er niet op een kiosk.
    if (this.zekerWeg_ !== id) {
      this.zekerWeg_ = id;
      this.paintPersonen_();
      setTimeout(() => {
        if (this.zekerWeg_ === id) {
          this.zekerWeg_ = "";
          this.paintPersonen_();
        }
      }, 5000);
      return;
    }
    this.zekerWeg_ = "";
    const mensen = (this.meldingen_().people ?? []).filter((p) => p.id !== id);
    await this.bewaarPersonen_(mensen, "#wie-status");
  }

  async zetSoort_(persoonId, soort, schuif) {
    const mensen = (this.meldingen_().people ?? []).map((p) => ({ ...p, kinds: { ...(p.kinds ?? {}) } }));
    const persoon = mensen.find((p) => p.id === persoonId);
    if (!persoon) return;
    const aan = !persoon.kinds[soort];
    persoon.kinds[soort] = aan;
    // Meteen laten zien; gaat het opslaan mis, dan tekent de kaart zich terug.
    schuif.setAttribute("aria-checked", String(aan));
    await this.bewaarPersonen_(mensen, "#mijn-status");
  }

  /**
   * Waarlangs dit scherm opslaat: de admin via `notifications/set` en iedereen
   * anders via `notifications/household` (v0.114.0). Die laatste laat een
   * koppeling aan een account staan die er van vroeger nog is.
   */
  opslagCommando_() {
    return this.isAdmin_() ? "domotiapp_coach/notifications/set" : "domotiapp_coach/notifications/household";
  }

  async bewaarPersonen_(mensen, statusId) {
    if (!this.hass_?.callWS) return false;
    this.bezig_ = true;
    try {
      const settings = await this.hass_.callWS({
        type: this.opslagCommando_(),
        notifications: { people: mensen.map((p) => ({
          id: p.id ?? "", name: p.name ?? "", target: p.target, user_id: p.user_id ?? "", kinds: p.kinds ?? {},
        })) },
      });
      this.settings_ = settings;
      this.status_(statusId, "Opgeslagen", false);
      return true;
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de personen niet opslaan", error);
      this.status_(statusId, `Opslaan mislukt: ${error?.message ?? error}`, true);
      return false;
    } finally {
      this.bezig_ = false;
      this.paintPersonen_();
    }
  }

  status_(kiezer, tekst, fout) {
    const el = this.$(kiezer);
    if (!el) return;
    el.textContent = tekst;
    el.classList.toggle("fout", Boolean(fout));
    if (!fout) setTimeout(() => { if (el.textContent === tekst) el.textContent = ""; }, 2500);
  }

  // ------------------------------------------------------------------
  // zware belasting

  belasting_() {
    return this.meldingen_().load_alert ?? {};
  }

  verbruik_() {
    return this.meldingen_().usage_alert ?? {};
  }

  paintVerbruik_() {
    const blok = this.$("#verbruik");
    if (!blok) return;
    blok.hidden = !this.settings_;
    if (blok.hidden) return;
    const alert = this.verbruik_();
    this.$("#verbruik-aan").setAttribute("aria-checked", String(Boolean(alert.enabled)));
    this.$("#verbruik-velden").hidden = !alert.enabled;
    this.$("#verbruik-water").value = String(alert.water_flow_minutes ?? 120);
    this.$("#verbruik-factor").value = String(alert.factor ?? 3);
  }

  async bewaarVerbruik_(wijziging) {
    if (!this.hass_?.callWS) return;
    try {
      const settings = await this.hass_.callWS({
        type: this.opslagCommando_(),
        notifications: { usage_alert: { ...this.verbruik_(), ...wijziging } },
      });
      this.settings_ = settings;
      this.status_("#verbruik-status", "Opgeslagen", false);
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de verbruiksmelding niet opslaan", error);
      this.status_("#verbruik-status", `Opslaan mislukt: ${error?.message ?? error}`, true);
    }
    this.paintVerbruik_();
  }

  // ------------------------------------------------------------------
  // thuisbatterij te warm (v0.108.0)

  warmte_() {
    return this.meldingen_().temp_alert ?? {};
  }

  /** Elke thuisbatterij, met de temperatuur die haar sensor nu geeft (of null). */
  batterijTemperaturen_() {
    return (this.settings_?.devices ?? [])
      .filter((d) => d?.type === "thuisbatterij")
      .map((d) => {
        const id = d.entities?.temperature;
        const waarde = id ? Number(this.hass_?.states?.[id]?.state) : NaN;
        return { naam: d.name || "Thuisbatterij", sensor: Boolean(id), graden: Number.isFinite(waarde) ? waarde : null };
      });
  }

  paintWarmte_() {
    const blok = this.$("#warmte");
    if (!blok) return;
    const accus = this.batterijTemperaturen_();
    // Alleen voor wie een thuisbatterij heeft; zonder is er niets om te meten.
    blok.hidden = !this.settings_ || !accus.length;
    if (blok.hidden) return;
    const alert = this.warmte_();
    this.$("#warmte-aan").setAttribute("aria-checked", String(Boolean(alert.enabled)));
    this.$("#warmte-velden").hidden = !alert.enabled;
    const veld = this.$("#warmte-grens");
    if (this.shadowRoot?.activeElement !== veld) veld.value = alert.max_c ?? "";
    const metSensor = accus.filter((a) => a.sensor);
    const graden = (g) => `${g.toLocaleString("nl-NL", { maximumFractionDigits: 1 })} °C`;
    let hint;
    // Apparaten ziet alleen de installateur (v0.114.0); de bewoner krijgt te
    // horen wie het kan regelen.
    if (!metSensor.length) {
      hint = this.isAdmin_()
        ? "Vul eerst de temperatuur van de batterij in onder Apparaten; zonder sensor is er niets te melden."
        : "Je installateur moet eerst de temperatuur van de batterij koppelen; zonder sensor is er niets te melden.";
    }
    else if (alert.max_c === null || alert.max_c === undefined) hint = "Vul in boven welke temperatuur je een bericht wilt.";
    else {
      hint = metSensor
        .map((a) => `${metSensor.length > 1 ? `${a.naam} nu` : "Nu"} ${a.graden === null ? "onbekend" : graden(a.graden)}`)
        .join(", ") + ".";
    }
    this.$("#warmte-grens-hint").textContent = hint;
  }

  async bewaarWarmte_(wijziging) {
    if (!this.hass_?.callWS) return;
    try {
      const settings = await this.hass_.callWS({
        type: this.opslagCommando_(),
        notifications: { temp_alert: { ...this.warmte_(), ...wijziging } },
      });
      this.settings_ = settings;
      this.status_("#warmte-status", "Opgeslagen", false);
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de temperatuurmelding niet opslaan", error);
      this.status_("#warmte-status", `Opslaan mislukt: ${error?.message ?? error}`, true);
    }
    this.paintWarmte_();
  }

  // ------------------------------------------------------------------
  // apparaat staat uit (v0.120.0)

  stekker_() {
    return this.meldingen_().always_on_alert ?? {};
  }

  /** De apparaten op een smart plug die altijd aan moeten staan. */
  altijdAan_() {
    return (this.settings_?.devices ?? []).filter((d) => d?.type === "smartplug" && d.always_on);
  }

  /**
   * De eigenaar op 15-10-2026: "Lukt dat niet wil ik na 2 min een melding
   * ontvangen. Pas de melding sturen als je dat hebt ingesteld in meldingen."
   * Alleen te zien als er iets altijd aan moet staan; zonder is er niets te melden.
   */
  paintStekker_() {
    const blok = this.$("#stekker");
    if (!blok) return;
    const apparaten = this.altijdAan_();
    blok.hidden = !this.settings_ || !apparaten.length;
    if (blok.hidden) return;
    this.$("#stekker-aan").setAttribute("aria-checked", String(Boolean(this.stekker_().enabled)));
    const labels = deviceLabelMap(this.settings_?.devices ?? []);
    const namen = apparaten.map((d) => labels.get(d.id) ?? deviceLabel(d));
    this.$("#stekker-wie").textContent =
      `Geldt voor ${namen.join(", ").replace(/, ([^,]*)$/, " en $1")}. Krijgt de coach het weer aan, dan staat dat alleen in de geschiedenis hieronder.`;
  }

  async bewaarStekker_(wijziging) {
    if (!this.hass_?.callWS) return;
    try {
      const settings = await this.hass_.callWS({
        type: this.opslagCommando_(),
        notifications: { always_on_alert: { ...this.stekker_(), ...wijziging } },
      });
      this.settings_ = settings;
      this.status_("#stekker-status", "Opgeslagen", false);
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de melding over een apparaat dat uit staat niet opslaan", error);
      this.status_("#stekker-status", `Opslaan mislukt: ${error?.message ?? error}`, true);
    }
    this.paintStekker_();
  }

  paintBelasting_() {
    const blok = this.$("#belasting");
    if (!blok) return;
    blok.hidden = !this.settings_;
    if (blok.hidden) return;
    const alert = this.belasting_();
    this.$("#belasting-aan").setAttribute("aria-checked", String(Boolean(alert.enabled)));
    this.$("#belasting-velden").hidden = !alert.enabled;
    this.$("#belasting-grens").value = alert.threshold_percent ?? 80;
    this.$("#belasting-wacht").value = String(alert.min_duration_seconds ?? 60);
    this.$("#belasting-tussen").value = String(alert.min_interval_minutes ?? 30);
    const fuse = Number(this.settings_?.installation?.fuse_amps) || 0;
    const phases = Number(this.settings_?.installation?.phases) || 1;
    const percent = Number(alert.threshold_percent) || 0;
    const hint = this.$("#belasting-grens-hint");
    if (!fuse) {
      hint.textContent = "Vul eerst je aansluiting in onder Installatie.";
    } else {
      const amps = ((fuse * percent) / 100).toLocaleString("nl-NL", { maximumFractionDigits: 1 });
      hint.textContent = `Bij ${phases} × ${fuse} A komt dat neer op ${amps} A per fase.`;
    }
  }

  async bewaarBelasting_(wijziging) {
    if (!this.hass_?.callWS) return;
    try {
      const settings = await this.hass_.callWS({
        type: this.opslagCommando_(),
        notifications: { load_alert: { ...this.belasting_(), ...wijziging } },
      });
      this.settings_ = settings;
      this.status_("#belasting-status", "Opgeslagen", false);
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de zekeringmelding niet opslaan", error);
      this.status_("#belasting-status", `Opslaan mislukt: ${error?.message ?? error}`, true);
    }
    this.paintBelasting_();
    this.paintVerbruik_();
  }

  // ------------------------------------------------------------------
  // de geschiedenis

  async laad_() {
    if (!this.hass_?.callWS) return;
    try {
      this.items_ = await this.hass_.callWS({ type: "domotiapp_coach/notifications/list" });
      this.geladen_ = true;
      this.paint_();
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de meldingen niet laden", error);
    }
  }

  async volg_() {
    if (!this.hass_?.connection || this.off_) return;
    try {
      this.off_ = await volgCoach(this.hass_, "notification", (item) => {
        if (!item?.message) return;
        this.items_ = [item, ...this.items_];
        this.paint_();
      });
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de meldingen niet volgen", error);
    }
  }

  /** De dagkeuze bijwerken zonder de gekozen dag kwijt te raken. */
  dagen_() {
    const keuze = this.$("#dag");
    if (!keuze) return;
    const gekozen = this.filter_.dag;
    const opties = dagen(recent(this.items_));
    if (gekozen && !opties.some((d) => d.sleutel === gekozen)) this.filter_ = { ...this.filter_, dag: "" };
    keuze.replaceChildren();
    const alle = document.createElement("option");
    alle.value = "";
    alle.textContent = "Alle dagen";
    keuze.append(alle);
    for (const d of opties) {
      const optie = document.createElement("option");
      optie.value = d.sleutel;
      optie.textContent = d.kop;
      keuze.append(optie);
    }
    keuze.value = this.filter_.dag;
  }

  paint_() {
    const lijst = this.$("#lijst");
    if (!lijst) return;
    for (const knop of this.$$("#filter button[data-soort]") ?? []) {
      knop.classList.toggle("aan", knop.dataset.soort === this.filter_.soort);
    }
    this.dagen_();
    lijst.replaceChildren();
    const groepen = groepeer(zeef(recent(this.items_), this.filter_));
    if (!groepen.length) {
      const leeg = document.createElement("div");
      leeg.className = "leeg";
      leeg.textContent = !this.geladen_
        ? "De meldingen worden opgehaald."
        : recent(this.items_).length
          ? "Niets dat aan dit filter voldoet."
          : "De coach heeft de afgelopen twee weken niets gemeld.";
      lijst.append(leeg);
      return;
    }
    for (const groep of groepen) {
      const kop = document.createElement("div");
      kop.className = "dag";
      kop.textContent = groep.kop;
      lijst.append(kop);
      for (const rij of groep.rijen) {
        const el = document.createElement("div");
        el.className = `rij ${rij.soort}`;
        const tijd = document.createElement("span");
        tijd.className = "tijd";
        tijd.textContent = rij.tijd;
        const tekst = document.createElement("span");
        tekst.className = "tekst";
        tekst.textContent = rij.tekst;
        el.append(tijd, tekst);
        lijst.append(el);
      }
    }
  }
}

define("dac-view-notifications", DacViewNotifications);
