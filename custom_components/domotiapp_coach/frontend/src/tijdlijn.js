/**
 * De tijdlijn in Historie: wat de coach en de apparaten die hij stuurt op een
 * dag deden, als gekleurde balken (v0.115.0).
 *
 * De eigenaar op 11-10-2026: "Ik wil kunnen zien wat de coach en de aanstuurbare
 * apparaten hebben gedaan ... de geschiedenis kort en krachtig", en over de
 * vorm: "een tijdlijn inderdaad en als je op de tijdlijn klikt een korte tekst.
 * Het moet visueel sterk zijn. Niet teveel tekst, alles heel overzichtelijk."
 * Op 12-10-2026: "zoals de verloop van wat hij heeft gedaan".
 *
 * Wat er gebeurde komt uit de geschiedenis van Meldingen
 * (`domotiapp_coach/notifications/list`): elk besluit staat daar al, op het
 * moment dat het veranderde. Sinds v0.115.0 staan bij een besluit ook het
 * apparaat, de regel en de stand; een regel van daarvoor wordt herkend aan de
 * naam vooraan, zodat de weken van voor de update er meteen staan.
 *
 * **Waar de stroom vandaan kwam is een meting, geen besluit.** De eerste opzet
 * kleurde een laadbeurt naar de regel van de coach, en dat loog: bij de
 * eigenaar op 11-10-2026 stond 12:08 tot 13:47 als "vooral op zon" (82% van de
 * tijd een zonregel), terwijl er volgens de meter 3,7 van de 6,6 kWh van het
 * net kwam.
 * De kleur komt daarom uit de kwartieren van de eigen opslag
 * (`domotiapp_coach/history/quarters`): per kwartier wat het apparaat trok en
 * wat er van het net kwam, met dezelfde som als de coach per ronde maakt
 * (`_geld_bij`: wat het net gaf, tot wat het apparaat trok). Alleen zonder
 * kwartieren valt hij terug op de regel.
 *
 * Hier staat niets van Home Assistant in, zodat de proeven het in node kunnen
 * narekenen.
 */

import { huisNu } from "./format.js";

/** De kleuren, met de naam in de legenda. Oranje is eigen stroom, blauw het net. */
export const KLASSEN = {
  zon: "Eigen zon",
  net: "Van het net",
  wacht: "Wacht",
  vol: "Klaar",
  nul: "Nul op de meter",
  ontladen: "Ontladen",
  stil: "Stil",
  aan: "Aan",
  leeg: "Er liep niets",
};

/** Wat een stand op het scherm heet, in de korte tekst bij een klik. */
const STAND_TEKST = {
  laden: "Laden",
  wacht: "Wacht",
  vol: "Klaar",
  nul: "Nul op de meter",
  "accu-zon": "Alleen zonneladen",
  "accu-net": "Laden van het net",
  ontladen: "Ontladen",
  stil: "Stil",
  draait: "Draait",
  aan: "Stroom erop",
};

/** Bij welke stand de herkomst gemeten wordt: er loopt stroom door het apparaat heen. */
const GEMETEN = new Set(["laden", "draait", "aan"]);

const PAAL_ZON = new Set(["surplus", "zon-modus"]);

const ACCU_STAND = {
  nul: "nul",
  zonneladen: "accu-zon",
  netladen: "accu-net",
  "max-laden": "accu-net",
  ontladen: "ontladen",
  handelen: "ontladen",
  standby: "stil",
};

/** De namen van `STAND_NAMEN` in batterij.py, voor regels van voor v0.115.0. */
const ACCU_KOP = [
  ["nul op de meter", "nul"],
  ["alleen zonneladen", "accu-zon"],
  ["alleen ontladen", "ontladen"],
  ["laden van het net", "accu-net"],
  ["maximaal laden", "accu-net"],
  ["handelen", "ontladen"],
  ["standby", "stil"],
];

/**
 * Redenen die er onderweg bij horen maar niet zeggen waarom er geladen werd:
 * wekken, en nog even doorladen op de laagste stand (`+wake` en `+hold` in
 * planner.py). Bij de eigenaar op 11-10-2026 stond "hij biedt even 16 A aan om
 * hem wakker te maken" anders bij elke laadbeurt van die dag als de reden.
 */
