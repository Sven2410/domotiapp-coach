/**
 * Wat de kaart van een thuisbatterij laat zien, uit het besluit van de coach.
 *
 * Los van de kaart zelf, zodat het na te meten is zonder scherm (zie
 * test_rapport.mjs). Alles wat hier staat heeft de coach gemeten of uitgerekend;
 * wat hij niet weet krijgt geen regel, of een regel die zegt dat hij het niet
 * weet.
 */

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

  if (besluit.applied && Number.isFinite(besluit.setpoint_w)) {
    const w = Math.round(besluit.setpoint_w);
    rijen.push({
      label: "Opdracht van de coach",
      text: w === 0 ? "0 W" : `${w > 0 ? "laden" : "ontladen"} op ${Math.abs(w).toLocaleString("nl-NL")} W`,
    });
  }

  if (Number.isFinite(besluit.value) && besluit.value !== null) {
    rijen.push({ label: "Een kWh erin is straks waard", text: euro(besluit.value, 3) });
  }

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

  const plan = planRegels(besluit.hours);
  if (plan.length) {
    rijen.push({ label: "Plan", text: "wat hij de komende uren van plan is:" });
    rijen.push(...plan);
  }

  return [...rijen, ...terugverdiendTekst(besluit.payback)];
}
