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

import { datum, locale, t } from "./i18n.js";
import { NAMEN } from "./tarifas.js";

const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

/** € 0,4090: vier decimalen, want een leverancier noemt zijn opslag in tienden van centen. */
export const euro4 = (v) =>
  `€ ${Number(v ?? 0).toLocaleString(locale(), { minimumFractionDigits: 4, maximumFractionDigits: 4 })}`;

/** Een procent of kVA zoals hij is, met het scheidingsteken van de taal: 21, 2,5 of 2.5. */
const los = (n) => Number(n).toLocaleString(locale(), { maximumFractionDigits: 6, useGrouping: false });

/** Een heel getal met de duizendtallen van de taal: 1.500 of 1,500. */
const heel = (n) => Math.round(Number(n) || 0).toLocaleString(locale());

/** Een datum als "1 januari 2027", of zonder jaar; leeg als hij niet te lezen is. */
const lang = (tekst, jaar = true) => {
  const d = new Date(tekst);
  return Number.isNaN(d.getTime()) ? "" : datum(d, jaar ? { day: "numeric", month: "long", year: "numeric" } : { day: "numeric", month: "long" });
};

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
    opslag: namen.opslag || t("Opslag van je leverancier"),
    vergoeding: namen.vergoeding || t("Vergoeding van je leverancier"),
    kosten: namen.kosten || t("Terugleverkosten"),
    bonus: namen.bonus || t("Bonus"),
    leverancier: namen.leverancier || t("je leverancier"),
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
  return `<p class="ob-noot ob-let">${t("Je saldeert niet volgens de instellingen. Tot 1 januari 2027 krijg je over wat je teruglevert, tot aan je eigen verbruik, ook de energiebelasting en btw terug. Klopt dat bij jou, zet dan bij Contract \"Je levert nog gesaldeerd terug\" aan.")}</p>`;
}

/**
 * Of een teruggeleverde kWh wegstreept tegen inkoop, over de afrekenperiode
 * (v0.134.0): wat er sinds het begin van de jaarafrekening van het net kwam en
 * terugging, en wat er tot het einde van salderen nog bij komt (dezelfde weken
 * vorig jaar). Uit de meterstanden (`_async_jaarsaldo` in coach.py). Leeg als
 * de coach de begindatum of de meter niet kent.
 */
/**
 * Wat de vorm van de terugleverkosten betekent voor een kWh extra (v0.135.0), of
 * leeg bij per kWh over alles: dan staan de kosten gewoon in de regels.
 */
export function kostenNoot(check) {
  const tekst = {
    schalen: t("Je terugleverkosten zijn een vast bedrag per jaar, in schalen. Wat je schaal kost staat in Historie, per dag."),
    overschot: t("Je leverancier rekent terugleverkosten alleen over wat er na salderen overblijft: een gesaldeerde kWh kost niets."),
    geen: t("Je leverancier rekent geen terugleverkosten."),
  }[check?.kosten_vorm];
  return tekst ? `<p class="ob-noot">${tekst}</p>` : "";
}

/**
 * De schaal van de terugleverkosten die eraan komt, met en zonder thuisbatterij (v0.137.0):
 * `schaal` van `contract/check` (`_async_schaal` in coach.py). Leeg zonder schalen.
 */
