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

# --- Contract --------------------------------------------------------------
CONTRACT_FIXED: Final = "fixed"
CONTRACT_DYNAMIC: Final = "dynamic"

# A dynamic contract either has one entity that already carries the all-in
# price, or a market price that still needs tax, markup and VAT applied.
DYNAMIC_ALL_IN: Final = "all_in"
DYNAMIC_MARKET: Final = "market"

# Nominal voltage per phase, used to turn the main fuse into a power ceiling.
# 3 x 25 A -> 17250 W, 1 x 25 A -> 5750 W.
GRID_VOLTAGE: Final = 230

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
    },
    "installation": {
        "home_name": "",
        # 1 or 3. With the main fuse it gives the connection's power ceiling.
        "phases": 3,
        "fuse_amps": 25,
        # Derived from phases x fuse x 230 V while `max_grid_auto` holds, but
        # editable: a customer with a limited or reinforced connection knows
        # better than the arithmetic does.
        "max_grid_watts": 17250,
        "max_grid_auto": True,
    },
    "contract": {
        "type": CONTRACT_FIXED,
        "fixed": {
            "all_in_price": 0.28,
            "feed_in_tariff": 0.07,
            "feed_in_costs": 0.0,
        },
        "dynamic": {
            "source": DYNAMIC_ALL_IN,
            # One entity that already includes tax, markup and VAT.
            "all_in_entity": "",
            # Or the bare market price, with the rest added here.
            "market_entity": "",
            "energy_tax": 0.1088,
            "supplier_markup": 0.02,
            "vat_percent": 21,
            "feed_in_costs": 0.0,
        },
    },
    "devices": [],
    "thresholds": {
        # Zelfbenutting in percent: below `low` is bad, above `high` is good.
        "self_use": {"low": 30, "high": 70},
        # Energy price in euro per kWh: below `low` is good, above `high` is bad.
        "price": {"low": 0.20, "high": 0.30},
    },
}
