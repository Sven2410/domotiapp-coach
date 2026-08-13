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

  connectedCallback() {
    if (this.rendered_) return;
    const tpl = document.createElement("template");
    tpl.innerHTML = this.render();
    this.shadowRoot.appendChild(tpl.content);
    this.rendered_ = true;
    this.afterRender();
  }

  /** @returns {string} HTML for the shadow root. Rendered once. */
  render() {
    return "";
  }

  /** Hook for wiring up listeners after the initial render. */
  afterRender() {}

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
