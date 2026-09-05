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
from homeassistant.helpers.start import async_at_started
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

# Hoe lang er geprobeerd wordt de inhaalslag alsnog te doen. Bij het opstarten
# van Home Assistant is de recorder er vaak nog niet, en dat is precies wanneer
# deze code voor het eerst draait. Na een dag houdt het op: de blokjes van toen
# zijn dan toch opgeruimd.
CATCHUP_GIVE_UP = timedelta(hours=24)

# Hoe ver terug er na een herstart naar gaten gezocht wordt, vanaf hoeveel
# seconden een kwartier als vol geldt, en hoe lang er na de start nog elke
# ronde naar gaten gekeken wordt (de recorder maakt zijn blokjes per vijf
# minuten, dus het laatste uur is pas na een tijdje compleet).
GATEN_VENSTER = timedelta(hours=24)
GAT = 840.0
GATEN_NA_START = timedelta(hours=2)

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


# Vóór deze datum bestond er geen meting die hier thuishoort. Een tijdstempel
# die eronder valt komt uit een rekenfout en niet uit een meter.
ONDERGRENS = datetime(2015, 1, 1)


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
        # Wat er nog uit Home Assistant overgenomen moet worden, en sinds
        # wanneer dat probeersel loopt. Zie `_async_inhalen`.
        self._inhalen: set[str] = set()
        self._inhalen_sinds: datetime | None = None
        self._inhalen_gemeld = False
        # Wanneer deze start was, voor het aanvullen van gaten rond een
        # herstart. Zie `_async_gaten_vullen`.
        self._gestart: datetime | None = None
        self._gaten_gemeld = False

    # --- opzetten en afbreken ---------------------------------------------

    async def async_start(self) -> None:
        """De tabel klaarzetten en gaan luisteren."""
        await self.hass.async_add_executor_job(self._maak_tabel)
        await self._async_volg()

        # De inhaalslag pas als Home Assistant helemaal op is. Deze code draait
        # bij het opstarten, en dan is de recorder er vaak nog niet; dat was op
        # 28-08-2026 precies waarom er bij de eerste klant niets overgenomen
        # werd. Draait hij al, dan gaat dit meteen af.
        self._uit.append(async_at_started(self.hass, self._async_opgestart))

        self._uit.append(
            self.hass.bus.async_listen(EVENT_SETTINGS_UPDATED, self._async_instellingen)
        )
        self._uit.append(
            async_track_time_interval(self.hass, self._async_wegschrijven, FLUSH)
        )
        # Gaat Home Assistant uit, dan eerst alles naar schijf, ook het
        # lopende kwartier. Anders raakt tot een half uur kwijt, plus het
        # kwartier waar we in zaten. Bij Van den Dam kostte dat op 05-09-2026
        # bij vijf herstarten samen zes van de vijftig kilowattuur van een
        # laadbeurt: kwartier 10:30 ontbrak, 13:45 had 44 seconden.
        self._uit.append(
            self.hass.bus.async_listen_once("homeassistant_stop", self._async_afsluiten)
        )
        self._gestart = dt_util.as_local(dt_util.utcnow()).replace(tzinfo=None)

    async def _async_afsluiten(self, _event: Event | None = None) -> None:
        """Home Assistant gaat uit: alles wat in het geheugen staat naar schijf."""
        await self._async_wegschrijven(None, alles=True)

    def async_stop(self) -> None:
        """Alles loslaten. Wat nog in het geheugen staat gaat verloren."""
        for af in self._uit:
            af()
        self._uit = []

    # --- welke sensoren -----------------------------------------------------

    async def _async_opgestart(self, _hass: HomeAssistant | None = None) -> None:
        """Home Assistant is helemaal op; nu pas kan de recorder bevraagd worden."""
        nu = dt_util.as_local(dt_util.utcnow()).replace(tzinfo=None)
        await self._async_inhalen(nu)
        await self._async_gaten_vullen(nu)

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
            self._inhalen.update(nieuwe)
            if self._inhalen_sinds is None:
                self._inhalen_sinds = nu
            await self._async_inhalen(nu)

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

    async def _async_inhalen(self, nu: datetime) -> None:
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
        if not self._inhalen:
            return

        # Na een dag proberen houdt het op. Wat er dan nog niet is, komt er niet
        # meer: de vijfminutenblokken van toen zijn inmiddels opgeruimd.
        if self._inhalen_sinds is not None and nu - self._inhalen_sinds > CATCHUP_GIVE_UP:
            _LOGGER.warning(
                "geschiedenis: de inhaalslag is opgegeven voor %s; "
                "de geschiedenis begint vanaf nu",
                ", ".join(sorted(self._inhalen)),
            )
            self._inhalen.clear()
            return

        alleen_lege = await self.hass.async_add_executor_job(
            self._zonder_regels, sorted(self._inhalen)
        )
        if not alleen_lege:
            self._inhalen.clear()
            return

        try:
            rijen = await self._async_uit_recorder(alleen_lege, nu)
        except Exception as fout:  # noqa: BLE001 - de recorder-API wisselt per versie
            # Eén keer melden en dan blijven proberen. Bij het opstarten van
            # Home Assistant is de recorder er vaak nog niet, en dat is precies
            # het moment waarop deze code voor het eerst draait; dat is dus een
            # reden om het straks nog eens te doen en niet om te stoppen.
            if not self._inhalen_gemeld:
                self._inhalen_gemeld = True
                _LOGGER.warning(
                    "geschiedenis: de inhaalslag lukte nog niet (%s); "
                    "hij wordt bij de volgende ronde opnieuw geprobeerd",
                    fout,
                )
            return

        if rijen:
            await self.hass.async_add_executor_job(self._schrijf, rijen, False, nu)
            _LOGGER.info(
                "geschiedenis: %d kwartieren overgenomen uit Home Assistant voor %s",
                len(rijen),
                ", ".join(alleen_lege),
            )
        self._inhalen.difference_update(alleen_lege)

    # --- gaten rond een herstart --------------------------------------------

    async def _async_gaten_vullen(self, nu: datetime) -> None:
        """Kwartieren die ontbreken of half zijn alsnog uit de recorder halen.

        Bij een herstart van Home Assistant raakte tot een half uur aan
        kwartieren kwijt (zie `_async_afsluiten`), en wat er vóór deze versie
        al kwijt was komt zo alsnog terug. De recorder heeft van dezelfde
        sensoren vijfminutenblokken; die zijn grover dan de eigen meting maar
        wel echt gemeten, en drie ervan zijn een heel kwartier. Alleen
        kwartieren die er niet zijn of korter dan `GAT` gedekt zijn worden
        vervangen, en alleen door een regel die méér seconden dekt.
        """
        ids = sorted(self._meters)
        if not ids:
            return
        # De laatste twee kwartieren niet: daar is de recorder zelf nog niet
        # klaar mee, en daar loopt de eigen meting nog.
        tot = bucket_start(nu) - BUCKET
        van = nu - GATEN_VENSTER
        try:
            bestaand = await self.hass.async_add_executor_job(
                self._lees_seconden, ids, van, tot
            )
        except sqlite3.Error as fout:
            _LOGGER.warning("de geschiedenis kon niet worden gelezen: %s", fout)
            return
        kandidaten = self.gaten(ids, bestaand, van, tot)
        if not kandidaten:
            return
        vroegste = datetime.fromtimestamp(min(start for _, start in kandidaten))
        try:
            rijen = await self._async_uit_recorder_tussen(ids, vroegste, tot + BUCKET)
        except Exception as fout:  # noqa: BLE001 - de recorder-API wisselt per versie
            if not self._gaten_gemeld:
                self._gaten_gemeld = True
                _LOGGER.warning("geschiedenis: gaten aanvullen lukte nog niet (%s)", fout)
            return
        aanvullen = self.aanvullingen(kandidaten, bestaand, rijen)
        if not aanvullen:
            return
        try:
            await self.hass.async_add_executor_job(self._schrijf, aanvullen, False, nu)
        except sqlite3.Error as fout:
            _LOGGER.warning("de geschiedenis kon niet worden weggeschreven: %s", fout)
            return
        _LOGGER.info("geschiedenis: %d kwartieren aangevuld uit Home Assistant", len(aanvullen))

    def _lees_seconden(
        self, entity_ids: list[str], van: datetime, tot: datetime
    ) -> dict[tuple[str, int], float]:
        """Per kwartier hoeveel seconden er al gedekt zijn."""
        vragen = ",".join("?" for _ in entity_ids)
        with sqlite3.connect(self._pad) as db:
            return {
                (rij[0], int(rij[1])): float(rij[2])
                for rij in db.execute(
                    f"SELECT entity_id, start, seconden FROM kwartieren "
                    f"WHERE entity_id IN ({vragen}) AND start >= ? AND start < ?",
                    (*entity_ids, int(van.timestamp()), int(tot.timestamp())),
                )
            }

    @staticmethod
    def gaten(
        entity_ids: list[str],
        bestaand: dict[tuple[str, int], float],
        van: datetime,
        tot: datetime,
    ) -> set[tuple[str, int]]:
        """Welke kwartieren tussen `van` en `tot` ontbreken of half zijn."""
        uit: set[tuple[str, int]] = set()
        start = bucket_start(van)
        while start < tot:
            stempel = int(start.timestamp())
            for entity_id in entity_ids:
                if bestaand.get((entity_id, stempel), 0.0) < GAT:
                    uit.add((entity_id, stempel))
            start += BUCKET
        return uit

    @staticmethod
    def aanvullingen(
        kandidaten: set[tuple[str, int]],
        bestaand: dict[tuple[str, int], float],
        rijen: list[tuple[str, int, float, float, float, float]],
    ) -> list[tuple[str, int, float, float, float, float]]:
        """Alleen de gevraagde kwartieren, en alleen als de recorder meer dekt."""
        return [
            rij for rij in rijen
            if (rij[0], rij[1]) in kandidaten and rij[5] > bestaand.get((rij[0], rij[1]), 0.0)
        ]

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
        return await self._async_uit_recorder_tussen(entity_ids, nu - CATCHUP, nu)

    async def _async_uit_recorder_tussen(
        self, entity_ids: list[str], van: datetime, tot: datetime
    ) -> list[tuple[str, int, float, float, float, float]]:
        """De vijfminutenblokken tussen twee lokale momenten, per kwartier."""
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import (
            statistics_during_period,
        )

        # Naïef lokaal. `as_local` van Home Assistant leest een naïeve tijd
        # als UTC, dus die eerst een tijdzone geven en dan pas omrekenen.
        einde = dt_util.as_utc(tot.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE))
        begin = dt_util.as_utc(van.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE))
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
                # De recorder geeft hier seconden sinds 1970, als kommagetal.
                # Het websocketcommando van Home Assistant geeft voor hetzelfde
                # veld milliseconden, en die vorm had ik overgenomen. Daardoor
                # kwamen alle kwartieren in januari 1970 terecht en veegde de
                # eerste opruimronde ze meteen weer weg: nul regels, geen fout,
                # niets in het logboek. Gevonden bij de eerste klant op
                # 28-08-2026, door de broncode van zijn HA-versie erbij te halen.
                moment = dt_util.as_local(
                    dt_util.utc_from_timestamp(ruw)
                    if isinstance(ruw, (int, float))
                    else ruw
                ).replace(tzinfo=None)
                begin = bucket_start(moment)
                if begin < ONDERGRENS:
                    # Een tijdstempel die nergens op slaat is geen meting. Liever
                    # overslaan dan een regel wegschrijven die niemand kan
                    # plaatsen; precies deze regel had de fout hierboven meteen
                    # aan het licht gebracht.
                    continue
                sleutel = (entity_id, begin)
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

    async def _async_wegschrijven(
        self, _now: datetime | None = None, alles: bool = False
    ) -> None:
        """De afgesloten kwartieren naar schijf, en af en toe opruimen.

        Met `alles` ook het lopende kwartier, als een halve regel: dat is
        voor het uitgaan van Home Assistant. Een halve regel is beter dan
        geen, en `_async_gaten_vullen` maakt hem straks vol als de recorder
        meer heeft.
        """
        nu = dt_util.as_local(dt_util.utcnow()).replace(tzinfo=None)
        rijen: list[tuple[str, int, float, float, float, float]] = []
        for meter in self._meters.values():
            meter.tot(nu)
            if alles:
                meter._sluit()
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

        # De recorder is bij het opstarten vaak nog niet zover, en juist dan
        # draait de inhaalslag voor het eerst. Dus elke ronde nog een poging.
        await self._async_inhalen(nu)
        # En de gaten rond de herstart, zolang de recorder zijn blokjes van
        # het laatste uur nog aan het maken is.
        if not alles and self._gestart is not None and nu - self._gestart <= GATEN_NA_START:
            await self._async_gaten_vullen(nu)

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
