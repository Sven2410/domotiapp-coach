"""Proeven op de prijsopbouw: de opbouw, de controle tegen de all-in sensor, en overdag.

Alleen rekenwerk, zonder Home Assistant. De getallen van de controle zijn die van
een avond in de eerste woning, 18-10-2026: de all-in sensor van de leverancier
per uur, de kale prijs van Nord Pool per kwartier. Marktprijzen, niets van de
woning zelf.

    python tests/test_prijsopbouw.py
"""

import datetime as dt
import importlib.util
import pathlib
import sys

if sys.version_info < (3, 11):
    print("Deze proeven willen Python 3.11 of nieuwer; "
          f"dit is {sys.version_info.major}.{sys.version_info.minor}.")
    sys.exit(1)

BRON = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "domotiapp_coach"
spec = importlib.util.spec_from_file_location("prijsopbouw", BRON / "prijsopbouw.py")
po = importlib.util.module_from_spec(spec)
spec.loader.exec_module(po)

GOED = FOUT = 0


def controle(naam, gelukt, uitleg=""):
    global GOED, FOUT
    if gelukt:
        GOED += 1
        print(f"  goed  {naam}")
    else:
        FOUT += 1
        print(f"  FOUT  {naam}  {uitleg}")


def uur(h, m=0):
    return dt.datetime(2026, 10, 18, h, m)


# De leverancier per uur, Nord Pool per kwartier, lokale tijd.
ALL_IN = {uur(20): (uur(21), 0.4482672), uur(21): (uur(22), 0.4090149)}
KWARTIER = [0.28563, 0.25721, 0.25704, 0.24944, 0.24205, 0.23912, 0.22556, 0.21283]
MARKT = {uur(20) + dt.timedelta(minutes=15 * i): (uur(20) + dt.timedelta(minutes=15 * (i + 1)), p)
         for i, p in enumerate(KWARTIER)}
# Energiebelasting 2026 zoals de leverancier hem zelf doorgeeft (all-in min zijn
# prijs zonder belasting, gedeeld door 1,21), en wat er van het gemeten verschil
# overblijft als opslag.
GOED_CONTRACT = {"energy_tax": 0.09161, "supplier_markup": 0.01653, "vat_percent": 21}
OUD_CONTRACT = {"energy_tax": 0.1088, "supplier_markup": 0.02, "vat_percent": 21}

print("1. de opbouw van de inkoopprijs")
o = po.inkoop(0.22989, GOED_CONTRACT)
print(f"  {o['markt']:.4f} + {o['belasting']:.4f} + {o['opslag']:.4f} = {o['subtotaal']:.4f}, "
      f"+ {o['btw']:.4f} btw = {o['totaal']:.4f}")
controle("kaal + belasting + opslag, maal de btw", abs(o["totaal"] - 0.40897) < 0.00005, f"{o['totaal']}")
controle("de btw is het verschil tussen het totaal en het subtotaal",
         abs(o["subtotaal"] + o["btw"] - o["totaal"]) < 1e-12)

print("2. de controle: uur tegenover kwartier")
c = po.controleer(ALL_IN, MARKT, GOED_CONTRACT, uur(21, 30))
print(f"  {c['status']}, {c['blokken']} blokken van {c.get('stap_minuten')} min, grootste {c['grootste']:+.5f}")
controle("met de belasting en opslag van de leverancier klopt het", c["status"] == "correct", f"{c}")
controle("vergeleken per uur, want de leverancier rekent per uur", c["blokken"] == 2 and c["stap_minuten"] == 60)
controle("het blok van nu is 21:00", c["blok"]["start"] == uur(21) and abs(c["blok"]["markt"] - 0.22989) < 1e-5,
         f"{c['blok']}")
c = po.controleer(ALL_IN, MARKT, OUD_CONTRACT, uur(21, 30))
print(f"  oude velden: {c['status']}, grootste {c['grootste']:+.5f}, vast {c['vast']}")
controle("met de energiebelasting van een ander jaar klopt het niet", c["status"] == "afwijking")
controle("het verschil is in elk uur even groot: een bedrag per kWh", c["vast"])
controle("en dat is 2,5 cent te veel", abs(c["grootste"] + 0.02505) < 0.0002, f"{c['grootste']}")
controle("zonder all-in sensor valt er niets te controleren",
         po.controleer({}, MARKT, GOED_CONTRACT, uur(21))["status"] == "onbekend")
