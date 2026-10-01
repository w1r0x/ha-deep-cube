"""Config flow of the deep sleep cube integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_MODEL,
    CONF_SCAN_INTERVAL,
    UnitOfTime,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MAX_SCAN_INTERVAL, MIN_SCAN_INTERVAL
from .protocol import MODEL_NAMES

_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement=UnitOfTime.MINUTES,
                )
            ),
            vol.Coerce(int),
        )
    }
)


def _title(model: str, address: str) -> str:
    """Return a title that tells apart several cubes of one model."""
    return f"{model} {address[-5:]}"


class DeepCubeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a deep sleep cube."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> DeepCubeOptionsFlow:
        """Create the options flow."""
        return DeepCubeOptionsFlow()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a cube found by Bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        if discovery_info.name not in MODEL_NAMES:
            return self.async_abort(reason="not_supported")
        self._discovery = discovery_info
        self.context["title_placeholders"] = {
            "name": _title(discovery_info.name, discovery_info.address)
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding a discovered cube."""
        assert self._discovery is not None
        title = _title(self._discovery.name, self._discovery.address)
        if user_input is not None:
            return self.async_create_entry(
                title=title,
                data={
                    CONF_ADDRESS: self._discovery.address,
                    CONF_MODEL: self._discovery.name,
                },
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders={"name": title}
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick one of the cubes in range."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            model = self._discovered[address]
            return self.async_create_entry(
                title=_title(model, address),
                data={CONF_ADDRESS: address, CONF_MODEL: model},
            )

        configured = self._async_current_ids(include_ignore=False)
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address not in configured and info.name in MODEL_NAMES:
                self._discovered[info.address] = info.name
        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: _title(model, address)
                            for address, model in self._discovered.items()
                        }
                    )
                }
            ),
        )


class DeepCubeOptionsFlow(OptionsFlow):
    """Handle the options of a deep sleep cube."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
