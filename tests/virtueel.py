"""Een virtueel huis waarin de coach een hele laadbeurt kan draaien.

De proeven in `test_coach.py` zijn foto's: een sensor krijgt een waarde, de
coach doet één ronde, en er wordt gekeken wat hij zei. Dit is de film. Er is
een zon die opkomt en ondergaat, een huis dat kookt, een auto die voller wordt
van wat de paal hem geeft, een meter die dat allemaal ziet, en een prijslijst
die om één uur 's middags de dag van morgen leert. De coach draait er elke
minuut een gewone ronde in, met zijn echte code, en krijgt alleen terug wat
zijn opdrachten in dat huis teweegbrengen.

Waarom dit bestaat: tot 04-09-2026 kon een laadbeurt alleen beproefd worden
met een lege bus aan een echte paal, in die woning of bij een klant. De eigenaar: "ik wil
nu echt een werkend product maken." Hier draait een nacht in seconden.

Wat er wél echt is: `coach.py`, `planner.py`, `storage.py` en de vertaling van
sensoren naar besluiten. Wat er nagemaakt is: Home Assistant (zie
`harnas.py`), en de wereld eromheen (dit bestand).

    python tests/virtueel.py                  # lijst van scenario's
    python tests/virtueel.py vast-zonnig      # één scenario, met tijdlijn per minuut
    python tests/virtueel.py vast-zonnig kort # dezelfde tijdlijn in blokken
    python tests/virtueel.py alles            # alle scenario's, alleen de uitkomst

De scenario's zelf staan in `scenarios.py`; de controles erop in
`test_virtueel.py`.
"""

import asyncio
import calendar
import dataclasses
import datetime as dt
import math
import random
import sys
from dataclasses import dataclass, field

from harnas import *  # noqa: F401,F403

VOLT = 230
MIN_AMPS = planner.MIN_AMPS


# --- de zon -----------------------------------------------------------------


