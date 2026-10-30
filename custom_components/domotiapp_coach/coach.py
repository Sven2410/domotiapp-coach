"""The part of the coach that actually watches and acts.

This runs in Home Assistant, on a timer, whether or not anybody has the panel
open. That is the whole reason it is here rather than in the browser: a car has
to start charging at two in the morning, and at two in the morning nobody is
looking at a dashboard. A restart must not matter either, so nothing is kept
that cannot be read back from the installation itself.

The thinking is next door in planner.py, which knows nothing about Home
Assistant and can therefore be run against a whole day of real history before
anything is switched. This file only reads sensors, calls services and keeps
the two apart.
"""

from __future__ import annotations

import asyncio
import re
import logging
from dataclasses import asdict, replace
from datetime import date, datetime, time, timedelta, timezone
from functools import partial
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceNotFound
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    BIJLADEN_MIN_WINST,
    GAS_VERGELIJK_DAGEN,
    BATTERIJ_ALLEEN_LEZEN,
    BATTERIJ_SCHEMA,
    NETTING_ENDS,
    HOLIDAY_MAX_DEFAULT,
    CHARGER_CONTROL,
    DOMAIN,
    EVENT_DECISION,
    EVENT_BERICHTEN,
    EVENT_NOTIFICATION,
    EVENT_SETTINGS_UPDATED,
    LEVEL_ADVISE,
    LEVEL_PROPOSE,
    LEVEL_READ,
    LEVEL_STEER,
    PHASE_START_AMPS,
    PROGRAMMA_TYPES,
    STEKKER_APPARATEN,
    TEMPO_ONDERGRENS,
)
from .archive import async_get_archive
from .batterij import (
    HANDELEN,
    HANDELEN_KAN_NIET,
    Besluit,
    MAX_LADEN,
    NETLADEN,
    NUL,
    ONTLADEN,
    STAND_NAMEN,
    STANDBY,
    ZONNELADEN,
    VOL_MARGE,
    Batterij,
    GROWATT_HOUDEN_KWH,
    GROWATT_MIN_PCT,
    GROWATT_STUK_PCT,
    GROWATT_VOORAF,
    GrowattSchema,
    Regelaar,
    Rendement,
    Rendementmeter,
    Uur,
    Voorraad,
    auto_grens,
    balans_kwh,
    growatt_besluit,
    growatt_bijstelling,
    growatt_duur,
    growatt_laatste_nacht,
    growatt_nachten,
    GROWATT_DAG,
    GROWATT_NACHTEN_V,
    growatt_inhoud,
    growatt_max_w,
    growatt_nacht,
    growatt_narekening,
    growatt_schema,
    growatt_vol,
    handelen_kan_niet,
    herreken,
    met_paal,
    plan_batterij,
    rendement_uit_stappen,
    rendement_uit_tellers,
    verdiend,
    vol_voor,
    zon_in_accu,
)
from . import berichten, prijsopbouw, taal, tarifas
from .taal import getal, t, tn
from .planner import (
    _dag_om,
    DAGNAMEN,
    MODI_ZONDER_SOM,
    accu_in_plan,
    rendement_van,
    plan_rang,
    plan_regels,
    zon_grens,
    zon_rang,
    zon_regels,
    Apparaat,
    BALANCER_MARGIN_AMPS,
    AIRCO_AAN_OP,
    AIRCO_STAP_C,
    Airco,
    AircoBesluit,
    airco_nodig,
    plan_airco,
    Boiler,
    BOILER_KIJKEN,
    BOILER_VERDACHT,
    BOILER_VERGEEFS,
    DRAAIT,
    KLAAR,
    boiler_nodig,
    plan_boiler,
    plan_programma,
    price_now,
    programma_van,
    tabel_van,
    met_metingen,
    Programma,
    PROGRAMMAS,
    VRIJGAVE_WOORD,
    PROFIEL_STAP_MIN,
    profiel_van,
    profiel_gemiddeld,
    CHARGE_EFFICIENCY,
    FUSE_MARGIN_AMPS,
    FUSE_MARGIN_SHARE,
    Car,
    Charger,
    Circuit,
    apparaat_fase,
    groep_apparaten_amps,
    groepen_keten,
    DayWindow,
    Decision,
    Forecast,
    Grid,
    Sun,
    Tariff,
    Window,
    STEP_AMPS,
    amps_for,
    ceiling_amps,
    zekering_plafond,
    decide,
    timeline,
    FULL_PERCENT,
    FASE_RUST,
    FASE_WACHT,
    kies_fasen,
    op_zon,
    RAMP_MINUTES,
    _dagnaam,
    _euro,
    beschikbaar_van_bewaker,
    doel_van,
    doel_bereikt,
    energy_needed_kwh,
    held_back,
    MIN_AMPS,
    resolve_window,
    should_send,
    VOLTS,
    watts_for,
    zet_zone,
)
from .ontvangers import ontvangers
from .storage import (
    async_get_berichten, async_get_beurten, async_get_geheugen, async_get_meldingen, async_get_store,
    async_get_zon,
)
from .zon import ZON_DAGEN, zon_uit_opwek
from .units import hour_to_watts, to_kwh, to_watts

_LOGGER = logging.getLogger(__name__)


def nt(nl: str) -> str:
    """Een zin in een tabel die er al staat voor de taal bekend is (v0.140.0).

    Blijft Nederlands, en wordt vertaald waar hij in een zin komt: `t(tekst)`.
    Het merkteken is er voor `tools/vertaalcheck.py`, dat zo ook deze zinnen
    vindt, net als `nt` in het paneel (i18n.js).
    """
    return nl


def _rond(waarde: float, decimalen: int) -> str:
    """`str(round(...))` met het scheidingsteken van de taal: 0,5 of 0.5.

    Niet `getal`: die schrijft altijd alle decimalen ("0,50"), en de meldingen
    die hiermee gemaakt worden lieten ze altijd weg.
    """
    tekst = str(round(waarde, decimalen))
    return tekst if taal.taal() == "en" else tekst.replace(".", ",")


# Hoe lang een sensor niets mag zeggen voordat de bewoner het hoort. Bij het
# opstarten van Home Assistant is van alles een paar minuten `unavailable`, en
# een Ford-app of een Easee-cloud hapert wel eens een paar minuten; daar hoeft
# niemand voor gewekt te worden. Tien minuten is wel een storing. De eigenaar op
# 04-09-2026: "wat als een sensor ineens niet meer beschikbaar is. Dat moet wel
# gemeld worden."
SENSOR_STIL = timedelta(minutes=10)
# De accustand van een auto mag langer zwijgen voordat dat een melding is: een
# auto-integratie haalt zijn stand eens per zoveel tijd op, en een auto die
# stilstaat verandert niet. De eigenaar op 22-09-2026 over de Ford: "zet dat maar
# op een uur polling."
SENSOR_STIL_AUTO = timedelta(minutes=60)
# Sensoren die kort na elkaar stilvallen horen bij één melding (v0.175.0). In de klantwoning viel op
# 28-10-2026 het internet weg, en na tien minuten kwamen er in één ronde vier kritieke meldingen, voor
# een koelkast, een vriezer, een droger en een wasmachine. Zwijgt er een sensor, dan neemt de melding
# elke sensor mee die al zo lang korter zwijgt.
SENSOR_BUNDEL = timedelta(minutes=5)
# Een groep zonder meter, gemeten via de apparaten die erop hangen (v0.165.0): vanaf welk deel van
# de zekering, en hoe lang, voordat de coach het meldt. Een wasmachine die opwarmt duurt minuten,
# een motor die aanloopt een seconde. Opnieuw pas als hij onder `GROEP_VOL_WEER` is geweest.
GROEP_VOL_DEEL = 0.9
GROEP_VOL_WEER = 0.8
GROEP_VOL_DUUR = timedelta(minutes=3)
# De temperatuurmelding van een thuisbatterij (v0.108.0). Zo lang blijft hij
# boven de grens voor er bericht uitgaat, zodat één verkeerde meting van de
# integratie niemand wekt; en zoveel graden moet hij weer onder de grens zakken
# voor een volgende keer erboven een nieuwe melding is. Een temperatuur die op
# de grens heen en weer gaat geeft zo één bericht, niet elke paar minuten een.
TEMP_AANHOUDEND = timedelta(minutes=2)
# Hoe vaak de coach kijkt of er een herinnering aan de beurt is (v0.130.0), en
# hoe vaak hij de prijsopbouw naast de all-in sensor legt voor een bericht als
# die omslaat. Een herinnering gaat per dag; tien minuten is ruim op tijd.
BERICHTEN_RONDE = timedelta(minutes=10)
CONTROLE_RONDE = timedelta(hours=1)
TEMP_TERUG = 1.0
# De vriezer (v0.125.0): de coach stuurt hem niet, hij meldt. De keuzes van de
# eigenaar op 15-10-2026: een melding als de deur 3 minuten openstaat, en als hij
# een half uur warmer is dan -15 °C. Weer koud is hij TEMP_TERUG onder de grens.
VRIEZER_DEUR = timedelta(minutes=3)
VRIEZER_GRENS_C = -15.0
VRIEZER_WARM = timedelta(minutes=30)
# Hoe lang na een temperatuur die niets zei een 0,0 als plaatshouder telt (v0.141.1).
KOEL_NUL = timedelta(minutes=2)
# De koelkast (v0.131.0): dezelfde drie meldingen, met dezelfde 3 minuten voor de
# deur en hetzelfde half uur, maar een eigen grens. De eigenaar op 19-10-2026:
# "boven de 10 graden". Met die van de vriezer zou een koelkast op 5 °C elke keer
# melden.
KOELKAST_GRENS_C = 10.0
# Per soort: hoe hij in een melding heet zonder eigen naam, en de grens.
KOELWAREN: dict[str, tuple[str, float]] = {
    "vriezer": ("de vriezer", VRIEZER_GRENS_C),
    "koelkast": ("de koelkast", KOELKAST_GRENS_C),
}
# Een smart plug die altijd aan moet staan (v0.120.0): zo lang mag hij uit zijn
# voor er een melding komt. De eigenaar op 15-10-2026: "Lukt dat niet wil ik na
# 2 min een melding ontvangen."
ALTIJD_AAN_WACHT = timedelta(minutes=2)
# Stekkers die samen wegvallen worden één melding (v0.178.0). Valt er een over
# `ALTIJD_AAN_WACHT`, dan gaan de stekkers die al een minuut weg zijn mee: de coach
# zet een stekker binnen een seconde aan, dus na een minuut weet hij dat het niet lukte.
ALTIJD_AAN_BUNDEL = timedelta(minutes=1)
# Sinds v0.183.0 telt een stekker die niet bereikbaar is vanaf het moment waarop zijn
# schakelaar wegviel (`last_changed`), niet vanaf het moment waarop de coach het zag. In een
# klantwoning op 30-10-2026 vielen twee stekkers in dezelfde seconde weg; de coach zag de
# tweede pas bij de volgende minuutronde, en ze kwamen in twee meldingen. Wat terugkomt wordt
# ook één regel: wat binnen `ALTIJD_AAN_BUNDEL` terugkwam, of alles zodra niets meer weg is.
# Welke apparaten "altijd aan" kunnen hebben. Een vaatwasser sinds v0.122.0: de
# eigenaar op 15-10-2026, "sommige vaatwassers hangen namelijk ook aan een smart
# plug om alles te meten." Een vriezer, koelkast, wasmachine en droger sinds
# v0.177.0: de eigenaar op 29-10-2026, "De miele apparaten zitten op een smart plug
# die altijd aan moet staan." De schakelaar van de stekker staat bij allemaal in
# `entities.switch`; alleen `_async_altijd_aan` raakt hem aan, en alleen om aan te zetten.
ALTIJD_AAN_TYPES = ("smartplug", "vaatwasser", "vriezer", "koelkast", "wasmachine", "droger")
# De ingebouwde Nord Pool van Home Assistant hangt geen prijslijst aan zijn
# sensoren; die geeft hij alleen via zijn dienst (v0.101.3). Zo vaak vraagt de
# coach een dag die nog niet binnen is opnieuw, en vanaf dit uur morgen erbij:
# de beurs maakt de prijzen van morgen rond 13:00 bekend.
NORDPOOL_DOMEIN = "nordpool"
NORDPOOL_OPNIEUW = timedelta(minutes=10)
NORDPOOL_MORGEN_VANAF = 12

# Hoe vaak de coach een slapende auto hooguit wekt om zijn accustand te horen,
# als de bewoner daarvoor gekozen heeft (`wake_mode` "hourly"). De eigenaar op
# 22-09-2026: "auto moet elke 60 minuten de accu status doorgeven wanneer deze
# stil staat."
WEK_INTERVAL = timedelta(minutes=60)

# Onder welke zonshoogte een omvormer die niets zegt geen storing is. Een
# SolarEdge gaat 's nachts slapen en is dan niet bereikbaar: in de klantwoning
# elke avond, op 18-09-2026 om 21:40, en om 21:51 kwam er een kritieke melding.
# 's Ochtends leverde hij op 17 en 18-09-2026 pas 64 en 55 minuten na
# zonsopkomst iets (46 W om 08:17, 152 W om 08:09); de zon staat dan rond de
# zeven graden. Tien graden laat hem wakker worden voordat er iets gemeld wordt.
# Alleen voor de melding: de coach rekent zonder zonnesensor toch al met nul.
ZON_SLAAPT_ONDER = 10.0

# Over hoeveel van de afgelopen tijd het gemiddelde plafond gaat dat in de
# klaar-tijdsom meetelt, en hoeveel daarvan er minstens gemeten moet zijn.
# Drie uur is lang genoeg om een warmtepomp die om het kwartier aangaat een
# paar keer te zien, en kort genoeg om het koken van zes uur kwijt te zijn
# tegen de tijd dat de nacht gepland wordt: het hele venster sinds het
# inpluggen nemen zette in het virtuele huis een rustig huis een uur eerder
# aan, alleen om de kookpiek van de avond ervoor. Minder dan een half uur is
# een momentopname; een warmtepomp die net aanstaat zou de hele nacht als vol
# tellen.
PLAFOND_VENSTER = timedelta(hours=3)
PLAFOND_MEETTIJD_MIN = 30.0

# Wat de coach van een lopende laadbeurt over een herstart meeneemt (v0.98.0):
# het begin, de meterstand en de accustand bij het begin, sinds wanneer de paal
# laadt, het gemeten plafond, en wat er al gemeld is. Het staat bij de beurt in
# de opslag, die elke vijf minuten bijgewerkt wordt. Ouder dan dit, dan is het
# niet meer met zekerheid dezelfde beurt en begint hij opnieuw, zoals vroeger.
# De eigenaar op 25-09-2026: "na een herstart dat hij alles nog weet? repareer
# alles als dat nodig is."
HERVAT_MAX = timedelta(minutes=30)

# Hetzelfde idee voor de zon: over hoeveel van de afgelopen tijd de coach
# vergelijkt wat de zonverwachting beloofde met wat zijn eigen dak gaf, en
# hoeveel daarvan er minstens gemeten moet zijn.
#
# Twee uur en niet drie: dit is een verhouding en geen gemiddelde, dus hij
# blijft over de dag heen bruikbaar, maar het weer verandert en een ochtend
# hoort de middag niet te blijven drukken. Een half uur meting eronder, anders
# zou één wolk de rest van de dag stempelen. En er moet genoeg beloofd zijn om
# een verhouding van te maken: bij 0,05 kWh verwacht overschot zegt "de helft
# ervan" niets. Zie `_zon_gemeten` en `overschot_kwh` in planner.py.
ZON_VENSTER = timedelta(hours=2)
ZON_MEETTIJD_MIN = 30.0
ZON_MIN_VOORSPELD = 0.5

# How often to think. A minute is often enough to catch a kettle before a fuse
# minds, and rare enough that a car is never re-commanded into giving up.
INTERVAL = timedelta(seconds=60)

# Hoe vaak de regelaar van een thuisbatterij ook zonder nieuwe meterwaarde
# kijkt. Hij wordt wakker van de meter zelf; dit is er voor de meter die
# zwijgt, want die meldt dat niet. Gelijk aan het tempo waarop Home Assistant
# in de eerste woning de meter kreeg (21-09-2026: om de vijf seconden).
REGEL_TIK = timedelta(seconds=5)
# Na zoveel ronden met een andere bedrijfsmodus dan de coach zette laat hij de
# batterij los (iets anders stuurt), en na zoveel tijd probeert hij het weer.
VREEMD_RONDEN = 2
VREEMD_PAUZE = timedelta(hours=1)
# "De batterij doet zelf nul op de meter" (v0.97.0). De eigenaar op 24-09-2026:
# "anker mag zelf nul op de meter doen", en erbij: "ook goed voor een vast
# contract, want dan heb je niks aan het strategisch inkopen." Een batterij met
# een eigen meter in de meterkast volgt het huis in een paar seconden; via
# Home Assistant is dat vijf tot dertien (zie `VOLG_WACHT` in batterij.py). Is
# het plan gewoon nul op de meter, dan zet de coach hem in zijn eigen stand en
# kijkt hij mee. Voor alles wat de batterij zelf niet weet neemt hij het meteen
# over: laden van het net, handelen, een laadpaal die laadt, de vakantiestand,
# de reserve voor noodstroom, en een zekering waar minder dan
# `ZELF_ZEKERING_W` ruimte op over is. Teruggeven doet hij pas als dat
# `ZELF_WACHT` zo gebleven is, zodat een plan dat op de rand staat niet elke
# minuut de modus omzet. Twee minuten sinds v0.102.1: de eigenaar op 30-09-2026,
# na een laadbeurt waarin de batterij vijf minuten na een volle auto pas weer
# zelf regelde: "zet die 5 min terug naar 2 min."
ZELF_WACHT = timedelta(minutes=2)
# Een batterij die de coach niet volgt (v0.167.0). In een klantwoning laadde de batterij op
# 27-10-2026 van 16:00:54 tot 16:17 2,5 kW van het net, eerst terwijl de coach wilde terugleveren
# en daarna in haar eigen stand op nul op de meter; elke eerdere keer volgde ze binnen 5 tot 15 s.
# Gemeten met het vermogen van de batterij en de meter, niet met de opdracht. Na `VOLGT_NIET_NA`
# probeert de coach het één keer opnieuw (in de eigen stand: overnemen op 0 W, en zolang
# `VOLGT_NIET_EXTERN` niet teruggeven), na `VOLGT_NIET_MELDEN` één melding.
VOLGT_NIET_W = 500.0
VOLGT_NIET_NA = timedelta(minutes=3)
VOLGT_NIET_MELDEN = timedelta(minutes=10)
VOLGT_NIET_EXTERN = timedelta(minutes=30)
ZELF_ZEKERING_W = 500.0
ZELF_MARGE = 1.0
# Stopt de laadpaal, dan telt hij voor de batterij nog als ladend tot de meter
# een waarde gaf van minstens zoveel later. Bij de eigenaar op 30-09-2026 stopte
# de auto om 13:39:54; de laatste meterwaarde was van 13:39:53 en zei nog
# 7,3 kW afname, midden in het afbouwen. De regelaar rekende daarmee en zette
# de batterij in dezelfde seconde op ontladen op vol vermogen, terwijl er 1 kW
# zon over was: een paar seconden 4,2 kW het net op, en daarna ruim een
# minuut niets, omdat hij dat zelf voor een korte last aanzag. De waarde van
# 13:39:55 klopte al; vijf seconden is de tijd die een batterij zelf nodig
# heeft (`VOLGT_NA` in batterij.py). Een meter die zwijgt houdt dit niet
# eeuwig vast: na `PAAL_UIT_LANGST` geldt het besluit weer zoals het is.
PAAL_UIT_WACHT = timedelta(seconds=5)
PAAL_UIT_LANGST = timedelta(seconds=30)
# Hoe lang de coach na het omzetten naar de externe stand wacht tot de stuurknop
# van de batterij er weer is, in stappen van een halve seconde. De Anker van de
# eigenaar (28-09-2026) maakte hem een seconde na het omzetten onbereikbaar; de
# weg terug duurt naar verwachting even lang. Zie `_async_overnemen_op_nul`.
KNOP_WACHT_STAP = 0.5
KNOP_WACHT_STAPPEN = 20
# Hoe lang `_async_bij_stop` hooguit wacht op een ronde of een stap van de
# regelaar die nog loopt, in dezelfde stappen. Een ronde duurt een seconde of
# twee; het overnemen van een batterij met een trage knop tot tien.
STOP_WACHT_STAPPEN = 30
# Hoe vaak wat de batterij verdiende naar de opslag gaat, en hoeveel dagen
# daarvan bewaard blijven: ruim een jaar, zodat In geld in Historie ook over een
# heel jaar weet wat de batterij opleverde.
BATTERIJ_BEWAREN = timedelta(minutes=5)
# Een Growatt met een laadschema (v0.150.0). De acties horen bij de integratie
# `growatt_server`. Een tweede opdracht vlak na de eerste faalt (de klantwoning,
# 22-10-2026): Growatt neemt per onderdeel van zijn API één vraag per vijf minuten aan
# (fout 10012 in growattServer), daarom de pauze. Teruglezen leest wat Home Assistant
# onthield, en dat zet hij na een schrijfopdracht zelf op wat er geschreven werd; wat de
# omvormer echt heeft staat er pas na de volgende ronde, en die komt elke vijf minuten
# (`SCAN_INTERVAL` van growatt_server). Daarom zes minuten (v0.152.0; tot dan 2 en 1,5).
# Een integratie die niet opkomt (v0.166.0). In een klantwoning startte Home Assistant op 27-10-2026
# na een stroomstoring eerder dan het internet, en ging de integratie van de batterij naar
# `setup_error`; daaruit probeert Home Assistant het niet zelf opnieuw. De coach kijkt elk kwartier
# de integraties achter zijn eigen entiteiten na, herlaadt alleen wat er niet staat, en meldt het na
# een uur. De eigenaar: "is die wel online dan niet herladen".
INTEGRATIE_CONTROLE = timedelta(minutes=15)
INTEGRATIE_MELDEN = timedelta(hours=1)
INTEGRATIE_WACHT = timedelta(seconds=60)
INTEGRATIE_HERLADEN = ("setup_error", "not_loaded")
_ENTITEIT_ID = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")
GROWATT_DOMEIN = "growatt_server"
GROWATT_PAUZE = timedelta(minutes=5)
GROWATT_TERUG = timedelta(minutes=6)
# Hoe vaak de coach een bevestigd schema opnieuw terugleest (v0.163.1). Het eerste teruglezen
# kan nog de buffer van Home Assistant zijn, van vóór de eigen ronde van de Growatt: in een
# klantwoning op 26-10-2026 bevestigde hij na een herstart 8%, terwijl er 100 stond.
GROWATT_CONTROLE = timedelta(minutes=30)
GROWATT_WACHT = timedelta(seconds=45)
GROWATT_OPNIEUW = timedelta(hours=1)
# Na een herstart is de Growatt-integratie soms later klaar dan de coach (v0.162.0). Zolang
# de accustand er niet is vraagt hij elke ronde opnieuw; lukte het lezen niet, dan na
# `GROWATT_NOG_NIET`, en na `GROWATT_WACHT_MELDEN` wachten een waarschuwing in het log.
GROWATT_NOG_NIET = timedelta(minutes=5)
GROWATT_WACHT_MELDEN = timedelta(minutes=10)
GROWATT_FOUTEN = 3
GROWATT_BESTENDIG = timedelta(minutes=5)
# Hoeveel metingen van de inhoud en van het laadvermogen hij bewaart, en hoeveel nachten.
GROWATT_BEWAAR = 30
GROWATT_NACHTEN_BEWAAR = 14
# Hoe vaak de telling van de dag naar de opslag gaat, en hoe lang de coach op een dag
# niet mag tellen voor die dag niet meer meetelt (v0.171.0, `_async_growatt_nacht`).
GROWATT_DAG_BEWAREN = timedelta(minutes=15)
GROWATT_DAG_GAT = timedelta(hours=1)
# Hoe ver hij een dag die hij niet helemaal zag terugrekent (v0.174.0): de recorder bewaart
# elke toestand tien dagen, en daar staat de accustand in.
GROWATT_NAREKENEN_MAX = timedelta(days=9)
# Onder hoeveel watt zon het laadvermogen een meting van het net is.
GROWATT_ZON_W = 50.0
# De vloer: onder hoeveel watt de batterij stil staat, en boven hoeveel watt het huis
# dan van het net haalt.
GROWATT_STIL_W = 30.0
GROWATT_VLOER_NET_W = 150.0
# Hoeveel dagen hij in de statistiek terugkijkt naar wat een Growatt eruit gaf, zolang hij
# dat zelf nog niet zag (v0.161.0); zie `_async_hoogste_ontladen`.
GROWATT_TERUGKIJK_DAGEN = 30
BATTERIJ_DAGEN_MAX = 400

# How long to wait for the charger to confirm a new limit before starting.
CONFIRM_SECONDS = 15

# How often to prod a charging point that is not doing what was asked. Some of
# the reasons it might not are outside the coach's reach altogether: a load
# balancer holding the session, a car that has decided it is full, a brand with
# its own idea of when a schedule applies. Repeating the command every minute
# changes none of them and only fills a log, but never repeating it at all means
# a car stands still all night because the decision happened not to change.
NUDGE_INTERVAL = timedelta(minutes=5)

# Hoe lang de fasemeting van het huis na mag ijlen op een paal die net gestopt
# is. In de klantwoning stond op 29-08-2026 om 11:27:06 `regel=no-room` op de
# kaart met de kabel er al uit: de paal meldde nul, het huis nog twaalf ampère.
# Een minuut is ruim genoeg voor een P1 of een seriële meter en kort genoeg om
# een huis dat werkelijk bijschakelt niet te missen.
METER_NAIJL = timedelta(minutes=1)

# Hoe lang een paal moet volhouden dat er geen kabel in zit voor de coach hem
# gelooft.
#
# Een Easee die zijn laadbeurt opnieuw opstart doorloopt de hele keten:
# `disconnected`, `awaiting_authorization`, `pending_authorization`,
# `waiting_in_queue`, `charging`. Dat duurt in de klantwoning ongeveer twee
# seconden en gebeurde in de nacht van 30-08-2026 drie keer, twee daarvan
# binnen tien seconden nadat de coach zelf zijn grens omlaag schreef. Elke keer
# las de coach dat als de kabel eruit: verslag versturen, en het akkoord,
# snelladen, de accustand en de klaar-tijd weggooien. Eén laadbeurt werd zo in
# vieren geknipt, en de vier verslagen telden samen 19,8 kWh terwijl er 13,65
# in ging.
#
# Dit staat naast de reparatie van v0.43.1, die over een sensor ging die even
# niets zei. Dit is een sensor die wél iets zei, alleen niet lang genoeg om het
# te geloven.
#
# Een halve minuut, en dat is een keuze en geen meting: lang genoeg voor elke
# herstart die ik gezien heb, en kort genoeg dat een echte kabel eruit nog
# steeds binnen een ronde opgemerkt wordt. Het verslag noemt het moment waarop
# de paal het voor het eerst zei, niet het moment waarop de coach het geloofde.
KABEL_ONTDREUN = timedelta(seconds=30)
# Het laadrendement meten (v0.94.0): over minstens zoveel procentpunt en kWh,
# want een accusensor meldt in stappen (een Ford per tien procent) en over een
# korte strook is de fout groter dan het verlies zelf. En alleen wat tussen
# deze grenzen valt: daarbuiten klopt de meting niet, niet het rendement.
REND_MIN_PROCENT = 10.0
REND_MIN_KWH = 3.0
REND_LAAGST = 0.70
REND_HOOGST = 1.0
REND_MAX_N = 5
# Hoeveel een batterij moet zakken voordat de fasemetingen van daarvoor niet
# meer voor de mediaan tellen (v0.88.2). Een halve kilowatt is ruim twee
# ampère op één fase; kleiner bijregelen doet de regelaar de hele dag.
BATTERIJ_DALING_W = 500.0

# Hoe lang de laatste bruikbare meting van een sensor blijft gelden als die
# sensor even niets zegt.
#
# Dit is dezelfde fout als bij de status van de laadpaal, maar dan in de
# meetkant, en die tak was niet nagekeken. In de klantwoning viel de P1-meter op
# 30-08-2026 om 11:07, 11:09 en 11:15 telkens een paar seconden weg. Zodra
# `grid_import` en `grid_export` allebei `unavailable` zijn, rekent `_read`
# `netto = 0` uit en concludeert de coach dat er geen zon over is. Op de zonregel
# betekent dat stoppen, en zo stond het laden die ochtend twee keer een kwartier
# stil zonder dat er iets aan de hand was.
#
# Het geldt voor élke sensor waarvan een ontbrekende waarde als nul zou lezen:
# de netmeting, de fasestromen en het vermogen van de paal zelf. Dat laatste is
# het gemeenste, want dat gaat in de som die het kringetje openhoudt: valt hij
# weg, dan ziet de coach zijn eigen laden aan voor huisverbruik en praat hij
# zichzelf uit.
#
# Vijf minuten, en dat is een keuze. Lang genoeg voor elke herverbinding die ik
# gezien heb, en kort genoeg dat een integratie die werkelijk stuk is niet een
# half uur met oude getallen doorrekent. Daarna weet de coach het niet meer, en
# dan zegt hij dat ook.
MEETNAIJL = timedelta(minutes=5)

# Over hoeveel tijd de fasestromen worden gladgestreken voor er een besluit op
# valt. De huismeter van de klantwoning meldt elke dertig seconden en gooit er af
# en toe één sample uit dat nergens bij hoort; zie `nood_ruimte` in planner.py.
# Een mediaan over anderhalve minuut haalt zo'n enkele uitschieter eruit en
# laat een huis dat werkelijk bijschakelt er binnen twee metingen door.
#
# De metingen komen niet uit de ronde maar uit de luisteraar op de fasesensoren,
# want een ronde per minuut levert nooit genoeg punten voor een mediaan.
FASE_VENSTER = timedelta(seconds=90)

# Vanaf welke stroom de fasemeting van een laadpunt iets betekent, en hoe vers
# de twee sensoren van elkaar moeten zijn. Zie `_measured_phases`.
FASEMETING_AMPS = 5.0
# Hoe lang de coach na een eigen herstart van de paal wacht voor hij "vol"
# gelooft, en hoe lang de auto daarna weer geladen moet hebben voor er een
# volgende herstart mag. De Ford in de klantwoning deed er op 06-09-2026 negen
# minuten over om na een start weer stroom te nemen (05:18 gestuurd, 05:27
# aan het laden). Een kwartier, dezelfde maat als `MIN_HOLD_MINUTES`.
HERSTART_WACHT = timedelta(minutes=15)

# Proefladen bij het inpluggen (v0.153.0). De eigenaar op 23-10-2026, nadat de
# Ford in de klantwoning om 19:30 bij het inpluggen in storing ging en de coach
# tot 00:45 zou wachten: "alles moet zo fail safe mogelijk", en per auto in te
# stellen (`proefladen` in het autoprofiel, standaard aan). Hoe lang één poging
# duurt: zolang er niets loopt kost wachten niets, en de Ford deed er na een
# start eens negen minuten over (06-09-2026). Na `PROEF_POGINGEN` mislukte
# pogingen, elk na een ronde op 0 A, meldt de coach het en houdt hij op.
PROEF_DUUR = timedelta(minutes=10)
PROEF_POGINGEN = 3
PROEF_PAUZE = timedelta(minutes=1)

# Wat de laadstatus van een auto zegt als hij in storing staat (`status_entity`
# in het autoprofiel, v0.153.0). De Ford-integratie zegt FAULT; andere merken
# zeggen error of iets met fault erin. Kleine letters, en een deel van het woord
# telt ook ("charging_fault").
AUTO_STORING = ("fault", "error", "storing")

# Apparaten met een programma die de coach start: `PROGRAMMA_TYPES` in
# const.py. De eigenaar op 06-09-2026: eerst alleen de vaatwasser.
# Hoe lang de coach na een druk op de startknop wacht op "run" voordat hij
# zegt dat het niet lukte, hoe vaak hij het probeert, en hoe lang daartussen.
# Home Connect doet er soms een minuut over om de nieuwe toestand te melden.
START_WACHT = timedelta(minutes=3)
START_POGINGEN = 2
START_OPNIEUW = timedelta(minutes=5)

# Een apparaat zonder startknop, op een meetstekker (merk "overig"). De coach
# ziet aan het vermogen of hij draait: boven DRAAI_W is draaien, en klaar is
# hij als het STIL_KLAAR lang onder die grens bleef. Een half uur, want
# tussen twee spoelgangen staat een vaatwasser gerust een paar minuten stil,
# en het drogen aan het eind trekt bij sommige machines bijna niets: die van
# De eigenaar zette op 07-09-2026 een kwartier voor het eind de deur open voor de
# stoom en deed daarna twintig minuten vrijwel niets, en een kwartier was
# daarmee te kort. De eigenaar op 06-09-2026: "adviseren en meten inderdaad, met
# zet hem aan."
DRAAI_W = 30.0
STIL_KLAAR = timedelta(minutes=30)
# Een beurt die al liep toen de coach begon (een herstart middenin): het gat
# tussen de laatste opslag en nu komt uit de kwartieropslag, maar die haalt
# na een herstart zelf eerst in wat hij miste. Daarom even wachten.
TERUGREKENEN_WACHT = timedelta(minutes=2)
# Hoe ver terug de coach in de geschiedenis kijkt naar het begin van een
# beurt die hij niet zelf zag beginnen.
PROGRAMMA_TERUGKIJK = timedelta(hours=8)
# Zegt de coach "zet hem aan" en gebeurt er niets, dan één keer opnieuw.
HERINNERING = timedelta(minutes=45)
# De meter telt voor een programma-apparaat als wat hij de afgelopen tien
# minuten ten minste naar het net zag gaan, niet als de meting van dit moment.
# De eigenaar op 11-09-2026 om 09:35: een opklaring van een paar minuten gaf 2694 W
# teruglevering, meer dan de piek van Express 60, en de coach startte; om
# 09:37 was het 721 W en de opwarmpieken kwamen van het net. Een programma
# start één keer en draait dan anderhalf uur, dus hij hoort te starten op zon
# die blijft. Zolang er nog geen METER_DEKKING gemeten is (na een herstart)
# telt de meter niet, en rekent hij het lopende uur met de verwachting.
METER_VENSTER = timedelta(minutes=10)
METER_DEKKING = timedelta(minutes=8)
# De eindtijd van het apparaat telt pas als hij bij deze beurt hoort. Home
# Connect zet hem al bij het kiezen van het programma (het moment van kiezen
# plus de duur) en rekent hem pas een minuut na de start opnieuw uit. In een echte woning
# op 11-09-2026: om 09:01 gekozen, om 09:36 gestart, en de melding zei "klaar
# rond 10:56" terwijl hij om 11:28 klaar was. Wat voor EINDTIJD_MARGE voor de
# start gezet is, telt niet; de marge omdat de coach de start soms een ronde
# later ziet dan hij gebeurde. De melding "is gestart" wacht er hooguit
# EINDTIJD_WACHT op, en neemt daarna de duur uit de tabel.
#
# En hij telt pas als hij stilstaat. Een eindtijd van ná de start kan nog
# steeds de verkeerde zijn: in die woning op 15-09-2026 gaf Home Connect om
# 10:11:56 (Run om 10:11:57) eerst 11:33, om 10:13:02 acht minuten later
# 11:41, en klaar was hij om 11:45. De melding van 10:12:53 zat er twaalf
# minuten naast, negen seconden voor de correctie. Een eindtijd telt daarom
# pas als de coach hem twee ronden achter elkaar ongeveer hetzelfde zag,
# want dan is het apparaat klaar met rekenen. Ongeveer, want de sensor
# wiebelt een minuut heen en weer (11:41:02 en 11:42:02 om de minuut);
# EINDTIJD_SPELING is ruimer dan dat gewiebel en krapper dan een echte
# herberekening. EINDTIJD_WACHT ging daarvoor van twee naar vier minuten: er
# zijn twee ronden nodig om stil te staan, en de eerste waarde komt soms pas
# een ronde na de start.
EINDTIJD_MARGE = timedelta(minutes=2)
EINDTIJD_WACHT = timedelta(minutes=4)
EINDTIJD_SPELING = timedelta(minutes=2)
# Een meting weegt mee als lopend gemiddelde over zoveel beurten; daarna
# blijft hij even zwaar tellen, zodat een machine die ouder wordt bijblijft.
METING_MAX_N = 5

# --- De boiler --------------------------------------------------------------
#
# De eigenaar op 19-09-2026: "alleen de switch invullen en power invullen", en de rest
# zelflerend. Wat de coach dus zelf moet uitvinden: hoeveel hij trekt, hoe lang
# een vol vat duurt, en hoe snel dat vat weer leeg is.
#
# Hij trekt iets, of hij trekt niets. Een boilerelement is minstens een paar
# honderd watt en een meetstekker in rust een paar watt, dus die twee zijn niet
# te verwarren; honderd watt ligt daar ruim tussenin. Zodra hij een keer
# gemeten heeft wat het element trekt gebruikt hij een vijfde daarvan, zodat
# een boiler die bovenin terugregelt niet als "vol" telt zolang hij nog
# behoorlijk trekt.
BOILER_DRAAI_W = 100.0
BOILER_DRAAI_DEEL = 0.2
# Hoe lang er stroom op moet staan voor "hij vraagt niets" ook werkelijk "het
# vat is vol" betekent. Een meetstekker meldt niet elke seconde, en een
# thermostaat die net dichtvalt mag even de tijd krijgen.
BOILER_AANLOOP = timedelta(minutes=3)
BOILER_STIL = timedelta(minutes=3)
# Hoe vaak hij even kijkt of het vat nog warm is. Met de stroom eraf kan de
# boiler niet zeggen dat hij warmte wil, en dat is het enige gat in deze
# aanpak; de eigenaar koos op 19-09-2026 voor af en toe proefdraaien. Kost niets
# zolang het vat vol is, want dan vraagt de boiler geen stroom. Hetzelfde
# getal als waarmee de planner een gemeten vol vat gelooft: het is dezelfde
# vraag.
BOILER_PROEF_ELKE = BOILER_KIJKEN
# Hoeveel er in een beurt gegaan moet zijn voordat het een beurt heet. Minder
# dan dit is een proefmoment of een thermostaat die even aantikte, en daar valt
# niets uit te leren.
BOILER_MIN_KWH = 0.05

# Hoe lang de coach wacht tot een airco laat zien wat hij hem vroeg, voor een
# andere stand als iets van de bewoner telt (v0.119.0). Een airco in de cloud
# wordt eens per minuut gelezen (in de klantwoning op 13-10-2026 gemeten: elke
# ~60 s een nieuwe regel), en een opdracht gaat eerst de cloud in; vijf rondes
# is ruim genoeg voor allebei.
AIRCO_VOLGT = timedelta(minutes=5)


def _gelijk(a: Any, b: Any) -> bool:
    """Twee temperaturen gelijk, op een honderdste; wat geen getal is, is niet gelijk."""
    try:
        return abs(float(a) - float(b)) < 0.01
    except (TypeError, ValueError):
        return False

FASEMETING_VERS = timedelta(seconds=10)

# Hoe vaak achter elkaar dezelfde uitkomst nodig is voor de coach er iets over
# zegt. Drie ronden, dus in de praktijk drie minuten stabiel laden.
FASEMETING_RONDEN = 3

# Hoe lang de coach stroom aanbiedt aan een auto die niets afneemt voor hij er
# iets over zegt, en alleen als de klaar-tijd erdoor in gevaar komt. Bij Van den
# Dam gaf de Ford er op 30-08-2026 om 04:34 de brui aan; het eerste bericht
# daarover kwam om 07:00, toen de klaar-tijd al voorbij was. Twintig minuten is
# ruim langer dan elke auto nodig heeft om wakker te worden.
STIL_AANBOD = timedelta(minutes=20)

# Hoe vaak het huisverbruik en de zonverwachting opnieuw worden opgehaald. Het
# eerste is een som over dagen en verandert niet binnen een uur; het tweede komt
# van een dienst die zelf een paar keer per dag ververst. Elke ronde opnieuw
# vragen zou een databaselezing per minuut betekenen voor een getal dat niet
# beweegt.
HUIS_VERVERSEN = timedelta(hours=1)
# De balans van de afrekenperiode (v0.134.0): wat er sinds het begin van de
# jaarafrekening van het net kwam en wat er terugging, en wat er tot het einde
# van salderen nog bij komt, eens per dag uit de statistiek van Home Assistant.
JAARSALDO_VERVERSEN = timedelta(hours=24)
ZON_VERVERSEN = timedelta(minutes=30)
# Hoeveel uur vooruit de zon uit de eigen opwek gaat (v0.151.0): tot morgenavond.
ZON_VOORUIT_UREN = 40

# Over hoeveel dagen het huisverbruik wordt gemeten. Een week vangt het verschil
# tussen doordeweeks en weekend en is kort genoeg om een seizoen te volgen.
HUIS_VENSTER = timedelta(days=7)


def _netmeters(bronnen: dict[str, Any]) -> list[str]:
    """Elke netmeter die is ingevuld, ook die van de andere vorm (v0.170.0); zie `_net_afname`."""
    return [e for e in (bronnen.get("grid_signed"), bronnen.get("grid_import"), bronnen.get("grid_export")) if e]


def _net_afname(bronnen: dict[str, Any], reeksen: dict[str, dict[int, float]], stempel: int) -> float | None:
    """Wat het huis in dit kwartier van het net nam, in watt, teruglevering negatief, of None.

    Uit de opslag, per kwartier: `reeksen` is per entiteit het gemiddelde per begin van een kwartier.
    Eerst de meter van `grid_mode`, en zegt die voor dit kwartier niets, dan de andere vorm als die nog
    is ingevuld. Zegt geen van beide iets, dan None: dat kwartier is onbekend, geen kwartier zonder net.

    In een klantwoning kwam op 27-10-2026 een meter met een teken bij, naast de twee losse meters die
    er al waren. Het huisverbruik nam toen "signed zodra die reeks iets heeft", en telde het net voor
    elk ouder kwartier als nul: 's ochtends 0,00 kWh per uur in plaats van 2,67. Twee losse meters
    tellen alleen als ze er allebei zijn (of als er maar één is ingevuld).
    """
    def getekend() -> float | None:
        naam = bronnen.get("grid_signed")
        w = (reeksen.get(naam) or {}).get(stempel) if naam else None
        if w is None:
            return None
        return -w if bronnen.get("grid_signed_invert") else w

    def los() -> float | None:
        erin, eruit = bronnen.get("grid_import"), bronnen.get("grid_export")
        if not erin and not eruit:
            return None
        waarden = [(reeksen.get(e) or {}).get(stempel) if e else 0.0 for e in (erin, eruit)]
        if any(w is None for w in waarden):
            return None
        return waarden[0] - waarden[1]

    for lees in (getekend, los) if bronnen.get("grid_mode") == "signed" else (los, getekend):
        waarde = lees()
        if waarde is not None:
            return waarde
    return None


def _mediaan(waarden: list[float]) -> float:
    """De middelste waarde.

    Bewust de mediaan en niet het gemiddelde: één keer wassen tilt een
    gemiddelde over een week heen op, en dan denkt de coach dat het huis elke
    dag om dat uur zwaar is. de keuze op 30-08-2026, uit drie mogelijkheden.
    """
    if not waarden:
        return 0.0
    op_volgorde = sorted(waarden)
    midden = len(op_volgorde) // 2
    if len(op_volgorde) % 2:
        return op_volgorde[midden]
    return (op_volgorde[midden - 1] + op_volgorde[midden]) / 2.0

# Over hoeveel tijd het overschot wordt gladgestreken voor er omhoog wordt
# gestuurd. Drie minuten is lang genoeg om een wolk te laten passeren en kort
# genoeg om een opklaring niet te missen.
#
# Uitdrukkelijk een tijd en geen aantal metingen. Dat was het eerst wel, en dat
# klopte zolang er precies één ronde per minuut liep. Sinds een kabel of een
# statuswissel ook een ronde start, kunnen drie metingen binnen drie seconden
# vallen, en dan hangt een meting van vlak vóór het inpluggen nog in het venster
# en ziet de coach geen zon terwijl het dak vol ligt.
SMOOTH_WINDOW = timedelta(minutes=3)

# Hoe ruim voor het einde een lopende pauze opnieuw wordt weggeschreven. Vijf
# minuten is vier ronden speling, dus een gemiste ronde laat de auto niet
# onbedoeld aanslaan.
PAUSE_REFRESH = timedelta(minutes=5)

# De uitkomsten waarbij een pauze blijft staan tot de coach hem zelf weghaalt.
# Bij een volle aansluiting zou aflopen betekenen dat de paal terugvalt op zijn
# eigen maximum terwijl het huis al te veel trekt, en bij een pauze van de
# bewoner zou het betekenen dat zijn eigen opdracht na een tijdje vervalt.
# Overal elders is aflopen juist het goede antwoord: dan laadt de auto door, en
# duur is beter dan leeg.
FOREVER_RULES = frozenset({"no-room", "user-hold"})

# En de uitkomsten waarbij er helemaal niets naar de paal gaat. Zonder kabel valt
# er niets tegen te houden, en bij een volle auto zou een 0 die blijft staan de
# volgende auto in de weg zitten.
#
# Met één uitzondering, en die staat in `_niets_schrijven`: laadt de paal op dat
# moment nog, dan is "klaar" een besluit van de coach en geen constatering, en
# moet die 0 er wél heen. Zie daar.
NO_WRITE_RULES = frozenset({"disconnected", "complete"})

# Hoe lang het verslag wacht op een accustand die bij deze laadbeurt hoort.
# Een auto meldt zijn percentage niet op commando: de eigen Ford stopte op
# 25-08-2026 om 14:44 op 80% terwijl de app nog 70% zei, en werkte pas ruim een
# minuut later bij. De melding was toen al de deur uit met het oude getal, en
# juist bij een auto die zelf op 80% stopt is dat percentage het interessantste
# van het hele bericht. Drie minuten is ruim genoeg voor die ene verversing en
# kort genoeg dat het bericht nog bij de laadbeurt hoort. Komt er niets, dan
# gaat het verslag alsnog: te laat melden is erger dan een getal dat een ronde
# oud is.
SOC_SETTLE = timedelta(minutes=3)

# Een accusensor die met stappen meldt: hoeveel procent de coach er hoogstens
# zelf bij mag tellen tussen twee stappen door, en waar hij mee begint zolang
# hij nog geen stap gezien heeft. Zie `_soc_bijgeteld`.
#
# Beginnen bij één en naar boven leren, nooit andersom: over-corrigeren laat de
# coach te vroeg stoppen, onder-corrigeren is wat hij tot v0.68.0 altijd deed
# en kost hooguit nauwkeurigheid. Een sprong groter dan `SOC_STAP_MAX` telt niet
# mee als stap; dat is een auto die ondertussen ergens anders geladen heeft.
SOC_STAP_START = 1.0
SOC_STAP_MAX = 25.0
# Een accustand die niet meer meebeweegt (v0.176.0). In een klantwoning stond de accustand van een bus
# op 28-10-2026 de hele dag op 25%, terwijl er 72,9 kWh in ging: de integratie van de auto vroeg om
# opnieuw inloggen en werkte niets meer bij. De coach plande daarop, herstartte de paal bij "klaar" en
# stuurde een kritieke melding "niet vol". Zo'n stand gelooft hij niet meer zodra er sinds de laatste
# verandering meer in de accu ging dan er volgens die stand nog in paste (plus `SOC_VAST_MARGE`), of
# `SOC_VAST_PROCENT` van de accu zonder één verandering. Een auto die per tien procent meldt, of eens per
# uur, haalt dat geen van beide. En nooit onder `SOC_VAST_MIN`: een auto op 100% neemt nog een tijd wat
# af terwijl zijn stand blijft staan (in het virtuele huis 2,9 kWh), en dat is geen storing.
SOC_VAST_PROCENT = 50.0
SOC_VAST_MARGE = 10.0
SOC_VAST_MIN = 25.0

# Hoeveel twee ronden van elkaar mogen verschillen voordat het geen meting meer
# is maar een sensor die nog aan het bijkomen is. Zie `_tempo_leren`. Ruim
# genoeg voor het gewiebel van een paal die op zijn limiet moduleert, krap
# genoeg dat een tussenstand van bijna nul er niet doorheen komt.
TEMPO_SPELING = 0.3

# Hoeveel het gemiddelde tempo van een band moet verschuiven voordat de coach
# het opnieuw bewaart, en hoeveel procentpunt een bewaarde meting hoger in de
# band mag zijn gekomen voordat een nieuwe hem niet meer vervangt (v0.128.0).
# Zie `_tempo_te_schrijven`.
TEMPO_STAP = 0.1
TEMPO_BEREIK = 1.0

# Hoe lang de auto na een verhoging van de limiet de tijd krijgt om bij te
# komen voordat wat hij neemt als zijn eigen tempo telt. Gemeten in de klantwoning
# in de nacht van 18 op 19-09-2026: na een verlaging voor de zekering bleef de
# Ford op 16 A nog negen minuten (01:35 tot 01:44) en elf minuten (03:33 tot
# 03:44) op de oude stand hangen, en die minuten werden het tempo van band 4
# (7,58 kW) en band 6 (5,52 kW) terwijl hij daar gewoon 10 kW trok. Een auto die
# echt afbouwt doet dat langer dan een kwartier, dus wachten kost niets.
TEMPO_HERSTEL = timedelta(minutes=15)

# Hoe vaak de waarschuwing terugkomt dat een eigen pauze de klaar-tijd gaat
# kosten. De eigenaar op 26-08-2026: de pauze zelf blijft winnen, want het is zijn huis
# en zijn knop, maar één keer waarschuwen is te weinig. Wie het bericht om elf
# uur 's avonds wegveegt en om zeven uur naar een lege auto loopt, is niet
# geholpen.
#
# Een uur, en dat is een keuze van mij en niet een meting: kort genoeg om er nog
# iets aan te kunnen doen, lang genoeg om geen gezeur te worden. Hij komt alleen
# terug zolang het risico er werkelijk is, en houdt dus vanzelf op zodra de
# pauze eraf gaat, de klaar-tijd verzet wordt of de kabel eruit komt.
PAUSE_WARN_AGAIN = timedelta(hours=1)

# Hoe lang een ronde hoogstens mag duren. Ruim boven wat hij nodig heeft (de
# bevestiging van een limiet duurt hooguit een seconde of vijftien per apparaat)
# en ruim onder de ronde zelf, zodat een vastgelopen opdracht de coach niet stil
# kan leggen. Zie de reden bij het afbreken zelf.
ROUND_TIMEOUT = timedelta(seconds=45)

# Hoe vaak de coach nakijkt of hij zelf nog draait, en na hoe lang stilte hij
# daar een melding over stuurt. Een aparte klok met opzet: gaat er iets mis in de
# ronde zelf, dan moet degene die dat opmerkt er niet in vastzitten.
WATCHDOG_INTERVAL = timedelta(minutes=5)
WATCHDOG_SILENCE = timedelta(minutes=10)

# Hoe lang een akkoord, snelladen of een pauze blijft gelden zonder dat de coach
# ernaar heeft kunnen kijken. Twaalf uur dekt een nacht en een werkdag, en is
# kort genoeg dat een opdracht van eergisteren nooit op de auto van vandaag
# terechtkomt. Het uittrekken van de kabel wist ze altijd meteen; dit geldt
# alleen voor wat er tijdens een herstart gebeurd kan zijn.
SESSION_MEMORY = timedelta(hours=12)
# Hoe vaak het geheugen over een herstart heen hooguit naar schijf gaat (`GeheugenStore`,
# v0.172.0); bij het stoppen altijd, en een melding of een vrijgave meteen.
GEHEUGEN_ELKE = timedelta(minutes=5)

# Hoe lang de wekstroom blijft staan. Een minuut, dus in de praktijk één ronde,
# maar uitgedrukt in tijd omdat een statuswissel van de laadpaal ook een ronde
# start: op ronden geteld stond de wekstroom er soms maar drie seconden.
WAKE_WINDOW = timedelta(seconds=60)

# Hoe vaak een te hoge fasestroom hoogstens een extra ronde mag opleveren. Een
# meter meldt zich elke seconde, en een huis dat vol zit doet dat een tijdlang
# achter elkaar; zonder deze grens zou de coach zichzelf de hele avond op hol
# laten brengen. Vijftien seconden is vier keer sneller dan de klok en rustig
# genoeg voor de laadpaal.
HURRY_INTERVAL = timedelta(seconds=15)


# Hoe Zonneplan zijn prijzen meegeeft: in tienmiljoensten van een euro per kWh.
# Gemeten in de eerste woning op 22-09-2026: de rij van het lopende uur zei
# 3355224 naast een toestand van 0,3355224 €/kWh.
ZONNEPLAN_DELER = 10_000_000.0


def _prijsrijen(attributes: Any) -> list[tuple[datetime, datetime | None, float]]:
    """Elke vorm waarin een prijsentiteit zijn lijst meegeeft: (begin, eind, prijs).

    Er is geen standaard, dus dezelfde vormen als `readSchedule` in
    data-source.js, in dezelfde volgorde:

    - `prices: [{from, till, price}]`               Frank Energie
    - `raw_today` en `raw_tomorrow: [{start, end, value}]`  Nord Pool
    - `data: [{startsAt, total}]`                    Tibber, EnergyZero
    - `forecast: [{datetime, electricity_price}]`    Zonneplan, zie `ZONNEPLAN_DELER`

    Een rij die niet te lezen is wordt overgeslagen, de rest blijft staan.
    Tot 22-09-2026 kende de coach alleen de eerste vorm; in de eerste woning
    stond daardoor bij een dynamisch contract met Zonneplan de hele dag "de
    prijs van dit uur is niet bekend", en laadde er niets van het net.
    """
    attributes = attributes or {}

    def lijst(naam: str) -> list:
        waarde = attributes.get(naam)
        return waarde if isinstance(waarde, list) else []

    uit: list[tuple[datetime, datetime | None, float]] = []

    def voeg(begin: Any, eind: Any, prijs: Any) -> None:
        try:
            start = _tijdstip(begin)
            end = _tijdstip(eind) if eind is not None else None
            waarde = float(prijs)
        except (TypeError, ValueError):
            return
        if start is None or (eind is not None and end is None):
            return
        uit.append((start, end, waarde))

    for row in lijst("prices"):
        if isinstance(row, dict):
            voeg(row.get("from", row.get("start")), row.get("till", row.get("end")),
                 row.get("price", row.get("value")))
    for row in lijst("raw_today") + lijst("raw_tomorrow"):
        if isinstance(row, dict):
            voeg(row.get("start"), row.get("end"), row.get("value", row.get("price")))
    for row in lijst("data"):
        if isinstance(row, dict):
            voeg(row.get("startsAt", row.get("start", row.get("from", row.get("datetime")))),
                 row.get("endsAt", row.get("end", row.get("till"))),
                 row.get("total", row.get("price", row.get("value"))))
    for row in lijst("forecast"):
        if isinstance(row, dict) and row.get("electricity_price") is not None:
            try:
                prijs = float(row["electricity_price"]) / ZONNEPLAN_DELER
            except (TypeError, ValueError):
                continue
            voeg(row.get("datetime"), None, prijs)
    return uit


def zonsensoren(settings: dict[str, Any]) -> list[str]:
    """De vermogenssensoren van alle omvormers: de eerste en de extra's (v0.77.0)."""
    bronnen = settings.get("sources") or {}
    uit = [bronnen.get("solar")] + list(bronnen.get("solar_extra") or [])
    return [z for z in uit if isinstance(z, str) and z]


def _moment(now: datetime | None = None) -> datetime:
    """De klok waar de coach mee rekent: lokale tijd, zonder tijdzone erbij.

    Eén functie, want alles wat de coach onthoudt wordt met alles vergeleken.
    De ronde rekende hierin en de luisteraar op de fasesensoren in UTC mét
    tijdzone, en die twee vergelijkt Python niet: dat is een `TypeError` midden
    in een ronde, en dus een coach die stilvalt. Gevonden bij het nalezen, niet
    in het echt, en dat is het soort dat je maar één keer wilt hebben.
    """
    return dt_util.as_local(now or dt_util.utcnow()).replace(tzinfo=None)


def _tussen(van: datetime, tot: datetime) -> timedelta:
    """Hoe lang het echt duurde van `van` tot `tot`, ook over de klokwissel heen (v0.139.1).

    De coach rekent in lokale tijd zonder tijdzone. Over de wintertijd heen (25-10-2026,
    03:00 wordt weer 02:00) is het verschil tussen twee van die tijden een uur korter dan
    wat er echt verstreek: een vaatwasser die om 01:30 begon en om 03:30 klaar was, liep
    volgens de klok twee uur en echt drie, en onthield de coach de kortste. Via `as_utc`,
    die het herhaalde uur met `fold` uit elkaar houdt, is het de echte tijd.
    """
    if van.tzinfo is None and tot.tzinfo is None:
        return dt_util.as_utc(tot) - dt_util.as_utc(van)
    return tot.astimezone(timezone.utc) - van.astimezone(timezone.utc)


def _naar_geheugen(moment: datetime | None) -> str | None:
    """Een moment van de coach (lokaal, zonder tijdzone) voor `GeheugenStore`: in UTC (v0.172.0)."""
    return None if moment is None else dt_util.as_utc(moment).isoformat()


def _uit_geheugen(tekst: Any) -> datetime | None:
    """En terug naar de klok van de coach, of None."""
    try:
        return _moment(datetime.fromisoformat(str(tekst))) if tekst else None
    except (TypeError, ValueError):
        return None


def _regelklok(moment: datetime | None = None) -> datetime:
    """De klok van de regelaar van de thuisbatterij: UTC, zonder tijdzone erbij (v0.139.1).

    De regelaar rekent in seconden en wacht op zijn eigen opdrachten. Bij het ingaan van
    de wintertijd loopt de lokale klok een uur terug (25-10-2026, 03:00 weer 02:00), en
    met `_moment` werd "sinds de opdracht" dan negatief: de regelaar wachtte een uur op
    een opdracht die al lang stond, en de bewaking van een stille meter stond zo lang
    uit. UTC loopt nooit terug. Een lokale tijd gaat via `as_utc`, die het herhaalde uur
    met `fold` uit elkaar houdt. Alleen voor de regelaar; de rest van de coach blijft
    lokaal rekenen.
    """
    if moment is None:
        moment = dt_util.utcnow()
    return (moment.astimezone(timezone.utc) if moment.tzinfo else dt_util.as_utc(moment)).replace(tzinfo=None)


def _naast_elkaar(uit: dict, start: datetime, einde: datetime, prijs: float | None) -> None:
    """Een prijsblok in een lijst op lokale begintijd, ook als die tijd twee keer komt (v0.139.1).

    Bij het ingaan van de wintertijd (25-10-2026) komt 02:00 tot 03:00 twee keer, met elk
    zijn eigen prijs. Op de lokale klok van de coach is dat een uur, en dat uur duurt twee
    echte uren. Tot v0.139.1 overschreef het tweede uur het eerste: de coach rekende het
    eerste uur met de prijs van het tweede, en het laatste kwartier van het eerste uur kreeg
    een einde vóór zijn begin. Nu worden ze samengevoegd: het gemiddelde van de twee prijzen,
    en het einde van de laatste.
    """
    if start in uit:
        oud_einde, oud_prijs = uit[start][0], uit[start][1]
        samen = prijs if oud_prijs is None else oud_prijs if prijs is None else (oud_prijs + prijs) / 2
        uit[start] = (max(oud_einde, einde), samen, *uit[start][2:])
        return
    uit[start] = (einde, prijs)


def _jaar_eerder(dag: date) -> date:
    """Dezelfde dag een jaar eerder; 29 februari wordt 28 februari."""
    try:
        return dag.replace(year=dag.year - 1)
    except ValueError:
        return dag.replace(year=dag.year - 1, day=28)


def _jaar_later(dag: date) -> date:
    """Dezelfde dag een jaar later; 29 februari wordt 28 februari (v0.135.0)."""
    try:
        return dag.replace(year=dag.year + 1)
    except ValueError:
        return dag.replace(year=dag.year + 1, day=28)


def _datum(waarde: Any) -> date | None:
    """Een datum uit een instelling ("2026-09-15"), of None als hij leeg of onleesbaar is."""
    try:
        return date.fromisoformat(str(waarde or ""))
    except ValueError:
        return None


def _afrekenstart(waarde: Any, vandaag: date) -> date | None:
    """Het begin van de afrekenperiode waar vandaag in valt (v0.134.0).

    De klant vult de begindatum van zijn jaarafrekening in (`billing_start`).
    Een jaarafrekening gaat over een jaar, dus een datum van langer geleden
    schuift per jaar op: wie hem vorig jaar invulde hoeft hem niet bij te
    werken. Leeg, onleesbaar of in de toekomst: onbekend.
    """
    try:
        begin = date.fromisoformat(str(waarde or ""))
    except ValueError:
        return None
    if begin > vandaag:
        return None
    while True:
        try:
            volgende = begin.replace(year=begin.year + 1)
        except ValueError:
            volgende = begin.replace(year=begin.year + 1, day=28)
        if volgende > vandaag:
            return begin
        begin = volgende


def _bewust(moment: datetime | None) -> datetime:
    """Een moment met tijdzone: zonder is het de lokale tijd van Home Assistant (v0.137.0)."""
    if moment is None:
        return dt_util.utcnow()
    if moment.tzinfo is None:
        return moment.replace(tzinfo=dt_util.get_default_time_zone())
    return moment


def _minder(terug: float, kosten: float) -> float:
    """De terugleverprijs min `kosten`, maar een positieve prijs niet onder nul (v0.137.0).

    Een schaal maakt teruglevering duur, niet de zon zelf: zon die je gebruikt
    kost hooguit niets. Een negatieve prijs die er al was blijft staan.
    """
    return terug - kosten if terug - kosten >= 0 else min(terug, 0.0)


def _periode_op(contract: dict[str, Any], dag: str) -> dict[str, Any] | None:
    """Het eerdere stroomcontract waar die dag in valt, zoals `contractAt` in data-source.js."""
    for periode in contract.get("periods") or []:
        if not isinstance(periode, dict):
            continue
        if (not periode.get("from") or periode["from"] <= dag) and (not periode.get("to") or dag <= periode["to"]):
            return periode
    return None


def _herreken_beurt(beurt: dict[str, Any], koop: float, terug: float) -> dict[str, Any]:
    """Een opgeslagen beurt met een andere vaste prijs (v0.136.0).

    Dezelfde som als `_geld_bij`, `_herkomst_bij` en `_beurt_regel`, maar over
    de kilowatturen die de beurt al telde: wat niet van de zon kwam tegen de
    inkoopprijs (ook wat uit de thuisbatterij kwam, zoals `betaald` dat doet),
    de zon tegen wat teruglevering had opgebracht, en de maat alles van het net.
    Bij een vaste prijs is de maat hetzelfde aantal kWh tegen dezelfde prijs.
    Kilowatturen zonder prijs blijven erbuiten, net als toen. Een beurt zonder
    maat houdt die: dan was het inplugmoment onbekend, en dat verandert een
    andere prijs niet.
    """
    uit = dict(beurt)
    kwh = float(beurt.get("kwh") or 0.0)
    zon = float(beurt.get("solar_kwh") or 0.0)
    accu = float(beurt.get("battery_kwh") or 0.0)
    bekend = max(0.0, kwh - float(beurt.get("unknown_kwh") or 0.0))
    zon_bekend = zon * bekend / kwh if kwh > 0 else 0.0
    betaald = (bekend - zon_bekend) * koop + zon_bekend * terug
    uit["paid"] = round(betaald, 4)
    uit["solar_saved"] = round(zon_bekend * max(0.0, koop - terug), 4)
    uit["ref_price"] = koop
    uit["ref_feed_in"] = terug
    if beurt.get("ref_cost") is not None:
        uit["ref_cost"] = round(bekend * koop, 4)
        uit["saved"] = round(max(0.0, uit["ref_cost"] - uit["paid"]), 4)
    if beurt.get("grid_cost") is not None:
        uit["grid_cost"] = round(max(0.0, kwh - zon - accu) * koop, 4)
    if isinstance(beurt.get("baseline"), dict):
        maat = dict(beurt["baseline"])
        maat["cost"] = round(float(maat.get("kwh") or 0.0) * koop, 4)
        maat["points"] = [[k, round(float(k) * koop, 4)] for k, _ in (maat.get("points") or [])]
        uit["baseline"] = maat
    return uit


# Zonvoorspellers die een uurwaarde op het EIND van de periode zetten, per
# domein van hun integratie. De rest zet hem op het begin.
VOORSPELLER_OP_EIND = frozenset({"forecast_solar"})


def zonkromme_uit(domein: str, wh_hours: dict[str, Any]) -> dict[datetime, float]:
    """De uurkromme van één zonvoorspeller: kWh per lokaal uur, met het begin
    van dat uur als sleutel.

    **Niet elke voorspeller bedoelt met een tijdstip hetzelfde.** Forecast.Solar
    zegt in zijn eigen documentatie: "the value is always for the period from
    last timestamp to the timestamp in the key". De waarde bij 14:00 is dus
    wat er van 13:00 tot 14:00 verwacht wordt. Solcast zet het begin van elk
    half uur (`period_start`), Open-Meteo het begin van elk uur. Vóór v0.100.0
    las de coach alles als begin, en stond de hele verwachting van
    Forecast.Solar een uur te laat: de zon van 13:00 tot 14:00 kwam bij hem op
    14:00 tot 15:00 terecht, bij de paal, de batterij, de vaatwasser en de
    boiler. In de eigen woning op 26-09-2026 was het aan de kromme zelf te zien:
    05:28:26 met 0 Wh (de zonsopkomst, er komt nog niets vóór) en 17:25:37
    UTC met 37 Wh (de zonsondergang: wat er van 17:00 tot dan nog kwam).

    Een seconde terug in de tijd legt zo'n eindpunt in het goede uur, ook het
    eindpunt van de zonsondergang en een sleutel die precies op het hele uur
    valt.
    """
    uit: dict[datetime, float] = {}
    op_eind = domein in VOORSPELLER_OP_EIND
    for stempel, wh in (wh_hours or {}).items():
        moment = dt_util.parse_datetime(str(stempel))
        if moment is None:
            continue
        lokaal = _moment(moment)
        if op_eind:
            lokaal -= timedelta(seconds=1)
        uur = lokaal.replace(minute=0, second=0, microsecond=0)
        uit[uur] = uit.get(uur, 0.0) + float(wh) / 1000.0
    return uit


def _hoofdletter(tekst: str) -> str:
    """Alleen de eerste letter groot, de rest zoals hij was.

    `str.capitalize` maakt de rest klein: "Proefauto zonder HA" werd in het
    verslag van 24-09-2026 "Proefauto zonder ha", en "Tesla Model Y" wordt
    "Tesla model y".
    """
    return tekst[:1].upper() + tekst[1:]


def _number(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """A sensor read as a plain number, or None when it says nothing useful."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unknown", "unavailable", ""):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _unit(hass: HomeAssistant, entity_id: str | None) -> str | None:
    """De eenheid die deze entiteit zelf opgeeft."""
    state = hass.states.get(entity_id) if entity_id else None
    return None if state is None else state.attributes.get("unit_of_measurement")


def _celsius(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Een temperatuursensor in graden Celsius, ook als hij Fahrenheit geeft."""
    waarde = _number(hass, entity_id)
    if waarde is not None and _unit(hass, entity_id) in ("°F", "℉"):
        return (waarde - 32) * 5 / 9
    return waarde


def _temp_grens(settings: dict[str, Any]) -> float | None:
    """De grens van de temperatuurmelding, of None als die uit staat."""
    alert = (settings.get("notifications") or {}).get("temp_alert") or {}
    if not alert.get("enabled"):
        return None
    try:
        return float(alert["max_c"])
    except (KeyError, TypeError, ValueError):
        return None


def _temp_nodig(settings: dict[str, Any], device: dict[str, Any]) -> bool:
    """Of de coach iets doet met de temperatuur van deze batterij: een melding
    (`temp_alert`) of een ventilator (`fan` met `fan_above_c`)."""
    entities = device.get("entities") or {}
    # Bij een vriezer (v0.125.0) en een koelkast (v0.131.0) is de temperatuur het hele punt.
    if device.get("type") in KOELWAREN and entities.get("temperature"):
        return True
    if device.get("type") != "thuisbatterij" or not entities.get("temperature"):
        return False
    ventilator = entities.get("fan") and (device.get("battery") or {}).get("fan_above_c") is not None
    return bool(ventilator) or _temp_grens(settings) is not None


def _altijd_aan(device: dict[str, Any]) -> str | None:
    """De schakelaar van een stekker die altijd aan moet staan, of None (v0.120.0)."""
    if device.get("type") not in ALTIJD_AAN_TYPES or not device.get("always_on"):
        return None
    return (device.get("entities") or {}).get("switch") or None


def _altijd_aan_melden(settings: dict[str, Any]) -> bool:
    """Of een stekker die uit blijft naar de telefoon gaat (Meldingen, `always_on_alert`)."""
    return bool(((settings.get("notifications") or {}).get("always_on_alert") or {}).get("enabled"))


def _stekker_naam(device: dict[str, Any]) -> str:
    """Een stekker vooraan in een melding: zijn eigen naam, of "De vriezer", "De vaatwasser"."""
    eigen = str(device.get("name") or "").strip()
    if eigen:
        return eigen[0].upper() + eigen[1:]
    # Bij een smart plug wat eraan hangt, bij een ander type het type zelf.
    soort = device.get("appliance") if device.get("type") == "smartplug" else device.get("type")
    label, lidwoord = STEKKER_APPARATEN.get(str(soort or ""), STEKKER_APPARATEN["overig"])
    # In het Engels "The freezer": het label uit de tabel vertaald, het lidwoord per taal.
    apparaat = t(label).lower()
    if lidwoord == "de":
        return t("De {apparaat}", apparaat=apparaat)
    if lidwoord == "het":
        return t("Het {apparaat}", apparaat=apparaat)
    return f"{lidwoord.capitalize()} {apparaat}"


def _graden(waarde: float) -> str:
    """46,2 °C, of 45 °C als er niets achter de komma staat."""
    tekst = getal(waarde, 1)
    return f"{tekst[:-2] if tekst.endswith((',0', '.0')) else tekst} °C"


def _watts(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Een vermogenssensor in watt, wat hij zichzelf ook noemt.

    Alles wat vermogen is gaat hierlangs en niet langs `_number`. Zie
    `units.py` voor waarom dat een klant een laadbeurt kon kosten.
    """
    return to_watts(_number(hass, entity_id), _unit(hass, entity_id))


def _kwh_tekst(waarde: float) -> str:
    """Kilowattuur zoals in de meldingen: 3,4 kWh."""
    return f"{getal(waarde, 1)} kWh"


def _bedrag(waarde: float, grootste: float | None = None) -> str:
    """Een bedrag in een verslag (v0.101.0): onder een euro in drie decimalen,
    zodat een besparing van anderhalve cent niet "€ 0,02" wordt, en daarboven
    in twee, want "€ 6,720" leest als een prijs per kWh. Staan er meer bedragen
    in één zin, dan bepaalt het grootste (`grootste`) het voor allemaal."""
    maat = abs(grootste if grootste is not None else waarde)
    return f"€ {getal(waarde, 2)}" if maat >= 1.0 else f"€ {getal(waarde, 3)}"



# Onder zoveel kWh noemt een verslag een bron niet: "0,0 kWh van het net" leest
# als een fout, en een paar wattuur zegt de bewoner niets.
HERKOMST_MIN_KWH = 0.05

# Een beurt waarin minder ging dan dit is geen laadbeurt voor de kaart: de kabel
# ging erin en er weer uit zonder te laden. Dan blijft de vorige staan (v0.106.0).
BEURT_KAART_MIN_KWH = 0.05


def _herkomst_zin(zon: float, accu: float, net: float, net_eur: float | None) -> str:
    """Waar de stroom van een beurt vandaan kwam, in één korte regel (v0.101.0).

    Voor elk apparaat dezelfde regel, eigen energie eerst. De eigenaar op
    28-09-2026, bij een vaatwasser die op zon en thuisbatterij draaide en toch
    "ongeveer € 0,199" meldde: "er is niks van het net af gehaald." Het bedrag
    hoort bij het net, want dat is wat er aan de leverancier betaald is; wat de
    thuisbatterij opleverde staat bij de batterij zelf.

    Sinds v0.102.1 een opsomming in plaats van een zin: "1,5 kWh zon, 15,3 kWh
    net (€ 3,71)." Zie `_verslag`.
    """
    bedrag = f" ({_bedrag(net_eur)})" if net_eur is not None and net_eur >= 0.005 else ""
    delen = []
    if zon >= HERKOMST_MIN_KWH:
        delen.append(("zon", t("{kwh} zon", kwh=_kwh_tekst(zon))))
    if accu >= HERKOMST_MIN_KWH:
        delen.append(("accu", t("{kwh} thuisbatterij", kwh=_kwh_tekst(accu))))
    if net >= HERKOMST_MIN_KWH:
        delen.append(("net", t("{kwh} net{bedrag}", kwh=_kwh_tekst(net), bedrag=bedrag)))
    if not delen:
        return ""
    if len(delen) == 1:
        soort = delen[0][0]
        if soort == "zon":
            return t("Alles van je zon.")
        if soort == "accu":
            return t("Alles uit je thuisbatterij.")
        return t("Alles van het net{bedrag}.", bedrag=bedrag)
    return ", ".join(tekst for _, tekst in delen) + "."


def _verslag(*regels: str) -> str:
    """Een verslag van een beurt: een paar korte regels onder elkaar (v0.102.1).

    De eigenaar op 30-09-2026, over een verslag van vijf zinnen: "deze tekst is
    veel te lang, moet korter en overzichtelijker. Op de telefoon past die
    melding niet." Dus per regel één ding: wat er klaar is, hoeveel en wanneer,
    waar het vandaan kwam, wat het scheelde. Elke regel eindigt op een punt,
    zodat het ook leest waar een regeleinde niet getoond wordt. De uitsplitsing
    van wat er bespaard is staat in het paneel, onder Bespaard.
    """
    return "\n".join(regel.strip() for regel in regels if regel and regel.strip())


def _kwh(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Een energiesensor in kilowattuur, wat hij zichzelf ook noemt."""
    return to_kwh(_number(hass, entity_id), _unit(hass, entity_id))


def _tijdstip(waarde: Any) -> datetime | None:
    """Een tijdstip uit een attribuut, of het nu tekst is of al een datetime.

    Een integratie mag in een attribuut zetten wat hij wil, en een `datetime`
    komt daar net zo vaak in voor als een ISO-string. Over de API van Home
    Assistant is dat verschil niet te zien, want daar wordt alles tot tekst
    geserialiseerd; binnen HA staat het echte object er nog.

    `dt_util.parse_datetime` wil alleen tekst en geeft op een `datetime` een
    TypeError. Die viel in `_slots` stilletjes weg in de `except`, waardoor er
    per blok een regel werd overgeslagen zonder spoor in enig logboek. In de
    klantwoning sneuvelden op 29-08-2026 zo alle 24 uurblokken tegelijk en zei de
    coach dat er geen prijzen binnenkwamen, terwijl zijn sensor gewoon gevuld
    was. Hij laadde daardoor op vol vermogen van het net terwijl hij op de zon
    had horen te wachten.
    """
    if isinstance(waarde, datetime):
        return waarde
    if isinstance(waarde, str):
        return dt_util.parse_datetime(waarde)
    return None


def _text(hass: HomeAssistant, entity_id: str | None) -> str:
    """A sensor read as its raw state, lower-cased for comparing."""
    if not entity_id:
        return ""
    state = hass.states.get(entity_id)
    return "" if state is None else str(state.state).lower()


def _opsomming(namen: list[tuple[str, str]]) -> str:
    """Stekkers in één zin: de eerste met zijn naam vooraan, de rest zoals hij verderop heet."""
    lijst = [namen[0][0], *(verder for _naam, verder in namen[1:])]
    if len(lijst) == 1:
        return lijst[0]
    return t("{voor} en {laatste}", voor=", ".join(lijst[:-1]), laatste=lijst[-1])


# De standen van Miele (de integratie `miele` van Home Assistant) in de woorden
# van Home Connect, waar de rest van de coach mee rekent (v0.124.0; `DRAAIT`,
# `KLAAR` in planner.py). "programmed" en "waiting_to_start" zijn: het
# programma staat klaar en wacht op een start, dus "ready". Een programma dat
# afgebroken is ("program_interrupted") is voorbij als er geen beurt loopt;
# midden in een beurt is het een pauze (v0.127.0, in `_one_programma`).
MIELE_STATUS = {
    "off": "inactive",
    "on": "ready",
    "idle": "ready",
    "programmed": "ready",
    "waiting_to_start": "ready",
    "in_use": "run",
    "pause": "pause",
    "rinse_hold": "pause",
    "program_ended": "finished",
    "program_interrupted": "finished",
    "failure": "error",
    "not_connected": "",
}

def _programma_alleen_lezen(device: dict[str, Any]) -> bool:
    """Of de coach dit apparaat met een programma alleen volgt (v0.127.0).

    Zonder het vinkje "mag sturen": draait, klaar, het verslag en de meting wel,
    starten, de vrijgave en een sessie niet. Hetzelfde als
    `programma_alleen_lezen` in entiteit.py, voor de kaarten.
    """
    return not device.get("controllable")


# Hoe een programma-apparaat in een melding heet zonder eigen naam.
PROGRAMMA_NAAM = {"vaatwasser": nt("De vaatwasser"), "wasmachine": nt("De wasmachine"), "droger": nt("De droger")}

# Wat Miele zegt als er geen programma gekozen is.
GEEN_PROGRAMMA = frozenset({"", "no_program", "unknown", "unavailable", "none"})


def _programma_naam(device: dict[str, Any]) -> str:
    """De naam van een programma-apparaat vooraan in een melding."""
    return device.get("name") or t(PROGRAMMA_NAAM.get(str(device.get("type") or ""), nt("Het apparaat")))


def _eindtijd(
    hass: HomeAssistant, entity_id: str | None, now: datetime, sinds: datetime | None = None
) -> datetime | None:
    """Wanneer het apparaat zelf zegt klaar te zijn, of None.

    Home Connect geeft de resterende tijd als een tijdstip (de sensor
    `remaining_program_time`, een timestamp); andere integraties geven de
    minuten of de seconden die nog resten, en Home Connect Local de uren
    (`sensor_remaining_program_time`, seconden van de machine, door Home
    Assistant als uren getoond: 1,4833 h thuis op 23-09-2026). Allemaal
    hetzelfde antwoord op dezelfde vraag, als lokaal tijdstip zonder zone,
    zoals `now`. De eigenaar op 07-09-2026: "pak de eindtijd van de
    integratie." Zonder eenheid zijn het minuten.

    Met `sinds` telt alleen een waarde die op of na dat moment gezet is: een
    eindtijd van voor de start is die van het kiezen van het programma, niet
    die van de beurt. Zie `EINDTIJD_MARGE`.
    """
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unknown", "unavailable", ""):
        return None
    if sinds is not None:
        gezet = getattr(state, "last_changed", None) or getattr(state, "last_updated", None)
        if gezet is not None:
            if gezet.tzinfo is not None:
                gezet = dt_util.as_local(gezet).replace(tzinfo=None)
            if gezet < sinds:
                return None
    try:
        getal = float(state.state)
    except (TypeError, ValueError):
        moment = _tijdstip(state.state)
        if moment is None:
            return None
        if moment.tzinfo is not None:
            moment = dt_util.as_local(moment).replace(tzinfo=None)
        return moment
    eenheid = str(state.attributes.get("unit_of_measurement") or "").lower()
    if eenheid in ("s", "sec", "seconds"):
        seconden = getal
    elif eenheid in ("h", "hr", "hrs", "hours", "uur", "u"):
        seconden = getal * 3600.0
    elif eenheid in ("d", "days", "dagen"):
        seconden = getal * 86400.0
    else:
        seconden = getal * 60.0
    if seconden < 0:
        return None
    return now + timedelta(seconds=seconden)


def _eindtijd_vast(sessie: dict[str, Any], rauw: datetime | None) -> datetime | None:
    """De eindtijd zoals de coach hem gelooft: pas als hij stilstaat.

    Een apparaat rekent zijn eindtijd nog even door nadat het begonnen is.
    In die woning op 15-09-2026 zei Home Connect bij de start 11:33 en een minuut
    later 11:41; klaar was hij om 11:45. Een nieuwe waarde telt daarom pas
    als de volgende ronde er ongeveer hetzelfde staat (`EINDTIJD_SPELING`,
    ruimer dan het gewiebel van een minuut dat die sensor vertoont).

    Tot die tijd blijft staan wat er al geloofd werd, want een eindtijd die
    verspringt hoort niet van de kaart te verdwijnen. Zonder waarde blijft
    het laatste antwoord ook staan: een sensor die even wegvalt zegt niet
    dat het apparaat niet meer weet wanneer hij klaar is.
    """
    if rauw is not None:
        vorig = sessie.get("eind_gezien")
        if vorig is not None and abs(rauw - vorig) <= EINDTIJD_SPELING:
            sessie["eind"] = rauw
        sessie["eind_gezien"] = rauw
    return sessie.get("eind")


def _wanneer(now: datetime, moment: datetime) -> str:
    """"06:00" of "morgen om 06:00", zodat een tijdstip niet twee dingen kan zijn."""
    if moment.date() == now.date():
        return f"{moment:%H:%M}"
    if moment.date() == (now + timedelta(days=1)).date():
        return t("morgen om {klok}", klok=f"{moment:%H:%M}")
    return t("{dag} om {klok}", dag=t(DAGNAMEN[moment.weekday()]), klok=f"{moment:%H:%M}")


def _time(value: str | None) -> time | None:
    """"07:00" as a time, or None."""
    if not value:
        return None
    try:
        hour, minute = value.split(":")
        return time(int(hour), int(minute))
    except (ValueError, AttributeError):
        return None


class PaalOnbereikbaar(Exception):
    """Een opdracht aan de laadpaal die niet aankwam (v0.163.3).

    Een paal die zichzelf herstart of even van het netwerk is, laat elke opdracht falen
    met een fout van zijn eigen integratie: bij een Alfen een `ConnectionException` van
    Modbus, bij een Easee een fout van de cloud. Dat is een storing buiten de coach, geen
    fout in hem; zie `_async_paal_weg`.
    """


class ChargerCoach:
    """Watches every steerable charging point and acts on what it sees."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up without touching anything yet."""
        self.hass = hass
        self._cancel = None
        # De naam van een stand zoals Home Assistant hem vertaalt, per
        # (entiteit, waarde): "cottons" wordt "Katoen" (v0.124.0).
        self._staat_namen: dict[tuple[str, str], str] = {}
        # What we last decided per device, so a charger is not re-commanded for
        # a fraction of an amp.
        self._last: dict[str, Decision] = {}
        # When the session we started began. Not persisted on purpose: after a
        # restart the charger itself says whether it is charging, and treating
        # that as "just started" only costs a few minutes of patience.
        self._since: dict[str, datetime] = {}
        # Of de paal de vorige ronde laadde. Begint hij opnieuw, dan begint de
        # aanloop ook opnieuw; zie `_since` hierboven en `_tempo_leren`.
        self._laadde: dict[str, bool] = {}
        # Of de paal deze ronde zelf zei dat de kabel eruit is, en niet alleen
        # niets zei. Zie `_read` en het vergeten van de sessie.
        self._echt_los: dict[str, bool] = {}
        # The latest decision per device, for the panel to ask after.
        self.state: dict[str, dict[str, Any]] = {}
        # Devices the customer said yes to. Only meaningful at "propose", and
        # it lasts exactly one session: pull the cable and the coach is back to
        # asking. Somebody who agreed to one charge did not agree to every
        # charge from now on.
        self._approved: set[str] = set()
        # When a charging point that was not following was last prodded.
        self._nudged: dict[str, datetime] = {}
        # Per laadpunt de laatste stroom die er werkelijk liep, met het moment
        # waarop de coach hem voor het eerst op nul zag (None zolang hij loopt).
        # Alleen om de na-ijl van de fasemeting op te vangen als de paal net
        # gestopt is; zie `_read`.
        self._laatste_stroom: dict[str, tuple[float, datetime | None]] = {}
        # Sinds wanneer een laadpunt onder zijn limiet blijft, en bij welke
        # limiet die klok begon. Zie `achter_s` in planner.py.
        self._achter_sinds: dict[str, tuple[datetime, float]] = {}
        # De laatste bruikbare status per laadpunt, zodat een entiteit die even
        # wegvalt niet als een losgekoppelde kabel leest. Zie `_read`.
        self._laatste_status: dict[str, str] = {}
        # Sinds wanneer een Alfen aanbod geeft zonder dat de auto iets neemt
        # (`_status_afgeleid`).
        self._stil_sinds: dict[str, datetime] = {}
        # En hetzelfde voor de metingen: per entiteit de laatste bruikbare
        # waarde met het moment erbij. Zie `_volgehouden` en `MEETNAIJL`.
        self._laatste_meting: dict[str, tuple[float, datetime]] = {}
        # De laatste ronde waarin de netmeting wél te lezen was, en sinds
        # wanneer hij zwijgt. Alleen om het te kunnen zeggen; zie `_nettip`.
        self._net_gezien: datetime | None = None
        self._net_stil_sinds: datetime | None = None
        self._net_stil_wat = "meter"
        # Sinds wanneer een paal zegt dat er geen kabel in zit. Pas als hij dat
        # `KABEL_ONTDREUN` lang volhoudt telt het, en dan is dít het moment dat
        # in het verslag komt. Zie `_read`.
        self._los_sinds: dict[str, datetime] = {}
        # Aan welke palen ooit een kabel gezien is. Alleen daar valt er iets te
        # ontdreunen: een paal die nog nooit bezet was is gewoon leeg.
        self._was_verbonden: set[str] = set()
        # De fasestromen zoals de meter ze meldt, met het moment erbij, om een
        # enkele uitschieter uit te kunnen middelen. Per entiteit, want de drie
        # fasen melden niet tegelijk. Zie `FASE_VENSTER`.
        self._fase_historie: dict[str, list[tuple[datetime, float]]] = {}
        # Wat elke paal in de vorige ronde trok, en wanneer er voor het laatst
        # een paal een stap omlaag deed. Zie `_gladde_fase`.
        self._stroom_vorige: dict[str, float] = {}
        self._daling: datetime | None = None
        # Wat de fasemeting van een laadpunt de laatste ronden opleverde, als
        # (aantal fasen, hoe vaak achter elkaar). Zie `_measured_phases`.
        self._fasen_gemeten: dict[str, tuple[int, int]] = {}
        # De laatste metingen van het overschot, per apparaat, om op te dempen.
        self._zon: dict[str, list[tuple[datetime, float]]] = {}
        # Wat de coach zelf aan energie langs zag komen, per apparaat en dus
        # over laadbeurten heen. Met de stand van de teller van de paal erbij en
        # hoeveel er zelf gemeten was toen die voor het laatst stapte. Zie
        # `_geladen`.
        self._eigen: dict[str, dict[str, Any]] = {}
        # Wat het huis zelf gebruikt per uur van de dag, en de zonverwachting per
        # uur. Samen bepalen ze hoeveel er in een komend uur voor de auto
        # overblijft. Zie `_async_huisverbruik` en `_async_zonkromme`.
        self._huis_kwh: dict[int, float] = {}
        # Per thuisbatterij: de regelaar, het besluit van deze minuut, en wat
        # hij sinds de laatste opslag verdiende. Zie `_one_batterij`.
        self._batterij: dict[str, dict[str, Any]] = {}
        # Per Growatt wat de coach ervan weet (v0.150.0): het apparaat in Home Assistant,
        # of hij een laadschema kan schrijven en wanneer hij dat het laatst probeerde.
        self._growatt: dict[str, dict[str, Any]] = {}
        self._batterij_meters: set[str] = set()
        self._unwatch_batterij = None
        self._cancel_regel = None
        # Per sensor sinds wanneer hij niets zegt, en welke daarvan al gemeld zijn.
        self._sensor_stil: dict[str, datetime] = {}
        # Welke sensoren de coach ooit een waarde zag geven (v0.178.0): alleen die tellen
        # mee voor "het internet thuis is weg". Zie `_async_sensoren_stil`.
        self._sensor_ooit: set[str] = set()
        self._sensor_gemeld: set[str] = set()
        # Per integratie die niet opkwam sinds wanneer, welke gemeld is, en de volgende controle (v0.166.0).
        self._integratie_stuk: dict[str, datetime] = {}
        self._integratie_gemeld: set[str] = set()
        # Integraties die om opnieuw inloggen vragen en al gemeld zijn (v0.176.0).
        self._integratie_inloggen: set[str] = set()
        self._integratie_om: datetime | None = None
        # Per laadpaal sinds wanneer een opdracht niet aankomt, en welke al gemeld zijn (v0.163.3).
        self._paal_weg: dict[str, datetime] = {}
        # Wat elke paal deze ronde in totaal trekt of gaat trekken, per fase (v0.164.1): voor een
        # groep zonder meter, waar een toezegging bovenop de meting niets zegt.
        self._paal_stroom: dict[str, float] = {}
        # Per groep zonder meter sinds wanneer de som boven `GROEP_VOL_DEEL` staat, en welke gemeld zijn.
        self._groep_vol: dict[str, datetime] = {}
        self._groep_vol_gemeld: set[str] = set()
        self._paal_gemeld: set[str] = set()
        # Wat daarvan in de opslag staat, zodat er alleen bij een verandering
        # geschreven wordt. Zie `sensor_quiet`.
        self._sensor_gemeld_bewaard: set[str] = set()
        # De prijslijsten van de ingebouwde Nord Pool, per sensor en per dag, en
        # wanneer een dag voor het laatst gevraagd is. Zie `_async_nordpool`.
        self._nordpool: dict[str, dict[str, list[dict[str, Any]]]] = {}
        self._nordpool_gevraagd: dict[tuple[str, str], datetime] = {}
        # De verbruikswacht: sinds wanneer er onafgebroken water loopt, of dat
        # al gemeld is, en welke dagen al gemeld zijn. Zie `_async_verbruikswacht`.
        self._water_loopt_sinds: datetime | None = None
        self._water_gemeld = False
        self._verbruik_gemeld: set[str] = set()
        # De temperatuurwacht: per thuisbatterij sinds wanneer hij boven de grens
        # is, en welke al gemeld zijn. Zie `_async_temperatuurwacht`.
        self._temp_boven: dict[str, datetime] = {}
        self._temp_gemeld: set[str] = set()
        # De vriezerwacht (v0.125.0): per vriezer en per soort (deur, warm,
        # storing) sinds wanneer, en wat al gemeld is. Zie `_async_vriezerwacht`.
        self._vriezer_sinds: dict[tuple[str, str], datetime] = {}
        # Wanneer de temperatuur van een vriezer of koelkast voor het laatst niets zei,
        # voor de 0,0 waarmee Miele terugkomt (`KOEL_NUL`, v0.141.1).
        self._koel_weg: dict[str, datetime] = {}
        self._vriezer_gemeld: set[tuple[str, str]] = set()
        # De smart plugs die altijd aan moeten staan (v0.120.0): sinds wanneer
        # hij uit is, welke al gemeld zijn, welke de coach zelf weer aanzette, en
        # de klok die na `ALTIJD_AAN_WACHT` nog een keer kijkt. Zie `_async_altijd_aan`.
        self._stekker_uit: dict[str, datetime] = {}
        self._stekker_gemeld: set[str] = set()
        self._stekker_gezet: set[str] = set()
        # Sinds v0.178.0: welke stekkers de coach ooit bereikbaar zag, en welke nog nooit
        # bereikbaar waren en dat al gemeld kregen (een gewone melding, geen kritiek).
        self._stekker_ooit: set[str] = set()
        self._stekker_nieuw: set[str] = set()
        self._stekker_klok: dict[str, Any] = {}
        # Sinds v0.183.0: welke gemelde stekkers terug zijn en sinds wanneer, voor één regel
        # "staan weer aan" (zie `ALTIJD_AAN_BUNDEL`).
        self._stekker_terug: dict[str, datetime] = {}
        # Welke vrijgaveschakelaars de stroom van hun eigen machine zijn, al in
        # het log gezet. Zie `_vrijgave_entiteit`.
        self._stroom_gemeld: set[tuple[str, str]] = set()
        # Wanneer de auto aan een laadpunt voor het laatst gewekt is, en of de
        # kabel er de vorige ronde al in zat. Zie `_async_auto_wekken`.
        self._gewekt: dict[str, datetime] = {}
        self._kabel_erin: dict[str, bool] = {}
        self._huis_tot: datetime | None = None
        # Wat er in de afrekenperiode van het net kwam en wat er terugging, en
        # wat er tot het einde van salderen nog bij komt, in kWh (v0.134.0).
        # Zie `_async_jaarsaldo`.
        self._jaarsaldo: dict[str, Any] | None = None
        self._jaarsaldo_tot: datetime | None = None
        # De schaal van de terugleverkosten die eraan komt, met en zonder
        # thuisbatterij, en wat een kWh minder teruglevering nu scheelt (v0.137.0).
        # Zie `_async_schaal`.
        self._schaal: dict[str, Any] | None = None
        self._schaal_tot: datetime | None = None
        self._zon_kwh: dict[datetime, float] = {}
        self._zon_geschat = True
        # Wat de zonverwachting per ronde beloofde en wat de meter gaf, als
        # (moment, voorspeld W, gemeten W, minuten). Van het huis en niet van
        # een laadpunt: de zon is van de woning. Zie `_zon_gemeten`.
        self._zon_reeks: list[tuple[datetime, float, float, float]] = []
        self._zon_tot: datetime | None = None
        # Wie er op snelladen staat. Net als een akkoord niet bewaard over een
        # herstart heen en afgelopen zodra de kabel eruit gaat: snelladen is
        # iets voor nu, niet iets wat stilletjes blijft staan.
        self._boost: set[str] = set()
        # Tot welke accustand "Nu vol laden" bij een thuisbatterij gaat (v0.141.0),
        # als de bewoner dat in de pop-up koos; zonder is het de laadgrens.
        self._vol_tot: dict[str, float] = {}
        # De modus die de bewoner op de kaart koos voor deze beurt, "zon" of
        # "continu" (v0.87.0). Leeg is de voorkeur van de paal (`charge_mode`
        # bij Apparaten). Zelfde levensduur als snelladen: de kabel eruit en
        # het is weer de voorkeur, zodat er niets te vergeten valt.
        self._modus: dict[str, str] = {}
        # Het vermogen van elke batterij bij de vorige lezing, om een flinke
        # daling te zien. Zie `_batterij_wijkt`.
        self._batterij_vorige_w: dict[str, float] = {}
        # Tot hoeveel procent deze beurt laadt, als de bewoner dat op de kaart
        # koos (v0.88.0), net als de schuif van evcc. Zonder keuze het doel uit
        # het autoprofiel. Weg zodra de kabel eruit gaat.
        self._doel: dict[str, float] = {}
        # Het doel van de planning dat deze ronde geldt, en de algemene limiet
        # ernaast, voor de kaart (v0.96.0). Zie `_read`.
        self._doel_planning: dict[str, float] = {}
        self._doel_algemeen: dict[str, float] = {}
        # De thuisbatterij nu leegladen tot deze accustand (procent), per
        # apparaat. Zie `async_drain`.
        self._drain: dict[str, float] = {}
        # En wie er met de hand op pauze staat. Zelfde levensduur, tegengestelde
        # bedoeling.
        self._paused: set[str] = set()
        # Hoeveel ronden een sessie al tegen de ladder in wordt aangehouden.
        self._holding: dict[str, int] = {}
        # De fasewissel van een Alfen (v0.104.0), per paal: welk aantal fasen het
        # besluit wil en sinds wanneer, wanneer er voor het laatst gewisseld is,
        # en een wissel die bezig is (eerst stil, dan omzetten). Zie `_fasen_besluit`.
        self._fase_wens: dict[str, tuple[int, datetime]] = {}
        self._fase_gewisseld: dict[str, datetime] = {}
        self._fase_bezig: dict[str, dict[str, Any]] = {}
        # Het laatste besluit dat in de geschiedenis staat, per paal, zodat
        # alleen een verandering een regel oplevert en niet elke minuut.
        self._besluit_genoteerd: dict[str, tuple[Any, ...]] = {}
        # Beurten die bij een herstart nog open stonden in de opslag, per
        # apparaat: het geld van de beurt loopt daar gewoon in door.
        self._beurt_open: dict[str, dict[str, Any]] = {}
        # Wat er van een lopende laadbeurt bewaard was, per paal, tot de
        # eerste ronde het overneemt. Zie `HERVAT_MAX` en `_async_beurten_laden`.
        self._hervat: dict[str, dict[str, Any]] = {}
        # Of de wekpoging van deze sessie nog openstaat. Eén per sessie, dus
        # zodra hij gedaan is blijft dit staan tot de kabel eruit gaat.
        self._woken: set[str] = set()
        # Laadpunten waar de paal "klaar" zegt terwijl de accustand zegt van
        # niet, en die deze ronde daarom één keer opnieuw gestart mogen worden.
        # De eigenaar op 06-09-2026, na een Ford die om 04:27 met een storing afhaakte
        # en op 86% bleef staan: "hij is nog niet vol, dus dan ook maar een
        # herstart." Wanneer die herstart gestuurd is staat in `_herstart_gedaan`;
        # zolang dat er staat gelooft de coach "klaar" gewoon weer.
        # Per programma-apparaat wat er deze beurt gebeurt: wanneer hij is
        # vrijgegeven, wanneer de coach op start drukte, wanneer hij ging
        # draaien, en de tellers voor het verslag. Zie `_one_programma`.
        self._programma: dict[str, dict[str, Any]] = {}
        # Per boiler wat er deze ronde bekend is: sinds wanneer er stroom op
        # staat, wanneer hij voor het laatst iets trok, en de tellers voor
        # Bespaard. Wat hij geléérd heeft staat in de instellingen, want dat
        # moet een herstart overleven. Zie `_one_boiler`.
        self._boiler: dict[str, dict[str, Any]] = {}
        # Per airco: wie hem aanzette, wat de coach net vroeg, wat de bewoner deed (v0.119.0).
        self._airco: dict[str, dict[str, Any]] = {}
        # Wat er de afgelopen METER_VENSTER per ronde naar het net ging:
        # (moment, watt). Zie `_meter_zeker`.
        self._meter: list[tuple[datetime, float]] = []
        self._herstart_open: set[str] = set()
        self._herstart_gedaan: dict[str, datetime] = {}
        # Per laadpunt waar het proefladen staat (v0.153.0): `fase` (open,
        # bezig, pauze, klaar, gedaan, mislukt), `sinds`, `pogingen`. Zie
        # `_proef_stand` en `_async_proef_na`. En of er bij de vorige ronde een
        # kabel in zat, want alleen een kabel die erin gaat opent een proef.
        self._proef: dict[str, dict[str, Any]] = {}
        self._proef_kabel: dict[str, bool] = {}
        self._herstart_melden: set[str] = set()
        # Sinds wanneer de paal van dit laadpunt "klaar" zegt. Het ijkpunt voor
        # `_soc_bezonken`: een accustand van vóór dit moment hoort nog bij het
        # laden en zegt niets over waar de auto geëindigd is.
        self._klaar_sinds: dict[str, datetime] = {}
        # Palen zonder eigen "completed" (Alfen) die de coach klaar verklaarde.
        # Klaar blijft klaar tot de auto weer stroom neemt of de kabel eruit
        # gaat. Zie `_status_afgeleid`.
        self._afgeleid_klaar: set[str] = set()
        # De accustand zoals `_read` hem deze ronde zag, en wanneer die voor het
        # laatst veranderde. Los van de sessie, want die wordt later in de ronde
        # bijgewerkt en is hier dus een ronde te oud.
        self._soc_stand: dict[str, float | None] = {}
        self._soc_op: dict[str, datetime] = {}
        # De laatste kale meting van de accusensor, en wat de eigen meting van
        # de paal toen stond. Daarmee telt `_soc_bijgeteld` op wat er sinds die
        # meting in ging. Kaal, want de bijgetelde stand verandert elke ronde en
        # dan zou `_soc_op` nooit meer tot rust komen.
        self._soc_ruw: dict[str, float] = {}
        self._soc_ijk: dict[str, tuple[float, float]] = {}
        # Per laadpunt: de accustand van de auto, wat de paal er sindsdien in deed, en of die
        # stand vastzit (v0.176.0, `_soc_vast_bij`). Overleeft een herstart (`accustand:<id>`).
        self._soc_vast: dict[str, dict[str, Any]] = {}
        # De kleinste sprong die deze sensor liet zien: zijn resolutie.
        self._soc_stap: dict[str, float] = {}
        # Het aantal fasen zoals het deze ronde gemeten is, per laadpunt. Eén
        # meting per ronde, want `_fasen_stabiel` telt ronden.
        self._fase_nu: dict[str, int | None] = {}
        # Wat de auto deze beurt per band van tien procent aannam terwijl hij
        # zelf de rem was (v0.128.0): de som van de kW per ronde, het aantal
        # ronden, vanaf welke en tot welke accustand, en wat er het laatst van
        # bewaard is. Zie `_tempo_leren`.
        self._tempo_band: dict[str, dict[int, dict[str, Any]]] = {}
        # De ronde ervoor als die ook een remronde was, per apparaat: band, kW,
        # accustand en of hij al meetelt. Een remronde telt pas als de volgende
        # er ook een is; zie `_tempo_leren`.
        self._tempo_vorig: dict[str, tuple[int, float, float, bool]] = {}
        # De limiet van de vorige ronde en wanneer hij voor het laatst omhoog
        # ging. Zie `TEMPO_HERSTEL`.
        self._limiet_vorig: dict[str, float] = {}
        self._limiet_omhoog: dict[str, datetime] = {}
        # De banden waarvan het tempo de vorige ronde overtroffen werd. Twee
        # ronden achter elkaar voordat een tempo vervalt, net als bij het leren.
        self._weerleg_vorig: dict[str, set[int]] = {}
        self._auto_id: dict[str, str] = {}
        # De accustand van de auto aan elke paal bij de vorige ronde, voor de
        # voorrang bij zonoverschot ("auto tot 60%"). Zie `_zon_correctie`.
        self._auto_soc: dict[str, float | None] = {}
        # Het laadrendement: waar de lopende meting per paal begon (accustand,
        # eigen kWh), wat er gemeten en nog niet bewaard is, en waarmee er nu
        # gerekend wordt. Zie `_rendement_meten`.
        self._rend_start: dict[str, tuple[float, float]] = {}
        self._rend_meting: dict[str, float] = {}
        self._rend_nu: dict[str, float] = {}
        # Wat elk apparaat er de komende minuut aan ampère bij gaat nemen, en
        # onder welke zekeringen: de toezeggingen voor de voorrang bij
        # planningen (v0.93.0). Zie `_hogere_toezeggingen`.
        self._toezeggingen: dict[str, dict[str, Any]] = {}
        # Sinds wanneer er stroom wordt aangeboden zonder dat de auto iets
        # afneemt. Daarmee weet de kaart het verschil tussen "begint zo" en "de
        # auto doet niets". Een tijdstip en geen teller: een ronde is niet altijd
        # een minuut, want een statuswissel van de paal start er ook een.
        self._asking_since: dict[str, datetime] = {}
        # Laadpunten waarvan de klaar-tijd verstreken is terwijl de auto niet vol
        # was. Die laden door tot ze vol zijn, want vol worden weegt zwaarder dan
        # goedkoop laden. Vervalt zodra de auto vol is of de kabel eruit gaat.
        self._te_laat: set[str] = set()
        # Het mikpunt van voor een herstart (v0.172.0), voor de eerste ronde daarna: anders
        # ziet hij een klaar-tijd die tijdens de herstart voorbijging nooit.
        self._mikpunt_terug: dict[str, datetime] = {}
        # Wat er van een boiler of een programma in `GeheugenStore` stond, tot de sessie er is.
        self._geheugen_terug: dict[str, dict[str, Any]] = {}
        # Wat er in deze laadbeurt gebeurd is: wanneer hij begon, hoeveel er in
        # ging en waar de tijd aan op is gegaan. Alleen om het achteraf te
        # kunnen navertellen, nooit om een besluit op te nemen.
        self._sessie: dict[str, dict[str, Any]] = {}
        # Laadbeurten waarvan de kabel eruit is en waar nog een verslag over
        # hoort te komen. Staat los van `_sessie`, want die is dan al opgeruimd
        # en mag ook niet blijven staan: een nieuwe kabel is een nieuwe beurt.
        self._afscheid: dict[str, tuple[datetime, dict[str, Any]]] = {}
        # De laatste beurt waarin werkelijk geladen werd, voor de kaart zolang
        # de kabel eruit is (v0.106.0). Zie `_beurt_kaart`.
        self._vorige_beurt: dict[str, dict[str, Any]] = {}
        # Naar welke klaar-tijd een sessie op vol vermogen aan het toewerken is.
        # Zodra hij daaraan begonnen is, blijft hij dat doen tot de auto vol is
        # of de klaar-tijd verandert: terugnemen betekent alsnog te laat.
        self._deadline_for: dict[str, datetime] = {}
        # Tot wanneer de wekstroom blijft staan. Om dezelfde reden een klok: op
        # ronden geteld kon de wekpoging na drie seconden alweer voorbij zijn,
        # en daar wordt geen auto wakker van.
        self._wake_until: dict[str, datetime] = {}
        # Of de knoppen van de bewoner al teruggehaald zijn uit de opslag. Eén
        # keer per opstart, bij de eerste ronde.
        self._restored = False
        # Wanneer er voor het laatst gewaarschuwd is dat een eigen pauze de
        # klaar-tijd gaat kosten, per apparaat. Een moment en geen vinkje, want
        # deze waarschuwing komt terug zolang het risico er is; zie
        # `PAUSE_WARN_AGAIN`.
        self._warned: dict[str, datetime] = {}
        # Wie er al gewezen is op een laderlimiet die zijn laadbeurten op één
        # fase zet. Ook één keer per sessie: het is een instelling in de app van
        # de paal, en die verandert niet doordat je het twee keer zegt.
        #
        # Per apparaat de soort tip die gemeld is: "net", "fase" of "uitleg".
        # Een netmeting die zwijgt hoort niet bij een sessie maar bij een
        # stilte, en die blijft gemeld tot hij voorbij is, ook als er geen kabel
        # in zit. Zonder dat kwam "De coach kan je netmeting al ... minuten niet
        # lezen" in de klantwoning op 26 en 27-09-2026 elke minuut opnieuw, 2.540
        # keer als kritiek: de kabel was eruit, en een paal zonder kabel wiste
        # elke ronde wat er al gezegd was.
        self._getipt: dict[str, str] = {}
        # De berichtenbox (v0.130.0): wanneer er het laatst gekeken is, en hoe de
        # prijscontrole de vorige keer uitviel, voor een bericht als hij omslaat.
        self._berichten_op: datetime | None = None
        self._controle_op: datetime | None = None
        self._controle_status: str | None = None
        # Wanneer er voor het laatst om een accustand is gevraagd, per apparaat.
        # Eén melding per sessie is genoeg; vaker is zeuren en dan zet iemand de
        # meldingen uit.
        self._soc_asked: set[str] = set()
        # Tot wanneer de pauze die er staat geldig is, voor zover die een
        # houdbaarheid heeft. Nodig omdat de dode band een ongewijzigd besluit
        # niet opnieuw verstuurt: zonder deze klok zou een pauze van drie uur
        # verlopen omdat er niets veranderde, en ging de auto vanzelf laden.
        self._pause_until: dict[str, datetime] = {}
        # Draait er op dit moment een ronde? Er kan er maar één tegelijk, want
        # een ronde stuurt opdrachten en twee tegelijk zouden elkaar overschrijven.
        self._running = False
        # Gaat Home Assistant uit, dan besluit de coach niets meer. Zie `_async_bij_stop`.
        self._stopt = False
        # De statussensoren waar we op meeluisteren, en hoe we dat weer opzeggen.
        self._watched: set[str] = set()
        self._watched_phases: set[str] = set()
        self._unwatch = None
        # Vanaf welke fasestroom het haast wordt, en wanneer dat voor het laatst
        # gold. Beide worden elke ronde bijgewerkt.
        # Per stroomsensor de grens waarboven de coach meteen opnieuw kijkt:
        # de zekering van de aansluiting of van de groep waar die sensor bij hoort.
        self._urgent_above: dict[str, float] | None = None
        self._last_urgent: datetime | None = None
        # Wanneer er voor het laatst een ronde helemaal is afgelopen, en of daar
        # al over gemeld is. Dit is wat de wachthond leest.
        self._last_round: datetime | None = None
        self._warned_silent = False
        self._cancel_watchdog = None

    @callback
    def async_start(self) -> None:
        """Begin the minute-by-minute round."""
        if self._cancel is None:
            self._cancel = async_track_time_interval(self.hass, self._tick, INTERVAL)
            # Gaat Home Assistant uit, dan eerst de lopende laadbeurten naar
            # de opslag: die gaan anders elke vijf minuten en de laatste
            # minuten raken kwijt.
            self.hass.bus.async_listen_once("homeassistant_stop", self._async_bij_stop)
        if self._cancel_watchdog is None:
            self._last_round = dt_util.utcnow()
            self._cancel_watchdog = async_track_time_interval(
                self.hass, self._async_watchdog, WATCHDOG_INTERVAL
            )

    @callback
    def async_stop(self) -> None:
        """Stop, leaving the charger on whatever limit it was given.

        Deliberately nothing is sent here. A limit set with an unlimited
        time-to-live stays put, and it is always at or under what the charging
        point allows, so a coach that goes away leaves a car charging safely
        rather than at full tilt.

        Bij een boiler is het andersom, en daarom gebeurt daar wél iets: een
        boiler zonder stroom blijft koud tot iemand het merkt, en dat is onder
        de douche. Gaat de coach weg, dan gaat de stroom erop en is de
        thermostaat weer de baas, precies zoals vóór de coach.
        """
        self.hass.async_create_task(self._async_boilers_aan())
        # En een batterij gaat terug naar zijn eigen stand: op zijn laatste
        # opdracht blijven staan is leeglopen naar het net, of vol van het net.
        self.hass.async_create_task(self._async_batterijen_los())
        for opzeggen in (self._unwatch_batterij, self._cancel_regel):
            if opzeggen is not None:
                opzeggen()
        self._unwatch_batterij = self._cancel_regel = None
        self._batterij_meters = set()
        for sleutel in list(self._stekker_klok):
            self._stekker_klok_stop(sleutel)
        if self._cancel is not None:
            self._cancel()
            self._cancel = None
        if self._cancel_watchdog is not None:
            self._cancel_watchdog()
            self._cancel_watchdog = None
        if self._unwatch is not None:
            self._unwatch()
            self._unwatch = None
        self._watched = set()

    async def _async_boilers_aan(self) -> None:
        """De stroom terug op elke boiler die de coach stuurde.

        Voor het afsluiten van de integratie en voor een herstart van Home
        Assistant: wat er dan gebeurt hoort nooit een koude boiler te zijn.
        """
        try:
            settings = await async_get_store(self.hass).async_load()
        except Exception:  # noqa: BLE001 - afsluiten mag hier niet op stuklopen
            _LOGGER.exception("kon de instellingen niet lezen bij het afsluiten")
            return
        for device in settings.get("devices") or []:
            if device.get("type") != "boiler" or not device.get("controllable"):
                continue
            try:
                await self._async_boiler_zetten(device, True)
            except Exception:  # noqa: BLE001 - één apparaat is niet alle apparaten
                _LOGGER.exception("kon %s niet aanzetten bij het afsluiten", device.get("id"))

    async def _async_watchdog(self, now: datetime | None = None) -> None:
        """Kijken of de coach zelf nog draait, en het zeggen als dat niet zo is.

        Een limiet die de coach heeft weggeschreven blijft staan tot hij hem
        weghaalt. Dat is met opzet, want het is de veilige kant: valt de coach
        weg, dan laadt de auto door op een stroom die de paal eerder heeft
        aangenomen. Maar het betekent ook dat een coach die stilvalt niets
        oplevert wat je zou opvallen. Er wordt geladen, of er wordt niet
        geladen, en beide zien er normaal uit.

        Dus zegt hij het zelf. Eén melding per stilte, niet elke vijf minuten,
        en zodra hij weer loopt is de stand weer schoon.
        """
        moment = now or dt_util.utcnow()
        stil = self._last_round is None or moment - self._last_round > WATCHDOG_SILENCE

        if not stil:
            self._warned_silent = False
            return
        if self._warned_silent:
            return

        self._warned_silent = True
        minuten = (
            t("onbekend hoe lang")
            if self._last_round is None
            else t("al {n} minuten", n=int((moment - self._last_round).total_seconds() // 60))
        )
        _LOGGER.error("de coach heeft %s geen ronde afgemaakt", minuten)
        await self._async_tell(
            t(
                "De coach heeft {minuten} niets meer beslist. Wat er nu op je laadpaal staat "
                "blijft staan tot hij weer draait. Kijk in het logboek van Home Assistant wat er misging.",
                minuten=minuten,
            ),
            kritiek=True,
        )

    async def _async_berichten(self, settings: dict[str, Any], now: datetime) -> None:
        """De berichtenbox bijwerken (v0.130.0): wat de bewoner zelf moet doen.

        Elke `BERICHTEN_RONDE` de herinneringen (meterstanden, een vast contract
        dat afloopt), en elk uur of de prijscontrole is omgeslagen. Een nieuw
        bericht gaat in de box en naar de telefoon, want het laat iemand iets
        doen; de eigenaar op 06-09-2026: per beurt een verslag "plus wat de
        bewoner zelf moet oplossen". Wat er al stond (op sleutel) komt niet nog
        eens. Zie berichten.py.
        """
        if self._berichten_op is not None and now - self._berichten_op < BERICHTEN_RONDE:
            return
        self._berichten_op = now
        vandaag = now.date()
        nieuw = []
        contract = settings.get("contract") or {}
        meter = berichten.meterstand_bericht(vandaag, settings.get("reminders") or {}, contract.get("country") or "NL")
        if meter:
            nieuw.append(meter)
        nieuw.extend(berichten.contract_berichten(vandaag, contract))
        if contract.get("type") == "dynamic" and (
            self._controle_op is None or now - self._controle_op >= CONTROLE_RONDE
        ):
            self._controle_op = now
            controle = (await self.async_prijscontrole(settings, None, now)).get("controle") or {}
            omslag = berichten.controle_bericht(vandaag, self._controle_status, controle)
            if controle.get("status") in ("correct", "afwijking"):
                self._controle_status = controle.get("status")
            if omslag:
                nieuw.append(omslag)
        if not nieuw:
            return
        box = async_get_berichten(self.hass)
        for bericht in nieuw:
            entry = await box.async_add(bericht, now)
            if entry is None:
                continue
            self.hass.bus.async_fire(EVENT_BERICHTEN, {"items": await box.async_list()})
            await self._async_tell(f"{entry['title']}. {entry['body']}")

    async def _async_tell(
        self, message: str, kritiek: bool = False, telefoon: bool = True
    ) -> None:
        """Een melding sturen aan wie hem wil hebben, en in de geschiedenis zetten.

        Wie wat krijgt staat per persoon in de instellingen, zie ontvangers.py;
        sinds 06-09-2026 zet de bewoner dat zelf in het tabje Meldingen.

        `kritiek` is voor wat de bewoner zelf moet oplossen of moet weten
        voordat het misgaat: een sensor die zwijgt, een coach die stilstaat,
        een auto die niet op tijd vol raakt. In de geschiedenis is daar op te
        filteren; de eigenaar op 05-09-2026: "dat je op normale en kritieke
        meldingen kan filteren".
        """
        soort = "kritiek" if kritiek else "melding"
        # De eigenaar op 06-09-2026: per beurt één verslag plus wat kritiek is. Wat
        # daarbuiten valt komt wel in de geschiedenis, niet op de telefoon.
        if telefoon:
            await self._async_versturen(message, soort)
        # En in de geschiedenis, ook als er geen ontvanger is ingesteld: het
        # paneel toont wat er gemeld is, en een telefoon vergeet dat zodra de
        # melding weggeveegd is.
        try:
            entry = await async_get_meldingen(self.hass).async_add(message, _moment(None), soort)
            self.hass.bus.async_fire(EVENT_NOTIFICATION, entry)
        except Exception:  # noqa: BLE001 - de geschiedenis mag de melding zelf niet kosten
            _LOGGER.exception("kon de melding niet in de geschiedenis zetten")

    async def _async_versturen(self, message: str, soort: str) -> None:
        """Naar de telefoons van wie deze soort aan heeft staan."""
        try:
            settings = await async_get_store(self.hass).async_load()
        except Exception:  # noqa: BLE001 - een stille coach is erger dan een lege melding
            _LOGGER.exception("kon de instellingen niet lezen voor een melding")
            return
        for target in ontvangers(settings, soort):
            try:
                await self.hass.services.async_call(
                    "notify",
                    target,
                    {"title": "DomotiApp Coach", "message": message},
                    blocking=False,
                )
            except Exception:  # noqa: BLE001 - één slechte ontvanger is niet alle
                _LOGGER.exception("Kon melding niet versturen naar notify.%s", target)

    async def _async_noteer(
        self, message: str, now: datetime, extra: dict[str, Any] | None = None
    ) -> None:
        """Een besluit in de geschiedenis, en naar wie dat per se wil.

        Elk besluit hoort terug te lezen te zijn, maar niemand wil er 's nachts
        een telefoon van horen zoemen. Vandaar dat de soort "besluit" bij een
        nieuwe persoon uit staat; wie alles wil volgen zet hem zelf aan.
        """
        await self._async_versturen(message, "besluit")
        try:
            entry = await async_get_meldingen(self.hass).async_add(message, now, "besluit", extra)
            self.hass.bus.async_fire(EVENT_NOTIFICATION, entry)
        except Exception:  # noqa: BLE001 - de geschiedenis mag de ronde niet kosten
            _LOGGER.exception("kon het besluit niet in de geschiedenis zetten")

    async def _async_noteer_besluit(
        self, device: dict[str, Any], device_id: str, now: datetime
    ) -> None:
        """Het besluit van deze ronde in de geschiedenis, als het anders is dan
        het vorige: een andere stroom, een andere regel, aan of uit, of een
        coach die niet meer mag sturen.

        De eigenaar op 05-09-2026, toen de paal om 09:42 op zon begon te laden en het
        meldingenscherm daar niets van zei: "ik wil dat alles wat de coach
        doet terug te lezen is in meldingen."
        """
        st = self.state.get(device_id) or {}
        kern = (
            bool(st.get("charge")),
            st.get("amps"),
            st.get("rule"),
            bool(st.get("applied")),
            bool(st.get("paused")),
            bool(st.get("boost")),
        )
        if self._besluit_genoteerd.get(device_id) == kern:
            return
        self._besluit_genoteerd[device_id] = kern
        naam = device.get("name") or t("De laadpaal")
        if st.get("applied"):
            kop = t("laden op {a} A", a=st.get("amps")) if st.get("charge") else t("niet laden")
        else:
            kop = (
                t("zou laden op {a} A, maar de coach stuurt nu niet", a=st.get("amps"))
                if st.get("charge")
                else t("zou niet laden, maar de coach stuurt nu niet")
            )
        reden = (st.get("reason") or "").strip()
        await self._async_noteer(f"{naam}: {kop}. {reden}".strip(), now, {
            "device": device_id, "rule": st.get("rule"), "charge": bool(st.get("charge")),
            "amps": st.get("amps"), "applied": bool(st.get("applied")),
        })

    def _status_afgeleid(self, device_id: str, entities: dict[str, Any], now: datetime) -> str:
        """De status van een paal die er zelf geen heeft, in de woorden van Easee.

        Een Alfen meldt geen "charging" of "completed" maar twee aan/uit-
        sensoren ("auto aangesloten", "auto laadt") en de modus 3-toestand uit
        IEC 61851: A geen auto, B1 auto aangesloten zonder aanbod, B2
        aangesloten met aanbod maar de auto neemt niets, C2 aan het laden, E
        en F niet beschikbaar of storing. De rest van de coach kent alleen de
        woorden van Easee, en die worden hier gemaakt, zodat er verderop niets
        per merk hoeft te zijn.

        "Completed" zegt een Alfen nooit. Wat hij wel laat zien is een auto die
        aanbod krijgt en niets neemt (B2 met een limiet boven de ondergrens).
        Houdt dat `HERSTART_WACHT` aan, dan is dat wat "klaar" bij een Easee
        ook betekent: een auto die na een kwartier nog niets doet. Korter is
        het een auto die nog bijkomt.

        Gebouwd op 23-09-2026 en nog niet aan een echte Alfen gezien; welke
        toestand een gepauzeerde paal met een auto eraan meldt (B1 of E) staat
        niet vast en moet gemeten worden.
        """
        verbonden = _text(self.hass, entities.get("connected")).strip().lower()
        if verbonden in ("", "unknown", "unavailable", "none"):
            return ""  # niets zeggen: dan telt wat de paal het laatst wél zei
        if verbonden == "off":
            self._stil_sinds.pop(device_id, None)
            self._afgeleid_klaar.discard(device_id)
            return "disconnected"
        laadt = _text(self.hass, entities.get("charging")).strip().lower()
        modus = _text(self.hass, entities.get("mode3")).strip().upper()
        if laadt == "on" or modus.startswith(("C", "D")):
            self._stil_sinds.pop(device_id, None)
            self._afgeleid_klaar.discard(device_id)
            return "charging"
        # Klaar blijft klaar (v0.99.0). Na de 0 A van de coach staat de paal op
        # B1, "wacht op start", en tot v0.99.0 was de auto dan weer niet klaar: in
        # de eerste woning op 25-09-2026 van 06:06 tot de ochtend elke zestien
        # minuten een kwartier 13 A aanbieden en een minuut 0, voor een Tesla die
        # op zijn eigen laadgrens stond. Alleen de ene herstart (`_read`) en een
        # auto die weer stroom neemt of de kabel die eruit gaat maken het los.
        if device_id in self._afgeleid_klaar:
            return "completed"
        if modus.startswith("B1"):
            self._stil_sinds.pop(device_id, None)
            return "awaiting_start"
        limiet = _number(self.hass, entities.get("dynamic_limit"))
        if limiet is not None and limiet >= MIN_AMPS:
            sinds = self._stil_sinds.setdefault(device_id, now)
            if now - sinds >= HERSTART_WACHT:
                self._afgeleid_klaar.add(device_id)
                return "completed"
        else:
            self._stil_sinds.pop(device_id, None)
        return "ready_to_charge"

    def _sensoren(self, settings: dict[str, Any]) -> dict[str, str]:
        """Elke sensor waar de coach op rekent, met hoe de bewoner hem kent.

        De slimme meter zelf staat er niet in: die heeft zijn eigen zin op de
        kaart en zijn eigen melding (`_nettip`), na vijf minuten, want zonder
        netmeting valt de zonregel meteen weg.
        """
        uit: dict[str, str] = {}
        bronnen = settings.get("sources") or {}
        for i, zon in enumerate(zonsensoren(settings)):
            uit[zon] = t("de zonnesensor") if i == 0 else t("de zonnesensor van omvormer {n}", n=i + 1)
        for fase, velden in (bronnen.get("phases") or {}).items():
            if isinstance(velden, dict) and velden.get("current"):
                uit[velden["current"]] = t("de stroommeting van fase {fase}", fase=str(fase).upper())
        installation = settings.get("installation") or {}
        for groep in installation.get("circuits") or []:
            if not isinstance(groep, dict):
                continue
            for fase, velden in (groep.get("sensors") or {}).items():
                if isinstance(velden, dict) and velden.get("current"):
                    uit[velden["current"]] = (
                        t("de stroommeting van fase {fase} van de onderverdeelkast {naam}",
                          fase=str(fase).upper(), naam=groep.get("name") or groep.get("id"))
                        if groep.get("kind") == "kast"
                        else t("de stroommeting van fase {fase} van de groep {naam}",
                               fase=str(fase).upper(), naam=groep.get("name") or groep.get("id"))
                    )
        if installation.get("load_balancer") and installation.get("balancer_entity"):
            uit[installation["balancer_entity"]] = t("je lastbewaker")
        contract = settings.get("contract") or {}
        if contract.get("type") == "dynamic":
            dynamic = contract.get("dynamic") or {}
            if dynamic.get("source") == "all_in" and dynamic.get("all_in_entity"):
                uit[dynamic["all_in_entity"]] = t("je prijssensor")
            elif dynamic.get("market_entity"):
                uit[dynamic["market_entity"]] = t("je marktprijssensor")
            if dynamic.get("fallback_entity"):
                uit.setdefault(dynamic["fallback_entity"], t("je reserveprijssensor"))
        stekker_meldt = _altijd_aan_melden(settings)
        for device in settings.get("devices") or []:
            naam = device.get("name") or t("een apparaat")
            # Een smart plug die altijd aan moet staan heeft zijn eigen melding,
            # na twee minuten (v0.120.0). Na tien minuten nog een over zijn
            # vermogen zou twee berichten zijn over één stekker die van het net is.
            # Sinds v0.178.0 ook met die melding uit, zolang de stekker zelf niet
            # bereikbaar is: die staat dan al in de geschiedenis, en het vermogen
            # zegt niets nieuws.
            plug = _altijd_aan(device)
            if plug and not stekker_meldt and _text(self.hass, plug).strip() not in ("on", "off"):
                plug_weg = True
            else:
                plug_weg = bool(plug and stekker_meldt)
            if device.get("entity") and not plug_weg:
                uit[device["entity"]] = t("het vermogen van {naam}", naam=naam)
            entities = device.get("entities") or {}
            for sleutel, wat in (
                ("status", t("de status")),
                ("connected", t("de kabelmelding")),
                ("charging", t("de laadmelding")),
                ("limit", t("de stroomlimiet")),
                ("current", t("de stroommeting")),
                ("dynamic_limit", t("de dynamische laadgrens")),
                ("max_limit", t("de laderlimiet")),
            ):
                if entities.get(sleutel):
                    uit[entities[sleutel]] = t("{wat} van {naam}", wat=wat, naam=naam)
            # De temperatuur alleen als er een melding of een ventilator aan
            # hangt (v0.108.0): wie daarop rekent, hoort het als de sensor zwijgt.
            if _temp_nodig(settings, device):
                uit[entities["temperature"]] = t("de temperatuur van {naam}", naam=naam)
            for car in device.get("cars") or []:
                # Een auto met een wekknop slaapt als hij niet laadt en meldt
                # dan niets; dat is geen storing maar zijn aard. De eigenaar op
                # 22-09-2026: "daardoor krijg ik telkens een melding van tesla
                # meldt al 10 min niks."
                if car.get("soc_entity") and not car.get("wake_entity"):
                    uit[car["soc_entity"]] = t("de accustand van {naam}", naam=car.get("name") or t("de auto"))
        return uit

    def _slaapt(self, entity_id: str | None) -> bool:
        """Of een sensor niets zegt: er niet is, of `unknown` of `unavailable`."""
        state = self.hass.states.get(entity_id) if entity_id else None
        return state is None or state.state in ("unknown", "unavailable", "")

    async def _async_wek(self, device_id: str, profile: dict[str, Any], now: datetime) -> bool:
        """Op de wekknop van deze auto drukken, als hij er een heeft."""
        entity_id = profile.get("wake_entity")
        if not entity_id:
            return False
        domein = entity_id.split(".")[0]
        dienst = {"button": "press", "switch": "turn_on", "script": "turn_on"}.get(domein, "press")
        await self.hass.services.async_call(domein, dienst, {"entity_id": entity_id}, blocking=True)
        self._gewekt[device_id] = now
        _LOGGER.info("%s: %s gewekt om zijn accustand te horen", device_id, profile.get("name") or "de auto")
        return True

    async def _async_auto_wekken(
        self, now: datetime, settings: dict[str, Any], device: dict[str, Any], connected: bool
    ) -> None:
        """Een slapende auto wekken als de bewoner dat wil, of als de kabel er net in gaat.

        Twee redenen. Bij "elk uur" (`wake_mode` hourly): staat hij stil en
        meldt hij niets, dan hooguit eens per `WEK_INTERVAL`. En bij het
        inpluggen altijd één keer, in beide standen: zonder accustand laadt
        de coach niet blind (eis 6) en wacht hij op de bewoner, en dat is
        precies het moment waarop de auto het zelf kan zeggen.
        """
        device_id = device.get("id", "")
        zat_erin = self._kabel_erin.get(device_id, False)
        self._kabel_erin[device_id] = connected
        _chosen, profile = self._chosen_car(settings, device)
        if not profile or not profile.get("wake_entity") or not profile.get("soc_entity"):
            return
        if not self._slaapt(profile.get("soc_entity")):
            return
        laatst = self._gewekt.get(device_id)
        if connected and not zat_erin:
            if laatst is None or now - laatst >= timedelta(minutes=5):
                await self._async_wek(device_id, profile, now)
            return
        if profile.get("wake_mode") == "hourly" and (laatst is None or now - laatst >= WEK_INTERVAL):
            await self._async_wek(device_id, profile, now)

    async def async_wake(self, device_id: str) -> bool:
        """De knop op de kaart: de auto aan dit laadpunt nu wekken."""
        try:
            settings = await async_get_store(self.hass).async_load()
        except Exception:  # noqa: BLE001 - een gemiste opslag is geen reden om te stoppen
            return False
        device = next((d for d in settings.get("devices") or [] if d.get("id") == device_id), None)
        if device is None:
            return False
        _chosen, profile = self._chosen_car(settings, device)
        if not profile:
            return False
        gewekt = await self._async_wek(device_id, profile, _moment())
        if gewekt:
            self.async_refresh()
        return gewekt

    def _wekbaar(self, settings: dict[str, Any], device: dict[str, Any]) -> bool:
        """Of de auto aan dit laadpunt een wekknop heeft, voor de knop op de kaart."""
        _chosen, profile = self._chosen_car(settings, device)
        return bool(profile and profile.get("wake_entity"))

    async def _async_sensorwacht(self, settings: dict[str, Any], now: datetime) -> None:
        """Zeggen welke sensor al `SENSOR_STIL` niets zegt, en wanneer hij terug is.

        Eén melding per storing en één als hij weer doet, niet elke ronde. Wat
        de coach ondertussen doet staat per sensor al elders: zonder accustand
        telt hij door op wat hij het laatst wist (`_onthouden_soc`), zonder
        status houdt hij de laatste (`_laatste_status`), zonder prijzen wacht
        hij (`no-prices`), zonder lastbewaker rekent hij op de zekering. Dit is
        alleen de melding dat er iets stuk is, want daar kijkt niemand naar.

        Sinds v0.175.0 één melding voor alles wat tegelijk stilvalt (`SENSOR_BUNDEL`), met het
        internet als oorzaak als er twee integraties of meer bij zijn, en kritiek alleen als er een
        sensor bij zit waar de coach iets mee moet (`_sensoren_meelezen`).
        """
        zonnen = set(zonsensoren(settings))
        auto_sensoren = {
            car.get("soc_entity")
            for device in settings.get("devices") or []
            for car in device.get("cars") or []
            if car.get("soc_entity")
        }
        stil_nu: list[tuple[str, str, datetime, timedelta]] = []
        terug: list[str] = []
        for entity_id, naam in self._sensoren(settings).items():
            state = self.hass.states.get(entity_id)
            stil = state is None or state.state in ("unknown", "unavailable", "")
            if stil and entity_id in zonnen and self._zon_slaapt():
                # Een omvormer die slaapt is geen storing. De klok begint pas
                # als de zon hoog genoeg staat om hem wakker te maken.
                self._sensor_stil.pop(entity_id, None)
                continue
            sinds = self._sensor_stil.get(entity_id)
            if not stil:
                self._sensor_ooit.add(entity_id)
                if entity_id in self._sensor_gemeld:
                    self._sensor_gemeld.discard(entity_id)
                    terug.append(naam)
                self._sensor_stil.pop(entity_id, None)
                continue
            if sinds is None:
                self._sensor_stil[entity_id] = now
                continue
            if entity_id in self._sensor_gemeld:
                continue
            grens = SENSOR_STIL_AUTO if entity_id in auto_sensoren else SENSOR_STIL
            stil_nu.append((entity_id, naam, sinds, grens))

        if terug:
            namen = [f"{terug[0][0].upper()}{terug[0][1:]}", *terug[1:]]
            await self._async_tell(
                t("{naam} doet het weer.", naam=namen[0]) if len(namen) == 1
                else t("{namen} doen het weer.", namen=t("{voor} en {laatste}", voor=", ".join(namen[:-1]),
                                                         laatste=namen[-1])),
                telefoon=False,
            )
        if any(now - sinds >= grens for _e, _n, sinds, grens in stil_nu):
            bundel = [rij for rij in stil_nu if now - rij[2] >= rij[3] - SENSOR_BUNDEL]
            await self._async_sensoren_stil(settings, bundel, now)

        # Een gemelde sensor die de coach niet meer gebruikt telt niet meer.
        self._sensor_gemeld &= set(self._sensoren(settings))
        self._sensor_ooit &= set(self._sensoren(settings))
        if self._sensor_gemeld != self._sensor_gemeld_bewaard:
            try:
                saved = await async_get_store(self.hass).async_save({"sensor_quiet": [
                    {"entity": entity_id, "at": now.isoformat()} for entity_id in sorted(self._sensor_gemeld)
                ]})
                self._sensor_gemeld_bewaard = set(self._sensor_gemeld)
                self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": saved})
            except Exception:  # noqa: BLE001 - een melding onthouden is geen reden om te stoppen
                _LOGGER.exception("kon niet bewaren welke sensoren al gemeld zijn")

    async def _async_sensoren_stil(
        self, settings: dict[str, Any], bundel: list[tuple[str, str, datetime, timedelta]], now: datetime
    ) -> None:
        """Eén melding voor de sensoren die samen stilvielen (v0.175.0)."""
        temperaturen = {
            device["entities"]["temperature"]
            for device in settings.get("devices") or []
            if _temp_nodig(settings, device)
        }
        meelezen = self._sensoren_meelezen(settings)
        entries: set[str] = set()
        try:
            from homeassistant.helpers import entity_registry as er

            register = er.async_get(self.hass)
            for entity_id, _naam, _sinds, _grens in bundel:
                # Alleen wat het eerst deed (v0.178.0): een sensor die nog nooit iets zei, zoals
                # een stekker die net is toegevoegd en nog niet aan het net hangt, zegt niets over
                # het internet. Bij een klant op 29-10-2026 heette vijf nieuwe stekkers zo "het internet".
                if entity_id not in self._sensor_ooit:
                    continue
                rij = register.async_get(entity_id)
                entry_id = getattr(rij, "config_entry_id", None) if rij is not None else None
                if entry_id:
                    entries.add(entry_id)
        except Exception:  # noqa: BLE001 - zonder register noemt de melding de integratie
            _LOGGER.debug("kon de integraties van de stille sensoren niet opzoeken", exc_info=True)
        minuten = min(int(_tussen(sinds, now).total_seconds() // 60) for _e, _n, sinds, _g in bundel)
        for entity_id, _naam, sinds, _grens in bundel:
            self._sensor_gemeld.add(entity_id)
            # De entiteit-id staat in het log en niet in de melding. De eigenaar op
            # 21-09-2026, over precies deze zin: "meld zo'n sensor niet
            # volledig, zeg gewoon dat er iets mis is met de integratie". Wie
            # hem moet opzoeken kijkt in het log; wie hem leest heeft genoeg aan
            # de naam die hij zelf heeft ingevuld.
            # Alleen de id (v0.141.1): het log blijft Nederlands, en de naam ging door
            # `t()`, dus in het Engels kwam er "the temperature of ..." midden in.
            _LOGGER.warning("%s meldt al %d minuten niets", entity_id,
                            int(_tussen(sinds, now).total_seconds() // 60))
        if len(entries) >= 2:
            _LOGGER.warning("%d sensoren van %d integraties tegelijk stil; waarschijnlijk het internet",
                            len(bundel), len(entries))
        # Kritiek alleen als de coach er iets mee moet. Een status die hij alleen
        # meeleest laat hem niets anders doen, en de bewoner kan er niets mee.
        kritiek = any(entity_id not in meelezen for entity_id, _n, _s, _g in bundel)
        ids = [entity_id for entity_id, _n, _s, _g in bundel]
        namen = [naam for _e, naam, _s, _g in bundel]
        namen[0] = f"{namen[0][0].upper()}{namen[0][1:]}"
        if len(bundel) == 1:
            entity_id = ids[0]
            # Valt de reserveprijsbron in, dan rekent de coach niet zonder maar
            # daarmee (v0.101.3).
            zolang = t("De coach rekent zolang zonder.")
            if self._reserve_valt_in(settings, entity_id):
                zolang = t("De coach rekent zolang met je reserveprijzen.")
            # Met de temperatuur rekent de coach niet; die is er voor de
            # melding en de ventilator.
            if entity_id in temperaturen:
                zolang = t("Zolang weet de coach niet of hij te warm wordt.")
            if entity_id in meelezen:
                zolang = ""
            tekst = t(
                "{naam} meldt al {minuten} minuten niets. Waarschijnlijk hapert de integratie erachter. {zolang}",
                naam=namen[0], minuten=minuten, zolang=zolang,
            ).strip()
        else:
            delen = [
                t("{namen} melden al {minuten} minuten niets.",
                  namen=t("{voor} en {laatste}", voor=", ".join(namen[:-1]), laatste=namen[-1]), minuten=minuten),
                t("Waarschijnlijk is het internet thuis weg.") if len(entries) >= 2
                else t("Waarschijnlijk hapert de integratie erachter."),
            ]
            if any(self._reserve_valt_in(settings, e) for e in ids):
                delen.append(t("De coach rekent zolang met je reserveprijzen."))
            if any(e in temperaturen for e in ids):
                delen.append(t("Zolang weet de coach niet of het ergens te warm wordt."))
            if any(e not in temperaturen and e not in meelezen and not self._reserve_valt_in(settings, e)
                   for e in ids):
                delen.append(t("De coach rekent zolang zonder."))
            tekst = " ".join(delen)
        await self._async_tell(tekst, kritiek=kritiek)

    @staticmethod
    def _sensoren_meelezen(settings: dict[str, Any]) -> set[str]:
        """De sensoren van een apparaat dat de coach alleen uitleest (v0.175.0).

        Een wasmachine of droger zonder "mag sturen", en een batterij die hij alleen leest: de coach
        doet er niets mee, dus een sensor die zwijgt is geen kritieke melding. De temperatuur van zo'n
        apparaat telt wel, als er een melding of een ventilator aan hangt (`_temp_nodig`).
        """
        uit: set[str] = set()
        for device in settings.get("devices") or []:
            alleen = (
                (device.get("type") in PROGRAMMA_TYPES and _programma_alleen_lezen(device))
                or (device.get("type") == "thuisbatterij" and device.get("brand") in BATTERIJ_ALLEEN_LEZEN)
            )
            if not alleen:
                continue
            entities = device.get("entities") or {}
            if device.get("entity"):
                uit.add(device["entity"])
            for sleutel, waarde in entities.items():
                if isinstance(waarde, str) and waarde and not (
                    sleutel == "temperature" and _temp_nodig(settings, device)
                ):
                    uit.add(waarde)
        return uit

    @staticmethod
    def _eigen_entiteiten(settings: dict[str, Any]) -> set[str]:
        """Elke entiteit die de bewoner in de coach invulde: bij de apparaten, de bronnen, de installatie
        en het contract (v0.166.0)."""
        uit: set[str] = set()

        def loop(waarde: Any) -> None:
            if isinstance(waarde, str):
                if _ENTITEIT_ID.match(waarde):
                    uit.add(waarde)
            elif isinstance(waarde, dict):
                for v in waarde.values():
                    loop(v)
            elif isinstance(waarde, (list, tuple)):
                for v in waarde:
                    loop(v)

        for sleutel in ("devices", "sources", "installation", "contract"):
            loop(settings.get(sleutel))
        return uit

    def _inloggen_gevraagd(self) -> set[str]:
        """De integraties waarvoor Home Assistant om opnieuw inloggen vraagt: een lopende reauth (v0.176.0).

        Gemeten in een klantwoning op 28-10-2026: de integratie zelf kan daarbij op `loaded` blijven
        staan (een auto) of op `setup_error` (een vaatwasser, met een token die niet meer geldt).
        """
        try:
            flows = self.hass.config_entries.flow.async_progress()
        except Exception:  # noqa: BLE001 - zonder flows geen melding
            return set()
        uit: set[str] = set()
        for flow in flows or []:
            context = (flow.get("context") if isinstance(flow, dict) else None) or {}
            if context.get("source") == "reauth" and context.get("entry_id"):
                uit.add(str(context["entry_id"]))
        return uit

    async def _async_integraties(self, settings: dict[str, Any], now: datetime) -> None:
        """Een integratie achter de entiteiten van de coach die niet opkwam: herladen (v0.166.0).

        Elk kwartier, en het eerste kwartier na de start niet: dan zet Home Assistant zelf nog alles
        neer. Alleen `setup_error`, en `not_loaded` als de gebruiker hem niet uitzette. Een geladen
        integratie raakt de coach nooit aan, en `setup_retry` ook niet: dat doet Home Assistant zelf.
        Lukt het na `INTEGRATIE_MELDEN` nog niet, dan één melding; lukt het, dan "doet het weer".
        """
        if self._integratie_om is None:
            self._integratie_om = now + INTEGRATIE_CONTROLE
            return
        if now < self._integratie_om:
            return
        self._integratie_om = now + INTEGRATIE_CONTROLE
        try:
            from homeassistant.helpers import entity_registry as er

            register = er.async_get(self.hass)
            entries: list[str] = []
            for entity_id in sorted(self._eigen_entiteiten(settings)):
                rij = register.async_get(entity_id)
                entry_id = getattr(rij, "config_entry_id", None) if rij is not None else None
                if entry_id and entry_id not in entries:
                    entries.append(entry_id)
        except Exception:  # noqa: BLE001 - zonder register geen controle
            _LOGGER.debug("kon de integraties niet nakijken", exc_info=True)
            return
        inloggen = self._inloggen_gevraagd()
        for entry_id in entries:
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is None or entry.domain == DOMAIN:
                continue
            naam = entry.title or entry.domain
            stand = str(getattr(entry.state, "value", entry.state))
            # Vraagt hij om opnieuw inloggen (v0.176.0), dan helpt herladen niet: dat moet de
            # bewoner doen. Eén melding, ook als de integratie op loaded blijft staan.
            if entry_id in inloggen:
                if entry_id not in self._integratie_inloggen:
                    self._integratie_inloggen.add(entry_id)
                    _LOGGER.warning("de integratie %s (%s) vraagt om opnieuw in te loggen", naam, entry.domain)
                    await self._async_tell(
                        t("De integratie {naam} vraagt om opnieuw in te loggen. Doe dat in Home Assistant bij "
                          "Instellingen, Apparaten en diensten.", naam=naam),
                        kritiek=True,
                    )
                continue
            if entry_id in self._integratie_inloggen:
                self._integratie_inloggen.discard(entry_id)
                if stand == "loaded" and entry_id not in self._integratie_stuk:
                    _LOGGER.warning("de integratie %s is weer ingelogd", naam)
                    await self._async_tell(t("De integratie {naam} doet het weer.", naam=naam), telefoon=False)
            if stand not in INTEGRATIE_HERLADEN or getattr(entry, "disabled_by", None):
                if stand == "loaded" and entry_id in self._integratie_stuk:
                    self._integratie_stuk.pop(entry_id, None)
                    self._integratie_gemeld.discard(entry_id)
                    await self._async_tell(t("De integratie {naam} doet het weer.", naam=naam), telefoon=False)
                continue
            sinds = self._integratie_stuk.setdefault(entry_id, now)
            _LOGGER.warning("de integratie %s (%s) staat op %s; de coach herlaadt hem", naam, entry.domain, stand)
            try:
                async with asyncio.timeout(INTEGRATIE_WACHT.total_seconds()):
                    await self.hass.config_entries.async_reload(entry_id)
            except Exception as err:  # noqa: BLE001 - het internet kan er nog niet zijn
                _LOGGER.warning("de integratie %s herladen lukte niet: %s", naam, err)
            stand = str(getattr(entry.state, "value", entry.state))
            if stand == "loaded":
                self._integratie_stuk.pop(entry_id, None)
                self._integratie_gemeld.discard(entry_id)
                _LOGGER.warning("de integratie %s is herladen en doet het weer", naam)
                await self._async_tell(t("De integratie {naam} doet het weer.", naam=naam), telefoon=False)
            elif entry_id not in self._integratie_gemeld and now - sinds >= INTEGRATIE_MELDEN:
                self._integratie_gemeld.add(entry_id)
                await self._async_tell(
                    t("De integratie {naam} komt niet op. Herlaad hem in Home Assistant, of kijk of het internet "
                      "het doet.", naam=naam),
                    kritiek=True,
                )

    async def _async_reserveverloop(
        self, dynamic: dict[str, Any], van: datetime, tot: datetime
    ) -> list[tuple[datetime, float]]:
        """Het all-in prijsverloop van de reserveprijsbron, als de eigen niets had."""
        reserve = dynamic.get("fallback_entity")
        if not reserve:
            return []
        uit: list[tuple[datetime, float]] = []
        for moment, toestand in await self._async_geschiedenis(reserve, van, tot):
            try:
                prijs = float(toestand)
            except ValueError:
                continue
            if dynamic.get("fallback_source") != "all_in":
                prijs = self._all_in(prijs, dynamic)
            uit.append((moment, prijs))
        return uit

    def _reserve_valt_in(self, settings: dict[str, Any], entity_id: str) -> bool:
        """Of deze sensor de eigen prijsbron is en de reserve het nu overneemt."""
        contract = settings.get("contract") or {}
        if contract.get("type") != "dynamic":
            return False
        dynamic = contract.get("dynamic") or {}
        eigen = dynamic.get("all_in_entity") if dynamic.get("source") == "all_in" else dynamic.get("market_entity")
        return entity_id == eigen and self._prijsbron(dynamic)[1]

    def _prijzen_voor_paneel(self, settings: dict[str, Any]) -> dict[str, Any]:
        """De prijslijst waar de coach mee rekent, voor het paneel (v0.101.3).

        Het paneel leest een prijslijst zelf uit de attributen van de sensor.
        Van de ingebouwde Nord Pool staat daar niets, en valt de reserve in, dan
        hoort het paneel dezelfde prijzen te tekenen als de coach gebruikt.
        """
        contract = settings.get("contract") or {}
        # Of de bewoner de opbouw bevestigde (v0.129.0): het overzicht vraagt
        # het anders tot hij dat doet.
        bevestigd = (contract.get("confirmed") or {}).get("values") == prijsopbouw.vingerafdruk(contract)
        if contract.get("country") == "PT":
            # Portugal (v0.137.0): de tijdvakken als prijslijst, zodat de grafiek en de
            # vooruitblik dezelfde prijzen tekenen als de coach gebruikt.
            return {"reserve": False, "bevestigd": bevestigd, "rows": [
                {"start": rij["start"].isoformat(), "end": rij["end"].isoformat(),
                 "price": rij["price"], "feed_in": rij["feed_in"]}
                for rij in self._prices(settings)
            ]}
        if contract.get("type") != "dynamic":
            return {"reserve": False, "rows": [], "bevestigd": bevestigd}
        _, reserve = self._prijsbron(contract.get("dynamic") or {})
        return {
            "bevestigd": bevestigd,
            "reserve": reserve,
            "rows": [
                {"start": rij["start"].isoformat(), "end": rij["end"].isoformat(),
                 "price": rij["price"], "feed_in": rij["feed_in"]}
                for rij in self._prices(settings)
            ],
        }

    async def async_prijscontrole(
        self, settings: dict[str, Any], contract: dict[str, Any] | None = None, now: datetime | None = None
    ) -> dict[str, Any]:
        """De opbouw van de stroomprijs van nu, en of die klopt met de all-in sensor (v0.129.0).

        Voor Contract en Voorkeuren in het paneel: dat toont dit in woorden en
        cijfers, en rekent zelf niets. `contract` is een concept dat nog niet is
        opgeslagen; zonder is het het opgeslagen contract. Zie prijsopbouw.py.
        """
        moment = _moment(now)
        contract = contract if contract is not None else (settings.get("contract") or {})
        bevestigd = contract.get("confirmed") or {}
        uit: dict[str, Any] = {
            "soort": contract.get("type") or "fixed",
            "salderen": self._salderen(contract, now),
            # Levert het huis over het jaar meer terug dan het afneemt (v0.133.3)?
            # Dan is een teruggeleverde kWh de vergoeding waard, ook met salderen.
            "netto_terug": self._netto_terug(),
            # Hoe de leverancier terugleverkosten rekent (v0.135.0), voor de opbouw.
            "kosten_vorm": ((contract.get("dynamic") if contract.get("type") == "dynamic" else contract.get("fixed")) or {}
                            ).get("feed_in_costs_mode") or "kwh",
            "jaar": dict(self._jaarsaldo) if self._jaarsaldo else None,
            # De schaal die eraan komt, met en zonder thuisbatterij (v0.137.0).
            "schaal": dict(self._schaal) if self._schaal else None,
            "bevestigd": bool(bevestigd.get("values"))
            and bevestigd.get("values") == prijsopbouw.vingerafdruk(contract),
            "bevestigd_op": bevestigd.get("at") or None,
            "bevestigd_door": bevestigd.get("by") or None,
        }
        if contract.get("country") == "PT":
            pt = contract.get("pt") or {}
            moment = _bewust(now)
            nu = tarifas.periodo(moment, pt.get("tarifa"), pt.get("ciclo"))
            rijen = self._pt_rijen(contract, now)
            terug_nu = rijen[0]["feed_in"] if rijen else tarifas.terug(pt)
            uit.update(
                soort="pt", salderen=False, inkoop=tarifas.preco(pt, nu), terug=terug_nu,
                pt={"tarifa": pt.get("tarifa") or "bi", "ciclo": pt.get("ciclo") or "diario",
                    "fornecedor": pt.get("fornecedor") or "", "nu": nu, "periodos": tarifas.opbouw(pt),
                    "excedente": (pt.get("excedente") or {}).get("modo") or "onbekend",
                    "kva": pt.get("kva"), "potencia_dia": pt.get("potencia_dia"), "servicos_mes": pt.get("servicos_mes")},
                controle={"status": "vast"},
            )
            return uit
        if contract.get("type") != "dynamic":
            vast = self._tarief({"contract": contract}, now)
            vergoeding, kosten = self._teruglevering(contract.get("fixed") or {}, now)
            uit.update(inkoop=vast.buy, terug=vast.feed_in, vergoeding=vergoeding, kosten=kosten,
                       controle={"status": "vast"})
            # Wat er na salderen geldt, als het contract dan nog loopt (v0.134.0).
            if moment.date() < NETTING_ENDS and (contract.get("end") or "9999-12-31") >= NETTING_ENDS.isoformat():
                v2, k2 = self._teruglevering(contract.get("fixed") or {}, datetime.combine(NETTING_ENDS, time(0)))
                uit["na_salderen"] = {"vanaf": NETTING_ENDS.isoformat(), "vergoeding": v2, "kosten": k2,
                                      "terug": round(v2 - k2, 6)}
            return uit

        d = contract.get("dynamic") or {}
        await self._async_nordpool({"contract": contract}, moment, opruimen=False)
        interval = str(d.get("interval") or "hour")
        all_in_id = d.get("all_in_entity") if d.get("source") == "all_in" else ""
        markt_id = d.get("market_entity") or ""
        zelfde = bool(all_in_id) and markt_id == all_in_id
        all_in = self._slots(all_in_id, interval) if all_in_id else {}
        markt = {} if zelfde else self._slots(markt_id, interval)
        controle = prijsopbouw.controleer(all_in, markt, d, moment)

        # Het blok van nu: dat van de controle, en anders dat van de sensor die er is.
        blok = controle.get("blok")
        if blok is None:
            bron = all_in or markt
            nu = next(((s, e) for s, (e, _) in bron.items() if s <= moment < e), None)
            if nu is not None:
                blok = {"start": nu[0], "einde": nu[1],
                        "all_in": prijsopbouw.gemiddeld(all_in, *nu) if all_in else None,
                        "markt": prijsopbouw.gemiddeld(markt, *nu) if markt else None}
        opbouw = terug = None
        dag = False
        if blok is not None:
            zone = dt_util.get_default_time_zone()
            dag = prijsopbouw.overdag(
                blok["start"].replace(tzinfo=zone), blok["einde"].replace(tzinfo=zone),
                getattr(self.hass.config, "latitude", None), getattr(self.hass.config, "longitude", None),
            )
            if blok.get("markt") is not None:
                opbouw = prijsopbouw.inkoop(blok["markt"], d)
            prijs = blok.get("all_in") if all_in_id else (opbouw or {}).get("totaal")
            terug = prijsopbouw.terug(blok.get("markt"), prijs, d, self._saldeert(contract, now), dag)

        def tijd(waarde):
            return waarde.isoformat() if isinstance(waarde, datetime) else waarde

        uit.update(
            bron={"all_in": all_in_id or None, "markt": None if zelfde else (markt_id or None),
                  "zelfde": zelfde, "interval": interval,
                  "markt_minuten": int(prijsopbouw.lengte(markt).total_seconds() // 60) if markt else None},
            bonus_procent=float(d.get("feed_in_bonus_percent") or 0),
            bonus_overdag=bool(d.get("bonus_daytime")),
            blok=None if blok is None else {k: tijd(v) for k, v in blok.items()},
            inkoop=opbouw,
            all_in=None if blok is None else blok.get("all_in"),
            terug=terug,
            overdag=dag,
            controle={k: (tijd(v) if not isinstance(v, dict) else {a: tijd(b) for a, b in v.items()})
                      for k, v in controle.items()},
        )
        return uit

    def _zon_w(self, settings: dict[str, Any]) -> float | None:
        """Wat alle omvormers samen nu geven, of None zolang er een niets zegt.

        Eén omvormer die zwijgt maakt de som onbekend, niet kleiner: wie de
        zonverwachting bijstelt op een halve meting rekent het dak naar beneden
        voor iets dat er wel was.
        """
        waarden = [_watts(self.hass, zon) for zon in zonsensoren(settings)]
        if not waarden or any(w is None for w in waarden):
            return None
        return sum(waarden)

    async def _async_temperatuurwacht(
        self, settings: dict[str, Any], now: datetime, level: str
    ) -> None:
        """Wat de coach doet met de temperatuur van een thuisbatterij (v0.108.0).

        Twee dingen, allebei alleen voor een batterij met een temperatuursensor
        (`temperature`). Een sensor die niets zegt verandert hier niets; dat
        meldt `_async_sensorwacht`.

        1. **Een bericht als hij te warm wordt.** De eigenaar op 10-10-2026: "ook
           wil ik een melding kunnen laten sturen wanneer de temperatuur te hoog
           is en dat je zelf een doel kan instellen zoals boven x dan melding."
           De grens staat in Meldingen (`temp_alert`) en geldt voor elke
           batterij. Eén bericht per keer dat hij erboven komt, pas als hij er
           `TEMP_AANHOUDEND` boven blijft. Weer gewoon is hij `TEMP_TERUG`
           graden onder de grens, en dat gaat alleen in de geschiedenis.
        2. **Een ventilator**, zie `_async_ventilator`.
        """
        grens = _temp_grens(settings)
        if grens is None:
            self._temp_boven.clear()
            self._temp_gemeld.clear()
        for device in settings.get("devices") or []:
            entity_id = (device.get("entities") or {}).get("temperature")
            if device.get("type") != "thuisbatterij" or not entity_id:
                continue
            sleutel = device.get("id") or entity_id
            temp = _celsius(self.hass, entity_id)
            if temp is None:
                continue
            naam = device.get("name") or t("de thuisbatterij")
            await self._async_ventilator(device, naam, temp, level)
            if grens is None:
                continue
            if temp > grens:
                sinds = self._temp_boven.setdefault(sleutel, now)
                if sleutel not in self._temp_gemeld and now - sinds >= TEMP_AANHOUDEND:
                    self._temp_gemeld.add(sleutel)
                    await self._async_tell(
                        t("De temperatuur van {naam} is {temp}, boven je grens van {grens}.",
                          naam=naam, temp=_graden(temp), grens=_graden(grens)),
                        kritiek=True,
                    )
                continue
            self._temp_boven.pop(sleutel, None)
            if sleutel in self._temp_gemeld and temp <= grens - TEMP_TERUG:
                self._temp_gemeld.discard(sleutel)
                await self._async_tell(
                    t("De temperatuur van {naam} is weer {temp}.", naam=naam, temp=_graden(temp)), telefoon=False
                )

    def _vriezer_temp(self, entity_id: str | None) -> float | None:
        """De temperatuur van een vriezer: een sensor, of de climate van de vriezer zelf."""
        if entity_id and entity_id.startswith("climate."):
            state = self.hass.states.get(entity_id)
            try:
                return float((getattr(state, "attributes", None) or {}).get("current_temperature"))
            except (TypeError, ValueError):
                return None
        return _celsius(self.hass, entity_id)

    async def _async_vriezerwacht(self, settings: dict[str, Any], now: datetime) -> None:
        """De vriezer in de gaten houden en melden (v0.125.0).

        De eigenaar op 15-10-2026 over de vriezer: "Uitlezen en melden", niet
        sturen, met drie meldingen: de deur die te lang openstaat (na
        `VRIEZER_DEUR`), de temperatuur die oploopt (een half uur warmer dan
        `VRIEZER_GRENS_C`), en een storing die de vriezer zelf meldt. Elk één
        keer, kritiek, want dat moet de bewoner oplossen; weer goed staat
        alleen in de geschiedenis. Een sensor die niets zegt verandert hier
        niets; dat meldt `_async_sensorwacht`.

        Sinds v0.131.0 ook de koelkast, met zijn eigen grens (`KOELWAREN`).
        """
        actief: set[tuple[str, str]] = set()
        for device in settings.get("devices") or []:
            if device.get("type") not in KOELWAREN:
                continue
            standaard, grens = KOELWAREN[device["type"]]
            standaard = t(standaard)
            entities = device.get("entities") or {}
            sleutel = str(device.get("id") or "")
            eigen = str(device.get("name") or "").strip()
            naam = (eigen[0].upper() + eigen[1:]) if eigen else standaard[0].upper() + standaard[1:]
            van = eigen or standaard

            deur = _text(self.hass, entities.get("door")).strip().lower()
            if deur in ("on", "open", "off", "closed"):
                await self._vriezer_stand(
                    (sleutel, "deur"), deur in ("on", "open"), now, VRIEZER_DEUR, actief,
                    t("De deur van {naam} staat al {n} minuten open.",
                      naam=van, n=int(VRIEZER_DEUR.total_seconds() // 60)),
                    t("De deur van {naam} is weer dicht.", naam=van),
                )
            temp = self._vriezer_temp(entities.get("temperature"))
            # Miele komt na een storing in de cloud terug met 0,0 en pas na zo'n twintig
            # seconden met de echte temperatuur (een klantwoning, 21-10-2026: vriezer en
            # koelkast om 16:29:53 UTC 0,0 en om 16:30:15 weer -18 en 5). Vlak na niets is
            # 0,0 dus een plaatshouder en geen meting.
            if temp is None:
                self._koel_weg[sleutel] = now
            elif temp == 0.0 and sleutel in self._koel_weg and _tussen(self._koel_weg[sleutel], now) <= KOEL_NUL:
                temp = None
            else:
                self._koel_weg.pop(sleutel, None)
            if temp is not None:
                warm = temp > grens
                koud = temp <= grens - TEMP_TERUG
                if warm or koud:
                    await self._vriezer_stand(
                        (sleutel, "warm"), warm, now, VRIEZER_WARM, actief,
                        t("{naam} is al een half uur warmer dan {grens}: nu {temp}.",
                          naam=naam, grens=_graden(grens), temp=_graden(temp)),
                        t("{naam} is weer {temp}.", naam=naam, temp=_graden(temp)),
                    )
                elif (sleutel, "warm") in self._vriezer_sinds or (sleutel, "warm") in self._vriezer_gemeld:
                    # Tussen de grens en een graad eronder blijft het zoals het was.
                    actief.add((sleutel, "warm"))
            storing = _text(self.hass, entities.get("problem")).strip().lower()
            if storing in ("on", "off"):
                await self._vriezer_stand(
                    (sleutel, "storing"), storing == "on", now, timedelta(0), actief,
                    t("{naam} meldt een storing.", naam=naam),
                    t("{naam} meldt geen storing meer.", naam=naam),
                )
        # Een vriezer die er niet meer is, of een sensor die verdween: vergeten.
        for weg in set(self._vriezer_sinds) - actief:
            self._vriezer_sinds.pop(weg, None)
        self._vriezer_gemeld &= actief

    async def _vriezer_stand(
        self, sleutel: tuple[str, str], mis: bool, now: datetime, wacht: timedelta,
        actief: set[tuple[str, str]], melding: str, terug: str,
    ) -> None:
        """Eén ding van een vriezer: `mis` sinds wanneer, één melding na `wacht`, en terug."""
        actief.add(sleutel)
        if mis:
            sinds = self._vriezer_sinds.setdefault(sleutel, now)
            if sleutel not in self._vriezer_gemeld and now - sinds >= wacht:
                self._vriezer_gemeld.add(sleutel)
                await self._async_tell(melding, kritiek=True)
            return
        self._vriezer_sinds.pop(sleutel, None)
        if sleutel in self._vriezer_gemeld:
            self._vriezer_gemeld.discard(sleutel)
            await self._async_tell(terug, telefoon=False)

    async def _async_ventilator(
        self, device: dict[str, Any], naam: str, temp: float, level: str
    ) -> None:
        """De ventilator bij de batterij aan boven zijn grens, en een graad eronder uit.

        De eigenaar op 10-10-2026: "ik wil de mogelijkheid om een smart plug in te
        schakelen om een ventilator aan te sturen als de batterij te heet wordt."
        De plug staat bij de batterij (`fan`), de grens ook (`fan_above_c`); leeg
        is nooit. Ertussen blijft hij staan zoals hij staat, zodat een
        temperatuur op de grens hem niet elke minuut aan en uit zet.

        Niet bij Alleen uitlezen en Adviseren: daar belooft de coach dat hij
        niets aanraakt. Wel bij Voorstellen, want wie een plug en een grens
        invult heeft daarmee ja gezegd. Elke keer dat hij schakelt staat in de
        geschiedenis, niet op de telefoon.
        """
        plug = (device.get("entities") or {}).get("fan")
        try:
            aan_boven = float((device.get("battery") or {}).get("fan_above_c"))
        except (TypeError, ValueError):
            return
        if not plug or level in (LEVEL_READ, LEVEL_ADVISE):
            return
        if temp > aan_boven:
            aan = True
        elif temp <= aan_boven - TEMP_TERUG:
            aan = False
        else:
            return
        # Een plug die niets zegt laat de coach met rust: aan of uit weet hij dan niet.
        if _text(self.hass, plug) != ("off" if aan else "on"):
            return
        if not await self._async_schakelen(device, aan, "fan"):
            return
        await self._async_tell(
            t("De ventilator van {naam} staat aan: {temp}.", naam=naam, temp=_graden(temp))
            if aan
            else t("De ventilator van {naam} staat uit: {temp}.", naam=naam, temp=_graden(temp)),
            telefoon=False,
        )

    async def _async_altijd_aan(
        self, settings: dict[str, Any], now: datetime, level: str
    ) -> None:
        """Een smart plug die altijd aan moet staan weer aanzetten (v0.120.0).

        De eigenaar op 15-10-2026: "een belangrijke optie, dit apparaat moet
        altijd aan staan. Als die aan staat moet de coach dat blijven
        controleren en als die door wat voor een reden dan uit gegaan is moet
        de coach hem weer aan zetten. Lukt dat niet wil ik na 2 min een melding
        ontvangen. Pas de melding sturen als je dat hebt ingesteld in meldingen."

        Staat de schakelaar uit, dan zet de coach hem aan, en elke ronde
        opnieuw zolang dat niet lukt. De schakelaar wekt de coach zelf
        (`_watch`), dus dat is binnen een seconde en niet pas bij de volgende
        minuut. Staat hij na `ALTIJD_AAN_WACHT` nog niet aan, dan één melding,
        als kritiek: naar de telefoon alleen als `always_on_alert` aan staat,
        in de geschiedenis altijd. Een stekker die niets zegt is van het
        netwerk af; die kan de coach niet aanzetten, en dat zegt de melding.

        Niet bij Alleen uitlezen en Adviseren, net als de ventilator: daar
        belooft de coach dat hij niets aanraakt. De melding komt dan wel. Dat
        hij hem weer aankreeg, en dat hij het weer doet, staat alleen in de
        geschiedenis.
        """
        telefoon = _altijd_aan_melden(settings)
        mag = level not in (LEVEL_READ, LEVEL_ADVISE)
        gezien: set[str] = set()
        # Wat er deze ronde over de wachttijd gaat, of al een minuut weg is: (sleutel, naam
        # vooraan, naam verderop, sinds, soort). Soort: "weg" (niet bereikbaar), "nieuw" (nog
        # nooit bereikbaar), "uit".
        kandidaten: list[tuple[str, str, str, datetime, str]] = []
        # Per stekker, in de volgorde van de instellingen: hoe hij vooraan en verderop heet.
        namen: dict[str, tuple[str, str]] = {}
        for device in settings.get("devices") or []:
            plug = _altijd_aan(device)
            if not plug:
                continue
            sleutel = str(device.get("id") or plug)
            gezien.add(sleutel)
            naam = _stekker_naam(device)
            # Verderop in een opsomming "de vriezer", maar een eigen naam blijft zoals hij is.
            verder = naam if str(device.get("name") or "").strip() else naam[0].lower() + naam[1:]
            namen[sleutel] = (naam, verder)
            stand = _text(self.hass, plug).strip()
            if stand != "on" and sleutel in self._stekker_terug:
                # Terug en meteen weer weg: dan was hij niet terug, en blijft hij gemeld.
                self._stekker_terug.pop(sleutel)
                self._stekker_gemeld.add(sleutel)
            if stand in ("on", "off") and sleutel not in self._stekker_ooit:
                # Voor het eerst bereikbaar: wat er tot nu toe gemeld was, was "nog niet
                # bereikbaar", en de klok voor "staat uit" begint nu pas.
                self._stekker_ooit.add(sleutel)
                if sleutel in self._stekker_nieuw:
                    self._stekker_nieuw.discard(sleutel)
                    await self._async_tell(t("{naam} is nu bereikbaar.", naam=naam), telefoon=False)
                if stand == "off":
                    self._stekker_uit[sleutel] = now
                    self._stekker_klok_stop(sleutel)
            if stand == "on":
                self._stekker_uit.pop(sleutel, None)
                self._stekker_klok_stop(sleutel)
                if sleutel in self._stekker_gemeld:
                    self._stekker_gemeld.discard(sleutel)
                    self._stekker_terug.setdefault(sleutel, now)
                elif sleutel in self._stekker_gezet:
                    await self._async_tell(
                        t("{naam} stond uit; de coach heeft hem weer aangezet.", naam=naam), telefoon=False
                    )
                self._stekker_gezet.discard(sleutel)
                continue
            if sleutel not in self._stekker_uit:
                # Uit telt vanaf nu, want de wachttijd is hoe lang de coach het al probeert.
                # Niet bereikbaar telt vanaf het wegvallen zelf (v0.183.0).
                self._stekker_uit[sleutel] = now if stand == "off" else self._stekker_weg_sinds(plug, now)
            if sleutel not in self._stekker_klok and now - self._stekker_uit[sleutel] < ALTIJD_AAN_WACHT:
                # De ronde loopt eens per minuut; deze klok kijkt precies als
                # de wachttijd om is, zodat de melding na twee minuten komt en
                # niet na bijna drie.
                wacht = ALTIJD_AAN_WACHT - (now - self._stekker_uit[sleutel])
                self._stekker_klok[sleutel] = async_call_later(
                    self.hass, wacht.total_seconds() + 1, self._stekker_klok_af
                )
            sinds = self._stekker_uit[sleutel]
            if stand == "off" and mag and await self._async_schakelen(device, True, "switch"):
                self._stekker_gezet.add(sleutel)
            nooit = sleutel not in self._stekker_ooit
            if sleutel in self._stekker_gemeld or (nooit and sleutel in self._stekker_nieuw):
                continue
            soort = "uit" if stand == "off" else ("nieuw" if nooit else "weg")
            kandidaten.append((sleutel, naam, verder, sinds, soort))
            # De entiteit-id in het log en niet in de melding, zoals bij de sensorwacht.
            if now - sinds >= ALTIJD_AAN_WACHT:
                _LOGGER.warning("%s (%s) staat al %d minuten %s", naam, plug,
                                int(_tussen(sinds, now).total_seconds() // 60), stand or "nergens")

        if any(now - k[3] >= ALTIJD_AAN_WACHT for k in kandidaten):
            bundel = [k for k in kandidaten if now - k[3] >= ALTIJD_AAN_BUNDEL]
            await self._async_stekkers_melden(bundel, now, mag, telefoon)

        # Een stekker die er niet meer is, of niet meer aan hoeft, telt niet meer.
        for sleutel in set(self._stekker_uit) - gezien:
            self._stekker_uit.pop(sleutel, None)
            self._stekker_klok_stop(sleutel)
        self._stekker_gemeld &= gezien
        self._stekker_gezet &= gezien
        self._stekker_nieuw &= gezien
        self._stekker_ooit &= gezien
        self._stekker_terug = {k: v for k, v in self._stekker_terug.items() if k in gezien}
        if self._stekker_terug and (
            not self._stekker_gemeld or now - min(self._stekker_terug.values()) >= ALTIJD_AAN_BUNDEL
        ):
            terug = [namen[k] for k in namen if k in self._stekker_terug]
            self._stekker_terug.clear()
            await self._async_tell(
                t("{naam} staat weer aan.", naam=terug[0][0]) if len(terug) == 1
                else t("{namen} staan weer aan.", namen=_opsomming(terug)),
                telefoon=False,
            )

    def _stekker_weg_sinds(self, entity_id: str, now: datetime) -> datetime:
        """Wanneer de schakelaar van een stekker wegviel, nooit later dan `now` (v0.183.0).

        Home Assistant zet `last_changed` bij elke wisseling van de toestand, ook naar niet
        bereikbaar. Zonder toestand is `now` het enige wat de coach weet.
        """
        state = self.hass.states.get(entity_id)
        gezet = getattr(state, "last_changed", None) if state is not None else None
        if not isinstance(gezet, datetime):
            return now
        if gezet.tzinfo is not None:
            gezet = dt_util.as_local(gezet).replace(tzinfo=None)
        return min(gezet, now)

    async def _async_stekkers_melden(
        self, bundel: list[tuple[str, str, str, datetime, str]], now: datetime, mag: bool, telefoon: bool
    ) -> None:
        """Eén melding voor de stekkers die samen wegvielen (v0.178.0).

        Bij een klant op 29-10-2026 kwamen er vijf kritieke meldingen in dezelfde seconde,
        een per stekker. Nu één, met per soort een zin: niet bereikbaar, uit en niet aan te
        krijgen, of uit. Kritiek blijft kritiek. Een stekker die de coach nog nooit bereikbaar
        zag krijgt een eigen gewone melding: de eigenaar koos op 29-10-2026 "ja b", want dat
        gebeurt bij elke nieuwe stekker die nog niet in het stopcontact zit, en de bewoner kan
        er niets aan doen. Valt hij later weg, nadat hij er was, dan is het wel kritiek.
        """
        def namen(rijen: list[tuple[str, str, str, datetime, str]]) -> str:
            return _opsomming([(k[1], k[2]) for k in rijen])

        weg = [k for k in bundel if k[4] == "weg"]
        uit = [k for k in bundel if k[4] == "uit"]
        nieuw = [k for k in bundel if k[4] == "nieuw"]
        # Eén tijd voor de hele melding: die van de stekker die over de wachttijd ging. Wat er
        # een halve minuut later bij kwam hoort bij dezelfde storing.
        lang = max((int(_tussen(k[3], now).total_seconds() // 60) for k in weg + uit), default=0)

        def minuten(_rijen: list[tuple[str, str, str, datetime, str]]) -> int:
            return lang
        delen: list[str] = []
        if weg:
            delen.append(
                t("{naam} is al {minuten} minuten niet bereikbaar; de coach weet niet of hij aan staat.",
                  naam=namen(weg), minuten=minuten(weg)) if len(weg) == 1
                else t("{namen} zijn al {minuten} minuten niet bereikbaar; de coach weet niet of ze aan staan.",
                       namen=namen(weg), minuten=minuten(weg))
            )
        if uit and mag:
            delen.append(
                t("{naam} staat al {minuten} minuten uit en de coach krijgt hem niet aan.",
                  naam=namen(uit), minuten=minuten(uit)) if len(uit) == 1
                else t("{namen} staan al {minuten} minuten uit en de coach krijgt ze niet aan.",
                       namen=namen(uit), minuten=minuten(uit))
            )
        elif uit:
            delen.append(
                t("{naam} staat al {minuten} minuten uit.", naam=namen(uit), minuten=minuten(uit)) if len(uit) == 1
                else t("{namen} staan al {minuten} minuten uit.", namen=namen(uit), minuten=minuten(uit))
            )
        if delen:
            self._stekker_gemeld |= {k[0] for k in weg + uit}
            await self._async_tell(" ".join(delen), kritiek=True, telefoon=telefoon)
        if nieuw:
            self._stekker_nieuw |= {k[0] for k in nieuw}
            await self._async_tell(
                t("{naam} is nog niet bereikbaar. Zodra hij er is, houdt de coach hem aan.", naam=namen(nieuw))
                if len(nieuw) == 1
                else t("{namen} zijn nog niet bereikbaar. Zodra ze er zijn, houdt de coach ze aan.",
                       namen=namen(nieuw)),
                telefoon=telefoon,
            )

    def _stekker_klok_stop(self, sleutel: str) -> None:
        """De klok van een stekker die uit stond opzeggen, als die er is."""
        opzeggen = self._stekker_klok.pop(sleutel, None)
        if opzeggen is not None:
            opzeggen()

    @callback
    def _stekker_klok_af(self, _now: Any) -> None:
        """De wachttijd van een stekker die uit staat is om: nu kijken."""
        self.async_refresh()

    async def _async_verbruikswacht(self, settings: dict[str, Any], now: datetime) -> None:
        """Lekkage of abnormaal verbruik van water en gas, één melding per geval.

        De bewoner van de eerste woning op 22-09-2026: "meldingen instellen
        obv abnormaal water- en gasverbruik, mogelijk lekkage." Twee tekenen:

        1. **Water dat blijft lopen.** Meldt de debietsensor (L/min) langer dan
           `water_flow_minutes` achter elkaar iets boven nul, dan staat er een
           kraan open of lekt er iets. Eén melding per keer dat het begint.
        2. **Een dag die uit de toon valt.** De coach houdt per meter het
           dagverbruik bij (`usage_days`), en zegt het als de dag van gisteren
           meer dan `factor` keer de mediaan van de dagen ervoor was, pas na
           `min_days` gemeten dagen. Eén melding per dag.

        Het dagverbruik komt uit de tellers zelf: bij de eerste ronde van een
        nieuwe dag is het verschil met de stand waarmee de dag begon het
        verbruik van gisteren. Dat vraagt geen recorder en overleeft een
        herstart, want de beginstand staat in de instellingen (`usage_start`).
        """
        alert = (settings.get("notifications") or {}).get("usage_alert") or {}
        meters = (settings.get("sources") or {}).get("meters") or {}
        tellers = {}
        if meters.get("gas_enabled") and meters.get("gas"):
            tellers["gas"] = meters["gas"]
        if meters.get("water_enabled") and meters.get("water"):
            tellers["water"] = meters["water"]

        # 1. Water dat blijft lopen.
        if alert.get("enabled") and meters.get("water_enabled") and meters.get("water_flow"):
            debiet = _number(self.hass, meters["water_flow"])
            if debiet is not None and debiet > 0:
                sinds = self._water_loopt_sinds or now
                self._water_loopt_sinds = sinds
                grens = timedelta(minutes=int(alert.get("water_flow_minutes") or 120))
                self._water_onthouden()
                if now - sinds >= grens and not self._water_gemeld:
                    self._water_gemeld = True
                    self._water_onthouden()
                    minuten = int(_tussen(sinds, now).total_seconds() // 60)
                    await self._async_tell(
                        t(
                            "Er loopt al {minuten} minuten onafgebroken water ({debiet} L/min). "
                            "Mogelijk een lekkage of een kraan die openstaat.",
                            minuten=minuten, debiet=_rond(debiet, 1),
                        ),
                        kritiek=True,
                    )
            else:
                self._water_loopt_sinds = None
                self._water_gemeld = False
                self._water_onthouden()

        # 2. Het dagverbruik bijhouden, en gisteren vergelijken met de dagen ervoor.
        if not tellers:
            return
        vandaag = now.date().isoformat()
        starts = {r.get("meter"): r for r in settings.get("usage_start") or [] if isinstance(r, dict)}
        dagen = [r for r in settings.get("usage_days") or [] if isinstance(r, dict)]
        nieuw_start = []
        nieuwe_dagen = list(dagen)
        veranderd = False
        for meter, entity in tellers.items():
            stand = _number(self.hass, entity)
            if stand is None:
                if meter in starts:
                    nieuw_start.append(starts[meter])
                continue
            begin = starts.get(meter)
            if begin is None or begin.get("date") != vandaag:
                if begin is not None and begin.get("date"):
                    try:
                        verbruik = stand - float(begin.get("value"))
                    except (TypeError, ValueError):
                        verbruik = None
                    if verbruik is not None and 0 <= verbruik < 1000:
                        nieuwe_dagen = [d for d in nieuwe_dagen if not (d.get("meter") == meter and d.get("date") == begin["date"])]
                        nieuwe_dagen.append({"meter": meter, "date": begin["date"], "m3": round(verbruik, 3)})
                nieuw_start.append({"meter": meter, "date": vandaag, "value": stand})
                veranderd = True
            else:
                nieuw_start.append(begin)
        # Hooguit dertig dagen per meter.
        per_meter: dict[str, list[dict]] = {}
        for d in sorted(nieuwe_dagen, key=lambda d: str(d.get("date"))):
            per_meter.setdefault(str(d.get("meter")), []).append(d)
        nieuwe_dagen = [d for lijst in per_meter.values() for d in lijst[-30:]]
        if veranderd:
            try:
                saved = await async_get_store(self.hass).async_save(
                    {"usage_start": nieuw_start, "usage_days": nieuwe_dagen}
                )
                settings["usage_start"], settings["usage_days"] = nieuw_start, nieuwe_dagen
                self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": saved})
            except Exception:  # noqa: BLE001 - een gemiste opslag is geen reden om te stoppen
                _LOGGER.exception("kon het dagverbruik niet bewaren")

        if not alert.get("enabled") or not veranderd:
            return
        factor = float(alert.get("factor") or 3)
        min_dagen = int(alert.get("min_days") or 5)
        for meter, lijst in per_meter.items():
            if len(lijst) < min_dagen + 1:
                continue
            gisteren = lijst[-1]
            # Gas tegen de laatste week, water tegen alles wat er is (v0.157.0). Gas volgt het seizoen:
            # in een klantwoning op 25-10-2026 een kritieke melding over 4,1 m³ tegen "normaal 0,72",
            # omdat de helft van de dertig dagen nog zomer was. Over zeven dagen lag de mediaan rond 2.
            vorige = lijst[:-1][-GAS_VERGELIJK_DAGEN:] if meter == "gas" else lijst[:-1]
            eerder = sorted(float(d.get("m3") or 0) for d in vorige)
            mediaan = eerder[len(eerder) // 2]
            if mediaan <= 0 or float(gisteren.get("m3") or 0) <= factor * mediaan:
                continue
            sleutel = f"{meter}:{gisteren.get('date')}"
            if sleutel in self._verbruik_gemeld:
                continue
            self._verbruik_gemeld.add(sleutel)
            naam = t("gas") if meter == "gas" else t("water")
            await self._async_tell(
                t(
                    "Gisteren ging er {m3} m³ {naam} doorheen, normaal is dat rond {mediaan} m³ per dag. "
                    "Kijk of er iets lekt of aan is blijven staan.",
                    m3=_rond(float(gisteren["m3"]), 2), naam=naam, mediaan=_rond(mediaan, 2),
                ),
                kritiek=True,
            )

    def _zon_slaapt(self) -> bool:
        """Of de zon zo laag staat dat een omvormer mag slapen (`sun.sun`).

        Zonder die entiteit weet de coach het niet, en dan blijft de melding
        zoals hij was.
        """
        state = self.hass.states.get("sun.sun")
        if state is None:
            return False
        if state.state == "below_horizon":
            return True
        try:
            return float(state.attributes.get("elevation")) < ZON_SLAAPT_ONDER
        except (TypeError, ValueError):
            return False

    @callback
    def async_refresh(self) -> None:
        """Nu meteen een ronde draaien, in plaats van tot de volgende minuut wachten.

        Een minuut is snel genoeg om een zekering voor te blijven, maar veel te
        traag als er iemand naar zit te kijken. Wie op pauze drukt en een halve
        minuut niets ziet gebeuren, concludeert dat de knop stuk is en gaat
        zoeken naar een andere manier. En wie de kabel eruit trekt, hoort niet
        nog een minuut op zijn scherm te lezen dat hij zelf gepauzeerd heeft.
        """
        self.hass.async_create_task(self._tick())

    def _watch_phases(self, settings: dict[str, Any], steerable: bool) -> None:
        """Welke fasesensoren er zijn, en vanaf welke stroom het haast wordt.

        De grens is dezelfde als waar de planner mee rekent: de zekering min de
        marge eronder. Komt een fase daarboven, dan is er voor de laadpaal niets
        meer over en hoort hij terug, nu en niet over een minuut.

        Zonder stuurbare laadpaal wordt er niets bewaakt: er is dan niets om
        terug te regelen, en meeluisteren met een meter die elke seconde meldt
        kost dan alleen maar.
        """
        sources = settings.get("sources") or {}
        installation = settings.get("installation") or {}

        entities: set[str] = set()
        if steerable and sources.get("phases_enabled"):
            for key in ("l1", "l2", "l3"):
                phase = (sources.get("phases") or {}).get(key) or {}
                # Alleen echte stroomsensoren. Uit vermogen en spanning valt het
                # ook te herleiden, maar dat is werk voor een ronde en niet voor
                # een melding die tien keer per seconde langskomt.
                if phase.get("current"):
                    entities.add(phase["current"])

        # En de stroomsensoren van elke groep, elk met de grens van zijn eigen
        # zekering: een garage van 16 A zit vol bij 14 A, lang voordat de
        # hoofdaansluiting iets merkt.
        grenzen: dict[str, float] = {}
        zekering = float(installation.get("fuse_amps") or 25)
        marge = (
            BALANCER_MARGIN_AMPS if installation.get("load_balancer") else FUSE_MARGIN_AMPS
        )
        for entity in entities:
            grenzen[entity] = zekering - max(marge, zekering * FUSE_MARGIN_SHARE)
        if steerable:
            for groep in installation.get("circuits") or []:
                if not isinstance(groep, dict):
                    continue
                grens_groep = float(groep.get("fuse_amps") or 16)
                grens_groep -= max(FUSE_MARGIN_AMPS, grens_groep * FUSE_MARGIN_SHARE)
                for key in ("l1", "l2", "l3"):
                    sensor = ((groep.get("sensors") or {}).get(key) or {}).get("current")
                    if sensor:
                        entities.add(sensor)
                        grenzen[sensor] = min(grenzen.get(sensor, grens_groep), grens_groep)

        self._watched_phases = entities
        self._urgent_above = grenzen or None

    def _watch(self, entity_ids: set[str]) -> None:
        """Meeluisteren met de statussensoren van de laadpalen.

        Zodat een kabel die erin gaat of eruit komt binnen een seconde een verse
        beslissing oplevert in plaats van bij de volgende ronde. De lijst
        verandert alleen als er apparaten bij komen of af gaan, dus dit doet
        vrijwel nooit iets.
        """
        if entity_ids == self._watched:
            return
        if self._unwatch is not None:
            self._unwatch()
            self._unwatch = None
        self._watched = entity_ids
        if entity_ids:
            self._unwatch = async_track_state_change_event(
                self.hass, sorted(entity_ids), self._async_state_changed
            )

    @callback
    def _async_state_changed(self, event) -> None:
        """Een wisseling waar de coach iets mee moet.

        Twee soorten. Een laadpaal die van toestand wisselt is er altijd een: de
        kabel gaat erin of eruit, het laden begint of stopt, en dan hoort er een
        vers besluit te komen in plaats van bij de volgende minuut.

        En de fasestromen, maar alleen als ze te hoog worden. Dat is de haast:
        een minuut is snel genoeg om een smeltveiligheid voor te blijven, maar
        het maakt die minuut wel het enige dat tussen een vol huis en een
        gesprongen zekering staat. Wordt het krap, dan kijkt hij binnen een
        seconde. Wordt het niet krap, dan gebeurt er hier niets, want anders
        draait de coach een ronde bij elke meterpuls.
        """
        entity = event.data.get("entity_id")
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        if new is None:
            return

        if entity in self._watched_phases:
            self._async_phase_changed(new)
            return

        if old is None or old.state == new.state:
            return
        self.async_refresh()

    @callback
    def _async_phase_changed(self, new) -> None:
        """Een fasestroom die over de grens komt, en niet te vaak.

        Elke meting wordt hier ook bewaard, ook de rustige. Dat is het enige
        punt in de coach waar ze binnenkomen op het tempo van de meter zelf, en
        zonder een handvol punten valt er niets glad te strijken. Zie
        `FASE_VENSTER`.
        """
        try:
            amps = float(new.state)
        except (TypeError, ValueError):
            return

        # Dezelfde klok als de ronde, want `_gladde_fase` zet deze stempels
        # naast de tijd van die ronde. Zie `_moment`.
        nu = _moment()
        historie = self._fase_historie.setdefault(new.entity_id, [])
        historie.append((nu, amps))
        grens = nu - FASE_VENSTER
        # Eén meting van vóór het venster blijft staan: die zegt wat er aan
        # het begin van het venster stond. De mediaan telt hem niet, de
        # hoogste meting wel; zie `_piek_fase`.
        while len(historie) > 1 and historie[1][0] < grens:
            historie.pop(0)

        grens = (self._urgent_above or {}).get(new.entity_id)
        if grens is None or amps < grens:
            return

        if self._last_urgent is not None and nu - self._last_urgent < HURRY_INTERVAL:
            return
        self._last_urgent = nu
        _LOGGER.debug("fasestroom %.1f A boven %.1f A, meteen opnieuw kijken", amps, grens)
        self.async_refresh()

    async def _tick(self, now: datetime | None = None) -> None:
        """One round: look, think, act.

        Er kan er maar één tegelijk lopen. Een ronde wordt niet alleen door de
        klok gestart maar ook door een druk op een knop en door een laadpaal die
        van toestand wisselt, en twee rondes die tegelijk opdrachten sturen
        zouden elkaar in de weg zitten.
        """
        if self._running or self._stopt:
            return
        self._running = True
        try:
            async with asyncio.timeout(ROUND_TIMEOUT.total_seconds()):
                gelukt = await self._round(now)
            # Alleen een ronde die er werkelijk doorheen kwam telt als teken van
            # leven. Anders zwijgt de wachthond terwijl de coach al een uur geen
            # besluit meer neemt omdat zijn instellingen niet te lezen zijn: een
            # stille coach die er van buiten uitziet als een werkende.
            if gelukt:
                self._last_round = dt_util.utcnow()
            try:
                self._meldingen_onthouden()
                await async_get_geheugen(self.hass).async_bewaar(dt_util.utcnow(), GEHEUGEN_ELKE)
            except Exception:  # noqa: BLE001 - onthouden mag een ronde niet stoppen
                _LOGGER.exception("kon het geheugen niet bewaren")
        except TimeoutError:
            # De gevaarlijkste storing die er is, want hij is stil: hangt een
            # opdracht naar de laadpaal, dan zou de vlag hierboven blijven staan
            # en werd elke volgende ronde overgeslagen. De coach leefde dan nog
            # wel, maar besliste niets meer, en er werd gewoon geladen. Met een
            # harde grens eromheen kan dat niet: hij breekt af, meldt het, en
            # probeert het een minuut later opnieuw.
            _LOGGER.error(
                "een ronde duurde langer dan %s seconden en is afgebroken",
                int(ROUND_TIMEOUT.total_seconds()),
            )
        finally:
            self._running = False

    async def _round(self, now: datetime | None) -> bool:
        """Wat er in één ronde gebeurt, en of dat gelukt is."""
        try:
            settings = await async_get_store(self.hass).async_load()
        except Exception:  # noqa: BLE001 - never let a bad read stop the timer
            _LOGGER.exception("kon de instellingen niet lezen")
            return False
        # De taal van wat de coach deze ronde schrijft (v0.140.0): de instelling bij
        # Installatie, en bij automatisch die van Home Assistant. Zie taal.py.
        taal.kies_uit(settings, getattr(self.hass.config, "language", None))
        # En de tijdzone van het huis, voor de planner en de batterij: elke duur over de
        # zomer- en wintertijd heen in echte uren (`zet_zone` in planner.py).
        zet_zone(dt_util.get_default_time_zone())

        if not self._restored:
            # Eén keer, vóór de eerste ronde: de beurten die nog liepen toen
            # Home Assistant stopte, zodat hun geld gewoon doortelt.
            await self._async_beurten_laden()
            await self._async_geheugen_laden()
        self._restore(settings)

        level = (settings.get("strategy") or {}).get("level", LEVEL_PROPOSE)
        moment = _moment(now)
        await self._async_nordpool(settings, moment)
        try:
            await self._async_berichten(settings, moment)
        except Exception:  # noqa: BLE001 - een herinnering mag een ronde niet kosten
            _LOGGER.exception("kon de berichtenbox niet bijwerken")

        chargers = [
            device
            for device in settings.get("devices") or []
            if device.get("type") == "laadpaal" and device.get("controllable")
        ]
        self._watch_phases(settings, bool(chargers))
        # En de vrijgaveschakelaar en de status van een programma-apparaat:
        # De eigenaar zette op 06-09-2026 zijn schakelaar aan en binnen vijf seconden
        # weer uit omdat er niets gebeurde, terwijl de coach pas bij de
        # volgende minuut keek. Een schakelaar hoort binnen een seconde
        # antwoord te geven, net als een kabel in de paal.
        programma_apparaten = [
            device
            for device in settings.get("devices") or []
            if device.get("type") in PROGRAMMA_TYPES and device.get("controllable")
        ]
        boilers = [
            device
            for device in settings.get("devices") or []
            if device.get("type") == "boiler" and device.get("controllable")
        ]
        # Een merk dat de coach alleen uitleest stuurt hij nooit, ook niet met het
        # vinkje aan. Een Growatt komt er hieronder bij als hij een laadschema kan
        # krijgen (v0.150.0), ook zonder het vinkje.
        batterijen = [
            device
            for device in settings.get("devices") or []
            if device.get("type") == "thuisbatterij" and device.get("controllable")
            and device.get("brand") not in BATTERIJ_ALLEEN_LEZEN + BATTERIJ_SCHEMA
        ]
        self._watch_batterij(settings, batterijen)
        self._watch(
            {
                entity
                for device in chargers
                for sleutel in ("status", "connected", "charging")
                if (entity := (device.get("entities") or {}).get(sleutel))
            }
            # De startknop erbij: bij Home Connect Local komt die pas terug
            # als de deur dichtgaat, en dan hoort de coach meteen te drukken.
            | {
                entity
                for device in programma_apparaten
                for sleutel in ("release_switch", "release_now_switch", "release_button", "door",
                                "status", "start", "remote_start")
                if (entity := (
                    self._vrijgave_entiteit(device, sleutel)
                    if sleutel in ("release_switch", "release_now_switch")
                    else (device.get("entities") or {}).get(sleutel)
                ))
            }
            # De schakelaar van een boiler, en niet zijn vermogenssensor: die
            # laatste beweegt voortdurend en zou de coach elke seconde wekken.
            # Of het vat vol is blijkt pas na minuten stilte, dus daar is de
            # klok snel genoeg voor.
            | {
                entity
                for device in boilers
                if (entity := (device.get("entities") or {}).get("switch"))
            }
            # En de schakelaar van een smart plug die altijd aan moet staan
            # (v0.120.0): gaat hij uit, dan hoort hij meteen weer aan te gaan.
            | {
                entity
                for device in settings.get("devices") or []
                if (entity := _altijd_aan(device))
            }
            | self._watched_phases
        )

        # Twee laadpunten op één zekering zagen allebei dezelfde vrije ampères
        # en namen ze allebei. Wat de een krijgt telt daarom mee als bezet voor
        # wie er in deze ronde na hem komt.
        #
        # Dan doet de volgorde er ineens toe, en die mag niet afhangen van wie
        # er toevallig het eerst is toegevoegd. De voorrang die de klant per
        # apparaat heeft ingesteld bepaalt hem: is er te weinig ruimte voor
        # allebei, dan krijgt de auto die je nodig hebt hem.
        # De twee dingen die de vergelijking over de komende uren nodig heeft.
        # Allebei op een eigen klok: ze bewegen niet per minuut en het zijn de
        # enige twee plekken waar de coach naar de database of naar een dienst
        # buiten zichzelf kijkt.
        await self._async_huisverbruik(settings, moment)
        await self._async_jaarsaldo(settings, moment)
        await self._async_schaal(settings, moment)
        await self._async_sensorwacht(settings, moment)
        await self._async_integraties(settings, moment)
        await self._async_groep_vol(settings, moment)
        await self._async_verbruikswacht(settings, moment)
        await self._async_temperatuurwacht(settings, moment, level)
        await self._async_vriezerwacht(settings, moment)
        await self._async_altijd_aan(settings, moment, level)
        await self._async_zonkromme(settings, moment)
        self._meter_bijhouden(settings, moment)

        # Een Growatt die een laadschema kan krijgen (v0.150.0) gaat door dezelfde
        # ronde. Zonder het vinkje rekent hij in de schaduw en schrijft hij niets: de
        # eigenaar op 22-10-2026, "eerst de schaduw".
        for device in settings.get("devices") or []:
            if device.get("type") == "thuisbatterij" and device.get("brand") in BATTERIJ_SCHEMA:
                if await self._async_growatt_soort(device, moment) == "sph":
                    batterijen.append(device)

        # De batterij eerst: wat hij deze minuut doet bepaalt wat de meter de
        # andere apparaten laat zien.
        for device in batterijen:
            try:
                await self._one_batterij(moment, settings, device, level)
                self._besluit_melden(device.get("id", ""))
                self._batterij_onthouden(device.get("id", ""))
            except ServiceNotFound:
                _LOGGER.warning(
                    "%s kan nog niet aangestuurd worden: de integratie van de batterij is er nog niet",
                    device.get("name") or device.get("id"),
                )
            except Exception:  # noqa: BLE001 - one broken device is not all of them
                _LOGGER.exception("kon %s niet beoordelen", device.get("id"))
        # Een batterij die de coach niet stuurt meet hij wel (v0.123.0).
        gestuurd = {d.get("id") for d in batterijen}
        for device in settings.get("devices") or []:
            if device.get("type") == "thuisbatterij" and device.get("id") not in gestuurd:
                await self._async_batterij_uitlezen(settings, device)
        # Een batterij die niet meer gestuurd mag worden gaat terug naar zijn
        # eigen stand, ook als het vinkje eraf ging.
        for device_id, sessie in list(self._batterij.items()):
            if device_id in {d.get("id") for d in batterijen}:
                continue
            oud = next((d for d in settings.get("devices") or [] if d.get("id") == device_id), None)
            if (sessie.get("stuurt") or sessie.get("growatt_stuurt")) and oud is not None:
                await self._async_batterij_loslaten(oud)
            self._batterij.pop(device_id, None)
            self.state.pop(device_id, None)

        # In de volgorde van de voorrang bij planningen (v0.93.0; daarvoor de
        # hoog/midden/laag per paal, die nu de beginvolgorde van die lijst is).
        rang = self._plan_voorrang(settings)
        chargers.sort(key=lambda device: rang.get(device.get("id", ""), len(rang)))
        # Wat er deze ronde al aan een eerder laadpunt is toegezegd, per
        # zekering: "" is de hoofdaansluiting, verder het id van elke groep.
        # Twee palen op dezelfde groep delen die groep; een paal in de garage
        # en een aan de meterkast delen alleen de hoofdaansluiting.
        vergeven: dict[str, float] = {}
        for device in chargers:
            try:
                # Wat de palen hiervoor al toezegden, plus wat een batterij of
                # boiler hoger in de voorrang toezegde.
                bezet = dict(vergeven)
                for sleutel, amps in self._hogere_toezeggingen(settings, device, zonder_palen=True).items():
                    bezet[sleutel] = bezet.get(sleutel, 0.0) + amps
                claim = await self._one(moment, settings, device, level, bezet)
                await self._async_paal_terug(device)
                sleutels = self._groep_sleutels(settings, device)
                for sleutel in sleutels:
                    vergeven[sleutel] = vergeven.get(sleutel, 0.0) + claim
                self._toezeggingen[device.get("id", "")] = {
                    "amps": claim, "totaal": self._paal_stroom.get(device.get("id", ""), claim), "sleutels": sleutels,
                }
            except ServiceNotFound as fout:
                # Gebeurt bij het opstarten: de coach draait al voordat de
                # integratie van het merk zijn diensten heeft klaargezet. Geen
                # reden voor een foutmelding met een spoor erbij; de volgende
                # ronde is hij er wel. Zou hij er nooit komen, dan blijft deze
                # regel elke minuut terugkomen en dat is precies het signaal.
                _LOGGER.warning(
                    "%s kan nog niet aangestuurd worden: %s bestaat niet (nog niet geladen?)",
                    device.get("name") or device.get("id"),
                    fout.translation_placeholders.get("service", "de opdracht")
                    if getattr(fout, "translation_placeholders", None)
                    else "de opdracht",
                )
            except PaalOnbereikbaar as fout:
                await self._async_paal_weg(device, moment, fout)
                # Wat hij de vorige ronde toezegde blijft staan: misschien laadt hij nog, en dan
                # rekenen de batterij en de lastbewaker beter niet met een paal op 0.
                vorige = self._toezeggingen.get(device.get("id", ""))
                if vorige:
                    for sleutel in vorige.get("sleutels") or []:
                        vergeven[sleutel] = vergeven.get(sleutel, 0.0) + vorige.get("amps", 0.0)
            except Exception:  # noqa: BLE001 - one broken device is not all of them
                _LOGGER.exception("kon %s niet beoordelen", device.get("id"))

        # En de apparaten met een programma: die starten één keer. Een apparaat
        # dat de coach niet mag sturen volgt hij wel (v0.127.0): draait, klaar,
        # het verslag en de meting, maar hij start het nooit. Tot dan sloeg hij
        # het helemaal over, en bleef de kaart staan op het laatste besluit; de
        # beheersessie op 16-10-2026 bij een Miele-wasmachine en -droger die
        # alleen uitgelezen worden.
        for device in settings.get("devices") or []:
            if device.get("type") not in PROGRAMMA_TYPES:
                continue
            try:
                await self._one_programma(moment, settings, device, level if device.get("controllable") else LEVEL_READ)
                self._besluit_melden(device.get("id", ""))
                # Na de hele ronde, ook als die eerder ophield: de vraag en de pogingen
                # komen pas aan het eind (v0.172.0).
                self._programma_onthouden(device.get("id", ""))
            except ServiceNotFound:
                _LOGGER.warning(
                    "%s kan nog niet aangestuurd worden: de startknop bestaat niet (nog niet geladen?)",
                    device.get("name") or device.get("id"),
                )
            except Exception:  # noqa: BLE001 - one broken device is not all of them
                _LOGGER.exception("kon %s niet beoordelen", device.get("id"))

        # En de boilers: die staan aan of uit, en hun eigen thermostaat zegt
        # wanneer het genoeg is.
        for device in settings.get("devices") or []:
            if device.get("type") != "boiler" or not device.get("controllable"):
                continue
            try:
                await self._one_boiler(moment, settings, device, level)
                self._besluit_melden(device.get("id", ""))
            except ServiceNotFound:
                _LOGGER.warning(
                    "%s kan nog niet aangestuurd worden: de schakelaar bestaat niet (nog niet geladen?)",
                    device.get("name") or device.get("id"),
                )
            except Exception:  # noqa: BLE001 - one broken device is not all of them
                _LOGGER.exception("kon %s niet beoordelen", device.get("id"))

        # En de airco's (v0.119.0): aan of uit, met de temperatuur van de bewoner.
        for device in settings.get("devices") or []:
            if device.get("type") != "airco" or not device.get("controllable"):
                continue
            try:
                await self._one_airco(moment, settings, device, level)
                self._besluit_melden(device.get("id", ""))
            except ServiceNotFound:
                _LOGGER.warning(
                    "%s kan nog niet aangestuurd worden: de airco bestaat niet (nog niet geladen?)",
                    device.get("name") or device.get("id"),
                )
            except Exception:  # noqa: BLE001 - one broken device is not all of them
                _LOGGER.exception("kon %s niet beoordelen", device.get("id"))

        return True

    def _besluit_melden(self, device_id: str) -> None:
        """Het besluit van deze ronde naar het paneel, zoals `_one` het voor een paal doet.

        Tot v0.94.0 deed alleen de paal dat. De kaart van een batterij, een
        boiler of een vaatwasser kreeg zijn besluit dus alleen bij het openen
        van het paneel, en in de eerste woning zei de kaart op 23-09-2026 om
        23:15 "de coach heeft 43 minuten niets beslist" en "accu nu 79%" terwijl
        de coach elke minuut besliste en de accu op 71% stond.
        """
        stand = self.state.get(device_id)
        if stand is not None:
            self.hass.bus.async_fire(EVENT_DECISION, {"device": device_id, **stand})

    # ------------------------------------------------------------------
    # Een apparaat met een programma: de vaatwasser
    #
    # De eigenaar op 06-09-2026: "nu verder met de vaatwasser sturing." Het denkwerk
    # staat in `plan_programma` in planner.py; hier alleen het lezen van de
    # sensoren, het drukken op de knop, en het verslag.

    async def _one_programma(
        self,
        now: datetime,
        settings: dict[str, Any],
        device: dict[str, Any],
        level: str,
    ) -> None:
        device_id = device.get("id", "")
        entities = device.get("entities") or {}
        naam = _programma_naam(device)
        soort = str(device.get("type") or "")
        # Een Miele noemt zijn programma's zelf en geeft de duur (v0.124.0).
        miele = device.get("brand") == "miele"
        if device_id not in self._programma:
            self._programma[device_id] = self._programma_terug(device_id, now)
        sessie = self._programma.setdefault(device_id, self._lege_programma_sessie(now))
        # De eerste ronde waarin deze coach het apparaat ziet: liep er toen al
        # een beurt, dan is dit een herstart middenin.
        eerste = not sessie.get("gezien")
        sessie["gezien"] = True

        # Zonder startknop is het een apparaat op een meetstekker: de coach
        # zegt wanneer, de bewoner drukt, en het vermogen zegt of hij draait.
        handmatig = not entities.get("start")
        # De tabel van dit apparaat: wat de klant invulde (of de opgave van de
        # fabrikant), met de metingen van eerdere beurten eroverheen.
        # Een wasmachine en een droger hebben geen opgave van de fabrikant
        # (v0.124.0): de tabel is wat de klant invulde, met wat de coach mat,
        # ook van programma's die er niet in staan.
        vaat = soort == "vaatwasser"
        tabel = met_metingen(
            tabel_van(device.get("programs"), PROGRAMMAS if vaat else ()),
            settings.get("program_measured"), device_id, ook_nieuw=not vaat,
        )

        # Alleen uitlezen (v0.127.0): geen vrijgave, en de coach komt niet aan
        # de knop, de schakelaars of de klep; die zijn van de bewoner.
        alleen_lezen = _programma_alleen_lezen(device)
        released = not alleen_lezen and device_id in (settings.get("ready_devices") or [])
        # Zonder vrijgave (v0.102.0) is klep dicht vrijgegeven; dat volgt
        # hieronder, als de status bekend is. Knop en schakelaars tellen dan niet.
        zonder_vrijgave = device.get("release_required") is False
        # Een fysieke knop of een knop-helper (v0.102.0): één druk is "ingeruimd
        # en dicht", nog een keer drukken doet niets.
        if not zonder_vrijgave and not alleen_lezen:
            released = await self._async_knop_volgen(settings, device, sessie, released)
        # Een vrijgaveschakelaar naast de knop op de kaart. De eigenaar op 06-09-2026:
        # een eigen kaart in de keuken met een knop "sturing" die een
        # schakelaar aanzet, "en dan wil ik dat Ingeruimd en dicht aangaat."
        # De twee volgen elkaar: beweegt de schakelaar, dan volgt de vrijgave;
        # beweegt de knop op de kaart, dan volgt de schakelaar; en na een
        # beurt gaan ze allebei uit.
        nu_starten = False
        if not zonder_vrijgave and not alleen_lezen:
            released = await self._async_schakelaar_volgen(settings, device, sessie, released)
            # En "ingeruimd en nu starten", op de kaart of met een eigen schakelaar
            # (de eigenaar, 13-09-2026).
            released, nu_starten = await self._async_nu_volgen(settings, device, sessie, released)
        # Wat erop staat: de sensor, en als die het niet zegt de select-entiteit
        # waarmee het gezet wordt. Home Connect Local (thuis sinds 23-09-2026)
        # heeft een sensor die alleen tijdens de beurt iets zegt (het actieve
        # programma) en een select die juist tijdens de beurt wegvalt; samen
        # weten ze het altijd. Bij de andere integraties zegt de sensor het
        # al, en dan komt de select niet aan de beurt.
        programma = None
        if miele:
            # Precies op de sleutel: bij Miele is de ene naam soms het eind van
            # een andere ("denim" en "gentle_denim"), en dan zou `programma_van`
            # de verkeerde kunnen vinden.
            ruw = _text(self.hass, entities.get("program")).strip()
            if ruw.lower() not in GEEN_PROGRAMMA:
                programma = next((p for p in tabel if p.key == ruw), None)
                if programma is None:
                    programma = await self._async_machine_programma(entities, ruw, sessie, now)
        elif entities.get("program") or entities.get("program_select"):
            for sleutel in ("program", "program_select"):
                if entities.get(sleutel):
                    programma = programma_van(_text(self.hass, entities[sleutel]), tabel)
                    if programma is not None:
                        break
        else:
            # Geen sensor die het programma zegt: de bewoner koos het op de kaart.
            programma = programma_van(device.get("program") or None, tabel)
        deur = _text(self.hass, entities.get("door")).strip().lower()
        deur_open = None if not deur else deur in ("open", "on")
        watts = _watts(self.hass, device.get("entity"))

        if handmatig:
            status = self._status_uit_vermogen(sessie, now, watts)
        else:
            status = _text(self.hass, entities.get("status")).strip().lower()
            # `Dishcare...OperationState.Run` en `run` zijn hetzelfde; zie
            # `programma_van` voor dezelfde afspraak bij het programma.
            status = status.split(".")[-1]
            ruw = status
            # En Miele in dezelfde woorden (v0.124.0).
            status = MIELE_STATUS.get(status, status)
            # Een onderbreking midden in een beurt is een pauze (v0.127.0). In
            # de klantwoning op 16-10-2026: 08:59:26 in_use, 08:59:42
            # program_interrupted, 09:00:16 weer in_use; 16 seconden om de
            # temperatuur bij te stellen. Als "klaar" gaf dat een valse
            # melding, een beurt van 16 seconden, en de vrijgave eraf. Voorbij
            # is hij pas als hij daarna uit gaat of weer klaarstaat, en dan
            # zonder meting: een afgebroken programma zegt niets over de duur.
            if ruw == "program_interrupted" and sessie["gestart"] is not None:
                status = "pause"
                # Wanneer hij stilviel, voor het verslag (v0.128.1).
                if not sessie.get("afgebroken"):
                    sessie["onderbroken_om"] = now
                sessie["afgebroken"] = True
            elif status in DRAAIT or status in KLAAR:
                sessie["afgebroken"] = False
                sessie["onderbroken_om"] = None

        klep = ""
        if zonder_vrijgave and not alleen_lezen:
            released, klep = await self._async_klep_volgen(settings, device, sessie, released, deur_open, status)

        if released and sessie["vrijgegeven"] is None:
            sessie["vrijgegeven"] = now
            sessie["programma"] = programma
            # De prijzen van dit moment bewaren: de maat (wat meteen starten
            # gekost had) rekent met de uren ná het vrijgeven, en die staan
            # morgen niet meer in de prijslijst van de sensor.
            sessie["prijzen"] = list(self._prices(settings))
        if not released and sessie["gestart"] is None:
            # Vrijgave ingetrokken voor er iets gebeurde: schone lei.
            self._programma[device_id] = {**sessie, "vrijgegeven": None, "gedrukt": None,
                                          "pogingen": 0, "gemeld": set(), "programma": None,
                                          "gevraagd": None, "eind": None, "eind_gezien": None,
                                          "knop_weg": None}
            sessie = self._programma[device_id]
        if programma is not None:
            sessie["programma"] = programma

        window = resolve_window(now, self._days(settings, device))
        apparaat = Apparaat(
            status=status, released=released, program=programma, door_open=deur_open,
            manual=handmatig, start_now=nu_starten, door_release=klep,
            vrijgave=VRIJGAVE_WOORD.get(soort, ""),
        )
        decision = plan_programma(
            now, self._prices(settings), self._tarief(settings),
            Forecast(solar_kwh=self._zon_kwh, house_kwh=self._huis_kwh,
                     estimated=self._zon_geschat, solar_factor=self._zon_gemeten(now),
                     solar_day=now.date()),
            window, apparaat,
            # Wat er werkelijk naar het net gaat: in het lopende uur wint de
            # meter van de verwachting (de eigenaar op 07-09-2026, zie
            # programma_kosten), maar dan wat hij de afgelopen tien minuten
            # ten minste zag en niet één opklaring (11-09-2026, METER_VENSTER).
            surplus_w=self._meter_zeker(now),
        )
        if alleen_lezen and decision.rule not in ("running", "finished"):
            decision = Decision(False, 0, t("Alleen uitlezen: de coach start hem niet."), rule="read-only")
        if sessie.pop("knop_melden", False):
            await self._async_tell(self._knop_zin(naam, decision, now, handmatig))

        draait = status in DRAAIT
        if not draait and sessie["gestart"] is None and eerste:
            # Een beurt die in de opslag nog liep, maar nu niet meer draait:
            # hij is afgelopen terwijl de coach weg was. Afronden met wat er
            # stond (het einde is dan de laatste opslag, hooguit vijf minuten
            # te vroeg), anders blijft de vrijgave staan en start hij zo nog
            # een keer.
            regel = self._beurt_open.get(device_id)
            if regel is not None and regel.get("kind") == "programma":
                self._beurt_open.pop(device_id, None)
                if self._programma_uit_regel(sessie, regel, tabel):
                    einde = _tijdstip(regel.get("ended"))
                    einde = einde.replace(tzinfo=None) if einde is not None else now
                    sessie["gemeld"].add("klaar")
                    await self._async_programma_klaar(
                        settings, device, naam, sessie, now, min(einde, now), meten=False
                    )
                    return
        if draait and sessie["gestart"] is None:
            # Liep hij al toen de coach begon (een herstart middenin), dan
            # de beurt oppakken waar hij was, in plaats van nu te beginnen.
            if eerste:
                await self._async_programma_hervatten(settings, device, sessie, tabel, now)
            if sessie["gestart"] is None:
                sessie["gestart"] = now
            sessie["laatst"] = now
            if sessie.get("programma") is not None and programma is None:
                programma = sessie["programma"]
            # Of de coach erop drukte of erom vroeg, voor de melding hieronder:
            # die kan een ronde later komen, en dan is `gedrukt` al leeg.
            sessie["door_coach"] = sessie.get("gedrukt") is not None or sessie.get("gevraagd") is not None
            sessie["gedrukt"] = None
        # Wanneer het apparaat zelf zegt klaar te zijn: alleen zolang hij
        # draait, alleen een tijd die bij deze beurt hoort (EINDTIJD_MARGE),
        # en pas als hij stilstaat (`_eindtijd_vast`).
        eind = (
            _eindtijd_vast(
                sessie,
                _eindtijd(
                    self.hass, entities.get("remaining"), now,
                    sinds=sessie["gestart"] - EINDTIJD_MARGE,
                ),
            )
            if draait and sessie["gestart"] is not None
            else None
        )
        # De eigenaar op 07-09-2026: "ik wil wel meldingen ontvangen dat de
        # vaatwasser gestart is en klaar is." Dus per beurt twee: deze en
        # het verslag. "Gestart" als de coach erop drukte of erom vroeg;
        # "draait" als de bewoner hem zelf aanzette of de coach net herstartte.
        # Heeft het apparaat een eindtijd, dan wacht de melding tot die bij
        # deze beurt hoort, hooguit EINDTIJD_WACHT.
        if draait and sessie["gestart"] is not None and "gestart" not in sessie["gemeld"] and not (
            eind is None and entities.get("remaining") and _tussen(sessie["gestart"], now) < EINDTIJD_WACHT
        ):
            sessie["gemeld"].add("gestart")
            zelf = sessie.get("door_coach", False)
            dit = programma or sessie.get("programma")
            wat = f" ({t(dit.label)})" if dit is not None else ""
            # Het apparaat zelf weet het beste wanneer hij klaar is;
            # zonder die sensor de duur uit de tabel.
            if eind is not None and eind > now:
                klaar = t(", klaar rond {klok}", klok=f"{eind:%H:%M}")
            elif dit is not None and dit.minutes:
                klaar = t(", klaar rond {klok}", klok=f"{(sessie['gestart'] + timedelta(minutes=dit.minutes)):%H:%M}")
            else:
                klaar = ""
            await self._async_tell(
                t("{naam} is gestart{wat}{klaar}.", naam=naam, wat=wat, klaar=klaar)
                if zelf
                else t("{naam} draait{wat}{klaar}.", naam=naam, wat=wat, klaar=klaar)
            )
        # Geen vermogenssensor maar wel een energieteller (Miele, v0.124.0): dan
        # telt de coach per stap van de teller (`_teller_tellen`).
        op_teller = watts is None and not device.get("entity") and bool(device.get("energy_entity"))
        if draait and op_teller:
            self._teller_tellen(settings, sessie, now, _kwh(self.hass, device["energy_entity"]))
        elif draait:
            self._programma_tellen(settings, sessie, now, watts)
            # Het verloop van deze beurt, voor het profiel: minuten sinds de
            # start en wat hij op dat moment trok. Niet uit een teller: die
            # loopt in stappen achter, en dat is geen verloop.
            if watts is not None and sessie["gestart"] is not None and not sessie.get("teller"):
                sessie["punten"].append((_tussen(sessie["gestart"], now).total_seconds() / 60.0, watts))
            # Het gat van een herstart, zodra de kwartieropslag het heeft.
            gat = sessie.get("terugrekenen")
            if gat is not None and now >= (sessie.get("terugrekenen_na") or now):
                sessie["terugrekenen"] = None
                await self._async_programma_terugrekenen(settings, device, sessie, *gat)
            # Elke vijf minuten naar de opslag, en meteen als de beurt net
            # begint: zo overleeft een lopende beurt een herstart. Niet bij
            # alleen uitlezen: een sessie is wat de coach liet draaien.
            bewaard = sessie.get("bewaard")
            if not alleen_lezen and (bewaard is None or (now - bewaard).total_seconds() >= 300):
                sessie["bewaard"] = now
                self._beurt_schrijven(self._programma_regel(device, naam, sessie, now, now, klaar=False))
        sessie["laatst"] = now

        mag = level == LEVEL_STEER or (level == LEVEL_PROPOSE and device_id in self._approved)
        if draait and eind is not None and eind > now and decision.rule == "running":
            decision = replace(decision, reason=t("Hij draait, klaar rond {klok}.", klok=f"{eind:%H:%M}"))
        self.state[device_id] = {
            **asdict(decision),
            "kind": "programma",
            "at": now.isoformat(),
            "level": level,
            "applied": mag and level != LEVEL_READ and level != LEVEL_ADVISE,
            "approved": device_id in self._approved,
            "running": draait,
            "started_at": sessie["gestart"].isoformat() if sessie["gestart"] else None,
            "ends_at": eind.isoformat() if draait and eind is not None else None,
            "released": released,
            # Volgen zonder te starten (v0.127.0), voor de kaart en het paneel.
            "read_only": alleen_lezen,
            "start_now": nu_starten,
            # De klaar-tijd uit het schema, voor de kaart: "klaar vóór 07:00" (v0.110.0).
            "deadline": window.deadline.isoformat() if window.deadline is not None else None,
            # De klaar-tijd van vandaag als die voorbij is, en de dag waar het
            # schema dan naar opschuift: de kaart vraagt dan morgen of nu.
            "missed": window.missed.isoformat() if window.missed is not None and window.deadline is not None else None,
            "later": _dagnaam(window.deadline, now) if window.missed is not None and window.deadline is not None else None,
            "manual": handmatig,
            "program": programma.key if programma is not None else "",
            # De naam zoals de machine hem noemt, voor de kaart (v0.124.0).
            "program_label": programma.label if programma is not None else "",
            # Hoe lang het programma duurt, voor "Wat gaat hij doen" (v0.133.0).
            "program_minutes": programma.minutes if programma is not None else None,
            "tip": "",
        }
        await self._async_noteer_programma(device, device_id, now)

        # Klaar: verslag, opslag, vrijgave eraf.
        if status in KLAAR or (sessie["gestart"] is not None and not draait and status in ("ready", "inactive", "")):
            if sessie["gestart"] is not None and "klaar" not in sessie["gemeld"]:
                sessie["gemeld"].add("klaar")
                gat = sessie.get("terugrekenen")
                if gat is not None:
                    sessie["terugrekenen"] = None
                    await self._async_programma_terugrekenen(settings, device, sessie, *gat)
                # Zonder statussensor is "klaar" het moment waarop hij voor het
                # laatst iets trok, niet het moment waarop de coach dat doorhad.
                einde = sessie.get("laatst_actief") if handmatig else None
                await self._async_programma_klaar(
                    settings, device, naam, sessie, now, einde or now, uit=status != "ready"
                )
            return

        if not (decision.charge and mag) or draait or status in KLAAR:
            return

        if handmatig:
            # Geen knop om op te drukken: de bewoner krijgt het te horen, één
            # keer, en nog één keer als er na drie kwartier niets gebeurt.
            gevraagd = sessie.get("gevraagd")
            # De reden zegt al "zet hem nu aan"; met de naam erin wordt dat
            # "Zet Vaatwasser nu aan: dit is het goedkoopste moment ...".
            reden = decision.reason
            # De reden komt uit planner.py, in de taal van nu; het begin dus ook.
            for kop in (t("Zet hem nu aan"), t("Zet hem meteen aan")):
                if reden.startswith(kop):
                    reden = reden[len(kop):]
                    break
            else:
                reden = ". " + reden
            if gevraagd is None:
                sessie["gevraagd"] = now
                await self._async_tell(t("Zet {naam} nu aan{reden}", naam=naam, reden=reden), kritiek=True)
            elif now - gevraagd >= HERINNERING and "herinnerd" not in sessie["gemeld"]:
                sessie["gemeld"].add("herinnerd")
                await self._async_tell(
                    t("{naam} staat nog steeds uit; de coach vroeg om {klok} om hem aan te zetten",
                      naam=naam, klok=f"{gevraagd:%H:%M}")
                    + (reden if reden.startswith(":") else "."),
                    kritiek=True,
                )
            return

        # Starten, en kijken of het lukt. Maar niet drukken op een knop die er
        # niet is: Home Connect Local zet de startknop op `unavailable` zolang
        # de machine geen start aanneemt (thuis op 23-09-2026: met de deur
        # open is `ActiveProgram` alleen leesbaar, met de deur dicht is de knop
        # er meteen, ook met de stroom uit), en Home Assistant slaat een dienst
        # op een onbeschikbare entiteit stilzwijgend over. Drukken zou dan
        # een poging kosten zonder dat er iets gebeurt. Dus wachten tot de
        # knop terug is, en na START_WACHT één keer zeggen waar het aan ligt.
        # Hetzelfde voor "starten op afstand" als de integratie dat zegt.
        gedrukt = sessie.get("gedrukt")
        if gedrukt is None and sessie["pogingen"] < START_POGINGEN:
            knop = _text(self.hass, entities.get("start"))
            afstand = _text(self.hass, entities.get("remote_start")).strip()
            waarom = None
            if knop == "unavailable":
                waarom = (
                    t("De deur staat open.")
                    if deur_open
                    else t("Zet de machine aan en kijk of starten op afstand aan staat.")
                )
            elif afstand == "off":
                waarom = t("Zet starten op afstand aan op het apparaat.")
            if waarom is not None:
                weg = sessie.get("knop_weg") or now
                sessie["knop_weg"] = weg
                if now - weg >= START_WACHT and "knop-weg" not in sessie["gemeld"]:
                    sessie["gemeld"].add("knop-weg")
                    await self._async_tell(
                        t("De coach wil {naam} starten, maar de machine neemt nu geen start aan. {waarom}",
                          naam=naam, waarom=waarom),
                        kritiek=True,
                    )
                return
            sessie["knop_weg"] = None
        if gedrukt is None:
            if sessie["pogingen"] >= START_POGINGEN:
                return
            await self._async_druk(device, "start")
            sessie["gedrukt"] = now
            sessie["pogingen"] += 1
            return
        if now - gedrukt >= START_WACHT and "start-mislukt" not in sessie["gemeld"]:
            sessie["gemeld"].add("start-mislukt")
            waarom = (
                t("De deur staat open.")
                if deur_open
                else t("Kijk of starten op afstand aan staat op het apparaat en of de deur dicht is.")
            )
            await self._async_tell(
                t("De coach heeft {naam} om {klok} gestart, maar hij is niet gaan draaien. {waarom}",
                  naam=naam, klok=f"{gedrukt:%H:%M}", waarom=waarom),
                kritiek=True,
            )
        if now - gedrukt >= START_OPNIEUW and sessie["pogingen"] < START_POGINGEN:
            await self._async_druk(device, "start")
            sessie["gedrukt"] = now
            sessie["pogingen"] += 1

    @staticmethod
    def _lege_programma_sessie(now: datetime) -> dict[str, Any]:
        return {
            "vrijgegeven": None,   # wanneer de bewoner hem vrijgaf
            "gedrukt": None,       # wanneer de coach het laatst op start drukte
            "pogingen": 0,
            "gestart": None,       # wanneer hij ging draaien
            "door_coach": False,   # of de coach hem startte of erom vroeg
            "kwh": 0.0,
            "zon_kwh": 0.0,
            "betaald": 0.0,
            "maat": 0.0,           # wat meteen starten, alles van het net, gekost had
            "maat_onbekend": False,
            "zon_winst": 0.0,      # wat de eigen zon scheelde tegenover inkopen
            "accu_kwh": 0.0,       # wat er uit de thuisbatterij kwam; zie `_herkomst_bij`
            "net_eur": 0.0,        # wat er werkelijk van het net kwam, in euro
            "laatst": now,
            "gemeld": set(),
            "programma": None,
            "prijzen": [],
            # Het verloop: (minuten sinds de start, watt), voor het profiel.
            "punten": [],
            # Zonder statussensor: wanneer hij voor het laatst iets trok, en
            # sinds wanneer hij stil is.
            "laatst_actief": None,
            "stil_sinds": None,
            # Zonder startknop: wanneer de coach vroeg om hem aan te zetten.
            "gevraagd": None,
            # De vrijgaveschakelaar en de vrijgave zoals ze de vorige ronde
            # stonden, om te zien wie er bewoog.
            "schakelaar": None,
            "vrij_vorig": None,
            # Wanneer de lopende beurt voor het laatst naar de opslag ging, en
            # onder welke sleutel; die blijft dezelfde, ook als het
            # terugrekenen het vrijgavemoment nog vindt.
            "bewaard": None,
            "regel_id": None,
            # Na een herstart: het stuk (van, tot) dat nog uit de
            # kwartieropslag moet komen, en vanaf wanneer dat mag.
            "terugrekenen": None,
            "terugrekenen_na": None,
            # Of deze coach het apparaat al eens gezien heeft; zie `eerste`.
            "gezien": False,
            # De eindtijd van het apparaat zoals de coach hem gelooft, en de
            # waarde die er de vorige ronde stond; zie `_eindtijd_vast`.
            "eind": None,
            "eind_gezien": None,
            # Sinds wanneer de coach wil drukken maar de startknop er niet is
            # (Home Connect Local met de deur open), of starten op afstand uit staat.
            "knop_weg": None,
            # De vrijgaveknop zoals hij de vorige ronde stond (het tijdstip van
            # de laatste druk), en of er na het besluit een melding moet komen.
            "knop": None,
            "knop_melden": False,
            # Zonder vrijgave: na een beurt eerst uitruimen (de klep open en weer
            # dicht) voordat klep dicht weer vrijgegeven is; zie `_async_klep_volgen`.
            "klep_uitruimen": False,
            "klep_open_gezien": False,
            # Zonder vermogenssensor, met een energieteller (Miele, v0.124.0):
            # of er geteld wordt, de stand bij de vorige stap, en de ronden
            # sinds die stap (`_teller_tellen`).
            "teller": False,
            "teller_waarde": None,
            "teller_ronden": [],
            # De duur die de machine per programma gaf zolang hij klaarstond.
            "machine_duur": {},
        }

    def _teller_tellen(
        self, settings: dict[str, Any], sessie: dict[str, Any], now: datetime, waarde: float | None
    ) -> None:
        """Een beurt tellen op een energieteller, voor een machine zonder vermogenssensor (v0.124.0).

        Miele geeft per programma een teller in kWh, in stappen van een tiende,
        en geen watt. Elke ronde gaat in een buffer: hoe lang hij was, de prijs,
        en wat de meter naar het net zag gaan. Zet de teller een stap, dan wordt
        die stap over de ronden sinds de vorige verdeeld. Hoeveel daarvan zon
        was volgt uit de meter over dezelfde ronden: wat er netto terugging plus
        de stap is wat er zonder de machine terug was gegaan. Zo liggen de twee
        altijd naast elkaar; een vermogen uit de teller loopt een stap achter, en
        dat telde in het virtuele huis 's nachts zon. Een teller die terugvalt
        begint een nieuw programma.
        """
        uren = max(0.0, (now - sessie["laatst"]).total_seconds()) / 3600.0
        if not sessie.get("teller"):
            # De eerste ronde van de beurt: alleen de stand van nu onthouden.
            sessie["teller"] = True
            sessie["teller_waarde"] = waarde
            sessie["teller_ronden"] = []
            return
        if 0 < uren <= 0.5:
            koop, terug = self._prijs_nu(settings, now)
            koop_toen = None
            vrij, gestart = sessie.get("vrijgegeven"), sessie.get("gestart")
            if vrij is not None and gestart is not None:
                toen = vrij + (now - gestart)
                rij = price_now(sessie.get("prijzen") or [], toen)
                koop_toen = rij["price"] if rij is not None else self._prijs_nu(settings, toen)[0]
            sessie["teller_ronden"].append({
                "uren": uren, "koop": koop, "terug": terug, "export_w": self._netto_export_w(settings),
                "accu": self._uit_accu(settings), "koop_toen": koop_toen,
            })
        vorige = sessie.get("teller_waarde")
        if waarde is None or (vorige is not None and abs(waarde - vorige) < 1e-9):
            return
        # Een teller die terugvalt begint een nieuw programma (Miele zet hem op nul). De teller van
        # een smart plug telt alles wat de stekker ooit doorliet (v0.177.0); zakt die een tikje,
        # dan is dat een hapering en geen nieuw begin, en anders telde zijn hele stand als één stap.
        if vorige is not None and vorige / 2 <= waarde < vorige:
            return
        stap = waarde - vorige if vorige is not None and waarde >= vorige else waarde
        sessie["teller_waarde"] = waarde
        ronden = sessie.get("teller_ronden") or []
        sessie["teller_ronden"] = []
        if stap <= 0:
            return
        totaal = sum(r["uren"] for r in ronden)
        if not ronden or totaal <= 0:
            koop, terug = self._prijs_nu(settings, now)
            ronden = [{"uren": 1.0, "koop": koop, "terug": terug, "export_w": None, "accu": self._uit_accu(settings),
                       "koop_toen": koop}]
            totaal = 1.0
        # Wat er zonder de machine terug was gegaan, over dezelfde ronden.
        if all(r["export_w"] is not None for r in ronden):
            terug_kwh = sum(r["export_w"] * r["uren"] for r in ronden) / 1000.0
            zon_deel = max(0.0, min(1.0, (terug_kwh + stap) / stap))
        else:
            zon_deel = 0.0
        for r in ronden:
            kwh = stap * r["uren"] / totaal
            deel = zon_deel if r["terug"] is not None else 0.0
            sessie["kwh"] += kwh
            sessie["zon_kwh"] += kwh * deel
            rest = kwh * (1.0 - deel)
            accu = rest * r["accu"]
            sessie["accu_kwh"] = float(sessie.get("accu_kwh") or 0.0) + accu
            if r["koop"] is not None:
                if not sessie.get("net_eur_onbekend"):
                    sessie["net_eur"] = float(sessie.get("net_eur") or 0.0) + (rest - accu) * r["koop"]
                sessie["betaald"] += kwh * ((1 - deel) * r["koop"] + deel * (r["terug"] or 0.0))
                sessie["zon_winst"] += kwh * deel * max(0.0, r["koop"] - (r["terug"] or 0.0))
            if sessie.get("vrijgegeven") is not None and sessie.get("gestart") is not None:
                if r["koop_toen"] is None:
                    sessie["maat_onbekend"] = True
                else:
                    sessie["maat"] += kwh * r["koop_toen"]

    def _teller_afronden(
        self, settings: dict[str, Any], device: dict[str, Any], sessie: dict[str, Any], now: datetime
    ) -> None:
        """Aan het eind: de laatste stap van de teller nog meetellen (v0.124.0).

        Miele zet de teller soms pas bij "afgelopen" op zijn laatste stand, en
        in die ronde draait hij al niet meer.
        """
        if sessie.get("teller") and device.get("energy_entity"):
            self._teller_tellen(settings, sessie, now, _kwh(self.hass, device["energy_entity"]))

    async def _async_machine_programma(
        self, entities: dict[str, Any], ruw: str, sessie: dict[str, Any], now: datetime
    ) -> Programma | None:
        """Een programma dat de coach nog niet gemeten heeft, met de duur van de machine (v0.124.0).

        De eigenaar op 15-10-2026 koos: plannen op de duur die de machine zelf
        geeft, alsof het verbruik gelijk over die duur valt, zonder kWh. Die duur
        is de resterende tijd zolang het programma klaarstaat; draait hij al,
        dan wat er bij het klaarstaan stond, of anders gedraaid plus resterend.
        Zonder duur is er niets te plannen, en dan None.
        """
        duur = sessie.setdefault("machine_duur", {})
        eind = _eindtijd(self.hass, entities.get("remaining"), now)
        minuten = (eind - now).total_seconds() / 60.0 if eind is not None else None
        if minuten is not None and minuten > 0 and sessie.get("gestart") is None:
            duur[ruw] = int(round(minuten))
        elif minuten is not None and minuten > 0 and ruw not in duur:
            duur[ruw] = int(round(minuten + _tussen(sessie["gestart"], now).total_seconds() / 60.0))
        if not duur.get(ruw):
            return None
        naam = await self._async_staat_naam(entities.get("program"), ruw)
        return Programma(ruw, naam, duur[ruw], 1.0, 0, kwh_bekend=False)

    async def _async_staat_naam(self, entity_id: str | None, waarde: str) -> str:
        """Een stand zoals Home Assistant hem in de eigen taal noemt: "cottons" is "Katoen".

        Uit de vertalingen van de integratie, via de `translation_key` van de
        entiteit (v0.124.0). Lukt dat niet, dan de waarde zelf, netjes.
        """
        sleutel = (str(entity_id or ""), waarde)
        if sleutel in self._staat_namen:
            return self._staat_namen[sleutel]
        naam = None
        try:
            from homeassistant.helpers import entity_registry as er
            from homeassistant.helpers.translation import async_get_translations

            rij = er.async_get(self.hass).async_get(entity_id) if entity_id else None
            if rij is not None and rij.translation_key and rij.platform:
                teksten = await async_get_translations(
                    self.hass, self.hass.config.language, "entity", {rij.platform}
                )
                domein = str(entity_id).split(".")[0]
                naam = teksten.get(
                    f"component.{rij.platform}.entity.{domein}.{rij.translation_key}.state.{waarde}"
                )
        except Exception:  # noqa: BLE001 - zonder vertaling de waarde zelf
            naam = None
        naam = naam or (waarde.replace("_", " ").strip().capitalize() or waarde)
        self._staat_namen[sleutel] = naam
        return naam

    @staticmethod
    def _status_uit_vermogen(sessie: dict[str, Any], now: datetime, watts: float | None) -> str:
        """De toestand van een apparaat op een meetstekker, uit het vermogen alleen.

        Boven DRAAI_W draait hij. Daaronder, terwijl er een beurt bezig was:
        nog even draaien, want tussen twee spoelgangen staat hij stil, en na
        STIL_KLAAR is hij klaar. Zonder beurt bezig: gereed.
        """
        if watts is not None and watts >= DRAAI_W:
            sessie["laatst_actief"] = now
            sessie["stil_sinds"] = None
            return "run"
        if sessie.get("gestart") is None:
            return "ready"
        stil = sessie.get("stil_sinds") or now
        sessie["stil_sinds"] = stil
        return "run" if _tussen(stil, now) < STIL_KLAAR else "finished"

    async def _async_druk(self, device: dict[str, Any], knop: str) -> None:
        """Op een knop van het apparaat drukken: bij Home Connect een button-entiteit."""
        entity_id = (device.get("entities") or {}).get(knop)
        if not entity_id:
            raise ServiceNotFound("button", "press")
        domein = entity_id.split(".")[0]
        dienst = {"button": "press", "switch": "turn_on", "script": "turn_on"}.get(domein, "press")
        await self.hass.services.async_call(domein, dienst, {"entity_id": entity_id}, blocking=True)

    def _meter_bijhouden(self, settings: dict[str, Any], now: datetime) -> None:
        """Elke ronde wat er naar het net gaat, voor `_meter_zeker`."""
        waarde = self._netto_export_w(settings)
        if waarde is not None:
            self._meter.append((now, waarde))
        grens = now - METER_VENSTER
        while self._meter and self._meter[0][0] < grens:
            self._meter.pop(0)

    def _meter_zeker(self, now: datetime) -> float | None:
        """Wat de meter de afgelopen METER_VENSTER ten minste naar het net zag
        gaan, of None zolang er nog geen METER_DEKKING gemeten is."""
        binnen = [w for t, w in self._meter if now - METER_VENSTER <= t <= now]
        if not binnen or now - self._meter[0][0] < METER_DEKKING:
            return None
        return min(binnen)

    def _netto_export_w(self, settings: dict[str, Any]) -> float | None:
        """Wat er naar het net zou gaan als er geen thuisbatterij was, of None.

        Positief bij teruglevering. Wat een batterij opslokt is zon die de
        vaatwasser of de boiler ook had kunnen nemen, en wat hij afgeeft is
        geen zon; zie `_batterijen_w`.
        """
        kaal = self._netto_export_kaal(settings)
        return None if kaal is None else kaal + self._batterijen_w(settings)

    def _netto_export_kaal(self, settings: dict[str, Any]) -> float | None:
        """Wat er nu werkelijk naar het net gaat, positief bij teruglevering, of None."""
        sources = settings.get("sources") or {}
        if sources.get("grid_mode") == "signed":
            signed = _watts(self.hass, sources.get("grid_signed"))
            if signed is None:
                return None
            if sources.get("grid_signed_invert"):
                signed = -signed
            return -signed
        export = _watts(self.hass, sources.get("grid_export"))
        invoer = _watts(self.hass, sources.get("grid_import"))
        if export is None and invoer is None:
            return None
        return (export or 0.0) - (invoer or 0.0)

    def _uit_accu(self, settings: dict[str, Any]) -> float:
        """Welk deel van wat nu niet van de zon komt uit een thuisbatterij komt, 0 tot 1 (v0.101.0).

        Wat het huis niet uit de zon haalt komt van het net of uit de batterij,
        en die twee delen alles wat er draait naar rato. Bij de eigenaar op 28-09-2026:
        een vaatwasser van 0,91 kWh kreeg 0,33 van de zon, 0,55 uit de Anker en
        0,03 van het net, en het verslag zei alleen "door de zon". Zonder meter
        is het onbekend, en dan is het nul: niet gokken.
        """
        afgifte = 0.0
        for device in settings.get("devices") or []:
            if device.get("type") == "thuisbatterij":
                afgifte += max(0.0, -(self._batterij_geregeld_w(device) or 0.0))
        if afgifte <= 0:
            return 0.0
        kaal = self._netto_export_kaal(settings)
        if kaal is None:
            return 0.0
        invoer = max(0.0, -kaal)
        return afgifte / (afgifte + invoer)

    def _herkomst_bij(
        self, teller: dict[str, Any], settings: dict[str, Any], kwh: float, zon_deel: float,
        koop: float | None,
    ) -> None:
        """Wat niet van de zon kwam verdeeld over thuisbatterij en net (v0.101.0).

        Het geld verandert hier niet: het deel uit de batterij telt in `betaald`
        als stroom van het net, want wat de batterij daarmee verdient staat in
        haar eigen kasboek (`verdiend`), en twee keer tellen maakt Bespaard te
        mooi. `net_eur` is alleen wat er werkelijk van het net kwam, voor het
        verslag.
        """
        rest = kwh * max(0.0, 1.0 - zon_deel)
        accu = rest * self._uit_accu(settings)
        teller["accu_kwh"] = float(teller.get("accu_kwh") or 0.0) + accu
        # Een beurt die liep toen de coach bijgewerkt werd heeft geen begin van
        # dit bedrag; dan liever geen bedrag dan een te laag (`net_eur_onbekend`).
        if koop is not None and not teller.get("net_eur_onbekend"):
            teller["net_eur"] = float(teller.get("net_eur") or 0.0) + (rest - accu) * koop

    @staticmethod
    def _herkomst_velden(teller: dict[str, Any]) -> dict[str, Any]:
        """Wat een beurt uit de thuisbatterij en van het net kreeg, voor de opslag."""
        return {
            "battery_kwh": round(float(teller.get("accu_kwh") or 0.0), 3),
            "grid_cost": None if teller.get("net_eur_onbekend") else round(float(teller.get("net_eur") or 0.0), 4),
        }

    @staticmethod
    def _herkomst_tekst(teller: dict[str, Any]) -> str:
        """De zin over waar de stroom van een beurt vandaan kwam; zie `_herkomst_zin`."""
        kwh = float(teller.get("kwh") or 0.0)
        zon = float(teller.get("zon_kwh") or 0.0)
        accu = float(teller.get("accu_kwh") or 0.0)
        net = max(0.0, kwh - zon - accu)
        net_eur = None if teller.get("net_eur_onbekend") else float(teller.get("net_eur") or 0.0)
        return _herkomst_zin(zon, accu, net, net_eur)

    def _programma_tellen(
        self, settings: dict[str, Any], sessie: dict[str, Any], now: datetime, watts: float | None
    ) -> None:
        """Wat deze ronde kostte, en wat hij gekost had als hij meteen was gestart.

        Dezelfde maat als bij een laadbeurt (de eigenaar op 05-09-2026: "de prijs
        vanaf het inpluggen"): hetzelfde verbruik, verschoven naar het moment
        van vrijgeven, en dan alles van het net tegen de prijs van toen. Zon
        telt in het betaalde tegen de terugleverprijs, en wat dat scheelde
        tegenover inkopen loopt apart mee (`zon_winst`), zodat Bespaard kan
        zeggen wat de zon deed en wat het wachten. De eigenaar op 09-09-2026: "wat je
        op zonne-energie laadt bespaar je natuurlijk ook door minder stroom in
        te kopen." Eén dag eerder rekende de maat de zon van het
        vrijgavemoment mee en stond een beurt die meteen op zon startte op nul.
        """
        if watts is None or watts <= 0:
            return
        uren = max(0.0, (now - sessie["laatst"]).total_seconds()) / 3600.0
        if uren <= 0 or uren > 0.5:
            return
        kwh = watts / 1000.0 * uren
        koop, terug = self._prijs_nu(settings, now)
        export = self._netto_export_w(settings)
        zon_deel = 0.0
        if export is not None and terug is not None:
            zon_deel = max(0.0, min(1.0, (export + watts) / watts))
        sessie["kwh"] += kwh
        sessie["zon_kwh"] += kwh * zon_deel
        self._herkomst_bij(sessie, settings, kwh, zon_deel, koop)
        if koop is not None:
            sessie["betaald"] += kwh * ((1 - zon_deel) * koop + zon_deel * (terug or 0.0))
            sessie["zon_winst"] += kwh * zon_deel * max(0.0, koop - (terug or 0.0))
        # De maat: hetzelfde kwartier, maar dan geteld vanaf het vrijgeven,
        # alles van het net.
        vrij = sessie.get("vrijgegeven")
        gestart = sessie.get("gestart")
        if vrij is not None and gestart is not None:
            toen = vrij + (now - gestart)
            rij = price_now(sessie.get("prijzen") or [], toen)
            if rij is not None:
                koop_toen = rij["price"]
            else:
                koop_toen, _ = self._prijs_nu(settings, toen)
            if koop_toen is None:
                sessie["maat_onbekend"] = True
            else:
                sessie["maat"] += kwh * koop_toen

    @staticmethod
    def _bespaard_zin(totaal: float) -> str:
        """Eén korte regel voor in het verslag: wat er bespaard is.

        `totaal` is de maat min het betaalde: wat dezelfde beurt gekost had
        als alles van het net was gekomen op het moment van vrijgeven of
        inpluggen. Tot v0.102.1 stond erbij waardoor (de zon, het wachten, en
        bij salderen waarom eigen zon zo weinig scheelt); dat maakte het
        verslag te lang voor een telefoon. De uitsplitsing staat in het paneel,
        onder Bespaard (`zon_winst` in de beurt).
        """
        return t("Bespaard {bedrag}.", bedrag=_bedrag(totaal))

    async def _async_programma_klaar(
        self,
        settings: dict[str, Any],
        device: dict[str, Any],
        naam: str,
        sessie: dict[str, Any],
        now: datetime,
        einde: datetime | None = None,
        meten: bool = True,
        uit: bool = True,
    ) -> None:
        """Het verslag, de beurt in de opslag, de meting bewaren, en de vrijgave eraf.

        `meten` uit als het einde niet echt gezien is (afgelopen terwijl de
        coach weg was): een te korte duur hoort niet in de tabel. Een
        afgebroken programma (v0.127.0) meet ook niet, en het verslag zegt
        "afgebroken", met het hele verloop erbij (v0.128.1): wanneer hij
        startte, wanneer hij stilviel en wanneer hij uit ging (`uit`) of een
        nieuw programma klaarstond. Bij alleen uitlezen geen sessie en geen
        vrijgave: de coach liet hem niet draaien en komt niet aan de schakelaars.
        """
        afgebroken = bool(sessie.get("afgebroken"))
        alleen_lezen = _programma_alleen_lezen(device)
        programma = sessie.get("programma")
        gestart: datetime = sessie["gestart"]
        einde = einde or now
        self._teller_afronden(settings, device, sessie, now)
        kwh = sessie["kwh"]
        betaald = sessie["betaald"]
        maat = None if sessie["maat_onbekend"] or sessie["vrijgegeven"] is None else sessie["maat"]
        wat = f" ({t(programma.label)})" if programma is not None else ""
        # Waar het vandaan kwam, en het bedrag bij het net: de eigenaar op
        # 28-09-2026 las "ongeveer € 0,199" bij een beurt op zon en
        # thuisbatterij, en "er is niks van het net af gehaald" (v0.101.0).
        herkomst = self._herkomst_tekst(sessie) if kwh > 0 else ""
        bespaard = ""
        if maat is not None and kwh > 0 and maat - betaald >= 0.005:
            bespaard = self._bespaard_zin(maat - betaald)
        wanneer = t("{van} tot {tot}.", van=f"{gestart:%H:%M}", tot=f"{einde:%H:%M}")
        onderbroken = sessie.get("onderbroken_om") if afgebroken else None
        if onderbroken is not None:
            # De eigenaar op 16-10-2026: "ik wil een compleet verslag". Tot
            # v0.128.1 stond er alleen van de start tot het uitgaan, en zag je
            # niet dat hij het grootste deel daarvan stillag.
            klokken = {"start": f"{gestart:%H:%M}", "stil": f"{onderbroken:%H:%M}", "einde": f"{einde:%H:%M}"}
            wanneer = (
                t("gestart om {start}, onderbroken om {stil}, uit om {einde}.", **klokken)
                if uit
                else t("gestart om {start}, onderbroken om {stil}, afgebroken om {einde}.", **klokken)
            )
        wanneer = f"{_kwh_tekst(kwh)}, {wanneer}" if kwh > 0 else wanneer[:1].upper() + wanneer[1:]
        await self._async_tell(_verslag(
            t("{naam} is afgebroken{wat}.", naam=naam, wat=wat)
            if afgebroken
            else t("{naam} is klaar{wat}.", naam=naam, wat=wat),
            wanneer,
            herkomst,
            bespaard,
        ))
        # Wat er gemeten is gaat in de instellingen, zodat de volgende beurt
        # met de echte duur, het echte verbruik en het verloop rekent.
        if meten and not afgebroken:
            await self._async_meting_bewaren(settings, device, programma, sessie, gestart, einde)
        if not alleen_lezen:
            self._beurt_schrijven(self._programma_regel(device, naam, sessie, now, einde, klaar=True))
            # De vrijgave eraf, en de schakelaar mee: de volgende lading vraagt
            # om een nieuwe.
            await self._async_vrijgave_zetten(settings, device.get("id", ""), False)
            await self._async_schakelen(device, False)
            await self._async_schakelen(device, False, "release_now_switch")
        self._programma[device.get("id", "")] = {
            **self._lege_programma_sessie(now), "gezien": True, "knop": sessie.get("knop"),
            "klep_uitruimen": device.get("release_required") is False,
        }

    def _programma_regel(
        self,
        device: dict[str, Any],
        naam: str,
        sessie: dict[str, Any],
        now: datetime,
        einde: datetime,
        klaar: bool,
    ) -> dict[str, Any]:
        """De beurt van een programma-apparaat zoals hij in de opslag staat.

        Een lopende beurt staat er ook al in, met `complete` op false en
        alles wat de coach nodig heeft om hem na een herstart op te pakken
        (`session`); de afgeronde regel heeft dat niet meer nodig.
        """
        programma = sessie.get("programma")
        gestart: datetime = sessie["gestart"]
        vrij = sessie.get("vrijgegeven") or gestart
        kwh = sessie["kwh"]
        betaald = sessie["betaald"]
        maat = None if sessie["maat_onbekend"] or sessie["vrijgegeven"] is None else sessie["maat"]
        if not sessie.get("regel_id"):
            sessie["regel_id"] = f"{device.get('id', '')}:{vrij.replace(microsecond=0).isoformat()}"
        regel = {
            "id": sessie["regel_id"],
            "device": device.get("id", ""),
            "name": naam,
            "kind": "programma",
            "car": programma.label if programma is not None else "",
            "program": programma.key if programma is not None else "",
            "plugged_at": vrij.replace(microsecond=0).isoformat(),
            "started": gestart.replace(microsecond=0).isoformat(),
            "ended": einde.replace(microsecond=0).isoformat(),
            "kwh": round(kwh, 3),
            "solar_kwh": round(sessie["zon_kwh"], 3),
            "paid": round(betaald, 4),
            "ref_price": None,
            "ref_feed_in": None,
            "ref_cost": None if maat is None else round(maat, 4),
            "saved": None if maat is None else round(max(0.0, maat - betaald), 4),
            "solar_saved": round(sessie.get("zon_winst") or 0.0, 4),
            **self._herkomst_velden(sessie),
            "price_unknown": maat is None,
            "unknown_kwh": 0.0,
            "baseline": {"kwh": round(kwh, 3), "cost": None if maat is None else round(maat, 4),
                         "unknown_kwh": 0.0, "points": []},
            "resumed": False,
            "complete": klaar,
        }
        if not klaar:
            regel["session"] = {
                "released": sessie["vrijgegeven"].isoformat() if sessie.get("vrijgegeven") else None,
                "prices": [
                    {"start": r["start"].isoformat(), "end": r["end"].isoformat(),
                     "price": r.get("price"), "feed_in": r.get("feed_in")}
                    for r in (sessie.get("prijzen") or [])
                ],
                "points": [[round(m, 2), round(w, 1)] for m, w in (sessie.get("punten") or [])],
                "told": sorted(sessie.get("gemeld") or ()),
                "asked": sessie["gevraagd"].isoformat() if sessie.get("gevraagd") else None,
                "ref_cost_unknown": bool(sessie["maat_onbekend"]),
                "ref_cost": round(sessie["maat"], 4),
            }
        return regel

    async def _async_programma_hervatten(
        self,
        settings: dict[str, Any],
        device: dict[str, Any],
        sessie: dict[str, Any],
        tabel: tuple[Any, ...],
        now: datetime,
    ) -> None:
        """Een beurt die al liep toen de coach begon, oppakken waar hij was.

        De eigenaar op 07-09-2026, over een herstart midden in een vaatwasserbeurt:
        "ja, reken terug." Stond de beurt in de opslag (elke vijf minuten
        bewaard), dan gaan de tellers daar verder en komt alleen het gat
        sinds die opslag uit de kwartieropslag. Stond er niets, dan zegt de
        recorder wanneer hij ging draaien, de vrijgaveschakelaar wanneer hij
        werd vrijgegeven, en komt de hele beurt tot nu uit de kwartieropslag.
        Lukt ook dat niet, dan begint de beurt gewoon nu, zoals eerst.
        """
        device_id = device.get("id", "")
        regel = self._beurt_open.get(device_id)
        if regel is not None and regel.get("kind") == "programma":
            self._beurt_open.pop(device_id, None)
            if self._programma_uit_regel(sessie, regel, tabel):
                van = _tijdstip(regel.get("ended"))
                van = van.replace(tzinfo=None) if van is not None else sessie["gestart"]
                sessie["terugrekenen"] = (min(van, now), now)
                sessie["terugrekenen_na"] = now + TERUGREKENEN_WACHT
                return
        try:
            gestart, vrij = await self._async_programma_begin(device, sessie, now)
        except Exception:  # noqa: BLE001 - liever nu beginnen dan een ronde die omvalt
            _LOGGER.exception("kon het begin van de beurt van %s niet vinden", device_id)
            return
        if gestart is None:
            return
        sessie["gestart"] = gestart
        # Een apparaat dat de coach alleen uitleest staat nooit in de opslag. Liep hij langer
        # dan de melding op zich laat wachten, dan kwam "draait" al voor de herstart; zonder
        # dit kwam hij na elke herstart opnieuw (de klantwoning, 23-10-2026: "Droger draait"
        # om 11:29 en om 11:56). Een apparaat dat hij stuurt zonder regel is iets anders: dan
        # was de coach er niet bij toen het begon, en dan hoort de melding er wel.
        if _programma_alleen_lezen(device) and _tussen(gestart, now) > EINDTIJD_WACHT:
            sessie["gemeld"].add("gestart")
        sessie["vrijgegeven"] = vrij
        sessie["terugrekenen"] = (gestart, now)
        sessie["terugrekenen_na"] = now + TERUGREKENEN_WACHT

    @staticmethod
    def _programma_uit_regel(
        sessie: dict[str, Any], regel: dict[str, Any], tabel: tuple[Any, ...]
    ) -> bool:
        """De sessie zoals hij in de opslag stond; False als de regel niet deugt."""
        gestart = _tijdstip(regel.get("started"))
        if gestart is None:
            return False
        extra = regel.get("session") or {}
        vrij = _tijdstip(extra.get("released"))
        gevraagd = _tijdstip(extra.get("asked"))
        prijzen = []
        for r in extra.get("prices") or []:
            try:
                prijzen.append({
                    "start": datetime.fromisoformat(r["start"]), "end": datetime.fromisoformat(r["end"]),
                    "price": r.get("price"), "feed_in": r.get("feed_in"),
                })
            except (KeyError, TypeError, ValueError):
                continue
        sessie["gestart"] = gestart.replace(tzinfo=None)
        sessie["vrijgegeven"] = vrij.replace(tzinfo=None) if vrij is not None else None
        sessie["gevraagd"] = gevraagd.replace(tzinfo=None) if gevraagd is not None else None
        sessie["programma"] = programma_van(regel.get("program") or None, tabel) or sessie.get("programma")
        sessie["prijzen"] = prijzen
        sessie["kwh"] = float(regel.get("kwh") or 0.0)
        sessie["zon_kwh"] = float(regel.get("solar_kwh") or 0.0)
        sessie["betaald"] = float(regel.get("paid") or 0.0)
        sessie["maat"] = float(extra.get("ref_cost") or 0.0)
        sessie["maat_onbekend"] = bool(extra.get("ref_cost_unknown"))
        sessie["zon_winst"] = float(regel.get("solar_saved") or 0.0)
        sessie["accu_kwh"] = float(regel.get("battery_kwh") or 0.0)
        sessie["net_eur"] = float(regel.get("grid_cost") or 0.0)
        sessie["net_eur_onbekend"] = regel.get("grid_cost") is None and sessie["kwh"] > 0
        sessie["punten"] = [
            (float(p[0]), float(p[1])) for p in (extra.get("points") or []) if len(p) == 2
        ]
        sessie["gemeld"] = set(extra.get("told") or ())
        sessie["regel_id"] = regel.get("id")
        return True

    async def _async_programma_begin(
        self, device: dict[str, Any], sessie: dict[str, Any], now: datetime
    ) -> tuple[datetime | None, datetime | None]:
        """Wanneer een beurt die de coach niet zag beginnen begon, en wanneer
        hij werd vrijgegeven; None voor wat niet te vinden is."""
        entities = device.get("entities") or {}
        gestart: datetime | None = None
        if entities.get("start") and entities.get("status"):
            # Home Connect: de laatste overgang naar "run" in de recorder.
            vorige: str | None = None
            for moment, toestand in await self._async_geschiedenis(
                entities["status"], now - PROGRAMMA_TERUGKIJK, now
            ):
                plat = toestand.strip().lower().split(".")[-1]
                if plat in DRAAIT and (vorige is None or vorige not in DRAAIT):
                    gestart = moment
                vorige = plat
        elif device.get("entity"):
            # Op een meetstekker: het laatste kwartier waarin hij ging trekken
            # na een stilte van minstens STIL_KLAAR.
            rijen = (await self._async_kwartieren([device["entity"]], now - PROGRAMMA_TERUGKIJK, now)).get(
                device["entity"]
            ) or []
            stil_sinds: datetime | None = now - PROGRAMMA_TERUGKIJK
            for rij in rijen:
                t0 = datetime.fromtimestamp(int(rij["start"]))
                if float(rij.get("gemiddeld") or 0.0) >= DRAAI_W:
                    if stil_sinds is not None and t0 - stil_sinds >= STIL_KLAAR:
                        gestart = t0
                    stil_sinds = None
                elif stil_sinds is None:
                    stil_sinds = t0
        if gestart is None or gestart >= now:
            return None, None
        vrij: datetime | None = None
        if schakelaar := self._vrijgave_entiteit(device):
            for moment, toestand in await self._async_geschiedenis(
                schakelaar, gestart - timedelta(days=3), gestart
            ):
                if toestand == "on":
                    vrij = moment
        return gestart, vrij

    async def _async_programma_terugrekenen(
        self,
        settings: dict[str, Any],
        device: dict[str, Any],
        sessie: dict[str, Any],
        van: datetime,
        tot: datetime,
    ) -> None:
        """Het stuk van een beurt dat de coach niet zag, uit de kwartieropslag.

        Dezelfde tellers als `_programma_tellen` live bijhoudt: kWh, het
        deel dat van eigen zon kwam, wat het kostte, wat meteen starten
        gekost had, en het verloop voor het profiel. Alleen gemeten getallen;
        een kwartier zonder prijs maakt de maat onbekend.
        """
        if tot <= van or not device.get("entity"):
            return
        gestart = sessie["gestart"]
        vrij = sessie.get("vrijgegeven")
        try:
            sources = settings.get("sources") or {}
            netten = _netmeters(sources)
            # Vanaf het vrijgeven, want de maat wil weten wat er toen aan zon
            # over was.
            rijen = await self._async_kwartieren(
                [device["entity"], *netten], min(van, vrij or van) - timedelta(minutes=15), tot
            )
            # De maat rekent met de prijzen vanaf het vrijgeven, dus die
            # horen er ook bij.
            prijs_op = await self._async_prijs_functie(settings, min(van, vrij or van), tot)
        except Exception:  # noqa: BLE001 - dan blijft het gat een gat
            _LOGGER.exception("terugrekenen van de beurt van %s mislukt", device.get("id", ""))
            return
        per_start = {e: {int(r["start"]): float(r.get("gemiddeld") or 0.0) for r in rijen.get(e) or []} for e in netten}

        def netto_op(start: int) -> float | None:
            # Naar het net positief; met de andere meter voor een kwartier waar die van `grid_mode`
            # niets zegt (v0.170.0).
            afname = _net_afname(sources, per_start, start)
            return None if afname is None else -afname

        for rij in rijen.get(device["entity"]) or []:
            t0 = datetime.fromtimestamp(int(rij["start"]))
            t1 = t0 + timedelta(minutes=15)
            if t1 <= van or t0 >= tot:
                continue
            sec = float(rij.get("seconden") or 0.0)
            if t0 < van:
                sec = min(sec, (t1 - van).total_seconds())
            if t1 > tot:
                sec = min(sec, (tot - t0).total_seconds())
            watts = max(0.0, float(rij.get("gemiddeld") or 0.0))
            if sec <= 0 or watts <= 0:
                continue
            netto = netto_op(int(rij["start"]))
            kwh = watts / 1000.0 * sec / 3600.0
            zon_deel = max(0.0, min(1.0, (netto + watts) / watts)) if netto is not None else 0.0
            begin = max(t0, van)
            koop, terug = self._prijs_toen(settings, sessie, prijs_op, begin)
            sessie["kwh"] += kwh
            sessie["zon_kwh"] += kwh * zon_deel
            if koop is not None:
                sessie["betaald"] += kwh * ((1 - zon_deel) * koop + zon_deel * (terug or 0.0))
                sessie["zon_winst"] += kwh * zon_deel * max(0.0, koop - (terug or 0.0))
                # Uit de kwartieropslag is niet te zien wat een batterij deed.
                if not sessie.get("net_eur_onbekend"):
                    sessie["net_eur"] = float(sessie.get("net_eur") or 0.0) + kwh * (1 - zon_deel) * koop
            # Het verloop: één punt per vijf minuten, zodat het profiel het
            # kwartier vult zoals de live meting dat doet.
            for stap in range(3):
                minuut = (t0 + timedelta(minutes=5 * stap) - gestart).total_seconds() / 60.0
                if minuut >= 0:
                    sessie["punten"].append((minuut, watts))
            if vrij is not None:
                toen = vrij + (begin - gestart)
                koop_toen, _ = self._prijs_toen(settings, sessie, prijs_op, toen)
                if koop_toen is None:
                    sessie["maat_onbekend"] = True
                else:
                    sessie["maat"] += kwh * koop_toen
        sessie["punten"].sort()

    def _prijs_toen(
        self, settings: dict[str, Any], sessie: dict[str, Any], prijs_op: Any, moment: datetime
    ) -> tuple[float | None, float | None]:
        """Wat een kWh op een moment kostte: eerst de lijst die bij het
        vrijgeven bewaard is, dan de recorder, dan de prijssensor van nu."""
        rij = price_now(sessie.get("prijzen") or [], moment)
        if rij is not None and rij.get("price") is not None:
            return rij["price"], rij.get("feed_in")
        if prijs_op is not None:
            koop, terug = prijs_op(moment)
            if koop is not None:
                return koop, terug
        return self._prijs_nu(settings, moment)

    async def _async_prijs_functie(
        self, settings: dict[str, Any], van: datetime, tot: datetime
    ) -> Any:
        """Wat een kWh op een moment in het verleden kostte en opbracht.

        Bij een vast contract het tarief; bij een dynamisch contract uit de
        geschiedenis van de prijssensor. None als die er niet is.
        """
        contract = settings.get("contract") or {}
        dynamic = contract.get("dynamic") or {}
        tarief = self._tarief(settings)
        if contract.get("country") == "PT":
            return lambda moment: self._vast_op(contract, moment)
        if contract.get("type") != "dynamic":
            return lambda moment: (tarief.buy, tarief.feed_in)
        bron = dynamic.get("all_in_entity") if dynamic.get("source") == "all_in" else dynamic.get("market_entity")
        prijzen: list[tuple[datetime, float]] = []
        for moment, toestand in await self._async_geschiedenis(bron, van - timedelta(hours=1), tot):
            try:
                prijzen.append((moment, float(toestand)))
            except ValueError:
                continue
        if dynamic.get("source") != "all_in":
            prijzen = [(m, self._all_in(p, dynamic)) for m, p in prijzen]
        if not prijzen:
            prijzen = await self._async_reserveverloop(dynamic, van - timedelta(hours=1), tot)
        if not prijzen:
            return None
        markt: list[tuple[datetime, float]] = []
        if not self._saldeert(contract) and dynamic.get("market_entity"):
            for moment, toestand in await self._async_geschiedenis(
                dynamic.get("market_entity"), van - timedelta(hours=1), tot
            ):
                try:
                    markt.append((moment, float(toestand)))
                except ValueError:
                    continue
        # De kosten per kWh in de vorm van het contract (v0.135.0), met en zonder salderen.
        bonus = float(dynamic.get("feed_in_bonus") or 0)
        kosten_saldo = prijsopbouw.kosten_per_kwh(dynamic, True) - bonus
        kosten = prijsopbouw.kosten_per_kwh(dynamic, False) - bonus
        opslag = float(dynamic.get("supplier_markup") or 0) * (1 + float(dynamic.get("vat_percent") or 0) / 100)
        salderen = self._saldeert(contract)

        def laatste(reeks: list[tuple[datetime, float]], moment: datetime) -> float | None:
            waarde = None
            for m, w in reeks:
                if m <= moment:
                    waarde = w
                else:
                    break
            return waarde

        def prijs_op(moment: datetime) -> tuple[float | None, float | None]:
            koop = laatste(prijzen, moment)
            if koop is None:
                return None, None
            if salderen:
                return koop, koop - opslag - kosten_saldo
            m = laatste(markt, moment)
            return koop, (m - kosten) if m is not None else None

        return prijs_op

    async def _async_vrijgave_zetten(
        self, settings: dict[str, Any], device_id: str, aan: bool, nu: bool | None = None
    ) -> None:
        """De vrijgave van één apparaat aan of uit, in de opslag en op de eventbus.

        `nu` zet "ingeruimd en nu starten" aan of uit; None laat dat staan.
        Zonder vrijgave is er geen "nu starten".
        """
        was_nu = device_id in (settings.get("ready_now") or [])
        ready = [d for d in (settings.get("ready_devices") or []) if d != device_id]
        snel = [d for d in (settings.get("ready_now") or []) if d != device_id]
        if aan:
            ready.append(device_id)
            if nu or (nu is None and was_nu):
                snel.append(device_id)
        nieuw = {"ready_devices": sorted(ready), "ready_now": sorted(snel)}
        if (nieuw["ready_devices"] == sorted(settings.get("ready_devices") or [])
                and nieuw["ready_now"] == sorted(settings.get("ready_now") or [])):
            return
        try:
            saved = await async_get_store(self.hass).async_save(nieuw)
            # Ook in de instellingen van deze ronde, zodat de rest van de ronde
            # met de nieuwe stand rekent.
            settings.update(nieuw)
            self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": saved})
        except Exception:  # noqa: BLE001 - een vrijgave die blijft staan is geen reden om te stoppen
            _LOGGER.exception("kon de vrijgave van %s niet zetten", device_id)

    def _vrijgave_entiteit(self, device: dict[str, Any], sleutel: str = "release_switch") -> str:
        """De vrijgaveschakelaar (of die van nu starten), of leeg als het de stroom van de machine zelf is.

        In de eerste woning stond tot 29-09-2026 de schakelaar van de meetstekker
        waar de vaatwasser op hangt als vrijgaveschakelaar ingevuld. De coach
        zette hem na elke beurt uit, dus de vaatwasser ging van de stroom (na
        de beurt van 28-09 31 uur lang), en de stekker weer aanzetten las hij
        als "ingeruimd en dicht", met een kritieke "zet hem nu aan" erachter.
        Een schakelaar op hetzelfde apparaat in Home Assistant als de
        vermogenssensor is de stroom en geen vrijgave: die laat de coach
        helemaal met rust, en het paneel zegt het bij Apparaten.
        """
        entity_id = str((device.get("entities") or {}).get(sleutel) or "")
        if not entity_id:
            return ""
        try:
            from homeassistant.helpers import entity_registry as er

            register = er.async_get(self.hass)
            rij = register.async_get(entity_id)
            eigen = rij.device_id if rij is not None else None
            meters = [
                getattr(register.async_get(meter), "device_id", None)
                for meter in (device.get("entity"), device.get("energy_entity"))
                if isinstance(meter, str) and meter
            ]
        except Exception:  # noqa: BLE001 - zonder registratie is er niets te vergelijken
            return entity_id
        if not eigen or eigen not in meters:
            return entity_id
        melding = (device.get("id", ""), entity_id)
        if melding not in self._stroom_gemeld:
            self._stroom_gemeld.add(melding)
            _LOGGER.warning(
                "%s: de vrijgaveschakelaar %s zit op dezelfde stekker als de vermogenssensor en is dus "
                "de stroom van de machine; de coach gebruikt hem niet",
                device.get("name") or device.get("id"), entity_id,
            )
        return ""

    async def _async_knop_volgen(
        self, settings: dict[str, Any], device: dict[str, Any], sessie: dict[str, Any], released: bool
    ) -> bool:
        """Een druk op de vrijgaveknop geeft hem vrij; geeft de vrijgave van nu (v0.102.0).

        De eigenaar op 29-09-2026: "een fysieke zigbee knop waar men op kan
        drukken die een event detecteert." Een knop heeft geen stand, dus een
        druk is altijd vrijgeven en nooit wisselen; nog een keer drukken doet
        niets (zijn keuze). Wat telt als druk: een event-entiteit (Zigbee, Hue,
        Shelly) of een knop-helper krijgt het tijdstip van de druk als
        toestand, een actiesensor (Zigbee2MQTT) de soort ("single") en daarna
        weer leeg. `release_press` kiest de soort; leeg is elke druk. Bij de
        eerste ronde (of na een herstart) is een oude druk geen nieuwe.
        """
        entity_id = str((device.get("entities") or {}).get("release_button") or "")
        if not entity_id:
            return released
        toestand = self.hass.states.get(entity_id)
        if toestand is None or toestand.state == "unavailable":
            return released
        stand = str(toestand.state)
        vorige = sessie.get("knop")
        sessie["knop"] = stand
        if vorige is None or stand == vorige or stand in ("unknown", ""):
            return released
        domein = entity_id.split(".")[0]
        soort = (toestand.attributes or {}).get("event_type") if domein == "event" else (
            stand if domein == "sensor" else None
        )
        gewenst = str(device.get("release_press") or "")
        if gewenst and str(soort or "") != gewenst:
            return released
        if released:
            return released
        await self._async_vrijgave_zetten(settings, device.get("id", ""), True)
        # Een knop laat zelf niets zien: één melding na het besluit van deze
        # ronde, met wanneer hij start (de eigenaar koos dat op 29-09-2026).
        sessie["knop_melden"] = True
        return True

    @staticmethod
    def _knop_zin(naam: str, decision: Decision, now: datetime, handmatig: bool) -> str:
        """De melding na een druk op de vrijgaveknop: vrijgegeven, en wanneer hij start."""
        if decision.charge:
            return (
                t("{naam} is vrijgegeven. Zet hem nu aan.", naam=naam)
                if handmatig
                else t("{naam} is vrijgegeven. Hij start nu.", naam=naam)
            )
        if decision.rule == "wait-for-start" and decision.starts_at:
            try:
                moment = datetime.fromisoformat(str(decision.starts_at)).replace(tzinfo=None)
            except ValueError:
                moment = None
            if moment is not None:
                wanneer = _dag_om(moment, now)
                return (
                    t("{naam} is vrijgegeven. Zet hem aan {wanneer}.", naam=naam, wanneer=wanneer)
                    if handmatig
                    else t("{naam} is vrijgegeven. Hij start {wanneer}.", naam=naam, wanneer=wanneer)
                )
        return t("{naam} is vrijgegeven. {reden}", naam=naam, reden=decision.reason).strip()

    async def _async_klep_volgen(
        self,
        settings: dict[str, Any],
        device: dict[str, Any],
        sessie: dict[str, Any],
        released: bool,
        deur_open: bool | None,
        status: str,
    ) -> tuple[bool, str]:
        """Zonder vrijgave: klep dicht is vrijgegeven (v0.102.0); geeft (vrijgave, waarom niet).

        De eigenaar op 29-09-2026: "als die optie uit staat dan is het klep dicht
        van de vaatwasser en dan is die al vrijgegeven." Niet vrij zolang de
        klep open is, zolang starten op afstand uit staat (dan zegt de machine
        zelf nee; Bosch en Siemens zetten dat uit zodra de deur opengaat), en
        na een beurt tot de klep open en weer dicht is geweest: anders start
        hij meteen weer met de schone vaat erin. Ook niet als de machine zegt
        dat hij klaar is, want dat is na een herstart het enige teken daarvan.
        Een lege machine die na het uitruimen dichtgaat herkent de coach niet;
        dat staat bij het vinkje in Apparaten. Tijdens een beurt blijft alles staan.
        """
        if sessie.get("gestart") is not None:
            return released, ""
        afstand = _text(self.hass, (device.get("entities") or {}).get("remote_start")).strip().lower()
        if deur_open:
            sessie["klep_open_gezien"] = True
        if deur_open is None:
            klep = "unknown"
        elif deur_open:
            klep = "open"
        elif (sessie.get("klep_uitruimen") and not sessie.get("klep_open_gezien")) or status in KLAAR:
            klep = "unload"
        elif afstand == "off":
            klep = "remote"
        else:
            klep = ""
        wil = klep == ""
        if wil != released:
            await self._async_vrijgave_zetten(settings, device.get("id", ""), wil)
            released = wil
        return released, klep

    async def _async_schakelen(self, device: dict[str, Any], aan: bool, sleutel: str = "release_switch") -> bool:
        """De vrijgaveschakelaar (of die van nu starten) aan of uit zetten, als er een is en hij anders staat.

        Geeft terug of er geschakeld is.
        """
        if sleutel in ("release_switch", "release_now_switch"):
            entity_id = self._vrijgave_entiteit(device, sleutel)
        else:
            entity_id = (device.get("entities") or {}).get(sleutel)
        if not entity_id:
            return False
        stand = _text(self.hass, entity_id).strip().lower()
        if stand == ("on" if aan else "off"):
            return False
        domein = entity_id.split(".")[0]
        try:
            await self.hass.services.async_call(
                domein, "turn_on" if aan else "turn_off", {"entity_id": entity_id}, blocking=True
            )
        except Exception:  # noqa: BLE001 - een schakelaar die blijft staan is geen reden om te stoppen
            _LOGGER.exception("kon de schakelaar %s niet zetten", entity_id)
            return False
        return True

    async def _async_schakelaar_volgen(
        self, settings: dict[str, Any], device: dict[str, Any], sessie: dict[str, Any], released: bool
    ) -> bool:
        """De vrijgaveschakelaar en de knop op de kaart gelijk houden; geeft de vrijgave van nu.

        Wie het laatst bewoog wint. Bij de eerste ronde (of na een herstart)
        wint een schakelaar die aan staat, want dan heeft de bewoner hem
        aangezet terwijl de coach niet keek.
        """
        entity_id = self._vrijgave_entiteit(device)
        if not entity_id:
            return released
        tekst = _text(self.hass, entity_id).strip().lower()
        stand = True if tekst == "on" else False if tekst == "off" else None
        if stand is None:
            return released
        device_id = device.get("id", "")
        vorige_stand = sessie.get("schakelaar")
        vorige_vrij = sessie.get("vrij_vorig")
        if vorige_stand is None:
            # Eerste keer dat de coach hem ziet: aan wint, uit zegt niets.
            if stand and not released:
                await self._async_vrijgave_zetten(settings, device_id, True)
                released = True
        elif stand != vorige_stand:
            # De schakelaar bewoog: de vrijgave volgt. Uit terwijl hij al
            # draait laat de beurt met rust; het verslag komt gewoon.
            if stand and not released:
                await self._async_vrijgave_zetten(settings, device_id, True)
                released = True
            elif not stand and released and sessie.get("gestart") is None:
                await self._async_vrijgave_zetten(settings, device_id, False)
                released = False
        elif vorige_vrij is not None and released != vorige_vrij and released != stand:
            # De knop op de kaart bewoog: de schakelaar volgt.
            await self._async_schakelen(device, released)
            stand = released
        sessie["schakelaar"] = stand
        sessie["vrij_vorig"] = released
        return released

    async def _async_nu_volgen(
        self, settings: dict[str, Any], device: dict[str, Any], sessie: dict[str, Any], released: bool
    ) -> tuple[bool, bool]:
        """De schakelaar "nu starten" en die keuze op de kaart gelijk houden; geeft (vrijgave, nu).

        De eigenaar op 13-09-2026: na de klaar-tijd de keuze "ingeruimd en morgen
        starten" of "ingeruimd en nu starten", en vanaf de keukenkaart met een
        tweede schakelaar. Dezelfde afspraak als de vrijgaveschakelaar: wie het
        laatst bewoog wint, en bij de eerste ronde wint aan. Aan is ingeruimd
        én nu, dus de vrijgave gaat mee aan; uit voordat hij draait haalt
        alleen "nu" eraf, ingeruimd blijft hij.
        """
        device_id = device.get("id", "")
        nu = released and device_id in (settings.get("ready_now") or [])
        entity_id = self._vrijgave_entiteit(device, "release_now_switch")
        if not entity_id:
            return released, nu
        tekst = _text(self.hass, entity_id).strip().lower()
        stand = True if tekst == "on" else False if tekst == "off" else None
        if stand is None:
            return released, nu
        vorige_stand = sessie.get("nu_schakelaar")
        vorige_nu = sessie.get("nu_vorig")
        if vorige_stand is None or stand != vorige_stand:
            if stand and not nu:
                await self._async_vrijgave_zetten(settings, device_id, True, nu=True)
                released = nu = True
            elif vorige_stand is not None and not stand and nu and sessie.get("gestart") is None:
                await self._async_vrijgave_zetten(settings, device_id, True, nu=False)
                nu = False
        elif vorige_nu is not None and nu != vorige_nu and nu != stand:
            # De keuze op de kaart bewoog: de schakelaar volgt.
            await self._async_schakelen(device, nu, "release_now_switch")
            stand = nu
        sessie["nu_schakelaar"] = stand
        sessie["nu_vorig"] = nu
        return released, nu

    async def _async_meting_bewaren(
        self,
        settings: dict[str, Any],
        device: dict[str, Any],
        programma: Any,
        sessie: dict[str, Any],
        gestart: datetime,
        einde: datetime,
    ) -> None:
        """De gemeten duur, het verbruik, de piek en het profiel van deze beurt bewaren.

        De eigenaar op 06-09-2026: "het verbruik van een vaatwasser is in het begin
        heel hoog vanwege het opwarmen, dus ik wil dat gaan meten en dan die
        waardes in kunnen vullen." Per apparaat en per programma, als lopend
        gemiddelde over de laatste beurten (`METING_MAX_N`). Een beurt zonder
        vermogenssensor, of een die te kort was om een beurt te zijn, telt niet.
        """
        if programma is None:
            return
        minuten = _tussen(gestart, einde).total_seconds() / 60.0
        # Alleen wat er tot het einde gemeten is: zonder statussensor kijkt
        # de coach nog een kwartier of hij echt stil blijft, en die stille
        # minuten horen niet in het profiel.
        punten = [(m, w) for m, w in (sessie.get("punten") or []) if m <= minuten + 0.5]
        # Op een energieteller (Miele, v0.124.0) is er geen verloop, alleen het
        # totaal: dan zonder piek en zonder profiel, en rekent de coach het
        # verbruik gelijk over de duur.
        teller = bool(sessie.get("teller"))
        if minuten < 5 or sessie["kwh"] <= 0.02 or not (punten or teller):
            return
        device_id = device.get("id", "")
        nieuw = {
            "minutes": int(round(minuten)),
            "kwh": round(sessie["kwh"], 3),
            "peak_w": 0 if teller else int(round(max(w for _, w in punten))),
            "profile": [] if teller else list(profiel_van(punten)),
            # De naam, voor een programma dat niet in de tabel staan (v0.124.0).
            "label": programma.label,
        }
        rows = [
            row for row in (settings.get("program_measured") or [])
            if isinstance(row, dict) and not (row.get("device") == device_id and row.get("key") == programma.key)
        ]
        oud = next(
            (row for row in (settings.get("program_measured") or [])
             if isinstance(row, dict) and row.get("device") == device_id and row.get("key") == programma.key),
            None,
        )
        n = 0
        if oud is not None:
            try:
                n = max(0, min(METING_MAX_N, int(oud.get("runs") or 0)))
                if n:
                    nieuw["minutes"] = int(round((float(oud["minutes"]) * n + nieuw["minutes"]) / (n + 1)))
                    nieuw["kwh"] = round((float(oud["kwh"]) * n + nieuw["kwh"]) / (n + 1), 3)
                    nieuw["peak_w"] = max(int(oud.get("peak_w") or 0), nieuw["peak_w"])
                    nieuw["profile"] = list(profiel_gemiddeld(
                        tuple(float(w) for w in (oud.get("profile") or [])), n, tuple(nieuw["profile"])
                    ))
            except (KeyError, TypeError, ValueError):
                n = 0
        rows.append({
            "device": device_id, "key": programma.key, **nieuw,
            "runs": min(METING_MAX_N, n + 1), "at": einde.isoformat(),
        })
        try:
            saved = await async_get_store(self.hass).async_save({"program_measured": rows})
        except Exception:  # noqa: BLE001 - een gemiste meting is geen reden om te stoppen
            _LOGGER.exception("kon de meting van %s niet bewaren", device_id)
            return
        self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": saved})

    async def _async_noteer_programma(
        self, device: dict[str, Any], device_id: str, now: datetime
    ) -> None:
        """Het besluit over een programma-apparaat in de geschiedenis, bij verandering."""
        st = self.state.get(device_id) or {}
        kern = (bool(st.get("charge")), st.get("rule"), bool(st.get("applied")), st.get("starts_at"))
        if self._besluit_genoteerd.get(device_id) == kern:
            return
        self._besluit_genoteerd[device_id] = kern
        naam = _programma_naam(device)
        if st.get("rule") == "read-only":
            await self._async_noteer(t("{naam}: alleen uitlezen, de coach start hem niet.", naam=naam), now, {
                "device": device_id, "rule": "read-only", "charge": False, "applied": False,
            })
            return
        if st.get("rule") == "running":
            kop = t("draait")
        elif st.get("charge"):
            kop = t("zet hem aan") if st.get("manual") else t("start nu")
        else:
            kop = t("wacht")
        if not st.get("applied") and st.get("charge") and st.get("rule") != "running":
            kop = t("zou nu starten, maar de coach stuurt nu niet")
        reden = (st.get("reason") or "").strip()
        await self._async_noteer(f"{naam}: {kop}. {reden}".strip(), now, {
            "device": device_id, "rule": st.get("rule"), "charge": bool(st.get("charge")),
            "applied": bool(st.get("applied")),
        })

    @staticmethod
    def _priority(settings: dict[str, Any], device: dict[str, Any]) -> int:
        """Wie er voorgaat als er te weinig ruimte is voor allebei."""
        rang = {"high": 0, "mid": 1, "low": 2}
        for entry in (settings.get("strategy") or {}).get("schedules") or []:
            if isinstance(entry, dict) and entry.get("device") == device.get("id"):
                return rang.get(entry.get("priority", "mid"), 1)
        return 1

    # ------------------------------------------------------------------
    # De airco (v0.119.0)
    #
    # De eigenaar op 14-10-2026: aan bij zon over of op een uur onder het
    # gemiddelde van vandaag, wat de bewoner kiest (standaard alleen zon, sinds
    # v0.119.1), zolang de kamer de temperatuur van de bewoner nog niet heeft; de
    # coach zet die temperatuur en kiest verwarmen of koelen. Zet de bewoner hem
    # zelf aan of uit, dan blijft de coach er de rest van de dag vanaf. Het denkwerk staat in `plan_airco` in planner.py; hier staat wat er
    # gebeurde: wie hem aanzette, wat de bewoner deed, en de opdrachten.

    def _airco_sessie(self, device_id: str) -> dict[str, Any]:
        return self._airco.setdefault(device_id, {
            # Sinds wanneer de coach hem aanzette, en waarom. Alleen wat de
            # coach aanzette zet hij ook uit.
            "aan_sinds": None, "reden": None,
            # Wat de coach net vroeg en nog niet terugzag: een cloud doet daar
            # een minuut over, en dat is dan de bewoner niet.
            "verwacht": None, "verwacht_sinds": None,
            "temp_verwacht": None,
            # Wat er de vorige ronde stond, om te zien dat iemand anders iets deed.
            "vorige": None, "temp_vorige": None,
            # Tot wanneer de bewoner wint.
            "bewoner_tot": None,
            # Het meeste dat hij trok terwijl hij draaide, als er een sensor is:
            # zonder typeplaatje de maat voor "genoeg zon". Het meeste, want een
            # airco begint hard en regelt terug als hij bijna op temperatuur is.
            "gemeten_w": None,
        })

    def _airco_staat(self, device: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """De stand van de climate ("off", "heat", "cool", ...) en zijn attributen."""
        entiteit = (device.get("entities") or {}).get("climate")
        staat = self.hass.states.get(entiteit) if entiteit else None
        if staat is None:
            return "", {}
        return str(staat.state or "").strip().lower(), dict(getattr(staat, "attributes", None) or {})

    @staticmethod
    def _airco_doel(device: dict[str, Any], attrs: dict[str, Any]) -> float | None:
        """Wat de bewoner wil; zolang hij niets koos, wat er op de airco staat."""
        for waarde in ((device.get("airco") or {}).get("target_c"), attrs.get("temperature")):
            try:
                if waarde not in (None, ""):
                    return float(waarde)
            except (TypeError, ValueError):
                continue
        return None

    def _airco_neemt_w(self, device: dict[str, Any]) -> float:
        """Wat deze airco nu trekt: gemeten, of het typeplaatje als de coach hem aanzette."""
        gemeten = _watts(self.hass, device.get("entity"))
        if gemeten is not None:
            return max(0.0, gemeten)
        sessie = self._airco.get(device.get("id", "")) or {}
        if sessie.get("aan_sinds") is None:
            return 0.0
        try:
            return float((device.get("airco") or {}).get("power_w") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    async def _one_airco(
        self,
        now: datetime,
        settings: dict[str, Any],
        device: dict[str, Any],
        level: str,
    ) -> None:
        device_id = device.get("id", "")
        entities = device.get("entities") or {}
        eigen = device.get("airco") or {}
        naam = device.get("name") or t("De airco")
        klimaat = entities.get("climate")
        sessie = self._airco_sessie(device_id)
        hvac, attrs = self._airco_staat(device)
        bereikbaar = hvac not in ("", "unavailable", "unknown")
        aan = bereikbaar and hvac != "off"
        temp = attrs.get("temperature")

        # Kwam wat de coach vroeg aan? Dan is dat de nieuwe maat waaraan de
        # bewoner gemeten wordt, en niet iets wat de bewoner deed. Zo niet
        # binnen AIRCO_VOLGT, dan ging de opdracht niet door, en blijft de maat
        # wat er voor de opdracht stond: wat de bewoner intussen deed, telt dan.
        if sessie["verwacht"] is not None:
            if hvac == sessie["verwacht"]:
                sessie["verwacht"] = None
                sessie["vorige"] = hvac
            elif now - sessie["verwacht_sinds"] > AIRCO_VOLGT:
                sessie["verwacht"] = None
        if sessie["temp_verwacht"] is not None:
            if _gelijk(temp, sessie["temp_verwacht"]):
                sessie["temp_verwacht"] = None
                sessie["temp_vorige"] = temp
            elif now - (sessie["verwacht_sinds"] or now) > AIRCO_VOLGT:
                sessie["temp_verwacht"] = None

        # Deed de bewoner iets? Aan, uit of een andere stand, terwijl de coach
        # niets vroeg: dan wint hij de rest van de dag. Een andere temperatuur
        # is geen schakelen maar zijn nieuwe wens (`target_c`).
        if bereikbaar and sessie["verwacht"] is None and sessie["vorige"] is not None and hvac != sessie["vorige"]:
            sessie["bewoner_tot"] = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
            sessie["aan_sinds"] = None
            sessie["reden"] = None
            self._remember(device_id)
        if (
            aan and sessie["temp_verwacht"] is None and sessie["temp_vorige"] is not None
            and temp is not None and not _gelijk(temp, sessie["temp_vorige"])
        ):
            await self._async_airco_voorkeur(device_id, "target_c", float(temp))
            eigen = {**eigen, "target_c": float(temp)}
        if not aan and sessie["aan_sinds"] is not None and sessie["verwacht"] is None:
            # Uit, door wie dan ook (ook een airco die zelf uitviel): niet meer van de coach.
            sessie["aan_sinds"] = None
            sessie["reden"] = None
        if bereikbaar:
            sessie["vorige"] = hvac
            sessie["temp_vorige"] = temp
        if sessie["bewoner_tot"] is not None and now >= sessie["bewoner_tot"]:
            sessie["bewoner_tot"] = None
            self._remember(device_id)

        watts = _watts(self.hass, device.get("entity"))
        if aan and watts is not None and watts > (sessie.get("gemeten_w") or 0.0):
            sessie["gemeten_w"] = watts
            self._remember(device_id)
        try:
            plaatje = float(eigen.get("power_w")) if eigen.get("power_w") not in (None, "") else None
        except (TypeError, ValueError):
            plaatje = None
        vermogen = plaatje or sessie.get("gemeten_w")
        kamer = _number(self.hass, entities.get("temperature")) if entities.get("temperature") else None
        if kamer is None:
            try:
                kamer = float(attrs["current_temperature"]) if attrs.get("current_temperature") is not None else None
            except (TypeError, ValueError):
                kamer = None
        modi = [str(m).lower() for m in attrs.get("hvac_modes") or []]
        aan_op = str(eigen.get("run_on") or AIRCO_AAN_OP[0])
        if aan_op not in AIRCO_AAN_OP:
            aan_op = AIRCO_AAN_OP[0]
        try:
            stap = float(attrs.get("target_temp_step") or AIRCO_STAP_C)
        except (TypeError, ValueError):
            stap = AIRCO_STAP_C

        airco = Airco(
            aan=aan,
            modus=hvac if aan else None,
            kamer_c=kamer,
            doel_c=self._airco_doel(device, attrs),
            stap_c=stap,
            vermogen_w=vermogen,
            kan_verwarmen=not modi or "heat" in modi,
            kan_koelen=not modi or "cool" in modi,
            aan_op=aan_op,
            coach_sinds=sessie["aan_sinds"],
            coach_reden=sessie["reden"],
        )
        # Wat er naar het net zou gaan als deze airco uit stond, zoals bij de
        # boiler (valkuil 2): anders eet hij zijn eigen zon op.
        gemeten = self._meter_zeker(now)
        if gemeten is not None:
            kaal = gemeten - self._batterijen_w(settings)
            gemeten = kaal + self._zon_correctie(settings, device, kaal)
        surplus = None if gemeten is None else gemeten + (self._airco_neemt_w(device) if aan else 0.0)
        prijzen = self._prices(settings)
        besluit = plan_airco(now, prijzen, airco, surplus_w=surplus)

        # Wat er boven de som gaat: de pauze en de bewoner.
        if eigen.get("paused"):
            besluit = AircoBesluit(
                aan=False if sessie["aan_sinds"] is not None and aan else None, modus=None,
                stand="pauze", rule="pauze",
                reason=t("Gepauzeerd: de coach doet niets met de airco."),
            )
        elif sessie["bewoner_tot"] is not None or (aan and sessie["aan_sinds"] is None):
            besluit = AircoBesluit(
                aan=None, modus=airco.modus, stand="bewoner", rule="bewoner",
                reason=(
                    t("Je zette hem zelf aan of uit, dus de coach blijft er vandaag vanaf.")
                    if sessie["bewoner_tot"] is not None
                    else t("Hij staat aan, maar niet door de coach. De coach laat hem met rust.")
                ),
            )

        mag = level == LEVEL_STEER or (level == LEVEL_PROPOSE and device_id in self._approved)
        self.state[device_id] = {
            "kind": "airco",
            "at": now.isoformat(),
            "level": level,
            "applied": mag and level not in (LEVEL_READ, LEVEL_ADVISE),
            "approved": device_id in self._approved,
            "charge": aan if besluit.aan is None else besluit.aan,
            "rule": besluit.rule,
            "reason": besluit.reason,
            "plan": "",
            "stand": besluit.stand,
            "modus": besluit.modus or airco_nodig(airco),
            "on": aan,
            "hvac": hvac,
            "climate": klimaat,
            "room_c": kamer,
            "target_c": airco.doel_c,
            "power_w": None if watts is None else round(watts),
            "vermogen_w": vermogen,
            "run_on": aan_op,
            "paused": bool(eigen.get("paused")),
            "dynamic": bool(prijzen),
            "resident_until": sessie["bewoner_tot"].isoformat() if sessie["bewoner_tot"] else None,
        }
        await self._async_noteer_airco(naam, device_id, now)
        self._toezeggingen.pop(device_id, None)

        if level in (LEVEL_READ, LEVEL_ADVISE) or not mag or not klimaat or not bereikbaar:
            return
        # Een opdracht die nog onderweg is wordt niet nog eens gestuurd: een
        # cloudkoppeling doet er een minuut over, en elke opdracht kost er weer een.
        if sessie["verwacht"] is not None:
            return
        if besluit.aan is False and aan:
            await self._async_airco_zetten(device, sessie, now, "off")
            sessie["aan_sinds"] = None
            sessie["reden"] = None
            self._remember(device_id)
            return
        if besluit.aan is True and not aan and besluit.modus:
            # Past hij nog onder de zekeringen, na wie hoger staat in de voorrang?
            ruimte = (
                self._laadruimte_w(settings, device, 0.0, self._hogere_toezeggingen(settings, device))
                if vermogen else None
            )
            if ruimte is not None and vermogen > ruimte:
                self.state[device_id].update(
                    charge=False, rule="no-room", stand="uit",
                    reason=t("Er is nu geen ruimte op de aansluiting voor de airco. Zodra er ruimte is, gaat hij aan."),
                )
                return
            await self._async_airco_zetten(device, sessie, now, besluit.modus, airco.doel_c)
            sessie["aan_sinds"] = now
            sessie["reden"] = besluit.stand
            self._remember(device_id)
        if sessie["aan_sinds"] is not None and vermogen:
            self._toezeggingen[device_id] = {
                "amps": float(vermogen) / VOLTS,
                "sleutels": self._groep_sleutels(settings, device),
            }

    async def _async_airco_zetten(
        self, device: dict[str, Any], sessie: dict[str, Any], now: datetime,
        modus: str, temperatuur: float | None = None,
    ) -> None:
        """De airco aan in een stand (met de temperatuur van de bewoner) of uit."""
        klimaat = (device.get("entities") or {}).get("climate")
        if not klimaat:
            return
        if modus == "off":
            dienst, data = "set_hvac_mode", {"entity_id": klimaat, "hvac_mode": "off"}
        elif temperatuur is not None:
            # Eén opdracht met de stand erin: een cloudkoppeling doet over elke
            # opdracht een minuut.
            dienst, data = "set_temperature", {"entity_id": klimaat, "temperature": temperatuur, "hvac_mode": modus}
            sessie["temp_verwacht"] = temperatuur
        else:
            dienst, data = "set_hvac_mode", {"entity_id": klimaat, "hvac_mode": modus}
        sessie["verwacht"] = modus
        sessie["verwacht_sinds"] = now
        try:
            await self.hass.services.async_call("climate", dienst, data, blocking=True)
        except Exception:  # noqa: BLE001 - een airco die blijft staan is geen reden om te stoppen
            _LOGGER.exception("kon de airco %s niet zetten", klimaat)
            sessie["verwacht"] = None
            sessie["temp_verwacht"] = None

    async def async_airco_doel(self, device_id: str, graden: float) -> None:
        """De temperatuur van de bewoner, van de kaart; staat de airco aan, dan meteen erop.

        Eén schrijver: de kaart zet de number, de coach zet de airco. Meteen, en
        niet pas bij de volgende ronde, want een cloud doet er al een minuut over.
        """
        await self._async_airco_voorkeur(device_id, "target_c", float(graden))
        settings = await async_get_store(self.hass).async_load()
        device = next((d for d in settings.get("devices") or [] if d.get("id") == device_id), None)
        if device is None:
            return
        hvac, _ = self._airco_staat(device)
        if hvac in ("", "off", "unavailable", "unknown"):
            return
        sessie = self._airco_sessie(device_id)
        klimaat = (device.get("entities") or {}).get("climate")
        sessie["temp_verwacht"] = float(graden)
        sessie["verwacht_sinds"] = _moment()
        try:
            await self.hass.services.async_call(
                "climate", "set_temperature", {"entity_id": klimaat, "temperature": float(graden)}, blocking=True
            )
        except Exception:  # noqa: BLE001 - dan staat hij in de opslag en zet de bewoner hem zelf
            _LOGGER.exception("kon de temperatuur van %s niet zetten", klimaat)
            sessie["temp_verwacht"] = None

    async def _async_airco_voorkeur(self, device_id: str, veld: str, waarde: Any) -> None:
        """Eén veld in `airco` van één apparaat bewaren, zoals de bewoner het zou zetten."""
        store = async_get_store(self.hass)
        settings = await store.async_load()
        apparaten = []
        for device in settings.get("devices") or []:
            if device.get("id") == device_id:
                device = {**device, "airco": {**(device.get("airco") or {}), veld: waarde}}
            apparaten.append(device)
        saved = await store.async_save({"devices": apparaten})
        self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": saved})

    async def _async_noteer_airco(self, naam: str, device_id: str, now: datetime) -> None:
        """Het besluit over een airco in de geschiedenis, bij verandering."""
        st = self.state.get(device_id) or {}
        kern = (st.get("stand"), bool(st.get("applied")))
        if self._besluit_genoteerd.get(device_id) == kern:
            return
        self._besluit_genoteerd[device_id] = kern
        kop = {
            "zon": t("aan op zon"), "goedkoop": t("aan op een goedkoop uur"), "op_temperatuur": t("op temperatuur"),
            "uit": t("uit"), "bewoner": t("door jou bediend"), "pauze": t("gepauzeerd"), "geen_meting": t("weet het niet"),
        }.get(str(st.get("stand")), str(st.get("stand")))
        await self._async_noteer(f"{naam}: {kop}. {(st.get('reason') or '').strip()}".strip(), now, {
            "device": device_id, "rule": st.get("rule"), "charge": bool(st.get("charge")),
            "applied": bool(st.get("applied")), "mode": st.get("stand"),
        })

    # ------------------------------------------------------------------
    # De boiler
    #
    # De eigenaar op 19-09-2026: "ik wil gewoon een sturing maken op een boiler waar
    # je alleen stroom op moet zetten, met een smart plug bijvoorbeeld. Als je
    # er stroom op zet en de boiler is warm moet de coach detecteren dat hij
    # warm genoeg is omdat de boiler dan onder een bepaald vermogen zit. Ik wil
    # dit zelflerend hebben. Alleen de switch invullen en power invullen."
    #
    # Twee entiteiten, en verder niets in te vullen. De coach zet de stroom
    # erop of eraf; de thermostaat van de boiler bepaalt hoe warm het water
    # wordt. Daardoor kan dit niets kapotmaken en niets gevaarlijks doen: het
    # ergste wat de coach kan is te laat aanzetten, en daar is de klaar-tijd
    # voor. Het denkwerk staat in `plan_boiler` in planner.py.

    async def _one_boiler(
        self,
        now: datetime,
        settings: dict[str, Any],
        device: dict[str, Any],
        level: str,
    ) -> None:
        device_id = device.get("id", "")
        entities = device.get("entities") or {}
        naam = device.get("name") or t("De boiler")
        schakelaar = entities.get("switch")
        if device_id not in self._boiler:
            self._boiler[device_id] = self._boiler_terug(device_id, now)
        sessie = self._boiler[device_id]
        geleerd = self._boiler_rij(settings, device_id)

        watts = _watts(self.hass, device.get("entity"))
        stand = _text(self.hass, schakelaar).strip().lower() if schakelaar else ""
        aan = stand == "on"
        if not aan and sessie.get("aan_sinds") is not None:
            # De schakelaar ging eraf, door wie dan ook: de opwarmbeurt is uit.
            sessie["aan_sinds"] = None
            sessie["stil_sinds"] = None
        if aan and sessie.get("aan_sinds") is None:
            sessie["aan_sinds"] = now

        # Trekt hij iets? Zodra de coach een keer gemeten heeft wat het element
        # trekt is de grens een vijfde daarvan, anders BOILER_DRAAI_W.
        grens = BOILER_DRAAI_W
        if geleerd.get("heat_w"):
            grens = max(BOILER_DRAAI_W, float(geleerd["heat_w"]) * BOILER_DRAAI_DEEL)
        draait = aan and watts is not None and watts >= grens

        if draait:
            sessie["stil_sinds"] = None
            self._boiler_tellen(settings, sessie, now, watts)
        elif aan:
            sessie["stil_sinds"] = sessie.get("stil_sinds") or now
        sessie["laatst"] = now

        # Vol is een meting: er staat lang genoeg stroom op en hij vraagt
        # niets. Pas na BOILER_AANLOOP, want een meetstekker meldt niet elke
        # seconde en een thermostaat mag even nadenken.
        vol = None
        if aan and sessie.get("aan_sinds") is not None and now - sessie["aan_sinds"] >= BOILER_AANLOOP:
            if draait:
                vol = False
            elif sessie.get("stil_sinds") is not None and now - sessie["stil_sinds"] >= BOILER_STIL:
                vol = True
        if vol is not None:
            # Hij heeft net gezien hoe het vat ervoor staat; dan hoeft er
            # voorlopig niet geproefd te worden, en is de proef afgelopen.
            sessie["gekeken"] = now
            sessie["proef_sinds"] = None
        elif sessie.get("proef_sinds") is not None and (
            now - sessie["proef_sinds"] > BOILER_AANLOOP + BOILER_STIL + timedelta(minutes=2)
        ):
            # Een proef die nergens op uitkomt (de meetstekker zegt niets) mag
            # niet blijven hangen: dan zou de stroom erop blijven staan.
            sessie["proef_sinds"] = None
            sessie["gekeken"] = now

        window = resolve_window(now, self._days(settings, device))
        einde = window.deadline if window.enabled else None
        # Hoeveel er uit het vat gegaan moet zijn sinds hij voor het laatst
        # werkelijk stroom trok. Dat is de maat waaraan "hij vraagt niets"
        # gelegd wordt; zie `BOILER_VERDACHT` in planner.py.
        zou_nodig = None
        getrokken = geleerd.get("getrokken_op")
        if getrokken is not None and geleerd.get("verbruik_kwh_h"):
            uren = max(0.0, (now - getrokken).total_seconds() / 3600.0)
            zou_nodig = uren * float(geleerd["verbruik_kwh_h"])

        if vol:
            geleerd = await self._async_boiler_vol(
                settings, device, naam, sessie, geleerd, now, zou_nodig
            )
            sessie = self._boiler[device_id]

        boiler = Boiler(
            on=aan,
            power_w=watts,
            # Vol weet hij alleen zolang er stroom op staat. Gaat de stroom
            # eraf, dan kan de boiler niets meer zeggen en rekent de coach
            # weer met wat hij geleerd heeft.
            full=vol if aan else None,
            heat_w=geleerd.get("heat_w"),
            vol_kwh=geleerd.get("vol_kwh"),
            verbruik_kwh_h=geleerd.get("verbruik_kwh_h"),
            vol_sinds=geleerd.get("vol_sinds"),
            kwh_sinds_vol=float(geleerd.get("kwh_sinds_vol") or 0.0) + sessie["beurt_kwh"],
            vergeefs=int(sessie.get("vergeefs") or 0),
            # Een proef die loopt is pas klaar als hij iets opgeleverd heeft.
            # Zonder dat zou hij na één minuut alweer afgebroken worden door
            # het gewone plan ("wacht op het goedkope uur"), en stond de boiler
            # elke minuut aan en uit; gezien op 19-09-2026 in `boiler-nacht`.
            proef_nodig=sessie.get("proef_sinds") is not None or (
                not aan and (
                    (gekeken := sessie.get("gekeken") or geleerd.get("vol_sinds")) is None
                    or now - gekeken >= BOILER_PROEF_ELKE
                )
            ),
        )
        # Wat er naar het net zou gaan als deze boiler níet liep. Zonder die
        # correctie zou hij zichzelf uitzetten zodra hij aangaat: hij eet zijn
        # eigen overschot op. Dezelfde som als bij de paal, waar het
        # laadvermogen er ook weer bij opgeteld wordt.
        gemeten = self._meter_zeker(now)
        eigen = (watts or 0.0) if draait else 0.0
        # De meter van tien minuten telt de batterij al als wijkend (zie
        # `_netto_export_w`); de voorrang bij zon (v0.92.0) zegt of dat klopt,
        # en of een paal lager in de voorrang voor de boiler wijkt.
        if gemeten is not None:
            kaal = gemeten - self._batterijen_w(settings)
            gemeten = kaal + self._zon_correctie(settings, device, kaal)
        surplus = None if gemeten is None else gemeten + eigen
        decision = plan_boiler(
            now, self._prices(settings), self._tarief(settings),
            Forecast(solar_kwh=self._zon_kwh, house_kwh=self._huis_kwh,
                     estimated=self._zon_geschat, solar_factor=self._zon_gemeten(now),
                     solar_day=now.date()),
            window, boiler,
            surplus_w=surplus,
        )

        # Sinds wanneer er warmte bij moest: het ijkpunt voor Bespaard, net als
        # het inpluggen bij een auto en het vrijgeven bij een vaatwasser.
        if decision.rule in ("deadline", "cheapest-hour", "wait-for-cheap", "zon", "leren"):
            if sessie.get("nodig_sinds") is None:
                sessie["nodig_sinds"] = now
                sessie["prijzen"] = list(self._prices(settings))

        mag = level == LEVEL_STEER or (level == LEVEL_PROPOSE and device_id in self._approved)
        nodig = boiler_nodig(now, boiler, window.deadline if window.enabled else None)
        self.state[device_id] = {
            **asdict(decision),
            "kind": "boiler",
            "at": now.isoformat(),
            "level": level,
            "applied": mag and level not in (LEVEL_READ, LEVEL_ADVISE),
            "approved": device_id in self._approved,
            "running": draait,
            "on": aan,
            "power_w": None if watts is None else round(watts),
            # Wat hij geleerd heeft, voor op de kaart. None is "nog niet
            # gemeten", en dat hoort de kaart ook zo te zeggen.
            "learned": {
                "heat_w": geleerd.get("heat_w"),
                "vol_kwh": geleerd.get("vol_kwh"),
                "use_kwh_h": geleerd.get("verbruik_kwh_h"),
                "runs": geleerd.get("runs") or 0,
                "full_at": geleerd["vol_sinds"].isoformat() if geleerd.get("vol_sinds") else None,
            },
            "needed_kwh": None if nodig is None else round(nodig, 2),
            "tip": "",
        }
        await self._async_noteer_programma(device, device_id, now)
        self._toezeggingen.pop(device_id, None)
        self._boiler_onthouden(device_id)

        if level in (LEVEL_READ, LEVEL_ADVISE) or not mag or not schakelaar:
            return
        if decision.charge == aan:
            return
        # Vergeefs aanzetten: er moest verwarmd worden en er liep niets. Dan is
        # er iets met de stekker of de schakelaar.
        if not decision.charge and aan:
            await self._async_boiler_zetten(device, False)
            # Wat er deze aanzetting in ging hoort bij dit vat en niet bij deze
            # aanzetting: hij mag over meerdere goedkope blokken verdeeld
            # worden. Dus naar de opslag, waar het ook een herstart overleeft.
            if sessie["beurt_kwh"] > 0:
                await self._async_boiler_bewaren(
                    settings, device_id, geleerd,
                    {"kwh_sinds_vol": float(geleerd.get("kwh_sinds_vol") or 0.0) + sessie["beurt_kwh"]},
                )
                sessie["beurt_kwh"] = 0.0
            return
        # Past het element nog onder de zekeringen, na wie er hoger staat in de
        # voorrang bij planningen (v0.93.0)? Een boiler die nog niets gemeten
        # heeft kent zijn vermogen niet, en dan wordt er niet gegokt.
        element = geleerd.get("heat_w")
        ruimte = (
            self._laadruimte_w(settings, device, 0.0, self._hogere_toezeggingen(settings, device))
            if element else None
        )
        if ruimte is not None and element > ruimte:
            self.state[device_id].update(
                charge=False,
                rule="no-room",
                reason=t(
                    "Er is nu geen ruimte op de aansluiting voor de boiler: wat hoger staat in "
                    "de voorrang gaat voor. Zodra er ruimte is, gaat hij aan."
                ),
            )
            self._toezeggingen.pop(device_id, None)
            return
        await self._async_boiler_zetten(device, True)
        if element:
            self._toezeggingen[device_id] = {
                "amps": float(element) / VOLTS,
                "sleutels": self._groep_sleutels(settings, device),
            }
        sessie["aan_sinds"] = now
        sessie["stil_sinds"] = None
        # Waarom de stroom erop ging. Bij het afronden is de regel altijd
        # "full", en dan is dit het enige dat nog zegt of er werkelijk warmte
        # bij moest; zie `_async_boiler_vol`.
        sessie["reden_aan"] = decision.rule
        if decision.rule == "proef":
            sessie["proef_sinds"] = now

    async def _async_boiler_zetten(self, device: dict[str, Any], aan: bool) -> None:
        """De stroom van de boiler erop of eraf."""
        await self._async_schakelen(device, aan, "switch")

    async def _async_boiler_vol(
        self,
        settings: dict[str, Any],
        device: dict[str, Any],
        naam: str,
        sessie: dict[str, Any],
        geleerd: dict[str, Any],
        now: datetime,
        zou_nodig: float | None = None,
    ) -> dict[str, Any]:
        """Het vat is vol: leren wat deze beurt zei, en de beurt wegschrijven.

        Alleen leren van een beurt waarin werkelijk iets gebeurde. Een
        proefmoment dat meteen "vol" oplevert meet niets, en zou het geleerde
        vermogen en de vatgrootte alleen maar verwateren.
        """
        if "vol" in sessie["gemeld"]:
            return geleerd
        sessie["gemeld"].add("vol")
        device_id = device.get("id", "")
        erin = sessie["beurt_kwh"] + float(geleerd.get("kwh_sinds_vol") or 0.0)
        nieuw: dict[str, Any] = {"vol_sinds": now, "kwh_sinds_vol": 0.0}

        if sessie["beurt_kwh"] > BOILER_MIN_KWH and sessie["draai_seconden"] > 60:
            sessie["vergeefs"] = 0
            sessie["gemeld"].discard("vergeefs")
            # Wanneer hij voor het laatst werkelijk iets trok. Hiervandaan
            # wordt geteld of stilte nog te verklaren is; zie BOILER_VERDACHT.
            nieuw["getrokken_op"] = now
            n = max(0, min(METING_MAX_N, int(geleerd.get("runs") or 0)))
            vermogen = sessie["beurt_kwh"] / (sessie["draai_seconden"] / 3600.0) * 1000.0
            oud_w = geleerd.get("heat_w")
            nieuw["heat_w"] = round(
                (oud_w * n + vermogen) / (n + 1) if oud_w and n else vermogen, 1
            )
            # Het vat is zo groot als de grootste volle beurt die hij zag: van
            # koud naar vol, en dat is een grens uit de natuurkunde en geen
            # gemiddelde.
            nieuw["vol_kwh"] = round(max(float(geleerd.get("vol_kwh") or 0.0), erin), 3)
            # Wat er per uur uit het vat gaat: afkoelen en douchen samen, over
            # de tijd sinds hij voor het laatst vol was. Onder het uur zegt dat
            # niets.
            vorig = geleerd.get("vol_sinds")
            if vorig is not None:
                uren = (now - vorig).total_seconds() / 3600.0
                if uren >= 1.0:
                    per_uur = erin / uren
                    oud_u = geleerd.get("verbruik_kwh_h")
                    nieuw["verbruik_kwh_h"] = round(
                        (oud_u * n + per_uur) / (n + 1) if oud_u and n else per_uur, 3
                    )
            nieuw["runs"] = min(METING_MAX_N, n + 1)
            sessie["gemeld"].discard("vergeefs")
            # Het verslag gaat naar de geschiedenis en niet naar de telefoon:
            # een boiler die om drie uur 's nachts warm wordt hoeft niemand te
            # wekken. De eigenaar op 06-09-2026: "niet telkens onnodig meldingen."
            erin_tekst = (
                t("{kwh} vanaf {klok}.", kwh=_kwh_tekst(erin), klok=f"{sessie['gestart']:%H:%M}")
                if sessie.get("gestart")
                else f"{_kwh_tekst(erin)}."
            )
            # Dezelfde regels als bij de andere apparaten (v0.101.0, v0.102.1).
            herkomst = self._herkomst_tekst(sessie)
            maat = None if sessie["maat_onbekend"] or sessie.get("nodig_sinds") is None else sessie["maat"]
            bespaard = ""
            if maat is not None and maat - sessie["betaald"] >= 0.005:
                bespaard = self._bespaard_zin(maat - sessie["betaald"])
            await self._async_tell(
                _verslag(t("{naam} is weer warm.", naam=naam), erin_tekst, herkomst, bespaard),
                telefoon=False,
            )
            self._beurt_schrijven(self._boiler_regel(device, naam, sessie, now))

        leeg = sessie["beurt_kwh"] <= BOILER_MIN_KWH
        if leeg and geleerd.get("getrokken_op") is None:
            # Nog nooit zien trekken: dan begint de klok nu, want zonder
            # beginpunt valt er niets te zeggen over hoe lang het al stil is.
            nieuw["getrokken_op"] = now
        verdacht = (
            leeg
            and zou_nodig is not None
            and geleerd.get("vol_kwh")
            and zou_nodig >= BOILER_VERDACHT * float(geleerd["vol_kwh"])
        )
        if verdacht:
            # Volgens de som is het vat halfleeg en toch vraagt hij niets. Dat
            # is geen vol vat maar een stekker die niets doet, en dan hoort
            # `vol_sinds` er niet op te schuiven: dan zou de coach zichzelf
            # wijsmaken dat het goed zit.
            nieuw.pop("vol_sinds", None)
            nieuw.pop("kwh_sinds_vol", None)
            sessie["vergeefs"] = int(sessie.get("vergeefs") or 0) + 1
            if sessie["vergeefs"] >= BOILER_VERGEEFS and "vergeefs" not in sessie["gemeld"]:
                sessie["gemeld"].add("vergeefs")
                await self._async_tell(
                    t(
                        "De coach zet {naam} wel aan, maar er loopt geen stroom: {n} keer achter elkaar "
                        "vroeg hij niets terwijl er warm water bij moest. Kijk of de stekker en de "
                        "schakelaar doen wat ze horen te doen.",
                        naam=naam, n=sessie["vergeefs"],
                    ),
                    kritiek=True,
                )

        samen = await self._async_boiler_bewaren(settings, device_id, geleerd, nieuw)
        self._boiler[device_id] = {
            **self._lege_boiler_sessie(now),
            "gekeken": now,
            "vergeefs": sessie.get("vergeefs") or 0,
            # Een melding die gedaan is blijft gedaan: anders komt "er loopt
            # geen stroom" bij elke volgende vergeefse poging opnieuw.
            "gemeld": {"vergeefs"} & set(sessie.get("gemeld") or ()),
        }
        return samen

    def _boiler_tellen(
        self, settings: dict[str, Any], sessie: dict[str, Any], now: datetime, watts: float | None
    ) -> None:
        """Wat deze ronde erin ging, wat het kostte, en wat het gekost had als
        hij meteen was gaan verwarmen toen het nodig was.

        Dezelfde maat als bij een laadbeurt en bij een vaatwasser: hetzelfde
        verbruik, verschoven naar het moment waarop de coach zag dat er warmte
        bij moest, en dan alles van het net tegen de prijs van toen.
        """
        if watts is None or watts <= 0:
            return
        uren = max(0.0, (now - sessie["laatst"]).total_seconds()) / 3600.0
        if uren <= 0 or uren > 0.5:
            return
        kwh = watts / 1000.0 * uren
        if sessie.get("gestart") is None:
            sessie["gestart"] = now
        sessie["beurt_kwh"] += kwh
        sessie["draai_seconden"] += uren * 3600.0
        koop, terug = self._prijs_nu(settings, now)
        export = self._netto_export_w(settings)
        zon_deel = 0.0
        if export is not None and terug is not None:
            zon_deel = max(0.0, min(1.0, (export + watts) / watts))
        sessie["kwh"] += kwh
        sessie["zon_kwh"] += kwh * zon_deel
        self._herkomst_bij(sessie, settings, kwh, zon_deel, koop)
        if koop is not None:
            sessie["betaald"] += kwh * ((1 - zon_deel) * koop + zon_deel * (terug or 0.0))
            sessie["zon_winst"] += kwh * zon_deel * max(0.0, koop - (terug or 0.0))
        nodig_sinds = sessie.get("nodig_sinds")
        if nodig_sinds is not None:
            toen = nodig_sinds + timedelta(seconds=sessie["draai_seconden"])
            rij = price_now(sessie.get("prijzen") or [], toen)
            koop_toen = rij["price"] if rij is not None else self._prijs_nu(settings, toen)[0]
            if koop_toen is None:
                sessie["maat_onbekend"] = True
            else:
                sessie["maat"] += kwh * koop_toen

    def _boiler_regel(
        self, device: dict[str, Any], naam: str, sessie: dict[str, Any], einde: datetime
    ) -> dict[str, Any]:
        """De opwarmbeurt zoals hij onder Bespaard komt te staan."""
        gestart = sessie.get("gestart") or einde
        begin = sessie.get("nodig_sinds") or gestart
        maat = None if sessie["maat_onbekend"] or sessie.get("nodig_sinds") is None else sessie["maat"]
        betaald = sessie["betaald"]
        return {
            "id": f"{device.get('id', '')}:{begin.replace(microsecond=0).isoformat()}",
            "device": device.get("id", ""),
            "name": naam,
            "kind": "boiler",
            "car": "",
            "program": "",
            "plugged_at": begin.replace(microsecond=0).isoformat(),
            "started": gestart.replace(microsecond=0).isoformat(),
            "ended": einde.replace(microsecond=0).isoformat(),
            "kwh": round(sessie["kwh"], 3),
            "solar_kwh": round(sessie["zon_kwh"], 3),
            "paid": round(betaald, 4),
            "ref_price": None,
            "ref_feed_in": None,
            "ref_cost": None if maat is None else round(maat, 4),
            "saved": None if maat is None else round(max(0.0, maat - betaald), 4),
            "solar_saved": round(sessie.get("zon_winst") or 0.0, 4),
            **self._herkomst_velden(sessie),
            "price_unknown": maat is None,
            "unknown_kwh": 0.0,
            "baseline": {"kwh": round(sessie["kwh"], 3),
                         "cost": None if maat is None else round(maat, 4),
                         "unknown_kwh": 0.0, "points": []},
            "resumed": False,
            "complete": True,
        }

    @staticmethod
    def _lege_boiler_sessie(now: datetime) -> dict[str, Any]:
        return {
            "aan_sinds": None,      # wanneer er stroom op ging
            "stil_sinds": None,     # sinds wanneer hij niets meer trekt
            "gestart": None,        # wanneer hij voor het eerst iets trok
            "gekeken": None,        # wanneer de coach zag hoe het vat ervoor staat
            "proef_sinds": None,    # of er een proef loopt, en sinds wanneer
            "reden_aan": "",        # waarom de stroom erop ging
            "nodig_sinds": None,    # wanneer er warmte bij moest: het ijkpunt
            "prijzen": [],
            "beurt_kwh": 0.0,       # wat er sinds de laatste volle beurt in ging
            "draai_seconden": 0.0,
            "kwh": 0.0,
            "zon_kwh": 0.0,
            "betaald": 0.0,
            "maat": 0.0,
            "maat_onbekend": False,
            "zon_winst": 0.0,
            "accu_kwh": 0.0,
            "net_eur": 0.0,
            "laatst": now,
            "vergeefs": 0,
            "gemeld": set(),
        }

    @staticmethod
    def _boiler_rij(settings: dict[str, Any], device_id: str) -> dict[str, Any]:
        """Wat de coach van deze boiler geleerd heeft, uit de instellingen."""
        for rij in settings.get("boiler_learned") or []:
            if not isinstance(rij, dict) or rij.get("device") != device_id:
                continue
            uit: dict[str, Any] = {}
            for sleutel in ("heat_w", "vol_kwh", "verbruik_kwh_h", "kwh_sinds_vol"):
                try:
                    waarde = rij.get(sleutel)
                    uit[sleutel] = None if waarde is None else float(waarde)
                except (TypeError, ValueError):
                    uit[sleutel] = None
            for sleutel in ("vol_sinds", "getrokken_op"):
                moment = _tijdstip(rij.get(sleutel))
                uit[sleutel] = moment.replace(tzinfo=None) if moment is not None else None
            try:
                uit["runs"] = int(rij.get("runs") or 0)
            except (TypeError, ValueError):
                uit["runs"] = 0
            return uit
        return {}

    async def _async_boiler_bewaren(
        self,
        settings: dict[str, Any],
        device_id: str,
        geleerd: dict[str, Any],
        nieuw: dict[str, Any],
    ) -> dict[str, Any]:
        """Het geleerde van deze boiler naar de instellingen, en terug.

        Terug, want `async_save` maakt een nieuwe instellingendict: wat deze
        ronde in de hand heeft is daarna oud, en die zou het net geleerde
        meteen weer vergeten.
        """
        samen = {**geleerd, **nieuw}
        rij = {
            "device": device_id,
            "heat_w": samen.get("heat_w"),
            "vol_kwh": samen.get("vol_kwh"),
            "verbruik_kwh_h": samen.get("verbruik_kwh_h"),
            "kwh_sinds_vol": round(float(samen.get("kwh_sinds_vol") or 0.0), 3),
            "vol_sinds": samen["vol_sinds"].isoformat() if samen.get("vol_sinds") else None,
            "getrokken_op": samen["getrokken_op"].isoformat() if samen.get("getrokken_op") else None,
            "runs": int(samen.get("runs") or 0),
        }
        rows = [
            r for r in (settings.get("boiler_learned") or [])
            if isinstance(r, dict) and r.get("device") != device_id
        ]
        rows.append(rij)
        try:
            saved = await async_get_store(self.hass).async_save({"boiler_learned": rows})
        except Exception:  # noqa: BLE001 - een gemiste meting is geen reden om te stoppen
            _LOGGER.exception("kon het geleerde van %s niet bewaren", device_id)
            return samen
        self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": saved})
        # De instellingen van deze ronde zijn nu oud; de rij die er net in
        # geschreven is telt.
        settings["boiler_learned"] = rows
        return samen

    # ------------------------------------------------------------------
    # De thuisbatterij
    #
    # De eigenaar op 21-09-2026: "het doel is om hem volledig third party te
    # sturen, dus via HA." Het denkwerk staat in batterij.py. Hier twee lussen:
    # `_one_batterij` kiest elke minuut een stand, en `_async_regel` voert die
    # uit op het tempo van de meter.

    def _batterij_wijkt(
        self, settings: dict[str, Any], now: datetime, voor: dict[str, Any] | None = None
    ) -> dict[tuple[str, str], float]:
        """Per zekering en fase: de stroom van een batterij die wijkt als de paal laadt.

        De eerste woning op 23-09-2026: de Anker en de Alfen op dezelfde groep
        van 16 A. Laadde de Anker 3,2 kW zon op L3, dan zei de paal "de groep
        Garage is te zwaar belast", en de zon die voor de auto was ging in de
        batterij; ontlaadde de Anker, dan net zo. Maar een batterij die de coach
        stuurt wijkt voor de paal: ontladen stopt zodra die laadt (`met_paal`),
        en laden op nul op de meter zakt vanzelf als de auto de zon neemt. Die
        stroom telt dus niet als belasting voor de paal, onder elke zekering in
        de keten van de batterij en onder de hoofdaansluiting. Wel bij laden van
        het net en maximaal laden: daar wijkt hij niet.

        En zakt een batterij flink, dan dragen de fasemetingen van daarvoor zijn
        oude stroom nog; net als bij een paal die omlaag gaat tellen voor de
        mediaan dan alleen de metingen van daarna (`_daling`, zie `_gladde_fase`).
        """
        uit: dict[tuple[str, str], float] = {}
        for device in settings.get("devices") or []:
            if device.get("type") != "thuisbatterij":
                continue
            device_id = device.get("id", "")
            watt = self._batterij_w(device)
            if watt is None:
                continue
            vorige = self._batterij_vorige_w.get(device_id)
            if vorige is not None and abs(watt) < abs(vorige) - BATTERIJ_DALING_W:
                self._daling = now
            self._batterij_vorige_w[device_id] = watt
            sessie = self._batterij.get(device_id) or {}
            besluit = sessie.get("besluit")
            if not sessie.get("stuurt") or besluit is None:
                continue
            if watt > 0 and besluit.stand in (NETLADEN, MAX_LADEN):
                # Laden van het net wijkt alleen voor wie hoger staat in de
                # voorrang bij planningen (v0.93.0): dan krijgt de batterij wat
                # er na de paal over is (`_laadruimte_w`).
                rang = self._plan_voorrang(settings)
                if voor is None or rang.get(device_id, 0) <= rang.get(voor.get("id", ""), 0):
                    continue
            fase = apparaat_fase(device)
            fasen = [fase] if fase in ("l1", "l2", "l3") else ["l1", "l2", "l3"]
            amps = abs(watt) / 230.0 / len(fasen)
            for sleutel in self._groep_sleutels(settings, device):
                for f in fasen:
                    uit[(sleutel, f)] = uit.get((sleutel, f), 0.0) + amps
        return uit

    def _batterij_w(self, device: dict[str, Any]) -> float | None:
        """Wat deze batterij nu doet, in watt, laden positief.

        Uit één sensor met een teken, of uit twee losse sensoren voor laden en
        ontladen: allebei de vormen komen voor, soms bij dezelfde batterij.
        """
        entities = device.get("entities") or {}
        getekend = _watts(self.hass, device.get("entity"))
        if getekend is not None:
            return -getekend if (device.get("battery") or {}).get("power_invert") else getekend
        laden = _watts(self.hass, entities.get("charge_power"))
        ontladen = _watts(self.hass, entities.get("discharge_power"))
        if laden is None and ontladen is None:
            return None
        return (laden or 0.0) - (ontladen or 0.0)

    def _plan_voorrang(self, settings: dict[str, Any]) -> dict[str, int]:
        """Ieders plek in de voorrang bij planningen (v0.93.0). Zie `plan_regels`."""
        oud = {
            entry.get("device"): entry.get("priority", "mid")
            for entry in (settings.get("strategy") or {}).get("schedules") or []
            if isinstance(entry, dict)
        }
        volgorde = plan_regels(
            (settings.get("strategy") or {}).get("plan_priority"), settings.get("devices") or [], oud
        )
        rang = plan_rang(volgorde)
        # De klaar-tijd is heilig (eis 2), ook boven de volgorde van de bewoner:
        # een paal die in de klaar-tijdregel zit of te laat is gaat bovenaan. In
        # het virtuele huis haalde de auto met de accu bovenaan anders 96% om
        # 07:00 in plaats van vol (`planning-accu-eerst`).
        for apparaat_id in rang:
            if apparaat_id in self._deadline_for or apparaat_id in self._te_laat:
                rang[apparaat_id] = -1
        return rang

    def _hogere_toezeggingen(
        self, settings: dict[str, Any], device: dict[str, Any], *, zonder_palen: bool = False,
        totaal: bool = False,
    ) -> dict[str, float]:
        """Per zekering wat apparaten hoger in de voorrang bij planningen toezegden.

        Een toezegging is wat een apparaat er de komende minuut bij gaat
        nemen, bovenop wat de meter al ziet. Wie lager staat krijgt de ruimte
        die daarna over is: de bewoner van de eerste woning, "laadt de accu
        maar met 3500 W en heb ik nog ruimte op mijn aansluiting, dan kan ik
        ook mijn boiler nog vol laden." `zonder_palen` voor de palen zelf: die
        tellen elkaar in de ronde al via `vergeven`.

        `totaal` (v0.164.1): niet wat er bovenop de meting komt, maar alles wat een paal trekt. Voor
        een groep zonder meter: daar ziet niemand de stroom die al loopt.
        """
        rang = self._plan_voorrang(settings)
        mijn = rang.get(device.get("id", ""))
        if mijn is None:
            return {}
        soort = {a.get("id"): a.get("type") for a in settings.get("devices") or []}
        uit: dict[str, float] = {}
        for apparaat_id, toezegging in self._toezeggingen.items():
            plek = rang.get(apparaat_id)
            if plek is None or plek >= mijn:
                continue
            if zonder_palen and soort.get(apparaat_id) == "laadpaal":
                continue
            amps = toezegging.get("totaal", toezegging.get("amps")) if totaal else toezegging.get("amps")
            for sleutel in toezegging.get("sleutels") or []:
                uit[sleutel] = uit.get(sleutel, 0.0) + float(amps or 0.0)
        return uit

    def _zon_voorrang(self, settings: dict[str, Any]) -> tuple[list[dict], dict[str, int]]:
        """De voorrang bij zonoverschot en ieders plek erin, op dit moment.

        Zie `zon_regels` en `zon_rang` in planner.py. De stand van een paal is
        de accustand van de auto die eraan hangt, van een batterij haar eigen.
        """
        apparaten = settings.get("devices") or []
        regels = zon_regels((settings.get("strategy") or {}).get("solar_priority"), apparaten)
        stand: dict[str, float | None] = {}
        for apparaat in apparaten:
            apparaat_id = apparaat.get("id", "")
            if apparaat.get("type") == "laadpaal":
                stand[apparaat_id] = self._auto_soc.get(apparaat_id)
            elif apparaat.get("type") == "thuisbatterij":
                stand[apparaat_id] = _number(self.hass, (apparaat.get("entities") or {}).get("soc"))
        return regels, zon_rang(regels, stand)

    def _zon_correctie(
        self, settings: dict[str, Any], device: dict[str, Any], kaal: float
    ) -> float:
        """Wat er voor dit apparaat bij de gemeten teruglevering komt of af gaat.

        De voorrang bij zonoverschot (v0.92.0, zie `zon_regels`). Een apparaat
        ziet de teruglevering, plus wat apparaten lager in de voorrang nu van de
        zon nemen, want die wijken:

        - Een batterij die ontlaadt is geen zon, waar hij ook staat.
        - Een batterij lager in de voorrang die laadt, wijkt: zijn lading telt.
          Zo ging het altijd (`_batterijen_w`), en zo is het de standaard.
        - Een batterij hoger in de voorrang die nog onder zijn grens zit en mag
          laden, wijkt niet: zijn lading telt niet, en de ruimte die hij nog
          heeft gaat eraf, zodat het apparaat eronder wijkt en de batterij het
          krijgt. De bewoner van de eerste woning: "eerst moet de accu 40% vol
          zijn, daarna mag het zonoverschot naar de auto."
        - Een paal of boiler lager in de voorrang wijkt met zijn zondeel: wat
          hij verbruikt, maar niet meer dan er aan zon was. Een paal die volgens
          zijn planning van het net laadt maakt voor de boiler dus geen zon.

        `kaal` is de teruglevering zonder batterij-correctie, positief is naar
        het net. Geeft het verschil terug, zodat de aanroeper zijn eigen
        vastgehouden meting kan houden.
        """
        regels, rang = self._zon_voorrang(settings)
        if device.get("id", "") not in rang:
            # Een apparaat dat niet in de voorrang staat (de coach stuurt het
            # niet): zoals het altijd ging, de batterij wijkt.
            return self._batterijen_w(settings)
        mijn = rang[device.get("id", "")]
        # Eerst het eigen verbruik: de zon die dit apparaat al neemt is van
        # hem, en pas wat daarna overblijft wordt toegerekend aan wie lager staat.
        eigen = max(0.0, _watts(self.hass, device.get("entity")) or 0.0)
        beschikbaar = kaal + eigen
        for apparaat in settings.get("devices") or []:
            if apparaat.get("type") != "thuisbatterij":
                continue
            w = self._batterij_geregeld_w(apparaat) or 0.0
            plek = rang.get(apparaat.get("id", ""), len(regels) + 1)
            if w < 0 or plek > mijn:
                beschikbaar += w
                continue
            sessie = self._batterij.get(apparaat.get("id", "")) or {}
            b = sessie.get("batterij")
            besluit = sessie.get("besluit")
            if not sessie.get("stuurt") or b is None or besluit is None or not besluit.grenzen[0]:
                beschikbaar += w
                continue
            grens = zon_grens(regels, rang, apparaat.get("id", "")) or (b.soc_max - VOL_MARGE)
            if b.soc is not None and b.soc >= min(grens, b.soc_max - VOL_MARGE):
                beschikbaar += w
                continue
            # Hij staat hoger en wil nog: zijn lading telt niet, zijn ruimte gaat eraf.
            beschikbaar -= max(0.0, b.max_charge_w - max(0.0, w))
        for apparaat in settings.get("devices") or []:
            if apparaat is device or apparaat.get("type") not in ("laadpaal", "boiler", "airco"):
                continue
            if not apparaat.get("controllable"):
                continue
            plek = rang.get(apparaat.get("id", ""), len(regels) + 1)
            if plek <= mijn:
                continue
            # Een airco staat niet in de voorrang en wijkt dus voor iedereen die
            # er wel in staat (v0.119.0); zonder vermogenssensor met zijn typeplaatje.
            neemt = (
                self._airco_neemt_w(apparaat) if apparaat.get("type") == "airco"
                else max(0.0, _watts(self.hass, apparaat.get("entity")) or 0.0)
            )
            if neemt <= 0:
                continue
            beschikbaar += max(0.0, min(neemt, beschikbaar + neemt))
        return beschikbaar - eigen - kaal

    def _batterijen_w(self, settings: dict[str, Any]) -> float:
        """Wat alle batterijen samen nu opnemen, in watt.

        Voor iedereen die naar het overschot kijkt: wat een batterij opslokt is
        geen huisverbruik maar zon die ook naar de auto of de vaatwasser had
        gekund, en wat hij afgeeft is geen zon. De auto laadt op zon zonder
        verlies en de batterij verliest een kwart, dus de andere apparaten gaan
        voor en de batterij krijgt wat er daarna over is; dat laatste regelt
        zich vanzelf, want hij houdt de meter op nul.
        """
        totaal = 0.0
        for device in settings.get("devices") or []:
            if device.get("type") == "thuisbatterij":
                totaal += self._batterij_geregeld_w(device) or 0.0
        return totaal

    def _batterij_geregeld_w(self, device: dict[str, Any]) -> float | None:
        """Wat deze batterij doet volgens de regelaar die hem stuurt, anders de sensor.

        Stuurt de coach hem, dan is de eigen opdracht de waarheid zolang de
        sensor die niet blijvend tegenspreekt (`Regelaar.vermogen_w`): de
        sensor van de Anker loopt na een opdracht vijf tot tien seconden achter,
        en wie daarop rekent ziet bij elke omslag een schijnoverschot. Gemeten
        in de eerste woning op 22-09-2026.
        """
        gemeten = self._batterij_w(device)
        sessie = self._batterij.get(device.get("id", ""))
        # Doet hij zelf nul op de meter, dan is er geen opdracht om op te rekenen.
        if sessie is not None and sessie.get("stuurt") and not sessie.get("zelf"):
            return sessie["regelaar"].vermogen_w(gemeten)
        return gemeten

    def _net_nu(self, settings: dict[str, Any]) -> tuple[float | None, datetime | None]:
        """De meter, positief bij afname, en wanneer hij dat voor het laatst zei."""
        sources = settings.get("sources") or {}
        if sources.get("grid_mode") == "signed":
            namen = [sources.get("grid_signed")]
        else:
            namen = [sources.get("grid_import"), sources.get("grid_export")]
        export = self._netto_export_kaal(settings)
        stempels = []
        for naam in namen:
            staat = self.hass.states.get(naam) if naam else None
            if staat is not None:
                stempels.append(getattr(staat, "last_reported", None) or staat.last_updated)
        if export is None or not stempels:
            return None, None
        return -export, _moment(max(stempels))

    def _laadruimte_w(
        self, settings: dict[str, Any], device: dict[str, Any], batterij_w: float | None,
        hoger: dict[str, float] | None = None,
    ) -> float | None:
        """Hoeveel de zekering deze batterij nog aan laadvermogen toestaat.

        Een batterij hangt meestal op één fase, en 3,5 kW is daar vijftien
        ampère. Laadt de auto tegelijk op drie fasen, dan zit die fase zo vol.
        Zonder fasesensoren en zonder groep bewaakt de coach dit niet: None.
        """
        sources = settings.get("sources") or {}
        installation = settings.get("installation") or {}
        fase = apparaat_fase(device)

        def stromen_uit(sensoren: dict[str, Any], alleen_fase: bool) -> list[float]:
            uit = []
            for key in ("l1", "l2", "l3"):
                if alleen_fase and fase and key != fase:
                    continue
                amps = _number(self.hass, ((sensoren or {}).get(key) or {}).get("current"))
                if amps is not None:
                    uit.append(abs(amps))
            return uit

        ruimten: list[float] = []
        # Voor een groep zonder meter: alles wat wie voor gaat trekt, niet alleen wat erbij komt.
        alles = self._hogere_toezeggingen(settings, device, totaal=True) if hoger is not None else {}
        # Wat ze zelf laadt staat in de meting van haar fase; dat mag ze houden.
        eigen_a = max(0.0, batterij_w or 0.0) / VOLTS
        if sources.get("phases_enabled"):
            zekering = float(installation.get("fuse_amps") or 25)
            marge = BALANCER_MARGIN_AMPS if installation.get("load_balancer") else FUSE_MARGIN_AMPS
            stromen = stromen_uit(sources.get("phases") or {}, True)
            if stromen:
                ruimten.append(zekering - max(marge, zekering * FUSE_MARGIN_SHARE) - max(stromen)
                               - (hoger or {}).get("", 0.0) + eigen_a)
        # En elke groep waar de batterij aan hangt, met haar eigen zekering en
        # meter. Op een eenfasige groep is er maar één meting en telt die.
        # Een groep zonder meter telt ook (v0.164.1), met wat er bekend is: de
        # toezeggingen van wie voor gaat, geen huis. Zoals `ruimten` in planner.py
        # het voor een paal doet. Tot dan sloeg de coach zo'n groep over, en laadde
        # een batterij daar op haar volle vermogen naast een paal die voor ging.
        for groep in self._groepen_keten(settings, device):
            zekering = float(groep.get("fuse_amps") or 16)
            stromen = stromen_uit(groep.get("sensors") or {}, int(groep.get("phases") or 3) == 3)
            # Wat ze zelf laadt zit alleen in een meting; zonder meter komt het er niet weer bij.
            if stromen:
                ruimten.append(zekering - max(FUSE_MARGIN_AMPS, zekering * FUSE_MARGIN_SHARE) - max(stromen)
                               - (hoger or {}).get(str(groep.get("id")), 0.0) + eigen_a)
            else:
                # Plus wat de apparaten trekken die bij de groep gekozen zijn (v0.165.0), op haar fase.
                bekend = self._groep_som(settings, groep) or {}
                op_fase = bekend.get(fase) if fase in bekend else max(bekend.values(), default=0.0)
                ruimten.append(zekering - max(FUSE_MARGIN_AMPS, zekering * FUSE_MARGIN_SHARE)
                               - alles.get(str(groep.get("id")), 0.0) - (op_fase or 0.0))
        if not ruimten:
            return None
        return min(ruimten) * VOLTS

    async def _async_groep_vol(self, settings: dict[str, Any], now: datetime) -> None:
        """Melden als een groep zonder meter bijna aan zijn zekering zit, gemeten via zijn apparaten (v0.165.0).

        Eén keer per keer, met de naam van de groep. De coach schakelt niets uit: de eigenaar op
        26-10-2026, "je wilt niet dat je wasmachine ineens uitschakelt toch?"
        """
        apparaten = {a.get("id"): a for a in settings.get("devices") or [] if isinstance(a, dict)}
        for groep in (settings.get("installation") or {}).get("circuits") or []:
            if not isinstance(groep, dict) or not groep.get("id"):
                continue
            sleutel = str(groep["id"])
            som = self._groep_som(settings, groep)
            zekering = float(groep.get("fuse_amps") or 0)
            if som is None or zekering <= 0:
                self._groep_vol.pop(sleutel, None)
                continue
            amps = max(som.values(), default=0.0)
            if amps < GROEP_VOL_WEER * zekering:
                self._groep_vol.pop(sleutel, None)
                self._groep_vol_gemeld.discard(sleutel)
                continue
            if amps < GROEP_VOL_DEEL * zekering:
                self._groep_vol.pop(sleutel, None)
                continue
            sinds = self._groep_vol.setdefault(sleutel, now)
            if sleutel in self._groep_vol_gemeld or _tussen(sinds, now) < GROEP_VOL_DUUR:
                continue
            self._groep_vol_gemeld.add(sleutel)
            namen = [
                str((apparaten.get(r.get("device")) or {}).get("name") or "")
                for r in groep.get("devices") or [] if isinstance(r, dict)
            ]
            namen = [n for n in namen if n]
            _LOGGER.warning("groep %s trekt %.1f A van %.0f A", sleutel, amps, zekering)
            await self._async_tell(
                t(
                    "De groep {naam} trekt {amps} A, bijna de {zekering} A van de zekering. Gemeten via {apparaten}.",
                    naam=groep.get("name") or t("zonder naam"), amps=getal(amps, 1), zekering=f"{zekering:.0f}",
                    apparaten=namen[0] if len(namen) == 1 else t("{voor} en {laatste}", voor=", ".join(namen[:-1]), laatste=namen[-1]),
                ),
                kritiek=True,
            )

    def _groep_som(self, settings: dict[str, Any], groep: dict[str, Any]) -> dict[str, float] | None:
        """Per fase wat de apparaten trekken die bij een groep zonder meter gekozen zijn (v0.165.0)."""
        return groep_apparaten_amps(
            groep, settings.get("devices") or [], lambda entity: _watts(self.hass, entity),
            lambda entity: _number(self.hass, entity),
        )

    def _laadruimte_plan(
        self, settings: dict[str, Any], device: dict[str, Any]
    ) -> list[tuple[datetime, datetime, float]]:
        """Per blok van het plan van een paal hoeveel watt de zekeringen deze batterij laten (v0.164.0).

        Dezelfde zekeringen als `_laadruimte_w`, maar vooruit: wat de regelaar straks op het
        moment zelf doet, rekent het uurplan van de batterij nu al mee. In een klantwoning plande
        de batterij op 26-10-2026 voor 02:00-05:00 2,5 kW van het net op L3, terwijl de paal op
        dezelfde kast van 3x16 A dan 13 A per fase plande. De regelaar gaf haar daar hooguit
        200 W, en het plan rekende met goedkope kWh die niet kwamen.

        Alleen een paal die voor gaat in de voorrang bij planningen (zoals in `_hogere_toezeggingen`),
        alleen een zekering die ze delen, en dezelfde zekeringen als de regelaar: de hoofdaansluiting
        met fasesensoren, en elke groep, ook zonder meter (v0.164.1). Het huis op die zekering telt niet
        mee, want dat weet de coach van tevoren niet. De paal laadt met de stroom van zijn plan op elke
        fase waar hij op laadt; bij één fase weet de coach niet welke, dus telt hij die van de batterij.
        Twee palen op dezelfde zekering tellen samen (v0.164.1): tot dan nam de coach de laagste ruimte
        per paal apart, en lieten twee palen van 6 A op een groep van 16 A de batterij 8 A in plaats van 2.
        """
        sources = settings.get("sources") or {}
        installation = settings.get("installation") or {}
        rang = self._plan_voorrang(settings)
        eigen = rang.get(device.get("id", ""), len(rang))
        fase = apparaat_fase(device)
        fasen = 1 if fase in ("l1", "l2", "l3") else 3

        def bewaakt(sensoren: dict[str, Any], alleen: str | None) -> bool:
            return any(
                ((sensoren or {}).get(key) or {}).get("current")
                for key in ("l1", "l2", "l3")
                if alleen is None or key == alleen
            )

        # Elke zekering van de batterij die de regelaar bewaakt: sleutel, grens in ampère na de marge.
        eigen_zekeringen: dict[str, float] = {}
        if sources.get("phases_enabled") and bewaakt(sources.get("phases") or {}, fase if fasen == 1 else None):
            zekering = float(installation.get("fuse_amps") or 25)
            marge = BALANCER_MARGIN_AMPS if installation.get("load_balancer") else FUSE_MARGIN_AMPS
            eigen_zekeringen[""] = zekering - max(marge, zekering * FUSE_MARGIN_SHARE)
        for groep in self._groepen_keten(settings, device):
            zekering = float(groep.get("fuse_amps") or 16)
            eigen_zekeringen[str(groep.get("id"))] = zekering - max(FUSE_MARGIN_AMPS, zekering * FUSE_MARGIN_SHARE)
        if not eigen_zekeringen:
            return []

        # Per zekering de blokken van elke paal die eronder hangt: van, tot, ampère.
        last: dict[str, list[tuple[datetime, datetime, float]]] = {k: [] for k in eigen_zekeringen}
        for paal in settings.get("devices") or []:
            if paal.get("type") != "laadpaal" or rang.get(paal.get("id", ""), len(rang)) >= eigen:
                continue
            gedeeld = [k for k in self._groep_sleutels(settings, paal) if k in eigen_zekeringen]
            stand = self.state.get(paal.get("id", ""))
            plan = stand.get("plan_ahead") if isinstance(stand, dict) else None
            if not gedeeld or not isinstance(plan, dict):
                continue
            try:
                toen = datetime.fromisoformat(str(stand.get("at")))
            except ValueError:
                continue
            for blok in plan.get("blocks") or []:
                amps = blok.get("amps")
                if not blok.get("charging") or not isinstance(amps, (int, float)) or amps <= 0:
                    continue
                try:
                    van = max(datetime.fromisoformat(blok["start"]), toen)
                    tot = datetime.fromisoformat(blok["end"])
                except (KeyError, TypeError, ValueError):
                    continue
                if tot > van:
                    for k in gedeeld:
                        last[k].append((van, tot, float(amps)))
        # Op elke grens van een blok een nieuw stuk, en per stuk de laagste ruimte over de zekeringen,
        # met de palen onder dezelfde zekering opgeteld.
        grenzen = sorted({t for blokken in last.values() for van, tot, _ in blokken for t in (van, tot)})
        uit: list[tuple[datetime, datetime, float]] = []
        for van, tot in zip(grenzen, grenzen[1:]):
            bezet = {
                k: sum(a for b_van, b_tot, a in blokken if b_van < tot and b_tot > van)
                for k, blokken in last.items()
            }
            if not any(bezet.values()):
                continue
            ruimte = min(eigen_zekeringen[k] - bezet[k] for k in eigen_zekeringen)
            uit.append((van, tot, max(0.0, ruimte) * VOLTS * fasen))
        return uit

    @staticmethod
    def _groepen_keten(settings: dict[str, Any], device: dict[str, Any]) -> list[dict[str, Any]]:
        """De groepen waar dit apparaat aan hangt, van onder naar boven.

        Een apparaat wijst naar één groep (`circuit`), en een groep naar de
        groep erboven (`parent`). De hoofdaansluiting staat er niet in: die is
        er altijd. Een kring of een groep die niet bestaat eindigt de keten.
        """
        return groepen_keten((settings.get("installation") or {}).get("circuits") or [], device)

    def _groep_sleutels(self, settings: dict[str, Any], device: dict[str, Any]) -> list[str]:
        """Onder welke zekeringen een toezegging aan dit apparaat meetelt."""
        return [""] + [str(g.get("id")) for g in self._groepen_keten(settings, device)]

    def _fase_piek(self, phase: dict[str, Any], now: datetime) -> float | None:
        """De hoogste meting van deze fase binnen `FASE_VENSTER`.

        Naast de mediaan van `_fase_amps`, en alleen voor de vraag of de limiet
        van een paal omhoog mag (`ruimten_nu` in planner.py): een apparaat dat
        om de tien seconden aan en uit gaat heeft een mediaan die alle kanten
        op valt, en een hoogste meting die zegt wat er straks weer staat. Hier
        geldt `_daling` niet: de metingen van vóór een stap omlaag dragen de
        oude stroom van de paal, en dat houdt hem het venster lang beneden.
        Een fase zonder stroomsensor heeft geen historie; dan telt wat hij nu
        zegt.
        """
        nu_amps = self._fase_amps(phase, now)
        if nu_amps is None:
            return None
        rauw = self._volgehouden(phase.get("current"), _number(self.hass, phase.get("current")), now)
        historie = self._fase_historie.get(phase.get("current") or "") or []
        grens = now - FASE_VENSTER
        # De laatste meting van vóór het venster stond er aan het begin ervan nog.
        voor = [waarde for stempel, waarde in historie if stempel < grens][-1:]
        binnen = [waarde for stempel, waarde in historie if stempel >= grens]
        return max([nu_amps] + ([rauw] if rauw is not None else []) + voor + binnen)

    def _fase_amps(self, phase: dict[str, Any], now: datetime) -> float | None:
        """Wat een fase trekt: de stroomsensor (vastgehouden en gladgestreken),
        anders vermogen gedeeld door spanning. Zie `_gladde_fase`."""
        amps = self._volgehouden(
            phase.get("current"), _number(self.hass, phase.get("current")), now
        )
        if amps is not None:
            return self._gladde_fase(phase.get("current"), amps, now)
        watts = self._volgehouden(
            phase.get("power"), _watts(self.hass, phase.get("power")), now
        )
        volts = _number(self.hass, phase.get("voltage")) or 230
        return watts / volts if watts is not None and volts else None

    @staticmethod
    def _batterij_rij(settings: dict[str, Any], device_id: str) -> dict[str, Any]:
        for rij in settings.get("battery_state") or []:
            if isinstance(rij, dict) and rij.get("device") == device_id:
                return dict(rij)
        return {"device": device_id}

    @staticmethod
    def _voorraad_uit(rij: dict[str, Any]) -> Voorraad:
        """De voorraad zoals hij bewaard is, of leeg: wat er al in zat kostte niets."""
        return Voorraad(euro=float(rij.get("stock_euro") or 0.0))

    @staticmethod
    def _opgeleverd_dagen(rij: dict[str, Any]) -> dict[str, float]:
        """Wat de batterij per dag opleverde; van voor v0.107.0 het kasboek."""
        if isinstance(rij.get("realized_days"), dict):
            return rij["realized_days"]
        return rij.get("earned_days") or {}

    @staticmethod
    def _opgeleverd_totaal(rij: dict[str, Any]) -> float:
        if rij.get("realized_total") is not None:
            return float(rij["realized_total"])
        return float(rij.get("earned_total") or 0.0)

    async def _async_batterij_bewaren(
        self, settings: dict[str, Any], device_id: str, nieuw: dict[str, Any]
    ) -> None:
        """Wat de coach van deze batterij bijhoudt naar de instellingen."""
        rij = {**self._batterij_rij(settings, device_id), **nieuw}
        # Van v0.163.x, en niet te vertrouwen (v0.165.1, `_growatt_min_pct`).
        rij.pop("growatt_pct_geweigerd", None)
        for sleutel in ("earned_days", "realized_days", "solar_stored_days"):
            dagen = rij.get(sleutel) or {}
            if len(dagen) > BATTERIJ_DAGEN_MAX:
                rij[sleutel] = dict(sorted(dagen.items())[-BATTERIJ_DAGEN_MAX:])
        rows = [
            r for r in (settings.get("battery_state") or [])
            if isinstance(r, dict) and r.get("device") != device_id
        ]
        rows.append(rij)
        try:
            saved = await async_get_store(self.hass).async_save({"battery_state": rows})
        except Exception:  # noqa: BLE001 - een gemiste opslag is geen reden om te stoppen
            _LOGGER.exception("kon de stand van %s niet bewaren", device_id)
            return
        self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": saved})
        settings["battery_state"] = rows

    def _rte_gemeten(
        self,
        device: dict[str, Any],
        capaciteit: float | None,
        tellers: tuple[str, str] = ("energy_in", "energy_out"),
    ) -> float | None:
        """Het rendement uit twee tellers, standaard die van een kWh-meter op de batterij, of None."""
        entities = device.get("entities") or {}
        return rendement_uit_tellers(
            _kwh(self.hass, entities.get(tellers[0])),
            _kwh(self.hass, entities.get(tellers[1])),
            capaciteit,
        )

    async def _async_batterij_uitlezen(self, settings: dict[str, Any], device: dict[str, Any]) -> None:
        """Een batterij die de coach niet stuurt: het rendement uit zijn eigen tellers (v0.123.0).

        Voor de pop-up, net als bij een batterij die hij wel stuurt ("ongeveer
        90%, gemeten in de accu"). Een Growatt leest de coach alleen uit, en
        daarvan zijn de tellers wat er voor de bewoner overblijft. Meer doet hij
        er niet mee: geen stand, geen plan, geen kasboek.
        """
        device_id = device.get("id", "")
        rij = self._batterij_rij(settings, device_id)
        entities = device.get("entities") or {}
        try:
            opgave = float((device.get("battery") or {}).get("capacity_kwh") or 0.0) or None
        except (TypeError, ValueError):
            opgave = None
        capaciteit = _kwh(self.hass, entities.get("capacity")) or opgave
        accu = self._rte_gemeten(device, capaciteit, ("accu_in", "accu_out"))
        if accu is not None and abs(float(rij.get("rte_accu") or 0.0) - accu) > 0.002:
            await self._async_batterij_bewaren(settings, device_id, {"rte_accu": round(accu, 4)})

    @staticmethod
    def _slijtage(eigen: dict[str, Any], capaciteit: float | None) -> float:
        """De afschrijving per kWh uit de cellen (v0.146.0), of nul.

        Uit de aanschafprijs en het aantal laadcycli als beide er zijn, anders wat de
        bewoner per kWh invulde. Een cyclus is de hele inhoud er een keer uit. De
        eigenaar op 22-10-2026: "Voor de eenvoud.. aanschafprijs/minimaal aantal cycli.
        Zou restwaarde oid niet meenemen, die weet je toch niet."
        """
        def getal(sleutel: str) -> float | None:
            try:
                waarde = eigen.get(sleutel)
                return None if waarde in (None, "") else float(waarde)
            except (TypeError, ValueError):
                return None

        prijs, cycli = getal("wear_price"), getal("wear_cycles")
        if prijs is not None and cycli and capaciteit:
            return max(0.0, prijs / (cycli * capaciteit))
        return max(0.0, getal("wear_per_kwh") or 0.0)

    def _rendement_bron(
        self, device: dict[str, Any], capaciteit: float | None, rij: dict[str, Any], ingevuld: float | None
    ) -> tuple[float | None, Rendement | None]:
        """Met welk rendement de coach rekent (v0.145.0): het rendement heen en terug, en per vermogen of None.

        De eigenaar op 22-10-2026: "ik zou bij rendement altijd het gemeten rendement
        hanteren uit de aparte kwh meter, mits die aanwezig is. Is er geen aparte meter
        aanwezig, dan moet je de interne RTE hanteren", en die interne "zouden de eigen
        tellers moeten zijn, of het zelf geleerde mits dat betrouwbaarder is".

        1. Een kWh-meter op de batterij: wat die over alles samen meet, of de laatste
           meting als hij even niets zegt. Daar zit alles in, ook wat de batterij stil
           verbruikt. Het zelf geleerde (v0.142.0) telt alleen stappen van een procent
           tussen 10 en 90%, en kwam in een klantwoning op 85% waar de meter 76% zag.
        2. Zonder meter het zelf geleerde, als er genoeg stappen zijn: dat meet aan de
           wisselstroomkant, met het verlies in de omvormer erbij.
        3. Anders de eigen tellers van de batterij. Die meten aan de accukant en zien
           de omvormer niet, en tellen pas na tien keer de inhoud aan doorzet.
        4. Anders wat de bewoner invulde; zonder dat is het onbekend.
        """
        if (device.get("entities") or {}).get("energy_in") and (device.get("entities") or {}).get("energy_out"):
            meter = self._rte_gemeten(device, capaciteit) or (float(rij["rte"]) if rij.get("rte") else None)
            if meter is not None:
                return meter, None
        geleerd = rendement_uit_stappen(rij.get("rte_steps"))
        if geleerd is not None:
            return geleerd.rte, geleerd
        accu = self._rte_gemeten(device, capaciteit, ("accu_in", "accu_out")) or (
            float(rij["rte_accu"]) if rij.get("rte_accu") else None
        )
        if accu is not None:
            return accu, None
        return (ingevuld / 100.0 if ingevuld else None), None

    def _batterij_van(
        self, now: datetime, settings: dict[str, Any], device: dict[str, Any], rij: dict[str, Any]
    ) -> Batterij:
        """De batterij zoals hij er nu bij staat: sensoren eerst, dan wat er is ingevuld."""
        entities = device.get("entities") or {}
        eigen = device.get("battery") or {}

        def getal(sleutel: str) -> float | None:
            try:
                waarde = eigen.get(sleutel)
                return None if waarde in (None, "") else float(waarde)
            except (TypeError, ValueError):
                return None

        stuur = self.hass.states.get(entities.get("setpoint")) if entities.get("setpoint") else None
        attrs = getattr(stuur, "attributes", None) or {}

        def uit_knop(*namen: str) -> float | None:
            for naam in namen:
                try:
                    if attrs.get(naam) is not None:
                        return float(attrs[naam])
                except (TypeError, ValueError):
                    continue
            return None

        capaciteit = _kwh(self.hass, entities.get("capacity")) or getal("capacity_kwh")
        rte, rendement = self._rendement_bron(device, capaciteit, rij, getal("rte_percent"))

        laatst_vol = _tijdstip(rij.get("full_at"))
        return Batterij(
            soc=_number(self.hass, entities.get("soc")),
            capacity_kwh=capaciteit,
            max_charge_w=getal("max_charge_w") or uit_knop("max_charge_power", "max") or 0.0,
            max_discharge_w=getal("max_discharge_w") or uit_knop("max_discharge_power", "max") or 0.0,
            soc_min=_number(self.hass, entities.get("discharge_limit")) or 0.0,
            # Vakantiestand: de coach rekent met een lagere bovengrens, en laat
            # de laadgrens van de batterij zelf met rust. Zie `_vakantie`.
            soc_max=min(
                _number(self.hass, entities.get("charge_limit")) or 100.0,
                self._vakantie(device) or 100.0,
            ),
            reserve=float(eigen.get("reserve_percent") or 0) if eigen.get("reserve_enabled") else None,
            rte=rte,
            rendement=rendement,
            handelen=bool(eigen.get("trade")),
            # Handelen in twee, met een grens per richting (v0.141.0).
            net_laden=bool(eigen.get("grid_charge", True)),
            net_laden_onder=getal("grid_charge_below"),
            handelen_boven=getal("trade_above"),
            slijtage=self._slijtage(eigen, capaciteit),
            # De ondergrens aan wat bijladen van het net oplevert (v0.160.0); leeg is de standaard.
            min_winst=BIJLADEN_MIN_WINST if getal("grid_charge_min_gain") is None else getal("grid_charge_min_gain"),
            auto_boven=getal("car_above"),
            nacht=bool((settings.get("strategy") or {}).get("night_strategy", True)),
            power_w=self._batterij_w(device),
            vol_voor=vol_voor(
                now, bool(eigen.get("weekly_full")) and self._vakantie(device) is None,
                eigen.get("weekly_full_day"),
                laatst_vol.replace(tzinfo=None) if laatst_vol is not None else None,
            ),
            zelf_nul=self._zelf_instelling(device),
            # Vol blijven kan alleen als de coach hem kan overnemen en op 0 W zetten (v0.158.0).
            vol_vasthouden=self._zelf_instelling(device) and bool((device.get("entities") or {}).get("setpoint")),
        )

    @staticmethod
    def _vakantie(device: dict[str, Any]) -> float | None:
        """De bovengrens van de vakantiestand in procent, of None als die uitstaat.

        De bewoner van de eerste woning op 22-09-2026: "met name in de zomer
        met veel opwek en minimaal verbruik moet de accu regelmatig
        leeggetrokken worden; slecht voor de accucellen als ze te lang op 100%
        blijven staan." De coach houdt hem dan onder deze grens: wat erboven
        zit gaat naar het huis of, met handelen, naar het net, en er komt pas
        weer zon in als hij eronder zit. De wekelijkse volle beurt vervalt
        zolang de stand aanstaat.
        """
        eigen = device.get("battery") or {}
        if not eigen.get("holiday"):
            return None
        try:
            return float(eigen.get("holiday_max_percent") or HOLIDAY_MAX_DEFAULT)
        except (TypeError, ValueError):
            return float(HOLIDAY_MAX_DEFAULT)

    def _paal_laadt(self, settings: dict[str, Any]) -> bool:
        """Of er op dit moment een laadpaal laadt, van wie hij ook de opdracht kreeg.

        Gemeten aan zijn vermogen en niet aan het besluit van de coach: in de
        eerste woning stuurde iets anders de paal, en dan telt het net zo goed.
        De grens is de helft van wat een paal op zijn laagst levert.
        """
        for device in settings.get("devices") or []:
            if device.get("type") != "laadpaal":
                continue
            watt = _watts(self.hass, device.get("entity"))
            if watt is not None and watt > watts_for(MIN_AMPS, 1) / 2.0:
                return True
            # En wat de paal zelf zegt, want dat komt meteen: het vermogen van
            # een Alfen komt eens per 30 seconden. In de eerste woning op
            # 23-09-2026 om 15:58:56 zei de Alfen "auto laadt", en het vermogen
            # stond tot 15:59:25 op 0 W; de batterij gaf 25 seconden lang
            # 3,45 kW aan de auto (v0.87.1).
            entities = device.get("entities") or {}
            if entities.get("charging") and _text(self.hass, entities.get("charging")) == "on":
                return True
            if entities.get("status") and "charging" in _text(self.hass, entities.get("status")):
                return True
        return False

    async def _one_batterij(
        self, now: datetime, settings: dict[str, Any], device: dict[str, Any], level: str
    ) -> None:
        device_id = device.get("id", "")
        naam = device.get("name") or t("De batterij")
        rij = self._batterij_rij(settings, device_id)
        sessie = self._batterij_sessie(device_id)
        if "voorraad" not in sessie:
            sessie["voorraad"] = self._voorraad_uit(rij)
        b = self._batterij_van(now, settings, device, rij)
        schema = device.get("brand") in BATTERIJ_SCHEMA
        if schema:
            self._growatt_batterij(b, device, rij)
            # Handmatig vol laden of leegladen bestaat bij een Growatt niet (v0.156.0). De eigenaar
            # op 24-10-2026: "ik wil niet kunnen handmatig laden en ontladen bij growatt".
            if device_id in self._boost or device_id in self._drain:
                self._boost.discard(device_id)
                self._drain.pop(device_id, None)
                self._vol_tot.pop(device_id, None)
                self._remember(device_id)
        # Een beurt van het net die al loopt maakt het plan af, en voor een
        # kleine neemt hij een batterij die zelf nul doet niet over (v0.102.3,
        # `_rustig_vermogen` in batterij.py).
        vorig = sessie.get("besluit")
        b.vorige_stand = vorig.stand if vorig is not None else None
        b.vorige_op = sessie.get("besluit_op")
        b.overgenomen = bool(sessie.get("stuurt")) and sessie.get("zelf") is False
        entities = device.get("entities") or {}
        mag = level == LEVEL_STEER or (level == LEVEL_PROPOSE and device_id in self._approved)
        stuurt = mag and level not in (LEVEL_READ, LEVEL_ADVISE) and bool(entities.get("setpoint"))
        if schema:
            # Een Growatt heeft geen stuurgetal: het schema is de opdracht, en het vinkje
            # zegt of de coach dat mag schrijven (v0.150.0).
            stuurt = mag and level not in (LEVEL_READ, LEVEL_ADVISE) and bool(device.get("controllable"))

        # De wekelijkse volle beurt gaat tot honderd procent, want daar is hij
        # voor: het balanceren van de cellen. De laadgrens van de batterij is
        # van de batterij en de coach schrijft hem nooit, met deze ene
        # uitzondering (de keuze van de eigenaar op 22-09-2026): op de dag van
        # de volle beurt zet hij hem op 100, en zodra de batterij vol is, de
        # dag om is of de coach niet meer stuurt, zet hij hem terug op wat er
        # stond. Wat er stond staat in de opslag, zodat een herstart het niet
        # vergeet.
        grens_terug = rij.get("limit_restore")
        vol_grens = 100.0 if stuurt and entities.get("charge_limit") else b.soc_max
        vol_nu = b.soc is not None and b.soc >= vol_grens - VOL_MARGE
        if schema:
            pass
        elif grens_terug is None and b.vol_voor is not None and stuurt and not vol_nu:
            if await self._async_laadgrens_omhoog(settings, device, b.soc_max):
                b.soc_max = 100.0
                rij = self._batterij_rij(settings, device_id)
        elif grens_terug is not None and (vol_nu or b.vol_voor is None or not stuurt):
            await self._async_laadgrens_terug(settings, device)
            rij = self._batterij_rij(settings, device_id)

        prijzen = self._prices(settings)
        tarief = self._tarief(settings)
        verwachting = Forecast(
            solar_kwh=self._zon_kwh, house_kwh=self._huis_kwh, estimated=self._zon_geschat,
            solar_factor=self._zon_gemeten(now), solar_day=now.date(),
        )
        # De som over de tijd kost met een lange prijslijst een tiende seconde,
        # en dat hoort niet in de lus van Home Assistant zelf.
        besluit = await self.hass.async_add_executor_job(
            partial(
                plan_batterij, now, prijzen, tarief, verwachting, b,
                enabled=True, paal_laadt=self._paal_laadt(settings),
                helpt=bool(sessie.get("helpt")),
                auto_laden=self._auto_laden(),
                laadruimte=self._laadruimte_plan(settings, device),
            )
        )

        vakantie = self._vakantie(device)
        if vakantie is not None:
            besluit.reason = t(
                "Vakantiestand: hij houdt de batterij onder {pct}%. {reden}",
                pct=f"{vakantie:.0f}", reden=besluit.reason,
            )

        # "Nu leegladen tot X%": naar het net op het ontlaadvermogen tot de
        # gekozen accustand, en dan weer het plan. Boven het plan en boven de
        # avondpiek, net als snelladen; nooit onder de eigen ondergrens van
        # de batterij, en niet zolang de paal laadt (die gaat voor).
        leeg_tot = self._drain.get(device_id)
        if leeg_tot is not None:
            grens = max(leeg_tot, b.bodem)
            if b.soc is not None and b.soc <= grens + VOL_MARGE - 1.0:
                self._drain.pop(device_id, None)
                self._remember(device_id)
                await self._async_noteer(t("{naam} is leeggeladen tot {pct}%; hij volgt het plan weer.",
                                           naam=naam, pct=f"{grens:.0f}"), now,
                                         {"device": device_id})
            elif b.soc is not None and b.max_discharge_w > 0 and not self._paal_laadt(settings):
                besluit = Besluit(
                    HANDELEN,
                    power_w=b.max_discharge_w,
                    reason=t(
                        "Je hebt gevraagd hem nu leeg te laden tot {pct}%, dus hij levert aan het net op "
                        "{kw} kW, wat de prijs ook is.",
                        pct=f"{grens:.0f}", kw=getal(b.max_discharge_w / 1000, 1),
                    ),
                    plan=besluit.plan,
                    rule="leeg-laden",
                    waarde=besluit.waarde,
                    uren=besluit.uren,
                    inkoop_tot=besluit.inkoop_tot,
                )

        # "Nu vol laden": dezelfde knop als snelladen bij de paal, voor wie de
        # batterij nu vol wil hebben, wat het plan ook zegt. De eigenaar op
        # 22-09-2026: "eigenlijk wil je nu dat de batterij handmatig vol wordt
        # geladen." Gaat vanzelf uit zodra hij vol is; boven de avondpiek, net
        # als snelladen.
        if device_id in self._boost:
            # Met een doel uit de pop-up tot daar, nooit boven de laadgrens (v0.141.0).
            doel = min(self._vol_tot.get(device_id, b.soc_max), b.soc_max)
            if b.soc is not None and b.soc >= doel - VOL_MARGE:
                self._boost.discard(device_id)
                self._vol_tot.pop(device_id, None)
                self._remember(device_id)
                await self._async_noteer(
                    t("{naam} is vol; hij volgt het plan weer.", naam=naam) if doel >= b.soc_max else
                    t("{naam} is geladen tot {pct}%; hij volgt het plan weer.", naam=naam, pct=f"{doel:.0f}"),
                    now, {"device": device_id})
            elif b.soc is not None and b.max_charge_w > 0:
                besluit = Besluit(
                    MAX_LADEN,
                    power_w=b.max_charge_w,
                    reason=t(
                        "Je hebt gevraagd hem nu vol te laden, dus hij laadt van het net op "
                        "{kw} kW tot {pct}%, wat de prijs ook is.",
                        kw=getal(b.max_charge_w / 1000, 1), pct=f"{doel:.0f}",
                    ),
                    plan=besluit.plan,
                    rule="vol-laden",
                    waarde=besluit.waarde,
                    uren=besluit.uren,
                    inkoop_tot=besluit.inkoop_tot,
                )

        # Het gemeten rendement en de laatste volle stand bewaren, zodat ze een
        # herstart overleven en de kaart ze kan tonen.
        nieuw: dict[str, Any] = {}
        # Alleen een meting, nooit wat er ingevuld is (zie `_batterij_van`).
        gemeten = self._rte_gemeten(device, b.capacity_kwh)
        if gemeten is not None and abs(float(rij.get("rte") or 0.0) - gemeten) > 0.002:
            nieuw["rte"] = round(gemeten, 4)
        # Wat de eigen tellers van de batterij zeggen (v0.118.0). Die meten aan de
        # accukant en zien het verlies in de omvormer niet; sinds v0.145.0 rekent de
        # coach ermee als er geen kWh-meter en geen zelf geleerd rendement is
        # (`_rendement_bron`).
        accu = self._rte_gemeten(device, b.capacity_kwh, ("accu_in", "accu_out"))
        if accu is not None and abs(float(rij.get("rte_accu") or 0.0) - accu) > 0.002:
            nieuw["rte_accu"] = round(accu, 4)
        # Wat de regelaar aan stappen van een procent leerde (v0.142.0), en voor
        # de pop-up wat daar per richting uit komt. Zijn de metingen gewist, dan
        # begint hij opnieuw.
        meter = sessie.get("rte_meter")
        if meter is not None and rij.get("rte_steps") is None and sessie.get("rte_bewaard"):
            meter.sommen = {}
            sessie["rte_bewaard"] = False
        if meter is not None and sessie.get("rte_nieuw") and (
            sessie.get("rte_op") is None or now - sessie["rte_op"] >= BATTERIJ_BEWAREN
        ):
            nieuw["rte_steps"] = meter.sommen
            r = rendement_uit_stappen(meter.sommen)
            nieuw["rte_power"] = None if r is None else {
                "rte": round(r.rte, 4),
                "in": [[round(kw, 3), round(e, 4)] for kw, e in r.laden],
                "out": [[round(kw, 3), round(e, 4)] for kw, e in r.ontladen],
            }
            sessie.update(rte_nieuw=False, rte_op=now, rte_bewaard=True)
        if vol_nu:
            vorige = _tijdstip(rij.get("full_at"))
            if vorige is None or now - vorige.replace(tzinfo=None) > timedelta(hours=1):
                nieuw["full_at"] = now.isoformat()
        geld = sessie.get("geld")
        if geld and (sessie.get("bewaard_op") is None or now - sessie["bewaard_op"] >= BATTERIJ_BEWAREN):
            dagen = dict(rij.get("earned_days") or {})
            for dag, euro in geld.items():
                dagen[dag] = round(float(dagen.get(dag) or 0.0) + euro, 5)
            nieuw["earned_days"] = dagen
            nieuw["earned_total"] = round(float(rij.get("earned_total") or 0.0) + sum(geld.values()), 5)
            sessie["geld"] = {}
            # Wat ze werkelijk opleverde (v0.107.0, `Voorraad`), en wat er nog
            # in zit. Van voor deze versie is alleen het kasboek bekend: die
            # dagen tellen zoals ze geteld zijn.
            echt = dict(self._opgeleverd_dagen(rij))
            for dag, euro in (sessie.get("opgeleverd") or {}).items():
                echt[dag] = round(float(echt.get(dag) or 0.0) + euro, 5)
            nieuw["realized_days"] = echt
            nieuw["realized_total"] = round(
                self._opgeleverd_totaal(rij) + sum((sessie.get("opgeleverd") or {}).values()), 5)
            sessie["opgeleverd"] = {}
            voorraad: Voorraad = sessie["voorraad"]
            nieuw["stock_euro"] = round(voorraad.euro, 5)
            # De zon die erin ging (`zon_in_accu`), per dag, en vanaf wanneer dat
            # geteld wordt: wat daarvoor lag schat Historie uit de statistieken.
            zon_dagen = dict(rij.get("solar_stored_days") or {})
            for dag, euro in (sessie.get("zon") or {}).items():
                zon_dagen[dag] = round(float(zon_dagen.get(dag) or 0.0) + euro, 5)
            nieuw["solar_stored_days"] = zon_dagen
            if not rij.get("solar_stored_from") and sessie.get("zon_vanaf") is not None:
                nieuw["solar_stored_from"] = sessie["zon_vanaf"].isoformat()
            sessie["zon"] = {}
            sessie["bewaard_op"] = now
        if nieuw:
            await self._async_batterij_bewaren(settings, device_id, nieuw)
            rij = self._batterij_rij(settings, device_id)

        nu_rij = price_now(prijzen, now)
        koop = nu_rij["price"] if nu_rij else tarief.buy
        terug = nu_rij.get("feed_in") if nu_rij else tarief.feed_in
        # Wat de batterij er de komende minuut van het net bij neemt, voor de
        # voorrang bij planningen (v0.93.0): wie lager staat krijgt de ruimte
        # die daarna over is. Zon en nul op de meter zeggen niets toe.
        if besluit.stand in (NETLADEN, MAX_LADEN):
            doel_w = besluit.power_w or b.max_charge_w
            nu_w = max(0.0, self._batterij_geregeld_w(device) or 0.0)
            self._toezeggingen[device_id] = {
                "amps": max(0.0, doel_w - nu_w) / VOLTS,
                "sleutels": self._groep_sleutels(settings, device),
            }
        else:
            self._toezeggingen.pop(device_id, None)
        sessie.update(besluit=besluit, besluit_op=now, batterij=b, koop=koop, terug=terug,
                      settings=settings, device=device,
                      # Wat er morgenvroeg over is, voor de snelle regelaar: die
                      # beslist elke paar seconden of de batterij de auto mag
                      # helpen (`auto_grens`, v0.90.0).
                      nacht_over=(nacht_over := balans_kwh(now, verwachting, b)),
                      auto_grens=auto_grens(b, nacht_over))

        totaal = self._opgeleverd_totaal(rij) + sum((sessie.get("opgeleverd") or {}).values())
        # Wat ze opleverde sinds de coach haar volgt, voor "Opgeleverd" op de
        # kaart, en wat de stroom kostte die er nog in zit. Laden is inkopen,
        # dus het bedrag zakt niet meer terwijl ze laadt (v0.107.0, `Voorraad`).
        # Geen terugverdientijd meer (v0.101.1, zie `verdiend`).
        opgeleverd = {
            "euro": round(totaal, 2),
            "days": len(self._opgeleverd_dagen(rij)),
            "stock_euro": round(sessie["voorraad"].euro, 2),
        }

        # Een Growatt doet wat zijn schema zegt (v0.156.0): het besluit en de reden komen daaruit,
        # niet uit het plan van dit kwartier. Met de coach aan het stuur wat erin staat, in de
        # schaduw wat hij zou schrijven; de conclusie voor de nacht uit wat hij gaat schrijven.
        if schema:
            wil_nu = sessie.get("growatt_wil")
            besluit = growatt_besluit(
                besluit, sessie.get("growatt_geschreven") if stuurt else wil_nu, now, b,
                balans_kwh(now, verwachting, b, besluit.auto_weg), wil=wil_nu,
            )

        # Het hele plan, voor de vooruitblik op het overzicht (v0.133.0): de
        # toestand neemt er 48 blokken van, met kwartierprijzen maar twaalf uur.
        sessie["uren"] = list(besluit.uren)
        self.state[device_id] = {
            "charge": besluit.stand in (NETLADEN, MAX_LADEN),
            "amps": 0,
            "reason": besluit.reason,
            "plan": besluit.plan,
            # Wat er morgenvroeg naar verwachting over is of tekortkomt, zodat de
            # kaart de conclusie groen of oranje kan maken.
            # Met wat de auto er volgens zijn plan uit haalt (v0.95.0). De grens
            # voor de auto zelf rekent zonder, anders telt die hulp dubbel.
            "balance_kwh": None if (bal := balans_kwh(now, verwachting, b, besluit.auto_weg)) is None else round(bal, 2),
            "car_floor": None if (vloer := sessie.get("auto_grens")) is None else round(vloer, 1),
            "rule": besluit.rule,
            "kind": "batterij",
            "mode": besluit.stand,
            "mode_name": STAND_NAMEN.get(besluit.stand, besluit.stand),
            "at": now.isoformat(),
            "level": level,
            "applied": stuurt,
            "approved": device_id in self._approved,
            "soc": b.soc,
            "power_w": None if b.power_w is None else round(b.power_w),
            # Een Growatt heeft geen stuurgetal maar een schema (`schedule`, v0.156.0).
            "setpoint_w": round(sessie["regelaar"].opdracht_w) if stuurt and not schema else None,
            "target_w": round(besluit.power_w),
            "value": None if besluit.waarde is None else round(besluit.waarde, 4),
            # Onder welke prijs bijkopen nu loont, voor de pop-up (v0.102.3).
            "buy_below": None if besluit.inkoop_tot is None else round(besluit.inkoop_tot, 4),
            "rte": None if b.rte is None else round(b.rte, 3),
            "capacity_kwh": b.capacity_kwh,
            "floor": b.bodem,
            "ceiling": b.soc_max,
            "full_before": b.vol_voor.isoformat() if b.vol_voor else None,
            "earned": opgeleverd,
            "boost": device_id in self._boost,
            # Tot waar "Nu vol laden" gaat, als de bewoner een doel koos (v0.141.0).
            "boost_to": self._vol_tot.get(device_id) if device_id in self._boost else None,
            "drain_to": self._drain.get(device_id),
            "holiday": vakantie is not None,
            "hours": [
                {
                    "start": uur.start.isoformat(), "end": uur.end.isoformat(), "mode": uur.stand,
                    "kwh": round(uur.kwh, 2), "grid_kwh": round(uur.net_kwh, 2),
                    "car_kwh": round(uur.auto_kwh, 2),
                    "soc": round(uur.soc), "price": uur.price,
                }
                for uur in besluit.uren[:48]
            ],
            # Iets dat alleen de bewoner of de installateur kan verhelpen, naast
            # de reden op de kaart (v0.128.2). Zie `handelen_kan_niet`.
            "tip": t(HANDELEN_KAN_NIET) if handelen_kan_niet(b, prijzen, now) else "",
        }

        kern = (besluit.stand, besluit.rule, stuurt)
        if self._besluit_genoteerd.get(device_id) != kern:
            self._besluit_genoteerd[device_id] = kern
            kop = t(STAND_NAMEN.get(besluit.stand, besluit.stand)).lower()
            if not stuurt:
                kop = t("zou op {stand} staan, maar de coach stuurt nu niet", stand=kop)
            await self._async_noteer(f"{naam}: {kop}. {besluit.reason}".strip(), now, {
                "device": device_id, "mode": besluit.stand, "rule": besluit.rule, "applied": stuurt,
            })

        # Iets anders stuurt de batterij: de modus staat niet meer op wat de
        # coach zette. In de eerste woning op 22-09-2026 nam evcc de Anker
        # over terwijl de coach hem op voorstellen had staan; had de coach
        # hem toen nog gestuurd, dan hadden twee sturingen om hetzelfde
        # register gevochten. Dus: twee ronden een andere modus, en de coach
        # laat los zonder zelf nog iets te schrijven (een 0 W zou de ander
        # overschrijven), zegt het één keer, en probeert het na
        # `VREEMD_PAUZE` opnieuw.
        #
        # Niet terwijl de regelaar bezig is. Die kan net de modus omzetten en
        # dan op de stuurknop wachten, en wat de sessie wil ("zelf") staat er
        # pas als dat klaar is. Bij de eigenaar op 11-10-2026 nam een tik van de
        # meter de batterij over voor de paal, zette om 12:08:05 de modus om en
        # wachtte tot 12:08:08 op de knop; de rondes die intussen kwamen, één
        # per wissel van de paal, zagen de modus van de coach zelf als een
        # andere sturing, en de coach liet de batterij een uur los. Zo'n ronde
        # telt niet en zet de teller ook niet terug.
        if stuurt and sessie.get("stuurt") and not sessie.get("bezig"):
            modus_entity = entities.get("mode")
            # Doet hij zelf nul op de meter, dan zette de coach zijn eigen stand.
            welke = "idle_mode" if sessie.get("zelf") else "control_mode"
            wil = ((device.get("battery") or {}).get(welke) or "").strip()
            staat = self.hass.states.get(modus_entity) if modus_entity else None
            anders = bool(wil) and staat is not None and staat.state not in ("unknown", "unavailable") and staat.state != wil
            sessie["modus_anders"] = sessie.get("modus_anders", 0) + 1 if anders else 0
            if sessie["modus_anders"] >= VREEMD_RONDEN:
                sessie["stuurt"] = False
                sessie["regelaar"] = Regelaar()
                sessie["vreemd"] = now
                sessie["modus_anders"] = 0
                _LOGGER.warning("%s: de modus staat op %s en niet op %s; iets anders stuurt, de coach laat los",
                                device_id, staat.state, wil)
                await self._async_tell(
                    t(
                        "Iets anders stuurt {naam}: de bedrijfsmodus staat niet meer op wat de coach zette. "
                        "De coach laat hem los en probeert het over een uur opnieuw. Zet de andere sturing uit, "
                        "of haal bij de coach het vinkje 'mag sturen' weg.",
                        naam=naam,
                    ),
                    kritiek=True,
                )
        if sessie.get("vreemd") is not None:
            if now - sessie["vreemd"] < VREEMD_PAUZE:
                stuurt = False
            else:
                sessie.pop("vreemd", None)
        self.state[device_id]["applied"] = stuurt
        self.state[device_id]["foreign"] = sessie.get("vreemd") is not None

        if schema:
            await self._async_growatt(now, settings, device, b, besluit, stuurt, sessie)
            return

        if stuurt and not sessie.get("stuurt"):
            if self._zelf_instelling(device):
                # Welke modus het wordt kiest `_async_regel` meteen hieronder.
                sessie["zelf"] = None
            elif self._knop_weg(device):
                # Is de knop in de eigen stand weg, dan net als bij het overnemen:
                # eerst de stand, en de 0 W zodra de knop er is. Tot 29-09-2026
                # zette dit alleen de modus, en schreef de regelaar zijn eerste
                # opdracht naar een knop die er nog niet was (in de klantwoning
                # 14 s weg); daarna dacht hij dat die opdracht stond.
                sessie["nul_open"] = not await self._async_overnemen_op_nul(device)
                sessie["regelaar"] = Regelaar(opdracht_w=0.0, opdracht_op=_regelklok(), bezonken=False)
                sessie["zelf"] = False
            else:
                # De knop is er: de regelaar schrijft in deze ronde meteen zijn opdracht.
                await self._async_batterij_modus(device, "control_mode")
                sessie["zelf"] = False
            sessie["stuurt"] = True
        elif not stuurt and sessie.get("stuurt"):
            await self._async_batterij_loslaten(device)
        if stuurt:
            await self._async_regel(device_id, settings, device)
        zelf = bool(stuurt and sessie.get("zelf"))
        self.state[device_id]["self_zero"] = zelf
        if zelf:
            # Alleen als het plan ook nul op de meter is. Loopt het overnemen
            # nog (de coach wacht op de stuurknop), dan staat hij nog in zijn
            # eigen stand terwijl het besluit al iets anders zegt, en dan stond
            # er bij de eigenaar op 30-09-2026 een ronde lang "De laadpaal
            # laadt, dus de batterij geeft niets af. De batterij doet dat zelf."
            if besluit.stand == NUL:
                self.state[device_id]["reason"] = t(
                    "{reden} De batterij doet dat zelf, met zijn eigen meter.", reden=besluit.reason
                ).strip()
            self.state[device_id]["setpoint_w"] = None
        if stuurt:
            await self._async_volgt_niet(now, settings, device, sessie, besluit)

    def _volgt_niet(self, settings: dict[str, Any], device: dict[str, Any], sessie: dict[str, Any],
                    besluit: Besluit) -> str | None:
        """Wat de batterij nu anders doet dan de coach wil, of None (v0.167.0).

        "net" als ze van het net laadt terwijl de coach niet van het net wil laden, "ontladen" als ze
        ontlaadt terwijl de coach laden of stilstaan wil. Helpt ze de auto, dan is ontladen de bedoeling.
        """
        watt = self._batterij_w(device)
        if watt is None or not sessie.get("stuurt") or sessie.get("bezig"):
            return None
        net_w = self._net_nu(settings)[0]
        if (watt > VOLGT_NIET_W and net_w is not None and net_w > VOLGT_NIET_W
                and besluit.stand in (NUL, ZONNELADEN, ONTLADEN, HANDELEN, STANDBY)):
            return "net"
        if (watt < -VOLGT_NIET_W and not sessie.get("helpt")
                and besluit.stand in (NETLADEN, MAX_LADEN, ZONNELADEN, STANDBY)):
            return "ontladen"
        return None

    async def _async_volgt_niet(self, now: datetime, settings: dict[str, Any], device: dict[str, Any],
                                sessie: dict[str, Any], besluit: Besluit) -> None:
        """Een batterij die de coach niet volgt: zeggen, één keer opnieuw, en na tien minuten melden."""
        device_id = device.get("id", "")
        naam = device.get("name") or t("De batterij")
        wat = self._volgt_niet(settings, device, sessie, besluit)
        if wat is None:
            sessie.pop("volgt_niet", None)
            if sessie.pop("volgt_niet_gemeld", False):
                await self._async_tell(t("{naam} volgt de coach weer.", naam=naam), telefoon=False)
            if sessie.get("volgt_extern_tot") is not None and now >= sessie["volgt_extern_tot"]:
                sessie.pop("volgt_extern_tot", None)
            return
        sinds, opnieuw = sessie.get("volgt_niet") or (now, False)
        sessie["volgt_niet"] = (sinds, opnieuw)
        if now - sinds < VOLGT_NIET_NA:
            return
        self.state[device_id]["reason"] = (
            t("{naam} laadt zelf van het net, en niet wat de coach wil. De coach probeert het opnieuw.", naam=naam)
            if wat == "net" else
            t("{naam} ontlaadt zelf, en niet wat de coach wil. De coach probeert het opnieuw.", naam=naam)
        )
        if not opnieuw:
            sessie["volgt_niet"] = (sinds, True)
            _LOGGER.warning("%s volgt de coach niet: de coach wil %s, de batterij doet %.0f W (net %s W)",
                            device_id, besluit.stand, self._batterij_w(device) or 0.0,
                            None if (n := self._net_nu(settings)[0]) is None else round(n))
            await self._async_noteer(
                t("{naam} volgt de coach niet; de coach probeert het opnieuw.", naam=naam), now,
                {"device": device_id, "mode": besluit.stand, "rule": "volgt-niet", "applied": True},
            )
            if sessie.get("zelf"):
                # In haar eigen stand: overnemen op 0 W, en zolang niet teruggeven.
                sessie["nul_open"] = not await self._async_overnemen_op_nul(device)
                sessie["zelf"] = False
                sessie["volgt_extern_tot"] = now + VOLGT_NIET_EXTERN
            else:
                await self._async_batterij_zetten(device, 0.0)
            sessie["regelaar"] = Regelaar(opdracht_w=0.0, opdracht_op=_regelklok(), bezonken=False)
            return
        if now - sinds >= VOLGT_NIET_MELDEN and not sessie.get("volgt_niet_gemeld"):
            sessie["volgt_niet_gemeld"] = True
            await self._async_tell(
                t("{naam} volgt de coach niet en laadt van het net. Kijk of de batterij zelf iets doet, zoals "
                  "kalibreren of een update.", naam=naam)
                if wat == "net" else
                t("{naam} volgt de coach niet en ontlaadt. Kijk of de batterij zelf iets doet, zoals "
                  "kalibreren of een update.", naam=naam),
                kritiek=True,
            )

    def _kasboek(
        self, sessie: dict[str, Any], settings: dict[str, Any], device_id: str, nu: datetime,
        net_w: float | None, bat_w: float | None, b: Batterij,
    ) -> None:
        """Het kasboek van een batterij: wat ze sinds de vorige stap opleverde.

        Uit de regelaar gehaald in v0.150.0, zodat een Growatt, die geen regelaar heeft,
        hetzelfde boekt: eens per ronde, met zijn eigen sensor.
        """
        vorige = sessie.get("geteld_op")
        sessie["geteld_op"] = nu
        if vorige is not None and net_w is not None:
            seconden = min(60.0, max(0.0, (nu - vorige).total_seconds()))
            # Nooit meer dan de batterij kan. De ontlaadsensor van de Anker
            # in de klantwoning gaf tussen 30-09 en 10-10-2026 2.856 keer meer
            # dan 3.600 W, tot 7.000 W, bij een batterij van 3.500 W; op
            # 02-10-2026 om 15:52:30 zag de meter op zijn fase 5,1 kW
            # teruglevering met 6,0 kW zon over drie fasen, en dat past bij
            # 3,5 kW uit de batterij, niet bij 7. Elk van die tikken telde
            # in het kasboek als stroom die het huis niet hoefde te kopen.
            if bat_w is not None:
                if b.max_charge_w > 0:
                    bat_w = min(bat_w, b.max_charge_w)
                if b.max_discharge_w > 0:
                    bat_w = max(bat_w, -b.max_discharge_w)
            # Doet hij het zelf en is zijn sensor weg, dan valt er deze stap
            # niets te tellen. Tot v0.112.1 viel `verdiend` hier om, en daarmee
            # alles hieronder: thuis bij de eigenaar op 11-10-2026 rond de
            # herstarts, en een paal die toen ging laden had de batterij niet
            # uit haar eigen stand gekregen (proef 148).
            euro = verdiend(net_w, bat_w,
                            sessie.get("koop"), sessie.get("terug"), seconden) if bat_w is not None else None
            if euro is not None:
                dag = nu.date().isoformat()
                geld = sessie.setdefault("geld", {})
                geld[dag] = geld.get(dag, 0.0) + euro
                # En wat ze werkelijk opleverde: laden is inkopen, pas
                # ontladen levert op (v0.107.0, `Voorraad`).
                if "voorraad" not in sessie:
                    sessie["voorraad"] = self._voorraad_uit(self._batterij_rij(settings, device_id))
                opgeleverd = sessie.setdefault("opgeleverd", {})
                opgeleverd[dag] = opgeleverd.get(dag, 0.0) + sessie["voorraad"].stap(
                    euro, bat_w * seconden / 3_600_000.0, b.soc, b.bodem, b.capacity_kwh, b.rte)
                # En wat de zon die erin ging minder waard was dan zelf
                # gebruikt, voor "Door je zon" in Historie (v0.101.2).
                zon = sessie.setdefault("zon", {})
                zon[dag] = zon.get(dag, 0.0) + (
                    zon_in_accu(net_w, bat_w, sessie.get("koop"), sessie.get("terug"), seconden) or 0.0
                )
                sessie.setdefault("zon_vanaf", nu)

    async def _async_regel(
        self, device_id: str, settings: dict[str, Any], device: dict[str, Any]
    ) -> None:
        """Eén stap van de regelaar: de meter lezen, de som maken, zo nodig schrijven.

        Wordt wakker van elke nieuwe waarde van de meter, en daarnaast om de
        vijf seconden: een meter die zwijgt meldt dat niet zelf.
        """
        sessie = self._batterij.get(device_id)
        if not sessie or not sessie.get("stuurt") or sessie.get("bezig"):
            return
        sessie["bezig"] = True
        try:
            nu = _moment()
            net_w, net_op = self._net_nu(settings)
            batterij_w = self._batterij_w(device)
            regelaar: Regelaar = sessie["regelaar"]
            b: Batterij = sessie["batterij"]
            soc = _number(self.hass, (device.get("entities") or {}).get("soc"))
            if soc is not None:
                b.soc = soc

            # Het rendement per vermogen leren (v0.142.0): de sensor van de
            # batterij en niet de opdracht, want het gaat om wat er echt liep,
            # en de tellers van een kWh-meter op de batterij als die er zijn.
            meter = sessie.get("rte_meter")
            if meter is None:
                bewaard = self._batterij_rij(settings, device_id).get("rte_steps")
                meter = sessie["rte_meter"] = Rendementmeter(sommen=dict(bewaard) if isinstance(bewaard, dict) else {})
                sessie["rte_bewaard"] = isinstance(bewaard, dict)
            entities = device.get("entities") or {}
            if meter.tik(nu, soc, batterij_w, b.capacity_kwh,
                         _kwh(self.hass, entities.get("energy_in")), _kwh(self.hass, entities.get("energy_out"))):
                sessie["rte_nieuw"] = True

            # Het kasboek: wat de batterij sinds de vorige stap opleverde. Doet
            # hij zelf nul op de meter, dan is de sensor de enige bron.
            self._kasboek(sessie, settings, device_id, nu, net_w,
                          batterij_w if sessie.get("zelf") else regelaar.vermogen_w(batterij_w), b)

            # Laadt er intussen een paal, dan geeft de batterij niets af, ook
            # als het besluit van deze minuut dat nog niet wist: de regelaar
            # tikt elke paar seconden, de besluitronde eens per minuut (v0.87.1).
            paal_laadt = self._paal_laadt(settings)
            besluit = sessie["besluit"]
            if self._paal_net_uit(sessie, paal_laadt, nu, net_op):
                # Op een kopie: het besluit van de ronde blijft zoals het is,
                # en geldt weer zodra de meter bij is.
                besluit = replace(besluit)
                paal_laadt = True
            besluit = met_paal(
                besluit, paal_laadt, b, sessie.get("nacht_over"),
                grens=sessie.get("auto_grens"), helpt=bool(sessie.get("helpt")),
            )
            sessie["helpt"] = besluit.rule == "auto-helpen"
            hoger = self._hogere_toezeggingen(settings, device)
            ruimte_w = self._laadruimte_w(settings, device, batterij_w, hoger)
            if self._zelf_instelling(device) or sessie.get("zelf"):
                extern_tot = sessie.get("volgt_extern_tot")
                waarom = t("hij volgde zijn eigen stand niet") if extern_tot is not None and nu < extern_tot else self._zelf_niet(
                    device, besluit, b, batterij_w, ruimte_w,
                    # Zonder wat een ander toezegde, en of dat een laadpaal was:
                    # dan is het niet de zekering maar de paal die gaat laden.
                    kaal_w=self._laadruimte_w(settings, device, batterij_w) if hoger else None,
                    paal_belooft=self._paal_belooft(settings),
                )
                await self._async_zelf_wissel(device, sessie, nu, waarom)
                if sessie.get("zelf"):
                    return
                regelaar = sessie["regelaar"]
            if sessie.get("nul_open"):
                # Het overnemen of de laatste opdracht kwam niet aan: de knop was
                # onbereikbaar, en in het register kan nog van alles staan. Zolang
                # hij weg is valt er niets te sturen; is hij terug, dan eerst 0 W,
                # en de regelaar begint daar opnieuw.
                if not await self._async_batterij_zetten(device, 0.0):
                    return
                sessie["nul_open"] = False
                sessie["regelaar"] = Regelaar(opdracht_w=0.0, opdracht_op=_regelklok(), bezonken=False)
                _LOGGER.info("%s: de stuurknop is er weer, 0 W geschreven", device_id)
                return
            # Op zijn eigen klok, die bij de wintertijd niet terugloopt (v0.139.1).
            opdracht = regelaar.stap(
                _regelklok(), net_w=net_w, net_op=None if net_op is None else _regelklok(net_op), batterij_w=batterij_w,
                besluit=besluit, b=b,
                doel_w=regelaar.doel_w(sessie.get("koop"), sessie.get("terug")),
                ruimte_w=ruimte_w,
            )
            if opdracht is not None and not await self._async_batterij_zetten(device, opdracht):
                sessie["nul_open"] = True
        except ServiceNotFound:
            _LOGGER.warning("%s kan nog niet aangestuurd worden (nog niet geladen?)", device_id)
        except Exception:  # noqa: BLE001 - de regelaar mag nooit stilvallen op één fout
            _LOGGER.exception("de regelaar van %s struikelde", device_id)
        finally:
            sessie["bezig"] = False

    @staticmethod
    def _zelf_instelling(device: dict[str, Any]) -> bool:
        """Of de bewoner de batterij zelf nul op de meter laat doen, en dat kan."""
        eigen = device.get("battery") or {}
        return bool(
            eigen.get("self_zero", True) and (device.get("entities") or {}).get("mode")
            and (eigen.get("idle_mode") or "").strip() and (eigen.get("control_mode") or "").strip()
        )

    def _zelf_niet(
        self, device: dict[str, Any], besluit: Besluit, b: Batterij,
        batterij_w: float | None, ruimte_w: float | None,
        kaal_w: float | None = None, paal_belooft: bool = False,
    ) -> str | None:
        """Waarom de batterij het nu niet zelf mag doen, of None als het mag.

        `kaal_w` is de ruimte zonder wat andere apparaten toezegden, of None
        als niemand iets toezegde.
        """
        if not self._zelf_instelling(device):
            return t("je hebt het uitgezet")
        if besluit.stand != NUL:
            if besluit.rule == "paal-laadt":
                return t("de laadpaal laadt")
            return t("het plan zegt {stand}", stand=t(STAND_NAMEN.get(besluit.stand, besluit.stand)).lower())
        if self._vakantie(device) is not None:
            return t("de vakantiestand staat aan")
        if b.soc is None:
            return t("de accustand is niet bekend")
        # Zijn eigen ondergrens kent hij; een hogere reserve van de bewoner niet.
        if b.bodem > b.soc_min and b.soc <= b.bodem + ZELF_MARGE:
            return t("hij zit bij de reserve voor noodstroom")
        eigen_w = max(0.0, batterij_w or 0.0)
        if ruimte_w is not None and ruimte_w - eigen_w < ZELF_ZEKERING_W:
            # Is het krap door wat een ander apparaat toezegde en nog niet
            # neemt, dan is dat de reden. Bij de eigenaar op 30-09-2026 om
            # 12:01:42: de paal had 16 A toegezegd en laadde nog niet, de fase
            # van de batterij stond op 4 A, en de melding zei "want de zekering
            # wordt krap".
            if kaal_w is not None and kaal_w - eigen_w >= ZELF_ZEKERING_W:
                return t("de laadpaal gaat laden") if paal_belooft else t("een ander apparaat krijgt de ruimte")
            return t("de zekering wordt krap")
        return None

    def _paal_belooft(self, settings: dict[str, Any]) -> bool:
        """Of een laadpaal deze ronde stroom toezegde die hij nog niet neemt."""
        soort = {a.get("id"): a.get("type") for a in settings.get("devices") or []}
        return any(
            soort.get(apparaat_id) == "laadpaal" and float(toezegging.get("amps") or 0.0) > 0
            for apparaat_id, toezegging in self._toezeggingen.items()
        )

    @staticmethod
    def _paal_net_uit(
        sessie: dict[str, Any], laadt: bool, nu: datetime, net_op: datetime | None
    ) -> bool:
        """Of de paal net stopte en de meter dat nog niet gezien heeft. Zie `PAAL_UIT_WACHT`."""
        if laadt:
            sessie["paal_op"] = nu
            return False
        gezien = sessie.get("paal_op")
        if gezien is None:
            return False
        if (net_op is not None and net_op > gezien + PAAL_UIT_WACHT) or nu - gezien > PAAL_UIT_LANGST:
            sessie.pop("paal_op", None)
            return False
        return True

    async def _async_zelf_wissel(
        self, device: dict[str, Any], sessie: dict[str, Any], nu: datetime, waarom: str | None
    ) -> None:
        """De batterij in zijn eigen stand zetten, of hem overnemen.

        Overnemen gaat meteen, teruggeven pas na `ZELF_WACHT`. In allebei de
        richtingen 0 W in het register: in zijn eigen stand doet de batterij
        daar niets mee, en bij het overnemen begint hij dan op nul in plaats van
        op een oude opdracht. Hoe dat gaat als de stuurknop in zijn eigen stand
        onbereikbaar is staat bij `_async_overnemen_op_nul`.
        """
        naam = device.get("name") or t("De batterij")
        zelf = sessie.get("zelf")
        if waarom is None:
            sessie.setdefault("zelf_sinds", nu)
            if zelf is None or (zelf is False and nu - sessie["zelf_sinds"] >= ZELF_WACHT):
                await self._async_batterij_zetten(device, 0.0)
                await self._async_batterij_modus(device, "idle_mode")
                sessie["zelf"] = True
                sessie["nul_open"] = False
                sessie["regelaar"] = Regelaar()
                await self._async_noteer(t("{naam} doet zelf nul op de meter, met zijn eigen meter.", naam=naam), nu,
                                         {"device": device.get("id"), "self_zero": True})
            return
        sessie.pop("zelf_sinds", None)
        if zelf is False:
            return
        sessie["nul_open"] = not await self._async_overnemen_op_nul(device)
        # Hij staat nu op nul, of zodra de knop er is; de regelaar wacht tot dat te zien is.
        sessie["regelaar"] = Regelaar(opdracht_w=0.0, opdracht_op=_regelklok(), bezonken=False)
        sessie["zelf"] = False
        if zelf:
            await self._async_noteer(t("{naam}: de coach neemt het over, want {waarom}.", naam=naam, waarom=waarom), nu,
                                     {"device": device.get("id"), "self_zero": False})

    def _knop_weg(self, device: dict[str, Any]) -> bool:
        """Of de stuurknop van de batterij nu onbereikbaar is."""
        knop = (device.get("entities") or {}).get("setpoint")
        staat = self.hass.states.get(knop) if knop else None
        return staat is not None and staat.state == "unavailable"

    async def _async_overnemen_op_nul(self, device: dict[str, Any]) -> bool:
        """De batterij in de externe stand, op 0 W (v0.100.2). False als de 0 W er nog niet in staat.

        Eerst 0 W en dan de stand, zodat hij nooit op een oude opdracht begint.
        Maar de Anker van de eigenaar maakt zijn stuurknop en richting in zijn
        eigen stand onbereikbaar (28-09-2026: om 11:07:55 naar
        `self_consumption`, om 11:07:56 allebei `unavailable`), en Home
        Assistant slaat een dienst aan een onbereikbare entiteit zonder melding
        over. Die 0 W kwam dan nooit aan, en de batterij begon in de externe
        stand op wat er nog in het register stond: in de eerste woning de
        laatste opdracht van de sturing die er daarvoor was. Is de knop weg,
        dan eerst de stand, wachten tot de knop er weer is, en dan de 0 W.

        Hooguit `KNOP_WACHT_STAPPEN` keer `KNOP_WACHT_STAP`, want zolang wacht
        de rest van de ronde ook. In de klantwoning kwam de knop op 29-09-2026
        pas na 14 s terug (15:51:42 omgezet, 15:51:56 terug); dan zet de
        aanroeper `nul_open` en schrijft de regelaar de 0 W zodra hij er is.
        """
        if not self._knop_weg(device):
            await self._async_batterij_zetten(device, 0.0)
            await self._async_batterij_modus(device, "control_mode")
            return True
        await self._async_batterij_modus(device, "control_mode")
        for _ in range(KNOP_WACHT_STAPPEN):
            if not self._knop_weg(device):
                return await self._async_batterij_zetten(device, 0.0)
            await self._sleep(KNOP_WACHT_STAP)
        _LOGGER.info(
            "%s: de stuurknop %s is na het omzetten nog onbereikbaar; de 0 W volgt zodra hij er is",
            device.get("id"), (device.get("entities") or {}).get("setpoint"),
        )
        return False

    async def _async_regel_tik(self, _now: datetime | None = None) -> None:
        """De regelaar van elke gestuurde batterij één stap laten doen."""
        # Met de instellingen van de laatste ronde, en niet opnieuw uit de
        # opslag: een meter die per seconde meldt zou anders elke seconde een
        # kopie van alle instellingen maken. Wat er verandert (het vinkje eraf,
        # een andere sensor) pakt de ronde binnen een minuut op.
        if self._stopt:
            return
        for device_id, sessie in list(self._batterij.items()):
            if sessie.get("stuurt") and sessie.get("settings") is not None:
                await self._async_regel(device_id, sessie["settings"], sessie["device"])

    @callback
    def _async_meter_gemeld(self, _event) -> None:
        self.hass.async_create_task(self._async_regel_tik())

    def _watch_batterij(self, settings: dict[str, Any], batterijen: list[dict[str, Any]]) -> None:
        """Meeluisteren met de meter, zolang er een batterij is om te sturen."""
        sources = settings.get("sources") or {}
        if not batterijen:
            namen: set[str] = set()
        elif sources.get("grid_mode") == "signed":
            namen = {sources.get("grid_signed")}
        else:
            namen = {sources.get("grid_import"), sources.get("grid_export")}
        namen = {naam for naam in namen if naam}
        if namen == self._batterij_meters:
            return
        for opzeggen in (self._unwatch_batterij, self._cancel_regel):
            if opzeggen is not None:
                opzeggen()
        self._unwatch_batterij = self._cancel_regel = None
        self._batterij_meters = namen
        if namen:
            self._unwatch_batterij = async_track_state_change_event(
                self.hass, sorted(namen), self._async_meter_gemeld
            )
            self._cancel_regel = async_track_time_interval(
                self.hass, self._async_regel_tik, REGEL_TIK
            )

    @staticmethod
    def _richting_keuze(opties: list[str], laden: bool) -> str | None:
        """Welke keuze van de richting-entiteit laden of ontladen betekent."""
        ontladen = [o for o in opties if "dis" in o.lower() or "ontl" in o.lower()]
        rest = [o for o in opties if o not in ontladen]
        gekozen = rest if laden else ontladen
        return gekozen[0] if gekozen else None

    async def _async_batterij_zetten(self, device: dict[str, Any], watt: float) -> bool:
        """Een vermogen naar de batterij, laden positief. False als het niet kon.

        Met een richting-entiteit ernaast gaat het getal er zonder teken in;
        zonder is het teken de richting. Eerst de richting en dan het getal, en
        de richting alleen als hij verandert.

        Een onbereikbare knop krijgt niets: Home Assistant slaat zo'n dienst
        zonder fout over, en wie dan denkt dat de opdracht staat, stuurt een
        batterij die nog op iets anders loopt. Wat de coach daarmee doet staat
        bij `nul_open` in `_async_regel`.
        """
        entities = device.get("entities") or {}
        knop, richting = entities.get("setpoint"), entities.get("direction")
        if not knop or self._knop_weg(device):
            return False
        eigen = device.get("battery") or {}
        if richting:
            staat = self.hass.states.get(richting)
            opties = list((getattr(staat, "attributes", None) or {}).get("options") or [])
            keuze = self._richting_keuze(opties, watt >= 0)
            if watt != 0 and keuze and (staat is None or staat.state != keuze):
                await self.hass.services.async_call(
                    "select", "select_option", {"entity_id": richting, "option": keuze}, blocking=True
                )
            waarde = abs(watt)
        else:
            waarde = -watt if eigen.get("setpoint_invert") else watt
        # Binnen het bereik dat de knop nu toelaat (v0.157.0). Een Anker Solix maakt zijn `max`
        # kleiner als hij bijna vol is: in een klantwoning op 25-10-2026 om 14:55, op 99%, van
        # 10000 naar 1428 W, en de 2376 W van de regelaar gaf een ServiceValidationError in plaats
        # van een batterij die laadt wat hij nog kan. Zonder `min` of `max` blijft het getal zoals het was.
        attrs = getattr(self.hass.states.get(knop), "attributes", None) or {}
        for grens, kies in (("max", min), ("min", max)):
            try:
                if attrs.get(grens) is not None:
                    waarde = kies(waarde, float(attrs[grens]))
            except (TypeError, ValueError):
                continue
        await self.hass.services.async_call(
            "number", "set_value", {"entity_id": knop, "value": round(waarde)}, blocking=True
        )
        return True

    async def _async_laadgrens_omhoog(
        self, settings: dict[str, Any], device: dict[str, Any], huidig: float
    ) -> bool:
        """De laadgrens van de batterij op honderd, en onthouden wat er stond."""
        entity = (device.get("entities") or {}).get("charge_limit")
        staat = self.hass.states.get(entity) if entity else None
        if staat is None:
            return False
        try:
            top = float((staat.attributes or {}).get("max", 100.0))
        except (TypeError, ValueError):
            top = 100.0
        if huidig >= top:
            return False
        await self.hass.services.async_call(
            "number", "set_value", {"entity_id": entity, "value": top}, blocking=True
        )
        await self._async_batterij_bewaren(settings, device.get("id", ""), {"limit_restore": huidig})
        _LOGGER.info("%s: laadgrens voor de volle beurt van %s naar %s", device.get("id"), huidig, top)
        return True

    async def _async_laadgrens_terug(self, settings: dict[str, Any], device: dict[str, Any]) -> None:
        """De laadgrens terug op wat er stond voor de volle beurt, als die er staat."""
        device_id = device.get("id", "")
        rij = self._batterij_rij(settings, device_id)
        terug = rij.get("limit_restore")
        if terug is None:
            return
        entity = (device.get("entities") or {}).get("charge_limit")
        if entity:
            await self.hass.services.async_call(
                "number", "set_value", {"entity_id": entity, "value": float(terug)}, blocking=True
            )
            _LOGGER.info("%s: laadgrens terug op %s", device_id, terug)
        await self._async_batterij_bewaren(settings, device_id, {"limit_restore": None})

    async def _async_batterij_modus(self, device: dict[str, Any], welke: str) -> None:
        """De modus van de batterij op "de coach stuurt", of terug op zijn eigen stand."""
        entity = (device.get("entities") or {}).get("mode")
        keuze = ((device.get("battery") or {}).get(welke) or "").strip()
        if not entity or not keuze:
            return
        staat = self.hass.states.get(entity)
        if staat is not None and staat.state == keuze:
            return
        await self.hass.services.async_call(
            "select", "select_option", {"entity_id": entity, "option": keuze}, blocking=True
        )

    async def _async_growatt_soort(self, device: dict[str, Any], now: datetime) -> str | None:
        """Of de coach deze Growatt een laadschema kan geven (v0.150.0): "sph", "min" of None.

        Niet uit een naam of een model, want dat geeft de integratie niet: de coach
        vraagt het schema op. Geeft de omvormer zijn laadvakken terug, dan is het een
        SPH op het API-token en kan hij gestuurd worden. Een MIN heeft tijdsegmenten
        (`read_time_segments`); die stuurt de coach (nog) niet. Een MIX of de
        klassieke inlog heeft geen van beide acties: dan leest hij hem uit zoals
        sinds v0.123.0, en vraagt hij het een uur later opnieuw.

        Alleen een echt antwoord onthoudt hij een uur (v0.162.0). In een klantwoning op
        26-10-2026 vroeg hij het na een herstart van Home Assistant om 12:51:22, terwijl de
        accustand van de Growatt pas om 12:51:42 terugkwam; een uur lang stond de batterij
        daarna buiten de coach, zonder besluit en met een lege kaart. De eigenaar: "zodra de
        batterij weer communicatie heeft moet ie niet dat uur afwachten." Dus: zonder
        accustand elke ronde opnieuw, en gaf het lezen geen antwoord, na `GROWATT_NOG_NIET`.
        """
        device_id = device.get("id", "")
        info = self._growatt.setdefault(device_id, {})
        if info.get("soort") == "sph" or (
            info.get("gevraagd") is not None and now - info["gevraagd"] < info.get("over", GROWATT_OPNIEUW)
        ):
            return info.get("soort")
        info["soort"] = None
        if not self._growatt_klaar(device):
            self._growatt_wacht_op(device, info, now)
            return None
        info["gevraagd"] = now
        info["over"] = GROWATT_OPNIEUW
        diensten = self.hass.services
        heeft = getattr(diensten, "has_service", None)
        if heeft is None or not heeft(GROWATT_DOMEIN, "read_ac_charge_times"):
            if heeft is not None and heeft(GROWATT_DOMEIN, "read_time_segments"):
                info["soort"] = "min"
            self._growatt_klaar_met_wachten(info)
            return info["soort"]
        apparaat = self._growatt_apparaat(device)
        if apparaat is None:
            info["over"] = GROWATT_NOG_NIET
            self._growatt_wacht_op(device, info, now)
            return None
        info["apparaat"] = apparaat
        antwoord = await self._async_growatt_lees(device)
        if antwoord is None:
            # Geen antwoord is geen nee: de cloud of de integratie is er nog niet.
            info["over"] = GROWATT_NOG_NIET
            self._growatt_wacht_op(device, info, now)
            return None
        self._growatt_klaar_met_wachten(info)
        if isinstance(antwoord.get("periods"), list):
            info["soort"] = "sph"
            _LOGGER.info("%s: een Growatt met laadvakken; de coach kan hem sturen", device_id)
        elif heeft(GROWATT_DOMEIN, "read_time_segments"):
            info["soort"] = "min"
        return info["soort"]

    def _growatt_klaar(self, device: dict[str, Any]) -> bool:
        """Of de Growatt-integratie er is: de accustand heeft een waarde (v0.162.0)."""
        entity_id = (device.get("entities") or {}).get("soc")
        if not entity_id:
            return True
        staat = self.hass.states.get(entity_id)
        return staat is not None and staat.state not in ("unavailable", "unknown", "")

    def _growatt_wacht_op(self, device: dict[str, Any], info: dict[str, Any], now: datetime) -> None:
        """Hoe lang de coach al op de Growatt wacht; na `GROWATT_WACHT_MELDEN` één keer in het log."""
        sinds = info.setdefault("wacht_sinds", now)
        if not info.get("wacht_gemeld") and now - sinds >= GROWATT_WACHT_MELDEN:
            info["wacht_gemeld"] = True
            _LOGGER.warning(
                "%s: de Growatt-integratie geeft sinds %s geen antwoord; de coach stuurt de batterij nog niet",
                device.get("name") or device.get("id"), sinds.strftime("%H:%M"),
            )

    @staticmethod
    def _growatt_klaar_met_wachten(info: dict[str, Any]) -> None:
        info.pop("wacht_sinds", None)
        info.pop("wacht_gemeld", None)

    def _growatt_apparaat(self, device: dict[str, Any]) -> str | None:
        """Het apparaat in Home Assistant waar de acties van de Growatt-integratie op werken.

        Dat van de accustand, want die hangt aan de omvormer en niet aan het apparaat
        met de totalen.
        """
        entities = device.get("entities") or {}
        for sleutel in ("soc", "charge_power", "discharge_power", "accu_in"):
            entity_id = entities.get(sleutel)
            if not entity_id:
                continue
            try:
                from homeassistant.helpers import entity_registry as er

                rij = er.async_get(self.hass).async_get(entity_id)
            except Exception:  # noqa: BLE001 - zonder register geen apparaat
                return None
            if rij is not None and getattr(rij, "device_id", None):
                return rij.device_id
        return None

    async def _async_growatt_lees(self, device: dict[str, Any]) -> dict[str, Any] | None:
        """Het laadschema zoals de Growatt het teruggeeft, of None."""
        apparaat = self._growatt.get(device.get("id", ""), {}).get("apparaat")
        if not apparaat:
            return None
        try:
            async with asyncio.timeout(GROWATT_WACHT.total_seconds()):
                antwoord = await self.hass.services.async_call(
                    GROWATT_DOMEIN, "read_ac_charge_times", {"device_id": apparaat},
                    blocking=True, return_response=True,
                )
        except Exception as err:  # noqa: BLE001 - de cloud zegt soms niets
            _LOGGER.info("%s: het laadschema lezen lukte niet: %s", device.get("id"), err)
            return None
        return antwoord if isinstance(antwoord, dict) else None

    async def _async_growatt_schrijf(self, device: dict[str, Any], schema: GrowattSchema) -> bool:
        """Het laadschema naar de Growatt. Of de cloud het aannam; of het er ook staat zegt het teruglezen."""
        apparaat = self._growatt.get(device.get("id", ""), {}).get("apparaat")
        if not apparaat:
            return False
        try:
            async with asyncio.timeout(GROWATT_WACHT.total_seconds()):
                await self.hass.services.async_call(
                    GROWATT_DOMEIN, "write_ac_charge_times", {"device_id": apparaat, **schema.velden()},
                    blocking=True,
                )
        except Exception as err:  # noqa: BLE001 - een tweede opdracht vlak na de eerste faalt
            _LOGGER.warning("%s: het laadschema schrijven lukte niet: %s", device.get("id"), err)
            return False
        return True

    def _growatt_batterij(self, b: Batterij, device: dict[str, Any], rij: dict[str, Any]) -> None:
        """Wat een Growatt anders maakt dan een batterij met een stuurgetal (v0.150.0).

        Hij doet zelf nul op de meter, en de coach laat hem alleen van het net laden;
        naar het net ontladen kan met een schema niet op een prijs. De inhoud en het
        laadvermogen leert de coach zelf (`growatt_inhoud`, `growatt_max_w`); tot dan
        geldt wat de installateur invulde. Een meting gaat voor een opgave, net als bij
        het rendement.
        """
        b.zelf_nul = True
        b.handelen = False
        # In een vak met de stopgrens op de accustand staat hij stil (v0.155.0).
        b.kan_vasthouden = True
        b.vol_vasthouden = False
        inhoud = growatt_inhoud(rij.get("growatt_kwh_pct"))
        if inhoud is not None:
            b.capacity_kwh = inhoud
        max_w = growatt_max_w(rij.get("growatt_w_pct"))
        if max_w is not None:
            b.max_charge_w = max_w
        elif not b.max_charge_w:
            # Zonder opgave en zonder meting bij een schema: het hoogste dat de coach hem
            # ooit zag laden. Een ondergrens: het schema laadt daardoor eerder te snel dan
            # te langzaam, en op de stopgrens zet de coach het zelf uit.
            try:
                b.max_charge_w = float(rij.get("growatt_in_w") or 0.0)
            except (TypeError, ValueError):
                b.max_charge_w = 0.0
        # De vloer van de Growatt zelf staat in geen entiteit; de coach ziet hem waar de
        # batterij stopt met ontladen terwijl het huis van het net haalt.
        try:
            vloer = float(rij["growatt_vloer"]) if rij.get("growatt_vloer") is not None else None
        except (TypeError, ValueError):
            vloer = None
        if vloer is not None and vloer > b.soc_min:
            b.soc_min = vloer
        # Wat hij eruit kan: ingevuld, of het hoogste dat de coach hem zag doen. Dat is
        # een ondergrens en geen aanname; zonder beide kan de som niet ontladen.
        if not b.max_discharge_w:
            try:
                b.max_discharge_w = float(rij.get("growatt_uit_w") or 0.0)
            except (TypeError, ValueError):
                b.max_discharge_w = 0.0

    async def _async_growatt(
        self, now: datetime, settings: dict[str, Any], device: dict[str, Any], b: Batterij,
        besluit: Besluit, stuurt: bool, sessie: dict[str, Any],
    ) -> None:
        """Het plan van de batterij als laadschema in de Growatt (v0.150.0).

        Elke ronde rekent de coach het schema uit het plan (`growatt_schema`), en
        schrijft hij het alleen als het genoeg verschilt van wat er staat, nooit twee
        keer binnen `GROWATT_PAUZE` (een tweede opdracht vlak na de eerste faalt), en
        leest hij na `GROWATT_TERUG` terug. Zit de batterij waar het schema hem laat
        stoppen, dan zet hij het schema zelf uit: het teruglezen van die grens is niet
        te vertrouwen. Na het laatste vak gaat het schema uit, want het herhaalt zich
        elke dag. Zonder het vinkje schrijft hij niets en zegt hij wat hij zou doen.
        """
        device_id = device.get("id", "")
        naam = device.get("name") or t("De batterij")
        rij = self._batterij_rij(settings, device_id)
        await self._async_growatt_leren(now, settings, device, b, sessie, rij)
        # Een eigen vlag en niet "stuurt": daar hangt de regelaar aan, en die heeft een
        # Growatt niet.
        sessie["growatt_stuurt"] = stuurt

        if stuurt:
            # Het kasboek, zoals bij een batterij met een regelaar, maar eens per ronde.
            self._kasboek(sessie, settings, device_id, now, self._net_nu(settings)[0], self._batterij_w(device), b)
            await self._async_growatt_nacht(now, settings, device, b, sessie, besluit.uren)
            rij = self._batterij_rij(settings, device_id)
        bijstel = growatt_bijstelling(growatt_nachten(rij), b.capacity_kwh)
        geschreven: GrowattSchema | None = sessie.get("growatt_geschreven")
        loopt = bool(stuurt and geschreven is not None and geschreven.net and not geschreven.houden
                     and self._growatt_in_vak(geschreven, now))
        mis = sessie.get("growatt_houden_mis")
        if mis is not None and now >= mis:
            sessie.pop("growatt_houden_mis", None)
            mis = None
        wil = growatt_schema(besluit.uren, now, b, bijstel, loopt=loopt, vasthouden=mis is None,
                             min_pct=self._growatt_min_pct(rij))
        if not b.max_charge_w:
            self.state[device_id]["tip"] = t(
                "De coach weet nog niet hoe snel deze Growatt laadt, dus hij laadt hem niet van het net. Vul "
                "bij de batterij het hoogste laadvermogen in, of wacht tot de coach hem een keer op zon ziet laden."
            )
        elif not b.max_discharge_w:
            self.state[device_id]["tip"] = t(
                "De coach weet nog niet hoeveel deze Growatt kan leveren, dus hij laadt hem niet van het net. "
                "Vul bij de batterij het hoogste ontlaadvermogen in, of wacht tot de coach hem een keer ziet ontladen."
            )
        if geschreven is not None and growatt_vol(geschreven, b.soc, b.soc_max, now):
            # Op de stopgrens: uit, en in dit stuk niet opnieuw.
            sessie["growatt_vol_tot"] = geschreven.tot
        vol_tot = sessie.get("growatt_vol_tot")
        if vol_tot is not None and now >= vol_tot:
            sessie.pop("growatt_vol_tot", None)
            vol_tot = None
        elif vol_tot is not None and not wil.houden:
            # Op de stopgrens uit, behalve als het plan hem daarna vasthoudt (v0.155.0): dan
            # zou hij anders het huis voeden in de goedkope uren.
            wil = GrowattSchema()
        elif (
            wil.houden and geschreven is not None and geschreven.net and not geschreven.houden
            and wil.tot == geschreven.tot and self._growatt_in_vak(geschreven, now)
            and (vol_tot is not None or (geschreven.stop_soc - wil.stop_soc) / 100.0 * (b.capacity_kwh or 0.0)
                 < GROWATT_HOUDEN_KWH)
        ):
            # Van laden naar vasthouden in hetzelfde vak, voor minder dan `GROWATT_HOUDEN_KWH`, of
            # terwijl hij al op de stopgrens stilstaat: een opdracht voor niets (v0.156.0). In de
            # klantwoning wilde de coach op 24-10-2026 om 07:45 nog "vasthouden op 32%" schrijven
            # in plaats van laden tot 35%, voor het laatste kwartier; de cloud weigerde dat drie keer.
            wil = geschreven
        elif (
            geschreven is not None and geschreven.houden and wil.net and not wil.houden
            and wil.tot == geschreven.tot and self._growatt_in_vak(geschreven, now)
            and (wil.stop_soc - geschreven.stop_soc) / 100.0 * (b.capacity_kwh or 0.0) < GROWATT_HOUDEN_KWH
        ):
            # En andersom: van vasthouden naar laden in hetzelfde vak voor minder dan een halve kWh
            # (v0.156.1). In het virtuele huis (`growatt-vasthouden`) schreef hij om 08:57 nog laden
            # tot 81% voor de laatste drie minuten, op 100%, en ging de zekering eroverheen.
            wil = geschreven
        # Na het vak het schema eruit, ook als de stopgrens niet gehaald is (v0.174.0): het
        # herhaalt zich elke dag. Tot dan zag `_growatt_wacht` het voorbije vak als het
        # volgende, ruim twintig uur weg, en liet hij het staan. In de klantwoning stond het
        # op 28-10-2026 na een vak dat op 98 eindigde bij stop 100 nog bijna twee uur in de
        # Growatt, en ging het er alleen uit door een toevallige sprong bij het teruglezen;
        # was de coach daarna weggevallen, dan laadde hij de volgende ochtend vol van het net.
        verlopen = bool(
            stuurt and geschreven is not None and geschreven.net and geschreven.tot is not None
            and now >= geschreven.tot and not self._growatt_in_vak(geschreven, now)
        )
        if verlopen and not (wil.net and (self._growatt_in_vak(wil, now)
                                          or self._growatt_begint(wil, now) <= GROWATT_VOORAF)):
            wil = GrowattSchema()
        # Aan of uit pas na `GROWATT_BESTENDIG`: het plan twijfelde in het virtuele huis
        # (`growatt-zon`) een ochtend lang of er vannacht nog 1 kWh bij moest, en dan ging
        # het schema om de paar minuten aan en uit. De stopgrens wacht niet.
        if geschreven is not None and wil.net != geschreven.net and vol_tot is None:
            sinds = sessie.get("growatt_wissel")
            if sinds is None or sinds[0] != wil.net:
                sessie["growatt_wissel"] = (wil.net, now)
            if now - sessie["growatt_wissel"][1] < GROWATT_BESTENDIG:
                wil = geschreven
        else:
            sessie.pop("growatt_wissel", None)
        sessie["growatt_wil"] = wil
        # Op de kaart: in een lopend vak wat er in de Growatt staat, zoals de reden (v0.156.0);
        # daarbuiten wat de coach erin gaat zetten.
        toon = geschreven if (stuurt and geschreven is not None and geschreven.net
                              and self._growatt_in_vak(geschreven, now)) else wil
        self.state[device_id]["schedule"] = {
            "grid": toon.net, "hold": toon.houden, "power_pct": toon.vermogen_pct if toon.net else None,
            "stop_soc": toon.stop_soc if toon.net else None, "periods": [list(v) for v in toon.vakken],
            "kwh": round(toon.kwh, 2), "written": None if geschreven is None else geschreven.net,
            "confirmed": sessie.get("growatt_bevestigd") is not None,
        }

        if not stuurt:
            # De schaduw: zeggen wat hij zou schrijven, op dezelfde momenten als hij het zou
            # schrijven. Alleen andere vakken of aan en uit: in de schaduw laadt er niets, dus
            # het vermogen loopt 's nachts elk uur op, en dat zegt niets over het schema.
            schaduw = sessie.get("growatt_schaduw")
            if schaduw is None or (not self._growatt_wacht(wil, schaduw, now)
                                   and wil.wijkt_af(schaduw, alleen_vakken=True, zakken=False)):
                sessie["growatt_schaduw"] = wil
                await self._async_noteer(
                    t("{naam}: zou dit schrijven, maar de coach stuurt nu niet: {schema}",
                      naam=naam, schema=self._growatt_zin(wil)), now,
                    {"device": device_id, "mode": besluit.stand, "rule": "growatt-schaduw", "applied": False},
                )
            # Stond er van de coach nog laden van het net in, dan dat er meteen uit.
            if geschreven is not None and geschreven.net:
                wil = GrowattSchema()
            else:
                return

        laatst = sessie.get("growatt_op")
        if geschreven is None or (not stuurt and wil.wijkt_af(geschreven)) or (verlopen and not wil.net) or (
            not self._growatt_wacht(wil, geschreven, now)
            and wil.wijkt_af(geschreven, alleen_vakken=self._growatt_vroeg(wil, geschreven, now))
        ):
            if laatst is not None and now - laatst < GROWATT_PAUZE:
                return
            sessie["growatt_op"] = now
            if await self._async_growatt_schrijf(device, wil):
                sessie["growatt_geschreven"] = wil
                sessie["growatt_bevestigd"] = None
                sessie["growatt_terug_om"] = now + GROWATT_TERUG
                if stuurt or wil.net:
                    await self._async_noteer(f"{naam}: {self._growatt_zin(wil)}", now, {
                        "device": device_id, "mode": besluit.stand, "rule": "growatt-schema", "applied": True,
                    })
            else:
                await self._async_growatt_fout(now, device, sessie, wil, staat=geschreven)
            return

        terug_om = sessie.get("growatt_terug_om")
        if terug_om is not None and now >= terug_om and geschreven is not None:
            sessie["growatt_terug_om"] = None
            gelezen = await self._async_growatt_lees(device)
            if gelezen is None and sessie.get("growatt_bevestigd") is not None:
                # Geen antwoord bij een controle van een schema dat er al stond: later nog eens.
                sessie["growatt_terug_om"] = now + GROWATT_TERUG
                return
            if geschreven.gelijk(gelezen):
                sessie["growatt_bevestigd"] = now
                sessie["growatt_fouten"] = 0
                aangenomen = self._growatt_pct(rij, "growatt_pct_aangenomen")
                if geschreven.net and (aangenomen is None or geschreven.vermogen_pct < aangenomen):
                    # Wat er één keer stond neemt hij aan (v0.165.1).
                    await self._async_batterij_bewaren(
                        settings, device_id, {"growatt_pct_aangenomen": geschreven.vermogen_pct})
                if geschreven.net:
                    # Zolang het van het net laadt blijft hij het nakijken.
                    sessie["growatt_terug_om"] = now + GROWATT_CONTROLE
                self.state[device_id]["schedule"]["confirmed"] = True
                if sessie.pop("growatt_gemeld", False):
                    await self._async_tell(t("{naam} neemt het laadschema weer aan.", naam=naam), telefoon=False)
            else:
                if self._growatt_vermogen_geweigerd(geschreven, gelezen):
                    # Alles staat er, behalve het vermogen. Geweigerd is alleen een getal dat er bij het
                    # eerste teruglezen al niet stond, en dat lager is dan wat hij ooit aannam (v0.165.1).
                    # In de klantwoning gaf de Growatt in de nacht van 26 op 27-10-2026 na zijn eigen ronde
                    # telkens 100 terug, ook voor een 48 die drie uur lang wel terugkwam; v0.163.0 telde dat
                    # elke keer als geweigerd en klom in één nacht van 48 naar 100%.
                    sleutel = (geschreven.vermogen_pct, tuple(tuple(v) for v in geschreven.vakken), geschreven.stop_soc)
                    aangenomen = self._growatt_pct(rij, "growatt_pct_aangenomen")
                    if (sessie.get("growatt_bevestigd") is None and sessie.get("growatt_sprong") != sleutel
                            and (aangenomen is None or geschreven.vermogen_pct < aangenomen)):
                        _LOGGER.warning("%s: het laadschema staat er niet zoals geschreven: %s", device_id, gelezen)
                        oud = self._growatt_pct(rij, "growatt_weigert_pct") or 0
                        if geschreven.vermogen_pct > oud:
                            await self._async_batterij_bewaren(
                                settings, device_id, {"growatt_weigert_pct": geschreven.vermogen_pct})
                            _LOGGER.warning(
                                "%s: de Growatt neemt %s%% laadvermogen niet aan; de coach schrijft voortaan minstens %s%%",
                                device_id, geschreven.vermogen_pct,
                                self._growatt_min_pct({"growatt_weigert_pct": geschreven.vermogen_pct}),
                            )
                    elif sessie.get("growatt_sprong") == sleutel:
                        # Al een keer opnieuw geschreven, en weer anders teruggelezen: dan laat hij het zo.
                        # De stopgrens begrenst wat erin gaat, en die staat er wel.
                        _LOGGER.info("%s: de Growatt geeft %s%% laadvermogen terug, geschreven %s%%; zo gelaten",
                                     device_id, gelezen.get("charge_power"), geschreven.vermogen_pct)
                        sessie["growatt_bevestigd"] = now
                        sessie["growatt_fouten"] = 0
                        sessie["growatt_terug_om"] = now + GROWATT_CONTROLE
                        self.state[device_id]["schedule"]["confirmed"] = True
                        return
                    else:
                        # Het stond er al eens: één keer opnieuw schrijven, zonder melding.
                        _LOGGER.warning("%s: de Growatt geeft %s%% laadvermogen terug, geschreven %s%%; nog één keer",
                                        device_id, gelezen.get("charge_power"), geschreven.vermogen_pct)
                        sessie["growatt_sprong"] = sleutel
                        sessie["growatt_geschreven"] = None
                        return
                else:
                    _LOGGER.warning("%s: het laadschema staat er niet zoals geschreven: %s", device_id, gelezen)
                # Opnieuw schrijven na de pauze.
                sessie["growatt_geschreven"] = None
                await self._async_growatt_fout(now, device, sessie, geschreven)

    @staticmethod
    def _growatt_pct(rij: dict[str, Any], sleutel: str) -> int | None:
        try:
            waarde = rij.get(sleutel)
            return None if waarde is None else int(waarde)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _growatt_min_pct(cls, rij: dict[str, Any]) -> int:
        """Het laagste laadvermogen dat deze Growatt aanneemt, in procent (v0.163.0).

        `GROWATT_MIN_PCT`, of het volgende tiental boven het hoogste dat hij ooit weigerde: wat hij
        wel aanneemt weet de coach niet, en met een procent tegelijk schreef hij in het virtuele huis
        (`growatt-weigert`) achttien keer voordat hij er was. Nooit boven een getal dat er wel eens
        stond (`growatt_pct_aangenomen`, v0.165.1). `growatt_pct_geweigerd` van v0.163.x telt niet
        meer: dat klom mee met een Growatt die 100 teruggaf voor een getal dat er wel stond.
        """
        geweigerd = cls._growatt_pct(rij, "growatt_weigert_pct") or 0
        grens = max(GROWATT_MIN_PCT, (geweigerd // 10 + 1) * 10)
        aangenomen = cls._growatt_pct(rij, "growatt_pct_aangenomen")
        if aangenomen is not None:
            grens = min(grens, max(GROWATT_MIN_PCT, aangenomen))
        return min(100, grens)

    @staticmethod
    def _growatt_vermogen_geweigerd(geschreven: GrowattSchema, gelezen: dict[str, Any] | None) -> bool:
        """Of het teruggelezen schema alleen in het vermogen afwijkt van wat de coach schreef."""
        if not isinstance(gelezen, dict) or not geschreven.net:
            return False
        try:
            vermogen = int(gelezen.get("charge_power"))
        except (TypeError, ValueError):
            return False
        return vermogen != geschreven.vermogen_pct and replace(geschreven, vermogen_pct=vermogen).gelijk(gelezen)

    async def _async_growatt_fout(
        self, now: datetime, device: dict[str, Any], sessie: dict[str, Any], wil: GrowattSchema,
        staat: GrowattSchema | None = None,
    ) -> None:
        """Een schema dat er niet in kwam: na `GROWATT_FOUTEN` keer één melding.

        `staat` is wat er volgens de coach nog in de Growatt staat, of None als dat niet zeker
        is. Laadt dat net zo goed of net zo min van het net als wat hij wilde schrijven, dan is
        er voor de bewoner niets aan de hand en gaat het alleen in de geschiedenis (v0.156.0).
        In de klantwoning op 24-10-2026 weigerde de cloud om 07:45-07:55 drie keer het
        vasthouden voor het laatste kwartier van vazio; de telefoon kreeg "hij laadt vannacht niet
        van het net", terwijl hij al tot zijn stopgrens geladen had.
        """
        sessie["growatt_fouten"] = int(sessie.get("growatt_fouten") or 0) + 1
        if wil.houden and sessie["growatt_fouten"] >= GROWATT_FOUTEN:
            # Vasthouden dat de Growatt niet aanneemt: voor dit goedkope stuk laat de coach het weg,
            # en schrijft hij het schema zonder (v0.156.0). In de klantwoning weigerde de cloud op
            # 24-10-2026 elk vasthouden (om 07:45 en om 21:31), en bleef het schema van die ochtend
            # staan terwijl de coach het om de vijf minuten opnieuw probeerde.
            sessie["growatt_houden_mis"] = wil.tot or now + timedelta(hours=12)
            sessie["growatt_fouten"] = 0
            naam = device.get("name") or t("De batterij")
            _LOGGER.warning("%s: vasthouden niet aangenomen; tot %s zonder", device.get("id"), wil.tot)
            await self._async_tell(
                t("{naam} neemt vasthouden niet aan; de coach laat dat voor deze goedkope uren weg.", naam=naam),
                telefoon=False,
            )
            return
        if sessie["growatt_fouten"] >= GROWATT_FOUTEN and not sessie.get("growatt_gemeld"):
            sessie["growatt_gemeld"] = True
            naam = device.get("name") or t("De batterij")
            if staat is not None and staat.net == wil.net:
                await self._async_tell(
                    t("{naam} neemt het nieuwe laadschema van de coach niet aan; het vorige blijft staan. "
                      "De coach probeert het opnieuw.", naam=naam),
                    telefoon=False,
                )
                return
            await self._async_tell(
                t(
                    "{naam} neemt het laadschema van de coach niet aan. Kijk in de Growatt-app of laden "
                    "van het net nu aan staat.", naam=naam,
                ) if not wil.net else t(
                    "{naam} neemt het laadschema van de coach niet aan; hij laadt niet van het net zoals gepland.",
                    naam=naam,
                ),
                kritiek=not wil.net,
            )

    @staticmethod
    def _growatt_zin(schema: GrowattSchema) -> str:
        """Het schema in woorden, voor het logboek."""
        if not schema.net:
            return t("geen laden van het net; hij doet zelf nul op de meter.")
        if schema.houden:
            return t(
                "vasthouden {vakken}, op {soc}%: niet laden en niet ontladen, het huis van het net.",
                vakken=", ".join(f"{a}-{b}" for a, b in schema.vakken), soc=schema.stop_soc,
            )
        vakken = ", ".join(f"{a}-{b}" for a, b in schema.vakken)
        return t(
            "laden van het net {vakken}, op {pct}% van zijn vermogen, tot {soc}% ({kwh} kWh).",
            vakken=vakken, pct=schema.vermogen_pct, soc=schema.stop_soc, kwh=getal(schema.kwh, 1),
        )

    async def _async_growatt_leren(
        self, now: datetime, settings: dict[str, Any], device: dict[str, Any], b: Batterij,
        sessie: dict[str, Any], rij: dict[str, Any],
    ) -> None:
        """De inhoud en het laadvermogen van een Growatt zelf leren (v0.150.0).

        De inhoud: een stuk alleen laden van minstens `GROWATT_STUK_PCT` procent, en
        hoeveel de eigen teller "geladen" daarbij per procent opliep. Loopt de teller
        "ontladen" ertussen op, of zakt de accustand, dan begint het stuk opnieuw.

        Het laadvermogen: in een vak van het net dat de coach schreef en dat de Growatt
        teruggaf, zonder zon, wat hij laadt gedeeld door het deel dat in het schema
        staat. Eén meting per verse waarde van de sensor, want die komt eens per vijf
        minuten.
        """
        entities = device.get("entities") or {}
        device_id = device.get("id", "")
        nieuw: dict[str, Any] = {}
        soc = b.soc
        erin = _kwh(self.hass, entities.get("accu_in"))
        eruit = _kwh(self.hass, entities.get("accu_out"))
        stuk = sessie.get("growatt_stuk")
        if soc is None or erin is None or eruit is None:
            sessie["growatt_stuk"] = None
        elif stuk is None or soc < stuk["soc_nu"] or eruit > stuk["uit"] + 0.05:
            sessie["growatt_stuk"] = {"soc": soc, "soc_nu": soc, "in": erin, "uit": eruit}
        else:
            stuk["soc_nu"] = soc
            if soc - stuk["soc"] >= GROWATT_STUK_PCT:
                per_pct = (erin - stuk["in"]) / (soc - stuk["soc"])
                rij_stukken = list(rij.get("growatt_kwh_pct") or [])[-(GROWATT_BEWAAR - 1):]
                nieuw["growatt_kwh_pct"] = [*rij_stukken, round(per_pct, 4)]
                sessie["growatt_stuk"] = {"soc": soc, "soc_nu": soc, "in": erin, "uit": eruit}

        geschreven: GrowattSchema | None = sessie.get("growatt_geschreven")
        laden_w = self._batterij_w(device)
        if laden_w is not None and -laden_w > float(rij.get("growatt_uit_w") or 0.0) + 50.0:
            nieuw["growatt_uit_w"] = round(-laden_w)
        if laden_w is not None and laden_w > float(rij.get("growatt_in_w") or 0.0) + 50.0:
            nieuw["growatt_in_w"] = round(laden_w)
        # Nog nooit zien ontladen, bijvoorbeeld een nieuwe klant die 's avonds leeg begint:
        # dan rekent de som met 0 W eruit en is bijladen niets waard. Wat hij vóór de coach
        # deed staat in de statistiek van Home Assistant; eens per dag kijken (v0.161.0).
        if not nieuw.get("growatt_uit_w") and not float(rij.get("growatt_uit_w") or 0.0) \
                and sessie.get("growatt_uit_gezocht") != now.date():
            sessie["growatt_uit_gezocht"] = now.date()
            hoogste = await self._async_hoogste_ontladen(device, now)
            if hoogste is not None and hoogste > 50.0:
                nieuw["growatt_uit_w"] = round(hoogste)
        # De vloer: stil, en toch haalt het huis van het net. Buiten een vak van het net,
        # want daar staat hij ook stil als hij vol is.
        net_w, _ = self._net_nu(settings)
        if (
            soc is not None and laden_w is not None and abs(laden_w) < GROWATT_STIL_W and net_w is not None
            and net_w > GROWATT_VLOER_NET_W and soc < 50.0
            and not (geschreven is not None and geschreven.net and self._growatt_in_vak(geschreven, now))
            and (rij.get("growatt_vloer") is None or soc < float(rij["growatt_vloer"]) - 0.5)
        ):
            nieuw["growatt_vloer"] = round(soc)
        # Zonder panelen is er geen zon, en dat is iets anders dan een omvormer die zwijgt.
        zon = self._zon_w(settings) if zonsensoren(settings) else 0.0
        staat = self.hass.states.get(entities.get("charge_power")) if entities.get("charge_power") else None
        vers = getattr(staat, "last_updated", None)
        if (
            geschreven is not None and geschreven.net and sessie.get("growatt_bevestigd") is not None
            and self._growatt_in_vak(geschreven, now) and laden_w is not None and laden_w > 0
            and zon is not None and zon < GROWATT_ZON_W and vers is not None
            and vers != sessie.get("growatt_vers") and b.soc is not None and b.soc < geschreven.stop_soc - 1
        ):
            sessie["growatt_vers"] = vers
            metingen = list(rij.get("growatt_w_pct") or [])[-(GROWATT_BEWAAR - 1):]
            nieuw["growatt_w_pct"] = [*metingen, round(laden_w * 100.0 / geschreven.vermogen_pct)]
        if nieuw:
            await self._async_batterij_bewaren(settings, device_id, nieuw)

    async def _async_hoogste_ontladen(self, device: dict[str, Any], now: datetime) -> float | None:
        """Het hoogste dat deze batterij de afgelopen weken ontlaadde, in watt, uit de statistiek (v0.161.0).

        Het maximum per uur van de sensor voor ontladen, of het minimum van een sensor met
        een teken. Een meting, en net als `growatt_uit_w` een ondergrens. None zonder
        sensor, zonder recorder of zonder een uur waarin hij ontlaadde.
        """
        entities = device.get("entities") or {}
        getekend = device.get("entity") or None
        los = entities.get("discharge_power") or None
        if not getekend and not los:
            return None
        zone = dt_util.get_default_time_zone()
        eind = dt_util.as_utc(now if now.tzinfo else now.replace(tzinfo=zone))
        begin = eind - timedelta(days=GROWATT_TERUGKIJK_DAGEN)
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import statistics_during_period

            rijen = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period, self.hass, begin, eind, {e for e in (getekend, los) if e}, "hour",
                {"power": "W"}, {"min", "max"},
            ) or {}
        except Exception as fout:  # noqa: BLE001 - zonder recorder geen geschiedenis
            _LOGGER.debug("kon de statistiek van de batterij niet lezen: %s", fout)
            return None

        def uiterste(entity_id: str | None, soort: str) -> float | None:
            waarden = []
            for r in rijen.get(entity_id) or []:
                try:
                    waarden.append(float(r[soort]))
                except (KeyError, TypeError, ValueError):
                    continue
            if not waarden:
                return None
            return max(waarden) if soort == "max" else min(waarden)

        kandidaten = []
        if los:
            kandidaten.append(uiterste(los, "max"))
        if getekend:
            if (device.get("battery") or {}).get("power_invert"):
                kandidaten.append(uiterste(getekend, "max"))
            else:
                laagste = uiterste(getekend, "min")
                kandidaten.append(-laagste if laagste is not None else None)
        hoogste = max((k for k in kandidaten if k is not None), default=None)
        return hoogste if hoogste is not None and hoogste > 0 else None

    def _growatt_wacht(self, wil: GrowattSchema, staat: GrowattSchema, now: datetime) -> bool:
        """Of de coach een nieuw schema nog even laat liggen (v0.150.0).

        Over het volgende goedkope stuk beslist hij pas `GROWATT_VOORAF` voordat het
        begint: het plan schuift overdag mee met de zon en de prijzen, en wat hij om 09:30
        over de nacht zou schrijven, schreef hij om 13:00 weer anders. De beheersessie in
        de klantwoning: één keer per dag, vóór het goedkope blok. Loopt er een vak, dan
        wacht hij niet.
        """
        vakken = [s for s in (wil, staat) if s.net]
        if not vakken:
            return False
        if any(self._growatt_in_vak(s, now) for s in vakken):
            return False
        return min(self._growatt_begint(s, now) for s in vakken) > GROWATT_VOORAF

    def _growatt_vroeg(self, wil: GrowattSchema, staat: GrowattSchema, now: datetime) -> bool:
        """Of het vak nog niet loopt: dan schrijft hij alleen andere vakken, niet een ander vermogen.

        Het vak dat in de Growatt staat telt, niet het nieuwe: sinds v0.152.0 ligt het vak aan
        het eind van het goedkope stuk, en terwijl hij laadt schuift het begin van het nieuwe
        vak voorbij nu. Met het nieuwe vak hier bleef in het virtuele huis een hogere stopgrens
        liggen, stond hij om 05:20 op 94%, en gaf hij daarna tot 09:00 het huis stroom uit de
        accu in de goedkope uren.
        """
        return bool(wil.net and staat.net and not self._growatt_in_vak(staat, now))

    async def _async_growatt_nacht(
        self, now: datetime, settings: dict[str, Any], device: dict[str, Any], b: Batterij,
        sessie: dict[str, Any], plan_uren: list | None = None,
    ) -> None:
        """Na elke nacht nakijken of het schema te veel of te weinig laadde (v0.151.0).

        Vanaf het eind van een vak dat de coach schreef tot het begin van het volgende telt
        hij twee dingen: zon die naar het net gaat terwijl de batterij vol is (te veel van het
        net geladen), en wat het huis van het net haalt terwijl de batterij op zijn vloer staat
        (te weinig), maar dat laatste alleen in een duurder uur dan het goedkoopste van het
        komende etmaal (`growatt_duur`, v0.156.0). En in het vak zelf wat er van het net in ging. Begint het volgende vak,
        dan gaat de nacht met `growatt_nacht` in `growatt_nachten`, en stelt
        `growatt_bijstelling` het schema daarop bij.

        **De telling staat ook in de opslag** (v0.171.0, `growatt_dag` bij de batterijrij),
        elk kwartier en bij het stoppen. Tot dan stond hij alleen in het geheugen, en wiste
        elke herstart de dag: in de klantwoning op 27-10-2026 zes herstarts, en de 12,9 kWh
        zon die bij een volle accu naar het net ging kwam nooit in `growatt_nachten`. Telde
        de coach op een dag samen langer dan `GROWATT_DAG_GAT` niet (een coach die uit
        stond), dan rekent hij die dag achteraf na uit de kwartieren (v0.174.0,
        `_async_growatt_dag_af`): half geteld is te weinig te veel.

        **Een nacht zonder vak sluit ook af** (v0.179.0), een etmaal na het begin van de dag
        (`GROWATT_DAG`), dus op het moment van het vak van de nacht ervoor. Tot dan sloot de dag
        alleen bij een vak dat de coach schreef; in de klantwoning laadde hij in de nacht van 28
        op 29-10-2026 terecht niet van het net, en liep de dag van 28-10 door in 29-10 en verder.
        Juist zo'n nacht laat zien of het te weinig was: op 29-10 stond de accu van 08:00 tot
        09:45 op zijn vloer en kwam er 2,1 kWh van het net in het dure uur. Een telling in de
        opslag zonder begin zoekt het laatste vak in de kwartieren (`growatt_laatste_nacht`).
        """
        device_id = device.get("id", "")
        geschreven: GrowattSchema | None = sessie.get("growatt_geschreven")
        if "growatt_dag" not in sessie:
            bewaard = self._batterij_rij(settings, device_id).get("growatt_dag")
            dag, vorige = self._growatt_dag_uit(bewaard)
            sessie["growatt_dag"] = dag
            sessie["growatt_dag_op"] = vorige
            # Een telling van een eerdere coach zonder begin: dat zoekt hij één keer op.
            sessie["growatt_begin_zoeken"] = isinstance(bewaard, dict) and dag.get("begon") is None
        dag = sessie["growatt_dag"]
        dag.setdefault("gat", 0.0)
        vorige = sessie.get("growatt_dag_op")
        sessie["growatt_dag_op"] = now
        in_vak = bool(geschreven is not None and geschreven.net and self._growatt_in_vak(geschreven, now))
        vak_begon = None
        if in_vak:
            klok = now.strftime("%H:%M")
            vak_begon = next((now.replace(hour=int(a[:2]), minute=int(a[3:5]), second=0, microsecond=0)
                              for a, e in geschreven.vakken if a <= klok < e), now)
        if dag["in_vak"] is None and vorige is None:
            # De eerste ronde zonder iets in de opslag: wat er voor nu lag zag hij niet. In een vak
            # begint de dag bij het vak, en mist hij wat er sinds het begin ervan van het net kwam.
            if in_vak:
                dag.update(begon=vak_begon, gat=self._growatt_gemist(vak_begon, now))
            else:
                dag.update(begon=now, gat=GROWATT_DAG_GAT.total_seconds() / 3600.0 + 1.0)
        if sessie.pop("growatt_begin_zoeken", False) and dag.get("begon") is None:
            dag["begon"] = await self._async_growatt_begin(settings, device, now)
            if dag["begon"] is None and in_vak and dag["in_vak"]:
                dag["begon"] = vak_begon
        grens = None
        if dag["in_vak"] is False and in_vak:
            # Een nieuw vak: de dag ervoor is klaar, en de volgende begint bij het vak.
            grens = vak_begon
        elif not in_vak and dag.get("begon") is None:
            # Geen begin, en ook niet in de kwartieren: zoals voor v0.179.0, de dag is hier om.
            grens = now
        elif not in_vak and now >= dag["begon"] + GROWATT_DAG:
            # Een etmaal zonder vak: de dag is om op het moment van het vak ervoor.
            dagen = (now - dag["begon"]) // GROWATT_DAG
            grens = dag["begon"] + dagen * GROWATT_DAG
        if grens is not None:
            if vorige is not None:
                # Wat hij na de grens nog bij de oude dag telde hoort er niet bij: zo lang
                # telt als niet geteld, en is dat te veel, dan rekent hij de dag na.
                dag["gat"] += self._growatt_gemist(vorige, grens) + max(
                    0.0, (vorige - grens).total_seconds() / 3600.0)
            await self._async_growatt_dag_af(grens, settings, device, b, dag)
            dag.update(net=0.0, teveel=0.0, tekort=0.0, gat=self._growatt_gemist(grens, now), begon=grens)
            sessie["growatt_dag_bewaard"] = None
        elif vorige is not None:
            dag["gat"] += self._growatt_gemist(vorige, now)
        dag["in_vak"] = in_vak
        bewaard = sessie.get("growatt_dag_bewaard")
        if bewaard is None or _tussen(bewaard, now) >= GROWATT_DAG_BEWAREN:
            sessie["growatt_dag_bewaard"] = now
            await self._async_growatt_dag_bewaren(settings, device_id, sessie)
        net_w, _ = self._net_nu(settings)
        bat_w = self._batterij_w(device)
        if vorige is None or net_w is None or bat_w is None or b.soc is None:
            return
        uren = min(60.0, max(0.0, (now - vorige).total_seconds())) / 3600.0
        if in_vak:
            if bat_w > 0 and net_w > 0:
                dag["net"] += min(bat_w, net_w) / 1000.0 * uren
        else:
            if net_w < 0 and b.soc >= b.soc_max - VOL_MARGE:
                dag["teveel"] += -net_w / 1000.0 * uren
            if (net_w > 0 and b.soc <= b.soc_min + 1.0 and abs(bat_w) < GROWATT_STIL_W
                    and growatt_duur(plan_uren or [], now)):
                dag["tekort"] += net_w / 1000.0 * uren

    @staticmethod
    def _growatt_gemist(van: datetime, tot: datetime) -> float:
        """Hoeveel uur hij tussen twee rondes niet telde: een ronde is een minuut."""
        if tot <= van:
            return 0.0
        gemist = (_tussen(van, tot) - timedelta(minutes=1)).total_seconds() / 3600.0
        return gemist if gemist > 1.0 / 60.0 else 0.0

    async def _async_growatt_begin(
        self, settings: dict[str, Any], device: dict[str, Any], now: datetime
    ) -> datetime | None:
        """Waar de dag in de opslag begon, uit het laatste vak in de kwartieren (v0.179.0)."""
        try:
            kwartieren, _ = await self._async_growatt_kwartieren(
                settings, device, now - GROWATT_NAREKENEN_MAX, now, accustand=False)
        except Exception:  # noqa: BLE001 - zoeken mag de ronde niet kosten
            _LOGGER.exception("%s: kon het laatste vak niet zoeken", device.get("id", ""))
            return None
        begon = growatt_laatste_nacht(kwartieren or [], GROWATT_STIL_W)
        _LOGGER.info("%s: de telling van de nacht had geen begin; het laatste vak begon %s",
                     device.get("id", ""), begon.isoformat() if begon else "niet in de kwartieren")
        return begon

    @staticmethod
    def _growatt_begint(schema: GrowattSchema, now: datetime) -> timedelta:
        """Hoe lang het nog duurt tot het eerste vak begint, op de klok."""
        klok = now.hour * 60 + now.minute
        minuten = []
        for begin, _ in schema.vakken:
            uur, minuut = (int(x) for x in begin.split(":"))
            minuten.append((uur * 60 + minuut - klok) % (24 * 60))
        return timedelta(minutes=min(minuten)) if minuten else timedelta(0)

    @staticmethod
    def _growatt_in_vak(schema: GrowattSchema, now: datetime) -> bool:
        klok = now.strftime("%H:%M")
        return any(begin <= klok < eind for begin, eind in schema.vakken)

    @staticmethod
    def _growatt_dag_uit(bewaard: Any) -> tuple[dict[str, Any], datetime | None]:
        """De telling van de dag uit de opslag, en wanneer hij voor het laatst telde (v0.171.0)."""
        dag: dict[str, Any] = {"net": 0.0, "teveel": 0.0, "tekort": 0.0, "in_vak": None, "gat": 0.0}
        if not isinstance(bewaard, dict):
            return dag, None
        for sleutel in ("net", "teveel", "tekort", "gat"):
            try:
                dag[sleutel] = max(0.0, float(bewaard.get(sleutel) or 0.0))
            except (TypeError, ValueError):
                pass
        if isinstance(bewaard.get("in_vak"), bool):
            dag["in_vak"] = bewaard["in_vak"]
        try:
            op = _moment(datetime.fromisoformat(str(bewaard.get("op"))))
        except (TypeError, ValueError):
            op = None
        try:
            dag["begon"] = _moment(datetime.fromisoformat(str(bewaard.get("begon"))))
        except (TypeError, ValueError):
            pass
        return dag, op

    async def _async_growatt_dag_bewaren(
        self, settings: dict[str, Any], device_id: str, sessie: dict[str, Any]
    ) -> None:
        """De telling van de dag naar de batterijrij, met het moment in UTC (v0.171.0)."""
        dag = sessie.get("growatt_dag")
        op = sessie.get("growatt_dag_op")
        if not isinstance(dag, dict) or op is None:
            return
        await self._async_batterij_bewaren(settings, device_id, {"growatt_dag": {
            "net": round(dag["net"], 4), "teveel": round(dag["teveel"], 4),
            "tekort": round(dag["tekort"], 4), "gat": round(dag.get("gat", 0.0), 4),
            "in_vak": dag["in_vak"], "op": dt_util.as_utc(op).isoformat(),
            "begon": dt_util.as_utc(dag["begon"]).isoformat() if dag.get("begon") else None,
        }})

    async def _async_growatt_dag_af(
        self, now: datetime, settings: dict[str, Any], device: dict[str, Any], b: Batterij, dag: dict[str, Any]
    ) -> None:
        """Een dag is om: de telling naar `growatt_nachten` (v0.151.0).

        Telde de coach samen langer dan `GROWATT_DAG_GAT` niet, dan rekent hij de dag na uit
        de kwartieropslag en de accustand uit de recorder (v0.174.0, `_async_growatt_narekenen`).
        Tot dan liet hij zo'n dag weg, en leerde hij juist niets van de dagen die het meest
        misgaan. In de klantwoning op 28-10-2026: een uitgave om 11:01, terwijl er die ochtend
        10,3 kWh van het net in de accu ging en om 11:00 4,4 kW zon naar het net ging bij 100%.
        Ontbreekt er in de kwartieren zelf meer dan `GROWATT_DAG_GAT`, dan telt de dag niet,
        met de reden in het log: wat ontbreekt blijft ontbreken.
        """
        device_id = device.get("id", "")
        if dag["gat"] * 3600.0 <= GROWATT_DAG_GAT.total_seconds():
            tellingen, hoe = [(dag["net"], dag["teveel"], dag["tekort"])], "geteld"
        else:
            begon = dag.get("begon")
            if begon is None:
                van, begin = now - timedelta(hours=24), False
            else:
                # Vanaf het begin van de dag, of het eerste begin van een etmaal daarna dat nog
                # in de kwartieren en de recorder staat.
                van, begin = begon, True
                if van < now - GROWATT_NAREKENEN_MAX:
                    van += -((van - (now - GROWATT_NAREKENEN_MAX)) // GROWATT_DAG) * GROWATT_DAG
            try:
                nagerekend, waarom = await self._async_growatt_narekenen(settings, device, b, van, now, begin)
            except Exception:  # noqa: BLE001 - narekenen mag de ronde niet kosten
                _LOGGER.exception("%s: kon de nacht niet narekenen", device_id)
                return
            if nagerekend is None:
                _LOGGER.info("%s: nacht niet nagekeken: %.1f uur niet geteld, en niet na te rekenen: %s",
                             device_id, dag["gat"], waarom)
                return
            tellingen, hoe = nagerekend, "nagerekend"
        nieuw = []
        for net, teveel, tekort in tellingen:
            if not (net > 0 or teveel > 0 or tekort > 0):
                continue
            nieuw.append(round(growatt_nacht(teveel, tekort, net), 3))
            _LOGGER.info("%s: nacht nagekeken (%s): %.2f kWh van het net, %.2f te veel, %.2f te weinig",
                         device_id, hoe, net, teveel, tekort)
        if not nieuw:
            return
        rij = self._batterij_rij(settings, device_id)
        nachten = [*growatt_nachten(rij), *nieuw][-GROWATT_NACHTEN_BEWAAR:]
        await self._async_batterij_bewaren(settings, device_id, {
            "growatt_nachten": nachten, "growatt_nachten_v": GROWATT_NACHTEN_V,
        })

    async def _async_growatt_narekenen(
        self, settings: dict[str, Any], device: dict[str, Any], b: Batterij, van: datetime, tot: datetime,
        begin: bool = False,
    ) -> tuple[list[tuple[float, float, float]] | None, str]:
        """Wat de telling van de dagen had moeten zijn, uit de kwartieren (v0.174.0).

        Het net en de batterij uit de kwartieropslag (`archive.py`, twee jaar), de accustand
        uit de recorder (tien dagen). Per kwartier hetzelfde als per ronde, zie
        `growatt_narekening`. Geeft per nacht (van het net, te veel, te weinig), of None met
        de reden. Een nacht waarin meer dan `GROWATT_DAG_GAT` ontbreekt valt weg. `begin`: `van`
        is het begin van een dag die de coach kende (v0.179.0).
        """
        kwartieren, waarom = await self._async_growatt_kwartieren(settings, device, van, tot)
        if kwartieren is None:
            return None, waarom
        prijsuren = [Uur(start=r["start"], end=r["end"], stand="", kwh=0.0, net_kwh=0.0, soc=0.0,
                         price=float(r["price"])) for r in self._prices(settings, van) if r.get("price") is not None]
        nachten = growatt_narekening(
            kwartieren, b.soc_min, b.soc_max, GROWATT_STIL_W, lambda m: growatt_duur(prijsuren, m), begin)
        goed = [n[:3] for n in nachten if n[3] * 3600.0 <= GROWATT_DAG_GAT.total_seconds()]
        if len(goed) < len(nachten):
            weg = ", ".join(f"{n[3]:.1f}" for n in nachten if n[3] * 3600.0 > GROWATT_DAG_GAT.total_seconds())
            _LOGGER.info("%s: %s van %s nachten niet nagerekend: %s uur zonder kwartieren of accustand",
                         device.get("id", ""), len(nachten) - len(goed), len(nachten), weg)
        if not goed:
            return None, "te veel uren zonder kwartieren of accustand" if nachten else "geen kwartieren"
        return goed, ""

    async def _async_growatt_kwartieren(
        self, settings: dict[str, Any], device: dict[str, Any], van: datetime, tot: datetime,
        accustand: bool = True,
    ) -> tuple[list[dict] | None, str]:
        """De kwartieren van `growatt_narekening`: het net, de batterij, de accustand en de zon.

        Zonder `accustand` alleen het net, de batterij en de zon, genoeg om een vak te zien
        (v0.179.0). De zon is er sinds v0.181.0, opgeteld over elke omvormer: zon die de accu laadt
        is geen vak (`_growatt_vak`). Zonder zonsensor geen `zon_w`.
        """
        sources = settings.get("sources") or {}
        entities = device.get("entities") or {}
        if sources.get("grid_mode") == "signed":
            netten = [sources.get("grid_signed")]
        else:
            netten = [sources.get("grid_import"), sources.get("grid_export")]
        getekend = device.get("entity")
        accus = [getekend] if getekend else [entities.get("charge_power"), entities.get("discharge_power")]
        soc_id = entities.get("soc")
        if not netten[0] or not any(accus) or (accustand and not soc_id):
            return None, "geen meter, batterijvermogen of accustand"
        zonnen = [e for e in (sources.get("solar"), *(sources.get("solar_extra") or [])) if e]
        ids = [e for e in (*netten, *accus, *zonnen) if e]
        rijen = await self._async_kwartieren(ids, van, tot)
        # Een kwartier telt als de sensor er twee derde van gedekt is.
        per = {e: {int(r["start"]): r for r in rijen.get(e) or [] if (r.get("seconden") or 0) >= 600} for e in ids}
        if not any(per[e] for e in (*netten, *accus) if e):
            return None, "geen kwartieren"
        socs: list[tuple[datetime, float | None]] = []
        for moment, staat in await self._async_geschiedenis(soc_id, van - timedelta(hours=6), tot) if accustand else []:
            try:
                socs.append((moment, float(staat)))
            except (TypeError, ValueError):
                socs.append((moment, None))
        socs.sort(key=lambda r: r[0])
        if accustand and not socs:
            return None, "geen accustand in de recorder"
        signed_invert = bool(sources.get("grid_signed_invert"))
        bat_invert = bool((device.get("battery") or {}).get("power_invert"))

        def gemiddeld(entity_id: str | None, ts: int) -> float | None:
            if not entity_id:
                return 0.0
            rij = per[entity_id].get(ts)
            return None if rij is None else float(rij["gemiddeld"])

        def verschil(plus: float | None, min_: float | None) -> float | None:
            return None if plus is None or min_ is None else plus - min_

        kwartieren = []
        i_soc, soc_nu = 0, None
        zone = dt_util.get_default_time_zone()
        moment = van.replace(tzinfo=zone).astimezone(timezone.utc)
        moment = moment.replace(minute=moment.minute - moment.minute % 15, second=0, microsecond=0)
        eind = tot.replace(tzinfo=zone).astimezone(timezone.utc)
        while moment + timedelta(minutes=15) <= eind:
            ts = int(moment.timestamp())
            begin = moment.astimezone(zone).replace(tzinfo=None)
            klaar = (moment + timedelta(minutes=15)).astimezone(zone).replace(tzinfo=None)
            if len(netten) == 1:
                net_w = gemiddeld(netten[0], ts)
                if net_w is not None and signed_invert:
                    net_w = -net_w
            else:
                net_w = verschil(gemiddeld(netten[0], ts), gemiddeld(netten[1], ts))
            if len(accus) == 1:
                bat_w = gemiddeld(accus[0], ts)
                if bat_w is not None and bat_invert:
                    bat_w = -bat_w
            else:
                bat_w = verschil(gemiddeld(accus[0], ts), gemiddeld(accus[1], ts))
            # De accustand van het begin van het kwartier, en elke verandering erin.
            while i_soc < len(socs) and socs[i_soc][0] <= begin:
                soc_nu = socs[i_soc][1]
                i_soc += 1
            standen = [soc_nu]
            while i_soc < len(socs) and socs[i_soc][0] < klaar:
                soc_nu = socs[i_soc][1]
                standen.append(soc_nu)
                i_soc += 1
            bekend = None not in standen
            kwartier = {
                "start": begin, "net_w": net_w, "bat_w": bat_w,
                "soc_laag": min(standen) if bekend else None, "soc_hoog": max(standen) if bekend else None,
            }
            if zonnen:
                zon = [gemiddeld(e, ts) for e in zonnen]
                kwartier["zon_w"] = None if None in zon else max(0.0, sum(zon))
            kwartieren.append(kwartier)
            moment += timedelta(minutes=15)
        return kwartieren, ""

    async def _async_batterij_loslaten(self, device: dict[str, Any], herstart: bool = False) -> None:
        """De batterij teruggeven: vermogen op nul, en zijn eigen stand terug.

        Dezelfde gedachte als de stroom terug op de boiler: een batterij die op
        zijn laatste opdracht blijft staan loopt leeg naar het net of trekt vol
        van het net tot iemand het ziet. Bij een herstart alleen de nul, in de
        externe modus (v0.96.0); zie `_async_bij_stop`.
        """
        sessie = self._batterij.get(device.get("id", ""))
        if device.get("brand") in BATTERIJ_SCHEMA:
            # Een Growatt: het laden van het net eruit, want het schema herhaalt zich
            # elke dag (v0.150.0). Wat er niet van de coach was laat hij staan. Bij een
            # herstart niet: dan schrijft de coach daarna meteen opnieuw, en twee
            # opdrachten vlak na elkaar faalt de tweede.
            geschreven = (sessie or {}).get("growatt_geschreven")
            if geschreven is not None and geschreven.net and not herstart:
                if await self._async_growatt_schrijf(device, GrowattSchema()) and sessie is not None:
                    sessie["growatt_geschreven"] = GrowattSchema()
            if sessie is not None:
                sessie["growatt_stuurt"] = False
            return
        zelf = bool(sessie and sessie.get("zelf"))
        if sessie is not None:
            sessie["stuurt"] = False
            sessie["zelf"] = None
            sessie["nul_open"] = False
            sessie["regelaar"] = Regelaar()
            if sessie.get("settings") is not None:
                await self._async_laadgrens_terug(sessie["settings"], device)
        if herstart and zelf:
            # Deed hij zelf nul op de meter, dan ook bij een herstart op 0 W in
            # de externe stand: "bij herstart accu op 0 en dan pas kijken" (de
            # eigenaar, 24-09-2026). Na de herstart kiest de coach opnieuw.
            await self._async_overnemen_op_nul(device)
            return
        await self._async_batterij_zetten(device, 0.0)
        if not herstart:
            await self._async_batterij_modus(device, "idle_mode")

    async def _async_batterijen_los(self, herstart: bool = False) -> None:
        """Bij het stoppen van de coach: elke batterij die hij stuurde teruggeven."""
        try:
            settings = await async_get_store(self.hass).async_load()
        except Exception:  # noqa: BLE001 - afsluiten mag hier niet op stuklopen
            return
        for device in settings.get("devices") or []:
            if device.get("type") != "thuisbatterij":
                continue
            sessie = self._batterij.get(device.get("id", "")) or {}
            if not (sessie.get("stuurt") or sessie.get("growatt_stuurt")):
                continue
            if "growatt_dag" in sessie:
                # De telling van de nacht, zodat een herstart de dag niet wist (v0.171.0).
                try:
                    await self._async_growatt_dag_bewaren(settings, device.get("id", ""), sessie)
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("kon de nachttelling van %s niet bewaren", device.get("id"))
            try:
                await self._async_batterij_loslaten(device, herstart=herstart)
            except Exception:  # noqa: BLE001 - één apparaat is niet alle apparaten
                _LOGGER.exception("kon %s niet teruggeven bij het afsluiten", device.get("id"))

    async def _one(
        self,
        now: datetime,
        settings: dict[str, Any],
        device: dict[str, Any],
        level: str,
        reserved: dict[str, float] | None = None,
    ) -> float:
        """Look at one charging point and act on what the planner says.

        Geeft terug hoeveel ampère er méér gevraagd is dan deze paal op dit
        moment trekt. Dat is de ruimte die het volgende laadpunt in deze ronde
        niet meer als vrij mag zien: de fasemeting kent hem nog niet, want de
        auto is nog niet begonnen met trekken.
        """
        device_id = device.get("id", "")
        grid, car, charger, window = self._read(now, settings, device, reserved)
        await self._async_soc_vast_melden(device, car)
        try:
            await self._async_auto_wekken(now, settings, device, charger.connected)
        except ServiceNotFound:
            _LOGGER.warning("%s: de wekknop van de auto bestaat niet (nog niet geladen?)", device_id)

        # Wekken mag zolang de auto aan de kabel hangt, niet laadt en de poging
        # van deze sessie nog openstaat. Dat de coach ook wíl laden weet de
        # planner zelf; hier gaat het alleen over of het nog mag.
        # Is de klaar-tijd voorbijgegaan terwijl de auto niet vol is? Te zien aan
        # een klaar-tijd die opschuift: die van vandaag is dan verstreken en de
        # eerstvolgende ligt verder weg. Dit moet vóór het besluit gebeuren, want
        # anders schrijft hij eerst nog één keer een 0 naar de paal.
        mikpunt = (self._sessie.get(device_id) or {}).get("mikpunt")
        terug = self._mikpunt_terug.pop(device_id, None)
        if terug is not None:
            # De eerste ronde na een herstart (v0.172.0): de sessie is nieuw en kent alleen
            # de klaar-tijd van nu, ook als die van voor de herstart al voorbij is.
            mikpunt = terug
        if (
            mikpunt is not None
            and window.deadline != mikpunt
            and mikpunt <= now
            and charger.connected
            and not charger.complete
        ):
            self._te_laat.add(device_id)

        # Werkt hij al toe naar deze klaar-tijd? Een andere klaar-tijd is een
        # andere afspraak, dus dan telt het besluit van daarnet niet meer.
        must_finish = bool(
            window.enabled
            and window.deadline is not None
            and self._deadline_for.get(device_id) == window.deadline
        )
        wektijd = self._wake_until.get(device_id)
        waking = charger.connected and not charger.charging and (
            device_id not in self._woken or (wektijd is not None and now < wektijd)
        )
        prijzen = self._prices(settings)
        tarief = self._tarief(settings)
        zon = self._sun(settings)
        verwachting = Forecast(
            solar_kwh=self._zon_kwh,
            house_kwh=self._huis_kwh,
            estimated=self._zon_geschat,
            solar_factor=self._zon_gemeten(now),
            solar_day=now.date(),
        )

        proef = self._proef_stand(
            now, device_id, self._chosen_car(settings, device)[1], charger,
            mag=level == LEVEL_STEER or (level == LEVEL_PROPOSE and device_id in self._approved),
        )

        def besluit(auto: Car) -> Decision:
            return decide(
                now, prijzen, grid, auto, charger, window, tarief, zon, verwachting,
                proef=proef,
                holding=self._holding.get(device_id, 0),
                waking=waking,
                asking_seconds=(
                    (now - self._asking_since[device_id]).total_seconds()
                    if device_id in self._asking_since
                    else 0.0
                ),
                must_finish=must_finish,
                overdue=device_id in self._te_laat,
            )

        decision = besluit(car)
        may_act = level == LEVEL_STEER or (
            level == LEVEL_PROPOSE and device_id in self._approved
        )
        # Een Alfen mag van fasen wisselen (v0.104.0): hetzelfde besluit op een
        # fase ernaast, en `kies_fasen` kiest. Het plan blijft dat van het
        # profiel, want drie fasen is wat de paal kan als het moet. `car_nu` is de
        # auto zoals hij deze ronde werkelijk laadt, voor het tempo.
        car_nu = car
        fasen_nu: int | None = None
        omzetten: int | None = None
        if may_act and car.phases == 3 and self._fasewissel_aan(device):
            fasen_nu = self._fasen_stand(device)
            if fasen_nu is not None:
                car_een = replace(car, phases=1, phases_measured=False)
                decision, een_fase, omzetten = self._fasen_besluit(
                    now, device_id, charger, decision, besluit(car_een), grid, fasen_nu
                )
                if een_fase:
                    car_nu = car_een

        await self._async_proef_na(now, device, car, charger, decision)
        if decision.rule == "complete":
            self._te_laat.discard(device_id)
        if decision.rule.startswith("deadline") and window.deadline is not None:
            self._deadline_for[device_id] = window.deadline
        elif not decision.charge or decision.rule in ("boost", "complete"):
            # Een volle auto, een opdracht van de bewoner of een besluit om te
            # stoppen maakt de race naar de klaar-tijd irrelevant. Bij de
            # eerstvolgende ronde wordt gewoon opnieuw gerekend.
            self._deadline_for.pop(device_id, None)
        # De wekpoging is verbruikt zodra hij verstuurd is, en het aanbieden
        # begint te tellen zodra de coach stroom vraagt terwijl er niets loopt.
        if decision.rule.endswith("+wake"):
            self._woken.add(device_id)
            self._wake_until.setdefault(device_id, now + WAKE_WINDOW)
        elif not decision.charge:
            # Een sessie die bewust stilgezet wordt, mag straks opnieuw gewekt
            # worden. Dat is geen tweede poging binnen dezelfde start maar een
            # nieuwe start, en juist daar bleek de auto niet wakker te worden:
            # na hervatten van een pauze deed hij op 6 A weer niets.
            self._woken.discard(device_id)
            self._wake_until.pop(device_id, None)
        if decision.charge and charger.connected and not charger.charging:
            self._asking_since.setdefault(device_id, now)
        else:
            self._asking_since.pop(device_id, None)
        self._bijhouden(now, device, car, charger, window, decision, grid, settings)
        self._tempo_leren(now, settings, device, car_nu, charger, grid)
        # Een nieuwe meting van het laadrendement bewaren (v0.94.0).
        if device_id in self._rend_meting:
            self.hass.async_create_task(self._async_rendement_bewaren(settings, device_id))

        # Bijhouden hoe lang een sessie al tegen de ladder in wordt aangehouden.
        # Zodra de ladder het weer eens is met wat er gebeurt, staat de teller
        # op nul en heeft de volgende wolk weer zijn volle uitstel.
        self._holding[device_id] = (
            self._holding.get(device_id, 0) + 1 if decision.holding else 0
        )

        # Remembered before anything is sent, so the panel can show what the
        # coach would do even at a level where it does nothing.
        self.state[device_id] = {
            **asdict(decision),
            "at": now.isoformat(),
            "level": level,
            "applied": level == LEVEL_STEER,
            # De hele tijdlijn tot de auto vol moet zijn. Uit dezelfde sommen
            # als het besluit hierboven, want een tijdlijn die iets anders zegt
            # dan wat de coach doet laat de bewoner op het verkeerde wachten.
            # Behalve in de modus zon of continu zonder planning (v0.87.0): dan
            # volgt hij het nu en is er niets vooruit te plannen, en een lijst
            # met goedkoopste uren zou iets beloven wat hij niet doet.
            # En zonder auto aan de paal ook niet (v0.141.0): de eigenaar op 19-10-2026
            # over laadblokken bij een lege paal, "niet weergeven of meenemen". Anders
            # plant de vooruitblik ze en rekent de batterij erop (`_auto_laden`).
            "plan_ahead": (
                None
                if decision.rule == "disconnected"
                or (not window.enabled and charger.modus in MODI_ZONDER_SOM)
                else self._tijdlijn(
                    now, settings, grid, car, charger, window,
                    # Laadt de klaar-tijdregel, dan zegt de tijdlijn dat ook
                    # (v0.128.0), en niet "wachten" boven een paal die laadt.
                    doorladen=decision.charge and decision.rule.startswith("deadline"),
                )
            ),
            # De klaar-tijd van het schema, ook zonder plan: de kaart toont de volgende
            # deadline als er geen auto hangt (v0.141.0).
            "deadline_next": window.deadline.isoformat() if window.enabled and window.deadline is not None else None,
            # Op hoeveel fasen een Alfen die mag wisselen nu staat (v0.104.0),
            # of niets als de coach daar niet over gaat.
            "phases_now": fasen_nu,
            # Welke modus er geldt, en of dat de keuze van deze beurt is of de
            # voorkeur van de paal. Snel is `boost`; een planning wint.
            "mode": "snel" if charger.boost else charger.modus,
            "mode_session": device_id in self._modus,
            # Tot hoeveel procent deze beurt laadt, en of dat de keuze van de
            # kaart is of het doel uit het profiel (v0.88.0).
            "target_percent": car.target_percent,
            "target_session": device_id in self._doel,
            # De laadlimiet van de planning als die deze beurt geldt, de
            # algemene limiet ernaast, en de dag van de klaar-tijd (v0.96.0).
            "target_plan": self._doel_planning.get(device_id),
            "target_general": self._doel_algemeen.get(device_id),
            "target_day": (
                DAGNAMEN[window.deadline.weekday()]
                if device_id in self._doel_planning and window.deadline else None
            ),
            # De accustand waar de coach mee rekent, en of die geschat is (een
            # opgegeven stand plus wat de paal er sindsdien in deed). De kaart
            # zegt het onder "Hoe vol is de auto nu?" (v0.89.0).
            "soc_now": None if car.soc_percent is None else round(car.soc_percent, 1),
            "soc_estimated": bool(car.soc_estimated),
            # Of de kaart moet vragen hoe vol de auto is (v0.117.0): er zit een
            # kabel in, de auto is geen gast, zijn accu is bekend, en hij zegt
            # het zelf niet, want hij heeft geen sensor of die zwijgt (`_soc_ruw`
            # staat er alleen bij een getal). Dezelfde grens als `vraagAccustand`
            # in devices.js. De number `accustand` geeft het door aan de
            # laadpaalkaart van DomotiApp Lovelace, met `soc_sensor` voor de uitleg.
            "soc_ask": (
                decision.rule != "disconnected" and not car.guest
                and car.capacity_kwh > 0 and device_id not in self._soc_ruw
            ),
            "soc_sensor": not car.guest and bool(
                (self._chosen_car(settings, device)[1] or {}).get("soc_entity")
            ),
            # Wat er deze beurt in ging, of in de laatste als de kabel eruit is
            # (v0.106.0); zie `_beurt_kaart`.
            "session": (
                self._beurt_kaart(device, self._sessie[device_id], actief=True)
                if device_id in self._sessie
                else self._vorige_beurt.get(device_id)
            ),
            "planned": bool(window.enabled),
            # Of er een knop "accustand opvragen" op de kaart hoort, en wanneer
            # de auto voor het laatst gewekt is.
            "wake": self._wekbaar(settings, device),
            "woke_at": self._gewekt[device_id].isoformat() if device_id in self._gewekt else None,
            # De actieradius van de auto in km, voor de laadpaalkaart (v0.111.0).
            "range_km": self._actieradius(settings, device),
        }
        # Iets dat alleen de bewoner zelf kan verhelpen, en dat losstaat van
        # het besluit van deze ronde. Het gaat dus naast de reden op de kaart
        # en niet erin.
        # De lastbewaker alleen zolang de coach ook werkelijk wil laden: bij een
        # auto die vol is of wacht begrenst hij niets. De eigenaar op 30-09-2026,
        # met deze tip als melding op zijn telefoon 24 minuten nadat de auto op
        # zijn doel stond: "waarom krijg ik deze melding als de auto al vol is?"
        nettip = self._nettip(now)
        fasetip = "" if nettip else self._fasetip(settings, device, charger)
        tip = (
            nettip
            or fasetip
            or (self._bewakertip(settings, device, charger) if decision.charge else "")
        )
        tipsoort = "net" if nettip else ("fase" if fasetip else ("uitleg" if tip else ""))
        # Is de netmeting terug, dan mag een volgende stilte weer gemeld worden.
        if not nettip and self._getipt.get(device_id) == "net":
            self._getipt.pop(device_id, None)
        self.state[device_id]["tip"] = tip
        # Eerst opruimen, dan pas opschrijven wat de stand is. Andersom bleef er
        # op de kaart nog een minuut "snelladen staat aan" staan nadat de kabel
        # er al uit was, en dat leest als een knop die blijft hangen.
        #
        # Een akkoord duurt zolang de auto aan de kabel hangt, en snelladen ook:
        # de auto waarvoor het bedoeld was staat er dan niet meer.
        #
        # Alleen als de paal het zelf zegt (v0.98.0). Na een herstart zegt een
        # paal waarvan de integratie nog laadt eerst niets, en dan wiste dit de
        # knoppen die `_restore` net had teruggehaald, en de opgegeven accustand.
        if not charger.connected and self._echt_los.get(device_id, True):
            self._approved.discard(device_id)
            self._boost.discard(device_id)
            self._modus.pop(device_id, None)
            self._doel.pop(device_id, None)
            self._rend_start.pop(device_id, None)
            self._paused.discard(device_id)
            self._zon.pop(device_id, None)
            self._holding.pop(device_id, None)
            self._pause_until.pop(device_id, None)
            self._woken.discard(device_id)
            self._wake_until.pop(device_id, None)
            self._asking_since.pop(device_id, None)
            self._deadline_for.pop(device_id, None)
            self._te_laat.discard(device_id)
            self._herstart_open.discard(device_id)
            self._herstart_gedaan.pop(device_id, None)
            self._herstart_melden.discard(device_id)
            self._tempo_band.pop(device_id, None)
            self._tempo_vorig.pop(device_id, None)
            self._limiet_vorig.pop(device_id, None)
            self._limiet_omhoog.pop(device_id, None)
            self._weerleg_vorig.pop(device_id, None)
            self._soc_asked.discard(device_id)
            self._warned.pop(device_id, None)
            if self._getipt.get(device_id) != "net":
                self._getipt.pop(device_id, None)
            # Wat er over deze sessie bewaard is gaat mee weg. Een opgegeven
            # accustand hoort bij de auto die eraan hing: blijft die staan, dan
            # rekent de coach morgen met het percentage van gisteren terwijl er
            # honderd kilometer tussen zit, en dat is de gevaarlijke kant op.
            # Voor de knoppen geldt hetzelfde: wie de kabel eruit trekt, heeft
            # niets meer goedgekeurd of gepauzeerd.
            await self._async_forget(settings, device_id)

        self._laden_onthouden(device_id)
        self.state[device_id]["applied"] = may_act
        self.state[device_id]["approved"] = device_id in self._approved
        self.state[device_id]["boost"] = device_id in self._boost
        self.state[device_id]["paused"] = device_id in self._paused
        # Of de paal op dit moment werkelijk laadt. Niet voor een besluit maar
        # voor de kaart: een akkoord vragen leest anders als de auto al loopt.
        # Dan begint er niets, dan wordt er iets overgenomen.
        self.state[device_id]["charging"] = charger.charging
        self.hass.bus.async_fire(
            EVENT_DECISION, {"device": device_id, **self.state[device_id]}
        )
        await self._async_noteer_besluit(device, device_id, now)

        # Wat deze paal straks méér gaat trekken dan nu. Alleen als de coach
        # ook werkelijk mag sturen, want anders gaat er niets naar de paal en is
        # er dus ook niets gereserveerd.
        claim = (
            max(0.0, decision.amps - charger.actual_amps)
            if may_act and decision.charge
            else 0.0
        )
        self._paal_stroom[device_id] = max(
            float(decision.amps) if may_act and decision.charge else 0.0, float(charger.actual_amps or 0.0)
        )

        if not may_act:
            return 0.0

        await self._async_verslag(now, device, car, charger, window, decision)

        if decision.needs_soc:
            await self._async_ask_soc(device, decision)

        if tip and self._getipt.get(device_id) != tipsoort:
            self._getipt[device_id] = tipsoort
            # Een meter die zwijgt of een fase die niet klopt moet de bewoner
            # zelf oplossen, en dat is kritiek. De lastbewaker die het tempo
            # bepaalt is uitleg: die staat op de kaart en in de geschiedenis,
            # en gaat niet naar de telefoon. De eigenaar op 06-09-2026: per
            # beurt één verslag, plus wat de bewoner zelf moet oplossen.
            uitleg = not nettip and not fasetip
            await self._async_tell(
                f"{device.get('name') or t('De laadpaal')}: {tip}",
                kritiek=not uitleg, telefoon=not uitleg,
            )

        # De pauze van de bewoner wint, ook van de klaar-tijd: het is zijn huis
        # en zijn knop. Maar de waarschuwing komt terug zolang het risico er is,
        # want één keer is te weinig om een lege auto mee te voorkomen.
        # Verdwijnt het risico, dan vervalt de klok en begint hij bij een
        # volgende keer weer opnieuw.
        gewaarschuwd = self._warned.get(device_id)
        if not decision.deadline_risk:
            self._warned.pop(device_id, None)
        elif gewaarschuwd is None or now - gewaarschuwd >= PAUSE_WARN_AGAIN:
            self._warned[device_id] = now
            await self._async_tell(
                t(
                    "De pauze op {naam} staat nog aan, en zo is de auto niet op tijd vol. "
                    "Hervat het laden of verzet je klaar-tijd.",
                    naam=device.get("name") or t("de laadpaal"),
                ),
                kritiek=True,
            )

        # The dead band holds only while the charging point is doing what it was
        # asked. When it is not, the command has to go again, or a car stands
        # still all night purely because the decision happened not to change:
        # that is exactly what a load balancer letting go looks like from here.
        # Prodding is on a timer of its own, because some of the reasons a
        # charger does not follow cannot be argued with by asking twice.
        following = self._following(device, charger, decision)
        if following:
            self._nudged.pop(device_id, None)
            if (
                not should_send(self._last.get(device_id), decision)
                and not self._pause_expiring(device_id, now)
                and not self._ververst(device)
            ):
                return claim
        elif charger.paused_by_balancer or held_back(charger):
            # Not following, and saying why: something outside the coach is
            # holding it. Ask again now and then, so a charger that quietly let
            # go is picked back up, but not every minute. Repeating a command at
            # a load balancer changes nothing and only fills its log.
            if not self._nudge_due(device_id, now):
                return claim
        else:
            # Not following and no reason given. That is the case where asking
            # again is exactly the right thing, so do it on the next round: this
            # is what a balancer letting go looks like from here, and a car that
            # waits five minutes for it has waited four too many.
            self._nudged.pop(device_id, None)

        # De paal staat stil voor een fasewissel: nu omzetten, en de volgende
        # ronde laadt hij verder op het nieuwe aantal fasen.
        if omzetten is not None:
            await self._async_fasen(now, device, omzetten)

        if await self._apply(device, charger, decision, now):
            self._last[device_id] = decision
            # A session that a balancer is holding has not begun, so it must not
            # be stamped as begun: doing so would run the minimum out while
            # nothing charges, and have the coach read a standstill as its pace.
            if decision.charge and not charger.paused_by_balancer:
                self._since.setdefault(device_id, now)
            elif not decision.charge:
                self._since.pop(device_id, None)

        return claim

    @staticmethod
    def _fasewissel_aan(device: dict[str, Any]) -> bool:
        """Of de coach deze paal van fasen mag laten wisselen (v0.104.0).

        Alleen een Alfen, met de keuzelijst van de fasen ingevuld en het vinkje
        aan. De eigenaar op 30-09-2026: "Easee houden we zo en alfen passen we aan."
        """
        return (
            device.get("brand") == "alfen"
            and bool(device.get("phase_switching"))
            and bool((device.get("entities") or {}).get("phases"))
        )

    def _fasen_stand(self, device: dict[str, Any]) -> int | None:
        """Op hoeveel fasen de paal nu staat, uit zijn keuzelijst ("1 Phase", "3 Phases")."""
        tekst = _text(self.hass, (device.get("entities") or {}).get("phases")).strip()
        if tekst[:1] in ("1", "3"):
            return int(tekst[:1])
        return None

    def _fasen_besluit(
        self,
        now: datetime,
        device_id: str,
        charger: Charger,
        drie: Decision,
        een: Decision,
        grid: Grid,
        fasen_nu: int,
    ) -> tuple[Decision, bool, int | None]:
        """Welk besluit er deze ronde geldt, of dat op een fase is, en of er omgezet moet worden.

        Wisselen doet hij alleen stilstaand: eerst 0 A, en pas als er geen stroom
        meer loopt de keuzelijst om (`_async_fasen`); de ronde daarna laadt hij
        verder. Een paal die al stilstaat wisselt meteen. Een lopende beurt
        wisselt pas als de wens `FASE_WACHT` blijft staan en de vorige wissel
        `FASE_RUST` geleden is. Komt de auto niet binnen `FASE_WACHT` tot
        stilstand, of volgt de paal de keuzelijst niet, dan laat hij het een
        `FASE_RUST` rusten.
        """
        wens = kies_fasen(drie, een, grid.surplus_w, fasen_nu)
        vorige = self._fase_wens.get(device_id)
        if vorige is None or vorige[0] != wens:
            self._fase_wens[device_id] = (wens, now)
        sinds = self._fase_wens[device_id][1]
        # Het besluit op één fase telt alleen als het op zon laadt. Anders rekent
        # het met een auto die alleen één fase kan, en dan zegt de klaar-tijd al
        # gauw "nu van het net" terwijl drie fasen straks ruim op tijd zijn.
        if fasen_nu == 1 and op_zon(een):
            huidig = replace(een, reason=t("{reden} Hij laadt op één fase.", reden=een.reason).strip())
        elif drie.rule == een.rule == "zon-wacht":
            # Allebei wachten op zon: dan begint hij op één fase, en is dat de
            # drempel die de bewoner hoort te lezen (v0.106.3). In de eerste
            # woning op 03-10-2026 om 13:57 stond er "Hij begint vanaf 3,7 kW",
            # terwijl hij met de wissel al bij 1,2 kW begint.
            huidig = een
        else:
            huidig = drie
        bezig = self._fase_bezig.get(device_id)

        if wens in (0, fasen_nu):
            self._fase_bezig.pop(device_id, None)
            return huidig, fasen_nu == 1, None

        stil = not charger.charging and charger.actual_amps < 1.0
        if bezig is None:
            laatste = self._fase_gewisseld.get(device_id)
            if not stil and (
                now - sinds < FASE_WACHT or (laatste is not None and now - laatste < FASE_RUST)
            ):
                return huidig, fasen_nu == 1, None
            bezig = self._fase_bezig[device_id] = {"naar": wens, "sinds": now}
        elif now - bezig["sinds"] >= FASE_WACHT:
            # Hij komt niet tot stilstand, of de paal volgt de keuzelijst niet.
            _LOGGER.warning(
                "%s: de fasewissel naar %s lukt niet (laadt nog: %s, staat op %s fasen)",
                device_id, wens, charger.charging, fasen_nu,
            )
            self._fase_bezig.pop(device_id, None)
            self._fase_gewisseld[device_id] = now
            return huidig, fasen_nu == 1, None

        kw = getal(grid.surplus_w / 1000, 1)
        if wens == 1:
            reden = t(
                "Er is {kw} kW zon over, te weinig voor drie fasen. "
                "Hij zet de paal op één fase: even stil, dan verder.",
                kw=kw,
            )
        elif op_zon(drie):
            reden = t(
                "Er is {kw} kW zon over, genoeg voor drie fasen. "
                "Hij zet de paal op drie fasen: even stil, dan verder.",
                kw=kw,
            )
        else:
            reden = t("Hij zet de paal op drie fasen om op vol vermogen te laden: even stil, dan verder.")
        doel = een if wens == 1 else drie
        stop = Decision(False, 0, reden, plan=doel.plan, rule="fasewissel")
        return stop, fasen_nu == 1, (wens if stil and not bezig.get("omgezet") else None)

    async def _async_fasen(self, now: datetime, device: dict[str, Any], fasen: int) -> None:
        """De keuzelijst van de fasen omzetten, op een paal die stilstaat."""
        device_id = device.get("id", "")
        entity = (device.get("entities") or {}).get("phases")
        staat = self.hass.states.get(entity) if entity else None
        opties = [str(o) for o in ((staat.attributes or {}).get("options") or [])] if staat else []
        keuze = next((o for o in opties if o.strip().startswith(str(fasen))), None)
        bezig = self._fase_bezig.get(device_id)
        if keuze is None:
            _LOGGER.warning("%s: de keuzelijst %s kent geen %s fasen (%s)", device_id, entity, fasen, opties)
            self._fase_bezig.pop(device_id, None)
            self._fase_gewisseld[device_id] = now
            return
        try:
            await self.hass.services.async_call(
                "select", "select_option", {"entity_id": entity, "option": keuze}, blocking=True
            )
        except ServiceNotFound:
            _LOGGER.warning("%s: de keuzelijst %s is er niet (nog niet geladen?)", device_id, entity)
            self._fase_bezig.pop(device_id, None)
            self._fase_gewisseld[device_id] = now
            return
        if bezig is not None:
            bezig["omgezet"] = now
        self._fase_gewisseld[device_id] = now
        _LOGGER.info("%s: fasen omgezet naar %s (%s)", device_id, fasen, keuze)

    def _smooth(self, device_id: str, surplus: float, now: datetime) -> float:
        """Het overschot, ontdaan van het gerimpel van een enkele minuut.

        Een wolk die voor de zon schuift, een waterkoker die aangaat: het
        overschot springt de hele dag heen en weer. Een coach die daar elke
        minuut achteraan loopt, stuurt de laadpaal grijs en levert er niets voor
        terug, want de auto merkt er niets van.

        Omhoog gaat langzaam en omlaag gaat meteen. Dat is met opzet niet
        symmetrisch: te veel vragen betekent inkopen tegen de dagprijs, en dat is
        een fout die geld kost. Te weinig vragen betekent een beetje zon
        exporteren die je ook zelf had kunnen gebruiken, en dat kost hooguit het
        verschil. Dus wordt er voor omhoog met het laagste van de laatste paar
        metingen gerekend, en voor omlaag met de meting van nu.
        """
        recent = self._zon.setdefault(device_id, [])
        recent.append((now, surplus))
        grens = now - SMOOTH_WINDOW
        recent[:] = [meting for meting in recent if meting[0] >= grens]
        return min(waarde for _, waarde in recent)

    def _following(
        self, device: dict[str, Any], charger: Charger, decision: Decision
    ) -> bool:
        """Of de laadpaal doet wat er gevraagd is.

        Voor laden is dat simpel: laadt hij. Voor niet laden juist niet, en daar
        zat een fout in. "Hij laadt nu niet" is namelijk niet hetzelfde als "hij
        gaat niet laden": een paal die op goedkeuring staat te wachten met een
        limiet van 32 erin begint zodra de auto erom vraagt. De coach zag dan
        geen verschil met wat hij wilde en stuurde dus niets, waarna de auto ging
        laden op een moment dat hij dat juist niet wilde. Wie zijn auto inplugt en
        meteen op pauze drukt, kreeg zo een knop die niets deed.

        Dus telt voor niet laden of onze nul er werkelijk staat, en niet of de
        paal toevallig stilstaat. Kan die limiet niet teruggelezen worden, dan
        blijft alleen de oude, zwakkere vraag over.
        """
        if decision.charge:
            return charger.charging
        if self._niets_schrijven(charger, decision):
            return True

        limiet = _number(self.hass, (device.get("entities") or {}).get("dynamic_limit"))
        if limiet is None:
            return not charger.charging
        return limiet < 0.5

    def _pause_expiring(self, device_id: str, now: datetime) -> bool:
        """Of de pauze die er staat bijna verlopen is en opnieuw moet.

        Een pauze wordt weggeschreven met de tijd die hij bedoeld is te duren,
        want dat is wat er moet gebeuren als de coach wegvalt: bij wachten op een
        goedkoop uur mag hij aflopen, en dan laadt de auto gewoon door. Maar
        zolang de coach er wél is, moet die pauze niet halverwege omvallen omdat
        het besluit toevallig niet veranderde. Vandaar dat hij ruim voor het
        einde nog eens gezet wordt.
        """
        einde = self._pause_until.get(device_id)
        return einde is not None and now >= einde - PAUSE_REFRESH

    def _nudge_due(self, device_id: str, now: datetime) -> bool:
        """Whether it is time to prod a charging point that is not following."""
        last = self._nudged.get(device_id)
        if last is not None and now - last < NUDGE_INTERVAL:
            return False
        self._nudged[device_id] = now
        return True

    def _prijsbron(
        self, dynamic: dict[str, Any], now: datetime | None = None
    ) -> tuple[dict[str, Any], bool]:
        """Met welke prijzen er nu gerekend wordt, en of dat de reserve is.

        De eigenaar op 29-09-2026, toen de integratie van Frank Energie na een
        wijziging bij Frank niets meer gaf: "Ik heb ook Nord Pool draaien. Dat
        wil ik als fallback hebben, zodat als Frank eruit ligt dat hij dat
        oppakt, en is Frank weer terug dat hij dat weer pakt."

        De eigen prijsbron telt zolang hij een prijs heeft voor dit moment. Heeft
        hij die niet en de reserve wel, dan de reserve, als marktprijs of als
        all-in prijs zoals ingevuld; een marktprijs krijgt dezelfde belasting,
        opslag en btw als altijd. Er wordt niet gemengd: een lijst die half van
        de een en half van de ander is, rekent met twee soorten prijzen door
        elkaar.
        """
        reserve = dynamic.get("fallback_entity")
        reserve_soort = dynamic.get("fallback_source")
        # Een kale marktprijs naast een all-in prijs is vanzelf de reserve
        # (v0.129.0). De bewoner van de eerste woning op 18-10-2026: "Als de
        # integratie met een leverancier wegvalt, weet je 100% zeker dat de
        # opgebouwde prijs ook klopt aan de hand van Nord Pool plus de losse
        # elementen." Of die opbouw klopt zegt `prijsopbouw.controleer`.
        markt = dynamic.get("market_entity")
        if (not reserve and dynamic.get("source") == "all_in" and markt
                and markt != dynamic.get("all_in_entity")):
            reserve, reserve_soort = markt, "market"
        if not reserve:
            return dynamic, False
        nu = _moment(now)
        interval = str(dynamic.get("interval") or "hour")

        def heeft_nu(entity_id: str | None) -> bool:
            state = self.hass.states.get(entity_id) if entity_id else None
            if state is None or state.state in ("unknown", "unavailable", ""):
                if entity_id not in self._nordpool:
                    return False
            return any(start <= nu < end for start, (end, _) in self._slots(entity_id, interval).items())

        eigen = dynamic.get("all_in_entity") if dynamic.get("source") == "all_in" else dynamic.get("market_entity")
        if heeft_nu(eigen) or not heeft_nu(reserve):
            return dynamic, False
        soort = "all_in" if reserve_soort == "all_in" else "market"
        vervanger = {**dynamic, "source": soort}
        if soort == "all_in":
            vervanger["all_in_entity"] = reserve
            # Een marktprijs van de eigen bron die nog wel werkt blijft voor de
            # teruglevering; een die ook weg is zegt niets.
            if not heeft_nu(dynamic.get("market_entity")):
                vervanger["market_entity"] = ""
        else:
            vervanger["market_entity"] = reserve
        return vervanger, True

    async def _async_nordpool(self, settings: dict[str, Any], now: datetime, opruimen: bool = True) -> None:
        """De prijslijst van een sensor van de ingebouwde Nord Pool ophalen.

        Die integratie hangt geen lijst aan zijn sensoren, zoals Frank Energie,
        Zonneplan of de Nord Pool uit HACS dat doen; hij geeft hem alleen via
        de dienst `nordpool.get_prices_for_date`, in euro per MWh. De coach
        vraagt vandaag één keer, en morgen vanaf `NORDPOOL_MORGEN_VANAF` tot
        hij er is, hooguit eens per `NORDPOOL_OPNIEUW`. Welke config entry en
        welk gebied erbij horen zegt de entiteitregistratie.
        """
        contract = settings.get("contract") or {}
        if contract.get("type") != "dynamic":
            return
        dynamic = contract.get("dynamic") or {}
        sensoren = {
            dynamic.get("all_in_entity"), dynamic.get("market_entity"), dynamic.get("fallback_entity")
        } - {None, ""}
        # Een controle van een contract dat nog niet is opgeslagen (v0.129.0)
        # haalt erbij, maar gooit de lijsten van het echte contract niet weg.
        for entity_id in list(self._nordpool) if opruimen else []:
            if entity_id not in sensoren:
                self._nordpool.pop(entity_id, None)
        for entity_id in sorted(sensoren):
            bron = self._nordpool_bron(entity_id)
            if bron is None:
                continue
            state = self.hass.states.get(entity_id)
            if state is not None and _prijsrijen(state.attributes):
                continue
            entry_id, gebied, munt = bron
            vandaag = now.date()
            dagen = [vandaag] + ([vandaag + timedelta(days=1)] if now.hour >= NORDPOOL_MORGEN_VANAF else [])
            cache = self._nordpool.setdefault(entity_id, {})
            for dag in list(cache):
                if dag < (vandaag - timedelta(days=1)).isoformat():
                    cache.pop(dag, None)
            for dag in dagen:
                sleutel = dag.isoformat()
                if cache.get(sleutel):
                    continue
                vorige = self._nordpool_gevraagd.get((entity_id, sleutel))
                if vorige is not None and now - vorige < NORDPOOL_OPNIEUW:
                    continue
                self._nordpool_gevraagd[(entity_id, sleutel)] = now
                rijen = await self._async_nordpool_vraag(entry_id, gebied, munt, sleutel)
                if rijen:
                    cache[sleutel] = rijen
                    # Het wachten is voor een dag die er nog niet is, niet
                    # voor een die binnen is.
                    self._nordpool_gevraagd.pop((entity_id, sleutel), None)

    async def _async_nordpool_vraag(self, entry_id: str, gebied: str, munt: str, dag: str) -> list[dict[str, Any]]:
        """De prijzen van één dag bij de ingebouwde Nord Pool, in euro per kWh.

        Leeg als de dienst niets geeft; dan vraagt de coach het later nog eens.
        """
        try:
            antwoord = await self.hass.services.async_call(
                NORDPOOL_DOMEIN, "get_prices_for_date",
                {"config_entry": entry_id, "date": dag, "areas": [gebied], "currency": munt},
                blocking=True, return_response=True,
            )
        except Exception:  # noqa: BLE001 - dan straks nog eens
            _LOGGER.debug("Nord Pool gaf geen prijzen voor %s", dag, exc_info=True)
            return []
        rijen = []
        for rij in (antwoord or {}).get(gebied) or []:
            try:
                rijen.append({"start": rij["start"], "end": rij["end"], "value": float(rij["price"]) / 1000.0})
            except (KeyError, TypeError, ValueError):
                continue
        return rijen

    async def _async_marktprijzen(self, entity_id: str, van: date, tot: date) -> dict[datetime, float]:
        """De kale marktprijs per kwartier over voorbije dagen (v0.130.1).

        Voor het opnieuw uitrekenen van "Opgeleverd": de ingebouwde Nord Pool
        geeft met zijn dienst ook dagen die voorbij zijn, en een prijssensor
        heeft niet altijd een statistiek in Home Assistant. {lokaal begin van het
        kwartier: euro per kWh}; een uurprijs geldt voor alle vier zijn
        kwartieren. Leeg als het geen sensor van de ingebouwde Nord Pool is.
        """
        bron = self._nordpool_bron(entity_id) if entity_id else None
        if bron is None:
            return {}
        entry_id, gebied, munt = bron
        uit: dict[datetime, float] = {}
        dag = van
        while dag <= tot:
            for rij in await self._async_nordpool_vraag(entry_id, gebied, munt, dag.isoformat()):
                begin, eind = dt_util.parse_datetime(str(rij["start"])), dt_util.parse_datetime(str(rij["end"]))
                if begin is None or eind is None:
                    continue
                t = dt_util.as_local(begin).replace(tzinfo=None)
                eind_lokaal = dt_util.as_local(eind).replace(tzinfo=None)
                while t < eind_lokaal:
                    uit[t] = rij["value"]
                    t += timedelta(minutes=15)
            dag += timedelta(days=1)
        return uit

    def _nordpool_bron(self, entity_id: str) -> tuple[str, str, str] | None:
        """Config entry, gebied en munt van een sensor van de ingebouwde Nord Pool."""
        try:
            from homeassistant.helpers import entity_registry as er

            rij = er.async_get(self.hass).async_get(entity_id)
        except Exception:  # noqa: BLE001 - zonder registratie geen Nord Pool
            return None
        if rij is None or getattr(rij, "platform", None) != NORDPOOL_DOMEIN or not rij.config_entry_id:
            return None
        entry = self.hass.config_entries.async_get_entry(rij.config_entry_id)
        if entry is None:
            return None
        # Het gebied staat vooraan in de unieke id van de sensor ("NL-current_price"),
        # en de gebieden van de entry in zijn gegevens.
        uniek = str(getattr(rij, "unique_id", "") or "")
        gebieden = [str(g) for g in (entry.data or {}).get("areas") or []] or [uniek.split("-")[0]]
        gebied = next((g for g in gebieden if uniek.lower().startswith(g.lower() + "-")), gebieden[0])
        if not gebied:
            return None
        return rij.config_entry_id, gebied, str((entry.data or {}).get("currency") or "EUR")

    def _slots(self, entity_id: str | None, interval: str = "hour") -> dict[datetime, tuple[datetime, float]]:
        """De blokken uit een prijsentiteit, op begintijd.

        Een blok zonder eindtijd loopt tot het volgende blok; het laatste blok
        is even lang als het blok ervoor, en zonder blok ervoor zo lang als
        het contract zegt. Dezelfde regel als `priceForecast` in data-source.js.
        """
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            return {}

        rijen = _prijsrijen(state.attributes)
        if not rijen and entity_id in self._nordpool:
            # De ingebouwde Nord Pool: de lijst die zijn dienst gaf.
            dagen = self._nordpool[entity_id]
            rijen = _prijsrijen({"raw_today": [rij for dag in sorted(dagen) for rij in dagen[dag]]})
        rijen = sorted(rijen, key=lambda r: r[0])
        vast = timedelta(minutes=15 if interval == "quarter" else 60)
        uit: dict[datetime, tuple[datetime, float]] = {}
        for i, (start, end, price) in enumerate(rijen):
            if end is None:
                if i + 1 < len(rijen):
                    end = rijen[i + 1][0]
                elif i > 0:
                    end = start + (start - rijen[i - 1][0])
                else:
                    end = start + vast
            if end <= start:
                continue
            _naast_elkaar(uit, dt_util.as_local(start).replace(tzinfo=None), dt_util.as_local(end).replace(tzinfo=None), price)
        return uit

    @staticmethod
    def _salderen(contract: dict[str, Any], now: datetime | None = None) -> bool:
        """Of er op dit moment nog gesaldeerd wordt.

        Het vinkje van de klant én de datum. De regeling loopt af op
        `NETTING_ENDS`, en zonder die grens zou de coach na de jaarwisseling
        maandenlang een belastingteruggave blijven inrekenen die niet meer
        bestaat. Het vinkje blijft staan; het telt alleen niet meer mee.
        """
        if not contract.get("netting") or contract.get("country") == "PT":
            return False
        vandaag = dt_util.as_local(now or dt_util.utcnow()).date()
        return vandaag < NETTING_ENDS

    def vooruitblik(self, settings: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        """Wat er de komende uren gebeurt, per uur, voor de vooruitblik op het overzicht (v0.133.0).

        De eigenaar op 19-10-2026, bij voorbeelden van andere apps: "Dan zie je
        in één oogopslag wat er toekomstig gaat gebeuren, en krijg je een
        visuele bevestiging of je ingestelde prioriteiten ook kloppen." Er wordt
        hier niets nieuws uitgerekend: de prijzen, de zonverwachting en het
        huisverbruik waar de coach zelf mee plant, en per apparaat het plan dat
        hij al had. Wat hij niet weet staat er niet in; een airco heeft geen
        plan, alleen wat hij nu doet.

        Tot het eind van de bekende prijzen, minstens twaalf uur en hooguit tot
        morgen 24:00. Momenten als tekst, lokaal en zonder tijdzone, zoals de
        rest van de toestand.
        """
        nu = _moment(now)
        van = nu.replace(minute=0, second=0, microsecond=0)
        prijzen = self._prices(settings, nu)
        einde = max([r["end"] for r in prijzen] + [van + timedelta(hours=12)])
        einde = min(einde, datetime.combine(nu.date() + timedelta(days=2), time()))
        uren: list[datetime] = []
        stap = van
        while stap < einde:
            uren.append(stap)
            stap += timedelta(hours=1)

        def lees(waarde: Any) -> datetime | None:
            moment = waarde if isinstance(waarde, datetime) else _tijdstip(waarde)
            if moment is not None and moment.tzinfo is not None:
                moment = dt_util.as_local(moment).replace(tzinfo=None)
            return moment

        def blok(start: datetime | str, eind: datetime | str, kwh: float | None, **meer) -> dict | None:
            a, b = lees(start), lees(eind)
            if a is None or b is None or b <= van or a >= einde or b <= a:
                return None
            uur = (b - a).total_seconds() / 3600
            return {"start": a.isoformat(), "end": b.isoformat(),
                    "kw": None if kwh is None else round(kwh / uur, 3), **meer}

        apparaten: list[dict[str, Any]] = []
        for device in settings.get("devices") or []:
            device_id = device.get("id") or ""
            soort = device.get("type")
            st = self.state.get(device_id) or {}
            blokken: list[dict | None] = []
            if soort == "laadpaal":
                for b in (st.get("plan_ahead") or {}).get("blocks") or []:
                    laadt = bool(b.get("charging")) and float(b.get("kwh") or 0) > 0
                    uur = blok(b.get("start"), b.get("end"), float(b.get("kwh") or 0) if laadt else 0.0,
                               zon_kw=None, wat="laadt" if laadt else "wacht", why=b.get("why") or "")
                    if uur is not None and laadt:
                        duur = (lees(b["end"]) - lees(b["start"])).total_seconds() / 3600
                        uur["zon_kw"] = round(float(b.get("solar_kwh") or 0) / duur, 3)
                        uur["accu_kw"] = round(float(b.get("accu_kwh") or 0) / duur, 3)
                    blokken.append(uur)
            elif soort == "thuisbatterij":
                for u in (self._batterij.get(device_id) or {}).get("uren") or []:
                    blokken.append(blok(u.start, u.end, u.kwh, wat=t(STAND_NAMEN.get(u.stand, u.stand)),
                                        stand=u.stand, soc=round(u.soc), net_kw=None))
            elif soort == "boiler":
                for b in st.get("blokken") or []:
                    blokken.append(blok(b.get("start"), b.get("end"), float(b.get("kwh") or 0), wat=t("verwarmt")))
            elif soort in PROGRAMMA_TYPES:
                programma = (self._programma.get(device_id) or {}).get("programma")
                kwh = programma.kwh if programma is not None and programma.kwh_bekend else None
                if st.get("running") and st.get("started_at") and st.get("ends_at"):
                    blokken.append(blok(st["started_at"], st["ends_at"], None, wat=t("draait")))
                elif st.get("starts_at") and programma is not None:
                    begin = lees(st["starts_at"])
                    if begin is not None:
                        blokken.append(blok(begin, begin + timedelta(minutes=programma.minutes), kwh,
                                            wat=t("start, {programma}", programma=t(programma.label))
                                            if programma.label else t("start")))
            elif soort == "airco":
                if st.get("on"):
                    vermogen = st.get("power_w") or st.get("vermogen_w")
                    blokken.append(blok(van, van + timedelta(hours=1),
                                        None if vermogen is None else float(vermogen) / 1000.0, wat=t("aan")))
            else:
                continue
            gevonden = [b for b in blokken if b is not None]
            # Een laadpaal zonder auto staat er niet in (v0.141.0, "niet weergeven of meenemen").
            if soort == "laadpaal" and st.get("rule") == "disconnected":
                continue
            if gevonden or soort in ("laadpaal", "thuisbatterij", "boiler") and device.get("controllable"):
                apparaten.append({"id": device_id, "type": soort, "blokken": gevonden})

        _regels, zon_rang = self._zon_voorrang(settings)
        plan_rang = self._plan_voorrang(settings)
        return {
            "van": van.isoformat(),
            "tot": einde.isoformat(),
            "prijzen": [
                {"start": r["start"].isoformat(), "end": r["end"].isoformat(), "price": r["price"], "feed_in": r["feed_in"]}
                for r in prijzen if r["end"] > van and r["start"] < einde
            ],
            # kWh per uur, op het begin van het uur.
            "zon": {u.isoformat(): round(self._zon_kwh[u], 3) for u in uren if u in self._zon_kwh},
            "zon_geschat": bool(self._zon_geschat),
            # Het huis zonder de apparaten die de coach stuurt: de mediaan per uur
            # van de afgelopen week (`_async_huisverbruik`).
            "huis": {u.isoformat(): round(self._huis_kwh[u.hour], 3) for u in uren if u.hour in self._huis_kwh},
            "apparaten": apparaten,
            "voorrang_zon": [d for d, _ in sorted(zon_rang.items(), key=lambda x: x[1])],
            "voorrang_plan": [d for d, _ in sorted(plan_rang.items(), key=lambda x: x[1])],
        }

    def _prices(self, settings: dict[str, Any], now: datetime | None = None) -> list[dict]:
        """De prijslijst, met per blok wat het kost én wat teruglevering opbrengt.

        Uit dezelfde entiteit die het paneel tekent, zodat de twee het nooit
        oneens kunnen zijn over wat een uur kost.

        Wat teruglevering opbrengt is de kale marktprijs min de kosten die de
        leverancier daarover rekent. Bij een all-in prijssensor zit die kale
        prijs er niet meer in, en dan is hij er ook niet uit te halen. Daarom mag
        de marktprijssensor er los bij: hij is dan alleen voor de teruglevering,
        en zonder die sensor blijft de opbrengst gewoon onbekend. Onbekend is
        hier beter dan aangenomen, want op een aangenomen bedrag zou de coach
        gaan bijkopen.
        """
        contract = settings.get("contract") or {}
        if contract.get("country") == "PT":
            return self._pt_rijen(contract, now)
        if contract.get("type") != "dynamic":
            return []

        # De prijsbron die er nu is: de eigen, en anders de reserve (v0.101.3).
        dynamic, _ = self._prijsbron(contract.get("dynamic") or {}, now)
        all_in = dynamic.get("source") == "all_in"
        salderen = self._saldeert(contract)
        # De opslag van de leverancier zit wel in wat je betaalt en niet in wat
        # je terugkrijgt. Bij salderen streept de energiebelasting weg tegen die
        # bij afname, maar die opslag niet: die betaal je per ingekochte kWh en
        # krijg je nergens terug. Zonder die aftrek stond de terugleveropbrengst
        # er ruim twee cent te hoog in en leek eigen zon gebruiken even duur als
        # het weggeven ervan. Gevonden op 27-08-2026, uit een eigen energienota.
        # De som staat sinds v0.129.0 in `prijsopbouw.terug`.

        interval = str(dynamic.get("interval") or "hour")
        # Dezelfde sensor twee keer zegt niets over teruglevering: een all-in
        # prijs als marktprijs lezen maakt van elke teruggeleverde kWh een die
        # de volle inkoopprijs opbrengt, en daar plant de coach dan op. In de
        # eerste woning stond dat zo ingevuld (22-09-2026). Dan is de opbrengst
        # onbekend, en dat is beter dan een verzonnen bedrag.
        markt_entity = dynamic.get("market_entity")
        if all_in and markt_entity and markt_entity == dynamic.get("all_in_entity"):
            markt_entity = None
        markt = self._slots(markt_entity, interval)
        inkoop = self._slots(dynamic.get("all_in_entity"), interval) if all_in else markt
        if not inkoop:
            return []

        rows: list[dict] = []
        # Voor een bonus die alleen overdag geldt (v0.129.0): waar de woning ligt.
        lat = getattr(self.hass.config, "latitude", None)
        lon = getattr(self.hass.config, "longitude", None)
        zone = dt_util.get_default_time_zone()
        for start, (end, prijs) in inkoop.items():
            # De kale prijs van dit blok: bij een all-in prijs per uur het
            # gemiddelde van de marktkwartieren erin. Tot v0.129.0 was dat het
            # kwartier dat op het hele uur begon.
            kaal = prijsopbouw.gemiddeld(markt, start, end) if all_in else prijs
            if not all_in:
                prijs = self._all_in(prijs, dynamic)
            # Salderen betekent dat een teruggeleverde kWh wegstreept tegen een
            # ingekochte: de inkoopprijs min de opslag van je leverancier, want
            # die opslag hangt aan de afname en niet aan de kWh. Daar is geen
            # marktprijssensor voor nodig, behalve voor een bonus in procenten.
            dag = prijsopbouw.overdag(start.replace(tzinfo=zone), end.replace(tzinfo=zone), lat, lon)
            terug = prijsopbouw.terug(kaal, prijs, dynamic, salderen, dag)["bedrag"]
            # Wat een kWh teruglevering aan schaal kost (v0.137.0, `_async_schaal`).
            schaal = self._schaal_per_kwh(settings, start)
            if schaal and terug is not None:
                terug = _minder(terug, schaal)

            rows.append({"start": start, "end": end, "price": prijs, "feed_in": terug})
        # Verder dan de lijst reikt weet de coach niets, en dat hoort zo.
        # Er stond hier op 04-09-2026 een middag lang een geschatte dag
        # achteraan (de prijzen van vandaag nog eens voor morgen); de eigenaar wil
        # geen gegokte prijzen. Reikt de lijst niet tot de klaar-tijd, dan
        # laadt hij tot die tijd alleen op zon. Zie `alleen_zon` in planner.py.
        return sorted(rows, key=lambda item: item["start"])

    def _pt_rijen(self, contract: dict[str, Any], now: datetime | None = None) -> list[dict]:
        """De prijslijst van een Portugees contract, per kwartier, twee dagen vooruit (v0.137.0).

        Uit de tijdvakken van de ERSE in de tijd van Lissabon (`tarifas.periodo`), dus
        ook goed als Home Assistant op een andere tijdzone staat. Per kwartier, want bij
        tri-horário en ciclo semanal begint een tijdvak soms op een kwart of een half uur.
        De terugleverprijs is wat het verkoopcontract geeft; bij OMIE de prijs uit de
        sensor van dat kwartier. Leeg zolang er een prijs ontbreekt: dan kent de coach
        het contract niet, en rekent hij niet met een verzonnen bedrag.
        """
        pt = contract.get("pt") or {}
        zone = dt_util.get_default_time_zone()
        nu = _moment(now)
        begin = nu.replace(minute=nu.minute - nu.minute % 15, second=0, microsecond=0)
        start_utc = begin.replace(tzinfo=zone).astimezone(timezone.utc)
        e = pt.get("excedente") or {}
        omie = self._slots(e.get("omie_entity")) if e.get("modo") == "omie" and e.get("omie_entity") else {}
        rijen: list[dict] = []
        for i in range(48 * 4):
            s_utc = start_utc + timedelta(minutes=15 * i)
            start = s_utc.astimezone(zone).replace(tzinfo=None)
            einde = (s_utc + timedelta(minutes=15)).astimezone(zone).replace(tzinfo=None)
            prijs = tarifas.preco(pt, tarifas.periodo(s_utc, pt.get("tarifa"), pt.get("ciclo")))
            if prijs is None:
                return []
            markt = next((p for s, (eind, p) in omie.items() if s <= start < eind), None)
            rijen.append({"start": start, "end": einde, "price": prijs, "feed_in": tarifas.terug(pt, markt)})
        # Het uur dat bij de wintertijd twee keer komt (v0.139.1): op de lokale klok één rij
        # die twee echte kwartieren duurt, zoals `_naast_elkaar` bij een prijssensor. Tot dan
        # stond elk kwartier van dat uur er twee keer, en één met een einde vóór zijn begin.
        samen: dict[datetime, dict] = {}
        for rij in rijen:
            oud = samen.get(rij["start"])
            if oud is None:
                samen[rij["start"]] = rij
                continue
            oud["end"] = max(oud["end"], rij["end"])
            oud["price"] = (oud["price"] + rij["price"]) / 2
            oud["feed_in"] = None if oud["feed_in"] is None or rij["feed_in"] is None else (oud["feed_in"] + rij["feed_in"]) / 2
        return sorted(samen.values(), key=lambda rij: rij["start"])

    def _sun(self, settings: dict[str, Any]) -> Sun:
        """De zonverwachting, voor zover die is ingevuld.

        De uurwaarden mogen in kWh over dat uur binnenkomen of als het gemiddelde
        vermogen over dat uur; welke van de twee het is staat in de eenheid van
        de sensor zelf. Zie `hour_to_watts` in units.py voor wat er misging toen
        dat niet werd nagekeken. De rest van de coach rekent in watt.
        """
        bron = (settings.get("sources") or {}).get("solar_forecast") or {}

        def uur(sleutel: str) -> float | None:
            entity_id = bron.get(sleutel)
            return hour_to_watts(_number(self.hass, entity_id), _unit(self.hass, entity_id))

        return Sun(
            now_w=uur("this_hour"),
            next_w=uur("next_hour"),
            remaining_kwh=_kwh(self.hass, bron.get("remaining_today")),
        )

    def _piek(self, settings: dict[str, Any]) -> datetime | None:
        """Wanneer het dak vandaag zijn hoogste punt haalt, als dat bekend is.

        Alleen om de schatting hieronder een vorm te geven. Elke zonvoorspeller
        levert dit als een tijdstip; staat er niets, dan wordt er niet geschat.
        """
        bron = (settings.get("sources") or {}).get("solar_forecast") or {}
        rauw = _text(self.hass, bron.get("peak_today"))
        moment = dt_util.parse_datetime(rauw) if rauw else None
        return None if moment is None else _moment(moment)

    async def _async_jaarsaldo(self, settings: dict[str, Any], now: datetime) -> None:
        """Of het huis over de afrekenperiode meer teruglevert dan het afneemt (v0.134.0).

        Salderen streept een teruggeleverde kWh weg tegen een afgenomen, maar
        alleen tot aan wat je afneemt, en per afrekenperiode: van de begindatum
        tot de einddatum van de jaarafrekening, ook over een nieuw contract
        heen. Op een jaarafrekening van half september tot half september die
        de eigenaar op 19-10-2026 liet zien, ging de saldering zo over het oude
        en het nieuwe contract samen. Wat er daarna nog over is, is de
        vergoeding na saldering waard. De regeling stopt op `NETTING_ENDS`, dus
        de periode die nu telt loopt van het begin van de afrekenperiode
        (`billing_start` bij Contract) tot die dag.

        Wat er al was komt uit de kWh-tellers van de meter (`meters` onder
        Installatie), via de statistiek van Home Assistant; wat er tot
        `NETTING_ENDS` nog bij komt uit dezelfde dagen een jaar eerder. Zonder
        begindatum, zonder tellers of zonder dat jaar ervoor is het onbekend,
        en telt het vinkje salderen zoals het staat.

        In v0.133.3 (niet uitgebracht) was dit het afgelopen jaar. In de woning
        van de eigenaar scheelden afname en teruglevering daarover op 19-10-2026
        nog geen 0,2 procent, met de zomer van het vorige contract erin: een
        schakelaar die elke dag kon omslaan, over een periode die niet telt.
        """
        if self._jaarsaldo_tot is not None and now < self._jaarsaldo_tot:
            return
        self._jaarsaldo_tot = now + JAARSALDO_VERVERSEN
        self._jaarsaldo = None
        contract = settings.get("contract") or {}
        vandaag = now.date()
        if not contract.get("netting") or vandaag >= NETTING_ENDS:
            return
        begin = _afrekenstart(contract.get("billing_start"), vandaag)
        meters = (settings.get("sources") or {}).get("meters") or {}
        afname_ids = [e for e in (meters.get("import_low"), meters.get("import_high")) if e]
        terug_ids = [e for e in (meters.get("export_low"), meters.get("export_high")) if e]
        if begin is None or not afname_ids or not terug_ids:
            return

        zone = dt_util.get_default_time_zone()

        def middernacht(dag: date) -> datetime:
            return dt_util.as_utc(datetime.combine(dag, time(0)).replace(tzinfo=zone))

        # Tot vandaag gemeten, en vanaf vandaag tot het einde van salderen
        # dezelfde dagen een jaar eerder.
        al = (middernacht(begin), middernacht(vandaag))
        rest = (middernacht(_jaar_eerder(vandaag)), middernacht(_jaar_eerder(NETTING_ENDS)))
        rijen: list[dict] = []
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import statistics_during_period

            ids = set(afname_ids + terug_ids)
            for van, tot in (al, rest):
                if van >= tot:
                    rijen.append({})
                    continue
                rijen.append(
                    await get_instance(self.hass).async_add_executor_job(
                        statistics_during_period, self.hass, van, tot, ids, "day",
                        {"energy": "kWh"}, {"change"},
                    ) or {}
                )
        except Exception as fout:  # noqa: BLE001 - zonder recorder geen balans
            _LOGGER.debug("kon de statistiek van de meter niet lezen: %s", fout)
            return

        def som(deel: dict, lijst: list[str]) -> float:
            return round(sum(float(r.get("change") or 0.0) for e in lijst for r in deel.get(e) or []), 1)

        def gedekt(deel: dict, van: datetime, tot: datetime) -> bool:
            # De statistiek moet het begin van het venster halen: een meter die
            # pas sinds gisteren meetelt zegt niets over vorig jaar.
            if van >= tot:
                return True
            eerste = None
            for e in afname_ids + terug_ids:
                for r in deel.get(e) or []:
                    moment = r.get("start")
                    if isinstance(moment, (int, float)):
                        moment = datetime.fromtimestamp(moment, tz=timezone.utc)
                    if isinstance(moment, datetime) and (eerste is None or moment < eerste):
                        eerste = moment
            return eerste is not None and eerste <= van + timedelta(days=1)

        self._jaarsaldo = {
            "van": begin.isoformat(),
            "afname": som(rijen[0], afname_ids),
            "terug": som(rijen[0], terug_ids),
            "afname_rest": som(rijen[1], afname_ids),
            "terug_rest": som(rijen[1], terug_ids),
            "compleet": gedekt(rijen[0], *al) and gedekt(rijen[1], *rest),
        }

    async def _async_meterkwh(
        self, settings: dict[str, Any], van: date, tot: date
    ) -> tuple[float, float, bool] | None:
        """Afname en teruglevering in kWh over [van, tot), uit de kWh-tellers van de meter (v0.135.0).

        Via de statistiek van Home Assistant, per dag, zoals `_async_jaarsaldo`.
        Met of de statistiek het begin haalt: een meter die pas later meetelt
        zegt niets over het begin. None zonder tellers of zonder recorder.
        """
        meters = (settings.get("sources") or {}).get("meters") or {}
        afname_ids = [e for e in (meters.get("import_low"), meters.get("import_high")) if e]
        terug_ids = [e for e in (meters.get("export_low"), meters.get("export_high")) if e]
        if not afname_ids or not terug_ids:
            return None
        if van >= tot:
            return 0.0, 0.0, True
        zone = dt_util.get_default_time_zone()
        begin = dt_util.as_utc(datetime.combine(van, time(0)).replace(tzinfo=zone))
        eind = dt_util.as_utc(datetime.combine(tot, time(0)).replace(tzinfo=zone))
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import statistics_during_period

            rijen = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period, self.hass, begin, eind, set(afname_ids + terug_ids), "day",
                {"energy": "kWh"}, {"change"},
            ) or {}
        except Exception as fout:  # noqa: BLE001 - zonder recorder geen tellers
            _LOGGER.debug("kon de statistiek van de meter niet lezen: %s", fout)
            return None

        def som(ids: list[str]) -> float:
            return round(sum(float(r.get("change") or 0.0) for e in ids for r in rijen.get(e) or []), 1)

        eerste = None
        for e in afname_ids + terug_ids:
            for r in rijen.get(e) or []:
                moment = r.get("start")
                if isinstance(moment, (int, float)):
                    moment = datetime.fromtimestamp(moment, tz=timezone.utc)
                if isinstance(moment, datetime) and (eerste is None or moment < eerste):
                    eerste = moment
        gedekt = eerste is not None and eerste <= begin + timedelta(days=1)
        return som(afname_ids), som(terug_ids), gedekt

    async def async_afrekening(
        self, settings: dict[str, Any], van: date, tot: date, now: datetime | None = None
    ) -> dict[str, Any]:
        """Salderen per afrekenperiode, en de schaal van de terugleverkosten, voor Historie (v0.135.0).

        Historie rekende per uur met het vinkje: elke teruggeleverde kWh als een
        gesaldeerde. Op de jaarafrekening van de eigenaar (19-10-2026) ging het
        anders: per afrekenperiode streept de teruglevering weg tegen de afname,
        en wat er daarna overblijft krijgt de vergoeding na saldering, naar rato
        over de contracten in die periode (29 kWh werd 27 maal de oude en 2 maal
        de nieuwe vergoeding, naar wat er onder elk contract terugging). Dus per
        periode het deel van de teruglevering dat wegstreept (`gesaldeerd`):
        de afname gedeeld door de teruglevering, hooguit één. Voor de periode van
        nu met wat er tot het einde van salderen nog komt, gemeten op dezelfde
        dagen een jaar eerder, zoals `_async_jaarsaldo`.

        En bij terugleverkosten in schalen de schaal van het contract: naar de
        teruglevering in het deel van de afrekenperiode onder dit contract, tot
        de einddatum van de schalen (`feed_in_scales_until`; leeg is de hele
        afrekenperiode), met het jaarbedrag gedeeld door 365 per dag. Van
        vorige contracten zijn de schalen niet bekend.

        Alleen met salderen aan, een begindatum (`billing_start`) en de tellers
        van de meter; anders leeg, en rekent Historie met het vinkje.
        """
        nu = _moment(now)
        vandaag = nu.date()
        contract = settings.get("contract") or {}
        uit: dict[str, Any] = {"perioden": [], "schaal": None}
        if not contract.get("netting"):
            return uit
        laatste_dag = min(vandaag, NETTING_ENDS - timedelta(days=1))
        start = _afrekenstart(contract.get("billing_start"), laatste_dag)
        if start is None:
            return uit

        # De perioden die [van, tot) raken, vanaf die van nu terug in de tijd.
        reeks: list[tuple[date, date]] = []
        p = start
        for _ in range(12):
            eind = min(_jaar_later(p), NETTING_ENDS)
            if p < tot and eind > van:
                reeks.append((p, eind))
            if p <= van:
                break
            p = _jaar_eerder(p)
        for p, eind in sorted(reeks):
            gemeten = await self._async_meterkwh(settings, p, min(eind, vandaag))
            if gemeten is None:
                return uit
            afname, terug, gedekt = gemeten
            afname_rest = terug_rest = 0.0
            if eind > vandaag:
                rest = await self._async_meterkwh(settings, _jaar_eerder(vandaag), _jaar_eerder(eind))
                if rest is None:
                    return uit
                afname_rest, terug_rest, gedekt_rest = rest
                gedekt = gedekt and gedekt_rest
            totaal_afname, totaal_terug = afname + afname_rest, terug + terug_rest
            uit["perioden"].append({
                "van": p.isoformat(), "tot": eind.isoformat(),
                "afname": afname, "terug": terug, "afname_rest": afname_rest, "terug_rest": terug_rest,
                "compleet": gedekt,
                "gesaldeerd": None if not gedekt else (
                    1.0 if totaal_terug <= 0 else round(min(1.0, totaal_afname / totaal_terug), 4)
                ),
            })

        velden = (contract.get("dynamic") if contract.get("type") == "dynamic" else contract.get("fixed")) or {}
        if velden.get("feed_in_costs_mode") == "schalen" and velden.get("feed_in_scales"):
            deel_van = max(start, _datum(contract.get("start")) or start)
            deel_tot = _jaar_later(start)
            tot_schaal = _datum(velden.get("feed_in_scales_until"))
            if tot_schaal is not None:
                deel_tot = min(deel_tot, tot_schaal)
            if deel_van < deel_tot:
                gemeten = await self._async_meterkwh(settings, deel_van, min(deel_tot, vandaag))
                rest = (await self._async_meterkwh(settings, _jaar_eerder(vandaag), _jaar_eerder(deel_tot))
                        if deel_tot > vandaag else (0.0, 0.0, True))
                if gemeten is not None and rest is not None:
                    kwh = round(gemeten[1] + rest[1], 1)
                    per_jaar = prijsopbouw.schaal_per_jaar(velden.get("feed_in_scales"), kwh) or 0.0
                    uit["schaal"] = {
                        "van": deel_van.isoformat(), "tot": deel_tot.isoformat(),
                        "terug": gemeten[1], "terug_rest": rest[1], "kwh": kwh,
                        "compleet": gemeten[2] and rest[2],
                        "per_jaar": round(per_jaar, 2), "per_dag": round(per_jaar / 365.0, 4),
                    }
        return uit

    def _netto_terug(self) -> bool | None:
        """Of het huis over de afrekenperiode meer teruglevert dan het afneemt (v0.134.0).

        Wat er al was plus wat er tot het einde van salderen nog bij komt. None
        als dat niet bekend is; zie `_async_jaarsaldo`.
        """
        s = self._jaarsaldo
        if not s or not s.get("compleet"):
            return None
        return s["terug"] + s["terug_rest"] > s["afname"] + s["afname_rest"]

    def _saldeert(self, contract: dict[str, Any], now: datetime | None = None) -> bool:
        """Of een teruggeleverde kWh nu wegstreept tegen een afgenomen (v0.133.3).

        Het vinkje en de datum (`_salderen`), en het huis levert over de
        afrekenperiode niet meer terug dan het afneemt. Anders is de volgende
        kWh die naar het net gaat er een boven het eigen verbruik, en geldt de
        vergoeding na saldering.
        """
        return self._salderen(contract, now) and self._netto_terug() is not True

    def _tarief(self, settings: dict[str, Any], now: datetime | None = None) -> Tariff:
        """`_tariff` met wat de coach van dit huis weet: levert het netto terug (v0.133.3),
        en wat een kWh teruglevering aan schaal kost (v0.137.0, `_schaal_per_kwh`)."""
        tarief = self._tariff(settings, self._saldeert(settings.get("contract") or {}, now), now)
        kosten = self._schaal_per_kwh(settings, now)
        if kosten and tarief.feed_in is not None:
            tarief = replace(tarief, feed_in=_minder(tarief.feed_in, kosten))
        return tarief

    def _schaal_per_kwh(self, settings: dict[str, Any], now: datetime | None = None) -> float:
        """Wat een kWh teruglevering nu aan schaal kost, of 0 (v0.137.0). Zie `_async_schaal`."""
        s = self._schaal
        if not s or not s.get("kosten_per_kwh"):
            return 0.0
        contract = settings.get("contract") or {}
        velden = (contract.get("dynamic") if contract.get("type") == "dynamic" else contract.get("fixed")) or {}
        if velden.get("feed_in_costs_mode") != "schalen":
            return 0.0
        if _moment(now).date().isoformat() >= str(s.get("tot") or ""):
            return 0.0
        return float(s["kosten_per_kwh"])

    async def _async_schaal(self, settings: dict[str, Any], now: datetime) -> None:
        """De schaal van de terugleverkosten die eraan komt, met en zonder thuisbatterij (v0.137.0).

        De eigenaar op 19-10-2026, toen bleek dat de batterij met salderen per kWh
        niets opbracht: "Dus je zegt nu eigenlijk dat iedereen die een batterij
        heeft gekocht het voor niks heeft gekocht?" Niet helemaal: een schaal hangt
        aan wat er terugging, en wat de batterij opnam ging niet terug. Dit telt
        dat: de teruglevering van de periode (`async_afrekening`, gemeten plus
        dezelfde dagen vorig jaar), en daarbovenop wat de batterijen per kwartier
        opnamen terwijl het huis terugleverde (`_async_accu_vermeden`).

        En wat een kWh teruglevering nu kost (`kosten_per_kwh`): komt het huis
        volgens die verwachting in een duurdere schaal dan waar het nu staat, dan
        is dat verschil het werk van wat er nog teruggaat. Naar rato over de dagen
        van de periode, zoals Historie het jaarbedrag telt, en verdeeld over de
        teruglevering die er nog verwacht wordt. Blijft het huis in dezelfde
        schaal, dan kost een kWh niets. `_tarief` en `_prices` trekken het van de
        terugleverprijs af, zodat de coach de zon dan liever zelf gebruikt.
        Eens per dag.
        """
        if self._schaal_tot is not None and now < self._schaal_tot:
            return
        self._schaal_tot = now + JAARSALDO_VERVERSEN
        self._schaal = None
        contract = settings.get("contract") or {}
        velden = (contract.get("dynamic") if contract.get("type") == "dynamic" else contract.get("fixed")) or {}
        if velden.get("feed_in_costs_mode") != "schalen" or not velden.get("feed_in_scales"):
            return
        try:
            s = (await self.async_afrekening(settings, now.date(), now.date() + timedelta(days=1), now)).get("schaal")
        except Exception:  # noqa: BLE001 - zonder schaal rekent hij gewoon door
            _LOGGER.exception("kon de schaal van de terugleverkosten niet uitrekenen")
            return
        if not s or not s.get("compleet"):
            return
        van, tot = date.fromisoformat(s["van"]), date.fromisoformat(s["tot"])
        if now.date() >= tot:
            return
        tabel = velden["feed_in_scales"]
        nu = prijsopbouw.schaal_per_jaar(tabel, float(s["terug"])) or 0.0
        straks = prijsopbouw.schaal_per_jaar(tabel, float(s["kwh"])) or 0.0
        rest = float(s.get("terug_rest") or 0.0)
        kosten = (straks - nu) * (tot - van).days / 365.0 / rest if rest > 0 and straks > nu else 0.0
        vermeden = await self._async_accu_vermeden(settings, van, min(tot, now.date()))
        self._schaal = {
            **s,
            "rij": prijsopbouw.schaal_rij(tabel, float(s["kwh"])),
            "kosten_per_kwh": round(kosten, 4),
            "accu_kwh": vermeden,
            "zonder_accu": None if vermeden is None else {
                "kwh": round(float(s["kwh"]) + vermeden, 1),
                "rij": prijsopbouw.schaal_rij(tabel, float(s["kwh"]) + vermeden),
            },
        }

    async def _async_accu_vermeden(self, settings: dict[str, Any], van: date, tot: date) -> float | None:
        """Hoeveel teruglevering de thuisbatterijen in [van, tot) tegenhielden, in kWh (v0.137.0).

        Per kwartier uit de eigen opslag: het net met en zonder wat de batterijen
        deden. Zonder batterij was het net `net - batterij` geweest (laden telt
        positief); wat er dan meer naar buiten ging, ging nu de batterij in. None
        zonder batterij of zonder kwartieren.
        """
        accus = [d for d in settings.get("devices") or [] if d.get("type") == "thuisbatterij"]
        if not accus or van >= tot:
            return None
        bronnen = settings.get("sources") or {}
        getekend = bronnen.get("grid_mode") == "signed"
        net_ids = [bronnen.get("grid_signed")] if getekend else [bronnen.get("grid_import"), bronnen.get("grid_export")]
        bat_ids: list[str | None] = []
        for d in accus:
            eigen = d.get("entities") or {}
            bat_ids += [d.get("entity"), eigen.get("charge_power"), eigen.get("discharge_power")]
        ids = sorted({e for e in net_ids + bat_ids if e})
        kwartieren = await self._async_kwartieren(
            ids, datetime(van.year, van.month, van.day), datetime(tot.year, tot.month, tot.day)
        )
        per = {e: {int(r["start"]): r for r in kwartieren.get(e, [])} for e in ids}

        def gemiddeld(entity_id: str | None, moment: int) -> float | None:
            r = per.get(entity_id, {}).get(moment) if entity_id else None
            return None if r is None or r.get("gemiddeld") is None else float(r["gemiddeld"])

        totaal, gezien = 0.0, False
        for moment in sorted({t for e in ids for t in per.get(e, {})}):
            if getekend:
                g = gemiddeld(bronnen.get("grid_signed"), moment)
                net_w = None if g is None else (-g if bronnen.get("grid_signed_invert") else g)
            else:
                invoer, export = gemiddeld(bronnen.get("grid_import"), moment), gemiddeld(bronnen.get("grid_export"), moment)
                net_w = None if invoer is None and export is None else (invoer or 0.0) - (export or 0.0)
            if net_w is None:
                continue
            bat_w = 0.0
            for d in accus:
                eigen = d.get("entities") or {}
                getal = gemiddeld(d.get("entity"), moment)
                if getal is not None:
                    bat_w += -getal if (d.get("battery") or {}).get("power_invert") else getal
                else:
                    laden, ontladen = gemiddeld(eigen.get("charge_power"), moment), gemiddeld(eigen.get("discharge_power"), moment)
                    bat_w += (laden or 0.0) - (ontladen or 0.0)
            gezien = True
            totaal += (max(0.0, -(net_w - bat_w)) - max(0.0, -net_w)) * 0.25 / 1000.0
        return round(totaal, 1) if gezien else None

    async def _async_huisverbruik(self, settings: dict[str, Any], now: datetime) -> None:
        """Wat het huis zelf gebruikt, per uur van de dag, uit de eigen opslag.

        Dit is het tweede getal dat de vergelijking nodig heeft. De
        zonverwachting zegt wat het dak gaat leveren; pas als je weet wat het
        huis daarvan zelf opmaakt, weet je hoeveel er voor de auto overblijft.

        Uit `archive.py`, en dus uit de kwartieren die de coach zelf al bijhoudt:
        `zon + inkoop - teruglevering - alle apparaten`. Geen nieuwe sensor, geen
        binnenkant van Home Assistant, en bij elke klant dezelfde som. Alles staat
        daar in watt, wat de sensor zichzelf ook noemt.

        **De mediaan en niet het gemiddelde.** De eigenaar koos die op 30-08-2026 nadat
        ik hem de drie mogelijkheden voorlegde. In de klantwoning zei het gemiddelde
        voor dat uur 1,63 kWh terwijl het huis er op dat moment 0,5 gebruikte:
        één keer wassen tilt een gemiddelde over dagen heen op. De mediaan is
        daar niet gevoelig voor, en de werkelijke sturing loopt hoe dan ook op de
        meting van dat moment. De verwachting bepaalt alleen wélke uren gekozen
        worden.
        """
        if self._huis_tot is not None and now < self._huis_tot:
            return
        self._huis_tot = now + HUIS_VERVERSEN

        bronnen = settings.get("sources") or {}
        zonnen_ids = zonsensoren(settings)
        netten = _netmeters(bronnen)
        # Elk apparaat met het teken waarmee het van het huisverbruik af gaat.
        # Een thuisbatterij telt twee kanten op: wat hij laadt is geen
        # huisverbruik, en wat hij ontlaadt heeft het huis wel gebruikt.
        tekens: list[tuple[str, float]] = []
        for device in settings.get("devices") or []:
            if device.get("type") == "thuisbatterij":
                extra = device.get("entities") or {}
                om = -1.0 if (device.get("battery") or {}).get("power_invert") else 1.0
                if device.get("entity"):
                    tekens.append((device["entity"], om))
                else:
                    if extra.get("charge_power"):
                        tekens.append((extra["charge_power"], 1.0))
                    if extra.get("discharge_power"):
                        tekens.append((extra["discharge_power"], -1.0))
            elif device.get("entity"):
                tekens.append((device["entity"], 1.0))
        apparaten = [naam for naam, _ in tekens]
        wanted = [e for e in [*zonnen_ids, *netten, *apparaten] if e]
        if not wanted:
            return

        einde = dt_util.utcnow()
        try:
            rijen = await async_get_archive(self.hass).async_lees(
                wanted, einde - HUIS_VENSTER, einde
            )
        except Exception:  # noqa: BLE001 - zonder geschiedenis rekent hij gewoon zonder
            _LOGGER.exception("kon de eigen geschiedenis niet lezen voor het huisverbruik")
            return

        def kwartieren(entity_id: str | None) -> dict[int, float]:
            if not entity_id:
                return {}
            return {
                int(rij["start"]): float(rij.get("gemiddeld") or 0.0)
                for rij in rijen.get(entity_id, [])
            }

        # Meer omvormers: per kwartier bij elkaar opgeteld.
        zonnen: dict[int, float] = {}
        for zon_id in zonnen_ids:
            for stempel, watt in kwartieren(zon_id).items():
                zonnen[stempel] = zonnen.get(stempel, 0.0) + watt
        net_reeksen = {naam: kwartieren(naam) for naam in netten}
        apparaat = [(kwartieren(naam), teken) for naam, teken in tekens]

        # Het net per kwartier volgens `grid_mode`, met de andere meter voor de kwartieren waar die
        # niets zegt, en het vinkje omgekeerd erbij (`_net_afname`, v0.170.0). Een kwartier zonder net
        # telt niet mee: als nul maakte het het huis te klein, en na een nieuwe meter een week lang.
        # Zonder netmeter rekent hij zoals altijd met alleen de zon en de apparaten.
        per_uur: dict[int, list[float]] = {}
        stempels = set(zonnen).union(*net_reeksen.values()) if net_reeksen else set(zonnen)
        for stempel in sorted(stempels):
            net = _net_afname(bronnen, net_reeksen, stempel) if netten else 0.0
            if net is None:
                continue
            watt = zonnen.get(stempel, 0.0) + net
            for reeks, teken in apparaat:
                watt -= teken * reeks.get(stempel, 0.0)
            uur = dt_util.as_local(
                datetime.fromtimestamp(stempel, tz=timezone.utc)
            ).hour
            per_uur.setdefault(uur, []).append(max(0.0, watt))

        # Vier kwartieren maken een uur, en de opslag staat in watt. Het
        # gemiddelde vermogen over een uur ís het aantal kilowattuur van dat uur.
        self._huis_kwh = {
            uur: _mediaan(waarden) / 1000.0 for uur, waarden in per_uur.items() if waarden
        }
        _LOGGER.debug("huisverbruik per uur bijgewerkt: %s", self._huis_kwh)

    async def _async_zonkromme(self, settings: dict[str, Any], now: datetime) -> None:
        """De zonverwachting per uur, zo precies als deze woning hem heeft.

        Drie bronnen, en de eerste die iets oplevert wint.

        **De voorspelling van het energiedashboard.** Elke zonvoorspeller die
        aan het energiedashboard hangt levert daar een uurkromme, en Home
        Assistant ontsluit ze allemaal op dezelfde manier. Dat is dus geen
        Forecast.Solar-truc: Solcast doet het net zo. Nagemeten in de klantwoning
        op 30-08-2026: veertien uur vooruit, per uur, in wattuur.

        **Dezelfde kromme via de ingevulde sensoren** (v0.100.1), voor wie zijn
        voorspeller niet in het energiedashboard heeft gezet. Zie
        `_async_zon_uit_integratie`.

        **En anders wat de klant zelf heeft ingevuld.** Dit uur en het volgende
        staan al onder Zonverwachting en zijn dus echte getallen. Wat er die dag
        verder nog aankomt is één getal, en dat wordt over de resterende
        daglichturen verdeeld met de piek als top. Dat is een schatting en geen
        meting, en `geschat` staat daarom in de uitkomst zodat het scherm het
        erbij kan zetten.

        Levert geen van beide iets, dan zijn er geen zonschijven voor de uren die
        nog moeten komen. De coach kiest dan op prijs, plus de zon die hij op dit
        moment wérkelijk meet. Dat is precies wat hij deed voordat dit bestond.
        """
        if self._zon_tot is not None and now < self._zon_tot:
            return
        self._zon_tot = now + ZON_VERVERSEN

        kromme = await self._async_zon_uit_dashboard()
        if not kromme:
            kromme = await self._async_zon_uit_integratie(settings)
        if kromme:
            self._zon_kwh, self._zon_geschat = kromme, False
            return

        sensoren = self._zon_uit_sensoren(settings, now)
        # Zegt de klant niets over de rest van de dag, dan de eigen opwek met het weer
        # (v0.151.0, zon.py). Dit uur en het volgende uit de sensoren gaan voor: dat zijn
        # metingen.
        uur = now.replace(minute=0, second=0, microsecond=0)
        if not any(k > uur + timedelta(hours=1) for k in sensoren):
            eigen = await self._async_zon_uit_opwek(settings, now)
            if eigen:
                sensoren = {**eigen, **sensoren}
        self._zon_kwh, self._zon_geschat = sensoren, True

    async def _async_zon_uit_opwek(self, settings: dict[str, Any], now: datetime) -> dict[datetime, float]:
        """De zonverwachting uit de eigen opwek en het weer, zonder paneelgegevens (v0.151.0).

        De opwek per uur uit de eigen kwartieropslag, het weer uit de eerste weerentiteit die
        een uurverwachting met bewolking geeft, en wat dat weer op elk voorbij uur zei uit
        `ZonStore`. Het rekenwerk staat in zon.py. Alles in UTC; de uitkomst in de tijd van
        het huis, zoals de andere bronnen.
        """
        zonnen = zonsensoren(settings)
        breedte = getattr(self.hass.config, "latitude", None)
        lengte = getattr(self.hass.config, "longitude", None)
        if not zonnen or breedte is None or lengte is None:
            return {}
        einde = dt_util.utcnow()
        try:
            rijen = await async_get_archive(self.hass).async_lees(
                zonnen, einde - timedelta(days=ZON_DAGEN + 1), einde
            )
        except Exception:  # noqa: BLE001 - zonder geschiedenis geen verwachting
            _LOGGER.debug("geen eigen opwek voor de zonverwachting", exc_info=True)
            return {}
        # Per uur in UTC, alleen hele uren: vier kwartieren van elke omvormer.
        per_uur: dict[datetime, list[float]] = {}
        for zon_id in zonnen:
            for rij in rijen.get(zon_id, []):
                start = datetime.fromtimestamp(int(rij["start"]), tz=timezone.utc)
                sleutel = (start.replace(minute=0, second=0, microsecond=0), zon_id)
                per_uur.setdefault(sleutel, []).append(max(0.0, float(rij.get("gemiddeld") or 0.0)))
        opwek: dict[datetime, float] = {}
        for (uur, _), watts in per_uur.items():
            if len(watts) == 4:
                opwek[uur] = opwek.get(uur, 0.0) + sum(watts) / 4.0 / 1000.0
        if not opwek:
            return {}

        nu_utc = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
        nu_bewolking, straks = await self._async_weer()
        geheugen = async_get_zon(self.hass)
        if nu_bewolking is not None:
            await geheugen.async_noteer(nu_utc, nu_bewolking)
        toen: dict[datetime, float] = {}
        for sleutel, procent in (await geheugen.async_bewolking()).items():
            try:
                toen[datetime.fromisoformat(sleutel)] = procent
            except ValueError:
                continue
        uren = [nu_utc + timedelta(hours=i) for i in range(ZON_VOORUIT_UREN)]
        uit = await self.hass.async_add_executor_job(
            partial(zon_uit_opwek, opwek, uren, breedte, lengte, toen, straks, dt_util.utcnow())
        )
        return {dt_util.as_local(uur).replace(tzinfo=None): kwh for uur, kwh in uit.items()}

    async def _async_weer(self) -> tuple[float | None, dict[datetime, float]]:
        """De bewolking nu en per komend uur, uit de eerste weerentiteit die dat geeft (v0.151.0).

        `weather.get_forecasts` met een uurverwachting, zoals elke weerintegratie van Home
        Assistant die uren kent hem geeft (Met.no, de standaard van een nieuwe installatie,
        doet dat). Zonder weer: niets, en dan rekent de coach met hoe het de laatste dagen ging.
        """
        try:
            namen = sorted(s.entity_id for s in self.hass.states.async_all("weather"))
        except Exception:  # noqa: BLE001 - zonder weer gewoon zonder
            return None, {}
        for naam in namen:
            staat = self.hass.states.get(naam)
            nu = (getattr(staat, "attributes", None) or {}).get("cloud_coverage")
            try:
                async with asyncio.timeout(10):
                    antwoord = await self.hass.services.async_call(
                        "weather", "get_forecasts", {"entity_id": naam, "type": "hourly"},
                        blocking=True, return_response=True,
                    )
            except Exception:  # noqa: BLE001 - een weerentiteit zonder uren
                continue
            rijen = ((antwoord or {}).get(naam) or {}).get("forecast") or []
            straks: dict[datetime, float] = {}
            for rij in rijen:
                tijd = dt_util.parse_datetime(str(rij.get("datetime") or ""))
                bewolking = rij.get("cloud_coverage")
                if tijd is None or not isinstance(bewolking, (int, float)):
                    continue
                straks[dt_util.as_utc(tijd).replace(minute=0, second=0, microsecond=0)] = float(bewolking)
            if straks:
                return (float(nu) if isinstance(nu, (int, float)) else None), straks
        return None, {}

    async def _async_zon_uit_dashboard(self) -> dict[datetime, float]:
        """De uurkromme die het energiedashboard van Home Assistant zelf toont.

        Precies de weg die dat dashboard ook loopt: de voorkeuren zeggen welke
        integraties een zonvoorspelling leveren, en elk van die integraties heeft
        een `energy`-platform met `async_get_solar_forecast`. Dat is de afspraak
        waar Forecast.Solar en Solcast zich allebei aan houden.

        Alles zit in een vangnet. Verandert Home Assistant hier iets aan, dan
        valt de coach terug op de sensoren van de klant in plaats van om te
        vallen. Een zonverwachting is nuttig, niet noodzakelijk.
        """
        try:
            from homeassistant.components.energy.data import async_get_manager

            manager = await async_get_manager(self.hass)
            entries = [
                entry_id
                for bron in (manager.data or {}).get("energy_sources") or []
                if bron.get("type") == "solar"
                for entry_id in bron.get("config_entry_solar_forecast") or []
            ]
            return await self._async_kromme_van(entries)
        except Exception:  # noqa: BLE001 - een voorspelling is nuttig, niet noodzakelijk
            _LOGGER.debug("geen uurkromme uit het energiedashboard", exc_info=True)
            return {}

    async def _async_zon_uit_integratie(self, settings: dict[str, Any]) -> dict[datetime, float]:
        """Dezelfde uurkromme, via de integratie achter de ingevulde zonsensoren.

        Voor wie zijn voorspeller niet in het energiedashboard heeft gezet. De
        losse sensoren zijn dan een slechte tweede keus, en bij Forecast.Solar
        dubbel: ze lezen dezelfde lijst als begin van het uur (zie
        `zonkromme_uit`), en ze worden maar eens per uur bijgewerkt. Thuis op
        26-09-2026 om 12:16 zei "dit uur" 1,228 kWh, en dat was de verwachting
        van 10:00 tot 11:00: bijgewerkt om 11:48, en toen al een uur achter.

        Elke integratie die het energiedashboard een kromme kan geven, geeft
        hem ook hier: de entiteitregistratie zegt bij welke config entry een
        ingevulde sensor hoort, en die vragen we om dezelfde
        `async_get_solar_forecast`. Levert dat niets op (een sjabloonsensor,
        een integratie zonder energieplatform), dan blijft `_zon_uit_sensoren`.
        """
        try:
            from homeassistant.helpers import entity_registry as er

            register = er.async_get(self.hass)
            bron = (settings.get("sources") or {}).get("solar_forecast") or {}
            entries = []
            for entity_id in bron.values():
                rij = register.async_get(entity_id) if isinstance(entity_id, str) and entity_id else None
                if rij is not None and rij.config_entry_id:
                    entries.append(rij.config_entry_id)
            return await self._async_kromme_van(entries) if entries else {}
        except Exception:  # noqa: BLE001 - een voorspelling is nuttig, niet noodzakelijk
            _LOGGER.debug("geen uurkromme via de zonsensoren", exc_info=True)
            return {}

    async def _async_kromme_van(self, entry_ids: list[str]) -> dict[datetime, float]:
        """De uurkromme van deze voorspellers samen, elk één keer, elk goed uitgelijnd.

        Eén keer, want twee omvormers in het energiedashboard kunnen naar
        dezelfde voorspeller wijzen, en dan telde de coach hem tot v0.100.1
        dubbel; het energiedashboard zelf telt hem één keer. Faalt er één, dan
        gooit dit, en valt de aanroeper terug: een halve kromme zegt te weinig
        zon en is erger dan geen kromme.
        """
        from homeassistant.loader import async_get_integration

        uit: dict[datetime, float] = {}
        for entry_id in dict.fromkeys(entry_ids):
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                continue
            integratie = await async_get_integration(self.hass, entry.domain)
            platform = await integratie.async_get_platform("energy")
            voorspeld = await platform.async_get_solar_forecast(self.hass, entry_id)
            # Welk uur een tijdstip bedoelt verschilt per voorspeller; zie
            # `zonkromme_uit`.
            kromme = zonkromme_uit(entry.domain, (voorspeld or {}).get("wh_hours") or {})
            for uur, kwh in kromme.items():
                uit[uur] = uit.get(uur, 0.0) + kwh
        return uit

    def _zon_uit_sensoren(
        self, settings: dict[str, Any], now: datetime
    ) -> dict[datetime, float]:
        """Een kromme uit de vier getallen die de klant zelf heeft ingevuld.

        Dit uur en het volgende zijn metingen en gaan er ongewijzigd in. Wat er
        vandaag verder nog aankomt is één getal; dat wordt over de resterende
        daglichturen verdeeld met een driehoek waarvan de top op het piekmoment
        ligt. Een vlakke verdeling zou zeggen dat zes uur 's avonds evenveel
        oplevert als het middaguur, en dat is aantoonbaar onwaar.

        Het is en blijft een schatting. Daarom zegt het scherm dat erbij, en
        daarom stuurt de coach nog steeds op wat hij op dit moment wérkelijk
        meet.
        """
        zon = self._sun(settings)
        uur = now.replace(minute=0, second=0, microsecond=0)
        uit: dict[datetime, float] = {}

        if zon.now_w:
            uit[uur] = zon.now_w / 1000.0
        if zon.next_w:
            uit[uur + timedelta(hours=1)] = zon.next_w / 1000.0

        rest = (zon.remaining_kwh or 0.0) - sum(uit.values())
        piek = self._piek(settings)
        if rest <= 0 or piek is None:
            return uit

        # De uren die vandaag nog komen na het uur dat we al kennen. De
        # daglengte volgt uit de piek: even lang na de piek als ervoor, en dat
        # klopt op een dag na de zonnewende beter dan elke vaste aanname.
        eind = piek + (piek - uur) if piek > uur else piek + timedelta(hours=1)
        uren = []
        stap = uur + timedelta(hours=2)
        while stap < eind and stap.date() == uur.date():
            uren.append(stap)
            stap += timedelta(hours=1)
        if not uren:
            return uit

        # Een driehoek met de top op de piek. De gewichten zijn de afstand tot
        # het einde van de dag, dus hoe dichter bij de piek hoe zwaarder.
        gewichten = [max(0.1, (eind - u).total_seconds() / 3600.0) for u in uren]
        totaal = sum(gewichten)
        for u, gewicht in zip(uren, gewichten):
            uit[u] = rest * gewicht / totaal
        return uit

    @staticmethod
    def _tariff(settings: dict[str, Any], saldeert: bool | None = None, now: datetime | None = None) -> Tariff:
        """Wat een kWh kost en opbrengt als de prijslijst niets zegt.

        `saldeert` is of een teruggeleverde kWh nu wegstreept (`_saldeert`,
        v0.133.3); zonder is het het vinkje en de datum.

        Een vast contract dat over 1 januari 2027 heen loopt heeft twee
        terugleverprijzen (v0.134.0): tot dan de vergoeding na saldering en de
        kosten van nu, daarna wat er in het contract staat voor na salderen
        (`_teruglevering`).

        Bij een vast contract staat het hele jaar hetzelfde getal, dus is er geen
        lijst en is dit alles wat de coach heeft. Juist daar telt het zwaar: het
        verschil tussen inkopen en terugleveren is bij een vast contract de enige
        reden die er is om het ene moment boven het andere te verkiezen.
        """
        contract = settings.get("contract") or {}
        if contract.get("country") == "PT":
            # Portugal (v0.137.0): de prijs van het tijdvak van nu, en wat het
            # verkoopcontract voor teruglevering geeft (`tarifas.py`).
            pt = contract.get("pt") or {}
            moment = _bewust(now)
            return Tariff(buy=tarifas.preco(pt, tarifas.periodo(moment, pt.get("tarifa"), pt.get("ciclo"))),
                          feed_in=tarifas.terug(pt))
        if contract.get("type") == "dynamic":
            return Tariff()

        fixed = contract.get("fixed") or {}
        prijs = fixed.get("all_in_price")
        koop = float(prijs) if prijs is not None else None
        gesaldeerd = ChargerCoach._salderen(contract, now) if saldeert is None else saldeert
        vergoeding, kosten = ChargerCoach._teruglevering(fixed, now, gesaldeerd)

        if gesaldeerd:
            # Salderen: wat je teruglevert streept weg tegen wat je inkoopt, dus
            # is het de inkoopprijs waard. Het ingevulde terugleverbedrag geldt
            # dan niet; dat is pas aan de orde boven wat je zelf verbruikt.
            terug = None if koop is None else koop - kosten
        else:
            terug = vergoeding - kosten

        return Tariff(buy=koop, feed_in=terug)

    @staticmethod
    def _teruglevering(fixed: dict[str, Any], now: datetime | None = None, saldeert: bool = False) -> tuple[float, float]:
        """De vergoeding en de kosten per kWh van een vast contract op dit moment (v0.134.0).

        Tot `NETTING_ENDS` de gewone velden. Daarna, als ze ingevuld zijn, wat
        het contract voor na salderen zegt (`feed_in_tariff_after`,
        `feed_in_costs_after`); een leeg veld houdt het bedrag van ervoor. De
        eigenaar op 19-10-2026, met een vast contract tot na die datum:
        "Terugleververgoeding na saldering tot 1-1-2027 € 0,124000",
        "Terugleververgoeding vanaf 1-1-2027 € 0,072100" en "Terugleverkosten
        vanaf 1-1-2027 € 0,052756 per kWh", met tot dan vaste terugleverkosten
        per schaal. Met één veld rekende de coach óf nu met de kosten van
        2027, óf in 2027 met de vergoeding van nu.
        """
        vergoeding = float(fixed.get("feed_in_tariff") or 0)
        # De kosten van een kWh extra, in de vorm die het contract zegt (v0.135.0).
        kosten = prijsopbouw.kosten_per_kwh(fixed, saldeert)
        if dt_util.as_local(now or dt_util.utcnow()).date() >= NETTING_ENDS:
            if fixed.get("feed_in_tariff_after") is not None:
                vergoeding = float(fixed["feed_in_tariff_after"])
            if fixed.get("feed_in_costs_after") is not None:
                # Na salderen per kWh over alles, zoals de leveranciers het aankondigen.
                kosten = float(fixed["feed_in_costs_after"])
        return vergoeding, kosten

    @staticmethod
    def _all_in(market: float, dynamic: dict[str, Any]) -> float:
        """A bare market price with tax, markup and VAT, the Dutch way round."""
        tax = float(dynamic.get("energy_tax") or 0)
        markup = float(dynamic.get("supplier_markup") or 0)
        vat = float(dynamic.get("vat_percent") or 0)
        return (market + tax + markup) * (1 + vat / 100)

    def _volgehouden(
        self, entity_id: str | None, waarde: float | None, now: datetime
    ) -> float | None:
        """De laatste bruikbare meting van deze sensor, als hij even niets zegt.

        Een sensor die `unavailable` of `unknown` meldt, of die er even helemaal
        niet is, heeft geen waarde nul. Hij heeft geen waarde. Dat verschil is
        precies waar het op 30-08-2026 in de klantwoning op misging: de P1-meter
        viel drie keer een paar seconden weg, de coach rekende de zon uit op nul
        en zette het laden stil. Zie `MEETNAIJL`.

        Blijft hij langer weg dan die naijl, dan geeft dit niets terug, en dan is
        onbekend ook echt onbekend. Doorrekenen met een getal van een half uur
        oud is erger dan zeggen dat je het niet weet.
        """
        if not entity_id:
            return waarde
        if waarde is not None:
            self._laatste_meting[entity_id] = (waarde, now)
            return waarde
        eerder = self._laatste_meting.get(entity_id)
        if eerder is None or now - eerder[1] > MEETNAIJL:
            self._laatste_meting.pop(entity_id, None)
            return None
        return eerder[0]

    def _gladde_fase(
        self, entity_id: str | None, amps: float, now: datetime
    ) -> float:
        """De fasestroom zonder de enkele uitschieter die er niet bij hoort.

        De mediaan van wat deze fase binnen `FASE_VENSTER` gemeld heeft.
        Uitdrukkelijk de mediaan en niet het gemiddelde: een gemiddelde laat één
        sample van 27 A over drie metingen nog altijd vijf ampère doortellen,
        een mediaan gooit hem weg. Een huis dat werkelijk bijschakelt heeft
        binnen twee metingen de meerderheid en komt er dus gewoon door.

        Minder dan drie metingen is geen mediaan maar een gok, en dan telt wat
        de sensor nu zegt. Dat is ook het geval vlak na een herstart, en dat
        hoort zo: liever een ronde te voorzichtig dan een ronde te laat.

        Alleen voor fasen die als stroomsensor zijn ingevuld. Een fase die uit
        vermogen en spanning wordt herleid komt niet langs de luisteraar en
        heeft dus geen historie; die blijft rauw.
        """
        historie = self._fase_historie.get(entity_id or "") or []
        grens = now - FASE_VENSTER
        # Deed een paal net een stap omlaag, dan tellen alleen de metingen van
        # daarna. De metingen van ervoor dragen zijn oude stroom nog, en een
        # mediaan daarover rekent die aan het huis toe: in het virtuele huis
        # ging een bus op een 1x25 A-aansluiting daardoor van 6 A naar
        # "no-room" en bleef hij de hele oventijd uit, terwijl 24,3 A gewoon
        # paste. Zijn er nog geen drie nieuwe, dan telt wat de sensor nu zegt,
        # en dat is op dat moment ook de waarheid.
        if self._daling is not None and self._daling > grens:
            grens = self._daling
        waarden = sorted(waarde for stempel, waarde in historie if stempel >= grens)
        if len(waarden) < 3:
            return amps
        return waarden[len(waarden) // 2]

    def _read(
        self,
        now: datetime,
        settings: dict[str, Any],
        device: dict[str, Any],
        reserved: dict[str, float] | None = None,
    ) -> tuple[Grid, Car, Charger, Window]:
        """Everything the planner needs, gathered from the installation."""
        sources = settings.get("sources") or {}
        installation = settings.get("installation") or {}
        entities = device.get("entities") or {}

        # --- what the grid is doing ---
        #
        # Wat er naar het net gaat is geen vaste waarde maar een gevolg van wat
        # de coach zelf doet, en dat is de valkuil. Lever je 5 kW terug en gaat
        # de laadpaal aan, dan is die 5 kW weg. De coach zou dan meten dat er
        # geen zon meer over is, de laadpaal uitzetten, de 5 kW terugzien, en
        # weer aangaan. Elke minuut opnieuw, de hele middag.
        #
        # Daarom wordt hier niet gemeten wat er nú naar het net gaat, maar wat
        # er naar het net zou gaan als de laadpaal uit stond: het net saldo plus
        # wat de paal op dit moment zelf trekt. Dat getal verandert niet doordat
        # de coach iets doet, en daarmee is het kringetje open.
        # Optellen mag alleen als het saldo echt bekend is. Met één sensor die
        # alleen teruglevering meet, weet de coach niet of er tegelijk wordt
        # ingekocht, en dan zou hij bij 2 kW inkoop en 4 kW laden concluderen dat
        # er 4 kW zon over is. Liever de rauwe teruglevering dan een optelsom van
        # iets wat hij niet kan zien.
        # Elke meting hieronder gaat langs `_volgehouden`. Een sensor die even
        # niets zegt houdt zijn laatste waarde; een die echt weg is geeft niets
        # terug, en dan rekent de coach niet door met een nul die hij verzonnen
        # heeft. Zie `MEETNAIJL`.
        # `vers` is of de meter op dit moment werkelijk iets zegt. Een waarde die
        # nog wordt vastgehouden telt voor het besluit, maar niet als teken van
        # leven: anders begint de klok van `_nettip` pas te lopen als het
        # vasthouden ophoudt en zegt de kaart "al 1 minuten" over een meter die
        # er al zes minuten niet is.
        if sources.get("grid_mode") == "signed":
            bron = sources.get("grid_signed")
            gemeten = _watts(self.hass, bron)
            vers = gemeten is not None
            signed = self._volgehouden(bron, gemeten, now)
            if signed is not None and sources.get("grid_signed_invert"):
                signed = -signed
            netto = None if signed is None else -signed
            compleet = signed is not None
        else:
            uit = sources.get("grid_export")
            in_ = sources.get("grid_import")
            export_gemeten = _watts(self.hass, uit)
            invoer_gemeten = _watts(self.hass, in_)
            vers = export_gemeten is not None and (in_ is None or invoer_gemeten is not None)
            export = self._volgehouden(uit, export_gemeten, now)
            invoer = self._volgehouden(in_, invoer_gemeten, now)
            compleet = export is not None and invoer is not None
            netto = (export - invoer) if compleet else (export if invoer is None else None)

        # Wat een thuisbatterij opneemt hoort bij het overschot zolang hij
        # lager in de voorrang staat, en wat hij afgeeft is geen zon; en een
        # boiler lager in de voorrang wijkt met wat hij van de zon neemt. Zie
        # `_zon_correctie` (v0.92.0; daarvoor ging de auto altijd voor de
        # batterij, en dat is nog steeds de standaard).
        if netto is not None:
            netto += self._zon_correctie(settings, device, netto)

        # Het vermogen van de paal zit in dezelfde som, en juist die houdt het
        # kringetje open: zonder hem ziet de coach zijn eigen laden aan voor
        # huisverbruik. Valt hij weg, dan telt de laatste waarde die er wél was.
        laadvermogen = self._volgehouden(
            device.get("entity"), _watts(self.hass, device.get("entity")), now
        )

        # De netmeting is niet te lezen. Dan is de zon onbekend en niet nul, dus
        # er wordt niet op gestuurd; de prijs- en klaar-tijdregels werken gewoon
        # door. En de coach zegt het, want stilstand zonder reden leest als kapot.
        if netto is None or (compleet and laadvermogen is None):
            # Sinds wanneer hij zwijgt is niet dit moment maar de laatste ronde
            # waarin hij er nog was: de naijl hierboven heeft er al een paar
            # minuten overheen gelaten voordat het hier terechtkomt.
            self._net_stil_sinds = self._net_stil_sinds or self._net_gezien or now
            # Wat er zwijgt: de meter zelf, of alleen het vermogen van de paal.
            # In de klantwoning was het van 25 tot 27-09-2026 de Easee, twee
            # dagen lang, terwijl de slimme meter gewoon doorliep; de melding
            # stuurde de bewoner naar de verkeerde integratie.
            self._net_stil_wat = "meter" if netto is None else "paal"
            surplus = 0.0
            self._zon.pop(device.get("id", ""), None)
        else:
            if vers:
                self._net_gezien = now
            self._net_stil_sinds = None
            surplus = max(
                0.0,
                netto + (laadvermogen or 0.0) if compleet else max(0.0, netto),
            )
            surplus = self._smooth(device.get("id", ""), surplus, now)
            # Wat de verwachting voor dit uur beloofde naast wat er werkelijk
            # over is. Alleen als er echt gemeten is; een ronde waarin de
            # netmeting wegviel zegt niets over de zon. Zie `_zon_gemeten`.
            self._zon_bijhouden(now, settings)

        charger_amps = (
            self._volgehouden(
                entities.get("current"), _number(self.hass, entities.get("current")), now
            )
            or 0.0
        )
        # Een stap omlaag van deze paal maakt de fasemetingen van daarvoor
        # onbruikbaar voor de mediaan: daar zit zijn oude stroom nog in, en die
        # zou als huisverbruik gelden. Zie `_gladde_fase`.
        device_id = device.get("id", "")
        vorige_stroom = self._stroom_vorige.get(device_id)
        if vorige_stroom is not None and charger_amps < vorige_stroom - STEP_AMPS:
            self._daling = now
        self._stroom_vorige[device_id] = charger_amps

        # Wat een gestuurde batterij op deze zekeringen doet, per fase. Die
        # stroom wijkt zodra de paal laadt, dus het is geen ruimte die het huis
        # inneemt (v0.88.2). Zie `_batterij_wijkt`.
        wijkt = self._batterij_wijkt(settings, now, device)

        phases = []
        pieken = []
        for key in ("l1", "l2", "l3"):
            fase = (sources.get("phases") or {}).get(key) or {}
            amps = self._fase_amps(fase, now)
            if amps is not None:
                phases.append(max(0.0, amps - wijkt.get(("", key), 0.0)))
                pieken.append(max(0.0, (self._fase_piek(fase, now) or amps) - wijkt.get(("", key), 0.0)))

        # De groepen waar deze paal aan hangt, elk met de eigen meter en de
        # eigen zekering. Zie `Circuit` in planner.py.
        reserved = reserved or {}
        circuits = []
        for groep in self._groepen_keten(settings, device):
            stromen = []
            toppen = []
            for key in ("l1", "l2", "l3"):
                fase = (groep.get("sensors") or {}).get(key) or {}
                amps = self._fase_amps(fase, now)
                if amps is not None:
                    wijk = wijkt.get((str(groep.get("id")), key), 0.0)
                    stromen.append(max(0.0, amps - wijk))
                    toppen.append(max(0.0, (self._fase_piek(fase, now) or amps) - wijk))
            # Zonder meter: wat de apparaten trekken die de bewoner bij de groep koos (v0.165.0).
            bekend = None if stromen else self._groep_som(settings, groep)
            circuits.append(Circuit(
                known_amps=max(bekend.values(), default=0.0) if bekend else 0.0,
                name=str(groep.get("name") or groep.get("id") or ""),
                soort="onderverdeelkast" if groep.get("kind") == "kast" else "groep",
                phase_amps=stromen,
                phase_peak_amps=toppen,
                fuse_amps=float(groep.get("fuse_amps") or 16),
                reserved_amps=float(reserved.get(str(groep.get("id")), 0.0)),
            ))

        # Wat deze paal kort geleden nog trok. De fasemeting van het huis loopt
        # achter op de paal, dus vlak na het stoppen draagt zij zijn stroom nog
        # terwijl hij zelf al op nul staat. Zonder dit geheugen wordt dat aan het
        # huis toegerekend en meldt de coach dat de aansluiting vol zit terwijl er
        # niets loopt. Zie `meter_loopt_achter` in planner.py.
        #
        # De minuut telt vanaf de eerste ronde die de paal op nul zag, niet
        # vanaf de laatste die hem zag laden (v0.157.0). In een klantwoning
        # herstartte de Easee op 24-10-2026 om 00:08:43 zijn laadbeurt; de
        # ronde daarvoor was om 00:07:46, en die van 00:08:46 viel net buiten
        # de minuut. De fasen stonden tot 00:09:02 nog op 18 A, dat werd huis,
        # de coach schreef 0 A ("te zwaar belast"), en de Ford pauzeerde
        # veertig seconden later voorgoed op 78%.
        recent = self._laatste_stroom.get(device_id)
        if charger_amps > STEP_AMPS:
            self._laatste_stroom[device_id] = (charger_amps, None)
            recent_amps = charger_amps
        elif recent is not None:
            weg = recent[1] or now
            if recent[1] is None:
                self._laatste_stroom[device_id] = (recent[0], now)
            if now - weg <= METER_NAIJL:
                recent_amps = recent[0]
            else:
                self._laatste_stroom.pop(device_id, None)
                recent_amps = 0.0
        else:
            recent_amps = 0.0

        grid = Grid(
            recent_charger_amps=recent_amps,
            surplus_w=surplus,
            # Wat een eerder laadpunt in deze ronde al toegezegd heeft gekregen
            # en nog niet in de fasemeting staat.
            reserved_amps=float(reserved.get("", 0.0)),
            circuits=circuits,
            phase_amps=phases,
            phase_peak_amps=pieken,
            fuse_amps=float(installation.get("fuse_amps") or 25),
            charger_amps=charger_amps,
            # An installation with a balancer of its own guards the same fuse in
            # hardware. The coach widens its margin so it is the one to give way
            # and the two never reach for the same amp at the same second.
            margin_amps=(
                BALANCER_MARGIN_AMPS
                if installation.get("load_balancer")
                else FUSE_MARGIN_AMPS
            ),
            # Wat de lastbewaker op dit moment vrijgeeft, als de klant die
            # sensor heeft ingevuld. Zie `beschikbaar_van_bewaker` in planner.py:
            # dat is een restwaarde en geen tweede zekering.
            balancer_amps=_number(self.hass, installation.get("balancer_entity")),
        )

        # --- the charging point ---
        # Wat de paal zelf zegt te doen. Zegt hij even níets, dan telt wat hij
        # het laatst wél zei.
        #
        # Onbekend is niet hetzelfde als losgekoppeld, en dat verschil is duur.
        # `connected` hieronder is onwaar zodra deze tekst leeg is, en `_text`
        # geeft een lege string zodra de entiteit er niet is. Trekt een
        # integratie kort zijn entiteiten in, bijvoorbeeld bij een herverbinding,
        # dan las de coach dat als een kabel die eruit gaat: hij stuurde een
        # verslag en wiste de hele sessie, dus het akkoord, snelladen, de
        # opgegeven accustand en de klaar-tijd waar hij aan werkte.
        #
        # De eigenaar kreeg op 29-08-2026 om 19:54 zo'n verslag terwijl de paal die hele
        # avond op `awaiting_start` stond. Of het toen precies hierdoor kwam is
        # achteraf niet te bewijzen, maar een sensor die niets zegt mag sowieso
        # geen afkoppeling betekenen.
        if entities.get("status"):
            gemeld = _text(self.hass, entities.get("status"))
        else:
            gemeld = self._status_afgeleid(device_id, entities, now)
        if gemeld in ("", "unknown", "unavailable", "none"):
            status = self._laatste_status.get(device_id, "")
        else:
            status = gemeld
            self._laatste_status[device_id] = status

        # En een paal die wél iets zegt, alleen niet lang genoeg om het te
        # geloven. Een Easee die zijn laadbeurt opnieuw opstart meldt twee
        # seconden `disconnected` en gaat daarna gewoon door met laden. Zie
        # `KABEL_ONTDREUN` voor wat dat in de klantwoning kostte.
        #
        # Het moment dat hier onthouden wordt is het moment dat straks in het
        # verslag komt: de kabel ging eruit toen de paal het zei, niet toen de
        # coach het geloofde.
        zegt_los = (not status) or "disconnect" in status
        # Wat de bewoner opgaf en wat er over de beurt bewaard is, gaat alleen
        # weg als de paal zegt dat de kabel eruit is. Na een herstart weet de
        # coach de laatste status nog niet, en zegt een paal waarvan de
        # integratie nog laadt eerst niets; dat telde als "kabel eruit", en dan
        # was de opgegeven accustand weg (v0.98.0).
        self._echt_los[device_id] = "disconnect" in status
        if not zegt_los:
            self._los_sinds.pop(device_id, None)
            self._was_verbonden.add(device_id)
            verbonden = True
        elif device_id not in self._was_verbonden:
            # Er is aan deze paal nog nooit een kabel gezien, dus er valt ook
            # niets te ontdreunen. Een coach die net opstart bij een lege paal
            # hoort niet een halve minuut te doen alsof er een auto hangt.
            verbonden = False
        else:
            sinds = self._los_sinds.setdefault(device_id, now)
            verbonden = now - sinds < KABEL_ONTDREUN
            if not verbonden:
                self._was_verbonden.discard(device_id)

        charger = Charger(
            max_amps=_number(self.hass, entities.get("max_limit")) or 16.0,
            connected=verbonden,
            charging="charging" in status,
            started_at=self._since.get(device.get("id", "")),
            actual_amps=charger_amps,
            # De paal zegt het zelf als de auto vol is, en dat is beter dan het
            # afleiden uit een stroom die bijna nul is: dat laatste lijkt sprekend
            # op een auto die om een andere reden niets vraagt.
            complete="complete" in status,
            boost=device.get("id", "") in self._boost,
            modus=self._modus_van(device),
            continu_amps=int(device.get("continuous_amps") or MIN_AMPS),
            zon_start=float(device.get("solar_start_percent") or 90) / 100.0,
            paused_by_user=device.get("id", "") in self._paused,
            paused_by_balancer="equalizer" in status or "load_balancing" in status,
            no_current_reason=_text(self.hass, entities.get("no_current_reason")),
            # Wat er op de paal staat, zodat de klaar-tijdsom kan zien of de
            # coach zelf de rem is. Zie `throttled_by_coach` in planner.py.
            limit_amps=_number(self.hass, entities.get("dynamic_limit")),
            circuit_amps=self._groep_amps(entities),
        )
        # Hoe lang de paal al onder zijn limiet blijft. Een naijl na een stap
        # omhoog is na de aanloop voorbij; een verschil dat daarna blijft staan
        # is de auto, en dan mag het plafond weer op de meting rusten (v0.113.1,
        # `meter_loopt_achter` in planner.py). Elke stap omhoog begint opnieuw.
        limiet = charger.limit_amps
        if charger.charging and limiet is not None and limiet - charger_amps > STEP_AMPS:
            klok = self._achter_sinds.get(device_id)
            if klok is None or limiet > klok[1]:
                klok = (now, limiet)
            self._achter_sinds[device_id] = (klok[0], limiet)
            grid.achter_s = (now - klok[0]).total_seconds()
        else:
            self._achter_sinds.pop(device_id, None)
        # Wat er de afgelopen uren gemiddeld overbleef voor deze paal, uit de
        # boekhouding van de beurt (`_bijhouden`). Een meting van deze beurt,
        # niet van gisteren: na de kabel eruit begint hij op nul. Na een
        # herstart gaat hij door met wat er bij de beurt bewaard was (v0.98.0),
        # anders koos hij in de eerste woning op 24-09-2026 om 22:59 "wacht tot
        # 01:00" en om 23:20 weer "nu doorladen".
        if charger.connected:
            charger.expected_amps = self._plafond_gemeten(device_id, now)
        # En het vaste plafond van de zekeringen, ook na een herstart meteen
        # bekend (v0.98.0). Zie `zekering_plafond` in planner.py.
        if (vast := zekering_plafond(grid)) is not None:
            charger.zekering_amps, charger.zekering_naam = vast

        # De aanloop hoort bij de paal en niet bij het besluit. Valt de paal uit
        # `charging` en komt hij terug, dan is alles weer aan het opstarten: de
        # stroomsensor loopt een ronde achter, de auto moet nog op gang komen en
        # de fasekeuze is opnieuw gemaakt. Zolang dit aan het bésluit hing bleef
        # de klok gewoon doorlopen, want de coach wilde al die tijd laden.
        #
        # Dat kostte op 17-09-2026 thuis een nacht. Om 14:24:31 ging snelladen
        # aan, de paal herstartte en zei om 14:24:58 weer "charging" terwijl de
        # stroomsensor nog op 0,152 A van de vorige stand stond. `_tempo_leren`
        # zag een sessie die al tien minuten liep, rekende 0,152 A maal 690 V
        # naar 0,1 kW en schreef op dat de bus tussen 0 en 10% niet meer dan
        # 0,1 kW aanneemt. De volgende ronde stond er 21,41 uur nodig waar het
        # er 1,93 waren, sloeg de klaar-tijdregel aan, en die bleef staan.
        #
        # After a restart of Home Assistant itself nothing is known about when
        # this session began either. Taking it as "just now" only means waiting
        # out the minimum run once.
        if charger.charging and not self._laadde.get(device_id):
            # De eerste ronde na een herstart en de paal laadt al: dan weet de
            # bewaarde beurt sinds wanneer (v0.98.0). Zonder dat hield hij in de
            # eerste woning op 24 en 25-09-2026 na elke herstart tien minuten
            # 6 A vast, "net begonnen met laden", terwijl de auto al een uur laadde.
            eerder = (self._hervat.get(device_id) or {}).get("laadt_sinds")
            if device_id not in self._laadde and eerder is not None:
                self._since[device_id] = eerder
            else:
                self._since[device_id] = now
            charger.started_at = self._since[device_id]
        elif charger.charging and charger.started_at is None:
            # Was het laatste wat de coach stuurde een stop, dan is dit geen beurt
            # die net begon maar een paal die zijn stop nog niet doorzette. Bij de
            # eigenaar op 11-10-2026 besloot de coach om 13:45:46 te stoppen, zette
            # de Easee de 0 A pas om 13:47:00 door, en las de ronde van 13:46:46
            # "charging" zonder begin als "Net begonnen met laden": 6 A en tien
            # minuten vasthouden, van het net.
            vorige = self._last.get(device_id)
            if vorige is None or vorige.charge:
                charger.started_at = self._since.setdefault(device_id, now)
        self._laadde[device_id] = charger.charging

        # Eén fasemeting per ronde; `_fasetip` en `_car` lezen allebei deze.
        if charger.charging:
            self._fase_nu[device_id] = self._fasen_stabiel(device)
        else:
            self._fasen_gemeten.pop(device_id, None)
            self._fase_nu.pop(device_id, None)

        # --- which car ---
        car = self._car(settings, device, charger)

        # --- when it may run ---
        window = resolve_window(now, self._days(settings, device))
        # De laadlimiet van de planning (v0.96.0). De bewoner van de eerste
        # woning op 23-09-2026, naar evcc: "de algemene 90 geldt voor snelladen,
        # continu en zon; stel je een planning in, dan is de laadlimiet van de
        # planning leidend." Een planning wint van de modus, dus ook van zijn
        # limiet; snelladen gaat boven de planning, dus daar de algemene.
        self._doel_algemeen[device_id] = car.target_percent
        if window.enabled and window.target is not None and not charger.boost:
            car.target_percent = window.target
            self._doel_planning[device_id] = window.target
        else:
            self._doel_planning.pop(device_id, None)

        # --- "klaar" terwijl de auto niet vol is ---
        # De paal zegt alleen dat de auto niets meer aanneemt. In de klantwoning
        # was dat op 06-09-2026 om 04:27 een Ford met een storing op 86%, en die
        # ging pas weer laden nadat er om 05:18 met de hand een start gestuurd
        # was. Weet de coach dat de auto niet vol is, dan doet hij dat zelf, één
        # keer: hij laat de planner gewoon beslissen en stuurt bij het eerste
        # besluit om te laden een start. Blijft de paal daarna "klaar" zeggen,
        # dan gelooft hij dat en zegt hij het, mét de herstart erbij.
        gedaan = self._herstart_gedaan.get(device_id)
        if gedaan is not None and charger.charging and now - gedaan >= HERSTART_WACHT:
            # Hij heeft na de herstart weer een kwartier geladen; haakt hij nog
            # eens af, dan mag er opnieuw één poging komen.
            self._herstart_gedaan.pop(device_id, None)
            gedaan = None
        # Wanneer deze accustand voor het laatst veranderde. De sessie houdt
        # hetzelfde bij, maar die wordt verderop in de ronde bijgewerkt en loopt
        # hier dus precies één ronde achter: net te laat om te zien dat de auto
        # zich mét het "klaar" van de paal meldde. Daarom hier nog een keer, op
        # het moment dat `car` gebouwd is.
        stand = self._soc_ruw.get(device_id, car.soc_percent)
        if stand != self._soc_stand.get(device_id):
            self._soc_stand[device_id] = stand
            self._soc_op[device_id] = now
        # Sinds wanneer de paal "klaar" zegt. Nodig om te weten of de accustand
        # bij dít einde hoort of nog van halverwege de beurt is.
        if charger.complete:
            self._klaar_sinds.setdefault(device_id, now)
        else:
            self._klaar_sinds.pop(device_id, None)
        # En pas oordelen als die stand bezonken is. Thuis op 16-09-2026 zei de
        # paal om 10:46:21 "completed" terwijl de Ford-app nog 70% toonde; om
        # 10:47:19 werd dat 80, de stand waar de bus ook op stond. De coach
        # besloot om 10:46:57, tweeëntwintig seconden te vroeg, herstartte de
        # paal voor niets en stuurde een kritieke melding over 70%. Een
        # accustand die per tien procent springt is nooit jonger dan zijn
        # laatste sprong, dus hier wachten tot de auto zich meldt of tot
        # `SOC_SETTLE` om is. De auto staat toch stil; dat kost niets.
        bezonken = self._soc_bezonken(
            now, self._klaar_sinds.get(device_id), self._soc_op.get(device_id), car
        )
        if charger.complete and gedaan is None and bezonken and self._niet_vol(car):
            charger.complete = False
            self._herstart_open.add(device_id)
            # De herstart is een nieuw aanbod (v0.99.0): de auto krijgt weer een
            # kwartier voordat een Alfen klaar heet, en de melding "neemt al
            # twintig minuten geen stroom af" telt vanaf nu en niet vanaf het
            # moment dat de auto zelf stopte.
            self._afgeleid_klaar.discard(device_id)
            self._stil_sinds.pop(device_id, None)
            self._asking_since.pop(device_id, None)
        else:
            self._herstart_open.discard(device_id)

        return grid, car, charger, window

    @staticmethod
    def _days(settings: dict[str, Any], device: dict[str, Any]) -> dict[int, DayWindow]:
        """Het schema van dit apparaat, per weekdag.

        Elke dag hetzelfde levert zeven gelijke dagen op; per dag levert alleen
        de dagen op die de klant heeft aangezet. De planner rekent het daarna om
        naar twee momenten, en dat is waar het vooruitkijken gebeurt: een
        weekend zonder eisen erin telt niet als "niets te doen" maar als "tijd
        om het goedkoopste moment uit te zoeken".
        """
        # Een laadpaal kent alleen "klaar om". De eigenaar op 04-09-2026: "niet eerder
        # dan en starten voor moet er helemaal uit." De coach kiest zelf het
        # goedkoopste moment; een begintijd zou hem alleen van de zon afhouden
        # en een starttijd zou hem laten laden terwijl het duur is. Het paneel
        # vraagt er bij een laadpaal niet meer om; wat er van vroeger nog in de
        # instellingen staat telt hier niet mee.
        # Een boiler net zo: de eigenaar koos op 19-09-2026 "klaar om, zoals de auto".
        alleen_klaar = device.get("type") in ("laadpaal", "boiler")

        def tijd(bron: dict[str, Any], sleutel: str) -> time | None:
            if alleen_klaar and sleutel != "done_by":
                return None
            return _time(bron.get(sleutel))

        def doel(bron: dict[str, Any]) -> float | None:
            # Het doel van de planning (v0.96.0), alleen bij een laadpaal.
            if device.get("type") != "laadpaal":
                return None
            try:
                waarde = float(bron.get("target"))
            except (TypeError, ValueError):
                return None
            return max(10.0, min(100.0, waarde))

        for entry in (settings.get("strategy") or {}).get("schedules") or []:
            if entry.get("device") != device.get("id") or not entry.get("enabled"):
                continue

            if not entry.get("per_day"):
                times = entry.get("window") or {}
                elke_dag = DayWindow(
                    enabled=True,
                    not_before=tijd(times, "not_before"),
                    start_by=tijd(times, "start_by"),
                    done_by=tijd(times, "done_by"),
                    target=doel(times),
                )
                return dict.fromkeys(range(7), elke_dag)

            uit: dict[int, DayWindow] = {}
            for day in entry.get("days") or []:
                weekdag = day.get("day")
                if not isinstance(weekdag, int) or not 0 <= weekdag <= 6:
                    continue
                uit[weekdag] = DayWindow(
                    enabled=bool(day.get("enabled")),
                    not_before=tijd(day, "not_before"),
                    start_by=tijd(day, "start_by"),
                    done_by=tijd(day, "done_by"),
                    target=doel(day),
                )
            return uit

        return {}

    def _actieradius(self, settings: dict[str, Any], device: dict[str, Any]) -> float | None:
        """De actieradius in km uit de sensor in het autoprofiel, of niets."""
        _gekozen, profiel = self._chosen_car(settings, device)
        entiteit = (profiel or {}).get("range_entity")
        waarde = _number(self.hass, entiteit) if entiteit else None
        return None if waarde is None else round(waarde)

    def _chosen_car(
        self, settings: dict[str, Any], device: dict[str, Any]
    ) -> tuple[str, dict[str, Any] | None]:
        """Welke auto er aan dit laadpunt hangt: de keuze, en het profiel erbij.

        De keuze is `__guest__` voor een auto die hier niet woont, en dan is er
        geen profiel om bij te zoeken. Heeft niemand ooit gekozen terwijl er
        precies één auto bekend is, dan is dat hem.
        """
        chosen = ""
        for entry in settings.get("active_cars") or []:
            if entry.get("device") == device.get("id"):
                chosen = entry.get("car", "")
                break

        if chosen == "__guest__":
            return chosen, None

        cars = device.get("cars") or []
        profile = next((car for car in cars if car.get("id") == chosen), None)
        if profile is None and len(cars) == 1:
            profile = cars[0]
        return chosen, profile

    def _car(
        self, settings: dict[str, Any], device: dict[str, Any], charger: Charger
    ) -> Car:
        """The car that is plugged in, as far as anybody has said."""
        chosen, profile = self._chosen_car(settings, device)
        # Wat een gast of een auto zonder sensor laadt, telt niet bij de stand van een andere auto.
        vast_rij = self._soc_vast.get(device.get("id", ""))
        if vast_rij is not None and (profile is None or profile.get("soc_entity") != vast_rij.get("entity")):
            vast_rij["laatste"] = self._teller(device)

        if chosen == "__guest__":
            return Car(guest=True, phases=3, name=t("Gast"))

        if profile is None:
            return Car(phases=3)

        # Eén fase of drie, en niets ertussenin. "Allebei" bestond hier ook, en
        # dan werd het aantal fasen gemeten zolang er stroom liep en anders
        # aangenomen. Dat maakte elke voorspelling het traagste geval en zette de
        # coach op de verkeerde momenten aan het werk. Klopt de keuze niet met
        # wat er gemeten wordt, dan zegt `_fasetip` dat; zie daar.
        phases = {"one": 1, "three": 3}.get(profile.get("phases"), 3)
        # Behalve als de paal aantoonbaar op één fase laadt terwijl het profiel
        # drie zegt. Een Easee in automatische fasemodus kiest bij het starten
        # zelf, en die modus blijft: de eigenaar op 06-09-2026, "die is belangrijk
        # voor gastauto's." Zolang deze beurt loopt rekent de coach dan met wat
        # er werkelijk loopt, want anders denkt hij drie keer zo snel te zijn.
        device_id = device.get("id", "")
        gemeten = self._fase_nu.get(device_id)
        # Niet bij een Alfen die van de coach mag wisselen (v0.104.0): daar is een
        # fase zijn eigen keuze, en rekent het plan met wat de paal kan.
        phases_measured = (
            phases == 3 and gemeten == 1 and charger.charging and not self._fasewissel_aan(device)
        )
        if phases_measured:
            phases = 1

        # Het laadrendement van deze auto, gemeten of aangenomen (v0.94.0).
        gemeten_rendement = self._rendement_uit(settings, device_id, str(profile.get("id") or ""))
        self._rend_nu[device_id] = gemeten_rendement or CHARGE_EFFICIENCY

        # De auto zelf gaat voor. Zegt hij niets, dan telt wat de bewoner heeft
        # opgegeven, bijgewerkt met wat de paal er sindsdien in heeft gedaan.
        soc = _number(self.hass, profile.get("soc_entity"))
        geschat = False
        # Een stand die niet meer meebeweegt is geen stand (v0.176.0): dan rekent de coach
        # zoals bij een auto zonder accustand, en vraagt de kaart erom (`soc_ask`).
        vast = soc is not None and self._soc_vast_bij(device, profile, soc)
        if vast:
            soc = None
        if soc is not None:
            # Wat de sensor zelf zei blijft apart staan: `_soc_op` hoort tot
            # rust te komen zodra de sensor stilstaat, en de bijgetelde stand
            # loopt elke ronde door. Zie `_soc_bijgeteld`.
            self._soc_ruw[device_id] = soc
            soc = self._soc_bijgeteld(
                device_id, soc, float(profile.get("capacity_kwh") or 0)
            )
        else:
            self._soc_ruw.pop(device_id, None)
            soc = self._typed_soc(settings, device, profile)
            geschat = soc is not None
        if soc is None and not vast:
            soc = self._onthouden_soc(device, profile)
            geschat = soc is not None

        auto_id = str(profile.get("id") or "")
        self._auto_id[device_id] = auto_id
        self._auto_soc[device_id] = soc
        return Car(
            name=str(profile.get("name") or "").strip(),
            capacity_kwh=float(profile.get("capacity_kwh") or 0),
            phases=phases,
            phases_measured=phases_measured,
            max_amps=float(profile.get("max_amps") or 0),
            target_percent=self._doel.get(device_id) or float(profile.get("target_percent") or 100),
            soc_percent=soc,
            soc_estimated=geschat,
            tempo_per_band=self._tempo_uit(settings, device_id, auto_id),
            tempo_vanaf=self._tempo_vanaf(settings, device_id, auto_id),
            efficiency=gemeten_rendement,
        )

    def _zon_bijhouden(self, now: datetime, settings: dict[str, Any]) -> None:
        """Wat de zonverwachting voor dit uur beloofde, naast wat het dak gaf.

        Het dak en niet het overschot, en dat verschil is het hele punt. Het
        overschot is opbrengst min huisverbruik, en in de ochtend liggen die
        twee vlak bij elkaar; dan is de verhouding tussen voorspeld en gemeten
        overschot wilde onzin en zou één ochtend de hele middag bijstellen. In
        het virtuele huis kostte dat `dynamisch-zonnig` vijf cent op een dag
        waarop de voorspelling gewoon klopte. Wat de voorspeller voorspelt is
        de opbrengst van het dak, dus dat is ook wat er tegen zijn eigen
        belofte gelegd hoort te worden; het huisverbruik wordt al apart gemeten
        (`_huisverbruik`).

        Eén regel per ronde, van de woning en niet van een laadpunt.
        """
        if self._zon_reeks and self._zon_reeks[-1][0] >= now:
            return
        opbrengst = self._zon_w(settings)
        if opbrengst is None:
            return
        uur = now.replace(minute=0, second=0, microsecond=0)
        voorspeld = max(0.0, self._zon_kwh.get(uur, 0.0)) * 1000.0
        stap = 1.0
        if self._zon_reeks:
            stap = min(5.0, max(0.0, (now - self._zon_reeks[-1][0]).total_seconds() / 60.0))
        self._zon_reeks.append((now, voorspeld, max(0.0, opbrengst), stap))
        grens = now - ZON_VENSTER
        self._zon_reeks = [r for r in self._zon_reeks if r[0] >= grens]

    def _zon_gemeten(self, now: datetime) -> float | None:
        """Welk deel van de beloofde opbrengst er de afgelopen uren echt kwam.

        Nul tot één, of niets zolang er te weinig gemeten is of er te weinig
        beloofd was om een verhouding van te maken. Nooit boven één: meer zon
        verwachten dan voorspeld is een gok, en dit hoort een correctie te zijn
        en geen tweede voorspelling. Voor het uur waar de coach ín zit telt de
        meter toch al rechtstreeks.

        De eigenaar op 17-09-2026: de voorspeller zei 1,552 kWh voor het uur van
        16:00 en het dak deed 0,58. De coach verschoof zijn belofte van 16:00
        naar 17:00 en zou hem om 17:00 weer verschoven hebben. Zie
        `overschot_kwh` in planner.py.
        """
        grens = now - ZON_VENSTER
        binnen = [r for r in self._zon_reeks if r[0] >= grens]
        minuten = sum(stap for _, _, _, stap in binnen)
        if minuten < ZON_MEETTIJD_MIN:
            return None
        voorspeld = sum(w * stap for _, w, _, stap in binnen) / 60.0 / 1000.0
        if voorspeld < ZON_MIN_VOORSPELD:
            return None
        gemeten = sum(w * stap for _, _, w, stap in binnen) / 60.0 / 1000.0
        return max(0.0, min(1.0, gemeten / voorspeld))

    def _plafond_gemeten(self, device_id: str, now: datetime) -> float | None:
        """Wat er de afgelopen `PLAFOND_VENSTER` gemiddeld voor de paal overbleef.

        Uit het plafond van elke ronde (zekering min wat het huis trok, de
        lastbewaker, de groep; onder de ondergrens van de paal telt als nul),
        gewogen naar hoe lang elke ronde duurde. None zolang er minder dan
        `PLAFOND_MEETTIJD_MIN` minuten in het venster staan. Zie
        `structural_ceiling` in planner.py voor waar dit heen gaat.
        """
        if device_id in self._sessie:
            reeks = self._sessie[device_id].get("plafond_reeks") or []
        else:
            # De eerste ronde na een herstart: wat er bij de beurt bewaard was.
            reeks = (self._hervat.get(device_id) or {}).get("plafond_reeks") or []
        grens = now - PLAFOND_VENSTER
        binnen = [r for r in reeks if r[0] >= grens]
        minuten = sum(stap for _, _, stap in binnen)
        if minuten < PLAFOND_MEETTIJD_MIN:
            return None
        return sum(plafond * stap for _, plafond, stap in binnen) / minuten

    def _soc_vast_bij(self, device: dict[str, Any], profile: dict[str, Any], soc: float) -> bool:
        """Of de accustand van deze auto vastzit: hij verandert niet, en de paal levert (v0.176.0).

        Per laadpunt de stand, en wat de teller van de paal er sinds de laatste verandering in deed.
        De teller en niet de eigen meting, want die overleeft een herstart en een nieuwe beurt: de
        bus van 28-10-2026 ging tussendoor een uur van de kabel. Verandert de stand, dan begint het
        opnieuw, en een vaste stand die weer beweegt is weer gewoon een stand.
        """
        device_id = device.get("id", "")
        entity = profile.get("soc_entity")
        meter = self._teller(device)
        rij = self._soc_vast.get(device_id)
        if rij is None or rij.get("entity") != entity or abs(float(rij.get("waarde", -1.0)) - soc) > 1e-9:
            terug = bool(rij and rij.get("vast") and rij.get("entity") == entity)
            if terug:
                _LOGGER.warning("%s: de accustand van %s beweegt weer (%.0f%%)", device_id, entity, soc)
            self._soc_vast[device_id] = {"entity": entity, "waarde": soc, "kwh": 0.0, "laatste": meter,
                                         "vast": False, "gemeld": False, "terug": terug}
            self._soc_vast_onthouden(device_id)
            return False
        if meter is not None:
            vorige = rij.get("laatste")
            if vorige is not None and meter > float(vorige):
                rij["kwh"] = float(rij.get("kwh") or 0.0) + meter - float(vorige)
                rij["laatste"] = meter
                self._soc_vast_onthouden(device_id)
            rij["laatste"] = meter
        if rij.get("vast"):
            return True
        capacity = float(profile.get("capacity_kwh") or 0)
        if not capacity:
            return False
        erin = float(rij.get("kwh") or 0.0) * self._rend_nu.get(device_id, CHARGE_EFFICIENCY) / capacity * 100.0
        if erin < min(max(100.0 - soc + SOC_VAST_MARGE, SOC_VAST_MIN), SOC_VAST_PROCENT):
            return False
        rij["vast"] = True
        _LOGGER.warning(
            "%s: de accustand van %s staat op %.0f%% terwijl er sindsdien %.1f kWh in ging; de coach gelooft "
            "hem niet meer", device_id, entity, soc, float(rij.get("kwh") or 0.0),
        )
        self._soc_vast_onthouden(device_id)
        return True

    def _soc_vast_onthouden(self, device_id: str) -> None:
        rij = self._soc_vast.get(device_id)
        data = None
        if rij is not None:
            data = {k: rij.get(k) for k in ("entity", "waarde", "kwh", "laatste", "vast", "gemeld")}
        self._onthoud(f"accustand:{device_id}", data, meteen=bool(rij and rij.get("vast")))

    async def _async_soc_vast_melden(self, device: dict[str, Any], car: Car) -> None:
        """Eén melding als de accustand vastzit, en één regel in de geschiedenis als hij weer beweegt."""
        rij = self._soc_vast.get(device.get("id", ""))
        if rij is None:
            return
        auto = _hoofdletter(self._hoe_heet(car))
        if rij.get("terug"):
            rij["terug"] = False
            await self._async_tell(t("De accustand van {auto} wordt weer bijgewerkt.", auto=auto), telefoon=False)
        if rij.get("vast") and not rij.get("gemeld"):
            rij["gemeld"] = True
            self._soc_vast_onthouden(device.get("id", ""))
            await self._async_tell(
                t(
                    "De accustand van {auto} blijft op {stand}% staan, terwijl er {kwh} kWh in ging. Waarschijnlijk "
                    "wordt hij niet meer bijgewerkt. Tot hij weer iets meldt, rekent de coach zonder.",
                    auto=auto, stand=round(float(rij.get("waarde") or 0.0)),
                    kwh=getal(float(rij.get("kwh") or 0.0), 1),
                ),
                kritiek=True,
            )

    def _onthouden_soc(
        self, device: dict[str, Any], profile: dict[str, Any]
    ) -> float | None:
        """De laatste accustand van deze laadbeurt, bijgewerkt tot nu.

        Een auto die zijn percentage even niet doorgeeft is geen auto waarvan
        niemand de stand kent. Hij hangt nog aan dezelfde kabel, want zodra die
        eruit gaat is de hele laadbeurt vergeten. Dus telt wat hij het laatst
        zei, plus wat de paal er sindsdien in heeft gedaan, net als bij een
        stand die met de hand is opgegeven.

        Dit repareert een melding die op 25-08-2026 om 15:45 langskwam: de
        Ford-integratie viel een minuut weg en de kaart zei "De auto is vol"
        terwijl de bus op 80% stond. Diezelfde avond om 20:04 vroeg de coach om
        een accustand die hij eerder op de avond gewoon gezien had.
        """
        sessie = self._sessie.get(device.get("id", "")) or {}
        percent = sessie.get("soc_gezien")
        if percent is None:
            return None

        capacity = float(profile.get("capacity_kwh") or 0)
        meter = self._teller(device)
        sinds = sessie.get("soc_meter")
        if capacity and meter is not None and sinds is not None:
            geladen = max(0.0, meter - float(sinds)) * self._rend_nu.get(device.get("id", ""), CHARGE_EFFICIENCY)
            percent = float(percent) + geladen / capacity * 100.0
        return min(100.0, float(percent))

    def _auto_storing(self, profiel: dict[str, Any] | None) -> bool:
        """Of de laadstatus van de auto zegt dat hij in storing staat.

        Alleen met een `status_entity` in het profiel. Onbekend, onbeschikbaar of
        een woord dat de integratie niet kent ("Unsupported" bij de Ford, net na
        een herstart van Home Assistant) is geen storing.
        """
        entiteit = (profiel or {}).get("status_entity")
        if not entiteit:
            return False
        staat = self.hass.states.get(entiteit)
        if staat is None:
            return False
        woord = str(staat.state).lower()
        return any(deel in woord for deel in AUTO_STORING)

    def _proef_stand(
        self,
        now: datetime,
        device_id: str,
        profiel: dict[str, Any] | None,
        charger: Charger,
        mag: bool,
    ) -> str:
        """Wat het proefladen deze ronde aan de planner vraagt: "laden", "klaar" of niets.

        Een proef gaat open als de kabel erin gaat en het profiel het niet
        uitzet, en opnieuw als de laadstatus van de auto een storing meldt
        terwijl hij stilstaat. Dat laatste hooguit eens per `HERSTART_WACHT`
        en binnen dezelfde `PROEF_POGINGEN`. Alleen als de coach mag sturen:
        op een stand waarin hij alleen voorstelt laadt er niets, en dan zou
        een geslaagde proef er als een mislukte uitzien.
        """
        zat_erin = self._proef_kabel.get(device_id)
        self._proef_kabel[device_id] = charger.connected
        if not charger.connected:
            self._proef.pop(device_id, None)
            return ""
        proef = self._proef.get(device_id)
        # Alleen een kabel die erin gaat, niet een coach die opstart terwijl hij
        # er al in zat: dan zou elke herstart van Home Assistant een proef geven.
        if zat_erin is False and proef is None and (profiel or {}).get("proefladen", True):
            proef = self._proef[device_id] = {"fase": "open", "sinds": None, "pogingen": 0}
        if (
            self._auto_storing(profiel)
            and not charger.charging
            and (proef is None or proef["fase"] in ("klaar", "gedaan"))
        ):
            # Ook een geslaagde keer telt mee (`keer`): een laadstatus die na het
            # laden nog een tijd FAULT blijft zeggen, omdat de auto zijn stand pas
            # bij de volgende peiling bijwerkt, mag geen proef per kwartier geven.
            vorige = (proef or {}).get("laatste")
            keer = (proef or {}).get("keer", 0)
            if keer < PROEF_POGINGEN and (vorige is None or now - vorige >= HERSTART_WACHT):
                proef = self._proef[device_id] = {
                    "fase": "open", "sinds": None, "pogingen": (proef or {}).get("pogingen", 0),
                    "storing": True, "keer": keer + 1, "laatste": vorige,
                }
        if proef is None or not mag:
            return ""
        # Laadt de paal, dan neemt de auto stroom aan: geslaagd, en in déze ronde
        # al weer stoppen, zodat de proef niet langer duurt dan het aanlopen.
        if charger.charging and proef["fase"] in ("open", "bezig", "pauze"):
            proef["laatste"] = now
            if proef["fase"] == "open":
                proef["fase"] = "gedaan"
                return ""
            proef["fase"] = "klaar"
            proef["melden"] = bool(proef["pogingen"] or proef.get("storing"))
        # Een pauze is pas om als er ook echt een ronde 0 A naar de paal ging
        # (`gepauzeerd`); een ronde die eerder komt (een statuswissel) telt niet.
        if proef["fase"] == "pauze" and proef.get("gepauzeerd") and now - proef["sinds"] >= PROEF_PAUZE:
            proef["fase"], proef["gepauzeerd"] = "open", False
        if proef["fase"] in ("open", "bezig"):
            return "laden"
        if proef["fase"] == "klaar" and charger.charging:
            return "klaar"
        return ""

    async def _async_proef_na(
        self, now: datetime, device: dict[str, Any], car: Car, charger: Charger, decision: Decision
    ) -> None:
        """Bijhouden hoe de proef afliep, en het zeggen als hij niet lukt.

        Laadt de paal, dan neemt de auto stroom aan en is de proef geslaagd.
        Laadt hij na `PROEF_DUUR` nog niet, dan één ronde 0 A en een nieuwe
        start: dat is wat de Ford op 23-10-2026 uit zijn storing haalde. Na
        `PROEF_POGINGEN` keer één kritieke melding, want dan moet de bewoner
        er zelf bij, en dat kan nu nog: hij heeft net ingeplugd.
        """
        device_id = device.get("id", "")
        proef = self._proef.get(device_id)
        if proef is None:
            return
        fase = proef["fase"]
        if proef.pop("melden", False):
            # Gelukt na een mislukte poging of een storing (`_proef_stand`).
            await self._async_tell(
                t(
                    "{auto} aan {naam} nam eerst geen stroom aan. Na een nieuwe start van de "
                    "coach wel.",
                    auto=_hoofdletter(self._hoe_heet(car)),
                    naam=device.get("name") or t("de laadpaal"),
                ),
                telefoon=False,
            )
            return
        if fase == "klaar" and not charger.charging:
            proef["fase"] = "gedaan"
            return
        if fase == "pauze" and not decision.charge:
            proef["gepauzeerd"] = True
            return
        if fase not in ("open", "bezig"):
            return
        if not decision.rule.endswith("+proef"):
            # Geen proef deze ronde (de avondpiek, de zekering, de lastbewaking):
            # de tijd van een poging telt pas als er ook echt stroom aangeboden wordt.
            proef["fase"], proef["sinds"] = "open", None
            return
        if fase == "open":
            proef["fase"], proef["sinds"] = "bezig", now
            return
        if now - proef["sinds"] < PROEF_DUUR:
            return
        proef["pogingen"] += 1
        proef["laatste"] = now
        if proef["pogingen"] < PROEF_POGINGEN:
            proef["fase"], proef["sinds"] = "pauze", now
            _LOGGER.info(
                "%s: de auto nam bij het proefladen niets af; poging %s, opnieuw na een ronde 0 A",
                device_id, proef["pogingen"],
            )
            return
        proef["fase"] = "mislukt"
        await self._async_tell(
            t(
                "{auto} aan {naam} neemt geen stroom aan. De coach probeerde het {keer} keer. "
                "Trek de kabel er even uit en doe hem er weer in.",
                auto=_hoofdletter(self._hoe_heet(car)),
                naam=device.get("name") or t("de laadpaal"),
                keer=PROEF_POGINGEN,
            ),
            kritiek=True,
        )

    @staticmethod
    def _niet_vol(car: Car) -> bool:
        """Of de accustand zegt dat er nog iets in moet.

        Alleen als dat te weten is: een gast of een auto zonder accustand
        levert hier onwaar op, en dan is "klaar" van de paal het enige dat er
        is. Een auto die niet in Home Assistant zit telt mee zodra de bewoner
        zijn stand heeft opgegeven, want daarna telt de coach zelf verder met de
        teller van de paal (`_typed_soc`).

        "Vol" is hier het doel uit het autoprofiel en niet honderd procent. Wie
        zijn bus op 80% zet is op 80% klaar, en een herstart zou daar een auto
        wakker schudden die precies doet wat hem gevraagd is.
        """
        rest = energy_needed_kwh(car)
        return rest is not None and rest > 0 and not doel_bereikt(car)

    def _tempo_leren(
        self,
        now: datetime,
        settings: dict[str, Any],
        device: dict[str, Any],
        car: Car,
        charger: Charger,
        grid: Grid,
    ) -> None:
        """Onthouden wat deze auto per band van tien procent aankan.

        De eigenaar op 06-09-2026: "bepaalde auto's schroeven vanaf een bepaald
        procent zelf hun doorlaatbaarheid in ampère terug." Dat is alleen te
        meten als de auto zélf de rem is: de paal biedt meer dan hij neemt, en
        niets anders houdt hem tegen. Niet de coach (zijn limiet ligt hoger dan
        wat er loopt), niet de lastbewaker, niet de groep.

        Per band het gemiddelde van de remronden, en vanaf welke accustand hij
        begon te remmen (v0.128.0). Tot dan was het het laagste van de beurt,
        en dat gold voor de hele band. In de eerste woning werd dat 1,69 kW voor
        90 tot 100 procent, gemeten op 10-10-2026 om 06:12 vlak voor 100%,
        terwijl de auto tot 96% gewoon 9,15 kW nam: 4,85 uur waar het er 1,14
        waren. De eigenaar op 16-10-2026: "ik wil een gemiddelde hebben en niet
        de laagste band kiezen." Een gemiddelde over de hele band zou afhangen
        van wat de paal toen gaf (één fase of drie); dit niet, want onder de
        grens rekent `_uren_met_afbouw` met de paal en erboven met de auto.

        Het staat per auto in de instellingen (`car_pace`) en de volgende beurt
        rekent ermee, zie `hours_needed` in planner.py. Een nieuwe beurt
        overschrijft de banden die hij zelf meet, zodat een auto die vandaag
        anders doet dan vorige maand morgen ook anders gepland wordt; behalve
        een meting die minder hoog in de band kwam (`TEMPO_BEREIK`).
        """
        device_id = device.get("id", "")
        limiet = charger.limit_amps
        if charger.charging and limiet is not None:
            vorige = self._limiet_vorig.get(device_id)
            if vorige is not None and limiet > vorige:
                self._limiet_omhoog[device_id] = now
            self._limiet_vorig[device_id] = limiet
        else:
            self._limiet_vorig.pop(device_id, None)
        self._tempo_weerleggen(settings, device_id, car, charger, now)

        omhoog = self._limiet_omhoog.get(device_id)
        if (
            not charger.charging
            or charger.started_at is None
            or now - charger.started_at < timedelta(minutes=RAMP_MINUTES)
            # Net meer aangeboden: wat er nu loopt is een auto die nog bijkomt
            # en niet een auto die afbouwt. Zie `TEMPO_HERSTEL`.
            or (omhoog is not None and now - omhoog < TEMPO_HERSTEL)
            or car.guest
            or not car.capacity_kwh
            or car.soc_percent is None
            or charger.limit_amps is None
            or charger.actual_amps <= 0
            or charger.actual_amps >= charger.limit_amps - STEP_AMPS
            or held_back(charger)
            or charger.paused_by_balancer
        ):
            self._tempo_vorig.pop(device_id, None)
            return
        bewaker = beschikbaar_van_bewaker(grid)
        if bewaker is not None and charger.actual_amps >= bewaker - STEP_AMPS:
            self._tempo_vorig.pop(device_id, None)
            return
        groep = charger.circuit_amps
        if groep is not None and charger.actual_amps >= groep - STEP_AMPS:
            self._tempo_vorig.pop(device_id, None)
            return
        kw = round(watts_for(charger.actual_amps, car.phases) / 1000.0, 2)
        band = int(car.soc_percent // 10)
        if kw < TEMPO_ONDERGRENS:
            # Minder dan een paal op zijn laagste stand op één fase levert. Dat
            # is geen auto die gas terugneemt maar een auto die stilstaat, of
            # een sensor die nog niet bij is. Als tempo zou het onzin zijn: op
            # 17-09-2026 rekende 0,1 kW een band van tien procent op bijna
            # twintig uur.
            self._tempo_vorig.pop(device_id, None)
            return

        # Twee remronden achter elkaar voordat het telt, zoals `_eindtijd_vast`
        # bij de vaatwasser en `_fasen_stabiel` bij de fasen. Een stroomsensor
        # loopt een ronde achter, en één zo'n ronde is hier duur: op 17-09-2026
        # werd een tussenstand van 0,152 A het tempo van een hele band. Telt de
        # tweede, dan telt de eerste alsnog mee. Hetzelfde tempo hoeven ze niet
        # meer te geven: een auto die afbouwt zakt soms meer dan `TEMPO_SPELING`
        # per minuut, en die ronden horen juist in het gemiddelde.
        soc = round(car.soc_percent, 1)
        vorig = self._tempo_vorig.get(device_id)
        if vorig is None or vorig[0] != band:
            self._tempo_vorig[device_id] = (band, kw, soc, False)
            return
        meting = self._tempo_band.setdefault(device_id, {}).setdefault(
            band, {"som": 0.0, "n": 0, "van": soc, "tot": soc, "bewaard": None}
        )
        for r_kw, r_soc in ([(kw, soc)] if vorig[3] else [(vorig[1], vorig[2]), (kw, soc)]):
            meting["som"] += r_kw
            meting["n"] += 1
            meting["van"] = min(meting["van"], r_soc)
            meting["tot"] = max(meting["tot"], r_soc)
        self._tempo_vorig[device_id] = (band, kw, soc, True)

        banden = self._tempo_te_schrijven(settings, device_id)
        if banden:
            # Meteen onthouden en niet pas na het opslaan, anders schrijft de
            # ronde erna hetzelfde nog een keer.
            for band, rij in banden.items():
                self._tempo_band[device_id][band]["bewaard"] = (rij["kw"], rij["van"], rij["soc"])
            self.hass.async_create_task(
                self._async_tempo_schrijven(settings, device_id, banden, now)
            )

    def _tempo_te_schrijven(
        self, settings: dict[str, Any], device_id: str
    ) -> dict[int, dict[str, Any]]:
        """De banden van deze beurt die anders zijn dan wat er bewaard staat.

        Pas na twee remronden, en alleen als het gemiddelde `TEMPO_STAP`
        verschoof, de grens een halve procent of de meting een procent hoger
        kwam: zo schrijft hij bovenin hooguit om het procent en niet elke minuut.
        En een meting die minder hoog in de band kwam dan de bewaarde
        (`TEMPO_BEREIK`) vervangt die niet: een beurt tot 98% weet niet wat de
        auto tussen 98 en 100 doet, en die van daarvoor wel.
        """
        auto_id = self._auto_id.get(device_id)
        if not auto_id:
            return {}
        bewaard = self._tempo_bewaard(settings, device_id, auto_id)
        uit: dict[int, dict[str, Any]] = {}
        for band, meting in (self._tempo_band.get(device_id) or {}).items():
            if meting["n"] < 2:
                continue
            kw = round(meting["som"] / meting["n"], 2)
            vorige = meting["bewaard"]
            if vorige is not None and (
                abs(kw - vorige[0]) < TEMPO_STAP
                and abs(meting["van"] - vorige[1]) < 0.5
                and meting["tot"] - vorige[2] < 1.0
            ):
                continue
            if vorige is None and band in bewaard and bewaard[band][1] > meting["tot"] + TEMPO_BEREIK:
                continue
            uit[band] = {"kw": kw, "van": meting["van"], "soc": meting["tot"]}
        return uit

    def _tempo_weerleggen(
        self,
        settings: dict[str, Any],
        device_id: str,
        car: Car,
        charger: Charger,
        now: datetime,
    ) -> None:
        """Een bewaard tempo laten vallen zodra de auto aantoonbaar meer neemt.

        Een auto die bovenin gas terugneemt doet dat niet ineens weer minder:
        binnen een band loopt het tempo alleen maar af. Neemt hij bij dezelfde
        of een hogere accustand twee ronden achter elkaar duidelijk meer dan wat
        er voor die band bewaard staat, dan was die meting geen afbouw maar iets
        anders, en dan hoort hij weg. In de klantwoning stond er op 19-09-2026
        5,52 kW voor band 6, gemeten om 03:35 terwijl de Ford nog bijkwam van een
        verlaging; om 03:45 trok hij in diezelfde band 9,6 kW.

        Een rij van vóór v0.69.0 weet niet bij welke stand hij gemeten is en telt
        als gemeten onderin zijn band. Een echte afbouw die zo wegvalt meet de
        coach later in de band opnieuw.

        En niet alleen in de eigen band (v0.108.1): wat een auto bij een hogere
        accustand aanneemt, kon hij lager ook. In de klantwoning op 04-10-2026
        leerde de coach 5,98 kW voor 50 tot 60 procent, bij 59,7%, terwijl de Ford
        nog opstartte (eerst 6 A, dan 8,7, pas na negentien minuten 13,2 A). Om
        15:36:30 nam hij 9,1 kW, maar toen stond hij al op 61% en dus in de
        volgende band. Weerleggen kon alleen tussen 59,7 en 60%, en de Ford meldt
        per halve procent: tot 10-10 bleef die 5,98 kW staan, en elke beurt door
        die band rekende een half uur te lang.
        """
        auto_id = self._auto_id.get(device_id)
        if (
            not auto_id
            or not charger.charging
            or car.soc_percent is None
            or charger.actual_amps <= 0
        ):
            self._weerleg_vorig.pop(device_id, None)
            return
        band = int(car.soc_percent // 10)
        metingen = self._tempo_band.get(device_id) or {}
        # Wat er van deze beurt is gemeten gaat voor wat er bewaard staat. Een
        # gemiddelde (v0.128.0) weerleg je net zo: binnen een band loopt het
        # tempo alleen maar af, dus wat de auto na de meting nog duidelijk meer
        # neemt dan het gemiddelde ervan, kon hij tijdens de meting ook.
        bekend = dict(self._tempo_bewaard(settings, device_id, auto_id))
        for b, meting in metingen.items():
            if meting["n"] >= 2:
                bekend[b] = (meting["som"] / meting["n"], meting["tot"])
        kw_nu = watts_for(charger.actual_amps, car.phases) / 1000.0
        # Elke band tot en met deze, gemeten bij deze of een lagere stand, met
        # een tempo dat de auto nu duidelijk overtreft.
        kandidaten = {
            b for b, (kw, soc) in bekend.items()
            if b <= band and soc <= car.soc_percent and kw_nu > kw + TEMPO_SPELING
        }
        vorige = self._weerleg_vorig.get(device_id) or set()
        if not kandidaten:
            self._weerleg_vorig.pop(device_id, None)
            return
        for b in sorted(kandidaten & vorige):
            metingen.pop(b, None)
            self._tempo_vorig.pop(device_id, None)
            self.hass.async_create_task(
                self._async_tempo_wissen(settings, device_id, auto_id, b)
            )
        self._weerleg_vorig[device_id] = kandidaten - vorige

    async def _async_tempo_wissen(
        self, settings: dict[str, Any], device_id: str, auto_id: str, band: int
    ) -> None:
        """Eén band van deze auto uit de instellingen halen."""
        rows = [
            row
            for row in (settings.get("car_pace") or [])
            if isinstance(row, dict)
            and not (
                row.get("device") == device_id
                and row.get("car") == auto_id
                and row.get("band") == band
            )
        ]
        if len(rows) == len(settings.get("car_pace") or []):
            return
        try:
            saved = await async_get_store(self.hass).async_save({"car_pace": rows})
        except Exception:  # noqa: BLE001 - een tempo te veel is geen reden om te stoppen
            _LOGGER.exception("kon het laadtempo van de auto niet bijwerken")
            return
        self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": saved})

    @staticmethod
    def _tempo_bewaard(
        settings: dict[str, Any], device_id: str, auto_id: str
    ) -> dict[int, tuple[float, float]]:
        """Per band het bewaarde tempo en de accustand waarbij het gemeten is."""
        uit: dict[int, tuple[float, float]] = {}
        for row in settings.get("car_pace") or []:
            if (
                isinstance(row, dict)
                and row.get("device") == device_id
                and row.get("car") == auto_id
            ):
                try:
                    band = int(row["band"])
                    soc = row.get("soc")
                    uit[band] = (float(row["kw"]), float(soc) if soc is not None else band * 10.0)
                except (KeyError, TypeError, ValueError):
                    continue
        return uit

    async def _async_tempo_schrijven(
        self,
        settings: dict[str, Any],
        device_id: str,
        banden: dict[int, dict[str, Any]],
        now: datetime,
    ) -> None:
        """De gemeten banden van deze beurt in de instellingen zetten.

        Per band het gemiddelde tempo (`kw`), vanaf welke accustand de auto
        remde (`van`) en tot welke hij gemeten is (`soc`). Zie `_tempo_leren`.
        """
        auto_id = self._auto_id.get(device_id)
        if not auto_id or not banden:
            return
        rows = [
            row
            for row in (settings.get("car_pace") or [])
            if isinstance(row, dict)
            and not (
                row.get("device") == device_id
                and row.get("car") == auto_id
                and row.get("band") in banden
            )
        ]
        for band, rij in sorted(banden.items()):
            rows.append({"device": device_id, "car": auto_id, "band": band, **rij,
                         "at": now.isoformat()})
        try:
            saved = await async_get_store(self.hass).async_save({"car_pace": rows})
        except Exception:  # noqa: BLE001 - een gemist tempo is geen reden om te stoppen
            _LOGGER.exception("kon het laadtempo van de auto niet bewaren")
            return
        # Zoals `_async_forget`: de andere lezers horen het via de eventbus. De
        # instellingen van deze ronde zelf niet aanraken, want in de proeven is
        # `saved` hetzelfde object en dan wist een clear() alles.
        self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": saved})

    @staticmethod
    def _tempo_uit(settings: dict[str, Any], device_id: str, auto_id: str) -> dict[int, float]:
        """Wat er over deze auto per band bewaard is.

        Rijen onder `TEMPO_ONDERGRENS` gaan eruit. Die konden er tot v0.66.0 in
        komen (zie `_tempo_leren`), ze staan dan in de opslag van een klant, en
        een herstart haalt ze er niet uit. Thuis stond er op 17-09-2026 0,1 kW
        voor band 0; daarmee rekende de klaar-tijdregel 21,41 uur waar het er
        1,93 waren.

        En een rij zonder `van` is het laagste punt van vóór v0.128.0, dat voor
        de hele band gold; die telt niet meer (zie `_tempo_leren`). De volgende
        beurt door die band meet het gemiddelde.
        """
        return {band: kw for band, (kw, _van) in ChargerCoach._tempo_rijen(settings, device_id, auto_id).items()}

    @staticmethod
    def _tempo_vanaf(settings: dict[str, Any], device_id: str, auto_id: str) -> dict[int, float]:
        """Per band vanaf welke accustand de auto zelf remde. Zie `_tempo_uit`."""
        return {band: van for band, (_kw, van) in ChargerCoach._tempo_rijen(settings, device_id, auto_id).items()}

    @staticmethod
    def _tempo_rijen(
        settings: dict[str, Any], device_id: str, auto_id: str
    ) -> dict[int, tuple[float, float]]:
        """De bruikbare rijen van `car_pace` voor deze auto: band, kW en grens."""
        uit: dict[int, tuple[float, float]] = {}
        for row in settings.get("car_pace") or []:
            if (
                isinstance(row, dict)
                and row.get("device") == device_id
                and row.get("car") == auto_id
            ):
                try:
                    kw = float(row["kw"])
                    van = float(row["van"])
                    if kw >= TEMPO_ONDERGRENS:
                        uit[int(row["band"])] = (kw, van)
                except (KeyError, TypeError, ValueError):
                    continue
        return uit

    def _soc_bijgeteld(self, device_id: str, gemeten: float, capacity: float) -> float:
        """De stand van de auto, plus wat de paal sinds die stand geleverd heeft.

        Hetzelfde wat `_typed_soc` voor een opgegeven stand doet, maar dan voor
        een auto die zijn stand zelf meldt. Dat was nodig omdat niet elke
        accusensor per procent meldt.

        de eigen Ford meldt per tien procent, ongeveer elk half uur. Op 17-09-2026
        stond hij van 21:58:43 tot 22:30:37 op zeventig; in die achtentwintig
        minuten leverde de paal 4.072 W, dus 1,90 kWh aan de stekker en bijna
        negen procentpunt in de accu. Om 22:26 zei de kaart "nog 2,2 kWh, vol
        rond 23:00" terwijl er 0,18 kWh in ging en de bus om 22:29 op zijn doel
        stond. De eigenaar: "dat hoeft helemaal niet en is onzin."

        Geen gok maar de eigen meting van de paal (`_eigen`, zie `_geladen`),
        want die loopt wél per ronde mee. Begrensd op één stap van de sensor,
        zodat een correctie nooit groter kan worden dan de onnauwkeurigheid die
        hij repareert; die stap wordt geleerd uit de sprongen die de sensor zelf
        maakt en begint bij één procent. Zo is over-corrigeren uitgesloten, en
        dat is de richting die ertoe doet: te hoog rekenen laat de coach te
        vroeg stoppen.
        """
        eigen = float((self._eigen.get(device_id) or {}).get("kwh") or 0.0)
        ijk = self._soc_ijk.get(device_id)
        if ijk is None or abs(ijk[0] - gemeten) > 1e-9:
            self._rendement_meten(device_id, gemeten, eigen, capacity)
            if ijk is not None and 0.0 < gemeten - ijk[0] <= SOC_STAP_MAX:
                sprong = gemeten - ijk[0]
                eerder = self._soc_stap.get(device_id)
                self._soc_stap[device_id] = sprong if eerder is None else min(eerder, sprong)
            self._soc_ijk[device_id] = (gemeten, eigen)
            return gemeten
        if not capacity:
            return gemeten
        erbij = max(0.0, eigen - ijk[1]) * self._rend_nu.get(device_id, CHARGE_EFFICIENCY) / capacity * 100.0
        return min(100.0, gemeten + min(erbij, self._soc_stap.get(device_id, SOC_STAP_START)))

    def _rendement_meten(self, device_id: str, soc: float, eigen: float, capacity: float) -> None:
        """Het laadrendement van de auto aan deze paal, uit zijn eigen sensor.

        De bewoner van de eerste woning op 23-09-2026: 78 kWh, van 60 naar 90%, is
        23,4 kWh, "nog te laden is 23,4 in plaats van 26." De 26 was 23,4 gedeeld
        door een aangenomen rendement van 90%, en een aanname hoort niet in de
        coach als hij het kan meten. Dat kan: wat de accustand stijgt, maal de
        capaciteit, tegenover wat de paal in dezelfde tijd leverde (`_eigen`).
        Over minstens `REND_MIN_PROCENT` en `REND_MIN_KWH`, en alleen een uitkomst
        tussen `REND_LAAGST` en `REND_HOOGST`. Een stand die daalt is een nieuwe
        auto of een nieuwe beurt: dan begint de meting opnieuw.
        """
        if not capacity:
            return
        start = self._rend_start.get(device_id)
        if start is None or soc < start[0] or eigen < start[1]:
            self._rend_start[device_id] = (soc, eigen)
            return
        erbij = soc - start[0]
        geleverd = eigen - start[1]
        if erbij < REND_MIN_PROCENT or geleverd < REND_MIN_KWH:
            return
        rendement = erbij / 100.0 * capacity / geleverd
        if REND_LAAGST <= rendement <= REND_HOOGST:
            self._rend_meting[device_id] = rendement
        self._rend_start[device_id] = (soc, eigen)

    @staticmethod
    def _rendement_uit(settings: dict[str, Any], device_id: str, auto_id: str) -> float | None:
        """Het gemeten laadrendement van deze auto aan deze paal, of None."""
        for row in settings.get("car_efficiency") or []:
            if isinstance(row, dict) and row.get("device") == device_id and row.get("car") == auto_id:
                try:
                    waarde = float(row["eff"])
                except (KeyError, TypeError, ValueError):
                    return None
                return waarde if REND_LAAGST <= waarde <= REND_HOOGST else None
        return None

    async def _async_rendement_bewaren(self, settings: dict[str, Any], device_id: str) -> None:
        """Een nieuwe meting bij het lopende gemiddelde van deze auto."""
        meting = self._rend_meting.pop(device_id, None)
        auto_id = self._auto_id.get(device_id)
        if meting is None or not auto_id:
            return
        rows = [r for r in (settings.get("car_efficiency") or []) if isinstance(r, dict)]
        oud = next((r for r in rows if r.get("device") == device_id and r.get("car") == auto_id), None)
        if oud is None:
            rows.append({"device": device_id, "car": auto_id, "eff": round(meting, 4), "n": 1})
        else:
            n = min(int(oud.get("n") or 1), REND_MAX_N - 1)
            oud["eff"] = round((float(oud.get("eff") or meting) * n + meting) / (n + 1), 4)
            oud["n"] = n + 1
        try:
            saved = await async_get_store(self.hass).async_save({"car_efficiency": rows})
        except Exception:  # noqa: BLE001 - een gemiste meting is geen reden om te stoppen
            _LOGGER.exception("kon het laadrendement niet bewaren")
            return
        self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": saved})

    def _typed_soc(
        self,
        settings: dict[str, Any],
        device: dict[str, Any],
        profile: dict[str, Any],
    ) -> float | None:
        """Wat de bewoner opgaf, plus wat er sindsdien in is gegaan.

        Zo hoeft er hooguit één keer per sessie iets ingevuld te worden. De
        teller van de laadpaal telt alles wat hij ooit geleverd heeft, dus het
        verschil met de stand van toen is precies wat er daarna in deze auto is
        gegaan. Daar gaat het laadrendement nog af, want niet alles wat de paal
        levert komt in de accu terecht.
        """
        capacity = float(profile.get("capacity_kwh") or 0)
        if not capacity:
            return None

        entry = next(
            (
                row
                for row in (settings.get("car_soc") or [])
                if isinstance(row, dict)
                and row.get("device") == device.get("id")
                and row.get("car") == profile.get("id")
            ),
            None,
        )
        if entry is None or entry.get("percent") is None:
            return None

        percent = float(entry["percent"])
        meter = self._teller(device)
        since = entry.get("meter")
        # Tot v0.94.0 bewaarde het paneel de kale toestand van de teller, en die
        # staat bij een Alfen in Wh. Zo'n stand ligt een factor duizend boven
        # wat `_teller` in kWh leest.
        if meter is not None and since is not None and meter > 0 and float(since) > meter * 100:
            since = float(since) / 1000.0
        if meter is not None and since is not None:
            geladen = max(0.0, meter - float(since)) * self._rend_nu.get(device.get("id", ""), CHARGE_EFFICIENCY)
            percent += geladen / capacity * 100.0
        return min(100.0, percent)

    # Waar de tijd aan opging, in woorden die een bewoner herkent. Zelfstandig
    # geformuleerd, zodat er "20 minuten naar ..." voor kan staan zonder dat het
    # kromme taal wordt.
    VERTRAGING = {
        "user-hold": nt("de pauze die je zelf aanzette"),
        "no-room": nt("een aansluiting die vol zat"),
        "held-back": nt("de lastbewaking van je aansluiting"),
        "balancer-paused": nt("de lastbewaking van je aansluiting"),
        "waiting-for-car": nt("een auto die geen stroom afnam"),
        "waiting-for-auth": nt("een paal die op goedkeuring wachtte"),
        "no-soc": nt("wachten op je accustand"),
        "wait-for-sun": nt("wachten op je eigen zon"),
        "wait-for-sun-today": nt("wachten op je eigen zon"),
        "zon-wacht": nt("wachten op genoeg zon"),
        "wait-for-price": nt("wachten op een goedkoper uur"),
        "too-early": nt("de tijden die je hebt ingesteld"),
    }

    # ------------------------------------------------------------------
    # Wat een laadbeurt kost en bespaart
    #
    # De eigenaar op 05-09-2026: "Kunnen we ergens een overzichtje maken wat we
    # hebben bespaard? Dat is natuurlijk het belangrijkste voor de klant." Het
    # ijkpunt is de prijs op het moment van inpluggen: "bereken die prijs
    # wanneer die gestopt is en gewacht heeft met laden op een goedkoop moment.
    # Dus de prijs vanaf het inpluggen." Elke kWh die later goedkoper werd
    # geladen, of uit eigen zon kwam, telt tegen die prijs.
    #
    # Alleen gemeten getallen: het vermogen van de paal per ronde, de prijs van
    # dat uur, en het zonoverschot van dat moment. Ontbreekt een prijs, dan is
    # de besparing van die beurt onbekend en staat dat erbij.
    # ------------------------------------------------------------------

    def _prijs_nu(
        self, settings: dict[str, Any], now: datetime
    ) -> tuple[float | None, float | None]:
        """Wat een kWh nu kost en wat teruglevering nu opbrengt, of None."""
        rows = self._prices(settings)
        if rows:
            for rij in rows:
                if rij["start"] <= now < rij["end"]:
                    return rij["price"], rij.get("feed_in")
            return None, None
        tarief = self._tarief(settings)
        return tarief.buy, tarief.feed_in

    @staticmethod
    def _geld_uit_regel(open_beurt: dict[str, Any], now: datetime) -> dict[str, Any]:
        """De tellers van een beurt zoals hij in de opslag stond."""
        ingeplugd = _tijdstip(open_beurt.get("plugged_at"))
        if ingeplugd is not None:
            ingeplugd = ingeplugd.replace(tzinfo=None)
        basis = open_beurt.get("baseline") or {}
        return {
            "ingeplugd": ingeplugd or now,
            "ijk_prijs": open_beurt.get("ref_price"),
            "ijk_terug": open_beurt.get("ref_feed_in"),
            "kwh": float(open_beurt.get("kwh") or 0.0),
            "zon_kwh": float(open_beurt.get("solar_kwh") or 0.0),
            "betaald": float(open_beurt.get("paid") or 0.0),
            "zon_winst": float(open_beurt.get("solar_saved") or 0.0),
            "accu_kwh": float(open_beurt.get("battery_kwh") or 0.0),
            "net_eur": float(open_beurt.get("grid_cost") or 0.0),
            "net_eur_onbekend": open_beurt.get("grid_cost") is None and float(open_beurt.get("kwh") or 0.0) > 0,
            "onbekend_kwh": float(open_beurt.get("unknown_kwh") or 0.0),
            "basis_kwh": float(basis.get("kwh") or 0.0),
            "basis_kosten": float(basis.get("cost") or 0.0),
            "basis_onbekend": float(basis.get("unknown_kwh") or 0.0),
            "basis_punten": [list(p) for p in (basis.get("points") or [])],
        }

    @staticmethod
    def _geld_leeg(now: datetime, koop: float | None, terug: float | None) -> dict[str, Any]:
        """Een verse teller."""
        return {
            "ingeplugd": now,
            "ijk_prijs": koop,
            "ijk_terug": terug,
            "kwh": 0.0,
            "zon_kwh": 0.0,
            "betaald": 0.0,
            # Wat de eigen zon scheelde tegenover inkopen: het deel van
            # bespaard dat van de zon komt. Zie `_geld_bij`.
            "zon_winst": 0.0,
            # Wat er uit de thuisbatterij kwam, en wat er werkelijk van het net
            # kwam in euro (v0.101.0). Zie `_herkomst_bij`.
            "accu_kwh": 0.0,
            "net_eur": 0.0,
            "onbekend_kwh": 0.0,
            # Wat dezelfde tijd op vol vermogen vanaf het inpluggen gekost had,
            # alles van het net: de maat waartegen bespaard wordt. Zie `_basis_bij`.
            "basis_kwh": 0.0,
            "basis_kosten": 0.0,
            "basis_onbekend": 0.0,
            "basis_punten": [],
            "basis_uur": None,
            "terugrekenen": False,
            "bewaard": None,
        }

    def _geld_begin(
        self,
        device_id: str,
        now: datetime,
        settings: dict[str, Any] | None,
        ingestapt: bool = False,
    ) -> dict[str, Any]:
        """De teller van een nieuwe beurt, of die van de beurt die bij de
        herstart nog open stond.

        Loopt de beurt al bij de eerste ronde (`ingestapt`) en staat er niets
        in de opslag, dan is het inplugmoment onbekend en dus ook de prijs van
        toen. Dan zoekt `_async_terugrekenen` het op in de recorder; lukt dat
        niet, dan komt er geen ijkpunt: de kilowatturen en de kosten tellen,
        de besparing blijft leeg. De eigenaar op 05-09-2026, bij "bespaard -0,01" op
        een beurt van vrijdagavond die de coach pas om 15:03 zag: "waarom is
        er vandaag niks bespaard?" Een ijkpunt van het verkeerde uur is erger
        dan geen ijkpunt.
        """
        open_beurt = self._beurt_open.pop(device_id, None)
        if open_beurt is not None:
            basis_oud = open_beurt.get("baseline") or {}
            zonder_maat = (
                float(basis_oud.get("kwh") or 0.0) + 0.5 < float(open_beurt.get("kwh") or 0.0)
            )
            if open_beurt.get("resumed") or open_beurt.get("ref_price") is None or zonder_maat:
                # Een beurt die een vorige coach al hervat had zonder het
                # echte inplugmoment (v0.49.x: met de prijs van het
                # herstartuur als ijkpunt, of zonder, of zonder maat).
                # Opnieuw beginnen en terugrekenen vanaf het echte inpluggen;
                # de opslag dekt ook wat die vorige coach al telde, dus zijn
                # tellers gaan niet dubbel mee. Zijn regel gaat straks weg,
                # tenzij het terugrekenen niet lukt: dan telt hij door.
                geld = self._geld_leeg(now, None, None)
                geld["terugrekenen"] = True
                geld["opruimen"] = [open_beurt.get("id")]
                geld["terugval"] = open_beurt
                return geld
            geld = self._geld_uit_regel(open_beurt, now)
            geld.update({"basis_uur": None, "terugrekenen": False, "bewaard": None,
                         "hervat_bekend": True})
            return geld
        koop, terug = self._prijs_nu(settings, now) if settings is not None else (None, None)
        if ingestapt:
            # Het inplugmoment is onbekend; `_async_terugrekenen` zoekt het
            # straks op in de recorder en vult de tellers van vóór nu aan.
            koop, terug = None, None
        geld = self._geld_leeg(now, koop, terug)
        geld["terugrekenen"] = ingestapt
        return geld

    def _basis_bij(
        self,
        geld: dict[str, Any],
        stap_min: float,
        cap_w: float,
        settings: dict[str, Any],
        now: datetime,
    ) -> None:
        """De maat waartegen bespaard wordt, per ronde bijgeteld.

        De eigenaar op 05-09-2026: "bereken die prijs wanneer die gestopt is en
        gewacht heeft met laden op een goedkoop moment. Dus de prijs vanaf het
        inpluggen." En: "een min getal bij besparen kan helemaal niet." Dus:
        wat dezelfde kilowatturen gekost hadden als de paal vanaf het
        inpluggen gewoon op vol vermogen was doorgegaan, uur na uur tegen de
        prijs van dat uur, alles van het net. Dat loopt hier als een tweede
        teller mee, elke ronde, ook als de coach zelf niets doet: want dan had
        die andere paal wél geladen. Per uur een ijkpunt (`basis_punten`),
        zodat voor elke hoeveelheid kilowatturen af te lezen is wat ze op die
        manier gekost hadden.

        Tot v0.60.0 telde de zon die er toen over was in de maat mee tegen de
        terugleverprijs, en dan was wat er op eigen zon geladen werd geen
        besparing. De eigenaar op 09-09-2026: "wat je op zonne-energie laadt bespaar
        je natuurlijk ook door minder stroom in te kopen." Dat deel staat nu
        apart in `zon_winst` (zie `_geld_bij`); de rest van bespaard is het
        wachten op een goedkoper uur.
        """
        if stap_min <= 0 or cap_w <= 0:
            return
        if geld.get("basis_uur") is not None and geld["basis_uur"] != now.hour:
            geld.setdefault("basis_punten", []).append(
                [round(geld.get("basis_kwh", 0.0), 3), round(geld.get("basis_kosten", 0.0), 4)]
            )
        geld["basis_uur"] = now.hour
        kwh_stap = cap_w / 1000.0 * stap_min / 60.0
        koop, _ = self._prijs_nu(settings, now)
        geld["basis_kwh"] = geld.get("basis_kwh", 0.0) + kwh_stap
        if koop is None:
            geld["basis_onbekend"] = geld.get("basis_onbekend", 0.0) + kwh_stap
            return
        geld["basis_kosten"] = geld.get("basis_kosten", 0.0) + kwh_stap * koop

    @staticmethod
    def _basis_kosten_voor(geld: dict[str, Any], kwh: float) -> float | None:
        """Wat `kwh` op vol vermogen vanaf het inpluggen gekost had."""
        punten = [tuple(p) for p in geld.get("basis_punten") or []]
        punten.append((geld.get("basis_kwh", 0.0), geld.get("basis_kosten", 0.0)))
        if kwh <= 0:
            return 0.0
        vorig = (0.0, 0.0)
        for k, c in punten:
            if k >= kwh:
                if k - vorig[0] <= 1e-9:
                    return c
                return vorig[1] + (c - vorig[1]) * (kwh - vorig[0]) / (k - vorig[0])
            vorig = (k, c)
        # De maat is nog niet zo ver als de coach: dan doortrekken tegen de
        # laatste prijs die de maat kende. Kan alleen als de paal harder ging
        # dan zijn eigen maximum, en dat is een afronding.
        if not punten or punten[-1][0] <= 1e-9:
            return None
        k, c = punten[-1]
        return c / k * kwh

    def _geld_bij(
        self,
        geld: dict[str, Any],
        kwh_stap: float,
        watt: float,
        grid: Grid | None,
        settings: dict[str, Any],
        now: datetime,
    ) -> None:
        """Eén ronde erbij: hoeveel er in ging, hoeveel daarvan zon was, en
        wat het kostte. Zon is wat er zonder de paal naar het net was gegaan,
        tot wat de paal trok; de rest kwam van het net tegen de prijs van nu.
        Eigen zon wordt gerekend tegen wat teruglevering opgebracht had, want
        dat is wat die kWh je werkelijk kostte."""
        if kwh_stap <= 0:
            return
        over_w = max(0.0, grid.surplus_w) if grid is not None else 0.0
        zon_deel = min(1.0, over_w / watt) if watt > 0 else 0.0
        zon_kwh = kwh_stap * zon_deel
        net_kwh = kwh_stap - zon_kwh
        koop, terug = self._prijs_nu(settings, now)
        geld["kwh"] += kwh_stap
        geld["zon_kwh"] += zon_kwh
        self._herkomst_bij(geld, settings, kwh_stap, zon_deel, koop)
        if koop is None:
            # Geen prijs op dit moment, bijvoorbeeld een prijssensor die even
            # weg is: deze kilowatturen tellen mee in het laden en niet in het
            # geld. Ze staan apart, zodat de rest van de beurt gewoon telt.
            geld["onbekend_kwh"] = geld.get("onbekend_kwh", 0.0) + kwh_stap
            return
        geld["betaald"] += net_kwh * koop + zon_kwh * (terug if terug is not None else 0.0)
        geld["zon_winst"] = geld.get("zon_winst", 0.0) + zon_kwh * max(
            0.0, koop - (terug if terug is not None else 0.0)
        )

    def _beurt_regel(
        self,
        device: dict[str, Any],
        car: Car | None,
        sessie: dict[str, Any],
        now: datetime,
        klaar: bool,
    ) -> dict[str, Any]:
        """De beurt zoals hij in de opslag en op het scherm komt."""
        geld = sessie.get("geld") or {}
        ingeplugd: datetime = geld.get("ingeplugd") or now
        kwh = round(float(geld.get("kwh") or 0.0), 3)
        betaald = round(float(geld.get("betaald") or 0.0), 4)
        ijk = geld.get("ijk_prijs")
        onbekend_kwh = round(float(geld.get("onbekend_kwh") or 0.0), 3)
        # De maat: wat de kilowatturen waarvan de prijs bekend was gekost
        # hadden op vol vermogen vanaf het inpluggen. Zolang het inplugmoment
        # onbekend is (`terugrekenen` loopt nog) is er geen maat.
        ijk_kosten = None
        if not geld.get("terugrekenen") and ijk is not None:
            ijk_kosten = self._basis_kosten_voor(geld, max(0.0, kwh - onbekend_kwh))
            if ijk_kosten is not None:
                ijk_kosten = round(ijk_kosten, 4)
        begon = sessie.get("begon")
        return {
            "id": f"{device.get('id', '')}:{ingeplugd.replace(microsecond=0).isoformat()}",
            "device": device.get("id", ""),
            "name": device.get("name") or t("Laadpaal"),
            "kind": "laden",
            "car": self._hoe_heet(car) if car is not None else "",
            "plugged_at": ingeplugd.replace(microsecond=0).isoformat(),
            "started": begon.replace(microsecond=0).isoformat() if begon else None,
            "ended": now.replace(microsecond=0).isoformat() if klaar else None,
            "kwh": kwh,
            "solar_kwh": round(float(geld.get("zon_kwh") or 0.0), 3),
            "paid": betaald,
            "ref_price": ijk,
            "ref_feed_in": geld.get("ijk_terug"),
            "ref_cost": ijk_kosten,
            # Nooit onder nul: de coach kan hooguit evenveel betalen als die
            # andere paal, en een paar cent eronder is een afronding.
            "saved": None if ijk_kosten is None else round(max(0.0, ijk_kosten - betaald), 4),
            "solar_saved": round(float(geld.get("zon_winst") or 0.0), 4),
            **self._herkomst_velden(geld),
            "price_unknown": ijk is None or onbekend_kwh > 0,
            "unknown_kwh": onbekend_kwh,
            # Voor de kaart na een herstart (v0.106.0): de kWh zoals het verslag
            # ze telt, naast die van het geld hierboven, en de accustand van
            # begin en eind. Zie `_beurt_kaart`.
            **{
                {"kwh": "charged_kwh"}.get(sleutel, sleutel): waarde
                for sleutel, waarde in self._beurt_kaart(device, sessie, actief=False).items()
                # Alleen wat de kaart van v0.106.0 had: het ingeplugde moment, het
                # geld en de zon van de laadpaalkaart (v0.111.0) staan hierboven al
                # in de regel zelf, en mogen die niet overschrijven.
                if sleutel in ("kwh", "soc_start", "soc_end", "soc_estimated")
            },
            "baseline": {
                "kwh": round(float(geld.get("basis_kwh") or 0.0), 3),
                "cost": round(float(geld.get("basis_kosten") or 0.0), 4),
                "unknown_kwh": round(float(geld.get("basis_onbekend") or 0.0), 3),
                "points": [list(p) for p in (geld.get("basis_punten") or [])][-240:],
            },
            # Hervat: de coach stapte midden in de beurt in én kent het
            # inplugmoment niet. Na een herstart met de regel nog in de opslag,
            # of na terugrekenen, is het inplugmoment wél bekend.
            "resumed": bool(sessie.get("ingestapt")) and not geld.get("hervat_bekend"),
            "complete": klaar,
            # Wat de coach nodig heeft om na een herstart door te gaan waar hij
            # was (v0.98.0); zie `_hervat_uit`. Een afgesloten beurt heeft het
            # niet meer nodig.
            **({} if klaar else {"session": self._sessie_bewaren(device.get("id", ""), sessie, now)}),
        }

    def _sessie_bewaren(self, device_id: str, sessie: dict[str, Any], now: datetime) -> dict[str, Any]:
        """Het deel van een lopende laadbeurt dat een herstart moet overleven."""
        begon = sessie.get("begon")
        laadt_sinds = self._since.get(device_id) if self._laadde.get(device_id) else None
        grens = now - PLAFOND_VENSTER
        return {
            "at": now.replace(microsecond=0).isoformat(),
            "begon": begon.replace(microsecond=0).isoformat() if begon else None,
            "meter": sessie.get("meter"),
            "geijkt": bool(sessie.get("geijkt")),
            "ijk_kwh": round(float(sessie.get("ijk_kwh") or 0.0), 4),
            # Wat de coach zelf telde sinds de laatste stap van de teller (v0.112.0).
            # Zie `_staart`.
            "staart_kwh": round(self._staart(device_id, sessie), 4),
            "soc_begin": sessie.get("soc_begin"),
            "laadt_sinds": laadt_sinds.replace(microsecond=0).isoformat() if laadt_sinds else None,
            "plafond": [
                [moment.replace(microsecond=0).isoformat(), round(amps, 2), round(stap, 3)]
                for moment, amps, stap in sessie.get("plafond_reeks") or []
                if moment >= grens
            ],
            "kwijt": {k: round(v, 2) for k, v in (sessie.get("kwijt") or {}).items()},
            "gemeld": sorted(str(x) for x in sessie.get("gemeld") or set()),
            "ingestapt": bool(sessie.get("ingestapt")),
            # Een Alfen die klaar is, en wanneer de ene herstart gestuurd is
            # (v0.99.0): anders begint na een herstart van Home Assistant de
            # lus van "klaar" en "weer aanbieden" opnieuw.
            "klaar": device_id in self._afgeleid_klaar,
            "herstart_op": (
                self._herstart_gedaan[device_id].replace(microsecond=0).isoformat()
                if self._herstart_gedaan.get(device_id) else None
            ),
        }

    def _beurt_schrijven(self, entry: dict[str, Any]) -> None:
        """Naar de opslag, buiten de ronde om: de ronde wacht er niet op."""

        async def schrijf() -> None:
            try:
                await async_get_beurten(self.hass).async_upsert(entry)
            except Exception:  # noqa: BLE001 - de opslag mag de ronde niet kosten
                _LOGGER.exception("kon de laadbeurt niet bewaren")

        self.hass.async_create_task(schrijf())

    # --- terugrekenen na een herstart midden in een beurt ---------------

    async def _async_geschiedenis(
        self, entity_id: str | None, start: datetime, einde: datetime
    ) -> list[tuple[datetime, str]]:
        """De toestanden van een sensor tussen twee momenten, uit de recorder,
        als (lokaal tijdstip, toestand). Leeg als de recorder er niet is."""
        if not entity_id:
            return []
        try:
            from homeassistant.components.recorder import get_instance, history

            begin = dt_util.as_utc(start.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE))
            eind = dt_util.as_utc(einde.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE))
            gevonden = await get_instance(self.hass).async_add_executor_job(
                history.state_changes_during_period, self.hass, begin, eind, entity_id
            )
        except Exception as fout:  # noqa: BLE001 - zonder recorder is er geen geschiedenis
            _LOGGER.warning("kon de geschiedenis van %s niet lezen: %s", entity_id, fout)
            return []
        uit: list[tuple[datetime, str]] = []
        for st in (gevonden or {}).get(entity_id, []):
            uit.append((dt_util.as_local(st.last_changed).replace(tzinfo=None), str(st.state)))
        return uit

    async def _async_uurgemiddelden(
        self, entity_ids: list[str], start: datetime, einde: datetime
    ) -> dict[str, dict[datetime, float]]:
        """Het gemiddelde per uur uit de statistieken van Home Assistant (v0.130.1).

        Voor wat verder terug ligt dan de tien dagen waarin de recorder elke
        toestand bewaart: de accustand en de prijzen van toen. Per sensor
        {lokaal uur: gemiddelde}; leeg als de recorder er niet is.
        """
        ids = {e for e in entity_ids if e}
        if not ids:
            return {}
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import statistics_during_period

            begin = dt_util.as_utc(start.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE))
            eind = dt_util.as_utc(einde.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE))
            gevonden = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period, self.hass, begin, eind, ids, "hour", None, {"mean"}
            )
        except Exception as fout:  # noqa: BLE001 - zonder recorder geen statistieken
            _LOGGER.warning("kon de statistieken niet lezen: %s", fout)
            return {}
        uit: dict[str, dict[datetime, float]] = {}
        for entity_id, rijen in (gevonden or {}).items():
            for rij in rijen or []:
                moment = rij.get("start")
                if isinstance(moment, (int, float)):
                    moment = datetime.fromtimestamp(moment, tz=timezone.utc)
                if not isinstance(moment, datetime) or rij.get("mean") is None:
                    continue
                uur = dt_util.as_local(moment).replace(tzinfo=None, minute=0, second=0, microsecond=0)
                uit.setdefault(entity_id, {})[uur] = float(rij["mean"])
        return uit

    async def async_herreken_batterij(
        self, settings: dict[str, Any], device_id: str, van: date, toepassen: bool = False
    ) -> dict[str, Any]:
        """"Opgeleverd" van een batterij opnieuw uitrekenen vanaf een dag (v0.130.1).

        In de eerste woning telde het kasboek van 22-09 tot 19-10-2026
        teruglevering als € 0 (de terugleverprijs was onbekend), en stond
        "Opgeleverd" te hoog. Dit rekent het opnieuw met de prijzen zoals het
        contract ze nu beschrijft, uit de kwartieren van het net en de batterij
        (de eigen opslag) en de accustand en de prijzen per uur (de statistieken
        van Home Assistant). Per kwartier en niet per minuut, dus het is de beste
        schatting achteraf; zie `herreken` in batterij.py.

        Zonder `toepassen` alleen wat het zou worden, zodat het paneel het eerst
        kan laten zien. Met: de dagen vanaf `van` vervangen, en de lopende
        tellingen van vandaag opnieuw beginnen.
        """
        device = next((d for d in settings.get("devices") or []
                       if d.get("id") == device_id and d.get("type") == "thuisbatterij"), None)
        if device is None:
            return {"fout": t("Die batterij bestaat niet.")}
        nu = _moment(None)
        # Tot het begin van dit uur: wat daarna komt telt de ronde zelf.
        tot = nu.replace(minute=0, second=0, microsecond=0)
        begin = datetime(van.year, van.month, van.day)
        if begin >= tot:
            return {"fout": t("Kies een dag in het verleden.")}
        rij = self._batterij_rij(settings, device_id)
        b = self._batterij_van(nu, settings, device, rij)
        bronnen = settings.get("sources") or {}
        eigen = device.get("entities") or {}
        getekend = bronnen.get("grid_mode") == "signed"
        net_ids = [bronnen.get("grid_signed")] if getekend else [bronnen.get("grid_import"), bronnen.get("grid_export")]
        bat_ids = [device.get("entity"), eigen.get("charge_power"), eigen.get("discharge_power")]
        ids = sorted({e for e in net_ids + bat_ids if e})
        kwartieren = await self._async_kwartieren(ids, begin, tot)
        per = {e: {int(r["start"]): r for r in kwartieren.get(e, [])} for e in ids}

        def gemiddeld(entity_id: str | None, moment: int) -> float | None:
            r = per.get(entity_id, {}).get(moment) if entity_id else None
            return None if r is None or r.get("gemiddeld") is None else float(r["gemiddeld"])

        contract = settings.get("contract") or {}
        d = contract.get("dynamic") or {}
        dynamisch = contract.get("type") == "dynamic"
        all_in_id = d.get("all_in_entity") if dynamisch and d.get("source") == "all_in" else ""
        markt_id = d.get("market_entity") if dynamisch and d.get("market_entity") != d.get("all_in_entity") else ""
        uur = await self._async_uurgemiddelden([eigen.get("soc"), all_in_id, markt_id], begin, tot)
        kwartier_markt = await self._async_marktprijzen(markt_id, begin.date(), (tot - timedelta(seconds=1)).date()) if markt_id else {}
        lat = getattr(self.hass.config, "latitude", None)
        lon = getattr(self.hass.config, "longitude", None)
        zone = dt_util.get_default_time_zone()
        zonder_prijs = 0

        def prijs(moment: datetime) -> tuple[float | None, float | None]:
            nonlocal zonder_prijs
            # Een vast contract, of een eerder vast contract van die dag: de
            # prijs van toen (v0.136.0). Tot dan het tarief van nu, voor elk
            # kwartier, ook van voor een contractwissel.
            koop, terug = self._vast_op(contract, moment)
            if koop is not None or not dynamisch:
                if koop is None:
                    zonder_prijs += 1
                return koop, terug
            u = moment.replace(minute=0, second=0, microsecond=0)
            markt = kwartier_markt.get(moment.replace(second=0, microsecond=0))
            if markt is None and markt_id:
                markt = uur.get(markt_id, {}).get(u)
            all_in = uur.get(all_in_id, {}).get(u) if all_in_id else None
            if all_in is None and markt is not None:
                all_in = prijsopbouw.inkoop(markt, d)["totaal"]
            if all_in is None:
                zonder_prijs += 1
                return None, None
            dag = prijsopbouw.overdag(u.replace(tzinfo=zone), (u + timedelta(hours=1)).replace(tzinfo=zone), lat, lon)
            return all_in, prijsopbouw.terug(markt, all_in, d, self._saldeert(contract, moment), dag)["bedrag"]

        stappen = []
        for moment in sorted({t for e in ids for t in per.get(e, {})}):
            start = dt_util.as_local(datetime.fromtimestamp(moment, tz=timezone.utc)).replace(tzinfo=None)
            if getekend:
                g = gemiddeld(bronnen.get("grid_signed"), moment)
                net_w = None if g is None else (-g if bronnen.get("grid_signed_invert") else g)
            else:
                invoer, export = gemiddeld(bronnen.get("grid_import"), moment), gemiddeld(bronnen.get("grid_export"), moment)
                net_w = None if invoer is None and export is None else (invoer or 0.0) - (export or 0.0)
            getal = gemiddeld(device.get("entity"), moment)
            if getal is not None:
                bat_w = -getal if (device.get("battery") or {}).get("power_invert") else getal
            else:
                laden, ontladen = gemiddeld(eigen.get("charge_power"), moment), gemiddeld(eigen.get("discharge_power"), moment)
                bat_w = None if laden is None and ontladen is None else (laden or 0.0) - (ontladen or 0.0)
            soc = uur.get(eigen.get("soc"), {}).get(start.replace(minute=0, second=0, microsecond=0)) if eigen.get("soc") else None
            stappen.append((start, 900.0, net_w, bat_w, soc))

        dagen, voorraad = herreken(
            stappen, prijs, bodem=b.bodem, capacity_kwh=b.capacity_kwh, rte=b.rte,
            max_charge_w=b.max_charge_w, max_discharge_w=b.max_discharge_w,
        )
        vanaf = van.isoformat()
        oud_kasboek = {k: float(v) for k, v in (rij.get("earned_days") or {}).items()}
        oud_echt = dict(self._opgeleverd_dagen(rij))
        voor = sum(oud_echt.get(k, oud_kasboek.get(k, 0.0)) for k in oud_kasboek if k >= vanaf)
        na = sum(w["realized"] for w in dagen.values())
        uit = {
            "van": vanaf, "dagen": len(dagen), "kwartieren": len(stappen), "zonder_prijs": zonder_prijs,
            "voor": round(voor, 2), "na": round(na, 2), "toegepast": False,
            # Waar de marktprijs van toen vandaan kwam, voor de uitleg op het paneel.
            "nordpool": bool(kwartier_markt),
        }
        if not toepassen or not dagen:
            return uit
        kasboek = {k: v for k, v in oud_kasboek.items() if k < vanaf}
        echt = {k: float(v) for k, v in oud_echt.items() if k < vanaf}
        zon_dagen = {k: float(v) for k, v in (rij.get("solar_stored_days") or {}).items() if k < vanaf}
        for dag, w in dagen.items():
            kasboek[dag] = round(w["earned"], 5)
            echt[dag] = round(w["realized"], 5)
            zon_dagen[dag] = round(w["solar"], 5)
        await self._async_batterij_bewaren(settings, device_id, {
            "earned_days": kasboek, "earned_total": round(sum(kasboek.values()), 5),
            "realized_days": echt, "realized_total": round(sum(echt.values()), 5),
            "solar_stored_days": zon_dagen, "stock_euro": round(voorraad.euro, 5),
        })
        # De lopende tellingen beginnen opnieuw vanaf het uur waar de
        # herberekening ophield, met de voorraad die daaruit kwam.
        sessie = self._batterij_sessie(device_id)
        sessie.update(geld={}, opgeleverd={}, zon={}, voorraad=voorraad, bewaard_op=nu)
        uit["toegepast"] = True
        return uit

    def _vast_op(self, contract: dict[str, Any], moment: datetime) -> tuple[float | None, float | None]:
        """Wat een kWh op een moment in het verleden kostte en opbracht, bij een vaste prijs (v0.136.0).

        Zoals `prijsOp` in geld.js zonder de verdeling per afrekenperiode: een
        eerder contract van die dag gaat voor; anders het contract van nu, met
        na `NETTING_ENDS` de bedragen van na salderen. Met salderen de
        inkoopprijs min de kosten per kWh (`prijsopbouw.kosten_per_kwh`); in de
        lopende afrekenperiode ook zoals de coach het nu ziet (`_saldeert`).
        (None, None) bij een dynamisch contract zonder eerder vast contract van
        die dag: dan komt de prijs uit de prijssensor.
        """
        dag = moment.date().isoformat()
        periode = _periode_op(contract, dag)
        fixed = contract.get("fixed") or {}
        if periode is None and contract.get("country") == "PT":
            # Portugal (v0.137.0): het tijdvak van dat moment.
            pt = contract.get("pt") or {}
            koop = tarifas.preco(pt, tarifas.periodo(_bewust(moment), pt.get("tarifa"), pt.get("ciclo")))
            return (koop, tarifas.terug(pt)) if koop is not None else (None, None)
        if periode is not None and periode.get("type") == "dynamic":
            return None, None
        if periode is not None and float(periode.get("all_in_price") or 0) > 0:
            koop: float | None = float(periode["all_in_price"])
        elif contract.get("type") == "dynamic":
            return None, None
        else:
            koop = float(fixed["all_in_price"]) if fixed.get("all_in_price") is not None else None
        if koop is None:
            return None, None
        saldeert = self._salderen(contract, moment)
        begin = _afrekenstart(contract.get("billing_start"), _moment(None).date())
        if saldeert and begin is not None and moment.date() >= begin and self._netto_terug() is True:
            saldeert = False
        if saldeert:
            return koop, koop - prijsopbouw.kosten_per_kwh(fixed, True)
        if periode is not None and float(periode.get("feed_in_tariff") or 0) > 0:
            return koop, float(periode["feed_in_tariff"])
        vergoeding, kosten = self._teruglevering(fixed, moment, False)
        return koop, vergoeding - kosten

    async def async_herreken_beurten(
        self, settings: dict[str, Any], van: date, toepassen: bool = False
    ) -> dict[str, Any]:
        """De opgeslagen beurten opnieuw uitrekenen met het contract van die dag (v0.136.0).

        De eigenaar op 19-10-2026, nadat zijn contract was rechtgezet: "Kan je dan
        ook de prijzen die eerder genoemd werden in de coach aanpassen de
        historie want ik denk dat dat dan ook niet meer klopt?" Historie In geld
        rekent elke keer opnieuw met het contract; Sessies niet, want elke beurt
        bewaart wat hij kostte en bespaarde toen hij liep. Daar rekende de zon
        nog tegen de terugleverprijs van het oude formulier.

        Alleen bij een vaste prijs, van nu of van een eerder contract van die
        dag (`_vast_op`): dan is de prijs over de hele beurt dezelfde, en volgt
        alles uit de kilowatturen die de beurt al telde (`_herreken_beurt`). Bij
        een dynamisch contract hing de prijs van het uur af en bewaart een beurt
        niet wanneer hij welke kWh nam; die blijven zoals ze zijn. Lopende
        beurten ook: die rekent de ronde zelf.

        Zonder `toepassen` alleen wat het zou worden.
        """
        contract = settings.get("contract") or {}
        vanaf = van.isoformat()
        nieuw: list[dict[str, Any]] = []
        overgeslagen = 0
        voor = {"paid": 0.0, "saved": 0.0, "solar_saved": 0.0}
        na = dict(voor)
        for beurt in await async_get_beurten(self.hass).async_list():
            begin = str(beurt.get("plugged_at") or beurt.get("started") or "")
            if begin[:10] < vanaf or not beurt.get("complete"):
                continue
            try:
                moment = datetime.fromisoformat(begin)
            except ValueError:
                overgeslagen += 1
                continue
            koop, terug = self._vast_op(contract, moment.replace(tzinfo=None))
            if koop is None or terug is None:
                overgeslagen += 1
                continue
            herrekend = _herreken_beurt(beurt, koop, terug)
            for sleutel in voor:
                voor[sleutel] += float(beurt.get(sleutel) or 0.0)
                na[sleutel] += float(herrekend.get(sleutel) or 0.0)
            nieuw.append(herrekend)
        uit = {
            "van": vanaf, "beurten": len(nieuw), "overgeslagen": overgeslagen,
            "voor": {k: round(v, 2) for k, v in voor.items()},
            "na": {k: round(v, 2) for k, v in na.items()},
            "toegepast": False,
        }
        if toepassen and nieuw:
            store = async_get_beurten(self.hass)
            for beurt in nieuw:
                await store.async_upsert(beurt)
            uit["toegepast"] = True
        return uit

    async def _async_kwartieren(
        self, entity_ids: list[str], start: datetime, einde: datetime
    ) -> dict[str, list[dict[str, float]]]:
        """De kwartieren uit de eigen opslag, of leeg als die er niet is."""
        try:
            return await async_get_archive(self.hass).async_lees(entity_ids, start, einde)
        except Exception as fout:  # noqa: BLE001
            _LOGGER.warning("kon de kwartieropslag niet lezen: %s", fout)
            return {}

    async def _async_terugrekenen(
        self, device: dict[str, Any], settings: dict[str, Any], tot: datetime
    ) -> dict[str, Any] | None:
        """Wat er in een beurt gebeurde vóór de coach hem zag.

        De eigenaar op 05-09-2026: "kan je niet historisch terugrekenen?" Ja: de
        recorder weet wanneer de kabel erin ging en wat een kWh toen kostte,
        en de eigen kwartieropslag weet wat de paal, de zon en het net daarna
        per kwartier deden. Daaruit komen dezelfde tellers als `_geld_bij` en
        `_basis_bij` live bijhouden. Alleen gemeten getallen; ontbreekt er
        iets, dan komt er niets terug en blijft het ijkpunt onbekend.
        """
        entities = device.get("entities") or {}
        status = entities.get("status")
        venster = timedelta(days=3)
        toestanden = await self._async_geschiedenis(status, tot - venster, tot)
        plug: datetime | None = None
        vorige: str | None = None
        for moment, toestand in toestanden:
            if vorige == "disconnected" and toestand != "disconnected":
                plug = moment
            vorige = toestand
        if plug is None or plug >= tot:
            return None

        # De prijs per moment: bij een dynamisch contract uit de geschiedenis
        # van de prijssensor, bij een vast contract het tarief.
        contract = settings.get("contract") or {}
        dynamic = contract.get("dynamic") or {}
        prijzen: list[tuple[datetime, float]] = []
        markt: list[tuple[datetime, float]] = []
        if contract.get("type") == "dynamic":
            bron = dynamic.get("all_in_entity") if dynamic.get("source") == "all_in" else dynamic.get("market_entity")
            for moment, toestand in await self._async_geschiedenis(bron, plug - timedelta(hours=1), tot):
                try:
                    prijzen.append((moment, float(toestand)))
                except ValueError:
                    continue
            if dynamic.get("source") != "all_in":
                prijzen = [(m, self._all_in(p, dynamic)) for m, p in prijzen]
            if not prijzen:
                prijzen = await self._async_reserveverloop(dynamic, plug - timedelta(hours=1), tot)
            if not self._saldeert(contract) and dynamic.get("market_entity"):
                for moment, toestand in await self._async_geschiedenis(
                    dynamic.get("market_entity"), plug - timedelta(hours=1), tot
                ):
                    try:
                        markt.append((moment, float(toestand)))
                    except ValueError:
                        continue
            if not prijzen:
                return None
        tarief = self._tarief(settings)
        bonus = float(dynamic.get("feed_in_bonus") or 0)
        kosten_saldo = prijsopbouw.kosten_per_kwh(dynamic, True) - bonus
        kosten = prijsopbouw.kosten_per_kwh(dynamic, False) - bonus
        opslag = float(dynamic.get("supplier_markup") or 0) * (
            1 + float(dynamic.get("vat_percent") or 0) / 100
        )

        def laatste(reeks: list[tuple[datetime, float]], moment: datetime) -> float | None:
            waarde = None
            for m, w in reeks:
                if m <= moment:
                    waarde = w
                else:
                    break
            return waarde

        def prijs_op(moment: datetime) -> tuple[float | None, float | None]:
            if contract.get("country") == "PT":
                return self._vast_op(contract, moment)
            if contract.get("type") != "dynamic":
                return tarief.buy, tarief.feed_in
            koop = laatste(prijzen, moment)
            if koop is None:
                return None, None
            if self._saldeert(contract):
                return koop, koop - opslag - kosten_saldo
            m = laatste(markt, moment)
            return koop, (m - kosten) if m is not None else None

        # De kwartieren: de paal, en het net zoals `_read` het leest.
        sources = settings.get("sources") or {}
        paal = device.get("entity")
        if not paal:
            return None
        netten = _netmeters(sources)
        rijen = await self._async_kwartieren([paal, *netten], plug - timedelta(minutes=15), tot)
        paal_rijen = rijen.get(paal) or []
        if not paal_rijen:
            return None
        per_start: dict[str, dict[int, float]] = {
            e: {int(r["start"]): float(r.get("gemiddeld") or 0.0) for r in rijen.get(e) or []} for e in netten
        }
        # Vol vermogen: het maximum van de paal op de fasen van de auto.
        fasen = 3
        for auto in device.get("cars") or []:
            if auto.get("phases"):
                fasen = {"one": 1, "three": 3}.get(auto["phases"], 3)
                break
        cap_w = watts_for(16.0, fasen)
        try:
            cap_w = watts_for(
                float((entities.get("max_limit") and _number(self.hass, entities.get("max_limit"))) or 16.0),
                fasen,
            )
        except Exception:  # noqa: BLE001
            pass

        uit = {
            "ingeplugd": plug, "kwh": 0.0, "zon_kwh": 0.0, "betaald": 0.0, "zon_winst": 0.0,
            "net_eur": 0.0, "onbekend_kwh": 0.0,
            "basis_kwh": 0.0, "basis_kosten": 0.0, "basis_onbekend": 0.0, "basis_punten": [],
        }
        uit["ijk_prijs"], uit["ijk_terug"] = prijs_op(plug)
        uur: int | None = None
        for rij in paal_rijen:
            t0 = datetime.fromtimestamp(int(rij["start"]))
            t1 = t0 + timedelta(minutes=15)
            if t1 <= plug or t0 >= tot:
                continue
            sec = float(rij.get("seconden") or 0.0)
            if t0 < plug:
                sec = min(sec, (t1 - plug).total_seconds())
            if t1 > tot:
                sec = min(sec, (tot - t0).total_seconds())
            if sec <= 0:
                continue
            paal_w = max(0.0, float(rij.get("gemiddeld") or 0.0))
            # Naar het net positief, met de andere meter waar die van `grid_mode` niets zegt (v0.170.0).
            afname = _net_afname(sources, per_start, int(rij["start"]))
            netto: float | None = None if afname is None else -afname
            over = max(0.0, netto + paal_w) if netto is not None else 0.0
            koop, terug = prijs_op(max(t0, plug))
            if uur is not None and uur != t0.hour:
                uit["basis_punten"].append([round(uit["basis_kwh"], 3), round(uit["basis_kosten"], 4)])
            uur = t0.hour
            kwh = paal_w / 1000.0 * sec / 3600.0
            zon = kwh * (min(1.0, over / paal_w) if paal_w > 0 else 0.0)
            uit["kwh"] += kwh
            uit["zon_kwh"] += zon
            basis = cap_w / 1000.0 * sec / 3600.0
            uit["basis_kwh"] += basis
            if koop is None:
                uit["onbekend_kwh"] += kwh
                uit["basis_onbekend"] += basis
                continue
            uit["betaald"] += (kwh - zon) * koop + zon * (terug if terug is not None else 0.0)
            uit["zon_winst"] += zon * max(0.0, koop - (terug if terug is not None else 0.0))
            # Uit de kwartieropslag is niet te zien wat een batterij deed: wat
            # geen zon was telt hier als net.
            uit["net_eur"] += (kwh - zon) * koop
            uit["basis_kosten"] += basis * koop
        return uit

    async def _async_terugrekenen_toepassen(
        self, device: dict[str, Any], settings: dict[str, Any] | None, tot: datetime
    ) -> None:
        """Het teruggerekende deel bij de lopende tellers optellen."""
        device_id = device.get("id", "")
        try:
            terug = await self._async_terugrekenen(device, settings or {}, tot)
        except Exception:  # noqa: BLE001 - liever geen ijkpunt dan een ronde die omvalt
            _LOGGER.exception("terugrekenen van de laadbeurt mislukt")
            terug = None
        sessie = self._sessie.get(device_id)
        geld = (sessie or {}).get("geld") if sessie else None
        if geld is None:
            return
        geld["terugrekenen"] = False
        terugval = geld.pop("terugval", None)
        if terug is None and terugval is not None:
            # Terugrekenen lukte niet (geen recorder, geen kwartieren): dan
            # toch verder met wat de vorige coach al geteld had, want dat is
            # beter dan opnieuw bij nul beginnen.
            terug = self._geld_uit_regel(terugval, tot)
            geld["opruimen"] = [
                weg for weg in (geld.get("opruimen") or []) if weg != terugval.get("id")
            ]
        if terug is None:
            return
        # De regel die al onder het herstartmoment in de opslag stond krijgt
        # straks een andere sleutel (het echte inplugmoment); de oude weg.
        oud_moment: datetime = geld.get("ingeplugd") or tot
        oud_id = f"{device_id}:{oud_moment.replace(microsecond=0).isoformat()}"
        for weg in [oud_id, *(geld.pop("opruimen", None) or [])]:
            if not weg:
                continue
            try:
                await async_get_beurten(self.hass).async_remove(weg)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("kon de voorlopige regel van de laadbeurt niet weghalen")
        for sleutel in ("kwh", "zon_kwh", "betaald", "zon_winst", "onbekend_kwh", "basis_kwh", "basis_kosten", "basis_onbekend"):
            geld[sleutel] = geld.get(sleutel, 0.0) + terug[sleutel]
        if not geld.get("net_eur_onbekend"):
            geld["net_eur"] = float(geld.get("net_eur") or 0.0) + terug.get("net_eur", 0.0)
        # De punten van na de herstart schuiven op met wat ervoor gebeurde.
        rk, rc = terug["basis_kwh"], terug["basis_kosten"]
        geld["basis_punten"] = terug["basis_punten"] + [
            [round(k + rk, 3), round(c + rc, 4)] for k, c in (geld.get("basis_punten") or [])
        ]
        geld["ingeplugd"] = terug["ingeplugd"]
        geld["ijk_prijs"] = terug["ijk_prijs"]
        geld["ijk_terug"] = terug["ijk_terug"]
        geld["hervat_bekend"] = True
        geld["bewaard"] = None  # meteen naar de opslag bij de volgende ronde

    async def _async_bij_stop(self, _event: Any = None) -> None:
        """Home Assistant gaat uit: elke lopende beurt nu naar de opslag, en
        daarna de apparaten teruggeven.

        Bij een herstart van Home Assistant wordt `async_unload_entry` niet
        aangeroepen en dus `async_stop` ook niet; alleen dit event komt. Tot
        23-09-2026 bleef de batterij daardoor bij elke herstart op zijn laatste
        opdracht staan (in de eerste woning: 235 W ontladen in de externe
        modus, twee minuten lang, tot de coach terug was; bij 2,5 kW in een leeg
        huis was dat leeglopen naar het net geweest) en bleef een boiler zonder
        stroom. Het teruggeven gebeurt hier dus zelf, en wordt afgewacht, want
        een taak die bij het afsluiten nog in de wachtrij staat wordt niet meer
        gedraaid.

        **Maar bij een herstart blijft de batterij in de externe modus, op 0 W**
        (v0.96.0). In eigen verbruik doet de batterij zelf nul op de meter, en
        met een ladende auto is dat de auto voeden: in de eerste woning op
        23-09-2026 om 23:53 gaf de Anker tijdens de herstart 3,45 kW aan de
        Tesla, tot de coach om 23:55:13 terug was. De eigenaar: "bij herstart
        accu op 0 en dan pas kijken." Stil blijven staan kan geen kwaad; na de
        herstart kijkt de coach zelf weer. Het echt uitzetten van de integratie
        (`async_stop`) geeft hem wel terug, want dan komt de coach niet terug.

        **En daarna besluit de coach niets meer** (v0.108.4). Home Assistant doet
        er na dit event nog even over, en in die tijd vallen de integraties één
        voor één weg. Bij de eigenaar op 11-10-2026 zette dit de batterij om
        14:41:40 op 0 W in de externe modus, viel om 14:41:40 de slimme meter
        weg, en draaide om 14:41:46 gewoon de minuutronde: "Batterij doet zelf
        nul op de meter" en "Laadpaal: laden op 16 A ... om hem wakker te
        maken", op een paal die tot 20:00 moest wachten. Tijdens de herstart
        laadde de bus op 10,8 kW, en gaf de batterij er 3,45 kW aan, tot de
        coach om 14:43:20 terug was. Dus: geen rondes en geen regelaar meer, en
        een ronde die al liep eerst laten aflopen.
        """
        self._stopt = True
        for _ in range(STOP_WACHT_STAPPEN):
            if not self._running and not any(s.get("bezig") for s in self._batterij.values()):
                break
            await self._sleep(KNOP_WACHT_STAP)
        try:
            settings = await async_get_store(self.hass).async_load()
        except Exception:  # noqa: BLE001
            settings = {}
        apparaten = {d.get("id", ""): d for d in settings.get("devices") or []}
        nu = _moment(None)
        for device_id, sessie in list(self._sessie.items()):
            if not sessie.get("geld"):
                continue
            device = apparaten.get(device_id) or {"id": device_id}
            try:
                await async_get_beurten(self.hass).async_upsert(
                    self._beurt_regel(device, None, sessie, nu, klaar=False)
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("kon de lopende laadbeurt niet bewaren bij het stoppen")
        try:
            # Wat de coach onthoudt, voor na de herstart (v0.172.0).
            self._meldingen_onthouden()
            await async_get_geheugen(self.hass).async_bewaar(dt_util.utcnow())
        except Exception:  # noqa: BLE001
            _LOGGER.exception("kon het geheugen niet bewaren bij het stoppen")
        await self._async_batterijen_los(herstart=True)
        await self._async_boilers_aan()

    async def _async_beurten_laden(self) -> None:
        """De beurten die bij de vorige keer nog liepen, voor `_geld_begin`."""
        try:
            for entry in await async_get_beurten(self.hass).async_open():
                device_id = str(entry.get("device") or "")
                self._beurt_open[device_id] = entry
                if entry.get("kind") == "laden" and isinstance(entry.get("session"), dict):
                    hervat = self._hervat_uit(entry["session"])
                    if hervat is not None:
                        self._hervat[device_id] = hervat
                        if hervat.get("klaar"):
                            self._afgeleid_klaar.add(device_id)
                        if hervat.get("herstart_op") is not None:
                            self._herstart_gedaan[device_id] = hervat["herstart_op"]
        except Exception:  # noqa: BLE001 - zonder geschiedenis begint hij gewoon opnieuw
            _LOGGER.exception("kon de lopende laadbeurten niet lezen")
        # De laatste afgesloten beurt per paal, voor de kaart (v0.106.0). De
        # lijst staat op inplugmoment, dus de laatste die telt wint.
        try:
            for entry in await async_get_beurten(self.hass).async_list():
                if entry.get("kind") != "laden" or not entry.get("complete"):
                    continue
                kaart = self._beurt_kaart_uit(entry)
                if kaart is not None:
                    self._vorige_beurt[str(entry.get("device") or "")] = kaart
        except Exception:  # noqa: BLE001 - dan staat er tot de volgende beurt niets
            _LOGGER.exception("kon de laatste laadbeurten niet lezen")

    @staticmethod
    def _hervat_uit(bewaard: dict[str, Any]) -> dict[str, Any] | None:
        """Wat er van een lopende laadbeurt bewaard was, terug in de vorm van de sessie.

        None als het ouder is dan `HERVAT_MAX` of niet te lezen.
        """
        def tijd(tekst: Any) -> datetime | None:
            try:
                return datetime.fromisoformat(str(tekst)) if tekst else None
            except ValueError:
                return None

        op = tijd(bewaard.get("at"))
        if op is None or _moment() - op > HERVAT_MAX:
            return None
        reeks = []
        for rij in bewaard.get("plafond") or []:
            try:
                moment = tijd(rij[0])
                if moment is not None:
                    reeks.append((moment, float(rij[1]), float(rij[2])))
            except (TypeError, ValueError, IndexError):
                continue
        return {
            "begon": tijd(bewaard.get("begon")),
            "meter": bewaard.get("meter"),
            "geijkt": bool(bewaard.get("geijkt")),
            "ijk_kwh": float(bewaard.get("ijk_kwh") or 0.0),
            "staart_kwh": float(bewaard.get("staart_kwh") or 0.0),
            "soc_begin": bewaard.get("soc_begin"),
            "laadt_sinds": tijd(bewaard.get("laadt_sinds")),
            "plafond_reeks": reeks,
            "kwijt": {str(k): float(v) for k, v in (bewaard.get("kwijt") or {}).items()},
            "gemeld": set(bewaard.get("gemeld") or []),
            "ingestapt": bool(bewaard.get("ingestapt")),
            "klaar": bool(bewaard.get("klaar")),
            "herstart_op": tijd(bewaard.get("herstart_op")),
        }

    def _bijhouden(
        self,
        now: datetime,
        device: dict[str, Any],
        car: Car,
        charger: Charger,
        window: Window,
        decision: Decision,
        grid: Grid | None = None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        """Onthouden wat er in deze laadbeurt gebeurt, om het na te kunnen vertellen."""
        device_id = device.get("id", "")
        if not charger.connected and not self._echt_los.get(device_id, True):
            # De paal zegt (nog) niets: niets afsluiten en niets vergeten. Na een
            # herstart is dat de integratie die nog laadt (v0.98.0).
            return
        if not charger.connected:
            # Een beurt die nog open stond in de opslag terwijl de kabel er nu
            # niet in zit: de kabel ging eruit terwijl Home Assistant herstartte.
            # Afsluiten met wat er bekend is, want anders blijft hij eeuwig lopen.
            open_beurt = self._beurt_open.pop(device_id, None)
            if open_beurt is not None:
                kaart = self._beurt_kaart_uit(open_beurt)
                if kaart is not None:
                    self._vorige_beurt[device_id] = kaart
                self._beurt_schrijven({**open_beurt, "complete": True,
                                       "ended": open_beurt.get("ended") or now.isoformat()})
            # De kabel is eruit. Voordat deze beurt wordt vergeten gaat hij naar
            # `_afscheid`, want er hoort nog een verslag over. De eigenaar trok hem er
            # op 20-08-2026 twee keer uit tijdens het laden en hoorde niets: er
            # kwam alleen iets bij "vol" en bij een gemiste klaar-tijd.
            #
            # Alleen als er ook werkelijk geladen is, en alleen als er nog niets
            # over gezegd is: een auto die vol was en daarna van de kabel gaat
            # heeft zijn verslag al gehad.
            beurt = self._sessie.pop(device_id, None)
            if beurt:
                kaart = self._beurt_kaart(device, beurt, actief=False)
                if kaart["kwh"] >= BEURT_KAART_MIN_KWH:
                    self._vorige_beurt[device_id] = kaart
            if beurt and beurt.get("geld"):
                self._beurt_schrijven(self._beurt_regel(device, car, beurt, now, klaar=True))
            if beurt and beurt.get("begon") and "vol" not in beurt.get("gemeld", set()):
                # Het moment waarop de paal het zei, niet het moment waarop de
                # coach het na `KABEL_ONTDREUN` geloofde. Anders staat er in het
                # verslag een tijd die een halve minuut naast de werkelijkheid
                # ligt.
                self._afscheid[device_id] = (self._los_sinds.get(device_id) or now, beurt)
            return

        vers = device_id not in self._sessie
        if vers:
            # Er hangt weer een kabel. Is er nog een afscheid blijven staan van
            # de vorige beurt, dan is dat er een die nooit verteld is omdat de
            # coach niet mocht sturen. Die hoort niet alsnog binnen te komen bij
            # een volgende auto; dan gaat het bericht over de verkeerde beurt.
            self._afscheid.pop(device_id, None)

        sessie = self._sessie.setdefault(
            device_id,
            {
                "begon": None,
                "meter": None,
                "laatst": now,
                "kwijt": {},
                # Het plafond van elke ronde, als (moment, ampère, minuten),
                # voor de afgelopen `PLAFOND_VENSTER`. Zie `_plafond_gemeten`.
                "plafond_reeks": [],
                "doel": window.deadline if window.enabled else None,
                "mikpunt": window.deadline if window.enabled else None,
                "gemeld": set(),
                "ingestapt": False,
                # Wanneer de auto zijn accustand voor het laatst wijzigde, en
                # vanaf wanneer hij niet verder laadt. Samen bepalen ze of het
                # percentage in het verslag bij deze beurt hoort.
                "soc_gezien": None,
                # De eerste accustand van deze beurt, voor het verslag: "de
                # accu ging van 44 naar 80%" (v0.89.0).
                "soc_begin": None,
                "soc_moment": None,
                "soc_meter": None,
                "klaar_sinds": None,
                # Waar deze beurt in de doorlopende eigen meting van dit
                # apparaat begon, en wat het ijkpunt opleverde. Zie `_geladen`.
                "eigen_bij_begin": 0.0,
                "geijkt": False,
                "ijk_kwh": 0.0,
            },
        )
        if vers:
            # Laadt hij al bij de allereerste ronde, dan is deze beurt eerder
            # begonnen dan de coach kan weten: Home Assistant is midden in de
            # laadbeurt herstart. Normaal ziet hij de kabel er eerst in gaan en
            # pas een ronde later stroom lopen.
            #
            # Dit onthouden is het verschil tussen een verslag dat klopt en een
            # dat liegt. Op 20-08-2026 herstartte de eigenaar om 20:57 en las hij daarna
            # "Geladen van 20:58 tot 21:32, 3,1 kWh", terwijl de auto vanaf 19:18
            # aan de kabel hing en er 5,2 kWh in was gegaan.
            sessie["ingestapt"] = charger.charging
            sessie["geld"] = self._geld_begin(device_id, now, settings, charger.charging)
            # En wat er van deze beurt bewaard was, zodat het verslag over de hele
            # beurt gaat en niet over het stuk na de herstart (v0.98.0). Op
            # 24-09-2026 om 02:49 zei het verslag "geladen van 02:00 tot 02:49,
            # 7,3 kWh, de accu ging van 72 naar 80%" naast "20,4 kWh kwam van het
            # net": het geld liep door vanaf het inpluggen, de rest begon opnieuw.
            hervat = self._hervat.pop(device_id, None)
            if hervat is not None and hervat.get("begon") is not None:
                sessie.update(
                    begon=hervat["begon"],
                    meter=hervat["meter"],
                    geijkt=hervat["geijkt"] and hervat["meter"] is not None,
                    ijk_kwh=hervat["ijk_kwh"],
                    eigen_bij_begin=0.0,
                    staart_hervat=hervat.get("staart_kwh", 0.0),
                    ingestapt=hervat["ingestapt"],
                )
                # Wat er tussen de laatste opslag en nu geladen werd staat nog
                # niet in het geld; de teller weet het zodra hij stapt. Zie hieronder.
                if (sessie.get("geld") or {}).get("hervat_bekend"):
                    sessie["gat_vullen"] = True
                    sessie["gat_teller"] = self._teller(device)
            if hervat is not None:
                if hervat.get("soc_begin") is not None:
                    sessie["soc_begin"] = hervat["soc_begin"]
                sessie["plafond_reeks"] = list(hervat.get("plafond_reeks") or [])
                sessie["kwijt"] = dict(hervat.get("kwijt") or {})
                sessie["gemeld"] = set(hervat.get("gemeld") or set())

        # Wat deze beurt kost en bespaart, per ronde bijgeteld. Zie `_geld_bij`.
        geld = sessie.get("geld")

        # Tijd toeschrijven aan wat er op dat moment aan de hand was. Het verschil
        # met de vorige ronde en niet één minuut, want een ronde kan ook door een
        # knop of een statuswissel gestart zijn.
        stap = (now - sessie["laatst"]).total_seconds() / 60
        sessie["laatst"] = now
        if 0 < stap <= 10:
            for sleutel in self.VERTRAGING:
                if sleutel in decision.rule:
                    sessie["kwijt"][sleutel] = sessie["kwijt"].get(sleutel, 0.0) + stap
                    break
            # Hoeveel er deze ronde voor de paal overbleef, of hij nu laadde of
            # niet: de zekering min wat het huis trok, de lastbewaker, de groep.
            # Zie `structural_ceiling` in planner.py voor waarom dit telt.
            # Onder de ondergrens van de paal levert hij niets, dus dat telt
            # als nul en niet als "bijna zes". En vroeg de coach het volle
            # plafond, dan telt wat er werkelijk liep: na elke keer dat de
            # Equalizer de paal stilzette kost het opnieuw aanlopen een minuut
            # of twee, en die minuten zag het plafond niet. In het virtuele
            # huis was het verschil tien procent, en dat was precies het
            # kwartier waarmee hij de klaar-tijd miste.
            # Een auto die niets neemt terwijl de coach aanbiedt, of die klaar is,
            # zegt niets over de zekering (v0.99.0): dan telt wat de zekering
            # toeliet en niet de nul die er liep. Na "klaar" zakte het in de
            # eerste woning op 25-09-2026 van 12 naar "gemiddeld 7 A over".
            # Een proef (v0.153.0) ook niet: daar wordt de auto juist op getest,
            # en een Ford in storing zette het plafond anders op nul en de
            # klaar-tijdregel om 20:01 aan het werk.
            auto_neemt_niets = (
                charger.complete or "waiting-for-car" in decision.rule or "+proef" in decision.rule
            )
            if grid is not None:
                plafond = ceiling_amps(grid, car, charger)
                if plafond < MIN_AMPS:
                    gemeten = 0.0
                elif decision.charge and decision.amps >= plafond and not auto_neemt_niets:
                    gemeten = min(float(plafond), max(0.0, charger.actual_amps))
                else:
                    gemeten = float(plafond)
                reeks = sessie.setdefault("plafond_reeks", [])
                reeks.append((now, gemeten, stap))
                grens = now - PLAFOND_VENSTER
                sessie["plafond_reeks"] = [r for r in reeks if r[0] >= grens]

        meter = self._teller(device)

        # De eigen meting hoort bij het apparaat en niet bij de laadbeurt.
        #
        # Dat is een reparatie. Stond hij in de beurt, dan begon hij bij elke
        # nieuwe beurt weer op nul, en dan is er niets meer om de eerste stap
        # van de teller mee te verdelen: die stap dekt immers ook tijd van vóór
        # deze beurt. In de klantwoning kostte dat op 30-08-2026 een verslag van
        # 10,0 kWh over vierentwintig minuten, waar er 3,34 in ging.
        eigen = self._eigen.setdefault(
            device_id,
            {
                "kwh": 0.0,
                "watt": 0.0,
                "liep": False,
                "meter_stand": None,
                "meter_bij": 0.0,
            },
        )


        # De laatste accustand van deze laadbeurt vasthouden, met de meterstand
        # van dat moment erbij. Een percentage dat wegvalt is geen nieuw
        # percentage: de auto hangt nog aan dezelfde kabel en kan dus niet
        # weggereden zijn. Zie `_onthouden_soc` voor wat ermee gebeurt.
        # De kale meting van de sensor, niet de bijgetelde stand: die laatste
        # loopt elke ronde door en dan zou "de accustand is net bijgewerkt"
        # altijd waar zijn. Dat brak in het virtuele huis `ford-storing`, waar
        # het verslag daardoor meteen bij de storing uitging in plaats van te
        # wachten tot de auto zich meldde. Zie `_soc_bijgeteld` en
        # `_soc_bezonken`.
        gemeten = self._soc_ruw.get(device_id, car.soc_percent)
        if sessie.get("soc_begin") is None and car.soc_percent is not None:
            sessie["soc_begin"] = car.soc_percent
        # En de laatste, voor de kaart na het loskoppelen (v0.106.0): dan is de
        # auto er niet meer om het te vragen.
        if car.soc_percent is not None:
            sessie["soc_eind"] = car.soc_percent
            sessie["soc_eind_geschat"] = bool(car.soc_estimated)
        if gemeten is not None and gemeten != sessie.get("soc_gezien"):
            sessie["soc_gezien"] = gemeten
            sessie["soc_moment"] = now
            sessie["soc_meter"] = meter

        # Zelf meten wat er langskomt, want de levensduurteller van de paal
        # loopt achter. In die woning werkte hij op 25-08-2026 maar één keer per uur
        # bij en sprong hij toen met 3,5 kWh ineens, dus het verslag miste het
        # laatste half uur van de beurt. Wat de teller al verwerkt heeft blijft
        # van de teller; alleen de staart daarna komt uit deze som.
        #
        # Gerekend met het vermogen van de vórige ronde, want dat is het
        # vermogen dat er in de minuut ertussen werkelijk stond. Met het
        # vermogen van nu schuift de hele meting een ronde op: de eerste minuut
        # telt dan mee terwijl er nog niets liep, en de laatste valt weg. En
        # alleen als hij toen ook laadde, want een vermogenssensor die na
        # afloop op zijn laatste waarde blijft hangen zou anders doortellen.
        if eigen["liep"] and 0 < stap <= 10:
            kwh_stap = eigen["watt"] / 1000.0 * stap / 60.0
            eigen["kwh"] += kwh_stap
            if geld is not None and settings is not None:
                self._geld_bij(geld, kwh_stap, eigen["watt"], grid, settings, now)
        if geld is not None and settings is not None and 0 < stap <= 10:
            # De maat loopt altijd mee, ook als de coach niets doet.
            self._basis_bij(
                geld, stap, watts_for(charger.max_amps or 16.0, car.phases), settings, now
            )
        eigen["watt"] = _watts(self.hass, device.get("entity")) or 0.0
        eigen["liep"] = charger.charging
        if geld is not None:
            # Elke vijf minuten naar de opslag, en meteen als de beurt net
            # begint: zo overleeft een lopende beurt een herstart.
            bewaard = geld.get("bewaard")
            if bewaard is None or (now - bewaard).total_seconds() >= 300:
                geld["bewaard"] = now
                self._beurt_schrijven(self._beurt_regel(device, car, sessie, now, klaar=False))
            # Ná het wegschrijven, zodat het terugrekenen de voorlopige regel
            # onder het herstartmoment kan vervangen door de echte.
            if geld.get("terugrekenen") and not geld.get("terugrekenen_bezig"):
                geld["terugrekenen_bezig"] = True
                self.hass.async_create_task(
                    self._async_terugrekenen_toepassen(device, settings, now)
                )

        if meter is not None and meter != eigen["meter_stand"]:
            vorige_stand = eigen["meter_stand"]
            vorige_bij = eigen["meter_bij"]
            eigen["meter_stand"] = meter
            eigen["meter_bij"] = eigen["kwh"]
            # Een echte stap na een herstart neemt de bewaarde staart mee: die
            # telt de teller nu zelf (v0.112.0). De eerste ronde na een herstart
            # is geen stap, want toen kende de coach de teller nog niet.
            if vorige_stand is not None:
                sessie.pop("staart_hervat", None)
            # De eerste stap ná het begin van deze beurt valt met één been aan
            # elke kant ervan: hij dekt de tijd vanaf de vorige stap, en die lag
            # vóór het begin. Alleen het deel dat bij deze beurt hoort telt mee,
            # en de eigen meting weet welk deel dat is. Vanaf hier is de teller
            # weer de maat. Zie `_geladen`.
            if (
                sessie["begon"] is not None
                and not sessie["geijkt"]
                and vorige_stand is not None
            ):
                stap_kwh = max(0.0, meter - float(vorige_stand))
                heel = eigen["kwh"] - vorige_bij
                onze = eigen["kwh"] - sessie["eigen_bij_begin"]
                # Heeft de coach in die tijd zelf niets gemeten, dan is er
                # niets om mee te verdelen en gaat de hele stap naar deze beurt.
                # Dat is wat hij vóór het ijkpunt altijd al deed, en zonder
                # eigen meting valt het niet beter te weten.
                sessie["ijk_kwh"] = (
                    stap_kwh * max(0.0, min(1.0, onze / heel))
                    if heel > 1e-9
                    else stap_kwh
                )
                sessie["meter"] = meter
                sessie["geijkt"] = True

        # Na een herstart: wat er tussen de laatste opslag van de beurt en nu
        # geladen werd, telde het geld niet mee, want de coach was weg (v0.98.0).
        # In het virtuele huis stond er daardoor "50,6 kWh kwam van het net"
        # naast "51,3 kWh geladen". Bij de eerste stap van de teller na de
        # herstart dekt die de hele beurt tot nu, en het verschil met het geld
        # gaat er in één keer bij, tegen de prijs van nu. Een Alfen stapt de
        # volgende ronde, een Easee binnen het uur.
        if (
            sessie.get("gat_vullen") and meter is not None and meter != sessie.get("gat_teller")
            and geld is not None and settings is not None
        ):
            sessie.pop("gat_vullen", None)
            gat = (self._geladen(device, sessie) or 0.0) - float(geld.get("kwh") or 0.0)
            if 0.0 < gat < 100.0:
                self._geld_bij(geld, gat, _watts(self.hass, device.get("entity")) or 0.0, grid, settings, now)

        sessie["mikpunt"] = window.deadline if window.enabled else None

        if charger.charging and sessie["begon"] is None:
            sessie["begon"] = now
            sessie["meter"] = eigen["meter_stand"]
            sessie["eigen_bij_begin"] = eigen["kwh"]
            sessie["geijkt"] = False
            sessie["ijk_kwh"] = 0.0

    def _geladen(self, device: dict[str, Any], sessie: dict[str, Any]) -> float | None:
        """Hoeveel kWh er deze beurt in is gegaan.

        De teller van de paal is de maat, want die is geijkt. Alleen loopt hij
        achter: hij verwerkt met sprongen, en wat er ná zijn laatste stap nog
        in ging staat er nog niet in. Dat laatste stuk komt uit wat de coach
        zelf aan vermogen langs zag komen, en is dus ook gemeten en niet
        aangenomen. Heeft de paal helemaal geen teller, dan is die eigen meting
        alles wat er is, en dat is nog altijd beter dan zwijgen.

        **En de kop loopt net zo goed voor.** Die kant stond er niet in. De
        teller stond bij het begin van de beurt stil op een stand van misschien
        wel een uur oud, en de eerste stap daarna bevat dus ook energie van vóór
        deze beurt. In de klantwoning sprong hij op 30-08-2026 om 04:02:45 in één
        keer 9,35 kWh, over de periode vanaf 02:55. De beurt die om 03:43 begon
        nam die hele sprong mee en meldde 10,0 kWh over vierentwintig minuten,
        wat 25 kW zou zijn. Er was 3,34 kWh in gegaan.

        Vandaar het ijkpunt. Tot de eerste stap ná het begin telt de eigen
        meting, want die is wél bij, en vanaf dat punt weer de teller. Zo hoort
        elke kWh bij precies één beurt.
        """
        staart = self._staart(device.get("id", ""), sessie)
        meter = self._teller(device)
        if meter is None or sessie.get("meter") is None:
            return staart or None
        eerder = sessie.get("ijk_kwh", 0.0) if sessie.get("geijkt") else 0.0
        return eerder + max(0.0, meter - float(sessie["meter"])) + staart

    def _staart(self, device_id: str, sessie: dict[str, Any]) -> float:
        """Wat de coach zelf telde sinds de laatste stap van de teller, voor de opslag.

        Bij de eigenaar op 11-10-2026 stapte de teller van de Easee na 18:10 niet
        meer, en herstartte Home Assistant om 20:19, 20:31 en 20:46, midden in de
        beurt. De eigen meting stond alleen in het geheugen, dus het verslag zei
        "12,5 kWh" (precies de teller) terwijl er volgens de paal 15,0 in ging en
        het geld 15,4 telde. Nu gaat de staart mee in de bewaarde beurt
        (`_sessie_bewaren`), en telt hij na een herstart mee tot de teller stapt.
        """
        eigen = self._eigen.get(device_id) or {}
        # Waar de staart begint. Zolang de teller nog niet gestapt is sinds deze
        # beurt begon is dat het begin van de beurt, want alles ervoor was van
        # een andere. Daarna is het de laatste stap.
        basis = eigen.get("meter_bij", 0.0) if sessie.get("geijkt") else sessie.get("eigen_bij_begin", 0.0)
        return max(0.0, eigen.get("kwh", 0.0) - basis) + float(sessie.get("staart_hervat") or 0.0)

    def _beurt_kaart(
        self, device: dict[str, Any], sessie: dict[str, Any], actief: bool
    ) -> dict[str, Any]:
        """Wat de kaart over een laadbeurt zegt: hoeveel erin ging en van welke
        accustand naar welke (v0.106.0).

        De bewoner van de eerste woning op 01-10-2026: "'Deze sessie - x kWh' ...
        Op die manier weet je dat er tijdens de huidige sessie al daadwerkelijk
        is gebeurd", en "de waardes zouden kunnen blijven staan, totdat een
        nieuwe laadbeurt wordt gestart." Dezelfde kWh als het verslag
        (`_geladen`) en dezelfde accustanden (`_accu_verloop`), zodat de kaart en
        de melding niet uit elkaar lopen. De kilometers rekent het paneel uit de
        sensoren van de auto zelf (`laadbeurtRegels` in data-source.js).
        """
        rond = lambda waarde: None if waarde is None else round(float(waarde), 1)  # noqa: E731
        # Voor het laden begon is er niets geteld: `_geladen` meet vanaf `begon`,
        # en daarvoor zou hij de eigen meting van de vorige beurt teruggeven.
        geladen = self._geladen(device, sessie) if sessie.get("begon") is not None else 0.0
        geld = sessie.get("geld") or {}
        ingeplugd = geld.get("ingeplugd")
        return {
            "active": actief,
            "kwh": round(geladen or 0.0, 2),
            "soc_start": rond(sessie.get("soc_begin")),
            "soc_end": rond(sessie.get("soc_eind")),
            "soc_estimated": bool(sessie.get("soc_eind_geschat")),
            # Voor de laadpaalkaart van DomotiApp Lovelace (v0.111.0): sinds
            # wanneer, wat het tot nu kostte en hoeveel van de zon kwam.
            "plugged_at": ingeplugd.replace(microsecond=0).isoformat() if ingeplugd else None,
            "ended": None,
            "paid": round(float(geld.get("betaald") or 0.0), 2),
            "solar_kwh": round(float(geld.get("zon_kwh") or 0.0), 2),
            # Alleen het net, zoals het verslag het noemt (v0.112.0), en de batterij.
            "grid_cost": None if geld.get("net_eur_onbekend") else round(float(geld.get("net_eur") or 0.0), 2),
            "battery_kwh": round(float(geld.get("accu_kwh") or 0.0), 2),
            "grid_kwh": round(max(0.0, float(geld.get("kwh") or 0.0) - float(geld.get("zon_kwh") or 0.0)
                                  - float(geld.get("accu_kwh") or 0.0)), 2),
        }

    @staticmethod
    def _beurt_kaart_uit(regel: dict[str, Any]) -> dict[str, Any] | None:
        """De kaart van een bewaarde beurt (`_beurt_regel`), of niets als er in
        die beurt niet geladen werd. Een regel van voor v0.106.0 heeft alleen de
        kWh van het geld; dan staan er geen procenten bij."""
        try:
            kwh = float(regel.get("charged_kwh", regel.get("kwh")) or 0.0)
        except (TypeError, ValueError):
            return None
        if kwh < BEURT_KAART_MIN_KWH:
            return None
        getal = lambda waarde: waarde if isinstance(waarde, (int, float)) else None  # noqa: E731
        return {
            "active": False,
            "kwh": round(kwh, 2),
            "soc_start": getal(regel.get("soc_start")),
            "soc_end": getal(regel.get("soc_end")),
            "soc_estimated": bool(regel.get("soc_estimated")),
            "plugged_at": regel.get("plugged_at"),
            "ended": regel.get("ended"),
            "paid": getal(regel.get("paid")),
            "solar_kwh": getal(regel.get("solar_kwh")),
            "grid_cost": getal(regel.get("grid_cost")),
            "battery_kwh": getal(regel.get("battery_kwh")),
            "grid_kwh": (
                round(max(0.0, kwh - float(regel.get("solar_kwh") or 0.0) - float(regel.get("battery_kwh") or 0.0)), 2)
                if regel.get("solar_kwh") is not None else None
            ),
        }

    @staticmethod
    def _hoe_heet(car: Car | None) -> str:
        """Hoe de coach deze auto noemt in een zin.

        Heeft de bewoner er een naam aan gegeven, dan is dat de naam. Anders
        blijft het "de auto", want dat is wat het is.

        Dit stond er niet, en daardoor was een naam die je invulde nergens meer
        terug te vinden: de kaart toonde de laadpaal en elke melding zei "de
        auto". De eigenaar op 30-08-2026: "ik heb de naam aangepast bij de auto maar in
        het overzicht staat de naam nog verkeerd en neemt hij het niet mee."
        """
        naam = ((car.name if car else "") or "").strip()
        return naam if naam else t("de auto")

    def _waarom(self, sessie: dict[str, Any]) -> str:
        """De twee dingen waar de meeste tijd aan op is gegaan, in gewone taal.

        Met de periode erbij, en dat is een reparatie. Deze minuten tellen vanaf
        het moment dat de kabel erin ging, terwijl de kWh in dezelfde zin vanaf
        het begin van het laden telt. De eigenaar kreeg op 30-08-2026 om 03:43: "er
        ging 6,9 kWh in sinds 03:00. Er ging 381 minuten naar wachten op een
        goedkoper uur." Dat leest als 381 minuten binnen drieënveertig, terwijl
        het klopte: de kabel zat er sinds 20:37 in. Elk getal was goed en de zin
        was onzin.
        """
        kwijt = [
            (minuten, self.VERTRAGING[sleutel])
            for sleutel, minuten in (sessie.get("kwijt") or {}).items()
            if minuten >= 2 and sleutel in self.VERTRAGING
        ]
        if not kwijt:
            return ""
        kwijt.sort(reverse=True)
        stukken = [t("{n} minuten naar {wat}", n=int(minuten), wat=t(tekst)) for minuten, tekst in kwijt[:2]]
        # Is de coach midden in de laadbeurt ingestapt, dan weet hij niet hoe
        # lang de kabel er al in zat en zegt hij wat hij wél weet.
        sinds = (
            t("Sinds de coach begon te kijken")
            if sessie.get("ingestapt")
            else t("Sinds de kabel erin ging")
        )
        samen = t("{een} en {twee}", een=stukken[0], twee=stukken[1]) if len(stukken) > 1 else stukken[0]
        return t("{sinds} is er {stukken} gegaan", sinds=sinds, stukken=samen)

    @staticmethod
    def _soc_bezonken(
        now: datetime,
        klaar: datetime | None,
        soc_moment: datetime | None,
        car: Car,
    ) -> bool:
        """Of de accustand hoort bij de laadbeurt die net is afgelopen.

        Een auto meldt zich op zijn eigen tempo. Stopt hij met laden en staat de
        app nog op het percentage van een half uur geleden, dan zou het verslag
        een getal noemen dat de bewoner op de kaart al gecorrigeerd ziet staan.
        Dus wacht het bericht tot de auto zich één keer heeft gemeld sinds hij
        ophield (`soc_moment`), of tot `SOC_SETTLE` voorbij is.

        Zonder accustand valt er niets te wachten: dan noemt het verslag geen
        percentage en is er ook niets dat verouderen kan.

        Twee aanroepers, en daarom de losse argumenten in plaats van de sessie:
        het verslag wacht hiermee met zijn bericht, en `_read` wacht ermee met
        het oordeel of de auto niet vol is. Dat laatste is sinds 16-09-2026 net
        zo belangrijk, want daar hing een herstart aan.
        """
        if car.soc_percent is None:
            return True
        if klaar is None:
            return True
        if soc_moment is not None and soc_moment >= klaar:
            return True
        return now - klaar >= SOC_SETTLE

    async def _async_verslag(
        self,
        now: datetime,
        device: dict[str, Any],
        car: Car,
        charger: Charger,
        window: Window,
        decision: Decision,
    ) -> None:
        """Vertellen hoe het afliep, en waarom het langer duurde dan afgesproken.

        Drie momenten. Als de auto vol is, want dan is de vraag "hoe laat was
        hij klaar" en niet "wat doet hij nu". Als de klaar-tijd voorbijgaat
        terwijl hij niet vol is, want dat is precies het geval waarin iemand
        anders zou denken dat de coach niets gedaan heeft. En als de kabel eruit
        gaat terwijl er geladen werd, want dan is de beurt net zo goed afgelopen
        en is dezelfde vraag aan de orde.
        """
        device_id = device.get("id", "")
        naam = device.get("name") or t("de laadpaal")

        # De kabel is eruit gegaan. Deze staat vooraan omdat de beurt dan al uit
        # `_sessie` gehaald is en de controle hieronder er dus overheen zou
        # lopen.
        afscheid = self._afscheid.pop(device_id, None)
        if afscheid:
            await self._async_afgekoppeld(device, naam, car, *afscheid)
            return

        sessie = self._sessie.get(device_id)
        if not sessie:
            return

        gemeld: set[str] = sessie["gemeld"]

        # De coach biedt stroom aan en er komt niets. Dit is het bericht dat bij
        # de klantwoning had moeten komen: de Ford hield op 30-08-2026 om 04:34 op
        # met laden en kwam daar zelf niet meer uit, maar het eerste woord
        # daarover was het verslag van 07:00, toen de klaar-tijd al voorbij was
        # en de auto op 69% stond. Twee en een half uur waarin niemand iets kon
        # doen omdat niemand het wist.
        #
        # Alleen als er een klaar-tijd is die nog moet komen, want zonder
        # afspraak is een auto die niets afneemt geen probleem maar een keuze
        # van de auto. En één keer per laadbeurt.
        biedt_aan = decision.charge and charger.connected and not charger.charging
        sinds = self._asking_since.get(device_id)
        if (
            biedt_aan
            and sinds is not None
            and now - sinds >= STIL_AANBOD
            and window.enabled
            and window.deadline is not None
            and window.deadline > now
            and "stil" not in gemeld
        ):
            gemeld.add("stil")
            minuten = int(_tussen(sinds, now).total_seconds() // 60)
            stand = (
                " " + t("Hij staat op {pct}%.", pct=round(car.soc_percent))
                if car.soc_percent is not None
                else ""
            )
            await self._async_tell(
                t(
                    "{auto} aan {naam} neemt al {minuten} minuten geen stroom af terwijl de coach hem "
                    "aanbiedt.{stand} Zo wordt {klok} niet gehaald. Meestal helpt het om de kabel er "
                    "even uit te trekken en er weer in te doen.",
                    auto=_hoofdletter(self._hoe_heet(car)), naam=naam, minuten=minuten, stand=stand,
                    klok=f"{window.deadline:%H:%M}",
                ),
                kritiek=True,
            )

        # De coach heeft de paal zojuist opnieuw gestart omdat de auto volgens
        # zijn accustand nog niet vol was. Dat hoort de bewoner te lezen, ook
        # als het lukt: de Ford-app zei op 06-09-2026 "charging error" en dan
        # wil je weten dat er iemand iets deed.
        if device_id in self._herstart_melden:
            self._herstart_melden.discard(device_id)
            stand = f" {round(car.soc_percent)}%" if car.soc_percent is not None else ""
            # Waar hij naartoe moest, als dat niet gewoon vol is. Zonder dat
            # leest "dat is niet vol" bij een doel van 90% als een coach die de
            # instelling niet kent.
            heen = (
                "" if doel_van(car) >= FULL_PERCENT else " " + t("en hij moet naar {pct}%", pct=int(doel_van(car)))
            )
            await self._async_tell(
                t(
                    "{naam} zei dat {auto} klaar was, maar hij staat op{stand}{heen} en dat is niet vol. "
                    "De coach heeft de paal een keer opnieuw gestart. Gaat de auto niet binnen een "
                    "kwartier verder, dan laat hij het daarbij.",
                    naam=naam, auto=self._hoe_heet(car), stand=stand, heen=heen,
                ),
                kritiek=True,
            )

        # Gaat een auto na "laadt niet verder" toch weer laden, dan was dat
        # verslag niet het einde van de beurt, en hoort er nog een te komen als
        # hij echt klaar is. In de klantwoning op 10-10-2026: de Ford ging om
        # 00:51 in storing op 36%, kwam om 01:22 uit zichzelf terug en was om
        # 06:48 vol, en het enige verslag van die nacht zei "36%, zonder gevolg".
        if "vol" in gemeld and sessie.get("niet_vol") and charger.charging and decision.rule != "complete":
            gemeld.discard("vol")
            sessie["niet_vol"] = False
            sessie["klaar_sinds"] = None

        # De auto is vol.
        if decision.rule == "complete" and "vol" not in gemeld and sessie["begon"]:
            if sessie.get("klaar_sinds") is None:
                sessie["klaar_sinds"] = now
            if not self._soc_bezonken(
                now, sessie.get("klaar_sinds"), sessie.get("soc_moment"), car
            ):
                return
            # Na een eigen herstart eerst een kwartier afwachten: de Ford bij
            # de klantwoning had er negen minuten voor nodig.
            herstart = self._herstart_gedaan.get(device_id)
            if herstart is not None and now - herstart < HERSTART_WACHT:
                return
            gemeld.add("vol")
            geladen = self._geladen(device, sessie)
            kwh = _kwh_tekst(geladen) if geladen else ""
            # "Vol" is wat de paal zegt, niet altijd wat de accu doet. Stopt een
            # auto op 80% omdat daar een laadgrens in staat, dan is "de auto is
            # vol" onwaar en leest het als een coach die niet weet wat hij doet.
            # Weet hij de accustand, dan zegt hij die gewoon. De eigenaar op 20-08-2026.
            #
            # En staat die 80% als doel in het profiel, dan is er niets bijzonders
            # gebeurd en hoort er ook geen bijzonderheid te staan: dan is dit
            # gewoon het einde van een geslaagde beurt. De eigenaar op 16-09-2026.
            #
            # Sinds v0.102.1 staat de accustand in de kop ("geladen van 44 naar
            # 80%", "is vol, van 30 naar 100%") in plaats van in een eigen zin,
            # en is "en verder hoefde hij niet" eruit: het verslag moest korter.
            wie = self._wie(car, naam)
            heel = doel_van(car) >= FULL_PERCENT
            accu = self._accu_verloop(sessie, car)
            if car.soc_percent is None:
                klaar = t("{wie} is vol.", wie=wie)
            elif not doel_bereikt(car):
                # Een laadgrens is één reden, een storing in de auto een andere:
                # de Ford op 10-10-2026 stond op 36% met een doel van 100%.
                klaar = t(
                    "{wie} laadt niet verder en staat op {pct}%. Mogelijk staat er een laadgrens in "
                    "de auto, of meldt hij een storing.",
                    wie=wie, pct=round(car.soc_percent),
                )
                sessie["niet_vol"] = True
            elif heel:
                klaar = t("{wie} is vol, {accu}.", wie=wie, accu=accu) if accu else t("{wie} is vol.", wie=wie)
            elif accu:
                klaar = t("{wie} geladen {accu}.", wie=wie, accu=accu)
            else:
                geschat = " " + t("(geschat)") if car.soc_estimated else ""
                klaar = t("{wie} geladen tot {pct}%{geschat}.", wie=wie, pct=round(car.soc_percent), geschat=geschat)
            # Is de coach midden in de laadbeurt ingestapt, dan weet hij niet
            # hoe laat die begon en hoort hij dat ook niet te suggereren.
            # Vandaar "sinds" en niet "van ... tot"; dat ene woord zegt het al.
            # Wat er niet meer bij staat is "en toen liep hij al". De eigenaar op
            # 21-09-2026: "ik vind dat en toen liep hij al onnodig. Alle
            # meldingen moeten gewoon duidelijk en kort zijn."
            begon = sessie["begon"]
            if sessie.get("ingestapt"):
                verloop = t("{kwh} sinds {klok}.", kwh=kwh, klok=f"{begon:%H:%M}") if kwh else ""
            elif kwh:
                verloop = f"{kwh}, " + t("{van} tot {tot}.", van=f"{begon:%H:%M}", tot=f"{now:%H:%M}")
            else:
                verloop = t("{van} tot {tot}.", van=f"{begon:%H:%M}", tot=f"{now:%H:%M}")
            # "Zonder gevolg" alleen bij een auto die ook echt niet verder kwam;
            # niet in het verslag van een auto die daarna alsnog vol werd.
            nog = (
                t("De coach heeft de paal om {klok} nog een keer opnieuw gestart, zonder gevolg.",
                  klok=f"{herstart:%H:%M}")
                if herstart is not None and sessie.get("niet_vol")
                else ""
            )
            await self._async_tell(_verslag(
                klaar, verloop, self._beurt_cijfers(sessie), self._beurt_bespaard(sessie), nog,
            ))
            return

        # De klaar-tijd is verstreken en de auto is niet vol. Te zien aan een
        # nieuwe klaar-tijd: die van vandaag is dan voorbij en de eerstvolgende
        # ligt morgen.
        doel = window.deadline if window.enabled else None
        vorig = sessie.get("doel")
        sessie["doel"] = doel
        if vorig is None or doel == vorig or vorig > now or "laat" in gemeld:
            return
        # Een auto die vol is, is niet te laat. Zonder deze regel kwam er elke
        # ochtend om de klaar-tijd "was om 06:00 nog niet vol, hij staat nu op
        # 100%" over een auto die de avond ervoor al als vol gemeld was: de
        # klaar-tijd schuift dan gewoon een dag op en dat leest hier als een
        # gemiste afspraak. Gevonden in het virtuele huis op 04-09-2026, in elk
        # scenario waarin de kabel na het vol laden bleef zitten.
        if decision.rule == "complete" or "vol" in gemeld:
            return

        gemeld.add("laat")
        stand = (
            " " + t("Hij staat nu op {pct}%.", pct=round(car.soc_percent))
            if car.soc_percent is not None
            else ""
        )
        waarom = self._waarom(sessie)
        await self._async_tell(
            t("{auto} aan {naam} was om {klok} nog niet vol.",
              auto=_hoofdletter(self._hoe_heet(car)), naam=naam, klok=f"{vorig:%H:%M}")
            + stand
            + (f" {waarom}." if waarom else "")
            + " " + t("Hij laadt door tot hij vol is."),
            kritiek=True,
        )

    @staticmethod
    def _wie(car: Car | None, naam: str) -> str:
        """Wie er in de kop van een verslag staat (v0.102.1).

        Een auto met een eigen naam is genoeg: "De blauwe bus geladen tot 80%".
        Zonder naam, en bij een gast, hoort de paal erbij, anders zegt "de auto"
        in een huis met twee palen niet welke.
        """
        eigen = ((car.name if car else "") or "").strip()
        if eigen and not (car is not None and car.guest):
            return _hoofdletter(eigen)
        return t("{auto} aan {naam}", auto=_hoofdletter(ChargerCoach._hoe_heet(car)), naam=naam)

    @staticmethod
    def _accu_verloop(sessie: dict[str, Any], car: Car | None) -> str:
        """ "van 44 naar 80%" voor in een verslag, of niets als dat niet bekend is.

        De bewoner van de eerste woning op 23-09-2026: "is de accu gestegen van
        A% naar B%." Alleen wat bekend is: zonder accustand geen procenten.
        """
        begin = sessie.get("soc_begin")
        eind = car.soc_percent if car is not None else None
        if begin is None or eind is None or round(eind) <= round(begin):
            return ""
        geschat = " " + t("(geschat)") if car.soc_estimated else ""
        return t("van {van} naar {tot}%{geschat}", van=int(round(begin)), tot=int(round(eind)), geschat=geschat)

    @staticmethod
    def _beurt_cijfers(sessie: dict[str, Any]) -> str:
        """Waar de stroom van een laadbeurt vandaan kwam, voor het verslag (v0.89.0).

        De bewoner van de eerste woning op 23-09-2026: "C kWh is afgenomen van
        het net met een totaalprijs van € D; E kWh heb je direct verbruikt van
        je zonopwek." Dezelfde regel als bij elk ander apparaat (v0.101.0):
        eigen zon, de thuisbatterij en het net, met het bedrag bij het net.
        Zonder geteld geld niets. De kWh zelf en de accustand staan in de
        regels erboven (`_accu_verloop`).
        """
        geld = sessie.get("geld") or {}
        if float(geld.get("kwh") or 0.0) > HERKOMST_MIN_KWH:
            return ChargerCoach._herkomst_tekst(geld)
        return ""

    def _beurt_bespaard(self, sessie: dict[str, Any]) -> str:
        """Wat een laadbeurt bespaarde, in de zin van de andere apparaten (v0.101.0).

        Dezelfde maat als onder Bespaard (`_beurt_regel`): wat de kilowatturen
        gekost hadden op vol vermogen vanaf het inpluggen, alles van het net.
        """
        geld = sessie.get("geld") or {}
        ijk = geld.get("ijk_prijs")
        if geld.get("terugrekenen") or ijk is None:
            return ""
        kwh = max(0.0, float(geld.get("kwh") or 0.0) - float(geld.get("onbekend_kwh") or 0.0))
        maat = self._basis_kosten_voor(geld, kwh)
        if maat is None:
            return ""
        bespaard = maat - float(geld.get("betaald") or 0.0)
        if bespaard < 0.005:
            return ""
        return self._bespaard_zin(bespaard)

    async def _async_afgekoppeld(
        self,
        device: dict[str, Any],
        naam: str,
        car: Car,
        moment: datetime,
        sessie: dict[str, Any],
    ) -> None:
        """Vertellen hoe het afliep toen de kabel eruit ging.

        Dezelfde vorm als het verslag bij een volle auto, want het is dezelfde
        vraag: wanneer hield het op en hoeveel is erin gegaan. Afgesproken met
        De eigenaar op 26-08-2026, met zijn eigen zin als voorbeeld: "afgekoppeld om
        19:12, er ging 4,2 kWh in".

        Wat er niet in staat is een oordeel. De kabel eruit trekken is een
        gewone handeling en geen storing, dus er hoort geen "maar hij was nog
        niet vol" bij; dat weet de bewoner zelf.
        """
        geladen = self._geladen(device, sessie)
        kwh = _kwh_tekst(geladen) if geladen else ""
        begon = sessie.get("begon")

        # "Sinds" en niet "van ... tot", want is de coach midden in de beurt
        # ingestapt dan weet hij het begin niet. Die ene regel dekt allebei de
        # gevallen; de bijzin "en toen liep hij al" is eruit (de eigenaar, 21-09-2026).
        accu = self._accu_verloop(sessie, car)
        verloop = ""
        if kwh:
            verloop = (
                t("{kwh} sinds {klok}, {accu}.", kwh=kwh, klok=f"{begon:%H:%M}", accu=accu)
                if accu
                else t("{kwh} sinds {klok}.", kwh=kwh, klok=f"{begon:%H:%M}")
            )
        elif accu:
            verloop = f"{_hoofdletter(accu)}."

        # Was de auto al als vol gemeld, dan is dit het tweede verslag van
        # dezelfde beurt: wel in de geschiedenis, niet nog eens op de telefoon.
        await self._async_tell(
            _verslag(
                t("{wie} is afgekoppeld om {klok}.", wie=self._wie(car, naam), klok=f"{moment:%H:%M}"),
                verloop,
                self._beurt_cijfers(sessie),
                self._beurt_bespaard(sessie),
            ),
            telefoon="vol" not in (sessie.get("gemeld") or set()),
        )

    async def _async_ask_soc(self, device: dict[str, Any], decision: Decision) -> None:
        """Vragen hoe vol de auto is, want zonder dat kan de coach niets plannen.

        Twee momenten en niet meer. Eén keer als hij het merkt, want dan is er
        nog tijd om er iets mee te doen, en één keer als het vangnet ingrijpt,
        want dan gebeurt er iets dat de bewoner had kunnen voorkomen. Vaker is
        zeuren, en wie gezeurd wordt zet zijn meldingen uit.
        """
        device_id = device.get("id", "")
        naam = device.get("name") or t("de laadpaal")
        merk = f"{device_id}:deadline" if decision.rule == "deadline" else device_id
        if merk in self._soc_asked:
            return
        self._soc_asked.add(merk)

        if decision.rule == "deadline":
            bericht = t(
                "De accustand van de auto aan {naam} is nog steeds niet doorgegeven, dus de coach gaat "
                "uit van een lege accu en laadt nu door om op tijd klaar te zijn.",
                naam=naam,
            )
        else:
            bericht = t(
                "De coach wil de auto aan {naam} gaan laden, maar weet niet hoe vol hij is. Geef de "
                "accustand door op de laadpaalkaart, dan laadt hij op het gunstigste moment.",
                naam=naam,
            )
        await self._async_tell(bericht, kritiek=True)

    async def _async_forget(self, settings: dict[str, Any], device_id: str) -> None:
        """Alles wat over deze sessie bewaard was vergeten, in één keer.

        In één schrijfbeurt, want dit gebeurt bij elke ronde dat er geen kabel
        in zit en twee schrijfbeurten per minuut is twee keer te veel. Staat er
        niets meer, dan wordt er ook niets geschreven.
        """
        wijziging = {}
        for sleutel in ("car_soc", "sessions"):
            rows = [
                row
                for row in (settings.get(sleutel) or [])
                if isinstance(row, dict) and row.get("device") != device_id
            ]
            if len(rows) != len(settings.get(sleutel) or []):
                wijziging[sleutel] = rows
        if not wijziging:
            return
        try:
            saved = await async_get_store(self.hass).async_save(wijziging)
        except Exception:  # noqa: BLE001 - een vergeten percentage is geen reden om te stoppen
            _LOGGER.exception("kon de gegevens van de vorige sessie niet vergeten")
            return
        self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": saved})

    def _teller(self, device: dict[str, Any]) -> float | None:
        """De geijkte kWh-teller van dit apparaat, hoe hij ook ingevuld is.

        Twee velden vroegen om hetzelfde. Bij een Easee vult de installateur
        onder Merk "Levensduur verbruik" in, en bij Apparaten staat daarnaast
        "Energieteller (optioneel)" die naar dezelfde sensor wijst. De eigenaar merkte
        dat op 27-08-2026 bij een klant: hij typte hem twee keer.

        Erger dan het dubbele typen was wat eronder zat. Alleen Easee heeft dat
        merkveld; een paal van een ander merk ("overig") heeft geen enkel merkveld.
        Bij die klanten kwam er dus nooit een teller binnen, ook niet als de
        Energieteller keurig was ingevuld, en viel het verslag terug op wat de
        coach zelf aan vermogen langs zag komen. Dat werkt, maar de geijkte
        teller ligt er dan ongebruikt naast.

        Het merkveld eerst, want bestaande installaties hebben dat ingevuld en
        die mogen hier niets van merken.
        """
        entiteit = (device.get("entities") or {}).get("lifetime_energy") or device.get(
            "energy_entity"
        )
        return _kwh(self.hass, entiteit)

    def _fasetip(
        self, settings: dict[str, Any], device: dict[str, Any], charger: Charger
    ) -> str:
        """Zeggen dat de laderlimiet laadsnelheid kost, als dat werkelijk zo is.

        De paal kiest bij het starten van een beurt zelf hoeveel fasen hij
        pakt, en gaat daarbij af op zijn eigen maximale limiet. Staat die te
        laag, dan laadt elke beurt eenfasig. In die woning kostte dat een week lang
        stilletjes een factor drie: 3,1 kW waar 10,9 kW kon, en niets in het
        paneel dat er iets over zei. De limiet die de coach schrijft telt in die
        keuze niet mee, dus dit is met sturen niet op te lossen en is het enige
        wat overblijft: het zeggen.

        Alleen zeggen wat gezien is. Er loopt stroom over één fase terwijl de
        laderlimiet onder `PHASE_START_AMPS` staat, aan een merk waar dat aan
        gemeten is. Een auto die zelf maar één fase kan, kan er niets aan doen
        en krijgt dus niets te lezen.

        Een Alfen die van de coach mag wisselen krijgt niets: een fase is dan
        zijn eigen keuze (v0.104.0).
        """
        if not charger.charging or self._fasewissel_aan(device):
            return ""
        gemeten = self._fase_nu.get(device.get("id", ""))
        if gemeten is None:
            return ""
        _, profile = self._chosen_car(settings, device)
        staat_op = (profile or {}).get("phases")

        # 1. De laderlimiet houdt hem op één fase. Dit gaat vóór het profiel,
        # want dan is de instelling niet fout maar de paal de oorzaak.
        if (
            device.get("brand") == "easee"
            and charger.max_amps
            and charger.max_amps < PHASE_START_AMPS
            and staat_op != "one"
            and gemeten == 1
        ):
            return t(
                "Hij laadt op één fase, want de maximale limiet van je lader staat op {max} A. Op "
                "{start} A of hoger begint elke laadbeurt op drie fasen, en gaat er ongeveer drie "
                "keer zoveel in per uur.",
                max=f"{charger.max_amps:.0f}", start=f"{PHASE_START_AMPS:.0f}",
            )

        # 2. Het profiel klopt niet met wat er gemeten wordt. Dit is het vangnet
        # dat in de plaats komt van de keuze "allebei": daar werd het aantal
        # fasen gemeten in plaats van ingesteld, en de prijs daarvan was dat elke
        # voorspelling het traagste geval nam. Nu staat het vast en wordt de
        # meting gebruikt waar hij hoort: om te zeggen dat de instelling niet
        # klopt, in plaats van er stilletjes omheen te rekenen.
        if staat_op == "three" and gemeten == 1:
            return t(
                "Dit profiel staat op driefasig, maar er wordt nu op één fase "
                "geladen. Laden duurt daardoor ongeveer drie keer zo lang; de coach "
                "rekent deze beurt met die ene fase. Gebeurt dit elke beurt, zet de "
                "auto dan op eenfasig bij Apparaten."
            )
        if staat_op == "one" and gemeten == 3:
            return t(
                "Dit profiel staat op eenfasig, maar er wordt op drie fasen geladen. "
                "De coach rekent daardoor met een auto die veel trager is dan hij "
                "werkelijk is en begint onnodig vroeg. Zet de auto op driefasig bij "
                "Apparaten."
            )
        return ""

    def _measured_phases(self, device: dict[str, Any]) -> int | None:
        """One phase or three, worked out from what the charger reports.

        De som is een verhouding: het vermogen gedeeld door de stroom is bij
        drie fasen ongeveer drie keer de spanning en bij één fase ongeveer één
        keer. Die som klopt alleen als de twee getallen bij hetzelfde moment
        horen, en dat is precies wat er misging.

        In de klantwoning meldde de Easee op 30-08-2026 om 04:28:17 een stroom van
        2,20 A terwijl het vermogen nog de 782 W van drie seconden eerder was.
        Dat is een verhouding van 1,54 en dus "één fase", en zo kreeg de eigenaar te
        lezen dat zijn auto eenfasig laadde terwijl alle drie de fasen van het
        huis netjes samen elf ampère zakten zodra de paal uitging.

        Drie eisen dus, en ze gaan allemaal over of de meting iets betekent.
        Genoeg stroom, want onder een paar ampère is elke verhouding ruis. De
        twee sensoren binnen `FASEMETING_VERS` van elkaar, want anders vergelijk
        je twee momenten. En een uitkomst die niet tussen wal en schip valt: bij
        een verhouding tussen 1,5 en 2,5 zegt de coach liever niets.
        """
        entities = device.get("entities") or {}
        vermogen = self.hass.states.get(device.get("entity") or "")
        stroom = self.hass.states.get(entities.get("current") or "")
        if vermogen is None or stroom is None:
            return None

        watts = _watts(self.hass, device.get("entity"))
        amps = _number(self.hass, entities.get("current"))
        if not watts or not amps or amps < FASEMETING_AMPS:
            return None

        # Twee sensoren van dezelfde paal die niet tegelijk gemeld hebben zeggen
        # samen niets. Tijdens het optrekken lopen ze seconden uit elkaar en dan
        # is de verhouding een vergelijking tussen nu en daarnet.
        if abs(vermogen.last_updated - stroom.last_updated) > FASEMETING_VERS:
            return None

        verhouding = amps_for(watts, 1) / amps
        if verhouding > 2.5:
            return 3
        if verhouding < 1.5:
            return 1
        return None

    def _tijdlijn(
        self,
        now: datetime,
        settings: dict[str, Any],
        grid: Grid,
        car: Car,
        charger: Charger,
        window: Window,
        doorladen: bool = False,
    ) -> dict[str, Any]:
        """De tijdlijn van de planner, klaar om over de websocket te gaan.

        Alleen de vertaalslag: momenten worden tekst en de blokken een lijst.
        Het denkwerk staat in `timeline` in planner.py, want dat is los te
        draaien tegen een hele dag echte prijzen.
        """
        plan = timeline(
            now,
            self._prices(settings),
            grid,
            car,
            charger,
            window,
            ceiling_amps(grid, car, charger),
            self._tarief(settings),
            Forecast(
                solar_kwh=self._zon_kwh,
                house_kwh=self._huis_kwh,
                estimated=self._zon_geschat,
                solar_factor=self._zon_gemeten(now),
                solar_day=now.date(),
            ),
            doorladen=doorladen,
        )

        hulp, tot = self._accu_hulp()
        accu_in_plan(plan, hulp, now, tot)

        def klok(moment: datetime | None) -> str | None:
            return None if moment is None else moment.isoformat()

        return {
            "deadline": klok(plan.deadline),
            "latest_start": klok(plan.latest_start),
            "expected_done": klok(plan.expected_done),
            "kwh_needed": plan.kwh_needed,
            "hours_needed": plan.hours_needed,
            "amps": plan.amps,
            "planned_kwh": plan.planned_kwh,
            "solar_only": plan.solar_only,
            "note": plan.note,
            "estimated": plan.estimated,
            "measured": plan.measured,
            # Welke zekering het plan onder wat paal en auto kunnen houdt (v0.98.0).
            "fuse_name": plan.fuse_name,
            # Zonder deze regel bleef `solar_measured_note` in v0.67.0 hangen
            # in de reden en bereikte hij de tijdlijn op de kaart nooit, terwijl
            # `plan-ahead-sheet.js` er wel naar keek.
            "solar_note": plan.solar_note,
            # Het laadrendement (v0.94.0): "nog te laden" is aan de paal, en
            # wat er daarvan in de accu komt staat ernaast, met of het gemeten
            # is of aangenomen.
            "efficiency": round(rendement_van(car), 3),
            "efficiency_measured": car.efficiency is not None,
            "kwh_in_car": None if plan.kwh_needed is None else round(plan.kwh_needed * rendement_van(car), 2),
            # Wat de thuisbatterij erbij geeft, en tot welke accustand (v0.95.0).
            "accu_kwh": plan.accu_kwh,
            "accu_to": None if plan.accu_to is None else round(plan.accu_to),
            "blocks": [
                {
                    "start": klok(blok.start),
                    "end": klok(blok.end),
                    "price": blok.price,
                    "charging": blok.charging,
                    "why": blok.why,
                    "solar_kwh": blok.solar_kwh,
                    "kwh": blok.kwh,
                    "amps": blok.amps,
                    "kw": blok.kw,
                    "accu_kwh": blok.accu_kwh,
                }
                for blok in plan.blocks
            ],
        }

    def _auto_laden(self) -> list[tuple[datetime, datetime, float]]:
        """Het plan van elke paal: per blok wat de auto van het net zou nemen.

        Voor het uurplan van de batterij (`auto_hulp` in batterij.py, v0.95.0).
        Uit de stand van de vorige ronde, want de batterij wordt eerst behandeld;
        het plan van de paal hangt niet van de batterij af, dus dat scheelt
        hooguit een minuut. Een blok dat al loopt telt vanaf het moment van dat
        plan, want daar rekende de paal vanaf.
        """
        uit: list[tuple[datetime, datetime, float]] = []
        for stand in self.state.values():
            plan = stand.get("plan_ahead") if isinstance(stand, dict) else None
            if not isinstance(plan, dict):
                continue
            try:
                toen = datetime.fromisoformat(str(stand.get("at")))
            except ValueError:
                continue
            for blok in plan.get("blocks") or []:
                if not blok.get("charging"):
                    continue
                try:
                    van = max(datetime.fromisoformat(blok["start"]), toen)
                    tot = datetime.fromisoformat(blok["end"])
                except (KeyError, TypeError, ValueError):
                    continue
                kwh = float(blok.get("kwh") or 0.0) - float(blok.get("solar_kwh") or 0.0)
                if tot > van and kwh > 0:
                    uit.append((van, tot, kwh))
        return uit

    def _accu_hulp(self) -> tuple[list[tuple[datetime, datetime, float]], float | None]:
        """Wat de gestuurde batterijen de auto per blok geven, en tot welke stand."""
        hulp: list[tuple[datetime, datetime, float]] = []
        tot: float | None = None
        for sessie in self._batterij.values():
            besluit = sessie.get("besluit")
            if not sessie.get("stuurt") or besluit is None:
                continue
            for uur in besluit.uren:
                if uur.auto_kwh > 0:
                    hulp.append((uur.start, uur.end, uur.auto_kwh))
            if sessie.get("auto_grens") is not None:
                tot = sessie["auto_grens"] if tot is None else max(tot, sessie["auto_grens"])
        return hulp, tot

    def _groep_amps(self, entities: dict[str, Any]) -> float | None:
        """De grens van de groep waar de paal op zit: de laagste die bekend is.

        Een Easee kent er twee, een dynamische en een vaste, en houdt zich aan
        de laagste. In de klantwoning stond de dynamische sinds 30-09-2026 op
        40 A bij een vaste van 16 A, en het veld wees naar de dynamische. In de
        nacht van 10-10-2026 trok de Ford om 00:43 16,8 A op één fase, de coach
        rekende met 40 A in plaats van 16, en om 00:50 hield de paal ermee op en
        ging de Ford in storing, net als op 06-09-2026. Zie `circuit_ceiling`.
        """
        grenzen = [
            waarde
            for waarde in (
                _number(self.hass, entities.get("circuit_limit")),
                _number(self.hass, entities.get("circuit_max")),
            )
            if waarde is not None
        ]
        return min(grenzen) if grenzen else None

    def _nettip(self, now: datetime) -> str:
        """Zeggen dat de netmeting er niet is, want dat verklaart de stilstand.

        Zonder netmeting is er geen zon te zien, en dan valt de zonregel weg.
        Prijs en klaar-tijd werken gewoon door, dus de coach doet nog van alles,
        maar wie op een zonnige middag naar een stilstaande paal kijkt heeft
        recht op de reden. Deze staat vóór de andere tips: een meting die er niet
        is maakt de rest van wat de kaart zegt minder waard.
        """
        if self._net_stil_sinds is None:
            return ""
        minuten = int(_tussen(self._net_stil_sinds, now).total_seconds() // 60)
        if minuten < 1:
            return ""
        duur = tn(minuten, "een minuut", "{n} minuten")
        if self._net_stil_wat == "paal":
            return t(
                "De coach kan het vermogen van je laadpaal al {duur} niet lezen, "
                "dus hij ziet niet hoeveel zon er over is en stuurt alleen op prijs "
                "en op je klaar-tijd. Kijk of de integratie van je laadpaal nog draait.",
                duur=duur,
            )
        return t(
            "De coach kan je netmeting al {duur} niet lezen, dus hij "
            "ziet niet hoeveel zon er over is en stuurt alleen op prijs en op je "
            "klaar-tijd. Kijk of de integratie van je slimme meter nog draait.",
            duur=duur,
        )

    def _bewakertip(
        self, settings: dict[str, Any], device: dict[str, Any], charger: Charger
    ) -> str:
        """Zeggen dat het de lastbewaker is die de snelheid bepaalt.

        Niet zomaar zodra die sensor er is, want dan staat het er altijd. Alleen
        als hij werkelijk de laagste van de plafonds is: de paal kan meer, de
        auto wil meer, en er past onder de zekering ook meer, maar de bewaker
        geeft niet meer vrij.

        Dat is de vraag die iemand zich dan stelt. In de klantwoning stond in het
        logboek van de nacht van 30-08-2026 uur na uur `limited_by_equalizer`
        terwijl er nergens op het scherm iets over te vinden was.
        """
        installation = settings.get("installation") or {}
        vrij = _number(self.hass, installation.get("balancer_entity"))
        if vrij is None or vrij <= 0:
            return ""
        if not charger.max_amps or vrij >= charger.max_amps:
            return ""
        return t(
            "Je lastbewaker geeft op dit moment {vrij} A vrij en je lader "
            "kan {max} A. Meer vraagt de coach dus niet: "
            "daarboven knijpt de bewaker toch. Dat getal beweegt mee met wat de "
            "rest van je huis gebruikt.",
            vrij=f"{vrij:.0f}", max=f"{charger.max_amps:.0f}",
        )

    def _fasen_stabiel(self, device: dict[str, Any]) -> int | None:
        """Dezelfde fasemeting, maar pas als hij `FASEMETING_RONDEN` lang staat.

        Een enkele ronde is nooit genoeg om iemand te vertellen dat zijn
        instelling niet klopt. Een meting die weifelt zet de teller op nul, dus
        er wordt alleen iets gezegd over een paal die er al minuten stabiel bij
        staat.

        Een ronde zonder bruikbare meting weifelt niet, die zegt niets: de stand
        van deze beurt blijft staan, en de teller ook (v0.106.1). In de eerste
        woning op 03-10-2026 wiste zo'n ronde de gemeten fase. De Alfen meldt
        elke 30 s, en een stroom die gelijk bleef was 30 s ouder dan het
        vermogen; dan rekende de coach met het driefasige profiel en ging de
        paal met 4,3 kW zon van 13 naar 6 A, drie keer in twintig minuten.
        Alleen een andere meting, drie ronden lang, of een nieuwe beurt zet hem om.
        """
        device_id = device.get("id", "")
        vast = self._fase_nu.get(device_id)
        gemeten = self._measured_phases(device)
        if gemeten is None:
            return vast

        vorig, keer = self._fasen_gemeten.get(device_id, (0, 0))
        keer = keer + 1 if vorig == gemeten else 1
        self._fasen_gemeten[device_id] = (gemeten, keer)
        return gemeten if keer >= FASEMETING_RONDEN else vast

    def _restore(self, settings: dict[str, Any]) -> None:
        """De knoppen van de bewoner terughalen na een herstart.

        Een akkoord, snelladen en een pauze zijn opdrachten van een mens, en die
        horen niet te verdampen omdat Home Assistant vannacht toevallig opnieuw
        opstartte. Zonder dit stond een auto die op "adviseren" was goedgekeurd
        's ochtends leeg, want de coach was zijn akkoord kwijt en niemand was
        wakker om opnieuw op de knop te drukken.

        Ze verlopen wel, en om twee redenen. Een opdracht van gisteren gaat niet
        over de auto die er nu hangt, en na een herstart kan de coach niet zien
        of de kabel er tussendoor uit is geweest. Het uittrekken van de kabel
        wist ze sowieso; dit is het vangnet voor wat hij niet gezien heeft.
        """
        if self._restored:
            return
        self._restored = True

        # De sensoren die al als stil gemeld waren (v0.98.0). In de eerste
        # woning kwam "Airco F&R meldt al 10 minuten niets" na elke herstart
        # opnieuw als kritieke melding (24-09-2026 om 00:05 en 00:53), terwijl
        # die stekker gewoon weg was.
        for row in settings.get("sensor_quiet") or []:
            if isinstance(row, dict) and row.get("entity"):
                self._sensor_gemeld.add(str(row["entity"]))
        self._sensor_gemeld_bewaard = set(self._sensor_gemeld)

        grens = dt_util.utcnow() - SESSION_MEMORY
        for row in settings.get("sessions") or []:
            if not isinstance(row, dict) or not row.get("device"):
                continue
            stempel = dt_util.parse_datetime(str(row.get("at") or ""))
            if stempel is None or stempel < grens:
                continue
            device_id = str(row["device"])
            if row.get("approved"):
                self._approved.add(device_id)
            if row.get("boost"):
                self._boost.add(device_id)
            if row.get("paused"):
                self._paused.add(device_id)
            if row.get("mode") in MODI_ZONDER_SOM:
                self._modus[device_id] = str(row["mode"])
            if row.get("target") is not None:
                try:
                    self._doel[device_id] = max(10.0, min(100.0, float(row["target"])))
                except (TypeError, ValueError):
                    pass
            if row.get("drain_to") is not None:
                try:
                    self._drain[device_id] = float(row["drain_to"])
                except (TypeError, ValueError):
                    pass
            if row.get("boost_to") is not None:
                try:
                    self._vol_tot[device_id] = float(row["boost_to"])
                except (TypeError, ValueError):
                    pass
            if row.get("airco_on") or row.get("resident_until") or row.get("airco_w"):
                sessie = self._airco_sessie(device_id)
                try:
                    sessie["gemeten_w"] = float(row["airco_w"]) if row.get("airco_w") else None
                except (TypeError, ValueError):
                    sessie["gemeten_w"] = None
                for sleutel, veld in (("airco_on", "aan_sinds"), ("resident_until", "bewoner_tot")):
                    try:
                        sessie[veld] = datetime.fromisoformat(str(row[sleutel])) if row.get(sleutel) else None
                    except ValueError:
                        sessie[veld] = None
                sessie["reden"] = row.get("airco_reason")

    # ------------------------------------------------------------------
    # Wat een herstart overleeft (v0.172.0)
    #
    # De eigenaar op 28-10-2026: "überhaupt alles wat we maken moet een herstart
    # overleven". In de klantwoning herstartte Home Assistant op 27-10-2026 zes keer
    # (uitgaven en stroomstoringen). Wat de coach van een lopende sessie alleen in het
    # geheugen had, begon dan opnieuw: een klaar-tijd die voorbij was, een boilerbeurt
    # half warm, een lek dat al een uur liep, een vaatwasser die al was vrijgegeven.
    # Per sleutel een klein stuk in `GeheugenStore`, teruggelezen bij de eerste ronde.

    # Wat er van een boilerbeurt over een herstart heen moet (getallen en momenten).
    _BOILER_GETALLEN = ("beurt_kwh", "draai_seconden", "kwh", "zon_kwh", "betaald", "maat", "zon_winst",
                        "accu_kwh", "net_eur")
    _BOILER_MOMENTEN = ("gestart", "gekeken", "nodig_sinds")
    # En van een programma dat vrijgegeven is maar nog niet draait.
    _PROGRAMMA_MOMENTEN = ("vrijgegeven", "gedrukt", "gevraagd", "knop_weg")

    async def _async_geheugen_laden(self) -> None:
        """Wat er voor de herstart onthouden was, terug in de coach."""
        try:
            alles = await async_get_geheugen(self.hass).async_alles(dt_util.utcnow())
        except Exception:  # noqa: BLE001 - zonder geheugen begint hij gewoon opnieuw
            _LOGGER.exception("kon het geheugen niet lezen")
            return
        for sleutel, data in alles.items():
            if sleutel.startswith("laden:"):
                device_id = sleutel.split(":", 1)[1]
                if data.get("te_laat"):
                    self._te_laat.add(device_id)
                mikpunt = _uit_geheugen(data.get("mikpunt"))
                if mikpunt is not None:
                    self._mikpunt_terug[device_id] = mikpunt
            elif sleutel.startswith("accustand:"):
                rij = {k: data.get(k) for k in ("entity", "waarde", "kwh", "laatste", "vast", "gemeld")}
                try:
                    rij["waarde"] = float(rij["waarde"])
                except (TypeError, ValueError):
                    continue
                rij["kwh"] = float(rij.get("kwh") or 0.0)
                rij["vast"], rij["gemeld"], rij["terug"] = bool(rij["vast"]), bool(rij["gemeld"]), False
                self._soc_vast[sleutel.split(":", 1)[1]] = rij
            elif sleutel == "water":
                self._water_loopt_sinds = _uit_geheugen(data.get("sinds"))
                self._water_gemeld = bool(data.get("gemeld")) and self._water_loopt_sinds is not None
            elif sleutel == "meldingen":
                self._meldingen_terug(data)
            else:
                self._geheugen_terug[sleutel] = data

    def _onthoud(self, sleutel: str, data: dict[str, Any] | None, meteen: bool = False) -> None:
        async_get_geheugen(self.hass).zet(sleutel, data, dt_util.utcnow(), meteen=meteen)

    def _laden_onthouden(self, device_id: str) -> None:
        """Of de klaar-tijd voorbij is terwijl de auto niet vol is, en het mikpunt (eis 7)."""
        mikpunt = (self._sessie.get(device_id) or {}).get("mikpunt")
        te_laat = device_id in self._te_laat
        data = {"te_laat": te_laat, "mikpunt": _naar_geheugen(mikpunt)} if te_laat or mikpunt else None
        self._onthoud(f"laden:{device_id}", data, meteen=True)

    def _water_onthouden(self) -> None:
        """Sinds wanneer het water loopt, en of dat al gemeld is."""
        data = None
        if self._water_loopt_sinds is not None:
            data = {"sinds": _naar_geheugen(self._water_loopt_sinds), "gemeld": self._water_gemeld}
        self._onthoud("water", data, meteen=True)

    def _boiler_onthouden(self, device_id: str) -> None:
        """De lopende opwarmbeurt: wat erin ging, wat het kostte, en wat er al gemeld is."""
        sessie = self._boiler.get(device_id)
        if sessie is None:
            return
        data: dict[str, Any] = {k: round(float(sessie.get(k) or 0.0), 5) for k in self._BOILER_GETALLEN}
        data.update({k: _naar_geheugen(sessie.get(k)) for k in self._BOILER_MOMENTEN})
        data["maat_onbekend"] = bool(sessie.get("maat_onbekend"))
        data["net_eur_onbekend"] = bool(sessie.get("net_eur_onbekend"))
        data["reden_aan"] = sessie.get("reden_aan") or ""
        data["vergeefs"] = int(sessie.get("vergeefs") or 0)
        data["gemeld"] = sorted(sessie.get("gemeld") or ())
        data["prijzen"] = self._prijzen_naar_geheugen(sessie.get("prijzen"), sessie.get("nodig_sinds"))
        # Hooguit elke GEHEUGEN_ELKE, want hij telt elke minuut; bij het stoppen altijd.
        self._onthoud(f"boiler:{device_id}", data)

    def _boiler_terug(self, device_id: str, now: datetime) -> dict[str, Any]:
        """Een nieuwe boilersessie, met wat er voor de herstart in de beurt zat.

        Of de stroom erop staat en sinds wanneer meet hij opnieuw: bij het stoppen zet
        `_async_boilers_aan` hem aan, en een herstart is geen bewijs dat hij vol is.
        """
        sessie = self._lege_boiler_sessie(now)
        data = self._geheugen_terug.pop(f"boiler:{device_id}", None)
        if not data:
            return sessie
        for sleutel in self._BOILER_GETALLEN:
            try:
                sessie[sleutel] = max(0.0, float(data.get(sleutel) or 0.0))
            except (TypeError, ValueError):
                pass
        for sleutel in self._BOILER_MOMENTEN:
            sessie[sleutel] = _uit_geheugen(data.get(sleutel))
        sessie["maat_onbekend"] = bool(data.get("maat_onbekend"))
        if data.get("net_eur_onbekend"):
            sessie["net_eur_onbekend"] = True
        sessie["reden_aan"] = str(data.get("reden_aan") or "")
        try:
            sessie["vergeefs"] = max(0, int(data.get("vergeefs") or 0))
        except (TypeError, ValueError):
            pass
        sessie["gemeld"] = {str(g) for g in data.get("gemeld") or []}
        sessie["prijzen"] = self._prijzen_uit_geheugen(data.get("prijzen"))
        return sessie

    # Wat er van een thuisbatterij over een herstart heen moet (v0.173.0): of iets anders hem
    # stuurt (dan laat de coach hem een uur los), of hij de coach niet volgt, en wat de cloud
    # van een Growatt weigerde. Zonder dit nam de coach hem na een herstart meteen weer over,
    # en kwam dezelfde kritieke melding opnieuw.
    _BATTERIJ_MOMENTEN = ("vreemd", "growatt_houden_mis")
    _BATTERIJ_VLAGGEN = ("volgt_niet_gemeld", "growatt_gemeld")

    def _batterij_sessie(self, device_id: str) -> dict[str, Any]:
        """De sessie van een batterij, bij de eerste keer met wat er voor de herstart stond."""
        if device_id in self._batterij:
            return self._batterij[device_id]
        sessie: dict[str, Any] = {"regelaar": Regelaar()}
        data = self._geheugen_terug.pop(f"batterij:{device_id}", None) or {}
        for sleutel in self._BATTERIJ_MOMENTEN:
            moment = _uit_geheugen(data.get(sleutel))
            if moment is not None:
                sessie[sleutel] = moment
        for sleutel in self._BATTERIJ_VLAGGEN:
            if data.get(sleutel):
                sessie[sleutel] = True
        sinds = _uit_geheugen(data.get("volgt_niet"))
        if sinds is not None:
            sessie["volgt_niet"] = (sinds, bool(data.get("volgt_niet_opnieuw")))
        self._batterij[device_id] = sessie
        return sessie

    def _batterij_onthouden(self, device_id: str) -> None:
        sessie = self._batterij.get(device_id)
        if sessie is None:
            return
        data: dict[str, Any] = {}
        for sleutel in self._BATTERIJ_MOMENTEN:
            if sessie.get(sleutel) is not None:
                data[sleutel] = _naar_geheugen(sessie[sleutel])
        for sleutel in self._BATTERIJ_VLAGGEN:
            if sessie.get(sleutel):
                data[sleutel] = True
        if sessie.get("volgt_niet"):
            data["volgt_niet"] = _naar_geheugen(sessie["volgt_niet"][0])
            data["volgt_niet_opnieuw"] = bool(sessie["volgt_niet"][1])
        self._onthoud(f"batterij:{device_id}", data or None, meteen=True)

    def _meldingen_onthouden(self) -> None:
        """Welke meldingen er al gedaan zijn, zodat ze na een herstart niet nog eens komen (v0.173.0).

        Elk van deze komt maar één keer zolang de toestand blijft: een integratie die niet
        opkomt, een batterij die te warm is, een vriezer die openstaat, een smart plug die
        uit staat, de vraag naar de accustand, een tip, en de waarschuwing dat de pauze de
        klaar-tijd kost. Is de toestand na de herstart voorbij, dan ruimt de wacht zijn eigen
        vlag op zoals altijd.
        """
        data = {
            "integratie": sorted(self._integratie_gemeld),
            "inloggen": sorted(self._integratie_inloggen),
            "integratie_stuk": {k: _naar_geheugen(v) for k, v in sorted(self._integratie_stuk.items())},
            "temp": sorted(str(k) for k in self._temp_gemeld),
            "vriezer": sorted([list(k) for k in self._vriezer_gemeld]),
            "stekker": sorted(self._stekker_gemeld),
            "stekker_nieuw": sorted(self._stekker_nieuw),
            "stekker_ooit": sorted(self._stekker_ooit),
            "stekker_sinds": {k: _naar_geheugen(v) for k, v in sorted(self._stekker_uit.items())},
            "stekker_terug": {k: _naar_geheugen(v) for k, v in sorted(self._stekker_terug.items())},
            "sensor_ooit": sorted(self._sensor_ooit),
            "soc_gevraagd": sorted(self._soc_asked),
            "getipt": dict(sorted(self._getipt.items())),
            "gewaarschuwd": {k: _naar_geheugen(v) for k, v in sorted(self._warned.items())},
        }
        self._onthoud("meldingen", data if any(data.values()) else None, meteen=True)

    def _meldingen_terug(self, data: dict[str, Any]) -> None:
        def lijst(sleutel: str) -> list:
            waarde = data.get(sleutel)
            return waarde if isinstance(waarde, list) else []

        def momenten(sleutel: str) -> dict[str, datetime]:
            waarde = data.get(sleutel)
            uit = {}
            for k, v in (waarde.items() if isinstance(waarde, dict) else ()):
                moment = _uit_geheugen(v)
                if moment is not None:
                    uit[str(k)] = moment
            return uit

        self._integratie_gemeld |= {str(k) for k in lijst("integratie")}
        self._integratie_inloggen |= {str(k) for k in lijst("inloggen")}
        self._integratie_stuk.update(momenten("integratie_stuk"))
        self._temp_gemeld |= {str(k) for k in lijst("temp")}
        self._vriezer_gemeld |= {(str(k[0]), str(k[1])) for k in lijst("vriezer") if isinstance(k, list) and len(k) == 2}
        self._stekker_gemeld |= {str(k) for k in lijst("stekker")}
        self._stekker_nieuw |= {str(k) for k in lijst("stekker_nieuw")}
        self._stekker_ooit |= {str(k) for k in lijst("stekker_ooit")}
        for k, v in momenten("stekker_sinds").items():
            self._stekker_uit.setdefault(k, v)
        for k, v in momenten("stekker_terug").items():
            self._stekker_terug.setdefault(k, v)
        self._sensor_ooit |= {str(k) for k in lijst("sensor_ooit")}
        self._soc_asked |= {str(k) for k in lijst("soc_gevraagd")}
        getipt = data.get("getipt")
        if isinstance(getipt, dict):
            self._getipt.update({str(k): str(v) for k, v in getipt.items()})
        self._warned.update(momenten("gewaarschuwd"))

    def _programma_onthouden(self, device_id: str) -> None:
        """Een programma dat vrijgegeven is maar nog niet draait; een draaiende beurt staat
        al in de beurten (`_async_programma_hervatten`)."""
        sessie = self._programma.get(device_id)
        if sessie is None:
            return
        if sessie.get("gestart") is not None or (
            sessie.get("vrijgegeven") is None and not sessie.get("klep_uitruimen")
        ):
            self._onthoud(f"programma:{device_id}", None, meteen=True)
            return
        data: dict[str, Any] = {k: _naar_geheugen(sessie.get(k)) for k in self._PROGRAMMA_MOMENTEN}
        data["pogingen"] = int(sessie.get("pogingen") or 0)
        data["gemeld"] = sorted(sessie.get("gemeld") or ())
        data["klep_uitruimen"] = bool(sessie.get("klep_uitruimen"))
        data["klep_open_gezien"] = bool(sessie.get("klep_open_gezien"))
        data["prijzen"] = self._prijzen_naar_geheugen(sessie.get("prijzen"), sessie.get("vrijgegeven"))
        self._onthoud(f"programma:{device_id}", data, meteen=True)

    def _programma_terug(self, device_id: str, now: datetime) -> dict[str, Any]:
        """Een nieuwe programmasessie, met de vrijgave, de pogingen en de meldingen van voor de herstart.

        Het programma zelf leest hij opnieuw van het apparaat; de vrijgave blijft alleen
        als die nog in `ready_devices` staat, want zonder vrijgave begint de ronde schoon.
        """
        sessie = self._lege_programma_sessie(now)
        data = self._geheugen_terug.pop(f"programma:{device_id}", None)
        if not data:
            return sessie
        for sleutel in self._PROGRAMMA_MOMENTEN:
            sessie[sleutel] = _uit_geheugen(data.get(sleutel))
        try:
            sessie["pogingen"] = max(0, int(data.get("pogingen") or 0))
        except (TypeError, ValueError):
            pass
        sessie["gemeld"] = {str(g) for g in data.get("gemeld") or []}
        if data.get("klep_uitruimen"):
            sessie["klep_uitruimen"] = True
        if data.get("klep_open_gezien"):
            sessie["klep_open_gezien"] = True
        sessie["prijzen"] = self._prijzen_uit_geheugen(data.get("prijzen"))
        return sessie

    @staticmethod
    def _prijzen_naar_geheugen(prijzen: Any, vanaf: datetime | None) -> list:
        """De prijzen vanaf het ijkpunt, als [begin, eind, prijs], voor de maat van Bespaard."""
        if vanaf is None:
            return []
        uit = []
        for rij in prijzen or []:
            try:
                if rij["end"] > vanaf:
                    uit.append([_naar_geheugen(rij["start"]), _naar_geheugen(rij["end"]), float(rij["price"])])
            except (KeyError, TypeError, ValueError):
                continue
        return uit

    @staticmethod
    def _prijzen_uit_geheugen(rijen: Any) -> list[dict[str, Any]]:
        uit = []
        for rij in rijen or []:
            try:
                begin, eind = _uit_geheugen(rij[0]), _uit_geheugen(rij[1])
                if begin is not None and eind is not None:
                    uit.append({"start": begin, "end": eind, "price": float(rij[2])})
            except (IndexError, TypeError, ValueError):
                continue
        return uit

    def _remember(self, device_id: str) -> None:
        """Vastleggen wat er nu voor dit apparaat aan staat.

        Wegschrijven duurt even en de knop moet meteen reageren, dus het gaat
        als eigen taak de wachtrij in. De ronde die er meteen achteraan komt
        leest de vlaggen uit het geheugen en niet uit de opslag, dus die hoeft
        er niet op te wachten.
        """
        self.hass.async_create_task(self._async_remember(device_id))

    async def _async_remember(self, device_id: str) -> None:
        """Het schrijfwerk van `_remember`."""
        aan = {
            "approved": device_id in self._approved,
            "boost": device_id in self._boost,
            "paused": device_id in self._paused,
            "drain_to": self._drain.get(device_id),
            "boost_to": self._vol_tot.get(device_id),
            "mode": self._modus.get(device_id),
            "target": self._doel.get(device_id),
        }
        # Van een airco: dat de coach hem aanzette, en tot wanneer de bewoner
        # wint (v0.119.0). Anders zou na een herstart een airco die de coach op
        # zon aanzette voor eeuwig van de bewoner lijken.
        airco = self._airco.get(device_id) or {}
        for sleutel, waarde in (("airco_on", airco.get("aan_sinds")), ("airco_reason", airco.get("reden")),
                                ("resident_until", airco.get("bewoner_tot")), ("airco_w", airco.get("gemeten_w"))):
            if waarde:
                aan[sleutel] = waarde.isoformat() if isinstance(waarde, datetime) else waarde
        try:
            store = async_get_store(self.hass)
            settings = await store.async_load()
            rows = [
                row
                for row in (settings.get("sessions") or [])
                if isinstance(row, dict) and row.get("device") != device_id
            ]
            if any(aan.values()):
                rows.append(
                    {"device": device_id, **aan, "at": dt_util.utcnow().isoformat()}
                )
            saved = await store.async_save({"sessions": rows})
        except Exception:  # noqa: BLE001 - een knop die werkt gaat voor op onthouden
            _LOGGER.exception("kon de stand van de knoppen niet bewaren")
            return
        self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, {"settings": saved})

    @callback
    def async_approve(self, device_id: str) -> None:
        """The customer agreed to this charging session."""
        self._approved.add(device_id)
        self._remember(device_id)
        self.async_refresh()

    @callback
    def async_withdraw(self, device_id: str) -> None:
        """And can take that back."""
        self._approved.discard(device_id)
        self._remember(device_id)
        self.async_refresh()

    @callback
    def async_boost(self, device_id: str, on: bool, to_percent: float | None = None) -> None:
        """Snelladen aan of uit: laden op vol vermogen, ongeacht de prijs.

        Bij een thuisbatterij met een doel (v0.141.0): "Nu vol laden" tot die
        accustand, gekozen met de schuif in de pop-up.
        """
        if on and to_percent is not None:
            self._vol_tot[device_id] = float(to_percent)
            self._drain.pop(device_id, None)
        else:
            self._vol_tot.pop(device_id, None)
        if on:
            self._boost.add(device_id)
            # Twee tegengestelde opdrachten van dezelfde persoon: de laatste
            # telt. Anders zou snelladen aanstaan terwijl er niets gebeurt.
            self._paused.discard(device_id)
        else:
            self._boost.discard(device_id)
        self._remember(device_id)
        self.async_refresh()

    @callback
    def async_drain(self, device_id: str, to_percent: float | None) -> None:
        """De thuisbatterij nu leegladen tot een accustand, of daarmee ophouden.

        De bewoner van de eerste woning op 22-09-2026: "naast pauze en laad
        snel vol ook een knop laad snel leeg, met een minimale accustand: nu
        maximaal ontladen tot 50%, daarna terug naar normale modus." Naar het
        net, op het ontlaadvermogen van de batterij; gaat vanzelf uit op de
        gekozen stand, en nooit onder de eigen ondergrens van de batterij.
        """
        if to_percent is None:
            self._drain.pop(device_id, None)
        else:
            self._drain[device_id] = float(to_percent)
            self._boost.discard(device_id)
            self._vol_tot.pop(device_id, None)
        self._remember(device_id)
        self.async_refresh()

    @callback
    def async_mode(self, device_id: str, mode: str) -> None:
        """De modus voor deze beurt: snel, continu, zon, of "" voor de voorkeur.

        De eigenaar op 23-09-2026: drie knoppen op de kaart, zoals bij evcc.
        Snel is snelladen en blijft dat; continu en zon zetten snelladen uit,
        en snel zet de gekozen modus terug naar de voorkeur. Alles vervalt als
        de kabel eruit gaat.
        """
        if mode == "snel":
            self._modus.pop(device_id, None)
            self.async_boost(device_id, True)
            return
        self._boost.discard(device_id)
        if mode in MODI_ZONDER_SOM or mode == "goedkoopst":
            self._modus[device_id] = mode
        else:
            self._modus.pop(device_id, None)
        self._remember(device_id)
        self.async_refresh()

    @callback
    def async_target(self, device_id: str, percent: float | None) -> None:
        """Tot hoeveel procent deze beurt laadt, of None voor het autoprofiel.

        De bewoner van de eerste woning op 23-09-2026, over evcc: "in de auto
        een harde max (100%), en in evcc een gewenste accustand van
        bijvoorbeeld 80." De laadgrens in de auto blijft de bovengrens; dit is
        waar de coach zelf ophoudt, en waar hij voor plant.
        """
        if percent is None:
            self._doel.pop(device_id, None)
        else:
            self._doel[device_id] = max(10.0, min(100.0, float(percent)))
        self._remember(device_id)
        self.async_refresh()

    def _modus_van(self, device: dict[str, Any]) -> str:
        """De modus die nu geldt: de keuze van deze beurt, anders de voorkeur."""
        gekozen = self._modus.get(device.get("id", ""))
        if gekozen:
            return gekozen
        voorkeur = str(device.get("charge_mode") or "goedkoopst")
        return voorkeur if voorkeur in (*MODI_ZONDER_SOM, "goedkoopst") else "goedkoopst"

    @callback
    def async_boosting(self, device_id: str) -> bool:
        """Of snelladen op dit moment aanstaat."""
        return device_id in self._boost

    @callback
    def async_pause(self, device_id: str, on: bool) -> None:
        """Met de hand pauzeren of hervatten.

        Anders dan de knoppen bij Handmatige besturing gaat dit niet langs de
        coach heen maar erdoorheen: hij weet ervan en houdt zijn handen thuis.
        Zonder dat zette de klant het laden stil en zette de coach het een minuut
        later weer aan, en dan is het een knop die niet werkt.
        """
        if on:
            self._paused.add(device_id)
            self._boost.discard(device_id)
        else:
            self._paused.discard(device_id)
        self._remember(device_id)
        self.async_refresh()

    @callback
    def async_paused(self, device_id: str) -> bool:
        """Of de bewoner op dit moment zelf gepauzeerd heeft."""
        return device_id in self._paused

    async def _apply(
        self, device: dict[str, Any], charger: Charger, decision: Decision, now: datetime
    ) -> bool:
        """Send it, in the order the hardware wants.

        The limit goes first and the start second, with a check in between that
        the charger really took the new limit. Blindly waiting a fixed second or
        two is either too short on a slow evening or wasted the rest of the
        time, and the panel already reads the limit back anyway.

        **Er wordt nooit een stopcommando gestuurd.** Dat is geen voorkeur maar
        een meting aan een echte paal: een stop haalt de goedkeuring van de
        sessie eraf, en die moet daarna opnieuw gegeven worden. Niet laden gaat
        daarom langs dezelfde weg als wel laden, namelijk de limiet, met een 0
        erin. De sessie blijft dan gewoon goedgekeurd en hervatten is niets meer
        dan een gewoon getal terugschrijven.
        """
        control = CHARGER_CONTROL.get(device.get("brand", ""))
        if not control or not self._stuuradres(device, control):
            return False

        if not decision.charge:
            return await self._pause(device, control, charger, decision, now)

        self._pause_until.pop(device.get("id", ""), None)
        await self._limit(device, control, decision.amps, 0)

        if charger.paused_by_balancer:
            # The limit above is still worth sending: it is our standing request
            # and the balancer works on the lowest of all the limits, so it has
            # to be in place for the moment room appears. Starting is not worth
            # sending. The charger is being held by something that does not
            # listen to us, and asking again every minute only fills its log.
            _LOGGER.debug(
                "laadpaal %s wordt tegengehouden door de lastbewaking; niet gestart",
                device.get("id"),
            )
            return True

        if not charger.charging:
            if not await self._confirmed(device, decision.amps):
                # Toch starten. De limiet die er dan staat is er een die de paal
                # eerder heeft aangenomen en ligt dus altijd onder zijn eigen
                # maximum, dus het is veilig. Niet starten zou betekenen dat een
                # auto de hele nacht leeg blijft omdat één sensor een andere
                # naam of een andere eenheid heeft dan verwacht, en dat is de
                # ene fout die een klant nooit vergeeft.
                _LOGGER.warning(
                    "laadpaal %s bevestigde de limiet van %s A niet; toch gestart",
                    device.get("id"),
                    decision.amps,
                )
            await self._command(device, control, "start")
            if device.get("id", "") in self._herstart_open:
                self._herstart_open.discard(device.get("id", ""))
                self._herstart_gedaan[device.get("id", "")] = now
                self._herstart_melden.add(device.get("id", ""))

        return True

    async def _limit(
        self, device: dict[str, Any], control: dict[str, Any], amps: int, minutes: int
    ) -> None:
        """De dynamische limiet zetten, met de houdbaarheid die erbij hoort.

        `minutes` is 0 voor "tot nader order". Dat is het gewone geval voor een
        limiet waarop geladen wordt: valt de coach weg, dan laadt de auto door op
        een stroom die de paal eerder heeft aangenomen, en dat is veilig. Voor
        een 0 ligt het andersom en staat de afweging bij `FOREVER_RULES`.
        """
        domain, service = control["limit_service"]
        if control.get("limit_entity"):
            # Een paal met een limiet-entiteit (Alfen): het getal gaat de
            # number in, zonder houdbaarheid, want die heeft de paal zelf.
            await self._paal_dienst(
                domain,
                service,
                {"entity_id": self._stuuradres(device, control), control["limit_field"]: amps},
            )
            return
        await self._paal_dienst(
            domain,
            service,
            {
                "device_id": device["device_id"],
                control["limit_field"]: amps,
                control["ttl_field"]: minutes,
            },
        )

    async def _paal_dienst(self, domain: str, service: str, data: dict[str, Any]) -> None:
        """Een opdracht aan de laadpaal; komt hij niet aan, dan `PaalOnbereikbaar` (v0.163.3).

        Een dienst die niet bestaat blijft `ServiceNotFound`: dat is het opstarten, met een
        eigen regel in de lus van de palen.
        """
        try:
            await self.hass.services.async_call(domain, service, data, blocking=True)
        except ServiceNotFound:
            raise
        except Exception as fout:  # noqa: BLE001 - elke integratie heeft zijn eigen fout
            raise PaalOnbereikbaar(str(fout) or type(fout).__name__) from fout

    async def _async_paal_weg(self, device: dict[str, Any], now: datetime, fout: Exception) -> None:
        """Een paal waar een opdracht niet aankwam: één regel in het log, en na `SENSOR_STIL` een melding.

        In een klantwoning herstartte een Alfen zich op 26-10-2026 twee keer, en zes minuten lang
        gaf elke ronde een fout met de hele traceback ("kon ... niet beoordelen"). De auto stond al
        stil, en zodra de paal terug was stuurde de coach hem weer goed. Net als een sensor die
        zwijgt: korter dan tien minuten zegt niets.
        """
        device_id = device.get("id", "")
        sinds = self._paal_weg.get(device_id)
        if sinds is None:
            self._paal_weg[device_id] = now
            _LOGGER.warning("%s is niet bereikbaar, de coach probeert het elke ronde opnieuw: %s", device_id, fout)
            return
        if device_id in self._paal_gemeld or _tussen(sinds, now) < SENSOR_STIL:
            return
        self._paal_gemeld.add(device_id)
        minuten = int(_tussen(sinds, now).total_seconds() // 60)
        _LOGGER.warning("%s is al %d minuten niet bereikbaar: %s", device_id, minuten, fout)
        naam = device.get("name") or t("De laadpaal")
        await self._async_tell(
            t(
                "{naam} is al {minuten} minuten niet bereikbaar. De coach probeert het elke minuut opnieuw.",
                naam=f"{naam[0].upper()}{naam[1:]}", minuten=minuten,
            ),
            kritiek=True,
        )

    async def _async_paal_terug(self, device: dict[str, Any]) -> None:
        """Een paal die weer opdrachten aanneemt: een regel in het log, en gemeld ook in de geschiedenis."""
        device_id = device.get("id", "")
        if self._paal_weg.pop(device_id, None) is None:
            return
        _LOGGER.info("%s is weer bereikbaar", device_id)
        if device_id in self._paal_gemeld:
            self._paal_gemeld.discard(device_id)
            naam = device.get("name") or t("De laadpaal")
            await self._async_tell(
                t("{naam} doet het weer.", naam=f"{naam[0].upper()}{naam[1:]}"), telefoon=False
            )

    @staticmethod
    def _stuuradres(device: dict[str, Any], control: dict[str, Any]) -> str:
        """Waar de opdrachten heen gaan.

        Bij Easee het HA-apparaat (`device_id`), want `action_command` en de
        dynamische limiet willen een apparaat. Bij Alfen de limiet-entiteit,
        want daar is niets anders om naartoe te schrijven. Leeg betekent dat
        de coach deze paal niet kan sturen.
        """
        if control.get("limit_entity"):
            return (device.get("entities") or {}).get(control["limit_entity"]) or ""
        return device.get("device_id") or ""

    @staticmethod
    def _ververst(device: dict[str, Any]) -> bool:
        """Of deze paal zijn limiet elke ronde opnieuw moet krijgen.

        Een Alfen vergeet zijn limiet na zijn geldigheidsduur en valt dan terug
        op zijn veilige stroom; de dode band op het besluit geldt daar dus
        niet. Zie `CHARGER_CONTROL`.
        """
        return bool(CHARGER_CONTROL.get(device.get("brand", ""), {}).get("refresh"))

    @staticmethod
    def _niets_schrijven(charger: Charger, decision: Decision) -> bool:
        """Of dit besluit de paal helemaal met rust laat.

        Zonder kabel valt er niets tegen te houden, en bij een auto die zelf
        gestopt is zou een 0 die blijft staan de volgende auto in de weg zitten.

        Behalve als de paal op dit moment nog laadt. Dan is "klaar" geen
        constatering maar een besluit van de coach: de accustand zegt dat het
        doel gehaald is terwijl de auto nog best wil. Sinds 16-09-2026 kan dat,
        want het doel hoeft niet meer honderd procent te zijn. Zonder deze
        uitzondering bleef de bus in het virtuele huis na "de auto staat op 80%"
        gewoon doorlopen tot 100, en dan is de instelling een mededeling in
        plaats van een opdracht.
        """
        if not charger.connected:
            return True
        if decision.rule not in NO_WRITE_RULES:
            return False
        return not charger.charging

    async def _pause(
        self,
        device: dict[str, Any],
        control: dict[str, Any],
        charger: Charger,
        decision: Decision,
        now: datetime,
    ) -> bool:
        """Niet laden, en dat vasthouden zonder de sessie op te breken."""
        device_id = device.get("id", "")

        # Een Alfen vergeet zijn 0 na zijn geldigheidsduur en laadt dan op zijn
        # veilige stroom door. Zolang er een auto hangt gaat de 0 er dus elke
        # ronde opnieuw in, ook bij "klaar": in het virtuele huis viel de paal
        # anders vijf minuten na het doel terug op 16 A (23-09-2026). Zonder
        # auto schrijft hij niets, en dan is de veilige stroom precies wat
        # de volgende auto hoort te krijgen.
        if self._niets_schrijven(charger, decision) and not (
            self._ververst(device) and charger.connected
        ):
            self._pause_until.pop(device_id, None)
            return True

        # Houdt de coach zelf op terwijl de paal nog laadt (`_niets_schrijven`
        # liet ons hier juist dóór omdat het doel gehaald is), dan hoort die 0
        # te blijven staan. Met een houdbaarheid loopt hij af, pakt de paal zijn
        # eigen limiet weer en laadt de auto alsnog door: in het virtuele huis
        # gaf dat honderdveertig wissels en 3,2 kWh van het net op een auto die
        # allang op 80% stond.
        blijvend = decision.rule in FOREVER_RULES or decision.rule in NO_WRITE_RULES
        minutes = 0 if blijvend else (decision.hold_minutes or 0)
        await self._limit(device, control, 0, minutes)

        if minutes:
            self._pause_until[device_id] = now + timedelta(minutes=minutes)
        else:
            self._pause_until.pop(device_id, None)
        return True

    async def _confirmed(self, device: dict[str, Any], amps: int) -> bool:
        """Wait until the charger reports the limit we just set."""
        entity_id = (device.get("entities") or {}).get("dynamic_limit")
        if not entity_id:
            # Nothing to check against, so fall back to giving it a moment.
            await self._sleep(2)
            return True

        for _ in range(CONFIRM_SECONDS):
            if (_number(self.hass, entity_id) or -1) >= amps - 0.5:
                return True
            await self._sleep(1)
        return False

    async def _sleep(self, seconds: float) -> None:
        """Waiting that a test can shortcut."""
        import asyncio

        await asyncio.sleep(seconds)

    async def _command(
        self, device: dict[str, Any], control: dict[str, Any], action: str
    ) -> None:
        """Start, stop or pause, in the word this installation uses.

        Een paal zonder opdrachten (Alfen) krijgt niets: daar is een limiet
        boven de ondergrens de start, en die is al geschreven.
        """
        if not control.get("command_service"):
            return
        domain, service = control["command_service"]
        word = (device.get("actions") or {}).get(action) or control["words"][action]
        await self._paal_dienst(
            domain,
            service,
            {"device_id": device["device_id"], control["command_field"]: word},
        )


@callback
def async_get_coach(hass: HomeAssistant) -> ChargerCoach:
    """The one coach for this Home Assistant."""
    data = hass.data.setdefault(DOMAIN, {})
    if "coach" not in data:
        data["coach"] = ChargerCoach(hass)
    return data["coach"]
