"""Persisted settings for DomotiApp Coach.

The panel owns its own settings screen, so the values live in HA's storage
rather than in the config entry: a customer changing a threshold on their phone
should not reload the integration, and the config entry stays empty enough that
adding the integration asks nothing at all.
"""

from __future__ import annotations

import copy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DEFAULT_SETTINGS, DOMAIN, STORAGE_KEY, STORAGE_VERSION


def schema_bijwerken(
    strategy: dict[str, Any] | None,
    device_id: str,
    *,
    enabled: bool | None = None,
    window: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Het schema van één apparaat bijwerken, en verder niets aanraken.

    Los van de handler eronder zodat er een proef op kan zonder een draaiende
    Home Assistant. Wat hier telt is wat er níét gebeurt: de schema's van andere
    apparaten blijven staan, en `days` en `per_day` worden nooit aangeraakt.
    Een kaart die per dag ingestelde tijden zou vereenvoudigen tot één rij,
    schrijft met één tikje de zaterdag over de zondag heen.
    """
    uit = dict(strategy or {})
    schedules = [
        dict(entry) for entry in (uit.get("schedules") or []) if isinstance(entry, dict)
    ]

    entry = next((row for row in schedules if row.get("device") == device_id), None)
    if entry is None:
        # Nog nooit iets ingesteld voor dit apparaat. Dan is de schuif zelf het
        # eerste wat eraan gebeurt, en hoort er een schema te ontstaan.
        entry = {"device": device_id, "enabled": False, "per_day": False}
        schedules.append(entry)

    if enabled is not None:
        entry["enabled"] = bool(enabled)

    # Alleen bij een schema dat elke dag hetzelfde is; anders staan de tijden in
    # `days` en zou dit ze stilzwijgend buitenspel zetten.
    if window is not None and not entry.get("per_day"):
        entry["window"] = dict(window)

    uit["schedules"] = schedules
    return uit


def _prune(defaults: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Drop keys that the current version no longer knows about.

    Settings written by an older version keep their old fields forever
    otherwise, and the panel hands the whole section back when it saves -- so a
    field that was removed here turns into "extra keys not allowed" on the next
    save, and the customer cannot save anything at all. Pruning on load is what
    makes removing a setting a safe thing to do.

    Only dictionaries are walked. Lists (the device list) are the caller's own
    shape and are validated on the way in instead.
    """
    out: dict[str, Any] = {}
    for key, default in defaults.items():
        if key not in data:
            out[key] = copy.deepcopy(default)
        elif isinstance(default, dict) and isinstance(data[key], dict):
            out[key] = _prune(default, data[key])
        else:
            out[key] = copy.deepcopy(data[key])
    return out


def _merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge `incoming` onto `base`, returning a new dict.

    Nested sections are merged key by key so the panel can save one section
    without having to send the whole document back. Lists (the device list) are
    replaced wholesale -- merging them by index would make removing a device
    impossible.
    """
    out = copy.deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _forget_removed_devices(data: dict[str, Any]) -> dict[str, Any]:
    """Drop everything that points at a device that no longer exists.

    Several settings name a device rather than containing it: the list of
    devices released for steering, the schedules that say when an appliance may
    run, and what is remembered about the session at a charging point. Delete
    the dishwasher under Apparaten and they would all stay behind -- invisible, because every screen only lists what is still
    there, and quietly back in force the day a new device happened to be given
    the same id.

    Done here rather than in the panel because the panel saves one section at a
    time: the screen that removes a device is not the screen that owns the
    schedules, and it must not send that section along.
    """
    known = {device.get("id") for device in data.get("devices", []) if isinstance(device, dict)}

    data["ready_devices"] = [item for item in data.get("ready_devices", []) if item in known]

    # Hetzelfde geldt voor wat er per laadpunt over de lopende sessie bewaard
    # is: welke auto eraan hangt, wat de bewoner over de accustand zei en welke
    # knoppen aanstonden. Verdwijnt het apparaat, dan hoort dat mee weg.
    for sleutel in ("active_cars", "car_soc", "sessions"):
        data[sleutel] = [
            entry
            for entry in data.get(sleutel, [])
            if isinstance(entry, dict) and entry.get("device") in known
        ]

    strategy = data.get("strategy")
    if isinstance(strategy, dict):
        strategy["schedules"] = [
            entry
            for entry in strategy.get("schedules", [])
            if isinstance(entry, dict) and entry.get("device") in known
        ]

    return data


def _migrate(stored: dict[str, Any]) -> dict[str, Any]:
    """Bring a settings file written by an older version up to date.

    Runs before the defaults are merged in, so it works on exactly what was on
    disk. Without this the rename below would simply drop the customer's
    setting on the floor: pruning removes keys the current version does not
    know, and it cannot tell a removed setting from a renamed one.
    """
    strategy = stored.get("strategy")
    if not isinstance(strategy, dict):
        return stored

    # v0.9.0 had a single "klaar om" time per device; v0.10.0 has a window of
    # three times, of which that one is `done_by`.
    if "deadlines" in strategy and "schedules" not in strategy:
        strategy["schedules"] = [
            {
                "device": entry.get("device", ""),
                "enabled": bool(entry.get("enabled")),
                "per_day": False,
                "window": {"not_before": "", "start_by": "", "done_by": entry.get("time", "")},
                "days": [],
            }
            for entry in strategy.get("deadlines", [])
            if isinstance(entry, dict) and entry.get("device")
        ]

    return stored


class SettingsStore:
    """Load, cache and save the panel's settings."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up the store without touching disk yet."""
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] | None = None

    async def async_load(self) -> dict[str, Any]:
        """Return the settings, filling in anything a newer version added."""
        if self._data is None:
            stored = _migrate(await self._store.async_load() or {})
            # Defaults are merged in on every load, so a settings file written by
            # an older version still gains the keys a newer one expects -- and
            # pruned afterwards, so it loses the ones that are gone.
            self._data = _forget_removed_devices(
                _prune(DEFAULT_SETTINGS, _merge(DEFAULT_SETTINGS, stored))
            )
        return copy.deepcopy(self._data)

    async def async_save(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Merge `changes` into the settings, persist them and return the result."""
        current = await self.async_load()
        self._data = _forget_removed_devices(_prune(DEFAULT_SETTINGS, _merge(current, changes)))
        await self._store.async_save(self._data)
        return copy.deepcopy(self._data)


def async_get_store(hass: HomeAssistant) -> SettingsStore:
    """Return the one store for this Home Assistant instance."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "store" not in domain_data:
        domain_data["store"] = SettingsStore(hass)
    return domain_data["store"]
