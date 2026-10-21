/**
 * The device types a customer can attach to the energy flow.
 *
 * Order matters: it is the order shown in the picker, heaviest and most common
 * first. "Overig" carries a free-text name so anything not on the list still
 * fits.
 *
 * Alleen wat de coach werkelijk iets met een apparaat kan. De eigenaar op 19-09-2026
 * haalde de thuisbatterij, de warmtepomp, de wasmachine, de droger en de
 * zwembadpomp eruit: hetzelfde argument als bij de merken van een laadpaal,
 * een regel in een lijst leest als een belofte.
 *
 * De tabellen in dit bestand houden het Nederlands, gemerkt met `nt` (v0.139.0): bij het
 * laden is de taal nog niet bekend. De hulpfuncties hieronder (`inTaal`, `brandFields`,
 * `valueLabel`, `kindLabel`, ...) vertalen op het moment dat ze gevraagd worden, zodat elk
 * scherm dat ze gebruikt de taal van nu krijgt. Wat bewaard of vergeleken wordt (de namen
 * van de programma's in de instellingen, `PROGRAM_BY_LABEL`) blijft Nederlands; zie
 * docs/taal.md.
 */

import { datum, nt, t } from "./i18n.js";

/**
 * Een zin met woorden erin, in een tabel (v0.139.0). De tabel houdt het Nederlands zoals het
 * altijd was, ingevuld ("de wasmachine"); `sleutels` en `vars` zijn voor `inTaal`, dat
 * dezelfde zin met dezelfde woorden in de taal van nu geeft.
 */
function metWoorden(veld, zin, woorden) {
  const ingevuld = zin.replace(/\{(\w+)\}/g, (heel, naam) => (naam in woorden ? String(woorden[naam]) : heel));
  return { [veld]: ingevuld, sleutels: { [veld]: zin }, vars: woorden };
}

export const DEVICE_TYPES = [
  { id: "laadpaal", label: nt("Laadpaal"), icon: "laadpaal" },
  // Terug sinds 22-09-2026, en nu omdat de coach hem werkelijk stuurt.
  { id: "thuisbatterij", label: nt("Thuisbatterij"), icon: "thuisbatterij" },
  { id: "boiler", label: nt("Boiler"), icon: "boiler" },
  { id: "vaatwasser", label: nt("Vaatwasser"), icon: "vaatwasser" },
  // Terug sinds v0.124.0, nu de coach ze start zoals de vaatwasser. De eigenaar
  // op 15-10-2026: "Ik wil dat de coach wel weer de apparaten aanmaakt:
  // Wasmachine droger en vriezer."
  { id: "wasmachine", label: nt("Wasmachine"), icon: "wasmachine" },
  { id: "droger", label: nt("Droger"), icon: "droger" },
  // Sinds v0.125.0: een vriezer die de coach in de gaten houdt en niet stuurt.
  { id: "vriezer", label: nt("Vriezer"), icon: "vriezer" },
  // Sinds v0.131.0: een koelkast, net zo, met een grens van 10 °C.
  { id: "koelkast", label: nt("Koelkast"), icon: "koelkast" },
  { id: "airco", label: nt("Airco"), icon: "airco" },
  // Sinds v0.120.0: wat aan een smart plug hangt, zie `PLUG_APPLIANCES`.
  { id: "smartplug", label: nt("Smart plug"), icon: "plug" },
  { id: "overig", label: nt("Overig"), icon: "overig" },
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
 * Only Easee is supported. De eigenaar took the other brands out on 04-09-2026: a
 * brand in a list reads as a promise, and there was none behind it. Op
 * 19-09-2026 ging "overig" er om dezelfde reden uit: een laadpaal die de coach
 * niet kan sturen is geen laadpaal maar een apparaat dat hij meet, en daarvoor
 * is er het type "Overig".
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
      label: nt("Easee-integratie"),
      hint: nt("Kies je laadpaal zoals hij in Home Assistant staat. Daar komt het device-id uit dat easee.action_command nodig heeft."),
    },
    service: "easee.action_command",
    field: "action_command",
    // De tweede dienst: die schrijft een getal in plaats van een woord. Hier
    // gaan pauzeren en hervatten doorheen, en straks ook de coach zelf.
    limitService: "easee.set_charger_dynamic_limit",
    // The words differ per brand and even per firmware, so they are typed in
    // rather than baked in. These are what Easee uses today.
    actions: [
      { key: "start", label: nt("Starten"), fallback: "start", icon: "play" },
      { key: "stop", label: nt("Stoppen"), fallback: "stop", icon: "stop" },
      // Pauzeren en hervatten gaan niet als opdracht maar als limiet, en dat is
      // geen voorkeur maar een meting. Het commando `pause` schrijft bij Easee
      // zelf een 0 in de dynamische laderlimiet en die staat na ongeveer een
      // minuut vanzelf weer terug, waarna de auto verder laadt. Als opdracht is
      // pauzeren dus onbetrouwbaar. Diezelfde 0 met houdbaarheid oneindig blijft
      // wel staan, en laat de goedkeuring met rust: gemeten aan een echte paal
      // op 17-08-2026 bleef de reden op `max_dynamic_charger_current_too_low`
      // staan en sprong hij niet naar `pending_authorization`, zoals bij stop.
      //
      // Daarom hebben deze twee geen woord dat de klant kan invullen: er valt
      // niets te spellen aan een getal.
      {
        key: "pause",
        label: nt("Pauzeren"),
        icon: "pause",
        limit: { current: 0, time_to_live: 0 },
      },
      {
        key: "resume",
        label: nt("Hervatten"),
        icon: "resume",
        // "max" wordt vlak voor het versturen opgezocht: de maximale limiet van
        // de lader zelf. Is die niet uit te lezen, dan 32, want de laderlimiet
        // begrenst dat alsnog. Zo geeft hervatten de paal terug wat hij aankan
        // en niet een getal dat wij verzinnen.
        limit: { current: "max", time_to_live: 0 },
      },
      // Rebooting is a different kind of thing from the other four: it drops
      // whatever the charger is doing and brings the box back up, so it stands
      // apart in the manual controls rather than in the row with them.
      {
        key: "reboot",
        label: nt("Herstarten"),
        fallback: "reboot",
        icon: "reboot",
        care: true,
        // `note` is what stands under the button in the manual controls; a
        // `hint` belongs to the settings screen and would read as instructions
        // from another room here.
        note: nt("Start de laadpaal opnieuw op. Een lopende laadsessie stopt daarmee; de lader is een halve minuut niet bereikbaar."),
      },
    ],
    fields: [
      {
        key: "status",
        label: nt("Status"),
        hint: nt("Waar de lader mee bezig is: aangesloten, aan het laden, klaar."),
        filter: "all",
        needed: true,
        // The Easee integration reports these as English keys, whatever the
        // language Home Assistant is set to -- the panel reads the raw state,
        // not the translated one the frontend shows. So the whole list the
        // integration can send is spelled out here; anything outside it still
        // gets shown as it comes, rather than hidden.
        values: {
          authenticating: nt("Bezig met authenticeren"),
          awaiting_authentication: nt("Wacht op authenticatie"),
          awaiting_authorization: nt("Wacht op goedkeuring"),
          awaiting_load_balancing: nt("Wacht op load balancing"),
          awaiting_scheduled_start: nt("Wacht op geplande start"),
          awaiting_smart_start: nt("Wacht op slimme start"),
          awaiting_start: nt("Wacht tot het laden begint"),
          charging: nt("Aan het laden"),
          completed: nt("Laden voltooid"),
          de_authorizing: nt("Goedkeuring intrekken"),
          disconnected: nt("Geen auto aangesloten"),
          erratic_ev: nt("Auto reageert onverwacht"),
          error: nt("Fout bij laden"),
          error_dead_powerboard: nt("Fout: defecte voedingsprint"),
          error_overcurrent: nt("Fout: overbelasting"),
          error_pen_fault: nt("Fout: PEN-fout in de aarde-nulleider"),
          error_temperature_too_high: nt("Fout: temperatuur te hoog"),
          offline: nt("Offline"),
          paused_due_to_equalizer: nt("Onderbroken door de Equalizer"),
          ready_to_charge: nt("Gereed om te laden"),
          searching_for_master: nt("Zoekt de master"),
          start_charging: nt("Start met laden"),
          stop_charging: nt("Stopt met laden"),
        },
      },
      {
        key: "no_current_reason",
        label: nt("Reden geen stroomvraag"),
        hint: nt("Waarom er niet geladen wordt terwijl de auto eraan hangt."),
        filter: "all",
        values: {
          car_not_charging: nt("De auto laadt niet"),
          charger_disabled: nt("Lader uitgeschakeld"),
          charger_in_error_state: nt("Lader in foutstatus"),
          circuit_fuse_too_low: nt("Zekering te laag"),
          eq_too_low_current: nt("Equalizerstroom te laag"),
          ev_behaving_erratic: nt("Auto reageert onverwacht"),
          illegal_grid_type: nt("Ongeldig nettype"),
          limited_by_cable_rating: nt("Begrensd door de laadkabel"),
          limited_by_car: nt("Begrensd door de auto"),
          limited_by_charger_dynamic_limit: nt("Dynamisch begrensd door de lader"),
          limited_by_charger_max_limit: nt("Begrensd door de maximale limiet van de lader"),
          limited_by_circuit_dynamic_limit: nt("Dynamisch begrensd door het stroomcircuit"),
          limited_by_circuit_fuse: nt("Begrensd door de zekering"),
          limited_by_circuit_max_limit: nt("Begrensd door de maximale limiet van het stroomcircuit"),
          limited_by_equalizer: nt("Begrensd door de Equalizer"),
          limited_by_load_balancing: nt("Begrensd door load balancing"),
          limited_by_local_adjustment: nt("Begrensd door een lokale instelling"),
          limited_by_offline_setting: nt("Begrensd door de offline-instelling"),
          limited_by_schedule: nt("Begrensd door het laadschema"),
          max_charger_current_too_low: nt("Maximale limiet van de lader te laag"),
          max_circuit_current_too_low: nt("Maximale limiet van het stroomcircuit te laag"),
          max_dynamic_charger_current_too_low: nt("Dynamische limiet van de lader te laag"),
          max_dynamic_circuit_current_too_low: nt("Dynamische limiet van het stroomcircuit te laag"),
          max_dynamic_offline_fallback_circuit_current_too_low:
            nt("Dynamische offline-terugvallimiet te laag"),
          no_current_request: nt("Geen stroomvraag"),
          none: nt("Geen"),
          not_connected_to_master: nt("Niet verbonden met de master"),
          not_requesting_current: nt("Geen stroomvraag"),
          ok: nt("Geen belemmering"),
          pending_authorization: nt("Wacht op goedkeuring"),
          pending_schedule: nt("Wacht op het laadschema"),
          phase_not_connected: nt("Fase niet aangesloten"),
          undefined: nt("Onbekend"),
          waiting_in_fully: nt("Wacht af"),
          waiting_in_queue: nt("Wacht op zijn beurt"),
        },
      },
      {
        key: "max_limit",
        label: nt("Maximale limiet lader"),
        hint: nt("Hoeveel ampère de lader maximaal mag leveren. Dit is de bovengrens die vastligt."),
        filter: "all",
        needed: true,
      },
      {
        key: "dynamic_limit",
        label: nt("Dynamisch limiet lader"),
        // Not `needed`: the coach cannot write to it yet, and marking it
        // required would block saving a charger that works fine today.
        hint: nt("De limiet die van moment tot moment mag meebewegen, in ampère. Hij staat op 0 zolang er niet geladen wordt. Hier gaat de coach straks op sturen. Hij blijft altijd onder de maximale limiet."),
        filter: "all",
      },
      {
        key: "circuit_limit",
        label: nt("Dynamisch limiet stroomcircuit"),
        // Bij Easee de dynamische limiet van het circuit waar de paal op zit.
        // Een auto trekt soms iets meer dan de laderlimiet, en boven deze grens
        // grijpt de paal zelf in: in de klantwoning op 06-09-2026 trok een Ford
        // 16,9 A op een groep van 16 A, de paal herstartte en de auto ging in
        // storing. Met deze sensor blijft de coach er zoveel onder als de auto
        // erboven zit.
        hint: nt("De limiet van de groep waar de paal op zit, in ampère. Daarmee blijft de coach eronder als de auto iets meer trekt dan gevraagd."),
        filter: "all",
      },
      {
        key: "circuit_max",
        label: nt("Maximale limiet stroomcircuit"),
        // De vaste grens van de groep. De dynamische hierboven kan erboven
        // staan: in de klantwoning stond die sinds 30-09-2026 op 40 A bij een
        // groep van 16 A, en dan keek de coach naar 40. De paal houdt zich aan
        // de laagste van de twee, en de coach dus ook.
        hint: nt("De vaste grens van de groep waar de paal op zit, in ampère. De coach neemt de laagste van deze en de dynamische limiet hierboven."),
        filter: "all",
      },
      {
        key: "current",
        label: "Stroom",
        // "Stroom" is elders elektriciteit (Contract: "Electricity"); hier ampère, met een
        // eigen sleutel voor het Engels (`inTaal`).
        sleutels: { label: nt("Stroom (wat de lader levert, in ampère)") },
        hint: nt("Wat de lader op dit moment levert, in ampère."),
        filter: "all",
      },
    ],
  },
  {
    id: "alfen",
    label: "Alfen",
    // Alfen (Eve Single en Double Pro-line) via de integratie "alfen_modbus"
    // (HACS, Modbus TCP). Geen dienst met een woord en geen apparaat-id: de
    // coach schrijft de maximale stroomlimiet (een number-entiteit) en leest
    // de status uit twee aan/uit-sensoren en de modus 3-toestand. Elke minuut
    // opnieuw, want de paal vergeet zijn limiet na zijn geldigheidsduur en
    // valt dan terug op zijn veilige stroom. Sinds 23-09-2026, naar de
    // entiteiten van de eerste woning; nog nooit aan een echte Alfen gestuurd.
    note: nt("Alfen gaat via de integratie alfen_modbus; zet in de paal de geldigheidsduur van de Modbus-stroomlimiet op minstens drie minuten."),
    fields: [
      {
        key: "limit",
        label: nt("Maximale stroomlimiet"),
        hint: nt("De number-entiteit van de socket (0 tot 32 A). Hier schrijft de coach op, elke minuut opnieuw."),
        filter: "all",
        needed: true,
      },
      {
        key: "connected",
        label: nt("Auto aangesloten"),
        hint: nt("De sensor die aan zegt zodra er een auto aan de kabel hangt."),
        filter: "all",
        needed: true,
        values: { on: nt("Auto aangesloten"), off: nt("Geen auto aangesloten") },
      },
      {
        key: "charging",
        label: nt("Auto laadt"),
        hint: nt("De sensor die aan zegt zolang er stroom in de auto gaat."),
        filter: "all",
        needed: true,
        values: { on: nt("Aan het laden"), off: nt("Laadt niet") },
      },
      {
        key: "mode3",
        label: nt("Modus 3-status"),
        hint: nt("De toestand volgens IEC 61851 (A, B1, B2, C2). Daaraan ziet de coach of de paal de auto stroom aanbiedt terwijl die niets neemt."),
        filter: "all",
        values: {
          A: nt("Geen auto"),
          B1: nt("Auto aangesloten, geen aanbod"),
          B2: nt("Auto aangesloten, wacht op de auto"),
          C1: nt("Auto vraagt, geen aanbod"),
          C2: nt("Aan het laden"),
          D1: nt("Auto vraagt met ventilatie, geen aanbod"),
          D2: nt("Aan het laden, met ventilatie"),
          E: nt("Niet beschikbaar"),
          F: nt("Storing"),
        },
      },
      {
        key: "max_limit",
        label: nt("Werkelijke maximale stroom"),
        hint: nt("Wat de paal zelf maximaal mag leveren, in ampère. Dit is de bovengrens die vastligt."),
        filter: "all",
        needed: true,
      },
      {
        key: "dynamic_limit",
        label: nt("Maximale stroom (teruggelezen)"),
        hint: nt("Wat de paal nu als limiet heeft staan, in ampère. Daaraan ziet de coach of zijn opdracht is aangenomen."),
        filter: "all",
      },
      {
        key: "current",
        label: nt("Stroom L1"),
        hint: nt("De stroom op fase 1, in ampère. Samen met het vermogen ziet de coach daaraan op hoeveel fasen de auto laadt."),
        filter: "all",
      },
      {
        key: "phases",
        label: nt("Bruikbare fasen"),
        hint: nt("De keuzelijst met 1 Phase en 3 Phases. Alleen nodig als de coach van fasen mag wisselen."),
        filter: "all",
      },
    ],
  },
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
  { key: "eco_50", alias: "Eco50", label: nt("Eco 50 °C"), minutes: 225, kwh: 0.8, peakW: 2100, peakMinutes: 40 },
  { key: "auto_2", alias: "Auto2", label: nt("Auto 45 tot 65 °C"), minutes: 135, kwh: 1.15, peakW: 2100, peakMinutes: 35 },
  { key: "intensiv_70", alias: "Intensiv70", label: nt("Intensief 70 °C"), minutes: 145, kwh: 1.4, peakW: 2100, peakMinutes: 50 },
  { key: "kurz_60", alias: "Kurz60", label: nt("Express 60 °C"), minutes: 60, kwh: 1.05, peakW: 2200, peakMinutes: 30 },
  { key: "night_wash", alias: "NightWash", label: nt("Nacht Was"), minutes: 210, kwh: 1.0, peakW: 1600, peakMinutes: 55 },
  { key: "machine_care", alias: "MachineCare", label: nt("Machine Onderhoud"), minutes: 120, kwh: 1.3, peakW: 2100, peakMinutes: 45 },
  { key: "pre_rinse", alias: "PreRinse", label: nt("Voorspoelen"), minutes: 15, kwh: 0.05, peakW: 0, peakMinutes: null },
];

