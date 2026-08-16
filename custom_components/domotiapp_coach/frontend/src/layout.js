/**
 * How one person wants the overview arranged.
 *
 * Two places to keep it, because a household has both cases. What somebody
 * chooses is normally about them: they should find their own arrangement on
 * their phone, on the tablet in the hall and on the laptop alike, so it lives
 * with their Home Assistant user in the panel's settings. But a wall tablet in
 * the kitchen is a screen with a job rather than a person, and there the
 * arrangement belongs to the device. That one is kept in the browser itself and
 * wins over the account, because a screen that was deliberately set up a certain
 * way must not be rearranged from somebody's phone.
 *
 * Writing goes through a command of its own that is not admin-only: how you
 * want your own dashboard is not an installer's decision, and the people who
 * use this every day are exactly the ones who are not administrators.
 */

/**
 * The cards on the overview, in the order a fresh install shows them.
 *
 * Order matters here: it is the default arrangement, and it is also what a card
 * added in a later version falls back to. `label` is what the customer sees
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

/** Where a device-bound arrangement is kept. */
const LOCAL_KEY = "dac-overview-layout";

/** The default: everything, in the order above. */
export const defaultLayout = () =>
  OVERVIEW_CARDS.map((card) => ({ id: card.id, hidden: false }));

/**
 * Clean up a stored arrangement and fill in whatever it does not mention.
 *
 * A card that was added in a later version is not in anybody's stored layout,
 * and dropping it would mean a new feature silently never appears for existing
 * customers. So unknown ids are thrown away and missing ones are appended in
 * their default order, visible.
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

/** The arrangement kept in this browser, or null when there is none. */
export function localLayout() {
  try {
    const raw = localStorage.getItem(LOCAL_KEY);
    return raw ? reconcile(JSON.parse(raw)) : null;
  } catch {
    // Private mode, a full quota, a half-written value: none of it is worth
    // breaking the dashboard over.
    return null;
  }
}

/**
 * The arrangement to draw, and where it came from.
 *
 * @returns {{cards: Array<{id: string, hidden: boolean}>, scope: "device"|"user"}}
 */
export function effectiveLayout(settings, userId) {
  const local = localLayout();
  if (local) return { cards: local, scope: "device" };

  const mine = (settings?.layouts ?? []).find((entry) => entry?.user === userId);
  return { cards: reconcile(mine?.cards), scope: "user" };
}

/**
 * Store an arrangement.
 *
 * `scope` decides where: "device" writes it into this browser only, "user"
 * writes it to the account and clears the local one, so choosing "everywhere"
 * on a tablet actually takes effect there instead of being shadowed forever by
 * the copy it left behind.
 */
export async function saveLayout(hass, cards, scope) {
  const clean = reconcile(cards);

  if (scope === "device") {
    localStorage.setItem(LOCAL_KEY, JSON.stringify(clean));
    return;
  }

  localStorage.removeItem(LOCAL_KEY);
  await hass?.callWS({ type: "domotiapp_coach/layout/set", cards: clean });
}

/** Forget both copies, back to the arrangement this panel ships with. */
export async function resetLayout(hass) {
  localStorage.removeItem(LOCAL_KEY);
  await hass?.callWS({ type: "domotiapp_coach/layout/set", cards: defaultLayout() });
}
