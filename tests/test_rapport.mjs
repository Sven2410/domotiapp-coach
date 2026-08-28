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
