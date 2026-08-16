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
import { energy, euro, percent } from "../format.js";
import { deviceLabel, deviceLabelMap } from "../devices.js";

/** Het merkteken op het rapport. */
const LOGO_URL = new URL("../../img/domotitech-mark.png", import.meta.url).href;
import { tariff } from "../data-source.js";
import {
  PERIODS,
  combine,
  fetchDevices,
  fetchPeriod,
  fetchPrices,
  periodLabel,
  periodStart,
  withStatistics,
} from "../statistics.js";

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

/** What each bucket is called under the chart. */
function bucketLabel(period, date) {
  if (period === "day") return String(date.getHours()).padStart(2, "0");
  if (period === "year") return date.toLocaleDateString("nl-NL", { month: "short" }).replace(".", "");
  return String(date.getDate());
}

/**
 * De opmaak van het rapport.
 *
 * Licht, want papier is wit en het donkere thema van het scherm is daar
 * onleesbaar. Wel dezelfde kleuren voor dezelfde dingen, zodat wie het scherm
 * kent de grafiek herkent. Punten in plaats van pixels: dat is de maat die een
 * printer aanhoudt.
 */
const REPORT_CSS = `
  @page { size: A4; margin: 15mm 14mm; }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: #fff; color: #1a1a18;
    font: 11pt/1.5 "Segoe UI", system-ui, sans-serif;
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }
  header { display: flex; align-items: center; gap: 14px; border-bottom: 2px solid #026FA1; padding-bottom: 12px; }
  header img { width: 46px; height: 46px; }
  .merk { font-size: 15pt; font-weight: 600; }
  .merk span { color: #026FA1; }
  .waar { font-size: 10pt; color: #55534e; }
  header .rechts { margin-left: auto; text-align: right; }
  header .rechts .titel { font-size: 13pt; font-weight: 600; }
  header .rechts .sub { font-size: 9.5pt; color: #55534e; }

  h2 { font-size: 11.5pt; margin: 20px 0 9px; page-break-after: avoid; }
  .cellen { display: flex; flex-wrap: wrap; gap: 9px; }
  .cel { flex: 1 1 120px; padding: 9px 11px; border: 1px solid #e2ded6; border-radius: 8px; }
  .cel span { display: block; font-size: 8pt; letter-spacing: 0.08em; text-transform: uppercase; color: #6b6862; }
  .cel strong { font-size: 13pt; font-weight: 600; }

  svg { width: 100%; height: auto; }
  .zero { stroke: #c9c4ba; }
  .b.own { fill: #dc7300; }
  .b.bought { fill: #0f7fbb; }
  .b.sold { fill: #a30fae; }
  .b.gas { fill: #b57d00; }
  .b.dim { opacity: 1; }
  .tick { fill: #6b6862; font-family: inherit; font-size: 10px; }
  .hit, .now-line, .flag { display: none; }

  .legenda { display: flex; gap: 16px; margin-top: 8px; font-size: 9pt; color: #55534e; }
  .legenda i { display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 6px; }

  table { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 9pt; }
  th, td { padding: 4px 8px; border-bottom: 1px solid #e8e4dc; text-align: left; }
  th { font-size: 8pt; letter-spacing: 0.06em; text-transform: uppercase; color: #6b6862; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  tbody tr:nth-child(even) { background: #faf8f4; }
  tfoot td { font-weight: 600; border-top: 2px solid #d8d3c9; border-bottom: none; }
  table { page-break-inside: auto; }
  tr { page-break-inside: avoid; }

  .voet { margin-top: 18px; padding-top: 9px; border-top: 1px solid #e2ded6; font-size: 8.5pt; color: #6b6862; display: flex; }
  .voet .rechts { margin-left: auto; }
  .uitleg { font-size: 9pt; color: #55534e; margin-top: 7px; }
  .cel em { display: block; font-size: 8pt; font-style: normal; color: #6b6862; margin-top: 2px; }
  em.schat { font-style: normal; font-size: 8pt; color: #8a867e; }
`;

