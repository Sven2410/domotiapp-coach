"""Foto's bij een ticket voor de DomotiTech Bot (v0.220.0): uploaden en bekijken over HTTP.

De eigenaar op 13-11-2026: bij een ticket "een foto bijvoegen". Een foto past niet over de websocket, dus:

- `POST /api/domotiapp_coach/tickets/bijlage`, ingelogd, multipart met één veld `bestand`. Alleen jpeg, png of
  webp, gekeurd op de eerste bytes (`soort_van` in tickets.py), hoogstens 10 MB. Antwoord `{id, type, grootte}`;
  `new` en `reply` nemen die id mee in `bijlagen`.
- `GET /api/domotiapp_coach/tickets/bijlage/<id>`, ingelogd. De kaart maakt er een plaatje van met een ondertekend
  pad (`auth/sign_path` van Home Assistant zelf), zodat er geen token in de pagina staat.

De bestanden staan in `.storage/domotiapp_coach_bijlagen/`, dus ze overleven een herstart en zitten in de back-up.
Wat erbij hoort (soort, grootte, aan welk ticket) staat in de opslag van de tickets; een foto die na een uur nog
nergens aan hangt gaat weg (`opruimen` in tickets.py).
"""

from __future__ import annotations

import logging
import pathlib
import re
import secrets
from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .taal import t
from .tickets import BIJLAGE_MAX, TicketFout, bijlage_erbij, opruimen, soort_van

try:  # Home Assistant 2024.6 en nieuwer
    from homeassistant.components.http import KEY_HASS
except ImportError:  # pragma: no cover - oudere uitvoeringen
    KEY_HASS = "hass"  # type: ignore[assignment]

_LOGGER = logging.getLogger(__name__)

URL = "/api/domotiapp_coach/tickets/bijlage"
MAP = "domotiapp_coach_bijlagen"
_ID = re.compile(r"^[0-9a-f]{32}$")


def map_van(hass: HomeAssistant) -> pathlib.Path:
    """Waar de foto's van deze installatie staan."""
    return pathlib.Path(hass.config.path(".storage", MAP))


def _schrijf(pad: pathlib.Path, inhoud: bytes) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    tijdelijk = pad.with_suffix(".deel")
    tijdelijk.write_bytes(inhoud)
    tijdelijk.replace(pad)


def _weg(map_: pathlib.Path, ids: list[str]) -> None:
    for bijlage_id in ids:
        if _ID.match(bijlage_id):
            (map_ / bijlage_id).unlink(missing_ok=True)


async def async_opruimen(hass: HomeAssistant) -> None:
    """Foto's die al een uur nergens aan hangen weghalen, uit de opslag en van de schijf."""
    from .storage import async_get_tickets

    try:
        weg = await async_get_tickets(hass).async_wijzig(lambda data: opruimen(data, dt_util.now()))
        if weg:
            await hass.async_add_executor_job(_weg, map_van(hass), weg)
    except Exception:  # noqa: BLE001 - opruimen mag een upload of een vraag niet kosten
        _LOGGER.exception("kon de losse foto's van de tickets niet opruimen")


class BijlageUploadView(HomeAssistantView):
    """Een foto erbij; het antwoord is wat `new` en `reply` meenemen."""

    url = URL
    name = "api:domotiapp_coach:tickets:bijlage"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        from .storage import async_get_tickets

        hass = request.app[KEY_HASS]
        reader = await request.multipart()
        veld = await reader.next()
        while veld is not None and getattr(veld, "name", None) != "bestand":
            veld = await reader.next()
        if veld is None:
            return self.json_message(t("Er zit geen foto in (veld bestand)."), 400)
        inhoud = bytearray()
        while True:
            stuk = await veld.read_chunk(65536)
            if not stuk:
                break
            inhoud += stuk
            if len(inhoud) > BIJLAGE_MAX:
                return self.json_message(t("Een foto is hoogstens {mb} MB.", mb=BIJLAGE_MAX // (1024 * 1024)), 413)
        soort = soort_van(bytes(inhoud))
        if soort is None:
            return self.json_message(t("Alleen een foto: jpeg, png of webp."), 415)
        bijlage_id = secrets.token_hex(16)
        await hass.async_add_executor_job(_schrijf, map_van(hass) / bijlage_id, bytes(inhoud))
        try:
            uit = await async_get_tickets(hass).async_wijzig(
                lambda data: bijlage_erbij(data, bijlage_id, soort, len(inhoud), dt_util.now()))
        except TicketFout as fout:
            await hass.async_add_executor_job(_weg, map_van(hass), [bijlage_id])
            return self.json_message(str(fout), 400)
        await async_opruimen(hass)
        return self.json(uit)


class BijlageView(HomeAssistantView):
    """Een foto bekijken."""

    url = URL + "/{bijlage_id}"
    name = "api:domotiapp_coach:tickets:bijlage:id"
    requires_auth = True

    async def get(self, request: web.Request, bijlage_id: str) -> web.Response:
        from .storage import async_get_tickets

        hass = request.app[KEY_HASS]
        if not _ID.match(bijlage_id):
            return web.Response(status=404)
        rij = ((await async_get_tickets(hass).async_data()).get("bijlagen") or {}).get(bijlage_id)
        pad = map_van(hass) / bijlage_id
        if rij is None:
            return web.Response(status=404)
        try:
            inhoud = await hass.async_add_executor_job(pad.read_bytes)
        except OSError:
            return web.Response(status=404)
        return web.Response(body=inhoud, content_type=rij.get("type") or "application/octet-stream",
                            headers={"Cache-Control": "private, max-age=86400"})


def async_register(hass: HomeAssistant) -> None:
    """Zet de twee wegen klaar, één keer per Home Assistant."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("bijlage_views"):
        return
    hass.http.register_view(BijlageUploadView())
    hass.http.register_view(BijlageView())
    domain_data["bijlage_views"] = True
