"""Sensor platform for Solar Sponge."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        OvernightLoadTracker(coordinator, entry),
        AverageOvernightLoad(coordinator, entry),
        DaytimeLoadTracker(coordinator, entry),
        AverageDaytimeLoad(coordinator, entry)
    ])

class OvernightLoadTracker(CoordinatorEntity, SensorEntity):
    """Representation of the overnight load tracker."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "Overnight Load Tracker"
        self._attr_unique_id = f"{entry.entry_id}_overnight_load_tracker"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:history"
        self._attr_has_entity_name = True

    @property
    def native_value(self):
        """Return the state of the sensor."""
        # Round it to 2 decimal places for neatness
        val = self.coordinator.data_store.get("overnight_load_tracker", 0.0)
        return round(val, 2)

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        return {
            "sunset_energy": round(self.coordinator.data_store.get("sunset_energy", 0.0), 2)
        }

class AverageOvernightLoad(CoordinatorEntity, SensorEntity):
    """Representation of the rolling 7-day average overnight load."""

    def __init__(self, coordinator, entry):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = "Average Overnight Load"
        self._attr_unique_id = f"{entry.entry_id}_average_overnight_load"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:chart-timeline-variant"
        self._attr_has_entity_name = True

    @property
    def native_value(self):
        """Return the state."""
        val = self.coordinator.calculated_data.get("avg_night_load", 10.0)
        return round(val, 2)

class DaytimeLoadTracker(CoordinatorEntity, SensorEntity):
    """Representation of the daytime load tracker."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "Daytime Load Tracker"
        self._attr_unique_id = f"{entry.entry_id}_daytime_load_tracker"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:weather-sunny"
        self._attr_has_entity_name = True

    @property
    def native_value(self):
        """Return the state of the sensor."""
        val = self.coordinator.data_store.get("daytime_load_tracker", 0.0)
        return round(val, 2)

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        return {
            "sunrise_energy": round(self.coordinator.data_store.get("sunrise_energy", 0.0), 2)
        }

class AverageDaytimeLoad(CoordinatorEntity, SensorEntity):
    """Representation of the rolling 7-day average daytime load."""

    def __init__(self, coordinator, entry):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = "Average Daytime Load"
        self._attr_unique_id = f"{entry.entry_id}_average_daytime_load"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:chart-timeline-variant"
        self._attr_has_entity_name = True

    @property
    def native_value(self):
        """Return the state."""
        val = self.coordinator.calculated_data.get("avg_day_load", 10.0)
        return round(val, 2)
