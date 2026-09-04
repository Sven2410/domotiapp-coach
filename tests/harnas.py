"""Home Assistant, net genoeg om coach.py in te laden en te laten draaien.

Wat hier staat is geen Home Assistant maar de handvol namen die coach.py,
monitor.py en storage.py eruit gebruiken, nagemaakt. Het is gedeeld tussen de
proeven op de bedrading (`test_coach.py`) en het virtuele huis (`virtueel.py`),
zodat die twee nooit een andere Home Assistant kunnen zien.

Importeren heeft een bijwerking: `sys.modules` krijgt de nagemaakte pakketten
en de modules van de coach worden ingeladen. Dat hoort zo; het is precies wat
de proeven vroeger zelf bovenaan deden.
"""

import asyncio
import datetime as dt
import importlib.util
import pathlib
import sys
import tempfile
import types

# Home Assistant draait op een verse Python en `coach.py` gebruikt dingen die
# daarbij horen, zoals `asyncio.timeout` (3.11). Apple levert bij zijn
# ontwikkelaarsgereedschappen nog een 3.9 mee, en die geeft midden in een proef
# een AttributeError die eruitziet als een bug in de coach. Dat is het niet.
if sys.version_info < (3, 11):
    raise SystemExit(
        "Deze proeven willen Python 3.11 of nieuwer; hier draait "
        f"{sys.version_info.major}.{sys.version_info.minor} "
        f"vanuit {sys.executable}. "
        "Op macOS: `brew install python`, daarna een nieuw terminalvenster. "
        "Home Assistant zelf draait op 3.13, dus de coach ziet een 3.9 nooit."
    )


# De code die beproefd wordt, gevonden vanaf dit bestand. Geen absoluut pad,
# want deze repo staat op de ene machine in C:\dev en op de andere in ~/dev.
BRON = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "domotiapp_coach"

# --- Home Assistant, net genoeg om te draaien ------------------------------

ha = types.ModuleType("homeassistant")
core = types.ModuleType("homeassistant.core")


class HomeAssistant:  # noqa: D101
    pass


core.HomeAssistant = HomeAssistant
core.callback = lambda func: func


class Event:  # noqa: D101
    pass


class State:  # noqa: D101
    pass


# `monitor.py` leest deze twee alleen als typenaam, maar zonder dat ze bestaan
# laadt de module niet.
core.Event = Event
core.State = State

excepties = types.ModuleType("homeassistant.exceptions")


class ServiceNotFound(Exception):  # noqa: D101
    pass


excepties.ServiceNotFound = ServiceNotFound

helpers = types.ModuleType("homeassistant.helpers")
helpers.__path__ = []
start = types.ModuleType("homeassistant.helpers.start")
start.async_at_started = lambda *a, **k: (lambda: None)
gebeurtenis = types.ModuleType("homeassistant.helpers.event")
gebeurtenis.async_track_state_change_event = lambda *a, **k: (lambda: None)
gebeurtenis.async_track_time_interval = lambda *a, **k: (lambda: None)
gebeurtenis.async_call_later = lambda *a, **k: (lambda: None)
opslag = types.ModuleType("homeassistant.helpers.storage")


class Store:  # noqa: D101
    def __init__(self, *a, **k):
        self._data = None

    async def async_load(self):
        return self._data

    async def async_save(self, data):
        self._data = data


opslag.Store = Store

util = types.ModuleType("homeassistant.util")
dtutil = types.ModuleType("homeassistant.util.dt")
dtutil.now = lambda: dt.datetime.now()
dtutil.utcnow = lambda: dt.datetime.now(dt.timezone.utc)
dtutil.as_local = lambda moment: moment


def _lees_tijd(waarde):
    """Zoals `dt_util.parse_datetime` van Home Assistant: die wil tekst.

    Op iets anders dan een string geeft de echte een TypeError. Dat verschil
    stond hier weggepoetst met `except TypeError: return None`, en daarmee was
    dit harnas vergevingsgezinder dan de werkelijkheid. Een `datetime` in een
    attribuut kwam er zo ongemerkt doorheen, en juist daarop liep het bij Van
    den Dam op 29-08-2026 stuk: de hele prijslijst sneuvelde en de coach zei dat
    er geen prijzen binnenkwamen.
    """
    if not isinstance(waarde, str):
        raise TypeError(f"parse_datetime wil tekst, kreeg {type(waarde).__name__}")
    try:
        return dt.datetime.fromisoformat(waarde)
    except ValueError:
        return None


dtutil.parse_datetime = _lees_tijd
util.dt = dtutil

