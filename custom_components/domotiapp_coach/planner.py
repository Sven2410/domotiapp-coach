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
# gestopt wordt. Een wolk duurt een minuut of twee, en daarvoor hoort een sessie
# niet af te breken.
#
# Dit staat los van de minimale looptijd hierboven en dat is geen dubbelop. De
# minimale looptijd beschermt alleen het bégin van een sessie; daarna kon één
# meting een sessie afbreken die al een uur liep. Samen begrenzen ze ook meteen
# hoe vaak er geschakeld kan worden: tien minuten draaien plus drie minuten
# uitstel plus een ronde maakt veertien minuten per cyclus, dus hooguit vier per
# uur. Een aparte teller daarvoor zou een mechanisme zijn dat zijn werk al gedaan
# ziet.
STOP_ROUNDS = 3

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
    # Wanneer het klaar moet zijn.
    deadline: datetime | None = None


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
    """
    if not charger.charging or charger.limit_amps is None:
        return False
    return charger.limit_amps - grid.charger_amps > STEP_AMPS


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
    return max(grid.charger_amps, min(charger.limit_amps, zwaarste))


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
            ruimte = min(ruimte, charger.limit_amps)
        limits.append(ruimte)

    return int(max(0, min(limits)))


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


def held_back(charger: Charger) -> bool:
    """Whether something outside the coach is keeping this charger down."""
    return charger.no_current_reason in HELD_BACK_REASONS


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

    for offset in range(LOOKAHEAD_DAYS):
        basis = now + timedelta(days=offset)
        day = days.get(basis.weekday())
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

        return Window(enabled=True, opens=opens, deadline=deadline)

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


# Hoeveel tijd er bovenop de laadtijd over moet blijven voordat de coach het
# nog verantwoord vindt om te wachten. Onder dit kwartier gaat hij door tot de
# auto vol is. Staat hier met een naam omdat zowel de regel als de tekst op de
# kaart hem gebruikt, en die twee mogen nooit uit elkaar lopen.
DEADLINE_SLACK_HOURS = 0.25

# En hoeveel het er zijn bij een klaar-tijd overdag. Een kwartier is daar te
# krap, en dat komt doordat de avondregel hieronder er niet bij helpt: die zet
# een auto met een klaar-tijd 's nachts al om acht uur 's avonds aan, ruim voor
# het laatste moment dat nog past. Overdag is er geen avond die erbij hoort, en
# dan is dat kwartier het enige dat er tussen de auto en een gemiste afspraak
# staat. Svens eigen getal, gevraagd en gegeven op 26-08-2026.
DEADLINE_SLACK_DAY_HOURS = 1.0

# Wanneer het huis tot rust komt. Bij een vast contract kost elk uur hetzelfde,
# dus zodra de zon niets meer oplevert is er niets om nog langer op te wachten.
# Wachten tot het laatste moment dat nog past levert dan geen cent op en laat
# een kwartier speling over, en dat is te weinig. Acht uur 's avonds is de tijd
# waarop koken, wassen en douchen achter de rug zijn, dus dan belast het laden
# de aansluiting ook het minst. Sven op 20-08-2026.
EVENING_START = time(20, 0)

# Hoe lang een klaar-tijd na die avond nog mag liggen om er nog bij te horen.
# Meer dan een halve dag betekent dat er een hele daglichtperiode tussen zit, en
# dan is er wel degelijk zon om op te wachten en gaat de avondregel niet op.
EVENING_NIGHT_HOURS = 12


def _slack_hours(end: datetime | None) -> float:
    """Hoeveel speling deze klaar-tijd hoort te krijgen.

    Geen nieuw begrip: het hangt aan de avond die bij de klaar-tijd hoort, en
    dat is precies dezelfde vraag die `_evening_before` hieronder beantwoordt.
    Hoort er een avond bij, dan zet de avondregel de auto daar al aan en is een
    kwartier genoeg. Hoort er geen avond bij, dan staat er niets tussen de auto
    en een gemiste afspraak, en dan is het een uur.
    """
    if end is None:
        return DEADLINE_SLACK_HOURS
    return DEADLINE_SLACK_HOURS if _evening_before(end) else DEADLINE_SLACK_DAY_HOURS


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
    goal: str = "cost",
    tariff: Tariff = Tariff(),
    sun: Sun = Sun(),
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
        now, prices, grid, car, charger, window, goal, tariff, sun, must_finish, overdue
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
        held = int(charger.actual_amps)
        if held < decision.amps - STEP_AMPS:
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
    goal: str = "cost",
    tariff: Tariff = Tariff(),
    sun: Sun = Sun(),
    must_finish: bool = False,
    overdue: bool = False,
) -> Decision:
    """What to do with this charging point, this minute.

    The rules are tried in order and the first that fits wins, which is what
    makes the outcome explainable: there is always exactly one reason.

    1. No cable, nothing to decide.
    2. De auto is vol; er valt niets meer te kiezen.
    3. De bewoner heeft zelf gepauzeerd.
    4. De aansluiting zit vol.
    5. A guest charges, full stop.
    6. Outside the window the coach keeps its hands off.
    7. The deadline is close enough that waiting would miss it.
    8. There is surplus from the roof worth using.
    9. This hour is one of the cheap ones the plan picked.
    10. Otherwise: wait.

    Above all of them sits the ceiling, so no rule can ever ask for more than
    the fuse, the charger or the car allows.
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

    if window.enabled and start and now < start:
        return Decision(
            False,
            0,
            f"Laden mag vanaf {_clock(start)}.",
            plan=f"Begint na {_clock(start)}, op het goedkoopste moment dat past.",
            rule="too-early",
            hold_minutes=_hold_until(now, start),
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
    pace = charging_pace(now, charger, ceiling)
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
                    f"van een lege accu en laadt nu door om {_clock(end)} te halen."
                    if soc_unknown
                    else f"Nu doorladen, anders is de auto om {_clock(end)} niet vol."
                ),
                plan="Laadt op vol vermogen tot de auto klaar is.",
                rule="deadline",
                needs_soc=soc_unknown,
            )

    # --- eigen zon --------------------------------------------------------
    #
    # Twee manieren om hier te beslissen, en welke het wordt hangt af van wat er
    # bekend is. Kent de coach zowel de inkoopprijs als wat teruglevering
    # opbrengt, dan rekent hij het gewoon uit. Kent hij dat niet, dan valt hij
    # terug op de vuistregel: alleen laden als de zon het grotendeels zelf dekt.
    # Een verzonnen getal is hier erger dan een voorzichtige regel.
    #
    # De ondergrens hangt aan het mínste dat deze auto kan. Kan hij eenfasig,
    # dan is 1,4 kW al genoeg om te beginnen; eist de coach 4,1 kW omdat hij
    # voor de zekerheid van drie fasen uitgaat, dan blijft een halve
    # ochtendzon onbenut terwijl de auto er prima op had kunnen laden.
    amps = max(MIN_AMPS, min(ceiling, int(amps_for(grid.surplus_w, car.phases))))
    trekt = watts_for(amps, car.phases)
    genoeg_zon = grid.surplus_w >= watts_for(MIN_AMPS, car.phases) * SURPLUS_SLACK

    nu_prijs = price_now(prices, now)
    koop = nu_prijs["price"] if nu_prijs else tariff.buy
    terug = (nu_prijs or {}).get("feed_in")
    if terug is None:
        terug = tariff.feed_in

    if goal != "solar" and koop is not None and terug is not None:
        # De som die de klant zelf zou maken: wat kost een kWh in de auto als ik
        # nu op de zon laad, en is er straks een uur dat goedkoper is? Zonder die
        # vergelijking bleef een halve kilowatt zon liggen omdat er net niet
        # genoeg was om zonder bijkopen te draaien, terwijl een paar honderd watt
        # bijkopen goedkoper is dan een heel uur van het net.
        nu_kost = charge_cost(trekt, grid.surplus_w, koop, terug)
        straks = cheapest_price(prices, now, end)
        if straks is None:
            straks = tariff.buy if tariff.buy is not None else koop

        if nu_kost < straks - PRICE_MARGIN:
            # Nu laden kost minder dan wachten op een goedkoop uur. Maar er is
            # een derde mogelijkheid die geen van beide is: wachten op meer zon.
            # Moet er nu nog bijgekocht worden en zegt de verwachting dat het
            # volgende uur flink beter is, dan is een uur geduld de goedkoopste
            # zet van de drie. Alleen als de klaar-tijd dat toelaat, en die
            # regel staat hierboven al, dus als we hier komen is er tijd.
            if _beter_straks(grid.surplus_w, trekt, sun, now, end, needed):
                komt = f"{(sun.next_w or 0) / 1000:.1f}".replace(".", ",")
                return Decision(
                    False,
                    0,
                    f"Over een uur wordt er {komt} kW zon verwacht, dus dan is laden "
                    f"goedkoper dan er nu stroom bij te kopen.",
                    plan="Wacht op de zon die eraan komt.",
                    rule="wait-for-forecast",
                    hold_minutes=MIN_HOLD_MINUTES,
                )

            # En dezelfde vraag over de hele dag in plaats van over één uur.
            if _zon_dekt_vandaag(
                grid.surplus_w, trekt, sun, car, koop, terug, now, end, needed
            ):
                komt = f"{sun.remaining_kwh:.1f}".replace(".", ",")
                # Hoeveel er nog in moet weet hij lang niet altijd: `_zon_verwacht`
                # laat een onbekende accustand er bewust doorheen, want "ik weet
                # het niet" is geen reden om te laden. Dan noemt de zin dat getal
                # gewoon niet, in plaats van er een te verzinnen.
                nodig = energy_needed_kwh(car)
                # Wanneer hij uiterlijk begint hoort erbij, en dat is bij een
                # vast contract de avondregel en niet het allerlaatste moment
                # dat nog past. Zonder prijslijst is er geen goedkoop uur om op
                # te wachten, dus dan is acht uur 's avonds het antwoord.
                avond = _evening_before(end) if not prices else None
                momenten = [
                    m for m in (avond, _latest_start(end, needed)) if m and m > now
                ]
                begint = min(momenten) if momenten else None
                return Decision(
                    False,
                    0,
                    (
                        f"Er komt vandaag nog {komt} kWh zon en er moet er "
                        f"{f'{nodig:.1f}'.replace('.', ',')} in, dus daar wacht hij "
                        "op in plaats van stroom bij te kopen."
                        if nodig is not None
                        else f"Er komt vandaag nog {komt} kWh zon, dus daar wacht "
                        "hij op in plaats van nu stroom bij te kopen."
                    ),
                    plan=(
                        f"Begint zodra je dak genoeg geeft, uiterlijk om {_clock(begint)}."
                        if begint
                        else "Begint zodra je dak genoeg geeft."
                    ),
                    rule="wait-for-sun-today",
                    hold_minutes=MIN_HOLD_MINUTES,
                )

            dekt = grid.surplus_w >= trekt
            hoeveel = f"{grid.surplus_w / 1000:.1f}".replace(".", ",")
            uitleg = (
                f"Je levert {hoeveel} kW terug, dus die gaat nu in de auto"
                if dekt
                else f"Je levert {hoeveel} kW terug. Dat net aanvullen is goedkoper dan wachten"
            )
            return Decision(
                True,
                amps,
                f"{uitleg}: {_euro(nu_kost)} per kWh tegen {_euro(straks)} straks.",
                plan="Loopt mee met wat de zon geeft.",
                rule="surplus",
            )
    elif genoeg_zon:
        hoeveel = f"{grid.surplus_w / 1000:.1f}".replace(".", ",")
        return Decision(
            True,
            amps,
            f"Je levert {hoeveel} kW terug, dus die gaat nu in de auto.",
            plan="Loopt mee met wat de zon geeft.",
            rule="surplus",
        )

    if goal == "solar" and genoeg_zon:
        hoeveel = f"{grid.surplus_w / 1000:.1f}".replace(".", ",")
        return Decision(
            True,
            amps,
            f"Je levert {hoeveel} kW terug, dus die gaat nu in de auto.",
            plan="Loopt mee met wat de zon geeft.",
            rule="surplus",
        )


    if goal == "solar":
        return Decision(
            False,
            0,
            "Er is te weinig overschot om op te laden.",
            plan="Wacht op de zon; als de klaar-tijd in zicht komt, laadt hij alsnog.",
            rule="wait-for-sun",
            hold_minutes=MIN_HOLD_MINUTES,
        )

    # --- niemand weet hoe vol de auto is -----------------------------------
    #
    # Vanaf hier zou er stroom uit het net gekocht worden, en dat mag niet op
    # een aanname. Zon is iets anders: die staat hierboven en gaat er altijd in,
    # want gratis stroom benutten kan nooit verkeerd zijn.
    #
    # Wachten kan alleen als er een klaar-tijd is om op terug te vallen. Die is
    # er, want de sport hierboven rekent dan met een lege accu uit wanneer hij
    # uiterlijk moet beginnen. Zo staat er nooit een lege auto en wordt er toch
    # niets vroeg gekocht op een getal dat niemand heeft ingevuld.
    # `needed` staat hier op het slechtste geval; is dat None, dan is zelfs dat
    # niet te berekenen omdat de accucapaciteit ontbreekt. Dan is wachten geen
    # optie, want er is geen moment waarop hij alsnog zou beginnen.
    if soc_unknown and needed is not None and window.enabled and end:
        return Decision(
            False,
            0,
            "Hij weet niet hoe vol de auto is, dus hij wacht met laden uit het net. "
            "Geef je accustand door, dan kiest hij het gunstigste moment.",
            plan=f"Begint hoe dan ook op tijd voor {_clock(end)}, uitgaand van een lege accu.",
            rule="no-soc",
            hold_minutes=_hold_until_start(now, end, needed),
            needs_soc=True,
        )

    # --- een vast contract -------------------------------------------------
    #
    # Zonder prijslijst is er geen goedkoop uur om op te wachten: elk uur van de
    # dag kost hetzelfde. Er is wél iets anders om op te wachten, en dat is het
    # enige wat een vast contract goedkoper kan maken: je eigen zon. Bij een
    # gebruikelijk vast contract is een zelf gebruikte kWh al gauw twintig cent
    # meer waard dan een teruggeleverde, dus een auto die 's ochtends bewolkt
    # vollaadt terwijl de middag zonnig wordt, kost een paar euro per keer.
    #
    # Wachten mag alleen als de coach ook kan weten dat hij het haalt, en dat
    # kan hij precies dan als er een klaar-tijd staat én bekend is hoeveel er
    # nog in de auto moet. De regel die daarop let staat hierboven en rekent met
    # de werkelijk gemeten laadstroom, dus die grijpt vanzelf in op het laatste
    # moment dat nog past. Meer is er niet nodig: geen voorspelling, geen
    # aanname over hoeveel zon er straks over is.
    #
    # Ontbreekt een van die twee, dan laadt hij zoals hij altijd deed. Liever een
    # keer te duur dan één keer een auto die 's ochtends niet weg kan.
    if not prices:
        if tariff.buy is None:
            # Geen prijslijst én geen vast bedrag: dan weet de coach helemaal
            # niet wat stroom kost. Dat is geen vast contract maar een gat, en
            # het hoort niet stilletjes te lijken op een normale beslissing.
            # Zo ziet een prijssensor eruit die even niets levert, of een
            # contract dat nog niet is ingevuld. Laden doet hij wel, want een
            # lege auto is erger dan een dure, maar hij zegt erbij waarom hij
            # niets beters kan.
            return Decision(
                True,
                ceiling,
                "Er komen geen prijzen binnen, dus hij laadt gewoon binnen je tijden. "
                "Kijk bij Installatie of je prijssensor het nog doet.",
                rule="no-prices",
            )

        if window.enabled and end and needed is not None:
            # Wachten is hier nooit duurder dan nu laden, want bij een vast
            # contract kost elk uur hetzelfde. Het enige dat verandert is
            # hoeveel eigen zon er nog in gaat, en dat kan alleen maar meer
            # worden. De klaar-tijdregel hierboven grijpt vanzelf in op het
            # laatste moment dat nog past, dus dit kan zonder risico.
            #
            # Hier stond eerder een poortje dat de zonverwachting vergeleek met
            # wat er nog in de auto moest, en dat was een klif: op 18-08-2026
            # zakte de verwachting van 6,6 naar 6,3 kWh en sprong de coach van
            # volledig wachten naar vol vermogen uit het net, een halve euro in
            # dertig minuten. De verwachting hoort de tekst te bepalen en niet
            # het gedrag.
            # Wachten houdt op zodra het huis tot rust komt. De zon levert dan
            # niets meer op, elk uur kost hetzelfde, en doorschuiven naar het
            # laatste moment dat nog past laat maar een kwartier speling over.
            # Een echte zonnestraal na achten pakt de zonregel hierboven nog
            # steeds, want die staat boven deze.
            avond = _evening_before(end)
            if avond is not None and now >= avond:
                # En dan op de ondergrens, niet op vol vermogen. Tussen acht uur
                # 's avonds en de klaar-tijd zit een hele nacht, terwijl een lege
                # auto op 6 A driefasig in ruim twee en een half uur vol is. Bij
                # een vast contract kost dat wachten niets, en de lagere piek
                # scheelt je aansluiting alles: 4 kW in plaats van 11 kW, en dus
                # ruimte voor de wasmachine die er om negen uur bij komt. Sven
                # vroeg dit op 25-08-2026, de dag dat zijn paal voor het eerst
                # driefasig laadde en het verschil dus echt ging tellen.
                #
                # Redt hij het zo niet, dan is dat geen probleem van deze sport:
                # de klaar-tijdregel hierboven rekent met wat er nog kán en
                # grijpt vanzelf in op het laatste moment dat nog past.
                rustig = min(ceiling, MIN_AMPS)
                return Decision(
                    True,
                    rustig,
                    "De zon levert niets meer op en de piek van het avondeten is "
                    f"voorbij. Hij vult rustig aan op {rustig} A, want er is tijd "
                    "genoeg en zo belast hij je aansluiting het minst.",
                    plan=f"Laadt rustig door tot de auto vol is, op tijd voor {_clock(end)}.",
                    rule="evening",
                    needs_soc=soc_unknown,
                )

            if _zon_verwacht(sun, car):
                reden = "Alles kost hetzelfde bij een vast contract, dus hij wacht op je eigen zon."
            else:
                reden = (
                    "Er komt vandaag minder zon dan er nog in moet, maar wachten kost je "
                    "niets bij een vast contract. Dus hij pakt de zon die er is."
                )
            # Wanneer hij weer begint hoort erbij te staan. Zonder dat leest
            # een paal die stilvalt als een paal die kapot is, en dan is de
            # eerste vraag "hoezo is hij gestopt" in plaats van "mooi, hij
            # wacht". Sven op 20-08-2026, precies die vraag.
            momenten = [m for m in (avond, _latest_start(end, needed)) if m and m > now]
            begint = min(momenten) if momenten else None
            return Decision(
                False,
                0,
                reden,
                plan=(
                    f"Begint uiterlijk om {_clock(begint)} en is op tijd vol "
                    f"voor {_clock(end)}."
                    if begint
                    else f"Vult de rest op tijd bij voor {_clock(end)}."
                ),
                rule="wait-for-sun",
                hold_minutes=(
                    _hold_until(now, begint) if begint
                    else _hold_until_start(now, end, needed)
                ),
                needs_soc=soc_unknown,
            )
        return Decision(
            True,
            ceiling,
            "Laden binnen de tijden die je hebt ingesteld.",
            rule="fixed-tariff",
        )

    # Zonder accustand staat hier het slechtste geval, en dat is beter dan het
    # alternatief: bij nul uren pakt `cheapest_hours` álle uren als "goedkoop"
    # en laadt de coach dus meteen, ook op het duurste uur van de nacht.
    plan_hours = cheapest_hours(prices, max(now, start) if start else now, end, needed or 0)
    current = price_now(prices, now)

    if current and any(row["start"] == current["start"] for row in plan_hours):
        return Decision(
            True,
            ceiling,
            f"Dit is een van de goedkoopste uren: {_euro(current['price'])} per kWh.",
            plan=_describe(plan_hours),
            rule="cheap-hour",
            needs_soc=soc_unknown,
        )

    return Decision(
        False,
        0,
        "Het is nu niet het goedkoopste moment om te laden.",
        plan=_describe(plan_hours),
        rule="wait-for-price",
        needs_soc=soc_unknown,
        # Tot het eerste uur dat hij van plan is te gebruiken. Verloopt de pauze
        # doordat de coach wegvalt, dan laadt de auto vanaf dat moment gewoon
        # door, en dat is precies het goede antwoord: duurder, maar wel vol.
        hold_minutes=_hold_until(now, plan_hours[0]["start"] if plan_hours else None),
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
NEVER_HOLD = frozenset({"disconnected", "complete", "user-hold", "no-room"})


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
