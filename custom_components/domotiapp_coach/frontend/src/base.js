/** Minimal base class for the panel's web components -- no framework, no build step. */

import { baseCss, followTheme, lightTokens, sheet, tokens } from "./theme.js";

const hostCss = /* css */ `
  :host {
    ${tokens}
    display: block;
    font-family: var(--dac-font);
    color: var(--dac-ink);
    /* So the browser draws its own parts -- the list of a select, a date field,
       a scrollbar -- in the same theme as the panel around them. */
    color-scheme: var(--dac-scheme);
    -webkit-font-smoothing: antialiased;
  }
  :host([light]) {
    ${lightTokens}
  }
`;

export class DacElement extends HTMLElement {
  /** Component-specific CSS, overridden by subclasses. */
  static css = "";

  /** One constructable stylesheet per subclass, built lazily and shared. */
  static get styleSheets_() {
    if (!Object.hasOwn(this, "sheets_")) {
      this.sheets_ = [sheet(hostCss + baseCss + this.css)];
    }
    return this.sheets_;
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.adoptedStyleSheets = new.target.styleSheets_;
    this.rendered_ = false;
  }

  /**
   * Two separate jobs, kept apart on purpose.
   *
   * Rendering happens once. Wiring -- timers, observers, subscriptions --
   * happens on every attach, because these elements are detached and reattached
   * routinely: views are cached and swapped in and out of the panel, and Home
   * Assistant moves the panel itself around.
   *
   * Doing both in one place is what froze the dashboard. `afterRender` started
   * the refresh timer and the state subscription; `disconnectedCallback` tore
   * them down; and on the way back in, the "already rendered" guard skipped the
   * setup. The element came back looking perfectly fine and never updated
   * again.
   */
  connectedCallback() {
    followTheme(this, true);
    if (!this.rendered_) {
      const tpl = document.createElement("template");
      tpl.innerHTML = this.render();
      this.shadowRoot.appendChild(tpl.content);
      this.rendered_ = true;
      this.afterRender();
    }
    this.onConnect();
  }

  disconnectedCallback() {
    followTheme(this, false);
    this.onDisconnect();
    // A sheet that leaves the page without closing would keep the page locked.
    for (const dialog of [...openSheets_.keys()]) {
      if (dialog.getRootNode?.() === this.shadowRoot) releaseSheet(dialog);
    }
  }

  /** @returns {string} HTML for the shadow root. Rendered once. */
  render() {
    return "";
  }

  /** Wire up listeners on the rendered DOM. Runs once. */
  afterRender() {}

  /** Start timers, observers and subscriptions. Runs on every attach. */
  onConnect() {}

  /** Stop whatever `onConnect` started. Runs on every detach. */
  onDisconnect() {}

  $(selector) {
    return this.shadowRoot.querySelector(selector);
  }

  $$(selector) {
    return [...this.shadowRoot.querySelectorAll(selector)];
  }

  /** Fire an event that escapes the shadow root, the way HA's own elements do. */
  fire(type, detail) {
    this.dispatchEvent(
      new CustomEvent(type, { detail, bubbles: true, composed: true })
    );
  }
}

/** Register a component, tolerating a double load of the module. */
export function define(name, cls) {
  if (!customElements.get(name)) customElements.define(name, cls);
}

/**
 * Open a sheet and hold the page behind it still until it closes.
 *
 * A modal dialog makes the page behind it inert, but not still: on an iPhone
 * the page went on scrolling under the open DomotiTech Bot (the owner on
 * 13-11-2026, "ik kan de achtergrond scrollen als de bot geopend is, dat moet
 * ook niet"). So every element that scrolls the panel, inside Home Assistant's
 * shadow roots as well as the document itself, gets `overflow: hidden` while a
 * sheet is open, and its own value back on close. Every sheet opens through
 * here, so they all behave the same.
 */
export function openSheet(dialog) {
  if (!dialog) return;
  if (!dialog.open) dialog.showModal();
  if (openSheets_.has(dialog)) return;
  if (!openSheets_.size) held_ = holdStill(scrollers(dialog));
  openSheets_.set(dialog, true);
  dialog.addEventListener("close", () => releaseSheet(dialog), { once: true });
}

const openSheets_ = new Map();
let held_ = [];

function releaseSheet(dialog) {
  if (!openSheets_.delete(dialog) || openSheets_.size) return;
  for (const [el, overflow] of held_) el.style.overflow = overflow;
  held_ = [];
}

/** Everything that could scroll the page under `node`: its scrolling ancestors and the document. */
export function scrollers(node) {
  const found = [];
  const doc = globalThis.document;
  for (let el = parentOf(node); el; el = parentOf(el)) {
    if (el.nodeType !== 1 || el === doc?.documentElement || el === doc?.body) continue;
    let style = null;
    try { style = getComputedStyle(el); } catch { /* not in a browser */ }
    if (/(auto|scroll|overlay)/.test(`${style?.overflowY} ${style?.overflow}`)) found.push(el);
  }
  for (const el of [doc?.documentElement, doc?.body]) if (el && !found.includes(el)) found.push(el);
  return found;
}

/** The next element up, crossing out of a shadow root to its host. */
function parentOf(node) {
  if (node?.assignedSlot) return node.assignedSlot;
  const up = node?.parentNode ?? null;
  return up?.nodeType === 11 ? up.host ?? null : up;
}

function holdStill(elements) {
  return elements.map((el) => {
    const was = [el, el.style.overflow];
    el.style.overflow = "hidden";
    return was;
  });
}
