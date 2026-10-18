"""Wanneer een herinnering aan de beurt is. Kent Home Assistant niet.

De eigenaar op 18-10-2026: "ik wil een soort berichtenbox met zo'n 1tje wat
optelt en dat je dat kan wegvinken van is gelezen bijvoorbeeld. Berichten zoals
denk aan je meterstanden doorgeven en contract loopt bijna af komen daar in. Ook
wil ik een invulveld voor herinnering meterstanden doorgeven." En de bewoner van
de eerste woning: "verschillende looptijden, dus ook een melding van contract
bijna verlopen."

Hier staat alleen wanneer iets aan de beurt is en wat erin staat. Bewaren
(`BerichtenStore` in storage.py) en versturen doet de coach. Elk bericht heeft
een `sleutel`; staat die er al, dan komt hij er niet nog eens bij, ook niet na
een herstart.
"""

from __future__ import annotations

from datetime import date, timedelta

# Hoeveel dagen voor het einde van een vast contract het bericht komt, als de
# klant niets anders koos (v0.130.0). Een keuze en geen meting: een maand is
# genoeg om te vergelijken en over te stappen, en hij staat als veld bij de
# looptijd.
HERINNER_DAGEN = 30

# Hoe lang na het einde het bericht "is afgelopen" nog komt. Wie het een week
# na dato voor het eerst ziet, heeft er nog wat aan; daarna niet meer.
NA_AFLOOP = timedelta(days=7)

HERHALINGEN = {"once": 0, "month": 1, "quarter": 3, "year": 12}


def _datum(tekst) -> date | None:
    try:
        return date.fromisoformat(str(tekst)[:10]) if tekst else None
    except ValueError:
        return None


def _plus_maanden(dag: date, maanden: int) -> date:
    jaar = dag.year + (dag.month - 1 + maanden) // 12
    maand = (dag.month - 1 + maanden) % 12 + 1
    # De 31e van een maand met dertig dagen wordt de laatste.
    for d in (dag.day, 30, 29, 28):
        try:
            return date(jaar, maand, d)
        except ValueError:
            continue
    return date(jaar, maand, 28)


def _keer(vandaag: date, eerste: date, stap: int) -> int:
    """Hoeveel stappen na de eerste keer de laatste keer op of voor vandaag valt."""
    n = ((vandaag.year - eerste.year) * 12 + vandaag.month - eerste.month) // stap
    while n > 0 and _plus_maanden(eerste, n * stap) > vandaag:
        n -= 1
    return max(n, 0)


def meterstand_wanneer(vandaag: date, start, herhaling: str) -> date | None:
    """De laatste keer op of voor vandaag dat de meterstanden aan de beurt waren, of None.

    `start` is de eerste keer ("2026-11-01"), `herhaling` een van `HERHALINGEN`.
    Eenmalig is alleen die ene dag; daarna niets meer.
    """
    eerste = _datum(start)
    if eerste is None or eerste > vandaag:
        return None
    stap = HERHALINGEN.get(herhaling, 12)
    if stap == 0:
        return eerste
    return _plus_maanden(eerste, _keer(vandaag, eerste, stap) * stap)


def meterstand_volgende(vandaag: date, start, herhaling: str) -> date | None:
    """Wanneer de meterstanden de volgende keer aan de beurt zijn, voor het scherm."""
    eerste = _datum(start)
    if eerste is None:
        return None
    if eerste > vandaag:
        return eerste
    stap = HERHALINGEN.get(herhaling, 12)
    if stap == 0:
        return None
    return _plus_maanden(eerste, (_keer(vandaag, eerste, stap) + 1) * stap)


def meterstand_bericht(vandaag: date, herinnering: dict) -> dict | None:
    """Het bericht over de meterstanden als het aan de beurt is (op die dag of de week erna)."""
    wanneer = meterstand_wanneer(vandaag, herinnering.get("meter_date"), herinnering.get("meter_repeat") or "year")
    if wanneer is None or vandaag - wanneer > NA_AFLOOP:
        return None
    return {
        "sleutel": f"meterstanden:{wanneer.isoformat()}",
        "soort": "meterstanden",
        "titel": "Geef je meterstanden door",
        "tekst": "Je leverancier vraagt je meterstanden. Ze staan op het overzicht onder Je meter.",
    }


def _lang(dag: date) -> str:
    maanden = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
               "september", "oktober", "november", "december"]
    return f"{dag.day} {maanden[dag.month - 1]} {dag.year}"


def contract_berichten(vandaag: date, contract: dict, namen: dict | None = None) -> list[dict]:
    """De berichten over een vast stroom- of gascontract dat bijna afloopt of is afgelopen.

    `namen` zet een id uit de catalogus om in een naam ("zonneplan" naar
    "Zonneplan"); de coach kent de catalogus niet, het paneel stuurt hem niet
    mee, dus zonder staat er gewoon "je stroomcontract".
    """
    uit = []
    for bron, deel in (("stroom", contract), ("gas", contract.get("gas") or {})):
        if (deel.get("type") or "fixed") != "fixed":
            continue
        einde = _datum(deel.get("end"))
        if einde is None:
            continue
        try:
            dagen = int(deel.get("reminder_days", HERINNER_DAGEN))
        except (TypeError, ValueError):
            dagen = HERINNER_DAGEN
        naam = (namen or {}).get(deel.get("supplier") or "", "")
        wat = f"Je {bron}contract{f' bij {naam}' if naam else ''}"
        if dagen > 0 and einde - timedelta(days=dagen) <= vandaag < einde:
            uit.append({
                "sleutel": f"contract:{bron}:{einde.isoformat()}:voor",
                "soort": "contract",
                "titel": f"{wat} loopt af op {_lang(einde)}",
                "tekst": "Kijk of je verlengt of overstapt. Een nieuw contract vul je in bij Contract.",
            })
        if einde <= vandaag <= einde + NA_AFLOOP:
            uit.append({
                "sleutel": f"contract:{bron}:{einde.isoformat()}:af",
                "soort": "contract",
                "titel": f"{wat} is afgelopen",
                "tekst": "Vul je nieuwe contract in bij Contract, zodat de coach met de goede prijzen rekent.",
            })
    return uit


def controle_bericht(vandaag: date, oud: str | None, nieuw: dict) -> dict | None:
    """Het bericht als de prijscontrole omslaat van correct naar een afwijking.

    Eén keer per dag hooguit, en alleen bij een omslag: wie nooit een kloppende
    opbouw had, ziet dat al op Contract en Voorkeuren.
    """
    if oud != "correct" or nieuw.get("status") != "afwijking":
        return None
    verschil = abs(float(nieuw.get("grootste") or 0.0))
    return {
        "sleutel": f"controle:{vandaag.isoformat()}",
        "soort": "prijs",
        "titel": "Je energieprijs klopt niet meer",
        "tekst": (
            f"De opbouw in de coach wijkt € {f'{verschil:.4f}'.replace('.', ',')} per kWh af van wat je leverancier zegt. "
            "Kijk het na bij Voorkeuren onder Je energieprijs."
        ),
    }
