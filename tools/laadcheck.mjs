/**
 * Laadt elk bestand van het paneel zoals de browser dat doet.
 *
 * **Waarom dit bestaat, en waarom `node --check` niet genoeg is.** Op
 * 30-08-2026 stond er een tweede `const device` in een functie die er al een in
 * zijn parameters had. Dat is een `SyntaxError` en dus een module die niet
 * laadt, en dus een paneel dat helemaal zwart blijft. `node --check` gaf groen:
 * die leest een bestand met `import` erin niet als de module die het is, en de
 * fout zit in een scope die hij daarmee anders beoordeelt.
 *
 * Sven keek naar een zwart scherm en dacht dat zijn herstart mislukt was.
 *
 * `python tools/stijlcheck.py` blijft ernaast staan: die zoekt een backtick in
 * een stijlblok, en dat is weer iets waar deze niet over valt zolang de string
 * toevallig geldig blijft. Drie controles die elkaar niet vervangen:
 *
 *     node   tools/laadcheck.mjs     # laadt elke module echt in
 *     python tools/stijlcheck.py     # backticks in css-commentaar
 *     node   --check <bestand>       # gewone tikfouten
 *
 * Draaien: node tools/laadcheck.mjs
 */

import { readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

// --- net genoeg browser om een module in te lezen ---------------------------
// Alleen wat er bij het inlezen echt aangeraakt wordt: een custom element dat
// zich registreert, een stylesheet die gevuld wordt. De elementen worden nooit
// aangemaakt, dus alles wat pas bij het tekenen nodig is hoeft hier niet.
const geregistreerd = new Map();

globalThis.HTMLElement = class {
  attachShadow() {
    return {
      adoptedStyleSheets: [],
      append() {},
      querySelector: () => null,
      querySelectorAll: () => [],
    };
  }
  addEventListener() {}
  removeEventListener() {}
  setAttribute() {}
  getAttribute() {
    return null;
  }
};

globalThis.customElements = {
  get: (naam) => geregistreerd.get(naam),
  define: (naam, klasse) => geregistreerd.set(naam, klasse),
};

globalThis.CSSStyleSheet = class {
  replaceSync(tekst) {
    this.tekst = tekst;
  }
};

globalThis.document = {
  createElement: () => ({
    style: {},
    append() {},
    setAttribute() {},
    classList: { add() {}, remove() {} },
  }),
  createTextNode: () => ({}),
  addEventListener() {},
};

globalThis.window = globalThis;
globalThis.matchMedia = () => ({ matches: false, addEventListener() {} });
globalThis.requestAnimationFrame = (fn) => fn();

// --- alle bestanden van het paneel ------------------------------------------

const WORTEL = resolve(
  import.meta.dirname,
  "..",
  "custom_components",
  "domotiapp_coach",
  "frontend",
  "src"
);

function alleModules(map) {
  const uit = [];
  for (const naam of readdirSync(map)) {
    const pad = join(map, naam);
    if (statSync(pad).isDirectory()) uit.push(...alleModules(pad));
    else if (naam.endsWith(".js")) uit.push(pad);
  }
  return uit.sort();
}

let fout = 0;
const modules = alleModules(WORTEL);
for (const pad of modules) {
  const kort = pad.slice(WORTEL.length + 1).replaceAll("\\", "/");
  try {
    await import(pathToFileURL(pad).href);
    console.log(`  ok    ${kort}`);
  } catch (error) {
    fout += 1;
    console.log(`  FOUT  ${kort}`);
    console.log(`        ${error.message.split("\n")[0]}`);
  }
}

console.log(
  `\n${modules.length - fout} van ${modules.length} modules geladen, ` +
    `${geregistreerd.size} elementen geregistreerd`
);
if (fout) {
  console.log("Een module die niet laadt is een zwart paneel.");
}
process.exit(fout ? 1 : 0);
