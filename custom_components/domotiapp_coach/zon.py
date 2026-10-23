"""De zon verwachten zonder paneelgegevens (v0.151.0). Kent Home Assistant niet.

De eigenaar op 22-10-2026, via de beheersessie: "Zon ZONDER paneelgegevens. Leer per uur
van de dag een helderhemel-omhullende uit de eigen opwek (hoogste waarden van de laatste
weken, meegeschoven met de zonnestand). Schaal die met de weersverwachting die HA al heeft.
Staat Forecast.Solar of Solcast er, gebruik die dan." Dit is dus de laatste bron in
`_async_zonkromme` (coach.py): na het energiedashboard, de integratie en de sensoren die de
klant invulde.

Drie stappen, alles in UTC zodat de dag van 23 en die van 25 uur vanzelf goed gaan:

* **De heldere dag** (`heldere_kromme`): per uur het meeste dat het dak de laatste
  `ZON_DAGEN` dagen op dat uur deed, omgerekend naar de stand van de zon op de dag die
  verwacht wordt (`zonhoogte`, de formules van NOAA). Een dak dat half oktober om 16:00
  nog in de zon lag, ligt daar eind oktober iets lager.
* **Hoeveel daarvan er komt** (`zonfactor`): de verhouding tussen wat het dak deed en de
  heldere dag, per klasse bewolking uit het weerbericht. Geleerd uit de eigen uren, pas
  met `ZON_MIN_PAREN` per klasse. Zonder weerbericht of te weinig paren: de mediaan van de
  laatste `ZON_RECENT` dagen, dus "zoals het de laatste dagen ging".
* **De verwachting** (`zon_uit_opwek`): de heldere dag maal de factor.

Het is een schatting, en het scherm zegt dat erbij. Wat het dak op dit moment doet stuurt
de coach daarnaast zoals altijd bij (`_zon_gemeten`).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import asin, cos, pi, radians, sin

# Hoeveel dagen terug de heldere dag gezocht wordt, en hoeveel dagen "de laatste dagen" zijn.
ZON_DAGEN = 14
ZON_RECENT = 3
# Onder welke zonnestand (de sinus van de hoogte) een uur niet meetelt voor de omrekening:
# vlak bij de horizon wordt de verhouding tussen twee dagen te groot om iets te zeggen.
ZON_LAAG = 0.05
# Onder hoeveel kWh een uur van de heldere dag te weinig is om een verhouding uit te halen.
ZON_MIN_HELDER = 0.1
# Vijf klassen bewolking, van 0 tot 100 procent, en hoeveel uren een klasse nodig heeft.
ZON_KLASSEN = 5
ZON_MIN_PAREN = 6


def zonhoogte(moment: datetime, breedte: float, lengte: float) -> float:
    """De sinus van de hoogte van de zon boven de horizon, op een moment in UTC.

    De benadering van NOAA (de declinatie en de tijdvereffening uit de dag van het jaar),
    op een paar tiende graad nauwkeurig; voor een verhouding tussen twee dagen ruim genoeg.
    """
    moment = moment.astimezone(timezone.utc) if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    dag = moment.timetuple().tm_yday
    uur = moment.hour + moment.minute / 60 + moment.second / 3600
    g = 2 * pi / 365 * (dag - 1 + (uur - 12) / 24)
    decl = (0.006918 - 0.399912 * cos(g) + 0.070257 * sin(g) - 0.006758 * cos(2 * g)
            + 0.000907 * sin(2 * g) - 0.002697 * cos(3 * g) + 0.00148 * sin(3 * g))
    tijd = 229.18 * (0.000075 + 0.001868 * cos(g) - 0.032077 * sin(g)
                     - 0.014615 * cos(2 * g) - 0.040849 * sin(2 * g))
    zonnetijd = uur * 60 + tijd + 4 * lengte
    hoek = radians(zonnetijd / 4 - 180)
    phi = radians(breedte)
    return sin(phi) * sin(decl) + cos(phi) * cos(decl) * cos(hoek)


def _midden(uur: datetime) -> datetime:
    return uur + timedelta(minutes=30)


def heldere_kromme(
    opwek: dict[datetime, float], uren: list[datetime], breedte: float, lengte: float,
) -> dict[datetime, float]:
    """Per uur in `uren` (UTC, het begin van het uur) wat een heldere dag zou geven, in kWh.

    `opwek` is wat het dak deed, per uur in UTC. Per gevraagd uur: dezelfde kloktijd in UTC
    op elk van de `ZON_DAGEN` dagen ervoor, omgerekend met de verhouding van de zonnestand,
    en daarvan het meeste. Geen uur van vroeger, dan niets.
    """
    uit: dict[datetime, float] = {}
    for uur in uren:
        nu_hoog = zonhoogte(_midden(uur), breedte, lengte)
        if nu_hoog <= 0:
            uit[uur] = 0.0
            continue
        beste = None
        for d in range(1, ZON_DAGEN + 1):
            toen = uur - timedelta(days=d)
            kwh = opwek.get(toen)
            if kwh is None:
                continue
            toen_hoog = zonhoogte(_midden(toen), breedte, lengte)
            if toen_hoog < ZON_LAAG:
                continue
            waarde = kwh * nu_hoog / toen_hoog
            beste = waarde if beste is None else max(beste, waarde)
        if beste is not None:
            uit[uur] = beste
    return uit


def _klasse(bewolking: float) -> int:
    return min(ZON_KLASSEN - 1, max(0, int(bewolking / (100 / ZON_KLASSEN))))


def _mediaan(rij: list[float]) -> float | None:
    if not rij:
        return None
    rij = sorted(rij)
    m = len(rij) // 2
    return rij[m] if len(rij) % 2 else (rij[m - 1] + rij[m]) / 2


def zonfactor(
    opwek: dict[datetime, float], helder: dict[datetime, float], bewolking: dict[datetime, float],
    nu: datetime,
) -> tuple[dict[int, float], float | None]:
    """Per klasse bewolking welk deel van de heldere dag er kwam, en de mediaan van de laatste dagen.

    Alleen uren die voorbij zijn, met een heldere dag van minstens `ZON_MIN_HELDER`. Een klasse
    telt pas met `ZON_MIN_PAREN` uren. Nooit boven één: een heldere dag is het meeste.
    """
    per_klasse: dict[int, list[float]] = {}
    recent: list[float] = []
    grens = nu - timedelta(days=ZON_RECENT)
    for uur, kwh in opwek.items():
        h = helder.get(uur)
        if h is None or h < ZON_MIN_HELDER or uur + timedelta(hours=1) > nu:
            continue
        deel = max(0.0, min(1.0, kwh / h))
        if uur >= grens:
            recent.append(deel)
        if uur in bewolking:
            per_klasse.setdefault(_klasse(bewolking[uur]), []).append(deel)
    factoren = {k: _mediaan(rij) for k, rij in per_klasse.items() if len(rij) >= ZON_MIN_PAREN}
    return {k: v for k, v in factoren.items() if v is not None}, _mediaan(recent)


def zon_uit_opwek(
    opwek: dict[datetime, float], uren: list[datetime], breedte: float, lengte: float,
    bewolking_toen: dict[datetime, float] | None = None,
    bewolking_straks: dict[datetime, float] | None = None,
    nu: datetime | None = None,
) -> dict[datetime, float]:
    """De zonverwachting per uur in `uren` (UTC), in kWh, uit de eigen opwek en het weer.

    `bewolking_toen` is wat het weerbericht op een uur dat voorbij is zei, `bewolking_straks`
    wat het voor de komende uren zegt, allebei in procent. Zonder een geleerde factor voor de
    klasse van een uur: zoals het de laatste dagen ging. Zonder dat ook: niets voor dat uur,
    want een heldere dag zonder meer is een belofte die het dak in de herfst zelden waarmaakt.
    """
    nu = nu or datetime.now(timezone.utc)
    verleden = sorted(opwek)
    helder_toen = heldere_kromme(opwek, verleden, breedte, lengte)
    factoren, recent = zonfactor(opwek, helder_toen, bewolking_toen or {}, nu)
    helder = heldere_kromme(opwek, uren, breedte, lengte)
    uit: dict[datetime, float] = {}
    for uur in uren:
        h = helder.get(uur)
        if h is None:
            continue
        factor = None
        if bewolking_straks and uur in bewolking_straks:
            factor = factoren.get(_klasse(bewolking_straks[uur]))
        if factor is None:
            factor = recent
        if factor is None:
            continue
        uit[uur] = round(h * factor, 4)
    return uit
