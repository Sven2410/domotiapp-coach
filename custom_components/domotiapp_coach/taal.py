"""De taal van wat de coach schrijft (v0.140.0).

De eigenaar op 19-10-2026: "ik wil ook dat het hele coach in het engels ingesteld kan
worden". Eén taal per installatie: Installatie, Taal (`installation.language`):
automatisch (de taal van Home Assistant), Nederlands of English. Dezelfde keuze als het
paneel (`i18n.js`), zodat de melding op de telefoon, de reden op de kaart en het paneel
dezelfde taal spreken.

Het Nederlands blijft in de bron staan en is de sleutel: `t("niet laden")`. In het Engels
zoekt `t` de zin op in de JSON-bestanden in `engels/`; wat daar (nog) niet staat blijft
Nederlands. Een waarde gaat tussen accolades: `t("laden op {a} A", a=stroom)`. Zo blijft
elke proef die Nederlandse tekst narekent gelden.

Kent Home Assistant niet, en importeert niets uit dit pakket: planner.py en batterij.py
worden in de proeven los ingeladen, en dan moet dit bestand ook los werken. Daarom staan
de vertalingen in JSON en niet in Python.

Een installatie per Home Assistant, dus de taal staat hier een keer voor het hele proces;
de coach zet hem bij elke ronde uit de instellingen (`kies_uit`).
"""

from __future__ import annotations

import json
import pathlib
import re

_MAP = pathlib.Path(__file__).with_name("engels")
_taal = "nl"
_en: dict[str, str] | None = None


def _engels() -> dict[str, str]:
    """De vertalingen, een keer ingelezen: alle JSON-bestanden in engels/ samen."""
    global _en
    if _en is None:
        samen: dict[str, str] = {}
        for pad in sorted(_MAP.glob("*.json")):
            samen.update(json.loads(pad.read_text(encoding="utf-8")))
        _en = samen
    return _en


def taal() -> str:
    """De taal van nu: "nl" of "en"."""
    return _taal


def kies(instelling: str | None, ha_taal: str | None = None) -> str:
    """De taal uit de instelling, of bij automatisch uit die van Home Assistant."""
    global _taal
    if instelling in ("nl", "en"):
        _taal = instelling
    else:
        _taal = "en" if str(ha_taal or "").lower().startswith("en") else "nl"
    return _taal


def kies_uit(settings: dict | None, ha_taal: str | None = None) -> str:
    """`kies` met de instellingen van de coach."""
    return kies(((settings or {}).get("installation") or {}).get("language"), ha_taal)


def t(nl: str, **waarden: object) -> str:
    """Een zin in de taal van nu, met de waarden tussen accolades ingevuld."""
    zin = _engels().get(nl, nl) if _taal == "en" else nl
    if not waarden:
        return zin
    return re.sub(r"\{(\w+)\}", lambda m: str(waarden[m.group(1)]) if m.group(1) in waarden else m.group(0), zin)


def tn(n: float, een: str, meer: str, **waarden: object) -> str:
    """Enkelvoud of meervoud: `tn(n, "{n} beurt", "{n} beurten")`."""
    return t(een if n == 1 else meer, n=n, **waarden)


def getal(waarde: float, decimalen: int = 1) -> str:
    """Een getal met het scheidingsteken van de taal: 1,5 of 1.5."""
    tekst = f"{waarde:.{decimalen}f}"
    return tekst if _taal == "en" else tekst.replace(".", ",")
