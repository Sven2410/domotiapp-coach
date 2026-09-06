"""Wie welke melding krijgt.

Sven op 06-09-2026: "ik wil dat de klant meldingen kan aan en uit zetten in
het meldingen tabje. Twee in een: de admin voegt de personen toe, en die
persoon ziet alleen zichzelf, met welke soorten meldingen hij of zij krijgt.
En niet telkens onnodig meldingen sturen."

Een persoon is een telefoon (een notify-dienst van Home Assistant) met een
naam, eventueel gekoppeld aan een gebruiker van Home Assistant, en per soort
melding een schakelaar. De soorten zijn dezelfde als in de geschiedenis van
het paneel, plus de zekeringmelding van monitor.py:

  kritiek    wat de bewoner zelf moet oplossen of moet weten voor het misgaat
  melding    de verslagen: vol, kabel eruit, een sensor die het weer doet
  besluit    elk besluit van de coach; standaard uit, want dat zijn er veel
  belasting  de aansluiting wordt te zwaar belast

Dit bestand kent Home Assistant niet en is los te beproeven.
"""

from __future__ import annotations

import copy
import secrets
from typing import Any

SOORTEN: tuple[str, ...] = ("kritiek", "melding", "besluit", "belasting")

# Wat een nieuwe persoon krijgt. Besluiten staan uit: dat is wat de coach elke
# paar minuten doet, en niemand wil daar 's nachts een telefoon van horen.
STANDAARD_SOORTEN: dict[str, bool] = {
    "kritiek": True,
    "melding": True,
    "besluit": False,
    "belasting": True,
}


def naam_uit_doel(target: str) -> str:
    """"mobile_app_iphone_van_sven" leest als "Iphone van sven".

    Dezelfde som als het paneel maakte voor de lijst met ontvangers; goed
    genoeg als eerste naam, en de admin kan hem aanpassen.
    """
    naam = str(target or "").removeprefix("mobile_app_").replace("_", " ").strip()
    return naam[:1].upper() + naam[1:] if naam else str(target or "")


def nieuwe_persoon(
    name: str, target: str, user_id: str = "", kinds: dict[str, bool] | None = None
) -> dict[str, Any]:
    """Eén persoon, met alle soorten ingevuld."""
    soorten = dict(STANDAARD_SOORTEN)
    for soort, aan in (kinds or {}).items():
        if soort in soorten:
            soorten[soort] = bool(aan)
    return {
        "id": f"p-{secrets.token_hex(4)}",
        "name": str(name or "").strip() or naam_uit_doel(target),
        "target": str(target or "").strip(),
        "user_id": str(user_id or ""),
        "kinds": soorten,
    }


def personen(settings: dict[str, Any]) -> list[dict[str, Any]]:
    """De personen uit de instellingen, alleen de rijen die ergens op slaan."""
    uit = []
    for row in (settings.get("notifications") or {}).get("people") or []:
        if isinstance(row, dict) and row.get("target"):
            uit.append(row)
    return uit


def ontvangers(settings: dict[str, Any], soort: str) -> list[str]:
    """De notify-diensten die deze soort melding willen, zonder dubbelen.

    Een onbekende soort levert niemand op: liever een melding die niet
    verstuurd wordt dan een die bij iedereen terechtkomt.
    """
    if soort not in SOORTEN:
        return []
    uit: list[str] = []
    for persoon in personen(settings):
        if (persoon.get("kinds") or {}).get(soort) and persoon["target"] not in uit:
            uit.append(persoon["target"])
    return uit


def eigen_persoon(settings: dict[str, Any], user_id: str) -> dict[str, Any] | None:
    """De persoon die aan deze gebruiker van Home Assistant hangt, als die er is."""
    if not user_id:
        return None
    for persoon in personen(settings):
        if persoon.get("user_id") == user_id:
            return persoon
    return None


def alleen_eigen(settings: dict[str, Any], user_id: str) -> dict[str, Any]:
    """De instellingen zoals een gewone bewoner ze te zien krijgt.

    Alleen de eigen persoon blijft over; de rest van de instellingen blijft
    zoals hij is, want het paneel heeft die nodig om te tekenen. Sven: "dat
    die persoon alleen zichzelf ziet."
    """
    uit = dict(settings)
    meldingen = dict(settings.get("notifications") or {})
    eigen = eigen_persoon(settings, user_id)
    meldingen["people"] = [copy.deepcopy(eigen)] if eigen else []
    uit["notifications"] = meldingen
    return uit


def zet_eigen_soorten(
    settings: dict[str, Any], user_id: str, kinds: dict[str, Any]
) -> list[dict[str, Any]] | None:
    """De schakelaars van de eigen persoon omzetten; de rest blijft staan.

    Geeft de nieuwe lijst personen terug, of None als deze gebruiker geen
    persoon heeft. Alleen de soorten worden overgenomen; naam, telefoon en
    koppeling zijn van de admin.
    """
    if eigen_persoon(settings, user_id) is None:
        return None
    uit = []
    for persoon in copy.deepcopy(personen(settings)):
        if persoon.get("user_id") == user_id:
            soorten = dict(STANDAARD_SOORTEN, **{k: bool(v) for k, v in (persoon.get("kinds") or {}).items() if k in SOORTEN})
            for soort, aan in kinds.items():
                if soort in SOORTEN:
                    soorten[soort] = bool(aan)
            persoon["kinds"] = soorten
        uit.append(persoon)
    return uit


def migreer_load_alert(stored: dict[str, Any]) -> dict[str, Any]:
    """v0.52.0: "Zware belasting" verhuist van Strategie naar Meldingen.

    De ontvangers van vroeger stonden in `strategy.load_alert.targets` en
    kregen álle meldingen. Ze worden personen, met alle soorten aan behalve
    besluiten, en de drempel, de wachttijd en de tussentijd gaan mee naar
    `notifications.load_alert`. Alleen als er nog geen `notifications` is,
    zodat dit één keer gebeurt en niet elke start opnieuw.
    """
    if "notifications" in stored:
        return stored
    strategy = stored.get("strategy")
    if not isinstance(strategy, dict) or not isinstance(strategy.get("load_alert"), dict):
        return stored
    oud = strategy["load_alert"]
    mensen = [
        nieuwe_persoon(naam_uit_doel(target), target)
        for target in oud.get("targets") or []
        if isinstance(target, str) and target
    ]
    stored["notifications"] = {
        "people": mensen,
        "load_alert": {
            sleutel: oud[sleutel]
            for sleutel in ("enabled", "threshold_percent", "min_interval_minutes", "min_duration_seconds")
            if sleutel in oud
        },
    }
    return stored
