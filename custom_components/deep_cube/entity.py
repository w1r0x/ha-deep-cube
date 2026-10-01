"""Base entities of the deep sleep cube integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import DeepCubeCoordinator


def _device_info(coordinator: DeepCubeCoordinator) -> DeviceInfo:
    """Describe the cube for the device registry."""
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.address)},
        connections={(CONNECTION_BLUETOOTH, coordinator.address)},
        name=coordinator.config_entry.title,
        manufacturer=MANUFACTURER,
        model=coordinator.model,
        sw_version=coordinator.firmware,
        hw_version=coordinator.hardware,
    )


class DeepCubeEntity(CoordinatorEntity[DeepCubeCoordinator]):
    """Entity that shows state read from the cube."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DeepCubeCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = _device_info(coordinator)


class DeepCubeLaunchEntity(Entity):
    """Entity that keeps a parameter of the next program start.

    The value lives in Home Assistant and is sent to the cube only with the
    start command, so the entity stays available while the cube is out of reach.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: DeepCubeCoordinator, key: str) -> None:
        """Initialize the entity."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = _device_info(coordinator)
