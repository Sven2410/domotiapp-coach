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
// De Easee Equalizer bij Van den Dam meldt in een sensor hoeveel hij op dit
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
// Sven vroeg er op 30-08-2026 om: zien wat de coach van plan is tot de auto vol
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

/** De tijdlijn zoals de coach hem voor Van den Dam die nacht uitrekende. */
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
      charging: false, why: "duurder dan wat hij nodig heeft" },
    { start: "2026-08-30T03:00:00", end: "2026-08-30T04:00:00", price: 0.2215,
      charging: true, why: "een van de goedkoopste uren" },
    { start: "2026-08-30T04:00:00", end: "2026-08-30T05:00:00", price: 0.2113,
      charging: true, why: "een van de goedkoopste uren" },
  ],
};

proef("de kop toont wat er nog in moet en wanneer hij begint", () => {
  const { el, knopen } = vooruitScherm(NACHT);
  el.paint_();
  const tekst = knopen.get("#vooruit-kop").kinderen
    .flatMap((vak) => vak.kinderen.map((kind) => kind.textContent))
    .join(" | ");
  assert.match(tekst, /37,2 kWh/, "het aantal kilowattuur hoort erin");
  assert.match(tekst, /op 16 A/, "en de stroom waar het op gerekend is");
  assert.match(tekst, /3 u 22 m/, "de laadtijd als uren en minuten");
  assert.match(tekst, /03:07/, "het uiterste startmoment");
  assert.match(tekst, /klaar om 07:00/, "en de klaar-tijd");
});

proef("elk uur staat er met zijn prijs en of hij laadt", () => {
  const { el, knopen } = vooruitScherm(NACHT);
  el.paint_();
  const rijen = knopen.get("#vooruit-uren").kinderen;
  assert.equal(rijen.length, 3, "drie blokken, drie regels");

  const eerste = rijen[0].kinderen.map((kind) => kind.textContent);
  assert.deepEqual(eerste, ["22:00", "€ 0,311", "Wachten, duurder dan wat hij nodig heeft"]);
  assert.ok(!rijen[0].className.includes("laadt"), "een wachtuur krijgt geen kleur");

  const derde = rijen[2].kinderen.map((kind) => kind.textContent);
  assert.deepEqual(derde, ["04:00", "€ 0,211", "Laden, een van de goedkoopste uren"]);
  assert.ok(rijen[2].className.includes("laadt"), "een laaduur wel");
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

// --- de knoppenrij op de laadpaalkaart --------------------------------------
//
// Op 30-08-2026 kreeg de nieuwe knop "Wat gaat hij doen" de klasse `plan-link`,
// en die stijlen staan onder `.plan-pick`. Buiten dat blok kreeg de knop dus
// helemaal geen vorm: het pictogram werd op ware grootte getekend, de rij groeide
// mee, en Snelladen en Pauzeren werden reusachtige cirkels omdat hun
// pillevorm de hoogte van de rij overnam. Sven: "waarom is dit ineens zo groot?"
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
