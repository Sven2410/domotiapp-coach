/**
 * Inline stroke icons, drawn in-house so the panel has no icon dependency and
 * keeps one consistent line weight. Every icon is a 24x24 viewBox using
 * currentColor, so sizing and coloring happen entirely in CSS.
 *
 * Every energy stream and every device type has one, because colour alone is
 * never allowed to carry identity here.
 */

const svg = (body, { fill = "none" } = {}) =>
  `<svg class="icon" viewBox="0 0 24 24" fill="${fill}" stroke="currentColor" ` +
  `stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" ` +
  `aria-hidden="true" focusable="false">${body}</svg>`;

export const icons = {
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

  /** Zelfbenutting: a leaf, the share of your own sun you keep. */
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

  // ---- device types -------------------------------------------------------

  laadpaal: svg(
    `<rect x="3.2" y="4.2" width="10.6" height="15.6" rx="2"/>
     <path d="M6 8.4h5M6 11.6h5"/>
     <path d="m9.4 14.2-1.6 2.6h2.4l-1.2 2.4"/>
     <path d="M13.8 9.4h3.2a2 2 0 0 1 2 2v5.2a1.7 1.7 0 0 0 1.7 1.7"/>`
  ),

  thuisbatterij: svg(
    `<rect x="2.8" y="6.6" width="16" height="10.8" rx="2"/>
     <path d="M21.2 10.4v3.2"/>
     <path d="M6.4 10.2v4M9.8 10.2v4M13.2 10.2v4"/>`
  ),

  warmtepomp: svg(
    `<circle cx="12" cy="12" r="8.6"/>
     <circle cx="12" cy="12" r="2.2"/>
     <path d="M12 3.4c2.4 2.6 2.4 4.6 0 6.4M20.6 12c-2.6 2.4-4.6 2.4-6.4 0M12 20.6c-2.4-2.6-2.4-4.6 0-6.4M3.4 12c2.6-2.4 4.6-2.4 6.4 0"/>`
  ),

  boiler: svg(
    `<rect x="5.6" y="2.8" width="12.8" height="18.4" rx="4"/>
     <path d="M9 7.4h6"/>
     <path d="M12 11.4c-1.6 1.8-2.4 3-2.4 4.1a2.4 2.4 0 0 0 4.8 0c0-1.1-.8-2.3-2.4-4.1Z"/>`
  ),

  vaatwasser: svg(
    `<rect x="3.6" y="3.2" width="16.8" height="17.6" rx="2.2"/>
     <path d="M3.6 8.2h16.8"/>
     <path d="M7 5.6h4"/>
     <path d="M8.4 12.4c1.2 1 2.2 1 3.6 0s2.4-1 3.6 0"/>
     <path d="M8.4 16.4c1.2 1 2.2 1 3.6 0s2.4-1 3.6 0"/>`
  ),

  wasmachine: svg(
    `<rect x="3.6" y="3.2" width="16.8" height="17.6" rx="2.2"/>
     <path d="M3.6 7.8h16.8"/>
     <path d="M6.8 5.5h2.4"/>
     <circle cx="12" cy="14.2" r="4"/>
     <path d="M9.4 12.6c1.4 1.1 2.2 1.1 3.4 0s2-1.1 3.4 0"/>`
  ),

  droger: svg(
    `<rect x="3.6" y="3.2" width="16.8" height="17.6" rx="2.2"/>
     <path d="M3.6 7.8h16.8"/>
     <path d="M6.8 5.5h2.4"/>
     <circle cx="12" cy="14.2" r="4"/>
     <path d="M12 11.4c-1.2 1.3-1.2 2.1 0 3.2s1.2 1.9 0 3.2"/>`
  ),

  airco: svg(
    `<rect x="2.8" y="4.6" width="18.4" height="7.4" rx="2.2"/>
     <path d="M6 8.4h9"/>
     <path d="M7.4 15.2c0 1.6-1 2-1 3.4M12 15.2c0 1.9-1.2 2.3-1.2 4M16.6 15.2c0 1.6-1 2-1 3.4"/>`
  ),

  zwembadpomp: svg(
    `<path d="M2.6 17.4c1.9 0 1.9 1.6 3.8 1.6s1.9-1.6 3.8-1.6 1.9 1.6 3.8 1.6 1.9-1.6 3.8-1.6 1.9 1.6 3.8 1.6"/>
     <path d="M2.6 12.6c1.9 0 1.9 1.6 3.8 1.6s1.9-1.6 3.8-1.6 1.9 1.6 3.8 1.6 1.9-1.6 3.8-1.6 1.9 1.6 3.8 1.6"/>
     <path d="M6.6 10.4V6.2a2.4 2.4 0 0 1 4.8 0v.6M14.4 10V5.6"/>`
  ),

  overig: svg(
    `<circle cx="12" cy="12" r="9"/>
     <circle cx="8.4" cy="12" r="1"/>
     <circle cx="12" cy="12" r="1"/>
     <circle cx="15.6" cy="12" r="1"/>`
  ),

  // ---- interface ----------------------------------------------------------

  arrowRight: svg(`<path d="M4.5 12h14M13 6.5l5.5 5.5-5.5 5.5"/>`),
  check: svg(`<path d="m4.8 12.6 4.6 4.6 9.8-10"/>`),
  close: svg(`<path d="M6 6l12 12M18 6 6 18"/>`),
  plus: svg(`<path d="M12 5v14M5 12h14"/>`),
  trash: svg(
    `<path d="M4 6.6h16"/>
     <path d="M9.4 6.6V4.8a1.2 1.2 0 0 1 1.2-1.2h2.8a1.2 1.2 0 0 1 1.2 1.2v1.8"/>
     <path d="M6.4 6.6 7.3 19a1.4 1.4 0 0 0 1.4 1.3h6.6a1.4 1.4 0 0 0 1.4-1.3l.9-12.4"/>`
  ),
  search: svg(`<circle cx="11" cy="11" r="6.6"/><path d="m16 16 4.4 4.4"/>`),
  warning: svg(
    `<path d="M12 3.6 21.2 19.4H2.8z"/>
     <path d="M12 9.6v4.4"/>
     <circle cx="12" cy="17" r="0.9" fill="currentColor" stroke="none"/>`
  ),
};
