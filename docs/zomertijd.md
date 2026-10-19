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
avondpiek ook op die klok staan. Alleen een duur gaat sinds v0.140.1 in echte uren (zie
hieronder). In het uur dat twee keer komt houdt Python de twee uit elkaar
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

## Wat er sinds v0.140.1 vanzelf goed gaat: de planner en de batterij

De planner en de batterij rekenen nog steeds op de klok van het huis, maar elke duur en elke
capaciteit gaat in echte uren. planner.py kent daarvoor de tijdzone van het huis, een keer voor
het hele proces zoals de taal in taal.py: `zet_zone`, en de coach zet hem bij elke ronde
(`_round`, met `dt_util.get_default_time_zone()`). Vier hulpjes doen het werk:

- `echte_duur` en `echte_uren`: hoe lang het echt duurt van een lokale tijd tot een andere, via
  UTC. Niet door twee tijden met dezelfde tijdzone af te trekken: dat geeft in Python het verschil
  op de klok.
- `echt_verder`: de tijd op de klok die zoveel echte tijd later (of eerder) komt. Een uur voor
  03:00 op 28-03-2027 is 01:00, niet 02:00.
- `_klokuren`: de uren op de klok tussen twee momenten. Op de dag van de zomertijd loopt het uur
  van 01:00 tot 03:00 (er is geen uur van 02:00), op die van de wintertijd is er één uur van 02:00
  dat twee echte uren duurt, net zoals een prijssensor het dan geeft (`_naast_elkaar`).
- `_klokuur_verder`: het volgende of vorige uur op de klok, voor het plan dat zijn uren op hun
  begin bijhoudt. Na 01:00 komt op 28-03-2027 meteen 03:00.

Zonder zone (None) is alles het verschil op de klok, precies zoals tot dan. Zo rekent elke
bestaande proef, en een coach die nog geen ronde deed. Nagemeten op 19-10-2026: alle 518 proeven
van test_planner.py en alle 206 van test_batterij.py geven ook met de zone van Amsterdam en met
een vaste UTC+2 dezelfde uitkomst; alleen de nachten van de klokwissel zijn anders.

**In echte uren:** de tijd tot de klaar-tijd en de speling van een uur (de klaar-tijdregel, de
pauze van de bewoner, wachten op prijzen), `plan_end` en `_latest_start`, wat er per blok in kan
(`schijven`, `capaciteit_kwh`, `_rustig_spreiden`, de tijdlijn, `_doorladen`, `accu_in_plan`,
`cheapest_hours`), de veiligheidspauze in de paal (`_hold_until`), de minimale looptijd en "zo
weer verder" (`_keep_alive`, `charging_pace`), een programma van begin tot eind en elk startmoment
per kwartier (`programma_kosten`, `_programma_stukken`, `plan_programma`), de boiler
(`boiler_nodig`, `boiler_schijven`, `plan_boiler`), de airco, en in de batterij de som over de
tijd (`_waarde_vooruit`, `_vooruit`), het rustige vermogen (`_rustig_vermogen`), de nacht tot
morgenvroeg (`_nacht_uren`), wat hij de auto geeft (`auto_hulp`) en de wekelijkse volle beurt.

**Op de klok, met opzet:** de klaar-tijd zelf, "niet eerder dan" en "uiterlijk starten"
(`resolve_window`), de avondpiek van 18:00 tot 20:00 (`in_evening_peak`), de avond van 20:00
voor een vaste klaar-tijd (`_evening_before`), morgenvroeg om 07:00 (`_morgenvroeg`), de zon en
het huis per uur van de dag, en alles wat op het scherm staat. Een bewoner leest de klok, en
"klaar om 07:00" is 07:00 op de klok, ook als de nacht een uur korter is.

Wat het op 28-03-2027 scheelt, nagerekend in proef 78 (test_planner.py) met een auto die vier
uur op 11,04 kW moet laden en klaar-tijd 07:00:

- In het prijsblok van 01:00 tot 03:00 past 11,04 kWh, niet 22,08.
- Uiterlijk beginnen is om 01:00, niet om 02:00 (dat bestaat niet en werd in de praktijk 03:00,
  een uur te laat). Het plan is om 06:00 vol, een echt uur voor 07:00.
- Om 01:10 grijpt de klaar-tijdregel in: er is nog 4 uur en 50 minuten, geen 5 uur en 50.
- Moet er een kwartier meer in dan de goedkope uren dragen, dan begint hij om 00:30 al; op de
  klok gerekend wachtte hij, en kwam hij 's ochtends tekort.
- Een veiligheidspauze van 01:30 tot 03:30 duurt 60 minuten, geen 120.
- Een vast contract heeft die nacht geen uur van 02:00.
- Een programma van drie uur dat om 05:00 klaar moet zijn, met een half uur speling, begint
  uiterlijk om 00:30 en niet om 01:30.

En in de batterij (proef 46, test_batterij.py): de nacht van 22:00 tot 07:00 heeft acht uur
huisverbruik in plaats van negen, en van het net laden smeert hij uit over de vier echte
goedkope uren in plaats van vijf op de klok. Bij de wintertijd is het omgekeerd: het blok van
02:00 tot 03:00 telt twee uur, de nacht tien uur huisverbruik, en het plan haalt twee uur uit
dat blok. Tot dan was rekenen op de klok daar voorzichtig, nu is het precies.

In Portugal gaat het net zo, een uur eerder op de klok: daar bestaat 01:00 tot 02:00 niet.

## Wat nog niet, en wanneer het telt

- **Een klaar-tijd in het uur van de wissel zelf** (tussen 02:00 en 03:00 in die twee nachten):
  op 28-03-2027 bestaat die tijd niet en leest Python hem als een uur later op de klok, op
  25-10-2026 hangt het af van welke keer de klok hem aanwijst. Niemand zet een klaar-tijd
  midden in de nacht, maar het staat hier.
- **Kwartierprijzen in het herhaalde uur** (de batterij): `_naast_elkaar` voegt de twee keer
  hetzelfde kwartier samen, en dan duren de eerste drie kwartieren van 02:00 echt 15 minuten en
  het laatste 75. Samen klopt het (twee uur), de verdeling van de prijs over dat uur niet precies.
- **Klein:** timers die op de lokale klok lopen (het bewaren van een sessie om de vijf minuten,
  het verversen van de zon- en huisverwachting) staan na 03:00 een uur stil; de vooruitblik
  toont 24 kolommen op een dag van 25 uur; een tijdsensor in het herhaalde uur staat een uur te
  vroeg in Home Assistant; een vraag van het paneel vóór de eerste ronde na een herstart rekent
  nog op de klok, want de zone komt pas met die ronde.
- **Een paneel in een andere tijdzone dan het huis** ziet het herhaalde uur nog als één uur.