/**
 * The same value, however an integration chose to spell it.
 *
 * The appliance world has no agreement here at all. Home Assistant's own Home
 * Connect integration reports `ready` and `dishcare_dishwasher_program_eco_50`;
 * the alternative integration reports the raw API names
 * `BSH.Common.EnumType.OperationState.Ready` and
 * `Dishcare.Dishwasher.Program.Eco50`; a third might send `Ready` or
 * `READY`. All of them are the same machine saying the same thing.
 *
 * Stripping everything that is not a letter or a digit and lower-casing gets
 * the two long forms to agree with each other; taking the part after the last
 * dot gets the qualified names to agree with the short ones. Between them
 * every spelling seen so far lands on the same key, and a brand added later
 * only has to list the words themselves.
 */
const squash = (raw) => String(raw ?? "").replace(/[^a-z0-9]/gi, "").toLowerCase();
const tail = (raw) => squash(String(raw ?? "").split(".").pop());

/** Index a brand's value map by every spelling its keys could arrive in. */
function spellings(values) {
  const index = new Map();
  for (const [key, label] of Object.entries(values ?? {})) {
    index.set(squash(key), label);
    index.set(tail(key), label);
  }
  return index;
}

/**
 * Look one value up, trying the exact word first and the spellings after, in de
 * taal van nu (v0.139.0). Om op te zoeken of te bewaren: `labelVan`, dat Nederlands blijft.
 */
export function valueLabel(values, raw) {
  const label = labelVan(values, raw);
  return label === undefined ? undefined : t(label);
}

/** Hetzelfde als `valueLabel`, in het Nederlands van de tabel: de sleutel van `PROGRAM_BY_LABEL`. */
function labelVan(values, raw) {
  if (!values) return undefined;
  const exact = values[raw];
  if (exact !== undefined) return exact;

  // Built once per map and kept on the map itself: these are module constants,
  // and rebuilding the index for every reading of every sensor is work that
  // repeats a few times a second.
  let index = SPELLING_CACHE.get(values);
  if (!index) {
    index = spellings(values);
    SPELLING_CACHE.set(values, index);
  }
  return index.get(squash(raw)) ?? index.get(tail(raw));
}

const SPELLING_CACHE = new WeakMap();

/** What to show instead of a raw program value. */
export const DISHWASHER_PROGRAM_VALUES = Object.fromEntries(
  DISHWASHER_PROGRAMS.flatMap((program) => [
    [`dishcare_dishwasher_program_${program.key}`, program.label],
    [`Dishcare.Dishwasher.Program.${program.alias}`, program.label],
  ])
);

const PROGRAM_BY_LABEL = new Map(DISHWASHER_PROGRAMS.map((program) => [program.label, program]));

/** The program behind a sensor value, or undefined for one we do not know. */
export const programFor = (raw) =>
  PROGRAM_BY_LABEL.get(labelVan(DISHWASHER_PROGRAM_VALUES, raw));

/**
 * Een schakelaar die hetzelfde zegt als de knop "Ingeruimd en dicht", voor
 * wie de vaatwasser vanaf een eigen dashboard vrijgeeft. De eigenaar op 06-09-2026:
 * een kaart in de keuken met een knop "sturing" die een schakelaar aanzet,
 * "en dan wil ik dat Ingeruimd en dicht aangaat." De coach houdt de twee
 * gelijk, in beide richtingen, en zet ze na een beurt allebei uit.
 */
const RELEASE_SWITCH_FIELD = {
  key: "release_switch",
  label: nt("Vrijgaveschakelaar"),
  hint: nt("Optioneel: een schakelaar of input_boolean die hetzelfde betekent als \"Ingeruimd en dicht\". Zet je die aan, bijvoorbeeld vanaf een eigen dashboard, dan geeft de coach de vaatwasser vrij; zet je hem op de kaart vrij, dan gaat de schakelaar mee aan. Na de beurt gaan ze allebei uit. Niet de schakelaar van de stekker waar de machine op hangt: die haalt de stroom eraf, en die gebruikt de coach dus niet."),
  filter: "all",
  hideRow: true,
};

/**
 * Een tweede schakelaar, voor "ingeruimd en nu starten". De eigenaar op 13-09-2026:
 * na de klaar-tijd de keuze "ingeruimd en morgen starten" of "ingeruimd en nu
 * starten", en vanaf zijn keukenkaart allebei. De vrijgaveschakelaar is dan
 * morgen, deze is nu.
 */
const RELEASE_NOW_SWITCH_FIELD = {
  key: "release_now_switch",
  label: nt("Schakelaar nu starten"),
  hint: nt("Optioneel: een schakelaar of input_boolean die \"ingeruimd en nu starten\" betekent. Zet je die aan, dan start de coach hem meteen, ook als het niet het goedkoopste moment is. Na de beurt gaat hij uit. Niet de schakelaar van de stekker waar de machine op hangt."),
  filter: "all",
  hideRow: true,
};

