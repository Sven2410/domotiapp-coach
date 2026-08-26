"""Vat live.log samen: per gevraagde laadgrens wat de paal er werkelijk van maakte."""
import re, sys

pad = sys.argv[1] if len(sys.argv) > 1 else "live.log"
rijen = []
for r in open(pad, encoding="utf-8"):
    m = re.match(
        r"(\d\d:\d\d:\d\d) (\S+)\s+limiet=\s*(\S+) A=\s*([\d.]+) W=\s*(\d+)\s+(\S+)"
        r".*uitgang=(\S+)", r)
    if not m:
        continue
    tijd, status, limiet, amp, watt, fasen, uitgang = m.groups()
    rijen.append((tijd, status, limiet, float(amp), int(watt), fasen, uitgang))

vorig = None
for i, rij in enumerate(rijen):
    sleutel = (rij[2], rij[6], rij[1])
    laatste = i == len(rijen) - 1 or (rijen[i + 1][2], rijen[i + 1][6], rijen[i + 1][1]) != sleutel
    if sleutel != vorig:
        eerste = rij
    if laatste and rij[1] == "charging":
        f = "3 fasen" if rij[5].endswith("3F") else ("1 fase" if rij[5].endswith("1F") else "?")
        print(f"{eerste[0]}-{rij[0]}  gevraagd {rij[2]:>3} A -> {rij[3]:5.2f} A  "
              f"{rij[4]:6d} W  {f:<8} uitgang={rij[6]}")
    vorig = sleutel
