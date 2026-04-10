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

_ENTITY_SELECTOR = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


def _req(key, defaults, entity_selector):
    """Return a vol.Required field, with default only if value actually exists."""
    val = defaults.get(key)
    if val:
        return {vol.Required(key, default=val): entity_selector}
    return {vol.Required(key): entity_selector}


def _opt(key, defaults, entity_selector):
    """Return a vol.Optional field, with default only if value actually exists."""
    val = defaults.get(key)
    if val:
        return {vol.Optional(key, default=val): entity_selector}
    return {vol.Optional(key): entity_selector}


def _get_user_schema(defaults=None):
    defaults = defaults or {}
    schema = {}
    schema.update(_req(CONF_TOTAL_HOME_ENERGY, defaults, _ENTITY_SELECTOR))
    schema[vol.Required(CONF_METER_RESETS_DAILY, default=defaults.get(CONF_METER_RESETS_DAILY, False))] = bool
    schema.update(_opt(CONF_AC_ENERGY, defaults, _ENTITY_SELECTOR))
    schema.update(_req(CONF_SOLAR_REMAINING_TODAY, defaults, _ENTITY_SELECTOR))
    schema.update(_req(CONF_SOLAR_TOMORROW, defaults, _ENTITY_SELECTOR))
    return vol.Schema(schema)


def _get_battery_schema(defaults=None):
    defaults = defaults or {}
    schema = {}
    schema.update(_req(CONF_BATTERY_REMAINING, defaults, _ENTITY_SELECTOR))
    schema[vol.Required(CONF_BATTERY_SENSOR_TYPE, default=defaults.get(CONF_BATTERY_SENSOR_TYPE, "energy"))] = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                {"value": "energy", "label": "Energy (kWh)"},
                {"value": "percentage", "label": "Percentage (%)"}
            ],
            mode=selector.SelectSelectorMode.DROPDOWN
        )
    )
    schema.update(_opt(CONF_BATTERY_CAPACITY_ENTITY, defaults, _ENTITY_SELECTOR))
    
    cap_man_val = defaults.get(CONF_BATTERY_CAPACITY_MANUAL)
    if cap_man_val is not None:
        schema[vol.Optional(CONF_BATTERY_CAPACITY_MANUAL, default=cap_man_val)] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=500, step=0.1, unit_of_measurement="kWh")
        )
    else:
        schema[vol.Optional(CONF_BATTERY_CAPACITY_MANUAL)] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=500, step=0.1, unit_of_measurement="kWh")
        )
    
    schema[vol.Required(CONF_EMERGENCY_RESERVE_PERCENT, default=defaults.get(CONF_EMERGENCY_RESERVE_PERCENT, 0))] = selector.NumberSelector(
        selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
    )
    return vol.Schema(schema)


def _validate_capacity(user_input, errors):
    """Validate that exactly one capacity field is filled. Returns True if valid."""
    # FIX: Check the VALUE is non-empty, not just key presence
    has_ent = bool(user_input.get(CONF_BATTERY_CAPACITY_ENTITY, "").strip() if isinstance(user_input.get(CONF_BATTERY_CAPACITY_ENTITY), str) else user_input.get(CONF_BATTERY_CAPACITY_ENTITY))
    has_man = user_input.get(CONF_BATTERY_CAPACITY_MANUAL) is not None

    if has_ent and has_man:
        errors["base"] = "capacity_conflict"
        return False
    if not has_ent and not has_man:
        errors["base"] = "capacity_missing"
        return False
    return True


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
            if _validate_capacity(user_input, errors):
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
        # Merge data under options so all fields are pre-populated correctly
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
            if _validate_capacity(user_input, errors):
                self.options_data.update(user_input)

                # Cleanup whichever capacity type was NOT chosen
                has_ent = bool(user_input.get(CONF_BATTERY_CAPACITY_ENTITY))
                has_man = user_input.get(CONF_BATTERY_CAPACITY_MANUAL) is not None
                if has_ent:
                    self.options_data.pop(CONF_BATTERY_CAPACITY_MANUAL, None)
                if has_man:
                    self.options_data.pop(CONF_BATTERY_CAPACITY_ENTITY, None)

                return self.async_create_entry(title="", data=self.options_data)

        return self.async_show_form(
            step_id="battery", data_schema=_get_battery_schema(self.options_data), errors=errors
        )
