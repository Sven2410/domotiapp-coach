/**
 * Design tokens for DomotiApp Coach.
 *
 * The palette is derived from domotitech.nl: a warm near-black canvas, warm
 * off-white ink, Cormorant Garamond for display type and Raleway for UI type.
 * The accent is the DomotiTech blue #026FA1.
 *
 * The four energy-stream hues are validated as a categorical palette against
 * the #0c0c0a surface (OKLCH lightness band, chroma floor, CVD separation and
 * contrast). Do not swap them for prettier values without re-validating -- the
 * amber/red pair in particular sits close under deuteranopia, which is why
 * every stream also carries its own icon and written label.
 */

export const tokens = /* css */ `
  --dac-bg:            #0c0c0a;
  --dac-bg-raise:      #121210;
  --dac-surface:       rgba(255, 255, 255, 0.038);
  --dac-surface-hi:    rgba(255, 255, 255, 0.070);
  --dac-border:        rgba(232, 228, 222, 0.10);
  --dac-border-hi:     rgba(232, 228, 222, 0.20);

  --dac-ink:           #e8e4de;
  --dac-ink-2:         rgba(232, 228, 222, 0.62);
  --dac-ink-3:         rgba(232, 228, 222, 0.38);

  --dac-accent:        #026fa1;
  --dac-accent-hi:     #198fd9;
  --dac-accent-soft:   rgba(2, 111, 161, 0.18);
  --dac-accent-glow:   rgba(25, 143, 217, 0.30);

  /* Energy streams -- validated categorical set, in this order. */
  --dac-solar:         #c07d01;
  --dac-house:         #1f93e6;
  --dac-grid:          #e8563f;
  --dac-surplus:       #05a869;

  --dac-good:          #05a869;
  --dac-warn:          #c07d01;
  --dac-bad:           #e8563f;

  --dac-radius:        20px;
  --dac-radius-sm:     12px;
  --dac-radius-pill:   999px;

  --dac-font:          "Raleway", "Segoe UI", Roboto, system-ui, sans-serif;
  --dac-display:       "Cormorant Garamond", "Iowan Old Style", Georgia, serif;

  --dac-shadow:        0 1px 0 rgba(255, 255, 255, 0.04) inset,
                       0 18px 40px -24px rgba(0, 0, 0, 0.9);
  --dac-header-h:      68px;
  --dac-maxw:          1440px;
`;

/**
 * Register the bundled webfonts.
 *
 * @font-face is document-scoped, so it cannot live in a shadow-root stylesheet
 * -- it has to be injected into the document once. The URLs are resolved
 * against this module so they keep working whatever HA mounts the panel under.
 * Fonts ship with the integration, so the panel needs no internet access.
 */
export function ensureFonts() {
  const ID = "domotiapp-coach-fonts";
  if (document.getElementById(ID)) return;

  const url = (file) => new URL(`../fonts/${file}`, import.meta.url).href;
  const style = document.createElement("style");
  style.id = ID;
  style.textContent = /* css */ `
    @font-face {
      font-family: "Raleway";
      src: url("${url("raleway.woff2")}") format("woff2");
      font-weight: 300 700;
      font-display: swap;
    }
    @font-face {
      font-family: "Cormorant Garamond";
      src: url("${url("cormorant-garamond.woff2")}") format("woff2");
      font-weight: 300 600;
      font-display: swap;
    }
    @font-face {
      font-family: "Cormorant Garamond";
      src: url("${url("cormorant-garamond-italic.woff2")}") format("woff2");
      font-weight: 300 600;
      font-style: italic;
      font-display: swap;
    }
  `;
  document.head.appendChild(style);
}

/** Styles shared by every component in the panel. */
export const baseCss = /* css */ `
  *, *::before, *::after { box-sizing: border-box; }

  .card {
    background: var(--dac-surface);
    border: 1px solid var(--dac-border);
    border-radius: var(--dac-radius);
    box-shadow: var(--dac-shadow);
    backdrop-filter: blur(6px);
  }

  .eyebrow {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--dac-ink-3);
  }

  .display {
    font-family: var(--dac-display);
    font-weight: 300;
    letter-spacing: -0.01em;
    line-height: 1.05;
  }

  .accent-italic {
    font-style: italic;
    color: var(--dac-accent-hi);
  }

  /* Numerals must line up as values change -- never let them jitter. */
  .tnum { font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1; }

  :focus-visible {
    outline: 2px solid var(--dac-accent-hi);
    outline-offset: 2px;
    border-radius: 6px;
  }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.001ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.001ms !important;
    }
  }
`;

/**
 * Build a constructable stylesheet once per component class.
 * @param {string} css
 * @returns {CSSStyleSheet}
 */
export function sheet(css) {
  const s = new CSSStyleSheet();
  s.replaceSync(css);
  return s;
}
