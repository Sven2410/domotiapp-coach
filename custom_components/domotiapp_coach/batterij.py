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

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from math import sqrt

from .planner import (
    PRICE_MARGIN,
    SCHIJF_MINIMUM,
    Forecast,
    Tariff,
    _clock,
    _echt,
    _euro,
    _gemiddeld_bekend,
    _klokuren,
    _kw,
    _kwh,
    _vlakke_blokken,
    echt_verder,
    echte_duur,
    echte_uren,
    in_evening_peak,
    zon_tussen,
    piek_dicht,
    price_now,
)
from .taal import t


def nt(zin: str) -> str:
    """Een zin in een tabel: blijft Nederlands, vertaald wordt hij waar hij getoond
    wordt (`t(zin)`). Zoals `nt` in i18n.js; tools/vertaalcheck.py ziet hem zo."""
    return zin


# --- De standen ---------------------------------------------------------------
# De namen zijn die van de bewoner van de eerste woning, 21-09-2026: "alleen
# zonneladen" en "standby" zijn zijn woorden, en "handelen" ook.
#
# De namen blijven Nederlands (de tijdlijn in Historie leest er oude meldingen
# mee); `stand_naam` geeft ze in de taal van nu.
NUL = "nul"                  # nul op de meter: overschot erin, tekort eruit
ZONNELADEN = "zonneladen"    # alleen zonoverschot erin, er komt niets uit
ONTLADEN = "ontladen"        # het huis voeden, maar geen zon opslaan
NETLADEN = "netladen"        # van het net laden, rustig verdeeld
MAX_LADEN = "max-laden"      # negatieve prijs: vol vermogen, ontladen dicht
HANDELEN = "handelen"        # ontladen naar het net
STANDBY = "standby"          # 0 W

STAND_NAMEN = {
    NUL: nt("Nul op de meter"),
    ZONNELADEN: nt("Alleen zonneladen"),
    ONTLADEN: nt("Alleen ontladen"),
    NETLADEN: nt("Laden van het net"),
    MAX_LADEN: nt("Maximaal laden"),
    HANDELEN: nt("Handelen"),
    STANDBY: nt("Standby"),
}


def stand_naam(stand: str) -> str:
    """De naam van een stand in de taal van nu ("Nul op de meter", "Zero at the meter")."""
    return t(STAND_NAMEN.get(stand, stand))

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
# Boven hoeveel watt laden een beurt van het net is die al loopt (v0.160.0); zie `_bijladen_loont`.
LOOPT_W = 100.0
# Hoeveel procent boven `auto_grens` de batterij moet zitten om opnieuw te
# beginnen met de auto helpen; stoppen doet hij op de grens zelf. De grens zakt
# 's nachts vanzelf (er is minder nacht over), en met een procent speling hielp
# hij in het virtuele huis zeventien keer een paar minuten (34 wissels).
AUTO_MARGE = 5.0


@dataclass
class Rendement:
    """Het rendement per richting en per vermogen, gemeten (v0.142.0).

    Per richting punten (kW aan de accukant, rendement), oplopend in vermogen;
    zie `Rendementmeter`, die ze leert. Tussen twee punten recht getrokken,
    buiten de punten het dichtstbijzijnde: verder dan de metingen reiken neemt
    de coach niets aan. In de eerste woning op 19-10-2026, tien dagen: laden
    92% boven 1,2 kW; ontladen 88% bij 0,6 kW, 93% bij 0,9 kW en 96% bij
    2,6 kW. 's Nachts nul op de meter is dus duurder dan de 83% heen en terug
    laat zien.

    Laden is wat er van een kWh aan de wisselstroomkant in de cellen komt,
    ontladen wat er van een kWh uit de cellen aan de wisselstroomkant
    overblijft.
    """

    laden: list[tuple[float, float]]
    ontladen: list[tuple[float, float]]
    # Per richting over alles wat er gemeten is, gewogen naar de energie. Voor
    # wat geen vermogen kent: wat een kWh erin straks waard is, de nachtbalans.
    gem_laden: float
    gem_ontladen: float

    @property
    def rte(self) -> float:
        return self.gem_laden * self.gem_ontladen


def _op_vermogen(punten: list[tuple[float, float]], kw: float) -> float:
    if kw <= punten[0][0]:
        return punten[0][1]
    for (k0, e0), (k1, e1) in zip(punten, punten[1:]):
        if kw <= k1:
            return e0 + (e1 - e0) * (kw - k0) / (k1 - k0) if k1 > k0 else e1
    return punten[-1][1]


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
    # Het rendement per richting en per vermogen, als dat gemeten is (v0.142.0).
    # Dan is `rte` wat daar heen en terug uit komt. Zie `eta_in`.
    rendement: Rendement | None = None
    # Of ontladen naar het net mag. Standaard uit.
    handelen: bool = False
    # Handelen in twee (v0.141.0). De eigenaar op 19-10-2026: "Batterij mag laden van
    # het net tijdens lage tarieven / Batterij mag ontladen naar het net tijdens hoge
    # tarieven." Van het net laden mag standaard, zoals altijd. En per richting een
    # grens in de all-in prijs, of None: dan bepaalt de coach het zelf. Zie
    # `_mag_netladen` en `_mag_handelen`.
    net_laden: bool = True
    net_laden_onder: float | None = None
    handelen_boven: float | None = None
    # De afschrijving (v0.146.0): wat elke kWh die uit de cellen komt aan slijtage
    # kost, in euro. De eigenaar op 22-10-2026: "Nu rekent coach alleen met het
    # rendementsverlies. Maar ook afschrijving moet meegerekend worden om de minimale
    # prijsspread te bepalen." Nul is alleen het verlies, zoals tot dan. Zie `_blok_kosten`.
    slijtage: float = 0.0
    # Hoeveel een laadbeurt van het net minstens moet opleveren, in euro (v0.160.0).
    # De eigenaar op 26-10-2026, na een ochtend waarop de verwachting net niet uitkwam: bijladen
    # pas als het verwacht meer dan € 0,05 oplevert. Een keuze, geen meting. Nul is geen grens;
    # de coach geeft `BIJLADEN_MIN_WINST` mee als de bewoner niets invult. Zie `_bijladen_loont`.
    min_winst: float = 0.0
    # Tot wanneer hij niet van het net laadt omdat die laadbeurt te weinig oplevert, of None.
    # Zet `_bijladen_loont`, niet de coach.
    net_laden_vanaf: datetime | None = None
    # Tot wanneer hij niet aan het net levert omdat die beurt te weinig oplevert, of None
    # (v0.162.0). Zet `_handelen_loont`, niet de coach.
    handelen_vanaf: datetime | None = None
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
    # Of hij met `zelf_nul` toch kan vasthouden: een Growatt in een vak van zijn laadschema
    # met de stopgrens op de accustand ontlaadt niet (v0.155.0). De som mag dan stilstaan
    # als het huis stroom vraagt; zie `_zelf_toegestaan` en `growatt_schema`.
    kan_vasthouden: bool = False
    # Of hij met `zelf_nul` vol mag blijven staan (v0.158.0): een batterij met een stuurgetal
    # die de coach overneemt en op 0 W zet. Alleen op het bovenste punt van de som, en alleen
    # zolang de volle beurt open staat (`_vol_open`). Zonder dit was vol met een huis dat vraagt altijd
    # ontladen, en dan een kwartier later weer bijladen: in een klantwoning op 25-10-2026, de dag
    # van de volle beurt, van 14:30 tot 16:00 acht keer om en om nul en laden, en elke keer de
    # Anker naar zijn eigen stand en terug. Zie `_zelf_toegestaan`.
    vol_vasthouden: bool = False
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


def _wortel(rte: float | None) -> float:
    """Eén richting uit het rendement heen en terug; zonder rendement geen verlies."""
    return sqrt(min(max(rte, 0.05), 1.0)) if rte else 1.0


def eta_in(b: Batterij, kw: float | None = None) -> float:
    """Wat er van een kWh aan de wisselstroomkant in de cellen komt.

    Bij `kw` aan de accukant als het rendement per vermogen gemeten is
    (v0.142.0), anders gemiddeld; zonder dat de helft van het verlies heen en
    terug, zoals tot dan overal.
    """
    r = b.rendement
    if r is None:
        return _wortel(b.rte)
    return r.gem_laden if kw is None else _op_vermogen(r.laden, kw)


def eta_uit(b: Batterij, kw: float | None = None) -> float:
    """Wat er van een kWh uit de cellen aan de wisselstroomkant overblijft. Zie `eta_in`."""
    r = b.rendement
    if r is None:
        return _wortel(b.rte)
    return r.gem_ontladen if kw is None else _op_vermogen(r.ontladen, kw)


def _ac(b: Batterij, e: float, naar: float, deel: float) -> float:
    """Wat de batterij aan de wisselstroomkant doet als de inhoud in `deel` uur van `e` naar `naar` gaat.

    In kWh, laden positief. Het vermogen is gelijk verdeeld over het blok.
    """
    d = naar - e
    if d >= 0:
        return d / eta_in(b, d / deel if deel > 0 else None)
    return d * eta_uit(b, -d / deel if deel > 0 else None)


def _cel_in(b: Batterij, ac: float, deel: float) -> float:
    """Hoeveel er in de cellen komt van `ac` kWh laden in `deel` uur; het omgekeerde van `_ac`.

    Het rendement hangt af van het vermogen aan de accukant, en dat hangt weer
    af van het rendement; na een paar rondes ligt het vast (het rendement
    verandert maar een paar procent over het hele bereik).
    """
    eta = eta_in(b)
    if b.rendement is not None and deel > 0:
        for _ in range(4):
            eta = eta_in(b, ac * eta / deel)
    return ac * eta


def _cel_uit(b: Batterij, ac: float, deel: float) -> float:
    """Hoeveel er uit de cellen moet voor `ac` kWh ontladen in `deel` uur. Zie `_cel_in`."""
    eta = eta_uit(b)
    if b.rendement is not None and deel > 0:
        for _ in range(4):
            eta = eta_uit(b, ac / eta / deel)
    return ac / eta


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
    # Of de som hem hier vasthoudt (v0.155.0): het huis vraagt, er zit iets in, en toch geeft
    # hij niets. Stilstaan omdat het huis niets vraagt of omdat hij leeg is, is iets anders.
    vast: bool = False


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
    # Wat bijladen van het net had opgeleverd als dat onder de grens van de bewoner bleef
    # (`min_winst`, v0.160.0), in euro; anders None. Voor de nachtzin.
    bijladen_winst: float | None = None
    # Wat de eerstvolgende beurt aan het net leveren had opgeleverd als dat onder de grens van
    # de bewoner bleef (`min_winst`, v0.162.0), in euro; anders None. Voor de kaart.
    handelen_winst: float | None = None
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
    if laatst_vol is not None and echte_duur(laatst_vol, now) < VOL_NA:
        return None
    if now.weekday() != dag:
        return None
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def _netto_huis_kwh(forecast: Forecast, rij: dict, deel: float, van: datetime | None = None) -> float:
    """Wat het huis in dit blok van het net vraagt als er geen batterij was.

    Negatief is overschot. Het huisverbruik min de zon, de zon bijgesteld met
    wat het dak vandaag waarmaakte; zie `overschot_kwh` in planner.py, dat
    dezelfde som maakt maar bij nul afkapt omdat een paal niets met een tekort
    kan. Sinds v0.160.0 loopt de zon binnen het uur op of af (`zon_tussen`): een
    kwartier aan het begin van de dag krijgt minder dan een kwart van het uur.
    """
    uur = rij["start"].replace(minute=0, second=0, microsecond=0)
    zon = zon_tussen(forecast, van or rij["start"], rij["end"])
    return forecast.house_kwh.get(uur.hour, 0.0) * deel - zon


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
    # Of de avondpiek dicht is voor het net (vast contract). Zie `piek_dicht`.
    piek: bool = True
    # Per blok de inhoud waaronder hij aan het eind niet aan het net levert, met
    # de nachtstrategie aan (v0.133.1); None zonder. Zie `_nacht_vloer`.
    vloer: list[float] | None = None
    # Per blok of er daarna nog een duurder blok komt (v0.155.0): alleen dan kan
    # vasthouden lonen. Zie `_duurder_later`.
    duurder: list[bool] | None = None
    # Wat de hele tijd kost vanaf nu, per roosterpunt (v0.160.0). Zie `_bijladen_loont`.
    begin: list[float] | None = None


