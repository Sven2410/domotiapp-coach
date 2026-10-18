/**
 * Wat de bewoner per apparaat instelt, in de pop-up Instellen achter de kaart
 * (v0.114.0).
 *
 * Stond tot dan onder Apparaten, en dat zag alleen de admin. De eigenaar op
 * 08-10-2026: "bij apparaten dat de klant dat niet kan zien. Maar nu staan er
 * onder apparaten wel dingen wat de klant wel moet kunnen instellen, zoals bij
 * de laadpaal zon beginnen vanaf % en zonder planning, zelfde bij apparaten van
 * reserve in de batterij houden, handelen, een keer per week vol", en op
 * 12-10-2026 koos hij voor een pop-up achter de kaart, met het schema erin.
 *
 * Nooit een entiteit, een merk of een grens van de hardware: die blijven onder
 * Apparaten. De server neemt ook niets anders aan (`VOORKEUREN` in storage.py,
 * `device/preferences` in websocket.py). Elk veld slaat meteen op, zoals de rest
 * van de pop-up.
 */

import { WAKE_MODES, WEEKDAGEN, canSkipRelease, releaseCopy } from "./devices.js";
import { terugleverBekend } from "./geld.js";

const esc = (s) =>
  String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

/** Of dit apparaat iets heeft om in te stellen, los van het schema. */
export const heeftVoorkeuren = (device) =>
  device?.type === "laadpaal" || device?.type === "thuisbatterij" || device?.type === "airco"
  || canSkipRelease(device);

const vink = (attr, sleutel, kop, uitleg) => `
  <label class="check">
    <input type="checkbox" ${attr}="${sleutel}">
    <span><strong>${kop}</strong> ${uitleg}</span>
  </label>`;

const getal = (attr, sleutel, label, grenzen, leeg, uitleg = "") => `
  <div class="row"${attr === "data-vk-accu" ? ` data-vk-rij="${sleutel}"` : ""}>
    <label>${label}</label>
    <input type="number" class="getal" ${attr}="${sleutel}" ${grenzen} inputmode="decimal" placeholder="${leeg}">
    ${uitleg ? `<span class="sub">${uitleg}</span>` : ""}
  </div>`;

function laadpaal(device) {
  const autos = (device.cars ?? []).map((car) => {
    const naam = esc(car.name || "de auto");
    const wekken = car.brand === "tesla" && car.wake_entity
      ? `
      <div class="row">
        <label>${naam}: accustand opvragen</label>
        <div class="segmented">
          ${WAKE_MODES.map((m) => `
            <button type="button" data-vk-wek="${esc(car.id)}:${m.id}" aria-pressed="false">
              <strong>${m.label}</strong>
              ${m.blurb}
            </button>`).join("")}
        </div>
      </div>`
      : "";
    return `
      ${getal("data-vk-auto", `${esc(car.id)}:target_percent`, `${naam}: laadt tot (%)`, 'min="10" max="100" step="5"', "100")}
      ${wekken}`;
  }).join("");
  // De uitleg één keer, onder de auto's, en niet bij elke auto opnieuw.
  const autoUitleg = (device.cars ?? []).length
    ? `<p class="sub">Staat er een laadgrens in de auto, zet hem hier ook. Dan weet de coach wanneer hij klaar is in plaats van het achteraf te merken.</p>`
    : "";
  return `
    <div class="row">
      <label for="vk-modus">Zonder planning</label>
      <select id="vk-modus" data-vk="charge_mode">
        <option value="zon">Zon: alleen op zonoverschot</option>
        <option value="continu">Continu: altijd, met zon erbovenop</option>
        <option value="goedkoopst">Goedkoopst: de goedkoopste bekende uren</option>
      </select>
      <span class="sub">Staat het schema aan, dan wint de planning. Op de kaart kies je per beurt Snel, Continu of Zon; als de kabel eruit gaat, geldt dit weer.</span>
    </div>
    ${getal("data-vk", "continuous_amps", "Continu laden op (A)", 'min="6" max="32" step="1"', "6",
      "Het vaste vermogen van Continu. Geeft de zon meer, dan laadt hij mee omhoog; nooit boven je zekering.")}
    ${getal("data-vk", "solar_start_percent", "Zon: beginnen vanaf (%)", 'min="10" max="100" step="5"', "90",
      "Van het kleinste laadvermogen: 6 A, op drie fasen 4,1 kW. Bij 50% begint Zon al op 2,1 kW zon en komt de rest van het net. Op 100% begint hij pas als de zon het hele vermogen geeft.")}
    ${autos}
    ${autoUitleg}`;
}

