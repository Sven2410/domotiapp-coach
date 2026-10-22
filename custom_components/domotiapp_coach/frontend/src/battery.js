/**
 * Wat de kaart van een thuisbatterij laat zien, uit het besluit van de coach.
 *
 * Los van de kaart zelf, zodat het na te meten is zonder scherm (zie
 * test_rapport.mjs). Alles wat hier staat heeft de coach gemeten of uitgerekend;
 * wat hij niet weet krijgt geen regel, of een regel die zegt dat hij het niet
 * weet.
 */

import { huisNu } from "./format.js";
import { locale, nt, t, tn } from "./i18n.js";
import { perUur } from "./prijsgrafiek.js";

const euro = (bedrag, cijfers = 2) =>
  `€ ${Number(bedrag).toLocaleString(locale(), { minimumFractionDigits: cijfers, maximumFractionDigits: cijfers })}`;

// Op de kaart nooit onder nul (v0.148.1). De eigenaar op 22-10-2026, bij "Opgeleverd € -7,46"
// en "Terugverdiend − € 7,46" thuis: "min getal wil ik niet, zet dan nul tot dat hij boven de
// nul is." Het kasboek zelf houdt het echte bedrag, zodat een tekort eerst ingelopen wordt.
const nietOnderNul = (bedrag) => euro(Math.max(0, Number(bedrag) || 0));

const klok = (iso) => String(iso ?? "").slice(11, 16);

const datum = (iso) => {
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(locale(), { month: "long", year: "numeric" });
};

/** De eerste aaneengesloten reeks uren waarin het plan van het net wil laden. */
export function volgendeNetlading(hours = []) {
  const eerste = hours.findIndex((uur) => Number(uur.grid_kwh) > 0.05);
  if (eerste < 0) return null;
  let laatste = eerste;
  while (laatste + 1 < hours.length && Number(hours[laatste + 1].grid_kwh) > 0.05) laatste += 1;
  const kwh = hours.slice(eerste, laatste + 1).reduce((som, uur) => som + Number(uur.grid_kwh), 0);
  return { start: hours[eerste].start, end: hours[laatste].end, kwh };
}

/** De naam van een stand met een hoofdletter, voor de grafiek ("Nul op de meter"). */
export function standNaam(stand) {
  const naam = naamVan(stand) ?? "";
  return naam.charAt(0).toUpperCase() + naam.slice(1);
}

// Nederlands, zoals `STAND_NAMEN` in batterij.py; vertaald waar hij getoond wordt
// (`naamVan`, v0.139.0).
const STAND_NAMEN = {
  nul: nt("nul op de meter"),
  zonneladen: nt("alleen zonneladen"),
  ontladen: nt("alleen ontladen"),
  netladen: nt("laden van het net"),
  "max-laden": nt("maximaal laden"),
  handelen: nt("handelen"),
  standby: nt("standby"),
};

/** De naam van een stand in de taal van nu; een onbekende stand zoals hij is. */
const naamVan = (stand) => (STAND_NAMEN[stand] ? t(STAND_NAMEN[stand]) : stand);

/**
 * Het plan van de coach voor de komende uren, samengevat per stand.
 *
 * De eigenaar op 22-09-2026: "ik kan nu niet zien wat de coach van plan is met
 * de batterij." De coach rekent het per uur uit; hier worden uren met dezelfde
 * stand samengevoegd tot één regel: van wanneer tot wanneer, wat hij doet, en
 * van hoeveel naar hoeveel procent. Laden van het net krijgt de kWh en de
 * gemiddelde prijs erbij.
 *
 * @returns {Array<{label: string, text: string}>}
 */
