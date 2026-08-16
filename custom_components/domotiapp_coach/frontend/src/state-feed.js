/**
 * A live view of the entities the dashboard cares about.
 *
 * Home Assistant hands a custom panel a `hass` object and replaces it whenever
 * anything changes, and for most panels that is enough. Here it was not: the
 * readings on Overzicht sat still until the customer switched dashboards and
 * came back, which is the signature of a panel that is only handed a fresh
 * `hass` when it is (re)attached rather than on every state change.
 *
 * So the panel stops depending on being handed anything. It subscribes to
 * `state_changed` itself and keeps its own map, seeded from whatever `hass` it
 * was given.
 *
 * Which of the two is right is decided per entity by `last_updated`, and that
 * matters more than it looks. A phone puts the app to sleep, the websocket
 * drops, and every event fired in the meantime is simply gone -- nobody replays
 * them. If the remembered event always won, that entity would keep showing the
 * reading it had when the screen went off, forever, and only a full reload of
 * Home Assistant would clear it. That is exactly what a customer sees as "the
 * dishwasher is stuck at 51 W on my phone".
 *
 * Belt and braces: on every reconnect the feed also refetches the states
 * itself, so it does not depend on being handed a fresh `hass` either.
 */

/**
 * When a state was last updated, as a number.
 *
 * Memoised on the state object rather than parsed per read: comparing two
 * candidates happens for every entity on every redraw, several times a second.
 */
const STAMPS = new WeakMap();

function stampOf(state) {
  if (!state) return -1;
  let stamp = STAMPS.get(state);
  if (stamp === undefined) {
    stamp = Date.parse(state.last_updated ?? state.last_changed ?? "") || 0;
    STAMPS.set(state, stamp);
  }
  return stamp;
}

export class StateFeed {
  constructor() {
    /** Entities we have seen an event for. */
    this.live_ = new Map();
    this.seed_ = {};
    this.listeners_ = new Set();
    this.unsubscribe_ = null;
    this.connecting_ = null;
    this.connection_ = null;
  }

  /**
   * Seed from a `hass` object and, the first time, start the subscription.
   * @param {object} hass
   */
  connect(hass) {
    if (hass?.states) this.seed_ = hass.states;

    const connection = hass?.connection;
    // Bail out only when this is the same connection we are already on. A new
    // one means a new subscription is due -- holding on to the old handle here
    // is what would leave the panel listening to a socket nobody is on.
    if (!connection || connection === this.connection_) return this.connecting_;

    this.connection_ = connection;
    this.unsubscribe_ = null;

    // Home Assistant's own socket restores its subscriptions after a drop, but
    // whatever happened while it was down was never sent to anyone. Refetching
    // on every reconnect is the only way to find out what changed meanwhile.
    // Optional because not every host of this panel is a full connection.
    connection.addEventListener?.("ready", () => this.resync_(connection));

    this.connecting_ = connection
      .subscribeEvents((event) => this.onStateChanged_(event), "state_changed")
      .then((unsubscribe) => {
        this.unsubscribe_ = unsubscribe;
        return unsubscribe;
      })
      .catch((error) => {
        // Not fatal: the seed still updates whenever HA does hand over a fresh
        // `hass`, so the dashboard degrades to how it behaved before.
        console.warn("[DomotiApp Coach] kon statuswijzigingen niet volgen", error);
        this.connecting_ = null;
      });

    return this.connecting_;
  }

  /** Pull a complete set of states after a reconnect and tell everyone. */
  async resync_(connection) {
    try {
      const states = await connection.sendMessagePromise({ type: "get_states" });
      if (connection !== this.connection_) return;

      this.live_ = new Map(states.map((state) => [state.entity_id, state]));
      for (const listener of this.listeners_) listener(null);
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de meetwaarden niet opnieuw ophalen", error);
    }
  }

  onStateChanged_(event) {
    const id = event?.data?.entity_id;
    const state = event?.data?.new_state;
    if (!id) return;

    if (state) this.live_.set(id, state);
    else this.live_.delete(id);

    for (const listener of this.listeners_) listener(id);
  }

  /**
   * Current state object for an entity, or undefined.
   * @param {string} entityId
   */
  get(entityId) {
    if (!entityId) return undefined;

    const live = this.live_.get(entityId);
    const seed = this.seed_[entityId];
    if (!live) return seed;
    if (!seed) return live;

    // Whichever of the two was measured last. Neither source is reliably ahead:
    // the seed goes stale when `hass` is not handed over, and the event map
    // goes stale across a dropped connection.
    return stampOf(seed) > stampOf(live) ? seed : live;
  }

  /** Every entity id we know about, for the picker. */
  ids() {
    const ids = new Set(Object.keys(this.seed_));
    for (const id of this.live_.keys()) ids.add(id);
    return [...ids];
  }

  /** @param {(entityId: string) => void} listener */
  subscribe(listener) {
    this.listeners_.add(listener);
    return () => this.listeners_.delete(listener);
  }

  /**
   * Drop the subscription to Home Assistant.
   *
   * Listeners are kept. They belong to components that get detached and
   * reattached all the time, and throwing them away on a detach means nothing
   * ever hears about a change again.
   */
  disconnect() {
    this.unsubscribe_?.();
    this.unsubscribe_ = null;
    this.connecting_ = null;
    this.connection_ = null;
  }
}
