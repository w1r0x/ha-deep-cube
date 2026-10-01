"""Dump the GATT table of the deep sleep cube: services, characteristics, descriptors and readable values.

Read-only, nothing is written to the cube.
Usage: .venv/Scripts/python tools/gatt_dump.py [address] [attempts]
"""
import asyncio
import sys

from bleak import BleakClient, BleakScanner

from _address import cube_address

ADDRESS = cube_address(sys.argv[1] if len(sys.argv) > 1 else None)
ATTEMPTS = int(sys.argv[2]) if len(sys.argv) > 2 else 5


async def dump() -> None:
    device = await BleakScanner.find_device_by_address(ADDRESS, timeout=30)
    if device is None:
        raise RuntimeError("device not found in scan")
    async with BleakClient(device, timeout=30) as client:
        print(f"connected, mtu={client.mtu_size}")
        for service in client.services:
            print(f"service {service.uuid} handle={service.handle} {service.description}")
            for char in service.characteristics:
                line = f"  char {char.uuid} handle={char.handle} props={','.join(char.properties)}"
                if "read" in char.properties:
                    try:
                        value = await client.read_gatt_char(char)
                        line += f" value={value.hex()} ascii={value.decode('ascii', 'replace')!r}"
                    except Exception as err:  # noqa: BLE001
                        line += f" read_error={err}"
                print(line)
                for descriptor in char.descriptors:
                    try:
                        value = await client.read_gatt_descriptor(descriptor.handle)
                        print(f"    desc {descriptor.uuid} handle={descriptor.handle} value={value.hex()}")
                    except Exception as err:  # noqa: BLE001
                        print(f"    desc {descriptor.uuid} handle={descriptor.handle} read_error={err}")


async def main() -> None:
    for attempt in range(1, ATTEMPTS + 1):
        try:
            await dump()
            return
        except Exception as err:  # noqa: BLE001
            print(f"attempt {attempt}: {type(err).__name__}: {err}")
    raise SystemExit(1)


asyncio.run(main())
