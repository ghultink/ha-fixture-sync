"""Config flow for Fixture Sync."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_CALENDAR_ENTITY,
    CONF_COMPETITION,
    CONF_EVENT_HOURS,
    CONF_TEAM,
    DEFAULT_EVENT_HOURS,
    DOMAIN,
)


class FixtureSyncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fixture Sync."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            title = f"{user_input[CONF_TEAM]} ({user_input[CONF_COMPETITION]})"
            await self.async_set_unique_id(
                f"{user_input[CONF_COMPETITION]}::{user_input[CONF_TEAM].lower()}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_COMPETITION, default="la-liga-2025"): TextSelector(),
            vol.Required(CONF_TEAM, default="Real Madrid"): TextSelector(),
            vol.Required(CONF_CALENDAR_ENTITY): EntitySelector(
                EntitySelectorConfig(domain="calendar")
            ),
            vol.Required(CONF_EVENT_HOURS, default=DEFAULT_EVENT_HOURS): NumberSelector(
                NumberSelectorConfig(min=1, max=6, step=1, mode=NumberSelectorMode.BOX)
            ),
        })
        return self.async_show_form(step_id="user", data_schema=schema)
