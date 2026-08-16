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

from . import report, websocket
from .coach import async_get_coach
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
    report.async_register(hass)
    await _async_register_static_path(hass, version)
    await _async_register_panel(hass, version)
    await _async_start_monitor(hass)
    _async_start_coach(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and remove the sidebar panel."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH)

    monitor: LoadMonitor | None = hass.data.get(DOMAIN, {}).pop(_MONITOR_KEY, None)
    if monitor:
        monitor.async_stop()

    coach = hass.data.get(DOMAIN, {}).pop("coach", None)
    if coach:
        coach.async_stop()

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


def _async_start_coach(hass: HomeAssistant) -> None:
    """Start the round that steers the charging points.

    Here rather than in the panel for the same reason as the load monitor: a car
    has to start charging at two in the morning, and nobody is looking at a
    dashboard at two in the morning. It also has to survive a restart without
    anybody noticing, which it does by reading the state of the installation
    rather than remembering its own.
    """
    async_get_coach(hass).async_start()


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


def asset_base(version: str) -> str:
    """Where this build of the panel is served from.

    The version is in the path and not in a query string, and that difference is
    the whole point. The panel is a graph of ES modules that import each other by
    relative path, and a relative import resolves against the URL of the module
    doing the importing. Versioning only the entry point therefore versions only
    the entry point: every module under it keeps the same URL from one release to
    the next, and a browser that already has one is perfectly entitled to go on
    using it. That is how a customer ends up with a panel that is half new after
    an update, which is the kind of thing that looks like a bug in the panel and
    is nearly impossible to diagnose from a distance.

    With the version in the path, a new release is simply a new set of URLs and
    the question does not arise.
    """
    return f"{URL_BASE}/{version}"


async def _async_register_static_path(hass: HomeAssistant, version: str) -> None:
    """Expose the frontend directory under a URL that carries the version."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_STATIC_PATH_KEY):
        return

    frontend_path = Path(__file__).parent / FRONTEND_DIR
    await hass.http.async_register_static_paths(
        [
            # The versioned path first, so it wins over the plain one.
            StaticPathConfig(asset_base(version), str(frontend_path), cache_headers=True),
            # And the plain path as well, purely so that a browser still holding
            # a page from before this release can finish what it was doing
            # instead of breaking halfway. Nothing new points at it, and without
            # the long-lived cache headers it is always revalidated.
            StaticPathConfig(URL_BASE, str(frontend_path), cache_headers=False),
        ]
    )
    domain_data[_STATIC_PATH_KEY] = True
    _LOGGER.debug(
        "Serving DomotiApp Coach frontend %s from %s", version, frontend_path
    )


async def _async_register_panel(hass: HomeAssistant, version: str) -> None:
    """Add the DomotiApp Coach panel to the sidebar."""
    # A reload re-registers the panel, so drop any previous registration first.
    frontend.async_remove_panel(hass, PANEL_URL_PATH)

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT_NAME,
        module_url=f"{asset_base(version)}/{PANEL_FILENAME}",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
        config={"version": version, "asset_base": asset_base(version)},
    )
