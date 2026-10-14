"""Tot hoeveel procent deze beurt laadt, voor de laadpaalkaart (v0.111.0).

Hetzelfde als "laden tot" op de coachkaart (`async_target`): voor deze beurt,
daarna weer het doel uit het autoprofiel. De laadgrens in de auto zelf blijft
de bovengrens.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entiteit import LEEG_TOT, CoachEntiteit, async_accustand, async_per_apparaat, coach_verversen


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    await async_per_apparaat(
        hass, entry, async_add_entities,
        lambda device: device.get("type") == "laadpaal",
        lambda device, stand, settings: [LadenTotNumber(device, stand), AccustandNumber(device, stand, settings)],
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


class AccustandNumber(CoachEntiteit, NumberEntity):
    """Hoe vol de auto nu is, als hij het zelf niet zegt (v0.117.0).

    Hetzelfde als "Hoe vol is de auto nu?" op de coachkaart, en het bewaart via
    dezelfde weg (`async_accustand`). De eigenaar op 14-10-2026, met de integratie
    van de auto even uit Home Assistant: "ja ook op de lovelace kaart wil ik die."

    De toestand is na een opgave de stand waar de coach nu mee rekent, die
    meeloopt met wat de paal erin doet; zonder opgave onbekend (`socVeld` in
    devices.js). De kaart toont het veld alleen bij `vragen` (`soc_ask` in
    coach.py); `wacht` is dat de coach erop wacht, `sensor` dat de auto een
    accusensor in zijn profiel heeft, voor de uitleg.
    """

    _attr_icon = "mdi:car-battery"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.BOX

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None, settings: dict[str, Any]) -> None:
        super().__init__(device, stand, "accustand", settings)

    def _kern(self) -> Any:
        return (self.native_value, repr(self.extra_state_attributes))

    def _opgave(self) -> dict[str, Any] | None:
        return next(
            (
                row
                for row in (self._settings.get("car_soc") or [])
                if isinstance(row, dict) and row.get("device") == self._device_id
            ),
            None,
        )

    @property
    def native_value(self) -> float | None:
        opgave = self._opgave()
        if opgave is None or opgave.get("percent") is None:
            return None
        nu = self._stand.get("soc_now")
        return float(round(float(nu if nu is not None else opgave["percent"])))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "vragen": bool(self._stand.get("soc_ask")),
            "wacht": bool(self._stand.get("needs_soc")),
            "sensor": bool(self._stand.get("soc_sensor")),
        }

    async def async_set_native_value(self, value: float) -> None:
        from .coach import async_get_coach

        # De auto die de coach kiest, en zonder keuze de eerste, zoals de
        # coachkaart (`activeCar_` of de eerste uit `carsFor`).
        _, profiel = async_get_coach(self.hass)._chosen_car(self._settings, self._device)
        auto = profiel or next(iter(self._device.get("cars") or []), None) or {}
        await async_accustand(self.hass, self._device_id, str(auto.get("id") or ""), float(value))
        coach_verversen(self.hass)


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
