/** Het Engels van een deel van het paneel (v0.139.0); zie docs/taal.md. */
export const INSTELLINGEN = {
  // views/installation.js
  "Hoe je huis gemeten wordt": "How your home is measured",
  "Je aansluiting, je kasten en groepen, en welke sensoren meten wat er gebeurt. Hierop rekent de coach. Je hoeft niet alles in te vullen; zonder gekoppelde sensoren blijven de cijfers leeg.":
    "Your grid connection, your panels and circuits, and which sensors measure what happens. The coach calculates with this. You do not have to fill in everything; without linked sensors the figures stay empty.",
  "De naam van de woning komt ook boven het overzicht te staan.": "The name of the home also appears above the overview.",
  "Naam van de woning": "Name of the home",
  "Terugverdiend ook aan de bewoner tonen": "Also show Paid back to the resident",
  "Op de kaart van de thuisbatterij: hoeveel van de aanschafprijs er al terug is, uit wat ze opleverde sinds de coach haar volgt. Zonder datum. De aanschafprijs vul je in bij de batterij, onder Afschrijving.":
    "On the home battery's card: how much of the purchase price has been earned back, from what it earned since the coach has been following it. Without a date. Enter the purchase price at the battery, under Depreciation.",
  "Bijvoorbeeld: Dorpsstraat 12": "For example: 12 High Street",
  "Aantal fasen": "Number of phases",
  "1 fase": "1 phase",
  "Eén fase van 230 V.": "One phase of 230 V.",
  "3 fasen": "3 phases",
  "Drie fasen van 230 V.": "Three phases of 230 V.",
  "Hoofdzekering per fase (A)": "Main fuse per phase (A)",
  "Maximaal netvermogen (W)": "Maximum grid power (W)",
  "Automatisch berekenen": "Calculate automatically",
  "Uit fasen × zekering × 230 V. Zet dit uit als je aansluiting begrensd of juist verzwaard is.":
    "From phases × fuse × 230 V. Turn this off if your connection is limited or upgraded.",
  "Er zit een lastbewaker op de aansluiting": "There is a load balancer on the connection",
  "Zoals een Easee Equalizer. Die bewaakt dezelfde zekering en kan het laden zelf terugschroeven. Staat dit aan, dan houdt de coach een ruimere marge aan en stapt hij als eerste terug, zodat de lastbewaker een vangnet blijft dat niet hoeft in te grijpen. Meet je lastbewaker de fasen, kies die sensoren dan hieronder bij de stroom per fase; dat is de zuiverste meting die je hebt.":
    "Such as an Easee Equalizer. It guards the same fuse and can turn charging down itself. With this on, the coach keeps a wider margin and steps back first, so the load balancer stays a safety net that does not need to step in. If your load balancer measures the phases, choose those sensors below under the current per phase; that is the cleanest measurement you have.",
  "Sensor: wat je lastbewaker vrijgeeft": "Sensor: what your load balancer allows",
  "Optioneel, en alleen als je bewaker meldt hoeveel hij op dit moment vrijgeeft voor het laden. Bij een Easee Equalizer heet die sensor \"Equalizer limiet\". Dat getal beweegt mee met wat de rest van je huis gebruikt: het is wat er overblijft, niet je hoofdzekering. Vul je hem in, dan vraagt de coach er nooit meer overheen en hoeft je bewaker niet in te grijpen.":
    "Optional, and only if your load balancer reports how much it currently allows for charging. On an Easee Equalizer that sensor is called \"Equalizer limit\". The number moves with what the rest of your home uses: it is what is left, not your main fuse. If you fill it in, the coach never asks for more than that and your load balancer does not need to step in.",
  "Onderverdeelkasten": "Sub-panels",
  "Heb je naast je hoofdkast een onderverdeelkast, bijvoorbeeld in de garage, met een eigen zekering? Zet hem hier neer. De coach blijft dan onder de zekering van die kast én onder die van je hoofdkast. Heeft de kast een eigen kWh-meter, dan weet de coach ook wat er de rest van de kast gebruikt wordt; zonder meter telt hij alleen wat hij er zelf naartoe stuurt.":
    "Do you have a sub-panel next to your main panel, for example in the garage, with its own fuse? Add it here. The coach then stays under the fuse of that panel and under that of your main panel. If the panel has its own kWh meter, the coach also knows what the rest of the panel uses; without a meter it only counts what it sends there itself.",
  "Onderverdeelkast toevoegen": "Add sub-panel",
  "Groepen": "Circuits",
  "Een groep met een eigen zekering, in je hoofdkast of in een onderverdeelkast, bijvoorbeeld een laadpaal op een eigen B20. Kies bij Apparaten welke apparaten eraan hangen. Een groep zonder eigen kWh-meter telt alleen wat de coach er zelf naartoe stuurt.":
    "A circuit with its own fuse, in your main panel or in a sub-panel, for example a charger on its own B20. Choose under Devices which devices are on it. A circuit without its own kWh meter only counts what the coach sends there itself.",
  "Groep toevoegen": "Add circuit",
  "Energiebronnen": "Energy sources",
  "Welke sensoren meten je opwek en je meterstand. Of de sensor in watt of kilowatt meet maakt niet uit, dat rekent de coach zelf om. Het verbruik van de woning wordt hieruit berekend.":
    "Which sensors measure your generation and your meter. Whether the sensor measures in watts or kilowatts does not matter; the coach converts it. Home consumption is calculated from this.",
  "Opwek zonnepanelen": "Solar generation",
  "Nog een omvormer": "Another inverter",
  "Heb je meer omvormers, zet ze hier erbij; de coach telt ze op.": "Got more inverters? Add them here; the coach adds them up.",
  "Hoe meet je slimme meter?": "How does your smart meter measure?",
  "Afzonderlijk": "Separate",
  "Twee sensoren: verbruik en productie. Eén van de twee staat altijd op nul.":
    "Two sensors: consumption and production. One of the two is always zero.",
  "Gecombineerd": "Combined",
  "Eén sensor die negatief wordt zodra je teruglevert.": "One sensor that goes negative as soon as you export.",
  "Energieverbruik (van het net)": "Energy consumption (from the grid)",
  "Energieproductie (naar het net)": "Energy production (to the grid)",
  "Netvermogen": "Grid power",
  "Normaal is positief inkoop en negatief teruglevering.": "Normally positive is import and negative is export.",
  "Meting omgekeerd": "Reversed measurement",
  "Aanvinken als je meter het andersom doet: positief bij teruglevering. Herken je aan een diagram dat precies verkeerd om staat.":
    "Tick this if your meter does it the other way round: positive when exporting. You can tell by a diagram that is exactly the wrong way round.",
  "Fasen": "Phases",
  "Heeft de meter van deze woning losse waarden per fase, vul ze dan hier in. Daarmee wordt de belastbaarheid per fase berekend in plaats van op het totaal. Een zekering gaat er immers uit op de zwaarste fase en niet op het gemiddelde.":
    "If the meter of this home has separate values per phase, fill them in here. The load is then calculated per phase instead of on the total. After all, a fuse trips on the most heavily loaded phase, not on the average.",
  "Fasen beschikbaar": "Phases available",
  "Aanzetten als deze woning per fase meet.": "Turn on if this home measures per phase.",
  "Stroom (A)": "Current (A)",
  "Vermogen": "Power",
  "Spanning (V)": "Voltage (V)",
  "Zonverwachting": "Solar forecast",
  "Wat er vandaag en morgen aan zon verwacht wordt. Daarmee kan de coach besluiten of het de moeite is om te wachten, of dat hij beter vannacht op de goedkope uren kan draaien. Integraties als Forecast.Solar en Solcast leveren deze waarden als sensoren; vul in wat je hebt.":
    "How much solar is expected today and tomorrow. With this the coach can decide whether it is worth waiting, or whether it is better to run on the cheap hours tonight. Integrations such as Forecast.Solar and Solcast provide these values as sensors; fill in what you have.",
  "Verwacht vandaag nog": "Expected for the rest of today",
  "Verwacht morgen": "Expected tomorrow",
  "Verwacht dit uur": "Expected this hour",
  "Verwacht volgend uur": "Expected next hour",
  "In kWh over dat uur. Dit zijn de twee die de coach echt gebruikt om te beslissen: moet hij nu stroom bijkopen om op de zon te laden terwijl er volgend uur veel meer aankomt, dan wacht hij dat uur af. Met alleen dagtotalen kan hij dat niet weten.":
    "In kWh over that hour. These are the two the coach really uses to decide: if it would have to buy power now to charge on solar while much more is coming next hour, it waits for that hour. With daily totals alone it cannot know that.",
  "Tijdstip hoogste opwek vandaag": "Time of peak generation today",
  "Optioneel. Hiermee kan de coach zeggen rond welk uur het overschot het grootst is.":
    "Optional. With this the coach can say around which hour the surplus is largest.",
  "Meterstanden": "Meter readings",
  "De tellers van je slimme meter, zoals ze op de meter zelf staan. Vul in wat je hebt; alleen de ingevulde standen komen op het overzicht te staan. Dit zijn totalen in kWh en m³, dus geen vermogens.":
    "The counters of your smart meter, as shown on the meter itself. Fill in what you have; only the readings you fill in appear on the overview. These are totals in kWh and m³, not power.",
  "Opwek totaal (teller)": "Total generation (counter)",
  "De teller van je omvormer in kWh, niet het vermogen. Zonder deze kan het paneel niet terugkijken op wat je hebt opgewekt.":
    "The counter of your inverter in kWh, not the power. Without it the panel cannot look back at what you have generated.",
  "Nog een opwekteller": "Another generation counter",
  "De teller van elke andere omvormer; het paneel telt ze op.": "The counter of every other inverter; the panel adds them up.",
  "Geleverd, laag tarief": "Import, low tariff",
  "Geleverd, hoog tarief": "Import, high tariff",
  "Teruggeleverd, laag tarief": "Export, low tariff",
  "Teruggeleverd, hoog tarief": "Export, high tariff",
  "Deze woning gebruikt gas": "This home uses gas",
  "Staat dit uit, dan blijft gas van het overzicht weg.": "If this is off, gas stays off the overview.",
  "Gasmeter (m³)": "Gas meter (m³)",
  "Deze woning heeft een watermeter in Home Assistant": "This home has a water meter in Home Assistant",
  "Bijvoorbeeld de HomeWizard Watermeter. Dan staat water bij de standen, in de historie en in het rapport.":
    "For example the HomeWizard Watermeter. Water then appears with the readings, in History and in the report.",
  "Watermeter (m³)": "Water meter (m³)",
  "De teller, in m³.": "The counter, in m³.",
  "Waterverbruik nu (L/min)": "Water use now (L/min)",
  "Optioneel. Met deze sensor kan de coach melden als er te lang onafgebroken water loopt; zie Meldingen.":
    "Optional. With this sensor the coach can tell you when water keeps running for too long; see Notifications.",
  "Navigatie": "Navigation",
  "De Home-knop rechtsboven brengt je terug naar je eigen dashboard. Draai je Kiosk Mode, dan is dat de enige weg terug.":
    "The Home button at the top right takes you back to your own dashboard. If you run Kiosk Mode, that is the only way back.",
  "Pad van je thuisdashboard": "Path of your home dashboard",
  "Bijvoorbeeld {a} of {b}.": "For example {a} or {b}.",
  "Zoek een vermogenssensor…": "Search for a power sensor…",
  "Zoek een stroomsensor…": "Search for a current sensor…",
  "Zoek een spanningssensor…": "Search for a voltage sensor…",
  "Zoek een tijdstip…": "Search for a time…",
  "Zoek een verwachting in kWh…": "Search for a forecast in kWh…",
  "Zoek je gasmeter…": "Search for your gas meter…",
  "Zoek een meterstand…": "Search for a meter reading…",
  "groep": "circuit",
  "Hangt onder": "Fed from",
  "Hoofdkast": "Main panel",
  "Nieuwe onderverdeelkast": "New sub-panel",
  "Nieuwe groep": "New circuit",
  "Naam": "Name",
  "Bijvoorbeeld: Garage": "For example: Garage",
  "Bijvoorbeeld: Laadpaal": "For example: Charger",
  "Zekering per fase (A)": "Fuse per phase (A)",
  "Deze onderverdeelkast heeft een eigen kWh-meter": "This sub-panel has its own kWh meter",
  "Deze groep heeft een eigen kWh-meter": "This circuit has its own kWh meter",
  "Dan vul je hieronder per fase de sensoren in.": "Then fill in the sensors per phase below.",
  "Onderverdeelkast verwijderen": "Remove sub-panel",
  "Groep verwijderen": "Remove circuit",
  "Omvormer {n}": "Inverter {n}",
  "Opwekteller {n}": "Generation counter {n}",
  "Weghalen": "Remove",
  "Handmatig ingesteld op {kw} kW; berekend zou {berekend} kW zijn": "Set manually to {kw} kW; calculated it would be {berekend} kW",

  // views/notifications.js
  "Kritiek": "Critical",
  "Wat je zelf moet oplossen: een sensor die zwijgt, een auto die niet op tijd vol raakt, een paal die opnieuw gestart is, een thuisbatterij die te warm wordt.":
    "What you need to fix yourself: a sensor that goes silent, a car that will not be full in time, a charger that restarted, a home battery that gets too hot.",
  "Verslagen": "Reports",
  "Als een laadbeurt klaar is, de kabel eruit gaat, of een sensor het weer doet.":
    "When a charging session is done, the cable is unplugged, or a sensor works again.",
  "Zware belasting": "Heavy load",
  "Als je aansluiting te zwaar belast wordt, zodat je iets uit kunt zetten voor de zekering eruit gaat.":
    "When your connection is overloaded, so you can switch something off before the fuse trips.",
  "Elk besluit": "Every decision",
  "Elke keer dat de coach iets anders gaat doen. Dat zijn er veel; alleen als je alles wilt volgen.":
    "Every time the coach starts doing something different. There are many; only if you want to follow everything.",
  "Vandaag": "Today",
  "Gisteren": "Yesterday",
  "Niets vandaag": "Nothing today",
  "{n} vandaag, {k} kritiek": "{n} today, {k} critical",
  "{n} vandaag": "{n} today",
  "Alles": "All",
  "Besluiten": "Decisions",
  "{n} seconden": "{n} seconds",
  "{n} minuut": "{n} minute",
  "{n} minuten": "{n} minutes",
  "uur": "hour",
  "1 uur": "1 hour",
  "{n} uur": "{n} hours",
  "Wie welke berichten op zijn telefoon krijgt, en alles wat de coach deed en meldde.":
    "Who gets which messages on their phone, and everything the coach did and reported.",
  "Wie krijgt wat": "Who gets what",
  "Naam van de bewoner": "Name of the resident",
  "Telefoon": "Phone",
  "Elke telefoon met de Home Assistant-app staat hier, zodra de app erop ingelogd is.":
    "Every phone with the Home Assistant app appears here once the app is logged in on it.",
  "Persoon toevoegen": "Add person",
  "Herinneringen": "Reminders",
  "Een bericht in je berichtenbox (het belletje bovenin) en op je telefoon, zodat je het niet vergeet.":
    "A message in your inbox (the bell at the top) and on your phone, so you do not forget.",
  "Meterstanden doorgeven, de eerste keer op": "Submit meter readings, the first time on",
  "Daarna": "After that",
  "elke maand": "every month",
  "elk kwartaal": "every quarter",
  "elk jaar": "every year",
  "niet meer, eenmalig": "not again, one-off",
  "Waarschuwingen": "Warnings",
  "Een bericht zodra je aansluiting te zwaar belast wordt. De coach kijkt naar de zwaarst belaste fase als die bekend is, anders naar je totale netvermogen. Wie het krijgt staat hierboven per persoon.":
    "A message as soon as your connection is overloaded. The coach looks at the most heavily loaded phase if it is known, otherwise at your total grid power. Who gets it is set per person above.",
  "Melding aanzetten": "Turn on notification",
  "Zonder dit blijft de belastbaarheid gewoon op het overzicht staan, maar krijgt niemand er bericht van.":
    "Without this the load still shows on the overview, but nobody gets a message about it.",
  "Zware belasting aan": "Heavy load notification",
  "Waarschuw vanaf (%)": "Warn from (%)",
  "Pas melden als het aanhoudt": "Only notify if it lasts",
  "Een oven of een motor die aanslaat geeft een piek van een seconde waar geen zekering van uit gaat. Pas als de belasting zo lang boven de grens blijft, gaat er bericht uit.":
    "An oven or a motor starting up gives a one-second peak that no fuse trips on. Only when the load stays above the limit this long is a message sent.",
  "Niet vaker dan eens per": "No more often than once per",
  "De belasting schommelt heen en weer over de grens; zonder tussentijd zou je een reeks berichten krijgen voor één druk uur.":
    "The load swings back and forth across the limit; without a gap you would get a string of messages for one busy hour.",
  "Lekkage of abnormaal verbruik": "Leak or unusual use",
  "Een bericht als er te lang onafgebroken water loopt, of als een dag veel meer gas of water vraagt dan gewoon. Water vraagt een watermeter onder Installatie; voor het lopende water ook de sensor van het verbruik nu.":
    "A message when water keeps running for too long, or when a day uses much more gas or water than usual. Water needs a water meter under Installation; for running water also the sensor for current use.",
  "De coach houdt het dagverbruik van gas en water sowieso bij; met dit aan zegt hij het als een dag uit de toon valt.":
    "The coach keeps track of daily gas and water use anyway; with this on it tells you when a day stands out.",
  "Lekkage of abnormaal verbruik aan": "Leak or unusual use notification",
  "Water dat blijft lopen, langer dan": "Water that keeps running, longer than",
  "Een bad of een wasmachine loopt een half uur; een kraan die openstaat of een lekkende leiding loopt de hele nacht.":
    "A bath or a washing machine runs for half an hour; a tap left open or a leaking pipe runs all night.",
  "Een dag valt uit de toon vanaf": "A day stands out from",
  "{n} keer het gewone dagverbruik": "{n} times the usual daily use",
  "Gewoon is de middelste dag van de laatste dertig. Een wasdag of een koude dag komt daar niet zomaar overheen; een lekkage wel.":
    "Usual is the median of the last thirty days. A laundry day or a cold day will rarely go above it; a leak will.",
  "Thuisbatterij te warm": "Home battery too hot",
  "Een bericht als de temperatuur van de thuisbatterij boven je grens komt, en blijft. Welke temperatuur te hoog is staat in de handleiding van de batterij. Het gaat naar wie Kritiek aan heeft staan.":
    "A message when the temperature of the home battery goes above your limit, and stays there. Which temperature is too high is in the manual of the battery. It goes to everyone who has Critical turned on.",
  "Zakt hij weer een graad onder de grens, dan staat dat alleen in de geschiedenis hieronder.":
    "If it drops a degree below the limit again, that only appears in the log below.",
  "Thuisbatterij te warm aan": "Home battery too hot notification",
  "Bericht boven (°C)": "Message above (°C)",
  "Apparaat staat uit": "Device is off",
  "Een bericht als een apparaat dat altijd aan moet staan uit gaat en de coach het na 2 minuten nog niet weer aan heeft gekregen. Het gaat naar wie Kritiek aan heeft staan.":
    "A message when a device that must always be on switches off and the coach has not got it back on after 2 minutes. It goes to everyone who has Critical turned on.",
  "Apparaat staat uit aan": "Device is off notification",
  "Geschiedenis": "Log",
  "Alles wat de coach deed en meldde in de afgelopen twee weken, de nieuwste bovenaan. Wat ook naar een telefoon ging staat in een kader; kritiek is wat je zelf moet oplossen.":
    "Everything the coach did and reported in the past two weeks, newest at the top. What also went to a phone has a frame; critical is what you need to fix yourself.",
  "Dag": "Day",
  "Alle dagen": "All days",
  "Nog niemand": "No one yet",
  "Niets ingesteld": "Nothing set",
  "Meterstanden op {datum}": "Meter readings on {datum}",
  "Geweest": "Passed",
  "aan": "on",
  "uit": "off",
  "{aan} van {totaal} aan": "{aan} of {totaal} on",
  "{n} persoon": "{n} person",
  "{n} personen": "{n} people",
  "Per persoon welke berichten er naar zijn telefoon gaan. Voeg hieronder iemand toe met de telefoon waarop de Home Assistant-app staat.":
    "Per person, which messages go to their phone. Add someone below with the phone that has the Home Assistant app.",
  "Er is nog niemand toegevoegd. Zonder personen gaat er niets naar een telefoon; de geschiedenis hieronder vult zich wel.":
    "No one has been added yet. Without people nothing goes to a phone; the log below still fills up.",
  "{dienst} (bestaat niet meer in Home Assistant)": "{dienst} (no longer exists in Home Assistant)",
  "Echt verwijderen?": "Really remove?",
  "Verwijderen": "Remove",
  "Nog geen telefoon met de app ingelogd": "No phone logged in to the app yet",
  "Die telefoon staat er al.": "That phone is already on the list.",
  "Opgeslagen": "Saved",
  "Opslaan mislukt: {fout}": "Saving failed: {fout}",
  "De volgende keer: {datum}.": "Next time: {datum}.",
  "Dit was eenmalig; er komt geen herinnering meer.": "This was a one-off; there will be no more reminders.",
  "Thuisbatterij": "Home battery",
  "Vul in boven welke temperatuur je een bericht wilt.": "Fill in above which temperature you want a message.",
  "{naam} nu {waarde}": "{naam} now {waarde}",
  "Nu {waarde}": "Now {waarde}",
  "Geldt voor {namen}. Krijgt de coach het weer aan, dan staat dat alleen in de geschiedenis hieronder.":
    "Applies to {namen}. If the coach gets it back on, that only appears in the log below.",
  "Vul eerst je aansluiting in onder Installatie.": "First fill in your grid connection under Installation.",
  "Bij {fasen} × {zekering} A komt dat neer op {stroom} A per fase.": "With {fasen} × {zekering} A that comes to {stroom} A per phase.",
  "De meldingen worden opgehaald.": "Loading the notifications.",
  "Niets dat aan dit filter voldoet.": "Nothing matches this filter.",
  "De coach heeft de afgelopen twee weken niets gemeld.": "The coach has reported nothing in the past two weeks.",
  "{n}, {k} kritiek": "{n}, {k} critical",

  // views/strategy.js
  "Alleen uitlezen": "Read only",
  "Je ziet wat je huis doet. De coach zegt en doet verder niets.": "You see what your home is doing. The coach says and does nothing else.",
  "Adviseren": "Advise",
  "Hij vertelt wat er te winnen valt, maar raakt niets aan.": "It tells you what there is to gain, but touches nothing.",
  "Voorstellen": "Propose",
  "Hij rekent het uit en laat het zien. Pas als jij ja zegt, voert hij het uit.":
    "It works it out and shows you. Only when you say yes does it carry it out.",
  "Zelf sturen": "Control on its own",
  "Hij doet het en vertelt achteraf wat hij gedaan heeft.": "It acts and tells you afterwards what it did.",
  "Wat de coach uit zichzelf doet": "What the coach does on its own",
  "Hier bepaal je hoeveel de coach zelf mag, wie voorgaat en hoe het overzicht eruitziet. Wat je per apparaat wilt stel je in op de kaart van dat apparaat, onder Instellen. Wie welke berichten krijgt staat onder Meldingen.":
    "Here you decide how much the coach may do on its own, who goes first and how the overview looks. What you want per device you set on the card of that device, under Settings. Who gets which messages is under Notifications.",
  "Hoeveel doet de coach zelf?": "How much does the coach do on its own?",
  "Van alleen meekijken tot zelf schakelen. Begin gerust bij Voorstellen: dan zie je precies wat hij zou doen en gebeurt er niets zonder jouw akkoord.":
    "From just watching to switching on its own. Feel free to start with Propose: then you see exactly what it would do and nothing happens without your approval.",
  "Waar hij op mikt staat vast: zo min mogelijk geld uitgeven. De coach legt alle manieren om je auto vol te krijgen naast elkaar, van je eigen zon tot elk uur tussen nu en je klaar-tijd, en kiest de goedkoopste. Je eigen zon wint daarbij vanzelf zodra hij goedkoper is dan het net.":
    "What it aims for is fixed: spending as little money as possible. The coach lines up every way to charge your car, from your own solar to every hour between now and your ready time, and picks the cheapest. Your own solar wins automatically as soon as it is cheaper than the grid.",
  "Voorrang bij zonoverschot": "Priority for solar surplus",
  "Wie het overschot van je zonnepanelen als eerste krijgt, van boven naar beneden. Elke regel krijgt wat hij kan opnemen tot zijn grens, en wat er dan over is gaat naar de volgende. Boven zijn grens laadt een apparaat gewoon verder met wat er dan nog over is; waar het laden van de auto stopt, stel je in op de kaart van de laadpaal, onder Instellen. Dit geldt alleen voor overschot: wat er volgens een planning van het net geladen wordt staat hier los van.":
    "Who gets the surplus of your solar panels first, from top to bottom. Each rule gets what it can take up to its limit, and whatever is left goes to the next. Above its limit a device simply keeps charging with whatever is still left; where charging the car stops, you set on the card of the charger, under Settings. This only applies to surplus: what is charged from the grid according to a schedule is separate from this.",
  "Warmtepomp, koken en de rest van je huis": "Heat pump, cooking and the rest of your home",
  "gaat altijd voor: de coach stuurt dit niet en geeft alleen wat er daarna over is":
    "always comes first: the coach does not control this and only hands out what is left after it",
  "Apparaat voor een nieuwe regel": "Device for a new rule",
  "Regel toevoegen": "Add rule",
  "Standaard terugzetten": "Restore default",
  "Voorrang bij planningen": "Priority for schedules",
  "Wie als eerste de ruimte op je aansluiting krijgt als er volgens een planning van het net geladen wordt. Wie hoger staat krijgt wat er onder je zekeringen past; wie lager staat krijgt wat er daarna over is, en een boiler gaat pas aan als hij er nog bij past.":
    "Who gets the room on your connection first when charging from the grid according to a schedule. Whoever is higher gets what fits under your fuses; whoever is lower gets what is left after that, and a water heater only turns on if it still fits.",
  "gaat altijd voor: de coach verdeelt alleen wat er daarna onder je zekering over is":
    "always comes first: the coach only shares out what is left under your fuse after it",
  "Nachtstrategie": "Night strategy",
  "Houd rekening met de nacht.": "Plan for the night.",
  "De coach houdt genoeg in de thuisbatterij om de nacht door te komen met opgeslagen energie. Zet je dit uit, dan mag de batterij voor de auto en voor handelen leeg tot zijn ingestelde minimum, maar haal je mogelijk de nacht niet met nul op de meter.":
    "The coach keeps enough in the home battery to get through the night on stored energy. If you turn this off, the battery may empty to its set minimum for the car and for trading, but you may not get through the night with zero at the meter.",
  "Zelfbenutting (%)": "Self-consumption (%)",
  "Onder deze waarde rood": "Red below this value",
  "Vanaf deze waarde groen": "Green from this value",
  "Energieprijs (€ per kWh)": "Energy price (€ per kWh)",
  "Tot deze prijs groen": "Green up to this price",
  "Boven deze prijs rood": "Red above this price",
  "Prijskleuren naar de bekende prijzen": "Price colours by the known prices",
  "Het goedkoopste derde van alle prijzen die bekend zijn groen en het duurste derde rood, wat de prijzen ook zijn. Dan zie je meteen de beste uren, ook op een dure dag. Komen rond 14:00 de prijzen van morgen erbij, dan kunnen de kleuren verschuiven.":
    "The cheapest third of all known prices green and the most expensive third red, whatever the prices are. Then you see the best hours at once, even on an expensive day. When tomorrow's prices come in around 14:00, the colours may shift.",
  "Het jaar in Historie begint in": "The year in History starts in",
  "Kies de maand waarin je contract ingaat, dan loopt het jaar daarmee gelijk.":
    "Choose the month your contract starts, so the year runs in step with it.",
  "De fasen tonen op het overzicht": "Show the phases on the overview",
  "Een kaart met de belasting per fase.": "A card with the load per phase.",
  "Verslepen": "Drag",
  "tot warm": "until hot",
  "doel": "target",
  "vol": "full",
  "Voorrang voor {naam} tot hoeveel procent": "Priority for {naam} up to what percentage",
  "eerst tot ": "first up to ",
  "Omhoog": "Up",
  "Omlaag": "Down",
  "Regel weghalen": "Remove rule",
  "volgens zijn laadplanning": "according to its charging schedule",
  "als hij van het net laadt": "when it charges from the grid",
  "laadt bij één prijs voor elk uur niet van het net": "does not charge from the grid when every hour has the same price",
  "als hij nog past": "when it still fits",

  // voorrang.js
  "tot hij warm is": "until it is hot",
  "tot het doel van de auto": "up to the target of the car",
  "tot vol": "until full",
  "eerst tot de auto op {grens}% staat, daarna wat er over is": "first until the car is at {grens}%, then whatever is left",
  "eerst tot {grens}%, daarna wat er over is": "first up to {grens}%, then whatever is left",

  // schedule-sheet.js
  "Niet eerder dan": "Not before",
  "Vóór deze tijd begint de coach er niet aan, hoe goedkoop de stroom ook is.":
    "The coach does not start before this time, however cheap the power is.",
  "Uiterlijk starten om": "Start at the latest at",
  "Starten vóór": "Start before",
  "Op deze tijd start hij hoe dan ook, ook als het dan een duur moment is.":
    "At this time it starts no matter what, even if it is an expensive moment.",
  "Uiterlijk klaar om": "Ready at the latest by",
  "Klaar om": "Ready by",
  "Hier rekent de coach van terug wanneer hij moet beginnen. Bij een programma gebruikt hij de duur die eronder staat.":
    "The coach counts back from this to know when to start. For a programme it uses the duration shown below.",
  "Hoog": "High",
  "Gaat voor de rest.": "Goes before the rest.",
  "Middel": "Medium",
  "De gewone stand.": "The normal setting.",
  "Laag": "Low",
  "Wacht op de anderen.": "Waits for the others.",
  "Leeg is de algemene limiet (Laden tot op de kaart). Ingevuld laadt hij voor deze klaar-tijd tot dit percentage.":
    "Empty means the general limit (Charge to on the card). Filled in, it charges to this percentage for this ready time.",
  "Uit. Zonder planning laadt hij alleen op zon.": "Off. Without a schedule it only charges on solar.",
  "Uit. Zonder planning laadt hij continu, met zon erbovenop.": "Off. Without a schedule it charges continuously, with solar on top.",
  "Uit. Snel staat aan: hij laadt op vol vermogen.": "Off. Fast is on: it charges at full power.",
  "Uit. De coach bepaalt zelf wanneer en kijkt puur naar het gunstigste moment.":
    "Off. The coach decides when, looking only at the best moment.",
  "Aan, maar er staat nog geen enkele tijd in.": "On, but no time has been set yet.",
  "Per dag · {dagen}": "Per day · {dagen}",
  "tot {doel}%": "up to {doel}%",
  "Elke dag · {delen}": "Every day · {delen}",
  "Apparaat": "Device",
  "Schema": "Schedule",
  "Zeg binnen welke grenzen de coach mag werken. Vul alleen in wat je belangrijk vindt, want elk van de drie tijden mag leeg blijven.":
    "Say within which limits the coach may work. Only fill in what matters to you; each of the three times may stay empty.",
  "Voor welke dagen?": "Which days?",
  "Elke dag hetzelfde": "Same every day",
  "Eén stel tijden voor de hele week.": "One set of times for the whole week.",
  "Per dag": "Per day",
  "In het weekend andere tijden dan doordeweeks.": "Different times at the weekend than on weekdays.",
  "Vrijgeven blijft nodig. De coach start dit apparaat alleen als je op het overzicht hebt aangegeven dat het mag draaien. Een tijd instellen is niet hetzelfde als toestemming geven.":
    "Release is still needed. The coach only starts this device once you have indicated on the overview that it may run. Setting a time is not the same as giving permission.",
  "Zo wil je het": "How you want it",
  "{veld} leegmaken": "Clear {veld}",
  "Laden tot": "Charge to",
  "algemeen": "general",
  "Nog geen tijd ingevuld. Zolang er geen enkele grens staat, is later altijd goedkoper en begint de coach nooit.":
    "No time filled in yet. As long as there is no limit at all, later is always cheaper and the coach never starts.",
  "De coach kiest binnen deze grenzen het goedkoopste moment om te starten.":
    "Within these limits the coach picks the cheapest moment to start.",
  "De auto moet om {tijd} opgeladen zijn. Hoe lang dat duurt hangt van de auto af, dus de coach begint zo vroeg als nodig is en laadt bij voorkeur op de goedkoopste uren daarvoor.":
    "The car must be charged by {tijd}. How long that takes depends on the car, so the coach starts as early as needed and prefers the cheapest hours before then.",
  "Klaar om is het einde van het programma, niet het begin. Hoe lang het duurt leest de coach van het apparaat af.":
    "Ready by is the end of the programme, not the start. The coach reads how long it takes from the device.",
  "{programma} duurt gemeten {duur}, dus starten moet uiterlijk om {klok}.":
    "{programma} takes {duur} (measured), so it must start by {klok} at the latest.",
  "{programma} duurt ongeveer {duur}, dus starten moet uiterlijk om {klok}.":
    "{programma} takes about {duur}, so it must start by {klok} at the latest.",
  "het einde van vandaag": "the end of today",
  "het einde van morgen": "the end of tomorrow",
  "De prijzen zijn bekend tot {wanneer}. Een klaar-tijd daarna kan de coach niet doorrekenen. Hij plant dan met wat hij weet, en dat is zelden het goedkoopste moment. De prijzen voor de volgende dag komen meestal in de loop van de middag binnen; daarna klopt de planning weer.":
    "Prices are known until {wanneer}. The coach cannot work out a ready time after that. It then plans with what it knows, and that is rarely the cheapest moment. Prices for the next day usually come in during the afternoon; after that the schedule is right again.",
  "Dit is niet opgeslagen. Probeer het nog een keer.": "This was not saved. Please try again.",
  // De koppen van de blokken (21-10-2026).
  "Weergave": "Display",
  "Hoe het overzicht en Historie eruitzien. Een wijziging hier slaat meteen op.": "How the overview and History look. A change here is saved straight away.",
  "Kleuren": "Colours",
  "Waar de kleuren op het overzicht omslaan van groen naar oranje naar rood.": "Where the colours on the overview change from green to orange to red.",
  "Kaarten": "Cards",
  "Aansluiting": "Grid connection",
  "Lastbewaker": "Load balancer",
  "Zonnepanelen": "Solar panels",
  "Slimme meter": "Smart meter",
  // Elk onderwerp een blok, en een vinkje bij elke functie (21-10-2026).
  "Zekering": "Fuse",
  // v0.165.0: een groep gemeten via de apparaten die erop hangen.
  "Fase": "Phase",
  "Apparaat toevoegen…": "Add a device…",
  "Gemeten via apparaten": "Measured through devices",
  // v0.168.0: de fase van een groep van één fase.
  "Op fase": "On phase",
  "Op welke fase van de hoofdaansluiting deze groep zit. Alles wat erop hangt zit op dezelfde fase.": "Which phase of the main connection this circuit is on. Everything on it is on the same phase.",
  "Kies de apparaten met een vermogenssensor die op deze groep hangen. Hun som is wat de coach van de groep weet; wat er verder op hangt ziet hij niet. Zit de groep bijna aan zijn zekering, dan krijg je een melding.": "Choose the devices with a power sensor on this circuit. Their total is what the coach knows about the circuit; anything else on it he does not see. When the circuit is close to its fuse, you get a notification.",
  // v0.169.0: de fase van een groep volgt de apparaten.
  "Fase onbekend": "Phase unknown",
  "De fase kies je bij het apparaat, onder Apparaten. Weet je hem niet, dan telt de zwaarste fase.": "You choose the phase with the device, under Devices. If you do not know it, the heaviest phase counts.",
  "Volgt de apparaten die erop hangen: {fase}.": "Follows the devices on it: {fase}.",
  "Op een andere fase dan {fase}: {apparaten}. Kies de juiste fase bij het apparaat of hier.": "On a different phase than {fase}: {apparaten}. Choose the right phase with the device or here.",
  "De apparaten op deze groep zeggen elk iets anders: {apparaten}. Kies de juiste fase bij het apparaat of hier.": "The devices on this circuit each say something different: {apparaten}. Choose the right phase with the device or here.",
};
