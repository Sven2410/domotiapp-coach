/**
 * Het rapport, opgemaakt als pdf.
 *
 * Wat hier binnenkomt zijn alleen nog cijfers en woorden: de Historie-sectie
 * heeft al uitgerekend wat er in staat, en dit bestand bepaalt alleen nog waar
 * het komt te staan. Die scheiding is met opzet, want de opmaak van een
 * bladzijde is fijnwerk en rekenwerk hoort daar niet doorheen te lopen.
 *
 * De tekening volgt het scherm: dezelfde stapeling in de grafiek, dezelfde
 * kleuren voor dezelfde dingen. Wie het overzicht kent moet het rapport zonder
 * uitleg kunnen lezen. Wat wel anders is, is de achtergrond. Op papier is een
 * donker thema onbruikbaar, dus het rapport is licht.
 */

import { A4, Pdf, jpegVan, textWidth, wrap } from "./pdf.js";

const MARGE = 40;
const BREEDTE = A4.width - MARGE * 2;
const ONDERKANT = A4.height - 54;

const KLEUR = {
  inkt: "#16202b",
  zacht: "#5d6b7a",
  lijn: "#d9e1e9",
  vlak: "#f4f7fa",
  zon: "#dc7300",
  net: "#0f7fbb",
  terug: "#a30fae",
};

/**
 * Een bladzijde die zijn eigen cursor bijhoudt.
 *
 * De reden dat dit een klasje is en geen losse functies: bij het opmaken van een
 * rapport is de vraag "past dit nog?" er bij elk onderdeel weer, en die vraag op
 * elke aanroeplocatie beantwoorden is precies hoe een rapport ontstaat waarin
 * een kop onderaan een bladzijde staat en de tabel erbij op de volgende.
 */
class Vel {
  constructor(pdf, voet) {
    this.pdf = pdf;
    this.voet = voet;
    this.y = MARGE;
    this.paginas = 1;
  }

  /** Zorgen dat er nog zo veel ruimte is, en anders een nieuwe bladzijde. */
  ruimte(hoogte) {
    if (this.y + hoogte <= ONDERKANT) return false;
    this.nieuw();
    return true;
  }

  nieuw() {
    this.voetregel();
    this.pdf.page();
    this.paginas += 1;
    this.y = MARGE;
    return this;
  }

  voetregel() {
    const y = A4.height - 32;
    this.pdf.line(MARGE, y - 12, MARGE + BREEDTE, y - 12, { color: KLEUR.lijn, width: 0.5 });
    this.pdf.text(MARGE, y, this.voet, { size: 8, color: KLEUR.zacht });
    this.pdf.text(MARGE + BREEDTE, y, `Bladzijde ${this.paginas}`, {
      size: 8,
      color: KLEUR.zacht,
      align: "right",
    });
  }

  /** Een kop, met de regel eronder die het scherm ook heeft. */
  kop(tekst) {
    this.ruimte(46);
    this.y += 14;
    this.pdf.text(MARGE, this.y + 11, tekst, { size: 13, bold: true, color: KLEUR.inkt });
    this.y += 18;
    this.pdf.line(MARGE, this.y, MARGE + BREEDTE, this.y, { color: KLEUR.lijn, width: 0.8 });
    this.y += 12;
  }

  /** Een stuk uitleg in kleine letters. */
  uitleg(tekst) {
    if (!tekst) return;
    const regels = wrap(tekst, 8, BREEDTE);
    this.ruimte(regels.length * 11 + 8);
    this.y = this.pdf.lines(MARGE, this.y + 8, regels, {
      size: 8,
      color: KLEUR.zacht,
      leading: 11,
    });
    this.y += 2;
  }
}

/** De kop van de eerste bladzijde: logo, merk, woning en periode. */
function schrijfHoofd(pdf, vel, gegevens, logo) {
  const boven = vel.y;

  if (logo) {
    const hoog = 30;
    pdf.image(MARGE, boven, (logo.w / logo.h) * hoog, hoog, logo.data, logo.w, logo.h);
  }
  const links = MARGE + (logo ? (logo.w / logo.h) * 30 + 12 : 0);

  pdf.text(links, boven + 13, "DomotiApp", { size: 14, bold: true, color: KLEUR.inkt });
  pdf.text(links + textWidth("DomotiApp ", 14, true), boven + 13, "Coach", {
    size: 14,
    bold: true,
    color: KLEUR.net,
  });
  if (gegevens.woning) {
    pdf.text(links, boven + 26, gegevens.woning, { size: 9, color: KLEUR.zacht });
  }

  pdf.text(MARGE + BREEDTE, boven + 13, gegevens.periode, {
    size: 14,
    bold: true,
    color: KLEUR.inkt,
    align: "right",
  });
  pdf.text(MARGE + BREEDTE, boven + 26, gegevens.korrel, {
    size: 9,
    color: KLEUR.zacht,
    align: "right",
  });

  vel.y = boven + 40;
  pdf.line(MARGE, vel.y, MARGE + BREEDTE, vel.y, { color: KLEUR.lijn, width: 0.8 });
  vel.y += 6;
}

