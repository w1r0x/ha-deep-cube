"""Passive observation of the deep sleep cube: notifications and periodic status reads.

Reads and subscriptions only, no commands are sent to the cube.
Usage: .venv/Scripts/python tools/monitor.py [seconds=240] [address]
"""
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

from bleak import BleakClient, BleakScanner

from _address import cube_address

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 240
ADDRESS = cube_address(sys.argv[2] if len(sys.argv) > 2 else None)

STATUS = "98658f39-e4e3-4ac4-8e14-b1b7ff024353"
COMMAND = "98658f3a-e4e3-4ac4-8e14-b1b7ff024353"
AUX = "9b5bfb13-20d7-4730-aa0c-993ea99fd4cd"
BATTERY = "00002a19-0000-1000-8000-00805f9b34fb"
POWER_STATE = "00002a1a-0000-1000-8000-00805f9b34fb"

LOG_DIR = Path(__file__).resolve().parents[1] / ".local" / "raw"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = (LOG_DIR / f"monitor-{datetime.now():%Y%m%d-%H%M%S}.log").open("w", encoding="utf-8")


def log(text: str) -> None:
    line = f"{datetime.now():%H:%M:%S.%f}"[:-3] + " " + text
    print(line, flush=True)
    log_file.write(line + "\n")
    log_file.flush()


async def main() -> None:
    device = await BleakScanner.find_device_by_address(ADDRESS, timeout=30)
    if device is None:
        raise SystemExit("device not found in scan")
    async with BleakClient(device, timeout=30) as client:
        log(f"connected mtu={client.mtu_size}")
        for name, uuid in (("status", STATUS), ("command", COMMAND), ("aux", AUX)):
            await client.start_notify(uuid, lambda _, data, name=name: log(f"notify {name} {data.hex()}"))
        last = {}
        deadline = time.monotonic() + DURATION
        while time.monotonic() < deadline and client.is_connected:
            for name, uuid in (("status", STATUS), ("battery", BATTERY), ("power", POWER_STATE)):
                value = (await client.read_gatt_char(uuid)).hex()
                if last.get(name) != value:
                    last[name] = value
                    log(f"read {name} {value}")
            await asyncio.sleep(2)
        log("done" if client.is_connected else "disconnected by device")


asyncio.run(main())
