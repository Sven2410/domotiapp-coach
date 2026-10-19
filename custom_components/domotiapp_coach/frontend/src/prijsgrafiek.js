/**
 * De prijs per uur als staafjes, met de uren waarin de coach laadt in groen.
 *
 * De bewoner van de eerste woning op 23-09-2026, over evcc: "met groene
 * balkjes laat hij precies zien welke (goedkope) uren hij gaat laden, en wat
 * de gemiddelde prijs wordt. Zo heb je als gebruiker een visuele check dat de
 * laadpaal inderdaad op de goedkoopste momenten gaat laden." De eigenaar
 * erbij: "ook voor de batterij."
 *
 * Hier wordt niets besloten. Welke uren groen zijn komt uit het plan van de
 * coach (`charging` bij de paal, `grid_kwh` bij de batterij); dit tekent
 * alleen. De rekenkant staat los van het tekenen, zodat test_rapport.mjs hem
 * zonder scherm kan nameten.
 */

import { datum, getal, t } from "./i18n.js";

const HOOGTE = 96;      // tekenhoogte van de staafjes, in eenheden van de viewBox
const BREEDTE = 300;
const TUSSEN = 2;       // ruimte tussen twee staafjes
const RAND = 4;         // afgeronde bovenkant

const prijsTekst = (p) => `€ ${getal(p, 3)}`;

const klok = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

/**
 * De staafjes, uitgerekend en nog niet getekend.
 *
 * @param {Array<{start: string, end?: string, price: number|null, groen: boolean,
 *                leveren?: boolean, kwh?: number}>} rijen  een per blok, in
 *   tijdsvolgorde. `kwh` is wat er in dat blok van het net gaat; daarmee wordt
 *   het gemiddelde gewogen. `leveren` is een blok waarin een thuisbatterij aan
 *   het net levert (v0.129.0).
 * @returns {null | {balken: Array<{x: number, y: number, w: number, h: number,
 *   groen: boolean, label: string, tip: string}>, nul: number,
 *   gemiddeld: number|null, kwh: number}}
 *   null als er geen prijzen zijn (een vast contract): dan valt er niets te tonen.
 */
/**
 * De stappen van de prijsas (v0.129.0): ronde bedragen, drie tot vijf, van nul
 * (of de laagste negatieve prijs) tot boven de hoogste. De bewoner van de eerste
 * woning op 18-10-2026: "Nu zijn de staven wel wisselend in hoogte, maar zeggen
 * ze nog niets over de prijs."
 */
export function prijsStappen(laagst, hoogst) {
  const bereik = Math.max(hoogst - laagst, 0.01);
  const stap = [0.01, 0.02, 0.05, 0.1, 0.2, 0.25, 0.5, 1].find((s) => bereik / s <= 5) ?? 1;
  const onder = Math.floor(laagst / stap + 1e-9) * stap;
  let boven = Math.ceil(hoogst / stap - 1e-9) * stap;
  if (boven <= onder) boven = onder + stap;
  const uit = [];
  for (let v = onder; v <= boven + 1e-9; v += stap) uit.push(Math.round(v * 1000) / 1000);
  return { stappen: uit, onder, boven };
}

