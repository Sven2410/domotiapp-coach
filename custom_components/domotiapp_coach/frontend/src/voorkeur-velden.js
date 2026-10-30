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

import { WAKE_MODES, WEEKDAGEN, canSkipRelease, inTaal, releaseCopy, weekdag } from "./devices.js";
import { terugleverBekend, vlakkePrijs } from "./geld.js";
import { locale, nt, t } from "./i18n.js";
import { accuKeuzes, handelenKan, klaarTijdTelt } from "./toepassing.js";

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

/**
 * Een onderwerp in een eigen vak met de kop erin (.block in theme.js), zoals elk
 * scherm. De eigenaar op 21-10-2026: "Ik vind de opzet zoals je bij installatie
 * gebruikt wel echt duidelijk", en "daar zou over de hele app meer uniformiteit in
 * mogen komen".
 */
const blok = (kop, inhoud, rij = "") => `
  <div class="block"${rij ? ` data-vk-rij="${rij}"` : ""}>
    <div class="block-title">${kop}</div>
    ${inhoud}
  </div>`;

/**
 * Een functie die aan of uit kan, met een getal dat erbij hoort (21-10-2026). Tot
 * dan was het alleen het getal, met "leeg is nooit". De eigenaar: "Ene is een checkbox
 * (bold font), ander is gewoon een regel." Het vinkje bewaart zelf niets: aan is een
 * getal in `sleutel`, uit is null, zoals altijd. Aanzetten zet alleen het veld neer;
 * pas met een getal erin staat het aan, want de coach verzint geen grens. Een leeg
 * veld blijft uit. `data-open` onthoudt dat iemand het vinkje net aanzette.
 */
const vinkMetGetal = (sleutel, kop, uitleg) => `
  <label class="check">
    <input type="checkbox" data-vk-aan="${sleutel}">
    <span><strong>${kop}</strong> ${uitleg}</span>
  </label>`;

const getal = (attr, sleutel, label, grenzen, leeg, uitleg = "") => `
  <div class="row"${attr === "data-vk-accu" ? ` data-vk-rij="${sleutel}"` : ""}>
    <label>${label}</label>
    <input type="number" class="getal" ${attr}="${sleutel}" ${grenzen} inputmode="decimal" placeholder="${leeg}">
    ${uitleg ? `<span class="sub">${uitleg}</span>` : ""}
  </div>`;

function laadpaal(device, zon) {
  const autos = (device.cars ?? []).map((car) => {
    const naam = esc(car.name || t("de auto"));
    const wekken = car.brand === "tesla" && car.wake_entity
      ? `
      <div class="row">
        <label>${t("{naam}: accustand opvragen", { naam })}</label>
        <div class="segmented">
          ${WAKE_MODES.map(inTaal).map((m) => `
            <button type="button" data-vk-wek="${esc(car.id)}:${m.id}" aria-pressed="false">
              <strong>${m.label}</strong>
              ${m.blurb}
            </button>`).join("")}
        </div>
      </div>`
      : "";
    return `
      ${getal("data-vk-auto", `${esc(car.id)}:target_percent`, t("{naam}: laadt tot (%)", { naam }), 'min="10" max="100" step="5"', "100")}
      ${wekken}`;
  }).join("");
  // De uitleg één keer, onder de auto's, en niet bij elke auto opnieuw.
  const autoUitleg = (device.cars ?? []).length
    ? `<p class="sub">${t("Staat er een laadgrens in de auto, zet hem hier ook. Dan weet de coach wanneer hij klaar is in plaats van het achteraf te merken.")}</p>`
    : "";
  return `${blok(t("Zonder planning"), `
    <div class="row">
      <label for="vk-modus">${t("Modus")}</label>
      <select id="vk-modus" data-vk="charge_mode">
        ${zon || device.charge_mode === "zon" ? `<option value="zon">${t("Zon: alleen op zonoverschot")}</option>` : ""}
        <option value="continu">${t("Continu: altijd, met zon erbovenop")}</option>
        <option value="goedkoopst" data-vk-goedkoopst>${t("Goedkoopst: de goedkoopste bekende uren")}</option>
      </select>
      <span class="sub">${klaarTijdTelt(device)
        ? t("Staat het schema aan, dan wint de planning. Op de kaart kies je per beurt Snel, Continu of Zon; als de kabel eruit gaat, geldt dit weer.")
        : t("Op de kaart kies je per beurt Snel, Continu of Zon; als de kabel eruit gaat, geldt dit weer.")}</span>
    </div>
    ${getal("data-vk", "continuous_amps", t("Continu laden op (A)"), 'min="6" max="32" step="1"', "6",
      t("Het vaste vermogen van Continu. Geeft de zon meer, dan laadt hij mee omhoog; nooit boven je zekering."))}
    ${zon ? getal("data-vk", "solar_start_percent", t("Zon: beginnen vanaf (%)"), 'min="10" max="100" step="5"', "90",
      t("Van het kleinste laadvermogen: 6 A, op drie fasen 4,1 kW. Bij 50% begint Zon al op 2,1 kW zon en komt de rest van het net. Op 100% begint hij pas als de zon het hele vermogen geeft.")) : ""}`)}
    ${(device.cars ?? []).length ? blok(t("Auto's"), `${autos}${autoUitleg}`) : ""}`;
}