const BIJZAAK_REGEL = /\+(wake|hold)\b/;
const BIJZAAK_TEKST = /wakker te maken|nog even (vol|door) op de laagste stand|laadt tot dan door op de laagste stand/i;

/** Of een apparaat een balk krijgt, en welke soort balk. */
export function balkSoort(device) {
  if (device?.type === "laadpaal") return "laadpaal";
  if (device?.type === "thuisbatterij") return "thuisbatterij";
  if (device?.type === "boiler") return "boiler";
  // Een airco staat aan of uit, net als een boiler (v0.119.0).
  if (device?.type === "airco") return "boiler";
  if (["vaatwasser", "wasmachine", "droger"].includes(device?.type)) return "programma";
  return null;
}

/**
 * Bij welk apparaat een regel hoort. Sinds v0.115.0 staat het erbij; daarvoor
 * is het de naam waarmee de regel begint ("Laadpaal: ...", "Batterij doet ...").
 */
export function apparaatVan(item, devices) {
  if (item?.device) return devices.find((d) => d.id === item.device) ?? null;
  const tekst = String(item?.message ?? "");
  // De langste naam eerst, anders wint "Bus" van "Bus achter".
  const kandidaten = [...devices]
    .filter((d) => d.name)
    .sort((a, b) => b.name.length - a.name.length);
  return kandidaten.find((d) => tekst.startsWith(`${d.name}:`) || tekst.startsWith(`${d.name} `)) ?? null;
}

/** Wat er na "Naam: kop." staat: de reden, voor de korte tekst bij een klik. */
export function reden(item, device) {
  let tekst = String(item?.message ?? "");
  if (device?.name && tekst.startsWith(device.name)) tekst = tekst.slice(device.name.length).replace(/^[:\s]+/, "");
  const punt = tekst.indexOf(". ");
  const rest = punt >= 0 ? tekst.slice(punt + 2) : "";
  return rest.trim();
}

/** Of een reden een bijzaak is: wekken of nog even doorladen. */
export function bijzaak(item, tekst) {
  return BIJZAAK_REGEL.test(String(item?.rule ?? "")) || BIJZAAK_TEKST.test(String(tekst ?? ""));
}

/**
 * Welke stand deze regel begint, of `undefined` als hij niets verandert (een
 * regel als "is vol; hij volgt het plan weer"). `null` betekent: vanaf hier
 * geen balk, zoals een paal zonder kabel of een vaatwasser die klaar is.
 *
 * Bij laden zegt `bron` wat de regel van de coach was ("zon" of "net"); dat
 * telt alleen als er geen meting is.
 */
export function standVan(item, device) {
  const soort = balkSoort(device);
  const tekst = String(item?.message ?? "").toLowerCase();
  const kop = tekst.slice((device?.name ?? "").length).replace(/^[:\s]+/, "");
  const regel = String(item?.rule ?? "").split("+")[0];

  if (soort === "laadpaal") {
    if (item.rule !== undefined || item.charge !== undefined) {
      if (item.charge) return { stand: "laden", bron: PAAL_ZON.has(regel) ? "zon" : "net" };
      if (regel === "disconnected") return null;
      if (regel === "complete") return { stand: "vol" };
      return { stand: "wacht" };
    }
    if (kop.startsWith("laden op") || kop.startsWith("zou laden")) {
      return { stand: "laden", bron: /zon over|op zon|eigen zon/.test(tekst) ? "zon" : "net" };
    }
    if (kop.startsWith("niet laden") || kop.startsWith("zou niet laden")) {
      // De tekst van sinds v0.130.1, en die van daarvoor voor wat al in de geschiedenis staat.
      if (tekst.includes("geen auto aangesloten") || tekst.includes("geen auto aan de lader")) return null;
      if (tekst.includes("verder hoeft hij niet") || tekst.includes("is vol")) return { stand: "vol" };
      return { stand: "wacht" };
    }
    return undefined;
  }

  if (soort === "thuisbatterij") {
    if (item.mode) return { stand: ACCU_STAND[item.mode] ?? "nul" };
    if (item.self_zero === true) return { stand: "nul" };
    if (item.self_zero === false) return undefined;
    if (kop.startsWith("doet zelf nul op de meter")) return { stand: "nul" };
    for (const [naam, stand] of ACCU_KOP) {
      if (kop.startsWith(naam) || kop.startsWith(`zou op ${naam}`)) return { stand };
    }
    return undefined;
  }

  if (soort === "programma") {
    if (item.rule !== undefined) return regel === "running" ? { stand: "draait" } : null;
    if (kop.startsWith("draait")) return { stand: "draait" };
    if (kop.startsWith("wacht") || kop.startsWith("start") || kop.startsWith("zou") || kop.startsWith("zet")) return null;
    return undefined;
  }

  // Een boiler is een buffer: de coach zet de stroom erop of eraf, en de
  // thermostaat beslist of er werkelijk iets loopt (docs/boiler.md).
  if (soort === "boiler") {
    if (item.charge !== undefined) return item.charge ? { stand: "aan" } : null;
    if (kop.startsWith("start nu") || kop.startsWith("zet hem aan") || kop.startsWith("draait")) return { stand: "aan" };
    if (kop.startsWith("wacht") || kop.startsWith("zou")) return null;
    return undefined;
  }
  return undefined;
}

