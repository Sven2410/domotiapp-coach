"""Live meekijken aan Svens paal tijdens de fasetest. Leest alleen, schrijft nooit.

Alles gaat in live.log; alleen betekenisvolle overgangen gaan naar stdout,
want dat zijn de dingen waar ik iets van moet vinden.
"""
import sys, time, datetime
import ha

E = {
    "status": "sensor.laadpaal_status",
    "watt": "sensor.laadpaal_vermogen",
    "amp": "sensor.emytx4ma_stroom",
    "limiet": "sensor.emytx4ma_dynamisch_laadgrens_van_lader",
    "circuit": "sensor.emytx4ma_dynamic_laadgrens_van_stroomcircuit",
    "reden": "sensor.emytx4ma_reden_geen_stroom",
    "fasemode": "sensor.emytx4ma_fase_mode",
    "volt": "sensor.emytx4ma_voltage",
    "soc": "sensor.fcq_wf0cxxsk1sx003660_soc",
    "plug": "sensor.fcq_wf0cxxsk1sx003660_elvehplug",
    "sessie": "sensor.laadpaal_sessie_energie",
    "teller": "sensor.laadpaal_levensduur_verbruik",
    "l1": "sensor.electricity_meter_stroom_fase_l1",
    "l2": "sensor.electricity_meter_stroom_fase_l2",
    "l3": "sensor.electricity_meter_stroom_fase_l3",
    "zon": "sensor.solaredge_i1_ac_power",
}

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
