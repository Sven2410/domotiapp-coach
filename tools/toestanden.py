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
import datetime, sys, time, ws

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
    apparaten = []
    for apparaat in inst.get("devices") or []:
        if apparaat.get("entity"):
            uit.add(apparaat["entity"])
        for v in (apparaat.get("entities") or {}).values():
            if isinstance(v, str) and "." in v:
                uit.add(v)
        if apparaat.get("energy_entity"):
            uit.add(apparaat["energy_entity"])
        for auto in apparaat.get("cars") or []:
            if auto.get("soc_entity"):
                uit.add(auto["soc_entity"])
        apparaten.append((apparaat.get("device_id"), apparaat.get("brand")))
    bronnen = inst.get("sources") or {}
    for k, v in bronnen.items():
        if isinstance(v, str) and "." in v:
            uit.add(v)
    for fase in (bronnen.get("phases") or {}).values():
        if isinstance(fase, dict):
            for v in fase.values():
                if isinstance(v, str) and "." in v:
                    uit.add(v)
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