controle("zonder marktprijs ook niet", po.controleer(ALL_IN, {}, GOED_CONTRACT, uur(21))["status"] == "onbekend")
# Een uur waarvan de marktprijs maar half bekend is telt niet mee.
half = {k: v for k, v in MARKT.items() if k < uur(21, 30)}
c = po.controleer(ALL_IN, half, GOED_CONTRACT, uur(21))
controle("een uur dat niet helemaal bekend is telt niet", c["blokken"] == 1, f"{c}")
# Allebei per kwartier: dan per kwartier.
kw_all_in = {k: (e, po.inkoop(p, GOED_CONTRACT)["totaal"]) for k, (e, p) in MARKT.items()}
c = po.controleer(kw_all_in, MARKT, GOED_CONTRACT, uur(21))
controle("allebei per kwartier: per kwartier vergeleken", c["status"] == "correct" and c["stap_minuten"] == 15
         and c["blokken"] == 8, f"{c}")

print("3. teruglevering")
d = {**GOED_CONTRACT, "feed_in_bonus": 0.02, "feed_in_costs": 0.0}
t = po.terug(0.22989, 0.4090149, d, salderen=True, overdag=False)
print(f"  salderen: {t['basis']:.4f} - {t['opslag']:.4f} + {t['vergoeding']:.4f} = {t['bedrag']:.4f}")
controle("met salderen en een vergoeding gelijk aan de opslag: de all-in prijs",
         abs(t["bedrag"] - 0.4090149) < 0.0001, f"{t}")
t = po.terug(0.22989, 0.4090149, d, salderen=False, overdag=False)
controle("zonder salderen: de kale prijs plus de vergoeding", abs(t["bedrag"] - 0.24989) < 1e-9, f"{t}")
controle("zonder all-in prijs is het met salderen onbekend",
         po.terug(0.22989, None, d, salderen=True, overdag=False)["bedrag"] is None)
controle("zonder marktprijs is het zonder salderen onbekend",
         po.terug(None, 0.40, d, salderen=False, overdag=False)["bedrag"] is None)
zb = {**d, "feed_in_bonus_percent": 10, "bonus_daytime": True, "bonus_base": "market_plus_fee"}
controle("een bonus van 10% over markt plus vergoeding, overdag",
         abs(po.bonus(0.08, zb, overdag=True) - 0.01) < 1e-12, f"{po.bonus(0.08, zb, True)}")
controle("en 's avonds niet", po.bonus(0.08, zb, overdag=False) == 0.0)
controle("en niet als markt plus vergoeding niet positief is", po.bonus(-0.03, zb, overdag=True) == 0.0)
controle("over alleen de markt als het contract dat zegt",
         abs(po.bonus(0.08, {**zb, "bonus_base": "market"}, True) - 0.008) < 1e-12)
t = po.terug(0.08, 0.30, zb, salderen=False, overdag=True)
controle("de bonus telt mee in de terugleverprijs", abs(t["bedrag"] - 0.11) < 1e-12 and abs(t["bonus"] - 0.01) < 1e-12,
         f"{t}")

# Het rekenvoorbeeld van Zonneplan zelf, met prijzen inclusief btw: "is de
# marktprijs € 0,08 per kWh? Dan krijg je € 0,11 per kWh (€ 0,08 + € 0,02
# inkoopvergoeding + 10% extra)". Zonneplan betaalt de marktprijs met btw.
zp = {"vat_percent": 21, "feed_in_bonus": 0.02, "feed_in_bonus_percent": 10, "bonus_daytime": True,
      "bonus_base": "market_plus_fee", "feed_in_vat": True}
