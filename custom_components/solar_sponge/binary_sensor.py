"""Binary sensor platform for Solar Sponge."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the binary sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SolarSpongePermission(coordinator, entry)])

class SolarSpongePermission(CoordinatorEntity, BinarySensorEntity):
    """Representation of the Solar Sponge Permission."""

    def __init__(self, coordinator, entry):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = "Solar Sponge Permission"
        self._attr_unique_id = f"{entry.entry_id}_solar_sponge_permission"
        self._attr_device_class = BinarySensorDeviceClass.POWER
        self._attr_icon = "mdi:sun-snowflake"
        self._attr_has_entity_name = True

    @property
    def is_on(self):
        """Return true if there is a surplus of energy."""
        return self.coordinator.calculated_data.get("permission", False)

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        return {
            "calculated_surplus_kwh": round(self.coordinator.calculated_data.get("surplus_kwh", 0.0), 2),
            "estimated_ac_runtime_hours": round(self.coordinator.calculated_data.get("estimated_runtime", 0.0), 1),
            "dynamic_expected_load": round(self.coordinator.calculated_data.get("dynamic_expected_load", 10.0), 2)
        }
