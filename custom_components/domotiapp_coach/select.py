"""De modus van een laadbeurt, voor de laadpaalkaart (v0.111.0).

Dezelfde knoppen als op de coachkaart: Planning, Snel, Continu, Zon. Ze gelden
voor deze beurt en vervallen als de kabel eruit gaat (`async_mode` in coach.py).
Zie entiteit.py voor het contract met de kaarten.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entiteit import PAAL_MODI, CoachEntiteit, async_per_apparaat


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    await async_per_apparaat(
        hass, entry, async_add_entities,
        lambda device: device.get("type") == "laadpaal",
        lambda device, stand, settings: [ModusSelect(device, stand)],
    )


class ModusSelect(CoachEntiteit, SelectEntity):
    """Planning, Snel, Continu of Zon, voor deze beurt."""

    _attr_icon = "mdi:ev-plug-type2"
    _attr_options = list(PAAL_MODI)

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None) -> None:
        super().__init__(device, stand, "modus")

    def _kern(self) -> Any:
        return self.current_option

    @property
    def current_option(self) -> str:
        modus = str(self._stand.get("mode") or "goedkoopst")
        return modus if modus in PAAL_MODI else "planning"

    async def async_select_option(self, option: str) -> None:
        from .coach import async_get_coach

        async_get_coach(self.hass).async_mode(self._device_id, PAAL_MODI.get(option, "goedkoopst"))
