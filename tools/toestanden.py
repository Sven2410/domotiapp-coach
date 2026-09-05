"""Elke toestandswisseling van de sensoren die de coach gebruikt, zoals
Home Assistant hem uitzendt. Leest alleen.

    python tools/toestanden.py                 # naar stdout
    python tools/toestanden.py toestanden.log  # en in dat bestand

Anders dan live.py, die elke vijf seconden een foto neemt, mist dit niets:
een sensor die een seconde `unavailable` was staat er met de seconde erbij.
Welke sensoren dat zijn komt uit het paneel en het entiteitenregister, op
dezelfde manier als in live.py. Valt de verbinding weg, dan haakt hij opnieuw
aan en zegt hoe lang hij weg was.
"""
import datetime, re, sys, time, ws

MERKSENSOREN = {
    "easee": ("session_energy", "voltage", "phase_mode", "cable_locked",
              "dynamic_circuit_limit", "easee_status", "power", "current",
              "dynamic_charger_limit", "max_charger_limit",
              "easee_reason_no_current", "lifetime_energy", "energy_per_hour",
              "circuit_current", "online", "enable_idle_current"),
}

PAD = sys.argv[1] if len(sys.argv) > 1 else None
log = open(PAD, "a", encoding="utf-8", buffering=1) if PAD else None


def nu():
    return datetime.datetime.now().strftime("%d-%m %H:%M:%S")


def schrijf(regel):
    print(regel, flush=True)
    if log:
        log.write(regel + "\n")


def entiteiten(w):
    inst = w.vraag("domotiapp_coach/settings/get")
    uit = set()

    # Elke entiteit-id waar dan ook in de instellingen: bronnen, prijs,
    # lastbewaker, zonverwachting, meters, auto's. Zo mist hij er geen als
    # er een nieuw veld bij komt.
    def loop(x):
        if isinstance(x, dict):
            for v in x.values():
                loop(v)
        elif isinstance(x, list):
            for v in x:
                loop(v)
        elif isinstance(x, str) and re.match(r"^[a-z_]+\.[a-z0-9_]+$", x):
            uit.add(x)

    loop(inst)
    apparaten = [(a.get("device_id"), a.get("brand")) for a in inst.get("devices") or []]
    # De rest van de paal uit het register, op translation_key.
    try:
        rijen = w.vraag("config/entity_registry/list")
    except Exception as e:
        print(f"[entiteitenregister niet te lezen: {e}]", file=sys.stderr)
        rijen = []
    for device_id, merk in apparaten:
        sleutels = MERKSENSOREN.get(merk, ())
        for rij in rijen:
            if (rij.get("device_id") == device_id and not rij.get("disabled_by")
                    and rij.get("translation_key") in sleutels):
                uit.add(rij["entity_id"])
    return uit


def verbind():
    weg = None
    while True:
        try:
            w = ws.WS()
            w.s.settimeout(None)
            ents = entiteiten(w)
            w.id += 1
            w.send({"id": w.id, "type": "subscribe_events", "event_type": "state_changed"})
            if weg:
                schrijf(f"{nu()}  [verbinding terug na {time.time() - weg:.0f} s]")
            return w, ents
        except Exception as e:
            if weg is None:
                weg = time.time()
            schrijf(f"{nu()}  [geen verbinding: {e}; over tien seconden opnieuw]")
            time.sleep(10)


w, ENT = verbind()
schrijf(f"{nu()}  [volgt {len(ENT)} entiteiten: {', '.join(sorted(ENT))}]")
while True:
    try:
        m = w.recv()
    except Exception as e:
        schrijf(f"{nu()}  [verbinding kwijt: {e}; opnieuw aanhaken]")
        time.sleep(3)
        w, ENT = verbind()
        continue
    if m.get("type") == "ping":
        w.send({"id": m.get("id"), "type": "pong"})
        continue
    if m.get("type") != "event":
        continue
    d = (m.get("event") or {}).get("data") or {}
    ent = d.get("entity_id")
    if ent not in ENT:
        continue
    oud = (d.get("old_state") or {}).get("state")
    nieuw = (d.get("new_state") or {}).get("state")
    if oud == nieuw:
        continue  # alleen een attribuut veranderde
    schrijf(f"{nu()}  {ent:<50} {oud} -> {nieuw}")
