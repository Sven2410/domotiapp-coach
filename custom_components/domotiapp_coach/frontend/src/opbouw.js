/**
 * Zo komt je prijs tot stand: de opbouw in woorden en cijfers (v0.129.0).
 *
 * De eigenaar op 18-10-2026: "Invullen, laten zien hoe de prijs tot stand is
 * gekomen in woord én cijfers, en het all-in resultaat tonen", en: "Dat is hoe
 * de leverancier het vaak op zijn website ook doet, dus daarmee kan de
 * consument dubbel checken."
 *
 * Dit rekent niets: het toont wat de coach uitrekende (`contract/check`,
 * `async_prijscontrole` in coach.py, `prijsopbouw.py`). Contract en Voorkeuren
 * tonen het allebei, met dezelfde woorden.
 */

const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

/** € 0,4090: vier decimalen, want een leverancier noemt zijn opslag in tienden van centen. */
export const euro4 = (v) =>
  `€ ${Number(v ?? 0).toLocaleString("nl-NL", { minimumFractionDigits: 4, maximumFractionDigits: 4 })}`;

const klok = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

const rij = (teken, woord, bedrag, extra = "") =>
  `<div class="ob-rij${extra ? ` ${extra}` : ""}"><span class="ob-teken">${teken}</span><span class="ob-woord">${woord}</span><span class="ob-bedrag">${bedrag}</span></div>`;

/**
 * De woorden voor de onderdelen: die van de leverancier als de catalogus ze
 * kent (de een zegt inkoopvergoeding, de ander opslag of handelingskosten).
 */
function woorden(namen = {}) {
  return {
    opslag: namen.opslag || "Opslag van je leverancier",
    vergoeding: namen.vergoeding || "Vergoeding van je leverancier",
    kosten: namen.kosten || "Terugleverkosten",
    bonus: namen.bonus || "Bonus",
    leverancier: namen.leverancier || "je leverancier",
  };
}

/**
 * Salderen staat uit terwijl het nog geldt (v0.129.1). De bewoner van de eerste
 * woning op 19-10-2026, met salderen uit: "Op dit moment krijg je namelijk ook de
 * btw en energiebelasting nog terug! Dat verandert wel per 1-1-27." Dat vinkje
 * is een afspraak met de leverancier en geen meting, dus de coach zet het niet
 * zelf; hij zegt het wel.
 */
export function salderenNoot(check, nu = new Date()) {
  if (!check || check.salderen || nu >= new Date(2027, 0, 1)) return "";
  return `<p class="ob-noot ob-let">Je saldeert niet volgens de instellingen. Tot 1 januari 2027 krijg je over wat je teruglevert, tot aan je eigen verbruik, ook de energiebelasting en btw terug. Klopt dat bij jou, zet dan bij Contract "Je levert nog gesaldeerd terug" aan.</p>`;
}

/**
 * De regels van de teruglevering tot aan de vergoeding, in dezelfde vorm als
 * de inkoop: de kale marktprijs, dan wat er bij komt. Met salderen de
 * energiebelasting en de btw, en de opslag alleen als de leverancier die ook
 * teruggeeft (`netting_full`); zonder salderen de btw als hij met btw uitbetaalt.
 */
