"""Tot hoeveel procent deze beurt laadt, voor de laadpaalkaart (v0.111.0).

Hetzelfde als "laden tot" op de coachkaart (`async_target`): voor deze beurt,
daarna weer het doel uit het autoprofiel. De laadgrens in de auto zelf blijft
de bovengrens.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entiteit import LEEG_TOT, CoachEntiteit, async_per_apparaat


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    await async_per_apparaat(
        hass, entry, async_add_entities,
        lambda device: device.get("type") == "laadpaal",
        lambda device, stand, settings: [LadenTotNumber(device, stand)],
    )
    # De thuisbatterij (v0.112.0).
    await async_per_apparaat(
        hass, entry, async_add_entities,
        lambda device: device.get("type") == "thuisbatterij",
        lambda device, stand, settings: [LeegTotNumber(device, stand)],
    )


class LadenTotNumber(CoachEntiteit, NumberEntity):
    """Laden tot (%), voor deze beurt."""

    _attr_icon = "mdi:battery-charging-80"
    _attr_native_min_value = 10
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "%"

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None) -> None:
        super().__init__(device, stand, "laden_tot")

    def _kern(self) -> Any:
        return self.native_value

    @property
    def native_value(self) -> float | None:
        waarde = self._stand.get("target_percent")
        return None if waarde is None else float(waarde)

    async def async_set_native_value(self, value: float) -> None:
        from .coach import async_get_coach

        async_get_coach(self.hass).async_target(self._device_id, float(value))


class LeegTotNumber(CoachEntiteit, NumberEntity):
    """Tot welk % "leegladen" gaat (v0.112.0); nooit onder de ondergrens van de batterij.

    Leeg is die ondergrens. Het getal staat in het geheugen van de coach en is na
    een herstart weer de ondergrens; de knop leest het op het moment dat je drukt.
    """

    _attr_icon = "mdi:battery-low"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "%"

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None) -> None:
        super().__init__(device, stand, "leeg_tot")

    def _kern(self) -> Any:
        return self.native_value

    @property
    def native_value(self) -> float:
        ondergrens = float(self._stand.get("floor") or 0.0)
        return max(ondergrens, LEEG_TOT.get(self._device_id, ondergrens))

    async def async_set_native_value(self, value: float) -> None:
        LEEG_TOT[self._device_id] = max(float(self._stand.get("floor") or 0.0), float(value))
        self._schrijf()
