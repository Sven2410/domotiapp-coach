"""Wat een sensor zichzelf noemt is ons probleem niet.

De ene klant zijn meter rapporteert watt, de volgende kilowatt, en dezelfde
installatie mengt de twee vrolijk door elkaar. Daarom wordt elke meting bij
binnenkomst omgerekend naar watt of naar kilowattuur, met de eenheid die de
entiteit zelf opgeeft. Verderop in de coach bestaat kW niet meer.

Dat het paneel dit al deed (`frontend/src/format.js`) en de zekeringbewaking
ook (`monitor.py`), en `coach.py` als enige niet, is precies waarom het hier nu
op één plek staat. Een klant met een netmeter in kW kreeg een coach die met een
duizend keer te klein getal rekende: het overschot kwam nooit boven nul, dus
laden op eigen zon gebeurde nooit, en het laadverslag klopte niet. Er kwam geen
foutmelding bij, want een getal is een getal. Het paneel liet ondertussen de
goede waarde zien, want dat rekende wél om. Gevonden op 28-08-2026.

Deze module kent Home Assistant niet en is dus los te draaien, net als
`planner.py`.

**Een onbekende of ontbrekende eenheid wordt als watt of kilowattuur gelezen.**
Dat is wat de grote meerderheid van de sensoren rapporteert. Gokken op kilo zou
een meting een factor duizend opblazen, en dat is een fout die niemand als een
eenheidsprobleem herkent.
"""

from __future__ import annotations

from typing import Final

# Van wat een sensor als eenheid opgeeft naar watt.
POWER_TO_WATT: Final[dict[str, float]] = {
    "w": 1.0,
    "watt": 1.0,
    "watts": 1.0,
    "kw": 1_000.0,
    "kilowatt": 1_000.0,
    "mw": 1_000_000.0,
    "megawatt": 1_000_000.0,
}

# Van wat een sensor als eenheid opgeeft naar kilowattuur.
ENERGY_TO_KWH: Final[dict[str, float]] = {
    "wh": 0.001,
    "watt-hour": 0.001,
    "kwh": 1.0,
    "mwh": 1_000.0,
}


def _factor(table: dict[str, float], unit: str | None) -> float:
    """De vermenigvuldiger voor deze eenheid, en 1 als we hem niet kennen."""
    return table.get(str(unit or "").strip().lower(), 1.0)


def to_watts(value: float | None, unit: str | None) -> float | None:
    """Een meting in watt, wat de sensor zelf ook zegt te rapporteren."""
    return None if value is None else value * _factor(POWER_TO_WATT, unit)


def to_kwh(value: float | None, unit: str | None) -> float | None:
    """Een meting in kilowattuur, wat de sensor zelf ook zegt te rapporteren."""
    return None if value is None else value * _factor(ENERGY_TO_KWH, unit)