/**
 * Bij het vinkje Handelen als de coach de terugleverprijs niet kent (v0.128.2).
 * Dan kan het vinkje niet aan, wel uit. De kaart zegt het ook, uit de prijzen
 * zelf (`HANDELEN_KAN_NIET` in batterij.py).
 */
export const HANDELEN_KAN_NIET =
  "Handelen kan nu niet: de coach kent je terugleverprijs niet. Daarvoor is bij Contract een marktprijssensor nodig, of salderen.";

function thuisbatterij(device) {
  const ventilator = device.entities?.fan
    ? getal("data-vk-accu", "fan_above_c", "Ventilator aan boven (°C)", 'min="0" max="100" step="0.5"', "nooit",
      "De coach zet de ventilator aan zodra de batterij warmer is dan dit, en weer uit als hij een graad eronder zakt. Niet als de coach op Alleen uitlezen of Adviseren staat. Leeg is nooit.")
    : "";
  return `
    ${vink("data-vk-accu", "reserve_enabled", "Reserve houden voor noodstroom.", "Onder deze accustand komt er niets meer uit, wat de prijzen ook zeggen.")}
    ${getal("data-vk-accu", "reserve_percent", "Reserve (%)", 'min="0" max="100" step="5"', "20")}
    ${vink("data-vk-accu", "trade", "Handelen: terugleveren op dure uren.", "De batterij mag dan ook naar het net ontladen, als dat meer opbrengt dan het bijladen straks kost. Staat dit uit, dan voedt hij alleen je eigen huis.")}
    <div class="notice" data-vk-rij="trade_kan_niet" hidden>${HANDELEN_KAN_NIET}</div>
    ${vink("data-vk-accu", "weekly_full", "Een keer per week helemaal vol.", "Tot 100%, voor het balanceren van de cellen. De coach kiest op die dag het goedkoopste moment, en slaat de beurt over als de batterij die week al vol was.")}
    <div class="row" data-vk-rij="weekly_full_day">
      <label for="vk-dag">Op</label>
      <select id="vk-dag" data-vk-accu="weekly_full_day">
        ${WEEKDAGEN.map((dag, i) => `<option value="${i}">${dag}</option>`).join("")}
      </select>
    </div>
    ${vink("data-vk-accu", "holiday", "Vakantiestand.", "Ben je weg en is er veel zon en weinig verbruik, dan staat een batterij dagenlang vol, en dat is slecht voor de cellen. In deze stand houdt de coach hem onder de grens hieronder; de wekelijkse volle beurt slaat hij over.")}
    ${getal("data-vk-accu", "holiday_max_percent", "Hoogste accustand in vakantiestand (%)", 'min="10" max="90" step="5"', "50")}
    ${getal("data-vk-accu", "car_above", "De auto mag de accu gebruiken boven (%)", 'min="0" max="100" step="5"', "nooit",
      "Laadt de auto, dan geeft de batterij normaal niets af: laden en ontladen van de accu en laden van de auto is drie keer verlies. Vul je hier een accustand in, dan mag wat er dáárboven zit naar de auto. Met de nachtstrategie aan (Voorkeuren) houdt hij altijd genoeg over voor de nacht. Leeg is nooit.")}
    ${ventilator}`;
}

