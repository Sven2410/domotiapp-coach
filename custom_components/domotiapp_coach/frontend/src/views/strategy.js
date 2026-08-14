/**
 * Strategie -- what the coach should do on its own, without being watched.
 *
 * For now that is one thing: warn when the connection is being pushed towards
 * its fuse. The interval is as much a part of the setting as the threshold --
 * load crosses any line dozens of times an hour, and a warning that repeats
 * itself is a warning people turn off.
 *
 * The notification is sent by the integration, not from here, so it also
 * arrives when nobody has the dashboard open.
 */

import { define } from "../base.js";
import { icons } from "../icons.js";
import {
  DacEditorElement,
  adminNoticeHtml,
  editorCss,
  saveBarHtml,
} from "./editor-base.js";

/** Sensible spacings, in minutes. */
const INTERVALS = [5, 10, 15, 30, 60, 120, 240];

class DacViewStrategy extends DacEditorElement {
  static sections = ["strategy"];

  set hass(value) {
    super.hass = value;
    if (this.rendered_) this.paintTargets_();
  }

  render() {
    return `
      <div class="wrap">
        <header class="intro">
          <div class="eyebrow">Strategie</div>
          <h1>Wat de coach uit zichzelf doet</h1>
          <p>Hier bepaal je waar de coach je actief voor waarschuwt. De rest van de tijd kijkt hij mee zonder iets te zeggen.</p>
        </header>

        ${adminNoticeHtml}

        <section class="card">
          <h2>${icons.warning} Melding bij zware belasting</h2>
          <p class="hint">Krijg een bericht zodra je aansluiting te zwaar belast wordt. De coach kijkt naar de zwaarst belaste fase als die bekend is, anders naar je totale netvermogen.</p>

          <div class="fields">
            <label class="check" for="alert-enabled">
              <input type="checkbox" id="alert-enabled">
              <span>
                <strong>Melding aanzetten</strong>
                Zonder dit blijft de belastbaarheid gewoon op het overzicht staan, maar krijg je er geen bericht over.
              </span>
            </label>

            <div id="alert-fields" class="fields">
              <div class="row">
                <label for="alert-threshold">Waarschuw vanaf (%)</label>
                <input type="number" id="alert-threshold" min="1" max="200" step="1" inputmode="numeric">
                <span class="sub" id="alert-threshold-hint"></span>
              </div>

              <div class="row">
                <label for="alert-interval">Niet vaker dan eens per</label>
                <select id="alert-interval">
                  ${INTERVALS.map((m) => `<option value="${m}">${label(m)}</option>`).join("")}
                </select>
                <span class="sub">De belasting schommelt heen en weer over de grens; zonder tussentijd zou je een reeks berichten krijgen voor één druk uur.</span>
              </div>

              <div class="row">
                <label>Wie krijgt de melding?</label>
                <div id="targets"></div>
                <span class="sub" id="targets-hint"></span>
              </div>
            </div>
          </div>
        </section>
      </div>

      ${saveBarHtml}
    `;
  }

  afterRender() {
    this.$("#alert-enabled").addEventListener("change", (ev) => {
      this.alert_().enabled = ev.target.checked;
      this.paintEnabled_();
      this.syncSaveBar_();
    });

    this.$("#alert-threshold").addEventListener("input", (ev) => {
      this.alert_().threshold_percent = Number(ev.target.value);
      this.paintHint_();
      this.syncSaveBar_();
    });

    this.$("#alert-interval").addEventListener("change", (ev) => {
      this.alert_().min_interval_minutes = Number(ev.target.value);
      this.syncSaveBar_();
    });

    this.wireSaveBar_();
    this.paint_();
  }

  alert_() {
    return this.draft_.strategy.load_alert;
  }

  /**
   * Every notify service Home Assistant knows about.
   *
   * These are what the mobile app registers itself as, which is how a
   * notification reaches a specific person's phone.
   */
  targets_() {
    return Object.keys(this.hass_?.services?.notify ?? {})
      .filter((name) => name !== "persistent_notification")
      .sort();
  }

  prettyTarget_(name) {
    return name
      .replace(/^mobile_app_/, "")
      .replace(/_/g, " ")
      .replace(/^\w/, (c) => c.toUpperCase());
  }

