"""Sensor platform for HA Solar Reserve."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        # --- Load history ---
        OvernightLoadTracker(coordinator, entry),
        AverageOvernightLoad(coordinator, entry),
        DaytimeLoadTracker(coordinator, entry),
        AverageDaytimeLoad(coordinator, entry),
        # --- Engine diagnostics ---
        CalculatedSurplus(coordinator, entry),
        EnergyAvailable(coordinator, entry),
        EnergyRequired(coordinator, entry),
        # --- Warm-up progress ---
        NightDataDaysCollected(coordinator, entry),
        DayDataDaysCollected(coordinator, entry),
        # --- Input verification ---
        ResolvedBatteryCapacity(coordinator, entry),
        ManagedLoadUsage(coordinator, entry),
    ])


class _SolarReserveSensorBase(CoordinatorEntity, SensorEntity):
    """Shared base class for HA Solar Reserve sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info to group all entities under one device card."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=NAME,
            manufacturer="HA Solar Reserve",
            model="Energy Manager",
        )


# ---------------------------------------------------------------------------
# Load History Sensors
# ---------------------------------------------------------------------------

class OvernightLoadTracker(_SolarReserveSensorBase):
    """Overnight baseline energy used (current/last night, managed load isolated)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Overnight Load Tracker"
        self._attr_unique_id = f"{entry.entry_id}_overnight_load_tracker"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        # No state_class: this is a calculated daily snapshot, not a meter
        self._attr_icon = "mdi:weather-night"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        val = self.coordinator.data.get("overnight_load_tracker", 0.0)
        return round(val, 2)

    @property
    def extra_state_attributes(self):
        return {
            "sunset_snapshot_kwh": round(self.coordinator.data_store.get("sunset_energy", 0.0), 2),
            "days_in_average": len(self.coordinator.data_store.get("daily_loads", [])),
        }


class AverageOvernightLoad(_SolarReserveSensorBase):
    """Rolling 7-day average of overnight baseline load."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Average Overnight Load"
        self._attr_unique_id = f"{entry.entry_id}_average_overnight_load"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:chart-timeline-variant"

    @property
    def native_value(self):
        val = self.coordinator.data.get("avg_night_load", 10.0)
        return round(val, 2)


class DaytimeLoadTracker(_SolarReserveSensorBase):
    """Daytime baseline energy used (current/last day, managed load isolated)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Daytime Load Tracker"
        self._attr_unique_id = f"{entry.entry_id}_daytime_load_tracker"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        # No state_class: this is a calculated daily snapshot, not a meter
        self._attr_icon = "mdi:weather-sunny"

    @property
    def native_value(self):
        val = self.coordinator.data.get("daytime_load_tracker", 0.0)
        return round(val, 2)

    @property
    def extra_state_attributes(self):
        return {
            "sunrise_snapshot_kwh": round(self.coordinator.data_store.get("sunrise_energy", 0.0), 2),
            "days_in_average": len(self.coordinator.data_store.get("daily_day_loads", [])),
        }


class AverageDaytimeLoad(_SolarReserveSensorBase):
    """Rolling 7-day average of daytime baseline load."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Average Daytime Load"
        self._attr_unique_id = f"{entry.entry_id}_average_daytime_load"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:chart-bell-curve"

    @property
    def native_value(self):
        val = self.coordinator.data.get("avg_day_load", 10.0)
        return round(val, 2)


# ---------------------------------------------------------------------------
# Engine Diagnostic Sensors
# ---------------------------------------------------------------------------

