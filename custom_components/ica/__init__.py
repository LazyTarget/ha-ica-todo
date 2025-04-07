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
from .icatypes import AuthCredentials, AuthState

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TODO]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    setup_global_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ICA from a config entry."""
    _LOGGER.info(
        "Loaded ICA config entry v%s.%s - Data: %s",
        entry.version,
        entry.minor_version,
        entry.data,
    )

    uid = entry.data[CONF_ICA_ID]
    pin = entry.data[CONF_ICA_PIN]
    update_interval = datetime.timedelta(
        minutes=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    credentials = AuthCredentials(username=uid, password=pin)
    auth_state: AuthState = entry.data.get("auth_state", {})
    api = IcaAPIAsync(credentials, auth_state)

    coordinator = IcaCoordinator(
        hass,
        entry,
        _LOGGER,
        update_interval,
        api,
    )
    await coordinator.init_cache()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    entry.coordinator = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("Final config entry data: %s", entry.data)
    _LOGGER.info("ICA integration successfully setup!")
    return True


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )
    _LOGGER.debug("Config data: %s", config_entry.data)

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        new_data = {**config_entry.data}
        if config_entry.minor_version < 2:
            if "access_token" in new_data:
                del new_data["access_token"]
            if "user" in new_data:
                del new_data["user"]
            if "userInfo" in new_data["auth_state"]:
                del new_data["auth_state"]["userInfo"]

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, minor_version=2, version=1
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