function vaatwasser(device) {
  // Een wasmachine of droger (v0.124.0) heeft een deur en geen klep, en de knop
  // heet daar "Mag draaien" (`releaseCopy`).
  const vaat = device?.type === "vaatwasser";
  const knop = releaseCopy(device).label;
  return vink("data-vk", "release_required", "Moet eerst vrijgegeven worden.",
    vaat
      ? 'Aan: de coach wacht tot je hem vrijgeeft met "Ingeruimd en dicht" op de kaart. Uit: klep dicht is genoeg, en de coach start hem zelf op het goedkoopste moment. Na een beurt wacht hij dan tot de klep open en weer dicht is geweest, zodat hij niet opnieuw start met de schone vaat erin.'
      : `Aan: de coach wacht tot je hem vrijgeeft met "${knop}" op de kaart. Uit: deur dicht is genoeg, en de coach start hem zelf op het goedkoopste moment. Na een beurt wacht hij dan tot de deur open en weer dicht is geweest, zodat hij niet opnieuw start met de schone was erin.`);
}

/**
 * Een airco (v0.119.0): welke temperatuur de bewoner wil, waarop hij aan mag
 * (v0.119.1: zon, goedkope uren of beide) en de pauze. De coach zet die
 * temperatuur op de airco en kiest zelf verwarmen of koelen; zie docs/airco.md.
 */
function airco() {
  return `
    ${getal("data-vk-airco", "target_c", "Gewenste temperatuur (°C)", 'min="7" max="35" step="0.5"', "wat er op de airco staat",
      "Kouder dan dit: hij verwarmt bij. Warmer: hij koelt bij. Op temperatuur doet hij niets.")}
    <div class="row">
      <label for="vk-aan-op">Aan op</label>
      <select id="vk-aan-op" data-vk-airco="run_on">
        <option value="zon">Zon: alleen met zon over</option>
        <option value="goedkoop">Goedkope uren: uren onder het daggemiddelde</option>
        <option value="beide">Beide: zon over of een goedkoop uur</option>
      </select>
      <span class="sub">De coach zet de airco nooit zomaar aan om de temperatuur te houden: alleen om bij te verwarmen of bij te koelen als er zon over is, of op een uur dat goedkoper is dan gemiddeld, zoals je hier kiest. Bij een vast contract is geen uur goedkoper dan een ander.</span>
    </div>
    ${vink("data-vk-airco", "paused", "Pauze.",
      "De coach doet niets met de airco. Wat hij zelf aanzette, zet hij uit.")}`;
}

/** De velden voor dit apparaat, zonder waarden; `vulVoorkeuren` zet ze. */
export function voorkeurHtml(device) {
  if (device?.type === "laadpaal") return laadpaal(device);
  if (device?.type === "thuisbatterij") return thuisbatterij(device);
  if (device?.type === "airco") return airco();
  if (canSkipRelease(device)) return vaatwasser(device);
  return "";
}

/**
 * De waarden van het apparaat in de velden, behalve in het veld waar iemand
 * in typt. En de rijen die bij een vinkje horen alleen als dat aanstaat.
 *
 * `contract` is dat uit de instellingen, voor het vinkje Handelen; zonder
 * contract blijft dat vinkje vrij.
 */
export function vulVoorkeuren(root, device, actief = null, contract = null) {
  const b = device?.battery ?? {};
  const zet = (el, waarde) => {
    if (el === actief) return;
    if (el.type === "checkbox") el.checked = Boolean(waarde);
    else el.value = waarde ?? "";
  };
  for (const el of root.querySelectorAll("[data-vk]")) {
    const sleutel = el.dataset.vk;
    const standaard = { charge_mode: "goedkoopst", continuous_amps: 6, solar_start_percent: 90 }[sleutel];
    zet(el, sleutel === "release_required" ? device?.release_required !== false : device?.[sleutel] ?? standaard);
  }
  for (const el of root.querySelectorAll("[data-vk-accu]")) {
    const sleutel = el.dataset.vkAccu;
    const standaard = { reserve_percent: 20, weekly_full_day: 6, holiday_max_percent: 50 }[sleutel];
    zet(el, b[sleutel] ?? standaard);
  }
  for (const el of root.querySelectorAll("[data-vk-airco]")) {
    const sleutel = el.dataset.vkAirco;
    zet(el, (device?.airco ?? {})[sleutel] ?? (sleutel === "run_on" ? "zon" : undefined));
  }
  for (const el of root.querySelectorAll("[data-vk-auto]")) {
    const [id, sleutel] = el.dataset.vkAuto.split(":");
    const auto = (device?.cars ?? []).find((c) => c.id === id);
    zet(el, auto?.[sleutel] ?? 100);
  }
  for (const knop of root.querySelectorAll("[data-vk-wek]")) {
    const [id, modus] = knop.dataset.vkWek.split(":");
    const auto = (device?.cars ?? []).find((c) => c.id === id);
    knop.setAttribute("aria-pressed", String((auto?.wake_mode ?? "manual") === modus));
  }
  const rij = (sleutel, aan) => {
    const el = root.querySelector(`[data-vk-rij="${sleutel}"]`);
    if (el) el.hidden = !aan;
  };
  rij("reserve_percent", b.reserve_enabled);
  rij("weekly_full_day", b.weekly_full);
  rij("holiday_max_percent", b.holiday);
  // Handelen zonder terugleverprijs: uitzetten mag, aanzetten niet.
  const handel = [...root.querySelectorAll("[data-vk-accu]")].find((el) => el.dataset.vkAccu === "trade");
  const kanNiet = Boolean(handel) && contract !== null && !terugleverBekend(contract);
  if (handel) handel.disabled = kanNiet && !handel.checked;
  rij("trade_kan_niet", kanNiet);
}

