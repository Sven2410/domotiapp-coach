"""Hoe een stroomprijs is opgebouwd, en of dat klopt. Kent Home Assistant niet.

De bewoner van de eerste woning op 18-10-2026, nadat de coach daar een maand
met een terugleverprijs van niets had gerekend: "Eigenlijk zou coach op de
achtergrond ingeregeld moeten hebben hoe de prijsopbouw is per
energieleverancier", en: "idealiter een all-in prijs én kale sensor +
additionele kosten/vergoedingen laten invullen. Indien het resultaat overeen
komt, krijg je automatisch de melding: de ingevoerde gegevens zijn correct."
De eigenaar: "Invullen, laten zien hoe de prijs tot stand is gekomen in woord
én cijfers, en het all-in resultaat tonen."

Drie dingen, en het paneel toont wat hier uitkomt in plaats van het zelf uit te
rekenen, zodat uitleg en controle niet uit elkaar kunnen lopen:

* **De opbouw** van de inkoopprijs uit de kale marktprijs en de velden van het
  contract (`inkoop`), zoals de leverancier hem op zijn eigen site uitlegt.
* **De controle** (`controleer`): die opbouw naast de all-in sensor van de
  leverancier, blok voor blok. Een leverancier die per uur afrekent tegenover een
  marktprijs per kwartier vergelijkt het uurgemiddelde; in de eerste woning op
  18-10-2026 klopte dat in elk uur tot op een honderdste cent.
* **Overdag** (`zon_op_onder`), voor een terugleverbonus die alleen van
  zonsopkomst tot zonsondergang geldt. Hetzelfde rekenwerk als `zonOpOnder` in
  geld.js, zodat Historie en de coach dezelfde uren tellen.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from math import acos, cos, degrees, pi, radians, sin, tan

# Hoeveel de opbouw van de all-in prijs mag afwijken om nog te kloppen, in euro
# per kWh: een tiende cent, dezelfde maat als `PRICE_MARGIN` in planner.py. Een
# leverancier rondt af op vijf decimalen, en de opbouw met een veld dat niet
# klopt zit er meteen ruim boven: bij een energiebelasting van een jaar eerder
# twee en een halve cent.
TOLERANTIE = 0.001

# Over hoeveel tijd terug de controle kijkt. De prijslijsten reiken van
# vandaag tot morgen; wat de sensor van gisteren nog heeft telt ook.
TERUG = timedelta(hours=24)


def _getal(waarde, standaard: float = 0.0) -> float:
    try:
        return float(waarde)
    except (TypeError, ValueError):
        return standaard


def btw_factor(d: dict) -> float:
    return 1.0 + _getal(d.get("vat_percent")) / 100.0


def inkoop(markt: float, d: dict) -> dict:
    """De inkoopprijs uit de kale marktprijs en de velden van een dynamisch contract.

    `d` is `contract.dynamic`. De energiebelasting en de opslag staan daar
    zonder btw, zoals `_all_in` in coach.py ze altijd gelezen heeft.
    """
    belasting = _getal(d.get("energy_tax"))
    opslag = _getal(d.get("supplier_markup"))
    factor = btw_factor(d)
    subtotaal = markt + belasting + opslag
    totaal = subtotaal * factor
    return {
        "markt": markt,
        "belasting": belasting,
        "opslag": opslag,
        "subtotaal": subtotaal,
        "btw_procent": _getal(d.get("vat_percent")),
        "btw": totaal - subtotaal,
        "totaal": totaal,
        # Dezelfde som zoals een leverancier die zijn opslag na de btw optelt
        # hem laat zien: (markt + belasting) maal de btw, plus de opslag met btw.
        # Zonneplan op zijn eigen site: "(EB + EPEX) x 1,21 + 0,02".
        "zonder_opslag": markt + belasting,
        "btw_zonder_opslag": (markt + belasting) * (factor - 1.0),
        "opslag_met_btw": opslag * factor,
    }


def markt_terug(markt: float, d: dict) -> float:
    """De marktprijs zoals de leverancier hem voor teruglevering betaalt: met of zonder btw.

    Zonneplan betaalt in 2026 de kale prijs mét btw ("de geldende stroomprijs
    exclusief energiebelasting", productvoorwaarden art. 7.2); dat zegt het
    vinkje `feed_in_vat`.
    """
    return markt * btw_factor(d) if d.get("feed_in_vat") else markt


def bonus(markt: float, d: dict, overdag: bool) -> float:
    """De terugleverbonus in procenten, per kWh, of 0 als hij niet geldt."""
    procent = _getal(d.get("feed_in_bonus_percent"))
    if procent <= 0:
        return 0.0
    if d.get("bonus_daytime") and not overdag:
        return 0.0
    vergoeding = _getal(d.get("feed_in_bonus"))
    basis = markt_terug(markt, d)
    over = basis + vergoeding if d.get("bonus_base") == "market_plus_fee" else basis
    if over <= 0:
        return 0.0
    return procent / 100.0 * over


def terug(markt: float | None, all_in: float | None, d: dict, salderen: bool, overdag: bool) -> dict:
    """Wat een teruggeleverde kWh opbrengt, en waaruit.

    Met salderen streept hij weg tegen een ingekochte: de all-in prijs min de
    opslag (die hangt aan de afname en komt niet terug), min de terugleverkosten,
    plus wat de leverancier per kWh vergoedt. Zonder salderen: de kale prijs
    min de kosten plus de vergoeding. Een bonus in procenten komt er in allebei
    bij, als het contract hem heeft. `bedrag` is None als de prijs waar hij op
    rust er niet is.
    """
    kosten = _getal(d.get("feed_in_costs"))
    vergoeding = _getal(d.get("feed_in_bonus"))
    opslag = _getal(d.get("supplier_markup")) * btw_factor(d)
    extra = bonus(markt, d, overdag) if markt is not None else 0.0
    if salderen:
        if all_in is None:
            return {"bedrag": None, "salderen": True}
        if d.get("netting_full"):
            # Sommige leveranciers geven binnen salderen de hele all-in prijs
            # terug, ook hun opslag (v0.129.1): Essent "per uur hetzelfde tarief
            # terug als je betaalt, inclusief btw, energiebelasting en
            # inkoopvergoeding". De vergoeding en de kosten gelden dan alleen
            # buiten salderen.
            return {"bedrag": all_in + extra, "salderen": True, "basis": all_in, "opslag": 0.0,
                    "kosten": 0.0, "vergoeding": 0.0, "bonus": extra, "vol": True}
        bedrag = all_in - opslag - kosten + vergoeding + extra
        return {"bedrag": bedrag, "salderen": True, "basis": all_in, "opslag": opslag,
                "kosten": kosten, "vergoeding": vergoeding, "bonus": extra}
    if d.get("feed_in_mode") == "fixed":
        # Een vaste terugleververgoeding naast een dynamische inkoop (v0.132.0):
        # dan telt de marktprijs niet, en een bonus in procenten daarover ook
        # niet. Wel de terugleverkosten.
        vast = _getal(d.get("feed_in_fixed"))
        return {"bedrag": vast - kosten, "salderen": False, "basis": vast, "opslag": 0.0,
                "kosten": kosten, "vergoeding": 0.0, "bonus": 0.0, "vast": True}
    if markt is None:
        return {"bedrag": None, "salderen": False}
    basis = markt_terug(markt, d)
    bedrag = basis - kosten + vergoeding + extra
    return {"bedrag": bedrag, "salderen": False, "basis": basis, "opslag": 0.0,
            "kosten": kosten, "vergoeding": vergoeding, "bonus": extra,
            "met_btw": bool(d.get("feed_in_vat"))}


Blokken = dict[datetime, tuple[datetime, float]]


def gemiddeld(blokken: Blokken, van: datetime, tot: datetime) -> float | None:
    """Het tijdgewogen gemiddelde over [van, tot), of None als dat niet helemaal bekend is."""
    som = 0.0
    gedekt = 0.0
    for start, (einde, prijs) in blokken.items():
        a, b = max(start, van), min(einde, tot)
        if b <= a:
            continue
        sec = (b - a).total_seconds()
        som += prijs * sec
        gedekt += sec
    lengte = (tot - van).total_seconds()
    if lengte <= 0 or gedekt < lengte - 1.0:
        return None
    return som / gedekt


def lengte(blokken: Blokken) -> timedelta:
    """De gewone lengte van een blok in deze lijst: de mediaan."""
    lengtes = sorted(einde - start for start, (einde, _) in blokken.items())
    return lengtes[len(lengtes) // 2] if lengtes else timedelta(hours=1)


def controleer(all_in: Blokken, markt: Blokken, d: dict, now: datetime) -> dict:
    """De opbouw naast de all-in sensor, over alle blokken die allebei kennen.

    Vergeleken wordt op de grofste van de twee: een leverancier die per uur
    afrekent tegenover een marktprijs per kwartier krijgt het uurgemiddelde.

    `status` is "correct", "afwijking" of "onbekend" (een van de twee mist, of
    ze hebben geen blok samen). Bij een afwijking zegt `vast` of het verschil
    in elk blok even groot is: dan zit het in een bedrag per kWh (de
    energiebelasting of de opslag), en niet in de btw.
    """
    if not all_in or not markt:
        return {"status": "onbekend", "blokken": 0}
    stap = max(lengte(all_in), lengte(markt))
    begin = now - TERUG
    eerste = min(min(all_in), min(markt))
    laatste = min(max(e for e, _ in all_in.values()), max(e for e, _ in markt.values()))
    # Het raster op de grofste blokken, vanaf het begin van een uur.
    blok = max(eerste, begin).replace(minute=0, second=0, microsecond=0)
    verschillen: list[tuple[datetime, float, float, float]] = []
    while blok + stap <= laatste:
        a = gemiddeld(all_in, blok, blok + stap)
        m = gemiddeld(markt, blok, blok + stap)
        if a is not None and m is not None:
            verschillen.append((blok, a, m, a - inkoop(m, d)["totaal"]))
        blok += stap
    if not verschillen:
        return {"status": "onbekend", "blokken": 0}
    alle = [v for *_, v in verschillen]
    grootste = max(alle, key=abs)
    nu = next((v for v in verschillen if v[0] <= now < v[0] + stap), verschillen[-1])
    return {
        "status": "correct" if abs(grootste) <= TOLERANTIE else "afwijking",
        "blokken": len(verschillen),
        "stap_minuten": int(stap.total_seconds() // 60),
        "grootste": grootste,
        "gemiddeld": sum(alle) / len(alle),
        "vast": max(alle) - min(alle) <= TOLERANTIE,
        "blok": {"start": nu[0], "einde": nu[0] + stap, "all_in": nu[1], "markt": nu[2],
                 "verschil": nu[3]},
    }


def zon_op_onder(dag: date, lat: float, lon: float) -> tuple[datetime, datetime] | None:
    """Zonsopkomst en zonsondergang op die dag, in UTC, of None als de zon niet op of onder gaat.

    De vergelijking van de NOAA, met de zon 0,833 graad onder de horizon voor
    de breking in de lucht en de rand van de schijf. Op een minuut na wat de
    tabellen zeggen, en dat is genoeg voor een bonus die per uur of per
    kwartier telt. `zonOpOnder` in geld.js doet hetzelfde.
    """
    n = dag.timetuple().tm_yday
    hoek = 2.0 * pi / 365.0 * (n - 1)
    tijdvereffening = 229.18 * (
        0.000075 + 0.001868 * cos(hoek) - 0.032077 * sin(hoek)
        - 0.014615 * cos(2 * hoek) - 0.040849 * sin(2 * hoek)
    )
    declinatie = (
        0.006918 - 0.399912 * cos(hoek) + 0.070257 * sin(hoek) - 0.006758 * cos(2 * hoek)
        + 0.000907 * sin(2 * hoek) - 0.002697 * cos(3 * hoek) + 0.00148 * sin(3 * hoek)
    )
    breedte = radians(lat)
    x = cos(radians(90.833)) / (cos(breedte) * cos(declinatie)) - tan(breedte) * tan(declinatie)
    if x < -1.0 or x > 1.0:
        return None
    uurhoek = degrees(acos(x))
    middag = 720.0 - 4.0 * lon - tijdvereffening
    middernacht = datetime(dag.year, dag.month, dag.day, tzinfo=timezone.utc)
    return (
        middernacht + timedelta(minutes=middag - 4.0 * uurhoek),
        middernacht + timedelta(minutes=middag + 4.0 * uurhoek),
    )


def overdag(start: datetime, einde: datetime, lat: float | None, lon: float | None) -> bool:
    """Of dit blok (in UTC, of met een tijdzone) tussen zonsopkomst en zonsondergang valt.

    Een blok telt als het midden ervan erbinnen ligt. Zonder ligging van de
    woning is het niet te zeggen, en telt een bonus die alleen overdag geldt
    niet: liever te weinig dan een bedrag dat niet uitbetaald wordt.
    """
    if lat is None or lon is None:
        return False
    midden = start + (einde - start) / 2
    if midden.tzinfo is None:
        return False
    midden = midden.astimezone(timezone.utc)
    zon = zon_op_onder(midden.date(), lat, lon)
    return zon is not None and zon[0] <= midden < zon[1]


# Velden van een dynamisch contract die er later bij kwamen, met hun standaard
# (v0.132.0); zie `vingerafdruk`.
LATER = {"feed_in_mode": "market", "feed_in_fixed": 0.0}


def vingerafdruk(contract: dict) -> str:
    """Een korte handtekening van alles wat de prijs bepaalt, voor de bevestiging.

    De bewoner bevestigt deze waarden; verandert er daarna iets (een bedrag,
    een sensor, salderen, de leverancier), dan hoort hij opnieuw te kijken.
    Eerdere contracten tellen niet: die gaan over terugkijken.
    """
    def gewoon(waarde):
        # 21 en 21.0 zijn hetzelfde bedrag; het paneel stuurt soms het een en
        # soms het ander terug.
        if isinstance(waarde, bool) or not isinstance(waarde, (int, float)):
            return waarde if waarde is not None else ""
        return round(float(waarde), 6)

    def dynamisch(velden: dict) -> dict:
        # Een veld dat later kwam telt pas mee als het iets anders zegt dan
        # zijn standaard: anders gold elke bevestiging van voor die uitgave
        # niet meer, terwijl er niets aan de prijs veranderde.
        return {k: gewoon(v) for k, v in velden.items() if LATER.get(k, object()) != v}

    deel = {
        "type": contract.get("type"),
        "netting": bool(contract.get("netting")),
        "supplier": contract.get("supplier") or "",
        "fixed": {k: gewoon(v) for k, v in (contract.get("fixed") or {}).items()},
        "dynamic": dynamisch(contract.get("dynamic") or {}),
        "gas": {k: gewoon(v) for k, v in (contract.get("gas") or {}).items() if k != "periods"},
        "water": {k: gewoon(v) for k, v in (contract.get("water") or {}).items() if k != "periods"},
    }
    tekst = json.dumps(deel, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha1(tekst.encode("utf-8")).hexdigest()[:16]


__all__ = [
    "TOLERANTIE", "bonus", "btw_factor", "controleer", "gemiddeld", "inkoop", "lengte", "markt_terug", "overdag",
    "terug",
    "vingerafdruk", "zon_op_onder",
]