/**
 * De vrijgaveschakelaars die op dezelfde stekker zitten als de vermogenssensor,
 * en dus de stroom van de machine zelf zijn. In de eerste woning stond tot
 * 29-09-2026 de schakelaar van de meetstekker onder de vaatwasser als
 * vrijgaveschakelaar ingevuld; de coach zette hem na elke beurt uit, en de
 * vaatwasser zat daarna zonder stroom. De coach gebruikt zo'n schakelaar niet
 * meer (`_vrijgave_entiteit` in coach.py) en Apparaten zegt het.
 * `entities` is `hass.entities` van Home Assistant, met per entiteit zijn `device_id`.
 */
export const releaseOnOwnPlug = (device, entities) => {
  const deviceOf = (id) => (id ? entities?.[id]?.device_id : undefined);
  const meters = [device?.entity, device?.energy_entity].map(deviceOf).filter(Boolean);
  if (!meters.length) return [];
  return ["release_switch", "release_now_switch"].filter((key) => {
    const own = deviceOf(device?.entities?.[key]);
    return Boolean(own) && meters.includes(own);
  });
};

/**
 * Een knop die "ingeruimd en dicht" betekent (v0.102.0). De eigenaar op
 * 29-09-2026: "een fysieke zigbee knop waar men op kan drukken die een event
 * detecteert." Een druk is altijd vrijgeven, nooit wisselen: een knop heeft
 * geen lampje. Welke soort druk telt staat in `release_press`, gekozen uit de
 * soorten die de knop zelf opgeeft; leeg is elke druk.
 */
const RELEASE_BUTTON_FIELD = {
  key: "release_button",
  label: nt("Vrijgaveknop"),
  hint: nt("Optioneel: een knop die hetzelfde betekent als \"Ingeruimd en dicht\", bijvoorbeeld een Zigbee-knop naast de vaatwasser (een event-entiteit), een knop-helper (input_button) of een actiesensor. Eén druk geeft hem vrij; nog een keer drukken doet niets. Je krijgt een melding met wanneer hij start."),
  filter: "all",
  hideRow: true,
};

/** De velden waarmee de bewoner een vaatwasser vrijgeeft; weg als dat niet hoeft. */
export const RELEASE_KEYS = ["release_switch", "release_now_switch", "release_button"];

export const DISHWASHER_BRANDS = [
  {
    id: "home_connect",
    label: "Home Connect",
    note: nt("Bosch, Siemens, Neff, Gaggenau en Constructa lopen allemaal via Home Connect. Werkt met de integratie van Home Assistant zelf, met Home Connect Alt en met Home Connect Local (lokaal, zonder cloud)."),
    fields: [
      {
        key: "status",
        label: nt("Status"),
        hint: nt("Waar de vaatwasser mee bezig is: klaar voor gebruik, aan het draaien, afgelopen."),
        filter: "all",
        needed: true,
        // Home Connect's operation states, as Home Assistant reports them.
        values: {
          inactive: nt("Uit"),
          ready: nt("Klaar voor gebruik"),
          delayedstart: nt("Wacht op de starttijd"),
          run: nt("Aan het draaien"),
          pause: nt("Gepauzeerd"),
          actionrequired: nt("Vraagt om aandacht"),
          finished: nt("Afgelopen"),
          error: nt("Storing"),
          aborting: nt("Wordt afgebroken"),
        },
      },
      {
        key: "program",
        label: nt("Geselecteerd programma"),
        hint: nt("De sensor die zegt welk programma klaarstaat. Daar hangt aan vast hoe lang het duurt en wat het kost. Bij Home Connect Local is dit de sensor \"Actief programma\", die alleen tijdens de beurt iets zegt; zet hieronder dan ook de select \"Geselecteerd programma\", want daaruit leest de coach het de rest van de tijd."),
        filter: "all",
        needed: true,
        values: DISHWASHER_PROGRAM_VALUES,
      },
      {
        key: "program_select",
        label: nt("Programma kiezen"),
        hint: nt("De select-entiteit waarmee je een programma op de machine zet. Hiermee kies je op de kaart welk programma erop staat, en hieruit komen de namen in de tabel hieronder."),
        filter: "select",
        // De eigenaar op 06-09-2026: "ik heb selected program in plaats van select;
        // voeg een optie toe waar ik een sensor in kan zetten." Vandaar twee
        // velden: de sensor die het zegt, en de select die het zet.
        values: DISHWASHER_PROGRAM_VALUES,
        hideRow: true,
      },
      {
        key: "remaining",
        label: nt("Resterende tijd"),
        hint: nt("Hoe lang het programma nog duurt. Home Connect geeft hier de eindtijd, Home Connect Local de uren die nog resten; het paneel rekent zelf terug."),
        filter: "all",
        format: "countdown",
      },
      {
        key: "remote_start",
        label: nt("Starten op afstand"),
        // Optioneel. Staat hij uit, dan drukt de coach niet: een druk doet
        // dan niets, en hij zegt de bewoner wat er aan moet. Thuis op
        // 23-09-2026 bij Home Connect Local "Start op afstand"; de andere
        // twee integraties hebben hem ook.
        hint: nt("Optioneel: de sensor die zegt of de machine op afstand gestart mag worden. Staat hij uit, dan drukt de coach niet en zegt hij dat je hem op het apparaat aan moet zetten."),
        filter: "all",
        values: { on: nt("Aan"), off: nt("Uit") },
      },
      RELEASE_SWITCH_FIELD,
      RELEASE_NOW_SWITCH_FIELD,
      RELEASE_BUTTON_FIELD,
      {
        key: "door",
        label: nt("Deurstand"),
        // Deliberately not `needed`, and deliberately not part of the decision
        // to start: see `releaseCopy`.
        hint: nt("Moet hij eerst vrijgegeven worden, dan alleen om te laten zien. Hoeft dat niet, dan is klep dicht de vrijgave, en dan is dit veld nodig."),
        filter: "all",
        values: {
          closed: nt("Dicht"),
          locked: nt("Vergrendeld"),
          open: nt("Open"),
          // The same state arrives as a binary sensor at some installations.
          off: nt("Dicht"),
          on: nt("Open"),
        },
      },
    ],
    // Started by pressing something rather than by calling a service with a
    // word: Home Connect exposes the start as its own button entity, and which
    // one that is differs per integration and per appliance.
    buttons: [
      {
        key: "start",
        label: nt("Starten"),
        icon: "play",
        needed: true,
        hint: nt("De knop die het geselecteerde programma start. Bij Home Connect heet die meestal \"Start\" of \"Start/Pauze\". De vaatwasser moet wel op afstand gestart mogen worden. Bij Home Connect Local is de knop er alleen als de machine een start aanneemt (deur dicht); tot die tijd wacht de coach."),
        filter: "all",
      },
      {
        key: "stop",
        label: nt("Stoppen"),
        icon: "stop",
        // Not `care`: stopping is the plain opposite of starting and belongs
        // next to it. That flag is for the thing that stands apart -- a reboot
        // that drops a running session -- and using it here pushed Stoppen onto
        // its own row under Starten.
        hint: nt("De knop die een lopend programma afbreekt. Optioneel: zonder deze knop kan de coach een programma wel starten maar niet meer terugdraaien."),
        note: nt("Breekt het lopende programma af. De vaatwasser begint daarna weer van voren af aan."),
        filter: "all",
      },
    ],
    // The program is set through the same entity that reports it, as long as
    // that entity is one you can write to. Nothing extra to fill in for it.
    programField: "program",
  },
  // Een vaatwasser zonder koppeling, op een meetstekker. Geen startknop, dus
  // de coach zegt wanneer en de bewoner drukt; het vermogen zegt of hij
  // draait en wat hij verbruikt. De eigenaar op 06-09-2026: "smart plug als starten
  // doen we niet, wel adviseren en meten."
  {
    id: "overig",
    label: nt("Overig"),
    note: nt("Een vaatwasser zonder koppeling, op een meetstekker: de coach zegt wanneer je hem aan moet zetten en meet wat hij verbruikt."),
    fields: [RELEASE_SWITCH_FIELD, RELEASE_NOW_SWITCH_FIELD, RELEASE_BUTTON_FIELD],
    manual: true,
  },
];

/**
 * Wasmachines en drogers, per merk (v0.124.0).
 *
 * De eigenaar op 15-10-2026: "Starten, zoals vaatwasser", met Miele en Overig.
 * Miele via de integratie van Home Assistant zelf (`miele`, via de cloud): het
 * programma kies je op de machine, en die geeft de duur zolang het klaarstaat.
 * Een vermogenssensor heeft hij niet; het verbruik telt de coach uit de
 * energieteller per programma (`energy_entity`, `_teller_watts` in coach.py).
 * Dezelfde lijst als `WASMACHINE_BRANDS` in const.py.
 */
const WASHER_BRANDS = (wat) => [
  {
    id: "miele",
    label: "Miele",
    ...metWoorden("note", nt("Voor Miele is dat de integratie Miele van Home Assistant zelf. De coach start de {wat} alleen als \"start op afstand\" aan staat op de machine."), { wat }),
    fields: [
      {
        key: "status",
        label: nt("Status"),
        ...metWoorden("hint", nt("De sensor die zegt waar de {wat} mee bezig is, bij Miele de sensor met de naam van de machine zelf."), { wat }),
        filter: "all",
        needed: true,
      },
      {
        key: "program",
        label: nt("Programma"),
        hint: nt("De sensor Programma. Het programma kies je op de machine; de coach leest het en plant op de duur die de machine geeft. Na een beurt rekent hij met wat hij gemeten heeft."),
        filter: "all",
        needed: true,
      },
      {
        key: "remaining",
        label: nt("Resterende tijd"),
        hint: nt("Hoe lang het programma nog duurt. Zolang het klaarstaat is dat de duur waarmee de coach plant."),
        filter: "all",
        format: "countdown",
        needed: true,
      },
      {
        key: "remote_start",
        label: nt("Start op afstand"),
        hint: nt("Optioneel: de sensor Start op afstand. Staat hij uit, dan drukt de coach niet en zegt hij dat je het op de machine aan moet zetten."),
        filter: "all",
        values: { on: nt("Aan"), off: nt("Uit") },
      },
      RELEASE_SWITCH_FIELD,
      RELEASE_NOW_SWITCH_FIELD,
      RELEASE_BUTTON_FIELD,
      {
        key: "door",
        label: nt("Deur"),
        hint: nt("Moet hij eerst vrijgegeven worden, dan alleen om te laten zien. Hoeft dat niet, dan is deur dicht de vrijgave, en dan is dit veld nodig."),
        filter: "all",
        values: { off: nt("Dicht"), on: nt("Open") },
      },
    ],
    buttons: [
      {
        key: "start",
        label: nt("Starten"),
        icon: "play",
        needed: true,
        hint: nt("De knop Starten van de machine. Die staat in Home Assistant standaard uit: zet hem eerst aan bij de entiteit. Hij is er alleen als de machine een start aanneemt; tot die tijd wacht de coach."),
        filter: "all",
      },
      {
        key: "stop",
        label: nt("Stoppen"),
        icon: "stop",
        hint: nt("Optioneel: de knop Stoppen, die een lopend programma afbreekt. Ook die staat standaard uit."),
        note: nt("Breekt het lopende programma af."),
        filter: "all",
      },
    ],
    programField: "program",
    // De machine noemt het programma en geeft de duur; er is geen tabel vooraf.
    programOnMachine: true,
    // Geen vermogenssensor: het verbruik komt uit de energieteller.
    energyCounter: true,
  },
  {
    id: "overig",
    label: nt("Overig"),
    ...metWoorden("note", nt("Een {wat} zonder koppeling, op een meetstekker: de coach zegt wanneer je hem aan moet zetten en meet wat hij verbruikt."), { wat }),
    fields: [RELEASE_SWITCH_FIELD, RELEASE_NOW_SWITCH_FIELD, RELEASE_BUTTON_FIELD],
    manual: true,
  },
];

