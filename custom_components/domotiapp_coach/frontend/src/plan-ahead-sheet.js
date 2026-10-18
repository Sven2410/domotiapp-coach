/**
 * Wat de coach van plan is, uur voor uur, tot de auto vol moet zijn.
 *
 * De eigenaar op 30-08-2026: "ik wil een knop op de laadpaalkaart dat ik kan zien wat
 * de coach van plan is met hele tijdlijn tot dat hij vol moet zijn." Dat is de
 * vraag die een coach die uren stilstaat oproept, en het antwoord stond tot nu
 * toe in één zin op de kaart: "wacht op een goedkoper uur." Dat klopt, maar het
 * zegt niet wélke uren, en dus ook niet of er iets misgaat.
 *
 * **Alles hier komt uit de coach zelf en wordt hier niets uitgerekend.** Dat is
 * met opzet. Een scherm dat zijn eigen sommen doet loopt vroeg of laat uit de
 * pas met wat er werkelijk gebeurt, en dan wacht de bewoner op een uur dat de
 * coach niet gekozen heeft. `timeline()` in planner.py maakt de lijst, met
 * precies dezelfde aanroep van `cheapest_hours` als het besluit van die minuut.
 */

import { batterijVooruit, standNaam } from "./battery.js";
import { perUur, prijsAs, prijsBalken, prijsCss, prijsStrook, prijsUitleg } from "./prijsgrafiek.js";

/**
 * Kwartierblokken van de paal samengenomen tot een regel per uur (v0.88.1).
 * Opgeteld en gemiddeld, verder niets: welke kwartieren laden komt uit het
 * plan, en de grafiek erboven laat ze elk apart zien.
 */
export function paalPerUur(blokken = []) {
  return perUur(blokken).map((groep) => {
    if (groep.length === 1) return groep[0];
    const laden = groep.filter((b) => b.charging);
    const prijzen = groep.map((b) => b.price).filter((p) => p !== null && p !== undefined);
    const som = (lijst, veld) => lijst.reduce((t, b) => t + (Number(b[veld]) || 0), 0);
    const uren = laden.reduce((t, b) => t + (new Date(b.end) - new Date(b.start)) / 3600000, 0);
    const kwh = som(groep, "kwh");
    const eerste = laden[0] ?? groep[0];
    return {
      start: groep[0].start,
      end: groep[groep.length - 1].end,
      price: prijzen.length ? prijzen.reduce((t, p) => t + p, 0) / prijzen.length : null,
      charging: laden.length > 0,
      why: laden.length && laden.length < groep.length
        ? `${eerste.why} (in ${laden.length} van de ${groep.length} kwartieren)`
        : eerste.why,
      solar_kwh: som(groep, "solar_kwh"),
      accu_kwh: som(groep, "accu_kwh"),
      kwh,
      amps: Math.max(0, ...laden.map((b) => Number(b.amps) || 0)),
      kw: uren > 0 ? kwh / uren : 0,
    };
  });
}
import { DacElement, define } from "./base.js";
import { icons } from "./icons.js";
import { sheetCss } from "./theme.js";

