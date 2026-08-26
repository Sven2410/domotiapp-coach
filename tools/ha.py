"""Lezen uit een Home Assistant. Schrijft nooit iets.

Werkt op elke machine, want het token staat nergens in deze repo. Waar hij hem
zoekt staat in `zoek_bestand` hieronder; de bedoeling is dat je meerdere
installaties naast elkaar kunt hebben (thuis, en een per klant) zonder telkens
een pad aan te passen.

Gebruik:

    import ha
    ha.states()                      # de installatie uit HA_INSTALLATIE, of "thuis"
    ha.kies("klant-jansen")          # overstappen naar een andere
    ha.get("/api/config")

Het tokenbestand is vormvrij: het eerste dat op een JWT lijkt is het token, en
het eerste dat op een adres lijkt is de host. Zo blijft een bestand dat met de
hand is volgeplakt gewoon werken.
"""

import json
import os
import pathlib
import re
import urllib.request

# Waar een tokenbestand kan staan, in volgorde van voorkeur. Alles buiten de
# repo, want dit hoort op geen enkele remote, ook niet op een privé.
MAPPEN = [
    pathlib.Path.home() / "dev" / "tokens",
    pathlib.Path("C:/dev/tokens"),
    pathlib.Path.home() / ".ha-tokens",
]

# Waar het vroeger stond, toen er nog één installatie was. Blijft werken.
OUDE_PADEN = [
    pathlib.Path("C:/dev/ha-token.txt"),
    pathlib.Path.home() / "dev" / "ha-token.txt",
]

JWT = re.compile(r"ey[A-Za-z0-9_\-\.]{40,}")
ADRES = re.compile(r"(?:https?://)?(\d{1,3}(?:\.\d{1,3}){3}|[a-z0-9\-\.]+\.[a-z]{2,})(?::(\d+))?")


def zoek_bestand(naam: str) -> pathlib.Path:
    """Het tokenbestand van deze installatie, of een uitleg waarom niet."""
    eigen = os.environ.get("HA_TOKEN_FILE")
    if eigen:
        pad = pathlib.Path(eigen)
        if pad.exists():
            return pad
        raise FileNotFoundError(f"HA_TOKEN_FILE wijst naar {pad}, en die bestaat niet.")

    for map_ in MAPPEN:
        pad = map_ / f"{naam}.txt"
        if pad.exists():
            return pad

    if naam == "thuis":
        for pad in OUDE_PADEN:
            if pad.exists():
                return pad

    gezocht = "\n  ".join(str(m / f"{naam}.txt") for m in MAPPEN)
    raise FileNotFoundError(
        f"Geen tokenbestand voor '{naam}'. Gezocht in:\n  {gezocht}\n"
        "Maak er een aan met het adres op de ene regel en het token op de andere, "
        "of zet HA_TOKEN_FILE naar het bestand."
    )


def lees(naam: str) -> tuple[str, str]:
    """Het token en de host uit het bestand van deze installatie."""
    tekst = zoek_bestand(naam).read_text(encoding="utf-8", errors="ignore")

    jwt = JWT.search(tekst)
    if not jwt:
        raise ValueError(f"In het tokenbestand van '{naam}' staat geen token.")

    # Het token is zelf een reeks punten en letters, dus zoek de host in wat
    # eromheen staat. Anders leest hij een stuk van het token als adres.
    rest = tekst.replace(jwt.group(0), " ")
    adres = ADRES.search(rest)
    if not adres:
        raise ValueError(
            f"In het tokenbestand van '{naam}' staat geen adres. Zet het IP of de "
            "hostnaam van Home Assistant op een eigen regel."
        )
    host = adres.group(1) + ":" + (adres.group(2) or "8123")
    return jwt.group(0), host


NAAM = os.environ.get("HA_INSTALLATIE", "thuis")
TOKEN, HOST = lees(NAAM)

# Https alleen waar het geen kaal IP is: een Home Assistant op het thuisnetwerk
# draait meestal zonder certificaat, en dan geeft https een SSL-fout.
SCHEMA = "http" if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}:\d+", HOST) else "https"


def kies(naam: str) -> str:
    """Overstappen naar een andere installatie, binnen hetzelfde script."""
    global NAAM, TOKEN, HOST, SCHEMA
    NAAM = naam
    TOKEN, HOST = lees(naam)
    SCHEMA = "http" if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}:\d+", HOST) else "https"
    return HOST


def get(path: str):
    """Een GET op de REST-API. Alleen lezen; er is bewust geen post."""
    req = urllib.request.Request(
        f"{SCHEMA}://{HOST}{path}",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def states() -> dict:
    """Alle huidige toestanden, op entiteit-id."""
    return {s["entity_id"]: s for s in get("/api/states")}


if __name__ == "__main__":
    print(f"installatie : {NAAM}")
    print(f"bestand     : {zoek_bestand(NAAM)}")
    print(f"adres       : {SCHEMA}://{HOST}")
    alles = states()
    print(f"bereikbaar  : ja, {len(alles)} entiteiten")
