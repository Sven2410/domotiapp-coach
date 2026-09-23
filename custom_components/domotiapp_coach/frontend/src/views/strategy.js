/**
 * Strategie -- what the coach should do on its own, without being watched.
 *
 * Sinds 06-09-2026 alleen nog het niveau: hoeveel de coach zelf mag. De
 * melding "Zware belasting" en wie hem krijgt staan in het tabje Meldingen
 * (`views/notifications.js`), samen met de andere soorten; de eigenaar wilde dat
 * twee in een. De schema's van apparaten staan sinds 27-08-2026 op de kaart
 * van het apparaat zelf.
 */

import { define } from "../base.js";
import { deviceLabelMap } from "../devices.js";
import { icons } from "../icons.js";
import { regelUitleg, zonRegels } from "../voorrang.js";
import {
  DacEditorElement,
  adminNoticeHtml,
  editorCss,
  saveBarHtml,
} from "./editor-base.js";

/**
 * Hoever de coach mag gaan.
 *
 * Geen strategie maar een mate van vertrouwen, en dat zijn twee vragen: een
 * strategie zegt waar hij op mikt, dit zegt hoeveel hij zelf mag. Voorstellen
 * is de stap die er in de praktijk toe doet: daarmee kun je een week meekijken
 * of de sommen kloppen voordat je hem loslaat.
 */
const LEVELS = [
  {
    key: "read",
    label: "Alleen uitlezen",
    blurb: "Je ziet wat je huis doet. De coach zegt en doet verder niets.",
  },
  {
    key: "advise",
    label: "Adviseren",
    blurb: "Hij vertelt wat er te winnen valt, maar raakt niets aan.",
  },
  {
    key: "propose",
    label: "Voorstellen",
    blurb: "Hij rekent het uit en laat het zien. Pas als jij ja zegt, voert hij het uit.",
  },
  {
    key: "steer",
    label: "Zelf sturen",
    blurb: "Hij doet het en vertelt achteraf wat hij gedaan heeft.",
  },
];

class DacViewStrategy extends DacEditorElement {
  static sections = ["strategy"];

  // Its own command, and one that is not admin-only. How far the coach may go
  // is a decision of whoever lives in the house, and that is usually not an
  // administrator in Home Assistant.
  static saveCommand = "domotiapp_coach/strategy/set";
  static savePayload = "strategy";

  /** Everyone, hence the command above. */
  canEdit_() {
    return true;
  }

  /**
   * Whether this user can reach Apparaten at all.
   *
   * Customers cannot: that section is hidden for them. So every sentence here
   * that sends somebody to it has to say something else to them, or it points
   * at a screen they will never find.
   */
  isAdmin_() {
    return this.hass_?.user?.is_admin !== false;
  }

  /** Er zijn geen subschermen meer; een oud pad wordt aangenomen en genegeerd. */
  set subroute(value) {}

  render() {
    return `
      <div class="wrap">
        <header class="intro">
          <div class="eyebrow">Strategie</div>
          <h1>Wat de coach uit zichzelf doet</h1>
          <p>Hier bepaal je hoeveel de coach zelf mag. Wie welke berichten krijgt staat onder Meldingen.</p>
        </header>

        ${adminNoticeHtml}

        <section class="card">
          <h2>${icons.compass} Hoeveel doet de coach zelf?</h2>
          <p class="hint">Van alleen meekijken tot zelf schakelen. Begin gerust bij Voorstellen: dan zie je precies wat hij zou doen en gebeurt er niets zonder jouw akkoord.</p>
          <div class="fields">
            <div class="segmented levels" id="level">
              ${LEVELS.map(
                (item) => `
                <button type="button" data-level="${item.key}" aria-pressed="false">
                  <strong>${item.label}</strong>
                  ${item.blurb}
                </button>`
              ).join("")}
            </div>

            <p class="hint">
              Waar hij op mikt staat vast: zo min mogelijk geld uitgeven. De coach legt
              alle manieren om je auto vol te krijgen naast elkaar, van je eigen zon tot
              elk uur tussen nu en je klaar-tijd, en kiest de goedkoopste. Je eigen zon
              wint daarbij vanzelf zodra hij goedkoper is dan het net.
            </p>
          </div>
        </section>

        <!-- De voorrang bij zonoverschot (v0.92.0). De bewoner van de eerste
             woning op 23-09-2026: "niet automatisch de auto voorrang geven op
             alles dus"; te verslepen zoals de kaarten op het overzicht. -->
        <section class="card">
          <h2>${icons.sun} Voorrang bij zonoverschot</h2>
          <p class="hint">
            Wie het overschot van je zonnepanelen als eerste krijgt, van boven naar beneden.
            Elke regel krijgt wat hij kan opnemen tot zijn grens, en wat er dan over is gaat
            naar de volgende. Dit geldt alleen voor overschot: wat er volgens een planning van
            het net geladen wordt staat hier los van.
          </p>
          <ol class="zon-lijst" id="zon-lijst"></ol>
          <div class="zon-voeg">
            <select id="zon-nieuw" aria-label="Apparaat voor een nieuwe regel"></select>
            <button type="button" id="zon-voeg">${icons.plus}<span>Regel toevoegen</span></button>
            <button type="button" class="zacht" id="zon-standaard">Standaard terugzetten</button>
          </div>
        </section>

        <!-- De nachtstrategie (v0.90.0), in de woorden van de bewoner van de
             eerste woning op 23-09-2026. -->
        <section class="card">
          <h2>${icons.thuisbatterij} Nachtstrategie</h2>
          <label class="check" for="night">
            <input type="checkbox" id="night">
            <span>
              <strong>Houd rekening met de nacht.</strong>
              De coach houdt genoeg in de thuisbatterij om de nacht door te komen met
              opgeslagen energie. Zet je dit uit, dan mag de batterij voor de auto en
              voor handelen leeg tot zijn ingestelde minimum, maar haal je mogelijk de
              nacht niet met nul op de meter.
            </span>
          </label>
        </section>
      </div>

      ${saveBarHtml}
    `;
  }