export function planRegels(hours = [], maxRegels = 8) {
  const uren = (hours ?? []).filter((u) => u && u.start && u.end);
  if (!uren.length) return [];
  const blokken = [];
  for (const uur of uren) {
    const laatste = blokken[blokken.length - 1];
    if (laatste && laatste.mode === uur.mode) {
      laatste.end = uur.end;
      laatste.socEind = uur.soc;
      laatste.kwh += Number(uur.grid_kwh) || 0;
      if (Number.isFinite(uur.price)) { laatste.prijsSom += uur.price; laatste.prijsN += 1; }
      laatste.n += 1;
    } else {
      blokken.push({
        mode: uur.mode, start: uur.start, end: uur.end,
        socBegin: laatste ? laatste.socEind : null, socEind: uur.soc,
        kwh: Number(uur.grid_kwh) || 0,
        prijsSom: Number.isFinite(uur.price) ? uur.price : 0, prijsN: Number.isFinite(uur.price) ? 1 : 0, n: 1,
      });
    }
  }
  const dagKlok = (iso) => {
    // De dag van het huis (v0.138.1); toISOString gaf de dag in UTC.
    const n = huisNu();
    const vandaag = `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, "0")}-${String(n.getDate()).padStart(2, "0")}`;
    const dag = String(iso ?? "").slice(0, 10);
    return dag && dag !== vandaag && dag > vandaag ? t("morgen {klok}", { klok: klok(iso) }) : klok(iso);
  };
  return blokken.slice(0, maxRegels).map((b) => {
    let text = naamVan(b.mode);
    if (Number.isFinite(b.socEind)) {
      text += Number.isFinite(b.socBegin) && Math.round(b.socBegin) !== Math.round(b.socEind)
        ? `, ${t("van {van} naar {naar}%", { van: Math.round(b.socBegin), naar: Math.round(b.socEind) })}`
        : `, ${Math.round(b.socEind)}%`;
    }
    if (b.kwh > 0.05) {
      const kwh = `${b.kwh.toLocaleString(locale(), { maximumFractionDigits: 1 })} kWh`;
      text += `, ${b.prijsN ? t("{kwh} tegen {prijs}", { kwh, prijs: euro(b.prijsSom / b.prijsN, 3) }) : kwh}`;
    }
    return { label: t("{van} tot {tot}", { van: dagKlok(b.start), tot: dagKlok(b.end) }), text };
  });
}

const kwhTekst = (kwh) =>
  `${Number(kwh).toLocaleString(locale(), { minimumFractionDigits: 1, maximumFractionDigits: 1 })} kWh`;

/**
 * De conclusie van de nachtzin: de laatste zin van `plan`, "Je houdt naar
 * verwachting ..." of "Je komt naar verwachting ... tekort". De hele zin staat
 * in de pop-up; op de kaart is de conclusie genoeg.
 */
export function nachtConclusie(besluit) {
  const tekst = String(besluit?.plan ?? "").trim();
  if (!tekst || besluit?.kind !== "batterij" || !Number.isFinite(besluit?.balance_kwh)) return tekst;
  const zinnen = tekst.split(/(?<=\.)\s+(?=[A-Z])/);
  return zinnen[zinnen.length - 1];
}

/**
 * Wat de pop-up "Wat gaat hij doen" van een batterij laat zien.
 *
 * De eigenaar op 23-09-2026: "ik wil het plan van de accu net als de laadpaal
 * hebben, zo'n pop-up; nu is de kaart best groot en onoverzichtelijk." Het
 * plan per uur, zoals de coach het uitrekende (`hours` in de stand), en
 * bovenaan de vier getallen die ertoe doen. Niets hiervan wordt hier
 * uitgerekend behalve optellen: de uren, de accustanden en de prijzen komen
 * uit `plan_batterij`.
 *
 * @returns {{kop: Array<{label: string, waarde: string, bij: string}>,
 *            uren: Array<{start: string, end: string, tijd: string, prijs: string,
 *                         soc: string, wat: string, net: boolean}>,
 *            voet: string} | null}
 */
