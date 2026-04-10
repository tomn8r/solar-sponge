"""Coordinator for Solar Sponge."""
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

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
    DEFAULT_AVG_NIGHT_LOAD,
    DEFAULT_AVG_DAY_LOAD,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.storage"

class SolarSpongeCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from multiple states."""

    def __init__(self, hass: HomeAssistant, entry):
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
        )
        self.entry = entry
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data_store = {
            "overnight_load_tracker": 0.0,
            "sunset_energy": 0.0,
            "sunset_ac_energy": 0.0,
            "max_energy_since_sunset": 0.0,
            "max_ac_energy_since_sunset": 0.0,
            "daily_loads": [],
            
            "daytime_load_tracker": 0.0,
            "sunrise_energy": 0.0,
            "sunrise_ac_energy": 0.0,
            "max_energy_since_sunrise": 0.0,
            "max_ac_energy_since_sunrise": 0.0,
            "daily_day_loads": [],
        }
        self.calculated_data = {
            "permission": False,
            "surplus_kwh": 0.0,
            "estimated_runtime": 0.0,
            "dynamic_expected_load": DEFAULT_AVG_NIGHT_LOAD,
            "avg_night_load": DEFAULT_AVG_NIGHT_LOAD,
            "avg_day_load": DEFAULT_AVG_DAY_LOAD,
            "tomorrow_deficit": 0.0,
        }

    def _get_config(self, key, default=None):
        """Get config from options first, then data."""
        return self.entry.options.get(key, self.entry.data.get(key, default))

    async def async_initialize(self):
        """Load stored data and setup listeners."""
        stored = await self._store.async_load()
        if stored:
            self.data_store.update(stored)

        self._recalc_average()

        entities = [
            self._get_config(CONF_TOTAL_HOME_ENERGY),
            self._get_config(CONF_BATTERY_REMAINING),
            self._get_config(CONF_SOLAR_REMAINING_TODAY),
            self._get_config(CONF_SOLAR_TOMORROW),
            self._get_config(CONF_AC_ENERGY),
        ]
        
        # Support legacy fallback too
        cap_ent = self._get_config(CONF_BATTERY_CAPACITY_ENTITY)
        legacy_cap = self.entry.data.get("battery_capacity", "")
        
        if cap_ent:
            entities.append(cap_ent)
        elif str(legacy_cap).startswith("sensor."):
            entities.append(str(legacy_cap))
            
        entities = [e for e in set(entities) if e is not None]
        
        self.entry.async_on_unload(
            async_track_state_change_event(
                self.hass, entities, self._async_sensor_changed
            )
        )
        
        self.entry.async_on_unload(
            async_track_state_change_event(
                self.hass, ["sun.sun"], self._async_sun_changed
            )
        )
        
        self.async_set_updated_data(self.calculated_data)
        self._recalculate()

    @callback
    def _async_sensor_changed(self, event):
        """Handle sensor state changes."""
        self._recalculate()

    @callback
    def _async_sun_changed(self, event):
        """Handle sun state changes."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if not new_state or not old_state:
            return

        if old_state.state == "above_horizon" and new_state.state == "below_horizon":
            self._handle_sunset()
        elif old_state.state == "below_horizon" and new_state.state == "above_horizon":
            self._handle_sunrise()
            
        self._recalculate()
        
    def _safe_float(self, entity_id, default=0.0):
        if not entity_id: return default
        state = self.hass.states.get(entity_id)
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                val = float(state.state)
                unit = state.attributes.get("unit_of_measurement", "")
                if unit in ["W", "kW", "MW"]:
                    _LOGGER.error(f"Sensor {entity_id} is reporting Power ({unit}). You must use an Energy sensor (kWh)!")
                    return default
                if unit == "Wh":
                    val = val / 1000.0
                elif unit == "MWh":
                    val = val * 1000.0
                return val
            except ValueError:
                return default
        return default

    def _get_usage_since(self, entity_id, start_key, max_key):
        if not entity_id:
            return 0.0
        current_val = self._safe_float(entity_id)
        start_val = self.data_store.get(start_key, current_val)
        max_val = self.data_store.get(max_key, start_val)
        
        if current_val > max_val:
            self.data_store[max_key] = current_val
            max_val = current_val
            
        check_daily_reset = self._get_config(CONF_METER_RESETS_DAILY, False)
        if check_daily_reset and current_val < start_val:
            return max(0.0, (max_val - start_val) + current_val)
        return max(0.0, current_val - start_val)

    def _handle_sunset(self):
        home_used = self._get_usage_since(self._get_config(CONF_TOTAL_HOME_ENERGY), "sunrise_energy", "max_energy_since_sunrise")
        ac_used = self._get_usage_since(self._get_config(CONF_AC_ENERGY), "sunrise_ac_energy", "max_ac_energy_since_sunrise")
        
        true_day_load = max(0.0, home_used - ac_used)
        self.data_store["daytime_load_tracker"] = true_day_load
        
        loads = self.data_store.get("daily_day_loads", [])
        loads.append(true_day_load)
        if len(loads) > 7: loads.pop(0)
        self.data_store["daily_day_loads"] = loads
        self._recalc_average()

        home_state = self._safe_float(self._get_config(CONF_TOTAL_HOME_ENERGY))
        self.data_store["sunset_energy"] = home_state
        self.data_store["max_energy_since_sunset"] = home_state
        
        if self._get_config(CONF_AC_ENERGY):
            ac_state = self._safe_float(self._get_config(CONF_AC_ENERGY))
            self.data_store["sunset_ac_energy"] = ac_state
            self.data_store["max_ac_energy_since_sunset"] = ac_state
            
        self.hass.async_create_task(self._store.async_save(self.data_store))

    def _handle_sunrise(self):
        home_used = self._get_usage_since(self._get_config(CONF_TOTAL_HOME_ENERGY), "sunset_energy", "max_energy_since_sunset")
        ac_used = self._get_usage_since(self._get_config(CONF_AC_ENERGY), "sunset_ac_energy", "max_ac_energy_since_sunset")
        
        true_night_load = max(0.0, home_used - ac_used)
        self.data_store["overnight_load_tracker"] = true_night_load
        
        loads = self.data_store.get("daily_loads", [])
        loads.append(true_night_load)
        if len(loads) > 7: loads.pop(0)
        self.data_store["daily_loads"] = loads
        self._recalc_average()
        
        home_state = self._safe_float(self._get_config(CONF_TOTAL_HOME_ENERGY))
        self.data_store["sunrise_energy"] = home_state
        self.data_store["max_energy_since_sunrise"] = home_state
        
        if self._get_config(CONF_AC_ENERGY):
            ac_state = self._safe_float(self._get_config(CONF_AC_ENERGY))
            self.data_store["sunrise_ac_energy"] = ac_state
            self.data_store["max_ac_energy_since_sunrise"] = ac_state

        self.hass.async_create_task(self._store.async_save(self.data_store))
                
    def _recalc_average(self):
        night_loads = self.data_store.get("daily_loads", [])
        if night_loads:
            self.calculated_data["avg_night_load"] = sum(night_loads) / len(night_loads)
        else:
            self.calculated_data["avg_night_load"] = DEFAULT_AVG_NIGHT_LOAD
            
        day_loads = self.data_store.get("daily_day_loads", [])
        if day_loads:
            self.calculated_data["avg_day_load"] = sum(day_loads) / len(day_loads)
        else:
            self.calculated_data["avg_day_load"] = DEFAULT_AVG_DAY_LOAD

    def _recalculate(self):
        """Perform the main calculations."""
        # Calculate Capacity: Entity -> Manual -> Legacy fallback
        cap_ent = self._get_config(CONF_BATTERY_CAPACITY_ENTITY)
        cap_man = self._get_config(CONF_BATTERY_CAPACITY_MANUAL)
        
        if cap_ent:
            capacity = self._safe_float(cap_ent, 10.0)
        elif cap_man is not None:
            capacity = float(cap_man)
        else:
            capacity_raw = self.entry.data.get("battery_capacity", "10.0")
            if str(capacity_raw).startswith("sensor."):
                capacity = self._safe_float(str(capacity_raw), 10.0)
            else:
                try: capacity = float(capacity_raw)
                except ValueError: capacity = 10.0

        battery_sensor_state = self._safe_float(self._get_config(CONF_BATTERY_REMAINING))
        sensor_type = self._get_config(CONF_BATTERY_SENSOR_TYPE, "energy")
        if sensor_type == "percentage":
            current_battery = capacity * (battery_sensor_state / 100.0)
        else:
            current_battery = battery_sensor_state
            
        solar_today = self._safe_float(self._get_config(CONF_SOLAR_REMAINING_TODAY))
        solar_tomorrow = self._safe_float(self._get_config(CONF_SOLAR_TOMORROW))
        
        avg_night_load = self.calculated_data["avg_night_load"]
        avg_day_load = self.calculated_data["avg_day_load"]
        
        sun_state = self.hass.states.get("sun.sun")
        is_night = sun_state and sun_state.state == "below_horizon"
        
        if is_night:
            home_used = self._get_usage_since(self._get_config(CONF_TOTAL_HOME_ENERGY), "sunset_energy", "max_energy_since_sunset")
            ac_used = self._get_usage_since(self._get_config(CONF_AC_ENERGY), "sunset_ac_energy", "max_ac_energy_since_sunset")
            used_so_far_tonight = max(0.0, home_used - ac_used)
            load_expected = max(0.0, avg_night_load - used_so_far_tonight)
        else:
            load_expected = avg_night_load
            
        self.calculated_data["dynamic_expected_load"] = load_expected
        
        tomorrow_expected_usage = avg_day_load + avg_night_load
        tomorrow_deficit = max(0.0, tomorrow_expected_usage - solar_tomorrow)
        self.calculated_data["tomorrow_deficit"] = tomorrow_deficit
        
        emergency_pct = float(self._get_config(CONF_EMERGENCY_RESERVE_PERCENT, 0))
        emergency_reserve = capacity * (emergency_pct / 100.0)
        
        total_reserve = tomorrow_deficit + emergency_reserve
        
        surplus = (current_battery + solar_today) - (load_expected + total_reserve)
        
        self.calculated_data["surplus_kwh"] = surplus
        self.calculated_data["permission"] = surplus > 0
        self.calculated_data["estimated_runtime"] = max(0.0, surplus / 3.0) if surplus > 0 else 0.0
        
        self.async_set_updated_data(self.calculated_data)
