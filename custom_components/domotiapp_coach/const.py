"""Constants for the DomotiApp Coach integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "domotiapp_coach"

# --- Sidebar panel ---------------------------------------------------------
PANEL_URL_PATH: Final = "domotiapp-coach"
PANEL_COMPONENT_NAME: Final = "domotiapp-coach-panel"
PANEL_TITLE: Final = "DomotiApp Coach"
PANEL_ICON: Final = "mdi:home-lightning-bolt"

# Public URL under which the panel assets are served.
URL_BASE: Final = "/domotiapp_coach_static"
FRONTEND_DIR: Final = "frontend"
PANEL_FILENAME: Final = "domotiapp-coach-panel.js"

# --- Options ---------------------------------------------------------------
# Path the "Home" button in the panel header navigates to. Customers run their
# dashboard in Kiosk Mode (no sidebar / no tabs), so the panel has to offer its
# own way back to the main dashboard.
CONF_HOME_PATH: Final = "home_path"
DEFAULT_HOME_PATH: Final = "/lovelace/0"

# Demo mode renders simulated values instead of real sensor data. Phase 1 ships
# with this on so the design can be reviewed before any entities are wired up.
CONF_DEMO_MODE: Final = "demo_mode"
DEFAULT_DEMO_MODE: Final = True
