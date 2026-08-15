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

/**
 * The dishwasher programs the panel knows, with what they cost to run.
 *
 * These are specifications, not measurements: they come from the appliance's
 * own documentation and are what makes planning possible before the machine
 * has ever run. Anything shown from this table is marked as an estimate, so it
 * never reads as something a sensor said.
 *
 * `plan` is the reason the coach may or may not move a program: a rinse cycle
 * is pointless to postpone and machine care is not something to start on the
 * customer's behalf at all.
 *
 * `key` is Home Connect's own program name in the spelling Home Assistant's
 * integration uses; `alias` is the same program in the camel-case spelling the
 * appliance API and the alternative integration report.
 */
export const DISHWASHER_PROGRAMS = [
  { key: "eco_50", alias: "Eco50", label: "Eco 50 °C", minutes: 225, kwh: 0.8, peakW: 2100, peakMinutes: 40, plan: "ideal" },
  { key: "auto_2", alias: "Auto2", label: "Auto 45–65 °C", minutes: 135, kwh: 1.15, peakW: 2100, peakMinutes: 35, plan: "variable" },
  { key: "intensiv_70", alias: "Intensiv70", label: "Intensief 70 °C", minutes: 145, kwh: 1.4, peakW: 2100, peakMinutes: 50, plan: "yes" },
  { key: "kurz_60", alias: "Kurz60", label: "Express 60 °C", minutes: 60, kwh: 1.05, peakW: 2200, peakMinutes: 30, plan: "yes" },
  { key: "night_wash", alias: "NightWash", label: "Nacht Was", minutes: 210, kwh: 1.0, peakW: 1600, peakMinutes: 55, plan: "yes" },
  { key: "machine_care", alias: "MachineCare", label: "Machine Onderhoud", minutes: 120, kwh: 1.3, peakW: 2100, peakMinutes: 45, plan: "rare" },
  { key: "pre_rinse", alias: "PreRinse", label: "Voorspoelen", minutes: 15, kwh: 0.05, peakW: 0, peakMinutes: null, plan: "never" },
];

/** Why the coach would or would not move this program. */
export const PLAN_LABELS = {
  ideal: "ideaal om te verschuiven",
  yes: "te verschuiven",
  variable: "te verschuiven, maar de duur varieert",
  rare: "zelden nodig",
  never: "niet verschuiven",
};

/**
 * Every spelling a program arrives in, pointing at the same program.
 *
 * Home Assistant's own Home Connect integration reports
 * `dishcare_dishwasher_program_eco_50`; the alternative integration reports
 * `Dishcare.Dishwasher.Program.Eco50`. Both are the customer's dishwasher
 * saying "Eco 50", so both have to land on the same row.
 */
const PROGRAM_BY_VALUE = new Map(
  DISHWASHER_PROGRAMS.flatMap((program) => [
    [`dishcare_dishwasher_program_${program.key}`, program],
    [`Dishcare.Dishwasher.Program.${program.alias}`, program],
    [program.key, program],
    [program.alias, program],
  ])
);

/** The program behind a sensor value, or undefined for one we do not know. */
export const programFor = (raw) => PROGRAM_BY_VALUE.get(String(raw ?? ""));

/** What to show instead of a raw program value, for every spelling of it. */
const PROGRAM_VALUES = Object.fromEntries(
  [...PROGRAM_BY_VALUE].map(([value, program]) => [value, program.label])
);

export const DISHWASHER_BRANDS = [
  {
    id: "home_connect",
    label: "Home Connect",
    note: "Bosch, Siemens, Neff, Gaggenau en Constructa lopen allemaal via Home Connect.",
    fields: [
      {
        key: "status",
        label: "Status",
        hint: "Waar de vaatwasser mee bezig is: klaar voor gebruik, aan het draaien, afgelopen.",
        filter: "all",
        needed: true,
        // Home Connect's operation states, as Home Assistant reports them.
        values: {
          inactive: "Uit",
          ready: "Klaar voor gebruik",
          delayedstart: "Wacht op de starttijd",
          run: "Aan het draaien",
          pause: "Gepauzeerd",
          actionrequired: "Vraagt om aandacht",
          finished: "Afgelopen",
          error: "Storing",
          aborting: "Wordt afgebroken",
        },
      },
      {
        key: "program",
        label: "Geselecteerd programma",
        hint: "Welk programma klaarstaat. Daar hangt aan vast hoe lang het duurt en wat het kost — die gegevens zitten in het paneel.",
        filter: "all",
        needed: true,
        values: PROGRAM_VALUES,
      },
      {
        key: "remaining",
        label: "Resterende tijd",
        hint: "Hoe lang het programma nog duurt. Home Connect geeft hier de eindtijd; het paneel rekent zelf terug.",
        filter: "all",
        format: "countdown",
      },
      {
        key: "door",
        label: "Deurstand",
        // Deliberately not `needed`, and deliberately not part of the decision
        // to start: see `releaseCopy`.
        hint: "Alleen om te laten zien. Of de vaatwasser mag draaien, zegt de klant zelf met de vrijgaveknop.",
        filter: "all",
        values: {
          closed: "Dicht",
          locked: "Vergrendeld",
          open: "Open",
          // The same state arrives as a binary sensor at some installations.
          off: "Dicht",
          on: "Open",
        },
      },
    ],
    // Started by pressing something rather than by calling a service with a
    // word: Home Connect exposes the start as its own button entity, and which
    // one that is differs per integration and per appliance.
    buttons: [
      {
        key: "start",
        label: "Starten",
        icon: "play",
        needed: true,
        hint: "De knop die het geselecteerde programma start. Bij Home Connect heet die meestal \"Start\" of \"Start/Pauze\". De vaatwasser moet wel op afstand gestart mogen worden.",
        filter: "all",
      },
    ],
  },
  { id: "miele", label: "Miele", fields: [] },
  { id: "lg", label: "LG", fields: [] },
  { id: "overig", label: "Overig", fields: [] },
];

