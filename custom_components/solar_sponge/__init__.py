"""Initialize the HA Solar Reserve integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from .const import DOMAIN
from .coordinator import SolarReserveCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Solar Reserve from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Register the custom panel (only do this once if multiple entries exist)
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

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
