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

const HOOGTE = 96;      // tekenhoogte van de staafjes, in eenheden van de viewBox
const BREEDTE = 300;
const TUSSEN = 2;       // ruimte tussen twee staafjes
const RAND = 4;         // afgeronde bovenkant

const prijsTekst = (p) => `€ ${Number(p).toFixed(3).replace(".", ",")}`;

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
 *                kwh?: number}>} rijen  een per blok, in tijdsvolgorde. `kwh` is
 *   wat er in dat blok van het net gaat; daarmee wordt het gemiddelde gewogen.
 * @returns {null | {balken: Array<{x: number, y: number, w: number, h: number,
 *   groen: boolean, label: string, tip: string}>, nul: number,
 *   gemiddeld: number|null, kwh: number}}
 *   null als er geen prijzen zijn (een vast contract): dan valt er niets te tonen.
 */
export function prijsBalken(rijen = []) {
  const metPrijs = (rijen ?? []).filter((r) => r && Number.isFinite(r.price));
  if (metPrijs.length < 2) return null;

  // De nullijn staat onderaan, tenzij er een negatieve prijs is: dan zakt
  // dat staafje eronder, en daar hoort ruimte voor.
  const hoogst = Math.max(0, ...metPrijs.map((r) => r.price));
  const laagst = Math.min(0, ...metPrijs.map((r) => r.price));
  const bereik = hoogst - laagst || 1;
  const schaal = (p) => (p / bereik) * HOOGTE;
  const nul = (hoogst / bereik) * HOOGTE;

  const n = metPrijs.length;
  const w = Math.max(1, (BREEDTE - TUSSEN * (n - 1)) / n);
  let vorigeUur = null;
  const balken = metPrijs.map((r, i) => {
    const h = Math.abs(schaal(r.price));
    const y = r.price >= 0 ? nul - h : nul;
    // Een tijd onder elk derde hele uur, want onder elk staafje is het een
    // muur van cijfers. Het eerste blok begint vaak midden in een uur (nu),
    // en krijgt dus geen label.
    const d = new Date(r.start);
    const uur = d.getHours();
    const heel = d.getMinutes() === 0;
    const label = heel && uur % 3 === 0 && uur !== vorigeUur ? String(uur).padStart(2, "0") : "";
    vorigeUur = uur;
    const tijd = r.end ? `${klok(r.start)} tot ${klok(r.end)}` : klok(r.start);
    return {
      x: i * (w + TUSSEN),
      y,
      w,
      h: Math.max(h, 1),
      groen: Boolean(r.groen),
      label,
      tip: `${tijd}: ${prijsTekst(r.price)}${r.groen ? ", hij laadt" : ""}`,
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
  return { balken, nul, gemiddeld, kwh };
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
    `Prijs per uur; in ${groen} van de ${berekend.balken.length} uren laadt hij.`
  );

  for (const b of berekend.balken) {
    const g = doc.createElementNS(NS, "g");
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
    staaf.setAttribute("class", b.groen ? "staaf groen" : "staaf");
    const titel = doc.createElementNS(NS, "title");
    titel.textContent = b.tip;
    g.append(vlak, staaf, titel);
    svg.append(g);
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
    const t = doc.createElement("span");
    t.textContent = b.label;
    t.style.left = `${((b.x + b.w / 2) / BREEDTE) * 100}%`;
    rij.append(t);
  }
  return rij;
}

/** De css die bij de grafiek hoort; de pop-up neemt hem op. */
export const prijsCss = /* css */ `
  .prijs-blok {
    margin: 0 0 14px;
    padding: 12px 12px 8px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(255,255,255,0.02);
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
  .prijsgrafiek .raak { fill: transparent; }
  .prijsgrafiek g:hover .staaf { opacity: 0.75; }
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
`;
