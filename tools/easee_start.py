"""Eén keer de dynamische limiet op 16 A zetten en de Easee een start sturen.

Dit is een handeling bij een klant en dus iets wat Sven zelf start:

    python tools/easee_start.py            # 16 A en start
    python tools/easee_start.py 10         # met een andere limiet

Gemaakt op 06-09-2026 om 04:50, toen de Ford bij Van den Dam na een
fasewissel van de Easee in fault stond en Sven op afstand een herstart wilde
proberen. Dezelfde twee diensten die de coach zelf gebruikt.
"""
import json, sys, urllib.request
import ha, ws

limiet = int(sys.argv[1]) if len(sys.argv) > 1 else 16
inst = ws.WS().vraag("domotiapp_coach/settings/get")
paal = next(d for d in inst["devices"] if d.get("type") == "laadpaal")
device_id = paal.get("device_id")
print(f"paal: {paal.get('name')} ({device_id})")


def dienst(naam: str, data: dict) -> int:
    req = urllib.request.Request(
        f"{ha.SCHEMA}://{ha.host()}/api/services/easee/{naam}",
        data=json.dumps(data).encode(),
        headers={"Authorization": f"Bearer {ha.TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status


print(f"limiet {limiet} A:", dienst("set_charger_dynamic_limit",
                                    {"device_id": device_id, "current": limiet, "time_to_live": 0}))
print("start:", dienst("action_command", {"device_id": device_id, "action_command": "start"}))
