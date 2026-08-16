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
    ALL_BRANDS,
    CONTRACT_DYNAMIC,
    CONTRACT_FIXED,
    DEVICE_TYPES,
    DYNAMIC_ALL_IN,
    DYNAMIC_MARKET,
    EVENT_SETTINGS_UPDATED,
    GRID_MODE_SIGNED,
    GRID_MODE_SPLIT,
    PRICE_INTERVAL_HOUR,
    PRICE_INTERVAL_QUARTER,
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

# One car that charges at this point. A household has one or two, and a guest
# is not one of them: that is a fixed profile the panel offers by itself.
_CAR = _schema(
    {
        vol.Required("id"): str,
        vol.Optional("name", default=""): str,
        # Battery size in kWh. What makes it possible to work out how many hours
        # are still needed, together with what the customer says is left in it.
        vol.Optional("capacity_kwh", default=0): vol.All(
            vol.Coerce(float), vol.Range(0, 500)
        ),
        # Whether the car charges on one phase, on three, or can do both. It
        # decides the floor: six amps is 1,4 kW on one phase and 4,1 on three.
        vol.Optional("phases", default="three"): vol.In(["one", "three", "both"]),
        # Some cars stop at 16 A however thick the cable is.
        vol.Optional("max_amps", default=0): vol.All(vol.Coerce(float), vol.Range(0, 100)),
        # The car's own state of charge, when Home Assistant knows it. With it
        # the coach works out how much still has to go in; without it the
        # customer says so, and without that it simply charges the cheapest
        # hours until the car stops by itself.
        vol.Optional("soc_entity", default=""): _ENTITY,
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
        # An energy counter for this device, in kWh. Optional: without one the
        # history is worked out from the average power, which is close enough
        # for a report but not a meter reading.
        vol.Optional("energy_entity", default=""): _ENTITY,
        # Types that have brands (chargers, dishwashers), "" until one is
        # picked. Which brands belong to which type is the panel's business.
        vol.Optional("brand", default=""): vol.In([*ALL_BRANDS, ""]),
        # Whether the coach may steer this device once steering exists. Plenty
        # of appliances sit on a smart plug that can only measure, so this is a
        # choice per device rather than a property of the type.
        vol.Optional("controllable", default=False): bool,
        # Whatever else the brand offers, keyed by the panel's own field names.
        # Free-form on purpose: adding a brand should not need a schema change
        # here as well as in the panel.
        vol.Optional("entities", default=dict): {vol.Match(r"^[a-z0-9_]+$"): _ENTITY},
        # The Home Assistant device this thing is, when its brand is steered
        # through a service that wants a device rather than an entity -- Easee's
        # action_command is one.
        vol.Optional("device_id", default=""): str,
        # What to send for start, stop, pause and resume. The words differ per
        # brand and even per firmware, so they are typed in rather than baked in.
        vol.Optional("actions", default=dict): {vol.Match(r"^[a-z0-9_]+$"): str},
        # The cars that charge here, for the device types that have them.
        vol.Optional("cars", default=list): vol.All([_CAR], vol.Length(max=8)),
    }
)

# A time of day, or "" for "the customer does not care about this one" -- which
# is not the same as a schedule that is switched off.
_TIME = vol.Any("", vol.Match(r"^([01]\d|2[0-3]):[0-5]\d$"))

_WINDOW = {
    vol.Optional("not_before", default=""): _TIME,
    vol.Optional("start_by", default=""): _TIME,
    vol.Optional("done_by", default=""): _TIME,
}

# One weekday of a per-day schedule. 0 is Monday, the way a week is written
# down here.
_PLAN_DAY = _schema(
    {
        vol.Required("day"): vol.All(vol.Coerce(int), vol.Range(0, 6)),
        vol.Optional("enabled", default=True): bool,
        **_WINDOW,
    }
)

# When an appliance may run, per device.
_SCHEDULE = _schema(
    {
        vol.Required("device"): str,
        vol.Optional("enabled", default=False): bool,
        vol.Optional("per_day", default=False): bool,
        # Who goes first when two appliances want the same room on the
        # connection. Not a schedule, but it belongs with one: both answer
        # "when may this run", and splitting them over two screens would mean
        # setting up one appliance in two places.
        vol.Optional("priority", default="mid"): vol.In(["low", "mid", "high"]),
        vol.Optional("window"): _schema(dict(_WINDOW)),
        vol.Optional("days", default=list): vol.All([_PLAN_DAY], vol.Length(max=7)),
    }
)