  afterRender() {
    for (const button of this.$$("#level button")) {
      button.addEventListener("click", () => {
        this.draft_.strategy.level = button.dataset.level;
        this.paintLevel_();
        this.afterChange_();
      });
    }
    this.$("#zon-voeg").addEventListener("click", () => {
      const id = this.$("#zon-nieuw").value;
      if (!id) return;
      const regels = this.zonRegels_();
      regels.push({ device: id, limit: null });
      this.zetZon_(regels);
    });
    this.$("#zon-standaard").addEventListener("click", () => this.zetZon_([]));
    this.$("#night").addEventListener("change", (event) => {
      this.draft_.strategy.night_strategy = event.target.checked;
      this.afterChange_();
    });
    this.wireSaveBar_();
    this.paint_();
  }

  /** A schedule for a device that no longer exists is nothing but a leftover. */
  reconcile_() {
    const schedules = this.draft_?.strategy?.schedules;
    if (!Array.isArray(schedules)) return;

    const known = new Set((this.draft_?.devices ?? []).map((device) => device.id));
    const kept = schedules.filter((entry) => known.has(entry.device));
    if (kept.length !== schedules.length) this.draft_.strategy.schedules = kept;
  }

  blockers_() {
    return [];
  }

  afterChange_() {
    this.syncSaveBar_();
  }

  paint_() {
    if (!this.draft_ || !this.rendered_) return;
    // Hoort hier en niet alleen in de klikafhandelaar. Stond hij daar alleen,
    // dan was het niveau na een herlaadbeurt nergens aangevinkt: opgeslagen
    // was het wel, maar het scherm liet niet zien wat er stond. Dat is niet te
    // onderscheiden van instellingen die verdwenen zijn, en zo is het ook gemeld.
    this.paintLevel_();
    this.paintZon_();
    this.$("#night").checked = this.draft_?.strategy?.night_strategy !== false;
    this.syncSaveBar_();
  }

  // --- voorrang bij zonoverschot (v0.92.0) --------------------------------

  /** De regels zoals ze gelden: opgeslagen, aangevuld tot elk apparaat erin staat. */
  zonRegels_() {
    return zonRegels(this.draft_?.strategy?.solar_priority, this.draft_?.devices ?? []);
  }

  /** Nieuwe regels in het concept, en opnieuw tekenen. */
  zetZon_(regels) {
    this.draft_.strategy.solar_priority = regels.map((rij) => ({ device: rij.device, limit: rij.limit }));
    this.paintZon_();
    this.afterChange_();
  }