/**
 * Bij het vinkje Handelen als de coach de terugleverprijs niet kent (v0.128.2).
 * Dan kan het vinkje niet aan, wel uit. De kaart zegt het ook, uit de prijzen
 * zelf (`HANDELEN_KAN_NIET` in batterij.py).
 */
export const HANDELEN_KAN_NIET =
  nt("Handelen kan nu niet: de coach kent je terugleverprijs niet. Daarvoor is bij Contract een marktprijssensor nodig, of salderen.");

function thuisbatterij(device) {
  // De ventilator alleen met een temperatuur erbij: zonder meet de coach niets om hem op aan te zetten.
  const ventilator = device.entities?.fan && device.entities?.temperature
    ? blok(t("Ventilator"), `
    ${vinkMetGetal("fan_above_c", t("De coach zet de ventilator aan."),
      t("Zodra de batterij warmer is dan de grens, en weer uit een graad eronder. Niet als de coach op Alleen uitlezen of Adviseren staat."))}
    ${getal("data-vk-accu", "fan_above_c", t("Aan boven (°C)"), 'min="0" max="100" step="0.5"', "", t("Zonder grens staat dit uit."))}`)
    : "";
  // Bij een batterij met een laadschema geen Noodstroom, Balanceren, Vakantiestand en De auto (v0.186.0).
  const keuzes = accuKeuzes(device);
  return `
    ${keuzes ? blok(t("Noodstroom"), `
    ${vink("data-vk-accu", "reserve_enabled", t("Reserve aanhouden."), t("Onder deze accustand komt er niets meer uit, wat de prijzen ook zeggen."))}
    ${getal("data-vk-accu", "reserve_percent", t("Reserve (%)"), 'min="0" max="100" step="5"', "20")}`) : ""}
    ${blok(t("Handelen"), `
    ${vink("data-vk-accu", "grid_charge", t("Laden uit het net tijdens lage tarieven."), t("De batterij mag dan ook van het net laden, als dat minder kost dan wat hij je straks bespaart. Staat dit uit, dan gaat er alleen zon in."))}
    ${getal("data-vk-accu", "grid_charge_below", t("Alleen als de prijs onder (€/kWh)"), 'min="-1" max="2" step="0.01"', t("de coach bepaalt"))}
    <div data-vk-rij="trade" style="display: contents">
    ${vink("data-vk-accu", "trade", t("Ontladen naar het net tijdens hoge tarieven."), t("De batterij mag dan ook naar het net ontladen, als dat meer opbrengt dan het bijladen straks kost. Staat dit uit, dan voedt hij alleen je eigen huis."))}
    <div class="notice" data-vk-rij="trade_kan_niet" hidden>${t(HANDELEN_KAN_NIET)}</div>
    ${getal("data-vk-accu", "trade_above", t("Alleen als de prijs boven (€/kWh)"), 'min="-1" max="2" step="0.01"', t("de coach bepaalt"))}
    </div>
    ${getal("data-vk-accu", "grid_charge_min_gain", t("Alleen als het minstens oplevert (€)"), 'min="0" max="5" step="0.01"', "0.05",
      t("Per beurt van of naar het net, na belasting, verlies en afschrijving. Een verwachting komt niet altijd uit; onder dit bedrag laat hij het. Nul is geen ondergrens."))}
    <p class="sub">${t("De prijzen zijn all-in, met belasting en opslag. Leeg: de coach kiest zelf de beste uren.")}</p>`, "handelen")}
    ${blok(t("Afschrijving"), `
    ${getal("data-vk-accu", "wear_per_kwh", t("Afschrijving (€ per kWh)"), 'min="0" max="1" step="0.001"', t("geen"),
      t("Wat elke kWh die uit de batterij komt aan slijtage kost. De coach laadt en ontlaadt pas als het verschil in prijs het verlies in de batterij én dit bedrag dekt. Leeg: alleen het verlies."))}
    <label class="check">
      <input type="checkbox" data-vk-hulp="afschrijving">
      <span><strong>${t("Help me dit uit te rekenen.")}</strong> ${t("Vul de aanschafprijs en het aantal laadcycli van de leverancier in.")}</span>
    </label>
    ${getal("data-vk-accu", "wear_price", t("Aanschafprijs (€)"), 'min="0" max="100000" step="1"', "", t("Ook voor Terugverdiend op de kaart. Zonder laadcycli telt hij niet mee in de afschrijving."))}
    ${getal("data-vk-accu", "wear_cycles", t("Laadcycli volgens de leverancier"), 'min="1" max="100000" step="1"', "")}
    <p class="sub" data-vk-rij="afschrijving_uitkomst" hidden></p>`)}
    ${keuzes ? blok(t("Balanceren"), `
    ${vink("data-vk-accu", "weekly_full", t("Een keer per week helemaal vol."), t("Tot 100%, voor het balanceren van de cellen. De coach kiest op die dag het goedkoopste moment, en slaat de beurt over als de batterij die week al vol was."))}
    <div class="row" data-vk-rij="weekly_full_day">
      <label for="vk-dag">${t("Op")}</label>
      <select id="vk-dag" data-vk-accu="weekly_full_day">
        ${WEEKDAGEN.map((_, i) => `<option value="${i}">${weekdag(i)}</option>`).join("")}
      </select>
    </div>`) : ""}
    ${keuzes ? blok(t("Vakantiestand"), `
    ${vink("data-vk-accu", "holiday", t("Aan zolang je weg bent."), t("Bij veel zon en weinig verbruik staat een batterij anders dagenlang vol, en dat is slecht voor de cellen. De coach houdt hem onder de grens hieronder en slaat de wekelijkse volle beurt over."))}
    ${getal("data-vk-accu", "holiday_max_percent", t("Hoogste accustand (%)"), 'min="10" max="90" step="5"', "50")}`) : ""}
    ${keuzes ? blok(t("De auto"), `
    ${vinkMetGetal("car_above", t("De accu mag de auto helpen."),
      t("Laadt de auto, dan geeft de batterij normaal niets af: laden en ontladen van de accu en laden van de auto is drie keer verlies. Met dit aan mag wat boven de grens zit naar de auto. Met de nachtstrategie aan (Voorkeuren) houdt hij altijd genoeg over voor de nacht."))}
    ${getal("data-vk-accu", "car_above", t("Boven deze accustand (%)"), 'min="0" max="100" step="5"', "", t("Zonder grens staat dit uit."))}`) : ""}
    ${ventilator}`;
}