/**
 * De balken van één dag.
 *
 * `items` is de lijst uit Meldingen, in welke volgorde ook; de stand aan het
 * begin van de dag is die van het laatste besluit daarvoor. Een stuk loopt tot
 * het volgende besluit dat iets anders zegt, en de dag van vandaag houdt op bij
 * `nu`. Per stuk staat bij elke reden hoe lang hij gold, zodat de hoofdreden
 * de reden is die het langst gold en niet de eerste.
 */
export function tijdlijn(items, devices, van, tot, nu = huisNu()) {
  const eind = new Date(Math.min(tot.getTime(), nu.getTime()));
  const rijen = [];
  for (const device of devices) {
    const soort = balkSoort(device);
    if (!soort) continue;
    const eigen = [];
    for (const item of items) {
      if (item?.kind !== "besluit") continue;
      const at = new Date(item.at);
      if (Number.isNaN(at.getTime()) || at >= eind) continue;
      if (apparaatVan(item, devices)?.id !== device.id) continue;
      const s = standVan(item, device);
      if (s === undefined) continue;
      const tekst = reden(item, device);
      eigen.push({ at, stand: s, reden: tekst, bijzaak: bijzaak(item, tekst) });
    }
    eigen.sort((a, b) => a.at - b.at);

    const stukken = [];
    let open = null;
    const sluit = (moment) => {
      if (open && moment > open.van) {
        tijdBij(open, open.laatste, moment);
        stukken.push({ ...open, tot: moment });
      }
      open = null;
    };
    for (const regel of eigen) {
      const begin = regel.at < van ? van : regel.at;
      if (open && regel.stand && open.stand === regel.stand.stand && open.bron === (regel.stand.bron ?? null)) {
        tijdBij(open, open.laatste, begin);
        open.laatste = { reden: regel.reden, bijzaak: regel.bijzaak, sinds: begin };
        continue;
      }
      sluit(begin);
      if (regel.stand !== null) {
        open = {
          van: begin,
          stand: regel.stand.stand,
          bron: regel.stand.bron ?? null,
          redenen: [],
          laatste: { reden: regel.reden, bijzaak: regel.bijzaak, sinds: begin },
        };
      }
    }
    sluit(eind);
    const samen = samenvoegen(stukken.map(({ laatste, ...stuk }) => stuk));
    if (samen.length) rijen.push({ device: device.id, naam: device.name || "", soort, stukken: samen });
  }
  return rijen;
}

/** De tijd van één reden bij een stuk optellen. */
function tijdBij(stuk, regel, tot) {
  if (!regel?.reden) return;
  const ms = Math.max(0, tot - regel.sinds);
  const al = stuk.redenen.find((r) => r.tekst === regel.reden);
  if (al) al.ms += ms;
  else stuk.redenen.push({ tekst: regel.reden, ms, bijzaak: regel.bijzaak });
}

/** Hoe kort een gat of een tussenstuk mag zijn om in het stuk eromheen op te gaan. */
const KORT_MS = 3 * 60 * 1000;

/**
 * Van besluiten naar iets wat je in één oogopslag leest.
 *
 * Een laadbeurt is één stuk, ook als de coach onderweg tussen zon, "nog even
 * door" en wekken wisselt: bij de eigenaar op 11-10-2026 stonden er anders
 * tussen 12:08 en 13:47 acht stukjes van een paar minuten. Een gat of een
 * tussenstuk korter dan `KORT_MS` gaat op in wat eromheen staat (een
 * vaatwasser die een tel "wacht" zei midden in zijn programma, een stop die de
 * paal een minuut later doorzette). `bron` is daarna wat de regel het langst
 * zei; de meting gaat daar later overheen (`metHerkomst`).
 */
