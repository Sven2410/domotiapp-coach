"""Proeven op de eigen geschiedenis: het kwartier, de piek en het gemiddelde.

Alleen het denkwerk, dus zonder Home Assistant en zonder schijf. Wat hier
getoetst wordt is de rekenkant van `archive.py`: hoe een reeks metingen in
kwartierregels valt, en of het gemiddelde naar tijd weegt en niet naar aantal.

Dat laatste is de kern. Hoe vaak een sensor zich meldt verschilt per klant: de
ene slimme meter elke seconde, de volgende elke dertig seconden. Zou het
gemiddelde per meting tellen, dan zou hetzelfde huis bij twee klanten een ander
getal opleveren, en dat is precies het soort verzonnen getal dat hier niet in
hoort.

    python tests/test_archive.py
"""

import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

if sys.version_info < (3, 11):
    print("Deze proeven willen Python 3.11 of nieuwer; "
          f"dit is {sys.version_info.major}.{sys.version_info.minor}.")
    sys.exit(1)

# archive.py importeert Home Assistant. Voor het rekenwerk is dat niet nodig, dus
# de module wordt hier los geladen met de handvol namen die hij eruit gebruikt
# nagemaakt, en zonder `__init__.py` te draaien. Dezelfde aanpak als in
# test_coach.py.
import importlib.util
import types

BRON = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "domotiapp_coach"

ha = types.ModuleType("homeassistant")
core = types.ModuleType("homeassistant.core")
core.HomeAssistant = type("HomeAssistant", (), {})
core.Event = type("Event", (), {})
core.State = type("State", (), {})
core.callback = lambda func: func

helpers = types.ModuleType("homeassistant.helpers")
gebeurtenis = types.ModuleType("homeassistant.helpers.event")
gebeurtenis.async_track_state_change_event = lambda *a, **k: (lambda: None)
gebeurtenis.async_track_time_interval = lambda *a, **k: (lambda: None)
starthulp = types.ModuleType("homeassistant.helpers.start")
starthulp.async_at_started = lambda *a, **k: (lambda: None)
opslag = types.ModuleType("homeassistant.helpers.storage")
opslag.Store = type("Store", (), {"__init__": lambda self, *a, **k: None})

util = types.ModuleType("homeassistant.util")
dtutil = types.ModuleType("homeassistant.util.dt")
dtutil.now = lambda: dt.datetime.now()
dtutil.utcnow = lambda: dt.datetime.now(dt.timezone.utc)
dtutil.parse_datetime = lambda w: dt.datetime.fromisoformat(w)
dtutil.utc_from_timestamp = lambda ts: dt.datetime.fromtimestamp(ts, dt.timezone.utc)
dtutil.as_utc = lambda m: m.astimezone(dt.timezone.utc)
dtutil.DEFAULT_TIME_ZONE = dt.datetime.now().astimezone().tzinfo
# Zoals Home Assistant het doet: een tijd met zone naar lokale tijd, en een
# naieve tijd als UTC lezen.
dtutil.as_local = lambda m: m.astimezone() if m.tzinfo else m
util.dt = dtutil

sys.modules.update({
    "homeassistant": ha,
    "homeassistant.core": core,
    "homeassistant.helpers": helpers,
    "homeassistant.helpers.event": gebeurtenis,
    "homeassistant.helpers.start": starthulp,
    "homeassistant.helpers.storage": opslag,
    "homeassistant.util": util,
    "homeassistant.util.dt": dtutil,
})

pakket = types.ModuleType("domotiapp_coach")
pakket.__path__ = [str(BRON)]
sys.modules["domotiapp_coach"] = pakket


