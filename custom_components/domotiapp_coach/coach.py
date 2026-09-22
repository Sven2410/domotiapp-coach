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
import logging
from dataclasses import asdict, replace
from datetime import datetime, time, timedelta, timezone
from functools import partial
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceNotFound
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    NETTING_ENDS,
    CHARGER_CONTROL,
    DOMAIN,
    EVENT_DECISION,
    EVENT_NOTIFICATION,
    EVENT_SETTINGS_UPDATED,
    LEVEL_ADVISE,
    LEVEL_PROPOSE,
    LEVEL_READ,
    LEVEL_STEER,
    PHASE_START_AMPS,
    PROGRAMMA_TYPES,
    TEMPO_ONDERGRENS,
)
from .archive import async_get_archive
from .batterij import (
    MAX_LADEN,
    NETLADEN,
    STAND_NAMEN,
    VOL_MARGE,
    Batterij,
    Regelaar,
    balans_kwh,
    plan_batterij,
    rendement_uit_tellers,
    terugverdiend,
    verdiend,
    vol_voor,
)
from .planner import (
    Apparaat,
    BALANCER_MARGIN_AMPS,
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
    PROFIEL_STAP_MIN,
    profiel_van,
    profiel_gemiddeld,
    CHARGE_EFFICIENCY,
    FUSE_MARGIN_AMPS,
    FUSE_MARGIN_SHARE,
    Car,
    Charger,
    Circuit,
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
    decide,
    timeline,
    FULL_PERCENT,
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
)
from .ontvangers import ontvangers
from .storage import async_get_beurten, async_get_meldingen, async_get_store
from .units import hour_to_watts, to_kwh, to_watts

_LOGGER = logging.getLogger(__name__)

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
# Hoe vaak wat de batterij verdiende naar de opslag gaat, en hoeveel dagen
# daarvan bewaard blijven: ruim een jaar, zodat de terugverdientijd zomer en
# winter allebei kent.
BATTERIJ_BEWAREN = timedelta(minutes=5)
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
ZON_VERVERSEN = timedelta(minutes=30)

# Over hoeveel dagen het huisverbruik wordt gemeten. Een week vangt het verschil
# tussen doordeweeks en weekend en is kort genoeg om een seizoen te volgen.
HUIS_VENSTER = timedelta(days=7)


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

# Hoeveel twee ronden van elkaar mogen verschillen voordat het geen meting meer
# is maar een sensor die nog aan het bijkomen is. Zie `_tempo_leren`. Ruim
# genoeg voor het gewiebel van een paal die op zijn limiet moduleert, krap
# genoeg dat een tussenstand van bijna nul er niet doorheen komt.
TEMPO_SPELING = 0.3

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


