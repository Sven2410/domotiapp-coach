/**
 * Proeven op het vermogensdeel van het rapport.
 *
 * Waarom dit bestand bestaat: bij de eerste woning met een P1 die met een teken
 * meet viel het net helemaal uit het rapport. `vermogenBronnen_` kende alleen de
 * gesplitste meter, en bij een meter met een teken zijn `grid_import` en
 * `grid_export` leeg, dus vielen beide regels weg zonder dat er iets voor
 * terugkwam. Zon en de apparaten stonden er wel, en daardoor zag het rapport er
 * compleet uit terwijl de belangrijkste regel ontbrak.
 *
 * Draaien: node tests/test_rapport.mjs
 */

import assert from "node:assert/strict";

// --- het paneel draait in een browser, dus die kant wordt hier nagemaakt -----
// Alleen wat er bij het inlezen van de module echt aangeraakt wordt. De
// elementen zelf worden nooit aangemaakt: de proeven pakken de prototype en
// zetten er de velden op die de methode leest.
const geregistreerd = new Map();
globalThis.HTMLElement = class {};
globalThis.customElements = {
  get: (naam) => geregistreerd.get(naam),
  define: (naam, klasse) => geregistreerd.set(naam, klasse),
};
globalThis.CSSStyleSheet = class {
  replaceSync() {}
};
globalThis.document = {
  createElement: () => ({ style: {}, append() {}, setAttribute() {} }),
  createTextNode: () => ({}),
};

await import("../custom_components/domotiapp_coach/frontend/src/views/history.js");
const Historie = geregistreerd.get("dac-view-history");
assert.ok(Historie, "de historieweergave hoort zich te registreren");

// --- gereedschap ------------------------------------------------------------

/** Kwartieren voor één sensor, vanaf middernacht vandaag. */
function kwartieren(waarden) {
  const nul = new Date();
  nul.setHours(0, 0, 0, 0);
  return waarden.map((v, i) => ({
    start: Math.round(nul.getTime() / 1000) + i * 900,
    laagste: v.laag,
    piek: v.piek,
    gemiddeld: v.gem,
    seconden: 900,
  }));
}

/** Een historieweergave zonder browser eromheen. */
function weergave(sources, opslag) {
  const el = Object.create(Historie.prototype);
  el.period_ = "day";
  el.offset_ = 0;
  el.korrel_ = "quarter";
  el.settings_ = { sources, devices: [], installation: {} };
  el.hass_ = {
    callWS: async ({ entity_ids }) =>
      Object.fromEntries(
        entity_ids.filter((id) => opslag[id]).map((id) => [id, opslag[id]])
      ),
  };
  return el;
}

const proeven = [];
const proef = (naam, fn) => proeven.push([naam, fn]);

// --- de gesplitste meter: serieel uitgelezen, twee aparte meters -------------

proef("twee losse meters geven twee regels, allebei positief", async () => {
  const el = weergave(
    {
      grid_mode: "split",
      grid_import: "sensor.afname",
      grid_export: "sensor.teruglevering",
      solar: "sensor.zon",
    },
    {
      "sensor.afname": kwartieren([{ laag: 0, piek: 1120, gem: 587 }]),
      "sensor.teruglevering": kwartieren([{ laag: 0, piek: 2377, gem: 213 }]),
      "sensor.zon": kwartieren([{ laag: 484, piek: 5511, gem: 1246 }]),
    }
  );

  const namen = el.vermogenBronnen_().map((r) => r.label);
  assert.deepEqual(namen, ["Van het net", "Naar het net", "Zon"]);

  const { samenvatting, detail } = await el.vermogen_();
  assert.deepEqual(
    samenvatting.rijen.map((r) => r[0]),
    ["Van het net", "Naar het net", "Zon"]
  );
  assert.deepEqual(
    detail.tabellen.map((t) => t.naam),
    ["Van het net", "Naar het net", "Zon"]
  );
  // Bij twee meters zegt de naam al welke kant het op gaat, dus de zin over het
  // teken hoort er niet bij te staan.
  assert.ok(!detail.uitleg.includes("een plus wat er van het net kwam"));
});

// --- de meter met een teken: een P1 die negatief en positief meet ------------

proef("een meter met een teken geeft een regel die het net heet", async () => {
  const el = weergave(
    {
      grid_mode: "signed",
      grid_import: "",
      grid_export: "",
      grid_signed: "sensor.p1",
      grid_signed_invert: false,
      solar: "sensor.zon",
    },
    {
      "sensor.p1": kwartieren([{ laag: -6891, piek: 874, gem: -3531 }]),
      "sensor.zon": kwartieren([{ laag: 1162, piek: 7297, gem: 6320 }]),
    }
  );

  const bronnen = el.vermogenBronnen_();
  assert.deepEqual(
    bronnen.map((r) => [r.label, r.entity]),
    [
      ["Het net", "sensor.p1"],
      ["Zon", "sensor.zon"],
    ]
  );

  const { samenvatting, detail } = await el.vermogen_();
  assert.deepEqual(
    detail.tabellen.map((t) => t.naam),
    ["Het net", "Zon"]
  );
  // Het teken blijft staan: dit is afname en teruglevering in een regel.
  const rij = detail.tabellen[0].rijen[0];
  assert.equal(rij[1], "-6,89 kW", "het laagste is de zwaarste teruglevering");
  assert.equal(rij[3], "874 W", "de piek is de zwaarste afname");
  assert.equal(samenvatting.rijen[0][1], "-6,89 kW");
  assert.ok(
    detail.uitleg.includes("een plus wat er van het net kwam"),
    "bij een regel hoort erbij te staan wat het teken betekent"
  );
});

proef("het net verdwijnt niet meer als import en export leeg zijn", async () => {
  const el = weergave(
    { grid_mode: "signed", grid_signed: "sensor.p1", solar: "" },
    { "sensor.p1": kwartieren([{ laag: -100, piek: 900, gem: 400 }]) }
  );
  const { detail } = await el.vermogen_();
  assert.equal(detail.tabellen.length, 1);
  assert.equal(detail.tabellen[0].naam, "Het net");
});

proef("een meter die andersom telt wordt rechtgezet", async () => {
  const el = weergave(
    { grid_mode: "signed", grid_signed: "sensor.p1", grid_signed_invert: true },
    { "sensor.p1": kwartieren([{ laag: -874, piek: 6891, gem: 3531 }]) }
  );

  const { samenvatting, detail } = await el.vermogen_();
  const rij = detail.tabellen[0].rijen[0];
  // Omdraaien wisselt het laagste en de piek van plek: het laagste van min
  // wordt de hoogste van plus.
  assert.equal(rij[1], "-6,89 kW");
  assert.equal(rij[2], "-3,53 kW");
  assert.equal(rij[3], "874 W");
  assert.equal(samenvatting.rijen[0][3], "874 W");
});

proef("zonder vinkje blijft de meter zoals hij gemeten heeft", async () => {
  const el = weergave(
    { grid_mode: "signed", grid_signed: "sensor.p1", grid_signed_invert: false },
    { "sensor.p1": kwartieren([{ laag: -874, piek: 6891, gem: 3531 }]) }
  );
  const { detail } = await el.vermogen_();
  assert.equal(detail.tabellen[0].rijen[0][3], "6,89 kW");
});

// --- het teken op de fasekaart ----------------------------------------------

// --- de resterende tijd in uren (Home Connect Local, 23-09-2026) --------------

const { countdown } = await import("../custom_components/domotiapp_coach/frontend/src/format.js");

proef("de resterende tijd telt in de eenheid van de sensor: uren, minuten, seconden", () => {
  // Thuis op 23-09-2026: 1,48333 h is 89 minuten. Zonder eenheid zijn het minuten.
  assert.equal(countdown("1.48333333333333", "h"), "nog 1 u 29 min");
  assert.equal(countdown("89", "min"), "nog 1 u 29 min");
  assert.equal(countdown("5340", "s"), "nog 1 u 29 min");
  assert.equal(countdown("89", undefined), "nog 1 u 29 min");
  assert.equal(countdown("0", "h"), "Klaar");
});

const { signedPower, zonderMinNul } = await import(
  "../custom_components/domotiapp_coach/frontend/src/format.js"
);

proef("een vermogen houdt zijn teken waar het de richting is", () => {
  assert.deepEqual(signedPower(485), { value: "485", unit: "W" });
  assert.deepEqual(signedPower(-339), { value: "-339", unit: "W" });
  assert.deepEqual(signedPower(-6891), { value: "-6,89", unit: "kW" });
  // Een min voor een nul leest als een fout terwijl er niets fout is.
  assert.deepEqual(signedPower(-0.4), { value: "0", unit: "W" });
  assert.deepEqual(signedPower(0), { value: "0", unit: "W" });
  assert.deepEqual(signedPower(null), { value: "—", unit: "" });
});

proef("een stroom van -0,017 A wordt 0,0 en niet -0,0", () => {
  assert.equal(zonderMinNul(-0.017, 1), 0);
  assert.equal(Object.is(zonderMinNul(-0.017, 1), -0), false);
  assert.equal(zonderMinNul(-0.096, 1), -0.1);
  assert.equal(zonderMinNul(2.123, 1), 2.1);
  assert.equal(zonderMinNul(-1.461, 1), -1.5);
});

// --- de grenssensor van de lastbewaker in het installatiescherm -------------
//
// De Easee Equalizer in de klantwoning meldt in een sensor hoeveel hij op dit
// moment vrijgeeft voor het laden. De coach vroeg daar de hele nacht van
// 30-08-2026 overheen en las uur na uur `limited_by_equalizer`, dus die sensor
// is nu in te vullen.

await import("../custom_components/domotiapp_coach/frontend/src/views/installation.js");
const Installatie = geregistreerd.get("dac-view-installation");
assert.ok(Installatie, "het installatiescherm hoort zich te registreren");

proef("het installatiescherm heeft een veld voor wat de lastbewaker vrijgeeft", () => {
  const html = Object.create(Installatie.prototype).render();
  assert.ok(
    html.includes('<dac-entity-picker id="balancer-limit">'),
    "er hoort een kiezer voor de grenssensor te staan"
  );
  assert.ok(
    html.includes('id="balancer-row"'),
    "en die hoort in een rij te zitten die te verbergen is"
  );
});

// De eigenaar op 29-09-2026: "Groepen met een eigen zekering moet even anders. Dat moet
// heten onderverdeelkast", met "een optie aanvinken: deze onderverdeelkast heeft een
// eigen kWh-meter, en dan pas de opties om L1/2/3 in te vullen", en daaronder een
// kopje Groepen met "hangt onder" en hetzelfde vinkje (v0.101.5).
proef("het installatiescherm heeft onderverdeelkasten en groepen, elk met een eigen knop", () => {
  const html = Object.create(Installatie.prototype).render();
  assert.ok(html.includes("Onderverdeelkasten") && html.includes('id="kasten"') && html.includes('id="kast-add"'));
  assert.ok(html.includes('id="circuits"') && html.includes('id="circuit-add"'), "en de groepen");
  assert.ok(!html.includes("Groepen met een eigen zekering"), "het oude kopje is weg");
});

proef("een kast en een groep: de sensoren per fase pas met een eigen kWh-meter", () => {
  const el = Object.create(Installatie.prototype);
  const kast = { id: "lounge", kind: "kast", name: "Lounge", fuse_amps: 20, phases: 3, parent: "", meter: false, sensors: {} };
  const paal = { id: "paal", kind: "groep", name: "Laadpaal", fuse_amps: 20, phases: 3, parent: "lounge", meter: false, sensors: {} };
  const accu = { id: "accu", kind: "groep", name: "Thuisbatterij", fuse_amps: 16, phases: 1, parent: "lounge", meter: true, sensors: {} };
  const alle = [kast, paal, accu];
  const kastHtml = el.circuitHtml_(kast, 0, alle);
  assert.ok(kastHtml.includes("Deze onderverdeelkast heeft een eigen kWh-meter"));
  assert.equal((kastHtml.match(/data-kind="current"/g) ?? []).length, 0, "zonder meter geen sensoren");
  assert.ok(!kastHtml.includes("Hangt onder"), "één kast hangt altijd onder de hoofdkast");
  assert.ok(kastHtml.includes("Onderverdeelkast verwijderen"));
  const paalHtml = el.circuitHtml_(paal, 1, alle);
  assert.ok(paalHtml.includes('<option value="lounge" selected>Lounge</option>'), "de groep hangt onder de lounge");
  assert.ok(paalHtml.includes(">Hoofdkast</option>") && paalHtml.includes("Deze groep heeft een eigen kWh-meter"));
  assert.ok(!paalHtml.includes('value="paal"'), "een groep hangt niet onder zichzelf");
  assert.equal((el.circuitHtml_(accu, 2, alle).match(/data-kind="current"/g) ?? []).length, 1, "met meter, één fase: één stroomsensor");
  assert.equal((el.circuitHtml_({ ...kast, meter: true }, 0, alle).match(/data-kind="current"/g) ?? []).length, 3);
});

proef("bestaande groepen worden ingedeeld: de lounge en de garage zijn kasten, een losse groep blijft een groep", async () => {
  const { kastenIndelen } = await import("../custom_components/domotiapp_coach/frontend/src/views/installation.js");
  const thuis = kastenIndelen([
    { id: "lounge", name: "Lounge", fuse_amps: 20, parent: "", sensors: {} },
    { id: "paal", name: "Laadpaal", fuse_amps: 20, parent: "lounge", sensors: {} },
  ]);
  assert.deepEqual(thuis.map((g) => [g.kind, g.meter]), [["kast", false], ["groep", false]]);
  const garage = kastenIndelen([{ id: "garage", name: "Garage", parent: "", sensors: { l1: { current: "sensor.g_l1" } } }]);
  assert.deepEqual([garage[0].kind, garage[0].meter], ["kast", true], "de garage met zijn meter");
  const los = kastenIndelen([{ id: "boiler", name: "Boiler", parent: "", sensors: {} }]);
  assert.equal(los[0].kind, "groep", "een groep in de hoofdkast zonder meter en zonder groepen eronder");
  const gekozen = kastenIndelen([{ id: "x", kind: "groep", meter: true, parent: "", sensors: {} }]);
  assert.deepEqual([gekozen[0].kind, gekozen[0].meter], ["groep", true], "wat al gekozen is blijft");
});

proef("opslaan zonder eigen kWh-meter stuurt geen sensoren mee, en laat het klad staan", () => {
  const el = Object.create(Installatie.prototype);
  const sensors = { l1: { current: "sensor.a" } };
  const draft = { installation: { circuits: [{ id: "g", meter: false, sensors }, { id: "h", meter: true, sensors }] }, contract: {} };
  const uit = el.payload_(draft);
  assert.deepEqual(uit.installation.circuits[0].sensors, {}, "zonder meter niets");
  assert.deepEqual(uit.installation.circuits[1].sensors, sensors, "met meter wel");
  assert.deepEqual(draft.installation.circuits[0].sensors, sensors, "het klad houdt ze, voor als het vinkje weer aan gaat");
});

proef("de rij hangt aan het vinkje van de lastbewaker", () => {
  const rij = { hidden: false, style: {} };
  const el = Object.create(Installatie.prototype);
  el.$ = (kiezer) => (kiezer === "#balancer-row" ? rij : null);

  el.draft_ = { installation: { load_balancer: false } };
  el.paintBalancer_();
  // `hidden` alleen is niet genoeg: dat attribuut verliest van elke `display`
  // die in de eigen stijlen staat, en `.row` heeft er een. Zie CLAUDE.md.
  assert.equal(rij.hidden, true);
  assert.equal(rij.style.display, "none");

  el.draft_ = { installation: { load_balancer: true } };
  el.paintBalancer_();
  assert.equal(rij.hidden, false);
  assert.equal(rij.style.display, "");
});

// --- de tijdlijn op de laadpaalkaart ---------------------------------------
//
// De eigenaar vroeg er op 30-08-2026 om: zien wat de coach van plan is tot de auto vol
// moet zijn. Het scherm rekent zelf niets uit; alles komt uit `timeline()` in
// planner.py. Wat hier beproefd wordt is dus of het staat wat er gestuurd is.

await import("../custom_components/domotiapp_coach/frontend/src/plan-ahead-sheet.js");
const Vooruit = geregistreerd.get("dac-plan-ahead-sheet");
assert.ok(Vooruit, "de tijdlijn-pop-up hoort zich te registreren");

/** Een nagemaakt element met alleen de knopen die `paint_` aanraakt. */
function vooruitScherm(planAhead) {
  const knopen = new Map();
  const maak = () => {
    const kinderen = [];
    return {
      className: "",
      style: {},
      textContent: "",
      classList: { add(naam) { this.klassen.push(naam); }, klassen: [] },
      kinderen,
      attrs: {},
      setAttribute(naam, waarde) { this.attrs[naam] = waarde; },
      append(...items) { kinderen.push(...items); },
      replaceChildren(...items) { kinderen.length = 0; kinderen.push(...items); },
    };
  };
  // Sinds v0.86.0 ook de prijsgrafiek, die svg-knopen maakt.
  for (const id of ["#vooruit-title", "#vooruit-nu", "#vooruit-kop", "#vooruit-uren", "#vooruit-voet", "#vooruit-prijs"]) {
    knopen.set(id, maak());
  }
  globalThis.document.createElementNS = () => maak();
  globalThis.document.createElement = () => {
    const el = maak();
    el.classList = {
      klassen: [],
      add(naam) { this.klassen.push(naam); el.className = this.klassen.join(" "); },
    };
    return el;
  };

  const el = Object.create(Vooruit.prototype);
  el.$ = (kiezer) => knopen.get(kiezer) ?? null;
  el.label_ = "Laadpaal";
  el.reason_ = "Het is nu niet het goedkoopste moment om te laden.";
  el.plan_ = planAhead;
  return { el, knopen };
}

/** De tijdlijn zoals de coach hem voor de klantwoning die nacht uitrekende. */
const NACHT = {
  deadline: "2026-08-30T07:00:00",
  latest_start: "2026-08-30T03:07:00",
  expected_done: "2026-08-30T07:00:00",
  kwh_needed: 37.2,
  hours_needed: 3.37,
  amps: 16,
  note: "",
  blocks: [
    { start: "2026-08-29T22:00:00", end: "2026-08-29T23:00:00", price: 0.3106,
      charging: false, why: "duurder dan wat hij nodig heeft", solar_kwh: 0, kwh: 0 },
    { start: "2026-08-30T03:00:00", end: "2026-08-30T04:00:00", price: 0.2215,
      charging: true, why: "een van de goedkoopste uren", solar_kwh: 0, kwh: 11.0 },
    { start: "2026-08-30T04:00:00", end: "2026-08-30T05:00:00", price: 0.2113,
      charging: true, why: "een van de goedkoopste uren", solar_kwh: 2.4, kwh: 11.0 },
  ],
};

proef("op een groep van 16 A zegt de kop 14 A en welke zekering dat is (v0.98.0)", () => {
  // De eerste woning op 25-09-2026 om 00:42: "16 A, wat paal en auto kunnen" voor een
  // paal op een groep die hem nooit meer dan 14 A geeft.
  const kop = (plan) => {
    const { el, knopen } = vooruitScherm(plan);
    el.paint_();
    return knopen.get("#vooruit-kop").kinderen.flatMap((vak) => vak.kinderen.map((kind) => kind.textContent)).join(" | ");
  };
  assert.match(kop({ ...NACHT, amps: 14, fuse_name: "Garage" }), /14 A, meer past er niet onder de zekering van de groep Garage/);
  assert.match(kop({ ...NACHT, amps: 14, fuse_name: "" }), /14 A, meer past er niet onder je zekering/);
  assert.match(kop({ ...NACHT, amps: 12, fuse_name: "Garage", measured: true }), /12 A, wat er de afgelopen uren gemiddeld overbleef/);
  assert.match(kop({ ...NACHT, fuse_name: null }), /16 A, wat paal en auto kunnen/);
});

proef("de kop toont wat er nog in moet en wanneer hij begint", () => {
  const { el, knopen } = vooruitScherm(NACHT);
  el.paint_();
  const tekst = knopen.get("#vooruit-kop").kinderen
    .flatMap((vak) => vak.kinderen.map((kind) => kind.textContent))
    .join(" | ");
  assert.match(tekst, /37,2 kWh/, "het aantal kilowattuur hoort erin");
  assert.match(tekst, /Op vol vermogen/, "de laadtijd heet wat hij is: een som op vol vermogen");
  assert.match(tekst, /16 A/, "met de stroom waar het op gerekend is");
  assert.match(tekst, /3 u 22 m/, "als uren en minuten");
  // Die nacht is niet vandaag, dus de dag hoort erbij: "zo 03:07".
  assert.match(tekst, /zo 03:07/, "het uiterste startmoment, met de dag erbij");
  assert.match(tekst, /klaar om zo 07:00/, "en de klaar-tijd");
  // Een server van voor v0.47.3 stuurt geen `planned_kwh` mee; dan blijft het
  // bij "vol rond" zoals het was.
  assert.match(tekst, /Vol rond/, "zonder planned_kwh staat er gewoon vol rond");
});

// In de klantwoning op 04-09-2026: "Vol rond 17:00" boven acht zonblokken van
// samen 33 van de 66 kWh, want de prijzen tot zondag 06:00 waren er nog niet.
// De eigenaar las dat als een belofte. Dekt het plan het tekort niet, dan staat er
// wat er gepland is en waarom de rest ontbreekt.
proef("dekt het plan het tekort niet, dan staat er gepland en geen vol rond", () => {
  const half = { ...NACHT, kwh_needed: 66.1, planned_kwh: 33.1, solar_only: true };
  const { el, knopen } = vooruitScherm(half);
  el.paint_();
  const tekst = knopen.get("#vooruit-kop").kinderen
    .flatMap((vak) => vak.kinderen.map((kind) => kind.textContent))
    .join(" | ");
  assert.match(tekst, /Gepland \| 33,1 kWh/, "wat er gepland staat");
  assert.match(tekst, /van 66,1 kWh; de rest zodra de prijzen er zijn/, "en waarom niet alles");
  assert.ok(!tekst.includes("Vol rond"), "geen belofte die het plan niet waarmaakt");
  assert.ok(!tekst.includes("07:00"), "en ook niet het einde van het laatste zonuur");

  const krap = { ...half, solar_only: false };
  const scherm2 = vooruitScherm(krap);
  scherm2.el.paint_();
  const tekst2 = scherm2.knopen.get("#vooruit-kop").kinderen
    .flatMap((vak) => vak.kinderen.map((kind) => kind.textContent))
    .join(" | ");
  assert.match(tekst2, /meer past er niet vóór de klaar-tijd/, "zonder zon-reden is het de ruimte");

  const vol = { ...NACHT, planned_kwh: 37.2 };
  const scherm3 = vooruitScherm(vol);
  scherm3.el.paint_();
  const tekst3 = scherm3.knopen.get("#vooruit-kop").kinderen
    .flatMap((vak) => vak.kinderen.map((kind) => kind.textContent))
    .join(" | ");
  assert.match(tekst3, /Vol rond \| zo 07:00/, "dekt het plan alles, dan wel vol rond");
});

