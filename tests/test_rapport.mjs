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

proef("het installatiescherm heeft een plek voor groepen met een eigen zekering", () => {
  const html = Object.create(Installatie.prototype).render();
  assert.ok(html.includes('id="circuits"'), "de lijst van groepen");
  assert.ok(html.includes('id="circuit-add"'), "en een knop om er een toe te voegen");
});

proef("een groep wordt een blok met naam, zekering, fasen, de groep erboven en sensoren", () => {
  const el = Object.create(Installatie.prototype);
  const garage = { id: "garage", name: "Garage", fuse_amps: 16, phases: 3, parent: "", sensors: {} };
  const carport = { id: "carport", name: "Carport", fuse_amps: 16, phases: 1, parent: "garage", sensors: {} };
  const html = el.circuitHtml_(carport, 1, [garage, carport]);
  assert.ok(html.includes('value="Carport"'));
  assert.ok(html.includes('<option value="garage" selected>Garage</option>'), "hangt onder de garage");
  assert.ok(!html.includes('value="carport"'), "een groep hangt niet onder zichzelf");
  assert.equal((html.match(/data-kind="current"/g) ?? []).length, 1, "één fase, dus één stroomsensor");
  assert.equal((el.circuitHtml_(garage, 0, [garage, carport]).match(/data-kind="current"/g) ?? []).length, 3);
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
      append(...items) { kinderen.push(...items); },
      replaceChildren(...items) { kinderen.length = 0; kinderen.push(...items); },
    };
  };
  for (const id of ["#vooruit-title", "#vooruit-nu", "#vooruit-kop", "#vooruit-uren", "#vooruit-voet"]) {
    knopen.set(id, maak());
  }
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
        programOptions, programRows, programChooser, apparatenZin, canSteer, brandsFor, brandFields, canHaveDeadline } =
  await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
const { timesFor } = await import("../custom_components/domotiapp_coach/frontend/src/schedule-sheet.js");
// De eigenaar op 07-09-2026: "de coach zegt zet nu de tablet lader aan, maar de
// tablet lader is alleen een vermogenssensor en het vinkje staat uit."
proef("de tip noemt alleen apparaten waarbij het vinkje aan staat", () => {
  const tablet = { type: "overig", name: "Tablet lader", controllable: false };
  const paal = { type: "laadpaal", name: "Laadpaal", brand: "easee", controllable: true };
  const dom = { type: "vaatwasser", brand: "overig", name: "Vaatwasser", controllable: true };
  assert.equal(apparatenZin([tablet, paal, dom]), "de laadpaal of de vaatwasser");
  assert.equal(apparatenZin([tablet]), "");
  assert.equal(apparatenZin([{ ...tablet, controllable: true }]), "de Tablet lader");
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
  el.items_ = [
    { at: "2026-09-05T13:40:00", message: "De accustand van Ford meldt al 10 minuten niets.", kind: "kritiek" },
    { at: "2026-09-05T11:10:00", message: "De status van Laadpaal meldt al 10 minuten niets." },
    { at: "2026-09-05T09:42:00", message: "Laadpaal: laden op 6 A.", kind: "besluit" },
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
  assert.match(knopen.get("#lijst").kinderen[0].textContent, /nog niets gemeld/, "leeg is een zin, geen leeg scherm");
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
function kaartKnoppen({ ready = [], now = [], missed = "2026-09-12T16:30:00", running = false } = {}) {
  const stub = () => {
    const doel = {
      hidden: false, innerHTML: "", textContent: "", value: "", dataset: {}, style: {}, attrs: {},
      setAttribute(k, v) { this.attrs[k] = v; },
      getAttribute(k) { return this.attrs[k]; },
      classList: { toggle() {}, add() {}, remove() {}, contains: () => false },
      replaceChildren() {}, append() {}, addEventListener() {}, close() {}, focus() {},
      querySelector: () => stub(), querySelectorAll: () => [],
    };
    return doel;
  };
  const knopen = new Map();
  const el = Object.create(Overzicht.prototype);
  el.$ = (kiezer) => { if (!knopen.has(kiezer)) knopen.set(kiezer, stub()); return knopen.get(kiezer); };
  el.$$ = () => [];
  const device = { id: "d2", type: "vaatwasser", name: "Vaatwasser", brand: "home_connect",
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
const { batteryRows, volgendeNetlading, terugverdiendTekst } = await import(
  "../custom_components/domotiapp_coach/frontend/src/battery.js"
);

proef("de thuisbatterij staat weer in de lijst, met Anker en Overig als merk", () => {
  assert.ok(TYPES.some((t) => t.id === "thuisbatterij"));
  assert.deepEqual(BATTERY_BRANDS.map((b) => b.id), ["anker", "overig"]);
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
  payback: { earned: 45, price: 4500, days: 30, min_days: 28, date: "2034-11-08" },
};

proef("de kaart van een batterij: stand, opdracht, waarde, netlading en terugverdientijd", () => {
  const rijen = Object.fromEntries(batteryRows(BESLUIT_BATTERIJ).map((r) => [r.label, r.text]));
  assert.equal(rijen["Stand"], "Laden van het net");
  assert.equal(rijen["Opdracht van de coach"], "laden op 1.750 W");
  assert.equal(rijen["Een kWh erin is straks waard"], "€ 0,245");
  assert.equal(rijen["Laadt van het net"], "02:00 tot 04:00, ongeveer 3,5 kWh");
  assert.equal(rijen["Terugverdiend"], "€ 45,00 van € 4.500");
  assert.match(rijen["Terugverdiend rond"], /november 2034, in het tempo van de laatste 30 gemeten dagen/);
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

proef("te vroeg voor een datum zegt hoeveel dagen er gemeten zijn", () => {
  const rijen = terugverdiendTekst({ earned: 12.5, price: 4500, days: 9, min_days: 28, date: null });
  assert.equal(rijen[1].text, "nog te vroeg voor een datum: 9 van de 28 dagen gemeten");
});

proef("zonder aankoopprijs alleen wat hij opleverde", () => {
  const rijen = terugverdiendTekst({ earned: 12.5, price: null, days: 9, date: null });
  assert.deepEqual(rijen, [{ label: "Opgeleverd", text: "€ 12,50 in 9 dagen" }]);
  assert.deepEqual(terugverdiendTekst({ earned: 0, price: null, days: 0 }), []);
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
