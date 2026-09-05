"""What the coach decides to do with a charging point, and why.

Deliberately free of Home Assistant. Everything in here is arithmetic on plain
numbers, which is what makes it possible to run a whole day of somebody's real
history through it and read the outcome before a single relay is switched. The
layer that reads sensors and sends commands lives next door in coach.py and
stays as thin as it can be.

Three ideas run through all of it.

**Never disappoint.** A deadline outranks a cheap hour and it outranks the sun.
Somebody who cannot drive to work does not care that the electricity was cheap.

**Own sun beats everything else on price.** A kilowatt-hour off the roof that
would otherwise be exported is worth what it costs to buy, minus the little that
exporting pays. In this country that is often thirty cents against two, so using
it is not a preference but simply the cheaper sum.

**Coarse is fine.** A kettle switches on, a cloud passes, and the charger is a
minute behind. A fuse carries a small overshoot for far longer than that, so
there is no reason to chase every watt, and every reason not to: a car that is
re-commanded every second stops charging altogether.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

# --- The hard limits ------------------------------------------------------

# Below this a charging point cannot deliver at all. Every brand lands on the
# same number because it is in the standard the cars speak.
MIN_AMPS = 6

# Room left under the fuse, als ondergrens. A minute of overshoot is harmless,
# but a household that switches on an oven while the car is at the ceiling
# should not be the thing that trips it.
#
# Twee ampère dekt trouwens geen oven; een oven is er tien tot zestien. Wat de
# marge werkelijk redt is dat een smeltveiligheid bij een overschrijding van een
# paar procent uren doet voordat hij komt, en de coach binnen een minuut heeft
# teruggeregeld. Dat werkt, maar het maakt die minuut wel veiligheidskritisch, en
# daarom staat er een snellere weg naast (zie `HAAST_SECONDEN` in coach.py).
FUSE_MARGIN_AMPS = 2.0

# En als aandeel van de zekering, want twee ampère betekent niet overal
# hetzelfde. Op een aansluiting van 25 A is dat acht procent en ruim genoeg; op
# 80 A is het nog maar twee en een half procent en dus veel te krap voor een
# huis dat in één klap een paar kilowatt bijschakelt. De marge is daarom het
# grootste van de twee.
FUSE_MARGIN_SHARE = 0.08

# The margin to keep when the installation has a load balancer of its own, such
# as an Easee Equalizer. Such a box guards the very same fuse, from the hardware
# side, and it cannot be switched off or argued with. Two regulators on one fuse
# is only a problem when they both act at the same moment, so the coach takes
# the wider margin and steps back first. The balancer then stays what it was
# meant to be: a net that never has to catch anything.
BALANCER_MARGIN_AMPS = 3.0

# A charger that has just been told to charge takes a moment to get there, and
# the car ramps up as well. Before this has passed, what is measured says
# nothing about what the session will do.
RAMP_MINUTES = 3

# Hoe ver vooruit er naar de eerstvolgende klaar-tijd wordt gezocht. Een week,
# want een schema herhaalt zich per week: staat er dan nog niets, dan staat er
# helemaal niets.
LOOKAHEAD_DAYS = 8

# Mains voltage per phase, the same figure the rest of the panel reckons with.
VOLTS = 230

# How much may be bought in on top of the surplus before "charging on surplus"
# stops being an honest description of it. On three phases the smallest step is
# over four kilowatts, so demanding an exact match would mean never charging on
# the sun at all.
SURPLUS_SLACK = 0.9

# Once charging, keep going at least this long. Cars dislike being interrupted,
# and a few of them stop asking for current altogether after a handful of
# cycles.
MIN_RUN_MINUTES = 10

# De stroom waarmee een auto wakker wordt gemaakt. Gemeten bij een Ford aan een
# Easee op 18-08-2026: op 6 A aangeboden bleef de paal minutenlang op
# `awaiting_start` staan met nul watt, en binnen twintig seconden na een ruimer
# aanbod liep hij. Terugzakken naar 6 A daarna was geen probleem, dus het is het
# wakker worden dat meer vraagt, niet het laden zelf.
#
# Eén ronde lang, en één poging per sessie. Twee keer heen en weer is precies het
# pendelen dat een auto na een stuk of wat pogingen helemaal laat afhaken, en de
# paar minuten bijkopen die dit hooguit kost wegen niet op tegen een auto die de
# hele middag stilstaat.
WAKE_AMPS = 10

# Hoe lang een auto de tijd krijgt voordat de kaart zegt dat hij niets afneemt.
# In seconden en niet in ronden, want een ronde is niet altijd een minuut: een
# statuswissel van de paal start er ook een. Op ronden geteld stond er drie
# seconden na het aanbod al "de auto neemt nog niets af", terwijl hij twintig
# seconden later gewoon begon.
WAITING_SECONDS = 60

# Hoeveel ronden achtereen de ladder "stoppen" moet zeggen voordat er echt
# gestopt wordt. Een wolk duurt een paar minuten, en daarvoor hoort een sessie
# niet af te breken.
#
# Dit staat los van de minimale looptijd hierboven en dat is geen dubbelop. De
# minimale looptijd beschermt alleen het bégin van een sessie; daarna kon één
# meting een sessie afbreken die al een uur liep. Samen begrenzen ze ook meteen
# hoe vaak er geschakeld kan worden: tien minuten draaien plus tien minuten
# uitstel plus een ronde maakt eenentwintig minuten per cyclus, dus hooguit
# drie per uur. Een aparte teller daarvoor zou een mechanisme zijn dat zijn werk
# al gedaan ziet.
#
# Tien, en niet drie. Sven op 05-09-2026, na een ochtend wisselend weer bij
# Van den Dam waarin de Ford om 10:10 en om 10:37 stopte en telkens opnieuw
# gewekt moest worden: "wekken doe maar per 10 min." Elke minuut vasthouden
# kost hooguit de ondergrens van de paal van het net; elke wekpoging is een
# auto die op een dag ophoudt met luisteren.
STOP_ROUNDS = 10

# De grenzen van een pauze die met een houdbaarheidsduur wordt weggeschreven.
# Korter dan een kwartier is niet de moeite en zou kunnen verlopen tussen twee
# ronden door; langer dan achttien uur neemt de laadpaal niet aan.
MIN_HOLD_MINUTES = 15
MAX_HOLD_MINUTES = 1080

# Only bother re-commanding when the difference is worth it; anything smaller is
# below what a car itself regulates to.
STEP_AMPS = 1

# Charging is never perfectly efficient: this much of what the charger delivers
# actually lands in the battery.
CHARGE_EFFICIENCY = 0.9

# Vanaf welke accustand "vol" ook echt vol heet. Een paal die `completed` meldt
# zegt alleen dat de auto niets meer aanneemt, en dat is iets anders: een auto
# met een laadgrens op 80% stopt daar ook. Onder deze grens noemt de coach het
# percentage in plaats van het woord vol.
FULL_PERCENT = 99.0

# Hoeveel goedkoper het ene moment moet zijn dan het andere voordat het meetelt.
# Een tiende cent per kWh, want dat is ook de fijnheid waarmee het paneel prijzen
# opschrijft: is het verschil kleiner, dan staan er twee gelijke bedragen op het
# scherm en zou de klant een keuze lezen die nergens op slaat.
#
# Dit is geen verfijning maar een reparatie. Bij een vast contract is de prijs
# van nu en de prijs van straks hetzelfde getal, en dan hangt "is dit goedkoper"
# af van de laatste cijfers achter de komma van een deling die wiskundig precies
# nul verschil oplevert. Viel dat de verkeerde kant op, dan besloot de coach dat
# hij op zon laadde terwijl er geen zon was, en pakte hij de zuinige zonstroom in
# plaats van het volle vermogen.
PRICE_MARGIN = 0.001

# Hoeveel duurder het uur waar een lopende beurt in zit mag zijn dan de uren
# van het plan voordat hij ervoor stopt. Een halve cent per kilowattuur: een
# hele cent is wel een reden om te stoppen (proef 40 in test_planner.py), een
# paar tiende cent niet. Een stop is niet gratis: een auto die uitgezet wordt
# komt daar niet altijd zelf weer uit (zie `nood_ruimte`), en in het virtuele
# huis stopte en startte hij op een zondagochtend vier keer omdat het uur van
# dat moment steeds een paar tiende cent duurder was dan het volgende zonuur.
STOP_MARGIN = 0.005


# --- What the coach is told -----------------------------------------------


@dataclass
class Grid:
    """What the house is doing right now."""

    # Positive while feeding back into the grid, in watts.
    surplus_w: float = 0.0
    # Current per phase, of which the heaviest is what a fuse cares about.
    phase_amps: list[float] = field(default_factory=list)
    fuse_amps: float = 25.0
    # How much of the charger's own draw is already in those phase readings.
    # Subtracted before working out what is left, or the coach would take its
    # own charging for household load and keep turning itself down.
    charger_amps: float = 0.0
    # How much room to leave under the fuse. Wider when a load balancer guards
    # the same fuse, so the coach is the one that gives way.
    margin_amps: float = FUSE_MARGIN_AMPS
    # Ruimte die in dezelfde ronde al aan een ánder laadpunt is toegezegd en die
    # nog niet in de fasemeting zit. Bij twee palen op één zekering rekenden ze
    # allebei dezelfde ampères als vrij, en samen namen ze dus twee keer wat er
    # één keer was.
    reserved_amps: float = 0.0
    # Wat de paal kort geleden nog trok, voor het geval hij net gestopt is. De
    # fasemeting van het huis loopt achter, dus die draagt die stroom nog even
    # terwijl de paal zelf al op nul staat. Zonder dit wordt dat aan het huis
    # toegerekend en denkt de coach dat de aansluiting vol zit. Zie
    # `meter_loopt_achter`.
    recent_charger_amps: float = 0.0
    # Hoeveel de lastbewaker van de installatie op dit moment vrijgeeft voor
    # het laden, als hij dat meldt. Zie `beschikbaar_van_bewaker`.
    balancer_amps: float | None = None


@dataclass
class Car:
    """The profile of the car that is plugged in."""

    capacity_kwh: float = 0.0
    # 1 of 3, en dat staat vast: het is een keuze in het autoprofiel en geen
    # meting. Er was een derde mogelijkheid, "allebei", en die maakte elke som
    # hieronder het traagste geval.
    phases: int = 3
    # What the car itself accepts, 0 when unknown.
    max_amps: float = 0.0
    # 0 to 100, or None when nobody knows.
    soc_percent: float | None = None
    # A guest charges straight away and until the cable comes out.
    guest: bool = False
    # Hoe de bewoner deze auto genoemd heeft. Alleen om erover te praten, nooit
    # om mee te rekenen. Zonder dit was een naam die je invulde nergens meer te
    # zien: de kaart toont de laadpaal en de meldingen zeiden "de auto".
    name: str = ""


@dataclass
class Charger:
    """The charging point, as it reports itself."""

    max_amps: float = 16.0
    connected: bool = False
    charging: bool = False
    # When the current session started, to honour the minimum run.
    started_at: datetime | None = None
    # What is really flowing. Not the same thing as what was asked for: a load
    # balancer on the connection, or the car itself, can hold the charger below
    # the limit the coach set.
    actual_amps: float = 0.0
    # De auto is vol. De kabel hangt er nog, maar er valt niets meer te laden en
    # dus ook niets meer te beslissen. Zonder deze viel een volle auto door naar
    # de zon- of prijsregel en stond er op de kaart dat hij nu het goedkoopst
    # laadt terwijl er niets gebeurt.
    complete: bool = False
    # De bewoner heeft gezegd dat het nu moet, hoe duur het ook is. Voor wie
    # eerder weg moet dan gepland; makkelijker dan een schema omgooien.
    boost: bool = False
    # En het omgekeerde: de bewoner heeft zelf op pauze gedrukt. Dat is geen
    # advies maar een opdracht, dus de coach houdt zijn handen thuis tot het
    # weer uit gaat of de kabel eruit komt.
    paused_by_user: bool = False
    # A load balancer has put the session on hold. Asking again changes nothing;
    # only waiting does.
    paused_by_balancer: bool = False
    # Why the charger is not drawing what it could, in the brand's own wording.
    # Empty when the installation has no sensor for it.
    no_current_reason: str = ""
    # The limit that is standing on the charger right now, as it reads back.
    # Needed to tell the coach's own throttle apart from anything else that
    # holds the charger down; see `throttled_by_coach`. None when the
    # installation has no sensor for it.
    limit_amps: float | None = None


@dataclass
class DayWindow:
    """Wat er op één weekdag is afgesproken."""

    enabled: bool = True
    not_before: time | None = None
    start_by: time | None = None
    done_by: time | None = None


@dataclass
class Window:
    """Wanneer dit apparaat mag draaien, als momenten en niet als kloktijden.

    Momenten, want de vraag "welke herhaling van elf uur" is niet te
    beantwoorden zonder het hele schema erbij. Met elke dag hetzelfde is het die
    van vanavond. Met een schema per dag kan het die van overmorgen zijn: wie
    zaterdag inplugt terwijl er pas maandag om zes uur iets klaar hoeft te zijn,
    heeft een deadline die twee dagen verderop ligt en een heel weekend om de
    goedkoopste uren uit te zoeken.
    """

    enabled: bool = False
    # Vanaf wanneer er geladen mag worden, of None als er geen ondergrens is.
    opens: datetime | None = None
    # Wanneer hij hoe dan ook begint, ook als het dan duur is. Dit stond in het
    # schemascherm, werd opgeslagen, en werd door niemand gelezen: `start_by`
    # zat wel in `DayWindow` maar kwam nooit in een `Window` terecht en dus
    # nooit in een besluit. Gevonden op 30-08-2026 bij het herbouwen van de
    # sturing. Het scherm belooft "op deze tijd start hij hoe dan ook", en dat
    # doet hij nu.
    start_by: datetime | None = None
    # Wanneer het klaar moet zijn.
    deadline: datetime | None = None
    # De dagen die de klant heeft uitgezet tussen nu en de klaar-tijd, bij hun
    # naam. Alleen voor de uitleg op de kaart: "zaterdag staat in je schema
    # uit, dus hij moet zondag om 06:00 vol zijn." Zonder dat las Sven op
    # 04-09-2026 "de prijzen tot 06:00 zijn nog niet bekend" als morgenochtend,
    # en die prijzen waren er wel; de klaar-tijd was zondag.
    skipped: tuple[str, ...] = ()


@dataclass
class Sun:
    """Wat de verwachting zegt dat er aan zon aankomt.

    Niet wat er nu gemeten wordt, dat staat in `Grid`. Dit is de voorspelling,
    en die beantwoordt een andere vraag: niet "hoeveel is er" maar "is wachten
    de moeite". Alles mag None zijn; zonder verwachting kijkt de coach gewoon
    alleen naar het heden, zoals hij altijd deed.
    """

    # Verwacht gemiddeld vermogen dit uur en het uur erna, in watt.
    now_w: float | None = None
    next_w: float | None = None
    # Wat er vandaag nog aan komt, in kWh.
    remaining_kwh: float | None = None


@dataclass
class Tariff:
    """Wat een kWh kost en opbrengt, als de prijslijst het niet zegt.

    Bij een vast contract staat het hele jaar hetzelfde getal en is er geen
    lijst. Bij een dynamisch contract staat de inkoopprijs per uur in de lijst
    en is `feed_in` wat teruglevering opbrengt.

    Allebei mogen None zijn en dat betekent "niet bekend", niet "nul". Het
    verschil is groot: nul zou zeggen dat teruglevering niets opbrengt, en dan
    lijkt bijkopen om de zon te gebruiken aantrekkelijker dan het is.
    """

    buy: float | None = None
    feed_in: float | None = None


@dataclass
class Decision:
    """What to do, and what to tell the customer."""

    charge: bool
    amps: int = 0
    # Short, in the customer's terms. Shown on the card and in the log.
    reason: str = ""
    # What the coach intends beyond this minute, when it can say.
    plan: str = ""
    # Which of the rules got us here, for the log rather than for the screen.
    rule: str = ""
    # Of dit een sessie is die tegen de ladder in wordt aangehouden. Alleen om
    # te tellen hoe lang dat al duurt; de klant leest het in `reason`.
    holding: bool = False
    # Hoe lang de coach van plan is deze pauze vast te houden, in minuten, of
    # None voor "tot nader order". Dat is geen tekst maar een getal dat de
    # laadpaal meekrijgt: valt de coach weg, dan bepaalt dit of de auto blijft
    # staan of vanzelf weer gaat laden. Bij wachten op een goedkoop uur mag hij
    # verlopen, want doorladen is dan hooguit duur. Bij een volle aansluiting
    # niet, want dan is doorladen gevaarlijk.
    hold_minutes: int | None = None
    # Of dit besluit genomen is zonder te weten hoe vol de auto is. Dan is er
    # gerekend met het slechtste geval, een lege accu, en kan de bewoner het
    # beter maken door zijn accustand door te geven. De kaart en de melding
    # hangen hieraan.
    needs_soc: bool = False
    # Of een opdracht van de bewoner zelf op het punt staat de klaar-tijd te
    # kosten. De coach zet die opdracht niet opzij, want het is zijn huis, maar
    # zwijgen hoort hier ook niet: dan staat de auto morgen leeg en is er niets
    # kapot om naar te wijzen.
    deadline_risk: bool = False


# --- The sums -------------------------------------------------------------


def amps_for(watts: float, phases: int) -> float:
    """Turn a power into a current, on one phase or on three."""
    return watts / (VOLTS * max(1, phases))


def watts_for(amps: float, phases: int) -> float:
    """And back again."""
    return amps * VOLTS * max(1, phases)


def meter_loopt_achter(grid: Grid, charger: Charger) -> bool:
    """Of de eigen meter van de paal nog niet bij is met wat er gevraagd is.

    Wat er bij Sven op 20-08-2026 misging. Hij zette snelladen aan, de coach
    schreef 16 A, de paal trok op, en de fasemeting van het huis stond al op 16
    terwijl de paal zelf nog 2,7 A meldde. Het verschil van 13,3 A werd toen aan
    het huis toegerekend terwijl het de auto zelf was, en er kwam 8 A uit. Een
    ronde later klopte het weer.

    Alleen waar terwijl de paal optrekt: er is meer gevraagd dan hij zegt af te
    nemen, en dat verschil is groter dan een stap. Zonder de sensor die de
    staande limiet teruggeeft is er niets om mee te vergelijken, en dan blijft
    het zoals het was.

    **En dezelfde na-ijl bestaat bij het afbouwen.** Die kant stond er niet in.
    Stopt de paal, dan staat zijn eigen meter meteen op nul terwijl de
    fasemeting van het huis zijn stroom nog een halve minuut meedraagt. Dat
    verschil werd dan aan het huis toegerekend, en de coach meldde dat de
    aansluiting te zwaar belast was terwijl er niets liep. Gezien bij Van den Dam
    op 29-08-2026 om 11:27:06, met de kabel er al uit: `regel=no-room`.
    """
    if charger.limit_amps is None:
        return False
    if not charger.charging:
        return grid.recent_charger_amps > STEP_AMPS
    return charger.limit_amps - grid.charger_amps > STEP_AMPS


def gevraagde_amps(grid: Grid, charger: Charger) -> float:
    """Het getal waarvan zeker is dat het van de paal komt en niet van het huis.

    Terwijl hij optrekt is dat de limiet die de coach erop gezet heeft. Is hij
    net gestopt, dan staat die limiet op nul terwijl de fasemeting zijn stroom
    nog draagt, en dan is het wat hij zojuist nog trok. Zonder dat onderscheid
    knijpt de rail in `ceiling_amps` op een nul die niets betekent.
    """
    if charger.charging and charger.limit_amps is not None:
        return charger.limit_amps
    return grid.recent_charger_amps


def charger_share(grid: Grid, charger: Charger) -> float:
    """Hoeveel ampère van de zwaarste fase van de laadpaal zelf is.

    Normaal is dat gewoon wat de paal meet. Loopt zijn meter achter, dan telt
    wat de coach zelf gevraagd heeft, want dat is het enige getal waarvan hij
    zeker weet dat het niet van het huis komt. Nooit meer dan er op die fase
    werkelijk loopt: meer aan de paal toerekenen dan er stroomt zou het huis
    stroom teruggeven die er niet is.
    """
    if not meter_loopt_achter(grid, charger):
        return grid.charger_amps
    zwaarste = max(grid.phase_amps) if grid.phase_amps else 0.0
    return max(grid.charger_amps, min(gevraagde_amps(grid, charger), zwaarste))


def ceiling_amps(grid: Grid, car: Car, charger: Charger) -> int:
    """The most this charger may draw right now, whatever the reason to charge.

    Three ceilings at once, and the lowest wins: what the charging point can
    deliver, what the car accepts, and what is left under the fuse on the
    heaviest phase. The charger's own current is taken out of that phase
    reading first, otherwise it reads its own charging as household load and
    walks itself down to the floor.
    """
    limits = [charger.max_amps]
    if car.max_amps:
        limits.append(car.max_amps)
    # En wat de lastbewaker vrijgeeft, als hij dat meldt. Dat is een eigen
    # plafond en geen tweede zekering: het huisverbruik zit er al af. Zie
    # `beschikbaar_van_bewaker`.
    bewaker = beschikbaar_van_bewaker(grid)
    if bewaker is not None:
        limits.append(bewaker)

    if grid.phase_amps:
        household = max(grid.phase_amps) - charger_share(grid, charger)
        ruimte = (
            grid.fuse_amps - max(0.0, household) - fuse_margin(grid) - grid.reserved_amps
        )
        if meter_loopt_achter(grid, charger):
            # De veiligheidsrail. Zolang de meter achterloopt is een deel van
            # deze som een aanname, en op een aanname mag er nooit méér gevraagd
            # worden dan er al gevraagd wás. Zo kan de correctie een onnodige
            # stap terug voorkomen, maar nooit een stap vooruit rechtvaardigen;
            # opschroeven wacht tot de paal het zelf bevestigt, en dat is één
            # ronde later. De marge blijft dus onaangeroerd, zoals afgesproken
            # met Sven op 26-08-2026.
            #
            # **Maar hij mag nooit onder de ondergrens duwen.** Deze rail zegt
            # "niet meer dan je al vroeg", en dat is iets anders dan "stop".
            # Stopt een paal die op 5,5 A liep, dan is `gevraagde_amps` 5,5, en
            # zonder deze grens komt het plafond op 5 uit: onder `MIN_AMPS`, dus
            # `no-room`, dus "je aansluiting is te zwaar belast" terwijl het huis
            # zeven ampère trok en de zekering 25 A is.
            #
            # Precies dat gebeurde bij Van den Dam op 30-08-2026 om 12:47:36 en
            # om 15:02:58. Beide keren stond er een ronde lang dat de aansluiting
            # vol zat, met de fasen op 5, 5 en 7. Ik heb er die dag twee keer
            # naar gezocht in de meting terwijl het de rail zelf was.
            #
            # Of er werkelijk geen ruimte is, beslist de som over de fasen
            # hierboven. Die staat er nog en wint gewoon als hij lager uitkomt.
            ruimte = min(ruimte, max(gevraagde_amps(grid, charger), float(MIN_AMPS)))
        limits.append(ruimte)

    return int(max(0, min(limits)))


def nood_ruimte(grid: Grid, charger: Charger) -> float:
    """Wat er onder de grens van de aansluiting past als de marge er niet was.

    De marge is comfort en geen natuurkunde. Hij staat er zodat een huis dat een
    oven aanzet de coach vóór is, niet omdat de laatste ampères eronder
    gevaarlijk zouden zijn. Een laadbeurt helemaal afbreken om die marge te
    sparen kost meer dan hij oplevert: een auto die uitgezet wordt komt daar
    lang niet altijd zelf weer uit.

    Gemeten bij Van den Dam in de nacht van 30-08-2026. De huismeter meldt daar
    elke dertig seconden en gaf om 04:28:56 één sample van 27 A op L3; tien
    seconden ervoor en dertig erna stond hij op 10. Op dat ene getal schreef de
    coach 0 A. De paal stond achtenzeventig seconden uit, de Ford beëindigde
    zijn laadbeurt, en die kwam de rest van de dag niet meer terug: de auto
    stond om 09:37 nog steeds op 69,5%.

    Dit tweede getal wordt daarom alleen gebruikt om een auto die al laadt op de
    laagste stand aan te houden. De grens zelf blijft heilig: past `MIN_AMPS` er
    ook zonder marge niet meer bij, dan gaat hij alsnog uit.
    """
    if not grid.phase_amps:
        return float("inf")
    household = max(0.0, max(grid.phase_amps) - charger_share(grid, charger))
    return grid.fuse_amps - household - grid.reserved_amps


def fuse_limited(grid: Grid, car: Car, charger: Charger) -> bool:
    """Whether the fuse is what is holding the charge down, not the charger or the car.

    Worth telling apart, because they read completely differently. "Snelladen
    staat aan, dus hij laadt op 8 A" sounds like a broken button; "meer past er
    nu niet onder je zekering" is an answer. Sven op 20-08-2026, die precies dat
    vroeg toen hij snelladen aanzette en er 8 A uit kwam.
    """
    if not grid.phase_amps:
        return False
    household = max(0.0, max(grid.phase_amps) - charger_share(grid, charger))
    room = grid.fuse_amps - household - fuse_margin(grid) - grid.reserved_amps
    hardware = [charger.max_amps] + ([car.max_amps] if car.max_amps else [])
    return room < min(hardware)


def beschikbaar_van_bewaker(grid: Grid) -> float | None:
    """Wat de lastbewaker op dit moment vrijgeeft voor het laden.

    **Dit is geen grens van de aansluiting maar een restwaarde**, en dat verschil
    is precies waar v0.44.0 de fout in ging. Daar werd dit getal als een tweede
    zekering behandeld, en dan gaat het huisverbruik er twee keer vanaf.

    Nagemeten bij Van den Dam op 30-08-2026, met `sensor.1_equalizer_limiet`:

    | moment | bewaker meldt | paal trok | huis zelf |
    |---|---|---|---|
    | 29-08 16:50 | 18 A | 15,0 A | ongeveer 5 A |
    | 29-08 17:20 | 20 A | 3,7 A | ongeveer 0 A |
    | 30-08 11:15 | 17 A | 0 A | ongeveer 5 A |

    Twee dingen staan daarmee vast. Het getal beweegt mee met wat het huis
    trekt, dus het huisverbruik zit er al af. En de paal zelf telt er niet in
    mee: om 16:50 trok hij vijftien ampère terwijl er achttien beschikbaar
    stond. Dat tweede is het belangrijkst, want het betekent dat er geen
    kringetje ontstaat waarin de coach zijn eigen laden voor huisverbruik
    aanziet en zichzelf naar beneden praat. Dezelfde valkuil als bij het
    overschot; zie `_read` in coach.py.

    Er gaat geen marge af. De bewaker rekent zelf al over de zekering en past
    zijn getal live aan, dus vragen wat hij vrijgeeft is per definitie niet meer
    dan hij toestaat. De marge in `fuse_margin` gaat over het huis dat zo meteen
    iets bijschakelt, en die staat er nog gewoon naast.
    """
    if grid.balancer_amps is None or grid.balancer_amps <= 0:
        return None
    return grid.balancer_amps


def fuse_margin(grid: Grid) -> float:
    """Hoeveel ruimte er onder de zekering vrij blijft.

    Een vast aantal ampère of een aandeel van de zekering, en het grootste van
    de twee wint. Zie `FUSE_MARGIN_SHARE` voor waarom een vast getal alleen niet
    volstaat.
    """
    return max(grid.margin_amps, grid.fuse_amps * FUSE_MARGIN_SHARE)


# The words the Easee reports when something other than the coach is holding the
# charger down. Kept as a set of the brand's own strings rather than translated,
# because this is read from a sensor and never shown as it is.
HELD_BACK_REASONS = frozenset(
    {
        "limited_by_equalizer",
        "eq_too_low_current",
        "limited_by_load_balancing",
        "limited_by_circuit_dynamic_limit",
        "limited_by_circuit_fuse",
        "limited_by_circuit_max_limit",
        "max_circuit_current_too_low",
        "max_dynamic_circuit_current_too_low",
        "awaiting_load_balancing",
    }
)


# En welke daarvan over de lastbewaker van de aansluiting gaan en niet over de
# eigen groep van de lader. Alleen bij deze eerste zegt de bewakersensor iets
# over dezelfde vraag, en kan hij dus tegenspreken wat de paal meldt.
BALANCER_REASONS = frozenset(
    {
        "limited_by_equalizer",
        "eq_too_low_current",
        "limited_by_load_balancing",
        "awaiting_load_balancing",
    }
)


def held_back(charger: Charger) -> bool:
    """Whether something outside the coach is keeping this charger down."""
    return charger.no_current_reason in HELD_BACK_REASONS


# Wat een paal meldt zolang de laadbeurt nog goedgekeurd moet worden. Dit staat
# bewust níet in HELD_BACK_REASONS: dat zou de coach op de rustige herhaalklok
# zetten, en juist het elke ronde opnieuw sturen is wat de paal bij Van den Dam
# op 29-08-2026 aan de praat kreeg. Het is alleen bedoeld om het goede te zeggen.
AUTHORISATION_REASONS = frozenset({"pending_authorization", "awaiting_authorization"})


# The word the Easee reports when the coach's own dynamic limit is the binding
# one. Only used as a fallback: reading the limit itself is brand independent.
OWN_LIMIT_REASON = "limited_by_charger_dynamic_limit"


def throttled_by_coach(charger: Charger) -> bool:
    """Whether the coach's own limit is the thing keeping this charger down.

    This is the difference between "it cannot go faster" and "I am not asking
    for faster", and mixing the two up is expensive. Op 20-08-2026 stond er om
    15:48 een auto op 12% aan de paal, zonvolgend op 6 A. De klaar-tijdsom
    rekende met die gemeten 6 A, zag dat 06:00 zo niet gehaald werd en zette hem
    tot de volgende ochtend op vol vermogen. Op 14 A had hij pas om 23:46 hoeven
    beginnen: ruim acht uur later, en al die tijd was er zon of een goedkoop uur
    te pakken geweest.

    Reading the limit that stands on the charger settles it without knowing the
    brand: draw it to within a step and nothing else is in the way, because the
    only thing the charger is respecting is what the coach put there. Without
    that sensor the brand's own wording is the next best answer, and without
    that too the caller falls back on the measured current, which is what it
    always did.
    """
    if charger.limit_amps is not None:
        return charger.actual_amps >= charger.limit_amps - STEP_AMPS
    return charger.no_current_reason == OWN_LIMIT_REASON


def charging_pace(now: datetime, charger: Charger, wanted: int) -> int:
    """What this charger is really going to draw, not what it was asked for.

    Asking is not the same as getting. A load balancer on the connection holds
    the charger under the limit the coach set, and a car that is nearly full
    tapers off by itself. Either way the deadline sum goes wrong in the one
    direction that matters: the coach believes it has hours in hand, waits for a
    cheaper one, and the car is not full in the morning.

    So once a session has settled, the measured current is what counts. During
    the first few minutes it is not: everything is still ramping up and reading
    that as the pace would have the coach charge far earlier than it needs to.

    And neither does it count while the coach is its own brake. A charging point
    that is following the sun draws six amps because it was told to, not because
    that is all it can do, and reading that back as the pace is how the coach
    talks itself into charging at full power all afternoon. See
    `throttled_by_coach`.
    """
    if not charger.charging or charger.started_at is None or charger.actual_amps <= 0:
        return wanted
    if now - charger.started_at < timedelta(minutes=RAMP_MINUTES):
        return wanted
    if charger.actual_amps >= wanted - STEP_AMPS:
        return wanted
    if throttled_by_coach(charger):
        return wanted
    return max(MIN_AMPS, int(charger.actual_amps))


def energy_needed_kwh(car: Car) -> float | None:
    """How much still has to go into this car, when that is knowable.

    Needs both a battery size and a state of charge. Without them the coach
    charges the cheapest hours until the car stops by itself, which is not as
    clever but never wrong.
    """
    if car.guest or not car.capacity_kwh or car.soc_percent is None:
        return None

    missing = max(0.0, (100.0 - car.soc_percent) / 100.0 * car.capacity_kwh)
    return missing / CHARGE_EFFICIENCY


def worst_case_kwh(car: Car) -> float | None:
    """Hoeveel er in moet als niemand weet hoe vol de auto is.

    Het slechtste geval, en dat is hier het enige eerlijke antwoord: een lege
    accu. Daarmee kan de coach wél uitrekenen hoe laat hij uiterlijk moet
    beginnen, zonder één verzonnen getal, want de capaciteit staat gewoon in het
    autoprofiel.

    Dat is geen reden om vroeg te gaan laden. Het is een uiterste
    startmoment, meer niet: tot dat moment wacht hij, en ondertussen vraagt hij
    de bewoner om de accustand, waarmee het meteen scherper wordt.
    """
    if car.guest or not car.capacity_kwh:
        return None
    return car.capacity_kwh / CHARGE_EFFICIENCY


def charge_cost(watts: float, surplus_w: float, buy: float, feed_in: float) -> float:
    """Wat een kWh in de auto kost als je nu laadt, alles meegerekend.

    Twee posten. De zon die je zelf gebruikt kost je wat je er anders voor had
    gekregen: de terugleververgoeding, na aftrek van de kosten die je
    leverancier daarover rekent. Wat er aan die zon tekortkomt koop je in tegen
    de prijs van dit moment.

    Zo wordt "laden op de zon" een bedrag per kWh dat je naast andere uren kunt
    leggen, en dat is de enige eerlijke manier om te beslissen. Levert de zon
    genoeg, dan komt er de terugleververgoeding uit en dat is bijna altijd het
    goedkoopste moment van de dag. Levert hij bijna niets, dan komt de
    inkoopprijs eruit en wint een goedkoop nachtuur vanzelf.
    """
    power = max(watts, 1.0) / 1000.0
    eigen = min(max(0.0, surplus_w) / 1000.0, power)
    gekocht = power - eigen
    return (eigen * feed_in + gekocht * buy) / power


def cheapest_price(prices: list[dict], since: datetime, until: datetime | None) -> float | None:
    """De laagste prijs die er tussen nu en de klaar-tijd nog aankomt."""
    usable = [
        row["price"]
        for row in prices
        if row["end"] > since and (until is None or row["start"] < until)
    ]
    return min(usable) if usable else None


def hours_needed(car: Car, amps: int, assume_empty: bool = False) -> float | None:
    """Hoe lang dat duurt bij deze stroom.

    Het aantal fasen staat in het autoprofiel en is geen aanname meer, dus deze
    som rekent er gewoon mee. Dat was anders zolang "allebei" bestond: dan werd
    hier het traagste geval genomen, want een auto die kan wisselen verraadt zich
    pas als hij laadt, en drie fasen aannemen die er één blijken te zijn levert
    een auto op die 's ochtends halfvol staat.

    De prijs daarvan was hoog. Bij Van den Dam stond op 29-08-2026 een bus van
    65 kWh op 12%: met "allebei" rekende deze som 17,2 uur en sloeg de
    klaar-tijdregel om 11:13 al aan, waarna hij op 16 A van het net laadde
    terwijl er zon lag. Met driefasig is het 5,7 uur en had hij tot 01:07 de tijd.

    Klopt de keuze in het profiel niet met wat er werkelijk gebeurt, dan is dat
    te zien zodra er stroom loopt en zegt `_fasetip` in coach.py het.

    Met `assume_empty` wordt gerekend alsof de accu leeg is. Dat is wat er
    overblijft als de accustand onbekend is, en het levert het uiterste
    startmoment op.
    """
    energy = worst_case_kwh(car) if assume_empty else energy_needed_kwh(car)
    if energy is None or amps <= 0:
        return None
    return energy / (watts_for(amps, car.phases) / 1000.0)


def _at(day: datetime, moment: time | None) -> datetime | None:
    """A time of day on the day of `day`."""
    if moment is None:
        return None
    return day.replace(hour=moment.hour, minute=moment.minute, second=0, microsecond=0)


def resolve_window(now: datetime, days: dict[int, DayWindow]) -> Window:
    """Het schema omrekenen naar twee momenten: vanaf wanneer, en waarvoor.

    `days` is per weekdag (0 is maandag) wat er die dag moet gebeuren. Staat er
    elke dag hetzelfde, dan zitten er zeven dezelfde in; is het per dag
    ingesteld, dan staan alleen de dagen erin die de klant heeft aangezet.

    **De klaar-tijd hoort bij zijn eigen dag.** "Maandag klaar om 06:00" is
    maandagochtend zes uur. De coach zoekt vooruit naar de eerstvolgende
    klaar-tijd die nog moet komen, tot een week ver. Daarmee is het antwoord op
    zaterdag inpluggen met alleen maandag als eis: maandag 06:00, en dus een
    heel weekend om de goedkoopste uren uit te kiezen.

    **Vanaf-wanneer bindt alleen als zijn eigen dag aan staat.** Dat is het
    enige stukje dat niet rechtstreeks uit de instelling volgt, en het is de
    kern van wat hier gevraagd werd. "Niet voor elf uur" hoort bij de avond waar
    het op staat. Ligt die avond op een dag die de klant heeft uitgezet, dan is
    er die dag niets afgesproken en geldt de ondergrens dus ook niet. Zonder die
    regel lag het hele weekend dicht en stond de auto tot zondagavond elf uur
    stil, terwijl er juist twee dagen waren om het goedkoopste moment te zoeken.

    Zonder ingeschakelde dag met een klaar-tijd komt er geen venster uit, en dan
    laadt de coach gewoon op de goedkoopste uren die hij ziet.
    """
    if not days:
        return Window()

    overgeslagen: list[str] = []
    for offset in range(LOOKAHEAD_DAYS):
        basis = now + timedelta(days=offset)
        day = days.get(basis.weekday())
        if day is not None and not day.enabled:
            overgeslagen.append(DAGNAMEN[basis.weekday()])
        if day is None or not day.enabled or day.done_by is None:
            continue

        deadline = _at(basis, day.done_by)
        if deadline is None or deadline <= now:
            continue

        opens = _at(basis, day.not_before)
        # Ligt "vanaf" na "klaar om", dan gaat het over de avond ervoor: niet
        # voor elf uur, klaar om zeven, is de nacht ertussen.
        if opens is not None and opens >= deadline:
            opens -= timedelta(days=1)
        # En hij bindt alleen als er op die dag iets is afgesproken.
        if opens is not None:
            avond = days.get(opens.weekday())
            if avond is None or not avond.enabled:
                opens = None

        # "Uiterlijk starten om" hoort bij dezelfde nacht als de klaar-tijd, dus
        # precies zoals "niet eerder dan": ligt hij erna, dan gaat hij over de
        # avond ervoor.
        uiterlijk = _at(basis, day.start_by)
        if uiterlijk is not None and uiterlijk >= deadline:
            uiterlijk -= timedelta(days=1)

        return Window(
            enabled=True, opens=opens, start_by=uiterlijk, deadline=deadline,
            skipped=tuple(overgeslagen),
        )

    return Window()


def cheapest_hours(
    prices: list[dict],
    since: datetime,
    until: datetime | None,
    hours: float,
) -> list[dict]:
    """The cheapest slots between `since` and the deadline, enough to fill `hours`.

    Both ends matter and leaving one out is expensive. Without a lower bound the
    cheapest hours of the whole published list get picked, which at eleven in the
    evening are this afternoon's -- hours that have already gone. The coach then
    finds nothing to do all night and ends up charging on the dearest hours at
    dawn because the deadline forces it. That is the exact opposite of the job.

    Sorted back into time order afterwards, because what comes out of here is
    read as a plan and a plan runs forwards.
    """
    usable = [
        row
        for row in prices
        if row["end"] > since and (until is None or row["start"] < until)
    ]
    if not usable:
        return []

    slot_hours = (usable[0]["end"] - usable[0]["start"]).total_seconds() / 3600
    wanted = max(1, int(hours / slot_hours + 0.999)) if hours else len(usable)

    chosen = sorted(usable, key=lambda row: row["price"])[:wanted]
    return sorted(chosen, key=lambda row: row["start"])



# --- de tijdlijn ------------------------------------------------------------


# --- alle manieren om een kilowattuur in de auto te krijgen -----------------

# Onder deze hoeveelheid is een schijf het rekenen niet waard. Een honderdste
# kilowattuur is drie seconden laden.
SCHIJF_MINIMUM = 0.01


@dataclass
class Schijf:
    """Eén manier om kilowattuur in de auto te krijgen, met wat die kost.

    Elk uur levert er twee: wat er uit de eigen zon kan, en wat er daarboven van
    het net moet komen. Ze staan los omdat ze verschillend kosten, en juist die
    twee prijzen naast elkaar leggen is het hele idee.
    """

    start: datetime
    end: datetime
    # Wat een kilowattuur via deze manier kost.
    price: float
    # Hoeveel er via deze manier past.
    kwh: float
    # Welke van de drie dit is:
    #
    #   "zon"   het dak geeft genoeg om er op eigen kracht op te laden
    #   "vloer" het dak geeft wél iets maar te weinig voor de ondergrens van de
    #           paal, dus de prijs is een mengsel van zon en bijkopen
    #   "net"   alles boven de zon, tegen de prijs van dat uur
    kind: str = "net"
    # Hoeveel van `kwh` werkelijk van het dak komt. Bij "zon" alles, bij
    # "vloer" alleen wat er over is (de rest is bijkopen), bij "net" niets.
    # Voor de tijdlijn: die zei "4,1 kWh zon" over een uur waarin het dak 2,4
    # gaf en het huis een deel opat. Sven op 04-09-2026: "dat weet je toch
    # niet." De 4,1 was wat er in de auto ging, zon plus net.
    zon_kwh: float = 0.0

    @property
    def solar(self) -> bool:
        """Of hier eigen zon in zit, in welke verhouding dan ook."""
        return self.kind in ("zon", "vloer")


@dataclass
class Forecast:
    """Wat er van de komende uren verwacht wordt.

    Twee dingen, allebei uit metingen en niet uit een aanname. De zon komt uit de
    voorspelling die aan het energiedashboard van Home Assistant hangt, en het
    huisverbruik uit de eigen meters van de woning. Zie `_zonkromme` en
    `_huisverbruik` in coach.py.

    Allebei mogen leeg zijn. Dan zijn er geen zonschijven voor de uren die nog
    moeten komen en kiest de coach op prijs alleen, precies zoals hij deed
    voordat dit bestond. Het uur waar we nú in zitten heeft de voorspelling niet
    nodig: daar wordt gemeten.
    """

    # De verwachte opbrengst per uur, in kWh, met het beginmoment als sleutel.
    solar_kwh: dict[datetime, float] = field(default_factory=dict)
    # Wat het huis zelf gebruikt, per uur van de dag, in kWh.
    house_kwh: dict[int, float] = field(default_factory=dict)
    # Of de zon per uur uit een echte uurkromme komt of over de dag verdeeld is.
    estimated: bool = False


def _vlakke_blokken(
    now: datetime, end: datetime | None, tariff: Tariff
) -> list[dict]:
    """Uurblokken tegen één vaste prijs, voor een contract zonder prijslijst.

    Zo hoeft er maar één som te bestaan. Bij een vast tarief kost elk uur
    hetzelfde en is de zon het enige dat de ene keuze van de andere onderscheidt,
    en dat komt er vanzelf uit: de zonschijven zijn dan de goedkoopste van
    allemaal en worden het eerst gepakt. De avondregel die hier vroeger voor
    stond is daarmee overbodig geworden in plaats van weggehaald.
    """
    if tariff.buy is None:
        return []
    grens = end or (now + PLAN_HORIZON)
    blokken = []
    uur = now.replace(minute=0, second=0, microsecond=0)
    while uur < grens:
        blokken.append(
            {
                "start": uur,
                "end": uur + timedelta(hours=1),
                "price": tariff.buy,
                "feed_in": tariff.feed_in,
            }
        )
        uur += timedelta(hours=1)
    return blokken


def structural_ceiling(car: Car, charger: Charger) -> int:
    """Wat deze paal en deze auto samen kunnen, los van dit moment.

    Het plafond van `ceiling_amps` is van nú: de zekering, de lastbewaker, wat
    het huis op dit moment trekt. Dat hoort niet in de uren die nog komen. Toen
    dat wel zo was, knijpte een Equalizer om 13:30 de paal naar 9 A, rekende de
    coach met die 9 A voor de hele nacht, zag dat het dan niet meer paste en
    zette de klaar-tijdregel aan terwijl er tijd zat was. Gezien in het
    virtuele huis op 04-09-2026.
    """
    plafond = charger.max_amps
    if car.max_amps:
        plafond = min(plafond, car.max_amps)
    return int(max(0, plafond))


def schijven(
    now: datetime,
    prices: list[dict],
    grid: Grid,
    car: Car,
    ceiling: int,
    start: datetime | None,
    end: datetime | None,
    tariff: Tariff = Tariff(),
    forecast: Forecast = Forecast(),
    ceiling_later: int | None = None,
    alleen_zon: bool = False,
) -> list[Schijf]:
    """Alle manieren om tussen nu en de klaar-tijd te laden, met hun prijs.

    Per uurblok twee schijven. De eerste is wat er uit de eigen zon kan, en die
    kost wat je er anders voor gekregen had; bij salderen is dat de inkoopprijs
    min wat je leverancier houdt. De tweede is de rest tot het plafond van de
    paal, en die kost de prijs van dat uur.

    Voor het blok waar we nú in zitten is de zon geen voorspelling maar de
    meting van dit moment. Dat is het verschil tussen sturen en gokken: wat er
    werkelijk uit het dak komt weegt zwaarder dan wat er verwacht werd.

    Buiten je begintijd bestaat er niets, en na de klaar-tijd ook niet. Zo zit
    het schema in dezelfde som en niet in een sport ernaast.
    """
    blokken = prices or _vlakke_blokken(now, end, tariff)
    vermogen_kw = watts_for(ceiling, car.phases) / 1000.0
    # Voor de uren die nog komen geldt wat paal en auto kunnen, niet wat er op
    # dit moment onder de zekering of de lastbewaker past. Zie `structural_ceiling`.
    vermogen_later_kw = watts_for(
        ceiling if ceiling_later is None else ceiling_later, car.phases
    ) / 1000.0
    if not blokken or vermogen_kw <= 0:
        return []

    vanaf = max(now, start) if start else now

    # De avondregel, en die gaat niet over prijs.
    #
    # Sven op 20-08-2026: "op een vast contract is een kwartier speling niet
    # voldoende. Ik wil dat wanneer het niet meer rendabel is van de zon, hij
    # vanaf 20 uur gaat laden. Dan heb je de grote pieken van het koken achter
    # de rug en belast je het ook niet zo veel."
    #
    # Bij een vast tarief kost elk uur hetzelfde, dus de vergelijking is
    # onverschillig tussen zes uur en acht uur en pakt het vroegste. Daarmee zou
    # deze afspraak verdwijnen, en het is er een over de aansluiting en niet over
    # geld. Hij staat er dus als voorwaarde in: vóór de avond komt er niets van
    # het net bij.
    #
    # **Alleen voor het net.** Zon die er nú is blijft gewoon beschikbaar, want
    # die belast de aansluiting niet en kost niets. Dat is precies het verschil
    # dat de oude sport ook maakte.
    #
    # Bij een dynamisch contract is dit overbodig: daar is de avondpiek vanzelf
    # het duurste uur van de dag en kiest de som hem toch al niet.
    netto_vanaf = vanaf
    if not prices:
        avond = _evening_before(end)
        if avond is not None and avond > vanaf:
            netto_vanaf = avond
    uit: list[Schijf] = []
    for rij in blokken:
        if rij["end"] <= vanaf or (end is not None and rij["start"] >= end):
            continue
        van = max(rij["start"], vanaf)
        tot = min(rij["end"], end) if end is not None else rij["end"]
        deel = (tot - van).total_seconds() / 3600.0
        if deel <= 0:
            continue
        nu_blok = rij["start"] <= now < rij["end"]
        plafond_kwh = (vermogen_kw if nu_blok else vermogen_later_kw) * deel

        if nu_blok:
            over = max(0.0, grid.surplus_w) / 1000.0 * deel
        else:
            heel = (rij["end"] - rij["start"]).total_seconds() / 3600.0
            verwacht = forecast.solar_kwh.get(rij["start"], 0.0)
            thuis = forecast.house_kwh.get(rij["start"].hour, 0.0)
            over = max(0.0, verwacht - thuis) * (deel / heel if heel else 1.0)

        terug = rij.get("feed_in")
        if terug is None:
            terug = tariff.feed_in

        # Zonder een terugleverwaarde is niet te zeggen dat de zon goedkoper is,
        # en dan gaat het hele blok als net de lijst in. Liever geen voorkeur dan
        # een verzonnen voorkeur.
        # Een paal levert niets onder `MIN_AMPS`. Geeft het dak minder dan dat,
        # dan bestaat "op die zon laden" niet: je koopt er onvermijdelijk bij.
        # Dat is geen reden om die zon weg te gooien maar om hem in de prijs te
        # verwerken, en dat is precies wat `charge_cost` doet. Een uur met 0,9 kW
        # zon en een vast tarief komt zo op 0,19 uit in plaats van op 0,24, en
        # dat is het eerlijke getal om naast een nachtuur te leggen.
        #
        # Zonder terugleverwaarde valt er niets te mengen en gaat alles als net
        # de lijst in. Liever geen voorkeur dan een verzonnen voorkeur.
        vloer_kwh = watts_for(MIN_AMPS, car.phases) / 1000.0 * deel
        gedekt = 0.0
        if terug is not None and over > SCHIJF_MINIMUM:
            if over >= vloer_kwh * SURPLUS_SLACK:
                gedekt = min(over, plafond_kwh)
                if gedekt > SCHIJF_MINIMUM:
                    uit.append(
                        Schijf(rij["start"], rij["end"], terug, gedekt, "zon", gedekt)
                    )
            elif in_evening_peak(rij["start"]):
                # Bijkopen tot de ondergrens is ook net, en in de avondpiek
                # komt er niets van het net bij. De zon van dat uur is dan te
                # weinig om alleen op te laden, dus dat uur bestaat niet.
                #
                # Buiten de avondpiek telt zo'n uur wél, ook als de prijzen
                # tot de klaar-tijd nog niet bekend zijn (`alleen_zon`). Sven
                # op 05-09-2026: "het kan toch zijn dat je wel wat opwekt om
                # 14 uur en dan is vaak de prijs ook goedkoop; dat weegt
                # zwaarder dan op een iets goedkopere prijs laden in de
                # nacht." Een uur met zon is een zonuur, ook als er net bij
                # moet; een uur zonder zon wacht op de prijzen.
                pass
            else:
                gedekt = min(vloer_kwh, plafond_kwh)
                gemengd = charge_cost(
                    watts_for(MIN_AMPS, car.phases),
                    over / deel * 1000.0 if deel else 0.0,
                    rij["price"],
                    terug,
                )
                if gedekt > SCHIJF_MINIMUM:
                    uit.append(
                        Schijf(rij["start"], rij["end"], gemengd, gedekt, "vloer",
                               min(over, gedekt))
                    )

        if (
            plafond_kwh - gedekt > SCHIJF_MINIMUM
            and rij["end"] > netto_vanaf
            and not in_evening_peak(rij["start"])
            and not alleen_zon
        ):
            uit.append(
                Schijf(rij["start"], rij["end"], rij["price"], plafond_kwh - gedekt)
            )
    return uit


def capaciteit_kwh(
    now: datetime,
    start: datetime | None,
    end: datetime | None,
    grid: Grid,
    car: Car,
    ceiling_later: int,
    forecast: Forecast = Forecast(),
    vast: bool = False,
) -> float:
    """Hoeveel er tot `end` nog in kan, wat de prijzen ook zijn.

    Voor de klaar-tijdregel. Die mag niet afhangen van welke prijzen al bekend
    zijn: een weekend waarin er alleen op zon geladen wordt omdat de prijzen
    van maandag er nog niet zijn (zie `alleen_zon` in `_decide`) is geen reden
    om zaterdagochtend al op vol vermogen te gaan. Wel afhankelijk van wat er
    wérkelijk dicht is: de avondpiek, en bij een vast contract de avond voor
    de klaar-tijd. Daar telt alleen de zon die er dan verwacht wordt.
    """
    if end is None:
        return float("inf")
    vanaf = max(now, start) if start else now
    avond = _evening_before(end) if vast else None
    vermogen = watts_for(ceiling_later, car.phases) / 1000.0
    som = 0.0
    uur = now.replace(minute=0, second=0, microsecond=0)
    while uur < end:
        volgend = uur + timedelta(hours=1)
        van = max(uur, vanaf)
        tot = min(volgend, end)
        deel = (tot - van).total_seconds() / 3600.0
        if deel > 0:
            net_mag = not in_evening_peak(uur) and (avond is None or volgend > avond)
            if net_mag:
                som += vermogen * deel
            else:
                if uur <= now < volgend:
                    over = max(0.0, grid.surplus_w) / 1000.0 * deel
                else:
                    over = max(
                        0.0,
                        forecast.solar_kwh.get(uur, 0.0) - forecast.house_kwh.get(uur.hour, 0.0),
                    ) * deel
                som += min(over, vermogen * deel)
        uur = volgend
    return som


def goedkoopste(alle: list[Schijf], nodig_kwh: float) -> list[tuple[Schijf, float]]:
    """De goedkoopste manier om `nodig_kwh` binnen te krijgen.

    Sorteren op prijs en van onder af vullen. Dat is niet zomaar een redelijke
    aanpak maar aantoonbaar de beste: elke schijf is deelbaar en kost overal
    hetzelfde per kilowattuur, en dan is dit het gebroken-knapzakprobleem. Daar
    is gulzig van goedkoop naar duur bewijsbaar optimaal.

    Wat eruit komt staat op tijd gesorteerd, want het wordt gelezen als een plan
    en een plan loopt vooruit.
    """
    rest = max(0.0, nodig_kwh)
    uit: list[tuple[Schijf, float]] = []
    for schijf in sorted(alle, key=lambda s: (s.price, s.start)):
        if rest <= SCHIJF_MINIMUM:
            break
        pak = min(schijf.kwh, rest)
        rest -= pak
        uit.append((schijf, pak))
    return sorted(uit, key=lambda paar: paar[0].start)


def _uren_van(gekozen: list[tuple[Schijf, float]]) -> list[dict]:
    """De gekozen schijven als uren, voor `_describe`.

    Twee schijven van hetzelfde uur zijn één uur op het scherm, en de prijs die
    erbij hoort is wat dat uur gemiddeld kost.
    """
    per_uur: dict[datetime, list[tuple[Schijf, float]]] = {}
    for schijf, kwh in gekozen:
        per_uur.setdefault(schijf.start, []).append((schijf, kwh))

    uit = []
    for start in sorted(per_uur):
        rijen = per_uur[start]
        totaal = sum(kwh for _, kwh in rijen)
        prijs = (
            sum(schijf.price * kwh for schijf, kwh in rijen) / totaal
            if totaal
            else rijen[0][0].price
        )
        uit.append({"start": start, "end": rijen[0][0].end, "price": prijs})
    return uit


def _kwh(waarde: float) -> str:
    """Kilowattuur zoals het paneel ze schrijft."""
    return f"{waarde:.1f} kWh".replace(".", ",")


@dataclass
class Blok:
    """Eén blok in de tijdlijn, meestal een uur lang."""

    start: datetime
    end: datetime
    # De all-in prijs van dat blok, of None bij een vast contract.
    price: float | None = None
    # Of de coach van plan is er in te laden.
    charging: bool = False
    # In één woord waarom, voor de kolom ernaast.
    why: str = ""
    # Hoeveel er in dit uur werkelijk van het dak verwacht wordt, na het huis,
    # en hoeveel hij er in totaal van plan is te laden. Bij een vloer-uur is
    # het tweede meer dan het eerste: de rest is bijkopen.
    solar_kwh: float = 0.0
    kwh: float = 0.0
    # En hoe hard dat is, gemiddeld over het blok: de stroom en het vermogen.
    # Sven op 04-09-2026: "laat sowieso zien hoeveel ampère hij laadt en kW."
    amps: int = 0
    kw: float = 0.0


@dataclass
class Plan:
    """Wat de coach van plan is tot de auto vol moet zijn.

    Alles hieronder komt uit dezelfde sommen als het besluit van deze minuut.
    Dat is de eis: een tijdlijn die iets anders zegt dan wat de coach doet is
    erger dan geen tijdlijn, want dan gaat de bewoner op het verkeerde wachten.
    Vandaar dat `blocks` uit `cheapest_hours` komt, met precies dezelfde grenzen
    als in `decide`.
    """

    # Wanneer de auto vol moet zijn, en het moment waarop de coach dan uiterlijk
    # begint. Dat laatste heeft de speling er al af; zie `DEADLINE_SLACK_HOURS`.
    deadline: datetime | None = None
    latest_start: datetime | None = None
    # Wat er nog in moet en hoe lang dat duurt op de stroom die er nu past.
    kwh_needed: float | None = None
    hours_needed: float | None = None
    amps: int = 0
    # Het einde van het laatste blok waarin hij van plan is te laden. Alleen
    # een belofte als `planned_kwh` het hele tekort dekt; zie daar.
    expected_done: datetime | None = None
    # Hoeveel er in de blokken hieronder gepland staat. Is dat minder dan
    # `kwh_needed`, dan is `expected_done` niet het moment waarop hij vol is
    # maar het einde van wat hij nú al kan plannen. In de alleen-zon-stand is
    # dat de helft: bij Van den Dam stond op 04-09-2026 "Vol rond 17:00" boven
    # acht zonblokken van samen 33 van de 66 kWh, en Sven las dat als een
    # belofte. Het scherm zegt sindsdien wat er gepland is en niet wanneer hij
    # vol is, zolang die twee niet hetzelfde zijn.
    planned_kwh: float = 0.0
    # Of de blokken alleen zon bevatten omdat de prijzen tot de klaar-tijd nog
    # niet bekend zijn. Dan komt de rest van het plan rond 13:00, en dat is een
    # andere uitleg dan "meer past er niet".
    solar_only: bool = False
    blocks: list[Blok] = field(default_factory=list)
    # Waarom er geen blokken zijn, als die er niet zijn.
    note: str = ""
    # Of de zon per uur een meting is of een schatting. Zie `_zonkromme` in
    # coach.py: staat er geen uurkromme klaar, dan wordt de dagverwachting over
    # de daglichturen verdeeld, en dat hoort het scherm te zeggen.
    estimated: bool = False


# Hoe ver een tijdlijn vooruit kijkt als er geen klaar-tijd is. Dan is er geen
# einde om naartoe te rekenen en zijn de blokken alleen nog "wat kost het per
# uur"; een etmaal is dan wat er aan prijzen bekend is en niet meer.
PLAN_HORIZON = timedelta(hours=24)


def timeline(
    now: datetime,
    prices: list[dict],
    grid: Grid,
    car: Car,
    charger: Charger,
    window: Window,
    ceiling: int,
    tariff: Tariff = Tariff(),
    forecast: Forecast = Forecast(),
) -> Plan:
    """De hele tijdlijn tot de auto vol moet zijn.

    Bedoeld voor het scherm en niet voor een besluit: hier wordt niets gestuurd.
    **Maar hij rekent met precies dezelfde schijven als het besluit van deze
    minuut**, dus wat er staat is wat er gebeurt. Een tijdlijn die iets anders
    zegt dan wat de coach doet laat de bewoner op het verkeerde wachten, en dat
    is erger dan geen tijdlijn.

    Sven op 30-08-2026: "ik wil zien wat de coach van plan is met hele tijdlijn
    tot dat hij vol moet zijn."
    """
    klaar = window.deadline if window.enabled else None
    # De tijdlijn eindigt waar het plan eindigt: een uur voor de klaar-tijd.
    einde = plan_end(klaar)
    begin = window.opens if window.enabled else None
    amps = max(MIN_AMPS, ceiling if ceiling >= MIN_AMPS else int(charger.max_amps or 0))
    # De sommen in de kop, "op vol vermogen" en "uiterlijk beginnen", rekenen
    # met wat paal en auto kunnen en niet met wat er op dit moment onder de
    # zekering past: dat is wat de klaar-tijdregel zelf ook doet (zie
    # `structural_ceiling`). Bij Van den Dam trok fase 3 op 04-09-2026 om 21:21
    # zestien ampère door het huis, en toen stond er "op vol vermogen 15 u 58 m
    # op 6 A, uiterlijk beginnen zaterdag 13:02" boven een plan dat om 09:00
    # begon. Het plafond van nu blijft wél gelden voor het uur waar we in
    # zitten; dat gaat via `amps` naar `schijven`.
    structureel = structural_ceiling(car, charger) or amps

    kwh = energy_needed_kwh(car)
    plan = Plan(
        deadline=klaar,
        latest_start=_latest_start(klaar, hours_needed(car, structureel)),
        kwh_needed=kwh,
        hours_needed=hours_needed(car, structureel),
        amps=structureel,
        estimated=forecast.estimated,
    )

    horizon = max((rij["end"] for rij in prices), default=None)
    alleen_zon = bool(prices) and einde is not None and horizon < einde
    alle = schijven(
        now, prices, grid, car, amps, begin, einde, tariff, forecast,
        ceiling_later=structureel, alleen_zon=alleen_zon,
    )
    plan.solar_only = alleen_zon
    if alleen_zon and klaar is not None:
        plan.note = (
            _prijzen_onbekend(window, klaar, now)
            + f". Tot die binnenkomen, meestal {_dagnaam(klaar - timedelta(days=1), now)} rond "
            "13:00, laadt hij alleen op je eigen zon; daarna plant hij de rest."
        )
    if not alle and alleen_zon:
        return plan
    if not alle:
        plan.note = (
            "Er zijn nog geen prijzen bekend, en er is ook geen vast bedrag "
            "ingevuld. Kijk de prijssensor na bij Installatie."
        )
        return plan
    if kwh is None:
        plan.note = (
            "Zonder accustand weet de coach niet hoeveel er nog in moet. Geef hem "
            "door, dan staat hier het plan."
        )
        return plan

    gekozen = goedkoopste(alle, kwh)
    genomen: dict[datetime, float] = {}
    for schijf, hoeveel in gekozen:
        genomen[schijf.start] = genomen.get(schijf.start, 0.0) + hoeveel

    # Eén regel per uur, want dat is hoe je het leest. Over de blokken en niet
    # over de schijven, want een uur waar helemaal geen schijf van bestaat is
    # juist het interessante geval: dat ligt voor je begintijd, en dat hoort er
    # met die reden bij te staan in plaats van gewoon te ontbreken.
    per_uur: dict[datetime, list[Schijf]] = {}
    for schijf in alle:
        per_uur.setdefault(schijf.start, []).append(schijf)

    blokken = prices or _vlakke_blokken(now, einde, tariff)
    grens = einde or (now + PLAN_HORIZON)
    for rij in blokken:
        if rij["end"] <= now or rij["start"] >= grens:
            continue
        start = rij["start"]
        schijven_hier = per_uur.get(start, [])
        laadt = genomen.get(start, 0.0) > SCHIJF_MINIMUM
        zonschijf = next((s for s in schijven_hier if s.solar), None)
        netschijf = next((s for s in schijven_hier if not s.solar), None)
        if laadt:
            if zonschijf is not None and netschijf is None:
                waarom = (
                    "wat zon, aangevuld tot de ondergrens van je paal"
                    if zonschijf.kind == "vloer"
                    else "je eigen zon is hier het goedkoopst"
                )
            else:
                waarom = "een van de goedkoopste manieren"
        elif begin is not None and rij["end"] <= begin:
            waarom = "voor je begintijd"
        elif not schijven_hier:
            waarom = "buiten je tijden"
        else:
            waarom = "duurder dan wat hij nodig heeft"

        # Het tempo over het deel van het blok dat nog komt: het uur waar we
        # in zitten is korter dan een uur.
        van = max(start, now)
        tot = min(rij["end"], grens)
        duur = max(0.0, (tot - van).total_seconds() / 3600.0)
        kwh_blok = genomen.get(start, 0.0)
        kw = kwh_blok / duur if duur > 0 else 0.0
        plan.blocks.append(
            Blok(
                start=start,
                end=rij["end"],
                price=rij["price"],
                charging=laadt,
                why=waarom,
                solar_kwh=zonschijf.zon_kwh if zonschijf is not None else 0.0,
                kwh=kwh_blok,
                amps=int(round(amps_for(kw * 1000.0, car.phases))) if laadt else 0,
                kw=round(kw, 2) if laadt else 0.0,
            )
        )

    geladen = [blok for blok in plan.blocks if blok.charging]
    plan.expected_done = geladen[-1].end if geladen else None
    plan.planned_kwh = sum(genomen.values())
    if not plan.blocks:
        plan.note = "Er is niets te plannen voor deze periode."
    return plan



def price_now(prices: list[dict], now: datetime) -> dict | None:
    """The slot `now` falls in."""
    for row in prices:
        if row["start"] <= now < row["end"]:
            return row
    return None


def _euro(value: float) -> str:
    """A price the way the panel writes it."""
    return f"€ {value:.3f}".replace(".", ",")


def _clock(moment: datetime) -> str:
    return moment.strftime("%H:%M")


DAGNAMEN = ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag")


def _dagnaam(moment: datetime, now: datetime) -> str:
    """Vandaag, morgen, of de naam van de dag."""
    verschil = (moment.date() - now.date()).days
    if verschil <= 0:
        return "vandaag"
    if verschil == 1:
        return "morgen"
    return DAGNAMEN[moment.weekday()]


def _wanneer(moment: datetime, now: datetime) -> str:
    """Een tijdstip zoals je het op de kaart leest: "06:00", of "zondag 06:00".

    Vandaag en morgen krijgen alleen de klok, want "06:00" leest vanzelf als
    de eerstvolgende zes uur. Verder weg hoort de dag erbij. Op vrijdagavond
    04-09-2026 stond er bij Van den Dam "de prijzen tot 06:00 zijn nog niet
    bekend" terwijl zaterdag uit stond en de klaar-tijd zondag was; de prijzen
    van zaterdag 06:00 waren er wel, en Sven las het als een fout.
    """
    if (moment.date() - now.date()).days <= 1:
        return _clock(moment)
    return f"{DAGNAMEN[moment.weekday()]} {_clock(moment)}"


def _prijzen_komen(end: datetime | None, now: datetime) -> str:
    """Wanneer de prijzen tot de klaar-tijd er zijn: de middag ervoor."""
    if end is None:
        return "Plant de rest zodra de prijzen er zijn, meestal rond 13:00."
    # De prijzen van een dag komen de middag ervoor. Een klaar-tijd van
    # zondag 06:00 valt in de dag die zaterdag 13:00 bekend wordt.
    dag = _dagnaam(end - timedelta(days=1), now)
    return f"Plant de rest zodra de prijzen er zijn, meestal {dag} rond 13:00."


def _prijzen_onbekend(window: Window, end: datetime, now: datetime) -> str:
    """Het begin van de wachtzin: tot wanneer de prijzen ontbreken, en waarom
    de klaar-tijd zo ver weg ligt als er dagen uit staan.

    Met een uitgezette dag: "Zaterdag staat in je schema uit, dus hij moet
    zondag om 06:00 vol zijn. De prijzen tot dan zijn nog niet bekend". Zonder:
    "De prijzen tot zondag 06:00 zijn nog niet bekend". Niet twee keer "zondag
    06:00" in één adem.
    """
    uitleg = _uitgezet(window, now)
    if uitleg:
        return uitleg + "De prijzen tot dan zijn nog niet bekend"
    return f"De prijzen tot {_wanneer(end, now)} zijn nog niet bekend"


def _uitgezet(window: Window, now: datetime) -> str:
    """Waarom de klaar-tijd zo ver weg ligt, als er dagen uit staan."""
    if not window.skipped or window.deadline is None:
        return ""
    dagen = list(window.skipped)
    if len(dagen) == 1:
        welke = dagen[0].capitalize()
        staat = "staat"
    else:
        welke = (", ".join(dagen[:-1]) + " en " + dagen[-1]).capitalize()
        staat = "staan"
    return (
        f"{welke} {staat} in je schema uit, dus hij moet "
        f"{_dagnaam(window.deadline, now)} om {_clock(window.deadline)} vol zijn. "
    )


# Hoeveel tijd er bovenop de laadtijd over moet blijven voordat de coach het
# nog verantwoord vindt om te wachten. Onder deze speling gaat hij door tot de
# auto vol is. Staat hier met een naam omdat zowel de regel als de tekst op de
# kaart hem gebruikt, en die twee mogen nooit uit elkaar lopen.
#
# Een uur, altijd. Sven op 04-09-2026: "De eindtijd is heel belangrijk. Een
# uur daarvoor moet hij altijd klaar zijn." Daarvoor was het een half uur 's
# nachts en een uur overdag, en daarvoor een kwartier; elk van die getallen was
# te krap voor wat er in de praktijk tussen komt: een auto die niet meteen
# opstart, een lastbewaker die knijpt, een integratie die even wegvalt.
#
# Dit ene getal doet twee dingen die bij elkaar horen. Het plan (`schijven`)
# eindigt een uur vóór de klaar-tijd, dus de coach rekent nooit op het laatste
# uur. En de klaar-tijdregel grijpt in zodra er minder dan dit uur over is
# bovenop wat er nog nodig is. Zo kunnen die twee elkaar niet tegenspreken;
# toen het plan tot de klaar-tijd liep en de regel een half uur eiste, stopte
# de coach om 00:13 voor een goedkoper uur en zette de regel hem om 00:17 weer
# aan.
DEADLINE_SLACK_HOURS = 1.0

# Wanneer het huis tot rust komt. Bij een vast contract kost elk uur hetzelfde,
# dus zodra de zon niets meer oplevert is er niets om nog langer op te wachten.
# Wachten tot het laatste moment dat nog past levert dan geen cent op en laat
# een kwartier speling over, en dat is te weinig. Acht uur 's avonds is de tijd
# waarop koken, wassen en douchen achter de rug zijn, dus dan belast het laden
# de aansluiting ook het minst. Sven op 20-08-2026.
EVENING_START = time(20, 0)

# En wanneer die avondpiek begint. Tussen deze twee tijden komt er bij geen
# enkel contract iets van het net bij, ook niet bij een dynamisch contract
# waar de som het toch al zelden zou kiezen. Sven op 04-09-2026, over een auto
# die om tien uur 's ochtends aan de kabel gaat: "dan ergens stoppen voor de
# avondpiek, want we hadden gezegd dat hij pas na 20 uur weer mag laden." De
# klaar-tijdregel staat hier nog boven: past het anders niet meer, dan laadt
# hij. Zon blijft in de avondpiek gewoon beschikbaar, want die belast de
# aansluiting niet. Vijf uur is een aanname van mij en geen meting; Sven kan
# hem verzetten.
EVENING_PEAK_START = time(17, 0)


def in_evening_peak(moment: datetime) -> bool:
    """Of dit blok in de avondpiek valt."""
    return EVENING_PEAK_START <= moment.time() < EVENING_START

# Hoe lang een klaar-tijd na die avond nog mag liggen om er nog bij te horen.
# Meer dan een halve dag betekent dat er een hele daglichtperiode tussen zit, en
# dan is er wel degelijk zon om op te wachten en gaat de avondregel niet op.
EVENING_NIGHT_HOURS = 12


def _slack_hours(end: datetime | None) -> float:
    """Hoeveel speling deze klaar-tijd krijgt: een uur, zie `DEADLINE_SLACK_HOURS`.

    Tot 04-09-2026 hing dit af van of er een avond bij de klaar-tijd hoorde.
    Sven wil het overal hetzelfde, en de functie blijft staan omdat elke plek
    die met de klaar-tijd rekent hierlangs hoort te gaan en niet langs het getal.
    """
    return DEADLINE_SLACK_HOURS


def plan_end(end: datetime | None) -> datetime | None:
    """Het moment waarop het plan af hoort te zijn: de klaar-tijd min de speling.

    Alles wat vooruit plant rekent hiermee en niet met de klaar-tijd zelf. Het
    laatste uur is van de bewoner, niet van de coach.
    """
    if end is None:
        return None
    return end - timedelta(hours=_slack_hours(end))


def _latest_start(end: datetime | None, needed: float | None) -> datetime | None:
    """Het moment waarop de coach uiterlijk begint om op tijd vol te zijn."""
    if end is None or needed is None:
        return None
    return end - timedelta(hours=needed + _slack_hours(end))


def _evening_before(end: datetime | None) -> datetime | None:
    """De avond die hoort bij deze klaar-tijd, of niets als die er niet is.

    De laatste acht uur 's avonds vóór de klaar-tijd, en alleen als die
    klaar-tijd in dezelfde nacht valt. Klaar om zes uur 's ochtends hoort bij de
    avond ervoor; klaar om zeven uur 's avonds hoort bij niets, want tussen die
    twee ligt een hele dag zon.
    """
    if end is None:
        return None
    avond = _at(end, EVENING_START)
    if avond is None:
        return None
    if avond >= end:
        avond -= timedelta(days=1)
    if (end - avond) > timedelta(hours=EVENING_NIGHT_HOURS):
        return None
    return avond


def _hold_until_start(now: datetime, end: datetime | None, needed: float | None) -> int:
    """Hoe lang een pauze mag staan als de coach zelf zou wegvallen.

    Dit is het vangnet voor het geval dat Home Assistant niet meer terugkomt.
    Een 0 in de laadpaal met een houdbaarheid blijft precies zo lang staan als
    hier staat; daarna valt de paal terug op zijn eigen maximum en laadt de auto
    gewoon door.

    Laten aflopen op de klaar-tijd zou daarom fout zijn: dan begint de auto pas
    te laden op het moment dat hij vol had moeten zijn. Het hoort af te lopen op
    het laatste moment dat nog past, want dat is precies wanneer de coach zelf
    zou zijn begonnen als hij er nog was geweest.
    """
    if end is None:
        return MIN_HOLD_MINUTES
    laatste = _latest_start(end, needed) or end
    return _hold_until(now, laatste)


def _hold_until(now: datetime, moment: datetime | None) -> int:
    """Hoeveel minuten een pauze mee moet gaan om tot `moment` te reiken.

    Binnen de grenzen die een laadpaal aanneemt. Zonder moment wordt het de
    ondergrens: dan is er geen plan om op te wachten en is een korte pauze die
    elke ronde opnieuw beoordeeld wordt eerlijker dan een lange die niemand
    onderbouwd heeft.
    """
    if moment is None:
        return MIN_HOLD_MINUTES
    minuten = int((moment - now).total_seconds() // 60)
    return max(MIN_HOLD_MINUTES, min(MAX_HOLD_MINUTES, minuten))


# --- The decision ---------------------------------------------------------


def decide(
    now: datetime,
    prices: list[dict],
    grid: Grid,
    car: Car,
    charger: Charger,
    window: Window,
    tariff: Tariff = Tariff(),
    sun: Sun = Sun(),
    forecast: Forecast = Forecast(),
    holding: int = 0,
    waking: bool = False,
    asking_seconds: float = 0.0,
    must_finish: bool = False,
    overdue: bool = False,
) -> Decision:
    """What to do with this charging point, and how to say it.

    The rules are in `_decide`. What happens here is the last word about them:
    a load balancer on the connection can overrule the coach without asking, and
    when it does, the customer should read that rather than a plan that is not
    being carried out.

    En hier staat ook het omgekeerde: een lopende sessie wordt niet meteen
    afgebroken als de ladder van gedachten verandert. Dat is met opzet geen
    sport in de ladder maar een filter erna, want het gaat over de vraag óf er
    gestopt wordt en niet over hoe hard er geladen wordt. Toen het wel een sport
    was, greep hij bij een verse zonnesessie het volle plafond en werd er tien
    minuten lang bijgekocht terwijl het dak vol zon lag.

    `holding` is hoeveel ronden er al tegen de ladder in wordt doorgeladen; de
    laag die de sensoren leest houdt dat bij. `waking` en `asking_seconds` gaan
    over hetzelfde soort geheugen: of de wekpoging van deze sessie nog openstaat,
    en hoe lang de coach al stroom aanbiedt zonder dat de auto iets afneemt.

    Note what is *not* done here. The coach never withdraws its request when it
    is being held back. It keeps asking, because the balancer works on the
    lowest of all the limits and the moment it lets go, the request has to be
    standing already. Lowering it would mean charging slowly for another minute
    for no reason at all.
    """
    decision = _decide(
        now, prices, grid, car, charger, window, tariff, sun, forecast,
        must_finish, overdue,
    )

    if not decision.charge:
        return _keep_alive(now, grid, car, charger, decision, holding)

    if charger.paused_by_balancer:
        return Decision(
            True,
            decision.amps,
            "De lastbewaking van je aansluiting heeft het laden stilgelegd. "
            "Zodra er ruimte is, gaat hij vanzelf verder.",
            plan=decision.plan,
            rule="balancer-paused",
        )

    if held_back(charger) and charger.charging and charger.actual_amps > 0:
        # Zegt de bewaker zélf dat hij ruimer staat dan de coach vraagt, dan kan
        # hij niet degene zijn die knijpt en is de reden die de paal meldt ouder
        # dan het getal ernaast. Zwijgen is dan beter dan een zin met twee
        # getallen die elkaar tegenspreken.
        #
        # Sven op 30-08-2026, tijdens een herstart: "de equalizer staat op 18 A
        # maar de coach zegt dat de lastbewaking op 7 A zit?" Allebei waar en
        # toch onzin. De 7 was de gemeten stroom van dat moment; de reden
        # `limited_by_equalizer` kwam van een sensor die er vijf minuten over
        # deed om bij te werken. Dezelfde fout als bij de fasemeting: twee
        # metingen uit twee momenten in één zin.
        #
        # Alleen voor de redenen die over de bewaker gaan. Een groep die vol
        # zit is iets anders en daar zegt die sensor niets over.
        vrij = beschikbaar_van_bewaker(grid)
        zwijgen = (
            charger.no_current_reason in BALANCER_REASONS
            and vrij is not None
            and vrij >= decision.amps
        )
        held = int(charger.actual_amps)
        if not zwijgen and held < decision.amps - STEP_AMPS:
            return Decision(
                True,
                decision.amps,
                f"De lastbewaking houdt het laden op {held} A, want je aansluiting "
                f"zit vol. De coach vraagt {decision.amps} A en pakt die zodra het kan.",
                plan=decision.plan,
                rule=f"{decision.rule}+held-back",
                needs_soc=decision.needs_soc,
            )

    if charger.connected and not charger.charging:
        return _wake(grid, car, charger, decision, waking, asking_seconds)

    return decision


def _wake(
    grid: Grid,
    car: Car,
    charger: Charger,
    decision: Decision,
    waking: bool,
    asking_seconds: float,
) -> Decision:
    """De auto staat stil terwijl de coach stroom aanbiedt.

    Twee dingen horen daarbij, en ze volgen op elkaar. Eerst één ronde een
    ruimer aanbod, want een aantal auto's wordt niet wakker van het minimum.
    Werkt dat niet, dan hoort de kaart dat te zeggen in plaats van te beloven
    dat er met de zon wordt meegelopen terwijl er nul watt loopt.
    """
    if waking:
        amps = min(ceiling_amps(grid, car, charger), max(decision.amps, WAKE_AMPS))
        if amps > decision.amps:
            return Decision(
                True,
                amps,
                f"De auto is nog niet begonnen, dus hij biedt even {amps} A aan om hem "
                "wakker te maken.",
                plan="Zakt terug naar het zuinige tempo zodra de auto laadt.",
                rule=f"{decision.rule}+wake",
                holding=decision.holding,
                needs_soc=decision.needs_soc,
            )

    # Hier komt alleen een besluit om te laden langs, want een besluit om niet te
    # laden is hierboven al afgehandeld.
    if asking_seconds >= WAITING_SECONDS:
        # Een paal die op goedkeuring staat te wachten is iets anders dan een
        # auto die niets afneemt, en het advies eronder verschilt ook: bij het
        # eerste valt er in de auto niets na te kijken. De coach blijft het in
        # allebei de gevallen elke ronde opnieuw proberen, want juist dat kreeg
        # de paal bij Van den Dam op 29-08-2026 alsnog aan de praat; alleen de
        # tekst stuurde je toen de verkeerde kant op.
        if charger.no_current_reason in AUTHORISATION_REASONS:
            return Decision(
                True,
                decision.amps,
                f"De paal wacht op goedkeuring en biedt nog niets aan. Hij vraagt "
                f"om {decision.amps} A zodra hij mag.",
                plan="De coach blijft het proberen. Staat de paal op privé, dan "
                     "hoort hij dit zelf goed te keuren.",
                rule=f"{decision.rule}+waiting-for-auth",
                holding=decision.holding,
                needs_soc=decision.needs_soc,
            )
        return Decision(
            True,
            decision.amps,
            f"De paal biedt {decision.amps} A aan, maar de auto neemt nog niets af.",
            plan="Kijk of het laden in de auto zelf is uitgesteld of geblokkeerd.",
            rule=f"{decision.rule}+waiting-for-car",
            holding=decision.holding,
            needs_soc=decision.needs_soc,
        )

    return decision


def _decide(
    now: datetime,
    prices: list[dict],
    grid: Grid,
    car: Car,
    charger: Charger,
    window: Window,
    tariff: Tariff = Tariff(),
    sun: Sun = Sun(),
    forecast: Forecast = Forecast(),
    must_finish: bool = False,
    overdue: bool = False,
) -> Decision:
    """What to do with this charging point, this minute.

    Eerst een handvol sporten die niet over geld gaan, want die overrulen elke
    som. Ze staan in volgorde en de eerste die past wint, en juist dat maakt de
    uitkomst uit te leggen: er is altijd precies één reden.

    1. Geen kabel, niets te beslissen.
    2. De auto is vol.
    3. De bewoner heeft zelf gepauzeerd.
    4. De aansluiting zit vol.
    5. Snelladen: de bewoner weet iets wat de coach niet weet.
    6. Een gast laadt meteen.
    7. Voor de begintijd blijft hij eraf.
    8. De klaar-tijd komt in gevaar, of is al voorbij.

    En daaronder geen sporten meer maar één vergelijking: alle manieren om de
    resterende kilowattuur binnen te krijgen, van goedkoop naar duur. Zie
    `schijven` en `goedkoopste`.

    Boven alles staat het plafond, dus geen enkele uitkomst kan meer vragen dan
    de zekering, de paal of de auto toestaat.
    """
    ceiling = ceiling_amps(grid, car, charger)

    if not charger.connected:
        return Decision(False, 0, "Er hangt geen auto aan de lader.", rule="disconnected")

    if charger.complete:
        # Er hangt nog een kabel, maar de auto neemt niets meer af. Zonder deze
        # sport viel dat door naar de zon- of prijsregel en stond er op de kaart
        # dat dit het goedkoopste moment is om te laden, terwijl er niets
        # gebeurde. Dat ondermijnt precies het vertrouwen dat één reden per
        # besluit moet opbouwen.
        return Decision(
            False,
            0,
            "De auto is vol."
            if car.soc_percent is None or car.soc_percent >= FULL_PERCENT
            else (
                f"De auto laadt niet verder en staat op {int(car.soc_percent)}%. "
                "Mogelijk staat er een laadgrens in de auto."
            ),
            rule="complete",
            hold_minutes=MIN_HOLD_MINUTES,
        )

    # Wat de accustand zegt telt net zo goed als wat de paal zegt. Een auto op
    # 100% hoeft niets meer, en zonder deze sport viel dat door naar de
    # prijsregel: die pakt bij "niets nodig" alle uren als goedkoop en zet dus
    # vol vermogen op een auto die niets meer aanneemt.
    rest = energy_needed_kwh(car)
    if rest is not None and rest <= 0:
        return Decision(
            False,
            0,
            "De auto is vol volgens zijn accustand.",
            rule="complete",
            hold_minutes=MIN_HOLD_MINUTES,
        )

    if charger.paused_by_user:
        # Een pauze is een opdracht en geen advies, dus die blijft staan. Maar
        # als hij de klaar-tijd gaat kosten, hoort dat er wel bij te staan: hij
        # is de enige die de auto morgen leeg kan laten staan zonder dat er iets
        # kapot is.
        eind = window.deadline if window.enabled else None
        tempo = charging_pace(now, charger, ceiling)
        uren = hours_needed(car, tempo)
        if uren is None:
            uren = hours_needed(car, tempo, assume_empty=True)
        krap = bool(
            eind
            and uren is not None
            and (eind - now).total_seconds() / 3600 - uren <= _slack_hours(eind)
        )
        return Decision(
            False,
            0,
            "Je hebt het laden zelf gepauzeerd."
            + (
                f" Zo haalt de auto {_clock(eind)} niet meer: hervat het laden of "
                "verzet je klaar-tijd."
                if krap
                else ""
            ),
            plan="Blijft stilstaan tot je het hervat of de kabel eruit gaat.",
            rule="user-hold",
            deadline_risk=krap,
        )

    if ceiling < MIN_AMPS:
        # Een auto die al laadt gaat niet uit voor de marge alleen. Zie
        # `nood_ruimte` voor waarom dat onderscheid er is.
        # En alleen als het de marge onder de zekering is die knijpt. Zegt de
        # lastbewaker zelf dat er niets meer in kan, of kan de paal of de auto
        # niet lager, dan valt er niets aan te houden.
        bewaker = beschikbaar_van_bewaker(grid)
        if (
            charger.charging
            and nood_ruimte(grid, charger) >= MIN_AMPS
            and (bewaker is None or bewaker >= MIN_AMPS)
        ):
            return Decision(
                True,
                MIN_AMPS,
                "Je aansluiting zit bijna vol, dus hij laadt door op de laagste stand.",
                plan="Gaat weer omhoog zodra er ruimte is.",
                rule="tight",
            )
        return Decision(
            False,
            0,
            "Je aansluiting is te zwaar belast om te laden. Zodra er ruimte is, gaat hij verder.",
            rule="no-room",
        )

    if charger.boost:
        # Boven de prijs en boven het schema, want de bewoner weet iets wat de
        # coach niet weet: dat hij zo weg moet. Wel onder de zekering, want die
        # weet iets wat de bewoner niet weet.
        return Decision(
            True,
            ceiling,
            (
                f"Snelladen staat aan, dus hij laadt op {ceiling} A. Meer past er nu "
                "niet onder je zekering. Zodra je huis minder vraagt, gaat hij omhoog."
                if fuse_limited(grid, car, charger)
                else f"Snelladen staat aan, dus hij laadt op {ceiling} A, ongeacht de prijs."
            ),
            plan="Blijft op vol vermogen tot je het uitzet of de kabel eruit gaat.",
            rule="boost",
        )

    if car.guest:
        return Decision(
            True,
            ceiling,
            "Er hangt een gast aan de lader, dus die laadt meteen.",
            plan="Laadt door tot de kabel eruit gaat.",
            rule="guest",
        )

    start = window.opens if window.enabled else None
    end = window.deadline if window.enabled else None
    # Alles wat vooruit plant mikt een uur vóór de klaar-tijd. De regels die
    # over de klaar-tijd zelf gaan rekenen hieronder met `end`.
    einde_plan = plan_end(end)

    if window.enabled and start and now < start:
        return Decision(
            False,
            0,
            f"Laden mag vanaf {_clock(start)}.",
            plan=f"Begint na {_clock(start)}, op het goedkoopste moment dat past.",
            rule="too-early",
            hold_minutes=_hold_until(now, start),
        )

    # De bewoner heeft gezegd: op deze tijd begint hij, wat het ook kost. Dat is
    # een afspraak en geen som, dus die staat boven de vergelijking en niet erin.
    # Onder de zekering en onder een eigen pauze, want die gaan nog steeds voor.
    if (
        window.enabled
        and window.start_by is not None
        and now >= window.start_by
        and (window.deadline is None or now < window.deadline)
    ):
        return Decision(
            True,
            ceiling,
            f"Je hebt ingesteld dat hij uiterlijk om {_clock(window.start_by)} "
            "begint, dus hij laadt nu.",
            plan="Laadt door tot de auto vol is.",
            rule="start-by",
        )

    # --- the deadline outranks everything ---------------------------------
    # Reckoned with what the charger really manages, not with what it is about
    # to be asked for. Being held back by a load balancer makes charging take
    # longer, and the only sound answer to that is to begin sooner.
    #
    # Weet niemand hoe vol de auto is, dan wordt er gerekend alsof hij leeg is.
    # Dat verandert niets aan de volgorde van de ladder en het is geen reden om
    # eerder te gaan laden; het levert alleen een uiterste startmoment op, zodat
    # een vergeten accustand nooit een lege auto oplevert. Elke sport die
    # hieronder staat weet dat het een aanname is en zegt dat ook.
    # Het tempo waarmee de klaar-tijdsom rekent is wat paal en auto kunnen,
    # niet het plafond van deze minuut: een lastbewaker die even knijpt of een
    # oven die even aanstaat zegt niets over de uren die nog komen. Wat de paal
    # werkelijk trekt telt wel mee, zie `charging_pace`.
    structureel = structural_ceiling(car, charger)
    pace = charging_pace(now, charger, structureel)
    needed = hours_needed(car, pace)
    soc_unknown = needed is None
    if soc_unknown:
        needed = hours_needed(car, pace, assume_empty=True)

    # De klaar-tijd is verstreken en de auto is niet vol. Dan is er niets meer te
    # plannen: de afspraak is al gebroken en het enige dat nog telt is dat hij vol
    # raakt. Sven op 18-08-2026: "de auto moet wel vol zitten, dat wint altijd. De
    # coach plant alleen in om geld te besparen."
    #
    # Dit staat bewust onder de pauze, snelladen en de zekering: een opdracht van
    # de bewoner en de veiligheid van de aansluiting gaan hier nog steeds voor.
    if overdue:
        return Decision(
            True,
            ceiling,
            "De klaar-tijd is voorbij en de auto is nog niet vol, dus hij laadt door.",
            plan="Blijft op vol vermogen tot de auto vol is.",
            rule="overdue",
        )

    # `must_finish` betekent: deze sessie is al eerder tegen de klaar-tijd
    # aangelopen en blijft daarom op vol vermogen. Zonder dat sloeg hij elke
    # minuut om, en dat is geen theorie: op 18-08-2026 wisselde hij twintig
    # minuten lang om de minuut tussen 14 en 6 A.
    #
    # De oorzaak is een kringetje. Op vol vermogen meet de coach een snel tempo,
    # dus lijkt er tijd zat en valt hij terug op de zonregel; op 6 A meet hij een
    # traag tempo, dus lijkt de klaar-tijd in gevaar en gaat hij weer vol. Beide
    # metingen kloppen, en juist daarom is het antwoord niet nog een som maar een
    # besluit dat blijft staan: wie op het laatste moment begonnen is, kan niet
    # halverwege gas terugnemen zonder alsnog te laat te zijn.
    if window.enabled and end and needed is not None:
        slack = (end - now).total_seconds() / 3600 - needed
        if slack <= _slack_hours(end) or must_finish:
            return Decision(
                True,
                ceiling,
                (
                    f"Je hebt niet doorgegeven hoe vol de auto is, dus hij gaat uit "
                    f"van een lege accu en laadt nu door om {_wanneer(end, now)} te halen."
                    if soc_unknown
                    else f"Nu doorladen, anders is de auto om {_wanneer(end, now)} niet vol."
                ),
                plan="Laadt op vol vermogen tot de auto klaar is.",
                rule="deadline",
                needs_soc=soc_unknown,
            )

    # --- alle manieren tegen elkaar ---------------------------------------
    #
    # Hieronder stond een ladder: eerst de zon, dan wachten-op-zon, dan de
    # avondregel, dan het goedkope uur, dan wachten-op-prijs. Elke sport gaf
    # voor zich een verdedigbaar antwoord en ze zijn stuk voor stuk uit een
    # echte waarneming ontstaan. Maar ze vergeleken niets met elkaar: welke
    # sport won hing af van de volgorde en niet van wat het goedkoopst was.
    #
    # Op 30-08-2026 om 13:06 kwam dat eruit. De zonsport stond boven de
    # prijssport, dus 0,7 kW zon nam een uur over dat de prijssport net op vol
    # vermogen had gezet: 6 A waar 16 A hoorde. Sven daarop: "het eindoel is
    # altijd lage kosten, dus alle scenario's moeten vergeleken worden met
    # elkaar."
    #
    # Dat is wat hier gebeurt. Zie `schijven` voor de opzet en `goedkoopste`
    # voor waarom van goedkoop naar duur vullen niet alleen redelijk maar
    # aantoonbaar optimaal is.
    nodig_kwh = energy_needed_kwh(car)

    # Zon die er nú is gaat er altijd in, ook als niemand weet hoe vol de auto
    # is. Dat was al zo en het blijft zo: gratis stroom benutten kan niet
    # verkeerd zijn, en de sport hieronder wacht juist omdat er ingekocht zou
    # worden. Zie `no-soc`.
    amps_zon = max(MIN_AMPS, min(ceiling, int(amps_for(grid.surplus_w, car.phases))))
    genoeg_zon = grid.surplus_w >= watts_for(MIN_AMPS, car.phases) * SURPLUS_SLACK

    if nodig_kwh is None:
        if genoeg_zon:
            hoeveel = f"{grid.surplus_w / 1000:.1f}".replace(".", ",")
            return Decision(
                True,
                amps_zon,
                f"Er is {hoeveel} kW zon over, dus die gaat nu in de auto.",
                plan="Loopt mee met wat de zon geeft.",
                rule="surplus",
                needs_soc=soc_unknown,
            )

        # --- niemand weet hoe vol de auto is -------------------------------
        #
        # Vanaf hier zou er stroom uit het net gekocht worden, en dat mag niet
        # op een aanname. Wachten kan alleen als er een klaar-tijd is om op
        # terug te vallen; die is er, want de klaar-tijdsport hierboven rekent
        # met een lege accu uit wanneer hij uiterlijk moet beginnen.
        if soc_unknown and needed is not None and window.enabled and end:
            return Decision(
                False,
                0,
                "Hij weet niet hoe vol de auto is, dus hij wacht met laden uit het "
                "net. Geef je accustand door, dan kiest hij het gunstigste moment.",
                plan=(
                    f"Begint hoe dan ook op tijd voor {_wanneer(end, now)}, uitgaand van "
                    "een lege accu."
                ),
                rule="no-soc",
                hold_minutes=_hold_until_start(now, end, needed),
                needs_soc=True,
            )

        # Geen accustand, geen capaciteit en geen klaar-tijd: dan is er niets om
        # mee te rekenen en is stilstaan erger dan duur laden.
        return Decision(
            True,
            ceiling,
            "Hij weet niet hoeveel er nog in moet, dus hij laadt gewoon binnen je "
            "tijden.",
            plan="Laadt tot de auto zelf stopt.",
            rule="fixed-tariff",
            needs_soc=soc_unknown,
        )

    # Reiken de bekende prijzen niet tot het einde van het plan, dan komt er tot
    # ze er zijn alleen zon in. Sven op 04-09-2026, over een zondag die in het
    # schema uitgevinkt is en een klaar-tijd op maandag 06:00: "dan moet hij
    # echt puur op zonne-energie laden totdat de prijzen ook bekend zijn." Geen
    # geschatte prijzen dus; die stonden hier een middag lang en zijn er weer
    # uit. De prijzen van morgen komen rond 13:00, en vanaf dat moment plant
    # hij de nacht gewoon. De klaar-tijdregel hierboven en `capaciteit_kwh`
    # blijven het vangnet.
    #
    # "Zon" is hier elk uur waarin het dak iets geeft, ook als dat te weinig is
    # om zonder net op te laden: de bijmenging tot de ondergrens hoort erbij,
    # tegen de bekende prijs van dat uur. Zie de vloer in `schijven`.
    horizon = max((rij["end"] for rij in prices), default=None)
    alleen_zon = bool(prices) and einde_plan is not None and horizon < einde_plan
    alle = schijven(
        now, prices, grid, car, ceiling, start, einde_plan, tariff, forecast,
        ceiling_later=structureel, alleen_zon=alleen_zon,
    )
    if not alle and alleen_zon:
        return Decision(
            False,
            0,
            _prijzen_onbekend(window, end, now)
            + ", dus tot die binnenkomen laadt hij alleen op je eigen zon, en die "
            "is er nu niet.",
            plan=_prijzen_komen(end, now),
            rule="wait-for-prices",
            hold_minutes=_hold_until_start(now, end, needed),
        )
    if not alle:
        # Geen prijzen en geen vast bedrag: dan weet de coach niet wat stroom
        # kost. Dat is geen vast contract maar een gat, en het hoort niet
        # stilletjes te lijken op een gewone beslissing.
        #
        # Is er een klaar-tijd en tijd genoeg, dan wacht hij, net als bij een
        # onbekende accustand: kopen zonder te weten wat het kost is precies
        # wat een dynamisch contract niet wil. Een prijssensor die bij het
        # inpluggen even niets zegt zette de auto anders meteen op vol vermogen,
        # en dat is wat Sven zag: "wanneer ik de auto inplugde ging hij gelijk
        # laden." Sinds 04-09-2026.
        if window.enabled and end and needed is not None:
            slack = (end - now).total_seconds() / 3600 - needed
            if slack > _slack_hours(end):
                return Decision(
                    False,
                    0,
                    "Er komen geen prijzen binnen, dus hij wacht met laden uit het "
                    "net. Controleer de prijssensor bij Installatie.",
                    plan=f"Begint hoe dan ook op tijd voor {_wanneer(end, now)}.",
                    rule="no-prices",
                    hold_minutes=_hold_until_start(now, end, needed),
                )
        return Decision(
            True,
            ceiling,
            "Er komen geen prijzen binnen, dus hij laadt gewoon binnen je tijden. "
            "Controleer de prijssensor bij Installatie.",
            plan="Laadt door tot de auto vol is.",
            rule="fixed-tariff",
        )

    # Past het niet meer in wat er nog aan uren over is, dan is er niets te
    # kiezen. Dit is dezelfde vraag als de klaar-tijdregel hierboven, maar dan
    # met wat het plan wél weet: dat de avondpiek dicht is en dat het plan een
    # uur vóór de klaar-tijd af moet zijn. Zonder deze regel rekende hij bij een
    # kabel om 17:00 alsof hij tot 23:00 vol vermogen had en wachtte hij tot
    # het te laat was.
    if end is not None and capaciteit_kwh(
        now, start, einde_plan, grid, car, structureel, forecast, vast=not prices
    ) < nodig_kwh:
        return Decision(
            True,
            ceiling,
            f"Wat er nog in moet past niet meer in de uren die overblijven, dus hij "
            f"laadt nu door om {_wanneer(end, now)} te halen.",
            plan="Laadt op vol vermogen tot de auto klaar is.",
            rule="deadline",
        )

    gekozen = goedkoopste(alle, nodig_kwh)
    nu_net = next(
        (s for s, _ in gekozen if not s.solar and s.start <= now < s.end), None
    )
    nu_zon = next((s for s, _ in gekozen if s.solar and s.start <= now < s.end), None)
    nu_vloer = nu_zon is not None and nu_zon.kind == "vloer"
    uren = _uren_van(gekozen)

    if nu_net is not None:
        # Dit uur zit met zijn netschijf in het plan, dus er is geen goedkopere
        # manier om deze kilowattuur binnen te krijgen.
        #
        # Hoe hard hangt af van of er iets te winnen is met haasten. Kosten alle
        # uren hetzelfde, dan levert vol vermogen geen cent op en is het
        # rustigste tempo dat de klaar-tijd nog haalt beter voor de aansluiting.
        # Sven op 20-08-2026, over de avond: "dan belast je het ook niet zo
        # veel." Verschillen de uren wel, dan is elk uur dat je in een goedkoop
        # blok wegneemt er een die je duurder terugkrijgt, en gaat hij vol.
        netschijven = [schijf for schijf in alle if not schijf.solar]
        prijzen = {round(schijf.price, 6) for schijf in netschijven}
        vlak = len(prijzen) == 1
        amps = ceiling
        if vlak:
            # Hoeveel uur er nog van het net te laden valt. Uit de inhoud van
            # de schijven en niet uit hun begin- en eindtijd, want die zijn
            # van het hele uurblok, ook voor het blok waar we nu middenin
            # zitten. Op de tijden gerekend telde 00:52 nog als een vol uur,
            # dus zakte het tempo door het uur heen van 8 naar 6 A en sprong
            # het op het hele uur weer op; het tekort dat zo opliep moest de
            # klaar-tijdregel om 05:20 met een sprint goedmaken. Gezien in het
            # virtuele huis op 04-09-2026.
            vermogen_kw = watts_for(ceiling, car.phases) / 1000.0
            beschikbaar = sum(schijf.kwh for schijf in netschijven) / vermogen_kw
            # De schijven lopen al tot een uur vóór de klaar-tijd (zie
            # `plan_end`), dus dit tempo is er een dat met dat uur speling
            # klaar is.
            if beschikbaar > 0:
                rustig = amps_for(nodig_kwh / beschikbaar * 1000.0, car.phases)
                # Naar boven afronden, want naar beneden is elke ronde net iets
                # te langzaam. Dat tekort stapelt op tot de klaar-tijdregel het
                # laatste uur op vol vermogen moet redden, en dan was het geen
                # rustig tempo maar een sprint met een aanloop. Gezien in het
                # virtuele huis op 04-09-2026: zeven uur op 8 en 9 A, en om
                # 04:01 alsnog naar 16 A.
                # Een tiende ampère is de nauwkeurigheid waarmee een paal een
                # limiet volgt; die hoort geen hele ampère extra te kosten.
                amps = max(MIN_AMPS, min(ceiling, math.ceil(rustig - 0.1)))
                # En niet elke minuut een ampère op en neer. De auto volgt de
                # limiet met een minuut vertraging, en een tempo dat elke ronde
                # opnieuw uit de meting komt, jaagt daar achteraan: 14, 15, 14,
                # 15, drieëndertig opdrachten in één uur naar de paal. Gezien in
                # het virtuele huis met Van den Dams cijfers op 04-09-2026.
                # Scheelt het nieuwe tempo één ampère met wat er al staat, dan
                # blijft staan wat er staat; naar boven afronden vangt de rest.
                # Twee ampère speling, want de slingering is er een van twee:
                # op 14 A loopt hij achter en zegt de som 16, op 16 A loopt hij
                # voor en zegt de som 14. Het tempo dat werkelijk klopt zit
                # ertussen, en dat haalt de afronding naar boven eruit.
                huidig = int(charger.limit_amps or 0)
                if (
                    charger.charging
                    and abs(amps - huidig) <= 2
                    and MIN_AMPS <= huidig <= ceiling
                ):
                    amps = huidig

        # Nooit langzamer dan het dak op dit moment geeft. Rustig aan doen is
        # goed voor de aansluiting, maar niet ten koste van zon die anders het
        # net op gaat: die is nu gratis en straks weg.
        if nu_zon is not None:
            amps = max(amps, amps_zon)

        if vlak and amps < ceiling:
            return Decision(
                True,
                amps,
                "Elk uur kost hetzelfde, dus haasten levert niets op. Hij laadt "
                f"rustig door en is op tijd klaar; zo belast hij je aansluiting "
                "het minst.",
                plan=_describe(uren),
                # Een eigen naam, want dit is niet "dit uur is goedkoop" maar
                # "alle uren zijn even duur". Op het scherm leest dat als een
                # coach die bewust rustig aan doet in plaats van een die niet
                # doorheeft dat hij harder kan.
                rule="easy-pace",
            )

        return Decision(
            True,
            amps,
            f"Dit uur kost {_euro(nu_net.price)} per kWh en dat is een van de "
            f"goedkoopste manieren om de {_kwh(nodig_kwh)} erin te krijgen.",
            plan=_describe(uren),
            rule="cheap-hour",
        )

    # Een beurt die loopt wordt niet afgebroken voor een verschil dat er niet is.
    # Wordt de auto voller, dan krimpt het plan mee en kan het uur waar hij net
    # in begon eruit vallen terwijl het praktisch evenveel kost als de uren die
    # overblijven. Bij Van den Dam scheelde dat op 30-08-2026 drie tienden van
    # een cent per kWh, en daarvoor ging de paal uit en straks weer aan. Een auto
    # stopt niet graag steeds; zie ook `MIN_RUN_MINUTES` en `_keep_alive`.
    if nu_net is None and charger.charging:
        netprijzen = [s.price for s, _ in gekozen if not s.solar]
        hier = next((s for s in alle if s.start <= now < s.end and not s.solar), None)
        if netprijzen and hier is not None and hier.price <= max(netprijzen) + STOP_MARGIN:
            return Decision(
                True,
                ceiling,
                f"Dit uur kost {_euro(hier.price)} per kWh en dat scheelt niets met "
                "de uren die hij gepland had, dus hij laadt door in plaats van te "
                "stoppen en zo weer te beginnen.",
                plan=_describe(uren),
                rule="cheap-hour+near",
            )

        # En hij stopt ook niet als de uren die overblijven maar nét genoeg
        # zijn. Een plan zonder reserve is een plan dat bij de eerste oven
        # omvalt: om 00:12 stopte hij voor een uur dat 0,6 cent goedkoper was,
        # om 01:00 zette de klaar-tijdregel hem weer aan, en toen om 02:00 de
        # oven aanging was de speling op en was hij om 05:18 vol in plaats van
        # om 05:00. Blijft er na dit uur minder dan een uur laden over aan
        # ruimte, dan laadt hij door. Gezien in het virtuele huis, 04-09-2026.
        if hier is not None and end is not None:
            later = sum(s.kwh for s in alle if s.start >= hier.end or s.solar)
            uur_kwh = watts_for(structureel, car.phases) / 1000.0
            if later - nodig_kwh < uur_kwh:
                return Decision(
                    True,
                    ceiling,
                    f"Dit uur kost {_euro(hier.price)} per kWh, iets meer dan de uren "
                    f"die hij gepland had, maar stoppen laat te weinig speling over "
                    f"voor {_wanneer(end, now)}. Dus hij laadt door.",
                    plan=_describe(uren),
                    rule="cheap-hour+reserve",
                )

    # Een lopende beurt op zon stopt evenmin voor een verschil dat er niet is.
    # Het uur waar hij in zit is dan net iets duurder dan het volgende zonuur,
    # bijvoorbeeld omdat de ochtend nog weinig geeft; dat is geen reden om de
    # auto uit te zetten en over een uur weer te wekken.
    if nu_zon is None and charger.charging:
        hier_zon = next((s for s in alle if s.solar and s.start <= now < s.end), None)
        duurste = max((s.price for s, _ in gekozen), default=None)
        if hier_zon is not None and duurste is not None and hier_zon.price <= duurste + STOP_MARGIN:
            hoeveel = f"{grid.surplus_w / 1000:.1f}".replace(".", ",")
            return Decision(
                True,
                MIN_AMPS if hier_zon.kind == "vloer" else amps_zon,
                f"Er is {hoeveel} kW zon over, en dit uur scheelt bijna niets met de "
                "uren die hij gepland had, dus hij laadt door in plaats van te stoppen "
                "en zo weer te beginnen.",
                plan=_describe(uren),
                rule="surplus+near",
            )

    if nu_zon is not None:
        # De zon van dit uur is goedkoop genoeg. Geeft het dak genoeg om er zelf
        # op te laden, dan loopt hij daarmee mee; geeft het minder, dan is de
        # ondergrens van de paal het antwoord en zit het bijkopen al in de prijs
        # waarop dit uur gekozen is.
        hoeveel = f"{grid.surplus_w / 1000:.1f}".replace(".", ",")
        return Decision(
            True,
            MIN_AMPS if nu_vloer else amps_zon,
            (
                f"Er is {hoeveel} kW zon over. Met de ondergrens van je paal erbij "
                "is dit uur goedkoper dan wachten op het net."
                if nu_vloer
                else f"Er is {hoeveel} kW zon over en die is goedkoper dan het net. "
                "De rest haalt hij op een uur dat minder kost."
            ),
            plan=_describe(uren),
            rule="surplus",
        )

    # Waarom hij wacht hangt af van wat er straks goedkoper is, en dat verschil
    # hoort op de kaart te staan. "Niet het goedkoopste moment" is bij een vast
    # tarief onzin: daar kost elk uur hetzelfde en wacht hij op de avond of op
    # de zon.
    begint = uren[0]["start"] if uren else None
    eerste = gekozen[0][0] if gekozen else None
    if alleen_zon:
        reden = (
            _prijzen_onbekend(window, end, now)
            + ", dus tot die binnenkomen laadt hij alleen op je eigen zon."
            + (f" De volgende zon verwacht hij om {_clock(begint)}." if begint else "")
        )
        regel = "wait-for-prices"
    elif begint is None:
        reden, regel = "Het is nu niet het goedkoopste moment om te laden.", "wait-for-price"
    elif eerste is not None and eerste.solar:
        reden = (
            f"Hij wacht op je eigen zon van {_clock(begint)}; die is goedkoper dan "
            "wat het net op dit moment kost."
        )
        regel = "wait-for-sun"
    elif not prices:
        reden = (
            f"Hij wacht tot {_clock(begint)}. Elk uur kost hetzelfde, en dan zijn "
            "de pieken van koken en wassen voorbij en belast het laden je "
            "aansluiting het minst."
        )
        regel = "wait-for-sun"
    else:
        reden = f"Stroom is straks goedkoper dan nu, dus hij wacht tot {_clock(begint)}."
        regel = "wait-for-price"

    return Decision(
        False,
        0,
        reden,
        plan=_describe(uren),
        rule=regel,
        # Tot het eerste uur dat hij van plan is te gebruiken. Verloopt de pauze
        # doordat de coach wegvalt, dan laadt de auto vanaf dat moment gewoon
        # door, en dat is precies het goede antwoord: duurder, maar wel vol.
        hold_minutes=_hold_until(now, begint),
    )

# Hoeveel beter het volgende uur moet zijn voordat wachten de moeite is. Onder
# deze verhouding is het verschil kleiner dan de onzekerheid van de verwachting
# zelf, en dan is een uur stilstaan puur verlies.
FORECAST_BETTER = 1.4


def _zon_dekt_vandaag(
    surplus_w: float,
    trekt_w: float,
    sun: Sun,
    car: Car,
    koop: float | None,
    terug: float | None,
    now: datetime,
    end: datetime | None,
    needed: float | None,
) -> bool:
    """Of de zon van vandaag alles nog dekt, zodat bijkopen nu zonde is.

    `_beter_straks` hierboven kijkt één uur vooruit en eist dat dat ene uur de
    laadstroom bijna helemaal dekt. Dat is te kort door de bocht voor een auto
    die er de hele dag over mag doen: om negen uur is een halve kilowatt zon
    genoeg om de coach te laten beginnen, waarna hij er drie kilowatt uit het net
    bij koopt terwijl diezelfde kilowatturen om één uur gratis van het dak waren
    gekomen. Sven op 25-08-2026: "zo goedkoop mogelijk".

    De som is die van de klant zelf. Komt er vandaag nog meer zon dan er in de
    auto moet, dan is elke kWh die hij nu bijkoopt een kWh die hij straks voor
    niets had gehad. Dan is wachten het goedkoopst. Blijft de zon achter bij wat
    er nog in moet, dan is het omgekeerde waar: dan is elke kWh die nu niet
    gebruikt wordt teruggeleverd voor een fractie van wat hij kost, en dan hoort
    hij te pakken wat er is, ook met bijkopen.

    Vier redenen om het niet te doen, en ze zijn er allemaal een van "dan valt er
    niets te winnen":

    Er wordt niet noemenswaardig bijgekocht. Dekt de zon het laden zo goed als
    helemaal, dan valt er niets te winnen. `SURPLUS_SLACK` is dezelfde marge
    waarmee hierboven bepaald wordt of het overschot genoeg is om op te laden:
    een lopende sessie stilzetten omdat er twintig watt bijgekocht wordt, kost
    meer dan het opbrengt.

    Eigen zon is niet meer waard dan teruglevering. Bij saldering krijg je voor
    een teruggeleverde kWh net zoveel als een gekochte kost, en dan maakt het
    niet uit of hij hem nu gebruikt of straks. `PRICE_MARGIN` is dezelfde
    ondergrens die de prijsvergelijking hierboven gebruikt.

    Er is geen klaar-tijd. Wachten mag alleen als er iets is om op terug te
    vallen; zonder afgesproken moment is er geen regel die hem alsnog aanzet.

    Er is geen verwachting, of de tijd is te krap. Zonder verwachting is er niets
    om op te wachten, en `_zon_verwacht` is dezelfde meetlat als bij het vaste
    contract: geen tweede definitie van "genoeg zon".
    """
    if surplus_w >= trekt_w * SURPLUS_SLACK:
        return False

    if koop is None or terug is None or koop - terug <= PRICE_MARGIN:
        return False

    if end is None or needed is None or not _zon_verwacht(sun, car):
        return False

    over = (end - now).total_seconds() / 3600
    return over >= needed + _slack_hours(end)


def _beter_straks(
    surplus_w: float,
    trekt_w: float,
    sun: Sun,
    now: datetime,
    end: datetime | None,
    needed: float | None,
) -> bool:
    """Of wachten op de zon van het volgende uur beter is dan nu bijkopen.

    Drie voorwaarden, en ze moeten alle drie kloppen.

    Er moet nu écht bijgekocht worden. Dekt de zon het al, dan valt er niets te
    winnen door te wachten; dan is laden nu al zo goedkoop als het wordt.

    Het volgende uur moet duidelijk beter zijn, niet een beetje. Een verwachting
    is geen meting, en een uur stilstaan voor tien procent meer zon is een uur
    stilstaan voor niets.

    En er moet tijd zijn. Een uur wachten mag de klaar-tijd niet in gevaar
    brengen, dus na dat uur moet er nog ruim genoeg over zijn om vol te laden.
    """
    if sun.next_w is None or surplus_w >= trekt_w:
        return False

    beter = sun.next_w >= max(surplus_w, sun.now_w or 0.0) * FORECAST_BETTER
    if not beter or sun.next_w < trekt_w * SURPLUS_SLACK:
        return False

    if end is not None and needed is not None:
        over = (end - now).total_seconds() / 3600 - 1.0
        if over < needed + _slack_hours(end):
            return False

    return True


# De uitkomsten waarbij een lopende sessie wél meteen mag stoppen. Drie ervan
# omdat er niets te beschermen valt, en één omdat wachten daar gevaarlijk is:
# een aansluiting die vol zit, zit vol.
# Regels waar een lopende beurt niet tegenin wordt vastgehouden. De laatste
# twee zijn Svens zesde eis, nooit blind laden: valt de prijssensor of de
# accustand weg, dan is elke minuut doorladen een minuut zonder te weten wat
# het kost of of het nog past. Met tien ronden uitstel was dat te veel.
NEVER_HOLD = frozenset(
    {"disconnected", "complete", "user-hold", "no-room", "tight", "no-prices", "no-soc"}
)


def _zon_verwacht(sun: Sun, car: Car) -> bool:
    """Of er vandaag genoeg zon aankomt om überhaupt op te wachten.

    Dit is een poortje en geen som. Zegt de verwachting dat er vandaag minder
    opgewekt wordt dan er nog in de auto moet, dan valt er niets te halen en is
    wachten alleen maar uitstel: dan kan hij net zo goed nu laden, op een moment
    dat de rest van het huis nog rustig is.

    Er wordt bewust niet geprobeerd te schatten hoeveel daarvan overblijft nadat
    het huis zijn deel heeft gehad. Dat zou een verzonnen getal zijn, en het is
    niet nodig: waar het echt om gaat, namelijk of de auto op tijd vol is, wordt
    door de klaar-tijd bewaakt en niet door deze schatting.

    **Zonder verwachting wordt er niet gewacht.** Wachten moet een reden hebben,
    en "ik weet het niet" is er geen. Wie geen zonverwachting heeft ingevuld
    houdt dus precies het gedrag dat hij gewend was. Dat scheelt bovendien een
    vervelend randgeval: 's nachts om twee uur is er niets om op te wachten, en
    dan is het beter om te laden terwijl het huis nog rustig is dan om tot het
    laatste moment te blijven staan.
    """
    if sun.remaining_kwh is None:
        return False
    nodig = energy_needed_kwh(car)
    return nodig is None or sun.remaining_kwh >= nodig


def _keep_alive(
    now: datetime,
    grid: Grid,
    car: Car,
    charger: Charger,
    decision: Decision,
    holding: int,
) -> Decision:
    """Een sessie die loopt niet meteen afbreken omdat de ladder omslaat.

    Twee redenen om door te laden, en ze staan naast elkaar.

    **Net begonnen.** Cars dislike being interrupted, and a few of them stop
    asking for current altogether after a handful of cycles.

    **Even geduld.** Daarna kon één meting een sessie afbreken die al een uur
    liep. Bij half bewolkt weer stopt en start hij dan om de paar minuten, en dat
    is precies het gedrag waar de minimale looptijd voor bedoeld was. Dus moet de
    ladder het een paar ronden achter elkaar volhouden voordat er echt gestopt
    wordt.

    **Op de laagste stand die kan.** Doorladen gebeurt hier niet om op te
    schieten maar om de sessie in leven te houden, en dan is het goedkoopste
    genoeg: wat het overschot draagt, met de ondergrens van de lader eronder.
    """
    if decision.rule in NEVER_HOLD:
        return decision
    if not charger.charging or charger.started_at is None:
        return decision

    net_begonnen = now - charger.started_at < timedelta(minutes=MIN_RUN_MINUTES)
    if not net_begonnen and holding >= STOP_ROUNDS:
        return decision

    ceiling = ceiling_amps(grid, car, charger)
    if ceiling < MIN_AMPS:
        return decision

    # In de avondpiek komt er niets van het net bij, ook niet om een sessie
    # in leven te houden: met tien minuten uitstel zou dat elke avond om 17:00
    # een kilowattuur uit de piek zijn. Draagt de zon de ondergrens, dan mag
    # het wel, want die belast de aansluiting niet.
    if in_evening_peak(now) and amps_for(grid.surplus_w, car.phases) < MIN_AMPS:
        return decision

    amps = max(MIN_AMPS, min(ceiling, int(amps_for(grid.surplus_w, car.phases))))
    reason = (
        "Net begonnen met laden, dus hij houdt het nog even vol op de laagste stand."
        if net_begonnen
        else "Hij laadt nog even door op de laagste stand. Een auto stopt niet graag steeds."
    )
    return Decision(
        True,
        amps,
        reason,
        plan=decision.plan,
        rule=f"{decision.rule}+hold",
        holding=True,
    )


def _describe(hours: list[dict]) -> str:
    """The plan in one sentence, or nothing when there is nothing to say."""
    if not hours:
        return ""

    first = hours[0]["start"]
    last = hours[-1]["end"]
    total = sum(row["price"] for row in hours) / len(hours)
    return (
        f"Van plan te laden tussen {_clock(first)} en {_clock(last)}, "
        f"gemiddeld {_euro(total)} per kWh."
    )


def should_send(previous: Decision | None, decision: Decision) -> bool:
    """Whether this decision is worth acting on at all.

    The dead band lives here rather than in the caller, so the rule that a
    charger is not re-commanded for a fraction of an amp is written down in one
    place. Starting and stopping always get through; only the size of a step is
    up for debate.
    """
    if previous is None:
        return True
    if previous.charge != decision.charge:
        return True
    if not decision.charge:
        return False
    return abs(previous.amps - decision.amps) >= STEP_AMPS
