"""Config flow for Solar Sponge Automation integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_TOTAL_HOME_ENERGY,
    CONF_BATTERY_REMAINING,
    CONF_SOLAR_REMAINING_TODAY,
    CONF_SOLAR_TOMORROW,
    CONF_METER_RESETS_DAILY,
    CONF_BATTERY_SENSOR_TYPE,
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CAPACITY_MANUAL,
    CONF_EMERGENCY_RESERVE_PERCENT,
    CONF_AC_ENERGY,
    NAME
)

def _get_user_schema(defaults=None):
    if defaults is None: defaults = {}
    return vol.Schema({
        vol.Required(CONF_TOTAL_HOME_ENERGY, default=defaults.get(CONF_TOTAL_HOME_ENERGY, vol.UNDEFINED)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_METER_RESETS_DAILY, default=defaults.get(CONF_METER_RESETS_DAILY, False)): bool,
        vol.Optional(CONF_AC_ENERGY, default=defaults.get(CONF_AC_ENERGY, vol.UNDEFINED)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_SOLAR_REMAINING_TODAY, default=defaults.get(CONF_SOLAR_REMAINING_TODAY, vol.UNDEFINED)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_SOLAR_TOMORROW, default=defaults.get(CONF_SOLAR_TOMORROW, vol.UNDEFINED)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
    })

def _get_battery_schema(defaults=None):
    if defaults is None: defaults = {}
    return vol.Schema({
        vol.Required(CONF_BATTERY_REMAINING, default=defaults.get(CONF_BATTERY_REMAINING, vol.UNDEFINED)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_BATTERY_SENSOR_TYPE, default=defaults.get(CONF_BATTERY_SENSOR_TYPE, "energy")): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {"value": "energy", "label": "Energy (kWh)"},
                    {"value": "percentage", "label": "Percentage (%)"}
                ],
                mode=selector.SelectSelectorMode.DROPDOWN
            )
        ),
        vol.Optional(CONF_BATTERY_CAPACITY_ENTITY, default=defaults.get(CONF_BATTERY_CAPACITY_ENTITY, vol.UNDEFINED)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Optional(CONF_BATTERY_CAPACITY_MANUAL, default=defaults.get(CONF_BATTERY_CAPACITY_MANUAL, vol.UNDEFINED)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=500, step=0.1, unit_of_measurement="kWh")
        ),
        vol.Required(CONF_EMERGENCY_RESERVE_PERCENT, default=defaults.get(CONF_EMERGENCY_RESERVE_PERCENT, 0)): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=100, step=1, unit_of_measurement="%"
            )
        ),
    })


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Sponge Automation."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

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

        return self.async_show_form(
            step_id="user", data_schema=_get_user_schema()
        )

    async def async_step_battery(self, user_input=None):
        """Handle the battery constraint step."""
        errors = {}

        if user_input is not None:
            has_ent = CONF_BATTERY_CAPACITY_ENTITY in user_input
            has_man = CONF_BATTERY_CAPACITY_MANUAL in user_input
            
            if has_ent and has_man:
                errors["base"] = "capacity_conflict"
            elif not has_ent and not has_man:
                errors["base"] = "capacity_missing"
            
            if not errors:
                self.config_data.update(user_input)
                return self.async_create_entry(title=NAME, data=self.config_data)

        return self.async_show_form(
            step_id="battery", data_schema=_get_battery_schema(), errors=errors
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Solar Sponge."""

    def __init__(self):
        """Initialize options flow."""
        self.options_data = {}

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        self.options_data = {**self.config_entry.data, **self.config_entry.options}
        return await self.async_step_user()
        
    async def async_step_user(self, user_input=None):
        """Step 1 Options."""
        if user_input is not None:
            self.options_data.update(user_input)
            return await self.async_step_battery()
            
        return self.async_show_form(
            step_id="user", data_schema=_get_user_schema(self.options_data)
        )
        
    async def async_step_battery(self, user_input=None):
        """Step 2 Options."""
        errors = {}

        if user_input is not None:
            has_ent = CONF_BATTERY_CAPACITY_ENTITY in user_input
            has_man = CONF_BATTERY_CAPACITY_MANUAL in user_input
            
            if has_ent and has_man:
                errors["base"] = "capacity_conflict"
            elif not has_ent and not has_man:
                errors["base"] = "capacity_missing"
            
            if not errors:
                self.options_data.update(user_input)
                
                # Cleanup manual vs entity
                if has_ent and CONF_BATTERY_CAPACITY_MANUAL in self.options_data:
                    self.options_data.pop(CONF_BATTERY_CAPACITY_MANUAL)
                if has_man and CONF_BATTERY_CAPACITY_ENTITY in self.options_data:
                    self.options_data.pop(CONF_BATTERY_CAPACITY_ENTITY)
                    
                return self.async_create_entry(title="", data=self.options_data)

        return self.async_show_form(
            step_id="battery", data_schema=_get_battery_schema(self.options_data), errors=errors
        )