export function samenvoegen(stukken) {
  const uit = [];
  const bij = (doel, stuk) => {
    doel.tot = stuk.tot;
    for (const [bron, ms] of Object.entries(stuk.bronTijd)) doel.bronTijd[bron] = (doel.bronTijd[bron] ?? 0) + ms;
    for (const r of stuk.redenen) {
      const al = doel.redenen.find((x) => x.tekst === r.tekst);
      if (al) al.ms += r.ms;
      else doel.redenen.push({ ...r });
    }
  };
  for (const ruw of stukken) {
    const stuk = {
      ...ruw,
      redenen: ruw.redenen.map((r) => ({ ...r })),
      bronTijd: ruw.bron ? { [ruw.bron]: ruw.tot - ruw.van } : {},
    };
    const vorige = uit[uit.length - 1];
    if (vorige && vorige.stand === stuk.stand && stuk.van - vorige.tot <= KORT_MS) {
      bij(vorige, stuk);
      continue;
    }
    // Een kort tussenstuk tussen twee stukken van dezelfde stand hoort erbij.
    const voorvorige = uit[uit.length - 2];
    if (
      vorige && voorvorige && vorige.tot - vorige.van <= KORT_MS &&
      voorvorige.stand === stuk.stand && vorige.van - voorvorige.tot <= KORT_MS &&
      stuk.van - vorige.tot <= KORT_MS
    ) {
      uit.pop();
      bij(voorvorige, stuk);
      continue;
    }
    uit.push(stuk);
  }
  for (const stuk of uit) {
    const zon = stuk.bronTijd.zon ?? 0;
    const net = stuk.bronTijd.net ?? 0;
    stuk.bron = zon + net > 0 ? (zon >= net ? "zon" : "net") : null;
    delete stuk.bronTijd;
  }
  return uit;
}

/** De reden die het langst gold, met een bijzaak als wekken alleen als er niets anders was. */
export function hoofdreden(stuk) {
  const redenen = stuk?.redenen ?? [];
  const kies = (lijst) => lijst.reduce((beste, r) => (!beste || r.ms > beste.ms ? r : beste), null);
  return (kies(redenen.filter((r) => !r.bijzaak)) ?? kies(redenen))?.tekst ?? "";
}

const KWARTIER_MS = 15 * 60 * 1000;

/**
 * Hoeveel er door het apparaat ging en hoeveel daarvan van het net kwam, per stuk.
 *
 * `vermogen` zijn de kwartieren van het apparaat, `net` die van wat er van het
 * net kwam, allebei in watt zoals `quarters` in statistics.js ze geeft. Per
 * kwartier telt van het net wat de meter binnenkreeg, tot wat het apparaat trok:
 * dezelfde som als de coach per ronde maakt, waarin het huis eerst de zon krijgt
 * en het net daarna. Een stuk dat maar een deel van een kwartier beslaat krijgt
 * dat deel. Zonder kwartieren blijft het stuk zoals het was.
 */
export function herkomst(stuk, vermogen, net) {
  if (!vermogen?.length) return null;
  // De kwartieren komen op de klok van het huis binnen (`quarters` in statistics.js,
  // v0.138.2), net als de besluiten van de coach.
  const netOp = new Map((net ?? []).map((rij) => [rij.start.getTime(), rij]));
  let kwh = 0;
  let netKwh = 0;
  let gedekt = 0;
  for (const rij of vermogen) {
    const begin = rij.start.getTime();
    const einde = begin + KWARTIER_MS;
    const deel = (Math.min(einde, stuk.tot.getTime()) - Math.max(begin, stuk.van.getTime())) / KWARTIER_MS;
    if (deel <= 0) continue;
    const uren = (Math.max(0, Number(rij.seconden) || 0) / 3600) * deel;
    const watt = Math.max(0, Number(rij.gemiddeld) || 0);
    const vanNet = netOp.has(begin) ? Math.max(0, Number(netOp.get(begin).gemiddeld) || 0) : null;
    kwh += (watt * uren) / 1000;
    if (vanNet !== null) netKwh += (Math.min(watt, vanNet) * uren) / 1000;
    gedekt += uren * 3600 * 1000;
  }
  if (gedekt <= 0) return null;
  return { kwh, netKwh, gedekt: Math.min(1, gedekt / Math.max(1, stuk.tot - stuk.van)) };
}

