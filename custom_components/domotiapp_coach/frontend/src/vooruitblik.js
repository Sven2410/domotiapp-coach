/**
 * De vooruitblik op het overzicht (v0.133.0): in één grafiek wat er de komende
 * uren gebeurt.
 *
 * De eigenaar op 19-10-2026, bij voorbeelden van andere apps (een
 * dynamisch-contract-app, een energie-app met een prijsgrafiek, en de bèta van
 * een optimizer): "Wat helemaal vet zou zijn is als er nog een overall
 * predictive modus komt op je hoofd dashboard", met de prijs in kleur, de zon,
 * de vermogens per apparaat en knoppen om te kiezen wat je ziet; en "Dan zie je
 * in één oogopslag wat er toekomstig gaat gebeuren, en krijg je een visuele
 * bevestiging of je ingestelde prioriteiten ook kloppen."
 *
 * Wat er staat komt van de coach (`domotiapp_coach/forecast`, `vooruitblik` in
 * coach.py): de prijzen, de zonverwachting en het huisverbruik waar hij zelf mee
 * plant, en per apparaat het plan dat hij al had. Hier wordt niets bijgeschat;
 * wat de coach niet weet staat er niet.
 *
 * Bovenaan de prijs per uur, in de kleuren van Voorkeuren. Daaronder de
 * vermogens: de apparaten gestapeld in de volgorde van de voorrang (eerst die
 * bij zon, dan die bij planningen), ontladen van de batterij onder de lijn, de
 * zon als vlak, het huis als stippellijn en de accustand als lijn op zijn eigen
 * schaal. Vegen gaat vooruit in de tijd, tikken op een uur zegt wat er dan
 * gebeurt.
 */

import { DacElement, define } from "./base.js";
import { level, levelTone } from "./format.js";

const UUR = 3600000;

/** De kleur per soort apparaat, en voor de zon, het huis en de accustand. */
export const KLEUR = {
  laadpaal: "#3fb68b",
  thuisbatterij: "#4c8dff",
  boiler: "#e0703a",
  vaatwasser: "#a37cf0",
  wasmachine: "#a37cf0",
  droger: "#c79bf2",
  airco: "#35c2d6",
  zon: "#f5b82e",
  huis: "#9aa3ad",
  soc: "#9ec2ff",
};

const getal = (n, d = 1) => Number(n).toLocaleString("nl-NL", { minimumFractionDigits: d, maximumFractionDigits: d });
const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
const twee = (n) => String(n).padStart(2, "0");

/** Een moment als de sleutel die de coach gebruikt: lokaal, zonder tijdzone. */
export function sleutel(d) {
  return `${d.getFullYear()}-${twee(d.getMonth() + 1)}-${twee(d.getDate())}T${twee(d.getHours())}:${twee(d.getMinutes())}:00`;
}

/** Hoeveel uur van [a, b) in [van, tot) valt. */
const overlap = (a, b, van, tot) => Math.max(0, Math.min(b, tot) - Math.max(a, van)) / UUR;

/**
 * De uren van de vooruitblik. Per uur de prijs (het tijdgewogen gemiddelde van
 * de blokken erin, of null als het uur niet helemaal bekend is), de zon en het
 * huis in kW (kWh in dat uur), en per apparaat het gemiddelde vermogen, wat het
 * doet (het blok dat het grootste deel van het uur beslaat) en de accustand aan
 * het eind.
 */