function vaatwasser(device) {
  // Een wasmachine of droger (v0.124.0) heeft een deur en geen klep, en de knop
  // heet daar "Mag draaien" (`releaseCopy`).
  const vaat = device?.type === "vaatwasser";
  const knop = releaseCopy(device).label;
  return blok(t("Vrijgeven"), vink("data-vk", "release_required", t("Moet eerst vrijgegeven worden."),
    vaat
      ? t("Aan: de coach wacht tot je hem vrijgeeft met \"Ingeruimd en dicht\" op de kaart. Uit: klep dicht is genoeg, en de coach start hem zelf op het goedkoopste moment. Na een beurt wacht hij dan tot de klep open en weer dicht is geweest, zodat hij niet opnieuw start met de schone vaat erin.")
      : t("Aan: de coach wacht tot je hem vrijgeeft met \"{knop}\" op de kaart. Uit: deur dicht is genoeg, en de coach start hem zelf op het goedkoopste moment. Na een beurt wacht hij dan tot de deur open en weer dicht is geweest, zodat hij niet opnieuw start met de schone was erin.", { knop })));
}

/**
 * Een airco (v0.119.0): welke temperatuur de bewoner wil, waarop hij aan mag
 * (v0.119.1: zon, goedkope uren of beide) en de pauze. De coach zet die
 * temperatuur op de airco en kiest zelf verwarmen of koelen; zie docs/airco.md.
 */
