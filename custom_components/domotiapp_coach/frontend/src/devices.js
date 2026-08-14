/**
 * The device types a customer can attach to the energy flow.
 *
 * Order matters: it is the order shown in the picker, heaviest and most common
 * first. "Overig" carries a free-text name so anything not on the list still
 * fits.
 */

export const DEVICE_TYPES = [
  { id: "laadpaal", label: "Laadpaal", icon: "laadpaal" },
  { id: "thuisbatterij", label: "Thuisbatterij", icon: "thuisbatterij" },
  { id: "warmtepomp", label: "Warmtepomp", icon: "warmtepomp" },
  { id: "boiler", label: "Boiler", icon: "boiler" },
  { id: "vaatwasser", label: "Vaatwasser", icon: "vaatwasser" },
  { id: "wasmachine", label: "Wasmachine", icon: "wasmachine" },
  { id: "droger", label: "Droger", icon: "droger" },
  { id: "airco", label: "Airco", icon: "airco" },
  { id: "zwembadpomp", label: "Zwembadpomp", icon: "zwembadpomp" },
  { id: "overig", label: "Overig", icon: "overig" },
];

/**
 * Charging points, by brand.
 *
 * Which extra entities a charger offers is entirely a brand question: not every
 * one of them can be started, stopped or paused, and the ones that can do not
 * agree on how. So the brand is the first thing asked, and it decides which
 * fields appear -- one dropdown instead of a screen full of fields that only
 * apply to somebody else's charger.
 *
 * `fields` are the entities beyond the power sensor, which every device has.
 * `needed` marks the ones the coach cannot steer without; they are only ever
 * insisted on once steering is switched on for that device.
 *
 * Only Easee is worked out. The rest are listed because a customer should be
 * able to say what they have before we get round to their brand.
 */
export const CHARGER_BRANDS = [
  {
    id: "easee",
    label: "Easee",
    fields: [
      {
        key: "status",
        label: "Status",
        hint: "Waar de paal mee bezig is: aangesloten, aan het laden, klaar.",
        filter: "all",
        needed: true,
        // The Easee integration reports these as words. Anything it sends that
        // is not in this list is shown as it comes, rather than hidden.
        values: {
          disconnected: "Niet aangesloten",
          awaiting_start: "Wacht op start",
          ready_to_charge: "Klaar om te laden",
          charging: "Aan het laden",
          completed: "Klaar",
          error: "Storing",
        },
      },
      {
        key: "no_current_reason",
        label: "Reden geen stroomvraag",
        hint: "Waarom er niet geladen wordt terwijl de auto eraan hangt.",
        filter: "all",
        values: {
          no_reason: "Geen belemmering",
          undefined: "Onbekend",
          loadbalancing_circuit_limit: "Begrensd door de groep",
          loadbalancing_charger_limit: "Begrensd door de paal",
          charger_limit: "Begrensd door de paal",
          circuit_limit: "Begrensd door de groep",
          waiting_in_queue: "Wacht op zijn beurt",
        },
      },
      {
        key: "lifetime_energy",
        label: "Levensduur verbruik",
        hint: "Alles wat deze paal ooit geladen heeft, in kWh.",
        filter: "all",
      },
      {
        key: "max_limit",
        label: "Maximale limiet lader",
        hint: "Hoeveel ampère de paal maximaal mag leveren. Hier stuurt de coach straks op.",
        filter: "all",
        needed: true,
      },
      {
        key: "current",
        label: "Stroom",
        hint: "Wat de paal op dit moment levert, in ampère.",
        filter: "all",
      },
    ],
  },
  { id: "zaptec", label: "Zaptec", fields: [] },
  { id: "wallbox", label: "Wallbox", fields: [] },
  { id: "zappi", label: "Zappi", fields: [] },
  { id: "peblar", label: "Peblar", fields: [] },
  { id: "overig", label: "Overig", fields: [] },
];

const BRAND_BY_ID = new Map(CHARGER_BRANDS.map((b) => [b.id, b]));

/** The brand of a device, or undefined when it has none (or none yet). */
export const brandMeta = (device) =>
  device?.type === "laadpaal" ? BRAND_BY_ID.get(device.brand) : undefined;

/** The extra entity fields this device asks for, beyond its power sensor. */
export const brandFields = (device) => brandMeta(device)?.fields ?? [];

/**
 * What still has to be filled in before this device can be steered.
 *
 * Everything is optional right up to the moment somebody ticks "may be
 * steered" -- at which point the entities the steering needs are no longer
 * optional, and saying so on the spot beats finding out when it silently does
 * nothing.
 */
export function missingForControl(device) {
  if (!device?.controllable) return [];
  return brandFields(device)
    .filter((field) => field.needed && !device.entities?.[field.key])
    .map((field) => field.label);
}

const BY_ID = new Map(DEVICE_TYPES.map((t) => [t.id, t]));

/** Metadata for a device type, falling back to "Overig" for unknown ids. */
export const typeMeta = (type) => BY_ID.get(type) ?? BY_ID.get("overig");

/** What to call a configured device: its own name if it has one, else its type. */
export function deviceLabel(device) {
  const name = (device?.name || "").trim();
  if (name) return name;
  return typeMeta(device?.type).label;
}

/**
 * Power above which a device counts as running.
 *
 * Standby draw is real -- a dishwasher sitting idle still reports a few watts --
 * so a bare "> 0" would show every device as active forever and the two bubbles
 * would never mean anything.
 */
export const ACTIVE_WATTS = 20;
