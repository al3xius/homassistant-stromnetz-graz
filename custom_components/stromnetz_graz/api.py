from __future__ import annotations
import datetime
from typing import Any, Callable
import aiohttp
from homeassistant.core import HomeAssistant
from .const import API_HOST
from homeassistant import exceptions
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

_LOGGER = logging.getLogger(__name__)

class StromNetzGrazAPI():
    def __init__(self, hass: HomeAssistant, username: str, password: str) -> None:
        self.hass = hass
        self.username = username
        self.password = password

        self.meters = []
        self.token = None
        self.installationID = None
        self.address = None

        self.loginRetries = 0


    async def login(self) -> str:
        _LOGGER.info(f"Logging in {self.username}")

        async with aiohttp.ClientSession() as session:
            async with session.post(API_HOST + "/login", json={
               "email": self.username,
               "password": self.password
            }) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    if data and data["success"] and data["token"]:
                        if data["success"] == False or not data["token"]:
                           raise InvalidAuth
                        else:
                            return data["token"]
                    else:
                        raise InvalidAuth
                elif resp.start == 401:
                    raise InvalidAuth
                else:
                    raise FetchError

    async def getToken(self) -> str:
        if self.token is None:
            self.token = await self.login()
            self.loginRetries = 0

        return self.token

    async def getInstallations(self) -> Any:
        _LOGGER.info(f"Getting installations {self.username}")
        async with aiohttp.ClientSession() as session:
            async with session.post(API_HOST + "/getInstallations", json={}, headers={
                "Authorization": f"Bearer {await self.getToken()}"
            }) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                elif resp.status == 401:
                    self.token = None
                    self.loginRetries += 1
                    raise InvalidAuth
                else:
                    raise FetchError

    async def getLastValidReading(self, meter: EnergyMeter) -> float:
        _LOGGER.info(f"Getting reading for {meter.meter_id}")
        async with aiohttp.ClientSession() as session:
             async with session.post(API_HOST + "/getMeterReading", json={
                 "meterPointId": meter.meter_id,
                 "interval": "Daily",
                 "unitOfConsump": "KWH",
                 "fromDate": meter.lastValid,
                 "toDate": datetime.datetime.now(),
                }, headers={
                "Authorization": f"Bearer {await self.getToken()}"
            }) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    _LOGGER.info(data)
                    return 10
                elif resp.status == 401:
                    self.token = None
                    self.loginRetries += 1
                    raise InvalidAuth
                else:
                    raise FetchError

    async def setupMeter(self, coordinator: Coordianator) -> None:
        # TODO: make selectable
        installations = await self.getInstallations()
        installation = installations[0]
        meter = installation["meterPoints"][0]

        self.installationID = installation["installationID"]
        self.address = installation["address"]
        self.meters = [EnergyMeter(meter["meterPointID"], meter["shortName"], meter["readingsAvailableSince"], self, coordinator, 0)]


    @property
    def hub_id(self) -> str:
        """ID for dummy hub."""
        return self.installationID

class InvalidAuth(exceptions.HomeAssistantError):
    """Invalid Credentials"""

class FetchError(exceptions.HomeAssistantError):
    """Non 200 Status code"""



class Coordianator(DataUpdateCoordinator):
    def __init__(self, hass, api: StromNetzGrazAPI):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=api.address,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                # Grab active context variables to limit data required to be fetched from API
                # Note: using context is not required if there is no need or ability to limit
                # data retrieved from API.
                # listening_idx = set(self.async_contexts())

                _LOGGER.log("Update Readings")
                # Update meters

                readings = [

                ]
                for meter in self.api.meters:
                    reading = await self.api.getLastValidReading(meter)
                    readings.append({
                        "energy": 10
                    })

                return readings
        except InvalidAuth as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            # raise ConfigEntryAuthFailed from err
            pass
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")



class EnergyMeter(CoordinatorEntity, ):
    def __init__(self, meterId: str, name: str, lastValid: str, api: StromNetzGrazAPI, coordinator, idx) -> None:
        super().__init__(coordinator, context=idx)
        self._id = meterId

        self.api = api
        self._name = name
        self._callbacks = set()
        self._loop = asyncio.get_event_loop()
        self.lastValid = lastValid
        self.energy = 0
        self.coordinator = coordinator

    @property
    def meter_id(self) -> str:
        """Return ID for meter."""
        return self._id

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)


    @property
    def online(self) -> bool:
        return True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.energy = self.coordinator.data[self.idx]["energy"]
        self.async_write_ha_state()

