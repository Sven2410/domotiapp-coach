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
from .entiteit import LEEG_TOT, AccuBediening, CoachEntiteit, async_per_apparaat, async_vrijgave, coach_verversen

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
    # De thuisbatterij (v0.112.0).
    await async_per_apparaat(
        hass, entry, async_add_entities,
        lambda device: device.get("type") == "thuisbatterij",
        lambda device, stand, settings: [BatterijKnop(device, stand, sleutel) for sleutel in ACCU_KNOPPEN],
    )


class VrijgaveKnop(CoachEntiteit, ButtonEntity):
    """Ingeruimd en op het goedkoopste moment starten, ingeruimd en nu, of toch niet."""

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None, sleutel: str) -> None:
        super().__init__(device, stand, sleutel)
        self._vrij, self._nu, self._attr_icon = KNOPPEN[sleutel]

    async def async_press(self) -> None:
        await async_vrijgave(self.hass, self._device_id, self._vrij, self._nu)
        coach_verversen(self.hass)


ACCU_KNOPPEN = {
    "vol_laden": "mdi:battery-arrow-up",
    "leegladen": "mdi:battery-arrow-down",
    "terug_naar_plan": "mdi:calendar-sync",
}


class BatterijKnop(AccuBediening, CoachEntiteit, ButtonEntity):
    """Nu vol laden, nu leegladen (tot `leeg_tot`), of terug naar het plan (v0.112.0).

    Dezelfde knoppen als op de batterijkaart van de coach (`async_boost`,
    `async_drain`); vol en leeg gaan vanzelf uit op hun doel.
    """

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None, sleutel: str) -> None:
        super().__init__(device, stand, sleutel)
        self._sleutel = sleutel
        self._attr_icon = ACCU_KNOPPEN[sleutel]

    async def async_press(self) -> None:
        from .coach import async_get_coach

        coach = async_get_coach(self.hass)
        if self._sleutel == "vol_laden":
            coach.async_boost(self._device_id, True)
        elif self._sleutel == "leegladen":
            ondergrens = float(self._stand.get("floor") or 0.0)
            coach.async_drain(self._device_id, max(ondergrens, LEEG_TOT.get(self._device_id, ondergrens)))
        else:
            coach.async_boost(self._device_id, False)
            coach.async_drain(self._device_id, None)