export function batterijVooruit(besluit) {
  if (!besluit || besluit.kind !== "batterij") return null;
  const uren = (besluit.hours ?? []).filter((u) => u && u.start && u.end);

  const kop = [];
  if (Number.isFinite(besluit.soc)) {
    kop.push({
      label: t("Accu nu"),
      waarde: `${Math.round(besluit.soc)}%`,
      bij: Number.isFinite(besluit.capacity_kwh)
        ? t("van {kwh}", { kwh: kwhTekst(besluit.capacity_kwh) })
        : "",
    });
  }
  if (Number.isFinite(besluit.balance_kwh)) {
    const over = besluit.balance_kwh >= 0;
    kop.push({
      label: t("Morgenvroeg"),
      waarde: `${over ? "" : "−"}${kwhTekst(Math.abs(besluit.balance_kwh))}`,
      bij: over ? t("over na de nacht") : t("tekort voor de nacht"),
    });
  }
  const netUren = uren.filter((u) => Number(u.grid_kwh) > 0.05);
  const netKwh = netUren.reduce((som, u) => som + Number(u.grid_kwh), 0);
  const prijzen = netUren.filter((u) => Number.isFinite(u.price));
  kop.push({
    label: t("Van het net"),
    waarde: netKwh > 0.05 ? kwhTekst(netKwh) : t("niets"),
    bij: prijzen.length
      ? t("gemiddeld {prijs}", { prijs: euro(prijzen.reduce((s, u) => s + u.price, 0) / prijzen.length, 3) })
      : t("in de uren die er bekend zijn"),
  });
  // Onder welke prijs bijkopen nu loont (v0.102.3), in plaats van "Een kWh
  // erin, is straks waard". De eigenaar op 30-09-2026 bij € 0,301 en een nacht
  // van € 0,313: "is het niet goedkoper om iets bij te kopen?" Die € 0,301 was
  // per kWh ín de batterij; met het laadverlies eraf is het € 0,259, en dat
  // getal kun je naast de prijslijst leggen.
  if (Number.isFinite(besluit.buy_below)) {
    const nu = Number(uren[0]?.price);
    kop.push({
      label: t("Bijkopen loont"),
      waarde: t("onder {prijs}", { prijs: euro(besluit.buy_below, 3) }),
      bij: Number.isFinite(nu) ? t("nu {prijs}", { prijs: euro(nu, 3) }) : t("per kWh van het net"),
    });
  }
  // De uren waarin hij de auto helpt, opgeteld (v0.95.0). De bewoner van de
  // eerste woning: "wat gaat hij doen zou moeten zien dat hij om 23 uur mee
  // moet gaan helpen laden."
  const naarAuto = uren.reduce((t, u) => t + (Number(u.car_kwh) || 0), 0);
  if (naarAuto > 0.05) {
    kop.push({
      label: t("Naar de auto"),
      waarde: kwhTekst(naarAuto),
      bij: Number.isFinite(besluit.car_floor) ? t("tot hij op {n}% staat", { n: Math.round(besluit.car_floor) }) : t("als de paal laadt"),
    });
  }

  // Het plan kan over middernacht lopen; dan zegt het eerste uur van de
  // nieuwe dag erbij dat het morgen is, zoals "morgen 00:00".
  const vandaag = String(uren[0]?.start ?? "").slice(0, 10);
  let dagGezien = vandaag;
  // Kwartierprijzen: een regel per uur in de lijst, de grafiek toont de
  // kwartieren zelf (v0.88.1). Opgeteld en gemiddeld, verder niets.
  const perUurRijen = perUur(uren).map((groep) => {
    if (groep.length === 1) return groep[0];
    const standen = [...new Set(groep.map((u) => u.mode))];
    const prijzen = groep.map((u) => u.price).filter((p) => Number.isFinite(p));
    return {
      start: groep[0].start,
      end: groep[groep.length - 1].end,
      mode: standen.length === 1 ? standen[0] : standen,
      kwh: groep.reduce((t, u) => t + (Number(u.kwh) || 0), 0),
      grid_kwh: groep.reduce((t, u) => t + (Number(u.grid_kwh) || 0), 0),
      car_kwh: groep.reduce((t, u) => t + (Number(u.car_kwh) || 0), 0),
      soc: groep[groep.length - 1].soc,
      price: prijzen.length ? prijzen.reduce((t, p) => t + p, 0) / prijzen.length : undefined,
    };
  });
  const rijen = perUurRijen.map((u) => {
    const dag = String(u.start).slice(0, 10);
    const nieuweDag = dag !== dagGezien;
    dagGezien = dag;
    const kwh = Number(u.kwh) || 0;
    const net = Number(u.grid_kwh) || 0;
    const auto = Number(u.car_kwh) || 0;
    let wat = Array.isArray(u.mode)
      ? u.mode.map((m) => naamVan(m)).join(` ${t("en")} `)
      : naamVan(u.mode) ?? "";
    // Komt alles wat erin gaat van het net, dan is "waarvan" dubbel.
    if (net > 0.05 && Math.abs(net - kwh) < 0.05) wat += `, ${t("{kwh} van het net", { kwh: kwhTekst(net) })}`;
    else {
      if (kwh > 0.05) wat += `, ${t("{kwh} erin", { kwh: kwhTekst(kwh) })}`;
      else if (kwh < -0.05) wat += `, ${t("{kwh} eruit", { kwh: kwhTekst(-kwh) })}`;
      // Wat daarvan naar de auto gaat (v0.95.0): de uren waarin hij helpt.
      if (auto > 0.05) wat += `, ${t("waarvan {kwh} naar de auto", { kwh: kwhTekst(auto) })}`;
      if (net > 0.05) wat += `, ${t("waarvan {kwh} van het net", { kwh: kwhTekst(net) })}`;
    }
    wat = wat.charAt(0).toUpperCase() + wat.slice(1);
    return {
      start: u.start,
      end: u.end,
      tijd: nieuweDag ? t("morgen {klok}", { klok: klok(u.start) }) : klok(u.start),
      prijs: Number.isFinite(u.price) ? euro(u.price, 3) : "",
      soc: Number.isFinite(u.soc) ? `${Math.round(u.soc)}%` : "",
      wat,
      net: net > 0.05,
      // Aan het net leveren (handelen), voor de oranje regel (v0.130.0).
      levert: net < -0.05,
    };
  });

  return { kop, uren: rijen, voet: String(besluit.plan ?? "") };
}