export function schaalNoot(check) {
  const s = check?.schaal;
  if (!s?.rij) return "";
  const vak = (r) => (r.tot
    ? t("{van} tot {tot} kWh", { van: heel(r.vanaf), tot: heel(r.tot) })
    : t("vanaf {van} kWh", { van: heel(r.vanaf) }));
  const tot = lang(`${s.tot}T00:00:00`) || t("het einde");
  const zinnen = [t("Tot {datum} naar verwachting {kwh} kWh teruglevering: de schaal van {vak}, € {bedrag} per jaar.",
    { datum: tot, kwh: heel(s.kwh), vak: vak(s.rij), bedrag: heel(s.rij.per_jaar) })];
  const z = s.zonder_accu;
  if (z?.rij && Number(s.accu_kwh) > 0) {
    zinnen.push(t("Zonder je thuisbatterij {kwh} kWh: {vak}, € {bedrag} per jaar.",
      { kwh: heel(z.kwh), vak: vak(z.rij), bedrag: heel(z.rij.per_jaar) }));
  }
  if (Number(s.kosten_per_kwh) > 0) {
    zinnen.push(t("Elke kWh die je minder teruglevert scheelt nu {bedrag}, dus gebruikt de coach je zon liever zelf.",
      { bedrag: euro4(s.kosten_per_kwh) }));
  }
  return `<p class="ob-noot">${zinnen.join(" ")}</p>`;
}

export function jaarNoot(check) {
  if (!check?.salderen || !check?.jaar) return "";
  const j = check.jaar;
  if (!j.compleet) {
    return `<p class="ob-noot">${t("Nog niet uit te rekenen of je over je afrekenperiode meer teruglevert dan je afneemt: de meter heeft geen metingen van dezelfde weken vorig jaar. De coach rekent tot dan met salderen.")}</p>`;
  }
  const kwh = (n) => `${heel(n)} kWh`;
  const sinds = lang(`${j.van}T00:00:00`, false) || t("het begin van je afrekenperiode");
  const zin = t("Sinds {sinds} nam je {afname} af en leverde je {terug} terug. Tot 1 januari 2027 komt daar naar verwachting {afname_rest} afname en {terug_rest} teruglevering bij, zoals in dezelfde weken vorig jaar.",
    { sinds, afname: kwh(j.afname), terug: kwh(j.terug), afname_rest: kwh(j.afname_rest), terug_rest: kwh(j.terug_rest) });
  if (check.netto_terug === true) {
    return `<p class="ob-noot">${zin} ${t("Je levert meer terug dan je afneemt, dus een kWh extra naar het net krijgt de vergoeding na saldering.")}</p>`;
  }
  return `<p class="ob-noot">${zin} ${t("Alles wat je teruglevert valt dus weg tegen inkoop.")}</p>`;
}

/** Wat een vast contract na salderen zegt (v0.134.0): `na_salderen` van `contract/check`. */
function naSalderenBlok(na) {
  if (!na) return "";
  return `<div class="ob-blok"><h4>${t("Teruglevering vanaf 1 januari 2027")}</h4>
    ${rij("", t("Terugleververgoeding"), euro4(na.vergoeding))}
    ${rij("−", t("Terugleverkosten"), euro4(na.kosten))}
    ${rij("=", t("Per teruggeleverde kWh"), euro4(na.terug), "ob-totaal")}
    <p class="ob-noot">${t("Dan stopt salderen, en geldt dit voor alles wat je teruglevert.")}</p>
  </div>`;
}

/**
 * De regels van de teruglevering tot aan de vergoeding, in dezelfde vorm als
 * de inkoop: de kale marktprijs, dan wat er bij komt. Met salderen de
 * energiebelasting en de btw, en de opslag alleen als de leverancier die ook
 * teruggeeft (`netting_full`); zonder salderen de btw als hij met btw uitbetaalt.
 */
