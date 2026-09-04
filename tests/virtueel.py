"""Een virtueel huis waarin de coach een hele laadbeurt kan draaien.

De proeven in `test_coach.py` zijn foto's: een sensor krijgt een waarde, de
coach doet één ronde, en er wordt gekeken wat hij zei. Dit is de film. Er is
een zon die opkomt en ondergaat, een huis dat kookt, een auto die voller wordt
van wat de paal hem geeft, een meter die dat allemaal ziet, en een prijslijst
die om één uur 's middags de dag van morgen leert. De coach draait er elke
minuut een gewone ronde in, met zijn echte code, en krijgt alleen terug wat
zijn opdrachten in dat huis teweegbrengen.

Waarom dit bestaat: tot 04-09-2026 kon een laadbeurt alleen beproefd worden
met een lege bus aan een echte paal, bij Sven of bij een klant. Sven: "ik wil
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
    zaad: int = 1
    # Een echte uurkromme, kWh per uur van de dag, zoals het energiedashboard
    # hem geeft. Dan is dit het heldere dak en niet de sinus; `wolken` en
    # `voorspeld` werken er net zo op. Voor een scenario dat een echte woning
    # nabouwt, zoals Van den Dam op 04-09-2026.
    kromme: dict[int, float] | None = None

    PATRONEN = {"helder": 1.0, "bewolkt": 0.3, "geen": 0.0}

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

    def nu_kw(self, moment: dt.datetime) -> float:
        return self.helder_kw(moment) * self.factor(moment, self.wolken)

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
    # koken en avond. Uit de mediaan van een echte woning; zie Van den Dam in
    # scenarios.py.
    profiel: dict[int, float] | None = None

    def watt(self, moment: dt.datetime, dag_offset: int = 0) -> float:
        u = moment.hour + moment.minute / 60
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
        return w

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
    # Onder deze stroom komt hij niet op gang. Svens Ford wil 10 A om wakker te
    # worden en doet daarna op 6 A gewoon mee; zie `WAKE_AMPS` in planner.py.
    wek_amps: float = 6.0
    laadgrens: float = 100.0
    meldt_soc: bool = True
    rendement: float = 0.9
    aanloop_s: int = 60
    # Zo lang doet zijn app erover om een nieuw percentage te laten zien.
    soc_vertraging_min: int = 0

    # toestand
    trekt_amps: float = 0.0
    wakker: bool = False
    klaar: bool = False
    aanloop: int = 0
    soc_gemeld: list = field(default_factory=list)

    def stap(self, aanbod_amps: float, gestart: bool, stap_s: int = 60) -> None:
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
        self.trekt_amps = min(aanbod_amps, self.max_amps)

    def laad(self, kwh_aan_de_stekker: float) -> None:
        self.soc = min(
            100.0,
            self.soc + kwh_aan_de_stekker * self.rendement / self.capaciteit_kwh * 100,
        )

    def gemelde_soc(self, nu: dt.datetime) -> float | None:
        if not self.meldt_soc:
            return None
        self.soc_gemeld.append((nu, int(self.soc)))
        grens = nu - dt.timedelta(minutes=self.soc_vertraging_min)
        oud = [s for t, s in self.soc_gemeld if t <= grens]
        return oud[-1] if oud else self.soc_gemeld[0][1]


# --- de laadpaal -------------------------------------------------------------


@dataclass
class Paal:
    """Een Easee-achtige paal: een dynamische limiet met houdbaarheid, en
    start/pauze als opdracht."""

    max_amps: float = 16.0
    fasen: int = 3
    dyn_limit: float = 16.0
    ttl_tot: dt.datetime | None = None
    gestart: bool = False
    kabel: bool = False
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

    def stap(self, nu: dt.datetime) -> None:
        # Een limiet met houdbaarheid vervalt: dan staat er weer het maximum.
        if self.ttl_tot is not None and nu >= self.ttl_tot:
            self.dyn_limit = self.max_amps
            self.ttl_tot = None

    def aanbod(self) -> float:
        return min(self.dyn_limit, self.max_amps) if self.kabel else 0.0

    def status(self, auto: Auto) -> str:
        if not self.kabel:
            return "disconnected"
        if auto.klaar:
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


# --- de prijzen --------------------------------------------------------------

# Een gewone dag op de Nederlandse markt, kaal, per uur. Goedkoop in de nacht
# en rond het middaguur, duur bij het koken.
MARKT = [
    0.070, 0.065, 0.060, 0.060, 0.065, 0.080, 0.095, 0.110,
    0.130, 0.100, 0.060, 0.030, 0.010, 0.000, 0.010, 0.040,
    0.080, 0.140, 0.190, 0.210, 0.160, 0.120, 0.100, 0.085,
]


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
    vast_prijs: float = 0.28
    vast_teruglevering: float = 0.07
    vast_terugleverkosten: float = 0.0
    # (tijd, actie, argument): ("13:10", "kabel_uit", None), ("18:00", "pauze", True),
    # ("12:00", "snelladen", True), ("09:30", "soc_opgeven", 40), ("11:00", "p1_weg", 3),
    # ("20:00", "oven", 30)
    gebeurtenissen: list[tuple] = field(default_factory=list)

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
    return {
        "devices": [{
            "id": "paal",
            "type": "laadpaal",
            "name": "Laadpaal",
            "brand": "easee",
            "controllable": True,
            "device_id": "virtueel",
            "entity": E["vermogen"],
            "entities": {
                "status": E["status"],
                "current": E["stroom"],
                "max_limit": E["max"],
                "dynamic_limit": E["dyn"],
                "lifetime_energy": E["teller"],
                "no_current_reason": E["reden"] if s.equalizer else "",
            },
            "cars": [{
                "id": "auto",
                "name": auto.naam,
                "capacity_kwh": auto.capaciteit_kwh,
                "phases": "one" if auto.fasen == 1 else "three",
                "max_amps": auto.max_amps,
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
            "load_alert": {"targets": ["virtueel"]},
            "schedules": [{
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
        "car_soc": [],
        "ready_devices": [],
        "sessions": [],
    }


# --- de wereld zelf ----------------------------------------------------------


class Wereld:
    """Alles buiten de coach, en de klok."""

    def __init__(self, s: Scenario):
        self.s = s
        self.zon = dataclasses.replace(s.zon)
        self.huis = dataclasses.replace(s.huis)
        self.auto = dataclasses.replace(s.auto, soc_gemeld=[])
        self.paal = dataclasses.replace(s.paal, ontvangen=[])
        self.prijzen = dataclasses.replace(s.prijzen)
        self.nu = dt.datetime.fromisoformat(s.begin)
        self.p1_weg_tot: dt.datetime | None = None
        self.prijzen_weg_tot: dt.datetime | None = None
        self.oven_tot: dt.datetime | None = None
        self.equalizer_vrij: float | None = None
        self.reden = ""
        self.oven_w = 3000.0
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
        self.auto.stap(aanbod, self.paal.gestart, self.s.stap_seconden)
        self.paal_fasen = min(self.auto.fasen, self.paal.fasen)
        self.paal_w = self.auto.trekt_amps * VOLT * self.paal_fasen

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
            uit.append(a)
        return uit

    def publiceer(self, hass) -> None:
        """Alle sensoren zetten zoals Home Assistant ze nu zou tonen."""
        nu = self.nu
        z = hass.states.zet
        netto = self.huis_w + self.paal_w - self.zon_w   # + is inkoop
        p1_weg = self.p1_weg_tot is not None and nu < self.p1_weg_tot
        weg = "unavailable"

        def w(waarde, eenheid):
            return {"state": waarde, "attributes": {"unit_of_measurement": eenheid}}

        z(E["zon"], weg if p1_weg else w(f"{self.zon_w:.0f}", "W"))
        z(E["afname"], weg if p1_weg else w(f"{max(0.0, netto):.0f}", "W"))
        z(E["teruglevering"], weg if p1_weg else w(f"{max(0.0, -netto):.0f}", "W"))
        teken = -1 if self.s.net == "signed-omgekeerd" else 1
        z(E["net"], weg if p1_weg else w(f"{teken * netto:.0f}", "W"))
        for naam, a in zip(("l1", "l2", "l3"), self.fase_amps()):
            z(E[naam], weg if p1_weg else w(f"{a:.2f}", "A"))

        z(E["status"], self.paal.status(self.auto))
        z(E["stroom"], w(f"{self.auto.trekt_amps:.2f}", "A"))
        z(E["vermogen"], w(f"{self.paal_w:.0f}", "W"))
        z(E["max"], w(f"{self.paal.max_amps:.0f}", "A"))
        z(E["dyn"], w(f"{self.paal.dyn_limit:.0f}", "A"))
        z(E["teller"], w(f"{self.paal.teller(nu):.3f}", "kWh"))

        soc = self.auto.gemelde_soc(nu)
        z(E["soc"], "unavailable" if soc is None else w(str(soc), "%"))
        if self.s.equalizer:
            z(E["equalizer"], w(f"{self.equalizer_vrij:.1f}", "A"))
            z(E["reden"], self.reden or "none")

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
            self.verloop.opdrachten.append((self.wereld.nu, dienst, dict(data)))
            # De paal meldt zijn nieuwe limiet meteen terug; de coach leest die
            # om te zien of zijn opdracht is aangenomen.
            self.hass.states.zet(E["dyn"], {"state": f"{self.wereld.paal.dyn_limit:.0f}",
                                            "attributes": {"unit_of_measurement": "A"}})
        elif domein == "notify":
            self.verloop.meldingen.append((self.wereld.nu, data.get("message", "")))


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
        capacity_kwh=auto.capaciteit_kwh, phases=auto.fasen, soc_percent=auto.soc))
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
                      soc_percent=auto.soc, max_amps=auto.max_amps)
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

    vorige = (None, None)
    laatste_ronde = None

    class Fasemelding:
        """Wat de luisteraar van de coach van Home Assistant krijgt: één toestand."""

        def __init__(self, entity_id, state):
            self.entity_id = entity_id
            self.state = state

    async def lus():
        nonlocal vorige, laatste_ronde
        while wereld.nu < einde:
            nu = wereld.nu
            while gebeurtenissen and gebeurtenissen[0][0] <= nu:
                _, actie, arg = gebeurtenissen.pop(0)
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
            besluit = coach.state.get("paal") or {}
            prijs, terug = _prijs_nu(coach, inst, nu)
            fasen = wereld.fase_amps()
            netto = wereld.huis_w + wereld.paal_w - wereld.zon_w
            regel = Regel(
                tijd=nu, regel=besluit.get("rule", "?"), amps=int(besluit.get("amps") or 0),
                reden=besluit.get("reason", ""), plan=besluit.get("plan", ""),
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
    """"13:10" op de eerste dag waarop dat nog komt."""
    h, m = map(int, tijd.split(":"))
    moment = begin.replace(hour=h, minute=m, second=0, microsecond=0)
    if moment < begin:
        moment += dt.timedelta(days=1)
    return moment


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
                   and v.soc_bij_klaar_tijd >= min(s.auto.laadgrens, planner.FULL_PERCENT))
        kt = (f"  klaar-tijd {v.klaar_tijd:%a %H:%M}: {'gehaald' if gehaald else 'GEMIST'}"
              f" ({v.soc_bij_klaar_tijd:.0f}%)")
    opt = "" if v.optimum is None else f"  optimum €{v.optimum:.2f}"
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
