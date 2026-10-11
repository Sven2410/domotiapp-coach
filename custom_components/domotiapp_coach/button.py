"""De knoppen van de vaatwasserkaart (v0.110.0).

De eigenaar op 11-10-2026, over de knoppen "Ingeruimd, morgen starten" en
"Ingeruimd, nu starten" in het paneel: "Dat moet ook op de vaatwasser kaart
komen." Dezelfde som als die knoppen (`async_vrijgave` in entiteit.py), voor
elk apparaat met een programma, en meteen een ronde erachteraan. Zie
entiteit.py voor het contract met de kaarten.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import PROGRAMMA_TYPES
from .entiteit import CoachEntiteit, async_per_apparaat, async_vrijgave, coach_verversen

# sleutel: (vrijgeven, nu starten, icoon)
KNOPPEN = {
    "ingeruimd_morgen": (True, False, "mdi:calendar-clock"),
    "ingeruimd_nu": (True, True, "mdi:play-circle-outline"),
    "vrijgave_intrekken": (False, None, "mdi:close-circle-outline"),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    await async_per_apparaat(
        hass, entry, async_add_entities,
        lambda device: device.get("type") in PROGRAMMA_TYPES,
        lambda device, stand, settings: [VrijgaveKnop(device, stand, sleutel) for sleutel in KNOPPEN],
    )


class VrijgaveKnop(CoachEntiteit, ButtonEntity):
    """Ingeruimd en op het goedkoopste moment starten, ingeruimd en nu, of toch niet."""

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None, sleutel: str) -> None:
        super().__init__(device, stand, sleutel)
        self._vrij, self._nu, self._attr_icon = KNOPPEN[sleutel]

    async def async_press(self) -> None:
        await async_vrijgave(self.hass, self._device_id, self._vrij, self._nu)
        coach_verversen(self.hass)
