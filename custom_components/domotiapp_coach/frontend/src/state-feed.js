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
 * was given. Events win over the seed, so even a completely frozen `hass`
 * property no longer freezes the dashboard.
 */

export class StateFeed {
  constructor() {
    /** Entities we have seen an event for -- always newer than the seed. */
    this.live_ = new Map();
    this.seed_ = {};
    this.listeners_ = new Set();
    this.unsubscribe_ = null;
    this.connecting_ = null;
  }

  /**
   * Seed from a `hass` object and, the first time, start the subscription.
   * @param {object} hass
   */
  connect(hass) {
    if (hass?.states) this.seed_ = hass.states;
    if (!hass?.connection || this.unsubscribe_ || this.connecting_) return this.connecting_;

    this.connecting_ = hass.connection
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
    return this.live_.get(entityId) ?? this.seed_[entityId];
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

  disconnect() {
    this.unsubscribe_?.();
    this.unsubscribe_ = null;
    this.connecting_ = null;
    this.listeners_.clear();
  }
}
