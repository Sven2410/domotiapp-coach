/**
 * De tijdvakken en de prijs van een Portugees stroomcontract (v0.137.0).
 *
 * De tweeling van tarifas.py: Historie rekent een uur met dezelfde regels als de
 * coach. Zie daar en docs/contract.md, Portugal. Kent Home Assistant niet.
 */

export const NAMEN = {
  simples: "Enkel (simples)",
  vazio: "Daluren (vazio)",
  fora_vazio: "Buiten de daluren (fora do vazio)",
  cheias: "Normaal (cheias)",
  ponta: "Piek (ponta)",
};

const DIARIO_VAZIO = [[0, 480], [1320, 1440]];
const DIARIO_PONTA = { inverno: [[540, 630], [1080, 1230]], verao: [[630, 780], [1170, 1260]] };
const SEMANAL_UTIL_VAZIO = [[0, 420]];
const SEMANAL_UTIL_PONTA = { inverno: [[570, 720], [1110, 1260]], verao: [[555, 735]] };
const SEMANAL_SABADO_CHEIAS = { inverno: [[570, 780], [1110, 1320]], verao: [[540, 840], [1200, 1320]] };

function laatsteZondag(jaar, maand) {
  // maand 1..12; de laatste dag van die maand, dan terug naar zondag.
  const dag = new Date(Date.UTC(jaar, maand, 0));
  dag.setUTCDate(dag.getUTCDate() - dag.getUTCDay());
  return dag;
}

/** Of het in Lissabon zomertijd is, met de EU-regel, zoals `zomertijd` in tarifas.py. */
export function zomertijd(when) {
  const t = new Date(when).getTime();
  const jaar = new Date(t).getUTCFullYear();
  const begin = laatsteZondag(jaar, 3).getTime() + 3600000;
  const eind = laatsteZondag(jaar, 10).getTime() + 3600000;
  return t >= begin && t < eind;
}

/** De lokale tijd in Lissabon als {weekdag (0 maandag), minuut}, en of het zomertijd is. */
export function lissabon(when) {
  const zomer = zomertijd(when);
  const lokaal = new Date(new Date(when).getTime() + (zomer ? 3600000 : 0));
  return { weekdag: (lokaal.getUTCDay() + 6) % 7, minuut: lokaal.getUTCHours() * 60 + lokaal.getUTCMinutes(), zomer };
}

const binnen = (minuut, vakken) => vakken.some(([van, tot]) => van <= minuut && minuut < tot);

/** Het tijdvak van een moment, zoals `periodo` in tarifas.py. */
export function periodo(when, tarifa, ciclo) {
  if (tarifa !== "bi" && tarifa !== "tri") return "simples";
  const { weekdag, minuut, zomer } = lissabon(when);
  const seizoen = zomer ? "verao" : "inverno";
  if (ciclo === "semanal") {
    if (weekdag === 6) return "vazio";
    if (weekdag === 5) return binnen(minuut, SEMANAL_SABADO_CHEIAS[seizoen]) ? (tarifa === "tri" ? "cheias" : "fora_vazio") : "vazio";
    if (binnen(minuut, SEMANAL_UTIL_VAZIO)) return "vazio";
    if (tarifa === "bi") return "fora_vazio";
    return binnen(minuut, SEMANAL_UTIL_PONTA[seizoen]) ? "ponta" : "cheias";
  }
  if (binnen(minuut, DIARIO_VAZIO)) return "vazio";
  if (tarifa === "bi") return "fora_vazio";
  return binnen(minuut, DIARIO_PONTA[seizoen]) ? "ponta" : "cheias";
}

/** De tijdvakken van deze tarifa, in de volgorde van het scherm. */
export function periodos(pt) {
  return { simples: ["simples"], bi: ["vazio", "fora_vazio"], tri: ["vazio", "cheias", "ponta"] }[pt?.tarifa ?? "bi"] ?? ["vazio", "fora_vazio"];
}

/** Wat een kWh in dit tijdvak kost, met IEC en IVA, zoals `preco` in tarifas.py. */
export function preco(pt, periode) {
  const energie = Number(pt?.energia?.[periode]);
  if (!Number.isFinite(energie) || energie <= 0) return null;
  const iec = Number(pt?.iec) || 0;
  const iva = pt?.iva === undefined || pt?.iva === null || pt?.iva === "" ? 23 : Number(pt.iva) || 0;
  return Math.round((energie + iec) * (1 + iva / 100) * 1e6) / 1e6;
}

/** Wat een teruggeleverde kWh opbrengt, zoals `terug` in tarifas.py. */
export function terug(pt, omie = null) {
  const e = pt?.excedente ?? {};
  if (e.modo === "nenhum") return 0;
  if (e.modo === "fixo") return Number(e.preco) || 0;
  if (e.modo === "omie") return omie === null || omie === undefined ? null : Math.round(omie * (Number(e.fator) || 0) / 100 * 1e6) / 1e6;
  // Nog niet gekozen: onbekend, en niet nul.
  return null;
}

/**
 * Wat een kWh in [when, when + lengte) kostte en opbracht: het gemiddelde van de
 * kwartieren, want een tijdvak kan op een half uur beginnen.
 */
export function ptPrijsOp(pt, when, lengte = 3600000) {
  const begin = new Date(when).getTime();
  const stappen = Math.max(1, Math.round(lengte / 900000));
  let som = 0;
  let n = 0;
  for (let i = 0; i < stappen; i += 1) {
    const p = preco(pt, periodo(begin + i * 900000, pt?.tarifa ?? "bi", pt?.ciclo ?? "diario"));
    if (p === null) return { koop: null, terug: terug(pt) };
    som += p;
    n += 1;
  }
  return { koop: n ? som / n : null, terug: terug(pt) };
}