export function vooruitUren(data) {
  if (!data?.van || !data?.tot) return [];
  const van = new Date(data.van).getTime();
  const tot = new Date(data.tot).getTime();
  const prijzen = (data.prijzen ?? []).map((r) => ({ a: new Date(r.start).getTime(), b: new Date(r.end).getTime(), prijs: r.price, terug: r.feed_in }));
  const apparaten = (data.apparaten ?? []).map((a) => ({
    id: a.id,
    blokken: (a.blokken ?? []).map((b) => ({ ...b, a: new Date(b.start).getTime(), b: new Date(b.end).getTime() })),
  }));
  const uren = [];
  for (let t = van; t < tot; t += UUR) {
    const eind = t + UUR;
    let gedekt = 0;
    let som = 0;
    let terugSom = 0;
    let terugGedekt = 0;
    for (const r of prijzen) {
      const deel = overlap(r.a, r.b, t, eind);
      if (!deel || r.prijs === null || r.prijs === undefined) continue;
      gedekt += deel;
      som += r.prijs * deel;
      if (r.terug !== null && r.terug !== undefined) {
        terugGedekt += deel;
        terugSom += r.terug * deel;
      }
    }
    const per = {};
    for (const apparaat of apparaten) {
      let kw = 0;
      let onbekend = false;
      let zonKw = 0;
      let accuKw = 0;
      let grootste = 0;
      let wat = "";
      let why = "";
      let soc = null;
      let socEind = -Infinity;
      for (const b of apparaat.blokken) {
        const deel = overlap(b.a, b.b, t, eind);
        if (!deel) continue;
        if (b.kw === null || b.kw === undefined) onbekend = true;
        else kw += b.kw * deel;
        zonKw += (Number(b.zon_kw) || 0) * deel;
        accuKw += (Number(b.accu_kw) || 0) * deel;
        // Bij een gelijke verdeling het laatste blok: dat past bij de accustand aan het eind.
        if (deel >= grootste) {
          grootste = deel;
          wat = b.wat ?? "";
          why = b.why ?? "";
        }
        if (b.soc !== undefined && b.soc !== null && b.b <= eind + 1 && b.b > socEind) {
          socEind = b.b;
          soc = b.soc;
        }
      }
      if (grootste) per[apparaat.id] = { kw, onbekend, zonKw, accuKw, wat, why, soc };
    }
    const k = sleutel(new Date(t));
    uren.push({
      start: new Date(t),
      end: new Date(eind),
      prijs: gedekt >= 0.999 ? som / gedekt : null,
      terug: terugGedekt >= 0.999 ? terugSom / terugGedekt : null,
      zon: data.zon?.[k] ?? null,
      huis: data.huis?.[k] ?? null,
      apparaten: per,
    });
  }
  return uren;
}

/**
 * De volgorde van de apparaten: eerst de voorrang bij zon, dan die bij
 * planningen, dan de rest zoals de coach ze noemt. Zo staat onderaan de stapel
 * wie als eerste aan de beurt is.
 */
export function volgorde(data) {
  const ids = (data?.apparaten ?? []).map((a) => a.id);
  const uit = [];
  for (const id of [...(data?.voorrang_zon ?? []), ...(data?.voorrang_plan ?? []), ...ids]) {
    if (ids.includes(id) && !uit.includes(id)) uit.push(id);
  }
  return uit;
}

/** De regels voor het gekozen uur, in de woorden van de bewoner. */
export function momentRegels(uur, { ids, labels, soorten, zichtbaar }) {
  if (!uur) return [];
  const regels = [];
  if (zichtbaar.zon && uur.zon !== null && uur.zon > 0.005) regels.push({ kleur: KLEUR.zon, tekst: `Zon: ${getal(uur.zon)} kW verwacht` });
  if (zichtbaar.huis && uur.huis !== null) regels.push({ kleur: KLEUR.huis, tekst: `Huis: ${getal(uur.huis)} kW verwacht` });
  for (const id of ids) {
    if (!zichtbaar[id]) continue;
    const naam = labels.get(id) ?? id;
    const soort = soorten.get(id);
    const d = uur.apparaten[id];
    let tekst;
    if (!d) {
      tekst = `${naam}: niets gepland`;
    } else if (soort === "thuisbatterij") {
      const richting = d.kw > 0.05 ? `, ${getal(d.kw)} kW erin` : d.kw < -0.05 ? `, ${getal(-d.kw)} kW eruit` : "";
      tekst = `${naam}: ${d.wat}${richting}${d.soc !== null ? `, naar ${d.soc}%` : ""}`;
    } else if (soort === "laadpaal") {
      if (d.kw > 0.05) {
        const delen = [];
        if (d.zonKw > 0.05) delen.push(`${getal(d.zonKw)} uit de zon`);
        if (d.accuKw > 0.05) delen.push(`${getal(d.accuKw)} uit de batterij`);
        tekst = `${naam}: laadt ${getal(d.kw)} kW${delen.length ? ` (${delen.join(", ")})` : ""}`;
      } else {
        tekst = `${naam}: wacht${d.why ? `, ${d.why}` : ""}`;
      }
    } else {
      const kw = d.onbekend || d.kw === null ? "" : `, ${getal(d.kw)} kW`;
      tekst = `${naam}: ${d.wat}${kw}`;
    }
    regels.push({ kleur: KLEUR[soort] ?? "var(--dac-ink-3)", tekst });
  }
  return regels;
}