def _duurder_later(blokken: list[dict]) -> list[bool]:
    """Per blok of er later een blok komt dat meer kost dan dit, boven de marge.

    Vasthouden mag alleen in zo'n blok (v0.155.0). Bij gelijke kosten kiest de som het
    kleinste gebaar, en dat is stilstaan: in het virtuele huis (`growatt-vasthouden`) hield
    hij de batterij zo de hele dure dag vast, omdat morgen even duur was, terwijl het huis
    van het net haalde. Dat kostte € 1,93 tegen € 1,82 zonder vasthouden.
    """
    uit, hoogste = [], float("-inf")
    for rij in reversed(blokken):
        uit.append(hoogste > rij["price"] + PRICE_MARGIN)
        hoogste = max(hoogste, rij["price"])
    return list(reversed(uit))


def _mag_netladen(b: Batterij, rij: dict) -> bool:
    """Of de batterij in dit blok van het net mag laden (v0.141.0).

    Met het vinkje aan, en met een grens alleen als de all-in prijs van het blok
    eronder ligt. Een bewoner op 21-10-2026: hij mag wel van het net laden "als de
    prijs bijv. <15 cent is". Zon opslaan gaat hier niet over; dat mag altijd.
    """
    if not b.net_laden:
        return False
    if b.net_laden_vanaf is not None and _echt(rij["start"]) < _echt(b.net_laden_vanaf):
        return False
    return b.net_laden_onder is None or rij["price"] < b.net_laden_onder


