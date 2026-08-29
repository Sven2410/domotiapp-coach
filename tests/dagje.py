"""Een bus die om 06:01 aan de lader gaat: wat doet de coach de hele dag?

Svens installatie, vast contract, klaar-tijd de volgende ochtend om 06:00.
Alleen rekenen, er gaat niets naar zijn paal.
"""
import importlib.util, sys
import datetime as dt

spec = importlib.util.spec_from_file_location(
    "planner",
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components" / "domotiapp_coach" / "planner.py",
)
P = importlib.util.module_from_spec(spec); sys.modules["planner"] = P
spec.loader.exec_module(P)

VAST = P.Tariff(buy=0.24171, feed_in=0.0721 - 0.052756)
KLAAR = dt.datetime(2026, 8, 27, 6, 0)          # de volgende ochtend
auto = P.Car(capacity_kwh=19.7, phases=3, soc_percent=30.0)

# tijd, overschot in W, zon nu in W, zon volgend uur in W, verwachting vandaag
dag = [
    ("06:01", 0, 0, 100, 22.0),
    ("07:30", 0, 400, 1200, 21.0),
    ("09:00", 900, 2200, 3500, 18.0),
    ("11:00", 3800, 5200, 6300, 13.0),
    ("13:00", 6000, 7000, 6800, 8.0),
    ("16:00", 2500, 3600, 2400, 3.0),
    ("18:30", 0, 700, 200, 0.4),
    ("20:00", 0, 0, 0, 0.0),
    ("23:00", 0, 0, 0, 0.0),
    ("03:00", 0, 0, 0, 0.0),
]

print(f"bus op {auto.soc_percent:.0f}%, klaar om {KLAAR:%d-%m %H:%M}, vast contract\n")
for klok, over, nu_w, straks_w, rest in dag:
    uur, minuut = (int(x) for x in klok.split(":"))
    dag_offset = 1 if uur < 5 else 0
    moment = dt.datetime(2026, 8, 26 + dag_offset, uur, minuut)
    paal = P.Charger(max_amps=16.0, connected=True, charging=False, actual_amps=0.0)
    net = P.Grid(surplus_w=float(over), phase_amps=[4.0, 3.0, 3.0], fuse_amps=25.0)
    zon = P.Sun(remaining_kwh=rest, now_w=float(nu_w), next_w=float(straks_w))
    d = P.decide(moment, [], net, auto, paal,
                 P.Window(enabled=True, opens=None, deadline=KLAAR),
                 tariff=VAST, sun=zon)
    doet = f"{d.amps:2d} A" if d.charge else "wacht"
    print(f"{klok}  overschot {over:5d} W  ->  {doet}  [{d.rule}]")
    print(f"          {d.reason}")
    if d.plan:
        print(f"          plan: {d.plan}")
