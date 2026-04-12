"""Initialize the HA Solar Reserve integration."""
from __future__ import annotations

import logging

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SolarReserveCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor"]

type SolarReserveConfigEntry = ConfigEntry[SolarReserveCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SolarReserveConfigEntry) -> bool:
    """Set up HA Solar Reserve from a config entry."""
    
    # Register the custom panel (only do this once across all entries)
    hass.data.setdefault(DOMAIN, {})
    if "frontend_registered" not in hass.data[DOMAIN]:
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                "/solar_reserve_frontend",
                hass.config.path("custom_components/solar_reserve/frontend"),
                False,
            )
        ])
        frontend.async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title="Solar Reserve",
            sidebar_icon="mdi:solar-power",
            frontend_url_path="solar-reserve",
            require_admin=True,
            config={
                "_panel_custom": {
                    "name": "solar-reserve-panel",
                    "embed_iframe": False,
                    "trust_external": False,
                    "js_url": "/solar_reserve_frontend/solar-reserve-panel.js",
                }
            },
        )
        hass.data[DOMAIN]["frontend_registered"] = True
    
    coordinator = SolarReserveCoordinator(hass, entry)
    await coordinator.async_initialize()

    # Modern 2024.1+ pattern: store coordinator directly in the entry
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolarReserveConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: SolarReserveConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
