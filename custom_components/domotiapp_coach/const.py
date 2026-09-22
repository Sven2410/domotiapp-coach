"""Constants for the DomotiApp Coach integration."""

from __future__ import annotations

from datetime import date

from typing import Any, Final

DOMAIN: Final = "domotiapp_coach"

# --- Sidebar panel ---------------------------------------------------------
PANEL_URL_PATH: Final = "domotiapp-coach"
PANEL_COMPONENT_NAME: Final = "domotiapp-coach-panel"
PANEL_TITLE: Final = "DomotiApp Coach"
PANEL_ICON: Final = "mdi:home-lightning-bolt"

# Public URL under which the panel assets are served.
URL_BASE: Final = "/domotiapp_coach_static"
FRONTEND_DIR: Final = "frontend"
PANEL_FILENAME: Final = "domotiapp-coach-panel.js"

# --- Settings storage ------------------------------------------------------
# Everything configurable lives in the panel's own Instellingen section rather
# than in a Home Assistant options flow: customers run this on a phone behind
# Kiosk Mode, where HA's own settings screens are out of reach.
STORAGE_KEY: Final = f"{DOMAIN}.settings"
STORAGE_VERSION: Final = 1

# Fired on the event bus after a save, so every open panel refreshes itself.
EVENT_SETTINGS_UPDATED: Final = f"{DOMAIN}_settings_updated"

# Elke melding die de coach naar de telefoon stuurt gaat ook hierlangs, zodat
# het paneel een geschiedenis kan tonen. De eigenaar op 04-09-2026: "daarom wil ik
# ook een soort geschiedenis meldingen scherm." Een melding op een telefoon is
# weg zodra hij weggeveegd is; hier blijft hij staan.
EVENT_NOTIFICATION: Final = f"{DOMAIN}_notification"
MELDINGEN_KEY: Final = f"{DOMAIN}.meldingen"
MELDINGEN_VERSION: Final = 1
MELDINGEN_MAX: Final = 3000

# De laadbeurten, met wat ze kostten en wat ze bespaarden. Eigen bestand, net
# als de meldingen. Tweeduizend beurten is jaren.
BEURTEN_KEY: Final = f"{DOMAIN}.beurten"
BEURTEN_VERSION: Final = 1
BEURTEN_MAX: Final = 2000

# --- Device types ----------------------------------------------------------
# "overig" carries a free-text name; the rest are named by their type.
#
# Alleen wat de coach werkelijk iets met een apparaat kan: de laadpaal en de
# vaatwasser stuurt hij, de boiler is het volgende, een airco meet hij mee.
# De eigenaar op 19-09-2026 haalde de thuisbatterij, de warmtepomp, de wasmachine, de
# droger en de zwembadpomp eruit; hetzelfde argument als bij de merken van een
# laadpaal, een regel in een lijst leest als een belofte. Wat er niet in staat
# past nog steeds onder "overig", met een eigen naam.
#
# De thuisbatterij is er sinds 22-09-2026 weer in, en nu omdat de coach hem
# werkelijk stuurt: zie batterij.py.
DEVICE_TYPES: Final = [
    "laadpaal",
    "thuisbatterij",
    "boiler",
    "vaatwasser",
    "airco",
    "overig",
]

# De types die er ooit in stonden, met hoe ze in het paneel heetten. Alleen om
# een apparaat dat er al staat netjes om te zetten naar "overig" zonder dat de
# bewoner kwijt is wat het was; zie `_migrate` in storage.py.
VERVALLEN_TYPES: Final = {
    "warmtepomp": "Warmtepomp",
    "wasmachine": "Wasmachine",
    "droger": "Droger",
    "zwembadpomp": "Zwembadpomp",
}

# --- Charger brands --------------------------------------------------------
# Which extra entities a charging point offers depends entirely on its brand:
# not every charger can be started, stopped or paused, and the ones that can do
# not agree on how. Picking the brand is what decides which fields are asked
# for. Only Easee is supported. De eigenaar on 04-09-2026: the other brands came out
# of the list, because a brand in a list reads as a promise, and there was
# none. Op 19-09-2026 ging "overig" er om dezelfde reden uit: een laadpaal die
# de coach niet kan sturen is geen laadpaal maar een apparaat dat hij meet, en
# daar is "overig" als type voor.
CHARGER_BRANDS: Final = [
    "easee",
]

