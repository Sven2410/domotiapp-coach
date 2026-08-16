/**
 * Een pdf schrijven, met de hand.
 *
 * Het rapport ging eerst via het afdrukvenster van de browser, waar "bewaren
 * als pdf" een bestemming is. Op een pc werkt dat prima. Op een telefoon niet:
 * in de app van Home Assistant, die een webweergave is en geen browser, bestaat
 * dat venster helemaal niet, en op iOS werkt afdrukken vanuit een verborgen
 * frame sowieso niet. Juist daar draaien de klanten, dus juist daar moest het
 * werken.
 *
 * Vandaar dit: de pdf wordt hier zelf gemaakt en komt als bestand naar buiten.
 * Dan is er geen afdrukvenster meer nodig en werkt het overal hetzelfde.
 *
 * Een pdf is in de kern eenvoudiger dan zijn reputatie. Het is een lijst
 * genummerde objecten, een van die objecten is een tekenopdracht in platte
 * tekst, en onderaan staat een tabel met de plek van elk object in het bestand.
 * Meer dan dat gebeurt hier niet. Geen bibliotheek dus, en geen bouwstap, wat
 * precies de twee dingen zijn die dit paneel niet heeft en niet wil.
 *
 * Twee dingen zijn met opzet zo gelaten:
 *
 * **De veertien standaardletters.** Helvetica zit in elke pdf-lezer ingebouwd,
 * dus hij hoeft niet mee in het bestand. Dat scheelt honderden kilobytes per
 * rapport en het lettertype kan nooit ontbreken. De keerzijde is dat de breedte
 * van elke letter hieronder moet staan, want zonder die maten kan niets
 * gecentreerd of rechts uitgelijnd worden. Die tabel staat er dan ook.
 *
 * **De oorsprong ligt linksboven.** Een pdf rekent vanaf linksonder met de y
 * naar boven, en dat is bij het opmaken van een rapport voortdurend achterstevoren
 * denken. Alles wat deze module naar buiten toont rekent vanaf linksboven, net
 * als een scherm, en draait het pas om op het laatste moment.
 */

/** Een staand A4, in punten: 72 per inch. */
export const A4 = { width: 595.28, height: 841.89 };

// De breedte van elke letter, in duizendsten van de tekengrootte. Dit zijn de
// maten van Adobe zelf. Een letter met een accent is in Helvetica precies even
// breed als de letter eronder, dus é telt als e en hoeft hier niet apart.
const WIDTHS = {
  normal: [
    278, 333, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
  ],
  bold: [
    278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
    975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
    333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
    611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584,
  ],
};

// Tekens buiten het gewone bereik die in een Nederlands rapport voorkomen, met
// de bytewaarde die de pdf ervoor gebruikt en hun breedte.
const EXTRA = {
  "€": { byte: 0x80, normal: 556, bold: 556 }, // euro
  "‘": { byte: 0x91, normal: 222, bold: 278 },
  "’": { byte: 0x92, normal: 222, bold: 278 },
  "“": { byte: 0x93, normal: 333, bold: 500 },
  "”": { byte: 0x94, normal: 333, bold: 500 },
  "•": { byte: 0x95, normal: 350, bold: 350 },
  "…": { byte: 0x85, normal: 1000, bold: 1000 },
  "–": { byte: 0x96, normal: 556, bold: 556 },
  "—": { byte: 0x97, normal: 1000, bold: 1000 },
};

// Een letter met een accent telt als de letter eronder: even breed, en zo is de
// tabel hierboven genoeg voor alles wat er in het rapport staat.
const KAAL = {
  "á": "a", "à": "a", "ä": "a", "â": "a", "å": "a",
  "é": "e", "è": "e", "ë": "e", "ê": "e",
  "í": "i", "ì": "i", "ï": "i", "î": "i",
  "ó": "o", "ò": "o", "ö": "o", "ô": "o",
  "ú": "u", "ù": "u", "ü": "u", "û": "u",
  "ç": "c", "ñ": "n", "ý": "y",
  "É": "E", "Ë": "E", "Ö": "O", "Ü": "U", "Ç": "C",
  "³": "3", "²": "2", "°": "o", "×": "x",
};

