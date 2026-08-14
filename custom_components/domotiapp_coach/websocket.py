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
    DEVICE_TYPES,
    EVENT_SETTINGS_UPDATED,
    GRID_MODE_SIGNED,
    GRID_MODE_SPLIT,
)
from .storage import async_get_store

# An entity id, or "" for "not configured yet".
_ENTITY = vol.Any("", vol.Match(r"^[a-z_]+\.[a-zA-Z0-9_]+$"))

_DEVICE = vol.Schema(
    {
        vol.Required("id"): str,
        vol.Required("type"): vol.In(DEVICE_TYPES),
        vol.Optional("name", default=""): str,
        vol.Optional("entity", default=""): _ENTITY,
    }
)

_SETTINGS = vol.Schema(
    {
        vol.Optional("navigation"): vol.Schema({vol.Optional("home_path"): str}),
        vol.Optional("sources"): vol.Schema(
            {
                vol.Optional("solar"): _ENTITY,
                vol.Optional("house"): _ENTITY,
                vol.Optional("grid_mode"): vol.In([GRID_MODE_SPLIT, GRID_MODE_SIGNED]),
                vol.Optional("grid_import"): _ENTITY,
                vol.Optional("grid_export"): _ENTITY,
                vol.Optional("grid_signed"): _ENTITY,
                vol.Optional("grid_signed_invert"): bool,
                vol.Optional("price"): _ENTITY,
            }
        ),
        vol.Optional("devices"): [_DEVICE],
        vol.Optional("thresholds"): vol.Schema(
            {
                vol.Optional("self_use"): vol.Schema(
                    {
                        vol.Optional("low"): vol.All(vol.Coerce(float), vol.Range(0, 100)),
                        vol.Optional("high"): vol.All(vol.Coerce(float), vol.Range(0, 100)),
                    }
                ),
                vol.Optional("price"): vol.Schema(
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
