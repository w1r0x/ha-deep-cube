"""The deep sleep cube integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import DeepCubeConfigEntry, DeepCubeCoordinator
from .services import async_setup_services

PLATFORMS = [Platform.SELECT, Platform.SENSOR, Platform.SWITCH, Platform.TIME]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DeepCubeConfigEntry) -> bool:
    """Set up a cube from a config entry."""
    coordinator = DeepCubeCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DeepCubeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_options(
    hass: HomeAssistant, entry: DeepCubeConfigEntry
) -> None:
    """Apply changed options without reconnecting to the cube."""
    entry.runtime_data.async_apply_options()
