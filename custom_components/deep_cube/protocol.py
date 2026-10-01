"""BLE protocol of the deep sleep cube.

Encoding of commands and parsing of replies, as described in docs/protocol.md.
This module has no dependencies on Home Assistant or on a BLE library.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from enum import IntEnum, StrEnum
import struct

STATUS_UUID = "98658f39-e4e3-4ac4-8e14-b1b7ff024353"
COMMAND_UUID = "98658f3a-e4e3-4ac4-8e14-b1b7ff024353"
SETTINGS_UUID = "9b5bfb13-20d7-4730-aa0c-993ea99fd4cd"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
FIRMWARE_UUID = "00002a26-0000-1000-8000-00805f9b34fb"
HARDWARE_UUID = "00002a27-0000-1000-8000-00805f9b34fb"

# Advertised local names of the supported models.
MODEL_NAMES = ("deep.r", "deep.n")

_CMD_START = 0x1A
_CMD_STOP = 0x3C
# The firmware reuses the command codes as "on" and "off" in settings.
_ON = 0x1A
_OFF = 0x3C
_STATE_IDLE = 0x00
_STATE_RUNNING = 0xAA
_REPLY_OK = 0x00

_COMMAND_LENGTH = 8
_STATUS_LENGTH = 12
_MAX_DURATION = 0xFFFFFFFF


class ProtocolError(ValueError):
    """The cube sent data that does not match the protocol."""


class Program(StrEnum):
    """Programs whose ids were observed in the official app traffic."""

    JUST_SLEEP = "just_sleep"
    BEAR_SLEEP = "bear_sleep"
    DREAM_WHALE = "dream_whale"
    DREAMCATCHER = "dreamcatcher"


class Intensity(StrEnum):
    """Intensity levels offered by the official app."""

    LOW = "low"
    NORMAL = "normal"
    MAX = "max"


class Setting(IntEnum):
    """On/off settings stored in the cube."""

    LED = 0x01
    LED_AUTO_OFF = 0x02
    VIBRATION = 0x03


# Program -> (id in byte 1, slot in byte 3).
_PROGRAM_CODES: dict[Program, tuple[int, int]] = {
    Program.JUST_SLEEP: (0x01, 1),
    Program.BEAR_SLEEP: (0x0A, 2),
    Program.DREAM_WHALE: (0x03, 3),
    Program.DREAMCATCHER: (0x0B, 4),
}
_PROGRAM_BY_ID = {code[0]: program for program, code in _PROGRAM_CODES.items()}

_INTENSITY_CODES: dict[Intensity, int] = {
    Intensity.LOW: 0x00,
    Intensity.NORMAL: 0x7F,
    Intensity.MAX: 0xFF,
}
_INTENSITY_BY_CODE = {code: level for level, code in _INTENSITY_CODES.items()}


@dataclass(frozen=True, slots=True)
class CubeStatus:
    """Parsed value of the status characteristic."""

    raw: bytes
    running: bool
    program_id: int
    program: Program | None
    intensity: Intensity | None
    duration: timedelta
    elapsed: timedelta

    @property
    def remaining(self) -> timedelta:
        """Return the time left until the program ends."""
        return max(self.duration - self.elapsed, timedelta())


def encode_start(program: Program, intensity: Intensity, duration: timedelta) -> bytes:
    """Encode the command that starts a program for the given duration."""
    seconds = int(duration.total_seconds())
    if not 0 < seconds <= _MAX_DURATION:
        raise ValueError(f"duration out of range: {duration}")
    program_id, slot = _PROGRAM_CODES[program]
    return struct.pack(
        "<BBBBI", _CMD_START, program_id, _INTENSITY_CODES[intensity], slot, seconds
    )


def encode_stop() -> bytes:
    """Encode the command that stops the running program."""
    return bytes([_CMD_STOP]) + bytes(_COMMAND_LENGTH - 1)


def command_accepted(reply: bytes) -> bool:
    """Tell whether the cube accepted a start or stop command.

    An accepted start does not mean the program runs: check the status.
    """
    if len(reply) < 2:
        raise ProtocolError(f"command reply too short: {reply.hex()}")
    return reply[0] == _REPLY_OK


def parse_status(data: bytes) -> CubeStatus:
    """Parse the value of the status characteristic."""
    if len(data) < _STATUS_LENGTH:
        raise ProtocolError(f"status too short: {data.hex()}")
    state, program_id, intensity = data[0], data[1], data[2]
    if state not in (_STATE_IDLE, _STATE_RUNNING):
        raise ProtocolError(f"unknown program state: {data.hex()}")
    duration, elapsed = struct.unpack_from("<II", data, 4)
    running = state == _STATE_RUNNING
    return CubeStatus(
        raw=bytes(data),
        running=running,
        program_id=program_id,
        program=_PROGRAM_BY_ID.get(program_id) if running else None,
        intensity=_INTENSITY_BY_CODE.get(intensity) if running else None,
        duration=timedelta(seconds=duration),
        elapsed=timedelta(seconds=elapsed),
    )


def encode_setting_read(setting: Setting) -> bytes:
    """Encode the request for the value of a setting."""
    return bytes([0x00, setting])


def parse_setting_read(setting: Setting, reply: bytes) -> bool:
    """Parse the reply to a setting read request."""
    if len(reply) < 4 or reply[0] != 0x00 or reply[1] != 0x00 or reply[2] != setting:
        raise ProtocolError(f"unexpected reply for setting {setting}: {reply.hex()}")
    if reply[3] not in (_ON, _OFF):
        raise ProtocolError(f"unknown value of setting {setting}: {reply.hex()}")
    return reply[3] == _ON


def encode_setting_write(setting: Setting, enabled: bool) -> bytes:
    """Encode the command that turns a setting on or off."""
    return bytes([setting, _ON if enabled else _OFF])


def setting_write_accepted(setting: Setting, reply: bytes) -> bool:
    """Tell whether the cube accepted a setting write."""
    if len(reply) < 2:
        raise ProtocolError(f"setting reply too short: {reply.hex()}")
    return reply[0] == setting and reply[1] == _REPLY_OK


def parse_battery(data: bytes) -> int:
    """Parse the battery level in percent."""
    if not data or data[0] > 100:
        raise ProtocolError(f"invalid battery level: {data.hex()}")
    return data[0]


def duration_until(wake_time: time, now: datetime) -> timedelta:
    """Return the time from now until the next occurrence of the wake-up time.

    The cube has no clock, so the wake-up time is sent as a duration.
    `now` must be timezone-aware; the wake-up time is taken in its timezone.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    wake = datetime.combine(now.date(), wake_time.replace(tzinfo=None), now.tzinfo)
    if wake <= now:
        wake = datetime.combine(
            now.date() + timedelta(days=1), wake_time.replace(tzinfo=None), now.tzinfo
        )
    # Subtract in UTC: aware datetimes sharing a tzinfo subtract as wall clock
    # time, which is off by an hour across a daylight saving change.
    return wake.astimezone(timezone.utc) - now.astimezone(timezone.utc)