/**
 * Een rij vakjes met een getal erin.
 *
 * Vier op een regel, en bij minder dan vier gaan ze niet uitrekken: een vakje
 * dat de halve bladzijde beslaat omdat er toevallig twee cijfers zijn, leest als
 * een fout.
 */
function schrijfVakjes(pdf, vel, vakjes) {
  if (!vakjes.length) return;

  const perRij = Math.min(4, Math.max(2, vakjes.length));
  const tussen = 10;
  const breed = (BREEDTE - tussen * (perRij - 1)) / perRij;
  const hoog = 48;

  vakjes.forEach((vakje, i) => {
    if (i % perRij === 0) vel.ruimte(hoog + 4);
    const rij = Math.floor(i / perRij);
    const kolom = i % perRij;
    const x = MARGE + kolom * (breed + tussen);
    const y = vel.y + rij * (hoog + tussen);

    pdf.rect(x, y, breed, hoog, { fill: KLEUR.vlak, radius: 6 });
    pdf.text(x + 12, y + 17, vakje.label.toUpperCase(), { size: 7, color: KLEUR.zacht });
    pdf.text(x + 12, y + 36, vakje.waarde, { size: 15, bold: true, color: KLEUR.inkt });
  });

  const rijen = Math.ceil(vakjes.length / perRij);
  vel.y += rijen * hoog + (rijen - 1) * tussen;
}

/**
 * De grafiek: dezelfde gestapelde balken als op het scherm.
 *
 * Eigen zon onderin, ingekochte stroom daarbovenop, teruglevering onder de
 * nullijn. De volgorde is niet willekeurig: onderaan staat het deel dat niets
 * gekost heeft, dus hoe hoger het blauw begint, hoe duurder de dag was.
 */
function schrijfGrafiek(pdf, vel, rijen, metZon) {
  const hoog = 170;
  vel.ruimte(hoog + 30);

  const boven = vel.y;
  const onder = boven + hoog;

  const op = Math.max(...rijen.map((r) => r.own + r.bought), 0.001);
  const neer = Math.max(...rijen.map((r) => r.sold), 0);
  const spanne = (op + neer) * 1.05 || 1;
  const nul = boven + ((op * 1.05) / spanne) * hoog;
  const schaal = hoog / spanne;

  const kolom = Math.min(BREEDTE / rijen.length, 46);
  const inspring = MARGE + (BREEDTE - kolom * rijen.length) / 2;
  const kier = kolom < 9 ? 1 : Math.min(6, kolom * 0.22);
  const balk = Math.max(1.2, kolom - kier);
  const bocht = Math.min(3, balk / 2);

  rijen.forEach((rij, i) => {
    const x = inspring + i * kolom + (kolom - balk) / 2;
    const eigen = rij.own * schaal;
    const gekocht = rij.bought * schaal;
    const verkocht = rij.sold * schaal;

    if (eigen > 0.4) {
      pdf.rect(x, nul - eigen, balk, eigen, {
        fill: KLEUR.zon,
        radius: gekocht > 0.4 ? 0 : bocht,
      });
    }
    if (gekocht > 0.4) {
      pdf.rect(x, nul - eigen - gekocht, balk, gekocht, { fill: KLEUR.net, radius: bocht });
    }
    if (verkocht > 0.4) {
      pdf.rect(x, nul, balk, verkocht, { fill: KLEUR.terug, radius: bocht });
    }
  });

  pdf.line(MARGE, nul, MARGE + BREEDTE, nul, { color: KLEUR.lijn, width: 0.8 });

  // Niet elk bijschrift past, dus er wordt overgeslagen tot ze uit elkaar staan.
  const breedste = Math.max(...rijen.map((r) => textWidth(r.label, 7)));
  const elke = Math.max(1, Math.ceil((breedste + 6) / kolom));
  rijen.forEach((rij, i) => {
    if (i % elke !== 0) return;
    pdf.text(inspring + i * kolom + kolom / 2, onder + 12, rij.label, {
      size: 7,
      color: KLEUR.zacht,
      align: "center",
    });
  });

  vel.y = onder + 18;

  // De legenda, op één regel en gecentreerd onder de grafiek.
  const stukken = [
    metZon ? { kleur: KLEUR.zon, tekst: "Eigen zon gebruikt" } : null,
    { kleur: KLEUR.net, tekst: "Van het net" },
    { kleur: KLEUR.terug, tekst: "Naar het net" },
  ].filter(Boolean);

  const totaal = stukken.reduce((som, s) => som + 10 + textWidth(s.tekst, 8) + 16, -16);
  let x = MARGE + (BREEDTE - totaal) / 2;
  for (const stuk of stukken) {
    pdf.rect(x, vel.y + 2, 7, 7, { fill: stuk.kleur, radius: 2 });
    pdf.text(x + 11, vel.y + 8, stuk.tekst, { size: 8, color: KLEUR.zacht });
    x += 10 + textWidth(stuk.tekst, 8) + 16;
  }
  vel.y += 16;
}