proef("elk uur staat er met zijn prijs en of hij laadt", () => {
  const { el, knopen } = vooruitScherm(NACHT);
  el.paint_();
  const rijen = knopen.get("#vooruit-uren").kinderen;
  assert.equal(rijen.length, 3, "drie blokken, drie regels");

  const eerste = rijen[0].kinderen.map((kind) => kind.textContent);
  assert.deepEqual(eerste,
    ["22:00", "€ 0,311", "", "Wachten, duurder dan wat hij nodig heeft"]);
  assert.ok(!rijen[0].className.includes("laadt"), "een wachtuur krijgt geen kleur");

  // Een uur zonder zon krijgt een lege kolom en geen streepje: een kolom vol
  // streepjes leest als een storing.
  assert.equal(rijen[1].kinderen[2].textContent, "", "geen zon, geen tekst");

  // Een server van vóór v0.47.5 stuurt geen stroom per blok mee; dan staat de
  // zon in de kolom, zoals het was.
  const derde = rijen[2].kinderen.map((kind) => kind.textContent);
  assert.deepEqual(derde,
    ["04:00", "€ 0,211", "2,4 kWh zon", "Laden, een van de goedkoopste uren"]);
  assert.ok(rijen[2].className.includes("laadt"), "een laaduur wel");
});

// De eigenaar op 04-09-2026, over "4,1 kWh zon" bij een dak van 2,4: "dat weet je toch
// niet. Laat sowieso zien hoeveel ampère hij laadt en kW."
proef("een laaduur zegt hoe hard, en hoeveel daarvan zon is", () => {
  const met = { ...NACHT, blocks: [
    { start: "2026-08-30T09:00:00", end: "2026-08-30T10:00:00", price: 0.132,
      charging: true, why: "wat zon, aangevuld tot de ondergrens van je paal",
      solar_kwh: 1.2, kwh: 4.14, amps: 6, kw: 4.14 },
    { start: "2026-08-30T03:00:00", end: "2026-08-30T04:00:00", price: 0.2215,
      charging: true, why: "een van de goedkoopste manieren",
      solar_kwh: 0, kwh: 11.0, amps: 16, kw: 11.04 },
    { start: "2026-08-30T08:00:00", end: "2026-08-30T09:00:00", price: 0.18,
      charging: false, why: "duurder dan wat hij nodig heeft",
      solar_kwh: 0.4, kwh: 0, amps: 0, kw: 0 },
  ] };
  const { el, knopen } = vooruitScherm(met);
  el.paint_();
  const rijen = knopen.get("#vooruit-uren").kinderen.map((rij) =>
    rij.kinderen.map((kind) => kind.textContent));
  assert.deepEqual(rijen[0], ["09:00", "€ 0,132", "6 A",
    "Laden op 4,1 kW, waarvan 1,2 kWh zon: wat zon, aangevuld tot de ondergrens van je paal"]);
  assert.deepEqual(rijen[1], ["03:00", "€ 0,222", "16 A",
    "Laden op 11,0 kW: een van de goedkoopste manieren"]);
  assert.deepEqual(rijen[2], ["08:00", "€ 0,180", "0,4 kWh zon",
    "Wachten, duurder dan wat hij nodig heeft"]);
});

proef("zonder plan staat er waarom, en geen leeg scherm", () => {
  const { el, knopen } = vooruitScherm(null);
  el.paint_();
  const rijen = knopen.get("#vooruit-uren").kinderen;
  assert.equal(rijen.length, 1);
  assert.match(rijen[0].textContent, /nog geen plan/);
});

proef("bij een vast tarief staat de uitleg en niet een lege lijst", () => {
  const vast = { ...NACHT, blocks: [], note: "Je hebt een vast tarief, dus elk uur kost hetzelfde." };
  const { el, knopen } = vooruitScherm(vast);
  el.paint_();
  const rijen = knopen.get("#vooruit-uren").kinderen;
  assert.equal(rijen.length, 1);
  assert.match(rijen[0].textContent, /vast tarief/);
  // De sommen erboven blijven wel staan: die kloppen ook zonder prijzenlijst.
  const kop = knopen.get("#vooruit-kop").kinderen;
  assert.equal(kop.length, 4);
});

proef("een onbekende accustand geeft een streepje en geen nul", () => {
  const leeg = { ...NACHT, kwh_needed: null, hours_needed: null, latest_start: null };
  const { el, knopen } = vooruitScherm(leeg);
  el.paint_();
  const tekst = knopen.get("#vooruit-kop").kinderen
    .flatMap((vak) => vak.kinderen.map((kind) => kind.textContent))
    .join(" | ");
  assert.match(tekst, /–/, "onbekend hoort een streepje te zijn");
  assert.ok(!tekst.includes("0,0 kWh"), "en zeker geen verzonnen nul");
});

// --- de programmatabel van de vaatwasser -------------------------------------
//
// Dezelfde tabel staat in planner.py (`PROGRAMMAS`), want de coach plant
// ermee zonder Home Assistant. Twee tabellen die uit elkaar lopen zouden een
// paneel geven dat "225 minuten" zegt en een coach die met iets anders rekent.