const binnen = (waarde, laag, hoog) => Math.min(hoog, Math.max(laag, Math.round(waarde)));

/**
 * Wat er naar `device/preferences` gaat voor een veld dat veranderde, of null
 * als er niets te sturen is (een leeg veld dat niet leeg mag zijn).
 */
export function voorkeurWijziging(el) {
  const getalVan = () => (el.value === "" ? null : Number(el.value));
  if (el.dataset.vk) {
    const sleutel = el.dataset.vk;
    if (sleutel === "release_required") return { release_required: el.checked };
    if (sleutel === "charge_mode") return { charge_mode: el.value };
    const n = getalVan();
    if (n === null || !Number.isFinite(n)) return null;
    if (sleutel === "continuous_amps") return { continuous_amps: binnen(n, 6, 32) };
    if (sleutel === "solar_start_percent") return { solar_start_percent: binnen(n, 10, 100) };
    return null;
  }
  if (el.dataset.vkAccu) {
    const sleutel = el.dataset.vkAccu;
    if (el.type === "checkbox") return { battery: { [sleutel]: el.checked } };
    if (sleutel === "weekly_full_day") return { battery: { weekly_full_day: Number(el.value) } };
    const n = getalVan();
    // Leeg is "nooit" bij deze twee; bij de rest is leeg niets om op te slaan.
    if (sleutel === "car_above" || sleutel === "fan_above_c") {
      if (n === null) return { battery: { [sleutel]: null } };
      if (!Number.isFinite(n)) return null;
      return { battery: { [sleutel]: Math.min(100, Math.max(0, n)) } };
    }
    if (n === null || !Number.isFinite(n)) return null;
    if (sleutel === "reserve_percent") return { battery: { reserve_percent: binnen(n, 0, 100) } };
    if (sleutel === "holiday_max_percent") return { battery: { holiday_max_percent: binnen(n, 10, 90) } };
    return null;
  }
  if (el.dataset.vkAirco) {
    const sleutel = el.dataset.vkAirco;
    if (el.type === "checkbox") return { airco: { [sleutel]: el.checked } };
    if (sleutel === "run_on") return { airco: { run_on: el.value } };
    const n = getalVan();
    // Leeg is: wat er op de airco staat.
    if (n === null) return { airco: { target_c: null } };
    if (!Number.isFinite(n)) return null;
    return { airco: { target_c: Math.min(35, Math.max(7, Math.round(n * 2) / 2)) } };
  }
  if (el.dataset.vkAuto) {
    const [id, sleutel] = el.dataset.vkAuto.split(":");
    const n = getalVan();
    if (n === null || !Number.isFinite(n) || sleutel !== "target_percent") return null;
    return { cars: [{ id, target_percent: Math.min(100, Math.max(10, n)) }] };
  }
  if (el.dataset.vkWek) {
    const [id, modus] = el.dataset.vkWek.split(":");
    return { cars: [{ id, wake_mode: modus }] };
  }
  return null;
}
