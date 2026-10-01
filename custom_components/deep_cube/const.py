"""Constants of the deep sleep cube integration."""

from datetime import time

from .protocol import Intensity, Program

DOMAIN = "deep_cube"
MANUFACTURER = "deep"

DEFAULT_SCAN_INTERVAL = 5
MIN_SCAN_INTERVAL = 1
MAX_SCAN_INTERVAL = 60

DEFAULT_PROGRAM = Program.JUST_SLEEP
DEFAULT_INTENSITY = Intensity.NORMAL
DEFAULT_WAKE_TIME = time(7, 0)

ATTR_PROGRAM = "program"
ATTR_INTENSITY = "intensity"
ATTR_WAKE_TIME = "wake_time"

SERVICE_START_PROGRAM = "start_program"
SERVICE_STOP_PROGRAM = "stop_program"