  paintZon_() {
    const lijst = this.$("#zon-lijst");
    if (!lijst || !this.draft_) return;
    const apparaten = this.draft_.devices ?? [];
    const namen = deviceLabelMap(apparaten);
    const soort = new Map(apparaten.map((a) => [a.id, a.type]));
    const regels = this.zonRegels_();

    lijst.replaceChildren(...regels.map((rij, plek) => {
      const type = soort.get(rij.device);
      const li = document.createElement("li");
      li.className = "zon-rij";
      li.dataset.plek = String(plek);

      const greep = document.createElement("button");
      greep.type = "button";
      greep.className = "greep";
      greep.setAttribute("aria-label", "Verslepen");
      greep.innerHTML = icons.menu;
      greep.addEventListener("pointerdown", (ev) => this.sleepZon_(ev, plek));

      const nr = document.createElement("span");
      nr.className = "nr";
      nr.textContent = String(plek + 1);

      const wie = document.createElement("span");
      wie.className = "wie";
      const naam = document.createElement("strong");
      naam.textContent = namen.get(rij.device) ?? rij.device;
      const uitleg = document.createElement("small");
      uitleg.textContent = regelUitleg(type, rij.limit);
      wie.append(naam, uitleg);

      const grens = document.createElement("span");
      grens.className = "grens";
      if (type === "boiler") {
        grens.textContent = "tot warm";
      } else {
        const veld = document.createElement("input");
        veld.type = "number";
        veld.min = "0";
        veld.max = "100";
        veld.step = "5";
        veld.inputMode = "numeric";
        veld.placeholder = type === "laadpaal" ? "doel" : "vol";
        veld.value = rij.limit ?? "";
        veld.setAttribute("aria-label", `Grens voor ${naam.textContent} in procent`);
        veld.addEventListener("change", () => {
          const nieuw = this.zonRegels_();
          const waarde = veld.value.trim();
          nieuw[plek].limit = waarde === "" ? null : Math.max(0, Math.min(100, Number(waarde)));
          this.zetZon_(nieuw);
        });
        grens.append("tot ", veld, " %");
      }

      const knoppen = document.createElement("span");
      knoppen.className = "knoppen";
      for (const [stap, icoon, label] of [[-1, icons.arrowLeft, "Omhoog"], [1, icons.arrowRight, "Omlaag"]]) {
        const knop = document.createElement("button");
        knop.type = "button";
        knop.innerHTML = icoon;
        knop.style.transform = "rotate(90deg)";
        knop.setAttribute("aria-label", label);
        knop.disabled = plek + stap < 0 || plek + stap >= regels.length;
        knop.addEventListener("click", () => {
          const nieuw = this.zonRegels_();
          const [rij2] = nieuw.splice(plek, 1);
          nieuw.splice(plek + stap, 0, rij2);
          this.zetZon_(nieuw);
        });
        knoppen.append(knop);
      }
      const weg = document.createElement("button");
      weg.type = "button";
      weg.innerHTML = icons.close;
      weg.setAttribute("aria-label", "Regel weghalen");
      // De laatste regel van een apparaat weghalen kan niet: dan komt hij
      // toch weer achteraan (zie `zonRegels`). Zeg dat liever met een
      // uitgeschakelde knop dan met een regel die terugkomt.
      weg.disabled = regels.filter((r2) => r2.device === rij.device).length < 2;
      weg.addEventListener("click", () => {
        const nieuw = this.zonRegels_();
        nieuw.splice(plek, 1);
        this.zetZon_(nieuw);
      });
      knoppen.append(weg);

      li.append(greep, nr, wie, grens, knoppen);
      return li;
    }));

    // Een tweede regel kan voor een auto of een batterij ("eerst tot 50%, en
    // na de auto tot vol"); een boiler heeft geen grens en dus geen tweede.
    const kiezer = this.$("#zon-nieuw");
    const kan = apparaten.filter((a) => a.controllable && (a.type === "laadpaal" || a.type === "thuisbatterij"));
    kiezer.replaceChildren(...kan.map((a) => {
      const optie = document.createElement("option");
      optie.value = a.id;
      optie.textContent = namen.get(a.id) ?? a.id;
      return optie;
    }));
    this.$("#zon-voeg").disabled = !kan.length;
  }

  /**
   * Een regel verslepen, op dezelfde manier als een kaart op het overzicht:
   * pointer events, zodat het ook op een telefoon werkt, en de pijltjes ernaast.
   */
  sleepZon_(event, plek) {
    const lijst = this.$("#zon-lijst");
    const rijen = [...lijst.children];
    const el = rijen[plek];
    if (!el) return;
    event.preventDefault();
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // Een pointer die al weg is.
    }
    const greep = event.currentTarget;
    const startY = event.clientY;
    const volgorde = rijen.map((_, i) => i);
    let settled = 0;
    el.classList.add("sleept");
    const zet = () => volgorde.forEach((oud, i) => { rijen[oud].style.order = String(i); });