/**
 * Which brands belong to which device type.
 *
 * A type that is not in here has no brands at all and goes straight to its
 * power sensor -- a boiler is a boiler.
 */
const BRANDS_BY_TYPE = new Map([
  ["laadpaal", CHARGER_BRANDS],
  ["vaatwasser", DISHWASHER_BRANDS],
]);

/** The brands offered for a device type, or an empty list. */
export const brandsFor = (type) => BRANDS_BY_TYPE.get(type) ?? [];

/** The brand of a device, or undefined when it has none (or none yet). */
export const brandMeta = (device) =>
  brandsFor(device?.type).find((brand) => brand.id === device?.brand);

/** The extra entity fields this device asks for, beyond its power sensor. */
export const brandFields = (device) => brandMeta(device)?.fields ?? [];

/** The entities this brand is steered through, if it works that way. */
export const brandButtons = (device) => brandMeta(device)?.buttons ?? [];

/** Everything that gets an entity picker on the settings screen. */
export const brandEntityFields = (device) => [...brandFields(device), ...brandButtons(device)];

/** The start/stop/pause/resume/reboot commands this brand takes, if any. */
export const brandActions = (device) => brandMeta(device)?.actions ?? [];

/** The integration device this brand is steered through, if it works that way. */
export const brandDevice = (device) => brandMeta(device)?.device;

/**
 * How to press an entity, whatever kind of entity it turns out to be.
 *
 * The customer picks the thing that starts their appliance; whether that is a
 * button, a switch or a script is not something to ask them about.
 */
function pressCall(entityId) {
  const domain = entityId.split(".")[0];
  const service = { button: "press", input_button: "press" }[domain];
  if (service) return { domain, service, data: { entity_id: entityId } };
  // turn_on covers switch, script, scene, automation and input_boolean alike.
  return { domain: "homeassistant", service: "turn_on", data: { entity_id: entityId } };
}

/**
 * Every command this device can actually be sent right now.
 *
 * Two mechanisms live side by side, because appliances do. A charger like Easee
 * takes one service call with a word in it, aimed at a Home Assistant device. A
 * dishwasher on Home Connect is started by pressing an entity. Both come out of
 * here as the same thing: a label, an icon and a call.
 *
 * Commands whose half is missing are left out rather than shown broken -- a
 * button that cannot work should not be on screen.
 */
export function deviceCommands(device) {
  const brand = brandMeta(device);
  if (!brand) return [];

  const commands = [];

  if (brand.service && device?.device_id) {
    const [domain, service] = brand.service.split(".");
    for (const action of brand.actions ?? []) {
      // The word is the customer's own: brands and even firmware versions
      // disagree on what to call these, so what is typed in wins and the
      // brand's default is only the starting point.
      const word = (device.actions?.[action.key] ?? action.fallback).trim() || action.fallback;
      commands.push({
        ...action,
        call: { domain, service, data: { device_id: device.device_id, [brand.field]: word } },
      });
    }
  }

  for (const button of brand.buttons ?? []) {
    const entityId = device?.entities?.[button.key];
    if (entityId) commands.push({ ...button, call: pressCall(entityId) });
  }

  return commands;
}

/** Whether there is anything to send to this device at all. */
export const canCommand = (device) => deviceCommands(device).length > 0;

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

  const missing = brandEntityFields(device)
    .filter((field) => field.needed && !device.entities?.[field.key])
    .map((field) => field.label);

  const wanted = brandDevice(device);
  if (wanted && !device.device_id) missing.unshift(wanted.label);

  return missing;
}

/**
 * The device types that run a program with a length, and so can have a time by
 * which they must be finished.
 *
 * A charger does not belong here: a car is done when it is full, and how long
 * that takes is a question about the car rather than about the programme.
 */
export const PROGRAM_TYPES = ["vaatwasser", "wasmachine", "droger"];

/** Whether "must be finished by" means anything for this device. */
export const canHaveDeadline = (device) =>
  Boolean(device?.controllable) && PROGRAM_TYPES.includes(device?.type);

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
