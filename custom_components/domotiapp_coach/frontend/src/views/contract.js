/**
 * Contract -- wat stroom, gas en water kosten, nu en vroeger.
 *
 * Stond tot v0.114.0 onder Installatie. De eigenaar op 08-10-2026: "sommige
 * dingen kunnen van installatie naar instellingen of andersom, het moet beter
 * gecategoriseerd worden." Installatie is nu hoe het huis gemeten wordt en wat
 * het aankan; wat het kost is een eigen onderwerp, en alleen de installateur
 * ziet het.
 *
 * Sinds v0.129.0 per energiebron. De bewoner van de eerste woning op
 * 18-10-2026: "Eerst álles uitvragen over elektriciteit (incl historische
 * contracten), dán pas alles over gas (en mogelijk ook te kiezen tussen vast en
 * dynamisch), en daarna pas water." Per bron een leverancier uit de catalogus
 * (`leveranciers.js`) die de velden voorinvult, de looptijd, en de knop "Ik heb
 * een nieuw contract afgesloten" die het huidige contract bij de eerdere zet.
 * Bij stroom de opbouw in woorden en cijfers (`opbouw.js`), nagerekend door de
 * coach tegen de all-in sensor, en "Ja, dit klopt".
 *
 * Sinds v0.130.1 ziet de bewoner dit scherm ook, alleen om te lezen: per bron
 * wat voor contract, bij wie, van wanneer tot wanneer, de opbouw van zijn
 * stroomprijs en "Ja, dit klopt". Die prijs stond tot dan onder Voorkeuren; de
 * eigenaar op 19-10-2026: "je energieprijs staat nu in voorkeuren maar dat moet
 * onder contract." Wat met `data-installateur` gemerkt is ziet hij niet, want
 * daar staan sensoren en bedragen die de installateur kiest.
 */

import { define } from "../base.js";
import { icons } from "../icons.js";
import {
  DacEditorElement,
  editorCss,
  saveBarHtml,
} from "./editor-base.js";
import "../components/entity-picker.js";
import { SALDEREN_TOT, salderen } from "../geld.js";
import { herrekenenKan, salderenTelt } from "../toepassing.js";
import { datum, locale, nt, t, tn } from "../i18n.js";
import { bevestigdZin, opbouwCss, opbouwHtml } from "../opbouw.js";
import {
  SOORTEN,
  belastingStroom,
  leverancier,
  leveranciersVoor,
  namenVan,
  nordPoolVan,
  sensorVan,
  voorstel,
} from "../leveranciers.js";

const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

/** De soort in een zin; vertaald waar hij getoond wordt, met `soortNaam`. */
const SOORT_NAAM = { fixed: nt("vast"), variable: nt("variabel"), dynamic: nt("dynamisch") };

/** De soort in de taal van nu, "vast" als hij onbekend is; met een hoofdletter vooraan voor een zin. */
const soortNaam = (soort) => t(SOORT_NAAM[soort] ?? "vast");
const hoofd = (tekst) => tekst.replace(/^./, (x) => x.toUpperCase());

/** Een datum als "18-10-2026" (in het Engels 18/10/2026), voor een naam. */
const kortDatum = (tekst) => {
  if (!tekst) return "";
  const d = new Date(`${tekst}T12:00:00`);
  return Number.isNaN(d.getTime())
    ? tekst.split("-").reverse().join("-")
    : datum(d, { day: "2-digit", month: "2-digit", year: "numeric" });
};

/** Van wanneer tot wanneer, met "?" en "nu" voor wat er niet is. */
const vanTot = (van, tot) => t("{van} tot {tot}", { van: kortDatum(van) || "?", tot: kortDatum(tot) || t("nu") });

/**
 * De naam die een eerder contract voorgesteld krijgt (v0.129.0): leverancier,
 * soort en de datums. De bewoner van de eerste woning op 19-10-2026: "ook
 * handmatig een naam kunnen ingeven van dat contract", zoals "Zonneplan Elektra
 * 2026"; dit is alleen het begin, hij past hem aan.
 */
function voorgesteldeNaam(bron, supplier, soort, van, tot) {
  const naam = leverancier(supplier)?.naam ?? "";
  const wat = { stroom: t("stroom"), gas: t("gas"), water: t("water") }[bron];
  const datums = van || tot ? vanTot(van, tot) : "";
  return [naam, soort ? `${wat}, ${t(SOORT_NAAM[soort] ?? "")}` : wat, datums].filter(Boolean).join(" ");
}

