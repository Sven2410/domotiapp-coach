"""Welke zinnen van de coach nog geen Engels hebben (v0.140.0).

    python tools/vertaalcheck.py                 # alle Python-bestanden van de coach
    python tools/vertaalcheck.py coach.py planner.py

Leest elke t("..."), tn(n, "...", "...") en nt("...") in custom_components/domotiapp_coach
(buiten commentaar en docstrings) en zoekt de zin op in engels/*.json. Ook: een zin die in twee
JSON-bestanden anders vertaald is, een vertaling met andere waarden tussen accolades dan het
Nederlands, en een gedachtestreepje. De proef "elke zin van de coach heeft Engels" in
tests/test_coach.py gebruikt dezelfde functie. Het paneel heeft tools/vertaalcheck.mjs.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

BRON = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "domotiapp_coach"
ENGELS = BRON / "engels"


def _zinnen(pad: pathlib.Path) -> set[str]:
    """De letterlijke zinnen in t(), tn() en nt() van een bestand."""
    uit: set[str] = set()
    boom = ast.parse(pad.read_text(encoding="utf-8"))
    for knoop in ast.walk(boom):
        if not isinstance(knoop, ast.Call):
            continue
        naam = knoop.func.id if isinstance(knoop.func, ast.Name) else knoop.func.attr if isinstance(knoop.func, ast.Attribute) else ""
        args = knoop.args
        if naam in ("t", "nt") and args and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
            uit.add(args[0].value)
        if naam == "tn" and len(args) >= 3:
            for arg in args[1:3]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    uit.add(arg.value)
    return uit


def controle(namen: list[str] | None = None) -> dict:
    paden = [BRON / naam for naam in namen] if namen else sorted(p for p in BRON.glob("*.py") if p.name != "taal.py")
    delen = {pad.name: json.loads(pad.read_text(encoding="utf-8")) for pad in sorted(ENGELS.glob("*.json"))}
    samen: dict[str, str] = {}
    verschillend = []
    for deel, lijst in delen.items():
        for nl, en in lijst.items():
            if nl in samen and samen[nl] != en:
                verschillend.append(f"{nl!r} ({deel}: {en!r}, eerder: {samen[nl]!r})")
            samen.setdefault(nl, en)
    ontbreekt = {}
    for pad in paden:
        mist = sorted(z for z in _zinnen(pad) if z not in samen)
        if mist:
            ontbreekt[pad.name] = mist
    waarden = lambda s: ",".join(sorted(re.findall(r"\{(\w+)\}", s)))  # noqa: E731
    scheef = [nl for nl, en in samen.items() if waarden(nl) != waarden(en)]
    streep = [nl for nl, en in samen.items() if re.search(r"\s[—–]\s", en)]
    return {"ontbreekt": ontbreekt, "verschillend": verschillend, "scheef": scheef, "streep": streep}


if __name__ == "__main__":
    uit = controle(sys.argv[1:] or None)
    fout = 0
    for pad, mist in uit["ontbreekt"].items():
        fout += len(mist)
        print(f"{pad}: {len(mist)} zonder Engels")
        for zin in mist:
            print(f"    {zin!r}")
    for kop, sleutel in (("anders vertaald in twee bestanden", "verschillend"), ("andere waarden tussen accolades", "scheef"), ("gedachtestreepje", "streep")):
        if uit[sleutel]:
            fout += len(uit[sleutel])
            print(f"{kop}:")
            for regel in uit[sleutel]:
                print(f"    {regel}")
    print(f"\n{fout} punten" if fout else "Alles vertaald.")
    sys.exit(1 if fout else 0)
