from __future__ import annotations
import datetime
import time
from typing import Any, Callable, Optional, Dict

import pytz
from homeassistant.components.recorder.models.statistics import StatisticData, StatisticMetaData
from homeassistant.const import ENERGY_KILO_WATT_HOUR
from homeassistant.core import HomeAssistant
import logging
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from datetime import timedelta
from .api import  StromNetzGrazAPI, AuthException, TimedReadingValue
from .const import DOMAIN

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_import_statistics,
    get_last_statistics,
    statistics_during_period,
)

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
            update_interval=timedelta(minutes=30),
        )
        self.api = api
        self.meters: list[EnergyMeter] = []

    def _only_last_reading_of_each_hour(self, valid_readings: list[TimedReadingValue]) -> list[TimedReadingValue]:
        """Return only the last reading of each hour."""
        last_reading_of_each_hour = []
        for reading in valid_readings:
            if not last_reading_of_each_hour:
                last_reading_of_each_hour.append(reading)
            else:
                last_reading = last_reading_of_each_hour[-1]
                if reading.time.hour != last_reading.time.hour:
                    last_reading_of_each_hour.append(reading)
        return last_reading_of_each_hour

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        _LOGGER.info("Updating data from API")
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            for meter in self.meters:
                _LOGGER.info("Updating meter %s", meter.name)
                statistic_id = f"{DOMAIN}:{meter.meter_id}_reading"
                _LOGGER.info("Getting last statistics for %s", statistic_id)
                last_stats = await get_instance(self.hass).async_add_executor_job(
                    get_last_statistics, self.hass, 1, statistic_id, True, {"state"}
                )

                _LOGGER.info("Found %s last statistics for meter %s", len(last_stats), meter.name)
                reading = None
                if not last_stats:
                    reading = await self.api.get_readings(meter.meter_id, meter.lastValid, datetime.datetime.now())
                else:
                    last_stats_time = datetime.datetime.fromtimestamp(last_stats[statistic_id][0]["start"])
                    last_stats_time = last_stats_time.replace(minute=1)
                    _LOGGER.info("Last statistics for meter %s is from %s", meter.name, last_stats_time)
                    reading = await self.api.get_readings(meter.meter_id, last_stats_time, datetime.datetime.now())

                _LOGGER.info("Found %s readings for meter %s", len(reading.meterReadingValues), meter.name)


                meterReadings = reading.meterReadingValues
                # Find all readings from start up to last valid
                validReadings: list[TimedReadingValue] = []
                for r in meterReadings:
                    if r.readingState == "NotAvailable":
                        continue
                    # TODO: Handle estimated readings better
                    if r.readingState == "Estimated":
                        continue
                    _LOGGER.info("Reading State %s", r.readingState)
                    if not r.readingState == "Valid":
                        break
                    validReadings.append(r)

                _LOGGER.info("Found %s valid readings for meter %s", len(validReadings), meter.name)
                if len(validReadings) == 0:
                    continue

                _LOGGER.info("Setting reading for meter %s to %s", meter.name, validReadings[-1].value)
                meter.setReading(validReadings[-1])

                # Filter out all but the last reading of each hour
                validReadings = self._only_last_reading_of_each_hour(validReadings)
                _LOGGER.info("Found %s last readings for meter %s: %s", len(validReadings), meter.name, validReadings[-1])

                # Update history with valid readings
                statistics = []
                for r in validReadings:
                    timestamp = r.time.replace(tzinfo=pytz.utc, minute=0, second=0, microsecond=0)
                    statistics.append(
                        StatisticData(
                            start=timestamp,
                            state=r.value,
                            sum=r.value
                        )
                    )

                _LOGGER.info("Adding %s statistics for meter %s", len(statistics), meter.name)

                metadata = StatisticMetaData(
                    source=DOMAIN,
                    name=f"{meter.name}",
                    statistic_id=statistic_id,
                    has_mean=False,
                    unit_of_measurement=ENERGY_KILO_WATT_HOUR,
                    has_sum=True,
                )

                async_add_external_statistics(self.hass, metadata, statistics)

        except AuthException as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            # raise ConfigEntryAuthFailed from err
            _LOGGER.error("Invalid Credentials: %s", err)
            pass
        except Exception as err:
            _LOGGER.error("Error communicating with API: %s", err)
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

    def setReading(self, reading: TimedReadingValue):
        self.reading = reading.value
        self.lastValid = reading.time

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