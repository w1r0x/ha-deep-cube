"""Sensor entities of the deep sleep cube."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CubeData, DeepCubeConfigEntry, DeepCubeCoordinator
from .entity import DeepCubeEntity
from .protocol import Program

PARALLEL_UPDATES = 0

_PROGRAM_NONE = "none"
_PROGRAM_OTHER = "other"


def _current_program(data: CubeData) -> str:
    """Return the running program, also when it was started by the app."""
    if not data.status.running:
        return _PROGRAM_NONE
    if data.status.program is None:
        return _PROGRAM_OTHER
    return data.status.program.value


@dataclass(frozen=True, kw_only=True)
class DeepCubeSensorDescription(SensorEntityDescription):
    """Description of a cube sensor."""

    value_fn: Callable[[CubeData], str | int | datetime | None]


_SENSORS = (
    DeepCubeSensorDescription(
        key="current_program",
        device_class=SensorDeviceClass.ENUM,
        options=[_PROGRAM_NONE, *(program.value for program in Program), _PROGRAM_OTHER],
        value_fn=_current_program,
    ),
    DeepCubeSensorDescription(
        key="program_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.ends_at,
    ),
    DeepCubeSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.battery,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DeepCubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        DeepCubeSensor(coordinator, description) for description in _SENSORS
    )


class DeepCubeSensor(DeepCubeEntity, SensorEntity):
    """Sensor that shows a part of the cube state."""

    entity_description: DeepCubeSensorDescription

    def __init__(
        self, coordinator: DeepCubeCoordinator, description: DeepCubeSensorDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | datetime | None:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