# --- Dishwasher brands -----------------------------------------------------
# Same reasoning as the chargers: what a dishwasher reports and how it is
# started differs per brand. Home Connect covers Bosch, Siemens, Neff,
# Gaggenau and Constructa in one, because they all speak the same API. It is
# the only one supported; same decision as the chargers, 04-09-2026.
DISHWASHER_BRANDS: Final = [
    "home_connect",
    "overig",
]

# --- Battery brands ----------------------------------------------------------
# Anker is de officiele Anker SOLIX-integratie, die lokaal via Modbus praat:
# een modus, een vermogen en een richting. "overig" is elke batterij die in
# Home Assistant dezelfde knoppen heeft: een getal voor het vermogen (met een
# teken, of met een richting ernaast) en eventueel een modus. Welke tekst er in
# die modus hoort staat per merk in devices.js en gaat mee in `battery`.
BATTERY_BRANDS: Final = [
    "anker",
    "overig",
]

# Every brand id the panel may send, whatever the device type. Kept as one set
# so the websocket schema does not have to know which brands belong to which
# type -- the panel decides that, and it only ever sends one it offered.
ALL_BRANDS: Final = sorted({*CHARGER_BRANDS, *DISHWASHER_BRANDS, *BATTERY_BRANDS})

# --- Grid metering patterns ------------------------------------------------
# Customers have one of two: a pair of sensors where one is always zero, or a
# single sensor that goes negative while feeding back into the grid.
GRID_MODE_SPLIT: Final = "split"
GRID_MODE_SIGNED: Final = "signed"

# --- Contract --------------------------------------------------------------
CONTRACT_FIXED: Final = "fixed"
CONTRACT_DYNAMIC: Final = "dynamic"

# A dynamic contract either has one entity that already carries the all-in
# price, or a market price that still needs tax, markup and VAT applied.
DYNAMIC_ALL_IN: Final = "all_in"
DYNAMIC_MARKET: Final = "market"

# How often a dynamic price changes. The Dutch market is moving from hourly to
# quarter-hourly settlement, and suppliers are following at their own pace, so
# it is the customer who knows which one their contract is on. It decides the
# block size the coach plans in.
PRICE_INTERVAL_HOUR: Final = "hour"
PRICE_INTERVAL_QUARTER: Final = "quarter"

# Nominal voltage per phase, used to turn the main fuse into a power ceiling.
# 3 x 25 A -> 17250 W, 1 x 25 A -> 5750 W.
GRID_VOLTAGE: Final = 230

# --- How much the coach may do on its own ----------------------------------
# Not a strategy but a level of trust, and they are different questions: a
# strategy says what to aim for, this says how far the coach may go on its own.
# "Voorstellen" is the one that matters most in practice -- it is what lets
# somebody watch the sums be right for a week before letting go.
LEVEL_READ: Final = "read"
LEVEL_ADVISE: Final = "advise"
LEVEL_PROPOSE: Final = "propose"
LEVEL_STEER: Final = "steer"
LEVELS: Final = [LEVEL_READ, LEVEL_ADVISE, LEVEL_PROPOSE, LEVEL_STEER]

# What the coach optimises for once it is allowed to act.

# Fired after every round, so an open panel can show what was decided without
# writing anything to disk a minute at a time.
EVENT_DECISION: Final = f"{DOMAIN}_decision"

# Vanaf welke maximale laderlimiet een paal in fasemodus `auto` een laadbeurt
# op drie fasen begint. Gemeten aan de eigen Easee op 25-08-2026: op 14 A koos hij
# bij elke start één fase (13,85 A, 3.125 W), en op 16 A koos dezelfde paal met
# dezelfde auto meteen drie fasen (15,45 A, 10.855 W). Waar de grens tussen die
# twee precies ligt is niet ingekaderd en Easee noemt zelf nergens een getal,
# dus dit is de laagste waarde waarvan bekend is dat het goed gaat. Het is
# meteen de fabrieksinstelling van de paal.
PHASE_START_AMPS: Final = 16.0

# --- Steering a charging point ---------------------------------------------
# How each brand is told what to do. The dynamic limit is the safe way in: it
# sits under the charger's own maximum, so a mistake there cannot ask for more
# than the installation allows. The words for start and stop differ per brand
# and even per firmware, so what the customer typed in wins over these.
CHARGER_CONTROL: Final = {
    "easee": {
        "limit_service": ("easee", "set_charger_dynamic_limit"),
        "limit_field": "current",
        # De houdbaarheid van die limiet, in minuten, waarbij 0 oneindig is en
        # 1080 het hoogste dat de paal aanneemt. Dit is geen instelling maar een
        # antwoord per geval op de vraag: wat moet er gebeuren als de coach
        # wegvalt terwijl dit getal er staat? Bij een stroom om op te laden is
        # doorladen veilig, dus oneindig. Bij een 0 hangt het ervan af waarom er
        # gepauzeerd wordt; dat staat in coach.py bij `FOREVER_RULES`.
        "ttl_field": "time_to_live",
        "command_service": ("easee", "action_command"),
        "command_field": "action_command",
        "words": {"start": "start", "stop": "stop", "pause": "pause", "resume": "resume"},
    },
}

