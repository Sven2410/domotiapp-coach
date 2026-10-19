# Zomer- en wintertijd

De eigenaar op 19-10-2026: "ik wil dat je sowieso rekening houd met de zomer en wintertijd.
Dat moet allemaal vanzelf gaan."

Twee keer per jaar verspringt de klok, in de hele EU op hetzelfde moment: om 01:00 UTC op de
laatste zondag van maart (een uur vooruit; die dag heeft 23 uur en 92 kwartieren) en van
oktober (een uur terug; 25 uur, 100 kwartieren). In Nederland komt 02:00 tot 03:00 dan twee
keer, in Portugal 01:00 tot 02:00. Zondag 25-10-2026 is de eerste wintertijd die de coach
meemaakt; de volgende zomertijd is 28-03-2027.

De coach rekent intern in lokale tijd zonder tijdzone (`_moment` in coach.py), en dat blijft
zo: de planner en de batterij plannen op de klok van het huis, zoals de klaar-tijd en de
avondpiek ook op die klok staan. In het uur dat twee keer komt houdt Python de twee uit elkaar
met `fold` (0 de eerste keer, 1 de tweede), en `dt_util.as_utc` van Home Assistant leest een
lokale tijd zo. Maar `==`, `hash` en aftrekken kijken niet naar `fold`, en daar zat het.

## Wat er sinds v0.139.1 vanzelf goed gaat

- **De kwartieropslag** (archive.py) rekent alleen nog in UTC: `utcnow`, `time_fired`, de
  kwartiergrenzen, de tijdstempels en het aanvullen uit de recorder. Tot dan liep zijn klok bij
  de wintertijd een uur terug: het hele tweede uur kwam in één kwartier van 75 minuten, het uur
  ervoor viel weg, en dat bleef twee jaar zo bewaard. Wie een lokale tijd meegeeft wordt
  omgerekend met `as_utc` (`_utc`). Een tijdstempel hangt zo ook niet meer af van de tijdzone van
  de container. Het teruglezen in de coach (`datetime.fromtimestamp`) gebruikt nog de tijdzone van
  de container; op Home Assistant OS is die gelijk aan die van Home Assistant, en dan zet Python
  zelf `fold` goed.
- **De regelaar van de thuisbatterij** heeft een eigen klok, `_regelklok` (UTC). Met de lokale
  klok werd "sinds de opdracht" na 03:00 negatief: de regelaar wachtte een uur op een opdracht
  die al stond, en de bewaking van een stille meter stond zo lang uit.
- **Een prijs per uur of per kwartier** in het herhaalde uur: `_naast_elkaar` voegt de twee
  samen tot één blok op de lokale klok, met het gemiddelde van beide prijzen, dat twee echte uren
  duurt. Tot dan overschreef het tweede uur het eerste, en kreeg het laatste kwartier van het
  eerste uur een einde vóór zijn begin. Hetzelfde in Portugal (`_pt_rijen`), waar elk kwartier
  van dat uur er twee keer stond.
- **Hoe lang iets duurde** (`_tussen`): een programma dat over de wissel heen draait, de
  meetpunten van zijn profiel, wanneer het stil is, en de minuten van de sensorwacht. Een
  vaatwasser van 01:30 tot 03:30 liep op de klok twee uur en echt drie.
- **Het paneel** (`alsHuis` in format.js) geeft het echte moment terug zolang de browser
  hetzelfde aanwijst als het huis, zodat de twee uren van 02:00 in Historie niet samenvallen
  (v0.138.2; `docs/paneel.md`).

Proeven: 181 in test_coach.py, 10 in test_archive.py, en "Historie op de klok van het huis, en
de wintertijd" in test_rapport.mjs. `tests/zomertijd.py` is een Europese tijdzone zonder
`tzdata`, voor de proeven.

## Wat nog niet, en wanneer het telt

- **Vóór 28-03-2027:** de planner rekent de tijd tot de klaar-tijd en wat er per uur in kan
  (`capaciteit_kwh`, `_latest_start`, `plan_end`, de slack, `_nacht_uren`) met lokale tijden. Bij
  de wintertijd is dat voorzichtig (er is een uur meer dan hij denkt), bij de zomertijd niet: dan
  mist er een uur, en dat eet het uur reserve voor de klaar-tijd op. Ook staat er bij een vast
  contract dan een uur van 02:00 in de lijst dat niet bestaat (`_vlakke_blokken`). Te doen: de
  uren in UTC tellen, en de lokale klok alleen voor de klaar-tijd en de avondpiek.
- **Klein:** timers die op de lokale klok lopen (het bewaren van een sessie om de vijf minuten,
  het verversen van de zon- en huisverwachting) staan na 03:00 een uur stil; de vooruitblik
  toont 24 kolommen op een dag van 25 uur; een tijdsensor in het herhaalde uur staat een uur te
  vroeg in Home Assistant.
- **Een paneel in een andere tijdzone dan het huis** ziet het herhaalde uur nog als één uur.
