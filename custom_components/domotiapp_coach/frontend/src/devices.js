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
