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
await import("../custom_components/domotiapp_coach/frontend/src/views/contract.js");
const Contract = geregistreerd.get("dac-view-contract");
assert.ok(Contract, "het contractscherm hoort zich te registreren (v0.114.0)");
const { heeftVoorkeuren, voorkeurHtml, vulVoorkeuren, voorkeurWijziging } = await import(
  "../custom_components/domotiapp_coach/frontend/src/voorkeur-velden.js"
);

/** De velden van Instellen als nepelementen, zodat `vulVoorkeuren` ze kan zetten. */
function nepVelden(html) {
  const camel = (s) => s.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
  const els = [];
  for (const m of html.matchAll(/<(input|select|button)([^>]*)>/g)) {
    const attrs = Object.fromEntries([...m[2].matchAll(/([a-z-]+)="([^"]*)"/g)].map(([, k, v]) => [k, v]));
    const dataset = {};
    for (const [k, v] of Object.entries(attrs)) if (k.startsWith("data-")) dataset[camel(k.slice(5))] = v;
    els.push({ tag: m[1], type: attrs.type ?? "", dataset, value: "", checked: false, attrs: {},
               setAttribute(n, v) { this.attrs[n] = v; } });
  }
  const rijen = [...html.matchAll(/data-vk-rij="([^"]+)"/g)].map(([, s]) => ({ sleutel: s, hidden: false }));
  return {
    els, rijen,
    veld: (attr, sleutel) => els.find((e) => e.dataset[camel(attr.slice(5))] === sleutel),
    querySelectorAll(kiezer) {
      const sleutel = camel(kiezer.match(/^\[data-([a-z-]+)\]$/)[1]);
      return els.filter((e) => sleutel in e.dataset);
    },
    querySelector(kiezer) {
      return rijen.find((r) => r.sleutel === kiezer.match(/data-vk-rij="([^"]+)"/)?.[1]) ?? null;
    },
  };
}

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
      getAttribute(naam) { return this.attrs[naam] ?? null; },
      append(...items) { kinderen.push(...items); },
      replaceChildren(...items) { kinderen.length = 0; kinderen.push(...items); },
      // Sinds v0.129.0 wacht de prijsgrafiek op een tik.
      luisteraars: {},
      addEventListener(soort, fn) { this.luisteraars[soort] = fn; },
      querySelectorAll() { return []; },
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
proef("iedereen ziet alle personen (v0.114.0, was: een bewoner alleen zichzelf)", () => {
  const mensen = [
    { id: "p-1", name: "Bewoner", target: "mobile_app_telefoon", user_id: "u-1" },
    { id: "p-2", name: "Partner", target: "mobile_app_partner", user_id: "u-partner" },
    { id: "p-3", name: "Tablet", target: "mobile_app_tablet", user_id: "" },
    { id: "p-4", name: "leeg", target: "" },
  ];
  assert.deepEqual(zichtbaar(mensen, { id: "u-x", is_admin: true }).map((p) => p.id), ["p-1", "p-2", "p-3"]);
  // De eigenaar op 12-10-2026: de bewoner beheert de personen, "Ja dat mag de bewoner."
  assert.deepEqual(zichtbaar(mensen, { id: "u-partner", is_admin: false }).map((p) => p.id), ["p-1", "p-2", "p-3"]);
  assert.deepEqual(zichtbaar(mensen, { id: "u-niemand", is_admin: false }).length, 3, "niet gekoppeld: ook iedereen");
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

// Meldingen in groepen die uitklappen (v0.133.2). De eigenaar op 19-10-2026: "ik wil wel bij
// meldingen dat je alles groepeert en alles kan uitklappen, nu staat alles op een vaste
// positie onder elkaar en wordt het onoverzichtelijk."
proef("Meldingen: vier groepen die uitklappen, met de stand in de kop (v0.133.2)", async () => {
  const { geschiedenisStand, STANDAARD_OPEN } = await import("../custom_components/domotiapp_coach/frontend/src/views/notifications.js");
  const html = Object.create(Meldingen.prototype).render();
  for (const groep of ["wie", "herinnering", "waarschuwingen", "geschiedenis"]) {
    assert.ok(html.includes(`<details class="groep" data-groep="${groep}"`), `de groep ${groep}`);
  }
  for (const id of ["belasting", "verbruik", "warmte", "stekker"]) {
    assert.ok(html.includes(`<details class="blok sub" id="${id}" hidden>`) && html.includes(`id="stand-${id}"`), `${id} klapt apart uit`);
  }
  assert.deepEqual(STANDAARD_OPEN, { wie: false, herinnering: false, waarschuwingen: false, geschiedenis: true });
  const nu = new Date(2026, 9, 20, 12, 0);
  assert.equal(geschiedenisStand([], nu), "Niets vandaag");
  assert.equal(geschiedenisStand([
    { at: "2026-10-20T09:00:00", message: "a", kind: "kritiek" },
    { at: "2026-10-20T10:00:00", message: "b" },
    { at: "2026-10-19T10:00:00", message: "c" },
  ], nu), "2 vandaag, 1 kritiek");
  // De stand in de kop: wie, de herinnering, en hoeveel waarschuwingen aan staan.
  const tekst = new Map();
  const knoop = (id) => ({ hidden: false, textContent: "", classList: { toggle() {} }, set text(v) { tekst.set(id, v); } });
  const knopen = new Map(["#stand-wie", "#stand-herinnering", "#stand-waarschuwingen", "#stand-geschiedenis", "#waarschuwingen",
    "#belasting", "#verbruik", "#warmte", "#stekker", "#stand-belasting", "#stand-verbruik", "#stand-warmte", "#stand-stekker"]
    .map((id) => [id, knoop(id)]));
  knopen.get("#warmte").hidden = true;
  knopen.get("#stekker").hidden = true;
  const el = Object.create(Meldingen.prototype);
  el.$ = (id) => knopen.get(id) ?? null;
  el.hass_ = { user: { is_admin: false } };
  el.geladen_ = true;
  el.items_ = [];
  el.settings_ = { notifications: { people: [{ target: "mobile_app_a" }, { target: "mobile_app_b" }],
    load_alert: { enabled: true }, usage_alert: { enabled: false } }, reminders: {} };
  el.paintStanden_();
  assert.equal(knopen.get("#stand-wie").textContent, "2 personen");
  assert.equal(knopen.get("#stand-herinnering").textContent, "Niets ingesteld");
  assert.equal(knopen.get("#stand-waarschuwingen").textContent, "1 van 2 aan", "alleen de waarschuwingen die er zijn");
  assert.equal(knopen.get("#stand-belasting").textContent, "aan");
  assert.equal(knopen.get("#stand-verbruik").textContent, "uit");
});

// De eigenaar op 10-10-2026: "ook wil ik een melding kunnen laten sturen wanneer de
// temperatuur te hoog is en dat je zelf een doel kan instellen zoals boven x dan melding."
proef("Thuisbatterij te warm in Meldingen: alleen met een batterij, en de hint zegt wat er nog moet (v0.108.0)", () => {
  const knoop = () => ({ hidden: false, value: "", textContent: "", attrs: {}, setAttribute(n, v) { this.attrs[n] = v; } });
  const knopen = new Map(["#warmte", "#warmte-aan", "#warmte-velden", "#warmte-grens", "#warmte-grens-hint"].map((k) => [k, knoop()]));
  const el = Object.create(Meldingen.prototype);
  el.$ = (kiezer) => knopen.get(kiezer) ?? null;
  el.hass_ = { user: { is_admin: true }, states: { "sensor.accu_temp": { state: "28.0" } } };
  el.settings_ = { devices: [{ type: "laadpaal" }], notifications: {} };
  el.paintWarmte_();
  assert.equal(knopen.get("#warmte").hidden, true, "zonder thuisbatterij geen blok");

  const accu = { type: "thuisbatterij", name: "Accu", entities: {} };
  el.settings_ = { devices: [accu], notifications: { temp_alert: { enabled: false, max_c: null } } };
  el.paintWarmte_();
  assert.equal(knopen.get("#warmte").hidden, false);
  assert.equal(knopen.get("#warmte-aan").attrs["aria-checked"], "false");
  assert.equal(knopen.get("#warmte-velden").hidden, true, "uit: geen grens te zien");
  assert.match(knopen.get("#warmte-grens-hint").textContent, /^Vul eerst de temperatuur van de batterij in onder Apparaten/);

  accu.entities.temperature = "sensor.accu_temp";
  el.settings_.notifications.temp_alert.enabled = true;
  el.paintWarmte_();
  assert.equal(knopen.get("#warmte-velden").hidden, false);
  assert.equal(knopen.get("#warmte-grens").value, "", "geen grens die niemand koos");
  assert.equal(knopen.get("#warmte-grens-hint").textContent, "Vul in boven welke temperatuur je een bericht wilt.");

  el.settings_.notifications.temp_alert.max_c = 45;
  el.paintWarmte_();
  assert.equal(knopen.get("#warmte-grens").value, 45);
  assert.equal(knopen.get("#warmte-grens-hint").textContent, "Nu 28 °C.");

  el.hass_.user.is_admin = false;
  el.paintWarmte_();
  assert.equal(knopen.get("#warmte").hidden, false, "sinds v0.114.0 ook voor de bewoner, net als de andere meldingen");
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
  // Sinds v0.133.2 is elke dag een blok dat uitklapt: een kop met het aantal, en de rijen erin.
  const lijst = knopen.get("#lijst").kinderen;
  assert.equal(lijst.length, 1, "één dag");
  assert.equal(lijst[0].className, "dag");
  assert.equal(lijst[0].open, true, "zonder meldingen van vandaag staat de eerste dag open");
  const dagblok = lijst[0].kinderen;
  assert.equal(dagblok.length, 4, "een kop en drie rijen");
  assert.deepEqual(dagblok[0].kinderen.map((k) => k.textContent), ["Gisteren", "3, 1 kritiek"]);
  assert.equal(dagblok[1].className, "rij kritiek", "kritiek valt op");
  assert.equal(dagblok[2].className, "rij melding", "een melding krijgt een kader");
  assert.equal(dagblok[3].className, "rij besluit", "een besluit staat er kaal tussen");
  // Vóór de volgende paint_, want die leegt dezelfde kinderen-lijst.
  assert.deepEqual(dagblok[1].kinderen.map((k) => k.textContent),
    ["13:40", "De accustand van Ford meldt al 10 minuten niets."]);

  el.filter_ = { soort: "kritiek", dag: "" };
  el.paint_();
  assert.equal(knopen.get("#lijst").kinderen[0].kinderen.length, 2, "met het filter op kritiek blijft één rij over");
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
  // Sinds v0.114.0 in Instellen op de kaart, en niet meer onder Apparaten.
  assert.ok(!el.controlHtml_(hc, 0).includes("release_required"), "niet meer onder Apparaten");
  const vrij = nepVelden(voorkeurHtml(hc));
  assert.ok(vrij.veld("data-vk", "release_required"), "het vinkje staat in Instellen bij Home Connect");
  vulVoorkeuren(vrij, hc);
  assert.equal(vrij.veld("data-vk", "release_required").checked, true, "standaard aan");
  vrij.veld("data-vk", "release_required").checked = false;
  assert.deepEqual(voorkeurWijziging(vrij.veld("data-vk", "release_required")), { release_required: false });
  assert.equal(voorkeurHtml(dom), "", "en niet bij een domme vaatwasser");
  assert.equal(heeftVoorkeuren(dom), false);

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
  // Sinds v0.114.0 in Instellen op de kaart van de paal, niet meer onder Apparaten.
  assert.ok(!el.carsHtml_(paal, 0).includes('data-car-field="target_percent"'), "niet meer onder Apparaten");
  const html = voorkeurHtml(paal);
  assert.ok(html.includes('data-vk-auto="auto:target_percent"'), "het veld staat in Instellen");
  assert.ok(html.includes("Bus: laadt tot (%)"), "en heet naar wat het doet, met de naam van de auto");
  // Een auto zonder het veld is een oude instelling: die laadt gewoon vol.
  const velden = nepVelden(html);
  vulVoorkeuren(velden, paal);
  assert.equal(velden.veld("data-vk-auto", "auto:target_percent").value, 100, "zonder ingevuld doel staat er 100");
  vulVoorkeuren(velden, { ...paal, cars: [{ ...paal.cars[0], target_percent: 80 }] });
  assert.equal(velden.veld("data-vk-auto", "auto:target_percent").value, 80, "en een ingevuld doel staat er zoals het is");
  // De server weigert alles onder de 10, dus een veld dat leeggemaakt wordt mag
  // geen nul opleveren: dat zou een foutmelding geven over iets wat de klant
  // niet deed.
  assert.ok(html.includes('min="10"') && html.includes('max="100"'), "de invoer blijft binnen bereik");
  const veld = velden.veld("data-vk-auto", "auto:target_percent");
  veld.value = "";
  assert.equal(voorkeurWijziging(veld), null, "leeg is niets om op te slaan");
  veld.value = "5";
  assert.deepEqual(voorkeurWijziging(veld), { cars: [{ id: "auto", target_percent: 10 }] }, "en onder de 10 wordt 10");
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
  // De keuze handmatig of elk uur is sinds v0.114.0 van de bewoner: Instellen.
  assert.ok(!tesla.includes("data-car-wake-mode"), "de keuze staat niet meer onder Apparaten");
  const teslaPaal = { ...paal, cars: [{ id: "a", name: "Model Y", brand: "tesla", wake_entity: "button.wake", wake_mode: "hourly" }] };
  const wek = nepVelden(voorkeurHtml(teslaPaal));
  assert.ok(wek.veld("data-vk-wek", "a:manual") && wek.veld("data-vk-wek", "a:hourly"), "en de keuze in Instellen");
  vulVoorkeuren(wek, teslaPaal);
  assert.equal(wek.veld("data-vk-wek", "a:hourly").attrs["aria-pressed"], "true", "met de gekozen stand ingedrukt");
  assert.deepEqual(voorkeurWijziging(wek.veld("data-vk-wek", "a:manual")), { cars: [{ id: "a", wake_mode: "manual" }] });
  assert.ok(!voorkeurHtml({ ...teslaPaal, cars: [{ ...teslaPaal.cars[0], wake_entity: "" }] }).includes("data-vk-wek"),
    "zonder wekknop valt er niets te kiezen");
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
  // Sinds v0.114.0 in Instellen op de kaart van de batterij.
  assert.ok(!el.batteryHtml_(accu, 0).includes('data-bat-field="holiday"'), "niet meer onder Apparaten");
  const html = voorkeurHtml(accu);
  assert.ok(html.includes('data-vk-accu="holiday"') && html.includes('data-vk-accu="holiday_max_percent"'));
  const velden = nepVelden(html);
  vulVoorkeuren(velden, accu);
  const rij = velden.rijen.find((r) => r.sleutel === "holiday_max_percent");
  assert.equal(rij.hidden, false, "de grens is zichtbaar als de stand aanstaat");
  assert.equal(velden.veld("data-vk-accu", "holiday_max_percent").value, 60);
  vulVoorkeuren(velden, { ...accu, battery: { ...accu.battery, holiday: false } });
  assert.equal(rij.hidden, true, "en weg als hij uit staat");
  assert.equal(html.split('data-vk-accu="holiday_max_percent"').length - 1, 1, "de grens staat precies een keer in het formulier (23-09-2026: hij stond er twee keer)");
  assert.equal(html.split('data-vk-accu="holiday"').length - 1, 1, "de vink staat precies een keer");
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
  assert.match(b.balken[1].tip, /, laden$/);
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
  // Sinds v0.129.0 staat de kaart met het moment erboven; de kop op naam.
  const kop = blok.kinderen.find((k) => k.className === "prijs-kop").kinderen[1].kinderen;
  // 03:00: 11,0 kWh van het net tegen 0,2215; 04:00: 11,0 - 2,4 = 8,6 kWh tegen 0,2113.
  // (0,2215 x 11 + 0,2113 x 8,6) / 19,6 = 0,2170.
  assert.equal(kop[1].textContent, "€ 0,217", JSON.stringify(kop));
  // Zonder iets van het net staat er rechts niets meer (v0.130.1): het vlak met
  // het moment erboven zegt het al.
  const zon = vooruitScherm({ ...NACHT, blocks: NACHT.blocks.map((b) => ({ ...b, solar_kwh: b.kwh })) });
  zon.el.paint_();
  const zonKop = zon.knopen.get("#vooruit-prijs").kinderen.find((k) => k.className === "prijs-kop");
  assert.equal(zonKop.kinderen.length, 1, JSON.stringify(zonKop.kinderen.map((k) => k.textContent)));
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/plan-ahead-sheet.js", import.meta.url), "utf8");
  assert.ok(!bron.includes(': "in deze uren niets van het net"') && bron.includes('wacht: "Nul op de meter", gemiddelde: false'));
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

// De eigenaar op 19-10-2026: "als ik de slider naar rechts swipe schiet hij weer terug naar
// links." De pop-up tekende bij elk besluit van de coach de grafiek opnieuw (v0.129.1).
proef("hetzelfde plan opnieuw tekenen laat de prijsgrafiek staan, een ander plan bouwt hem opnieuw", () => {
  const { el, knopen } = vooruitScherm(NACHT);
  el.paint_();
  const blok = knopen.get("#vooruit-prijs");
  const eerst = blok.kinderen[0];
  el.paint_();
  assert.equal(blok.kinderen[0], eerst, "hetzelfde plan: dezelfde grafiek, dus waar je veegde blijft staan");
  el.plan_ = { ...NACHT, blocks: NACHT.blocks.map((b, i) => (i === 0 ? { ...b, price: (b.price ?? 0) + 0.01 } : b)) };
  el.paint_();
  assert.notEqual(blok.kinderen[0], eerst, "een ander plan: opnieuw getekend");
});

proef("de pop-up zegt 'prijs per kwartier' bij kwartierprijzen", () => {
  const k = (m, charging) => ({ start: `2026-08-30T03:${String(m).padStart(2, "0")}:00`,
    end: `2026-08-30T03:${String(m + 14).padStart(2, "0")}:59`, price: 0.2 + m / 1000, charging, why: "x",
    solar_kwh: 0, kwh: charging ? 2.7 : 0, amps: charging ? 16 : 0, kw: charging ? 11 : 0 });
  const { el, knopen } = vooruitScherm({ ...NACHT, blocks: [k(0, false), k(15, true), k(30, true), k(45, false)] });
  el.paint_();
  const kop = knopen.get("#vooruit-prijs").kinderen.find((k) => k.className === "prijs-kop").kinderen[0];
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
  // Sinds v0.133.0 ook de boiler en de programma's (`paintAnder_`).
  assert.equal(sheet.split("this.paintPrijs_(").length - 1, 4, "leeg maken, de paal, de batterij, en de boiler en programma's");
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
  // Sinds v0.114.0 in Instellen op de kaart, niet meer onder Apparaten.
  assert.ok(!el.controlHtml_(paal, 0).includes("charge_mode"), "niet meer onder Apparaten");
  const velden = nepVelden(voorkeurHtml(paal));
  assert.ok(velden.veld("data-vk", "charge_mode"), "de keuzelijst staat erin");
  vulVoorkeuren(velden, paal);
  assert.equal(velden.veld("data-vk", "charge_mode").value, "continu", "met de keuze van de paal");
  assert.equal(velden.veld("data-vk", "continuous_amps").value, 10);
  vulVoorkeuren(velden, { ...paal, charge_mode: undefined });
  assert.equal(velden.veld("data-vk", "charge_mode").value, "goedkoopst", "een paal zonder keuze is goedkoopst, zoals hij altijd deed");
  const stroom = velden.veld("data-vk", "continuous_amps");
  stroom.value = "40";
  assert.deepEqual(voorkeurWijziging(stroom), { continuous_amps: 32 }, "nooit boven de 32");
  assert.equal(voorkeurHtml({ id: "b", type: "boiler", controllable: true, entities: { switch: "switch.b" } }), "", "een boiler heeft geen laadmodus");
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
  assert.ok(kaart.includes('t("Dit loopt mee met wat de paal erin doet: sinds je {pct}% doorgaf is er {kwh} kWh geladen."'), "de zin met de kWh sinds de opgave");
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

// De eigenaar op 14-10-2026, met de integratie van de auto even uit Home Assistant: de
// coach vroeg om de accustand op de laadpaalkaart, "maar ik kan nergens de accustand
// doorgeven." Het veld stond er alleen bij een auto zonder sensor (v0.116.2).
proef("'hoe vol is de auto nu' staat er ook als de sensor van de auto niets zegt (v0.116.2)", async () => {
  const { vraagAccustand } = await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  const staten = {
    "sensor.auto_soc": { state: "unavailable" },
    "sensor.leeg": { state: "" },
    "sensor.onbekend": { state: "unknown" },
    "sensor.goed": { state: "68" },
    "sensor.nul": { state: "0" },
  };
  const feed = { get: (id) => staten[id] };
  const auto = (extra) => ({ id: "a", name: "Auto", capacity_kwh: 68, ...extra });
  assert.equal(vraagAccustand(auto({}), feed), true, "zonder sensor, zoals altijd");
  assert.equal(vraagAccustand(auto({ soc_entity: "sensor.auto_soc" }), feed), true, "de sensor is unavailable");
  assert.equal(vraagAccustand(auto({ soc_entity: "sensor.onbekend" }), feed), true, "de sensor is unknown");
  assert.equal(vraagAccustand(auto({ soc_entity: "sensor.leeg" }), feed), true, "de sensor is leeg");
  assert.equal(vraagAccustand(auto({ soc_entity: "sensor.weg" }), feed), true, "de sensor bestaat niet meer");
  assert.equal(vraagAccustand(auto({ soc_entity: "sensor.goed" }), feed), false, "de auto zegt het zelf");
  assert.equal(vraagAccustand(auto({ soc_entity: "sensor.nul" }), feed), false, "0% is ook een stand");
  assert.equal(vraagAccustand(auto({ soc_entity: "sensor.auto_soc", guest: true }), feed), false, "een gast niet");
  assert.equal(vraagAccustand(auto({ capacity_kwh: 0 }), feed), false, "zonder accu zegt een percentage niets");
  assert.equal(vraagAccustand(undefined, feed), false);
  const kaart = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf-8");
  assert.ok(kaart.includes("socPick.hidden = !(hangt && vraagAccustand(gekozen, this.feed_));"),
    "de kaart vraagt het met dezelfde grens");
  assert.ok(kaart.includes('"De auto geeft zijn accustand nu niet door. "'), "en zegt waarom");
});

proef("bij de batterij de grens voor de auto, op Voorkeuren de nachtstrategie (v0.90.0)", () => {
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.feed_ = {};
  const accu = { id: "b", type: "thuisbatterij", brand: "anker", name: "Anker", controllable: true, entities: {},
    battery: { ...defaultBattery("anker"), car_above: 40 } };
  const velden = nepVelden(voorkeurHtml(accu));
  vulVoorkeuren(velden, accu);
  assert.equal(velden.veld("data-vk-accu", "car_above").value, 40, "het veld met de grens, in Instellen (v0.114.0)");
  velden.veld("data-vk-accu", "car_above").value = "";
  assert.deepEqual(voorkeurWijziging(velden.veld("data-vk-accu", "car_above")), { battery: { car_above: null } }, "leeg is nooit");
  // Sinds 21-10-2026 een vinkje erboven: aan volgt de grens, uit wist hem, en aanzetten
  // zonder getal bewaart niets, want de coach verzint geen grens.
  const vinkAuto = velden.veld("data-vk-aan", "car_above");
  assert.equal(vinkAuto.checked, true, "met een grens staat het vinkje aan");
  vinkAuto.checked = false;
  assert.deepEqual(voorkeurWijziging(vinkAuto), { battery: { car_above: null } }, "uit is geen grens");
  vinkAuto.checked = true;
  assert.equal(voorkeurWijziging(vinkAuto), null, "aan zonder getal: niets op te slaan");
  const zonder = nepVelden(voorkeurHtml({ ...accu, battery: { ...accu.battery, car_above: null } }));
  vulVoorkeuren(zonder, { ...accu, battery: { ...accu.battery, car_above: null } });
  assert.equal(zonder.veld("data-vk-aan", "car_above").checked, false, "zonder grens uit");
  assert.equal(zonder.rijen.find((r) => r.sleutel === "car_above").hidden, true, "en de grens weg");
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/strategy.js", import.meta.url), "utf-8");
  assert.ok(bron.includes('id="night"') && bron.includes("night_strategy"), "de schakelaar op Voorkeuren");
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
  assert.ok(/id="steer-sort"[^>]*aria-label="\$\{t\("Volgorde aanpassen"\)\}"[^>]*>\$\{icons\.sliders\}<\/button>/.test(kaart),
    "hetzelfde icoon als Indeling aanpassen, zonder tekst");
  assert.ok(kaart.includes('${icons.sliders} ${t("Indeling aanpassen")}'), "dat is het icoon van de knop onderaan");
  assert.ok(!/startTabDrag_|startDrag_|setPointerCapture|\.grip|dragging/.test(kaart), "er wordt nergens meer gesleept");
  assert.ok(!/[Ss]leep de apparaten/.test(kaart) && kaart.includes('<span>${t("Schuif het gekozen apparaat:")}</span>'), "en de tekst belooft het ook niet meer");
  assert.ok(kaart.includes('data-move="-1" aria-label="${t("Omhoog")}"') && kaart.includes('data-move="1" aria-label="${t("Omlaag")}"'),
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
  assert.ok(kaart.includes('t("Deze beurt laadt tot {pct}%, volgens je planning'), "de zin op de kaart");
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
  // v0.114.1: een grens is voorrang, geen eindpunt (de eigenaar op 12-10-2026: "A").
  assert.equal(regelUitleg("thuisbatterij", 50), "eerst tot 50%, daarna wat er over is");
  assert.equal(regelUitleg("laadpaal", 40), "eerst tot de auto op 40% staat, daarna wat er over is");
  const bron8 = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/strategy.js", import.meta.url), "utf8");
  assert.ok(bron8.includes('grens.append("eerst tot ", veld, " %")'), "het veld zegt eerst tot");
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
  // Sinds v0.129.0 heeft gas zijn eigen eerdere contracten (`contract.gas.periods`).
  const contract = {
    type: "fixed",
    fixed: { all_in_price: 0.28, feed_in_tariff: 0.07, feed_in_costs: 0.01 },
    periods: [
      { from: "2025-01-01", to: "2025-12-31", all_in_price: 0.35, feed_in_tariff: 0.09 },
      { from: "2024-01-01", to: "2024-12-31", all_in_price: 0.4, feed_in_tariff: 0 },
    ],
    gas: { type: "fixed", price: 1.3, periods: [
      { from: "2025-01-01", to: "2025-12-31", price: 1.5 },
      { from: "2024-01-01", to: "2024-12-31", price: 0 },
    ] },
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
  const html = Object.create(Contract.prototype).render();
  assert.ok(html.includes('id="dyn-feedbonus"'));
  // De "kwart cent van na het salderen" (0,0025) staat er sinds v0.129.0 niet meer:
  // dat was geen bedrag met een bron, en de wet zegt vanaf 2027 minstens de helft
  // van de kale prijs. Wat een leverancier geeft vult de catalogus in.
  assert.ok(!html.includes("0,0025"));
});

proef("water hoort erbij: prijs per dag, meterstand, formulier en de lekmelding", async () => {
  const contract = { type: "fixed", fixed: { all_in_price: 0.28 },
    periods: [{ from: "2025-01-01", to: "2025-12-31", all_in_price: 0.35 }],
    gas: { type: "fixed", price: 1.3, periods: [{ from: "2025-01-01", to: "2025-12-31", price: 1.5 }] },
    water: { price: 1.1, periods: [{ from: "2025-01-01", to: "2025-12-31", price: 0.9 }] } };
  assert.equal(contractAt(contract, new Date(2025, 5, 1)).water, 0.9);
  assert.equal(contractAt(contract, new Date(2026, 5, 1)).water, 1.1);
  assert.equal(contractAt({ type: "fixed" }, new Date()).water, null);
  const { meterReadings } = await import("../custom_components/domotiapp_coach/frontend/src/data-source.js");
  const staten = { "sensor.water": { state: "50.563", attributes: { unit_of_measurement: "m³" } } };
  const feed = { get: (id) => staten[id] };
  assert.equal(meterReadings(feed, { meters: { water: "sensor.water", water_enabled: false } }).length, 0);
  assert.equal(meterReadings(feed, { meters: { water: "sensor.water", water_enabled: true } })[0].label, "Water");
  const prijzen = Object.create(Contract.prototype).render();
  assert.ok(prijzen.includes('id="water-price"'));
  // Instellingen is sinds v0.114.0 opgegaan in Installatie.
  const set = Object.create(Installatie.prototype).render();
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
  // Sinds v0.116.0 een uitklaplijst: Dag staat er als eerste in.
  assert.ok(html.indexOf('<option value="day">') > 0 && html.indexOf('<option value="day">') < html.indexOf('<option value="week">'));
});

proef("het contractscherm heeft de gasprijs en de eerdere contracten, per energiebron (v0.129.0)", () => {
  const html = Object.create(Contract.prototype).render();
  assert.ok(html.includes('id="gas-price"'));
  for (const bron of ["stroom", "gas", "water"]) {
    assert.ok(html.includes(`id="periods-${bron}"`) && html.includes(`data-period-add="${bron}"`), bron);
  }
  // Eerst alles over stroom, dan gas, dan water.
  assert.ok(html.indexOf('id="stroom"') < html.indexOf('id="gas"') && html.indexOf('id="gas"') < html.indexOf('id="water"'));
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

proef("de thuisbatterij staat weer in de lijst, met Anker, Growatt en Overig als merk", () => {
  assert.ok(TYPES.some((t) => t.id === "thuisbatterij"));
  assert.deepEqual(BATTERY_BRANDS.map((b) => b.id), ["anker", "growatt", "overig"]);
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

// Sinds v0.141.0 is het vak "tot 50 %" weg: "Nu vol laden" en "Nu leegladen" openen
// een pop-up met een schuif tussen de ondergrens en het plafond (de eigenaar op
// 19-10-2026), en zolang het loopt draait er een ring om de knop.
proef("vol en leeg laden van de batterij: de pop-up met de schuif (v0.141.0)", async () => {
  const { opSchuif } = await import("../custom_components/domotiapp_coach/frontend/src/accu-doel-sheet.js");
  assert.equal(opSchuif(52, 10, 95), 50);
  assert.equal(opSchuif(3, 10, 95), 10, "nooit onder de ondergrens");
  assert.equal(opSchuif(100, 10, 95), 95, "nooit boven het plafond");

  const Overzicht = geregistreerd.get("dac-view-overview");
  const geopend = [];
  const verstuurd = [];
  const el = Object.create(Overzicht.prototype);
  el.$ = (kiezer) => (kiezer === "#doel-sheet" ? { open: (k) => geopend.push(k) } : null);
  el.steerDevices_ = [{ id: "accu", name: "Batterij" }];
  el.lastDevices_ = [];
  el.labelFor_ = () => "Batterij";
  el.updateSteerable_ = () => {};
  el.coach_ = { accu: { kind: "batterij", floor: 10, ceiling: 95, soc: 40, boost: false, drain_to: null } };
  el.hass = { callWS: async (msg) => { if (msg.type !== "domotiapp_coach/coach/state") verstuurd.push(msg); return el.coach_; } };

  await el.toggleBoost_(0);
  assert.equal(verstuurd.length, 0, "eerst de pop-up, nog niets naar de coach");
  assert.deepEqual([geopend[0].soort, geopend[0].laag, geopend[0].hoog, geopend[0].actief], ["vol", 10, 95, false]);
  el.toggleDrain_(0);
  assert.equal(geopend[1].soort, "leeg");

  await el.kiesDoel_({ slot: 0, soort: "vol", pct: 80 });
  await el.kiesDoel_({ slot: 0, soort: "leeg", pct: 30 });
  await el.kiesDoel_({ slot: 0, soort: "leeg", pct: null });
  assert.deepEqual(verstuurd, [
    { type: "domotiapp_coach/coach/boost", device_id: "accu", boost: true, to_percent: 80 },
    { type: "domotiapp_coach/coach/drain", device_id: "accu", to_percent: 30 },
    { type: "domotiapp_coach/coach/drain", device_id: "accu", to_percent: null },
  ]);

  // Loopt het, dan staat de schuif op het doel van nu, met een knop om te stoppen.
  el.coach_.accu = { ...el.coach_.accu, boost: true, boost_to: 80 };
  await el.toggleBoost_(0);
  assert.deepEqual([geopend[2].waarde, geopend[2].actief], [80, true]);

  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf8");
  assert.ok(!bron.includes("data-drain-to"), "het vak naast Nu leegladen is weg");
  assert.match(bron, /button\.boost\.ring\[aria-pressed="true"\]::before/, "de ring om de knop");
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
    contract: { ...VAST, gas: { type: "fixed", price: 1.33 } },
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

// De eigenaar op 05-10-2026, bij "Opgeleverd € 0,74 in 8 dagen": "dat geld fluctueert
// telkens en klopt niet ... Komt ook niet overeen met de historie." Laden is nu
// inkopen: opgeleverd telt pas bij ontladen (v0.107.0, `Voorraad` in batterij.py).
proef("laden is inkopen: Historie telt opgeleverd, en wat er in de batterij bij kwam staat bij Uitgegeven", () => {
  const settings = { battery_state: [{
    device: "b",
    // 27-09 van voor v0.107.0: alleen het kasboek. 28-09: 's nachts € 1,00 van het
    // net erin, overdag eruit voor € 1,20, en € 0,40 ervan zit er 's avonds nog in.
    earned_days: { "2026-09-27": 0.5, "2026-09-28": -0.2 },
    realized_days: { "2026-09-27": 0.5, "2026-09-28": 0.2 },
  }] };
  const dag = geld.accuVerdiend(settings, new Date(2026, 8, 28), new Date(2026, 8, 29));
  assert.ok(Math.abs(dag.euro - 0.2) < 1e-9 && Math.abs(dag.voorraad - 0.4) < 1e-9 && dag.dagen === 1,
    `${dag.euro} ${dag.voorraad}`);
  const oud = geld.accuVerdiend(settings, new Date(2026, 8, 27), new Date(2026, 8, 28));
  assert.ok(Math.abs(oud.euro - 0.5) < 1e-9 && oud.voorraad === 0, "een dag van voor v0.107.0 telt zoals hij geteld is");

  // Zonder telt de stroom die er nog in zit niet als verbruik: zonder is wat het
  // gekost had zonder batterij, en die had die € 0,40 niet ingekocht.
  const rij = { start: new Date(2026, 8, 28, 12), own: 0, bought: 10, sold: 0 };
  const prijs = () => ({ koop: 0.3, terug: 0.1 });
  const met = geld.balans({ rijen: [rij], prijs, accu: dag.euro, accuVoorraad: dag.voorraad });
  const kasboek = geld.balans({ rijen: [rij], prijs, accu: -0.2 });
  assert.ok(Math.abs(met.uitgegeven - 3) < 1e-9 && Math.abs(met.delen.accu - 0.2) < 1e-9);
  assert.ok(Math.abs(met.zonder - kasboek.zonder) < 1e-9,
    `zonder hoort niet te veranderen door anders te boeken: ${met.zonder} tegen ${kasboek.zonder}`);
  assert.ok(Math.abs(met.voorraad - 0.4) < 1e-9);

  // De regel onder Uitgegeven, en in het rapport.
  const el = Object.create(Historie.prototype);
  assert.deepEqual(el.voorraadRegel_({ metAccu: true, voorraad: 0.4 }), { naam: "Waarvan nog in je batterij", tekst: "€ 0,40" });
  assert.deepEqual(el.voorraadRegel_({ metAccu: true, voorraad: -0.8 }), { naam: "En uit je batterij, eerder betaald", tekst: "€ 0,80" });
  assert.equal(el.voorraadRegel_({ metAccu: true, voorraad: 0.001 }), null);
});

// De eigenaar op 14-10-2026, bij "Wat erin zit: ingekocht voor € 2,02": "snap ik nog niet
// helemaal", en daarna: weghalen. Op de kaart alleen Opgeleverd; Historie houdt de voorraad.
proef("de kaart van de batterij zegt wat ze opleverde, en niet meer wat erin zit (v0.118.1)", () => {
  const rijen = (earned) => Object.fromEntries(batteryRows({ ...BESLUIT_BATTERIJ, earned }).map((r) => [r.label, r.text]));
  for (const voorraad of [0.55, -0.3, 2.02]) {
    const r = rijen({ euro: 1.4, days: 2, stock_euro: voorraad });
    assert.equal(r["Opgeleverd"], "€ 1,40 in 2 dagen");
    assert.equal(r["Wat erin zit"], undefined, `geen regel bij ${voorraad}`);
  }
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/battery.js", import.meta.url), "utf-8");
  assert.doesNotMatch(bron, /`ingekocht voor|label: "Wat erin zit"/, "alleen nog in de uitleg");
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

proef("Historie: Energie en Sessies, niet meer Beurten (v0.126.4)", () => {
  // De eigenaar op 16-10-2026: "maak daar Energie en Sessies van."
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/history.js", import.meta.url), "utf8");
  assert.ok(bron.includes('<option value="energie">Energie</option>'), "Energie in de keuzelijst");
  assert.ok(bron.includes('<option value="bespaard">Sessies</option>'), "Sessies in de keuzelijst, de waarde blijft bespaard");
  assert.ok(bron.includes('<div class="eyebrow">Sessies</div>'), "de kop van de kaart");
  // Alles tussen aanhalingstekens dat de bewoner leest: geen beurt meer. Het
  // commentaar eruit (daar citeert het de eigenaar), en de klasse van de tabel.
  const zonder = bron
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/^\s*\/\/.*$/gm, "")
    .replace(/table\.beurten|class="beurten"/g, "");
  const teksten = zonder.match(/"[^"\n]*"|`[^`]*`/g) ?? [];
  const fout = teksten.filter((t) => /\bbeurt(en)?\b/i.test(t));
  assert.deepEqual(fout, [], "nog beurt in een tekst van Historie");
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
  // Geladen en ontladen per vak, apart (v0.126.0).
  el.accu_ = new Map([
    ["b", [{ start: uur(d1, 10), kwh: 1, erin: 1.2, eruit: 0.2 }, { start: uur(d1, 22), kwh: -0.5, erin: 0, eruit: 0.5 }]],
    ["c", [{ start: uur(d1, 12), kwh: 0.3, erin: 0.3, eruit: 0 }, { start: uur(d2, 2), kwh: -0.3, erin: 0, eruit: 0.3 }]],
  ]);
  const apart = el.accuPerVak_(tijden, (i) => tijden[i + 1] ?? d3 + 86400000);
  assert.deepEqual(apart.map((v) => [v.erin, v.eruit].map((x) => Math.round(x * 1000) / 1000)), [[1.5, 0.7], [0, 0.3], [0, 0]]);
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
  // Geladen en ontladen apart (v0.126.0): tellers en losse sensoren meten het
  // zelf, een sensor met een teken alleen netto per uur.
  const apart = (id) => [r.get(id)[0].erin, r.get(id)[0].eruit].map((x) => Math.round(x * 1000) / 1000);
  assert.deepEqual(apart("meter"), [1.2, 0.2]);
  assert.deepEqual(apart("twee"), [0.8, 0.1]);
  assert.deepEqual(apart("teken"), [0, 0.5]);
  // Over een jaar per dag; de dag van vandaag telt alleen de uren die voorbij zijn.
  const vandaag = new Date();
  vandaag.setHours(0, 0, 0, 0);
  const jaarVragen = [];
  const jaar = {
    callWS: async (v) => {
      jaarVragen.push(v);
      return { "sensor.laad": [{ start: vandaag.getTime(), mean: 1000 }], "sensor.teken": [{ start: vandaag.getTime(), mean: 1000 }] };
    },
  };
  const j = await fetchBattery(
    jaar,
    [{ id: "t", entities: { charge_power: "sensor.laad" } }, { id: "s", entity: "sensor.teken", entities: {} }],
    "year",
    new Date(vandaag.getFullYear(), 0, 1)
  );
  const verstreken = Math.floor((Date.now() - vandaag.getTime()) / 3600000);
  assert.ok(Math.abs(j.get("t")[0].kwh - verstreken) < 1e-9, `${j.get("t")[0].kwh} tegen ${verstreken}`);
  assert.ok(Math.abs(j.get("t")[0].erin - verstreken) < 1e-9);
  // Een sensor met een teken ook over een jaar per uur: per dag valt middag
  // laden en avond ontladen tegen elkaar weg.
  const vraagTeken = jaarVragen.find((v) => v.statistic_ids.includes("sensor.teken"));
  assert.equal(vraagTeken.period, "hour");
  assert.ok(!vraagTeken.statistic_ids.includes("sensor.laad"));
  assert.equal(jaarVragen.find((v) => v.statistic_ids.includes("sensor.laad")).period, "day");
  assert.ok(Math.abs(j.get("s")[0].kwh - 1) < 1e-9, "een uur van 1000 W");
});

proef("fetchBattery: de eigen tellers van de batterij voor de vermogenssensoren, een kWh-meter daarvoor (v0.126.1)", async () => {
  const { fetchBattery } = await import("../custom_components/domotiapp_coach/frontend/src/statistics.js");
  const uur = new Date(2026, 9, 14, 12).getTime();
  // Wat Home Assistant van elke sensor heeft; een sensor die er niet in staat
  // heeft geen statistiek.
  const bekend = {
    "sensor.m_in": 1.0, "sensor.m_uit": 0.1,
    "sensor.a_in": 1.25, "sensor.a_uit": 0.5,
    "sensor.laad": 1340, "sensor.ontlaad": 570,
    "sensor.half_in": 0.9,
  };
  const hass = {
    callWS: async (v) => {
      const uit = {};
      for (const id of v.statistic_ids) {
        if (!(id in bekend)) continue;
        uit[id] = [v.types[0] === "change" ? { start: uur, change: bekend[id] } : { start: uur, mean: bekend[id] }];
      }
      return uit;
    },
  };
  const vermogen = { charge_power: "sensor.laad", discharge_power: "sensor.ontlaad" };
  const accus = [
    { id: "meter", entities: { energy_in: "sensor.m_in", energy_out: "sensor.m_uit", accu_in: "sensor.a_in", accu_out: "sensor.a_uit", ...vermogen } },
    { id: "accu", entities: { accu_in: "sensor.a_in", accu_out: "sensor.a_uit", ...vermogen } },
    { id: "geen-statistiek", entities: { accu_in: "sensor.weg_in", accu_out: "sensor.weg_uit", ...vermogen } },
    { id: "half", entities: { accu_in: "sensor.half_in", accu_out: "sensor.weg_uit", ...vermogen } },
    { id: "alleen-vermogen", entities: vermogen },
  ];
  const r = await fetchBattery(hass, accus, "day", new Date(2026, 9, 14));
  const apart = (id) => [r.get(id)[0].erin, r.get(id)[0].eruit].map((x) => Math.round(x * 1000) / 1000);
  assert.deepEqual(apart("meter"), [1.0, 0.1], "de kWh-meter gaat voor alles");
  assert.deepEqual(apart("accu"), [1.25, 0.5], "de tellers van de batterij voor het vermogen");
  assert.deepEqual(apart("geen-statistiek"), [1.34, 0.57], "tellers zonder statistiek: terug naar het vermogen");
  assert.deepEqual(apart("half"), [1.34, 0.57], "één teller is geen paar");
  assert.deepEqual(apart("alleen-vermogen"), [1.34, 0.57]);
  assert.ok(Math.abs(r.get("accu")[0].kwh - 0.75) < 1e-9, "netto is erin min eruit, uit dezelfde bron");
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
  const allIn = { type: "dynamic", dynamic: { source: "all_in", fallback_entity: "sensor.reserve", fallback_source: "all_in", energy_tax: 0.1088, supplier_markup: 0.02, vat_percent: 21 } };
  const a = prijsbron.allInPrijzen(new Map([[1, 0.3]]), new Map([[1, 0.9], [2, 0.25]]), allIn);
  assert.equal(a.get(1), 0.3, "de eigen sensor gaat voor");
  assert.equal(a.get(2), 0.25, "een all-in reserve blijft zoals hij is");
  // v0.129.0: zonder reservesensor is de kale marktprijs de reserve, en die krijgt
  // belasting, opslag en btw.
  const kaal = { type: "dynamic", dynamic: { source: "all_in", market_entity: "sensor.np", energy_tax: 0.09161, supplier_markup: 0.016529, vat_percent: 21 } };
  const k = prijsbron.allInPrijzen(new Map([[1, 0.3]]), new Map([[2, 0.2]]), kaal);
  assert.ok(Math.abs(k.get(2) - (0.2 + 0.09161 + 0.016529) * 1.21) < 1e-9, `${k.get(2)}`);
});

// Sinds v0.129.0 is de kale marktprijs vanzelf de reserve; de reservesensor blijft
// voor een tweede all-in prijs, en staat er alleen als hij is ingevuld.
proef("het formulier heeft een reserveprijssensor, als tweede all-in prijs", () => {
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/contract.js", import.meta.url), "utf8");
  assert.ok(bron.includes('id="dyn-reserve"') && bron.includes('["dyn-reserve", "fallback_entity"]'));
  assert.ok(bron.includes('d.fallback_source = "all_in"'));
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

// De eigenaar op 10-10-2026: "ik heb nu ook een batterijtemperatuur van de anker, ik wil
// dat ik die kan invullen en dat je die toont op de batterijkaart." Een optioneel veld
// voor elk merk, op de kaart direct onder de accustand, met één cijfer achter de komma.
proef("de temperatuur van de thuisbatterij is in te vullen en staat onder de accustand (v0.108.0)", () => {
  for (const brand of ["anker", "overig"]) {
    const veld = veldenVan({ type: "thuisbatterij", brand }).find((f) => f.key === "temperature");
    assert.ok(veld, `${brand} heeft een veld voor de temperatuur`);
    assert.ok(!veld.needed && !veld.hideRow, "optioneel, en wel op de kaart");
  }
  const staten = {
    "sensor.batterij_soc": { state: "39", attributes: { unit_of_measurement: "%" } },
    "sensor.batterij_temp": { state: "28.0", attributes: { unit_of_measurement: "°C", device_class: "temperature" } },
    "select.batterij_modus": { state: "third_party_control", attributes: { options: [] } },
  };
  const feed = { get: (id) => staten[id] };
  const accu = { id: "b", type: "thuisbatterij", brand: "anker", entity: "",
    entities: { soc: "sensor.batterij_soc", temperature: "sensor.batterij_temp", mode: "select.batterij_modus" } };
  const labels = (r) => r.devices[0].details.map((d) => d.label);
  const r = new LiveSource().sample(feed, { sources: {}, devices: [accu] });
  assert.deepEqual(labels(r).slice(0, 3), ["Accustand", "Temperatuur", "Bedrijfsmodus"], JSON.stringify(labels(r)));
  assert.equal(r.devices[0].details[1].text, "28 °C");
  staten["sensor.batterij_temp"].state = "27.46";
  assert.equal(new LiveSource().sample(feed, { sources: {}, devices: [accu] }).devices[0].details[1].text, "27,5 °C");
  staten["sensor.batterij_temp"].state = "unavailable";
  assert.equal(new LiveSource().sample(feed, { sources: {}, devices: [accu] }).devices[0].details[1].text, "—");
  const zonder = { ...accu, entities: { soc: "sensor.batterij_soc" } };
  assert.ok(!labels(new LiveSource().sample(feed, { sources: {}, devices: [zonder] })).includes("Temperatuur"),
    "niet ingevuld, geen regel");
});

// De eigenaar op 10-10-2026: "ik wil de mogelijkheid om een smart plug in te schakelen om
// een ventilator aan te sturen als de batterij te heet wordt." De plug is een veld van de
// batterij, de grens staat onder Wat jij wilt, en de kaart zegt of hij aan staat.
proef("de ventilator van de thuisbatterij: een veld, een grens die leeg begint, en aan of uit op de kaart", () => {
  const veld = veldenVan({ type: "thuisbatterij", brand: "anker" }).find((f) => f.key === "fan");
  assert.ok(veld && !veld.needed && !veld.hideRow, "optioneel, en op de kaart");
  assert.equal(defaultBattery("anker").fan_above_c, null, "geen grens die niemand koos");
  const staten = {
    "sensor.batterij_soc": { state: "39", attributes: { unit_of_measurement: "%" } },
    "sensor.batterij_temp": { state: "36.4", attributes: { unit_of_measurement: "°C" } },
    "switch.ventilator": { state: "on", attributes: {} },
  };
  const feed = { get: (id) => staten[id] };
  const accu = { id: "b", type: "thuisbatterij", brand: "overig", entity: "",
    entities: { soc: "sensor.batterij_soc", temperature: "sensor.batterij_temp", fan: "switch.ventilator" } };
  const rijen = new LiveSource().sample(feed, { sources: {}, devices: [accu] }).devices[0].details;
  assert.deepEqual(rijen.slice(0, 3).map((r) => `${r.label}: ${r.text}`),
    ["Accustand: 39 %", "Temperatuur: 36,4 °C", "Ventilator: Aan"], JSON.stringify(rijen));
});

// De eigenaar op 14-10-2026, over "Rendement: nog niet bekend" zonder kWh-meter op de batterij:
// "ja alleen op de kaart". De eigen tellers van de batterij als benadering, met dat erbij.
proef("het rendement op de batterijkaart: kWh-meter, zelf geleerd, uit de accu, opgegeven, of nog niet bekend (v0.145.0)", () => {
  const velden = veldenVan({ type: "thuisbatterij", brand: "anker" });
  for (const key of ["accu_in", "accu_out"]) {
    const veld = velden.find((f) => f.key === key);
    assert.ok(veld && !veld.needed && veld.hideRow, `${key}: optioneel, en zelf geen regel op de kaart`);
  }
  const staten = { "sensor.batterij_soc": { state: "39", attributes: { unit_of_measurement: "%" } } };
  const feed = { get: (id) => staten[id] };
  const regel = (battery, rij, meter = false) => new LiveSource().sample(feed, {
    sources: {},
    devices: [{ id: "b", type: "thuisbatterij", brand: "overig", entity: "", battery,
      entities: { soc: "sensor.batterij_soc", ...(meter ? { energy_in: "sensor.in", energy_out: "sensor.uit" } : {}) } }],
    battery_state: [{ device: "b", ...rij }],
  }).devices[0].details.find((d) => d.label === "Rendement")?.text;
  // Dezelfde volgorde als `_rendement_bron` in coach.py (v0.145.0).
  const geleerd = { rte: 0.85, in: [[2, 0.92]], out: [[2, 0.92]] };
  assert.equal(regel({}, { rte_accu: 0.8792 }), "ongeveer 88%, gemeten in de accu");
  assert.equal(regel({ rte_percent: 80 }, { rte_accu: 0.8792 }), "ongeveer 88%, gemeten in de accu", "een meting gaat voor de opgave");
  assert.equal(regel({ rte_percent: 80 }, {}), "80% opgegeven");
  assert.equal(regel({}, { rte_power: geleerd, rte_accu: 0.8792 }), "85% zelf geleerd", "het zelf geleerde gaat voor de eigen tellers");
  assert.equal(regel({}, { rte: 0.76, rte_power: geleerd }, true), "76% gemeten met de kWh-meter", "een kWh-meter gaat voor alles");
  assert.equal(regel({}, { rte: 0.736, rte_accu: 0.8792 }), "ongeveer 88%, gemeten in de accu", "een oude meting zonder meter telt niet");
  assert.equal(regel({}, {}), "nog niet bekend");
});

// De eigenaar op 14-10-2026 over de airco: "De klant stelt gewoon op de kaart in welke temperatuur
// het moet zijn", en na v0.119.0: "goedkoop uur mag de bewoner zelf kiezen dus 3 opties of op zon of
// goedkope uren of beide" en "Bij apparaten toevoegen alleen nog de optie Mitsubishi Electric kunnen
// kiezen." Het typeplaatje is van de installateur.
proef("de airco: alleen Mitsubishi Electric, een climate, een vermogen, en de keuze van de bewoner (v0.119.1)", () => {
  assert.deepEqual(brandsFor("airco").map((b) => b.id), ["mitsubishi_electric"], "één merk");
  const zonder = { type: "airco", controllable: true, entities: {} };
  assert.equal(canSteer(zonder), false, "zonder merk niet");
  assert.deepEqual(brandFields(zonder), [], "zonder merk nog geen velden");
  const leeg = { ...zonder, brand: "mitsubishi_electric" };
  assert.equal(canSteer(leeg), true);
  assert.deepEqual(brandFields(leeg).map((f) => f.key), ["climate", "temperature"]);
  assert.deepEqual(missingForControl(leeg), ["Airco", "Vermogenssensor of typeplaatje"]);
  assert.deepEqual(missingForControl({ ...leeg, entities: { climate: "climate.kamer" }, airco: { power_w: 1200 } }), []);
  assert.deepEqual(missingForControl({ ...leeg, entities: { climate: "climate.kamer" }, entity: "sensor.airco_w" }), []);
  assert.equal(canHaveDeadline({ ...leeg, entities: { climate: "climate.kamer" } }), false, "geen klaar-tijd");

  const device = { id: "a", type: "airco", brand: "mitsubishi_electric",
    airco: { power_w: 1200, target_c: 22.5, run_on: "beide", paused: false } };
  assert.equal(heeftVoorkeuren(device), true);
  const html = voorkeurHtml(device);
  assert.ok(!/power_w|typeplaatje/i.test(html), "het typeplaatje staat niet bij de bewoner");
  assert.ok(!/solar_only/.test(html), "geen vinkje alleen op zon meer");
  assert.match(html, /value="zon"[^>]*>Zon/);
  assert.match(html, /value="goedkoop"/);
  assert.match(html, /value="beide"/);
  const velden = nepVelden(html);
  vulVoorkeuren(velden, device);
  assert.equal(velden.veld("data-vk-airco", "target_c").value, 22.5);
  assert.equal(velden.veld("data-vk-airco", "run_on").value, "beide");
  assert.equal(velden.veld("data-vk-airco", "paused").checked, false);
  const nieuw = nepVelden(html);
  vulVoorkeuren(nieuw, { ...device, airco: {} });
  assert.equal(nieuw.veld("data-vk-airco", "run_on").value, "zon", "standaard zon");
  const doel = velden.veld("data-vk-airco", "target_c");
  assert.deepEqual(voorkeurWijziging({ ...doel, value: "21.3" }), { airco: { target_c: 21.5 } }, "op een halve graad");
  assert.deepEqual(voorkeurWijziging({ ...doel, value: "" }), { airco: { target_c: null } }, "leeg is wat er op de airco staat");
  const keuze = velden.veld("data-vk-airco", "run_on");
  assert.deepEqual(voorkeurWijziging({ ...keuze, value: "goedkoop" }), { airco: { run_on: "goedkoop" } });
});

// De eigenaar op 14-10-2026, bij de batterijkaart met "ontlaadt", "ongeveer 89%, gemeten in de accu"
// en "de batterij zelf, met zijn eigen meter; de coach kijkt mee": "even alles met een hoofdletter beginnen."
proef("een waarde op een apparaatkaart begint met een hoofdletter (v0.119.2)", async () => {
  const { metHoofdletter } = await import("../custom_components/domotiapp_coach/frontend/src/format.js");
  assert.equal(metHoofdletter("ontlaadt"), "Ontlaadt");
  assert.equal(metHoofdletter("ongeveer 89%, gemeten in de accu"), "Ongeveer 89%, gemeten in de accu");
  assert.equal(metHoofdletter("de batterij zelf, met zijn eigen meter; de coach kijkt mee"),
    "De batterij zelf, met zijn eigen meter; de coach kijkt mee");
  assert.equal(metHoofdletter("Eigen verbruik"), "Eigen verbruik");
  assert.equal(metHoofdletter("58 % · 8,2 van 14,2 kWh"), "58 % · 8,2 van 14,2 kWh");
  assert.equal(metHoofdletter("€ 4,26 in 17 dagen"), "€ 4,26 in 17 dagen");
  assert.equal(metHoofdletter("—"), "—");
  assert.equal(metHoofdletter(""), "");
  assert.equal(metHoofdletter(undefined), "");
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf-8");
  assert.match(bron, /value\.textContent = metHoofdletter\(row\.text\)/, "de kaart zet hem ervoor");
});

// De eigenaar op 15-10-2026, bij de pop-up van de batterij in de energiestroom met "laadt" en
// "ongeveer 93%, gemeten in de accu": "hier ook hoofdletters toepassen."
proef("de pop-up in de energiestroom begint elke waarde met een hoofdletter (v0.119.3)", async () => {
  await import("../custom_components/domotiapp_coach/frontend/src/components/energy-flow.js");
  const Stroom = geregistreerd.get("dac-energy-flow");
  const knoop = () => {
    const kinderen = [];
    return {
      className: "", textContent: "", hidden: true, kinderen,
      append(...items) { kinderen.push(...items); },
      replaceChildren(...items) { kinderen.length = 0; kinderen.push(...items); },
    };
  };
  const knopen = new Map(["#detail", "#detail-title", "#detail-list"].map((k) => [k, knoop()]));
  const el = Object.create(Stroom.prototype);
  el.$ = (kiezer) => knopen.get(kiezer);
  el.slots_ = [{
    id: "a", type: "thuisbatterij", name: "Batterij", watts: 2940,
    details: [
      { label: "Doet nu", text: "laadt" },
      { label: "Accustand", text: "28 % · 4,1 van 14,5 kWh" },
      { label: "Bedrijfsmodus", text: "Eigen verbruik" },
      { label: "Rendement", text: "ongeveer 93%, gemeten in de accu" },
    ],
  }];
  const echt = globalThis.document.createElement;
  globalThis.document.createElement = knoop;
  try {
    el.openDetail_("dev1");
  } finally {
    globalThis.document.createElement = echt;
  }
  const rijen = knopen.get("#detail-list").kinderen.map((li) => li.kinderen.map((s) => s.textContent));
  assert.deepEqual(rijen, [
    ["Vermogen", "2,94 kW"],
    ["Doet nu", "Laadt"],
    ["Accustand", "28 % · 4,1 van 14,5 kWh"],
    ["Bedrijfsmodus", "Eigen verbruik"],
    ["Rendement", "Ongeveer 93%, gemeten in de accu"],
  ]);
  assert.equal(knopen.get("#detail").hidden, false, "de pop-up gaat open");
});

// Gemeten op 10-10-2026 in Chrome: "Hoogste accustand in vakantiestand" stond in beeld met
// de vakantiestand uit. De rij had hidden, maar display: grid van .row won.
proef("de rijen onder een vinkje van de batterij verdwijnen echt als het vinkje uit staat", () => {
  // Sinds v0.114.0 in Instellen: daar zet `vulVoorkeuren` het attribuut hidden,
  // en de pop-up heeft de regel die het laat winnen van elke display.
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/schedule-sheet.js", import.meta.url), "utf-8");
  assert.match(bron, /\[hidden\] \{ display: none !important; \}/);
  const velden = nepVelden(voorkeurHtml({ id: "b", type: "thuisbatterij", battery: {} }));
  vulVoorkeuren(velden, { id: "b", type: "thuisbatterij", battery: {} });
  assert.deepEqual(velden.rijen.filter((r) => r.hidden).map((r) => r.sleutel).sort(),
    // En de melding bij Handelen zonder terugleverprijs (v0.128.2), die hier geen contract heeft,
    // en de grens bij ontladen naar het net, dat standaard uit staat (v0.141.0). En de grens
    // voor de auto, die sinds 21-10-2026 onder een eigen vinkje staat.
    ["car_above", "holiday_max_percent", "reserve_percent", "trade_above", "trade_kan_niet", "weekly_full_day"], "reserve, de dag en de vakantiestand");
  // Laden van het net staat standaard aan, dus de grens daarbij staat er.
  assert.ok(!velden.rijen.find((r) => r.sleutel === "grid_charge_below").hidden, "de grens bij laden van het net");
  const uit = nepVelden(voorkeurHtml({ id: "b", type: "thuisbatterij", battery: { grid_charge: false, trade: true } }));
  vulVoorkeuren(uit, { id: "b", type: "thuisbatterij", battery: { grid_charge: false, trade: true } });
  assert.ok(uit.rijen.find((r) => r.sleutel === "grid_charge_below").hidden, "laden van het net uit: geen grens");
  assert.ok(!uit.rijen.find((r) => r.sleutel === "trade_above").hidden, "handelen aan: de grens");
  // Leeg is "de coach bepaalt", en een getal gaat in euro per kWh mee.
  const veld = (sleutel, value) => ({ dataset: { vkAccu: sleutel }, type: "number", value });
  assert.deepEqual(voorkeurWijziging(veld("grid_charge_below", "")), { battery: { grid_charge_below: null } });
  assert.deepEqual(voorkeurWijziging(veld("trade_above", "0.35")), { battery: { trade_above: 0.35 } });
});

proef("de keuzelijst zet temperatuursensoren bovenaan bij de temperatuur van de batterij", () => {
  const Kiezer = geregistreerd.get("dac-entity-picker");
  const kiezer = Object.create(Kiezer.prototype);
  kiezer.hass_ = { states: {
    "sensor.accu_temperatuur": { attributes: { device_class: "temperature", unit_of_measurement: "°C" } },
    "sensor.zolder": { attributes: { unit_of_measurement: "°F" } },
    "sensor.accu_soc": { attributes: { device_class: "battery", unit_of_measurement: "%" } },
  } };
  kiezer.filter = "temperature";
  assert.equal(kiezer.filter_, "temperature", "een filter dat de kiezer kent, anders wordt het stil 'all'");
  const { preferred, other } = kiezer.candidates_("");
  assert.deepEqual(preferred, ["sensor.accu_temperatuur", "sensor.zolder"]);
  assert.deepEqual(other, ["sensor.accu_soc"], "de rest blijft te kiezen");
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
  // Tot v0.116.2 een regel met een streepje; nu vraagt de kaart de stand zelf.
  assert.deepEqual(regels({ active_cars: [{ device: "p", car: "tesla" }] }), [],
    "een gekozen auto waarvan de sensor niets zegt: geen streepje, de kaart vraagt het");
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
  assert.match(zin, /Tot 1 januari 2027 saldeer je/);
  assert.match(zin, /Thuisbatterij: wat ontladen opbracht, min wat het laden kostte/);
  assert.match(zin, /Coach: /);
  // De eigenaar op 13-10-2026: "zo duidelijk mogelijk en zo kort mogelijk". Met
  // salderen staat erbij wat opslaan per kWh scheelt: de stroomprijs min wat
  // terugleveren opbrengt.
  assert.match(zin, /scheelt maar € \d+,\d\d per kWh/);
  for (const z of zin.split(/(?<=\.) /)) assert.ok(z.length <= 150, `te lange zin: ${z}`);
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

// De eigenaar op 08-10-2026, met een schermafdruk van "Laden tot" in het schema van
// de laadpaal: "algemeen staat niet helemaal lekker in het veld." Op 96 px stond er
// "algemee". Gemeten in Chrome: het woord is 61 px op 14 px letters en 69 px op 16
// (een telefoon), de pijltjes van een getalveld ongeveer 15, opvulling 2 × 12, rand 2.
proef("in het veld Laden tot past het woord algemeen helemaal", () => {
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/schedule-sheet.js", import.meta.url), "utf-8");
  const regel = bron.match(/\.time-field input\.doel \{[^}]*?\bwidth: (\d+)px/);
  assert.ok(regel, "de breedte van het veld staat in de stijl");
  const ruimte = Number(regel[1]) - 24 - 2 - 15;
  assert.ok(ruimte >= 69, `er is ${ruimte} px voor een woord van 69 px`);
  assert.equal((bron.match(/placeholder="algemeen"/g) ?? []).length, 2, "allebei de velden, elke dag en per dag");
});

// --- draaien ----------------------------------------------------------------

// De klantwoning: sinds 08-10-2026 23 keer "Refusing to allow ... to subscribe to event
// domotiapp_coach_settings_updated" in het log, en het overzicht van een bewoner zonder
// beheerdersrechten werkte na het openen niet meer bij. Sinds v0.108.1 via het eigen
// commando van de coach, dat iedereen mag gebruiken.
proef("het paneel volgt de coach via domotiapp_coach/subscribe, ook zonder beheerder", async () => {
  const { volgCoach } = await import("../custom_components/domotiapp_coach/frontend/src/data-source.js");
  const gevraagd = [];
  let terugroep = null;
  const hass = {
    connection: {
      async subscribeMessage(cb, bericht) {
        gevraagd.push(bericht);
        terugroep = cb;
        return () => {};
      },
      async subscribeEvents() {
        throw new Error("niet voor een gewone gebruiker");
      },
    },
  };
  const ontvangen = [];
  await volgCoach(hass, "decision", (data) => ontvangen.push(data));
  assert.deepEqual(gevraagd, [{ type: "domotiapp_coach/subscribe", event: "decision" }]);
  terugroep({ device: "dev-1", amps: 16 });
  assert.deepEqual(ontvangen, [{ device: "dev-1", amps: 16 }], "wat het event meedraagt komt er kaal uit");
  // Zonder het commando, zoals in de preview: de events zelf, met dezelfde vorm.
  const events = [];
  const preview = {
    connection: {
      async subscribeEvents(cb, soort) {
        events.push(soort);
        cb({ data: { message: "hallo" } });
        return () => {};
      },
    },
  };
  const meldingen = [];
  await volgCoach(preview, "notification", (data) => meldingen.push(data));
  assert.deepEqual(events, ["domotiapp_coach_notification"]);
  assert.deepEqual(meldingen, [{ message: "hallo" }]);
  assert.equal(await volgCoach({}, "settings", () => {}), null, "zonder verbinding niets");
  // En geen enkel deel van het paneel abonneert zich nog rechtstreeks op een event van de coach.
  const fs = await import("node:fs");
  const path = await import("node:path");
  const wortel = new URL("../custom_components/domotiapp_coach/frontend/", import.meta.url);
  const bestanden = [];
  const loop = (map) => {
    for (const naam of fs.readdirSync(map, { withFileTypes: true })) {
      const vol = path.join(map, naam.name);
      if (naam.isDirectory()) loop(vol);
      else if (naam.name.endsWith(".js")) bestanden.push(vol);
    }
  };
  loop(new URL(wortel).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
  // state_changed mag iedereen volgen (state-feed.js); de terugval staat in data-source.js.
  const direct = bestanden
    .filter((f) => fs.readFileSync(f, "utf8").includes("subscribeEvents("))
    .map((f) => path.basename(f))
    .filter((naam) => !["state-feed.js", "data-source.js"].includes(naam));
  assert.deepEqual(direct, [], "alles van de coach loopt via volgCoach");
});

proef("licht en donker: geen scherm draagt nog een kleur van alleen het donkere thema (v0.113.0)", async () => {
  // De eigenaar op 11-10-2026: "alles moet ook goed licht zijn. Ook de coach." Elke
  // kleur die bij het thema hoort komt uit theme.js; een tint over de achtergrond is
  // rgba(var(--dac-veil), ...), wit in het donker en zwart in het licht.
  const fs = await import("node:fs");
  const path = await import("node:path");
  const wortel = new URL("../custom_components/domotiapp_coach/frontend/", import.meta.url);
  const bestanden = [];
  const loop = (map) => {
    for (const naam of fs.readdirSync(map, { withFileTypes: true })) {
      const vol = path.join(map, naam.name);
      if (naam.isDirectory()) loop(vol);
      else if (naam.name.endsWith(".js")) bestanden.push(vol);
    }
  };
  loop(new URL(wortel).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
  // Het rapport en de pdf zijn papier: altijd wit, dus eigen kleuren.
  const donker = /rgba\(\s*(255\s*,\s*255\s*,\s*255|232\s*,\s*228\s*,\s*222|12\s*,\s*12\s*,\s*10|18\s*,\s*18\s*,\s*15)\s*,|#12120f|#161613|#171714|#0c0c0a|#e8e4de|color-scheme:\s*dark/i;
  const fout = bestanden
    .filter((f) => !["theme.js", "report.js", "pdf.js"].includes(path.basename(f)))
    .flatMap((f) => fs.readFileSync(f, "utf8").split(/\r?\n/).map((regel, i) => [path.basename(f), i + 1, regel]))
    .filter(([, , regel]) => donker.test(regel))
    .map(([f, i, regel]) => `${f}:${i} ${regel.trim().slice(0, 60)}`);
  assert.deepEqual(fout, [], "kleuren van het thema horen in theme.js");
  // En het lichte thema zet elke tint die de schermen gebruiken.
  const thema = await import("../custom_components/domotiapp_coach/frontend/src/theme.js");
  for (const token of ["--dac-veil", "--dac-ink-rgb", "--dac-bg-rgb", "--dac-raise-rgb", "--dac-popover", "--dac-knob",
                       "--dac-shadow-deep", "--dac-scheme", "--dac-bg", "--dac-surface", "--dac-ink", "--dac-ink-2", "--dac-ink-3"]) {
    assert.ok(thema.tokens.includes(`${token}:`), `${token} in het donker`);
    assert.ok(thema.lightTokens.includes(`${token}:`), `${token} in het licht`);
  }
  // Het thema volgt Home Assistant: elk element krijgt het attribuut light, ook als het later komt.
  const a = { attrs: new Set(), toggleAttribute(n, aan) { aan ? this.attrs.add(n) : this.attrs.delete(n); } };
  const b = { attrs: new Set(), toggleAttribute(n, aan) { aan ? this.attrs.add(n) : this.attrs.delete(n); } };
  thema.followTheme(a, true);
  thema.setLight(true);
  thema.followTheme(b, true);
  assert.ok(a.attrs.has("light") && b.attrs.has("light"), "licht op elk element");
  thema.setLight(false);
  assert.ok(!a.attrs.has("light") && !b.attrs.has("light"), "en weer donker");
  thema.followTheme(a, false);
  thema.followTheme(b, false);
});

let goed = 0;
let fout = 0;
// --- de indeling bewoner en installateur (v0.114.0) ----------------------------
//
// De eigenaar op 08-10-2026: "voorop staat dat de klant geen entiteiten moet kunnen
// kiezen", en op 12-10-2026 zijn antwoorden: Instellen achter de kaart met het
// schema erin, de strategie van de bewoner, de personen bij Meldingen ook.
// Contract ziet de bewoner sinds v0.130.1 ook, om te lezen en zijn prijs te bevestigen.
proef("de bewoner ziet Overzicht, Historie, Meldingen, Voorkeuren en Contract; de installateur ook Apparaten en Installatie", async () => {
  const { navItemsFor, NAV_ITEMS } = await import("../custom_components/domotiapp_coach/frontend/src/header.js");
  assert.deepEqual(navItemsFor(false).map((i) => i.label), ["Overzicht", "Historie", "Meldingen", "Voorkeuren", "Contract"]);
  assert.deepEqual(navItemsFor(true).map((i) => i.label),
    ["Overzicht", "Historie", "Meldingen", "Voorkeuren", "Apparaten", "Installatie", "Contract"]);
  assert.ok(!NAV_ITEMS.some((i) => i.id === "instellingen"), "Instellingen is opgegaan in Installatie");
  assert.equal(NAV_ITEMS.find((i) => i.label === "Voorkeuren").id, "strategie", "het oude pad blijft werken");
  const paneel = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/domotiapp-coach-panel.js", import.meta.url), "utf8");
  assert.ok(paneel.includes('contract: "dac-view-contract"') && !paneel.includes("settings.js"), "elk tabje heeft zijn scherm");
});

proef("Installatie heeft de sensoren van Instellingen, maar niet de kleuren en niet de fasenkaart", () => {
  const html = Object.create(Installatie.prototype).render();
  for (const stuk of ['id="home-path"', 'id="grid-mode"', 'data-forecast="this_hour"', 'id="phases-enabled"',
                      'data-meter="import_low"', 'id="solar-extra-add"', 'id="kast-add"']) {
    assert.ok(html.includes(stuk), stuk);
  }
  assert.ok(!html.includes('id="self-low"') && !html.includes('id="phases-overview"'), "die staan onder Voorkeuren");
  assert.ok(!html.includes('id="contract-type"'), "het contract staat op een eigen scherm");
  assert.deepEqual(Installatie.sections, ["installation", "navigation", "sources"]);
  assert.deepEqual(Contract.sections, ["contract"]);
  // Opslaan stuurt de fasenkaart niet mee: die zet de bewoner onder Voorkeuren,
  // en een oude kopie hier mag hem niet terugzetten.
  const el = Object.create(Installatie.prototype);
  const uit = el.payload_({ installation: { circuits: [] }, navigation: {}, sources: { phases_on_overview: true, solar: "sensor.zon" } });
  assert.equal("phases_on_overview" in uit.sources, false);
  assert.equal(uit.sources.solar, "sensor.zon");
  // De sensoren van de hoofdaansluiting en die van een groep zitten elkaar niet in de weg.
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/installation.js", import.meta.url), "utf8");
  assert.ok(bron.includes('#phase-fields dac-entity-picker[data-phase]'), "de fasen van de hoofdaansluiting apart van die van een groep");
});

proef("Voorkeuren heeft het overzicht erbij, en slaat dat meteen op via display/set", async () => {
  await import("../custom_components/domotiapp_coach/frontend/src/views/strategy.js");
  const Voorkeuren = geregistreerd.get("dac-view-strategy");
  const html = Object.create(Voorkeuren.prototype).render();
  assert.ok(html.includes(">Voorkeuren<"), "de kop heet Voorkeuren");
  assert.ok(html.includes('data-drempel="self_use.low"') && html.includes('data-drempel="price.high"'));
  assert.ok(html.includes('id="phases-overview"'));
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/strategy.js", import.meta.url), "utf8");
  assert.ok(bron.includes('"domotiapp_coach/display/set"'));
  // De schema's horen niet bij dit scherm: niet in wat er opgeslagen wordt, en
  // niet in de vraag of er iets niet opgeslagen is.
  const el = Object.create(Voorkeuren.prototype);
  const stuk = el.slice_({ strategy: { level: "steer", schedules: [{ device: "x" }] } });
  assert.deepEqual(stuk, { strategy: { level: "steer" } });
});

proef("op de kaart heet het Instellen, en de batterij krijgt een eigen knop", () => {
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf8");
  assert.ok(bron.includes('${icons.sliders} ${t("Instellen")}') && !bron.includes("Schema instellen"));
  assert.ok(bron.includes('data-settings="${slot}"'), "de knop voor een apparaat zonder schema");
  assert.ok(bron.includes("instellen.hidden = !blok.hidden || !heeftVoorkeuren(device)"), "alleen waar geen schema is en wel iets in te stellen");
  assert.equal(heeftVoorkeuren({ type: "thuisbatterij" }), true);
  assert.equal(heeftVoorkeuren({ type: "laadpaal" }), true);
  assert.equal(heeftVoorkeuren({ type: "boiler" }), false);
  const sheet = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/schedule-sheet.js", import.meta.url), "utf8");
  assert.ok(sheet.includes('"domotiapp_coach/device/preferences"'), "de pop-up slaat op via het commando van de bewoner");
  // Nooit een entiteit in Instellen.
  const accu = voorkeurHtml({ id: "b", type: "thuisbatterij", entities: { fan: "switch.fan" }, battery: {} });
  const paal = voorkeurHtml({ id: "p", type: "laadpaal", cars: [{ id: "a", name: "Bus", brand: "tesla", wake_entity: "button.w" }] });
  for (const html of [accu, paal]) assert.ok(!html.includes("dac-entity-picker"), "geen entiteit te kiezen");
  assert.ok(accu.includes('data-vk-accu="fan_above_c"'), "de ventilator alleen met een ventilator");
  assert.ok(!voorkeurHtml({ id: "b", type: "thuisbatterij", entities: {}, battery: {} }).includes("fan_above_c"));
});

proef("Meldingen: iedereen voegt personen toe, en er staat geen account meer bij", async () => {
  await import("../custom_components/domotiapp_coach/frontend/src/views/notifications.js");
  const Meldingen = geregistreerd.get("dac-view-notifications");
  const html = Object.create(Meldingen.prototype).render();
  assert.ok(!html.includes('id="nieuw-gebruiker"'), "geen keuze van een account");
  const el = Object.create(Meldingen.prototype);
  el.hass_ = { user: { is_admin: false } };
  assert.equal(el.opslagCommando_(), "domotiapp_coach/notifications/household");
  el.hass_ = { user: { is_admin: true } };
  assert.equal(el.opslagCommando_(), "domotiapp_coach/notifications/set");
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/notifications.js", import.meta.url), "utf8");
  assert.ok(!bron.includes("!this.isAdmin_() || !this.settings_"), "de drempels zijn er voor iedereen");
  assert.ok(!bron.includes("config/auth/list"), "de lijst gebruikers wordt niet meer opgevraagd");
});

// De eigenaar op 12-10-2026, met een schermafdruk van de pop-up Instellen: "dit is wit
// moet ook donker zijn". De uitklaplijst tekent de browser zelf; zonder een eigen regel
// voor de opties is hij wit, en met onze lichte letters onleesbaar. Op 06-09-2026
// gebeurde hetzelfde bij Meldingen. Elk scherm met een uitklaplijst krijgt dus de
// kleuren van het thema, of de stijlen van de bewerkschermen waar die regel in zit.
proef("elke uitklaplijst heeft de kleuren van het thema, ook in Instellen", async () => {
  const { readdirSync } = await import("node:fs");
  const map = new URL("../custom_components/domotiapp_coach/frontend/src/", import.meta.url);
  const bestanden = [...readdirSync(map).filter((n) => n.endsWith(".js")),
                     ...readdirSync(new URL("views/", map)).filter((n) => n.endsWith(".js")).map((n) => `views/${n}`)];
  // Wie de velden maakt en wie de stijl levert: voorkeur-velden.js tekent in schedule-sheet.js.
  const stijlVan = { "voorkeur-velden.js": "schedule-sheet.js" };
  const missen = [];
  for (const naam of bestanden) {
    const bron = readFileSync(new URL(naam, map), "utf8");
    if (!/<select\b|createElement\("select"\)/.test(bron)) continue;
    const stijl = readFileSync(new URL(stijlVan[naam] ?? naam, map), "utf8");
    const heeft = /select option \{ background: var\(--dac-bg-raise\)/.test(stijl) || stijl.includes("${editorCss}");
    if (!heeft) missen.push(naam);
  }
  assert.deepEqual(missen, [], "zonder kleuren voor de opties");
  const blad = readFileSync(new URL("schedule-sheet.js", map), "utf8");
  assert.ok(blad.includes("color-scheme: var(--dac-scheme)"), "en de lijst zelf volgt licht en donker");
});

// --- de tijdlijn in Historie (v0.115.0) --------------------------------------
// De eigenaar op 11-10-2026: wat de coach en de apparaten deden, als tijdlijn,
// met een korte tekst bij een klik. De kleur is wat de meter zegt; zie
// tijdlijn.js voor de dag waarop de regel loog.

const T = await import("../custom_components/domotiapp_coach/frontend/src/tijdlijn.js");
const TL_DAG = new Date(2026, 9, 11);
const tlOm = (klok, dagen = 0) => {
  const [u, m] = klok.split(":").map(Number);
  const t = new Date(TL_DAG); t.setDate(t.getDate() + dagen); t.setHours(u, m, 0, 0);
  return t;
};
const tlTot = new Date(TL_DAG.getTime() + 864e5);
const tlBesluit = (klok, device, message, extra = {}) =>
  ({ at: tlOm(klok).toISOString(), kind: "besluit", message, ...(device ? { device } : {}), ...extra });
/** Kwartieren met een vast vermogen tussen twee kloktijden, zoals `quarters` ze geeft. */
const tlWatt = (van, tot, watt) => {
  const uit = [];
  const eind = tot === "24:00" ? tlTot : tlOm(tot);
  for (let t = tlOm(van); t < eind; t = new Date(t.getTime() + 9e5)) {
    uit.push({ start: t, laagste: watt, piek: watt, gemiddeld: watt, seconden: 900 });
  }
  return uit;
};
const TL_APPARATEN = [
  { id: "p", type: "laadpaal", name: "Laadpaal", entity: "sensor.paal" },
  { id: "a", type: "thuisbatterij", name: "Batterij", entity: "" },
  { id: "v", type: "vaatwasser", name: "Vaatwasser", entity: "sensor.vaat" },
  { id: "b", type: "boiler", name: "Boiler", entity: "sensor.boiler" },
  { id: "o", type: "overig", name: "Printer", entity: "sensor.printer" },
];
const TL_BEURT = [
  tlBesluit("12:08", "p", "Laadpaal: laden op 6 A. De auto is nog niet begonnen, dus hij biedt even 16 A aan om hem wakker te maken.",
    { rule: "surplus+wake", charge: true }),
  tlBesluit("12:11", "p", "Laadpaal: laden op 6 A. Er is 1,5 kW zon over.", { rule: "surplus", charge: true }),
  tlBesluit("13:45", "p", "Laadpaal: niet laden. Hij wacht tot 20:00.", { rule: "wait", charge: false }),
];
const tlRijen = (items, vermogen = {}, net = []) =>
  T.metHerkomst(T.tijdlijn(items, TL_APPARATEN, TL_DAG, tlTot, tlOm("23:59", 1)),
    (id) => vermogen[id] ?? [], net);

proef("Tijdlijn: de kleur van een laadbeurt is de meter, niet de regel", () => {
  // De regel zei zon, de meter zei dat 65% van het net kwam: bij de eigenaar op 11-10-2026
  // stond zo'n beurt eerst oranje.
  const rijen = tlRijen(TL_BEURT, { p: tlWatt("12:00", "13:45", 4000) }, tlWatt("00:00", "24:00", 2600));
  const laden = rijen[0].stukken[0];
  assert.equal(laden.stand, "laden");
  assert.equal(T.klasseVan(laden), "net", "blauw, want het meeste kwam van het net");
  assert.equal(Math.round(laden.netDeel * 100), 65);
  assert.match(T.klikTekst(rijen[0], laden).wat, /^Laden, \d+,\d kWh, ongeveer 65% van het net\.$/);
  // En met een zonnige meter wordt hij oranje.
  const zonnig = tlRijen(TL_BEURT, { p: tlWatt("12:00", "13:45", 4000) }, tlWatt("00:00", "24:00", 200));
  assert.equal(T.klasseVan(zonnig[0].stukken[0]), "zon");
  assert.match(T.klikTekst(zonnig[0], zonnig[0].stukken[0]).wat, /ongeveer 5% van het net|op zon/);
});

proef("Tijdlijn: de reden bij een klik is de reden die het langst gold, niet het wekken", () => {
  const rijen = tlRijen(TL_BEURT);
  assert.equal(T.hoofdreden(rijen[0].stukken[0]), "Er is 1,5 kW zon over.");
  // Alleen wekken: dan is dat het, want er is niets anders.
  const alleenWekken = tlRijen([TL_BEURT[0], TL_BEURT[2]]);
  assert.match(T.hoofdreden(alleenWekken[0].stukken[0]), /wakker te maken/);
  // Zonder regel erbij herkend aan de tekst, en "nog even door" is ook een bijzaak.
  assert.ok(T.bijzaak({}, "Hij laadt nog even door op de laagste stand. Een auto stopt niet graag steeds."));
  assert.ok(T.bijzaak({ rule: "cheap-hour+hold" }, ""));
  assert.ok(!T.bijzaak({ rule: "surplus" }, "Er is 1,5 kW zon over."));
});

proef("Tijdlijn: van het net bij een gesplitste meter en bij een meter met een teken, in allebei de richtingen", () => {
  const rij = (watt) => [{ start: tlOm("12:00"), laagste: watt, piek: watt, gemiddeld: watt, seconden: 900 }];
  const gesplitst = T.netReeks({ grid_mode: "split", grid_import: "sensor.af" }, new Map([["sensor.af", rij(800)]]));
  assert.equal(gesplitst[0].gemiddeld, 800);
  const teken = (invert, watt) =>
    T.netReeks({ grid_mode: "signed", grid_signed: "sensor.p1", grid_signed_invert: invert },
      new Map([["sensor.p1", rij(watt)]]))[0].gemiddeld;
  assert.equal(teken(false, 800), 800, "plus is afname");
  assert.equal(teken(false, -800), 0, "min is teruglevering, dus niets van het net");
  assert.equal(teken(true, -800), 800, "omgekeerd: min is afname");
  assert.equal(teken(true, 800), 0);
  assert.deepEqual(T.netReeks({ grid_mode: "split", grid_import: "" }, new Map()), [], "zonder meter niets");
});

proef("Tijdlijn: aan zonder dat er iets liep is geen zon en geen net", () => {
  // Een auto die niet wakker werd: de paal stond aan, de meter van de paal zag niets.
  const rijen = tlRijen(TL_BEURT, { p: tlWatt("12:00", "13:45", 0) }, tlWatt("00:00", "24:00", 500));
  const stuk = rijen[0].stukken[0];
  assert.equal(T.klasseVan(stuk), "leeg");
  assert.equal(T.klikTekst(rijen[0], stuk).wat, "Laden, er liep niets.");
});

proef("Tijdlijn: zonder kwartieren valt de kleur terug op de regel, en dat zegt de tekst", () => {
  const rijen = tlRijen(TL_BEURT);
  const stuk = rijen[0].stukken[0];
  assert.equal(stuk.kwh, undefined, "niets gemeten");
  assert.equal(T.klasseVan(stuk), "zon", "de regel was zon");
  assert.equal(T.klikTekst(rijen[0], stuk).wat, "Laden, vooral op zon.");
});

proef("Tijdlijn: de stand van gisteren loopt door tot er iets anders komt, en vandaag houdt op bij nu", () => {
  const items = [
    { at: tlOm("22:00", -1).toISOString(), kind: "besluit", device: "a", mode: "nul",
      message: "Batterij: nul op de meter. Hij houdt de meter op nul." },
    tlBesluit("18:00", "a", "Batterij: handelen. Het net betaalt nu veel.", { mode: "handelen" }),
  ];
  const heel = T.tijdlijn(items, TL_APPARATEN, TL_DAG, tlTot, tlOm("23:59", 1));
  assert.deepEqual(heel[0].stukken.map((s) => [T.klok(s.van), s.stand]), [["00:00", "nul"], ["18:00", "ontladen"]]);
  assert.equal(T.klikTekst(heel[0], heel[0].stukken[1], { dagEind: tlTot }).tijd, "18:00 tot 24:00");
  const nu = tlOm("19:30");
  const vandaag = T.tijdlijn(items, TL_APPARATEN, TL_DAG, tlTot, nu);
  assert.equal(vandaag[0].stukken[1].tot.getTime(), nu.getTime());
  assert.equal(T.klikTekst(vandaag[0], vandaag[0].stukken[1], { dagEind: tlTot, nu }).tijd, "18:00 tot nu");
});

proef("Tijdlijn: regels van voor v0.115.0 worden herkend aan de naam vooraan", () => {
  const apparaten = [
    { id: "p1", type: "laadpaal", name: "Bus" },
    { id: "p2", type: "laadpaal", name: "Bus achter" },
    { id: "a", type: "thuisbatterij", name: "Batterij" },
  ];
  const items = [
    tlBesluit("09:00", null, "Bus achter: laden op 6 A. Er is 1,5 kW zon over."),
    tlBesluit("10:00", null, "Bus achter: niet laden. Er hangt geen auto aan de lader."),
    tlBesluit("09:30", null, "Batterij doet zelf nul op de meter, met zijn eigen meter."),
  ];
  const rijen = T.tijdlijn(items, apparaten, TL_DAG, tlTot, tlOm("23:59", 1));
  assert.deepEqual(rijen.map((r) => r.device), ["p2", "a"], "de langste naam wint, en Bus zelf deed niets");
  assert.equal(rijen[0].stukken[0].bron, "zon");
  assert.equal(T.klok(rijen[0].stukken[0].tot), "10:00", "geen auto: daar houdt de baan op");
  assert.equal(rijen[1].stukken[0].stand, "nul");
});

proef("Tijdlijn: alleen wat de coach stuurt krijgt een baan, en een boiler en een vaatwasser kleuren ook naar de meter", () => {
  const items = [
    tlBesluit("11:00", "b", "Boiler: start nu. Er is zon over.", { rule: "zon", charge: true }),
    tlBesluit("12:00", "b", "Boiler: wacht. Het vat is vol.", { rule: "vol", charge: false }),
    tlBesluit("13:00", "v", "Vaatwasser: draait. Hij draait.", { rule: "running", charge: true }),
    tlBesluit("14:30", "v", "Vaatwasser: wacht. Het programma is klaar.", { rule: "done", charge: false }),
    tlBesluit("15:00", "o", "Printer: iets."),
  ];
  const rijen = tlRijen(items,
    { b: tlWatt("11:00", "12:00", 2000), v: tlWatt("13:00", "14:30", 800) },
    [...tlWatt("11:00", "13:00", 0), ...tlWatt("13:00", "14:30", 800)]);
  assert.deepEqual(rijen.map((r) => r.device), ["v", "b"], "de printer stuurt de coach niet");
  const vaat = rijen.find((r) => r.device === "v").stukken[0];
  const boiler = rijen.find((r) => r.device === "b").stukken[0];
  assert.equal(T.klasseVan(boiler), "zon");
  assert.equal(T.klikTekst({ naam: "Boiler" }, boiler, { metAccu: true }).wat, "Stroom erop, 2,0 kWh, op zon of batterij.");
  assert.equal(T.klasseVan(vaat), "net");
  assert.equal(T.klikTekst({ naam: "Vaatwasser" }, vaat).wat, "Draait, 1,2 kWh, van het net.");
});

proef("Tijdlijn: een kort tussenstuk gaat op in de beurt eromheen", () => {
  const items = [
    tlBesluit("12:00", "p", "Laadpaal: laden op 6 A. Er is zon over.", { rule: "surplus", charge: true }),
    tlBesluit("12:30", "p", "Laadpaal: niet laden. Even niet.", { rule: "wait", charge: false }),
    tlBesluit("12:32", "p", "Laadpaal: laden op 6 A. Dit uur is goedkoop.", { rule: "cheap-hour", charge: true }),
    tlBesluit("14:00", "p", "Laadpaal: niet laden. De auto staat op 80% en verder hoeft hij niet.", { rule: "complete", charge: false }),
  ];
  const rijen = T.tijdlijn(items, TL_APPARATEN, TL_DAG, tlTot, tlOm("23:59", 1));
  assert.deepEqual(rijen[0].stukken.map((s) => [T.klok(s.van), T.klok(s.tot), s.stand]),
    [["12:00", "14:00", "laden"], ["14:00", "00:00", "vol"]]);
  assert.equal(rijen[0].stukken[0].bron, "net", "88 minuten goedkoop uur tegen 30 minuten zon");
});

proef("Tijdlijn: de tekening, met een knop per stuk, de stippen en de streep op nu", () => {
  const items = [...TL_BEURT,
    { at: tlOm("08:10").toISOString(), kind: "kritiek", message: "De accustand meldt al 60 minuten niets." },
    { at: tlOm("13:46").toISOString(), kind: "melding", message: "Geladen.\n6,4 kWh." }];
  const rijen = tlRijen(items, { p: tlWatt("12:00", "13:45", 4000) }, tlWatt("00:00", "24:00", 200));
  const punten = T.stippen(items, TL_DAG, tlTot);
  const html = T.tekenTijdlijn({ rijen, stippen: punten, van: TL_DAG, tot: tlTot, nu: tlOm("15:00"), gekozen: "0:0", metAccu: true });
  assert.equal((html.match(/class="stuk /g) ?? []).length, rijen[0].stukken.length);
  assert.equal((html.match(/class="stip/g) ?? []).length, 2);
  assert.ok(html.includes('class="stip kritiek'), "kritiek is rood");
  assert.equal((html.match(/class="nu"/g) ?? []).length, 2, "een streep in elke baan, ook die van de meldingen");
  assert.ok(/class="stuk zon gekozen"/.test(html), "het aangetikte stuk");
  const gisteren = T.tekenTijdlijn({ rijen, stippen: punten, van: TL_DAG, tot: tlTot, nu: tlOm("12:00", 1) });
  assert.ok(!gisteren.includes('class="nu"'), "een dag die voorbij is heeft geen nu");
  const uitleg = T.tekenUitleg({ rijen, stippen: punten, gekozen: "stip:1", tot: tlTot });
  assert.ok(uitleg.includes("13:46") && uitleg.includes("Geladen."), "een stip zegt de melding");
  assert.deepEqual(T.legenda(rijen, true).map((l) => l.label), ["Eigen zon en batterij", "Wacht"]);
  assert.deepEqual(T.legenda(rijen, false).map((l) => l.label), ["Eigen zon", "Wacht"]);
});

proef("Tijdlijn: de kaart staat bij Dag en Week, en zegt het bij Maand; alleen als de coach iets stuurt", () => {
  const vak = () => ({ hidden: false, innerHTML: "", textContent: "", replaceChildren() { this.innerHTML = ""; } });
  const el = Object.create(Historie.prototype);
  const vakken = { "#tijdlijn-card": vak(), "#tijdlijn": vak(), "#tijdlijn-legenda": vak(), "#tijdlijn-uitleg": vak(), "#tijdlijn-note": vak() };
  el.$ = (sel) => vakken[sel];
  el.onderwerp_ = "energie";
  el.period_ = "day";
  // Gisteren, en niet vandaag: tussen middernacht en 01:00 lag een besluit om 01:00
  // vandaag in de toekomst, en dan viel deze proef 's nachts om (19-10-2026, 00:05).
  el.offset_ = -1;
  el.settings_ = { sources: { grid_mode: "split", grid_import: "sensor.net" }, devices: TL_APPARATEN };
  const van = new Date(); van.setHours(0, 0, 0, 0); van.setDate(van.getDate() - 1);
  el.tl_ = { dag: `day:${van.getTime()}`, meldingen: [{ at: new Date(van.getTime() + 36e5).toISOString(), kind: "besluit",
    device: "a", mode: "nul", message: "Batterij: nul op de meter. Hij houdt de meter op nul." }], kwartieren: new Map(), gehaald: Date.now() };
  el.paintTijdlijn_();
  assert.equal(vakken["#tijdlijn-card"].hidden, false);
  assert.ok(vakken["#tijdlijn"].innerHTML.includes('class="stuk nul'), "de batterij staat erop");
  assert.equal(vakken["#tijdlijn-uitleg"].hidden, true, "nog niets aangetikt");
  // De eigenaar op 13-10-2026, bij Week: "waarom is de tijdlijn weg die wil ik wel behouden".
  el.period_ = "week";
  el.paintTijdlijn_();
  assert.equal(vakken["#tijdlijn-card"].hidden, false, "bij een week blijft hij staan");
  el.period_ = "month";
  el.paintTijdlijn_();
  assert.equal(vakken["#tijdlijn-card"].hidden, false, "bij een maand verdwijnt hij niet zomaar");
  assert.equal(vakken["#tijdlijn-note"].textContent, "De tijdlijn staat bij Dag en Week.");
  assert.equal(vakken["#tijdlijn"].innerHTML, "");
  el.period_ = "day";
  el.settings_ = { ...el.settings_, devices: [TL_APPARATEN[4]] };
  el.paintTijdlijn_();
  assert.equal(vakken["#tijdlijn-card"].hidden, true, "alleen een apparaat dat de coach meet");
});

// --- Historie overzichtelijk (v0.116.0) ---------------------------------------
// De eigenaar op 13-10-2026: "ik wil alles zo duidelijk mogelijk hebben en zo kort
// mogelijk", "Het moet niet zo zijn dat het gigantisch veel wordt alle data dat
// mensen het niet meer snappen", en "periode onderwerp en verloop moet een drop
// down worden".

/** Een element zonder browser: genoeg voor wat de teken-methoden aanraken. */
function nepEl(tag = "div") {
  return {
    tag, className: "", textContent: "", hidden: false, kinderen: [], style: { setProperty() {} },
    append(...k) { this.kinderen.push(...k); },
    replaceChildren(...k) { this.kinderen = k; },
    setAttribute() {},
  };
}
function metNepDocument(fn) {
  const oud = globalThis.document.createElement;
  globalThis.document.createElement = (tag) => nepEl(tag);
  try { return fn(); } finally { globalThis.document.createElement = oud; }
}

proef("Historie: onderwerp, periode en verloop zijn uitklaplijsten, en er is één knop Rapport", () => {
  const html = Object.create(Historie.prototype).render();
  for (const id of ["onderwerp", "periode", "korrel"]) assert.ok(html.includes(`<select id="${id}">`), id);
  assert.ok(!html.includes('class="segmented'), "geen rijen knoppen meer");
  assert.ok(!html.includes("korrel-note"), "geen regel over het aantal rapportregels");
  assert.ok(html.includes('<option value="bespaard">Sessies</option>'), "het onderwerp heet Sessies (v0.126.4)");
  assert.equal((html.match(/id="rapport-knop"/g) ?? []).length, 1);
  assert.ok(/id="rapport-menu"[^>]*hidden/.test(html), "het menu is dicht tot je op Rapport tikt");
  assert.ok(html.includes("Boven de lijn wat je verbruikte, onder de lijn wat je teruggaf."), "de inleiding is één zin");
});

proef("Historie: een verloop dat bij de periode niet kan valt terug op wat erbij past", () => {
  const el = Object.create(Historie.prototype);
  el.period_ = "day";
  el.korrel_ = "month";
  assert.equal(el.korrel_id(), "quarter", "een maand per kwartier op een dag bestaat niet");
  el.korrel_ = "hour";
  assert.equal(el.korrel_id(), "hour");
  el.period_ = "year";
  assert.equal(el.korrel_id(), "hour", "een jaar per uur kan wel");
  el.korrel_ = "";
  assert.equal(el.korrel_id(), "month");
});

proef("Energie: vier tegels en twee percentages, en geen 'Hele periode'", () => {
  const el = Object.create(Historie.prototype);
  const vak = { totals: nepEl(), titel: nepEl() };
  el.$ = (sel) => (sel === "#totals" ? vak.totals : vak.titel);
  metNepDocument(() => el.paintTotals_({ solar: 25.8, used: 18.2, bought: 4.7, sold: 12.2, selfUse: 53, selfSufficient: 75 }));
  const labels = vak.totals.kinderen.map((cel) => cel.kinderen[0].textContent);
  // Zon zelf gebruikt is terug sinds v0.126.5: "ik wil zelf verbruikte zonne-energie wel terug hebben weer."
  assert.deepEqual(labels, ["Opgewekt", "Verbruikt", "Van het net", "Naar het net", "Zon zelf gebruikt", "Zelfvoorzienend"]);
  const waarde = vak.totals.kinderen[4].kinderen[1];
  assert.equal(`${waarde.textContent}${waarde.kinderen[0].textContent}`, "53%");
  metNepDocument(() => el.paintTotals_({ solar: null, used: null, bought: 4.7, sold: 0, selfUse: null, selfSufficient: null }));
  assert.ok(!vak.totals.kinderen.some((cel) => cel.kinderen[0].textContent === "Zon zelf gebruikt"), "zonder zon geen percentage");
  assert.ok(!Historie.css.includes("Hele periode"));
});

proef("de grafiek: de batterij in haar eigen kleur, boven de lijn eruit en onder de lijn erin (v0.126.2)", async () => {
  const { stapel, huisMetAccu: huis } = await import("../custom_components/domotiapp_coach/frontend/src/views/history.js");
  const vak = (own, bought, sold, erin, eruit) => ({ own, bought, sold, accuIn: erin, accuUit: eruit, ...huis(own, bought, { battery: erin - eruit, voor: 0 }) });
  const kwh = (delen) => Object.fromEntries(delen.map(([soort, w]) => [soort, Math.round(w * 1000) / 1000]));
  const som = (delen) => delen.reduce((t, [, w]) => t + w, 0);
  // Een uur zon: 1 kWh zelf gebruikt, 2 de batterij in, 1 naar het net.
  const middag = vak(3, 0.2, 1, 2, 0);
  assert.deepEqual(kwh(stapel(middag).boven), { own: 1, accu: 0, bought: 0.2 });
  assert.deepEqual(kwh(stapel(middag).onder), { accu: 2, sold: 1 });
  // Een uur in de avond: 0,85 uit de batterij, 0,1 van het net.
  const avond = vak(0, 0.1, 0, 0, 0.85);
  assert.deepEqual(kwh(stapel(avond).boven), { own: 0, accu: 0.85, bought: 0.1 });
  assert.deepEqual(kwh(stapel(avond).onder), { accu: 0, sold: 0 });
  // Een nacht laden van het net is geen verbruik; het staat onder de lijn.
  const nacht = vak(0, 3, 0, 2.5, 0);
  assert.deepEqual(kwh(stapel(nacht).boven), { own: 0, accu: 0, bought: 0.5 });
  assert.deepEqual(kwh(stapel(nacht).onder), { accu: 2.5, sold: 0 });
  // Een dag: 's nachts 5 van het net de batterij in en 's avonds eruit telt als
  // van het net, zoals in Zelfvoorzienend; de balk blijft precies Verbruikt.
  const dag = vak(0, 7, 0, 5, 5);
  assert.deepEqual(kwh(stapel(dag).boven), { own: 0, accu: 0, bought: 7 });
  for (const v of [middag, avond, nacht, dag]) assert.ok(Math.abs(som(stapel(v).boven) - v.used) < 1e-9, "boven is Verbruikt");
  // Het scherm, de legenda en het rapport.
  const bron = Historie.toString() + Historie.css;
  assert.ok(Historie.css.includes(".b.accu { fill: var(--dac-device-1); }"));
  assert.ok(/label: "Batterij"/.test(Historie.toString()));
  // Geen roze voor de batterij (v0.126.3): het eerste bolletje, waar de batterij
  // altijd staat, is groenblauw, en het rapport tekent haar in dezelfde kleur.
  const tokens = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/theme.js", import.meta.url), "utf8");
  assert.ok(/--dac-device-1:\s*#039580;/.test(tokens), "de batterij is groenblauw");
  assert.ok(/--dac-device-2:\s*#fd0774;/.test(tokens), "het roze is naar het tweede bolletje");
  assert.ok(/\.stuk\.nul, \.vlek\.nul \{ background: color-mix\(in srgb, var\(--dac-device-1\)/.test(Historie.css), "nul op de meter is geen roze");
  const rbron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/report.js", import.meta.url), "utf8");
  assert.ok(/accu: "#039580"/.test(rbron) && /net: "#129be4"/.test(rbron) && /terug: "#bc10c8"/.test(rbron), "het rapport heeft de kleuren van het scherm");
  assert.ok(/verloop: rows\.map\(\(row\) => \(\{ label: bucketLabel\(this\.period_, row\.start\), \.\.\.stapel\(row\) \}\)\)/.test(bron), "het rapport tekent dezelfde stapel");
});

proef("Energie: met een thuisbatterij ook geladen en ontladen, naast het net (v0.126.0)", () => {
  const el = Object.create(Historie.prototype);
  const vak = { totals: nepEl(), titel: nepEl() };
  el.$ = (sel) => (sel === "#totals" ? vak.totals : vak.titel);
  el.accuTegels_ = true;
  metNepDocument(() =>
    el.paintTotals_({ solar: 25.8, used: 18.2, bought: 4.7, sold: 12.2, accuIn: 6.4, accuUit: 5.1, selfSufficient: 75 })
  );
  const tegels = vak.totals.kinderen.map((cel) => [cel.kinderen[0].textContent, cel.kinderen[1].textContent]);
  assert.deepEqual(tegels.map((t) => t[0]), [
    "Opgewekt", "Verbruikt", "Van het net", "Naar het net", "Batterij geladen", "Batterij ontladen", "Zelfvoorzienend",
  ]);
  assert.ok(tegels[4][1].startsWith("6,4"), tegels[4][1]);
  assert.ok(tegels[5][1].startsWith("5,1"), tegels[5][1]);
  // Een vak aangewezen waarin de batterij niets deed: dan 0, niet weg.
  vak.totals = nepEl();
  metNepDocument(() => el.paintTotals_({ solar: 1, used: 1, bought: 0, sold: 0, accuIn: 0, accuUit: 0, selfSufficient: 100 }));
  assert.equal(vak.totals.kinderen.length, 7);
  // Zonder batterij geen tegels; en het rapport zegt hetzelfde.
  el.accuTegels_ = false;
  vak.totals = nepEl();
  metNepDocument(() => el.paintTotals_({ solar: 1, used: 1, bought: 0, sold: 0, selfSufficient: 100 }));
  assert.equal(vak.totals.kinderen.length, 5);
  const bron = Historie.toString();
  assert.ok(/cel\("Batterij geladen"/.test(bron) && /cel\("Batterij ontladen"/.test(bron), "ook in het rapport");
});

proef("In geld: twee getallen bovenaan, de derde volgde uit die twee", () => {
  const bron = Historie.toString();
  assert.ok(!/kop\("Zonder zon, batterij en coach"/.test(bron), "niet op het scherm");
  assert.ok(!/cel\("Zonder zon, batterij en coach"/.test(bron), "en niet in het rapport");
});

proef("Beurten: drie tegels met de uitsplitsing eronder, één lijst met vijf kolommen", () => {
  const el = Object.create(Historie.prototype);
  const vak = { "#saved-note": nepEl("p"), "#saved-totals": nepEl(), "#saved-list": nepEl("table") };
  el.$ = (sel) => vak[sel];
  el.period_ = "month";
  el.offset_ = 0;
  const nu = new Date();
  el.beurten_ = [
    { device: "p", name: "Laadpaal", kind: "laden", car: "De blauwe", plugged_at: nu.toISOString(), ended: nu.toISOString(),
      complete: true, kwh: 21.9, solar_kwh: 2.4, battery_kwh: 0.7, paid: 4.95, ref_cost: 6.1, saved: 1.15, solar_saved: 0.39 },
  ];
  metNepDocument(() => el.paintSaved_());
  const tegels = vak["#saved-totals"].kinderen;
  assert.deepEqual(tegels.map((t) => t.kinderen[0].textContent), ["Bespaard", "Betaald", "Geladen"]);
  assert.match(tegels[0].kinderen[2].textContent, /door zon, .* door wachten$/);
  assert.match(tegels[2].kinderen[2].textContent, /zon, .* uit de batterij$/);
  const kop = vak["#saved-list"].kinderen[0].kinderen.map((c) => c.textContent);
  assert.deepEqual(kop, ["Ingeplugd", "Apparaat", "Geladen", "Betaald", "Bespaard"]);
  for (const zin of vak["#saved-note"].textContent.split(/(?<=\.) /)) assert.ok(zin.length <= 120, `te lang: ${zin}`);
});

proef("Tijdlijn: een week heeft dagen langs de as, en de tekst bij een klik noemt de dag", () => {
  const maandag = new Date(2026, 9, 5);
  const zondagEind = new Date(2026, 9, 12);
  const items = [
    { at: new Date(2026, 9, 10, 22, 30).toISOString(), kind: "besluit", device: "p", rule: "cheap-hour", charge: true,
      message: "Laadpaal: laden op 16 A. Dit uur is goedkoop." },
    { at: new Date(2026, 9, 11, 1, 40).toISOString(), kind: "besluit", device: "p", rule: "complete", charge: false,
      message: "Laadpaal: niet laden. De auto staat op 80% en verder hoeft hij niet." },
    { at: new Date(2026, 9, 11, 7, 30).toISOString(), kind: "besluit", device: "p", rule: "disconnected", charge: false,
      message: "Laadpaal: niet laden. Er is geen auto aangesloten op de laadpaal." },
  ];
  const rijen = T.tijdlijn(items, TL_APPARATEN, maandag, zondagEind, new Date(2026, 9, 20));
  const html = T.tekenTijdlijn({ rijen, van: maandag, tot: zondagEind, nu: new Date(2026, 9, 20) });
  assert.equal((html.match(/class="dag"/g) ?? []).length, 7, "zeven dagen langs de as");
  assert.ok(html.includes(">ma 5<") && html.includes(">zo 11<"), "van maandag tot zondag");
  assert.ok(html.includes("--raster:14.29%"), "een lijntje per dag");
  assert.equal(T.klikTekst(rijen[0], rijen[0].stukken[0], { metDag: true }).tijd, "za 10 22:30 tot zo 11 01:40");
  assert.equal(T.klikTekst(rijen[0], rijen[0].stukken[1], { metDag: true }).tijd, "zo 11 01:40 tot 07:30");
  // En een dag blijft zoals hij was.
  const dag = T.tekenTijdlijn({ rijen: [], van: TL_DAG, tot: tlTot });
  assert.ok(dag.includes(">00:00<") && !dag.includes('class="dag"') && dag.includes("--raster:12.5%"));
});

proef("Historie: het pijltje van een uitklaplijst hoort bij de lijst, niet bij het opschrift", () => {
  assert.match(Historie.css, /\.kies \{[^}]*align-self: flex-start/);
});

proef("Sessies: de uitleg zegt eerst wat een sessie is", () => {
  const el = Object.create(Historie.prototype);
  const vak = { "#saved-note": nepEl("p"), "#saved-totals": nepEl(), "#saved-list": nepEl("table") };
  el.$ = (sel) => vak[sel];
  el.period_ = "month";
  el.offset_ = 0;
  const nu = new Date();
  el.beurten_ = [{ device: "v", name: "Vaatwasser", kind: "programma", plugged_at: nu.toISOString(), ended: nu.toISOString(),
    complete: true, kwh: 0.9, solar_kwh: 0.3, battery_kwh: 0, paid: 0.2, ref_cost: 0.22, saved: 0.02, solar_saved: 0.02 }];
  metNepDocument(() => el.paintSaved_());
  assert.match(vak["#saved-note"].textContent, /^Een sessie is één keer dat de coach een apparaat liet draaien/);
});

// --- de smart plug (v0.120.0) ----------------------------------------------------
//
// De eigenaar op 15-10-2026: "Ik wil bij apparaten toevoegen dan de optie smart plug. En
// dan als ik die heb gekozen een hele lijst met apparaten zoals wasmachine, oven vriezer
// etc etc. Allemaal met de naam en icon. Dan de optie energieteller, vermogensteller en
// een belangrijke optie, dit apparaat moet altijd aan staan."

proef("smart plug: de lijst in het paneel is dezelfde als in const.py, en elk apparaat heeft een eigen icoon", async () => {
  const { PLUG_APPLIANCES, DEVICE_TYPES } = await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  const { icons } = await import("../custom_components/domotiapp_coach/frontend/src/icons.js");
  assert.ok(DEVICE_TYPES.some((t) => t.id === "smartplug" && t.label === "Smart plug"), "een type");
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/const.py", import.meta.url), "utf-8")
    .replace(/\r/g, "");
  const blok = bron.slice(bron.indexOf("STEKKER_APPARATEN: Final = {"), bron.indexOf("}", bron.indexOf("STEKKER_APPARATEN: Final = {")));
  const python = new Map([...blok.matchAll(/"([a-z_]+)": \("([^"]+)", "(de|het)"\)/g)].map((m) => [m[1], m[2]]));
  assert.equal(python.size, PLUG_APPLIANCES.length, "evenveel apparaten");
  for (const a of PLUG_APPLIANCES) {
    assert.ok(python.has(a.id), `${a.id} staat ook in const.py`);
    if (a.id !== "overig") assert.equal(python.get(a.id), a.label, a.id);
    assert.ok(icons[a.icon], `${a.id} heeft een icoon`);
  }
  assert.ok(PLUG_APPLIANCES.length >= 20, "een hele lijst");
  assert.equal(PLUG_APPLIANCES.at(-1).id, "overig", "Iets anders onderaan");
  const namen = PLUG_APPLIANCES.slice(0, -1).map((a) => a.label);
  assert.deepEqual(namen, [...namen].sort((a, b) => a.localeCompare(b, "nl")), "de rest op naam");
  const eigen = PLUG_APPLIANCES.filter((a) => a.id !== "overig" && a.id !== "vaatwasser").map((a) => a.icon);
  assert.equal(new Set(eigen).size, eigen.length, "geen twee apparaten met hetzelfde icoon");
});

proef("smart plug: de naam en het icoon komen van wat eraan hangt, ook in de tip", async () => {
  const { deviceLabel, deviceLabels, deviceIcon, kindLabel, apparatenZin, canSteer } =
    await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  const vriezer = { id: "v", type: "smartplug", appliance: "vriezer", name: "" };
  assert.equal(deviceLabel(vriezer), "Vriezer");
  assert.equal(deviceIcon(vriezer), "vriezer");
  assert.equal(deviceLabel({ ...vriezer, name: "Vriezer garage" }), "Vriezer garage", "een eigen naam wint");
  assert.equal(deviceLabel({ ...vriezer, appliance: "overig" }), "Smart plug", "Iets anders heet Smart plug");
  assert.equal(deviceIcon({ ...vriezer, appliance: "overig" }), "plug");
  assert.equal(deviceLabel({ ...vriezer, appliance: "" }), "Smart plug", "nog niets gekozen");
  assert.equal(deviceIcon({ ...vriezer, appliance: "" }), "plug");
  assert.equal(kindLabel({ type: "laadpaal" }), "Laadpaal", "een ander type blijft zoals het was");
  assert.equal(deviceIcon({ type: "laadpaal" }), "laadpaal");
  assert.deepEqual(deviceLabels([vriezer, { ...vriezer, id: "w" }]), ["Vriezer 1", "Vriezer 2"], "twee vriezers krijgen een nummer");
  // Een smart plug telt niet als stuurbaar, dus de tip mag hem noemen.
  const was = { id: "w", type: "smartplug", appliance: "wasmachine", name: "", controllable: true, entities: { switch: "switch.was" } };
  assert.equal(canSteer(was), false);
  assert.match(apparatenZin([was]), /wasmachine/, "met het woord van wat eraan hangt, klein midden in een zin");
  assert.equal(apparatenZin([{ ...was, controllable: false }]), "", "zonder het vinkje niet");
});

proef("smart plug: de kaart en de pop-up zeggen of de stekker aan staat", () => {
  const plug = { id: "v", type: "smartplug", appliance: "vriezer", entity: "sensor.v_w", entities: { switch: "switch.v" } };
  const rij = (stand) => {
    const staten = { "switch.v": stand === undefined ? undefined : { state: stand, attributes: {} },
                     "sensor.v_w": { state: "85", attributes: { unit_of_measurement: "W" } } };
    const r = new LiveSource().sample({ get: (id) => staten[id] }, { sources: {}, devices: [plug] });
    return r.devices[0].details.find((d) => d.label === "Stekker")?.text;
  };
  assert.equal(rij("on"), "Aan");
  assert.equal(rij("off"), "Uit");
  assert.equal(rij("unavailable"), "—");
  const zonder = new LiveSource().sample({ get: () => undefined }, { sources: {}, devices: [{ ...plug, entities: {} }] });
  assert.equal(zonder.devices[0].details.length, 0, "zonder schakelaar geen regel");
});

proef("smart plug in Apparaten: eerst wat eraan hangt, dan schakelaar, vermogen, teller en altijd aan", async () => {
  await import("../custom_components/domotiapp_coach/frontend/src/views/devices.js");
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  const plug = { id: "v", type: "smartplug", appliance: "", name: "", entity: "", entities: {}, controllable: false };
  el.draft_ = { devices: [plug] };
  let html = el.brandHtml_(plug, 0);
  assert.ok(html.includes('data-field="appliance"') && html.includes("Kies wat eraan hangt"), "eerst de keuze");
  assert.ok(html.includes('<option value="vriezer">Vriezer</option>') && html.includes('<option value="overig">Iets anders</option>'));
  assert.ok(!html.includes("data-power") && !html.includes("always_on"), "verder nog niets");
  assert.equal(el.controlHtml_(plug, 0), "", "en geen vinkje zolang er niets gekozen is");
  assert.deepEqual(el.summary_(plug), { text: "nog niet gekozen wat eraan hangt", warn: true });

  plug.appliance = "vriezer";
  html = el.brandHtml_(plug, 0);
  const plek = (stuk) => html.indexOf(stuk);
  assert.ok(plek('data-field="appliance"') < plek('data-entity-key="switch"'), "apparaat, dan schakelaar");
  assert.ok(plek('data-entity-key="switch"') < plek("data-power"), "schakelaar, dan vermogen");
  assert.ok(plek("data-power") < plek("data-energy"), "vermogen, dan energieteller");
  assert.ok(plek("data-energy") < plek('data-field="always_on"'), "en dan altijd aan");
  assert.ok(html.includes("Dit apparaat moet altijd aan staan"));
  assert.ok(html.includes("na 2 minuten") && html.includes("Meldingen"), "de uitleg zegt wanneer er een bericht komt, en waar");
  assert.ok(/data-plug-missing="0"[^>]*>/.test(html) && /class="notice" hidden data-plug-missing/.test(html),
    "geen waarschuwing zolang altijd aan uit staat");
  assert.ok(el.controlHtml_(plug, 0).includes("De coach mag dit apparaat noemen"), "het vinkje om hem te noemen blijft");
  assert.equal(el.entityField_(plug, "switch")?.values?.on, "Aan", "de kiezer zegt Aan en Uit");

  plug.always_on = true;
  assert.ok(/class="notice" data-plug-missing/.test(el.brandHtml_(plug, 0)), "altijd aan zonder schakelaar: waarschuwing");
  assert.deepEqual(el.summary_(plug), { text: "altijd aan, maar zonder schakelaar", warn: true });
  plug.entities = { switch: "switch.v" };
  plug.entity = "sensor.v_w";
  assert.deepEqual(el.summary_(plug), { text: "sensor.v_w · altijd aan", warn: false });
  plug.name = "Vriezer garage";
  assert.deepEqual(el.summary_(plug), { text: "Vriezer · sensor.v_w · altijd aan", warn: false }, "met een eigen naam het soortwoord ervoor");

  // Een vaatwasser op een stekker: zeggen waar hij moet als de coach hem moet plannen.
  assert.match(el.brandHtml_({ ...plug, appliance: "vaatwasser" }, 0), /voeg hem dan toe als Vaatwasser/);
});

proef("Apparaat staat uit in Meldingen: alleen met iets dat altijd aan moet, en standaard uit", () => {
  const knoop = () => ({ hidden: false, textContent: "", attrs: {}, setAttribute(n, v) { this.attrs[n] = v; },
    getAttribute(n) { return this.attrs[n]; } });
  const knopen = new Map(["#stekker", "#stekker-aan", "#stekker-wie"].map((k) => [k, knoop()]));
  const el = Object.create(Meldingen.prototype);
  el.$ = (kiezer) => knopen.get(kiezer) ?? null;
  const vriezer = { id: "v", type: "smartplug", appliance: "vriezer", always_on: true };
  el.settings_ = { devices: [{ ...vriezer, always_on: false }], notifications: {} };
  el.paintStekker_();
  assert.equal(knopen.get("#stekker").hidden, true, "zonder altijd aan geen blok");
  el.settings_ = { devices: [vriezer, { id: "a", type: "smartplug", appliance: "aquarium", always_on: true }], notifications: {} };
  el.paintStekker_();
  assert.equal(knopen.get("#stekker").hidden, false);
  assert.equal(knopen.get("#stekker-aan").attrs["aria-checked"], "false", "standaard uit");
  assert.match(knopen.get("#stekker-wie").textContent, /^Geldt voor Vriezer en Aquarium\./);
  el.settings_.notifications = { always_on_alert: { enabled: true } };
  el.paintStekker_();
  assert.equal(knopen.get("#stekker-aan").attrs["aria-checked"], "true");
  const html = Object.create(Meldingen.prototype).render();
  assert.ok(html.includes('id="stekker" hidden') && html.includes("Apparaat staat uit"), "het blok staat in Meldingen");
});

// De eigenaar op 15-10-2026: "bij het apparaat vaatwasser ook de optie kunnen aanzetten dat
// hij nooit uit mag sommige vaatwassers hangen namelijk ook aan een smart plug om alles te meten."
proef("vaatwasser: een eigen stekker en altijd aan, zodra het merk gekozen is (v0.122.0)", async () => {
  await import("../custom_components/domotiapp_coach/frontend/src/views/devices.js");
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  const vw = { id: "vw", type: "vaatwasser", brand: "", name: "", entity: "sensor.vw_w", entities: {}, controllable: true, programs: [] };
  el.draft_ = { devices: [vw] };
  assert.ok(!el.brandHtml_(vw, 0).includes("Smart plug (optioneel)"), "zonder merk nog niet");
  for (const merk of ["overig", "home_connect"]) {
    vw.brand = merk;
    const html = el.brandHtml_(vw, 0);
    assert.ok(html.includes("Smart plug (optioneel)") && html.includes('data-entity-key="switch"'), `bij ${merk} het veld`);
    assert.ok(html.includes("Dit apparaat moet altijd aan staan"), `bij ${merk} het vinkje`);
  }
  assert.equal(el.entityField_(vw, "switch")?.values?.off, "Uit", "de kiezer zegt Aan en Uit");
  vw.brand = "overig";
  vw.always_on = true;
  assert.equal(el.plugMissing_(vw), true, "altijd aan zonder stekker: waarschuwing");
  vw.entities = { switch: "switch.vw_stekker" };
  assert.equal(el.plugMissing_(vw), false);
  assert.match(el.summary_(vw).text, / · altijd aan$/);
  // Een laadpaal heeft het niet.
  assert.ok(!el.brandHtml_({ id: "p", type: "laadpaal", brand: "easee", entities: {} }, 0).includes("altijd aan staan"));

  const staten = { "switch.vw_stekker": { state: "off", attributes: {} } };
  const r = new LiveSource().sample({ get: (id) => staten[id] }, { sources: {}, devices: [vw] });
  assert.equal(r.devices[0].details.find((d) => d.label === "Stekker")?.text, "Uit", "de kaart zegt het ook bij een vaatwasser");

  const knoop = () => ({ hidden: false, textContent: "", attrs: {}, setAttribute(n, v) { this.attrs[n] = v; } });
  const knopen = new Map(["#stekker", "#stekker-aan", "#stekker-wie"].map((k) => [k, knoop()]));
  const m = Object.create(Meldingen.prototype);
  m.$ = (kiezer) => knopen.get(kiezer) ?? null;
  m.settings_ = { devices: [vw], notifications: {} };
  m.paintStekker_();
  assert.equal(knopen.get("#stekker").hidden, false, "Apparaat staat uit staat er ook voor alleen een vaatwasser");
  assert.match(knopen.get("#stekker-wie").textContent, /^Geldt voor Vaatwasser\./);
});

// --- zelfvoorzienend: waar de stroom in de batterij vandaan kwam (v0.144.0) -----------
//
// De eigenaar op 22-10-2026: "Als mijn accu is geladen met netstroom, kan dat nooit
// resultaat hebben in mijn zelfvoorzienendheid. Zelfvoorzienend kan alleen maar door
// gebruikte stroom afkomstig van de zon die ik direct verbruik, óf eerst in de accu is
// opgeslagen." En: "ik heb ook andere klanten", dus elke vorm van installatie.

/**
 * Een nagemaakt huis voor `laadHerkomst_` en `buckets_`: per uur (tijd van het huis) zon,
 * afname, teruglevering en per batterij wat erin en eruit ging en de laagste accustand.
 * Antwoordt op de recorder zoals Home Assistant: per uur, per dag of per maand opgeteld.
 */
async function herkomstHuis({ uren, batterijen, periode = "day", start, zon = true }) {
  const { vanHuis, alsHuis } = await import("../custom_components/domotiapp_coach/frontend/src/format.js");
  const { periodEnd } = await import("../custom_components/domotiapp_coach/frontend/src/statistics.js");
  const vak = (tijd, korrel) => {
    const d = new Date(tijd);
    if (korrel === "hour") return d.getTime();
    if (korrel === "day") return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    return new Date(d.getFullYear(), d.getMonth()).getTime();
  };
  const reeks = (id) => {
    if (id === "sensor.zon") return uren.filter((u) => u.zon !== undefined).map((u) => [u.t, u.zon]);
    if (id === "sensor.af") return uren.map((u) => [u.t, u.af ?? 0]);
    if (id === "sensor.terug") return uren.map((u) => [u.t, u.terug ?? 0]);
    for (const b of batterijen) {
      if (b.entities?.energy_in === id) return uren.filter((u) => u[b.id]).map((u) => [u.t, u[b.id].erin ?? 0]);
      if (b.entities?.energy_out === id) return uren.filter((u) => u[b.id]).map((u) => [u.t, u[b.id].eruit ?? 0]);
      // Een vermogenssensor met een teken: het gemiddelde in watt, laden positief.
      if (b.entity === id) return uren.filter((u) => u[b.id]).map((u) => [u.t, ((u[b.id].erin ?? 0) - (u[b.id].eruit ?? 0)) * 1000]);
      // Losse sensoren voor laden en ontladen, zoals een Growatt die alleen uitgelezen wordt.
      if (b.entities?.charge_power === id) return uren.filter((u) => u[b.id]).map((u) => [u.t, (u[b.id].erin ?? 0) * 1000]);
      if (b.entities?.discharge_power === id) return uren.filter((u) => u[b.id]).map((u) => [u.t, (u[b.id].eruit ?? 0) * 1000]);
      if (b.entities?.soc === id) return uren.filter((u) => u[b.id]?.soc !== undefined).map((u) => [u.t, u[b.id].soc]);
    }
    return [];
  };
  const vragen = [];
  const hass = {
    callWS: async (msg) => {
      vragen.push(msg);
      const van = alsHuis(new Date(msg.start_time)).getTime();
      const tot = alsHuis(new Date(msg.end_time)).getTime();
      const uit = {};
      for (const id of msg.statistic_ids) {
        const per = new Map();
        for (const [t, w] of reeks(id)) {
          if (t < van || t >= tot) continue;
          const k = vak(t, msg.period);
          const soort = msg.types[0];
          const oud = per.get(k);
          per.set(k, soort === "min" ? Math.min(oud ?? Infinity, w) : soort === "mean" ? w : (oud ?? 0) + w);
        }
        uit[id] = [...per].sort((a, b) => a[0] - b[0]).map(([k, w]) => ({ start: vanHuis(new Date(k)).getTime(), [msg.types[0]]: w }));
      }
      return uit;
    },
  };
  const el = Object.create(Historie.prototype);
  el.hass_ = hass;
  el.period_ = periode;
  el.periodeStart_ = () => start;
  el.settings_ = { devices: batterijen, battery_state: [] };
  const roles = { solar: zon ? ["sensor.zon"] : [], import: ["sensor.af"], export: ["sensor.terug"], gas: [], water: [] };
  const { fetchPeriod, fetchBattery, combine } = await import("../custom_components/domotiapp_coach/frontend/src/statistics.js");
  const ids = [...roles.solar, ...roles.import, ...roles.export];
  const [series, accu, herk] = await Promise.all([
    fetchPeriod(hass, ids, periode, start),
    fetchBattery(hass, batterijen, periode, start),
    el.laadHerkomst_(roles, batterijen, start),
  ]);
  el.accu_ = accu;
  el.herkomst_ = herk;
  el.rows_ = { solar: combine(series, roles.solar), import: combine(series, roles.import), export: combine(series, roles.export), gas: [], water: [] };
  const rows = el.buckets_();
  const som = (key) => rows.reduce((t, r) => t + (r[key] ?? 0), 0);
  const used = som("used");
  return {
    el, rows, herk, vragen, eind: periodEnd(periode, start),
    totaal: {
      solar: zon ? som("solar") : null,
      used,
      zonZelf: Math.max(0, som("zonZelfSom")),
      eigen: som("ownUse"),
      zelfvoorzienend: used > 0 ? Math.max(0, (1 - som("fromGrid") / used) * 100) : null,
    },
  };
}

const ACCU_TELLER = { id: "a", type: "thuisbatterij", entities: { energy_in: "sensor.a_in", energy_out: "sensor.a_uit", soc: "sensor.a_soc" }, battery: { capacity_kwh: 10 } };
const ACCU_GROWATT = { id: "g", type: "thuisbatterij", entities: { charge_power: "sensor.g_in_w", discharge_power: "sensor.g_uit_w", soc: "sensor.g_soc" }, battery: { capacity_kwh: 5 } };
const ACCU_TEKEN = { id: "s", type: "thuisbatterij", entity: "sensor.s_w", entities: {}, battery: { capacity_kwh: 8 } };
const H = (d, h) => new Date(d.getFullYear(), d.getMonth(), d.getDate(), h).getTime();
const rond = (x, n = 3) => Math.round(x * 10 ** n) / 10 ** n;

proef("zelfvoorzienend: 's nachts van het net geladen en 's ochtends ontladen is 0 %, en teruglevering uit de batterij is geen opwek (v0.144.0)", async () => {
  // De schermafdruk van 22-10-2026, 08:45: 10,3 van het net, 9,1 geladen tussen 03 en
  // 05, 174 Wh ontladen, 4 Wh naar het net, geen zon. Stond er 12 % en Opgewekt 4 Wh.
  const dag = new Date(2026, 9, 22);
  const uren = [];
  for (let h = 0; h < 9; h += 1) {
    const u = { t: H(dag, h), zon: 0, af: 0.15, terug: 0 };
    if (h === 3 || h === 4) Object.assign(u, { af: 4.55 + 0.15, a: { erin: 4.55, eruit: 0, soc: 50 } });
    else if (h >= 5) Object.assign(u, { af: 0.25, a: { erin: 0, eruit: 0.0435 + (h === 8 ? 0.004 : 0), soc: 90 } });
    else u.a = { erin: 0, eruit: 0, soc: 50 };
    if (h === 8) u.terug = 0.004;
    uren.push(u);
  }
  const { totaal, rows } = await herkomstHuis({ uren, batterijen: [ACCU_TELLER], start: dag });
  assert.equal(rond(totaal.zelfvoorzienend, 6), 0, JSON.stringify(totaal));
  assert.equal(rond(totaal.solar), 0, "geen zon, geen opwek");
  assert.equal(rond(totaal.zonZelf), 0);
  assert.ok(Math.abs(totaal.used - (9 * 0.15 + 4 * 0.1 + 0.174)) < 1e-6, `verbruikt ${totaal.used}`);
  const { stapel } = await import("../custom_components/domotiapp_coach/frontend/src/views/history.js");
  for (const r of rows) assert.equal(rond(stapel(r).boven[1][1], 6), 0, "uit de batterij staat bij van het net");
  // Het rapport en het aanwijzen per vak rekenen met dezelfde velden.
  const bron = Historie.toString();
  assert.ok(bron.includes("kwh(row.solar), kwh(row.used), kwh(row.zonZelf)"));
  assert.ok(bron.includes('Math.max(0, sum("zonZelfSom"))') && bron.includes('kwh(Math.max(0, som("zonZelfSom")))'));
  assert.ok(bron.includes("solar: row.solar,") && bron.includes("(row.zonZelf / row.solar)"));
  assert.ok(bron.includes('solar: hasSolar ? sum("solar") : null'));
});

proef("zelfvoorzienend: zon in de batterij die 's avonds ontladen wordt telt mee, half zon is half (v0.144.0)", async () => {
  const dag = new Date(2026, 9, 20);
  const uren = [];
  for (let h = 0; h < 24; h += 1) {
    const u = { t: H(dag, h), zon: 0, af: 0, terug: 0, a: { erin: 0, eruit: 0, soc: 40 } };
    // Middag: 3 zon, 0,5 naar het huis, 2 de batterij in, 0,5 naar het net.
    if (h >= 11 && h < 14) Object.assign(u, { zon: 3, terug: 0.5, a: { erin: 2, eruit: 0, soc: 60 } });
    // Avond: 1 per uur uit de batterij naar het huis.
    if (h >= 18 && h < 24) Object.assign(u, { a: { erin: 0, eruit: 1, soc: 40 } });
    uren.push(u);
  }
  const { totaal, rows } = await herkomstHuis({ uren, batterijen: [ACCU_TELLER], start: dag });
  // Verbruikt: 3 × 0,5 overdag plus 6 uit de batterij. Alles is zon.
  assert.ok(Math.abs(totaal.used - 7.5) < 1e-9, `${totaal.used}`);
  assert.equal(rond(totaal.zelfvoorzienend), 100);
  assert.equal(rond(totaal.solar), 9);
  assert.equal(rond(totaal.zonZelf), 7.5, "wat de batterij in ging is zon zelf gebruikt");
  assert.equal(rond(rows[18].accuEigen), 1, "in de grafiek staat het als uit de batterij");

  // Dezelfde batterij, maar 's nachts eerst 6 van het net erin: half zon, half net.
  const gemengd = uren.map((u) => ({ ...u, a: { ...u.a } }));
  gemengd[2] = { ...gemengd[2], af: 6, a: { erin: 6, eruit: 0, soc: 60 } };
  const twee = await herkomstHuis({ uren: gemengd, batterijen: [ACCU_TELLER], start: dag });
  // 6 net en 6 zon, 6 eruit: 3 zon. Eigen is 1,5 direct plus 3.
  assert.ok(Math.abs(twee.totaal.eigen - 4.5) < 1e-6, `${twee.totaal.eigen}`);
});

proef("zelfvoorzienend: wat de vorige dag van het net in de batterij ging telt de volgende dag als net, ook over een week (v0.144.0)", async () => {
  const zondag = new Date(2026, 9, 18);
  const maandag = new Date(2026, 9, 19);
  const uren = [];
  // Zondagnacht 22-24: 8 van het net erin.
  for (const h of [22, 23]) uren.push({ t: H(zondag, h), af: 4, a: { erin: 4, eruit: 0, soc: 50 } });
  // Maandag: geen zon, 's ochtends 0,5 per uur uit de batterij.
  for (let h = 6; h < 12; h += 1) uren.push({ t: H(maandag, h), af: 0, a: { erin: 0, eruit: 0.5, soc: 80 } });
  const dag = await herkomstHuis({ uren, batterijen: [ACCU_TELLER], start: maandag });
  assert.equal(rond(dag.totaal.zelfvoorzienend, 6), 0, "de dag zelf");
  // De week die op maandag begint, en de maand: zelfde antwoord.
  const week = await herkomstHuis({ uren, batterijen: [ACCU_TELLER], start: maandag, periode: "week" });
  assert.equal(rond(week.totaal.zelfvoorzienend, 6), 0, "de week");
  assert.equal(week.rows.length, 1, "één vak van een dag");
  // Om de aanloop: de recorder wordt per uur gevraagd vanaf twee dagen eerder.
  const perUur = dag.vragen.filter((v) => v.period === "hour" && v.types[0] === "change");
  assert.ok(perUur.some((v) => v.statistic_ids.includes("sensor.af") && new Date(v.start_time) <= new Date(maandag.getTime() - 47 * 3600000)), "aanloop");
  // Zonder aanloop zou het 100 % zijn geweest (zo stond het voor v0.144.0).
  const { huisMetAccu } = await import("../custom_components/domotiapp_coach/frontend/src/views/history.js");
  const oud = huisMetAccu(0, 0, { battery: -3, voor: 0 });
  assert.equal(oud.ownUse, 3);
});

proef("zelfvoorzienend: handelen, een lege batterij, gaten, en de capaciteit (v0.144.0)", async () => {
  const { herkomst } = await import("../custom_components/domotiapp_coach/frontend/src/views/history.js");
  const u = (start, x) => ({ start, ...x });
  // Handelen: 's nachts 5 van het net erin, om 19:00 4 eruit naar het net en 0,5 naar
  // het huis. Teruglevering zonder zon is geen zon naar het net, en niets is eigen.
  let r = herkomst([u(1, { bought: 5, erin: 5 }), u(19, { sold: 4, eruit: 4.5 })]);
  assert.deepEqual(r.get(19), { opwek: 0, zonHuis: 0, accuZon: 0, zonNet: 0, zonAccuNet: 0 });
  // Meer terug dan zon en batterij samen: de opwekmeter miste iets (een omvormer die er
  // later bij kwam). Dat deel is zon, zoals Opgewekt het zonder batterij ook telt.
  r = herkomst([u(1, { solar: 0, sold: 3, bought: 1, eruit: 0.5 })]);
  assert.equal(rond(r.get(1).opwek), 2.5);
  assert.equal(rond(r.get(1).zonNet), 2.5);
  // Meldde de opwekmeter dat uur wel iets, dan is het verschil ruis en geen opwek (v0.144.2).
  r = herkomst([u(1, { solar: 1, sold: 1.2, bought: 0.3, eruit: 0.1, zonGemeten: true })]);
  assert.equal(rond(r.get(1).opwek), 1);
  assert.equal(rond(r.get(1).zonNet), 1);
  // Zon in de batterij, verkocht om 20:00: geen zon naar het net dat uur (er is geen zon).
  r = herkomst([u(12, { solar: 4, erin: 4 }), u(20, { sold: 3, eruit: 3.5 })]);
  assert.equal(r.get(20).zonNet, 0);
  assert.equal(rond(r.get(20).accuZon), 0.5, "wat het huis kreeg was zon");
  assert.equal(rond(r.get(20).zonAccuNet), 3, "en wat naar het net ging ook: dat is niet zelf gebruikt");
  // Leeg: eerst 5 net erin, dan leeg (alles eruit), daarna zon erin en eruit: dat is zon.
  r = herkomst([
    u(1, { bought: 5, erin: 5 }),
    u(2, { eruit: 4 }),
    u(3, { leeg: true }),
    u(12, { solar: 2, erin: 2 }),
    u(20, { eruit: 2 }),
  ]);
  assert.equal(rond(r.get(20).accuZon), 2, "na leeg alleen de zon");
  // Zonder de lege batterij zou er 1 kWh net blijven hangen: 2 van 3 is zon.
  r = herkomst([u(1, { bought: 5, erin: 5 }), u(2, { eruit: 4 }), u(12, { solar: 2, erin: 2 }), u(20, { eruit: 2 })]);
  assert.equal(rond(r.get(20).accuZon), rond(4 / 3));
  // Een gat: uren zonder gegevens houden de inhoud zoals hij was.
  r = herkomst([u(12, { solar: 3, erin: 3 }), u(40, { eruit: 1 })]);
  assert.equal(rond(r.get(40).accuZon), 1);
  // Eruit zonder dat er iets bekend in zat telt als net.
  r = herkomst([u(5, { eruit: 1 })]);
  assert.equal(r.get(5).accuZon, 0);
  // De capaciteit: het verlies valt naar verhouding weg, de verhouding blijft.
  r = herkomst([u(1, { bought: 10, erin: 10 }), u(12, { solar: 10, erin: 10 }), u(20, { eruit: 4 })], { capaciteit: 10 });
  assert.equal(rond(r.get(20).accuZon), 2, "half zon, half net");
});

proef("zelfvoorzienend: de batterij laadt eerst uit zon, eigen is per uur nooit meer dan voor v0.144.0, en handelen is geen zon zelf gebruikt (v0.144.1)", async () => {
  const { herkomst, huisMetAccu } = await import("../custom_components/domotiapp_coach/frontend/src/views/history.js");
  // Een klantwoning op 22-10-2026 om 11:00: zon 6,0, af 0,5, terug 0,1, de batterij in 1,6.
  // De batterij laadt uit zon, het huis kreeg het netdeel; zoals het energiedashboard.
  const r = herkomst([{ start: 11, solar: 6, bought: 0.5, sold: 0.1, erin: 1.6 }]).get(11);
  assert.equal(rond(r.zonHuis), 4.3);
  const oud = huisMetAccu(6 - 0.1, 0.5, { battery: 1.6, voor: 0 });
  assert.equal(rond(r.zonHuis + r.accuZon), rond(oud.ownUse));
  // Willekeurige dagen zonder teruglevering uit de batterij: per uur nooit meer eigen
  // dan zoals Historie het voor v0.144.0 telde (`huisMetAccu` zonder herkomst).
  let zaad = 7;
  const kans = () => ((zaad = (zaad * 16807) % 2147483647) / 2147483647);
  for (let dag = 0; dag < 50; dag += 1) {
    const uren = [];
    for (let h = 0; h < 48; h += 1) {
      const solar = h % 24 >= 8 && h % 24 < 18 ? kans() * 5 : 0;
      const huis = 0.2 + kans() * 2;
      const erin = kans() < 0.4 ? kans() * 3 : 0;
      const eruit = erin === 0 && kans() < 0.5 ? kans() * 2 : 0;
      const netto = huis + erin - eruit - solar;
      uren.push({ start: h, solar, erin, eruit, bought: Math.max(0, netto), sold: Math.max(0, -netto) });
    }
    const herk = herkomst(uren, { capaciteit: 10 });
    for (const x of uren) {
      const oudUur = huisMetAccu(Math.max(0, x.solar - x.sold), x.bought, { battery: x.erin - x.eruit, voor: 0 });
      const nu = huisMetAccu(x.solar - x.sold, x.bought, { battery: x.erin - x.eruit, voor: 0 }, herk.get(x.start));
      assert.ok(nu.ownUse <= oudUur.ownUse + 1e-9, `dag ${dag} uur ${x.start}: ${nu.ownUse} > ${oudUur.ownUse}`);
    }
  }
  // Handelen: zon die de batterij in ging en 's avonds naar het net, is niet zelf gebruikt.
  const dag = new Date(2026, 9, 20);
  const uren = [];
  for (let h = 0; h < 24; h += 1) {
    const x = { t: H(dag, h), zon: 0, af: 0.2, terug: 0, a: { erin: 0, eruit: 0, soc: 50 } };
    if (h >= 11 && h < 13) Object.assign(x, { zon: 3, af: 0, a: { erin: 2.8, eruit: 0, soc: 70 } });
    if (h === 20) Object.assign(x, { af: 0, terug: 4, a: { erin: 0, eruit: 4.2, soc: 30 } });
    uren.push(x);
  }
  const { totaal } = await herkomstHuis({ uren, batterijen: [ACCU_TELLER], start: dag });
  // 6 opgewekt: 0,4 meteen het huis in, 5,6 de batterij in; daarvan 0,2 naar het huis en 4 naar het net.
  assert.equal(rond(totaal.solar), 6);
  assert.equal(rond(totaal.zonZelf), 2, "6 min de 4 die via de batterij terugging");
});

proef("zelfvoorzienend: twee batterijen, een zonder tellers en een met, en de lege batterij uit de accustand (v0.144.0)", async () => {
  const dag = new Date(2026, 9, 21);
  const uren = [];
  for (let h = 0; h < 24; h += 1) {
    const x = { t: H(dag, h), zon: 0, af: 0.1, terug: 0, a: { erin: 0, eruit: 0, soc: 50 }, s: { erin: 0, eruit: 0 } };
    // 's Nachts laadt de batterij met tellers van het net, die met een vermogenssensor (alleen uitlezen) niet.
    if (h === 2) Object.assign(x, { af: 4.1, a: { erin: 4, eruit: 0, soc: 90 } });
    // De ochtend: de batterij met tellers gaat leeg tot de bodem van 10 %.
    if (h >= 6 && h < 10) Object.assign(x, { af: 0, a: { erin: 0, eruit: 1, soc: h === 9 ? 10 : 50 } });
    // Middag: zon in de batterij met een vermogenssensor.
    if (h >= 12 && h < 14) Object.assign(x, { zon: 2, s: { erin: 1.9, eruit: 0 } });
    // Avond: die geeft het weer af.
    if (h >= 19 && h < 21) Object.assign(x, { af: 0, s: { erin: 0, eruit: 1.9 } });
    uren.push(x);
  }
  const { totaal } = await herkomstHuis({ uren, batterijen: [ACCU_TELLER, ACCU_TEKEN], start: dag });
  // Zon direct: 2 × 0,1. Uit de batterijen naar het huis: 4 (net, 's ochtends) en 3,8 's avonds.
  // Zonder accustand voor de tweede batterij weet de coach niet wanneer alles leeg was, dus
  // zijn de 3,8 kWh van de avond een mengsel: 3,8 zon bij 0 net over (de ochtend nam de 4 net).
  assert.ok(Math.abs(totaal.eigen - (0.2 + 3.8)) < 1e-6, `${totaal.eigen}`);
  assert.ok(Math.abs(totaal.used - 9.8) < 1e-6, `${totaal.used}`);
  // Een Growatt met losse sensoren voor laden en ontladen, zonder teller van het net
  // naar de batterij: zelfde uitkomst als met tellers.
  const growatt = uren.map((x) => ({ ...x, g: x.a, a: undefined }));
  const g = await herkomstHuis({ uren: growatt, batterijen: [ACCU_GROWATT, ACCU_TEKEN], start: dag });
  assert.ok(Math.abs(g.totaal.eigen - totaal.eigen) < 1e-6, `${g.totaal.eigen}`);
  // De lege batterij uit de accustand: 5 van het net erin, 4 eruit en dan op de bodem
  // (het verlies), daarna 2 zon erin en eruit. Dat is helemaal zon, niet 2 van 3.
  const leeg = [];
  for (let h = 0; h < 24; h += 1) {
    const x = { t: H(dag, h), af: 0, a: { erin: 0, eruit: 0, soc: 60 } };
    if (h === 2) Object.assign(x, { af: 5, a: { erin: 5, eruit: 0, soc: 90 } });
    if (h >= 6 && h < 10) x.a = { erin: 0, eruit: 1, soc: h === 9 ? 10 : 50 };
    if (h === 10) x.a = { erin: 0, eruit: 0, soc: 10 };
    if (h === 12) Object.assign(x, { zon: 2, a: { erin: 2, eruit: 0, soc: 40 } });
    if (h === 20) x.a = { erin: 0, eruit: 2, soc: 20 };
    leeg.push(x);
  }
  const l = await herkomstHuis({ uren: leeg, batterijen: [ACCU_TELLER], start: dag });
  assert.equal(rond(l.herk.get(H(dag, 20)).accuZon), 2, "na de bodem alleen de zon");
  // Komt de batterij niet laag (nooit onder een kwart), dan is hij nooit leeg geweest.
  const hoog = leeg.map((x) => ({ ...x, a: { ...x.a, soc: Math.max(40, x.a.soc) } }));
  const h2 = await herkomstHuis({ uren: hoog, batterijen: [ACCU_TELLER], start: dag });
  assert.equal(rond(h2.herk.get(H(dag, 20)).accuZon), rond(4 / 3));
  const el = Object.create(Historie.prototype);
  assert.equal(await el.laadHerkomst_({ solar: [], import: [], export: [] }, [], dag), null, "zonder batterij geen herkomst");
});

proef("zelfvoorzienend: zonder batterij verandert er niets, en zonder zon staat er geen opwek (v0.144.0)", async () => {
  const dag = new Date(2026, 9, 21);
  const uren = [];
  for (let h = 0; h < 24; h += 1) uren.push({ t: H(dag, h), zon: h >= 10 && h < 16 ? 2 : 0, af: h >= 10 && h < 16 ? 0 : 0.4, terug: h >= 10 && h < 16 ? 1.5 : 0 });
  const zonder = await herkomstHuis({ uren, batterijen: [], start: dag });
  assert.equal(zonder.herk, null);
  // Zoals voor v0.144.0: eigen is zon min teruggeleverd, per vak.
  assert.equal(rond(zonder.totaal.eigen), 3);
  assert.equal(rond(zonder.totaal.solar), 12);
  assert.equal(rond(zonder.totaal.zelfvoorzienend, 2), rond((3 / (3 + 18 * 0.4)) * 100, 2));
  for (const r of zonder.rows) assert.equal(r.accuEigen, undefined);
  for (const r of zonder.rows) assert.equal(r.solar, r.own + r.sold, "Opgewekt zoals voor v0.144.0");
  const zonderMeter = await herkomstHuis({ uren: uren.map((x) => ({ ...x, zon: 0 })), batterijen: [], start: dag });
  assert.equal(rond(zonderMeter.totaal.solar), 9, "geen opwekmeter: wat terugging blijft opwek, zoals altijd");
  // Week, maand en jaar zonder batterij: dezelfde som per vak.
  for (const periode of ["week", "month", "year"]) {
    const p = await herkomstHuis({ uren, batterijen: [], start: dag, periode });
    assert.equal(rond(p.totaal.eigen), 3, periode);
  }
  // Geen zonnepanelen, wel een batterij die van het net laadt: nul procent, geen opwek.
  const netAccu = [];
  for (let h = 0; h < 24; h += 1) netAccu.push({ t: H(dag, h), af: h < 4 ? 2.5 : 0.1, a: { erin: h < 4 ? 2 : 0, eruit: h >= 17 && h < 21 ? 1 : 0, soc: 50 } });
  const geenZon = await herkomstHuis({ uren: netAccu, batterijen: [ACCU_TELLER], start: dag, zon: false });
  assert.equal(geenZon.totaal.solar, null);
  // Een opwekmeter die er pas later bij kwam: in de uren zonder meting is wat terugging
  // (en niet uit de batterij kwam) zon; in de uren met meting telt alleen de meter.
  const later = [];
  for (let h = 0; h < 24; h += 1) {
    const x = { t: H(dag, h), af: 0.2, a: { erin: 0, eruit: 0, soc: 50 } };
    if (h >= 10 && h < 12) Object.assign(x, { terug: 1 });
    if (h >= 13 && h < 15) Object.assign(x, { zon: 1, terug: 1.05, af: 0.25 });
    later.push(x);
  }
  for (const x of later) if (x.t < H(dag, 13)) delete x.zon;
  const l = await herkomstHuis({ uren: later, batterijen: [ACCU_TELLER], start: dag });
  assert.equal(rond(l.totaal.solar), 4, "2 zonder meter uit wat terugging, 2 van de meter");
  assert.equal(rond(geenZon.totaal.eigen, 6), 0);
});

// --- per apparaat in Historie (v0.121.0) -------------------------------------------
//
// De eigenaar op 15-10-2026: "ik wil ook het energieverbruik per apparaat kunnen zien in
// historie zoals het HA energy dashboard snap je? En dat per dag per jaar etc moet op die
// pagina's er bij komen."

proef("per apparaat: een schatting uit het vermogen komt per uur, en een dag die loopt telt alleen zijn uren", async () => {
  const { fetchDevices, periodStart } = await import("../custom_components/domotiapp_coach/frontend/src/statistics.js");
  const vragen = [];
  const nu = new Date();
  const vandaag = new Date(nu); vandaag.setHours(0, 0, 0, 0);
  const gisteren = new Date(vandaag); gisteren.setDate(gisteren.getDate() - 1);
  const hass = {
    callWS: async (msg) => {
      vragen.push(msg);
      if (msg.types[0] === "change") return { "sensor.vriezer_kwh": [{ start: gisteren.getTime(), change: 1.2 }] };
      return { "sensor.was_w": [{ start: gisteren.getTime(), mean: 100 }, { start: vandaag.getTime(), mean: 100 }] };
    },
  };
  const apparaten = [{ id: "v", energy: "sensor.vriezer_kwh", power: "sensor.v_w" }, { id: "w", energy: "", power: "sensor.was_w" }];

  await fetchDevices(hass, apparaten, "month", periodStart("month", 0));
  assert.equal(vragen.find((v) => v.types[0] === "change").period, "day", "een teller per vak van de grafiek");
  assert.equal(vragen.find((v) => v.types[0] === "mean").period, "hour", "een vermogen per uur");

  vragen.length = 0;
  const jaar = await fetchDevices(hass, apparaten, "year", periodStart("year", 0));
  assert.equal(vragen.find((v) => v.types[0] === "change").period, "month");
  assert.equal(vragen.find((v) => v.types[0] === "mean").period, "day", "over een jaar per dag");
  const was = jaar.get("w");
  assert.equal(was.exact, false);
  assert.equal(was.rows.get(gisteren.getTime()), 2.4, "een hele dag: 100 W maal 24 uur");
  const uren = Math.max(0, Math.floor((Date.now() - vandaag.getTime()) / 3600000));
  assert.ok(Math.abs(was.rows.get(vandaag.getTime()) - (100 * uren) / 1000) < 1e-9, "vandaag alleen de uren die voorbij zijn, geen 24");
  assert.equal(jaar.get("v").exact, true);
  assert.equal(jaar.get("v").rows.get(gisteren.getTime()), 1.2);
});

proef("per apparaat: rijen per uur vallen in hun vak, en wat erbuiten valt telt niet", async () => {
  await import("../custom_components/domotiapp_coach/frontend/src/views/history.js");
  const { perVak } = await import("../custom_components/domotiapp_coach/frontend/src/views/history.js");
  const dag = 86400000;
  const tijden = [0, dag, 2 * dag];
  const rijen = new Map([[0, 1], [3600000, 2], [dag + 7200000, 4], [2 * dag, 8], [3 * dag, 16], [-3600000, 32]]);
  assert.deepEqual(perVak(rijen, tijden, 3 * dag), [3, 4, 8]);
  assert.deepEqual(perVak(new Map(), tijden, 3 * dag), [0, 0, 0]);
  assert.deepEqual(perVak(undefined, tijden, 3 * dag), [0, 0, 0]);
});

proef("per apparaat: geen batterij, een vaste kleur op de volgorde van Apparaten, vanaf de zevende grijs", async () => {
  const { apparaatReeksen } = await import("../custom_components/domotiapp_coach/frontend/src/views/history.js");
  const tijden = [0, 3600000];
  const apparaat = (id, extra = {}) => ({ id, type: "overig", name: `App ${id}`, entity: `sensor.${id}`, ...extra });
  const devices = [
    apparaat("a"), { id: "accu", type: "thuisbatterij", entity: "sensor.accu" }, apparaat("b"), apparaat("c"),
    apparaat("d"), apparaat("e"), apparaat("f"), apparaat("g"), apparaat("h"), apparaat("zonder", { entity: "" }),
  ];
  const stats = new Map([
    ["accu", { rows: new Map([[0, 5]]), exact: false }],
    ["a", { rows: new Map([[0, 1], [3600000, -0.5]]), exact: true }],
    ["c", { rows: new Map([[0, 2]]), exact: false }],
    ["d", { rows: new Map([[0, 0.001]]), exact: true }],
    ["g", { rows: new Map([[0, 0.3]]), exact: true }],
    ["h", { rows: new Map([[3600000, 0.2]]), exact: false }],
  ]);
  const reeksen = apparaatReeksen(devices, stats, tijden, 7200000);
  assert.ok(!reeksen.some((r) => r.id === "accu"), "de batterij verbruikt niet");
  assert.deepEqual(reeksen.map((r) => [r.id, r.kleur]), [["a", 1], ["c", 3], ["__overig__", "rest"]],
    "b zonder gegevens houdt zijn plek, d is te weinig, g en h zijn de zevende en achtste");
  assert.deepEqual(reeksen[0].vakken, [1, 0], "een vak onder nul telt als nul");
  const overig = reeksen.at(-1);
  assert.equal(overig.label, "Overige apparaten");
  assert.deepEqual(overig.vakken, [0.3, 0.2]);
  assert.equal(overig.exact, false, "een geschatte erin maakt het geheel geschat");
  assert.equal(reeksen[1].label, "App c");
  // Een andere periode met andere gegevens verandert de kleur van c niet.
  const later = apparaatReeksen(devices, new Map([["c", { rows: new Map([[0, 9]]), exact: true }]]), tijden, 7200000);
  assert.deepEqual(later.map((r) => [r.id, r.kleur]), [["c", 3]]);
});

proef("per apparaat: de lijst met kWh, het deel van het huis, en de rest van het huis", async () => {
  const el = Object.create(Historie.prototype);
  const lijst = nepEl("ul");
  lijst.klassen = new Set();
  lijst.classList = { toggle: (k, aan) => (aan ? lijst.klassen.add(k) : lijst.klassen.delete(k)) };
  const vak = { "#apparaten-lijst": lijst, "#apparaten-note": nepEl("p") };
  el.$ = (sel) => vak[sel];
  el.appReeksen_ = [
    { id: "p", label: "Laadpaal", kleur: 1, vakken: [6, 4], totaal: 10, exact: true },
    { id: "w", label: "Wasmachine", kleur: 2, vakken: [0, 1.5], totaal: 1.5, exact: false },
  ];
  el.appHuis_ = [10, 10];
  metNepDocument(() => el.paintAppLijst_(null));
  const rijen = () => lijst.kinderen.map((li) => li.kinderen.map((k) => k.textContent));
  assert.deepEqual(rijen(), [
    ["", "Laadpaal", "10,0 kWh", "50%"],
    ["", "Wasmachine", "≈ 1,50 kWh", "8%"],
    ["", "Rest van het huis", "8,50 kWh", "43%"],
  ]);
  assert.equal(lijst.kinderen[2].className, "rest");
  assert.ok(!lijst.klassen.has("zonder-deel"));
  assert.match(vak["#apparaten-note"].textContent, /≈ is geschat uit het vermogen/);

  metNepDocument(() => el.paintAppLijst_(0));
  assert.deepEqual(rijen(), [["", "Laadpaal", "6,00 kWh", "60%"], ["", "Rest van het huis", "4,00 kWh", "40%"]],
    "één vak: alleen wat daarin verbruikte");

  // Schattingen boven het huis: geen deel, geen rest, en de zin zegt waarom.
  el.appHuis_ = [5, 5];
  metNepDocument(() => el.paintAppLijst_(null));
  assert.deepEqual(rijen(), [["", "Laadpaal", "10,0 kWh", ""], ["", "Wasmachine", "≈ 1,50 kWh", ""]]);
  assert.ok(lijst.klassen.has("zonder-deel"));
  assert.match(vak["#apparaten-note"].textContent, /boven wat het huis verbruikte/);

  // Zonder opwekteller weet Historie niet wat het huis verbruikte: alleen kWh.
  el.appHuis_ = null;
  metNepDocument(() => el.paintAppLijst_(null));
  assert.equal(rijen().length, 2);
  assert.ok(!/boven wat het huis/.test(vak["#apparaten-note"].textContent));

  const html = Object.create(Historie.prototype).render();
  assert.ok(html.includes('id="apparaten-card" hidden') && html.includes("Per apparaat"), "de kaart staat in Historie");
});

// --- Growatt: alleen uitlezen (v0.123.0) -------------------------------------------
//
// De eigenaar op 15-10-2026: "nee sturen niet voor growatt alleen uitlezen", en "dat ik
// dus alleen invulvelden krijg die noodzakelijk zijn voor growatt".
proef("Growatt: alleen de velden om uit te lezen, en niets om te sturen (v0.123.0)", async () => {
  const devs = await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  const accu = { id: "g", type: "thuisbatterij", brand: "growatt", name: "", entity: "", entities: {}, controllable: false, battery: {} };
  assert.deepEqual(devs.brandFields(accu).map((f) => f.key), ["soc", "charge_power", "discharge_power", "accu_in", "accu_out"]);
  assert.ok(!devs.brandFields(accu).some((f) => f.needed), "geen veld met 'nodig zodra de coach mag sturen'");
  assert.equal(devs.isReadOnly(accu), true);
  assert.equal(devs.canSteer(accu), false, "een Growatt is niet te sturen");
  assert.deepEqual(devs.missingForControl({ ...accu, controllable: true }), [], "en mist dus ook niets om te sturen");
  assert.equal(devs.isReadOnly({ ...accu, brand: "anker" }), false);

  // Dezelfde lijst als const.py.
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/const.py", import.meta.url), "utf8");
  const blok = bron.slice(bron.indexOf("BATTERIJ_ALLEEN_LEZEN: Final = ("));
  const python = [...blok.slice(0, blok.indexOf(")")).matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
  assert.deepEqual(python, devs.BATTERY_BRANDS.filter((b) => b.readOnly).map((b) => b.id));

  await import("../custom_components/domotiapp_coach/frontend/src/views/devices.js");
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.feed_ = {};
  el.draft_ = { devices: [accu] };
  const html = el.brandHtml_(accu, 0);
  for (const key of ["soc", "charge_power", "discharge_power", "accu_in", "accu_out"]) {
    assert.ok(html.includes(`data-entity-key="${key}"`), `het veld ${key}`);
  }
  for (const key of ["setpoint", "direction", "mode", "charge_limit", "discharge_limit", "temperature", "fan", "energy_in", "energy_out", "capacity"]) {
    assert.ok(!html.includes(`data-entity-key="${key}"`), `geen veld ${key}`);
  }
  assert.ok(!html.includes("data-power"), "geen vermogenssensor met een teken");
  assert.ok(!html.includes("Nodig zodra de coach mag sturen"));
  assert.match(html, /Een Growatt leest de coach alleen uit/, "het merk zegt het");

  const vink = el.controlHtml_({ ...accu, controllable: true }, 0);
  assert.ok(!vink.includes('data-field="controllable"'), "geen vinkje om te sturen");
  assert.match(vink, /alleen uit/);

  const blokHtml = el.batteryHtml_(accu, 0);
  assert.ok(blokHtml.includes('data-bat-field="capacity_kwh"'), "de capaciteit als getal");
  for (const veld of ["rte_percent", "max_charge_w", "max_discharge_w", "phase", "power_invert", "setpoint_invert", "control_mode", "idle_mode", "self_zero"]) {
    assert.ok(!blokHtml.includes(`data-bat-field="${veld}"`), `geen ${veld}`);
  }
  assert.ok(!blokHtml.includes("onder Instellen"), "en geen verwijzing naar de instellingen van de bewoner");
  assert.equal(el.summary_(accu).text, "Growatt · alleen uitlezen");

  // Een Anker houdt alles.
  const anker = el.batteryHtml_({ ...accu, brand: "anker" }, 0);
  assert.ok(anker.includes('data-bat-field="self_zero"') && anker.includes('data-bat-field="max_charge_w"'));
  assert.ok(el.brandHtml_({ ...accu, brand: "anker" }, 0).includes("data-power"));
});

proef("Growatt: van een ander merk naar Growatt laat niets staan om te sturen (v0.123.0)", async () => {
  const { alleenUitlezen } = await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  const was = {
    id: "g", type: "thuisbatterij", brand: "growatt", controllable: true, entity: "sensor.accu_w",
    entities: { soc: "sensor.soc", setpoint: "number.accu", energy_in: "sensor.in", accu_in: "sensor.accu_in" },
  };
  const nu = alleenUitlezen(was);
  assert.equal(nu.controllable, false);
  assert.equal(nu.entity, "", "de vermogenssensor met een teken gaat eraf, want die gaat bij de coach voor");
  assert.deepEqual(nu.entities, { soc: "sensor.soc", accu_in: "sensor.accu_in" });
  const anker = { ...was, brand: "anker" };
  assert.equal(alleenUitlezen(anker), anker, "een ander merk blijft zoals het is");
});

proef("Growatt: de accustand gekozen, de rest van hetzelfde apparaat vanzelf (v0.123.0)", async () => {
  const { growattVanzelf } = await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  // Zoals hass.entities ze geeft: per entiteit device_id, platform en translation_key.
  const rij = (id, tk, toestel = "d1", platform = "growatt_server") => [id, { entity_id: id, device_id: toestel, platform, translation_key: tk }];
  const mix = Object.fromEntries([
    rij("sensor.a_soc", "mix_statement_of_charge"),
    rij("sensor.a_laden", "mix_battery_charge"),
    rij("sensor.a_ontladen_w", "mix_battery_discharge_w"),
    rij("sensor.a_ontladen_kw", "mix_battery_discharge_kw"),
    rij("sensor.a_in_vandaag", "mix_battery_charge_today"),
    rij("sensor.a_in", "mix_battery_charge_lifetime"),
    rij("sensor.a_uit_vandaag", "mix_battery_discharge_today"),
    rij("sensor.a_uit", "mix_battery_discharge_lifetime"),
    // Een tweede omvormer met dezelfde sleutels hoort er niet bij.
    rij("sensor.b_laden", "mix_battery_charge", "d2"),
  ]);
  const accu = { type: "thuisbatterij", brand: "growatt", entities: { soc: "sensor.a_soc" } };
  assert.deepEqual(growattVanzelf(accu, mix), {
    charge_power: "sensor.a_laden",
    discharge_power: "sensor.a_ontladen_kw",
    accu_in: "sensor.a_in",
    accu_out: "sensor.a_uit",
  }, "een MIX: het ontladen in kW, en de tellers voor levenslang");

  // Een SPH heeft geen ontladen in kW.
  const sph = { ...mix };
  delete sph["sensor.a_ontladen_kw"];
  assert.equal(growattVanzelf(accu, sph).discharge_power, "sensor.a_ontladen_w");

  // Wat er al staat blijft staan.
  const half = { ...accu, entities: { soc: "sensor.a_soc", charge_power: "sensor.eigen" } };
  assert.equal(growattVanzelf(half, mix).charge_power, undefined);

  // Een accustand van iets anders dan de Growatt-integratie: niets.
  const ander = { ...mix, "sensor.x_soc": { entity_id: "sensor.x_soc", device_id: "d1", platform: "template" } };
  assert.deepEqual(growattVanzelf({ ...accu, entities: { soc: "sensor.x_soc" } }, ander), {});
  assert.deepEqual(growattVanzelf(accu, undefined), {}, "zonder register ook niets");
});

proef("Growatt: laden en ontladen in kW op de energiestroom, en het rendement uit zijn tellers (v0.123.0)", () => {
  const staten = {
    "sensor.g_soc": { state: "68", attributes: { unit_of_measurement: "%" } },
    "sensor.g_laden": { state: "0", attributes: { unit_of_measurement: "kW" } },
    "sensor.g_ontladen": { state: "5.4", attributes: { unit_of_measurement: "kW" } },
  };
  const accu = {
    id: "g", type: "thuisbatterij", brand: "growatt", entity: "", controllable: false, battery: { capacity_kwh: 15.3 },
    entities: { soc: "sensor.g_soc", charge_power: "sensor.g_laden", discharge_power: "sensor.g_ontladen" },
  };
  const r = new LiveSource().sample({ get: (id) => staten[id] }, {
    sources: {}, devices: [accu], battery_state: [{ device: "g", rte_accu: 0.9015 }],
  });
  assert.equal(r.devices[0].batteryWatts, -5400, "5,4 kW ontladen is 5400 W eruit");
  assert.equal(r.devices[0].details.find((d) => d.label === "Rendement")?.text, "ongeveer 90%, gemeten in de accu");
});

// --- Miele: wasmachine en droger (v0.124.0) -----------------------------------------
//
// De eigenaar op 15-10-2026: "Ik wil dat de coach wel weer de apparaten aanmaakt:
// Wasmachine droger en vriezer", en "Starten, zoals vaatwasser", met Miele en Overig.
proef("wasmachine en droger zijn er weer, met Miele en Overig, dezelfde lijst als const.py (v0.124.0)", async () => {
  const devs = await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  for (const soort of ["wasmachine", "droger"]) {
    assert.ok(devs.DEVICE_TYPES.some((t) => t.id === soort), `${soort} is een type`);
    assert.deepEqual(devs.brandsFor(soort).map((b) => b.id), ["miele", "overig"], `${soort}: Miele en Overig`);
    assert.ok(devs.PROGRAM_TYPES.includes(soort) && devs.RELEASE_TYPES.includes(soort));
  }
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/const.py", import.meta.url), "utf8");
  const lijst = (naam) => {
    const blok = bron.slice(bron.indexOf(`${naam}: Final = [`));
    return [...blok.slice(0, blok.indexOf("]")).matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
  };
  assert.deepEqual(lijst("WASMACHINE_BRANDS"), devs.WASMACHINE_BRANDS.map((b) => b.id));
  const programmaTypes = bron.match(/PROGRAMMA_TYPES = \(([^)]*)\)/)[1].match(/"([a-z]+)"/g).map((s) => s.slice(1, -1));
  assert.deepEqual(programmaTypes, devs.PROGRAM_TYPES, "PROGRAMMA_TYPES in const.py en PROGRAM_TYPES in devices.js");
});

// Tot v0.124.0 stond Mitsubishi Electric alleen in het paneel, en weigerde de coach een
// airco met dat merk bij het opslaan. Elk merk dat het paneel aanbiedt moet in ALL_BRANDS.
proef("elk merk dat het paneel aanbiedt neemt de coach aan bij het opslaan (v0.124.0)", async () => {
  const devs = await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/const.py", import.meta.url), "utf8");
  const python = new Set();
  for (const blok of bron.matchAll(/^[A-Z_]+_BRANDS: Final = \[([\s\S]*?)\]/gm)) {
    for (const m of blok[1].matchAll(/"([a-z_]+)"/g)) python.add(m[1]);
  }
  const alle = ["laadpaal", "vaatwasser", "wasmachine", "droger", "vriezer", "koelkast", "thuisbatterij", "airco"]
    .flatMap((soort) => devs.brandsFor(soort).map((b) => `${soort}:${b.id}`));
  const mist = alle.filter((naam) => !python.has(naam.split(":")[1]));
  assert.deepEqual(mist, [], `niet in const.py: ${mist.join(", ")}`);
  assert.ok(/ALL_BRANDS: Final = sorted\(\s*\{[^}]*\*AIRCO_BRANDS/.test(bron), "AIRCO_BRANDS zit in ALL_BRANDS");
});

// Terugleverkosten in vier vormen en Historie per afrekenperiode (v0.135.0). De eigenaar op
// 19-10-2026: "ik wil het zo goed mogelijk hebben". De regels zijn die van prijsopbouw.py
// (test_prijsopbouw.py) en `async_afrekening` in coach.py (proef 176 in test_coach.py).
proef("terugleverkosten in vier vormen, en Historie per afrekenperiode (v0.135.0)", async () => {
  const g = await import("../custom_components/domotiapp_coach/frontend/src/geld.js");
  const v = { feed_in_costs: 0.05 };
  assert.equal(g.kostenPerKwh(v, true), 0.05);
  assert.equal(g.kostenPerKwh({ ...v, feed_in_costs_mode: "overschot" }, true), 0);
  assert.equal(g.kostenPerKwh({ ...v, feed_in_costs_mode: "overschot" }, false), 0.05);
  assert.equal(g.kostenPerKwh({ ...v, feed_in_costs_mode: "schalen" }, false), 0);
  assert.equal(g.kostenPerKwh({ ...v, feed_in_costs_mode: "geen" }, false), 0);
  const schalen = [{ vanaf: 500, per_jaar: 70 }, { vanaf: 0, per_jaar: 0 }, { vanaf: 750, per_jaar: 140 }];
  assert.deepEqual([g.schaalPerJaar(schalen, 499.9), g.schaalPerJaar(schalen, 500), g.schaalPerJaar(schalen, 6800), g.schaalPerJaar([], 1)],
    [0, 70, 140, null], "dezelfde schaal als schaal_per_jaar in prijsopbouw.py");
  // Per afrekenperiode: 75% saldeert, de rest krijgt de vergoeding na saldering.
  const afrekening = {
    perioden: [{ van: "2026-04-01", tot: "2027-01-01", gesaldeerd: 0.75 }, { van: "2025-04-01", tot: "2026-04-01", gesaldeerd: null }],
    schaal: { van: "2026-09-15", tot: "2027-01-01", per_jaar: 73, per_dag: 0.2, kwh: 600 },
  };
  assert.equal(g.aandeelOp(afrekening, new Date(2026, 9, 19, 12)), 0.75);
  assert.equal(g.aandeelOp(afrekening, new Date(2025, 9, 19, 12)), null, "een periode zonder metingen: het vinkje");
  assert.equal(g.aandeelOp(null, new Date(2026, 9, 19)), null);
  const vast = { type: "fixed", netting: true, fixed: { all_in_price: 0.25, feed_in_tariff: 0.12, feed_in_costs: 0.05 } };
  const p = g.prijsOp(vast, { buy: 0.25, feedIn: null }, new Map(), new Date(2026, 9, 19, 12), null, 3600000, 0.75);
  assert.ok(Math.abs(p.terug - (0.75 * 0.20 + 0.25 * 0.07)) < 1e-12, `vast: 75% inkoopprijs min kosten, 25% vergoeding min kosten: ${p.terug}`);
  const zonder = g.prijsOp(vast, { buy: 0.25, feedIn: null }, new Map(), new Date(2026, 9, 19, 12));
  assert.ok(Math.abs(zonder.terug - 0.20) < 1e-12, "zonder afrekening alles gesaldeerd, zoals tot nu");
  const overschot = g.prijsOp({ ...vast, fixed: { ...vast.fixed, feed_in_costs_mode: "overschot" } }, { buy: 0.25 }, new Map(),
    new Date(2026, 9, 19, 12), null, 3600000, 0.75);
  assert.ok(Math.abs(overschot.terug - (0.75 * 0.25 + 0.25 * 0.07)) < 1e-12, `alleen over het overschot: ${overschot.terug}`);
  // De schaal per dag, alleen over de dagen die al voorbij zijn.
  const kosten = g.schaalKosten(afrekening, new Date(2026, 9, 1), new Date(2026, 10, 1), new Date(2026, 9, 11));
  assert.ok(Math.abs(kosten - 10 * 0.2) < 1e-9, `tien dagen van 1 tot 11 oktober: ${kosten}`);
  assert.equal(g.schaalKosten({ schaal: null }, new Date(2026, 9, 1), new Date(2026, 10, 1)), 0);
  const b = g.balans({ rijen: [{ start: new Date(2026, 9, 2), bought: 1, own: 0, sold: 2 }], prijs: () => ({ koop: 0.25, terug: 0.2 }),
    contract: vast, vasteKosten: 2 });
  assert.ok(Math.abs(b.terug - (0.4 - 2)) < 1e-12 && b.vasteKosten === 2, "de schaal gaat van wat teruglevering opleverde af");
  // De opbouw zegt wat de vorm betekent, en Contract heeft de keuze en de tabel.
  const { kostenNoot } = await import("../custom_components/domotiapp_coach/frontend/src/opbouw.js");
  assert.match(kostenNoot({ kosten_vorm: "schalen" }), /vast bedrag per jaar, in schalen. Wat je schaal kost staat in Historie/);
  assert.equal(kostenNoot({ kosten_vorm: "kwh" }), "");
  const Contract = geregistreerd.get("dac-view-contract");
  const html = Object.create(Contract.prototype).render();
  for (const id of ["fx-kostvorm", "dyn-kostvorm", "fx-schalen", "fx-schalen-tot", "dyn-schalen-tot"]) assert.ok(html.includes(`id="${id}"`), id);
  const cat = await import("../custom_components/domotiapp_coach/frontend/src/leveranciers.js");
  assert.deepEqual(
    ["vattenfall", "budget-thuis", "energiedirect"].map((id) => cat.voorstel(id, "fixed")?.velden?.feed_in_costs_mode),
    ["schalen", "schalen", "schalen"], "de catalogus kent de schalen tot 2027");
  assert.equal(cat.voorstel("vattenfall", "fixed").velden.feed_in_scales_until, "2027-01-01");
  const hist = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/history.js", import.meta.url), "utf8");
  assert.ok(hist.includes('type: "domotiapp_coach/afrekening"') && hist.includes("aandeelOp(this.afrekening_, when)")
    && hist.includes("vasteKosten: schaalKosten(this.afrekening_, start, end)"));
});

// Salderen tot aan wat je afneemt (v0.133.3). De eigenaar op 19-10-2026, bij "Teruglevering
// (je saldeert: je inkoopprijs min de kosten) € 0,1890": "ik had verwacht dat mijn
// teruglevering is: 0,0721-0,052756". Levert het huis over een jaar meer terug dan het
// afneemt, dan zegt de opbouw dat, met de kWh van dat jaar erbij (proef 175 in test_coach.py).
proef("de opbouw zegt of je over je afrekenperiode netto teruglevert, en wat er na 1-1-2027 geldt (v0.134.0)", async () => {
  const { opbouwHtml, jaarNoot } = await import("../custom_components/domotiapp_coach/frontend/src/opbouw.js");
  const jaar = { van: "2026-04-01", afname: 1500, terug: 3200, afname_rest: 700, terug_rest: 200, compleet: true };
  const vast = { soort: "fixed", salderen: true, inkoop: 0.25, terug: 0.124, netto_terug: true, jaar, controle: { status: "vast" } };
  const html = opbouwHtml(vast);
  assert.ok(html.includes("Teruglevering (vergoeding min de kosten)") && !html.includes("je saldeert: je inkoopprijs"), html);
  assert.ok(html.includes("Sinds 1 april nam je 1.500 kWh af en leverde je 3.200 kWh terug")
    && html.includes("700 kWh afname en 200 kWh teruglevering bij")
    && html.includes("krijgt de vergoeding na saldering"), html);
  const afname = opbouwHtml({ ...vast, terug: 0.25, netto_terug: false,
    jaar: { van: "2026-09-15", afname: 350, terug: 170, afname_rest: 1300, terug_rest: 150, compleet: true } });
  assert.ok(afname.includes("je saldeert: je inkoopprijs min de kosten") && afname.includes("Sinds 15 september")
    && afname.includes("Alles wat je teruglevert valt dus weg tegen inkoop"), afname);
  assert.ok(jaarNoot({ ...vast, netto_terug: null, jaar: { ...jaar, compleet: false } }).includes("geen metingen van dezelfde weken vorig jaar"),
    "zonder vorig jaar zegt hij dat hij het niet weet");
  assert.equal(jaarNoot({ ...vast, jaar: null }), "", "zonder begindatum of meter geen noot");
  assert.equal(jaarNoot({ ...vast, salderen: false }), "", "zonder salderen niets uit te leggen");
  // Een vast contract dat over 1 januari 2027 heen loopt.
  const na = opbouwHtml({ ...vast, na_salderen: { vanaf: "2027-01-01", vergoeding: 0.0721, kosten: 0.052756, terug: 0.019344 } });
  assert.ok(na.includes("Teruglevering vanaf 1 januari 2027") && na.includes("€ 0,0721") && na.includes("€ 0,0528")
    && na.includes("€ 0,0193"), na);
  assert.ok(!html.includes("vanaf 1 januari 2027"), "zonder na salderen geen blok");
});

proef("Historie: een vast contract rekent na 1-1-2027 met wat het contract voor daarna zegt (v0.134.0)", () => {
  const twee = { ...VAST, fixed: { all_in_price: 0.24171, feed_in_tariff: 0.124, feed_in_costs: 0,
    feed_in_tariff_after: 0.0721, feed_in_costs_after: 0.052756 } };
  const voor = geld.prijsOp(twee, TARIEF, new Map(), new Date(2026, 9, 19, 12));
  assert.ok(Math.abs(voor.terug - 0.24171) < 1e-9, `met salderen de inkoopprijs min de kosten van nu: ${voor.terug}`);
  const buiten = geld.prijsOp({ ...twee, netting: false }, TARIEF, new Map(), new Date(2026, 9, 19, 12));
  assert.ok(Math.abs(buiten.terug - 0.124) < 1e-9, `zonder salderen de vergoeding van nu: ${buiten.terug}`);
  const na = geld.prijsOp(twee, TARIEF, new Map(), new Date(2027, 0, 1, 12));
  assert.ok(Math.abs(na.terug - (0.0721 - 0.052756)) < 1e-9, `${na.terug}`);
  const leeg = { ...twee, fixed: { ...twee.fixed, feed_in_tariff_after: null, feed_in_costs_after: "" } };
  assert.ok(Math.abs(geld.prijsOp(leeg, TARIEF, new Map(), new Date(2027, 0, 1, 12)).terug - 0.124) < 1e-9, "leeg houdt het bedrag van ervoor");
  const nul = { ...twee, fixed: { ...twee.fixed, feed_in_tariff_after: 0, feed_in_costs_after: 0 } };
  assert.equal(geld.prijsOp(nul, TARIEF, new Map(), new Date(2027, 0, 1, 12)).terug, 0, "nul is een bedrag, geen leeg veld");
  assert.deepEqual(geld.vasteTeruglevering(twee.fixed, new Date(2026, 11, 31, 23)), { vergoeding: 0.124, kosten: 0 });
  assert.deepEqual(geld.vasteTeruglevering(twee.fixed, new Date(2027, 0, 1, 0)), { vergoeding: 0.0721, kosten: 0.052756 });
});

// Prijskleuren naar de bekende prijzen (v0.133.1). De bewoner van de eerste woning op
// 19-10-2026: "relatief gezien naar de spread op de dag", en "Worden de nieuwe prijzen om
// 14u bekend, dan past ie zijn kleurstelling aan. Het kán dan zo zijn dat een kolom die
// om 13.59 nog groen was, rood wordt, omdat de prijzen morgen veel lager zijn."
proef("prijskleuren naar de bekende prijzen: groen blijft niet groen als morgen goedkoper is (v0.133.1)", async () => {
  const { prijsGrenzen, level } = await import("../custom_components/domotiapp_coach/frontend/src/format.js");
  const uur = (h) => new Date(2026, 9, 20, h);
  const rij = (h, prijs) => ({ start: uur(h), end: uur(h + 1), price: prijs });
  const vandaag = [rij(10, 0.50), rij(11, 0.40), rij(12, 0.38), rij(13, 0.45), rij(18, 0.47), rij(19, 0.46)];
  const nu = new Date(2026, 9, 20, 11, 30);
  // Vast: alles boven 0,30 is rood.
  assert.equal(level(0.38, prijsGrenzen({ low: 0.2, high: 0.3 }, vandaag, nu)(), true), "bad");
  // Naar de bekende prijzen: 0,38 is het goedkoopste van wat nog komt, dus groen.
  const relatief = prijsGrenzen({ low: 0.2, high: 0.3, relative: true }, vandaag, nu);
  assert.equal(level(0.38, relatief(), true), "good", JSON.stringify(relatief()));
  assert.equal(level(0.47, relatief(), true), "bad");
  assert.ok(Math.abs(relatief().low - (0.38 + 0.09 / 3)) < 1e-12, "het uur van 10:00 is voorbij en telt niet mee");
  // Om 14:00 komen de prijzen van morgen erbij, en die zijn veel lager: 0,38 wordt rood.
  const morgen = [...vandaag, ...[0.12, 0.10, 0.15, 0.20].map((p, i) => ({ start: new Date(2026, 9, 21, 1 + i), end: new Date(2026, 9, 21, 2 + i), price: p }))];
  const later = prijsGrenzen({ low: 0.2, high: 0.3, relative: true }, morgen, new Date(2026, 9, 20, 11, 30));
  assert.equal(level(0.38, later(), true), "bad", "naast een goedkope nacht is 0,38 duur");
  assert.equal(level(0.10, later(), true), "good");
  assert.deepEqual(prijsGrenzen({ low: 0.2, high: 0.3, relative: true }, [], nu)(), { low: 0.2, high: 0.3 }, "zonder prijzen de vaste grenzen");
  const vk = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/strategy.js", import.meta.url), "utf8");
  assert.ok(vk.includes('id="prijs-relatief"') && vk.includes("thresholds: { price: { relative: event.target.checked } }"));
  for (const bestand of ["vooruitblik.js", "components/price-chart.js", "views/overview.js"]) {
    const bron = readFileSync(new URL(`../custom_components/domotiapp_coach/frontend/src/${bestand}`, import.meta.url), "utf8");
    assert.ok(bron.includes("prijsGrenzen("), `${bestand} kleurt met prijsGrenzen`);
  }
});

// De vooruitblik op het overzicht (v0.133.0). De eigenaar op 19-10-2026: "Dan zie je in
// één oogopslag wat er toekomstig gaat gebeuren, en krijg je een visuele bevestiging of je
// ingestelde prioriteiten ook kloppen." De vorm van de gegevens is die van `vooruitblik`
// in coach.py (proef 174 in test_coach.py).
proef("de vooruitblik: per uur de prijs, de zon, het huis en elk plan, in de volgorde van de voorrang (v0.133.0)", async () => {
  const vb = await import("../custom_components/domotiapp_coach/frontend/src/vooruitblik.js");
  const data = {
    van: "2026-10-18T18:00:00", tot: "2026-10-18T22:00:00",
    prijzen: [
      { start: "2026-10-18T18:00:00", end: "2026-10-18T18:15:00", price: 0.40, feed_in: 0.30 },
      { start: "2026-10-18T18:15:00", end: "2026-10-18T19:00:00", price: 0.44, feed_in: 0.32 },
      { start: "2026-10-18T19:00:00", end: "2026-10-18T20:00:00", price: 0.46, feed_in: null },
    ],
    zon: { "2026-10-18T18:00:00": 0.4 }, huis: { "2026-10-18T18:00:00": 0.6, "2026-10-18T19:00:00": 0.8 },
    apparaten: [
      { id: "b", type: "thuisbatterij", blokken: [
        { start: "2026-10-18T18:00:00", end: "2026-10-18T18:30:00", kw: -1.0, wat: "Nul op de meter", soc: 61 },
        { start: "2026-10-18T18:30:00", end: "2026-10-18T19:00:00", kw: -2.0, wat: "Handelen", soc: 55 },
      ] },
      { id: "p", type: "laadpaal", blokken: [
        { start: "2026-10-18T18:00:00", end: "2026-10-18T19:00:00", kw: 0, wat: "wacht", why: "duurder dan nodig" },
        { start: "2026-10-18T21:00:00", end: "2026-10-18T22:00:00", kw: 11, zon_kw: 0, accu_kw: 1, wat: "laadt" },
      ] },
      { id: "v", type: "vaatwasser", blokken: [{ start: "2026-10-18T20:30:00", end: "2026-10-18T21:30:00", kw: null, wat: "start, Katoen" }] },
    ],
    voorrang_zon: ["p", "b"], voorrang_plan: ["b", "p"],
  };
  const uren = vb.vooruitUren(data);
  assert.equal(uren.length, 4, "18, 19, 20 en 21 uur");
  assert.ok(Math.abs(uren[0].prijs - (0.40 * 0.25 + 0.44 * 0.75)) < 1e-12, "het tijdgewogen gemiddelde van de kwartieren");
  assert.equal(uren[2].prijs, null, "een uur zonder prijs blijft zonder");
  assert.equal(uren[1].terug, null, "een terugleverprijs die er niet is ook");
  assert.equal(uren[0].zon, 0.4);
  assert.equal(uren[1].huis, 0.8);
  const accu = uren[0].apparaten.b;
  assert.ok(Math.abs(accu.kw - (-1.5)) < 1e-12 && accu.soc === 55, `de batterij: het gemiddelde vermogen en de accustand aan het eind: ${JSON.stringify(accu)}`);
  assert.equal(uren[2].apparaten.v.onbekend, true, "een onbekend verbruik blijft onbekend");
  assert.deepEqual(vb.volgorde(data), ["p", "b", "v"], "eerst de voorrang bij zon, dan bij planningen, dan de rest");
  const zichtbaar = { prijs: true, zon: true, huis: true, soc: true, p: true, b: true, v: true };
  const labels = new Map([["p", "Laadpaal"], ["b", "Thuisbatterij"], ["v", "Vaatwasser"]]);
  const soorten = new Map([["p", "laadpaal"], ["b", "thuisbatterij"], ["v", "vaatwasser"]]);
  const regels = vb.momentRegels(uren[0], { ids: vb.volgorde(data), labels, soorten, zichtbaar }).map((r) => r.tekst);
  assert.deepEqual(regels, ["Zon: 0,4 kW verwacht", "Huis: 0,6 kW verwacht", "Laadpaal: wacht, duurder dan nodig",
    "Thuisbatterij: Handelen, 1,5 kW eruit, naar 55%", "Vaatwasser: niets gepland"], JSON.stringify(regels));
  const later = vb.momentRegels(uren[3], { ids: vb.volgorde(data), labels, soorten, zichtbaar }).map((r) => r.tekst);
  assert.ok(later.includes("Laadpaal: laadt 11,0 kW (1,0 uit de batterij)"), JSON.stringify(later));
  assert.ok(vb.momentRegels(uren[2], { ids: ["v"], labels, soorten, zichtbaar }).some((r) => r.tekst === "Vaatwasser: start, Katoen"),
    "zonder verbruik geen kW");
  const zonderHuis = vb.momentRegels(uren[0], { ids: [], labels, soorten, zichtbaar: { ...zichtbaar, huis: false } }).map((r) => r.tekst);
  assert.ok(!zonderHuis.some((t) => t.startsWith("Huis")), "een uitgezette laag staat er niet");
  const s = vb.schalen(uren, { ids: vb.volgorde(data), zichtbaar });
  assert.ok(s.boven >= 11 && Math.abs(s.onder - 1.5) < 1e-12, JSON.stringify(s));
  const svg = vb.vooruitSvg(uren, { ids: vb.volgorde(data), soorten, zichtbaar, drempels: { low: 0.2, high: 0.3 }, gekozen: 1 });
  assert.ok(svg.includes('width="104"') && svg.includes('class="gekozen" x="26"'), "een kolom per uur");
  assert.ok(!svg.includes('class="soc"'), "een accustand van één uur is nog geen lijn");
  assert.ok(svg.includes("var(--dac-bad)"), "een prijs boven de grens in rood");
  // De kaart op het overzicht, direct onder de coach, ook voor wie de volgorde al eens veranderde.
  const store = {};
  globalThis.localStorage = { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v; }, removeItem: (k) => { delete store[k]; } };
  const layout = await import("../custom_components/domotiapp_coach/frontend/src/layout.js");
  assert.equal(layout.OVERVIEW_CARDS[1].id, "vooruit");
  store["dac-overview-layout"] = JSON.stringify([{ id: "flow" }, { id: "coach" }, { id: "tiles", hidden: true }]);
  assert.deepEqual(layout.effectiveLayout().map((c) => c.id), ["flow", "coach", "vooruit", "tiles", "phases", "meters", "steerable"],
    "een nieuwe kaart komt na zijn voorganger, niet achteraan");
  const ov = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf8");
  assert.ok(ov.includes('data-card="vooruit"') && ov.includes('type: "domotiapp_coach/forecast"'));
});

// "Wat gaat hij doen" voor de boiler en een apparaat met een programma (v0.133.0), zoals bij
// de laadpaal en de batterij. De eigenaar op 18-10-2026: "Zou bij zowel batterij, als ev
// laden, als boiler, etc op dezelfde manier weergegeven mogen worden."
proef("Wat gaat hij doen: de boiler en een programma in dezelfde prijsgrafiek (v0.133.0)", async () => {
  const { apparaatVooruit } = await import("../custom_components/domotiapp_coach/frontend/src/plan-ahead-sheet.js");
  const nu = new Date(2026, 9, 18, 18, 20);
  const rijen = [12, 13, 14, 21, 22, 23].map((h) => ({
    start: new Date(2026, 9, 18, h), end: new Date(2026, 9, 18, h + 1), price: h >= 21 ? 0.20 + (h - 21) * 0.01 : 0.40,
  }));
  const boiler = apparaatVooruit({ kind: "boiler", needed_kwh: 3.2, blokken: [
    { start: "2026-10-18T22:00:00", end: "2026-10-18T23:00:00", kwh: 2.0 },
    { start: "2026-10-18T23:00:00", end: "2026-10-19T00:00:00", kwh: 1.84 },
  ] }, rijen, nu);
  assert.deepEqual(boiler.kop.map((k) => k[1]), ["3,2 kWh", "2 blokken", "22:00"]);
  assert.equal(boiler.kop[2][2], "vandaag");
  assert.deepEqual(boiler.rijen.map((r) => r.groen), [false, true, true], "de uren van vandaag die nog komen, groen waar hij verwarmt");
  assert.equal(boiler.uren[0].tijd, "22:00 tot 23:00");
  assert.equal(boiler.uren[0].prijs, "€ 0,210");
  assert.equal(boiler.uren[0].wat, "verwarmt, 2,0 kWh");
  assert.equal(boiler.woorden.groen, "Verwarmen");
  const vw = apparaatVooruit({ kind: "programma", starts_at: "2026-10-18T21:30:00", program_minutes: 90, program_label: "Eco 50 °C" }, rijen, nu);
  assert.deepEqual(vw.kop.map((k) => k[1]), ["Eco 50 °C", "21:30", "rond 23:00"]);
  assert.deepEqual(vw.rijen.map((r) => r.groen), [true, true, false], "21 en 22 uur groen");
  assert.equal(vw.uren[0].wat, "start, Eco 50 °C");
  const loopt = apparaatVooruit({ kind: "programma", running: true, started_at: "2026-10-18T18:00:00", ends_at: "2026-10-18T19:10:00" }, [], nu);
  assert.equal(loopt.kop[1][0], "Begonnen");
  assert.equal(loopt.uren[0].wat, "draait");
  assert.equal(loopt.rijen.length, 0, "zonder prijzen geen grafiek, wel de vakken");
  const onbekend = apparaatVooruit({ kind: "programma", starts_at: "2026-10-19T09:00:00" }, rijen, nu);
  assert.equal(onbekend.kop[2][1], "onbekend", "zonder duur geen verzonnen eindtijd");
  assert.equal(onbekend.kop[1][2], "morgen");
  assert.equal(apparaatVooruit({ kind: "boiler", blokken: [] }, rijen, nu), null);
  assert.equal(apparaatVooruit({ kind: "airco" }, rijen, nu), null, "een airco heeft geen plan");
  const ov = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf8");
  assert.ok(ov.includes('besluit.kind === "boiler"\n        ? !(besluit.blokken ?? []).length') || ov.includes("!(besluit.blokken ?? []).length"));
});

// Het jaar in Historie met een startmaand (v0.132.0), zodat het met het contract
// gelijkloopt. Wat vandaag is hangt van de klok af, dus de proef rekent per maand na
// dat het jaar in die maand begint en vandaag erin valt.
proef("Historie: het jaar begint in de gekozen maand, en vandaag valt erin (v0.132.0)", async () => {
  const { periodStart, periodEnd, periodLabel } = await import("../custom_components/domotiapp_coach/frontend/src/statistics.js");
  const nu = new Date();
  for (let maand = 1; maand <= 12; maand++) {
    const van = periodStart("year", 0, maand);
    const tot = periodEnd("year", van);
    assert.equal(van.getMonth(), maand - 1, `begint in maand ${maand}`);
    assert.equal(van.getDate(), 1);
    assert.ok(van <= nu && nu < tot, `vandaag valt in het jaar vanaf maand ${maand}: ${van.toISOString()}`);
    const vorig = periodStart("year", -1, maand);
    assert.equal(vorig.getFullYear(), van.getFullYear() - 1, "een jaar terug");
  }
  assert.equal(periodStart("year", 0).getMonth(), 0, "zonder keuze januari, zoals altijd");
  assert.equal(periodLabel("year", new Date(2026, 6, 1)), "juli 2026 tot juni 2027");
  assert.equal(periodLabel("year", new Date(2026, 0, 1)), "2026", "een kalenderjaar blijft een jaartal");
  const vk = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/strategy.js", import.meta.url), "utf8");
  assert.ok(vk.includes('id="jaar-start"') && vk.includes("year_start_month: Number(event.target.value)"));
  const hist = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/history.js", import.meta.url), "utf8");
  assert.ok(!hist.includes("periodStart(this.period_, this.offset_)"), "elke periode in Historie gaat via periodeStart_");
});

// Teruglevering tegen een vast bedrag (v0.132.0): de opbouw toont het bedrag en de kosten.
proef("de opbouw van een vaste terugleververgoeding (v0.132.0)", async () => {
  const { opbouwHtml } = await import("../custom_components/domotiapp_coach/frontend/src/opbouw.js");
  const html = opbouwHtml({ soort: "dynamic", salderen: false, inkoop: { markt: 0.15, belasting: 0.09161, opslag: 0.02, subtotaal: 0.26161, btw_procent: 21, btw: 0.0549, totaal: 0.3165 },
    terug: { bedrag: 0.06, salderen: false, basis: 0.07, kosten: 0.01, vergoeding: 0, bonus: 0, vast: true },
    controle: { status: "onbekend", blokken: 0 } });
  assert.ok(html.includes("Vaste terugleververgoeding") && html.includes("0,0700") && html.includes("0,0600"), html);
  const terugDeel = html.slice(html.indexOf("Teruglevering nu"));
  assert.ok(!terugDeel.includes("Kale marktprijs") && terugDeel.includes("uit je contract"), "geen marktprijs in de teruglevering");
  const contract = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/contract.js", import.meta.url), "utf8");
  assert.ok(contract.includes('data-terug="fixed"') && contract.includes('id="dyn-feedfixed"'));
});

// De koelkast (v0.131.0): net als de vriezer uitlezen en melden, met een grens van
// 10 °C. De eigenaar op 19-10-2026: "boven de 10 graden".
proef("de koelkast: een soort naast de vriezer, Miele en Overig, alleen meldingen, 10 °C (v0.131.0)", async () => {
  const devs = await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  assert.ok(devs.DEVICE_TYPES.some((t) => t.id === "koelkast" && t.icon === "koelkast"));
  assert.deepEqual(devs.brandsFor("koelkast").map((b) => [b.id, b.readOnly]), [["miele", true], ["overig", true]]);
  const koel = { id: "k", type: "koelkast", brand: "miele", entities: {} };
  assert.equal(devs.isReadOnly(koel), true, "de coach stuurt hem niet");
  assert.ok(devs.brandMeta(koel).fields.find((f) => f.key === "temperature").hint.includes("warmer dan 10 °C"));
  assert.ok(devs.koelUitleg("koelkast").includes("de koelkast") && devs.koelUitleg("koelkast").includes("10 °C"));
  assert.ok(devs.koelUitleg("vriezer").includes("-15 °C"), "de vriezer houdt zijn grens");
  assert.equal(devs.koelUitleg("airco"), "");
  // Dezelfde soorten als const.py, in dezelfde volgorde, anders weigert het opslaan.
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/const.py", import.meta.url), "utf8");
  const blok = bron.slice(bron.indexOf("DEVICE_TYPES: Final = ["));
  const python = [...blok.slice(0, blok.indexOf("]")).matchAll(/^\s*"([a-z_]+)",/gm)].map((m) => m[1]);
  assert.deepEqual(devs.DEVICE_TYPES.map((t) => t.id), python, "DEVICE_TYPES in devices.js en const.py");
  const coach = readFileSync(new URL("../custom_components/domotiapp_coach/coach.py", import.meta.url), "utf8");
  assert.ok(coach.includes('"koelkast": ("de koelkast", KOELKAST_GRENS_C)') && coach.includes("KOELKAST_GRENS_C = 10.0"));
});

proef("Miele: de velden, de vrijgave, het programma op de machine en geen tabel vooraf (v0.124.0)", async () => {
  const devs = await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  const was = { id: "w", type: "wasmachine", brand: "miele", name: "", controllable: true, entity: "",
                energy_entity: "", entities: {} };
  const nodig = devs.brandEntityFields(was).filter((f) => f.needed).map((f) => f.key);
  assert.deepEqual(nodig, ["status", "program", "remaining", "start"]);
  assert.equal(devs.canSteer(was), true, "Miele drukt zelf op Starten");
  assert.equal(devs.canSkipRelease(was), true, "deur en startknop: deur dicht kan de vrijgave zijn");
  assert.equal(devs.releaseCopy(was).short, "Mag draaien", "geen 'Ingeruimd', net als de kaart van DomotiApp Lovelace");
  assert.equal(devs.releaseCopy({ type: "vaatwasser" }).short, "Ingeruimd");
  assert.deepEqual(devs.programPicker({ ...was, entities: { program: "sensor.w_programma" } }),
                   { kind: "machine", entityId: "sensor.w_programma" });
  assert.deepEqual(devs.defaultPrograms(was), [], "geen opgave van de fabrikant");
  assert.equal(devs.defaultPrograms({ type: "vaatwasser" }).length, devs.DISHWASHER_PROGRAMS.length);
  assert.equal(devs.isManualProgram({ ...was, brand: "overig" }), true, "Overig is op een meetstekker");
  assert.deepEqual(devs.programsFor({ ...was, brand: "overig" }), [], "ook zonder vaatwasserprogramma's");

  // Een gemeten Miele-programma: de naam en de duur uit de meting.
  const settings = { program_measured: [{ device: "w", key: "cottons", label: "Katoen", minutes: 95, kwh: 1.2, peak_w: 0, profile: [], runs: 2 }] };
  const prog = devs.programOf(was, "cottons", settings);
  assert.equal(prog?.label, "Katoen");
  assert.equal(prog?.minutes, 95);
  assert.equal(devs.programOf(was, "cottons_eco", settings), undefined, "een ander programma is niet gemeten");

  await import("../custom_components/domotiapp_coach/frontend/src/views/devices.js");
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.feed_ = {};
  el.draft_ = { devices: [was], program_measured: [] };
  let html = el.brandHtml_(was, 0);
  // De energieteller staat bij elk apparaat bovenaan; bij Miele zonder "(optioneel)".
  const teller = el.energyHtml_(was, 0);
  assert.ok(teller.includes("Energieteller</label>") && teller.includes("Een vermogenssensor heeft hij niet"),
            "bij Miele is de energieteller waar hij het verbruik uit telt");
  assert.ok(el.energyHtml_({ ...was, brand: "overig" }, 0).includes("Energieteller (optioneel)"));
  assert.ok(!html.includes("data-energy"), "niet nog een keer bij het merk");
  assert.ok(html.includes("Er is nog niets gemeten"), "geen tabel vooraf");
  assert.ok(!html.includes("Eco 50"), "geen vaatwasserprogramma's");
  el.draft_ = { devices: [was], ...settings };
  html = el.brandHtml_(was, 0);
  assert.ok(html.includes("Katoen") && html.includes("2 beurten") && html.includes('data-prog-forget="cottons"'),
            "een gemeten programma staat erin, te wissen");
  assert.ok(!html.includes("data-prog-add"), "niets toe te voegen: de machine noemt ze zelf");

  // Overig: een eigen tabel, leeg om mee te beginnen, zonder "Opgaven terugzetten".
  const dom = { ...was, brand: "overig", entity: "sensor.w_w", programs: [] };
  el.draft_ = { devices: [dom], program_measured: [] };
  html = el.brandHtml_(dom, 0);
  assert.ok(html.includes("data-prog-add") && html.includes("Voeg de programma's toe die je gebruikt"));
  assert.match(html, /data-prog-reset="0" hidden/);
});

proef("Miele: de kaart noemt het programma zoals Home Assistant het vertaalt (v0.124.0)", async () => {
  const was = { id: "w", type: "wasmachine", brand: "miele", name: "", controllable: true, entity: "",
                entities: { status: "sensor.w", program: "sensor.w_programma" } };
  const staten = {
    "sensor.w": { entity_id: "sensor.w", state: "programmed", attributes: {} },
    "sensor.w_programma": { entity_id: "sensor.w_programma", state: "cottons", attributes: {} },
  };
  const vertaald = { programmed: "Geprogrammeerd", cottons: "Katoen" };
  const feed = { get: (id) => staten[id], label: (id) => vertaald[staten[id]?.state] };
  const r = new LiveSource().sample(feed, { sources: {}, devices: [was] });
  const rij = (label) => r.devices[0].details.find((d) => d.label === label)?.text;
  assert.equal(rij("Programma"), "Katoen");
  assert.equal(rij("Status"), "Geprogrammeerd");
  // Zonder vertaling de waarde zelf, netjes.
  const kaal = new LiveSource().sample({ get: (id) => staten[id] }, { sources: {}, devices: [was] });
  assert.equal(kaal.devices[0].details.find((d) => d.label === "Programma")?.text, "Cottons");
});

proef("wasmachine: zonder vrijgave is deur dicht genoeg, met de woorden van een wasmachine (v0.124.0)", async () => {
  const { voorkeurHtml } = await import("../custom_components/domotiapp_coach/frontend/src/voorkeur-velden.js");
  const was = { id: "w", type: "wasmachine", brand: "miele", controllable: true, entities: {} };
  const html = voorkeurHtml(was);
  assert.ok(html.includes("Mag meedraaien") && html.includes("deur dicht") && html.includes("schone was"), "de woorden van een wasmachine");
  assert.ok(!html.includes("Ingeruimd") && !html.includes("vaat"));
  const vaat = voorkeurHtml({ id: "v", type: "vaatwasser", brand: "home_connect", controllable: true, entities: {} });
  assert.ok(vaat.includes("Ingeruimd en dicht") && vaat.includes("schone vaat"), "de vaatwasser houdt de zijne");
});

// --- de vriezer (v0.125.0) ------------------------------------------------------------
//
// De eigenaar op 15-10-2026: "Uitlezen en melden", niet sturen.
proef("de vriezer: Miele en Overig, temperatuur, deur en storing, en niets om te sturen (v0.125.0)", async () => {
  const devs = await import("../custom_components/domotiapp_coach/frontend/src/devices.js");
  assert.ok(devs.DEVICE_TYPES.some((t) => t.id === "vriezer"));
  assert.deepEqual(devs.brandsFor("vriezer").map((b) => b.id), ["miele", "overig"]);
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/const.py", import.meta.url), "utf8");
  const blok = bron.slice(bron.indexOf("VRIEZER_BRANDS: Final = ["));
  assert.deepEqual([...blok.slice(0, blok.indexOf("]")).matchAll(/"([a-z_]+)"/g)].map((m) => m[1]),
                   devs.VRIEZER_BRANDS.map((b) => b.id));
  const vriezer = { id: "v", type: "vriezer", brand: "miele", name: "", controllable: false, entity: "", entities: {} };
  assert.deepEqual(devs.brandFields(vriezer).map((f) => f.key), ["temperature", "door", "problem"]);
  assert.equal(devs.canSteer(vriezer), false);
  assert.equal(devs.isReadOnly(vriezer), true);
  assert.equal(devs.isReadOnly({ ...vriezer, brand: "overig" }), true);

  await import("../custom_components/domotiapp_coach/frontend/src/views/devices.js");
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.feed_ = {};
  el.draft_ = { devices: [vriezer] };
  const html = el.brandHtml_(vriezer, 0);
  assert.ok(html.includes('data-entity-key="temperature"') && html.includes('data-entity-key="door"')
            && html.includes('data-entity-key="problem"'));
  assert.ok(html.includes("data-power"), "een vriezer op een meetstekker mag zijn vermogen houden");
  const stuur = el.controlHtml_({ ...vriezer, controllable: true }, 0);
  assert.ok(!stuur.includes('data-field="controllable"') && stuur.includes("3 minuten") && stuur.includes("-15 °C"));
  assert.equal(el.summary_(vriezer).text, "Miele · meldingen");
  // Een Growatt houdt geen vermogenssensor.
  assert.ok(!el.brandHtml_({ ...vriezer, type: "thuisbatterij", brand: "growatt" }, 0).includes("data-power"));

  const staten = {
    "sensor.v_temp": { entity_id: "sensor.v_temp", state: "-18.25", attributes: { unit_of_measurement: "°C" } },
    "binary_sensor.v_deur": { entity_id: "binary_sensor.v_deur", state: "off", attributes: {} },
  };
  const r = new LiveSource().sample({ get: (id) => staten[id] }, {
    sources: {}, devices: [{ ...vriezer, entities: { temperature: "sensor.v_temp", door: "binary_sensor.v_deur" } }],
  });
  const rij = (label) => r.devices[0].details.find((d) => d.label === label)?.text;
  assert.equal(rij("Temperatuur"), "-18,3 °C");
  assert.equal(rij("Deur"), "Dicht");
});

// De eerste woning op 18-10-2026: handelen aan, in beide prijsvelden dezelfde all-in
// sensor en salderen uit. De coach kende de terugleverprijs niet en handelde nooit, en
// dat stond alleen in de kleine letters bij het marktveld (v0.128.2).
proef("handelen zonder terugleverprijs: het vinkje kan niet aan, en Contract zegt waarom (v0.128.2)", async () => {
  const dubbel = { type: "dynamic", netting: false,
    dynamic: { source: "all_in", all_in_entity: "sensor.prijs", market_entity: "sensor.prijs" } };
  const nu = new Date(2026, 9, 18, 18, 10);
  assert.equal(geld.terugleverBekend(dubbel, nu), false, "dezelfde sensor twee keer: onbekend");
  assert.equal(geld.terugleverBekend({ ...dubbel, netting: true }, nu), true, "met salderen volgt hij uit de inkoopprijs");
  assert.equal(geld.terugleverBekend({ ...dubbel, netting: true }, new Date(2027, 0, 2)), false, "maar na 2026 niet meer");
  assert.equal(geld.terugleverBekend({ ...dubbel, dynamic: { ...dubbel.dynamic, market_entity: "sensor.nordpool" } }, nu), true,
    "een andere marktprijssensor");
  assert.equal(geld.terugleverBekend({ ...dubbel, dynamic: { ...dubbel.dynamic, market_entity: "" } }, nu), false, "geen marktprijssensor");
  assert.equal(geld.terugleverBekend({ type: "dynamic", netting: false, dynamic: { source: "market", market_entity: "sensor.nordpool" } }, nu),
    true, "een zelf opgebouwde prijs heeft de marktprijs al");
  assert.equal(geld.terugleverBekend({ type: "fixed", netting: false, fixed: {} }, nu), true, "een vast contract heeft een vergoeding");
  // Een dynamische inkoop met een vaste terugleververgoeding (v0.132.0) is ook bekend,
  // en rekent zoals `terug` in prijsopbouw.py (test_prijsopbouw.py).
  const vastTerug = { ...dubbel, dynamic: { ...dubbel.dynamic, feed_in_mode: "fixed", feed_in_fixed: 0.07, feed_in_costs: 0.01 } };
  assert.equal(geld.terugleverBekend(vastTerug, nu), true, "een vaste terugleververgoeding");
  assert.ok(Math.abs(geld.terugOp(null, 0.40, vastTerug.dynamic, false, true) - 0.06) < 1e-12, "0,07 min 0,01");
  assert.ok(Math.abs(geld.terugOp(0.15, 0.40, { ...vastTerug.dynamic, supplier_markup: 0 }, true, true) - 0.39) < 1e-12,
    "binnen salderen de inkoopprijs min de kosten");

  const accu = { id: "b", type: "thuisbatterij", brand: "anker", name: "Anker", controllable: true, entities: {},
    battery: { ...defaultBattery("anker"), trade: false } };
  const velden = nepVelden(voorkeurHtml(accu));
  const handel = velden.veld("data-vk-accu", "trade");
  const melding = velden.rijen.find((r) => r.sleutel === "trade_kan_niet");
  assert.ok(handel && melding, "het vinkje en de melding staan in Instellen");
  vulVoorkeuren(velden, accu, null, dubbel);
  assert.equal(handel.disabled, true, "uit en geen terugleverprijs: aanzetten kan niet");
  assert.equal(melding.hidden, false, "en er staat waarom");
  vulVoorkeuren(velden, { ...accu, battery: { ...accu.battery, trade: true } }, null, dubbel);
  assert.equal(handel.checked, true);
  assert.equal(handel.disabled, false, "stond hij al aan, dan mag hij nog wel uit");
  assert.equal(melding.hidden, false, "met de melding erbij");
  vulVoorkeuren(velden, accu, null, { ...dubbel, netting: true });
  assert.equal(handel.disabled, false, "met een terugleverprijs is het vinkje vrij");
  assert.equal(melding.hidden, true, "en de melding weg");
  vulVoorkeuren(velden, accu);
  assert.equal(handel.disabled, false, "zonder contract erbij blijft het vinkje vrij");

  const html = Object.create(Contract.prototype).render();
  assert.ok(html.includes('id="dyn-same"') && html.includes('id="dyn-same-text"'), "Contract heeft een melding bij het marktveld");
  const el = Object.create(Contract.prototype);
  const nep = {};
  el.$ = (kiezer) => (nep[kiezer] ??= { style: {}, hidden: false, textContent: "", value: "",
    classList: { toggle() {} }, setAttribute() {} });
  el.$$ = () => [];
  el.draft_ = { contract: { ...dubbel, dynamic: { ...dubbel.dynamic } } };
  el.paintContract_();
  assert.equal(nep["#dyn-same"].hidden, false, "dezelfde sensor twee keer: de melding staat er");
  assert.match(nep["#dyn-same-text"].textContent, /niet handelen/, nep["#dyn-same-text"].textContent);
  el.draft_.contract.netting = true;
  el.paintContract_();
  assert.match(nep["#dyn-same-text"].textContent, /Zolang je saldeert/, "met salderen een andere zin");
  el.draft_.contract.dynamic.market_entity = "sensor.nordpool";
  el.paintContract_();
  assert.equal(nep["#dyn-same"].hidden, true, "een andere sensor: geen melding");
});

// De eigenaar op 18-10-2026, bij de grafiek van de batterij: "Deze laat nu alleen vandaag
// zien. Ik zou hem horizontaal scrollable/swipable maken", en "als ik op een bar klik in
// de diagram, wil ik de prijs zien van dat moment" (v0.129.0).
proef("de prijsgrafiek: morgen om middernacht, leveren in een eigen kleur, en breed genoeg om te vegen (v0.129.0)", async () => {
  const { prijsBalken } = await import("../custom_components/domotiapp_coach/frontend/src/prijsgrafiek.js");
  const begin = new Date(2026, 9, 18, 22, 0);
  const rijen = Array.from({ length: 30 }, (_, i) => {
    const s = new Date(begin.getTime() + i * 3600000);
    return { start: s.toISOString(), end: new Date(s.getTime() + 3600000).toISOString(), price: 0.3 + (i % 5) / 100,
      groen: i === 3, leveren: i === 10 || i === 3, kwh: i === 3 ? 1 : 0 };
  });
  const b = prijsBalken(rijen);
  const middernacht = b.balken.findIndex((x) => x.dagGrens);
  assert.equal(middernacht, 2, "om 00:00 begint morgen");
  assert.equal(b.balken[2].label, "morgen");
  assert.equal(b.balken.filter((x) => x.dagGrens).length, 2, "en de dag daarna ook een streep");
  assert.ok(b.balken[10].leveren && b.balken[10].tip.includes("ontladen aan het net"), b.balken[10].tip);
  assert.ok(b.balken[3].groen && !b.balken[3].leveren, "laden gaat voor leveren");
  assert.equal(b.minBreedte, 30 * 14, "14 px per uur");
  // De prijsas: ronde stappen van nul tot boven de hoogste prijs.
  const { prijsStappen, prijsUitleg } = await import("../custom_components/domotiapp_coach/frontend/src/prijsgrafiek.js");
  assert.deepEqual(prijsStappen(0, 0.469).stappen, [0, 0.1, 0.2, 0.3, 0.4, 0.5]);
  assert.deepEqual(prijsStappen(-0.03, 0.12).stappen, [-0.05, 0, 0.05, 0.1, 0.15]);
  assert.equal(b.stappen[0].waarde, 0);
  assert.ok(Math.abs(b.stappen[0].y - b.nul) < 1e-9, "de nul van de as is de nullijn");
  // De kaart: nu tegen het gemiddelde, een gekozen blok tegen nu, en wat hij dan doet.
  const nu = prijsUitleg(b, 0, { groen: "hij laadt", leveren: "hij levert aan het net", wacht: "hij wacht" });
  assert.ok(nu.kop.startsWith("Nu: ") && nu.prijs === "€ 0,300" && nu.onder.includes("onder het gemiddelde"), JSON.stringify(nu));
  const later = prijsUitleg(b, 4, { groen: "hij laadt", leveren: "hij levert aan het net", wacht: "hij wacht" });
  assert.ok(later.onder === "13% duurder dan nu, hij wacht", later.onder);
  assert.ok(prijsUitleg(b, 10, { leveren: "hij levert aan het net" }).onder.endsWith("hij levert aan het net"));
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/plan-ahead-sheet.js", import.meta.url), "utf8");
  assert.ok(bron.includes("Tik op een staafje"));
  // De woorden van de legenda bij een batterij (v0.130.0, de eerste woning op 19-10-2026).
  assert.ok(bron.includes('"Laden van het net"') && bron.includes('"Ontladen aan het net"') && bron.includes('"Nul op de meter"'));
  // Een blok met een eigen stand houdt die naam in de kaart, zoals "Standby".
  const eigen = prijsBalken(rijen.map((r, i) => ({ ...r, label: i === 5 ? "Standby" : "Nul op de meter" })));
  assert.ok(prijsUitleg(eigen, 5, { groen: "Laden van het net", wacht: "Nul op de meter" }).onder.endsWith("standby"));
  assert.ok(prijsUitleg(eigen, 6, { groen: "Laden van het net", wacht: "Nul op de meter" }).onder.endsWith("nul op de meter"));
  // De lijst eronder in dezelfde kleuren: oranje als hij aan het net levert.
  const { batterijVooruit } = await import("../custom_components/domotiapp_coach/frontend/src/battery.js");
  const plan = batterijVooruit({ hours: [
    { start: "2026-10-19T08:00:00", end: "2026-10-19T09:00:00", mode: "handelen", kwh: -2.5, grid_kwh: -2.15, soc: 54, price: 0.469 },
    { start: "2026-10-19T09:00:00", end: "2026-10-19T10:00:00", mode: "nul", kwh: -0.3, grid_kwh: 0, soc: 52, price: 0.446 },
    { start: "2026-10-19T03:00:00", end: "2026-10-19T04:00:00", mode: "netladen", kwh: 2, grid_kwh: 2, soc: 60, price: 0.30 },
  ], kind: "batterij", soc: 60, capacity_kwh: 14.6 });
  assert.deepEqual(plan.uren.map((u) => [u.levert, u.net]), [[true, false], [false, false], [false, true]]);
});

// De bewoner van de eerste woning op 18-10-2026: "Invullen, laten zien hoe de prijs tot
// stand is gekomen in woord én cijfers, en het all-in resultaat tonen", en "indien het
// resultaat overeen komt, krijg je automatisch de melding: de ingevoerde gegevens zijn
// correct" (v0.129.0).
proef("de opbouw in woorden en cijfers, in de volgorde van de leverancier, met de controle (v0.129.0)", async () => {
  const { opbouwHtml, controleZin, bevestigdZin } = await import("../custom_components/domotiapp_coach/frontend/src/opbouw.js");
  const check = {
    soort: "dynamic", salderen: false, bevestigd: false, bevestigd_op: null,
    blok: { start: "2026-10-18T21:00:00", einde: "2026-10-18T22:00:00" },
    bron: { all_in: "sensor.a", markt: "sensor.np", zelfde: false, interval: "hour", markt_minuten: 15 },
    inkoop: { markt: 0.22989, belasting: 0.09161, opslag: 0.016529, subtotaal: 0.338029, btw_procent: 21, btw: 0.070986,
      totaal: 0.409015, zonder_opslag: 0.3215, btw_zonder_opslag: 0.067515, opslag_met_btw: 0.02 },
    all_in: 0.4090149,
    terug: { bedrag: 0.298167, salderen: false, basis: 0.278167, opslag: 0, kosten: 0, vergoeding: 0.02, bonus: 0, met_btw: true },
    bonus_procent: 10, bonus_overdag: true, overdag: false,
    controle: { status: "correct", blokken: 24, stap_minuten: 60, grootste: 0.00001, vast: true },
  };
  const html = opbouwHtml(check, { opslag: "Inkoopvergoeding", bonus: "Zonnebonus", leverancier: "Zonneplan", opslagNaBtw: true });
  for (const woord of ["Kale marktprijs, gemiddelde van vier kwartieren", "Energiebelasting", "Inkoopvergoeding",
    "All-in", "Wat Zonneplan zegt", "€ 0,4090", "Zonnebonus 10%, alleen overdag: nu niet",
    "De ingevoerde gegevens zijn correct", "Niet te controleren: Zonneplan geeft de terugleverprijs niet door"]) {
    assert.ok(html.includes(woord), woord);
  }
  // Alles zonder btw, dan een regel btw, bij inkoop en teruglevering (v0.129.1, de eigenaar op
  // 19-10-2026: "Doe alles mét, of alles zónder btw").
  assert.ok(!html.includes("met btw"), "geen bedrag met btw tussen de bedragen zonder");
  assert.ok(html.indexOf("Energiebelasting") < html.indexOf("Inkoopvergoeding") && html.indexOf("Inkoopvergoeding") < html.indexOf("Btw 21%"),
    "de opslag zonder btw voor de btw-regel, ook als de leverancier hem met btw noemt");
  const terug = html.slice(html.indexOf("Teruglevering nu"));
  assert.ok(terug.includes("Kale marktprijs") && terug.includes("Samen, zonder btw") && terug.includes("Btw 21%"),
    "teruglevering in dezelfde vorm: de kale prijs, en de btw als eigen regel");
  assert.ok(terug.includes("€ 0,0165"), "de € 0,02 van Zonneplan zonder btw");
  const vol = opbouwHtml({ ...check, salderen: true, terug: { bedrag: 0.4090149, salderen: true, basis: 0.4090149, opslag: 0, kosten: 0,
    vergoeding: 0, bonus: 0, vol: true } }, { opslag: "Inkoopvergoeding", leverancier: "Zonneplan" });
  const volTerug = vol.slice(vol.indexOf("Teruglevering nu"));
  assert.ok(volTerug.includes("Energiebelasting, terug omdat je saldeert") && volTerug.includes("Inkoopvergoeding, ook terug"),
    "met salderen de energiebelasting en de opslag als eigen regel");
  const fout = controleZin({ ...check, controle: { status: "afwijking", grootste: -0.025, vast: true, stap_minuten: 60 } },
    { opslag: "Inkoopvergoeding", leverancier: "Zonneplan" });
  assert.equal(fout.toon, "fout");
  assert.ok(fout.tekst.includes("€ 0,0250 hoger") && fout.tekst.includes("energiebelasting"), fout.tekst);
  const zelfde = controleZin({ ...check, bron: { ...check.bron, zelfde: true }, controle: { status: "onbekend" } });
  assert.ok(zelfde.tekst.includes("dezelfde sensor"), zelfde.tekst);
  const vast = controleZin({ soort: "fixed" });
  assert.ok(vast.tekst.startsWith("Niet te controleren"), vast.tekst);
  assert.equal(bevestigdZin({ bevestigd: false, bevestigd_op: null }), "Nog niet bevestigd.");
  // Salderen uit voor 2027: de opbouw zegt dat het nog geldt (v0.129.1, de eerste woning op 19-10-2026).
  const { salderenNoot } = await import("../custom_components/domotiapp_coach/frontend/src/opbouw.js");
  assert.ok(salderenNoot({ salderen: false }, new Date(2026, 9, 19)).includes("Je levert nog gesaldeerd terug"));
  assert.equal(salderenNoot({ salderen: true }, new Date(2026, 9, 19)), "", "met salderen aan niets");
  assert.equal(salderenNoot({ salderen: false }, new Date(2027, 0, 2)), "", "na 2026 geldt het niet meer");
  assert.ok(html.includes("Je saldeert niet volgens de instellingen") || new Date() >= new Date(2027, 0, 1),
    "en het staat in het blok teruglevering");
  assert.ok(bevestigdZin({ bevestigd: true, bevestigd_op: "2026-10-18T21:41:00", bevestigd_door: "Bewoner" }).startsWith("Bevestigd door Bewoner op 18 oktober 2026"));
  assert.ok(bevestigdZin({ bevestigd: false, bevestigd_op: "2026-10-18T21:41:00" }).includes("opnieuw"));
});

proef("Contract per energiebron: soort, leverancier, looptijd, opbouw, bevestigen en een nieuw contract (v0.129.0)", () => {
  const html = Object.create(Contract.prototype).render();
  for (const id of ["stroom-soort", "stroom-lev", "stroom-start", "stroom-end", "opbouw", "bevestig", "gas-soort", "gas-lev",
    "gas-start", "gas-end", "gas-entity", "dyn-feedvat", "dyn-bonuspct", "dyn-bonusdag", "dyn-bonusbase"]) {
    assert.ok(html.includes(`id="${id}"`), id);
  }
  assert.ok(html.includes('data-soort="variable"'), "variabel staat er als soort");
  assert.ok(html.includes("Mijn contract loopt af op") && html.includes("Mijn huidige stroomcontract"));
  assert.ok(html.includes('data-nieuw="stroom"') && html.includes('data-nieuw="gas"'));
  // "Ik heb een nieuw contract afgesloten": het huidige bij de eerdere, en een leeg formulier.
  const el = Object.create(Contract.prototype);
  el.draft_ = { contract: { type: "fixed", supplier: "zonneplan", start: "2025-11-01", end: "2026-10-31",
    fixed: { all_in_price: 0.28, feed_in_tariff: 0.07, feed_in_costs: 0.01 }, dynamic: {}, periods: [],
    gas: { type: "fixed", price: 1.3, start: "2025-11-01", periods: [] } } };
  el.paint_ = () => {}; el.afterChange_ = () => {}; el.vraagControle_ = () => {};
  el.nieuwContract_("stroom");
  const c = el.draft_.contract;
  assert.equal(c.periods.length, 1);
  assert.equal(c.periods[0].from, "2025-11-01");
  assert.equal(c.periods[0].all_in_price, 0.28);
  assert.equal(c.periods[0].type, "fixed");
  assert.equal(c.periods[0].supplier, "zonneplan");
  // Een naam om zelf aan te passen (19-10-2026: "Zonneplan Elektra 2026").
  assert.ok(c.periods[0].name.startsWith("Zonneplan stroom, vast 01-11-2025 tot "), c.periods[0].name);
  assert.equal(c.supplier, "");
  assert.equal(c.fixed.all_in_price, 0);
  assert.equal(c.end, "");
  assert.ok(/^\d{4}-\d{2}-\d{2}$/.test(c.start), "het nieuwe contract gaat vandaag in");
  el.nieuwContract_("gas");
  assert.equal(c.gas.periods[0].price, 1.3);
  assert.ok(c.gas.periods[0].name.startsWith("gas, vast 01-11-2025 tot "), c.gas.periods[0].name);
  assert.equal(c.gas.price, 0);
});

proef("de catalogus: elk voorstel rust op een bron en een datum, en vult alleen bekende velden (v0.129.0)", async () => {
  const cat = await import("../custom_components/domotiapp_coach/frontend/src/leveranciers.js");
  const VELDEN = new Set(["supplier_markup", "feed_in_costs", "feed_in_bonus", "feed_in_vat", "feed_in_bonus_percent",
    "bonus_daytime", "bonus_base", "energy_tax", "vat_percent", "feed_in_tariff", "all_in_price", "price", "netting_full",
    // De vorm van de terugleverkosten (v0.135.0).
    "feed_in_costs_mode", "feed_in_scales_until"]);
  assert.ok(cat.LEVERANCIERS.length >= 1);
  const ids = new Set();
  for (const l of cat.LEVERANCIERS) {
    assert.ok(l.id && l.naam && /^\d{4}-\d{2}-\d{2}$/.test(l.peildatum), `${l.id}: id, naam en peildatum`);
    assert.ok(!ids.has(l.id), `${l.id} staat er twee keer in`);
    ids.add(l.id);
    for (const bron of ["stroom", "gas"]) {
      for (const [soort, deel] of Object.entries(l[bron] ?? {})) {
        assert.ok(["vast", "variabel", "dynamisch"].includes(soort), `${l.id} ${bron} ${soort}`);
        assert.ok(Array.isArray(deel.bronnen) && deel.bronnen.every((u) => /^https?:\/\//.test(u)), `${l.id} ${bron} ${soort}: bronnen`);
        for (const [veld, waarde] of Object.entries(deel.velden ?? {})) {
          assert.ok(VELDEN.has(veld), `${l.id} ${bron} ${soort}: onbekend veld ${veld}`);
          assert.ok(typeof waarde === "number" || typeof waarde === "boolean" || typeof waarde === "string", `${l.id}: ${veld}`);
        }
      }
    }
  }
  // Zonneplan: het eigen rekenvoorbeeld.
  const v = cat.voorstel("zonneplan", "dynamic", "stroom", 2026);
  assert.ok(Math.abs(v.velden.supplier_markup * 1.21 - 0.02) < 1e-5, "de € 0,02 met btw");
  assert.equal(v.velden.energy_tax, 0.09161, "de energiebelasting van dat jaar");
  assert.equal(cat.belastingStroom(2027), 0.08802);
  assert.ok(cat.BELASTING[2027].voorlopig, "2027 is nog voorlopig");
  assert.ok(cat.soortenVan("zonneplan", "stroom").includes("dynamic"));
  assert.equal(cat.sensorVan("zonneplan", { "sensor.zonneplan_current_electricity_tariff": {}, "sensor.x": {} }), "sensor.zonneplan_current_electricity_tariff");
  assert.equal(cat.nordPoolVan({ "sensor.nord_pool_nl_huidige_prijs": {} }), "sensor.nord_pool_nl_huidige_prijs");
});

// Sinds v0.130.1 op Contract, niet meer onder Voorkeuren. De eigenaar op
// 19-10-2026: "je energieprijs staat nu in voorkeuren maar dat moet onder
// contract", en bij "Kijk onder Voorkeuren": "voorkeuren ken ik niet".
proef("Contract toont de bewoner zijn prijs om te bevestigen, en het overzicht wijst erheen (v0.130.1)", async () => {
  await import("../custom_components/domotiapp_coach/frontend/src/views/strategy.js");
  const Voorkeuren = geregistreerd.get("dac-view-strategy");
  const vk = Object.create(Voorkeuren.prototype).render();
  assert.ok(!vk.includes('id="prijs"') && !vk.includes("Ja, dit klopt"), "niet meer onder Voorkeuren");
  const contractMod = await import("../custom_components/domotiapp_coach/frontend/src/views/contract.js");
  const Contract = geregistreerd.get("dac-view-contract");
  const html = Object.create(Contract.prototype).render();
  assert.ok(html.includes('class="primary vrij" id="bevestig"'), "Ja, dit klopt mag de bewoner zelf");
  assert.ok(html.includes('id="opbouw"') && html.includes("bewoner-uitleg"));
  // Wat de bewoner niet ziet: elke sensor en elk bedrag is van de installateur.
  const zonderInstallateur = html.replace(/<(div|label)[^>]*data-installateur[^>]*>[\s\S]*?<\/\1>/g, "");
  assert.ok(!/<dac-entity-picker/.test(html.split("data-installateur").slice(-1)[0]), "geen sensorkiezer na het laatste installateursblok");
  for (const id of ["dyn-allin", "dyn-market", "fx-price", "gas-entity", "water-price"]) {
    const plek = html.indexOf(`id="${id}"`);
    const ervoor = html.lastIndexOf("data-installateur", plek);
    assert.ok(plek > 0 && ervoor > 0, `${id} staat in een blok van de installateur`);
  }
  assert.ok(zonderInstallateur.length > 0);
  const css = Contract.css;
  assert.ok(css.includes(":host([readonly]) [data-installateur] { display: none !important; }"));
  const basis = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/editor-base.js", import.meta.url), "utf8");
  assert.ok(basis.includes(":not(.sheet-close):not(.vrij)"), "de leesstand laat een vrije knop met rust");
  // De eerdere contracten leest de bewoner als regels, zonder velden.
  const lezen = contractMod.periodesLezen("stroom", [
    { name: "Elektra 2025", from: "2025-01-01", to: "2025-12-31", type: "fixed", all_in_price: 0.31 },
    { name: "", from: "2026-01-01", to: "", type: "dynamic", supplier: "" },
  ]);
  assert.ok(lezen.includes("Elektra 2025") && lezen.includes("01-01-2025 tot 31-12-2025") && lezen.includes("€ 0,31 per kWh"), lezen);
  assert.ok(lezen.includes("Eerder contract") && lezen.includes("Dynamisch") && !lezen.includes("<input"), lezen);
  assert.ok(contractMod.periodesLezen("gas", []).includes("Geen eerdere contracten"));
  await import("../custom_components/domotiapp_coach/frontend/src/views/overview.js");
  const Overzicht = geregistreerd.get("dac-view-overview");
  const ov = Object.create(Overzicht.prototype).render();
  assert.ok(ov.includes('id="prijs-melding"') && ov.includes("Klopt je energieprijs?"));
  assert.ok(!ov.includes("</strong> Kijk onder") && ov.includes("</strong> Tik hier en zie hoe de coach hem opbouwt."), "geen tabblad in de tekst");
  const ovBron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf8");
  assert.ok(ovBron.includes('#prijs-melding").addEventListener("click", () => this.fire("dac-navigate", { id: "contract" })'));
  const ds = await import("../custom_components/domotiapp_coach/frontend/src/data-source.js");
  ds.zetCoachPrijzen({ bevestigd: false });
  assert.equal(ds.prijsBevestigd(), false);
  ds.zetCoachPrijzen({ bevestigd: true });
  assert.equal(ds.prijsBevestigd(), true);
  ds.zetCoachPrijzen({});
});

// Opgeleverd opnieuw uitrekenen onder de batterij (v0.130.1): eerst de som,
// dan Overnemen. Wat er staat komt van battery/recalculate (coach.py, proef 171).
proef("Apparaten: Opgeleverd opnieuw uitrekenen, eerst laten zien en dan overnemen (v0.130.1)", async () => {
  const mod = await import("../custom_components/domotiapp_coach/frontend/src/views/devices.js");
  const zin = mod.herrekenZin({ van: "2026-09-22", dagen: 27, kwartieren: 2592, zonder_prijs: 4, voor: 18.42, na: 9.87, toegepast: false, nordpool: true });
  assert.ok(zin.startsWith("Vanaf 22 september, 27 dagen: Opgeleverd was € 18,42, en wordt € 9,87."), zin);
  assert.ok(zin.includes("4 kwartieren hadden geen prijs") && zin.includes("Nord Pool") && !zin.includes("Overgenomen"), zin);
  assert.ok(mod.herrekenZin({ van: "2026-10-01", dagen: 1, voor: 1, na: 1, toegepast: true }).endsWith("Overgenomen."));
  assert.ok(mod.herrekenZin({ van: "2026-10-01", dagen: 1, voor: 1, na: 1 }).includes("statistiek van Home Assistant"));
  assert.equal(mod.herrekenZin({ fout: "Kies een dag in het verleden." }), "Kies een dag in het verleden.");
  assert.ok(mod.herrekenZin({ van: "2026-10-01", dagen: 0 }).includes("geen kwartieren"));
  const Apparaten = geregistreerd.get("dac-view-devices");
  const el = Object.create(Apparaten.prototype);
  el.herrekend_ = new Map();
  const leeg = el.herrekenHtml_({ id: "dev-b" }, 2);
  assert.ok(leeg.includes('data-herreken-van="2"') && leeg.includes('data-herreken="2"') && !leeg.includes("data-herreken-over"), "Overnemen pas na de som");
  el.herrekend_.set("dev-b", { van: "2026-09-22", uit: { van: "2026-09-22", dagen: 27, voor: 18.42, na: 9.87 } });
  assert.ok(el.herrekenHtml_({ id: "dev-b" }, 2).includes('data-herreken-over="2"'));
  el.herrekend_.set("dev-b", { van: "2026-09-22", uit: { van: "2026-09-22", dagen: 27, voor: 18.42, na: 9.87, toegepast: true } });
  assert.ok(!el.herrekenHtml_({ id: "dev-b" }, 2).includes("data-herreken-over"), "na Overnemen niet nog eens");
  const basis = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/editor-base.js", import.meta.url), "utf8");
  assert.ok(basis.includes('input[type="time"], input[type="date"], select {'), "een datumveld heeft de stijl van de andere velden");
});

proef("geld.js rekent teruglevering en de bonus zoals prijsopbouw.py (v0.129.0)", () => {
  const zp = { vat_percent: 21, feed_in_bonus: 0.02, feed_in_bonus_percent: 10, bonus_daytime: true, bonus_base: "market_plus_fee", feed_in_vat: true };
  assert.ok(Math.abs(geld.terugOp(0.08 / 1.21, null, zp, false, true) - 0.11) < 1e-9, "Zonneplan: € 0,08 + € 0,02 + 10%");
  assert.ok(Math.abs(geld.terugOp(0.08 / 1.21, null, zp, false, false) - 0.10) < 1e-9, "zonder bonus na zonsondergang");
  assert.equal(geld.bonusOp(-0.05, zp, true), 0, "niet als markt plus vergoeding negatief is");
  // Binnen salderen de hele all-in prijs terug (v0.129.1, Essent), zoals prijsopbouw.py.
  const es = { vat_percent: 21, supplier_markup: 0.02089, feed_in_bonus: -0.02089, netting_full: true };
  assert.equal(geld.terugOp(0.15, 0.40, es, true, false), 0.40);
  assert.ok(Math.abs(geld.terugOp(0.15, 0.40, es, false, false) - (0.15 - 0.02089)) < 1e-12);
  const zon = geld.zonOpOnder(new Date(Date.UTC(2026, 9, 18, 12)), 52.09, 5.12);
  const op = zon[0].getUTCHours() * 60 + zon[0].getUTCMinutes();
  assert.ok(Math.abs(op - (6 * 60 + 7)) <= 3, `zonsopkomst Utrecht 18-10-2026 rond 06:07 UTC, kreeg ${zon[0].toISOString()}`);
  const ligging = { lat: 52.09, lon: 5.12 };
  assert.ok(geld.overdag(new Date(Date.UTC(2026, 9, 18, 10)), new Date(Date.UTC(2026, 9, 18, 11)), ligging));
  assert.ok(!geld.overdag(new Date(Date.UTC(2026, 9, 18, 19)), new Date(Date.UTC(2026, 9, 18, 20)), ligging));
  // Historie per vak: de kale prijs uit de all-in prijs en de velden, en zonder salderen de bonus overdag.
  const contract = { type: "dynamic", netting: false, dynamic: { ...zp, source: "all_in", all_in_entity: "sensor.a",
    market_entity: "sensor.np", energy_tax: 0.09161, supplier_markup: 0.02 / 1.21 } };
  const middag = new Date(2026, 9, 18, 12);
  const koop = (0.15 + 0.09161) * 1.21 + 0.02;
  const p = geld.prijsOp(contract, { buy: null, feedIn: null }, new Map([[middag.getTime(), koop]]), middag, ligging);
  const verwacht = 0.15 * 1.21 + 0.02 + 0.1 * (0.15 * 1.21 + 0.02);
  assert.ok(Math.abs(p.terug - verwacht) < 1e-9, `${p.terug} tegen ${verwacht}`);
});

// De eigenaar op 18-10-2026: "ik wil een soort berichtenbox met zo'n 1tje wat optelt en dat
// je dat kan wegvinken van is gelezen", en "een invulveld voor herinnering meterstanden
// doorgeven" (v0.130.0).
proef("de berichtenbox: het tellertje, de lijst met Gelezen, en de herinnering voor de meterstanden (v0.130.0)", async () => {
  const b = await import("../custom_components/domotiapp_coach/frontend/src/berichten-sheet.js");
  const items = [
    { id: "1", at: "2026-10-19T08:00:00", kind: "meterstanden", title: "Geef je meterstanden door", body: "Ze staan op het overzicht.", read: false },
    { id: "2", at: "2026-10-12T08:00:00", kind: "contract", title: "Je stroomcontract loopt af op 10 november 2026", body: "Kijk of je verlengt.", read: true },
  ];
  assert.equal(b.ongelezen(items), 1);
  const nu = new Date(2026, 9, 19, 12, 0);
  assert.equal(b.wanneerTekst("2026-10-19T08:00:00", nu), "vandaag 08:00");
  assert.equal(b.wanneerTekst("2026-10-18T21:30:00", nu), "gisteren 21:30");
  assert.equal(b.wanneerTekst("2026-10-12T08:00:00", nu), "12 oktober");
  const html = b.berichtenHtml(items, nu);
  assert.ok(html.indexOf("Geef je meterstanden door") < html.indexOf("Je stroomcontract"), "nieuwste bovenaan");
  assert.equal(html.split("data-gelezen=").length - 1, 1, "alleen een ongelezen bericht heeft de knop Gelezen");
  assert.ok(html.includes('class="bericht gelezen"'), "een gelezen bericht ziet er anders uit");
  assert.ok(b.berichtenHtml([], nu).includes("Geen berichten"));
  // Een prijsbericht wijst met een knop naar Contract, niet met een tabblad in de tekst (v0.130.1).
  const prijs = b.berichtenHtml([{ id: "3", at: "2026-10-19T09:00:00", kind: "prijs", title: "Je energieprijs klopt niet meer", body: "Kijk na hoe de coach hem opbouwt.", read: true }], nu);
  assert.ok(prijs.includes('data-naar="contract"') && prijs.includes("Bekijk je energieprijs"), prijs);
  assert.ok(!html.includes("data-naar"), "een bericht zonder bestemming heeft die knop niet");
  // Het belletje in de kop.
  const kop = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/header.js", import.meta.url), "utf8");
  assert.ok(kop.includes('id="berichten"') && kop.includes('id="teller"') && kop.includes("dac-berichten"));
  assert.ok(kop.includes('<i class="teller"'), "het getal is geen span, anders verdwijnt het op een telefoon");
  // De volgende keer meterstanden: dezelfde som als berichten.py (proef 170 in test_coach.py).
  const { volgendeMeterstand } = await import("../custom_components/domotiapp_coach/frontend/src/views/notifications.js");
  const dag = (d) => d && `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const v = new Date(2026, 9, 19);
  assert.equal(dag(volgendeMeterstand(v, "2026-01-31", "month")), "2026-10-31");
  assert.equal(dag(volgendeMeterstand(v, "2026-10-15", "quarter")), "2027-01-15");
  assert.equal(dag(volgendeMeterstand(v, "2025-11-01", "year")), "2026-11-01");
  assert.equal(volgendeMeterstand(v, "2026-10-01", "once"), null);
  assert.equal(dag(volgendeMeterstand(v, "2026-11-01", "once")), "2026-11-01", "nog niet geweest: die dag");
  // De velden: onder Meldingen voor de bewoner, en de dagen vooraf bij Contract.
  const Meldingen = geregistreerd.get("dac-view-notifications");
  const m = Object.create(Meldingen.prototype).render();
  assert.ok(m.includes('id="meter-datum"') && m.includes('id="meter-herhaling"'));
  const c = Object.create(Contract.prototype).render();
  assert.ok(c.includes('id="stroom-dagen"') && c.includes('id="gas-dagen"'));
});

// De eerdere contracten (v0.136.0). De eigenaar op 19-10-2026: "weghalen staat niet lekker
// uitgelijnd" en "ook van tot etc staat niet mooi". Een <details> legt zijn kinderen niet als
// raster uit, dus de afstand van .circuit kwam er niet in.
proef("de eerdere contracten hebben hun inhoud in een eigen raster, en de beurten zijn opnieuw uit te rekenen (v0.136.0)", async () => {
  const contractMod = await import("../custom_components/domotiapp_coach/frontend/src/views/contract.js");
  const Contract = geregistreerd.get("dac-view-contract");
  const host = { innerHTML: "", querySelectorAll: () => [] };
  const nep = Object.create(Contract.prototype);
  nep.$ = () => host;
  nep.periodsVan_ = () => [{ name: "Gas 2023", from: "2023-09-01", to: "2023-12-31", price: 1.370204 }];
  nep.canEdit_ = () => true;
  Contract.prototype.paintPeriods_.call(nep, "gas");
  const binnen = host.innerHTML.split('<div class="p-inhoud">')[1] ?? "";
  assert.ok(binnen.includes("Van") && binnen.includes("Tot") && binnen.includes("Weghalen"), host.innerHTML);
  assert.ok(Contract.css.includes("details.period > .p-inhoud { display: grid; gap: 12px;"), "de afstand zit in de inhoud");
  // Opnieuw uitrekenen staat bij de installateur, met eerst laten zien.
  const html = Object.create(Contract.prototype).render();
  const plek = html.indexOf('id="beurten-van"');
  assert.ok(plek > 0 && html.lastIndexOf("data-installateur", plek) > html.lastIndexOf("</div>", plek - 400), "in een blok van de installateur");
  assert.ok(html.includes('id="beurten-over" hidden'), "Overnemen pas na het voorbeeld");
  const zin = contractMod.beurtenZin({ van: "2026-09-01", beurten: 30, overgeslagen: 0,
    voor: { paid: 6.12, saved: 1.31 }, na: { paid: 7.57, saved: 0.05 }, toegepast: false });
  assert.ok(zin.includes("Vanaf 1 september 2026, 30 beurten") && zin.includes("betaald was € 6,12 en wordt € 7,57")
    && zin.includes("bespaard was € 1,31 en wordt € 0,05") && !zin.includes("Overgenomen"), zin);
  assert.ok(contractMod.beurtenZin({ van: "2026-09-01", beurten: 1, overgeslagen: 1, voor: {}, na: {}, toegepast: true })
    .includes("1 beurt met een dynamische prijs blijft zoals hij was. Overgenomen."));
  assert.ok(contractMod.beurtenZin({ van: "2026-09-01", beurten: 0, overgeslagen: 0 }).includes("geen afgeronde beurt"));
  assert.equal(contractMod.beurtenZin({ fout: "Uitrekenen mislukt: x" }), "Uitrekenen mislukt: x");
});

// De schaal op Contract, "Jaar vanaf" in Historie en de accustand in de vooruitblik (v0.137.0).
proef("de schaal met en zonder thuisbatterij, het jaar vanaf een maand, en de accustand boven de 0-lijn (v0.137.0)", async () => {
  const { schaalNoot } = await import("../custom_components/domotiapp_coach/frontend/src/opbouw.js");
  const schaal = { van: "2026-09-15", tot: "2027-01-01", terug: 193.2, terug_rest: 143, kwh: 336.2, accu_kwh: 172.8,
    rij: { vanaf: 0, tot: 500, per_jaar: 0 }, kosten_per_kwh: 0, zonder_accu: { kwh: 509, rij: { vanaf: 500, tot: 750, per_jaar: 70 } } };
  const zin = schaalNoot({ schaal });
  assert.ok(zin.includes("Tot 1 januari 2027 naar verwachting 336 kWh teruglevering: de schaal van 0 tot 500 kWh, € 0 per jaar.")
    && zin.includes("Zonder je thuisbatterij 509 kWh: 500 tot 750 kWh, € 70 per jaar.") && !zin.includes("scheelt nu"), zin);
  const duur = schaalNoot({ schaal: { ...schaal, kosten_per_kwh: 0.1375, rij: { vanaf: 500, tot: 750, per_jaar: 70 } } });
  assert.ok(duur.includes("Elke kWh die je minder teruglevert scheelt nu € 0,1375"), duur);
  assert.ok(!schaalNoot({ schaal: { ...schaal, accu_kwh: 0 } }).includes("Zonder je thuisbatterij"), "zonder wat de batterij opnam geen vergelijking");
  assert.equal(schaalNoot({}), "");

  // Historie: Jaar vanaf een maand, met de maand van het contract erbij.
  const hist = await import("../custom_components/domotiapp_coach/frontend/src/views/history.js");
  assert.equal(hist.jaarMaandContract({ start: "2026-09-01" }), 9);
  assert.equal(hist.jaarMaandContract({ start: "", gas: { start: "2025-07-01" } }), 7);
  assert.equal(hist.jaarMaandContract({}), null);
  const Historie = geregistreerd.get("dac-view-history");
  const html = Object.create(Historie.prototype).render();
  assert.ok(html.includes('id="jaar-vanaf-rij" hidden') && html.includes('id="jaar-vanaf"'), "alleen bij Jaar");
  assert.ok(Historie.css.includes(".keuze[hidden] { display: none; }"), "verborgen is ook echt weg");

  // De vooruitblik: 0% op de 0-lijn en 100% bovenaan.
  const vb = await import("../custom_components/domotiapp_coach/frontend/src/vooruitblik.js");
  const uur = (h, soc, kw) => ({ start: new Date(2026, 9, 19, h), prijs: 0.3, terug: null, zon: 0, huis: 0.4,
    apparaten: { acc: { kw, onbekend: false, zonKw: 0, accuKw: 0, wat: "", why: "", soc } } });
  const uren = [uur(15, 100, 0.5), uur(16, 0, -2.5)];
  const zichtbaar = { prijs: true, zon: true, huis: true, soc: true, acc: true };
  const s = vb.schalen(uren, { ids: ["acc"], zichtbaar });
  assert.ok(s.boven >= s.onder, `boven de lijn minstens zoveel als eronder: ${JSON.stringify(s)}`);
  const svg = vb.vooruitSvg(uren, { ids: ["acc"], soorten: new Map([["acc", "thuisbatterij"]]), zichtbaar, drempels: { low: 0.2, high: 0.3 }, gekozen: -1 });
  const nul = Number(/class="nul"[^>]*y1="([\d.]+)"/.exec(svg)?.[1]);
  const punten = /class="soc" points="([^"]+)"/.exec(svg)?.[1].split(" ").map((p) => Number(p.split(",")[1]));
  assert.ok(punten && Math.abs(punten[1] - nul) < 0.11, `0% op de 0-lijn: ${punten} tegen ${nul}`);
  assert.ok(punten && Math.abs(punten[0] - 68) < 0.11, `100% bovenaan: ${punten}`);
});

// Portugal (v0.137.0): tarifas.js rekent hetzelfde als tarifas.py, Historie rekent ermee, en
// Contract toont het land en de opbouw per tijdvak.
proef("Portugal: dezelfde tijdvakken als de coach, Historie per tijdvak, en de opbouw op Contract (v0.137.0)", async () => {
  const ta = await import("../custom_components/domotiapp_coach/frontend/src/tarifas.js");
  // Dezelfde gevallen als in test_prijsopbouw.py.
  const GEVALLEN = [
    [[2026, 1, 15, 21, 59], "bi", "diario", "fora_vazio"], [[2026, 1, 15, 22, 0], "bi", "diario", "vazio"],
    [[2026, 1, 16, 7, 59], "bi", "diario", "vazio"], [[2026, 1, 16, 8, 0], "bi", "diario", "fora_vazio"],
    [[2026, 7, 15, 20, 59], "bi", "diario", "fora_vazio"], [[2026, 7, 15, 21, 0], "bi", "diario", "vazio"],
    [[2026, 1, 15, 9, 0], "tri", "diario", "ponta"], [[2026, 1, 15, 10, 30], "tri", "diario", "cheias"],
    [[2026, 1, 15, 18, 0], "tri", "diario", "ponta"], [[2026, 7, 15, 9, 30], "tri", "diario", "ponta"],
    [[2026, 7, 15, 12, 0], "tri", "diario", "cheias"], [[2026, 1, 14, 6, 59], "bi", "semanal", "vazio"],
    [[2026, 1, 14, 7, 0], "bi", "semanal", "fora_vazio"], [[2026, 1, 14, 9, 30], "tri", "semanal", "ponta"],
    [[2026, 1, 14, 12, 0], "tri", "semanal", "cheias"], [[2026, 1, 14, 23, 0], "tri", "semanal", "cheias"],
    [[2026, 7, 15, 8, 15], "tri", "semanal", "ponta"], [[2026, 1, 17, 9, 30], "bi", "semanal", "fora_vazio"],
    [[2026, 1, 17, 13, 0], "tri", "semanal", "vazio"], [[2026, 1, 17, 18, 30], "tri", "semanal", "cheias"],
    [[2026, 1, 18, 12, 0], "bi", "semanal", "vazio"], [[2026, 1, 18, 12, 0], "simples", "diario", "simples"],
  ];
  const fout = GEVALLEN.filter(([[j, m, d, u, mi], tarifa, ciclo, verwacht]) => ta.periodo(Date.UTC(j, m - 1, d, u, mi), tarifa, ciclo) !== verwacht);
  assert.deepEqual(fout, [], "tarifas.js wijkt af van tarifas.py");
  assert.ok(!ta.zomertijd(Date.UTC(2026, 2, 29, 0, 59)) && ta.zomertijd(Date.UTC(2026, 2, 29, 1, 0))
    && ta.zomertijd(Date.UTC(2026, 9, 25, 0, 59)) && !ta.zomertijd(Date.UTC(2026, 9, 25, 1, 0)), "zomertijd");
  const pt = { tarifa: "bi", ciclo: "diario", energia: { vazio: 0.134, fora_vazio: 0.2198 }, iec: 0.001, iva: 23, excedente: { modo: "nenhum" } };
  assert.equal(ta.preco(pt, "vazio"), 0.16605);
  assert.equal(ta.preco(pt, "fora_vazio"), 0.271584);
  // Een uur dat in de daluren begint (22:00 in Lissabon is 21:00 UTC in de zomer).
  assert.deepEqual(ta.ptPrijsOp(pt, Date.UTC(2026, 9, 19, 21, 0)), { koop: 0.16605, terug: 0 });
  assert.equal(ta.ptPrijsOp(pt, Date.UTC(2026, 9, 19, 10, 0)).koop, 0.271584);
  // Historie: prijsOp rekent met de tijdvakken, en er is geen salderen.
  const contract = { type: "fixed", netting: true, country: "PT", pt };
  assert.equal(geld.salderen(contract, new Date(2026, 9, 19, 12)), false, "geen salderen in Portugal");
  const p = geld.prijsOp(contract, { buy: 0.3, feedIn: 0.1 }, new Map(), new Date(Date.UTC(2026, 9, 19, 21, 0)));
  assert.deepEqual(p, { koop: 0.16605, terug: 0 }, JSON.stringify(p));
  // Een eerder contract gaat voor.
  const eerder = { ...contract, periods: [{ from: "2026-01-01", to: "2026-12-31", type: "fixed", all_in_price: 0.3, feed_in_tariff: 0.05 }] };
  assert.equal(geld.prijsOp(eerder, { buy: 0.3, feedIn: 0.1 }, new Map(), new Date(2026, 5, 1, 12)).koop, 0.3);

  // De opbouw op Contract.
  const { opbouwHtml } = await import("../custom_components/domotiapp_coach/frontend/src/opbouw.js");
  const html = opbouwHtml({ soort: "pt", salderen: false, inkoop: 0.271584, terug: 0, controle: { status: "vast" },
    pt: { tarifa: "bi", ciclo: "diario", fornecedor: "EDP Comercial", nu: "fora_vazio", excedente: "nenhum", kva: 20.7, potencia_dia: 0.8543, servicos_mes: 8.89,
      periodos: [{ periodo: "vazio", energia: 0.134, iec: 0.001, iva: 23, all_in: 0.16605 }, { periodo: "fora_vazio", energia: 0.2198, iec: 0.001, iva: 23, all_in: 0.271584 }] } });
  assert.ok(html.includes("Stroom in Portugal, EDP Comercial") && html.includes("Daluren (vazio): € 0,1340 + IEC € 0,0010, plus 23% IVA")
    && html.includes("€ 0,1661") && html.includes("Buiten de daluren (fora do vazio), nu") && html.includes("€ 0,2716")
    && html.includes("Daluren elke dag van 22:00 tot 08:00") && html.includes("niet verkocht") && html.includes("20,7 kVA"), html);
  assert.ok(!html.includes("—"), "geen gedachtestreepjes");
  const onbekend = opbouwHtml({ soort: "pt", salderen: false, inkoop: 0.27, terug: null, controle: { status: "vast" },
    pt: { tarifa: "bi", ciclo: "diario", nu: "vazio", excedente: "onbekend", periodos: [] } });
  assert.ok(onbekend.includes("nog niet ingevuld, dus weet de coach niet wat het opbrengt"), onbekend);
  assert.equal(ta.terug({}), null, "nog niet gekozen is onbekend, niet nul");
  assert.equal(ta.terug({ excedente: { modo: "nenhum" } }), 0);

  // Het formulier: het land bovenaan, het Portugese blok voor de installateur.
  await import("../custom_components/domotiapp_coach/frontend/src/views/contract.js");
  const Contract = geregistreerd.get("dac-view-contract");
  const vorm = Object.create(Contract.prototype).render();
  // Sinds v0.138.0 een keuzelijst in plaats van twee knoppen.
  assert.ok(vorm.includes('<select id="land">') && vorm.includes('<option value="NL">Nederland</option>')
    && vorm.includes('<option value="PT">Portugal</option>') && !vorm.includes("data-land=")
    && vorm.includes('id="pt-fields" class="fields" data-installateur'));
  for (const id of ["pt-tarifa", "pt-ciclo", "pt-vazio", "pt-fora", "pt-iva", "pt-iec", "pt-excedente", "pt-omie", "pt-kva", "pt-potencia", "pt-servicos"]) {
    assert.ok(vorm.includes(`id="${id}"`), id);
  }
  assert.ok(vorm.indexOf('<select id="land">') < vorm.indexOf('id="soort-rij"'), "het land staat bovenaan");
});

// De eigenaar op 19-10-2026, bij de klant in Portugal: "ik wil een dropdown menu van het land",
// "ook onder contract staat gas etc maar dat heeft deze klant niet je moet het kunnen uitzetten",
// "portugal heeft geen meterstanden", "hij zegt gemiddeld tarief maar de grafiek is rood", en
// "ik wil op de prijs kunnen klikken ... hier heb je 2 prijzen".
proef("Portugal op het overzicht en op Contract: de prijs van nu, de grafiek, gas uit, geen meterstanden (v0.138.0)", async () => {
  const ds = await import("../custom_components/domotiapp_coach/frontend/src/data-source.js");
  const ta = await import("../custom_components/domotiapp_coach/frontend/src/tarifas.js");
  const { level, prijsGrenzen } = await import("../custom_components/domotiapp_coach/frontend/src/format.js");
  const pt = { tarifa: "bi", ciclo: "diario", energia: { vazio: 0.134, fora_vazio: 0.2198 }, iec: 0.001, iva: 23 };
  // Een Portugees contract is type fixed, met de Nederlandse standaard van 0,28 er nog in.
  const contract = { type: "fixed", country: "PT", fixed: { all_in_price: 0.28 }, pt };
  const leeg = { get: () => undefined };

  // De tegel: het tijdvak van nu, niet de vaste prijs van Nederland.
  ds.zetCoachPrijzen({});
  assert.equal(ds.priceNow(leeg, contract), ta.ptPrijsOp(pt, new Date(), 900000).koop);
  assert.notEqual(ds.priceNow(leeg, contract), 0.28);
  assert.equal(ds.priceNow(leeg, { ...contract, country: "NL" }), 0.28, "Nederland blijft zoals het was");

  // De lijst: die van de coach, zoals de vooruitblik, ook bij type fixed.
  const nu = new Date();
  nu.setMinutes(0, 0, 0);
  const uur = (h) => new Date(nu.getTime() + h * 3600000);
  const rijen = [
    { start: uur(0), end: uur(1), price: 0.271584, feedIn: null },
    { start: uur(1), end: uur(2), price: 0.16605, feedIn: null },
  ];
  ds.zetCoachPrijzen({ rows: rijen });
  assert.deepEqual(ds.priceForecast(leeg, contract).map((r) => r.price), [0.271584, 0.16605]);
  assert.deepEqual(ds.priceForecast(leeg, { ...contract, country: "NL" }), [], "een Nederlands vast contract heeft geen lijst");

  // Dezelfde kleur als de grafiek: met de grenzen uit dezelfde lijst is fora do vazio hoog
  // en vazio laag. Tot v0.138.0 kreeg de tegel geen lijst en zei hij bij 0,28 "Gemiddeld".
  const grens = prijsGrenzen({ low: 0.2, high: 0.3, relative: true }, ds.priceForecast(leeg, contract))(new Date());
  assert.equal(level(0.271584, grens, true), "bad");
  assert.equal(level(0.16605, grens, true), "good");
  assert.equal(level(0.28, prijsGrenzen({ low: 0.2, high: 0.3, relative: true }, [])(new Date()), true), "warn", "zo stond het er");
  ds.zetCoachPrijzen({});

  // Onder de grafiek: wanneer de daluren zijn, dezelfde zin als op Contract.
  const { ptTijden } = await import("../custom_components/domotiapp_coach/frontend/src/opbouw.js");
  assert.equal(ptTijden(pt), "Daluren elke dag van 22:00 tot 08:00, in de tijd van Portugal.");
  assert.equal(ptTijden({ ...pt, tarifa: "simples" }), "");
  const bron = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf8");
  assert.ok(bron.includes("new Set(this.forecast_.map((rij) => rij.price)).size > 1"), "klikbaar bij meer dan een prijs");
  assert.ok(bron.includes('this.settings_?.contract?.country === "PT" ? [] : meterReadings('), "geen kaart Je meter in Portugal");

  // Contract: gas en water uit te zetten, met dezelfde vinkjes als Installatie en alleen die.
  await import("../custom_components/domotiapp_coach/frontend/src/views/contract.js");
  const Contract = geregistreerd.get("dac-view-contract");
  const vorm = Object.create(Contract.prototype).render();
  for (const id of ["gas-aan", "gas-velden", "water-aan", "water-velden"]) assert.ok(vorm.includes(`id="${id}"`), id);
  const stuk = Object.create(Contract.prototype).slice_({
    contract: { type: "fixed" },
    sources: { solar: "sensor.zon", meters: { gas_enabled: true, gas: "sensor.gas", import_low: "sensor.in" } },
  });
  assert.deepEqual(stuk, { contract: { type: "fixed" }, sources: { meters: { gas_enabled: true, water_enabled: false } } },
    "alleen de twee vinkjes, zodat opslaan de sensoren van Installatie niet terugzet");

  // Meldingen: de herinnering voor de meterstanden niet in Portugal (hieronder verder).
  const meld = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/notifications.js", import.meta.url), "utf8");
  assert.ok(meld.includes(`this.$('details.groep[data-groep="herinnering"]').hidden = this.settings_?.contract?.country === "PT";`));
});

// Gemeten op 19-10-2026 bij de woning in Portugal, vanaf een pc op Nederlandse tijd: de
// vooruitblik zei "15:00 tot 16:00", de prijsgrafiek eronder "Nu 16:45 tot 17:00". De
// eigenaar: "bouw inderdaad een reparatie voor een installatie niet in NL".
proef("de klok van het huis: nu in de tijd van Home Assistant, niet van de browser (v0.138.1)", async () => {
  const f = await import("../custom_components/domotiapp_coach/frontend/src/format.js");
  const ds = await import("../custom_components/domotiapp_coach/frontend/src/data-source.js");
  const MOMENT = new Date(Date.UTC(2026, 9, 19, 14, 57));
  try {
    // Lissabon is op 19-10-2026 UTC+1, wat de tijdzone van deze machine ook is.
    f.zetHuisZone("Europe/Lisbon");
    const h = f.alsHuis(MOMENT);
    assert.deepEqual([h.getFullYear(), h.getMonth(), h.getDate(), h.getHours(), h.getMinutes()], [2026, 9, 19, 15, 57]);
    // Een dag verder aan de andere kant van de wereld.
    f.zetHuisZone("Pacific/Kiritimati");
    const k = f.alsHuis(MOMENT);
    assert.deepEqual([k.getDate(), k.getHours()], [20, 4]);
    // Een tijd met een tijdzone wordt omgerekend, een tijd van de coach (zonder) niet.
    f.zetHuisZone("Europe/Lisbon");
    assert.equal(f.huisTijd("2026-10-19T14:57:00Z").getHours(), 15);
    assert.equal(f.huisTijd("2026-10-19T16:57:00+02:00").getHours(), 15);
    const naief = f.huisTijd("2026-10-19T15:45:00");
    assert.deepEqual([naief.getHours(), naief.getMinutes()], [15, 45]);
    assert.equal(f.huisTijd(MOMENT.getTime()).getHours(), 15, "milliseconden zijn een echt moment");

    // Nu: hetzelfde uur als de klok van het huis.
    const deel = Object.fromEntries(new Intl.DateTimeFormat("en-CA", { timeZone: "Pacific/Kiritimati", hour: "2-digit", hourCycle: "h23" })
      .formatToParts(new Date()).map((p) => [p.type, p.value]));
    f.zetHuisZone("Pacific/Kiritimati");
    assert.equal(f.huisNu().getHours(), Number(deel.hour));

    // De prijs van nu uit de lijst van de coach: het kwartier van het huis.
    const begin = f.huisNu();
    begin.setMinutes(begin.getMinutes() - (begin.getMinutes() % 15), 0, 0);
    const rijen = [0, 1, 2].map((i) => ({ start: new Date(begin.getTime() + i * 900000), end: new Date(begin.getTime() + (i + 1) * 900000), price: 0.1 + i }));
    assert.equal(ds.priceAt(rijen).price, 0.1, "het kwartier van nu op de klok van het huis");
    // Laag 0,1 en hoog 2,1: zonder het kwartier van nu zou de grens bij 1,1 beginnen.
    assert.ok(Math.abs(f.prijsGrenzen({ low: 0.2, high: 0.3, relative: true }, rijen)().low - (0.1 + 2 / 3)) < 1e-9, "het kwartier van nu telt mee");

    // Een prijssensor met tijdzone (Nord Pool) komt op dezelfde klok.
    f.zetHuisZone("Europe/Lisbon");
    const feed = { get: () => ({ state: "0.25", attributes: { raw_today: [{ start: "2026-10-19T14:00:00+00:00", end: "2026-10-19T15:00:00+00:00", value: 0.25 }] } }) };
    const rij = ds.priceForecast(feed, { type: "dynamic", dynamic: { source: "all_in", all_in_entity: "sensor.p" } })[0];
    assert.deepEqual([rij.start.getHours(), rij.end.getHours()], [15, 16]);

    // Een tijdzone die niet bestaat, of geen: de klok van de browser.
    f.zetHuisZone("Nergens/Niets");
    assert.ok(Math.abs(f.huisNu() - new Date()) < 2000);
    f.zetHuisZone(null);
    assert.ok(Math.abs(f.huisNu() - new Date()) < 2000);
  } finally {
    f.zetHuisZone(null);
  }

  // Het paneel zet de tijdzone, en de plekken die "nu" naast een tijd van de coach leggen
  // gebruiken de klok van het huis.
  const lees = (pad) => readFileSync(new URL(`../custom_components/domotiapp_coach/frontend/${pad}`, import.meta.url), "utf8");
  assert.ok(lees("domotiapp-coach-panel.js").includes("zetHuisZone(value?.config?.time_zone);"));
  for (const pad of ["src/components/price-chart.js", "src/plan-ahead-sheet.js", "src/tijdlijn.js", "src/views/notifications.js",
    "src/berichten-sheet.js", "src/schedule-sheet.js", "src/vooruitblik.js"]) {
    assert.ok(!/nu = new Date\(\)|now_ = new Date\(\)|from = new Date\(\)|new Date\(\)\.getDate\(\)/.test(lees(pad)), pad);
  }
  assert.ok(lees("src/views/overview.js").includes("Math.round((huisNu().getTime() - toen) / 60000)"), "De coach heeft N minuten niets beslist");
});

// De eigenaar op 19-10-2026: "ik wil ook dat het hele coach in het engels ingesteld kan worden".
proef("Engels: de taal kiezen, en elke zin heeft een vertaling (v0.139.0)", async () => {
  const i = await import("../custom_components/domotiapp_coach/frontend/src/i18n.js");
  const { EN } = await import("../custom_components/domotiapp_coach/frontend/src/i18n/en.js");
  const f = await import("../custom_components/domotiapp_coach/frontend/src/format.js");
  try {
    assert.equal(i.taal(), "nl", "Nederlands is de standaard");
    assert.equal(i.t("Klaar"), "Klaar");
    assert.equal(f.duration(105), "1 u 45 min");
    assert.equal(i.kiesTaal("auto", "en-GB"), true, "automatisch volgt Home Assistant");
    assert.equal(i.taal(), "en");
    assert.equal(i.t("Klaar"), "Done");
    assert.equal(f.duration(105), "1 h 45 min");
    assert.equal(i.t("nog {duur}", { duur: "5 min" }), "5 min left");
    assert.equal(i.t("Een zin die er niet is"), "Een zin die er niet is", "zonder vertaling blijft het Nederlands");
    assert.equal(i.getal(1.5), "1.5");
    assert.equal(i.tn(1, "{n} proefje", "{n} proefjes"), "1 proefje", "meervoud, zonder vertaling Nederlands");
    i.kiesTaal("nl");
    assert.equal(i.getal(1.5), "1,5");
    assert.equal(i.kiesTaal("auto", "nl"), false);
    assert.equal(i.kiesTaal("auto", "de"), false, "een andere taal dan Engels: Nederlands");
    assert.equal(i.taal(), "nl");
  } finally {
    i.kiesTaal("nl");
  }

  // Elke t("..."), tn(n, "...", "...") en nt("...") in het paneel heeft een Engelse zin, overal
  // dezelfde, met dezelfde waarden tussen accolades en zonder gedachtestreepje. Hetzelfde als
  // tools/vertaalcheck.mjs, dat per bestand zegt wat er mist.
  const { controle } = await import("../tools/vertaalcheck.mjs");
  const uit = await controle();
  const mist = Object.entries(uit.ontbreekt).map(([pad, zinnen]) => `${pad}: ${zinnen.length}`);
  assert.deepEqual(mist, [], `zinnen zonder Engels (node tools/vertaalcheck.mjs): ${mist.join(", ")}`);
  assert.deepEqual(uit.verschillend, [], "anders vertaald in twee delen");
  assert.deepEqual(uit.scheef, [], "andere waarden tussen accolades");
  assert.deepEqual(uit.streep, [], "gedachtestreepje in het Engels");
});

// "ja bouw het maar" (de eigenaar op 19-10-2026): ook Historie op de klok van het huis. En
// wat er bij een Nederlands huis vanuit Nederland niet mag veranderen, ook niet op de dag
// dat de wintertijd ingaat en 02:00 twee keer komt.
proef("Historie op de klok van het huis, en de wintertijd (v0.138.2)", async () => {
  const f = await import("../custom_components/domotiapp_coach/frontend/src/format.js");
  const st = await import("../custom_components/domotiapp_coach/frontend/src/statistics.js");
  const geld = await import("../custom_components/domotiapp_coach/frontend/src/geld.js");
  const eigen = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const opKlok = (iso, zone) => new Intl.DateTimeFormat("en-CA", { timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso));
  try {
    // Dezelfde klok als de machine: het moment zelf, ook voor de twee uren van 02:00.
    f.zetHuisZone(eigen);
    const a = new Date(Date.UTC(2026, 9, 25, 0, 30));
    const b = new Date(Date.UTC(2026, 9, 25, 1, 30));
    assert.ok(f.alsHuis(a) === a && f.alsHuis(b) === b && f.vanHuis(a) === a, "dezelfde klok: niets omgerekend");

    for (const zone of ["Europe/Lisbon", "Pacific/Kiritimati", "America/New_York"]) {
      f.zetHuisZone(zone);
      // Heen en terug geeft hetzelfde moment.
      for (const t of [Date.UTC(2026, 9, 19, 14, 57), Date.UTC(2026, 0, 15, 23, 30), Date.UTC(2026, 6, 1, 0, 0)]) {
        assert.equal(f.vanHuis(f.alsHuis(t)).getTime(), t, `${zone} ${new Date(t).toISOString()}`);
      }
      // Een dag begint om middernacht in het huis, en zo vraagt het paneel het ook op.
      const van = st.periodStart("day", 0);
      const nuHuis = f.huisNu();
      assert.deepEqual([van.getFullYear(), van.getMonth(), van.getDate(), van.getHours()], [nuHuis.getFullYear(), nuHuis.getMonth(), nuHuis.getDate(), 0], zone);
      let gevraagd = null;
      const hass = { callWS: async (msg) => { gevraagd = msg; return {}; } };
      await st.fetchPeriod(hass, ["sensor.x"], "day", van);
      assert.ok(opKlok(gevraagd.start_time, zone).endsWith("00:00") && opKlok(gevraagd.end_time, zone).endsWith("00:00"), `${zone}: ${gevraagd.start_time}`);
      await st.quarters(hass, ["sensor.x"], van, st.periodEnd("day", van));
      assert.ok(opKlok(gevraagd.start, zone).endsWith("00:00"), `${zone}: kwartieren vanaf ${gevraagd.start}`);
      // Wat terugkomt staat op de klok van het huis.
      const moment = Date.UTC(2026, 9, 19, 14, 0);
      const terug = await st.quarters({ callWS: async () => ({ "sensor.x": [{ start: moment / 1000, laagste: 1, piek: 2, gemiddeld: 1.5, seconden: 900 }] }) }, ["sensor.x"], van, van);
      assert.equal(terug.get("sensor.x")[0].start.getTime(), f.alsHuis(moment).getTime(), zone);
    }

    // Portugal: een uur in Historie op de klok van het huis krijgt de prijs van dat tijdvak.
    f.zetHuisZone("Europe/Lisbon");
    const pt = { tarifa: "bi", ciclo: "diario", energia: { vazio: 0.134, fora_vazio: 0.2198 }, iec: 0.001, iva: 23, excedente: { modo: "nenhum" } };
    const tienUur = f.alsHuis(Date.UTC(2026, 9, 19, 21, 0));
    assert.equal(tienUur.getHours(), 22);
    assert.equal(geld.prijsOp({ type: "fixed", country: "PT", pt }, { buy: 0.3, feedIn: 0 }, new Map(), tienUur).koop, 0.16605, "22:00 in Lissabon is vazio");
  } finally {
    f.zetHuisZone(null);
  }
});

// De eigenaar op 19-10-2026: lange namen in de energiestroom ("Anker Solix Solarbank Max AC"
// liep over de rand) over twee regels, en anders afgekapt.
proef("de energiestroom: een lange naam over twee regels, anders met … (v0.141.0)", async () => {
  const { naamRegels } = await import("../custom_components/domotiapp_coach/frontend/src/components/energy-flow.js");
  assert.deepEqual(naamRegels("Batterij", 12), ["Batterij"]);
  assert.deepEqual(naamRegels("Anker Solix Solarbank Max AC", 18), ["Anker Solix", "Solarbank Max AC"]);
  const smal = naamRegels("Anker Solix Solarbank Max AC", 12);
  assert.equal(smal.length, 2);
  assert.ok(smal.every((r) => r.length <= 12), JSON.stringify(smal));
  assert.ok(smal[1].endsWith("…"), JSON.stringify(smal));
  const woord = naamRegels("Warmtepompboilerinstallatie", 12);
  assert.deepEqual(woord, ["Warmtepompb…"]);
  assert.deepEqual(naamRegels("", 12), []);
});

// De eigenaar op 21-10-2026, met schermafdrukken van Contract op een iPhone: de datumvelden
// liepen rechts buiten de kaart, een leeg datumveld was hoger, en de datum stond in het midden.
// iOS geeft een datumveld een eigen minimale breedte en centreert de waarde met de flexbox van
// het veld zelf; in Chrome is daar niets van te zien, dus deze proef leest de stijl zelf.
proef("datum en tijd op een iPhone: niet breder dan het vak, links, en even hoog (v0.141.2)", async () => {
  const { baseCss } = await import("../custom_components/domotiapp_coach/frontend/src/theme.js");
  const regel = baseCss.slice(baseCss.indexOf('input[type="date"], input[type="time"]'));
  assert.match(regel, /appearance: none/);
  assert.match(regel, /min-width: 0; max-width: 100%/);
  assert.match(regel, /justify-content: flex-start/);
  assert.match(baseCss, /::-webkit-date-and-time-value[^}]*text-align: left/);
  const editor = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/editor-base.js", import.meta.url), "utf8");
  assert.match(editor, /input\[type="date"\], input\[type="time"\] \{[^}]*height: 44px/, "even hoog als de andere velden, ook leeg");
  // En de ring om vol of leeg laden: het binnenvlak is dicht, anders schijnt het verloop door.
  const ov = readFileSync(new URL("../custom_components/domotiapp_coach/frontend/src/views/overview.js", import.meta.url), "utf8");
  assert.match(ov, /::after \{[^}]*var\(--dac-bg-raise\)/);
});

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
