"""Tests of the protocol module.

Byte vectors are taken from the captured traffic of the official app.
"""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from deep_cube_protocol import (
    Intensity,
    Program,
    ProtocolError,
    Setting,
    command_accepted,
    duration_until,
    encode_setting_read,
    encode_setting_write,
    encode_start,
    encode_stop,
    parse_battery,
    parse_setting_read,
    parse_status,
    setting_write_accepted,
)


@pytest.mark.parametrize(
    ("program", "intensity", "seconds", "expected"),
    [
        (Program.JUST_SLEEP, Intensity.NORMAL, 72530, "1a017f01521b0100"),
        (Program.BEAR_SLEEP, Intensity.NORMAL, 72504, "1a0a7f02381b0100"),
        (Program.DREAM_WHALE, Intensity.NORMAL, 72477, "1a037f031d1b0100"),
        (Program.DREAMCATCHER, Intensity.NORMAL, 72457, "1a0b7f04091b0100"),
        (Program.JUST_SLEEP, Intensity.LOW, 71415, "1a010001f7160100"),
        (Program.JUST_SLEEP, Intensity.MAX, 71349, "1a01ff01b5160100"),
    ],
)
def test_encode_start_matches_app(
    program: Program, intensity: Intensity, seconds: int, expected: str
) -> None:
    """Start commands are byte-for-byte the ones the app sent."""
    command = encode_start(program, intensity, timedelta(seconds=seconds))
    assert command.hex() == expected


def test_every_program_can_be_encoded() -> None:
    """Each known program has an id and a slot."""
    for program in Program:
        assert len(encode_start(program, Intensity.NORMAL, timedelta(hours=8))) == 8


@pytest.mark.parametrize("seconds", [0, -5, 2**32])
def test_encode_start_rejects_bad_duration(seconds: int) -> None:
    """A duration must fit the uint32 field and be positive."""
    with pytest.raises(ValueError):
        encode_start(Program.JUST_SLEEP, Intensity.NORMAL, timedelta(seconds=seconds))


def test_encode_stop() -> None:
    """The stop command matches the app."""
    assert encode_stop().hex() == "3c00000000000000"


@pytest.mark.parametrize(
    ("reply", "accepted"),
    [("0001", True), ("000a", True), ("0000", True), ("0400", False)],
)
def test_command_accepted(reply: str, accepted: bool) -> None:
    """Replies to commands are told apart by the first byte."""
    assert command_accepted(bytes.fromhex(reply)) is accepted


def test_command_reply_too_short() -> None:
    """A truncated reply is a protocol error."""
    with pytest.raises(ProtocolError):
        command_accepted(b"\x00")


def test_parse_status_idle() -> None:
    """The idle status has no program and no intensity."""
    status = parse_status(bytes.fromhex("00007f000000000000000000"))
    assert not status.running
    assert status.program is None
    assert status.intensity is None
    assert status.remaining == timedelta()


def test_parse_status_running() -> None:
    """A running status carries the program, intensity and times."""
    status = parse_status(bytes.fromhex("aa0a7f00381b01003c000000"))
    assert status.running
    assert status.program is Program.BEAR_SLEEP
    assert status.intensity is Intensity.NORMAL
    assert status.duration == timedelta(seconds=72504)
    assert status.elapsed == timedelta(seconds=60)
    assert status.remaining == timedelta(seconds=72444)


@pytest.mark.parametrize(
    ("raw", "intensity"),
    [
        ("aa010000f716010000000000", Intensity.LOW),
        ("aa01ff00b516010000000000", Intensity.MAX),
    ],
)
def test_parse_status_intensity(raw: str, intensity: Intensity) -> None:
    """The intensity of the running program comes back in byte 2."""
    assert parse_status(bytes.fromhex(raw)).intensity is intensity


def test_parse_status_unknown_program() -> None:
    """A program started by the app with an unknown id is still running."""
    status = parse_status(bytes.fromhex("aa777f00100e000000000000"))
    assert status.running
    assert status.program is None
    assert status.program_id == 0x77


@pytest.mark.parametrize("raw", ["aa01", "55017f000000000000000000"])
def test_parse_status_invalid(raw: str) -> None:
    """A short status or an unknown state byte is a protocol error."""
    with pytest.raises(ProtocolError):
        parse_status(bytes.fromhex(raw))


def test_setting_read() -> None:
    """Setting reads match the app traffic."""
    assert encode_setting_read(Setting.LED).hex() == "0001"
    assert encode_setting_read(Setting.VIBRATION).hex() == "0003"
    assert parse_setting_read(Setting.LED, bytes.fromhex("0000013c")) is False
    assert parse_setting_read(Setting.LED_AUTO_OFF, bytes.fromhex("0000021a")) is True


@pytest.mark.parametrize("reply", ["000010", "0000021a", "00000155"])
def test_setting_read_invalid(reply: str) -> None:
    """A reply without a value, for another setting or with an unknown value fails."""
    with pytest.raises(ProtocolError):
        parse_setting_read(Setting.LED, bytes.fromhex(reply))


def test_setting_write() -> None:
    """Setting writes match the app traffic."""
    assert encode_setting_write(Setting.LED, True).hex() == "011a"
    assert encode_setting_write(Setting.VIBRATION, False).hex() == "033c"
    assert setting_write_accepted(Setting.LED, bytes.fromhex("0100"))
    assert not setting_write_accepted(Setting.LED, bytes.fromhex("0200"))
    assert not setting_write_accepted(Setting.LED, bytes.fromhex("0104"))


def test_parse_battery() -> None:
    """The battery level is a percentage."""
    assert parse_battery(b"\x63") == 99
    with pytest.raises(ProtocolError):
        parse_battery(b"")
    with pytest.raises(ProtocolError):
        parse_battery(b"\xff")


def test_duration_until_same_day() -> None:
    """A wake-up time later today is used as is."""
    now = datetime(2026, 10, 1, 5, 0, tzinfo=timezone.utc)
    assert duration_until(time(7, 30), now) == timedelta(hours=2, minutes=30)


def test_duration_until_matches_app() -> None:
    """The app sent 72530 s for a 9:30 wake-up when started at 13:21:10."""
    now = datetime(2026, 10, 1, 13, 21, 10, tzinfo=ZoneInfo("Europe/Moscow"))
    assert duration_until(time(9, 30), now) == timedelta(seconds=72530)


def test_duration_until_now_means_tomorrow() -> None:
    """A wake-up time equal to the current time is a full day away."""
    now = datetime(2026, 10, 1, 7, 0, tzinfo=timezone.utc)
    assert duration_until(time(7, 0), now) == timedelta(days=1)


def test_duration_until_across_dst_change() -> None:
    """The duration is real elapsed time when the clocks change at night."""
    berlin = ZoneInfo("Europe/Berlin")
    # Clocks go back one hour on 2026-10-25 at 03:00.
    now = datetime(2026, 10, 24, 23, 0, tzinfo=berlin)
    assert duration_until(time(7, 0), now) == timedelta(hours=9)


def test_duration_until_requires_timezone() -> None:
    """A naive current time is rejected."""
    with pytest.raises(ValueError):
        duration_until(time(7, 0), datetime(2026, 10, 1, 5, 0))