function terugRegels(check, t, w) {
  const o = check.inkoop;
  if (!o) {
    // Zonder opbouw (geen kale marktprijs): alleen wat er is.
    return [rij("", t.salderen ? "All-in prijs (je saldeert)" : "Kale marktprijs", euro4(t.basis))];
  }
  const procent = Number(o.btw_procent) || 0;
  const factor = 1 + procent / 100;
  // Wordt er met btw uitbetaald (bij salderen, of als de leverancier dat zo
  // doet), dan staan de vergoeding, de kosten en de bonus hier zonder btw,
  // net als bij de inkoop, en komt de btw er als een regel bij.
  const metBtw = t.salderen || t.met_btw;
  const zonder = (bedrag) => (metBtw ? bedrag / factor : bedrag);
  const regels = [rij("", "Kale marktprijs", euro4(o.markt))];
  let som = o.markt;
  if (t.salderen) {
    regels.push(rij("+", "Energiebelasting, terug omdat je saldeert", euro4(o.belasting)));
    som += o.belasting;
    if (t.vol) {
      regels.push(rij("+", `${esc(w.opslag)}, ook terug`, euro4(o.opslag)));
      som += o.opslag;
    }
  }
  if (t.vergoeding) {
    regels.push(rij(t.vergoeding < 0 ? "−" : "+", esc(w.vergoeding), euro4(Math.abs(zonder(t.vergoeding)))));
    som += zonder(t.vergoeding);
  }
  if (t.kosten) {
    regels.push(rij("−", esc(w.kosten), euro4(zonder(t.kosten))));
    som -= zonder(t.kosten);
  }
  if (check.bonus_procent) {
    const wanneer = check.bonus_overdag ? (check.overdag ? ", overdag" : ", alleen overdag: nu niet") : "";
    regels.push(rij("+", `${esc(w.bonus)} ${String(check.bonus_procent).replace(".", ",")}%${wanneer}`, euro4(zonder(t.bonus || 0))));
    som += zonder(t.bonus || 0);
  }
  if (metBtw) {
    regels.push(rij("=", "Samen, zonder btw", euro4(som), "ob-tussen"));
    regels.push(rij("+", `Btw ${String(procent).replace(".", ",")}%`, euro4(som * (factor - 1))));
  }
  return regels;
}

/** De zin onder de inkoop: klopt het, klopt het niet, of valt er niets te controleren. */
export function controleZin(check, namen = {}) {
  const w = woorden(namen);
  const c = check?.controle ?? {};
  if (check?.soort !== "dynamic") {
    return { toon: "neutraal", tekst: "Niet te controleren: een vaste of variabele prijs staat in je contract, en er is geen sensor om hem mee te vergelijken." };
  }
  if (c.status === "correct") {
    const uren = c.stap_minuten === 15 ? `${c.blokken} kwartieren` : `${c.blokken} uur`;
    return { toon: "goed", tekst: `De ingevoerde gegevens zijn correct. Nagerekend over ${uren}.` };
  }
  if (c.status === "afwijking") {
    const verschil = -Number(c.grootste ?? 0);
    const richting = verschil > 0 ? "hoger" : "lager";
    if (c.vast) {
      return { toon: "fout", tekst: `Dit klopt niet: de opbouw komt elk ${c.stap_minuten === 15 ? "kwartier" : "uur"} ${euro4(Math.abs(verschil))} ${richting} uit dan ${w.leverancier} zegt. Dat zit in een bedrag per kWh: kijk de energiebelasting en de ${w.opslag.toLowerCase()} na.` };
    }
    return { toon: "fout", tekst: `Dit klopt niet: de opbouw wijkt tot ${euro4(Math.abs(verschil))} af van wat ${w.leverancier} zegt, en niet elk uur even veel. Kijk de btw na, en of je leverancier per uur of per kwartier rekent.` };
  }
  const bron = check?.bron ?? {};
  if (bron.zelfde) return { toon: "fout", tekst: "Niet te controleren: bij de marktprijs staat dezelfde sensor als bij de all-in prijs. Kies een kale marktprijs, zoals de ingebouwde Nord Pool." };
  if (!bron.all_in) return { toon: "neutraal", tekst: `Niet te controleren: er is geen all-in sensor van ${w.leverancier} om mee te vergelijken. De coach rekent met de kale marktprijs plus de bedragen hierboven.` };
  if (!bron.markt) return { toon: "fout", tekst: "Niet te controleren: er is geen kale marktprijs (zoals de ingebouwde Nord Pool). Zonder kan de coach je prijs niet nagaan, en valt hij niet terug als je leverancier wegvalt." };
  return { toon: "neutraal", tekst: "Nog niet te controleren: de twee sensoren hebben nog geen uur samen. Kijk over een uur nog eens." };
}

