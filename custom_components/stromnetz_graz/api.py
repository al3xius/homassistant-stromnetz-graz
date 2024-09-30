from __future__ import annotations
import datetime
from typing import Optional
import aiohttp
from .const import API_HOST
from homeassistant import exceptions
import logging


_LOGGER = logging.getLogger(__name__)

class StromNetzGrazAPI():
    """
        Stromnetz Graz API
        Uses aiohttp to make the api requests
        init takes username and password as parameters

    """

    def __init__(self, email: str, password: str, session: Optional[aiohttp.ClientSession] = None) -> None:
        """Initialize the API wrapper."""
        self.email = email
        self.password = password

        self.token = None
        self.login_retries = 0

        if session is None:
            self.session = aiohttp.ClientSession()
        if session is not None:
            self.session = session




    async def token_request(self) -> str:
        """Get the token from the API."""
        async with self.session.post(
            f"{API_HOST}/login",
            json={"email": self.email, "password": self.password},
        ) as response:
            print("Logging in!")
            print(response)
            if response.status != 200:
                _LOGGER.error("Could not log in! Statuscode is: ", response.status)
                raise AuthException

            # check for mime type
            mime = response.headers.get("Content-Type") or ""

            if "application/json" not in mime:
                _LOGGER.error("Unknown response from API: %s", mime)
                raise AuthException


            data = await response.json()
            resp = LoginResponse(data)
            if not resp.success:
                _LOGGER.error("Could not log in!")
                raise AuthException

            self.login_retries = 0
            return resp.token

    async def loggedin_request(self, url: str, json: dict) -> dict:
        """Make a request to the API. That take url and json as parameters."""
        if not self.token:
            self.token = await self.token_request()

        async with self.session.post(
            f"{API_HOST}{url}",
            headers={"Authorization": f"Bearer {self.token}"},
            json=json,
        ) as response:
            if response.status == 401:
                _LOGGER.warning("Token invalid: Try to regenerate.")
                if self.login_retries > 0:
                    _LOGGER.error("Could not log in! Too many retries.")
                    raise AuthException
                # Retry once
                self.token = await self.token_request()
                self.login_retries += 1
                return await self.loggedin_request(url, json)

            if response.status != 200:
                _LOGGER.error("Statuscode is: ", response.status)
                raise UnknownResponseExeption

            # check for mime type
            mime = response.headers.get("Content-Type") or ""
            if "application/json" not in mime:
                _LOGGER.error("Unknown response from API: %s", mime)
                raise UnknownResponseExeption


            # _LOGGER.info(f"{url}: {json}")
            _LOGGER.info(f"{url}: {response.status}")
            _LOGGER.info(f"{url}: {response.headers}")

            data = await response.json()
            # _LOGGER.info(f"{url}: {data}")
            return data

    async def get_installations(self) -> InstallationsResponse:
        """Get the installations from the API."""
        data = await self.loggedin_request("/getInstallations", {})
        return InstallationsResponse(data)

    async def get_readings(self, meter_point_id: int, start: datetime.datetime, end: datetime.datetime, quaterHour: bool = True) -> ReadingResponse:
        data = await self.loggedin_request("/getMeterReading", {
            "meterPointId": meter_point_id,
            "fromDate": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "toDate": end.strftime("%Y-%m-%dT%H:%M:%S"),
            "interval": "QuarterHourly" if quaterHour else "Daily",
            "unitOfConsumption": "KWH"
        })

        return ReadingResponse(data)

class LoginResponse:
    def __init__(self, data: dict) -> None:
        self.data = data

    @property
    def token(self) -> str:
        return self.data["token"]

    @property
    def error(self) -> str:
        return self.data["error"]

    @property
    def success(self) -> bool:
        return self.data["success"]

class InstallationsResponse:
    def __init__(self, data: dict) -> None:
        self.data = data

    @property
    def installations(self) -> list[Installation]:
        return [Installation(installation) for installation in self.data]

class Installation:
    def __init__(self, data: dict) -> None:
        self.data = data

    @property
    def installationID(self) -> int:
        return self.data["installationID"]

    @property
    def installationNumber(self) -> int:
        return self.data["installationNumber"]

    @property
    def customerID(self) -> int:
        return self.data["customerID"]

    @property
    def customerNumber(self) -> int:
        return self.data["customerNumber"]

    @property
    def address(self) -> str:
        return self.data["address"]

    @property
    def deliveryDirection(self) -> str:
        return self.data["deliveryDirection"]

    @property
    def meterPoints(self) -> list[MeterPoint]:
        return [MeterPoint(meterPoint) for meterPoint in self.data["meterPoints"]]

class MeterPoint:
    def __init__(self, data: dict) -> None:
        self.data = data

    @property
    def meterPointID(self) -> int:
        return self.data["meterPointID"]

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def shortName(self) -> str:
        return self.data["shortName"]

    @property
    def readingsAvailableSince(self) -> datetime.datetime:
        return datetime.datetime.strptime(self.data["readingsAvailableSince"], "%Y-%m-%dT%H:%M:%SZ")

    @property
    def meterType(self) -> str:
        return self.data["meterType"]

class ReadingResponse:
    def __init__(self, data: dict) -> None:
        self.data = data

    @property
    def intervalType(self) -> str:
        return self.data["intervalType"]

    @property
    def readings(self) -> list[Reading]:
        return [Reading(reading) for reading in self.data["readings"]]

    @property
    def meterReadingValues(self) -> list[TimedReadingValue]:
        # extract reading values from readings with readingtype "MR" and add timestamp
        values = [TimedReadingValue(readingValue, reading.readTime) for reading in self.readings for readingValue in reading.readingValues if readingValue.readingType == "MR"]
        # sort by time
        return sorted(values, key=lambda x: x.time)

class Reading:
    def __init__(self, data: dict) -> None:
        self.data = data

    @property
    def readTime(self) -> datetime.datetime:
        if self.data["readTime"][-1] == 'Z':
            # parse 2023-11-12T23:00:00Z
            return datetime.datetime.strptime(self.data["readTime"], "%Y-%m-%dT%H:%M:%SZ").astimezone(datetime.timezone.utc)

        # parse 2023-11-03T00:00:00.000+01:00
        return datetime.datetime.strptime(self.data["readTime"], "%Y-%m-%dT%H:%M:%S.%f+%z").astimezone(datetime.timezone.utc)

    @property
    def readingValues(self) -> list[ReadingValue]:
        return [ReadingValue(readingValue) for readingValue in self.data["readingValues"]]

class ReadingValue:
    def __init__(self, data: dict) -> None:
        self.data = data

    def __repr__(self) -> str:
        return f"ReadingValue({self.readingType}: {self.value} {self.unit})"

    @property
    def scale(self) -> str:
        return self.data["scale"]

    @property
    def readingType(self) -> str:
        return self.data["readingType"]

    @property
    def value(self) -> float:
        return self.data["value"]

    @property
    def unit(self) -> str:
        return self.data["unit"]

    @property
    def readingState(self) -> str:
        return self.data["readingState"]

class TimedReadingValue(ReadingValue):
    def __init__(self, reading: ReadingValue, time: datetime.datetime) -> None:
        self.data = reading.data
        self.time = time

    def __repr__(self) -> str:
        return super().__repr__() + f" at {self.time}"

class AuthException(exceptions.HomeAssistantError):
    """Exception to indicate an authentication error."""

class UnknownResponseExeption(exceptions.HomeAssistantError):
    """Exception to indicate that the response code is unknown."""