"""Het rapport afleveren als een gewone download.

Het paneel maakt de pdf zelf, in de browser. Het lag dus voor de hand om hem daar
ook meteen aan te bieden, met een `blob:` en een downloadkoppeling. Op een
computer werkt dat prima, maar in de Home Assistant app niet: een webweergave is
geen browser en kan zo'n adres niet zelf ophalen. Er kwam wel een bestand uit,
maar het was er geen dat open ging. Precies wat er gemeld werd.

Daarom gaat de pdf hier langs. Het paneel stuurt hem over de websocket naar Home
Assistant, krijgt een gewoon webadres terug, en gaat daarheen. Voor de telefoon
is dat niet te onderscheiden van het downloaden van een pdf op welke website dan
ook, en dat is nou juist iets wat elk apparaat kan.

Wat hier bewust niet gebeurt is opslaan op schijf. Een rapport is een momentopname
die de klant meteen bewaart of doorstuurt; het een tweede keer bewaren op de
machine van iemand anders levert alleen een map op die volloopt met de
energiegegevens van vorige maand.
"""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Hoe lang een adres blijft werken. Ruim genoeg voor een telefoon die er even
# over doet, kort genoeg dat een rapport niet blijft rondslingeren.
TTL_SECONDS = 300

# Hoeveel rapporten er hoogstens tegelijk klaarstaan. Meer dan een handvol
# betekent dat er iets misgaat, en dan is vergeten beter dan volhouden.
MAX_REPORTS = 5

# Een rapport van een heel jaar is een paar honderd kilobyte. Alles daarboven is
# geen rapport meer en hoort niet in het geheugen van iemands woning.
MAX_BYTES = 20 * 1024 * 1024

URL = "/api/domotiapp_coach/report/{token}"


def _reports(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """De rapporten die op dit moment klaarstaan."""
    return hass.data.setdefault(DOMAIN, {}).setdefault("reports", {})


def async_put(hass: HomeAssistant, pdf: bytes, filename: str) -> str:
    """Leg een rapport klaar en geef het adres terug waar het op te halen is."""
    reports = _reports(hass)
    now = time.monotonic()

    # Alles wat over tijd is gaat eruit, en als het er dan nog te veel zijn de
    # oudste. Zonder dat groeit dit bij elke druk op de knop.
    for token in [t for t, r in reports.items() if r["expires"] <= now]:
        reports.pop(token, None)
    while len(reports) >= MAX_REPORTS:
        reports.pop(min(reports, key=lambda t: reports[t]["expires"]), None)

    token = secrets.token_urlsafe(32)
    reports[token] = {
        "pdf": pdf,
        "filename": filename,
        "expires": now + TTL_SECONDS,
    }
    return URL.format(token=token)


class ReportView(HomeAssistantView):
    """Serveert één rapport, één keer.

    Het adres is niet te raden en is alleen te krijgen door er over een
    aangemelde websocket om te vragen. Zelf vraagt deze weg niet nog eens om
    aanmelden, en dat is met opzet: de download wordt gestart door de webweergave
    van de app, en die stuurt de aanmeldgegevens van het paneel niet mee. Een weg
    die dat wel eist, is precies de weg die op een telefoon niets oplevert.

    Wat het veilig houdt is dat het adres eenmalig is, na vijf minuten vervalt,
    en verdwijnt zodra het is opgehaald.
    """

    url = URL
    name = "api:domotiapp_coach:report"
    requires_auth = False

    async def get(self, request: web.Request, token: str) -> web.Response:
        """Geef de pdf terug, en vergeet hem daarna."""
        reports = _reports(request.app["hass"])
        report = reports.pop(token, None)

        if report is None or report["expires"] <= time.monotonic():
            return web.Response(status=404, text="Dit rapport is niet meer beschikbaar.")

        return web.Response(
            body=report["pdf"],
            content_type="application/pdf",
            headers={
                # Zonder deze regel toont een browser de pdf alleen; met deze
                # regel biedt hij hem aan om te bewaren, onder de naam die de
                # klant op zijn telefoon terugziet.
                "Content-Disposition": f'attachment; filename="{report["filename"]}"',
                "Cache-Control": "no-store",
            },
        )


def async_register(hass: HomeAssistant) -> None:
    """Zet de weg klaar, één keer per Home Assistant."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("report_view"):
        return

    hass.http.register_view(ReportView())
    domain_data["report_view"] = True
    _LOGGER.debug("DomotiApp Coach kan rapporten afleveren op %s", URL)
