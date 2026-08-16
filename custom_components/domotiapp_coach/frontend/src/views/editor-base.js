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
    padding: 24px max(22px, var(--dac-safe-r)) 140px max(22px, var(--dac-safe-l));
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
  /* align-content, not the default stretch: two fields side by side where only
     one carries a hint line would otherwise hand the spare height to the other
     one's input, leaving two boxes of different sizes that do not line up. */
  .fields, .row { min-width: 0; }
  .row { display: grid; grid-template-columns: minmax(0, 1fr); gap: 6px; align-content: start; }
  .row > label { font-size: 13px; font-weight: 500; color: var(--dac-ink); }
  .row > .sub { font-size: 12px; color: var(--dac-ink-3); line-height: 1.45; }

  input[type="text"], input[type="number"], input[type="time"], select {
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
  /* See theme.js: below 16px iOS zooms the page in on focus and stays there. */
  @media (pointer: coarse) {
    input[type="text"], input[type="number"], input[type="time"], select, textarea { font-size: 16px; }
  }
  @supports (-webkit-touch-callout: none) {
    input[type="text"], input[type="number"], input[type="time"], select, textarea { font-size: 16px; }
  }
  input:focus, select:focus { border-color: var(--dac-accent-hi); outline: none; }
  select { appearance: none; background-image: none; }
  select option { background: #12120f; color: var(--dac-ink); }

  /* minmax(0, 1fr) rather than 1fr: a bare 1fr column never shrinks below the
     min-content of what is in it, so one wide child pushes the whole column --
     and with it the page -- past the edge of a phone. */
  .two { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; }
  @media (max-width: 560px) { .two { grid-template-columns: minmax(0, 1fr); } }

  /* ---- checkbox ----
     Shared, because every settings screen has these and three copies of the
     same block is how one screen ends up with the label running on inline. */
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
  /* The text half has to be allowed to shrink and to break. Some of these
     labels carry an entity or service name -- one unbreakable word wide enough
     to push the whole row off a narrow phone. */
  label.check span { min-width: 0; overflow-wrap: anywhere; }
  label.check strong {
    display: block;
    font-size: 13px;
    font-weight: 600;
    color: var(--dac-ink);
    margin-bottom: 2px;
  }
  label.check:has(input:checked) { border-color: rgba(25,143,217,0.5); background: var(--dac-accent-soft); }

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

  /* ---- segmented choice ----
     Two or three mutually exclusive options with a line of explanation each.
     Shared: Installatie picks a contract with it and Strategie picks how a
     schedule repeats, and two copies is how they drift apart. */
  .segmented { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 8px; }
  @media (max-width: 560px) { .segmented { grid-template-columns: minmax(0, 1fr); } }
  .segmented button {
    padding: 12px 14px;
    border-radius: var(--dac-radius-sm);
    border: 1px solid var(--dac-border-hi);
    background: rgba(255,255,255,0.03);
    color: var(--dac-ink-2);
    font: inherit;
    font-size: 13.5px;
    text-align: left;
    cursor: pointer;
    transition: border-color 200ms ease, background 200ms ease, color 200ms ease;
  }
  .segmented button strong { display: block; font-weight: 600; color: var(--dac-ink); margin-bottom: 3px; }
  .segmented button[aria-pressed="true"] {
    border-color: rgba(25,143,217,0.6);
    background: var(--dac-accent-soft);
    color: var(--dac-ink);
  }

  /* ---- save bar ---- */
  .savebar {
    position: fixed;
    left: 0; right: 0; bottom: 0;
    z-index: 30;
    padding: 12px max(22px, var(--dac-safe-r)) calc(12px + var(--dac-safe-b)) max(22px, var(--dac-safe-l));
    background: linear-gradient(0deg, rgba(12,12,10,0.98) 60%, rgba(12,12,10,0.0));
    display: flex; align-items: center; gap: 12px; justify-content: flex-end;
    transform: translateY(120%);
    transition: transform 260ms cubic-bezier(0.22,0.61,0.36,1);
  }
  .savebar.on { transform: none; }
  .savebar .status { margin-right: auto; font-size: 13px; color: var(--dac-ink-2); }
  .savebar .status.blocked { color: var(--dac-warn); }
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
    .wrap { padding: 16px max(12px, var(--dac-safe-r)) 150px max(12px, var(--dac-safe-l)); }
    section.card { padding: 16px 14px 18px; }
    .savebar { padding: 12px max(12px, var(--dac-safe-r)) calc(12px + var(--dac-safe-b)) max(12px, var(--dac-safe-l)); }
  }

  @media (max-width: 560px) {
    /* At phone width the status line and two labels fight for one row and all
       three wrap. The buttons are what has to stay readable -- except when the
       status is the reason the save button will not work, which then gets a
       line of its own above them. */
    .savebar { flex-wrap: wrap; }
    .savebar .status { display: none; }
    .savebar .status.blocked {
      display: block;
      flex: 1 0 100%;
      margin: 0 0 2px;
      font-size: 12.5px;
      line-height: 1.4;
    }
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
     changes it.

     Everything that changes something is locked, and the exceptions are listed
     rather than the other way round. Naming the controls to lock meant every
     button added later was unlocked by default -- which is how a customer could
     still empty a time field on Strategie. Reading, unfolding a card and
     stepping into a sub-screen stay open: they change nothing. */
  :host([readonly]) input,
  :host([readonly]) select,
  :host([readonly]) textarea,
  :host([readonly]) label.check,
  :host([readonly]) button:not(.link):not(.back):not(.toggle):not(.dismiss):not(.sheet-close) {
    pointer-events: none;
    opacity: 0.55;
  }
  :host([readonly]) dac-entity-picker { pointer-events: none; opacity: 0.6; }
  :host([readonly]) .savebar { display: none; }
`;

export const adminNoticeHtml = /* html */ `
  <div class="notice admin-notice" hidden>
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
    // A screen may carry the notice more than once -- a sub-screen needs it as
    // much as the list it was opened from.
    for (const notice of this.$$(".admin-notice")) notice.hidden = this.canEdit_();
  }

  /** Push the state feed into every entity picker on the page. */
  onFeed_() {
    for (const picker of this.$$("dac-entity-picker")) picker.stateFeed = this.feed_;
  }

  set settings(value) {
    if (!value) return;
    this.saved_ = clone(value);

    if (this.draft_ && this.dirty_()) {
      // Everything this screen does not own is context, not a draft: the device
      // list on Strategie, the connection behind its threshold hint. Holding a
      // stale copy of it is how a device deleted under Apparaten kept its row
      // here, and the screen had no way to know it was looking at the past.
      for (const key of Object.keys(value)) {
        if (!this.constructor.sections.includes(key)) this.draft_[key] = clone(value[key]);
      }
      // With the new context in hand the screen can drop what it was holding on
      // to that no longer exists -- which is often the only reason it counted as
      // unsaved at all.
      this.reconcile_();
    }

    // A save from another device must not overwrite what is being typed here;
    // only adopt the whole document when there is nothing unsaved.
    if (!this.dirty_()) this.draft_ = clone(value);
    if (this.rendered_) this.paint_();
  }

  /**
   * Drop anything in this screen's own sections that points at something gone.
   *
   * The integration does the same on the way in, so this is not about keeping
   * the file clean -- it is about the draft in front of you agreeing with it,
   * so the save bar does not sit there offering to save a device that was
   * deleted three screens ago.
   */
  reconcile_() {}

  dirty_() {
    if (!this.draft_) return false;
    // Only this screen's own sections count: a pending edit on the other screen
    // must not light up this one's save bar.
    return JSON.stringify(this.slice_(this.draft_)) !== JSON.stringify(this.slice_(this.saved_));
  }

  /**
   * Reasons this screen may not be saved, in words the customer can act on.
   *
   * Only for settings that promise something the coach cannot deliver: a device
   * marked steerable without the entities to steer it, a notification switched
   * on with nobody to send it to. Those save cleanly and then quietly do
   * nothing, which is the worst of both -- the screen says it is arranged and
   * the house behaves as if it is not.
   *
   * Anything that is merely unfinished is not a blocker. Half an installation
   * has to be savable, or filling it in over two evenings is impossible.
   *
   * @returns {string[]}
   */
  blockers_() {
    return [];
  }

  /** Hook for subclasses that need to push `hass` into child components. */
  onHass_() {}

  /** Subclasses fill their controls from `this.draft_`. */
  paint_() {}

  /** Runs after a save went through. Nothing to do for most screens. */
  afterSave_() {}

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
    const blockers = this.blockers_();
    this.applyPermissions_();

    // The bar still comes up when something is blocking: it is where the reason
    // is written, and a save bar that hides itself when you have made a mistake
    // leaves you with a screen that will not save and no idea why.
    this.$("#savebar").classList.toggle("on", dirty && canSave);
    this.$("#save").disabled = !canSave || blockers.length > 0;
    this.$("#save-status").textContent = blockers.length
      ? blockers[0]
      : dirty
        ? "Niet-opgeslagen wijzigingen"
        : "";
    this.$("#save-status").classList.toggle("blocked", blockers.length > 0);
  }

  async save_() {
    const blockers = this.blockers_();
    if (blockers.length) {
      this.toast_(blockers[0], false);
      return;
    }

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
      this.afterSave_();
    } catch (error) {
      status.textContent = "";
      this.toast_(`Opslaan mislukt: ${error?.message ?? error}`, false);
    } finally {
      button.disabled = false;
      this.$("#savebar").classList.toggle("on", this.dirty_());
    }
  }

  /**
   * Persist one explicit slice, leaving the rest of the draft where it is.
   *
   * For the handful of actions that carry their own confirmation and are done
   * the moment they are confirmed -- deleting a device is the one. Asking "weet
   * je het zeker", getting a yes, and then still waiting for the save bar is one
   * question too many, and it leaves the screen showing a device that the
   * customer considers gone.
   *
   * What is sent is built by the caller from what is already stored, never from
   * the draft, so half-finished edits elsewhere on the screen stay unsaved.
   *
   * @param {Record<string, unknown>} sections
   * @param {string} message
   */
  async persist_(sections, message) {
    try {
      const saved = await this.hass_.callWS({
        type: "domotiapp_coach/settings/set",
        settings: sections,
      });
      this.saved_ = clone(saved);
      // Everything the customer had not touched follows the server; the rest of
      // the draft is left alone and keeps the save bar up on its own merits.
      if (!this.dirty_()) this.draft_ = clone(saved);
      this.fire("dac-settings-saved", { settings: saved });
      this.toast_(message, true);
    } catch (error) {
      this.toast_(`Opslaan mislukt: ${error?.message ?? error}`, false);
    } finally {
      this.syncSaveBar_();
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