t = po.terug(0.08 / 1.21, None, zp, salderen=False, overdag=True)
print(f"  het voorbeeld van Zonneplan: {t['basis']:.4f} + {t['vergoeding']:.4f} + {t['bonus']:.4f} = {t['bedrag']:.4f}")
controle("Zonneplan: € 0,08 + € 0,02 + 10% is € 0,11", abs(t["bedrag"] - 0.11) < 1e-9, f"{t}")
controle("en 's avonds zonder bonus € 0,10", abs(po.terug(0.08 / 1.21, None, zp, False, False)["bedrag"] - 0.10) < 1e-9)
o = po.inkoop(0.2, {"energy_tax": 0.09161, "supplier_markup": 0.02 / 1.21, "vat_percent": 21})
controle("de opslag na de btw is dezelfde som: (markt + belasting) x 1,21 + 0,02",
         abs((o["zonder_opslag"] + o["btw_zonder_opslag"] + o["opslag_met_btw"]) - o["totaal"]) < 1e-12
         and abs(o["opslag_met_btw"] - 0.02) < 1e-12)

# Essent: binnen salderen "per uur hetzelfde tarief terug als je betaalt, inclusief
# btw, energiebelasting en inkoopvergoeding"; buiten salderen de beursprijs min
# 0,02089 (v0.129.1).
es = {"vat_percent": 21, "supplier_markup": 0.02089, "feed_in_bonus": -0.02089, "netting_full": True}
controle("binnen salderen de hele all-in prijs terug", po.terug(0.15, 0.40, es, salderen=True, overdag=False)["bedrag"] == 0.40)
controle("en buiten salderen de beursprijs min de aftrek",
         abs(po.terug(0.15, 0.40, es, salderen=False, overdag=False)["bedrag"] - (0.15 - 0.02089)) < 1e-12)
controle("zonder het vinkje binnen salderen de all-in prijs min de opslag",
         abs(po.terug(0.15, 0.40, {**es, "netting_full": False, "feed_in_bonus": 0}, True, False)["bedrag"]
             - (0.40 - 0.02089 * 1.21)) < 1e-12)

# Een vaste terugleververgoeding naast een dynamische inkoop (v0.132.0): buiten
# salderen het vaste bedrag min de kosten, wat de markt ook doet; binnen salderen
# blijft het de inkoopprijs.
vt = {"vat_percent": 21, "supplier_markup": 0.02, "feed_in_costs": 0.01, "feed_in_mode": "fixed", "feed_in_fixed": 0.07,
      "feed_in_bonus": 0.02, "feed_in_bonus_percent": 10}
t = po.terug(0.15, 0.40, vt, salderen=False, overdag=True)
print(f"  vast: {t['basis']:.4f} - {t['kosten']:.4f} = {t['bedrag']:.4f}")
controle("vast bedrag: 0,07 min 0,01 kosten, zonder vergoeding of bonus over de markt",
         abs(t["bedrag"] - 0.06) < 1e-12 and t.get("vast") is True and t["bonus"] == 0.0, f"{t}")
controle("ook zonder marktprijs bekend", abs(po.terug(None, 0.40, vt, False, True)["bedrag"] - 0.06) < 1e-12)
controle("binnen salderen nog steeds de inkoopprijs", po.terug(0.15, 0.40, vt, salderen=True, overdag=False).get("vast") is None)
basis = {"type": "dynamic", "netting": True, "supplier": "", "fixed": {}, "dynamic": {"energy_tax": 0.09161, "vat_percent": 21}}
met_standaard = {**basis, "dynamic": {**basis["dynamic"], "feed_in_mode": "market", "feed_in_fixed": 0.0}}
controle("de nieuwe velden op hun standaard laten een bevestiging staan",
         po.vingerafdruk(basis) == po.vingerafdruk(met_standaard))
controle("maar een vast bedrag kiezen vraagt opnieuw om Ja, dit klopt",
         po.vingerafdruk(basis) != po.vingerafdruk({**basis, "dynamic": {**met_standaard["dynamic"], "feed_in_mode": "fixed"}}))

# De vier vormen van terugleverkosten (v0.135.0).
v = {"feed_in_costs": 0.05}
controle("per kWh over alles", po.kosten_per_kwh(v, True) == 0.05 and po.kosten_per_kwh(v, False) == 0.05)
controle("alleen over het overschot: gesaldeerd niets",
         po.kosten_per_kwh({**v, "feed_in_costs_mode": "overschot"}, True) == 0.0
         and po.kosten_per_kwh({**v, "feed_in_costs_mode": "overschot"}, False) == 0.05)
