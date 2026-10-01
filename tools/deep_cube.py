"""Control prototype for the deep.r sleep cube over BLE (protocol recovered from the deep up 1.5.5 HCI log).

Usage: .venv/Scripts/python tools/deep_cube.py <command> [arguments] [--address AA:BB:..]
  status                       program state, battery, settings
  start <program> <minutes>    start a program (id or name) for the given time
                               (the cube silently ignores 2 minutes and accepts 30 minutes)
  start <program> HH:MM        start a program until the given wake-up time
  stop                         stop the program
  set <led|dimming|vibration> <on|off>
  watch [seconds]              print status notifications
"""
import argparse
import asyncio
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta

from bleak import BleakClient, BleakScanner

from _address import cube_address


STATUS_UUID = "98658f39-e4e3-4ac4-8e14-b1b7ff024353"
COMMAND_UUID = "98658f3a-e4e3-4ac4-8e14-b1b7ff024353"
SETTINGS_UUID = "9b5bfb13-20d7-4730-aa0c-993ea99fd4cd"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
POWER_STATE_UUID = "00002a1a-0000-1000-8000-00805f9b34fb"

CMD_START = 0x1A
CMD_STOP = 0x3C
ON, OFF = 0x1A, 0x3C  # the firmware uses the same values as "on"/"off" in settings
STATE_RUNNING = 0xAA
STATE_IDLE = 0x00
POWER_LEVELS = {"low": 0x00, "normal": 0x7F, "max": 0xFF}
DEFAULT_POWER = POWER_LEVELS["normal"]

# program ids observed in the app traffic; names as shown in the Russian interface of the app
PROGRAMS = {
    0x01: "Просто сон",
    0x0A: "Сон медведя",
    0x03: "Дрим кит",
    0x0B: "Ловец снов",
}
SETTINGS = {"led": 0x01, "dimming": 0x02, "vibration": 0x03}


@dataclass
class Status:
    raw: bytes
    state: int
    program: int
    power: int
    duration: timedelta
    elapsed: timedelta

    @classmethod
    def parse(cls, data: bytes) -> "Status":
        state, program, power, _ = data[:4]
        duration, elapsed = struct.unpack("<II", data[4:12])
        return cls(bytes(data), state, program, power, timedelta(seconds=duration), timedelta(seconds=elapsed))

    @property
    def remaining(self) -> timedelta:
        return self.duration - self.elapsed

    def __str__(self) -> str:
        if self.state == STATE_IDLE:
            return f"idle (raw {self.raw.hex()})"
        name = PROGRAMS.get(self.program, f"0x{self.program:02x}")
        state = "running" if self.state == STATE_RUNNING else f"state 0x{self.state:02x}"
        return f"{state}: program {name}, power 0x{self.power:02x}, duration {self.duration}, elapsed {self.elapsed}, remaining {self.remaining} (raw {self.raw.hex()})"


class DeepCube:
    def __init__(self, client: BleakClient) -> None:
        self.client = client
        self._replies: dict[str, asyncio.Queue[bytes]] = {COMMAND_UUID: asyncio.Queue(), SETTINGS_UUID: asyncio.Queue()}

    async def setup(self) -> None:
        for uuid, queue in self._replies.items():
            await self.client.start_notify(uuid, lambda _, data, queue=queue: queue.put_nowait(bytes(data)))

    async def _request(self, uuid: str, payload: bytes) -> bytes:
        queue = self._replies[uuid]
        while not queue.empty():
            queue.get_nowait()
        await self.client.write_gatt_char(uuid, payload, response=True)
        return await asyncio.wait_for(queue.get(), timeout=5)

    async def status(self) -> Status:
        return Status.parse(await self.client.read_gatt_char(STATUS_UUID))

    async def battery(self) -> tuple[int, int]:
        level = (await self.client.read_gatt_char(BATTERY_UUID))[0]
        power_state = (await self.client.read_gatt_char(POWER_STATE_UUID))[0]
        return level, power_state

    async def start(self, program: int, duration: timedelta, slot: int = 1, power: int = DEFAULT_POWER) -> bytes:
        payload = struct.pack("<BBBBI", CMD_START, program, power, slot, int(duration.total_seconds()))
        return await self._request(COMMAND_UUID, payload)

    async def stop(self) -> bytes:
        return await self._request(COMMAND_UUID, bytes([CMD_STOP]) + bytes(7))

    async def get_setting(self, setting: int) -> bytes:
        reply = await self._request(SETTINGS_UUID, bytes([0x00, setting]))
        return reply[3:]

    async def set_setting(self, setting: int, enabled: bool) -> bytes:
        return await self._request(SETTINGS_UUID, bytes([setting, ON if enabled else OFF]))


def parse_program(value: str) -> int:
    for program, name in PROGRAMS.items():
        if value.lower() == name.lower():
            return program
    return int(value, 0)


def parse_duration(value: str) -> timedelta:
    if ":" in value:
        now = datetime.now()
        hours, minutes = map(int, value.split(":"))
        wake = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        if wake <= now:
            wake += timedelta(days=1)
        return wake - now
    return timedelta(minutes=float(value))


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["status", "start", "stop", "set", "watch"])
    parser.add_argument("args", nargs="*")
    parser.add_argument("--address")
    parser.add_argument("--slot", type=lambda v: int(v, 0), default=1)
    parser.add_argument("--power", type=lambda v: POWER_LEVELS[v] if v in POWER_LEVELS else int(v, 0), default=DEFAULT_POWER, help="low | normal | max")
    options = parser.parse_args()

    device = await BleakScanner.find_device_by_address(cube_address(options.address), timeout=30)
    if device is None:
        raise SystemExit("cube not found: it is out of range or busy with another connection")
    async with BleakClient(device, timeout=30) as client:
        cube = DeepCube(client)
        await cube.setup()
        if options.command == "status":
            print("status:", await cube.status())
            print("battery: %d%%, power state 0x%02x" % await cube.battery())
            for name, setting in SETTINGS.items():
                value = await cube.get_setting(setting)
                print(f"{name}: {'on' if value[:1] == bytes([ON]) else 'off' if value[:1] == bytes([OFF]) else value.hex()}")
        elif options.command == "start":
            program, duration = parse_program(options.args[0]), parse_duration(options.args[1])
            print("reply:", (await cube.start(program, duration, options.slot, options.power)).hex())
            print("status:", await cube.status())
        elif options.command == "stop":
            print("reply:", (await cube.stop()).hex())
            print("status:", await cube.status())
        elif options.command == "set":
            enabled = options.args[1].lower() in ("on", "1", "true")
            print("reply:", (await cube.set_setting(SETTINGS[options.args[0]], enabled)).hex())
        elif options.command == "watch":
            await client.start_notify(STATUS_UUID, lambda _, data: print(datetime.now().strftime("%H:%M:%S"), Status.parse(data)))
            print("status:", await cube.status())
            await asyncio.sleep(float(options.args[0]) if options.args else 60)


asyncio.run(main())
