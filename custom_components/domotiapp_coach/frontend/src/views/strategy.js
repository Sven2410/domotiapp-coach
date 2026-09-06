/**
 * Strategie -- what the coach should do on its own, without being watched.
 *
 * Sinds 06-09-2026 alleen nog het niveau: hoeveel de coach zelf mag. De
 * melding "Zware belasting" en wie hem krijgt staan in het tabje Meldingen
 * (`views/notifications.js`), samen met de andere soorten; Sven wilde dat
 * twee in een. De schema's van apparaten staan sinds 27-08-2026 op de kaart
 * van het apparaat zelf.
 */

import { define } from "../base.js";
import { icons } from "../icons.js";
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
    this.syncSaveBar_();
  }

  /**
   * Het niveau: hoeveel de coach zelf mag doen.
   *
   * De keuze tussen laagste kosten en zoveel mogelijk zon stond hier ook, en die
   * is weg. Sven op 30-08-2026: "het eindoel is altijd lage kosten." Sindsdien
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
  @media (min-width: 720px) { .segmented.levels { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
`;

define("dac-view-strategy", DacViewStrategy);
