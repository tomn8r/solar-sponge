"""Config flow for Solar Sponge Automation integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_TOTAL_HOME_ENERGY,
    CONF_BATTERY_REMAINING,
    CONF_SOLAR_REMAINING_TODAY,
    CONF_SOLAR_TOMORROW,
    CONF_METER_RESETS_DAILY,
    CONF_BATTERY_SENSOR_TYPE,
    CONF_BATTERY_CAPACITY,
    CONF_EMERGENCY_RESERVE_PERCENT,
    CONF_AC_ENERGY,
    NAME
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Sponge Automation."""

    VERSION = 1

    def __init__(self):
        """Initialize flow."""
        self.config_data = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            self.config_data.update(user_input)
            return await self.async_step_battery()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_TOTAL_HOME_ENERGY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_METER_RESETS_DAILY, default=False): bool,
                vol.Optional(CONF_AC_ENERGY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_SOLAR_REMAINING_TODAY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_SOLAR_TOMORROW): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema
        )

    async def async_step_battery(self, user_input=None):
        """Handle the battery constraint step."""
        errors = {}

        if user_input is not None:
            capacity_input = user_input.get(CONF_BATTERY_CAPACITY, "").strip()
            # Validation
            if capacity_input.startswith("sensor."):
                pass # Valid entity ID
            else:
                try:
                    val = float(capacity_input)
                    if not (0 <= val <= 500):
                        errors[CONF_BATTERY_CAPACITY] = "invalid_capacity"
                    elif round(val, 2) != val:
                        errors[CONF_BATTERY_CAPACITY] = "invalid_capacity"
                except ValueError:
                    errors[CONF_BATTERY_CAPACITY] = "invalid_capacity"
            
            if not errors:
                self.config_data.update(user_input)
                return self.async_create_entry(title=NAME, data=self.config_data)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_BATTERY_REMAINING): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_BATTERY_SENSOR_TYPE, default="energy"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": "energy", "label": "Energy (kWh)"},
                            {"value": "percentage", "label": "Percentage (%)"}
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required(CONF_BATTERY_CAPACITY): selector.TextSelector(),
                vol.Required(CONF_EMERGENCY_RESERVE_PERCENT, default=0): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=100, step=1, unit_of_measurement="%"
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="battery", data_schema=data_schema, errors=errors
        )
