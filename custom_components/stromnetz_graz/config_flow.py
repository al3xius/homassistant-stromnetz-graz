from homeassistant import config_entries, exceptions
import voluptuous as vol
from .const import DOMAIN
import logging
from homeassistant.core import HomeAssistant
from typing import Any

from .api import StromNetzGrazAPI, InvalidAuth

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    vol.Required("username", description="Username"): str,
    vol.Required("password", description="Password"): str,
    }
)

async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    # Try to login
    api = StromNetzGrazAPI(hass, data["username"], data["password"])

    await api.login()
    await api.setupMeter(None)


    return {"address": api.address, "username": data["username"], "password": data["password"]}

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """StromNetzGraz config flow."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""

        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["address"], data=user_input)
            except InvalidAuth:
                _LOGGER.error("Invalid Credentials!")
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # If there is no user input or there were errors, show the form again, including any errors that were found with the input.
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors, last_step=True
        )
