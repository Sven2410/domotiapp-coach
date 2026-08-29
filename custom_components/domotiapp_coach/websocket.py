"""Websocket API the panel uses to read and write its settings.

The panel is a plain web component with no build step, so it talks to Home
Assistant over the connection HA already hands it. Reading is open to any signed
in user -- a customer needs the settings just to render the dashboard -- while
writing is admin-only, so a household member cannot silently repoint the meter.
"""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from . import report
from .const import (
    ALL_BRANDS,
    GOALS,
    LEVELS,
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
from .storage import async_get_store, schema_bijwerken


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
        vol.Optional("phases", default="three"): vol.In(["one", "three"]),
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
        vol.Optional("level"): vol.In(LEVELS),
        vol.Optional("goal"): vol.In(GOALS),
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
                        vol.Optional("this_hour"): _ENTITY,
                        vol.Optional("next_hour"): _ENTITY,
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
                vol.Optional("load_balancer"): bool,
            }
        ),
        vol.Optional("contract"): _schema(
            {
                vol.Optional("type"): vol.In([CONTRACT_FIXED, CONTRACT_DYNAMIC]),
                vol.Optional("netting"): bool,
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
        vol.Required("type"): "domotiapp_coach/device/schedule",
        vol.Required("device_id"): str,
        # Alleen wat er verandert wordt meegestuurd; de rest blijft staan.
        vol.Optional("enabled"): bool,
        vol.Optional("priority"): vol.In(["low", "mid", "high"]),
        vol.Optional("per_day"): bool,
        # Alle drie de tijden tegelijk, want `_WINDOW` vult een ontbrekende tijd
        # aan met een lege string en dat wist hem: een half venster sturen zou
        # de twee andere weggooien.
        vol.Optional("window"): _schema(dict(_WINDOW)),
        vol.Optional("days"): vol.All([_PLAN_DAY], vol.Length(max=7)),
    }
)
@websocket_api.async_response
async def async_set_device_schedule(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Het schema van één apparaat, vanaf zijn eigen kaart in Overzicht.

    Sinds 27-08-2026 staan de schema's niet meer in Strategie. De schuif en de
    voorrang staan op de kaart zelf, en de knop Schema opent een pop-up met de
    tijden en het per-dag-werk. Alles wat over één apparaat gaat komt dus langs
    dit commando.

    Uit betekent dat de coach zelf bepaalt wanneer er gedraaid wordt en puur
    naar het gunstigste moment kijkt: `_days` in coach.py slaat een schema dat
    uit staat over, waarna in planner.py de hele klaar-tijdtak vervalt.

    Geen beheerderswerk, om dezelfde reden als de twee commando's hieronder: wie
    weet dat de vaatwasser vanavond klaar moet zijn, is degene die hem heeft
    ingeruimd.

    Eén apparaat en verder niets, en alleen de velden die meegestuurd zijn. De
    nieuwe lijst wordt hier uitgerekend en niet door het paneel meegestuurd, zodat
    een dashboard dat een uur openstaat niet ongemerkt terugdraait wat er
    ondertussen op een telefoon veranderd is.
    """
    store = async_get_store(hass)
    settings = await store.async_load()
    strategy = schema_bijwerken(
        settings.get("strategy"),
        msg["device_id"],
        enabled=msg.get("enabled"),
        priority=msg.get("priority"),
        per_day=msg.get("per_day"),
        window=msg.get("window"),
        days=msg.get("days"),
    )
    settings = await store.async_save({"strategy": strategy})
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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "domotiapp_coach/device/soc",
        vol.Required("device_id"): str,
        vol.Required("car"): str,
        # None wist de opgave weer.
        vol.Required("percent"): vol.Any(None, vol.All(vol.Coerce(float), vol.Range(0, 100))),
    }
)
@websocket_api.async_response
async def async_set_car_soc(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Doorgeven hoe vol de auto is die eraan hangt.

    Net als het kiezen van een auto geen beheerderswerk: degene die het weet is
    degene die naast de auto staat.

    De meterstand van de laadpaal wordt er hier bij gezet en niet door het
    paneel meegestuurd. Daarmee telt de coach zelf verder zodra er stroom loopt,
    en hoeft er hooguit één keer per sessie iets ingevuld te worden. Dat het hier
    gebeurt en niet in de browser is met opzet: de stand van dat moment is een
    feit van de installatie, geen invoer van een scherm dat een minuut oud kan zijn.
    """
    store = async_get_store(hass)
    settings = await store.async_load()

    device = next(
        (
            row
            for row in (settings.get("devices") or [])
            if isinstance(row, dict) and row.get("id") == msg["device_id"]
        ),
        None,
    )
    meter = None
    if device:
        # Het merkveld eerst en anders de Energieteller. Die twee vroegen om
        # dezelfde sensor, en alleen Easee heeft dat merkveld; zie `_teller` in
        # coach.py voor het hele verhaal.
        entiteit = (device.get("entities") or {}).get("lifetime_energy") or device.get(
            "energy_entity"
        )
        state = hass.states.get(entiteit or "")
        if state is not None:
            try:
                meter = float(state.state)
            except (TypeError, ValueError):
                meter = None

    rows = [
        row
        for row in (settings.get("car_soc") or [])
        if isinstance(row, dict) and row.get("device") != msg["device_id"]
    ]
    if msg["percent"] is not None:
        rows.append(
            {
                "device": msg["device_id"],
                "car": msg["car"],
                "percent": float(msg["percent"]),
                "meter": meter,
            }
        )

    settings = await store.async_save({"car_soc": rows})
    hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": settings})
    connection.send_result(msg["id"], settings)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "domotiapp_coach/history/quarters",
        vol.Required("entity_ids"): [str],
        vol.Required("start"): str,
        vol.Required("end"): str,
    }
)
@websocket_api.async_response
async def async_history_quarters(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Het laagste, de piek en het gemiddelde per kwartier, uit de eigen opslag.

    De recorder van Home Assistant bewaart fijner dan een uur maar tien dagen.
    Dit gaat twee jaar terug, en dat is precies waarvoor `archive.py` bestaat.
    """
    from .archive import async_get_archive

    start = dt_util.parse_datetime(msg["start"])
    einde = dt_util.parse_datetime(msg["end"])
    if start is None or einde is None:
        connection.send_error(msg["id"], "invalid_format", "start of end is geen tijd")
        return

    rijen = await async_get_archive(hass).async_lees(
        msg["entity_ids"],
        dt_util.as_local(start).replace(tzinfo=None),
        dt_util.as_local(einde).replace(tzinfo=None),
    )
    connection.send_result(msg["id"], rijen)


@websocket_api.websocket_command({vol.Required("type"): "domotiapp_coach/coach/state"})
@callback
def async_coach_state(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """What the coach decided the last time it looked.

    The panel follows along on the event bus after this, but a dashboard that
    was just opened would otherwise stare at nothing for up to a minute.
    """
    from .coach import async_get_coach

    connection.send_result(msg["id"], async_get_coach(hass).state)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "domotiapp_coach/coach/approve",
        vol.Required("device_id"): str,
        vol.Required("approve"): bool,
    }
)
@callback
def async_coach_approve(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Say yes to what the coach proposed, for this session.

    Not admin-only: agreeing that the car may charge tonight is a decision of
    whoever is standing in the driveway, exactly like releasing a dishwasher.
    """
    from .coach import async_get_coach

    coach = async_get_coach(hass)
    if msg["approve"]:
        coach.async_approve(msg["device_id"])
    else:
        coach.async_withdraw(msg["device_id"])
    connection.send_result(msg["id"], coach.state)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "domotiapp_coach/report/store",
        vol.Required("pdf"): str,
        vol.Required("filename"): str,
    }
)
@callback
def async_store_report(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Neem een rapport aan en zeg waar het op te halen is.

    Het paneel maakt de pdf zelf en zou hem in de browser kunnen aanbieden, maar
    een webweergave kan een `blob:` niet downloaden en levert dan een bestand op
    dat niet open gaat. Dus komt hij hierlangs en gaat hij als een gewone
    download naar buiten. Zie report.py.

    Niet alleen voor beheerders: wie het rapport mag zien, mag het bewaren.
    """
    try:
        pdf = base64.b64decode(msg["pdf"], validate=True)
    except (ValueError, binascii.Error):
        connection.send_error(msg["id"], "invalid_format", "Dit is geen leesbaar rapport.")
        return

    if not pdf.startswith(b"%PDF-"):
        connection.send_error(msg["id"], "invalid_format", "Dit is geen pdf.")
        return
    if len(pdf) > report.MAX_BYTES:
        connection.send_error(msg["id"], "too_large", "Dit rapport is te groot.")
        return

    # De naam komt uit de browser en belandt in een kopregel, dus alles wat daar
    # een tweede regel van zou kunnen maken gaat eruit.
    filename = re.sub(r'[\r\n"\\]', "", msg["filename"]).strip() or "rapport.pdf"

    connection.send_result(
        msg["id"], {"url": report.async_put(hass, pdf, filename[:120])}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "domotiapp_coach/coach/boost",
        vol.Required("device_id"): str,
        vol.Required("boost"): bool,
    }
)
@callback
def async_coach_boost(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Snelladen aan of uit zetten.

    Niet alleen voor beheerders. Wie eerder weg moet dan gepland is degene die
    in de auto stapt, en die staat meestal niet als beheerder in Home Assistant.
    Het gaat bovendien om deze ene sessie: de kabel eruit en het staat weer uit.
    """
    from .coach import async_get_coach

    async_get_coach(hass).async_boost(msg["device_id"], msg["boost"])
    connection.send_result(msg["id"], {"boost": msg["boost"]})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "domotiapp_coach/coach/pause",
        vol.Required("device_id"): str,
        vol.Required("paused"): bool,
    }
)
@callback
def async_coach_pause(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Het laden met de hand stilzetten of hervatten.

    Om dezelfde reden geen beheerdersrecht als snelladen: dit is iets van de
    bewoner die bij de auto staat. En net als een akkoord duurt het precies zo
    lang als de kabel erin zit.
    """
    from .coach import async_get_coach

    async_get_coach(hass).async_pause(msg["device_id"], msg["paused"])
    connection.send_result(msg["id"], {"paused": msg["paused"]})


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the panel's websocket commands."""
    websocket_api.async_register_command(hass, async_store_report)
    websocket_api.async_register_command(hass, async_get_settings)
    websocket_api.async_register_command(hass, async_set_settings)
    websocket_api.async_register_command(hass, async_set_device_ready)
    websocket_api.async_register_command(hass, async_set_strategy)
    websocket_api.async_register_command(hass, async_set_device_schedule)
    websocket_api.async_register_command(hass, async_set_active_car)
    websocket_api.async_register_command(hass, async_set_car_soc)
    websocket_api.async_register_command(hass, async_history_quarters)
    websocket_api.async_register_command(hass, async_coach_state)
    websocket_api.async_register_command(hass, async_coach_approve)
    websocket_api.async_register_command(hass, async_coach_boost)
    websocket_api.async_register_command(hass, async_coach_pause)