class DacViewHistory extends DacElement {
  constructor() {
    super();
    this.period_ = "week";
    this.offset_ = 0;
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
          <div class="segmented" id="periods">
            ${PERIODS.map(
              (item) => `<button type="button" data-period="${item.id}" aria-pressed="false">${item.label}</button>`
            ).join("")}
          </div>
          <button type="button" class="download" id="report" title="Een rapport om te bewaren of te printen">
            ${icons.compass}<span>Rapport</span>
          </button>
          <div class="stepper">
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
      </div>
    `;
  }

  afterRender() {
    for (const button of this.$$("#periods button")) {
      button.addEventListener("click", () => {
        if (this.period_ === button.dataset.period) return;
        this.period_ = button.dataset.period;
        this.offset_ = 0;
        this.load_();
      });
    }
    this.$("#report").addEventListener("click", () => this.report_());
    this.$("#prev").addEventListener("click", () => this.step_(-1));
    this.$("#next").addEventListener("click", () => this.step_(1));

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

  paintPeriod_() {
    for (const button of this.$$("#periods button")) {
      button.setAttribute("aria-pressed", String(button.dataset.period === this.period_));
    }
    this.$("#period-label").textContent = periodLabel(
      this.period_,
      periodStart(this.period_, this.offset_)
    );
    this.$("#next").disabled = this.offset_ >= 0;
  }

  paint_() {
    if (!this.rendered_) return;
    this.paintPeriod_();

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
   * Deze periode als rapport, om te bewaren of door te sturen.
   *
   * Via het afdrukvenster van de browser, waar "Bewaren als pdf" een van de
   * bestemmingen is. Dat scheelt een bibliotheek van honderden kilobytes in een
   * paneel dat bewust zonder bouwstap draait, en het levert een betere pdf op:
   * de grafiek gaat als vectortekening mee en blijft scherp op elk formaat.
   *
   * Op papier is het donkere thema onbruikbaar, dus het rapport is licht. Wel
   * dezelfde kleuren voor dezelfde dingen, zodat wie het scherm kent de grafiek
   * meteen herkent.
   *
   * In een eigen iframe en niet in een nieuw venster: dat laatste vangen
   * popupblokkers weg, en in de app van Home Assistant is het helemaal de vraag
   * of het opengaat.
   */
  reportHtml_() {
    const rows = this.rowsShown_ ?? [];
    if (!rows.length) return "";

    const prices = this.prices_ ?? new Map();
    const rate = tariff(this.feed_, this.settings_?.contract);
    const hasSolar = this.meters_().solar.length > 0;
    const gas = new Map((this.rows_?.gas ?? []).map((row) => [row.start.getTime(), row.value]));
    const totals = this.totals_ ?? {};

    const woning = (this.settings_?.installation?.home_name ?? "").trim();
    const periode = periodLabel(this.period_, periodStart(this.period_, this.offset_));
    const korrel = { day: "Per uur", week: "Per dag", month: "Per dag", year: "Per maand" }[
      this.period_
    ];

    const cel = (label, waarde, sub) =>
      `<div class="cel"><span>${label}</span><strong>${waarde}</strong>${
        sub ? `<em>${sub}</em>` : ""
      }</div>`;

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

    const regels = rows
      .map((row) => {
        const prijs = prijsBij(row);
        const cellen = [bucketTitle(this.period_, row.start)];
        if (hasSolar) cellen.push(kwh(row.own + row.sold), kwh(row.used), kwh(row.own));
        cellen.push(kwh(row.bought), kwh(row.sold));
        if (gas.size) cellen.push(`${nl(gas.get(row.start.getTime()) ?? 0, 2)} m³`);
        if (rate.buy !== null) {
          cellen.push(prijs === null ? "" : euro(prijs), euro(row.bought * (prijs ?? 0)));
        }
        return `<tr>${cellen
          .map((c, i) => `<td${i ? ' class="num"' : ""}>${c}</td>`)
          .join("")}</tr>`;
      })
      .join("");

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

    const apparatenHtml = !apparaten.length
      ? ""
      : [
          "<h2>Per apparaat</h2>",
          '<table><thead><tr><th>Apparaat</th><th class="num">Verbruik</th>',
          rate.buy === null ? "" : '<th class="num">Kosten</th>',
          aandeelKlopt ? '<th class="num">Aandeel</th>' : "",
          "</tr></thead><tbody>",
          apparaten
            .map(
              (device) =>
                `<tr><td>${device.label}${
                  device.exact ? "" : ' <em class="schat">bij benadering</em>'
                }</td><td class="num">${kwh(device.kwh)}</td>${
                  rate.buy === null ? "" : `<td class="num">${euro(device.euro)}</td>`
                }${
                  aandeelKlopt
                    ? `<td class="num">${Math.round((device.kwh / totals.used) * 100)} %</td>`
                    : ""
                }</tr>`
            )
            .join(""),
          "</tbody></table>",
          '<p class="uitleg">Van apparaten zonder eigen energieteller wordt het verbruik afgeleid uit het gemiddelde vermogen. Dat is nauwkeurig genoeg om te zien waar je stroom heen gaat, maar het is geen meterstand. Vul bij Apparaten een energieteller in als je die hebt, dan klopt het tot op de komma.' +
            (aandeelKlopt
              ? ""
              : " Deze schattingen tellen samen op tot meer dan het verbruik van de woning, dus staat er geen aandeel bij.") +
            "</p>",
        ].join("");

    const html = [
      '<!doctype html><html lang="nl"><head><meta charset="utf-8">',
      `<title>${periode}</title><style>${REPORT_CSS}</style></head><body>`,

      "<header>",
      `<img src="${LOGO_URL}" alt="">`,
      '<div><div class="merk">DomotiApp <span>Coach</span></div>',
      woning ? `<div class="waar">${woning}</div>` : "",
      "</div>",
      `<div class="rechts"><div class="titel">${periode}</div><div class="sub">${korrel}</div></div>`,
      "</header>",

      "<h2>Energie</h2>",
      '<div class="cellen">',
      hasSolar ? cel("Opgewekt", kwh(totals.solar)) : "",
      hasSolar ? cel("Verbruikt", kwh(totals.used)) : "",
      cel("Van het net", kwh(totals.bought)),
      cel("Naar het net", kwh(totals.sold)),
      totals.selfUse === null || totals.selfUse === undefined
        ? ""
        : cel("Zelf gebruikt", `${percent(totals.selfUse).value} %`),
      gas.size ? cel("Gas", `${nl([...gas.values()].reduce((a, b) => a + b, 0), 1)} m³`) : "",
      "</div>",

      rate.buy === null
        ? ""
        : [
            "<h2>In geld</h2>",
            '<div class="cellen">',
            hasSolar ? cel("Eigen zon bespaarde", euro(waarde("own"))) : "",
            cel("Stroom gekocht voor", euro(waarde("bought"))),
            rate.feedIn === null
              ? ""
              : cel("Teruglevering leverde", euro(Math.max(0, (totals.sold ?? 0) * rate.feedIn))),
            "</div>",
            `<p class="uitleg">${this.$("#money-note").textContent}</p>`,
          ].join(""),

      "<h2>Verloop</h2>",
      this.$("#stage svg")?.outerHTML ?? "",
      '<div class="legenda">',
      hasSolar ? '<span><i style="background:#dc7300"></i>Eigen zon gebruikt</span>' : "",
      '<span><i style="background:#0f7fbb"></i>Van het net</span>',
      '<span><i style="background:#a30fae"></i>Naar het net</span>',
      "</div>",

      apparatenHtml,

      "<h2>Alle cijfers</h2>",
      "<table><thead><tr>",
      kop.map((k, i) => `<th${i ? ' class="num"' : ""}>${k}</th>`).join(""),
      "</tr></thead><tbody>",
      regels,
      "</tbody><tfoot><tr>",
      totaalCellen.map((c, i) => `<td${i ? ' class="num"' : ""}>${c}</td>`).join(""),
      "</tr></tfoot></table>",

      '<div class="voet">',
      `<span>Gemaakt op ${new Date().toLocaleDateString("nl-NL", {
        day: "numeric",
        month: "long",
        year: "numeric",
      })}</span>`,
      '<span class="rechts">domotitech.nl</span>',
      "</div></body></html>",
    ].join("");

    return html;
  }

  /** Het rapport naar het afdrukvenster, waar "bewaren als pdf" een keuze is. */
  report_() {
    const html = this.reportHtml_();
    if (!html) return;

    const frame = document.createElement("iframe");
    frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;opacity:0";
    document.body.appendChild(frame);

    const doc = frame.contentDocument;
    doc.open();
    doc.write(html);
    doc.close();

    // Wachten tot het logo binnen is, anders staat er een lege plek op papier.
    const printen = () => {
      frame.contentWindow.focus();
      frame.contentWindow.print();
      setTimeout(() => frame.remove(), 1000);
    };
    const logo = doc.querySelector("img");
    if (logo && !logo.complete) {
      logo.addEventListener("load", printen, { once: true });
      logo.addEventListener("error", printen, { once: true });
    } else {
      setTimeout(printen, 60);
    }
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
    const H = 90;
    const top = Math.max(...rows.map((row) => row.value), 0.001);
    const colW = Math.min(W / rows.length, 64);
    const inset = (W - colW * rows.length) / 2;
    const barW = Math.max(1.5, colW - (colW < 9 ? 1 : Math.min(8, colW * 0.22)));

    const bars = rows
      .map((row, index) => {
        const height = (row.value / (top * 1.05)) * (H - 8);
        if (height <= 0.4) return "";
        const x = inset + index * colW + (colW - barW) / 2;
        return `<path class="b gas" d="${block(x, barW, H - height, height, Math.min(4, barW / 2))}"/>`;
      })
      .join("");

    const hits = rows
      .map(
        (row, index) =>
          `<rect class="hit" data-index="${index}" x="${inset + index * colW}" y="0"
                 width="${colW}" height="${H}"/>`
      )
      .join("");

    gasStage.innerHTML = `
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Gasverbruik per periode">${bars}${hits}</svg>
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

  .controls { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }

  .segmented { display: flex; gap: 6px; flex-wrap: wrap; }
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
