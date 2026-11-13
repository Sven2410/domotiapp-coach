"""Vraag het de DomotiTech Bot (v0.220.0): een doorlopend gesprek en tickets van het huis, met foto's.

De eigenaar op 12-11-2026: "Kunnen we niet een soort ticket systeem maken dat klanten aanvraag kunnen doen en
ook gewoon normale vragen kunnen stellen [...] Ik wil het centraal houden dus het moet in een popup komen zoals
Vraag het de DomotiTech Bot". En op 13-11-2026: "Gewoon een vraag stellen over de installatie en echt een ticket
aan maken zijn aparte dingen." Dus:

- **het gesprek**: één doorlopende chat per huis, met de vorm van een ticket, `id` 0 en soort `vraag`, zonder
  stand en zonder onderwerp. Het bestaat altijd, desnoods leeg;
- **tickets**: een storing of een aanvraag, met een nummer, een stand en eventueel foto's (`bijlagen`).

De bewoner stelt zijn vraag in Home Assistant (de knop in het paneel of de kaart van DomotiApp Lovelace), de coach
bewaart het en geeft een gebeurtenis af, en het antwoord komt van een beheerder terug in hetzelfde venster, met een
pushmelding.

Kent Home Assistant niet: alles werkt op het opgeslagen geheel `{"volgende", "gesprek", "tickets", "bijlagen"}`. De
opslag staat in storage.py (`TicketsStore`), de websocket in websocket.py, de foto's zelf in bijlagen.py.

Het contract met de kaart en met wie de vragen beantwoordt is `CONTRACT`: toevoegen mag, hernoemen of weghalen
alleen met een hoger getal, zoals bij de entiteiten (`CONTRACT` in entiteit.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .taal import t

CONTRACT = 1

GESPREK = 0
SOORTEN = ("storing", "aanvraag")
# nieuw: net binnen; in_behandeling: er is geantwoord of er wordt aan gewerkt; bij_beheerder: ligt bij de beheerder
# ter beslissing; klaar.
STANDEN = ("nieuw", "in_behandeling", "bij_beheerder", "klaar")

TEKST_MAX = 4000
ONDERWERP_MAX = 80
# Hoeveel nieuwe tickets één gebruiker per uur mag maken, hoeveel berichten in het gesprek, en hoeveel `lijst`
# er teruggeeft: tickets, en de laatste berichten van het gesprek.
PER_UUR = 20
GESPREK_PER_UUR = 60
LIJST_MAX = 200
GESPREK_MAX = 100

# Foto's: welke soorten (op de eerste bytes, niet op wat de browser zegt), hoe groot, hoeveel per bericht, en hoe
# lang een foto die nergens aan hangt blijft.
BIJLAGE_SOORTEN = ("image/jpeg", "image/png", "image/webp")
BIJLAGE_MAX = 10 * 1024 * 1024
BIJLAGEN_PER_BERICHT = 4
BIJLAGE_LOS = timedelta(hours=1)

KLANT = "klant"
DOMOTITECH = "domotitech"


class TicketFout(ValueError):
    """Een vraag die niet kan; `code` gaat als foutcode over de websocket."""

    def __init__(self, code: str, tekst: str) -> None:
        super().__init__(tekst)
        self.code = code


def _gesprek_leeg() -> dict[str, Any]:
    return {"id": GESPREK, "soort": "vraag", "berichten": [], "gelezen": {}, "bijgewerkt": None}


def leeg() -> dict[str, Any]:
    """Het opgeslagen geheel van een huis zonder tickets."""
    return {"volgende": 1, "gesprek": _gesprek_leeg(), "tickets": [], "bijlagen": {}}


def heel(data: dict[str, Any]) -> dict[str, Any]:
    """Wat er van een eerdere vorm mist, erbij; voor het laden."""
    data.setdefault("volgende", 1)
    data.setdefault("tickets", [])
    data.setdefault("bijlagen", {})
    if not isinstance(data.get("gesprek"), dict):
        data["gesprek"] = _gesprek_leeg()
    return data


def soort_van(bestand: bytes) -> str | None:
    """De soort van een foto aan de eerste bytes, of None als het geen jpeg, png of webp is."""
    if bestand[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if bestand[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if bestand[:4] == b"RIFF" and bestand[8:12] == b"WEBP":
        return "image/webp"
    return None


def _stempel(at: datetime) -> str:
    return at.replace(microsecond=0).isoformat()


def _moment(tekst: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(tekst))
    except ValueError:
        return None


def _sinds(moment: datetime, grens: datetime) -> bool:
    """Of `moment` op of na `grens` valt. Met tijdzone, zoals de coach ze schrijft, vergelijkt Python het echte
    moment, ook in het uur dat bij de wintertijd twee keer komt; zonder (een oude of een nagemaakte) de kloktijd."""
    if (moment.tzinfo is None) != (grens.tzinfo is None):
        return moment.replace(tzinfo=None) >= grens.replace(tzinfo=None)
    return moment >= grens


def _tekst(tekst: Any, mag_leeg: bool = False) -> str:
    """1 tot `TEKST_MAX` tekens, gewone tekst; witruimte eromheen eraf. Leeg mag alleen met een foto."""
    schoon = str(tekst or "").strip()
    if not schoon and not mag_leeg:
        raise TicketFout("leeg", t("De tekst is leeg."))
    if len(schoon) > TEKST_MAX:
        raise TicketFout("te_lang", t("De tekst is langer dan {n} tekens.", n=TEKST_MAX))
    return schoon


def onderwerp(tekst: str) -> str:
    """De eerste regel, hoogstens `ONDERWERP_MAX` tekens."""
    regel = next((r.strip() for r in str(tekst).splitlines() if r.strip()), "")
    return regel if len(regel) <= ONDERWERP_MAX else regel[: ONDERWERP_MAX - 1].rstrip() + "…"


def zoek(data: dict[str, Any], ticket_id: Any) -> dict[str, Any]:
    """Het gesprek (0) of het ticket met dit nummer, of een `TicketFout`."""
    if ticket_id == GESPREK:
        return heel(data)["gesprek"]
    for ticket in data.get("tickets") or []:
        if ticket.get("id") == ticket_id:
            return ticket
    raise TicketFout("niet_gevonden", t("Ticket {nr} bestaat niet.", nr=ticket_id))


def bijlage_erbij(data: dict[str, Any], bijlage_id: str, soort: str, grootte: int, at: datetime) -> dict[str, Any]:
    """Een geüploade foto, nog nergens aan vast; wat de websocket en de kaart ervan zien."""
    if soort not in BIJLAGE_SOORTEN:
        raise TicketFout("bijlage_soort", t("Alleen een foto: jpeg, png of webp."))
    if grootte > BIJLAGE_MAX:
        raise TicketFout("bijlage_groot", t("Een foto is hoogstens {mb} MB.", mb=BIJLAGE_MAX // (1024 * 1024)))
    heel(data)["bijlagen"][bijlage_id] = {"type": soort, "grootte": int(grootte), "at": _stempel(at), "ticket": None}
    return {"id": bijlage_id, "type": soort, "grootte": int(grootte)}


def _vastmaken(data: dict[str, Any], ticket: dict[str, Any], ids: list[str] | None) -> list[dict[str, Any]]:
    """De foto's bij een bericht: bestaan, nog los, hoogstens `BIJLAGEN_PER_BERICHT`, en niet in het gesprek."""
    ids = list(dict.fromkeys(ids or []))
    if not ids:
        return []
    if ticket.get("id") == GESPREK:
        raise TicketFout("bijlage_gesprek", t("Een foto hoort bij een ticket, niet bij een vraag."))
    if len(ids) > BIJLAGEN_PER_BERICHT:
        raise TicketFout("bijlage_te_veel", t("Hoogstens {n} foto's per bericht.", n=BIJLAGEN_PER_BERICHT))
    alle = heel(data)["bijlagen"]
    uit = []
    for bijlage_id in ids:
        rij = alle.get(bijlage_id)
        if rij is None or rij.get("ticket") is not None:
            raise TicketFout("bijlage_onbekend", t("Die foto bestaat niet (meer). Voeg hem opnieuw toe."))
        rij["ticket"] = ticket["id"]
        uit.append({"id": bijlage_id, "type": rij["type"], "grootte": rij["grootte"]})
    return uit


