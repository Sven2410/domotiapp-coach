/**
 * Historie als bestand voor Excel (v0.180.0).
 *
 * Een bewoner in een klantwoning wilde op 29-10-2026 de kwartieren in Excel, om scenario's voor
 * een thuisbatterij door te rekenen. Per regel een tijdvak: de datum en de tijd op de klok van het
 * huis, en het moment in UTC, want bij het ingaan van de wintertijd komt het uur van 02:00 twee
 * keer. Per bron het laagste, het gemiddelde en de piek.
 *
 * In het Nederlands zoals Excel het daar leest: een puntkomma tussen de velden en een decimale
 * komma. In het Engels een komma en een punt. Altijd met een BOM, anders leest Excel een naam met
 * een trema als twee rare tekens.
 */

import { taal } from "./i18n.js";

/** Het scheidingsteken en de decimale komma van deze taal. */
export function csvOpmaak(welke = taal()) {
  return welke === "en" ? { scheiding: ",", komma: "." } : { scheiding: ";", komma: "," };
}

/** Een getal met vaste decimalen, zonder duizendtallen en zonder "-0". */
export function csvGetal(waarde, decimalen, opmaak) {
  if (!Number.isFinite(waarde)) return "";
  const tekst = waarde.toFixed(decimalen);
  const schoon = Number(tekst) === 0 ? (0).toFixed(decimalen) : tekst;
  return schoon.replace(".", opmaak.komma);
}

/** Een veld tussen aanhalingstekens als het een scheidingsteken, aanhalingsteken of regeleinde bevat. */
export function csvVeld(waarde, opmaak) {
  const tekst = String(waarde ?? "");
  return tekst.includes(opmaak.scheiding) || /["\r\n]/.test(tekst) ? `"${tekst.replace(/"/g, '""')}"` : tekst;
}

/** De kop en de regels als tekst, met een BOM ervoor en een regeleinde zoals Windows dat kent. */
export function csvTekst(kop, rijen, opmaak) {
  return `﻿${[kop, ...rijen].map((rij) => rij.map((v) => csvVeld(v, opmaak)).join(opmaak.scheiding)).join("\r\n")}\r\n`;
}

const twee = (n) => String(n).padStart(2, "0");

/** De datum op de klok van het huis, als 2026-10-27: zo leest Excel hem in elke taal. */
export const csvDatum = (d) => `${d.getFullYear()}-${twee(d.getMonth() + 1)}-${twee(d.getDate())}`;
export const csvKlok = (d) => `${twee(d.getHours())}:${twee(d.getMinutes())}`;
/** Het echte moment in UTC, zonder milliseconden. */
export const csvUtc = (d) => (d ? d.toISOString().replace(/\.\d{3}Z$/, "Z") : "");

/**
 * De tabel: per tijdvak een regel, per reeks drie kolommen.
 *
 * `reeksen`: `{naam, eenheid, decimalen, vakken}`, met per vak `start` (de klok van het huis),
 * `utc` (het echte moment) en `laagste`, `gemiddeld`, `piek`. Een vak dat een reeks niet heeft
 * blijft daar leeg. `woorden` zijn de koppen in de taal van het paneel.
 *
 * @returns {{kop: string[], rijen: string[][]}}
 */
export function csvTabel(reeksen, opmaak, woorden) {
  const plek = (vak) => (vak.utc ?? vak.start).getTime();
  const regels = new Map();
  reeksen.forEach((reeks, i) => {
    for (const vak of reeks.vakken) {
      const sleutel = plek(vak);
      const regel = regels.get(sleutel) ?? { vak, waarden: new Array(reeksen.length).fill(null) };
      regel.waarden[i] = vak;
      regels.set(sleutel, regel);
    }
  });
  const kop = [woorden.datum, woorden.tijd, "UTC"];
  for (const reeks of reeksen) {
    for (const soort of [woorden.laagste, woorden.gemiddeld, woorden.piek]) kop.push(`${reeks.naam} ${soort} (${reeks.eenheid})`);
  }
  const rijen = [...regels.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([, { vak, waarden }]) => [
      csvDatum(vak.start),
      csvKlok(vak.start),
      csvUtc(vak.utc),
      ...waarden.flatMap((w, i) =>
        w ? [w.laagste, w.gemiddeld, w.piek].map((x) => csvGetal(x, reeksen[i].decimalen, opmaak)) : ["", "", ""]
      ),
    ]);
  return { kop, rijen };
}
