"""The part of the coach that actually watches and acts.

This runs in Home Assistant, on a timer, whether or not anybody has the panel
open. That is the whole reason it is here rather than in the browser: a car has
to start charging at two in the morning, and at two in the morning nobody is
looking at a dashboard. A restart must not matter either, so nothing is kept
that cannot be read back from the installation itself.

The thinking is next door in planner.py, which knows nothing about Home
Assistant and can therefore be run against a whole day of real history before
anything is switched. This file only reads sensors, calls services and keeps
the two apart.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceNotFound
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    NETTING_ENDS,
    CHARGER_CONTROL,
    DOMAIN,
    EVENT_DECISION,
    EVENT_SETTINGS_UPDATED,
    LEVEL_PROPOSE,
    LEVEL_STEER,
    PHASE_START_AMPS,
)
from .planner import (
    BALANCER_MARGIN_AMPS,
    CHARGE_EFFICIENCY,
    FUSE_MARGIN_AMPS,
    FUSE_MARGIN_SHARE,
    Car,
    Charger,
    DayWindow,
    Decision,
    Grid,
    Sun,
    Tariff,
    Window,
    amps_for,
    decide,
    FULL_PERCENT,
    held_back,
    resolve_window,
    should_send,
)
from .storage import async_get_store
from .units import to_kwh, to_watts

_LOGGER = logging.getLogger(__name__)

# How often to think. A minute is often enough to catch a kettle before a fuse
# minds, and rare enough that a car is never re-commanded into giving up.
INTERVAL = timedelta(seconds=60)

# How long to wait for the charger to confirm a new limit before starting.
CONFIRM_SECONDS = 15

# How often to prod a charging point that is not doing what was asked. Some of
# the reasons it might not are outside the coach's reach altogether: a load
# balancer holding the session, a car that has decided it is full, a brand with
# its own idea of when a schedule applies. Repeating the command every minute
# changes none of them and only fills a log, but never repeating it at all means
# a car stands still all night because the decision happened not to change.
NUDGE_INTERVAL = timedelta(minutes=5)

# Over hoeveel tijd het overschot wordt gladgestreken voor er omhoog wordt
# gestuurd. Drie minuten is lang genoeg om een wolk te laten passeren en kort
# genoeg om een opklaring niet te missen.
#
# Uitdrukkelijk een tijd en geen aantal metingen. Dat was het eerst wel, en dat
# klopte zolang er precies één ronde per minuut liep. Sinds een kabel of een
# statuswissel ook een ronde start, kunnen drie metingen binnen drie seconden
# vallen, en dan hangt een meting van vlak vóór het inpluggen nog in het venster
# en ziet de coach geen zon terwijl het dak vol ligt.
SMOOTH_WINDOW = timedelta(minutes=3)

# Hoe ruim voor het einde een lopende pauze opnieuw wordt weggeschreven. Vijf
# minuten is vier ronden speling, dus een gemiste ronde laat de auto niet
# onbedoeld aanslaan.
PAUSE_REFRESH = timedelta(minutes=5)

# De uitkomsten waarbij een pauze blijft staan tot de coach hem zelf weghaalt.
# Bij een volle aansluiting zou aflopen betekenen dat de paal terugvalt op zijn
# eigen maximum terwijl het huis al te veel trekt, en bij een pauze van de
# bewoner zou het betekenen dat zijn eigen opdracht na een tijdje vervalt.
# Overal elders is aflopen juist het goede antwoord: dan laadt de auto door, en
# duur is beter dan leeg.
FOREVER_RULES = frozenset({"no-room", "user-hold"})

# En de uitkomsten waarbij er helemaal niets naar de paal gaat. Zonder kabel valt
# er niets tegen te houden, en bij een volle auto zou een 0 die blijft staan de
# volgende auto in de weg zitten.
NO_WRITE_RULES = frozenset({"disconnected", "complete"})

# Hoe lang het verslag wacht op een accustand die bij deze laadbeurt hoort.
# Een auto meldt zijn percentage niet op commando: Svens Ford stopte op
# 25-08-2026 om 14:44 op 80% terwijl de app nog 70% zei, en werkte pas ruim een
# minuut later bij. De melding was toen al de deur uit met het oude getal, en
# juist bij een auto die zelf op 80% stopt is dat percentage het interessantste
# van het hele bericht. Drie minuten is ruim genoeg voor die ene verversing en
# kort genoeg dat het bericht nog bij de laadbeurt hoort. Komt er niets, dan
# gaat het verslag alsnog: te laat melden is erger dan een getal dat een ronde
# oud is.
SOC_SETTLE = timedelta(minutes=3)

# Hoe vaak de waarschuwing terugkomt dat een eigen pauze de klaar-tijd gaat
# kosten. Sven op 26-08-2026: de pauze zelf blijft winnen, want het is zijn huis
# en zijn knop, maar één keer waarschuwen is te weinig. Wie het bericht om elf
# uur 's avonds wegveegt en om zeven uur naar een lege auto loopt, is niet
# geholpen.
#
# Een uur, en dat is een keuze van mij en niet een meting: kort genoeg om er nog
# iets aan te kunnen doen, lang genoeg om geen gezeur te worden. Hij komt alleen
# terug zolang het risico er werkelijk is, en houdt dus vanzelf op zodra de
# pauze eraf gaat, de klaar-tijd verzet wordt of de kabel eruit komt.
PAUSE_WARN_AGAIN = timedelta(hours=1)

# Hoe lang een ronde hoogstens mag duren. Ruim boven wat hij nodig heeft (de
# bevestiging van een limiet duurt hooguit een seconde of vijftien per apparaat)
# en ruim onder de ronde zelf, zodat een vastgelopen opdracht de coach niet stil
# kan leggen. Zie de reden bij het afbreken zelf.
ROUND_TIMEOUT = timedelta(seconds=45)

# Hoe vaak de coach nakijkt of hij zelf nog draait, en na hoe lang stilte hij
# daar een melding over stuurt. Een aparte klok met opzet: gaat er iets mis in de
# ronde zelf, dan moet degene die dat opmerkt er niet in vastzitten.
WATCHDOG_INTERVAL = timedelta(minutes=5)
WATCHDOG_SILENCE = timedelta(minutes=10)

# Hoe lang een akkoord, snelladen of een pauze blijft gelden zonder dat de coach
# ernaar heeft kunnen kijken. Twaalf uur dekt een nacht en een werkdag, en is
# kort genoeg dat een opdracht van eergisteren nooit op de auto van vandaag
# terechtkomt. Het uittrekken van de kabel wist ze altijd meteen; dit geldt
# alleen voor wat er tijdens een herstart gebeurd kan zijn.
SESSION_MEMORY = timedelta(hours=12)

# Hoe lang de wekstroom blijft staan. Een minuut, dus in de praktijk één ronde,
# maar uitgedrukt in tijd omdat een statuswissel van de laadpaal ook een ronde
# start: op ronden geteld stond de wekstroom er soms maar drie seconden.
WAKE_WINDOW = timedelta(seconds=60)

# Hoe vaak een te hoge fasestroom hoogstens een extra ronde mag opleveren. Een
# meter meldt zich elke seconde, en een huis dat vol zit doet dat een tijdlang
# achter elkaar; zonder deze grens zou de coach zichzelf de hele avond op hol
# laten brengen. Vijftien seconden is vier keer sneller dan de klok en rustig
# genoeg voor de laadpaal.
HURRY_INTERVAL = timedelta(seconds=15)


def _number(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """A sensor read as a plain number, or None when it says nothing useful."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unknown", "unavailable", ""):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _unit(hass: HomeAssistant, entity_id: str | None) -> str | None:
    """De eenheid die deze entiteit zelf opgeeft."""
    state = hass.states.get(entity_id) if entity_id else None
    return None if state is None else state.attributes.get("unit_of_measurement")