def _mag_handelen(b: Batterij, rij: dict) -> bool:
    """Of de batterij in dit blok aan het net mag leveren.

    Met een grens (v0.141.0) alleen als de all-in prijs van het blok erboven ligt;
    de eigenaar op 21-10-2026: "zou dan in alle gevallen met de all-in energieprijs
    rekenen". Zonder grens bepaalt de som het.

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
    if b.handelen_vanaf is not None and _echt(rij["start"]) < _echt(b.handelen_vanaf):
        return False
    return (
        b.handelen and rij.get("feed_in") is not None
        and (b.handelen_boven is None or rij["price"] > b.handelen_boven)
    )


# Wat de kaart zegt als handelen aanstaat en niet kan (v0.128.2). Het paneel
# zegt het ook, bij het vinkje (`HANDELEN_KAN_NIET` in voorkeur-velden.js) en
# bij het marktveld van Contract. Nederlands, zoals de tabel hierboven; op de
# kaart `t(HANDELEN_KAN_NIET)`.
HANDELEN_KAN_NIET = nt(
    "Handelen staat aan, maar kan nu niet: de coach kent je terugleverprijs niet. "
    "Daarvoor is bij Contract een marktprijssensor nodig, of salderen."
)


def handelen_kan_niet(b: Batterij, prijzen: list[dict], now: datetime) -> bool:
    """Of handelen aanstaat terwijl geen enkel komend blok een terugleverprijs heeft.

    Dan laat `_mag_handelen` nooit iets naar het net, en tot v0.128.2 zei niets
    op het scherm dat. De bewoner van de eerste woning op 18-10-2026, met de
    batterij op 95%, "7,1 kWh over" tot morgenvroeg en een avond boven de 45
    cent: "Het enige waar ik op dit moment nog niet echt tevreden over ben is
    het handelen (of eigenlijk het ontbreken ervan)." Handelen stond aan, maar
    in beide prijsvelden stond dezelfde all-in sensor en salderen stond uit,
    dus in alle 50 blokken was `feed_in` None.

    Een vast contract heeft altijd een terugleverprijs (`_vlakke_blokken`), en
    zonder prijzen staat er al een andere reden op de kaart.
    """
    if not b.handelen:
        return False
    komend = [rij for rij in prijzen if rij["end"] > now]
    return bool(komend) and all(rij.get("feed_in") is None for rij in komend)


def _mogelijk(
    e: float, rij: dict, deel: float, huis: float, b: Batterij, som_laag: float,
    hoog: float, piek: bool = True, vloer: float | None = None,
) -> tuple[float, float]:
    """Tussen welke inhoud de batterij aan het eind van dit blok kan zitten.

    `vloer` is de inhoud waaronder hij niet aan het net levert (v0.133.1): het
    huis voeden mag eronder, handelen niet. Zie `_nacht_vloer`.
    """
    op = min(hoog, e + _cel_in(b, b.max_charge_w / 1000.0 * deel, deel))
    if (piek and in_evening_peak(rij["start"])) or not _mag_netladen(b, rij):
        # Eis 4: in de avondpiek komt er niets van het net bij. Zon mag. En ook
        # niet als de bewoner het hier niet wil (v0.141.0).
        op = min(op, e + _cel_in(b, max(0.0, -huis), deel))
    neer_w = b.max_discharge_w / 1000.0 * deel
    handelt = _mag_handelen(b, rij)
    if not handelt:
        # Zonder handelen gaat er niets naar het net: hooguit wat het huis vraagt.
        neer_w = min(neer_w, max(0.0, huis))
    neer = max(min(som_laag, e), e - _cel_uit(b, neer_w, deel))
    if handelt and vloer is not None:
        # Aan het net leveren alleen tot de vloer; het huis voeden mag verder.
        alleen_huis = max(min(som_laag, e), e - _cel_uit(b, min(neer_w, max(0.0, huis)), deel))
        neer = min(alleen_huis, max(neer, min(e, vloer)))
    return max(op, e), min(neer, e)


def _zelf_toegestaan(
    kandidaten: set[float], e: float, deel: float, huis: float, b: Batterij,
    som_laag: float, hoog: float, stap: float = 0.0, handelen: bool | None = None,
    vasthouden: bool = False, vol_vanaf: float | None = None, vol_open: bool = False,
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
        nul = max(min(som_laag, e), e - _cel_uit(b, min(b.max_discharge_w / 1000.0 * deel, huis), deel))
    elif huis < 0:
        nul = min(max(hoog, e), e + _cel_in(b, min(b.max_charge_w / 1000.0 * deel, -huis), deel))
    else:
        nul = e
    uit = {nul}
    # Vasthouden (v0.155.0): de eigenaar op 23-10-2026, "pas als het dure uur in gaat dan pas
    # ontladen". Alleen als het huis vraagt; bij zon over is stilstaan zon weggeven.
    if b.kan_vasthouden and vasthouden and huis > 0:
        uit.add(e)
    # Vol blijven (v0.158.0): hetzelfde voor een batterij die op het bovenste punt van de som
    # staat (`vol_vanaf`, een stap onder de grens) terwijl de volle beurt nog open is. Daar kan
    # van het net laden niets meer toevoegen, dus zonder dit bleef alleen ontladen over, en
    # daarna weer bijladen voor de beurt. Niet voor elk duurder blok verderop, zoals bij een
    # Growatt: dan werd bovenin staan elk middaguur waard, laadde hij in batterij-kwartier-zelf
    # 's middags vol en hield hij dat vast door de dure avond (€ 6,62 tegen € 2,94 zonder batterij).
    elif b.vol_vasthouden and vol_open and huis > 0 and vol_vanaf is not None and e >= vol_vanaf - 1e-9:
        uit.add(e)
    boven, onder = max(e, nul), min(e, nul)
    # Wat het blok in tijd en vermogen toelaat, zonder de grenzen van de accustand.
    op_blok = e + _cel_in(b, b.max_charge_w / 1000.0 * deel, deel)
    neer_blok = e - _cel_uit(b, b.max_discharge_w / 1000.0 * deel, deel)
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


def _blok_kosten(e: float, naar: float, huis: float, rij: dict, b: Batterij, deel: float) -> float:
    """Wat dit blok kost als de inhoud van `e` naar `naar` gaat.

    Met het rendement bij het vermogen van dat blok (v0.142.0): 's nachts het
    huis voeden op een paar honderd watt kost meer verlies dan op twee kilowatt
    aan het net leveren.
    """
    # Met de afschrijving per kWh die uit de cellen komt (v0.146.0): laden en later
    # ontladen loont pas als het verschil in prijs het verlies én de slijtage dekt.
    return _kosten(huis + _ac(b, e, naar, deel), rij) + b.slijtage * max(0.0, e - naar)


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
        # Echte uren (`echte_uren` in planner.py): het blok van 01:00 tot 03:00 op
        # 28-03-2027 duurt er een, dat van 02:00 tot 03:00 op 25-10-2026 twee.
        van = max(rij["start"], now, key=_echt)
        deel = max(0.0, echte_uren(van, rij["end"]))
        delen.append(deel)
        huis.append(_netto_huis_kwh(forecast, rij, deel, van))

    vloer = _nacht_vloer(blokken, forecast, b, bodem)
    duurder = _duurder_later(blokken)

    eind_prijs = _gemiddeld_bekend(blokken) or 0.0
    # Wat er aan het eind nog in zit, min de slijtage die het ontladen ervan kost.
    volgende = [-(max(0.0, e - bodem)) * max(0.0, eta_uit(b) * eind_prijs - b.slijtage) for e in rooster]

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
            op, neer = _mogelijk(e, rij, deel, h, b, bodem, hoog, piek, None if vloer is None else vloer[k])
            kandidaten = {e, op, neer}
            if h > 0:
                kandidaten.add(max(neer, e - _cel_uit(b, h, deel)))
            elif h < 0:
                kandidaten.add(min(op, e + _cel_in(b, -h, deel)))
            eerste = int((neer - laag) / stap) + 1
            laatste = int((op - laag) / stap)
            for i in range(max(0, eerste), min(STAPPEN, laatste) + 1):
                kandidaten.add(rooster[i])
            kandidaten = _zelf_toegestaan(
                kandidaten, e, deel, h, b, bodem, hoog, 0.0 if k == 0 and _loopt_al(b, rij) else stap,
                handelen=_mag_handelen(b, rij), vasthouden=duurder[k], vol_vanaf=hoog - stap,
                vol_open=_vol_open(b, rij),
            )
            begin.append(
                min(
                    _blok_kosten(e, naar, h, rij, b, deel) + _tussen(volgende, stap, laag, naar)
                    for naar in kandidaten
                )
            )
        volgende = begin

    return _Som(blokken, delen, huis, na, laag, hoog, stap, piek, vloer, duurder, volgende)


def _vol_open(b: Batterij, rij: dict) -> bool:
    """Of de volle beurt in dit blok nog open staat: er is een `vol_voor`, en die komt nog."""
    return b.vol_voor is not None and rij["start"] < b.vol_voor


def _bijladen_loont(
    now: datetime, blokken: list[dict], forecast: Forecast, b: Batterij, dicht: bool, som: _Som
) -> tuple[Batterij, _Som, float | None]:
    """Laat de som de eerste laadbeurt van het net weg als die minder oplevert dan `min_winst` (v0.160.0).

    Per laadbeurt en niet per kwartier, anders valt elke stap eronder. De beurt begint bij het
    eerste blok waarin het plan van het net laadt en loopt tot het plan de batterij weer laat
    leveren: zolang hij niets teruggeeft kan wat hij in het ene kwartier niet laadt in een ander
    erbij, en dan lijkt elk stuk weinig waard. Een tweede beurt daarna, zoals een aan het eind
    van de bekende prijzen, toetst hij als hij aan de beurt is: in proef 56 haalde een ochtend
    van € 0,026 samen met zo'n beurt de grens anders wel.

    De som zonder laden van het net tot het eind van de beurt naast die met, vanaf de accustand
    van nu. Levert het verschil minder op dan de grens, dan rekent hij verder met die beperking,
    en geeft hij terug hoeveel het had opgeleverd, voor de kaart.

    Een beurt die al loopt maakt hij af: aan het eind levert de rest altijd weinig op. Dat is de
    vorige ronde van het net laden, of nu laden zonder zon over. Een Growatt laadt in zijn vak
    vanaf het begin, ook als het plan dat later in het vak zet; in `growatt-bihorario` zakte de
    rest om 04:10 onder de grens, en daarna schreef hij elk half uur een nieuw schema. Laden om
    terug te leveren is ook laden van het net, dus de grens geldt daar evengoed.
    """
    if b.min_winst <= 0 or not b.net_laden or b.vorige_stand == NETLADEN or som.begin is None:
        return b, som, None
    uren = _vooruit(som, b)
    eerste = next((i for i, u in enumerate(uren) if u.stand == NETLADEN and u.net_kwh > 0.005), None)
    if eerste is None:
        return b, som, None
    if (b.power_w or 0.0) > LOOPT_W and som.huis and som.huis[0] > 0:
        return b, som, None
    eind = next((u.start for u in uren[eerste + 1:] if u.kwh < -0.005), uren[-1].end)
    zonder_b = replace(b, net_laden_vanaf=eind)
    zonder = _waarde_vooruit(now, blokken, forecast, zonder_b, piek=dicht)
    if zonder is None or zonder.begin is None:
        return b, som, None
    e = (b.soc or 0.0) / 100.0 * (b.capacity_kwh or 0.0)
    winst = _tussen(zonder.begin, zonder.stap, zonder.laag, e) - _tussen(som.begin, som.stap, som.laag, e)
    if winst >= b.min_winst:
        return b, som, None
    return zonder_b, zonder, max(0.0, winst)


def _handelen_loont(
    now: datetime, blokken: list[dict], forecast: Forecast, b: Batterij, dicht: bool, som: _Som
) -> tuple[Batterij, _Som, float | None]:
    """Laat de som de eerste beurt aan het net leveren weg als die minder oplevert dan `min_winst` (v0.162.0).

    De eigenaar op 26-10-2026: "Handelen moet alleen wat opleveren als alle kosten er
    afgehaald zijn zoals belasting, rendement etc, dus onder aan de streep moet het geld
    opleveren en niet gaan pendelen." De som rekent al met de all-in prijs, de
    terugleverprijs na kosten, het rendement bij elk vermogen en de slijtage; wat hij
    daarbovenop vraagt is dat een beurt de moeite waard is. Dezelfde grens als bij
    bijladen (`_bijladen_loont`), en op dezelfde manier: per beurt, niet per kwartier.

    De beurt begint bij het eerste blok waarin het plan aan het net levert en loopt tot de
    batterij weer geladen wordt: zolang er niets bij komt kan wat hij in het ene blok niet
    levert in een ander eruit, en dan lijkt elk stuk weinig waard. De som zonder leveren
    tot het eind van de beurt naast die met, vanaf de accustand van nu; onder de grens
    rekent hij verder zonder, en geeft hij terug wat het had opgeleverd.

    Een beurt die al loopt (vorige ronde handelen) maakt hij af: aan het eind levert de
    rest altijd weinig op, en zonder dat zou hij aan en uit gaan.
    """
    if b.min_winst <= 0 or not b.handelen or b.vorige_stand == HANDELEN or som.begin is None:
        return b, som, None
    uren = _vooruit(som, b)
    eerste = next((i for i, u in enumerate(uren) if u.stand == HANDELEN and u.net_kwh < -0.005), None)
    if eerste is None:
        return b, som, None
    eind = next((u.start for u in uren[eerste + 1:] if u.kwh > 0.005), uren[-1].end)
    zonder_b = replace(b, handelen_vanaf=eind)
    zonder = _waarde_vooruit(now, blokken, forecast, zonder_b, piek=dicht)
    if zonder is None or zonder.begin is None:
        return b, som, None
    e = (b.soc or 0.0) / 100.0 * (b.capacity_kwh or 0.0)
    winst = _tussen(zonder.begin, zonder.stap, zonder.laag, e) - _tussen(som.begin, som.stap, som.laag, e)
    if winst >= b.min_winst:
        return b, som, None
    return zonder_b, zonder, max(0.0, winst)


def _beste_stap(som: _Som, k: int, e: float, b: Batterij) -> float:
    """Naar welke inhoud de batterij in blok k het beste kan gaan."""
    rij, deel, h = som.blokken[k], som.delen[k], som.huis[k]
    bodem = b.bodem / 100.0 * (b.capacity_kwh or 0.0)
    op, neer = _mogelijk(e, rij, deel, h, b, bodem, som.hoog, som.piek,
                         None if som.vloer is None else som.vloer[k])
    kandidaten = {e, op, neer}
    if h > 0:
        kandidaten.add(max(neer, e - _cel_uit(b, h, deel)))
    elif h < 0:
        kandidaten.add(min(op, e + _cel_in(b, -h, deel)))
    i = int((neer - som.laag) / som.stap) + 1
    while i <= STAPPEN and som.laag + i * som.stap <= op:
        kandidaten.add(som.laag + i * som.stap)
        i += 1
    kandidaten = _zelf_toegestaan(
        kandidaten, e, deel, h, b, bodem, som.hoog, 0.0 if k == 0 and _loopt_al(b, rij) else som.stap,
        handelen=_mag_handelen(b, rij), vasthouden=bool(som.duurder and som.duurder[k]),
        vol_vanaf=som.hoog - som.stap, vol_open=_vol_open(b, rij),
    )
    # Bij gelijke kosten wint niets doen, en daarna het kleinste gebaar: een
    # batterij die zonder reden beweegt slijt voor niets.
    return min(
        kandidaten,
        key=lambda naar: (
            round(
                _blok_kosten(e, naar, h, rij, b, deel)
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
        ac = _ac(b, e, naar, som.delen[k])
        h = som.huis[k]
        net = max(0.0, ac - max(0.0, -h)) if ac > 0 else min(0.0, ac + max(0.0, h))
        stand = _stand_van(ac, h)
        uit.append(
            Uur(
                max(rij["start"], echt_verder(rij["end"], -timedelta(hours=som.delen[k])), key=_echt),
                rij["end"],
                stand,
                ac,
                net,
                naar / (b.capacity_kwh or 1.0) * 100.0,
                rij["price"],
                # Alleen in een goedkoper blok dan wat er nog komt: op de dure prijs doet hij
                # gewoon nul op de meter (de eigenaar op 23-10-2026, over bi-horário).
                vast=stand == STANDBY and h > 0.005 and (
                    b.kan_vasthouden and bool(som.duurder and som.duurder[k])
                    and e > b.bodem / 100.0 * (b.capacity_kwh or 0.0) + 0.01
                    or b.vol_vasthouden and _vol_open(b, rij) and e >= som.hoog - som.stap - 1e-9
                ),
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
        tijd += echte_uren(uur.start, uur.end)
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


def _nacht_uren(now: datetime, forecast: Forecast) -> list[tuple[float, float, float]]:
    """Per uur tot morgenvroeg: (zon, huis) in kWh, het lopende uur naar rato, en hoeveel uur dat is."""
    uren = []
    eind = _morgenvroeg(now)
    # Per uur op de klok, met de echte duur (`_klokuren` in planner.py): de nacht van
    # de zomertijd heeft een uur minder huisverbruik, die van de wintertijd een meer.
    for uur, volgend in _klokuren(now, eind):
        deel = echte_uren(max(uur, now, key=_echt), volgend)
        opbrengst = max(0.0, forecast.solar_kwh.get(uur, 0.0))
        if forecast.solar_factor is not None and uur.date() == forecast.solar_day:
            opbrengst *= forecast.solar_factor
        uren.append((opbrengst * deel, forecast.house_kwh.get(uur.hour, 0.0) * deel, deel))
    return uren


def nachtbalans(now: datetime, forecast: Forecast, b: Batterij) -> tuple[float, float, float] | None:
    """Zon, huis en wat er bruikbaar in de batterij zit, tot morgenvroeg, in kWh.

    None als er geen huisprofiel of geen accustand is. De zon van de uren die
    komen wordt bijgesteld met wat het dak vandaag waarmaakte, net als overal.
    """
    if not forecast.house_kwh or b.inhoud_kwh is None:
        return None
    uren = _nacht_uren(now, forecast)
    zon = sum(z for z, _h, _d in uren)
    huis = sum(h for _z, h, _d in uren)
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
    net; wat het huis vraagt komt eruit met het rendement van het ontladen, op
    het vermogen van dat uur (v0.142.0; tot dan het hele verlies heen en terug), tot de ondergrens;
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
    tekort = weg = 0.0
    for zon, huis, deel in _nacht_uren(now, forecast):
        netto = zon - huis
        if netto >= 0:
            erbij = min(netto, max(0.0, ruimte - inhoud))
            inhoud += erbij
            weg += netto - erbij
        else:
            nodig = -netto
            eta = nodig / _cel_uit(b, nodig, deel)
            kan = inhoud * eta
            if kan >= nodig:
                inhoud -= nodig / eta
            else:
                tekort += nodig - kan
                inhoud = 0.0
    return inhoud, tekort, weg


def _nacht_nodig(t: datetime, forecast: Forecast, b: Batterij) -> float:
    """Wat er op `t` boven de ondergrens in moet zitten om zonder net morgenvroeg te halen.

    Dezelfde som als `nachtverloop`, achterstevoren: van morgenvroeg terug naar
    `t`, per uur wat het huis vraagt min de zon, met het verlies zoals daar.
    Zon in een uur maakt het tekort van de uren erna kleiner.
    """
    nodig = 0.0
    for zon, huis, deel in reversed(_nacht_uren(t, forecast)):
        netto = zon - huis
        nodig = nodig + _cel_uit(b, -netto, deel) if netto < 0 else max(0.0, nodig - netto)
    return nodig


def _nacht_vloer(blokken: list[dict], forecast: Forecast, b: Batterij, bodem: float) -> list[float] | None:
    """Per blok de inhoud waaronder de som aan het eind niet aan het net levert (v0.133.1).

    De bewoner van de eerste woning op 19-10-2026, met de nachtstrategie aan,
    een volle batterij en de prijzen tot middernacht: "Ondanks dat handelen aan
    staat, zou ik verwachten dat ie om 19u nog zo'n 20 a 30% over heeft om de
    nacht door te komen." Het besluit van het moment hield zich daar al aan
    ("handelen alleen met wat er boven de nacht uitkomt", `plan_batterij`), maar
    de som niet: die gaf wat er om middernacht nog in zat de gemiddelde prijs
    als waarde, verkocht de rest op de dure avond, en zo stond er in het plan en
    in de vooruitblik 5% om 23:00. Nu heeft de som dezelfde grens, zodat het
    plan laat zien wat hij doet.

    None zonder nachtstrategie, zonder handelen of zonder huisprofiel.
    """
    if not b.nacht or not b.handelen or not forecast.house_kwh:
        return None
    return [bodem + _nacht_nodig(rij["end"], forecast, b) for rij in blokken]


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
    return inhoud * eta_uit(b)


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
    uren: list[Uur] | None = None, conclusie: bool = True, inkoop: float | None = None,
    te_weinig: float | None = None,
) -> str:
    """Twee zinnen: zon, huis en batterij tot morgenvroeg, en de conclusie.

    Zonder `conclusie` alleen de eerste: bij een Growatt komt die uit zijn schema
    (`growatt_besluit`, v0.156.0).

    De bewoner van de eerste woning liet op 21-09-2026 zien wat hij van zijn
    oude sturing het meest miste als het weg zou zijn: een regel die zegt
    waaróm er wel of niet bijgeladen wordt. "Wat is mijn verwacht verbruik
    vandaag? Wat is de verwachte zonopbrengst?" En op 22-09-2026: "Als laatste
    afsluiten met een conclusie: je hebt naar verwachting X kWh overschot in je
    accu, of je hebt X kWh tekort om de nacht te overbruggen."
    """
    som = nachtbalans(now, forecast, b)
    eta = eta_uit(b)
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
    eruit = t(", goed voor {kwh} na het verlies", kwh=_kwh(bruikbaar * eta)) if b.rte and bruikbaar > 0 else ""
    # En zon die er niet meer in past gaat naar het net: dat verklaart waarom
    # de optelsom van zon en batterij meer is dan wat er morgenvroeg over is.
    past_niet = (
        " " + t("Van die zon past {kwh} niet meer in de accu; die gaat naar het net.", kwh=_kwh(weg))
        if weg > 0.05 else ""
    )
    naar_auto = t(", de auto krijgt er {kwh} uit", kwh=_kwh(auto)) if auto > 0.05 else ""
    zin = t(
        "Tot morgenvroeg verwacht hij {zon} zon, het huis vraagt {huis}{auto} en er zit {accu} in de batterij{eruit}.",
        zon=_kwh(zon), huis=_kwh(huis), auto=naar_auto, accu=_kwh(bruikbaar), eruit=eruit,
    ) + past_niet + " "
    if not conclusie:
        return zin.strip()
    if balans >= 0:
        return zin + t("Je houdt naar verwachting {kwh} over in je accu.", kwh=_kwh(balans))
    return (
        zin + t("Je komt naar verwachting {kwh} tekort om de nacht te overbruggen;", kwh=_kwh(-balans)) + " "
        + (_bijladen_zin(now, b, uren or [], -balans, inkoop, te_weinig) if bijladen else t("dat komt van het net."))
    )


def _bijladen_zin(
    now: datetime, b: Batterij, uren: list[Uur], tekort: float, inkoop: float | None = None,
    te_weinig: float | None = None,
) -> str:
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
            return t("dat laadt hij op de goedkoopste momenten van het net bij.")
        return t(
            "hij laadt er {kwh} van op de goedkoopste momenten van het net bij, "
            "de rest komt rechtstreeks van het net.",
            kwh=_kwh(erbij),
        )
    if te_weinig is not None and b.min_winst > 0:
        # De grens van de bewoner (v0.160.0) is dan de reden, en die zegt hij.
        return t(
            "dat komt van het net, want bijladen zou {winst} opleveren, minder dan de ondergrens van {grens}.",
            winst=_euro(te_weinig), grens=_euro(b.min_winst),
        )
    if not nacht or not b.rte:
        return t("hij laadt bij als de stroom goedkoop genoeg is.")
    goedkoopst = min(nacht, key=lambda u: u.price)
    bekend = "" if nacht[-1].end >= eind else " " + t("in de bekende uren")
    if inkoop is None:
        return _minstens_zin(goedkoopst, b, bekend)
    # Sinds v0.159.0 zegt hij waaróm het niet loont. De eigenaar op 25-10-2026 om 21:33, bij een
    # batterij op de vloer, een nacht van € 0,166 en een ochtend van € 0,272: "waarom gaat hij niet
    # laden?" Er stond alleen "minstens € 0,184", en dat naast € 0,272 leest als een fout.
    #
    # Valt het tekort in uren die zelf niet duurder zijn dan bijladen via de batterij, dan is dat de
    # reden. Wat voor het goedkoopste uur valt, haalt bijladen toch niet meer in.
    leeg = [u for u in nacht if u.start >= goedkoopst.start and u.soc <= b.bodem + 0.5 and u.kwh <= 0.005]
    goedkope_nacht = bool(leeg) and all(u.price <= goedkoopst.price / b.rte for u in leeg)
    if not goedkope_nacht and inkoop >= goedkoopst.price - 0.0005:
        return _minstens_zin(goedkoopst, b, bekend)
    # En maakt de zon hem daarna toch vol, dan is wat er 's nachts bij komt morgen niets meer waard.
    vol = next(
        (u for u in uren if u.start >= now and u.stand != NETLADEN and u.kwh > 0.005
         and u.soc >= b.soc_max - VOL_MARGE and u.start.date() <= eind.date()),
        None,
    )
    waarden = dict(kale=_euro(goedkoopst.price), prijs=_euro(goedkoopst.price / b.rte), grens=_euro(inkoop))
    if vol is not None:
        waarden.update(tijd=_clock(vol.end), soc=round(vol.soc))
    if goedkope_nacht:
        if vol is not None:
            return t("dat komt van het net tegen {kale}, goedkoper dan via de batterij ({prijs} met het "
                     "verlies), en om {tijd} is hij op zon vol ({soc}%).", **waarden)
        return t("dat komt van het net tegen {kale}, goedkoper dan via de batterij ({prijs} met het verlies).",
                 **waarden)
    if vol is not None:
        return t("dat komt van het net tegen {kale}, want een kWh erbij loont pas onder {grens}: om {tijd} "
                 "is hij op zon vol ({soc}%).", **waarden)
    return t("dat komt van het net tegen {kale}, want een kWh erbij loont pas onder {grens} (wat hij straks "
             "waard is, min het verlies).", **waarden)


def _minstens_zin(goedkoopst: Uur, b: Batterij, bekend: str) -> str:
    """Wat een kWh via de batterij minstens kost (v0.102.3), als de som er niets naast zet."""
    return t(
        "dat komt van het net, want bijladen kost via de batterij{bekend} minstens "
        "{prijs} per kWh ({kale} om {tijd}, plus het verlies).",
        bekend=bekend, prijs=_euro(goedkoopst.price / b.rte), kale=_euro(goedkoopst.price),
        tijd=_clock(goedkoopst.start),
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
            reason=t("De sturing van deze batterij staat uit."),
            rule="uit",
        )
    if b.soc is None or b.capacity_kwh is None:
        return Besluit(
            STANDBY,
            reason=t("De coach weet niet hoe vol de batterij is, dus hij laat hem stilstaan."),
            plan=t("Zodra de accustand er weer is gaat hij verder."),
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
                reason=t("De prijs van dit uur is niet bekend, dus hij houdt alleen de meter op nul."),
                plan=t("Van het net laden doet hij pas weer als de prijzen er zijn."),
                rule="geen-prijs",
            ),
            paal_laadt, b,
        )

    koop, terug = nu["price"], nu.get("feed_in")

    # Een negatieve prijs gaat voor alles: elk verlies levert dan geld op. Het
    # gaat om wat de bewoner betaalt, met belasting en opslag erin; dat kwam in
    # 2026 een paar keer voor (de eigenaar, 21-09-2026).
    if koop < 0 and not (dicht and in_evening_peak(now)) and b.soc < b.soc_max - VOL_MARGE and _mag_netladen(b, nu):
        return Besluit(
            MAX_LADEN,
            power_w=b.max_charge_w,
            reason=t(
                "Stroom kost nu {prijs} per kWh: je krijgt geld toe. Hij laadt op vol vermogen en geeft niets af.",
                prijs=_euro(koop),
            ),
            plan=t("Zodra de prijs weer boven nul komt rekent hij gewoon verder."),
            rule="negatieve-prijs",
        )

    if b.rte is None:
        # Zonder rendement valt er niets te vergelijken. Wat wel zeker is: als
        # terugleveren evenveel opbrengt als stroom kost, verliest opslaan
        # altijd, hoe goed de batterij ook is.
        if terug is not None and terug >= koop - PRICE_MARGIN and not b.zelf_nul:
            return Besluit(
                STANDBY,
                reason=t("Terugleveren brengt nu evenveel op als stroom kost, dus opslaan kost alleen het verlies in de batterij."),
                rule="salderen",
            )
        if _vlak(blokken):
            # Van het net laden loont hier nooit, wat het rendement ook is; daar
            # hoeft de bewoner dus ook niets voor in te vullen.
            return _met_paal(
                Besluit(
                    NUL,
                    reason=t("Hij houdt de meter op nul: overschot gaat erin, wat het huis vraagt komt eruit."),
                    plan=t("Stroom kost bij je contract elk uur hetzelfde, dus van het net laden levert nooit iets op."),
                    rule="nul",
                ),
                paal_laadt, b,
            )
        return _met_paal(
            Besluit(
                NUL,
                reason=t("Hij houdt de meter op nul. Het rendement van de batterij is nog niet bekend, dus van het net laden doet hij nog niet."),
                plan=t("De coach meet het zelf terwijl hij de batterij laadt en ontlaadt; je kunt het ook invullen bij Apparaten."),
                rule="rendement-onbekend",
            ),
            paal_laadt, b,
        )

    som = _waarde_vooruit(now, blokken, forecast, b, piek=dicht)
    if som is None:
        return _met_paal(
            Besluit(NUL, reason=t("Hij houdt de meter op nul."), rule="nul"), paal_laadt, b
        )
    b, som, te_weinig = _bijladen_loont(now, blokken, forecast, b, dicht, som)
    b, som, handel_te_weinig = _handelen_loont(now, blokken, forecast, b, dicht, som)

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
    auto_weg = auto_ac / eta_uit(b)
    # Onder welke prijs een kWh van het net erbij nu loont: wat hij in de
    # batterij waard is, min het verlies bij het laden. Voor de kaart; de
    # eigenaar op 30-09-2026 bij "Een kWh erin € 0,301, is straks waard" en een
    # nacht van € 0,313: "is het niet goedkoper om iets bij te kopen?" Die
    # € 0,301 is per kWh ín de batterij; naast de prijslijst hoort € 0,259.
    inkoop = None if vol else erbij * eta_in(b)
    kijk = _vooruitkijk_zin(now, forecast, b, auto_ac, bijladen=not _vlak(blokken), uren=uren,
                            conclusie=not b.kan_vasthouden, inkoop=inkoop, te_weinig=te_weinig)
    piek = dicht and in_evening_peak(now)

    # Zon opslaan en het huis voeden: elk tegen wat een kilowattuur in de
    # batterij straks waard is.
    #
    # Bij gelijkspel wint wat je in handen hebt. Op een zonnige dag komt de
    # batterij hoe dan ook vol, en dan is een kilowattuur zon nu opslaan precies
    # evenveel waard als hem straks opslaan; wie dan "niet" kiest rekent op een
    # zon die er nog niet is. Hetzelfde voor het huis voeden.
    # Met het rendement bij het vermogen van dit blok: wat het huis nu vraagt of
    # wat er nu over is (v0.142.0). 's Nachts op 300 W levert een kWh uit de
    # batterij minder op dan het gemiddelde zegt.
    nu_kw = som.huis[0] / som.delen[0] if som.delen and som.delen[0] > 0 else 0.0
    zon_eta = nu_kw < 0 and _cel_in(b, -nu_kw, 1.0) / -nu_kw or eta_in(b)
    huis_eta = nu_kw > 0 and nu_kw / _cel_uit(b, nu_kw, 1.0) or eta_uit(b)
    mag_zon = not vol and (terug is None or terug <= erbij * zon_eta + PRICE_MARGIN)
    mag_huis = not leeg and koop * huis_eta >= eraf - PRICE_MARGIN

    if (b.kan_vasthouden or b.vol_vasthouden) and uren and uren[0].vast and not leeg:
        # Een Growatt die het plan nu vasthoudt (v0.155.0): wat erin zit is straks meer waard. Voor
        # het laden, want dat komt later in het vak, en de bewoner leest wat hij nu doet.
        return Besluit(
            STANDBY,
            reason=t(
                "Hij houdt de batterij vast: wat erin zit is straks meer waard dan nu. Het huis haalt zolang "
                "van het net, tegen {prijs}.",
                prijs=_euro(koop),
            ),
            plan=kijk, rule="vasthouden", waarde=eraf, uren=uren, auto_weg=auto_weg,
        )

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
                hoe = t("Hij maakt het laden van het net af tot {tijd} en geeft tot dan niets af.", tijd=_clock(tot))
            elif rustig and tot:
                hoe = t("Hij laadt van het net op {kw}, rustig verdeeld tot {tijd}.", kw=_kw(vermogen), tijd=_clock(tot))
            else:
                hoe = t("Hij laadt van het net op {kw}.", kw=_kw(vermogen))
            return Besluit(
                NETLADEN,
                power_w=vermogen,
                reason=(
                    t("Stroom kost nu {prijs} en dat is goedkoper dan wat de batterij je straks bespaart.", prijs=_euro(koop))
                    + " " + hoe
                ) if b.vol_voor is None else t(
                    "Vandaag hoort de batterij een keer helemaal vol, voor het balanceren van de cellen. "
                    "Dit zijn daar de goedkoopste uren voor: hij laadt van het net op {kw}.",
                    kw=_kw(vermogen),
                ),
                plan=kijk,
                rule="netladen" if b.vol_voor is None else "volle-beurt",
                waarde=erbij,
                uren=uren,
                auto_weg=auto_weg,
                inkoop_tot=inkoop, bijladen_winst=te_weinig,
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
                reason=t(
                    "Terugleveren brengt nu {prijs} op, meer dan het straks kost om bij te laden. Hij levert aan het net.",
                    prijs=_euro(terug or 0.0),
                ),
                plan=kijk,
                rule="handelen",
                waarde=eraf,
                uren=uren,
                auto_weg=auto_weg,
                inkoop_tot=inkoop, bijladen_winst=te_weinig,
            )

    if b.zelf_nul or (mag_huis and mag_zon):
        # Doet de batterij het zelf, dan is dit wat hij doet: stilstaan, alleen
        # zon opslaan of alleen ontladen kan hij in zijn eigen stand niet.
        besluit = Besluit(
            NUL,
            reason=t("Hij houdt de meter op nul: overschot gaat erin, wat het huis vraagt komt eruit."),
            plan=kijk, rule="nul", waarde=eraf, uren=uren, auto_weg=auto_weg,
        )
    elif mag_zon:
        besluit = Besluit(
            ZONNELADEN,
            reason=(
                t("De batterij is leeg tot aan zijn ondergrens. Zonoverschot gaat er wel in.")
                if leeg else
                t(
                    "Stroom kost nu {prijs}, en wat er in de batterij zit bespaart straks meer. Hij bewaart het; zonoverschot gaat er wel in.",
                    prijs=_euro(koop),
                )
            ),
            plan=kijk, rule="leeg" if leeg else "bewaren", waarde=eraf, uren=uren,
            auto_weg=auto_weg,
        )
    elif mag_huis:
        besluit = Besluit(
            ONTLADEN,
            reason=(
                t("De batterij is vol. Wat het huis vraagt komt eruit.")
                if vol else
                t(
                    "Terugleveren brengt nu {prijs} op, meer dan opslaan oplevert. Wat het huis vraagt komt wel uit de batterij.",
                    prijs=_euro(terug or 0.0),
                )
            ),
            plan=kijk, rule="vol" if vol else "niet-opslaan", waarde=eraf, uren=uren,
            auto_weg=auto_weg,
        )
    else:
        besluit = Besluit(
            STANDBY,
            reason=(
                t("Terugleveren brengt nu evenveel op als stroom kost, dus opslaan kost alleen het verlies in de batterij.")
                if terug is not None and terug >= koop - PRICE_MARGIN else
                t("Nu laden of ontladen levert niets op, dus hij staat stil.")
            ),
            plan=kijk, rule="standby", waarde=eraf, uren=uren, auto_weg=auto_weg,
        )
    besluit.inkoop_tot = inkoop
    besluit.bijladen_winst = te_weinig
    besluit.handelen_winst = handel_te_weinig
    if handel_te_weinig is not None:
        # De grens van de bewoner is dan de reden dat hij niet aan het net levert (v0.162.0).
        besluit.reason += " " + t(
            "Aan het net leveren zou deze keer {winst} opleveren, minder dan de ondergrens van {grens}, dus dat doet hij niet.",
            winst=_euro(handel_te_weinig), grens=_euro(b.min_winst),
        )
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
    return som.stap / eta_in(b)


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
    eta = eta_uit(b)
    cap = b.capacity_kwh
    vrij = float("inf")
    if b.nacht:
        if over_kwh is None:
            return uit
        # Dezelfde maat als `auto_grens`: wat er morgenvroeg over is, terug naar
        # de accukant.
        vrij = max(0.0, over_kwh) / eta
    grens = max(float(b.auto_boven), b.bodem) / 100.0 * cap
    marge = AUTO_MARGE / 100.0 * cap
    # Per blok: wat de auto van het net zou nemen, wat er naast het huis van het
    # ontlaadvermogen over is, en wat de batterij aan het eind van het blok
    # boven zijn grens heeft zonder hulp (accukant).
    wil, ruimte, boven = [], [], []
    for uur in uren:
        deel = max(0.0, echte_uren(uur.start, uur.end))
        w = 0.0
        for van, tot, kwh in laden:
            lengte = echte_duur(van, tot).total_seconds()
            overlap = echte_duur(max(van, uur.start, key=_echt), min(tot, uur.end, key=_echt)).total_seconds()
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
    eta = eta_uit(b)
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
        vrij = max(0.0, over_kwh) / eta_uit(b)
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
            t("De laadpaal laadt, en de batterij heeft meer dan de nacht nodig: tot {grens}% helpt hij de auto.",
              grens=f"{grens:.0f}")
            if b.nacht else
            t("De laadpaal laadt, en de batterij zit boven {grens}%: tot daar helpt hij de auto.", grens=f"{grens:.0f}")
        )
        besluit.rule = "auto-helpen"
        return besluit
    besluit.stand = ZONNELADEN if besluit.stand == NUL else STANDBY
    besluit.power_w = 0.0
    om = besluit.auto_hulp_om
    besluit.reason = (
        (
            t("De laadpaal laadt. De batterij helpt de auto om {tijd}, op een duurder laaduur, en geeft nu niets af.",
              tijd=f"{om:%H:%M}")
            if later and om is not None else
            t("De laadpaal laadt, dus de batterij geeft niets af.")
        )
        + (" " + t("Zonoverschot gaat er nog wel in.") if besluit.stand == ZONNELADEN else "")
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


def herreken(
    stappen: list[tuple[datetime, float, float | None, float | None, float | None]],
    prijs,
    *,
    bodem: float,
    capacity_kwh: float | None,
    rte: float | None,
    max_charge_w: float = 0.0,
    max_discharge_w: float = 0.0,
) -> tuple[dict[str, dict[str, float]], Voorraad]:
    """Het kasboek over een stuk tijd opnieuw, uit metingen van toen (v0.130.1).

    In de eerste woning telde het kasboek van 22-09 tot 19-10-2026 teruglevering
    als € 0, omdat de terugleverprijs onbekend was (dezelfde sensor twee keer,
    salderen uit). Dan lijkt zon in de batterij opslaan gratis en levert elke
    ontlading de volle prijs op: "Opgeleverd" stond er te hoog. Hier rekent
    hetzelfde kasboek het opnieuw, met `verdiend`, `Voorraad` en `zon_in_accu`
    zoals de coach ze per ronde gebruikt.

    `stappen` is (begin, seconden, netvermogen, batterijvermogen laden
    positief, accustand) in tijdsvolgorde; in de coach een per kwartier, uit de
    kwartieropslag. `prijs(begin)` geeft (inkoop, terugleveren). Een stap
    zonder net- of batterijvermogen telt niet, zoals in de ronde. Geeft per dag
    "earned", "realized" en "solar", en de voorraad aan het eind.
    """
    voorraad = Voorraad()
    dagen: dict[str, dict[str, float]] = {}
    for begin, seconden, net_w, bat_w, soc in stappen:
        if net_w is None or bat_w is None or seconden <= 0:
            continue
        if max_charge_w > 0:
            bat_w = min(bat_w, max_charge_w)
        if max_discharge_w > 0:
            bat_w = max(bat_w, -max_discharge_w)
        koop, terug = prijs(begin)
        euro = verdiend(net_w, bat_w, koop, terug, seconden)
        if euro is None:
            continue
        dag = dagen.setdefault(begin.date().isoformat(), {"earned": 0.0, "realized": 0.0, "solar": 0.0})
        dag["earned"] += euro
        dag["realized"] += voorraad.stap(euro, bat_w * seconden / 3_600_000.0, soc, bodem, capacity_kwh, rte)
        dag["solar"] += zon_in_accu(net_w, bat_w, koop, terug, seconden) or 0.0
    return dagen, voorraad


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


# --- Het rendement per vermogen leren (v0.142.0) -----------------------------
#
# De eigenaar op 19-10-2026, bij een grafiek van een thuisbatterij die bij 200 W
# ongeveer 70% haalt en vanaf 1.200 W 92 tot 93%: "RTE is dramatisch op lage
# vermogens.. NoM in de nacht niet bevorderlijk dus." Eerst gemeten, in de
# eerste woning over tien dagen (notities van 19-10-2026): 896 schone stappen van
# één procent, met de wisselstroom uit het vermogen van de batterij zelf
# (nagemeten op de fase van de meter waar hij aan hangt, op 0,2 tot 0,4%) en de
# cellen uit de accustand maal de capaciteit. Dezelfde som doet de coach nu zelf,
# terwijl hij de batterij volgt; dan werkt hij ook zonder kWh-meter.

# De vermogensbanden aan de wisselstroomkant, in watt: de ondergrens van elke
# band. Die van de meting van 19-10-2026, met de bovenste gesplitst bij 2 kW.
RTE_BANDEN = (0.0, 300.0, 700.0, 1200.0, 2000.0)
# Alleen stappen tussen deze accustanden: daarbuiten kwamen er in de meting
# waarden boven 100% uit (de batterij kalibreert zich bovenin en onderin).
RTE_SOC_LAAG = 10.0
RTE_SOC_HOOG = 90.0
# Hoeveel er tijdens een stap de andere kant op mag gaan, als deel van wat er
# de goede kant op ging. Meer is geen stap van laden of van ontladen.
RTE_TEGEN = 0.02
# Hoeveel van de tijd van een stap in één band moet liggen om bij die band te
# horen (0,5 in de meting: `band.py 0.5`).
RTE_BAND_DEEL = 0.5
# Een stap met een rendement daarbuiten is een hapering van een sensor en geen
# meting. Binnen die grenzen middelt het uit: een procent is nooit precies een
# procent, en in de meting lag een op de tien stappen boven de 98%.
RTE_STAP_LAAG = 0.4
RTE_STAP_HOOG = 1.6
# Hoeveel stappen een band minstens heeft voordat hij telt, en per richting in
# totaal voordat de coach ermee rekent. Een dag laden en ontladen is er ruim
# genoeg voor: in de meting 40 tot 90 stappen per richting per dag.
RTE_MIN_BAND = 10
RTE_MIN_RICHTING = 30
# Boven zoveel stappen in een band telt alles voor de helft, zodat een batterij
# die ouder wordt of een nieuwe omvormer krijgt het rendement meeneemt.
RTE_MAX_BAND = 400
# Een gat tussen twee metingen van langer dan dit maakt de stap ongeldig: wat er
# in dat gat gebeurde weet de coach niet.
RTE_GAT = timedelta(seconds=90)


def _band(watt: float) -> int:
    for i in range(len(RTE_BANDEN) - 1, -1, -1):
        if watt >= RTE_BANDEN[i]:
            return i
    return 0


@dataclass
class Rendementmeter:
    """Leert het rendement per richting en per vermogen, tussen twee omslagen van de accustand.

    Een stap begint op het moment dat de accustand een procent omslaat en eindigt
    bij de volgende omslag dezelfde kant op. In die tijd ging er precies een
    procent van de capaciteit in of uit de cellen, en telt de meter wat er aan
    de wisselstroomkant doorheen ging: uit een kWh-meter op de batterij als die
    er is, anders uit het vermogen. Een sprong van meer dan een procent, een
    omkering, een gat in de metingen of te veel de andere kant op, en de stap
    telt niet; de volgende begint dan bij deze omslag.

    `sommen` is wat er bewaard wordt: per richting ("in", "uit") per band de
    wisselstroom en de cellen in kWh, de seconden en het aantal stappen.
    """

    sommen: dict = field(default_factory=dict)
    _soc: float | None = None
    _richting: int = 0
    _geldig: bool = False
    _op: datetime | None = None
    _erin: float = 0.0
    _eruit: float = 0.0
    _seconden: float = 0.0
    _in_band: dict = field(default_factory=dict)
    _teller: tuple[float, float] | None = None
    _w: float | None = None

    def tik(
        self, now: datetime, soc: float | None, watt: float | None, capaciteit_kwh: float | None,
        teller_in: float | None = None, teller_uit: float | None = None,
    ) -> bool:
        """Eén meting: de accustand, het vermogen (laden positief) en eventueel de tellers.

        True als er een stap bij kwam, zodat de coach weet dat er iets te bewaren is.
        """
        if soc is None or watt is None or not capaciteit_kwh:
            self._opnieuw(None)
            self._w = None
            return False
        if self._op is not None and self._w is not None:
            # Het vermogen van de vorige meting gold tot nu.
            vorig = self._w
            dt = (now - self._op).total_seconds()
            if dt < 0 or dt > RTE_GAT.total_seconds():
                self._geldig = False
            elif self._geldig:
                kwh = vorig * dt / 3_600_000.0
                if kwh >= 0:
                    self._erin += kwh
                else:
                    self._eruit -= kwh
                self._seconden += dt
                band = _band(abs(vorig))
                self._in_band[band] = self._in_band.get(band, 0.0) + dt
        self._op = now
        self._w = watt
        teller = (teller_in, teller_uit) if teller_in is not None and teller_uit is not None else None
        if self._soc is None:
            self._opnieuw(soc, teller)
            return False
        if soc == self._soc:
            return False
        d = soc - self._soc
        richting = 1 if d > 0 else -1
        bij = False
        if abs(d) == 1.0 and self._geldig and richting == self._richting:
            bij = self._stap(richting, min(soc, self._soc), capaciteit_kwh, teller)
        self._opnieuw(soc, teller, richting if abs(d) == 1.0 else 0)
        return bij

    def _opnieuw(self, soc: float | None, teller: tuple[float, float] | None = None, richting: int = 0) -> None:
        self._soc = soc
        self._richting = richting
        self._geldig = richting != 0
        self._erin = self._eruit = self._seconden = 0.0
        self._in_band = {}
        self._teller = teller

    def _stap(self, richting: int, soc: float, capaciteit_kwh: float, teller: tuple[float, float] | None) -> bool:
        if soc < RTE_SOC_LAAG or soc + 1.0 > RTE_SOC_HOOG or self._seconden <= 0:
            return False
        erin, eruit = self._erin, self._eruit
        if teller is not None and self._teller is not None:
            # Een kWh-meter op de batterij weet het beter dan het vermogen.
            erin, eruit = teller[0] - self._teller[0], teller[1] - self._teller[1]
            if erin < 0 or eruit < 0:
                return False
        goed, tegen = (erin, eruit) if richting > 0 else (eruit, erin)
        if goed <= 0 or tegen > RTE_TEGEN * goed:
            return False
        ac = goed - tegen
        cel = capaciteit_kwh / 100.0
        eta = cel / ac if richting > 0 else ac / cel
        if not RTE_STAP_LAAG <= eta <= RTE_STAP_HOOG:
            return False
        band, tijd = max(self._in_band.items(), key=lambda kv: kv[1])
        if tijd < RTE_BAND_DEEL * self._seconden:
            return False
        kant = self.sommen.setdefault("in" if richting > 0 else "uit", {})
        som = kant.setdefault(str(int(RTE_BANDEN[band])), {"ac": 0.0, "cel": 0.0, "s": 0.0, "n": 0})
        if som["n"] >= RTE_MAX_BAND:
            for sleutel in ("ac", "cel", "s"):
                som[sleutel] /= 2.0
            som["n"] //= 2
        som["ac"] += ac
        som["cel"] += cel
        som["s"] += self._seconden
        som["n"] += 1
        return True


def rendement_uit_stappen(sommen: dict | None) -> Rendement | None:
    """Het rendement per vermogen uit wat `Rendementmeter` bewaarde, of None als het nog te weinig is.

    Per band een punt: het gemiddelde vermogen aan de accukant en het rendement
    over al zijn stappen samen. Beide richtingen moeten er zijn, want de som
    heeft ze allebei nodig, en een richting telt pas met `RTE_MIN_RICHTING`
    stappen in banden die er elk minstens `RTE_MIN_BAND` hebben.
    """
    if not isinstance(sommen, dict):
        return None
    punten: dict[str, list[tuple[float, float]]] = {}
    gem: dict[str, float] = {}
    for kant in ("in", "uit"):
        banden = [
            som for som in (sommen.get(kant) or {}).values()
            if isinstance(som, dict) and int(som.get("n") or 0) >= RTE_MIN_BAND
            and float(som.get("ac") or 0) > 0 and float(som.get("cel") or 0) > 0 and float(som.get("s") or 0) > 0
        ]
        if sum(int(som["n"]) for som in banden) < RTE_MIN_RICHTING:
            return None
        rij = []
        for som in banden:
            ac, cel = float(som["ac"]), float(som["cel"])
            rij.append((cel / float(som["s"]) * 3600.0, cel / ac if kant == "in" else ac / cel))
        punten[kant] = sorted(rij)
        ac = sum(float(som["ac"]) for som in banden)
        cel = sum(float(som["cel"]) for som in banden)
        gem[kant] = cel / ac if kant == "in" else ac / cel
    # Heen en terug moet onder de honderd procent blijven, anders klopt er iets
    # niet (een capaciteit die te hoog staat telt bij laden te veel en bij
    # ontladen te weinig, maar heen en terug valt dat weg).
    if not 0.3 <= gem["in"] * gem["uit"] <= 1.0:
        return None
    return Rendement(punten["in"], punten["uit"], gem["in"], gem["uit"])


# --- Growatt: sturen met een laadschema (v0.150.0) --------------------------------
#
# De eigenaar op 22-10-2026: de Growatt-thuisbatterij sturen vanuit de coach, voor
# elke klant met een Growatt, en zelflerend. Een Growatt heeft geen stuurgetal in
# watt waar de regelaar op kan draaien: de integratie haalt alles eens per vijf
# minuten uit de cloud. Wat wel kan, bij een SPH op het API-token: een laadschema
# schrijven, drie vakken per dag met een laadvermogen in procent, een accustand
# waar hij stopt en of hij van het net mag laden. Daarbuiten doet de batterij
# zelf nul op de meter. Dus dezelfde som als bij een batterij die zelf nul doet
# (`zelf_nul`), en van het plan alleen de blokken van het net.

# Hoeveel er in een blok van het net moet komen voordat het een vak wordt, in kWh.
# Daaronder is het afronding in de som en geen plan.
GROWATT_MIN_KWH = 0.05
# Hoeveel vakken een Growatt heeft.
GROWATT_VAKKEN = 3
# Hoever vooruit het schema reikt. Het schema herhaalt zich elke dag op dezelfde
# kloktijden, dus een vak van morgen mag niet in een vak van vandaag vallen.
GROWATT_VOORUIT = timedelta(hours=23)
# Hoe lang een stuk alleen laden moet zijn om de inhoud te meten, in procent; na hoeveel
# stukken de coach de gemeten inhoud gelooft, en na hoeveel metingen het laadvermogen.
GROWATT_STUK_PCT = 10
GROWATT_MIN_STUKKEN = 3
# Vanaf hoeveel procent verschil in vermogen of stopgrens een nieuw schema loont.
GROWATT_SPELING_PCT = 5
GROWATT_SPELING_SOC = 3
# Vanaf hoeveel procent een lagere stopgrens wel een nieuw schema is (v0.163.1). Een stopgrens die
# te hoog staat laadt meer dan het plan wil, en op 100 zet de coach het schema niet zelf uit
# (`growatt_vol`); dan is het vermogen de enige rem.
GROWATT_ZAK_SOC = 10
# Hoe lang voor een vak de coach het vermogen en de stopgrens nog bijstelt. Daarvoor
# schuift het plan mee met hoe leeg de avond hem maakt.
GROWATT_VOORAF = timedelta(minutes=30)
# Over hoeveel nachten de coach zijn schema bijstelt, en vanaf hoeveel (v0.151.0).
GROWATT_NACHTEN = 7
GROWATT_MIN_NACHTEN = 3
# Nachten van voor v0.156.0 telden het tekort ook in de goedkope uren; die tellen niet mee.
GROWATT_NACHTEN_V = 2
GROWATT_MIN_VERMOGEN = 6
# Het vak ligt aan het eind van het goedkope stuk (v0.152.0): minstens zo lang, en zo lang
# dat hij op hooguit dit deel van zijn vermogen laadt. Die marge vangt een opdracht op die
# een keer niet aankomt, en een accu die trager laadt dan gedacht.
GROWATT_LAAT_MIN = timedelta(hours=2)
GROWATT_LAAT_DEEL = 0.5
# Vasthouden (v0.155.0) pas vanaf zoveel kWh boven de vloer. Bij bi-horário in de klantwoning
# (0,166 tegen 0,272) is een halve kWh vasthouden ruim vijf cent waard; minder is een extra
# schrijfopdracht naar de cloud van Growatt niet waard.
GROWATT_HOUDEN_KWH = 0.5
# Het vermogen in een vak om vast te houden (v0.156.1). Met de stopgrens op de accustand laadt hij
# niet, dus het getal zegt alleen hoe snel hij terugkomt als hij eronder zakt. In de klantwoning
# weigerde de Growatt-API op 24-10-2026 elk schema met 1% (zeven keer, ook na uren zonder opdracht),
# en nam hij om 22:37 hetzelfde vasthouden met 10% en de stopgrens op de accustand meteen aan.
GROWATT_HOUDEN_PCT = 10
# Het laagste laadvermogen dat de coach in een schema zet, in procent (v0.163.0). Wat de API
# lager krijgt neemt hij niet aan: hij houdt het oude getal en zet de rest wel. In de klantwoning
# op 26-10-2026 werd 8% geweigerd (en 1% op 24-10), en 10% aangenomen. De hoeveelheid begrenst de
# stopgrens, dus een hoger vermogen laadt niet meer, alleen eerder. Weigert een omvormer ook 10%,
# dan leert de coach dat (`growatt_pct_geweigerd`, `_async_growatt`).
GROWATT_MIN_PCT = 10


@dataclass
class GrowattSchema:
    """Wat er in de Growatt hoort te staan: laden van het net in vakken, of niet."""

    # Of hij in de vakken van het net mag laden. Uit is gewoon zelf nul op de meter.
    net: bool = False
    # Het laadvermogen in procent van wat hij kan, en tot welke accustand.
    vermogen_pct: int = 100
    stop_soc: int = 100
    # Tot drie vakken, als kloktijden "HH:MM" in de tijd van het huis.
    vakken: list[tuple[str, str]] = field(default_factory=list)
    # Wanneer het laatste vak afloopt; daarna hoort het schema weer uit.
    tot: datetime | None = None
    # Hoeveel er volgens het plan van het net in gaat, in kWh, voor de reden.
    kwh: float = 0.0
    # Vasthouden (v0.155.0): een vak met de stopgrens op de accustand, zodat hij niet laadt en
    # niet ontlaadt. Moet er later bij, dan wordt het een schema om te laden.
    houden: bool = False

    def velden(self) -> dict:
        """Wat er naar `growatt_server.write_ac_charge_times` gaat, zonder het apparaat."""
        uit: dict = {
            "charge_power": self.vermogen_pct,
            "charge_stop_soc": self.stop_soc,
            "mains_enabled": self.net,
        }
        for i in range(GROWATT_VAKKEN):
            vak = self.vakken[i] if i < len(self.vakken) else None
            uit[f"period_{i + 1}_start"] = vak[0] if vak else "00:00"
            uit[f"period_{i + 1}_end"] = vak[1] if vak else "00:00"
            uit[f"period_{i + 1}_enabled"] = vak is not None
        return uit

    def gelijk(self, gelezen: dict | None) -> bool:
        """Of wat de Growatt teruggeeft hierop lijkt.

        Zonder de accustand waar hij stopt: in de klantwoning gaf het teruglezen op
        22-10-2026 vlak na het schrijven 25 en een uur later 100, terwijl er 25 in
        stond (de omvormer heeft er twee velden voor). Dat de batterij daar stopt
        bewaakt de coach dus zelf (`growatt_vol`).
        """
        if not isinstance(gelezen, dict):
            return False
        if bool(gelezen.get("mains_enabled")) != self.net:
            return False
        if not self.net:
            return True
        try:
            if int(gelezen.get("charge_power")) != self.vermogen_pct:
                return False
        except (TypeError, ValueError):
            return False
        aan = sorted(
            (str(p.get("start_time")), str(p.get("end_time")))
            for p in gelezen.get("periods") or []
            if isinstance(p, dict) and p.get("enabled")
        )
        return aan == sorted(self.vakken)

    def wijkt_af(self, ander: "GrowattSchema | None", alleen_vakken: bool = False, zakken: bool = True) -> bool:
        """Of dit zoveel van een eerder schema verschilt dat schrijven loont.

        Het plan schuift elke minuut een beetje mee met de accustand. Elke procent
        verschil schrijven zou de cloud elke ronde een opdracht geven, en een tweede
        opdracht vlak na de eerste faalt (de klantwoning, 22-10-2026). Andere vakken
        of aan en uit zijn altijd een verschil. Het vermogen en de stopgrens alleen
        omhoog, en pas vanaf `GROWATT_SPELING_PCT` en `GROWATT_SPELING_SOC`: wil het plan
        minder, dan zet het het schema zelf uit zodra er genoeg in zit; behalve een stopgrens die
        `GROWATT_ZAK_SOC` of meer zakt (v0.163.1). `zakken=False` voor de schaduw: daar laadt er
        niets, dus het plan zakt de hele nacht, en dat zegt niets over het schema.
        """
        if ander is None or self.net != ander.net:
            return True
        if not self.net:
            return False
        if self.houden != ander.houden:
            # Een schema om te laden met een stopgrens op of onder het vasthouden doet al
            # hetzelfde: hij staat in zijn vak stil. Zoals na vol laden tot 100%.
            if self.houden and ander.stop_soc <= self.stop_soc and all(
                any(eind == oud_eind and oud_begin <= begin for oud_begin, oud_eind in ander.vakken)
                for begin, eind in self.vakken
            ):
                return False
            return True
        # Een vak dat al loopt valt na elk blok een stukje korter uit het plan; zolang het
        # oude vak het nieuwe dekt en op dezelfde tijd eindigt, staat het goed.
        dekt = all(
            any(eind == oud_eind and oud_begin <= begin for oud_begin, oud_eind in ander.vakken)
            for begin, eind in self.vakken
        )
        if alleen_vakken:
            return (not dekt or len(self.vakken) > len(ander.vakken)
                    or (zakken and ander.stop_soc - self.stop_soc >= GROWATT_ZAK_SOC))
        # Een veel lagere stopgrens wel (v0.163.1). In een klantwoning schreef de coach op 26-10-2026
        # om 13:51, bij 84% en met zon, tot 100% voor 1,1 kWh om 06:00; om 21:30 stond de accu op 15%,
        # en dan laadt dat schema van 15 tot 100%. Om 05:30 wilde hij een lagere grens, maar die schreef
        # hij niet: alleen omhoog telde.
        return (
            not dekt
            or len(self.vakken) > len(ander.vakken)
            or self.vermogen_pct - ander.vermogen_pct >= GROWATT_SPELING_PCT
            or self.stop_soc - ander.stop_soc >= GROWATT_SPELING_SOC
            or (zakken and ander.stop_soc - self.stop_soc >= GROWATT_ZAK_SOC)
        )


def _klok(moment: datetime) -> str:
    return moment.strftime("%H:%M")


def growatt_schema(
    uren: list[Uur], now: datetime, b: Batterij, bijstel_kwh: float = 0.0, loopt: bool = False,
    vasthouden: bool = True, min_pct: int = GROWATT_MIN_PCT,
) -> GrowattSchema:
    """Het laadschema voor een Growatt uit het plan van de batterij.

    Wat het plan in de komende uren van het net wil halen, in de laatste uren van het
    stuk even dure uren waar het in valt (v0.152.0; tot dan uitgesmeerd over het hele
    stuk). De eigenaar op 23-10-2026: "de laatste 2 uur van de goedkope uren de accu vol
    laden", en "je wilt uiteindelijk gewoon dat je de goedkope uren en de zon zoveel
    mogelijk gebruikt". Zo laat mogelijk betekent dat de coach over de hoeveelheid
    beslist met de verste zonverwachting (`GROWATT_VOORAF` voor het vak), en binnen het
    stuk kost het niets extra. Het vak duurt `GROWATT_LAAT_MIN`, of langer als hij
    anders boven `GROWATT_LAAT_DEEL` van zijn vermogen moet. Het vermogen is wat erin
    moet over wat er van het vak over is, naar boven afgerond op een procent van wat
    hij kan; hij stopt waar het plan zegt dat hij na het laatste stuk zit. Een vak over
    middernacht wordt er twee, want een vak van de Growatt loopt van een kloktijd
    naar een latere.

    `loopt`: het vak dat de coach schreef loopt al. Dan blijft het lopen tot het eind van
    het stuk, met wat er nog moet over de rest: anders schoof het begin terwijl hij laadde
    voorbij nu, en stond de batterij tot dat nieuwe begin buiten een vak, en voedde hij het
    huis in de goedkope uren (het virtuele huis, `growatt-bihorario`).
    """
    if not b.max_charge_w or not b.capacity_kwh:
        return GrowattSchema()
    rij = [u for u in uren if u.end > now]
    # Stukken even dure uren die aan elkaar liggen.
    stukken: list[list[Uur]] = []
    for u in rij:
        if stukken and stukken[-1][-1].end == u.start and abs(stukken[-1][0].price - u.price) <= PRICE_MARGIN:
            stukken[-1].append(u)
        else:
            stukken.append([u])
    # Alleen het eerstvolgende stuk: de Growatt heeft één stopgrens voor alle vakken,
    # en het schema herhaalt zich elke dag. Is dat stuk voorbij, dan schrijft de coach
    # het volgende; zo is het één schema per goedkoop stuk, zoals de beheersessie het
    # in de klantwoning voorstelde.
    #
    # Een vak reikt hooguit een etmaal vooruit, want daarna staat het op de klok weer bij
    # nu. Valt het eind van het stuk later, dan mag het toch blijven als nu even goedkoop
    # is: dan laadt het schema nu ook niet duurder. Anders afkappen. Zonder dat schoof het
    # eind elk blok een stukje op en schreef de coach elk kwartier een nieuw schema.
    rand = now + timedelta(hours=24)

    def laadt(u: Uur) -> bool:
        return u.net_kwh >= GROWATT_MIN_KWH and u.kwh > 0 and u.start < rand

    def houdt(u: Uur) -> bool:
        # Vasthouden (v0.155.0): stil terwijl het huis vraagt, en er zit iets in om vast te houden.
        # Minstens `GROWATT_HOUDEN_KWH` boven de vloer: voor minder is een opdracht de moeite niet.
        # Zonder `vasthouden` niet: de Growatt nam het niet aan (v0.156.0, `_async_growatt_fout`).
        boven = (u.soc - b.soc_min) / 100.0 * (b.capacity_kwh or 0.0)
        return vasthouden and u.vast and boven >= GROWATT_HOUDEN_KWH and u.start < rand

    gekozen = None
    for stuk in stukken:
        if stuk[0].start < now + GROWATT_VOORUIT and any(laadt(u) or houdt(u) for u in stuk):
            eind = stuk[-1].end
            if eind > rand and not (rij and rij[0].price <= stuk[0].price + PRICE_MARGIN):
                eind = max((u.end for u in stuk if u.end <= rand), default=stuk[0].end)
            gekozen = (stuk, eind)
            break
    if gekozen is None:
        return GrowattSchema()
    stuk, eind = gekozen
    net = [u for u in stuk if laadt(u)]
    vast = [u for u in stuk if houdt(u)]
    # Wat de nachten hiervoor leerden (`growatt_bijstelling`): meer of minder dan het plan.
    kwh = kwh_plan = sum(u.kwh for u in net)
    if net:
        kwh = kwh + bijstel_kwh
    laden = bool(net) and kwh >= GROWATT_MIN_KWH
    if not laden and not vast:
        return GrowattSchema()
    laat = eind
    if laden:
        soc_eind = net[-1].soc + (kwh - kwh_plan) / b.capacity_kwh * 100.0
        # Aan het eind van het stuk, in echte uren: de nacht van de wintertijd duurt er een langer.
        duur = max(GROWATT_LAAT_MIN, timedelta(hours=kwh / (b.max_charge_w * GROWATT_LAAT_DEEL / 1000.0)))
        duur = timedelta(minutes=-(-duur.total_seconds() // 900) * 15)
        laat = max(stuk[0].start, echt_verder(eind, -duur), key=_echt)
        if loopt and _echt(now) < _echt(laat):
            laat = now
    # Het vak begint waar hij gaat vasthouden, en anders waar hij gaat laden. Vasthouden is
    # één vak met de stopgrens op de accustand; komt het late moment om te laden, dan gaat de
    # stopgrens omhoog (`wijkt_af` met `houden`).
    begin = vast[0].start if vast else laat
    if laden and vast and _echt(laat) < _echt(vast[0].start):
        begin = laat
    # Komt het laden eerst (een beetje bij, en dan vasthouden), dan eerst een schema om te laden;
    # op de stopgrens houdt de coach hem daarna vast (`_async_growatt`).
    eerst_laden = laden and bool(vast) and _echt(net[0].start) <= _echt(vast[0].start)
    houden = bool(vast) and not eerst_laden and not (laden and _echt(now) >= _echt(laat))
    # Een vak is een kloktijd die zich elke dag herhaalt: begint het later, dan mag die kloktijd
    # nu niet al lopen, anders geldt hij vandaag al (v0.155.0). In het virtuele huis schreef hij
    # om 05:50 het vasthouden van morgen vanaf 05:15, en hield hij hem dus meteen vast.
    if _echt(begin) > _echt(now) and _echt(now) < _echt(eind) - timedelta(hours=24):
        return GrowattSchema()
    # Op het kwartier: het eerste blok van het plan begint op nu, en een begin dat elke
    # ronde een minuut opschuift is geen nieuw vak. Kloktijden, en over middernacht in tweeën.
    begin = begin.replace(minute=begin.minute // 15 * 15, second=0, microsecond=0)
    if eind.date() != begin.date() and _klok(eind) != "00:00":
        klok = [(_klok(begin), "23:59"), ("00:00", _klok(eind))]
    else:
        klok = [(_klok(begin), "23:59" if _klok(eind) == "00:00" else _klok(eind))]
    if houden:
        # Niet laden en niet ontladen: de stopgrens op wat er in zit als het vasthouden begint,
        # een klein vermogen (`GROWATT_HOUDEN_PCT`). Niet de stand van nu: een vak dat om 18:00 geschreven wordt
        # begint om 22:00, en dan zit er minder in; met een hogere grens laadt hij bij op
        # `GROWATT_HOUDEN_PCT`.
        stop = max(int(b.soc_min), int(min(b.soc or 0, vast[0].soc)))
        return GrowattSchema(
            net=True, vermogen_pct=min(100, max(GROWATT_HOUDEN_PCT, min_pct)), stop_soc=stop, vakken=klok, tot=eind,
            kwh=kwh if laden else 0.0, houden=True,
        )
    # Het vermogen over wat er van het laden nog over is.
    watt = kwh / max(echte_duur(max(laat, now, key=_echt), eind).total_seconds() / 3600.0, 1 / 60) * 1000.0
    pct = min(100, max(min_pct, 1, int(-(-watt * 100 // b.max_charge_w))))
    stop = min(int(b.soc_max), max(int(b.soc or 0) + 1, int(-(-soc_eind // 1))))
    return GrowattSchema(
        net=True, vermogen_pct=pct, stop_soc=stop, vakken=klok, tot=eind, kwh=kwh,
    )


def growatt_vol(schema: GrowattSchema, soc: float | None, soc_max: float = 100.0) -> bool:
    """Of de batterij al zit waar het schema hem laat stoppen, gemeten en niet teruggelezen.

    Niet als het schema tot vol gaat: vol stopt hij zelf, en zolang het vak loopt staat hij
    dan stil terwijl het huis goedkoop van het net haalt. Zou de coach het schema uitzetten,
    dan gaf de batterij in de goedkope uren stroom aan het huis en laadde de coach hem
    daarna weer bij, met het verlies twee keer. In het virtuele huis (`growatt-bihorario`)
    ging het schema zo tussen 05:20 en 08:46 zeventien keer aan en uit.
    """
    if not schema.net or schema.houden or soc is None or schema.stop_soc >= soc_max - 0.5:
        return False
    return soc >= schema.stop_soc - 0.5


def growatt_vakken_tekst(vakken: list) -> str:
    """De vakken van een schema als "22:00-08:00": een vak over middernacht staat er in twee."""
    rij: list[list[str]] = []
    for begin, eind in vakken:
        if rij and rij[-1][1] == "23:59" and begin == "00:00":
            rij[-1][1] = eind
        else:
            rij.append([begin, eind])
    return ", ".join(f"{a}-{b}" for a, b in rij)


def growatt_besluit(
    besluit: Besluit, schema: GrowattSchema | None, now: datetime, b: Batterij, balans: float | None = None,
    wil: GrowattSchema | None = None,
) -> Besluit:
    """Wat een Growatt doet, uit het schema dat erin staat, en niet uit het plan van dit kwartier.

    De Growatt volgt zijn schema; het plan per kwartier is daar alleen de som achter. In de
    klantwoning op 24-10-2026 laadde hij van 06:00 tot 07:57 rustig op 1,2 kW, terwijl het
    besluit elk kwartier tussen laden en vasthouden wisselde: in de laatste minuut van elk
    kwartier zag het plan laden, daarna weer vasthouden. Twaalf besluiten, en een reden
    ("het huis haalt zolang van het net") die niet klopte. Sinds v0.156.0: in een vak om te
    laden laadt hij, in een vak om vast te houden houdt hij vast, en daarbuiten doet hij zelf
    nul op de meter. De conclusie van de nacht zegt wat het schema gaat doen.

    `schema` is wat er in de Growatt staat (wat hij nu doet), `wil` wat de coach erin gaat
    zetten (voor de conclusie); zonder `wil` beide uit `schema`.
    """
    plan_schema = wil if wil is not None else schema
    nu = next((u for u in besluit.uren if u.start <= now < u.end), None)
    prijs = _euro(nu.price) if nu is not None else None
    klok = now.strftime("%H:%M")
    # Een vak dat om 23:59 eindigt loopt door in het vak van 00:00; die laatste minuut hoort erbij.
    in_vak = bool(schema is not None and schema.net and any(
        a <= klok < e or (e == "23:59" and klok >= a) for a, e in schema.vakken))
    plan = besluit.plan
    # Alleen de besluiten van de som zelf; geen accustand of geen prijzen blijft zoals het is.
    eigen = besluit.stand in (NUL, NETLADEN, STANDBY) and besluit.rule in ("nul", "netladen", "vasthouden")
    if not eigen:
        return besluit
    if plan_schema is not None and plan_schema.net:
        vakken = growatt_vakken_tekst(plan_schema.vakken)
        # De laatste zin van de nachtzin is de conclusie op de kaart (`nachtConclusie`).
        zin = (
            t("In de goedkope uren houdt hij de batterij vast op {soc}% ({vakken}); het huis haalt dan van het net.",
              soc=plan_schema.stop_soc, vakken=vakken)
            if plan_schema.houden else
            t("In de goedkope uren laadt hij {kwh} van het net bij ({vakken}), tot {soc}%.",
              kwh=_kwh(plan_schema.kwh), vakken=vakken, soc=plan_schema.stop_soc)
        )
        plan = f"{plan} {zin}".strip()
    elif plan and balans is not None:
        # Geen schema: dezelfde conclusie als bij elke andere batterij.
        zin = (
            t("Je houdt naar verwachting {kwh} over in je accu.", kwh=_kwh(balans)) if balans >= 0 else
            t("Je komt naar verwachting {kwh} tekort om de nacht te overbruggen;", kwh=_kwh(-balans)) + " "
            + _bijladen_zin(now, b, besluit.uren, -balans, besluit.inkoop_tot, besluit.bijladen_winst)
        )
        plan = f"{plan} {zin}".strip()
    if in_vak and schema.houden:
        return Besluit(
            STANDBY,
            reason=t("Hij houdt de batterij vast tot {eind}: wat erin zit is straks meer waard. Het huis haalt "
                     "zolang van het net, tegen {prijs}.", eind=schema.vakken[-1][1], prijs=prijs or "—"),
            plan=plan, rule="vasthouden", waarde=besluit.waarde, uren=besluit.uren,
            auto_weg=besluit.auto_weg, inkoop_tot=besluit.inkoop_tot, bijladen_winst=besluit.bijladen_winst,
        )
    if in_vak and b.soc is not None and b.soc < schema.stop_soc - 0.5:
        return Besluit(
            NETLADEN,
            reason=t("Hij laadt van het net tot {soc}%, tot {eind}, tegen {prijs}.",
                     soc=schema.stop_soc, eind=schema.vakken[-1][1], prijs=prijs or "—"),
            plan=plan, rule="netladen", waarde=besluit.waarde, uren=besluit.uren,
            auto_weg=besluit.auto_weg, inkoop_tot=besluit.inkoop_tot, bijladen_winst=besluit.bijladen_winst,
        )
    return Besluit(
        NUL,
        reason=t("Hij houdt de meter op nul: overschot gaat erin, wat het huis vraagt komt eruit."),
        plan=plan, rule="nul", waarde=besluit.waarde, uren=besluit.uren,
        auto_weg=besluit.auto_weg, inkoop_tot=besluit.inkoop_tot, bijladen_winst=besluit.bijladen_winst,
    )


def growatt_inhoud(stukken: list | None) -> float | None:
    """De bruikbare inhoud bij honderd procent in kWh, uit wat de eigen teller per procent telde.

    Elk stuk is een stuk alleen laden van minstens `GROWATT_STUK_PCT` procent, en
    wat de teller van de batterij zelf ("geladen") daarbij per procent opliep. Een
    stuk en niet elke procent, want de teller telt per 0,1 kWh en een procent is
    daar maar iets meer dan. In de klantwoning kwam er op 15-10-2026 ongeveer 12 kWh
    per 100% uit, tegen 15,3 op het typeplaatje. De mediaan, zodat één stuk waarin
    de cloud een meting oversloeg het niet bepaalt.
    """
    rij = sorted(float(s) for s in stukken or [] if isinstance(s, (int, float)) and 0.0 < s < 1.0)
    if len(rij) < GROWATT_MIN_STUKKEN:
        return None
    return rij[len(rij) // 2] * 100.0


def growatt_max_w(metingen: list | None) -> float | None:
    """Wat hij bij honderd procent van het net laadt, in watt, uit wat hij bij een deel haalde.

    Elke meting is het laadvermogen gedeeld door het deel dat in het schema stond,
    gemeten in een vak van het net zonder zon. In de klantwoning laadde hij op
    22-10-2026 bij 20% met 1.570 W aan de accukant: ongeveer 7,8 kW bij 100%.
    """
    rij = sorted(float(m) for m in metingen or [] if isinstance(m, (int, float)) and m > 0)
    if len(rij) < GROWATT_MIN_VERMOGEN:
        return None
    return rij[len(rij) // 2]


def growatt_nacht(teveel_kwh: float, tekort_kwh: float, net_kwh: float) -> float:
    """Wat een nacht had moeten laden boven op wat hij laadde, in kWh (v0.151.0).

    `teveel_kwh` is de zon die de volgende dag naar het net ging terwijl de batterij vol
    was; hooguit wat er die nacht van het net in ging (`net_kwh`), want meer had minder
    laden niet gescheeld. `tekort_kwh` is wat het huis buiten het goedkope stuk van het net
    haalde terwijl de batterij op zijn vloer stond. Positief: meer laden; negatief: minder.
    """
    return max(0.0, tekort_kwh) - min(max(0.0, teveel_kwh), max(0.0, net_kwh))


def growatt_duur(uren: list[Uur], now: datetime) -> bool:
    """Of nu een duurder uur is dan het goedkoopste van het komende etmaal (v0.156.0).

    Alleen dan telt een batterij op de vloer als tekort. In de klantwoning op 24-10-2026
    telde de coach de eerste echte nacht het huis van 23:53 tot 06:00 mee, in vazio, op de
    vloer en zonder vak: 11 kWh "te weinig", terwijl het huis daar juist van het net hoort
    te draaien. Zonder prijzen telt er niets: dan is het niet te zeggen.
    """
    nu = next((u for u in uren if u.start <= now < u.end), None)
    rand = now + timedelta(hours=24)
    prijzen = [u.price for u in uren if u.end > now and u.start < rand]
    if nu is None or not prijzen:
        return False
    return nu.price > min(prijzen) + PRICE_MARGIN


def growatt_nachten(rij: dict | None) -> list:
    """De nachten die de coach nakeek, zonder die van voor v0.156.0 (daar telde vazio mee)."""
    rij = rij or {}
    if rij.get("growatt_nachten_v") != GROWATT_NACHTEN_V:
        return []
    return list(rij.get("growatt_nachten") or [])


def growatt_bijstelling(nachten: list | None, capaciteit_kwh: float | None) -> float:
    """Hoeveel het schema boven of onder het plan laadt, in kWh, uit de laatste nachten.

    De mediaan van de laatste `GROWATT_NACHTEN`, vanaf `GROWATT_MIN_NACHTEN`; nooit meer
    dan de inhoud. Eén nacht met een feest of een dag zonder zon bepaalt het dus niet.
    """
    rij = [float(n) for n in (nachten or [])[-GROWATT_NACHTEN:] if isinstance(n, (int, float))]
    if len(rij) < GROWATT_MIN_NACHTEN or not capaciteit_kwh:
        return 0.0
    rij.sort()
    m = len(rij) // 2
    mediaan = rij[m] if len(rij) % 2 else (rij[m - 1] + rij[m]) / 2
    return max(-capaciteit_kwh, min(capaciteit_kwh, mediaan))