import { readFileSync } from "node:fs";
const { DISHWASHER_PROGRAMS } = await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
proef("de programmatabel in het paneel is dezelfde als die in planner.py", () => {
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/planner.py", import.meta.url), "utf-8");
  const regels = [...bron.matchAll(/Programma\("([a-z0-9_]+)", "[^"]+", (\d+), ([\d.]+), (\d+)\)/g)];
  const python = new Map(regels.map((m) => [m[1], { minutes: Number(m[2]), kwh: Number(m[3]), peakW: Number(m[4]) }]));
  assert.equal(python.size, DISHWASHER_PROGRAMS.length, "evenveel programma's");
  for (const p of DISHWASHER_PROGRAMS) {
    const q = python.get(p.key);
    assert.ok(q, `${p.key} staat ook in planner.py`);
    assert.deepEqual({ minutes: p.minutes, kwh: p.kwh, peakW: p.peakW }, q, p.key);
  }
});

// --- de programmatabel per apparaat (06-09-2026 's avonds) -------------------
//
// De eigenaar: "ik wil dat kunnen aanpassen, wel moet hij dit als uitgangspunt
// hebben", en "bij een domme vaatwasser een dropdown van de variabelen die ik
// er in heb gezet." De opgave is het uitgangspunt, de eigen tabel wint, en de
// meting wint van allebei.

const { programsFor, defaultPrograms, hasOwnPrograms, programKey, programOf, programPicker, isManualProgram, missingForControl,
        programOptions, programRows, programChooser, programChoices, apparatenZin, canSteer, brandsFor, brandFields, canHaveDeadline } =
  await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
const { timesFor } = await import("../custom_components/domotiapp_coach/frontend/src/schedule-sheet.js");
// De eigenaar op 07-09-2026: "de coach zegt zet nu de tablet lader aan, maar de
// tablet lader is alleen een vermogenssensor en het vinkje staat uit."
proef("de tip noemt alleen apparaten waarbij het vinkje aan staat, en nooit wat de coach zelf stuurt of plant", () => {
  const tablet = { type: "overig", name: "Tablet lader", controllable: false };
  const paal = { type: "laadpaal", name: "Laadpaal", brand: "easee", controllable: true };
  const dom = { type: "vaatwasser", brand: "overig", name: "Vaatwasser", controllable: true };
  const accu = { type: "thuisbatterij", brand: "anker", name: "Anker", controllable: true, entities: { setpoint: "number.x" } };
  const was = { type: "overig", name: "Wasmachine", controllable: true };
  const alfen = { type: "laadpaal", name: "Alfen", brand: "", controllable: false };
  // De eigenaar op 22-09-2026: "je mag nooit de batterij adviseren om aan te
  // zetten, dat doet de coach zelf. Ook met een laadpaal die stuurbaar is."
  assert.equal(apparatenZin([tablet, paal, dom, accu, was]), "de Wasmachine");
  assert.equal(apparatenZin([tablet]), "");
  assert.equal(apparatenZin([{ ...tablet, controllable: true }]), "de Tablet lader");
  assert.equal(apparatenZin([alfen, { ...alfen, controllable: true }]), "de Alfen");
});

// Het advies bovenaan het overzicht als de batterij handelt, of afgeeft.
const { advise } = await import("../custom_components/domotiapp_coach/frontend/src/views/overview.js");
proef("handelt de batterij, dan is wat naar het net gaat verkoop en geen overschot", () => {
  const drempels = { price: { high: 0.4, low: 0.1 }, self_use: { low: 20 } };
  const r = { solar: 275, grid: -2290, exportW: 2290, importW: 0, load: 1, loadBasis: "phase", price: 0.39, selfUse: 100 };
  const accu = { name: "Anker", mode: "handelen", setpoint_w: -2400, target_w: 2400, power_w: -2400, balance_kwh: 3.2 };
  const advies = advise(r, drempels, true, 80, null, [], accu);
  assert.equal(advies.title, "Anker handelt");
  assert.ok(advies.body.includes("toegestaan om te handelen") && advies.body.includes("2.400 W") && advies.body.includes("3,2 kWh"), advies.body);
  assert.ok(advies.body.includes("zo min mogelijk stroom"), advies.body);
  const metWas = advise(r, drempels, true, 80, null, [{ type: "overig", name: "Wasmachine", controllable: true }], accu);
  assert.ok(metWas.body.includes("stel de Wasmachine uit"), metWas.body);
  // Geeft hij aan het huis af en gaat er toch iets naar het net, dan is alleen
  // het deel dat niet uit de accu komt overschot.
  const nul = advise(r, drempels, true, 80, null, [], { ...accu, mode: "nul", power_w: -2400 });
  assert.notEqual(nul.title, "Gebruik je overschot");
  // Ook zonder besluit van de coach: de meting aan de batterij zelf telt.
  const rAccu = { ...r, devices: [{ type: "thuisbatterij", batteryWatts: -2400 }] };
  assert.notEqual(advise(rAccu, drempels, true, 80, null, [], null).title, "Gebruik je overschot");
  const zon = advise({ ...r, exportW: 2290, grid: -2290 }, drempels, true, 80, null, [], { ...accu, mode: "nul", power_w: 500 });
  assert.equal(zon.title, "Gebruik je overschot");
});
// "Er is een verschil tussen de coach mag aansturen en adviseren, want een
// domme vaatwasser kan de coach helemaal niet aansturen maar wel adviseren."
proef("sturen kan alleen wat een merk met knoppen heeft, of een boiler met een schakelaar", () => {
  assert.equal(canSteer({ type: "laadpaal", brand: "easee" }), true);
  assert.equal(canSteer({ type: "vaatwasser", brand: "home_connect" }), true);
  assert.equal(canSteer({ type: "vaatwasser", brand: "overig" }), false);
  assert.equal(canSteer({ type: "overig" }), false);
  // Een boiler heeft geen merk maar wel een schakelaar (v0.71.0). De eigenaar op
  // 19-09-2026: "alleen de switch invullen en power invullen."
  assert.equal(canSteer({ type: "boiler" }), true);
});
proef("een boiler vraagt om twee dingen en verder niets", () => {
  const leeg = { type: "boiler", controllable: true };
  // De velden van het type, zonder dat er een merk gekozen hoeft te worden.
  assert.deepEqual(brandsFor("boiler"), []);
  assert.deepEqual(brandFields(leeg).map((f) => f.key), ["switch"]);
  // En allebei zijn ze nodig zodra hij mag sturen: zonder schakelaar kan hij
  // niets, zonder vermogen ziet hij niet dat het vat vol is.
  assert.deepEqual(missingForControl(leeg), ["Vermogenssensor", "Schakelaar"]);
  assert.deepEqual(
    missingForControl({ ...leeg, entity: "sensor.boiler", entities: { switch: "switch.boiler" } }),
    []
  );
  // Een klaar-tijd hoort erbij, en dan alleen die ene tijd.
  assert.equal(canHaveDeadline({ ...leeg, type: "boiler" }), true);
  assert.deepEqual(timesFor({ type: "boiler" }).map((t) => t.key), ["done_by"]);
});
proef("zonder eigen tabel is de tabel van een apparaat de opgave van de fabrikant", () => {
  const rows = programsFor({ type: "vaatwasser", brand: "overig" });
  assert.equal(rows.length, DISHWASHER_PROGRAMS.length);
  assert.deepEqual(rows[0], { key: "eco_50", label: "Eco 50 °C", minutes: 225, kwh: 0.8, peak_w: 2100 });
  assert.equal(hasOwnPrograms({ programs: [] }), false);
  // Elke keer een verse kopie, zodat bewerken de opgave zelf niet aanraakt.
  assert.notEqual(defaultPrograms()[0], defaultPrograms()[0]);
});
proef("de sleutel uit een naam is dezelfde als in planner.py", () => {
  assert.equal(programKey("Glas 40 °C"), "glas_40_c");
  assert.equal(programKey("Auto 45 tot 65 °C"), "auto_45_tot_65_c");
  assert.equal(programKey(""), "programma");
});
proef("programOf vindt een programma op de sensorwaarde, in de eigen tabel, met de meting erover", () => {
  const device = {
    id: "vw", type: "vaatwasser", brand: "home_connect",
    programs: [
      { key: "eco_50", label: "Eco 50 °C", minutes: 180, kwh: 0.6, peak_w: 2000 },
      { key: "", label: "Glas 40 °C", minutes: 90, kwh: 0.5, peak_w: 1800 },
    ],
  };
  assert.equal(programOf(device, "dishcare_dishwasher_program_eco_50").minutes, 180);
  assert.equal(programOf(device, "Dishcare.Dishwasher.Program.Eco50").minutes, 180);
  assert.equal(programOf(device, "glas_40_c").label, "Glas 40 °C");
  assert.equal(programOf(device, "Glas 40 °C").key, "glas_40_c");
  assert.equal(programOf(device, "iets_anders"), undefined);
  const settings = { program_measured: [{ device: "vw", key: "eco_50", minutes: 200, kwh: 0.95, runs: 2 }] };
  const gemeten = programOf(device, "dishcare_dishwasher_program_eco_50", settings);
  assert.equal(gemeten.minutes, 200);
  assert.equal(gemeten.kwh, 0.95);
  assert.equal(gemeten.measured, true);
  // De meting van een ander apparaat telt niet mee.
  assert.equal(programOf({ ...device, id: "ander" }, "dishcare_dishwasher_program_eco_50", settings).measured, undefined);
});
proef("de programmakeuze op de kaart: de entiteit bij een slimme machine, de eigen tabel bij een domme", () => {
  const slim = { type: "vaatwasser", brand: "home_connect", entities: { program: "select.vaatwasser_programma" } };
  assert.deepEqual(programPicker(slim), { kind: "entity", entityId: "select.vaatwasser_programma" });
  // De eigenaar heeft de sensor "selected program" én, apart, de select om te kiezen.
  const vaatwasser58 = { type: "vaatwasser", brand: "home_connect",
                 entities: { program: "sensor.vaatwasser_programma", program_select: "select.vaatwasser_programmas" } };
  assert.deepEqual(programPicker(vaatwasser58), { kind: "entity", entityId: "select.vaatwasser_programmas" });
  assert.equal(programChooser(vaatwasser58).entityId, "select.vaatwasser_programmas");
  const alleenLezen = { type: "vaatwasser", brand: "home_connect", entities: { program: "sensor.vaatwasser_programma" } };
  assert.deepEqual(programPicker(alleenLezen), { kind: "missing" }, "een sensor is niet te kiezen, en de kaart zegt wat er mist");
  const dom = { type: "vaatwasser", brand: "overig", entities: {} };
  const keuze = programPicker(dom);
  assert.equal(keuze.kind, "table");
  assert.equal(keuze.options.length, DISHWASHER_PROGRAMS.length);
  assert.equal(programPicker({ type: "laadpaal", brand: "easee" }), undefined);
});
proef("de tabel bij Home Connect: de rijen van de machine, met de cijfers van de klant of de opgave", () => {
  const device = {
    id: "vw", type: "vaatwasser", brand: "home_connect",
    entities: { program: "sensor.vw_programma", program_select: "select.vw_programmas" },
    programs: [{ key: "eco_50", label: "Eco 50 °C", minutes: 180, kwh: 0.6, peak_w: 2000 }],
  };
  const feed = new Map([["select.vw_programmas", { state: "dishcare_dishwasher_program_eco_50", attributes: {
    options: ["dishcare_dishwasher_program_eco_50", "dishcare_dishwasher_program_kurz_60", "dishcare_dishwasher_program_glas_40"],
  } }]]);
  const options = programOptions(device, feed);
  assert.deepEqual(options.map((o) => [o.key, o.label]),
    [["eco_50", "Eco 50 °C"], ["kurz_60", "Express 60 °C"], ["glas_40", "Glas 40"]]);
  const rows = programRows(device, options);
  assert.equal(rows.length, 3, "één rij per optie van de machine");
  assert.deepEqual(rows[0], { key: "eco_50", label: "Eco 50 °C", minutes: 180, kwh: 0.6, peak_w: 2000 }, "de eigen cijfers");
  assert.deepEqual(rows[1], { key: "kurz_60", label: "Express 60 °C", minutes: 60, kwh: 1.05, peak_w: 2200 }, "de opgave");
  assert.deepEqual(rows[2], { key: "glas_40", label: "Glas 40", minutes: 120, kwh: 1, peak_w: 2000 }, "onbekend: een gok om te bewerken");
  assert.deepEqual(programOptions(device, new Map()), [], "zonder feed nog niets");
  assert.equal(programRows(device, []).length, 1, "zonder opties de eigen tabel");
});
proef("een domme vaatwasser is handmatig en heeft een vermogenssensor nodig", () => {
  const dom = { type: "vaatwasser", brand: "overig", controllable: true, entities: {}, entity: "" };
  assert.equal(isManualProgram(dom), true);
  assert.deepEqual(missingForControl(dom), ["Vermogenssensor"]);
  assert.deepEqual(missingForControl({ ...dom, entity: "sensor.stekker" }), []);
  assert.equal(isManualProgram({ type: "vaatwasser", brand: "home_connect" }), false);
  assert.equal(isManualProgram({ type: "laadpaal", brand: "overig" }), false);
});

// --- het meldingenscherm -----------------------------------------------------
//
// De eigenaar op 04-09-2026: "daarom wil ik ook een soort geschiedenis meldingen
// scherm." De lijst komt van de server, de nieuwste eerst, en wordt per dag
// gegroepeerd: Vandaag, Gisteren, en daarna de dag bij naam.

const { groepeer, dagkop, zeef, dagen, zichtbaar, naamVanTelefoon, STANDAARD_SOORTEN } = await import(
  "../custom_components/domotiapp_coach/frontend/src/views/notifications.js"
);

// De eigenaar op 06-09-2026: "de admin voegt de personen toe, en die persoon ziet
// alleen zichzelf."
proef("een bewoner ziet alleen zichzelf, de admin iedereen", () => {
  const mensen = [
    { id: "p-1", name: "Bewoner", target: "mobile_app_telefoon", user_id: "u-1" },
    { id: "p-2", name: "Partner", target: "mobile_app_partner", user_id: "u-partner" },
    { id: "p-3", name: "Tablet", target: "mobile_app_tablet", user_id: "" },
    { id: "p-4", name: "leeg", target: "" },
  ];
  assert.deepEqual(zichtbaar(mensen, { id: "u-x", is_admin: true }).map((p) => p.id), ["p-1", "p-2", "p-3"]);
  assert.deepEqual(zichtbaar(mensen, { id: "u-partner", is_admin: false }).map((p) => p.id), ["p-2"]);
  assert.deepEqual(zichtbaar(mensen, { id: "u-niemand", is_admin: false }), [], "niet gekoppeld: niets");
  assert.deepEqual(zichtbaar(mensen, null).length, 3, "zonder gebruiker (het voorbeeld) alles");
  assert.equal(naamVanTelefoon("mobile_app_iphone_van_de_keuken"), "Iphone van de keuken");
  assert.equal(naamVanTelefoon(""), "");
  assert.deepEqual(STANDAARD_SOORTEN, { kritiek: true, melding: true, besluit: false, belasting: true },
    "een nieuwe persoon krijgt alles behalve de besluiten, net als op de server");
});
const Meldingen = geregistreerd.get("dac-view-notifications");
assert.ok(Meldingen, "het meldingenscherm hoort zich te registreren");

proef("meldingen worden per dag gegroepeerd, de nieuwste eerst", () => {
  const nu = new Date(2026, 8, 6, 8, 0);
  const groepen = groepeer([
    { at: "2026-09-06T04:44:00", message: "Ford aan Laadpaal is vol." },
    { at: "2026-09-05T13:40:00", message: "De accustand van Ford meldt al 10 minuten niets." },
    { at: "2026-09-05T11:10:00", message: "De status van Laadpaal meldt al 10 minuten niets." },
    { at: "2026-09-04T19:01:00", message: "De coach wil laden maar weet niet hoe vol hij is." },
    { at: "", message: "zonder tijd hoort er niet in" },
  ], nu);
  assert.deepEqual(groepen.map((g) => g.kop), ["Vandaag", "Gisteren", "vrijdag 4 september"]);
  assert.deepEqual(groepen[1].rijen.map((r) => r.tijd), ["13:40", "11:10"]);
  assert.equal(groepen[0].rijen[0].tekst, "Ford aan Laadpaal is vol.");
  assert.equal(groepen[0].rijen[0].soort, "melding", "zonder kind is het een melding van vroeger");
  const besluit = groepeer([
    { at: "2026-09-05T09:42:00", message: "Laadpaal: laden op 6 A. Er is 0,3 kW zon over.", kind: "besluit" },
  ], nu)[0].rijen[0];
  assert.equal(besluit.soort, "besluit", "wat de coach deed heet een besluit");
  assert.equal(dagkop(new Date(2025, 11, 24), nu), "woensdag 24 december 2025", "een ander jaar krijgt het jaar erbij");
});

// De eigenaar op 05-09-2026: "dat je op normale en kritieke meldingen kan filteren
// en op de tijd."
proef("het filter zeeft op soort en op dag", () => {
  const nu = new Date(2026, 8, 6, 8, 0);
  const items = [
    { at: "2026-09-06T04:44:00", message: "Ford aan Laadpaal is vol." },
    { at: "2026-09-05T13:40:00", message: "De accustand van Ford meldt al 10 minuten niets.", kind: "kritiek" },
    { at: "2026-09-05T09:42:00", message: "Laadpaal: laden op 6 A.", kind: "besluit" },
    { at: "2026-09-04T19:01:00", message: "De coach wil laden maar weet niet hoe vol hij is.", kind: "kritiek" },
  ];
  assert.equal(zeef(items).length, 4, "zonder filter blijft alles staan");
  assert.deepEqual(zeef(items, { soort: "besluit" }).map((i) => i.at), ["2026-09-05T09:42:00"]);
  assert.equal(zeef(items, { soort: "melding" }).length, 3, "meldingen zijn alles behalve besluiten, kritiek erbij");
  assert.deepEqual(zeef(items, { soort: "kritiek" }).map((i) => i.at),
    ["2026-09-05T13:40:00", "2026-09-04T19:01:00"]);
  assert.deepEqual(zeef(items, { dag: "2026-09-05" }).map((i) => i.at),
    ["2026-09-05T13:40:00", "2026-09-05T09:42:00"], "één dag");
  assert.deepEqual(zeef(items, { soort: "kritiek", dag: "2026-09-05" }).map((i) => i.at),
    ["2026-09-05T13:40:00"], "soort en dag samen");
  assert.deepEqual(dagen(items, nu), [
    { sleutel: "2026-09-06", kop: "Vandaag" },
    { sleutel: "2026-09-05", kop: "Gisteren" },
    { sleutel: "2026-09-04", kop: "vrijdag 4 september" },
  ], "de dagkeuze kent elke dag één keer, de nieuwste eerst");
});

proef("het scherm tekent een kop per dag en een rij per melding", () => {
  const knopen = new Map();
  const maak = () => {
    const kinderen = [];
    return {
      className: "", textContent: "", kinderen,
      append(...items) { kinderen.push(...items); },
      replaceChildren(...items) { kinderen.length = 0; kinderen.push(...items); },
    };
  };
  knopen.set("#lijst", maak());
  globalThis.document.createElement = () => maak();
  const el = Object.create(Meldingen.prototype);
  el.$ = (kiezer) => knopen.get(kiezer) ?? null;
  el.$$ = () => [];
  el.geladen_ = true;
  el.filter_ = { soort: "alles", dag: "" };
  // Een dag binnen de twee weken die de geschiedenis toont (v0.101.5).
  const d = new Date();
  d.setDate(d.getDate() - 1);
  const dag = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  el.items_ = [
    { at: `${dag}T13:40:00`, message: "De accustand van Ford meldt al 10 minuten niets.", kind: "kritiek" },
    { at: `${dag}T11:10:00`, message: "De status van Laadpaal meldt al 10 minuten niets." },
    { at: `${dag}T09:42:00`, message: "Laadpaal: laden op 6 A.", kind: "besluit" },
  ];
  el.paint_();
  const lijst = knopen.get("#lijst").kinderen;
  assert.equal(lijst.length, 4, "een dagkop en drie rijen");
  assert.equal(lijst[0].className, "dag");
  assert.equal(lijst[1].className, "rij kritiek", "kritiek valt op");
  assert.equal(lijst[2].className, "rij melding", "een melding krijgt een kader");
  assert.equal(lijst[3].className, "rij besluit", "een besluit staat er kaal tussen");
  // Vóór de volgende paint_, want die leegt dezelfde kinderen-lijst.
  assert.deepEqual(lijst[1].kinderen.map((k) => k.textContent),
    ["13:40", "De accustand van Ford meldt al 10 minuten niets."]);

  el.filter_ = { soort: "kritiek", dag: "" };
  el.paint_();
  assert.equal(knopen.get("#lijst").kinderen.length, 2, "met het filter op kritiek blijft één rij over");
  el.filter_ = { soort: "kritiek", dag: "2026-09-04" };
  el.paint_();
  assert.match(knopen.get("#lijst").kinderen[0].textContent, /aan dit filter/, "een leeg filter zegt dat het het filter is");
  el.filter_ = { soort: "alles", dag: "" };

  el.items_ = [];
  el.paint_();
  assert.match(knopen.get("#lijst").kinderen[0].textContent, /twee weken niets gemeld/, "leeg is een zin, geen leeg scherm");
});

// --- Bespaard: de laadbeurten opgeteld --------------------------------------
//
// De eigenaar op 05-09-2026: "een overzichtje wat we hebben bespaard, per dag, week,
// maand, jaar, van elk apparaat." Het rekenwerk per beurt zit in de coach; hier
// wordt alleen opgeteld, en een beurt zonder prijs telt niet mee in het geld.

const { beurtenIn, totalen, perApparaat, opmerking, woorden, soort, delen } = await import(
  "../custom_components/domotiapp_coach/frontend/src/savings.js"
);

// De eigenaar op 07-09-2026, bij de eerste vaatwasserbeurt onder Bespaard: "hij heeft
// het hier over de paal, maar dat moet vaatwasser zijn. Ook kan je niet een
// vaatwasser inpluggen."
proef("de woorden van Bespaard volgen wat er in de lijst staat", () => {
  const auto = { kind: "laden", name: "Laadpaal" };
  const oud = { name: "Laadpaal" };
  const vaat = { kind: "programma", name: "Vaatwasser" };
  assert.equal(soort(oud), "laden", "een beurt van voor v0.57.2 is een laadbeurt");
  assert.deepEqual([woorden([auto]).wanneer, woorden([auto]).hoeveel, woorden([auto]).vanaf],
    ["Ingeplugd", "Geladen", "Vanaf inpluggen"]);
  assert.deepEqual([woorden([vaat]).wanneer, woorden([vaat]).hoeveel, woorden([vaat]).vanaf],
    ["Vrijgegeven", "Verbruikt", "Meteen starten"]);
  assert.ok(!woorden([vaat]).uitleg.includes("paal") && !woorden([vaat]).uitleg.includes("inplug"),
    "over een vaatwasser geen paal en geen inpluggen");
  assert.deepEqual([woorden([auto, vaat]).wanneer, woorden([auto, vaat]).hoeveel, woorden([auto, vaat]).vanaf],
    ["Vanaf", "Verbruikt", "Zonder coach"]);
  assert.equal(woorden([]).wanneer, "Ingeplugd");
  assert.equal(opmerking({ ...vaat, resumed: true, ref_price: null, price_unknown: true, complete: true }),
    "na een herstart, prijs bij vrijgeven onbekend");
});

proef("bespaard telt per periode en per apparaat op, zonder verzonnen geld", () => {
  const beurten = [
    { id: "a:1", device: "a", name: "Laadpaal", plugged_at: "2026-09-04T19:01:00", ended: "2026-09-06T04:09:00",
      kwh: 66.1, solar_kwh: 6.9, paid: 9.5, ref_price: 0.36, ref_cost: 23.8, saved: 14.3, solar_saved: 1.3, price_unknown: false, complete: true },
    { id: "a:2", device: "a", name: "Laadpaal", plugged_at: "2026-09-02T18:00:00", ended: "2026-09-03T05:00:00",
      kwh: 20, solar_kwh: 0, paid: 4, ref_price: 0.3, ref_cost: 6, saved: 2, price_unknown: false, complete: true },
    { id: "b:1", device: "b", name: "Vaatwasser", plugged_at: "2026-09-05T20:00:00", ended: null,
      kwh: 1.2, solar_kwh: 0, paid: 0, ref_price: null, ref_cost: null, saved: null, price_unknown: true, complete: false },
  ];
  const week = beurtenIn(beurten, new Date(2026, 8, 5), new Date(2026, 8, 7));
  assert.deepEqual(week.map((b) => b.id), ["a:1", "b:1"], "een beurt valt op zijn eind, of op nu als hij loopt; de nieuwste eerst");
  const t = totalen(week);
  assert.equal(t.beurten, 2);
  assert.ok(Math.abs(t.kwh - 67.3) < 1e-9, "de kilowatturen tellen altijd mee");
  assert.equal(t.saved, 14.3, "het geld alleen van beurten met een prijs");
  assert.ok(Math.abs(t.solar_saved - 1.3) < 1e-9 && Math.abs(t.wait_saved - 13) < 1e-9, "bespaard in twee delen: door de zon en door te wachten");
  assert.deepEqual(delen(beurten[1]), { zon: null, wachten: 2 }, "een beurt van voor v0.60.0 kent het zondeel niet; toen was bespaard alleen het wachten");
  assert.deepEqual(delen(beurten[2]), { zon: null, wachten: null }, "zonder prijs geen delen");
  assert.equal(t.onbekend, 1);
  assert.equal(t.lopend, 1);
  const per = perApparaat(beurtenIn(beurten, new Date(2026, 8, 1), new Date(2026, 8, 8)));
  assert.deepEqual(per.map((a) => [a.name, a.beurten, a.saved]), [["Laadpaal", 2, 16.3], ["Vaatwasser", 1, 0]]);
  assert.equal(opmerking(beurten[2]), "loopt nog, prijs onbekend");
  assert.equal(opmerking({ ...beurten[2], complete: true }), "prijs onbekend");
  assert.equal(opmerking({ ...beurten[0], resumed: true }), "na een herstart");
  assert.equal(opmerking({ ...beurten[0], resumed: true, ref_price: null, saved: null, price_unknown: true }),
    "na een herstart, prijs bij inpluggen onbekend", "midden in een beurt ingestapt: geen ijkpunt");
  assert.equal(opmerking(beurten[0]), "");
});

// --- de programmatabel in Apparaten: een gemeten rij staat op slot ----------
//
// De eigenaar op 07-09-2026, na de eerste echte beurt: "er staan nog wel mijn dingen
// in; moeten we niet iets maken dat als hij het gemeten heeft, dat dan
// geblokkeerd wordt tot je het wist?"

proef("een gemeten programma toont de meting, staat op slot en heeft wissen en overnemen", async () => {
  await import("../custom_components/domotiapp_coach/frontend/src/views/devices.js");
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.feed_ = {};
  el.draft_ = {
    devices: [{ id: "vw", type: "vaatwasser", brand: "overig", name: "Vaatwasser", controllable: true, entities: {}, programs: [] }],
    program_measured: [{ device: "vw", key: "kurz_60", minutes: 90, kwh: 0.825, peak_w: 2264, runs: 1, profile: [] }],
  };
  const html = el.programsHtml_(el.draft_.devices[0], 0);
  const rijen = html.split("<tr").slice(1);
  const gemeten = rijen.find((r) => r.includes('class="locked"'));
  assert.ok(gemeten, "de gemeten rij heeft de klasse locked");
  assert.ok(gemeten.includes("kurz_60") || gemeten.includes("Express"), "en is Express 60");
  assert.equal((gemeten.match(/ disabled/g) ?? []).length, 3, "duur, energie en piek staan op slot");
  assert.ok(gemeten.includes('value="90"') && gemeten.includes('value="0.83"') && gemeten.includes('value="2264"'),
    "de velden tonen de meting, niet de opgave");
  assert.ok(gemeten.includes("data-prog-take") && gemeten.includes("data-prog-forget"), "overnemen en wissen");
  const vrij = rijen.filter((r) => !r.includes('class="locked"'));
  assert.ok(vrij.length >= 1 && vrij.every((r) => !r.includes(" disabled")), "de andere rijen zijn gewoon te bewerken");
  assert.ok(html.includes("staat op slot"), "en de uitleg zegt het");
});

// De eerste woning op 29-09-2026: de schakelaar van de meetstekker onder de vaatwasser
// stond als vrijgaveschakelaar, en de coach zette na elke beurt de stroom eraf.
// Apparaten zegt het nu op de ingeklapte regel (v0.101.11).

proef("een vrijgaveschakelaar op de eigen stekker geeft een waarschuwing in Apparaten", async () => {
  const { releaseOnOwnPlug } = await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  const registratie = {
    "sensor.vw_vermogen": { device_id: "stekker" },
    "switch.vw_stekker": { device_id: "stekker" },
    "switch.keukenknop": { device_id: "knop" },
    "input_boolean.vw": {},
  };
  const vw = { id: "vw", type: "vaatwasser", brand: "overig", name: "Vaatwasser", controllable: true,
               entity: "sensor.vw_vermogen", entities: { release_switch: "switch.vw_stekker" }, programs: [] };
  assert.deepEqual(releaseOnOwnPlug(vw, registratie), ["release_switch"], "de stekker zelf");
  assert.deepEqual(releaseOnOwnPlug({ ...vw, entities: { release_now_switch: "switch.vw_stekker" } }, registratie),
    ["release_now_switch"], "ook voor nu starten");
  assert.deepEqual(releaseOnOwnPlug({ ...vw, entities: { release_switch: "switch.keukenknop" } }, registratie), [],
    "een schakelaar op een ander apparaat is goed");
  assert.deepEqual(releaseOnOwnPlug({ ...vw, entities: { release_switch: "input_boolean.vw" } }, registratie), [],
    "een helper is goed");
  assert.deepEqual(releaseOnOwnPlug(vw, undefined), [], "zonder registratie weet het paneel het niet");
  assert.deepEqual(releaseOnOwnPlug({ ...vw, entity: "" }, registratie), [], "zonder vermogenssensor niets te vergelijken");

  await import("../custom_components/domotiapp_coach/frontend/src/views/devices.js");
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.hass_ = { entities: registratie };
  el.draft_ = { devices: [vw] };
  const regel = el.summary_(vw);
  assert.ok(regel.warn && regel.text.includes("stekker zelf") && regel.text.includes("stroom"), regel.text);
  const goed = { ...vw, entities: { release_switch: "input_boolean.vw" } };
  el.draft_ = { devices: [goed] };
  assert.ok(!el.summary_(goed).warn, "met een helper geen waarschuwing");
});

// De eigenaar op 29-09-2026: "bij het toevoegen van een vaatwasser: moet eerst
// vrijgegeven worden. Als je die aanzet verschijnt er een invulveld voor je helper of
// knop, en de kaart toont Ingeruimd en dicht. Staat het vinkje uit, dan mag de
// vaatwasser gewoon draaien met de coach als de klep dicht zit, en dan heb je ook
// geen knop vrijgeven op de kaart." (v0.102.0)

proef("moet eerst vrijgegeven worden: aan toont de vrijgavevelden, uit is klep dicht", async () => {
  const { needsRelease, canSkipRelease, brandFields, missingForControl } =
    await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  const hc = { id: "vw", type: "vaatwasser", brand: "home_connect", name: "Vaatwasser", controllable: true,
               entity: "sensor.vw_vermogen", entities: { start: "button.vw_start", status: "sensor.vw_status",
               program: "select.vw_programma" }, programs: [] };
  const sleutels = (d) => brandFields(d).map((f) => f.key);
  assert.equal(canSkipRelease(hc), true, "Home Connect ziet de klep en kan starten");
  assert.equal(needsRelease(hc), true, "zonder keuze: eerst vrijgeven, zoals altijd");
  assert.ok(["release_switch", "release_now_switch", "release_button"].every((k) => sleutels(hc).includes(k)),
    "met vrijgave: schakelaar, nu starten en knop");
  const klep = { ...hc, release_required: false };
  assert.equal(needsRelease(klep), false, "vinkje uit: geen vrijgaveknop op de kaart");
  assert.ok(!sleutels(klep).some((k) => k.startsWith("release_")), "en geen vrijgavevelden");
  assert.ok(sleutels(klep).includes("door"), "de deurstand blijft");
  assert.deepEqual(missingForControl(klep), ["Deurstand"], "en is dan nodig");
  assert.deepEqual(missingForControl({ ...klep, entities: { ...klep.entities, door: "binary_sensor.vw_deur" } }), []);
  const dom = { id: "d", type: "vaatwasser", brand: "overig", controllable: true, entity: "sensor.d", entities: {},
                release_required: false };
  assert.equal(canSkipRelease(dom), false, "een domme vaatwasser ziet de klep niet en kan niet starten");
  assert.equal(needsRelease(dom), true, "dus die vraagt altijd om een vrijgave");
  assert.ok(sleutels(dom).includes("release_button"), "met de knop erbij");

  await import("../custom_components/domotiapp_coach/frontend/src/views/devices.js");
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.draft_ = { devices: [hc, dom], installation: {} };
  assert.ok(el.controlHtml_(hc, 0).includes('data-field="release_required"'), "het vinkje staat bij Home Connect");
  assert.ok(el.controlHtml_(hc, 0).includes("checked"), "standaard aan");
  assert.ok(!el.controlHtml_(dom, 1).includes('data-field="release_required"'), "en niet bij een domme vaatwasser");

  // Welke druk telt: de soorten van de knop zelf, en leeg is elke druk.
  el.hass_ = { states: { "event.knop": { state: "unknown", attributes: { event_types: ["single", "double", "long"] } } } };
  const knop = { ...hc, entities: { ...hc.entities, release_button: "event.knop" }, release_press: "double" };
  const html = el.pressHtml_(knop, 0);
  assert.ok(html.includes('<option value="">Elke druk</option>') || html.includes('value=""'), html);
  assert.ok(["single", "double", "long"].every((s) => html.includes(`value="${s}"`)), html);
  assert.ok(html.includes('value="double" selected'), "de gekozen soort staat geselecteerd");
  assert.equal(el.pressHtml_(hc, 0), "", "zonder knop geen keuze");
});

// De eigenaar op 16-09-2026: "ik wil een optie hebben op de kaart dat ik kan aangeven
// tot hoever de bus laadt. Mijne laadt tot 80% namelijk maar ik kan hem ook op
// 100% instellen."

proef("het autoprofiel heeft een doel, standaard 100, en een lege invoer is geen nul", async () => {
  await import("../custom_components/domotiapp_coach/frontend/src/views/devices.js");
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.feed_ = {};
  const paal = {
    id: "paal", type: "laadpaal", brand: "easee", name: "Laadpaal", controllable: true,
    entities: {}, cars: [{ id: "auto", name: "Bus", capacity_kwh: 19.7, phases: "three", max_amps: 0 }],
  };
  const html = el.carsHtml_(paal, 0);
  assert.ok(html.includes('data-car-field="target_percent"'), "het veld staat er");
  assert.ok(html.includes("Laadt tot"), "en heet naar wat het doet");
  // Een auto zonder het veld is een oude instelling: die laadt gewoon vol.
  const doelVeld = (h) => h.match(/data-car-field="target_percent"[\s\S]*?value="(\d+)"/)?.[1];
  assert.equal(doelVeld(html), "100", "zonder ingevuld doel staat er 100");
  const tot80 = el.carsHtml_({ ...paal, cars: [{ ...paal.cars[0], target_percent: 80 }] }, 0);
  assert.equal(doelVeld(tot80), "80", "en een ingevuld doel staat er zoals het is");
  // De server weigert alles onder de 10, dus een veld dat leeggemaakt wordt mag
  // geen nul opleveren: dat zou een foutmelding geven over iets wat de klant
  // niet deed.
  assert.ok(html.includes('min="10"') && html.includes('max="100"'), "de invoer blijft binnen bereik");
});

proef("een nieuwe auto begint met het merk, en een Tesla krijgt de wekknop en de keuze", async () => {
  await import("../custom_components/domotiapp_coach/frontend/src/views/devices.js");
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.feed_ = {};
  const paal = { id: "paal", type: "laadpaal", brand: "easee", name: "Laadpaal", controllable: true, entities: {} };
  const nieuw = el.carsHtml_({ ...paal, cars: [{ id: "a", name: "", capacity_kwh: 0, brand: "" }] }, 0);
  assert.ok(nieuw.includes('data-car-field="brand"'), "het merk staat er");
  assert.ok(!nieuw.includes('data-car-field="capacity_kwh"'), "en verder nog niets, tot het merk gekozen is");
  const ford = el.carsHtml_({ ...paal, cars: [{ id: "a", name: "Bus", capacity_kwh: 19.7, brand: "ford" }] }, 0);
  assert.ok(ford.includes('data-car-field="capacity_kwh"'), "een Ford heeft zijn velden");
  assert.ok(!ford.includes("data-car-wake="), "maar geen wekknop");
  const tesla = el.carsHtml_({ ...paal, cars: [{ id: "a", name: "Model Y", capacity_kwh: 75, brand: "tesla", wake_mode: "hourly" }] }, 0);
  assert.ok(tesla.includes("data-car-wake="), "een Tesla heeft de wekknop");
  assert.ok(tesla.includes('data-car-wake-mode="0:0:manual"') && tesla.includes('data-car-wake-mode="0:0:hourly"'), "en de keuze");
  assert.ok(tesla.includes('data-car-wake-mode="0:0:hourly"\n                        aria-pressed="true"'), "met de gekozen stand ingedrukt");
  // Een profiel van voor er merken waren houdt zijn velden.
  const oud = el.carsHtml_({ ...paal, cars: [{ id: "a", name: "Bus", capacity_kwh: 19.7 }] }, 0);
  assert.ok(oud.includes('data-car-field="capacity_kwh"'));
  // De actieradius (v0.106.0) bij elk merk, bij een Tesla met de naam van zijn sensor.
  assert.ok(ford.includes('data-car-range="0:0"') && tesla.includes('data-car-range="0:0"'), "het veld voor de actieradius");
  assert.ok(tesla.includes('"Battery range"'), "bij een Tesla met de naam van de sensor");
});

proef("de vakantiestand staat in het formulier en op de kaart", async () => {
  await import("../custom_components/domotiapp_coach/frontend/src/views/devices.js");
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.feed_ = {};
  const accu = { id: "b", type: "thuisbatterij", brand: "anker", name: "Anker", controllable: true, entities: {},
    battery: { ...defaultBattery("anker"), holiday: true, holiday_max_percent: 60 } };
  const html = el.batteryHtml_(accu, 0);
  assert.ok(html.includes('data-bat-field="holiday"') && html.includes('data-bat-field="holiday_max_percent"'));
  assert.ok(html.includes('data-bat-holiday="0"') && !html.includes('hidden data-bat-holiday="0"'), "de grens is zichtbaar als de stand aanstaat");
  assert.equal(html.split('data-bat-field="holiday_max_percent"').length - 1, 1, "de grens staat precies een keer in het formulier (23-09-2026: hij stond er twee keer)");
  assert.equal(html.split('data-bat-field="holiday"').length - 1, 1, "de vink staat precies een keer");
  const rijen = batteryRows({ kind: "batterij", mode: "nul", mode_name: "Nul op de meter", holiday: true, ceiling: 60 });
  assert.ok(rijen.some((r) => r.label === "Vakantiestand" && r.text.includes("60%")), JSON.stringify(rijen));
});

// De eigenaar op 29-09-2026: "de coach moet niet meer de batterij sturen, dat vinkje moet
// theoretisch gewoon standaard aan staan" (v0.101.10).
proef("een nieuwe batterij doet standaard zelf nul op de meter, en het vinkje staat aan", async () => {
  assert.equal(defaultBattery("anker").self_zero, true);
  assert.equal(defaultBattery("overig").self_zero, true);
  await import("../custom_components/domotiapp_coach/frontend/src/views/devices.js");
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.feed_ = {};
  const nieuw = { id: "n", type: "thuisbatterij", brand: "anker", name: "", controllable: true, entities: {}, battery: {} };
  const html = el.batteryHtml_(nieuw, 0);
  assert.match(html, /data-bat-field="self_zero" data-index="0"\s+checked/, "het vinkje staat aan zonder dat er iets is opgeslagen");
  assert.ok(html.includes("Staat standaard aan"), "de uitleg zegt dat het standaard is");
  const uit = el.batteryHtml_({ ...nieuw, battery: { self_zero: false } }, 0);
  assert.doesNotMatch(uit, /data-bat-field="self_zero" data-index="0"\s+checked/, "uitgezet blijft uit");
});

// --- het plan van de batterij op de kaart ------------------------------------------
//
// De eigenaar op 22-09-2026: "ik kan nu niet zien wat de coach van plan is met
// de batterij." Uren met dezelfde stand worden één regel.
const { planRegels } = await import("../custom_components/domotiapp_coach/frontend/src/battery.js");

proef("het plan vat de uren samen per stand, met accustand, kWh en prijs", () => {
  const dag = new Date().toISOString().slice(0, 10);
  const uur = (h, mode, soc, grid = 0, price = 0.25) => ({
    start: `${dag}T${String(h).padStart(2, "0")}:00:00`, end: `${dag}T${String(h + 1).padStart(2, "0")}:00:00`,
    mode, soc, grid_kwh: grid, kwh: grid, price,
  });
  const regels = planRegels([
    uur(18, "nul", 80), uur(19, "nul", 70), uur(20, "nul", 60),
    uur(21, "netladen", 75, 2.1, 0.12), uur(22, "netladen", 90, 2.1, 0.14),
    uur(23, "nul", 85),
  ]);
  assert.equal(regels.length, 3);
  assert.equal(regels[0].label, "18:00 tot 21:00");
  assert.ok(regels[0].text.startsWith("nul op de meter"));
  assert.ok(regels[0].text.includes("60%"));
  assert.ok(regels[1].text.includes("van 60 naar 90%"), regels[1].text);
  assert.ok(regels[1].text.includes("4,2 kWh") && regels[1].text.includes("0,130"), regels[1].text);
  assert.deepEqual(planRegels([]), []);
  // Sinds v0.85.0 staat het plan niet meer op de kaart maar in de pop-up.
  const rijen = batteryRows({ kind: "batterij", mode: "nul", mode_name: "Nul op de meter", hours: [uur(18, "nul", 80)] });
  assert.ok(!rijen.some((r) => r.label === "Plan"), "het plan hoort in de pop-up, niet op de kaart");
});

// --- het plan van de batterij in een pop-up (v0.85.0) ------------------------------
//
// De eigenaar op 23-09-2026: "ik wil het plan van de accu net als de laadpaal
// hebben, zo'n pop-up; nu is de kaart best groot en onoverzichtelijk."
const { batterijVooruit, nachtConclusie } = await import("../custom_components/domotiapp_coach/frontend/src/battery.js");

proef("de pop-up van de batterij: vier vakken, een rij per uur, netladen gekleurd, morgen na middernacht", () => {
  const besluit = {
    kind: "batterij", soc: 62, capacity_kwh: 14.6, balance_kwh: 17.06, value: 0.301, buy_below: 0.2588,
    reason: "Hij houdt de meter op nul.",
    plan: "Tot morgenvroeg verwacht hij 15,7 kWh zon. Je houdt naar verwachting 17,1 kWh over in je accu.",
    hours: [
      { start: "2026-09-23T13:16:57.071", end: "2026-09-23T14:00:00", mode: "standby", kwh: 0, grid_kwh: 0, soc: 62, price: 0.1944 },
      { start: "2026-09-23T15:00:00", end: "2026-09-23T16:00:00", mode: "nul", kwh: 2.53, grid_kwh: 0, soc: 77, price: 0.253 },
      { start: "2026-09-23T19:00:00", end: "2026-09-23T20:00:00", mode: "nul", kwh: -0.32, grid_kwh: 0, soc: 92, price: 0.404 },
      { start: "2026-09-24T02:00:00", end: "2026-09-24T03:00:00", mode: "netladen", kwh: 2.1, grid_kwh: 2.1, soc: 90, price: 0.12 },
    ],
  };
  const v = batterijVooruit(besluit);
  const kop = Object.fromEntries(v.kop.map((k) => [k.label, `${k.waarde} | ${k.bij}`]));
  assert.equal(kop["Accu nu"], "62% | van 14,6 kWh");
  assert.equal(kop["Morgenvroeg"], "17,1 kWh | over na de nacht");
  assert.equal(kop["Van het net"], "2,1 kWh | gemiddeld € 0,120");
  // Sinds v0.102.3 onder welke prijs bijkopen loont, naast de prijs van nu; de
  // waarde per kWh in de batterij (€ 0,301) staat er niet meer.
  assert.equal(kop["Bijkopen loont"], "onder € 0,259 | nu € 0,194");
  assert.equal(kop["Een kWh erin"], undefined);
  assert.equal(v.uren.length, 4);
  assert.equal(v.uren[0].tijd, "13:16");
  assert.equal(v.uren[0].wat, "Standby");
  assert.equal(v.uren[1].wat, "Nul op de meter, 2,5 kWh erin");
  assert.equal(v.uren[2].wat, "Nul op de meter, 0,3 kWh eruit");
  assert.equal(v.uren[3].tijd, "morgen 02:00");
  assert.equal(v.uren[3].wat, "Laden van het net, 2,1 kWh van het net");
  const deels = batterijVooruit({ ...besluit, hours: [{ ...besluit.hours[3], kwh: 3.0, grid_kwh: 1.2 }] });
  assert.equal(deels.uren[0].wat, "Laden van het net, 3,0 kWh erin, waarvan 1,2 kWh van het net");
  assert.deepEqual(v.uren.map((u) => u.net), [false, false, false, true]);
  assert.equal(v.uren[3].soc, "90%");
  assert.equal(v.voet, besluit.plan);

  const tekort = batterijVooruit({ ...besluit, balance_kwh: -2.34, hours: [] });
  assert.equal(tekort.kop.find((k) => k.label === "Morgenvroeg").waarde, "−2,3 kWh");
  assert.equal(tekort.kop.find((k) => k.label === "Van het net").waarde, "niets");
  assert.equal(tekort.kop.find((k) => k.label === "Bijkopen loont").bij, "per kWh van het net", "zonder uren geen prijs van nu");
  assert.equal(batterijVooruit({ ...besluit, buy_below: null }).kop.find((k) => k.label === "Bijkopen loont"), undefined,
    "een volle batterij: geen vak");
  assert.equal(batterijVooruit({ kind: "laadpaal" }), null);
});

proef("op de kaart van de batterij staat van de nachtzin alleen de conclusie", () => {
  const plan = "Tot morgenvroeg verwacht hij 15,7 kWh zon, het huis vraagt 4,9 kWh en er zit 8,3 kWh in de batterij, goed voor 6,2 kWh na het verlies. Je houdt naar verwachting 17,1 kWh over in je accu.";
  assert.equal(nachtConclusie({ kind: "batterij", balance_kwh: 17.06, plan }), "Je houdt naar verwachting 17,1 kWh over in je accu.");
  assert.equal(nachtConclusie({ kind: "batterij", balance_kwh: -1, plan: "Tot morgenvroeg 1,5 kWh zon. Je komt naar verwachting 1,0 kWh tekort om de nacht te overbruggen; hij laadt bij als de stroom goedkoop genoeg is." }),
    "Je komt naar verwachting 1,0 kWh tekort om de nacht te overbruggen; hij laadt bij als de stroom goedkoop genoeg is.");
  // Zonder balans (geen rendement, geen accustand) blijft de zin zoals hij is.
  assert.equal(nachtConclusie({ kind: "batterij", plan: "Hij weet de accustand niet." }), "Hij weet de accustand niet.");
});

proef("de knop Wat gaat hij doen staat er bij een batterij zodra er een plan per uur is", async () => {
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf-8");
  assert.match(bron, /besluit\.kind === "batterij"\s*\?\s*!\(besluit\.hours \?\? \[\]\)\.length/, "zichtbaarheid van data-ahead bij een batterij");
  const sheet = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/plan-ahead-sheet.js", import.meta.url), "utf-8");
  assert.ok(sheet.includes("batterijVooruit(this.besluit_)"));
});

// --- de prijsgrafiek in de pop-up (v0.86.0) ----------------------------------------
//
// De bewoner van de eerste woning op 23-09-2026, over evcc: "met groene balkjes
// laat hij precies zien welke (goedkope) uren hij gaat laden, en wat de
// gemiddelde prijs wordt." De eigenaar: "ook voor de batterij."
const { prijsBalken } = await import("../custom_components/domotiapp_coach/frontend/src/prijsgrafiek.js");

proef("de prijsgrafiek: groen waar hij laadt, het gemiddelde gewogen naar de kWh van het net", () => {
  const u = (h, price, groen, kwh) => ({ start: `2026-09-23T${String(h).padStart(2, "0")}:00:00`, end: `2026-09-23T${String(h + 1).padStart(2, "0")}:00:00`, price, groen, kwh });
  const b = prijsBalken([u(12, 0.30, false, 0), u(13, 0.20, true, 1), u(14, 0.10, true, 3), u(15, 0.40, false, 0)]);
  assert.deepEqual(b.balken.map((x) => x.groen), [false, true, true, false]);
  // (0,20 x 1 + 0,10 x 3) / 4 = 0,125, en niet het kale gemiddelde 0,15.
  assert.ok(Math.abs(b.gemiddeld - 0.125) < 1e-9, String(b.gemiddeld));
  assert.equal(b.kwh, 4);
  // Het duurste uur is het hoogste staafje en de nullijn ligt onderaan.
  const hoogste = b.balken.reduce((a, x) => (x.h > a.h ? x : a));
  assert.equal(hoogste.tip, "15:00 tot 16:00: € 0,400");
  assert.equal(b.nul, 96);
  // Een tijd onder elk derde hele uur.
  assert.deepEqual(b.balken.map((x) => x.label), ["12", "", "", "15"]);
  assert.match(b.balken[1].tip, /hij laadt$/);
});

proef("de prijsgrafiek: een negatieve prijs zakt onder de nullijn, zon telt niet mee in het gemiddelde", () => {
  const u = (h, price, groen, kwh) => ({ start: `2026-09-23T${String(h).padStart(2, "0")}:00:00`, price, groen, kwh });
  const b = prijsBalken([u(12, 0.2, false, 0), u(13, -0.1, true, 2)]);
  assert.ok(b.nul < 96 && b.balken[1].y === b.nul, "het negatieve staafje begint op de nullijn en gaat omlaag");
  // Een laaduur dat helemaal op zon draait: geen kWh van het net, dus geen prijs om te middelen.
  const zon = prijsBalken([u(12, 0.2, true, 0), u(13, 0.3, false, 0)]);
  assert.equal(zon.gemiddeld, null);
  // Een vast contract heeft geen prijzen per uur: dan geen grafiek.
  assert.equal(prijsBalken([u(12, null, true, 1), u(13, null, false, 0)]), null);
  assert.equal(prijsBalken([]), null);
});

proef("de pop-up van de paal toont de prijsgrafiek met het gewogen gemiddelde van wat van het net komt", () => {
  const { el, knopen } = vooruitScherm(NACHT);
  el.paint_();
  const blok = knopen.get("#vooruit-prijs");
  assert.equal(blok.hidden, false);
  const kop = blok.kinderen[0].kinderen[1].kinderen;
  // 03:00: 11,0 kWh van het net tegen 0,2215; 04:00: 11,0 - 2,4 = 8,6 kWh tegen 0,2113.
  // (0,2215 x 11 + 0,2113 x 8,6) / 19,6 = 0,2170.
  assert.equal(kop[1].textContent, "€ 0,217", JSON.stringify(kop));
  // Een vast contract: geen prijzen, dus geen grafiek.
  const vast = vooruitScherm({ ...NACHT, blocks: NACHT.blocks.map((b) => ({ ...b, price: null })) });
  vast.el.paint_();
  assert.equal(vast.knopen.get("#vooruit-prijs").hidden, true);
});

proef("kwartierprijzen: een staafje per kwartier, en de lijst een regel per uur (v0.88.1)", async () => {
  const { perUur } = await import("../custom_components/domotiapp_coach/frontend/src/prijsgrafiek.js");
  const { paalPerUur } = await import("../custom_components/domotiapp_coach/frontend/src/plan-ahead-sheet.js");
  const k = (h, m, price, charging, kwh = 0) => ({
    start: `2026-09-23T${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:00`,
    end: `2026-09-23T${String(h + (m + 15 >= 60 ? 1 : 0)).padStart(2, "0")}:${String((m + 15) % 60).padStart(2, "0")}:00`,
    price, charging, kwh, why: charging ? "een van de goedkoopste manieren" : "duurder", amps: charging ? 16 : 0,
    groen: charging, solar_kwh: 0,
  });
  const blokken = [k(1, 0, 0.30, false), k(1, 15, 0.29, false), k(1, 30, 0.28, false), k(1, 45, 0.27, false),
    k(2, 0, 0.20, true, 2.75), k(2, 15, 0.19, true, 2.75), k(2, 30, 0.31, false), k(2, 45, 0.32, false)];
  const b = prijsBalken(blokken);
  assert.equal(b.balken.length, 8, "een staafje per kwartier");
  assert.equal(b.stap, 15);
  assert.deepEqual(perUur(blokken).map((g) => g.length), [4, 4]);
  const rijen = paalPerUur(blokken);
  assert.equal(rijen.length, 2, "twee regels: 01:00 en 02:00");
  assert.equal(rijen[1].charging, true);
  assert.match(rijen[1].why, /in 2 van de 4 kwartieren/);
  assert.ok(Math.abs(rijen[1].kwh - 5.5) < 1e-9 && Math.abs(rijen[1].kw - 11.0) < 1e-9, JSON.stringify(rijen[1]));
  assert.ok(Math.abs(rijen[1].price - 0.255) < 1e-9, "de gemiddelde prijs van het uur");
  // Uurprijzen blijven zoals ze zijn.
  const uren = [{ start: "2026-09-23T01:00:00", end: "2026-09-23T02:00:00", price: 0.3 },
    { start: "2026-09-23T02:00:00", end: "2026-09-23T03:00:00", price: 0.2 }];
  assert.deepEqual(perUur(uren).map((g) => g.length), [1, 1]);
  assert.equal(prijsBalken(uren).stap, 60);
  // De batterij: ook een regel per uur, met beide standen als ze wisselen.
  const acc = batterijVooruit({ kind: "batterij", soc: 50, hours: [
    { start: "2026-09-23T02:00:00", end: "2026-09-23T02:15:00", mode: "netladen", kwh: 0.8, grid_kwh: 0.8, soc: 55, price: 0.19 },
    { start: "2026-09-23T02:15:00", end: "2026-09-23T02:30:00", mode: "netladen", kwh: 0.8, grid_kwh: 0.8, soc: 60, price: 0.18 },
    { start: "2026-09-23T02:30:00", end: "2026-09-23T02:45:00", mode: "nul", kwh: 0, grid_kwh: 0, soc: 60, price: 0.31 },
    { start: "2026-09-23T02:45:00", end: "2026-09-23T03:00:00", mode: "nul", kwh: 0, grid_kwh: 0, soc: 60, price: 0.32 },
  ] });
  assert.equal(acc.uren.length, 1);
  assert.equal(acc.uren[0].wat, "Laden van het net en nul op de meter, 1,6 kWh van het net");
  assert.equal(acc.uren[0].soc, "60%");
});

proef("de pop-up zegt 'prijs per kwartier' bij kwartierprijzen", () => {
  const k = (m, charging) => ({ start: `2026-08-30T03:${String(m).padStart(2, "0")}:00`,
    end: `2026-08-30T03:${String(m + 14).padStart(2, "0")}:59`, price: 0.2 + m / 1000, charging, why: "x",
    solar_kwh: 0, kwh: charging ? 2.7 : 0, amps: charging ? 16 : 0, kw: charging ? 11 : 0 });
  const { el, knopen } = vooruitScherm({ ...NACHT, blocks: [k(0, false), k(15, true), k(30, true), k(45, false)] });
  el.paint_();
  const kop = knopen.get("#vooruit-prijs").kinderen[0].kinderen[0];
  assert.equal(kop.textContent, "Prijs per kwartier");
  assert.equal(knopen.get("#vooruit-uren").kinderen.length, 1, "een regel voor het hele uur");
});

proef("nog te laden: aan de paal, en wat er in de accu komt, gemeten of aangenomen (v0.94.0)", () => {
  const { el, knopen } = vooruitScherm({ ...NACHT, kwh_needed: 26.0, kwh_in_car: 23.4, efficiency: 0.9, efficiency_measured: false });
  el.paint_();
  const vak = knopen.get("#vooruit-kop").kinderen[0];
  const bij = vak.kinderen[2]?.textContent ?? "";
  assert.equal(vak.kinderen[1].textContent, "26,0 kWh");
  assert.equal(bij, "aan de paal; 23,4 kWh in de auto, 10% laadverlies (aangenomen, nog niet gemeten)");
  const gemeten = vooruitScherm({ ...NACHT, kwh_needed: 24.6, kwh_in_car: 23.4, efficiency: 0.95, efficiency_measured: true });
  gemeten.el.paint_();
  assert.match(gemeten.knopen.get("#vooruit-kop").kinderen[0].kinderen[2].textContent, /5% laadverlies \(gemeten aan deze auto\)/);
});

proef("de thuisbatterij helpt: in de kop, in de regel, en niet in wat van het net komt (v0.95.0)", () => {
  // De bewoner van de eerste woning op 23-09-2026: "de EV-laadplanning zou nu
  // moeten weten dat de accu mee gaat helpen."
  const blok = { start: "2026-08-29T23:00:00", end: "2026-08-30T00:00:00", price: 0.308,
    charging: true, why: "een van de goedkoopste manieren", solar_kwh: 0, kwh: 9.0, accu_kwh: 1.0, amps: 13, kw: 9.0 };
  const { el, knopen } = vooruitScherm({ ...NACHT, accu_kwh: 1.0, accu_to: 70, blocks: [blok] });
  el.paint_();
  const vakken = knopen.get("#vooruit-kop").kinderen;
  const laatste = vakken[vakken.length - 1].kinderen.map((k) => k.textContent);
  assert.deepEqual(laatste, ["Uit je thuisbatterij", "1,0 kWh", "tot hij op 70% staat"]);
  const rij = knopen.get("#vooruit-uren").kinderen[0].kinderen;
  assert.equal(rij[3].textContent, "Laden op 9,0 kW, waarvan 1,0 kWh uit je thuisbatterij: een van de goedkoopste manieren");
  const zonder = vooruitScherm({ ...NACHT });
  zonder.el.paint_();
  assert.ok(!zonder.knopen.get("#vooruit-kop").kinderen.some((v) => v.kinderen[0]?.textContent === "Uit je thuisbatterij"),
    "zonder hulp geen vak");
  const sheet = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/plan-ahead-sheet.js", import.meta.url), "utf-8");
  assert.ok(sheet.includes("- Number(b.accu_kwh || 0)"), "wat de batterij geeft komt niet van het net");
});

proef("het uurplan van de batterij zegt welke uren hij de auto helpt (v0.95.0)", () => {
  const v = batterijVooruit({
    kind: "batterij", soc: 78, capacity_kwh: 14.6, car_floor: 70,
    hours: [
      { start: "2026-09-23T23:00:00", end: "2026-09-24T00:00:00", mode: "nul", kwh: -1.2, grid_kwh: 0, car_kwh: 1.0, soc: 69, price: 0.308 },
      { start: "2026-09-24T00:00:00", end: "2026-09-24T01:00:00", mode: "nul", kwh: -0.2, grid_kwh: 0, car_kwh: 0, soc: 68, price: 0.319 },
    ],
  });
  assert.equal(v.uren[0].wat, "Nul op de meter, 1,2 kWh eruit, waarvan 1,0 kWh naar de auto");
  assert.equal(v.uren[1].wat, "Nul op de meter, 0,2 kWh eruit");
  const kop = v.kop.find((k) => k.label === "Naar de auto");
  assert.equal(`${kop.waarde} | ${kop.bij}`, "1,0 kWh | tot hij op 70% staat");
  assert.equal(batterijVooruit({ kind: "batterij", soc: 78, hours: [] }).kop.find((k) => k.label === "Naar de auto"), undefined);
});

proef("de pop-up tekent de grafiek bij de paal en bij de batterij", () => {
  const sheet = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/plan-ahead-sheet.js", import.meta.url), "utf-8");
  assert.equal(sheet.split("this.paintPrijs_(").length - 1, 3, "leeg maken, de paal, en de batterij");
  assert.ok(sheet.includes("Number(b.kwh) - Number(b.solar_kwh || 0)"), "bij de paal telt alleen wat van het net komt");
});

// --- de laadmodus zonder planning (v0.87.0) ----------------------------------------
//
// De eigenaar op 23-09-2026: "de modus is leidend (snel, continu of zon), tenzij er
// een planning ingesteld is. Geen planning, standaard terug naar zon, of welke
// voorkeursmodus dan ook."
proef("bij een stuurbare laadpaal kies je de modus zonder planning en het vermogen van continu", () => {
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.feed_ = {};
  el.draft_ = { installation: { circuits: [] }, devices: [] };
  const paal = { id: "p", type: "laadpaal", brand: "easee", controllable: true, device_id: "x",
    entities: { status: "sensor.s", limit: "number.l" }, charge_mode: "continu", continuous_amps: 10 };
  const html = el.controlHtml_(paal, 0);
  assert.ok(html.includes('data-field="charge_mode"'), "de keuzelijst staat erin");
  assert.ok(html.includes('value="continu" selected'), "met de keuze van de paal");
  assert.ok(html.includes('data-field="continuous_amps"') && html.includes('value="10"'));
  const oud = el.controlHtml_({ ...paal, charge_mode: undefined }, 0);
  assert.ok(oud.includes('value="goedkoopst" selected'), "een paal zonder keuze is goedkoopst, zoals hij altijd deed");
  const boiler = el.controlHtml_({ id: "b", type: "boiler", controllable: true, entities: { switch: "switch.b" } }, 0);
  assert.ok(!boiler.includes("charge_mode"), "een boiler heeft geen laadmodus");
});

proef("een nieuwe paal begint op zon, en de kaart heeft Continu en Zon naast Snel", () => {
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/devices.js", import.meta.url), "utf-8");
  assert.match(bron, /charge_mode: "zon",\s*continuous_amps: 6,/);
  const kaart = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf-8");
  assert.ok(kaart.includes('data-modus-naam="continu"') && kaart.includes('data-modus-naam="zon"'));
  assert.ok(kaart.includes("const modi = kan && !besluit.planned"), "alleen zonder planning");
  assert.ok(kaart.includes('type: "domotiapp_coach/coach/mode"'));
});

proef("op de kaart kies je per beurt tot hoeveel procent hij laadt (v0.88.0)", () => {
  const kaart = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf-8");
  assert.ok(kaart.includes('data-target-select="${slot}"'), "de keuzelijst staat op de kaart");
  assert.ok(kaart.includes("Zoals het autoprofiel ("), "met het doel uit het profiel als eerste keuze");
  assert.ok(kaart.includes('type: "domotiapp_coach/coach/target"'));
  assert.match(kaart, /percent: waarde === "" \? null : Number\(waarde\)/, "leeg is terug naar het profiel");
});

proef("onder 'hoe vol is de auto nu' staat wat de coach van de opgave maakt, en het veld heeft een %", () => {
  const kaart = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf-8");
  assert.ok(kaart.includes('<span class="soc-procent" aria-hidden="true">%</span>'));
  assert.ok(kaart.includes("sinds je ${Math.round(opgegeven)}% doorgaf is er "), "de zin met de kWh sinds de opgave");
  assert.ok(kaart.includes("Zegt de auto iets anders, vul dat in en druk op Doorgeven."));
});

proef("'hoe vol is de auto nu' loopt live mee, en wat de bewoner typt blijft staan tot hij doorgeeft (v0.98.0)", async () => {
  const { socVeld } = await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  assert.equal(socVeld({ percent: 32 }, 46.5), "47", "na een opgave de stand die de coach nu verwacht");
  assert.equal(socVeld({ percent: 32 }, null), "32", "weet de coach nog niets, dan de opgave zelf");
  assert.equal(socVeld(null, 46.5), "", "zonder opgave leeg: de sensor van de auto telt dan, of niets");
  assert.equal(socVeld({ percent: null }, 46.5), "");
  const kaart = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf-8");
  assert.ok(kaart.includes("const stand = socVeld(opgave, oordeel?.soc_now);"), "het veld toont de stand van nu");
  assert.ok(kaart.includes('field.dataset.bewerkt !== "1"'), "en overschrijft niet wat de bewoner net intypte");
  assert.ok(kaart.includes('field.addEventListener("input", () => { field.dataset.bewerkt = "1"; });'));
  assert.ok(kaart.includes("delete field.dataset.bewerkt;"), "na doorgeven loopt hij weer mee");
});

proef("bij de batterij de grens voor de auto, op Strategie de nachtstrategie (v0.90.0)", () => {
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.feed_ = {};
  const accu = { id: "b", type: "thuisbatterij", brand: "anker", name: "Anker", controllable: true, entities: {},
    battery: { ...defaultBattery("anker"), car_above: 40 } };
  const html = el.batteryHtml_(accu, 0);
  assert.ok(html.includes('data-bat-field="car_above"') && html.includes('value="40"'), "het veld met de grens");
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/strategy.js", import.meta.url), "utf-8");
  assert.ok(bron.includes('id="night"') && bron.includes("night_strategy"), "de schakelaar op Strategie");
  assert.ok(bron.includes("night_strategy !== false"), "standaard aan");
});

proef("de rij apparaten in de volgorde van dit scherm, nieuwe apparaten achteraan (v0.91.0)", async () => {
  const { orderDevices } = await import("../custom_components/domotiapp_coach/frontend/src/layout.js");
  const lijst = [{ id: "paal" }, { id: "vaat" }, { id: "boiler" }, { id: "accu" }];
  assert.deepEqual(orderDevices(lijst, ["accu", "paal"]).map((d) => d.id), ["accu", "paal", "vaat", "boiler"]);
  assert.deepEqual(orderDevices(lijst, []).map((d) => d.id), ["paal", "vaat", "boiler", "accu"], "zonder keuze de volgorde van de instellingen");
  assert.deepEqual(orderDevices(lijst, ["weg", "boiler"]).map((d) => d.id), ["boiler", "paal", "vaat", "accu"], "een verdwenen apparaat doet niets");
  const kaart = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf-8");
  assert.ok(kaart.includes("orderDevices(") && kaart.includes("deviceOrder()"), "de rij volgt de gekozen volgorde");
  assert.ok(kaart.includes('id="steer-left"') && kaart.includes('id="steer-right"'), "de pijltjes die het gekozen apparaat opschuiven");
  // Het onzichtbare woord in een tab (.sr, absoluut) hoort aan zijn tab te
  // hangen. Zonder anker hing het aan de pagina en werd die op een smal scherm
  // zo breed als de hele rij: 610 px op 390, met zes apparaten (v0.102.2).
  assert.ok(/\.steer-tab \{[^}]*position: relative;/.test(kaart), "een tab is het anker van zijn onzichtbare woord");
  assert.ok(/\.sr \{\s*position: absolute;/.test(kaart), "en dat woord staat er absoluut in");
  assert.ok(kaart.includes("resetDeviceOrder();"), "standaard terugzetten zet ook de apparaten terug");
});

proef("de rij apparaten: het knopje van Indeling aanpassen, zonder tekst, en dan de pijltjes (v0.96.0, v0.102.1)", () => {
  // De eigenaar op 23-09-2026: "waarom kan ik hier de volgorde niet aanpassen,
  // drag en drop wat ik vroeg toch?" en daarna "niet lang indrukken maar het
  // zelfde icoontje als indeling aanpassen beneden, alleen dan zonder tekst, en
  // dat je dan kan slepen." En op 30-09-2026: "ook werkt de indeling aanpassen
  // drag en drop niet. Dat moet weg en wel de pijltjes behouden om dat aan te
  // passen." Sinds v0.102.1 dus alleen nog de pijltjes, bij de apparaten en bij
  // de kaarten.
  const kaart = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf-8");
  assert.ok(/id="steer-sort"[^>]*aria-label="Volgorde aanpassen"[^>]*>\$\{icons\.sliders\}<\/button>/.test(kaart),
    "hetzelfde icoon als Indeling aanpassen, zonder tekst");
  assert.ok(kaart.includes("${icons.sliders} Indeling aanpassen"), "dat is het icoon van de knop onderaan");
  assert.ok(!/startTabDrag_|startDrag_|setPointerCapture|\.grip|dragging/.test(kaart), "er wordt nergens meer gesleept");
  assert.ok(!/[Ss]leep de apparaten/.test(kaart) && kaart.includes("<span>Schuif het gekozen apparaat:</span>"), "en de tekst belooft het ook niet meer");
  assert.ok(kaart.includes('data-move="-1" aria-label="Omhoog"') && kaart.includes('data-move="1" aria-label="Omlaag"'),
    "de kaarten houden hun pijltjes omhoog en omlaag");
  assert.ok(!kaart.includes('aria-label="Verslepen"'), "zonder de greep om aan te slepen");
  assert.ok(kaart.includes('this.$("#steer-sort").hidden = list.length < 2;'), "alleen als er iets te ordenen valt");
  assert.ok(!kaart.includes("langDrukken_"), "geen lang indrukken");
});

proef("de laadlimiet per planning: het veld, de samenvatting en de zin op de kaart (v0.96.0)", async () => {
  const { planSummary, kentDoel, doelUit } = await import("../custom_components/domotiapp_coach/frontend/src/schedule-sheet.js");
  assert.ok(kentDoel({ type: "laadpaal" }) && !kentDoel({ type: "boiler" }) && !kentDoel({ type: "vaatwasser" }));
  assert.equal(doelUit(""), null);
  assert.equal(doelUit("50"), 50);
  assert.equal(doelUit("5"), 10, "nooit onder de 10");
  assert.equal(doelUit("120"), 100);
  assert.equal(doelUit("abc"), null);
  const elke = { enabled: true, per_day: false, window: { done_by: "07:00", target: 80 }, days: [] };
  assert.equal(planSummary(elke), "Elke dag · klaar om 07:00 · tot 80%");
  const perDag = { enabled: true, per_day: true, window: {}, days: [
    { day: 0, enabled: true, done_by: "07:00", target: 50 },
    { day: 1, enabled: true, done_by: "07:00", target: 100 },
    { day: 2, enabled: true, done_by: "07:00", target: null },
  ] };
  assert.match(planSummary(perDag), /50%.*100%/);
  const blad = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/schedule-sheet.js", import.meta.url), "utf-8");
  assert.ok(blad.includes("window_.target = doelUit(doelVeld.value)") && blad.includes("entry.target = doelUit(doelVeld.value)"),
    "het doel gaat mee bij elke dag hetzelfde en per dag");
  const kaart = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf-8");
  assert.ok(kaart.includes("Deze beurt laadt tot ${Math.round(oordeel.target_plan)}%, volgens je planning"), "de zin op de kaart");
  assert.ok(kaart.includes("const algemeen = oordeel.target_general ?? oordeel.target_percent;"), "de keuzelijst is de algemene limiet");
});

proef("voorrang bij zonoverschot: het paneel vult aan zoals de coach (zie proef 63 in test_planner.py)", async () => {
  const { zonRegels, regelUitleg } = await import("../custom_components/domotiapp_coach/frontend/src/voorrang.js");
  const apparaten = [
    { id: "paal", type: "laadpaal", controllable: true },
    { id: "boiler", type: "boiler", controllable: true },
    { id: "accu", type: "thuisbatterij", controllable: true },
    { id: "vaat", type: "vaatwasser", controllable: true },
    { id: "meet", type: "laadpaal", controllable: false },
  ];
  assert.deepEqual(zonRegels([], apparaten), [
    { device: "paal", limit: null }, { device: "boiler", limit: null }, { device: "accu", limit: null }]);
  assert.deepEqual(
    zonRegels([{ device: "accu", limit: 50 }, { device: "paal", limit: 60 }, { device: "boiler", limit: 40 },
      { device: "weg", limit: 10 }], apparaten),
    [{ device: "accu", limit: 50 }, { device: "paal", limit: 60 }, { device: "boiler", limit: null }],
    "dezelfde uitkomst als zon_regels in planner.py");
  assert.equal(regelUitleg("thuisbatterij", 50), "tot 50%");
  assert.equal(regelUitleg("laadpaal", null), "tot het doel van de auto");
  assert.equal(regelUitleg("boiler", null), "tot hij warm is");
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/strategy.js", import.meta.url), "utf-8");
  assert.ok(bron.includes('id="zon-lijst"') && bron.includes("sleepIn_(") && bron.includes("solar_priority"));
});

proef("voorrang bij planningen: standaard auto, accu, boiler, palen in hun oude voorrang (v0.93.0)", async () => {
  const { planRegels } = await import("../custom_components/domotiapp_coach/frontend/src/voorrang.js");
  const apparaten = [
    { id: "boiler", type: "boiler", controllable: true },
    { id: "accu", type: "thuisbatterij", controllable: true },
    { id: "paal1", type: "laadpaal", controllable: true },
    { id: "paal2", type: "laadpaal", controllable: true },
    { id: "vaat", type: "vaatwasser", controllable: true },
  ];
  assert.deepEqual(planRegels([], apparaten), ["paal1", "paal2", "accu", "boiler"]);
  assert.deepEqual(planRegels([], apparaten, [{ device: "paal1", priority: "low" }, { device: "paal2", priority: "high" }]),
    ["paal2", "paal1", "accu", "boiler"], "de oude hoog/laag van de kaart is de beginvolgorde");
  assert.deepEqual(planRegels(["boiler", "weg", "accu"], apparaten), ["boiler", "accu", "paal1", "paal2"],
    "dezelfde uitkomst als plan_regels in planner.py (proef 64)");
  const kaart = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf-8");
  assert.ok(!kaart.includes("data-plan-prio"), "het keuzelijstje Prioriteit staat niet meer op de kaart");
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/strategy.js", import.meta.url), "utf-8");
  assert.ok(bron.includes('id="plan-lijst"') && bron.includes("plan_priority"));
  // De eigenaar op 23-09-2026: "warmtepomp moet prio 1 zijn." Wat de coach niet stuurt
  // gaat altijd voor, en dat staat als vaste regel boven beide lijsten.
  assert.equal(bron.split("Warmtepomp, koken en de rest van je huis").length - 1, 2, "boven beide lijsten");
});

proef("de energiestroom: de thuisbatterij staat altijd rechts, de rest eronder (v0.93.0)", async () => {
  const { chooseBubbles } = await import("../custom_components/domotiapp_coach/frontend/src/components/energy-flow.js");
  const accu = { id: "a", type: "thuisbatterij", watts: 3450, batteryWatts: -3450 };
  const paal = { id: "p", type: "laadpaal", watts: 9200 };
  const vaat = { id: "v", type: "vaatwasser", watts: 2000 };
  const stil = { id: "b", type: "thuisbatterij", watts: 0, batteryWatts: 0 };
  assert.deepEqual(chooseBubbles([paal, accu]).slots.map((d) => d.id), ["a", "p"], "de accu rechts, ook naast een zwaardere paal");
  const drie = chooseBubbles([paal, vaat, accu]);
  assert.equal(drie.slots[0].id, "a");
  assert.equal(drie.slots[1].id, "__rest__");
  assert.deepEqual(drie.rolled.map((d) => d.id), ["p", "v"], "de rest opgeteld onder");
  assert.deepEqual(chooseBubbles([stil, paal]).slots.map((d) => d.id), ["b", "p"], "ook als hij stilstaat");
  assert.deepEqual(chooseBubbles([paal, vaat]).slots.map((d) => d.id), ["p", "v"], "zonder accu zoals het was");
});

proef("onder het schemaschuifje staat wat hij zonder planning doet", async () => {
  const { planSummary } = await import("../custom_components/domotiapp_coach/frontend/src/schedule-sheet.js");
  const uit = { enabled: false, per_day: false, window: {}, days: [] };
  assert.equal(planSummary(uit, "zon"), "Uit. Zonder planning laadt hij alleen op zon.");
  assert.match(planSummary(uit, "continu"), /continu/);
  assert.match(planSummary(uit), /gunstigste moment/, "een apparaat zonder modus houdt de oude zin");
});

// --- eerdere contracten en gas ---------------------------------------------------
//
// De bewoner van de eerste woning op 22-09-2026: "gascontract 1: van-tot +
// prijs, gascontract 2: van-tot + prijs; dat kun je ook doen bij de
// stroomprijzen. Op die manier kun je een goede weergave bieden van kosten,
// ook bij wijzigen van aanbieder."
const { contractAt } = await import("../custom_components/domotiapp_coach/frontend/src/data-source.js");

proef("een dag in een eerder contract rekent met de prijs van toen, daarbuiten met het huidige", () => {
  const contract = {
    type: "fixed", gas_price: 1.3,
    fixed: { all_in_price: 0.28, feed_in_tariff: 0.07, feed_in_costs: 0.01 },
    periods: [
      { from: "2025-01-01", to: "2025-12-31", all_in_price: 0.35, feed_in_tariff: 0.09, gas_price: 1.5 },
      { from: "2024-01-01", to: "2024-12-31", all_in_price: 0.4, feed_in_tariff: 0, gas_price: 0 },
    ],
  };
  const toen = contractAt(contract, new Date(2025, 5, 15, 12));
  assert.equal(toen.buy, 0.35);
  assert.equal(toen.feedIn, 0.09);
  assert.equal(toen.gas, 1.5);
  assert.ok(toen.period);
  const nu = contractAt(contract, new Date(2026, 8, 22, 12));
  assert.equal(nu.buy, 0.28);
  assert.ok(Math.abs(nu.feedIn - 0.06) < 1e-9, "teruglevering min de kosten");
  assert.equal(nu.gas, 1.3);
  assert.equal(nu.period, null);
  // Een leeg veld in een eerder contract valt terug op het huidige contract.
  const leeg = contractAt(contract, new Date(2024, 3, 1, 12));
  assert.equal(leeg.buy, 0.4);
  assert.ok(Math.abs(leeg.feedIn - 0.06) < 1e-9);
  assert.equal(leeg.gas, 1.3);
  // Zonder gasprijs is gas onbekend, en een dynamisch contract heeft geen vaste inkoopprijs.
  assert.equal(contractAt({ type: "dynamic", dynamic: {} }, new Date()).buy, null);
  assert.equal(contractAt({ type: "fixed", fixed: { all_in_price: 0.28 } }, new Date()).gas, null);
  // Een contract zonder einde loopt nog.
  const open = contractAt({ type: "dynamic", periods: [{ from: "2026-01-01", to: "", all_in_price: 0.3 }] }, new Date(2026, 8, 22));
  assert.equal(open.buy, 0.3);
});

proef("een negatieve prijs krijgt zijn eigen tip, en de verkoopvergoeding staat in het formulier", () => {
  const drempels = { price: { high: 0.4, low: 0.1 }, self_use: { low: 20 } };
  const r = { solar: 2000, grid: -1500, exportW: 1500, importW: 0, load: 1, loadBasis: "phase", price: -0.03, selfUse: 30 };
  const tip = advise(r, drempels, true, 80, null, [{ type: "overig", name: "Droger", controllable: true }], null);
  assert.equal(tip.title, "De stroomprijs is negatief");
  assert.ok(tip.body.includes("de Droger"), tip.body);
  const html = Object.create(Installatie.prototype).render();
  assert.ok(html.includes('id="dyn-feedbonus"'));
  assert.ok(html.includes("0,0025"), "de kwart cent van na het salderen staat erbij");
});

proef("water hoort erbij: prijs per dag, meterstand, formulier en de lekmelding", async () => {
  const contract = { type: "fixed", gas_price: 1.3, water_price: 1.1, fixed: { all_in_price: 0.28 },
    periods: [{ from: "2025-01-01", to: "2025-12-31", all_in_price: 0.35, gas_price: 1.5, water_price: 0.9 }] };
  assert.equal(contractAt(contract, new Date(2025, 5, 1)).water, 0.9);
  assert.equal(contractAt(contract, new Date(2026, 5, 1)).water, 1.1);
  assert.equal(contractAt({ type: "fixed" }, new Date()).water, null);
  const { meterReadings } = await import("../custom_components/domotiapp_coach/frontend/src/data-source.js");
  const staten = { "sensor.water": { state: "50.563", attributes: { unit_of_measurement: "m³" } } };
  const feed = { get: (id) => staten[id] };
  assert.equal(meterReadings(feed, { meters: { water: "sensor.water", water_enabled: false } }).length, 0);
  assert.equal(meterReadings(feed, { meters: { water: "sensor.water", water_enabled: true } })[0].label, "Water");
  const inst = Object.create(Installatie.prototype).render();
  assert.ok(inst.includes('id="water-price"'));
  await import("../custom_components/domotiapp_coach/frontend/src/views/settings.js");
  const Instellingen = geregistreerd.get("dac-view-settings");
  const set = Object.create(Instellingen.prototype).render();
  assert.ok(set.includes('id="water-enabled"') && set.includes('data-meter="water_flow"'));
  await import("../custom_components/domotiapp_coach/frontend/src/views/notifications.js");
  const Meldingen = geregistreerd.get("dac-view-notifications");
  const mel = Object.create(Meldingen.prototype).render();
  assert.ok(mel.includes('id="verbruik-aan"') && mel.includes('id="verbruik-water"') && mel.includes('id="verbruik-factor"'));
  const hist = Object.create(Historie.prototype).render();
  assert.ok(hist.includes('id="water-card"') && hist.includes('id="water-stage"'));
  const el = Object.create(Historie.prototype);
  el.settings_ = { sources: { meters: { water_enabled: true, water: "sensor.water", gas_enabled: true, gas: "sensor.gas" } } };
  assert.deepEqual(el.meters_().water, ["sensor.water"]);
});

proef("Historie opent op vandaag, de eerste knop van de rij (22-09-2026)", () => {
  const bron = Historie.toString();
  assert.ok(/this\.period_ = "day";/.test(bron), "de constructor begint op day");
  assert.ok(!/this\.period_ = "week";/.test(bron));
  const html = Object.create(Historie.prototype).render();
  assert.ok(html.indexOf('data-period="day"') < html.indexOf('data-period="week"'));
});

proef("het installatiescherm heeft de gasprijs en de eerdere contracten", () => {
  const html = Object.create(Installatie.prototype).render();
  assert.ok(html.includes('id="gas-price"'));
  assert.ok(html.includes('id="periods"') && html.includes('id="period-add"'));
});

proef("de historie biedt een kort en een uitgebreid rapport", () => {
  const html = Object.create(Historie.prototype).render();
  assert.ok(html.includes('id="report-short"') && html.includes("Kort rapport"));
  assert.ok(html.includes('id="report"') && html.includes("Uitgebreid rapport"));
});

// --- meer omvormers ------------------------------------------------------------
//
// De bewoner van de eerste woning op 22-09-2026: "steeds meer consumenten
// hebben meerdere omvormers." De tweede en derde tellen op bij de eerste.
proef("twee omvormers tellen op in de energiestroom, en een slapende telt als nul", () => {
  const staten = {
    "sensor.zon1": { state: "1500", attributes: { unit_of_measurement: "W" } },
    "sensor.zon2": { state: "0.7", attributes: { unit_of_measurement: "kW" } },
    "sensor.afname": { state: "0", attributes: { unit_of_measurement: "W" } },
    "sensor.teruglevering": { state: "1200", attributes: { unit_of_measurement: "W" } },
    "sun.sun": { state: "above_horizon", attributes: {} },
  };
  const feed = { get: (id) => staten[id] };
  const settings = { sources: { solar: "sensor.zon1", solar_extra: ["sensor.zon2", ""], grid_mode: "split",
    grid_import: "sensor.afname", grid_export: "sensor.teruglevering" } };
  const r = new LiveSource().sample(feed, settings);
  assert.equal(r.solar, 2200);
  assert.equal(r.house, 1000);
  staten["sensor.zon2"] = { state: "unavailable", attributes: {} };
  assert.equal(new LiveSource().sample(feed, settings).solar, 1500, "wat er is telt, op het scherm");
  assert.ok(LiveSource.isConfigured({ sources: { solar: "", solar_extra: ["sensor.zon2"], grid_mode: "split" } }),
    "een installatie met alleen een tweede omvormer is ingesteld");
});

proef("de tellers van meer omvormers tellen op in de historie, en het rapport noemt elke omvormer", () => {
  const el = Object.create(Historie.prototype);
  el.settings_ = {
    sources: { solar: "sensor.zon1", solar_extra: ["sensor.zon2"], grid_mode: "split", grid_import: "sensor.afname", grid_export: "sensor.teruglevering",
      meters: { solar_total: "sensor.zon1_kwh", solar_total_extra: ["sensor.zon2_kwh", ""] } },
    devices: [],
  };
  assert.deepEqual(el.meters_().solar, ["sensor.zon1_kwh", "sensor.zon2_kwh"]);
  assert.deepEqual(el.vermogenBronnen_().map((r) => r.label), ["Van het net", "Naar het net", "Zon", "Zon 2"]);
});

// --- de knoppenrij op de laadpaalkaart --------------------------------------
//
// Op 30-08-2026 kreeg de nieuwe knop "Wat gaat hij doen" de klasse `plan-link`,
// en die stijlen staan onder `.plan-pick`. Buiten dat blok kreeg de knop dus
// helemaal geen vorm: het pictogram werd op ware grootte getekend, de rij groeide
// mee, en Snelladen en Pauzeren werden reusachtige cirkels omdat hun
// pillevorm de hoogte van de rij overnam. De eigenaar: "waarom is dit ineens zo groot?"
//
// Elke knop in die rij hoort dus een klasse te hebben die de stijlen ook echt
// vormgeven, en een die verborgen kan worden hoort een eigen `[hidden]`-regel
// te hebben. Dat laatste is dezelfde regel als in CLAUDE.md.

await import("../custom_components/domotiapp_coach/frontend/src/views/overview.js");
const Overzicht = geregistreerd.get("dac-view-overview");
assert.ok(Overzicht, "het overzicht hoort zich te registreren");

/** De kaarten van de stuurbare apparaten, als platte html. */
function steerHtml() {
  const knopen = new Map();
  const maak = () => ({ hidden: false, innerHTML: "", close() {}, style: {} });
  for (const id of ["#steerable", "#steer-tabs", "#steer-grid", "#manual"]) {
    knopen.set(id, maak());
  }
  const el = Object.create(Overzicht.prototype);
  el.$ = (kiezer) => knopen.get(kiezer) ?? maak();
  el.$$ = () => [];
  el.labels_ = new Map([["dev-1", "Laadpaal"]]);
  el.buildSteerable_([
    { id: "dev-1", type: "laadpaal", name: "Laadpaal", controllable: true, cars: [] },
  ]);
  return knopen.get("#steer-grid").innerHTML;
}

/** De stijlen van het overzicht, zoals de browser ze krijgt. */
const stijlen = Overzicht.css;

proef("elke knop in de actierij heeft een klasse die vorm geeft", () => {
  const html = steerHtml();
  const rij = html.slice(html.indexOf('class="steer-actions"'));
  const einde = rij.indexOf('class="steer-hint"');
  const blok = einde > 0 ? rij.slice(0, einde) : rij;

  // Alleen de knoppen die rechtstreeks in de rij staan. Wat in een eigen blok
  // zit, zoals `.plan-pick`, heeft zijn eigen stijlen.
  const knoppen = [...blok.matchAll(/<button[^>]*>/g)].map((m) => m[0]);
  assert.ok(knoppen.length >= 4, `verwacht een handvol knoppen, kreeg ${knoppen.length}`);

  const gevormd = ["release", "manual", "boost", "plan-toggle", "plan-link", "soc-save",
                   "says-yes"];
  for (const knop of knoppen) {
    const klasse = /class="([^"]*)"/.exec(knop)?.[1] ?? "";
    assert.ok(
      klasse.split(/\s+/).some((naam) => gevormd.includes(naam)),
      `knop zonder vormgevende klasse: ${knop}`
    );
  }
});

proef("een knop die verborgen kan worden heeft een eigen hidden-regel", () => {
  const html = steerHtml();
  const knoppen = [...html.matchAll(/<button[^>]*\shidden[^>]*>/g)].map((m) => m[0]);
  assert.ok(knoppen.length >= 2, "er horen verborgen knoppen te zijn");

  for (const knop of knoppen) {
    const klasse = (/class="([^"]*)"/.exec(knop)?.[1] ?? "").split(/\s+/)[0];
    if (!klasse) continue;
    // Het attribuut `hidden` is een regel van de browser zelf en verliest van
    // elke `display` in de eigen stijlen. Zie CLAUDE.md.
    assert.match(
      stijlen,
      new RegExp(String.raw`(?:button)?\.${klasse}\[hidden\]`),
      `.${klasse} krijgt een display maar heeft geen [hidden]-regel`
    );
  }
});

