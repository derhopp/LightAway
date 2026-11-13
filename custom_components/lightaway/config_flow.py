"""Configure a single LightAway instance in the integrations UI."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class LightAwayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """LightAway setup flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """No credentials; all preferences are maintained in the dashboard card."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="LightAway", data={})
        return self.async_show_form(step_id="user")
