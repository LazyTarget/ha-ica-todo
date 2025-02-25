"""The ICA integration."""

import datetime
import logging

from homeassistant.config_entries import ConfigEntry, ConfigType
from homeassistant.const import Platform, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from .icaapi_async import IcaAPIAsync
from .coordinator import IcaCoordinator
from .services import setup_global_services
from .const import DOMAIN, CONF_ICA_PIN, CONF_ICA_ID, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TODO]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    setup_global_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ICA from a config entry."""

    uid = entry.data[CONF_ICA_ID]
    pin = entry.data[CONF_ICA_PIN]
    update_interval = datetime.timedelta(
        minutes=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    user_token = entry.data["user"]
    api = IcaAPIAsync(uid, pin, user_token)
    coordinator = IcaCoordinator(hass, entry, _LOGGER, update_interval, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    entry.coordinator = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
