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

  return [...rijen, ...terugverdiendTekst(besluit.payback)];
}