// Het woord blijft Nederlands tot het getoond wordt (`inTaal`).
export const WASMACHINE_BRANDS = WASHER_BRANDS(nt("wasmachine"));
export const DROGER_BRANDS = WASHER_BRANDS(nt("droger"));

/**
 * Een vriezer, per merk (v0.125.0). De eigenaar op 15-10-2026: "Uitlezen en
 * melden": de temperatuur en de deur bijhouden, en een melding als de deur te
 * lang openstaat, de temperatuur oploopt of de vriezer een storing meldt. De
 * coach stuurt hem niet (`readOnly`); de meldingen staan in
 * `_async_vriezerwacht` in coach.py. Dezelfde lijst als `VRIEZER_BRANDS` in const.py.
 */
/**
 * Wat de coach met een vriezer of een koelkast doet (v0.131.0: de koelkast erbij),
 * met de grens van `KOELWAREN` in coach.py. De eigenaar op 19-10-2026 over de
 * koelkast: "boven de 10 graden".
 */
export const KOELWAREN = {
  vriezer: { naam: nt("de vriezer"), grens: -15 },
  koelkast: { naam: nt("de koelkast"), grens: 10 },
};

/** De zin onder een vriezer of koelkast in Apparaten: wat de coach doet in plaats van sturen. */
export function koelUitleg(type) {
  const k = KOELWAREN[type];
  if (!k) return "";
  return t("De coach stuurt {naam} niet. Hij houdt hem in de gaten en stuurt een melding als de deur 3 minuten openstaat, als hij een half uur warmer is dan {grens} °C, of als {naam} een storing meldt.",
    { naam: t(k.naam), grens: k.grens });
}

/** De woorden in de hints van een vriezer of koelkast (`metWoorden`). */
const koelWoorden = (soort) => ({
  naam: KOELWAREN[soort].naam,
  grens: KOELWAREN[soort].grens,
  deze: soort === "vriezer" ? nt("deze vriezer") : nt("deze koelkast"),
});

const VRIEZER_FIELDS = (miele, soort = "vriezer") => [
  {
    key: "temperature",
    label: nt("Temperatuur"),
    ...metWoorden("hint", miele
      ? nt("De sensor Temperatuur van {naam}. Is hij een half uur warmer dan {grens} °C, dan krijg je een melding. Niet de zones 2 en 3: die bestaan bij {deze} niet echt.")
      : nt("Een temperatuursensor in {naam}. Is hij een half uur warmer dan {grens} °C, dan krijg je een melding."), koelWoorden(soort)),
    filter: "temperature",
    decimals: 1,
  },
  {
    key: "door",
    label: nt("Deur"),
    hint: nt("Optioneel: de deursensor. Staat de deur 3 minuten open, dan krijg je een melding."),
    filter: "all",
    values: { on: nt("Open"), off: nt("Dicht"), open: nt("Open"), closed: nt("Dicht") },
  },
  {
    key: "problem",
    label: nt("Storing"),
    ...metWoorden("hint", miele
      ? nt("Optioneel: de sensor Probleem van {naam}. Meldt hij een storing, dan krijg je een melding.")
      : nt("Optioneel: een sensor die aan gaat bij een storing. Dan krijg je een melding."), koelWoorden(soort)),
    filter: "all",
    values: { on: nt("Storing"), off: nt("Geen") },
  },
];

export const VRIEZER_BRANDS = [
  {
    id: "miele",
    label: "Miele",
    note: nt("Voor Miele is dat de integratie Miele van Home Assistant zelf."),
    fields: VRIEZER_FIELDS(true),
    readOnly: true,
  },
  {
    id: "overig",
    label: nt("Overig"),
    note: nt("Onder Overig past elke vriezer met een temperatuursensor erin."),
    fields: VRIEZER_FIELDS(false),
    readOnly: true,
  },
];

/** De koelkast (v0.131.0): dezelfde merken als de vriezer, `KOELKAST_BRANDS` in const.py. */
export const KOELKAST_BRANDS = [
  {
    id: "miele",
    label: "Miele",
    note: nt("Voor Miele is dat de integratie Miele van Home Assistant zelf."),
    fields: VRIEZER_FIELDS(true, "koelkast"),
    readOnly: true,
  },
  {
    id: "overig",
    label: nt("Overig"),
    note: nt("Onder Overig past elke koelkast met een temperatuursensor erin."),
    fields: VRIEZER_FIELDS(false, "koelkast"),
    readOnly: true,
  },
];


/**
 * Thuisbatterijen, per merk.
 *
 * De eigenaar op 21-09-2026: "Ik wil de coach gaan uitbreiden met een
 * thuisbatterij. Ik wil hem kunnen aansturen in HA. Laden, ontladen, blokkeren
 * als de laadpaal laadt." En later: "het doel is om hem volledig third party
 * te sturen."
 *
 * Wat de coach nodig heeft is overal hetzelfde: een getal waarmee hij het
 * vermogen zet, een accustand, en wat de batterij nu doet. De rest maakt het
 * beter maar is niet nodig. Een merk legt alleen vast welke woorden er in de
 * modus horen; de velden zijn voor elk merk gelijk, zodat een batterij met
 * dezelfde knoppen onder "Overig" past zonder dat er code bij moet.
 */
const BATTERY_FIELDS = (richtingNodig) => [
  {
    key: "soc",
    label: nt("Accustand"),
    hint: nt("Hoe vol de batterij is, in procent."),
    filter: "all",
    needed: true,
  },
  // Onder de accustand op de kaart, en voor de melding "Thuisbatterij te warm"
  // (v0.108.0). De eigenaar op 10-10-2026: "ik heb nu ook een
  // batterijtemperatuur van de anker, ik wil dat ik die kan invullen en dat je
  // die toont op de batterijkaart." De coach stuurt er niet op.
  {
    key: "temperature",
    label: nt("Temperatuur"),
    hint: nt("Optioneel: de temperatuur van de batterij. Die staat dan op de kaart, en onder Meldingen kun je een bericht krijgen als hij te warm wordt. De coach stuurt er niet op."),
    filter: "temperature",
    decimals: 1,
  },
  // De eigenaar op 10-10-2026: "ik wil de mogelijkheid om een smart plug in te
  // schakelen om een ventilator aan te sturen als de batterij te heet wordt."
  // De grens staat onder Wat jij wilt (`fan_above_c`); zie `_async_ventilator`.
  {
    key: "fan",
    label: nt("Ventilator"),
    hint: nt("Optioneel: de smart plug of schakelaar van een ventilator bij de batterij. Met de temperatuur hierboven en een grens onder Wat jij wilt zet de coach hem aan als de batterij te warm wordt."),
    filter: "all",
    values: { on: nt("Aan"), off: nt("Uit") },
  },
  {
    key: "setpoint",
    label: nt("Vermogen zetten"),
    hint: nt("Het getal (number) waarmee het vermogen van de batterij gezet wordt, in watt. Hier stuurt de coach mee."),
    filter: "all",
    needed: true,
    hideRow: true,
  },
  {
    key: "direction",
    label: nt("Richting"),
    hint: richtingNodig
      ? nt("De keuzelijst (select) die zegt of dat vermogen laden of ontladen is.")
      : nt("Optioneel: een keuzelijst die zegt of het vermogen laden of ontladen is. Zonder deze is het teken van het getal de richting: plus is laden."),
    filter: "select",
    needed: richtingNodig,
    hideRow: true,
  },
  {
    key: "mode",
    label: nt("Bedrijfsmodus"),
    hint: nt("Optioneel: de keuzelijst met de modus van de batterij. De coach zet hem op de modus voor externe sturing zodra hij gaat sturen, en terug zodra hij stopt."),
    filter: "select",
    // De woorden van de officiele Anker-integratie. Een ander merk laat zijn
    // eigen woord zien zoals het binnenkomt.
    values: {
      self_consumption: nt("Eigen verbruik"),
      tou_mode: nt("Tijdschema"),
      third_party_control: nt("Externe sturing"),
      custom_mode: nt("Eigen modus"),
      smart_mode: nt("Slimme modus"),
      dynamic_pricing: nt("Dynamische prijzen"),
    },
  },
  {
    key: "charge_power",
    label: nt("Laadvermogen"),
    hint: nt("Alleen als er hierboven geen vermogenssensor met een teken is: wat de batterij nu laadt."),
    filter: "power",
    hideRow: true,
  },
  {
    key: "discharge_power",
    label: nt("Ontlaadvermogen"),
    hint: nt("En wat hij nu ontlaadt."),
    filter: "power",
    hideRow: true,
  },
  {
    key: "capacity",
    label: nt("Capaciteit (kWh)"),
    hint: nt("Optioneel: de sensor met de bruikbare inhoud. Zonder deze vul je hem hieronder in."),
    filter: "all",
    hideRow: true,
  },
  {
    key: "charge_limit",
    label: nt("Laadgrens (%)"),
    hint: nt("Optioneel: tot hoever de batterij zelf laadt. De coach leest dit, en zet het alleen voor de wekelijkse volle beurt even op 100%."),
    filter: "all",
    hideRow: true,
  },
  {
    key: "discharge_limit",
    label: nt("Ontlaadgrens (%)"),
    hint: nt("Optioneel: tot hoever de batterij zelf ontlaadt. Ook alleen gelezen."),
    filter: "all",
    hideRow: true,
  },
  {
    key: "energy_in",
    label: nt("kWh-meter: erin"),
    hint: nt("Optioneel: de teller van een kWh-meter op de batterij, wat erin ging. Met deze twee tellers meet de coach het echte rendement. De tellers van de batterij zelf zijn daar meestal niet goed voor: die meten aan de accukant."),
    filter: "all",
    hideRow: true,
  },
  {
    key: "energy_out",
    label: nt("kWh-meter: eruit"),
    hint: nt("En wat eruit kwam."),
    filter: "all",
    hideRow: true,
  },
  // Voor de kaart (v0.118.0): "ongeveer 88%, gemeten in de accu". De coach
  // rekent er in zijn sommen niet mee, want deze tellers zien het verlies in de
  // omvormer niet; zie `rte_accu` in coach.py. Historie telt er sinds v0.126.1
  // wel geladen en ontladen mee, zoals het energiedashboard (`fetchBattery`).
  {
    key: "accu_in",
    label: nt("Batterij zelf: geladen"),
    hint: nt("Optioneel, voor wie geen kWh-meter op de batterij heeft: de eigen teller van de batterij, wat erin ging. Daarmee telt Historie wat de batterij laadt en ontlaadt, en staat er op de kaart ongeveer hoeveel er weer uit komt. In zijn sommen rekent de coach er niet mee: deze tellers meten aan de accukant, zonder het verlies in de omvormer."),
    filter: "all",
    hideRow: true,
  },
  {
    key: "accu_out",
    label: nt("Batterij zelf: ontladen"),
    hint: nt("En wat eruit ging."),
    filter: "all",
    hideRow: true,
  },
];

