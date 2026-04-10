"""Sensor platform for Solar Sponge."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        OvernightLoadTracker(coordinator, entry),
        AverageOvernightLoad(coordinator, entry),
        DaytimeLoadTracker(coordinator, entry),
        AverageDaytimeLoad(coordinator, entry),
    ])


class _SolarSpongeSensorBase(CoordinatorEntity, SensorEntity):
    """Shared base class for Solar Sponge sensors."""

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
            manufacturer="Solar Sponge",
            model="Energy Manager",
        )


class OvernightLoadTracker(_SolarSpongeSensorBase):
    """Overnight baseline energy used (current/last night, AC-isolated)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Overnight Load Tracker"
        self._attr_unique_id = f"{entry.entry_id}_overnight_load_tracker"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
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


class AverageOvernightLoad(_SolarSpongeSensorBase):
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


class DaytimeLoadTracker(_SolarSpongeSensorBase):
    """Daytime baseline energy used (current/last day, AC-isolated)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Daytime Load Tracker"
        self._attr_unique_id = f"{entry.entry_id}_daytime_load_tracker"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
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


class AverageDaytimeLoad(_SolarSpongeSensorBase):
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
