/** Minimal base class for the panel's web components -- no framework, no build step. */

import { baseCss, sheet, tokens } from "./theme.js";

const hostCss = /* css */ `
  :host {
    ${tokens}
    display: block;
    font-family: var(--dac-font);
    color: var(--dac-ink);
    -webkit-font-smoothing: antialiased;
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
    this.onDisconnect();
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