_STRATEGY = _schema(
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
        vol.Optional("schedules"): [_SCHEDULE],
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
                vol.Optional("solar_forecast"): _schema(
                    {
                        vol.Optional("remaining_today"): _ENTITY,
                        vol.Optional("tomorrow"): _ENTITY,
                        vol.Optional("peak_today"): _ENTITY,
                    }
                ),
                vol.Optional("meters"): _schema(
                    {
                        vol.Optional("solar_total"): _ENTITY,
                        vol.Optional("import_low"): _ENTITY,
                        vol.Optional("import_high"): _ENTITY,
                        vol.Optional("export_low"): _ENTITY,
                        vol.Optional("export_high"): _ENTITY,
                        vol.Optional("gas_enabled"): bool,
                        vol.Optional("gas"): _ENTITY,
                    }
                ),
            }
        ),
        vol.Optional("strategy"): _STRATEGY,
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
                        vol.Optional("interval"): vol.In(
                            [PRICE_INTERVAL_HOUR, PRICE_INTERVAL_QUARTER]
                        ),
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
        vol.Optional("ready_devices"): [str],
        vol.Optional("active_cars"): [
            _schema({vol.Required("device"): str, vol.Required("car"): str})
        ],
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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "domotiapp_coach/device/ready",
        vol.Required("device_id"): str,
        vol.Required("ready"): bool,
    }
)
@websocket_api.async_response
async def async_set_device_ready(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Release a device for steering, or take that release back.

    Deliberately not admin-only, unlike everything else that writes here. This
    is the customer saying "the dishwasher is loaded and shut" -- the one person
    who can know that is whoever is standing in the kitchen, and they are not
    the installer.

    The new list is worked out here rather than sent by the panel, so a stale
    dashboard cannot undo somebody else's release by handing back the list it
    happened to be holding.
    """
    store = async_get_store(hass)
    settings = await store.async_load()

    ready = set(settings.get("ready_devices") or [])
    if msg["ready"]:
        ready.add(msg["device_id"])
    else:
        ready.discard(msg["device_id"])

    settings = await store.async_save({"ready_devices": sorted(ready)})
    hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": settings})
    connection.send_result(msg["id"], settings)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "domotiapp_coach/strategy/set",
        vol.Required("strategy"): _STRATEGY,
    }
)
@websocket_api.async_response
async def async_set_strategy(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Save the strategy, admin or not.

    Everything else about this installation is the installer's: which sensor
    measures what, how heavy the connection is, what the contract costs. The
    strategy is not. When the dishwasher has to be finished, which appliance
    goes first and who gets a notification are decisions of whoever lives in the
    house, and they are usually not an administrator in Home Assistant.

    Only this one section is accepted here. Everything else still goes through
    the admin-only command.
    """
    settings = await async_get_store(hass).async_save({"strategy": msg["strategy"]})
    hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": settings})
    connection.send_result(msg["id"], settings)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "domotiapp_coach/device/car",
        vol.Required("device_id"): str,
        vol.Required("car"): str,
    }
)
@websocket_api.async_response
async def async_set_active_car(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Say which car is on this charging point now.

    Not admin-only, for the same reason releasing a dishwasher is not: the
    person plugging a car in is whoever is standing in the driveway.

    The new list is worked out here rather than sent by the panel, so a
    dashboard that has been open all afternoon cannot undo a change somebody
    made on their phone five minutes ago.
    """
    store = async_get_store(hass)
    settings = await store.async_load()

    cars = [
        entry
        for entry in (settings.get("active_cars") or [])
        if isinstance(entry, dict) and entry.get("device") != msg["device_id"]
    ]
    if msg["car"]:
        cars.append({"device": msg["device_id"], "car": msg["car"]})

    settings = await store.async_save({"active_cars": cars})
    hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": settings})
    connection.send_result(msg["id"], settings)


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the panel's websocket commands."""
    websocket_api.async_register_command(hass, async_get_settings)
    websocket_api.async_register_command(hass, async_set_settings)
    websocket_api.async_register_command(hass, async_set_device_ready)
    websocket_api.async_register_command(hass, async_set_strategy)
    websocket_api.async_register_command(hass, async_set_active_car)