  paint_() {
    if (!this.draft_ || !this.rendered_) return;
    const alert = this.alert_();

    this.$("#alert-enabled").checked = Boolean(alert.enabled);
    this.$("#alert-threshold").value = alert.threshold_percent;
    this.$("#alert-interval").value = String(alert.min_interval_minutes);

    this.paintEnabled_();
    this.paintTargets_();
    this.paintHint_();
    this.syncSaveBar_();
  }

  paintEnabled_() {
    this.$("#alert-fields").style.display = this.alert_().enabled ? "" : "none";
  }

  paintHint_() {
    // The draft holds the whole settings document, not just this screen's
    // sections, so the connection is available here without a second fetch.
    const fuse = Number(this.draft_?.installation?.fuse_amps) || 0;
    const phases = Number(this.draft_?.installation?.phases) || 1;
    const percent = Number(this.alert_().threshold_percent) || 0;
    const hint = this.$("#alert-threshold-hint");

    if (!fuse) {
      hint.textContent = "Vul eerst je aansluiting in onder Installatie.";
      return;
    }
    const amps = ((fuse * percent) / 100).toLocaleString("nl-NL", { maximumFractionDigits: 1 });
    hint.textContent = `Bij ${phases} × ${fuse} A komt dat neer op ${amps} A per fase.`;
  }

  paintTargets_() {
    if (!this.rendered_ || !this.draft_) return;

    const holder = this.$("#targets");
    const available = this.targets_();
    const chosen = new Set(this.alert_().targets ?? []);

    if (!available.length) {
      holder.innerHTML = `<p class="empty">Er zijn nog geen notify-diensten in Home Assistant. Die verschijnen zodra de mobiele app op een telefoon is ingelogd.</p>`;
      this.$("#targets-hint").textContent = "";
      return;
    }

    holder.innerHTML = available
      .map(
        (name) => `
        <label class="check target" for="tgt-${name}">
          <input type="checkbox" id="tgt-${name}" data-target="${name}"${chosen.has(name) ? " checked" : ""}>
          <span>
            <strong>${this.prettyTarget_(name)}</strong>
            notify.${name}
          </span>
        </label>`
      )
      .join("");

    for (const box of holder.querySelectorAll("[data-target]")) {
      box.addEventListener("change", () => {
        const targets = new Set(this.alert_().targets ?? []);
        if (box.checked) targets.add(box.dataset.target);
        else targets.delete(box.dataset.target);
        this.alert_().targets = [...targets].sort();
        this.$("#targets-hint").textContent = this.targetsHint_();
        this.syncSaveBar_();
      });
    }

    this.$("#targets-hint").textContent = this.targetsHint_();
  }

  targetsHint_() {
    const count = (this.alert_().targets ?? []).length;
    if (!count) return "Niemand geselecteerd — er wordt dan niets verstuurd.";
    return count === 1 ? "1 ontvanger" : `${count} ontvangers`;
  }
}

/** "eens per ..." in words. */
function label(minutes) {
  if (minutes < 60) return `${minutes} minuten`;
  const hours = minutes / 60;
  return hours === 1 ? "uur" : `${hours} uur`;
}

DacViewStrategy.css = /* css */ `
  ${editorCss}

  label.check {
    display: flex;
    align-items: flex-start;
    gap: 11px;
    padding: 12px 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border);
    background: rgba(255,255,255,0.022);
    cursor: pointer;
    font-size: 12.5px;
    line-height: 1.5;
    color: var(--dac-ink-2);
  }
  label.check input {
    width: 18px; height: 18px; flex: 0 0 auto; margin: 1px 0 0;
    accent-color: var(--dac-accent-hi);
    cursor: pointer;
  }
  label.check strong { display: block; font-size: 13px; font-weight: 600; color: var(--dac-ink); margin-bottom: 2px; }
  label.check:has(input:checked) { border-color: rgba(25,143,217,0.5); background: var(--dac-accent-soft); }

  label.check.target span { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11.5px; }
  label.check.target strong { font-family: var(--dac-font); font-size: 13.5px; }

  #targets { display: grid; gap: 8px; }
  .empty { margin: 0; font-size: 13px; color: var(--dac-ink-3); line-height: 1.55; }
`;

define("dac-view-strategy", DacViewStrategy);
