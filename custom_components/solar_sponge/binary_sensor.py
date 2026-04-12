"""Binary sensor platform for HA Solar Reserve."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the binary sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SolarReservePermission(coordinator, entry)])


class SolarReservePermission(CoordinatorEntity, BinarySensorEntity):
    """Representation of the HA Solar Reserve Permission sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Permission"
        self._attr_unique_id = f"{entry.entry_id}_solar_reserve_permission"
        self._attr_device_class = BinarySensorDeviceClass.POWER
        self._attr_icon = "mdi:sun-snowflake"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info to group all entities under one device card."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=NAME,
            manufacturer="HA Solar Reserve",
            model="Energy Manager",
        )

    @property
    def is_on(self):
        """Return true if there is a calculated energy surplus."""
        return self.coordinator.data.get("permission", False)

    @property
    def extra_state_attributes(self):
        """Return extra diagnostic attributes."""
        data = self.coordinator.data or {}
        surplus = data.get("surplus_kwh", 0.0)
        runtime = data.get("estimated_runtime", 0.0)
        dynamic_load = data.get("dynamic_expected_load", 10.0)
        deficit = data.get("tomorrow_deficit", 0.0)
        avg_night = data.get("avg_night_load", 10.0)
        avg_day = data.get("avg_day_load", 10.0)
        
        return {
            "calculated_surplus_kwh": round(surplus, 2) if surplus is not None else None,
            "estimated_runtime_hours": round(runtime, 1) if runtime is not None else None,
            "dynamic_expected_load_kwh": round(dynamic_load, 2) if dynamic_load is not None else None,
            "tomorrow_deficit_kwh": round(deficit, 2) if deficit is not None else None,
            "avg_night_load_kwh": round(avg_night, 2) if avg_night is not None else None,
            "avg_day_load_kwh": round(avg_day, 2) if avg_day is not None else None,
            "raw_home_energy": data.get("raw_home_energy"),
            "raw_managed_load": data.get("raw_managed_load"),
            "raw_solar_today": data.get("raw_solar_today"),
            "raw_solar_tomorrow": data.get("raw_solar_tomorrow"),
            "raw_battery_percent": data.get("raw_battery_percent"),
            "dyn_rest_of_day_kwh": data.get("dyn_rest_of_day_kwh"),
            "dyn_rest_of_night_kwh": data.get("dyn_rest_of_night_kwh"),
            "dyn_morning_buffer_kwh": data.get("dyn_morning_buffer_kwh"),
            "dyn_emergency_reserve_kwh": data.get("dyn_emergency_reserve_kwh"),
        }
