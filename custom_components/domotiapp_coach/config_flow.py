"""Config flow for the DomotiApp Coach integration.

Setup asks nothing: every setting lives in the panel's own Instellingen section,
so adding the integration is a single confirmation and the customer configures
the rest from the dashboard itself.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN, PANEL_TITLE


class DomotiAppCoachConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding the panel."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title=PANEL_TITLE, data={})

        return self.async_show_form(step_id="user")
