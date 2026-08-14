/**
 * Shared machinery for the two screens that write settings: Apparaten and
 * Instellingen.
 *
 * Both keep a draft that only reaches Home Assistant when the save bar is used.
 * Nothing saves as you type -- a half-typed entity id must never become the live
 * configuration, and on a phone it is far too easy to leave a field mid-word.
 */

import { DacElement } from "../base.js";
import { icons } from "../icons.js";

/** Deep clone that does not need structuredClone to be present. */
export const clone = (value) => JSON.parse(JSON.stringify(value));

export const editorCss = /* css */ `
  .wrap {
    max-width: 860px;
    margin: 0 auto;
    padding: 24px 22px 140px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .intro h1 { margin: 6px 0 0; font-size: 26px; font-weight: 600; letter-spacing: -0.01em; }
  .intro p { margin: 8px 0 0; font-size: 14px; line-height: 1.6; color: var(--dac-ink-2); max-width: 70ch; }

  section.card { padding: 20px 22px 22px; }
  section h2 {
    margin: 0;
    font-size: 17px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 9px;
  }
  section h2 .icon { width: 18px; height: 18px; color: var(--dac-accent-hi); }
  section .hint { margin: 8px 0 0; font-size: 13px; line-height: 1.55; color: var(--dac-ink-2); }

  .fields { margin-top: 18px; display: grid; gap: 14px; }
  .row { display: grid; gap: 6px; }
  .row > label { font-size: 13px; font-weight: 500; color: var(--dac-ink); }
  .row > .sub { font-size: 12px; color: var(--dac-ink-3); line-height: 1.45; }

  input[type="text"], input[type="number"], select {
    width: 100%;
    padding: 10px 12px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border-hi);
    background: rgba(255,255,255,0.04);
    color: var(--dac-ink);
    font: inherit;
    font-size: 14px;
    min-height: 44px;
  }
  input:focus, select:focus { border-color: var(--dac-accent-hi); outline: none; }
  select { appearance: none; background-image: none; }
  select option { background: #12120f; color: var(--dac-ink); }

  .two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  @media (max-width: 560px) { .two { grid-template-columns: 1fr; } }

  .notice {
    margin-top: 14px;
    padding: 12px 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid rgba(250,178,25,0.35);
    background: rgba(250,178,25,0.10);
    font-size: 13px;
    line-height: 1.5;
    color: var(--dac-ink);
    display: flex; gap: 10px; align-items: flex-start;
  }
  .notice .icon { width: 16px; height: 16px; flex: 0 0 auto; color: var(--dac-warn); margin-top: 1px; }
  .notice[hidden] { display: none; }

  /* ---- save bar ---- */
  .savebar {
    position: fixed;
    left: 0; right: 0; bottom: 0;
    z-index: 30;
    padding: 12px 22px calc(12px + env(safe-area-inset-bottom));
    background: linear-gradient(0deg, rgba(12,12,10,0.98) 60%, rgba(12,12,10,0.0));
    display: flex; align-items: center; gap: 12px; justify-content: flex-end;
    transform: translateY(120%);
    transition: transform 260ms cubic-bezier(0.22,0.61,0.36,1);
  }
  .savebar.on { transform: none; }
  .savebar .status { margin-right: auto; font-size: 13px; color: var(--dac-ink-2); }
  .savebar button {
    padding: 11px 20px;
    border-radius: var(--dac-radius-pill);
    border: 1px solid var(--dac-border-hi);
    background: var(--dac-surface);
    color: var(--dac-ink-2);
    font: inherit; font-size: 14px; font-weight: 500;
    cursor: pointer;
    min-height: 44px;
  }
  .savebar button.primary {
    border-color: transparent;
    background: var(--dac-accent);
    color: #fff;
    font-weight: 600;
  }
  .savebar button.primary:disabled { opacity: 0.55; cursor: default; }

  @media (max-width: 640px) {
    .wrap { padding: 16px 12px 150px; }
    section.card { padding: 16px 14px 18px; }
    .savebar { padding: 12px 12px calc(12px + env(safe-area-inset-bottom)); }
  }

  @media (max-width: 560px) {
    /* At phone width the status line and two labels fight for one row and all
       three wrap. The buttons are what has to stay readable. */
    .savebar .status { display: none; }
    .savebar button { flex: 1 1 0; white-space: nowrap; text-align: center; }
  }
`;