function airco() {
  return blok(t("Zo wil je het"), `
    ${getal("data-vk-airco", "target_c", t("Gewenste temperatuur (°C)"), 'min="7" max="35" step="0.5"', t("wat er op de airco staat"),
      t("Kouder dan dit: hij verwarmt bij. Warmer: hij koelt bij. Op temperatuur doet hij niets."))}
    <div class="row" data-vk-rij="run_on">
      <label for="vk-aan-op">${t("Aan op")}</label>
      <select id="vk-aan-op" data-vk-airco="run_on">
        <option value="zon">${t("Zon: alleen met zon over")}</option>
        <option value="goedkoop">${t("Goedkope uren: uren onder het daggemiddelde")}</option>
        <option value="beide">${t("Beide: zon over of een goedkoop uur")}</option>
      </select>
      <span class="sub">${t("De coach zet de airco nooit zomaar aan om de temperatuur te houden: alleen om bij te verwarmen of bij te koelen als er zon over is, of op een uur dat goedkoper is dan gemiddeld, zoals je hier kiest. Bij een vast contract is geen uur goedkoper dan een ander.")}</span>
    </div>
    ${vink("data-vk-airco", "paused", t("Pauze."),
      t("De coach doet niets met de airco. Wat hij zelf aanzette, zet hij uit."))}`);
}

/**
 * De velden voor dit apparaat, zonder waarden; `vulVoorkeuren` zet ze. `zon` is of er
 * zonnepanelen zijn (`heeftZon` in toepassing.js): zonder geen modus Zon en geen "Zon: beginnen
 * vanaf" (v0.186.0), tenzij Zon al gekozen was. Onbekend telt als wel.
 */