export function prijsBalken(rijen = []) {
  const metPrijs = (rijen ?? []).filter((r) => r && Number.isFinite(r.price));
  if (metPrijs.length < 2) return null;

  // De as loopt van een rond bedrag onder de laagste prijs (nul, of lager bij
  // een negatieve prijs) tot een rond bedrag boven de hoogste, en de staafjes
  // staan daarop: dan zegt de hoogte iets over de prijs.
  const as = prijsStappen(Math.min(0, ...metPrijs.map((r) => r.price)), Math.max(0, ...metPrijs.map((r) => r.price)));
  const hoogst = as.boven;
  const laagst = as.onder;
  const bereik = hoogst - laagst || 1;
  const schaal = (p) => (p / bereik) * HOOGTE;
  const nul = (hoogst / bereik) * HOOGTE;

  const n = metPrijs.length;
  const w = Math.max(1, (BREEDTE - TUSSEN * (n - 1)) / n);
  let vorigeUur = null;
  let dagen = 0;
  const balken = metPrijs.map((r, i) => {
    const h = Math.abs(schaal(r.price));
    const y = r.price >= 0 ? nul - h : nul;
    // Een tijd onder elk derde hele uur, want onder elk staafje is het een
    // muur van cijfers. Het eerste blok begint vaak midden in een uur (nu),
    // en krijgt dus geen label.
    const d = new Date(r.start);
    const uur = d.getHours();
    const heel = d.getMinutes() === 0;
    // Waar een nieuwe dag begint (v0.129.0): daar staat "morgen" in plaats van
    // 00, met een streep, anders lijkt een lijst tot morgenavond één dag.
    const dagGrens = i > 0 && heel && uur === 0 && uur !== vorigeUur;
    if (dagGrens) dagen += 1;
    const dagNaam = dagen === 1 ? t("morgen") : datum(d, { weekday: "short" });
    const label = dagGrens ? dagNaam : heel && uur % 3 === 0 && uur !== vorigeUur ? String(uur).padStart(2, "0") : "";
    vorigeUur = uur;
    const tijd = r.end ? t("{van} tot {tot}", { van: klok(r.start), tot: klok(r.end) }) : klok(r.start);
    return {
      x: i * (w + TUSSEN),
      y,
      w,
      h: Math.max(h, 1),
      groen: Boolean(r.groen),
      leveren: Boolean(r.leveren) && !r.groen,
      dagGrens,
      label,
      tip: `${tijd}: ${prijsTekst(r.price)}${r.groen ? `, ${t("laden")}` : r.leveren ? `, ${t("ontladen aan het net")}` : ""}`,
    };
  });

  // Het gemiddelde van wat er gekocht wordt, gewogen naar de kilowatturen
  // van het net. Een groen uur dat helemaal op zon draait weegt dus niet mee:
  // die kWh kost de inkoopprijs niet. Alleen zonder kWh per blok (een oudere
  // server) telt elk groen blok even zwaar.
  const groen = metPrijs.filter((r) => r.groen);
  const metKwh = groen.some((r) => r.kwh !== undefined && r.kwh !== null);
  let gemiddeld = null;
  let kwh = 0;
  if (metKwh) {
    kwh = groen.reduce((s, r) => s + Math.max(0, Number(r.kwh) || 0), 0);
    if (kwh > 0.05) {
      gemiddeld = groen.reduce((s, r) => s + r.price * Math.max(0, Number(r.kwh) || 0), 0) / kwh;
    }
  } else if (groen.length) {
    gemiddeld = groen.reduce((s, r) => s + r.price, 0) / groen.length;
  }
  // Hoe lang een blok is, in minuten: 60 bij uurprijzen, 15 bij kwartierprijzen
  // (v0.88.1). Het eerste blok telt niet mee, want dat begint vaak midden in
  // een uur (nu).
  const duren = metPrijs.slice(1)
    .filter((r) => r.end)
    .map((r) => (new Date(r.end) - new Date(r.start)) / 60000)
    .filter((m) => m > 0);
  const stap = duren.length ? Math.round(Math.min(...duren)) : 60;
  // Hoe breed de grafiek minstens is, in px (v0.129.0): een uur 14 px, een
  // kwartier 5. Past dat niet, dan veeg je verder, zo ver als de lijst eronder.
  const minBreedte = n * (stap <= 20 ? 5 : 14);
  // Het gemiddelde van alle blokken, voor de stippellijn en "onder het
  // gemiddelde" (v0.129.0); niet hetzelfde als `gemiddeld`, dat gaat over wat
  // er van het net gekocht wordt.
  const gemiddeldAlles = metPrijs.reduce((s, r) => s + r.price, 0) / n;
  const hoogte = (p) => nul - schaal(p);
  const stappen = as.stappen.map((v) => ({ waarde: v, y: hoogte(v) }));
  const blokken = metPrijs.map((r) => ({ start: r.start, end: r.end, price: r.price, groen: Boolean(r.groen),
    leveren: Boolean(r.leveren) && !r.groen, label: r.label ?? "" }));
  return { balken, nul, gemiddeld, kwh, stap, minBreedte, gemiddeldAlles, gemiddeldY: hoogte(gemiddeldAlles),
    stappen, blokken };
}

