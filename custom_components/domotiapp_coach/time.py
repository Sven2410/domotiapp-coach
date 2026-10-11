"""De klaar-tijd van een laadpaal voor elke dag, voor de laadpaalkaart (v0.111.0).

Een laadpaal kent alleen "klaar om" (eis 5). Staat het schema per dag, dan
geldt deze tijd niet en is hij `unavailable`: dan biedt geen kaart of
automatisering een tijd aan die niets doet. Het weekschema staat op de sensor
van de coach (`schema_dagen`) en wordt in de coach bewerkt.
"""

from __future__ import annotations

from datetime import time
from typing import Any

from homeassistant.components.time import TimeEntity
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
        lambda device, stand, settings: [KlaarOmTime(device, stand, settings)],
    )


class KlaarOmTime(CoachEntiteit, TimeEntity):
    """Klaar om, elke dag dezelfde tijd."""

    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None, settings: dict[str, Any]) -> None:
        super().__init__(device, stand, "klaar_om", settings)

    @property
    def available(self) -> bool:
        return not paal_schema(self._settings, self._device_id)["per_dag"]

    @property
    def native_value(self) -> time | None:
        tekst = paal_schema(self._settings, self._device_id)["klaar_om"]
        try:
            uur, minuut = (int(deel) for deel in str(tekst).split(":")[:2])
            return time(uur, minuut)
        except (TypeError, ValueError):
            return None

    async def async_set_value(self, value: time) -> None:
        # Alle drie de tijden tegelijk, zoals `domotiapp_coach/device/schedule`
        # het vraagt; van een laadpaal blijven de twee andere leeg (eis 5).
        await async_schema(
            self.hass, self._device_id,
            window={"not_before": "", "start_by": "", "done_by": f"{value.hour:02d}:{value.minute:02d}"},
        )