export function voorkeurHtml(device, { zon = true } = {}) {
  if (device?.type === "laadpaal") return laadpaal(device, zon);
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
 * contract blijft dat vinkje vrij. Bij een vlakke prijs (v0.149.0, `vlakkePrijs`)
 * verdwijnen Handelen en de keuze waarop een airco aan mag, en heet Goedkoopst
 * bij de laadpaal Slim. Wat er stond blijft bewaard: de coach doet er bij een
 * vlakke prijs niets mee, en na een overstap naar dynamisch staat het er weer.
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
    const standaard = { reserve_percent: 20, weekly_full_day: 6, holiday_max_percent: 50, grid_charge: true }[sleutel];
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
  for (const el of root.querySelectorAll("[data-vk-aan]")) {
    if (el === actief) continue;
    el.checked = b[el.dataset.vkAan] != null || el.dataset.open === "1";
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
  // De grens per richting alleen als die richting aanstaat (v0.141.0).
  rij("grid_charge_below", b.grid_charge !== false);
  // Naar het net ontladen niet bij een batterij met een laadschema, en niet als teruglevering
  // niets oplevert (v0.186.0, `handelenKan`). Wat aan stond blijft bewaard en doet niets.
  const handelen = handelenKan(device, contract);
  rij("trade", handelen);
  rij("grid_charge_min_gain", b.grid_charge !== false || (handelen && Boolean(b.trade)));
  rij("trade_above", Boolean(b.trade));
  // Een grens die bij een vinkje hoort, zolang het vinkje aan staat (21-10-2026).
  for (const el of root.querySelectorAll("[data-vk-aan]")) {
    rij(el.dataset.vkAan, b[el.dataset.vkAan] != null || el.dataset.open === "1" || el.checked);
  }
  // De afschrijving (v0.146.0): het veld per kWh, of met de hulp de aanschafprijs en
  // de laadcycli, en wat dat per kWh is. Een cyclus is de hele inhoud er een keer uit.
  const hulp = root.querySelector("[data-vk-hulp]");
  const hulpOpen = b.wear_price != null || b.wear_cycles != null || hulp?.dataset.open === "1";
  if (hulp && hulp !== actief) hulp.checked = hulpOpen;
  rij("wear_per_kwh", !hulpOpen);
  rij("wear_price", hulpOpen);
  rij("wear_cycles", hulpOpen);
  const uitkomst = root.querySelector('[data-vk-rij="afschrijving_uitkomst"]');
  if (uitkomst) {
    const per = afschrijvingPerKwh(b);
    uitkomst.textContent = !hulpOpen || b.wear_price == null || !b.wear_cycles
      ? ""
      : per === null
        ? t("De coach deelt de aanschafprijs door het aantal cycli maal de capaciteit van de batterij.")
        : t("Dat is € {bedrag} per kWh uit de batterij.", { bedrag: per.toLocaleString(locale(), { minimumFractionDigits: 3, maximumFractionDigits: 3 }) });
    uitkomst.hidden = !uitkomst.textContent;
  }
  // Een vlakke prijs (v0.149.0): wat op een goedkoper of duurder uur wacht doet niets.
  const vlak = vlakkePrijs(contract);
  rij("handelen", !vlak);
  rij("run_on", !vlak);
  const goedkoopst = root.querySelector("[data-vk-goedkoopst]");
  if (goedkoopst) {
    // Met Zonder accustand, in de goedkope uren (v0.185.0) laadt Goedkoopst in het blok.
    goedkoopst.textContent = vlak
      ? t("Slim: eerst zon, dan het net buiten de avondpiek")
      : klaarTijdTelt(device)
        ? t("Goedkoopst: de goedkoopste bekende uren")
        : t("Goedkoopst: het goedkoopste blok van het etmaal");
  }
  // Handelen zonder terugleverprijs: uitzetten mag, aanzetten niet.
  const handel = [...root.querySelectorAll("[data-vk-accu]")].find((el) => el.dataset.vkAccu === "trade");
  const kanNiet = Boolean(handel) && handelen && contract !== null && !terugleverBekend(contract);
  if (handel) handel.disabled = kanNiet && !handel.checked;
  rij("trade_kan_niet", kanNiet);
}

const binnen = (waarde, laag, hoog) => Math.min(hoog, Math.max(laag, Math.round(waarde)));

/**
 * De afschrijving per kWh uit de aanschafprijs en de laadcycli, zoals `_slijtage` in
 * coach.py: prijs gedeeld door cycli maal capaciteit. Null als de capaciteit hier niet
 * bekend is (een sensor leest alleen de coach).
 */
export function afschrijvingPerKwh(b) {
  const prijs = Number(b?.wear_price);
  const cycli = Number(b?.wear_cycles);
  const cap = Number(b?.capacity_kwh);
  if (!(prijs >= 0) || !(cycli > 0) || !(cap > 0) || b?.wear_price == null) return null;
  return prijs / (cycli * cap);
}

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
  if (el.dataset.vkHulp) {
    el.dataset.open = el.checked ? "1" : "";
    return el.checked ? null : { battery: { wear_price: null, wear_cycles: null } };
  }
  if (el.dataset.vkAan) {
    const sleutel = el.dataset.vkAan;
    el.dataset.open = el.checked ? "1" : "";
    return el.checked ? null : { battery: { [sleutel]: null } };
  }
  if (el.dataset.vkAccu) {
    const sleutel = el.dataset.vkAccu;
    if (el.type === "checkbox") return { battery: { [sleutel]: el.checked } };
    if (sleutel === "weekly_full_day") return { battery: { weekly_full_day: Number(el.value) } };
    const n = getalVan();
    // Leeg is "de coach bepaalt" bij de grenzen van handelen (v0.141.0), in euro per kWh.
    // De afschrijving (v0.146.0): leeg is geen.
    if (sleutel === "wear_per_kwh" || sleutel === "wear_price" || sleutel === "wear_cycles") {
      if (n === null) return { battery: { [sleutel]: null } };
      if (!Number.isFinite(n)) return null;
      const grens = { wear_per_kwh: [0, 1], wear_price: [0, 100000], wear_cycles: [1, 100000] }[sleutel];
      const afgerond = sleutel === "wear_per_kwh" ? Math.round(n * 10000) / 10000 : Math.round(n);
      return { battery: { [sleutel]: Math.min(grens[1], Math.max(grens[0], afgerond)) } };
    }
    if (sleutel === "grid_charge_min_gain") {
      if (n === null) return { battery: { grid_charge_min_gain: null } };
      if (!Number.isFinite(n)) return null;
      return { battery: { grid_charge_min_gain: Math.min(5, Math.max(0, Math.round(n * 100) / 100)) } };
    }
    if (sleutel === "grid_charge_below" || sleutel === "trade_above") {
      if (n === null) return { battery: { [sleutel]: null } };
      if (!Number.isFinite(n)) return null;
      return { battery: { [sleutel]: Math.min(2, Math.max(-1, Math.round(n * 10000) / 10000)) } };
    }
    // Leeg is uit bij deze twee; bij de rest is leeg niets om op te slaan. Het vinkje
    // erboven gaat dan ook uit (21-10-2026).
    if (sleutel === "car_above" || sleutel === "fan_above_c") {
      if (n === null) {
        const aan = el.closest?.(".block")?.querySelector?.("[data-vk-aan]");
        if (aan) aan.dataset.open = "";
        return { battery: { [sleutel]: null } };
      }
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
