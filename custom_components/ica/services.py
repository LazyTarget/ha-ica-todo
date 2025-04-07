import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv

from .coordinator import IcaCoordinator
from .const import DOMAIN, IcaServices
from .icatypes import IcaBaseItem, IcaRecipe, ServiceCallResponse

import logging

_LOGGER = logging.getLogger(__name__)

GET_BASEITEMS_SCHEMA = vol.Schema(
    {
        # vol.Required("integration"): cv.string
        vol.Required("integration"): vol.All(cv.ensure_list, [cv.string]),
    }
)

ADD_BASEITEM_SCHEMA = vol.Schema(
    {
        # vol.Required("integration"): cv.string
        vol.Required("integration"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("identifier"): cv.string,
    }
)

LOOKUP_PRODUCT_SCHEMA = vol.Schema(
    {
        vol.Required("identifier"): cv.string,
    }
)


def setup_global_services(hass: HomeAssistant) -> None:
    if not hass.services.has_service(DOMAIN, IcaServices.REFRESH_ALL):

        async def handle_refresh_all(call: ServiceCall):
            """Call will force the coordinator to refresh all data"""
            c = 0
            for config_entry in hass.config_entries.async_entries(DOMAIN):
                if config_entry.state != ConfigEntryState.LOADED:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="not_loaded",
                        translation_placeholders={"target": config_entry.title},
                    )
                coordinator: IcaCoordinator = (
                    config_entry.coordinator or hass.data[DOMAIN][config_entry.entry_id]
                )
                await coordinator.refresh_data(invalidate_cache=True)
                coordinator.async_update_listeners()
                c += 1
            return {"updated_integrations": c}

        hass.services.async_register(
            DOMAIN,
            IcaServices.REFRESH_ALL,
            handle_refresh_all,
            schema=vol.Schema({}),
            supports_response=SupportsResponse.OPTIONAL,
        )

    if not hass.services.has_service(DOMAIN, IcaServices.GET_BASEITEMS):

        async def handle_get_baseitems(
            call: ServiceCall,
        ) -> ServiceCallResponse[list[IcaBaseItem]]:
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
                baseitems = await coordinator.async_get_baseitems(invalidate_cache=True)
                return ServiceCallResponse[list[IcaBaseItem]](
                    success=bool(baseitems), data=baseitems or []
                )
            return None

        hass.services.async_register(
            DOMAIN,
            IcaServices.GET_BASEITEMS,
            handle_get_baseitems,
            schema=GET_BASEITEMS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    if not hass.services.has_service(DOMAIN, IcaServices.ADD_BASEITEM):

        async def handle_add_baseitem(
            call: ServiceCall,
        ) -> ServiceCallResponse[list[IcaBaseItem]]:
            """Call will add item to the user's favorite items"""
            identifier = call.data["identifier"]
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
                baseitems = await coordinator.async_lookup_and_add_baseitem(identifier)
                return ServiceCallResponse[list[IcaBaseItem]](
                    success=bool(baseitems), data=baseitems or []
                )
            return ServiceCallResponse[list[IcaBaseItem]](success=False)

        hass.services.async_register(
            DOMAIN,
            IcaServices.ADD_BASEITEM,
            handle_add_baseitem,
            schema=ADD_BASEITEM_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )

    # Non-entity based Services
    if not hass.services.has_service(DOMAIN, IcaServices.GET_RECIPE):
        async def handle_get_recipe(
            call: ServiceCall,
        ) -> ServiceCallResponse[IcaRecipe]:
            """Call will query ICA api after a specific Recipe"""
            config_entry: ConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
            coordinator: IcaCoordinator = (
                config_entry.coordinator or hass.data[DOMAIN][config_entry.entry_id]
            )

            recipe_id = call.data["recipe_id"]
            recipe = await coordinator.async_get_recipe(recipe_id)
            return ServiceCallResponse[IcaRecipe](success=bool(recipe), data=recipe)

        hass.services.async_register(
            DOMAIN,
            IcaServices.GET_RECIPE,
            handle_get_recipe,
            schema=vol.Schema({vol.Required("recipe_id"): cv.string}),
            supports_response=SupportsResponse.ONLY,
        )

    # Non-entity based Services
    if not hass.services.has_service(DOMAIN, IcaServices.LOOKUP_PRODUCT):
        async def handle_lookup_product(
            call: ServiceCall,
        ) -> ServiceCallResponse[IcaRecipe]:
            """Call will query local Product registry and fill in with info from OpenFoodFacts."""
            config_entry: ConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
            coordinator: IcaCoordinator = (
                config_entry.coordinator or hass.data[DOMAIN][config_entry.entry_id]
            )
            identifier = call.data["identifier"]
            product_info = await coordinator.get_product_info(identifier)
            return ServiceCallResponse[IcaRecipe](success=bool(product_info), data=product_info)

        hass.services.async_register(
            DOMAIN,
            IcaServices.LOOKUP_PRODUCT,
            handle_lookup_product,
            schema=LOOKUP_PRODUCT_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
