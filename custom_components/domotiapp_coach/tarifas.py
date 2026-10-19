"""De tijdvakken en de prijs van een Portugees stroomcontract (v0.137.0).

Kent Home Assistant niet, zoals planner.py: los te draaien en los te beproeven.

De eigenaar op 19-10-2026: "Hun wonen in portugal dus bij contract bovenaan wil ik
dat je een land kan kiezen dus Nederland en Portugal." Een Portugees contract
heeft geen salderen, een prijs zonder belastingen per tijdvak, en de tijdvakken
van de ERSE in de wettelijke tijd van het vasteland (Lissabon). Uitgezocht op
19-10-2026 uit de ERSE ("ERSExplica, períodos horários", 14-11-2025), Lei 38/2024
(IVA), de FAQ van EDP en DECO Proteste; zie docs/contract.md, Portugal.

- `simples`: één prijs.
- `bi` (bi-horário): `vazio` en `fora_vazio`.
- `tri` (tri-horário): `vazio`, `cheias` en `ponta`.

Ciclo diário is elke dag hetzelfde; ciclo semanal kent werkdagen, zaterdag en
zondag. Allebei met een winter- en zomertijd. De nieuwe tijden van de ERSE
(Diretiva 3/2026, per meter tussen 1-7 en 31-12-2027) staan hier nog niet.

De prijs per kWh: (energie + IEC) maal (1 + IVA). De IVA is die van de kWh die de
coach verschuift: 23%, want 6% geldt alleen voor de eerste 200 kWh per 30 dagen
bij hooguit 6,9 kVA, en een huis met een auto of een warmtepomp zit daar ruim
boven. Het veld staat open voor wie dat anders wil.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

TARIFAS = ("simples", "bi", "tri")
CICLOS = ("diario", "semanal")
PERIODOS = ("simples", "vazio", "fora_vazio", "cheias", "ponta")

# Wat een periode heet op het scherm, met de Portugese naam erbij.
NAMEN = {
    "simples": "Enkel (simples)",
    "vazio": "Daluren (vazio)",
    "fora_vazio": "Buiten de daluren (fora do vazio)",
    "cheias": "Normaal (cheias)",
    "ponta": "Piek (ponta)",
}
# De standaard van een Portugees contract staat in const.py (`contract.pt`).

# Minuten sinds middernacht, [van, tot), in de tijd van Lissabon. Uit de ERSE.
_DIARIO_VAZIO = ((0, 8 * 60), (22 * 60, 24 * 60))
_DIARIO_PONTA = {
    "inverno": ((9 * 60, 10 * 60 + 30), (18 * 60, 20 * 60 + 30)),
    "verao": ((10 * 60 + 30, 13 * 60), (19 * 60 + 30, 21 * 60)),
}
_SEMANAL_UTIL_VAZIO = ((0, 7 * 60),)
_SEMANAL_UTIL_PONTA = {
    "inverno": ((9 * 60 + 30, 12 * 60), (18 * 60 + 30, 21 * 60)),
    "verao": ((9 * 60 + 15, 12 * 60 + 15),),
}
# Zaterdag: geen ponta, cheias in deze vakken en de rest vazio.
_SEMANAL_SABADO_CHEIAS = {
    "inverno": ((9 * 60 + 30, 13 * 60), (18 * 60 + 30, 22 * 60)),
    "verao": ((9 * 60, 14 * 60), (20 * 60, 22 * 60)),
}


def _laatste_zondag(jaar: int, maand: int) -> date:
    dag = date(jaar, maand + 1, 1) - timedelta(days=1) if maand < 12 else date(jaar, 12, 31)
    return dag - timedelta(days=(dag.weekday() - 6) % 7)


def zomertijd(moment: datetime) -> bool:
    """Of het in Lissabon zomertijd is: de EU-regel, van de laatste zondag van maart
    01:00 UTC tot de laatste zondag van oktober 01:00 UTC. Een moment zonder tijdzone
    is UTC."""
    utc = moment.astimezone(timezone.utc) if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    begin = datetime.combine(_laatste_zondag(utc.year, 3), time(1), tzinfo=timezone.utc)
    eind = datetime.combine(_laatste_zondag(utc.year, 10), time(1), tzinfo=timezone.utc)
    return begin <= utc < eind


def lissabon(moment: datetime) -> tuple[datetime, bool]:
    """Het moment als lokale tijd in Lissabon (zonder tijdzone), en of het zomertijd is.

    Zelf uitgerekend en niet via een tijdzonedatabase: Lissabon is UTC, met een uur
    erbij in de zomer. Zo klopt het ook als Home Assistant zelf op een andere
    tijdzone staat, en op een machine zonder tzdata.
    """
    utc = moment.astimezone(timezone.utc) if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    zomer = zomertijd(utc)
    return (utc + timedelta(hours=1 if zomer else 0)).replace(tzinfo=None), zomer


def _in(minuut: int, vakken) -> bool:
    return any(van <= minuut < tot for van, tot in vakken)


def periodo(moment: datetime, tarifa: str, ciclo: str) -> str:
    """Het tijdvak van dit moment (met tijdzone), zoals de ERSE het indeelt."""
    if tarifa not in ("bi", "tri"):
        return "simples"
    lokaal, zomer = lissabon(moment)
    seizoen = "verao" if zomer else "inverno"
    minuut = lokaal.hour * 60 + lokaal.minute
    if ciclo == "semanal":
        dag = lokaal.weekday()
        if dag == 6:
            return "vazio"
        if dag == 5:
            if _in(minuut, _SEMANAL_SABADO_CHEIAS[seizoen]):
                return "cheias" if tarifa == "tri" else "fora_vazio"
            return "vazio"
        if _in(minuut, _SEMANAL_UTIL_VAZIO):
            return "vazio"
        if tarifa == "bi":
            return "fora_vazio"
        return "ponta" if _in(minuut, _SEMANAL_UTIL_PONTA[seizoen]) else "cheias"
    if _in(minuut, _DIARIO_VAZIO):
        return "vazio"
    if tarifa == "bi":
        return "fora_vazio"
    return "ponta" if _in(minuut, _DIARIO_PONTA[seizoen]) else "cheias"


def _getal(waarde) -> float | None:
    try:
        getal = float(waarde)
    except (TypeError, ValueError):
        return None
    return getal


def periodos(pt: dict) -> list[str]:
    """De tijdvakken van deze tarifa, in de volgorde van het scherm."""
    tarifa = (pt or {}).get("tarifa") or "bi"
    return {"simples": ["simples"], "bi": ["vazio", "fora_vazio"], "tri": ["vazio", "cheias", "ponta"]}.get(tarifa, ["vazio", "fora_vazio"])


def preco(pt: dict, periode: str) -> float | None:
    """Wat een kWh in dit tijdvak kost, met IEC en IVA. None zonder prijs."""
    energie = _getal(((pt or {}).get("energia") or {}).get(periode))
    if energie is None or energie <= 0:
        return None
    iec = _getal(pt.get("iec")) or 0.0
    iva = _getal(pt.get("iva"))
    iva = 23.0 if iva is None else iva
    return round((energie + iec) * (1 + iva / 100), 6)


def opbouw(pt: dict) -> list[dict]:
    """Per tijdvak de prijs zonder belastingen, de IEC, de IVA en het totaal, voor Contract."""
    uit = []
    iec = _getal((pt or {}).get("iec")) or 0.0
    iva = _getal((pt or {}).get("iva"))
    iva = 23.0 if iva is None else iva
    for periode in periodos(pt):
        energie = _getal(((pt or {}).get("energia") or {}).get(periode))
        uit.append({"periodo": periode, "energia": energie, "iec": iec, "iva": iva, "all_in": preco(pt, periode)})
    return uit


def terug(pt: dict, omie: float | None = None) -> float | None:
    """Wat een teruggeleverde kWh opbrengt, of None als dat niet bekend is.

    `nenhum`: niets verkocht, dus niets (geen salderen in Portugal). `fixo`: de prijs
    van het verkoopcontract. `omie`: de OMIE-prijs van dat moment maal de factor
    (EDP: 75%, "OMIE x (1 - 25%)"); zonder OMIE-prijs onbekend. Nog niet gekozen
    (`onbekend`, de standaard): onbekend, en niet nul. De sessie op een klant in
    Portugal op 19-10-2026: "Ik wil hier geen nenhum invullen omdat het ontbreekt."
    """
    e = (pt or {}).get("excedente") or {}
    modo = e.get("modo") or "onbekend"
    if modo == "nenhum":
        return 0.0
    if modo == "fixo":
        return _getal(e.get("preco")) or 0.0
    if modo == "omie":
        if omie is None:
            return None
        return round(omie * (_getal(e.get("fator")) or 0.0) / 100, 6)
    return None
