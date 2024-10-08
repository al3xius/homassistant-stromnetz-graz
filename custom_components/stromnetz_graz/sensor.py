"""Platform for sensor integration."""

from __future__ import annotations

import voluptuous as vol

from .hub import EnergyMeter
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import MATCH_ALL, UnitOfEnergy
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_platform, service

from .const import DOMAIN
import logging
from .hub import Hub


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up platform for a new integration.

    Called by the HA framework after async_setup_platforms has been called
    during initialization of a new integration.
    """
    MeterHub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    # _LOGGER.info(f"Setup Sensors with API: {api.username}")

    sensors = []
    for meter in MeterHub.meters:
        sensor = MeterReadingSensor(meter)
        sensors.append(sensor)

    # add sensors
    async_add_entities(sensors)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "sync_data", {vol.Optional("sync_all"): cv.boolean}, sync_data
    )

    platform.async_register_entity_service("clear_data", {}, clear_data)


async def sync_data(entity: MeterReadingSensor, service_call):
    """Sync data from API."""
    _LOGGER.info(f"Syncing data for {entity.name}")
    sync_all = service_call.data.get("sync_all", False)
    if sync_all:
        await entity.coordinator.clear_data()
    await entity.coordinator.sync_data(sync_all)


async def clear_data(entity: MeterReadingSensor, service_call):
    """Sync data from API."""
    _LOGGER.info("Clear data for %s", entity.name)
    await entity.coordinator.clear_data()


class MeterReadingSensor(CoordinatorEntity, SensorEntity):
    """Enery Sensor base on Api data."""

    _attr_name = "Meter Reading"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    _attr_entity_picture = "https://www.stromnetz-graz.at/static/frontend/Magento/sgg/de_AT/images/logo_sgg.svg"

    def __init__(self, meter: EnergyMeter) -> None:
        """Initialize the sensor."""
        super().__init__(meter.coordinator, context=meter.meter_id)
        self._state = None
        self._meter = meter
        self._attr_unique_id = f"{self._meter.meter_id}_reading"

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return {
            "identifiers": {(DOMAIN, self._meter.meter_id)},
            "name": self._meter.name,
            "manufacturer": "Stromnetz Graz",
        }

    @property
    def available(self) -> bool:
        """Return True if meter available."""
        return self._meter.online

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Meter Reading"

    # @property
    # def state(self):
    #     """Return the state of the sensor."""
    #     return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfEnergy.KILO_WATT_HOUR

    # @callback
    # def _handle_coordinator_update(self) -> None:
    #     """Handle updated data from the coordinator."""
    #     self._state = self.coordinator.data[self._meter.meter_id]["reading"]
    #     self.async_write_ha_state()

    @property
    def native_value(self):
        """Return the value of the sensor."""
        return self._meter.reading
