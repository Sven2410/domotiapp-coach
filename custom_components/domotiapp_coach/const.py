"""Constants for the DomotiApp Coach integration."""

from __future__ import annotations

from typing import Any, Final

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

# --- Settings storage ------------------------------------------------------
# Everything configurable lives in the panel's own Instellingen section rather
# than in a Home Assistant options flow: customers run this on a phone behind
# Kiosk Mode, where HA's own settings screens are out of reach.
STORAGE_KEY: Final = f"{DOMAIN}.settings"
STORAGE_VERSION: Final = 1

# Fired on the event bus after a save, so every open panel refreshes itself.
EVENT_SETTINGS_UPDATED: Final = f"{DOMAIN}_settings_updated"

# --- Device types ----------------------------------------------------------
# "overig" carries a free-text name; the rest are named by their type.
DEVICE_TYPES: Final = [
    "laadpaal",
    "thuisbatterij",
    "warmtepomp",
    "boiler",
    "vaatwasser",
    "wasmachine",
    "droger",
    "airco",
    "zwembadpomp",
    "overig",
]

# --- Grid metering patterns ------------------------------------------------
# Customers have one of two: a pair of sensors where one is always zero, or a
# single sensor that goes negative while feeding back into the grid.
GRID_MODE_SPLIT: Final = "split"
GRID_MODE_SIGNED: Final = "signed"

# --- Default settings ------------------------------------------------------
# The panel falls back to simulated values while `sources` is still empty, so a
# fresh install shows a working dashboard before any sensor is mapped.
DEFAULT_SETTINGS: Final[dict[str, Any]] = {
    "navigation": {
        # Where the Home button goes. Customers run Kiosk Mode (no sidebar, no
        # tabs), so the panel has to offer its own way back.
        "home_path": "/lovelace/0",
    },
    "sources": {
        "solar": "",
        "house": "",
        "grid_mode": GRID_MODE_SPLIT,
        "grid_import": "",
        "grid_export": "",
        "grid_signed": "",
        # Most single-sensor meters report negative while feeding back, but not
        # all of them. Without this the diagram runs exactly backwards, and it
        # looks plausible enough that nobody questions it.
        "grid_signed_invert": False,
        "price": "",
    },
    "devices": [],
    "thresholds": {
        # Zelfbenutting in percent: below `low` is bad, above `high` is good.
        "self_use": {"low": 30, "high": 70},
        # Energy price in euro per kWh: below `low` is good, above `high` is bad.
        "price": {"low": 0.20, "high": 0.30},
    },
}
