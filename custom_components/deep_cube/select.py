"""Select entities of the deep sleep cube: program and intensity of the next start."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import DeepCubeConfigEntry, DeepCubeCoordinator
from .entity import DeepCubeLaunchEntity
from .protocol import Intensity, Program

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DeepCubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        [DeepCubeProgramSelect(coordinator), DeepCubeIntensitySelect(coordinator)]
    )


class DeepCubeProgramSelect(DeepCubeLaunchEntity, SelectEntity, RestoreEntity):
    """Program that the next start will run."""

    _attr_options = [program.value for program in Program]

    def __init__(self, coordinator: DeepCubeCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, "program")

    async def async_added_to_hass(self) -> None:
        """Restore the last selected program."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) and state.state in self.options:
            self.coordinator.program = Program(state.state)

    @property
    def current_option(self) -> str:
        """Return the selected program."""
        return self.coordinator.program.value

    async def async_select_option(self, option: str) -> None:
        """Select a program."""
        self.coordinator.program = Program(option)
        self.async_write_ha_state()


class DeepCubeIntensitySelect(DeepCubeLaunchEntity, SelectEntity, RestoreEntity):
    """Intensity that the next start will use."""

    _attr_entity_category = EntityCategory.CONFIG
    # Rarely changed: reachable on the device page, kept off the dashboards.
    _attr_entity_registry_visible_default = False
    _attr_options = [intensity.value for intensity in Intensity]

    def __init__(self, coordinator: DeepCubeCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, "intensity")

    async def async_added_to_hass(self) -> None:
        """Restore the last selected intensity."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) and state.state in self.options:
            self.coordinator.intensity = Intensity(state.state)

    @property
    def current_option(self) -> str:
        """Return the selected intensity."""
        return self.coordinator.intensity.value

    async def async_select_option(self, option: str) -> None:
        """Select an intensity."""
        self.coordinator.intensity = Intensity(option)
        self.async_write_ha_state()
