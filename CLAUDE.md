# DomotiApp Coach

Een custom integration voor Home Assistant die apparaten in huis op het
gunstigste moment laat draaien: nu de laadpaal, straks de vaatwasser. Hij wordt
via HACS verspreid, dus alleen `custom_components/` gaat mee naar de klant.

Eigenaar en opdrachtgever is Sven. Hij beoordeelt en beslist; ik bouw, test,
commit, tag en breng uit.

## Werkafspraken

- **Nederlands** in het gesprek, in commit messages en in releasenotes.
  Codecommentaar in het Engels of Nederlands, zoals het bestand het al doet.
- **Geen gedachtestreepjes** in teksten die de klant leest.
- **Ik doe git zelf**: feature-branch, één commit, `--no-ff` merge naar `main`,
  tag, push, en een GitHub release. HACS kijkt naar releases en niet naar tags,
  dus zonder release krijgt niemand de update.
- **Testen vóór opleveren.** Sven installeert meteen bij zichzelf; alles wat ik
  zelf had kunnen zien kost hem een ronde. Meld eerlijk wat niet getest is.
- **Nooit verzonnen getallen.** Elk getal in de code of op het scherm komt uit
  een meting, uit een instelling van de klant of uit een som die daarop rust.
  Weet de coach iets niet, dan zegt hij dat in plaats van iets aan te nemen.
- **Lees zijn klacht letterlijk.** Hij beschrijft wat hij zag, niet wat er
  technisch misging. Vraag je af wat hij verwáchtte te zien.
- Niets bouwen zonder zijn seintje. Wat er op de lijst staat betekent niet dat
  het aan mag.

## Hoe het in elkaar zit

| bestand | wat het doet |
|---|---|
| `planner.py` | alle denkwerk, kent Home Assistant niet, is los te draaien |
| `coach.py` | leest sensoren, stuurt de paal aan, houdt de laadbeurt bij |
| `websocket.py` | wat het paneel mag opvragen en wijzigen |
| `storage.py` | de instellingen op schijf |
| `monitor.py` | de zekeringbewaking en de wachthond |
| `report.py` | het pdf-rapport |
| `frontend/src/` | het paneel, ES-modules zonder buildstap |

De scheiding tussen `planner.py` en `coach.py` is de kern: het denkwerk is los
te draaien tegen een hele dag echte historie voordat er ook maar iets geschakeld
wordt. Zet daar niets in dat `hass` nodig heeft.

## Proeven draaien

```
python tests/test_planner.py     # 82 controles op het denkwerk
python tests/test_coach.py       # 62 op de bedrading, met een nagebouwde HA
```

Home Assistant hoeft er niet voor te draaien; de handvol namen die `coach.py`
eruit gebruikt worden nagemaakt. **Draai ze allebei voor elke uitgave.**

Bij een rode proef: verdenk eerst de proef en dan pas de code. Van de zeventien
"fouten" die de scenario's ooit opleverden waren er vijftien van het harnas.

Een proefopzet die begint met een paal die al laadt is geen gewone laadbeurt maar
een herstart middenin, en daar gedraagt de coach zich bewust anders. Doe eerst
één ronde met de kabel erin en nog geen stroom.

## Het paneel bekijken

```
python tools/serve.py            # http://127.0.0.1:8899/preview.html
```

`preview.html` staat in `.gitignore`: het is een lokaal harnas dat de serverkant
nabootst. Handige parameters: `?empty=1`, `?klant=1`, `?phone=390&h=700`,
`?coach=fase`, `?stuurfout=1`.

Serveer altijd met `Cache-Control: no-store` (dat doet `serve.py`), want Chrome
houdt ES-modules anders vast en dan meet je een oude versie. Ververs met een
unieke querystring (`?v=2`) als het in een iframe draait.

Meet smalle schermen op **320 én 280 px**, niet alleen 390: zodra iOS inzoomt op
een invoerveld wordt de viewport smaller en komt echte overflow er alsnog uit.

Geen backticks in CSS-commentaar; de stijlen staan in een template literal en een
backtick sluit de string af. Controleren met
`node --check custom_components/domotiapp_coach/frontend/src/views/overview.js`.

## Meekijken in een echte installatie

`tools/ha.py` leest alleen. Hij zoekt een tokenbestand in `~/dev/tokens/` of
`C:\dev\tokens\`, met een bestand per installatie:

```
tokens/thuis.txt
tokens/klant-naam.txt
```

Adres op de ene regel, het long-lived token op de andere. **Die bestanden horen
op geen enkele remote, ook niet op een privérepo.** Maak op een nieuwe machine
gewoon een nieuw token aan in Home Assistant (Profiel → Beveiliging).

```
python tools/ha.py                                   # werkt de verbinding?
HA_INSTALLATIE=klant-naam python tools/ha.py         # een andere installatie
python tools/logboek.py 2026-08-29T06:00             # tijdlijn uit de recorder
python tools/besluiten.py                            # live meeluisteren
```

`logboek.py` vraagt aan het paneel zelf welke entiteiten erbij horen, dus hij
werkt bij een klant net zo goed als thuis. Geef de history-API altijd een
`end_time` mee, anders krijg je maar één dag vanaf de starttijd terug.

De besluiten van de coach staan **niet** in de recorder; die gaan over de
eventbus. Wil je die van een laadbeurt hebben, laat dan `tools/besluiten.py`
meelopen terwijl het gebeurt.

## Waar we staan

De lopende stand, de openstaande vragen en wat er in het echt nog beproefd moet
worden staan in de privérepo ernaast: `../notities/domotiapp-coach/`. Die staat
er niet in deze publieke repo omdat er IP-adressen, klantgegevens en
meterstanden in staan. **Lees dat bestand aan het begin van een sessie.**

Staat die map er niet, dan werk je op een machine waar alleen deze repo is
uitgecheckt. Zeg dat dan, en vraag om `Sven2410/dev` erbij.
