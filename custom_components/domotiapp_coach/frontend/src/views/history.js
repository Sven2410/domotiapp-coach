/**
 * Historie -- what this house did per day, week, month or year.
 *
 * Reads Home Assistant's own long-term statistics and stores nothing of its
 * own; see statistics.js for why that is the whole point.
 *
 * The bars are the same drawing the energy dashboard makes, for a reason: above
 * the line is what the house used, split into the part that came from its own
 * roof and the part that was bought, and below the line is what went back to
 * the grid. In one shape that answers both "how much did I use" and "how much
 * of it was my own", and the second question is the one this panel exists for.
 *
 * Consumption is derived rather than measured, exactly as it is on Overzicht:
 * generation plus what came in, minus what went out, and since v0.101.2 minus
 * what a home battery took in net (`fetchBattery`). A separate house meter
 * would only add a way for them to disagree.
 */

import { DacElement, define } from "../base.js";
import { icons } from "../icons.js";
import { energy, euro, percent, signedPower } from "../format.js";
import { deviceLabel, deviceLabelMap } from "../devices.js";

/** Het merkteken op het rapport. */
const LOGO_URL = new URL("../../img/domotitech-mark.png", import.meta.url).href;
import { allInPrijzen, contractAt, laadCoachPrijzen, tariff, volgCoach } from "../data-source.js";
import { balkSoort, legenda, metHerkomst, netReeks, stippen, tekenTijdlijn, tekenUitleg, tijdlijn } from "../tijdlijn.js";
import { afleveren, base64Van } from "../pdf.js";
import { reportPdf } from "../report.js";
import { beurtenIn, delen, opmerking, perApparaat, totalen, woorden } from "../savings.js";
import { SALDEREN_TOT, accuVerdiend, accuZon, balans, prijsOp, salderen } from "../geld.js";
import {
  PERIODS,
  combine,
  fetchBattery,
  fetchDevices,
  fetchPeriod,
  fetchPrices,
  periodEnd,
  periodLabel,
  periodStart,
  quarters,
  samenvatting,
  withStatistics,
} from "../statistics.js";

/** Waar de terugknop je heen brengt, per tijdvak. */
const NOW_LABEL = {
  day: "Vandaag",
  week: "Deze week",
  month: "Deze maand",
  year: "Dit jaar",
};

/** Hoe oud de kwartieren van de tijdlijn van vandaag mogen zijn voor ze opnieuw komen. */
const TIJDLIJN_VERS_MS = 5 * 60 * 1000;

/**
 * Bij welke periodes de tijdlijn staat. Een dag sinds v0.115.0, een week sinds
 * v0.116.1: de eigenaar op 13-10-2026, bij Week, "waarom is de tijdlijn weg die
 * wil ik wel behouden". Een maand aan balken leest niemand meer.
 */
const TIJDLIJN_PERIODES = new Set(["day", "week"]);

/** Drawing units; the chart measures itself in pixels like the price chart. */
const MIN_W = 240;
const TOP = 18;
const BOTTOM_PAD = 22;

const nl = (value, digits = 1) =>
  value.toLocaleString("nl-NL", { minimumFractionDigits: digits, maximumFractionDigits: digits });

/**
 * Wat het huis in één vak gebruikte, met de thuisbatterij erbij (v0.101.2).
 *
 * `battery` is wat de batterijen netto opnamen, laden positief. Verbruik is dan
 * de eigen zon plus wat er van het net kwam, min wat de batterij opnam: een
 * nacht op de batterij is verbruik, een middag laden niet. Van het net naar het
 * huis is wat er binnenkwam min wat daarvan de batterij in ging; die laadt eerst
 * uit de eigen zon, zoals het energiedashboard van Home Assistant het ook
 * verdeelt. `zonInAccu` is de zon die de batterij in ging, voor In geld over de
 * tijd dat de coach dat nog niet zelf telde (`voor`).
 */
export function huisMetAccu(own, bought, accu = { battery: 0, voor: 0 }) {
  const battery = Number(accu?.battery) || 0;
  const used = Math.max(0, own + bought - battery);
  const vanNetInAccu = Math.max(0, Math.max(0, battery) - own);
  const fromGrid = Math.min(used, Math.max(0, bought - vanNetInAccu));
  return {
    used,
    fromGrid,
    ownUse: used - fromGrid,
    battery,
    zonInAccu: Math.min(Math.max(0, Number(accu?.voor) || 0), own),
  };
}

/** Hoeveel apparaten een eigen kleur krijgen (`--dac-app-1` tot en met 6); de rest is grijs. */
const APP_KLEUREN = 6;

/**
 * Wat er in elk vak van de grafiek valt, uit rijen van een uur, een dag of een
 * maand (v0.121.0). `tijden` zijn de begintijden van de vakken, `einde` het
 * eind van de periode; een rij erbuiten telt niet mee. Een teller geeft zijn
 * vakken al, een schatting uit het vermogen komt per uur (`fetchDevices`).
 */
export function perVak(rijen, tijden, einde) {
  const uit = tijden.map(() => 0);
  for (const [tijd, kwh] of rijen ?? []) {
    let i = tijden.length - 1;
    while (i >= 0 && tijden[i] > tijd) i -= 1;
    if (i < 0 || tijd >= (tijden[i + 1] ?? einde)) continue;
    uit[i] += Number(kwh) || 0;
  }
  return uit;
}

/**
 * Het verbruik per apparaat over de vakken van de grafiek (v0.121.0), zoals
 * "Afzonderlijke apparaten" in het energiedashboard van Home Assistant. De
 * eigenaar op 15-10-2026: "ik wil ook het energieverbruik per apparaat kunnen
 * zien in historie zoals het HA energy dashboard", "per dag per jaar etc".
 *
 * De thuisbatterij hoort er niet bij: die verbruikt niet, die schuift op. Elk
 * apparaat houdt zijn kleur op de volgorde van Apparaten en niet op grootte,
 * zodat een andere periode hem niet overschildert; vanaf het zevende valt het
 * onder "Overige apparaten". Een vak telt nooit onder nul (een teller die
 * opnieuw begint).
 *
 * @returns {{id: string, label: string, kleur: number|"rest", vakken: number[],
 *   totaal: number, exact: boolean}[]} op de volgorde van Apparaten
 */
export function apparaatReeksen(devices, stats, tijden, einde) {
  const labels = deviceLabelMap(devices ?? []);
  const reeksen = [];
  const overig = { id: "__overig__", label: "Overige apparaten", kleur: "rest", vakken: tijden.map(() => 0), totaal: 0, exact: true };
  let plek = 0;
  for (const device of devices ?? []) {
    if (!device || device.type === "thuisbatterij" || (!device.entity && !device.energy_entity)) continue;
    plek += 1;
    const gevonden = stats?.get(device.id);
    if (!gevonden) continue;
    const vakken = perVak(gevonden.rows, tijden, einde).map((kwh) => Math.max(0, kwh));
    const totaal = vakken.reduce((som, kwh) => som + kwh, 0);
    if (totaal < 0.01) continue;
    if (plek > APP_KLEUREN) {
      vakken.forEach((kwh, i) => { overig.vakken[i] += kwh; });
      overig.totaal += totaal;
      overig.exact &&= gevonden.exact !== false;
      continue;
    }
    reeksen.push({ id: device.id, label: labels.get(device.id) ?? deviceLabel(device), kleur: plek, vakken, totaal, exact: gevonden.exact !== false });
  }
  if (overig.totaal >= 0.01) reeksen.push(overig);
  return reeksen;
}

/** How one bucket is named in the read-out above the chart. */
function bucketTitle(period, date) {
  if (period === "day") {
    return `${String(date.getHours()).padStart(2, "0")}:00 tot ${String((date.getHours() + 1) % 24).padStart(2, "0")}:00`;
  }
  if (period === "year") return date.toLocaleDateString("nl-NL", { month: "long", year: "numeric" });
  return date.toLocaleDateString("nl-NL", { weekday: "long", day: "numeric", month: "long" });
}

/**
 * Een vermogen als tekst, met de eenheid die er bij de grootte past.
 *
 * Met het teken erbij, anders dan op de meeste plekken in het paneel. In een
 * tabel staat er geen pijl en geen kleur naast, en bij een netmeter die met een
 * teken werkt is dat het enige verschil tussen zes kilowatt afnemen en zes
 * kilowatt terugleveren.
 */
function watt(value) {
  if (!Number.isFinite(value)) return "";
  const { value: getal, unit } = signedPower(value);
  return `${getal} ${unit}`;
}

/**
 * Hoe fijn het verloop per periode wordt getoond.
 *
 * Op een dag is dat het kwartier waarin het bewaard wordt; fijner bestaat niet
 * en grover zou de pieken uitsmeren. Over een maand zouden kwartieren bijna
 * drieduizend regels per apparaat opleveren, en dat is geen rapport meer maar
 * een gegevensbestand. De piek blijft in elk tijdvak de echte piek: bij het
 * samenvoegen wordt de hoogste van de kwartieren genomen en niet een nieuw
 * gemiddelde.
 */
