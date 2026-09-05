"""Luister mee met de meldingen van de coach, en leg elke vijf minuten zijn
hele stand vast. Leest alleen.

    python tools/meldingen.py                  # meldingen naar stdout
    python tools/meldingen.py stand.jsonl 300  # en de stand elke 300 s in dat bestand

De meldingen zijn wat de bewoner te zien krijgt; de stand is alles wat het
paneel weet (regel, stroom, plan, tijdlijn), zodat achteraf na te rekenen is
waarom een besluit viel. besluiten.py laat alleen de wijzigingen zien en
zonder plan; dit is het geheugen ernaast.
"""
import datetime, json, sys, time, ws

PAD = sys.argv[1] if len(sys.argv) > 1 else "stand.jsonl"
ELKE = float(sys.argv[2]) if len(sys.argv) > 2 else 300


def verbind():
    while True:
        try:
            return _verbind()
        except Exception as e:
            print(f"[nog geen verbinding: {e}; over tien seconden opnieuw]", flush=True)
            time.sleep(10)


def _verbind():
    w = ws.WS()
    w.s.settimeout(ELKE)  # even niets is geen storing, maar wel het sein voor een stand
    w.id += 1
    w.send({"id": w.id, "type": "subscribe_events",
            "event_type": "domotiapp_coach_notification"})
    return w


def stand(w):
    """De stand van nu, één regel json met de tijd erbij."""
    w.id += 1
    w.send({"id": w.id, "type": "domotiapp_coach/coach/state"})
    return w.id


def nu():
    return datetime.datetime.now().strftime("%d-%m %H:%M:%S")


w = verbind()
log = open(PAD, "a", encoding="utf-8", buffering=1)
print(f"[luistert naar de meldingen; de stand elke {ELKE:.0f} s in {PAD}]", flush=True)
wacht_op = stand(w)
laatste = time.time()
while True:
    try:
        m = w.recv()
    except TimeoutError:
        m = None
    except Exception as e:
        print(f"[verbinding kwijt: {e}; opnieuw aanhaken]", flush=True)
        time.sleep(3)
        w = verbind()
        wacht_op = stand(w)
        laatste = time.time()
        continue
    if m is None or time.time() - laatste >= ELKE:
        wacht_op = stand(w)
        laatste = time.time()
        if m is None:
            continue
    if m.get("type") == "ping":
        w.send({"id": m.get("id"), "type": "pong"})
        continue
    if m.get("type") == "result" and m.get("id") == wacht_op:
        st = m.get("result") or {}
        log.write(json.dumps({"tijd": nu(), "stand": st}, ensure_ascii=False) + "\n")
        kort = []
        for dev, d in st.items():
            if not isinstance(d, dict):
                continue
            kort.append(f"{d.get('rule', '?')} {d.get('amps', '?')} A "
                        f"{(d.get('reason') or d.get('text') or '')[:120]}")
        print(f"{nu()}  stand: " + " | ".join(kort), flush=True)
        continue
    if m.get("type") != "event":
        continue
    d = (m.get("event") or {}).get("data") or {}
    print(f"{nu()}  MELDING  {json.dumps(d, ensure_ascii=False)}", flush=True)
