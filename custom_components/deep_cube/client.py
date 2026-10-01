"""Short-lived BLE connection to the deep sleep cube.

The cube accepts a single connection, so every operation connects, does its
work and disconnects, leaving the cube free for the official app.
This module does not depend on Home Assistant.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import timedelta
import logging

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from .protocol import (
    BATTERY_UUID,
    COMMAND_UUID,
    FIRMWARE_UUID,
    HARDWARE_UUID,
    SETTINGS_UUID,
    STATUS_UUID,
    CubeStatus,
    Intensity,
    Program,
    ProtocolError,
    Setting,
    command_accepted,
    encode_setting_read,
    encode_setting_write,
    encode_start,
    encode_stop,
    parse_battery,
    parse_setting_read,
    parse_status,
    setting_write_accepted,
)

_LOGGER = logging.getLogger(__name__)

_REPLY_TIMEOUT = 5.0
# The status may lag behind the reply to a start command.
_START_CHECKS = 3
_START_CHECK_INTERVAL = 1.0


class CubeError(Exception):
    """Base error of an exchange with the cube."""


class CubeConnectionError(CubeError):
    """The cube is out of reach, busy with another client or the link failed."""


class CubeCommandRejected(CubeError):
    """The cube answered a command with an error."""


class CubeStartNotConfirmed(CubeError):
    """The cube accepted the start command, but the program is not running."""


class CubeConnection:
    """Operations on a connected cube."""

    def __init__(self, client: BleakClient) -> None:
        """Wrap a connected client."""
        self._client = client
        self._replies: dict[str, asyncio.Queue[bytes]] = {}

    async def _request(self, uuid: str, payload: bytes) -> bytes:
        """Write to a characteristic and wait for the reply notification."""
        if (queue := self._replies.get(uuid)) is None:
            queue = self._replies[uuid] = asyncio.Queue()
            await self._client.start_notify(
                uuid, lambda _, data: queue.put_nowait(bytes(data))
            )
        while not queue.empty():
            queue.get_nowait()
        await self._client.write_gatt_char(uuid, payload, response=True)
        async with asyncio.timeout(_REPLY_TIMEOUT):
            reply = await queue.get()
        _LOGGER.debug("%s: sent %s, got %s", uuid, payload.hex(), reply.hex())
        return reply

    async def read_status(self) -> CubeStatus:
        """Read the program status."""
        data = bytes(await self._client.read_gatt_char(STATUS_UUID))
        _LOGGER.debug("Status: %s", data.hex())
        return parse_status(data)

    async def read_battery(self) -> int:
        """Read the battery level in percent."""
        return parse_battery(bytes(await self._client.read_gatt_char(BATTERY_UUID)))

    async def read_settings(self) -> dict[Setting, bool]:
        """Read all on/off settings."""
        return {
            setting: parse_setting_read(
                setting,
                await self._request(SETTINGS_UUID, encode_setting_read(setting)),
            )
            for setting in Setting
        }

    async def read_versions(self) -> tuple[str, str]:
        """Read the firmware and hardware versions."""
        firmware = await self._client.read_gatt_char(FIRMWARE_UUID)
        hardware = await self._client.read_gatt_char(HARDWARE_UUID)
        return (
            bytes(firmware).decode("utf-8", "replace").strip("\x00 "),
            bytes(hardware).decode("utf-8", "replace").strip("\x00 "),
        )

    async def write_setting(self, setting: Setting, enabled: bool) -> None:
        """Turn a setting on or off."""
        reply = await self._request(
            SETTINGS_UUID, encode_setting_write(setting, enabled)
        )
        if not setting_write_accepted(setting, reply):
            raise CubeCommandRejected(f"setting {setting.name}: {reply.hex()}")

    async def stop(self) -> None:
        """Stop the running program, if any."""
        if not (await self.read_status()).running:
            return
        reply = await self._request(COMMAND_UUID, encode_stop())
        if not command_accepted(reply):
            raise CubeCommandRejected(f"stop: {reply.hex()}")

    async def start(
        self, program: Program, intensity: Intensity, duration: timedelta
    ) -> None:
        """Start a program and make sure it is really running.

        A running program is stopped first, the way the official app does it.
        """
        await self.stop()
        reply = await self._request(
            COMMAND_UUID, encode_start(program, intensity, duration)
        )
        if not command_accepted(reply):
            raise CubeCommandRejected(f"start: {reply.hex()}")
        for attempt in range(_START_CHECKS):
            if attempt:
                await asyncio.sleep(_START_CHECK_INTERVAL)
            if (await self.read_status()).running:
                return
        raise CubeStartNotConfirmed(f"{program} for {duration}")


@asynccontextmanager
async def connect(
    device: BLEDevice, max_attempts: int = 3
) -> AsyncIterator[CubeConnection]:
    """Connect to the cube for the duration of the context."""
    try:
        client = await establish_connection(
            BleakClientWithServiceCache,
            device,
            device.name or device.address,
            max_attempts=max_attempts,
        )
    except (BleakError, TimeoutError) as err:
        raise CubeConnectionError(f"cannot connect: {err}") from err
    try:
        yield CubeConnection(client)
    except (BleakError, TimeoutError, EOFError) as err:
        raise CubeConnectionError(f"exchange failed: {err!r}") from err
    except ProtocolError as err:
        raise CubeError(str(err)) from err
    finally:
        with suppress(BleakError, TimeoutError, EOFError):
            await client.disconnect()
