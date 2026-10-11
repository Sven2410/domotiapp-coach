"""Pauze en het schema van een laadpaal, voor de laadpaalkaart (v0.111.0).

Pauze gaat door de coach heen (`async_pause`), zodat hij het laden niet een
minuut later weer aanzet; hij vervalt als de kabel eruit gaat. Het schema is de
planning met een klaar-tijd, aan of uit, zoals de schuif op de coachkaart.
Zie entiteit.py voor het contract met de kaarten.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entiteit import CoachEntiteit, async_per_apparaat, async_schema, paal_schema


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    await async_per_apparaat(
        hass, entry, async_add_entities,
        lambda device: device.get("type") == "laadpaal",
        lambda device, stand, settings: [PauzeSwitch(device, stand), SchemaSwitch(device, stand, settings)],
    )


class PauzeSwitch(CoachEntiteit, SwitchEntity):
    """Met de hand pauzeren, via de coach."""

    _attr_icon = "mdi:pause-circle-outline"

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None) -> None:
        super().__init__(device, stand, "pauze")

    def _kern(self) -> Any:
        return self.is_on

    @property
    def is_on(self) -> bool:
        return bool(self._stand.get("paused"))

    async def async_turn_on(self, **_kwargs: Any) -> None:
        from .coach import async_get_coach

        async_get_coach(self.hass).async_pause(self._device_id, True)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        from .coach import async_get_coach

        async_get_coach(self.hass).async_pause(self._device_id, False)


class SchemaSwitch(CoachEntiteit, SwitchEntity):
    """De planning met een klaar-tijd aan of uit."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None, settings: dict[str, Any]) -> None:
        super().__init__(device, stand, "schema", settings)

    @property
    def is_on(self) -> bool:
        return paal_schema(self._settings, self._device_id)["schema_aan"]

    async def async_turn_on(self, **_kwargs: Any) -> None:
        await async_schema(self.hass, self._device_id, enabled=True)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        await async_schema(self.hass, self._device_id, enabled=False)
