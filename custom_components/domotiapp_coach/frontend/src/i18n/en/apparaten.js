/** Het Engels van een deel van het paneel (v0.139.0); zie docs/taal.md. */
export const APPARATEN = {
  // devices.js: de soorten apparaten
  "Laadpaal": "Charger",
  "Thuisbatterij": "Home battery",
  "Boiler": "Water heater",
  "Vaatwasser": "Dishwasher",
  "Wasmachine": "Washing machine",
  "Droger": "Dryer",
  "Vriezer": "Freezer",
  "Koelkast": "Fridge",
  "Airco": "Air conditioner",
  "Smart plug": "Smart plug",
  "Overig": "Other",

  // devices.js: de laadpaal, Easee
  "Easee-integratie": "Easee integration",
  "Kies je laadpaal zoals hij in Home Assistant staat. Daar komt het device-id uit dat easee.action_command nodig heeft.":
    "Choose your charger as it appears in Home Assistant. That gives the device id that easee.action_command needs.",
  "Starten": "Start",
  "Stoppen": "Stop",
  "Pauzeren": "Pause",
  "Hervatten": "Resume",
  "Herstarten": "Restart",
  "Start de laadpaal opnieuw op. Een lopende laadsessie stopt daarmee; de lader is een halve minuut niet bereikbaar.":
    "Restarts the charger. A running charging session stops; the charger is unreachable for half a minute.",
  "Status": "Status",
  "Waar de lader mee bezig is: aangesloten, aan het laden, klaar.": "What the charger is doing: connected, charging, done.",
  "Bezig met authenticeren": "Authenticating",
  "Wacht op authenticatie": "Awaiting authentication",
  "Wacht op goedkeuring": "Awaiting authorisation",
  "Wacht op load balancing": "Awaiting load balancing",
  "Wacht op geplande start": "Awaiting scheduled start",
  "Wacht op slimme start": "Awaiting smart start",
  "Wacht tot het laden begint": "Waiting for charging to start",
  "Aan het laden": "Charging",
  "Laden voltooid": "Charging complete",
  "Goedkeuring intrekken": "Withdrawing authorisation",
  "Geen auto aangesloten": "No car connected",
  "Auto reageert onverwacht": "Car behaving unexpectedly",
  "Fout bij laden": "Charging error",
  "Fout: defecte voedingsprint": "Error: faulty power board",
  "Fout: overbelasting": "Error: overcurrent",
  "Fout: PEN-fout in de aarde-nulleider": "Error: PEN fault in the earth neutral",
  "Fout: temperatuur te hoog": "Error: temperature too high",
  "Offline": "Offline",
  "Onderbroken door de Equalizer": "Paused by the Equalizer",
  "Gereed om te laden": "Ready to charge",
  "Zoekt de master": "Searching for the master",
  "Start met laden": "Starting to charge",
  "Stopt met laden": "Stopping charging",
  "Reden geen stroomvraag": "Reason for no current",
  "Waarom er niet geladen wordt terwijl de auto eraan hangt.": "Why it is not charging while the car is connected.",
  "De auto laadt niet": "The car is not charging",
  "Lader uitgeschakeld": "Charger disabled",
  "Lader in foutstatus": "Charger in error state",
  "Zekering te laag": "Fuse too low",
  "Equalizerstroom te laag": "Equalizer current too low",
  "Ongeldig nettype": "Invalid grid type",
  "Begrensd door de laadkabel": "Limited by the charging cable",
  "Begrensd door de auto": "Limited by the car",
  "Dynamisch begrensd door de lader": "Dynamically limited by the charger",
  "Begrensd door de maximale limiet van de lader": "Limited by the charger's maximum limit",
  "Dynamisch begrensd door het stroomcircuit": "Dynamically limited by the circuit",
  "Begrensd door de zekering": "Limited by the fuse",
  "Begrensd door de maximale limiet van het stroomcircuit": "Limited by the circuit's maximum limit",
  "Begrensd door de Equalizer": "Limited by the Equalizer",
  "Begrensd door load balancing": "Limited by load balancing",
  "Begrensd door een lokale instelling": "Limited by a local setting",
  "Begrensd door de offline-instelling": "Limited by the offline setting",
  "Begrensd door het laadschema": "Limited by the charging schedule",
  "Maximale limiet van de lader te laag": "Charger's maximum limit too low",
  "Maximale limiet van het stroomcircuit te laag": "Circuit's maximum limit too low",
  "Dynamische limiet van de lader te laag": "Charger's dynamic limit too low",
  "Dynamische limiet van het stroomcircuit te laag": "Circuit's dynamic limit too low",
  "Dynamische offline-terugvallimiet te laag": "Dynamic offline fallback limit too low",
  "Geen stroomvraag": "No current requested",
  "Geen": "None",
  "Niet verbonden met de master": "Not connected to the master",
  "Geen belemmering": "No restriction",
  "Wacht op het laadschema": "Waiting for the charging schedule",
  "Fase niet aangesloten": "Phase not connected",
  "Onbekend": "Unknown",
  "Wacht af": "Waiting",
  "Wacht op zijn beurt": "Waiting its turn",
  "Maximale limiet lader": "Charger maximum limit",
  "Hoeveel ampère de lader maximaal mag leveren. Dit is de bovengrens die vastligt.":
    "The most amps the charger may deliver. This is the fixed upper limit.",
  "Dynamisch limiet lader": "Charger dynamic limit",
  "De limiet die van moment tot moment mag meebewegen, in ampère. Hij staat op 0 zolang er niet geladen wordt. Hier gaat de coach straks op sturen. Hij blijft altijd onder de maximale limiet.":
    "The limit that may change from moment to moment, in amps. It is 0 while nothing is charging. This is what the coach will steer on. It always stays below the maximum limit.",
  "Dynamisch limiet stroomcircuit": "Circuit dynamic limit",
  "De limiet van de groep waar de paal op zit, in ampère. Daarmee blijft de coach eronder als de auto iets meer trekt dan gevraagd.":
    "The limit of the circuit the charger is on, in amps. With it the coach stays below it when the car draws a little more than asked.",
  "Maximale limiet stroomcircuit": "Circuit maximum limit",
  "De vaste grens van de groep waar de paal op zit, in ampère. De coach neemt de laagste van deze en de dynamische limiet hierboven.":
    "The fixed limit of the circuit the charger is on, in amps. The coach takes the lower of this and the dynamic limit above.",
  "Stroom (wat de lader levert, in ampère)": "Current",
  "Wat de lader op dit moment levert, in ampère.": "What the charger is delivering right now, in amps.",

  // devices.js: de laadpaal, Alfen
  "Alfen gaat via de integratie alfen_modbus; zet in de paal de geldigheidsduur van de Modbus-stroomlimiet op minstens drie minuten.":
    "Alfen works through the alfen_modbus integration; in the charger, set the validity time of the Modbus current limit to at least three minutes.",
  "Maximale stroomlimiet": "Maximum current limit",
  "De number-entiteit van de socket (0 tot 32 A). Hier schrijft de coach op, elke minuut opnieuw.":
    "The number entity of the socket (0 to 32 A). The coach writes to it, again every minute.",
  "Auto aangesloten": "Car connected",
  "De sensor die aan zegt zodra er een auto aan de kabel hangt.": "The sensor that turns on as soon as a car is on the cable.",
  "Auto laadt": "Car charging",
  "De sensor die aan zegt zolang er stroom in de auto gaat.": "The sensor that is on while power is going into the car.",
  "Laadt niet": "Not charging",
  "Modus 3-status": "Mode 3 state",
  "De toestand volgens IEC 61851 (A, B1, B2, C2). Daaraan ziet de coach of de paal de auto stroom aanbiedt terwijl die niets neemt.":
    "The state according to IEC 61851 (A, B1, B2, C2). From it the coach sees whether the charger offers the car power while it takes nothing.",
  "Geen auto": "No car",
  "Auto aangesloten, geen aanbod": "Car connected, nothing offered",
  "Auto aangesloten, wacht op de auto": "Car connected, waiting for the car",
  "Auto vraagt, geen aanbod": "Car requesting, nothing offered",
  "Auto vraagt met ventilatie, geen aanbod": "Car requesting with ventilation, nothing offered",
  "Aan het laden, met ventilatie": "Charging, with ventilation",
  "Niet beschikbaar": "Not available",
  "Storing": "Fault",
  "Werkelijke maximale stroom": "Actual maximum current",
  "Wat de paal zelf maximaal mag leveren, in ampère. Dit is de bovengrens die vastligt.":
    "The most the charger itself may deliver, in amps. This is the fixed upper limit.",
  "Maximale stroom (teruggelezen)": "Maximum current (read back)",
  "Wat de paal nu als limiet heeft staan, in ampère. Daaraan ziet de coach of zijn opdracht is aangenomen.":
    "The limit the charger has set right now, in amps. From it the coach sees whether its command was accepted.",
  "Stroom L1": "Current L1",
  "De stroom op fase 1, in ampère. Samen met het vermogen ziet de coach daaraan op hoeveel fasen de auto laadt.":
    "The current on phase 1, in amps. Together with the power, the coach sees from it on how many phases the car charges.",
  "Bruikbare fasen": "Usable phases",
  "De keuzelijst met 1 Phase en 3 Phases. Alleen nodig als de coach van fasen mag wisselen.":
    "The select with 1 Phase and 3 Phases. Only needed if the coach may switch phases.",

  // devices.js: de programma's van een vaatwasser
  "Eco 50 °C": "Eco 50 °C",
  "Auto 45 tot 65 °C": "Auto 45 to 65 °C",
  "Intensief 70 °C": "Intensive 70 °C",
  "Express 60 °C": "Express 60 °C",
  "Nacht Was": "Night wash",
  "Machine Onderhoud": "Machine care",
  "Voorspoelen": "Pre-rinse",

  // devices.js: vrijgeven
  "Vrijgaveschakelaar": "Release switch",
  "Optioneel: een schakelaar of input_boolean die hetzelfde betekent als \"Ingeruimd en dicht\". Zet je die aan, bijvoorbeeld vanaf een eigen dashboard, dan geeft de coach de vaatwasser vrij; zet je hem op de kaart vrij, dan gaat de schakelaar mee aan. Na de beurt gaan ze allebei uit. Niet de schakelaar van de stekker waar de machine op hangt: die haalt de stroom eraf, en die gebruikt de coach dus niet.":
    "Optional: a switch or input_boolean that means the same as \"Loaded and closed\". Turn it on, for example from a dashboard of your own, and the coach releases the dishwasher; release it on the card and the switch turns on too. After the run both turn off. Not the switch of the plug the machine is on: that cuts the power, so the coach does not use it.",
  "Schakelaar nu starten": "Start now switch",
  "Optioneel: een schakelaar of input_boolean die \"ingeruimd en nu starten\" betekent. Zet je die aan, dan start de coach hem meteen, ook als het niet het goedkoopste moment is. Na de beurt gaat hij uit. Niet de schakelaar van de stekker waar de machine op hangt.":
    "Optional: a switch or input_boolean that means \"loaded, start now\". Turn it on and the coach starts it straight away, even if it is not the cheapest moment. After the run it turns off. Not the switch of the plug the machine is on.",
  "Vrijgaveknop": "Release button",
  "Optioneel: een knop die hetzelfde betekent als \"Ingeruimd en dicht\", bijvoorbeeld een Zigbee-knop naast de vaatwasser (een event-entiteit), een knop-helper (input_button) of een actiesensor. Eén druk geeft hem vrij; nog een keer drukken doet niets. Je krijgt een melding met wanneer hij start.":
    "Optional: a button that means the same as \"Loaded and closed\", for example a Zigbee button next to the dishwasher (an event entity), a button helper (input_button) or an action sensor. One press releases it; pressing again does nothing. You get a notification saying when it starts.",

  // devices.js: de vaatwasser, Home Connect
  "Bosch, Siemens, Neff, Gaggenau en Constructa lopen allemaal via Home Connect. Werkt met de integratie van Home Assistant zelf, met Home Connect Alt en met Home Connect Local (lokaal, zonder cloud).":
    "Bosch, Siemens, Neff, Gaggenau and Constructa all work through Home Connect. Works with Home Assistant's own integration, with Home Connect Alt and with Home Connect Local (local, without the cloud).",
  "Waar de vaatwasser mee bezig is: klaar voor gebruik, aan het draaien, afgelopen.":
    "What the dishwasher is doing: ready to use, running, finished.",
  "Uit": "Off",
  "Klaar voor gebruik": "Ready to use",
  "Wacht op de starttijd": "Waiting for the start time",
  "Aan het draaien": "Running",
  "Gepauzeerd": "Paused",
  "Vraagt om aandacht": "Needs attention",
  "Afgelopen": "Finished",
  "Wordt afgebroken": "Aborting",
  "Geselecteerd programma": "Selected programme",
  "De sensor die zegt welk programma klaarstaat. Daar hangt aan vast hoe lang het duurt en wat het kost. Bij Home Connect Local is dit de sensor \"Actief programma\", die alleen tijdens de beurt iets zegt; zet hieronder dan ook de select \"Geselecteerd programma\", want daaruit leest de coach het de rest van de tijd.":
    "The sensor that says which programme is set. How long it takes and what it costs follow from it. With Home Connect Local this is the sensor \"Active programme\", which only says something during the run; then also set the select \"Selected programme\" below, because the coach reads it from there the rest of the time.",
  "Programma kiezen": "Choose programme",
  "De select-entiteit waarmee je een programma op de machine zet. Hiermee kies je op de kaart welk programma erop staat, en hieruit komen de namen in de tabel hieronder.":
    "The select entity that sets a programme on the machine. With it you choose on the card which programme is set, and the names in the table below come from it.",
  "Resterende tijd": "Remaining time",
  "Hoe lang het programma nog duurt. Home Connect geeft hier de eindtijd, Home Connect Local de uren die nog resten; het paneel rekent zelf terug.":
    "How long the programme has left. Home Connect gives the end time here, Home Connect Local the hours remaining; the panel works it out itself.",
  "Starten op afstand": "Remote start",
  "Optioneel: de sensor die zegt of de machine op afstand gestart mag worden. Staat hij uit, dan drukt de coach niet en zegt hij dat je hem op het apparaat aan moet zetten.":
    "Optional: the sensor that says whether the machine may be started remotely. If it is off, the coach does not press and tells you to turn it on at the appliance.",
  "Aan": "On",
  "Deurstand": "Door state",
  "Moet hij eerst vrijgegeven worden, dan alleen om te laten zien. Hoeft dat niet, dan is klep dicht de vrijgave, en dan is dit veld nodig.":
    "If it has to be released first, this is only for display. If not, a closed door is the release, and then this field is needed.",
  "Dicht": "Closed",
  "Vergrendeld": "Locked",
  "Open": "Open",
  "De knop die het geselecteerde programma start. Bij Home Connect heet die meestal \"Start\" of \"Start/Pauze\". De vaatwasser moet wel op afstand gestart mogen worden. Bij Home Connect Local is de knop er alleen als de machine een start aanneemt (deur dicht); tot die tijd wacht de coach.":
    "The button that starts the selected programme. With Home Connect it is usually called \"Start\" or \"Start/Pause\". The dishwasher must allow remote start. With Home Connect Local the button is only there when the machine accepts a start (door closed); until then the coach waits.",
  "De knop die een lopend programma afbreekt. Optioneel: zonder deze knop kan de coach een programma wel starten maar niet meer terugdraaien.":
    "The button that aborts a running programme. Optional: without it the coach can start a programme but not undo it.",
  "Breekt het lopende programma af. De vaatwasser begint daarna weer van voren af aan.":
    "Aborts the running programme. The dishwasher then starts again from the beginning.",
  "Een vaatwasser zonder koppeling, op een meetstekker: de coach zegt wanneer je hem aan moet zetten en meet wat hij verbruikt.":
    "A dishwasher without an integration, on a metering plug: the coach tells you when to turn it on and measures what it uses.",

  // devices.js: wasmachine en droger, Miele
  "Voor Miele is dat de integratie Miele van Home Assistant zelf. De coach start de {wat} alleen als \"start op afstand\" aan staat op de machine.":
    "For Miele that is Home Assistant's own Miele integration. The coach only starts the {wat} when \"remote start\" is on at the machine.",
  "De sensor die zegt waar de {wat} mee bezig is, bij Miele de sensor met de naam van de machine zelf.":
    "The sensor that says what the {wat} is doing; with Miele the sensor with the name of the machine itself.",
  "Programma": "Programme",
  "De sensor Programma. Het programma kies je op de machine; de coach leest het en plant op de duur die de machine geeft. Na een beurt rekent hij met wat hij gemeten heeft.":
    "The Programme sensor. You choose the programme on the machine; the coach reads it and plans on the duration the machine gives. After a run it uses what it measured.",
  "Hoe lang het programma nog duurt. Zolang het klaarstaat is dat de duur waarmee de coach plant.":
    "How long the programme has left. While it is set, that is the duration the coach plans with.",
  "Start op afstand": "Remote start",
  "Optioneel: de sensor Start op afstand. Staat hij uit, dan drukt de coach niet en zegt hij dat je het op de machine aan moet zetten.":
    "Optional: the Remote start sensor. If it is off, the coach does not press and tells you to turn it on at the machine.",
  "Deur": "Door",
  "Moet hij eerst vrijgegeven worden, dan alleen om te laten zien. Hoeft dat niet, dan is deur dicht de vrijgave, en dan is dit veld nodig.":
    "If it has to be released first, this is only for display. If not, a closed door is the release, and then this field is needed.",
  "De knop Starten van de machine. Die staat in Home Assistant standaard uit: zet hem eerst aan bij de entiteit. Hij is er alleen als de machine een start aanneemt; tot die tijd wacht de coach.":
    "The machine's Start button. It is disabled by default in Home Assistant: enable it at the entity first. It is only there when the machine accepts a start; until then the coach waits.",
  "Optioneel: de knop Stoppen, die een lopend programma afbreekt. Ook die staat standaard uit.":
    "Optional: the Stop button, which aborts a running programme. It is also disabled by default.",
  "Breekt het lopende programma af.": "Aborts the running programme.",
  "Een {wat} zonder koppeling, op een meetstekker: de coach zegt wanneer je hem aan moet zetten en meet wat hij verbruikt.":
    "A {wat} without an integration, on a metering plug: the coach tells you when to turn it on and measures what it uses.",
  "wasmachine": "washing machine",
  "droger": "dryer",

  // devices.js: vriezer en koelkast
  "de vriezer": "the freezer",
  "de koelkast": "the fridge",
  "De coach stuurt {naam} niet. Hij houdt hem in de gaten en stuurt een melding als de deur 3 minuten openstaat, als hij een half uur warmer is dan {grens} °C, of als {naam} een storing meldt.":
    "The coach does not control {naam}. It keeps an eye on it and sends a notification if the door is open for 3 minutes, if it is warmer than {grens} °C for half an hour, or if {naam} reports a fault.",
  "deze vriezer": "this freezer",
  "deze koelkast": "this fridge",
  "Temperatuur": "Temperature",
  "De sensor Temperatuur van {naam}. Is hij een half uur warmer dan {grens} °C, dan krijg je een melding. Niet de zones 2 en 3: die bestaan bij {deze} niet echt.":
    "The Temperature sensor of {naam}. If it is warmer than {grens} °C for half an hour, you get a notification. Not zones 2 and 3: {deze} does not really have them.",
  "Een temperatuursensor in {naam}. Is hij een half uur warmer dan {grens} °C, dan krijg je een melding.":
    "A temperature sensor in {naam}. If it is warmer than {grens} °C for half an hour, you get a notification.",
  "Optioneel: de deursensor. Staat de deur 3 minuten open, dan krijg je een melding.":
    "Optional: the door sensor. If the door is open for 3 minutes, you get a notification.",
  "Optioneel: de sensor Probleem van {naam}. Meldt hij een storing, dan krijg je een melding.":
    "Optional: the Problem sensor of {naam}. If it reports a fault, you get a notification.",
  "Optioneel: een sensor die aan gaat bij een storing. Dan krijg je een melding.":
    "Optional: a sensor that turns on when there is a fault. Then you get a notification.",
  "Voor Miele is dat de integratie Miele van Home Assistant zelf.": "For Miele that is Home Assistant's own Miele integration.",
  "Onder Overig past elke vriezer met een temperatuursensor erin.": "Any freezer with a temperature sensor in it fits under Other.",
  "Onder Overig past elke koelkast met een temperatuursensor erin.": "Any fridge with a temperature sensor in it fits under Other.",

  // devices.js: de thuisbatterij
  "Accustand": "Battery level",
  "Hoe vol de batterij is, in procent.": "How full the battery is, in percent.",
  "Optioneel: de temperatuur van de batterij. Die staat dan op de kaart, en onder Meldingen kun je een bericht krijgen als hij te warm wordt. De coach stuurt er niet op.":
    "Optional: the temperature of the battery. It then shows on the card, and under Notifications you can get a message when it gets too warm. The coach does not steer on it.",
  "Ventilator": "Fan",
  "Optioneel: de smart plug of schakelaar van een ventilator bij de batterij. Met de temperatuur hierboven en een grens onder Wat jij wilt zet de coach hem aan als de batterij te warm wordt.":
    "Optional: the smart plug or switch of a fan near the battery. With the temperature above and a limit under What you want, the coach turns it on when the battery gets too warm.",
  "Vermogen zetten": "Set power",
  "Het getal (number) waarmee het vermogen van de batterij gezet wordt, in watt. Hier stuurt de coach mee.":
    "The number that sets the battery's power, in watts. This is what the coach steers with.",
  "Richting": "Direction",
  "De keuzelijst (select) die zegt of dat vermogen laden of ontladen is.": "The select that says whether that power is charging or discharging.",
  "Optioneel: een keuzelijst die zegt of het vermogen laden of ontladen is. Zonder deze is het teken van het getal de richting: plus is laden.":
    "Optional: a select that says whether the power is charging or discharging. Without it the sign of the number is the direction: plus is charging.",
  "Bedrijfsmodus": "Operating mode",
  "Optioneel: de keuzelijst met de modus van de batterij. De coach zet hem op de modus voor externe sturing zodra hij gaat sturen, en terug zodra hij stopt.":
    "Optional: the select with the battery's mode. The coach sets it to the mode for external control as soon as it starts steering, and back as soon as it stops.",
  "Eigen verbruik": "Self-consumption",
  "Tijdschema": "Time schedule",
  "Externe sturing": "External control",
  "Eigen modus": "Custom mode",
  "Slimme modus": "Smart mode",
  "Dynamische prijzen": "Dynamic prices",
  "Laadvermogen": "Charging power",
  "Alleen als er hierboven geen vermogenssensor met een teken is: wat de batterij nu laadt.":
    "Only if there is no power sensor with a sign above: what the battery is charging now.",
  "Ontlaadvermogen": "Discharging power",
  "En wat hij nu ontlaadt.": "And what it is discharging now.",
  "Capaciteit (kWh)": "Capacity (kWh)",
  "Optioneel: de sensor met de bruikbare inhoud. Zonder deze vul je hem hieronder in.":
    "Optional: the sensor with the usable capacity. Without it, fill it in below.",
  "Laadgrens (%)": "Charge limit (%)",
  "Optioneel: tot hoever de batterij zelf laadt. De coach leest dit, en zet het alleen voor de wekelijkse volle beurt even op 100%.":
    "Optional: how far the battery charges by itself. The coach reads this, and only sets it to 100% briefly for the weekly full charge.",
  "Ontlaadgrens (%)": "Discharge limit (%)",
  "Optioneel: tot hoever de batterij zelf ontlaadt. Ook alleen gelezen.": "Optional: how far the battery discharges by itself. Also only read.",
  "kWh-meter: erin": "kWh meter: in",
  "Optioneel: de teller van een kWh-meter op de batterij, wat erin ging. Met deze twee tellers meet de coach het echte rendement. De tellers van de batterij zelf zijn daar meestal niet goed voor: die meten aan de accukant.":
    "Optional: the counter of a kWh meter on the battery, what went in. With these two counters the coach measures the real efficiency. The battery's own counters are usually not good for that: they measure on the cell side.",
  "kWh-meter: eruit": "kWh meter: out",
  "En wat eruit kwam.": "And what came out.",
  "Batterij zelf: geladen": "Battery itself: charged",
  "Optioneel, voor wie geen kWh-meter op de batterij heeft: de eigen teller van de batterij, wat erin ging. Daarmee telt Historie wat de batterij laadt en ontlaadt, en staat er op de kaart ongeveer hoeveel er weer uit komt. In zijn sommen rekent de coach er niet mee: deze tellers meten aan de accukant, zonder het verlies in de omvormer.":
    "Optional, if there is no kWh meter on the battery: the battery's own counter, what went in. With it History counts what the battery charges and discharges, and the card shows roughly how much comes back out. The coach does not use it in its sums: these counters measure on the cell side, without the loss in the inverter.",
  "Batterij zelf: ontladen": "Battery itself: discharged",
  "En wat eruit ging.": "And what went out.",
  "Hoe vol de batterij is, in procent. Kies je die van een Growatt, dan vult het paneel de vier hieronder vanzelf in, als hetzelfde apparaat ze heeft.":
    "How full the battery is, in percent. Choose the one from a Growatt and the panel fills in the four below by itself, if the same device has them.",
  "Wat de batterij nu laadt. In kW of in W, dat rekent de coach zelf om.": "What the battery is charging now. In kW or in W; the coach converts it itself.",
  "De teller van alles wat er ooit in ging (levenslang), niet die van vandaag. Daarmee staat het rendement in de pop-up van de batterij, en telt Historie wat hij laadt en ontlaadt.":
    "The counter of everything that ever went in (lifetime), not today's. With it the efficiency shows in the battery's pop-up, and History counts what it charges and discharges.",
  "En van alles wat er ooit uit ging.": "And of everything that ever went out.",
  "Voor Anker is dat de officiele Anker SOLIX-integratie, die lokaal met de batterij praat.":
    "For Anker that is the official Anker SOLIX integration, which talks to the battery locally.",
  "Een Growatt stuurt de coach met een laadschema, via de Growatt-integratie: een SPH met een API-token. Kan de omvormer dat niet, dan leest hij hem alleen uit.": "The coach controls a Growatt with a charging schedule, through the Growatt integration: an SPH with an API token. If the inverter cannot do that, the coach only reads it.",
  "laadschema": "charging schedule",
  "Het laadvermogen is wat hij van het net laadt op 100% in het laadschema. Leeg mag: de coach meet allebei zelf, en rekent met wat hij meet zodra hij genoeg heeft.": "The charging power is what it draws from the grid at 100% in the charging schedule. Empty is fine: the coach measures both itself, and uses what it measures once it has enough.",
  "Onder Overig past elke batterij die in Home Assistant een getal heeft waarmee je het vermogen zet.":
    "Any battery that has a number in Home Assistant to set its power fits under Other.",

  // devices.js: airco, boiler, smart plug
  "De airco zelf, zoals Home Assistant hem kent (een climate). Hiermee zet de coach hem aan of uit, in verwarmen of koelen, op de temperatuur die de bewoner kiest.":
    "The air conditioner itself, as Home Assistant knows it (a climate). With it the coach turns it on or off, in heating or cooling, at the temperature the resident chooses.",
  "Kamertemperatuur": "Room temperature",
  "Optioneel: een eigen sensor in de kamer. Leeg is de temperatuur die de airco zelf meet.":
    "Optional: a separate sensor in the room. Empty is the temperature the air conditioner measures itself.",
  "Voor Mitsubishi Electric is dat de airco zoals de MELCloud-integratie hem in Home Assistant zet. Die praat via de cloud: een opdracht van de coach staat er na ongeveer een minuut.":
    "For Mitsubishi Electric that is the air conditioner as the MELCloud integration adds it to Home Assistant. It talks through the cloud: a command from the coach arrives after about a minute.",
  "Schakelaar": "Switch",
  "De smart plug, schakelaar of het relais waarmee de boiler stroom krijgt. Hier zet de coach hem mee aan en uit; hoe warm het water wordt blijft aan de thermostaat van de boiler zelf.":
    "The smart plug, switch or relay that powers the water heater. The coach turns it on and off with it; how hot the water gets is left to the water heater's own thermostat.",
  "Stroom staat erop": "Powered",
  "Geen stroom": "No power",
  "Airfryer": "Air fryer",
  "Aquarium": "Aquarium",
  "Computer": "Computer",
  "Elektrische kachel": "Electric heater",
  "Fietslader": "E-bike charger",
  "Koffiezetapparaat": "Coffee maker",
  "Lamp": "Lamp",
  "Maairobot": "Robot mower",
  "Magnetron": "Microwave",
  "Ontvochtiger": "Dehumidifier",
  "Oven": "Oven",
  "Router": "Router",
  "Server": "Server",
  "Spelcomputer": "Games console",
  "Televisie": "Television",
  "Vijverpomp": "Pond pump",
  "Waterkoker": "Kettle",
  "Iets anders": "Something else",
  "De schakelaar van de smart plug zelf. Die heeft de coach alleen nodig om hem aan te houden; voor meten is het vermogen genoeg.":
    "The switch of the smart plug itself. The coach only needs it to keep it on; for measuring the power is enough.",
  "Smart plug (optioneel)": "Smart plug (optional)",
  "Hangt de vaatwasser aan een smart plug, dan de schakelaar daarvan. Alleen nodig om hem altijd aan te houden; de coach zet hem nooit zelf uit.":
    "If the dishwasher is on a smart plug, its switch. Only needed to keep it always on; the coach never turns it off itself.",

  // devices.js: de auto
  "Handmatig opvragen": "Request manually",
  "Het zuinigst: de auto slaapt door. Op de laadpaalkaart komt een knop om de accustand op te vragen.":
    "The most economical: the car keeps sleeping. The charger card gets a button to request the charge level.",
  "Elk uur wakker maken": "Wake every hour",
  "Staat hij stil en meldt hij niets, dan wekt de coach hem elk uur. Let op: elke keer wakker worden kost accu en houdt de auto uit zijn diepe slaap.":
    "If it is parked and reports nothing, the coach wakes it every hour. Note: every wake-up costs battery and keeps the car out of its deep sleep.",
  "Eén fase": "One phase",
  "Laagste stap ongeveer 1,4 kW.": "Lowest step about 1.4 kW.",
  "Drie fasen": "Three phases",
  "Laagste stap ongeveer 4,1 kW.": "Lowest step about 4.1 kW.",
  "Gast": "Guest",

  // devices.js: vrijgeven op de kaart, en wat er nog ontbreekt
  "Ingeruimd en dicht": "Loaded and closed",
  "Ingeruimd": "Loaded",
  "Zet dit aan als de vaatwasser vol staat en de klep dicht zit. Anders zou de coach hem leeg kunnen laten spoelen.":
    "Turn this on when the dishwasher is full and the door is closed. Otherwise the coach could run it empty.",
  "Mag meedraaien": "OK to run",
  "Mag draaien": "OK to run",
  "Zet dit aan als de machine gevuld is, het programma klaarstaat en starten op afstand aan staat.":
    "Turn this on when the machine is loaded, the programme is set and remote start is on.",
  "Zet dit aan als de coach dit apparaat nu mag inschakelen.": "Turn this on when the coach may switch this device on now.",
  "Vermogenssensor": "Power sensor",
  "Vermogenssensor of typeplaatje": "Power sensor or rating plate",
  "de {naam}": "the {naam}",
  "{rest} en {laatste}": "{rest} and {laatste}",
  "{rest} of {laatste}": "{rest} or {laatste}",

  // views/devices.js: wat er nog ontbreekt om te sturen
  "Om te kunnen sturen ontbreken nog: {lijst}.": "Still needed before the coach can steer it: {lijst}.",
  "Om te kunnen sturen ontbreekt nog: {lijst}.": "Still needed before the coach can steer it: {lijst}.",
  "{naam}: om te kunnen sturen ontbreken nog: {lijst}.": "{naam}: still needed before the coach can steer it: {lijst}.",
  "{naam}: om te kunnen sturen ontbreekt nog: {lijst}.": "{naam}: still needed before the coach can steer it: {lijst}.",
  "om te kunnen sturen ontbreken nog: {lijst}": "still needed to steer: {lijst}",
  "om te kunnen sturen ontbreekt nog: {lijst}": "still needed to steer: {lijst}",
  "{n} apparaten kunnen nog niet gestuurd worden, om te beginnen {naam}.": "{n} devices cannot be steered yet, starting with {naam}.",

  // views/devices.js: Opgeleverd opnieuw uitrekenen
  "Over die dagen staan er geen kwartieren van de meter en de batterij in de opslag van de coach.":
    "The coach's storage has no quarter hours of the meter and the battery for those days.",
  "Vanaf {datum}, {n} dag: Opgeleverd was {voor}, en wordt {na}.": "From {datum}, {n} day: Earned was {voor}, and becomes {na}.",
  "Vanaf {datum}, {n} dagen: Opgeleverd was {voor}, en wordt {na}.": "From {datum}, {n} days: Earned was {voor}, and becomes {na}.",
  "{n} kwartieren hadden geen prijs en tellen niet mee.": "{n} quarter hours had no price and do not count.",
  "De marktprijs van toen komt van Nord Pool.": "The market price of the time comes from Nord Pool.",
  "De prijzen van toen komen uit de statistiek van Home Assistant.": "The prices of the time come from Home Assistant's statistics.",
  "Overgenomen.": "Applied.",
  "Opgeleverd opnieuw uitrekenen": "Recalculate Earned",
  "Stond de terugleverprijs een tijd verkeerd of leeg, dan klopt Opgeleverd over die dagen niet. De coach rekent het opnieuw vanaf de dag die je kiest, met het contract zoals het nu is: uit de kwartieren van de meter en de batterij in zijn eigen opslag, en de accustand en de prijzen van toen. Eerst zie je wat het wordt; pas met Overnemen verandert er iets.":
    "If the export price was wrong or empty for a while, Earned is not right for those days. The coach recalculates it from the day you choose, with the contract as it is now: from the quarter hours of the meter and the battery in its own storage, and the charge level and prices of the time. First you see what it becomes; only Apply changes anything.",
  "Vanaf": "From",
  "Bezig…": "Working…",
  "Uitrekenen": "Calculate",
  "Overnemen": "Apply",
  "Kies eerst een dag.": "Choose a day first.",
  "Opgeleverd is opnieuw uitgerekend": "Earned has been recalculated",
  "Uitrekenen mislukt: {fout}": "Calculation failed: {fout}",

  // views/devices.js: het scherm
  "Apparaten": "Devices",
  "Wat er in huis energie vraagt": "What uses energy in the house",
  "Deze apparaten verschijnen als bollen in de energiestroom op het overzicht. Er staan er altijd hoogstens twee in beeld: draaien er meer, dan krijgt de zwaarste zijn eigen bol en worden de rest bij elkaar opgeteld in de tweede.":
    "These devices appear as bubbles in the energy flow on the overview. At most two are shown at a time: if more are running, the heaviest gets its own bubble and the rest are added together in the second.",
  "Apparaat toevoegen": "Add device",
  "Ruimte toevoegen": "Add room",
  "Verwijderen": "Remove",
  "Sluiten": "Close",
  "Laat staan": "Keep",
  "Geef elke ruimte een naam, of verwijder hem.": "Give every room a name, or remove it.",
  "{n} apparaat": "{n} device",
  "{n} apparaten": "{n} devices",
  "Zonder ruimte": "No room",
  "Naam van de ruimte": "Room name",
  "Volgorde van de ruimtes": "Order of the rooms",
  "Ruimte omhoog": "Room up",
  "Ruimte omlaag": "Room down",
  "Ruimte verwijderen": "Remove room",
  "Nog niets in deze ruimte. Kies hem bij een apparaat, onder Ruimte.": "Nothing in this room yet. Choose it at a device, under Room.",
  "Merk": "Brand",
  "Kies een merk…": "Choose a brand…",
  "Welke gegevens een {wat} levert, hangt van het merk af. Kies er een en de bijbehorende velden verschijnen.":
    "What data the {wat} provides depends on the brand. Choose one and its fields appear.",
  "Nodig zodra de coach mag sturen.": "Needed as soon as the coach may steer.",
  "Voor dit merk zijn de velden nog niet uitgewerkt. Het vermogen wordt wel meegenomen.":
    "The fields for this brand are not worked out yet. The power is still taken into account.",
  "Apparaat": "Device",
  "Kies wat eraan hangt…": "Choose what is plugged in…",
  "Op een smart plug meet de coach hem alleen. Moet hij hem plannen, voeg hem dan toe als {soort}.":
    "On a smart plug the coach only measures it. If it should plan it, add it as {soort}.",
  "Daarmee krijgt hij zijn naam en zijn icoon.": "That gives it its name and its icon.",
  "Dit apparaat moet altijd aan staan": "This device must always be on",
  "Gaat de stekker uit, om wat voor reden ook, dan zet de coach hem meteen weer aan. Lukt dat na 2 minuten nog niet, dan krijg je een melding als je die aanzet onder Meldingen. Bij Alleen uitlezen en Adviseren zet hij hem niet zelf aan, maar meldt hij het wel.":
    "If the plug turns off, for whatever reason, the coach turns it straight back on. If that has not worked after 2 minutes, you get a notification if you turn it on under Notifications. In Read only and Advise it does not turn it on itself, but it does report it.",
  "Kies de schakelaar, anders kan de coach hem niet aanhouden.": "Choose the switch, otherwise the coach cannot keep it on.",
  "Stekker": "Plug",
  "Energieteller": "Energy meter",
  "Energieteller (optioneel)": "Energy meter (optional)",
  // v0.168.0: stroom en spanning van een apparaat.
  "Stroomsensor (optioneel)": "Current sensor (optional)",
  "In ampère, als de stekker die meet. Dan telt de groep waar dit apparaat op hangt met de echte stroom.": "In amps, if the plug measures it. The circuit this device is on then counts with the real current.",
  "Spanningssensor (optioneel)": "Voltage sensor (optional)",
  "In volt, als de stekker die meet. Dan rekent de coach het vermogen van de groep om met de echte spanning in plaats van 230 V.": "In volts, if the plug measures it. The coach then converts the power of the circuit with the real voltage instead of 230 V.",
  "Gekozen bij Groepen, onder Installatie: daar staat dit apparaat bij deze groep.": "Chosen under Circuits, in Installation: this device is listed with that circuit there.",
  "De teller van de smart plug in kWh, als die er een heeft. Daarmee klopt het verbruik in je rapport tot op de komma; zonder wordt het afgeleid uit het gemiddelde vermogen.":
    "The smart plug's counter in kWh, if it has one. With it the consumption in your report is exact; without it, it is derived from the average power.",
  "De sensor Energieverbruik van de machine, in kWh. Een vermogenssensor heeft hij niet: hieruit telt de coach wat een programma verbruikt en wat het kost. Zonder plant hij alleen op de duur.":
    "The machine's Energy consumption sensor, in kWh. It has no power sensor: from this the coach counts what a programme uses and what it costs. Without it, it plans on the duration only.",
  "De teller van dit apparaat in kWh, als die er is. Bij een laadpaal is dat de teller van alles wat hij ooit geladen heeft. Daarmee klopt het verbruik in je rapport tot op de komma en klopt het aantal kWh in het verslag na een laadbeurt; zonder wordt allebei afgeleid uit het gemiddelde vermogen.":
    "This device's counter in kWh, if there is one. For a charger that is the counter of everything it has ever charged. With it the consumption in your report is exact, and so is the number of kWh in the summary after a charging session; without it, both are derived from the average power.",
  "Bediening": "Controls",
  "Wat er ingedrukt wordt om dit apparaat te laten lopen. Dit is wat de knoppen onder Handmatige besturing op het overzicht doen; de coach doet het nog niet uit zichzelf.":
    "What gets pressed to run this device. This is what the buttons under Manual control on the overview do; the coach does not do it by itself yet.",
  "piek {w} W": "peak {w} W",
  "{n} beurten": "{n} sessions",
  "1 beurt": "1 session",
  "Naam": "Name",
  "De meting wordt je eigen opgave": "The measurement becomes your own figure",
  "overnemen": "apply",
  "Terug naar je eigen getallen": "Back to your own figures",
  "wissen": "clear",
  "nog niet gemeten": "not yet measured",
  "Programma verwijderen": "Remove programme",
  "Een gemeten programma staat op slot en toont de meting, want daar rekent de coach mee. \"Wissen\" geeft je eigen getallen terug, \"overnemen\" maakt de meting je eigen opgave.":
    "A measured programme is locked and shows the measurement, because that is what the coach uses. \"Clear\" brings back your own figures, \"apply\" makes the measurement your own figure.",
  "Deze programma's kun je op de kaart kiezen; typ de namen zoals ze op je machine heten. Duur en verbruik zijn opgaven van de fabrikant als uitgangspunt; pas ze aan als je ze beter weet. Zodra een programma een keer gedraaid heeft op de vermogenssensor, rekent de coach met wat er gemeten is.":
    "You can choose these programmes on the card; type the names as they are called on your machine. Duration and consumption are the manufacturer's figures as a starting point; adjust them if you know better. As soon as a programme has run once on the power sensor, the coach uses what was measured.",
  "Deze programma's kun je op de kaart kiezen. Voeg de programma's toe die je gebruikt, met hoe lang ze duren en wat ze ongeveer verbruiken. Zodra een programma een keer gedraaid heeft op de vermogenssensor, rekent de coach met wat er gemeten is.":
    "You can choose these programmes on the card. Add the programmes you use, with how long they take and roughly what they use. As soon as a programme has run once on the power sensor, the coach uses what was measured.",
  "De programma's van je machine, zoals de select-entiteit ze noemt. De opgaven van de fabrikant zijn het uitgangspunt; pas ze aan als je ze beter weet. Zodra een programma een keer gedraaid heeft, rekent de coach met wat er bij jou gemeten is.":
    "Your machine's programmes, as the select entity names them. The manufacturer's figures are the starting point; adjust them if you know better. As soon as a programme has run once, the coach uses what was measured at your home.",
  "Vul hierboven \"Programma kiezen\" in, dan komen hier de programma's van je machine te staan. Tot die tijd rekent de coach met de opgaven van de fabrikant hieronder.":
    "Fill in \"Choose programme\" above and your machine's programmes appear here. Until then the coach uses the manufacturer's figures below.",
  "Programma's": "Programmes",
  "Duur": "Duration",
  "Energie": "Energy",
  "Piek": "Peak",
  "Gemeten": "Measured",
  "Programma toevoegen": "Add programme",
  "Opgaven terugzetten": "Restore manufacturer figures",
  "Het programma kies je op de machine. Zolang het klaarstaat geeft de machine de duur, en daarmee plant de coach; het verbruik weet hij dan nog niet. Na een beurt staat het programma hieronder met wat hij gemeten heeft, en dan rekent hij daarmee.":
    "You choose the programme on the machine. While it is set, the machine gives the duration and the coach plans with that; it does not know the consumption yet. After a run the programme appears below with what it measured, and then it uses that.",
  "Er is nog niets gemeten.": "Nothing has been measured yet.",
  "Deze meting weggooien": "Discard this measurement",
  "Home Assistant kent nog geen {naam}. Installeer die integratie eerst.": "Home Assistant does not know any {naam} yet. Install that integration first.",
  "Kies je laadpaal…": "Choose your charger…",
  "Opdrachten": "Commands",
  "Wat er naar <code>{dienst}</code> gestuurd wordt als <code>{veld}</code>. De ingevulde woorden zijn wat Easee vandaag gebruikt; wijkt jouw paal af, dan pas je ze hier aan. Pauzeren en hervatten staan er niet bij: die schrijven een getal in de dynamische laderlimiet en hebben geen woord nodig.":
    "What is sent to <code>{dienst}</code> as <code>{veld}</code>. The words filled in are what Easee uses today; if your charger differs, change them here. Pause and resume are not listed: they write a number to the dynamic charger limit and need no word.",
  "De coach leest deze batterij alleen uit: hoe vol hij is, wat hij laadt en ontlaadt, en zijn tellers. Sturen doet hij hem niet.":
    "The coach only reads this battery: how full it is, what it charges and discharges, and its counters. It does not control it.",
  "De coach mag dit apparaat aansturen": "The coach may control this device",
  "De coach mag over dit apparaat adviseren": "The coach may give advice about this device",
  "De coach mag dit apparaat noemen": "The coach may mention this device",
  "Hij komt dan op het overzicht te staan, met een vrijgaveknop en handmatige besturing, en de coach bedient hem zelf op het gunstigste moment.":
    "It then appears on the overview, with a release button and manual control, and the coach operates it itself at the best moment.",
  "Hij komt dan op het overzicht te staan, met handmatige besturing, en de coach bedient hem zelf op het gunstigste moment.":
    "It then appears on the overview, with manual control, and the coach operates it itself at the best moment.",
  "Hij heeft geen startknop, dus sturen kan de coach niet. Hij zegt op de kaart en op je telefoon wanneer je hem aan moet zetten, en meet via de vermogenssensor hoe lang een programma duurt en wat het verbruikt. Het apparaat komt dan op het overzicht te staan, met de vrijgaveknop en de programmakeuze.":
    "It has no start button, so the coach cannot control it. It tells you on the card and on your phone when to turn it on, and measures through the power sensor how long a programme takes and what it uses. The device then appears on the overview, with the release button and the programme choice.",
  "De coach plant dit apparaat niet. Met dit vinkje aan noemt hij het wel als je overschot hebt of de stroom goedkoop is; uit, dan volgt hij alleen het verbruik.":
    "The coach does not plan this device. With this ticked it does mention it when you have a surplus or power is cheap; unticked, it only follows the consumption.",
  "Dit apparaat zit alleen op een meetstekker: de coach kan het niet sturen en niet plannen. Met dit vinkje aan noemt hij het wel als je overschot hebt of de stroom goedkoop is; uit, dan volgt hij alleen het verbruik.":
    "This device is only on a metering plug: the coach cannot control or plan it. With this ticked it does mention it when you have a surplus or power is cheap; unticked, it only follows the consumption.",
  "onderverdeelkast": "sub-panel",
  "groep": "circuit",
  "Hangt aan": "Connected to",
  "Hoofdkast": "Main panel",
  "Voor de zekeringbewaking: de coach blijft onder deze zekering én onder alles wat erboven hangt, tot de hoofdkast.":
    "For the fuse monitoring: the coach stays below this fuse and below everything above it, up to the main panel.",
  "Fasen wisselen": "Switch phases",
  "Op zon laadt hij op één fase zolang het dak minder geeft dan drie fasen op hun laagst (4,1 kW), dus al vanaf 1,4 kW. Van het net laadt hij op drie fasen. Wisselen doet hij alleen als de auto stilstaat, en tijdens een beurt hooguit eens per tien minuten. Vul hiervoor ook Bruikbare fasen in. Alleen voor een auto die drie fasen kan.":
    "On solar it charges on one phase while the roof gives less than three phases at their lowest (4.1 kW), so from as little as 1.4 kW. From the grid it charges on three phases. It only switches while the car is not charging, and during a session at most once every ten minutes. Also fill in Usable phases for this. Only for a car that can do three phases.",
  "Welke druk": "Which press",
  "Elke druk": "Any press",
  "Bijvoorbeeld alleen een enkele druk, zodat dubbel drukken iets anders kan doen.":
    "For example only a single press, so a double press can do something else.",
  "de vrijgaveschakelaar is de stekker zelf en haalt de stroom eraf; de coach gebruikt hem niet":
    "the release switch is the plug itself and cuts the power; the coach does not use it",
  "nog geen merk gekozen": "no brand chosen yet",
  "nog niet gekozen wat eraan hangt": "not yet chosen what is plugged in",
  "altijd aan, maar zonder schakelaar": "always on, but without a switch",
  "{entiteit} zit al op een ander apparaat": "{entiteit} is already used by another device",
  "meldingen": "notifications",
  "alleen uitlezen": "read only",
  "geen vermogenssensor": "no power sensor",
  "altijd aan": "always on",
  "De airco": "The air conditioner",
  "Vermogen van het typeplaatje (W)": "Power on the rating plate (W)",
  "alleen zonder vermogenssensor": "only without a power sensor",
  "Wat de airco trekt als hij draait. Daaraan ziet de coach of er genoeg zon over is om hem aan te zetten. Met een vermogenssensor meet hij het zelf, en dan wint de meting. Staan er twee getallen op het plaatje, voor koelen en verwarmen, neem dan het hoogste.":
    "What the air conditioner draws when it runs. From it the coach sees whether there is enough spare solar to turn it on. With a power sensor it measures it itself, and then the measurement wins. If the plate shows two figures, for cooling and heating, take the higher one.",
  "De batterij": "The battery",
  "de inhoud van de accu": "the battery's capacity",
  "De integratie geeft hem niet door, dus vul hem hier in.": "The integration does not report it, so fill it in here.",
  "alleen zonder sensor": "only without a sensor",
  "Rendement heen en terug (%)": "Round-trip efficiency (%)",
  "alleen zonder kWh-meter": "only without a kWh meter",
  "Met het rendement rekent de coach uit of laden van het net loont: bij 75% moet het dure uur een derde duurder zijn dan het goedkope. Bij een vast contract zonder dal- en piektarief loont laden van het net nooit; dan bepaalt het rendement alleen of zon opslaan meer oplevert dan terugleveren. Met een kWh-meter op de batterij meet hij het zelf, en dan wint de meting. Zonder rendement houdt hij alleen de meter op nul.":
    "With the efficiency the coach works out whether charging from the grid pays off: at 75% the expensive hour has to cost a third more than the cheap one. With a fixed contract without off-peak and peak rates, charging from the grid never pays off; then the efficiency only decides whether storing solar earns more than exporting it. With a kWh meter on the battery it measures it itself, and then the measurement wins. Without an efficiency it only keeps the meter at zero.",
  "Hoogste laadvermogen (W)": "Maximum charging power (W)",
  "bijvoorbeeld {n}": "for example {n}",
  "Hoogste ontlaadvermogen (W)": "Maximum discharging power (W)",
  "Hangt op fase": "Connected to phase",
  "Weet ik niet": "Don't know",
  "Voor de zekeringbewaking: laadt de auto tegelijk, dan blijft de batterij onder wat die fase nog overlaat. Weet je het niet, dan telt de zwaarste fase.":
    "For the fuse monitoring: if the car charges at the same time, the battery stays below what that phase has left. If you don't know, the heaviest phase counts.",
  "De vermogenssensor is positief bij ontladen.": "The power sensor is positive when discharging.",
  "Standaard leest de coach plus als laden.": "By default the coach reads plus as charging.",
  "Het stuurgetal is positief bij ontladen.": "The control number is positive when discharging.",
  "Alleen van belang zonder aparte richting.": "Only relevant without a separate direction.",
  "Modus als de coach stuurt": "Mode while the coach steers",
  "de keuze in de bedrijfsmodus": "the option in the operating mode",
  "Modus als de coach stopt": "Mode when the coach stops",
  "Stopt de coach, dan zet hij het vermogen op nul en geeft hij de batterij terug aan zijn eigen modus, zodat hij nooit op zijn laatste opdracht blijft staan.":
    "When the coach stops, it sets the power to zero and hands the battery back to its own mode, so it never stays on its last command.",
  "De batterij doet zelf nul op de meter.": "The battery keeps the meter at zero itself.",
  "Staat standaard aan. Zet hem alleen uit bij een batterij zonder eigen meter in de meterkast; dan regelt de coach de meter via Home Assistant, en dat is trager. De coach zet hem in zijn eigen modus (hierboven: als de coach stopt) en kijkt mee. Hij neemt het alleen over voor laden van het net, handelen, als de laadpaal laadt, in de vakantiestand, bij de reserve en als de zekering krap wordt, en geeft hem na vijf rustige minuten terug. Stilstaan of alleen ontladen plant hij dan niet, want dat kan de batterij in zijn eigen stand niet.":
    "On by default. Only turn it off for a battery without its own meter in the meter cupboard; then the coach controls the meter through Home Assistant, which is slower. The coach puts it in its own mode (above: when the coach stops) and keeps watch. It only takes over for charging from the grid, trading, when the charger is charging, in holiday mode, at the reserve and when the fuse gets tight, and hands it back after five quiet minutes. It then does not plan standing still or only discharging, because the battery cannot do that in its own mode.",
  "Wat de bewoner wil (de reserve, handelen, een keer per week vol, de vakantiestand, de auto helpen en de ventilator) staat sinds v0.114.0 op de kaart van de batterij, onder Instellen.":
    "What the resident wants (the reserve, trading, full once a week, holiday mode, helping the car and the fan) has been on the battery card, under Settings, since v0.114.0.",
  "Auto verwijderen": "Remove car",
  "Wekknop": "Wake button",
  "De knop \"Wake up\" van de Tesla-integratie. Een Tesla slaapt als hij niet laadt en meldt dan geen accustand; met deze knop kan de coach hem wekken. Bij het inpluggen doet hij dat altijd één keer, anders weet hij niet hoeveel er nog in moet.":
    "The \"Wake up\" button of the Tesla integration. A Tesla sleeps when it is not charging and then reports no charge level; with this button the coach can wake it. When plugged in it always does this once, otherwise it does not know how much still has to go in.",
  "Bijvoorbeeld: de blauwe": "For example: the blue one",
  "Accu (kWh)": "Battery (kWh)",
  "Tot hoever hij laadt staat op de kaart van de laadpaal, onder Instellen.": "How far it charges is on the charger card, under Settings.",
  "Hoogste stroom (A)": "Maximum current (A)",
  "optioneel": "optional",
  "Alleen invullen als de auto zelf lager blijft dan je paal aankan.": "Only fill in if the car itself stays below what your charger can handle.",
  "Accupercentage van de auto": "Car's battery percentage",
  "De sensor \"Battery level\" van de Tesla-integratie. Daarmee weet de coach zelf hoeveel er nog in moet.":
    "The \"Battery level\" sensor of the Tesla integration. With it the coach knows by itself how much still has to go in.",
  "Optioneel. Staat de auto in Home Assistant, wijs dan de sensor aan die zegt hoe vol hij is; dan weet de coach zelf hoeveel er nog in moet. Zonder deze vraagt hij het aan jou.":
    "Optional. If the car is in Home Assistant, point to the sensor that says how full it is; then the coach knows by itself how much still has to go in. Without it, it asks you.",
  "Actieradius (optioneel)": "Range (optional)",
  "De sensor \"Battery range\" van de Tesla-integratie. Dan staat er op de kaart hoeveel kilometer er in de accu zit in plaats van hoeveel kWh, en wat een laadbeurt aan kilometers opleverde.":
    "The \"Battery range\" sensor of the Tesla integration. The card then shows how many kilometres are in the battery instead of how many kWh, and how many kilometres a charging session added.",
  "Zegt de auto in Home Assistant hoe ver hij nog komt, wijs die sensor dan aan. Dan staat er op de kaart hoeveel kilometer er in de accu zit in plaats van hoeveel kWh, en wat een laadbeurt aan kilometers opleverde. Werkt samen met het accupercentage hierboven.":
    "If the car says in Home Assistant how far it can still go, point to that sensor. The card then shows how many kilometres are in the battery instead of how many kWh, and how many kilometres a charging session added. Works together with the battery percentage above.",
  "Laadt op": "Charges on",
  "Auto's": "Cars",
  "Welke auto's hier laden. Op het overzicht kies je welke er op dat moment aan hangt, en de coach rekent met de accu en het aantal fasen van die auto. Een gast hoef je niet toe te voegen; die staat er altijd bij en laadt meteen.":
    "Which cars charge here. On the overview you choose which one is connected at the moment, and the coach works with that car's battery and number of phases. You don't need to add a guest; a guest is always listed and charges straight away.",
  "Auto toevoegen": "Add car",
  "Nog geen apparaten": "No devices yet",
  "Voeg je laadpaal, warmtepomp of vaatwasser toe om te zien wanneer ze draaien en wat ze op dat moment vragen.":
    "Add your charger, heat pump or dishwasher to see when they run and what they draw at that moment.",
  "Volgorde": "Order",
  "Omhoog": "Up",
  "Omlaag": "Down",
  "Type": "Type",
  "Eigen naam": "Own name",
  "Bijvoorbeeld: serverkast": "For example: server cabinet",
  "Er staan er twee van dit type. Zonder eigen naam heten ze hier en op het overzicht \"{soort} 1\" en \"{soort} 2\"; met een naam weet je meteen welke welke is.":
    "There are two of this type. Without a name of their own they are called \"{soort} 1\" and \"{soort} 2\" here and on the overview; with a name you know straight away which is which.",
  "Ruimte": "Room",
  "Geen ruimte": "No room",
  "Nieuwe ruimte": "New room",
  "Zoek een energieteller…": "Search for an energy meter…",
  "Zoek het accupercentage…": "Search for the battery percentage…",
  "Zoek de actieradius…": "Search for the range…",
  "Zoek de wekknop…": "Search for the wake button…",
  "Zoek een vermogenssensor…": "Search for a power sensor…",
  "Zoek een entiteit…": "Search for an entity…",
  "Dit apparaat verdwijnt uit de lijst, met alles wat je eraan gekoppeld hebt en met zijn schema. Verwijderen gaat meteen door en is niet terug te draaien.":
    "This device disappears from the list, with everything you linked to it and its schedule. Removing takes effect immediately and cannot be undone.",
  "Dit apparaat is nog niet opgeslagen, dus het verdwijnt gewoon weer uit de lijst.": "This device has not been saved yet, so it simply disappears from the list again.",
  "Apparaat verwijderd": "Device removed",

  // voorkeur-velden.js: Instellen achter de kaart
  "de auto": "the car",
  "{naam}: accustand opvragen": "{naam}: request charge level",
  "{naam}: laadt tot (%)": "{naam}: charges to (%)",
  "Staat er een laadgrens in de auto, zet hem hier ook. Dan weet de coach wanneer hij klaar is in plaats van het achteraf te merken.":
    "If the car has a charge limit set, set it here too. Then the coach knows when it is done instead of noticing afterwards.",
  "Zonder planning": "Without a schedule",
  "Zon: alleen op zonoverschot": "Solar: only on solar surplus",
  "Continu: altijd, met zon erbovenop": "Continuous: always, with solar on top",
  "Goedkoopst: de goedkoopste bekende uren": "Cheapest: the cheapest known hours",
  "Slim: eerst zon, dan het net buiten de avondpiek": "Smart: solar first, then the grid outside the evening peak",
  "Staat het schema aan, dan wint de planning. Op de kaart kies je per beurt Snel, Continu of Zon; als de kabel eruit gaat, geldt dit weer.":
    "If the schedule is on, the schedule wins. On the card you choose Fast, Continuous or Solar per session; when the cable comes out, this applies again.",
  "Continu laden op (A)": "Continuous charging at (A)",
  "Het vaste vermogen van Continu. Geeft de zon meer, dan laadt hij mee omhoog; nooit boven je zekering.":
    "The fixed power of Continuous. If the sun gives more, it charges higher along with it; never above your fuse.",
  "Zon: beginnen vanaf (%)": "Solar: start from (%)",
  "Van het kleinste laadvermogen: 6 A, op drie fasen 4,1 kW. Bij 50% begint Zon al op 2,1 kW zon en komt de rest van het net. Op 100% begint hij pas als de zon het hele vermogen geeft.":
    "Of the lowest charging power: 6 A, on three phases 4.1 kW. At 50%, Solar already starts at 2.1 kW of solar and the rest comes from the grid. At 100% it only starts when the sun gives all the power.",
  "Handelen kan nu niet: de coach kent je terugleverprijs niet. Daarvoor is bij Contract een marktprijssensor nodig, of salderen.":
    "Trading is not possible now: the coach does not know your export price. That needs a market price sensor under Contract, or net metering.",
  "nooit": "never",
  "Onder deze accustand komt er niets meer uit, wat de prijzen ook zeggen.": "Below this charge level nothing more comes out, whatever the prices say.",
  "Reserve (%)": "Reserve (%)",
  "Handelen": "Trading",
  "Laden uit het net tijdens lage tarieven.": "Charge from the grid at low prices.",
  "De batterij mag dan ook van het net laden, als dat minder kost dan wat hij je straks bespaart. Staat dit uit, dan gaat er alleen zon in.":
    "The battery may then also charge from the grid, if that costs less than it saves you later. If this is off, only solar goes in.",
  "Alleen als de prijs onder (€/kWh)": "Only when the price is below (€/kWh)",
  "Alleen als het minstens oplevert (€)": "Only when it saves at least (€)",
  "Per beurt van of naar het net, na belasting, verlies en afschrijving. Een verwachting komt niet altijd uit; onder dit bedrag laat hij het. Nul is geen ondergrens.": "Per charge from or delivery to the grid, after tax, losses and wear. A forecast does not always come true; below this amount it skips it. Zero is no minimum.",
  "Alleen als de prijs boven (€/kWh)": "Only when the price is above (€/kWh)",
  "Afschrijving": "Depreciation",
  "Afschrijving (€ per kWh)": "Depreciation (€ per kWh)",
  "geen": "none",
  "Wat elke kWh die uit de batterij komt aan slijtage kost. De coach laadt en ontlaadt pas als het verschil in prijs het verlies in de batterij én dit bedrag dekt. Leeg: alleen het verlies.": "What each kWh out of the battery costs in wear. The coach only charges and discharges when the price difference covers the battery's losses and this amount. Empty: only the losses.",
  "Help me dit uit te rekenen.": "Help me work this out.",
  "Vul de aanschafprijs en het aantal laadcycli van de leverancier in.": "Enter the purchase price and the number of charge cycles the supplier states.",
  "Aanschafprijs (€)": "Purchase price (€)",
  "Ook voor Terugverdiend op de kaart. Zonder laadcycli telt hij niet mee in de afschrijving.": "Also used for Paid back on the card. Without charge cycles it does not count towards depreciation.",
  "Laadcycli volgens de leverancier": "Charge cycles according to the supplier",
  "De coach deelt de aanschafprijs door het aantal cycli maal de capaciteit van de batterij.": "The coach divides the purchase price by the number of cycles times the battery's capacity.",
  "Dat is € {bedrag} per kWh uit de batterij.": "That is € {bedrag} per kWh out of the battery.",
  "de coach bepaalt": "the coach decides",
  "Ontladen naar het net tijdens hoge tarieven.": "Discharge to the grid at high prices.",
  "De batterij mag dan ook naar het net ontladen, als dat meer opbrengt dan het bijladen straks kost. Staat dit uit, dan voedt hij alleen je eigen huis.":
    "The battery may then also discharge to the grid, if that earns more than recharging later costs. If this is off, it only powers your own home.",
  "Een keer per week helemaal vol.": "Completely full once a week.",
  "Tot 100%, voor het balanceren van de cellen. De coach kiest op die dag het goedkoopste moment, en slaat de beurt over als de batterij die week al vol was.":
    "To 100%, for balancing the cells. The coach picks the cheapest moment on that day, and skips it if the battery was already full that week.",
  "Op": "On",
  "Moet eerst vrijgegeven worden.": "Must be released first.",
  "Aan: de coach wacht tot je hem vrijgeeft met \"Ingeruimd en dicht\" op de kaart. Uit: klep dicht is genoeg, en de coach start hem zelf op het goedkoopste moment. Na een beurt wacht hij dan tot de klep open en weer dicht is geweest, zodat hij niet opnieuw start met de schone vaat erin.":
    "On: the coach waits until you release it with \"Loaded and closed\" on the card. Off: a closed door is enough, and the coach starts it itself at the cheapest moment. After a run it then waits until the door has been opened and closed again, so it does not start again with the clean dishes inside.",
  "Aan: de coach wacht tot je hem vrijgeeft met \"{knop}\" op de kaart. Uit: deur dicht is genoeg, en de coach start hem zelf op het goedkoopste moment. Na een beurt wacht hij dan tot de deur open en weer dicht is geweest, zodat hij niet opnieuw start met de schone was erin.":
    "On: the coach waits until you release it with \"{knop}\" on the card. Off: a closed door is enough, and the coach starts it itself at the cheapest moment. After a run it then waits until the door has been opened and closed again, so it does not start again with the clean laundry inside.",
  "Gewenste temperatuur (°C)": "Desired temperature (°C)",
  "wat er op de airco staat": "what the air conditioner is set to",
  "Kouder dan dit: hij verwarmt bij. Warmer: hij koelt bij. Op temperatuur doet hij niets.":
    "Colder than this: it heats. Warmer: it cools. At temperature it does nothing.",
  "Aan op": "Runs on",
  "Zon: alleen met zon over": "Solar: only with spare solar",
  "Goedkope uren: uren onder het daggemiddelde": "Cheap hours: hours below the daily average",
  "Beide: zon over of een goedkoop uur": "Both: spare solar or a cheap hour",
  "De coach zet de airco nooit zomaar aan om de temperatuur te houden: alleen om bij te verwarmen of bij te koelen als er zon over is, of op een uur dat goedkoper is dan gemiddeld, zoals je hier kiest. Bij een vast contract is geen uur goedkoper dan een ander.":
    "The coach never just turns the air conditioner on to hold the temperature: only to heat or cool when there is spare solar, or at an hour that is cheaper than average, as you choose here. With a fixed contract no hour is cheaper than another.",
  "Pauze.": "Pause.",
  "De coach doet niets met de airco. Wat hij zelf aanzette, zet hij uit.": "The coach does nothing with the air conditioner. What it turned on itself, it turns off.",
  // De koppen van de blokken (21-10-2026).
  "Koppeling": "Connection",
  "Sturen": "Control",
  "Hoe de coach hem aanstuurt": "How the coach controls it",
  "Noodstroom": "Backup power",
  "Balanceren": "Balancing",
  "De auto": "The car",
  // Elk onderwerp een blok, en een vinkje bij elke functie (21-10-2026).
  "Wat eraan hangt": "What is plugged in",
  "Modus": "Mode",
  "De coach zet de ventilator aan.": "The coach turns the fan on.",
  "Zodra de batterij warmer is dan de grens, en weer uit een graad eronder. Niet als de coach op Alleen uitlezen of Adviseren staat.": "As soon as the battery is warmer than the limit, and off again one degree below it. Not when the coach is set to Read only or Advise.",
  "Aan boven (°C)": "On above (°C)",
  "Zonder grens staat dit uit.": "Without a limit this is off.",
  "Reserve aanhouden.": "Keep a reserve.",
  "De prijzen zijn all-in, met belasting en opslag. Leeg: de coach kiest zelf de beste uren.": "The prices are all-in, with tax and markup. Empty: the coach picks the best hours itself.",
  "Aan zolang je weg bent.": "On while you are away.",
  "Bij veel zon en weinig verbruik staat een batterij anders dagenlang vol, en dat is slecht voor de cellen. De coach houdt hem onder de grens hieronder en slaat de wekelijkse volle beurt over.": "With lots of sun and little consumption a battery would otherwise stay full for days, and that is bad for the cells. The coach keeps it below the limit below and skips the weekly full charge.",
  "Hoogste accustand (%)": "Highest charge level (%)",
  "De accu mag de auto helpen.": "The battery may help the car.",
  "Laadt de auto, dan geeft de batterij normaal niets af: laden en ontladen van de accu en laden van de auto is drie keer verlies. Met dit aan mag wat boven de grens zit naar de auto. Met de nachtstrategie aan (Voorkeuren) houdt hij altijd genoeg over voor de nacht.": "While the car charges, the battery normally gives nothing: charging and discharging the battery and charging the car is three times loss. With this on, what is above the limit may go to the car. With the night strategy on (Preferences) it always keeps enough for the night.",
  "Boven deze accustand (%)": "Above this charge level (%)",
  "Vrijgeven": "Release",
  "Laadstatus (optioneel)": "Charging status (optional)",
  "Zegt de auto in Home Assistant of hij laadt of in storing staat, wijs die sensor dan aan. Meldt hij een storing terwijl hij wacht, dan start de coach het laden even om hem eruit te halen.": "If the car tells Home Assistant whether it is charging or in a fault, point to that sensor. If it reports a fault while it waits, the coach starts charging briefly to get it out.",
  "Proefladen bij inpluggen": "Test charge when plugged in",
  "Wacht de coach op een goedkoper uur, dan laadt hij eerst even om te zien of de auto stroom aanneemt. Lukt dat niet, dan probeert hij het opnieuw en meldt hij het als het niet lukt. Kost een paar cent.": "If the coach waits for a cheaper hour, it first charges briefly to see whether the car takes power. If not, it tries again and tells you if it still fails. Costs a few cents.",
  "Zoek de laadstatus…": "Search for the charging status…",
};