const KORRELS = {
  quarter: {
    kop: "Kwartier",
    sleutel: (d) => d.getTime(),
    label: (d) => d.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" }),
    uitleg:
      "Elk kwartier van deze dag, met het laagste, het gemiddelde en de piek. De piek is de " +
      "hoogste waarde die de sensor binnen dat kwartier gemeld heeft, dus zo scherp als je " +
      "meter meet. Kwartieren waarin de sensor niets liet horen staan er niet in.",
  },
  hour: {
    kop: "Uur",
    sleutel: (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate(), d.getHours()).getTime(),
    label: (d) =>
      `${d.toLocaleDateString("nl-NL", { weekday: "short" }).replace(".", "")} ` +
      `${String(d.getHours()).padStart(2, "0")}:00`,
    uitleg:
      "Elk uur van deze week, samengesteld uit de kwartieren eronder. De piek is de hoogste " +
      "waarde binnen dat uur. Wil je het fijner of grover, kies dan een andere korrel boven de grafiek.",
  },
  day: {
    kop: "Dag",
    sleutel: (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime(),
    label: (d) => d.toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short" })
      .replace(/\./g, ""),
    uitleg:
      "Elke dag van deze maand, samengesteld uit de kwartieren eronder. De piek is de hoogste " +
      "waarde die er die dag in een kwartier stond. Wil je het fijner of grover, kies dan een andere korrel boven de grafiek.",
  },
  month: {
    kop: "Maand",
    sleutel: (d) => new Date(d.getFullYear(), d.getMonth()).getTime(),
    label: (d) => d.toLocaleDateString("nl-NL", { month: "long" }),
    uitleg:
      "Elke maand van dit jaar, samengesteld uit de kwartieren eronder. De piek is de hoogste " +
      "waarde die er die maand in een kwartier stond.",
  },
};

/** De knoppen waarmee de klant de fijnheid kiest, van fijn naar grof. */
const KORREL_KNOPPEN = [
  { id: "quarter", label: "Kwartier" },
  { id: "hour", label: "Uur" },
  { id: "day", label: "Dag" },
  { id: "month", label: "Maand" },
];

/** Wat er bij een periode past zolang de klant zelf niets aanwijst. */
const STANDAARD_KORREL = {
  day: "quarter",
  week: "hour",
  month: "day",
  year: "month",
};

/**
 * Hoeveel regels een keuze ongeveer oplevert, per apparaat.
 *
 * Ruwe getallen, want een maand heeft 28 tot 31 dagen en dat verschil doet er
 * hier niet toe: het gaat erom of het tien regels worden of tienduizend. Een
 * lege plek betekent dat die keuze bij die periode niets oplevert, en dan gaat
 * de knop uit; een jaar per maand is zinnig, een dag per maand is één regel.
 */
const REGELS = {
  day: { quarter: 96, hour: 24 },
  week: { quarter: 672, hour: 168, day: 7 },
  month: { quarter: 2976, hour: 744, day: 31 },
  year: { quarter: 35040, hour: 8760, day: 365, month: 12 },
};

/**
 * De netmeter, in de vorm waarin deze woning hem heeft.
 *
 * Twee soorten, en het rapport hoort ze allebei te kunnen. Serieel uitgelezen
 * geeft twee aparte meters, een voor wat er binnenkomt en een voor wat er
 * teruggaat, allebei altijd positief. Een P1 met een teken is er een: positief
 * is afname en negatief is teruglevering, en dan is een tweede regel er niet en
 * zou "Van het net" ook niet meer kloppen.
 *
 * Welke van de twee het is staat in `grid_mode`, dezelfde keuze die
 * `data-source.js` maakt voor het scherm. Zonder deze tak viel bij een meter
 * met een teken het net helemaal uit het rapport: `grid_import` en
 * `grid_export` zijn dan leeg, en die twee regels vielen weg zonder dat er iets
 * voor terugkwam.
 */
function netBronnen(bronnen) {
  if (bronnen.grid_mode === "signed") {
    return [
      {
        entity: bronnen.grid_signed,
        label: "Het net",
        omkeren: Boolean(bronnen.grid_signed_invert),
      },
    ];
  }
  return [
    { entity: bronnen.grid_import, label: "Van het net" },
    { entity: bronnen.grid_export, label: "Naar het net" },
  ];
}

/**
 * Een reeks kwartieren omdraaien, voor een meter die de andere kant op telt.
 *
 * `archive.py` bewaart wat de sensor zelf zei en past het vinkje van de klant
 * niet toe; dat gebeurt overal pas bij het lezen. Hier dus ook, anders staat
 * afname bij zo'n meter als teruglevering in het rapport.
 *
 * Het laagste en de piek wisselen daarbij van plek: het laagste van min wordt
 * de hoogste van plus.
 */
function omgekeerd(rows) {
  return (rows ?? []).map((row) => ({
    ...row,
    laagste: -row.piek,
    piek: -row.laagste,
    gemiddeld: -row.gemiddeld,
  }));
}

/**
 * Kwartieren samenvoegen tot de tijdvakken van deze korrel.
 *
 * Het laagste en de piek gaan mee zoals ze zijn: dat zijn gemeten waarden en
 * die worden niet opnieuw uitgerekend. Het gemiddelde weegt naar de tijd die
 * elk kwartier werkelijk gedekt heeft, dus een kwartier waarin de sensor tien
 * minuten weg was telt voor een derde mee.
 */
function vakken(rows, korrel) {
  const uit = new Map();
  for (const row of rows) {
    if (!Number.isFinite(row.gemiddeld) || row.seconden <= 0) continue;
    const sleutel = korrel.sleutel(row.start);
    const vak = uit.get(sleutel) ?? {
      start: new Date(sleutel),
      laagste: Infinity,
      piek: -Infinity,
      gewogen: 0,
      seconden: 0,
    };
    vak.laagste = Math.min(vak.laagste, row.laagste);
    vak.piek = Math.max(vak.piek, row.piek);
    vak.gewogen += row.gemiddeld * row.seconden;
    vak.seconden += row.seconden;
    uit.set(sleutel, vak);
  }
  return [...uit.values()]
    .sort((a, b) => a.start - b.start)
    .map((vak) => ({ ...vak, gemiddeld: vak.gewogen / vak.seconden }));
}

/**
 * Wanneer een piek viel, zo kort als in deze periode nog eenduidig is.
 *
 * Op een dagrapport is de klok genoeg. Over een week of langer is het tijdstip
 * zonder de dag erbij niets waard: "19:45" zegt dan niet welke avond.
 */
function piekMoment(period, date) {
  const klok = date.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" });
  if (period === "day") return klok;
  const dag = date.toLocaleDateString("nl-NL", { day: "numeric", month: "short" });
  return `${dag.replace(".", "")} ${klok}`;
}

/** What each bucket is called under the chart. */
function bucketLabel(period, date) {
  if (period === "day") return String(date.getHours()).padStart(2, "0");
  if (period === "year") return date.toLocaleDateString("nl-NL", { month: "short" }).replace(".", "");
  return String(date.getDate());
}


class DacViewHistory extends DacElement {
  constructor() {
    super();
    // Vandaag, want dat is wat je meestal wilt zien; het is ook de eerste knop
    // van de rij, en een rij die op de tweede opent leest als een fout
    // (de eigenaar op 22-09-2026).
    this.period_ = "day";
    // Energie of Bespaard; de laadbeurten komen pas als iemand daarnaar kijkt.
    this.onderwerp_ = "energie";
    this.beurten_ = undefined;
    this.offset_ = 0;
    // Hoe fijn het verloop in het rapport komt te staan. Leeg betekent: kies
    // wat bij de periode past. Zodra de klant zelf iets aanwijst blijft die
    // keuze staan, ook als hij van periode wisselt: iemand die pieken per
    // kwartier wil zien, wil dat over een week net zo goed als over een dag.
    this.korrel_ = "";
  }

  set hass(value) {
    const first = !this.hass_;
    this.hass_ = value;
    if (first && this.rendered_) this.load_();
  }

  /** @param {import("../state-feed.js").StateFeed} value */
  set stateFeed(value) {
    this.feed_ = value;
    if (this.rendered_) this.paint_();
  }

  set settings(value) {
    const before = JSON.stringify(value?.sources?.meters ?? {});
    const changed = before !== this.metersKey_;
    this.metersKey_ = before;
    this.settings_ = value;
    if (this.rendered_ && changed) this.load_();
  }

  render() {
    return `
      <div class="wrap">
        <header class="intro">
          <div class="eyebrow">Historie</div>
          <h1>Wat je huis heeft gedaan</h1>
          <p id="intro-lijn">Boven de lijn wat je verbruikte, onder de lijn wat je teruggaf.</p>
        </header>

        <!-- De keuzes als uitklaplijst, en een knop Rapport. De eigenaar op
             13-10-2026: "periode onderwerp en verloop moet een drop down worden
             wat je kiest", en het moet overzichtelijk zijn: vier rijen knoppen
             en een regel over 768 rapportregels was te veel. -->
        <div class="controls">
          <label class="keuze">
            <span class="keuze-kop">Onderwerp</span>
            <span class="kies"><select id="onderwerp">
              <option value="energie">Energie</option>
              <option value="bespaard">Beurten</option>
            </select></span>
          </label>
          <label class="keuze">
            <span class="keuze-kop">Periode</span>
            <span class="kies"><select id="periode">
              ${PERIODS.map((item) => `<option value="${item.id}">${item.label}</option>`).join("")}
            </select></span>
          </label>
          <label class="keuze" title="Hoe fijn het verloop in het rapport komt te staan">
            <span class="keuze-kop">Verloop in het rapport</span>
            <span class="kies"><select id="korrel">
              ${KORREL_KNOPPEN.map((item) => `<option value="${item.id}">${item.label}</option>`).join("")}
            </select></span>
          </label>
          <!-- Twee rapporten achter één knop. De bewoner van de eerste woning op
               22-09-2026: "omdat ie nu zó uitgebreid is downloaden consumenten m
               straks niet meer; dus twee varianten bieden, een onepager en een
               uitgebreide." -->
          <div class="rapport">
            <button type="button" class="download" id="rapport-knop" aria-haspopup="true" aria-expanded="false">
              ${icons.compass}<span>Rapport</span>
            </button>
            <div class="rapport-menu" id="rapport-menu" hidden>
              <button type="button" id="report-short"><span>Kort rapport</span><small>Eén pagina: de cijfers, het geld en bespaard</small></button>
              <button type="button" id="report"><span>Uitgebreid rapport</span><small>Alles, met het verloop per apparaat</small></button>
            </div>
          </div>
          <div class="stepper">
            <button type="button" class="now" id="now" hidden></button>
            <button type="button" id="prev" aria-label="Vorige">${icons.arrowLeft}</button>
            <span id="period-label"></span>
            <button type="button" id="next" aria-label="Volgende">${icons.arrowRight}</button>
          </div>
        </div>

        <section class="card" id="card">
          <div class="totals-title" id="totals-title"></div>
          <div class="totals" id="totals"></div>
          <div id="stage"></div>
          <div class="legend" id="legend"></div>
          <p class="note" id="note"></p>
        </section>

        <!-- Per apparaat (v0.121.0), zoals het energiedashboard van Home
             Assistant. De eigenaar op 15-10-2026: "ik wil ook het energieverbruik
             per apparaat kunnen zien in historie", bij elke periode. -->
        <section class="card" id="apparaten-card" hidden>
          <div class="panel-head">
            <div class="eyebrow">Per apparaat</div>
            <h2 id="apparaten-titel">Wat je apparaten verbruikten</h2>
          </div>
          <div id="apparaten-stage"></div>
          <ul class="app-lijst" id="apparaten-lijst"></ul>
          <p class="note" id="apparaten-note"></p>
        </section>

        <!-- De tijdlijn (v0.115.0). De eigenaar op 11-10-2026: "Ik wil kunnen zien
             wat de coach en de aanstuurbare apparaten hebben gedaan", als tijdlijn,
             "en als je op de tijdlijn klikt een korte tekst". De som staat in
             tijdlijn.js. -->
        <section class="card" id="tijdlijn-card" hidden>
          <div class="panel-head">
            <div class="eyebrow">Tijdlijn</div>
            <h2>Wat de coach deed</h2>
          </div>
          <div id="tijdlijn"></div>
          <div class="legend" id="tijdlijn-legenda"></div>
          <div class="tl-uitleg" id="tijdlijn-uitleg" role="status" hidden></div>
          <p class="note" id="tijdlijn-note"></p>
        </section>

        <!-- In geld (v0.101.0). De eigenaar op 28-09-2026: "ik wil op het historie
             overzicht duidelijk hebben wat ik heb bespaard die dag, totaal
             uitgegeven en totaal bespaard. Maak een mooi overzicht." De som
             staat in geld.js, zodat het rapport precies hetzelfde zegt. -->
        <section class="card money" id="money-card" hidden>
          <div class="panel-head">
            <div class="eyebrow">In geld</div>
            <h2 id="money-title">Wat deze periode kostte en opleverde</h2>
          </div>
          <div class="geld-kop" id="money-hero"></div>
          <div class="geld-balk" id="money-bar" role="img"></div>
          <div class="geld-delen" id="money-parts"></div>
          <p class="note" id="money-note"></p>
        </section>

        <section class="card gas" id="gas-card" hidden>
          <div class="panel-head">
            <div class="eyebrow">Gas</div>
            <h2 id="gas-total"></h2>
          </div>
          <div id="gas-stage"></div>
        </section>

        <section class="card gas water" id="water-card" hidden>
          <div class="panel-head">
            <div class="eyebrow">Water</div>
            <h2 id="water-total"></h2>
          </div>
          <div id="water-stage"></div>
        </section>

        <section class="card saved" id="saved-card" hidden>
          <div class="panel-head">
            <div class="eyebrow">Beurten</div>
            <h2>Wat de coach je bespaarde</h2>
          </div>
          <div class="totals" id="saved-totals"></div>
          <p class="note" id="saved-note"></p>
          <div class="tabel-wrap"><table class="beurten" id="saved-list"></table></div>
        </section>
      </div>
    `;
  }

  afterRender() {
    this.$("#onderwerp").addEventListener("change", (event) => {
      this.onderwerp_ = event.target.value;
      if (this.onderwerp_ === "bespaard") this.laadBeurten_();
      this.paint_();
    });
    this.$("#periode").addEventListener("change", (event) => {
      this.period_ = event.target.value;
      this.offset_ = 0;
      this.load_();
    });
    this.$("#korrel").addEventListener("change", (event) => {
      this.korrel_ = event.target.value;
      this.paintKorrel_();
    });

    // Rapport: één knop, en daaronder de keuze tussen kort en uitgebreid.
    const menu = this.$("#rapport-menu");
    const rapportKnop = this.$("#rapport-knop");
    const zetMenu = (open) => {
      menu.hidden = !open;
      rapportKnop.setAttribute("aria-expanded", String(open));
      menu.style.left = "";
      if (!open) return;
      // Op een telefoon past het menu niet altijd rechts van de knop; dan
      // schuift het naar links, anders scrolt de hele pagina opzij.
      const rand = (window.innerWidth || document.documentElement.clientWidth) - 12;
      const over = menu.getBoundingClientRect().right - rand;
      if (over > 0) menu.style.left = `${-over}px`;
    };
    rapportKnop.addEventListener("click", () => zetMenu(menu.hidden));
    this.$("#report").addEventListener("click", () => {
      zetMenu(false);
      this.report_(false);
    });
    this.$("#report-short").addEventListener("click", () => {
      zetMenu(false);
      this.report_(true);
    });
    this.addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || menu.hidden) return;
      zetMenu(false);
      rapportKnop.focus();
    });
    this.addEventListener("pointerdown", (event) => {
      if (!menu.hidden && !event.composedPath().some((node) => node?.classList?.contains?.("rapport"))) zetMenu(false);
    });
    this.$("#prev").addEventListener("click", () => this.step_(-1));
    this.$("#next").addEventListener("click", () => this.step_(1));
    this.$("#now").addEventListener("click", () => {
      if (this.offset_ === 0) return;
      this.offset_ = 0;
      this.load_();
    });

    // Een muis meldt zich af zodra hij de grafiek verlaat; een vinger niet. Dus
    // telt hier een tik ergens anders op het scherm als afmelden, anders blijft
    // er op een telefoon een dag geselecteerd staan die niemand meer bedoelde.
    this.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "mouse") return;
      const path = event.composedPath();
      if (!path.some((node) => ["stage", "gas-stage", "water-stage", "apparaten-stage"].includes(node?.id))) {
        this.clearPick_();
        this.clearGasPick_();
        this.clearAppPick_();
      }
    });

    // Een tik op een stuk van de tijdlijn zet de korte tekst eronder; nog een
    // keer op hetzelfde stuk haalt hem weg.
    this.$("#tijdlijn").addEventListener("click", (event) => {
      const knop = event.target.closest?.("button[data-rij], button[data-stip]");
      if (!knop) return;
      const sleutel = knop.dataset.stip !== undefined ? `stip:${knop.dataset.stip}` : `${knop.dataset.rij}:${knop.dataset.stuk}`;
      this.tlGekozen_ = this.tlGekozen_ === sleutel ? "" : sleutel;
      this.paintTijdlijn_();
      // Met het toetsenbord blijft de focus op het stuk staan, ook nu het
      // opnieuw getekend is.
      if (event.detail === 0) {
        const selector = knop.dataset.stip !== undefined
          ? `[data-stip="${knop.dataset.stip}"]`
          : `[data-rij="${knop.dataset.rij}"][data-stuk="${knop.dataset.stuk}"]`;
        this.$(`#tijdlijn ${selector}`)?.focus({ preventScroll: true });
      }
    });

    this.load_();
  }

  onConnect() {
    // Redrawn on a resize because the chart is measured in pixels rather than
    // scaled: at phone width a scaled box takes 11px labels down to 3px.
    this.observer_ ??= new ResizeObserver(() => {
      const width = Math.round(this.getBoundingClientRect().width);
      if (!width || width === this.width_) return;
      this.width_ = width;
      this.paint_();
    });
    this.observer_.observe(this);

    // De tijdlijn van vandaag loopt mee: elke minuut schuift nu op, en om de
    // vijf minuten komen de kwartieren opnieuw.
    this.tlKlok_ ??= setInterval(() => {
      if (!TIJDLIJN_PERIODES.has(this.period_) || this.offset_ !== 0 || this.onderwerp_ !== "energie") return;
      if (this.tl_ && Date.now() - this.tl_.gehaald > TIJDLIJN_VERS_MS) this.laadTijdlijn_();
      else this.paintTijdlijn_();
    }, 60_000);
    this.volgMeldingen_();
  }

  onDisconnect() {
    this.observer_?.disconnect();
    clearInterval(this.tlKlok_);
    this.tlKlok_ = null;
    this.tlAf_?.();
    this.tlAf_ = null;
    this.tlVolg_ = false;
  }

  step_(direction) {
    // Never past today: there is nothing to see in a week that has not started.
    if (this.offset_ + direction > 0) return;
    this.offset_ += direction;
    this.load_();
  }

  /**
   * The entity whose price history to use, if there is one.
   *
   * Only for a dynamic contract: a fixed one is a number the customer typed in,
   * and that is exact for every day of the year without asking anybody.
   */
  priceEntity_() {
    const contract = this.settings_?.contract;
    if (contract?.type !== "dynamic") return "";
    const dynamic = contract.dynamic ?? {};
    return dynamic.source === "all_in" ? dynamic.all_in_entity : dynamic.market_entity;
  }

  /** De reserveprijssensor, voor de vakken waarin de eigen niets gaf (v0.101.3). */
  reserveEntity_() {
    const contract = this.settings_?.contract;
    return contract?.type === "dynamic" ? (contract.dynamic?.fallback_entity ?? "") : "";
  }

  /** Which counters this installation has, in the roles the chart needs. */
  meters_() {
    const meters = this.settings_?.sources?.meters ?? {};
    return {
      solar: [meters.solar_total, ...(Array.isArray(meters.solar_total_extra) ? meters.solar_total_extra : [])].filter(Boolean),
      import: [meters.import_low, meters.import_high].filter(Boolean),
      export: [meters.export_low, meters.export_high].filter(Boolean),
      gas: meters.gas_enabled && meters.gas ? [meters.gas] : [],
      water: meters.water_enabled && meters.water ? [meters.water] : [],
    };
  }

  async load_() {
    const roles = this.meters_();
    const ids = [...roles.solar, ...roles.import, ...roles.export, ...roles.gas, ...roles.water];

    this.paintPeriod_();
    // Los van de meterstanden: de tijdlijn heeft die niet nodig.
    this.laadTijdlijn_();

    if (!ids.length) {
      this.rows_ = null;
      this.paint_();
      return;
    }

    // A run of its own, so a slow answer for last month cannot overwrite the
    // week somebody clicked on in the meantime.
    const run = (this.run_ = (this.run_ ?? 0) + 1);
    const start = periodStart(this.period_, this.offset_);

    if (!this.checked_) {
      this.checked_ = true;
      this.have_ = await withStatistics(this.hass_, ids);
    }

    const apparaten = (this.settings_?.devices ?? []).map((device) => ({
      id: device.id,
      power: device.entity,
      energy: device.energy_entity,
    }));

    const batterijen = (this.settings_?.devices ?? []).filter((device) => device.type === "thuisbatterij");
    const [series, prices, reservePrijzen, devices, accu] = await Promise.all([
      fetchPeriod(this.hass_, ids, this.period_, start),
      fetchPrices(this.hass_, this.priceEntity_(), this.period_, start),
      fetchPrices(this.hass_, this.reserveEntity_(), this.period_, start),
      fetchDevices(this.hass_, apparaten, this.period_, start),
      fetchBattery(this.hass_, batterijen, this.period_, start),
      laadCoachPrijzen(this.hass_),
    ]);
    if (run !== this.run_) return;
    this.prices_ = allInPrijzen(prices, reservePrijzen, this.settings_?.contract);
    this.devices_ = devices;
    this.accu_ = accu;
    // Voor In geld: wat de coach bespaarde. De kaart tekent zichzelf bij als
    // de beurten binnen zijn.
    this.laadBeurten_();

    this.rows_ = {
      solar: combine(series, roles.solar),
      import: combine(series, roles.import),
      export: combine(series, roles.export),
      gas: combine(series, roles.gas),
      water: combine(series, roles.water),
    };
    this.paint_();
  }

  /** Welke fijnheid er gekozen is, en wat dat aan regels gaat kosten. */
  korrel_id() {
    const eigen = this.korrel_;
    return eigen && REGELS[this.period_]?.[eigen] ? eigen : STANDAARD_KORREL[this.period_];
  }

  paintKorrel_() {
    const lijst = this.$("#korrel");
    if (!lijst) return;
    // Wat bij deze periode niet kan staat er wel, maar is niet te kiezen: een
    // dag per maand bestaat niet.
    for (const optie of lijst.options) optie.disabled = !REGELS[this.period_]?.[optie.value];
    lijst.value = this.korrel_id();
  }

  paintPeriod_() {
    this.paintKorrel_();
    this.$("#periode").value = this.period_;
    this.$("#onderwerp").value = this.onderwerp_;
    this.$("#period-label").textContent = periodLabel(
      this.period_,
      periodStart(this.period_, this.offset_)
    );
    this.$("#next").disabled = this.offset_ >= 0;

    // Terug naar nu, in één tik. Een datum vertelt je namelijk niet of het de
    // datum van vandaag is: wie een paar weken teruggebladerd heeft, moet
    // anders eerst uitrekenen hoe vaak hij op het pijltje moet drukken. De knop
    // draagt de naam van waar hij je heen brengt en verdwijnt zodra je er bent.
    const nu = this.$("#now");
    nu.textContent = NOW_LABEL[this.period_] ?? "Nu";
    nu.title = `Terug naar ${(NOW_LABEL[this.period_] ?? "nu").toLowerCase()}`;
    nu.hidden = this.offset_ === 0;
  }

  paint_() {
    if (!this.rendered_) return;
    this.paintPeriod_();

    // Bespaard is een eigen onderwerp met dezelfde periodeknoppen: de
    // energiekaarten gaan dicht en de besparingskaart open, of andersom.
    const bespaard = this.onderwerp_ === "bespaard";
    this.$("#saved-card").hidden = !bespaard;
    // De zin over de lijn hoort bij de grafiek, en die staat bij Beurten niet.
    this.$("#intro-lijn").hidden = bespaard;
    this.$("#card").hidden = bespaard;
    if (bespaard) {
      this.$("#money-card").hidden = true;
      this.$("#apparaten-card").hidden = true;
      this.$("#gas-card").hidden = true;
      this.$("#water-card").hidden = true;
      this.$("#tijdlijn-card").hidden = true;
      this.paintSaved_();
      return;
    }
    this.paintTijdlijn_();

    const note = this.$("#note");
    const roles = this.meters_();

    if (!roles.import.length && !roles.export.length && !roles.solar.length) {
      this.$("#stage").innerHTML = "";
      this.$("#totals").replaceChildren();
      this.$("#legend").replaceChildren();
      this.$("#apparaten-card").hidden = true;
      this.$("#gas-card").hidden = true;
      this.$("#water-card").hidden = true;
      note.textContent =
        "Er zijn nog geen meterstanden gekozen. Onder Installatie bij Meterstanden wijs je de tellers aan; daarna staat hier je geschiedenis.";
      return;
    }

    if (!this.rows_) {
      note.textContent = "Bezig met ophalen…";
      return;
    }

    const missing = [...roles.solar, ...roles.import, ...roles.export].filter(
      (id) => this.have_ && !this.have_.has(id)
    );

    const zinnen = [];
    if (!roles.solar.length) {
      zinnen.push(
        "Je opwekteller staat nog niet ingesteld, dus je ziet hier alleen wat er van het net kwam en wat er naar het net ging. Vul bij Installatie onder Meterstanden de teller van je omvormer in, dan komen je opwek, je verbruik en je zelfbenutting er ook bij te staan."
      );
    }
    if (missing.length) {
      zinnen.push(
        `Van ${missing.length === 1 ? "één teller" : `${missing.length} tellers`} houdt Home Assistant geen geschiedenis bij. Dat gebeurt alleen bij sensoren die zichzelf als oplopende totaalstand aanbieden.`
      );
    }
    note.textContent = zinnen.join(" ");

    this.paintChart_();
    this.paintApparaten_();
    this.paintMoney_();
    this.paintGas_();
    this.paintVolume_("water", "Waterverbruik per periode");
  }

  /** De apparaten die een balk op de tijdlijn krijgen: wat de coach stuurt. */
  tijdlijnApparaten_() {
    return (this.settings_?.devices ?? []).filter((device) => balkSoort(device));
  }

  /**
   * Wat de tijdlijn van de gekozen dag of week nodig heeft (v0.115.0): de
   * besluiten uit Meldingen, en de kwartieren van de apparaten en van het net
   * voor de kleur.
   */
  async laadTijdlijn_() {
    if (!TIJDLIJN_PERIODES.has(this.period_) || !this.hass_?.callWS) return;
    const apparaten = this.tijdlijnApparaten_();
    if (!apparaten.length) return;
    const run = (this.tlRun_ = (this.tlRun_ ?? 0) + 1);
    const van = periodStart(this.period_, this.offset_);
    const sleutel = `${this.period_}:${van.getTime()}`;
    if (this.tl_?.dag !== sleutel) this.tlGekozen_ = "";

    const bronnen = this.settings_?.sources ?? {};
    const netId = bronnen.grid_mode === "signed" ? bronnen.grid_signed : bronnen.grid_import;
    let meldingen = [];
    try {
      meldingen = (await this.hass_.callWS({ type: "domotiapp_coach/notifications/list" })) ?? [];
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de meldingen voor de tijdlijn niet ophalen", error);
    }
    const kwartieren = await quarters(
      this.hass_,
      [...apparaten.map((device) => device.entity), netId],
      van,
      periodEnd(this.period_, van)
    );
    if (run !== this.tlRun_) return;
    this.tl_ = { dag: sleutel, meldingen, kwartieren, gehaald: Date.now() };
    this.volgMeldingen_();
    this.paintTijdlijn_();
  }

  /** Nieuwe meldingen komen er meteen bij, zodat vandaag niet op een herlaad wacht. */
  async volgMeldingen_() {
    if (this.tlVolg_ || !this.hass_ || !this.isConnected) return;
    this.tlVolg_ = true;
    const af = await volgCoach(this.hass_, "notification", (item) => {
      if (!item?.at || !this.tl_) return;
      this.tl_.meldingen = [item, ...this.tl_.meldingen];
      if (TIJDLIJN_PERIODES.has(this.period_) && this.offset_ === 0) this.paintTijdlijn_();
    });
    if (!this.isConnected) {
      af?.();
      this.tlVolg_ = false;
      return;
    }
    this.tlAf_ = af;
  }

  paintTijdlijn_() {
    const kaart = this.$("#tijdlijn-card");
    if (!kaart) return;
    const apparaten = this.tijdlijnApparaten_();
    kaart.hidden = this.onderwerp_ !== "energie" || !apparaten.length;
    if (kaart.hidden) return;

    const stage = this.$("#tijdlijn");
    const legendaVak = this.$("#tijdlijn-legenda");
    const uitleg = this.$("#tijdlijn-uitleg");
    const note = this.$("#tijdlijn-note");
    // Bij een maand of een jaar staat er één regel in plaats van niets, zodat de
    // kaart niet zomaar verdwijnt.
    if (!TIJDLIJN_PERIODES.has(this.period_)) {
      stage.innerHTML = "";
      legendaVak.replaceChildren();
      uitleg.hidden = true;
      note.textContent = "De tijdlijn staat bij Dag en Week.";
      return;
    }
    const van = periodStart(this.period_, this.offset_);
    const tot = periodEnd(this.period_, van);
    const tl = this.tl_;
    if (!tl || tl.dag !== `${this.period_}:${van.getTime()}`) {
      stage.innerHTML = "";
      legendaVak.replaceChildren();
      uitleg.hidden = true;
      note.textContent = "Bezig met ophalen…";
      return;
    }

    const nu = new Date();
    const alle = this.settings_?.devices ?? [];
    const namen = deviceLabelMap(alle);
    const bronnen = this.settings_?.sources ?? {};
    const metAccu = alle.some((device) => device.type === "thuisbatterij");
    const rijen = metHerkomst(
      tijdlijn(tl.meldingen, alle, van, tot, nu),
      (id) => tl.kwartieren.get(alle.find((device) => device.id === id)?.entity) ?? [],
      netReeks(bronnen, tl.kwartieren)
    );
    for (const rij of rijen) rij.naam = namen.get(rij.device) ?? rij.naam;
    const punten = stippen(tl.meldingen, van, tot);

    if (!rijen.length && !punten.length) {
      stage.innerHTML = "";
      legendaVak.replaceChildren();
      uitleg.hidden = true;
      const oudste = tl.meldingen.reduce((min, item) => (item?.at && item.at < min ? item.at : min), "9999");
      const deze = this.period_ === "day" ? "deze dag" : "deze week";
      note.textContent =
        oudste !== "9999" && new Date(oudste) >= tot
          ? `Van ${deze} heeft de coach niets bewaard. De tijdlijn begint op ${new Date(oudste).toLocaleDateString("nl-NL", { day: "numeric", month: "long" })}.`
          : `In ${deze} heeft de coach geen apparaten gestuurd.`;
      return;
    }

    const gekozen = this.tlGekozen_ ?? "";
    stage.innerHTML = tekenTijdlijn({ rijen, stippen: punten, van, tot, nu, gekozen, metAccu });
    legendaVak.innerHTML = legenda(rijen, metAccu)
      .map((item) => `<span><i class="vlek ${item.klasse}"></i>${item.label}</span>`)
      .join("");
    const tekst = gekozen ? tekenUitleg({ rijen, stippen: punten, gekozen, van, tot, nu, metAccu }) : "";
    uitleg.innerHTML = tekst;
    uitleg.hidden = !tekst;
    note.textContent = tekst ? "" : "Tik op een balk of een stip voor wat er gebeurde.";
  }

  /** The buckets of this period, in order, with everything that belongs to one. */
  buckets_() {
    const keys = new Set();
    for (const key of ["solar", "import", "export"]) {
      for (const row of this.rows_[key]) keys.add(row.start.getTime());
    }

    const at = (key, time) => this.rows_[key].find((row) => row.start.getTime() === time)?.value ?? 0;
    const tijden = [...keys].sort((a, b) => a - b);
    const einde = periodEnd(this.period_, periodStart(this.period_, this.offset_)).getTime();
    const vakEinde = (index) => tijden[index + 1] ?? einde;
    const accu = this.accuPerVak_(tijden, vakEinde);

    return tijden.map((time, index) => {
      const solar = at("solar", time);
      const bought = at("import", time);
      const sold = at("export", time);
      // Own use is what the roof made minus what went out. Never negative:
      // meters are read at slightly different moments and a rounding of a few
      // watt-hours must not turn into a negative bar.
      const own = Math.max(0, solar - sold);
      return { start: new Date(time), own, bought, sold, ...huisMetAccu(own, bought, accu[index]) };
    });
  }

  /**
   * Per vak wat de thuisbatterijen netto opnamen (`battery`), en welk deel
   * daarvan van batterijen is waarvan de coach toen nog niet bijhield hoeveel
   * zon erin ging (`voor`): daarvoor schat In geld het uit de vakken zelf.
   *
   * De uren of dagen van `fetchBattery` gaan in het vak waarin ze beginnen, met
   * de grenzen van de vakken zoals Home Assistant ze gaf, dus ook als die in
   * een andere tijdzone rekent dan deze browser.
   */
  accuPerVak_(tijden, vakEinde) {
    const uit = tijden.map(() => ({ battery: 0, voor: 0 }));
    const vanaf = new Map(
      (this.settings_?.battery_state ?? []).map((rij) => [
        rij?.device,
        rij?.solar_stored_from ? new Date(rij.solar_stored_from).getTime() : null,
      ])
    );
    for (const [id, rijen] of this.accu_ ?? new Map()) {
      let index = 0;
      for (const rij of rijen) {
        while (index < tijden.length && rij.start >= vakEinde(index)) index += 1;
        if (index >= tijden.length) break;
        if (rij.start < tijden[index]) continue;
        uit[index].battery += rij.kwh;
        const sinds = vanaf.get(id);
        if (!Number.isFinite(sinds) || vakEinde(index) <= sinds) uit[index].voor += rij.kwh;
      }
    }
    return uit;
  }

  paintChart_() {
    const rows = this.buckets_();
    const stage = this.$("#stage");

    if (!rows.length) {
      stage.innerHTML = "";
      this.$("#totals").replaceChildren();
      this.$("#legend").replaceChildren();
      this.$("#note").textContent = "Over deze periode is nog niets vastgelegd.";
      return;
    }

    const sum = (key) => rows.reduce((total, row) => total + row[key], 0);
    // Zonder opwekteller is er geen opwek en dus ook geen verbruik: verbruik is
    // opwek plus inkoop min teruglevering, en die eerste term ontbreekt dan.
    // Eerder rekende dit toch door, waarmee "opgewekt" gelijk werd aan wat er
    // naar het net ging en zelfbenutting altijd op nul stond. Beter niets tonen
    // dan een getal dat nergens op slaat.
    const hasSolar = this.meters_().solar.length > 0;
    const totals = {
      solar: hasSolar ? sum("own") + sum("sold") : null,
      used: hasSolar ? sum("used") : null,
      bought: sum("bought"),
      sold: sum("sold"),
    };
    this.metAccu_ = rows.some((row) => Math.abs(row.battery) > 0.001);
    totals.selfUse =
      hasSolar && totals.solar > 0 ? (sum("own") / totals.solar) * 100 : null;
    // Zelfvoorzienend, zoals het energiedashboard van Home Assistant het noemt:
    // welk deel van je verbruik niet van het net kwam. De bewoner van de eerste
    // woning op 22-09-2026: "daar mag zelfvoorzienend nog wel bij."
    // Met een thuisbatterij telt alleen wat er van het net naar het huis ging;
    // wat van het net de batterij in ging telt pas als hij het afgeeft.
    totals.selfSufficient =
      hasSolar && totals.used > 0 ? Math.max(0, (1 - sum("fromGrid") / totals.used) * 100) : null;

    this.paintTotals_(totals);
    this.paintLegend_();

    // De breedte van het tekenvlak zelf, niet die van het scherm: de kaart
    // heeft eigen marges, en meten op het verkeerde element schaalt de hele
    // tekening inclusief de bijschriften mee omlaag.
    const W = Math.max(MIN_W, Math.round(stage.getBoundingClientRect().width) || MIN_W);
    const H = W < 420 ? 200 : 260;
    const BOTTOM = H - BOTTOM_PAD;

    const up = Math.max(...rows.map((row) => row.used), 0.001);
    const down = Math.max(...rows.map((row) => row.sold), 0);
    const span = up + down || 1;
    const zero = TOP + ((up * 1.05) / (span * 1.05)) * (BOTTOM - TOP);
    const scale = (BOTTOM - TOP) / (span * 1.05);

    // Zeven dagen over een breed scherm zou zeven balken van anderhalve
    // centimeter geven. Een balk is een hoeveelheid, geen vlak, dus hij heeft
    // een bovengrens en de rij staat gecentreerd.
    const colW = Math.min(W / rows.length, 64);
    const inset = (W - colW * rows.length) / 2;
    const gap = colW < 9 ? 1 : Math.min(8, colW * 0.22);
    const barW = Math.max(1.5, colW - gap);
    const radius = Math.min(4, barW / 2);

    const bars = rows
      .map((row, index) => {
        const x = inset + index * colW + (colW - barW) / 2;
        // Stacked upwards: bought sits on top of own use, so the bottom of every
        // bar is the part that cost nothing.
        const ownH = row.ownUse * scale;
        const boughtH = row.fromGrid * scale;
        const soldH = row.sold * scale;

        const parts = [];
        if (ownH > 0.4) {
          parts.push(
            `<path class="b own" data-index="${index}" d="${block(x, barW, zero - ownH, ownH, boughtH > 0.4 ? 0 : radius)}"/>`
          );
        }
        if (boughtH > 0.4) {
          parts.push(
            `<path class="b bought" data-index="${index}" d="${block(x, barW, zero - ownH - boughtH, boughtH, radius)}"/>`
          );
        }
        if (soldH > 0.4) {
          parts.push(`<path class="b sold" data-index="${index}" d="${block(x, barW, zero, soldH, radius, true)}"/>`);
        }
        return parts.join("");
      })
      .join("");

    const every = Math.max(1, Math.ceil(rows.length / Math.max(4, Math.floor(W / 46))));
    const ticks = rows
      .map((row, index) =>
        index % every === 0
          ? `<text class="tick" x="${inset + index * colW + colW / 2}" y="${H - 6}" text-anchor="middle">${bucketLabel(
              this.period_,
              row.start
            )}</text>`
          : ""
      )
      .join("");

    const hits = rows
      .map(
        (row, index) =>
          `<rect class="hit" data-index="${index}" x="${inset + index * colW}" y="${TOP}"
                 width="${colW}" height="${BOTTOM - TOP}"/>`
      )
      .join("");

    stage.innerHTML = `
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Verbruik en teruglevering per periode">
        <line class="zero" x1="0" y1="${zero}" x2="${W}" y2="${zero}"/>
        ${bars}
        ${ticks}
        ${hits}
      </svg>
    `;

    // Wijs een balk aan en de cijfers erboven gaan over die ene dag. Dezelfde
    // ruimte, geen zwevend kaartje dat op een telefoon onder je vinger zit.
    this.totals_ = totals;
    this.rowsShown_ = rows;
    const svg = stage.querySelector("svg");
    const at = (event) => {
      const box = svg.getBoundingClientRect();
      const x = ((event.clientX - box.left) / box.width) * W;
      return Math.min(rows.length - 1, Math.max(0, Math.floor((x - inset) / colW)));
    };
    const pick = (index) => {
      const row = rows[index];
      if (!row) return;
      this.paintTotals_(
        {
          solar: row.own + row.sold,
          used: row.used,
          bought: row.bought,
          sold: row.sold,
          selfUse: row.own + row.sold > 0 ? (row.own / (row.own + row.sold)) * 100 : null,
          selfSufficient: row.used > 0 ? Math.max(0, (1 - row.fromGrid / row.used) * 100) : null,
        },
        bucketTitle(this.period_, row.start)
      );
      for (const bar of svg.querySelectorAll(".b")) bar.classList.remove("dim");
      for (const bar of svg.querySelectorAll(`.b:not([data-index="${index}"])`)) bar.classList.add("dim");
    };

    svg.addEventListener("pointerdown", (event) => {
      this.scrubbing_ = true;
      pick(at(event));
    });
    svg.addEventListener("pointermove", (event) => {
      if (this.scrubbing_ || event.pointerType === "mouse") pick(at(event));
    });
    for (const done of ["pointerup", "pointercancel"]) {
      svg.addEventListener(done, () => {
        this.scrubbing_ = false;
      });
    }
    svg.addEventListener("pointerleave", (event) => {
      if (event.pointerType !== "mouse") return;
      this.clearPick_();
    });
  }

  /**
   * Alles wat er in het rapport komt, uitgerekend en al opgemaakt als tekst.
   *
   * De opmaak zelf staat in report.js. Hier gebeurt het rekenwerk en verder
   * niets, zodat een verandering aan de bladspiegel nooit per ongeluk een getal
   * verandert en andersom.
   */
  async reportData_(beknopt = false) {
    const rows = this.rowsShown_ ?? [];
    if (!rows.length) return null;

    // Het beknopte rapport slaat het vermogensdeel over: dat is het lange
    // stuk, en het is niet nodig voor één pagina.
    const vermogen = beknopt ? { samenvatting: null, detail: null } : await this.vermogen_();
    const contract = this.settings_?.contract;

    const prices = this.prices_ ?? new Map();
    const rate = tariff(this.feed_, this.settings_?.contract);
    const hasSolar = this.meters_().solar.length > 0;
    const gas = new Map((this.rows_?.gas ?? []).map((row) => [row.start.getTime(), row.value]));
    const totals = this.totals_ ?? {};

    const woning = (this.settings_?.installation?.home_name ?? "").trim();
    const periode = periodLabel(this.period_, periodStart(this.period_, this.offset_));
    // Er staan twee fijnheden in dit rapport en die zijn niet hetzelfde: de
    // grafiek en Alle cijfers volgen de periode, het verloop volgt wat de klant
    // gekozen heeft. "Per uur" in de kop terwijl er Kwartier aanstond leest als
    // een fout, ook al klopte het over de grafiek. Dus staat er nu bij waar het
    // over gaat.
    const grafiekKorrel = { day: "uur", week: "dag", month: "dag", year: "maand" }[
      this.period_
    ];
    const detailKorrel = KORRELS[this.korrel_id()]?.kop.toLowerCase();
    const korrel =
      detailKorrel && detailKorrel !== grafiekKorrel
        ? `Grafiek per ${grafiekKorrel}, verloop per ${detailKorrel}`
        : `Per ${grafiekKorrel}`;

    const cel = (label, waarde) => ({ label, waarde });

    const kwh = (value) => {
      if (value === null || value === undefined) return "";
      const { value: getal, unit } = energy(value);
      return `${getal} ${unit}`;
    };

    const prijsBij = (row) =>
      contractAt(contract, row.start).period?.all_in_price > 0
        ? contractAt(contract, row.start).buy
        : (prices.get(row.start.getTime()) ?? rate.buy);
    const water = new Map((this.rows_?.water ?? []).map((row) => [row.start.getTime(), row.value]));
    const waarde = (key) =>
      rows.reduce((total, row) => total + row[key] * (prijsBij(row) ?? 0), 0);

    // ---- de tabel per tijdvak ----
    const kop = ["Periode"];
    if (hasSolar) kop.push("Opgewekt", "Verbruikt", "Eigen zon");
    kop.push("Van het net", "Naar het net");
    if (gas.size) kop.push("Gas");
    if (water.size) kop.push("Water");
    if (rate.buy !== null) kop.push("Prijs", "Kosten");

    const regels = rows.map((row) => {
      const prijs = prijsBij(row);
      const cellen = [bucketTitle(this.period_, row.start)];
      if (hasSolar) cellen.push(kwh(row.own + row.sold), kwh(row.used), kwh(row.own));
      cellen.push(kwh(row.bought), kwh(row.sold));
      if (gas.size) cellen.push(`${nl(gas.get(row.start.getTime()) ?? 0, 2)} m³`);
      if (water.size) cellen.push(`${nl(water.get(row.start.getTime()) ?? 0, 2)} m³`);
      if (rate.buy !== null) {
        cellen.push(prijs === null ? "" : euro(prijs), euro(row.bought * (prijs ?? 0)));
      }
      return cellen;
    });

    const som = (key) => rows.reduce((total, row) => total + row[key], 0);
    const totaalCellen = ["Totaal"];
    if (hasSolar) totaalCellen.push(kwh(som("own") + som("sold")), kwh(som("used")), kwh(som("own")));
    totaalCellen.push(kwh(som("bought")), kwh(som("sold")));
    if (gas.size) {
      totaalCellen.push(`${nl([...gas.values()].reduce((a, b) => a + b, 0), 2)} m³`);
    }
    if (water.size) {
      totaalCellen.push(`${nl([...water.values()].reduce((a, b) => a + b, 0), 2)} m³`);
    }
    if (rate.buy !== null) totaalCellen.push("", euro(waarde("bought")));

    // ---- de tabel per apparaat ----
    const apparaten = this.deviceRows_();
    const samen = apparaten.reduce((total, device) => total + device.kwh, 0);
    // Een aandeel heeft alleen betekenis als de delen in het geheel passen.
    // Schattingen uit gemiddeld vermogen kunnen te hoog uitvallen, en dan komt
    // er "172 %" te staan, wat niemand kan plaatsen. Dan liever geen kolom en
    // een zin die zegt waarom.
    const aandeelKlopt = Boolean(totals.used) && samen <= totals.used * 1.02;

    const apparaatKop = ["Apparaat", "Verbruik"];
    if (rate.buy !== null) apparaatKop.push("Kosten");
    if (aandeelKlopt) apparaatKop.push("Aandeel");

    const apparaatRijen = apparaten.map((device) => {
      const cellen = [
        device.exact ? device.label : `${device.label} (bij benadering)`,
        kwh(device.kwh),
      ];
      if (rate.buy !== null) cellen.push(euro(device.euro));
      if (aandeelKlopt) cellen.push(`${Math.round((device.kwh / totals.used) * 100)} %`);
      return cellen;
    });

    const apparaatUitleg =
      "Van apparaten zonder eigen energieteller wordt het verbruik afgeleid uit het " +
      "gemiddelde vermogen. Dat is nauwkeurig genoeg om te zien waar je stroom heen gaat, " +
      "maar het is geen meterstand. Vul bij Apparaten een energieteller in als je die hebt, " +
      "dan klopt het tot op de komma." +
      (aandeelKlopt
        ? ""
        : " Deze schattingen tellen samen op tot meer dan het verbruik van de woning, dus staat er geen aandeel bij.");

    const energieVakjes = [
      hasSolar ? cel("Opgewekt", kwh(totals.solar)) : null,
      hasSolar ? cel("Verbruikt", kwh(totals.used)) : null,
      cel("Van het net", kwh(totals.bought)),
      cel("Naar het net", kwh(totals.sold)),
      totals.selfUse === null || totals.selfUse === undefined
        ? null
        : cel("Zelf gebruikt", `${percent(totals.selfUse).value} %`),
      totals.selfSufficient === null || totals.selfSufficient === undefined
        ? null
        : cel("Zelfvoorzienend", `${percent(totals.selfSufficient).value} %`),
      gas.size
        ? cel("Gas", `${nl([...gas.values()].reduce((a, b) => a + b, 0), 1)} m³`)
        : null,
      water.size
        ? cel("Water", `${nl([...water.values()].reduce((a, b) => a + b, 0), 1)} m³`)
        : null,
    ].filter(Boolean);

    // In geld: dezelfde som als de kaart op het scherm (geld.js), zodat het
    // rapport en Historie het nooit oneens zijn (v0.101.0).
    const g = this.geld_();
    const batterijRegel = g ? this.voorraadRegel_(g) : null;
    const geldVakjes = !g
      ? []
      : [
          cel(g.uitgegeven < 0 ? "Verdiend" : "Uitgegeven", euro(Math.abs(g.uitgegeven))),
          cel("Bespaard", euro(g.bespaard)),
          cel("Stroom van het net", euro(g.stroom)),
          g.metTerug ? cel("Teruglevering", `− ${euro(g.terug)}`) : null,
          g.metGas ? cel("Gas", euro(g.gas)) : null,
          g.metWater ? cel("Water", euro(g.water)) : null,
          batterijRegel ? cel(batterijRegel.naam, batterijRegel.tekst) : null,
          ...this.geldDelen_(g).map((d) => cel(d.naam, euro(d.waarde))),
        ].filter(Boolean);

    const bespaard = this.bespaardRapport_();
    return {
      logoUrl: LOGO_URL,
      woning,
      periode,
      korrel: beknopt ? "Beknopt" : korrel,
      beknopt,
      metZon: hasSolar,
      gemaakt: new Date().toLocaleDateString("nl-NL", {
        day: "numeric",
        month: "long",
        year: "numeric",
      }),
      energie: energieVakjes,
      geld: geldVakjes,
      geldUitleg: g ? this.geldUitleg_(g) : "",
      // Beknopt: de tegels van Bespaard wel, de regels per beurt niet.
      bespaard: beknopt && bespaard ? { ...bespaard, rijen: [] } : bespaard,
      verloop: rows.map((row) => ({
        label: bucketLabel(this.period_, row.start),
        own: row.own,
        bought: row.bought,
        sold: row.sold,
      })),
      apparaten: { kop: apparaatKop, rijen: apparaatRijen, uitleg: apparaatUitleg },
      vermogen: vermogen.samenvatting,
      vermogenDetail: vermogen.detail,
      cijfers: beknopt ? null : { kop, rijen: regels, totaal: totaalCellen },
    };
  }

  /**
   * Welke sensoren er in het vermogensdeel horen, met hun naam.
   *
   * Het net, de zon en elk apparaat dat de klant gekoppeld heeft. Precies wat
   * hij zelf heeft ingevuld, in de volgorde waarin hij ernaar kijkt.
   */
  vermogenBronnen_() {
    const bronnen = this.settings_?.sources ?? {};
    const namen = deviceLabelMap(this.settings_?.devices ?? []);
    return [
      ...netBronnen(bronnen),
      { entity: bronnen.solar, label: "Zon" },
      ...(Array.isArray(bronnen.solar_extra) ? bronnen.solar_extra : [])
        .filter(Boolean)
        .map((entity, i) => ({ entity, label: `Zon ${i + 2}` })),
      ...(this.settings_?.devices ?? []).map((device) => ({
        entity: device.entity,
        label: namen.get(device.id) ?? deviceLabel(device),
      })),
    ].filter((rij) => rij.entity);
  }

  /**
   * Het vermogensdeel van het rapport: een samenvatting en de tabellen erachter.
   *
   * Een som in kWh zegt hoeveel er door de meter ging; dit zegt hoe hard het op
   * zijn zwaarst ging, en dat is een andere vraag. Een huis dat over een dag
   * netjes binnen zijn aansluiting blijft kan er om zeven uur 's avonds vlak
   * tegenaan hebben gezeten, en dat is precies wat er niet in een dagtotaal te
   * zien is.
   *
   * Twee lagen, want dat zijn twee verschillende vragen. De samenvatting is
   * "hoe zwaar was deze periode": één regel per apparaat. Daarachter staat het
   * verloop: per tijdvak het laagste, het gemiddelde en de piek, per apparaat
   * een eigen tabel.
   *
   * De fijnheid volgt de gekozen periode, net als bij Alle cijfers. Op een dag
   * is dat het kwartier waarin het bewaard wordt; over een maand zouden dat
   * bijna drieduizend regels zijn en dat is geen rapport meer maar een
   * gegevensbestand.
   */
  async vermogen_() {
    const wilde = this.vermogenBronnen_();
    if (!wilde.length) return { samenvatting: null, detail: null };

    const start = periodStart(this.period_, this.offset_);
    const gevonden = await quarters(
      this.hass_,
      wilde.map((rij) => rij.entity),
      start,
      periodEnd(this.period_, start)
    );

    // Een meter die andersom telt wordt hier rechtgezet, en niet verderop:
    // daarachter rekenen de samenvatting en het verloop allebei met dezelfde
    // rijen, en dan kan er maar een van de twee vergeten worden.
    for (const rij of wilde) {
      if (rij.omkeren) gevonden.set(rij.entity, omgekeerd(gevonden.get(rij.entity)));
    }

    return {
      samenvatting: this.vermogenSamenvatting_(wilde, gevonden),
      detail: this.vermogenDetail_(wilde, gevonden),
    };
  }

  /**
   * Wat het teken bij Het net betekent, als deze woning er een heeft.
   *
   * Bij twee losse meters staat het al in de namen: van het net en naar het
   * net. Bij een meter met een teken is er een regel en zegt het teken de
   * richting, en dan hoort er bij te staan welke.
   */
  tekenUitleg_() {
    return this.settings_?.sources?.grid_mode === "signed"
      ? " Bij Het net is een plus wat er van het net kwam en een min wat er naartoe ging."
      : "";
  }

  /** Eén regel per apparaat: hoe zwaar was deze periode. */
  vermogenSamenvatting_(wilde, gevonden) {
    const rijen = [];
    for (const { entity, label } of wilde) {
      const vat = samenvatting(gevonden.get(entity));
      if (!vat) continue;
      rijen.push([
        label,
        watt(vat.laagste),
        watt(vat.gemiddeld),
        watt(vat.piek),
        vat.piekOp ? piekMoment(this.period_, vat.piekOp) : "",
      ]);
    }
    if (!rijen.length) return null;

    return {
      kop: ["", "Laagste", "Gemiddeld", "Piek", "Piek op"],
      rijen,
      uitleg:
        "Per kwartier wordt het laagste, het gemiddelde en de piek bewaard, twee jaar lang. " +
        "De piek is de hoogste waarde die de sensor zelf gemeld heeft, dus zo scherp als je " +
        "meter meet. Het gemiddelde weegt naar tijd en niet naar het aantal metingen. " +
        "Deze geschiedenis begint op de dag dat de coach hem is gaan bijhouden; wat daarvoor " +
        "ligt is overgenomen uit Home Assistant voor zover dat er nog was." +
        this.tekenUitleg_(),
    };
  }

  /** Het verloop per tijdvak, met per apparaat een eigen tabel. */
  vermogenDetail_(wilde, gevonden) {
    const korrel = KORRELS[this.korrel_id()];
    if (!korrel) return null;

    const tabellen = [];
    for (const { entity, label } of wilde) {
      const rijen = [];
      for (const vak of vakken(gevonden.get(entity) ?? [], korrel)) {
        rijen.push([
          korrel.label(vak.start),
          watt(vak.laagste),
          watt(vak.gemiddeld),
          watt(vak.piek),
        ]);
      }
      if (rijen.length) tabellen.push({ naam: label, rijen });
    }
    if (!tabellen.length) return null;

    return {
      korrel: korrel.kop,
      kop: [korrel.kop, "Laagste", "Gemiddeld", "Piek"],
      tabellen,
      uitleg: korrel.uitleg + this.tekenUitleg_(),
    };
  }

  /**
   * Het rapport als pdf, en dan het bestand naar de klant toe.
   *
   * Het ging eerst via het afdrukvenster van de browser. Dat werkt op een pc,
   * maar op een telefoon niet: in de app van Home Assistant bestaat dat venster
   * niet en op iOS werkt afdrukken vanuit een frame sowieso niet. Nu wordt de
   * pdf zelf gemaakt, zie pdf.js, en gaat hij als bestand naar buiten. Daarmee
   * werkt het op elk apparaat op dezelfde manier.
   */
  async report_(beknopt = false) {
    const knop = this.$("#rapport-knop");
    if (knop?.disabled) return;

    const gegevens = await this.reportData_(beknopt);
    if (!gegevens) return;

    const label = knop?.querySelector("span");
    const oud = label?.textContent;
    if (knop) knop.disabled = true;
    if (label) label.textContent = "Bezig";

    try {
      const blob = await reportPdf(gegevens);
      const naam = `DomotiApp Coach ${gegevens.periode}${beknopt ? " (beknopt)" : ""}.pdf`.replace(/[\\/:*?"<>|]/g, "-");
      const uitkomst = await this.bezorg_(blob, naam);
      if (label && uitkomst === "mislukt") label.textContent = "Niet gelukt";
      else if (label) label.textContent = oud;
    } catch (fout) {
      console.error("[DomotiApp Coach] het rapport kon niet gemaakt worden", fout);
      if (label) label.textContent = "Niet gelukt";
    } finally {
      if (knop) knop.disabled = false;
      // Een knop die "Niet gelukt" blijft zeggen is na een minuut alleen nog
      // maar in de weg, dus die komt vanzelf weer terug op zijn eigen woord.
      if (label && label.textContent !== oud) {
        setTimeout(() => {
          label.textContent = oud;
        }, 4000);
      }
    }
  }

  /**
   * De pdf bij de klant krijgen.
   *
   * Langs Home Assistant en niet rechtstreeks uit de browser. Het paneel maakt
   * de pdf hier ter plekke, dus een downloadkoppeling naar een `blob:` lag voor
   * de hand, en op een computer werkt dat ook. In de Home Assistant app niet:
   * dat is een webweergave en geen browser, en die kan zo'n adres niet zelf
   * ophalen. Er kwam dan wel een bestand uit, maar het ging niet open.
   *
   * Via de omweg wordt het een gewoon webadres met een gewone pdf erachter, en
   * dat kan elk apparaat aan. Lukt de omweg niet, dan alsnog rechtstreeks: op
   * een computer is dat prima, en een rapport dat je niet krijgt is slechter
   * dan een rapport dat langs de oude weg komt.
   *
   * Met een koppeling en niet met `location.assign`. Dat laatste navigeert de
   * hele pagina weg, en op een computer valt dat niet op omdat de download
   * meteen begint en de pagina blijft staan. In de Home Assistant app wel: daar
   * ging het paneel eraan en bleef het logo staan met "clean cache and reload"
   * eronder. Een koppeling die zijn eigen venster opent laat het paneel met
   * rust.
   */
  async bezorg_(blob, naam) {
    try {
      const { url } = await this.hass_.callWS({
        type: "domotiapp_coach/report/store",
        pdf: await base64Van(blob),
        filename: naam,
      });
      if (url) {
        const link = document.createElement("a");
        link.href = url;
        link.download = naam;
        link.target = "_blank";
        link.rel = "noopener";
        link.style.display = "none";
        document.body.appendChild(link);
        link.click();
        link.remove();
        return "gedownload";
      }
    } catch (fout) {
      console.warn("[DomotiApp Coach] rapport kon niet via Home Assistant, nu rechtstreeks", fout);
    }
    return afleveren(blob, naam);
  }

  /** Wat elk apparaat deze periode verbruikte, van groot naar klein. */
  deviceRows_() {
    const stats = this.devices_ ?? new Map();
    if (!stats.size) return [];

    const prices = this.prices_ ?? new Map();
    const rate = tariff(this.feed_, this.settings_?.contract);
    const labels = deviceLabelMap(this.settings_?.devices);
    // In de vakken van de grafiek, zodat elk vak zijn eigen prijs krijgt: een
    // schatting uit het vermogen komt sinds v0.121.0 per uur (`fetchDevices`).
    const tijden = this.rows_ ? this.buckets_().map((row) => row.start.getTime()) : [];
    const einde = periodEnd(this.period_, periodStart(this.period_, this.offset_)).getTime();

    return (this.settings_?.devices ?? [])
      .map((device) => {
        const found = stats.get(device.id);
        if (!found) return null;

        const paren = tijden.length
          ? perVak(found.rows, tijden, einde).map((value, i) => [tijden[i], value])
          : [...found.rows];
        let kwh = 0;
        let cost = 0;
        for (const [time, value] of paren) {
          kwh += value;
          cost += value * (prices.get(time) ?? rate.buy ?? 0);
        }
        return { label: labels.get(device.id) ?? deviceLabel(device), kwh, euro: cost, exact: found.exact };
      })
      .filter((row) => row && row.kwh > 0.01)
      .sort((a, b) => b.kwh - a.kwh);
  }

  /** Terug naar de cijfers van de hele periode. */
  clearPick_() {
    if (this.totals_) this.paintTotals_(this.totals_);
    for (const bar of this.$$("#stage .b")) bar.classList.remove("dim");
  }

  paintTotals_(totals, title) {
    this.$("#totals-title").textContent = title ?? "";

    const rows = [];
    if (totals.solar !== null) {
      rows.push({ label: "Opgewekt", value: energy(totals.solar), tone: "var(--dac-solar)" });
      rows.push({ label: "Verbruikt", value: energy(totals.used), tone: "var(--dac-house)" });
    }
    rows.push({ label: "Van het net", value: energy(totals.bought), tone: "var(--dac-grid-in)" });
    rows.push({ label: "Naar het net", value: energy(totals.sold), tone: "var(--dac-grid-out)" });
    // Eén percentage en niet twee (v0.116.0): "Zelf gebruikt" en
    // "Zelfvoorzienend" naast elkaar leken op hetzelfde. Dit is het deel van je
    // verbruik dat je zelf opwekte; het andere staat in het rapport.
    if (totals.selfSufficient !== null && totals.selfSufficient !== undefined) {
      rows.push({ label: "Zelfvoorzienend", value: percent(totals.selfSufficient), tone: "var(--dac-good)" });
    }

    this.$("#totals").replaceChildren(
      ...rows.map((row) => {
        const cell = document.createElement("div");
        cell.className = "total";
        cell.style.setProperty("--tone", row.tone);

        const label = document.createElement("span");
        label.className = "t-label";
        label.textContent = row.label;

        const value = document.createElement("span");
        value.className = "t-value";
        value.textContent = row.value.value;

        const unit = document.createElement("span");
        unit.className = "t-unit";
        unit.textContent = row.value.unit;

        value.append(unit);
        cell.append(label, value);
        return cell;
      })
    );
  }

  paintLegend_() {
    const entries = [
      { tone: "var(--dac-solar)", label: this.metAccu_ ? "Eigen zon en batterij" : "Eigen zon gebruikt" },
      { tone: "var(--dac-grid-in)", label: "Van het net" },
      { tone: "var(--dac-grid-out)", label: "Naar het net" },
    ];

    this.$("#legend").replaceChildren(
      ...entries.map((entry) => {
        const item = document.createElement("span");
        const swatch = document.createElement("i");
        swatch.style.background = entry.tone;
        item.append(swatch, document.createTextNode(` ${entry.label}`));
        return item;
      })
    );
  }

  /**
   * The same period in euros.
   *
   * Only the parts that can be worked out from what the customer filled in. The
   * big one is the sun they used themselves: every kilowatt-hour off their own
   * roof is one they did not have to buy, and it is worth far more than the
   * same kilowatt-hour exported, which is exactly what makes using it worth
   * anything at all.
   *
   * No tariff history is kept anywhere, so a dynamic contract is reckoned with
   * today's average and the screen says so. Guessing at what a kilowatt-hour
   * cost last February would put a precise-looking number on nothing.
   */
  /**
   * Bespaard voor in het rapport: de vakjes, de uitleg en een tabel per beurt.
   * Alleen als de beurten al opgehaald zijn en er iets in de periode valt;
   * anders komt het hoofdstuk niet in het rapport.
   */
  bespaardRapport_() {
    if (!Array.isArray(this.beurten_)) return null;
    const { items, totaal } = this.bespaard_();
    if (!items.length) return null;
    const kwh = (value) => {
      const { value: getal, unit } = energy(value);
      return `${getal} ${unit}`;
    };
    const wanneer = (b) => {
      const t = new Date(b.plugged_at);
      if (Number.isNaN(t.getTime())) return "";
      return `${String(t.getDate()).padStart(2, "0")}-${String(t.getMonth() + 1).padStart(2, "0")} ${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
    };
    const w = woorden(items);
    const metAccu = totaal.battery_kwh >= 0.05;
    return {
      vakjes: [
        { label: "Bespaard", waarde: euro(totaal.saved) },
        { label: "Door de zon", waarde: euro(totaal.solar_saved) },
        { label: "Door te wachten", waarde: euro(totaal.wait_saved) },
        { label: "Betaald", waarde: euro(totaal.paid) },
        { label: w.hoeveel, waarde: kwh(totaal.kwh) },
        { label: "Waarvan zon", waarde: kwh(totaal.solar_kwh) },
        ...(metAccu ? [{ label: "Uit je thuisbatterij", waarde: kwh(totaal.battery_kwh) }] : []),
      ],
      uitleg:
        w.uitleg +
        (totaal.onbekend
          ? ` ${totaal.onbekend === 1 ? "Eén beurt telt" : `${totaal.onbekend} beurten tellen`} niet mee in het geld, omdat de prijs toen niet bekend was.`
          : ""),
      kop: [w.wanneer, "Apparaat", w.hoeveel, "Zon", ...(metAccu ? ["Accu"] : []), w.vanaf, "Betaald", "Bespaard", "Door zon"],
      rijen: items.map((b) => [
        wanneer(b),
        b.car ? `${b.name}, ${b.car}` : b.name,
        kwh(b.kwh),
        kwh(b.solar_kwh),
        ...(metAccu ? [kwh(Number(b.battery_kwh) || 0)] : []),
        b.ref_cost === null || b.ref_cost === undefined ? "" : euro(b.ref_cost),
        euro(b.paid),
        b.saved === null || b.saved === undefined ? "" : euro(b.saved),
        delen(b).zon === null ? "" : euro(delen(b).zon),
      ]),
      totaal: [
        "Totaal", "", kwh(totaal.kwh), kwh(totaal.solar_kwh), ...(metAccu ? [kwh(totaal.battery_kwh)] : []),
        euro(totaal.ref_cost), euro(totaal.paid), euro(totaal.saved), euro(totaal.solar_saved),
      ],
    };
  }

  /** De laadbeurten ophalen, één keer; daarna leeft de lijst mee met de periode. */
  async laadBeurten_() {
    if (this.beurten_ !== undefined || !this.hass_?.callWS) return;
    this.beurten_ = null;
    try {
      this.beurten_ = await this.hass_.callWS({ type: "domotiapp_coach/savings/list" });
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de laadbeurten niet laden", error);
      this.beurten_ = [];
    }
    this.paint_();
  }

  /** De beurten van de gekozen periode en wat ze samen bespaarden. */
  bespaard_() {
    const start = periodStart(this.period_, this.offset_);
    const end = periodEnd(this.period_, start);
    const items = beurtenIn(this.beurten_ ?? [], start, end);
    return { items, totaal: totalen(items), apparaten: perApparaat(items) };
  }

  /**
   * Beurten (heette Bespaard tot v0.116.0): wat de coach per beurt scheelde.
   *
   * De eigenaar op 13-10-2026: "Het moet niet zo zijn dat het gigantisch veel
   * wordt alle data dat mensen het niet meer snappen." Daarom drie tegels in
   * plaats van zeven, met de uitsplitsing eronder in kleine letters, en één lijst
   * met vijf kolommen in plaats van twee tabellen met acht. Wat zon, batterij en
   * het ijkpunt per beurt waren staat in het uitgebreide rapport.
   */
  paintSaved_() {
    const note = this.$("#saved-note");
    const tegels = this.$("#saved-totals");
    const lijst = this.$("#saved-list");
    tegels.replaceChildren();
    lijst.replaceChildren();

    if (this.beurten_ === undefined || this.beurten_ === null) {
      note.textContent = "Bezig met ophalen…";
      return;
    }
    const { items, totaal } = this.bespaard_();
    if (!items.length) {
      note.textContent = this.beurten_.length
        ? "Geen beurten in deze periode."
        : "Nog geen beurten. Vanaf de eerstvolgende staat hier wat hij kostte en bespaarde.";
      return;
    }

    const tegel = (label, value, tone, sub = "") => {
      const box = document.createElement("div");
      box.className = "total";
      if (tone) box.style.setProperty("--tone", tone);
      const l = document.createElement("span");
      l.className = "t-label";
      l.textContent = label;
      const v = document.createElement("span");
      v.className = "t-value";
      v.textContent = value;
      box.append(l, v);
      if (sub) {
        const o = document.createElement("span");
        o.className = "t-sub";
        o.textContent = sub;
        box.append(o);
      }
      return box;
    };
    const kwh = (value) => {
      const { value: getal, unit } = energy(value);
      return `${getal} ${unit}`;
    };
    // De woorden naar wat er in de lijst staat: een auto wordt ingeplugd en
    // geladen, een vaatwasser vrijgegeven en verbruikt. De eigenaar op 07-09-2026.
    const w = woorden(items);
    const metAccu = totaal.battery_kwh >= 0.05;
    // Wat er bespaard is, en daarvan wat de zon deed en wat het wachten op een
    // goedkoper moment (de eigenaar op 09-09-2026); waar de stroom vandaan kwam
    // (op 28-09-2026: "moet daar niet iets van de batterij bij?").
    tegels.append(
      tegel("Bespaard", euro(totaal.saved), "var(--dac-solar)",
        `${euro(totaal.solar_saved)} door zon, ${euro(totaal.wait_saved)} door wachten`),
      tegel("Betaald", euro(totaal.paid), "var(--dac-grid-in)"),
      tegel(w.hoeveel, kwh(totaal.kwh), "",
        `${kwh(totaal.solar_kwh)} zon${metAccu ? `, ${kwh(totaal.battery_kwh)} uit de batterij` : ""}`)
    );

    // De eigenaar op 13-10-2026: "leg eens beurten uit dat snap ik niet."
    const zinnen = ["Een beurt is één keer dat de coach een apparaat liet draaien, zoals de auto laden of de vaatwasser.", w.uitleg];
    if (metAccu) zinnen.push("Stroom uit de batterij telt als netstroom, zodat niets dubbel telt.");
    if (totaal.onbekend) {
      zinnen.push(
        `${totaal.onbekend === 1 ? "Eén beurt telt" : `${totaal.onbekend} beurten tellen`} niet mee: de prijs was niet bekend.`
      );
    }
    if (totaal.lopend) zinnen.push("Een beurt die nog loopt telt mee tot nu.");
    note.textContent = zinnen.join(" ");

    const rij = (cellen, kop = false) => {
      const tr = document.createElement("tr");
      for (const cel of cellen) {
        const td = document.createElement(kop ? "th" : "td");
        td.textContent = cel;
        tr.append(td);
      }
      return tr;
    };
    const wanneer = (b) => {
      const t = new Date(b.plugged_at);
      if (Number.isNaN(t.getTime())) return "";
      const dag = `${String(t.getDate()).padStart(2, "0")}-${String(t.getMonth() + 1).padStart(2, "0")}`;
      const klok = `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
      return this.period_ === "day" ? klok : `${dag} ${klok}`;
    };
    lijst.append(rij([w.wanneer, "Apparaat", w.hoeveel, "Betaald", "Bespaard"], true));
    for (const b of items) {
      const extra = opmerking(b);
      lijst.append(
        rij([
          wanneer(b),
          `${b.car ? `${b.name}, ${b.car}` : b.name}${extra ? ` (${extra})` : ""}`,
          kwh(b.kwh),
          euro(b.paid),
          b.saved === null || b.saved === undefined ? "" : euro(b.saved),
        ])
      );
    }
  }

  /**
   * De som van In geld voor de getoonde periode, zoals het scherm en het rapport
   * hem allebei gebruiken. Zie geld.js.
   */
  geld_() {
    const rows = this.rowsShown_ ?? [];
    const contract = this.settings_?.contract;
    const rate = tariff(this.feed_, contract);
    if (!rows.length || rate.buy === null) return null;
    const prices = this.prices_ ?? new Map();
    const start = periodStart(this.period_, this.offset_);
    const end = periodEnd(this.period_, start);
    const beurten = Array.isArray(this.beurten_) ? beurtenIn(this.beurten_, start, end) : [];
    const accu = accuVerdiend(this.settings_, start, end);
    const zonInAccu = accuZon(this.settings_, start, end);
    return {
      rate,
      start,
      end,
      prices,
      accuDagen: accu.dagen,
      metAccu: (this.settings_?.devices ?? []).some((d) => d.type === "thuisbatterij"),
      metCoach: (this.settings_?.devices ?? []).some((d) => d.controllable && d.type !== "thuisbatterij"),
      beurtenGeladen: Array.isArray(this.beurten_),
      ...balans({
        rijen: rows,
        prijs: (when) => prijsOp(contract, rate, prices, when),
        gas: this.rows_?.gas ?? [],
        water: this.rows_?.water ?? [],
        contract,
        accu: accu.euro,
        accuVoorraad: accu.voorraad,
        accuZon: zonInAccu.euro,
        coach: totalen(beurten),
      }),
    };
  }

  /** De delen van bespaard, in de volgorde en kleur van de balk. */
  geldDelen_(g) {
    const heeftZon = this.meters_().solar.length > 0;
    return [
      heeftZon ? { naam: "Door je zon", waarde: g.delen.zon, tone: "var(--dac-solar)" } : null,
      g.metAccu ? { naam: "Door je thuisbatterij", waarde: g.delen.accu, tone: "var(--dac-good)" } : null,
      g.metCoach ? { naam: "Door de coach", waarde: g.delen.coach, tone: "var(--dac-accent-hi)" } : null,
    ].filter(Boolean);
  }

  paintMoney_() {
    const card = this.$("#money-card");
    const g = this.geld_();
    if (!g) {
      card.hidden = true;
      return;
    }
    card.hidden = false;
    const vandaag = this.period_ === "day" && this.offset_ === 0;
    this.$("#money-title").textContent = vandaag
      ? "Wat vandaag tot nu kostte en opleverde"
      : `Wat deze ${{ day: "dag", week: "week", month: "maand", year: "periode" }[this.period_]} kostte en opleverde`;

    // Twee getallen bovenaan. Levert teruglevering meer op dan de rest kost,
    // dan heet het verdiend: een minteken voor een euroteken leest als een fout.
    const kop = (label, waarde, uitleg, tone) => {
      const box = document.createElement("div");
      box.className = "geld-getal";
      box.style.setProperty("--tone", tone);
      const l = document.createElement("span");
      l.className = "t-label";
      l.textContent = label;
      const v = document.createElement("span");
      v.className = "geld-waarde";
      v.textContent = euro(waarde);
      const u = document.createElement("span");
      u.className = "geld-uitleg";
      u.textContent = uitleg;
      box.append(l, v, u);
      return box;
    };
    const bespaardDelen = this.geldDelen_(g);
    const verdiend = g.uitgegeven < 0;
    const wat = [g.metGas ? "gas" : null, g.metWater ? "water" : null].filter(Boolean);
    const door = bespaardDelen.map((d) => d.naam.replace(/^Door (je )?/, ""));
    const hero = [
      kop(
        verdiend ? "Verdiend" : "Uitgegeven",
        Math.abs(g.uitgegeven),
        `stroom${wat.length ? `, ${wat.join(" en ")}` : ""}${g.metTerug ? ", min wat teruglevering opbracht" : ""}`,
        verdiend ? "var(--dac-good)" : "var(--dac-grid-in)"
      ),
      kop(
        "Bespaard",
        g.bespaard,
        door.length ? `door ${door.length > 1 ? `${door.slice(0, -1).join(", ")} en ${door.at(-1)}` : door[0]}` : "",
        "var(--dac-solar)"
      ),
    ];
    // Een derde getal "Zonder zon, batterij en coach" stond hier tot v0.116.0;
    // dat is Uitgegeven plus Bespaard, en de balk eronder laat het al zien.
    this.$("#money-hero").replaceChildren(...hero);

    // De balk: wat het gekost had, verdeeld in wat je uitgaf en wat er bespaard
    // werd. Alleen als alle delen positief zijn; een negatief deel valt niet te
    // tekenen zonder te liegen over de lengte.
    // Wat er aan stroom in de batterij bij kwam is uitgegeven maar nog niet
    // gebruikt, en telt pas bij Bespaard als het eruit gaat (v0.107.0). In de
    // balk staat daarom wat je uitgaf aan wat je gebruikte, zodat hij precies
    // op "Zonder" uitkomt.
    const metVoorraad = Math.abs(g.voorraad) >= 0.005;
    const stukken = [
      {
        naam: metVoorraad ? "Uitgegeven aan wat je gebruikte" : "Uitgegeven",
        waarde: g.uitgegeven - g.voorraad,
        tone: "var(--dac-grid-in)",
      },
      ...bespaardDelen,
    ];
    const balk = this.$("#money-bar");
    const totaal = stukken.reduce((som, d) => som + d.waarde, 0);
    if (stukken.every((d) => d.waarde >= 0) && totaal > 0.005) {
      balk.hidden = false;
      balk.setAttribute("aria-label", stukken.map((d) => `${d.naam} ${euro(d.waarde)}`).join(", "));
      balk.replaceChildren(
        ...stukken
          .filter((d) => d.waarde / totaal >= 0.004)
          .map((d) => {
            const stuk = document.createElement("i");
            stuk.style.setProperty("--tone", d.tone);
            stuk.style.flexGrow = String(d.waarde);
            stuk.title = `${d.naam}: ${euro(d.waarde)}`;
            return stuk;
          })
      );
    } else {
      balk.hidden = true;
      balk.replaceChildren();
    }

    // Twee kolommen: waar het geld heen ging, en waardoor er bespaard werd.
    const kolom = (kopTekst, regels) => {
      const box = document.createElement("div");
      box.className = "geld-kolom";
      const h = document.createElement("div");
      h.className = "t-label";
      h.textContent = kopTekst;
      box.append(h);
      for (const r of regels) {
        const rij = document.createElement("div");
        rij.className = "geld-regel";
        const bol = document.createElement("i");
        bol.style.setProperty("--tone", r.tone);
        const n = document.createElement("span");
        n.textContent = r.naam;
        const v = document.createElement("span");
        v.className = "geld-bedrag";
        v.textContent = r.tekst;
        rij.append(bol, n, v);
        box.append(rij);
      }
      return box;
    };
    const uit = [{ naam: "Stroom van het net", tekst: euro(g.stroom), tone: "var(--dac-grid-in)" }];
    if (g.metTerug) uit.push({ naam: "Teruglevering", tekst: `− ${euro(g.terug)}`, tone: "var(--dac-grid-out)" });
    if (g.metGas) uit.push({ naam: "Gas", tekst: euro(g.gas), tone: "var(--dac-warn)" });
    if (g.metWater) uit.push({ naam: "Water", tekst: euro(g.water), tone: "var(--dac-grid-in)" });
    const batterijRegel = this.voorraadRegel_(g);
    if (batterijRegel) uit.push({ ...batterijRegel, tone: "var(--dac-ink-3)" });
    const bij = bespaardDelen.map((d) => ({ naam: d.naam, tekst: euro(d.waarde), tone: d.tone }));
    this.$("#money-parts").replaceChildren(
      kolom(verdiend ? "Verdiend" : "Uitgegeven", uit),
      ...(bij.length ? [kolom("Bespaard", bij)] : [])
    );

    this.$("#money-note").textContent = this.geldUitleg_(g);
  }

  /**
   * Wat er aan stroom in de thuisbatterij bij kwam of uit ging, als regel onder
   * Uitgegeven, of null. Laden is inkopen (v0.107.0): betaald, maar pas bij
   * Bespaard als ze ontlaadt.
   */
  voorraadRegel_(g) {
    if (!g.metAccu || Math.abs(g.voorraad) < 0.005) return null;
    return g.voorraad > 0
      ? { naam: "Waarvan nog in je batterij", tekst: euro(g.voorraad) }
      : { naam: "En uit je batterij, eerder betaald", tekst: euro(-g.voorraad) };
  }

  /** Hoe hard de getallen van In geld zijn, en waar ze vandaan komen. Ook voor het rapport. */
  /**
   * De uitleg onder In geld: per zin één ding, zo kort als het kan. De eigenaar
   * op 13-10-2026, na een alinea van zes zinnen waarin hij niet terugvond waarom
   * de batterij op € 0,00 stond: "ik wil alles zo duidelijk mogelijk hebben en
   * zo kort mogelijk." Met salderen staat erbij wat opslaan per kWh scheelt,
   * want dat is het antwoord op die vraag.
   */
  geldUitleg_(g) {
    const rate = g.rate;
    const perBucket = g.prices.size > 0;
    const vast = rate.basis === "je vaste tarief";
    const contract = this.settings_?.contract;
    const rijen = this.rowsShown_ ?? [];
    const zinnen = ["Bespaard is wat alles van het net gekost had, min wat je betaalde."];
    zinnen.push(
      vast
        ? `Stroom kost ${euro(rate.buy)} per kWh.`
        : perBucket
          ? this.period_ === "day"
            ? "Gerekend met de prijs van elk uur."
            : `Gerekend met ${this.period_ === "year" ? "maandgemiddelden" : "daggemiddelden"} van de prijs, dus ongeveer.`
          : `Gerekend met ${rate.basis}, ${euro(rate.buy)} per kWh.`
    );
    if (rijen.some((r) => salderen(contract, r.start))) {
      const p = prijsOp(contract, rate, g.prices, g.start);
      const jaar = SALDEREN_TOT.slice(0, 4);
      zinnen.push(
        p.terug !== null && p.koop !== null
          ? `Tot 1 januari ${jaar} saldeer je: terugleveren levert ${euro(p.terug)} per kWh op, dus zelf gebruiken of opslaan scheelt maar ${euro(p.koop - p.terug)} per kWh.`
          : `Tot 1 januari ${jaar} saldeer je: zelf gebruiken of opslaan scheelt dan alleen de terugleverkosten.`
      );
    }
    if (rijen.some((row) => contractAt(contract, row.start).period)) {
      zinnen.push("Dagen in een eerder contract rekenen met dat contract.");
    }
    if (g.metAccu) {
      zinnen.push(
        g.accuDagen
          ? "Thuisbatterij: wat ontladen opbracht, min wat het laden kostte. Wat er nog in zit staat bij Uitgegeven."
          : "Thuisbatterij: telt vanaf de dag dat de coach haar volgt."
      );
    }
    if (g.metCoach) {
      zinnen.push(
        g.beurtenGeladen
          ? "Coach: zon naar een apparaat sturen en wachten op een goedkoper moment."
          : "Wat de coach bespaarde wordt nog opgehaald."
      );
    }
    if (!g.metTerug) {
      zinnen.push("Wat terugleveren opbrengt ontbreekt: uit een all-in prijs is de marktprijs niet te halen.");
    }
    if (g.onbekend) zinnen.push("Van een deel van de periode is de prijs niet bekend; dat deel telt niet mee.");
    return zinnen.join(" ");
  }

  /**
   * Per apparaat (v0.121.0): gestapelde balken over dezelfde vakken als de
   * grafiek erboven, en een lijst met per apparaat zijn kWh en zijn deel van
   * wat het huis verbruikte. Aanwijzen zet de lijst op dat ene vak, zoals de
   * kop bij gas. Wat de apparaten samen niet verklaren staat onderaan als
   * "Rest van het huis", net als het niet-gemeten verbruik in Home Assistant.
   */
  paintApparaten_() {
    const card = this.$("#apparaten-card");
    if (!card) return;
    const vakken = this.buckets_();
    const tijden = vakken.map((row) => row.start.getTime());
    const einde = periodEnd(this.period_, periodStart(this.period_, this.offset_)).getTime();
    const reeksen = apparaatReeksen(this.settings_?.devices, this.devices_, tijden, einde);
    card.hidden = !tijden.length || !reeksen.length;
    if (card.hidden) return;

    // Het verbruik van het huis is er alleen met een opwekteller (`paintChart_`).
    const huis = this.meters_().solar.length > 0 ? vakken.map((row) => row.used) : null;
    this.appReeksen_ = reeksen;
    this.appHuis_ = huis;
    this.$("#apparaten-titel").textContent = "Wat je apparaten verbruikten";
    this.paintAppLijst_(null);

    const stage = this.$("#apparaten-stage");
    const W = Math.max(MIN_W, Math.round(stage.getBoundingClientRect().width) || MIN_W);
    const H = W < 420 ? 160 : 200;
    const BOTTOM = H - BOTTOM_PAD;
    const som = tijden.map((_, i) => reeksen.reduce((totaal, reeks) => totaal + reeks.vakken[i], 0));
    const top = Math.max(...som, 0.001);
    const colW = Math.min(W / tijden.length, 64);
    const inset = (W - colW * tijden.length) / 2;
    const barW = Math.max(1.5, colW - (colW < 9 ? 1 : Math.min(8, colW * 0.22)));
    const schaal = (BOTTOM - 8) / (top * 1.05);
    // Twee pixels lucht tussen de stukken van een balk, zodat twee buren met
    // een kleur die op elkaar lijkt toch twee stukken blijven.
    const GAT = 2;

    const balken = tijden
      .map((_, i) => {
        const x = inset + i * colW + (colW - barW) / 2;
        let y = BOTTOM;
        const delen = reeksen.filter((reeks) => reeks.vakken[i] * schaal > 0.4);
        const stukken = delen.map((reeks, d) => {
          const h = reeks.vakken[i] * schaal;
          y -= h;
          const kleur = reeks.kleur === "rest" ? "var(--dac-app-rest)" : `var(--dac-app-${reeks.kleur})`;
          const zicht = h > GAT + 1 ? h - GAT : h;
          // Alleen de bovenste krijgt de ronde kop, de rest staat er recht op.
          return d === delen.length - 1
            ? `<path d="${block(x, barW, y, zicht, Math.min(4, barW / 2))}" fill="${kleur}"/>`
            : `<rect x="${x.toFixed(1)}" y="${(y + GAT).toFixed(1)}" width="${barW.toFixed(1)}" height="${Math.max(0.5, zicht).toFixed(1)}" fill="${kleur}"/>`;
        });
        return stukken.length ? `<g class="b app">${stukken.join("")}</g>` : `<g class="b app"></g>`;
      })
      .join("");

    const every = Math.max(1, Math.ceil(tijden.length / Math.max(4, Math.floor(W / 46))));
    const ticks = vakken
      .map((row, index) =>
        index % every === 0
          ? `<text class="tick" x="${inset + index * colW + colW / 2}" y="${H - 6}" text-anchor="middle">${bucketLabel(this.period_, row.start)}</text>`
          : ""
      )
      .join("");
    const hits = tijden
      .map((_, index) => `<rect class="hit" data-index="${index}" x="${inset + index * colW}" y="0" width="${colW}" height="${BOTTOM}"/>`)
      .join("");

    stage.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Verbruik per apparaat">${balken}${ticks}${hits}</svg>`;

    const svg = stage.querySelector("svg");
    const at = (event) => {
      const box = svg.getBoundingClientRect();
      const x = ((event.clientX - box.left) / box.width) * W;
      return Math.min(tijden.length - 1, Math.max(0, Math.floor((x - inset) / colW)));
    };
    const pick = (index) => {
      this.$("#apparaten-titel").textContent = `Wat je apparaten verbruikten op ${bucketTitle(this.period_, vakken[index].start)}`;
      this.paintAppLijst_(index);
      svg.querySelectorAll(".b").forEach((balk, i) => balk.classList.toggle("dim", i !== index));
    };
    svg.addEventListener("pointerdown", (event) => {
      this.appScrub_ = true;
      pick(at(event));
    });
    svg.addEventListener("pointermove", (event) => {
      if (this.appScrub_ || event.pointerType === "mouse") pick(at(event));
    });
    for (const done of ["pointerup", "pointercancel"]) {
      svg.addEventListener(done, () => {
        this.appScrub_ = false;
      });
    }
    svg.addEventListener("pointerleave", (event) => {
      if (event.pointerType === "mouse") this.clearAppPick_();
    });
  }

  /**
   * De lijst onder de balken: per apparaat zijn kWh en zijn deel van het huis,
   * van groot naar klein, over de hele periode of over één vak (`index`).
   * Een deel staat er alleen als de apparaten samen in het huis passen; een
   * schatting uit het vermogen kan te hoog uitvallen, en "112 %" kan niemand
   * plaatsen (dezelfde regel als in het rapport).
   */
  paintAppLijst_(index) {
    const reeksen = this.appReeksen_ ?? [];
    const waarde = (reeks) => (index === null ? reeks.totaal : reeks.vakken[index]);
    const huis = this.appHuis_ ? (index === null ? this.appHuis_.reduce((a, b) => a + b, 0) : this.appHuis_[index]) : null;
    const samen = reeksen.reduce((totaal, reeks) => totaal + waarde(reeks), 0);
    const deelKlopt = huis !== null && huis > 0 && samen <= huis * 1.02;

    const rijen = reeksen
      .filter((reeks) => waarde(reeks) >= 0.005)
      .sort((a, b) => waarde(b) - waarde(a))
      .map((reeks) => ({
        label: reeks.label,
        kleur: reeks.kleur === "rest" ? "var(--dac-app-rest)" : `var(--dac-app-${reeks.kleur})`,
        kwh: waarde(reeks),
        exact: reeks.exact,
      }));
    if (deelKlopt && huis - samen >= 0.05) {
      rijen.push({ label: "Rest van het huis", kleur: null, kwh: huis - samen, exact: true, rest: true });
    }

    // Zonder deel geen lege kolom: op een smal scherm is dat ruimte voor de naam.
    this.$("#apparaten-lijst").classList.toggle("zonder-deel", !deelKlopt);
    this.$("#apparaten-lijst").replaceChildren(
      ...rijen.map((rij) => {
        const li = document.createElement("li");
        if (rij.rest) li.className = "rest";
        const vlak = document.createElement("i");
        if (rij.kleur) vlak.style.background = rij.kleur;
        const naam = document.createElement("span");
        naam.className = "app-naam";
        naam.textContent = rij.label;
        const kwh = document.createElement("span");
        kwh.className = "app-kwh";
        kwh.textContent = `${rij.exact ? "" : "≈ "}${nl(rij.kwh, rij.kwh < 10 ? 2 : 1)} kWh`;
        const deel = document.createElement("span");
        deel.className = "app-deel";
        deel.textContent = deelKlopt ? `${Math.round((rij.kwh / huis) * 100)}%` : "";
        li.append(vlak, naam, kwh, deel);
        return li;
      })
    );

    const zinnen = [];
    if (!rijen.length) zinnen.push("In dit vak verbruikte geen van je apparaten iets.");
    if (rijen.some((rij) => !rij.exact)) zinnen.push("≈ is geschat uit het vermogen, voor een apparaat zonder energieteller.");
    if (huis !== null && !deelKlopt && samen > 0) {
      zinnen.push("Samen komen de schattingen boven wat het huis verbruikte, dus er staat geen deel bij.");
    }
    this.$("#apparaten-note").textContent = zinnen.join(" ");
  }

  clearAppPick_() {
    if (!this.appReeksen_ || this.$("#apparaten-card")?.hidden) return;
    this.$("#apparaten-titel").textContent = "Wat je apparaten verbruikten";
    this.paintAppLijst_(null);
    for (const balk of this.$$("#apparaten-stage .b")) balk.classList.remove("dim");
  }

  paintGas_() {
    this.paintVolume_("gas", "Gasverbruik per periode");
  }

  /**
   * De grafiek van een m³-meter: gas, en sinds v0.81.0 ook water. Dezelfde
   * tekening, dezelfde schaal en hetzelfde aanwijzen, elk op zijn eigen kaart.
   */
  paintVolume_(soort, titel) {
    const rows = this.rows_?.[soort] ?? [];
    const card = this.$(`#${soort}-card`);
    if (!card) return;
    card.hidden = !rows.length;
    if (!rows.length) return;

    const total = rows.reduce((sum, row) => sum + row.value, 0);
    this.$(`#${soort}-total`).textContent = `${nl(total, 1)} m³ verbruikt`;

    const gasStage = this.$(`#${soort}-stage`);
    const W = Math.max(MIN_W, Math.round(gasStage.getBoundingClientRect().width) || MIN_W);
    // Ruimte onderaan voor de tijdschaal. Die stond er eerst niet, waardoor je
    // wel zag dat er een piek was maar niet wanneer, en dat is bij gas nu juist
    // de vraag: stookte ik 's ochtends of 's avonds. De stroomgrafiek erboven
    // heeft die schaal wel, dus zonder deze staan er twee grafieken onder
    // elkaar waarvan de x-as verschillend leest.
    const BOTTOM = 90;
    const H = BOTTOM + BOTTOM_PAD;
    const top = Math.max(...rows.map((row) => row.value), 0.001);
    const colW = Math.min(W / rows.length, 64);
    const inset = (W - colW * rows.length) / 2;
    const barW = Math.max(1.5, colW - (colW < 9 ? 1 : Math.min(8, colW * 0.22)));

    const bars = rows
      .map((row, index) => {
        const height = (row.value / (top * 1.05)) * (BOTTOM - 8);
        if (height <= 0.4) return "";
        const x = inset + index * colW + (colW - barW) / 2;
        return `<path class="b gas" d="${block(x, barW, BOTTOM - height, height, Math.min(4, barW / 2))}"/>`;
      })
      .join("");

    // Dezelfde overslagregel als bij stroom, zodat de bijschriften van de twee
    // grafieken op precies dezelfde momenten staan en je ze kunt vergelijken.
    const every = Math.max(1, Math.ceil(rows.length / Math.max(4, Math.floor(W / 46))));
    const ticks = rows
      .map((row, index) =>
        index % every === 0
          ? `<text class="tick" x="${inset + index * colW + colW / 2}" y="${H - 6}" text-anchor="middle">${bucketLabel(
              this.period_,
              row.start
            )}</text>`
          : ""
      )
      .join("");

    const hits = rows
      .map(
        (row, index) =>
          `<rect class="hit" data-index="${index}" x="${inset + index * colW}" y="0"
                 width="${colW}" height="${BOTTOM}"/>`
      )
      .join("");

    gasStage.innerHTML = `
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${titel}">${bars}${ticks}${hits}</svg>
    `;

    // Net als de stroomgrafiek: aanwijzen zet de kop erboven op die ene balk.
    const svg = gasStage.querySelector("svg");
    const heel = `${nl(total, 1)} m³ verbruikt`;
    const at = (event) => {
      const box = svg.getBoundingClientRect();
      const x = ((event.clientX - box.left) / box.width) * W;
      return Math.min(rows.length - 1, Math.max(0, Math.floor((x - inset) / colW)));
    };
    const pick = (index) => {
      const row = rows[index];
      if (!row) return;
      this.$(`#${soort}-total`).textContent = `${nl(row.value, 1)} m³ op ${bucketTitle(this.period_, row.start)}`;
      for (const bar of svg.querySelectorAll(".b")) bar.classList.add("dim");
      svg.querySelectorAll(".b")[index]?.classList.remove("dim");
    };

    svg.addEventListener("pointerdown", (event) => {
      this.gasScrub_ = true;
      pick(at(event));
    });
    svg.addEventListener("pointermove", (event) => {
      if (this.gasScrub_ || event.pointerType === "mouse") pick(at(event));
    });
    for (const done of ["pointerup", "pointercancel"]) {
      svg.addEventListener(done, () => {
        this.gasScrub_ = false;
      });
    }
    (this.volumeWhole_ ??= {})[soort] = heel;
    svg.addEventListener("pointerleave", (event) => {
      if (event.pointerType !== "mouse") return;
      this.clearGasPick_();
    });
  }

  clearGasPick_() {
    for (const soort of ["gas", "water"]) {
      const heel = this.volumeWhole_?.[soort];
      const kop = this.$(`#${soort}-total`);
      if (heel && kop) kop.textContent = heel;
      for (const bar of this.$$(`#${soort}-stage .b`)) bar.classList.remove("dim");
    }
  }
}

/** A block with its far end rounded, drawn downwards when `down` is set. */
function block(x, w, y, h, r, down = false) {
  const radius = Math.min(r, h, w / 2);
  const top = down ? y + h : y;
  const base = down ? y : y + h;
  const sign = down ? -1 : 1;

  return [
    `M${x.toFixed(1)} ${base.toFixed(1)}`,
    `L${x.toFixed(1)} ${(top + sign * radius).toFixed(1)}`,
    `Q${x.toFixed(1)} ${top.toFixed(1)} ${(x + radius).toFixed(1)} ${top.toFixed(1)}`,
    `L${(x + w - radius).toFixed(1)} ${top.toFixed(1)}`,
    `Q${(x + w).toFixed(1)} ${top.toFixed(1)} ${(x + w).toFixed(1)} ${(top + sign * radius).toFixed(1)}`,
    `L${(x + w).toFixed(1)} ${base.toFixed(1)}`,
    "Z",
  ].join(" ");
}

DacViewHistory.css = /* css */ `
  :host { display: block; }

  .wrap {
    max-width: var(--dac-maxw);
    margin: 0 auto;
    padding: 24px max(22px, var(--dac-safe-r)) calc(64px + var(--dac-safe-b)) max(22px, var(--dac-safe-l));
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .intro h1 { margin: 6px 0 0; font-size: 26px; font-weight: 600; letter-spacing: -0.01em; }
  .intro p { margin: 8px 0 0; font-size: 14px; line-height: 1.6; color: var(--dac-ink-2); max-width: 70ch; }

  /* Uitlijnen op de onderkant, want de knoppenrijen dragen nu een opschrift en
     de knop Rapport en de bladerpijlen niet. Op de bovenkant uitlijnen zou die
     laatste twee boven de knoppen laten zweven. */
  .controls { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; }

  /* Elke keuze een uitklaplijst met een opschrift erboven (v0.116.0). */
  .keuze { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
  .keuze-kop {
    font-size: 11px; font-weight: 600; letter-spacing: .02em;
    color: var(--dac-ink-3); text-transform: uppercase;
  }
  /* Zo breed als de lijst, niet als het opschrift erboven: anders stond het
     pijltje bij "Verloop in het rapport" naast de lijst (13-10-2026). */
  .kies { position: relative; display: block; align-self: flex-start; }
  /* Het pijltje van de lijst, want "appearance: none" haalt dat van de browser weg. */
  .kies::after {
    content: ""; position: absolute; right: 14px; top: 50%;
    width: 7px; height: 7px; margin-top: -5px;
    border-right: 1.5px solid var(--dac-ink-2); border-bottom: 1.5px solid var(--dac-ink-2);
    transform: rotate(45deg); pointer-events: none;
  }
  .kies select {
    appearance: none; -webkit-appearance: none;
    min-width: 128px; min-height: 40px; padding: 8px 36px 8px 14px;
    border-radius: var(--dac-radius-pill);
    border: 1px solid var(--dac-border-hi);
    background: rgba(var(--dac-veil), 0.04);
    color: var(--dac-ink);
    font: inherit; font-size: 13.5px;
    cursor: pointer;
    color-scheme: var(--dac-scheme);
  }
  .kies select:hover { border-color: var(--dac-ink-3); }
  .kies select:focus-visible { outline: none; border-color: var(--dac-accent-hi); }
  /* De lijst die opklapt tekent de browser zelf: zonder deze regel wit met
     lichte letters (zie proef "elke uitklaplijst" in test_rapport.mjs). */
  select option { background: var(--dac-bg-raise); color: var(--dac-ink); }
  /* Onder 16 px zoomt iOS in zodra je de lijst aantikt, en blijft daar. */
  @media (pointer: coarse) { .kies select { font-size: 16px; } }

  .rapport { position: relative; }
  .rapport-menu {
    position: absolute; z-index: 5; top: calc(100% + 6px); left: 0;
    display: flex; flex-direction: column; gap: 2px;
    width: max-content; max-width: min(300px, calc(100vw - 32px));
    padding: 6px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border-hi);
    background: var(--dac-popover);
    box-shadow: 0 18px 40px -20px rgba(0, 0, 0, var(--dac-shadow-deep));
  }
  .rapport-menu[hidden] { display: none; }
  .rapport-menu button {
    display: flex; flex-direction: column; gap: 2px; align-items: flex-start;
    padding: 9px 12px; border: 0; border-radius: 8px;
    background: transparent; color: var(--dac-ink);
    font: inherit; font-size: 13.5px; text-align: left; cursor: pointer;
  }
  .rapport-menu button:hover, .rapport-menu button:focus-visible {
    background: rgba(var(--dac-veil), 0.06); outline: none;
  }
  .rapport-menu small { font-size: 12px; color: var(--dac-ink-3); }

  button.download {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 9px 16px;
    border-radius: var(--dac-radius-pill);
    border: 1px solid var(--dac-border);
    background: transparent;
    color: var(--dac-ink-2);
    font: inherit; font-size: 13.5px;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }
  button.download:hover { color: var(--dac-ink); border-color: var(--dac-border-hi); }
  /* Het pijltje wijst omlaag: het bestand komt naar je toe. */
  button.download .icon { width: 15px; height: 15px; transform: rotate(90deg); }

  .stepper { display: flex; align-items: center; gap: 6px; margin-left: auto; min-width: 0; }
  .stepper span {
    font-size: 13.5px;
    color: var(--dac-ink);
    min-width: 0;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .stepper button {
    width: 38px; height: 38px; flex: 0 0 auto;
    display: grid; place-items: center;
    border-radius: var(--dac-radius-pill);
    border: 1px solid var(--dac-border);
    background: transparent;
    color: var(--dac-ink-2);
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }
  .stepper button.now {
    width: auto; height: 34px; padding: 0 14px;
    font: inherit; font-size: 12.5px; font-weight: 600;
    color: var(--dac-ink-2);
    white-space: nowrap;
  }
  .stepper button.now[hidden] { display: none; }
  .stepper button:hover:not(:disabled) { color: var(--dac-ink); border-color: var(--dac-border-hi); }
  .stepper button:disabled { opacity: 0.3; cursor: default; }
  .stepper .icon { width: 16px; height: 16px; }

  section.card { padding: 20px 22px 22px; }
  .panel-head .eyebrow { font-size: 11px; }
  .panel-head h2 { margin: 4px 0 0; font-size: 17px; font-weight: 600; }

  .totals-title {
    font-size: 12.5px;
    color: var(--dac-ink-2);
    margin-bottom: 10px;
    min-height: 1.2em;
  }

  .totals {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
  }
  .total { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
  .t-label {
    font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--dac-ink-3);
  }
  .t-value {
    font-size: 22px; font-weight: 400; color: var(--dac-ink);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .t-unit { font-size: 12px; font-weight: 600; color: var(--dac-ink-3); margin-left: 5px; }
  .t-sub { font-size: 12px; line-height: 1.4; color: var(--dac-ink-3); }

  svg { width: 100%; height: auto; display: block; }
  .zero { stroke: var(--dac-border-hi); stroke-width: 1; }
  .b.own { fill: var(--dac-solar); }
  .b.bought { fill: var(--dac-grid-in); }
  .b.sold { fill: var(--dac-grid-out); }
  .b.gas { fill: var(--dac-warn); }
  .b { transition: opacity 150ms ease; }
  /* Aanwijzen licht er één uit door de rest te dempen: de balk zelf verandert
     niet van kleur, want die kleur betekent iets. */
  .b.dim { opacity: 0.3; }
  .hit { fill: transparent; cursor: pointer; }
  svg { touch-action: pan-y; }
  .tick {
    font-family: var(--dac-font);
    font-size: 11px;
    fill: var(--dac-ink-3);
    font-variant-numeric: tabular-nums;
  }

  .legend { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 14px; }

  /* Per apparaat (v0.121.0): een regel per apparaat met zijn kleur, zijn naam,
     zijn kWh en zijn deel van het huis. De lijst is ook de legenda. */
  .app-lijst { list-style: none; margin: 14px 0 0; padding: 0; display: grid; gap: 2px; }
  .app-lijst li {
    display: grid;
    grid-template-columns: 12px minmax(0, 1fr) auto 3.2em;
    align-items: center;
    gap: 10px;
    padding: 6px 0;
    border-top: 1px solid var(--dac-border);
    font-size: 13px;
  }
  .app-lijst.zonder-deel li { grid-template-columns: 12px minmax(0, 1fr) auto; }
  .app-lijst.zonder-deel .app-deel { display: none; }
  .app-lijst li:first-child { border-top: 0; }
  .app-lijst i { width: 12px; height: 12px; border-radius: 3px; display: block; }
  .app-lijst li.rest i { border: 1px dashed var(--dac-border-hi); box-sizing: border-box; }
  .app-lijst li.rest .app-naam { color: var(--dac-ink-2); }
  .app-naam { color: var(--dac-ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .app-kwh { color: var(--dac-ink); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .app-deel { color: var(--dac-ink-3); font-variant-numeric: tabular-nums; text-align: right; }
  .legend span { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: var(--dac-ink-2); }
  .legend i { width: 12px; height: 12px; border-radius: 3px; display: inline-block; flex: 0 0 auto; }

  /* De tijdlijn (v0.115.0): een baan per apparaat over de hele dag. Oranje is
     eigen stroom en blauw het net, net als in de grafiek erboven. De lijntjes in
     de baan staan om de drie uur. */
  .tijdlijn { margin-top: 18px; }
  .tijdlijn .rijen { position: relative; display: flex; flex-direction: column; gap: 10px; }
  .tijdlijn .rij { display: grid; grid-template-columns: 112px minmax(0, 1fr); align-items: center; gap: 12px; }
  .tijdlijn .naam {
    font-size: 13px; color: var(--dac-ink-2);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .tijdlijn .baan {
    position: relative; height: 28px; border-radius: 8px;
    background-color: rgba(var(--dac-veil), 0.035);
    background-image: repeating-linear-gradient(to right,
      transparent 0, transparent calc(var(--raster, 12.5%) - 1px),
      rgba(var(--dac-veil), 0.08) calc(var(--raster, 12.5%) - 1px), rgba(var(--dac-veil), 0.08) var(--raster, 12.5%));
  }
  .tijdlijn .stippen .baan { height: 18px; background: none; }
  .stuk {
    position: absolute; top: 0; bottom: 0; min-width: 3px;
    padding: 0; border: 0; border-radius: 6px;
    cursor: pointer; -webkit-tap-highlight-color: transparent;
    transition: opacity 150ms ease, box-shadow 150ms ease;
  }
  .stuk:focus, .stip:focus { outline: none; }
  .stuk:focus-visible, .stip:focus-visible { box-shadow: 0 0 0 2px var(--dac-accent); }
  .stuk.gekozen { box-shadow: 0 0 0 2px var(--dac-ink); z-index: 1; }
  /* Iets aangetikt: de rest gaat zachter, de kleur zelf blijft wat hij betekent. */
  .rijen:has(.gekozen) .stuk:not(.gekozen),
  .rijen:has(.gekozen) .stip:not(.gekozen) { opacity: 0.35; }
  .vlek { display: inline-block; width: 10px; height: 10px; border-radius: 3px; flex: 0 0 auto; }
  .stuk.zon, .vlek.zon { background: var(--dac-solar); }
  .stuk.net, .vlek.net { background: var(--dac-grid-in); }
  .stuk.nul, .vlek.nul { background: var(--dac-device-2); }
  .stuk.ontladen, .vlek.ontladen { background: var(--dac-device-1); }
  .stuk.wacht, .vlek.wacht { background: rgba(var(--dac-veil), 0.16); }
  .stuk.stil, .vlek.stil { background: rgba(var(--dac-veil), 0.10); }
  .stuk.aan, .vlek.aan { background: rgba(var(--dac-veil), 0.28); }
  .stuk.leeg, .vlek.leeg { background: transparent; border: 1.5px dashed rgba(var(--dac-veil), 0.30); }
  .stuk.vol, .vlek.vol { background: color-mix(in srgb, var(--dac-good) 50%, transparent); }
  .stip {
    position: absolute; top: 50%; width: 12px; height: 12px; margin: -6px 0 0 -6px;
    padding: 0; border: 2px solid var(--dac-surface); border-radius: 50%;
    background: var(--dac-ink-3);
    cursor: pointer; -webkit-tap-highlight-color: transparent;
    transition: opacity 150ms ease;
  }
  /* Een vinger is breder dan twaalf pixels. */
  .stip::before { content: ""; position: absolute; inset: -8px; }
  .stip.kritiek { background: var(--dac-bad); }
  .stip.gekozen { box-shadow: 0 0 0 2px var(--dac-ink); }
  .tijdlijn .nu {
    position: absolute; top: -3px; bottom: -3px; width: 2px; margin-left: -1px;
    border-radius: 1px; background: var(--dac-accent); pointer-events: none; z-index: 2;
  }
  .tijdlijn .uren {
    position: relative; height: 16px; margin: 8px 0 0 124px;
    font-size: 11px; color: var(--dac-ink-3); font-variant-numeric: tabular-nums;
  }
  .tijdlijn .uren span { position: absolute; transform: translateX(-50%); white-space: nowrap; }
  .tijdlijn .uren span:first-child { transform: none; }
  .tijdlijn .uren span:last-child { transform: translateX(-100%); }
  /* Bij een week staat de dag in het midden van zijn eigen vak. */
  .tijdlijn .uren span.dag { transform: translateX(-50%); }
  #tijdlijn-legenda:empty { display: none; }
  .tl-uitleg {
    margin-top: 14px; padding: 12px 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(var(--dac-veil), 0.03);
  }
  .tl-uitleg[hidden] { display: none; }
  .tl-uitleg .tijd { font-size: 12.5px; color: var(--dac-ink-2); }
  .tl-uitleg .tijd strong { color: var(--dac-ink); font-weight: 600; }
  .tl-uitleg .wat {
    margin: 6px 0 0; font-size: 14px; line-height: 1.45; color: var(--dac-ink);
    white-space: pre-line;
  }
  .tl-uitleg .wat .vlek { margin-right: 8px; }
  .tl-uitleg .reden { margin: 4px 0 0; font-size: 13px; line-height: 1.5; color: var(--dac-ink-2); }

  .money .totals { margin: 16px 0 0; }
  .saved .totals { margin: 16px 0 0; }

  /* In geld (v0.101.0): drie getallen, een balk en twee kolommen. */
  .geld-kop {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 14px;
    margin: 18px 0 0;
  }
  .geld-getal {
    display: flex; flex-direction: column; gap: 4px; min-width: 0;
    padding: 14px 16px;
    border-radius: var(--dac-radius-sm);
    background: var(--dac-surface);
    border-left: 3px solid var(--tone, var(--dac-border-hi));
  }
  .geld-waarde {
    font-size: 30px; font-weight: 400; color: var(--dac-ink);
    font-variant-numeric: tabular-nums; white-space: nowrap; line-height: 1.15;
  }
  .geld-uitleg { font-size: 12.5px; line-height: 1.4; color: var(--dac-ink-2); }
  .geld-balk {
    display: flex; gap: 3px; height: 14px; margin: 18px 0 0;
    border-radius: var(--dac-radius-pill); overflow: hidden;
  }
  .geld-balk[hidden] { display: none; }
  .geld-balk i { display: block; flex: 1 1 0; min-width: 3px; background: var(--tone); }
  .geld-delen {
    display: grid;
    /* Nooit breder dan de kaart: op 280 px is er 211 px en liep hij 14 px over. */
    grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr));
    gap: 10px 28px;
    margin: 16px 0 0;
  }
  .geld-kolom { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
  .geld-regel {
    display: grid; grid-template-columns: 10px 1fr auto; align-items: center; gap: 10px;
    font-size: 13.5px; color: var(--dac-ink-2);
    padding: 5px 0; border-bottom: 1px solid var(--dac-border);
  }
  .geld-regel i { width: 10px; height: 10px; border-radius: 3px; background: var(--tone); }
  .geld-bedrag { color: var(--dac-ink); font-variant-numeric: tabular-nums; white-space: nowrap; }

  .tabel-wrap { overflow-x: auto; margin-top: 16px; }
  .tabel-wrap:has(table:empty) { display: none; }
  table.beurten { border-collapse: collapse; width: 100%; font-size: 13px; }
  table.beurten th, table.beurten td {
    text-align: left; padding: 6px 10px 6px 0; border-bottom: 1px solid var(--dac-border);
    white-space: nowrap; font-variant-numeric: tabular-nums;
  }
  table.beurten th { font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--dac-ink-3); }
  .note { margin: 12px 0 0; font-size: 13px; line-height: 1.5; color: var(--dac-ink-2); }
  .note:empty { display: none; }

  @media (max-width: 640px) {
    .wrap { padding: 16px max(12px, var(--dac-safe-r)) calc(48px + var(--dac-safe-b)) max(12px, var(--dac-safe-l)); }
    section.card { padding: 16px 14px 18px; }
    .stepper { margin-left: 0; flex-basis: 100%; }
    .t-value { font-size: 19px; }
    /* Op een telefoon de naam boven de baan: de baan krijgt de hele breedte. */
    .tijdlijn .rij { grid-template-columns: minmax(0, 1fr); gap: 4px; }
    .tijdlijn .naam { font-size: 12px; }
    .tijdlijn .uren { margin-left: 0; }
  }
`;

define("dac-view-history", DacViewHistory);