controle("schalen en geen: niets per kWh", po.kosten_per_kwh({**v, "feed_in_costs_mode": "schalen"}, False) == 0.0
         and po.kosten_per_kwh({**v, "feed_in_costs_mode": "geen"}, False) == 0.0)
t = po.terug(0.15, 0.40, {"supplier_markup": 0.0, "vat_percent": 21, **v, "feed_in_costs_mode": "overschot"}, salderen=True, overdag=False)
controle("de terugleverprijs volgt de vorm", abs(t["bedrag"] - 0.40) < 1e-12, f"{t}")
schalen = [{"vanaf": 500, "per_jaar": 70}, {"vanaf": 0, "per_jaar": 0}, {"vanaf": 750, "per_jaar": 140}]
controle("de schaal: onder 500 niets, 500 tot 750 het tweede bedrag, daarboven het derde",
         po.schaal_per_jaar(schalen, 499.9) == 0 and po.schaal_per_jaar(schalen, 500) == 70
         and po.schaal_per_jaar(schalen, 6800) == 140 and po.schaal_per_jaar([], 100) is None)
basis_v = {"type": "fixed", "netting": True, "supplier": "", "fixed": {"all_in_price": 0.25}, "dynamic": {}}
controle("de nieuwe velden op hun standaard laten een bevestiging staan",
         po.vingerafdruk(basis_v) == po.vingerafdruk({**basis_v, "fixed": {**basis_v["fixed"], "feed_in_costs_mode": "kwh",
                                                                          "feed_in_scales": [], "feed_in_scales_until": ""}}))

print("4. zonsopkomst en zonsondergang")
def lokaal(d, lat=52.09, lon=5.12, uren=2):
    op, onder = po.zon_op_onder(d, lat, lon)
    return op + dt.timedelta(hours=uren), onder + dt.timedelta(hours=uren)
op, onder = lokaal(dt.date(2026, 10, 18))
print(f"  Utrecht 18-10-2026: op {op:%H:%M}, onder {onder:%H:%M}")
def bij(t, h, m, minuten=3):
    return abs((t.hour * 60 + t.minute) - (h * 60 + m)) <= minuten
controle("18 oktober: op 08:08 en onder 18:40, op een paar minuten", bij(op, 8, 8) and bij(onder, 18, 40), f"{op} {onder}")
op, onder = lokaal(dt.date(2026, 6, 21))
controle("21 juni: op 05:20 en onder 22:04", bij(op, 5, 20) and bij(onder, 22, 4), f"{op} {onder}")
op, onder = lokaal(dt.date(2026, 12, 21), uren=1)
controle("21 december: op 08:45 en onder 16:29", bij(op, 8, 45) and bij(onder, 16, 29), f"{op} {onder}")
cest = dt.timezone(dt.timedelta(hours=2))
middag = dt.datetime(2026, 10, 18, 12, 0, tzinfo=cest)
avond = dt.datetime(2026, 10, 18, 21, 0, tzinfo=cest)
controle("een blok rond de middag is overdag", po.overdag(middag, middag + dt.timedelta(hours=1), 52.09, 5.12))
controle("een blok om 21:00 niet", not po.overdag(avond, avond + dt.timedelta(hours=1), 52.09, 5.12))
grens = dt.datetime(2026, 10, 18, 18, 30, tzinfo=cest)
controle("18:30 tot 18:45 nog wel, 18:45 tot 19:00 niet meer",
         po.overdag(grens, grens + dt.timedelta(minutes=15), 52.09, 5.12)
         and not po.overdag(grens + dt.timedelta(minutes=15), grens + dt.timedelta(minutes=30), 52.09, 5.12))
controle("zonder ligging van de woning telt het niet", not po.overdag(middag, middag + dt.timedelta(hours=1), None, None))

print()
print(f"{GOED} goed, {FOUT} fout")
sys.exit(1 if FOUT else 0)
