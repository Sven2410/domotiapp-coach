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

/**
 * Wat een beurt bespaarde, in twee delen: door de zon (wat eigen zon scheelde
 * tegenover inkopen) en door te wachten (de rest: een goedkoper uur). Een
 * beurt van voor v0.60.0 kent het zondeel niet; toen zat de zon al in de maat
 * en was bespaard alleen het wachten, dus dan is dat ook het hele bedrag.
 * Sven op 09-09-2026: "ik wil het totaal plaatje."
 */
export function delen(beurt) {
  if (beurt?.saved === null || beurt?.saved === undefined) return { zon: null, wachten: null };
  const totaal = Number(beurt.saved) || 0;
  const zon = beurt.solar_saved === null || beurt.solar_saved === undefined ? null : Number(beurt.solar_saved) || 0;
  return { zon, wachten: totaal - (zon ?? 0) };
}

/** Alles opgeteld. `onbekend` is hoeveel beurten geen prijs hadden. */
export function totalen(items) {
  const uit = {
    beurten: 0, kwh: 0, solar_kwh: 0, paid: 0, ref_cost: 0, saved: 0, solar_saved: 0, wait_saved: 0,
    onbekend: 0, lopend: 0,
  };
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
    const d = delen(b);
    uit.solar_saved += d.zon ?? 0;
    uit.wait_saved += d.wachten;
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

/**
 * Wat voor beurt het is: "laden" (een auto aan een paal) of "programma" (een
 * vaatwasser die één keer start en afdraait). Een beurt van voor v0.57.2 zegt
 * het niet zelf; dat was toen altijd een laadbeurt.
 */
export const soort = (beurt) => (beurt?.kind === "programma" ? "programma" : "laden");

/**
 * De woorden voor de kop van Bespaard, naar wat er in de lijst staat. Sven op
 * 07-09-2026, bij de eerste vaatwasserbeurt onder Bespaard: "hij heeft het
 * hier over de paal, maar dat moet vaatwasser zijn. Ook kan je niet een
 * vaatwasser inpluggen." Een vaatwasser wordt vrijgegeven en verbruikt; een
 * auto wordt ingeplugd en geladen. Staan ze door elkaar, dan woorden die
 * voor allebei kloppen.
 *
 * `vanaf` is de kolom met het ijkpunt: wat dezelfde beurt gekost had zonder
 * de coach en zonder zon, vanaf het inpluggen op vol vermogen of meteen bij
 * het vrijgeven gestart, alles van het net tegen de prijs van dat moment.
 * Sven op 09-09-2026: "wat het heeft gekost nu tegenover een duurder moment
 * van het vrijgeven, en wat je op zonne-energie laadt bespaar je natuurlijk
 * ook door minder stroom in te kopen."
 */
export function woorden(items) {
  const soorten = new Set((items ?? []).map(soort));
  const alleen = (s) => soorten.size === 1 && soorten.has(s);
  if (alleen("programma")) {
    return {
      wanneer: "Vrijgegeven",
      hoeveel: "Verbruikt",
      vanaf: "Meteen starten",
      uitleg:
        "Bespaard is wat dezelfde beurt gekost had als het apparaat meteen bij het vrijgeven was gestart " +
        "met alles van het net, tegen de prijs van dat moment, min wat hij werkelijk kostte. " +
        "Door de zon is wat eigen zon scheelde tegenover inkopen; door te wachten is wat het latere moment scheelde.",
    };
  }
  if (alleen("laden") || !soorten.size) {
    return {
      wanneer: "Ingeplugd",
      hoeveel: "Geladen",
      vanaf: "Vanaf inpluggen",
      uitleg:
        "Bespaard is wat dezelfde kilowatturen gekost hadden als de paal vanaf het inpluggen gewoon op vol " +
        "vermogen was doorgegaan met alles van het net, uur na uur tegen de prijs van dat uur, min wat ze " +
        "werkelijk kostten. Door de zon is wat eigen zon scheelde tegenover inkopen; door te wachten is wat " +
        "de goedkopere uren scheelden.",
    };
  }
  return {
    wanneer: "Vanaf",
    hoeveel: "Verbruikt",
    vanaf: "Zonder coach",
    uitleg:
      "Bespaard is wat dezelfde beurt zonder de coach en met alles van het net gekost had, min wat hij werkelijk " +
      "kostte: voor een auto vanaf het inpluggen op vol vermogen, uur na uur tegen de prijs van dat uur; voor een " +
      "vaatwasser meteen bij het vrijgeven gestart. Door de zon is wat eigen zon scheelde tegenover inkopen; " +
      "door te wachten is wat het latere moment scheelde.",
  };
}

/** Wat er over een beurt te zeggen is naast de getallen. */
export function opmerking(beurt) {
  if (!beurt) return "";
  const delen = [];
  if (!beurt.complete) delen.push("loopt nog");
  if (beurt.resumed && (beurt.ref_price === null || beurt.ref_price === undefined)) {
    // De coach stapte midden in de beurt in en kent het begin niet, dus ook
    // de prijs van toen niet: geen ijkpunt, geen verzonnen bedrag.
    delen.push(
      soort(beurt) === "programma"
        ? "na een herstart, prijs bij vrijgeven onbekend"
        : "na een herstart, prijs bij inpluggen onbekend"
    );
  } else if (beurt.price_unknown) {
    const zonder = Number(beurt.unknown_kwh) || 0;
    delen.push(
      beurt.saved !== null && beurt.saved !== undefined && zonder > 0
        ? `${zonder.toFixed(1).replace(".", ",")} kWh zonder prijs`
        : "prijs onbekend"
    );
  } else if (beurt.resumed) {
    delen.push("na een herstart");
  }
  return delen.join(", ");
}