/**
 * Blokken van korter dan een uur samengenomen per uur, voor de lijst onder de
 * grafiek (v0.88.1). Met kwartierprijzen zijn het anders zestig tot tachtig
 * regels; de grafiek laat de kwartieren zelf zien. Uurblokken blijven zoals ze
 * zijn. Geeft groepen: een lijst per uur, in tijdsvolgorde.
 */
export function perUur(blokken = []) {
  const lijst = (blokken ?? []).filter((b) => b && b.start);
  const kwartieren = lijst.slice(1).some((b) => b.end && new Date(b.end) - new Date(b.start) <= 20 * 60000);
  if (!kwartieren) return lijst.map((b) => [b]);
  const groepen = [];
  let sleutel = null;
  for (const b of lijst) {
    const d = new Date(b.start);
    const k = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}-${d.getHours()}`;
    if (k !== sleutel) {
      groepen.push([]);
      sleutel = k;
    }
    groepen[groepen.length - 1].push(b);
  }
  return groepen;
}

const NS = "http://www.w3.org/2000/svg";

/** Het getekende figuur: een svg met een staafje per blok, en een titel per staafje voor de hover. */
export function prijsSvg(berekend, doc = document) {
  const svg = doc.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${BREEDTE} ${HOOGTE}`);
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("class", "prijsgrafiek");
  svg.setAttribute("role", "img");
  const groen = berekend.balken.filter((b) => b.groen).length;
  svg.setAttribute(
    "aria-label",
    t("Prijs per uur; in {groen} van de {n} uren laadt hij.", { groen, n: berekend.balken.length })
  );

  berekend.balken.forEach((b, i) => {
    const g = doc.createElementNS(NS, "g");
    // Welk staafje dit is, voor de tik die de prijs laat zien (v0.129.0).
    g.setAttribute("data-i", String(i));
    // Een raakvlak over de hele hoogte, zodat ook een laag staafje te
    // aanwijzen is met de muis of een vinger.
    const vlak = doc.createElementNS(NS, "rect");
    vlak.setAttribute("x", b.x);
    vlak.setAttribute("y", 0);
    vlak.setAttribute("width", b.w + TUSSEN);
    vlak.setAttribute("height", HOOGTE);
    vlak.setAttribute("class", "raak");
    const staaf = doc.createElementNS(NS, "rect");
    staaf.setAttribute("x", b.x);
    staaf.setAttribute("y", b.y);
    staaf.setAttribute("width", b.w);
    staaf.setAttribute("height", b.h);
    staaf.setAttribute("rx", Math.min(RAND / 2, b.w / 2));
    staaf.setAttribute("class", b.groen ? "staaf groen" : b.leveren ? "staaf leveren" : "staaf");
    const titel = doc.createElementNS(NS, "title");
    titel.textContent = b.tip;
    g.append(vlak, staaf, titel);
    svg.append(g);
  });

  // Een streep waar een nieuwe dag begint.
  for (const b of berekend.balken.filter((x) => x.dagGrens)) {
    const grens = doc.createElementNS(NS, "line");
    grens.setAttribute("x1", b.x - TUSSEN / 2);
    grens.setAttribute("x2", b.x - TUSSEN / 2);
    grens.setAttribute("y1", 0);
    grens.setAttribute("y2", HOOGTE);
    grens.setAttribute("class", "dag");
    svg.append(grens);
  }

  // Lichte hulplijnen op de stappen van de prijsas, en het gemiddelde gestippeld.
  for (const s of berekend.stappen ?? []) {
    const hulp = doc.createElementNS(NS, "line");
    hulp.setAttribute("x1", 0);
    hulp.setAttribute("x2", BREEDTE);
    hulp.setAttribute("y1", s.y);
    hulp.setAttribute("y2", s.y);
    hulp.setAttribute("class", "hulp");
    svg.append(hulp);
  }
  if (Number.isFinite(berekend.gemiddeldY)) {
    const gem = doc.createElementNS(NS, "line");
    gem.setAttribute("x1", 0);
    gem.setAttribute("x2", BREEDTE);
    gem.setAttribute("y1", berekend.gemiddeldY);
    gem.setAttribute("y2", berekend.gemiddeldY);
    gem.setAttribute("class", "gem");
    svg.append(gem);
  }

  const lijn = doc.createElementNS(NS, "line");
  lijn.setAttribute("x1", 0);
  lijn.setAttribute("x2", BREEDTE);
  lijn.setAttribute("y1", berekend.nul);
  lijn.setAttribute("y2", berekend.nul);
  lijn.setAttribute("class", "nul");
  svg.append(lijn);
  return svg;
}

