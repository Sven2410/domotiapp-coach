/**
 * Wat de kaart van een thuisbatterij laat zien, uit het besluit van de coach.
 *
 * Los van de kaart zelf, zodat het na te meten is zonder scherm (zie
 * test_rapport.mjs). Alles wat hier staat heeft de coach gemeten of uitgerekend;
 * wat hij niet weet krijgt geen regel, of een regel die zegt dat hij het niet
 * weet.
 */

import { perUur } from "./prijsgrafiek.js";

const euro = (bedrag, cijfers = 2) =>
  `€ ${Number(bedrag).toLocaleString("nl-NL", { minimumFractionDigits: cijfers, maximumFractionDigits: cijfers })}`;

const klok = (iso) => String(iso ?? "").slice(11, 16);

const datum = (iso) => {
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString("nl-NL", { month: "long", year: "numeric" });
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

const STAND_NAMEN = {
  nul: "nul op de meter",
  zonneladen: "alleen zonneladen",
  ontladen: "alleen ontladen",
  netladen: "laden van het net",
  "max-laden": "maximaal laden",
  handelen: "handelen",
  standby: "standby",
};

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
    const vandaag = new Date().toISOString().slice(0, 10);
    const dag = String(iso ?? "").slice(0, 10);
    return `${dag && dag !== vandaag && dag > vandaag ? "morgen " : ""}${klok(iso)}`;
  };
  return blokken.slice(0, maxRegels).map((b) => {
    let text = STAND_NAMEN[b.mode] ?? b.mode;
    if (Number.isFinite(b.socEind)) {
      text += Number.isFinite(b.socBegin) && Math.round(b.socBegin) !== Math.round(b.socEind)
        ? `, van ${Math.round(b.socBegin)} naar ${Math.round(b.socEind)}%`
        : `, ${Math.round(b.socEind)}%`;
    }
    if (b.kwh > 0.05) {
      text += `, ${b.kwh.toLocaleString("nl-NL", { maximumFractionDigits: 1 })} kWh`;
      if (b.prijsN) text += ` tegen ${euro(b.prijsSom / b.prijsN, 3)}`;
    }
    return { label: `${dagKlok(b.start)} tot ${dagKlok(b.end)}`, text };
  });
}

const kwhTekst = (kwh) =>
  `${Number(kwh).toLocaleString("nl-NL", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} kWh`;

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
      label: "Accu nu",
      waarde: `${Math.round(besluit.soc)}%`,
      bij: Number.isFinite(besluit.capacity_kwh)
        ? `van ${kwhTekst(besluit.capacity_kwh)}`
        : "",
    });
  }
  if (Number.isFinite(besluit.balance_kwh)) {
    const over = besluit.balance_kwh >= 0;
    kop.push({
      label: "Morgenvroeg",
      waarde: `${over ? "" : "−"}${kwhTekst(Math.abs(besluit.balance_kwh))}`,
      bij: over ? "over na de nacht" : "tekort voor de nacht",
    });
  }
  const netUren = uren.filter((u) => Number(u.grid_kwh) > 0.05);
  const netKwh = netUren.reduce((som, u) => som + Number(u.grid_kwh), 0);
  const prijzen = netUren.filter((u) => Number.isFinite(u.price));
  kop.push({
    label: "Van het net",
    waarde: netKwh > 0.05 ? kwhTekst(netKwh) : "niets",
    bij: prijzen.length
      ? `gemiddeld ${euro(prijzen.reduce((s, u) => s + u.price, 0) / prijzen.length, 3)}`
      : "in de uren die er bekend zijn",
  });
  if (Number.isFinite(besluit.value)) {
    kop.push({ label: "Een kWh erin", waarde: euro(besluit.value, 3), bij: "is straks waard" });
  }
  // De uren waarin hij de auto helpt, opgeteld (v0.95.0). De bewoner van de
  // eerste woning: "wat gaat hij doen zou moeten zien dat hij om 23 uur mee
  // moet gaan helpen laden."
  const naarAuto = uren.reduce((t, u) => t + (Number(u.car_kwh) || 0), 0);
  if (naarAuto > 0.05) {
    kop.push({
      label: "Naar de auto",
      waarde: kwhTekst(naarAuto),
      bij: Number.isFinite(besluit.car_floor) ? `tot hij op ${Math.round(besluit.car_floor)}% staat` : "als de paal laadt",
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
      ? u.mode.map((m) => STAND_NAMEN[m] ?? m).join(" en ")
      : STAND_NAMEN[u.mode] ?? u.mode ?? "";
    // Komt alles wat erin gaat van het net, dan is "waarvan" dubbel.
    if (net > 0.05 && Math.abs(net - kwh) < 0.05) wat += `, ${kwhTekst(net)} van het net`;
    else {
      if (kwh > 0.05) wat += `, ${kwhTekst(kwh)} erin`;
      else if (kwh < -0.05) wat += `, ${kwhTekst(-kwh)} eruit`;
      // Wat daarvan naar de auto gaat (v0.95.0): de uren waarin hij helpt.
      if (auto > 0.05) wat += `, waarvan ${kwhTekst(auto)} naar de auto`;
      if (net > 0.05) wat += `, waarvan ${kwhTekst(net)} van het net`;
    }
    wat = wat.charAt(0).toUpperCase() + wat.slice(1);
    return {
      start: u.start,
      end: u.end,
      tijd: nieuweDag ? `morgen ${klok(u.start)}` : klok(u.start),
      prijs: Number.isFinite(u.price) ? euro(u.price, 3) : "",
      soc: Number.isFinite(u.soc) ? `${Math.round(u.soc)}%` : "",
      wat,
      net: net > 0.05,
    };
  });

  return { kop, uren: rijen, voet: String(besluit.plan ?? "") };
}

