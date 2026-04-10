"""Constants for the Solar Sponge Automation integration."""

DOMAIN = "solar_sponge"
NAME = "HA Solar Reserve"

# Configuration Keys
CONF_TOTAL_HOME_ENERGY = "total_home_energy"
CONF_BATTERY_REMAINING = "battery_remaining"
CONF_SOLAR_REMAINING_TODAY = "solar_remaining_today"
CONF_SOLAR_TOMORROW = "solar_tomorrow"
CONF_METER_RESETS_DAILY = "meter_resets_daily"
CONF_BATTERY_SENSOR_TYPE = "battery_sensor_type"
CONF_BATTERY_CAPACITY_ENTITY = "battery_capacity_entity"
CONF_BATTERY_CAPACITY_MANUAL = "battery_capacity_manual"
CONF_EMERGENCY_RESERVE_PERCENT = "emergency_reserve_percent"
CONF_AC_ENERGY = "ac_energy"

# Defaults
DEFAULT_AVG_NIGHT_LOAD = 10.0
DEFAULT_AVG_DAY_LOAD = 10.0
