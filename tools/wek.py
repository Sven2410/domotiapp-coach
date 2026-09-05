"""Wacht tot de coach iets anders doet, en stop dan. Leest alleen.

Bedoeld als achtergrondtaak in een sessie die gewekt wil worden: de taak
eindigt zodra er in besluiten.log een besluit staat met een andere stroom,
een andere regel of aan/uit, of zodra er in meldingen.log een MELDING-regel
bij komt. Wat er veranderde staat op stdout.

    python tools/wek.py besluiten.log meldingen.log

Sven op 05-09-2026, toen de paal om 09:42 begon en ik het pas om 10:07 zag:
"waarom meldde je niet om 10 uur dat hij aan het laden begon?"
"""
import re, sys, time

BESLUITEN = sys.argv[1] if len(sys.argv) > 1 else "besluiten.log"
MELDINGEN = sys.argv[2] if len(sys.argv) > 2 else "meldingen.log"
RIJ = re.compile(r"^(\d\d:\d\d:\d\d)\s+(laden|NIET laden)\s+(\S+) A\s+regel=(\S+)")


def kern(laden, amps, regel):
    """Waar je voor gewekt wilt worden: aan of uit, een andere stroom, een
    andere regel. Niet voor zon die even achter een wolk gaat: `surplus` en
    `wait-for-prices+hold` op dezelfde stroom zijn dezelfde laadbeurt, en bij
    wisselend weer wisselen die elke paar minuten."""
    basis = regel.split("+")[0]
    if laden == "laden" and basis in ("surplus", "wait-for-prices"):
        basis = "zon"
    return (laden, amps, basis)


def besluiten():
    uit = []
    try:
        for r in open(BESLUITEN, encoding="utf-8", errors="replace"):
            m = RIJ.match(r)
            if m:
                uit.append(kern(m.group(2), m.group(3), m.group(4)) + (r.rstrip(),))
    except FileNotFoundError:
        pass
    return uit


def meldingen():
    try:
        return [r.rstrip() for r in open(MELDINGEN, encoding="utf-8", errors="replace")
                if "  MELDING  " in r]
    except FileNotFoundError:
        return []


b0 = besluiten()
m0 = len(meldingen())
kern0 = b0[-1][:3] if b0 else None
print(f"[wacht op een ander besluit dan {kern0} of een nieuwe melding]", flush=True)
while True:
    time.sleep(15)
    b = besluiten()
    if b and b[-1][:3] != kern0:
        print("ANDER BESLUIT:")
        for rij in b[len(b0):] or b[-1:]:
            print("  " + rij[3][:220])
        break
    m = meldingen()
    if len(m) > m0:
        print("NIEUWE MELDING:")
        for rij in m[m0:]:
            print("  " + rij[:300])
        break
