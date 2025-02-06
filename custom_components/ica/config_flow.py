"""Config flow for ICA integration."""

from http import HTTPStatus
import logging
from typing import Any

from requests.exceptions import HTTPError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryBaseFlow, ConfigFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .icaapi_async import IcaAPIAsync
from .const import DOMAIN, CONF_ICA_ID, CONF_ICA_PIN, CONF_NUM_RECIPES, CONF_SHOPPING_LISTS

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


class IcaConfigFlow(ConfigFlow, domain=DOMAIN):
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
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            api = IcaAPIAsync(user_input[CONF_ICA_ID], user_input[CONF_ICA_PIN])
            try:
                self.shopping_lists = await api.get_shopping_lists()
                self.user_token = api.get_authenticated_user()
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
                self.SHOPPING_LIST_SELECTOR_SCHEMA = self.build_shopping_list_selector_schema(self.shopping_lists)
                return self.async_show_form(
                    step_id="shoppingslists",
                    data_shema=self.SHOPPING_LIST_SELECTOR_SCHEMA,
                    errors=errors,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    def build_shopping_list_selector_schema(self, data):
        lists = data["shoppingLists"]
        _LOGGER.fatal("Lists: %s", lists)
        _LOGGER.fatal("List[0]: %s", lists[0])
        _LOGGER.fatal("List[0][title]: %s", lists[0]["title"])
        schema = vol.Schema(
            {
                vol.Required(CONF_SHOPPING_LISTS, description="the shopping lists to track"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                label=list["title"],
                                value=list["id"]
                            )
                            for list in lists
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        _LOGGER.fatal("SCh: %s", schema)
        return schema

    async def async_step_shoppinglists(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the ShoppingLists-step."""
        _LOGGER.warning("ShoppingLists-step!")

        if user_input is not None:
            _LOGGER.warning("User input: %s", user_input)

            config_entry_data = {
                CONF_ICA_ID: user_input[CONF_ICA_ID] or self.initial_input[CONF_ICA_ID],
                CONF_ICA_PIN: user_input[CONF_ICA_PIN] or self.initial_input[CONF_ICA_PIN],
                "user": self.user_token,
                "access_token": self.user_token["access_token"],
                CONF_SHOPPING_LISTS: user_input[CONF_SHOPPING_LISTS]
            }
            return self.async_create_entry(title=DOMAIN,
                                           data=config_entry_data)

        return self.async_show_form(
            step_id="shoppinglists",
            data_schema=self.SHOPPING_LIST_SELECTOR_SCHEMA,
        )
