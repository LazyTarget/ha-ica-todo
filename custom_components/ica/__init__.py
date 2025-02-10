"""The ica integration."""

import datetime
import logging

# from todoist_api_python.api_async import TodoistAPIAsync

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .icaapi_async import IcaAPIAsync
from .coordinator import IcaCoordinator
from .const import DOMAIN, CONF_ICA_PIN, CONF_ICA_ID, CONF_NUM_RECIPES

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=1)


PLATFORMS: list[Platform] = [Platform.TODO]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ICA from a config entry."""

    uid = entry.data[CONF_ICA_ID]
    pin = entry.data[CONF_ICA_PIN]
    #nRecipes = entry.data[CONF_NUM_RECIPES]
    #_LOGGER.fatal("async_setup_entry. %s", entry.data)
    user_token = entry.data["user"]
    api = IcaAPIAsync(uid, pin, user_token)
    coordinator = IcaCoordinator(hass, _LOGGER, SCAN_INTERVAL, api)
    _LOGGER.info("Setup entry - data: %s", entry.data)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
