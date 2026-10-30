/**
 * Wat van toepassing is (v0.186.0): of een instelling bij deze installatie iets doet.
 *
 * De eigenaar op 30-10-2026, bij "Thuisbatterij te warm" in Meldingen bij een batterij zonder
 * temperatuursensor: "Zijn er apparaten ingesteld waar het niet van toepassing is moet de
 * instelling weg natuurlijk. Zo houd je de coach heel overzichtelijk voor iedereen." Een blok,
 * schuif of veld staat dus alleen in beeld als de coach er bij deze installatie iets mee doet.
 * Elk scherm vraagt het hier, zodat ze hetzelfde zien, en elke vraag volgt wat de coach zelf
 * doet (de functie in coach.py of monitor.py staat erbij). Wat verborgen raakt blijft in de
 * opslag; zie docs/paneel.md, Alleen wat van toepassing is.
 */

import { solarEntities } from "./data-source.js";
import { PROGRAM_TYPES, isSchema } from "./devices.js";
import { SALDEREN_TOT } from "./geld.js";

const apparaten = (settings) => (settings?.devices ?? []).filter(Boolean);

/** Of er zonnepanelen zijn: een omvormer onder Energiebronnen (`zonsensoren` in coach.py). */
export const heeftZon = (settings) => solarEntities(settings?.sources).length > 0;

/** Of de coach minstens één apparaat mag sturen; anders doet hoe ver hij mag gaan niets. */
export const ietsStuurbaar = (settings) => apparaten(settings).some((d) => d.controllable);

/** Of er een thuisbatterij is die de coach stuurt: de nachtstrategie gaat over haar (`b.nacht`). */
export const stuurbareBatterij = (settings) =>
  apparaten(settings).some((d) => d.type === "thuisbatterij" && d.controllable);

/**
 * Of teruglevering iets opbrengt. In Portugal niet met `excedente` op nenhum, of een vaste
 * prijs van nul (`terug` in tarifas.js geeft dan 0); dan levert ontladen naar het net nooit
 * iets op. In Nederland ziet `vlakkePrijs` en `terugleverBekend` (geld.js) de rest.
 */
export function terugleveringBrengtOp(contract) {
  if (contract?.country !== "PT") return true;
  const e = contract.pt?.excedente ?? {};
  if (e.modo === "nenhum") return false;
  return !(e.modo === "fixo" && !(Number(e.preco) > 0));
}

/**
 * Of de batterij naar het net mag ontladen (`trade`). Niet bij een batterij met een laadschema:
 * daar kan dat niet op een prijs (`b.handelen = False` in `_growatt_batterij`). En niet als
 * teruglevering niets oplevert.
 */
export const handelenKan = (device, contract) => !isSchema(device) && terugleveringBrengtOp(contract);

/**
 * Noodstroom, balanceren, de vakantiestand en De auto (v0.186.0). Niet bij een batterij met een
 * laadschema: de eigenaar op 30-10-2026, "growatt moet geen noodstroom hebben. geen balanceren
 * geen vakantiestand accu helpen ook niet. Dus de accu mag gewoon standaard de auto helpen".
 * De coach negeert ze daar ook (`_batterij_van`), en de accu helpt de auto tot zijn ondergrens.
 */
export const accuKeuzes = (device) => !isSchema(device);

/** Of de temperatuur van een thuisbatterij gemeten wordt (`_temp_nodig` in coach.py). */
export const batterijMetTemperatuur = (settings) =>
  apparaten(settings).some((d) => d.type === "thuisbatterij" && d.entities?.temperature);

/** De gas- en watermeter die de coach volgt (`_async_verbruikswacht` in coach.py). */
export function meters(settings) {
  const m = settings?.sources?.meters ?? {};
  const gas = Boolean(m.gas_enabled && m.gas);
  const water = Boolean(m.water_enabled && m.water);
  return { gas, water, waterLoopt: Boolean(m.water_enabled && m.water_flow) };
}

/**
 * Of de coach de belasting van de aansluiting kan meten (`async_current_load` in monitor.py):
 * de fasen tegen de hoofdzekering, een groep met een zekering, of het vermogen tegen een
 * ingevuld plafond.
 */
export function belastingTeMeten(settings) {
  const inst = settings?.installation ?? {};
  const bronnen = settings?.sources ?? {};
  if (bronnen.phases_enabled && Number(inst.fuse_amps) > 0) return true;
  if ((inst.circuits ?? []).some((g) => Number(g?.fuse_amps) > 0)) return true;
  return Number(inst.max_grid_watts) > 0;
}

/** Of er beurten zijn om opnieuw uit te rekenen: een laadpaal of een apparaat met een programma. */
export const heeftBeurten = (settings) =>
  apparaten(settings).some((d) => d.type === "laadpaal" || PROGRAM_TYPES.includes(d.type));

/**
 * Of het opnieuw uitrekenen iets doet: met beurten, en niet bij een dynamisch contract in
 * Nederland, want daar rekent de coach elke beurt al met de prijs van dat kwartier.
 */
export const herrekenenKan = (settings) =>
  heeftBeurten(settings) && !(settings?.contract?.type === "dynamic" && settings?.contract?.country !== "PT");

/**
 * Of salderen bij dit contract nog iets doet: tot 1 januari 2027 (`SALDEREN_TOT`), of zolang het
 * contract dagen van daarvoor dekt, want Historie rekent die met het vinkje. In Portugal nooit.
 */
export function salderenTelt(contract, vandaag) {
  if (contract?.country === "PT") return false;
  if (vandaag < SALDEREN_TOT) return true;
  return !contract?.start || contract.start < SALDEREN_TOT;
}

/** Een auto van het huis met een bekende accu: dan kent "laden tot" een accustand om op te stoppen. */
export const autoMetAccu = (device) =>
  (device?.cars ?? []).some((c) => c && !c.guest && Number(c.capacity_kwh) > 0);

/** Of de klaar-tijd telt: niet met Zonder accustand, in de goedkope uren (v0.185.0). */
export const klaarTijdTelt = (device) => !(device?.type === "laadpaal" && device.goedkoop_blok);

/** Of een fase kiezen iets doet: alleen in een huis met drie fasen. */
export const drieFasen = (settings) => Number(settings?.installation?.phases ?? 3) === 3;