/**
 * De opbouw als html.
 *
 * @param {object} check wat `contract/check` gaf
 * @param {object} [namen] de woorden van de leverancier (`namenVan` in leveranciers.js)
 */
export function opbouwHtml(check, namen = {}) {
  if (!check) return `<p class="ob-leeg">De opbouw wordt opgehaald.</p>`;
  const w = woorden(namen);
  const delen = [];

  if (check.soort !== "dynamic") {
    const terug = check.terug;
    delen.push(`<div class="ob-blok"><h4>Stroom</h4>
      ${rij("", "All-in prijs, zoals in je contract", check.inkoop === null || check.inkoop === undefined ? "niet ingevuld" : euro4(check.inkoop), "ob-totaal")}
      ${rij("", check.salderen ? "Teruglevering (je saldeert: je inkoopprijs min de kosten)" : "Teruglevering (vergoeding min de kosten)", terug === null || terug === undefined ? "onbekend" : euro4(terug))}
    </div>`);
  } else {
    const blok = check.blok;
    const tijd = blok ? ` (${klok(blok.start)} tot ${klok(blok.einde)})` : "";
    const o = check.inkoop;
    if (o) {
      // Een leverancier per uur tegenover een marktprijs per kwartier: het uurgemiddelde.
      const blokMin = blok ? Math.round((new Date(blok.einde) - new Date(blok.start)) / 60000) : 0;
      const marktMin = Number(check.bron?.markt_minuten) || 0;
      const markt = marktMin && blokMin > marktMin
        ? `Kale marktprijs, gemiddelde van ${blokMin / marktMin === 4 ? "vier" : blokMin / marktMin} ${marktMin === 15 ? "kwartieren" : "blokken"}`
        : "Kale marktprijs";
      // Alles zonder btw, dan een regel btw (v0.129.1). De eigenaar op
      // 19-10-2026: "Doe alles mét, of alles zónder btw. Alles op dezelfde
      // manier is eenvoudiger vergelijken en checken." Een leverancier die zijn
      // opslag met btw noemt (Zonneplan: € 0,02) staat hier dus zonder.
      const stappen = [
        rij("", esc(markt), euro4(o.markt)),
        rij("+", "Energiebelasting", euro4(o.belasting)),
        rij("+", esc(w.opslag), euro4(o.opslag)),
        rij("=", "Samen, zonder btw", euro4(o.subtotaal), "ob-tussen"),
        rij("+", `Btw ${String(o.btw_procent).replace(".", ",")}%`, euro4(o.btw)),
      ];
      delen.push(`<div class="ob-blok"><h4>Inkoop nu${tijd}</h4>
        ${stappen.join("")}
        ${rij("=", "All-in", euro4(o.totaal), "ob-totaal")}
        ${check.all_in !== null && check.all_in !== undefined ? rij("", `Wat ${esc(w.leverancier)} zegt`, euro4(check.all_in), "ob-sensor") : ""}
      </div>`);
    } else if (check.all_in !== null && check.all_in !== undefined) {
      delen.push(`<div class="ob-blok"><h4>Inkoop nu${tijd}</h4>
        ${rij("", `All-in, van ${esc(w.leverancier)}`, euro4(check.all_in), "ob-totaal")}
      </div>`);
    } else {
      delen.push(`<div class="ob-blok"><h4>Inkoop</h4><p class="ob-leeg">Er is nu geen prijs: de sensoren geven niets voor dit moment.</p></div>`);
    }

    const t = check.terug;
    if (t && t.bedrag !== null && t.bedrag !== undefined) {
      // Dezelfde opbouw als de inkoop erboven (v0.129.1). De bewoner van de
      // eerste woning op 19-10-2026: "identiek opbouwen als het overzicht van
      // de afnameprijs. Bij afname geef je de post kale marktprijs, bij
      // teruglevering zeg je marktprijs met btw." Dus ook hier de kale prijs,
      // en de btw en de energiebelasting als eigen regel.
      const regels = terugRegels(check, t, w);
      regels.push(rij("=", "Per teruggeleverde kWh", euro4(t.bedrag), "ob-totaal"));
      delen.push(`<div class="ob-blok"><h4>Teruglevering nu</h4>${regels.join("")}
        <p class="ob-noot">Niet te controleren: ${esc(w.leverancier)} geeft de terugleverprijs niet door. Zo rekent de coach.</p>
        ${salderenNoot(check)}</div>`);
    } else {
      delen.push(`<div class="ob-blok"><h4>Teruglevering</h4><p class="ob-leeg">${
        check.salderen ? "Onbekend: er is nu geen all-in prijs." : "Onbekend: zonder kale marktprijs weet de coach niet wat teruglevering opbrengt, en kan een thuisbatterij niet handelen."
      }</p></div>`);
    }
  }

  const zin = controleZin(check, namen);
  delen.push(`<p class="ob-controle ${zin.toon}">${esc(zin.tekst)}</p>`);
  return delen.join("");
}

