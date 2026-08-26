"""Luister mee met de besluiten die de coach uitzendt. Leest alleen."""
import datetime, json, time, ws


def verbind():
    """Opnieuw aanhaken als de verbinding wegvalt; stilte mag geen einde zijn.

    Blijft proberen, want een Home Assistant die herstart weigert verbindingen
    en dat is geen reden om te stoppen met meekijken.
    """
    while True:
        try:
            return _verbind()
        except Exception as e:
            print(f"[nog geen verbinding: {e}; over tien seconden opnieuw]", flush=True)
            time.sleep(10)


def _verbind():
    w = ws.WS()
    w.s.settimeout(None)  # een coach die even niets besluit is geen storing
    w.id += 1
    w.send({"id": w.id, "type": "subscribe_events",
            "event_type": "domotiapp_coach_decision"})
    return w


w = verbind()
vorige = [None]
print("[luistert naar de besluiten van de coach; alleen wijzigingen]", flush=True)
while True:
    try:
        m = w.recv()
    except Exception as e:
        print(f"[verbinding kwijt: {e}; opnieuw aanhaken]", flush=True)
        time.sleep(3)
        w = verbind()
        continue
    if m.get("type") == "ping":
        # Home Assistant sluit de verbinding als hier niets op terugkomt.
        w.send({"id": m.get("id"), "type": "pong"})
        continue
    if m.get("type") != "event":
        continue
    d = (m.get("event") or {}).get("data") or {}
    kort = {k: v for k, v in d.items()
            if k in ("device", "amps", "rule", "charge", "charging", "text", "plan", "reason")}
    kern = (kort.get("charge"), kort.get("amps"), kort.get("rule"),
            kort.get("reason"), d.get("level"), d.get("paused"), d.get("boost"))
    if kern == vorige[0]:
        continue  # hetzelfde besluit als vorige ronde is geen nieuws
    vorige[0] = kern
    tijd = datetime.datetime.now().strftime("%H:%M:%S")
    regel = kort.get("rule", "?")
    amps = kort.get("amps", "?")
    laden = "laden" if kort.get("charge") else "NIET laden"
    tekst = (kort.get("reason") or kort.get("text") or "")[:180]
    print(f"{tijd}  {laden} {amps} A  regel={regel}  {tekst}", flush=True)
    rest = {k: v for k, v in d.items() if k not in kort and k != "device"}
    if rest:
        print(f"          overig: {json.dumps(rest, ensure_ascii=False)[:300]}", flush=True)