const PRIJS_H = 56;
const TUSSEN = 12;
const VERMOGEN_H = 150;
const AS_H = 20;
export const HOOGTE = PRIJS_H + TUSSEN + VERMOGEN_H + AS_H;

/**
 * De schalen van de grafiek: de hoogste prijs, het meeste vermogen erboven
 * (apparaten, zon, huis) en eronder (ontladen).
 */
export function schalen(uren, { ids, zichtbaar }) {
  let prijsMax = 0;
  let prijsMin = 0;
  let boven = 0;
  let onder = 0;
  for (const u of uren) {
    if (u.prijs !== null) {
      prijsMax = Math.max(prijsMax, u.prijs);
      prijsMin = Math.min(prijsMin, u.prijs);
    }
    let op = 0;
    let neer = 0;
    for (const id of ids) {
      const d = u.apparaten[id];
      if (!zichtbaar[id] || !d || d.onbekend) continue;
      if (d.kw > 0) op += d.kw;
      else neer -= d.kw;
    }
    boven = Math.max(boven, op, zichtbaar.zon ? u.zon ?? 0 : 0, zichtbaar.huis ? u.huis ?? 0 : 0);
    onder = Math.max(onder, neer);
  }
  return { prijsMax: Math.max(prijsMax, 0.01), prijsMin, boven: Math.max(boven, 0.5), onder };
}

