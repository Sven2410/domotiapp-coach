/**
 * How this screen shows the overview.
 *
 * Per screen, deliberately, and not per person. Hanging it on the Home
 * Assistant user sounds tidier until you look at a real household: everybody
 * shares one account, or one person has the panel open on three devices at
 * once. Then rearranging the dashboard on your own laptop silently rearranges
 * the phone in somebody else's pocket. A wall tablet in the hall is a screen
 * with a job rather than a person, and the kitchen tablet should stay the way
 * the kitchen wants it.
 *
 * So it lives in this browser and nowhere else. Nothing to save on the server,
 * nothing that can reach another device, and nothing to ask the customer about.
 */

/**
 * The cards on the overview, in the order a fresh install shows them.
 *
 * Order matters here: it is the default arrangement, and it is also where a
 * card added in a later version ends up. `label` is what the customer sees
 * while rearranging, so it names the card rather than the code behind it.
 */
export const OVERVIEW_CARDS = [
  { id: "coach", label: "Energiecoach" },
  { id: "tiles", label: "Meetwaarden" },
  { id: "phases", label: "Belasting per fase" },
  { id: "meters", label: "Je meter" },
  { id: "steerable", label: "Aanstuurbare apparaten" },
  { id: "flow", label: "Energiestroom" },
];

const KNOWN = new Set(OVERVIEW_CARDS.map((card) => card.id));

const KEY = "dac-overview-layout";

/** The default: everything, in the order above. */
export const defaultLayout = () =>
  OVERVIEW_CARDS.map((card) => ({ id: card.id, hidden: false }));

/**
 * Clean up a stored arrangement and fill in whatever it does not mention.
 *
 * A card added in a later version is in nobody's stored layout, and dropping it
 * would mean a new feature silently never appears for existing customers. So
 * unknown ids are thrown away and missing ones are appended in their default
 * order, visible.
 */
function reconcile(cards) {
  const seen = new Set();
  const out = [];

  for (const card of cards ?? []) {
    if (!KNOWN.has(card?.id) || seen.has(card.id)) continue;
    seen.add(card.id);
    out.push({ id: card.id, hidden: Boolean(card.hidden) });
  }

  for (const card of OVERVIEW_CARDS) {
    if (!seen.has(card.id)) out.push({ id: card.id, hidden: false });
  }

  return out;
}

/** The arrangement to draw on this screen. */
export function effectiveLayout() {
  try {
    const raw = localStorage.getItem(KEY);
    return reconcile(raw ? JSON.parse(raw) : null);
  } catch {
    // Private mode, a full quota, a half-written value: none of it is worth
    // breaking the dashboard over.
    return defaultLayout();
  }
}

/** Remember this arrangement on this screen. */
export function saveLayout(cards) {
  try {
    localStorage.setItem(KEY, JSON.stringify(reconcile(cards)));
  } catch {
    // Nothing to be done, and nothing worth interrupting the customer for.
  }
}

/** Forget it, back to the arrangement this panel ships with. */
export function resetLayout() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // As above.
  }
}