/** Hoe breed een stuk tekst wordt, in punten. */
export function textWidth(text, size, bold = false) {
  const soort = bold ? "bold" : "normal";
  let duizendsten = 0;
  for (const teken of String(text)) {
    const extra = EXTRA[teken];
    if (extra) {
      duizendsten += extra[soort];
      continue;
    }
    const kaal = KAAL[teken] ?? teken;
    const code = kaal.charCodeAt(0);
    duizendsten += code >= 32 && code <= 126 ? WIDTHS[soort][code - 32] : 556;
  }
  return (duizendsten * size) / 1000;
}

/**
 * Tekst in regels breken die binnen een breedte passen.
 *
 * Breekt op spaties. Past een enkel woord niet, dan gaat het toch op zijn eigen
 * regel: een woord middenin hakken leest slechter dan een regel die iets
 * uitsteekt, en in dit rapport komen zulke woorden niet voor.
 */
export function wrap(text, size, maxWidth, bold = false) {
  const regels = [];
  for (const alinea of String(text).split("\n")) {
    let regel = "";
    for (const woord of alinea.split(/\s+/).filter(Boolean)) {
      const kandidaat = regel ? `${regel} ${woord}` : woord;
      if (regel && textWidth(kandidaat, size, bold) > maxWidth) {
        regels.push(regel);
        regel = woord;
      } else {
        regel = kandidaat;
      }
    }
    regels.push(regel);
  }
  return regels;
}

/** "#1a2b3c" als de drie getallen tussen 0 en 1 die een pdf wil. */
function kleur(hex) {
  const h = String(hex).replace("#", "");
  const vol = h.length === 3 ? [...h].map((c) => c + c).join("") : h;
  const n = parseInt(vol, 16);
  return [
    ((n >> 16) & 255) / 255,
    ((n >> 8) & 255) / 255,
    (n & 255) / 255,
  ]
    .map((v) => v.toFixed(3))
    .join(" ");
}

/** Een getal zoals een pdf het leest: punt als scheiding, niet te veel cijfers. */
function num(value) {
  return Number(value).toFixed(2).replace(/\.?0+$/, "") || "0";
}

/** Tekst als bytes, met de haakjes en de schuine streep ontzien. */
function pdfString(text) {
  const bytes = [0x28]; // (
  for (const teken of String(text)) {
    const extra = EXTRA[teken];
    let code;
    if (extra) {
      code = extra.byte;
    } else {
      code = teken.charCodeAt(0);
      if (code > 255) code = (KAAL[teken] ?? "?").charCodeAt(0);
    }
    if (code === 0x28 || code === 0x29 || code === 0x5c) bytes.push(0x5c);
    bytes.push(code);
  }
  bytes.push(0x29); // )
  return new Uint8Array(bytes);
}

/** Platte tekst als bytes, één byte per teken. */
function bytes(text) {
  const uit = new Uint8Array(text.length);
  for (let i = 0; i < text.length; i += 1) uit[i] = text.charCodeAt(i) & 255;
  return uit;
}

/** Een pdf in wording. */
export class Pdf {
  /**
   * @param {{width?: number, height?: number}} [formaat] Standaard een staand A4.
   */
  constructor(formaat = {}) {
    this.width = formaat.width ?? A4.width;
    this.height = formaat.height ?? A4.height;
    /** @type {string[][]} de tekenopdrachten per bladzijde */
    this.pages = [[]];
    /** @type {{data: Uint8Array, w: number, h: number}[]} */
    this.images = [];
  }

  /** De opdrachten van de bladzijde waar nu op getekend wordt. */
  get current() {
    return this.pages[this.pages.length - 1];
  }

  /** Een nieuwe bladzijde beginnen. */
  page() {
    this.pages.push([]);
    return this;
  }

  /** Van boven gerekend naar de rekenwijze van de pdf zelf. */
  y_(y) {
    return this.height - y;
  }

