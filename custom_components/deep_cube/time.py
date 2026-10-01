"""Time entity of the deep sleep cube: wake-up time of the next start."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import DeepCubeConfigEntry, DeepCubeCoordinator
from .entity import DeepCubeLaunchEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DeepCubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the time entity."""
    async_add_entities([DeepCubeWakeTime(entry.runtime_data)])


class DeepCubeWakeTime(DeepCubeLaunchEntity, TimeEntity, RestoreEntity):
    """Wake-up time: a started program runs until its next occurrence."""

    def __init__(self, coordinator: DeepCubeCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, "wake_time")

    async def async_added_to_hass(self) -> None:
        """Restore the last wake-up time."""
        await super().async_added_to_hass()
        if state := await self.async_get_last_state():
            try:
                self.coordinator.wake_time = time.fromisoformat(state.state)
            except ValueError:
                pass

    @property
    def native_value(self) -> time:
        """Return the wake-up time."""
        return self.coordinator.wake_time

    async def async_set_value(self, value: time) -> None:
        """Set the wake-up time."""
        self.coordinator.wake_time = value
        self.async_write_ha_state()