# Wanneer de salderingsregeling afloopt. Op die datum vervalt het wegstrepen
# van teruglevering tegen afname, en daarmee de reden waarom een teruggeleverde
# kWh nu bijna evenveel waard is als een gekochte.
#
# Het staat hier als datum en niet als iets dat de klant moet aanzetten, want
# het is landelijk geregeld en op de dag zelf verandert het voor iedereen
# tegelijk. Zonder deze grens zou de coach na de jaarwisseling maandenlang een
# belastingteruggave blijven inrekenen die niet meer bestaat, en dat merk je
# pas op de eindafrekening. Het vinkje van de klant blijft staan; het telt
# alleen niet meer mee.
NETTING_ENDS = date(2027, 1, 1)


# --- Default settings ------------------------------------------------------
# The panel falls back to simulated values while `sources` is still empty, so a
# fresh install shows a working dashboard before any sensor is mapped.
DEFAULT_SETTINGS: Final[dict[str, Any]] = {
    "navigation": {
        # Where the Home button goes. Customers run Kiosk Mode (no sidebar, no
        # tabs), so the panel has to offer its own way back.
        "home_path": "/lovelace/0",
    },
    "sources": {
        "solar": "",
        # Meer omvormers: de vermogenssensoren van de tweede en derde, bij de
        # eerste opgeteld. De bewoner van de eerste woning op 22-09-2026:
        # "steeds meer consumenten hebben meerdere omvormers."
        "solar_extra": [],
        # House consumption is never configured: it follows from generation and
        # the meter, and one less mandatory sensor is one less thing to get
        # wrong at a customer.
        "grid_mode": GRID_MODE_SPLIT,
        "grid_import": "",
        "grid_export": "",
        "grid_signed": "",
        # Most single-sensor meters report negative while feeding back, but not
        # all of them. Without this the diagram runs exactly backwards, and it
        # looks plausible enough that nobody questions it.
        "grid_signed_invert": False,
        # Per-phase detail, when the customer's meter offers it. With phase
        # currents the load on the connection can be judged per phase, which is
        # what actually trips a fuse -- an average never does.
        "phases_enabled": False,
        "phases_on_overview": False,
        "phases": {
            "l1": {"current": "", "power": "", "voltage": ""},
            "l2": {"current": "", "power": "", "voltage": ""},
            "l3": {"current": "", "power": "", "voltage": ""},
        },
        # What the sun is expected to bring. Not a measurement but a forecast,
        # and it is used for a different question than the meters are: not "what
        # is happening" but "is it worth waiting". Forecast.Solar and Solcast
        # both publish this as plain sensors, so it is entity fields rather than
        # an integration this panel talks to itself.
        "solar_forecast": {
            "remaining_today": "",
            "tomorrow": "",
            "peak_today": "",
            # Wat er dit uur en het uur erna verwacht wordt, in kWh. Hiermee kan
            # de coach beslissen dat een uur wachten goedkoper is dan nu stroom
            # bijkopen; met alleen dagtotalen kan dat niet.
            "this_hour": "",
            "next_hour": "",
        },
        # The meter readings themselves: the four counters a Dutch smart meter
        # keeps for electricity, plus gas. These are totals rather than a rate,
        # so nothing on the dashboard computes with them -- they are what a
        # customer copies onto a supplier's website, and having them on the
        # overview saves a trip to the meter cupboard.
        #
        # Gas has its own switch because plenty of houses no longer have it,
        # and an empty gas line on the card reads as a broken sensor.
        "meters": {
            # The generation counter, in kWh. Not the same thing as the power
            # sensor above: that one says what the panels do right now, and a
            # counter is what makes it possible to look back at a week.
            "solar_total": "",
        # De kWh-tellers van de andere omvormers, opgeteld bij de eerste.
        "solar_total_extra": [],
            "import_low": "",
            "import_high": "",
            "export_low": "",
            "export_high": "",
            "gas_enabled": False,
            "gas": "",
            # Water: de teller in m³ en, als die er is, het debiet in L/min
            # voor de lekmelding. De bewoner van de eerste woning op
            # 22-09-2026: "water toevoegen, incl prijs, dan is je nutsrapport
            # compleet."
            "water_enabled": False,
            "water": "",
            "water_flow": "",
        },
    },
    "installation": {
        "home_name": "",
        # 1 or 3. With the main fuse it gives the connection's power ceiling.
        "phases": 3,
        "fuse_amps": 25,
        # Derived from phases x fuse x 230 V while `max_grid_auto` holds, but
        # editable: a customer with a limited or reinforced connection knows
        # better than the arithmetic does.
        "max_grid_watts": 17250,
        "max_grid_auto": True,
        # Whether something else already guards this fuse in hardware, such as
        # an Easee Equalizer. It changes how much room the coach leaves under
        # the fuse: with a balancer present it gives way first, so the balancer
        # never has to intervene at all.
        "load_balancer": False,
        # De sensor waarin die lastbewaker meldt hoeveel hij op dit moment
        # vrijgeeft voor het laden. Een Easee Equalizer heeft er een. Dat is een
        # restwaarde en geen tweede zekering: het huisverbruik zit er al af, de
        # laadpaal zelf niet. Zie `beschikbaar_van_bewaker` in planner.py.
        "balancer_entity": "",
        # Groepen onder de aansluiting met een eigen zekering, zoals een
        # onderverdeelkast in de garage van 3x16 A onder een hoofdaansluiting
        # van 3x25 A (de eerste woning, 22-09-2026). Per groep: id, name,
        # fuse_amps, phases (1 of 3), parent (het id van de groep erboven, ""
        # is de hoofdaansluiting) en sensors (per fase current, power,
        # voltage, zoals `sources.phases`). Een apparaat wijst met `circuit`
        # naar zijn groep. Zie `Circuit` in planner.py.
        "circuits": [],
    },
    "contract": {
        "type": CONTRACT_FIXED,
        # Of teruggeleverde stroom nog gesaldeerd wordt. Dat is geen strategie
        # maar één getal: bij salderen is een teruggeleverde kWh precies zoveel
        # waard als een ingekochte, dus wordt de terugleververgoeding de
        # inkoopprijs, min de kosten die de leverancier erover rekent. De sommen
        # eronder veranderen niet; er komt alleen een ander bedrag in.
        #
        # Het staat als vinkje en niet als iets meetbaars, want het is een
        # afspraak met je leverancier en geen sensor. De regeling loopt af op
        # 1 januari 2027, dus dit vinkje gaat vanzelf uit de praktijk verdwijnen.
        "netting": False,
        # Wat gas kost, in euro per m³, voor de historie en het rapport. Nul is
        # onbekend, en dan staat er geen bedrag. De bewoner van de eerste
        # woning op 22-09-2026: "prijs van gas laten invullen."
        "gas_price": 0.0,
        # Wat water kost, in euro per m³, net als gas.
        "water_price": 0.0,
        # Eerdere contracten, voor wie van leverancier wisselde: de historie
        # rekent elke dag met de prijs die toen gold. Per contract van, tot
        # (leeg is nog lopend), de all-in stroomprijs, de terugleververgoeding
        # en de gasprijs. Dezelfde bewoner: "gascontract 1: van-tot + prijs,
        # gascontract 2: van-tot + prijs; dat kun je ook doen bij de
        # stroomprijzen, dan kun je een goede weergave bieden van kosten, ook
        # bij wijzigen van aanbieder." Wat de coach nú doet rekent met het
        # contract hierboven; dit is alleen voor terugkijken.
        "periods": [],
        "fixed": {
            "all_in_price": 0.28,
            "feed_in_tariff": 0.07,
            "feed_in_costs": 0.0,
        },
        "dynamic": {
            "source": DYNAMIC_ALL_IN,
            # Hourly or quarter-hourly. Not derivable from the price sensor:
            # a sensor that only publishes hourly prices looks exactly the same
            # as a quarter-hourly one that happens to be flat for an hour.
            "interval": PRICE_INTERVAL_HOUR,
            # One entity that already includes tax, markup and VAT.
            "all_in_entity": "",
            # Or the bare market price, with the rest added here.
            "market_entity": "",
            "energy_tax": 0.1088,
            "supplier_markup": 0.02,
            "vat_percent": 21,
            "feed_in_costs": 0.0,
            # Wat de leverancier per teruggeleverde kWh bovenop de marktprijs
            # betaalt. Uit een artikel over het einde van het salderen dat de
            # eigenaar op 22-09-2026 doorstuurde: Zonneplan, Frank Energie en
            # ANWB 2 cent, Tibber niets, Next Energy 2,19 cent eraf. Mag dus
            # ook negatief zijn.
            "feed_in_bonus": 0.0,
        },
    },
    # Wie welke melding krijgt, en de zekeringmelding zelf. De eigenaar op 06-09-2026:
    # de klant zet zijn meldingen aan en uit in het tabje Meldingen, de admin
    # voegt de personen toe, en een persoon ziet alleen zichzelf. Een persoon
    # is een telefoon (notify-dienst) met een naam, eventueel gekoppeld aan een
    # gebruiker van Home Assistant, en een schakelaar per soort; zie
    # ontvangers.py. Een lijst, want storage.py snoeit dicts tegen deze
    # standaard en zou een vrije map leegmaken.
    "notifications": {
        "people": [],
        # Warn when the connection is being pushed towards its limit. The
        # interval matters as much as the threshold: load swings across the
        # trigger point constantly, so without it one busy hour would send a
        # stream of notifications.
        # Lekkage of abnormaal verbruik van water en gas. De bewoner van de eerste
        # woning op 22-09-2026: "meldingen instellen obv abnormaal water- en
        # gasverbruik, mogelijk lekkage." Water dat langer dan `water_flow_minutes`
        # onafgebroken loopt, of een dag die meer dan `factor` keer het gewone
        # dagverbruik is (na `min_days` gemeten dagen).
        "usage_alert": {
            "enabled": False,
            "water_flow_minutes": 120,
            "factor": 3,
            "min_days": 5,
        },
        "load_alert": {
            "enabled": False,
            "threshold_percent": 80,
            "min_interval_minutes": 30,
            # How long the load has to stay over the line before anything is
            # sent. An oven element or a motor starting produces a spike of a
            # second or two that no fuse minds and nobody can act on, and a
            # notification for it is exactly the kind people switch off. A
            # minute still leaves plenty of room: a fuse carrying a little over
            # its rating holds for the better part of an hour.
            "min_duration_seconds": 60,
        },
    },
    "strategy": {
        # How far the coach may go on its own. It starts at "propose": it works
        # out what it would do and shows it, and only acts once somebody agrees.
        # Nobody should have to trust an automation they have never seen be
        # right.
        "level": LEVEL_PROPOSE,
        # What it aims for when it does act. Lowest cost reckons everything in
        # euros, which by itself already prefers using your own sun over
        # exporting it; "solar" insists on the sun even when buying would be
        # cheaper.
        # "Zware belasting" stond hier tot v0.52.0 als `load_alert`, met de
        # ontvangers erin. Sinds 06-09-2026 staat dat onder `notifications`,
        # in het tabje Meldingen; storage.py verhuist het één keer.
        # When an appliance may run. One entry per device, as a list rather
        # than a map keyed by device id: the storage prunes dictionaries
        # against these defaults, which would empty a free-form map on every
        # load. Nested dictionaries inside a list item are left alone, so the
        # shape of an entry is free.
        #
        # Three times, all optional and all meaning something different:
        # `not_before` is the earliest it may start, `start_by` the latest it
        # may start, `done_by` the moment it has to be finished. A customer who
        # only cares about one of them fills in one of them.
        #
        # At least one of the three is what turns "run this when power is
        # cheap" into a question with an answer. Without any of them the
        # cheapest moment is always later, so nothing would ever start.
        #
        # `per_day` swaps the single window for one per weekday, because
        # weekends are not weekdays.
        "schedules": [],
    },
    "devices": [],
    # Device ids the customer has released for steering right now: the
    # dishwasher is loaded and its door is shut, the car may charge. Kept as a
    # list rather than a map on purpose -- the storage prunes dictionaries
    # against these defaults, which would empty a free-form map on every load.
    #
    # It is state rather than configuration, but it belongs here all the same:
    # it has to survive a restart (a dishwasher stays loaded) and reach every
    # open panel over the same event.
    "ready_devices": [],
    # Welke daarvan de bewoner "nu starten" gaf in plaats van het goedkoopste
    # moment; altijd ook in `ready_devices`. De eigenaar op 13-09-2026: na de
    # klaar-tijd de keuze "ingeruimd en morgen starten" of "ingeruimd en nu
    # starten".
    "ready_now": [],
    # Which car is hanging on which charging point right now. State rather than
    # configuration, like `ready_devices`: it changes when somebody plugs in a
    # different car, it has to survive a restart, and whoever is standing in the
    # driveway is not an administrator. A list for the same reason as the rest:
    # storage.py prunes dictionaries against these defaults.
    "active_cars": [],
    # Wat de bewoner zelf heeft opgegeven over hoe vol zijn auto zit, voor auto's
    # die dat niet aan Home Assistant vertellen. Per opgave wordt de stand van de
    # kilowattuurteller van de laadpaal bewaard, want daarmee telt de coach zelf
    # verder en hoeft er niet elk uur opnieuw iets ingevuld te worden. Vervalt
    # zodra de kabel eruit gaat: het percentage hoorde bij die auto en die rit.
    "car_soc": [],
    # Wat een auto per band van tien procent aankan, in kW, zoals de coach dat
    # bij een echte beurt mat terwijl de auto zelf de rem was. Sommige auto's
    # nemen bovenin gas terug, en zonder dit rekent de klaar-tijdsom met het
    # tempo van de paal en is de auto 's ochtends niet vol. Per laadpunt en per
    # auto; storage.py snoeit op het laadpunt. Zie `_tempo_leren` in coach.py.
    "car_pace": [],
    # Wat de coach bij een echte beurt mat van een programma-apparaat: per
    # apparaat en per programma de duur, het verbruik, de piek en het verloop
    # (watt per vijf minuten vanaf de start), als lopend gemiddelde over de
    # laatste beurten. Wint van de tabel van de klant zodra hij er is. De eigenaar op
    # 06-09-2026: "dat gaan meten en dan die waardes in kunnen vullen." Zie
    # `_async_meting_bewaren` in coach.py en `met_metingen` in planner.py.
    "program_measured": [],
    # Wat de coach van een boiler leerde door hem aan te zetten en te kijken:
    # het vermogen van het element, hoeveel er in een vol vat gaat, wat er per
    # uur uit gaat, wanneer hij voor het laatst vol was en wat er sindsdien in
    # ging. Per apparaat. De eigenaar op 19-09-2026: "alleen de switch invullen en
    # power invullen", de rest zelflerend. Zie `_one_boiler` in coach.py.
    "boiler_learned": [],
    # Wat de coach van een thuisbatterij bijhoudt, per apparaat: het gemeten
    # rendement, wanneer hij voor het laatst vol was (voor de wekelijkse volle
    # beurt) en wat hij per dag verdiende (voor de terugverdientijd). Zie
    # `_one_batterij` in coach.py.
    "battery_state": [],
    # Het dagverbruik van gas en water dat de coach bijhoudt voor de melding
    # bij abnormaal verbruik: per meter en per dag de m³, en per meter de
    # stand waarmee de dag begon. Lijsten, want `_prune` laat lijsten met rust.
    "usage_days": [],
    "usage_start": [],
    # De knoppen van de bewoner per laadpunt: een akkoord, snelladen, een pauze.
    # Opdrachten van een mens, dus ze horen een herstart van Home Assistant te
    # overleven. Ze gelden voor de sessie die er dan hangt: de kabel eruit wist
    # ze, en na twaalf uur zonder toezicht vervallen ze vanzelf.
    "sessions": [],
    "thresholds": {
        # Zelfbenutting in percent: below `low` is bad, above `high` is good.
        "self_use": {"low": 30, "high": 70},
        # Energy price in euro per kWh: below `low` is good, above `high` is bad.
        "price": {"low": 0.20, "high": 0.30},
    },
}

# Apparaten met een programma die de coach start. De eigenaar op 06-09-2026: eerst
# alleen de vaatwasser. Hier en niet in coach.py, omdat de opslag ze ook nodig heeft: een beurt
# van zo'n apparaat is een "programma" en geen laadbeurt.
PROGRAMMA_TYPES = ("vaatwasser",)

# Wat een laadtempo minstens moet zijn om er een te heten: zes ampère op één
# fase, de laagste stand die een paal kan leveren. Wat daaronder gemeten wordt
# komt van een auto die stilstaat of van een sensor die achterloopt; thuis
# kwam er op 17-09-2026 0,1 kW in de opslag en daarmee rekende de
# klaar-tijdregel twintig uur voor één band. Hier en niet in coach.py, omdat de
# opslag zulke rijen ook opruimt. Zie `_tempo_leren` en `_tempo_uit`.
TEMPO_ONDERGRENS = 6 * 230.0 / 1000.0