/** De grafiek als svg, een kolom per uur. */
export function vooruitSvg(uren, { ids, soorten, zichtbaar, drempels, gekozen, kolom = 26 }) {
  const n = uren.length;
  const breed = n * kolom;
  const s = schalen(uren, { ids, zichtbaar });
  const delen = [];
  const midden = (i) => i * kolom + kolom / 2;

  // Het gekozen uur, achter alles.
  if (gekozen >= 0 && gekozen < n) {
    delen.push(`<rect class="gekozen" x="${gekozen * kolom}" y="0" width="${kolom}" height="${HOOGTE - AS_H}" rx="4"/>`);
  }
  // Middernacht: een lijn en de dag.
  uren.forEach((u, i) => {
    if (u.start.getHours() === 0 && i > 0) {
      delen.push(`<line class="dag" x1="${i * kolom}" x2="${i * kolom}" y1="0" y2="${HOOGTE - AS_H}"/>`);
    }
  });

  // De prijs.
  if (zichtbaar.prijs) {
    const bereik = s.prijsMax - s.prijsMin;
    const nul = PRIJS_H * (s.prijsMax / bereik);
    uren.forEach((u, i) => {
      if (u.prijs === null) return;
      const h = Math.max(1.5, (Math.abs(u.prijs) / bereik) * PRIJS_H);
      const y = u.prijs >= 0 ? nul - h : nul;
      delen.push(`<rect class="prijs" x="${i * kolom + 3}" y="${y.toFixed(1)}" width="${kolom - 6}" height="${h.toFixed(1)}" rx="2" fill="${levelTone(level(u.prijs, drempels, true))}"/>`);
    });
  }

  // De vermogens.
  const top = PRIJS_H + TUSSEN;
  const totaal = s.boven + s.onder;
  const schaal = VERMOGEN_H / totaal;
  const y0 = top + s.boven * schaal;
  delen.push(`<line class="nul" x1="0" x2="${breed}" y1="${y0.toFixed(1)}" y2="${y0.toFixed(1)}"/>`);
  if (zichtbaar.zon) {
    const punten = uren.map((u, i) => `${midden(i)},${(y0 - (u.zon ?? 0) * schaal).toFixed(1)}`);
    if (uren.some((u) => (u.zon ?? 0) > 0)) {
      delen.push(`<path class="zon" d="M0,${y0.toFixed(1)} L${punten.join(" L")} L${breed},${y0.toFixed(1)} Z"/>`);
    }
  }
  uren.forEach((u, i) => {
    let op = y0;
    let neer = y0;
    for (const id of ids) {
      const d = u.apparaten[id];
      if (!zichtbaar[id] || !d || d.onbekend || Math.abs(d.kw) < 0.01) continue;
      const h = Math.abs(d.kw) * schaal;
      const kleur = KLEUR[soorten.get(id)] ?? "#888";
      if (d.kw > 0) {
        op -= h;
        delen.push(`<rect x="${i * kolom + 4}" y="${op.toFixed(1)}" width="${kolom - 8}" height="${h.toFixed(1)}" fill="${kleur}"/>`);
      } else {
        delen.push(`<rect x="${i * kolom + 4}" y="${neer.toFixed(1)}" width="${kolom - 8}" height="${h.toFixed(1)}" fill="${kleur}" opacity="0.75"/>`);
        neer += h;
      }
    }
    // Een programma waarvan het verbruik niet bekend is: een streepje, geen hoogte.
    for (const id of ids) {
      const d = u.apparaten[id];
      if (zichtbaar[id] && d?.onbekend) {
        delen.push(`<rect x="${i * kolom + 4}" y="${(y0 - 3).toFixed(1)}" width="${kolom - 8}" height="3" fill="${KLEUR[soorten.get(id)] ?? "#888"}"/>`);
      }
    }
  });
  if (zichtbaar.huis && uren.some((u) => u.huis !== null)) {
    const punten = uren.map((u, i) => (u.huis === null ? null : `${midden(i)},${(y0 - u.huis * schaal).toFixed(1)}`)).filter(Boolean);
    delen.push(`<polyline class="huis" points="${punten.join(" ")}"/>`);
  }
  if (zichtbaar.zon && uren.some((u) => (u.zon ?? 0) > 0)) {
    const punten = uren.map((u, i) => `${midden(i)},${(y0 - (u.zon ?? 0) * schaal).toFixed(1)}`);
    delen.push(`<polyline class="zonlijn" points="${punten.join(" ")}"/>`);
  }
  // De accustand, op zijn eigen schaal: 0 tot 100% over de hoogte van de vermogens.
  if (zichtbaar.soc) {
    for (const id of ids) {
      if (soorten.get(id) !== "thuisbatterij") continue;
      const punten = uren
        .map((u, i) => (u.apparaten[id]?.soc === null || u.apparaten[id]?.soc === undefined ? null
          : `${midden(i)},${(top + VERMOGEN_H * (1 - u.apparaten[id].soc / 100)).toFixed(1)}`))
        .filter(Boolean);
      if (punten.length > 1) delen.push(`<polyline class="soc" points="${punten.join(" ")}"/>`);
    }
  }
  // De uren eronder, om de drie.
  uren.forEach((u, i) => {
    const uur = u.start.getHours();
    if (uur % 3 === 0) {
      delen.push(`<text class="${uur === 0 ? "uur nacht" : "uur"}" x="${midden(i)}" y="${HOOGTE - 5}">${twee(uur)}</text>`);
    }
  });

  return `<svg class="vb" width="${breed}" height="${HOOGTE}" viewBox="0 0 ${breed} ${HOOGTE}" role="img" aria-label="Vooruitblik per uur">${delen.join("")}</svg>`;
}

