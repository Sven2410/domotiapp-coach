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
  bolt: svg(`<path d="M13.4 2.6 4.8 13.4h5.6l-.8 8 8.6-10.8h-5.6z"/>`),

  // Gas en water op Contract (v0.129.0), elk met een eigen kaart.
  vlam: svg(
    `<path d="M12 21.2c-3.6 0-6.3-2.6-6.3-6.1 0-3.2 2.2-5.3 3.7-7.6.4 1.9 1.4 3 2.5 3.6-.2-2.9.9-5.7 3.1-8.3.6 3.6 4.9 6.6 4.9 12.1 0 3.5-2.6 6.3-7.9 6.3Z"/>
     <path d="M12 21.2c-1.6 0-2.8-1.2-2.8-2.8 0-1.8 1.5-2.7 2.3-4.3.9 1.4 3.3 2.4 3.3 4.4 0 1.5-1.2 2.7-2.8 2.7Z"/>`
  ),
  druppel: svg(`<path d="M12 2.8c3.1 4 6.2 7.6 6.2 11.6a6.2 6.2 0 0 1-12.4 0c0-4 3.1-7.6 6.2-11.6Z"/>`),

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
    `<rect x="4.2" y="6.4" width="14.4" height="11.2" rx="2.2"/>
     <path d="M18.6 10v4h1.6a.6.6 0 0 0 .6-.6v-2.8a.6.6 0 0 0-.6-.6Z"/>
     <path d="m12.2 8.8-2.4 3.6h3.2l-2.4 3.6"/>`
  ),

  // De twee knoppen van de thuisbatterij (23-09-2026; daarvoor stond er
  // een bliksem en een pauzeteken, en dat laatste zei niets over leegladen).
  // Dezelfde accu als hierboven, met een pijl die erin gaat of eruit komt.
  accuVol: svg(
    `<rect x="4.2" y="6.4" width="14.4" height="11.2" rx="2.2"/>
     <path d="M18.6 10v4h1.6a.6.6 0 0 0 .6-.6v-2.8a.6.6 0 0 0-.6-.6Z"/>
     <path d="M11.4 8.6v6.6M8.8 12.6l2.6 2.6 2.6-2.6"/>`
  ),

  accuLeeg: svg(
    `<rect x="4.2" y="6.4" width="14.4" height="11.2" rx="2.2"/>
     <path d="M18.6 10v4h1.6a.6.6 0 0 0 .6-.6v-2.8a.6.6 0 0 0-.6-.6Z"/>
     <path d="M11.4 15.4V8.8M8.8 11.4l2.6-2.6 2.6 2.6"/>`
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

  airco: svg(
    `<rect x="2.8" y="4.6" width="18.4" height="7.4" rx="2.2"/>
     <path d="M6 8.4h9"/>
     <path d="M7.4 15.2c0 1.6-1 2-1 3.4M12 15.2c0 1.9-1.2 2.3-1.2 4M16.6 15.2c0 1.6-1 2-1 3.4"/>`
  ),

  overig: svg(
    `<circle cx="12" cy="12" r="9"/>
     <circle cx="8.4" cy="12" r="1"/>
     <circle cx="12" cy="12" r="1"/>
     <circle cx="15.6" cy="12" r="1"/>`
  ),

  // ---- wat er aan een smart plug hangt (v0.120.0) ----------------------------
  // Een stip is een pad van nul lang: de ronde lijnkap maakt er een rondje van
  // in dezelfde dikte als de rest.

  wasmachine: svg(
    `<rect x="4" y="2.8" width="16" height="18.4" rx="2.2"/>
     <path d="M4 7.4h16M7 5.1h2.4M16.4 5.1h.01"/>
     <circle cx="12" cy="14.2" r="4.4"/>
     <path d="M9.4 14.8c1-.8 1.8-.8 2.6 0s1.6.8 2.6 0"/>`
  ),

  droger: svg(
    `<rect x="4" y="2.8" width="16" height="18.4" rx="2.2"/>
     <path d="M4 7.4h16M7 5.1h2.4M16.4 5.1h.01"/>
     <circle cx="12" cy="14.2" r="4.4"/>
     <circle cx="12" cy="14.2" r="1.6"/>`
  ),

  koelkast: svg(
    `<rect x="5.4" y="2.6" width="13.2" height="18.8" rx="2"/>
     <path d="M5.4 9.6h13.2M8.4 5.2v2M8.4 12.2v3.2"/>`
  ),

  vriezer: svg(
    `<rect x="5.4" y="2.6" width="13.2" height="18.8" rx="2"/>
     <path d="M8.4 5.2v2.2"/>
     <path d="M12 10.4v7.4M8.8 12.25l6.4 3.7M8.8 15.95l6.4-3.7"/>`
  ),

  oven: svg(
    `<rect x="3.4" y="3.6" width="17.2" height="16.8" rx="2"/>
     <path d="M3.4 8.4h17.2M6.6 6h.01M9.4 6h.01M14.4 6h3"/>
     <rect x="6.6" y="11.2" width="10.8" height="6.2" rx="1"/>`
  ),

  magnetron: svg(
    `<rect x="2.6" y="5" width="18.8" height="14" rx="2"/>
     <rect x="5.2" y="7.8" width="9.4" height="8.4" rx="1"/>
     <path d="M17.8 8.6h.01M17.8 11.4h.01M17.8 14.2v1.8"/>`
  ),

  airfryer: svg(
    `<path d="M4.6 9.6A5.4 5.4 0 0 1 10 4.2h4a5.4 5.4 0 0 1 5.4 5.4V19a1.6 1.6 0 0 1-1.6 1.6H6.2A1.6 1.6 0 0 1 4.6 19Z"/>
     <path d="M4.6 13.2h14.8M9.4 16.8h5.2"/>
     <circle cx="12" cy="8.6" r="1.6"/>`
  ),

  waterkoker: svg(
    `<path d="M5.4 20.6h10.8"/>
     <path d="M6.2 20.6 7.4 8h7l1.2 12.6"/>
     <path d="M8.4 8 9 5.6h3.8l.6 2.4"/>
     <path d="M15 10.4h1.8a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2h-1.3"/>`
  ),

  koffiezetapparaat: svg(
    `<rect x="4" y="2.8" width="16" height="18.4" rx="2"/>
     <path d="M4 7.2h16M12 9.2v1.8"/>
     <path d="M9 13h5.6v2.8a2.4 2.4 0 0 1-2.4 2.4h-.8A2.4 2.4 0 0 1 9 15.8Z"/>
     <path d="M14.6 13.8h.6a1.2 1.2 0 0 1 0 2.4h-.6"/>`
  ),

  televisie: svg(
    `<rect x="2.6" y="4" width="18.8" height="12.6" rx="1.8"/>
     <path d="M8.4 20.4h7.2M12 16.6v3.8"/>`
  ),

  computer: svg(
    `<rect x="4.6" y="4.6" width="14.8" height="10.4" rx="1.4"/>
     <path d="M2.6 18.6h18.8L19.8 15H4.2Z"/>`
  ),

  server: svg(
    `<rect x="5" y="2.8" width="14" height="18.4" rx="2"/>
     <path d="M5 8.9h14M5 15.1h14"/>
     <path d="M8 5.9h.01M8 12h.01M8 18.1h.01M12 5.9h4M12 12h4M12 18.1h4"/>`
  ),

  router: svg(
    `<rect x="3" y="13" width="18" height="6.6" rx="1.8"/>
     <path d="M7 16.3h.01M10 16.3h.01M14.4 16.3h3"/>
     <path d="M9.6 9.6a3.4 3.4 0 0 1 4.8 0M7.4 7.2a6.6 6.6 0 0 1 9.2 0"/>`
  ),

  aquarium: svg(
    `<rect x="2.8" y="5.4" width="18.4" height="13.6" rx="1.6"/>
     <path d="M2.8 8.8c1.5 1 3.1 1 4.6 0s3.1-1 4.6 0 3.1 1 4.6 0 3.1-1 4.6 0"/>
     <path d="M7.4 14c1.6-2 4.4-2 6 0-1.6 2-4.4 2-6 0Z"/>
     <path d="m13.4 14 2.4-1.6v3.2Z"/>`
  ),

  vijverpomp: svg(
    `<path d="M12 15.6V5"/>
     <path d="M12 7.2c-2.4-1-4.8.2-5.8 3.4M12 7.2c2.4-1 4.8.2 5.8 3.4"/>
     <path d="M2.6 16c1.5 1 3.1 1 4.6 0s3.1-1 4.6 0 3.1 1 4.6 0 3.1-1 4.6 0M2.6 20c1.5 1 3.1 1 4.6 0s3.1-1 4.6 0 3.1 1 4.6 0 3.1-1 4.6 0"/>`
  ),

  kachel: svg(
    `<rect x="3.4" y="10" width="17.2" height="9.4" rx="1.8"/>
     <path d="M7.6 10v9.4M12 10v9.4M16.4 10v9.4M5.6 19.4v1.4M18.4 19.4v1.4"/>
     <path d="M8 3.4c-.9 1-.9 2 0 3.2M12 3.4c-.9 1-.9 2 0 3.2M16 3.4c-.9 1-.9 2 0 3.2"/>`
  ),

  ventilator: svg(
    `<circle cx="12" cy="9.8" r="7"/>
     <path d="M12 9.8c-.4-2.6.6-4.2 2.6-4.4M12 9.8c2.4.9 3.2 2.6 2.2 4.4M12 9.8c-2 1.7-3.8 1.6-4.8 0"/>
     <path d="M12 16.8v3.6M8.4 20.4h7.2"/>`
  ),

  ontvochtiger: svg(
    `<rect x="5.4" y="2.8" width="13.2" height="18.4" rx="2.4"/>
     <path d="M8.4 5.8h7.2M8.4 8h7.2"/>
     <path d="M12 10.6c-1.8 2.1-2.7 3.4-2.7 4.7a2.7 2.7 0 0 0 5.4 0c0-1.3-.9-2.6-2.7-4.7Z"/>`
  ),

  fietslader: svg(
    `<circle cx="5.6" cy="16" r="3.4"/>
     <circle cx="18.4" cy="16" r="3.4"/>
     <path d="M5.6 16 9 9.6h6.4M9 9.6l3 6.4 3.4-6.4 3 6.4M12 16H5.6M7.8 7.6h2.6M15.4 9.6l-.6-2h1.8"/>`
  ),

  maairobot: svg(
    `<rect x="2.8" y="11" width="18.4" height="5.6" rx="2.8"/>
     <path d="M7.6 11c.6-2 2.3-3.2 4.4-3.2s3.8 1.2 4.4 3.2"/>
     <circle cx="7" cy="18.2" r="1.8"/>
     <circle cx="17" cy="18.2" r="1.8"/>
     <path d="M2.6 21.4h1.6M10 21.4h4M19.8 21.4h1.6"/>`
  ),

  lamp: svg(
    `<path d="M12 3.2a6 6 0 0 0-3.6 10.8c.6.5.8 1.1.8 1.8v1.4h5.6v-1.4c0-.7.2-1.3.8-1.8A6 6 0 0 0 12 3.2Z"/>
     <path d="M10 20.4h4"/>`
  ),

  spelcomputer: svg(
    `<path d="M7.4 7.6h9.2a4.4 4.4 0 0 1 4.3 3.5l1 4.9a2.6 2.6 0 0 1-4.4 2.3L15.4 16H8.6l-2.1 2.3A2.6 2.6 0 0 1 2.1 16l1-4.9a4.4 4.4 0 0 1 4.3-3.5Z"/>
     <path d="M7.6 10.4v3.2M6 12h3.2M15.8 11h.01M17.6 12.8h.01"/>`
  ),

  // ---- interface ----------------------------------------------------------

  arrowRight: svg(`<path d="M4.5 12h14M13 6.5l5.5 5.5-5.5 5.5"/>`),
  arrowLeft: svg(`<path d="M19.5 12h-14M11 6.5 5.5 12l5.5 5.5"/>`),
  chevronRight: svg(`<path d="m9.5 5.5 6.5 6.5-6.5 6.5"/>`),
  bell: svg(
    `<path d="M18 9.4a6 6 0 1 0-12 0c0 5.2-2 6.6-2 6.6h16s-2-1.4-2-6.6Z"/>
     <path d="M13.7 19.4a2 2 0 0 1-3.4 0"/>`
  ),
  check: svg(`<path d="m4.8 12.6 4.6 4.6 9.8-10"/>`),
  close: svg(`<path d="M6 6l12 12M18 6 6 18"/>`),
  plus: svg(`<path d="M12 5v14M5 12h14"/>`),
  trash: svg(
    `<path d="M4 6.6h16"/>
     <path d="M9.4 6.6V4.8a1.2 1.2 0 0 1 1.2-1.2h2.8a1.2 1.2 0 0 1 1.2 1.2v1.8"/>
     <path d="M6.4 6.6 7.3 19a1.4 1.4 0 0 0 1.4 1.3h6.6a1.4 1.4 0 0 0 1.4-1.3l.9-12.4"/>`
  ),
  search: svg(`<circle cx="11" cy="11" r="6.6"/><path d="m16 16 4.4 4.4"/>`),

  // ---- manual control ------------------------------------------------------
  // Each command gets its own shape: on a row of buttons that all do something
  // to the same charger, colour and label alone are not enough to tell them
  // apart at a glance.

  play: svg(`<path d="M8 5.4 19 12 8 18.6z"/>`),
  stop: svg(`<rect x="6.4" y="6.4" width="11.2" height="11.2" rx="1.8"/>`),
  pause: svg(`<path d="M9.4 5.6v12.8M14.6 5.6v12.8"/>`),
  resume: svg(`<path d="M5.4 5.6v12.8"/><path d="M9.4 5.4 19.4 12l-10 6.6z"/>`),
  reboot: svg(
    `<path d="M20 12a8 8 0 1 1-2.6-5.9"/>
     <path d="M20.4 4.2v4.6h-4.6"/>`
  ),
  warning: svg(
    `<path d="M12 3.6 21.2 19.4H2.8z"/>
     <path d="M12 9.6v4.4"/>
     <circle cx="12" cy="17" r="0.9" fill="currentColor" stroke="none"/>`
  ),
};