function terugRegels(check, tr, w) {
  // Een vaste terugleververgoeding (v0.132.0): het bedrag, en de kosten eraf.
  if (tr.vast) {
    const regels = [rij("", t("Vaste terugleververgoeding"), euro4(tr.basis))];
    if (tr.kosten) regels.push(rij("−", esc(w.kosten), euro4(tr.kosten)));
    return regels;
  }
  const o = check.inkoop;
  if (!o) {
    // Zonder opbouw (geen kale marktprijs): alleen wat er is.
    return [rij("", tr.salderen ? t("All-in prijs (je saldeert)") : t("Kale marktprijs"), euro4(tr.basis))];
  }
  const procent = Number(o.btw_procent) || 0;
  const factor = 1 + procent / 100;
  // Wordt er met btw uitbetaald (bij salderen, of als de leverancier dat zo
  // doet), dan staan de vergoeding, de kosten en de bonus hier zonder btw,
  // net als bij de inkoop, en komt de btw er als een regel bij.
  const metBtw = tr.salderen || tr.met_btw;
  const zonder = (bedrag) => (metBtw ? bedrag / factor : bedrag);
  const regels = [rij("", t("Kale marktprijs"), euro4(o.markt))];
  let som = o.markt;
  if (tr.salderen) {
    regels.push(rij("+", t("Energiebelasting, terug omdat je saldeert"), euro4(o.belasting)));
    som += o.belasting;
    if (tr.vol) {
      regels.push(rij("+", t("{opslag}, ook terug", { opslag: esc(w.opslag) }), euro4(o.opslag)));
      som += o.opslag;
    }
  }
  if (tr.vergoeding) {
    regels.push(rij(tr.vergoeding < 0 ? "−" : "+", esc(w.vergoeding), euro4(Math.abs(zonder(tr.vergoeding)))));
    som += zonder(tr.vergoeding);
  }
  if (tr.kosten) {
    regels.push(rij("−", esc(w.kosten), euro4(zonder(tr.kosten))));
    som -= zonder(tr.kosten);
  }
  if (check.bonus_procent) {
    const bonus = { bonus: esc(w.bonus), procent: los(check.bonus_procent) };
    const woord = !check.bonus_overdag ? `${bonus.bonus} ${bonus.procent}%`
      : check.overdag ? t("{bonus} {procent}%, overdag", bonus) : t("{bonus} {procent}%, alleen overdag: nu niet", bonus);
    regels.push(rij("+", woord, euro4(zonder(tr.bonus || 0))));
    som += zonder(tr.bonus || 0);
  }
  if (metBtw) {
    regels.push(rij("=", t("Samen, zonder btw"), euro4(som), "ob-tussen"));
    regels.push(rij("+", t("Btw {procent}%", { procent: los(procent) }), euro4(som * (factor - 1))));
  }
  return regels;
}

/** De zin onder de inkoop: klopt het, klopt het niet, of valt er niets te controleren. */
export function controleZin(check, namen = {}) {
  const w = woorden(namen);
  const c = check?.controle ?? {};
  if (check?.soort !== "dynamic") {
    return { toon: "neutraal", tekst: t("Niet te controleren: een vaste of variabele prijs staat in je contract, en er is geen sensor om hem mee te vergelijken.") };
  }
  if (c.status === "correct") {
    return { toon: "goed", tekst: c.stap_minuten === 15
      ? t("De ingevoerde gegevens zijn correct. Nagerekend over {n} kwartieren.", { n: c.blokken })
      : t("De ingevoerde gegevens zijn correct. Nagerekend over {n} uur.", { n: c.blokken }) };
  }
  if (c.status === "afwijking") {
    const verschil = -Number(c.grootste ?? 0);
    const waarden = { bedrag: euro4(Math.abs(verschil)), leverancier: w.leverancier };
    if (c.vast) {
      const v = { ...waarden, opslag: w.opslag.toLowerCase() };
      const tekst = c.stap_minuten === 15
        ? (verschil > 0
          ? t("Dit klopt niet: de opbouw komt elk kwartier {bedrag} hoger uit dan {leverancier} zegt. Dat zit in een bedrag per kWh: kijk de energiebelasting en de {opslag} na.", v)
          : t("Dit klopt niet: de opbouw komt elk kwartier {bedrag} lager uit dan {leverancier} zegt. Dat zit in een bedrag per kWh: kijk de energiebelasting en de {opslag} na.", v))
        : (verschil > 0
          ? t("Dit klopt niet: de opbouw komt elk uur {bedrag} hoger uit dan {leverancier} zegt. Dat zit in een bedrag per kWh: kijk de energiebelasting en de {opslag} na.", v)
          : t("Dit klopt niet: de opbouw komt elk uur {bedrag} lager uit dan {leverancier} zegt. Dat zit in een bedrag per kWh: kijk de energiebelasting en de {opslag} na.", v));
      return { toon: "fout", tekst };
    }
    return { toon: "fout", tekst: t("Dit klopt niet: de opbouw wijkt tot {bedrag} af van wat {leverancier} zegt, en niet elk uur even veel. Kijk de btw na, en of je leverancier per uur of per kwartier rekent.", waarden) };
  }
  const bron = check?.bron ?? {};
  if (bron.zelfde) return { toon: "fout", tekst: t("Niet te controleren: bij de marktprijs staat dezelfde sensor als bij de all-in prijs. Kies een kale marktprijs, zoals de ingebouwde Nord Pool.") };
  if (!bron.all_in) return { toon: "neutraal", tekst: t("Niet te controleren: er is geen all-in sensor van {leverancier} om mee te vergelijken. De coach rekent met de kale marktprijs plus de bedragen hierboven.", { leverancier: w.leverancier }) };
  if (!bron.markt) return { toon: "fout", tekst: t("Niet te controleren: er is geen kale marktprijs (zoals de ingebouwde Nord Pool). Zonder kan de coach je prijs niet nagaan, en valt hij niet terug als je leverancier wegvalt.") };
  return { toon: "neutraal", tekst: t("Nog niet te controleren: de twee sensoren hebben nog geen uur samen. Kijk over een uur nog eens.") };
}