/**
 * De kwartieren van het net als één reeks "van het net", in watt.
 *
 * Twee losse meters: de afname. Een meter met een teken: wat erboven nul zit,
 * na het vinkje omkeren van de klant. Zo werkt het voor allebei de vormen.
 */
export function netReeks(bronnen, kwartieren) {
  if (bronnen?.grid_mode === "signed") {
    const teken = bronnen.grid_signed_invert ? -1 : 1;
    return (kwartieren.get(bronnen.grid_signed) ?? []).map((rij) => ({
      ...rij,
      gemiddeld: Math.max(0, teken * Number(rij.gemiddeld)),
    }));
  }
  return kwartieren.get(bronnen?.grid_import) ?? [];
}

/** Onder dit is er niets gemeten dat een kleur verdient. */
const NIETS_KWH = 0.05;

/**
 * De meting over de balken heen: de kleur van een stuk waar stroom door liep.
 *
 * `vermogenVan(deviceId)` geeft de kwartieren van dat apparaat, `net` de reeks
 * van `netReeks`. Een stuk krijgt `kwh` en `netDeel`, en zijn kleur wordt wat
 * de meter zegt: meer dan de helft van het net is blauw, anders oranje.
 */
export function metHerkomst(rijen, vermogenVan, net) {
  for (const rij of rijen) {
    const vermogen = vermogenVan(rij.device);
    for (const stuk of rij.stukken) {
      if (!GEMETEN.has(stuk.stand)) continue;
      const meting = herkomst(stuk, vermogen, net);
      if (!meting) continue;
      stuk.kwh = meting.kwh;
      // Aan, maar er liep niets: een auto die niet wakker werd, een vol vat.
      // Dat is geen zon en geen net, en zo hoort hij er ook uit te zien.
      if (meting.kwh < NIETS_KWH) {
        stuk.bron = null;
        stuk.leeg = true;
        continue;
      }
      if (net?.length) {
        stuk.netDeel = meting.netKwh / meting.kwh;
        stuk.bron = stuk.netDeel > 0.5 ? "net" : "zon";
        stuk.gemeten = true;
      }
    }
  }
  return rijen;
}

/** De kleur van een stuk: de herkomst als die er is, anders de stand. */
export function klasseVan(stuk) {
  if (GEMETEN.has(stuk.stand)) {
    if (stuk.leeg) return "leeg";
    return stuk.bron ?? "aan";
  }
  if (stuk.stand === "accu-zon") return "zon";
  if (stuk.stand === "accu-net") return "net";
  return KLASSEN[stuk.stand] ? stuk.stand : "wacht";
}

/** De meldingen van die dag die als stip boven de balken komen: kritiek en verslagen. */
export function stippen(items, van, tot) {
  return items
    .filter((item) => item?.kind === "kritiek" || item?.kind === "melding")
    .map((item) => ({ at: new Date(item.at), kritiek: item.kind === "kritiek", tekst: String(item.message ?? "") }))
    .filter((stip) => stip.at >= van && stip.at < tot)
    .sort((a, b) => a.at - b.at);
}

/** "12:08" */
export function klok(moment) {
  return `${String(moment.getHours()).padStart(2, "0")}:${String(moment.getMinutes()).padStart(2, "0")}`;
}

/** "ma 12": de dag op de as van een week en in de tekst bij een klik. */
export function dagKort(moment) {
  return `${moment.toLocaleDateString("nl-NL", { weekday: "short" }).replace(".", "")} ${moment.getDate()}`;
}

const zelfdeDag = (a, b) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

/**
 * Van wanneer tot wanneer een stuk liep: "12:08 tot 13:47", en bij een week met
 * de dag erbij, "za 11 12:08 tot 13:47" of "za 11 22:30 tot zo 12 01:40". Een
 * stuk dat om middernacht ophoudt eindigt om 24:00, en een stuk dat nog loopt
 * "nu".
 */
