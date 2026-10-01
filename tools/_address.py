"""Cube address for the tools: the DEEP_CUBE_ADDRESS variable or the .local/cube_address file (outside Git)."""
import os
from pathlib import Path

ADDRESS_FILE = Path(__file__).resolve().parent.parent / ".local" / "cube_address"


def cube_address(explicit: str | None = None) -> str:
    address = explicit or os.environ.get("DEEP_CUBE_ADDRESS")
    if not address and ADDRESS_FILE.exists():
        address = ADDRESS_FILE.read_text(encoding="utf-8").strip()
    if not address:
        raise SystemExit("cube address is not set: pass it as an argument, in DEEP_CUBE_ADDRESS or in .local/cube_address")
    return address.upper()
