import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv

from .coordinator import IcaCoordinator
from .const import DOMAIN, IcaServices

import logging

_LOGGER = logging.getLogger(__name__)

GET_BASEITEMS_SCHEMA = vol.Schema(
    {
        # vol.Required("integration"): cv.string
        vol.Required("integration"): vol.All(cv.ensure_list, [cv.string]),
    }
)


def setup_global_services(hass: HomeAssistant) -> None:
    if not hass.services.has_service(DOMAIN, IcaServices.GET_BASEITEMS):

        async def handle_get_baseitems(call: ServiceCall) -> None:
            """Call will query ICA api after the user's favorite items"""
            config_entry: ConfigEntry | None
            for entry_id in call.data["integration"]:
                if not (config_entry := hass.config_entries.async_get_entry(entry_id)):
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="integration_not_found",
                        translation_placeholders={"target": DOMAIN},
                    )
                if config_entry.state != ConfigEntryState.LOADED:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="not_loaded",
                        translation_placeholders={"target": config_entry.title},
                    )
                coordinator: IcaCoordinator = (
                    config_entry.coordinator or hass.data[DOMAIN][entry_id]
                )
                items = await coordinator.async_get_baseitems()
                return {"items": items}
            return None

        hass.services.async_register(
            DOMAIN,
            IcaServices.GET_BASEITEMS,
            handle_get_baseitems,
            schema=GET_BASEITEMS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    # Non-entity based Services
    if not hass.services.has_service(DOMAIN, IcaServices.GET_RECIPE):

        async def handle_get_recipe(call: ServiceCall) -> None:
            """Call will query ICA api after a specific Recipe"""
            config_entry: ConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
            coordinator: IcaCoordinator = (
                config_entry.coordinator or hass.data[DOMAIN][entry_id]
            )

            recipe_id = call.data["recipe_id"]
            recipe = await coordinator.async_get_recipe(recipe_id)
            return recipe

        hass.services.async_register(
            DOMAIN,
            IcaServices.GET_RECIPE,
            handle_get_recipe,
            schema=vol.Schema({vol.Required("recipe_id"): cv.string}),
            supports_response=SupportsResponse.ONLY,
        )