const ZICHT_SLEUTEL = "dac-vooruitblik";

/** Wat er verborgen is, per scherm: een voorkeur van wie kijkt, niet van het huis. */
function leesVerborgen() {
  try {
    return new Set(JSON.parse(localStorage.getItem(ZICHT_SLEUTEL) || "[]"));
  } catch {
    return new Set();
  }
}

function bewaarVerborgen(verborgen) {
  try {
    localStorage.setItem(ZICHT_SLEUTEL, JSON.stringify([...verborgen]));
  } catch {
    // Privé venster of vol: dan geldt het alleen tot het scherm ververst.
  }
}

const css = /* css */ `
  :host { display: block; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 12px; }
  .chip {
    display: inline-flex; align-items: center; gap: 6px; font: inherit; font-size: 12.5px;
    padding: 6px 10px; border-radius: 999px; cursor: pointer;
    border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.04); color: var(--dac-ink-2);
  }
  .chip i { width: 10px; height: 10px; border-radius: 3px; flex: 0 0 auto; }
  .chip[aria-pressed="false"] { opacity: 0.45; }
  .chip[aria-pressed="false"] i { background: transparent !important; outline: 1px solid var(--dac-border-hi); }
  .moment {
    padding: 10px 12px; margin: 0 0 12px; border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border-hi); background: rgba(var(--dac-veil),0.03);
  }
  .moment .kop { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
  .moment .wanneer { font-size: 13px; color: var(--dac-ink-2); }
  .moment .prijs { font-size: 18px; font-weight: 700; color: var(--dac-ink); font-variant-numeric: tabular-nums; }
  .moment ul { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 4px; }
  .moment li { display: flex; align-items: baseline; gap: 8px; font-size: 13px; line-height: 1.4; color: var(--dac-ink-2); }
  .moment li i { width: 9px; height: 9px; border-radius: 2px; flex: 0 0 auto; transform: translateY(1px); }
  .grafiek { position: relative; display: flex; gap: 6px; }
  .as { flex: 0 0 auto; position: relative; width: 44px; font-size: 10.5px; color: var(--dac-ink-3); font-variant-numeric: tabular-nums; }
  .as span { position: absolute; right: 0; transform: translateY(-50%); white-space: nowrap; }
  .veeg { flex: 1 1 auto; min-width: 0; overflow-x: auto; overscroll-behavior-x: contain; -webkit-overflow-scrolling: touch; cursor: pointer; }
  .veeg svg { display: block; }
  .vb .gekozen { fill: rgba(var(--dac-veil),0.07); }
  .vb .dag { stroke: var(--dac-border-hi); stroke-dasharray: 2 3; }
  .vb .nul { stroke: var(--dac-border-hi); }
  .vb .zon { fill: ${KLEUR.zon}; opacity: 0.18; }
  .vb .zonlijn { fill: none; stroke: ${KLEUR.zon}; stroke-width: 2; }
  .vb .huis { fill: none; stroke: ${KLEUR.huis}; stroke-width: 1.5; stroke-dasharray: 4 3; }
  .vb .soc { fill: none; stroke: ${KLEUR.soc}; stroke-width: 2; }
  .vb .uur { fill: var(--dac-ink-3); font-size: 10.5px; text-anchor: middle; }
  .vb .uur.nacht { fill: var(--dac-ink-2); font-weight: 700; }
  .legenda { display: flex; flex-wrap: wrap; gap: 6px 14px; margin: 10px 0 0; font-size: 12px; color: var(--dac-ink-2); }
  .legenda span { display: inline-flex; align-items: center; gap: 6px; }
  .legenda i { width: 10px; height: 10px; border-radius: 2px; }
  .legenda i.lijn { height: 0; border-top: 2px solid; border-radius: 0; width: 14px; }
  .legenda i.stip { height: 0; border-top: 2px dashed; border-radius: 0; width: 14px; }
  .voorrang { margin: 10px 0 0; font-size: 12.5px; line-height: 1.5; color: var(--dac-ink-2); }
  .voorrang:empty { display: none; }
  .leeg { margin: 0; font-size: 13px; color: var(--dac-ink-2); }
`;

