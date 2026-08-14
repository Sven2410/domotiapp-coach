"""Websocket API the panel uses to read and write its settings.

The panel is a plain web component with no build step, so it talks to Home
Assistant over the connection HA already hands it. Reading is open to any signed
in user -- a customer needs the settings just to render the dashboard -- while
writing is admin-only, so a household member cannot silently repoint the meter.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import (
    CHARGER_BRANDS,
    CONTRACT_DYNAMIC,
    CONTRACT_FIXED,
    DEVICE_TYPES,
    DYNAMIC_ALL_IN,
    DYNAMIC_MARKET,
    EVENT_SETTINGS_UPDATED,
    GRID_MODE_SIGNED,
    GRID_MODE_SPLIT,
)
from .storage import async_get_store


def _schema(mapping: dict) -> vol.Schema:
    """A settings schema that drops fields it does not recognise.

    Rejecting them instead looks tidy until a setting is removed: the panel
    hands whole sections back when it saves, so a customer whose stored settings
    still carry a field from an older version could not save anything at all
    until the storage had been cleaned. Dropping is the forgiving half; the
    storage prunes the leftovers on load.
    """
    return vol.Schema(mapping, extra=vol.REMOVE_EXTRA)


# An entity id, or "" for "not configured yet".
_ENTITY = vol.Any("", vol.Match(r"^[a-z_]+\.[a-zA-Z0-9_]+$"))

# A euro amount per kWh. Negative is real: market prices go below zero.
_EURO = vol.All(vol.Coerce(float), vol.Range(-100, 100))

_PHASE = _schema(
    {
        vol.Optional("current"): _ENTITY,
        vol.Optional("power"): _ENTITY,
        vol.Optional("voltage"): _ENTITY,
    }
)

_DEVICE = _schema(
    {
        vol.Required("id"): str,
        vol.Required("type"): vol.In(DEVICE_TYPES),
        vol.Optional("name", default=""): str,
        # The power sensor. Every device has one, whatever it is -- it is what
        # puts the device on the energy flow at all.
        vol.Optional("entity", default=""): _ENTITY,
        # Chargers only, "" until one is picked.
        vol.Optional("brand", default=""): vol.In([*CHARGER_BRANDS, ""]),
        # Whether the coach may steer this device once steering exists. Plenty
        # of appliances sit on a smart plug that can only measure, so this is a
        # choice per device rather than a property of the type.
        vol.Optional("controllable", default=False): bool,
        # Whatever else the brand offers, keyed by the panel's own field names.
        # Free-form on purpose: adding a brand should not need a schema change
        # here as well as in the panel.
        vol.Optional("entities", default=dict): {vol.Match(r"^[a-z0-9_]+$"): _ENTITY},
    }
)

_SETTINGS = _schema(
    {
        vol.Optional("navigation"): _schema({vol.Optional("home_path"): str}),
        vol.Optional("sources"): _schema(
            {
                vol.Optional("solar"): _ENTITY,
                vol.Optional("grid_mode"): vol.In([GRID_MODE_SPLIT, GRID_MODE_SIGNED]),
                vol.Optional("grid_import"): _ENTITY,
                vol.Optional("grid_export"): _ENTITY,
                vol.Optional("grid_signed"): _ENTITY,
                vol.Optional("grid_signed_invert"): bool,
                vol.Optional("phases_enabled"): bool,
                vol.Optional("phases_on_overview"): bool,
                vol.Optional("phases"): _schema(
                    {vol.Optional(phase): _PHASE for phase in ("l1", "l2", "l3")}
                ),
            }
        ),
        vol.Optional("strategy"): _schema(
            {
                vol.Optional("load_alert"): _schema(
                    {
                        vol.Optional("enabled"): bool,
                        vol.Optional("threshold_percent"): vol.All(
                            vol.Coerce(float), vol.Range(1, 200)
                        ),
                        vol.Optional("targets"): [str],
                        vol.Optional("min_interval_minutes"): vol.All(
                            vol.Coerce(int), vol.Range(1, 1440)
                        ),
                        vol.Optional("min_duration_seconds"): vol.All(
                            vol.Coerce(int), vol.Range(0, 3600)
                        ),
                    }
                ),
            }
        ),
        vol.Optional("installation"): _schema(
            {
                vol.Optional("home_name"): str,
                vol.Optional("phases"): vol.In([1, 3]),
                vol.Optional("fuse_amps"): vol.All(vol.Coerce(float), vol.Range(1, 1000)),
                vol.Optional("max_grid_watts"): vol.All(vol.Coerce(float), vol.Range(0, 1_000_000)),
                vol.Optional("max_grid_auto"): bool,
            }
        ),
        vol.Optional("contract"): _schema(
            {
                vol.Optional("type"): vol.In([CONTRACT_FIXED, CONTRACT_DYNAMIC]),
                vol.Optional("fixed"): _schema(
                    {
                        vol.Optional("all_in_price"): _EURO,
                        vol.Optional("feed_in_tariff"): _EURO,
                        vol.Optional("feed_in_costs"): _EURO,
                    }
                ),
                vol.Optional("dynamic"): _schema(
                    {
                        vol.Optional("source"): vol.In([DYNAMIC_ALL_IN, DYNAMIC_MARKET]),
                        vol.Optional("all_in_entity"): _ENTITY,
                        vol.Optional("market_entity"): _ENTITY,
                        vol.Optional("energy_tax"): _EURO,
                        vol.Optional("supplier_markup"): _EURO,
                        vol.Optional("vat_percent"): vol.All(vol.Coerce(float), vol.Range(0, 100)),
                        vol.Optional("feed_in_costs"): _EURO,
                    }
                ),
            }
        ),
        vol.Optional("devices"): [_DEVICE],
        vol.Optional("thresholds"): _schema(
            {
                vol.Optional("self_use"): _schema(
                    {
                        vol.Optional("low"): vol.All(vol.Coerce(float), vol.Range(0, 100)),
                        vol.Optional("high"): vol.All(vol.Coerce(float), vol.Range(0, 100)),
                    }
                ),
                vol.Optional("price"): _schema(
                    {
                        vol.Optional("low"): vol.All(vol.Coerce(float), vol.Range(0, 10)),
                        vol.Optional("high"): vol.All(vol.Coerce(float), vol.Range(0, 10)),
                    }
                ),
            }
        ),
    }
)


@websocket_api.websocket_command({vol.Required("type"): "domotiapp_coach/settings/get"})
@websocket_api.async_response
async def async_get_settings(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send the current settings to the panel."""
    settings = await async_get_store(hass).async_load()
    connection.send_result(msg["id"], settings)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "domotiapp_coach/settings/set",
        vol.Required("settings"): _SETTINGS,
    }
)
@websocket_api.async_response
async def async_set_settings(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Merge the given changes into the settings and persist them."""
    settings = await async_get_store(hass).async_save(msg["settings"])
    # Other open panels -- a tablet on the wall, a second phone -- pick the new
    # values up from this rather than having to be reloaded by hand.
    hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": settings})
    connection.send_result(msg["id"], settings)


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the panel's websocket commands."""
    websocket_api.async_register_command(hass, async_get_settings)
    websocket_api.async_register_command(hass, async_set_settings)
