"""De schaduwcoach: de echte coach.py naast een echte installatie, zonder iets te schrijven.

Wat de coach zou doen terwijl iets anders stuurt. De eigenaar op 25-09-2026, toen
in de eerste woning Omnibattery de batterij stuurde: "kijk of de coach hetzelfde en
het goede zou doen." Hier draait de coach uit deze map (dus de versie die hier
staat) in het nagemaakte Home Assistant van de proeven (`tests/harnas.py`), gevoed
met de toestanden van de echte installatie over de websocket. Elke opdracht die hij
geeft wordt opgeschreven en gaat nergens heen: de websocket wordt alleen gelezen.

Gebruik (met HA_INSTALLATIE gezet, net als de andere loggers):

    python tools/schaduw.py schaduw.log                       # de instellingen zoals ze zijn
    python tools/schaduw.py schaduw.log sturen=<apparaat-id>  # dit apparaat mag in de schaduw sturen
    python tools/schaduw.py schaduw.log sturen=<id> zelf=1    # en de batterij doet zelf nul op de meter
    python tools/schaduw.py schaduw.log naast=sensor.a,sensor.b  # per minuut ernaast in het log

Per minuut een regel per gestuurde batterij: wat de coach zou doen (stand, regel,
opdracht, of hij het zelf laat doen) en wat er werkelijk gebeurt (het vermogen van
de batterij, de meter, de accustand), plus de entiteiten van `naast=`. Bij elke
opdracht die hij zou schrijven een eigen regel. Wat hij in de geschiedenis zou
zetten en op de telefoon zou melden komt er ook in.

Wat hier níet te zien is: hoe de batterij op zijn opdrachten zou reageren. Die gaan
nergens heen, dus de lus is open; de regelaar rekent met wat de batterij werkelijk
doet. Dat vergelijkt het doel, niet de regeling. De regeling zelf is iets voor het
virtuele huis.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import pathlib
import queue
import sys
import threading
import time

HIER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "tests"))
sys.path.insert(0, str(HIER))

import harnas  # noqa: E402  (zet het nagemaakte Home Assistant en de coach klaar)
import ws  # noqa: E402

coachmod = harnas.coachmod
dtutil = sys.modules["homeassistant.util.dt"]

# De klok van deze machine, in de tijdzone van deze machine: net als Home Assistant
# zelf, en niet de vaste tijden van de proeven.
dtutil.utcnow = lambda: dt.datetime.now(dt.timezone.utc)
dtutil.now = lambda: dt.datetime.now().astimezone()
dtutil.as_local = lambda moment: moment.astimezone()

ARGS = [a for a in sys.argv[1:] if "=" not in a]
OPTIES = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
PAD = ARGS[0] if ARGS else None
STUREN = [x for x in OPTIES.get("sturen", "").split(",") if x]
ZELF = OPTIES.get("zelf", "") in ("1", "ja", "aan")
NAAST = [x for x in OPTIES.get("naast", "").split(",") if x]

log = open(PAD, "a", encoding="utf-8", buffering=1) if PAD else None


def nu_tekst() -> str:
    return dt.datetime.now().strftime("%d-%m %H:%M:%S")


def schrijf(regel: str) -> None:
    print(regel, flush=True)
    if log:
        log.write(regel + "\n")


def vraag(type_: str, **kw):
    """Eén vraag over een eigen verbinding, met een paar pogingen."""
    for poging in range(4):
        try:
            w = ws.WS()
            try:
                return w.vraag(type_, **kw)
            finally:
                try:
                    w.s.close()
                except OSError:
                    pass
        except Exception as e:  # noqa: BLE001 - Nabu Casa hapert wel eens
            if poging == 3:
                raise
            schrijf(f"{nu_tekst()}  [vraag {type_} mislukt: {e}; opnieuw]")
            time.sleep(3)
    return None


def lees_tijd(tekst):
    try:
        return dt.datetime.fromisoformat(str(tekst)) if tekst else None
    except ValueError:
        return None


# --- de instellingen, met wat de schaduw anders mag -----------------------------

def instellingen() -> dict:
    inst = vraag("domotiapp_coach/settings/get")
    inst = inst.get("settings", inst) if isinstance(inst, dict) else {}
    for device in inst.get("devices") or []:
        if device.get("id") in STUREN:
            device["controllable"] = True
            if ZELF and device.get("type") == "thuisbatterij":
                device.setdefault("battery", {})["self_zero"] = True
    return inst


INST = instellingen()
GESTUURD = [d for d in INST.get("devices") or [] if d.get("id") in STUREN or (not STUREN and d.get("controllable"))]
BATTERIJEN = [d for d in GESTUURD if d.get("type") == "thuisbatterij"]

# Wat de schaduw zelf schrijft, leest hij ook zelf terug: de modus en het stuurgetal
# van een batterij die hij stuurt. Die worden niet van de installatie overgenomen,
# anders ziet hij de modus van de andere sturing en denkt hij dat iets anders hem
# overneemt.
EIGEN: set[str] = set()
for device in BATTERIJEN:
    ents = device.get("entities") or {}
    EIGEN |= {e for e in (ents.get("setpoint"), ents.get("direction"), ents.get("mode"), ents.get("charge_limit")) if e}


# --- Home Assistant, nagemaakt en gevoed met de echte toestanden -----------------

def als_waarde(toestand: dict):
    return {"state": toestand.get("state"), "attributes": dict(toestand.get("attributes") or {})}


hass = harnas.NepHass({})
store = harnas.NepStore(INST)
hass.data["domotiapp_coach"] = {"store": store}


def spiegel(toestand: dict) -> None:
    eid = toestand.get("entity_id", "")
    if not eid or eid in EIGEN:
        return
    hass.states.zet(eid, als_waarde(toestand), last_updated=lees_tijd(toestand.get("last_updated")))


for t in vraag("get_states") or []:
    spiegel(t)
# De eigen entiteiten beginnen met wat er nu werkelijk staat.
for t in vraag("get_states") or []:
    if t.get("entity_id") in EIGEN:
        hass.states.zet(t["entity_id"], als_waarde(t), last_updated=lees_tijd(t.get("last_updated")))


class LiveArchief:
    """De eigen opslag van de coach, via de websocket."""

    async def async_lees(self, entity_ids, start, einde):
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: vraag("domotiapp_coach/history/quarters", entity_ids=list(entity_ids),
                                start=start.isoformat(), end=einde.isoformat()) or {}
        )


coachmod.async_get_archive = lambda _hass: LiveArchief()


class Opgeschreven(harnas.Diensten):
    """Elke dienst wordt opgeschreven, en wat de schaduw aan zijn eigen entiteiten doet
    ziet hij terug, zoals Home Assistant dat zou doen."""

    async def async_call(self, domein, dienst, data, blocking=False):
        await super().async_call(domein, dienst, data, blocking)
        eid = data.get("entity_id")
        if eid in EIGEN:
            waarde = data.get("option", data.get("value"))
            oud = hass.states.get(eid)
            hass.states.zet(eid, {"state": str(waarde), "attributes": dict(getattr(oud, "attributes", {}) or {})})
            schrijf(f"{nu_tekst()}  OPDRACHT  {eid} = {waarde}")
        elif domein == "notify":
            schrijf(f"{nu_tekst()}  ZOU MELDEN  {data.get('message', '')}")


hass.services = Opgeschreven()
coach = coachmod.ChargerCoach(hass)
coach._sleep = lambda seconds: asyncio.sleep(0)


async def zonkromme():
    """De uurkromme van het energiedashboard, zoals `_async_zon_uit_dashboard` hem leest."""
    try:
        data = await asyncio.get_running_loop().run_in_executor(None, lambda: vraag("energy/solar_forecast") or {})
    except Exception:  # noqa: BLE001
        return {}
    uit: dict[dt.datetime, float] = {}
    for bron in (data or {}).values():
        for stempel, wh in ((bron or {}).get("wh_hours") or {}).items():
            moment = lees_tijd(stempel)
            if moment is None:
                continue
            uur = coachmod._moment(moment).replace(minute=0, second=0, microsecond=0)
            uit[uur] = uit.get(uur, 0.0) + float(wh) / 1000.0
    return uit


coach._async_zon_uit_dashboard = zonkromme

eigen_noteer = coach._async_noteer


async def noteer(tekst, *args, **kwargs):
    schrijf(f"{nu_tekst()}  GESCHIEDENIS  {tekst}")
    return await eigen_noteer(tekst, *args, **kwargs)


coach._async_noteer = noteer


# --- meeluisteren ---------------------------------------------------------------

wachtrij: queue.Queue = queue.Queue()


def luister() -> None:
    while True:
        try:
            w = ws.WS()
            w.s.settimeout(60)
            w.id += 1
            w.send({"id": w.id, "type": "subscribe_events", "event_type": "state_changed"})
            wachtrij.put(("verbonden", None))
            while True:
                m = w.recv()
                if m.get("type") == "event":
                    nieuw = ((m.get("event") or {}).get("data") or {}).get("new_state")
                    if nieuw:
                        wachtrij.put(("toestand", nieuw))
        except Exception as e:  # noqa: BLE001
            wachtrij.put(("weg", str(e)))
            time.sleep(5)


def meters() -> set[str]:
    bronnen = INST.get("sources") or {}
    if bronnen.get("grid_mode") == "signed":
        return {bronnen.get("grid_signed")} - {None, ""}
    return {bronnen.get("grid_import"), bronnen.get("grid_export")} - {None, ""}


METERS = meters()


def getal(eid):
    staat = hass.states.get(eid) if eid else None
    try:
        return float(staat.state)
    except (AttributeError, TypeError, ValueError):
        return None


def tekst_van(eid):
    staat = hass.states.get(eid)
    return "?" if staat is None else str(staat.state)


vorige_kern: dict[str, tuple] = {}


def minuutregel() -> None:
    netto, _ = coach._net_nu(INST)
    for device in BATTERIJEN:
        did = device.get("id", "")
        b = coach.state.get(did) or {}
        sessie = coach._batterij.get(did) or {}
        kern = (b.get("mode"), b.get("rule"), b.get("self_zero"))
        if kern != vorige_kern.get(did):
            vorige_kern[did] = kern
            schrijf(f"{nu_tekst()}  REDEN  {b.get('mode_name')}: {b.get('reason')}")
        opdracht = None if sessie.get("zelf") else round(sessie["regelaar"].opdracht_w) if sessie.get("regelaar") else None
        echt = coach._batterij_w(device)
        naast = "  ".join(f"{e.split('.', 1)[-1][-28:]}={tekst_van(e)}" for e in NAAST)
        schrijf(
            f"{nu_tekst()}  COACH {b.get('mode') or '?':10s} {b.get('rule') or '':18s} "
            f"{'zelf' if b.get('self_zero') else 'opdracht=' + str(opdracht):16s} | "
            f"ECHT accu={'?' if echt is None else round(echt)} W  meter={'?' if netto is None else round(netto)} W  "
            f"soc={b.get('soc')}%  {naast}"
        )


async def hoofd() -> None:
    threading.Thread(target=luister, daemon=True).start()
    schrijf(f"{nu_tekst()}  [schaduw: stuurt {[d.get('id') for d in GESTUURD]}, zelf nul op de meter {'aan' if ZELF else 'uit'}, "
            f"eigen entiteiten {sorted(EIGEN)}, meter {sorted(METERS)}]")
    volgende_ronde = 0.0
    volgende_tik = 0.0
    volgende_inst = time.time() + 300
    while True:
        regel_nu = False
        try:
            while True:
                soort, inhoud = wachtrij.get_nowait()
                if soort == "toestand":
                    spiegel(inhoud)
                    if inhoud.get("entity_id") in METERS:
                        regel_nu = True
                elif soort == "weg":
                    schrijf(f"{nu_tekst()}  [verbinding kwijt: {inhoud}; opnieuw aanhaken]")
                elif soort == "verbonden":
                    schrijf(f"{nu_tekst()}  [luistert mee]")
        except queue.Empty:
            pass
        klok = time.time()
        try:
            if klok >= volgende_inst:
                volgende_inst = klok + 300
                nieuw = await asyncio.get_running_loop().run_in_executor(None, instellingen)
                # Wat de schaduw zelf bijhield (battery_state, sessions) blijft van hem.
                for sleutel, waarde in nieuw.items():
                    if sleutel not in ("battery_state", "sessions", "car_pace", "car_efficiency", "sensor_quiet"):
                        INST[sleutel] = waarde
            if klok >= volgende_ronde:
                volgende_ronde = klok + 60
                async with asyncio.timeout(55):
                    await coach._round(None)
                await hass.afmaken()
                minuutregel()
                hass.services.verstuurd.clear()
            if regel_nu or klok >= volgende_tik:
                volgende_tik = klok + 5
                await coach._async_regel_tik()
                await hass.afmaken()
        except Exception as e:  # noqa: BLE001 - de schaduw mag niet stilvallen op één fout
            schrijf(f"{nu_tekst()}  [fout in de ronde: {type(e).__name__}: {e}]")
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(hoofd())