/**
 * Growatt (v0.123.0): alleen uitlezen. De eigenaar op 15-10-2026: "nee sturen niet
 * voor growatt alleen uitlezen", en "dat ik dus alleen invulvelden krijg die
 * noodzakelijk zijn voor growatt". De Growatt-integratie van Home Assistant haalt
 * alles eens per vijf minuten uit de cloud en heeft voor een MIX alleen sensoren.
 * Dus de accustand, wat hij laadt en ontlaadt, en zijn eigen tellers, voor het
 * rendement in de pop-up. De capaciteit is een getal onder De batterij, want een
 * sensor daarvoor heeft de integratie niet.
 */
const GROWATT_FIELDS = [
  {
    key: "soc",
    label: nt("Accustand"),
    hint: nt("Hoe vol de batterij is, in procent. Kies je die van een Growatt, dan vult het paneel de vier hieronder vanzelf in, als hetzelfde apparaat ze heeft."),
    filter: "all",
  },
  {
    key: "charge_power",
    label: nt("Laadvermogen"),
    hint: nt("Wat de batterij nu laadt. In kW of in W, dat rekent de coach zelf om."),
    filter: "power",
    hideRow: true,
  },
  {
    key: "discharge_power",
    label: nt("Ontlaadvermogen"),
    hint: nt("En wat hij nu ontlaadt."),
    filter: "power",
    hideRow: true,
  },
  {
    key: "accu_in",
    label: nt("Batterij zelf: geladen"),
    hint: nt("De teller van alles wat er ooit in ging (levenslang), niet die van vandaag. Daarmee staat het rendement in de pop-up van de batterij, en telt Historie wat hij laadt en ontlaadt."),
    filter: "all",
    hideRow: true,
  },
  {
    key: "accu_out",
    label: nt("Batterij zelf: ontladen"),
    hint: nt("En van alles wat er ooit uit ging."),
    filter: "all",
    hideRow: true,
  },
];

export const BATTERY_BRANDS = [
  {
    id: "anker",
    label: "Anker SOLIX",
    note: nt("Voor Anker is dat de officiele Anker SOLIX-integratie, die lokaal met de batterij praat."),
    fields: BATTERY_FIELDS(true),
    // Wat er in de bedrijfsmodus hoort te staan terwijl de coach stuurt, en
    // wat er terugkomt als hij stopt. De woorden van de integratie zelf.
    battery: { control_mode: "third_party_control", idle_mode: "self_consumption" },
  },
  {
    id: "growatt",
    label: "Growatt",
    note: nt("Een Growatt leest de coach alleen uit, via de Growatt-integratie."),
    fields: GROWATT_FIELDS,
    // Alleen uitlezen: geen vinkje om te sturen en geen instellingen daarvoor.
    // Dezelfde lijst als `BATTERIJ_ALLEEN_LEZEN` in const.py.
    readOnly: true,
    // En geen vermogenssensor met een teken: laden en ontladen staan in de velden.
    noPower: true,
    battery: { control_mode: "", idle_mode: "" },
  },
  {
    id: "overig",
    label: nt("Overig"),
    note: nt("Onder Overig past elke batterij die in Home Assistant een getal heeft waarmee je het vermogen zet."),
    fields: BATTERY_FIELDS(false),
    battery: { control_mode: "", idle_mode: "" },
  },
];

/** De types die een thuisbatterij zijn, met hun eigen blok instellingen. */
export const isBattery = (device) => device?.type === "thuisbatterij";

/** Een merk dat de coach alleen uitleest (v0.123.0): Growatt. */
export const isReadOnly = (device) => Boolean(brandMeta(device)?.readOnly);

/**
 * Een batterij die naar een merk gaat dat alleen uitgelezen wordt (v0.123.0): niet
 * sturen, en geen sensor laten staan die daar geen veld heeft. De coach zou hem
 * anders nog lezen; een vermogenssensor met een teken gaat bij hem zelfs voor.
 */
export function alleenUitlezen(device) {
  if (!isReadOnly(device)) return device;
  const velden = brandFields(device).map((veld) => veld.key);
  return {
    ...device,
    controllable: false,
    entity: "",
    entities: Object.fromEntries(Object.entries(device.entities ?? {}).filter(([key]) => velden.includes(key))),
  };
}

/**
 * Wat het paneel bij een Growatt vanzelf invult zodra de accustand gekozen is
 * (v0.123.0): de sensoren van hetzelfde apparaat, op hun `translation_key`. Alleen
 * de vorm `mix_*`, die een MIX en een SPH allebei hebben; zo staan ze in de bron
 * van de integratie, en zo stonden ze op 15-10-2026 in een klantwoning. Een SPH
 * heeft geen ontlaadvermogen in kW, vandaar de tweede keus. Wat er al staat
 * blijft staan.
 *
 * `entities` is `hass.entities` van Home Assistant: per entiteit `device_id`,
 * `platform` en `translation_key`.
 */
const GROWATT_KEYS = {
  charge_power: ["mix_battery_charge"],
  discharge_power: ["mix_battery_discharge_kw", "mix_battery_discharge_w"],
  accu_in: ["mix_battery_charge_lifetime"],
  accu_out: ["mix_battery_discharge_lifetime"],
};

export function growattVanzelf(device, entities) {
  const soc = entities?.[device?.entities?.soc ?? ""];
  if (!soc?.device_id || soc.platform !== "growatt_server") return {};
  const zelfde = Object.values(entities).filter(
    (e) => e?.device_id === soc.device_id && e.platform === "growatt_server"
  );
  const uit = {};
  for (const [key, sleutels] of Object.entries(GROWATT_KEYS)) {
    if (device.entities?.[key]) continue;
    const treffer = sleutels.map((tk) => zelfde.find((e) => e.translation_key === tk)).find(Boolean);
    if (treffer) uit[key] = treffer.entity_id;
  }
  return uit;
}

/** De dagen van de week zoals de coach ze telt: nul is maandag. */
export const WEEKDAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"];

/**
 * De naam van dag `i` (nul is maandag) in de taal van nu (v0.139.0): "maandag" of "Monday".
 * Uit de datum zelf, niet uit een eigen lijst; 1 januari 2024 was een maandag.
 */
export const weekdag = (i) => datum(new Date(2024, 0, 1 + Number(i)), { weekday: "long" });

/** Wat een nieuwe batterij aan instellingen meekrijgt. */
export const defaultBattery = (brandId) => ({
  capacity_kwh: null,
  max_charge_w: null,
  max_discharge_w: null,
  rte_percent: null,
  power_invert: false,
  setpoint_invert: false,
  phase: "",
  reserve_enabled: false,
  reserve_percent: 20,
  trade: false,
  // Handelen in twee (v0.141.0): laden van het net mag, en per richting een grens
  // in de all-in prijs; leeg is "de coach bepaalt".
  grid_charge: true,
  grid_charge_below: null,
  trade_above: null,
  weekly_full: false,
  weekly_full_day: 6,
  holiday: false,
  holiday_max_percent: 50,
  // De batterij doet zelf nul op de meter; de coach grijpt alleen in om in te
  // kopen, voor de laadpaal en voor de veiligheid (standaard sinds v0.101.10).
  self_zero: true,
  // Boven welke temperatuur de ventilator aan gaat (v0.108.0); leeg is nooit.
  fan_above_c: null,
  ...(BATTERY_BRANDS.find((brand) => brand.id === brandId)?.battery ?? { control_mode: "", idle_mode: "" }),
});

/**
 * De airco (v0.119.0). De coach zet hem aan of uit, op de temperatuur die de
 * bewoner koos, in verwarmen of koelen; hoe hard hij draait is aan de airco
 * zelf. De eigenaar op 14-10-2026; zie docs/airco.md.
 */
const AIRCO_FIELDS = [
  {
    key: "climate",
    label: nt("Airco"),
    hint: nt("De airco zelf, zoals Home Assistant hem kent (een climate). Hiermee zet de coach hem aan of uit, in verwarmen of koelen, op de temperatuur die de bewoner kiest."),
    filter: "climate",
    needed: true,
  },
  {
    key: "temperature",
    label: nt("Kamertemperatuur"),
    hint: nt("Optioneel: een eigen sensor in de kamer. Leeg is de temperatuur die de airco zelf meet."),
    filter: "temperature",
  },
];

/**
 * De merken van een airco (v0.119.1). De eigenaar op 14-10-2026: "Bij apparaten
 * toevoegen alleen nog de optie Mitsubishi Electric kunnen kiezen." Zonder merk
 * staan de velden er niet en mag hij niet sturen, net als een thuisbatterij.
 */
export const AIRCO_BRANDS = [
  {
    id: "mitsubishi_electric",
    label: "Mitsubishi Electric",
    note: nt("Voor Mitsubishi Electric is dat de airco zoals de MELCloud-integratie hem in Home Assistant zet. Die praat via de cloud: een opdracht van de coach staat er na ongeveer een minuut."),
    fields: AIRCO_FIELDS,
  },
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
  ["wasmachine", WASMACHINE_BRANDS],
  ["droger", DROGER_BRANDS],
  ["vriezer", VRIEZER_BRANDS],
  ["koelkast", KOELKAST_BRANDS],
  ["thuisbatterij", BATTERY_BRANDS],
  ["airco", AIRCO_BRANDS],
]);

/**
 * De schakelaar waarmee een boiler stroom krijgt.
 *
 * De eigenaar op 19-09-2026: "een boiler waar je alleen stroom op moet zetten, met
 * een smart plug bijvoorbeeld. Alleen de switch invullen en power invullen."
 * Geen merk, geen programma, geen temperatuur: de coach zet de stroom erop of
 * eraf en de thermostaat van de boiler bepaalt hoe warm het water wordt. Wat
 * hij trekt terwijl er stroom op staat zegt of het vat nog warmte vraagt, en
 * daar leert de coach de rest uit.
 */
const BOILER_SWITCH_FIELD = {
  key: "switch",
  label: nt("Schakelaar"),
  hint: nt("De smart plug, schakelaar of het relais waarmee de boiler stroom krijgt. Hier zet de coach hem mee aan en uit; hoe warm het water wordt blijft aan de thermostaat van de boiler zelf."),
  filter: "all",
  needed: true,
  values: { on: nt("Stroom staat erop"), off: nt("Geen stroom") },
};

/**
 * De entiteiten die bij een type horen zonder dat er een merk aan te pas komt.
 * Een boiler is overal dezelfde boiler; een laadpaal is dat niet.
 */
const FIELDS_BY_TYPE = new Map([["boiler", [BOILER_SWITCH_FIELD]]]);

/** De velden van dit type, los van welk merk er gekozen is. */
export const typeFields = (device) => FIELDS_BY_TYPE.get(device?.type) ?? [];

/** De types waarvoor de vermogenssensor geen luxe is maar het enige zintuig. */
const POWER_NEEDED_TYPES = ["boiler"];

