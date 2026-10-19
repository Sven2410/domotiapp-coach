/** Het Engels van een deel van het paneel (v0.140.0, stap 3); zie docs/taal.md. */
export const RAPPORT = {
  // report.js: de koppen, de legenda en de voetregel
  "Verloop": "Over time",
  "Vermogen en pieken": "Power and peaks",
  "Verloop per {korrel}": "Breakdown per {korrel}",
  "Alle cijfers": "All figures",
  "Bladzijde {n}": "Page {n}",
  "{naam} (vervolg)": "{naam} (continued)",
  "{woning}, gemaakt op {datum}": "{woning}, created on {datum}",
  "Gemaakt op {datum}": "Created on {datum}",

  // views/history.js: de kop van het rapport en de bestandsnaam
  "Grafiek per {grafiek}, verloop per {verloop}": "Chart per {grafiek}, breakdown per {verloop}",
  "Per {korrel}": "Per {korrel}",
  "Beknopt": "Short",
  "beknopt": "short",

  // views/history.js: Alle cijfers en Per apparaat
  "Kosten": "Cost",
  "Totaal": "Total",
  "Verbruik": "Consumption",
  "Aandeel": "Share",
  "{naam} (bij benadering)": "{naam} (approximate)",
  "Van apparaten zonder eigen energieteller wordt het verbruik afgeleid uit het gemiddelde vermogen.":
    "For devices without their own energy meter, consumption is derived from the average power.",
  "Dat is nauwkeurig genoeg om te zien waar je stroom heen gaat, maar het is geen meterstand.":
    "That is accurate enough to see where your electricity goes, but it is not a meter reading.",
  "Vul bij Apparaten een energieteller in als je die hebt, dan klopt het tot op de komma.":
    "If you have an energy meter, add it under Devices and the figures will be exact.",
  "Deze schattingen tellen samen op tot meer dan het verbruik van de woning, dus staat er geen aandeel bij.":
    "Together these estimates add up to more than the home used, so no share is shown.",

  // views/history.js: Bespaard
  "Door de zon": "From solar",
  "Door te wachten": "From waiting",
  "Waarvan zon": "Of which solar",
  "Accu": "Battery",
  "Door zon": "From solar",
  "Eén sessie telt niet mee in het geld, omdat de prijs toen niet bekend was.":
    "One session is not counted in the money, because the price was not known at the time.",
  "{n} sessies tellen niet mee in het geld, omdat de prijs toen niet bekend was.":
    "{n} sessions are not counted in the money, because the price was not known at the time.",

  // views/history.js: Vermogen en pieken
  "Het net": "The grid",
  "Zon {n}": "Solar {n}",
  "Laagste": "Lowest",
  "Gemiddeld": "Average",
  "Piek op": "Peak at",
  "Per kwartier wordt het laagste, het gemiddelde en de piek bewaard, twee jaar lang.":
    "For every quarter hour the lowest, the average and the peak are kept, for two years.",
  "De piek is de hoogste waarde die de sensor zelf gemeld heeft, dus zo scherp als je meter meet.":
    "The peak is the highest value the sensor itself reported, so as sharp as your meter measures.",
  "Het gemiddelde weegt naar tijd en niet naar het aantal metingen.":
    "The average is weighted by time, not by the number of readings.",
  "Deze geschiedenis begint op de dag dat de coach hem is gaan bijhouden; wat daarvoor ligt is overgenomen uit Home Assistant voor zover dat er nog was.":
    "This history starts on the day the coach began keeping it; anything before that was taken from Home Assistant as far as it was still there.",
  "Bij Het net is een plus wat er van het net kwam en een min wat er naartoe ging.":
    "In the row The grid, a plus is what came from the grid and a minus what went to it.",

  // views/history.js: het verloop per kwartier, uur, dag of maand (KORRELS)
  "Elk kwartier van deze dag, met het laagste, het gemiddelde en de piek.":
    "Every quarter hour of this day, with the lowest, the average and the peak.",
  "De piek is de hoogste waarde die de sensor binnen dat kwartier gemeld heeft, dus zo scherp als je meter meet.":
    "The peak is the highest value the sensor reported within that quarter hour, so as sharp as your meter measures.",
  "Kwartieren waarin de sensor niets liet horen staan er niet in.":
    "Quarter hours in which the sensor reported nothing are left out.",
  "Elk uur van deze week, samengesteld uit de kwartieren eronder.":
    "Every hour of this week, built from its quarter hours.",
  "De piek is de hoogste waarde binnen dat uur.": "The peak is the highest value within that hour.",
  "Wil je het fijner of grover, kies dan een andere korrel boven de grafiek.":
    "For more or less detail, choose another breakdown above the chart.",
  "Elke dag van deze maand, samengesteld uit de kwartieren eronder.":
    "Every day of this month, built from its quarter hours.",
  "De piek is de hoogste waarde die er die dag in een kwartier stond.":
    "The peak is the highest value of any quarter hour that day.",
  "Elke maand van dit jaar, samengesteld uit de kwartieren eronder.":
    "Every month of this year, built from its quarter hours.",
  "De piek is de hoogste waarde die er die maand in een kwartier stond.":
    "The peak is the highest value of any quarter hour that month.",
};
