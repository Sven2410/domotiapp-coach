/**
 * De voorrang bij zonoverschot, zoals het paneel hem toont (v0.92.0).
 *
 * Dezelfde regels als `zon_regels` in planner.py: wat er is opgeslagen, zonder
 * apparaten die er niet meer zijn of die de coach niet stuurt, aangevuld met
 * elk apparaat dat nog geen regel heeft, zonder grens, in de volgorde auto,
 * boiler, batterij. Een lege lijst is dus de standaard. test_rapport.mjs legt
 * de twee naast elkaar.
 */

/** Welke soorten zon kunnen opnemen, in de volgorde van de standaard. */
export const ZON_SOORTEN = ["laadpaal", "boiler", "thuisbatterij"];

/** De voorrang zoals hij geldt. */
export function zonRegels(opgeslagen, apparaten) {
  const mag = new Map(
    (apparaten ?? [])
      .filter((a) => a?.id && a.controllable && ZON_SOORTEN.includes(a.type))
      .map((a) => [a.id, a.type])
  );
  const uit = [];
  for (const rij of opgeslagen ?? []) {
    if (!rij || !mag.has(rij.device)) continue;
    let grens = mag.get(rij.device) === "boiler" ? null : rij.limit;
    grens = grens === null || grens === undefined || grens === "" || !Number.isFinite(Number(grens))
      ? null
      : Math.max(0, Math.min(100, Number(grens)));
    uit.push({ device: rij.device, limit: grens });
  }
  const gezien = new Set(uit.map((rij) => rij.device));
  for (const soort of ZON_SOORTEN) {
    for (const [id, type] of mag) {
      if (type === soort && !gezien.has(id)) uit.push({ device: id, limit: null });
    }
  }
  return uit;
}

/** Wat een regel zegt, in gewone woorden, voor onder de naam. */
export function regelUitleg(type, grens) {
  if (type === "boiler") return "tot hij warm is";
  if (grens === null || grens === undefined) {
    return type === "laadpaal" ? "tot het doel van de auto" : "tot vol";
  }
  return type === "laadpaal" ? `tot de auto op ${grens}% staat` : `tot ${grens}%`;
}
