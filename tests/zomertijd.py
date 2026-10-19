"""Een tijdzone met de Europese zomertijd, voor de proeven (v0.139.1).

De eigenaar op 19-10-2026: "ik wil dat je sowieso rekening houd met de zomer en
wintertijd. Dat moet allemaal vanzelf gaan." Zondag 25-10-2026 is de eerste wintertijd
die de coach meemaakt: om 01:00 UTC gaat de klok in Nederland van 03:00 terug naar
02:00, en in Portugal van 02:00 naar 01:00. Die dag heeft 25 uur en 100 kwartierprijzen;
op 28-03-2027 mist er een uur.

De proeven draaien ook op machines zonder `tzdata`, en dan bestaat `ZoneInfo` niet.
Daarom hier zelf de regel van de EU: zomertijd van de laatste zondag van maart tot de
laatste zondag van oktober, steeds om 01:00 UTC. Met `fold` zoals PEP 495 het wil: in het
uur dat twee keer komt is `fold=0` de eerste keer (zomertijd) en `fold=1` de tweede; in
het uur dat niet bestaat rekent `fold=0` met de tijd van ervoor.
"""

from __future__ import annotations

import datetime as dt

UTC = dt.timezone.utc


def _laatste_zondag(jaar: int, maand: int) -> dt.date:
    dag = dt.date(jaar, maand + 1, 1) - dt.timedelta(days=1) if maand < 12 else dt.date(jaar, 12, 31)
    return dag - dt.timedelta(days=(dag.weekday() - 6) % 7)


def zomer_van_tot(jaar: int) -> tuple[dt.datetime, dt.datetime]:
    """Begin en einde van de zomertijd in dat jaar, in UTC."""
    van = dt.datetime.combine(_laatste_zondag(jaar, 3), dt.time(1), UTC)
    tot = dt.datetime.combine(_laatste_zondag(jaar, 10), dt.time(1), UTC)
    return van, tot


class EuropaTijd(dt.tzinfo):
    """Een Europese tijdzone: `EuropaTijd(1)` is Amsterdam, `EuropaTijd(0)` Lissabon."""

    def __init__(self, standaard_uren: int, naam: str = "") -> None:
        self._std = dt.timedelta(hours=standaard_uren)
        self._naam = naam or f"UTC{standaard_uren:+d}"

    def __repr__(self) -> str:
        return f"EuropaTijd({self._naam})"

    def _zomer_utc(self, moment_utc: dt.datetime) -> bool:
        van, tot = zomer_van_tot(moment_utc.year)
        return van <= moment_utc.replace(tzinfo=UTC) < tot

    def utcoffset(self, moment: dt.datetime | None) -> dt.timedelta:
        if moment is None:
            return self._std
        return self._std + self.dst(moment)

    def dst(self, moment: dt.datetime | None) -> dt.timedelta:
        if moment is None:
            return dt.timedelta(0)
        lokaal = moment.replace(tzinfo=None)
        van, tot = zomer_van_tot(lokaal.year)
        # De wisselmomenten op de klok van hier.
        voorjaar = (van + self._std).replace(tzinfo=None)          # bv. 02:00 -> 03:00
        najaar = (tot + self._std + dt.timedelta(hours=1)).replace(tzinfo=None)  # bv. 03:00 -> 02:00
        uur = dt.timedelta(hours=1)
        if voorjaar <= lokaal < voorjaar + uur:
            # Het uur dat niet bestaat: fold 0 rekent met de tijd van ervoor (winter).
            return uur if moment.fold else dt.timedelta(0)
        if najaar - uur <= lokaal < najaar:
            # Het uur dat twee keer komt: fold 0 is de eerste keer (zomer).
            return dt.timedelta(0) if moment.fold else uur
        return uur if voorjaar + uur <= lokaal < najaar - uur else dt.timedelta(0)

    def tzname(self, moment: dt.datetime | None) -> str:
        return self._naam

    def fromutc(self, moment: dt.datetime) -> dt.datetime:
        utc = moment.replace(tzinfo=None)
        zomer = self._zomer_utc(utc)
        lokaal = utc + self._std + (dt.timedelta(hours=1) if zomer else dt.timedelta(0))
        uit = lokaal.replace(tzinfo=self)
        # De tweede keer van het herhaalde uur: fold 1.
        _, tot = zomer_van_tot(utc.year)
        if not zomer and tot.replace(tzinfo=None) <= utc < tot.replace(tzinfo=None) + dt.timedelta(hours=1):
            uit = uit.replace(fold=1)
        return uit


AMSTERDAM = EuropaTijd(1, "Europe/Amsterdam")
LISSABON = EuropaTijd(0, "Europe/Lisbon")


if __name__ == "__main__":
    # Een snelle blik: de nacht van 25-10-2026 in Amsterdam, per kwartier.
    t = dt.datetime(2026, 10, 24, 23, 30, tzinfo=UTC)
    for _ in range(12):
        lokaal = t.astimezone(AMSTERDAM)
        print(t.strftime("%H:%MZ"), lokaal.strftime("%H:%M"), lokaal.fold, lokaal.utcoffset())
        t += dt.timedelta(minutes=15)
