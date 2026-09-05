"""Wachter op de verbinding met de installatie. Leest alleen.

Probeert elke dertig seconden elk adres uit het tokenbestand en schrijft alleen
een regel als er iets verandert: een adres dat wegvalt, een adres dat
terugkomt, en hoe lang het weg was. Zo is achteraf te zien of een gat in de
andere logs aan de verbinding lag, aan Home Assistant (dan zijn beide adressen
tegelijk weg) of aan de coach.

    python tools/verbinding.py                 # naar stdout
    python tools/verbinding.py verbinding.log 30
"""
import datetime, sys, time
import ha

PAD = sys.argv[1] if len(sys.argv) > 1 else None
ELKE = float(sys.argv[2]) if len(sys.argv) > 2 else 30
log = open(PAD, "a", encoding="utf-8", buffering=1) if PAD else None


def nu():
    return datetime.datetime.now().strftime("%d-%m %H:%M:%S")


def schrijf(regel):
    print(regel, flush=True)
    if log:
        log.write(regel + "\n")


def proef(host):
    t0 = time.time()
    try:
        r = ha._haal(host, "/api/config", 8)
        return True, f"{(time.time() - t0) * 1000:.0f} ms, HA {r.get('version', '?')}"
    except Exception as e:  # noqa: BLE001 - elke reden is "weg"
        return False, str(e)[:120]


stand = {}
sinds = {}
schrijf(f"{nu()}  [wachter op {len(ha.ADRESSEN)} adressen, elke {ELKE:.0f} s]")
while True:
    for host in ha.ADRESSEN:
        ok, uitleg = proef(host)
        adres = f"{ha.schema_van(host)}://{host}"
        if host not in stand:
            schrijf(f"{nu()}  {adres}: {'bereikbaar' if ok else 'NIET bereikbaar'} ({uitleg})")
        elif ok != stand[host]:
            if ok:
                schrijf(f"{nu()}  {adres}: TERUG na {time.time() - sinds[host]:.0f} s ({uitleg})")
            else:
                schrijf(f"{nu()}  {adres}: WEG ({uitleg})")
        if ok != stand.get(host):
            sinds[host] = time.time()
        stand[host] = ok
    time.sleep(ELKE)
