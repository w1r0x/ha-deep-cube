"""Switch entities of the deep sleep cube: the program and the cube settings."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DeepCubeConfigEntry, DeepCubeCoordinator
from .entity import DeepCubeEntity
from .protocol import Setting

# The cube accepts one connection; the coordinator serializes the commands.
PARALLEL_UPDATES = 1

_SETTING_KEYS: dict[Setting, str] = {
    Setting.LED: "led",
    Setting.LED_AUTO_OFF: "led_auto_off",
    Setting.VIBRATION: "vibration",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DeepCubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            DeepCubeProgramSwitch(coordinator),
            *(DeepCubeSettingSwitch(coordinator, setting) for setting in Setting),
        ]
    )


class DeepCubeProgramSwitch(DeepCubeEntity, SwitchEntity):
    """Starts the selected program and stops the running one.

    This is the main feature of the cube, so the entity carries the device name.
    """

    _attr_name = None

    def __init__(self, coordinator: DeepCubeCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, "program")

    @property
    def is_on(self) -> bool:
        """Return true while a program is running."""
        return self.coordinator.data.status.running

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the selected program until the wake-up time."""
        await self.coordinator.async_start_program()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the running program."""
        await self.coordinator.async_stop_program()


class DeepCubeSettingSwitch(DeepCubeEntity, SwitchEntity):
    """On/off setting stored in the cube."""

    _attr_entity_category = EntityCategory.CONFIG
    # Rarely changed: reachable on the device page, kept off the dashboards.
    _attr_entity_registry_visible_default = False

    def __init__(self, coordinator: DeepCubeCoordinator, setting: Setting) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, _SETTING_KEYS[setting])
        self._setting = setting

    @property
    def is_on(self) -> bool:
        """Return true if the setting is on."""
        return self.coordinator.data.settings[self._setting]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self.coordinator.async_set_setting(self._setting, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self.coordinator.async_set_setting(self._setting, False)
