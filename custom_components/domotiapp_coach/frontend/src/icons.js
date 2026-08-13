/**
 * Inline stroke icons, drawn in-house so the panel has no icon dependency and
 * keeps one consistent line weight. Every icon is a 24x24 viewBox using
 * currentColor, so sizing and coloring happen entirely in CSS.
 */

const svg = (body, { fill = "none" } = {}) =>
  `<svg class="icon" viewBox="0 0 24 24" fill="${fill}" stroke="currentColor" ` +
  `stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" ` +
  `aria-hidden="true" focusable="false">${body}</svg>`;

export const icons = {
  /** Brand mark: a bolt inside the tile. */
  bolt: svg(`<path d="M13.5 2.5 5 13.6h5.6L10 21.5 19 10.4h-5.6z"/>`),

  sun: svg(
    `<circle cx="12" cy="12" r="4.1"/>
     <path d="M12 2.4v2.3M12 19.3v2.3M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6M2.4 12h2.3M19.3 12h2.3M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6"/>`
  ),

  house: svg(
    `<path d="M3.2 11.3 12 4.1l8.8 7.2"/>
     <path d="M5.4 12.9V20a.9.9 0 0 0 .9.9h11.4a.9.9 0 0 0 .9-.9v-7.1"/>
     <path d="M9.8 20.9v-5.2h4.4v5.2"/>`
  ),

  /** Transmission tower -- reads as "the grid" at a glance. */
  grid: svg(
    `<path d="M8.2 21 12 3l3.8 18"/>
     <path d="M9.6 14.3h4.8M8.8 17.6h6.4M10.6 9.8h2.8"/>
     <path d="M6.6 9.6 12 12.4l5.4-2.8"/>`
  ),

  leaf: svg(
    `<path d="M4.6 19.6c-1.4-7.6 3.4-14 14.9-15.2 1.1 8.4-3.3 15.3-14.9 15.2Z"/>
     <path d="M4.2 20.4c2.6-4.6 6-7.6 10.4-9.6"/>`
  ),

  euro: svg(
    `<path d="M17.4 6.6a6.4 6.4 0 1 0 0 10.8"/>
     <path d="M5.6 10.4h7.6M5.6 13.8h7.6"/>`
  ),

  gauge: svg(
    `<path d="M3.6 17.4a9.2 9.2 0 1 1 16.8 0"/>
     <path d="M12 17.2 15.8 10"/>
     <circle cx="12" cy="17.4" r="1.4"/>`
  ),

  devices: svg(
    `<rect x="2.6" y="5.2" width="12.6" height="9.4" rx="1.6"/>
     <rect x="17.2" y="9.4" width="4.6" height="9.4" rx="1.4"/>
     <path d="M6.4 18.4h5.4M8.9 14.6v3.8"/>`
  ),

  compass: svg(
    `<circle cx="12" cy="12" r="9"/>
     <path d="m15.4 8.6-2 4.8-4.8 2 2-4.8z"/>`
  ),

  plug: svg(
    `<path d="M9 2.6v5M15 2.6v5"/>
     <path d="M5.8 7.6h12.4v3.2a6.2 6.2 0 0 1-12.4 0z"/>
     <path d="M12 17v4.4"/>`
  ),

  sliders: svg(
    `<path d="M3.4 7.2h17.2M3.4 12h17.2M3.4 16.8h17.2"/>
     <circle cx="8.6" cy="7.2" r="2.1"/>
     <circle cx="15.4" cy="12" r="2.1"/>
     <circle cx="10.2" cy="16.8" r="2.1"/>`
  ),

  home: svg(
    `<path d="M3.4 11.4 12 4.4l8.6 7"/>
     <path d="M5.6 12.9V20a.9.9 0 0 0 .9.9h11a.9.9 0 0 0 .9-.9v-7.1"/>`
  ),

  menu: svg(`<path d="M4 7h16M4 12h16M4 17h16"/>`),

  /** Coach mark: a four-pointed spark. */
  spark: svg(
    `<path d="M12 2.8c.9 4.9 2.4 6.4 7.3 7.3-4.9.9-6.4 2.4-7.3 7.3-.9-4.9-2.4-6.4-7.3-7.3 4.9-.9 6.4-2.4 7.3-7.3Z"/>
     <path d="M18.4 16.2c.4 2.2 1.1 2.9 3.3 3.3-2.2.4-2.9 1.1-3.3 3.3-.4-2.2-1.1-2.9-3.3-3.3 2.2-.4 2.9-1.1 3.3-3.3Z"/>`
  ),

  arrowRight: svg(`<path d="M4.5 12h14M13 6.5l5.5 5.5-5.5 5.5"/>`),
};