def opruimen(data: dict[str, Any], at: datetime) -> list[str]:
    """Foto's die al `BIJLAGE_LOS` nergens aan hangen gaan weg; de ids, om de bestanden weg te halen."""
    weg = []
    for bijlage_id, rij in list(heel(data)["bijlagen"].items()):
        moment = _moment(rij.get("at"))
        if rij.get("ticket") is None and (moment is None or not _sinds(moment, at - BIJLAGE_LOS)):
            weg.append(bijlage_id)
            del data["bijlagen"][bijlage_id]
    return weg


def _bericht(
    ticket: dict[str, Any], van: str, naam: str, tekst: str, at: datetime,
    user_id: str | None = None, bijlagen: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    berichten = ticket.setdefault("berichten", [])
    bericht = {
        "id": max((int(b.get("id") or 0) for b in berichten), default=0) + 1,
        "van": van, "naam": naam, "tekst": tekst, "at": _stempel(at),
    }
    if user_id is not None:
        bericht["user_id"] = user_id
    if bijlagen:
        bericht["bijlagen"] = bijlagen
    berichten.append(bericht)
    ticket["bijgewerkt"] = bericht["at"]
    return bericht


def nieuw(
    data: dict[str, Any], soort: str, tekst: Any, user_id: str, naam: str, at: datetime,
    bijlagen: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Een nieuw ticket (storing of aanvraag) met het eerste bericht; (ticket, bericht).

    Nummers lopen per huis op en worden nooit hergebruikt (`volgende`). Hoogstens `PER_UUR` per gebruiker. Een
    vraag is geen ticket: die gaat in het gesprek (`reageer` op 0).
    """
    heel(data)
    if soort not in SOORTEN:
        raise TicketFout("soort", t("Onbekende soort: {soort}.", soort=soort))
    schoon = _tekst(tekst, mag_leeg=bool(bijlagen))
    recent = sum(
        1 for ticket in data["tickets"]
        if (ticket.get("door") or {}).get("user_id") == user_id
        and (moment := _moment(ticket.get("gemaakt"))) is not None and _sinds(moment, at - timedelta(hours=1))
    )
    if recent >= PER_UUR:
        raise TicketFout("te_veel", t("Je kunt hoogstens {n} nieuwe tickets per uur maken. Probeer het straks opnieuw.",
                                      n=PER_UUR))
    nummer = max(int(data.get("volgende") or 1),
                 max((int(tk.get("id") or 0) for tk in data["tickets"]), default=0) + 1)
    ticket = {
        "id": nummer, "soort": soort, "stand": "nieuw", "onderwerp": onderwerp(schoon) or t("Foto"),
        "gemaakt": _stempel(at), "bijgewerkt": _stempel(at),
        "door": {"user_id": user_id, "naam": naam}, "berichten": [], "gelezen": {},
    }
    vast = _vastmaken(data, ticket, bijlagen)
    data["volgende"] = nummer + 1
    bericht = _bericht(ticket, KLANT, naam, schoon, at, user_id, vast)
    ticket["gelezen"][user_id] = bericht["id"]
    data["tickets"].append(ticket)
    return ticket, bericht


def reageer(
    data: dict[str, Any], ticket_id: Any, tekst: Any, user_id: str, naam: str, at: datetime,
    bijlagen: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Een bericht van de bewoner: een vraag in het gesprek (0), of een reactie op een ticket. Een ticket dat klaar
    was gaat terug naar `nieuw`. In het gesprek hoogstens `GESPREK_PER_UUR` berichten per gebruiker."""
    ticket = zoek(data, ticket_id)
    schoon = _tekst(tekst, mag_leeg=bool(bijlagen) and ticket_id != GESPREK)
    if ticket_id == GESPREK:
        recent = sum(
            1 for b in ticket.get("berichten") or []
            if b.get("user_id") == user_id and (moment := _moment(b.get("at"))) is not None
            and _sinds(moment, at - timedelta(hours=1))
        )
        if recent >= GESPREK_PER_UUR:
            raise TicketFout("te_veel", t("Je kunt hoogstens {n} vragen per uur stellen. Probeer het straks opnieuw.",
                                          n=GESPREK_PER_UUR))
    vast = _vastmaken(data, ticket, bijlagen)
    bericht = _bericht(ticket, KLANT, naam, schoon, at, user_id, vast)
    if ticket.get("stand") == "klaar":
        ticket["stand"] = "nieuw"
    ticket.setdefault("gelezen", {})[user_id] = bericht["id"]
    return ticket, bericht


def antwoord(
    data: dict[str, Any], ticket_id: Any, tekst: Any, at: datetime, stand: str | None = None,
    naam: str = "DomotiTech",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Een antwoord van DomotiTech; bij een ticket wordt de stand `stand`, of `in_behandeling`. Het gesprek heeft
    geen stand."""
    ticket = zoek(data, ticket_id)
    if ticket_id != GESPREK:
        nieuw_stand = stand or "in_behandeling"
        if nieuw_stand not in STANDEN:
            raise TicketFout("stand", t("Onbekende stand: {stand}.", stand=nieuw_stand))
        ticket["stand"] = nieuw_stand
    bericht = _bericht(ticket, DOMOTITECH, naam, _tekst(tekst), at)
    return ticket, bericht


def zet_stand(data: dict[str, Any], ticket_id: Any, stand: str, at: datetime) -> dict[str, Any]:
    """Alleen de stand van een ticket; geen bericht. Het gesprek heeft geen stand."""
    if ticket_id == GESPREK:
        raise TicketFout("stand", t("Het gesprek heeft geen stand."))
    if stand not in STANDEN:
        raise TicketFout("stand", t("Onbekende stand: {stand}.", stand=stand))
    ticket = zoek(data, ticket_id)
    ticket["stand"] = stand
    ticket["bijgewerkt"] = _stempel(at)
    return ticket


def gelezen(data: dict[str, Any], ticket_id: Any, user_id: str) -> dict[str, Any]:
    """Deze gebruiker zag alles wat er nu in het ticket of het gesprek staat."""
    ticket = zoek(data, ticket_id)
    laatste = max((int(b.get("id") or 0) for b in ticket.get("berichten") or []), default=0)
    ticket.setdefault("gelezen", {})[user_id] = laatste
    return ticket


def voor_buiten(ticket: dict[str, Any]) -> dict[str, Any]:
    """Wat er over de websocket gaat: van het gesprek de laatste `GESPREK_MAX` berichten."""
    if ticket.get("id") != GESPREK:
        return ticket
    return {**ticket, "berichten": list(ticket.get("berichten") or [])[-GESPREK_MAX:]}


def lijst(data: dict[str, Any]) -> list[dict[str, Any]]:
    """De tickets, nieuwste eerst (op het laatste bericht), hoogstens `LIJST_MAX`. Het gesprek staat er niet in."""
    tickets = sorted(data.get("tickets") or [], key=lambda tk: (str(tk.get("bijgewerkt") or ""), tk.get("id") or 0),
                     reverse=True)
    return tickets[:LIJST_MAX]


def overzicht(data: dict[str, Any]) -> dict[str, Any]:
    """Het antwoord van `list` en het eerste event van `subscribe`."""
    return {"contract": CONTRACT, "gesprek": voor_buiten(heel(data)["gesprek"]), "tickets": lijst(data)}