def _watts(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Een vermogenssensor in watt, wat hij zichzelf ook noemt.

    Alles wat vermogen is gaat hierlangs en niet langs `_number`. Zie
    `units.py` voor waarom dat een klant een laadbeurt kon kosten.
    """
    return to_watts(_number(hass, entity_id), _unit(hass, entity_id))


def _kwh(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Een energiesensor in kilowattuur, wat hij zichzelf ook noemt."""
    return to_kwh(_number(hass, entity_id), _unit(hass, entity_id))


def _tijdstip(waarde: Any) -> datetime | None:
    """Een tijdstip uit een attribuut, of het nu tekst is of al een datetime.

    Een integratie mag in een attribuut zetten wat hij wil, en een `datetime`
    komt daar net zo vaak in voor als een ISO-string. Over de API van Home
    Assistant is dat verschil niet te zien, want daar wordt alles tot tekst
    geserialiseerd; binnen HA staat het echte object er nog.

    `dt_util.parse_datetime` wil alleen tekst en geeft op een `datetime` een
    TypeError. Die viel in `_slots` stilletjes weg in de `except`, waardoor er
    per blok een regel werd overgeslagen zonder spoor in enig logboek. Bij Van
    den Dam sneuvelden op 29-08-2026 zo alle 24 uurblokken tegelijk en zei de
    coach dat er geen prijzen binnenkwamen, terwijl zijn sensor gewoon gevuld
    was. Hij laadde daardoor op vol vermogen van het net terwijl hij op de zon
    had horen te wachten.
    """
    if isinstance(waarde, datetime):
        return waarde
    if isinstance(waarde, str):
        return dt_util.parse_datetime(waarde)
    return None


def _text(hass: HomeAssistant, entity_id: str | None) -> str:
    """A sensor read as its raw state, lower-cased for comparing."""
    if not entity_id:
        return ""
    state = hass.states.get(entity_id)
    return "" if state is None else str(state.state).lower()


def _wanneer(now: datetime, moment: datetime) -> str:
    """"06:00" of "morgen om 06:00", zodat een tijdstip niet twee dingen kan zijn."""
    if moment.date() == now.date():
        return f"{moment:%H:%M}"
    if moment.date() == (now + timedelta(days=1)).date():
        return f"morgen om {moment:%H:%M}"
    dagen = ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag")
    return f"{dagen[moment.weekday()]} om {moment:%H:%M}"


def _time(value: str | None) -> time | None:
    """"07:00" as a time, or None."""
    if not value:
        return None
    try:
        hour, minute = value.split(":")
        return time(int(hour), int(minute))
    except (ValueError, AttributeError):
        return None


class ChargerCoach:
    """Watches every steerable charging point and acts on what it sees."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up without touching anything yet."""
        self.hass = hass
        self._cancel = None
        # What we last decided per device, so a charger is not re-commanded for
        # a fraction of an amp.
        self._last: dict[str, Decision] = {}
        # When the session we started began. Not persisted on purpose: after a
        # restart the charger itself says whether it is charging, and treating
        # that as "just started" only costs a few minutes of patience.
        self._since: dict[str, datetime] = {}
        # The latest decision per device, for the panel to ask after.
        self.state: dict[str, dict[str, Any]] = {}
        # Devices the customer said yes to. Only meaningful at "propose", and
        # it lasts exactly one session: pull the cable and the coach is back to
        # asking. Somebody who agreed to one charge did not agree to every
        # charge from now on.
        self._approved: set[str] = set()
        # When a charging point that was not following was last prodded.
        self._nudged: dict[str, datetime] = {}
        # De laatste metingen van het overschot, per apparaat, om op te dempen.
        self._zon: dict[str, list[tuple[datetime, float]]] = {}
        # Wie er op snelladen staat. Net als een akkoord niet bewaard over een
        # herstart heen en afgelopen zodra de kabel eruit gaat: snelladen is
        # iets voor nu, niet iets wat stilletjes blijft staan.
        self._boost: set[str] = set()
        # En wie er met de hand op pauze staat. Zelfde levensduur, tegengestelde
        # bedoeling.
        self._paused: set[str] = set()
        # Hoeveel ronden een sessie al tegen de ladder in wordt aangehouden.
        self._holding: dict[str, int] = {}
        # Of de wekpoging van deze sessie nog openstaat. Eén per sessie, dus
        # zodra hij gedaan is blijft dit staan tot de kabel eruit gaat.
        self._woken: set[str] = set()
        # Sinds wanneer er stroom wordt aangeboden zonder dat de auto iets
        # afneemt. Daarmee weet de kaart het verschil tussen "begint zo" en "de
        # auto doet niets". Een tijdstip en geen teller: een ronde is niet altijd
        # een minuut, want een statuswissel van de paal start er ook een.
        self._asking_since: dict[str, datetime] = {}
        # Laadpunten waarvan de klaar-tijd verstreken is terwijl de auto niet vol
        # was. Die laden door tot ze vol zijn, want vol worden weegt zwaarder dan
        # goedkoop laden. Vervalt zodra de auto vol is of de kabel eruit gaat.
        self._te_laat: set[str] = set()
        # Wat er in deze laadbeurt gebeurd is: wanneer hij begon, hoeveel er in
        # ging en waar de tijd aan op is gegaan. Alleen om het achteraf te
        # kunnen navertellen, nooit om een besluit op te nemen.
        self._sessie: dict[str, dict[str, Any]] = {}
        # Laadbeurten waarvan de kabel eruit is en waar nog een verslag over
        # hoort te komen. Staat los van `_sessie`, want die is dan al opgeruimd
        # en mag ook niet blijven staan: een nieuwe kabel is een nieuwe beurt.
        self._afscheid: dict[str, tuple[datetime, dict[str, Any]]] = {}
        # Naar welke klaar-tijd een sessie op vol vermogen aan het toewerken is.
        # Zodra hij daaraan begonnen is, blijft hij dat doen tot de auto vol is
        # of de klaar-tijd verandert: terugnemen betekent alsnog te laat.
        self._deadline_for: dict[str, datetime] = {}
        # Tot wanneer de wekstroom blijft staan. Om dezelfde reden een klok: op
        # ronden geteld kon de wekpoging na drie seconden alweer voorbij zijn,
        # en daar wordt geen auto wakker van.
        self._wake_until: dict[str, datetime] = {}
        # Of de knoppen van de bewoner al teruggehaald zijn uit de opslag. Eén
        # keer per opstart, bij de eerste ronde.
        self._restored = False
        # Wanneer er voor het laatst gewaarschuwd is dat een eigen pauze de
        # klaar-tijd gaat kosten, per apparaat. Een moment en geen vinkje, want
        # deze waarschuwing komt terug zolang het risico er is; zie
        # `PAUSE_WARN_AGAIN`.
        self._warned: dict[str, datetime] = {}
        # Wie er al gewezen is op een laderlimiet die zijn laadbeurten op één
        # fase zet. Ook één keer per sessie: het is een instelling in de app van
        # de paal, en die verandert niet doordat je het twee keer zegt.
        self._getipt: set[str] = set()
        # Wanneer er voor het laatst om een accustand is gevraagd, per apparaat.
        # Eén melding per sessie is genoeg; vaker is zeuren en dan zet iemand de
        # meldingen uit.
        self._soc_asked: set[str] = set()
        # Tot wanneer de pauze die er staat geldig is, voor zover die een
        # houdbaarheid heeft. Nodig omdat de dode band een ongewijzigd besluit
        # niet opnieuw verstuurt: zonder deze klok zou een pauze van drie uur
        # verlopen omdat er niets veranderde, en ging de auto vanzelf laden.
        self._pause_until: dict[str, datetime] = {}
        # Draait er op dit moment een ronde? Er kan er maar één tegelijk, want
        # een ronde stuurt opdrachten en twee tegelijk zouden elkaar overschrijven.
        self._running = False
        # De statussensoren waar we op meeluisteren, en hoe we dat weer opzeggen.
        self._watched: set[str] = set()
        self._watched_phases: set[str] = set()
        self._unwatch = None
        # Vanaf welke fasestroom het haast wordt, en wanneer dat voor het laatst
        # gold. Beide worden elke ronde bijgewerkt.
        self._urgent_above: float | None = None
        self._last_urgent: datetime | None = None
        # Wanneer er voor het laatst een ronde helemaal is afgelopen, en of daar
        # al over gemeld is. Dit is wat de wachthond leest.
        self._last_round: datetime | None = None
        self._warned_silent = False
        self._cancel_watchdog = None

    @callback
    def async_start(self) -> None:
        """Begin the minute-by-minute round."""
        if self._cancel is None:
            self._cancel = async_track_time_interval(self.hass, self._tick, INTERVAL)
        if self._cancel_watchdog is None:
            self._last_round = dt_util.utcnow()
            self._cancel_watchdog = async_track_time_interval(
                self.hass, self._async_watchdog, WATCHDOG_INTERVAL
            )

    @callback
    def async_stop(self) -> None:
        """Stop, leaving the charger on whatever limit it was given.

        Deliberately nothing is sent here. A limit set with an unlimited
        time-to-live stays put, and it is always at or under what the charging
        point allows, so a coach that goes away leaves a car charging safely
        rather than at full tilt.
        """
        if self._cancel is not None:
            self._cancel()
            self._cancel = None
        if self._cancel_watchdog is not None:
            self._cancel_watchdog()
            self._cancel_watchdog = None
        if self._unwatch is not None:
            self._unwatch()
            self._unwatch = None
        self._watched = set()

    async def _async_watchdog(self, now: datetime | None = None) -> None:
        """Kijken of de coach zelf nog draait, en het zeggen als dat niet zo is.

        Een limiet die de coach heeft weggeschreven blijft staan tot hij hem
        weghaalt. Dat is met opzet, want het is de veilige kant: valt de coach
        weg, dan laadt de auto door op een stroom die de paal eerder heeft
        aangenomen. Maar het betekent ook dat een coach die stilvalt niets
        oplevert wat je zou opvallen. Er wordt geladen, of er wordt niet
        geladen, en beide zien er normaal uit.

        Dus zegt hij het zelf. Eén melding per stilte, niet elke vijf minuten,
        en zodra hij weer loopt is de stand weer schoon.
        """
        moment = now or dt_util.utcnow()
        stil = self._last_round is None or moment - self._last_round > WATCHDOG_SILENCE

        if not stil:
            self._warned_silent = False
            return
        if self._warned_silent:
            return

        self._warned_silent = True
        minuten = (
            "onbekend hoe lang"
            if self._last_round is None
            else f"al {int((moment - self._last_round).total_seconds() // 60)} minuten"
        )
        _LOGGER.error("de coach heeft %s geen ronde afgemaakt", minuten)
        await self._async_tell(
            f"De coach heeft {minuten} niets meer beslist. Wat er nu op je "
            "laadpaal staat blijft staan tot hij weer draait. Kijk in het "
            "logboek van Home Assistant wat er misging."
        )

    async def _async_tell(self, message: str) -> None:
        """Een melding sturen aan wie de klant daarvoor heeft uitgekozen.

        Dezelfde ontvangers als de waarschuwing over de belasting, want het is
        dezelfde vraag: er is iets waar je iets mee moet en niemand kijkt naar
        het scherm.
        """
        try:
            settings = await async_get_store(self.hass).async_load()
        except Exception:  # noqa: BLE001 - een stille coach is erger dan een lege melding
            _LOGGER.exception("kon de instellingen niet lezen voor een melding")
            return

        alert = (settings.get("strategy") or {}).get("load_alert") or {}
        for target in alert.get("targets") or []:
            try:
                await self.hass.services.async_call(
                    "notify",
                    target,
                    {"title": "DomotiApp Coach", "message": message},
                    blocking=False,
                )
            except Exception:  # noqa: BLE001 - één slechte ontvanger is niet alle
                _LOGGER.exception("Kon melding niet versturen naar notify.%s", target)

    @callback
    def async_refresh(self) -> None:
        """Nu meteen een ronde draaien, in plaats van tot de volgende minuut wachten.

        Een minuut is snel genoeg om een zekering voor te blijven, maar veel te
        traag als er iemand naar zit te kijken. Wie op pauze drukt en een halve
        minuut niets ziet gebeuren, concludeert dat de knop stuk is en gaat
        zoeken naar een andere manier. En wie de kabel eruit trekt, hoort niet
        nog een minuut op zijn scherm te lezen dat hij zelf gepauzeerd heeft.
        """
        self.hass.async_create_task(self._tick())

    def _watch_phases(self, settings: dict[str, Any], steerable: bool) -> None:
        """Welke fasesensoren er zijn, en vanaf welke stroom het haast wordt.

        De grens is dezelfde als waar de planner mee rekent: de zekering min de
        marge eronder. Komt een fase daarboven, dan is er voor de laadpaal niets
        meer over en hoort hij terug, nu en niet over een minuut.

        Zonder stuurbare laadpaal wordt er niets bewaakt: er is dan niets om
        terug te regelen, en meeluisteren met een meter die elke seconde meldt
        kost dan alleen maar.
        """
        sources = settings.get("sources") or {}
        installation = settings.get("installation") or {}

        entities: set[str] = set()
        if steerable and sources.get("phases_enabled"):
            for key in ("l1", "l2", "l3"):
                phase = (sources.get("phases") or {}).get(key) or {}
                # Alleen echte stroomsensoren. Uit vermogen en spanning valt het
                # ook te herleiden, maar dat is werk voor een ronde en niet voor
                # een melding die tien keer per seconde langskomt.
                if phase.get("current"):
                    entities.add(phase["current"])

        self._watched_phases = entities
        if not entities:
            self._urgent_above = None
            return

        zekering = float(installation.get("fuse_amps") or 25)
        marge = (
            BALANCER_MARGIN_AMPS if installation.get("load_balancer") else FUSE_MARGIN_AMPS
        )
        self._urgent_above = zekering - max(marge, zekering * FUSE_MARGIN_SHARE)

    def _watch(self, entity_ids: set[str]) -> None:
        """Meeluisteren met de statussensoren van de laadpalen.

        Zodat een kabel die erin gaat of eruit komt binnen een seconde een verse
        beslissing oplevert in plaats van bij de volgende ronde. De lijst
        verandert alleen als er apparaten bij komen of af gaan, dus dit doet
        vrijwel nooit iets.
        """
        if entity_ids == self._watched:
            return
        if self._unwatch is not None:
            self._unwatch()
            self._unwatch = None
        self._watched = entity_ids
        if entity_ids:
            self._unwatch = async_track_state_change_event(
                self.hass, sorted(entity_ids), self._async_state_changed
            )

    @callback
    def _async_state_changed(self, event) -> None:
        """Een wisseling waar de coach iets mee moet.

        Twee soorten. Een laadpaal die van toestand wisselt is er altijd een: de
        kabel gaat erin of eruit, het laden begint of stopt, en dan hoort er een
        vers besluit te komen in plaats van bij de volgende minuut.

        En de fasestromen, maar alleen als ze te hoog worden. Dat is de haast:
        een minuut is snel genoeg om een smeltveiligheid voor te blijven, maar
        het maakt die minuut wel het enige dat tussen een vol huis en een
        gesprongen zekering staat. Wordt het krap, dan kijkt hij binnen een
        seconde. Wordt het niet krap, dan gebeurt er hier niets, want anders
        draait de coach een ronde bij elke meterpuls.
        """
        entity = event.data.get("entity_id")
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        if new is None:
            return

        if entity in self._watched_phases:
            self._async_phase_changed(new)
            return

        if old is None or old.state == new.state:
            return
        self.async_refresh()

    @callback
    def _async_phase_changed(self, new) -> None:
        """Een fasestroom die over de grens komt, en niet te vaak."""
        if self._urgent_above is None:
            return
        try:
            amps = float(new.state)
        except (TypeError, ValueError):
            return
        if amps < self._urgent_above:
            return

        nu = dt_util.utcnow()
        if self._last_urgent is not None and nu - self._last_urgent < HURRY_INTERVAL:
            return
        self._last_urgent = nu
        _LOGGER.debug("fasestroom %.1f A boven %.1f A, meteen opnieuw kijken",
                      amps, self._urgent_above)
        self.async_refresh()

    async def _tick(self, now: datetime | None = None) -> None:
        """One round: look, think, act.

        Er kan er maar één tegelijk lopen. Een ronde wordt niet alleen door de
        klok gestart maar ook door een druk op een knop en door een laadpaal die
        van toestand wisselt, en twee rondes die tegelijk opdrachten sturen
        zouden elkaar in de weg zitten.
        """
        if self._running:
            return
        self._running = True
        try:
            async with asyncio.timeout(ROUND_TIMEOUT.total_seconds()):
                gelukt = await self._round(now)
            # Alleen een ronde die er werkelijk doorheen kwam telt als teken van
            # leven. Anders zwijgt de wachthond terwijl de coach al een uur geen
            # besluit meer neemt omdat zijn instellingen niet te lezen zijn: een
            # stille coach die er van buiten uitziet als een werkende.
            if gelukt:
                self._last_round = dt_util.utcnow()
        except TimeoutError:
            # De gevaarlijkste storing die er is, want hij is stil: hangt een
            # opdracht naar de laadpaal, dan zou de vlag hierboven blijven staan
            # en werd elke volgende ronde overgeslagen. De coach leefde dan nog
            # wel, maar besliste niets meer, en er werd gewoon geladen. Met een
            # harde grens eromheen kan dat niet: hij breekt af, meldt het, en
            # probeert het een minuut later opnieuw.
            _LOGGER.error(
                "een ronde duurde langer dan %s seconden en is afgebroken",
                int(ROUND_TIMEOUT.total_seconds()),
            )
        finally:
            self._running = False

    async def _round(self, now: datetime | None) -> bool:
        """Wat er in één ronde gebeurt, en of dat gelukt is."""
        try:
            settings = await async_get_store(self.hass).async_load()
        except Exception:  # noqa: BLE001 - never let a bad read stop the timer
            _LOGGER.exception("kon de instellingen niet lezen")
            return False

        self._restore(settings)

        level = (settings.get("strategy") or {}).get("level", LEVEL_PROPOSE)
        moment = dt_util.as_local(now or dt_util.utcnow()).replace(tzinfo=None)

        chargers = [
            device
            for device in settings.get("devices") or []
            if device.get("type") == "laadpaal" and device.get("controllable")
        ]
        self._watch_phases(settings, bool(chargers))
        self._watch(
            {
                entity
                for device in chargers
                if (entity := (device.get("entities") or {}).get("status"))
            }
            | self._watched_phases
        )

        # Twee laadpunten op één zekering zagen allebei dezelfde vrije ampères
        # en namen ze allebei. Wat de een krijgt telt daarom mee als bezet voor
        # wie er in deze ronde na hem komt.
        #
        # Dan doet de volgorde er ineens toe, en die mag niet afhangen van wie
        # er toevallig het eerst is toegevoegd. De voorrang die de klant per
        # apparaat heeft ingesteld bepaalt hem: is er te weinig ruimte voor
        # allebei, dan krijgt de auto die je nodig hebt hem.
        chargers.sort(key=lambda device: self._priority(settings, device))
        vergeven = 0.0
        for device in chargers:
            try:
                vergeven += await self._one(moment, settings, device, level, vergeven)
            except ServiceNotFound as fout:
                # Gebeurt bij het opstarten: de coach draait al voordat de
                # integratie van het merk zijn diensten heeft klaargezet. Geen
                # reden voor een foutmelding met een spoor erbij; de volgende
                # ronde is hij er wel. Zou hij er nooit komen, dan blijft deze
                # regel elke minuut terugkomen en dat is precies het signaal.
                _LOGGER.warning(
                    "%s kan nog niet aangestuurd worden: %s bestaat niet (nog niet geladen?)",
                    device.get("name") or device.get("id"),
                    fout.translation_placeholders.get("service", "de opdracht")
                    if getattr(fout, "translation_placeholders", None)
                    else "de opdracht",
                )
            except Exception:  # noqa: BLE001 - one broken device is not all of them
                _LOGGER.exception("kon %s niet beoordelen", device.get("id"))

        return True

    @staticmethod
    def _priority(settings: dict[str, Any], device: dict[str, Any]) -> int:
        """Wie er voorgaat als er te weinig ruimte is voor allebei."""
        rang = {"high": 0, "mid": 1, "low": 2}
        for entry in (settings.get("strategy") or {}).get("schedules") or []:
            if isinstance(entry, dict) and entry.get("device") == device.get("id"):
                return rang.get(entry.get("priority", "mid"), 1)
        return 1

    async def _one(
        self,
        now: datetime,
        settings: dict[str, Any],
        device: dict[str, Any],
        level: str,
        reserved: float = 0.0,
    ) -> float:
        """Look at one charging point and act on what the planner says.

        Geeft terug hoeveel ampère er méér gevraagd is dan deze paal op dit
        moment trekt. Dat is de ruimte die het volgende laadpunt in deze ronde
        niet meer als vrij mag zien: de fasemeting kent hem nog niet, want de
        auto is nog niet begonnen met trekken.
        """
        device_id = device.get("id", "")
        grid, car, charger, window = self._read(now, settings, device, reserved)
        goal = (settings.get("strategy") or {}).get("goal", "cost")

        # Wekken mag zolang de auto aan de kabel hangt, niet laadt en de poging
        # van deze sessie nog openstaat. Dat de coach ook wíl laden weet de
        # planner zelf; hier gaat het alleen over of het nog mag.
        # Is de klaar-tijd voorbijgegaan terwijl de auto niet vol is? Te zien aan
        # een klaar-tijd die opschuift: die van vandaag is dan verstreken en de
        # eerstvolgende ligt verder weg. Dit moet vóór het besluit gebeuren, want
        # anders schrijft hij eerst nog één keer een 0 naar de paal.
        mikpunt = (self._sessie.get(device_id) or {}).get("mikpunt")
        if (
            mikpunt is not None
            and window.deadline != mikpunt
            and mikpunt <= now
            and charger.connected
            and not charger.complete
        ):
            self._te_laat.add(device_id)

        # Werkt hij al toe naar deze klaar-tijd? Een andere klaar-tijd is een
        # andere afspraak, dus dan telt het besluit van daarnet niet meer.
        must_finish = bool(
            window.enabled
            and window.deadline is not None
            and self._deadline_for.get(device_id) == window.deadline
        )
        wektijd = self._wake_until.get(device_id)
        waking = charger.connected and not charger.charging and (
            device_id not in self._woken or (wektijd is not None and now < wektijd)
        )
        decision = decide(
            now, self._prices(settings), grid, car, charger, window, goal,
            self._tariff(settings), self._sun(settings),
            holding=self._holding.get(device_id, 0),
            waking=waking,
            asking_seconds=(
                (now - self._asking_since[device_id]).total_seconds()
                if device_id in self._asking_since
                else 0.0
            ),
            must_finish=must_finish,
            overdue=device_id in self._te_laat,
        )

        if decision.rule == "complete":
            self._te_laat.discard(device_id)
        if decision.rule.startswith("deadline") and window.deadline is not None:
            self._deadline_for[device_id] = window.deadline
        elif not decision.charge or decision.rule in ("boost", "complete"):
            # Een volle auto, een opdracht van de bewoner of een besluit om te
            # stoppen maakt de race naar de klaar-tijd irrelevant. Bij de
            # eerstvolgende ronde wordt gewoon opnieuw gerekend.
            self._deadline_for.pop(device_id, None)
        # De wekpoging is verbruikt zodra hij verstuurd is, en het aanbieden
        # begint te tellen zodra de coach stroom vraagt terwijl er niets loopt.
        if decision.rule.endswith("+wake"):
            self._woken.add(device_id)
            self._wake_until.setdefault(device_id, now + WAKE_WINDOW)
        elif not decision.charge:
            # Een sessie die bewust stilgezet wordt, mag straks opnieuw gewekt
            # worden. Dat is geen tweede poging binnen dezelfde start maar een
            # nieuwe start, en juist daar bleek de auto niet wakker te worden:
            # na hervatten van een pauze deed hij op 6 A weer niets.
            self._woken.discard(device_id)
            self._wake_until.pop(device_id, None)
        if decision.charge and charger.connected and not charger.charging:
            self._asking_since.setdefault(device_id, now)
        else:
            self._asking_since.pop(device_id, None)
        self._bijhouden(now, device, car, charger, window, decision)

        # Bijhouden hoe lang een sessie al tegen de ladder in wordt aangehouden.
        # Zodra de ladder het weer eens is met wat er gebeurt, staat de teller
        # op nul en heeft de volgende wolk weer zijn volle uitstel.
        self._holding[device_id] = (
            self._holding.get(device_id, 0) + 1 if decision.holding else 0
        )

        # Remembered before anything is sent, so the panel can show what the
        # coach would do even at a level where it does nothing.
        self.state[device_id] = {
            **asdict(decision),
            "at": now.isoformat(),
            "level": level,
            "applied": level == LEVEL_STEER,
        }
        # Iets dat alleen de bewoner zelf kan verhelpen, en dat losstaat van
        # het besluit van deze ronde. Het gaat dus naast de reden op de kaart
        # en niet erin.
        tip = self._fasetip(settings, device, charger)
        self.state[device_id]["tip"] = tip

        may_act = level == LEVEL_STEER or (
            level == LEVEL_PROPOSE and device_id in self._approved
        )
        # Eerst opruimen, dan pas opschrijven wat de stand is. Andersom bleef er
        # op de kaart nog een minuut "snelladen staat aan" staan nadat de kabel
        # er al uit was, en dat leest als een knop die blijft hangen.
        #
        # Een akkoord duurt zolang de auto aan de kabel hangt, en snelladen ook:
        # de auto waarvoor het bedoeld was staat er dan niet meer.
        if not charger.connected:
            self._approved.discard(device_id)
            self._boost.discard(device_id)
            self._paused.discard(device_id)
            self._zon.pop(device_id, None)
            self._holding.pop(device_id, None)
            self._pause_until.pop(device_id, None)
            self._woken.discard(device_id)
            self._wake_until.pop(device_id, None)
            self._asking_since.pop(device_id, None)
            self._deadline_for.pop(device_id, None)
            self._te_laat.discard(device_id)
            self._soc_asked.discard(device_id)
            self._warned.pop(device_id, None)
            self._getipt.discard(device_id)
            # Wat er over deze sessie bewaard is gaat mee weg. Een opgegeven
            # accustand hoort bij de auto die eraan hing: blijft die staan, dan
            # rekent de coach morgen met het percentage van gisteren terwijl er
            # honderd kilometer tussen zit, en dat is de gevaarlijke kant op.
            # Voor de knoppen geldt hetzelfde: wie de kabel eruit trekt, heeft
            # niets meer goedgekeurd of gepauzeerd.
            await self._async_forget(settings, device_id)

        self.state[device_id]["applied"] = may_act
        self.state[device_id]["approved"] = device_id in self._approved
        self.state[device_id]["boost"] = device_id in self._boost
        self.state[device_id]["paused"] = device_id in self._paused
        # Of de paal op dit moment werkelijk laadt. Niet voor een besluit maar
        # voor de kaart: een akkoord vragen leest anders als de auto al loopt.
        # Dan begint er niets, dan wordt er iets overgenomen.
        self.state[device_id]["charging"] = charger.charging
        self.hass.bus.async_fire(
            EVENT_DECISION, {"device": device_id, **self.state[device_id]}
        )

        # Wat deze paal straks méér gaat trekken dan nu. Alleen als de coach
        # ook werkelijk mag sturen, want anders gaat er niets naar de paal en is
        # er dus ook niets gereserveerd.
        claim = (
            max(0.0, decision.amps - charger.actual_amps)
            if may_act and decision.charge
            else 0.0
        )

        if not may_act:
            return 0.0

        await self._async_verslag(now, device, car, charger, window, decision)

        if decision.needs_soc:
            await self._async_ask_soc(device, decision)

        if tip and device_id not in self._getipt:
            self._getipt.add(device_id)
            await self._async_tell(f"{device.get('name') or 'De laadpaal'}: {tip}")

        # De pauze van de bewoner wint, ook van de klaar-tijd: het is zijn huis
        # en zijn knop. Maar de waarschuwing komt terug zolang het risico er is,
        # want één keer is te weinig om een lege auto mee te voorkomen.
        # Verdwijnt het risico, dan vervalt de klok en begint hij bij een
        # volgende keer weer opnieuw.
        gewaarschuwd = self._warned.get(device_id)
        if not decision.deadline_risk:
            self._warned.pop(device_id, None)
        elif gewaarschuwd is None or now - gewaarschuwd >= PAUSE_WARN_AGAIN:
            self._warned[device_id] = now
            await self._async_tell(
                f"De pauze op {device.get('name') or 'de laadpaal'} staat nog aan, en zo "
                "is de auto niet op tijd vol. Hervat het laden of verzet je klaar-tijd."
            )

        # The dead band holds only while the charging point is doing what it was
        # asked. When it is not, the command has to go again, or a car stands
        # still all night purely because the decision happened not to change:
        # that is exactly what a load balancer letting go looks like from here.
        # Prodding is on a timer of its own, because some of the reasons a
        # charger does not follow cannot be argued with by asking twice.
        following = self._following(device, charger, decision)
        if following:
            self._nudged.pop(device_id, None)
            if not should_send(self._last.get(device_id), decision) and not (
                self._pause_expiring(device_id, now)
            ):
                return claim
        elif charger.paused_by_balancer or held_back(charger):
            # Not following, and saying why: something outside the coach is
            # holding it. Ask again now and then, so a charger that quietly let
            # go is picked back up, but not every minute. Repeating a command at
            # a load balancer changes nothing and only fills its log.
            if not self._nudge_due(device_id, now):
                return claim
        else:
            # Not following and no reason given. That is the case where asking
            # again is exactly the right thing, so do it on the next round: this
            # is what a balancer letting go looks like from here, and a car that
            # waits five minutes for it has waited four too many.
            self._nudged.pop(device_id, None)

        if await self._apply(device, charger, decision, now):
            self._last[device_id] = decision
            # A session that a balancer is holding has not begun, so it must not
            # be stamped as begun: doing so would run the minimum out while
            # nothing charges, and have the coach read a standstill as its pace.
            if decision.charge and not charger.paused_by_balancer:
                self._since.setdefault(device_id, now)
            elif not decision.charge:
                self._since.pop(device_id, None)

        return claim

    def _smooth(self, device_id: str, surplus: float, now: datetime) -> float:
        """Het overschot, ontdaan van het gerimpel van een enkele minuut.

        Een wolk die voor de zon schuift, een waterkoker die aangaat: het
        overschot springt de hele dag heen en weer. Een coach die daar elke
        minuut achteraan loopt, stuurt de laadpaal grijs en levert er niets voor
        terug, want de auto merkt er niets van.

        Omhoog gaat langzaam en omlaag gaat meteen. Dat is met opzet niet
        symmetrisch: te veel vragen betekent inkopen tegen de dagprijs, en dat is
        een fout die geld kost. Te weinig vragen betekent een beetje zon
        exporteren die je ook zelf had kunnen gebruiken, en dat kost hooguit het
        verschil. Dus wordt er voor omhoog met het laagste van de laatste paar
        metingen gerekend, en voor omlaag met de meting van nu.
        """
        recent = self._zon.setdefault(device_id, [])
        recent.append((now, surplus))
        grens = now - SMOOTH_WINDOW
        recent[:] = [meting for meting in recent if meting[0] >= grens]
        return min(waarde for _, waarde in recent)

    def _following(
        self, device: dict[str, Any], charger: Charger, decision: Decision
    ) -> bool:
        """Of de laadpaal doet wat er gevraagd is.

        Voor laden is dat simpel: laadt hij. Voor niet laden juist niet, en daar
        zat een fout in. "Hij laadt nu niet" is namelijk niet hetzelfde als "hij
        gaat niet laden": een paal die op goedkeuring staat te wachten met een
        limiet van 32 erin begint zodra de auto erom vraagt. De coach zag dan
        geen verschil met wat hij wilde en stuurde dus niets, waarna de auto ging
        laden op een moment dat hij dat juist niet wilde. Wie zijn auto inplugt en
        meteen op pauze drukt, kreeg zo een knop die niets deed.

        Dus telt voor niet laden of onze nul er werkelijk staat, en niet of de
        paal toevallig stilstaat. Kan die limiet niet teruggelezen worden, dan
        blijft alleen de oude, zwakkere vraag over.
        """
        if decision.charge:
            return charger.charging
        if decision.rule in NO_WRITE_RULES:
            return True

        limiet = _number(self.hass, (device.get("entities") or {}).get("dynamic_limit"))
        if limiet is None:
            return not charger.charging
        return limiet < 0.5

    def _pause_expiring(self, device_id: str, now: datetime) -> bool:
        """Of de pauze die er staat bijna verlopen is en opnieuw moet.

        Een pauze wordt weggeschreven met de tijd die hij bedoeld is te duren,
        want dat is wat er moet gebeuren als de coach wegvalt: bij wachten op een
        goedkoop uur mag hij aflopen, en dan laadt de auto gewoon door. Maar
        zolang de coach er wél is, moet die pauze niet halverwege omvallen omdat
        het besluit toevallig niet veranderde. Vandaar dat hij ruim voor het
        einde nog eens gezet wordt.
        """
        einde = self._pause_until.get(device_id)
        return einde is not None and now >= einde - PAUSE_REFRESH

    def _nudge_due(self, device_id: str, now: datetime) -> bool:
        """Whether it is time to prod a charging point that is not following."""
        last = self._nudged.get(device_id)
        if last is not None and now - last < NUDGE_INTERVAL:
            return False
        self._nudged[device_id] = now
        return True

    def _slots(self, entity_id: str | None) -> dict[datetime, tuple[datetime, float]]:
        """De blokken uit een prijsentiteit, op begintijd."""
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            return {}

        uit: dict[datetime, tuple[datetime, float]] = {}
        for row in state.attributes.get("prices") or []:
            try:
                start = _tijdstip(row["from"])
                end = _tijdstip(row["till"])
                price = float(row["price"])
            except (KeyError, TypeError, ValueError):
                continue
            if start is None or end is None:
                continue
            uit[dt_util.as_local(start).replace(tzinfo=None)] = (
                dt_util.as_local(end).replace(tzinfo=None),
                price,
            )
        return uit

    @staticmethod
    def _salderen(contract: dict[str, Any], now: datetime | None = None) -> bool:
        """Of er op dit moment nog gesaldeerd wordt.

        Het vinkje van de klant én de datum. De regeling loopt af op
        `NETTING_ENDS`, en zonder die grens zou de coach na de jaarwisseling
        maandenlang een belastingteruggave blijven inrekenen die niet meer
        bestaat. Het vinkje blijft staan; het telt alleen niet meer mee.
        """
        if not contract.get("netting"):
            return False
        vandaag = dt_util.as_local(now or dt_util.utcnow()).date()
        return vandaag < NETTING_ENDS

    def _prices(self, settings: dict[str, Any]) -> list[dict]:
        """De prijslijst, met per blok wat het kost én wat teruglevering opbrengt.

        Uit dezelfde entiteit die het paneel tekent, zodat de twee het nooit
        oneens kunnen zijn over wat een uur kost.

        Wat teruglevering opbrengt is de kale marktprijs min de kosten die de
        leverancier daarover rekent. Bij een all-in prijssensor zit die kale
        prijs er niet meer in, en dan is hij er ook niet uit te halen. Daarom mag
        de marktprijssensor er los bij: hij is dan alleen voor de teruglevering,
        en zonder die sensor blijft de opbrengst gewoon onbekend. Onbekend is
        hier beter dan aangenomen, want op een aangenomen bedrag zou de coach
        gaan bijkopen.
        """
        contract = settings.get("contract") or {}
        if contract.get("type") != "dynamic":
            return []

        dynamic = contract.get("dynamic") or {}
        all_in = dynamic.get("source") == "all_in"
        kosten = float(dynamic.get("feed_in_costs") or 0)
        salderen = self._salderen(contract)
        # De opslag van de leverancier zit wel in wat je betaalt en niet in wat
        # je terugkrijgt. Bij salderen streept de energiebelasting weg tegen die
        # bij afname, maar die opslag niet: die betaal je per ingekochte kWh en
        # krijg je nergens terug. Zonder deze aftrek stond de terugleveropbrengst
        # er ruim twee cent te hoog in en leek eigen zon gebruiken even duur als
        # het weggeven ervan. Gevonden op 27-08-2026, uit Svens eigen nota.
        opslag = float(dynamic.get("supplier_markup") or 0) * (
            1 + float(dynamic.get("vat_percent") or 0) / 100
        )

        markt = self._slots(dynamic.get("market_entity"))
        inkoop = self._slots(dynamic.get("all_in_entity")) if all_in else markt
        if not inkoop:
            return []

        rows: list[dict] = []
        for start, (end, prijs) in inkoop.items():
            terug = None
            if not all_in:
                prijs = self._all_in(prijs, dynamic)

            if salderen:
                # Salderen betekent dat een teruggeleverde kWh wegstreept tegen
                # een ingekochte. Wat je daarmee bespaart is de inkoopprijs min
                # de opslag van je leverancier, want die opslag hangt aan de
                # afname en niet aan de kWh. Er is geen marktprijssensor voor
                # nodig: het antwoord staat al in de prijs die er is.
                terug = prijs - opslag - kosten
            elif all_in:
                if start in markt:
                    terug = markt[start][1] - kosten
            else:
                terug = markt[start][1] - kosten if start in markt else None

            rows.append({"start": start, "end": end, "price": prijs, "feed_in": terug})
        return sorted(rows, key=lambda item: item["start"])

    def _sun(self, settings: dict[str, Any]) -> Sun:
        """De zonverwachting, voor zover die is ingevuld.

        De uurwaarden komen in kWh over dat uur binnen, wat hetzelfde is als het
        gemiddelde vermogen in kW. Vandaar de vermenigvuldiging: de rest van de
        coach rekent in watt.
        """
        bron = (settings.get("sources") or {}).get("solar_forecast") or {}

        def uur(sleutel: str) -> float | None:
            kwh = _kwh(self.hass, bron.get(sleutel))
            return None if kwh is None else kwh * 1000.0

        return Sun(
            now_w=uur("this_hour"),
            next_w=uur("next_hour"),
            remaining_kwh=_kwh(self.hass, bron.get("remaining_today")),
        )

    @staticmethod
    def _tariff(settings: dict[str, Any]) -> Tariff:
        """Wat een kWh kost en opbrengt als de prijslijst niets zegt.

        Bij een vast contract staat het hele jaar hetzelfde getal, dus is er geen
        lijst en is dit alles wat de coach heeft. Juist daar telt het zwaar: het
        verschil tussen inkopen en terugleveren is bij een vast contract de enige
        reden die er is om het ene moment boven het andere te verkiezen.
        """
        contract = settings.get("contract") or {}
        if contract.get("type") == "dynamic":
            return Tariff()

        fixed = contract.get("fixed") or {}
        prijs = fixed.get("all_in_price")
        koop = float(prijs) if prijs is not None else None
        kosten = float(fixed.get("feed_in_costs") or 0)

        if ChargerCoach._salderen(contract):
            # Salderen: wat je teruglevert streept weg tegen wat je inkoopt, dus
            # is het de inkoopprijs waard. Het ingevulde terugleverbedrag geldt
            # dan niet; dat is pas aan de orde boven wat je zelf verbruikt.
            terug = None if koop is None else koop - kosten
        else:
            terug = float(fixed.get("feed_in_tariff") or 0) - kosten

        return Tariff(buy=koop, feed_in=terug)

    @staticmethod
    def _all_in(market: float, dynamic: dict[str, Any]) -> float:
        """A bare market price with tax, markup and VAT, the Dutch way round."""
        tax = float(dynamic.get("energy_tax") or 0)
        markup = float(dynamic.get("supplier_markup") or 0)
        vat = float(dynamic.get("vat_percent") or 0)
        return (market + tax + markup) * (1 + vat / 100)

    def _read(
        self,
        now: datetime,
        settings: dict[str, Any],
        device: dict[str, Any],
        reserved: float = 0.0,
    ) -> tuple[Grid, Car, Charger, Window]:
        """Everything the planner needs, gathered from the installation."""
        sources = settings.get("sources") or {}
        installation = settings.get("installation") or {}
        entities = device.get("entities") or {}

        # --- what the grid is doing ---
        #
        # Wat er naar het net gaat is geen vaste waarde maar een gevolg van wat
        # de coach zelf doet, en dat is de valkuil. Lever je 5 kW terug en gaat
        # de laadpaal aan, dan is die 5 kW weg. De coach zou dan meten dat er
        # geen zon meer over is, de laadpaal uitzetten, de 5 kW terugzien, en
        # weer aangaan. Elke minuut opnieuw, de hele middag.
        #
        # Daarom wordt hier niet gemeten wat er nú naar het net gaat, maar wat
        # er naar het net zou gaan als de laadpaal uit stond: het net saldo plus
        # wat de paal op dit moment zelf trekt. Dat getal verandert niet doordat
        # de coach iets doet, en daarmee is het kringetje open.
        # Optellen mag alleen als het saldo echt bekend is. Met één sensor die
        # alleen teruglevering meet, weet de coach niet of er tegelijk wordt
        # ingekocht, en dan zou hij bij 2 kW inkoop en 4 kW laden concluderen dat
        # er 4 kW zon over is. Liever de rauwe teruglevering dan een optelsom van
        # iets wat hij niet kan zien.
        if sources.get("grid_mode") == "signed":
            signed = _watts(self.hass, sources.get("grid_signed")) or 0.0
            if sources.get("grid_signed_invert"):
                signed = -signed
            netto, compleet = -signed, True
        else:
            export = _watts(self.hass, sources.get("grid_export"))
            invoer = _watts(self.hass, sources.get("grid_import"))
            netto = (export or 0.0) - (invoer or 0.0)
            compleet = export is not None and invoer is not None

        laadvermogen = _watts(self.hass, device.get("entity")) or 0.0
        surplus = max(0.0, netto + laadvermogen if compleet else max(0.0, netto))
        surplus = self._smooth(device.get("id", ""), surplus, now)

        phases = []
        for key in ("l1", "l2", "l3"):
            phase = (sources.get("phases") or {}).get(key) or {}
            amps = _number(self.hass, phase.get("current"))
            if amps is None:
                watts = _watts(self.hass, phase.get("power"))
                volts = _number(self.hass, phase.get("voltage")) or 230
                amps = watts / volts if watts is not None and volts else None
            if amps is not None:
                phases.append(amps)

        charger_amps = _number(self.hass, entities.get("current")) or 0.0

        grid = Grid(
            surplus_w=surplus,
            # Wat een eerder laadpunt in deze ronde al toegezegd heeft gekregen
            # en nog niet in de fasemeting staat.
            reserved_amps=reserved,
            phase_amps=phases,
            fuse_amps=float(installation.get("fuse_amps") or 25),
            charger_amps=charger_amps,
            # An installation with a balancer of its own guards the same fuse in
            # hardware. The coach widens its margin so it is the one to give way
            # and the two never reach for the same amp at the same second.
            margin_amps=(
                BALANCER_MARGIN_AMPS
                if installation.get("load_balancer")
                else FUSE_MARGIN_AMPS
            ),
        )

        # --- the charging point ---
        status = _text(self.hass, entities.get("status"))
        charger = Charger(
            max_amps=_number(self.hass, entities.get("max_limit")) or 16.0,
            connected=bool(status) and "disconnect" not in status,
            charging="charging" in status,
            started_at=self._since.get(device.get("id", "")),
            actual_amps=charger_amps,
            # De paal zegt het zelf als de auto vol is, en dat is beter dan het
            # afleiden uit een stroom die bijna nul is: dat laatste lijkt sprekend
            # op een auto die om een andere reden niets vraagt.
            complete="complete" in status,
            boost=device.get("id", "") in self._boost,
            paused_by_user=device.get("id", "") in self._paused,
            paused_by_balancer="equalizer" in status or "load_balancing" in status,
            no_current_reason=_text(self.hass, entities.get("no_current_reason")),
            # Wat er op de paal staat, zodat de klaar-tijdsom kan zien of de
            # coach zelf de rem is. Zie `throttled_by_coach` in planner.py.
            limit_amps=_number(self.hass, entities.get("dynamic_limit")),
        )
        # After a restart nothing is known about when this session began. Taking
        # it as "just now" only means waiting out the minimum run once.
        if charger.charging and charger.started_at is None:
            charger.started_at = self._since.setdefault(device.get("id", ""), now)

        # --- which car ---
        car = self._car(settings, device, charger)

        # --- when it may run ---
        window = resolve_window(now, self._days(settings, device))

        return grid, car, charger, window

    @staticmethod
    def _days(settings: dict[str, Any], device: dict[str, Any]) -> dict[int, DayWindow]:
        """Het schema van dit apparaat, per weekdag.

        Elke dag hetzelfde levert zeven gelijke dagen op; per dag levert alleen
        de dagen op die de klant heeft aangezet. De planner rekent het daarna om
        naar twee momenten, en dat is waar het vooruitkijken gebeurt: een
        weekend zonder eisen erin telt niet als "niets te doen" maar als "tijd
        om het goedkoopste moment uit te zoeken".
        """
        for entry in (settings.get("strategy") or {}).get("schedules") or []:
            if entry.get("device") != device.get("id") or not entry.get("enabled"):
                continue

            if not entry.get("per_day"):
                times = entry.get("window") or {}
                elke_dag = DayWindow(
                    enabled=True,
                    not_before=_time(times.get("not_before")),
                    start_by=_time(times.get("start_by")),
                    done_by=_time(times.get("done_by")),
                )
                return dict.fromkeys(range(7), elke_dag)

            uit: dict[int, DayWindow] = {}
            for day in entry.get("days") or []:
                weekdag = day.get("day")
                if not isinstance(weekdag, int) or not 0 <= weekdag <= 6:
                    continue
                uit[weekdag] = DayWindow(
                    enabled=bool(day.get("enabled")),
                    not_before=_time(day.get("not_before")),
                    start_by=_time(day.get("start_by")),
                    done_by=_time(day.get("done_by")),
                )
            return uit

        return {}

    def _chosen_car(
        self, settings: dict[str, Any], device: dict[str, Any]
    ) -> tuple[str, dict[str, Any] | None]:
        """Welke auto er aan dit laadpunt hangt: de keuze, en het profiel erbij.

        De keuze is `__guest__` voor een auto die hier niet woont, en dan is er
        geen profiel om bij te zoeken. Heeft niemand ooit gekozen terwijl er
        precies één auto bekend is, dan is dat hem.
        """
        chosen = ""
        for entry in settings.get("active_cars") or []:
            if entry.get("device") == device.get("id"):
                chosen = entry.get("car", "")
                break

        if chosen == "__guest__":
            return chosen, None

        cars = device.get("cars") or []
        profile = next((car for car in cars if car.get("id") == chosen), None)
        if profile is None and len(cars) == 1:
            profile = cars[0]
        return chosen, profile

    def _car(
        self, settings: dict[str, Any], device: dict[str, Any], charger: Charger
    ) -> Car:
        """The car that is plugged in, as far as anybody has said."""
        chosen, profile = self._chosen_car(settings, device)

        if chosen == "__guest__":
            return Car(guest=True, phases=3)

        if profile is None:
            return Car(phases=3)

        phases = {"one": 1, "three": 3}.get(profile.get("phases"), 3)
        zeker = True
        if profile.get("phases") == "both":
            # A car that switches phases tells on itself: power divided by
            # current is roughly one phase or roughly three. Standing still it
            # says nothing, and then three is the safe guess for how much of the
            # sun to take but the dangerous one for how long charging will last.
            # See hours_needed for what is done with that.
            gemeten = self._measured_phases(device)
            phases = gemeten or 3
            zeker = gemeten is not None

        # De auto zelf gaat voor. Zegt hij niets, dan telt wat de bewoner heeft
        # opgegeven, bijgewerkt met wat de paal er sindsdien in heeft gedaan.
        soc = _number(self.hass, profile.get("soc_entity"))
        if soc is None:
            soc = self._typed_soc(settings, device, profile)
        if soc is None:
            soc = self._onthouden_soc(device, profile)

        return Car(
            capacity_kwh=float(profile.get("capacity_kwh") or 0),
            phases=phases,
            phases_certain=zeker,
            max_amps=float(profile.get("max_amps") or 0),
            soc_percent=soc,
        )

    def _onthouden_soc(
        self, device: dict[str, Any], profile: dict[str, Any]
    ) -> float | None:
        """De laatste accustand van deze laadbeurt, bijgewerkt tot nu.

        Een auto die zijn percentage even niet doorgeeft is geen auto waarvan
        niemand de stand kent. Hij hangt nog aan dezelfde kabel, want zodra die
        eruit gaat is de hele laadbeurt vergeten. Dus telt wat hij het laatst
        zei, plus wat de paal er sindsdien in heeft gedaan, net als bij een
        stand die met de hand is opgegeven.

        Dit repareert een melding die op 25-08-2026 om 15:45 langskwam: de
        Ford-integratie viel een minuut weg en de kaart zei "De auto is vol"
        terwijl de bus op 80% stond. Diezelfde avond om 20:04 vroeg de coach om
        een accustand die hij eerder op de avond gewoon gezien had.
        """
        sessie = self._sessie.get(device.get("id", "")) or {}
        percent = sessie.get("soc_gezien")
        if percent is None:
            return None

        capacity = float(profile.get("capacity_kwh") or 0)
        meter = self._teller(device)
        sinds = sessie.get("soc_meter")
        if capacity and meter is not None and sinds is not None:
            geladen = max(0.0, meter - float(sinds)) * CHARGE_EFFICIENCY
            percent = float(percent) + geladen / capacity * 100.0
        return min(100.0, float(percent))

    def _typed_soc(
        self,
        settings: dict[str, Any],
        device: dict[str, Any],
        profile: dict[str, Any],
    ) -> float | None:
        """Wat de bewoner opgaf, plus wat er sindsdien in is gegaan.

        Zo hoeft er hooguit één keer per sessie iets ingevuld te worden. De
        teller van de laadpaal telt alles wat hij ooit geleverd heeft, dus het
        verschil met de stand van toen is precies wat er daarna in deze auto is
        gegaan. Daar gaat het laadrendement nog af, want niet alles wat de paal
        levert komt in de accu terecht.
        """
        capacity = float(profile.get("capacity_kwh") or 0)
        if not capacity:
            return None

        entry = next(
            (
                row
                for row in (settings.get("car_soc") or [])
                if isinstance(row, dict)
                and row.get("device") == device.get("id")
                and row.get("car") == profile.get("id")
            ),
            None,
        )
        if entry is None or entry.get("percent") is None:
            return None

        percent = float(entry["percent"])
        meter = self._teller(device)
        since = entry.get("meter")
        if meter is not None and since is not None:
            geladen = max(0.0, meter - float(since)) * CHARGE_EFFICIENCY
            percent += geladen / capacity * 100.0
        return min(100.0, percent)

    # Waar de tijd aan opging, in woorden die een bewoner herkent. Zelfstandig
    # geformuleerd, zodat er "20 minuten naar ..." voor kan staan zonder dat het
    # kromme taal wordt.
    VERTRAGING = {
        "user-hold": "de pauze die je zelf aanzette",
        "no-room": "een aansluiting die vol zat",
        "held-back": "de lastbewaking van je aansluiting",
        "balancer-paused": "de lastbewaking van je aansluiting",
        "waiting-for-car": "een auto die geen stroom afnam",
        "no-soc": "wachten op je accustand",
        "wait-for-sun": "wachten op je eigen zon",
        "wait-for-sun-today": "wachten op je eigen zon",
        "wait-for-price": "wachten op een goedkoper uur",
        "too-early": "de tijden die je hebt ingesteld",
    }

    def _bijhouden(
        self,
        now: datetime,
        device: dict[str, Any],
        car: Car,
        charger: Charger,
        window: Window,
        decision: Decision,
    ) -> None:
        """Onthouden wat er in deze laadbeurt gebeurt, om het na te kunnen vertellen."""
        device_id = device.get("id", "")
        if not charger.connected:
            # De kabel is eruit. Voordat deze beurt wordt vergeten gaat hij naar
            # `_afscheid`, want er hoort nog een verslag over. Sven trok hem er
            # op 20-08-2026 twee keer uit tijdens het laden en hoorde niets: er
            # kwam alleen iets bij "vol" en bij een gemiste klaar-tijd.
            #
            # Alleen als er ook werkelijk geladen is, en alleen als er nog niets
            # over gezegd is: een auto die vol was en daarna van de kabel gaat
            # heeft zijn verslag al gehad.
            beurt = self._sessie.pop(device_id, None)
            if beurt and beurt.get("begon") and "vol" not in beurt.get("gemeld", set()):
                self._afscheid[device_id] = (now, beurt)
            return

        vers = device_id not in self._sessie
        if vers:
            # Er hangt weer een kabel. Is er nog een afscheid blijven staan van
            # de vorige beurt, dan is dat er een die nooit verteld is omdat de
            # coach niet mocht sturen. Die hoort niet alsnog binnen te komen bij
            # een volgende auto; dan gaat het bericht over de verkeerde beurt.
            self._afscheid.pop(device_id, None)

        sessie = self._sessie.setdefault(
            device_id,
            {
                "begon": None,
                "meter": None,
                "laatst": now,
                "kwijt": {},
                "doel": window.deadline if window.enabled else None,
                "mikpunt": window.deadline if window.enabled else None,
                "gemeld": set(),
                "ingestapt": False,
                # Wanneer de auto zijn accustand voor het laatst wijzigde, en
                # vanaf wanneer hij niet verder laadt. Samen bepalen ze of het
                # percentage in het verslag bij deze beurt hoort.
                "soc_gezien": None,
                "soc_moment": None,
                "soc_meter": None,
                "klaar_sinds": None,
                # Wat de coach zelf aan energie langs heeft zien komen, en welk
                # deel daarvan de teller van de paal al verwerkt had. Samen
                # maken ze het verslag compleet; zie `_geladen`.
                "gemeten_kwh": 0.0,
                "meter_stand": None,
                "meter_kwh": 0.0,
                "watt": 0.0,
                "liep": False,
            },
        )
        if vers:
            # Laadt hij al bij de allereerste ronde, dan is deze beurt eerder
            # begonnen dan de coach kan weten: Home Assistant is midden in de
            # laadbeurt herstart. Normaal ziet hij de kabel er eerst in gaan en
            # pas een ronde later stroom lopen.
            #
            # Dit onthouden is het verschil tussen een verslag dat klopt en een
            # dat liegt. Op 20-08-2026 herstartte Sven om 20:57 en las hij daarna
            # "Geladen van 20:58 tot 21:32, 3,1 kWh", terwijl de auto vanaf 19:18
            # aan de kabel hing en er 5,2 kWh in was gegaan.
            sessie["ingestapt"] = charger.charging

        # Tijd toeschrijven aan wat er op dat moment aan de hand was. Het verschil
        # met de vorige ronde en niet één minuut, want een ronde kan ook door een
        # knop of een statuswissel gestart zijn.
        stap = (now - sessie["laatst"]).total_seconds() / 60
        sessie["laatst"] = now
        if 0 < stap <= 10:
            for sleutel in self.VERTRAGING:
                if sleutel in decision.rule:
                    sessie["kwijt"][sleutel] = sessie["kwijt"].get(sleutel, 0.0) + stap
                    break

        meter = self._teller(device)

        # De laatste accustand van deze laadbeurt vasthouden, met de meterstand
        # van dat moment erbij. Een percentage dat wegvalt is geen nieuw
        # percentage: de auto hangt nog aan dezelfde kabel en kan dus niet
        # weggereden zijn. Zie `_onthouden_soc` voor wat ermee gebeurt.
        if car.soc_percent is not None and car.soc_percent != sessie.get("soc_gezien"):
            sessie["soc_gezien"] = car.soc_percent
            sessie["soc_moment"] = now
            sessie["soc_meter"] = meter

        # Zelf meten wat er langskomt, want de levensduurteller van de paal
        # loopt achter. Bij Sven werkte hij op 25-08-2026 maar één keer per uur
        # bij en sprong hij toen met 3,5 kWh ineens, dus het verslag miste het
        # laatste half uur van de beurt. Wat de teller al verwerkt heeft blijft
        # van de teller; alleen de staart daarna komt uit deze som.
        #
        # Gerekend met het vermogen van de vórige ronde, want dat is het
        # vermogen dat er in de minuut ertussen werkelijk stond. Met het
        # vermogen van nu schuift de hele meting een ronde op: de eerste minuut
        # telt dan mee terwijl er nog niets liep, en de laatste valt weg. En
        # alleen als hij toen ook laadde, want een vermogenssensor die na
        # afloop op zijn laatste waarde blijft hangen zou anders doortellen.
        if sessie.get("liep") and 0 < stap <= 10:
            sessie["gemeten_kwh"] += sessie.get("watt", 0.0) / 1000.0 * stap / 60.0
        sessie["watt"] = _watts(self.hass, device.get("entity")) or 0.0
        sessie["liep"] = charger.charging
        if meter is not None and meter != sessie.get("meter_stand"):
            sessie["meter_stand"] = meter
            sessie["meter_kwh"] = sessie["gemeten_kwh"]

        sessie["mikpunt"] = window.deadline if window.enabled else None

        if charger.charging and sessie["begon"] is None:
            sessie["begon"] = now
            sessie["meter"] = meter
            sessie["meter_kwh"] = sessie["gemeten_kwh"]

    def _geladen(self, device: dict[str, Any], sessie: dict[str, Any]) -> float | None:
        """Hoeveel kWh er deze beurt in is gegaan.

        De teller van de paal is de maat, want die is geijkt. Alleen loopt hij
        achter: hij verwerkt met sprongen, en wat er ná zijn laatste stap nog
        in ging staat er nog niet in. Dat laatste stuk komt uit wat de coach
        zelf aan vermogen langs zag komen, en is dus ook gemeten en niet
        aangenomen. Heeft de paal helemaal geen teller, dan is die eigen meting
        alles wat er is, en dat is nog altijd beter dan zwijgen.
        """
        staart = max(0.0, sessie.get("gemeten_kwh", 0.0) - sessie.get("meter_kwh", 0.0))
        meter = self._teller(device)
        if meter is None or sessie.get("meter") is None:
            return staart or None
        return max(0.0, meter - float(sessie["meter"])) + staart

    def _waarom(self, sessie: dict[str, Any]) -> str:
        """De twee dingen waar de meeste tijd aan op is gegaan, in gewone taal."""
        kwijt = [
            (minuten, self.VERTRAGING[sleutel])
            for sleutel, minuten in (sessie.get("kwijt") or {}).items()
            if minuten >= 2 and sleutel in self.VERTRAGING
        ]
        if not kwijt:
            return ""
        kwijt.sort(reverse=True)
        stukken = [f"{int(minuten)} minuten naar {tekst}" for minuten, tekst in kwijt[:2]]
        return " en ".join(stukken)

    def _soc_bezonken(
        self, now: datetime, sessie: dict[str, Any], car: Car
    ) -> bool:
        """Of de accustand hoort bij de laadbeurt die net is afgelopen.

        Een auto meldt zich op zijn eigen tempo. Stopt hij met laden en staat de
        app nog op het percentage van een half uur geleden, dan zou het verslag
        een getal noemen dat de bewoner op de kaart al gecorrigeerd ziet staan.
        Dus wacht het bericht tot de auto zich één keer heeft gemeld sinds hij
        ophield, of tot `SOC_SETTLE` voorbij is.

        Zonder accustand valt er niets te wachten: dan noemt het verslag geen
        percentage en is er ook niets dat verouderen kan.
        """
        if car.soc_percent is None:
            return True
        klaar = sessie.get("klaar_sinds")
        if klaar is None:
            return True
        moment = sessie.get("soc_moment")
        if moment is not None and moment >= klaar:
            return True
        return now - klaar >= SOC_SETTLE

    async def _async_verslag(
        self,
        now: datetime,
        device: dict[str, Any],
        car: Car,
        charger: Charger,
        window: Window,
        decision: Decision,
    ) -> None:
        """Vertellen hoe het afliep, en waarom het langer duurde dan afgesproken.

        Drie momenten. Als de auto vol is, want dan is de vraag "hoe laat was
        hij klaar" en niet "wat doet hij nu". Als de klaar-tijd voorbijgaat
        terwijl hij niet vol is, want dat is precies het geval waarin iemand
        anders zou denken dat de coach niets gedaan heeft. En als de kabel eruit
        gaat terwijl er geladen werd, want dan is de beurt net zo goed afgelopen
        en is dezelfde vraag aan de orde.
        """
        device_id = device.get("id", "")
        naam = device.get("name") or "de laadpaal"

        # De kabel is eruit gegaan. Deze staat vooraan omdat de beurt dan al uit
        # `_sessie` gehaald is en de controle hieronder er dus overheen zou
        # lopen.
        afscheid = self._afscheid.pop(device_id, None)
        if afscheid:
            await self._async_afgekoppeld(device, naam, *afscheid)
            return

        sessie = self._sessie.get(device_id)
        if not sessie:
            return

        gemeld: set[str] = sessie["gemeld"]

        # De auto is vol.
        if decision.rule == "complete" and "vol" not in gemeld and sessie["begon"]:
            if sessie.get("klaar_sinds") is None:
                sessie["klaar_sinds"] = now
            if not self._soc_bezonken(now, sessie, car):
                return
            gemeld.add("vol")
            geladen = self._geladen(device, sessie)
            kwh = f"{geladen:.1f} kWh".replace(".", ",") if geladen else ""
            waarom = self._waarom(sessie)
            # "Vol" is wat de paal zegt, niet altijd wat de accu doet. Stopt een
            # auto op 80% omdat daar een laadgrens in staat, dan is "de auto is
            # vol" onwaar en leest het als een coach die niet weet wat hij doet.
            # Weet hij de accustand, dan zegt hij die gewoon. Sven op 20-08-2026.
            klaar = (
                f"De auto aan {naam} is vol."
                if car.soc_percent is None or car.soc_percent >= FULL_PERCENT
                else (
                    f"De auto aan {naam} laadt niet verder en staat op "
                    f"{int(car.soc_percent)}%. Mogelijk staat er een laadgrens in "
                    "de auto."
                )
            )
            # Is de coach midden in de laadbeurt ingestapt, dan weet hij niet
            # hoe laat die begon en hoort hij dat ook niet te suggereren.
            begon = sessie["begon"]
            if sessie.get("ingestapt") and kwh:
                verloop = f" Sinds {begon:%H:%M} ging er {kwh} in, en toen liep hij al."
            elif sessie.get("ingestapt"):
                verloop = f" Hij liep al toen de coach om {begon:%H:%M} begon te kijken."
            elif kwh:
                verloop = f" Geladen van {begon:%H:%M} tot {now:%H:%M}, {kwh}."
            else:
                verloop = f" Geladen van {begon:%H:%M} tot {now:%H:%M}."
            await self._async_tell(
                klaar + verloop + (f" Daarvan ging {waarom}." if waarom else "")
            )
            return

        # De klaar-tijd is verstreken en de auto is niet vol. Te zien aan een
        # nieuwe klaar-tijd: die van vandaag is dan voorbij en de eerstvolgende
        # ligt morgen.
        doel = window.deadline if window.enabled else None
        vorig = sessie.get("doel")
        sessie["doel"] = doel
        if vorig is None or doel == vorig or vorig > now or "laat" in gemeld:
            return

        gemeld.add("laat")
        stand = (
            f" Hij staat nu op {int(car.soc_percent)}%."
            if car.soc_percent is not None
            else ""
        )
        waarom = self._waarom(sessie)
        await self._async_tell(
            f"De auto aan {naam} was om {vorig:%H:%M} nog niet vol.{stand}"
            + (f" Er ging {waarom}." if waarom else "")
            + " Hij laadt door tot hij vol is."
        )

    async def _async_afgekoppeld(
        self,
        device: dict[str, Any],
        naam: str,
        moment: datetime,
        sessie: dict[str, Any],
    ) -> None:
        """Vertellen hoe het afliep toen de kabel eruit ging.

        Dezelfde vorm als het verslag bij een volle auto, want het is dezelfde
        vraag: wanneer hield het op en hoeveel is erin gegaan. Afgesproken met
        Sven op 26-08-2026, met zijn eigen zin als voorbeeld: "afgekoppeld om
        19:12, er ging 4,2 kWh in".

        Wat er niet in staat is een oordeel. De kabel eruit trekken is een
        gewone handeling en geen storing, dus er hoort geen "maar hij was nog
        niet vol" bij; dat weet de bewoner zelf.
        """
        geladen = self._geladen(device, sessie)
        kwh = f"{geladen:.1f} kWh".replace(".", ",") if geladen else ""
        begon = sessie.get("begon")

        # Is de coach midden in de laadbeurt ingestapt, dan weet hij niet hoe
        # laat die begon en hoort hij dat ook niet te suggereren. Zelfde
        # afweging als bij het verslag hierboven.
        if sessie.get("ingestapt") and kwh:
            verloop = f", er ging {kwh} in sinds {begon:%H:%M}, en toen liep hij al."
        elif kwh:
            verloop = f", er ging {kwh} in sinds {begon:%H:%M}."
        else:
            verloop = "."

        waarom = self._waarom(sessie)
        await self._async_tell(
            f"De auto aan {naam} is afgekoppeld om {moment:%H:%M}"
            + verloop
            + (f" Er ging {waarom}." if waarom else "")
        )

    async def _async_ask_soc(self, device: dict[str, Any], decision: Decision) -> None:
        """Vragen hoe vol de auto is, want zonder dat kan de coach niets plannen.

        Twee momenten en niet meer. Eén keer als hij het merkt, want dan is er
        nog tijd om er iets mee te doen, en één keer als het vangnet ingrijpt,
        want dan gebeurt er iets dat de bewoner had kunnen voorkomen. Vaker is
        zeuren, en wie gezeurd wordt zet zijn meldingen uit.
        """
        device_id = device.get("id", "")
        naam = device.get("name") or "de laadpaal"
        merk = f"{device_id}:deadline" if decision.rule == "deadline" else device_id
        if merk in self._soc_asked:
            return
        self._soc_asked.add(merk)

        if decision.rule == "deadline":
            bericht = (
                f"De accustand van de auto aan {naam} is nog steeds niet doorgegeven, "
                "dus de coach gaat uit van een lege accu en laadt nu door om op tijd "
                "klaar te zijn."
            )
        else:
            bericht = (
                f"De coach wil de auto aan {naam} gaan laden, maar weet niet hoe vol "
                "hij is. Geef de accustand door op de laadpaalkaart, dan laadt hij op "
                "het gunstigste moment."
            )
        await self._async_tell(bericht)

    async def _async_forget(self, settings: dict[str, Any], device_id: str) -> None:
        """Alles wat over deze sessie bewaard was vergeten, in één keer.

        In één schrijfbeurt, want dit gebeurt bij elke ronde dat er geen kabel
        in zit en twee schrijfbeurten per minuut is twee keer te veel. Staat er
        niets meer, dan wordt er ook niets geschreven.
        """
        wijziging = {}
        for sleutel in ("car_soc", "sessions"):
            rows = [
                row
                for row in (settings.get(sleutel) or [])
                if isinstance(row, dict) and row.get("device") != device_id
            ]
            if len(rows) != len(settings.get(sleutel) or []):
                wijziging[sleutel] = rows
        if not wijziging:
            return
        try:
            saved = await async_get_store(self.hass).async_save(wijziging)
        except Exception:  # noqa: BLE001 - een vergeten percentage is geen reden om te stoppen
            _LOGGER.exception("kon de gegevens van de vorige sessie niet vergeten")
            return
        self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": saved})

    def _teller(self, device: dict[str, Any]) -> float | None:
        """De geijkte kWh-teller van dit apparaat, hoe hij ook ingevuld is.

        Twee velden vroegen om hetzelfde. Bij een Easee vult de installateur
        onder Merk "Levensduur verbruik" in, en bij Apparaten staat daarnaast
        "Energieteller (optioneel)" die naar dezelfde sensor wijst. Sven merkte
        dat op 27-08-2026 bij een klant: hij typte hem twee keer.

        Erger dan het dubbele typen was wat eronder zat. Alleen Easee heeft dat
        merkveld; Zaptec, Wallbox, Zappi en Peblar hebben geen enkel merkveld.
        Bij die klanten kwam er dus nooit een teller binnen, ook niet als de
        Energieteller keurig was ingevuld, en viel het verslag terug op wat de
        coach zelf aan vermogen langs zag komen. Dat werkt, maar de geijkte
        teller ligt er dan ongebruikt naast.

        Het merkveld eerst, want bestaande installaties hebben dat ingevuld en
        die mogen hier niets van merken.
        """
        entiteit = (device.get("entities") or {}).get("lifetime_energy") or device.get(
            "energy_entity"
        )
        return _kwh(self.hass, entiteit)

    def _fasetip(
        self, settings: dict[str, Any], device: dict[str, Any], charger: Charger
    ) -> str:
        """Zeggen dat de laderlimiet laadsnelheid kost, als dat werkelijk zo is.

        De paal kiest bij het starten van een beurt zelf hoeveel fasen hij
        pakt, en gaat daarbij af op zijn eigen maximale limiet. Staat die te
        laag, dan laadt elke beurt eenfasig. Bij Sven kostte dat een week lang
        stilletjes een factor drie: 3,1 kW waar 10,9 kW kon, en niets in het
        paneel dat er iets over zei. De limiet die de coach schrijft telt in die
        keuze niet mee, dus dit is met sturen niet op te lossen en is het enige
        wat overblijft: het zeggen.

        Alleen zeggen wat gezien is. Er loopt stroom over één fase terwijl de
        laderlimiet onder `PHASE_START_AMPS` staat, aan een merk waar dat aan
        gemeten is. Een auto die zelf maar één fase kan, kan er niets aan doen
        en krijgt dus niets te lezen.
        """
        if device.get("brand") != "easee" or not charger.charging:
            return ""
        if not charger.max_amps or charger.max_amps >= PHASE_START_AMPS:
            return ""
        _, profile = self._chosen_car(settings, device)
        if profile is not None and profile.get("phases") == "one":
            return ""
        if self._measured_phases(device) != 1:
            return ""
        return (
            "Hij laadt op één fase, want de maximale limiet van je lader staat "
            f"op {charger.max_amps:.0f} A. Op {PHASE_START_AMPS:.0f} A of hoger "
            "begint elke laadbeurt op drie fasen, en gaat er ongeveer drie keer "
            "zoveel in per uur."
        )

    def _measured_phases(self, device: dict[str, Any]) -> int | None:
        """One phase or three, worked out from what the charger reports."""
        entities = device.get("entities") or {}
        watts = _watts(self.hass, device.get("entity"))
        amps = _number(self.hass, entities.get("current"))
        if not watts or not amps or amps < 1:
            return None
        return 3 if amps_for(watts, 1) / amps > 2 else 1

    def _restore(self, settings: dict[str, Any]) -> None:
        """De knoppen van de bewoner terughalen na een herstart.

        Een akkoord, snelladen en een pauze zijn opdrachten van een mens, en die
        horen niet te verdampen omdat Home Assistant vannacht toevallig opnieuw
        opstartte. Zonder dit stond een auto die op "adviseren" was goedgekeurd
        's ochtends leeg, want de coach was zijn akkoord kwijt en niemand was
        wakker om opnieuw op de knop te drukken.

        Ze verlopen wel, en om twee redenen. Een opdracht van gisteren gaat niet
        over de auto die er nu hangt, en na een herstart kan de coach niet zien
        of de kabel er tussendoor uit is geweest. Het uittrekken van de kabel
        wist ze sowieso; dit is het vangnet voor wat hij niet gezien heeft.
        """
        if self._restored:
            return
        self._restored = True

        grens = dt_util.utcnow() - SESSION_MEMORY
        for row in settings.get("sessions") or []:
            if not isinstance(row, dict) or not row.get("device"):
                continue
            stempel = dt_util.parse_datetime(str(row.get("at") or ""))
            if stempel is None or stempel < grens:
                continue
            device_id = str(row["device"])
            if row.get("approved"):
                self._approved.add(device_id)
            if row.get("boost"):
                self._boost.add(device_id)
            if row.get("paused"):
                self._paused.add(device_id)

    def _remember(self, device_id: str) -> None:
        """Vastleggen wat er nu voor dit apparaat aan staat.

        Wegschrijven duurt even en de knop moet meteen reageren, dus het gaat
        als eigen taak de wachtrij in. De ronde die er meteen achteraan komt
        leest de vlaggen uit het geheugen en niet uit de opslag, dus die hoeft
        er niet op te wachten.
        """
        self.hass.async_create_task(self._async_remember(device_id))

    async def _async_remember(self, device_id: str) -> None:
        """Het schrijfwerk van `_remember`."""
        aan = {
            "approved": device_id in self._approved,
            "boost": device_id in self._boost,
            "paused": device_id in self._paused,
        }
        try:
            store = async_get_store(self.hass)
            settings = await store.async_load()
            rows = [
                row
                for row in (settings.get("sessions") or [])
                if isinstance(row, dict) and row.get("device") != device_id
            ]
            if any(aan.values()):
                rows.append(
                    {"device": device_id, **aan, "at": dt_util.utcnow().isoformat()}
                )
            saved = await store.async_save({"sessions": rows})
        except Exception:  # noqa: BLE001 - een knop die werkt gaat voor op onthouden
            _LOGGER.exception("kon de stand van de knoppen niet bewaren")
            return
        self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": saved})

    @callback
    def async_approve(self, device_id: str) -> None:
        """The customer agreed to this charging session."""
        self._approved.add(device_id)
        self._remember(device_id)
        self.async_refresh()

    @callback
    def async_withdraw(self, device_id: str) -> None:
        """And can take that back."""
        self._approved.discard(device_id)
        self._remember(device_id)
        self.async_refresh()

    @callback
    def async_boost(self, device_id: str, on: bool) -> None:
        """Snelladen aan of uit: laden op vol vermogen, ongeacht de prijs."""
        if on:
            self._boost.add(device_id)
            # Twee tegengestelde opdrachten van dezelfde persoon: de laatste
            # telt. Anders zou snelladen aanstaan terwijl er niets gebeurt.
            self._paused.discard(device_id)
        else:
            self._boost.discard(device_id)
        self._remember(device_id)
        self.async_refresh()

    @callback
    def async_boosting(self, device_id: str) -> bool:
        """Of snelladen op dit moment aanstaat."""
        return device_id in self._boost

    @callback
    def async_pause(self, device_id: str, on: bool) -> None:
        """Met de hand pauzeren of hervatten.

        Anders dan de knoppen bij Handmatige besturing gaat dit niet langs de
        coach heen maar erdoorheen: hij weet ervan en houdt zijn handen thuis.
        Zonder dat zette de klant het laden stil en zette de coach het een minuut
        later weer aan, en dan is het een knop die niet werkt.
        """
        if on:
            self._paused.add(device_id)
            self._boost.discard(device_id)
        else:
            self._paused.discard(device_id)
        self._remember(device_id)
        self.async_refresh()

    @callback
    def async_paused(self, device_id: str) -> bool:
        """Of de bewoner op dit moment zelf gepauzeerd heeft."""
        return device_id in self._paused

    async def _apply(
        self, device: dict[str, Any], charger: Charger, decision: Decision, now: datetime
    ) -> bool:
        """Send it, in the order the hardware wants.

        The limit goes first and the start second, with a check in between that
        the charger really took the new limit. Blindly waiting a fixed second or
        two is either too short on a slow evening or wasted the rest of the
        time, and the panel already reads the limit back anyway.

        **Er wordt nooit een stopcommando gestuurd.** Dat is geen voorkeur maar
        een meting aan een echte paal: een stop haalt de goedkeuring van de
        sessie eraf, en die moet daarna opnieuw gegeven worden. Niet laden gaat
        daarom langs dezelfde weg als wel laden, namelijk de limiet, met een 0
        erin. De sessie blijft dan gewoon goedgekeurd en hervatten is niets meer
        dan een gewoon getal terugschrijven.
        """
        control = CHARGER_CONTROL.get(device.get("brand", ""))
        if not control or not device.get("device_id"):
            return False

        if not decision.charge:
            return await self._pause(device, control, charger, decision, now)

        self._pause_until.pop(device.get("id", ""), None)
        await self._limit(device, control, decision.amps, 0)

        if charger.paused_by_balancer:
            # The limit above is still worth sending: it is our standing request
            # and the balancer works on the lowest of all the limits, so it has
            # to be in place for the moment room appears. Starting is not worth
            # sending. The charger is being held by something that does not
            # listen to us, and asking again every minute only fills its log.
            _LOGGER.debug(
                "laadpaal %s wordt tegengehouden door de lastbewaking; niet gestart",
                device.get("id"),
            )
            return True

        if not charger.charging:
            if not await self._confirmed(device, decision.amps):
                # Toch starten. De limiet die er dan staat is er een die de paal
                # eerder heeft aangenomen en ligt dus altijd onder zijn eigen
                # maximum, dus het is veilig. Niet starten zou betekenen dat een
                # auto de hele nacht leeg blijft omdat één sensor een andere
                # naam of een andere eenheid heeft dan verwacht, en dat is de
                # ene fout die een klant nooit vergeeft.
                _LOGGER.warning(
                    "laadpaal %s bevestigde de limiet van %s A niet; toch gestart",
                    device.get("id"),
                    decision.amps,
                )
            await self._command(device, control, "start")

        return True

    async def _limit(
        self, device: dict[str, Any], control: dict[str, Any], amps: int, minutes: int
    ) -> None:
        """De dynamische limiet zetten, met de houdbaarheid die erbij hoort.

        `minutes` is 0 voor "tot nader order". Dat is het gewone geval voor een
        limiet waarop geladen wordt: valt de coach weg, dan laadt de auto door op
        een stroom die de paal eerder heeft aangenomen, en dat is veilig. Voor
        een 0 ligt het andersom en staat de afweging bij `FOREVER_RULES`.
        """
        domain, service = control["limit_service"]
        await self.hass.services.async_call(
            domain,
            service,
            {
                "device_id": device["device_id"],
                control["limit_field"]: amps,
                control["ttl_field"]: minutes,
            },
            blocking=True,
        )

    async def _pause(
        self,
        device: dict[str, Any],
        control: dict[str, Any],
        charger: Charger,
        decision: Decision,
        now: datetime,
    ) -> bool:
        """Niet laden, en dat vasthouden zonder de sessie op te breken."""
        device_id = device.get("id", "")

        if not charger.connected or decision.rule in NO_WRITE_RULES:
            self._pause_until.pop(device_id, None)
            return True

        minutes = 0 if decision.rule in FOREVER_RULES else (decision.hold_minutes or 0)
        await self._limit(device, control, 0, minutes)

        if minutes:
            self._pause_until[device_id] = now + timedelta(minutes=minutes)
        else:
            self._pause_until.pop(device_id, None)
        return True

    async def _confirmed(self, device: dict[str, Any], amps: int) -> bool:
        """Wait until the charger reports the limit we just set."""
        entity_id = (device.get("entities") or {}).get("dynamic_limit")
        if not entity_id:
            # Nothing to check against, so fall back to giving it a moment.
            await self._sleep(2)
            return True

        for _ in range(CONFIRM_SECONDS):
            if (_number(self.hass, entity_id) or -1) >= amps - 0.5:
                return True
            await self._sleep(1)
        return False

    async def _sleep(self, seconds: float) -> None:
        """Waiting that a test can shortcut."""
        import asyncio

        await asyncio.sleep(seconds)

    async def _command(
        self, device: dict[str, Any], control: dict[str, Any], action: str
    ) -> None:
        """Start, stop or pause, in the word this installation uses."""
        domain, service = control["command_service"]
        word = (device.get("actions") or {}).get(action) or control["words"][action]
        await self.hass.services.async_call(
            domain,
            service,
            {"device_id": device["device_id"], control["command_field"]: word},
            blocking=True,
        )


@callback
def async_get_coach(hass: HomeAssistant) -> ChargerCoach:
    """The one coach for this Home Assistant."""
    data = hass.data.setdefault(DOMAIN, {})
    if "coach" not in data:
        data["coach"] = ChargerCoach(hass)
    return data["coach"]