/**
 * Een tabel, met de kop die zichzelf herhaalt op elke bladzijde.
 *
 * Zonder die herhaling is een tabel van een heel jaar op de tweede bladzijde een
 * raadsel: twaalf kolommen getallen waar niet meer bij staat wat ze betekenen.
 */
function schrijfTabel(pdf, vel, kop, rijen, totaal) {
  const regel = 16;
  const { breedtes, maat } = kolommen(kop, rijen, totaal);
  const xVan = (i) => MARGE + breedtes.slice(0, i).reduce((a, b) => a + b, 0);

  /** Eén regel cellen, links de naam en rechts de getallen. */
  const schrijfRij = (cellen, opties) => {
    cellen.forEach((cel, i) => {
      const rechts = i > 0;
      // Wat niet past wordt ingekort. In een echt rapport gebeurt dat nooit,
      // want de kolommen zijn hierboven op hun inhoud gemeten; dit is het
      // vangnet voor het geval er ooit een kolom bij komt. Twee getallen die
      // tegen elkaar aan geplakt staan zijn onleesbaar, en een getal met een
      // beletselteken erachter is zichtbaar onaf. Dat laatste is beter.
      const tekst = inkorten(cel, opties.size, breedtes[i] - KANTLIJN * 2, opties.bold);
      pdf.text(rechts ? xVan(i) + breedtes[i] - KANTLIJN : xVan(i) + KANTLIJN, vel.y + 10, tekst, {
        ...opties,
        color: i === 0 && opties.eerste ? opties.eerste : opties.color,
        align: rechts ? "right" : "left",
      });
    });
  };

  const schrijfKop = () => {
    pdf.rect(MARGE, vel.y, BREEDTE, regel + 4, { fill: KLEUR.vlak, radius: 3 });
    vel.y += 3;
    schrijfRij(kop, { size: maat, bold: true, color: KLEUR.zacht });
    vel.y += regel + 5;
  };

  vel.ruimte(regel * 4);
  schrijfKop();

  for (const rij of rijen) {
    if (vel.ruimte(regel + 24)) schrijfKop();
    // De eerste kolom draagt de naam en staat donkerder, zodat het oog een rij
    // kan volgen zonder liniaal.
    schrijfRij(rij, { size: maat, color: KLEUR.zacht, eerste: KLEUR.inkt });
    vel.y += regel;
    pdf.line(MARGE, vel.y - 3, MARGE + BREEDTE, vel.y - 3, { color: KLEUR.lijn, width: 0.4 });
  }

  if (totaal) {
    if (vel.ruimte(regel + 24)) schrijfKop();
    vel.y += 2;
    schrijfRij(totaal, { size: maat, bold: true, color: KLEUR.inkt });
    vel.y += regel;
  }
  vel.y += 4;
}

/** Wat er links en rechts van een cel vrij blijft. */
const KANTLIJN = 6;

/**
 * Hoe breed elke kolom moet zijn, en in welke lettergrootte.
 *
 * Kolommen van gelijke breedte lijken netjes tot er een jaarrapport uitrolt:
 * negen kolommen, en dan lopen "Van het net" en "Naar het net" dwars door
 * elkaar heen en plakt de totaalregel aan elkaar tot één lange reeks cijfers.
 * Dus wordt hier eerst gemeten wat er werkelijk in staat, koppen en totaalregel
 * meegerekend, want juist die zijn het breedst.
 *
 * Past het niet, dan gaat de letter omlaag in plaats van de kolom. Een tabel die
 * een maatje kleiner staat leest nog prima; een tabel waarin twee getallen tegen
 * elkaar aan staan leest niemand meer. Pas als ook de kleinste maat niet helpt
 * worden de kolommen alsnog ingedrukt, want dan is er niets beters over.
 */
