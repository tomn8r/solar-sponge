"""Binary sensor platform for Solar Sponge."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the binary sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SolarSpongePermission(coordinator, entry)])


class SolarSpongePermission(CoordinatorEntity, BinarySensorEntity):
    """Representation of the Solar Sponge Permission sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "HA Solar Reserve Permission"
        self._attr_unique_id = f"{entry.entry_id}_solar_reserve_permission"
        self._attr_device_class = BinarySensorDeviceClass.POWER
        self._attr_icon = "mdi:sun-snowflake"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info to group all entities under one device card."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=NAME,
            manufacturer="Solar Sponge",
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
        return {
            "calculated_surplus_kwh": round(data.get("surplus_kwh", 0.0), 2),
            "estimated_ac_runtime_hours": round(data.get("estimated_runtime", 0.0), 1),
            "dynamic_expected_load_kwh": round(data.get("dynamic_expected_load", 10.0), 2),
            "tomorrow_deficit_kwh": round(data.get("tomorrow_deficit", 0.0), 2),
            "avg_night_load_kwh": round(data.get("avg_night_load", 10.0), 2),
            "avg_day_load_kwh": round(data.get("avg_day_load", 10.0), 2),
        }