@dataclass
class Zon:
    """Wat het dak doet, en wat de voorspeller ervan zegt.

    `wolken` is het weer dat er werkelijk is; `voorspeld` is wat de voorspeller
    de dag ervoor dacht. Zijn ze gelijk, dan klopt de voorspelling. Het verschil
    ertussen is precies wat een coach die op een verwachting plant moet kunnen
    hebben.
    """

    piek_kw: float = 6.0        # een helder middaguur, aan de omvormer
    opkomst: float = 7.0        # uur van de dag, september
    onder: float = 19.75
    wolken: str = "helder"      # helder | bewolkt | wisselend | middag-dicht | geen
    voorspeld: str | None = None  # None: de voorspelling klopt
    # Het echte weer per dag, geteld vanaf de eerste dag van het scenario:
    # {0: "bewolkt", 1: "helder"}. Waar niets staat geldt `wolken`. De
    # voorspelling blijft `voorspeld`, dus hiermee is een dag te maken waarop de
    # voorspeller er flink naast zat en een dag waarop hij klopt. Dat is nodig
    # om te zien of een meting van gisteren de zon van vandaag met rust laat;
    # zie `solar_day` in planner.py.
    wolken_per_dag: dict = field(default_factory=dict)
    zaad: int = 1
    # Een echte uurkromme, kWh per uur van de dag, zoals het energiedashboard
    # hem geeft. Dan is dit het heldere dak en niet de sinus; `wolken` en
    # `voorspeld` werken er net zo op. Voor een scenario dat een echte woning
    # nabouwt, zoals de klantwoning op 04-09-2026.
    kromme: dict[int, float] | None = None
    # Een opklaring van een paar minuten die de voorspeller niet ziet: (van,
    # tot, kW aan de omvormer). In die woning op 11-09-2026 ging het dak om 09:35
    # van 1,1 naar 3,0 kW, en twee minuten later weer naar 1,2.
    pieken: list[tuple[str, str, float]] = field(default_factory=list)
    # De eerste dag van het scenario, gezet door `Wereld`; alleen nodig om
    # `wolken_per_dag` te kunnen tellen.
    eerste_dag: dt.date | None = None

    # "half": de voorspeller zag de helft van wat het dak deed, zoals in een echte woning
    # op 08-09-2026 (Forecast.Solar 1,0 tot 1,7 kWh per uur, het dak 1,9 tot 4,4).
    PATRONEN = {"helder": 1.0, "half": 0.5, "bewolkt": 0.3, "geen": 0.0}

    def helder_kw(self, moment: dt.datetime) -> float:
        u = moment.hour + moment.minute / 60 + moment.second / 3600
        if self.kromme is not None:
            # Het gemiddelde van een uur hoort in het midden van dat uur; daar
            # tussen rechtdoor, zodat de minuten geen trap zijn.
            links = int(u - 0.5) if u >= 0.5 else -1
            a = self.kromme.get(links, 0.0) if links >= 0 else 0.0
            b = self.kromme.get(links + 1, 0.0) if links + 1 <= 23 else 0.0
            f = u - 0.5 - links
            return max(0.0, a + (b - a) * f)
        if not self.opkomst < u < self.onder:
            return 0.0
        x = (u - self.opkomst) / (self.onder - self.opkomst)
        return self.piek_kw * math.sin(math.pi * x) ** 1.6

    def factor(self, moment: dt.datetime, patroon: str, verwacht: bool = False) -> float:
        if patroon in self.PATRONEN:
            return self.PATRONEN[patroon]
        if patroon == "middag-dicht":
            return 1.0 if moment.hour < 13 else 0.25
        if patroon == "wisselend":
            # De voorspeller ziet een gemiddelde; de werkelijkheid wisselt per
            # twintig minuten tussen zon en wolk, vast per dag en per blok.
            if verwacht:
                return 0.7
            blok = (moment.toordinal(), moment.hour, moment.minute // 20)
            return 1.0 if random.Random(f"{self.zaad}-{blok}").random() < 0.6 else 0.3
        raise ValueError(f"onbekend weer: {patroon}")

    def weer_op(self, moment: dt.datetime) -> str:
        """Het echte weer op deze dag; `wolken` als er niets per dag staat."""
        if not self.wolken_per_dag or self.eerste_dag is None:
            return self.wolken
        return self.wolken_per_dag.get((moment.date() - self.eerste_dag).days, self.wolken)

    def nu_kw(self, moment: dt.datetime) -> float:
        u = moment.hour + moment.minute / 60 + moment.second / 3600
        for van, tot, kw in self.pieken:
            if _uur(van) <= u < _uur(tot):
                return kw
        return self.helder_kw(moment) * self.factor(moment, self.weer_op(moment))

    def verwacht_kwh(self, uur: dt.datetime) -> float:
        """Wat de voorspeller voor dit hele uur zegt, in kWh."""
        patroon = self.voorspeld or self.wolken
        stappen = 12
        som = 0.0
        for i in range(stappen):
            t = uur + dt.timedelta(minutes=60 * i / stappen)
            som += self.helder_kw(t) * self.factor(t, patroon, verwacht=True)
        return som / stappen

    def piek_moment(self, dag: dt.date) -> dt.datetime:
        if self.kromme:
            top = max(self.kromme, key=self.kromme.get)
            return dt.datetime.combine(dag, dt.time(0)) + dt.timedelta(hours=top + 0.5)
        midden = (self.opkomst + self.onder) / 2
        return dt.datetime.combine(dag, dt.time(0)) + dt.timedelta(hours=midden)


# --- het huis ----------------------------------------------------------------


@dataclass
class Huis:
    """Wat het huis zelf gebruikt, per moment van de dag."""

    basis_w: float = 250.0
    ochtend_w: float = 800.0    # 07:00-08:30
    koken_w: float = 2000.0     # 17:30-19:00
    avond_w: float = 400.0      # 19:00-23:00
    # Extra verbruik alleen op de dag van de proef: ("10:00", "11:00", 1500).
    extra: list[tuple[str, str, float]] = field(default_factory=list)
    # Hoe het verbruik over de fasen valt. Koken zit op de eerste.
    verdeling: tuple[float, float, float] = (0.5, 0.3, 0.2)
    # Een echt profiel, watt per uur van de dag, in plaats van basis, ochtend,
    # koken en avond. Uit de mediaan van een echte woning; zie de klantwoning in
    # scenarios.py.
    profiel: dict[int, float] | None = None
    # Een last die elke zoveel minuten kort aanstaat: (watt, seconden, elke
    # minuten). In de eerste woning op 22-09-2026 elk uur 1,7 tot 5,3 kW, 30
    # tot 50 s lang, ook 's nachts, ongeveer 54 minuten uit elkaar; een boiler
    # of een warmtepomp, zei de eigenaar. Elke sturing op de meter schiet daar
    # op door als hij niet oppast.
    puls: tuple[float, float, float] | None = None

    def watt(self, moment: dt.datetime, dag_offset: int = 0) -> float:
        u = moment.hour + moment.minute / 60
        puls_w = 0.0
        if self.puls is not None:
            watt_p, seconden, elke = self.puls
            minuut = moment.hour * 60 + moment.minute + moment.second / 60
            if (minuut % elke) * 60 < seconden:
                puls_w = watt_p
        if self.profiel is not None:
            w = self.profiel.get(moment.hour, self.basis_w)
        else:
            w = self.basis_w
            if 7.0 <= u < 8.5:
                w += self.ochtend_w
            if 17.5 <= u < 19.0:
                w += self.koken_w
            if 19.0 <= u < 23.0:
                w += self.avond_w
        if dag_offset == 0:
            for van, tot, extra in self.extra:
                if _uur(van) <= u < _uur(tot):
                    w += extra
        else:
            # Andere dagen wijken wat af, anders is een mediaan geen mediaan.
            w *= 1.0 + 0.15 * math.sin(dag_offset * 1.7 + u)
        return w + puls_w

    def per_fase(self, watt: float, fasen: int) -> list[float]:
        if fasen == 1:
            return [watt]
        return [watt * deel for deel in self.verdeling]


def _uur(tekst: str) -> float:
    h, m = tekst.split(":")
    return int(h) + int(m) / 60


# --- de auto -----------------------------------------------------------------


@dataclass
class Auto:
    """Een auto aan de kabel, met de eigenaardigheden die er in het echt zijn."""

    naam: str = "Bus"
    capaciteit_kwh: float = 19.7
    soc: float = 30.0
    fasen: int = 1
    max_amps: float = 16.0
    # Onder deze stroom komt hij niet op gang. de eigen Ford wil 10 A om wakker te
    # worden en doet daarna op 6 A gewoon mee; zie `WAKE_AMPS` in planner.py.
    wek_amps: float = 6.0
    laadgrens: float = 100.0
    # Tot hoever de bewoner deze auto wil laden: `target_percent` in het
    # autoprofiel. Iets anders dan `laadgrens` hierboven, dat is wat de auto
    # zelf doet. Staan ze gelijk, dan weet de coach waar de beurt eindigt in
    # plaats van het achteraf te merken; staat het doel hoger, dan loopt hij
    # tegen de grens van de auto aan zoals altijd.
    doel: float = 100.0
    meldt_soc: bool = True
    rendement: float = 0.9
    aanloop_s: int = 60
    # Zo lang doet zijn app erover om een nieuw percentage te laten zien.
    soc_vertraging_min: int = 0
    # In stappen van zoveel procent meldt hij zijn accustand. de eigen Ford doet
    # tien: 31, 40, 50, 60, 70, 80, ongeveer elk half uur. Tussen twee stappen
    # staat het beeld van de coach stil terwijl de auto voller wordt; zie
    # `_soc_bijgeteld` in coach.py.
    soc_stap: float = 1.0
    # Vanaf dit percentage neemt de auto zelf gas terug: daarboven neemt hij
    # nog `afbouw_deel` van zijn maximum. De eigenaar op 06-09-2026: "bepaalde auto's
    # schroeven vanaf een bepaald procent zelf hun doorlaatbaarheid terug."
    afbouw_vanaf: float | None = None
    afbouw_deel: float = 0.5
    # Zoveel ampère trekt hij bóven de limiet die hij krijgt. De Ford bij Van
    # den Dam trok op 06-09-2026 16,9 A op een limiet van 16 op één fase.
    overschot_amps: float = 0.0
    # Een auto die een herstart van de paal midden in de sessie niet verdraagt:
    # hij gaat in storing en laat de paal "completed" melden. Uit die storing
    # komt hij alleen met een nieuw startcommando, en daar doet hij zo veel
    # minuten over (de Ford: negen, van 05:18 tot 05:27).
    storing_bij_herstart: bool = False
    storing_herstel_min: int = 9
    # Een auto die na een lange verlaging niet meteen terugkomt. De Ford bij Van
    # den Dam, nacht van 18 op 19-09-2026: na negen en na zestien minuten op
    # 7 tot 9 A bleef hij op 16 A nog negen (01:35 tot 01:44) en elf minuten
    # (03:33 tot 03:44) op de oude stroom hangen; na een dip van een minuut
    # kwam hij binnen een halve minuut terug. Nul is een auto die meteen volgt.
    bijkomen_min: int = 0
    bijkomen_na_min: int = 5

    # toestand
    trekt_amps: float = 0.0
    wakker: bool = False
    klaar: bool = False
    aanloop: int = 0
    soc_gemeld: list = field(default_factory=list)
    storing: bool = False
    herstel_op: dt.datetime | None = None
    vorig_aanbod: float = 0.0
    laag_sinds: dt.datetime | None = None
    vast_tot: dt.datetime | None = None
    vast_amps: float = 0.0

    def stap(self, aanbod_amps: float, gestart: bool, stap_s: int = 60,
             nu: dt.datetime | None = None, fasen: int = 3) -> None:
        if self.storing:
            self.trekt_amps = 0.0
            if self.herstel_op is not None and nu is not None and nu >= self.herstel_op:
                self.storing = False
                self.herstel_op = None
                self.wakker = False
            else:
                return
        if self.soc >= self.laadgrens - 1e-9:
            self.klaar = True
        if self.klaar:
            self.trekt_amps = 0.0
            return
        if not gestart or aanbod_amps < MIN_AMPS:
            self.trekt_amps = 0.0
            self.wakker = False
            return
        if not self.wakker:
            if aanbod_amps < self.wek_amps:
                self.trekt_amps = 0.0
                return
            self.wakker = True
            self.aanloop = -(-self.aanloop_s // stap_s)
        if self.aanloop > 0:
            self.aanloop -= 1
            self.trekt_amps = 0.0
            return
        kan = self.max_amps
        if self.afbouw_vanaf is not None and self.soc >= self.afbouw_vanaf:
            kan = max(MIN_AMPS, self.max_amps * self.afbouw_deel)
        # Het overschot komt bovenop wat hij krijgt, ook boven zijn eigen
        # maximum: de Ford trok 16,9 A waar 16 het maximum van de paal was.
        # Alleen op één fase; op drie bleef dezelfde Ford met 14,4 A onder de 16.
        doel = min(aanbod_amps, kan)
        if self.bijkomen_min and nu is not None:
            if aanbod_amps < self.vorig_aanbod - 0.5:
                self.laag_sinds = nu
            elif aanbod_amps > self.vorig_aanbod + 0.5:
                if (self.laag_sinds is not None and self.trekt_amps > 0
                        and nu - self.laag_sinds >= dt.timedelta(minutes=self.bijkomen_na_min)):
                    self.vast_tot = nu + dt.timedelta(minutes=self.bijkomen_min)
                    self.vast_amps = self.trekt_amps
                self.laag_sinds = None
            self.vorig_aanbod = aanbod_amps
            if self.vast_tot is not None and nu < self.vast_tot:
                doel = min(doel, self.vast_amps)
            else:
                self.vast_tot = None
        self.trekt_amps = doel + (self.overschot_amps if fasen == 1 else 0.0)

    def start_ontvangen(self, nu: dt.datetime) -> None:
        """De paal stuurde een start. In storing telt vanaf nu het herstel."""
        if self.storing and self.herstel_op is None:
            self.herstel_op = nu + dt.timedelta(minutes=self.storing_herstel_min)

    def ga_in_storing(self) -> None:
        self.storing = True
        self.herstel_op = None
        self.trekt_amps = 0.0
        self.wakker = False

    def laad(self, kwh_aan_de_stekker: float) -> None:
        self.soc = min(
            100.0,
            self.soc + kwh_aan_de_stekker * self.rendement / self.capaciteit_kwh * 100,
        )

    def gemelde_soc(self, nu: dt.datetime) -> float | None:
        if not self.meldt_soc:
            return None
        stap = max(1.0, self.soc_stap)
        self.soc_gemeld.append((nu, int(self.soc // stap * stap)))
        grens = nu - dt.timedelta(minutes=self.soc_vertraging_min)
        oud = [s for t, s in self.soc_gemeld if t <= grens]
        return oud[-1] if oud else self.soc_gemeld[0][1]


# --- de laadpaal -------------------------------------------------------------


@dataclass
class Paal:
    """Een Easee-achtige paal: een dynamische limiet met houdbaarheid, en
    start/pauze als opdracht.

    Met `merk="alfen"` een Alfen zoals de integratie alfen_modbus hem laat
    zien (23-09-2026): de limiet is een number-entiteit zonder houdbaarheid,
    er is geen start- of stopwoord (een limiet boven de ondergrens is de
    start), en de paal vergeet zijn limiet na `geldig_s` en valt dan terug op
    zijn veilige stroom, zoals de echte na zijn "Modbus slave max current
    valid time". De status komt niet uit één sensor maar uit "auto
    aangesloten", "auto laadt" en de modus 3-toestand.
    """

    merk: str = "easee"
    geldig_s: int = 300
    veilig_amps: float = 16.0
    geschreven_op: dt.datetime | None = None
    max_amps: float = 16.0
    fasen: int = 3
    dyn_limit: float = 16.0
    ttl_tot: dt.datetime | None = None
    gestart: bool = False
    kabel: bool = False
    # De groep waar de paal op zit (bij Easee de dynamische circuitlimiet), en
    # of de coach die sensor heeft. Trekt de auto er langer dan een minuut
    # overheen, dan pauzeert de paal en start hij de sessie opnieuw, zoals de
    # Easee in de klantwoning op 06-09-2026 om 04:25:57 deed.
    circuit_amps: float | None = None
    circuit_zichtbaar: bool = True
    # Een Easee in automatische fasemodus kiest bij het starten zelf. Met dit
    # aan kiest hij bij de eerstvolgende start één fase, zoals om 04:17.
    kiest_een_fase: bool = False
    # En zo kiest hij als er niets aan de hand is: onder deze stroom wordt het
    # één fase, erboven drie, en dat opnieuw bij elke start. Thuis op
    # 17-09-2026 stopte de coach om 14:10 om op de zon van 15:00 te wachten,
    # wekte om 14:14 met tien ampère, en de paal begon op één fase: 5,875 A bij
    # 1323 W is 225 V per ampère, waar het om 14:05 nog 690 was. Zie
    # `WAKE_AMPS` in planner.py.
    fase_drempel: float | None = None
    fasen_nu: int = 3
    boven_groep_sinds: dt.datetime | None = None
    herstarts: int = 0
    terugvallen: int = 0
    teller_kwh: float = 100.0
    # De echte Easee werkt zijn levensduurteller maar af en toe bij, in
    # sprongen. Zie `_geladen` in coach.py voor wat dat kostte.
    teller_interval_min: int = 60
    teller_zichtbaar: float = 100.0
    teller_bij: dt.datetime | None = None
    ontvangen: list = field(default_factory=list)

    def opdracht(self, dienst: str, data: dict, nu: dt.datetime) -> None:
        self.ontvangen.append((nu, dienst, dict(data)))
        if dienst == "set_charger_dynamic_limit":
            self.dyn_limit = float(data.get("current") or 0)
            ttl = int(data.get("time_to_live") or 0)
            self.ttl_tot = nu + dt.timedelta(minutes=ttl) if ttl else None
        elif dienst == "action_command":
            woord = data.get("action_command")
            if woord in ("start", "resume"):
                self.gestart = True
            elif woord in ("stop", "pause"):
                self.gestart = False
        elif dienst == "set_value":
            # Alfen: het getal is alles. Boven de ondergrens laadt de auto,
            # op nul staat hij stil.
            self.dyn_limit = float(data.get("value") or 0)
            self.geschreven_op = nu
            self.gestart = self.dyn_limit >= MIN_AMPS

    def stap(self, nu: dt.datetime) -> None:
        # Een limiet met houdbaarheid vervalt: dan staat er weer het maximum.
        if self.ttl_tot is not None and nu >= self.ttl_tot:
            self.dyn_limit = self.max_amps
            self.ttl_tot = None
        # Een Alfen die niets meer hoort valt terug op zijn veilige stroom.
        if (
            self.merk == "alfen"
            and self.geschreven_op is not None
            and nu - self.geschreven_op >= dt.timedelta(seconds=self.geldig_s)
        ):
            self.dyn_limit = self.veilig_amps
            self.gestart = True
            self.geschreven_op = None
            self.terugvallen += 1

    def aanbod(self) -> float:
        return min(self.dyn_limit, self.max_amps) if self.kabel else 0.0

    def status(self, auto: Auto) -> str:
        if not self.kabel:
            return "disconnected"
        if auto.klaar or auto.storing:
            return "completed"
        if auto.trekt_amps > 0:
            return "charging"
        return "awaiting_start"

    def teller(self, nu: dt.datetime) -> float:
        if self.teller_bij is None or (nu - self.teller_bij) >= dt.timedelta(
            minutes=self.teller_interval_min
        ):
            self.teller_bij = nu
            self.teller_zichtbaar = self.teller_kwh
        return self.teller_zichtbaar


# --- de vaatwasser -------------------------------------------------------------


@dataclass
class Vaatwasser:
    """Een Home Connect-vaatwasser: een programma dat je start en dat afdraait.

    Het verbruik loopt in twee bulten, verwarmen aan het begin en drogen aan
    het eind, met daartussen een pomp. De opgaven van de fabrikant zijn de
    tabel in planner.py; hier is het een profiel dat op dezelfde kWh uitkomt.
    """

    programma: str = "dishcare_dishwasher_program_eco_50"
    minuten: int = 225
    kwh: float = 0.8
    piek_w: float = 1200.0
    piek_minuten: int = 40
    pomp_w: float = 60.0
    # Of "starten op afstand" op het apparaat aan staat. Staat het uit, dan
    # doet een druk op de knop niets, zoals bij een echte Home Connect.
    afstand_aan: bool = True
    deur_open: bool = False
    # Hoe lang Home Connect erover doet om na de knop "run" te melden.
    aanloop_min: int = 1
    # Home Connect geeft de eindtijd als tijdstip, en die staat er al voor de
    # start: het moment waarop het programma gekozen werd plus de duur. Pas
    # `eindtijd_na_min` na de start rekent hij hem opnieuw uit. In die woning op
    # 11-09-2026: om 09:01 gekozen (eindtijd 10:56), om 09:36 gestart, om
    # 09:37:05 de echte eindtijd 11:31. False: de minuten die nog resten, en
    # alleen zolang hij draait.
    eindtijd_tijdstip: bool = False
    gekozen: str | None = None      # "HH:MM" op de eerste dag; None is het begin van de proef
    eindtijd_na_min: int = 1
    # De eindtijd die hij meteen bij de start neerzet, als duur in minuten:
    # wel van na de start, maar nog niet de goede. In die woning op 15-09-2026 gaf
    # Home Connect bij Run 11:33 en een minuut later 11:41; klaar was hij om
    # 11:45. None: bij de start blijft de eindtijd van het kiezen staan.
    eindtijd_eerst_min: int | None = None
    # Een domme vaatwasser op een meetstekker (merk "overig"): geen status,
    # geen programma, geen knop; alleen het vermogen. De coach zegt wanneer
    # en de bewoner drukt zelf, zoveel minuten later. None: hij doet het niet.
    # De eigenaar op 06-09-2026: "wel adviseren en meten, met zet hem aan."
    slim: bool = True
    bewoner_reageert_min: int | None = 5

    # toestand
    status: str = "ready"
    gestart_op: dt.datetime | None = None
    gedrukt_op: dt.datetime | None = None
    kwh_geleverd: float = 0.0

    def druk_start(self, nu: dt.datetime) -> None:
        if self.afstand_aan and not self.deur_open and self.status in ("ready", "inactive"):
            self.gedrukt_op = nu

    def zet_aan(self, nu: dt.datetime) -> bool:
        """De bewoner drukt zelf op de knop van de machine."""
        if self.status in ("ready", "inactive", "finished"):
            self.status = "run"
            self.gestart_op = nu
            self.gedrukt_op = None
            return True
        return False

    def stap(self, nu: dt.datetime) -> float:
        """Eén stap; geeft het vermogen van dit moment in watt."""
        if self.gedrukt_op is not None and self.status != "run":
            if nu - self.gedrukt_op >= dt.timedelta(minutes=self.aanloop_min):
                self.status = "run"
                self.gestart_op = nu
                self.gedrukt_op = None
        if self.status != "run" or self.gestart_op is None:
            return 0.0
        verstreken = (nu - self.gestart_op).total_seconds() / 60
        if verstreken >= self.minuten:
            self.status = "finished"
            return 0.0
        helft = self.piek_minuten / 2
        if verstreken < helft or verstreken >= self.minuten - helft:
            return self.piek_w
        return self.pomp_w

    def resterend(self, nu: dt.datetime) -> int | None:
        if self.status != "run" or self.gestart_op is None:
            return None
        return max(0, int(self.minuten - (nu - self.gestart_op).total_seconds() / 60))

    def eindtijd(self, nu: dt.datetime, gekozen_op: dt.datetime) -> dt.datetime | None:
        """Wat Home Connect als eindtijd laat zien; zie `eindtijd_tijdstip`."""
        if self.status == "finished":
            return None
        if self.status == "run" and self.gestart_op is not None \
                and nu - self.gestart_op >= dt.timedelta(minutes=self.eindtijd_na_min):
            return self.gestart_op + dt.timedelta(minutes=self.minuten)
        if self.status == "run" and self.gestart_op is not None and self.eindtijd_eerst_min is not None:
            return self.gestart_op + dt.timedelta(minutes=self.eindtijd_eerst_min)
        return gekozen_op + dt.timedelta(minutes=self.minuten)


# --- de prijzen --------------------------------------------------------------

# Een gewone dag op de Nederlandse markt, kaal, per uur. Goedkoop in de nacht
# en rond het middaguur, duur bij het koken.
MARKT = [
    0.070, 0.065, 0.060, 0.060, 0.065, 0.080, 0.095, 0.110,
    0.130, 0.100, 0.060, 0.030, 0.010, 0.000, 0.010, 0.040,
    0.080, 0.140, 0.190, 0.210, 0.160, 0.120, 0.100, 0.085,
]


@dataclass
class Boiler:
    """Een elektrische boiler op een smart plug.

    Een vat met een thermostaat ervoor. Staat er stroom op en is het water
    kouder dan de thermostaat wil, dan trekt het element zijn vermogen; is het
    vat op temperatuur, dan trekt hij niets, ook al staat de stekker erin. Dat
    laatste is precies wat de coach meet om te zien dat het vat vol is.

    Wat er uit het vat gaat is afkoeling plus douchen. De thermostaat heeft
    speling: hij vraagt pas warmte als er een stuk uit is, en houdt die vraag
    vast tot het vat weer vol is. Zo gedraagt een echte zich ook, en zo kan de
    coach niet elke minuut een kruimel bijverwarmen.
    """

    element_w: float = 2000.0
    vat_kwh: float = 6.0
    verlies_kwh_h: float = 0.08
    # Wanneer er warm water getapt wordt en hoeveel: {"07:15": 2.0}.
    tappen: dict = field(default_factory=lambda: {"07:20": 2.2, "21:30": 1.4})
    # Hoeveel er uit moet zijn voor de thermostaat warmte vraagt.
    speling_kwh: float = 0.5
    # Of de stekker het doet. Uit: er komt nooit stroom, wat de coach ook zegt.
    stekker_werkt: bool = True

    # toestand
    aan: bool = False
    inhoud_kwh: float | None = None
    vraagt: bool = False
    getapt: set = field(default_factory=set)
    laagste_kwh: float | None = None
    begonnen: dt.datetime | None = None

    def stap(self, nu: dt.datetime, seconden: float) -> float:
        """Eén stap; geeft het vermogen van dit moment in watt."""
        if self.inhoud_kwh is None:
            self.inhoud_kwh = self.vat_kwh
        if self.begonnen is None:
            self.begonnen = nu
        uren = seconden / 3600.0
        self.inhoud_kwh = max(0.0, self.inhoud_kwh - self.verlies_kwh_h * uren)
        for tijd, kwh in self.tappen.items():
            moment = nu.replace(hour=int(tijd[:2]), minute=int(tijd[3:5]), second=0, microsecond=0)
            sleutel = (nu.date(), tijd)
            # Een douche van vóór het begin van de proef is al geweest; die
            # hoort niet in de eerste minuut alsnog het vat leeg te trekken.
            if moment < self.begonnen:
                self.getapt.add(sleutel)
            if sleutel not in self.getapt and nu >= moment:
                self.getapt.add(sleutel)
                self.inhoud_kwh = max(0.0, self.inhoud_kwh - kwh)

        watt = 0.0
        if self.aan and self.stekker_werkt and self.vraagt:
            watt = self.element_w
            self.inhoud_kwh = min(self.vat_kwh, self.inhoud_kwh + watt / 1000.0 * uren)

        # De thermostaat: vol is vol, en daarna vraagt hij pas weer warmte als
        # er een stuk uit is. De marge is er omdat het vat elke stap ook een
        # beetje afkoelt; zonder die marge stond hij een haar onder vol en
        # bleef hij eeuwig bijverwarmen.
        if self.inhoud_kwh >= self.vat_kwh - 0.005:
            self.vraagt = False
        elif self.inhoud_kwh <= self.vat_kwh - self.speling_kwh:
            self.vraagt = True
        self.laagste_kwh = (
            self.inhoud_kwh if self.laagste_kwh is None else min(self.laagste_kwh, self.inhoud_kwh)
        )
        return watt


@dataclass
class Batterij:
    """Een thuisbatterij die precies doet wat hem gezegd wordt, een paar tellen later.

    Gebouwd naar wat er op 21-09-2026 in de eerste woning gemeten is: 14,6 kWh,
    3,5 kW erin en 2,5 kW eruit, grenzen op 5 en 95 procent, 73,6% rendement
    heen en terug, en een opdracht die na ongeveer vijf seconden in het
    vermogen te zien is. In de stand voor externe sturing regelt hij zelf niets:
    hij houdt zijn laatste opdracht vast tot er een nieuwe komt. Dat is precies
    wat de coach gevaarlijk zou maken als zijn lus stilvalt, en dus wat hier
    nagemeten wordt.
    """

    capaciteit_kwh: float = 14.6
    soc: float = 50.0
    max_laden_w: float = 3500.0
    max_ontladen_w: float = 2500.0
    soc_min: float = 5.0
    soc_max: float = 95.0
    rte: float = 0.736
    volgt_na_s: float = 5.0
    # Op welke fase hij hangt (0 is L1).
    fase: int = 2
    # Een kWh-meter op de batterij, met standen die samen 73,6% geven: daar
    # leest de coach het rendement uit. Zonder meter moet de bewoner het
    # opgeven (`rte_opgegeven`), en anders weet de coach het niet.
    meter: bool = True
    rte_opgegeven: float | None = None
    # Wat de bewoner instelt.
    reserve: float | None = None
    handelen: bool = False
    wekelijks_vol_dag: int | None = None
    aankoop: float | None = None
    # --- de sensor ---
    # Gemeten aan de Anker van de eerste woning op 22-09-2026, naast een
    # kWh-meter op dezelfde batterij: het vermogen dat de integratie meldt loopt
    # vijf tot tien seconden achter, toont onderweg een aanloop die er niet is
    # (1040, 1020, 1010, 1000, 940 en dan pas 2500, terwijl de meter meteen
    # 2580 zag), en vlak na een opdracht soms de opdracht zelf in plaats van de
    # meting (0 W terwijl er 2215 liep). Standaard staat dit uit, zodat de
    # oudere scenario's blijven wat ze waren; `ANKER_SENSOR` in scenarios.py
    # zet het aan.
    sensor_na_s: float = 0.0
    sensor_aanloop: bool = False
    sensor_echo_s: float = 0.0
    # --- de meter ---
    # De P1 meldt eens per zoveel seconden en houdt daartussen zijn waarde vast,
    # met de tijd van die melding als stempel; `meter_fase_s` zegt op welke
    # seconde van die vijf hij meldt. In de eerste woning op 22-09-2026 's
    # nachts: de P1 om :08 nog de oude stand, de sensor van de batterij om :09
    # al de nieuwe, en de regelaar die om :09 met die twee rekende. Alleen met
    # stappen van een seconde te zien; standaard uit.
    meter_tik_s: float = 0.0
    meter_fase_s: float = 0.0
    # --- toestand ---
    modus: str = "self_consumption"
    richting: str = "charge"
    vermogen_w: float = 0.0
    wachtrij: list = field(default_factory=list)
    teller_in: float = 250.0
    teller_uit: float = 184.0
    # Wat hij werkelijk deed, per stap: (tijd, watt). Voor de sensor.
    sensor_verloop: list = field(default_factory=list)
    opdracht_op: dt.datetime | None = None
    opdracht_w: float = 0.0

    def opdracht(self, watt: float, nu: dt.datetime) -> None:
        self.wachtrij.append((nu + dt.timedelta(seconds=self.volgt_na_s), watt))
        self.opdracht_op, self.opdracht_w = nu, watt

    def sensor_w(self, nu: dt.datetime) -> float:
        """Wat de vermogenssensor van de batterij nu meldt."""
        echt = self.sensor_verloop[-1][1] if self.sensor_verloop else 0.0
        if self.sensor_na_s <= 0 and self.sensor_echo_s <= 0:
            return echt
        if (self.opdracht_op is not None
                and 0 <= (nu - self.opdracht_op).total_seconds() < self.sensor_echo_s):
            return self.opdracht_w
        toen = nu - dt.timedelta(seconds=self.sensor_na_s)
        oud = echt
        for t, w in reversed(self.sensor_verloop):
            oud = w
            if t <= toen:
                break
        if self.sensor_aanloop and abs(echt - oud) > 1.0:
            return oud + 0.4 * (echt - oud)
        return oud

    def stap(self, nu: dt.datetime, seconden: float) -> float:
        """Wat hij deze stap doet, in watt aan de wisselstroomkant, laden positief."""
        klaar = [w for t, w in self.wachtrij if t <= nu]
        if klaar:
            self.vermogen_w = klaar[-1]
            self.wachtrij = [(t, w) for t, w in self.wachtrij if t > nu]
        w = max(-self.max_ontladen_w, min(self.max_laden_w, self.vermogen_w))
        if (w > 0 and self.soc >= self.soc_max) or (w < 0 and self.soc <= self.soc_min):
            w = 0.0
        self.sensor_verloop.append((nu, w))
        grens = nu - dt.timedelta(seconds=self.sensor_na_s + 60)
        while len(self.sensor_verloop) > 2 and self.sensor_verloop[0][0] < grens:
            self.sensor_verloop.pop(0)
        eta = math.sqrt(self.rte)
        kwh = w / 1000 * seconden / 3600
        if kwh >= 0:
            self.soc += kwh * eta / self.capaciteit_kwh * 100
            self.teller_in += kwh
        else:
            self.soc += kwh / eta / self.capaciteit_kwh * 100
            self.teller_uit += -kwh
        self.soc = max(0.0, min(100.0, self.soc))
        return w


@dataclass
class Prijzen:
    markt: list[float] = field(default_factory=lambda: list(MARKT))
    bekend_om: str = "13:00"     # vanaf dan is de dag van morgen bekend
    energiebelasting: float = 0.1088
    opslag: float = 0.02
    btw: float = 21.0
    terugleverkosten: float = 0.0
    # Echte all-in prijzen per dag, "2026-09-05": [24 prijzen]. Een dag die
    # hier niet in staat valt terug op `markt`. Zo draait een scenario op
    # precies de prijzen die een klant op dat moment zag.
    per_dag: dict[str, list[float]] | None = None

    def kaal(self, moment: dt.datetime) -> float:
        dag = (self.per_dag or {}).get(moment.date().isoformat())
        if dag is not None:
            return dag[moment.hour] / (1 + self.btw / 100) - self.energiebelasting - self.opslag
        return self.markt[moment.hour]

    def all_in(self, moment: dt.datetime) -> float:
        dag = (self.per_dag or {}).get(moment.date().isoformat())
        if dag is not None:
            return dag[moment.hour]
        return (self.kaal(moment) + self.energiebelasting + self.opslag) * (1 + self.btw / 100)

    def lijst(self, nu: dt.datetime, all_in: bool, tot_dag: dt.date | None = None) -> list[dict]:
        dagen = [nu.date()]
        if nu.hour + nu.minute / 60 >= _uur(self.bekend_om):
            dagen.append(nu.date() + dt.timedelta(days=1))
        # Voor het optimum: alles tot en met een dag, alsof alles al bekend was.
        while tot_dag is not None and dagen[-1] < tot_dag:
            dagen.append(dagen[-1] + dt.timedelta(days=1))
        uit = []
        for dag in dagen:
            for uur in range(24):
                van = dt.datetime.combine(dag, dt.time(uur))
                prijs = self.all_in(van) if all_in else self.kaal(van)
                uit.append({
                    "from": van.isoformat(),
                    "till": (van + dt.timedelta(hours=1)).isoformat(),
                    "price": round(prijs, 5),
                })
        return uit


# --- het scenario ------------------------------------------------------------


@dataclass
class Scenario:
    naam: str
    uitleg: str = ""
    contract: str = "vast"   # vast | vast-salderen | dynamisch | dynamisch-markt | dynamisch-salderen
    zon: Zon = field(default_factory=Zon)
    huis: Huis = field(default_factory=Huis)
    auto: Auto = field(default_factory=Auto)
    paal: Paal = field(default_factory=Paal)
    prijzen: Prijzen = field(default_factory=Prijzen)
    begin: str = "2026-09-07 06:55"     # een maandag
    duur_uren: float = 24.0
    # Hoe fijn de wereld tikt. De coach draait hoe dan ook elke minuut een
    # ronde; met een fijnere stap ziet hij ook wat er tússen twee ronden
    # gebeurt, zoals een oven die aangaat, en luistert hij mee op de fasen.
    stap_seconden: int = 60
    kabel_erin: str | None = "07:00"    # op de eerste dag; None: hangt er al
    klaar_om: str | None = "06:00"
    # Weekdagen (0 is maandag) die in het schema uitgevinkt zijn. Dan schuift de
    # klaar-tijd naar de eerstvolgende dag die wel aan staat.
    dagen_uit: tuple = ()
    niet_voor: str | None = None
    uiterlijk_starten: str | None = None
    schema_aan: bool = True
    net: str = "split"                  # split | signed | signed-omgekeerd
    aansluiting_fasen: int = 3
    zekering: float = 25.0
    lastbewaker: bool = False
    # Een Easee Equalizer: houdt de som van huis en paal zelf onder de zekering,
    # meldt hoeveel hij vrijgeeft, en de paal zegt waarom hij geknepen wordt.
    equalizer: bool = False
    voorspeller: str = "dashboard"      # dashboard | sensoren | geen
    # Wat de coach bij een eerdere beurt over deze auto leerde: kW per band van
    # tien procent, zoals `car_pace` in de instellingen. Zie `_tempo_leren`.
    geleerd_tempo: dict = field(default_factory=dict)
    # Een vaatwasser in huis, met haar eigen schema ("klaar om"); None is geen.
    vaatwasser: Vaatwasser | None = None
    vaatwasser_klaar_om: str | None = "07:00"
    vaatwasser_uiterlijk: str | None = None
    vaatwasser_niet_eerder: str | None = None
    # De eigen programmatabel van de klant (rijen zoals `programs` in de
    # instellingen); None is de opgave van de fabrikant.
    vaatwasser_tabel: list | None = None
    # Welk programma erop staat bij een domme vaatwasser (de sleutel).
    vaatwasser_programma: str = "eco_50"
    # Wat de coach bij een eerdere beurt al mat (rijen zoals `program_measured`).
    vaatwasser_gemeten: list = field(default_factory=list)
    # Een boiler op een smart plug, met zijn eigen "klaar om"; None is geen.
    boiler: Boiler | None = None
    boiler_klaar_om: str | None = "07:00"
    # Wat de coach van deze boiler al geleerd had (een rij zoals
    # `boiler_learned` in de instellingen); leeg is: hij begint met meten.
    boiler_geleerd: dict = field(default_factory=dict)
    # Een thuisbatterij; None is geen. En of de coach de paal stuurt: in de
    # eerste woning deed iets anders dat, en dan ziet de coach alleen zijn
    # vermogen.
    batterij: Batterij | None = None
    paal_stuurbaar: bool = True
    # Wat de coach van de batterij al bijhield (een rij zoals `battery_state`).
    batterij_stand: dict = field(default_factory=dict)
    vast_prijs: float = 0.28
    vast_teruglevering: float = 0.07
    vast_terugleverkosten: float = 0.0
    # (tijd, actie, argument): ("13:10", "kabel_uit", None), ("18:00", "pauze", True),
    # ("12:00", "snelladen", True), ("09:30", "soc_opgeven", 40), ("11:00", "p1_weg", 3),
    # ("20:00", "oven", 30)
    gebeurtenissen: list[tuple] = field(default_factory=list)
    # Wat "oven" aanzet, in watt; valt over de fasen zoals `Huis.verdeling`.
    # 5,5 kW met 80% op één fase is een warmtepomp zoals in de klantwoning.
    oven_w: float = 3000.0

    def kopie(self, **wijzigingen) -> "Scenario":
        return dataclasses.replace(self, **wijzigingen)


# --- wat er gebeurde ---------------------------------------------------------


@dataclass
class Regel:
    tijd: dt.datetime
    regel: str
    amps: int
    reden: str
    plan: str
    paal_w: float
    paal_amps: float
    soc: float
    zon_w: float
    huis_w: float
    over_w: float
    inkoop_w: float
    terug_w: float
    prijs: float | None
    fase_amps: list[float]
    status: str
    # Wat de coach zelf zegt nog te moeten laden, uit `plan_ahead`. Dat is het
    # getal dat de bewoner op de kaart leest, en het hangt aan de accustand
    # zoals de coach die kent; zie `_soc_bijgeteld` in coach.py.
    nodig_kwh: float | None = None


@dataclass
class Verloop:
    scenario: Scenario
    regels: list[Regel] = field(default_factory=list)
    meldingen: list[tuple[dt.datetime, str]] = field(default_factory=list)
    opdrachten: list = field(default_factory=list)
    geladen_kwh: float = 0.0
    uit_zon_kwh: float = 0.0
    uit_net_kwh: float = 0.0
    betaald: float = 0.0          # aan het net, tegen de inkoopprijs
    misgelopen: float = 0.0       # zon die anders teruggeleverd was
    optimum: float | None = None  # met de hele dag vooraf bekend
    klaar_op: dt.datetime | None = None
    soc_bij_klaar_tijd: float | None = None
    klaar_tijd: dt.datetime | None = None
    hoogste_fase: float = 0.0
    # Hoe lang één regel duurt, in uren. Energie is vermogen maal dit getal.
    stap_uur: float = 1 / 60
    fouten: list[str] = field(default_factory=list)
    # De laadbeurten zoals de coach ze in de opslag zette: kWh, betaald, bespaard.
    beurten: list = field(default_factory=list)
    # Hoe vaak de paal zelf de sessie herstartte omdat de auto over de groep ging.
    paal_herstarts: int = 0
    # Hoe vaak een Alfen op zijn veilige stroom terugviel omdat de coach
    # zijn limiet niet op tijd opnieuw schreef. Hoort nul te zijn.
    paal_terugvallen: int = 0
    # Wat de coach aan het eind over de auto geleerd had: kW per band.
    geleerd: dict = field(default_factory=dict)
    # De vaatwasser: wanneer de coach op start drukte, wanneer hij draaide,
    # wanneer hij klaar was, en wat hij aan energie en geld kostte.
    vw_gedrukt: list = field(default_factory=list)
    vw_gestart: dt.datetime | None = None
    vw_klaar: dt.datetime | None = None
    vw_kwh: float = 0.0
    vw_betaald: float = 0.0
    # Elke beurt apart: (gestart, klaar, met een gemeten programma gepland).
    vw_beurten: list = field(default_factory=list)
    # Wat de coach aan het eind over de programma's gemeten had.
    vw_gemeten: list = field(default_factory=list)
    # Wanneer de coach de bewoner vroeg om hem aan te zetten (domme machine).
    vw_gevraagd: list = field(default_factory=list)
    # De boiler: wanneer de stroom erop en eraf ging, wat erin ging en wat dat
    # kostte, hoe leeg het vat onderweg werd en hoe vol het was op de
    # klaar-tijd. Dat laatste is waar het om gaat: er hoort warm water te zijn
    # als de bewoner onder de douche stapt.
    boiler_schakels: list = field(default_factory=list)
    boiler_kwh: float = 0.0
    boiler_betaald: float = 0.0
    boiler_zon_kwh: float = 0.0
    boiler_bij_klaar: float | None = None
    boiler_laagste: float | None = None
    # Wat de coach aan het eind van deze boiler geleerd had.
    boiler_geleerd: dict = field(default_factory=dict)
    # De thuisbatterij: elke opdracht die de coach gaf, het verloop per stap
    # (tijd, meter, batterij, accustand, stand), wat het huis van het net nam en
    # eraan gaf, en wat de dag kostte met en zonder batterij.
    bat_opdrachten: list = field(default_factory=list)
    bat_modi: list = field(default_factory=list)
    # De laadgrens die de coach schreef, voor de wekelijkse volle beurt.
    bat_grenzen: list = field(default_factory=list)
    bat_verloop: list = field(default_factory=list)
    bat_afname_kwh: float = 0.0
    bat_levering_kwh: float = 0.0
    bat_kosten_met: float = 0.0
    bat_kosten_zonder: float = 0.0
    bat_stand: dict = field(default_factory=dict)

    def bat_wissels(self) -> int:
        """Hoe vaak de batterij van richting wisselde of aan- en uitging."""
        tekens = [0 if abs(w) < 1 else (1 if w > 0 else -1) for _, w in self.bat_opdrachten]
        return sum(1 for a, b in zip(tekens, tekens[1:]) if a != b)

    def bat_minuten(self, stand: str) -> float:
        return sum(1 for r in self.bat_verloop if r[4] == stand) * self.stap_uur * 60

    def bat_soc_op(self, tijd: str, dag: int = 0) -> float | None:
        doel = _moment_op(self.regels[0].tijd, tijd) + dt.timedelta(days=dag)
        for r in self.bat_verloop:
            if r[0] >= doel:
                return r[3]
        return None

    @property
    def kosten(self) -> float:
        return self.betaald + self.misgelopen

    def wissels(self) -> int:
        """Hoe vaak de paal aan of uit ging."""
        n = 0
        vorige = None
        for r in self.regels:
            laadt = r.paal_amps > 0
            if vorige is not None and laadt != vorige:
                n += 1
            vorige = laadt
        return n

    def net_kwh_tussen(self, van: str, tot: str) -> float:
        """Uit het net geladen tussen twee kloktijden, elke dag van de proef."""
        som = 0.0
        for r in self.regels:
            u = r.tijd.hour + r.tijd.minute / 60
            if _uur(van) <= u < _uur(tot):
                som += max(0.0, r.paal_w - max(0.0, r.zon_w - r.huis_w)) / 1000 * self.stap_uur
        return som

    def zon_kwh_tussen(self, van: str, tot: str) -> float:
        som = 0.0
        for r in self.regels:
            u = r.tijd.hour + r.tijd.minute / 60
            if _uur(van) <= u < _uur(tot):
                som += min(r.paal_w, max(0.0, r.zon_w - r.huis_w)) / 1000 * self.stap_uur
        return som

    def regels_met(self, naam: str) -> list[Regel]:
        return [r for r in self.regels if naam in r.regel]


# --- de instellingen van de coach --------------------------------------------

E = {
    "status": "sensor.v_paal_status",
    "stroom": "sensor.v_paal_stroom",
    "vermogen": "sensor.v_paal_vermogen",
    "max": "sensor.v_paal_max",
    "dyn": "sensor.v_paal_dyn",
    "circuit": "sensor.v_paal_circuit",
    "teller": "sensor.v_paal_teller",
    "zon": "sensor.v_zon",
    "afname": "sensor.v_afname",
    "teruglevering": "sensor.v_teruglevering",
    "net": "sensor.v_net",
    "l1": "sensor.v_l1", "l2": "sensor.v_l2", "l3": "sensor.v_l3",
    "soc": "sensor.v_auto_soc",
    "equalizer": "sensor.v_equalizer",
    "reden": "sensor.v_paal_reden",
    "prijs": "sensor.v_prijs",
    "markt": "sensor.v_markt",
    "zon_rest": "sensor.v_zon_rest",
    "zon_dit_uur": "sensor.v_zon_dit_uur",
    "zon_volgend_uur": "sensor.v_zon_volgend_uur",
    "zon_piek": "sensor.v_zon_piek",
    "vw_status": "sensor.v_vaatwasser_status",
    "vw_programma": "select.v_vaatwasser_programma",
    "vw_rest": "sensor.v_vaatwasser_rest",
    "vw_deur": "binary_sensor.v_vaatwasser_deur",
    "vw_start": "button.v_vaatwasser_start",
    "vw_stop": "button.v_vaatwasser_stop",
    "vw_vermogen": "sensor.v_vaatwasser_vermogen",
    "boiler_vermogen": "sensor.v_boiler_vermogen",
    "boiler_switch": "switch.v_boiler",
    "bat_soc": "sensor.v_batterij_soc",
    "bat_vermogen": "sensor.v_batterij_vermogen",
    "bat_stuur": "number.v_batterij_vermogen",
    "bat_richting": "select.v_batterij_richting",
    "bat_modus": "select.v_batterij_modus",
    "bat_cap": "sensor.v_batterij_capaciteit",
    "bat_hoog": "number.v_batterij_laadgrens",
    "bat_laag": "number.v_batterij_ontlaadgrens",
    "bat_in": "sensor.v_batterij_meter_in",
    "bat_uit": "sensor.v_batterij_meter_uit",
    "alfen_limit": "number.v_paal_limiet",
    "alfen_connected": "sensor.v_paal_auto_aangesloten",
    "alfen_charging": "sensor.v_paal_auto_laadt",
    "alfen_mode3": "sensor.v_paal_modus3",
}


def instellingen(s: Scenario) -> dict:
    auto = s.auto
    fasen = {"l1": {"current": E["l1"]}, "l2": {"current": E["l2"]}, "l3": {"current": E["l3"]}}
    if s.aansluiting_fasen == 1:
        fasen = {"l1": {"current": E["l1"]}, "l2": {}, "l3": {}}
    bronnen = {
        "solar": E["zon"],
        "grid_mode": "signed" if s.net.startswith("signed") else "split",
        "grid_import": E["afname"],
        "grid_export": E["teruglevering"],
        "grid_signed": E["net"],
        "grid_signed_invert": s.net == "signed-omgekeerd",
        "phases_enabled": True,
        "phases": fasen,
        "solar_forecast": {
            "remaining_today": E["zon_rest"],
            "this_hour": E["zon_dit_uur"],
            "next_hour": E["zon_volgend_uur"],
            "peak_today": E["zon_piek"],
        } if s.voorspeller != "geen" else {},
    }
    salderen = s.contract.endswith("salderen")
    if s.contract.startswith("vast"):
        contract = {
            "type": "fixed",
            "netting": salderen,
            "fixed": {
                "all_in_price": s.vast_prijs,
                "feed_in_tariff": s.vast_teruglevering,
                "feed_in_costs": s.vast_terugleverkosten,
            },
        }
    else:
        markt = s.contract == "dynamisch-markt"
        contract = {
            "type": "dynamic",
            "netting": salderen,
            "dynamic": {
                "source": "market" if markt else "all_in",
                "interval": "hour",
                "all_in_entity": "" if markt else E["prijs"],
                "market_entity": E["markt"],
                "energy_tax": s.prijzen.energiebelasting,
                "supplier_markup": s.prijzen.opslag,
                "vat_percent": s.prijzen.btw,
                "feed_in_costs": s.prijzen.terugleverkosten,
            },
        }
    apparaten = []
    schemas = []
    if s.vaatwasser is not None:
        if s.vaatwasser.slim:
            apparaten.append({
                "id": "vaatwasser",
                "type": "vaatwasser",
                "name": "Vaatwasser",
                "brand": "home_connect",
                "controllable": True,
                "entity": E["vw_vermogen"],
                "entities": {
                    "status": E["vw_status"],
                    "program": E["vw_programma"],
                    "remaining": E["vw_rest"],
                    "door": E["vw_deur"],
                    "start": E["vw_start"],
                    "stop": E["vw_stop"],
                },
                "programs": list(s.vaatwasser_tabel or []),
            })
        else:
            # Een domme vaatwasser: alleen een meetstekker, en het programma
            # zoals de bewoner het op de kaart koos.
            apparaten.append({
                "id": "vaatwasser",
                "type": "vaatwasser",
                "name": "Vaatwasser",
                "brand": "overig",
                "controllable": True,
                "entity": E["vw_vermogen"],
                "entities": {},
                "programs": list(s.vaatwasser_tabel or []),
                "program": s.vaatwasser_programma,
            })
        schemas.append({
            "device": "vaatwasser",
            "enabled": bool(s.vaatwasser_klaar_om or s.vaatwasser_uiterlijk or s.vaatwasser_niet_eerder),
            "priority": "mid",
            "per_day": False,
            "window": {"not_before": s.vaatwasser_niet_eerder or "", "start_by": s.vaatwasser_uiterlijk or "",
                       "done_by": s.vaatwasser_klaar_om or ""},
            "days": [],
        })
    if s.boiler is not None:
        apparaten.append({
            "id": "boiler",
            "type": "boiler",
            "name": "Boiler",
            "controllable": True,
            "entity": E["boiler_vermogen"],
            "entities": {"switch": E["boiler_switch"]},
        })
        schemas.append({
            "device": "boiler",
            "enabled": bool(s.boiler_klaar_om),
            "priority": "mid",
            "per_day": False,
            "window": {"not_before": "", "start_by": "", "done_by": s.boiler_klaar_om or ""},
            "days": [],
        })
    if s.batterij is not None:
        bat = s.batterij
        apparaten.append({
            "id": "batterij",
            "type": "thuisbatterij",
            "name": "Thuisbatterij",
            "brand": "anker",
            "controllable": True,
            "entity": E["bat_vermogen"],
            "entities": {
                "soc": E["bat_soc"],
                "setpoint": E["bat_stuur"],
                "direction": E["bat_richting"],
                "mode": E["bat_modus"],
                "capacity": E["bat_cap"],
                "charge_limit": E["bat_hoog"],
                "discharge_limit": E["bat_laag"],
                **({"energy_in": E["bat_in"], "energy_out": E["bat_uit"]} if bat.meter else {}),
            },
            "battery": {
                "max_charge_w": bat.max_laden_w,
                "max_discharge_w": bat.max_ontladen_w,
                "rte_percent": None if bat.rte_opgegeven is None else bat.rte_opgegeven * 100,
                "phase": ("l1", "l2", "l3")[bat.fase],
                "reserve_enabled": bat.reserve is not None,
                "reserve_percent": bat.reserve or 0,
                "trade": bat.handelen,
                "weekly_full": bat.wekelijks_vol_dag is not None,
                "weekly_full_day": bat.wekelijks_vol_dag or 0,
                "purchase_price": bat.aankoop,
                "control_mode": "third_party_control",
                "idle_mode": "self_consumption",
            },
        })
    return {
        "battery_state": [{"device": "batterij", **s.batterij_stand}] if s.batterij_stand else [],
        "devices": [*apparaten, {
            "id": "paal",
            "type": "laadpaal",
            "name": "Laadpaal",
            "brand": s.paal.merk,
            "controllable": s.paal_stuurbaar,
            "device_id": "" if s.paal.merk == "alfen" else "virtueel",
            "entity": E["vermogen"],
            "entities": {
                **(
                    {"status": E["status"]}
                    if s.paal.merk != "alfen"
                    else {
                        "limit": E["alfen_limit"],
                        "connected": E["alfen_connected"],
                        "charging": E["alfen_charging"],
                        "mode3": E["alfen_mode3"],
                    }
                ),
                "current": E["stroom"],
                "max_limit": E["max"],
                "dynamic_limit": E["dyn"],
                "lifetime_energy": E["teller"],
                "no_current_reason": E["reden"] if s.equalizer else "",
                "circuit_limit": E["circuit"]
                if s.paal.circuit_amps is not None and s.paal.circuit_zichtbaar else "",
            },
            "cars": [{
                "id": "auto",
                "name": auto.naam,
                "capacity_kwh": auto.capaciteit_kwh,
                "phases": "one" if auto.fasen == 1 else "three",
                "max_amps": auto.max_amps,
                "target_percent": auto.doel,
                "soc_entity": E["soc"] if auto.meldt_soc else "",
            }],
        }],
        "installation": {
            "phases": s.aansluiting_fasen,
            "fuse_amps": s.zekering,
            "load_balancer": s.lastbewaker or s.equalizer,
            "balancer_entity": E["equalizer"] if s.equalizer else "",
        },
        "sources": bronnen,
        "contract": contract,
        "strategy": {
            "level": "steer",
            "schedules": [*schemas, {
                "device": "paal",
                "enabled": s.schema_aan,
                "priority": "high",
                "per_day": bool(s.dagen_uit),
                "window": {
                    "not_before": s.niet_voor or "",
                    "start_by": s.uiterlijk_starten or "",
                    "done_by": s.klaar_om or "",
                },
                "days": [
                    {"day": dag, "enabled": dag not in s.dagen_uit,
                     "not_before": "", "start_by": "", "done_by": s.klaar_om or ""}
                    for dag in range(7)
                ] if s.dagen_uit else [],
            }],
        },
        "active_cars": [{"device": "paal", "car": "auto"}],
        # Eén bewoner die alles wil horen behalve de besluiten, net als in het echt.
        "notifications": {
            "people": [{"id": "p-1", "name": "Bewoner", "target": "virtueel", "user_id": "",
                        "kinds": {"kritiek": True, "melding": True, "besluit": False, "belasting": True}}],
            "load_alert": {"enabled": False, "threshold_percent": 80,
                           "min_interval_minutes": 30, "min_duration_seconds": 60},
        },
        "car_soc": [],
        # Wat een eerdere beurt over deze auto leerde, per band van tien procent.
        "car_pace": [{"device": "paal", "car": "auto", "band": band, "kw": kw, "at": ""}
                     for band, kw in sorted(s.geleerd_tempo.items())],
        "ready_devices": [],
        "sessions": [],
        # Wat een eerdere beurt over de programma's van de vaatwasser mat.
        "program_measured": [dict(r) for r in s.vaatwasser_gemeten],
        # En wat de coach van de boiler geleerd had.
        "boiler_learned": [{"device": "boiler", **s.boiler_geleerd}] if s.boiler_geleerd else [],
    }


# --- de wereld zelf ----------------------------------------------------------


class Wereld:
    """Alles buiten de coach, en de klok."""

    def __init__(self, s: Scenario):
        self.s = s
        self.zon = dataclasses.replace(s.zon)
        self.huis = dataclasses.replace(s.huis)
        self.vaatwasser = dataclasses.replace(s.vaatwasser) if s.vaatwasser is not None else None
        self.boiler = dataclasses.replace(s.boiler, getapt=set()) if s.boiler is not None else None
        self.boiler_w = 0.0
        self.batterij = (dataclasses.replace(s.batterij, wachtrij=[], sensor_verloop=[])
                         if s.batterij is not None else None)
        self.bat_w = 0.0
        self.vw_w = 0.0
        self.vw_gevraagd: dt.datetime | None = None
        self.auto = dataclasses.replace(s.auto, soc_gemeld=[])
        self.paal = dataclasses.replace(s.paal, ontvangen=[])
        self.prijzen = dataclasses.replace(s.prijzen)
        self.nu = dt.datetime.fromisoformat(s.begin)
        # Vanaf welke dag `Zon.wolken_per_dag` telt.
        self.zon.eerste_dag = self.nu.date()
        # Wanneer het programma op de vaatwasser gekozen werd, en de eindtijd
        # zoals Home Connect hem laat zien met sinds wanneer: Home Assistant
        # zet `last_changed` alleen als de waarde verandert. Zie
        # `Vaatwasser.eindtijd`.
        vw = s.vaatwasser
        self.vw_gekozen_op = (
            self.nu.replace(hour=int(vw.gekozen[:2]), minute=int(vw.gekozen[3:5]), second=0)
            if vw is not None and vw.gekozen else self.nu
        )
        self.vw_eind_waarde: str | None = None
        self.vw_eind_sinds: dt.datetime | None = None
        self.p1_weg_tot: dt.datetime | None = None
        # De laatste melding van een P1 die niet elke stap meldt: (tijd, netto).
        self.meter_melding: tuple[dt.datetime, float] | None = None
        self.prijzen_weg_tot: dt.datetime | None = None
        self.oven_tot: dt.datetime | None = None
        self.equalizer_vrij: float | None = None
        # Sensoren die tijdelijk `unavailable` zijn, met tot wanneer.
        self.weg: dict[str, dt.datetime] = {}
        self.reden = ""
        self.oven_w = s.oven_w
        if s.kabel_erin is None:
            self.paal.kabel = True
        # wat er deze minuut gebeurde
        self.zon_w = 0.0
        self.huis_w = 0.0
        self.paal_w = 0.0
        self.paal_fasen = 1

    # Het weer en het huis zoals ze op dit moment zijn.
    def meet(self) -> None:
        nu = self.nu
        self.zon_w = self.zon.nu_kw(nu) * 1000
        self.huis_w = self.huis.watt(nu)
        if self.oven_tot is not None and nu < self.oven_tot:
            self.huis_w += self.oven_w
        # De vaatwasser hangt op de eerste fase en telt bij het huis: de meter
        # ziet hem, de coach leest hem apart via zijn eigen vermogenssensor.
        if self.vaatwasser is not None:
            self.vw_w = self.vaatwasser.stap(nu)
            self.huis_w += self.vw_w
        # De boiler hangt net zo in huis: de meter ziet hem, de coach leest
        # hem apart via zijn eigen meetstekker.
        if self.boiler is not None:
            self.boiler_w = self.boiler.stap(nu, self.s.stap_seconden)
            self.huis_w += self.boiler_w
        if self.batterij is not None:
            self.bat_w = self.batterij.stap(nu, self.s.stap_seconden)
        self.paal.stap(nu)
        aanbod = self.paal.aanbod()
        # De Equalizer zit tussen de paal en de auto: hij laat nooit meer door
        # dan er naast het huis onder de zekering past, en zegt dat erbij.
        self.reden = ""
        if self.s.equalizer:
            huis = self.huis.per_fase(self.huis_w, self.s.aansluiting_fasen)
            vrij = self.s.zekering - max(huis) / VOLT
            self.equalizer_vrij = max(0.0, vrij)
            if vrij < MIN_AMPS:
                if aanbod >= MIN_AMPS:
                    self.reden = "eq_too_low_current"
                aanbod = 0.0
            elif aanbod > vrij:
                self.reden = "limited_by_equalizer"
                aanbod = math.floor(vrij)
        trok = self.auto.trekt_amps
        # Op hoeveel fasen deze sessie loopt, of gaat lopen als hij nu begint.
        # Met een drempel kiest de paal naar wat hem op dat moment aangeboden
        # wordt; zie `fase_drempel`.
        if self.paal.fase_drempel is not None:
            volgende = 1 if aanbod < self.paal.fase_drempel else self.paal.fasen
        else:
            volgende = 1 if self.paal.kiest_een_fase else self.paal.fasen
        fasen_nu = self.paal.fasen_nu if trok > 0 else volgende
        self.auto.stap(aanbod, self.paal.gestart, self.s.stap_seconden, nu,
                       fasen=min(self.auto.fasen, fasen_nu))
        # De paal kiest zijn fasen bij het begin van een sessie, niet
        # halverwege. Een Easee in automatische modus pakt er soms één.
        if self.auto.trekt_amps > 0 and trok <= 0:
            self.paal.fasen_nu = volgende
            self.paal.kiest_een_fase = False
        self.paal_fasen = min(self.auto.fasen, self.paal.fasen_nu)
        self.paal_w = self.auto.trekt_amps * VOLT * self.paal_fasen
        # Boven de groep: de paal grijpt na een minuut zelf in, met een
        # herstart van de sessie. Een auto die daar niet tegen kan gaat in
        # storing en de paal meldt "completed".
        groep = self.paal.circuit_amps
        if groep is not None and self.auto.trekt_amps > groep + 1e-9:
            if self.paal.boven_groep_sinds is None:
                self.paal.boven_groep_sinds = nu
            elif nu - self.paal.boven_groep_sinds >= dt.timedelta(minutes=1):
                self.paal.boven_groep_sinds = None
                self.paal.herstarts += 1
                self.paal.fasen_nu = self.paal.fasen
                if self.auto.storing_bij_herstart:
                    self.auto.ga_in_storing()
                else:
                    self.auto.wakker = False
                self.auto.trekt_amps = 0.0
                self.paal_w = 0.0
        else:
            self.paal.boven_groep_sinds = None

    def verstrijk(self, seconden: float) -> None:
        """Een stap energie laten stromen."""
        kwh = self.paal_w / 1000 * seconden / 3600
        if kwh > 0:
            self.auto.laad(kwh)
            self.paal.teller_kwh += kwh
        self.nu += dt.timedelta(seconds=seconden)

    def fase_amps(self) -> list[float]:
        huis = self.huis.per_fase(self.huis_w, self.s.aansluiting_fasen)
        uit = []
        for i, w in enumerate(huis):
            a = w / VOLT
            if i < self.paal_fasen:
                a += self.auto.trekt_amps
            if self.batterij is not None and i == self.batterij.fase:
                a += self.bat_w / VOLT
            uit.append(a)
        return uit

    def publiceer(self, hass) -> None:
        """Alle sensoren zetten zoals Home Assistant ze nu zou tonen."""
        nu = self.nu
        z = hass.states.zet
        netto = self.huis_w + self.paal_w + self.bat_w - self.zon_w   # + is inkoop
        p1_weg = self.p1_weg_tot is not None and nu < self.p1_weg_tot
        weg = "unavailable"
        # De meter krijgt de tijd van de wereld mee: de regelaar van de batterij
        # kijkt hoe oud een meting is, en de klok van deze computer zegt daar
        # niets over.
        stempel = nu.replace(tzinfo=dt.timezone.utc) if self.batterij is not None else None
        gemeld = netto
        if self.batterij is not None and self.batterij.meter_tik_s > 0:
            tik, fase = self.batterij.meter_tik_s, self.batterij.meter_fase_s
            if self.meter_melding is None or (nu.second + nu.minute * 60) % tik == fase:
                self.meter_melding = (nu, netto)
            gemeld = self.meter_melding[1]
            stempel = self.meter_melding[0].replace(tzinfo=dt.timezone.utc)

        def w(waarde, eenheid):
            return {"state": waarde, "attributes": {"unit_of_measurement": eenheid}}

        z(E["zon"], weg if p1_weg else w(f"{self.zon_w:.0f}", "W"))
        z(E["afname"], weg if p1_weg else w(f"{max(0.0, gemeld):.0f}", "W"), last_updated=stempel)
        z(E["teruglevering"], weg if p1_weg else w(f"{max(0.0, -gemeld):.0f}", "W"), last_updated=stempel)
        teken = -1 if self.s.net == "signed-omgekeerd" else 1
        z(E["net"], weg if p1_weg else w(f"{teken * gemeld:.0f}", "W"), last_updated=stempel)
        if self.batterij is not None:
            bat = self.batterij
            z(E["bat_soc"], w(f"{bat.soc:.0f}", "%"))
            z(E["bat_vermogen"], w(f"{bat.sensor_w(nu):.0f}", "W"))
            z(E["bat_cap"], w(f"{bat.capaciteit_kwh:.1f}", "kWh"))
            z(E["bat_hoog"], w(f"{bat.soc_max:.0f}", "%"))
            z(E["bat_laag"], w(f"{bat.soc_min:.0f}", "%"))
            z(E["bat_in"], w(f"{bat.teller_in:.3f}", "kWh"))
            z(E["bat_uit"], w(f"{bat.teller_uit:.3f}", "kWh"))
            z(E["bat_modus"], bat.modus)
            z(E["bat_richting"], {"state": bat.richting,
                                  "attributes": {"options": ["charge", "discharge"]}})
            # Zoals de echte: deze knop leest niet terug wat erin staat.
            z(E["bat_stuur"], {"state": "0", "attributes": {
                "unit_of_measurement": "W", "max_charge_power": 7000, "max_discharge_power": 2500}})
        for naam, a in zip(("l1", "l2", "l3"), self.fase_amps()):
            z(E[naam], weg if p1_weg else w(f"{a:.2f}", "A"))

        status = self.paal.status(self.auto)
        z(E["status"], status)
        if self.paal.merk == "alfen":
            # Zoals alfen_modbus het meldt: twee aan/uit-sensoren en de modus
            # 3-toestand. "Completed" kent een Alfen niet: een volle auto is
            # een auto met aanbod die niets neemt, B2.
            z(E["alfen_connected"], "off" if status == "disconnected" else "on")
            z(E["alfen_charging"], "on" if status == "charging" else "off")
            z(E["alfen_mode3"], {"disconnected": "A", "charging": "C2"}.get(
                status, "B2" if self.paal.dyn_limit >= MIN_AMPS else "B1"))
            z(E["alfen_limit"], w(f"{self.paal.dyn_limit:.1f}", "A"))
        z(E["stroom"], w(f"{self.auto.trekt_amps:.2f}", "A"))
        z(E["vermogen"], w(f"{self.paal_w:.0f}", "W"))
        z(E["max"], w(f"{self.paal.max_amps:.0f}", "A"))
        z(E["dyn"], w(f"{self.paal.dyn_limit:.0f}", "A"))
        if self.paal.circuit_amps is not None:
            z(E["circuit"], w(f"{self.paal.circuit_amps:.0f}", "A"))
        z(E["teller"], w(f"{self.paal.teller(nu):.3f}", "kWh"))

        soc = self.auto.gemelde_soc(nu)
        z(E["soc"], "unavailable" if soc is None else w(str(soc), "%"))
        if self.vaatwasser is not None:
            vw = self.vaatwasser
            z(E["vw_status"], vw.status)
            z(E["vw_programma"], vw.programma)
            if vw.eindtijd_tijdstip:
                eind = vw.eindtijd(nu, self.vw_gekozen_op)
                waarde = "unavailable" if eind is None else eind.isoformat()
                if waarde != self.vw_eind_waarde:
                    self.vw_eind_waarde, self.vw_eind_sinds = waarde, nu
                z(E["vw_rest"], waarde, last_updated=self.vw_eind_sinds)
            else:
                rest = vw.resterend(nu)
                z(E["vw_rest"], "unknown" if rest is None else w(str(rest), "min"))
            z(E["vw_deur"], "on" if vw.deur_open else "off")
            z(E["vw_vermogen"], w(f"{self.vw_w:.0f}", "W"))
        if self.boiler is not None:
            z(E["boiler_switch"], "on" if self.boiler.aan else "off")
            z(E["boiler_vermogen"], w(f"{self.boiler_w:.0f}", "W"))
        if self.s.equalizer:
            z(E["equalizer"], w(f"{self.equalizer_vrij:.1f}", "A"))
            z(E["reden"], self.reden or "none")

        # Een sensor die even niets zegt, wat de rest ook doet. Na de andere
        # sensoren, zodat dit wint.
        for naam, tot in list(self.weg.items()):
            if nu < tot:
                z(E[naam], weg)
            else:
                del self.weg[naam]

        prijzen_weg = self.prijzen_weg_tot is not None and nu < self.prijzen_weg_tot
        if self.s.contract.startswith("dynamisch") and prijzen_weg:
            z(E["prijs"], weg)
            z(E["markt"], weg)
        elif self.s.contract.startswith("dynamisch"):
            z(E["prijs"], {"state": f"{self.prijzen.all_in(nu):.5f}",
                           "attributes": {"unit_of_measurement": "€/kWh",
                                          "prices": self.prijzen.lijst(nu, True)}})
            z(E["markt"], {"state": f"{self.prijzen.kaal(nu):.5f}",
                           "attributes": {"unit_of_measurement": "€/kWh",
                                          "prices": self.prijzen.lijst(nu, False)}})

        if self.s.voorspeller != "geen":
            uur = nu.replace(minute=0, second=0, microsecond=0)
            rest = sum(self.zon.verwacht_kwh(uur + dt.timedelta(hours=i))
                       for i in range(24 - uur.hour))
            z(E["zon_rest"], w(f"{rest:.2f}", "kWh"))
            z(E["zon_dit_uur"], w(f"{self.zon.verwacht_kwh(uur):.3f}", "kWh"))
            z(E["zon_volgend_uur"], w(f"{self.zon.verwacht_kwh(uur + dt.timedelta(hours=1)):.3f}", "kWh"))
            z(E["zon_piek"], self.zon.piek_moment(nu.date()).isoformat())

    # --- wat de coach van buiten krijgt ---

    async def zonkromme(self) -> dict:
        """Wat het energiedashboard zou geven: een uurkromme, vandaag en morgen."""
        if self.s.voorspeller != "dashboard":
            return {}
        uit = {}
        vandaag = dt.datetime.combine(self.nu.date(), dt.time(0))
        for i in range(48):
            uur = vandaag + dt.timedelta(hours=i)
            kwh = self.zon.verwacht_kwh(uur)
            if kwh > 0:
                uit[uur] = kwh
        return uit

    def archief(self):
        """Zeven dagen kwartieren van vóór de proef, zoals archive.py ze bewaart."""
        wereld = self

        class NepArchief:
            async def async_lees(self, ids, start, einde):
                uit = {e: [] for e in ids}
                dag0 = dt.datetime.combine(wereld.nu.date(), dt.time(0))
                for d in range(1, 8):
                    for k in range(96):
                        t = dag0 - dt.timedelta(days=d) + dt.timedelta(minutes=15 * k)
                        huis = wereld.huis.watt(t, dag_offset=-d)
                        # Twee van de zeven dagen bewolkt, de rest helder.
                        zon = wereld.zon.helder_kw(t) * (0.3 if d in (3, 6) else 1.0) * 1000
                        netto = huis - zon
                        stempel = calendar.timegm(t.timetuple())
                        rij = {
                            E["zon"]: zon,
                            E["afname"]: max(0.0, netto),
                            E["teruglevering"]: max(0.0, -netto),
                            E["net"]: (-1 if wereld.s.net == "signed-omgekeerd" else 1) * netto,
                            E["vermogen"]: 0.0,
                            E["bat_vermogen"]: 0.0,
                        }
                        for e in ids:
                            if e in rij:
                                uit[e].append({"start": stempel, "gemiddeld": rij[e]})
                return uit

        return NepArchief()

    # --- gebeurtenissen ---

    def gebeurtenis(self, actie: str, arg, coach, inst: dict) -> str:
        if actie == "kabel_uit":
            self.paal.kabel = False
            self.paal.gestart = False
            self.auto.wakker = False
            self.auto.klaar = False
            return "de kabel gaat eruit"
        if actie == "kabel_in":
            self.paal.kabel = True
            if arg is not None:
                self.auto.soc = float(arg)
                self.auto.klaar = False
            return f"de kabel gaat erin, auto op {self.auto.soc:.0f}%"
        if actie == "pauze":
            coach.async_pause("paal", bool(arg))
            return "pauze aan" if arg else "pauze uit"
        if actie == "snelladen":
            coach.async_boost("paal", bool(arg))
            return "snelladen aan" if arg else "snelladen uit"
        if actie == "soc_opgeven":
            inst["car_soc"] = [{"device": "paal", "car": "auto", "percent": float(arg),
                                "meter": self.paal.teller(self.nu)}]
            return f"bewoner geeft {arg}% op"
        if actie == "p1_weg":
            self.p1_weg_tot = self.nu + dt.timedelta(minutes=int(arg))
            return f"de P1-meter valt {arg} minuten weg"
        if actie == "prijzen_weg":
            self.prijzen_weg_tot = self.nu + dt.timedelta(minutes=int(arg))
            return f"de prijssensor valt {arg} minuten weg"
        if actie == "oven":
            self.oven_tot = self.nu + dt.timedelta(minutes=int(arg))
            return f"de oven gaat {arg} minuten aan ({self.oven_w:.0f} W)"
        if actie == "paal_max":
            self.paal.max_amps = float(arg)
            return f"de paal staat nu op maximaal {arg} A"
        if actie == "storing":
            self.auto.ga_in_storing()
            return "de auto gaat in storing, de paal meldt 'completed'"
        if actie == "vaatwasser_vrijgeven":
            klaar = set(inst.get("ready_devices") or [])
            klaar.add("vaatwasser")
            inst["ready_devices"] = sorted(klaar)
            if self.vaatwasser is not None and self.vaatwasser.status == "finished":
                self.vaatwasser.status = "ready"
                self.vaatwasser.gestart_op = None
            return "de bewoner geeft de vaatwasser vrij: ingeruimd en dicht"
        if actie == "vaatwasser_nu_starten":
            # "Ingeruimd en nu starten" (de eigenaar, 13-09-2026).
            for sleutel in ("ready_devices", "ready_now"):
                inst[sleutel] = sorted(set(inst.get(sleutel) or []) | {"vaatwasser"})
            if self.vaatwasser is not None and self.vaatwasser.status == "finished":
                self.vaatwasser.status = "ready"
                self.vaatwasser.gestart_op = None
            return "de bewoner geeft de vaatwasser vrij: ingeruimd en nu starten"
        if actie == "vaatwasser_deur":
            self.vaatwasser.deur_open = bool(arg)
            return "de deur van de vaatwasser gaat " + ("open" if arg else "dicht")
        if actie == "vaatwasser_aan":
            self.vaatwasser.zet_aan(self.nu)
            return "de bewoner zet de vaatwasser zelf aan"
        if actie == "sensor_weg":
            naam, minuten = arg
            self.weg[naam] = self.nu + dt.timedelta(minutes=int(minuten))
            return f"de sensor {E[naam]} ({naam}) valt {minuten} minuten weg"
        raise ValueError(f"onbekende gebeurtenis {actie}")


# --- de diensten die de coach aanroept ---------------------------------------


class Diensten:
    def __init__(self, wereld: Wereld, hass, verloop: Verloop):
        self.wereld = wereld
        self.hass = hass
        self.verloop = verloop
        self.verstuurd = []

    async def async_call(self, domein, dienst, data, blocking=False):
        self.verstuurd.append((domein, dienst, dict(data)))
        if domein == "easee":
            self.wereld.paal.opdracht(dienst, data, self.wereld.nu)
            if dienst == "action_command" and data.get("action_command") == "start":
                self.wereld.auto.start_ontvangen(self.wereld.nu)
            self.verloop.opdrachten.append((self.wereld.nu, dienst, dict(data)))
            # De paal meldt zijn nieuwe limiet meteen terug; de coach leest die
            # om te zien of zijn opdracht is aangenomen.
            self.hass.states.zet(E["dyn"], {"state": f"{self.wereld.paal.dyn_limit:.0f}",
                                            "attributes": {"unit_of_measurement": "A"}})
        elif domein == "number" and dienst == "set_value" and data.get("entity_id") == E["alfen_limit"]:
            self.wereld.paal.opdracht("set_value", data, self.wereld.nu)
            self.verloop.opdrachten.append((self.wereld.nu, dienst, dict(data)))
            self.hass.states.zet(E["dyn"], {"state": f"{self.wereld.paal.dyn_limit:.0f}",
                                            "attributes": {"unit_of_measurement": "A"}})
            self.hass.states.zet(E["alfen_limit"], {"state": f"{self.wereld.paal.dyn_limit:.1f}",
                                                    "attributes": {"unit_of_measurement": "A"}})
        elif domein == "notify":
            self.verloop.meldingen.append((self.wereld.nu, data.get("message", "")))
        elif data.get("entity_id") == E["boiler_switch"] and dienst in ("turn_on", "turn_off"):
            if self.wereld.boiler is not None:
                self.wereld.boiler.aan = dienst == "turn_on"
                self.verloop.boiler_schakels.append((self.wereld.nu, dienst == "turn_on"))
            self.hass.states.zet(E["boiler_switch"], "on" if dienst == "turn_on" else "off")
        elif data.get("entity_id") == E["bat_stuur"] and dienst == "set_value":
            bat = self.wereld.batterij
            watt = float(data.get("value") or 0.0) * (1 if bat.richting == "charge" else -1)
            bat.opdracht(watt, self.wereld.nu)
            self.verloop.bat_opdrachten.append((self.wereld.nu, watt))
        elif data.get("entity_id") == E["bat_hoog"] and dienst == "set_value":
            self.wereld.batterij.soc_max = float(data.get("value") or 0.0)
            self.verloop.bat_grenzen.append((self.wereld.nu, self.wereld.batterij.soc_max))
            self.hass.states.zet(E["bat_hoog"], {"state": f"{self.wereld.batterij.soc_max:.0f}",
                                                 "attributes": {"unit_of_measurement": "%", "min": 80, "max": 100}})
        elif data.get("entity_id") == E["bat_richting"] and dienst == "select_option":
            self.wereld.batterij.richting = data.get("option")
            self.hass.states.zet(E["bat_richting"], {"state": data.get("option"),
                                                     "attributes": {"options": ["charge", "discharge"]}})
        elif data.get("entity_id") == E["bat_modus"] and dienst == "select_option":
            self.wereld.batterij.modus = data.get("option")
            self.verloop.bat_modi.append((self.wereld.nu, data.get("option")))
            self.hass.states.zet(E["bat_modus"], data.get("option"))
        elif domein == "button" and data.get("entity_id") == E["vw_start"]:
            self.verloop.vw_gedrukt.append(self.wereld.nu)
            if self.wereld.vaatwasser is not None:
                self.wereld.vaatwasser.druk_start(self.wereld.nu)


# --- draaien -----------------------------------------------------------------


def _prijs_nu(coach, inst, nu) -> tuple[float | None, float | None]:
    """Wat een kWh op dit moment kost en opbrengt, zoals de coach het ziet."""
    prijzen = coach._prices(inst)
    if prijzen:
        rij = planner.price_now(prijzen, nu)
        if rij is None:
            return None, None
        return rij["price"], rij.get("feed_in")
    tarief = coach._tariff(inst)
    return tarief.buy, tarief.feed_in


def optimum(s: Scenario, coach, inst, kabel_in: dt.datetime) -> float | None:
    """Wat de laadbeurt had gekost met de hele dag vooraf bekend.

    Dezelfde som als de coach zelf maakt (`schijven` en `goedkoopste`), maar
    met de werkelijke zon en het werkelijke huisverbruik in plaats van een
    voorspelling, en met álle prijzen bekend. Dus geen andere maatstaf, maar
    dezelfde met perfecte kennis. Alleen als ondergrens te lezen: hij kent de
    aanloop van de auto niet en telt geen wekstroom.
    """
    w = Wereld(s)
    auto = s.auto
    nodig = planner.energy_needed_kwh(planner.Car(
        capacity_kwh=auto.capaciteit_kwh, phases=auto.fasen, soc_percent=auto.soc,
        target_percent=auto.doel))
    if nodig is None:
        return None
    einde = klaar_tijd_na(s, kabel_in)
    grens = einde or (kabel_in + dt.timedelta(hours=s.duur_uren))
    zon = {}
    huis = {}
    t = kabel_in.replace(minute=0, second=0)
    while t < grens:
        zon[t] = sum(w.zon.nu_kw(t + dt.timedelta(minutes=m)) for m in range(0, 60, 5)) / 12
        huis[t.hour] = sum(w.huis.watt(t + dt.timedelta(minutes=m)) for m in range(0, 60, 5)) / 12 / 1000
        t += dt.timedelta(hours=1)
    if s.contract.startswith("dynamisch"):
        # Alle prijzen bekend, tot en met de dag van de klaar-tijd.
        for sleutel, all_in in ((E["prijs"], True), (E["markt"], False)):
            coach.hass.states.zet(sleutel, {"state": "0", "attributes": {
                "prices": w.prijzen.lijst(kabel_in.replace(hour=23), all_in, grens.date())}})
    prijzen = coach._prices(inst)
    tarief = coach._tariff(inst)
    fasen = min(auto.fasen, s.paal.fasen)
    ceiling = int(min(s.paal.max_amps, auto.max_amps))
    car = planner.Car(capacity_kwh=auto.capaciteit_kwh, phases=fasen,
                      soc_percent=auto.soc, max_amps=auto.max_amps,
                      target_percent=auto.doel)
    uur0 = kabel_in.replace(minute=0, second=0)
    grid = planner.Grid(surplus_w=max(0.0, zon.get(uur0, 0.0) * 1000 - huis.get(uur0.hour, 0.0) * 1000))
    alle = planner.schijven(kabel_in, prijzen, grid, car, ceiling, None, einde, tarief,
                            planner.Forecast(solar_kwh=zon, house_kwh=huis))
    gekozen = planner.goedkoopste(alle, nodig)
    if sum(k for _, k in gekozen) < nodig - 0.05:
        return None   # het paste niet, dan is er geen eerlijk optimum
    return sum(schijf.price * kwh for schijf, kwh in gekozen)


def draai(s: Scenario, toon: bool = False) -> Verloop:
    wereld = Wereld(s)
    inst = instellingen(s)
    stap_s = s.stap_seconden
    verloop = Verloop(scenario=s, stap_uur=stap_s / 3600)
    hass = NepHass({})
    hass.services = Diensten(wereld, hass, verloop)
    store = NepStore(inst)
    hass.data["domotiapp_coach"] = {"store": store}
    coach = coachmod.ChargerCoach(hass)
    coach._sleep = lambda seconds: asyncio.sleep(0)
    coach._async_zon_uit_dashboard = wereld.zonkromme
    coachmod.async_get_archive = lambda hass: wereld.archief()

    # De klok van Home Assistant is de klok van de wereld.
    dtutil.now = lambda: wereld.nu
    dtutil.utcnow = lambda: wereld.nu.replace(tzinfo=dt.timezone.utc)

    einde = wereld.nu + dt.timedelta(hours=s.duur_uren)
    gebeurtenissen = [
        (_moment_op(wereld.nu, tijd), actie, arg) for tijd, actie, arg in s.gebeurtenissen
    ]
    if s.kabel_erin:
        gebeurtenissen.append((_moment_op(wereld.nu, s.kabel_erin), "kabel_in", None))
    gebeurtenissen.sort(key=lambda g: g[0])
    kabel_in = wereld.nu if s.kabel_erin is None else _moment_op(wereld.nu, s.kabel_erin)
    verloop.klaar_tijd = klaar_tijd_na(s, kabel_in)
    boiler_klaar = None
    if s.boiler is not None and s.boiler_klaar_om:
        boiler_klaar = _moment_op(wereld.nu, s.boiler_klaar_om)
        if boiler_klaar <= wereld.nu:
            boiler_klaar += dt.timedelta(days=1)

    vorige = (None, None)
    laatste_ronde = None

    class Fasemelding:
        """Wat de luisteraar van de coach van Home Assistant krijgt: één toestand."""

        def __init__(self, entity_id, state):
            self.entity_id = entity_id
            self.state = state

    def nieuwe_coach():
        """Zoals Home Assistant hem na een herstart neerzet: leeg geheugen,
        dezelfde opslag, dezelfde sensoren."""
        c = coachmod.ChargerCoach(hass)
        c._sleep = lambda seconds: asyncio.sleep(0)
        c._async_zon_uit_dashboard = wereld.zonkromme
        return c

    async def lus():
        nonlocal vorige, laatste_ronde, coach
        while wereld.nu < einde:
            nu = wereld.nu
            while gebeurtenissen and gebeurtenissen[0][0] <= nu:
                _, actie, arg = gebeurtenissen.pop(0)
                if actie == "herstart":
                    # Een onverwachte herstart van Home Assistant: de coach
                    # verliest alles wat hij in zijn hoofd had en begint
                    # opnieuw uit de opslag. De eigenaar op 04-09-2026: "ook
                    # onverwachte herstarten."
                    coach = nieuwe_coach()
                    laatste_ronde = None
                    tekst = "Home Assistant herstart: de coach begint met een leeg geheugen"
                else:
                    tekst = wereld.gebeurtenis(actie, arg, coach, inst)
                if toon:
                    print(f"{nu:%a %H:%M}  >> {tekst}")
                # Een knop of een kabel wekt de coach meteen, net als in HA.
                if actie in ("pauze", "snelladen", "kabel_uit", "kabel_in"):
                    laatste_ronde = None
            wereld.meet()
            wereld.publiceer(hass)
            await hass.afmaken()
            # De fasen komen bij de coach binnen op het tempo van de meter, en
            # een fase boven de grens wekt hem. Zie `_async_phase_changed`.
            for naam, a in zip(("l1", "l2", "l3"), wereld.fase_amps()):
                if E[naam] in coach._watched_phases and wereld.p1_weg_tot is None:
                    coach._async_phase_changed(Fasemelding(E[naam], f"{a:.2f}"))
            gewekt = bool(hass.taken)
            await hass.afmaken()
            if gewekt:
                laatste_ronde = nu
            elif laatste_ronde is None or nu - laatste_ronde >= dt.timedelta(seconds=60):
                await coach._round(nu)
                laatste_ronde = nu
            # De regelaar van de batterij loopt op het tempo van de meter, los
            # van de ronde. Zie `_async_regel_tik` in coach.py.
            if wereld.batterij is not None:
                await coach._async_regel_tik()
            besluit = coach.state.get("paal") or {}
            # Een domme vaatwasser: zegt de coach "zet hem aan", dan doet de
            # bewoner dat zoveel minuten later, als hij dat doet.
            if wereld.vaatwasser is not None and not wereld.vaatwasser.slim:
                vw_besluit = coach.state.get("vaatwasser") or {}
                vraagt = bool(vw_besluit.get("charge")) and not vw_besluit.get("running") \
                    and wereld.vaatwasser.status != "run"
                if vraagt and wereld.vw_gevraagd is None:
                    wereld.vw_gevraagd = nu
                    verloop.vw_gevraagd.append(nu)
                elif not vraagt:
                    wereld.vw_gevraagd = None
                reageert = wereld.vaatwasser.bewoner_reageert_min
                if (vraagt and reageert is not None and wereld.vw_gevraagd is not None
                        and nu - wereld.vw_gevraagd >= dt.timedelta(minutes=reageert)):
                    if wereld.vaatwasser.zet_aan(nu):
                        verloop.vw_gedrukt.append(nu)
                        if toon:
                            print(f"{nu:%a %H:%M}  >> de bewoner zet de vaatwasser aan, zoals de coach vroeg")
                    wereld.vw_gevraagd = None
            prijs, terug = _prijs_nu(coach, inst, nu)
            fasen = wereld.fase_amps()
            netto = wereld.huis_w + wereld.paal_w + wereld.bat_w - wereld.zon_w
            if wereld.batterij is not None:
                deel_b = verloop.stap_uur / 1000
                zonder = netto - wereld.bat_w
                stand = (coach.state.get("batterij") or {}).get("mode", "")
                verloop.bat_verloop.append((nu, netto, wereld.bat_w, wereld.batterij.soc, stand))
                verloop.bat_afname_kwh += max(0.0, netto) * deel_b
                verloop.bat_levering_kwh += max(0.0, -netto) * deel_b
                if prijs is not None:
                    def _rekening(watt):
                        return watt * deel_b * (prijs if watt >= 0 else (terug or 0.0))
                    verloop.bat_kosten_met += _rekening(netto)
                    verloop.bat_kosten_zonder += _rekening(zonder)
            regel = Regel(
                tijd=nu, regel=besluit.get("rule", "?"), amps=int(besluit.get("amps") or 0),
                reden=besluit.get("reason", ""), plan=besluit.get("plan", ""),
                nodig_kwh=(besluit.get("plan_ahead") or {}).get("kwh_needed"),
                paal_w=wereld.paal_w, paal_amps=wereld.auto.trekt_amps, soc=wereld.auto.soc,
                zon_w=wereld.zon_w, huis_w=wereld.huis_w,
                over_w=max(0.0, wereld.zon_w - wereld.huis_w),
                inkoop_w=max(0.0, netto), terug_w=max(0.0, -netto), prijs=prijs,
                fase_amps=fasen, status=wereld.paal.status(wereld.auto),
            )
            verloop.regels.append(regel)
            verloop.hoogste_fase = max(verloop.hoogste_fase, *fasen)

            # de boekhouding van deze minuut
            over = max(0.0, wereld.zon_w - wereld.huis_w)
            uit_zon = min(wereld.paal_w, over)
            uit_net = wereld.paal_w - uit_zon
            deel = verloop.stap_uur / 1000
            verloop.geladen_kwh += wereld.paal_w * deel
            verloop.uit_zon_kwh += uit_zon * deel
            verloop.uit_net_kwh += uit_net * deel
            if prijs is not None:
                verloop.betaald += uit_net * deel * prijs
            if terug is not None:
                verloop.misgelopen += uit_zon * deel * terug
            if verloop.klaar_op is None and wereld.auto.klaar and wereld.paal.kabel:
                verloop.klaar_op = nu
            if wereld.vaatwasser is not None:
                vw = wereld.vaatwasser
                if vw.status == "run" and verloop.vw_gestart is None:
                    verloop.vw_gestart = vw.gestart_op
                if vw.status == "finished" and verloop.vw_klaar is None and verloop.vw_gestart is not None:
                    verloop.vw_klaar = nu
                # En elke beurt apart, voor een proef die er meer dan één ziet.
                if vw.status == "run" and (not verloop.vw_beurten or verloop.vw_beurten[-1][1] is not None):
                    sessie = coach._programma.get("vaatwasser") or {}
                    programma = sessie.get("programma")
                    verloop.vw_beurten.append([vw.gestart_op, None, bool(programma is not None and programma.measured)])
                if vw.status == "finished" and verloop.vw_beurten and verloop.vw_beurten[-1][1] is None:
                    verloop.vw_beurten[-1][1] = nu
                if wereld.vw_w > 0:
                    verloop.vw_kwh += wereld.vw_w * deel
                    if prijs is not None:
                        verloop.vw_betaald += wereld.vw_w * deel * prijs
            if wereld.boiler is not None:
                if wereld.boiler_w > 0:
                    verloop.boiler_kwh += wereld.boiler_w * deel
                    uit_zon_b = min(wereld.boiler_w, max(0.0, over - wereld.paal_w))
                    verloop.boiler_zon_kwh += uit_zon_b * deel
                    if prijs is not None:
                        verloop.boiler_betaald += (wereld.boiler_w - uit_zon_b) * deel * prijs
                verloop.boiler_laagste = wereld.boiler.laagste_kwh
                # De eerste klaar-tijd ná het begin van de proef: dáár hoort
                # er warm water te zijn. Valt hij op de begindag al achter ons,
                # dan is het die van de volgende dag.
                if boiler_klaar is not None and verloop.boiler_bij_klaar is None and nu >= boiler_klaar:
                    verloop.boiler_bij_klaar = wereld.boiler.inhoud_kwh

            if (verloop.klaar_tijd is not None and verloop.soc_bij_klaar_tijd is None
                    and nu >= verloop.klaar_tijd):
                verloop.soc_bij_klaar_tijd = wereld.auto.soc

            if toon:
                if (regel.regel, regel.amps) != vorige or (nu.minute == 0 and nu.second == 0):
                    _toon_regel(regel)
                for t, m in verloop.meldingen:
                    if t == nu:
                        print(f"           !! melding: {m}")
            vorige = (regel.regel, regel.amps)
            wereld.verstrijk(stap_s)

    asyncio.run(lus())
    asyncio.run(hass.afmaken())
    try:
        verloop.beurten = asyncio.run(coachmod.async_get_beurten(hass).async_list())
        verloop.paal_herstarts = wereld.paal.herstarts
        verloop.paal_terugvallen = wereld.paal.terugvallen
        verloop.geleerd = {int(r["band"]): float(r["kw"]) for r in inst.get("car_pace") or []
                           if isinstance(r, dict) and r.get("car") == "auto"}
        verloop.vw_gemeten = [r for r in inst.get("program_measured") or []
                              if isinstance(r, dict) and r.get("device") == "vaatwasser"]
        verloop.boiler_geleerd = next(
            (r for r in inst.get("boiler_learned") or []
             if isinstance(r, dict) and r.get("device") == "boiler"), {}
        )
        verloop.bat_stand = next(
            (r for r in inst.get("battery_state") or []
             if isinstance(r, dict) and r.get("device") == "batterij"), {}
        )
    except Exception as fout:  # noqa: BLE001
        verloop.fouten.append(f"beurten niet te lezen: {fout!r}")
    if verloop.klaar_tijd is not None and verloop.soc_bij_klaar_tijd is None:
        verloop.soc_bij_klaar_tijd = wereld.auto.soc
    try:
        verloop.optimum = optimum(s, coach, inst, kabel_in)
    except Exception as fout:  # noqa: BLE001 - het optimum is een maatstaf, geen proef
        verloop.fouten.append(f"optimum niet te bepalen: {fout!r}")
    return verloop


def klaar_tijd_na(s: Scenario, moment: dt.datetime) -> dt.datetime | None:
    """De eerstvolgende klaar-tijd na dit moment, met de uitgevinkte dagen erin."""
    if not s.klaar_om or not s.schema_aan:
        return None
    h, m = map(int, s.klaar_om.split(":"))
    for offset in range(8):
        dag = moment.date() + dt.timedelta(days=offset)
        if dag.weekday() in s.dagen_uit:
            continue
        klaar = dt.datetime.combine(dag, dt.time(h, m))
        if klaar > moment:
            return klaar
    return None


def _moment_op(begin: dt.datetime, tijd: str) -> dt.datetime:
    """"13:10" op de eerste dag waarop dat nog komt; "+1 04:20" een dag later."""
    dagen = 0
    if " " in tijd:
        offset, tijd = tijd.split()
        dagen = int(offset)
    h, m = map(int, tijd.split(":"))
    moment = begin.replace(hour=h, minute=m, second=0, microsecond=0)
    if moment < begin:
        moment += dt.timedelta(days=1)
    return moment + dt.timedelta(days=dagen)


def _toon_regel(r: Regel) -> None:
    prijs = "  -  " if r.prijs is None else f"{r.prijs:.3f}"
    print(
        f"{r.tijd:%a %H:%M}  {r.regel:<26} {r.amps:2d}A  paal {r.paal_w/1000:4.1f}kW  "
        f"soc {r.soc:5.1f}%  zon {r.zon_w/1000:4.1f}  huis {r.huis_w/1000:3.1f}  "
        f"over {r.over_w/1000:4.1f}  €{prijs}  "
        f"L{'/'.join(f'{a:.0f}' for a in r.fase_amps)}"
    )
    print(f"           {r.reden}")


def samenvatting(v: Verloop) -> str:
    s = v.scenario
    klaar = "niet vol" if v.klaar_op is None else f"vol om {v.klaar_op:%a %H:%M}"
    kt = ""
    if v.klaar_tijd is not None:
        gehaald = (v.soc_bij_klaar_tijd is not None
                   and v.soc_bij_klaar_tijd >= min(s.auto.laadgrens, s.auto.doel,
                                                   planner.FULL_PERCENT))
        kt = (f"  klaar-tijd {v.klaar_tijd:%a %H:%M}: {'gehaald' if gehaald else 'GEMIST'}"
              f" ({v.soc_bij_klaar_tijd:.0f}%)")
    opt = "" if v.optimum is None else f"  optimum €{v.optimum:.2f}"
    if v.scenario.vaatwasser is not None:
        vw = (f"  vaatwasser {v.vw_gestart:%a %H:%M}-{v.vw_klaar:%H:%M} {v.vw_kwh:.2f} kWh €{v.vw_betaald:.2f}"
              if v.vw_gestart and v.vw_klaar else
              f"  vaatwasser {'draait nog' if v.vw_gestart else 'niet gestart'}")
        opt += vw
    if v.scenario.boiler is not None:
        vol = "" if v.boiler_bij_klaar is None else f", vat {v.boiler_bij_klaar:.1f} kWh op de klaar-tijd"
        opt += (f"  boiler {v.boiler_kwh:.2f} kWh (zon {v.boiler_zon_kwh:.2f}) €{v.boiler_betaald:.2f}"
                f", {sum(1 for _, aan in v.boiler_schakels if aan)}x aan{vol}")
    if v.scenario.batterij is not None:
        eind = v.bat_verloop[-1][3] if v.bat_verloop else 0.0
        opt += (f"  batterij: net {v.bat_afname_kwh:.1f} kWh erin en {v.bat_levering_kwh:.1f} eruit, "
                f"€{v.bat_kosten_met:.2f} tegen €{v.bat_kosten_zonder:.2f} zonder, "
                f"{len(v.bat_opdrachten)} opdrachten, {v.bat_wissels()} wissels, eindigt op {eind:.0f}%")
    return (
        f"{s.naam:<28} {v.geladen_kwh:5.1f} kWh (zon {v.uit_zon_kwh:4.1f}, net {v.uit_net_kwh:4.1f})"
        f"  kosten €{v.kosten:.2f} (betaald €{v.betaald:.2f}){opt}"
        f"  wissels {v.wissels():2d}  L-max {v.hoogste_fase:4.1f} A  {klaar}{kt}"
    )


def blokken(v: Verloop) -> list[str]:
    """De tijdlijn in blokken: van wanneer tot wanneer welke regel en stroom."""
    uit = []
    start = None
    vorige = None
    laatste = None
    for r in v.regels + [None]:
        sleutel = None if r is None else (r.regel, r.amps)
        if sleutel != vorige:
            if vorige is not None:
                uit.append(f"{start:%a %H:%M}-{laatste.tijd:%H:%M}  {vorige[0]:<26} {vorige[1]:2d} A")
            start = None if r is None else r.tijd
            vorige = sleutel
        laatste = r
    return uit


if __name__ == "__main__":
    import scenarios

    # Een Windows-console staat vaak nog op cp1252 en struikelt over een euroteken.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if len(sys.argv) < 2:
        print("scenario's:\n")
        for sc in scenarios.ALLE:
            print(f"  {sc.naam:<28} {sc.uitleg}")
        print("\npython tests/virtueel.py <naam>   of   python tests/virtueel.py alles")
        sys.exit(0)

    if sys.argv[1] == "alles":
        for sc in scenarios.ALLE:
            v = draai(sc)
            print(samenvatting(v))
            for fout in v.fouten:
                print(f"    ! {fout}")
        sys.exit(0)

    gekozen = [sc for sc in scenarios.ALLE if sc.naam == sys.argv[1]]
    if not gekozen:
        sys.exit(f"geen scenario {sys.argv[1]!r}; zie python tests/virtueel.py")
    sc = gekozen[0]
    kort = len(sys.argv) > 2 and sys.argv[2] == "kort"
    print(f"=== {sc.naam}: {sc.uitleg}\n")
    v = draai(sc, toon=not kort)
    if kort:
        for blok in blokken(v):
            print(f"  {blok}")
    print()
    print(samenvatting(v))
    if v.meldingen:
        print("\nmeldingen:")
        for t, m in v.meldingen:
            print(f"  {t:%a %H:%M}  {m}")
    for fout in v.fouten:
        print(f"  ! {fout}")