/**
 * De opbouw als html.
 *
 * @param {object} check wat `contract/check` gaf
 * @param {object} [namen] de woorden van de leverancier (`namenVan` in leveranciers.js)
 */
export function opbouwHtml(check, namen = {}) {
  if (!check) return `<p class="ob-leeg">${t("De opbouw wordt opgehaald.")}</p>`;
  const w = woorden(namen);
  const delen = [];

  if (check.soort === "pt") {
    delen.push(ptBlok(check));
    const zin = controleZin(check, namen);
    delen.push(`<p class="ob-controle ${zin.toon}">${esc(zin.tekst)}</p>`);
    return delen.join("");
  }

  if (check.soort !== "dynamic") {
    const terug = check.terug;
    delen.push(`<div class="ob-blok"><h4>${t("Stroom")}</h4>
      ${rij("", t("All-in prijs, zoals in je contract"), check.inkoop === null || check.inkoop === undefined ? t("niet ingevuld") : euro4(check.inkoop), "ob-totaal")}
      ${rij("", check.salderen && check.netto_terug !== true ? t("Teruglevering (je saldeert: je inkoopprijs min de kosten)") : t("Teruglevering (vergoeding min de kosten)"), terug === null || terug === undefined ? t("onbekend") : euro4(terug))}
      ${jaarNoot(check)}
      ${kostenNoot(check)}
      ${schaalNoot(check)}
    </div>`);
    delen.push(naSalderenBlok(check.na_salderen));
  } else {
    const blok = check.blok;
    const inkoopNu = blok ? t("Inkoop nu ({van} tot {tot})", { van: klok(blok.start), tot: klok(blok.einde) }) : t("Inkoop nu");
    const o = check.inkoop;
    if (o) {
      // Een leverancier per uur tegenover een marktprijs per kwartier: het uurgemiddelde.
      const blokMin = blok ? Math.round((new Date(blok.einde) - new Date(blok.start)) / 60000) : 0;
      const marktMin = Number(check.bron?.markt_minuten) || 0;
      const markt = marktMin && blokMin > marktMin
        ? t("Kale marktprijs, gemiddelde van {n} {blokken}", {
          n: blokMin / marktMin === 4 ? t("vier") : blokMin / marktMin,
          blokken: marktMin === 15 ? t("kwartieren") : t("blokken"),
        })
        : t("Kale marktprijs");
      // Alles zonder btw, dan een regel btw (v0.129.1). De eigenaar op
      // 19-10-2026: "Doe alles mét, of alles zónder btw. Alles op dezelfde
      // manier is eenvoudiger vergelijken en checken." Een leverancier die zijn
      // opslag met btw noemt (Zonneplan: € 0,02) staat hier dus zonder.
      const stappen = [
        rij("", esc(markt), euro4(o.markt)),
        rij("+", t("Energiebelasting"), euro4(o.belasting)),
        rij("+", esc(w.opslag), euro4(o.opslag)),
        rij("=", t("Samen, zonder btw"), euro4(o.subtotaal), "ob-tussen"),
        rij("+", t("Btw {procent}%", { procent: los(o.btw_procent) }), euro4(o.btw)),
      ];
      delen.push(`<div class="ob-blok"><h4>${inkoopNu}</h4>
        ${stappen.join("")}
        ${rij("=", t("All-in"), euro4(o.totaal), "ob-totaal")}
        ${check.all_in !== null && check.all_in !== undefined ? rij("", t("Wat {leverancier} zegt", { leverancier: esc(w.leverancier) }), euro4(check.all_in), "ob-sensor") : ""}
      </div>`);
    } else if (check.all_in !== null && check.all_in !== undefined) {
      delen.push(`<div class="ob-blok"><h4>${inkoopNu}</h4>
        ${rij("", t("All-in, van {leverancier}", { leverancier: esc(w.leverancier) }), euro4(check.all_in), "ob-totaal")}
      </div>`);
    } else {
      delen.push(`<div class="ob-blok"><h4>${t("Inkoop")}</h4><p class="ob-leeg">${t("Er is nu geen prijs: de sensoren geven niets voor dit moment.")}</p></div>`);
    }

    const tr = check.terug;
    if (tr && tr.bedrag !== null && tr.bedrag !== undefined) {
      // Dezelfde opbouw als de inkoop erboven (v0.129.1). De bewoner van de
      // eerste woning op 19-10-2026: "identiek opbouwen als het overzicht van
      // de afnameprijs. Bij afname geef je de post kale marktprijs, bij
      // teruglevering zeg je marktprijs met btw." Dus ook hier de kale prijs,
      // en de btw en de energiebelasting als eigen regel.
      const regels = terugRegels(check, tr, w);
      regels.push(rij("=", t("Per teruggeleverde kWh"), euro4(tr.bedrag), "ob-totaal"));
      delen.push(`<div class="ob-blok"><h4>${t("Teruglevering nu")}</h4>${regels.join("")}
        ${jaarNoot(check)}
      ${kostenNoot(check)}
      ${schaalNoot(check)}
        <p class="ob-noot">${tr.vast ? t("Het vaste bedrag uit je contract.") : t("Niet te controleren: {leverancier} geeft de terugleverprijs niet door. Zo rekent de coach.", { leverancier: esc(w.leverancier) })}</p>
        ${salderenNoot(check)}</div>`);
    } else {
      delen.push(`<div class="ob-blok"><h4>${t("Teruglevering")}</h4><p class="ob-leeg">${
        check.salderen ? t("Onbekend: er is nu geen all-in prijs.") : t("Onbekend: zonder kale marktprijs weet de coach niet wat teruglevering opbrengt, en kan een thuisbatterij niet handelen.")
      }</p></div>`);
    }
  }

  const zin = controleZin(check, namen);
  delen.push(`<p class="ob-controle ${zin.toon}">${esc(zin.tekst)}</p>`);
  return delen.join("");
}