function tijdVan(stuk, { nu, metDag = false } = {}) {
  const begin = metDag ? `${dagKort(stuk.van)} ${klok(stuk.van)}` : klok(stuk.van);
  if (nu && Math.abs(stuk.tot.getTime() - nu.getTime()) < 60_000) return `${begin} tot nu`;
  const middernacht = stuk.tot.getHours() === 0 && stuk.tot.getMinutes() === 0;
  const dag = middernacht ? new Date(stuk.tot.getTime() - 1) : stuk.tot;
  const uur = middernacht ? "24:00" : klok(stuk.tot);
  return `${begin} tot ${metDag && !zelfdeDag(dag, stuk.van) ? `${dagKort(dag)} ${uur}` : uur}`;
}

const kommagetal = (waarde, cijfers = 1) =>
  waarde.toLocaleString("nl-NL", { minimumFractionDigits: cijfers, maximumFractionDigits: cijfers });

/** Een deel als "ongeveer 55%", op vijf procent, want het is een kwartiermeting. */
function ongeveer(deel) {
  return `ongeveer ${Math.round((deel * 100) / 5) * 5}%`;
}

/**
 * De korte tekst bij een klik: wanneer, wat, hoeveel, en waarom.
 *
 * `metAccu`: of er een thuisbatterij is. Wat niet van het net kwam is dan zon of
 * batterij, en dat zegt de tekst ook, want de meter ziet het verschil niet.
 */
export function klikTekst(rij, stuk, { nu, metAccu = false, metDag = false } = {}) {
  const tijd = tijdVan(stuk, { nu, metDag });
  let wat = STAND_TEKST[stuk.stand] ?? "";
  if (stuk.leeg) {
    wat += ", er liep niets";
  } else if (Number.isFinite(stuk.kwh) && stuk.kwh >= NIETS_KWH) {
    wat += `, ${kommagetal(stuk.kwh)} kWh`;
    if (Number.isFinite(stuk.netDeel)) {
      const eigen = metAccu ? "zon of batterij" : "zon";
      if (stuk.netDeel >= 0.95) wat += ", van het net";
      else if (stuk.netDeel <= 0.05) wat += `, op ${eigen}`;
      else wat += `, ${ongeveer(stuk.netDeel)} van het net`;
    }
  } else if (stuk.stand === "laden" && stuk.bron) {
    wat += stuk.bron === "zon" ? ", vooral op zon" : ", vooral van het net";
  }
  return { naam: rij.naam, tijd, wat: `${wat}.`, reden: hoofdreden(stuk) };
}

