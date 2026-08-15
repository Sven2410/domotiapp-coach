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
    // Easee is steered through `easee.action_command`, which wants the device
    // rather than an entity -- so the integration's own device is picked here
    // and its id is what gets sent.
    device: {
      domain: "easee",
      label: "Easee-integratie",
      hint: "Kies je laadpaal zoals hij in Home Assistant staat. Daar komt het device-id uit dat easee.action_command nodig heeft.",
    },
    service: "easee.action_command",
    field: "action_command",
    // The words differ per brand and even per firmware, so they are typed in
    // rather than baked in. These are what Easee uses today.
    actions: [
      { key: "start", label: "Starten", fallback: "start", icon: "play" },
      { key: "stop", label: "Stoppen", fallback: "stop", icon: "stop" },
      { key: "pause", label: "Pauzeren", fallback: "pause", icon: "pause" },
      { key: "resume", label: "Hervatten", fallback: "resume", icon: "resume" },
      // Rebooting is a different kind of thing from the other four: it drops
      // whatever the charger is doing and brings the box back up, so it stands
      // apart in the manual controls rather than in the row with them.
      {
        key: "reboot",
        label: "Herstarten",
        fallback: "reboot",
        icon: "reboot",
        care: true,
        hint: "Start de laadpaal opnieuw op. Een lopende laadsessie stopt daarmee; de paal is een halve minuut niet bereikbaar.",
      },
    ],
    fields: [
      {
        key: "status",
        label: "Status",
        hint: "Waar de paal mee bezig is: aangesloten, aan het laden, klaar.",
        filter: "all",
        needed: true,
        // The Easee integration reports these as English keys, whatever the
        // language Home Assistant is set to -- the panel reads the raw state,
        // not the translated one the frontend shows. So the whole list the
        // integration can send is spelled out here; anything outside it still
        // gets shown as it comes, rather than hidden.
        values: {
          authenticating: "Bezig met authenticeren",
          awaiting_authentication: "Wacht op authenticatie",
          awaiting_authorization: "Wacht op goedkeuring",
          awaiting_load_balancing: "Wacht op load balancing",
          awaiting_scheduled_start: "Wacht op geplande start",
          awaiting_smart_start: "Wacht op slimme start",
          awaiting_start: "Wacht tot het laden begint",
          charging: "Aan het laden",
          completed: "Laden voltooid",
          de_authorizing: "Goedkeuring intrekken",
          disconnected: "Geen auto aangesloten",
          erratic_ev: "Auto reageert onverwacht",
          error: "Fout bij laden",
          error_dead_powerboard: "Fout: defecte voedingsprint",
          error_overcurrent: "Fout: overbelasting",
          error_pen_fault: "Fout: PEN-fout in de aarde-nulleider",
          error_temperature_too_high: "Fout: temperatuur te hoog",
          offline: "Offline",
          paused_due_to_equalizer: "Onderbroken door de Equalizer",
          ready_to_charge: "Gereed om te laden",
          searching_for_master: "Zoekt de master",
          start_charging: "Start met laden",
          stop_charging: "Stopt met laden",
        },
      },
      {
        key: "no_current_reason",
        label: "Reden geen stroomvraag",
        hint: "Waarom er niet geladen wordt terwijl de auto eraan hangt.",
        filter: "all",
        values: {
          car_not_charging: "De auto laadt niet",
          charger_disabled: "Lader uitgeschakeld",
          charger_in_error_state: "Lader in foutstatus",
          circuit_fuse_too_low: "Zekering te laag",
          eq_too_low_current: "Equalizerstroom te laag",
          ev_behaving_erratic: "Auto reageert onverwacht",
          illegal_grid_type: "Ongeldig nettype",
          limited_by_cable_rating: "Begrensd door de laadkabel",
          limited_by_car: "Begrensd door de auto",
          limited_by_charger_dynamic_limit: "Dynamisch begrensd door de lader",
          limited_by_charger_max_limit: "Begrensd door de maximale limiet van de lader",
          limited_by_circuit_dynamic_limit: "Dynamisch begrensd door het stroomcircuit",
          limited_by_circuit_fuse: "Begrensd door de zekering",
          limited_by_circuit_max_limit: "Begrensd door de maximale limiet van het stroomcircuit",
          limited_by_equalizer: "Begrensd door de Equalizer",
          limited_by_load_balancing: "Begrensd door load balancing",
          limited_by_local_adjustment: "Begrensd door een lokale instelling",
          limited_by_offline_setting: "Begrensd door de offline-instelling",
          limited_by_schedule: "Begrensd door het laadschema",
          max_charger_current_too_low: "Maximale limiet van de lader te laag",
          max_circuit_current_too_low: "Maximale limiet van het stroomcircuit te laag",
          max_dynamic_charger_current_too_low: "Dynamische limiet van de lader te laag",
          max_dynamic_circuit_current_too_low: "Dynamische limiet van het stroomcircuit te laag",
          max_dynamic_offline_fallback_circuit_current_too_low:
            "Dynamische offline-terugvallimiet te laag",
          no_current_request: "Geen stroomvraag",
          none: "Geen",
          not_connected_to_master: "Niet verbonden met de master",
          not_requesting_current: "Geen stroomvraag",
          ok: "Geen belemmering",
          pending_authorization: "Wacht op goedkeuring",
          pending_schedule: "Wacht op het laadschema",
          phase_not_connected: "Fase niet aangesloten",
          undefined: "Onbekend",
          waiting_in_fully: "Wacht af",
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

/** The start/stop/pause/resume/reboot commands this brand takes, if any. */
export const brandActions = (device) => brandMeta(device)?.actions ?? [];

/** The integration device this brand is steered through, if it works that way. */
export const brandDevice = (device) => brandMeta(device)?.device;

/**
 * Whether a command can actually be sent to this device right now.
 *
 * Both halves have to be there: a brand that takes commands at all, and the
 * Home Assistant device to send them to. Without the second one the service
 * call would fail, and a button that cannot work should not be on screen.
 */
export const canCommand = (device) =>
  Boolean(brandMeta(device)?.service && brandActions(device).length && device?.device_id);

/**
 * A command as it goes out over the wire.
 *
 * The word is the customer's own: brands and even firmware versions disagree on
 * what to call these, so what is typed in wins and the brand's default is only
 * the starting point.
 */
export function commandCall(device, action) {
  const brand = brandMeta(device);
  const [domain, service] = brand.service.split(".");
  const word = (device.actions?.[action.key] ?? action.fallback).trim() || action.fallback;
  return { domain, service, data: { device_id: device.device_id, [brand.field]: word } };
}

/**
 * What the customer presses to say a device may run right now.
 *
 * A dishwasher is the case that makes this necessary: it can be switched on at
 * any moment the sun is out, and doing that to an empty one with its door open
 * is worse than not steering at all. Only whoever is standing in the kitchen
 * knows, so only they can say so.
 */
export function releaseCopy(device) {
  switch (device?.type) {
    case "vaatwasser":
      return {
        label: "Ingeruimd en dicht",
        hint: "Zet dit aan als de vaatwasser vol staat en de klep dicht zit. Anders zou de coach hem leeg kunnen laten spoelen.",
      };
    case "wasmachine":
      return {
        label: "Gevuld en dicht",
        hint: "Zet dit aan als de was erin zit en de deur dicht is.",
      };
    case "droger":
      return {
        label: "Gevuld en dicht",
        hint: "Zet dit aan als de droger gevuld is en de deur dicht is.",
      };
    case "laadpaal":
      return {
        label: "Mag laden",
        hint: "Zet dit aan als de auto eraan hangt en opgeladen mag worden.",
      };
    default:
      return {
        label: "Mag meedraaien",
        hint: "Zet dit aan als de coach dit apparaat nu mag inschakelen.",
      };
  }
}

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

  const missing = brandFields(device)
    .filter((field) => field.needed && !device.entities?.[field.key])
    .map((field) => field.label);

  const wanted = brandDevice(device);
  if (wanted && !device.device_id) missing.unshift(wanted.label);

  return missing;
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