def _watts(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Een vermogenssensor in watt, wat hij zichzelf ook noemt.

    Alles wat vermogen is gaat hierlangs en niet langs `_number`. Zie
    `units.py` voor waarom dat een klant een laadbeurt kon kosten.
    """
    return to_watts(_number(hass, entity_id), _unit(hass, entity_id))


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
    per blok een regel werd overgeslagen zonder spoor in enig logboek. Bij Van
    den Dam sneuvelden op 29-08-2026 zo alle 24 uurblokken tegelijk en zei de
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


def _eindtijd(
    hass: HomeAssistant, entity_id: str | None, now: datetime, sinds: datetime | None = None
) -> datetime | None:
    """Wanneer het apparaat zelf zegt klaar te zijn, of None.

    Home Connect geeft de resterende tijd als een tijdstip (de sensor
    `remaining_program_time`, een timestamp); andere integraties geven de
    minuten of de seconden die nog resten. Allebei hetzelfde antwoord op
    dezelfde vraag, als lokaal tijdstip zonder zone, zoals `now`. De eigenaar op
    07-09-2026: "pak de eindtijd van de integratie."

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
    seconden = getal if eenheid in ("s", "sec", "seconds") else getal * 60.0
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
        return f"morgen om {moment:%H:%M}"
    dagen = ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag")
    return f"{dagen[moment.weekday()]} om {moment:%H:%M}"


def _time(value: str | None) -> time | None:
    """"07:00" as a time, or None."""
    if not value:
        return None
    try:
        hour, minute = value.split(":")
        return time(int(hour), int(minute))
    except (ValueError, AttributeError):
        return None


class ChargerCoach:
    """Watches every steerable charging point and acts on what it sees."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up without touching anything yet."""
        self.hass = hass
        self._cancel = None
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
        # erbij. Alleen om de na-ijl van de fasemeting op te vangen als de paal
        # net gestopt is; zie `_read`.
        self._laatste_stroom: dict[str, tuple[float, datetime]] = {}
        # De laatste bruikbare status per laadpunt, zodat een entiteit die even
        # wegvalt niet als een losgekoppelde kabel leest. Zie `_read`.
        self._laatste_status: dict[str, str] = {}
        # En hetzelfde voor de metingen: per entiteit de laatste bruikbare
        # waarde met het moment erbij. Zie `_volgehouden` en `MEETNAIJL`.
        self._laatste_meting: dict[str, tuple[float, datetime]] = {}
        # De laatste ronde waarin de netmeting wél te lezen was, en sinds
        # wanneer hij zwijgt. Alleen om het te kunnen zeggen; zie `_nettip`.
        self._net_gezien: datetime | None = None
        self._net_stil_sinds: datetime | None = None
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
        self._batterij_meters: set[str] = set()
        self._unwatch_batterij = None
        self._cancel_regel = None
        # Per sensor sinds wanneer hij niets zegt, en welke daarvan al gemeld zijn.
        self._sensor_stil: dict[str, datetime] = {}
        self._sensor_gemeld: set[str] = set()
        # Wanneer de auto aan een laadpunt voor het laatst gewekt is, en of de
        # kabel er de vorige ronde al in zat. Zie `_async_auto_wekken`.
        self._gewekt: dict[str, datetime] = {}
        self._kabel_erin: dict[str, bool] = {}
        self._huis_tot: datetime | None = None
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
        # En wie er met de hand op pauze staat. Zelfde levensduur, tegengestelde
        # bedoeling.
        self._paused: set[str] = set()
        # Hoeveel ronden een sessie al tegen de ladder in wordt aangehouden.
        self._holding: dict[str, int] = {}
        # Het laatste besluit dat in de geschiedenis staat, per paal, zodat
        # alleen een verandering een regel oplevert en niet elke minuut.
        self._besluit_genoteerd: dict[str, tuple[Any, ...]] = {}
        # Beurten die bij een herstart nog open stonden in de opslag, per
        # apparaat: het geld van de beurt loopt daar gewoon in door.
        self._beurt_open: dict[str, dict[str, Any]] = {}
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
        # Wat er de afgelopen METER_VENSTER per ronde naar het net ging:
        # (moment, watt). Zie `_meter_zeker`.
        self._meter: list[tuple[datetime, float]] = []
        self._herstart_open: set[str] = set()
        self._herstart_gedaan: dict[str, datetime] = {}
        self._herstart_melden: set[str] = set()
        # Sinds wanneer de paal van dit laadpunt "klaar" zegt. Het ijkpunt voor
        # `_soc_bezonken`: een accustand van vóór dit moment hoort nog bij het
        # laden en zegt niets over waar de auto geëindigd is.
        self._klaar_sinds: dict[str, datetime] = {}
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
        # De kleinste sprong die deze sensor liet zien: zijn resolutie.
        self._soc_stap: dict[str, float] = {}
        # Het aantal fasen zoals het deze ronde gemeten is, per laadpunt. Eén
        # meting per ronde, want `_fasen_stabiel` telt ronden.
        self._fase_nu: dict[str, int | None] = {}
        # Wat de auto deze beurt per band van tien procent aannam terwijl hij
        # zelf de rem was, in kW: het laagste per band. Zie `_tempo_leren`.
        self._tempo_gezien: dict[str, dict[int, float]] = {}
        # De meting van de vorige ronde, per apparaat: band en kW. Een tempo
        # telt pas als twee ronden achter elkaar hetzelfde zeggen; zie
        # `_tempo_leren`.
        self._tempo_vorig: dict[str, tuple[int, float]] = {}
        # Bij welke accustand het laagste per band gemeten is, zodat een latere
        # meting erboven hem kan weerleggen; zie `_tempo_weerleggen`.
        self._tempo_soc: dict[str, dict[int, float]] = {}
        # De limiet van de vorige ronde en wanneer hij voor het laatst omhoog
        # ging. Zie `TEMPO_HERSTEL`.
        self._limiet_vorig: dict[str, float] = {}
        self._limiet_omhoog: dict[str, datetime] = {}
        # De band waarin de vorige ronde meer liep dan het bekende tempo. Twee
        # ronden achter elkaar voordat een tempo vervalt, net als bij het leren.
        self._weerleg_vorig: dict[str, int] = {}
        self._auto_id: dict[str, str] = {}
        # Sinds wanneer er stroom wordt aangeboden zonder dat de auto iets
        # afneemt. Daarmee weet de kaart het verschil tussen "begint zo" en "de
        # auto doet niets". Een tijdstip en geen teller: een ronde is niet altijd
        # een minuut, want een statuswissel van de paal start er ook een.
        self._asking_since: dict[str, datetime] = {}
        # Laadpunten waarvan de klaar-tijd verstreken is terwijl de auto niet vol
        # was. Die laden door tot ze vol zijn, want vol worden weegt zwaarder dan
        # goedkoop laden. Vervalt zodra de auto vol is of de kabel eruit gaat.
        self._te_laat: set[str] = set()
        # Wat er in deze laadbeurt gebeurd is: wanneer hij begon, hoeveel er in
        # ging en waar de tijd aan op is gegaan. Alleen om het achteraf te
        # kunnen navertellen, nooit om een besluit op te nemen.
        self._sessie: dict[str, dict[str, Any]] = {}
        # Laadbeurten waarvan de kabel eruit is en waar nog een verslag over
        # hoort te komen. Staat los van `_sessie`, want die is dan al opgeruimd
        # en mag ook niet blijven staan: een nieuwe kabel is een nieuwe beurt.
        self._afscheid: dict[str, tuple[datetime, dict[str, Any]]] = {}
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
        self._getipt: set[str] = set()
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
            "onbekend hoe lang"
            if self._last_round is None
            else f"al {int((moment - self._last_round).total_seconds() // 60)} minuten"
        )
        _LOGGER.error("de coach heeft %s geen ronde afgemaakt", minuten)
        await self._async_tell(
            f"De coach heeft {minuten} niets meer beslist. Wat er nu op je "
            "laadpaal staat blijft staan tot hij weer draait. Kijk in het "
            "logboek van Home Assistant wat er misging.",
            kritiek=True,
        )

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

    async def _async_noteer(self, message: str, now: datetime) -> None:
        """Een besluit in de geschiedenis, en naar wie dat per se wil.

        Elk besluit hoort terug te lezen te zijn, maar niemand wil er 's nachts
        een telefoon van horen zoemen. Vandaar dat de soort "besluit" bij een
        nieuwe persoon uit staat; wie alles wil volgen zet hem zelf aan.
        """
        await self._async_versturen(message, "besluit")
        try:
            entry = await async_get_meldingen(self.hass).async_add(message, now, "besluit")
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
        naam = device.get("name") or "De laadpaal"
        kop = f"laden op {st.get('amps')} A" if st.get("charge") else "niet laden"
        if not st.get("applied"):
            kop = f"zou {kop}, maar de coach stuurt nu niet"
        reden = (st.get("reason") or "").strip()
        await self._async_noteer(f"{naam}: {kop}. {reden}".strip(), now)

    def _sensoren(self, settings: dict[str, Any]) -> dict[str, str]:
        """Elke sensor waar de coach op rekent, met hoe de bewoner hem kent.

        De slimme meter zelf staat er niet in: die heeft zijn eigen zin op de
        kaart en zijn eigen melding (`_nettip`), na vijf minuten, want zonder
        netmeting valt de zonregel meteen weg.
        """
        uit: dict[str, str] = {}
        bronnen = settings.get("sources") or {}
        for i, zon in enumerate(zonsensoren(settings)):
            uit[zon] = "de zonnesensor" if i == 0 else f"de zonnesensor van omvormer {i + 1}"
        for fase, velden in (bronnen.get("phases") or {}).items():
            if isinstance(velden, dict) and velden.get("current"):
                uit[velden["current"]] = f"de stroommeting van fase {str(fase).upper()}"
        installation = settings.get("installation") or {}
        for groep in installation.get("circuits") or []:
            if not isinstance(groep, dict):
                continue
            for fase, velden in (groep.get("sensors") or {}).items():
                if isinstance(velden, dict) and velden.get("current"):
                    uit[velden["current"]] = (
                        f"de stroommeting van fase {str(fase).upper()} van de groep "
                        f"{groep.get('name') or groep.get('id')}"
                    )
        if installation.get("load_balancer") and installation.get("balancer_entity"):
            uit[installation["balancer_entity"]] = "je lastbewaker"
        contract = settings.get("contract") or {}
        if contract.get("type") == "dynamic":
            dynamic = contract.get("dynamic") or {}
            if dynamic.get("source") == "all_in" and dynamic.get("all_in_entity"):
                uit[dynamic["all_in_entity"]] = "je prijssensor"
            elif dynamic.get("market_entity"):
                uit[dynamic["market_entity"]] = "je marktprijssensor"
        for device in settings.get("devices") or []:
            naam = device.get("name") or "een apparaat"
            if device.get("entity"):
                uit[device["entity"]] = f"het vermogen van {naam}"
            entities = device.get("entities") or {}
            for sleutel, wat in (
                ("status", "de status"),
                ("current", "de stroommeting"),
                ("dynamic_limit", "de dynamische laadgrens"),
                ("max_limit", "de laderlimiet"),
            ):
                if entities.get(sleutel):
                    uit[entities[sleutel]] = f"{wat} van {naam}"
            for car in device.get("cars") or []:
                # Een auto met een wekknop slaapt als hij niet laadt en meldt
                # dan niets; dat is geen storing maar zijn aard. De eigenaar op
                # 22-09-2026: "daardoor krijg ik telkens een melding van tesla
                # meldt al 10 min niks."
                if car.get("soc_entity") and not car.get("wake_entity"):
                    uit[car["soc_entity"]] = f"de accustand van {car.get('name') or 'de auto'}"
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
        """
        zonnen = set(zonsensoren(settings))
        auto_sensoren = {
            car.get("soc_entity")
            for device in settings.get("devices") or []
            for car in device.get("cars") or []
            if car.get("soc_entity")
        }
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
                if entity_id in self._sensor_gemeld:
                    self._sensor_gemeld.discard(entity_id)
                    await self._async_tell(
                        f"{naam[0].upper()}{naam[1:]} doet het weer.", telefoon=False
                    )
                self._sensor_stil.pop(entity_id, None)
                continue
            if sinds is None:
                self._sensor_stil[entity_id] = now
                continue
            grens = SENSOR_STIL_AUTO if entity_id in auto_sensoren else SENSOR_STIL
            if entity_id in self._sensor_gemeld or now - sinds < grens:
                continue
            self._sensor_gemeld.add(entity_id)
            minuten = int((now - sinds).total_seconds() // 60)
            # De entiteit-id staat in het log en niet in de melding. De eigenaar op
            # 21-09-2026, over precies deze zin: "meld zo'n sensor niet
            # volledig, zeg gewoon dat er iets mis is met de integratie". Wie
            # hem moet opzoeken kijkt in het log; wie hem leest heeft genoeg aan
            # de naam die hij zelf heeft ingevuld.
            _LOGGER.warning(
                "%s (%s) meldt al %d minuten niets", naam, entity_id, minuten
            )
            await self._async_tell(
                f"{naam[0].upper()}{naam[1:]} meldt al {minuten} minuten niets. "
                "Waarschijnlijk hapert de integratie erachter. De coach rekent "
                "zolang zonder.",
                kritiek=True,
            )

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
        while historie and historie[0][0] < grens:
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
        if self._running:
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

        if not self._restored:
            # Eén keer, vóór de eerste ronde: de beurten die nog liepen toen
            # Home Assistant stopte, zodat hun geld gewoon doortelt.
            await self._async_beurten_laden()
        self._restore(settings)

        level = (settings.get("strategy") or {}).get("level", LEVEL_PROPOSE)
        moment = _moment(now)

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
        batterijen = [
            device
            for device in settings.get("devices") or []
            if device.get("type") == "thuisbatterij" and device.get("controllable")
        ]
        self._watch_batterij(settings, batterijen)
        self._watch(
            {
                entity
                for device in chargers
                if (entity := (device.get("entities") or {}).get("status"))
            }
            | {
                entity
                for device in programma_apparaten
                for sleutel in ("release_switch", "release_now_switch", "status")
                if (entity := (device.get("entities") or {}).get(sleutel))
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
        await self._async_sensorwacht(settings, moment)
        await self._async_zonkromme(settings, moment)
        self._meter_bijhouden(settings, moment)

        # De batterij eerst: wat hij deze minuut doet bepaalt wat de meter de
        # andere apparaten laat zien.
        for device in batterijen:
            try:
                await self._one_batterij(moment, settings, device, level)
            except ServiceNotFound:
                _LOGGER.warning(
                    "%s kan nog niet aangestuurd worden: de integratie van de batterij is er nog niet",
                    device.get("name") or device.get("id"),
                )
            except Exception:  # noqa: BLE001 - one broken device is not all of them
                _LOGGER.exception("kon %s niet beoordelen", device.get("id"))
        # Een batterij die niet meer gestuurd mag worden gaat terug naar zijn
        # eigen stand, ook als het vinkje eraf ging.
        for device_id, sessie in list(self._batterij.items()):
            if device_id in {d.get("id") for d in batterijen}:
                continue
            oud = next((d for d in settings.get("devices") or [] if d.get("id") == device_id), None)
            if sessie.get("stuurt") and oud is not None:
                await self._async_batterij_loslaten(oud)
            self._batterij.pop(device_id, None)
            self.state.pop(device_id, None)

        chargers.sort(key=lambda device: self._priority(settings, device))
        # Wat er deze ronde al aan een eerder laadpunt is toegezegd, per
        # zekering: "" is de hoofdaansluiting, verder het id van elke groep.
        # Twee palen op dezelfde groep delen die groep; een paal in de garage
        # en een aan de meterkast delen alleen de hoofdaansluiting.
        vergeven: dict[str, float] = {}
        for device in chargers:
            try:
                claim = await self._one(moment, settings, device, level, vergeven)
                for sleutel in self._groep_sleutels(settings, device):
                    vergeven[sleutel] = vergeven.get(sleutel, 0.0) + claim
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
            except Exception:  # noqa: BLE001 - one broken device is not all of them
                _LOGGER.exception("kon %s niet beoordelen", device.get("id"))

        # En de apparaten met een programma: die starten één keer.
        for device in settings.get("devices") or []:
            if device.get("type") not in PROGRAMMA_TYPES or not device.get("controllable"):
                continue
            try:
                await self._one_programma(moment, settings, device, level)
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
            except ServiceNotFound:
                _LOGGER.warning(
                    "%s kan nog niet aangestuurd worden: de schakelaar bestaat niet (nog niet geladen?)",
                    device.get("name") or device.get("id"),
                )
            except Exception:  # noqa: BLE001 - one broken device is not all of them
                _LOGGER.exception("kon %s niet beoordelen", device.get("id"))

        return True

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
        naam = device.get("name") or "De vaatwasser"
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
        tabel = met_metingen(
            tabel_van(device.get("programs")), settings.get("program_measured"), device_id
        )

        released = device_id in (settings.get("ready_devices") or [])
        # Een vrijgaveschakelaar naast de knop op de kaart. De eigenaar op 06-09-2026:
        # een eigen kaart in de keuken met een knop "sturing" die een
        # schakelaar aanzet, "en dan wil ik dat Ingeruimd en dicht aangaat."
        # De twee volgen elkaar: beweegt de schakelaar, dan volgt de vrijgave;
        # beweegt de knop op de kaart, dan volgt de schakelaar; en na een
        # beurt gaan ze allebei uit.
        released = await self._async_schakelaar_volgen(settings, device, sessie, released)
        # En "ingeruimd en nu starten", op de kaart of met een eigen schakelaar
        # (de eigenaar, 13-09-2026).
        released, nu_starten = await self._async_nu_volgen(settings, device, sessie, released)
        # Wat erop staat: de sensor, of anders de select-entiteit waarmee het
        # gezet wordt (Home Connect heeft ze allebei; de eigenaar heeft de sensor).
        programma_entiteit = entities.get("program") or entities.get("program_select")
        if programma_entiteit:
            programma = programma_van(_text(self.hass, programma_entiteit), tabel)
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
                                          "gevraagd": None, "eind": None, "eind_gezien": None}
            sessie = self._programma[device_id]
        if programma is not None:
            sessie["programma"] = programma

        window = resolve_window(now, self._days(settings, device))
        apparaat = Apparaat(
            status=status, released=released, program=programma, door_open=deur_open,
            manual=handmatig, start_now=nu_starten,
        )
        decision = plan_programma(
            now, self._prices(settings), self._tariff(settings),
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
            eind is None and entities.get("remaining") and now - sessie["gestart"] < EINDTIJD_WACHT
        ):
            sessie["gemeld"].add("gestart")
            zelf = sessie.get("door_coach", False)
            dit = programma or sessie.get("programma")
            wat = f" ({dit.label})" if dit is not None else ""
            # Het apparaat zelf weet het beste wanneer hij klaar is;
            # zonder die sensor de duur uit de tabel.
            if eind is not None and eind > now:
                klaar = f", klaar rond {eind:%H:%M}"
            elif dit is not None and dit.minutes:
                klaar = f", klaar rond {(sessie['gestart'] + timedelta(minutes=dit.minutes)):%H:%M}"
            else:
                klaar = ""
            await self._async_tell(f"{naam} {'is gestart' if zelf else 'draait'}{wat}{klaar}.")
        if draait:
            self._programma_tellen(settings, sessie, now, watts)
            # Het verloop van deze beurt, voor het profiel: minuten sinds de
            # start en wat hij op dat moment trok.
            if watts is not None and sessie["gestart"] is not None:
                sessie["punten"].append(((now - sessie["gestart"]).total_seconds() / 60.0, watts))
            # Het gat van een herstart, zodra de kwartieropslag het heeft.
            gat = sessie.get("terugrekenen")
            if gat is not None and now >= (sessie.get("terugrekenen_na") or now):
                sessie["terugrekenen"] = None
                await self._async_programma_terugrekenen(settings, device, sessie, *gat)
            # Elke vijf minuten naar de opslag, en meteen als de beurt net
            # begint: zo overleeft een lopende beurt een herstart.
            bewaard = sessie.get("bewaard")
            if bewaard is None or (now - bewaard).total_seconds() >= 300:
                sessie["bewaard"] = now
                self._beurt_schrijven(self._programma_regel(device, naam, sessie, now, now, klaar=False))
        sessie["laatst"] = now

        mag = level == LEVEL_STEER or (level == LEVEL_PROPOSE and device_id in self._approved)
        if draait and eind is not None and eind > now and decision.rule == "running":
            decision = replace(decision, reason=f"Hij draait, klaar rond {eind:%H:%M}.")
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
            "start_now": nu_starten,
            # De klaar-tijd van vandaag als die voorbij is, en de dag waar het
            # schema dan naar opschuift: de kaart vraagt dan morgen of nu.
            "missed": window.missed.isoformat() if window.missed is not None and window.deadline is not None else None,
            "later": _dagnaam(window.deadline, now) if window.missed is not None and window.deadline is not None else None,
            "manual": handmatig,
            "program": programma.key if programma is not None else "",
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
                await self._async_programma_klaar(settings, device, naam, sessie, now, einde or now)
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
            for kop in ("Zet hem nu aan", "Zet hem meteen aan"):
                if reden.startswith(kop):
                    reden = reden[len(kop):]
                    break
            else:
                reden = ". " + reden
            if gevraagd is None:
                sessie["gevraagd"] = now
                await self._async_tell(f"Zet {naam} nu aan{reden}", kritiek=True)
            elif now - gevraagd >= HERINNERING and "herinnerd" not in sessie["gemeld"]:
                sessie["gemeld"].add("herinnerd")
                await self._async_tell(
                    f"{naam} staat nog steeds uit; de coach vroeg om {gevraagd:%H:%M} om hem aan te zetten"
                    + (reden if reden.startswith(":") else "."),
                    kritiek=True,
                )
            return

        # Starten, en kijken of het lukt.
        gedrukt = sessie.get("gedrukt")
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
                " De deur staat open."
                if deur_open
                else " Kijk of starten op afstand aan staat op het apparaat en of de deur dicht is."
            )
            await self._async_tell(
                f"De coach heeft {naam} om {gedrukt:%H:%M} gestart, maar hij is niet gaan "
                f"draaien.{waarom}",
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
        }

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
        return "run" if now - stil < STIL_KLAAR else "finished"

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
    def _bespaard_zin(totaal: float, zon: float) -> str:
        """Eén zin voor in het verslag: wat er bespaard is, en waardoor.

        `totaal` is de maat min het betaalde: wat dezelfde beurt gekost had
        als alles van het net was gekomen op het moment van vrijgeven of
        inpluggen. `zon` is wat de eigen zon daarvan scheelde; de rest is het
        wachten op een goedkoper moment. De eigenaar op 09-09-2026: "ik wil het
        totaal plaatje."
        """
        wachten = totaal - zon
        if zon < 0.005:
            return f"Bespaard {_euro(totaal)} door te wachten."
        if wachten < -0.005:
            return (
                f"Bespaard {_euro(totaal)}: de zon scheelde {_euro(zon)}, "
                f"het wachten kostte {_euro(-wachten)}."
            )
        if wachten < 0.005:
            return f"Bespaard {_euro(totaal)}, allemaal door de zon."
        return (
            f"Bespaard {_euro(totaal)}: {_euro(zon)} door de zon en "
            f"{_euro(wachten)} door te wachten."
        )

    async def _async_programma_klaar(
        self,
        settings: dict[str, Any],
        device: dict[str, Any],
        naam: str,
        sessie: dict[str, Any],
        now: datetime,
        einde: datetime | None = None,
        meten: bool = True,
    ) -> None:
        """Het verslag, de beurt in de opslag, de meting bewaren, en de vrijgave eraf.

        `meten` uit als het einde niet echt gezien is (afgelopen terwijl de
        coach weg was): een te korte duur hoort niet in de tabel.
        """
        programma = sessie.get("programma")
        gestart: datetime = sessie["gestart"]
        einde = einde or now
        kwh = sessie["kwh"]
        betaald = sessie["betaald"]
        maat = None if sessie["maat_onbekend"] or sessie["vrijgegeven"] is None else sessie["maat"]
        wat = f" ({programma.label})" if programma is not None else ""
        geld = f", ongeveer {_euro(betaald)}" if kwh > 0 else ""
        bespaard = ""
        if maat is not None and kwh > 0 and maat - betaald >= 0.005:
            bespaard = " " + self._bespaard_zin(maat - betaald, sessie.get("zon_winst") or 0.0)
        await self._async_tell(
            f"{naam} is klaar{wat}: gedraaid van {gestart:%H:%M} tot {einde:%H:%M}"
            + (f", {kwh:.1f} kWh".replace(".", ",") if kwh > 0 else "")
            + geld + "." + bespaard
        )
        # Wat er gemeten is gaat in de instellingen, zodat de volgende beurt
        # met de echte duur, het echte verbruik en het verloop rekent.
        if meten:
            await self._async_meting_bewaren(settings, device, programma, sessie, gestart, einde)
        self._beurt_schrijven(self._programma_regel(device, naam, sessie, now, einde, klaar=True))
        # De vrijgave eraf, en de schakelaar mee: de volgende lading vraagt om
        # een nieuwe.
        await self._async_vrijgave_zetten(settings, device.get("id", ""), False)
        await self._async_schakelen(device, False)
        await self._async_schakelen(device, False, "release_now_switch")
        self._programma[device.get("id", "")] = {**self._lege_programma_sessie(now), "gezien": True}

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
        if entities.get("release_switch"):
            for moment, toestand in await self._async_geschiedenis(
                entities["release_switch"], gestart - timedelta(days=3), gestart
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
            signed = sources.get("grid_mode") == "signed"
            netten = [sources.get("grid_signed")] if signed else [sources.get("grid_export"), sources.get("grid_import")]
            netten = [e for e in netten if e]
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
        per_start = {e: {int(r["start"]): r for r in rijen.get(e) or []} for e in netten}

        def netto_op(start: int) -> float | None:
            if signed and netten:
                r = per_start.get(netten[0], {}).get(start)
                if r is None:
                    return None
                s = float(r.get("gemiddeld") or 0.0)
                return -(-s if sources.get("grid_signed_invert") else s)
            if len(netten) == 2:
                re_ = per_start[netten[0]].get(start)
                ri = per_start[netten[1]].get(start)
                if re_ is None or ri is None:
                    return None
                return float(re_.get("gemiddeld") or 0.0) - float(ri.get("gemiddeld") or 0.0)
            return None

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
        tarief = self._tariff(settings)
        if contract.get("type") != "dynamic":
            return lambda moment: (tarief.buy, tarief.feed_in)
        bron = dynamic.get("all_in_entity") if dynamic.get("source") == "all_in" else dynamic.get("market_entity")
        prijzen: list[tuple[datetime, float]] = []
        for moment, toestand in await self._async_geschiedenis(bron, van - timedelta(hours=1), tot):
            try:
                prijzen.append((moment, float(toestand)))
            except ValueError:
                continue
        if not prijzen:
            return None
        if dynamic.get("source") != "all_in":
            prijzen = [(m, self._all_in(p, dynamic)) for m, p in prijzen]
        markt: list[tuple[datetime, float]] = []
        if not self._salderen(contract) and dynamic.get("market_entity"):
            for moment, toestand in await self._async_geschiedenis(
                dynamic.get("market_entity"), van - timedelta(hours=1), tot
            ):
                try:
                    markt.append((moment, float(toestand)))
                except ValueError:
                    continue
        kosten = float(dynamic.get("feed_in_costs") or 0)
        opslag = float(dynamic.get("supplier_markup") or 0) * (1 + float(dynamic.get("vat_percent") or 0) / 100)
        salderen = self._salderen(contract)

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
                return koop, koop - opslag - kosten
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

    async def _async_schakelen(self, device: dict[str, Any], aan: bool, sleutel: str = "release_switch") -> None:
        """De vrijgaveschakelaar (of die van nu starten) aan of uit zetten, als er een is en hij anders staat."""
        entity_id = (device.get("entities") or {}).get(sleutel)
        if not entity_id:
            return
        stand = _text(self.hass, entity_id).strip().lower()
        if stand == ("on" if aan else "off"):
            return
        domein = entity_id.split(".")[0]
        try:
            await self.hass.services.async_call(
                domein, "turn_on" if aan else "turn_off", {"entity_id": entity_id}, blocking=True
            )
        except Exception:  # noqa: BLE001 - een schakelaar die blijft staan is geen reden om te stoppen
            _LOGGER.exception("kon de vrijgaveschakelaar %s niet zetten", entity_id)

    async def _async_schakelaar_volgen(
        self, settings: dict[str, Any], device: dict[str, Any], sessie: dict[str, Any], released: bool
    ) -> bool:
        """De vrijgaveschakelaar en de knop op de kaart gelijk houden; geeft de vrijgave van nu.

        Wie het laatst bewoog wint. Bij de eerste ronde (of na een herstart)
        wint een schakelaar die aan staat, want dan heeft de bewoner hem
        aangezet terwijl de coach niet keek.
        """
        entity_id = (device.get("entities") or {}).get("release_switch")
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
        entity_id = (device.get("entities") or {}).get("release_now_switch")
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
        minuten = (einde - gestart).total_seconds() / 60.0
        # Alleen wat er tot het einde gemeten is: zonder statussensor kijkt
        # de coach nog een kwartier of hij echt stil blijft, en die stille
        # minuten horen niet in het profiel.
        punten = [(m, w) for m, w in (sessie.get("punten") or []) if m <= minuten + 0.5]
        if minuten < 5 or sessie["kwh"] <= 0.02 or not punten:
            return
        device_id = device.get("id", "")
        nieuw = {
            "minutes": int(round(minuten)),
            "kwh": round(sessie["kwh"], 3),
            "peak_w": int(round(max(w for _, w in punten))),
            "profile": list(profiel_van(punten)),
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
        naam = device.get("name") or "De vaatwasser"
        if st.get("rule") == "running":
            kop = "draait"
        elif st.get("charge"):
            kop = "zet hem aan" if st.get("manual") else "start nu"
        else:
            kop = "wacht"
        if not st.get("applied") and st.get("charge") and st.get("rule") != "running":
            kop = "zou nu starten, maar de coach stuurt nu niet"
        reden = (st.get("reason") or "").strip()
        await self._async_noteer(f"{naam}: {kop}. {reden}".strip(), now)

    @staticmethod
    def _priority(settings: dict[str, Any], device: dict[str, Any]) -> int:
        """Wie er voorgaat als er te weinig ruimte is voor allebei."""
        rang = {"high": 0, "mid": 1, "low": 2}
        for entry in (settings.get("strategy") or {}).get("schedules") or []:
            if isinstance(entry, dict) and entry.get("device") == device.get("id"):
                return rang.get(entry.get("priority", "mid"), 1)
        return 1

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
        naam = device.get("name") or "De boiler"
        schakelaar = entities.get("switch")
        sessie = self._boiler.setdefault(device_id, self._lege_boiler_sessie(now))
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
        surplus = None if gemeten is None else gemeten + eigen
        decision = plan_boiler(
            now, self._prices(settings), self._tariff(settings),
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
        await self._async_boiler_zetten(device, True)
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
            vanaf = f" vanaf {sessie['gestart']:%H:%M}" if sessie.get("gestart") else ""
            erin_tekst = f"{erin:.1f} kWh".replace(".", ",")
            await self._async_tell(
                f"{naam} is weer warm: {erin_tekst}{vanaf}.", telefoon=False
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
                    f"De coach zet {naam} wel aan, maar er loopt geen stroom: "
                    f"{sessie['vergeefs']} keer achter elkaar vroeg hij niets terwijl er warm water "
                    "bij moest. Kijk of de stekker en de schakelaar doen wat ze horen te doen.",
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
        if sessie is not None and sessie.get("stuurt"):
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
        self, settings: dict[str, Any], device: dict[str, Any], batterij_w: float | None
    ) -> float | None:
        """Hoeveel de zekering deze batterij nog aan laadvermogen toestaat.

        Een batterij hangt meestal op één fase, en 3,5 kW is daar vijftien
        ampère. Laadt de auto tegelijk op drie fasen, dan zit die fase zo vol.
        Zonder fasesensoren bewaakt de coach dit niet: None.
        """
        sources = settings.get("sources") or {}
        installation = settings.get("installation") or {}
        fase = (device.get("battery") or {}).get("phase") or ""

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
        if sources.get("phases_enabled"):
            zekering = float(installation.get("fuse_amps") or 25)
            marge = BALANCER_MARGIN_AMPS if installation.get("load_balancer") else FUSE_MARGIN_AMPS
            stromen = stromen_uit(sources.get("phases") or {}, True)
            if stromen:
                ruimten.append(zekering - max(marge, zekering * FUSE_MARGIN_SHARE) - max(stromen))
        # En elke groep waar de batterij aan hangt, met haar eigen zekering en
        # meter. Op een eenfasige groep is er maar één meting en telt die.
        for groep in self._groepen_keten(settings, device):
            zekering = float(groep.get("fuse_amps") or 16)
            stromen = stromen_uit(groep.get("sensors") or {}, int(groep.get("phases") or 3) == 3)
            if stromen:
                ruimten.append(zekering - max(FUSE_MARGIN_AMPS, zekering * FUSE_MARGIN_SHARE) - max(stromen))
        if not ruimten:
            return None
        return min(ruimten) * VOLTS + max(0.0, batterij_w or 0.0)

    @staticmethod
    def _groepen_keten(settings: dict[str, Any], device: dict[str, Any]) -> list[dict[str, Any]]:
        """De groepen waar dit apparaat aan hangt, van onder naar boven.

        Een apparaat wijst naar één groep (`circuit`), en een groep naar de
        groep erboven (`parent`). De hoofdaansluiting staat er niet in: die is
        er altijd. Een kring of een groep die niet bestaat eindigt de keten.
        """
        groepen = {
            g.get("id"): g
            for g in ((settings.get("installation") or {}).get("circuits") or [])
            if isinstance(g, dict) and g.get("id")
        }
        keten: list[dict[str, Any]] = []
        volgende = device.get("circuit") or ""
        while volgende and volgende in groepen and len(keten) < 12:
            groep = groepen[volgende]
            if any(g is groep for g in keten):
                break
            keten.append(groep)
            volgende = groep.get("parent") or ""
        return keten

    def _groep_sleutels(self, settings: dict[str, Any], device: dict[str, Any]) -> list[str]:
        """Onder welke zekeringen een toezegging aan dit apparaat meetelt."""
        return [""] + [str(g.get("id")) for g in self._groepen_keten(settings, device)]

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

    async def _async_batterij_bewaren(
        self, settings: dict[str, Any], device_id: str, nieuw: dict[str, Any]
    ) -> None:
        """Wat de coach van deze batterij bijhoudt naar de instellingen."""
        rij = {**self._batterij_rij(settings, device_id), **nieuw}
        dagen = rij.get("earned_days") or {}
        if len(dagen) > BATTERIJ_DAGEN_MAX:
            rij["earned_days"] = dict(sorted(dagen.items())[-BATTERIJ_DAGEN_MAX:])
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
        gemeten = rendement_uit_tellers(
            _kwh(self.hass, entities.get("energy_in")),
            _kwh(self.hass, entities.get("energy_out")),
            capaciteit,
        )
        ingevuld = getal("rte_percent")
        bewaard = rij.get("rte")
        rte = gemeten or (float(bewaard) if bewaard else None) or (ingevuld / 100.0 if ingevuld else None)

        laatst_vol = _tijdstip(rij.get("full_at"))
        return Batterij(
            soc=_number(self.hass, entities.get("soc")),
            capacity_kwh=capaciteit,
            max_charge_w=getal("max_charge_w") or uit_knop("max_charge_power", "max") or 0.0,
            max_discharge_w=getal("max_discharge_w") or uit_knop("max_discharge_power", "max") or 0.0,
            soc_min=_number(self.hass, entities.get("discharge_limit")) or 0.0,
            soc_max=_number(self.hass, entities.get("charge_limit")) or 100.0,
            reserve=float(eigen.get("reserve_percent") or 0) if eigen.get("reserve_enabled") else None,
            rte=rte,
            handelen=bool(eigen.get("trade")),
            power_w=self._batterij_w(device),
            vol_voor=vol_voor(
                now, bool(eigen.get("weekly_full")), eigen.get("weekly_full_day"),
                laatst_vol.replace(tzinfo=None) if laatst_vol is not None else None,
            ),
        )

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
        return False

    async def _one_batterij(
        self, now: datetime, settings: dict[str, Any], device: dict[str, Any], level: str
    ) -> None:
        device_id = device.get("id", "")
        naam = device.get("name") or "De batterij"
        rij = self._batterij_rij(settings, device_id)
        sessie = self._batterij.setdefault(device_id, {"regelaar": Regelaar()})
        b = self._batterij_van(now, settings, device, rij)
        entities = device.get("entities") or {}
        mag = level == LEVEL_STEER or (level == LEVEL_PROPOSE and device_id in self._approved)
        stuurt = mag and level not in (LEVEL_READ, LEVEL_ADVISE) and bool(entities.get("setpoint"))

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
        if grens_terug is None and b.vol_voor is not None and stuurt and not vol_nu:
            if await self._async_laadgrens_omhoog(settings, device, b.soc_max):
                b.soc_max = 100.0
                rij = self._batterij_rij(settings, device_id)
        elif grens_terug is not None and (vol_nu or b.vol_voor is None or not stuurt):
            await self._async_laadgrens_terug(settings, device)
            rij = self._batterij_rij(settings, device_id)

        prijzen = self._prices(settings)
        tarief = self._tariff(settings)
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
            )
        )

        # Het gemeten rendement en de laatste volle stand bewaren, zodat ze een
        # herstart overleven en de kaart ze kan tonen.
        nieuw: dict[str, Any] = {}
        if b.rte is not None and abs(float(rij.get("rte") or 0.0) - b.rte) > 0.002:
            nieuw["rte"] = round(b.rte, 4)
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
            sessie["bewaard_op"] = now
        if nieuw:
            await self._async_batterij_bewaren(settings, device_id, nieuw)
            rij = self._batterij_rij(settings, device_id)

        nu_rij = price_now(prijzen, now)
        koop = nu_rij["price"] if nu_rij else tarief.buy
        terug = nu_rij.get("feed_in") if nu_rij else tarief.feed_in
        sessie.update(besluit=besluit, batterij=b, koop=koop, terug=terug,
                      settings=settings, device=device)

        totaal = float(rij.get("earned_total") or 0.0) + sum((sessie.get("geld") or {}).values())
        eigen = device.get("battery") or {}
        try:
            aankoop = float(eigen.get("purchase_price")) if eigen.get("purchase_price") not in (None, "") else None
        except (TypeError, ValueError):
            aankoop = None
        terug_verdiend = terugverdiend(dict(rij.get("earned_days") or {}), aankoop, now)
        terug_verdiend["earned"] = round(totaal, 2)

        self.state[device_id] = {
            "charge": besluit.stand in (NETLADEN, MAX_LADEN),
            "amps": 0,
            "reason": besluit.reason,
            "plan": besluit.plan,
            # Wat er morgenvroeg naar verwachting over is of tekortkomt, zodat de
            # kaart de conclusie groen of oranje kan maken.
            "balance_kwh": None if (bal := balans_kwh(now, verwachting, b)) is None else round(bal, 2),
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
            "setpoint_w": round(sessie["regelaar"].opdracht_w) if stuurt else None,
            "target_w": round(besluit.power_w),
            "value": None if besluit.waarde is None else round(besluit.waarde, 4),
            "rte": None if b.rte is None else round(b.rte, 3),
            "capacity_kwh": b.capacity_kwh,
            "floor": b.bodem,
            "ceiling": b.soc_max,
            "full_before": b.vol_voor.isoformat() if b.vol_voor else None,
            "payback": terug_verdiend,
            "hours": [
                {
                    "start": uur.start.isoformat(), "end": uur.end.isoformat(), "mode": uur.stand,
                    "kwh": round(uur.kwh, 2), "grid_kwh": round(uur.net_kwh, 2),
                    "soc": round(uur.soc), "price": uur.price,
                }
                for uur in besluit.uren[:48]
            ],
            "tip": "",
        }

        kern = (besluit.stand, besluit.rule, stuurt)
        if self._besluit_genoteerd.get(device_id) != kern:
            self._besluit_genoteerd[device_id] = kern
            kop = STAND_NAMEN.get(besluit.stand, besluit.stand).lower()
            if not stuurt:
                kop = f"zou op {kop} staan, maar de coach stuurt nu niet"
            await self._async_noteer(f"{naam}: {kop}. {besluit.reason}".strip(), now)

        if stuurt and not sessie.get("stuurt"):
            await self._async_batterij_modus(device, "control_mode")
            sessie["stuurt"] = True
        elif not stuurt and sessie.get("stuurt"):
            await self._async_batterij_loslaten(device)
        if stuurt:
            await self._async_regel(device_id, settings, device)

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

            # Het kasboek: wat de batterij sinds de vorige stap opleverde.
            vorige = sessie.get("geteld_op")
            sessie["geteld_op"] = nu
            if vorige is not None and net_w is not None:
                seconden = min(60.0, max(0.0, (nu - vorige).total_seconds()))
                euro = verdiend(net_w, regelaar.vermogen_w(batterij_w),
                                sessie.get("koop"), sessie.get("terug"), seconden)
                if euro is not None:
                    dag = nu.date().isoformat()
                    geld = sessie.setdefault("geld", {})
                    geld[dag] = geld.get(dag, 0.0) + euro

            opdracht = regelaar.stap(
                nu, net_w=net_w, net_op=net_op, batterij_w=batterij_w,
                besluit=sessie["besluit"], b=b,
                doel_w=regelaar.doel_w(sessie.get("koop"), sessie.get("terug")),
                ruimte_w=self._laadruimte_w(settings, device, batterij_w),
            )
            if opdracht is not None:
                await self._async_batterij_zetten(device, opdracht)
        except ServiceNotFound:
            _LOGGER.warning("%s kan nog niet aangestuurd worden (nog niet geladen?)", device_id)
        except Exception:  # noqa: BLE001 - de regelaar mag nooit stilvallen op één fout
            _LOGGER.exception("de regelaar van %s struikelde", device_id)
        finally:
            sessie["bezig"] = False

    async def _async_regel_tik(self, _now: datetime | None = None) -> None:
        """De regelaar van elke gestuurde batterij één stap laten doen."""
        # Met de instellingen van de laatste ronde, en niet opnieuw uit de
        # opslag: een meter die per seconde meldt zou anders elke seconde een
        # kopie van alle instellingen maken. Wat er verandert (het vinkje eraf,
        # een andere sensor) pakt de ronde binnen een minuut op.
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

    async def _async_batterij_zetten(self, device: dict[str, Any], watt: float) -> None:
        """Een vermogen naar de batterij, laden positief.

        Met een richting-entiteit ernaast gaat het getal er zonder teken in;
        zonder is het teken de richting. Eerst de richting en dan het getal, en
        de richting alleen als hij verandert.
        """
        entities = device.get("entities") or {}
        knop, richting = entities.get("setpoint"), entities.get("direction")
        if not knop:
            return
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
        await self.hass.services.async_call(
            "number", "set_value", {"entity_id": knop, "value": round(waarde)}, blocking=True
        )

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

    async def _async_batterij_loslaten(self, device: dict[str, Any]) -> None:
        """De batterij teruggeven: vermogen op nul, en zijn eigen stand terug.

        Dezelfde gedachte als de stroom terug op de boiler: een batterij die op
        zijn laatste opdracht blijft staan loopt leeg naar het net of trekt vol
        van het net tot iemand het ziet.
        """
        sessie = self._batterij.get(device.get("id", ""))
        if sessie is not None:
            sessie["stuurt"] = False
            sessie["regelaar"] = Regelaar()
            if sessie.get("settings") is not None:
                await self._async_laadgrens_terug(sessie["settings"], device)
        await self._async_batterij_zetten(device, 0.0)
        await self._async_batterij_modus(device, "idle_mode")

    async def _async_batterijen_los(self) -> None:
        """Bij het stoppen van de coach: elke batterij die hij stuurde teruggeven."""
        try:
            settings = await async_get_store(self.hass).async_load()
        except Exception:  # noqa: BLE001 - afsluiten mag hier niet op stuklopen
            return
        for device in settings.get("devices") or []:
            if device.get("type") != "thuisbatterij":
                continue
            if not (self._batterij.get(device.get("id", "")) or {}).get("stuurt"):
                continue
            try:
                await self._async_batterij_loslaten(device)
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
        decision = decide(
            now, self._prices(settings), grid, car, charger, window,
            self._tariff(settings), self._sun(settings),
            Forecast(
                solar_kwh=self._zon_kwh,
                house_kwh=self._huis_kwh,
                estimated=self._zon_geschat,
                solar_factor=self._zon_gemeten(now),
                solar_day=now.date(),
            ),
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
        self._tempo_leren(now, settings, device, car, charger, grid)

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
            "plan_ahead": self._tijdlijn(now, settings, grid, car, charger, window),
            # Of er een knop "accustand opvragen" op de kaart hoort, en wanneer
            # de auto voor het laatst gewekt is.
            "wake": self._wekbaar(settings, device),
            "woke_at": self._gewekt[device_id].isoformat() if device_id in self._gewekt else None,
        }
        # Iets dat alleen de bewoner zelf kan verhelpen, en dat losstaat van
        # het besluit van deze ronde. Het gaat dus naast de reden op de kaart
        # en niet erin.
        tip = (
            self._nettip(now)
            or self._fasetip(settings, device, charger)
            or self._bewakertip(settings, device, charger)
        )
        self.state[device_id]["tip"] = tip

        may_act = level == LEVEL_STEER or (
            level == LEVEL_PROPOSE and device_id in self._approved
        )
        # Eerst opruimen, dan pas opschrijven wat de stand is. Andersom bleef er
        # op de kaart nog een minuut "snelladen staat aan" staan nadat de kabel
        # er al uit was, en dat leest als een knop die blijft hangen.
        #
        # Een akkoord duurt zolang de auto aan de kabel hangt, en snelladen ook:
        # de auto waarvoor het bedoeld was staat er dan niet meer.
        if not charger.connected:
            self._approved.discard(device_id)
            self._boost.discard(device_id)
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
            self._tempo_gezien.pop(device_id, None)
            self._tempo_soc.pop(device_id, None)
            self._limiet_vorig.pop(device_id, None)
            self._limiet_omhoog.pop(device_id, None)
            self._weerleg_vorig.pop(device_id, None)
            self._soc_asked.discard(device_id)
            self._warned.pop(device_id, None)
            self._getipt.discard(device_id)
            # Wat er over deze sessie bewaard is gaat mee weg. Een opgegeven
            # accustand hoort bij de auto die eraan hing: blijft die staan, dan
            # rekent de coach morgen met het percentage van gisteren terwijl er
            # honderd kilometer tussen zit, en dat is de gevaarlijke kant op.
            # Voor de knoppen geldt hetzelfde: wie de kabel eruit trekt, heeft
            # niets meer goedgekeurd of gepauzeerd.
            await self._async_forget(settings, device_id)

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

        if not may_act:
            return 0.0

        await self._async_verslag(now, device, car, charger, window, decision)

        if decision.needs_soc:
            await self._async_ask_soc(device, decision)

        if tip and device_id not in self._getipt:
            self._getipt.add(device_id)
            await self._async_tell(
                f"{device.get('name') or 'De laadpaal'}: {tip}", kritiek=True
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
                f"De pauze op {device.get('name') or 'de laadpaal'} staat nog aan, en zo "
                "is de auto niet op tijd vol. Hervat het laden of verzet je klaar-tijd.",
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
            if not should_send(self._last.get(device_id), decision) and not (
                self._pause_expiring(device_id, now)
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

    def _slots(self, entity_id: str | None, interval: str = "hour") -> dict[datetime, tuple[datetime, float]]:
        """De blokken uit een prijsentiteit, op begintijd.

        Een blok zonder eindtijd loopt tot het volgende blok; het laatste blok
        is even lang als het blok ervoor, en zonder blok ervoor zo lang als
        het contract zegt. Dezelfde regel als `priceForecast` in data-source.js.
        """
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            return {}

        rijen = sorted(_prijsrijen(state.attributes), key=lambda r: r[0])
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
            uit[dt_util.as_local(start).replace(tzinfo=None)] = (
                dt_util.as_local(end).replace(tzinfo=None),
                price,
            )
        return uit

    @staticmethod
    def _salderen(contract: dict[str, Any], now: datetime | None = None) -> bool:
        """Of er op dit moment nog gesaldeerd wordt.

        Het vinkje van de klant én de datum. De regeling loopt af op
        `NETTING_ENDS`, en zonder die grens zou de coach na de jaarwisseling
        maandenlang een belastingteruggave blijven inrekenen die niet meer
        bestaat. Het vinkje blijft staan; het telt alleen niet meer mee.
        """
        if not contract.get("netting"):
            return False
        vandaag = dt_util.as_local(now or dt_util.utcnow()).date()
        return vandaag < NETTING_ENDS

    def _prices(self, settings: dict[str, Any]) -> list[dict]:
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
        if contract.get("type") != "dynamic":
            return []

        dynamic = contract.get("dynamic") or {}
        all_in = dynamic.get("source") == "all_in"
        kosten = float(dynamic.get("feed_in_costs") or 0)
        salderen = self._salderen(contract)
        # De opslag van de leverancier zit wel in wat je betaalt en niet in wat
        # je terugkrijgt. Bij salderen streept de energiebelasting weg tegen die
        # bij afname, maar die opslag niet: die betaal je per ingekochte kWh en
        # krijg je nergens terug. Zonder deze aftrek stond de terugleveropbrengst
        # er ruim twee cent te hoog in en leek eigen zon gebruiken even duur als
        # het weggeven ervan. Gevonden op 27-08-2026, uit een eigen energienota.
        opslag = float(dynamic.get("supplier_markup") or 0) * (
            1 + float(dynamic.get("vat_percent") or 0) / 100
        )

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
        for start, (end, prijs) in inkoop.items():
            terug = None
            if not all_in:
                prijs = self._all_in(prijs, dynamic)

            if salderen:
                # Salderen betekent dat een teruggeleverde kWh wegstreept tegen
                # een ingekochte. Wat je daarmee bespaart is de inkoopprijs min
                # de opslag van je leverancier, want die opslag hangt aan de
                # afname en niet aan de kWh. Er is geen marktprijssensor voor
                # nodig: het antwoord staat al in de prijs die er is.
                terug = prijs - opslag - kosten
            elif all_in:
                if start in markt:
                    terug = markt[start][1] - kosten
            else:
                terug = markt[start][1] - kosten if start in markt else None

            rows.append({"start": start, "end": end, "price": prijs, "feed_in": terug})
        # Verder dan de lijst reikt weet de coach niets, en dat hoort zo.
        # Er stond hier op 04-09-2026 een middag lang een geschatte dag
        # achteraan (de prijzen van vandaag nog eens voor morgen); de eigenaar wil
        # geen gegokte prijzen. Reikt de lijst niet tot de klaar-tijd, dan
        # laadt hij tot die tijd alleen op zon. Zie `alleen_zon` in planner.py.
        return sorted(rows, key=lambda item: item["start"])

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
        erin = bronnen.get("grid_import")
        eruit = bronnen.get("grid_export")
        getekend = bronnen.get("grid_signed")
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
        wanted = [e for e in [*zonnen_ids, erin, eruit, getekend, *apparaten] if e]
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
        binnen, buiten, getekende = (
            kwartieren(erin),
            kwartieren(eruit),
            kwartieren(getekend),
        )
        apparaat = [(kwartieren(naam), teken) for naam, teken in tekens]

        # Een meter met een teken meet één getal, en of plus inkoop of
        # teruglevering betekent verschilt per merk. Dat vinkje staat al bij
        # Instellingen en wordt overal elders gelezen; hier stond het niet, en
        # dan zou een woning met een omgekeerde meter een huisverbruik krijgen
        # met het verkeerde teken. Zie ook `_read` en `monitor.py`.
        omgekeerd = bool(bronnen.get("grid_signed_invert"))

        per_uur: dict[int, list[float]] = {}
        for stempel in sorted(set(zonnen) | set(binnen) | set(getekende)):
            if getekende:
                net = getekende.get(stempel, 0.0)
                if omgekeerd:
                    net = -net
            else:
                net = binnen.get(stempel, 0.0) - buiten.get(stempel, 0.0)
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

        Twee bronnen, en de eerste die iets oplevert wint.

        **De voorspelling van het energiedashboard.** Elke zonvoorspeller die
        aan het energiedashboard hangt levert daar een uurkromme, en Home
        Assistant ontsluit ze allemaal op dezelfde manier. Dat is dus geen
        Forecast.Solar-truc: Solcast doet het net zo. Nagemeten in de klantwoning
        op 30-08-2026: veertien uur vooruit, per uur, in wattuur.

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
        if kromme:
            self._zon_kwh, self._zon_geschat = kromme, False
            return

        self._zon_kwh, self._zon_geschat = self._zon_uit_sensoren(settings, now), True

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
            from homeassistant.loader import async_get_integration

            manager = await async_get_manager(self.hass)
            uit: dict[datetime, float] = {}
            for bron in (manager.data or {}).get("energy_sources") or []:
                if bron.get("type") != "solar":
                    continue
                for entry_id in bron.get("config_entry_solar_forecast") or []:
                    entry = self.hass.config_entries.async_get_entry(entry_id)
                    if entry is None:
                        continue
                    integratie = await async_get_integration(self.hass, entry.domain)
                    platform = await integratie.async_get_platform("energy")
                    voorspeld = await platform.async_get_solar_forecast(self.hass, entry_id)
                    for stempel, wh in ((voorspeld or {}).get("wh_hours") or {}).items():
                        moment = dt_util.parse_datetime(str(stempel))
                        if moment is None:
                            continue
                        uur = _moment(moment).replace(minute=0, second=0, microsecond=0)
                        uit[uur] = uit.get(uur, 0.0) + float(wh) / 1000.0
            return uit
        except Exception:  # noqa: BLE001 - een voorspelling is nuttig, niet noodzakelijk
            _LOGGER.debug("geen uurkromme uit het energiedashboard", exc_info=True)
            return {}

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
    def _tariff(settings: dict[str, Any]) -> Tariff:
        """Wat een kWh kost en opbrengt als de prijslijst niets zegt.

        Bij een vast contract staat het hele jaar hetzelfde getal, dus is er geen
        lijst en is dit alles wat de coach heeft. Juist daar telt het zwaar: het
        verschil tussen inkopen en terugleveren is bij een vast contract de enige
        reden die er is om het ene moment boven het andere te verkiezen.
        """
        contract = settings.get("contract") or {}
        if contract.get("type") == "dynamic":
            return Tariff()

        fixed = contract.get("fixed") or {}
        prijs = fixed.get("all_in_price")
        koop = float(prijs) if prijs is not None else None
        kosten = float(fixed.get("feed_in_costs") or 0)

        if ChargerCoach._salderen(contract):
            # Salderen: wat je teruglevert streept weg tegen wat je inkoopt, dus
            # is het de inkoopprijs waard. Het ingevulde terugleverbedrag geldt
            # dan niet; dat is pas aan de orde boven wat je zelf verbruikt.
            terug = None if koop is None else koop - kosten
        else:
            terug = float(fixed.get("feed_in_tariff") or 0) - kosten

        return Tariff(buy=koop, feed_in=terug)

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

        # Wat een thuisbatterij opneemt hoort bij het overschot: de auto laadt
        # op zon zonder verlies en de batterij niet, dus de auto gaat voor. En
        # wat de batterij afgeeft is geen zon. Zie `_batterijen_w`.
        if netto is not None:
            netto += self._batterijen_w(settings)

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

        phases = []
        for key in ("l1", "l2", "l3"):
            amps = self._fase_amps((sources.get("phases") or {}).get(key) or {}, now)
            if amps is not None:
                phases.append(amps)

        # De groepen waar deze paal aan hangt, elk met de eigen meter en de
        # eigen zekering. Zie `Circuit` in planner.py.
        reserved = reserved or {}
        circuits = []
        for groep in self._groepen_keten(settings, device):
            stromen = []
            for key in ("l1", "l2", "l3"):
                amps = self._fase_amps((groep.get("sensors") or {}).get(key) or {}, now)
                if amps is not None:
                    stromen.append(amps)
            circuits.append(Circuit(
                name=str(groep.get("name") or groep.get("id") or ""),
                phase_amps=stromen,
                fuse_amps=float(groep.get("fuse_amps") or 16),
                reserved_amps=float(reserved.get(str(groep.get("id")), 0.0)),
            ))

        # Wat deze paal kort geleden nog trok. De fasemeting van het huis loopt
        # achter op de paal, dus vlak na het stoppen draagt zij zijn stroom nog
        # terwijl hij zelf al op nul staat. Zonder dit geheugen wordt dat aan het
        # huis toegerekend en meldt de coach dat de aansluiting vol zit terwijl er
        # niets loopt. Zie `meter_loopt_achter` in planner.py.
        recent = self._laatste_stroom.get(device_id)
        if charger_amps > STEP_AMPS:
            self._laatste_stroom[device_id] = (charger_amps, now)
            recent_amps = charger_amps
        elif recent is not None and now - recent[1] <= METER_NAIJL:
            recent_amps = recent[0]
        else:
            self._laatste_stroom.pop(device_id, None)
            recent_amps = 0.0

        grid = Grid(
            recent_charger_amps=recent_amps,
            surplus_w=surplus,
            # Wat een eerder laadpunt in deze ronde al toegezegd heeft gekregen
            # en nog niet in de fasemeting staat.
            reserved_amps=float(reserved.get("", 0.0)),
            circuits=circuits,
            phase_amps=phases,
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
        gemeld = _text(self.hass, entities.get("status"))
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
            paused_by_user=device.get("id", "") in self._paused,
            paused_by_balancer="equalizer" in status or "load_balancing" in status,
            no_current_reason=_text(self.hass, entities.get("no_current_reason")),
            # Wat er op de paal staat, zodat de klaar-tijdsom kan zien of de
            # coach zelf de rem is. Zie `throttled_by_coach` in planner.py.
            limit_amps=_number(self.hass, entities.get("dynamic_limit")),
            circuit_amps=_number(self.hass, entities.get("circuit_limit")),
        )
        # Wat er de afgelopen uren gemiddeld overbleef voor deze paal, uit de
        # boekhouding van de beurt (`_bijhouden`). Een meting van deze beurt,
        # niet van gisteren: na de kabel eruit begint hij op nul, en na een
        # herstart ook, want de beurt zelf wordt niet bewaard.
        if charger.connected:
            charger.expected_amps = self._plafond_gemeten(device_id, now)

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
            self._since[device_id] = now
            charger.started_at = now
        elif charger.charging and charger.started_at is None:
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
        else:
            self._herstart_open.discard(device_id)

        # --- when it may run ---
        window = resolve_window(now, self._days(settings, device))

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
                )
            return uit

        return {}

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

        if chosen == "__guest__":
            return Car(guest=True, phases=3, name="Gast")

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
        phases_measured = phases == 3 and gemeten == 1 and charger.charging
        if phases_measured:
            phases = 1

        # De auto zelf gaat voor. Zegt hij niets, dan telt wat de bewoner heeft
        # opgegeven, bijgewerkt met wat de paal er sindsdien in heeft gedaan.
        soc = _number(self.hass, profile.get("soc_entity"))
        geschat = False
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
        if soc is None:
            soc = self._onthouden_soc(device, profile)
            geschat = soc is not None

        auto_id = str(profile.get("id") or "")
        self._auto_id[device_id] = auto_id
        return Car(
            name=str(profile.get("name") or "").strip(),
            capacity_kwh=float(profile.get("capacity_kwh") or 0),
            phases=phases,
            phases_measured=phases_measured,
            max_amps=float(profile.get("max_amps") or 0),
            target_percent=float(profile.get("target_percent") or 100),
            soc_percent=soc,
            soc_estimated=geschat,
            tempo_per_band=self._tempo_uit(settings, device_id, auto_id),
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
        reeks = (self._sessie.get(device_id) or {}).get("plafond_reeks") or []
        grens = now - PLAFOND_VENSTER
        binnen = [r for r in reeks if r[0] >= grens]
        minuten = sum(stap for _, _, stap in binnen)
        if minuten < PLAFOND_MEETTIJD_MIN:
            return None
        return sum(plafond * stap for _, plafond, stap in binnen) / minuten

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
            geladen = max(0.0, meter - float(sinds)) * CHARGE_EFFICIENCY
            percent = float(percent) + geladen / capacity * 100.0
        return min(100.0, float(percent))

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
        wat er loopt), niet de lastbewaker, niet de groep. Per band het laagste
        van deze beurt, want een auto die afbouwt doet dat bovenin de band het
        sterkst, en de eigenaar wil liever te vroeg vol dan te laat.

        Het staat per auto in de instellingen (`car_pace`) en de volgende beurt
        rekent ermee, zie `hours_needed` in planner.py. Een nieuwe beurt
        overschrijft de banden die hij zelf meet, zodat een auto die vandaag
        anders doet dan vorige maand morgen ook anders gepland wordt.
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

        # Twee ronden hetzelfde voordat het telt, zoals `_eindtijd_vast` bij de
        # vaatwasser en `_fasen_stabiel` bij de fasen. Een stroomsensor loopt
        # een ronde achter, en één zo'n ronde is hier duur: op 17-09-2026 werd
        # een tussenstand van 0,152 A het tempo van een hele band. Wat er echt
        # gebeurt houdt langer dan een minuut aan, dus dit kost niets.
        vorig = self._tempo_vorig.get(device_id)
        self._tempo_vorig[device_id] = (band, kw)
        if vorig is None or vorig[0] != band or abs(vorig[1] - kw) > TEMPO_SPELING:
            return

        gezien = self._tempo_gezien.setdefault(device_id, {})
        if band in gezien and gezien[band] <= kw:
            return
        gezien[band] = kw
        self._tempo_soc.setdefault(device_id, {})[band] = round(car.soc_percent, 1)
        self.hass.async_create_task(self._async_tempo_schrijven(settings, device_id, now))

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
        gezien = self._tempo_gezien.get(device_id) or {}
        if band in gezien:
            bekend = (gezien[band], (self._tempo_soc.get(device_id) or {}).get(band, band * 10.0))
        else:
            bekend = self._tempo_bewaard(settings, device_id, auto_id).get(band)
        kw_nu = watts_for(charger.actual_amps, car.phases) / 1000.0
        if (
            bekend is None
            or car.soc_percent < bekend[1]
            or kw_nu <= bekend[0] + TEMPO_SPELING
        ):
            self._weerleg_vorig.pop(device_id, None)
            return
        if self._weerleg_vorig.get(device_id) != band:
            self._weerleg_vorig[device_id] = band
            return
        self._weerleg_vorig.pop(device_id, None)
        gezien.pop(band, None)
        (self._tempo_soc.get(device_id) or {}).pop(band, None)
        self._tempo_vorig.pop(device_id, None)
        self.hass.async_create_task(
            self._async_tempo_wissen(settings, device_id, auto_id, band)
        )

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
        self, settings: dict[str, Any], device_id: str, now: datetime
    ) -> None:
        """De gemeten banden van deze beurt in de instellingen zetten."""
        auto_id = self._auto_id.get(device_id)
        gezien = self._tempo_gezien.get(device_id) or {}
        if not auto_id or not gezien:
            return
        rows = [
            row
            for row in (settings.get("car_pace") or [])
            if isinstance(row, dict)
            and not (
                row.get("device") == device_id
                and row.get("car") == auto_id
                and row.get("band") in gezien
            )
        ]
        socs = self._tempo_soc.get(device_id) or {}
        for band, kw in sorted(gezien.items()):
            row = {"device": device_id, "car": auto_id, "band": band, "kw": kw,
                   "at": now.isoformat()}
            if band in socs:
                row["soc"] = socs[band]
            rows.append(row)
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
        """
        uit: dict[int, float] = {}
        for row in settings.get("car_pace") or []:
            if (
                isinstance(row, dict)
                and row.get("device") == device_id
                and row.get("car") == auto_id
            ):
                try:
                    kw = float(row["kw"])
                    if kw >= TEMPO_ONDERGRENS:
                        uit[int(row["band"])] = kw
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
            if ijk is not None and 0.0 < gemeten - ijk[0] <= SOC_STAP_MAX:
                sprong = gemeten - ijk[0]
                eerder = self._soc_stap.get(device_id)
                self._soc_stap[device_id] = sprong if eerder is None else min(eerder, sprong)
            self._soc_ijk[device_id] = (gemeten, eigen)
            return gemeten
        if not capacity:
            return gemeten
        erbij = max(0.0, eigen - ijk[1]) * CHARGE_EFFICIENCY / capacity * 100.0
        return min(100.0, gemeten + min(erbij, self._soc_stap.get(device_id, SOC_STAP_START)))

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
        if meter is not None and since is not None:
            geladen = max(0.0, meter - float(since)) * CHARGE_EFFICIENCY
            percent += geladen / capacity * 100.0
        return min(100.0, percent)

    # Waar de tijd aan opging, in woorden die een bewoner herkent. Zelfstandig
    # geformuleerd, zodat er "20 minuten naar ..." voor kan staan zonder dat het
    # kromme taal wordt.
    VERTRAGING = {
        "user-hold": "de pauze die je zelf aanzette",
        "no-room": "een aansluiting die vol zat",
        "held-back": "de lastbewaking van je aansluiting",
        "balancer-paused": "de lastbewaking van je aansluiting",
        "waiting-for-car": "een auto die geen stroom afnam",
        "waiting-for-auth": "een paal die op goedkeuring wachtte",
        "no-soc": "wachten op je accustand",
        "wait-for-sun": "wachten op je eigen zon",
        "wait-for-sun-today": "wachten op je eigen zon",
        "wait-for-price": "wachten op een goedkoper uur",
        "too-early": "de tijden die je hebt ingesteld",
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
        tarief = self._tariff(settings)
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
            "name": device.get("name") or "Laadpaal",
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
            "price_unknown": ijk is None or onbekend_kwh > 0,
            "unknown_kwh": onbekend_kwh,
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
            if not self._salderen(contract) and dynamic.get("market_entity"):
                for moment, toestand in await self._async_geschiedenis(
                    dynamic.get("market_entity"), plug - timedelta(hours=1), tot
                ):
                    try:
                        markt.append((moment, float(toestand)))
                    except ValueError:
                        continue
            if not prijzen:
                return None
        tarief = self._tariff(settings)
        kosten = float(dynamic.get("feed_in_costs") or 0)
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
            if contract.get("type") != "dynamic":
                return tarief.buy, tarief.feed_in
            koop = laatste(prijzen, moment)
            if koop is None:
                return None, None
            if self._salderen(contract):
                return koop, koop - opslag - kosten
            m = laatste(markt, moment)
            return koop, (m - kosten) if m is not None else None

        # De kwartieren: de paal, en het net zoals `_read` het leest.
        sources = settings.get("sources") or {}
        paal = device.get("entity")
        if not paal:
            return None
        signed = sources.get("grid_mode") == "signed"
        netten = [sources.get("grid_signed")] if signed else [sources.get("grid_export"), sources.get("grid_import")]
        netten = [e for e in netten if e]
        rijen = await self._async_kwartieren([paal, *netten], plug - timedelta(minutes=15), tot)
        paal_rijen = rijen.get(paal) or []
        if not paal_rijen:
            return None
        per_start: dict[str, dict[int, dict[str, float]]] = {
            e: {int(r["start"]): r for r in rijen.get(e) or []} for e in netten
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
            "onbekend_kwh": 0.0,
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
            netto: float | None = None
            if signed:
                r = per_start.get(netten[0], {}).get(int(rij["start"])) if netten else None
                if r is not None:
                    s = float(r.get("gemiddeld") or 0.0)
                    netto = -(-s if sources.get("grid_signed_invert") else s)
            elif len(netten) == 2:
                re_ = per_start[netten[0]].get(int(rij["start"]))
                ri = per_start[netten[1]].get(int(rij["start"]))
                if re_ is not None and ri is not None:
                    netto = float(re_.get("gemiddeld") or 0.0) - float(ri.get("gemiddeld") or 0.0)
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
        """Home Assistant gaat uit: elke lopende beurt nu naar de opslag."""
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

    async def _async_beurten_laden(self) -> None:
        """De beurten die bij de vorige keer nog liepen, voor `_geld_begin`."""
        try:
            for entry in await async_get_beurten(self.hass).async_open():
                self._beurt_open[str(entry.get("device") or "")] = entry
        except Exception:  # noqa: BLE001 - zonder geschiedenis begint hij gewoon opnieuw
            _LOGGER.exception("kon de lopende laadbeurten niet lezen")

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
        if not charger.connected:
            # Een beurt die nog open stond in de opslag terwijl de kabel er nu
            # niet in zit: de kabel ging eruit terwijl Home Assistant herstartte.
            # Afsluiten met wat er bekend is, want anders blijft hij eeuwig lopen.
            open_beurt = self._beurt_open.pop(device_id, None)
            if open_beurt is not None:
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
            if grid is not None:
                plafond = ceiling_amps(grid, car, charger)
                if plafond < MIN_AMPS:
                    gemeten = 0.0
                elif decision.charge and decision.amps >= plafond:
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
        eigen = self._eigen.get(device.get("id", "")) or {}
        # Waar de staart begint. Zolang de teller nog niet gestapt is sinds deze
        # beurt begon is dat het begin van de beurt, want alles ervoor was van
        # een andere. Daarna is het de laatste stap.
        basis = (
            eigen.get("meter_bij", 0.0)
            if sessie.get("geijkt")
            else sessie.get("eigen_bij_begin", 0.0)
        )
        staart = max(0.0, eigen.get("kwh", 0.0) - basis)
        meter = self._teller(device)
        if meter is None or sessie.get("meter") is None:
            return staart or None
        eerder = sessie.get("ijk_kwh", 0.0) if sessie.get("geijkt") else 0.0
        return eerder + max(0.0, meter - float(sessie["meter"])) + staart

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
        return naam if naam else "de auto"

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
        stukken = [f"{int(minuten)} minuten naar {tekst}" for minuten, tekst in kwijt[:2]]
        # Is de coach midden in de laadbeurt ingestapt, dan weet hij niet hoe
        # lang de kabel er al in zat en zegt hij wat hij wél weet.
        sinds = (
            "Sinds de coach begon te kijken"
            if sessie.get("ingestapt")
            else "Sinds de kabel erin ging"
        )
        return f"{sinds} is er " + " en ".join(stukken) + " gegaan"

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
        naam = device.get("name") or "de laadpaal"

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
            minuten = int((now - sinds).total_seconds() // 60)
            stand = (
                f" Hij staat op {int(car.soc_percent)}%."
                if car.soc_percent is not None
                else ""
            )
            await self._async_tell(
                f"{self._hoe_heet(car).capitalize()} aan {naam} neemt al {minuten} "
                "minuten geen stroom af "
                f"terwijl de coach hem aanbiedt.{stand} Zo wordt "
                f"{window.deadline:%H:%M} niet gehaald. Meestal helpt het om de "
                "kabel er even uit te trekken en er weer in te doen.",
                kritiek=True,
            )

        # De coach heeft de paal zojuist opnieuw gestart omdat de auto volgens
        # zijn accustand nog niet vol was. Dat hoort de bewoner te lezen, ook
        # als het lukt: de Ford-app zei op 06-09-2026 "charging error" en dan
        # wil je weten dat er iemand iets deed.
        if device_id in self._herstart_melden:
            self._herstart_melden.discard(device_id)
            stand = f" {int(car.soc_percent)}%" if car.soc_percent is not None else ""
            # Waar hij naartoe moest, als dat niet gewoon vol is. Zonder dat
            # leest "dat is niet vol" bij een doel van 90% als een coach die de
            # instelling niet kent.
            heen = (
                "" if doel_van(car) >= FULL_PERCENT else f" en hij moet naar {int(doel_van(car))}%"
            )
            await self._async_tell(
                f"{naam} zei dat {self._hoe_heet(car)} klaar was, maar hij staat op"
                f"{stand}{heen} en dat is niet vol. De coach heeft de paal een keer "
                "opnieuw gestart. Gaat de auto niet binnen een kwartier verder, dan "
                "laat hij het daarbij.",
                kritiek=True,
            )

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
            kwh = f"{geladen:.1f} kWh".replace(".", ",") if geladen else ""
            waarom = self._waarom(sessie)
            # "Vol" is wat de paal zegt, niet altijd wat de accu doet. Stopt een
            # auto op 80% omdat daar een laadgrens in staat, dan is "de auto is
            # vol" onwaar en leest het als een coach die niet weet wat hij doet.
            # Weet hij de accustand, dan zegt hij die gewoon. De eigenaar op 20-08-2026.
            #
            # En staat die 80% als doel in het profiel, dan is er niets bijzonders
            # gebeurd en hoort er ook geen bijzonderheid te staan: dan is dit
            # gewoon het einde van een geslaagde beurt. De eigenaar op 16-09-2026.
            wie = f"{self._hoe_heet(car).capitalize()} aan {naam}"
            heel = doel_van(car) >= FULL_PERCENT
            if car.soc_percent is None or (heel and doel_bereikt(car)):
                klaar = f"{wie} is vol."
            elif doel_bereikt(car):
                klaar = f"{wie} staat op {int(car.soc_percent)}%, en verder hoefde hij niet."
            else:
                klaar = (
                    f"{wie} laadt niet verder en staat op "
                    f"{int(car.soc_percent)}%. Mogelijk staat er een laadgrens in "
                    "de auto."
                )
            # Is de coach midden in de laadbeurt ingestapt, dan weet hij niet
            # hoe laat die begon en hoort hij dat ook niet te suggereren.
            # Vandaar "sinds" en niet "van ... tot"; dat ene woord zegt het al.
            # Wat er niet meer bij staat is "en toen liep hij al". De eigenaar op
            # 21-09-2026: "ik vind dat en toen liep hij al onnodig. Alle
            # meldingen moeten gewoon duidelijk en kort zijn."
            begon = sessie["begon"]
            if sessie.get("ingestapt"):
                verloop = f" Sinds {begon:%H:%M} ging er {kwh} in." if kwh else ""
            elif kwh:
                verloop = f" Geladen van {begon:%H:%M} tot {now:%H:%M}, {kwh}."
            else:
                verloop = f" Geladen van {begon:%H:%M} tot {now:%H:%M}."
            nog = (
                f" De coach heeft de paal om {herstart:%H:%M} nog een keer opnieuw "
                "gestart, zonder gevolg."
                if herstart is not None
                else ""
            )
            await self._async_tell(
                klaar + verloop + (f" {waarom}." if waarom else "") + nog
            )
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
            f" Hij staat nu op {int(car.soc_percent)}%."
            if car.soc_percent is not None
            else ""
        )
        waarom = self._waarom(sessie)
        await self._async_tell(
            f"{self._hoe_heet(car).capitalize()} aan {naam} was om {vorig:%H:%M} "
            f"nog niet vol.{stand}"
            + (f" {waarom}." if waarom else "")
            + " Hij laadt door tot hij vol is.",
            kritiek=True,
        )

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
        kwh = f"{geladen:.1f} kWh".replace(".", ",") if geladen else ""
        begon = sessie.get("begon")

        # "Sinds" en niet "van ... tot", want is de coach midden in de beurt
        # ingestapt dan weet hij het begin niet. Die ene zin dekt allebei de
        # gevallen; de bijzin "en toen liep hij al" is eruit (de eigenaar, 21-09-2026).
        if kwh:
            verloop = f", er ging {kwh} in sinds {begon:%H:%M}."
        else:
            verloop = "."

        waarom = self._waarom(sessie)
        # Was de auto al als vol gemeld, dan is dit het tweede verslag van
        # dezelfde beurt: wel in de geschiedenis, niet nog eens op de telefoon.
        await self._async_tell(
            f"{self._hoe_heet(car).capitalize()} aan {naam} is afgekoppeld om "
            f"{moment:%H:%M}"
            + verloop
            + (f" {waarom}." if waarom else ""),
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
        naam = device.get("name") or "de laadpaal"
        merk = f"{device_id}:deadline" if decision.rule == "deadline" else device_id
        if merk in self._soc_asked:
            return
        self._soc_asked.add(merk)

        if decision.rule == "deadline":
            bericht = (
                f"De accustand van de auto aan {naam} is nog steeds niet doorgegeven, "
                "dus de coach gaat uit van een lege accu en laadt nu door om op tijd "
                "klaar te zijn."
            )
        else:
            bericht = (
                f"De coach wil de auto aan {naam} gaan laden, maar weet niet hoe vol "
                "hij is. Geef de accustand door op de laadpaalkaart, dan laadt hij op "
                "het gunstigste moment."
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
        """
        if not charger.charging:
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
            return (
                "Hij laadt op één fase, want de maximale limiet van je lader staat "
                f"op {charger.max_amps:.0f} A. Op {PHASE_START_AMPS:.0f} A of hoger "
                "begint elke laadbeurt op drie fasen, en gaat er ongeveer drie keer "
                "zoveel in per uur."
            )

        # 2. Het profiel klopt niet met wat er gemeten wordt. Dit is het vangnet
        # dat in de plaats komt van de keuze "allebei": daar werd het aantal
        # fasen gemeten in plaats van ingesteld, en de prijs daarvan was dat elke
        # voorspelling het traagste geval nam. Nu staat het vast en wordt de
        # meting gebruikt waar hij hoort: om te zeggen dat de instelling niet
        # klopt, in plaats van er stilletjes omheen te rekenen.
        if staat_op == "three" and gemeten == 1:
            return (
                "Dit profiel staat op driefasig, maar er wordt nu op één fase "
                "geladen. Laden duurt daardoor ongeveer drie keer zo lang; de coach "
                "rekent deze beurt met die ene fase. Gebeurt dit elke beurt, zet de "
                "auto dan op eenfasig bij Apparaten."
            )
        if staat_op == "one" and gemeten == 3:
            return (
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
            self._tariff(settings),
            Forecast(
                solar_kwh=self._zon_kwh,
                house_kwh=self._huis_kwh,
                estimated=self._zon_geschat,
                solar_factor=self._zon_gemeten(now),
                solar_day=now.date(),
            ),
        )

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
            # Zonder deze regel bleef `solar_measured_note` in v0.67.0 hangen
            # in de reden en bereikte hij de tijdlijn op de kaart nooit, terwijl
            # `plan-ahead-sheet.js` er wel naar keek.
            "solar_note": plan.solar_note,
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
                }
                for blok in plan.blocks
            ],
        }

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
        minuten = int((now - self._net_stil_sinds).total_seconds() // 60)
        if minuten < 1:
            return ""
        duur = "een minuut" if minuten == 1 else f"{minuten} minuten"
        return (
            f"De coach kan je netmeting al {duur} niet lezen, dus hij "
            "ziet niet hoeveel zon er over is en stuurt alleen op prijs en op je "
            "klaar-tijd. Kijk of de integratie van je slimme meter nog draait."
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
        return (
            f"Je lastbewaker geeft op dit moment {vrij:.0f} A vrij en je lader "
            f"kan {charger.max_amps:.0f} A. Meer vraagt de coach dus niet: "
            "daarboven knijpt de bewaker toch. Dat getal beweegt mee met wat de "
            "rest van je huis gebruikt."
        )

    def _fasen_stabiel(self, device: dict[str, Any]) -> int | None:
        """Dezelfde fasemeting, maar pas als hij `FASEMETING_RONDEN` lang staat.

        Een enkele ronde is nooit genoeg om iemand te vertellen dat zijn
        instelling niet klopt. Een meting die weifelt zet de teller op nul, dus
        er wordt alleen iets gezegd over een paal die er al minuten stabiel bij
        staat.
        """
        device_id = device.get("id", "")
        gemeten = self._measured_phases(device)
        if gemeten is None:
            self._fasen_gemeten.pop(device_id, None)
            return None

        vorig, keer = self._fasen_gemeten.get(device_id, (0, 0))
        keer = keer + 1 if vorig == gemeten else 1
        self._fasen_gemeten[device_id] = (gemeten, keer)
        return gemeten if keer >= FASEMETING_RONDEN else None

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
        }
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
    def async_boost(self, device_id: str, on: bool) -> None:
        """Snelladen aan of uit: laden op vol vermogen, ongeacht de prijs."""
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
        if not control or not device.get("device_id"):
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
        await self.hass.services.async_call(
            domain,
            service,
            {
                "device_id": device["device_id"],
                control["limit_field"]: amps,
                control["ttl_field"]: minutes,
            },
            blocking=True,
        )

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

        if self._niets_schrijven(charger, decision):
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
        """Start, stop or pause, in the word this installation uses."""
        domain, service = control["command_service"]
        word = (device.get("actions") or {}).get(action) or control["words"][action]
        await self.hass.services.async_call(
            domain,
            service,
            {"device_id": device["device_id"], control["command_field"]: word},
            blocking=True,
        )


@callback
def async_get_coach(hass: HomeAssistant) -> ChargerCoach:
    """The one coach for this Home Assistant."""
    data = hass.data.setdefault(DOMAIN, {})
    if "coach" not in data:
        data["coach"] = ChargerCoach(hass)
    return data["coach"]