proef("de tijdlijnknop staat in de rij en is verborgen tot er een plan is", () => {
  const html = steerHtml();
  assert.match(html, /data-ahead="0"/, "de knop hoort er te staan");
  const knop = /<button[^>]*data-ahead="0"[^>]*>/.exec(html)[0];
  assert.match(knop, /class="boost"/, "met dezelfde vorm als de andere actieknoppen");
  assert.match(knop, /\shidden/, "en verborgen tot de coach een tijdlijn heeft");
});

// De eigenaar op 13-09-2026, na een vrijgave om 16:33 bij klaar om 16:30: "de keuze
// ingeruimd en morgen starten of ingeruimd en nu starten." De coach zegt in
// zijn besluit welke klaar-tijd gemist is (`missed`) en naar welke dag het
// schema opschuift (`later`); de kaart maakt daar twee knoppen van.
function kaartKnoppen({ ready = [], now = [], missed = "2026-09-12T16:30:00", running = false, apparaat = null } = {}) {
  const stub = () => {
    const doel = {
      hidden: false, innerHTML: "", textContent: "", value: "", dataset: {}, style: {}, attrs: {},
      setAttribute(k, v) { this.attrs[k] = v; },
      getAttribute(k) { return this.attrs[k]; },
      classList: {
        klassen: new Set(),
        toggle(k, aan) { if (aan) this.klassen.add(k); else this.klassen.delete(k); },
        add() {}, remove() {}, contains: () => false,
      },
      replaceChildren() {}, append() {}, addEventListener() {}, close() {}, focus() {},
      querySelector: () => stub(), querySelectorAll: () => [],
    };
    return doel;
  };
  const knopen = new Map();
  const el = Object.create(Overzicht.prototype);
  el.$ = (kiezer) => { if (!knopen.has(kiezer)) knopen.set(kiezer, stub()); return knopen.get(kiezer); };
  el.$$ = () => [];
  const device = apparaat ?? { id: "d2", type: "vaatwasser", name: "Vaatwasser", brand: "home_connect",
                              controllable: true, entities: {}, details: [] };
  el.labels_ = new Map([["d2", "Vaatwasser"]]);
  el.settings_ = { devices: [device], ready_devices: ready, ready_now: now, strategy: { schedules: [] } };
  el.coach_ = { d2: { kind: "programma", rule: ready.length ? "wait-for-start" : "not-released", level: "steer",
                      reason: "", plan: "", missed, later: missed ? "morgen" : null, running,
                      at: new Date().toISOString() } };
  el.fillSteerable_([device]);
  return {
    el, device,
    gewoon: knopen.get('[data-release-text="0"]')?.textContent,
    nuTekst: knopen.get('[data-release-now-text="0"]')?.textContent,
    nuVerborgen: knopen.get('[data-release-now="0"]')?.hidden,
    uitleg: knopen.get('[data-hint="0"]')?.textContent,
    groen: knopen.get('[data-tab-dot="0"]')?.classList.klassen.has("on"),
    staat: knopen.get('[data-tab-state="0"]')?.textContent,
  };
}