function kolommen(kop, rijen, totaal) {
  const alles = [kop, ...rijen, ...(totaal ? [totaal] : [])];

  for (let maat = 8.5; maat >= 6.5; maat -= 0.25) {
    const nodig = kop.map((_, i) =>
      Math.max(
        ...alles.map((rij) => textWidth(rij[i] ?? "", maat, rij === kop || rij === totaal))
      ) + KANTLIJN * 2
    );
    const samen = nodig.reduce((a, b) => a + b, 0);
    if (samen <= BREEDTE) {
      // Wat overblijft gaat naar de eerste kolom: daar staan de namen, en die
      // mogen ademen.
      nodig[0] += BREEDTE - samen;
      return { breedtes: nodig, maat };
    }
  }

  // Zelfs op de kleinste maat te breed. Dan gaat het van de naamkolom af: die
  // kan worden ingekort en een getal niet. De getallen houden dus hun ruimte en
  // wat overblijft is voor de naam.
  const maat = 6.5;
  const nodig = kop.map((_, i) =>
    Math.max(...alles.map((rij) => textWidth(rij[i] ?? "", maat, rij === kop || rij === totaal))) +
    KANTLIJN * 2
  );
  const rest = nodig.slice(1).reduce((a, b) => a + b, 0);
  if (rest <= BREEDTE - NAAM_MINIMAAL) {
    nodig[0] = BREEDTE - rest;
    return { breedtes: nodig, maat };
  }

  // En als zelfs de getallen alleen al niet passen, is er niets beters over dan
  // evenredig indrukken. Dat kan in dit rapport niet voorkomen, want de koppen
  // liggen vast, maar het is beter dan een tabel die de bladzijde uit loopt.
  const samen = nodig.reduce((a, b) => a + b, 0);
  return { breedtes: nodig.map((w) => (w / samen) * BREEDTE), maat };
}

/** Hoe smal de naamkolom hoogstens mag worden voor hij onleesbaar wordt. */
const NAAM_MINIMAAL = 60;

/** Tekst die niet past, met een beletselteken erachter. */
function inkorten(tekst, maat, breedte, vet = false) {
  const woord = String(tekst ?? "");
  if (textWidth(woord, maat, vet) <= breedte) return woord;

  let uit = woord;
  while (uit.length > 1 && textWidth(`${uit}…`, maat, vet) > breedte) {
    uit = uit.slice(0, -1);
  }
  return `${uit.trimEnd()}…`;
}

/**
 * Het hele rapport bouwen.
 *
 * @param {object} gegevens Alles wat erin komt, al uitgerekend en al opgemaakt
 *   als tekst. Zie `reportData_` in de Historie-sectie voor wat er in zit.
 * @returns {Promise<Blob>}
 */
export async function reportPdf(gegevens) {
  const pdf = new Pdf();
  const vel = new Vel(
    pdf,
    gegevens.woning
      ? `${gegevens.woning}, gemaakt op ${gegevens.gemaakt}`
      : `Gemaakt op ${gegevens.gemaakt}`
  );

  // Een logo dat niet laadt is geen reden om geen rapport te maken.
  let logo = null;
  try {
    logo = await jpegVan(gegevens.logoUrl, 300);
  } catch {
    logo = null;
  }

  schrijfHoofd(pdf, vel, gegevens, logo);

  vel.kop("Energie");
  schrijfVakjes(pdf, vel, gegevens.energie);

  if (gegevens.geld?.length) {
    vel.kop("In geld");
    schrijfVakjes(pdf, vel, gegevens.geld);
    vel.uitleg(gegevens.geldUitleg);
  }

  if (gegevens.verloop?.length) {
    vel.kop("Verloop");
    schrijfGrafiek(pdf, vel, gegevens.verloop, gegevens.metZon);
  }

  if (gegevens.apparaten?.rijen?.length) {
    vel.kop("Per apparaat");
    schrijfTabel(pdf, vel, gegevens.apparaten.kop, gegevens.apparaten.rijen);
    vel.uitleg(gegevens.apparaten.uitleg);
  }

  if (gegevens.cijfers?.rijen?.length) {
    vel.kop("Alle cijfers");
    schrijfTabel(
      pdf,
      vel,
      gegevens.cijfers.kop,
      gegevens.cijfers.rijen,
      gegevens.cijfers.totaal
    );
  }

  vel.voetregel();
  return pdf.blob();
}
