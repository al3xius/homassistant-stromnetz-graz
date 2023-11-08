"""The example sensor integration."""
from __future__ import annotations
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from .api import StromNetzGrazAPI
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .hub import Coordianator, meter_factory, Hub
import logging

PLATFORMS: list[str] = ["sensor"]

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Hello World from a config entry."""
    # Store an instance of the "connecting" class that does the work of speaking
    # with your actual devices.

    _LOGGER.info("Setting up Stromnetz Graz")

    api = StromNetzGrazAPI(entry.data["email"], entry.data["password"], async_get_clientsession(hass))
    coordinator = Coordianator(hass, api)
    meters = await meter_factory(api, entry.data["installation"], coordinator)
    coordinator.meters = meters
    MeterHub = Hub(api, coordinator, meters)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = MeterHub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True



async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
