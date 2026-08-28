"""Live meekijken aan een laadpaal. Leest alleen, schrijft nooit.

Alles gaat in live.log; alleen betekenisvolle overgangen gaan naar stdout,
want dat zijn de dingen waar ik iets van moet vinden.

**Hij moet bij elke klant draaien zonder dat er iets ingetypt wordt.** Daarom
zoekt hij zijn sensoren zelf op, in deze volgorde:

1. **Het paneel** (`domotiapp_coach/settings/get`) voor alles wat de coach zelf
   leest. Wat hij stuurt hoort te zijn wat je meet.
2. **Het entiteitenregister van Home Assistant** voor de rest van de paal: de
   sessie, de spanning, de fasemodus, de kabel. Dat gaat op `translation_key`
   en niet op de naam van de entiteit, want die naam is vertaald: dezelfde
   Easee heet hier `sensor.1_fase_mode` en bij een Engelse installatie
   `sensor.x_phase_mode`. De `translation_key` is bij beide `phase_mode`.
3. **Wat je zelf meegeeft** wint van allebei.

Zo staan er ook geen entiteitnamen in dit bestand. Dat is niet alleen netjes
maar nodig: deze repo is publiek, en een entiteitnaam van een auto draagt bij
sommige merken het chassisnummer met zich mee.

    python tools/live.py                       # zoekt alles zelf op
    python tools/live.py live.log 3600         # logbestand en hoeveel seconden
    python tools/live.py live.log 3600 zon=sensor.omvormer_vermogen
"""
import sys, time, datetime
import ha
import ws


# Wat een merk zijn sensoren noemt, op de `translation_key` uit het
# entiteitenregister. Die sleutel is de enige naam die niet meevertaalt en niet
# per installatie verschilt, dus het is de enige waar je op mag zoeken.
#
# Alleen wat het paneel zelf niet weet staat hier; de rest komt uit de
# instellingen, zodat meten en sturen niet uit elkaar kunnen lopen.
MERKSENSOREN = {
    "easee": {
        "sessie": "session_energy",
        "volt": "voltage",
        "fasemode": "phase_mode",
        "plug": "cable_locked",
        "circuit": "dynamic_circuit_limit",
        # Vangnet voor een paneel waar deze nog niet ingevuld zijn.
        "status": "easee_status",
        "watt": "power",
        "amp": "current",
        "limiet": "dynamic_charger_limit",
        "maxlimiet": "max_charger_limit",
        "reden": "easee_reason_no_current",
        "teller": "lifetime_energy",
    },
}


def _register(device_id):
    """De entiteiten van dit HA-apparaat, op `translation_key`.

    Het register opvragen mag alleen een beheerder. Kan het niet, dan is dat
    geen reden om te stoppen: dan draait hij op wat het paneel weet, en de
    kolommen die daarbuiten vallen blijven leeg.
    """
    if not device_id:
        return {}
    try:
        rijen = ws.WS().vraag("config/entity_registry/list")
    except Exception as e:
        print(f"[entiteitenregister niet te lezen: {e}]", file=sys.stderr)
        return {}
    uit = {}
    for rij in rijen:
        if rij.get("device_id") != device_id or rij.get("disabled_by"):
            continue
        sleutel = rij.get("translation_key")
        if sleutel:
            uit[sleutel] = rij.get("entity_id")
    return uit


def entiteiten():
    """De sensoren van deze installatie, uit de instellingen van het paneel."""
    inst = ws.WS().vraag("domotiapp_coach/settings/get")
    uit = {}
    for apparaat in inst.get("devices") or []:
        if apparaat.get("type") != "laadpaal":
            continue
        ent = apparaat.get("entities") or {}
        uit.update({
            "status": ent.get("status"),
            "watt": apparaat.get("entity"),
            "amp": ent.get("current"),
            "limiet": ent.get("dynamic_limit"),
            "maxlimiet": ent.get("max_limit"),
            "reden": ent.get("no_current_reason"),
            # De levensduurteller staat bij het apparaat zelf zodra het paneel
            # hem daar heeft staan; ouder werk zette hem tussen de entiteiten.
            "teller": ent.get("lifetime_energy") or apparaat.get("energy_entity"),
        })
        for auto in apparaat.get("cars") or []:
            if auto.get("soc_entity"):
                uit["soc"] = auto["soc_entity"]

        # De rest van de paal, opgezocht bij het merk dat de klant heeft. Wat
        # het paneel al wist blijft staan; dit vult alleen de gaten.
        register = _register(apparaat.get("device_id"))
        for naam, sleutel in MERKSENSOREN.get(apparaat.get("brand"), {}).items():
            if not uit.get(naam) and register.get(sleutel):
                uit[naam] = register[sleutel]
    bronnen = inst.get("sources") or {}
    uit["afname"] = bronnen.get("grid_import")
    uit["terug"] = bronnen.get("grid_export")
    uit["zon"] = bronnen.get("solar")
    for fase in ("l1", "l2", "l3"):
        uit[fase] = ((bronnen.get("phases") or {}).get(fase) or {}).get("current")

    # Wat je zelf meegeeft wint, want dat is het enige dat een mens intypt.
    for arg in sys.argv[1:]:
        if "=" in arg:
            naam, ent = arg.split("=", 1)
            uit[naam.lstrip("-")] = ent

    return {k: v for k, v in uit.items() if v}