/**
 * Wat de batterij opleverde sinds de coach haar volgt.
 *
 * Tot v0.107.0 was dit het kasboek zelf, en dat zakte elke dag terwijl ze
 * laadde: de eigenaar op 05-10-2026, "dat geld fluctueert telkens en klopt
 * niet." Nu telt ontladen pas, min wat die stroom kostte.
 *
 * Geen datum waarop hij terugverdiend is (v0.101.1): de eigenaar op 29-09-2026
 * kan geen datum in het paneel verdedigen die afwijkt van wat een installateur
 * de klant voorrekende. Wat er al terug is staat er sinds v0.148.0 wel weer,
 * zie `terugverdiendRegel`.
 *
 * Geen "Wat erin zit" meer (v0.118.1): "ingekocht voor € 2,02" las als stroom
 * die gekocht was, terwijl het bij een vast contract zon is die niet werd
 * teruggeleverd. De eigenaar op 14-10-2026 koos weghalen; Historie houdt
 * "Waarvan nog in je batterij" (`voorraadRegel_`).
 */
export function opgeleverdTekst(earned) {
  if (!earned?.days) return [];
  const dagen = Number(earned.days);
  // Laden is inkopen (v0.107.0): wat de stroom die erin zit kostte, telt pas
  // bij Opgeleverd als hij eruit gaat. Zie `Voorraad` in batterij.py.
  return [{ label: t("Opgeleverd"), text: tn(dagen, "{bedrag} in {n} dag", "{bedrag} in {n} dagen", { bedrag: nietOnderNul(earned.euro ?? 0) }) }];
}

