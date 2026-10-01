"""Diagnostics of the deep sleep cube integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import DeepCubeConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DeepCubeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics without the address of the cube."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "model": coordinator.model,
        "firmware": coordinator.firmware,
        "hardware": coordinator.hardware,
        "options": dict(entry.options),
        "last_update_success": coordinator.last_update_success,
        "status_raw": data.status.raw.hex(),
        "battery": data.battery,
        "settings": {setting.name: value for setting, value in data.settings.items()},
    }