  /**
   * Tekst neerzetten.
   *
   * @param {number} x Links, of het punt waar `align` omheen draait.
   * @param {number} y De onderkant van de letters, vanaf de bovenrand gerekend.
   */
  text(x, y, text, opties = {}) {
    const { size = 10, bold = false, color = "#000000", align = "left" } = opties;
    const inhoud = String(text ?? "");
    if (!inhoud) return this;

    let links = x;
    if (align === "right") links = x - textWidth(inhoud, size, bold);
    else if (align === "center") links = x - textWidth(inhoud, size, bold) / 2;

    this.current.push(
      `BT /${bold ? "F2" : "F1"} ${num(size)} Tf ${kleur(color)} rg ` +
        `${num(links)} ${num(this.y_(y))} Td `,
      pdfString(inhoud),
      " Tj ET\n"
    );
    return this;
  }

  /** Meerdere regels onder elkaar. Geeft terug waar de volgende regel begint. */
  lines(x, y, regels, opties = {}) {
    const hoogte = opties.leading ?? (opties.size ?? 10) * 1.35;
    let cursor = y;
    for (const regel of regels) {
      this.text(x, cursor, regel, opties);
      cursor += hoogte;
    }
    return cursor;
  }

  /** Een vlak, gevuld of met een lijn eromheen. */
  rect(x, y, w, h, opties = {}) {
    const { fill, stroke, width = 0.6, radius = 0 } = opties;
    if (!fill && !stroke) return this;

    const teken = radius > 0 ? this.rounded_(x, y, w, h, radius) : `${num(x)} ${num(this.y_(y + h))} ${num(w)} ${num(h)} re`;
    const stijl = fill && stroke ? "B" : fill ? "f" : "S";
    this.current.push(
      `q ${fill ? `${kleur(fill)} rg ` : ""}${stroke ? `${kleur(stroke)} RG ${num(width)} w ` : ""}` +
        `${teken} ${stijl} Q\n`
    );
    return this;
  }

  /** Een rechthoek met ronde hoeken, in vier bochten. */
  rounded_(x, y, w, h, r) {
    const straal = Math.min(r, w / 2, h / 2);
    const k = straal * 0.5523; // waarmee een boog een kwartcirkel benadert
    const b = this.y_(y + h);
    const t = this.y_(y);
    const l = x;
    const rechts = x + w;
    return [
      `${num(l + straal)} ${num(b)} m`,
      `${num(rechts - straal)} ${num(b)} l`,
      `${num(rechts - straal + k)} ${num(b)} ${num(rechts)} ${num(b + straal - k)} ${num(rechts)} ${num(b + straal)} c`,
      `${num(rechts)} ${num(t - straal)} l`,
      `${num(rechts)} ${num(t - straal + k)} ${num(rechts - straal + k)} ${num(t)} ${num(rechts - straal)} ${num(t)} c`,
      `${num(l + straal)} ${num(t)} l`,
      `${num(l + straal - k)} ${num(t)} ${num(l)} ${num(t - straal + k)} ${num(l)} ${num(t - straal)} c`,
      `${num(l)} ${num(b + straal)} l`,
      `${num(l)} ${num(b + straal - k)} ${num(l + straal - k)} ${num(b)} ${num(l + straal)} ${num(b)} c`,
      "h",
    ].join(" ");
  }

  /** Een lijn. */
  line(x1, y1, x2, y2, opties = {}) {
    const { color = "#000000", width = 0.6 } = opties;
    this.current.push(
      `q ${kleur(color)} RG ${num(width)} w ${num(x1)} ${num(this.y_(y1))} m ` +
        `${num(x2)} ${num(this.y_(y2))} l S Q\n`
    );
    return this;
  }