/** Wie bevestigde en wanneer, of dat het nog moet. */
export function bevestigdZin(check) {
  if (!check) return "";
  if (check.bevestigd) {
    const d = new Date(check.bevestigd_op);
    const datum = Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric" });
    return `Bevestigd${check.bevestigd_door ? ` door ${esc(check.bevestigd_door)}` : ""}${datum ? ` op ${datum}` : ""}.`;
  }
  return check.bevestigd_op ? "Er is iets veranderd sinds de vorige bevestiging. Kijk het na en bevestig opnieuw." : "Nog niet bevestigd.";
}

export const opbouwCss = /* css */ `
  .ob { display: grid; gap: 12px; }
  .ob-blok { display: grid; gap: 4px; padding: 12px 14px; border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.022); }
  .ob-blok h4 { margin: 0 0 4px; font-size: 13px; font-weight: 600; color: var(--dac-ink); }
  .ob-rij { display: grid; grid-template-columns: 14px minmax(0, 1fr) auto; gap: 8px; align-items: baseline;
    font-size: 13px; color: var(--dac-ink-2); }
  .ob-teken { color: var(--dac-ink-3, var(--dac-ink-2)); text-align: center; }
  .ob-woord { min-width: 0; overflow-wrap: anywhere; }
  .ob-bedrag { font-variant-numeric: tabular-nums; white-space: nowrap; color: var(--dac-ink); }
  .ob-tussen { border-top: 1px dashed var(--dac-border); padding-top: 4px; }
  .ob-totaal { border-top: 1px solid var(--dac-border-hi, var(--dac-border)); padding-top: 4px; font-weight: 600; }
  .ob-totaal .ob-woord, .ob-totaal .ob-bedrag { color: var(--dac-ink); }
  .ob-sensor .ob-woord { font-style: italic; }
  .ob-noot, .ob-leeg { margin: 4px 0 0; font-size: 12px; color: var(--dac-ink-2); }
  .ob-let { padding: 8px 10px; border-radius: var(--dac-radius-sm); border: 1px solid rgba(250,178,25,0.4); background: rgba(250,178,25,0.08); color: var(--dac-ink); }
  .ob-controle { margin: 0; padding: 10px 12px; border-radius: var(--dac-radius-sm); font-size: 13px; line-height: 1.45; }
  .ob-controle.goed { border: 1px solid rgba(48,164,108,0.4); background: rgba(48,164,108,0.10); color: var(--dac-ink); }
  .ob-controle.fout { border: 1px solid rgba(250,178,25,0.4); background: rgba(250,178,25,0.10); color: var(--dac-ink); }
  .ob-controle.neutraal { border: 1px solid var(--dac-border); background: rgba(var(--dac-veil),0.03); color: var(--dac-ink-2); }
`;