export const adminNoticeHtml = /* html */ `
  <div class="notice" id="admin-notice" hidden>
    ${icons.warning}
    <span>Je bent geen beheerder in Home Assistant, dus je kunt dit wel bekijken maar niet opslaan.</span>
  </div>
`;

export const saveBarHtml = /* html */ `
  <div class="savebar" id="savebar">
    <span class="status" id="save-status"></span>
    <button type="button" id="revert">Ongedaan maken</button>
    <button type="button" class="primary" id="save">Opslaan</button>
  </div>
`;

export class DacEditorElement extends DacElement {
  /**
   * Top-level settings keys this screen owns.
   *
   * A screen only ever sends its own sections. Both screens hold a full copy of
   * the settings, so saving the whole document from one of them would push its
   * stale copy of the other one's section back to the server -- edit the sensors,
   * walk over to Apparaten, add a device, save, and the device list the first
   * screen was holding would quietly undo it.
   */
  static sections = [];

  constructor() {
    super();
    this.draft_ = null;
    this.saved_ = null;
  }

  /** The part of a settings document this screen is responsible for. */
  slice_(settings) {
    if (!settings) return {};
    return Object.fromEntries(
      this.constructor.sections.map((key) => [key, settings[key]])
    );
  }

  set hass(value) {
    this.hass_ = value;
    if (this.rendered_) this.onHass_();
  }

  set settings(value) {
    if (!value) return;
    this.saved_ = clone(value);
    // A save from another device must not overwrite what is being typed here;
    // only adopt it when there is nothing unsaved.
    if (!this.dirty_()) {
      this.draft_ = clone(value);
      if (this.rendered_) this.paint_();
    }
  }

  dirty_() {
    if (!this.draft_) return false;
    // Only this screen's own sections count: a pending edit on the other screen
    // must not light up this one's save bar.
    return JSON.stringify(this.slice_(this.draft_)) !== JSON.stringify(this.slice_(this.saved_));
  }

  /** Hook for subclasses that need to push `hass` into child components. */
  onHass_() {}

  /** Subclasses fill their controls from `this.draft_`. */
  paint_() {}

  wireSaveBar_() {
    this.$("#save").addEventListener("click", () => this.save_());
    this.$("#revert").addEventListener("click", () => {
      this.draft_ = clone(this.saved_);
      this.paint_();
      this.syncSaveBar_();
    });
  }

  syncSaveBar_() {
    const dirty = this.dirty_();
    const canSave = this.hass_?.user?.is_admin !== false;
    const notice = this.$("#admin-notice");
    if (notice) notice.hidden = canSave;
    this.$("#savebar").classList.toggle("on", dirty);
    this.$("#save").disabled = !canSave;
    this.$("#save-status").textContent = dirty ? "Niet-opgeslagen wijzigingen" : "";
  }

  async save_() {
    const status = this.$("#save-status");
    const button = this.$("#save");
    button.disabled = true;
    status.textContent = "Opslaan…";

    try {
      const saved = await this.hass_.callWS({
        type: "domotiapp_coach/settings/set",
        settings: this.slice_(this.draft_),
      });
      this.saved_ = clone(saved);
      this.draft_ = clone(saved);
      this.fire("dac-settings-saved", { settings: saved });
      status.textContent = "Opgeslagen";
      setTimeout(() => this.syncSaveBar_(), 1600);
    } catch (error) {
      status.textContent = `Opslaan mislukt: ${error?.message ?? error}`;
    } finally {
      button.disabled = false;
      this.$("#savebar").classList.toggle("on", this.dirty_());
    }
  }
}