export class DacVooruitblik extends DacElement {
  static css = css;

  constructor() {
    super();
    this.data_ = null;
    this.labels_ = new Map();
    this.soorten_ = new Map();
    this.drempels_ = { low: 0.2, high: 0.3 };
    this.verborgen_ = leesVerborgen();
    this.gekozen_ = 0;
    this.sleutel_ = "";
  }

  render() {
    return /* html */ `
      <div class="chips" id="chips"></div>
      <div class="moment" id="moment"></div>
      <div class="grafiek">
        <div class="as" id="as"></div>
        <div class="veeg" id="veeg"></div>
      </div>
      <div class="legenda" id="legenda"></div>
      <p class="voorrang" id="voorrang"></p>
    `;
  }

  afterRender() {
    this.$("#chips").addEventListener("click", (event) => {
      const chip = event.target?.closest?.("[data-laag]");
      if (!chip) return;
      const laag = chip.dataset.laag;
      if (this.verborgen_.has(laag)) this.verborgen_.delete(laag);
      else this.verborgen_.add(laag);
      bewaarVerborgen(this.verborgen_);
      this.paint_();
    });
    const veeg = this.$("#veeg");
    veeg.addEventListener("click", (event) => {
      const svg = veeg.querySelector("svg");
      if (!svg) return;
      const plek = event.clientX - svg.getBoundingClientRect().left;
      const index = Math.floor(plek / 26);
      if (index >= 0 && index < (this.uren_?.length ?? 0)) {
        this.gekozen_ = index;
        this.paint_();
      }
    });
    this.paint_();
  }

  /**
   * @param {{data: object|null, devices: object[], labels: Map<string,string>, drempels: {low:number, high:number}}} opties
   */
  update({ data, devices, labels, drempels }) {
    this.data_ = data ?? null;
    this.labels_ = labels ?? new Map();
    this.soorten_ = new Map((devices ?? []).map((d) => [d.id, d.type]));
    for (const a of data?.apparaten ?? []) if (!this.soorten_.has(a.id)) this.soorten_.set(a.id, a.type);
    if (drempels) this.drempels_ = drempels;
    // Een nieuw begin (een nieuw uur) zet de keuze terug op nu.
    if (data?.van !== this.sleutel_) {
      this.sleutel_ = data?.van ?? "";
      this.gekozen_ = 0;
    }
    this.paint_();
  }

  zichtbaar_() {
    const z = {};
    for (const laag of ["prijs", "zon", "huis", "soc", ...(this.data_?.apparaten ?? []).map((a) => a.id)]) {
      z[laag] = !this.verborgen_.has(laag);
    }
    return z;
  }

