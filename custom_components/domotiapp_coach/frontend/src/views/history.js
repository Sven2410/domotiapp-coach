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
 * generation plus what came in, minus what went out. A separate house meter
 * would only add a way for the three to disagree.
 */

import { DacElement, define } from "../base.js";
import { icons } from "../icons.js";
import { energy, euro, percent, signedPower } from "../format.js";
import { deviceLabel, deviceLabelMap } from "../devices.js";

/** Het merkteken op het rapport. */
const LOGO_URL = new URL("../../img/domotitech-mark.png", import.meta.url).href;
import { tariff } from "../data-source.js";
import { afleveren, base64Van } from "../pdf.js";
import { reportPdf } from "../report.js";
import { beurtenIn, opmerking, perApparaat, totalen } from "../savings.js";
import {
  PERIODS,
  combine,
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

/** Drawing units; the chart measures itself in pixels like the price chart. */
const MIN_W = 240;
const TOP = 18;
const BOTTOM_PAD = 22;

const nl = (value, digits = 1) =>
  value.toLocaleString("nl-NL", { minimumFractionDigits: digits, maximumFractionDigits: digits });

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
    this.period_ = "week";
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
          <p>Uit de geschiedenis die Home Assistant zelf bijhoudt. Boven de lijn staat wat je verbruikt hebt, gesplitst in je eigen zon en wat je van het net kocht. Onder de lijn staat wat je hebt teruggeleverd.</p>
        </header>

        <div class="controls">
          <div class="keuze">
            <span class="keuze-kop">Onderwerp</span>
            <div class="segmented" id="onderwerpen">
              <button type="button" data-onderwerp="energie" aria-pressed="true">Energie</button>
              <button type="button" data-onderwerp="bespaard" aria-pressed="false">Bespaard</button>
            </div>
          </div>
          <div class="keuze">
            <span class="keuze-kop">Periode</span>
            <div class="segmented" id="periods">
            ${PERIODS.map(
              (item) => `<button type="button" data-period="${item.id}" aria-pressed="false">${item.label}</button>`
            ).join("")}
            </div>
          </div>
          <div class="keuze">
            <span class="keuze-kop">Verloop in het rapport</span>
            <div class="segmented detail" id="korrels" title="Hoe fijn het verloop in het rapport komt te staan">
              ${KORREL_KNOPPEN.map(
                (item) => `<button type="button" data-korrel="${item.id}" aria-pressed="false">${item.label}</button>`
              ).join("")}
            </div>
          </div>
          <button type="button" class="download" id="report" title="Een rapport om te bewaren of te printen">
            ${icons.compass}<span>Rapport</span>
          </button>
          <div class="stepper">
            <button type="button" class="now" id="now" hidden></button>
            <button type="button" id="prev" aria-label="Vorige">${icons.arrowLeft}</button>
            <span id="period-label"></span>
            <button type="button" id="next" aria-label="Volgende">${icons.arrowRight}</button>
          </div>
        </div>

        <p class="note korrel-note" id="korrel-note"></p>

        <section class="card" id="card">
          <div class="totals-title" id="totals-title"></div>
          <div class="totals" id="totals"></div>
          <div id="stage"></div>
          <div class="legend" id="legend"></div>
          <p class="note" id="note"></p>
        </section>

        <section class="card money" id="money-card" hidden>
          <div class="panel-head">
            <div class="eyebrow">In geld</div>
            <h2>Wat je zon opleverde</h2>
          </div>
          <div class="totals" id="money"></div>
          <p class="note" id="money-note"></p>
        </section>

        <section class="card gas" id="gas-card" hidden>
          <div class="panel-head">
            <div class="eyebrow">Gas</div>
            <h2 id="gas-total"></h2>
          </div>
          <div id="gas-stage"></div>
        </section>

        <section class="card saved" id="saved-card" hidden>
          <div class="panel-head">
            <div class="eyebrow">Bespaard</div>
            <h2>Wat de coach je bespaarde</h2>
          </div>
          <div class="totals" id="saved-totals"></div>
          <p class="note" id="saved-note"></p>
          <div class="tabel-wrap"><table class="beurten" id="saved-devices"></table></div>
          <div class="tabel-wrap"><table class="beurten" id="saved-list"></table></div>
        </section>
      </div>
    `;
  }

  afterRender() {
    for (const button of this.$$("#onderwerpen button")) {
      button.addEventListener("click", () => {
        if (this.onderwerp_ === button.dataset.onderwerp) return;
        this.onderwerp_ = button.dataset.onderwerp;
        for (const knop of this.$$("#onderwerpen button")) {
          knop.setAttribute("aria-pressed", String(knop.dataset.onderwerp === this.onderwerp_));
        }
        if (this.onderwerp_ === "bespaard") this.laadBeurten_();
        this.paint_();
      });
    }
    for (const button of this.$$("#periods button")) {
      button.addEventListener("click", () => {
        if (this.period_ === button.dataset.period) return;
        this.period_ = button.dataset.period;
        this.offset_ = 0;
        this.load_();
      });
    }
    for (const button of this.$$("#korrels button")) {
      button.addEventListener("click", () => {
        // Nog eens op dezelfde knop laat de keuze weer los, en dan volgt hij
        // de periode. Zonder die weg terug zit je eraan vast.
        this.korrel_ = this.korrel_ === button.dataset.korrel ? "" : button.dataset.korrel;
        this.paintKorrel_();
      });
    }
    this.$("#report").addEventListener("click", () => this.report_());
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
      if (!path.some((node) => node?.id === "stage" || node?.id === "gas-stage")) {
        this.clearPick_();
        this.clearGasPick_();
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
  }

  onDisconnect() {
    this.observer_?.disconnect();
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

  /** Which counters this installation has, in the roles the chart needs. */
  meters_() {
    const meters = this.settings_?.sources?.meters ?? {};
    return {
      solar: [meters.solar_total].filter(Boolean),
      import: [meters.import_low, meters.import_high].filter(Boolean),
      export: [meters.export_low, meters.export_high].filter(Boolean),
      gas: meters.gas_enabled && meters.gas ? [meters.gas] : [],
    };
  }

  async load_() {
    const roles = this.meters_();
    const ids = [...roles.solar, ...roles.import, ...roles.export, ...roles.gas];

    this.paintPeriod_();

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

    const [series, prices, devices] = await Promise.all([
      fetchPeriod(this.hass_, ids, this.period_, start),
      fetchPrices(this.hass_, this.priceEntity_(), this.period_, start),
      fetchDevices(this.hass_, apparaten, this.period_, start),
    ]);
    if (run !== this.run_) return;
    this.prices_ = prices;
    this.devices_ = devices;

    this.rows_ = {
      solar: combine(series, roles.solar),
      import: combine(series, roles.import),
      export: combine(series, roles.export),
      gas: combine(series, roles.gas),
    };
    this.paint_();
  }

  /** Welke fijnheid er gekozen is, en wat dat aan regels gaat kosten. */
  korrel_id() {
    return this.korrel_ || STANDAARD_KORREL[this.period_];
  }

  paintKorrel_() {
    const gekozen = this.korrel_id();
    for (const button of this.$$("#korrels button")) {
      const id = button.dataset.korrel;
      button.setAttribute("aria-pressed", String(id === gekozen));
      // Zeggen wat het gaat kosten voordat er iemand op Rapport drukt. Bij een
      // jaar per kwartier zijn dat tienduizenden regels, en dat is geen reden
      // om het te verbieden maar wel om het niet te verzwijgen.
      const regels = REGELS[this.period_]?.[id];
      button.title = regels
        ? `Ongeveer ${nl(regels, 0)} regels per apparaat in het rapport`
        : "";
      button.disabled = !regels;
    }
    const uitleg = this.$("#korrel-note");
    if (uitleg) {
      const regels = REGELS[this.period_]?.[gekozen] ?? 0;
      const apparaten = Math.max(1, this.vermogenBronnen_().length);
      uitleg.textContent = regels
        ? `Het rapport krijgt het verloop per ${KORRELS[gekozen].kop.toLowerCase()}: ` +
          `ongeveer ${nl(regels * apparaten, 0)} regels over ${apparaten} ` +
          `${apparaten === 1 ? "apparaat" : "apparaten"}.`
        : "";
    }
  }

  paintPeriod_() {
    this.paintKorrel_();
    for (const button of this.$$("#periods button")) {
      button.setAttribute("aria-pressed", String(button.dataset.period === this.period_));
    }
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
    this.$("#card").hidden = bespaard;
    this.$("#korrel-note").hidden = bespaard;
    if (bespaard) {
      this.$("#money-card").hidden = true;
      this.$("#gas-card").hidden = true;
      this.paintSaved_();
      return;
    }

    const note = this.$("#note");
    const roles = this.meters_();

    if (!roles.import.length && !roles.export.length && !roles.solar.length) {
      this.$("#stage").innerHTML = "";
      this.$("#totals").replaceChildren();
      this.$("#legend").replaceChildren();
      this.$("#gas-card").hidden = true;
      note.textContent =
        "Er zijn nog geen meterstanden gekozen. Onder Instellingen bij Meterstanden wijs je de tellers aan; daarna staat hier je geschiedenis.";
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
        "Je opwekteller staat nog niet ingesteld, dus je ziet hier alleen wat er van het net kwam en wat er naar het net ging. Vul bij Instellingen onder Meterstanden de teller van je omvormer in, dan komen je opwek, je verbruik en je zelfbenutting er ook bij te staan."
      );
    }
    if (missing.length) {
      zinnen.push(
        `Van ${missing.length === 1 ? "één teller" : `${missing.length} tellers`} houdt Home Assistant geen geschiedenis bij. Dat gebeurt alleen bij sensoren die zichzelf als oplopende totaalstand aanbieden.`
      );
    }
    note.textContent = zinnen.join(" ");

    this.paintChart_();
    this.paintMoney_();
    this.paintGas_();
  }

  /** The buckets of this period, in order, with everything that belongs to one. */
  buckets_() {
    const keys = new Set();
    for (const key of ["solar", "import", "export"]) {
      for (const row of this.rows_[key]) keys.add(row.start.getTime());
    }

    const at = (key, time) => this.rows_[key].find((row) => row.start.getTime() === time)?.value ?? 0;

    return [...keys]
      .sort((a, b) => a - b)
      .map((time) => {
        const solar = at("solar", time);
        const bought = at("import", time);
        const sold = at("export", time);
        // Own use is what the roof made minus what went out. Never negative:
        // meters are read at slightly different moments and a rounding of a few
        // watt-hours must not turn into a negative bar.
        const own = Math.max(0, solar - sold);
        return { start: new Date(time), own, bought, sold, used: own + bought };
      });
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
    totals.selfUse =
      hasSolar && totals.solar > 0 ? (sum("own") / totals.solar) * 100 : null;

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
        const ownH = row.own * scale;
        const boughtH = row.bought * scale;
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
  async reportData_() {
    const rows = this.rowsShown_ ?? [];
    if (!rows.length) return null;

    const vermogen = await this.vermogen_();

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

    const prijsBij = (row) => prices.get(row.start.getTime()) ?? rate.buy;
    const waarde = (key) =>
      rows.reduce((total, row) => total + row[key] * (prijsBij(row) ?? 0), 0);

    // ---- de tabel per tijdvak ----
    const kop = ["Periode"];
    if (hasSolar) kop.push("Opgewekt", "Verbruikt", "Eigen zon");
    kop.push("Van het net", "Naar het net");
    if (gas.size) kop.push("Gas");
    if (rate.buy !== null) kop.push("Prijs", "Kosten");

    const regels = rows.map((row) => {
      const prijs = prijsBij(row);
      const cellen = [bucketTitle(this.period_, row.start)];
      if (hasSolar) cellen.push(kwh(row.own + row.sold), kwh(row.used), kwh(row.own));
      cellen.push(kwh(row.bought), kwh(row.sold));
      if (gas.size) cellen.push(`${nl(gas.get(row.start.getTime()) ?? 0, 2)} m³`);
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
      gas.size
        ? cel("Gas", `${nl([...gas.values()].reduce((a, b) => a + b, 0), 1)} m³`)
        : null,
    ].filter(Boolean);

    const geldVakjes =
      rate.buy === null
        ? []
        : [
            hasSolar ? cel("Eigen zon bespaarde", euro(waarde("own"))) : null,
            cel("Stroom gekocht voor", euro(waarde("bought"))),
            rate.feedIn === null
              ? null
              : cel(
                  "Teruglevering leverde",
                  euro(Math.max(0, (totals.sold ?? 0) * rate.feedIn))
                ),
          ].filter(Boolean);

    return {
      logoUrl: LOGO_URL,
      woning,
      periode,
      korrel,
      metZon: hasSolar,
      gemaakt: new Date().toLocaleDateString("nl-NL", {
        day: "numeric",
        month: "long",
        year: "numeric",
      }),
      energie: energieVakjes,
      geld: geldVakjes,
      geldUitleg: geldVakjes.length ? this.$("#money-note").textContent : "",
      bespaard: this.bespaardRapport_(),
      verloop: rows.map((row) => ({
        label: bucketLabel(this.period_, row.start),
        own: row.own,
        bought: row.bought,
        sold: row.sold,
      })),
      apparaten: { kop: apparaatKop, rijen: apparaatRijen, uitleg: apparaatUitleg },
      vermogen: vermogen.samenvatting,
      vermogenDetail: vermogen.detail,
      cijfers: { kop, rijen: regels, totaal: totaalCellen },
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
  async report_() {
    const knop = this.$("#report");
    if (knop?.disabled) return;

    const gegevens = await this.reportData_();
    if (!gegevens) return;

    const label = knop?.querySelector("span");
    const oud = label?.textContent;
    if (knop) knop.disabled = true;
    if (label) label.textContent = "Bezig";

    try {
      const blob = await reportPdf(gegevens);
      const naam = `DomotiApp Coach ${gegevens.periode}.pdf`.replace(/[\\/:*?"<>|]/g, "-");
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

    return (this.settings_?.devices ?? [])
      .map((device) => {
        const found = stats.get(device.id);
        if (!found) return null;

        let kwh = 0;
        let cost = 0;
        for (const [time, value] of found.rows) {
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
    if (totals.selfUse !== null) {
      rows.push({ label: "Zelf gebruikt", value: percent(totals.selfUse), tone: "var(--dac-good)" });
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
      { tone: "var(--dac-solar)", label: "Eigen zon gebruikt" },
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
    return {
      vakjes: [
        { label: "Bespaard", waarde: euro(totaal.saved) },
        { label: "Betaald", waarde: euro(totaal.paid) },
        { label: "Geladen", waarde: kwh(totaal.kwh) },
        { label: "Waarvan zon", waarde: kwh(totaal.solar_kwh) },
      ],
      uitleg:
        "Bespaard is wat dezelfde kilowatturen gekost hadden tegen de prijs op het moment van " +
        "inpluggen, min wat ze werkelijk kostten. Eigen zon telt tegen wat teruglevering " +
        "opgebracht had." +
        (totaal.onbekend
          ? ` ${totaal.onbekend === 1 ? "Eén beurt telt" : `${totaal.onbekend} beurten tellen`} niet mee in het geld, omdat de prijs toen niet bekend was.`
          : ""),
      kop: ["Ingeplugd", "Apparaat", "Geladen", "Zon", "Prijs toen", "Betaald", "Bespaard"],
      rijen: items.map((b) => [
        wanneer(b),
        b.car ? `${b.name}, ${b.car}` : b.name,
        kwh(b.kwh),
        kwh(b.solar_kwh),
        b.ref_price === null || b.ref_price === undefined ? "" : euro(b.ref_price),
        b.price_unknown ? "" : euro(b.paid),
        b.saved === null || b.saved === undefined ? "" : euro(b.saved),
      ]),
      totaal: ["Totaal", "", kwh(totaal.kwh), kwh(totaal.solar_kwh), "", euro(totaal.paid), euro(totaal.saved)],
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
    if (this.onderwerp_ === "bespaard") this.paint_();
  }

  /** De beurten van de gekozen periode en wat ze samen bespaarden. */
  bespaard_() {
    const start = periodStart(this.period_, this.offset_);
    const end = periodEnd(this.period_, start);
    const items = beurtenIn(this.beurten_ ?? [], start, end);
    return { items, totaal: totalen(items), apparaten: perApparaat(items) };
  }

  paintSaved_() {
    const note = this.$("#saved-note");
    const tegels = this.$("#saved-totals");
    const apparaten = this.$("#saved-devices");
    const lijst = this.$("#saved-list");
    tegels.replaceChildren();
    apparaten.replaceChildren();
    lijst.replaceChildren();

    if (this.beurten_ === undefined || this.beurten_ === null) {
      note.textContent = "Bezig met ophalen…";
      return;
    }
    const { items, totaal, apparaten: perDevice } = this.bespaard_();
    if (!items.length) {
      note.textContent = this.beurten_.length
        ? "Geen laadbeurten in deze periode."
        : "Nog geen laadbeurten. Vanaf de eerstvolgende beurt staat hier wat hij kostte en bespaarde.";
      return;
    }

    const tegel = (label, value, tone) => {
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
      return box;
    };
    const kwh = (value) => {
      const { value: getal, unit } = energy(value);
      return `${getal} ${unit}`;
    };
    tegels.append(
      tegel("Bespaard", euro(totaal.saved), "var(--dac-solar)"),
      tegel("Betaald", euro(totaal.paid), "var(--dac-grid-in)"),
      tegel("Geladen", kwh(totaal.kwh)),
      tegel("Waarvan zon", kwh(totaal.solar_kwh), "var(--dac-solar)")
    );

    const zinnen = [
      "Bespaard is wat dezelfde kilowatturen gekost hadden tegen de prijs op het moment van inpluggen, min wat ze werkelijk kostten. Eigen zon telt tegen wat teruglevering opgebracht had.",
    ];
    if (totaal.onbekend) {
      zinnen.push(
        `${totaal.onbekend === 1 ? "Eén beurt telt" : `${totaal.onbekend} beurten tellen`} niet mee in het geld, omdat de prijs toen niet bekend was.`
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
    if (perDevice.length > 1) {
      apparaten.append(rij(["Apparaat", "Beurten", "Geladen", "Zon", "Betaald", "Bespaard"], true));
      for (const a of perDevice) {
        apparaten.append(rij([a.name, String(a.beurten), kwh(a.kwh), kwh(a.solar_kwh), euro(a.paid), euro(a.saved)]));
      }
    }

    const wanneer = (b) => {
      const t = new Date(b.plugged_at);
      if (Number.isNaN(t.getTime())) return "";
      const dag = `${String(t.getDate()).padStart(2, "0")}-${String(t.getMonth() + 1).padStart(2, "0")}`;
      const klok = `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
      return this.period_ === "day" ? klok : `${dag} ${klok}`;
    };
    lijst.append(rij(["Ingeplugd", "Apparaat", "Geladen", "Zon", "Prijs toen", "Betaald", "Bespaard", ""], true));
    for (const b of items) {
      lijst.append(
        rij([
          wanneer(b),
          b.car ? `${b.name}, ${b.car}` : b.name,
          kwh(b.kwh),
          kwh(b.solar_kwh),
          b.ref_price === null || b.ref_price === undefined ? "" : euro(b.ref_price),
          b.price_unknown ? "" : euro(b.paid),
          b.saved === null || b.saved === undefined ? "" : euro(b.saved),
          opmerking(b),
        ])
      );
    }
  }

  paintMoney_() {
    const card = this.$("#money-card");
    const rows = this.rowsShown_ ?? [];
    const rate = tariff(this.feed_, this.settings_?.contract);

    if (!rows.length || rate.buy === null) {
      card.hidden = true;
      return;
    }

    // Per bucket met de prijs van dat moment, als die er is. Anders valt het
    // terug op één tarief voor de hele periode.
    const prices = this.prices_ ?? new Map();
    const perBucket = prices.size > 0;
    const priceAt = (row) => (perBucket ? prices.get(row.start.getTime()) ?? rate.buy : rate.buy);

    const own = rows.reduce((total, row) => total + row.own, 0);
    const bought = rows.reduce((total, row) => total + row.bought, 0);
    const sold = rows.reduce((total, row) => total + row.sold, 0);

    const ownValue = rows.reduce((total, row) => total + row.own * priceAt(row), 0);
    const boughtValue = rows.reduce((total, row) => total + row.bought * priceAt(row), 0);

    // Alle drie als positief bedrag, met het label dat de richting draagt. Een
    // minteken voor een euroteken leest als een fout, en met "gekocht voor" is
    // er niets uit te leggen.
    const cells = [];
    // Zonder opwekteller is er geen eigen zon om te tellen, en een nul is dan
    // geen uitkomst maar een gemis.
    if (this.meters_().solar.length) {
      cells.push({ label: "Eigen zon bespaarde", value: euro(ownValue), tone: "var(--dac-solar)" });
    }
    cells.push({ label: "Stroom gekocht voor", value: euro(boughtValue), tone: "var(--dac-grid-in)" });
    if (rate.feedIn !== null) {
      cells.push({
        label: "Teruglevering leverde",
        value: euro(Math.max(0, sold * rate.feedIn)),
        tone: "var(--dac-grid-out)",
      });
    }

    card.hidden = false;
    this.$("#money").replaceChildren(
      ...cells.map((cell) => {
        const box = document.createElement("div");
        box.className = "total";
        box.style.setProperty("--tone", cell.tone);

        const label = document.createElement("span");
        label.className = "t-label";
        label.textContent = cell.label;

        const value = document.createElement("span");
        value.className = "t-value";
        value.textContent = cell.value;

        box.append(label, value);
        return box;
      })
    );

    // Hoe hard dit getal is verschilt per geval, en dat hoort erbij te staan.
    const vast = rate.basis === "je vaste tarief";
    const uitleg = vast
      ? `Gerekend met je vaste tarief van ${euro(rate.buy)} per kWh.`
      : perBucket
        ? this.period_ === "day"
          ? "Gerekend met de werkelijke prijs van elk uur, uit de geschiedenis die Home Assistant bewaart."
          : `Gerekend met de werkelijke ${
              this.period_ === "year" ? "maandgemiddelden" : "daggemiddelden"
            } uit de geschiedenis die Home Assistant bewaart. Binnen zo'n ${
              this.period_ === "year" ? "maand" : "dag"
            } wisselt de prijs nog, dus het is een benadering en geen factuur.`
        : `Gerekend met ${rate.basis}, ${euro(rate.buy)} per kWh. Van deze prijsentiteit bewaart Home Assistant nog geen geschiedenis.`;

    this.$("#money-note").textContent =
      uitleg +
      (rate.feedIn === null
        ? " Wat teruglevering opbrengt staat er niet bij, want bij een all-in prijsentiteit is de kale marktprijs er niet uit te halen."
        : "");
  }

  paintGas_() {
    const rows = this.rows_?.gas ?? [];
    const card = this.$("#gas-card");
    card.hidden = !rows.length;
    if (!rows.length) return;

    const total = rows.reduce((sum, row) => sum + row.value, 0);
    this.$("#gas-total").textContent = `${nl(total, 1)} m³ verbruikt`;

    const gasStage = this.$("#gas-stage");
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
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Gasverbruik per periode">${bars}${ticks}${hits}</svg>
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
      this.$("#gas-total").textContent = `${nl(row.value, 1)} m³ op ${bucketTitle(this.period_, row.start)}`;
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
    this.gasWhole_ = heel;
    svg.addEventListener("pointerleave", (event) => {
      if (event.pointerType !== "mouse") return;
      this.clearGasPick_();
    });
  }

  clearGasPick_() {
    if (this.gasWhole_) this.$("#gas-total").textContent = this.gasWhole_;
    for (const bar of this.$$("#gas-stage .b")) bar.classList.remove("dim");
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

  /* Twee rijen knoppen naast elkaar zijn niet uit zichzelf te onderscheiden.
     Zonder opschrift lijkt Maand bij Periode en bij Verloop hetzelfde ding. */
  .keuze { display: flex; flex-direction: column; gap: 4px; }
  .keuze-kop {
    font-size: 11px; font-weight: 600; letter-spacing: .02em;
    color: var(--dac-ink-3); text-transform: uppercase;
  }
  .segmented { display: flex; gap: 6px; flex-wrap: wrap; }
  .segmented.detail button[disabled] { opacity: .4; cursor: default; }
  .korrel-note { margin: -4px 0 12px; }
  .korrel-note:empty { display: none; }
  .segmented button {
    padding: 9px 16px;
    border-radius: var(--dac-radius-pill);
    border: 1px solid var(--dac-border);
    background: transparent;
    color: var(--dac-ink-2);
    font: inherit; font-size: 13.5px;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
    transition: border-color 200ms ease, background 200ms ease, color 200ms ease;
  }
  .segmented button[aria-pressed="true"] {
    border-color: rgba(25,143,217,0.6);
    background: var(--dac-accent-soft);
    color: var(--dac-ink);
  }

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
  .totals-title:empty::before { content: "Hele periode"; color: var(--dac-ink-3); }

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
  .legend span { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: var(--dac-ink-2); }
  .legend i { width: 12px; height: 12px; border-radius: 3px; display: inline-block; flex: 0 0 auto; }

  .money .totals { margin: 16px 0 0; }
  .saved .totals { margin: 16px 0 0; }
  .tabel-wrap { overflow-x: auto; margin-top: 16px; }
  .tabel-wrap:has(table:empty) { display: none; }
  table.beurten { border-collapse: collapse; width: 100%; font-size: 13px; }
  table.beurten th, table.beurten td {
    text-align: left; padding: 6px 10px 6px 0; border-bottom: 1px solid var(--dac-border);
    white-space: nowrap; font-variant-numeric: tabular-nums;
  }
  table.beurten th { font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--dac-ink-3); }
  table.beurten td:last-child { color: var(--dac-ink-3); }
  .note { margin: 12px 0 0; font-size: 13px; line-height: 1.5; color: var(--dac-ink-2); }
  .note:empty { display: none; }

  @media (max-width: 640px) {
    .wrap { padding: 16px max(12px, var(--dac-safe-r)) calc(48px + var(--dac-safe-b)) max(12px, var(--dac-safe-l)); }
    section.card { padding: 16px 14px 18px; }
    .stepper { margin-left: 0; flex-basis: 100%; }
    .t-value { font-size: 19px; }
  }
`;

define("dac-view-history", DacViewHistory);
