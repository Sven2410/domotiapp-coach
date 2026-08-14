/**
 * Design tokens for DomotiApp Coach.
 *
 * Type is Home Assistant's own UI font -- no webfonts ship with the panel, so
 * the dashboard matches the rest of HA and loads nothing.
 *
 * The energy-stream hues are not hand-picked. They were searched against the
 * #12120f card surface under the categorical rules (OKLCH lightness band,
 * chroma floor, all-pairs CVD separation, normal-vision floor and contrast) and
 * validated in both grid states -- import and export never appear at once,
 * since one of the two meter sensors is always zero. Both states clear every
 * gate: worst all-pairs deuteranopia ΔE 8.0, worst normal-vision ΔE 15.2.
 *
 * Red and green are deliberately absent from the stream colours: they are
 * reserved for status (duur / kritiek and goed), and a device bubble wearing one
 * would read as a warning instead of an identity. Every stream also carries its
 * own icon and written label, so colour never has to work alone.
 *
 * Do not swap these without re-running the search -- the margins are tight, and
 * two of the six pairs sit close to their floor.
 */

export const tokens = /* css */ `
  --dac-bg:            #0c0c0a;
  --dac-bg-raise:      #12120f;
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

  /* Energy streams -- validated categorical set. See the note above. */
  --dac-solar:         #dc7300;
  --dac-house:         #235efa;
  --dac-grid-in:       #129be4;
  --dac-grid-out:      #bc10c8;
  --dac-device-1:      #fd0774;
  --dac-device-2:      #039580;

  /* Status -- reserved meaning, always shipped with an icon and a label. */
  --dac-good:          #0ca30c;
  --dac-warn:          #fab219;
  --dac-bad:           #d03b3b;

  --dac-radius:        20px;
  --dac-radius-sm:     12px;
  --dac-radius-pill:   999px;

  /* Home Assistant's own UI font, so the panel matches the rest of HA. */
  --dac-font:          var(--ha-font-family-body,
                         var(--paper-font-body1_-_font-family,
                           Roboto, "Noto Sans", "Segoe UI", system-ui, sans-serif));

  --dac-shadow:        0 1px 0 rgba(255, 255, 255, 0.04) inset,
                       0 18px 40px -24px rgba(0, 0, 0, 0.9);
  --dac-header-h:      64px;
  --dac-maxw:          1440px;

  /* What the screen itself takes: the notch or Dynamic Island at the top, the
     home indicator at the bottom, and -- in landscape -- a strip on the side the
     island sits. Named here so every screen can keep clear of it the same way;
     they resolve to 0px anywhere that has no such cutouts. */
  --dac-safe-t:        env(safe-area-inset-top, 0px);
  --dac-safe-r:        env(safe-area-inset-right, 0px);
  --dac-safe-b:        env(safe-area-inset-bottom, 0px);
  --dac-safe-l:        env(safe-area-inset-left, 0px);
`;

/** Styles shared by every component in the panel. */
export const baseCss = /* css */ `
  *, *::before, *::after { box-sizing: border-box; }

  .card {
    background: var(--dac-surface);
    border: 1px solid var(--dac-border);
    border-radius: var(--dac-radius);
    box-shadow: var(--dac-shadow);
  }

  .eyebrow {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--dac-ink-3);
  }

  /* Numerals must line up as values change -- never let them jitter. */
  .tnum { font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1; }

  /* iOS zooms the page in when a field it focuses has type smaller than 16px,
     and it does not zoom back out afterwards -- which is what left the dashboard
     scrollable sideways on a phone. Only touch devices need the larger type; on
     a mouse the fields keep their own size. */
  @media (pointer: coarse) {
    input, select, textarea { font-size: 16px; }
  }

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
