/**
 * De belasting per fase in Historie (v0.180.0), uit de kwartieropslag.
 *
 * Een bewoner in een klantwoning wilde op 29-10-2026 weten of zijn aansluiting van 3x50 A naar
 * 3x25 A kan. Dat hangt af van L1, L2 en L3 elk apart, en een zekering beslist op minuten, niet
 * op een uur. De coach kende de fasen al voor de lastbewaker (`sources.phases`); sinds v0.180.0
 * bewaart `archive.py` ze per kwartier: de stroom als die er is, anders het vermogen en de
 * spanning. De ampères komen er hier uit met `phaseAmps` uit data-source.js, dezelfde som als
 * `_phase_amps` in monitor.py.
 *
 * De piek van een fase in de opslag is sinds v0.182.0 de hoogste stroom die tien seconden aanhield
 * (`FASE_VAST` in archive.py), niet één melding van de meter.
 *
 * Kent Home Assistant niet en tekent niets; views/history.js zet het op het scherm.
 */

import { phaseAmps } from "./data-source.js";

export const FASEN = ["l1", "l2", "l3"];

/** Zekeringen om te proberen, naast die van de installatie. */
export const ZEKERINGEN = [16, 20, 25, 32, 35, 40, 50, 63, 80];

/**
 * De fasen met hun sensoren, zoals `_wat_volgen` in archive.py ze volgt. Leeg zonder het vinkje
 * Fasen, of zonder een fase met een stroom of een vermogen. Bij een eenfasige installatie één.
 *
 * @returns {Array<{key: string, label: string, current?: string, power?: string, voltage?: string}>}
 */
export function faseBronnen(sources) {
  if (!sources?.phases_enabled) return [];
  const config = sources.phases ?? {};
  return FASEN.map((key) => {
    const fase = config[key] ?? {};
    if (fase.current) return { key, label: key.toUpperCase(), current: fase.current };
    if (fase.power) return { key, label: key.toUpperCase(), power: fase.power, voltage: fase.voltage || "" };
    return null;
  }).filter(Boolean);
}

/** Alle sensoren van de fasen, om in één keer op te halen. */
export const faseEntiteiten = (bronnen) =>
  bronnen.flatMap((bron) => [bron.current, bron.power, bron.voltage]).filter(Boolean);

const moment = (rij) => (rij.utc ?? rij.start).getTime();

/**
 * Per kwartier de ampères van één fase: de stroom zoals hij is, of het vermogen gedeeld door de
 * spanning van dat kwartier (en 230 V zonder spanning). Dezelfde vorm als een rij uit `quarters`.
 */
export function faseKwartieren(bron, gevonden) {
  const geldig = (rij) => Number.isFinite(rij.gemiddeld) && rij.seconden > 0;
  if (bron.current) return (gevonden.get(bron.current) ?? []).filter(geldig);
  const spanning = new Map((gevonden.get(bron.voltage) ?? []).filter(geldig).map((rij) => [moment(rij), rij.gemiddeld]));
  return (gevonden.get(bron.power) ?? []).filter(geldig).map((rij) => {
    const amps = (watt) => phaseAmps({ power: watt, voltage: spanning.get(moment(rij)) });
    return { ...rij, laagste: amps(rij.laagste), piek: amps(rij.piek), gemiddeld: amps(rij.gemiddeld) };
  });
}

/**
 * Hoe vaak een fase boven een zekering kwam, per kwartier: gemiddeld erboven (zo lang belast),
 * of alleen een piek erboven (zo hoog ging het even). Teruglevering belast de zekering ook, dus
 * telt de grootte, niet de richting. Met de hoogste piek en wanneer.
 *
 * @returns {{kwartieren: number, gemiddeld: number, piek: number, hoogste: {amps: number, op: Date}|null}}
 */
export function overZekering(rijen, zekering) {
  const uit = { kwartieren: 0, gemiddeld: 0, piek: 0, hoogste: null };
  for (const rij of rijen ?? []) {
    if (!Number.isFinite(rij.gemiddeld) || !(rij.seconden > 0)) continue;
    uit.kwartieren += 1;
    const top = Math.max(Math.abs(rij.piek), Math.abs(rij.laagste));
    if (Math.abs(rij.gemiddeld) > zekering) uit.gemiddeld += 1;
    if (top > zekering) uit.piek += 1;
    if (!uit.hoogste || top > uit.hoogste.amps) uit.hoogste = { amps: top, op: rij.start };
  }
  return uit;
}

/** De keuzes in het keuzeveld: de vaste rij plus die van de installatie, van klein naar groot. */
export function zekeringKeuzes(eigen) {
  const n = Number(eigen);
  return [...new Set([...ZEKERINGEN, ...(n > 0 ? [n] : [])])].sort((a, b) => a - b);
}
