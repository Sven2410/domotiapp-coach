"""De eigen geschiedenis: per kwartier het laagste, de piek en het gemiddelde.

Home Assistant bewaart per uur een min, een gemiddelde en een max, en dat voor
altijd. Fijner dan een uur bestaat alleen binnen het opruimvenster van de
recorder, standaard tien dagen. Nagemeten bij een klant op 28-08-2026: de
uurstatistiek ging ruim vierhonderd dagen terug, de vijfminutenstatistiek
stopte na tien dagen en twee uur.

Een kwartier is fijn genoeg om te zien wat er op een dag gebeurde en grof
genoeg om twee jaar te bewaren zonder dat iemand het merkt. Per sensor komt dat
op 96 regels per dag, dus 70.080 voor twee jaar: **een kleine vier megabyte per
sensor voor de hele bewaartermijn.** Een back-up van Home Assistant neemt de
configuratiemap mee, en dat is precies waarom het een kwartier is en geen
seconde.

**Het gemiddelde is naar tijd gewogen en niet naar aantal metingen.** Dat is
geen fijnproeverij maar het enige eerlijke antwoord: hoe vaak een sensor zich
meldt verschilt per klant en per merk. De ene slimme meter meldt elke seconde,
de volgende elke dertig seconden, de derde elke minuut. Een waarde die een
halve minuut blijft staan telt hier dus een halve minuut mee, en niet één keer.
Zo betekent hetzelfde getal bij elke klant hetzelfde.

De piek is de hoogste waarde die de sensor zelf gemeld heeft. Die is dus zo
scherp als de meter van die klant is: meldt hij elke seconde, dan staat er een
secondepiek in een kwartierregel.

**Een waarde blijft gelden tot de volgende melding, hoe lang dat ook duurt.**
Er staat bewust geen tijdgrens op. Veel sensoren melden zich alleen als er iets
verandert: een laadpaal die niet laadt meldt uren niets, en een fasestroom in
hele ampères staat een halve avond op hetzelfde getal. Zou stilte na een paar
minuten als een gat gelden, dan zou een rustige nacht half leeg in de opslag
komen. Een sensor die werkelijk wegvalt zegt dat zelf: Home Assistant zet hem
op `unavailable`, en dan telt de tijd erna niet meer mee. Dat is dezelfde
aanname als de statistiek van Home Assistant zelf maakt.

Hoeveel seconden van een kwartier er werkelijk gedekt zijn staat in de regel,
zodat een gat te zien is in plaats van weggerekend.

Alles gaat als watt de opslag in, ongeacht wat de sensor zichzelf noemt. Zie
`units.py` voor wat dat een klant eerder gekost heeft.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_SETTINGS_UPDATED
from .storage import async_get_store
from .units import to_watts

_LOGGER = logging.getLogger(__name__)

# De lengte van een blok. Verander dit niet zonder na te denken over wat er met
# de regels gebeurt die er al staan: die zijn per kwartier en blijven dat.
BUCKET = timedelta(minutes=15)

# Hoe lang de regels blijven staan. Twee jaar, want dan kun je dit jaar met
# vorig jaar vergelijken en houdt het ergens op.
KEEP = timedelta(days=730)

# Hoe vaak er naar schijf geschreven wordt. Niet elk kwartier en al helemaal
# niet elke meting: op een Home Assistant die van een SD-kaart draait is elke
# schrijfbeurt slijtage. Wat nog niet weggeschreven is staat in het geheugen en
# gaat bij een herstart verloren; dat is hoogstens dit half uur.
FLUSH = timedelta(minutes=30)

# Eens per dag opruimen wat ouder is dan de bewaartermijn.
PURGE = timedelta(hours=24)

# Hoe ver er bij de eerste keer teruggehaald wordt uit wat Home Assistant zelf
# nog heeft. De recorder bewaart vijfminutenblokken zolang zijn opruimvenster
# duurt, standaard tien dagen; veertien vragen kost niets en pakt mee wat er bij
# een ruimere instelling nog ligt. Verder terug bestaat alleen per uur, en van
# uurblokken kwartieren maken zou getallen opleveren die nooit gemeten zijn.
CATCHUP = timedelta(days=14)

_TABEL = """
CREATE TABLE IF NOT EXISTS kwartieren (
    entity_id TEXT NOT NULL,
    start     INTEGER NOT NULL,
    laagste   REAL NOT NULL,
    piek      REAL NOT NULL,
    gemiddeld REAL NOT NULL,
    seconden  REAL NOT NULL,
    PRIMARY KEY (entity_id, start)
)
"""


def bucket_start(moment: datetime) -> datetime:
    """Het begin van het kwartier waar dit moment in valt."""
    return moment.replace(
        minute=moment.minute - moment.minute % 15, second=0, microsecond=0
    )


@dataclass
class _Lopend:
    """Wat er van dit kwartier tot nu toe bekend is, nog in het geheugen."""

    start: datetime
    laagste: float
    piek: float
    gewogen: float = 0.0
    seconden: float = 0.0

    def tel(self, waarde: float, seconden: float) -> None:
        """Een waarde die zo lang gegolden heeft erbij optellen."""
        self.laagste = min(self.laagste, waarde)
        self.piek = max(self.piek, waarde)
        self.gewogen += waarde * seconden
        self.seconden += seconden

    @property
    def gemiddeld(self) -> float:
        """Naar tijd gewogen, en anders de enige waarde die we zagen."""
        if self.seconden > 0:
            return self.gewogen / self.seconden
        return self.piek


@dataclass
class _Meter:
    """Eén sensor die gevolgd wordt."""

    entity_id: str
    waarde: float | None = None
    sinds: datetime | None = None
    lopend: _Lopend | None = None
    klaar: list[tuple[datetime, float, float, float, float]] = field(
        default_factory=list
    )

    def _open(self, start: datetime, waarde: float) -> _Lopend:
        return _Lopend(start=start, laagste=waarde, piek=waarde)

    def _sluit(self) -> None:
        """Het lopende kwartier wegleggen om straks weg te schrijven."""
        if self.lopend is None or self.lopend.seconden <= 0:
            self.lopend = None
            return
        self.klaar.append(
            (
                self.lopend.start,
                self.lopend.laagste,
                self.lopend.piek,
                self.lopend.gemiddeld,
                self.lopend.seconden,
            )
        )
        self.lopend = None

    def tot(self, moment: datetime) -> None:
        """De tijd tot dit moment meetellen met de waarde die er stond.

        Zo nodig over kwartiergrenzen heen, want een meter die een uur lang
        hetzelfde meldt hoort in vier regels te staan en niet in één.
        """
        if self.waarde is None or self.sinds is None or moment <= self.sinds:
            return

        einde = moment
        while self.sinds < einde:
            if self.lopend is None:
                self.lopend = self._open(bucket_start(self.sinds), self.waarde)
            grens = self.lopend.start + BUCKET
            tot = min(einde, grens)
            self.lopend.tel(self.waarde, (tot - self.sinds).total_seconds())
            self.sinds = tot
            if tot >= grens:
                self._sluit()

        self.sinds = moment

    def meet(self, moment: datetime, waarde: float) -> None:
        """Een nieuwe meting: eerst de tijd afsluiten, dan de waarde omzetten."""
        self.tot(moment)
        self.waarde = waarde
        self.sinds = moment
        if self.lopend is None:
            self.lopend = self._open(bucket_start(moment), waarde)
        else:
            self.lopend.laagste = min(self.lopend.laagste, waarde)
            self.lopend.piek = max(self.lopend.piek, waarde)

    def verloren(self, moment: datetime) -> None:
        """De sensor zegt niets bruikbaars meer; de tijd erna telt niet mee."""
        self.tot(moment)
        self.waarde = None
        self.sinds = None

    def oogst(self) -> list[tuple[datetime, float, float, float, float]]:
        """De afgesloten kwartieren ophalen en het mandje legen."""
        uit, self.klaar = self.klaar, []
        return uit


class Archive:
    """Houdt per kwartier bij wat elke gevolgde sensor deed, en bewaart dat."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Opzetten zonder de schijf of de toestand aan te raken."""
        self.hass = hass
        self._pad = Path(hass.config.path(f"{DOMAIN}_geschiedenis.db"))
        self._meters: dict[str, _Meter] = {}
        self._uit: list[Any] = []
        self._laatste_purge: datetime | None = None

    # --- opzetten en afbreken ---------------------------------------------

    async def async_start(self) -> None:
        """De tabel klaarzetten en gaan luisteren."""
        await self.hass.async_add_executor_job(self._maak_tabel)
        await self._async_volg()

        self._uit.append(
            self.hass.bus.async_listen(EVENT_SETTINGS_UPDATED, self._async_instellingen)
        )
        self._uit.append(
            async_track_time_interval(self.hass, self._async_wegschrijven, FLUSH)
        )

    def async_stop(self) -> None:
        """Alles loslaten. Wat nog in het geheugen staat gaat verloren."""
        for af in self._uit:
            af()
        self._uit = []

    # --- welke sensoren -----------------------------------------------------

    async def _async_instellingen(self, _event: Event | None = None) -> None:
        """De instellingen zijn gewijzigd, dus mogelijk ook wat er gevolgd wordt."""
        await self._async_volg()

    async def _async_volg(self) -> None:
        """Opnieuw bepalen welke sensoren erbij horen en daarop luisteren."""
        settings = await async_get_store(self.hass).async_load()
        wilde = self._wat_volgen(settings)

        # Wie eraf gaat wordt eerst netjes afgesloten, anders blijft er een half
        # kwartier in het geheugen hangen dat nooit meer weggeschreven wordt.
        nu = dt_util.as_local(dt_util.utcnow()).replace(tzinfo=None)
        for entity_id in list(self._meters):
            if entity_id not in wilde:
                self._meters[entity_id].verloren(nu)
                self._meters[entity_id]._sluit()

        nieuwe = [e for e in wilde if e not in self._meters]
        for entity_id in nieuwe:
            self._meters[entity_id] = _Meter(entity_id)
            self._lees(self._meters[entity_id], nu)

        if nieuwe:
            await self._async_inhalen(nieuwe, nu)

        # Eén luisteraar voor alles, opnieuw opgehangen. Losse luisteraars per
        # sensor bijhouden is meer boekhouding dan het waard is.
        for af in list(self._uit):
            if getattr(af, "_domotiapp_volgen", False):
                af()
                self._uit.remove(af)

        if wilde:
            af = async_track_state_change_event(
                self.hass, sorted(wilde), self._async_gemeten
            )
            af._domotiapp_volgen = True  # type: ignore[attr-defined]
            self._uit.append(af)

    @staticmethod
    def _wat_volgen(settings: dict[str, Any]) -> set[str]:
        """Elke vermogenssensor die het paneel kent.

        Het net, de zon en elk apparaat dat de klant gekoppeld heeft. Dat is
        precies de lijst die hij zelf heeft ingevuld, dus er komt nooit een
        sensor bij die hij niet kent, en er valt er nooit een af die hij wel
        wil zien.
        """
        bronnen = settings.get("sources") or {}
        uit = {
            bronnen.get("grid_import"),
            bronnen.get("grid_export"),
            bronnen.get("grid_signed"),
            bronnen.get("solar"),
        }
        for apparaat in settings.get("devices") or []:
            uit.add(apparaat.get("entity"))
        return {e for e in uit if e}

    # --- de inhaalslag bij de eerste keer -----------------------------------

    async def _async_inhalen(self, entity_ids: list[str], nu: datetime) -> None:
        """Wat Home Assistant zelf nog heeft alsnog overnemen.

        Anders begint de geschiedenis pas op de dag dat de klant bijwerkt, en
        dat is precies het moment waarop hij hem wil zien. De recorder heeft
        vijfminutenblokken met een min, een max en een gemiddelde staan, en drie
        daarvan zijn samen een kwartier. Dat zijn echte metingen, geen
        omgerekende uurwaarden, dus ze mogen hierin.

        Verder terug bestaat alleen per uur. Daar kwartieren van maken zou
        betekenen dat er getallen in de opslag komen die niemand gemeten heeft,
        en dat gebeurt niet. Voor alles vóór de inhaalslag blijft de uur-max van
        Home Assistant de bron.

        Loopt dit stuk, om wat voor reden dan ook, dan is dat geen ramp: dan
        begint de geschiedenis gewoon bij nu.
        """
        alleen_lege = await self.hass.async_add_executor_job(
            self._zonder_regels, entity_ids
        )
        if not alleen_lege:
            return

        try:
            rijen = await self._async_uit_recorder(alleen_lege, nu)
        except Exception as fout:  # noqa: BLE001 - de recorder-API wisselt per versie
            _LOGGER.debug("de inhaalslag ging niet door: %s", fout)
            return

        if rijen:
            await self.hass.async_add_executor_job(self._schrijf, rijen, False, nu)
            _LOGGER.info(
                "geschiedenis: %d kwartieren overgenomen uit Home Assistant voor %s",
                len(rijen),
                ", ".join(alleen_lege),
            )

    def _zonder_regels(self, entity_ids: list[str]) -> list[str]:
        """Welke van deze sensoren nog helemaal niets in de opslag hebben."""
        with sqlite3.connect(self._pad) as db:
            bezet = {
                rij[0]
                for rij in db.execute(
                    "SELECT DISTINCT entity_id FROM kwartieren WHERE entity_id IN "
                    f"({','.join('?' for _ in entity_ids)})",
                    entity_ids,
                )
            }
        return [e for e in entity_ids if e not in bezet]

    async def _async_uit_recorder(
        self, entity_ids: list[str], nu: datetime
    ) -> list[tuple[str, int, float, float, float, float]]:
        """De vijfminutenblokken van de recorder, samengevat per kwartier."""
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import (
            statistics_during_period,
        )

        begin = dt_util.as_utc(dt_util.as_local(nu - CATCHUP))
        einde = dt_util.as_utc(dt_util.as_local(nu))
        gevonden = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            begin,
            einde,
            set(entity_ids),
            "5minute",
            {"power": "W"},
            {"mean", "min", "max"},
        )

        return self.kwartieren_uit_blokjes(gevonden or {})

    @staticmethod
    def kwartieren_uit_blokjes(
        gevonden: dict[str, list[dict[str, Any]]]
    ) -> list[tuple[str, int, float, float, float, float]]:
        """Vijfminutenblokjes samenvatten tot kwartieren.

        Elk blokje beslaat evenveel tijd, dus het gemiddelde van de gemiddelden
        is hier het naar tijd gewogen gemiddelde. Ontbreekt er een blokje, dan
        is dat te zien aan de seconden en niet weggerekend.
        """
        emmers: dict[tuple[str, datetime], list[Any]] = {}
        for entity_id, blokjes in gevonden.items():
            for blokje in blokjes:
                gem = blokje.get("mean")
                if gem is None:
                    continue
                ruw = blokje["start"]
                moment = dt_util.as_local(
                    dt_util.utc_from_timestamp(ruw / 1000)
                    if isinstance(ruw, (int, float))
                    else ruw
                ).replace(tzinfo=None)
                sleutel = (entity_id, bucket_start(moment))
                emmer = emmers.setdefault(sleutel, [None, None, 0.0, 0.0])
                laag = blokje.get("min")
                hoog = blokje.get("max")
                laag = gem if laag is None else laag
                hoog = gem if hoog is None else hoog
                emmer[0] = laag if emmer[0] is None else min(emmer[0], laag)
                emmer[1] = hoog if emmer[1] is None else max(emmer[1], hoog)
                emmer[2] += float(gem) * 300.0
                emmer[3] += 300.0

        return [
            (
                entity_id,
                int(start.timestamp()),
                float(emmer[0]),
                float(emmer[1]),
                emmer[2] / emmer[3],
                emmer[3],
            )
            for (entity_id, start), emmer in sorted(emmers.items(), key=lambda p: p[0][1])
            if emmer[3] > 0
        ]

    # --- meten --------------------------------------------------------------

    def _lees(self, meter: _Meter, nu: datetime) -> None:
        """De stand van nu ophalen, zodat een verse sensor niet leeg begint."""
        self._verwerk(meter, self.hass.states.get(meter.entity_id), nu)

    @staticmethod
    def _verwerk(meter: _Meter, state: State | None, nu: datetime) -> None:
        """Eén toestand in de meter verwerken, of hem als gat aanmerken."""
        if state is None or state.state in ("unknown", "unavailable", ""):
            meter.verloren(nu)
            return
        try:
            ruw = float(state.state)
        except (TypeError, ValueError):
            meter.verloren(nu)
            return
        watt = to_watts(ruw, state.attributes.get("unit_of_measurement"))
        if watt is None:
            meter.verloren(nu)
            return
        meter.meet(nu, watt)

    @callback
    def _async_gemeten(self, event: Event) -> None:
        """Een sensor meldde zich."""
        meter = self._meters.get(event.data.get("entity_id"))
        if meter is None:
            return
        nu = dt_util.as_local(event.time_fired).replace(tzinfo=None)
        self._verwerk(meter, event.data.get("new_state"), nu)

    # --- wegschrijven -------------------------------------------------------

    async def _async_wegschrijven(self, _now: datetime | None = None) -> None:
        """De afgesloten kwartieren naar schijf, en af en toe opruimen."""
        nu = dt_util.as_local(dt_util.utcnow()).replace(tzinfo=None)
        rijen: list[tuple[str, int, float, float, float, float]] = []
        for meter in self._meters.values():
            meter.tot(nu)
            for start, laagste, piek, gemiddeld, seconden in meter.oogst():
                rijen.append(
                    (
                        meter.entity_id,
                        int(start.timestamp()),
                        laagste,
                        piek,
                        gemiddeld,
                        seconden,
                    )
                )

        opruimen = self._laatste_purge is None or nu - self._laatste_purge >= PURGE
        if opruimen:
            self._laatste_purge = nu

        if not rijen and not opruimen:
            return

        try:
            await self.hass.async_add_executor_job(self._schrijf, rijen, opruimen, nu)
        except sqlite3.Error as fout:
            # Een volle schijf of een stukke database mag de coach niet stoppen:
            # sturen is belangrijker dan bijhouden.
            _LOGGER.warning("de geschiedenis kon niet worden weggeschreven: %s", fout)

    def _maak_tabel(self) -> None:
        with sqlite3.connect(self._pad) as db:
            db.execute(_TABEL)

    def _schrijf(self, rijen: list[Any], opruimen: bool, nu: datetime) -> None:
        with sqlite3.connect(self._pad) as db:
            if rijen:
                # Vervangen en niet negeren: draait dit twee keer over hetzelfde
                # kwartier, dan is de laatste versie de volledigste.
                db.executemany(
                    "INSERT OR REPLACE INTO kwartieren "
                    "(entity_id, start, laagste, piek, gemiddeld, seconden) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    rijen,
                )
            if opruimen:
                grens = int((nu - KEEP).timestamp())
                db.execute("DELETE FROM kwartieren WHERE start < ?", (grens,))

    # --- teruglezen ---------------------------------------------------------

    async def async_lees(
        self, entity_ids: list[str], start: datetime, einde: datetime
    ) -> dict[str, list[dict[str, float]]]:
        """De kwartieren van deze sensoren tussen twee momenten."""
        # Eerst wegschrijven wat er nog in het geheugen staat, anders mist het
        # rapport van vandaag het laatste half uur.
        await self._async_wegschrijven()
        try:
            return await self.hass.async_add_executor_job(
                self._lees_rijen, entity_ids, start, einde
            )
        except sqlite3.Error as fout:
            _LOGGER.warning("de geschiedenis kon niet worden gelezen: %s", fout)
            return {}

    def _lees_rijen(
        self, entity_ids: list[str], start: datetime, einde: datetime
    ) -> dict[str, list[dict[str, float]]]:
        uit: dict[str, list[dict[str, float]]] = {e: [] for e in entity_ids}
        if not entity_ids:
            return uit
        vragen = ",".join("?" for _ in entity_ids)
        with sqlite3.connect(self._pad) as db:
            for rij in db.execute(
                f"SELECT entity_id, start, laagste, piek, gemiddeld, seconden "
                f"FROM kwartieren WHERE entity_id IN ({vragen}) "
                f"AND start >= ? AND start < ? ORDER BY start",
                (*entity_ids, int(start.timestamp()), int(einde.timestamp())),
            ):
                uit[rij[0]].append(
                    {
                        "start": rij[1],
                        "laagste": rij[2],
                        "piek": rij[3],
                        "gemiddeld": rij[4],
                        "seconden": rij[5],
                    }
                )
        return uit


@callback
def async_get_archive(hass: HomeAssistant) -> Archive:
    """De ene geschiedenis van deze installatie."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    archive = domain_data.get("archive")
    if archive is None:
        archive = domain_data["archive"] = Archive(hass)
    return archive
