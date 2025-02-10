"""Config flow for ICA integration."""

from http import HTTPStatus
import logging
from typing import Any

from requests.exceptions import HTTPError
import voluptuous as vol
import copy

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .icaapi_async import IcaAPIAsync
from .const import DOMAIN, CONFIG_ENTRY_NAME, CONF_ICA_ID, CONF_ICA_PIN, CONF_NUM_RECIPES, CONF_SHOPPING_LISTS, CONF_JSON_DATA_IN_DESC

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ICA_ID, description="user id (personal ID number)"): str,
        vol.Required(CONF_ICA_PIN, description="pin code"): str,
        vol.Required(
            CONF_NUM_RECIPES, default=5, description="# random recipes to retrieve"
        ): int,
    }
)

CONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_JSON_DATA_IN_DESC, description="Whether to write extra information as JSON in the description field"): bool
    }
)


class IcaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ICA."""

    VERSION = 1

    initial_input = None
    user_token = None
    shopping_lists = None

    SHOPPING_LIST_SELECTOR_SCHEMA = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        self.initial_input = user_input

        _LOGGER.fatal("Current config entries: %s", self._async_current_entries())
        if self._async_current_entries():
            _LOGGER.fatal("Current config_entry data: %s", self._async_current_entries()[0].data)
            return self.async_abort(reason="single_instance_allowed")        

        errors: dict[str, str] = {}
        if user_input is not None:
            # Assign unique id based on Account ID
            await self.async_set_unique_id(f"{DOMAIN}__{user_input[CONF_ICA_ID]}")
            # Abort flow if a config entry with same Accound ID exists (prevent duplicate requests...)
            self._abort_if_unique_id_configured()

            api = IcaAPIAsync(user_input[CONF_ICA_ID], user_input[CONF_ICA_PIN])
            try:
                self.shopping_lists = await api.get_shopping_lists()
                self.user_token = api.get_authenticated_user()
                #self.decoded_id = jwt.decode(self.user_token["id_token"], options={"verify_signature": False})
                #self.user_token["name"] = f"{self.decoded_id["given_name"]} {self.decoded_id["family_name"]}"
            except HTTPError as err:
                if err.response.status_code == HTTPStatus.UNAUTHORIZED:
                    errors["base"] = "invalid_credentials"
                else:
                    errors["base"] = "cannot_connect"
                _LOGGER.exception("HttpError %s", err, exc_info=True)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                #self.SHOPPING_LIST_SELECTOR_SCHEMA = self.build_shopping_list_selector_schema(self.shopping_lists)
                #return self.async_show_form(
                #    step_id="shoppingslists",
                #    data_shema=self.SHOPPING_LIST_SELECTOR_SCHEMA,
                #    errors=errors,
                #)
                config_entry_data = {
                    CONF_ICA_ID: user_input[CONF_ICA_ID] or self.initial_input[CONF_ICA_ID],
                    CONF_ICA_PIN: user_input[CONF_ICA_PIN] or self.initial_input[CONF_ICA_PIN],
                    "user": self.user_token,
                    "access_token": self.user_token["access_token"],
                    #CONF_SHOPPING_LISTS: user_input[CONF_SHOPPING_LISTS]
                }
                return self.async_create_entry(
                    title=CONFIG_ENTRY_NAME % self.user_token["person_name"],
                    data=config_entry_data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    # async def async_step_shoppinglists(
    #     self, user_input: dict[str, Any] | None = None
    # ) -> FlowResult:
    #     """Handle the ShoppingLists-step."""
    #     _LOGGER.warning("ShoppingLists-step!")

    #     if user_input is not None:
    #         _LOGGER.warning("User input: %s", user_input)

    #         config_entry_data = {
    #             CONF_ICA_ID: user_input[CONF_ICA_ID] or self.initial_input[CONF_ICA_ID],
    #             CONF_ICA_PIN: user_input[CONF_ICA_PIN] or self.initial_input[CONF_ICA_PIN],
    #             "user": self.user_token,
    #             "access_token": self.user_token["access_token"],
    #             CONF_SHOPPING_LISTS: user_input.get(CONF_SHOPPING_LISTS, 'defualt')
    #         }
    #         return self.async_create_entry(title=DOMAIN,
    #                                        data=config_entry_data)

    #     return self.async_show_form(
    #         step_id="shoppinglists",
    #         data_schema=self.SHOPPING_LIST_SELECTOR_SCHEMA,
    #     )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return IcaOptionsFlowHandler(config_entry)


class IcaOptionsFlowHandler(OptionsFlow):
    """Handle an options flow for ICA."""

    initial_input = None
    user_token = None
    shopping_lists = None

    SHOPPING_LIST_SELECTOR_SCHEMA = None

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Ica options flow"""
        self.config_entry = config_entry
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        self.user_token = self.config_entry.data["user"]
        _LOGGER.info("Options flow - User token: %s", self.user_token)
        _LOGGER.info("Options flow - Config_entry data: %s", self.config_entry.data)

        if self.SHOPPING_LIST_SELECTOR_SCHEMA is None:
            api = IcaAPIAsync(
                uid=self.config_entry.data[CONF_ICA_ID],
                pin=self.config_entry.data[CONF_ICA_PIN],
                user_token=self.user_token)
            if not self.shopping_lists:
                data = await api.get_shopping_lists()
                self.shopping_lists = data["shoppingLists"]
            self.SHOPPING_LIST_SELECTOR_SCHEMA = self.build_shopping_list_selector_schema(self.shopping_lists)

        config_entry_data = self.config_entry.data.copy()
        if user_input is not None:
            config_entry_data[CONF_JSON_DATA_IN_DESC] = user_input.get(CONF_JSON_DATA_IN_DESC, False)

            selection = user_input.get(CONF_SHOPPING_LISTS, [])
            if selection:
                config_entry_data[CONF_SHOPPING_LISTS] = selection
                _LOGGER.fatal("new config entry data %s", config_entry_data)
                #     # CONF_ICA_ID: user_input[CONF_ICA_ID] or self.initial_input[CONF_ICA_ID],
                #     # CONF_ICA_PIN: user_input[CONF_ICA_PIN] or self.initial_input[CONF_ICA_PIN],
                #     # "user": self.user_token,
                #     # "access_token": self.user_token["access_token"],
                #     CONF_SHOPPING_LISTS: selection,
                # }

                # #return self.async_create_entry(title=CONFIG_ENTRY_NAME % self.user_token["person_name"],
                # #                               data=config_entry_data)
                # #return self.async_create_entry(title="", data={})

                r = self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=config_entry_data,
                )
                if r:
                    self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
                return self.async_abort(reason="Integration was reloaded")

                # # Only works for ConfigFlows
                # return self.async_update_reload_and_abort(
                #     self.config_entry,
                #     data=config_entry_data
                # )
            else:
                _LOGGER.fatal("Posted other: %s", selection)

        schema = vol.Schema(
            {
                vol.Required(CONF_JSON_DATA_IN_DESC,
                             default=config_entry_data.get(CONF_JSON_DATA_IN_DESC, False),
                             description="Whether to write extra information as JSON in the description field"): bool
            }
        ).extend(self.SHOPPING_LIST_SELECTOR_SCHEMA)

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )

    def build_shopping_list_selector_schema(self, lists):
        current_lists_value = self.config_entry.data.get(CONF_SHOPPING_LISTS, [])
        schema = {
            vol.Required(CONF_SHOPPING_LISTS, description="The shopping lists to track", default=current_lists_value): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            label=list["title"],
                            value=list["offlineId"]
                        )
                        for list in lists
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True
                )
            ),
        }
        return schema