  paint_() {
    if (!this.rendered_) return;
    const data = this.data_;
    this.uren_ = vooruitUren(data);
    const uren = this.uren_;
    if (!uren.length) {
      this.$("#moment").innerHTML = `<p class="leeg">Nog niets om vooruit te kijken: de coach heeft nog geen plan.</p>`;
      for (const id of ["#chips", "#as", "#veeg", "#legenda", "#voorrang"]) this.$(id).replaceChildren();
      return;
    }
    const ids = volgorde(data);
    const zichtbaar = this.zichtbaar_();
    const accu = ids.some((id) => this.soorten_.get(id) === "thuisbatterij");
    const naam = (id) => this.labels_.get(id) ?? id;

    // De keuzeknoppen.
    const lagen = [
      ["prijs", "Prijs", "var(--dac-good)"],
      ["zon", "Zon", KLEUR.zon],
      ["huis", "Huis", KLEUR.huis],
      ...ids.map((id) => [id, naam(id), KLEUR[this.soorten_.get(id)] ?? "#888"]),
      ...(accu ? [["soc", "Accustand", KLEUR.soc]] : []),
    ];
    this.$("#chips").innerHTML = lagen.map(([laag, tekst, kleur]) =>
      `<button type="button" class="chip" data-laag="${esc(laag)}" aria-pressed="${zichtbaar[laag] !== false}"><i style="background:${kleur}"></i>${esc(tekst)}</button>`).join("");

    // Het gekozen uur.
    const uur = uren[Math.min(this.gekozen_, uren.length - 1)];
    const morgen = uur.start.getDate() !== new Date().getDate() ? "morgen " : "";
    const prijs = uur.prijs === null ? "" : `€ ${getal(uur.prijs, 3)}`;
    const regels = momentRegels(uur, { ids, labels: this.labels_, soorten: this.soorten_, zichtbaar });
    this.$("#moment").innerHTML = `
      <div class="kop"><span class="wanneer">${morgen}${twee(uur.start.getHours())}:00 tot ${twee(uur.end.getHours())}:00</span>
        <span class="prijs"${uur.prijs === null ? "" : ` style="color:${levelTone(level(uur.prijs, this.drempels_, true))}"`}>${prijs}</span></div>
      ${regels.length ? `<ul>${regels.map((r) => `<li><i style="background:${r.kleur}"></i><span>${esc(r.tekst)}</span></li>`).join("")}</ul>` : ""}`;

    // De grafiek; waar je naartoe veegde blijft staan.
    const veeg = this.$("#veeg");
    const plek = veeg.scrollLeft;
    veeg.innerHTML = vooruitSvg(uren, { ids, soorten: this.soorten_, zichtbaar, drempels: this.drempels_, gekozen: this.gekozen_ });
    veeg.scrollLeft = plek;

    // De as links: de hoogste prijs en het meeste vermogen.
    const s = schalen(uren, { ids, zichtbaar });
    const top = PRIJS_H + TUSSEN;
    const y0 = top + VERMOGEN_H * (s.boven / (s.boven + s.onder));
    this.$("#as").style.height = `${HOOGTE}px`;
    this.$("#as").innerHTML = [
      zichtbaar.prijs ? `<span style="top:4px">€ ${getal(s.prijsMax, 2)}</span>` : "",
      `<span style="top:${top + 4}px">${getal(s.boven)} kW</span>`,
      `<span style="top:${y0}px">0</span>`,
      s.onder > 0.05 ? `<span style="top:${top + VERMOGEN_H - 4}px">−${getal(s.onder)} kW</span>` : "",
    ].join("");

    // De legenda.
    const legenda = [];
    if (zichtbaar.zon) legenda.push(`<span><i class="lijn" style="border-color:${KLEUR.zon}"></i>Zon, verwacht</span>`);
    if (zichtbaar.huis) legenda.push(`<span><i class="stip" style="border-color:${KLEUR.huis}"></i>Huis, verwacht</span>`);
    if (accu && zichtbaar.soc) legenda.push(`<span><i class="lijn" style="border-color:${KLEUR.soc}"></i>Accustand, 0 tot 100%</span>`);
    if (accu) legenda.push(`<span>Onder de lijn: de batterij ontlaadt</span>`);
    this.$("#legenda").innerHTML = legenda.join("");

    // De voorrang zoals Voorkeuren hem zet.
    const zonVolgorde = (data.voorrang_zon ?? []).filter((id) => ids.includes(id)).map(naam);
    const planVolgorde = (data.voorrang_plan ?? []).filter((id) => ids.includes(id)).map(naam);
    const zinnen = [];
    if (zonVolgorde.length > 1) zinnen.push(`Voorrang bij zon: ${zonVolgorde.join(", ")}.`);
    if (planVolgorde.length > 1) zinnen.push(`Bij planningen: ${planVolgorde.join(", ")}.`);
    this.$("#voorrang").textContent = zinnen.join(" ");
  }
}

define("dac-vooruitblik", DacVooruitblik);