class CalculatedSurplus(_SolarReserveSensorBase):
    """Raw kWh surplus/deficit driving the permission decision.

    Positive = permission ON (surplus available to run loads).
    Negative = permission OFF (holding back for tonight or tomorrow).
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Calculated Surplus"
        self._attr_unique_id = f"{entry.entry_id}_calculated_surplus"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:scale-balance"

    @property
    def native_value(self):
        val = self.coordinator.data.get("surplus_kwh", 0.0)
        return round(val, 2)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {
            "permission": data.get("permission", False),
            "estimated_runtime_hours": round(data.get("estimated_runtime", 0.0), 1),
        }


class EnergyAvailable(_SolarReserveSensorBase):
    """Total energy available right now: battery + remaining solar today.

    This is the 'assets' side of the equation. If this looks wrong,
    check your battery sensor and solar forecast sensor inputs.
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Energy Available"
        self._attr_unique_id = f"{entry.entry_id}_energy_available"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:battery-charging-high"

    @property
    def native_value(self):
        val = self.coordinator.data.get("energy_available_kwh", 0.0)
        return round(val, 2)


class EnergyRequired(_SolarReserveSensorBase):
    """Total energy the system needs to hold in reserve.

    Equals: tonight's expected load + tomorrow's deficit + emergency reserve.
    This is the 'liabilities' side of the equation. Compare with
    Energy Available to understand the surplus calculation.
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Energy Required"
        self._attr_unique_id = f"{entry.entry_id}_energy_required"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:battery-arrow-down-outline"

    @property
    def native_value(self):
        val = self.coordinator.data.get("energy_required_kwh", 0.0)
        return round(val, 2)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {
            "dynamic_expected_load_kwh": round(data.get("dynamic_expected_load", 0.0), 2),
            "tomorrow_deficit_kwh": round(data.get("tomorrow_deficit", 0.0), 2),
        }


# ---------------------------------------------------------------------------
# Warm-Up Progress Sensors
# ---------------------------------------------------------------------------

class NightDataDaysCollected(_SolarReserveSensorBase):
    """Number of nights of data collected for the overnight rolling average (0–7).

    Until this reaches 7, the overnight average is based on fewer data points.
    During the first night it uses the 10 kWh default.
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Night Data Days Collected"
        self._attr_unique_id = f"{entry.entry_id}_night_data_days"
        self._attr_native_unit_of_measurement = "days"
        self._attr_icon = "mdi:calendar-night"
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self):
        return self.coordinator.data.get("night_data_days", 0)


class DayDataDaysCollected(_SolarReserveSensorBase):
    """Number of days of data collected for the daytime rolling average (0–7).

    Until this reaches 7, the daytime average is based on fewer data points.
    During the first day it uses the 10 kWh default.
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Day Data Days Collected"
        self._attr_unique_id = f"{entry.entry_id}_day_data_days"
        self._attr_native_unit_of_measurement = "days"
        self._attr_icon = "mdi:calendar-today"
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self):
        return self.coordinator.data.get("day_data_days", 0)


# ---------------------------------------------------------------------------
# Input Verification Sensors
# ---------------------------------------------------------------------------

class ResolvedBatteryCapacity(_SolarReserveSensorBase):
    """The battery capacity value actually being used by the engine.

    Resolved priority: entity sensor → manual input → legacy fallback.
    Use this to verify the correct capacity is being picked up.
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Resolved Battery Capacity"
        self._attr_unique_id = f"{entry.entry_id}_resolved_battery_capacity"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:battery"

    @property
    def native_value(self):
        val = self.coordinator.data.get("resolved_battery_capacity_kwh", 10.0)
        return round(val, 2)


class ManagedLoadUsage(_SolarReserveSensorBase):
    """Energy consumed by the managed load sensor since the last sunrise/sunset snapshot.

    Use this to verify that your managed load isolation is working correctly.
    During the day this resets at sunrise; at night it resets at sunset.
    Shows 0.0 if no managed load sensor is configured.
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Managed Load Usage"
        self._attr_unique_id = f"{entry.entry_id}_managed_load_usage"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:home-lightning-bolt-outline"

    @property
    def native_value(self):
        val = self.coordinator.data.get("managed_load_usage_kwh", 0.0)
        return round(val, 3)