/**
 * Wat er aan een smart plug hangt (v0.120.0).
 *
 * De eigenaar op 15-10-2026: "Heel veel mensen hebben smart plugs om het
 * vermogen te meten van een apparaat. Ik wil bij apparaten toevoegen dan de
 * optie smart plug. En dan als ik die heb gekozen een hele lijst met apparaten
 * zoals wasmachine, oven vriezer etc etc. Allemaal met de naam en icon."
 *
 * Een belofte is het niet: de coach plant en stuurt ze niet. Hij meet ze, noemt
 * ze in een tip als dat mag (`controllable`), en houdt de stekker aan als dat
 * gevraagd is (`always_on`, `_async_altijd_aan` in coach.py). Op naam, met
 * "Iets anders" onderaan voor wat er niet tussen staat. Dezelfde lijst staat in
 * const.py (`STEKKER_APPARATEN`) voor de meldingen; test_rapport.mjs legt ze
 * naast elkaar.
 */
export const PLUG_APPLIANCES = [
  { id: "airfryer", label: nt("Airfryer"), icon: "airfryer" },
  { id: "aquarium", label: nt("Aquarium"), icon: "aquarium" },
  { id: "computer", label: nt("Computer"), icon: "computer" },
  { id: "droger", label: nt("Droger"), icon: "droger" },
  { id: "kachel", label: nt("Elektrische kachel"), icon: "kachel" },
  { id: "fietslader", label: nt("Fietslader"), icon: "fietslader" },
  { id: "koelkast", label: nt("Koelkast"), icon: "koelkast" },
  { id: "koffiezetapparaat", label: nt("Koffiezetapparaat"), icon: "koffiezetapparaat" },
  { id: "lamp", label: nt("Lamp"), icon: "lamp" },
  { id: "maairobot", label: nt("Maairobot"), icon: "maairobot" },
  { id: "magnetron", label: nt("Magnetron"), icon: "magnetron" },
  { id: "ontvochtiger", label: nt("Ontvochtiger"), icon: "ontvochtiger" },
  { id: "oven", label: nt("Oven"), icon: "oven" },
  { id: "router", label: nt("Router"), icon: "router" },
  { id: "server", label: nt("Server"), icon: "server" },
  { id: "spelcomputer", label: nt("Spelcomputer"), icon: "spelcomputer" },
  { id: "televisie", label: nt("Televisie"), icon: "televisie" },
  { id: "vaatwasser", label: nt("Vaatwasser"), icon: "vaatwasser" },
  { id: "ventilator", label: nt("Ventilator"), icon: "ventilator" },
  { id: "vijverpomp", label: nt("Vijverpomp"), icon: "vijverpomp" },
  { id: "vriezer", label: nt("Vriezer"), icon: "vriezer" },
  { id: "wasmachine", label: nt("Wasmachine"), icon: "wasmachine" },
  { id: "waterkoker", label: nt("Waterkoker"), icon: "waterkoker" },
  { id: "overig", label: nt("Iets anders"), icon: "plug" },
];

const PLUG_BY_ID = new Map(PLUG_APPLIANCES.map((apparaat) => [apparaat.id, apparaat]));

export const isSmartPlug = (device) => device?.type === "smartplug";

/**
 * Wat "altijd aan" kan hebben (v0.120.0): een smart plug, en sinds v0.122.0 een
 * vaatwasser. De eigenaar op 15-10-2026: "bij het apparaat vaatwasser ook de optie
 * kunnen aanzetten dat hij nooit uit mag, sommige vaatwassers hangen namelijk ook
 * aan een smart plug om alles te meten." Dezelfde lijst als `ALTIJD_AAN_TYPES` in
 * coach.py; de schakelaar staat bij allebei in `entities.switch`.
 */
export const ALWAYS_ON_TYPES = ["smartplug", "vaatwasser"];
export const canAlwaysOn = (device) => ALWAYS_ON_TYPES.includes(device?.type);

/** Wat er aan deze smart plug hangt, of undefined (geen smart plug, of nog niets gekozen). */
export const plugAppliance = (device) => (isSmartPlug(device) ? PLUG_BY_ID.get(device?.appliance) : undefined);

/**
 * De schakelaar van een smart plug (v0.120.0). Een eigen veld en geen veld van
 * het type zoals bij de boiler: een type met velden telt als stuurbaar
 * (`canSteer`), en dan viel de stekker uit de tip die hem mag noemen.
 */
export const PLUG_SWITCH_FIELD = {
  key: "switch",
  label: nt("Schakelaar"),
  hint: nt("De schakelaar van de smart plug zelf. Die heeft de coach alleen nodig om hem aan te houden; voor meten is het vermogen genoeg."),
  filter: "all",
  values: { on: nt("Aan"), off: nt("Uit") },
};

/** Hetzelfde veld bij een vaatwasser (v0.122.0), die er lang niet altijd een heeft. */
export const DISHWASHER_PLUG_FIELD = {
  ...PLUG_SWITCH_FIELD,
  label: nt("Smart plug (optioneel)"),
  hint: nt("Hangt de vaatwasser aan een smart plug, dan de schakelaar daarvan. Alleen nodig om hem altijd aan te houden; de coach zet hem nooit zelf uit."),
};

/**
 * Een rij uit een tabel hierboven (een veld, een knop, een merk, een soort) in de taal van
 * nu (v0.139.0): een kopie met `label`, `hint`, `note` en `blurb` vertaald. De tabel zelf
 * blijft Nederlands; `values` blijft dezelfde, want `valueLabel` vertaalt die.
 *
 * Een zin met woorden erin (`metWoorden`) gaat langs zijn sleutel in `sleutels`, met de
 * woorden uit `vars`, die zelf ook vertaald worden ("de {wat}" met "wasmachine"). En een
 * woord dat in het Nederlands twee dingen betekent ("Stroom": in ampère, en elders
 * elektriciteit) heeft daar een eigen sleutel voor het Engels; zonder vertaling, en dus in
 * het Nederlands, blijft het woord van de tabel.
 */
export function inTaal(rij) {
  if (!rij) return rij;
  const vars = rij.vars
    ? Object.fromEntries(Object.entries(rij.vars).map(([naam, woord]) => [naam, typeof woord === "string" ? t(woord) : woord]))
    : undefined;
  const uit = { ...rij };
  for (const veld of ["label", "hint", "note", "blurb"]) {
    if (typeof rij[veld] !== "string") continue;
    const sleutel = rij.sleutels?.[veld];
    const via = typeof sleutel === "string" ? t(sleutel, vars) : sleutel;
    uit[veld] = via !== undefined && via !== sleutel ? via : t(rij[veld], vars);
  }
  return uit;
}

/** The brands offered for a device type, or an empty list. */
export const brandsFor = (type) => BRANDS_BY_TYPE.get(type) ?? [];

/** The brand of a device, or undefined when it has none (or none yet). */
export const brandMeta = (device) =>
  brandsFor(device?.type).find((brand) => brand.id === device?.brand);

/** The extra entity fields this device asks for, beyond its power sensor; in de taal van nu. */
export const brandFields = (device) => {
  const fields = brandMeta(device)?.fields ?? typeFields(device);
  return (device?.release_required === false && canSkipRelease(device)
    ? fields.filter((field) => !RELEASE_KEYS.includes(field.key))
    : fields).map(inTaal);
};

/** The entities this brand is steered through, if it works that way. */
export const brandButtons = (device) => (brandMeta(device)?.buttons ?? []).map(inTaal);

/** Everything that gets an entity picker on the settings screen. */
export const brandEntityFields = (device) => [...brandFields(device), ...brandButtons(device)];

/** The start/stop/pause/resume/reboot commands this brand takes, if any. */
export const brandActions = (device) => (brandMeta(device)?.actions ?? []).map(inTaal);

/** The integration device this brand is steered through, if it works that way. */
export const brandDevice = (device) => inTaal(brandMeta(device)?.device);

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
export function deviceCommands(device, readNumber) {
  const brand = brandMeta(device);
  if (!brand) return [];

  const commands = [];

  if (brand.service && device?.device_id) {
    const [domain, service] = brand.service.split(".");
    for (const action of brand.actions ?? []) {
      if (action.limit) {
        // Een getal in plaats van een woord. `readNumber` is er om "max" op te
        // zoeken bij de lader zelf; wie hem niet meegeeft krijgt de 32 die de
        // laderlimiet toch begrenst.
        if (!brand.limitService) continue;
        const [limitDomain, limitService] = brand.limitService.split(".");
        const current =
          action.limit.current === "max"
            ? readNumber?.(device?.entities?.max_limit) || 32
            : action.limit.current;
        commands.push({
          ...inTaal(action),
          call: {
            domain: limitDomain,
            service: limitService,
            data: { ...action.limit, device_id: device.device_id, current },
          },
        });
        continue;
      }

      // The word is the customer's own: brands and even firmware versions
      // disagree on what to call these, so what is typed in wins and the
      // brand's default is only the starting point.
      const word = (device.actions?.[action.key] ?? action.fallback).trim() || action.fallback;
      commands.push({
        ...inTaal(action),
        call: { domain, service, data: { device_id: device.device_id, [brand.field]: word } },
      });
    }
  }

  for (const button of brand.buttons ?? []) {
    const entityId = device?.entities?.[button.key];
    if (entityId) commands.push({ ...inTaal(button), call: pressCall(entityId) });
  }

  return commands;
}

/**
 * The entity that both reports and sets the program, when there is one.
 *
 * Only entities you can actually write to count: plenty of integrations expose
 * the selected program as a read-only sensor next to a `select` that changes
 * it, and offering a dropdown that silently does nothing is worse than not
 * offering one.
 */
export function programChooser(device) {
  const key = brandMeta(device)?.programField;
  if (!key) return undefined;
  // Eerst de select die ervoor bedoeld is, dan de programmasensor als die
  // toevallig zelf een select is.
  for (const entityId of [device?.entities?.program_select, device?.entities?.[key]]) {
    if (!entityId) continue;
    const domain = entityId.split(".")[0];
    if (domain === "select" || domain === "input_select") return { entityId, domain };
  }
  return undefined;
}

/** Whether there is anything to send to this device at all. */
export const canCommand = (device) =>
  deviceCommands(device).length > 0 || Boolean(programChooser(device));

/**
 * The device types that charge a car, and so keep profiles.
 *
 * A profile is what the coach needs to plan with: how big the battery is, what
 * the car can take, and on how many phases it charges. Six amps is 1,4 kW on
 * one phase and 4,1 kW on three, so that last one decides whether charging on
 * surplus is fine-grained or coarse.
 */
export const CAR_TYPES = ["laadpaal"];

export const hasCars = (device) => CAR_TYPES.includes(device?.type);

/** How a car takes its power, and what that means for the lowest step. */
/** De merken van een auto, en daarmee welke velden er bij het profiel horen. */
/**
 * Wat er in "Hoe vol is de auto nu?" staat (v0.98.0): na een opgave de stand die
 * de coach nu verwacht, afgerond, en die loopt elke ronde mee met wat de paal erin
 * doet. De eigenaar op 25-09-2026: "ik wil dat je hoe vol is de auto nu live mee
 * laat lopen en dat de bewoner hem kan bijstellen waar nodig." Zonder opgave leeg;
 * weet de coach nog niets, dan de opgave zelf.
 */