const css = /* css */ `
  ${sheetCss}
  ${prijsCss}

  .kop {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 10px;
    margin-bottom: 14px;
  }
  .kop .vak {
    padding: 10px 12px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(var(--dac-veil),0.03);
  }
  .kop .label {
    font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase;
    color: var(--dac-ink-3); font-weight: 700;
  }
  .kop .waarde {
    font-size: 17px; font-weight: 700; color: var(--dac-ink-1);
    font-variant-numeric: tabular-nums; margin-top: 2px;
  }
  .kop .bij { font-size: 11.5px; color: var(--dac-ink-3); }

  .uren { display: flex; flex-direction: column; gap: 4px; }

  .uur {
    display: grid;
    grid-template-columns: 56px 74px 62px 1fr;
    align-items: center;
    gap: 10px;
    padding: 9px 11px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(var(--dac-veil),0.02);
    font-size: 13px;
  }
  /* Een uur waarin geladen wordt is het nieuws, dus dat is het enige dat kleur
     krijgt. Alles kleuren is hetzelfde als niets kleuren. */
  .uur.laadt {
    border-color: rgba(56,189,124,0.45);
    background: rgba(56,189,124,0.10);
  }
  .uur.levert {
    border-color: rgba(240,160,40,0.5);
    background: rgba(240,160,40,0.10);
  }
  .uur.levert .wat { color: var(--dac-ink-2); }
  .uur.nu { outline: 2px solid var(--dac-accent-hi); outline-offset: 1px; }

  .uur .tijd { font-weight: 700; font-variant-numeric: tabular-nums; color: var(--dac-ink-1); }
  .uur .prijs { font-variant-numeric: tabular-nums; color: var(--dac-ink-2); }
  /* Hoeveel er van dit uur uit je eigen dak kan komen. Alleen ingevuld waar er
     iets staat, want een kolom vol streepjes leest als een storing. */
  .uur .zon {
    font-variant-numeric: tabular-nums; font-size: 12px;
    color: var(--dac-warn);
  }
  .uur .wat { color: var(--dac-ink-3); font-size: 12.5px; }
  .uur.laadt .wat { color: var(--dac-ink-2); }

  /* Een batterij: tijd, prijs, accustand aan het eind van het uur, en wat hij
     doet. De tijd is breder, want na middernacht staat er "morgen" voor. */
  .uur.accu { grid-template-columns: 92px 62px 42px 1fr; }
  .uur .soc { font-variant-numeric: tabular-nums; color: var(--dac-ink-2); }

  .leeg {
    padding: 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px dashed var(--dac-border-hi);
    color: var(--dac-ink-3);
    font-size: 13px; line-height: 1.5;
  }

  .voet { margin-top: 12px; font-size: 12px; line-height: 1.55; color: var(--dac-ink-3); }

  /* Onder de 360 px vallen drie kolommen om. De reden mag dan onder de tijd
     staan; wat er niet mag is dat de kaart zijwaarts gaat schuiven. */
  @media (max-width: 360px) {
    .uur { grid-template-columns: 52px 68px 1fr; }
    .uur .wat { grid-column: 1 / -1; }
    .uur.accu { grid-template-columns: 1fr 62px 42px; }
  }
`;

/** Een tijdstip uit de coach als kloktijd, of een streepje. */
const klok = (iso) => {
  if (!iso) return "–";
  const moment = new Date(iso);
  return Number.isNaN(moment.getTime())
    ? "–"
    : `${String(moment.getHours()).padStart(2, "0")}:${String(moment.getMinutes()).padStart(2, "0")}`;
};

// Een tijdstip met de dag erbij zodra het niet vandaag is. Een plan dat over
// het weekend loopt zegt anders "uiterlijk beginnen 22:36" en dan zoek je op
// de verkeerde avond. Zonder dag als het wel vandaag is, want "vr 22:36" leest
// op vrijdag als een raadsel.
const DAGEN = ["zo", "ma", "di", "wo", "do", "vr", "za"];
const wanneer = (iso) => {
  if (!iso) return "–";
  const moment = new Date(iso);
  if (Number.isNaN(moment.getTime())) return "–";
  const vandaag = new Date();
  const zelfde =
    moment.getFullYear() === vandaag.getFullYear() &&
    moment.getMonth() === vandaag.getMonth() &&
    moment.getDate() === vandaag.getDate();
  return zelfde ? klok(iso) : `${DAGEN[moment.getDay()]} ${klok(iso)}`;
};

const kwh = (value) =>
  value === null || value === undefined
    ? "–"
    : `${Number(value).toFixed(1).replace(".", ",")} kWh`;

const euro = (value) =>
  value === null || value === undefined
    ? ""
    : `€ ${Number(value).toFixed(3)}`.replace(".", ",");

const uren = (value) => {
  if (value === null || value === undefined) return "–";
  const totaal = Math.round(Number(value) * 60);
  const u = Math.floor(totaal / 60);
  const m = totaal % 60;
  return u ? `${u} u ${String(m).padStart(2, "0")} m` : `${m} min`;
};

export class DacPlanAheadSheet extends DacElement {
  static css = css;

  constructor() {
    super();
    this.plan_ = null;
    this.besluit_ = null;
    this.label_ = "";
    this.reason_ = "";
  }

