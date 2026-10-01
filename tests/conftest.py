"""Test setup: load the protocol module without importing Home Assistant."""

import importlib.util
from pathlib import Path
import sys

COMPONENT_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "deep_cube"

# Importing the package would pull in Home Assistant; the protocol module is
# self-contained, so it is loaded straight from its file.
_spec = importlib.util.spec_from_file_location(
    "deep_cube_protocol", COMPONENT_DIR / "protocol.py"
)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)