/**
 * Hoeveel van de aanschafprijs er al terug is (v0.148.0), of niets.
 *
 * De eigenaar op 22-10-2026: "ja ik wil hem toch terug hebben", alleen voor de
 * thuisbatterij, als wat er al terugverdiend is en zonder datum: een datum is
 * een belofte, en die viel in v0.101.1 af. Het bedrag is Opgeleverd, dus alleen
 * wat de batterij opleverde sinds de coach haar volgt. De aanschafprijs is die
 * van de afschrijving (`wear_price`); de bewoner ziet de regel alleen met het
 * vinkje bij Installatie (`payback_resident`), dat beslist de kaart.
 *
 * @param {{euro?: number, days?: number}|undefined} earned het kasboek van de coach
 * @param {number|null|undefined} aanschaf de aanschafprijs in euro
 */
export function terugverdiendRegel(earned, aanschaf) {
  const prijs = Number(aanschaf);
  if (!earned?.days || aanschaf == null || !(prijs > 0)) return [];
  const terug = Number(earned.euro ?? 0);
  const deel = Math.max(0, Math.min(1, terug / prijs));
  return [{
    label: t("Terugverdiend"),
    // Een batterij die tot nu toe kostte staat op nul, met een lege balk (v0.148.1).
    text: t("{bedrag} van {prijs}", { bedrag: nietOnderNul(terug), prijs: euro(prijs, 0) }),
    deel,
  }];
}

/**
 * De regels op de kaart van een batterij.
 *
 * @param {object} besluit de stand van de coach voor deze batterij
 * @param {{aanschaf?: number|null}} [opties] de aanschafprijs, alleen als deze
 *   kijker Terugverdiend mag zien
 */
export function batteryRows(besluit, { aanschaf = null } = {}) {
  if (!besluit || besluit.kind !== "batterij") return [];
  const rijen = [{ label: t("Stand"), text: besluit.mode_name ?? besluit.mode ?? "—" }];

  // Sinds v0.97.0 kan de batterij het zelf doen, met een eigen meter; dan is er
  // geen opdracht van de coach en zegt de kaart wie het doet.
  if (besluit.applied && besluit.self_zero) {
    rijen.push({ label: t("Wie regelt"), text: t("de batterij zelf, met zijn eigen meter; de coach kijkt mee") });
  }

  if (besluit.applied && Number.isFinite(besluit.setpoint_w)) {
    const w = Math.round(besluit.setpoint_w);
    rijen.push({
      label: t("Opdracht van de coach"),
      text: w === 0 ? "0 W" : w > 0
        ? t("laden op {w} W", { w: Math.abs(w).toLocaleString(locale()) })
        : t("ontladen op {w} W", { w: Math.abs(w).toLocaleString(locale()) }),
    });
  }

  // Wat een kWh straks waard is en het plan per uur staan sinds v0.85.0 in de
  // pop-up "Wat gaat hij doen" (`batterijVooruit`); de kaart werd er te lang
  // van. De eerstvolgende netlading blijft, want dat is nieuws.
  const net = volgendeNetlading(besluit.hours);
  if (net) {
    rijen.push({
      label: t("Laadt van het net"),
      text: t("{van} tot {tot}, ongeveer {kwh} kWh", {
        van: klok(net.start), tot: klok(net.end), kwh: net.kwh.toLocaleString(locale(), { maximumFractionDigits: 1 }),
      }),
    });
  }

  if (besluit.full_before) {
    rijen.push({ label: t("Volle beurt"), text: t("vandaag een keer helemaal vol, voor het balanceren van de cellen") });
  }

  if (besluit.holiday) {
    rijen.push({
      label: t("Vakantiestand"),
      text: t("hij houdt de batterij onder {grens}%, en de wekelijkse volle beurt slaat hij over", {
        grens: Number.isFinite(besluit.ceiling) ? Math.round(besluit.ceiling) : t("de grens"),
      }),
    });
  }

  return [...rijen, ...opgeleverdTekst(besluit.earned), ...terugverdiendRegel(besluit.earned, aanschaf)];
}
