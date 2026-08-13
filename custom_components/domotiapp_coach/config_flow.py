"""Config flow for the DomotiApp Coach integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    CONF_DEMO_MODE,
    CONF_HOME_PATH,
    DEFAULT_DEMO_MODE,
    DEFAULT_HOME_PATH,
    DOMAIN,
    PANEL_TITLE,
)


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the options schema pre-filled with the current values."""
    return vol.Schema(
        {
            vol.Required(
                CONF_HOME_PATH,
                default=defaults.get(CONF_HOME_PATH, DEFAULT_HOME_PATH),
            ): str,
            vol.Required(
                CONF_DEMO_MODE,
                default=defaults.get(CONF_DEMO_MODE, DEFAULT_DEMO_MODE),
            ): bool,
        }
    )


class DomotiAppCoachConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the setup step shown in the UI."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title=PANEL_TITLE, data=user_input)

        return self.async_show_form(step_id="user", data_schema=_options_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return DomotiAppCoachOptionsFlow()


class DomotiAppCoachOptionsFlow(OptionsFlow):
    """Handle changing the options after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=_options_schema(defaults)
        )