/** Wat er over de terugverdientijd te zeggen valt, of niets. */
export function terugverdiendTekst(payback) {
  if (!payback) return [];
  const rijen = [];
  const verdiend = Number(payback.earned ?? 0);
  const prijs = Number(payback.price ?? 0);
  if (prijs > 0) {
    rijen.push({ label: "Terugverdiend", text: `${euro(verdiend)} van ${euro(prijs, 0)}` });
    if (payback.date === "klaar") {
      rijen.push({ label: "Terugverdiend rond", text: "hij heeft zichzelf terugbetaald" });
    } else if (payback.date) {
      rijen.push({
        label: "Terugverdiend rond",
        text: `${datum(payback.date)}, in het tempo van de laatste ${payback.days} gemeten dagen`,
      });
    } else {
      rijen.push({
        label: "Terugverdiend rond",
        text: `nog te vroeg voor een datum: ${payback.days ?? 0} van de ${payback.min_days ?? 28} dagen gemeten`,
      });
    }
  } else if (payback.days) {
    rijen.push({ label: "Opgeleverd", text: `${euro(verdiend)} in ${payback.days} dagen` });
  }
  return rijen;
}

/** De regels op de kaart van een batterij. */
export function batteryRows(besluit) {
  if (!besluit || besluit.kind !== "batterij") return [];
  const rijen = [{ label: "Stand", text: besluit.mode_name ?? besluit.mode ?? "—" }];

  // Sinds v0.97.0 kan de batterij het zelf doen, met een eigen meter; dan is er
  // geen opdracht van de coach en zegt de kaart wie het doet.
  if (besluit.applied && besluit.self_zero) {
    rijen.push({ label: "Wie regelt", text: "de batterij zelf, met zijn eigen meter; de coach kijkt mee" });
  }

  if (besluit.applied && Number.isFinite(besluit.setpoint_w)) {
    const w = Math.round(besluit.setpoint_w);
    rijen.push({
      label: "Opdracht van de coach",
      text: w === 0 ? "0 W" : `${w > 0 ? "laden" : "ontladen"} op ${Math.abs(w).toLocaleString("nl-NL")} W`,
    });
  }

  // Wat een kWh straks waard is en het plan per uur staan sinds v0.85.0 in de
  // pop-up "Wat gaat hij doen" (`batterijVooruit`); de kaart werd er te lang
  // van. De eerstvolgende netlading blijft, want dat is nieuws.
  const net = volgendeNetlading(besluit.hours);
  if (net) {
    rijen.push({
      label: "Laadt van het net",
      text: `${klok(net.start)} tot ${klok(net.end)}, ongeveer ${net.kwh.toLocaleString("nl-NL", { maximumFractionDigits: 1 })} kWh`,
    });
  }

  if (besluit.full_before) {
    rijen.push({ label: "Volle beurt", text: "vandaag een keer helemaal vol, voor het balanceren van de cellen" });
  }

  if (besluit.holiday) {
    rijen.push({
      label: "Vakantiestand",
      text: `hij houdt de batterij onder ${Number.isFinite(besluit.ceiling) ? Math.round(besluit.ceiling) : "de grens"}%, en de wekelijkse volle beurt slaat hij over`,
    });
  }

  return [...rijen, ...terugverdiendTekst(besluit.payback)];
}
