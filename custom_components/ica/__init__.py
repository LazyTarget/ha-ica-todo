"""The ICA integration."""

import datetime
import logging
import json

from homeassistant.config_entries import ConfigEntry, ConfigType
from homeassistant.const import Platform, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from .icaapi_async import IcaAPIAsync
from .background_worker import BackgroundWorker
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
    _LOGGER.info("Config entry data: %s", entry.data)

    uid = entry.data[CONF_ICA_ID]
    pin = entry.data[CONF_ICA_PIN]
    update_interval = datetime.timedelta(
        minutes=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    credentials = AuthCredentials({"username": uid, "password": pin})
    auth_state: AuthState = entry.data.get("auth_state", {})
    # pre = json.dumps(auth_state)

    api = IcaAPIAsync(credentials, auth_state)
    # await api.ensure_login()
    coordinator = IcaCoordinator(
        hass,
        entry,
        _LOGGER,
        update_interval,
        api,
        background_worker=BackgroundWorker(hass, entry),
    )

    await coordinator.async_config_entry_first_refresh()
    # auth_state = api.get_authenticated_user()
    # post = json.dumps(auth_state)
    # diff = pre != post
    # if diff:
    #     entry.data["auth_state"] = auth_state
    #     _LOGGER.debug("Persisting new config entry data: %s", entry.data)
    #     if hass.config_entries.async_update_entry(entry, data=entry.data):
    #         _LOGGER.info(
    #             "Successfully updated config entry data with updated auth state"
    #         )
    #     else:
    #         _LOGGER.warning(
    #             "Failed to update config entry data with updated auth state"
    #         )
    # else:
    #     _LOGGER.debug("Reusing stored authentication info")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    entry.coordinator = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("Final config entry data: %s", entry.data)
    _LOGGER.info("ICA integration successfully setup!")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: IcaCoordinator = entry.coordinator
    await coordinator._worker.shutdown()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
