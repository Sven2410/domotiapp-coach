// Welke zinnen in het paneel nog geen Engels hebben (v0.139.0).
//
//   node tools/vertaalcheck.mjs                       # het hele paneel
//   node tools/vertaalcheck.mjs src/views/contract.js  # alleen deze bestanden (vanaf frontend/)
//
// Leest elke t("..."), tn(n, "...", "...") en nt("...") buiten commentaar, en zoekt de zin
// op in i18n/en.js. Ook: een zin die in twee delen van en/ anders vertaald is, en een
// vertaling met andere waarden tussen accolades dan het Nederlands. Proef "elke zin heeft
// een vertaling" in tests/test_rapport.mjs gebruikt dezelfde functies.

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const WORTEL = fileURLToPath(new URL("../custom_components/domotiapp_coach/frontend/", import.meta.url));
// Stap 3 van het Engels (het rapport en de leverancierslijst) hoort er sinds v0.140.0 bij.
const LATER = [];

export function bestanden() {
  const uit = [];
  const loop = (map) => {
    for (const naam of readdirSync(map)) {
      const pad = join(map, naam);
      if (statSync(pad).isDirectory()) {
        if (naam !== "i18n") loop(pad);
      } else if (naam.endsWith(".js")) uit.push(pad);
    }
  };
  loop(join(WORTEL, "src"));
  uit.push(join(WORTEL, "domotiapp-coach-panel.js"));
  return uit.filter((pad) => !LATER.includes(relative(WORTEL, pad).replaceAll("\\", "/")));
}

const LIT = '"((?:[^"\\\\]|\\\\.)*)"';

/** De zinnen van een bestand, zonder wat in commentaar staat. */
export function zinnen(pad) {
  const bron = readFileSync(pad, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
  const uit = new Set();
  for (const m of bron.matchAll(new RegExp(`\\b(?:t|nt)\\(\\s*${LIT}`, "g"))) uit.add(JSON.parse(`"${m[1]}"`));
  for (const m of bron.matchAll(new RegExp(`\\btn\\([^,()]+,\\s*${LIT},\\s*${LIT}`, "g"))) {
    uit.add(JSON.parse(`"${m[1]}"`));
    uit.add(JSON.parse(`"${m[2]}"`));
  }
  return uit;
}

const waarden = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");

/** Wat er mis is: per bestand de zinnen zonder Engels, en de scheve vertalingen. */
export async function controle(paden = bestanden()) {
  const { DELEN, EN } = await import(pathToFileURL(join(WORTEL, "src/i18n/en.js")).href);
  const ontbreekt = {};
  for (const pad of paden) {
    const mist = [...zinnen(pad)].filter((zin) => !(zin in EN));
    if (mist.length) ontbreekt[relative(WORTEL, pad).replaceAll("\\", "/")] = mist;
  }
  const verschillend = [];
  const gezien = new Map();
  for (const [deel, lijst] of Object.entries(DELEN)) {
    for (const [nl, en] of Object.entries(lijst)) {
      if (gezien.has(nl) && gezien.get(nl).en !== en) verschillend.push(`${nl} (${gezien.get(nl).deel}: ${gezien.get(nl).en}; ${deel}: ${en})`);
      if (!gezien.has(nl)) gezien.set(nl, { deel, en });
    }
  }
  const scheef = Object.entries(EN).filter(([nl, en]) => waarden(nl) !== waarden(en)).map(([nl]) => nl);
  const streep = Object.entries(EN).filter(([, en]) => /\s[—–]\s/.test(en)).map(([nl]) => nl);
  return { ontbreekt, verschillend, scheef, streep };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const gevraagd = process.argv.slice(2).map((pad) => resolve(WORTEL, pad));
  const uit = await controle(gevraagd.length ? gevraagd : bestanden());
  let fout = 0;
  for (const [pad, mist] of Object.entries(uit.ontbreekt)) {
    fout += mist.length;
    console.log(`${pad}: ${mist.length} zonder Engels`);
    for (const zin of mist) console.log(`    ${JSON.stringify(zin)}`);
  }
  for (const [kop, lijst] of [["anders vertaald in twee delen", uit.verschillend], ["andere waarden tussen accolades", uit.scheef], ["gedachtestreepje", uit.streep]]) {
    if (!lijst.length) continue;
    fout += lijst.length;
    console.log(`${kop}:`);
    for (const regel of lijst) console.log(`    ${regel}`);
  }
  console.log(fout ? `\n${fout} punten` : "Alles vertaald.");
  process.exit(fout ? 1 : 0);
}
