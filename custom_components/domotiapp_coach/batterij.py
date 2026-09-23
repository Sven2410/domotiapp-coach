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
    if not b.handelen:
        # Zonder handelen gaat er niets naar het net: hooguit wat het huis vraagt.
        neer_w = min(neer_w, max(0.0, huis))
    neer = max(min(som_laag, e), e - neer_w / eta)
    return max(op, e), min(neer, e)


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


def _rustig_vermogen(
    uren: list[Uur], b: Batterij, ontladen: bool = False, piek: bool = True
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
    """
    if not uren:
        return 0.0, None
    prijs = uren[0].price
    energie, tijd, tot = 0.0, 0.0, None
    for uur in uren:
        if abs(uur.price - prijs) > PRICE_MARGIN or (piek and not ontladen and in_evening_peak(uur.start)):
            break
        energie += max(0.0, -uur.net_kwh if ontladen else uur.net_kwh)
        tijd += (uur.end - uur.start).total_seconds() / 3600.0
        tot = uur.end
    # Minder dan een procent van de batterij is geen plan maar afronding: een
    # accusensor is niet fijner dan dat, en in het virtuele huis ging hij er
    # twee minuten voor van het net laden en hield er dan weer mee op.
    if tijd <= 0 or energie <= max(SCHIJF_MINIMUM, 0.01 * (b.capacity_kwh or 0.0)):
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


def _nacht_uren(now: datetime, forecast: Forecast) -> list[tuple[float, float]]:
    """Per uur tot morgenvroeg: (zon, huis) in kWh, het lopende uur naar rato."""
    uren = []
    uur = now.replace(minute=0, second=0, microsecond=0)
    eind = now.replace(hour=OCHTEND_UUR, minute=0, second=0, microsecond=0)
    if eind <= now:
        eind += timedelta(days=1)
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


def nachtverloop(now: datetime, forecast: Forecast, b: Batterij) -> tuple[float, float, float] | None:
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

    De inhoud is aan de accukant en boven de ondergrens, in kWh.
    """
    som = nachtbalans(now, forecast, b)
    if som is None:
        return None
    _zon, _huis, inhoud = som
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


def balans_kwh(now: datetime, forecast: Forecast, b: Batterij) -> float | None:
    """Wat er morgenvroeg naar verwachting over is (positief) of tekortkomt.

    Over is wat er dan nog uit de accu kan komen, na het verlies; nooit meer
    dan de accu kan bevatten. Tekort is wat er in de nacht van het net moet.
    Zie `nachtverloop`.
    """
    verloop = nachtverloop(now, forecast, b)
    if verloop is None:
        return None
    inhoud, tekort, _weg = verloop
    if tekort > 0.05:
        return -tekort
    return inhoud * (b.rte if b.rte else 1.0)


def _vooruitkijk_zin(now: datetime, forecast: Forecast, b: Batterij) -> str:
    """Twee zinnen: zon, huis en batterij tot morgenvroeg, en de conclusie.

    De bewoner van de eerste woning liet op 21-09-2026 zien wat hij van zijn
    oude sturing het meest miste als het weg zou zijn: een regel die zegt
    waaróm er wel of niet bijgeladen wordt. "Wat is mijn verwacht verbruik
    vandaag? Wat is de verwachte zonopbrengst?" En op 22-09-2026: "Als laatste
    afsluiten met een conclusie: je hebt naar verwachting X kWh overschot in je
    accu, of je hebt X kWh tekort om de nacht te overbruggen."
    """
    som = nachtbalans(now, forecast, b)
    verloop = nachtverloop(now, forecast, b)
    if som is None or verloop is None:
        return ""
    zon, huis, bruikbaar = som
    _inhoud, _tekort, weg = verloop
    balans = balans_kwh(now, forecast, b) or 0.0
    # Wat erin zit komt er niet helemaal uit; de conclusie rekent met het
    # rendement, dus de zin zegt erbij waar hij mee rekent.
    eruit = f", goed voor {_kwh(bruikbaar * b.rte)} na het verlies" if b.rte and bruikbaar > 0 else ""
    # En zon die er niet meer in past gaat naar het net: dat verklaart waarom
    # de optelsom van zon en batterij meer is dan wat er morgenvroeg over is.
    past_niet = f" Van die zon past {_kwh(weg)} niet meer in de accu; die gaat naar het net." if weg > 0.05 else ""
    zin = (
        f"Tot morgenvroeg verwacht hij {_kwh(zon)} zon, het huis vraagt {_kwh(huis)} "
        f"en er zit {_kwh(bruikbaar)} in de batterij{eruit}.{past_niet} "
    )
    if balans >= 0:
        return zin + f"Je houdt naar verwachting {_kwh(balans)} over in je accu."
    return (
        zin + f"Je komt naar verwachting {_kwh(-balans)} tekort om de nacht te overbruggen; "
        "hij laadt bij als de stroom goedkoop genoeg is."
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
) -> Besluit:
    """Welke stand de batterij nu hoort te hebben.

    Van boven naar beneden: wat niet over geld gaat, en dan de som.
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
        if terug is not None and terug >= koop - PRICE_MARGIN:
            return Besluit(
                STANDBY,
                reason="Terugleveren brengt nu evenveel op als stroom kost, dus opslaan kost alleen het verlies in de batterij.",
                rule="salderen",
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
    kijk = _vooruitkijk_zin(now, forecast, b)
    piek = dicht and in_evening_peak(now)

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
        vermogen, tot = _rustig_vermogen(uren, b, piek=dicht)
        if vermogen > 0:
            rustig = vermogen < b.max_charge_w - 1.0
            return Besluit(
                NETLADEN,
                power_w=vermogen,
                reason=(
                    f"Stroom kost nu {_euro(koop)} en dat is goedkoper dan wat de batterij je straks bespaart. "
                    f"Hij laadt van het net op {_kw(vermogen)}"
                    + (f", rustig verdeeld tot {_clock(tot)}." if rustig and tot else ".")
                ) if b.vol_voor is None else (
                    "Vandaag hoort de batterij een keer helemaal vol, voor het balanceren van de cellen. "
                    f"Dit zijn daar de goedkoopste uren voor: hij laadt van het net op {_kw(vermogen)}."
                ),
                plan=kijk,
                rule="netladen" if b.vol_voor is None else "volle-beurt",
                waarde=erbij,
                uren=uren,
            )

    # Handelen alleen met wat er boven de nacht uitkomt. De eigenaar op
    # 22-09-2026: "nul op de meter heeft prioriteit, het overschot verhandelen
    # met hoge tarieven." De som zelf zou alles verkopen en 's nachts
    # terugkopen zodra dat goedkoper is, maar dat is niet wat de bewoner
    # bedoelt met een batterij die de nacht overbrugt.
    nacht = balans_kwh(now, forecast, b)
    if b.handelen and not leeg and not paal_laadt and (not b.nacht or nacht is None or nacht > 0):
        vermogen, tot = _rustig_vermogen(uren, b, ontladen=True)
        if vermogen > 0:
            return Besluit(
                HANDELEN,
                power_w=vermogen,
                reason=f"Terugleveren brengt nu {_euro(terug or 0.0)} op, meer dan het straks kost om bij te laden. Hij levert aan het net.",
                plan=kijk,
                rule="handelen",
                waarde=eraf,
                uren=uren,
            )

    if mag_huis and mag_zon:
        besluit = Besluit(
            NUL,
            reason="Hij houdt de meter op nul: overschot gaat erin, wat het huis vraagt komt eruit.",
            plan=kijk, rule="nul", waarde=eraf, uren=uren,
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
        )
    else:
        besluit = Besluit(
            STANDBY,
            reason=(
                "Terugleveren brengt nu evenveel op als stroom kost, dus opslaan kost alleen het verlies in de batterij."
                if terug is not None and terug >= koop - PRICE_MARGIN else
                "Nu laden of ontladen levert niets op, dus hij staat stil."
            ),
            plan=kijk, rule="standby", waarde=eraf, uren=uren,
        )
    return _met_paal(besluit, paal_laadt, b, nacht, helpt=helpt)


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
    if grens is not None and b is not None and b.soc is not None and b.soc > grens + (0.0 if helpt else AUTO_MARGE):
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
    besluit.reason = (
        "De laadpaal laadt, dus de batterij geeft niets af."
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
        return self._zet(now, wens)

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

    De bewoner van de eerste woning op 21-09-2026: "Elke consument wil weten
    hoelang het duurt voor zijn accu terugverdiend is. Dat doet nog geen enkele
    integratie."
    """
    if koop is None:
        return None

    def rekening(watt: float) -> float:
        prijs = koop if watt >= 0 else (terug or 0.0)
        return watt / 1000.0 * prijs * seconden / 3600.0

    return rekening(net_w - batterij_w) - rekening(net_w)


# Vanaf hoeveel gemeten dagen de coach een datum noemt. Vier volle weken, zodat
# elke weekdag even vaak meetelt. Eerder is het een gok met een datum erop.
TERUGVERDIEN_MIN_DAGEN = 28
# Over hoeveel dagen het tempo gemeten wordt: een jaar, zodat zomer en winter
# er allebei in zitten zodra ze er zijn.
TERUGVERDIEN_VENSTER = 365


def terugverdiend(
    per_dag: dict[str, float], aankoop: float | None, vandaag: datetime
) -> dict:
    """Hoeveel er van de aankoopprijs terug is, en wanneer de rest.

    De datum rust op het tempo van de gemeten dagen en zegt dat erbij. Een
    batterij verdient in juli iets anders dan in december, dus wie in de zomer
    begint krijgt een te vroege datum en wie in de winter begint een te late;
    na een jaar klopt hij. Wat de batterij verdiende voordat de coach erbij
    kwam is niet bekend en wordt niet geschat.
    """
    totaal = sum(per_dag.values())
    dagen = sorted(per_dag)[-TERUGVERDIEN_VENSTER:]
    uit = {
        "earned": round(totaal, 2), "days": len(per_dag), "price": aankoop, "date": None,
        "per_day": None, "min_days": TERUGVERDIEN_MIN_DAGEN,
    }
    if not dagen:
        return uit
    tempo = sum(per_dag[d] for d in dagen) / len(dagen)
    uit["per_day"] = round(tempo, 3)
    if aankoop is None or aankoop <= 0:
        return uit
    rest = aankoop - totaal
    if rest <= 0:
        uit["date"] = "klaar"
        return uit
    if len(dagen) >= TERUGVERDIEN_MIN_DAGEN and tempo > 0:
        uit["date"] = (vandaag + timedelta(days=rest / tempo)).date().isoformat()
    return uit


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
