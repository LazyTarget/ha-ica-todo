"""Config flow for ICA integration."""

from http import HTTPStatus
import logging
from typing import Any

from requests.exceptions import HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .icaapi_async import IcaAPIAsync
from .const import (
    DOMAIN,
    CONFIG_ENTRY_NAME,
    CONF_ICA_ID,
    CONF_ICA_PIN,
    CONF_SHOPPING_LISTS,
    CONF_JSON_DATA_IN_DESC,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ICA_ID, description="user id (personal ID number)"): str,
        vol.Required(CONF_ICA_PIN, description="pin code"): str,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
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

        if self._async_current_entries():
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
                # self.decoded_id = jwt.decode(self.user_token["id_token"], options={"verify_signature": False})
                # self.user_token["name"] = f"{self.decoded_id["given_name"]} {self.decoded_id["family_name"]}"
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
                config_entry_data = {
                    CONF_ICA_ID: user_input[CONF_ICA_ID]
                    or self.initial_input[CONF_ICA_ID],
                    CONF_ICA_PIN: user_input[CONF_ICA_PIN]
                    or self.initial_input[CONF_ICA_PIN],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL]
                    or self.initial_input[CONF_SCAN_INTERVAL],
                    "user": self.user_token,
                    "access_token": self.user_token["access_token"],
                    # CONF_SHOPPING_LISTS: user_input[CONF_SHOPPING_LISTS]
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
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        self.user_token = self.config_entry.data["user"]
        _LOGGER.debug("Options flow - data: %s", self.config_entry.data)

        if self.SHOPPING_LIST_SELECTOR_SCHEMA is None:
            api = IcaAPIAsync(
                uid=self.config_entry.data[CONF_ICA_ID],
                pin=self.config_entry.data[CONF_ICA_PIN],
                user_token=self.user_token,
            )
            if not self.shopping_lists:
                data = await api.get_shopping_lists()
                self.shopping_lists = data["shoppingLists"]
            self.SHOPPING_LIST_SELECTOR_SCHEMA = (
                self.build_shopping_list_selector_schema(self.shopping_lists)
            )

        config_entry_data = self.config_entry.data.copy()
        if user_input is not None:
            config_entry_data[CONF_SCAN_INTERVAL] = user_input.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
            config_entry_data[CONF_JSON_DATA_IN_DESC] = user_input.get(
                CONF_JSON_DATA_IN_DESC, False
            )

            if selection := user_input.get(CONF_SHOPPING_LISTS, []):
                config_entry_data[CONF_SHOPPING_LISTS] = selection
                _LOGGER.info("Options flow - new data %s", config_entry_data)
            else:
                errors[CONF_SHOPPING_LISTS] = f"Invalid value submitted: {selection}"

            if self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=config_entry_data,
            ):
                self.hass.config_entries.async_schedule_reload(
                    self.config_entry.entry_id
                )
            return self.async_abort(reason="Integration was reloaded")

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=config_entry_data.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): int,
                vol.Required(
                    CONF_JSON_DATA_IN_DESC,
                    default=config_entry_data.get(CONF_JSON_DATA_IN_DESC, False),
                    description="Whether to write extra information as JSON in the description field",
                ): bool,
            }
        ).extend(self.SHOPPING_LIST_SELECTOR_SCHEMA)

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )

    def build_shopping_list_selector_schema(self, lists):
        current_lists_value = self.config_entry.data.get(CONF_SHOPPING_LISTS, [])
        return {
            vol.Required(
                CONF_SHOPPING_LISTS,
                description="The shopping lists to track",
                default=current_lists_value,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            label=list["title"], value=list["offlineId"]
                        )
                        for list in lists
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            ),
        }