/**
 * Wanneer de daluren zijn, in een zin, of leeg bij simples (een prijs). Op Contract en
 * onder de prijsgrafiek van het overzicht (v0.138.0). `pt` is het Portugese contract of
 * `pt` van `contract/check`: allebei met `tarifa` en `ciclo`.
 */
export function ptTijden(pt) {
  if (pt?.tarifa === "simples") return "";
  return pt?.ciclo === "semanal"
    ? t("Daluren doordeweeks van 00:00 tot 07:00, op zaterdag het grootste deel van de dag en op zondag de hele dag, in de tijd van Portugal.")
    : t("Daluren elke dag van 22:00 tot 08:00, in de tijd van Portugal.");
}

/**
 * Een Portugees contract (v0.137.0): per tijdvak de prijs zonder belastingen, de IEC en
 * de IVA, en wat het samen kost. `pt` van `contract/check` (`tarifas.opbouw`).
 */
export function ptBlok(check) {
  const p = check?.pt ?? {};
  const procent = (n) => `${los(Number(n) || 0)}%`;
  const regels = (p.periodos ?? []).map((r) => {
    const naam = esc(NAMEN[r.periodo] ? t(NAMEN[r.periodo]) : r.periodo);
    const som = r.energia > 0
      ? t("{energia} + IEC {iec}, plus {iva} IVA", { energia: euro4(r.energia), iec: euro4(r.iec), iva: procent(r.iva) })
      : t("niet ingevuld");
    const woord = r.periodo === p.nu ? t("{naam}, nu: {som}", { naam, som }) : `${naam}: ${som}`;
    return rij("", woord, r.all_in === null || r.all_in === undefined ? t("onbekend") : euro4(r.all_in), r.periodo === p.nu ? "ob-totaal" : "");
  });
  const tijden = ptTijden(p);
  const terug = {
    onbekend: t("Teruglevering: nog niet ingevuld, dus weet de coach niet wat het opbrengt. In Portugal is er geen salderen."),
    nenhum: t("Teruglevering: niet verkocht, dus niets. In Portugal is er geen salderen."),
    fixo: t("Teruglevering: {bedrag} per kWh, uit je verkoopcontract. In Portugal is er geen salderen.", { bedrag: euro4(check.terug) }),
    omie: t("Teruglevering: een deel van de OMIE-prijs van dat moment. In Portugal is er geen salderen."),
  }[p.excedente] ?? "";
  const vast = [];
  if (Number(p.potencia_dia) > 0) {
    vast.push(`${t("potência {bedrag} per dag", { bedrag: euro4(p.potencia_dia) })}${Number(p.kva) > 0 ? ` (${los(p.kva)} kVA)` : ""}`);
  }
  if (Number(p.servicos_mes) > 0) {
    vast.push(t("diensten {bedrag} per maand", { bedrag: `€ ${Number(p.servicos_mes).toLocaleString(locale(), { minimumFractionDigits: 2 })}` }));
  }
  return `<div class="ob-blok"><h4>${t("Stroom in Portugal")}${p.fornecedor ? `, ${esc(p.fornecedor)}` : ""}</h4>
    ${regels.join("")}
    ${tijden ? `<p class="ob-noot">${tijden}</p>` : ""}
    ${terug ? `<p class="ob-noot">${terug}</p>` : ""}
    ${vast.length ? `<p class="ob-noot">${t("Vaste kosten, zonder IVA en niet in de sturing: {kosten}.", { kosten: vast.join(", ") })}</p>` : ""}
  </div>`;
}

/** Wie bevestigde en wanneer, of dat het nog moet. */
export function bevestigdZin(check) {
  if (!check) return "";
  if (check.bevestigd) {
    const op = lang(check.bevestigd_op);
    const door = check.bevestigd_door ? esc(check.bevestigd_door) : "";
    if (door && op) return t("Bevestigd door {naam} op {datum}.", { naam: door, datum: op });
    if (door) return t("Bevestigd door {naam}.", { naam: door });
    return op ? t("Bevestigd op {datum}.", { datum: op }) : t("Bevestigd.");
  }
  return check.bevestigd_op ? t("Er is iets veranderd sinds de vorige bevestiging. Kijk het na en bevestig opnieuw.") : t("Nog niet bevestigd.");
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
