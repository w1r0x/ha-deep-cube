"""Extract the ATT exchange with a single BLE device from an Android btsnoop_hci.log.

Prints only GATT operations of connections with the given address; other traffic and keys are not printed.
Usage: python tools/btsnoop_att.py <btsnoop.log> [address]
"""
import struct
import sys
from datetime import datetime, timedelta

from _address import cube_address

PATH = sys.argv[1]
ADDRESS = cube_address(sys.argv[2] if len(sys.argv) > 2 else None)
EPOCH_DELTA = 0x00DCDDB30F2F8000  # microseconds from year 0 AD to 2000-01-01 in the btsnoop format

OPCODES = {
    0x01: "ERROR", 0x02: "MTU_REQ", 0x03: "MTU_RSP", 0x04: "FIND_INFO_REQ", 0x05: "FIND_INFO_RSP",
    0x08: "READ_TYPE_REQ", 0x09: "READ_TYPE_RSP", 0x0A: "READ_REQ", 0x0B: "READ_RSP",
    0x0C: "READ_BLOB_REQ", 0x0D: "READ_BLOB_RSP", 0x10: "READ_GROUP_REQ", 0x11: "READ_GROUP_RSP",
    0x12: "WRITE_REQ", 0x13: "WRITE_RSP", 0x16: "PREP_WRITE_REQ", 0x17: "PREP_WRITE_RSP",
    0x18: "EXEC_WRITE_REQ", 0x19: "EXEC_WRITE_RSP", 0x1B: "NOTIFY", 0x1D: "INDICATE",
    0x1E: "CONFIRM", 0x52: "WRITE_CMD",
}
WITH_HANDLE = {0x0A, 0x0C, 0x12, 0x16, 0x1B, 0x1D, 0x52}


def records(data: bytes):
    offset = 16
    while offset + 24 <= len(data):
        _, included, flags, _, ts = struct.unpack(">IIIIq", data[offset:offset + 24])
        payload = data[offset + 24:offset + 24 + included]
        offset += 24 + included
        when = datetime(2000, 1, 1) + timedelta(microseconds=ts - EPOCH_DELTA)
        yield when, flags & 1, payload


def main() -> None:
    data = open(PATH, "rb").read()
    assert data[:8] == b"btsnoop\x00"
    target = bytes.fromhex(ADDRESS.replace(":", ""))[::-1]
    handles: set[int] = set()
    pending: dict[tuple[int, int], tuple[int, bytearray]] = {}
    last_read: dict[int, int] = {}

    for when, received, packet in records(data):
        kind = packet[0]
        stamp = when.strftime("%H:%M:%S.%f")[:-3]
        if kind == 0x04 and packet[1] == 0x3E:  # LE Meta event
            sub = packet[3]
            if sub in (0x01, 0x0A) and packet[4] == 0 and packet[9:15] == target:
                handle = struct.unpack("<H", packet[5:7])[0]
                handles.add(handle)
                print(f"{stamp} -- connected handle=0x{handle:04x}")
        elif kind == 0x04 and packet[1] == 0x05:  # Disconnection complete
            handle = struct.unpack("<H", packet[4:6])[0]
            if handle in handles:
                handles.discard(handle)
                print(f"{stamp} -- disconnected reason=0x{packet[6]:02x}")
        elif kind == 0x02:
            word, length = struct.unpack("<HH", packet[1:5])
            handle, boundary = word & 0x0FFF, (word >> 12) & 3
            if handle not in handles:
                continue
            body = packet[5:5 + length]
            key = (handle, received)
            if boundary == 1:  # continuation fragment
                if key not in pending:
                    continue
                pending[key][1].extend(body)
            else:
                l2cap_len, cid = struct.unpack("<HH", body[:4])
                if cid != 4:
                    continue
                pending[key] = (l2cap_len, bytearray(body[4:]))
            l2cap_len, buffer = pending[key]
            if len(buffer) < l2cap_len:
                continue
            del pending[key]
            att = bytes(buffer)
            opcode = att[0]
            name = OPCODES.get(opcode, f"OP_{opcode:02x}")
            direction = "<-" if received else "->"
            if opcode in WITH_HANDLE:
                att_handle = struct.unpack("<H", att[1:3])[0]
                if opcode in (0x0A, 0x0C):
                    last_read[handle] = att_handle
                print(f"{stamp} {direction} {name:<10} h={att_handle:<3} {att[3:].hex()}")
            elif opcode in (0x0B, 0x0D):
                print(f"{stamp} {direction} {name:<10} h={last_read.get(handle, 0):<3} {att[1:].hex()}")
            else:
                print(f"{stamp} {direction} {name:<10}       {att[1:].hex()}")


main()