    const move = (ev) => {
      const dy = ev.clientY - startY;
      el.style.transform = `translateY(${dy + settled}px)`;
      for (;;) {
        const index = volgorde.indexOf(plek);
        const stap = dy + settled < 0 ? -1 : 1;
        const ander = volgorde[index + stap];
        if (ander === undefined) break;
        const box = rijen[ander].getBoundingClientRect();
        const zelf = el.getBoundingClientRect();
        const voorbij = stap < 0 ? zelf.top < box.top + box.height / 2 : zelf.bottom > box.bottom - box.height / 2;
        if (!voorbij) break;
        const voor = el.getBoundingClientRect().top;
        volgorde.splice(index, 1);
        volgorde.splice(index + stap, 0, plek);
        zet();
        settled += voor - el.getBoundingClientRect().top;
        el.style.transform = `translateY(${dy + settled}px)`;
      }
    };
    const stop = () => {
      greep.removeEventListener("pointermove", move);
      greep.removeEventListener("pointerup", stop);
      greep.removeEventListener("pointercancel", stop);
      el.classList.remove("sleept");
      el.style.transform = "";
      const regels = this.zonRegels_();
      if (volgorde.some((oud, i) => oud !== i)) this.zetZon_(volgorde.map((oud) => regels[oud]));
      else this.paintZon_();
    };
    greep.addEventListener("pointermove", move);
    greep.addEventListener("pointerup", stop);
    greep.addEventListener("pointercancel", stop);
  }

  /**
   * Het niveau: hoeveel de coach zelf mag doen.
   *
   * De keuze tussen laagste kosten en zoveel mogelijk zon stond hier ook, en die
   * is weg. De eigenaar op 30-08-2026: "het eindoel is altijd lage kosten." Sindsdien
   * legt de coach alle manieren naast elkaar en wint zon vanzelf zodra hij
   * goedkoper is; een knop die dat overrulet zou alleen maar geld kosten.
   */
  paintLevel_() {
    const level = this.draft_?.strategy?.level ?? "propose";
    for (const button of this.$$("#level button")) {
      button.setAttribute("aria-pressed", String(button.dataset.level === level));
    }
  }
}

DacViewStrategy.css = /* css */ `
  ${editorCss}

  /* Vier keuzes onder elkaar: het zijn zinnen, geen knoppen, en naast elkaar
     wordt elke zin een kolom van drie woorden breed. */
  .segmented.levels { grid-template-columns: minmax(0, 1fr); }

  /* De voorrang bij zonoverschot (v0.92.0). */
  .zon-lijst { list-style: none; margin: 12px 0 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
  .zon-rij {
    display: grid; grid-template-columns: 34px 22px minmax(0, 1fr) auto auto;
    align-items: center; gap: 8px; padding: 8px 10px;
    border: 1px solid var(--dac-border); border-radius: var(--dac-radius-sm);
    background: rgba(255,255,255,0.02);
  }
  .zon-rij.sleept { position: relative; z-index: 2; box-shadow: 0 8px 22px rgba(0,0,0,0.4); }
  .zon-rij .greep {
    display: inline-grid; place-items: center; width: 34px; height: 34px;
    border: 0; background: transparent; color: var(--dac-ink-3); cursor: grab; touch-action: none;
  }
  .zon-rij .nr { font-weight: 700; color: var(--dac-ink-2); font-variant-numeric: tabular-nums; text-align: center; }
  .zon-rij .wie { display: grid; min-width: 0; }
  .zon-rij .wie strong { font-size: 13.5px; color: var(--dac-ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .zon-rij .wie small { font-size: 12px; color: var(--dac-ink-3); }
  .zon-rij .grens { font-size: 13px; color: var(--dac-ink-2); white-space: nowrap; }
  .zon-rij .grens input {
    width: 64px; min-height: 34px; padding: 4px 8px; font: inherit;
    border-radius: var(--dac-radius-sm); border: 1px solid var(--dac-border-hi);
    background: rgba(255,255,255,0.04); color: var(--dac-ink);
  }
  .zon-rij .knoppen { display: inline-flex; gap: 2px; }
  .zon-rij .knoppen button {
    display: inline-grid; place-items: center; width: 32px; height: 32px; border-radius: 50%;
    border: 0; background: transparent; color: var(--dac-ink-2); cursor: pointer;
  }
  .zon-rij .knoppen button:disabled { opacity: 0.3; cursor: default; }
  .zon-rij svg { width: 16px; height: 16px; }
  .zon-voeg { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
  .zon-voeg select, .zon-voeg button {
    min-height: 38px; padding: 6px 12px; font: inherit; font-size: 13px;
    border-radius: var(--dac-radius-sm); border: 1px solid var(--dac-border-hi);
    background: rgba(255,255,255,0.04); color: var(--dac-ink);
  }
  .zon-voeg select { width: auto; flex: 1 1 180px; max-width: 280px; }
  .zon-voeg button { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; white-space: nowrap; }
  .zon-voeg svg { width: 16px; height: 16px; flex: 0 0 auto; }
  .zon-voeg button.zacht { background: transparent; color: var(--dac-ink-2); }
  /* Smal: de grens en de knoppen onder de naam. */
  @media (max-width: 420px) {
    .zon-rij { grid-template-columns: 34px 22px minmax(0, 1fr); }
    .zon-rij .grens { grid-column: 3; }
    .zon-rij .knoppen { grid-column: 1 / -1; justify-content: flex-end; }
  }
  @media (min-width: 720px) { .segmented.levels { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
`;

define("dac-view-strategy", DacViewStrategy);