sys.modules.update({
    "homeassistant": ha,
    "homeassistant.core": core,
    "homeassistant.exceptions": excepties,
    "homeassistant.helpers": helpers,
    "homeassistant.helpers.event": gebeurtenis,
    "homeassistant.helpers.start": start,
    "homeassistant.helpers.storage": opslag,
    "homeassistant.util": util,
    "homeassistant.util.dt": dtutil,
})

# --- het pakket zelf, zonder __init__.py te draaien ------------------------

pakket = types.ModuleType("domotiapp_coach")
pakket.__path__ = [str(BRON)]
sys.modules["domotiapp_coach"] = pakket


def laad(naam):
    spec = importlib.util.spec_from_file_location(
        f"domotiapp_coach.{naam}", BRON / f"{naam}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"domotiapp_coach.{naam}"] = module
    spec.loader.exec_module(module)
    return module


laad("const")
planner = laad("planner")
storage = laad("storage")
coachmod = laad("coach")
monitormod = laad("monitor")

# --- een huis om in te meten ------------------------------------------------

class Staat:
    """Een toestand, met attributen als de proef die nodig heeft.

    Een gewone waarde blijft een string, zoals overal hierboven. Een prijslijst
    zit bij Home Assistant in de attributen en niet in de toestand zelf, en
    daarvoor mag een waarde ook een dict zijn met `state` en `attributes`.
    """

    def __init__(self, waarde, last_updated=None):
        if isinstance(waarde, dict):
            self.state = waarde.get("state", "")
            self.attributes = dict(waarde.get("attributes") or {})
        else:
            self.state = waarde
            self.attributes = {}
        # Home Assistant zet dit op elke toestand en de coach leest het: twee
        # sensoren van dezelfde paal die niet tegelijk gemeld hebben zeggen
        # samen niets over het aantal fasen. Zonder dit veld hier was het harnas
        # weer vergevingsgezinder dan de werkelijkheid.
        self.last_updated = last_updated or dt.datetime.now(dt.timezone.utc)
        self.last_changed = self.last_updated


class Staten:
    def __init__(self, waarden):
        self.waarden = dict(waarden)
        self.stempels = {}

    def get(self, entity_id):
        waarde = self.waarden.get(entity_id)
        if waarde is None:
            return None
        return Staat(waarde, self.stempels.get(entity_id))

    def zet(self, entity_id, waarde, last_updated=None):
        self.waarden[entity_id] = waarde
        if last_updated is not None:
            self.stempels[entity_id] = last_updated
        else:
            self.stempels.pop(entity_id, None)

    def verouder(self, entity_id, seconden):
        """Deze sensor deed er zoveel seconden geleden voor het laatst iets."""
        self.stempels[entity_id] = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
            seconds=seconden
        )


class Diensten:
    def __init__(self):
        self.verstuurd = []

    async def async_call(self, domein, dienst, data, blocking=False):
        self.verstuurd.append((domein, dienst, dict(data)))


class Bus:
    def __init__(self):
        self.gebeurtenissen = []

    def async_fire(self, soort, data):
        self.gebeurtenissen.append((soort, data))


class NepConfig:
    """Net genoeg van `hass.config` voor het archief.

    Het archief legt een sqlite-bestand aan naast de configuratie. In de proeven
    mag dat nergens landen, dus wijst dit naar een map die weggegooid mag worden.
    """

    def __init__(self):
        self.config_dir = tempfile.mkdtemp(prefix="domotiapp-proef-")

    def path(self, *delen):
        return str(pathlib.Path(self.config_dir, *delen))


class NepHass:
    def __init__(self, waarden):
        self.config = NepConfig()
        self.states = Staten(waarden)
        self.services = Diensten()
        self.bus = Bus()
        self.data = {}
        self.taken = []

    async def async_add_executor_job(self, func, *args):
        """Zoals Home Assistant het doet, maar zonder aparte draad."""
        return func(*args)

    def async_create_task(self, coro):
        """Zoals HA het doet: erbij zetten en doorgaan.

        In Home Assistant draait er altijd een lus; hier soms niet, want ik roep
        een knop ook wel eens buiten een ronde aan. Dan wordt het werk bewaard
        en bij de volgende ronde alsnog gedaan.
        """
        try:
            taak = asyncio.ensure_future(coro)
        except RuntimeError:
            self.taken.append(coro)
            return None
        self.taken.append(taak)
        return taak

    async def afmaken(self):
        """Het uitgestelde werk alsnog doen."""
        wachtend, self.taken = self.taken, []
        for werk in wachtend:
            await werk


class NepStore:
    """De instellingen, zoals storage.py ze zou bewaren."""

    def __init__(self, instellingen):
        self.instellingen = instellingen

    async def async_load(self):
        return self.instellingen

    async def async_save(self, changes):
        self.instellingen.update(changes)
        return self.instellingen