proef("na de klaar-tijd: ingeruimd en morgen starten, of ingeruimd en nu starten", () => {
  const k = kaartKnoppen();
  assert.equal(k.gewoon, "Ingeruimd, morgen starten");
  assert.equal(k.nuTekst, "Ingeruimd, nu starten");
  assert.equal(k.nuVerborgen, false, "de knop nu starten hoort te staan");
  assert.match(k.uitleg, /^16:30 is vandaag voorbij\. Kies of hij morgen/);
});

proef("vrijgegeven voor morgen blijft 'toch nu starten' staan; nu gekozen verdwijnt hij", () => {
  const morgen = kaartKnoppen({ ready: ["d2"] });
  assert.equal(morgen.gewoon, "Vrijgegeven, start morgen");
  assert.equal(morgen.nuTekst, "Toch nu starten");
  assert.equal(morgen.nuVerborgen, false);
  assert.equal(morgen.uitleg, "");
  const nu = kaartKnoppen({ ready: ["d2"], now: ["d2"] });
  assert.equal(nu.gewoon, "Vrijgegeven, start nu");
  assert.equal(nu.nuVerborgen, true);
});

// De eigenaar op 26-09-2026: "bij aanstuurbare apparaten draait de vaatwasser
// maar het bolletje is niet groen." Thuis was hij met de hand gestart, dus de
// vrijgave stond uit, en het bolletje zei alleen "vrijgegeven".
proef("het bolletje is groen als hij vrijgegeven is, en ook als hij draait zonder vrijgave", () => {
  const niets = kaartKnoppen({ missed: null });
  assert.equal(niets.groen, false, "niet vrijgegeven en stil: grijs");
  assert.equal(niets.staat, "");
  const vrij = kaartKnoppen({ ready: ["d2"], missed: null });
  assert.equal(vrij.groen, true, "vrijgegeven: groen");
  assert.equal(vrij.staat, " (vrijgegeven)");
  const hand = kaartKnoppen({ missed: null, running: true });
  assert.equal(hand.groen, true, "met de hand gestart: groen");
  assert.equal(hand.staat, " (draait)");
});

