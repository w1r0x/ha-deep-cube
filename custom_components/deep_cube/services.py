"""Services of the deep sleep cube integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    ATTR_INTENSITY,
    ATTR_PROGRAM,
    ATTR_WAKE_TIME,
    DOMAIN,
    SERVICE_START_PROGRAM,
    SERVICE_STOP_PROGRAM,
)
from .coordinator import DeepCubeCoordinator
from .protocol import Intensity, Program

_START_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_PROGRAM): vol.Coerce(Program),
        vol.Optional(ATTR_INTENSITY): vol.Coerce(Intensity),
        vol.Optional(ATTR_WAKE_TIME): cv.time,
    }
)
_STOP_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})


def _coordinator(call: ServiceCall) -> DeepCubeCoordinator:
    """Find the coordinator of the cube a service call targets."""
    device = dr.async_get(call.hass).async_get(call.data[ATTR_DEVICE_ID])
    if device is not None:
        for entry_id in device.config_entries:
            entry = call.hass.config_entries.async_get_entry(entry_id)
            if (
                entry is not None
                and entry.domain == DOMAIN
                and entry.state is ConfigEntryState.LOADED
            ):
                return entry.runtime_data
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="device_not_found"
    )


async def _async_start_program(call: ServiceCall) -> None:
    """Start a program on a cube."""
    await _coordinator(call).async_start_program(
        call.data.get(ATTR_PROGRAM),
        call.data.get(ATTR_INTENSITY),
        call.data.get(ATTR_WAKE_TIME),
    )


async def _async_stop_program(call: ServiceCall) -> None:
    """Stop the program running on a cube."""
    await _coordinator(call).async_stop_program()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services of the integration."""
    hass.services.async_register(
        DOMAIN, SERVICE_START_PROGRAM, _async_start_program, schema=_START_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_PROGRAM, _async_stop_program, schema=_STOP_SCHEMA
    )