/** Vandaag en gisteren als "2026-10-18", in de tijd van het huis. */
const euro2 = (n) => `€ ${Number(n || 0).toLocaleString(locale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/**
 * Wat het opnieuw uitrekenen van de beurten gaf (v0.136.0), in een paar zinnen.
 * `uit` komt van `savings/recalculate` (`async_herreken_beurten` in coach.py).
 */
export function beurtenZin(uit) {
  if (!uit) return "";
  if (uit.fout) return uit.fout;
  const vanaf = datum(new Date(`${uit.van}T12:00:00`), { day: "numeric", month: "long", year: "numeric" });
  const zinnen = [];
  if (!uit.beurten) {
    zinnen.push(t("Vanaf {datum} is er geen afgeronde beurt met een vaste prijs.", { datum: vanaf }));
  } else {
    const bedragen = { datum: vanaf, betaaldVoor: euro2(uit.voor?.paid), betaaldNa: euro2(uit.na?.paid),
      bespaardVoor: euro2(uit.voor?.saved), bespaardNa: euro2(uit.na?.saved) };
    zinnen.push(tn(uit.beurten,
      "Vanaf {datum}, {n} beurt: betaald was {betaaldVoor} en wordt {betaaldNa}, bespaard was {bespaardVoor} en wordt {bespaardNa}.",
      "Vanaf {datum}, {n} beurten: betaald was {betaaldVoor} en wordt {betaaldNa}, bespaard was {bespaardVoor} en wordt {bespaardNa}.",
      bedragen));
  }
  if (uit.overgeslagen) {
    zinnen.push(tn(uit.overgeslagen,
      "{n} beurt met een dynamische prijs blijft zoals hij was.",
      "{n} beurten met een dynamische prijs blijven zoals ze waren."));
  }
  if (uit.toegepast) zinnen.push(t("Overgenomen."));
  return zinnen.join(" ");
}

function dagTekst(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const euroTekst = (n) => `€ ${Number(n).toLocaleString(locale(), { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`;

function datumLang(tekst) {
  if (!tekst) return "";
  const d = new Date(`${tekst}T12:00:00`);
  return Number.isNaN(d.getTime()) ? tekst : datum(d, { day: "numeric", month: "long", year: "numeric" });
}

/** De vier vormen van terugleverkosten (v0.135.0), zoals `kosten_per_kwh` in prijsopbouw.py. */
const KOSTEN_VORMEN = [
  ["kwh", nt("Per kWh, over alles wat je teruglevert")],
  ["overschot", nt("Per kWh, alleen over wat er na salderen overblijft")],
  ["schalen", nt("Een vast bedrag per jaar, in schalen")],
  ["geen", nt("Geen terugleverkosten")],
];

/**
 * De keuze hoe de leverancier terugleverkosten rekent, en bij schalen de tabel
 * (v0.135.0). De eigenaar op 19-10-2026: "ik wil het zo goed mogelijk hebben".
 */
const kostenVorm = (prefix) => `
  <div class="row">
    <label for="${prefix}-kostvorm">${t("Hoe rekent je leverancier terugleverkosten?")}</label>
    <select id="${prefix}-kostvorm" data-kostvorm="${prefix}">
      ${KOSTEN_VORMEN.map(([id, tekst]) => `<option value="${id}">${t(tekst)}</option>`).join("")}
    </select>
  </div>
  <div class="schalen" id="${prefix}-schalen-blok">
    <span class="sub">${t("De tabel van je leverancier: vanaf hoeveel kWh teruglevering over je afrekenperiode een schaal geldt, en wat hij per jaar kost met btw. Onder de eerste schaal kost het niets. Een kWh extra kost dan niets; het bedrag staat in Historie per dag.")}</span>
    <div class="schaal-kop"><span>${t("Vanaf (kWh)")}</span><span>${t("Per jaar (€)")}</span><span></span></div>
    <div id="${prefix}-schalen"></div>
    <div class="circuit-actions"><button type="button" data-schaal-erbij="${prefix}">${t("Schaal toevoegen")}</button></div>
    <div class="row">
      <label for="${prefix}-schalen-tot">${t("De schalen gelden tot")}</label>
      <input type="date" id="${prefix}-schalen-tot" data-schalen-tot="${prefix}">
      <span class="sub">${t("Leeg is de hele afrekenperiode. Stoppen de vaste terugleverkosten op 1 januari 2027, zoals bij veel leveranciers, vul dan die datum in: dan telt de teruglevering tot die dag voor de schaal.")}</span>
    </div>
  </div>`;

// De drie soorten staan in leveranciers.js (stap 3 van het Engels); hun Engels staat al in
// i18n/en/contract.js, want het zijn de knoppen van dit scherm.
const soortKnoppen = (id) => `
  <div class="segmented drie" id="${id}">
    ${SOORTEN.map((s) => `
      <button type="button" data-soort="${s.key}" aria-pressed="false">
        <strong>${t(s.label)}</strong>
        ${t(s.uitleg)}
      </button>`).join("")}
  </div>`;

const levKeuze = (id, bron) => `
  <select id="${id}">
    <option value="">${t("Andere leverancier")}</option>
    ${leveranciersVoor(bron).map((l) => `<option value="${esc(l.id)}">${esc(l.naam)}</option>`).join("")}
  </select>`;

/**
 * De eerdere contracten voor de bewoner (v0.130.1): een regel per contract met
 * de naam, de datums en de prijs, zonder velden.
 */
export function periodesLezen(bron, lijst) {
  if (!lijst?.length) return `<p class="sub geen">${t("Geen eerdere contracten.")}</p>`;
  return lijst.map((p) => {
    const titel = p.name || leverancier(p.supplier)?.naam || t("Eerder contract");
    const wanneer = p.from || p.to ? vanTot(p.from, p.to) : "";
    let prijs = "";
    if (bron === "stroom") {
      prijs = p.type === "dynamic" ? t("Dynamisch") : Number(p.all_in_price) > 0 ? `${euroTekst(p.all_in_price)} per kWh` : "";
    } else if (Number(p.price) > 0) {
      prijs = `${euroTekst(p.price)} per m³`;
    }
    return `
      <div class="circuit period lezen">
        <div class="p-kop"><span class="p-naam">${esc(titel)}</span><span class="p-wanneer">${esc(wanneer)}</span></div>
        ${prijs ? `<span class="sub">${esc(prijs)}</span>` : ""}
      </div>`;
  }).join("");
}

class DacViewContract extends DacEditorElement {
  static sections = ["contract"];

  /**
   * Het contract, en sinds v0.138.0 ook of de woning gas en een watermeter heeft:
   * dezelfde twee vinkjes als bij Installatie. Alleen die twee uit `sources`, zodat
   * opslaan hier de sensoren van Installatie niet terugzet; de server voegt ze samen
   * (`_merge` in storage.py).
   */
  slice_(settings) {
    if (!settings) return {};
    const meters = settings.sources?.meters ?? {};
    return {
      contract: settings.contract,
      sources: { meters: { gas_enabled: Boolean(meters.gas_enabled), water_enabled: Boolean(meters.water_enabled) } },
    };
  }

  constructor() {
    super();
    this.check_ = null;
    this.checkTimer_ = null;
    this.checkRun_ = 0;
  }

  render() {
    return `
      <div class="wrap">
        <header class="intro">
          <div class="eyebrow">${t("Contract")}</div>
          <h1>${t("Wat je energie kost")}</h1>
          <p>${t("Per energiebron je contract van nu en wat je eerder had. De coach rekent met je stroomcontract; gas en water zijn voor de historie en het rapport.")}</p>
          <p class="bewoner-uitleg">${t("Je installateur vult je contract in. Kijk hieronder of je stroomprijs klopt met de app of site van je leverancier, en bevestig hem. Klopt er iets niet, laat het je installateur dan weten.")}</p>
        </header>

        <!-- ================= stroom ================= -->
        <section class="card" id="stroom">
          <h2>${icons.bolt} ${t("Mijn huidige stroomcontract")}</h2>
          <p class="hint" id="stroom-samenvatting"></p>
          <div class="fields">
            <!-- Het land (v0.137.0). De eigenaar op 19-10-2026: "bij contract bovenaan wil ik
                 dat je een land kan kiezen dus Nederland en Portugal." Sinds v0.138.0 een
                 keuzelijst: "ik wil een dropdown menu van het land hebben nu staat er 2 velden
                 groot in beeld." -->
            <div class="block" data-installateur>
            <div class="block-title">${t("Leverancier en looptijd")}</div>
            <div class="row">
              <label for="land">${t("Land")}</label>
              <select id="land">
                <option value="NL">${t("Nederland")}</option>
                <option value="PT">Portugal</option>
              </select>
              <span class="sub" id="land-hint"></span>
            </div>

            <div class="row" data-installateur id="soort-rij">
              <label>${t("Soort contract")}</label>
              ${soortKnoppen("stroom-soort")}
            </div>

            <div class="row" data-installateur id="lev-rij">
              <label for="stroom-lev">${t("Leverancier")}</label>
              ${levKeuze("stroom-lev", "stroom")}
              <span class="sub" id="stroom-lev-hint"></span>
            </div>

            <div class="row" id="pt-lev-rij">
              <label for="pt-lev">${t("Leverancier")}</label>
              <input type="text" id="pt-lev" maxlength="60" placeholder="${t("Bijvoorbeeld EDP Comercial")}">
            </div>

            <div class="two">
              <div class="row">
                <label for="stroom-start">${t("Mijn contract is ingegaan op")}</label>
                <input type="date" id="stroom-start">
              </div>
              <div class="row" id="stroom-eind-rij">
                <label for="stroom-end">${t("Mijn contract loopt af op")}</label>
                <input type="date" id="stroom-end">
                <span class="sub">${t("Alleen bij een vast contract. Variabel en dynamisch zijn maandelijks opzegbaar.")}</span>
                <label for="stroom-dagen" class="klein">${t("Herinner me zoveel dagen vooraf")}</label>
                <input type="number" id="stroom-dagen" min="0" max="365" step="1" inputmode="numeric">
              </div>
            </div>
            </div>

            <!-- Portugal (v0.137.0): een prijs per tijdvak van de ERSE; zie tarifas.py. -->
            <div id="pt-fields" class="fields" data-installateur>
              <div class="block fields">
              <div class="block-title">${t("Prijs per tijdvak")}</div>
              <div class="row">
                <label>Opção horária</label>
                <div class="segmented drie" id="pt-tarifa">
                  <button type="button" data-tarifa="simples" aria-pressed="false"><strong>Simples</strong>${t("Eén prijs, de hele dag.")}</button>
                  <button type="button" data-tarifa="bi" aria-pressed="false"><strong>Bi-horário</strong>${t("Daluren (vazio) en de rest.")}</button>
                  <button type="button" data-tarifa="tri" aria-pressed="false"><strong>Tri-horário</strong>${t("Daluren, normaal (cheias) en piek (ponta).")}</button>
                </div>
              </div>
              <div class="row" id="pt-ciclo-rij">
                <label>Ciclo</label>
                <div class="segmented" id="pt-ciclo">
                  <button type="button" data-ciclo="diario" aria-pressed="false"><strong>Ciclo diário</strong>${t("Elke dag hetzelfde, daluren van 22:00 tot 08:00.")}</button>
                  <button type="button" data-ciclo="semanal" aria-pressed="false"><strong>Ciclo semanal</strong>${t("Doordeweeks daluren van 00:00 tot 07:00, in het weekend meer.")}</button>
                </div>
                <span class="sub">${t("Staat op je factuur. De tijden zijn die van Portugal.")}</span>
              </div>
              <div class="two">
                <div class="row" data-periodo="simples"><label for="pt-simples">${t("Prijs (€ per kWh)")}</label><input type="number" id="pt-simples" min="0" step="0.0001" inputmode="decimal"></div>
                <div class="row" data-periodo="vazio"><label for="pt-vazio">${t("Daluren, vazio (€ per kWh)")}</label><input type="number" id="pt-vazio" min="0" step="0.0001" inputmode="decimal"></div>
                <div class="row" data-periodo="fora_vazio"><label for="pt-fora">${t("Buiten de daluren, fora do vazio (€ per kWh)")}</label><input type="number" id="pt-fora" min="0" step="0.0001" inputmode="decimal"></div>
                <div class="row" data-periodo="cheias"><label for="pt-cheias">${t("Normaal, cheias (€ per kWh)")}</label><input type="number" id="pt-cheias" min="0" step="0.0001" inputmode="decimal"></div>
                <div class="row" data-periodo="ponta"><label for="pt-ponta">${t("Piek, ponta (€ per kWh)")}</label><input type="number" id="pt-ponta" min="0" step="0.0001" inputmode="decimal"></div>
              </div>
              <div class="row"><span class="sub">${t("De prijs na korting en zonder belastingen, zoals in de tabel van je contract (preço a pagar).")}</span></div>
              <div class="two">
                <div class="row">
                  <label for="pt-iva">IVA (%)</label>
                  <input type="number" id="pt-iva" min="0" max="100" step="1" inputmode="numeric">
                  <span class="sub">${t("Meestal 23%. Alleen de eerste 200 kWh per 30 dagen vallen onder 6%, en alleen bij hooguit 6,9 kVA. Wat de coach verschuift valt daarboven.")}</span>
                </div>
                <div class="row">
                  <label for="pt-iec">IEC (€ per kWh)</label>
                  <input type="number" id="pt-iec" min="0" step="0.0001" inputmode="decimal">
                  <span class="sub">${t("De belasting op elektriciteit: € 0,001 in 2026.")}</span>
                </div>
              </div>
              </div>
              <div class="block fields">
              <div class="block-title">${t("Teruglevering")}</div>
              <div class="row">
                <label>${t("Teruglevering (excedentes)")}</label>
                <div class="segmented drie" id="pt-excedente">
                  <button type="button" data-modo="nenhum" aria-pressed="false"><strong>${t("Niet verkocht")}</strong>${t("Wat je teruglevert brengt niets op.")}</button>
                  <button type="button" data-modo="fixo" aria-pressed="false"><strong>${t("Vaste prijs")}</strong>${t("Een verkoopcontract met een prijs per kWh.")}</button>
                  <button type="button" data-modo="omie" aria-pressed="false"><strong>${t("OMIE-prijs")}</strong>${t("Een deel van de marktprijs, zoals bij EDP.")}</button>
                </div>
                <span class="sub" id="pt-excedente-hint">${t("In Portugal is er geen salderen.")}</span>
              </div>
              <div class="row" id="pt-preco-rij">
                <label for="pt-preco">${t("Prijs per teruggeleverde kWh (€)")}</label>
                <input type="number" id="pt-preco" min="0" step="0.0001" inputmode="decimal">
              </div>
              <div class="two" id="pt-omie-rij">
                <div class="row">
                  <label>${t("OMIE-prijs")}</label>
                  <dac-entity-picker id="pt-omie"></dac-entity-picker>
                </div>
                <div class="row">
                  <label for="pt-fator">${t("Deel van de OMIE-prijs (%)")}</label>
                  <input type="number" id="pt-fator" min="0" max="200" step="1" inputmode="numeric">
                  <span class="sub">${t("EDP betaalt 75%.")}</span>
                </div>
              </div>
              </div>
              <div class="block fields">
              <div class="block-title">${t("Vaste kosten")}</div>
              <div class="two">
                <div class="row">
                  <label for="pt-kva">Potência contratada (kVA)</label>
                  <input type="number" id="pt-kva" min="0" step="0.01" inputmode="decimal">
                </div>
                <div class="row">
                  <label for="pt-potencia">${t("Potência (€ per dag, zonder IVA)")}</label>
                  <input type="number" id="pt-potencia" min="0" step="0.0001" inputmode="decimal">
                </div>
              </div>
              <div class="row">
                <label for="pt-servicos">${t("Diensten (€ per maand)")}</label>
                <input type="number" id="pt-servicos" min="0" step="0.0001" inputmode="decimal">
                <span class="sub">${t("Zoals EDP Smart. Vaste kosten staan er voor het overzicht; de coach stuurt er niet op.")}</span>
              </div>
              </div>
            </div>

            <!-- vast en variabel -->
            <div id="fixed-fields" class="fields" data-installateur>
              <div class="block fields">
                <div class="block-title">${t("Prijs")}</div>
                <div class="row">
                  <label for="fx-price">${t("All-in prijs (€ per kWh)")}</label>
                  <input type="number" id="fx-price" min="0" step="0.0001" inputmode="decimal">
                  <span class="sub">${t("Inclusief energiebelasting, opslag en btw, zoals op je contract.")}</span>
                </div>
              </div>
              <div class="block fields">
              <div class="block-title">${t("Teruglevering")}</div>
              <div class="row">
                <label for="fx-feedin" id="fx-feedin-label">${t("Terugleververgoeding (€ per kWh)")}</label>
                <input type="number" id="fx-feedin" min="0" step="0.0001" inputmode="decimal">
                <span class="sub">${t("Wat je krijgt voor wat je teruglevert boven je eigen verbruik.")}</span>
              </div>
              ${kostenVorm("fx")}
              <div class="row" id="fx-feedcost-rij">
                <label for="fx-feedcost" id="fx-feedcost-label">${t("Terugleverkosten (€ per kWh)")}</label>
                <input type="number" id="fx-feedcost" min="0" step="0.0001" inputmode="decimal">
                <span class="sub" id="fx-feedcost-hint">${t("Wat je leverancier per teruggeleverde kWh rekent. Rekent hij een vast bedrag per jaar in schalen, kies dat hierboven.")}</span>
              </div>
              </div>
              <!-- wat het contract na salderen zegt (v0.134.0) -->
              <div id="fx-na" class="block fields">
                <div class="block-title">${t("Vanaf 1 januari 2027")}</div>
                <p class="sub">${t("Dan stopt salderen. Vul in wat je contract voor daarna zegt; leeg is hetzelfde als hierboven.")}</p>
                <div class="two">
                  <div class="row">
                    <label for="fx-feedin-na">${t("Terugleververgoeding (€ per kWh)")}</label>
                    <input type="number" id="fx-feedin-na" min="0" step="0.0001" inputmode="decimal">
                  </div>
                  <div class="row">
                    <label for="fx-feedcost-na">${t("Terugleverkosten (€ per kWh)")}</label>
                    <input type="number" id="fx-feedcost-na" min="0" step="0.0001" inputmode="decimal">
                  </div>
                </div>
              </div>
            </div>

            <!-- dynamisch -->
            <div id="dynamic-fields" class="fields" data-installateur>
              <div class="block fields">
              <div class="block-title">${t("Prijssensoren")}</div>
              <div class="row">
                <label>${t("Hoe vaak verandert de prijs?")}</label>
                <div class="segmented" id="dynamic-interval">
                  <button type="button" data-interval="hour" aria-pressed="false">
                    <strong>${t("Per uur")}</strong>
                    ${t("Eén prijs per klokuur.")}
                  </button>
                  <button type="button" data-interval="quarter" aria-pressed="false">
                    <strong>${t("Per kwartier")}</strong>
                    ${t("Vier prijzen per uur.")}
                  </button>
                </div>
                <span class="sub">${t("De lengte van de blokken waarin de coach plant. Met kwartieren komt hij dichter bij het goedkoopste moment, als je leverancier ook zo afrekent.")}</span>
              </div>

              <div class="row">
                <label>${t("All-in prijssensor van je leverancier")}</label>
                <dac-entity-picker id="dyn-allin"></dac-entity-picker>
                <span class="sub">${t("De prijs zoals je hem betaalt. Dit is de prijs waar de coach mee rekent.")}</span>
              </div>
              <div class="row">
                <label>${t("Kale marktprijs")}</label>
                <dac-entity-picker id="dyn-market"></dac-entity-picker>
                <span class="sub">${t("Zonder belasting en btw, zoals de ingebouwde Nord Pool van Home Assistant. Hiermee rekent de coach je prijs na, weet hij wat teruglevering opbrengt, en neemt hij het over als je leverancier geen prijs geeft. Zonder all-in sensor rekent hij er je prijs mee uit.")}</span>
              </div>
              <div class="notice" id="dyn-same" hidden>
                ${icons.warning}
                <span id="dyn-same-text"></span>
              </div>
              <div class="row" id="dyn-reserve-row">
                <label>${t("Reserveprijssensor")}</label>
                <dac-entity-picker id="dyn-reserve"></dac-entity-picker>
                <span class="sub">${t("Een tweede all-in prijs voor als die van je leverancier wegvalt. Meestal niet nodig: de kale marktprijs neemt het dan al over.")}</span>
              </div>
              </div>

              <div class="block fields">
              <div class="block-title">${t("Belasting en opslag")}</div>
              <div class="two">
                <div class="row">
                  <label for="dyn-tax">${t("Energiebelasting (€ per kWh, zonder btw)")}</label>
                  <input type="number" id="dyn-tax" min="0" step="0.00001" inputmode="decimal">
                  <span class="sub" id="dyn-tax-hint"></span>
                </div>
                <div class="row">
                  <label for="dyn-vat">${t("Btw (%)")}</label>
                  <input type="number" id="dyn-vat" min="0" max="100" step="1" inputmode="numeric">
                </div>
              </div>
              <div class="row">
                <label for="dyn-markup" id="dyn-markup-label">${t("{opslag} (€ per kWh, zonder btw)", { opslag: t("Opslag van je leverancier") })}</label>
                <input type="number" id="dyn-markup" min="0" step="0.000001" inputmode="decimal">
                <span class="sub" id="dyn-markup-hint"></span>
              </div>
              </div>
              <!-- Teruglevering apart (v0.132.0): de marktprijs, of een vast bedrag
                   naast de dynamische inkoop. -->
              <div class="block fields">
              <div class="block-title">${t("Teruglevering")}</div>
              <div class="row">
                <label>${t("Vergoeding")}</label>
                <div class="segmented" id="dyn-terug">
                  <button type="button" data-terug="market" aria-pressed="false">
                    <strong>${t("Marktprijs")}</strong>
                    ${t("Per uur of kwartier, zoals de inkoop.")}
                  </button>
                  <button type="button" data-terug="fixed" aria-pressed="false">
                    <strong>${t("Vast bedrag")}</strong>
                    ${t("Een vaste vergoeding per kWh.")}
                  </button>
                </div>
                <span class="sub">${t("Zolang je saldeert telt een teruggeleverde kWh tot aan je eigen verbruik als je inkoopprijs, wat je hier ook kiest.")}</span>
              </div>
              <div class="row" id="dyn-vast-rij">
                <label for="dyn-feedfixed">${t("Vaste terugleververgoeding (€ per kWh)")}</label>
                <input type="number" id="dyn-feedfixed" min="0" step="0.0001" inputmode="decimal">
              </div>
              ${kostenVorm("dyn")}
              <div class="two">
                <div class="row" id="dyn-feedcost-rij">
                  <label for="dyn-feedcost">${t("Terugleverkosten (€ per kWh)")}</label>
                  <input type="number" id="dyn-feedcost" min="0" step="0.0001" inputmode="decimal">
                </div>
                <div class="row alleen-markt">
                  <label for="dyn-feedbonus">${t("Vergoeding bij teruglevering (€ per kWh)")}</label>
                  <input type="number" id="dyn-feedbonus" step="0.0001" inputmode="decimal">
                  <span class="sub">${t("Wat je leverancier per teruggeleverde kWh bovenop de marktprijs betaalt. Haalt hij er iets af, dan een negatief getal.")}</span>
                </div>
              </div>
              <label class="check" for="dyn-nettingfull">
                <input type="checkbox" id="dyn-nettingfull">
                <span><strong>${t("Binnen salderen de hele all-in prijs terug")}</strong> ${t("Ook de opslag. Anders rekent de coach binnen salderen met de all-in prijs min de opslag.")}</span>
              </label>
              <label class="check alleen-markt" for="dyn-feedvat">
                <input type="checkbox" id="dyn-feedvat">
                <span><strong>${t("Teruglevering met btw")}</strong> ${t("De leverancier betaalt de marktprijs voor teruglevering inclusief btw.")}</span>
              </label>
              <div class="two alleen-markt">
                <div class="row">
                  <label for="dyn-bonuspct">${t("Bonus op teruglevering (%)")}</label>
                  <input type="number" id="dyn-bonuspct" min="0" max="100" step="0.1" inputmode="decimal">
                  <span class="sub">${t("Een bonus in procenten, zoals de Zonnebonus. Leeg of 0 is geen bonus.")}</span>
                </div>
                <div class="row">
                  <label for="dyn-bonusbase">${t("Over")}</label>
                  <select id="dyn-bonusbase">
                    <option value="market">${t("de marktprijs")}</option>
                    <option value="market_plus_fee">${t("de marktprijs plus de vergoeding")}</option>
                  </select>
                </div>
              </div>
              <label class="check alleen-markt" for="dyn-bonusdag">
                <input type="checkbox" id="dyn-bonusdag">
                <span><strong>${t("Bonus alleen overdag")}</strong> ${t("Van zonsopkomst tot zonsondergang, uitgerekend voor waar het huis staat.")}</span>
              </label>
              </div>
            </div>

            <div class="block fields" id="salderen-blok" data-installateur>
            <div class="block-title">${t("Salderen")}</div>
            <label class="check" for="netting" data-installateur id="netting-rij">
              <input type="checkbox" id="netting">
              <span>
                <strong>${t("Je levert nog gesaldeerd terug")}</strong>
                ${t("Dan streept elke teruggeleverde kWh weg tegen een ingekochte, tot aan wat je zelf verbruikt, en is hij je inkoopprijs waard in plaats van je terugleververgoeding. De regeling loopt af op 1 januari 2027.")}
              </span>
            </label>
            <div class="row" id="afreken-rij" data-installateur>
              <label for="afreken-start">${t("Je afrekenperiode begon op")}</label>
              <input type="date" id="afreken-start">
              <span class="sub">${t("De dag na de einddatum op je laatste jaarafrekening. Salderen telt per afrekenperiode, ook over een nieuw contract heen. Wat je daarin meer teruglevert dan je afneemt krijgt de vergoeding.")}</span>
            </div>
            </div>

            <div class="block fields">
            <div class="block-title">${t("Zo komt je prijs tot stand")}</div>
            <div class="ob" id="opbouw"></div>
            <div class="bevestig">
              <button type="button" class="primary vrij" id="bevestig">${t("Ja, dit klopt")}</button>
              <span class="sub" id="bevestigd-zin"></span>
            </div>
            </div>

            <div class="block fields">
            <div class="block-title">${t("Eerdere stroomcontracten")}</div>
            <p class="sub">${t("Historie en rapport rekenen elke dag met de prijs van toen. Wat de coach nu doet rekent altijd met het contract hierboven.")}</p>
            <div class="nieuw" data-installateur>
              <button type="button" data-nieuw="stroom">${t("Ik heb een nieuw stroomcontract afgesloten")}</button>
              <span class="sub">${t("Zet dit contract bij de eerdere, en begin een nieuw formulier.")}</span>
            </div>
            <div id="periods-stroom"></div>
            <div class="circuit-actions" data-installateur>
              <button type="button" data-period-add="stroom">${t("Eerder stroomcontract toevoegen")}</button>
            </div>
            </div>

            <!-- de opgeslagen beurten opnieuw uitrekenen (v0.136.0) -->
            <div class="block" data-installateur id="herreken-blok">
              <label class="block-title" for="beurten-van">${t("Laadbeurten en programma's opnieuw uitrekenen")}</label>
              <span class="sub">${t("Na een gewijzigde prijs: wat de opgeslagen beurten kostten en bespaarden, opnieuw met het contract van die dag. Alleen bij een vaste of variabele prijs. Eerst zie je wat het wordt.")}</span>
              <input type="date" id="beurten-van">
              <div class="herreken-knoppen">
                <button type="button" id="beurten-bekijk">${t("Uitrekenen")}</button>
                <button type="button" id="beurten-over" hidden>${t("Overnemen")}</button>
              </div>
              <p class="sub" id="beurten-uit"></p>
            </div>
          </div>
        </section>

        <!-- ================= gas ================= -->
        <section class="card" id="gas">
          <h2>${icons.vlam} ${t("Mijn huidige gascontract")}</h2>
          <p class="hint" id="gas-samenvatting"></p>
          <!-- Gas en water uit te zetten (v0.138.0). De eigenaar op 19-10-2026: "ook onder
               contract staat gas etc maar dat heeft deze klant niet je moet het kunnen
               uitzetten." Hetzelfde vinkje als bij Installatie (sources.meters), zie slice_. -->
          <label class="check" for="gas-aan" data-installateur>
            <input type="checkbox" id="gas-aan">
            <span><strong>${t("Deze woning gebruikt gas")}</strong> ${t("Staat dit uit, dan blijft gas weg, hier en op het overzicht.")}</span>
          </label>
          <div class="fields" id="gas-velden">
            <div class="block" data-installateur>
            <div class="block-title">${t("Leverancier en looptijd")}</div>
            <div class="row">
              <label>${t("Soort contract")}</label>
              ${soortKnoppen("gas-soort")}
            </div>
            <div class="row">
              <label for="gas-lev">${t("Leverancier")}</label>
              ${levKeuze("gas-lev", "gas")}
              <span class="sub" id="gas-lev-hint">${t("Mag een andere zijn dan die van je stroom.")}</span>
            </div>
            <div class="two">
              <div class="row">
                <label for="gas-start">${t("Mijn contract is ingegaan op")}</label>
                <input type="date" id="gas-start">
              </div>
              <div class="row" id="gas-eind-rij">
                <label for="gas-end">${t("Mijn contract loopt af op")}</label>
                <input type="date" id="gas-end">
                <label for="gas-dagen" class="klein">${t("Herinner me zoveel dagen vooraf")}</label>
                <input type="number" id="gas-dagen" min="0" max="365" step="1" inputmode="numeric">
              </div>
            </div>
            </div>
            <div class="block fields" data-installateur>
            <div class="block-title">${t("Prijs")}</div>
            <div class="row" id="gas-prijs-rij" data-installateur>
              <label for="gas-price">${t("Gasprijs, all-in (€ per m³)")}</label>
              <input type="number" id="gas-price" min="0" step="0.0001" inputmode="decimal">
              <span class="sub">${t("Inclusief energiebelasting, opslag en btw.")}</span>
            </div>
            <div class="row" id="gas-sensor-rij" data-installateur>
              <label>${t("Sensor met de all-in gasprijs")}</label>
              <dac-entity-picker id="gas-entity"></dac-entity-picker>
              <span class="sub" id="gas-sensor-hint">${t("Een dynamische gasprijs verandert per dag. Historie neemt de prijs van elke dag uit deze sensor.")}</span>
            </div>
            </div>
            <div class="block fields">
            <div class="block-title">${t("Eerdere gascontracten")}</div>
            <div class="nieuw" data-installateur>
              <button type="button" data-nieuw="gas">${t("Ik heb een nieuw gascontract afgesloten")}</button>
            </div>
            <div id="periods-gas"></div>
            <div class="circuit-actions" data-installateur>
              <button type="button" data-period-add="gas">${t("Eerder gascontract toevoegen")}</button>
            </div>
            </div>
          </div>
        </section>

        <!-- ================= water ================= -->
        <section class="card" id="water">
          <h2>${icons.druppel} ${t("Mijn huidige waterprijs")}</h2>
          <p class="hint" id="water-samenvatting"></p>
          <label class="check" for="water-aan" data-installateur>
            <input type="checkbox" id="water-aan">
            <span><strong>${t("Deze woning heeft een watermeter in Home Assistant")}</strong> ${t("Staat dit uit, dan blijft water weg, hier en op het overzicht.")}</span>
          </label>
          <div class="fields" id="water-velden">
            <div class="block" data-installateur>
            <div class="block-title">${t("Prijs")}</div>
            <div class="row">
              <label for="water-lev">${t("Waterbedrijf")}</label>
              <input type="text" id="water-lev" maxlength="60" placeholder="${t("Bijvoorbeeld Vitens")}">
            </div>
            <div class="row" data-installateur>
              <label for="water-price">${t("Waterprijs, all-in (€ per m³)")}</label>
              <input type="number" id="water-price" min="0" step="0.0001" inputmode="decimal">
              <span class="sub">${t("Inclusief belasting.")}</span>
            </div>
            </div>
            <div class="block fields">
            <div class="block-title">${t("Eerdere waterprijzen")}</div>
            <div id="periods-water"></div>
            <div class="circuit-actions" data-installateur>
              <button type="button" data-period-add="water">${t("Eerdere waterprijs toevoegen")}</button>
            </div>
            </div>
          </div>
        </section>
      </div>

      ${saveBarHtml}
    `;
  }

  afterRender() {
    const c = () => this.draft_.contract;
    const bind = (id, apply) => {
      const el = this.$(`#${id}`);
      el.addEventListener("input", () => {
        apply(el.type === "checkbox" ? el.checked : el.value);
        this.wijziging_();
      });
      if (el.type === "checkbox" || el.tagName === "SELECT") {
        el.addEventListener("change", () => {
          apply(el.type === "checkbox" ? el.checked : el.value);
          this.wijziging_();
        });
      }
    };
    const getal = (v) => (v === "" ? 0 : Number(v) || 0);
    // Leeg is iets anders dan nul: hetzelfde als ervoor (v0.134.0).
    const leegOfGetal = (v) => (v === "" ? null : Number(v) || 0);

    bind("stroom-start", (v) => (c().start = v));
    bind("stroom-end", (v) => (c().end = v));
    bind("stroom-dagen", (v) => (c().reminder_days = v === "" ? 30 : Math.max(0, Math.round(Number(v) || 0))));
    bind("gas-dagen", (v) => (this.gas_().reminder_days = v === "" ? 30 : Math.max(0, Math.round(Number(v) || 0))));
    bind("fx-price", (v) => (c().fixed.all_in_price = getal(v)));
    bind("fx-feedin", (v) => (c().fixed.feed_in_tariff = getal(v)));
    bind("fx-feedcost", (v) => (c().fixed.feed_in_costs = getal(v)));
    bind("fx-feedin-na", (v) => (c().fixed.feed_in_tariff_after = leegOfGetal(v)));
    bind("fx-feedcost-na", (v) => (c().fixed.feed_in_costs_after = leegOfGetal(v)));
    bind("afreken-start", (v) => (c().billing_start = v));
    // Portugal (v0.137.0).
    const pt = () => {
      const deel = (c().pt ??= {});
      deel.energia ??= {};
      deel.excedente ??= {};
      return deel;
    };
    bind("pt-lev", (v) => (pt().fornecedor = v));
    for (const [id, sleutel] of [["pt-simples", "simples"], ["pt-vazio", "vazio"], ["pt-fora", "fora_vazio"], ["pt-cheias", "cheias"], ["pt-ponta", "ponta"]]) {
      bind(id, (v) => (pt().energia[sleutel] = getal(v)));
    }
    bind("pt-iva", (v) => (pt().iva = v === "" ? 23 : getal(v)));
    bind("pt-iec", (v) => (pt().iec = getal(v)));
    bind("pt-preco", (v) => (pt().excedente.preco = getal(v)));
    bind("pt-fator", (v) => (pt().excedente.fator = getal(v)));
    bind("pt-kva", (v) => (pt().kva = getal(v)));
    bind("pt-potencia", (v) => (pt().potencia_dia = getal(v)));
    bind("pt-servicos", (v) => (pt().servicos_mes = getal(v)));
    for (const [id, sleutel] of [["gas-aan", "gas_enabled"], ["water-aan", "water_enabled"]]) {
      this.$(`#${id}`).addEventListener("change", (ev) => {
        ((this.draft_.sources ??= {}).meters ??= {})[sleutel] = ev.target.checked;
        this.wijziging_();
        this.paint_();
      });
    }
    this.$("#land").addEventListener("change", (ev) => {
      c().country = ev.target.value;
      // Een Portugees contract is een vaste prijs per tijdvak, zonder salderen.
      if (ev.target.value === "PT") { c().type = "fixed"; c().netting = false; }
      this.wijziging_();
      this.paint_();
    });
    for (const [lijst, zet] of [
      ["#pt-tarifa button", (b) => (pt().tarifa = b.dataset.tarifa)],
      ["#pt-ciclo button", (b) => (pt().ciclo = b.dataset.ciclo)],
      ["#pt-excedente button", (b) => (pt().excedente.modo = b.dataset.modo)],
    ]) {
      for (const knop of this.$$(lijst)) knop.addEventListener("click", () => { zet(knop); this.wijziging_(); this.paint_(); });
    }
    const omie = this.$("#pt-omie");
    omie.filter = "price";
    omie.placeholder = t("Zoek een OMIE-prijssensor…");
    omie.addEventListener("dac-entity-change", (ev) => { pt().excedente.omie_entity = ev.detail.value; this.wijziging_(); });
    bind("dyn-tax", (v) => (c().dynamic.energy_tax = getal(v)));
    bind("dyn-markup", (v) => (c().dynamic.supplier_markup = getal(v)));
    bind("dyn-vat", (v) => (c().dynamic.vat_percent = getal(v)));
    bind("dyn-feedcost", (v) => (c().dynamic.feed_in_costs = getal(v)));
    // De vorm van de terugleverkosten en de schalen (v0.135.0), bij vast en bij dynamisch.
    const velden = (prefix) => (prefix === "fx" ? c().fixed : c().dynamic);
    for (const keuze of this.$$("[data-kostvorm]")) {
      keuze.addEventListener("change", () => {
        velden(keuze.dataset.kostvorm).feed_in_costs_mode = keuze.value;
        this.paintSchalen_(keuze.dataset.kostvorm);
        this.wijziging_();
      });
    }
    for (const veld of this.$$("[data-schalen-tot]")) {
      veld.addEventListener("input", () => {
        velden(veld.dataset.schalenTot).feed_in_scales_until = veld.value || "";
        this.wijziging_();
      });
    }
    for (const knop of this.$$("[data-schaal-erbij]")) {
      knop.addEventListener("click", () => {
        const v = velden(knop.dataset.schaalErbij);
        const rijen = (v.feed_in_scales ??= []);
        const laatste = rijen[rijen.length - 1];
        rijen.push({ vanaf: laatste ? (Number(laatste.vanaf) || 0) + 250 : 0, per_jaar: 0 });
        this.paintSchalen_(knop.dataset.schaalErbij);
        this.wijziging_();
      });
    }
    bind("dyn-feedbonus", (v) => (c().dynamic.feed_in_bonus = getal(v)));
    bind("dyn-feedvat", (v) => (c().dynamic.feed_in_vat = Boolean(v)));
    bind("dyn-nettingfull", (v) => (c().dynamic.netting_full = Boolean(v)));
    bind("dyn-bonuspct", (v) => (c().dynamic.feed_in_bonus_percent = getal(v)));
    bind("dyn-bonusbase", (v) => (c().dynamic.bonus_base = v));
    bind("dyn-bonusdag", (v) => (c().dynamic.bonus_daytime = Boolean(v)));
    bind("dyn-feedfixed", (v) => (c().dynamic.feed_in_fixed = getal(v)));
    bind("netting", (v) => (c().netting = Boolean(v)));
    bind("gas-start", (v) => (this.gas_().start = v));
    bind("gas-end", (v) => (this.gas_().end = v));
    bind("gas-price", (v) => (this.gas_().price = getal(v)));
    bind("water-price", (v) => (this.water_().price = getal(v)));
    bind("water-lev", (v) => (this.water_().supplier = v));

    this.$("#stroom-lev").addEventListener("change", (ev) => this.kiesLeverancier_("stroom", ev.target.value));
    this.$("#gas-lev").addEventListener("change", (ev) => this.kiesLeverancier_("gas", ev.target.value));

    for (const [id, zet] of [["stroom-soort", (s) => (c().type = s)], ["gas-soort", (s) => (this.gas_().type = s)]]) {
      for (const button of this.$$(`#${id} button`)) {
        button.addEventListener("click", () => {
          zet(button.dataset.soort);
          this.wijziging_();
        });
      }
    }
    for (const button of this.$$("#dynamic-interval button")) {
      button.addEventListener("click", () => {
        c().dynamic.interval = button.dataset.interval;
        this.wijziging_();
      });
    }
    for (const button of this.$$("#dyn-terug button")) {
      button.addEventListener("click", () => {
        c().dynamic.feed_in_mode = button.dataset.terug;
        this.wijziging_();
      });
    }

    for (const [id, key] of [["dyn-allin", "all_in_entity"], ["dyn-market", "market_entity"], ["dyn-reserve", "fallback_entity"]]) {
      const picker = this.$(`#${id}`);
      picker.filter = "price";
      picker.placeholder = t("Zoek een prijssensor…");
      picker.addEventListener("dac-entity-change", (ev) => {
        const d = c().dynamic;
        d[key] = ev.detail.value;
        // Met een all-in sensor is die de prijs; zonder bouwt de coach hem op
        // uit de kale marktprijs (v0.129.0: geen aparte keuze meer).
        d.source = d.all_in_entity ? "all_in" : "market";
        if (key === "fallback_entity" && ev.detail.value) d.fallback_source = "all_in";
        this.wijziging_();
      });
    }
    const gasPicker = this.$("#gas-entity");
    gasPicker.filter = "price";
    gasPicker.placeholder = t("Zoek een gasprijssensor…");
    gasPicker.addEventListener("dac-entity-change", (ev) => {
      this.gas_().entity = ev.detail.value;
      this.wijziging_();
    });

    for (const knop of this.$$("[data-period-add]")) {
      knop.addEventListener("click", () => {
        const bron = knop.dataset.periodAdd;
        const lijst = this.periodsVan_(bron);
        lijst.push(bron === "stroom"
          ? { name: "", from: "", to: "", type: "fixed", supplier: "", all_in_price: 0, feed_in_tariff: 0 }
          : { name: "", from: "", to: "", price: 0 });
        this.openPeriode_ = `${bron}:${lijst.length - 1}`;
        this.paintPeriods_(bron);
        this.afterChange_();
      });
    }
    for (const knop of this.$$("[data-nieuw]")) {
      knop.addEventListener("click", () => this.nieuwContract_(knop.dataset.nieuw));
    }
    this.$("#bevestig").addEventListener("click", () => this.bevestig_());
    this.$("#beurten-van").addEventListener("input", (ev) => { this.beurten_ = { van: ev.target.value }; this.paintBeurten_(); });
    this.$("#beurten-bekijk").addEventListener("click", () => this.herrekenBeurten_(false));
    this.$("#beurten-over").addEventListener("click", () => this.herrekenBeurten_(true));

    this.wireSaveBar_();
    this.paint_();
  }

  gas_() {
    const contract = this.draft_.contract;
    contract.gas ??= { type: "fixed", supplier: "", price: 0, entity: "", start: "", end: "", periods: [] };
    return contract.gas;
  }

  water_() {
    const contract = this.draft_.contract;
    contract.water ??= { price: 0, periods: [] };
    return contract.water;
  }

  periodsVan_(bron) {
    if (bron === "stroom") {
      const contract = this.draft_.contract;
      if (!Array.isArray(contract.periods)) contract.periods = [];
      return contract.periods;
    }
    const deel = bron === "gas" ? this.gas_() : this.water_();
    if (!Array.isArray(deel.periods)) deel.periods = [];
    return deel.periods;
  }

  /** Na elke wijziging: tekenen, de opslagbalk, en de controle opnieuw vragen. */
  wijziging_() {
    this.paintContract_();
    this.afterChange_();
    this.vraagControle_();
  }

  afterChange_() {
    this.syncSaveBar_();
  }

  /**
   * Een leverancier kiezen vult de velden voor (v0.129.0). Wat er staat wordt
   * overschreven door wat de catalogus van die leverancier weet; wat hij niet
   * weet blijft staan. Bij een dynamisch contract zoekt hij ook de sensoren op.
   */
  kiesLeverancier_(bron, id) {
    const deel = bron === "stroom" ? this.draft_.contract : this.gas_();
    deel.supplier = id;
    const l = leverancier(id);
    if (l) {
      // De soort blijft wat de klant koos: de catalogus kan een soort missen, en
      // dan zou hij een goede keuze overschrijven. Heeft de leverancier die soort
      // niet in de lijst, dan zegt de hint dat.
      const v = voorstel(id, deel.type, bron);
      if (v && bron === "stroom") {
        const doel = deel.type === "dynamic" ? deel.dynamic : deel.fixed;
        Object.assign(doel, v.velden);
        if (deel.type === "dynamic" && v.interval) deel.dynamic.interval = v.interval;
      }
      if (v && bron === "gas" && v.velden?.price !== undefined) deel.price = v.velden.price;
      const staten = this.hass_?.states;
      if (bron === "stroom" && deel.type === "dynamic") {
        const d = deel.dynamic;
        d.all_in_entity = d.all_in_entity || sensorVan(id, staten, "stroom") || "";
        d.market_entity = d.market_entity && d.market_entity !== d.all_in_entity ? d.market_entity : (nordPoolVan(staten) || "");
        d.source = d.all_in_entity ? "all_in" : "market";
      }
      if (bron === "gas" && deel.type === "dynamic") {
        deel.entity = deel.entity || sensorVan(id, staten, "gas") || "";
      }
    }
    this.paint_();
    this.afterChange_();
    this.vraagControle_();
  }

  /**
   * "Ik heb een nieuw contract afgesloten": het huidige contract bij de eerdere,
   * van de ingangsdatum tot gisteren, en een leeg formulier dat vandaag ingaat.
   * De bewoner van de eerste woning op 18-10-2026: "waarmee je het huidige
   * contract automatisch archiveert en er een nieuw (leeg) formulier komt voor
   * het nieuwe contract."
   */
  nieuwContract_(bron) {
    const nu = new Date();
    const gisteren = new Date(nu.getTime() - 86400000);
    const contract = this.draft_.contract;
    if (bron === "stroom") {
      const vast = contract.type !== "dynamic";
      this.periodsVan_("stroom").unshift({
        name: voorgesteldeNaam("stroom", contract.supplier, contract.type, contract.start, dagTekst(gisteren)),
        from: contract.start || "",
        to: dagTekst(gisteren),
        type: contract.type || "fixed",
        supplier: contract.supplier || "",
        all_in_price: vast ? Number(contract.fixed?.all_in_price) || 0 : 0,
        feed_in_tariff: vast ? Number(contract.fixed?.feed_in_tariff) || 0 : 0,
      });
      contract.supplier = "";
      contract.start = dagTekst(nu);
      contract.end = "";
      // De afrekenperiode blijft: die loopt over een nieuw contract heen (v0.134.0).
      contract.fixed = { ...contract.fixed, all_in_price: 0, feed_in_tariff: 0, feed_in_costs: 0,
        feed_in_tariff_after: null, feed_in_costs_after: null,
        feed_in_costs_mode: "kwh", feed_in_scales: [], feed_in_scales_until: "" };
      contract.dynamic = { ...contract.dynamic, supplier_markup: 0, feed_in_costs: 0, feed_in_bonus: 0,
        feed_in_bonus_percent: 0, bonus_daytime: false, feed_in_vat: false,
        feed_in_costs_mode: "kwh", feed_in_scales: [], feed_in_scales_until: "" };
    } else if (bron === "gas") {
      const gas = this.gas_();
      this.periodsVan_("gas").unshift({
        name: voorgesteldeNaam("gas", gas.supplier, gas.type, gas.start, dagTekst(gisteren)),
        from: gas.start || "", to: dagTekst(gisteren), price: Number(gas.price) || 0,
      });
      Object.assign(gas, { supplier: "", start: dagTekst(nu), end: "", price: 0 });
    }
    this.paint_();
    this.afterChange_();
    this.vraagControle_();
  }

  /** De opbouw opnieuw laten uitrekenen door de coach, met het concept erbij. */
  vraagControle_() {
    clearTimeout(this.checkTimer_);
    this.checkTimer_ = setTimeout(() => this.haalControle_(), 350);
  }

  async haalControle_() {
    if (!this.hass_?.callWS || !this.draft_) return;
    const run = ++this.checkRun_;
    try {
      const vraag = { type: "domotiapp_coach/contract/check" };
      if (this.canEdit_()) vraag.contract = this.draft_.contract;
      const antwoord = await this.hass_.callWS(vraag);
      if (run !== this.checkRun_) return;
      this.check_ = antwoord;
    } catch (error) {
      if (run !== this.checkRun_) return;
      this.check_ = null;
      console.warn("[DomotiApp Coach] de opbouw kon niet worden opgehaald", error);
    }
    this.paintOpbouw_();
  }

  /** "Ja, dit klopt": eerst opslaan wat er veranderde, dan bevestigen. */
  async bevestig_() {
    if (!this.hass_?.callWS) return;
    if (this.dirty_()) {
      await this.save_();
      if (this.dirty_()) return;
    }
    try {
      const settings = await this.hass_.callWS({ type: "domotiapp_coach/contract/confirm" });
      this.saved_ = JSON.parse(JSON.stringify(settings));
      this.draft_ = JSON.parse(JSON.stringify(settings));
      this.fire("dac-settings-saved", { settings });
      this.toast_(t("Bevestigd"), true);
    } catch (error) {
      this.toast_(t("Bevestigen mislukt: {fout}", { fout: error?.message ?? error }), false);
    }
    this.paint_();
    this.vraagControle_();
  }

  /**
   * De opgeslagen beurten opnieuw uitrekenen (v0.136.0): eerst laten zien,
   * dan overnemen. De coach rekent met het opgeslagen contract, dus wat hier
   * nog niet is opgeslagen gaat eerst.
   */
  async herrekenBeurten_(toepassen) {
    if (!this.hass_?.callWS) return;
    const stand = this.beurten_ ?? {};
    if (!stand.van) {
      this.toast_(t("Kies eerst een dag."), false);
      return;
    }
    if (this.dirty_()) {
      await this.save_();
      if (this.dirty_()) return;
    }
    this.beurten_ = { ...stand, bezig: true };
    this.paintBeurten_();
    try {
      const uit = await this.hass_.callWS({ type: "domotiapp_coach/savings/recalculate", from: stand.van, apply: toepassen });
      this.beurten_ = { van: stand.van, uit };
      if (uit?.toegepast) this.toast_(t("De beurten zijn opnieuw uitgerekend"), true);
    } catch (error) {
      this.beurten_ = { van: stand.van, uit: { fout: t("Uitrekenen mislukt: {fout}", { fout: error?.message ?? error }) } };
    }
    this.paintBeurten_();
  }

  paintBeurten_() {
    if (!this.rendered_) return;
    const stand = this.beurten_ ?? {};
    const knop = this.$("#beurten-bekijk");
    knop.disabled = Boolean(stand.bezig);
    knop.textContent = stand.bezig ? t("Bezig…") : t("Uitrekenen");
    this.$("#beurten-over").hidden = !(stand.uit && !stand.uit.fout && !stand.uit.toegepast && stand.uit.beurten > 0);
    this.$("#beurten-uit").textContent = stand.uit ? beurtenZin(stand.uit) : "";
  }

  afterSave_() {
    this.vraagControle_();
  }

  /** Wie het scherm bekijkt kan veranderen; de eerdere contracten tekenen dan opnieuw. */
  applyPermissions_() {
    super.applyPermissions_();
    if (this.draft_) for (const bron of ["stroom", "gas", "water"]) this.paintPeriods_(bron);
  }

  paint_() {
    if (!this.draft_ || !this.rendered_) return;
    for (const d of [this.draft_, this.saved_]) if (d?.contract) d.contract.periods ??= [];
    const contract = this.draft_.contract;
    contract.dynamic ??= {};
    contract.fixed ??= {};

    this.$("#stroom-lev").value = leverancier(contract.supplier) ? contract.supplier : "";
    this.$("#stroom-start").value = contract.start || "";
    this.$("#stroom-end").value = contract.end || "";
    this.$("#stroom-dagen").value = contract.reminder_days ?? 30;
    this.$("#netting").checked = Boolean(contract.netting);
    this.$("#fx-price").value = contract.fixed.all_in_price || "";
    this.$("#fx-feedin").value = contract.fixed.feed_in_tariff || "";
    this.$("#fx-feedcost").value = contract.fixed.feed_in_costs || "";
    this.$("#fx-feedin-na").value = contract.fixed.feed_in_tariff_after ?? "";
    this.$("#fx-feedcost-na").value = contract.fixed.feed_in_costs_after ?? "";
    this.$("#afreken-start").value = contract.billing_start || "";
    const p = contract.pt ?? {};
    const e = p.energia ?? {};
    this.$("#pt-lev").value = p.fornecedor ?? "";
    this.$("#pt-simples").value = e.simples || "";
    this.$("#pt-vazio").value = e.vazio || "";
    this.$("#pt-fora").value = e.fora_vazio || "";
    this.$("#pt-cheias").value = e.cheias || "";
    this.$("#pt-ponta").value = e.ponta || "";
    this.$("#pt-iva").value = p.iva ?? 23;
    this.$("#pt-iec").value = p.iec ?? 0.001;
    this.$("#pt-preco").value = p.excedente?.preco || "";
    this.$("#pt-fator").value = p.excedente?.fator ?? 75;
    this.$("#pt-omie").value = p.excedente?.omie_entity ?? "";
    this.$("#pt-kva").value = p.kva || "";
    this.$("#pt-potencia").value = p.potencia_dia || "";
    this.$("#pt-servicos").value = p.servicos_mes || "";
    const d = contract.dynamic;
    this.$("#dyn-allin").value = d.source === "all_in" ? d.all_in_entity ?? "" : (d.all_in_entity ?? "");
    this.$("#dyn-market").value = d.market_entity ?? "";
    this.$("#dyn-reserve").value = d.fallback_entity ?? "";
    this.$("#dyn-tax").value = d.energy_tax ?? "";
    this.$("#dyn-markup").value = d.supplier_markup ?? "";
    this.$("#dyn-vat").value = d.vat_percent ?? "";
    this.$("#dyn-feedcost").value = d.feed_in_costs ?? "";
    this.paintSchalen_("fx");
    this.paintSchalen_("dyn");
    this.$("#dyn-feedbonus").value = d.feed_in_bonus ?? "";
    this.$("#dyn-feedvat").checked = Boolean(d.feed_in_vat);
    this.$("#dyn-nettingfull").checked = Boolean(d.netting_full);
    this.$("#dyn-bonuspct").value = d.feed_in_bonus_percent || "";
    this.$("#dyn-bonusbase").value = d.bonus_base === "market_plus_fee" ? "market_plus_fee" : "market";
    this.$("#dyn-bonusdag").checked = Boolean(d.bonus_daytime);
    this.$("#dyn-feedfixed").value = d.feed_in_fixed || "";

    const gas = this.gas_();
    this.$("#gas-lev").value = leverancier(gas.supplier) ? gas.supplier : "";
    this.$("#gas-start").value = gas.start || "";
    this.$("#gas-end").value = gas.end || "";
    this.$("#gas-dagen").value = gas.reminder_days ?? 30;
    this.$("#gas-price").value = gas.price || "";
    this.$("#gas-entity").value = gas.entity || "";
    this.$("#water-price").value = this.water_().price || "";
    this.$("#water-lev").value = this.water_().supplier || "";

    this.paintContract_();
    for (const bron of ["stroom", "gas", "water"]) this.paintPeriods_(bron);
    this.paintOpbouw_();
    if (!this.check_) this.vraagControle_();
  }

  /** Wat er zichtbaar is hangt af van de soort, en de hints van de leverancier. */
  paintContract_() {
    const contract = this.draft_.contract;
    const d = contract.dynamic ?? {};
    const dynamic = contract.type === "dynamic";
    const vast = contract.type === "fixed";

    for (const button of this.$$("#stroom-soort button")) {
      button.setAttribute("aria-pressed", String(button.dataset.soort === (contract.type || "fixed")));
    }
    this.$("#fixed-fields").style.display = dynamic ? "none" : "";
    this.$("#dynamic-fields").style.display = dynamic ? "" : "none";
    this.$("#stroom-eind-rij").style.display = vast ? "" : "none";
    // Twee terugleverprijzen als het contract over 1 januari 2027 heen loopt (v0.134.0).
    const naSalderen = (!contract.start || contract.start < SALDEREN_TOT)
      && (!vast || !contract.end || contract.end >= SALDEREN_TOT);
    this.$("#fx-na").style.display = naSalderen ? "" : "none";
    this.$("#fx-feedin-label").textContent = naSalderen
      ? t("Terugleververgoeding tot 1 januari 2027 (€ per kWh)") : t("Terugleververgoeding (€ per kWh)");
    this.$("#fx-feedcost-label").textContent = naSalderen
      ? t("Terugleverkosten tot 1 januari 2027 (€ per kWh)") : t("Terugleverkosten (€ per kWh)");
    this.$("#afreken-rij").style.display = contract.netting && dagTekst(new Date()) < SALDEREN_TOT ? "" : "none";

    // Portugal (v0.137.0): de velden van het land, en de Nederlandse weg.
    const portugal = contract.country === "PT";
    this.$("#land").value = portugal ? "PT" : "NL";
    this.$("#land-hint").textContent = portugal
      ? t("Een prijs per tijdvak, zonder salderen.")
      : t("Een all-in prijs of een dynamisch contract, salderen tot 2027.");
    this.$("#pt-fields").style.display = portugal ? "" : "none";
    this.$("#pt-lev-rij").style.display = portugal ? "" : "none";
    if (portugal) {
      for (const id of ["#soort-rij", "#lev-rij", "#fixed-fields", "#dynamic-fields", "#salderen-blok", "#afreken-rij", "#fx-na"]) {
        this.$(id).style.display = "none";
      }
      const p = contract.pt ?? {};
      const tarifa = p.tarifa ?? "bi";
      for (const knop of this.$$("#pt-tarifa button")) knop.setAttribute("aria-pressed", String(knop.dataset.tarifa === tarifa));
      for (const knop of this.$$("#pt-ciclo button")) knop.setAttribute("aria-pressed", String(knop.dataset.ciclo === (p.ciclo ?? "diario")));
      const modo = p.excedente?.modo ?? "onbekend";
      this.$("#pt-excedente-hint").textContent = modo === "onbekend"
        ? t("Nog niet gekozen: dan weet de coach niet wat teruglevering opbrengt. In Portugal is er geen salderen.")
        : t("In Portugal is er geen salderen.");
      for (const knop of this.$$("#pt-excedente button")) knop.setAttribute("aria-pressed", String(knop.dataset.modo === modo));
      this.$("#pt-ciclo-rij").style.display = tarifa === "simples" ? "none" : "";
      const zichtbaar = { simples: ["simples"], bi: ["vazio", "fora_vazio"], tri: ["vazio", "cheias", "ponta"] }[tarifa] ?? [];
      for (const rij of this.$$("[data-periodo]")) rij.style.display = zichtbaar.includes(rij.dataset.periodo) ? "" : "none";
      this.$("#pt-preco-rij").style.display = modo === "fixo" ? "" : "none";
      this.$("#pt-omie-rij").style.display = modo === "omie" ? "" : "none";
    } else {
      this.$("#soort-rij").style.display = "";
      this.$("#lev-rij").style.display = "";
      // Salderen zolang het nog iets doet (v0.186.0, `salderenTelt`).
      this.$("#salderen-blok").style.display = salderenTelt(contract, dagTekst(new Date())) ? "" : "none";
    }
    // Opnieuw uitrekenen alleen met beurten, en niet bij dynamisch in Nederland (v0.186.0).
    this.$("#herreken-blok").style.display = herrekenenKan(this.draft_) ? "" : "none";
    for (const button of this.$$("#dynamic-interval button")) {
      button.setAttribute("aria-pressed", String(button.dataset.interval === (d.interval ?? "hour")));
    }
    this.$("#dyn-reserve-row").style.display = d.fallback_entity ? "" : "none";
    // Teruglevering tegen de marktprijs of een vast bedrag (v0.132.0).
    const terugVast = d.feed_in_mode === "fixed";
    for (const button of this.$$("#dyn-terug button")) {
      button.setAttribute("aria-pressed", String(button.dataset.terug === (terugVast ? "fixed" : "market")));
    }
    this.$("#dyn-vast-rij").style.display = terugVast ? "" : "none";
    for (const el of this.$$(".alleen-markt")) el.style.display = terugVast ? "none" : "";

    // De samenvatting bovenaan: wat voor contract, bij wie, sinds wanneer, tot wanneer.
    const l = leverancier(contract.supplier);
    const soort = hoofd(soortNaam(contract.type));
    const delen = [l ? t("{soort} contract bij {naam}", { soort, naam: l.naam }) : t("{soort} contract", { soort })];
    if (contract.start) delen.push(t("ingegaan op {datum}", { datum: datumLang(contract.start) }));
    if (vast && contract.end) delen.push(t("loopt af op {datum}", { datum: datumLang(contract.end) }));
    if (contract.country === "PT") {
      const p = contract.pt ?? {};
      // De opção horária in het Portugees, zoals op de factuur.
      const tarifa = { simples: "simples", bi: "bi-horário", tri: "tri-horário" }[p.tarifa ?? "bi"];
      delen[0] = p.fornecedor ? t("Portugal, {tarifa} bij {naam}", { tarifa, naam: p.fornecedor }) : `Portugal, ${tarifa}`;
    }
    this.$("#stroom-samenvatting").textContent = `${delen.join(", ")}.`;

    // Waar het voorstel vandaan kwam. De uitleg zelf komt uit de catalogus (leveranciers.js).
    const v = l ? voorstel(l.id, contract.type, "stroom") : null;
    const hint = this.$("#stroom-lev-hint");
    if (l && v) {
      hint.innerHTML = `${esc(v.uitleg)}${v.terug ? ` ${esc(v.terug)}` : ""} ${t("Ingevuld uit de gegevens van {naam}, nagekeken op {datum}", { naam: esc(l.naam), datum: esc(datumLang(v.peildatum)) })}${
        v.bronnen.length ? ` (<a href="${esc(v.bronnen[0])}" target="_blank" rel="noopener">${t("bron")}</a>)` : ""}. ${t("Kijk ze na en bevestig onderaan.")}${
        v.onzeker.length ? ` <strong>${t("Niet zeker:")}</strong> ${v.onzeker.map(esc).join(" ")}` : ""}`;
    } else if (l) {
      hint.textContent = t("{naam} heeft geen {soort} stroomcontract in de lijst. Vul de bedragen van je contract zelf in.",
        { naam: l.naam, soort: t(SOORT_NAAM[contract.type] ?? "") });
    } else {
      hint.textContent = t("Staat je leverancier er niet tussen? Vul de bedragen van je contract zelf in.");
    }

    const namen = namenVan(contract.supplier, contract.type);
    this.$("#dyn-markup-label").textContent = t("{opslag} (€ per kWh, zonder btw)", { opslag: namen.opslag || t("Opslag van je leverancier") });
    const markup = Number(d.supplier_markup) || 0;
    const vat = Number(d.vat_percent) || 0;
    this.$("#dyn-markup-hint").textContent = markup
      ? t("Met btw {bedrag} per kWh. Bij salderen komt dit bedrag niet terug: het hangt aan wat je afneemt.", {
        bedrag: `€ ${(markup * (1 + vat / 100)).toLocaleString(locale(), { minimumFractionDigits: 4, maximumFractionDigits: 4 })}` })
      : t("Wat je leverancier per kWh bovenop de marktprijs rekent, zonder btw.");
    const jaar = new Date().getFullYear();
    const eb = belastingStroom(jaar);
    this.$("#dyn-tax-hint").textContent = eb !== null
      ? t("In {jaar} {bedrag} zonder btw. Verandert elk jaar op 1 januari.", { jaar, bedrag: `€ ${eb.toLocaleString(locale(), { minimumFractionDigits: 5 })}` })
      : t("Verandert elk jaar op 1 januari; kijk het na op je jaarnota.");

    // Dezelfde sensor twee keer laat de coach het marktveld leeg (`_prices` in
    // coach.py), en tot v0.128.2 stond dat alleen in de kleine letters erboven.
    // In de eerste woning op 18-10-2026 stond hij zo, met salderen uit, en
    // handelde de batterij nooit.
    const zelfde = Boolean(d.market_entity) && d.market_entity === d.all_in_entity;
    this.$("#dyn-same").hidden = !zelfde;
    this.$("#dyn-same-text").textContent = !zelfde ? "" : salderen(contract, new Date())
      ? t("Dit is dezelfde sensor als de all-in prijs, en die telt niet als marktprijs. Zolang je saldeert rekent de coach de terugleverprijs uit de all-in prijs; daarna heeft hij een kale marktprijs nodig, zoals de ingebouwde Nord Pool.")
      : t("Dit is dezelfde sensor als de all-in prijs, en die telt niet als marktprijs. Zo kent de coach je terugleverprijs niet, en kan een thuisbatterij niet handelen. Kies een kale marktprijs, zoals de ingebouwde Nord Pool.");

    // Gas.
    const gas = this.gas_();
    const gasType = gas.type || "fixed";
    for (const button of this.$$("#gas-soort button")) {
      button.setAttribute("aria-pressed", String(button.dataset.soort === gasType));
    }
    this.$("#gas-eind-rij").style.display = gasType === "fixed" ? "" : "none";
    this.$("#gas-prijs-rij").style.display = gasType === "dynamic" ? "none" : "";
    this.$("#gas-sensor-rij").style.display = gasType === "dynamic" ? "" : "none";
    const gl = leverancier(gas.supplier);
    const gsoort = hoofd(soortNaam(gasType));
    const gdelen = [gl ? t("{soort} contract bij {naam}", { soort: gsoort, naam: gl.naam }) : t("{soort} contract", { soort: gsoort })];
    if (gas.start) gdelen.push(t("ingegaan op {datum}", { datum: datumLang(gas.start) }));
    if (gasType === "fixed" && gas.end) gdelen.push(t("loopt af op {datum}", { datum: datumLang(gas.end) }));
    if (gasType !== "dynamic" && Number(gas.price) > 0) gdelen.push(`${euroTekst(gas.price)} per m³`);
    // Geen gas of geen watermeter (v0.138.0): dan alleen het vinkje en een zin.
    const meters = this.draft_.sources?.meters ?? {};
    this.$("#gas-aan").checked = Boolean(meters.gas_enabled);
    this.$("#water-aan").checked = Boolean(meters.water_enabled);
    this.$("#gas-velden").style.display = meters.gas_enabled ? "" : "none";
    this.$("#water-velden").style.display = meters.water_enabled ? "" : "none";
    // Zonder gas of watermeter de hele kaart weg (v0.186.0); het vinkje staat ook onder
    // Installatie, bij Meterstanden. Tot dan stond er "Geen gas." en "Geen watermeter.".
    this.$("#gas").style.display = meters.gas_enabled ? "" : "none";
    this.$("#water").style.display = meters.water_enabled ? "" : "none";
    this.$("#gas-samenvatting").textContent = meters.gas_enabled ? `${gdelen.join(", ")}.` : t("Geen gas.");
    // Water (v0.130.1): het waterbedrijf en de prijs in een zin, voor wie de
    // velden niet ziet.
    const water = this.water_();
    const wdelen = [water.supplier ? t("Bij {naam}", { naam: water.supplier }) : "", Number(water.price) > 0 ? `${euroTekst(water.price)} per m³` : ""].filter(Boolean);
    this.$("#water-samenvatting").textContent = !meters.water_enabled ? t("Geen watermeter.")
      : wdelen.length ? `${wdelen.join(", ")}.` : t("Nog geen waterprijs ingevuld.");
    const gv = gl ? voorstel(gl.id, gasType, "gas") : null;
    this.$("#gas-lev-hint").textContent = gv
      ? `${gv.uitleg} ${t("Uit de gegevens van {naam}, nagekeken op {datum}.", { naam: gl.naam, datum: datumLang(gv.peildatum) })}`
      : t("Mag een andere zijn dan die van je stroom.");
  }

  /**
   * De vorm van de terugleverkosten en de tabel met schalen (v0.135.0). De rijen
   * opnieuw alleen bij een andere vorm of een rij erbij of eraf, zodat een veld
   * waar iemand in typt blijft staan.
   */
  paintSchalen_(prefix) {
    const contract = this.draft_?.contract;
    if (!contract) return;
    const v = (prefix === "fx" ? contract.fixed : contract.dynamic) ?? {};
    const vorm = v.feed_in_costs_mode || "kwh";
    this.$(`#${prefix}-kostvorm`).value = vorm;
    this.$(`#${prefix}-feedcost-rij`).style.display = vorm === "kwh" || vorm === "overschot" ? "" : "none";
    this.$(`#${prefix}-schalen-blok`).style.display = vorm === "schalen" ? "" : "none";
    const tot = this.$(`#${prefix}-schalen-tot`);
    if (this.shadowRoot?.activeElement !== tot) tot.value = v.feed_in_scales_until || "";
    const host = this.$(`#${prefix}-schalen`);
    const rijen = v.feed_in_scales ?? [];
    host.innerHTML = rijen.map((r, i) => `
      <div class="schaal">
        <input type="number" min="0" step="1" inputmode="numeric" data-schaal="${prefix}:${i}:vanaf" value="${esc(r.vanaf ?? "")}" aria-label="${t("Vanaf kWh")}">
        <input type="number" min="0" step="0.01" inputmode="decimal" data-schaal="${prefix}:${i}:per_jaar" value="${esc(r.per_jaar ?? "")}" aria-label="${t("Bedrag per jaar")}">
        <button type="button" class="remove" data-schaal-weg="${prefix}:${i}">${t("Weghalen")}</button>
      </div>`).join("") || `<p class="sub geen">${t("Nog geen schalen.")}</p>`;
    for (const veld of host.querySelectorAll("[data-schaal]")) {
      veld.addEventListener("input", () => {
        const [, i, sleutel] = veld.dataset.schaal.split(":");
        rijen[Number(i)][sleutel] = Number(veld.value) || 0;
        this.wijziging_();
      });
    }
    for (const knop of host.querySelectorAll("[data-schaal-weg]")) {
      knop.addEventListener("click", () => {
        rijen.splice(Number(knop.dataset.schaalWeg.split(":")[1]), 1);
        this.paintSchalen_(prefix);
        this.wijziging_();
      });
    }
  }

  /** De eerdere contracten van een bron, een per rij. */
  paintPeriods_(bron) {
    const host = this.$(`#periods-${bron}`);
    if (!host) return;
    const lijst = this.periodsVan_(bron);
    if (!this.canEdit_()) {
      host.innerHTML = periodesLezen(bron, lijst);
      return;
    }
    const veld = (i, key, type, extra, waarde) =>
      `<input type="${type}" data-period-field="${key}" data-index="${i}" ${extra} value="${esc(waarde)}">`;
    const getal = 'min="0" step="0.0001" inputmode="decimal"';
    host.innerHTML = lijst.map((p, i) => {
      const voorbeeld = { stroom: t("Bijvoorbeeld Zonneplan Elektra 2026"), gas: t("Bijvoorbeeld Delta Gas 07/26 tot 06/27"), water: t("Bijvoorbeeld Waterbedrijf 2025") }[bron];
      const kop = `
        <div class="row"><label>${t("Naam")}</label>${veld(i, "name", "text", `maxlength="80" placeholder="${voorbeeld}"`, p.name ?? "")}</div>
        <div class="two">
          <div class="row"><label>${t("Van")}</label>${veld(i, "from", "date", "", p.from)}</div>
          <div class="row"><label>${t("Tot")}</label>${veld(i, "to", "date", "", p.to)}</div>
        </div>`;
      let prijzen;
      if (bron === "stroom") {
        const naam = leverancier(p.supplier)?.naam;
        const soort = hoofd(soortNaam(p.type));
        const wat = naam ? t("{soort} bij {naam}", { soort, naam: esc(naam) }) : soort;
        prijzen = p.type === "dynamic"
          ? `<p class="sub">${t("{wat}: Historie neemt de prijzen van toen uit de prijssensor.", { wat })}</p>`
          : `<p class="sub">${wat}</p>
            <div class="two">
              <div class="row"><label>${t("Stroom, all-in (€ per kWh)")}</label>${veld(i, "all_in_price", "number", getal, p.all_in_price || "")}</div>
              <div class="row"><label>${t("Terugleververgoeding (€ per kWh)")}</label>${veld(i, "feed_in_tariff", "number", getal, p.feed_in_tariff || "")}</div>
            </div>`;
      } else {
        prijzen = `<div class="row"><label>${bron === "gas" ? t("Gas, all-in (€ per m³)") : t("Water, all-in (€ per m³)")}</label>${veld(i, "price", "number", getal, p.price || "")}</div>`;
      }
      // Ingeklapt een regel, zoals een lijst van contracten in de app van een
      // meter (19-10-2026): naam of leverancier, en van wanneer tot wanneer.
      const titel = p.name || leverancier(p.supplier)?.naam || t("Eerder contract");
      const wanneer = p.from || p.to ? vanTot(p.from, p.to) : t("nog geen datums");
      const open = this.openPeriode_ === `${bron}:${i}` ? " open" : "";
      return `
        <details class="circuit period" data-period="${i}"${open}>
          <summary><span class="p-naam">${esc(titel)}</span><span class="p-wanneer">${esc(wanneer)}</span></summary>
          <div class="p-inhoud">
            ${kop}
            ${prijzen}
            <div class="circuit-actions">
              <button type="button" class="remove" data-period-remove="${i}">${t("Weghalen")}</button>
            </div>
          </div>
        </details>`;
    }).join("");
    // Wat openstaat blijft open als er opnieuw getekend wordt.
    for (const blok of host.querySelectorAll("details[data-period]")) {
      blok.addEventListener("toggle", () => {
        if (blok.open) this.openPeriode_ = `${bron}:${blok.dataset.period}`;
        else if (this.openPeriode_ === `${bron}:${blok.dataset.period}`) this.openPeriode_ = null;
      });
    }
    for (const el of host.querySelectorAll("[data-period-field]")) {
      const p = lijst[Number(el.dataset.index)];
      const key = el.dataset.periodField;
      el.addEventListener("input", () => {
        p[key] = el.type === "number" ? Number(el.value) || 0 : el.value;
        this.afterChange_();
      });
    }
    for (const knop of host.querySelectorAll("[data-period-remove]")) {
      knop.addEventListener("click", () => {
        lijst.splice(Number(knop.dataset.periodRemove), 1);
        this.paintPeriods_(bron);
        this.afterChange_();
      });
    }
  }

  /** De opbouw van de coach, en of hij bevestigd is. */
  paintOpbouw_() {
    if (!this.rendered_ || !this.draft_) return;
    const contract = this.draft_.contract;
    this.$("#opbouw").innerHTML = opbouwHtml(this.check_, namenVan(contract.supplier, contract.type));
    const zin = bevestigdZin(this.check_);
    this.$("#bevestigd-zin").textContent = this.dirty_() ? t("Je wijzigingen worden eerst opgeslagen.") : zin;
    this.$("#bevestig").hidden = Boolean(this.check_?.bevestigd) && !this.dirty_();
  }
}

