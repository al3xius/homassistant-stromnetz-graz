"""Platform for sensor integration."""
from __future__ import annotations
from config.custom_components.stromnetz_graz.api import EnergyMeter, StromNetzGrazAPI

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import DEVICE_CLASS_ENERGY, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up platform for a new integration.

    Called by the HA framework after async_setup_platforms has been called
    during initialization of a new integration.
    """
    api: StromNetzGrazAPI = hass.data[DOMAIN][config_entry.entry_id]

    _LOGGER.info(f"Setup Sensors with API: {api.username}")


    new_devices = []
    for meter in api.meters:
        new_devices.append(EnergySensor(meter))
    if new_devices:
        async_add_entities(new_devices)



class EnergySensor(SensorEntity):
    """Enery Sensor base on Api data"""
    device_class = DEVICE_CLASS_ENERGY

    _attr_name = "Consumed Energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, meter: EnergyMeter) -> None:
        """Initialize the sensor."""
        self._state = None
        self._meter = meter
        self._attr_unique_id = f"{self._meter.meter_id}_energy"

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return {"identifiers": {(DOMAIN, self._meter.meter_id)}}

    @property
    def available(self) -> bool:
        """Return True if meter available"""
        return self._meter.online

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        # Sensors should also register callbacks to HA when their state changes
        self._meter.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self._meter.remove_callback(self.async_write_ha_state)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return 'Consumed Energy'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._meter.energy

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfEnergy.KILO_WATT_HOUR


