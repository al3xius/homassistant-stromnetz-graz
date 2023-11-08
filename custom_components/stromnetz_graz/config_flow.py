from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN
import logging
from homeassistant.core import HomeAssistant
from typing import Any, Optional, Dict
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import StromNetzGrazAPI, AuthException

_LOGGER = logging.getLogger(__name__)

CREDENTIALS_DATA_SCHEMA = vol.Schema({
    vol.Required("email", description="Email"): str,
    vol.Required("password", description="Password"): str,
    }
)

async def validate_credentials(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    # Try to login
    api = StromNetzGrazAPI(data["email"], data["password"])

    await api.token_request()

    return {"email": data["email"], "password": data["password"]}

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
        StromNetzGraz config flow.
        Step 1: Credentials
        Step 2: Select Installation based on API response
    """
    VERSION = 1

    data: Optional[Dict[str, Any]]


    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle Credentials. Then select installation."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            try:
                data = await validate_credentials(self.hass, user_input)
                # return self.async_create_entry(title=data["email"], data=data)
            except AuthException:
                errors["base"] = "auth"
            except Exception:
                errors["base"] = "unknown"


            if not errors:
                # Input is valid, set data.
                self.data = user_input
                self.data["installation"] = []
                # Return the form of the next step.
                return await self.async_step_installation()

        return self.async_show_form(
            step_id="user", data_schema=CREDENTIALS_DATA_SCHEMA, errors=errors
        )


    async def async_step_installation(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle installation selection."""

        errors: Dict[str, str] = {}

        if user_input is not None:
            # no need to validate

            if self.data:
                self.data["installation"] = user_input["installation"]
                api = StromNetzGrazAPI(self.data["email"], self.data["password"])
                data = await api.get_installations()

                # Get Address
                address = self.data["installation"]
                for installation in data.installations:
                    if installation.installationID == self.data["installation"]:
                        address = installation.address

                return self.async_create_entry(title=address, data=self.data)

        installations = []
        if self.data:
            api = StromNetzGrazAPI(self.data["email"], self.data["password"])
            data = await api.get_installations()
            installations = data.installations

        # Schema: Dropdown of installation address but value is the installation object
        installations_schema = vol.Schema(
            {
                vol.Required(
                    "installation",
                    description="Select the installation you want to add",
                ): vol.In(
                    {installation.installationID: installation.address for installation in installations}
                )
            }
        )

        return self.async_show_form(
            step_id="installation", data_schema=installations_schema, errors=errors, last_step=False
        )
