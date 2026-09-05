/**
 * Bespaard: wat de laadbeurten kostten en wat ze bespaarden, opgeteld.
 *
 * Sven op 05-09-2026: "Kunnen we ergens een overzichtje maken wat we hebben
 * bespaard? En dat per dag, week, maand, jaar van elk apparaat. Dat is
 * natuurlijk het belangrijkste voor de klant." Het ijkpunt is de prijs op het
 * moment van inpluggen: "bereken die prijs wanneer die gestopt is en gewacht
 * heeft met laden op een goedkoop moment. Dus de prijs vanaf het inpluggen."
 *
 * De beurten komen van `domotiapp_coach/savings/list`; de coach rekent ze per
 * ronde bij (zie `_geld_bij` in coach.py). Hier wordt alleen opgeteld. Een
 * beurt zonder bekende prijs telt mee in de kilowatturen en niet in het geld,
 * en dat staat erbij: liever een gat dan een verzonnen getal.
 */

/** Het moment waarop een beurt in het overzicht valt: het eind, of nu als hij nog loopt. */
export function moment(beurt) {
  const t = new Date(beurt?.ended ?? beurt?.plugged_at ?? "");
  return Number.isNaN(t.getTime()) ? null : t;
}

/** De beurten die in [start, end) vallen, de nieuwste eerst. */
export function beurtenIn(items, start, end) {
  return (items ?? [])
    .filter((b) => {
      const t = moment(b);
      return t !== null && t >= start && t < end;
    })
    .sort((a, b) => moment(b) - moment(a));
}

/** Alles opgeteld. `onbekend` is hoeveel beurten geen prijs hadden. */
export function totalen(items) {
  const uit = { beurten: 0, kwh: 0, solar_kwh: 0, paid: 0, ref_cost: 0, saved: 0, onbekend: 0, lopend: 0 };
  for (const b of items ?? []) {
    uit.beurten += 1;
    uit.kwh += Number(b.kwh) || 0;
    uit.solar_kwh += Number(b.solar_kwh) || 0;
    if (!b.complete) uit.lopend += 1;
    if (b.price_unknown) uit.onbekend += 1;
    if (b.saved === null || b.saved === undefined) continue;
    uit.paid += Number(b.paid) || 0;
    uit.ref_cost += Number(b.ref_cost) || 0;
    uit.saved += Number(b.saved) || 0;
  }
  return uit;
}

/** Per apparaat, op naam, het meest bespaard bovenaan. */
export function perApparaat(items) {
  const groepen = new Map();
  for (const b of items ?? []) {
    const sleutel = b.device ?? "";
    if (!groepen.has(sleutel)) groepen.set(sleutel, { device: sleutel, name: b.name ?? "Apparaat", items: [] });
    groepen.get(sleutel).items.push(b);
  }
  return [...groepen.values()]
    .map((g) => ({ device: g.device, name: g.name, ...totalen(g.items) }))
    .sort((a, b) => b.saved - a.saved);
}

/** Wat er over een beurt te zeggen is naast de getallen. */
export function opmerking(beurt) {
  if (!beurt) return "";
  if (!beurt.complete) return "loopt nog";
  if (beurt.price_unknown) {
    const zonder = Number(beurt.unknown_kwh) || 0;
    if (beurt.saved !== null && beurt.saved !== undefined && zonder > 0) {
      return `${zonder.toFixed(1).replace(".", ",")} kWh zonder prijs`;
    }
    return "prijs onbekend";
  }
  if (beurt.resumed) return "na een herstart";
  return "";
}
