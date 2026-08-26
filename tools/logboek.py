"""Een periode uit de recorder van Home Assistant op één tijdlijn.

    python tools/logboek.py 2026-08-25T18:00 2026-08-26T12:00
    python tools/logboek.py 2026-08-29T06:00                    # tot nu
    python tools/logboek.py 2026-08-29T06:00 sensor.iets_erbij
    python tools/logboek.py 2026-08-29T06:00 --alles           # ook het gerimpel

Alleen de overgangen, niet elke meting, want anders lees je duizend regels
waarin niets gebeurt.

Welke entiteiten erin horen verschilt per installatie, dus die worden niet
geraden maar opgevraagd bij het paneel zelf (`domotiapp_coach/settings/get`).
Dat zijn per definitie precies de sensoren waar de coach zijn besluiten op
neemt, en het werkt daarmee net zo goed bij een klant als thuis.

Per entiteit los opgehaald en altijd met `end_time` erbij: zonder dat geeft de
history-API maar één dag vanaf de starttijd terug en denk je dat de recorder
gestopt is.
"""

import datetime as dt
import sys
import urllib.parse

import ha
import ws

# Hoe de velden uit de instellingen op de kaart heten. De sleutel is wat het
# paneel gebruikt, de waarde wat er in de tijdlijn moet staan.
VELDEN = {
    "status": "status",
    "current": "stroom A",
    "dynamic_limit": "coach schrijft A",
    "max_limit": "laderlimiet A",
    "lifetime_energy": "teller kWh",
    "no_current_reason": "geen stroom want",
}


def uit_instellingen() -> dict[str, str]:
    """De entiteiten die het paneel voor zijn laadpunten heeft ingevuld."""
    w = ws.WS()
    instellingen = w.vraag("domotiapp_coach/settings/get")
    uit: dict[str, str] = {}

    for apparaat in instellingen.get("devices") or []:
        if apparaat.get("type") != "laadpaal":
            continue
        naam = apparaat.get("name") or "laadpaal"
        if apparaat.get("entity"):
            uit[apparaat["entity"]] = f"{naam} vermogen W"
        for sleutel, label in VELDEN.items():
            entiteit = (apparaat.get("entities") or {}).get(sleutel)
            if entiteit:
                uit[entiteit] = f"{naam} {label}"
        for auto in apparaat.get("cars") or []:
            if auto.get("soc_entity"):
                uit[auto["soc_entity"]] = f"{auto.get('name') or 'auto'} accu %"

    bronnen = instellingen.get("sources") or {}
    for sleutel, label in (("grid_import", "afname W"), ("grid_export", "teruglevering W")):
        if bronnen.get(sleutel):
            uit[bronnen[sleutel]] = label

    return uit


# Hoeveel een meetwaarde moet bewegen voor hij een regel waard is, en hoe vaak
# hij dat hoogstens mag. Zonder dit verzuipt een tijdlijn in de netafname: die
# verspringt elke twee seconden een paar watt en levert vierhonderd regels op
# waarin niets gebeurt. Een status of een reden is geen meetwaarde en komt er
# altijd doorheen, want daar is elke overgang juist het nieuws.
DEMPING = dt.timedelta(seconds=60)
BEWEGING = 0.05


def getal(waarde):
    """De waarde als getal, of niets als het een woord is."""
    try:
        return float(waarde)
    except (TypeError, ValueError):
        return None


def toon(laatst, moment, waarde) -> bool:
    """Of deze overgang een regel waard is."""
    if laatst is None:
        return True
    nu = getal(waarde)
    if nu is None:
        return True  # een woord: elke overgang telt
    was = getal(laatst[1])
    if was is None:
        return True  # van onbekend naar een getal is nieuws
    if moment - laatst[0] < DEMPING:
        return False
    return abs(nu - was) > max(abs(was) * BEWEGING, 0.01)


def haal(entiteit: str, start: dt.datetime, eind: dt.datetime) -> list:
    pad = (
        f"/api/history/period/{start.isoformat()}"
        f"?end_time={urllib.parse.quote(eind.isoformat())}"
        f"&filter_entity_id={entiteit}&minimal_response"
    )
    reeksen = ha.get(pad)
    return reeksen[0] if reeksen else []


def main() -> None:
    argumenten = sys.argv[1:]
    if not argumenten:
        print(__doc__)
        return

    argumenten = [a for a in argumenten if a != "--alles"]
    losse = [a for a in argumenten if "." in a and not a[0].isdigit()]
    tijden = [a for a in argumenten if a not in losse]
    start = dt.datetime.fromisoformat(tijden[0])
    eind = dt.datetime.fromisoformat(tijden[1]) if len(tijden) > 1 else dt.datetime.now()

    entiteiten = uit_instellingen()
    for e in losse:
        entiteiten.setdefault(e, e.split(".", 1)[-1][:18])

    alles = "--alles" in sys.argv
    tijdlijn = []
    for entiteit, label in entiteiten.items():
        vorig = None
        laatst_getoond = None
        for punt in haal(entiteit, start, eind):
            waarde = punt.get("state")
            if waarde == vorig:
                continue
            vorig = waarde
            moment = dt.datetime.fromisoformat(punt["last_changed"]).astimezone()
            if not alles and not toon(laatst_getoond, moment, waarde):
                continue
            laatst_getoond = (moment, waarde)
            tijdlijn.append((moment, label, waarde))

    tijdlijn.sort(key=lambda r: r[0])
    breed = max((len(l) for _, l, _ in tijdlijn), default=10)
    for moment, label, waarde in tijdlijn:
        print(f"{moment:%d-%m %H:%M:%S}  {label:{breed}} {str(waarde)[:38]}")
    print(
        f"\n{len(tijdlijn)} overgangen over {len(entiteiten)} entiteiten, "
        f"{start:%d-%m %H:%M} tot {eind:%d-%m %H:%M}, installatie '{ha.NAAM}'"
    )


if __name__ == "__main__":
    main()
