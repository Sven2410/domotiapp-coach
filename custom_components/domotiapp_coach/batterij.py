"""Het denkwerk voor een thuisbatterij. Kent Home Assistant niet.

De eigenaar op 21-09-2026: "Ik wil de coach gaan uitbreiden met een
thuisbatterij. Laden, ontladen, blokkeren als de laadpaal laadt. Laden op
goedkope tarieven overdag en in de nacht. Laden op overschot zonne-energie. Hij
moet helemaal samenwerken met de energiecoach." En later die avond: "het doel
is om hem volledig third party te sturen, dus via HA."

Twee lagen, en die scheiding is de kern:

* **De strategie** (`plan_batterij`) kijkt per minuut vooruit over alle uren
  waarvan de prijs bekend is en kiest een stand. Het is dezelfde gedachte als
  `schijven` en `goedkoopste` bij de paal, alle manieren om een kilowattuur te
  gebruiken op één hoop, maar een batterij kan twee kanten op en onthoudt wat
  erin zit, dus hier is het een som over de tijd (`_waarde_vooruit`).
* **De regelaar** (`Regelaar`) voert die stand uit op het tempo van de meter.
  Hij rekent niet met prijzen en weet niets van morgen.

Alles wat hier een getal is komt uit een meting, uit een instelling van de
bewoner of uit een som die daarop rust. Het rendement is daar het belangrijkste
voorbeeld van: zonder gemeten of ingevuld rendement plant de coach niet maar
houdt hij alleen de meter op nul, en dat zegt hij erbij.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import sqrt

from .planner import (
    PRICE_MARGIN,
    SCHIJF_MINIMUM,
    Forecast,
    Tariff,
    _clock,
    _euro,
    _gemiddeld_bekend,
    _kw,
    _kwh,
    _vlakke_blokken,
    in_evening_peak,
    piek_dicht,
    price_now,
)

# --- De standen ---------------------------------------------------------------
# De namen zijn die van de bewoner van de eerste woning, 21-09-2026: "alleen
# zonneladen" en "standby" zijn zijn woorden, en "handelen" ook.
NUL = "nul"                  # nul op de meter: overschot erin, tekort eruit
ZONNELADEN = "zonneladen"    # alleen zonoverschot erin, er komt niets uit
ONTLADEN = "ontladen"        # het huis voeden, maar geen zon opslaan
NETLADEN = "netladen"        # van het net laden, rustig verdeeld
MAX_LADEN = "max-laden"      # negatieve prijs: vol vermogen, ontladen dicht
HANDELEN = "handelen"        # ontladen naar het net
STANDBY = "standby"          # 0 W

STAND_NAMEN = {
    NUL: "Nul op de meter",
    ZONNELADEN: "Alleen zonneladen",
    ONTLADEN: "Alleen ontladen",
    NETLADEN: "Laden van het net",
    MAX_LADEN: "Maximaal laden",
    HANDELEN: "Handelen",
    STANDBY: "Standby",
}

# In hoeveel stappen de inhoud van de batterij verdeeld wordt voor de som over
# de tijd. Geen getal over de batterij maar over de rekenmachine: fijner dan
# veertig verandert in het virtuele huis geen enkel besluit meer, en de som
# draait in een achtergronddraad omdat hij met honderden prijsblokken een
# tiende seconde kost.
STAPPEN = 40

# Wat het kost om de wekelijkse volle beurt te missen, per kilowattuur die
# ontbreekt. Geen prijs maar een gewicht: zo hoog dat de som elke haalbare
# manier om vol te komen verkiest boven niet vol komen, en dan vanzelf de
# goedkoopste uren daarvoor pakt.
VOL_GEWICHT = 10.0

# Na hoeveel dagen zonder volle batterij de wekelijkse beurt aan de orde is. Zes
# en niet zeven: de beurt van vorige week eindigde ergens op die dag, en met
# zeven dagen zou hij deze week pas op datzelfde uur weer mogen beginnen.
VOL_NA = timedelta(days=6)

# Wanneer de batterij als vol telt voor die beurt: binnen zoveel procentpunt
# van zijn eigen laadgrens. Een accusensor is nooit fijner dan een procent; zie
# `DOEL_MARGE` in planner.py.
VOL_MARGE = 1.0
# Hoeveel procent boven `auto_grens` de batterij moet zitten om opnieuw te
# beginnen met de auto helpen; stoppen doet hij op de grens zelf. De grens zakt
# 's nachts vanzelf (er is minder nacht over), en met een procent speling hielp
# hij in het virtuele huis zeventien keer een paar minuten (34 wissels).
AUTO_MARGE = 5.0


@dataclass
class Batterij:
    """Een thuisbatterij zoals de coach hem deze ronde ziet.

    Wat None mag zijn is "niet bekend" en niet nul.
    """

    # De accustand in procent.
    soc: float | None = None
    # De bruikbare inhoud bij honderd procent, in kWh.
    capacity_kwh: float | None = None
    # Wat hij aan de wisselstroomkant kan, in watt.
    max_charge_w: float = 0.0
    max_discharge_w: float = 0.0
    # De grenzen van de batterij zelf, in procent. De coach leest ze en schrijft
    # ze nooit: de eigenaar op 21-09-2026 over de laadgrens van 95%, "dit is een
    # waarde waar niet aan gekomen moet worden."
    soc_min: float = 0.0
    soc_max: float = 100.0
    # De reserve voor noodstroom van de bewoner, in procent, of None voor geen.
    reserve: float | None = None
    # Het rendement heen en terug aan de wisselstroomkant, 0 tot 1. Gemeten met
    # een kWh-meter op de batterij, of door de bewoner ingevuld. None is "weet
    # hij niet", en dan wordt er niet gepland.
    rte: float | None = None
    # Of ontladen naar het net mag. Standaard uit.
    handelen: bool = False
    # Boven welke accustand de batterij de auto mag helpen als de paal laadt,
    # in procent, of None: dan geeft hij de auto niets (v0.90.0). Zie `auto_grens`.
    auto_boven: float | None = None
    # De nachtstrategie (Strategie, standaard aan): de batterij houdt genoeg
    # over om de nacht door te komen. Uit, dan mag hij voor de auto en voor
    # handelen leeg tot zijn eigen ondergrens (v0.90.0).
    nacht: bool = True
    # Wat hij nu doet, in watt aan de wisselstroomkant, laden positief.
    power_w: float | None = None
    # Vóór wanneer de batterij een keer helemaal vol hoort te zijn, of None.
    # Zie `vol_voor`.
    vol_voor: datetime | None = None
    # De batterij doet zelf nul op de meter (v0.97.0), en de coach grijpt alleen
    # in om van het net te laden, te handelen of als de paal laadt (v0.101.9).
    # De eigenaar op 29-09-2026: "de coach moet de batterij niet zelf sturen ...
    # alleen goedkoop inkopen en de anker stoppen als de laadpaal aan gaat."
    # Stilstaan, alleen zon opslaan en alleen ontladen zijn er dan niet; zie
    # `_zelf_toegestaan`.
    zelf_nul: bool = False
    # Of de coach hem nu zelf in de externe stand heeft. Zonder `zelf_nul`
    # altijd zodra hij stuurt; met alleen als hij hem overnam. Voor een kleine
    # laadbeurt neemt hij hem niet over; zie `_rustig_vermogen`.
    overgenomen: bool = False
    # De stand van de vorige ronde, en wanneer die was. Een laadbeurt van het
    # net die al loopt maakt hij af; zie `_rustig_vermogen` en `_loopt_al`.
    vorige_stand: str | None = None
    vorige_op: datetime | None = None

    @property
    def bodem(self) -> float:
        """Onder welke accustand er niets uit mag, in procent."""
        return max(self.soc_min, self.reserve or 0.0)

    @property
    def inhoud_kwh(self) -> float | None:
        if self.soc is None or self.capacity_kwh is None:
            return None
        return self.soc / 100.0 * self.capacity_kwh


@dataclass
class Uur:
    """Eén blok van het plan, voor de kaart."""

    start: datetime
    end: datetime
    stand: str
    # Wat de batterij in dit blok doet, in kWh aan de wisselstroomkant: laden
    # positief, ontladen negatief.
    kwh: float
    # Hoeveel daarvan van het net komt (laden) of naar het net gaat (handelen).
    net_kwh: float
    # De verwachte accustand aan het eind, in procent.
    soc: float
    price: float
    # Wat daarvan naar de auto gaat, in kWh aan de wisselstroomkant, positief
    # (v0.95.0). Zit al in `kwh`. Zie `auto_hulp`.
    auto_kwh: float = 0.0


@dataclass
class Besluit:
    """Welke stand de regelaar moet uitvoeren, en wat de bewoner leest."""

    stand: str
    # Het vermogen bij NETLADEN en HANDELEN, in watt. Bij NETLADEN een
    # ondergrens: is er meer zon dan dat, dan gaat die erin.
    power_w: float = 0.0
    reason: str = ""
    plan: str = ""
    rule: str = ""
    # Wat een kilowattuur in de batterij straks waard is, in euro. Voor het log
    # en voor de kaart.
    waarde: float | None = None
    uren: list[Uur] = field(default_factory=list)
    # Wat er volgens het plan van de paal naar de auto gaat, aan de accukant in
    # kWh (v0.95.0). Voor de nachtbalans op de kaart; zie `auto_hulp`.
    auto_weg: float = 0.0
    # Onder welke prijs een kWh van het net erbij nu loont, in euro: wat hij in
    # de batterij straks waard is, min het verlies bij het laden (v0.102.3).
    # None als de batterij vol is of er niet gerekend is.
    inkoop_tot: float | None = None
    # Of de batterij de auto in dit blok helpt volgens het plan (v0.104.1): True,
    # False als de paal nu volgens zijn plan laadt maar de hulp naar een duurder
    # laaduur gaat, en None als de paal nu buiten zijn plan laadt (Snel, of een
    # andere sturing); dan helpt hij zoals altijd boven de grens. En wanneer het
    # eerstvolgende blok met hulp begint, voor de kaart.
    auto_hulp_nu: bool | None = None
    auto_hulp_om: datetime | None = None

    @property
    def grenzen(self) -> tuple[bool, bool]:
        """Of de regelaar in deze stand mag laden en mag ontladen."""
        return (
            self.stand in (NUL, ZONNELADEN, NETLADEN, MAX_LADEN),
            self.stand in (NUL, ONTLADEN, HANDELEN),
        )


def vol_voor(
    now: datetime, aan: bool, dag: int | None, laatst_vol: datetime | None
) -> datetime | None:
    """Vóór wanneer de batterij helemaal vol hoort te zijn, of None.

    De bewoner van de eerste woning op 21-09-2026: "bouw een 1x per week 100%
    modus in voor accu cel balancering." Op de dag die hij kiest, en alleen als
    de batterij de afgelopen week niet al vol was: in de zomer is hij dat elke
    middag, en dan is er niets te doen. "Vol" is de laadgrens van de batterij
    zelf.
    """
    if not aan or dag is None:
        return None
    if laatst_vol is not None and now - laatst_vol < VOL_NA:
        return None
    if now.weekday() != dag:
        return None
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def _netto_huis_kwh(forecast: Forecast, rij: dict, deel: float) -> float:
    """Wat het huis in dit blok van het net vraagt als er geen batterij was.

    Negatief is overschot. Het huisverbruik min de zon, de zon bijgesteld met
    wat het dak vandaag waarmaakte; zie `overschot_kwh` in planner.py, dat
    dezelfde som maakt maar bij nul afkapt omdat een paal niets met een tekort
    kan.
    """
    uur = rij["start"].replace(minute=0, second=0, microsecond=0)
    zon = max(0.0, forecast.solar_kwh.get(uur, 0.0))
    if forecast.solar_factor is not None and uur.date() == forecast.solar_day:
        zon *= forecast.solar_factor
    return (forecast.house_kwh.get(uur.hour, 0.0) - zon) * deel


def _kosten(net_kwh: float, rij: dict) -> float:
    """Wat een blok kost met zoveel kWh van het net (negatief: ernaartoe)."""
    if net_kwh >= 0:
        return net_kwh * rij["price"]
    return net_kwh * (rij.get("feed_in") or 0.0)


def _tussen(rij_v: list[float], stap: float, laag: float, e: float) -> float:
    """De waarde bij inhoud `e`, recht getrokken tussen twee roosterpunten."""
    plek = (e - laag) / stap if stap else 0.0
    plek = min(max(plek, 0.0), len(rij_v) - 1.0)
    i = int(plek)
    if i >= len(rij_v) - 1:
        return rij_v[-1]
    rest = plek - i
    return rij_v[i] * (1.0 - rest) + rij_v[i + 1] * rest


@dataclass
class _Som:
    """De uitkomst van de som over de tijd, om mee verder te rekenen."""

    blokken: list[dict]
    delen: list[float]
    huis: list[float]
    # `na[k]` is wat de rest van de tijd nog kost vanaf het einde van blok k,
    # per roosterpunt van de inhoud.
    na: list[list[float]]
    laag: float
    hoog: float
    stap: float
    eta: float
    # Of de avondpiek dicht is voor het net (vast contract). Zie `piek_dicht`.
    piek: bool = True


def _mag_handelen(b: Batterij, rij: dict) -> bool:
    """Of de batterij in dit blok aan het net mag leveren.

    Alleen met handelen aan en een terugleverprijs die bekend is (v0.106.2).
    Zonder die prijs telt teruglevering in `_kosten` als nul, en dan is aan het
    net leveren nooit winst maar hooguit gelijkspel. In de eerste woning op
    03-10-2026 won dat gelijkspel: de marktsensor was daar de all-in sensor, de
    dag had meer zon dan er in de batterij paste, en met zelf nul (stilstaan mag
    niet) was één stap naar het net een kleiner gebaar dan de ochtendzon opslaan.
    Van 09:00 tot 12:00 ging er 4,57 kWh zon naar het net, de batterij bleef op
    21% en gaf er 0,48 kWh bij, "Terugleveren brengt nu € 0,000 op". Om 12:16
    kwam de auto en die ging voor, dus die zon kwam er die dag niet meer in.
    """
    return b.handelen and rij.get("feed_in") is not None


def _mogelijk(
    e: float, rij: dict, deel: float, huis: float, b: Batterij, som_laag: float,
    hoog: float, eta: float, piek: bool = True,
) -> tuple[float, float]:
    """Tussen welke inhoud de batterij aan het eind van dit blok kan zitten."""
    op = min(hoog, e + b.max_charge_w / 1000.0 * deel * eta)
    if piek and in_evening_peak(rij["start"]):
        # Eis 4: in de avondpiek komt er niets van het net bij. Zon mag.
        op = min(op, e + max(0.0, -huis) * eta)
    neer_w = b.max_discharge_w / 1000.0 * deel
    if not _mag_handelen(b, rij):
        # Zonder handelen gaat er niets naar het net: hooguit wat het huis vraagt.
        neer_w = min(neer_w, max(0.0, huis))
    neer = max(min(som_laag, e), e - neer_w / eta)
    return max(op, e), min(neer, e)


def _zelf_toegestaan(
    kandidaten: set[float], e: float, deel: float, huis: float, b: Batterij,
    som_laag: float, hoog: float, eta: float, stap: float = 0.0, handelen: bool | None = None,
) -> set[float]:
    """Wat er van de kandidaten overblijft als de batterij zelf nul op de meter doet.

    Zijn eigen stand is precies het huis voeden of precies het overschot
    opslaan, zover hij kan. Daarboven is van het net laden, en dat doet de coach;
    daaronder is handelen, alleen als dat aanstaat. Wat ertussen ligt (stilstaan,
    of maar een deel) kan de batterij in zijn eigen stand niet.

    En van het net laden of handelen is minstens één stap van het rooster
    (`stap`), of zoveel als de tijd in dit blok nog toelaat (v0.102.3). Anders
    koos de som voor stilstaan, dat hij hier niet mag, het eerstvolgende
    roosterpunt erboven: in de klantwoning op 30-09-2026 om 21:45 "laden van
    het net, 0,01 kWh" midden in een avond ontladen. Dat is geen inkoop maar
    een overname om stil te staan, en die hoort hier niet.

    De tijd en niet de grens van de batterij (v0.103.0). Tot dan telde ook de
    95% als "wat er nog kan", en dan vulde hij een batterij die 's nachts op
    94% stond met 0,14 tot 0,20 kWh bij: nagerekend over 1.320 plannen van de
    eerste woning op 30-09-2026, tien keer, allemaal op 94 of 95%. Het restje
    van een kwartier dat bijna om is blijft wel mogen, anders stopte een beurt
    elk kwartier 2:20 te vroeg (proef 37 in test_batterij.py).

    `handelen` is of dit blok aan het net mag leveren (`_mag_handelen`);
    zonder is het de instelling van de batterij.
    """
    if not b.zelf_nul:
        return kandidaten
    if handelen is None:
        handelen = b.handelen
    if huis > 0:
        nul = max(min(som_laag, e), e - min(b.max_discharge_w / 1000.0 * deel, huis) / eta)
    elif huis < 0:
        nul = min(max(hoog, e), e + min(b.max_charge_w / 1000.0 * deel, -huis) * eta)
    else:
        nul = e
    uit = {nul}
    boven, onder = max(e, nul), min(e, nul)
    # Wat het blok in tijd en vermogen toelaat, zonder de grenzen van de accustand.
    op_blok = e + b.max_charge_w / 1000.0 * deel * eta
    neer_blok = e - b.max_discharge_w / 1000.0 * deel / eta
    erop = boven + min(stap, max(0.0, op_blok - boven)) - 1e-9
    eraf = onder - min(stap, max(0.0, onder - neer_blok)) + 1e-9
    for k in kandidaten:
        if (k > boven + 1e-9 and k >= erop) or (handelen and k < onder - 1e-9 and k <= eraf):
            uit.add(k)
    return uit


def _loopt_al(b: Batterij, rij: dict) -> bool:
    """Of de coach in dit blok al van het net laadt of eraan levert (v0.102.3).

    Dan mag de som het blok afmaken met minder dan een stap van het rooster
    (`_zelf_toegestaan`): de accustand loopt in procenten op, een procent is
    bij 14,5 kWh 0,145 kWh en een stap 0,33, en elke tik liet het restje van
    het blok onder die stap zakken. In het virtuele huis stopte hij daardoor
    om 05:47:40 twee minuten na het begin van een kwartier. Alleen in het blok
    zelf: in het volgende moet een beurt weer een stap zijn, anders kan hij de
    batterij blok na blok met een beetje laden vasthouden.
    """
    return (
        b.vorige_stand in (NETLADEN, HANDELEN) and b.vorige_op is not None
        and rij["start"] <= b.vorige_op < rij["end"]
    )


def _blok_kosten(e: float, naar: float, huis: float, rij: dict, eta: float) -> float:
    """Wat dit blok kost als de inhoud van `e` naar `naar` gaat."""
    if naar >= e:
        ac = (naar - e) / eta
    else:
        ac = -(e - naar) * eta
    return _kosten(huis + ac, rij)


def _waarde_vooruit(
    now: datetime, blokken: list[dict], forecast: Forecast, b: Batterij, piek: bool = True
) -> _Som | None:
    """De som over de tijd: wat de rest van de bekende uren kost, per inhoud.

    Van achter naar voren. Aan het eind is wat er nog in zit waard wat een
    gemiddeld bekend uur kost (`_gemiddeld_bekend`, dezelfde maat als bij de
    paal), maal wat er bij het ontladen van overblijft: verder dan de prijzen
    reiken weet de coach niets, en het gemiddelde van wat hij wél weet is het
    enige getal dat geen gok is.

    Per blok en per inhoud worden alle manieren geprobeerd om het blok door te
    komen: niets doen, precies het huis voeden, precies het overschot opslaan,
    en elk roosterpunt dat binnen het vermogen ligt. De kosten zijn recht tussen
    die punten, dus het beste zit altijd op een ervan.
    """
    if b.rte is None or b.capacity_kwh is None or b.soc is None or not blokken:
        return None
    eta = sqrt(min(max(b.rte, 0.05), 1.0))
    inhoud = b.soc / 100.0 * b.capacity_kwh
    hoog = max(b.soc_max / 100.0 * b.capacity_kwh, inhoud)
    bodem = b.bodem / 100.0 * b.capacity_kwh
    laag = min(bodem, inhoud)
    if hoog - laag < 1e-6:
        return None
    stap = (hoog - laag) / STAPPEN
    rooster = [laag + i * stap for i in range(STAPPEN + 1)]

    delen, huis = [], []
    for rij in blokken:
        van = max(rij["start"], now)
        deel = max(0.0, (rij["end"] - van).total_seconds() / 3600.0)
        delen.append(deel)
        huis.append(_netto_huis_kwh(forecast, rij, deel))

    eind_prijs = _gemiddeld_bekend(blokken) or 0.0
    volgende = [-(max(0.0, e - bodem)) * eta * eind_prijs for e in rooster]

    # `na[k]` is wat de rest nog kost vanaf het einde van blok k.
    na: list[list[float]] = [[] for _ in blokken]
    for k in range(len(blokken) - 1, -1, -1):
        rij, deel, h = blokken[k], delen[k], huis[k]
        if b.vol_voor is not None and rij["start"] < b.vol_voor <= rij["end"]:
            # De wekelijkse volle beurt: wie hier niet vol is betaalt.
            volgende = [v + VOL_GEWICHT * max(0.0, hoog - e) for v, e in zip(volgende, rooster)]
        na[k] = volgende
        begin = []
        for e in rooster:
            op, neer = _mogelijk(e, rij, deel, h, b, bodem, hoog, eta, piek)
            kandidaten = {e, op, neer}
            if h > 0:
                kandidaten.add(max(neer, e - h / eta))
            elif h < 0:
                kandidaten.add(min(op, e + (-h) * eta))
            eerste = int((neer - laag) / stap) + 1
            laatste = int((op - laag) / stap)
            for i in range(max(0, eerste), min(STAPPEN, laatste) + 1):
                kandidaten.add(rooster[i])
            kandidaten = _zelf_toegestaan(
                kandidaten, e, deel, h, b, bodem, hoog, eta, 0.0 if k == 0 and _loopt_al(b, rij) else stap,
                handelen=_mag_handelen(b, rij),
            )
            begin.append(
                min(
                    _blok_kosten(e, naar, h, rij, eta) + _tussen(volgende, stap, laag, naar)
                    for naar in kandidaten
                )
            )
        volgende = begin

    return _Som(blokken, delen, huis, na, laag, hoog, stap, eta, piek)


def _beste_stap(som: _Som, k: int, e: float, b: Batterij) -> float:
    """Naar welke inhoud de batterij in blok k het beste kan gaan."""
    rij, deel, h = som.blokken[k], som.delen[k], som.huis[k]
    bodem = b.bodem / 100.0 * (b.capacity_kwh or 0.0)
    op, neer = _mogelijk(e, rij, deel, h, b, bodem, som.hoog, som.eta, som.piek)
    kandidaten = {e, op, neer}
    if h > 0:
        kandidaten.add(max(neer, e - h / som.eta))
    elif h < 0:
        kandidaten.add(min(op, e + (-h) * som.eta))
    i = int((neer - som.laag) / som.stap) + 1
    while i <= STAPPEN and som.laag + i * som.stap <= op:
        kandidaten.add(som.laag + i * som.stap)
        i += 1
    kandidaten = _zelf_toegestaan(
        kandidaten, e, deel, h, b, bodem, som.hoog, som.eta, 0.0 if k == 0 and _loopt_al(b, rij) else som.stap,
        handelen=_mag_handelen(b, rij),
    )
    # Bij gelijke kosten wint niets doen, en daarna het kleinste gebaar: een
    # batterij die zonder reden beweegt slijt voor niets.
    return min(
        kandidaten,
        key=lambda naar: (
            round(
                _blok_kosten(e, naar, h, rij, som.eta)
                + _tussen(som.na[k], som.stap, som.laag, naar),
                6,
            ),
            abs(naar - e),
        ),
    )


def _stand_van(ac: float, huis: float) -> str:
    """Welke stand bij een blok hoort, uit wat de batterij erin doet."""
    klein = 0.005
    if ac > max(0.0, -huis) + klein:
        return NETLADEN
    if ac < -max(0.0, huis) - klein:
        return HANDELEN
    if abs(ac) > klein:
        return NUL
    return STANDBY


def _vooruit(som: _Som, b: Batterij) -> list[Uur]:
    """Het plan zoals het nu uitpakt, blok voor blok, voor de kaart."""
    e = (b.soc or 0.0) / 100.0 * (b.capacity_kwh or 0.0)
    uit: list[Uur] = []
    for k, rij in enumerate(som.blokken):
        if som.delen[k] <= 0:
            continue
        naar = _beste_stap(som, k, e, b)
        ac = (naar - e) / som.eta if naar >= e else -(e - naar) * som.eta
        h = som.huis[k]
        net = max(0.0, ac - max(0.0, -h)) if ac > 0 else min(0.0, ac + max(0.0, h))
        uit.append(
            Uur(
                max(rij["start"], rij["end"] - timedelta(hours=som.delen[k])),
                rij["end"],
                _stand_van(ac, h),
                ac,
                net,
                naar / (b.capacity_kwh or 1.0) * 100.0,
                rij["price"],
            )
        )
        e = naar
    return uit


def _houden_tot(b: Batterij, som: _Som) -> datetime | None:
    """Het eind van het blok waarin al van het net geladen wordt, of None.

    Een accustand in hele procenten loopt soms een tik voor op het plan, en dan
    wil het plan in de rest van het blok niets meer van het net. Tot v0.108.0
    viel het besluit dan naar nul op de meter, en een batterij die dat zelf
    doet dekte het huis uit wat hij net gekocht had. In de klantwoning in de
    nacht van 05 op 06-10-2026: 7,68 kWh erin en 2,36 kWh eruit tussen 22:45 en
    05:30, in gaten van een paar minuten tot een half uur tussen de kwartieren
    door; op 10-10-2026 tussen 15:46 en 16:00 tikte de stand elke minuut tussen
    83 en 84%, met vier moduswissels. Het besluit om dit blok te laden is aan
    het begin van het blok genomen, dus hij houdt de batterij vast tot het blok
    om is: niets eruit, zon er nog wel in.
    """
    if b.vorige_stand != NETLADEN:
        return None
    for k, rij in enumerate(som.blokken):
        if som.delen[k] > 0:
            return rij["end"] if _loopt_al(b, rij) else None
    return None


# Vasthouden is laden van het net op niets: de regelaar haalt dan niets uit de
# batterij, en het telt overal als een lopende netlading. Eén watt en geen nul,
# want nul betekent bij een netlading "het volle vermogen" (`doel_w` in coach.py).
HOUD_W = 1.0


def _rustig_vermogen(
    uren: list[Uur], b: Batterij, ontladen: bool = False, piek: bool = True, drempel: float = 0.0,
    houden_tot: datetime | None = None,
) -> tuple[float, datetime | None]:
    """Op welk vermogen hij van het net laadt (of eraan levert), en tot wanneer.

    De bewoner van de eerste woning op 21-09-2026: "als we 5u lang een
    energieprijs van 13 cent hebben, heb ik liever dat ie 5u lang laadt op 50%
    capaciteit, dan 2,5u op 100%. Hoger rendement, lagere temp, lagere
    slijtage." Dezelfde gedachte als `rustig_tempo` bij de paal: bij gelijke
    prijzen valt er met haasten niets te winnen. De som over de tijd is daar
    onverschillig en schuift alles naar het laatste uur; hier wordt wat hij in
    de aaneengesloten even dure uren van het net wil halen over al die uren
    uitgesmeerd.

    Dit is ook het antwoord op de vraag óf hij nu van het net laadt: wil het
    plan dat in deze even dure uren, dan ja. Een vergelijking met wat een
    kilowattuur straks waard is staat in het randuur precies op gelijkspel, en
    viel in het virtuele huis elke minuut anders (22-09-2026, zeven wissels
    tussen 11:07 en 11:23).

    Alleen over uren die even duur zijn. Waar de omvormer het zuinigst is wordt
    niet aangenomen; een iets duurder uur erbij nemen om rustiger te laden is
    pas een som als dat rendement per vermogen gemeten is.

    Of hij begint gaat over de hele laadbeurt, en niet over wat er in dit blok
    nog bij moet (v0.102.3). In de klantwoning op 30-09-2026, met prijzen per
    kwartier: 3,5 kW maal de laatste 2 minuten en 20 seconden van een kwartier
    is 0,136 kWh, minder dan de procent hieronder, dus laadde hij elk kwartier
    twaalf minuten en drie niet. En 's nachts, toen de accustand een procent
    sneller opliep dan het plan dacht, zei hij midden in het laden van het net
    "nul op de meter"; hij had de batterij in handen, en dekte de warmtepomp er
    toen uit. Van 03:25 tot 06:00 laden en ontladen door elkaar, en met een
    `ZELF_WACHT` van twee minuten was het elk kwartier teruggeven en weer
    overnemen geworden. Een beurt die al loopt (`vorige_stand`) maakt hij
    daarom af zolang het plan in dit blok nog iets van het net wil, hoe weinig
    ook: dan houdt hij de batterij vast en neemt het huis van het net.

    `drempel` is wat een beurt minstens moet zijn om te beginnen, in kWh aan
    de wisselstroomkant, bovenop de procent; zie de aanroep in `plan_batterij`.
    """
    if not uren:
        return 0.0, None

    def naar_net(uur: Uur) -> float:
        return max(0.0, -uur.net_kwh if ontladen else uur.net_kwh)

    def dicht(uur: Uur) -> bool:
        return piek and not ontladen and in_evening_peak(uur.start)

    prijs = uren[0].price
    energie, tijd, tot, n = 0.0, 0.0, None, 0
    for uur in uren:
        if abs(uur.price - prijs) > PRICE_MARGIN or dicht(uur):
            break
        energie += naar_net(uur)
        tijd += (uur.end - uur.start).total_seconds() / 3600.0
        tot = uur.end
        n += 1
    if tijd <= 0 or energie <= 1e-6:
        if houden_tot is not None and not ontladen:
            return HOUD_W, houden_tot
        return 0.0, tot
    if b.vorige_stand != (HANDELEN if ontladen else NETLADEN):
        # Minder dan een procent van de batterij is geen plan maar afronding: een
        # accusensor is niet fijner dan dat, en in het virtuele huis ging hij er
        # twee minuten voor van het net laden en hield er dan weer mee op. Dat
        # gaat over de hele beurt: deze even dure blokken, en de blokken daarna
        # waarin het plan ook van het net laadt (of eraan levert), wat ze ook
        # kosten.
        beurt = energie
        for uur in uren[n:]:
            if dicht(uur) or naar_net(uur) <= 1e-6:
                break
            beurt += naar_net(uur)
        if beurt <= max(SCHIJF_MINIMUM, 0.01 * (b.capacity_kwh or 0.0), drempel):
            return 0.0, tot
    grens = b.max_discharge_w if ontladen else b.max_charge_w
    return min(grens, energie / tijd * 1000.0), tot


# Tot hoe laat "de nacht overbruggen" loopt: morgenvroeg. De bewoner van de
# eerste woning op 22-09-2026: "de meeste consumenten hebben een accu om de
# nacht te overbruggen. 'Tot middernacht' klinkt logisch, maar bij doel
# overbruggen van de nacht zou het logischer zijn om te zeggen 'tot
# morgenvroeg'." Zeven uur: dan geeft een dak in de zomer al iets en in de
# winter nog niets, en dat verschil zit in de zonverwachting zelf.
OCHTEND_UUR = 7


def _morgenvroeg(now: datetime) -> datetime:
    """Het eerstvolgende `OCHTEND_UUR`."""
    eind = now.replace(hour=OCHTEND_UUR, minute=0, second=0, microsecond=0)
    return eind + timedelta(days=1) if eind <= now else eind


def _nacht_uren(now: datetime, forecast: Forecast) -> list[tuple[float, float]]:
    """Per uur tot morgenvroeg: (zon, huis) in kWh, het lopende uur naar rato."""
    uren = []
    uur = now.replace(minute=0, second=0, microsecond=0)
    eind = _morgenvroeg(now)
    while uur < eind:
        deel = 1.0 if uur >= now else (uur + timedelta(hours=1) - now).total_seconds() / 3600.0
        opbrengst = max(0.0, forecast.solar_kwh.get(uur, 0.0))
        if forecast.solar_factor is not None and uur.date() == forecast.solar_day:
            opbrengst *= forecast.solar_factor
        uren.append((opbrengst * deel, forecast.house_kwh.get(uur.hour, 0.0) * deel))
        uur += timedelta(hours=1)
    return uren


def nachtbalans(now: datetime, forecast: Forecast, b: Batterij) -> tuple[float, float, float] | None:
    """Zon, huis en wat er bruikbaar in de batterij zit, tot morgenvroeg, in kWh.

    None als er geen huisprofiel of geen accustand is. De zon van de uren die
    komen wordt bijgesteld met wat het dak vandaag waarmaakte, net als overal.
    """
    if not forecast.house_kwh or b.inhoud_kwh is None:
        return None
    uren = _nacht_uren(now, forecast)
    zon = sum(z for z, _ in uren)
    huis = sum(h for _, h in uren)
    bruikbaar = max(0.0, b.inhoud_kwh - b.bodem / 100.0 * (b.capacity_kwh or 0.0))
    return zon, huis, bruikbaar


def nachtverloop(
    now: datetime, forecast: Forecast, b: Batterij, weg: float = 0.0
) -> tuple[float, float, float] | None:
    """Uur voor uur tot morgenvroeg: (inhoud morgenvroeg, tekort, zon die er niet in past).

    De bewoner van de eerste woning op 23-09-2026, bij "je houdt naar
    verwachting 15,9 kWh over in je accu" onder een accu van 14,6 kWh: "hoe kan
    je ooit 16 kWh in een accu hebben van 14 kWh?" De som telde alle zon tot
    morgenvroeg bij wat erin zat, en een accu is geen emmer zonder rand. Nu per
    uur: overschot gaat erin tot de laadgrens (`soc_max`) en de rest naar het
    net; wat het huis vraagt komt eruit met het rendement, tot de ondergrens;
    en wat er dan nog ontbreekt is tekort, dat van het net komt en niet meer
    terugkomt als 's ochtends de zon opkomt. Zonder gemeten rendement telt
    wat erin zit voor de volle inhoud, want een gok is geen meting.

    De inhoud is aan de accukant en boven de ondergrens, in kWh. `weg` is wat
    de auto er volgens het plan van de paal uit haalt, ook aan de accukant
    (v0.95.0): dat gaat er aan het begin af, want de batterij helpt zodra de
    paal laadt.
    """
    som = nachtbalans(now, forecast, b)
    if som is None:
        return None
    _zon, _huis, inhoud = som
    inhoud = max(0.0, inhoud - max(0.0, weg))
    cap = b.capacity_kwh or 0.0
    ruimte = max(0.0, (b.soc_max - b.bodem) / 100.0 * cap)
    inhoud = min(inhoud, ruimte) if ruimte else inhoud
    eta = b.rte if b.rte else 1.0
    tekort = weg = 0.0
    for zon, huis in _nacht_uren(now, forecast):
        netto = zon - huis
        if netto >= 0:
            erbij = min(netto, max(0.0, ruimte - inhoud))
            inhoud += erbij
            weg += netto - erbij
        else:
            nodig = -netto
            kan = inhoud * eta
            if kan >= nodig:
                inhoud -= nodig / eta
            else:
                tekort += nodig - kan
                inhoud = 0.0
    return inhoud, tekort, weg


def balans_kwh(now: datetime, forecast: Forecast, b: Batterij, weg: float = 0.0) -> float | None:
    """Wat er morgenvroeg naar verwachting over is (positief) of tekortkomt.

    Over is wat er dan nog uit de accu kan komen, na het verlies; nooit meer
    dan de accu kan bevatten. Tekort is wat er in de nacht van het net moet.
    Zie `nachtverloop`.
    """
    verloop = nachtverloop(now, forecast, b, weg)
    if verloop is None:
        return None
    inhoud, tekort, _weg = verloop
    if tekort > 0.05:
        return -tekort
    return inhoud * (b.rte if b.rte else 1.0)


def _vlak(blokken: list[dict]) -> bool:
    """Of stroom in alle bekende blokken evenveel kost.

    Dan levert van het net laden nooit iets op: elke kWh kost overal hetzelfde,
    en de batterij verliest er een deel van. Zo is het bij een vast contract
    zonder dal- en piektarief. De eigenaar op 29-09-2026, bij "het rendement van
    de batterij is nog niet bekend, dus van het net laden doet hij nog niet":
    "waarom zegt de coach dit terwijl ik een vast contract heb? Inkopen is niet
    rendabel en heeft alleen maar verlies."
    """
    prijzen = [rij["price"] for rij in blokken if rij.get("price") is not None]
    return bool(prijzen) and max(prijzen) - min(prijzen) <= PRICE_MARGIN


def _vooruitkijk_zin(
    now: datetime, forecast: Forecast, b: Batterij, auto: float = 0.0, bijladen: bool = True,
    uren: list[Uur] | None = None,
) -> str:
    """Twee zinnen: zon, huis en batterij tot morgenvroeg, en de conclusie.

    De bewoner van de eerste woning liet op 21-09-2026 zien wat hij van zijn
    oude sturing het meest miste als het weg zou zijn: een regel die zegt
    waaróm er wel of niet bijgeladen wordt. "Wat is mijn verwacht verbruik
    vandaag? Wat is de verwachte zonopbrengst?" En op 22-09-2026: "Als laatste
    afsluiten met een conclusie: je hebt naar verwachting X kWh overschot in je
    accu, of je hebt X kWh tekort om de nacht te overbruggen."
    """
    som = nachtbalans(now, forecast, b)
    eta = sqrt(min(max(b.rte, 0.05), 1.0)) if b.rte else 1.0
    # `auto` is aan de wisselstroomkant, zoals de bewoner hem in de auto ziet
    # gaan; de nachtbalans rekent aan de accukant.
    verloop = nachtverloop(now, forecast, b, auto / eta)
    if som is None or verloop is None:
        return ""
    zon, huis, bruikbaar = som
    _inhoud, _tekort, weg = verloop
    balans = balans_kwh(now, forecast, b, auto / eta) or 0.0
    # Wat erin zit komt er niet helemaal uit; de conclusie rekent met het
    # rendement, dus de zin zegt erbij waar hij mee rekent.
    eruit = f", goed voor {_kwh(bruikbaar * b.rte)} na het verlies" if b.rte and bruikbaar > 0 else ""
    # En zon die er niet meer in past gaat naar het net: dat verklaart waarom
    # de optelsom van zon en batterij meer is dan wat er morgenvroeg over is.
    past_niet = f" Van die zon past {_kwh(weg)} niet meer in de accu; die gaat naar het net." if weg > 0.05 else ""
    naar_auto = f", de auto krijgt er {_kwh(auto)} uit" if auto > 0.05 else ""
    zin = (
        f"Tot morgenvroeg verwacht hij {_kwh(zon)} zon, het huis vraagt {_kwh(huis)}{naar_auto} "
        f"en er zit {_kwh(bruikbaar)} in de batterij{eruit}.{past_niet} "
    )
    if balans >= 0:
        return zin + f"Je houdt naar verwachting {_kwh(balans)} over in je accu."
    return (
        zin + f"Je komt naar verwachting {_kwh(-balans)} tekort om de nacht te overbruggen; "
        + (_bijladen_zin(now, b, uren or [], -balans) if bijladen else "dat komt van het net.")
    )


def _bijladen_zin(now: datetime, b: Batterij, uren: list[Uur], tekort: float) -> str:
    """Het slot van de nachtzin bij een tekort: laadt hij bij, en zo niet, waarom niet.

    Tot v0.102.3 stond hier altijd "hij laadt bij als de stroom goedkoop genoeg
    is". De eigenaar op 30-09-2026 om 19:45, bij 8,1 kWh tekort en "Van het net:
    niets": "hij komt te kort, is het niet goedkoper om iets bij te kopen?"
    Het antwoord stond nergens. Nu zegt de zin wat het plan tot morgenvroeg van
    het net haalt, of wat een kWh via de batterij minstens kost: de goedkoopste
    prijs tot morgenvroeg gedeeld door het rendement. Eén zin, want de kaart
    toont alleen de laatste (`nachtConclusie` in battery.js).
    """
    eind = _morgenvroeg(now)
    nacht = [u for u in uren if u.start < eind]
    erbij = sum(max(0.0, u.net_kwh) for u in nacht if u.stand == NETLADEN)
    if erbij > 0.05:
        if erbij >= tekort - 0.05:
            return "dat laadt hij op de goedkoopste momenten van het net bij."
        return (
            f"hij laadt er {_kwh(erbij)} van op de goedkoopste momenten van het net bij, "
            "de rest komt rechtstreeks van het net."
        )
    if not nacht or not b.rte:
        return "hij laadt bij als de stroom goedkoop genoeg is."
    goedkoopst = min(nacht, key=lambda u: u.price)
    bekend = "" if nacht[-1].end >= eind else " in de bekende uren"
    return (
        f"dat komt van het net, want bijladen kost via de batterij{bekend} minstens "
        f"{_euro(goedkoopst.price / b.rte)} per kWh ({_euro(goedkoopst.price)} om "
        f"{_clock(goedkoopst.start)}, plus het verlies)."
    )


def plan_batterij(
    now: datetime,
    prices: list[dict],
    tariff: Tariff,
    forecast: Forecast,
    b: Batterij,
    *,
    enabled: bool = True,
    paal_laadt: bool = False,
    helpt: bool = False,
    auto_laden: list[tuple[datetime, datetime, float]] | None = None,
) -> Besluit:
    """Welke stand de batterij nu hoort te hebben.

    Van boven naar beneden: wat niet over geld gaat, en dan de som.

    `auto_laden` is het plan van de paal: per blok wat de auto van het net
    zou nemen (v0.95.0). Daarmee zegt het uurplan welke uren de batterij de
    auto helpt, en rekent de nachtbalans ermee; zie `auto_hulp`.
    """
    if not enabled:
        return Besluit(
            STANDBY,
            reason="De sturing van deze batterij staat uit.",
            rule="uit",
        )
    if b.soc is None or b.capacity_kwh is None:
        return Besluit(
            STANDBY,
            reason="De coach weet niet hoe vol de batterij is, dus hij laat hem stilstaan.",
            plan="Zodra de accustand er weer is gaat hij verder.",
            rule="geen-accustand",
        )

    blokken = [rij for rij in prices if rij["end"] > now] or _vlakke_blokken(now, None, tariff)
    # Bij een dynamisch contract is de avondpiek een gewoon uur op zijn prijs.
    dicht = piek_dicht(prices)
    nu = price_now(blokken, now)
    if nu is None:
        # Eis 6: nooit blind. Zonder prijs van dit moment alleen zon erin en het
        # huis eruit, want daar is geen prijs voor nodig om het goed te doen.
        return _met_paal(
            Besluit(
                NUL,
                reason="De prijs van dit uur is niet bekend, dus hij houdt alleen de meter op nul.",
                plan="Van het net laden doet hij pas weer als de prijzen er zijn.",
                rule="geen-prijs",
            ),
            paal_laadt, b,
        )

    koop, terug = nu["price"], nu.get("feed_in")

    # Een negatieve prijs gaat voor alles: elk verlies levert dan geld op. Het
    # gaat om wat de bewoner betaalt, met belasting en opslag erin; dat kwam in
    # 2026 een paar keer voor (de eigenaar, 21-09-2026).
    if koop < 0 and not (dicht and in_evening_peak(now)) and b.soc < b.soc_max - VOL_MARGE:
        return Besluit(
            MAX_LADEN,
            power_w=b.max_charge_w,
            reason=f"Stroom kost nu {_euro(koop)} per kWh: je krijgt geld toe. Hij laadt op vol vermogen en geeft niets af.",
            plan="Zodra de prijs weer boven nul komt rekent hij gewoon verder.",
            rule="negatieve-prijs",
        )

    if b.rte is None:
        # Zonder rendement valt er niets te vergelijken. Wat wel zeker is: als
        # terugleveren evenveel opbrengt als stroom kost, verliest opslaan
        # altijd, hoe goed de batterij ook is.
        if terug is not None and terug >= koop - PRICE_MARGIN and not b.zelf_nul:
            return Besluit(
                STANDBY,
                reason="Terugleveren brengt nu evenveel op als stroom kost, dus opslaan kost alleen het verlies in de batterij.",
                rule="salderen",
            )
        if _vlak(blokken):
            # Van het net laden loont hier nooit, wat het rendement ook is; daar
            # hoeft de bewoner dus ook niets voor in te vullen.
            return _met_paal(
                Besluit(
                    NUL,
                    reason="Hij houdt de meter op nul: overschot gaat erin, wat het huis vraagt komt eruit.",
                    plan="Stroom kost bij je contract elk uur hetzelfde, dus van het net laden levert nooit iets op.",
                    rule="nul",
                ),
                paal_laadt, b,
            )
        return _met_paal(
            Besluit(
                NUL,
                reason="Hij houdt de meter op nul. Het rendement van de batterij is nog niet bekend, dus van het net laden doet hij nog niet.",
                plan="Met een kWh-meter op de batterij meet de coach het zelf; anders vul je het in bij Apparaten.",
                rule="rendement-onbekend",
            ),
            paal_laadt, b,
        )

    som = _waarde_vooruit(now, blokken, forecast, b, piek=dicht)
    if som is None:
        return _met_paal(
            Besluit(NUL, reason="Hij houdt de meter op nul.", rule="nul"), paal_laadt, b
        )

    e = b.soc / 100.0 * b.capacity_kwh
    na = som.na[0]
    # Wat een kilowattuur erbij oplevert en wat een kilowattuur eraf kost, over
    # een stap van het rooster. Vlak onder de laadgrens past er geen hele stap
    # meer bij: dan telt wat er nog wel bij past. Met een hele stap in de noemer
    # kwam de waarde daar een achtste te laag uit, precies genoeg om een
    # gelijkspel de verkeerde kant op te laten vallen: in het virtuele huis
    # bleef de batterij op een zonnige dag op 93% staan in plaats van 95.
    op_stap = min(som.stap, som.hoog - e)
    neer_stap = min(som.stap, e - som.laag)
    erbij = (
        (_tussen(na, som.stap, som.laag, e) - _tussen(na, som.stap, som.laag, e + op_stap)) / op_stap
        if op_stap > 1e-6 else 0.0
    )
    eraf = (
        (_tussen(na, som.stap, som.laag, e - neer_stap) - _tussen(na, som.stap, som.laag, e)) / neer_stap
        if neer_stap > 1e-6 else float("inf")
    )
    vol = e >= som.hoog - 1e-6
    leeg = b.soc <= b.bodem + 1e-6
    uren = _vooruit(som, b)
    nacht_voor_auto = balans_kwh(now, forecast, b)
    hulp = auto_hulp(uren, b, nacht_voor_auto, auto_laden or [], helpt)
    # Laadt de paal nu volgens zijn eigen plan? Dan helpt de batterij alleen als
    # dit blok hulp kreeg (v0.104.1); anders gaat die naar een duurder laaduur.
    laadt_gepland = any(van <= now < tot and kwh > 0.005 for van, tot, kwh in auto_laden or [])
    hulp_nu = (hulp[0] > 0.005) if laadt_gepland and hulp else None
    hulp_om = next((u.start for u, h in zip(uren, hulp) if h > 0.005), None)
    auto_ac = _met_auto(uren, b, hulp)
    auto_weg = auto_ac / som.eta
    kijk = _vooruitkijk_zin(now, forecast, b, auto_ac, bijladen=not _vlak(blokken), uren=uren)
    piek = dicht and in_evening_peak(now)
    # Onder welke prijs een kWh van het net erbij nu loont: wat hij in de
    # batterij waard is, min het verlies bij het laden. Voor de kaart; de
    # eigenaar op 30-09-2026 bij "Een kWh erin € 0,301, is straks waard" en een
    # nacht van € 0,313: "is het niet goedkoper om iets bij te kopen?" Die
    # € 0,301 is per kWh ín de batterij; naast de prijslijst hoort € 0,259.
    inkoop = None if vol else erbij * som.eta

    # Zon opslaan en het huis voeden: elk tegen wat een kilowattuur in de
    # batterij straks waard is.
    #
    # Bij gelijkspel wint wat je in handen hebt. Op een zonnige dag komt de
    # batterij hoe dan ook vol, en dan is een kilowattuur zon nu opslaan precies
    # evenveel waard als hem straks opslaan; wie dan "niet" kiest rekent op een
    # zon die er nog niet is. Hetzelfde voor het huis voeden.
    mag_zon = not vol and (terug is None or terug <= erbij * som.eta + PRICE_MARGIN)
    mag_huis = not leeg and koop * som.eta >= eraf - PRICE_MARGIN

    # Van het net laden en handelen: die volgen het plan zelf. Zie
    # `_rustig_vermogen`.
    if not vol and not piek:
        vermogen, tot = _rustig_vermogen(
            uren, b, piek=dicht, drempel=_overname_drempel(som, b), houden_tot=_houden_tot(b, som),
        )
        if vermogen > 0:
            rustig = vermogen < b.max_charge_w - 1.0
            if _kw(vermogen) == _kw(0.0):
                # Het einde van een beurt die al liep: er moet bijna niets meer
                # bij, en hij houdt de batterij vast tot het blok om is.
                hoe = f"Hij maakt het laden van het net af tot {_clock(tot)} en geeft tot dan niets af."
            else:
                hoe = f"Hij laadt van het net op {_kw(vermogen)}" + (
                    f", rustig verdeeld tot {_clock(tot)}." if rustig and tot else "."
                )
            return Besluit(
                NETLADEN,
                power_w=vermogen,
                reason=(
                    f"Stroom kost nu {_euro(koop)} en dat is goedkoper dan wat de batterij je straks bespaart. "
                    + hoe
                ) if b.vol_voor is None else (
                    "Vandaag hoort de batterij een keer helemaal vol, voor het balanceren van de cellen. "
                    f"Dit zijn daar de goedkoopste uren voor: hij laadt van het net op {_kw(vermogen)}."
                ),
                plan=kijk,
                rule="netladen" if b.vol_voor is None else "volle-beurt",
                waarde=erbij,
                uren=uren,
                auto_weg=auto_weg,
                inkoop_tot=inkoop,
            )

    # Handelen alleen met wat er boven de nacht uitkomt. De eigenaar op
    # 22-09-2026: "nul op de meter heeft prioriteit, het overschot verhandelen
    # met hoge tarieven." De som zelf zou alles verkopen en 's nachts
    # terugkopen zodra dat goedkoper is, maar dat is niet wat de bewoner
    # bedoelt met een batterij die de nacht overbrugt.
    # Wat de auto er vannacht uit haalt telt mee: die surplus is dan al op.
    nacht = nacht_voor_auto
    na_auto = balans_kwh(now, forecast, b, auto_weg)
    if b.handelen and not leeg and not paal_laadt and (not b.nacht or na_auto is None or na_auto > 0):
        vermogen, tot = _rustig_vermogen(uren, b, ontladen=True, drempel=_overname_drempel(som, b))
        if vermogen > 0:
            return Besluit(
                HANDELEN,
                power_w=vermogen,
                reason=f"Terugleveren brengt nu {_euro(terug or 0.0)} op, meer dan het straks kost om bij te laden. Hij levert aan het net.",
                plan=kijk,
                rule="handelen",
                waarde=eraf,
                uren=uren,
                auto_weg=auto_weg,
                inkoop_tot=inkoop,
            )

    if b.zelf_nul or (mag_huis and mag_zon):
        # Doet de batterij het zelf, dan is dit wat hij doet: stilstaan, alleen
        # zon opslaan of alleen ontladen kan hij in zijn eigen stand niet.
        besluit = Besluit(
            NUL,
            reason="Hij houdt de meter op nul: overschot gaat erin, wat het huis vraagt komt eruit.",
            plan=kijk, rule="nul", waarde=eraf, uren=uren, auto_weg=auto_weg,
        )
    elif mag_zon:
        besluit = Besluit(
            ZONNELADEN,
            reason=(
                "De batterij is leeg tot aan zijn ondergrens. Zonoverschot gaat er wel in."
                if leeg else
                f"Stroom kost nu {_euro(koop)}, en wat er in de batterij zit bespaart straks meer. Hij bewaart het; zonoverschot gaat er wel in."
            ),
            plan=kijk, rule="leeg" if leeg else "bewaren", waarde=eraf, uren=uren,
            auto_weg=auto_weg,
        )
    elif mag_huis:
        besluit = Besluit(
            ONTLADEN,
            reason=(
                "De batterij is vol. Wat het huis vraagt komt eruit."
                if vol else
                f"Terugleveren brengt nu {_euro(terug or 0.0)} op, meer dan opslaan oplevert. Wat het huis vraagt komt wel uit de batterij."
            ),
            plan=kijk, rule="vol" if vol else "niet-opslaan", waarde=eraf, uren=uren,
            auto_weg=auto_weg,
        )
    else:
        besluit = Besluit(
            STANDBY,
            reason=(
                "Terugleveren brengt nu evenveel op als stroom kost, dus opslaan kost alleen het verlies in de batterij."
                if terug is not None and terug >= koop - PRICE_MARGIN else
                "Nu laden of ontladen levert niets op, dus hij staat stil."
            ),
            plan=kijk, rule="standby", waarde=eraf, uren=uren, auto_weg=auto_weg,
        )
    besluit.inkoop_tot = inkoop
    besluit.auto_hulp_nu = hulp_nu
    besluit.auto_hulp_om = hulp_om
    return _met_paal(besluit, paal_laadt, b, nacht, helpt=helpt)


def _overname_drempel(som: _Som, b: Batterij) -> float:
    """Hoe groot een beurt van of naar het net minstens is om een batterij die zelf nul doet over te nemen.

    Eén stap van het rooster van de som, aan de wisselstroomkant (v0.102.3).
    Doet de batterij zelf nul, dan kent de som geen stilstaan
    (`_zelf_toegestaan`), en is het dichtstbijzijnde wat hij wel mag het
    eerstvolgende punt van het rooster erboven: een beetje van het net laden.
    Een beurt kleiner dan één stap is dus afronding van de som, en geen plan.
    In de klantwoning op 30-09-2026 nam de coach de batterij om 16:00:41 over
    en laadde hij drie minuten op 1,2 kW; om 15:00:41 zeventien minuten voor
    een plan van 0,35 kWh, bij een stap van 0,38. Heeft de coach hem al in
    handen, dan geldt alleen de procent in `_rustig_vermogen`.
    """
    if not b.zelf_nul or b.overgenomen:
        return 0.0
    return som.stap / som.eta


def auto_hulp(
    uren: list[Uur],
    b: Batterij,
    over_kwh: float | None,
    laden: list[tuple[datetime, datetime, float]],
    helpt: bool = False,
) -> list[float]:
    """Per blok van het uurplan: wat de batterij aan de auto geeft, in kWh (v0.95.0).

    De bewoner van de eerste woning op 23-09-2026 om 22:40, bij een accu die
    boven 50% de auto mocht helpen: "theoretisch zou 'wat gaat hij doen' nu
    moeten kijken naar de EV-laadplanning, en zien dat hij om 23 uur mee moet
    gaan helpen laden." Die avond hielp hij van 23:00:48 tot 23:17:43 op
    3,45 kW, van 78 tot de 70% die toen de grens was, en het uurplan wist
    daar niets van.

    Dezelfde regels als `_met_paal`, want dat is wat de regelaar doet: niet
    in een blok waarin hij zelf van het net laadt, boven `auto_grens` (de
    eerste keer pas vanaf de grens plus `AUTO_MARGE`), op wat er naast het huis
    nog van het ontlaadvermogen over is, en met de nachtstrategie nooit meer
    dan wat er morgenvroeg over zou zijn. Een blok op standby telt wel: bij
    gelijke prijzen kiest het uurplan standby waar de coach die minuut zelf nul
    op de meter kiest (in `plan_batterij` wint dan wat je in handen hebt). `laden` is per blok van de paal
    (van, tot, kWh van het net), van zijn eigen plan; wat daarvan in een blok
    hier valt, naar rato van de tijd.

    Aan de wisselstroomkant, zoals de bewoner hem in de auto ziet gaan.

    **Op de duurste laaduren eerst** (v0.104.1). De eigenaar op 30-09-2026 om
    23:48, bij het plan van de eerste woning (laden om 00:00 voor € 0,319, om
    02:00 voor € 0,326 en om 04:00 voor € 0,325, en de 2,3 kWh uit de batterij om
    00:00): "hij pakt het goedkoopste uur om te ondersteunen. Eigenlijk moet hij
    meehelpen op de duurste momenten, om daar de financiële pijn het meest te
    verzachten." Tot dan gaf hij vanaf het eerste laaduur tot zijn grens. Nu
    gaan de laaduren van duur naar goedkoop, en krijgt elk wat er dan nog kan:
    wat er naast het huis van het ontlaadvermogen over is, en wat de batterij
    aan het eind van dat blok boven zijn grens heeft, zonder dat een later blok
    dat al hulp kreeg eronder zakt. De grens is er voor de auto; het huis mag
    daarna gewoon verder uit de batterij, zoals altijd. Bij gelijke prijzen het vroegste eerst, zoals het
    was. Beginnen doet hij pas `AUTO_MARGE` boven de grens, zoals `_met_paal`:
    het vroegste blok met hulp moet dat halen, tenzij hij de vorige ronde al
    hielp (`helpt`).
    """
    uit = [0.0] * len(uren)
    if b.auto_boven is None or b.capacity_kwh is None or b.soc is None or not laden:
        return uit
    eta = sqrt(min(max(b.rte, 0.05), 1.0)) if b.rte else 1.0
    cap = b.capacity_kwh
    vrij = float("inf")
    if b.nacht:
        if over_kwh is None:
            return uit
        # Dezelfde maat als `auto_grens`: wat er morgenvroeg over is, terug naar
        # de accukant.
        vrij = max(0.0, over_kwh) / (b.rte if b.rte else 1.0)
    grens = max(float(b.auto_boven), b.bodem) / 100.0 * cap
    marge = AUTO_MARGE / 100.0 * cap
    # Per blok: wat de auto van het net zou nemen, wat er naast het huis van het
    # ontlaadvermogen over is, en wat de batterij aan het eind van het blok
    # boven zijn grens heeft zonder hulp (accukant).
    wil, ruimte, boven = [], [], []
    for uur in uren:
        deel = max(0.0, (uur.end - uur.start).total_seconds() / 3600.0)
        w = 0.0
        for van, tot, kwh in laden:
            lengte = (tot - van).total_seconds()
            overlap = (min(tot, uur.end) - max(van, uur.start)).total_seconds()
            if lengte > 0 and overlap > 0:
                w += max(0.0, kwh) * overlap / lengte
        mag = w > 0.005 and uur.stand not in (NETLADEN, MAX_LADEN) and deel > 0
        wil.append(w if mag else 0.0)
        ruimte.append(max(0.0, b.max_discharge_w / 1000.0 * deel - max(0.0, -uur.kwh)))
        boven.append(uur.soc / 100.0 * cap - grens)
    weg = 0.0
    volgorde = sorted((i for i in range(len(uren)) if wil[i] > 0), key=lambda i: (-uren[i].price, i))
    for i in volgorde:
        if not helpt and not any(uit[:i]):
            # Het vroegste blok met hulp: begint hij hier, dan pas boven de marge.
            begin = (uren[i - 1].soc if i else b.soc) / 100.0 * cap
            if begin <= grens + marge:
                continue
        kan = min([boven[i]] + [boven[j] for j in range(i + 1, len(uren)) if uit[j] > 0])
        geef = min(wil[i], ruimte[i], max(0.0, min(kan, vrij - weg)) * eta)
        if geef > 0.005:
            uit[i] = geef
            weg += geef / eta
            for j in range(i, len(boven)):
                boven[j] -= geef / eta
    return uit


def _met_auto(uren: list[Uur], b: Batterij, hulp: list[float]) -> float:
    """Wat `auto_hulp` zegt in het uurplan zetten, en het totaal teruggeven."""
    if not any(hulp) or not b.capacity_kwh:
        return 0.0
    eta = sqrt(min(max(b.rte, 0.05), 1.0)) if b.rte else 1.0
    weg = 0.0
    for uur, geef in zip(uren, hulp):
        if geef > 0:
            uur.auto_kwh = geef
            uur.kwh -= geef
            weg += geef / eta
        uur.soc = max(b.bodem, uur.soc - weg / b.capacity_kwh * 100.0)
    return sum(hulp)


def met_paal(
    besluit: Besluit, paal_laadt: bool, b: Batterij | None = None, over_kwh: float | None = None,
    *, grens: float | None = None, helpt: bool = False,
) -> Besluit:
    """`_met_paal` voor de snelle regelaar in coach.py (v0.87.1).

    De regelaar tikt elke paar seconden; de grens voor de auto wordt eens per
    minuut in de besluitronde vastgesteld en hier meegegeven, anders schuift
    hij met elke tik mee en valt de batterij rond de grens aan en uit (in het
    virtuele huis 34 wissels in een nacht, `batterij-helpt-auto-nacht`).
    `helpt` is of hij de vorige tik al hielp: dan tot de grens, anders pas
    vanaf de grens plus `AUTO_MARGE`.
    """
    return _met_paal(besluit, paal_laadt, b, over_kwh, grens=grens, helpt=helpt)


def auto_grens(b: Batterij, over_kwh: float | None) -> float | None:
    """Tot welke accustand de batterij de auto mag helpen, of None: dan niet.

    De bewoner van de eerste woning op 23-09-2026, naar evcc: "bij laden van de
    auto mag alle batterijcapaciteit boven X% gebruikt worden." En de eigenaar
    erbij: de nachtbalans gaat voor, want "auto laden vanuit de batterij doe
    je echt alleen als er te veel capaciteit over is; in het kader van
    efficiëntie is het niet top, namelijk drie keer verlies." Dus de hoogste
    van: de grens van de bewoner, de eigen ondergrens van de batterij, en met
    de nachtstrategie aan de accustand die de nacht nog nodig heeft. Dat
    laatste is wat er nu in zit min wat er morgenvroeg over zou zijn
    (`balans_kwh`, na het verlies, dus hier terug naar de accukant). Weet hij
    de nacht niet, dan helpt hij niet.
    """
    if b.auto_boven is None or b.capacity_kwh is None or b.soc is None:
        return None
    grens = max(float(b.auto_boven), b.bodem)
    if b.nacht:
        if over_kwh is None:
            return None
        vrij = max(0.0, over_kwh) / (b.rte if b.rte else 1.0)
        grens = max(grens, b.soc - vrij / b.capacity_kwh * 100.0)
    return grens


def _met_paal(
    besluit: Besluit, paal_laadt: bool, b: Batterij | None = None, over_kwh: float | None = None,
    *, grens: float | None = None, helpt: bool = False,
) -> Besluit:
    """De laadpaal laadt: dan geeft de batterij niets af.

    De eigenaar op 21-09-2026: "als een laadpaal aan gaat moet de batterij niet
    ontladen." Anders loopt hij met een paar kilowatt leeg in een auto die er
    elf trekt. Zon opslaan mag wel, voor zover de paal die niet zelf neemt.

    Behalve met wat er echt over is (v0.90.0): boven `auto_grens` houdt hij
    de meter op nul, en dan komt wat de auto vraagt uit de batterij.
    """
    if not paal_laadt or besluit.stand not in (NUL, ONTLADEN, HANDELEN):
        return besluit
    if grens is None and b is not None:
        grens = auto_grens(b, over_kwh)
    # Het plan bewaart de hulp voor een duurder laaduur (v0.104.1).
    later = besluit.auto_hulp_nu is False
    if not later and grens is not None and b is not None and b.soc is not None and b.soc > grens + (0.0 if helpt else AUTO_MARGE):
        besluit.stand = NUL
        besluit.power_w = 0.0
        besluit.reason = (
            f"De laadpaal laadt, en de batterij heeft meer dan de nacht nodig: tot "
            f"{grens:.0f}% helpt hij de auto."
            if b.nacht else
            f"De laadpaal laadt, en de batterij zit boven {grens:.0f}%: tot daar helpt hij de auto."
        )
        besluit.rule = "auto-helpen"
        return besluit
    besluit.stand = ZONNELADEN if besluit.stand == NUL else STANDBY
    besluit.power_w = 0.0
    om = besluit.auto_hulp_om
    besluit.reason = (
        (
            f"De laadpaal laadt. De batterij helpt de auto om {om:%H:%M}, op een duurder laaduur, en geeft nu niets af."
            if later and om is not None else
            "De laadpaal laadt, dus de batterij geeft niets af."
        )
        + (" Zonoverschot gaat er nog wel in." if besluit.stand == ZONNELADEN else "")
    )
    besluit.rule = "paal-laadt"
    return besluit


# --- De regelaar --------------------------------------------------------------
#
# De eigenaar op 21-09-2026: "als je realistisch kijkt verbruik je nooit steady
# 350 W. Hoe zorgen we dat we niet gaan pendelen?"
#
# Diezelfde avond gemeten in de eerste woning, waar een andere sturing de
# batterij op dat moment regelde. Een rustig half uur: de meter 98,9% van de
# tijd binnen 50 W van nul met zes opdrachten, en drie minuten lang -37 W
# zonder dat er iets gebeurde (een dode band van 40 W). Een sprong van 2,1 kW
# om 19:19:47: opdracht na twee seconden, de meter na tien seconden terug op
# 23 W, geen doorschot; de batterij volgde een opdracht binnen ongeveer vijf
# seconden en Home Assistant kreeg de meter daar elke vijf seconden. En waar
# het misging: rond nul, standby en ontladen om de tien tot vijftien seconden,
# 233 statuswissels op een dag.

# Binnen zoveel watt van het doel gebeurt er niets. De gemeten 40 W.
DODE_BAND_W = 40.0

# Hoe lang de batterij nodig heeft om een opdracht uit te voeren: de gemeten
# vijf seconden. Een meting van de meter of van de batterij van vóór dat
# moment zegt nog niets over de opdracht.
VOLGT_NA = timedelta(seconds=5)

# Hoe lang de regelaar na een opdracht hooguit wacht op de bevestiging dat de
# batterij hem uitvoert, voordat hij toch opnieuw corrigeert. Hier komt
# pendelen vandaan: bijsturen op een meterwaarde waar je vorige opdracht nog
# niet in zit. De keuze van de eigenaar op 22-09-2026: vijftien seconden, want
# de sensor van de Anker liep die dag vijf tot tien seconden achter.
WACHT_OP_BATTERIJ = timedelta(seconds=15)

# Buiten dat venster rekent de regelaar met zijn eigen opdracht en niet met de
# vermogenssensor van de batterij, tot die sensor hem zoveel metingen achter
# elkaar tegenspreekt. Gemeten op 22-09-2026 in de eerste woning, naast een
# kWh-meter op dezelfde batterij: de sensor van de Anker toont na een opdracht
# eerst een aanloop die er niet is (1040, 1020, 1010, 1000, 940 en dan pas
# 2500, terwijl de meter meteen 2580 zag), en soms twee seconden lang de
# opdracht zelf (0 W terwijl er 2215 liep). Wie daarop rekent telt zijn eigen
# opdracht dubbel, en dat was precies de slinger van de sturing die daar toen
# draaide. Maar een batterij die een opdracht blijvend niet uitvoert (vol,
# leeg, te warm) moet wel gezien worden, en dat is wat de teller doet.
AFWIJK_METINGEN = 3

# Een afwijking boven deze grens wordt meteen gevolgd; daaronder pas als hij
# `KLEIN_METINGEN` metingen achter elkaar dezelfde kant op staat. Vijf keer de
# dode band, en in het virtuele huis nagemeten op een oven die op zijn
# thermostaat klikt.
GROOT_W = 200.0
KLEIN_METINGEN = 3

# Rond nul twee grenzen: pas beginnen boven de ene, pas ophouden onder de
# andere, en een richting niet omkeren binnen een minuut. Grijpen en loslaten
# op verschillende punten, zoals `DEADLINE_RELEASE_HOURS` bij de klaar-tijd.
# De getallen komen van de gemeten wissels: die zaten bij opdrachten tussen 100
# en 200 W. **Te beproeven aan een echte batterij.**
BEGIN_W = 100.0
STOP_W = 50.0
RICHTING_WACHT = timedelta(seconds=60)

# Geduld met lasten die korter duren dan de lus om ze te volgen. De bewoner van
# de eerste woning op 24-09-2026: "je zou ervoor kunnen kiezen om de accu pas
# bij te laten springen als een load minimaal 30 of 60 seconden boven een
# bepaalde waarde komt." Die nacht ging daar om de dertig seconden een last van
# 490 W tien seconden aan, de batterij volgde een opdracht na drie tot acht
# seconden, en de regelaar stond in tegenfase: 07:44:06 de meter +468 W en de
# opdracht 688, 07:44:14 de batterij op 681, 07:44:16 de last weg en de meter
# -511 W. Tot 210 opdrachten per uur, en een derde van wat hij gaf ging naar
# het net.
#
# Niet altijd wachten: een oven op zijn thermostaat (45 s aan, 45 s uit) volgt
# hij met wachten slechter dan zonder, want dan springt hij bij juist op het
# moment dat de oven afslaat, en het laagste van een halve minuut ruis dekt
# structureel te weinig. Dus: gewoon volgen, tot hij een grote last achterna
# ging die binnen `KORTE_LAST` alweer weg was (de tegenfase van die nacht).
# Dan `GEDULD_DUUR` lang geduld, en dat geduld verlengt zich zolang er grote
# lasten komen en gaan die korter duren. Met geduld volgt hij van een grote
# sprong alleen wat er `VOLG_WACHT` lang de hele tijd was; terug naar nul gaat
# altijd meteen, want anders levert de batterij aan het net of laadt hij van
# het net. **De getallen zijn gekozen in het virtuele huis**; zie
# docs/batterij.md.
VOLG_WACHT = timedelta(seconds=30)
KORTE_LAST = timedelta(seconds=30)
GEDULD_DUUR = timedelta(minutes=15)

# Zwijgt de meter zo lang, dan gaat de batterij naar 0 W. Een lus die stilvalt
# mag hem nooit op zijn laatste opdracht laten staan: dat is leeglopen naar het
# net, of vol van het net trekken, tot iemand het ziet.
METER_STIL = timedelta(seconds=30)


@dataclass
class Regelaar:
    """Houdt de meter op zijn doel, op het tempo van de meter zelf.

    Eén som en geen versterkingsfactor: het huis vraagt wat de meter zegt plus
    wat de batterij nu levert, en dat is de nieuwe opdracht. Alles eromheen is
    er om dat niet te vaak en niet te vroeg te doen.

    Tekens: de meter positief bij afname, de batterij positief bij laden.
    """

    opdracht_w: float = 0.0
    opdracht_op: datetime | None = None
    # Of de laatste opdracht al in het gemeten batterijvermogen terug te zien
    # was. Tot dan wordt er niet opnieuw gecorrigeerd.
    bezonken: bool = True
    # Wanneer de sensor de laatste opdracht voor het eerst bevestigde. Een
    # meting van de meter telt pas als hij daarna genomen is; zie `stap`.
    bevestigd_op: datetime | None = None
    # Hoe vaak de sensor achter elkaar iets anders zei dan de opdracht, buiten
    # het venster na een opdracht. Zie `AFWIJK_METINGEN` en `vermogen_w`.
    _afwijkt: int = 0
    # De richting van de laatste opdracht die niet nul was, en wanneer er voor
    # het laatst zo'n opdracht stond. Voor `RICHTING_WACHT`.
    laatste_kant: float = 0.0
    actief_op: datetime | None = None
    # Wanneer de meter voor het laatst iets zei. Zie `METER_STIL`.
    net_gezien_op: datetime | None = None
    # Hoeveel metingen achter elkaar een kleine afwijking dezelfde kant op stond.
    _kant: int = 0
    _keren: int = 0
    # Wat het huis de afgelopen `VOLG_WACHT` van de batterij vroeg: (tijd, watt).
    # Tot wanneer hij geduld heeft, wanneer hij voor het laatst een grote stap
    # van nul af zette, en sinds wanneer er met geduld een grote vraag staat
    # die hij nog niet volgt. Zie `_geduld`.
    _vraag: list = field(default_factory=list)
    geduldig_tot: datetime | None = None
    _weg_op: datetime | None = None
    _piek_sinds: datetime | None = None

    def doel_w(self, koop: float | None, terug: float | None) -> float:
        """Waar de meter op hoort te staan.

        Waar terugleveren minder opbrengt dan inkopen kost, is een paar watt te
        veel terugleveren goedkoper dan een paar watt tekortkomen: dan mikt hij
        een halve dode band onder nul. Anders op nul.
        """
        if koop is not None and terug is not None and terug >= koop:
            return 0.0
        return -DODE_BAND_W / 2.0

    def vermogen_w(self, batterij_w: float | None) -> float:
        """Wat de batterij doet, zoals de regelaar erover denkt: zijn eigen opdracht.

        De sensor is de bevestiging, niet de bron: hij loopt achter en toont
        onderweg waarden die er niet zijn (zie `AFWIJK_METINGEN`). Pas als hij
        de opdracht een tijdje tegenspreekt is het de batterij die niet doet
        wat er gevraagd is, en dan telt de sensor. Zonder sensor is er alleen
        de opdracht. Ook voor wie buiten de regelaar naar de batterij kijkt:
        de paalplanner ziet anders bij elke omslag een schijnoverschot.
        """
        if batterij_w is None or abs(batterij_w - self.opdracht_w) <= DODE_BAND_W:
            return self.opdracht_w
        return batterij_w if self._afwijkt >= AFWIJK_METINGEN else self.opdracht_w

    def stap(
        self,
        now: datetime,
        *,
        net_w: float | None,
        net_op: datetime | None,
        batterij_w: float | None,
        besluit: Besluit,
        b: Batterij,
        doel_w: float = 0.0,
        ruimte_w: float | None = None,
    ) -> float | None:
        """De nieuwe opdracht in watt (laden positief), of None voor "laat staan".

        `ruimte_w` is wat de zekering de batterij nog aan laadvermogen toestaat,
        of None als dat niet bewaakt wordt.
        """
        mag_laden, mag_ontladen = besluit.grenzen
        hoog = b.max_charge_w if mag_laden else 0.0
        laag = -b.max_discharge_w if mag_ontladen else 0.0
        if b.soc is not None:
            if b.soc >= b.soc_max:
                hoog = 0.0
            if b.soc <= b.bodem:
                laag = 0.0
        if ruimte_w is not None:
            hoog = min(hoog, max(0.0, ruimte_w))

        if self.opdracht_w != 0.0:
            self.actief_op = now

        # Een meter die één meting overslaat is geen meter die zwijgt: veel
        # integraties melden tussendoor even "niet beschikbaar". Dan blijft de
        # opdracht staan. Pas na `METER_STIL` zonder een enkele goede meting
        # gaat de batterij naar nul.
        if net_w is not None and net_op is not None:
            self.net_gezien_op = max(net_op, self.net_gezien_op or net_op)
        stil = self.net_gezien_op is None or now - self.net_gezien_op > METER_STIL
        if besluit.stand == STANDBY or stil:
            return self._zet(now, 0.0, meteen=True)
        if net_w is None:
            return None
        if besluit.stand == MAX_LADEN:
            return self._zet(now, hoog, meteen=True)

        # Wacht tot de vorige opdracht te zien is, anders corrigeer je dubbel.
        # Te zien is: de batterij heeft de tijd gehad om hem uit te voeren, de
        # sensor meldt hem (of er is geen sensor), en de meter heeft daarna nog
        # gemeten. Een sensor die vlak na de opdracht al "klopt" toont de
        # opdracht en niet de meting; die telt niet. Duurt het langer dan
        # `WACHT_OP_BATTERIJ`, dan gaat hij toch verder.
        #
        # "Daarna" is na de bevestiging van de sensor en niet na de opdracht
        # plus `VOLGT_NA`. In de eerste woning op 22-09-2026 's nachts volgde
        # de batterij pas na tien seconden: de meter van :08 toonde nog de
        # oude stand, de sensor van :09 al de nieuwe, en de regelaar telde die
        # oude meting bij de nieuwe stand op. Elke tien seconden een opdracht
        # van 1 tot 2 kW de andere kant op, laden van het net op 12% midden
        # in de nacht. De meter meldt eens per vijf seconden, dus dit kost
        # hooguit één tik extra.
        if not self.bezonken and self.opdracht_op is not None:
            sinds = now - self.opdracht_op
            aangekomen = sinds >= VOLGT_NA and (
                batterij_w is None or abs(batterij_w - self.opdracht_w) <= DODE_BAND_W
            )
            if aangekomen and batterij_w is not None and self.bevestigd_op is None:
                self.bevestigd_op = now
            # Zonder sensor is de meter het enige bewijs, en dan hoort de
            # batterij ruim de tijd gehad te hebben voordat die meting telt.
            if batterij_w is None:
                grens = self.opdracht_op + 2 * VOLGT_NA
            else:
                grens = self.bevestigd_op or (self.opdracht_op + VOLGT_NA)
            meter_na = net_op is not None and net_op > grens
            if (aangekomen and meter_na) or sinds >= WACHT_OP_BATTERIJ:
                self.bezonken = True
            else:
                return None
        if batterij_w is not None:
            if abs(batterij_w - self.opdracht_w) <= DODE_BAND_W:
                self._afwijkt = 0
            else:
                self._afwijkt += 1

        # De som: wat het huis vraagt is de meter plus wat de batterij nu doet,
        # en dat laatste is de eigen opdracht zolang de sensor die niet
        # blijvend tegenspreekt.
        wens = self.vermogen_w(batterij_w) - (net_w - doel_w)
        wens = self._geduld(now, min(max(wens, laag), hoog))
        if besluit.stand == NETLADEN:
            wens = max(wens, besluit.power_w)
        elif besluit.stand == HANDELEN:
            wens = min(wens, -besluit.power_w)
        wens = min(max(wens, laag), hoog)

        # Rond nul: twee grenzen.
        if abs(self.opdracht_w) < 1.0:
            if abs(wens) < BEGIN_W:
                wens = 0.0
        elif abs(wens) < STOP_W:
            wens = 0.0

        # Een kleine wens keert de richting niet binnen een minuut om; tot dan
        # staat hij stil. Een grote wel: een waterkoker die aangaat terwijl de
        # batterij op zon laadt hoort niet een minuut van het net te komen.
        if (
            wens != 0.0 and self.laatste_kant * wens < 0 and abs(wens) < GROOT_W
            and self.actief_op is not None and now - self.actief_op < RICHTING_WACHT
        ):
            wens = 0.0

        verschil = wens - self.opdracht_w
        if abs(verschil) <= DODE_BAND_W and not (wens == 0.0 and self.opdracht_w != 0.0):
            self._keren = 0
            return None
        if abs(verschil) < GROOT_W:
            kant = 1 if verschil > 0 else -1
            self._keren = self._keren + 1 if kant == self._kant else 1
            self._kant = kant
            if self._keren < KLEIN_METINGEN:
                return None
        self._tegenfase(now, wens)
        return self._zet(now, wens)

    def geduldig(self, now: datetime) -> bool:
        return self.geduldig_tot is not None and now < self.geduldig_tot

    def _geduld(self, now: datetime, wens: float) -> float:
        """Met geduld: van een grote stap van nul af alleen wat al `VOLG_WACHT` bleef.

        Van alles wat het huis in dat venster vroeg telt het stuk dat er de
        hele tijd was: bij laden het laagste, bij ontladen het minst negatieve.
        Een last die korter aanstaat komt zo nooit in de opdracht, en een last
        die blijft wordt na het venster gewoon gevolgd. Terug naar nul gaat
        altijd meteen; een wens de andere kant op eerst meteen naar nul. Een
        kleine stap (onder `GROOT_W`) gaat zoals altijd, anders volgt hij de
        ruis van een rustig huis structureel te laag.
        """
        self._vraag.append((now, wens))
        grens = now - VOLG_WACHT
        # Eén meting van vóór het venster blijft staan: die zegt wat er aan
        # het begin van het venster gevraagd werd.
        while len(self._vraag) > 1 and self._vraag[1][0] <= grens:
            self._vraag.pop(0)
        nu_w = self.opdracht_w
        terug = nu_w * wens >= 0 and abs(wens) <= abs(nu_w)
        vanaf = 0.0 if nu_w * wens < 0 else nu_w
        groot = not terug and abs(wens - vanaf) >= GROOT_W
        if not self.geduldig(now):
            self._piek_sinds = None
            return wens
        # Met geduld: een grote vraag die weer weg is voordat hij `KORTE_LAST`
        # duurde, is er weer een. Het geduld gaat door.
        if groot:
            if self._piek_sinds is None:
                self._piek_sinds = now
        elif self._piek_sinds is not None:
            if now - self._piek_sinds < KORTE_LAST:
                self.geduldig_tot = now + GEDULD_DUUR
            self._piek_sinds = None
        if not groot:
            return wens
        if self._vraag[0][0] > grens:
            return vanaf
        if wens > vanaf:
            return max(vanaf, min(w for _, w in self._vraag))
        return min(vanaf, max(w for _, w in self._vraag))

    def _tegenfase(self, now: datetime, watt: float) -> None:
        """Ging hij net een grote last achterna die alweer weg is? Dan geduld."""
        oud = self.opdracht_w
        if abs(watt) >= abs(oud) + GROOT_W or (watt * oud < 0 and abs(watt) >= GROOT_W):
            self._weg_op = now
        elif (
            abs(watt) <= abs(oud) - GROOT_W and self._weg_op is not None
            and now - self._weg_op < KORTE_LAST
        ):
            self.geduldig_tot = now + GEDULD_DUUR
            self._weg_op = None

    def _zet(self, now: datetime, watt: float, meteen: bool = False) -> float | None:
        watt = float(round(watt))
        if abs(watt - self.opdracht_w) < 1.0 and self.opdracht_op is not None:
            return None
        if watt != 0.0:
            self.laatste_kant = 1.0 if watt > 0 else -1.0
            self.actief_op = now
        self.opdracht_w = watt
        self.opdracht_op = now
        self.bezonken = meteen
        self.bevestigd_op = None
        self._keren = 0
        return watt


# --- Wat de batterij verdient ---------------------------------------------------


def verdiend(
    net_w: float, batterij_w: float, koop: float | None, terug: float | None, seconden: float
) -> float | None:
    """Wat de batterij in dit stukje tijd opleverde, in euro. Kan negatief zijn.

    Het verschil tussen de rekening zoals hij nu loopt en zoals hij zonder
    batterij gelopen had: de meter zonder batterij is de meter min wat de
    batterij doet. Laden kost dus op het moment zelf geld en ontladen levert het
    op, en het rendement zit er vanzelf in omdat er meer in gaat dan eruit komt.

    Per dag opgeteld is dit het kasboek van de batterij: "Opgeleverd" op haar
    kaart en "Door je thuisbatterij" onder In geld in Historie. Een
    terugverdientijd met een aankoopprijs erbij stond er van v0.73.0 tot
    v0.101.1; de eigenaar op 29-09-2026: niet te verdedigen als een installateur
    de klant een terugverdientijd voorrekende en het paneel een andere noemt.
    """
    if koop is None:
        return None

    def rekening(watt: float) -> float:
        prijs = koop if watt >= 0 else (terug or 0.0)
        return watt / 1000.0 * prijs * seconden / 3600.0

    return rekening(net_w - batterij_w) - rekening(net_w)


def zon_in_accu(
    net_w: float, batterij_w: float, koop: float | None, terug: float | None, seconden: float
) -> float | None:
    """Wat de zon die de batterij opnam minder waard was dan zelf gebruikt, in euro.

    De zon die de batterij in ging was zonder batterij het net op gegaan: de
    teruglevering zonder batterij min die met. In geld in Historie telt al het
    niet teruggeleverde deel van de zon tegen de inkoopprijs, alsof het huis
    het meteen gebruikte; voor dit deel klopt dat niet, want zonder batterij
    had het alleen de terugleverprijs opgebracht. Dit verschil gaat eraf, en
    wat de batterij er later mee deed staat in haar kasboek (`verdiend`).

    Tot v0.101.2 ontbrak dit, en trok Historie het hele kasboek van de zon af:
    bij de eigenaar op 29-09-2026 om 10:00 "Door je zon € -0,56", na een nacht waarin de
    batterij het huis voedde. Ontlaadt de batterij naar het net, dan is het
    verschil negatief en telt de zon weer vol.
    """
    if koop is None:
        return None
    met = max(0.0, -net_w)
    zonder = max(0.0, -(net_w - batterij_w))
    return (zonder - met) / 1000.0 * (koop - (terug or 0.0)) * seconden / 3600.0


@dataclass
class Voorraad:
    """Wat de stroom in de batterij kostte, zodat "Opgeleverd" pas telt als ze ontlaadt (v0.107.0).

    Het kasboek (`verdiend`) rekent laden af op het moment zelf: van het net de
    inkoop, uit de zon wat terugleveren had opgebracht, en met salderen is dat
    bijna de hele prijs. Ontladen levert het later terug. Op de kaart zakte
    "Opgeleverd" daardoor elke dag terwijl de batterij laadde, en steeg het 's
    avonds weer; de eigenaar op 05-10-2026, bij "€ 0,74 in 8 dagen": "dat geld
    fluctueert telkens en klopt niet."

    Hier is laden inkopen: wat het kostte gaat in de voorraad. Ontlaadt ze, dan
    gaat er een deel uit, zoveel als wat eruit komt van wat er boven haar
    ondergrens nog uit kan, en wat ontladen opbracht min dat deel is wat ze
    opleverde (gemiddelde kostprijs). Wat er nog uit kan komt bij elke nieuwe
    accustand opnieuw uit die stand en de inhoud, met het rendement voor wat
    er na het verlies van over is; tussen twee standen telt hij de kWh zelf.

    Niet per procent afrekenen: de accustand komt in hele procenten, dus één
    stap is in werkelijkheid ergens tussen niets en twee procent. Zo gerekend
    zakte het bedrag op de proef (test_batterij.py, proef 41) bij de eerste
    stap na het laden 2,7 cent onder nul. Nu loopt het mee met de kWh.

    Wat er al in zat toen de coach begon te tellen kostte niets: wat het kostte
    is niet bekend, dus telt dat deel voluit, net als in het kasboek. Zonder
    accustand of inhoud is er niets om naar te rekenen, en telt het kasboek.
    """

    # Wat de stroom die erin zit kostte, in euro. Negatief als ze bij een
    # negatieve prijs laadde: dan kreeg ze geld toe.
    euro: float = 0.0
    # Wat er boven de ondergrens nog uit kan, in kWh aan de wisselstroomkant.
    kwh: float | None = None
    # De accustand waaruit `kwh` het laatst vastgesteld is.
    soc: float | None = None

    def stap(
        self, euro: float, kwh: float, soc: float | None, bodem: float,
        capaciteit_kwh: float | None, rte: float | None,
    ) -> float:
        """Wat de batterij in deze stap opleverde.

        `euro` komt uit `verdiend`, `kwh` is wat ze deed aan de
        wisselstroomkant, laden positief.
        """
        if soc is None or not capaciteit_kwh:
            return euro
        eta = min(max(rte, 0.05), 1.0) if rte else 1.0
        if self.kwh is None or soc != self.soc:
            self.kwh = max(0.0, soc - bodem) / 100.0 * capaciteit_kwh * sqrt(eta)
            self.soc = soc
        if kwh > 0:
            # Laden: wat het kostte gaat erin, het levert nog niets op.
            self.euro -= euro
            self.kwh += kwh * eta
            return 0.0
        if kwh < 0:
            deel = 1.0 if self.kwh <= -kwh else -kwh / self.kwh
            kost = self.euro * deel
            self.euro -= kost
            self.kwh = max(0.0, self.kwh + kwh)
            return euro - kost
        return euro


# --- Het rendement meten -------------------------------------------------------

# Hoeveel keer de inhoud van de batterij er door de meter gegaan moet zijn
# voordat de tellerstanden samen een rendement geven. Wat er op dat moment nog
# in de batterij zit is dan hooguit een tiende van wat erdoor ging.
RTE_MIN_DOORZET = 10.0


def rendement_uit_tellers(
    erin_kwh: float | None, eruit_kwh: float | None, capacity_kwh: float | None
) -> float | None:
    """Het rendement uit de twee tellers van een kWh-meter op de batterij.

    In de eerste woning op 21-09-2026 kwam zo 73,6% uit de meter. De eigen
    tellers van die batterij telden in dezelfde tijd meer eruit
    dan erin: die meten aan de accukant en zijn hiervoor onbruikbaar.
    """
    if not erin_kwh or eruit_kwh is None or not capacity_kwh:
        return None
    if erin_kwh < RTE_MIN_DOORZET * capacity_kwh:
        return None
    rte = eruit_kwh / erin_kwh
    return rte if 0.3 <= rte <= 1.0 else None
