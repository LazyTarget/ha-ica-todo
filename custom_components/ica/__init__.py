"""The ICA integration."""

import datetime
import logging
import json

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

    uid = entry.data[CONF_ICA_ID]
    pin = entry.data[CONF_ICA_PIN]
    update_interval = datetime.timedelta(
        minutes=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    user_token = entry.data.get("user", None)
    _LOGGER.warning("Current persisted user: %s", user_token)

    credentials = AuthCredentials({"username": uid, "password": pin})
    auth_state = AuthState(entry.data.get("auth_state", {}))
    auth_state["token"] = user_token

    pre = json.dumps(auth_state)
    _LOGGER.warning("Before ensure_login: %s", auth_state)

    api = IcaAPIAsync(credentials, auth_state)
    await api.ensure_login()
    coordinator = IcaCoordinator(hass, entry, _LOGGER, update_interval, api)

    ft = api.get_authenticated_user()
    _LOGGER.warning("Before first_refresh: %s", ft)
    await coordinator.async_config_entry_first_refresh()
    at = api.get_authenticated_user()
    _LOGGER.warning("After first_refresh: %s", at)
    post = json.dumps(at)
    diff = pre != post
    _LOGGER.warning("Config entry state diff: %s", diff)
    if diff:
        new_data = entry.data.copy()
        new_data["user"] = at["token"]
        new_data["auth_state"] = at
        _LOGGER.warning("Entry data to persist: %s", new_data)
        r = hass.config_entries.async_update_entry(
            entry,
            data=new_data,
        )
        _LOGGER.warning("Update res: %s", r)

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