// De eigenaar op 28-09-2026: "bolletje van de batterij is niet groen. Als die laadt
// of ontlaadt moet hij groen zijn. Staat hij echt niks te doen dan moet hij uit
// zijn." Dezelfde grens als "Doet nu" op de kaart (`ACTIVE_WATTS`).
proef("het bolletje van de thuisbatterij is groen als hij laadt of ontlaadt, en uit als hij stilstaat", () => {
  const accu = (w) => kaartKnoppen({
    missed: null,
    apparaat: { id: "d2", type: "thuisbatterij", name: "Batterij", brand: "anker", controllable: true,
                entities: {}, details: [], watts: w === null ? null : Math.abs(w), batteryWatts: w },
  });
  const laadt = accu(1470);
  assert.equal(laadt.groen, true, "laden: groen");
  assert.equal(laadt.staat, " (laadt)");
  const ontlaadt = accu(-300);
  assert.equal(ontlaadt.groen, true, "ontladen: groen");
  assert.equal(ontlaadt.staat, " (ontlaadt)");
  for (const w of [0, 3, -3, null]) {
    const stil = accu(w);
    assert.equal(stil.groen, false, `${w} W: uit`);
    assert.equal(stil.staat, "");
  }
});

proef("voor de klaar-tijd en tijdens een beurt blijft het één knop", () => {
  const voor = kaartKnoppen({ missed: null });
  assert.equal(voor.gewoon, "Ingeruimd en dicht");
  assert.equal(voor.nuVerborgen, true);
  const draait = kaartKnoppen({ ready: ["d2"], running: true });
  assert.equal(draait.gewoon, "Vrijgegeven");
  assert.equal(draait.nuVerborgen, true);
});

proef("nu starten stuurt ready en now mee, de gewone knop now uit", async () => {
  const k = kaartKnoppen();
  const verstuurd = [];
  k.el.hass = { callWS: async (msg) => { verstuurd.push(msg); } };
  k.el.steerDevices_ = [k.device];
  await k.el.toggleReady_(0, true);
  assert.deepEqual(verstuurd.at(-1), { type: "domotiapp_coach/device/ready", device_id: "d2", ready: true, now: true });
  assert.deepEqual(k.el.settings_.ready_now, ["d2"]);
  await k.el.toggleReady_(0);
  assert.deepEqual(verstuurd.at(-1), { type: "domotiapp_coach/device/ready", device_id: "d2", ready: false, now: false });
  assert.deepEqual(k.el.settings_.ready_devices, []);
  assert.deepEqual(k.el.settings_.ready_now, []);
});

// --- de woning bij een slapende omvormer (de klantwoning, 19-09-2026) ----------
// Om 03:40 stond er een streepje bij Woning: 6,77 kW van het net en 5,49 kW
// naar de paal, maar de SolarEdge was sinds 21:40 onbereikbaar en het verbruik
// is zon plus net.
const { LiveSource } = await import("../custom_components/domotiapp_coach/frontend/src/data-source.js");

function woningBij(zon, sun) {
  const staten = {
    "sensor.omvormer": { state: zon, attributes: { unit_of_measurement: "W" } },
    "sensor.afname": { state: "6770", attributes: { unit_of_measurement: "W" } },
    "sensor.teruglevering": { state: "0", attributes: { unit_of_measurement: "W" } },
  };
  if (sun) staten["sun.sun"] = { state: sun, attributes: {} };
  const feed = { get: (id) => staten[id] };
  const settings = { sources: { solar: "sensor.omvormer", grid_mode: "split",
    grid_import: "sensor.afname", grid_export: "sensor.teruglevering" } };
  return new LiveSource().sample(feed, settings);
}

proef("een favoriet van de machine is geen programma en staat niet in de lijst", () => {
  // De eigenaar op 23-09-2026: "favorite 001 is geen programma, haal die eruit."
  const state = { state: "dishcare_dishwasher_program_kurz60", attributes: { options: [
    "favorite_001", "dishcare_dishwasher_program_auto2", "dishcare_dishwasher_program_eco50", "Favorite.002",
  ] } };
  assert.deepEqual(programChoices(state), ["dishcare_dishwasher_program_auto2", "dishcare_dishwasher_program_eco50"]);
  assert.deepEqual(programChoices(undefined), []);
  const device = { id: "vw", type: "vaatwasser", brand: "home_connect",
    entities: { program: "sensor.vw_actief", program_select: "select.vw_programma" } };
  const feed = new Map([["select.vw_programma", state]]);
  assert.deepEqual(programOptions(device, feed).map((o) => o.key), ["auto_2", "eco_50"]);
  assert.equal(programRows(device, programOptions(device, feed)).length, 2);
});

proef("het programma op de kaart: uit de select zolang de sensor niets zegt, uit de sensor tijdens de beurt (Home Connect Local)", () => {
  // Thuis op 23-09-2026: "Actief programma" zegt alleen tijdens de beurt
  // iets, en de select "Geselecteerd programma" valt juist dan weg.
  const device = { id: "vw", type: "vaatwasser", name: "Vaatwasser", brand: "home_connect", entity: "sensor.vw_w",
    entities: { status: "sensor.vw_status", program: "sensor.vw_actief", program_select: "select.vw_programma" } };
  const rij = (staten) => {
    const feed = { get: (id) => staten[id] };
    const r = new LiveSource().sample(feed, { sources: {}, devices: [device] });
    return r.devices[0].details.find((d) => d.label === "Geselecteerd programma")?.text;
  };
  assert.equal(rij({ "sensor.vw_status": { state: "ready", attributes: {} },
                     "sensor.vw_actief": { state: "unknown", attributes: {} },
                     "select.vw_programma": { state: "dishcare_dishwasher_program_kurz60", attributes: {} } }), "Express 60 °C");
  assert.equal(rij({ "sensor.vw_status": { state: "run", attributes: {} },
                     "sensor.vw_actief": { state: "dishcare_dishwasher_program_eco50", attributes: {} },
                     "select.vw_programma": { state: "unavailable", attributes: {} } }), "Eco 50 °C");
  // Het veld "Starten op afstand" hoort bij het merk, optioneel, en leest aan/uit.
  const velden = brandFields(device);
  const afstand = velden.find((f) => f.key === "remote_start");
  assert.ok(afstand && !afstand.needed, "remote_start is een optioneel veld van Home Connect");
  assert.equal(afstand.values.off, "Uit");
});

proef("een slapende omvormer met de zon onder telt als nul, en de woning staat er", () => {
  const r = woningBij("unavailable", "below_horizon");
  assert.equal(r.solar, 0);
  assert.equal(r.house, 6770);
});

proef("overdag blijft een onbereikbare omvormer een streepje", () => {
  const r = woningBij("unavailable", "above_horizon");
  assert.equal(r.solar, null);
  assert.equal(r.house, null);
});

proef("zonder sun.sun ook", () => {
  assert.equal(woningBij("unavailable", null).house, null);
});

proef("een omvormer die wel iets zegt wint altijd", () => {
  assert.equal(woningBij("12", "below_horizon").solar, 12);
});

// De belasting: een garage van 16 A op 12 A is zwaarder belast dan een
// aansluiting van 25 A op 6, en de kaart zegt erbij welke groep het is.
const { loadOf: belastingVan, readCircuits: groepenVan } = await import(
  "../custom_components/domotiapp_coach/frontend/src/data-source.js"
);

proef("de belasting kijkt ook naar de groepen, elk tegen zijn eigen zekering", () => {
  const hoofd = [{ label: "L1", amps: 6 }, { label: "L2", amps: 4 }];
  const garage = [{ name: "Garage", fuse: 16, phases: [{ label: "L1", amps: 12 }] }];
  const met = belastingVan(hoofd, null, { fuse_amps: 25 }, garage);
  assert.equal(met.basis, "phase");
  assert.ok(Math.abs(met.percent - 75) < 0.01);
  assert.equal(met.worst, "L1 (Garage)");
  const zonder = belastingVan(hoofd, null, { fuse_amps: 25 });
  assert.equal(zonder.worst, "L1");
  assert.ok(Math.abs(zonder.percent - 24) < 0.01);
});

proef("een groep zonder meetwaarde blijft van de kaart", () => {
  const staten = { "sensor.g1": { state: "12", attributes: { unit_of_measurement: "A" } } };
  const feed = { get: (id) => staten[id] };
  const groepen = groepenVan(feed, { circuits: [
    { id: "garage", name: "Garage", fuse_amps: 16, phases: 1, sensors: { l1: { current: "sensor.g1" } } },
    { id: "leeg", name: "Leeg", fuse_amps: 16, phases: 3, sensors: {} },
  ] });
  assert.equal(groepen.length, 1);
  assert.equal(groepen[0].name, "Garage");
  assert.equal(groepen[0].phases.length, 1);
  assert.equal(groepen[0].phases[0].amps, 12);
});

// Zonneplan geeft zijn prijzen als `forecast`, in tienmiljoensten van een
// euro en zonder eindtijd. Gemeten in de eerste woning op 22-09-2026.
const { priceForecast } = await import("../custom_components/domotiapp_coach/frontend/src/data-source.js");

proef("een Zonneplan-lijst wordt een prijs per uur in euro's", () => {
  const staten = {
    "sensor.prijs": { state: "0.3355224", attributes: { unit_of_measurement: "€/kWh", forecast: [
      { electricity_price: 3355224, datetime: "2026-08-27T10:00:00.000000Z" },
      { electricity_price: 2500000, datetime: "2026-08-27T11:00:00.000000Z" },
    ] } },
  };
  const contract = { type: "dynamic", dynamic: { source: "all_in", all_in_entity: "sensor.prijs", interval: "quarter" } };
  const rijen = priceForecast({ get: (id) => staten[id] }, contract);
  assert.equal(rijen.length, 2);
  assert.ok(Math.abs(rijen[0].price - 0.3355224) < 1e-9);
  assert.equal(rijen[0].end.getTime(), rijen[1].start.getTime());
  // Het laatste blok kent geen opvolger en is even lang als het blok ervoor.
  assert.equal(rijen[1].end.getTime() - rijen[1].start.getTime(), 3_600_000);
});

// --- de thuisbatterij ---------------------------------------------------------
//
// De eigenaar op 21-09-2026: "Ik wil de coach gaan uitbreiden met een
// thuisbatterij." Hier wat het paneel ervan laat zien: het merk met zijn velden,
// de regels op de kaart, en de woning die klopt terwijl de batterij het huis
// voedt.
const { BATTERY_BRANDS, DEVICE_TYPES: TYPES, brandFields: veldenVan, canSteer: kanSturen, missingForControl: mistNog, defaultBattery } =
  await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
const { batteryRows, volgendeNetlading, opgeleverdTekst } = await import(
  "../custom_components/domotiapp_coach/frontend/src/battery.js"
);

proef("de thuisbatterij staat weer in de lijst, met Anker en Overig als merk", () => {
  assert.ok(TYPES.some((t) => t.id === "thuisbatterij"));
  assert.deepEqual(BATTERY_BRANDS.map((b) => b.id), ["anker", "overig"]);
});

