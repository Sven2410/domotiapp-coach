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

# --- Charger brands --------------------------------------------------------
# Which extra entities a charging point offers depends entirely on its brand:
# not every charger can be started, stopped or paused, and the ones that can do
# not agree on how. Picking the brand is what decides which fields are asked
# for. Only Easee is filled in so far; the rest are listed so a customer can
# already say what they have.
CHARGER_BRANDS: Final = [
    "easee",
    "zaptec",
    "wallbox",
    "zappi",
    "peblar",
    "overig",
]

# --- Dishwasher brands -----------------------------------------------------
# Same reasoning as the chargers: what a dishwasher reports and how it is
# started differs per brand. Home Connect covers Bosch, Siemens, Neff,
# Gaggenau and Constructa in one, because they all speak the same API.
DISHWASHER_BRANDS: Final = [
    "home_connect",
    "miele",
    "lg",
    "overig",
]

# Every brand id the panel may send, whatever the device type. Kept as one set
# so the websocket schema does not have to know which brands belong to which
# type -- the panel decides that, and it only ever sends one it offered.
ALL_BRANDS: Final = sorted({*CHARGER_BRANDS, *DISHWASHER_BRANDS})

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

# How often a dynamic price changes. The Dutch market is moving from hourly to
# quarter-hourly settlement, and suppliers are following at their own pace, so
# it is the customer who knows which one their contract is on. It decides the
# block size the coach plans in.
PRICE_INTERVAL_HOUR: Final = "hour"
PRICE_INTERVAL_QUARTER: Final = "quarter"

# Nominal voltage per phase, used to turn the main fuse into a power ceiling.
# 3 x 25 A -> 17250 W, 1 x 25 A -> 5750 W.
GRID_VOLTAGE: Final = 230

# --- How much the coach may do on its own ----------------------------------
# Not a strategy but a level of trust, and they are different questions: a
# strategy says what to aim for, this says how far the coach may go on its own.
# "Voorstellen" is the one that matters most in practice -- it is what lets
# somebody watch the sums be right for a week before letting go.
LEVEL_READ: Final = "read"
LEVEL_ADVISE: Final = "advise"
LEVEL_PROPOSE: Final = "propose"
LEVEL_STEER: Final = "steer"
LEVELS: Final = [LEVEL_READ, LEVEL_ADVISE, LEVEL_PROPOSE, LEVEL_STEER]

# What the coach optimises for once it is allowed to act.
GOAL_COST: Final = "cost"
GOAL_SOLAR: Final = "solar"
GOALS: Final = [GOAL_COST, GOAL_SOLAR]

# Fired after every round, so an open panel can show what was decided without
# writing anything to disk a minute at a time.
EVENT_DECISION: Final = f"{DOMAIN}_decision"

