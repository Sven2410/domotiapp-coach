"""De modus van een laadbeurt, voor de laadpaalkaart (v0.111.0).

Dezelfde knoppen als op de coachkaart: Snel, Continu, Zon, en Planning als
toestand (de planning zet het schema aan, `modus_keuzes`). Ze gelden voor deze
beurt en vervallen als de kabel eruit gaat (`async_mode` in coach.py). Nog een
keer de modus die al geldt kiezen gaat terug naar de voorkeur, zoals op de
coachkaart (v0.112.3). Zie entiteit.py voor het contract met de kaarten.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entiteit import PAAL_MODI, CoachEntiteit, async_airco_veld, async_per_apparaat, paal_modus_actief
from .planner import AIRCO_AAN_OP


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    await async_per_apparaat(
        hass, entry, async_add_entities,
        lambda device: device.get("type") == "laadpaal",
        lambda device, stand, settings: [ModusSelect(device, stand)],
    )
    # De airco (v0.119.1): waarop hij aan mag.
    await async_per_apparaat(
        hass, entry, async_add_entities,
        lambda device: device.get("type") == "airco",
        lambda device, stand, settings: [AanOpSelect(device, stand)],
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
        # Wat er echt geldt, niet de voorkeur van de paal: met een planning is dat
        # Planning, ook als de paal op Zon staat (v0.111.1).
        return paal_modus_actief(self._stand)

    async def async_select_option(self, option: str) -> None:
        from .coach import async_get_coach

        coach = async_get_coach(self.hass)
        if option == self.current_option and (option == "snel" or self._stand.get("mode_session")):
            # Nog een keer op de knop die aan staat: terug naar de voorkeur (v0.112.3).
            # Met een planning is Snel de enige knop, en anders kreeg je hem van de
            # kaart niet meer uit tot de kabel eruit ging.
            coach.async_mode(self._device_id, "")
            return
        coach.async_mode(self._device_id, PAAL_MODI.get(option, "goedkoopst"))


class AanOpSelect(CoachEntiteit, SelectEntity):
    """Waarop de airco aan mag: zon over, goedkope uren, of beide (v0.119.1).

    De eigenaar op 14-10-2026: "goedkoop uur mag de bewoner zelf kiezen dus 3
    opties of op zon of goedkope uren of beide." Standaard zon. Hetzelfde veld
    als in Instellen achter de kaart (`run_on` in `airco`); zie docs/airco.md.
    """

    _attr_icon = "mdi:air-conditioner"
    _attr_options = list(AIRCO_AAN_OP)

    def __init__(self, device: dict[str, Any], stand: dict[str, Any] | None) -> None:
        super().__init__(device, stand, "aan_op")

    def _kern(self) -> Any:
        return self.current_option

    @property
    def current_option(self) -> str:
        keuze = (self._device.get("airco") or {}).get("run_on")
        return keuze if keuze in AIRCO_AAN_OP else AIRCO_AAN_OP[0]

    async def async_select_option(self, option: str) -> None:
        if option in AIRCO_AAN_OP:
            await async_airco_veld(self.hass, self._device_id, "run_on", option)
