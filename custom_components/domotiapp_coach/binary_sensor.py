"""Of een apparaat met een programma vrijgegeven is (v0.110.0).

Voor de vaatwasserkaart: de waarheid is de vrijgave in de coach zelf
(`ready_devices`). De vrijgaveschakelaar van de klant is een ingang die de
coach leest en na een beurt weer uitzet; zie `_async_schakelaar_volgen` in
coach.py. Zie entiteit.py voor het contract met de kaarten.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import PROGRAMMA_TYPES
from .entiteit import CoachEntiteit, ProgrammaBediening, async_per_apparaat


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    await async_per_apparaat(
        hass, entry, async_add_entities,
        lambda device: device.get("type") in PROGRAMMA_TYPES,
        lambda device, stand, settings: [VrijgegevenSensor(device, stand)],
    )


class VrijgegevenSensor(ProgrammaBediening, CoachEntiteit, BinarySensorEntity):
    """Aan als het apparaat ingeruimd en vrijgegeven is; niet beschikbaar bij alleen uitlezen (v0.127.0)."""

    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None) -> None:
        super().__init__(device, stand, "vrijgegeven")

    def _kern(self) -> Any:
        return self.is_on

    @property
    def is_on(self) -> bool:
        return bool(self._stand.get("released"))