def laad(naam):
    spec = importlib.util.spec_from_file_location(
        f"domotiapp_coach.{naam}", BRON / f"{naam}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"domotiapp_coach.{naam}"] = module
    spec.loader.exec_module(module)
    return module


laad("const")
laad("units")
laad("storage")
archive = laad("archive")

GOED = 0
FOUT = 0


def controle(naam, gelukt, uitleg=""):
    global GOED, FOUT
    if gelukt:
        GOED += 1
    else:
        FOUT += 1
        print(f"  FOUT  {naam}: {uitleg}")


def t(uur, minuut, seconde=0):
    return dt.datetime(2026, 8, 28, uur, minuut, seconde)


print("=== 1. het kwartier waar een moment in valt ===")
controle("14:07 hoort bij 14:00", archive.bucket_start(t(14, 7)) == t(14, 0))
controle("14:15 begint zelf een kwartier", archive.bucket_start(t(14, 15)) == t(14, 15))
controle("14:59 hoort bij 14:45", archive.bucket_start(t(14, 59)) == t(14, 45))


print("=== 2. het gemiddelde weegt naar tijd, niet naar aantal metingen ===")
# Dezelfde werkelijkheid, twee meters. De ene meldt elke minuut, de andere elke
# vijf. Vijf minuten 1000 W en tien minuten 100 W: het gewogen gemiddelde is
# (5*1000 + 10*100) / 15 = 400 W. Bij tellen per meting zou de snelle meter iets
# heel anders geven dan de trage, en dat is precies wat er niet mag gebeuren.
def loop(stap_minuten):
    meter = archive._Meter("sensor.proef")
    minuut = 0
    while minuut < 15:
        meter.meet(t(14, 0) + dt.timedelta(minutes=minuut),
                   1000.0 if minuut < 5 else 100.0)
        minuut += stap_minuten
    meter.tot(t(14, 15))
    return meter.oogst()


for stap in (1, 5):
    rijen = loop(stap)
    controle(f"om de {stap} min: precies een kwartier", len(rijen) == 1, f"{rijen}")
    start, laagste, piek, gemiddeld, seconden = rijen[0]
    controle(f"om de {stap} min: het gemiddelde is 400 W",
             abs(gemiddeld - 400.0) < 1e-6, f"{gemiddeld}")
    controle(f"om de {stap} min: de piek is 1000 W", piek == 1000.0, f"{piek}")
    controle(f"om de {stap} min: het laagste is 100 W", laagste == 100.0, f"{laagste}")
    controle(f"om de {stap} min: het hele kwartier is gedekt",
             abs(seconden - 900.0) < 1e-6, f"{seconden}")

print(f"  meldsnelheid maakt niet uit: {loop(1)[0][3]:.0f} W tegen {loop(5)[0][3]:.0f} W")


print("=== 3. een piek van een seconde overleeft het kwartier ===")
# Waar het hele ding om begonnen is. Een kwartier rustig op 200 W met één
# seconde 9000 W erin: het gemiddelde merkt daar bijna niets van, de piek staat
# er onverkort in.
meter = archive._Meter("sensor.proef")
meter.meet(t(14, 0), 200.0)
meter.meet(t(14, 7, 30), 9000.0)
meter.meet(t(14, 7, 31), 200.0)
meter.tot(t(14, 15))
rijen = meter.oogst()
_, laagste, piek, gemiddeld, _ = rijen[0]
print(f"  een seconde 9000 W: piek {piek:.0f} W, gemiddeld {gemiddeld:.1f} W")
controle("de piek van een seconde staat er", piek == 9000.0, f"{piek}")
controle("het gemiddelde blijft er bijna gelijk van",
         abs(gemiddeld - (200.0 + 8800.0 / 900.0)) < 1e-6, f"{gemiddeld}")
controle("en het laagste ook", laagste == 200.0, f"{laagste}")


print("=== 4. een meting die blijft staan vult meerdere kwartieren ===")
# Een sensor die een uur lang hetzelfde meldt hoort in vier regels te staan.
# Zonder dit zou een rustige nacht één regel opleveren en zou het rapport over
# die nacht niets te tekenen hebben.
meter = archive._Meter("sensor.proef")
meter.meet(t(14, 0), 500.0)
meter.tot(t(15, 0))
rijen = meter.oogst()
controle("een uur stilte geeft vier kwartieren", len(rijen) == 4, f"{len(rijen)}")
controle("die allemaal 500 W zeggen",
         all(abs(r[3] - 500.0) < 1e-6 for r in rijen), f"{rijen}")
controle("en die op de kwartieren beginnen",
         [r[0] for r in rijen] == [t(14, 0), t(14, 15), t(14, 30), t(14, 45)],
         f"{[r[0] for r in rijen]}")

print("=== 5. stilte is geen gat, maar wegvallen wel ===")
# Veel sensoren melden alleen bij verandering: een laadpaal die niet laadt meldt
# uren niets. Zou stilte als een gat gelden, dan kwam een rustige nacht half leeg
# in de opslag. Een sensor die werkelijk wegvalt zegt dat zelf.
meter = archive._Meter("sensor.proef")
meter.meet(t(14, 0), 800.0)
meter.tot(t(18, 0))
rijen = meter.oogst()
gedekt = sum(r[4] for r in rijen)
print(f"  vier uur zwijgen op 800 W: {len(rijen)} kwartieren, {gedekt:.0f} seconden")
controle("vier uur stilte geeft zestien volle kwartieren", len(rijen) == 16,
         f"{len(rijen)}")
controle("en die zijn helemaal gedekt", abs(gedekt - 4 * 3600) < 1e-6, f"{gedekt}")
controle("allemaal op 800 W", all(abs(r[3] - 800.0) < 1e-6 for r in rijen))

# Een minuut gemeten, tien minuten weg, vier minuten weer terug: van het
# kwartier is dan vijf minuten gedekt en niet vijftien.
meter = archive._Meter("sensor.proef")
meter.meet(t(14, 0), 800.0)
meter.verloren(t(14, 1))
meter.meet(t(14, 11), 800.0)
meter.tot(t(14, 15))
rijen = meter.oogst()
gedekt = rijen[0][4] if rijen else 0
print(f"  een gat van tien minuten: {gedekt:.0f} van de 900 seconden gedekt")
controle("na 'onbeschikbaar' telt de tijd niet meer mee",
         bool(rijen) and abs(gedekt - 300.0) < 1e-6, f"{rijen}")
controle("dus het gat is te zien in plaats van weggerekend", gedekt < 900.0,
         f"{gedekt}")


print("=== 6. wat er gevolgd wordt komt uit de instellingen ===")
# Geen lijst in de code, want dan zou een apparaat dat de klant koppelt er niet
# in komen. Precies wat hij zelf heeft ingevuld, en niets erbuiten.
instellingen = {
    "sources": {
        "grid_import": "sensor.afname",
        "grid_export": "sensor.teruglevering",
        "grid_signed": "",
        "solar": "sensor.zon",
    },
    "devices": [
        {"id": "d1", "entity": "sensor.laadpaal"},
        {"id": "d2", "entity": "sensor.warmtepomp"},
        {"id": "d3", "entity": ""},
    ],
}
volgt = archive.Archive._wat_volgen(instellingen)
controle("het net, de zon en elk gekoppeld apparaat",
         volgt == {"sensor.afname", "sensor.teruglevering", "sensor.zon",
                   "sensor.laadpaal", "sensor.warmtepomp"}, f"{sorted(volgt)}")
controle("en een leeg veld levert geen sensor op", "" not in volgt, f"{sorted(volgt)}")


print("=== 7. wat twee jaar aan regels kost ===")
# Geen proef op de code maar op de belofte: 96 regels per dag per sensor.
per_dag = int(dt.timedelta(days=1) / archive.BUCKET)
totaal = per_dag * archive.KEEP.days
print(f"  {per_dag} regels per dag, {totaal:,} voor de hele bewaartermijn"
      .replace(",", "."))
controle("een kwartier geeft 96 regels per dag", per_dag == 96, f"{per_dag}")
controle("en de bewaartermijn is twee jaar", archive.KEEP.days == 730,
         f"{archive.KEEP.days}")

print("=== 8. de inhaalslag: vijfminutenblokjes worden kwartieren ===")
# Bij de eerste keer wordt overgenomen wat Home Assistant zelf nog heeft, zodat
# de geschiedenis niet pas begint op de dag dat de klant bijwerkt. Drie blokjes
# van vijf minuten zijn samen een kwartier.
#
# Deze samenvatting is op 28-08-2026 naast de uurstatistiek van Home Assistant
# gelegd bij een echte installatie: piek, laagste en gemiddelde kwamen tot op de
# decimaal overeen. Die meting staat in de privénotities; hier staan verzonnen
# getallen omdat de meterstanden van een klant niet in een publieke repo horen.
def ms(minuut, laag, hoog, gem):
    return {"start": t(14, minuut), "min": laag, "max": hoog, "mean": gem}


blokjes = {"sensor.proef": [
    ms(0, 100.0, 900.0, 300.0),
    ms(5, 50.0, 400.0, 200.0),
    ms(10, 200.0, 1500.0, 400.0),
    ms(15, 0.0, 100.0, 60.0),
]}
kwartieren = archive.Archive.kwartieren_uit_blokjes(blokjes)
controle("vier blokjes geven twee kwartieren", len(kwartieren) == 2,
         f"{len(kwartieren)}")
_, _, laagste, piek, gemiddeld, seconden = kwartieren[0]
print(f"  eerste kwartier: laag {laagste:.0f}, piek {piek:.0f}, "
      f"gemiddeld {gemiddeld:.0f}, {seconden:.0f} s")
controle("de piek is de hoogste van de drie", piek == 1500.0, f"{piek}")
controle("het laagste is de laagste van de drie", laagste == 50.0, f"{laagste}")
controle("het gemiddelde is het gemiddelde van de drie",
         abs(gemiddeld - 300.0) < 1e-9, f"{gemiddeld}")
controle("en drie blokjes dekken een heel kwartier", seconden == 900.0, f"{seconden}")
controle("het losse blokje staat er als een kwart kwartier",
         kwartieren[1][5] == 300.0, f"{kwartieren[1]}")

# Een blokje zonder gemiddelde is geen meting en telt niet mee.
leeg = {"sensor.proef": [ms(0, 1.0, 2.0, None), ms(5, 50.0, 400.0, 200.0)]}
uit = archive.Archive.kwartieren_uit_blokjes(leeg)
controle("een blokje zonder gemiddelde wordt overgeslagen",
         len(uit) == 1 and uit[0][5] == 300.0, f"{uit}")

print("=== 9. de recorder telt in seconden, niet in milliseconden ===")
# Deze proef bestaat omdat het bij de eerste klant precies hier misging. Het
# websocketcommando van Home Assistant geeft `start` in milliseconden, de
# Python-API in seconden. Die vorm had ik overgenomen, en dus kwamen alle
# kwartieren in januari 1970 terecht; de eerste opruimronde veegde ze weg en er
# stond nul in de opslag zonder dat er iets fout leek te gaan.
sec = dt.datetime(2026, 8, 28, 14, 0).timestamp()
uit = archive.Archive.kwartieren_uit_blokjes(
    {"sensor.proef": [{"start": sec, "min": 10.0, "max": 90.0, "mean": 50.0}]}
)
controle("een tijdstempel in seconden landt op het goede kwartier",
         bool(uit) and uit[0][1] == int(sec), f"{uit}")
if uit:
    print(f"  {sec:.0f} -> {dt.datetime.fromtimestamp(uit[0][1]):%d-%m-%Y %H:%M}")

# En de ondergrens vangt de fout die dit was, mocht hij ooit terugkomen.
in_ms = {"sensor.proef": [{"start": sec * 1000 / 1_000_000, "min": 1.0, "max": 2.0,
                           "mean": 1.5}]}
controle("een tijdstempel uit 1970 wordt niet weggeschreven",
         archive.Archive.kwartieren_uit_blokjes(in_ms) == [],
         f"{archive.Archive.kwartieren_uit_blokjes(in_ms)}")

print()
print(f"{GOED} goed, {FOUT} fout")
sys.exit(1 if FOUT else 0)
