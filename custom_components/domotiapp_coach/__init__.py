"""The DomotiApp Coach integration.

Registers a standalone sidebar panel that serves the DomotiApp Coach dashboard.
The dashboard itself is a plain ES-module web component (no build step), which
keeps the repository directly installable through HACS.

Everything configurable lives in the panel's own Instellingen section, reached
over the websocket API in websocket.py -- so adding the integration asks nothing
and a customer can change settings from their phone.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from . import websocket
from .monitor import LoadMonitor
from .const import (
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

# Static paths and websocket commands survive a config entry reload, so they may
# only be registered once per Home Assistant run.
_STATIC_PATH_KEY = "static_registered"
_WEBSOCKET_KEY = "websocket_registered"
_MONITOR_KEY = "load_monitor"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DomotiApp Coach from a config entry."""
    version = await _async_frontend_version(hass)

    _async_register_websocket(hass)
    await _async_register_static_path(hass)
    await _async_register_panel(hass, version)
    await _async_start_monitor(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and remove the sidebar panel."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH)

    monitor: LoadMonitor | None = hass.data.get(DOMAIN, {}).pop(_MONITOR_KEY, None)
    if monitor:
        monitor.async_stop()

    return True


async def _async_start_monitor(hass: HomeAssistant) -> None:
    """Start watching the load on the connection.

    This runs in the integration rather than in the panel because the warning
    has to arrive when nobody has the dashboard open -- which is most of the
    time, and exactly when a heavy load goes unnoticed.
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_MONITOR_KEY):
        return

    monitor = LoadMonitor(hass)
    await monitor.async_start()
    domain_data[_MONITOR_KEY] = monitor


async def _async_frontend_version(hass: HomeAssistant) -> str:
    """Return the integration version, used to bust the frontend cache."""
    integration = await async_get_integration(hass, DOMAIN)
    return str(integration.version or "0")


def _async_register_websocket(hass: HomeAssistant) -> None:
    """Register the settings websocket commands once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_WEBSOCKET_KEY):
        return

    websocket.async_register(hass)
    domain_data[_WEBSOCKET_KEY] = True


async def _async_register_static_path(hass: HomeAssistant) -> None:
    """Expose the frontend directory under URL_BASE."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_STATIC_PATH_KEY):
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
    domain_data[_STATIC_PATH_KEY] = True
    _LOGGER.debug("Serving DomotiApp Coach frontend from %s", frontend_path)


async def _async_register_panel(hass: HomeAssistant, version: str) -> None:
    """Add the DomotiApp Coach panel to the sidebar."""
    # A reload re-registers the panel, so drop any previous registration first.
    frontend.async_remove_panel(hass, PANEL_URL_PATH)

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT_NAME,
        module_url=f"{URL_BASE}/{PANEL_FILENAME}?v={version}",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
        config={"version": version, "asset_base": URL_BASE},
    )
