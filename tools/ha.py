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
import sys
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

    # Het token is zelf een reeks punten en letters, dus zoek de adressen in
    # wat eromheen staat. Anders leest hij een stuk van het token als adres.
    rest = tekst.replace(jwt.group(0), " ")
    adressen = [_host(m) for m in ADRES.finditer(rest)]
    if not adressen:
        raise ValueError(
            f"In het tokenbestand van '{naam}' staat geen adres. Zet het IP of de "
            "hostnaam van Home Assistant op een eigen regel."
        )
    # Dubbele eruit, volgorde houden: die volgorde is de voorkeur.
    uniek = list(dict.fromkeys(adressen))
    return jwt.group(0), uniek


def _host(m: "re.Match") -> str:
    """Een gevonden adres als host:poort.

    Een poort erbij verzinnen mag alleen bij een kaal IP, want daar is 8123 de
    gewoonte. Nabu Casa draait op 443 en niet op 8123: stond er 8123 achter een
    nabu.casa-naam, dan gaf dat een verbindingsfout die eruitzag als een
    verkeerd token.
    """
    naam, poort = m.group(1), m.group(2)
    if poort:
        return f"{naam}:{poort}"
    kaal_ip = re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", naam)
    return f"{naam}:8123" if kaal_ip else f"{naam}:443"


def schema_van(host: str) -> str:
    """Https overal behalve op een kaal IP: een Home Assistant op het eigen
    netwerk draait meestal zonder certificaat, en dan geeft https een SSL-fout.
    """
    return "http" if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}:\d+", host) else "https"


# Hoe lang een adres de tijd krijgt om te laten weten dat het bestaat. Kort,
# want het thuisadres wordt ook geprobeerd als je niet thuis bent.
PROBE_SECONDEN = 4

NAAM = os.environ.get("HA_INSTALLATIE", "thuis")

try:
    TOKEN, ADRESSEN = lees(NAAM)
except (FileNotFoundError, ValueError) as _reden:
    # Een naam die niet bestaat is bijna altijd een typefout, en dan help je
    # meer met de lijst die er wel is dan met een traceback van tien regels.
    print(f"[ha] {_reden}", file=sys.stderr)
    _aanwezig = sorted(
        {p.stem for m in MAPPEN if m.is_dir() for p in m.glob("*.txt")}
    )
    if _aanwezig:
        print("[ha] wel aanwezig: " + ", ".join(_aanwezig), file=sys.stderr)
    print(f"[ha] aanmaken met: cd tokens && ./nieuw.sh {NAAM}", file=sys.stderr)
    raise SystemExit(1) from None

HOST = ADRESSEN[0]
SCHEMA = schema_van(HOST)
# Met één adres valt er niets te kiezen, en dan blijft de foutmelding bij een
# mislukte verbinding die van de verbinding zelf in plaats van een opsomming.
_gekozen = len(ADRESSEN) == 1


def _meld(naam: str) -> None:
    """Eén regel naar stderr: tegen welke installatie er gemeten wordt.

    Zonder dit schrijft een logger die een uur meeloopt stilzwijgend de
    verkeerde installatie mee, en dat merk je pas achteraf. Naar stderr en niet
    naar stdout, zodat het doorpijpen van een tool blijft werken. Uit te zetten
    met HA_STIL=1, voor als een script zijn eigen kop schrijft.
    """
    if os.environ.get("HA_STIL"):
        return
    if os.environ.get("HA_TOKEN_FILE"):
        waar = "uit HA_TOKEN_FILE"
    elif os.environ.get("HA_INSTALLATIE"):
        waar = "uit HA_INSTALLATIE"
    else:
        waar = "standaard, HA_INSTALLATIE is niet gezet"
    print(f"[ha] installatie: {naam} ({waar})", file=sys.stderr)


_meld(NAAM)


def _haal(host: str, path: str, timeout: int):
    req = urllib.request.Request(
        f"{schema_van(host)}://{host}{path}",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def verbind() -> str:
    """Het eerste adres uit het bestand dat antwoord geeft.

    Zo werkt hetzelfde bestand thuis op het eigen netwerk en onderweg via Nabu
    Casa, zonder dat er iets omgezet hoeft te worden. De volgorde in het bestand
    is de voorkeur: zet het adres op het eigen netwerk bovenaan, want dat is
    sneller en het verkeer blijft binnen.
    """
    global HOST, SCHEMA, _gekozen
    fouten = []
    for host in ADRESSEN:
        try:
            _haal(host, "/api/", PROBE_SECONDEN)
        except Exception as e:  # noqa: BLE001 - elke reden telt als "niet deze"
            fouten.append(f"  {schema_van(host)}://{host} -> {e}")
            continue
        HOST, SCHEMA, _gekozen = host, schema_van(host), True
        return HOST
    raise ConnectionError(
        f"Geen van de adressen van '{NAAM}' gaf antwoord:\n" + "\n".join(fouten)
    )


def host() -> str:
    """Het adres dat werkt, zo nodig eerst opgezocht."""
    if not _gekozen:
        verbind()
    return HOST


def kies(naam: str) -> str:
    """Overstappen naar een andere installatie, binnen hetzelfde script."""
    global NAAM, TOKEN, ADRESSEN, HOST, SCHEMA, _gekozen
    NAAM = naam
    TOKEN, ADRESSEN = lees(naam)
    HOST = ADRESSEN[0]
    SCHEMA = schema_van(HOST)
    _gekozen = len(ADRESSEN) == 1
    _meld(naam)
    return HOST


def get(path: str):
    """Een GET op de REST-API. Alleen lezen; er is bewust geen post."""
    return _haal(host(), path, 20)


def states() -> dict:
    """Alle huidige toestanden, op entiteit-id."""
    return {s["entity_id"]: s for s in get("/api/states")}


if __name__ == "__main__":
    print(f"installatie : {NAAM}")
    print(f"bestand     : {zoek_bestand(NAAM)}")
    if len(ADRESSEN) > 1:
        print(f"adressen    : {len(ADRESSEN)}, in volgorde van voorkeur")
        for a in ADRESSEN:
            print(f"              {schema_van(a)}://{a}")
    alles = states()
    print(f"verbonden   : {SCHEMA}://{HOST}")
    print(f"bereikbaar  : ja, {len(alles)} entiteiten")