const escape = (tekst) =>
  String(tekst ?? "").replace(/[&<>"]/g, (teken) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[teken]);

/** De legenda: alleen de kleuren die die dag voorkomen, in een vaste volgorde. */
export function legenda(rijen, metAccu = false) {
  const gebruikt = new Set(rijen.flatMap((rij) => rij.stukken.map(klasseVan)));
  return Object.keys(KLASSEN)
    .filter((klasse) => gebruikt.has(klasse))
    // Zoals de grafiek erboven het noemt (`paintLegend_` in history.js).
    .map((klasse) => ({ klasse, label: klasse === "zon" && metAccu ? "Eigen zon en batterij" : KLASSEN[klasse] }));
}

/**
 * De tijdlijn als HTML: een rij per apparaat, de meldingen als stippen erboven,
 * de uren eronder en een streep op nu. Voor een week (v0.116.1) staan er dagen
 * langs de as en een lijntje per dag; de eigenaar op 13-10-2026, bij Week:
 * "waarom is de tijdlijn weg die wil ik wel behouden".
 *
 * Elk stuk en elke stip is een knop met `data-rij` en `data-stuk` (of
 * `data-stip`), zodat een klik in history.js de tekst eronder kan zetten.
 * `gekozen` is wat er nu open staat, als `"rij:stuk"` of `"stip:i"`.
 */
export function tekenTijdlijn({ rijen, stippen: punten = [], van, tot, nu, gekozen = "", metAccu = false }) {
  const lengte = tot - van;
  const metDag = meerDagen(van, tot);
  const plek = (moment) => Math.max(0, Math.min(100, ((moment - van) / lengte) * 100));
  const rond = (getal) => Math.round(getal * 100) / 100;
  // De streep op nu staat in elke baan apart, zodat hij op een telefoon, waar
  // de naam boven de baan staat, niet door de namen heen loopt.
  const nuStreep =
    nu && nu > van && nu < tot ? `<div class="nu" style="left:${rond(plek(nu))}%" aria-hidden="true"></div>` : "";

  const balken = rijen
    .map((rij, r) => {
      const stukken = rij.stukken
        .map((stuk, s) => {
          const links = plek(stuk.van);
          const breed = Math.max(0, plek(stuk.tot) - links);
          const tekst = klikTekst(rij, stuk, { nu, metAccu, metDag });
          const sleutel = `${r}:${s}`;
          return `<button type="button" class="stuk ${klasseVan(stuk)}${gekozen === sleutel ? " gekozen" : ""}"
            data-rij="${r}" data-stuk="${s}" style="left:${rond(links)}%;width:${rond(breed)}%"
            aria-pressed="${gekozen === sleutel}" aria-label="${escape(`${tekst.tijd}: ${tekst.wat}`)}"></button>`;
        })
        .join("");
      return `<div class="rij"><div class="naam">${escape(rij.naam)}</div><div class="baan">${stukken}${nuStreep}</div></div>`;
    })
    .join("");

  const stipRij = punten.length
    ? `<div class="rij stippen"><div class="naam">Meldingen</div><div class="baan">${punten
        .map((stip, i) => `<button type="button" class="stip${stip.kritiek ? " kritiek" : ""}${gekozen === `stip:${i}` ? " gekozen" : ""}"
          data-stip="${i}" style="left:${rond(plek(stip.at))}%" aria-pressed="${gekozen === `stip:${i}`}"
          aria-label="${escape(`${stipTijd(stip, metDag)}: ${stip.tekst}`)}"></button>`)
        .join("")}${nuStreep}</div></div>`
    : "";

  const dagen = [];
  for (let dag = new Date(van); dag < tot; dag = new Date(dag.getFullYear(), dag.getMonth(), dag.getDate() + 1)) {
    dagen.push(dag);
  }
  const uren = metDag
    ? dagen
        .map((dag) => {
          const morgen = new Date(dag.getFullYear(), dag.getMonth(), dag.getDate() + 1);
          const midden = new Date((dag.getTime() + morgen.getTime()) / 2);
          return `<span class="dag" style="left:${rond(plek(midden))}%">${dagKort(dag)}</span>`;
        })
        .join("")
    : [0, 6, 12, 18, 24]
        .map((uur) => `<span style="left:${(uur / 24) * 100}%">${String(uur).padStart(2, "0")}:00</span>`)
        .join("");
  // Het lijntje in de baan: om de drie uur op een dag, om de dag in een week.
  const raster = metDag ? rond(100 / Math.max(1, dagen.length)) : 12.5;
  return `
    <div class="tijdlijn" style="--raster:${raster}%">
      <div class="rijen">${stipRij}${balken}</div>
      <div class="uren" aria-hidden="true">${uren}</div>
    </div>`;
}

/** De tekst onder de tijdlijn bij wat er gekozen is, of leeg. */
export function tekenUitleg({ rijen, stippen: punten = [], gekozen = "", van, tot, nu, metAccu = false }) {
  const metDag = van && tot ? meerDagen(van, tot) : false;
  if (gekozen.startsWith("stip:")) {
    const stip = punten[Number(gekozen.slice(5))];
    if (!stip) return "";
    return `<div class="tijd">${stipTijd(stip, metDag)}${stip.kritiek ? " · moet je iets mee" : ""}</div>
      <p class="wat">${escape(stip.tekst)}</p>`;
  }
  const [r, s] = gekozen.split(":").map(Number);
  const rij = rijen[r];
  const stuk = rij?.stukken[s];
  if (!stuk) return "";
  const tekst = klikTekst(rij, stuk, { nu, metAccu, metDag });
  return `<div class="tijd"><strong>${escape(tekst.naam)}</strong> · ${tekst.tijd}</div>
    <p class="wat"><span class="vlek ${klasseVan(stuk)}"></span>${escape(tekst.wat)}</p>
    ${tekst.reden ? `<p class="reden">${escape(tekst.reden)}</p>` : ""}`;
}

/** Of een tijdlijn meer dan een dag beslaat; een dag waarop de klok verzet wordt telt nog als een. */
function meerDagen(van, tot) {
  return tot - van > 26 * 3600 * 1000;
}

function stipTijd(stip, metDag) {
  return metDag ? `${dagKort(stip.at)} ${klok(stip.at)}` : klok(stip.at);
}