proef("Alfen is een laadpaalmerk: velden zonder apparaat-id of dienst, dezelfde lijst als const.py", async () => {
  // 23-09-2026: het tweede paalmerk. Geen `device` en geen `service`: de
  // coach schrijft een number en leest twee aan/uit-sensoren. Sturen kan dus
  // wel, handmatige knoppen zijn er niet.
  const { CHARGER_BRANDS, deviceCommands } = await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  assert.deepEqual(CHARGER_BRANDS.map((b) => b.id), ["easee", "alfen"]);
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/const.py", import.meta.url), "utf8");
  const blok = bron.slice(bron.indexOf("CHARGER_BRANDS: Final = ["));
  const python = [...blok.slice(0, blok.indexOf("]")).matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
  assert.deepEqual(python, CHARGER_BRANDS.map((b) => b.id));
  const alfen = CHARGER_BRANDS.find((b) => b.id === "alfen");
  assert.ok(!alfen.device && !alfen.service && !alfen.actions, "geen apparaat-id, geen dienst, geen woorden");
  const paal = { type: "laadpaal", brand: "alfen", controllable: true, entities: {} };
  assert.deepEqual(veldenVan(paal).filter((f) => f.needed).map((f) => f.key), ["limit", "connected", "charging", "max_limit"]);
  assert.ok(kanSturen(paal), "een Alfen is te sturen");
  assert.deepEqual(deviceCommands({ ...paal, device_id: "x" }), [], "maar heeft geen handmatige knoppen");
  assert.deepEqual(mistNog(paal), ["Maximale stroomlimiet", "Auto aangesloten", "Auto laadt", "Werkelijke maximale stroom"]);
});

proef("de merken van de batterij zijn dezelfde als in const.py", () => {
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/const.py", import.meta.url), "utf8");
  const blok = bron.slice(bron.indexOf("BATTERY_BRANDS: Final = ["));
  const python = [...blok.slice(0, blok.indexOf("]")).matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
  assert.deepEqual(python, BATTERY_BRANDS.map((b) => b.id));
});

proef("Anker vraagt om een richting, Overig niet", () => {
  const nodig = (brand) =>
    veldenVan({ type: "thuisbatterij", brand }).filter((f) => f.needed).map((f) => f.key);
  assert.deepEqual(nodig("anker"), ["soc", "setpoint", "direction"]);
  assert.deepEqual(nodig("overig"), ["soc", "setpoint"]);
});

proef("een batterij is te sturen, en zegt wat er nog mist", () => {
  const batterij = { type: "thuisbatterij", brand: "anker", controllable: true, entities: { soc: "sensor.soc" } };
  assert.equal(kanSturen(batterij), true);
  assert.deepEqual(mistNog(batterij), ["Vermogen zetten", "Richting"]);
});

proef("Anker krijgt de woorden van zijn bedrijfsmodus mee, Overig niet", () => {
  assert.equal(defaultBattery("anker").control_mode, "third_party_control");
  assert.equal(defaultBattery("anker").idle_mode, "self_consumption");
  assert.equal(defaultBattery("overig").control_mode, "");
  // Niets wat de coach zou moeten weten staat standaard ingevuld.
  assert.equal(defaultBattery("anker").capacity_kwh, null);
  assert.equal(defaultBattery("anker").rte_percent, null);
  assert.equal(defaultBattery("anker").trade, false);
});

const BESLUIT_BATTERIJ = {
  kind: "batterij", mode: "netladen", mode_name: "Laden van het net", applied: true,
  setpoint_w: 1750, value: 0.2451, full_before: null,
  hours: [
    { start: "2026-09-22T01:00:00", end: "2026-09-22T02:00:00", grid_kwh: 0 },
    { start: "2026-09-22T02:00:00", end: "2026-09-22T03:00:00", grid_kwh: 1.7 },
    { start: "2026-09-22T03:00:00", end: "2026-09-22T04:00:00", grid_kwh: 1.8 },
    { start: "2026-09-22T04:00:00", end: "2026-09-22T05:00:00", grid_kwh: 0 },
    { start: "2026-09-22T13:00:00", end: "2026-09-22T14:00:00", grid_kwh: 2.0 },
  ],
  earned: { euro: 45, days: 30 },
};

proef("de kaart van een batterij: stand, opdracht, waarde, netlading en wat hij opleverde", () => {
  const rijen = Object.fromEntries(batteryRows(BESLUIT_BATTERIJ).map((r) => [r.label, r.text]));
  assert.equal(rijen["Stand"], "Laden van het net");
  assert.equal(rijen["Opdracht van de coach"], "laden op 1.750 W");
  assert.equal(rijen["Een kWh erin is straks waard"], undefined, "staat sinds v0.85.0 in de pop-up");
  assert.equal(rijen["Laadt van het net"], "02:00 tot 04:00, ongeveer 3,5 kWh");
  assert.equal(rijen["Opgeleverd"], "€ 45,00 in 30 dagen");
  // Geen terugverdientijd meer (v0.101.1), ook niet als er een oude stand binnenkomt.
  const oud = batteryRows({ ...BESLUIT_BATTERIJ, payback: { earned: 45, price: 4500, days: 30, date: "2034-11-08" } });
  assert.ok(!oud.some((r) => /Terugverdiend/.test(r.label)));
});

proef("alleen de eerste aaneengesloten netlading staat erop", () => {
  const net = volgendeNetlading(BESLUIT_BATTERIJ.hours);
  assert.equal(net.start, "2026-09-22T02:00:00");
  assert.equal(net.end, "2026-09-22T04:00:00");
  assert.equal(volgendeNetlading([]), null);
});

proef("een ontlaadopdracht leest als ontladen, en nul als nul", () => {
  const tekst = (w) => batteryRows({ ...BESLUIT_BATTERIJ, setpoint_w: w }).find((r) => r.label === "Opdracht van de coach").text;
  assert.equal(tekst(-340), "ontladen op 340 W");
  assert.equal(tekst(0), "0 W");
});

proef("stuurt de coach niet, dan staat er geen opdracht", () => {
  const rijen = batteryRows({ ...BESLUIT_BATTERIJ, applied: false });
  assert.ok(!rijen.some((r) => r.label === "Opdracht van de coach"));
});

proef("doet de batterij zelf nul op de meter, dan zegt de kaart wie regelt en staat er geen opdracht (v0.97.0)", () => {
  const rijen = Object.fromEntries(
    batteryRows({ ...BESLUIT_BATTERIJ, mode: "nul", mode_name: "Nul op de meter", self_zero: true, setpoint_w: null })
      .map((r) => [r.label, r.text]),
  );
  assert.equal(rijen["Wie regelt"], "de batterij zelf, met zijn eigen meter; de coach kijkt mee");
  assert.equal(rijen["Opdracht van de coach"], undefined);
  const zonder = batteryRows({ ...BESLUIT_BATTERIJ, self_zero: false });
  assert.ok(!zonder.some((r) => r.label === "Wie regelt"));
});

proef("Opgeleverd zegt wat de batterij opleverde en over hoeveel dagen, en niets zonder dagen", () => {
  assert.deepEqual(opgeleverdTekst({ euro: 12.5, days: 9 }), [{ label: "Opgeleverd", text: "€ 12,50 in 9 dagen" }]);
  assert.equal(opgeleverdTekst({ euro: 0.03, days: 1 })[0].text, "€ 0,03 in 1 dag");
  assert.deepEqual(opgeleverdTekst({ euro: 0, days: 0 }), []);
  assert.deepEqual(opgeleverdTekst(undefined), []);
});

proef("een apparaat dat geen batterij is krijgt geen batterijregels", () => {
  assert.deepEqual(batteryRows({ kind: "boiler" }), []);
  assert.deepEqual(batteryRows(undefined), []);
});

function woningMetBatterij(batterijW, extra = {}) {
  const staten = {
    "sensor.omvormer": { state: "0", attributes: { unit_of_measurement: "W" } },
    "sensor.afname": { state: "24", attributes: { unit_of_measurement: "W" } },
    "sensor.teruglevering": { state: "0", attributes: { unit_of_measurement: "W" } },
    "sensor.batterij": { state: String(batterijW), attributes: { unit_of_measurement: "W" } },
    ...extra,
  };
  const feed = { get: (id) => staten[id] };
  const settings = {
    sources: { solar: "sensor.omvormer", grid_mode: "split",
      grid_import: "sensor.afname", grid_export: "sensor.teruglevering" },
    devices: [{ id: "b", type: "thuisbatterij", brand: "anker", entity: "sensor.batterij", entities: {} }],
  };
  return new LiveSource().sample(feed, settings);
}

// In de eerste woning op 21-09-2026 om 19:30: 24 W op de meter, geen zon, en
// de batterij gaf 2250 W af. Het huis gebruikte dus 2274 W en geen 24.
proef("de knoppen van de batterij hebben eigen iconen: een accu met een pijl erin en eruit", async () => {
  // 23-09-2026: "Nu leegladen" droeg een pauzeteken en "Nu vol laden" de
  // bliksem van snelladen. Nu twee eigen tekeningen, en de paal houdt de bliksem.
  const { icons } = await import("../custom_components/domotiapp_coach/frontend/src/icons.js");
  assert.ok(icons.accuVol && icons.accuLeeg && icons.accuVol !== icons.accuLeeg);
  assert.ok(icons.accuVol.startsWith("<svg") && icons.accuLeeg.startsWith("<svg"));
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf8");
  const knop = bron.indexOf('data-drain="${slot}" aria-pressed');
  const leeg = bron.slice(knop, bron.indexOf('data-drain-text="${slot}"', knop));
  assert.ok(leeg.includes("icons.accuLeeg") && !leeg.includes("icons.pause"), "leegladen draagt de accu met de pijl eruit");
  assert.ok(bron.includes('const wilIcoon = batterij ? "accuVol" : "bolt"'), "vol laden draagt de accu met de pijl erin, de paal de bliksem");
});

proef("de woning telt mee wat de batterij afgeeft", () => {
  const r = woningMetBatterij(-2250);
  assert.equal(r.house, 2274);
  assert.equal(r.devices[0].watts, 2250);
  assert.equal(r.devices[0].details[0].text, "ontlaadt");
});

proef("en wat de batterij laadt is geen verbruik van de woning", () => {
  const staten = { "sensor.afname": { state: "2300", attributes: { unit_of_measurement: "W" } } };
  const r = woningMetBatterij(2000, staten);
  assert.equal(r.house, 300);
  assert.equal(r.devices[0].details[0].text, "laadt");
});

// --- In geld (v0.101.0) -------------------------------------------------------
// De eigenaar op 28-09-2026: "ik wil op het historie overzicht duidelijk hebben wat
// ik heb bespaard die dag, totaal uitgegeven en totaal bespaard", en "stel alles
// goed op elkaar af".
const geld = await import("../custom_components/domotiapp_coach/frontend/src/geld.js");
const VAST = { type: "fixed", netting: true, fixed: { all_in_price: 0.24171, feed_in_tariff: 0.0721, feed_in_costs: 0.052756 } };
const TARIEF = { buy: 0.24171, feedIn: 0.0721 - 0.052756 };

proef("salderen: tot 2027 is een teruggeleverde kWh de prijs min de terugleverkosten, daarna de vergoeding", () => {
  const voor = geld.prijsOp(VAST, TARIEF, new Map(), new Date(2026, 8, 28, 12));
  assert.ok(Math.abs(voor.koop - 0.24171) < 1e-9 && Math.abs(voor.terug - (0.24171 - 0.052756)) < 1e-9, `${voor.terug}`);
  const na = geld.prijsOp(VAST, TARIEF, new Map(), new Date(2027, 0, 1, 12));
  assert.ok(Math.abs(na.terug - (0.0721 - 0.052756)) < 1e-9, `${na.terug}`);
  const zonder = geld.prijsOp({ ...VAST, netting: false }, TARIEF, new Map(), new Date(2026, 8, 28, 12));
  assert.ok(Math.abs(zonder.terug - (0.0721 - 0.052756)) < 1e-9, "zonder het vinkje de vergoeding");
});

proef("salderen bij een dynamisch contract: de prijs van dat uur min opslag en terugleverkosten, zoals de coach", () => {
  const dyn = { type: "dynamic", netting: true, dynamic: { supplier_markup: 0.02, vat_percent: 21, feed_in_costs: 0.0182, feed_in_bonus: 0 } };
  const uur = new Date(2026, 8, 28, 13);
  const p = geld.prijsOp(dyn, { buy: 0.3, feedIn: null }, new Map([[uur.getTime(), 0.25]]), uur);
  assert.ok(Math.abs(p.terug - (0.25 - 0.02 * 1.21 - 0.0182)) < 1e-9, `${p.terug}`);
});

proef("de balans: uitgegeven en bespaard, en de drie delen tellen samen op tot bespaard", () => {
  const dag = new Date(2026, 8, 28, 12);
  const b = geld.balans({
    rijen: [{ start: dag, own: 10, bought: 4, sold: 6, used: 14 }],
    prijs: (w) => geld.prijsOp(VAST, TARIEF, new Map(), w),
    gas: [{ start: dag, value: 2 }],
    contract: { ...VAST, gas_price: 1.33 },
    accu: 0.034,
    coach: { saved: 0.3, solar_saved: 0.2, wait_saved: 0.1 },
  });
  const terug = 0.24171 - 0.052756;
  assert.ok(Math.abs(b.stroom - 4 * 0.24171) < 1e-9);
  assert.ok(Math.abs(b.terug - 6 * terug) < 1e-9);
  assert.ok(Math.abs(b.uitgegeven - (4 * 0.24171 - 6 * terug + 2 * 1.33)) < 1e-9, `${b.uitgegeven}`);
  // Sinds v0.101.2 telt het kasboek van de batterij erbij: de meters zien haar niet.
  assert.ok(Math.abs(b.bespaard - (10 * 0.24171 + 6 * terug + 0.034 + 0.1)) < 1e-9, `${b.bespaard}`);
  const som = b.delen.zon + b.delen.accu + b.delen.coach;
  assert.ok(Math.abs(som - b.bespaard) < 1e-9, `${som} tegen ${b.bespaard}`);
  assert.ok(Math.abs(b.zonder - (b.uitgegeven + b.bespaard)) < 1e-9);
});

proef("het kasboek van de batterij telt alleen de dagen van de periode", () => {
  const settings = { battery_state: [{ device: "b", earned_days: { "2026-09-27": 0.5, "2026-09-28": 0.034, "2026-09-29": 1 } }] };
  const r = geld.accuVerdiend(settings, new Date(2026, 8, 28), new Date(2026, 8, 29));
  assert.ok(Math.abs(r.euro - 0.034) < 1e-9 && r.dagen === 1, `${r.euro} ${r.dagen}`);
});

proef("geen terugverdientijd en geen aankoopprijzen meer, nergens (v0.101.1)", () => {
  // De eigenaar op 29-09-2026: een datum in het paneel die afwijkt van wat een
  // installateur de klant voorrekende is niet te verdedigen. "Haal het invullen
  // van de kosten van de panelen weg en de batterij", met de teksten erbij.
  assert.equal(geld.terugverdienen, undefined);
  assert.equal(Historie.prototype.terugRijen_, undefined);
  const lees = (pad) => readFileSync(new URL(`../custom_components/domotiapp_coach/${pad}`, import.meta.url), "utf8");
  const bronnen = {
    "frontend/src/views/history.js": lees("frontend/src/views/history.js"),
    "frontend/src/views/installation.js": lees("frontend/src/views/installation.js"),
    "frontend/src/views/devices.js": lees("frontend/src/views/devices.js"),
    "frontend/src/devices.js": lees("frontend/src/devices.js"),
    "frontend/src/report.js": lees("frontend/src/report.js"),
    "websocket.py": lees("websocket.py"),
    "const.py": lees("const.py"),
  };
  for (const [pad, bron] of Object.entries(bronnen)) {
    for (const woord of ["purchase_price", "investments", "Aankoopprijs", "Investeringen", "payback", "Terugverdiend"]) {
      assert.ok(!bron.includes(woord), `${woord} staat nog in ${pad}`);
    }
  }
});

// --- de thuisbatterij in Historie (v0.101.2) ---------------------------------
// Bij de eigenaar op 29-09-2026 om 10:00: "Door je zon € -0,56" naast "Door je
// thuisbatterij € 0,60", en 2,65 kWh verbruikt waar het huis er ruim vijf
// gebruikte. De uren van 00:00 tot 09:00 zoals de recorder ze die dag gaf: zon,
// van het net, naar het net, en wat de batterij netto opnam (gemiddeld vermogen).
const { huisMetAccu } = await import("../custom_components/domotiapp_coach/frontend/src/views/history.js");
const NACHT_29 = [
  [0.0, 0.02, 0.0, -0.765], [0.0, 0.0, 0.0, -0.570], [0.0, 0.0, 0.0, -0.559], [0.0, 0.0, 0.0, -0.573],
  [0.0, 0.42, 0.0, -0.145], [0.0, 0.60, 0.0, 0.0], [0.0, 0.58, 0.0, 0.0], [0.0, 0.57, 0.0, 0.0],
  [0.15, 0.31, 0.0, 0.0],
].map(([zon, af, terug, accu], uur) => {
  const own = Math.max(0, zon - terug);
  return { start: new Date(2026, 8, 29, uur), own, bought: af, sold: terug, ...huisMetAccu(own, af, { battery: accu, voor: 0 }) };
});

proef("de eigenaar, 29-09 tot 09:00: de nacht op de batterij is verbruik, en de zon wordt niet negatief", () => {
  const verbruikt = NACHT_29.reduce((s, r) => s + r.used, 0);
  assert.ok(Math.abs(verbruikt - 5.262) < 0.001, `${verbruikt}`);
  const vanNet = NACHT_29.reduce((s, r) => s + r.fromGrid, 0);
  assert.ok(Math.abs(vanNet - 2.50) < 0.001, `${vanNet}`);
  const b = geld.balans({ rijen: NACHT_29, prijs: (w) => geld.prijsOp(VAST, TARIEF, new Map(), w), contract: VAST, accu: 0.60 });
  assert.ok(Math.abs(b.delen.zon - 0.15 * 0.24171) < 1e-9, `zon ${b.delen.zon}`);
  assert.ok(Math.abs(b.bespaard - (0.15 * 0.24171 + 0.60)) < 1e-9, `bespaard ${b.bespaard}`);
  assert.ok(Math.abs(b.delen.zon + b.delen.accu + b.delen.coach - b.bespaard) < 1e-9);
  assert.ok(Math.abs(b.zonder - (b.uitgegeven + b.bespaard)) < 1e-9);
});

proef("huisMetAccu: laden uit de zon is geen verbruik, laden van het net telt niet als van het net naar het huis", () => {
  const zon = huisMetAccu(3, 0.2, { battery: 2, voor: 2 });
  assert.ok(Math.abs(zon.used - 1.2) < 1e-9 && Math.abs(zon.fromGrid - 0.2) < 1e-9 && Math.abs(zon.zonInAccu - 2) < 1e-9, JSON.stringify(zon));
  const net = huisMetAccu(0, 3, { battery: 2.5, voor: 2.5 });
  assert.ok(Math.abs(net.used - 0.5) < 1e-9 && Math.abs(net.fromGrid - 0.5) < 1e-9 && net.zonInAccu === 0, JSON.stringify(net));
  const zonder = huisMetAccu(4, 1);
  assert.deepEqual(zonder, { used: 5, fromGrid: 1, ownUse: 4, battery: 0, zonInAccu: 0 });
});

proef("de zon die de batterij in ging: uit de telling van de coach, en daarvoor uit het vak zelf", () => {
  const dag = new Date(2026, 9, 1, 12);
  const terug = 0.24171 - 0.052756;
  const rij = { start: dag, own: 3, bought: 0.2, sold: 1, ...huisMetAccu(3, 0.2, { battery: 2, voor: 2 }) };
  const b = geld.balans({ rijen: [rij], prijs: (w) => geld.prijsOp(VAST, TARIEF, new Map(), w), contract: VAST, accu: 0 });
  assert.ok(Math.abs(b.delen.zon - (3 * 0.24171 + 1 * terug - 2 * 0.052756)) < 1e-9, `${b.delen.zon}`);
  const geteld = geld.balans({
    rijen: [{ ...rij, zonInAccu: 0 }], prijs: (w) => geld.prijsOp(VAST, TARIEF, new Map(), w), contract: VAST, accuZon: 0.1,
  });
  assert.ok(Math.abs(geteld.delen.zon - (3 * 0.24171 + 1 * terug - 0.1)) < 1e-9, `${geteld.delen.zon}`);
  const settings = { battery_state: [{ device: "b", solar_stored_days: { "2026-09-30": 0.5, "2026-10-01": 0.1 } }] };
  assert.ok(Math.abs(geld.accuZon(settings, new Date(2026, 9, 1), new Date(2026, 9, 2)).euro - 0.1) < 1e-9);
});

proef("de batterij per vak: uren in hun dag, en de schatting alleen voor wat de coach nog niet telde", () => {
  const el = Object.create(Historie.prototype);
  const d1 = new Date(2026, 8, 28).getTime();
  const d2 = new Date(2026, 8, 29).getTime();
  const d3 = new Date(2026, 8, 30).getTime();
  const uur = (d, h) => d + h * 3600000;
  el.settings_ = { battery_state: [{ device: "b", solar_stored_from: new Date(2026, 8, 29, 14, 5).toISOString() }] };
  el.accu_ = new Map([["b", [
    { start: uur(d1, 10), kwh: 1 }, { start: uur(d1, 22), kwh: -0.5 },
    { start: uur(d2, 10), kwh: 2 }, { start: uur(d3, 1), kwh: -1 },
  ]]]);
  const tijden = [d1, d2, d3];
  const vakken = el.accuPerVak_(tijden, (i) => tijden[i + 1] ?? d3 + 86400000);
  assert.deepEqual(vakken.map((v) => v.battery), [0.5, 2, -1]);
  assert.deepEqual(vakken.map((v) => v.voor), [0.5, 0, 0], "28-09 helemaal voor de telling, 29-09 niet meer");
  // Per uur op de dag zelf: de uren tot de telling begon wel, daarna niet.
  const uren = Array.from({ length: 24 }, (_, h) => uur(d2, h));
  el.accu_ = new Map([["b", [{ start: uur(d2, 10), kwh: 0.8 }, { start: uur(d2, 15), kwh: 0.6 }]]]);
  const perUur = el.accuPerVak_(uren, (i) => uren[i + 1] ?? d3);
  assert.equal(perUur[10].voor, 0.8);
  assert.equal(perUur[15].voor, 0);
  assert.equal(perUur[15].battery, 0.6);
});

proef("fetchBattery: tellers, een sensor met een teken en twee losse, en van vandaag alleen de verstreken uren", async () => {
  const { fetchBattery } = await import("../custom_components/domotiapp_coach/frontend/src/statistics.js");
  const uur = new Date(2026, 8, 29, 3).getTime();
  const vragen = [];
  const hass = {
    callWS: async (v) => {
      vragen.push(v);
      const uit = {};
      for (const id of v.statistic_ids) {
        if (v.types[0] === "change") uit[id] = [{ start: uur, change: id.endsWith("_in") ? 1.2 : 0.2 }];
        else uit[id] = [{ start: uur, mean: { "sensor.laad": 800, "sensor.ontlaad": 100, "sensor.teken": 500 }[id] }];
      }
      return uit;
    },
  };
  const accus = [
    { id: "meter", entities: { energy_in: "sensor.m_in", energy_out: "sensor.m_uit" }, entity: "sensor.teken" },
    { id: "twee", entities: { charge_power: "sensor.laad", discharge_power: "sensor.ontlaad" } },
    { id: "teken", entity: "sensor.teken", battery: { power_invert: true }, entities: {} },
    { id: "niets", entities: {} },
  ];
  const r = await fetchBattery(hass, accus, "day", new Date(2026, 8, 29));
  assert.ok(Math.abs(r.get("meter")[0].kwh - 1.0) < 1e-9, "de kWh-meter gaat voor");
  assert.ok(Math.abs(r.get("twee")[0].kwh - 0.7) < 1e-9, `${r.get("twee")[0].kwh}`);
  assert.ok(Math.abs(r.get("teken")[0].kwh + 0.5) < 1e-9, "omgekeerd teken: 500 W is ontladen");
  assert.equal(r.has("niets"), false);
  assert.ok(vragen.every((v) => v.period === "hour"), "per uur, ook als het vak een uur is");
  // Over een jaar per dag; de dag van vandaag telt alleen de uren die voorbij zijn.
  const vandaag = new Date();
  vandaag.setHours(0, 0, 0, 0);
  const jaar = {
    callWS: async (v) => ({ "sensor.teken": [{ start: vandaag.getTime(), mean: 1000 }] }),
  };
  const j = await fetchBattery(jaar, [{ id: "t", entity: "sensor.teken", entities: {} }], "year", new Date(vandaag.getFullYear(), 0, 1));
  const verstreken = Math.floor((Date.now() - vandaag.getTime()) / 3600000);
  assert.ok(Math.abs(j.get("t")[0].kwh - verstreken) < 1e-9, `${j.get("t")[0].kwh} tegen ${verstreken}`);
});

// --- een reserveprijssensor (v0.101.3) -----------------------------------------
// De eigenaar op 29-09-2026, toen Frank Energie eruit lag: "ik heb ook Nord Pool
// draaien, dat wil ik als fallback hebben." Het paneel tekent dan de lijst van
// de coach, en Historie vult een vak zonder prijs aan met de reserve.
const prijsbron = await import("../custom_components/domotiapp_coach/frontend/src/data-source.js");

proef("reserve: het paneel tekent de lijst van de coach als de reserve invalt of de sensor geen lijst heeft", () => {
  const nu = new Date();
  const begin = new Date(nu.getTime() - 5 * 60_000);
  const eind = new Date(nu.getTime() + 10 * 60_000);
  const contract = { type: "dynamic", dynamic: { source: "all_in", all_in_entity: "sensor.frank", fallback_entity: "sensor.np" } };
  const frank = { get: (id) => (id === "sensor.frank" ? { state: "0.30", attributes: { prices: [
    { from: begin.toISOString(), till: eind.toISOString(), price: 0.3 }] } } : undefined) };
  const weg = { get: (id) => (id === "sensor.frank" ? { state: "unavailable", attributes: {} } : undefined) };
  prijsbron.zetCoachPrijzen({ reserve: false, rows: [{ start: begin, end: eind, price: 0.27685, feedIn: 0.1 }] });
  assert.equal(prijsbron.priceForecast(frank, contract)[0].price, 0.3, "Frank werkt: Frank");
  assert.equal(prijsbron.priceNow(frank, contract), 0.3);
  assert.equal(prijsbron.priceForecast(weg, contract)[0].price, 0.27685, "Frank weg: de lijst van de coach");
  assert.equal(prijsbron.priceNow(weg, contract), 0.27685);
  prijsbron.zetCoachPrijzen({ reserve: true, rows: [{ start: begin, end: eind, price: 0.27685, feedIn: 0.1 }] });
  assert.equal(prijsbron.priceForecast(frank, contract)[0].price, 0.27685, "zegt de coach dat de reserve invalt, dan die");
  assert.ok(Math.abs(prijsbron.tariff(weg, contract).feedIn - 0.1) < 1e-9);
  assert.equal(prijsbron.reserveValtIn(), true);
  prijsbron.zetCoachPrijzen({});
  assert.deepEqual(prijsbron.priceForecast(weg, contract), [], "zonder lijst van de coach: niets, zoals altijd");
});

proef("Historie: een marktprijs krijgt belasting, opslag en btw, en een vak zonder prijs die van de reserve", () => {
  const markt = { type: "dynamic", dynamic: { source: "market", energy_tax: 0.1088, supplier_markup: 0.02, vat_percent: 21 } };
  const m = prijsbron.allInPrijzen(new Map([[1, 0.1]]), new Map([[1, 0.5], [2, 0.2]]), markt);
  assert.ok(Math.abs(m.get(1) - (0.1 + 0.1088 + 0.02) * 1.21) < 1e-9, `${m.get(1)}`);
  assert.ok(Math.abs(m.get(2) - (0.2 + 0.1088 + 0.02) * 1.21) < 1e-9, "de reserve is standaard een marktprijs");
  const allIn = { type: "dynamic", dynamic: { source: "all_in", fallback_source: "all_in", energy_tax: 0.1088, supplier_markup: 0.02, vat_percent: 21 } };
  const a = prijsbron.allInPrijzen(new Map([[1, 0.3]]), new Map([[1, 0.9], [2, 0.25]]), allIn);
  assert.equal(a.get(1), 0.3, "de eigen sensor gaat voor");
  assert.equal(a.get(2), 0.25, "een all-in reserve blijft zoals hij is");
});

proef("het formulier heeft een reserveprijssensor en zegt wat voor prijs hij geeft", () => {
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/installation.js", import.meta.url), "utf8");
  assert.ok(bron.includes('id="dyn-reserve"') && bron.includes('["dyn-reserve", "fallback_entity"]'));
  assert.ok(bron.includes('data-reserve="market"') && bron.includes('data-reserve="all_in"'));
  const py = readFileSync(new URL("../custom_components/domotiapp_coach/websocket.py", import.meta.url), "utf8");
  assert.ok(py.includes('vol.Optional("fallback_entity")') && py.includes('vol.Optional("fallback_source")'));
});

proef("de geschiedenis onder Meldingen laat twee weken zien (v0.101.5)", async () => {
  // De eigenaar op 29-09-2026: "max 2 weken, anders teveel scrollen."
  const { recent, GESCHIEDENIS_DAGEN } = await import("../custom_components/domotiapp_coach/frontend/src/views/notifications.js");
  assert.equal(GESCHIEDENIS_DAGEN, 14);
  const nu = new Date(2026, 8, 29, 14, 0);
  const op = (d, h = 12) => ({ at: new Date(2026, 8, d, h).toISOString(), message: "x" });
  const lijst = [op(29), op(16, 0), op(15, 23), op(1)];
  const over = recent(lijst, nu);
  assert.deepEqual(over.map((i) => new Date(i.at).getDate()), [29, 16], "vandaag en de dertien dagen ervoor, vanaf middernacht");
  assert.deepEqual(recent([{ at: "geen datum" }], nu), []);
});

proef("Apparaten: een apparaat hangt aan de hoofdkast, een onderverdeelkast of een groep", () => {
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.feed_ = {};
  el.draft_ = { installation: { circuits: [
    { id: "lounge", kind: "kast", name: "Lounge" }, { id: "paal", kind: "groep", name: "Laadpaal", parent: "lounge" },
  ] }, devices: [] };
  const paal = { id: "p", type: "laadpaal", brand: "easee", controllable: true, device_id: "x", circuit: "paal",
    entities: { status: "sensor.s", limit: "number.l" } };
  const html = el.controlHtml_(paal, 0);
  assert.ok(html.includes("Hangt aan") && html.includes(">Hoofdkast</option>"), html.slice(0, 200));
  assert.ok(html.includes(">Lounge (onderverdeelkast)</option>") && html.includes('value="paal" selected>Laadpaal (groep)</option>'));
});

// --- de accustand in kWh op de kaarten (v0.101.6) --------------------------------
// De eigenaar op 29-09-2026: "op de laadpaalkaart de batterijstand van de auto zien
// als die in HA staat, en de accu kWh van de batterij, nu zie ik alleen het percentage."
proef("accuTekst: het percentage met wat erin zit, en zonder inhoud alleen het percentage", async () => {
  const { accuTekst } = await import("../custom_components/domotiapp_coach/frontend/src/data-source.js");
  assert.equal(accuTekst(39, 14.5), "39 % · 5,7 van 14,5 kWh");
  assert.equal(accuTekst(68, 19.7), "68 % · 13,4 van 19,7 kWh");
  assert.equal(accuTekst(39, NaN), "39 %");
  assert.equal(accuTekst(39, 0), "39 %");
});

proef("de kaart van de thuisbatterij zegt hoeveel kWh erin zit, uit haar inhoudsensor of zoals ingevuld", () => {
  const staten = {
    "sensor.batterij_soc": { state: "39", attributes: { unit_of_measurement: "%" } },
    "sensor.batterij_inhoud": { state: "14500", attributes: { unit_of_measurement: "Wh" } },
  };
  const feed = { get: (id) => staten[id] };
  const accu = { id: "b", type: "thuisbatterij", brand: "anker", entity: "", entities: { soc: "sensor.batterij_soc", capacity: "sensor.batterij_inhoud" } };
  const r = new LiveSource().sample(feed, { sources: {}, devices: [accu] });
  const regel = r.devices[0].details.find((d) => d.label === "Accustand");
  assert.equal(regel?.text, "39 % · 5,7 van 14,5 kWh", JSON.stringify(r.devices[0].details));
  const ingevuld = { ...accu, entities: { soc: "sensor.batterij_soc" }, battery: { capacity_kwh: 10 } };
  const r2 = new LiveSource().sample(feed, { sources: {}, devices: [ingevuld] });
  assert.equal(r2.devices[0].details.find((d) => d.label === "Accustand")?.text, "39 % · 3,9 van 10,0 kWh");
});

proef("de laadpaalkaart laat de accustand van de auto zien als die in Home Assistant staat", () => {
  const staten = {
    "sensor.ford_soc": { state: "68", attributes: { unit_of_measurement: "%" } },
    "sensor.tesla_soc": { state: "unavailable", attributes: {} },
  };
  const feed = { get: (id) => staten[id] };
  const ford = { id: "ford", name: "Ford", soc_entity: "sensor.ford_soc", capacity_kwh: 19.7 };
  const tesla = { id: "tesla", name: "Tesla", soc_entity: "sensor.tesla_soc", capacity_kwh: 75 };
  const gast = { id: "gast", name: "Gast", guest: true, soc_entity: "sensor.ford_soc" };
  const zonder = { id: "oud", name: "Oude auto", capacity_kwh: 40 };
  const paal = { id: "p", type: "laadpaal", brand: "easee", entity: "", entities: {}, cars: [ford, tesla, gast, zonder] };
  const regels = (settings) => new LiveSource().sample(feed, { sources: {}, devices: [paal], ...settings }).devices[0].details
    .filter((d) => d.label.startsWith("Accu"));
  assert.deepEqual(regels({ active_cars: [{ device: "p", car: "ford" }] }),
    [{ label: "Accu auto", text: "68 % · 13,4 van 19,7 kWh" }], "de gekozen auto");
  assert.deepEqual(regels({ active_cars: [{ device: "p", car: "tesla" }] }),
    [{ label: "Accu auto", text: "—" }], "een gekozen auto waarvan de sensor niets zegt");
  assert.deepEqual(regels({}), [{ label: "Accu auto", text: "68 % · 13,4 van 19,7 kWh" }],
    "zonder keuze de eerste auto, net als de keuzelijst op de kaart");
  // De eigenaar op 29-09-2026: "als ik de gastauto kies blijft de accu auto stand staan
  // in de kaart, dat moet niet" (v0.101.7).
  assert.deepEqual(regels({ active_cars: [{ device: "p", car: "__guest__" }] }), [], "de gast: geen accustand");
  assert.deepEqual(regels({ active_cars: [{ device: "p", car: "oud" }] }), [],
    "een gekozen auto zonder sensor vraagt het op de kaart zelf");
});

// De bewoner van de eerste woning op 01-10-2026, bij "Accu auto 28 % · 21,8 van 78,0 kWh":
// "Ik denk dat de meeste consumenten dat niets zegt ... Dus 'accu auto - 28% - 138 van
// 493 km'." Met een sensor voor de actieradius in kilometers (v0.106.0).
proef("de laadpaalkaart zegt de actieradius in kilometers als de auto die meldt", async () => {
  const { actieradius, radiusTekst } = await import("../custom_components/domotiapp_coach/frontend/src/data-source.js");
  const staten = {
    "sensor.tesla_soc": { state: "28", attributes: { unit_of_measurement: "%" } },
    "sensor.tesla_range": { state: "137.9", attributes: { unit_of_measurement: "km", device_class: "distance" } },
    "sensor.mijl": { state: "85.7", attributes: { unit_of_measurement: "mi" } },
    "sensor.vreemd": { state: "137.9", attributes: { unit_of_measurement: "parsec" } },
    "sensor.weg": { state: "unavailable", attributes: { unit_of_measurement: "km" } },
    "sensor.laag": { state: "6", attributes: { unit_of_measurement: "%" } },
  };
  const feed = { get: (id) => staten[id] };
  const tesla = { id: "tesla", name: "Model Y", soc_entity: "sensor.tesla_soc", range_entity: "sensor.tesla_range", capacity_kwh: 78 };
  const paal = { id: "p", type: "laadpaal", brand: "alfen", entity: "", entities: {}, cars: [tesla] };
  const regel = (auto) => new LiveSource().sample(feed, { sources: {}, devices: [{ ...paal, cars: [auto] }] })
    .devices[0].details.find((d) => d.label === "Accu auto")?.text;
  assert.equal(regel(tesla), "28% · 138 van 493 km", "het voorbeeld van de bewoner");
  assert.equal(regel({ ...tesla, range_entity: "sensor.mijl" }), "28% · 138 van 493 km", "mijlen worden kilometers");
  assert.equal(regel({ ...tesla, range_entity: "sensor.vreemd" }), "28 % · 21,8 van 78,0 kWh", "een onbekende eenheid telt niet");
  assert.equal(regel({ ...tesla, range_entity: "sensor.weg" }), "28 % · 21,8 van 78,0 kWh", "een sensor die niets zegt ook niet");
  assert.equal(regel({ ...tesla, range_entity: "" }), "28 % · 21,8 van 78,0 kWh", "zonder sensor zoals het was");
  // Onder 10% is de volle radius uit hele procenten niet na te rekenen.
  const laag = actieradius(feed, { ...tesla, soc_entity: "sensor.laag" });
  assert.equal(laag.perProcent, null);
  assert.equal(radiusTekst(6, laag), "6% · 138 km");
  assert.equal(actieradius(feed, { ...tesla, soc_entity: "" }), null, "zonder accustand geen radius");
});

proef("de laadpaalkaart zegt wat er deze laadbeurt in ging, en daarna wat de laatste opleverde", async () => {
  const { laadbeurtRegels } = await import("../custom_components/domotiapp_coach/frontend/src/data-source.js");
  const staten = {
    "sensor.tesla_soc": { state: "33", attributes: { unit_of_measurement: "%" } },
    "sensor.tesla_range": { state: "162.5", attributes: { unit_of_measurement: "km" } },
  };
  const feed = { get: (id) => staten[id] };
  const tesla = { id: "tesla", name: "Model Y", soc_entity: "sensor.tesla_soc", range_entity: "sensor.tesla_range", capacity_kwh: 78 };
  const paal = { id: "p", type: "laadpaal", brand: "alfen", entity: "", entities: {}, cars: [tesla] };
  const beurt = (session) => laadbeurtRegels(feed, paal, {}, { session });
  assert.deepEqual(beurt({ active: true, kwh: 0, soc_start: 28, soc_end: 28 }),
    [{ label: "Deze laadbeurt", text: "nog niets" }], "de kabel zit erin en hij wacht");
  assert.deepEqual(beurt({ active: true, kwh: 4.234, soc_start: 28, soc_end: 32.6 }),
    [{ label: "Deze laadbeurt", text: "4,2 kWh · +5% · +25 km" }], "kWh, procenten en kilometers");
  assert.deepEqual(beurt({ active: false, kwh: 20.4, soc_start: 28, soc_end: 54 }),
    [{ label: "Laatste laadbeurt", text: "20,4 kWh · +26% · +128 km" }], "na het loskoppelen blijft hij staan");
  assert.deepEqual(beurt({ active: false, kwh: 3.21, soc_start: null, soc_end: null }),
    [{ label: "Laatste laadbeurt", text: "3,2 kWh" }], "een beurt van voor v0.106.0: alleen de kWh");
  assert.deepEqual(beurt({ active: true, kwh: 4.2, soc_start: 28, soc_end: 33, soc_estimated: true }),
    [{ label: "Deze laadbeurt", text: "4,2 kWh" }], "een geschatte stand geeft geen procenten");
  // Zonder sensor voor de actieradius alleen kWh en procenten.
  const zonder = { ...paal, cars: [{ ...tesla, range_entity: "" }] };
  assert.deepEqual(laadbeurtRegels(feed, zonder, {}, { session: { active: true, kwh: 4.2, soc_start: 28, soc_end: 33 } }),
    [{ label: "Deze laadbeurt", text: "4,2 kWh · +5%" }]);
  assert.deepEqual(beurt(null), [], "nog nooit geladen: geen regel");
  assert.deepEqual(laadbeurtRegels(feed, { ...paal, type: "boiler" }, {}, { session: { active: true, kwh: 1 } }), [],
    "alleen bij een laadpaal");
});

/** Een historieweergave met een dag aan vakken, de batterij en een beurt. */
function geldweergave() {
  const el = Object.create(Historie.prototype);
  el.period_ = "day";
  el.offset_ = 0;
  const vandaag = new Date();
  vandaag.setHours(12, 0, 0, 0);
  const dag = `${vandaag.getFullYear()}-${String(vandaag.getMonth() + 1).padStart(2, "0")}-${String(vandaag.getDate()).padStart(2, "0")}`;
  el.settings_ = {
    contract: VAST,
    sources: { meters: { solar_total: "sensor.zon", import_low: "sensor.af", export_low: "sensor.terug" } },
    devices: [
      { id: "bat", type: "thuisbatterij", name: "Batterij", controllable: true, battery: {} },
      { id: "vw", type: "vaatwasser", name: "Vaatwasser", controllable: true },
    ],
    battery_state: [{ device: "bat", earned_days: { [dag]: 0.034 }, earned_total: 0.034 }],
  };
  el.rowsShown_ = [{ start: vandaag, own: 5, bought: 1, sold: 3, used: 6 }];
  el.rows_ = { gas: [], water: [] };
  el.prices_ = new Map();
  el.feed_ = { get: () => null };
  el.beurten_ = [{ device: "vw", name: "Vaatwasser", plugged_at: vandaag.toISOString(), ended: vandaag.toISOString(),
                   complete: true, kwh: 0.908, solar_kwh: 0.329, battery_kwh: 0.553, paid: 0.199, ref_cost: 0.217,
                   saved: 0.018, solar_saved: 0.018 }];
  return el;
}

proef("In geld rekent met het kasboek van de batterij en met de beurten van die dag", () => {
  const g = geldweergave().geld_();
  assert.ok(Math.abs(g.delen.accu - 0.034) < 1e-9, `${g.delen.accu}`);
  assert.ok(Math.abs(g.delen.coach - 0.018) < 1e-9, `${g.delen.coach}`);
  assert.ok(Math.abs(g.delen.zon + g.delen.accu + g.delen.coach - g.bespaard) < 1e-9);
  assert.equal(g.metAccu, true);
  assert.equal(g.metCoach, true);
});

proef("de uitleg van In geld noemt het salderen en waar de delen vandaan komen", () => {
  const el = geldweergave();
  const zin = el.geldUitleg_(el.geld_());
  assert.match(zin, /Je saldeert nog tot 1 januari 2027/);
  assert.match(zin, /kasboek/);
  assert.match(zin, /Door de coach/);
});

proef("het bolletje van de laadpaal en de boiler is groen als ze aan staan", () => {
  const paal = (w) => kaartKnoppen({
    missed: null,
    apparaat: { id: "d2", type: "laadpaal", name: "Laadpaal", brand: "easee", controllable: true,
                entities: {}, details: [], watts: w, cars: [] },
  });
  const laadt = paal(7400);
  assert.equal(laadt.groen, true);
  assert.equal(laadt.staat, " (laadt)");
  assert.equal(paal(0).groen, false);
  const boiler = kaartKnoppen({
    missed: null,
    apparaat: { id: "d2", type: "boiler", name: "Boiler", controllable: true, entities: {}, details: [], watts: 2000 },
  });
  assert.equal(boiler.groen, true);
  assert.equal(boiler.staat, " (verwarmt)");
});

// --- draaien ----------------------------------------------------------------

let goed = 0;
let fout = 0;
for (const [naam, fn] of proeven) {
  try {
    await fn();
    goed += 1;
    console.log(`  ${naam}`);
  } catch (error) {
    fout += 1;
    console.log(`  FOUT  ${naam}`);
    console.log(`        ${error.message.split("\n")[0]}`);
  }
}
console.log(`\n${goed} goed, ${fout} fout`);
process.exit(fout ? 1 : 0);