DacViewContract.css = /* css */ `
  ${editorCss}
  ${opbouwCss}

  .segmented.drie { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  @media (max-width: 720px) { .segmented.drie { grid-template-columns: minmax(0, 1fr); } }
  select {
    width: 100%; min-height: 44px; padding: 10px 36px 10px 12px; border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border-hi); background-color: rgba(var(--dac-veil),0.04); color: var(--dac-ink);
    font: inherit; font-size: 14px; color-scheme: var(--dac-scheme);
    /* Het pijltje van de lijst (v0.138.0), want appearance none haalt dat van de browser weg;
       zonder pijltje leek het land op een gewoon veld. */
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1.5l5 5 5-5' fill='none' stroke='%238a8f98' stroke-width='1.6'/%3E%3C/svg%3E");
    background-repeat: no-repeat; background-position: right 14px center;
    cursor: pointer;
  }
  select option { background: var(--dac-bg-raise); color: var(--dac-ink); }
  .sub a { color: var(--dac-accent-hi); }

  /* De schalen van de terugleverkosten (v0.135.0). */
  .schalen { display: grid; gap: 8px; }
  .schaal-kop, .schaal { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; gap: 8px; align-items: center; }
  .schaal-kop { font-size: 12px; color: var(--dac-ink-3); }
  /* De rijen staan samen in een eigen div, en daar komt de afstand van .schalen
     niet in: de vakken lagen tegen elkaar (de eigenaar op 21-10-2026). */
  .schaal + .schaal { margin-top: 8px; }
  .schaal .remove {
    font: inherit; font-size: 12.5px; padding: 8px 10px; border-radius: var(--dac-radius-sm); cursor: pointer;
    border: 1px solid var(--dac-border); background: transparent; color: var(--dac-danger, #e5484d);
  }

  /* De bewoner leest (v0.130.1): wat de installateur kiest is er niet. */
  :host([readonly]) [data-installateur] { display: none !important; }
  .bewoner-uitleg { display: none; }
  :host([readonly]) .bewoner-uitleg { display: block; }
  .period.lezen { gap: 4px; }
  .period.lezen .p-kop { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; font-size: 14px; color: var(--dac-ink); }
  .period.lezen .p-naam { font-weight: 600; min-width: 0; overflow-wrap: anywhere; }
  .period.lezen .p-wanneer { margin-left: auto; font-size: 12.5px; color: var(--dac-ink-2); white-space: nowrap; }
  .sub.geen { margin: 0 0 12px; }
  label.klein { margin-top: 6px; font-size: 12.5px; font-weight: 500; color: var(--dac-ink-2); }

  .bevestig, .nieuw { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px; }
  .bevestig[hidden], .nieuw[hidden] { display: none; }
  .bevestig .sub, .nieuw .sub { font-size: 12.5px; line-height: 1.45; color: var(--dac-ink-2); }
  .bevestig button, .nieuw button {
    font: inherit; font-size: 14px; padding: 10px 16px; border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.04); color: var(--dac-ink); cursor: pointer;
  }
  .bevestig button.primary { background: var(--dac-accent); border-color: var(--dac-accent); color: var(--dac-on-accent, #fff); font-weight: 600; }
  .bevestig button[hidden] { display: none; }

  /* ---- eerdere contracten ---- */
  .circuit {
    padding: 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(var(--dac-veil),0.022);
    display: grid;
    gap: 12px;
    margin-bottom: 12px;
  }
  .circuit .sub { margin: 0; }
  details.period > summary {
    display: flex; justify-content: space-between; align-items: baseline; gap: 10px; cursor: pointer;
    list-style: none; font-size: 14px; color: var(--dac-ink);
  }
  details.period > summary::-webkit-details-marker { display: none; }
  details.period > summary::after { content: "›"; color: var(--dac-ink-3); margin-left: 6px; transition: transform 150ms ease; }
  details.period[open] > summary::after { transform: rotate(90deg); }
  details.period > summary .p-naam { font-weight: 600; min-width: 0; overflow-wrap: anywhere; }
  details.period > summary .p-wanneer { margin-left: auto; font-size: 12.5px; color: var(--dac-ink-2); white-space: nowrap; }
  details.period:not([open]) { gap: 0; }
  /* De inhoud in een eigen raster (v0.136.0): een <details> legt zijn kinderen niet
     als raster uit, dus de afstand van .circuit kwam er niet in, en Van, Tot, de
     prijs en Weghalen plakten tegen elkaar (de eigenaar op 19-10-2026). */
  details.period { display: block; }
  details.period > .p-inhoud { display: grid; gap: 12px; margin-top: 14px; }
  .circuit-actions { display: flex; justify-content: flex-end; }
  .circuit-actions button {
    font: inherit;
    font-size: 13px;
    padding: 8px 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(var(--dac-veil),0.04);
    color: var(--dac-ink);
    cursor: pointer;
  }
  .circuit-actions button.remove { color: var(--dac-danger, #e5484d); }
  .herreken-knoppen { display: flex; flex-wrap: wrap; gap: 8px; }
  .herreken-knoppen button {
    font: inherit; font-size: 13px; padding: 8px 14px; border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.04); color: var(--dac-ink); cursor: pointer;
  }
  .herreken-knoppen button[hidden] { display: none; }
`;

define("dac-view-contract", DacViewContract);