/** De tijden onder de grafiek, als html, zodat ze niet mee uitrekken met de svg. */
export function prijsLabels(berekend, doc = document) {
  const rij = doc.createElement("div");
  rij.className = "prijs-tijden";
  for (const b of berekend.balken) {
    if (!b.label) continue;
    const tijd = doc.createElement("span");
    tijd.textContent = b.label;
    if (b.dagGrens) tijd.className = "dag";
    tijd.style.left = `${((b.x + b.w / 2) / BREEDTE) * 100}%`;
    rij.append(tijd);
  }
  return rij;
}

/**
 * De svg en de tijden in een strook die je horizontaal veegt als hij breder is
 * dan het scherm (v0.129.0). De eigenaar op 18-10-2026: "horizontaal
 * scrollable/swipable maken, zodat je net zover vooruit kan kijken als de
 * strategie eronder doet."
 */
export function prijsStrook(berekend, doc = document) {
  const strook = doc.createElement("div");
  strook.className = "prijs-strook";
  const binnen = doc.createElement("div");
  binnen.className = "prijs-binnen";
  // Minstens zo breed als de staafjes vragen; past dat niet, dan loopt hij over en veeg je.
  binnen.style.minWidth = `${berekend.minBreedte ?? 0}px`;
  binnen.append(prijsSvg(berekend, doc), prijsLabels(berekend, doc));
  strook.append(binnen);
  return strook;
}

/** De prijsas links, die blijft staan als je de strook veegt (v0.129.0). */
export function prijsAs(berekend, doc = document) {
  const as = doc.createElement("div");
  as.className = "prijs-as";
  for (const s of berekend.stappen ?? []) {
    const bedrag = doc.createElement("span");
    bedrag.textContent = `€ ${getal(s.waarde, 2)}`;
    bedrag.style.top = `${(s.y / HOOGTE) * 100}%`;
    as.append(bedrag);
  }
  return as;
}

/**
 * De zin bij een blok, voor de kaart boven de grafiek (v0.129.0): wanneer, wat
 * het kost, hoe dat zich verhoudt, en wat het apparaat dan doet. Zoals de app
 * van een leverancier: "Nu: 23:30 tot 23:45, 36,3 ct, 1% onder het
 * gemiddelde", en bij een gekozen blok "9% duurder dan nu".
 *
 * @param {object} berekend uit `prijsBalken`
 * @param {number} i welk blok; 0 is nu
 * @param {{groen?: string, leveren?: string, wacht?: string}} [wat] wat het apparaat doet, in woorden
 */
export function prijsUitleg(berekend, i, wat = {}) {
  const b = berekend?.blokken?.[i];
  if (!b) return null;
  const tijd = b.end ? t("{van} tot {tot}", { van: klok(b.start), tot: klok(b.end) }) : klok(b.start);
  const procent = (prijs, met) => (Number.isFinite(met) && Math.abs(met) > 1e-9
    ? Math.round(((prijs - met) / Math.abs(met)) * 100) : null);
  let vergelijk = "";
  if (i === 0) {
    const pct = procent(b.price, berekend.gemiddeldAlles);
    if (pct !== null) vergelijk = pct === 0 ? t("precies het gemiddelde") : pct < 0 ? t("{pct}% onder het gemiddelde", { pct: -pct }) : t("{pct}% boven het gemiddelde", { pct });
  } else {
    const pct = procent(b.price, berekend.blokken[0].price);
    if (pct !== null) vergelijk = pct === 0 ? t("even duur als nu") : pct < 0 ? t("{pct}% goedkoper dan nu", { pct: -pct }) : t("{pct}% duurder dan nu", { pct });
  }
  // Wat het apparaat doet, in de woorden van de legenda; een blok met een eigen
  // naam (de stand van een batterij, zoals "Standby") houdt die.
  const doet = (b.groen ? wat.groen : b.leveren ? wat.leveren : (b.label || wat.wacht)) ?? "";
  const klein = doet ? doet.charAt(0).toLowerCase() + doet.slice(1) : "";
  return {
    kop: i === 0 ? t("Nu: {tijd}", { tijd }) : tijd,
    prijs: prijsTekst(b.price),
    onder: [vergelijk, klein].filter(Boolean).join(", "),
  };
}