# --- Steering a charging point ---------------------------------------------
# How each brand is told what to do. The dynamic limit is the safe way in: it
# sits under the charger's own maximum, so a mistake there cannot ask for more
# than the installation allows. The words for start and stop differ per brand
# and even per firmware, so what the customer typed in wins over these.
CHARGER_CONTROL: Final = {
    "easee": {
        "limit_service": ("easee", "set_charger_dynamic_limit"),
        "limit_field": "current",
        # Nought means "until further notice". A limit that expires would fall
        # back to the charger's own maximum, which is the wrong way to fail.
        "limit_extra": {"time_to_live": 0},
        "command_service": ("easee", "action_command"),
        "command_field": "action_command",
        "words": {"start": "start", "stop": "stop", "pause": "pause", "resume": "resume"},
    },
}

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
        # House consumption is never configured: it follows from generation and
        # the meter, and one less mandatory sensor is one less thing to get
        # wrong at a customer.
        "grid_mode": GRID_MODE_SPLIT,
        "grid_import": "",
        "grid_export": "",
        "grid_signed": "",
        # Most single-sensor meters report negative while feeding back, but not
        # all of them. Without this the diagram runs exactly backwards, and it
        # looks plausible enough that nobody questions it.
        "grid_signed_invert": False,
        # Per-phase detail, when the customer's meter offers it. With phase
        # currents the load on the connection can be judged per phase, which is
        # what actually trips a fuse -- an average never does.
        "phases_enabled": False,
        "phases_on_overview": False,
        "phases": {
            "l1": {"current": "", "power": "", "voltage": ""},
            "l2": {"current": "", "power": "", "voltage": ""},
            "l3": {"current": "", "power": "", "voltage": ""},
        },
        # What the sun is expected to bring. Not a measurement but a forecast,
        # and it is used for a different question than the meters are: not "what
        # is happening" but "is it worth waiting". Forecast.Solar and Solcast
        # both publish this as plain sensors, so it is entity fields rather than
        # an integration this panel talks to itself.
        "solar_forecast": {
            "remaining_today": "",
            "tomorrow": "",
            "peak_today": "",
        },
        # The meter readings themselves: the four counters a Dutch smart meter
        # keeps for electricity, plus gas. These are totals rather than a rate,
        # so nothing on the dashboard computes with them -- they are what a
        # customer copies onto a supplier's website, and having them on the
        # overview saves a trip to the meter cupboard.
        #
        # Gas has its own switch because plenty of houses no longer have it,
        # and an empty gas line on the card reads as a broken sensor.
        "meters": {
            # The generation counter, in kWh. Not the same thing as the power
            # sensor above: that one says what the panels do right now, and a
            # counter is what makes it possible to look back at a week.
            "solar_total": "",
            "import_low": "",
            "import_high": "",
            "export_low": "",
            "export_high": "",
            "gas_enabled": False,
            "gas": "",
        },
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
        # Whether something else already guards this fuse in hardware, such as
        # an Easee Equalizer. It changes how much room the coach leaves under
        # the fuse: with a balancer present it gives way first, so the balancer
        # never has to intervene at all.
        "load_balancer": False,
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
            # Hourly or quarter-hourly. Not derivable from the price sensor:
            # a sensor that only publishes hourly prices looks exactly the same
            # as a quarter-hourly one that happens to be flat for an hour.
            "interval": PRICE_INTERVAL_HOUR,
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
    "strategy": {
        # How far the coach may go on its own. It starts at "propose": it works
        # out what it would do and shows it, and only acts once somebody agrees.
        # Nobody should have to trust an automation they have never seen be
        # right.
        "level": LEVEL_PROPOSE,
        # What it aims for when it does act. Lowest cost reckons everything in
        # euros, which by itself already prefers using your own sun over
        # exporting it; "solar" insists on the sun even when buying would be
        # cheaper.
        "goal": GOAL_COST,
        # Warn when the connection is being pushed towards its limit. The
        # interval matters as much as the threshold: load swings across the
        # trigger point constantly, so without it one busy hour would send a
        # stream of notifications.
        "load_alert": {
            "enabled": False,
            "threshold_percent": 80,
            # notify service names without their domain, e.g. "mobile_app_sven".
            "targets": [],
            "min_interval_minutes": 30,
            # How long the load has to stay over the line before anything is
            # sent. An oven element or a motor starting produces a spike of a
            # second or two that no fuse minds and nobody can act on, and a
            # notification for it is exactly the kind people switch off. A
            # minute still leaves plenty of room: a fuse carrying a little over
            # its rating holds for the better part of an hour.
            "min_duration_seconds": 60,
        },
        # When an appliance may run. One entry per device, as a list rather
        # than a map keyed by device id: the storage prunes dictionaries
        # against these defaults, which would empty a free-form map on every
        # load. Nested dictionaries inside a list item are left alone, so the
        # shape of an entry is free.
        #
        # Three times, all optional and all meaning something different:
        # `not_before` is the earliest it may start, `start_by` the latest it
        # may start, `done_by` the moment it has to be finished. A customer who
        # only cares about one of them fills in one of them.
        #
        # At least one of the three is what turns "run this when power is
        # cheap" into a question with an answer. Without any of them the
        # cheapest moment is always later, so nothing would ever start.
        #
        # `per_day` swaps the single window for one per weekday, because
        # weekends are not weekdays.
        "schedules": [],
    },
    "devices": [],
    # Device ids the customer has released for steering right now: the
    # dishwasher is loaded and its door is shut, the car may charge. Kept as a
    # list rather than a map on purpose -- the storage prunes dictionaries
    # against these defaults, which would empty a free-form map on every load.
    #
    # It is state rather than configuration, but it belongs here all the same:
    # it has to survive a restart (a dishwasher stays loaded) and reach every
    # open panel over the same event.
    "ready_devices": [],
    # Which car is hanging on which charging point right now. State rather than
    # configuration, like `ready_devices`: it changes when somebody plugs in a
    # different car, it has to survive a restart, and whoever is standing in the
    # driveway is not an administrator. A list for the same reason as the rest:
    # storage.py prunes dictionaries against these defaults.
    "active_cars": [],
    "thresholds": {
        # Zelfbenutting in percent: below `low` is bad, above `high` is good.
        "self_use": {"low": 30, "high": 70},
        # Energy price in euro per kWh: below `low` is good, above `high` is bad.
        "price": {"low": 0.20, "high": 0.30},
    },
}
