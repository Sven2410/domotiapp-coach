"""Live meekijken aan een laadpaal. Leest alleen, schrijft nooit.

Alles gaat in live.log; alleen betekenisvolle overgangen gaan naar stdout,
want dat zijn de dingen waar ik iets van moet vinden.

Welke entiteiten erbij horen wordt aan het paneel zelf gevraagd
(`domotiapp_coach/settings/get`) in plaats van hier opgeschreven. Dat is niet
alleen handiger bij een klant, het is ook nodig: deze repo is publiek, en een
entiteitnaam van een auto draagt bij sommige merken het chassisnummer met zich
mee. Zulke namen horen niet in code die iedereen kan lezen.

Wat je zelf nog kunt meegeven zijn de sensoren die niet uit het paneel komen:

    python tools/live.py --extra zon=sensor.omvormer_vermogen
"""
import sys, time, datetime
import ha
import ws


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
            "teller": ent.get("lifetime_energy"),
        })
        for auto in apparaat.get("cars") or []:
            if auto.get("soc_entity"):
                uit["soc"] = auto["soc_entity"]
    bronnen = inst.get("sources") or {}
    uit["afname"] = bronnen.get("grid_import")
    uit["terug"] = bronnen.get("grid_export")
    for fase in ("l1", "l2", "l3"):
        uit[fase] = ((bronnen.get("phases") or {}).get(fase) or {}).get("current")

    for arg in sys.argv[1:]:
        if "=" in arg:
            naam, ent = arg.split("=", 1)
            uit[naam.lstrip("-")] = ent

    return {k: v for k, v in uit.items() if v}


E = entiteiten()

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
    s = st.get(E[key])
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
