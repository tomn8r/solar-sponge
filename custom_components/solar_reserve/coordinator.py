"""Coordinator for HA Solar Reserve."""
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
import datetime

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
    CONF_LOAD_ENERGY,
    CONF_MORNING_BUFFER_HOURS,
    DEFAULT_AVG_NIGHT_LOAD,
    DEFAULT_AVG_DAY_LOAD,
    DEFAULT_APPLIANCE_POWER_KW,
    DEFAULT_MORNING_BUFFER_HOURS,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.storage"


class SolarReserveCoordinator(DataUpdateCoordinator):
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

        # Persisted store: snapshot values and rolling load averages only
        self.data_store = {
            "overnight_load_tracker": 0.0,
            "sunset_energy": 0.0,
            "sunset_ac_energy": 0.0,
            "daily_loads": [],
            "daytime_load_tracker": 0.0,
            "sunrise_energy": 0.0,
            "sunrise_ac_energy": 0.0,
            "daily_day_loads": [],
            "last_sunset_time": None,
            "last_sunrise_time": None,
        }

        # In-memory only: rolling max values for meter-reset detection
        # These are re-seeded from snapshot values after each load
        self._session_max = {
            "max_energy_since_sunset": 0.0,
            "max_ac_energy_since_sunset": 0.0,
            "max_energy_since_sunrise": 0.0,
            "max_ac_energy_since_sunrise": 0.0,
        }

        # Cache of the last valid floats read, allowing graceful degradation if sensors go offline
        self._last_good_states = {}

        self.calculated_data = {
            "permission": False,
            "surplus_kwh": 0.0,
            "estimated_runtime": 0.0,
            "dynamic_expected_load": DEFAULT_AVG_NIGHT_LOAD,
            "avg_night_load": DEFAULT_AVG_NIGHT_LOAD,
            "avg_day_load": DEFAULT_AVG_DAY_LOAD,
            "tomorrow_deficit": 0.0,
            # Load trackers exposed here so sensors update via coordinator signal
            "overnight_load_tracker": 0.0,
            "daytime_load_tracker": 0.0,
            # Diagnostic sensors
            "energy_available_kwh": 0.0,
            "energy_required_kwh": 0.0,
            "resolved_battery_capacity_kwh": 10.0,
            "managed_load_usage_kwh": 0.0,
            "night_data_days": 0,
            "day_data_days": 0,
        }

    def _get_config(self, key, default=None):
        """Get config from options first, then data."""
        return self.entry.options.get(key, self.entry.data.get(key, default))

    async def async_initialize(self):
        """Load stored data and setup listeners."""
        stored = await self._store.async_load()
        if stored:
            self.data_store.update(stored)
        else:
            # First run: seed snapshot values from the live sensor readings NOW.
            # Without this, _get_usage_since treats the entire meter lifetime
            # (e.g. 1,500 kWh cumulative) as energy used 'since the last snapshot',
            # which completely breaks the dynamic load calculation.
            home_entity = self._get_config(CONF_TOTAL_HOME_ENERGY)
            load_entity = self._get_config(CONF_LOAD_ENERGY)
            current_home = self._safe_float(home_entity) if home_entity else 0.0
            current_load = self._safe_float(load_entity) if load_entity else 0.0
            # Seed both sunset and sunrise snapshots to current reading
            self.data_store["sunset_energy"] = current_home
            self.data_store["sunrise_energy"] = current_home
            self.data_store["sunset_ac_energy"] = current_load
            self.data_store["sunrise_ac_energy"] = current_load
            _LOGGER.info(
                "HA Solar Reserve: first run detected. Seeding snapshots to current "
                "sensor values (home=%.3f kWh, managed_load=%.3f kWh)",
                current_home, current_load,
            )

        if not self.data_store.get("last_sunset_time"):
            self.data_store["last_sunset_time"] = dt_util.utcnow().isoformat()
        if not self.data_store.get("last_sunrise_time"):
            self.data_store["last_sunrise_time"] = dt_util.utcnow().isoformat()

        # Seed session max values from the persisted snapshots
        self._session_max["max_energy_since_sunset"] = self.data_store["sunset_energy"]
        self._session_max["max_ac_energy_since_sunset"] = self.data_store["sunset_ac_energy"]
        self._session_max["max_energy_since_sunrise"] = self.data_store["sunrise_energy"]
        self._session_max["max_ac_energy_since_sunrise"] = self.data_store["sunrise_ac_energy"]

        # Sync load trackers into calculated_data
        self.calculated_data["overnight_load_tracker"] = self.data_store["overnight_load_tracker"]
        self.calculated_data["daytime_load_tracker"] = self.data_store["daytime_load_tracker"]

        self._recalc_average()

        entities = [
            self._get_config(CONF_TOTAL_HOME_ENERGY),
            self._get_config(CONF_BATTERY_REMAINING),
            self._get_config(CONF_SOLAR_REMAINING_TODAY),
            self._get_config(CONF_SOLAR_TOMORROW),
            self._get_config(CONF_LOAD_ENERGY),
        ]

        cap_ent = self._get_config(CONF_BATTERY_CAPACITY_ENTITY)
        # Legacy fallback for users upgrading from v1.0.0
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
        """Handle sun state changes (only on real horizon crossings)."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if not new_state or not old_state:
            return

        # Explicitly require transition FROM known state to prevent restart false triggers
        if old_state.state == "above_horizon" and new_state.state == "below_horizon":
            self._handle_sunset()
        elif old_state.state == "below_horizon" and new_state.state == "above_horizon":
            self._handle_sunrise()

        self._recalculate()

    def _safe_float(self, entity_id, default=0.0):
        """Safely read a sensor state, auto-scaling energy units to kWh."""
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                val = float(state.state)
                unit = state.attributes.get("unit_of_measurement", "")
                if unit in ["W", "kW", "MW"]:
                    _LOGGER.error(
                        "Sensor %s is reporting instantaneous Power (%s). "
                        "You must use a cumulative Energy sensor (kWh/Wh/MWh)!",
                        entity_id, unit
                    )
                    return self._last_good_states.get(entity_id, default)
                if unit == "Wh":
                    val = val / 1000.0
                elif unit == "MWh":
                    val = val * 1000.0
                    
                self._last_good_states[entity_id] = val
                return val
            except (ValueError, TypeError):
                pass
                
        return self._last_good_states.get(entity_id, default)

    def _get_usage_since(self, entity_id, start_key, max_key):
        """Calculate energy used since a snapshot, handling daily resets."""
        if not entity_id:
            return 0.0
        current_val = self._safe_float(entity_id)
        start_val = self.data_store.get(start_key, current_val)

        # Update in-memory max ONLY (not persisted data_store)
        current_max = self._session_max.get(max_key, start_val)
        if current_val > current_max:
            self._session_max[max_key] = current_val
            current_max = current_val

        check_daily_reset = self._get_config(CONF_METER_RESETS_DAILY, False)
        if check_daily_reset and current_val < start_val:
            # Meter reset: total used = (progress before reset) + (progress after reset)
            return max(0.0, (current_max - start_val) + current_val)
        return max(0.0, current_val - start_val)

    def _handle_sunset(self):
        """Record daytime load and take sunset snapshots for the night."""
        home_used = self._get_usage_since(
            self._get_config(CONF_TOTAL_HOME_ENERGY), "sunrise_energy", "max_energy_since_sunrise"
        )
        ac_used = self._get_usage_since(
            self._get_config(CONF_LOAD_ENERGY), "sunrise_ac_energy", "max_ac_energy_since_sunrise"
        )

        true_day_load = max(0.0, home_used - ac_used)
        self.data_store["daytime_load_tracker"] = true_day_load
        self.calculated_data["daytime_load_tracker"] = true_day_load

        loads = self.data_store.get("daily_day_loads", [])
        loads.append(true_day_load)
        if len(loads) > 7:
            loads.pop(0)
        self.data_store["daily_day_loads"] = loads
        self._recalc_average()

        # Take sunset snapshot
        home_state = self._safe_float(self._get_config(CONF_TOTAL_HOME_ENERGY))
        self.data_store["sunset_energy"] = home_state
        self._session_max["max_energy_since_sunset"] = home_state

        load_entity = self._get_config(CONF_LOAD_ENERGY)
        if load_entity:
            ac_state = self._safe_float(load_entity)
            self.data_store["sunset_ac_energy"] = ac_state
            self._session_max["max_ac_energy_since_sunset"] = ac_state

        self.data_store["last_sunset_time"] = dt_util.utcnow().isoformat()

        self.hass.async_create_task(self._store.async_save(self.data_store))

    def _handle_sunrise(self):
        """Record overnight load and take sunrise snapshots for the day."""
        home_used = self._get_usage_since(
            self._get_config(CONF_TOTAL_HOME_ENERGY), "sunset_energy", "max_energy_since_sunset"
        )
        ac_used = self._get_usage_since(
            self._get_config(CONF_LOAD_ENERGY), "sunset_ac_energy", "max_ac_energy_since_sunset"
        )

        true_night_load = max(0.0, home_used - ac_used)
        self.data_store["overnight_load_tracker"] = true_night_load
        self.calculated_data["overnight_load_tracker"] = true_night_load

        loads = self.data_store.get("daily_loads", [])
        loads.append(true_night_load)
        if len(loads) > 7:
            loads.pop(0)
        self.data_store["daily_loads"] = loads
        self._recalc_average()

        # Take sunrise snapshot
        home_state = self._safe_float(self._get_config(CONF_TOTAL_HOME_ENERGY))
        self.data_store["sunrise_energy"] = home_state
        self._session_max["max_energy_since_sunrise"] = home_state

        load_entity = self._get_config(CONF_LOAD_ENERGY)
        if load_entity:
            ac_state = self._safe_float(load_entity)
            self.data_store["sunrise_ac_energy"] = ac_state
            self._session_max["max_ac_energy_since_sunrise"] = ac_state

        self.data_store["last_sunrise_time"] = dt_util.utcnow().isoformat()

        self.hass.async_create_task(self._store.async_save(self.data_store))

    def _recalc_average(self):
        """Recalculate the 7-day rolling averages."""
        night_loads = self.data_store.get("daily_loads", [])
        self.calculated_data["avg_night_load"] = (
            sum(night_loads) / len(night_loads) if night_loads else DEFAULT_AVG_NIGHT_LOAD
        )

        day_loads = self.data_store.get("daily_day_loads", [])
        self.calculated_data["avg_day_load"] = (
            sum(day_loads) / len(day_loads) if day_loads else DEFAULT_AVG_DAY_LOAD
        )

    def _recalculate(self):
        """Perform the main surplus calculation."""
        # --- Capacity: Entity sensor > Manual number > Legacy v1.0.0 fallback ---
        cap_ent = self._get_config(CONF_BATTERY_CAPACITY_ENTITY)
        cap_man = self._get_config(CONF_BATTERY_CAPACITY_MANUAL)

        if cap_ent:
            capacity = self._safe_float(cap_ent, 10.0)
        elif cap_man is not None:
            try:
                capacity = float(cap_man)
            except (ValueError, TypeError):
                capacity = 10.0
        else:
            capacity_raw = self.entry.data.get("battery_capacity", "10.0")
            if str(capacity_raw).startswith("sensor."):
                capacity = self._safe_float(str(capacity_raw), 10.0)
            else:
                try:
                    capacity = float(capacity_raw)
                except (ValueError, TypeError):
                    capacity = 10.0

        self.calculated_data["resolved_battery_capacity_kwh"] = round(capacity, 2)

        # --- Current battery level ---
        battery_sensor_state = self._safe_float(self._get_config(CONF_BATTERY_REMAINING), default=None)
        if battery_sensor_state is None:
            _LOGGER.debug("HA Solar Reserve: Battery sensor unavailable and no previous cache exists. Delaying recalculation.")
            return
            
        sensor_type = self._get_config(CONF_BATTERY_SENSOR_TYPE, "energy")
        current_battery = (
            capacity * (battery_sensor_state / 100.0)
            if sensor_type == "percentage"
            else battery_sensor_state
        )

        solar_today = self._safe_float(self._get_config(CONF_SOLAR_REMAINING_TODAY), default=None)
        if solar_today is None:
            _LOGGER.debug("HA Solar Reserve: Solar today sensor unavailable and no previous cache exists. Delaying recalculation.")
            return
            
        solar_tomorrow = self._safe_float(self._get_config(CONF_SOLAR_TOMORROW), default=0.0)

        energy_available = current_battery + solar_today
        self.calculated_data["energy_available_kwh"] = round(energy_available, 2)

        avg_night_load = self.calculated_data["avg_night_load"]
        avg_day_load = self.calculated_data["avg_day_load"]

        # --- Dynamic expected load (shrinks through the night as house uses energy) ---
        sun_state = self.hass.states.get("sun.sun")
        is_night = sun_state is not None and sun_state.state == "below_horizon"

        now = dt_util.utcnow()

        def parse_str_time(dt_str):
            if not dt_str:
                return now
            try:
                parsed = dt_util.parse_datetime(dt_str)
                return parsed if parsed else now
            except Exception:
                return now
                
        # --- Morning Buffer Calculation ---
        buffer_hours = float(self._get_config(CONF_MORNING_BUFFER_HOURS, DEFAULT_MORNING_BUFFER_HOURS))
        last_sunset_dt = parse_str_time(self.data_store.get("last_sunset_time"))
        last_sunrise_dt = parse_str_time(self.data_store.get("last_sunrise_time"))
        
        # Determine actual daylight duration for the buffer hourly rate (fallback to 12)
        try:
            daylight_duration_secs = (last_sunset_dt - last_sunrise_dt).total_seconds()
            daylight_hours = max(4.0, abs(daylight_duration_secs) / 3600.0)
            morning_buffer_kwh = (avg_day_load / daylight_hours) * buffer_hours
        except (TypeError, ZeroDivisionError):
            morning_buffer_kwh = 0.0

        if is_night:
            home_used = self._get_usage_since(
                self._get_config(CONF_TOTAL_HOME_ENERGY), "sunset_energy", "max_energy_since_sunset"
            )
            ac_used = self._get_usage_since(
                self._get_config(CONF_LOAD_ENERGY), "sunset_ac_energy", "max_ac_energy_since_sunset"
            )
            used_so_far_tonight = max(0.0, home_used - ac_used)
            
            # Prorating
            last_sunset = parse_str_time(self.data_store.get("last_sunset_time"))
            next_rising_str = sun_state.attributes.get("next_rising") if sun_state else None
            next_event = parse_str_time(next_rising_str) if next_rising_str else (now + datetime.timedelta(hours=12))
            
            if next_event <= now:
                next_event = now + datetime.timedelta(hours=12)
                
            total_duration = (next_event - last_sunset).total_seconds()
            remaining_duration = (next_event - now).total_seconds()
            fraction_remaining = min(1.0, max(0.0, remaining_duration / max(1.0, total_duration)))

            prorated_expected = avg_night_load * fraction_remaining
            normal_expected = max(0.0, avg_night_load - used_so_far_tonight)
            load_expected = max(prorated_expected, normal_expected)

            managed_load_used = self._get_usage_since(
                self._get_config(CONF_LOAD_ENERGY), "sunset_ac_energy", "max_ac_energy_since_sunset"
            )
        else:
            home_used = self._get_usage_since(
                self._get_config(CONF_TOTAL_HOME_ENERGY), "sunrise_energy", "max_energy_since_sunrise"
            )
            managed_load_used = self._get_usage_since(
                self._get_config(CONF_LOAD_ENERGY), "sunrise_ac_energy", "max_ac_energy_since_sunrise"
            )
            used_so_far_today = max(0.0, home_used - managed_load_used)
            
            # Prorating for day
            last_sunrise = parse_str_time(self.data_store.get("last_sunrise_time"))
            next_setting_str = sun_state.attributes.get("next_setting") if sun_state else None
            next_event = parse_str_time(next_setting_str) if next_setting_str else (now + datetime.timedelta(hours=12))
            
            if next_event <= now:
                next_event = now + datetime.timedelta(hours=12)
                
            total_duration = (next_event - last_sunrise).total_seconds()
            remaining_duration = (next_event - now).total_seconds()
            fraction_remaining = min(1.0, max(0.0, remaining_duration / max(1.0, total_duration)))

            prorated_expected_day = avg_day_load * fraction_remaining
            normal_expected_day = max(0.0, avg_day_load - used_so_far_today)
            rest_of_day_load = max(prorated_expected_day, normal_expected_day)
            
            # Overall expected combines rest of day + full night
            load_expected = rest_of_day_load + avg_night_load

        # Append the morning buffer safely onto the expected load for the next dawn
        load_expected += morning_buffer_kwh

        self.calculated_data["dynamic_expected_load"] = load_expected
        self.calculated_data["managed_load_usage_kwh"] = round(managed_load_used, 3)

        # --- 36-Hour deficit engine ---
        tomorrow_expected_usage = avg_day_load + avg_night_load
        tomorrow_deficit = max(0.0, tomorrow_expected_usage - solar_tomorrow)
        self.calculated_data["tomorrow_deficit"] = tomorrow_deficit

        emergency_pct = float(self._get_config(CONF_EMERGENCY_RESERVE_PERCENT, 0))
        emergency_reserve = capacity * (emergency_pct / 100.0)
        total_reserve = tomorrow_deficit + emergency_reserve

        # --- Final surplus ---
        energy_required = load_expected + total_reserve
        self.calculated_data["energy_required_kwh"] = round(energy_required, 2)

        # --- Data warm-up progress ---
        self.calculated_data["night_data_days"] = len(self.data_store.get("daily_loads", []))
        self.calculated_data["day_data_days"] = len(self.data_store.get("daily_day_loads", []))

        surplus = energy_available - energy_required

        self.calculated_data["surplus_kwh"] = surplus
        self.calculated_data["permission"] = surplus > 0
        try:
            self.calculated_data["estimated_runtime"] = (
                max(0.0, surplus / DEFAULT_APPLIANCE_POWER_KW) if surplus > 0 else 0.0
            )
        except ZeroDivisionError:
            self.calculated_data["estimated_runtime"] = 0.0

        self.async_set_updated_data(self.calculated_data)
