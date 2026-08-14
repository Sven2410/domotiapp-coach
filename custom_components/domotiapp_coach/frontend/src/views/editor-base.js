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

/** How long a confirmation stays up. Long enough to notice, then gone. */
const TOAST_MS = 3200;

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

  /* ---- confirmation ----
     The save bar slides away on success, and a control disappearing is not a
     confirmation -- it reads the same as the change being discarded. This says
     so in as many words, and stays long enough to be read. */
  .toast {
    position: fixed;
    left: 50%;
    bottom: 84px;
    z-index: 40;
    transform: translate(-50%, 14px);
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 18px;
    border-radius: var(--dac-radius-pill);
    background: #171714;
    border: 1px solid var(--dac-border-hi);
    box-shadow: 0 20px 44px -18px rgba(0,0,0,0.95);
    font-size: 14px;
    font-weight: 500;
    color: var(--dac-ink);
    opacity: 0;
    pointer-events: none;
    transition: opacity 220ms ease, transform 220ms cubic-bezier(0.22,0.61,0.36,1);
    white-space: nowrap;
    max-width: calc(100vw - 32px);
  }
  .toast.on { opacity: 1; transform: translate(-50%, 0); pointer-events: auto; }
  .toast .icon { width: 17px; height: 17px; flex: 0 0 auto; }
  .toast.ok { border-color: rgba(12,163,12,0.45); }
  .toast.ok .icon { color: var(--dac-good); }
  .toast.fail {
    border-color: rgba(208,59,59,0.5);
    white-space: normal;
    align-items: flex-start;
    max-width: min(560px, calc(100vw - 32px));
    border-radius: var(--dac-radius-sm);
    line-height: 1.5;
  }
  .toast.fail .icon { color: var(--dac-bad); margin-top: 2px; }
  /* An error message is the one thing here worth copying -- into a search, or
     into a message to whoever installed this. */
  .toast #toast-text { user-select: text; -webkit-user-select: text; cursor: text; }
  .toast button.dismiss {
    flex: 0 0 auto;
    margin: -4px -6px -4px 2px;
    padding: 6px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: var(--dac-ink-3);
    cursor: pointer;
    line-height: 0;
  }
  .toast button.dismiss:hover { color: var(--dac-ink); background: rgba(255,255,255,0.07); }
  .toast button.dismiss .icon { width: 14px; height: 14px; }
  .toast.ok button.dismiss { display: none; }

  /* ---- read only ----
     Customers may look at their installation and question it; only an admin
     changes it. */
  :host([readonly]) input,
  :host([readonly]) select,
  :host([readonly]) textarea { pointer-events: none; opacity: 0.55; }
  :host([readonly]) .segmented button,
  :host([readonly]) button.add,
  :host([readonly]) .device-head button.remove,
  :host([readonly]) label.check { pointer-events: none; opacity: 0.55; }
  :host([readonly]) dac-entity-picker { pointer-events: none; opacity: 0.6; }
  :host([readonly]) .savebar { display: none; }
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
  <div class="toast" id="toast" role="status" aria-live="polite">
    <span id="toast-icon"></span>
    <span id="toast-text"></span>
    <button type="button" class="dismiss" id="toast-dismiss" aria-label="Sluiten">${icons.close}</button>
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
    if (this.rendered_) {
      this.applyPermissions_();
      this.onHass_();
    }
  }

  /** @param {import("../state-feed.js").StateFeed} feed */
  set stateFeed(value) {
    this.feed_ = value;
    if (this.rendered_) this.onFeed_();
  }

  /** Whether this user may change anything here. */
  canEdit_() {
    return this.hass_?.user?.is_admin !== false;
  }

  applyPermissions_() {
    this.toggleAttribute("readonly", !this.canEdit_());
    const notice = this.$("#admin-notice");
    if (notice) notice.hidden = this.canEdit_();
  }

  /** Push the state feed into every entity picker on the page. */
  onFeed_() {
    for (const picker of this.$$("dac-entity-picker")) picker.stateFeed = this.feed_;
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
    this.applyPermissions_();
    this.onFeed_();
    this.$("#toast-dismiss").addEventListener("click", () => this.hideToast_());
    this.$("#save").addEventListener("click", () => this.save_());
    this.$("#revert").addEventListener("click", () => {
      this.draft_ = clone(this.saved_);
      this.paint_();
      this.syncSaveBar_();
    });
  }

  syncSaveBar_() {
    const dirty = this.dirty_();
    const canSave = this.canEdit_();
    this.applyPermissions_();
    this.$("#savebar").classList.toggle("on", dirty && canSave);
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
      status.textContent = "";
      this.toast_("Opgeslagen", true);
    } catch (error) {
      status.textContent = "";
      this.toast_(`Opslaan mislukt — ${error?.message ?? error}`, false);
    } finally {
      button.disabled = false;
      this.$("#savebar").classList.toggle("on", this.dirty_());
    }
  }

  /**
   * Say what happened.
   * @param {string} message
   * @param {boolean} ok
   */
  toast_(message, ok) {
    const toast = this.$("#toast");
    if (!toast) return;

    this.$("#toast-icon").innerHTML = ok ? icons.check : icons.warning;
    this.$("#toast-text").textContent = message;
    toast.classList.remove("ok", "fail");
    toast.classList.add("on", ok ? "ok" : "fail");

    clearTimeout(this.toastTimer_);
    // A failure stays put: it is the only place the reason appears, and three
    // seconds is not enough to read an error, let alone copy it. It goes when
    // it is dismissed or when this section is left.
    if (ok) this.toastTimer_ = setTimeout(() => toast.classList.remove("on"), TOAST_MS);
  }

  hideToast_() {
    clearTimeout(this.toastTimer_);
    this.$("#toast")?.classList.remove("on");
  }

  onDisconnect() {
    // Leaving the section clears it. A stale error hanging over a screen the
    // customer has already moved on from is just confusing.
    this.hideToast_();
  }
}