E = entiteiten()

# Zeggen wat hij gevonden heeft en wat niet, want een lege kolom is anders niet
# van een sensor van nul te onderscheiden.
_alles = ["status", "watt", "amp", "limiet", "maxlimiet", "reden", "teller",
          "sessie", "soc", "volt", "fasemode", "plug", "circuit", "zon",
          "afname", "terug",
          "l1", "l2", "l3"]
_mist = [k for k in _alles if k not in E]
print(f"[live] {len(E)} sensoren gevonden"
      + (f"; niet gevonden: {', '.join(_mist)}" if _mist else ""), file=sys.stderr)


def num(st, key):
    try:
        return float(st[E[key]]["state"])
    except (TypeError, ValueError, KeyError):
        return None

def attr(st, key, naam):
    try:
        return st[E[key]]["attributes"].get(naam, "?")
    except KeyError:
        return "?"


def txt(st, key):
    # Niet elke installatie heeft elke sensor; een ontbrekende naam is geen fout.
    s = st.get(E.get(key))
    return s["state"] if s else "?"

def meet(st):
    w = num(st, "watt") or 0.0
    a = num(st, "amp") or 0.0
    v = num(st, "volt") or 230.0
    fasen = None
    ratio = None
    if a >= 2 and w > 500:
        ratio = w / (a * v)
        fasen = 3 if ratio > 2 else 1
    return w, a, fasen, ratio

def regel(st):
    w, a, fasen, ratio = meet(st)
    f = f"{ratio:.1f}~{fasen}F" if fasen else "-"
    soc = num(st, "soc")
    return (
        f"{datetime.datetime.now():%H:%M:%S} "
        f"{txt(st,'status'):<22} limiet={txt(st,'limiet'):>5} "
        f"circuit={txt(st,'circuit'):>5} "
        f"A={a:5.2f} W={w:7.0f} {f:<8} "
        f"L1={num(st,'l1') or 0:4.1f} L2={num(st,'l2') or 0:4.1f} L3={num(st,'l3') or 0:4.1f} "
        f"soc={soc if soc is not None else '?'} "
        f"sessie={num(st,'sessie') or 0:.2f} teller={num(st,'teller') or 0:.2f} "
        f"zon={num(st,'zon') or 0:.0f}W reden={txt(st,'reden')} "
        f"mode={txt(st,'fasemode')}/{attr(st,'status','config_phaseMode')} "
        f"uitgang={attr(st,'status','state_outputPhase')} plug={txt(st,'plug')}"
    )

def main():
    pad = sys.argv[1] if len(sys.argv) > 1 else "live.log"
    duur = float(sys.argv[2]) if len(sys.argv) > 2 else 5400
    einde = time.time() + duur
    log = open(pad, "a", encoding="utf-8", buffering=1)
    log.write(f"\n=== start {datetime.datetime.now():%d-%m %H:%M:%S} ===\n")
    vorig_regel = None
    vorig_kern = None
    while time.time() < einde:
        try:
            st = ha.states()
            r = regel(st)
            if r[9:] != vorig_regel:
                log.write(r + "\n")
                vorig_regel = r[9:]
            w, a, fasen, _ = meet(st)
            kern = (
                txt(st, "status"),
                txt(st, "limiet"),
                fasen,
                a > 0.5,
                txt(st, "plug"),
                txt(st, "fasemode"),
                attr(st, "status", "state_outputPhase"),
            )
            if vorig_kern is None:
                print(f"[start] {r}", flush=True)
            elif kern != vorig_kern:
                wat = []
                namen = ["status", "limiet", "fasen", "stroom loopt", "stekker", "fase_mode", "uitgangsfase"]
                for naam, oud, nieuw in zip(namen, vorig_kern, kern):
                    if oud != nieuw:
                        wat.append(f"{naam}: {oud} -> {nieuw}")
                print(f"[{' | '.join(wat)}] {r}", flush=True)
            vorig_kern = kern
        except Exception as e:
            log.write(f"{datetime.datetime.now():%H:%M:%S} FOUT {e}\n")
        time.sleep(5)
    print("[einde meting]", flush=True)

main()
