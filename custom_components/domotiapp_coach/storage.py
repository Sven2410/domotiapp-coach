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


class SettingsStore:
    """Load, cache and save the panel's settings."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up the store without touching disk yet."""
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] | None = None

    async def async_load(self) -> dict[str, Any]:
        """Return the settings, filling in anything a newer version added."""
        if self._data is None:
            stored = await self._store.async_load() or {}
            # Defaults are merged in on every load, so a settings file written by
            # an older version still gains the keys a newer one expects.
            self._data = _merge(DEFAULT_SETTINGS, stored)
        return copy.deepcopy(self._data)

    async def async_save(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Merge `changes` into the settings, persist them and return the result."""
        current = await self.async_load()
        self._data = _merge(current, changes)
        await self._store.async_save(self._data)
        return copy.deepcopy(self._data)


def async_get_store(hass: HomeAssistant) -> SettingsStore:
    """Return the one store for this Home Assistant instance."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "store" not in domain_data:
        domain_data["store"] = SettingsStore(hass)
    return domain_data["store"]
