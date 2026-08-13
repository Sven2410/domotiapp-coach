"""The DomotiApp Coach integration.

Registers a standalone sidebar panel that serves the DomotiApp Coach dashboard.
The dashboard itself is a plain ES-module web component (no build step), which
keeps the repository directly installable through HACS.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import (
    CONF_DEMO_MODE,
    CONF_HOME_PATH,
    DEFAULT_DEMO_MODE,
    DEFAULT_HOME_PATH,
    DOMAIN,
    FRONTEND_DIR,
    PANEL_COMPONENT_NAME,
    PANEL_FILENAME,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    URL_BASE,
)

_LOGGER = logging.getLogger(__name__)

# Static paths survive a config entry reload, so they may only be registered
# once per Home Assistant run.
_STATIC_PATH_KEY = f"{DOMAIN}_static_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DomotiApp Coach from a config entry."""
    version = await _async_frontend_version(hass)

    await _async_register_static_path(hass)
    await _async_register_panel(hass, entry, version)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and remove the sidebar panel."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Re-register the panel when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_frontend_version(hass: HomeAssistant) -> str:
    """Return the integration version, used to bust the frontend cache."""
    integration = await async_get_integration(hass, DOMAIN)
    return str(integration.version or "0")


async def _async_register_static_path(hass: HomeAssistant) -> None:
    """Expose the frontend directory under URL_BASE."""
    if hass.data.get(_STATIC_PATH_KEY):
        return

    frontend_path = Path(__file__).parent / FRONTEND_DIR
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                URL_BASE,
                str(frontend_path),
                # Assets are versioned through a query string; skipping the
                # long-lived cache headers keeps upgrades predictable.
                cache_headers=False,
            )
        ]
    )
    hass.data[_STATIC_PATH_KEY] = True
    _LOGGER.debug("Serving DomotiApp Coach frontend from %s", frontend_path)


async def _async_register_panel(
    hass: HomeAssistant, entry: ConfigEntry, version: str
) -> None:
    """Add the DomotiApp Coach panel to the sidebar."""
    # A reload re-registers the panel, so drop any previous registration first.
    frontend.async_remove_panel(hass, PANEL_URL_PATH)

    options = {**entry.data, **entry.options}

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT_NAME,
        module_url=f"{URL_BASE}/{PANEL_FILENAME}?v={version}",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
        config={
            "version": version,
            "asset_base": URL_BASE,
            CONF_HOME_PATH: options.get(CONF_HOME_PATH, DEFAULT_HOME_PATH),
            CONF_DEMO_MODE: options.get(CONF_DEMO_MODE, DEFAULT_DEMO_MODE),
        },
    )
