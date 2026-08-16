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

# Room left under the fuse. A minute of overshoot is harmless, but a household
# that switches on an oven while the car is at the ceiling should not be the
# thing that trips it.
FUSE_MARGIN_AMPS = 2.0

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

# Only bother re-commanding when the difference is worth it; anything smaller is
# below what a car itself regulates to.
STEP_AMPS = 1

# Charging is never perfectly efficient: this much of what the charger delivers
# actually lands in the battery.
CHARGE_EFFICIENCY = 0.9


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


@dataclass
class Car:
    """The profile of the car that is plugged in."""

    capacity_kwh: float = 0.0
    # 1 or 3. For a car that can do both this is what is being measured now.
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


@dataclass
class Window:
    """When this device may run, from the schedule."""

    enabled: bool = False
    not_before: time | None = None
    start_by: time | None = None
    done_by: time | None = None


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


# --- The sums -------------------------------------------------------------


def amps_for(watts: float, phases: int) -> float:
    """Turn a power into a current, on one phase or on three."""
    return watts / (VOLTS * max(1, phases))


def watts_for(amps: float, phases: int) -> float:
    """And back again."""
    return amps * VOLTS * max(1, phases)


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
        household = max(grid.phase_amps) - grid.charger_amps
        limits.append(grid.fuse_amps - max(0.0, household) - FUSE_MARGIN_AMPS)

    return int(max(0, min(limits)))


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


def hours_needed(car: Car, amps: int) -> float | None:
    """How long that takes at this current."""
    energy = energy_needed_kwh(car)
    if energy is None or amps <= 0:
        return None
    return energy / (watts_for(amps, car.phases) / 1000.0)


def _at(day: datetime, moment: time | None) -> datetime | None:
    """A time of day on the day of `day`."""
    if moment is None:
        return None
    return day.replace(hour=moment.hour, minute=moment.minute, second=0, microsecond=0)


def window_bounds(now: datetime, window: Window) -> tuple[datetime | None, datetime | None]:
    """The window this schedule describes, as two moments around `now`.

    A schedule is two times on a clock, and a clock repeats. Which of the
    repetitions is meant is decided here, and it is easy to get wrong: at two in
    the morning the window that matters is the one that opened at eleven
    *yesterday*, not the one that opens tonight. Looking only at today put the
    coach to sleep for the entire night it was supposed to be charging in.

    So all three candidates are laid out -- yesterday's, today's and tomorrow's
    -- and the one containing `now` wins. If none does, the next one to come is
    returned, because that is what "you may charge from eleven" means.

    A window that ends before it starts runs through the night, which is the
    ordinary case: not before eleven, finished by seven.
    """
    if window.not_before is None and window.done_by is None:
        return None, None

    spans = []
    for days in (-1, 0, 1):
        basis = now + timedelta(days=days)
        start = _at(basis, window.not_before)
        end = _at(basis, window.done_by)
        if start and end and end <= start:
            end += timedelta(days=1)
        spans.append((start, end))

    for start, end in spans:
        if (start is None or start <= now) and (end is None or now < end):
            return start, end

    ahead = [(start, end) for start, end in spans if start and start > now]
    return min(ahead, key=lambda span: span[0]) if ahead else spans[1]


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


# --- The decision ---------------------------------------------------------


def decide(
    now: datetime,
    prices: list[dict],
    grid: Grid,
    car: Car,
    charger: Charger,
    window: Window,
    goal: str = "cost",
) -> Decision:
    """What to do with this charging point, this minute.

    The rules are tried in order and the first that fits wins, which is what
    makes the outcome explainable: there is always exactly one reason.

    1. No cable, nothing to decide.
    2. A guest charges, full stop.
    3. Outside the window the coach keeps its hands off.
    4. The deadline is close enough that waiting would miss it.
    5. There is surplus from the roof worth using.
    6. This hour is one of the cheap ones the plan picked.
    7. Otherwise: wait.

    Above all of them sits the ceiling, so no rule can ever ask for more than
    the fuse, the charger or the car allows.
    """
    ceiling = ceiling_amps(grid, car, charger)

    if not charger.connected:
        return Decision(False, 0, "Er hangt geen auto aan de paal.", rule="disconnected")

    if ceiling < MIN_AMPS:
        return Decision(
            False,
            0,
            "Je aansluiting is te zwaar belast om te laden. Zodra er ruimte is, gaat hij verder.",
            rule="no-room",
        )

    if car.guest:
        return Decision(
            True,
            ceiling,
            "Er hangt een gast aan de paal, dus die laadt meteen.",
            plan="Laadt door tot de kabel eruit gaat.",
            rule="guest",
        )

    # Once running, keep running for a bit. Cars mind being interrupted more
    # than the electricity bill minds a few extra minutes.
    if charger.charging and charger.started_at is not None:
        if now - charger.started_at < timedelta(minutes=MIN_RUN_MINUTES):
            return Decision(
                True,
                min(ceiling, _running_amps(grid, car, ceiling, goal)),
                "Net begonnen met laden.",
                rule="min-run",
            )

    start, end = window_bounds(now, window) if window.enabled else (None, None)

    if window.enabled and start and now < start:
        return Decision(
            False,
            0,
            f"Laden mag vanaf {_clock(start)}.",
            plan=f"Begint na {_clock(start)}, op het goedkoopste moment dat past.",
            rule="too-early",
        )

    # --- the deadline outranks everything ---------------------------------
    needed = hours_needed(car, ceiling)
    if window.enabled and end and needed is not None:
        slack = (end - now).total_seconds() / 3600 - needed
        if slack <= 0.25:
            return Decision(
                True,
                ceiling,
                f"Nu doorladen, anders is de auto om {_clock(end)} niet vol.",
                plan="Laadt op vol vermogen tot de auto klaar is.",
                rule="deadline",
            )

    # --- own sun --------------------------------------------------------
    surplus_amps = int(amps_for(grid.surplus_w, car.phases))
    floor_watts = watts_for(MIN_AMPS, car.phases)
    if grid.surplus_w >= floor_watts * SURPLUS_SLACK:
        amps = max(MIN_AMPS, min(ceiling, surplus_amps))
        return Decision(
            True,
            amps,
            f"Je levert {grid.surplus_w / 1000:.1f} kW terug, dus die gaat nu in de auto.".replace(
                ".", ",", 1
            ),
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
        )

    # --- the cheap hours ---------------------------------------------------
    if not prices:
        # Without a price list there is nothing to choose between, so a fixed
        # tariff simply charges inside its window.
        return Decision(
            True,
            ceiling,
            "Laden binnen de tijden die je hebt ingesteld.",
            rule="fixed-tariff",
        )

    plan_hours = cheapest_hours(prices, max(now, start) if start else now, end, needed or 0)
    current = price_now(prices, now)

    if current and any(row["start"] == current["start"] for row in plan_hours):
        return Decision(
            True,
            ceiling,
            f"Dit is een van de goedkoopste uren: {_euro(current['price'])} per kWh.",
            plan=_describe(plan_hours),
            rule="cheap-hour",
        )

    return Decision(
        False,
        0,
        "Het is nu niet het goedkoopste moment om te laden.",
        plan=_describe(plan_hours),
        rule="wait-for-price",
    )


def _running_amps(grid: Grid, car: Car, ceiling: int, goal: str) -> int:
    """What to hold while the minimum run is being served out."""
    surplus = int(amps_for(grid.surplus_w, car.phases))
    if goal == "solar":
        return max(MIN_AMPS, min(ceiling, surplus))
    return ceiling


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