/** De css die bij de grafiek hoort; de pop-up neemt hem op. */
export const prijsCss = /* css */ `
  .prijs-blok {
    margin: 0 0 14px;
    padding: 12px 12px 8px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(var(--dac-veil),0.02);
  }
  .prijs-blok[hidden] { display: none; }
  .prijs-kop {
    display: flex; justify-content: space-between; align-items: baseline; gap: 10px;
    font-size: 12px; color: var(--dac-ink-3); margin-bottom: 8px;
  }
  .prijs-kop strong { color: var(--dac-ink-1); font-size: 15px; font-variant-numeric: tabular-nums; }
  .prijsgrafiek { display: block; width: 100%; height: 96px; overflow: visible; }
  .prijsgrafiek .staaf { fill: var(--dac-ink-3); }
  .prijsgrafiek .staaf.groen { fill: rgb(56,189,124); }
  .prijsgrafiek .staaf.leveren { fill: rgb(240,160,40); }
  .prijsgrafiek .dag { stroke: var(--dac-ink-3); stroke-width: 1; stroke-dasharray: 3 3; vector-effect: non-scaling-stroke; }
  .prijsgrafiek .hulp { stroke: var(--dac-border); stroke-width: 1; vector-effect: non-scaling-stroke; opacity: 0.7; }
  .prijsgrafiek .gem { stroke: var(--dac-ink-2); stroke-width: 1; stroke-dasharray: 4 3; vector-effect: non-scaling-stroke; }
  .prijs-raam { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 6px; }
  .prijs-as { position: relative; height: 96px; min-width: 46px; }
  .prijs-as span {
    position: absolute; right: 0; transform: translateY(-50%);
    font-size: 10.5px; color: var(--dac-ink-3); font-variant-numeric: tabular-nums; white-space: nowrap;
  }
  .prijs-moment {
    display: grid; gap: 2px; margin: 0 0 10px; padding: 10px 12px; text-align: center;
    border-radius: var(--dac-radius-sm); border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.03);
  }
  .prijs-moment .wanneer { font-size: 12.5px; color: var(--dac-ink-2); font-variant-numeric: tabular-nums; }
  .prijs-moment .bedrag { font-size: 24px; font-weight: 600; color: var(--dac-ink-1, var(--dac-ink)); font-variant-numeric: tabular-nums; }
  .prijs-moment .wat { font-size: 12.5px; color: var(--dac-ink-2); }
  .prijs-moment.gekozen { border-color: rgba(56,132,240,0.6); }
  .prijs-strook { overflow-x: auto; overscroll-behavior-x: contain; -webkit-overflow-scrolling: touch; }
  .prijs-binnen { width: 100%; }
  .prijs-tijden span.dag { color: var(--dac-ink-2); font-weight: 600; }
  .prijsgrafiek .raak { fill: transparent; }
  .prijsgrafiek g:hover .staaf { opacity: 0.75; }
  .prijsgrafiek g { cursor: pointer; }
  .prijsgrafiek g.gekozen .staaf { fill: rgb(56,132,240); }

  .prijsgrafiek .nul { stroke: var(--dac-border); stroke-width: 1; vector-effect: non-scaling-stroke; }
  .prijs-tijden { position: relative; height: 14px; margin-top: 2px; }
  .prijs-tijden span {
    position: absolute; transform: translateX(-50%);
    font-size: 11px; color: var(--dac-ink-3); font-variant-numeric: tabular-nums;
  }
  .prijs-legenda { display: flex; gap: 14px; margin-top: 4px; font-size: 11.5px; color: var(--dac-ink-3); }
  .prijs-legenda i {
    display: inline-block; width: 9px; height: 9px; border-radius: 2px;
    margin-right: 5px; vertical-align: -1px; background: var(--dac-ink-3);
  }
  .prijs-legenda i.groen { background: rgb(56,189,124); }
  .prijs-legenda i.leveren { background: rgb(240,160,40); }
`;
