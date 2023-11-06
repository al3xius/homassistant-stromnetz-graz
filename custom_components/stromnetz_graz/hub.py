from __future__ import annotations
import datetime
from typing import Any, Callable, Optional, Dict
from homeassistant.core import HomeAssistant
import logging
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
import async_timeout
from homeassistant.core import callback

from datetime import timedelta

import asyncio

from .api import StromNetzGrazAPI, AuthException

_LOGGER = logging.getLogger(__name__)



class Coordianator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, api: StromNetzGrazAPI):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Stromnetz Graz",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self.api = api
        self.meters: list[EnergyMeter] = []

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        _LOGGER.info("Updating data from API")
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):

                data = {}
                for meter in self.meters:
                    reading = await self.api.get_readings(meter.meter_id, meter.lastValid, datetime.datetime.now())

                    # Find valid reading from last to first
                    meter_data = {
                        "reading": None,
                        "consumption": None
                    }
                    for r in reversed(reading.readings):
                        readingValues = r.readingValues

                        meter_data: Dict[str, Optional[float]] = {
                            "reading": None,
                            "consumption": None
                        }
                        for readingValue in readingValues:
                            if not readingValue.readingState == "Valid":
                                continue

                            if readingValue.readingType == "CONSUMP":
                                meter_data["consumption"] = readingValue.value
                            elif readingValue.readingType == "MR":
                                meter_data["reading"] = readingValue.value

                        if meter_data["reading"] is not None and meter_data["consumption"] is not None:
                            meter.lastValid = r.readTime
                            break

                    _LOGGER.info(f"Meter {meter.meter_id} has reading {meter_data['reading']} and consumption {meter_data['consumption']}")
                    data[meter.meter_id] = meter_data

                return data
        except AuthException as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            # raise ConfigEntryAuthFailed from err
            pass
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")


class EnergyMeter(CoordinatorEntity):
    def __init__(self, meterId: int, name: str, lastValid: datetime.datetime, coordinator, idx) -> None:
        super().__init__(coordinator, context=idx)
        self._id = meterId
        self._name = name
        self._callbacks = set()
        self.lastValid = lastValid
        self.consumption = None
        self.reading = None
        self.coordinator = coordinator

    @property
    def meter_id(self) -> int:
        """Return ID for meter."""
        return self._id

    @property
    def name(self) -> str:
        """Return Name of meter."""
        return self._name

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)


    @property
    def online(self) -> bool:
        return True

class Hub():
    def __init__(self, api: StromNetzGrazAPI, coordinator: Coordianator, meters: list[EnergyMeter]) -> None:
        self.api = api
        self.coordinator = coordinator
        self.meters = meters

async def meter_factory(api: StromNetzGrazAPI, installationID: int, coordinator: Coordianator):
    installations = await api.get_installations()
    installations = installations.installations

    # Find installation
    installation = installations[0]
    for i in installations:
        if i.installationID == installationID:
            installation = i
            break


    meterPoints = installation.meterPoints
    meters = []
    for i, meterPoint in enumerate(meterPoints):
        meters.append(EnergyMeter(meterPoint.meterPointID, meterPoint.shortName, meterPoint.readingsAvailableSince, coordinator, i))

    return meters