export function socVeld(opgave, socNu) {
  const opgegeven = opgave?.percent;
  if (opgegeven === null || opgegeven === undefined || opgegeven === "") return "";
  const nu = socNu === null || socNu === undefined || socNu === "" ? NaN : Number(socNu);
  return String(Math.round(Number.isFinite(nu) ? nu : Number(opgegeven)));
}

/**
 * Of de kaart vraagt hoe vol deze auto is (v0.116.2): bij een auto zonder
 * sensor, en ook bij een auto waarvan de sensor nu niets zegt. Tot v0.116.2
 * alleen het eerste. De eigenaar op 14-10-2026, met de integratie van de auto
 * even uit Home Assistant: de coach vroeg "geef de accustand door op de
 * laadpaalkaart", "maar ik kan nergens de accustand doorgeven." De coach zelf
 * nam een opgave toen al aan zodra de sensor zweeg (`_typed_soc` in coach.py);
 * zegt de sensor weer iets, dan gaat die voor en verdwijnt het veld.
 * Dezelfde grens als `_number` in coach.py. Een gast en een auto zonder
 * accu in zijn profiel krijgen geen veld, want daar zegt een percentage niets.
 */
export function vraagAccustand(car, feed) {
  if (!car || car.guest || !(Number(car.capacity_kwh) > 0)) return false;
  if (!car.soc_entity) return true;
  const stand = feed?.get(car.soc_entity)?.state;
  return stand === undefined || stand === null || String(stand).trim() === "" || !Number.isFinite(Number(stand));
}

export const CAR_BRANDS = [
  { id: "ford", label: "Ford" },
  { id: "tesla", label: "Tesla" },
];

/**
 * Hoe de coach een slapende Tesla zijn accustand laat melden. De eigenaar op
 * 22-09-2026: "als een tesla niet aan de lader hangt slaapt hij en geeft hij
 * geen accu door."
 */
export const WAKE_MODES = [
  {
    id: "manual",
    label: nt("Handmatig opvragen"),
    blurb: nt("Het zuinigst: de auto slaapt door. Op de laadpaalkaart komt een knop om de accustand op te vragen."),
  },
  {
    id: "hourly",
    label: nt("Elk uur wakker maken"),
    blurb: nt("Staat hij stil en meldt hij niets, dan wekt de coach hem elk uur. Let op: elke keer wakker worden kost accu en houdt de auto uit zijn diepe slaap."),
  },
];

export const CAR_PHASES = [
  { id: "one", label: nt("Eén fase"), blurb: nt("Laagste stap ongeveer 1,4 kW.") },
  { id: "three", label: nt("Drie fasen"), blurb: nt("Laagste stap ongeveer 4,1 kW.") },
];

/**
 * The profile for a guest's car.
 *
 * Always there and nothing to fill in. A guest charges straight away and until
 * the cable comes out: they came to visit, not to wait for the cheapest hour.
 * It is a profile rather than a switch of its own so there is one mechanism
 * deciding what the charger does, instead of two that can disagree.
 */
export const GUEST_CAR = { id: "__guest__", name: nt("Gast"), guest: true };

/** Every profile that can be chosen at this device, guests included; de gast in de taal van nu. */
export const carsFor = (device) =>
  hasCars(device) ? [...(device.cars ?? []), { ...GUEST_CAR, name: t(GUEST_CAR.name) }] : [];

/**
 * The device types that need somebody to say they may run.
 *
 * A dishwasher is the case that makes this necessary: it can be switched on at
 * any moment the sun is out, and doing that to an empty one with its door open
 * is worse than not steering at all. Only whoever is standing in the kitchen
 * knows, so only they can say so.
 *
 * A charger deliberately is not on this list. Plugging the cable in is the
 * permission: nobody connects a car they do not want charged, and a charger
 * with no cable in it cannot start whatever anybody says. Asking for a second
 * yes on the dashboard was a step that only ever cost a walk to the phone.
 */
export const RELEASE_TYPES = ["vaatwasser", "wasmachine", "droger"];

/**
 * Whether this device waits for the customer before the coach may start it.
 *
 * Sinds v0.102.0 een keuze bij Apparaten, "Moet eerst vrijgegeven worden". De
 * eigenaar op 29-09-2026: "staat dat vinkje uit dan mag de vaatwasser gewoon
 * draaien met de coach als de klep dicht zit, en dan heb je ook geen knop
 * vrijgeven op de vaatwasser kaart." Alleen waar de coach de klep ziet en zelf
 * kan starten; een domme vaatwasser vraagt altijd.
 */
export const needsRelease = (device) =>
  RELEASE_TYPES.includes(device?.type) && !(device?.release_required === false && canSkipRelease(device));

/** Of dit apparaat zonder vrijgave kan: een merk met een deurstand en een startknop. */
export const canSkipRelease = (device) => {
  const meta = brandMeta(device);
  return RELEASE_TYPES.includes(device?.type) && !meta?.manual
    && (meta?.fields ?? []).some((field) => field.key === "door")
    && (meta?.buttons ?? []).some((button) => button.key === "start");
};

