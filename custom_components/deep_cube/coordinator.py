"""Data update coordinator of the deep sleep cube."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, time, timedelta
import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_MODEL, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import (
    CubeConnection,
    CubeConnectionError,
    CubeError,
    CubeStartNotConfirmed,
    connect,
)
from .const import (
    DEFAULT_INTENSITY,
    DEFAULT_PROGRAM,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WAKE_TIME,
    DOMAIN,
)
from .protocol import CubeStatus, Intensity, Program, Setting, duration_until

_LOGGER = logging.getLogger(__name__)

# The end time is derived from the elapsed counter at the moment of a poll.
# The counter advances in steps of 1/1000 of the duration, so the result
# jitters; shifts within the tolerance are not reported.
_END_TIME_TOLERANCE = timedelta(seconds=60)
_END_TIME_TOLERANCE_STEPS = 2

# A failed poll is simply repeated at the next interval, so it gives up sooner
# than a command; this also keeps a cube in poor range from delaying startup.
_POLL_CONNECT_ATTEMPTS = 2
_COMMAND_CONNECT_ATTEMPTS = 3

type DeepCubeConfigEntry = ConfigEntry[DeepCubeCoordinator]


def _scan_interval(entry: DeepCubeConfigEntry) -> timedelta:
    """Return the polling interval set in the options."""
    return timedelta(
        minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )


@dataclass(frozen=True, slots=True)
class CubeData:
    """State of the cube read in one connection."""

    status: CubeStatus
    battery: int
    settings: dict[Setting, bool]
    ends_at: datetime | None


class DeepCubeCoordinator(DataUpdateCoordinator[CubeData]):
    """Polls the cube and sends commands, one short connection at a time."""

    config_entry: DeepCubeConfigEntry

    def __init__(self, hass: HomeAssistant, entry: DeepCubeConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=_scan_interval(entry),
        )
        self.address: str = entry.data[CONF_ADDRESS]
        self.model: str = entry.data[CONF_MODEL]
        self.firmware: str | None = None
        self.hardware: str | None = None
        # What the next start will use; owned by the select and time entities.
        self.program: Program = DEFAULT_PROGRAM
        self.intensity: Intensity = DEFAULT_INTENSITY
        self.wake_time: time = DEFAULT_WAKE_TIME
        self._lock = asyncio.Lock()

    @callback
    def async_apply_options(self) -> None:
        """Start using a changed polling interval."""
        self.update_interval = _scan_interval(self.config_entry)
        if self.last_update_success:
            # Reschedules the next poll; no connection is made.
            self.async_set_updated_data(self.data)

    @asynccontextmanager
    async def _session(self, max_attempts: int) -> AsyncIterator[CubeConnection]:
        """Connect to the cube for one operation."""
        async with self._lock:
            device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if device is None:
                raise CubeConnectionError(
                    "not in range of a connectable Bluetooth adapter"
                    " or busy with another client"
                )
            async with connect(device, max_attempts) as cube:
                yield cube

    async def _async_read(self, cube: CubeConnection) -> CubeData:
        """Read the whole state over an open connection."""
        if self.firmware is None:
            self.firmware, self.hardware = await cube.read_versions()
        status = await cube.read_status()
        return CubeData(
            status=status,
            battery=await cube.read_battery(),
            settings=await cube.read_settings(),
            ends_at=self._ends_at(status),
        )

    def _ends_at(self, status: CubeStatus) -> datetime | None:
        """Return the moment the running program ends."""
        if not status.running:
            return None
        ends_at = dt_util.utcnow().replace(microsecond=0) + status.remaining
        tolerance = (
            _END_TIME_TOLERANCE + status.duration * _END_TIME_TOLERANCE_STEPS / 1000
        )
        if (
            self.data is not None
            and (previous := self.data.ends_at) is not None
            and abs(ends_at - previous) < tolerance
        ):
            return previous
        return ends_at

    async def _async_update_data(self) -> CubeData:
        """Poll the cube."""
        try:
            async with self._session(_POLL_CONNECT_ATTEMPTS) as cube:
                return await self._async_read(cube)
        except CubeError as err:
            raise UpdateFailed(f"Cannot read {self.model}: {err}") from err

    async def _async_execute(
        self, action: Callable[[CubeConnection], Awaitable[None]]
    ) -> None:
        """Run a command and refresh the state in the same connection."""
        failure: CubeError | None = None
        try:
            async with self._session(_COMMAND_CONNECT_ATTEMPTS) as cube:
                try:
                    await action(cube)
                except CubeStartNotConfirmed as err:
                    failure = err
                data = await self._async_read(cube)
        except CubeConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err
        except CubeError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self.async_set_updated_data(data)
        if failure is not None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="start_not_confirmed"
            ) from failure

    async def async_start_program(
        self,
        program: Program | None = None,
        intensity: Intensity | None = None,
        wake_time: time | None = None,
    ) -> None:
        """Start a program that runs until the next wake-up time."""
        program = program or self.program
        intensity = intensity or self.intensity
        duration = duration_until(wake_time or self.wake_time, dt_util.now())
        await self._async_execute(
            lambda cube: cube.start(program, intensity, duration)
        )

    async def async_stop_program(self) -> None:
        """Stop the running program."""
        await self._async_execute(lambda cube: cube.stop())

    async def async_set_setting(self, setting: Setting, enabled: bool) -> None:
        """Turn a cube setting on or off."""
        await self._async_execute(lambda cube: cube.write_setting(setting, enabled))
