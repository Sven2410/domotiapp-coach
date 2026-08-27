"""Backticks in CSS-commentaar opsporen, want `node --check` doet dat niet.

De stijlen van het paneel staan in een template literal. Een backtick in een
CSS-commentaar daarbinnen sluit die string af, en wat erna komt wordt als
JavaScript gelezen. Soms geeft dat een parseerfout en soms niet: op 27-08-2026
kwam er een bestand doorheen waar `node --check` groen op gaf, terwijl de
browser de module weigerde met "Unexpected identifier".

    python tools/stijlcheck.py

Geen uitvoer en exitcode 0 betekent schoon.
"""

import pathlib
import re
import sys

MAP = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components"
    / "domotiapp_coach"
    / "frontend"
    / "src"
)

# Waar een stijlblok begint. Het paneel schrijft dat overal hetzelfde op, met
# de /* css */ ervoor die editors gebruiken om er CSS in te kleuren.
START = re.compile(r"/\* css \*/\s*`")


def stijlblokken(tekst: str):
    """De inhoud van elk stijlblok, met de regel waarop het begint."""
    for match in START.finditer(tekst):
        begin = match.end()
        # Tot de eerstvolgende backtick die niet ontsnapt is. Loopt het blok
        # verder dan de bedoeling, dan is dat juist het probleem dat we zoeken,
        # en dan valt het commentaar met de backtick er alsnog binnen.
        i = begin
        while i < len(tekst):
            if tekst[i] == "\\":
                i += 2
                continue
            if tekst[i] == "`":
                break
            i += 1
        yield tekst.count("\n", 0, begin) + 1, tekst[begin:i]


def main() -> int:
    fout = 0
    for pad in sorted(MAP.rglob("*.js")):
        tekst = pad.read_text(encoding="utf-8")
        for regel, blok in stijlblokken(tekst):
            # Een stijlblok dat middenin een commentaar ophoudt, is afgesloten
            # door een backtick die ín dat commentaar stond. Dat is het kenmerk
            # waar het om gaat. Zoeken naar backticks binnen het blok werkt
            # niet: het blok houdt juist bij die backtick op, dus het
            # commentaar valt er dan buiten.
            rest = re.sub(r"/\*.*?\*/", "", blok, flags=re.S)
            if "/*" not in rest:
                continue
            staart = " ".join(rest[rest.index("/*"):].split())[:90]
            naam = pad.relative_to(MAP)
            print(f"{naam}: het stijlblok op regel {regel} eindigt middenin een commentaar.")
            print(f"  {staart}")
            print("  Er staat vrijwel zeker een backtick in dat commentaar.")
            fout += 1
    if fout:
        print(f"\n{fout} gevonden. Een backtick sluit de stijlstring af; haal hem weg.")
    return 1 if fout else 0


if __name__ == "__main__":
    sys.exit(main())
