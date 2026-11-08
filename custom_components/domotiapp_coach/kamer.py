"""Wat een kamer met een airco doet: hoe snel hij afkoelt, en wat een kilowattuur oplevert (v0.207.0).

Een bewoner op 07-11-2026: "Hoe snel koelt een woning af bij een bepaalde
buitentemperatuur, en hoe snel warmt een woning weer op om op een gewenste
temperatuur te komen. Dit gekoppeld aan de verbruikte energie." Dit is stap 1:
alleen leren en laten zien, de coach doet er nog niets anders door.

Twee getallen per kamer, allebei uit metingen en nooit uit een aanname:

- **Het verlies** `k`, in °C per uur per °C verschil met buiten. Zolang de airco
  uit staat zakt de kamer naar de buitentemperatuur toe:
  ``dT/dt = -k (binnen - buiten)``. Alleen uit rustige vensters van twee uur:
  's nachts (geen zon op het raam), minstens een uur nadat de airco uitging, met
  minstens drie graden verschil, en zonder sprong (een raam dat opengaat).
- **De winst**, in °C per kWh, per stand. Terwijl de airco verwarmt of koelt is
  wat de kamer doet het verlies plus wat de airco erin stopt. Met `k` erbij is
  wat de airco deed: ``(eind - begin) + k * gemiddeld verschil * uren``, en dat
  gedeeld door de kilowatturen van de vermogenssensor. Op temperatuur klopt dat
  ook: dan houdt hij precies het verlies bij.

Kent Home Assistant niet. `_async_airco_leren` in coach.py geeft per ronde een
meting; de tijden zijn in UTC, zodat een venster over de klokwissel heen echt
twee uur is.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

# Hoe lang een venster duurt. Een kamersensor meet op een tiende graad; over twee
# uur bij tien graden verschil is dat een paar procent van wat er gemeten wordt.
VERLIES_DUUR = timedelta(hours=2)
WINST_DUUR = timedelta(hours=1)
# Het eerste uur na uit telt niet mee: de muren en de lucht uit de airco zijn dan
# nog warmer (of kouder) dan de kamer.
NA_UIT = timedelta(hours=1)
# Onder dit verschil met buiten is wat de kamer doet vooral ruis.
MIN_VERSCHIL_C = 3.0
# Meer dan dit tussen twee metingen is geen afkoelen maar een raam of een deur.
SPRONG_C = 0.5
# Een gat in de metingen (een herstart, een sensor die wegviel) breekt het venster.
GAT = timedelta(minutes=5)
# Wat een airco onder dit vermogen trekt is stand-by: hij staat uit.
STILLE_W = 30.0
# Onder dit aantal kilowattuur in een venster valt er niets te delen.
MIN_KWH = 0.1
# Vanaf zoveel vensters staat het op de kaart; daarvoor "nog aan het leren".
GENOEG = 5
# Het lopende gemiddelde weegt een nieuw venster nooit lichter dan 1 op dit aantal,
# zodat een kamer die anders wordt (een nieuw raam, een ander seizoen) bijleert.
GEWICHT = 20
# Wat geen kamer is: sneller afkoelen dan de helft van het verschil per uur, of een
# kilowattuur dat meer dan twintig graden doet.
K_MAX = 0.5
WINST_MAX = 20.0


def _getal(waarde: Any) -> float | None:
    try:
        return None if waarde is None else float(waarde)
    except (TypeError, ValueError):
        return None


def _moment(tekst: Any) -> datetime | None:
    if isinstance(tekst, datetime):
        return tekst
    try:
        return datetime.fromisoformat(str(tekst)) if tekst else None
    except ValueError:
        return None


def soort_nu(hvac: str, watt: float | None) -> str | None:
    """Wat de airco nu doet voor het leren: "uit", "heat", "cool", of None (iets anders)."""
    if hvac == "off":
        return "uit" if watt is None or watt < STILLE_W else None
    if hvac in ("heat", "cool"):
        return hvac
    return None


def leer_stap(
    venster: dict[str, Any] | None,
    nu: datetime,
    kamer_c: float | None,
    buiten_c: float | None,
    soort: str | None,
    watt: float | None,
    nacht: bool,
    uit_sinds: datetime | None,
    geleerd: dict[str, Any],
) -> tuple[dict[str, Any] | None, tuple[str, float] | None]:
    """Eén meting erbij. Geeft het venster terug, en een uitkomst als er een af is.

    `venster` is wat er loopt (of None): soort, begin, de eerste en de laatste
    kamertemperatuur, de som van het verschil met buiten, het aantal metingen en de
    kilowatturen. `uit_sinds` is sinds wanneer de airco uit staat (UTC). De uitkomst
    is ("verlies", k) of ("heat"/"cool", °C per kWh).
    """
    # De winst rekent met het verlies, dus pas als dat vaak genoeg gemeten is.
    k = geleerd_bekend(geleerd, "k")
    mag = kamer_c is not None and buiten_c is not None
    if soort == "uit":
        mag = mag and nacht and uit_sinds is not None and nu - uit_sinds >= NA_UIT
    elif soort in ("heat", "cool"):
        # Zonder het verlies valt de winst niet te scheiden van wat de kamer zelf doet,
        # en zonder vermogenssensor zijn er geen kilowatturen.
        mag = mag and k is not None and watt is not None
    else:
        mag = False

    if venster is not None:
        laatste = _moment(venster.get("laatste_at"))
        breekt = (
            not mag
            or venster.get("soort") != soort
            or laatste is None
            or nu - laatste > GAT
            or nu < laatste
            or abs(float(kamer_c) - float(venster["laatste_c"])) > SPRONG_C
        )
        if breekt:
            venster = None
    if not mag:
        return None, None
    if venster is None:
        return {
            "soort": soort, "begin": nu.isoformat(), "laatste_at": nu.isoformat(),
            "begin_c": float(kamer_c), "laatste_c": float(kamer_c),
            "verschil_som": float(kamer_c) - float(buiten_c), "n": 1, "kwh": 0.0,
        }, None

    stap_uren = (nu - _moment(venster["laatste_at"])).total_seconds() / 3600.0
    venster = {
        **venster,
        "laatste_at": nu.isoformat(),
        "laatste_c": float(kamer_c),
        "verschil_som": float(venster["verschil_som"]) + float(kamer_c) - float(buiten_c),
        "n": int(venster["n"]) + 1,
        "kwh": float(venster["kwh"]) + (max(0.0, float(watt)) * stap_uren / 1000.0 if watt is not None else 0.0),
    }
    duur = nu - _moment(venster["begin"])
    uren = duur.total_seconds() / 3600.0
    verschil = float(venster["verschil_som"]) / int(venster["n"])
    gezakt = float(venster["begin_c"]) - float(kamer_c)

    if soort == "uit":
        if duur < VERLIES_DUUR:
            return venster, None
        if abs(verschil) < MIN_VERSCHIL_C:
            return None, None
        waarde = gezakt / (uren * verschil)
        return None, (("verlies", waarde) if 0.0 <= waarde <= K_MAX else None)

    if duur < WINST_DUUR:
        return venster, None
    kwh = float(venster["kwh"])
    if kwh < MIN_KWH:
        return None, None
    gedaan = -gezakt + float(k) * verschil * uren
    if soort == "cool":
        gedaan = -gedaan
    waarde = gedaan / kwh
    return None, ((soort, waarde) if 0.0 < waarde <= WINST_MAX else None)


def leer_erbij(geleerd: dict[str, Any], uitkomst: tuple[str, float]) -> dict[str, Any]:
    """Een uitkomst in het lopende gemiddelde: `k` en `k_n`, of `heat`/`cool` met hun `_n`."""
    soort, waarde = uitkomst
    sleutel = "k" if soort == "verlies" else soort
    oud = _getal(geleerd.get(sleutel))
    n = int(geleerd.get(f"{sleutel}_n") or 0)
    if oud is None or n <= 0:
        nieuw = waarde
    else:
        nieuw = oud + (waarde - oud) / min(n + 1, GEWICHT)
    return {**geleerd, sleutel: round(nieuw, 5), f"{sleutel}_n": n + 1}


def geleerd_bekend(geleerd: dict[str, Any], sleutel: str) -> float | None:
    """Het geleerde getal, maar pas vanaf `GENOEG` vensters."""
    if int(geleerd.get(f"{sleutel}_n") or 0) < GENOEG:
        return None
    return _getal(geleerd.get(sleutel))