/** What the customer presses to say a device may run right now. */
export function releaseCopy(device) {
  switch (device?.type) {
    case "vaatwasser":
      return {
        label: t("Ingeruimd en dicht"),
        short: t("Ingeruimd"),
        hint: t("Zet dit aan als de vaatwasser vol staat en de klep dicht zit. Anders zou de coach hem leeg kunnen laten spoelen."),
      };
    // Dezelfde knop als de rest, met wat er bij een wasmachine of droger bij
    // hoort (v0.124.0). De kaart van DomotiApp Lovelace zegt ook "Mag draaien".
    case "wasmachine":
    case "droger":
      return {
        label: t("Mag meedraaien"),
        short: t("Mag draaien"),
        hint: t("Zet dit aan als de machine gevuld is, het programma klaarstaat en starten op afstand aan staat."),
      };
    default:
      return {
        label: t("Mag meedraaien"),
        short: t("Mag draaien"),
        hint: t("Zet dit aan als de coach dit apparaat nu mag inschakelen."),
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
  // Zonder vrijgave is klep dicht de vrijgave: zonder deurstand zou hij nooit starten.
  if (device.release_required === false && canSkipRelease(device) && !device.entities?.door) {
    missing.push(t("Deurstand"));
  }

  // Zonder startknop is het vermogen het enige wat de coach van het apparaat
  // ziet: daaraan meet hij of hij draait, hoe lang, en wat het kost.
  if (isManualProgram(device) && !device.entity) missing.unshift(t("Vermogenssensor"));
  // En bij een boiler net zo: daaraan ziet hij dat het vat vol is, want dan
  // vraagt de boiler niets meer. Zonder die sensor zou hij blind schakelen.
  if (POWER_NEEDED_TYPES.includes(device?.type) && !device.entity) missing.unshift(t("Vermogenssensor"));
  // Een airco: zonder vermogen weet de coach niet wanneer er genoeg zon voor is.
  // Een sensor, of anders het typeplaatje (v0.119.0).
  if (device?.type === "airco" && !device.entity && !(Number(device.airco?.power_w) > 0)) {
    missing.push(t("Vermogenssensor of typeplaatje"));
  }

  return missing;
}

/** Een programma-apparaat zonder startknop: de coach adviseert en meet. */
export const isManualProgram = (device) =>
  PROGRAM_TYPES.includes(device?.type) && Boolean(brandMeta(device)?.manual);

/**
 * Of de coach dit apparaat zelf kan bedienen: er zit een merk met knoppen of
 * een dienst achter. Alles zonder (een meetstekker, het merk "overig") kan
 * hij alleen plannen of noemen. De eigenaar op 07-09-2026: "er is een verschil
 * tussen de coach mag aansturen en adviseren, want een domme vaatwasser kan
 * de coach helemaal niet aansturen maar wel adviseren."
 */
export const canSteer = (device) =>
  (Boolean(brandMeta(device)) && !isManualProgram(device) && !isReadOnly(device)) ||
  typeFields(device).length > 0;

/**
 * The device types that run a program of a known length.
 *
 * The length is what lets the panel work back from "done by" to "start by", so
 * this list is about the sum, not about permission to plan.
 */
export const PROGRAM_TYPES = ["vaatwasser", "wasmachine", "droger"];

/**
 * De programmatabel van één apparaat.
 *
 * De opgave van de fabrikant is het uitgangspunt; wat de klant zelf invulde
 * staat in `device.programs` en wint zodra het er is. Dezelfde veldnamen als
 * de instellingen (`peak_w`), zodat een rij ongewijzigd opgeslagen kan worden.
 * De eigenaar op 06-09-2026: "ik wil dat kunnen aanpassen, wel moet hij dit als
 * uitgangspunt hebben."
 */
export const defaultPrograms = (device) =>
  // Een wasmachine en een droger hebben geen opgave vooraf (v0.124.0).
  (device && device.type !== "vaatwasser" ? [] : DISHWASHER_PROGRAMS).map((program) => ({
    key: program.key,
    label: program.label,
    minutes: program.minutes,
    kwh: program.kwh,
    peak_w: program.peakW,
  }));

/**
 * De keuzes van een programma-select, zonder de favorieten.
 *
 * Home Connect Local zet naast de programma's ook de opgeslagen favorieten
 * van de machine in de lijst (`favorite_001`). Dat is geen programma maar
 * een verwijzing naar een programma met opties, en de coach weet er geen
 * duur of verbruik van. De eigenaar op 23-09-2026: "favorite 001 is geen
 * programma, haal die eruit." Overal waar de opties van de select gelezen
 * worden gaat het langs hier: de tabel bij Apparaten en de keuze op de kaart.
 */
export const programChoices = (state) =>
  (state?.attributes?.options ?? []).filter((value) => !/(^|[._])favorite[._]?\d*$/i.test(String(value)));

/**
 * De programma's zoals de machine ze zelf aanbiedt: de opties van de
 * select-entiteit, elk met de sleutel waaronder de coach hem kent en een
 * leesbare naam. Leeg zonder select of zolang de feed er nog niet is.
 */
export function programOptions(device, feed) {
  const chooser = programChooser(device);
  if (!chooser || !feed) return [];
  const options = programChoices(feed.get(chooser.entityId));
  return options.map((value) => {
    const known = programFor(value);
    // Een programma dat de tabel niet kent: het stuk na het vaste voorvoegsel,
    // netjes gemaakt. `dishcare_dishwasher_program_glas_40` wordt "Glas 40".
    const staart = String(value).replace(/^dishcare[._]dishwasher[._]program[._]/i, "").split(".").pop();
    const label = known?.label ?? labelVan(DISHWASHER_PROGRAM_VALUES, value)
      ?? staart.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
    return { value, key: known?.key ?? programKey(staart), label };
  });
}

/**
 * De rijen van de tabel in Apparaten.
 *
 * Bij een machine die haar programma's zelf noemt (Home Connect met een
 * select): één rij per optie, in die volgorde en met die naam, en de cijfers
 * uit wat de klant invulde of anders uit de opgave. Zonder opties: de eigen
 * tabel, of de opgave als uitgangspunt.
 */
export function programRows(device, options = []) {
  if (!options.length) return programsFor(device).map((row) => ({ ...row }));
  const eigen = new Map((device?.programs ?? []).map((row) => [row.key || programKey(row.label), row]));
  const opgave = new Map(defaultPrograms(device).map((row) => [row.key, row]));
  return options.map((option) => {
    const row = eigen.get(option.key) ?? opgave.get(option.key) ?? { minutes: 120, kwh: 1, peak_w: 2000 };
    return { key: option.key, label: option.label, minutes: row.minutes, kwh: row.kwh, peak_w: row.peak_w ?? 0 };
  });
}

export const hasOwnPrograms = (device) =>
  Array.isArray(device?.programs) && device.programs.length > 0;

export const programsFor = (device) =>
  hasOwnPrograms(device) ? device.programs : defaultPrograms(device);

/** Dezelfde sleutel als `sleutel_van` in planner.py: "Glas 40 °C" wordt "glas_40_c". */
export const programKey = (label) =>
  String(label ?? "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .join("_") || "programma";

/** Wat de coach bij dit apparaat gemeten heeft, per programma. */
export function measuredFor(settings, device) {
  const map = new Map();
  for (const row of settings?.program_measured ?? []) {
    if (row?.device === device?.id && row?.key) map.set(row.key, row);
  }
  return map;
}

/**
 * Het programma achter een waarde, in de tabel van dit apparaat, met de
 * meting eroverheen. Dezelfde afspraak als `programma_van` in planner.py:
 * eerst de sleutel (als staart van wat de sensor zegt), dan de naam.
 */
export function programOf(device, raw, settings) {
  if (!raw) return undefined;
  const table = programsFor(device);
  const heel = squash(raw);
  const staart = tail(raw);
  const keyOf = (program) => program.key || programKey(program.label);
  const found =
    table.find((program) => {
      const key = squash(keyOf(program));
      return key && (heel.endsWith(key) || staart === key);
    }) ??
    table.find((program) => heel === squash(program.label) || staart === squash(program.label));
  if (!found) {
    // Een Miele heeft geen tabel: dan wat de coach van dit programma mat, op de
    // sleutel zoals de machine hem noemt (v0.124.0).
    const meting = brandMeta(device)?.programOnMachine && settings
      ? measuredFor(settings, device).get(String(raw))
      : undefined;
    if (!meting || !(Number(meting.minutes) > 0)) return undefined;
    return {
      key: String(raw),
      label: meting.label || String(raw),
      minutes: Number(meting.minutes),
      kwh: Number(meting.kwh) || 0,
      measured: true,
    };
  }
  const meting = settings ? measuredFor(settings, device).get(keyOf(found)) : undefined;
  if (!meting) return { ...found, key: keyOf(found) };
  return {
    ...found,
    key: keyOf(found),
    minutes: Number(meting.minutes) > 0 ? Number(meting.minutes) : found.minutes,
    kwh: Number.isFinite(Number(meting.kwh)) ? Number(meting.kwh) : found.kwh,
    measured: true,
  };
}

/**
 * Hoe de bewoner op de kaart het programma kiest.
 *
 * Bij een machine met een schrijfbare select-entiteit: de opties van de
 * machine zelf, en de keuze gaat naar die entiteit. Zonder programmasensor:
 * de eigen tabel, en de keuze gaat naar de instellingen (`device.program`).
 * Een alleen-lezen programmasensor geeft niets te kiezen. De coach kiest
 * nooit zelf; de eigenaar op 06-09-2026: "dat doet de klant altijd zelf."
 */
export function programPicker(device) {
  if (!PROGRAM_TYPES.includes(device?.type)) return undefined;
  // Een Miele: het programma kies je op de machine; de kaart laat zien welk (v0.124.0).
  if (brandMeta(device)?.programOnMachine) return { kind: "machine", entityId: device?.entities?.program };
  const chooser = programChooser(device);
  if (chooser) return { kind: "entity", entityId: chooser.entityId };
  // Een merk dat het programma van de machine leest maar zonder select om het
  // te zetten: niets te kiezen, maar wel zeggen waar dat aan ligt.
  if (brandMeta(device)?.programField && !isManualProgram(device)) return { kind: "missing" };
  return { kind: "table", options: programsFor(device) };
}

/**
 * The device types that can be given a time window at all.
 *
 * A charger has no programme and no fixed length -- a car is done when it is
 * full, and how long that takes is a question about the car. It still belongs
 * here: "the car has to be charged by seven" is exactly the kind of boundary
 * that makes cheap night-time charging possible, and without a deadline later
 * is always cheaper and the coach would never begin.
 */
export const SCHEDULABLE_TYPES = [...PROGRAM_TYPES, "laadpaal", "boiler"];

/**
 * De types die alleen "klaar om" kennen, en niet de andere twee tijden.
 *
 * Bij een laadpaal omdat de coach zelf het goedkoopste moment kiest (de eigenaar,
 * 04-09-2026); bij een boiler om dezelfde reden, en omdat "uiterlijk starten"
 * bij een vat dat zichzelf uitzet niets betekent. De eigenaar op 19-09-2026 koos
 * "klaar om, zoals de auto".
 */
export const DEADLINE_ONLY_TYPES = ["laadpaal", "boiler"];

/** Whether "must be finished by" means anything for this device. */
export const canHaveDeadline = (device) =>
  Boolean(device?.controllable) && SCHEDULABLE_TYPES.includes(device?.type);

const BY_ID = new Map(DEVICE_TYPES.map((soort) => [soort.id, soort]));

/** Metadata for a device type, falling back to "Overig" for unknown ids; de naam in de taal van nu. */
export const typeMeta = (type) => inTaal(BY_ID.get(type) ?? BY_ID.get("overig"));

/**
 * Het woord voor wat een apparaat is: zijn type, en bij een smart plug wat
 * eraan hangt (v0.120.0). "Iets anders" is geen woord voor een apparaat; dan
 * blijft het "Smart plug".
 */
export function kindLabel(device) {
  const apparaat = plugAppliance(device);
  if (apparaat && apparaat.id !== "overig") return t(apparaat.label);
  return typeMeta(device?.type).label;
}

/** Het icoon van een apparaat: dat van zijn type, of van wat aan de smart plug hangt. */
export const deviceIcon = (device) => plugAppliance(device)?.icon ?? typeMeta(device?.type).icon;

/** What to call a configured device: its own name if it has one, else its type. */
export function deviceLabel(device) {
  const name = (device?.name || "").trim();
  if (name) return name;
  return kindLabel(device);
}

/**
 * Labels for a whole list, with duplicates told apart.
 *
 * Two dishwashers with no names of their own are both "Vaatwasser", and on a
 * list where each row is a thing you can set separately that is unusable. They
 * get a number, in the order they were added -- not a guess at which is which,
 * just enough to see that they are two. Giving them names is the better answer
 * and the screens say so; this is what happens until somebody does.
 */
export function deviceLabelMap(devices) {
  const labels = deviceLabels(devices);
  return new Map((devices ?? []).map((device, index) => [device.id, labels[index]]));
}

export function deviceLabels(devices) {
  const counts = new Map();
  for (const device of devices ?? []) {
    const label = deviceLabel(device);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }

  const seen = new Map();
  return (devices ?? []).map((device) => {
    const label = deviceLabel(device);
    if (counts.get(label) === 1) return label;
    const nth = (seen.get(label) ?? 0) + 1;
    seen.set(label, nth);
    return `${label} ${nth}`;
  });
}

/**
 * Power above which a device counts as running.
 *
 * Standby draw is real, so a bare "> 0" would show every device as active
 * forever and the bubbles would stop meaning anything. But the line has to sit
 * under the smallest thing worth seeing, and that is smaller than it sounds: a
 * tablet charger doing its job draws about five watts. Three leaves standby out
 * and lets everything that is actually running in.
 */
export const ACTIVE_WATTS = 3;

/**
 * De apparaten van deze klant opsommen, zoals je ze zou uitspreken.
 *
 * "de vaatwasser, de wasmachine of de laadpaal". Zonder deze lijst stond er een
 * vaste zin met een vaatwasser en een wasmachine erin, en bij een klant die er
 * geen van beide heeft las dat als een coach die het over iemand anders huis
 * heeft. Gevonden bij een klant op 28-08-2026, die alleen een laadpaal heeft.
 *
 * Alleen wat de klant zelf heeft ingevuld komt erin, met de naam die hij eraan
 * gaf. Heeft hij niets ingevuld, dan komt er niets: dan is er geen apparaat om
 * te noemen en hoort de zin dat ook niet te doen.
 *
 * En alleen apparaten waarbij het vinkje aan staat dat de coach er iets mee
 * mag: sturen, plannen of noemen. De eigenaar op 07-09-2026: "de coach zegt zet nu
 * de tablet lader aan, maar de tablet lader is alleen een vermogenssensor en
 * het vinkje staat uit." Een apparaat dat alleen gevolgd wordt, wordt nergens
 * genoemd.
 *
 * **En nooit iets wat de coach zelf stuurt of plant.** De eigenaar op 22-09-2026,
 * bij een tip die de thuisbatterij en de vaatwasser noemde: "je mag nooit de
 * batterij adviseren om aan te zetten, dat doet de coach zelf. Ook met een
 * laadpaal die stuurbaar is. Adviseer alleen apparaten die de coach niet
 * aanstuurt." Dus geen thuisbatterij, geen paal die de coach kan sturen, en
 * geen apparaat met een programma: dat plant de coach zelf en zegt hij op zijn
 * eigen kaart. Wat overblijft is wat op een meetstekker zit: de wasmachine, de
 * droger, een airco. Zie `canSteer`.
 *
 * @param {Array} devices de apparaten uit de instellingen
 * @param {string} voegwoord "of" bij een keuze, "en" bij een opsomming
 * @returns {string} de opsomming, of "" als er niets is
 */
export function apparatenZin(devices, voegwoord = "of") {
  const namen = (devices ?? [])
    .filter((device) => Boolean(device?.controllable))
    .filter((device) => device?.type !== "thuisbatterij" && !canSteer(device) && !PROGRAM_TYPES.includes(device?.type))
    .map((device) => {
      const eigen = (device?.name || "").trim();
      // Een naam die de klant zelf getypt heeft blijft staan zoals hij hem
      // schreef: "Bosch" verkleinen tot "de bosch" leest als een tikfout, en
      // het is zijn woord en niet het mijne. Alleen het woord dat wij er zelf
      // bij verzinnen als hij niets invulde ("Laadpaal") gaat naar
      // kleine letters, want dat staat middenin een zin.
      const soort = kindLabel(device);
      // Vulde hij precies het soortwoord in ("Laadpaal"), dan is dat geen naam
      // maar hetzelfde woord met een hoofdletter omdat het in een lijst stond.
      // Middenin een zin hoort dat klein. In de klantwoning las het anders als
      // "Zet de Laadpaal aan."
      if (!eigen || eigen.toLowerCase() === soort.toLowerCase()) {
        return soort.toLowerCase();
      }
      return eigen;
    })
    .filter(Boolean)
    // Twee keer dezelfde naam in één zin leest als een tikfout.
    .filter((naam, i, alle) => alle.indexOf(naam) === i);

  if (!namen.length) return "";
  // In de taal van nu (v0.139.0): "de vaatwasser, de droger of de airco", "the dryer or the
  // air conditioner".
  const met = namen.map((naam) => t("de {naam}", { naam }));
  if (met.length === 1) return met[0];
  const rest = met.slice(0, -1).join(", ");
  const laatste = met[met.length - 1];
  if (voegwoord === "en") return t("{rest} en {laatste}", { rest, laatste });
  if (voegwoord === "of") return t("{rest} of {laatste}", { rest, laatste });
  return `${rest} ${voegwoord} ${laatste}`;
}