  /**
   * Een afbeelding, aangeleverd als jpeg.
   *
   * Jpeg omdat een pdf dat formaat ongewijzigd mag doorgeven: de bytes gaan er
   * zo in als ze zijn. Een png zou eerst uitgepakt moeten worden en daarna weer
   * ingepakt, en dat is veel werk voor een logo.
   */
  image(x, y, w, h, jpeg, px, py) {
    this.images.push({ data: jpeg, w: px, h: py });
    const naam = `Im${this.images.length}`;
    this.current.push(
      `q ${num(w)} 0 0 ${num(h)} ${num(x)} ${num(this.y_(y + h))} cm /${naam} Do Q\n`
    );
    return this;
  }

  /** Het hele bestand, klaar om te bewaren. */
  blob() {
    return new Blob([this.build_()], { type: "application/pdf" });
  }

  /**
   * De objecten aan elkaar schrijven en de tabel eronder zetten.
   *
   * De volgorde ligt vast omdat de nummers verwijzingen zijn: eerst de catalogus
   * en de bladzijdelijst, dan de twee letters, dan per bladzijde een object voor
   * de bladzijde zelf en een voor wat erop staat, en tot slot de afbeeldingen.
   */
  build_() {
    const objecten = [];
    const aantal = this.pages.length;
    const eerstePagina = 5;
    const eersteAfbeelding = eerstePagina + aantal * 2;

    const paginaIds = this.pages.map((_, i) => eerstePagina + i * 2);
    const bronnen =
      `<< /Font << /F1 3 0 R /F2 4 0 R >>` +
      (this.images.length
        ? ` /XObject << ${this.images
            .map((_, i) => `/Im${i + 1} ${eersteAfbeelding + i} 0 R`)
            .join(" ")} >>`
        : "") +
      " >>";

    objecten[1] = bytes("<< /Type /Catalog /Pages 2 0 R >>");
    objecten[2] = bytes(
      `<< /Type /Pages /Count ${aantal} /Kids [${paginaIds
        .map((id) => `${id} 0 R`)
        .join(" ")}] >>`
    );
    objecten[3] = bytes(
      "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    );
    objecten[4] = bytes(
      "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    );

    this.pages.forEach((opdrachten, i) => {
      const paginaId = eerstePagina + i * 2;
      objecten[paginaId] = bytes(
        `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${num(this.width)} ${num(this.height)}] ` +
          `/Resources ${bronnen} /Contents ${paginaId + 1} 0 R >>`
      );
      const stroom = samenvoegen(
        opdrachten.map((deel) => (typeof deel === "string" ? bytes(deel) : deel))
      );
      objecten[paginaId + 1] = samenvoegen([
        bytes(`<< /Length ${stroom.length} >>\nstream\n`),
        stroom,
        bytes("\nendstream"),
      ]);
    });

    this.images.forEach((afbeelding, i) => {
      objecten[eersteAfbeelding + i] = samenvoegen([
        bytes(
          `<< /Type /XObject /Subtype /Image /Width ${afbeelding.w} /Height ${afbeelding.h} ` +
            `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode ` +
            `/Length ${afbeelding.data.length} >>\nstream\n`
        ),
        afbeelding.data,
        bytes("\nendstream"),
      ]);
    });

    // --- alles achter elkaar, en onthouden waar elk object begint ---
    const delen = [bytes("%PDF-1.4\n%âãÏÓ\n")];
    let positie = delen[0].length;
    const plek = [];

    for (let id = 1; id < objecten.length; id += 1) {
      plek[id] = positie;
      const kop = bytes(`${id} 0 obj\n`);
      const staart = bytes("\nendobj\n");
      delen.push(kop, objecten[id], staart);
      positie += kop.length + objecten[id].length + staart.length;
    }

    const start = positie;
    const tabel = [
      `xref\n0 ${objecten.length}\n`,
      "0000000000 65535 f \n",
      ...plek.slice(1).map((p) => `${String(p).padStart(10, "0")} 00000 n \n`),
      `trailer\n<< /Size ${objecten.length} /Root 1 0 R >>\nstartxref\n${start}\n%%EOF\n`,
    ].join("");
    delen.push(bytes(tabel));

    return samenvoegen(delen);
  }
}

/** Losse stukken bytes achter elkaar. */
function samenvoegen(delen) {
  const totaal = delen.reduce((som, deel) => som + deel.length, 0);
  const uit = new Uint8Array(totaal);
  let op = 0;
  for (const deel of delen) {
    uit.set(deel, op);
    op += deel.length;
  }
  return uit;
}

/**
 * Een afbeelding van een adres ophalen als jpeg, klaar om in een pdf te gaan.
 *
 * Via een tekenvlak, want daarmee komt elk formaat dat de browser kan tonen er
 * als jpeg weer uit. Op een witte ondergrond, omdat een doorzichtige png anders
 * zwart wordt: papier is wit en een rapport hoort dat ook te zijn.
 */
export async function jpegVan(url, maxBreedte = 600) {
  const plaatje = new Image();
  plaatje.crossOrigin = "anonymous";
  await new Promise((klaar, mis) => {
    plaatje.onload = klaar;
    plaatje.onerror = mis;
    plaatje.src = url;
  });

  const schaal = Math.min(1, maxBreedte / plaatje.naturalWidth);
  const breed = Math.max(1, Math.round(plaatje.naturalWidth * schaal));
  const hoog = Math.max(1, Math.round(plaatje.naturalHeight * schaal));

  const vlak = document.createElement("canvas");
  vlak.width = breed;
  vlak.height = hoog;
  const pen = vlak.getContext("2d");
  pen.fillStyle = "#ffffff";
  pen.fillRect(0, 0, breed, hoog);
  pen.drawImage(plaatje, 0, 0, breed, hoog);

  const base64 = vlak.toDataURL("image/jpeg", 0.92).split(",")[1];
  const ruw = atob(base64);
  const data = new Uint8Array(ruw.length);
  for (let i = 0; i < ruw.length; i += 1) data[i] = ruw.charCodeAt(i);

  return { data, w: breed, h: hoog };
}

/**
 * Het bestand bij de klant afleveren, op de manier die dit apparaat aankan.
 *
 * Drie wegen, want geen enkele werkt overal. Op een telefoon is het deelvenster
 * de beste: daar staan "bewaren in bestanden" en "afdrukken" allebei in, en de
 * app van Home Assistant hoeft er niets voor te kunnen. Lukt dat niet, dan een
 * gewone download, wat op een pc juist het prettigst is. En anders het bestand
 * gewoon openen, dan kan de klant het van daaruit bewaren.
 *
 * Waarom niet altijd delen als het kan: op een pc kan het ook, en dan krijgt
 * iemand die op Rapport klikt ineens het deelvenster van Windows te zien in
 * plaats van een bestand in zijn downloadmap. Dat is geen verbetering van iets
 * wat daar al goed ging. Vandaar dat de aanraakbediening de doorslag geeft: die
 * onderscheidt een telefoon of tablet van een computer met een muis, en dat is
 * precies de grens waar het antwoord verandert.
 *
 * @returns {Promise<"gedeeld"|"afgebroken"|"gedownload"|"geopend"|"mislukt">}
 */
export async function afleveren(blob, bestandsnaam) {
  const bestand = new File([blob], bestandsnaam, { type: "application/pdf" });
  const opAanraking = window.matchMedia?.("(pointer: coarse)")?.matches ?? false;

  if (opAanraking && navigator.canShare?.({ files: [bestand] })) {
    try {
      await navigator.share({ files: [bestand], title: bestandsnaam });
      return "gedeeld";
    } catch (fout) {
      // Wie het venster wegtikt heeft een keuze gemaakt, en die staat niet toe
      // dat er daarna alsnog ongevraagd een bestand binnenkomt.
      if (fout?.name === "AbortError") return "afgebroken";
    }
  }

  const adres = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    if ("download" in link) {
      link.href = adres;
      link.download = bestandsnaam;
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(adres), 60_000);
      return "gedownload";
    }
    const venster = window.open(adres, "_blank");
    setTimeout(() => URL.revokeObjectURL(adres), 60_000);
    return venster ? "geopend" : "mislukt";
  } catch {
    URL.revokeObjectURL(adres);
    return "mislukt";
  }
}
