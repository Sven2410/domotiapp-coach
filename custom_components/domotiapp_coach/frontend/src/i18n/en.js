/**
 * Het Engels van het paneel (v0.139.0): de Nederlandse zin als sleutel, de Engelse als
 * waarde. Per deel van het paneel een eigen bestand in en/, zodat ze naast elkaar te
 * vullen zijn. Een zin die in twee delen voorkomt moet daar hetzelfde vertaald zijn; de
 * proef "elke zin heeft een vertaling" in test_rapport.mjs kijkt dat na. Schrijfwijze en
 * woordenlijst: docs/taal.md.
 */

import { ALGEMEEN } from "./en/algemeen.js";
import { APPARATEN } from "./en/apparaten.js";
import { CONTRACT } from "./en/contract.js";
import { HISTORIE } from "./en/historie.js";
import { INSTELLINGEN } from "./en/instellingen.js";
import { OVERIG } from "./en/overig.js";
import { OVERZICHT } from "./en/overzicht.js";

/** De delen apart, voor de proef die kijkt of een zin overal hetzelfde vertaald is. */
export const DELEN = { ALGEMEEN, APPARATEN, CONTRACT, HISTORIE, INSTELLINGEN, OVERIG, OVERZICHT };

export const EN = Object.assign({}, ...Object.values(DELEN));