  render() {
    return /* html */ `
      <dialog class="sheet wide" tabindex="-1" aria-labelledby="vooruit-title">
        <div class="sheet-head">
          <div>
            <div class="eyebrow">Wat gaat hij doen</div>
            <h3 id="vooruit-title"></h3>
          </div>
          <button class="sheet-close" type="button" id="vooruit-close" aria-label="Sluiten">
            ${icons.close}
          </button>
        </div>
        <p class="sheet-sub" id="vooruit-nu"></p>

        <div class="kop" id="vooruit-kop"></div>
        <div class="prijs-blok" id="vooruit-prijs" hidden></div>
        <div class="uren" id="vooruit-uren"></div>
        <p class="voet" id="vooruit-voet"></p>
      </dialog>
    `;
  }

  afterRender() {
    const dialog = this.$("dialog");
    this.$("#vooruit-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  }

  /** Openen met de tijdlijn zoals de coach hem net heeft uitgerekend. */
  open(label, besluit) {
    // Een ander apparaat: geen gekozen moment van het vorige, en de grafiek
    // opnieuw vanaf het begin.
    this.gekozenStart_ = null;
    this.prijsSleutel_ = null;
    this.label_ = label || "";
    this.besluit_ = besluit ?? null;
    this.plan_ = besluit?.plan_ahead ?? null;
    this.reason_ = [besluit?.reason, besluit?.plan].filter(Boolean).join(" ");
    this.paint_();
    const dialog = this.$("dialog");
    if (!dialog.open) dialog.showModal();
  }

  /** Bijwerken terwijl hij openstaat, want de coach denkt elke minuut opnieuw. */
  update(besluit) {
    if (!this.rendered_ || !this.$("dialog")?.open) return;
    this.besluit_ = besluit ?? null;
    this.plan_ = besluit?.plan_ahead ?? null;
    this.reason_ = [besluit?.reason, besluit?.plan].filter(Boolean).join(" ");
    this.paint_();
  }

  close() {
    this.$("dialog")?.close();
  }

  /**
   * Alles opnieuw, behalve de prijsgrafiek als die niet veranderd is (v0.129.1).
   * De eigenaar op 19-10-2026: "als ik de slider naar rechts swipe schiet hij
   * weer terug naar links." De coach geeft bij een batterij om de paar seconden
   * een besluit, en elke keer werd de grafiek opnieuw gebouwd, terug naar het begin.
   */
  paint_() {
    this.prijsGezet_ = false;
    this.paintInhoud_();
    if (!this.prijsGezet_) this.paintPrijs_(null);
  }

  paintInhoud_() {
    this.$("#vooruit-title").textContent = this.label_;
    this.$("#vooruit-nu").textContent = this.reason_;

    const plan = this.plan_;
    const kop = this.$("#vooruit-kop");
    const uurlijst = this.$("#vooruit-uren");
    kop.replaceChildren();
    uurlijst.replaceChildren();

    // Een thuisbatterij heeft geen tijdlijn tot een klaar-tijd maar een plan
    // per uur tot de prijzen ophouden; zie `batterijVooruit` in battery.js.
    const accu = batterijVooruit(this.besluit_);
    if (accu) {
      this.paintAccu_(accu);
      return;
    }

    if (!plan) {
      this.$("#vooruit-voet").textContent = "";
      const leeg = document.createElement("div");
      leeg.className = "leeg";
      leeg.textContent =
        "De coach heeft nog geen plan. Dat komt zodra hij een ronde gedraaid heeft.";
      uurlijst.append(leeg);
      return;
    }

    // "Op vol vermogen" is een som en geen plan: zo lang zou het duren als
    // hij nu op alles wat er past door zou laden, en daar komt "uiterlijk
    // beginnen" uit. Het plan zelf staat in de uren eronder en gaat meestal
    // langzamer, want de goedkoopste uren zijn zelden aaneengesloten. De eigenaar op
    // 04-09-2026, met "laadtijd 6 u 23 m op 15 A" naast acht uur op 6 A:
    // "mij lijkt het toch logisch dynamisch te laden".
    //
    // En "vol rond" alleen als het plan het hele tekort dekt. Dekt het minder,
    // dan staat er wat er gepland is en waarom de rest ontbreekt; zie
    // `planned_kwh` in planner.py. Een server van vóór v0.47.3 stuurt dat veld
    // niet mee, en dan blijft het bij "vol rond" zoals het was.
    const nodig = Number(plan.kwh_needed);
    const gepland = Number(plan.planned_kwh);
    const tekort =
      plan.planned_kwh !== null && plan.planned_kwh !== undefined &&
      Number.isFinite(nodig) && gepland > 0 && gepland + 0.05 < nodig;
    const laatste = tekort
      ? ["Gepland", kwh(gepland),
          plan.solar_only
            ? `van ${kwh(nodig)}; de rest zodra de prijzen er zijn`
            : `van ${kwh(nodig)}; meer past er niet vóór de klaar-tijd`]
      : ["Vol rond", wanneer(plan.expected_done),
          plan.deadline ? `klaar om ${wanneer(plan.deadline)}` : "geen klaar-tijd"];

    // Aan de paal, en wat daarvan in de accu komt (v0.94.0). De bewoner van de
    // eerste woning rekende 78 kWh x 30% = 23,4 en las 26,0: dat was aan de
    // paal, met 10% laadverlies dat niemand gemeten had.
    const inAccu = plan.kwh_in_car ?? null;
    const verlies = plan.efficiency ? Math.round((1 - plan.efficiency) * 100) : null;
    const nogBij = inAccu === null || verlies === null
      ? ""
      : `aan de paal; ${kwh(inAccu)} in de auto, ${verlies}% laadverlies `
        + (plan.efficiency_measured ? "(gemeten aan deze auto)" : "(aangenomen, nog niet gemeten)");
    this.paintKop_([
      ["Nog te laden", kwh(plan.kwh_needed), nogBij],
      ["Op vol vermogen", uren(plan.hours_needed),
        // Sinds v0.61.0 kan dit een meting zijn: wat er de afgelopen uren
        // gemiddeld onder de zekering overbleef, bij een huis met een
        // warmtepomp die om het kwartier aangaat. Zie structural_ceiling.
        // Sinds v0.98.0 telt ook de zekering zelf, als vast plafond: op een
        // groep van 16 A krijgt de paal nooit meer dan 14 A, ook niet direct
        // na een herstart, als er nog niets gemeten is.
        plan.amps
          ? plan.measured
            ? `${plan.amps} A, wat er de afgelopen uren gemiddeld overbleef onder je zekering`
            : typeof plan.fuse_name === "string"
              ? `${plan.amps} A, meer past er niet onder ${plan.fuse_name ? `de zekering van de groep ${plan.fuse_name}` : "je zekering"}`
              : `${plan.amps} A, wat paal en auto kunnen`
          : ""],
      ["Uiterlijk beginnen", wanneer(plan.latest_start), "met een uur speling"],
      laatste,
      // De thuisbatterij helpt mee (v0.95.0): wat er daardoor niet van het net
      // komt. De bewoner van de eerste woning: "de EV-laadplanning zou nu moeten
      // weten dat de accu mee gaat helpen."
      ...(Number(plan.accu_kwh) > 0.05
        ? [["Uit je thuisbatterij", kwh(plan.accu_kwh),
            Number.isFinite(plan.accu_to) ? `tot hij op ${plan.accu_to}% staat` : "de rest komt van het net"]]
        : []),
    ]);

    // De prijs per uur met de laaduren in groen, zoals evcc het laat zien.
    // Van het net is wat er in dat uur geladen wordt min wat het dak geeft.
    this.paintPrijs_(
      (plan.blocks ?? []).map((b) => ({
        start: b.start, end: b.end, price: b.price, groen: Boolean(b.charging),
        kwh: b.kwh === undefined
          ? undefined
          : Math.max(0, Number(b.kwh) - Number(b.solar_kwh || 0) - Number(b.accu_kwh || 0)),
      })),
      "laden"
    );

    const nu = Date.now();
    for (const blok of paalPerUur(plan.blocks ?? [])) {
      const rij = document.createElement("div");
      rij.className = "uur";
      if (blok.charging) rij.classList.add("laadt");
      const start = new Date(blok.start).getTime();
      const eind = new Date(blok.end).getTime();
      if (start <= nu && nu < eind) rij.classList.add("nu");

      const tijd = document.createElement("span");
      tijd.className = "tijd";
      tijd.textContent = klok(blok.start);
      const prijs = document.createElement("span");
      prijs.className = "prijs";
      prijs.textContent = euro(blok.price);
      // In een laaduur staat er hoe hard: de stroom in de kolom, het vermogen
      // en het zonaandeel in de zin. "4,1 kWh zon" stond er over een uur
      // waarin het dak 2,4 gaf: dat was wat er in de auto ging, zon plus net.
      // De eigenaar op 04-09-2026: "laat sowieso zien hoeveel ampère hij laadt en
      // kW." Een server van vóór v0.47.5 stuurt geen amps mee; dan blijft de
      // zonkolom zoals hij was.
      const zonTekst = blok.solar_kwh > 0.05
        ? `${Number(blok.solar_kwh).toFixed(1).replace(".", ",")} kWh zon`
        : "";
      const accuTekst = Number(blok.accu_kwh) > 0.05
        ? `${Number(blok.accu_kwh).toFixed(1).replace(".", ",")} kWh uit je thuisbatterij`
        : "";
      const waarvan = [zonTekst, accuTekst].filter(Boolean).join(" en ");
      const zon = document.createElement("span");
      zon.className = "zon";
      const wat = document.createElement("span");
      wat.className = "wat";
      if (blok.charging && blok.amps) {
        zon.textContent = `${blok.amps} A`;
        const kw = `${Number(blok.kw).toFixed(1).replace(".", ",")} kW`;
        wat.textContent = waarvan
          ? `Laden op ${kw}, waarvan ${waarvan}: ${blok.why}`
          : `Laden op ${kw}: ${blok.why}`;
      } else {
        zon.textContent = zonTekst;
        wat.textContent = blok.charging ? `Laden, ${blok.why}` : `Wachten, ${blok.why}`;
      }

      rij.append(tijd, prijs, zon, wat);
      uurlijst.append(rij);
    }

    if (!(plan.blocks ?? []).length) {
      const leeg = document.createElement("div");
      leeg.className = "leeg";
      leeg.textContent =
        plan.note || "Er is niets te plannen: er is geen auto aangesloten of er zijn geen prijzen.";
      uurlijst.append(leeg);
      this.$("#vooruit-voet").textContent = "";
      return;
    }

    const geschat = plan.estimated
      ? " De zon per uur is een schatting: er staat geen uurverwachting klaar, dus " +
        "de dagverwachting is over de daglichturen verdeeld."
      : "";
    const gemeten = plan.measured
      ? ` De afgelopen uren bleef er gemiddeld ${plan.amps} A over voor de paal, omdat ` +
        "je huis bij vlagen veel trok. Daarmee rekent hij voor de uren die komen, " +
        "zodat hij op tijd begint."
      : "";
    // Sinds v0.67.0: de zonverwachting bijgesteld met wat de meter gaf. Zie
    // solar_measured_note in planner.py.
    const zon = plan.solar_note ? ` ${plan.solar_note}` : "";
    this.$("#vooruit-voet").textContent =
      (plan.note ||
        "Dit is wat de coach nu van plan is. Hij vergelijkt elk uur tot je klaar-tijd, " +
          "en per uur wat je eigen zon kost tegen wat het net kost. Verandert je " +
          "accustand, de prijs of de verwachting, dan rekent hij het opnieuw uit.") +
      geschat +
      gemeten +
      zon;
  }

  /**
   * De prijsgrafiek boven de uren, of niets bij een vast contract.
   *
   * De bewoner van de eerste woning op 23-09-2026, over evcc: "zo heb je als
   * gebruiker een visuele check dat de laadpaal inderdaad op de goedkoopste
   * momenten gaat laden." Zie prijsgrafiek.js.
   */
  /**
   * `wat` zijn de woorden van de legenda (v0.130.0). De bewoner van de eerste
   * woning op 19-10-2026, bij de grafiek van de batterij: "Laden van het net",
   * "Ontladen aan het net", "Eigen gebruik of Nul op de meter"; "hij wacht" klopte
   * daar niet, want dan voedt de batterij het huis. Bij de laadpaal blijft het
   * laden en wachten.
   */
  paintPrijs_(rijen, wat = { groen: "Laden", wacht: "Wacht" }) {
    const woorden = { leveren: "Ontladen aan het net", ...wat };
    if (rijen) this.prijsGezet_ = true;
    const blok = this.$("#vooruit-prijs");
    // Dezelfde prijzen en hetzelfde plan: laten staan zoals hij staat, met waar
    // je naartoe veegde en wat je aantikte.
    const sleutel = rijen ? JSON.stringify([rijen, wat]) : null;
    if (sleutel !== null && sleutel === this.prijsSleutel_) return;
    this.prijsSleutel_ = sleutel;
    // Toch opnieuw: dan op dezelfde plek verder.
    const veegPlek = blok.querySelector?.(".prijs-strook")?.scrollLeft ?? 0;
    blok.replaceChildren();
    const berekend = rijen ? prijsBalken(rijen) : null;
    blok.hidden = !berekend;
    if (!berekend) return;

    const kop = document.createElement("div");
    kop.className = "prijs-kop";
    const links = document.createElement("span");
    links.textContent = berekend.stap <= 20 ? "Prijs per kwartier" : "Prijs per uur";
    kop.append(links);
    // Rechts alleen wat een kWh van het net gemiddeld kost, en alleen waar dat
    // nergens anders staat (v0.130.1). De bewoner van de eerste woning op
    // 19-10-2026, bij "in deze uren niets van het net" boven de grafiek van de
    // batterij: "overbodig veldje nu, door dat nieuwe tekstveld erboven". Bij
    // de batterij staat "Van het net" al in een vak erboven.
    if (berekend.gemiddeld !== null && woorden.gemiddelde !== false) {
      const rechts = document.createElement("span");
      const sterk = document.createElement("strong");
      sterk.textContent = `€ ${berekend.gemiddeld.toFixed(3).replace(".", ",")}`;
      rechts.append("gemiddeld ", sterk, " per kWh van het net");
      kop.append(rechts);
    }

    const legenda = document.createElement("div");
    legenda.className = "prijs-legenda";
    const levert = berekend.balken.some((b) => b.leveren);
    for (const [klasse, tekst] of [["groen", woorden.groen], ...(levert ? [["leveren", woorden.leveren]] : []), ["", woorden.wacht]]) {
      const item = document.createElement("span");
      const blokje = document.createElement("i");
      if (klasse) blokje.className = klasse;
      item.append(blokje, tekst);
      legenda.append(item);
    }
    // Tik op een staafje: de tijd en de prijs van dat moment (v0.129.0). De
    // eigenaar op 18-10-2026: "als ik op een bar klik in de diagram, wil ik de
    // prijs zien van dat moment." De tooltip van de muis werkt op een telefoon niet.
    // Bovenaan het moment: eerst nu, na een tik het gekozen blok, zoals de app
    // van een leverancier dat doet (v0.129.0).
    const moment = document.createElement("div");
    moment.className = "prijs-moment";
    const zet = (i) => {
      const u = prijsUitleg(berekend, i, woorden);
      moment.replaceChildren();
      if (!u) return;
      for (const [klasse, tekst] of [["wanneer", u.kop], ["bedrag", u.prijs], ["wat", u.onder]]) {
        const regel = document.createElement("span");
        regel.className = klasse;
        regel.textContent = tekst;
        moment.append(regel);
      }
      moment.className = i === 0 ? "prijs-moment" : "prijs-moment gekozen";
    };
    const strook = prijsStrook(berekend);
    const kies = (i) => {
      for (const ander of strook.querySelectorAll("g.gekozen")) ander.classList.remove("gekozen");
      if (i > 0) strook.querySelector(`g[data-i="${i}"]`)?.classList.add("gekozen");
      zet(i);
    };
    strook.addEventListener("click", (ev) => {
      const g = ev.target?.closest?.("g[data-i]");
      if (!g) return;
      const i = Number(g.getAttribute("data-i"));
      // Onthouden op begintijd: de coach denkt elke minuut opnieuw en dan wordt
      // dit opnieuw getekend, en een keuze die dan terugspringt naar nu is weg.
      this.gekozenStart_ = berekend.blokken[i]?.start ?? null;
      kies(i);
    });
    const eerder = this.gekozenStart_ ? berekend.blokken.findIndex((b) => b.start === this.gekozenStart_) : -1;
    kies(eerder > 0 ? eerder : 0);
    const raam = document.createElement("div");
    raam.className = "prijs-raam";
    raam.append(prijsAs(berekend), strook);
    blok.append(moment, kop, raam, legenda);
    if (veegPlek && globalThis.requestAnimationFrame) {
      globalThis.requestAnimationFrame(() => { strook.scrollLeft = veegPlek; });
    }
  }

  /** De vakken bovenaan: label, waarde en een regel eronder. */
  paintKop_(vakken) {
    const kop = this.$("#vooruit-kop");
    for (const [label, waarde, bij] of vakken) {
      const vak = document.createElement("div");
      vak.className = "vak";
      const kl = document.createElement("div");
      kl.className = "label";
      kl.textContent = label;
      const wa = document.createElement("div");
      wa.className = "waarde";
      wa.textContent = waarde;
      vak.append(kl, wa);
      if (bij) {
        const bj = document.createElement("div");
        bj.className = "bij";
        bj.textContent = bij;
        vak.append(bj);
      }
      kop.append(vak);
    }
  }

  /** Het plan van een thuisbatterij, uur voor uur. */
  paintAccu_(accu) {
    // De nachtzin staat in de voet; bovenaan alleen wat hij nu doet.
    this.$("#vooruit-nu").textContent = this.besluit_?.reason ?? "";
    this.paintKop_(accu.kop.map((v) => [v.label, v.waarde, v.bij]));
    this.paintPrijs_(
      (this.besluit_?.hours ?? []).map((u) => ({
        start: u.start, end: u.end, price: u.price,
        groen: Number(u.grid_kwh) > 0.05, kwh: Number(u.grid_kwh) || 0,
        // Aan het net leveren (handelen) heeft een eigen kleur (v0.129.0).
        leveren: Number(u.grid_kwh) < -0.05,
        label: standNaam(u.mode),
      })),
      { groen: "Laden van het net", leveren: "Ontladen aan het net", wacht: "Nul op de meter", gemiddelde: false }
    );
    const uurlijst = this.$("#vooruit-uren");
    const nu = Date.now();
    for (const uur of accu.uren) {
      const rij = document.createElement("div");
      rij.className = "uur accu";
      // Laden van het net is wat geld kost, dus dat krijgt kleur; de rest is
      // de batterij die met het huis en de zon meebeweegt.
      if (uur.net) rij.classList.add("laadt");
      // Dezelfde kleuren als de grafiek (v0.130.0): oranje als hij aan het net levert.
      if (uur.levert) rij.classList.add("levert");
      const start = new Date(uur.start).getTime();
      const eind = new Date(uur.end).getTime();
      if (start <= nu && nu < eind) rij.classList.add("nu");
      for (const [klasse, tekst] of [
        ["tijd", uur.tijd], ["prijs", uur.prijs], ["soc", uur.soc], ["wat", uur.wat],
      ]) {
        const vak = document.createElement("span");
        vak.className = klasse;
        vak.textContent = tekst;
        rij.append(vak);
      }
      uurlijst.append(rij);
    }
    if (!accu.uren.length) {
      const leeg = document.createElement("div");
      leeg.className = "leeg";
      leeg.textContent =
        "De coach heeft nog geen plan: er zijn geen prijzen, of hij weet de accustand niet.";
      uurlijst.append(leeg);
    }
    this.$("#vooruit-voet").textContent =
      (accu.voet ? `${accu.voet} ` : "") +
      "De accustand is die aan het eind van het uur. Dit is wat de coach nu van plan " +
      "is; verandert de zon, het huis of de prijs, dan rekent hij het elke minuut opnieuw uit.";
  }
}

define("dac-plan-ahead-sheet", DacPlanAheadSheet);
