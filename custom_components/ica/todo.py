"""A todo platform for ICA shopping lists."""

import asyncio
import datetime
import json
from typing import Any, cast
import voluptuous as vol
import uuid

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    Event,
    HomeAssistant,
    ServiceCall,
    callback,
    SupportsResponse,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, CONF_JSON_DATA_IN_DESC, IcaServices
from .coordinator import IcaCoordinator
from .icatypes import IcaShoppingList

import logging

_LOGGER = logging.getLogger(__name__)

# #GET_RECIPE_SERVICE_SCHEMA = vol.Schema(
# GET_RECIPE_SERVICE_SCHEMA = cv._make_entity_service_schema(

# )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ICA shopping list platform config entry."""
    coordinator: IcaCoordinator = hass.data[DOMAIN][entry.entry_id]
    shopping_lists: list[IcaShoppingList] = await coordinator.async_get_shopping_lists()
    async_add_entities(
        IcaShoppingListEntity(
            coordinator, entry, shopping_list["offlineId"], shopping_list["title"]
        )
        for shopping_list in shopping_lists
    )
    async_register_services(hass, coordinator)


def async_register_services(hass: HomeAssistant, coordinator: IcaCoordinator) -> None:
    """Register services."""

    async def handle_add_offer_to_shopping_list(entity: IcaShoppingListEntity, call: ServiceCall) -> None:
        """Call will add an existing Offer to a ICA shopping list"""
        offer_id = call.data["offer_id"]
        offer = coordinator.get_offer_info_full(offer_id)
        # _LOGGER.fatal("Offer to add: %s", offer)
        if not offer:
            return
        item = {
            "internalOrder": 999,
            "productName": offer["name"],
            "isStrikedOver": False,
            "sourceId": -1,
            "articleGroupId": offer.get("category", {}).get("articleGroupId", 12),
            "articleGroupIdExtended": offer.get("category", {}).get("expandedArticleGroupId", 12),
            "offerId": offer_id,
            "lastChange": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "offlineId": str(uuid.uuid4()),
        }
        # _LOGGER.fatal("Item to add: %s", item)
        await entity._async_create_todo_item_from_ica_shopping_list_item(item)
        return item

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        IcaServices.Add_OFFER_TO_SHOPPING_LIST,
        {
            vol.Required("offer_id"): cv.string
        },
        handle_add_offer_to_shopping_list,
        supports_response=SupportsResponse.OPTIONAL)

    # # Non-entity based Services
    # if not hass.services.has_service(DOMAIN, IcaServices.GET_RECIPE):
    #     async def handle_get_recipe(call: ServiceCall) -> None:
    #         """Call will query ICA api after a specific Recipe"""
    #         recipe_id = call.data["recipe_id"]
    #         recipe = await coordinator.async_get_recipe(recipe_id)
    #         return recipe

    #     hass.services.async_register(
    #         DOMAIN,
    #         IcaServices.GET_RECIPE,
    #         handle_get_recipe,
    #         schema=vol.Schema({
    #             vol.Required("recipe_id"): cv.string
    #         }),
    #         supports_response=SupportsResponse.ONLY)


def _task_api_data(item: TodoItem) -> dict[str, Any]:
    """Convert a TodoItem to the set of add or update arguments."""
    item_data: dict[str, Any] = {}
    if summary := item.summary:
        item_data["content"] = summary
    if due := item.due:
        if isinstance(due, datetime.datetime):
            item_data["due"] = {
                "date": due.date().isoformat(),
                "datetime": due.isoformat(),
            }
        else:
            item_data["due"] = {"date": due.isoformat()}
    if description := item.description:
        item_data["description"] = description
    return item_data


class IcaShoppingListEntity(CoordinatorEntity[IcaCoordinator], TodoListEntity):
    """A ICA shopping list TodoListEntity."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
    )

    def __init__(
        self,
        coordinator: IcaCoordinator,
        config_entry: ConfigEntry,
        shopping_list_id: str,
        shopping_list_name: str,
    ) -> None:
        """Initialize IcaShoppingListEntity."""
        if config_entry.data.get(CONF_JSON_DATA_IN_DESC, False):
            self._attr_supported_features = (
                TodoListEntityFeature.CREATE_TODO_ITEM
                | TodoListEntityFeature.UPDATE_TODO_ITEM
                | TodoListEntityFeature.DELETE_TODO_ITEM
                | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
                | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
                # adds Description
                | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
            )

        super().__init__(coordinator=coordinator)
        self._config_entry = config_entry
        self._project_id = shopping_list_id
        self._attr_unique_id = f"{config_entry.entry_id}-{shopping_list_id}"
        self._attr_name = shopping_list_name
        # self._attr_icon = "icon.png"
        self._attr_icon = "mdi:cart"

    @property
    def name(self):
        return f"ICA {self._attr_name}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        items = []
        shopping_list = self.coordinator.get_shopping_list(self._project_id)
        if shopping_list:
            self._project_name = shopping_list["title"]
            for task in shopping_list["rows"]:
                if task.get("offerId", None):
                    offer = self.coordinator.get_offer_info(task["offerId"])
                    task["offer"] = offer
                    task["due"] = offer.get("validTo", None) if offer else None
                due = (
                    datetime.datetime.fromisoformat(task["due"])
                    if task.get("due", None)
                    else None
                )

                items.append(
                    TodoItem(
                        summary=task["productName"],
                        uid=task["offlineId"],
                        status=TodoItemStatus.COMPLETED
                        if task["isStrikedOver"]
                        else TodoItemStatus.NEEDS_ACTION,
                        description=self.generate_item_description(task)
                        if self._config_entry.data.get(CONF_JSON_DATA_IN_DESC, False)
                        else None,
                        due=due,
                    )
                )
            _LOGGER.debug("%s ITEMS: %s", self._project_name, items)
        self._attr_todo_items = items
        super()._handle_coordinator_update()

    def generate_item_description(self, item: TodoItem):
        if not item:
            return None
        result = {}

        if item.get("quantity", None):
            result["quantity"] = item.get("quantity")

        if item.get("unit", None):
            result["unit"] = item.get("unit")

        if item.get("articleGroupId", None):
            result["articleGroupId"] = item.get("articleGroupId")

        if item.get("offerId", None):
            result["offerId"] = item.get("offerId")

        if item.get("due", None):
            result["due"] = item.get("due")

        if item.get("sourceId", None):
            result["sourceId"] = item.get("sourceId")

        if item.get("productEan", None):
            result["productEan"] = item.get("productEan")

        if item.get("recepies", None):
            result["recepies"] = item.get("recepies")

        if not result.keys():
            return None
        result = json.dumps(result)
        return result

    async def _async_create_todo_item_from_ica_shopping_list_item(self, row_item):
        """Create a To-do item."""
        # if item.status != TodoItemStatus.NEEDS_ACTION:
        #     raise ValueError("Only active tasks may be created.")
        shopping_list = await self.coordinator.async_get_shopping_list(
            self._project_id,
            invalidate_cache=True
        )

        # ti = self.coordinator.parse_summary(item.summary)
        # ti["sourceId"] = -1
        # ti["isStrikedOver"] = False
        if "createdRows" not in shopping_list:
            shopping_list["createdRows"] = []
        shopping_list["createdRows"].append(row_item)

        shopping_list["latestChange"] = (
            datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        )
        await self.coordinator.api.sync_shopping_list(shopping_list)
        await self.coordinator.async_refresh()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a To-do item."""
        if item.status != TodoItemStatus.NEEDS_ACTION:
            raise ValueError("Only active tasks may be created.")
        # shopping_list = self.coordinator.get_shopping_list(self._project_id)
        shopping_list = await self.coordinator.async_get_shopping_list(
            self._project_id,
            invalidate_cache=True
        )

        ti = self.coordinator.parse_summary(item.summary)
        ti["sourceId"] = -1
        ti["isStrikedOver"] = False
        if "createdRows" not in shopping_list:
            shopping_list["createdRows"] = []
        shopping_list["createdRows"].append(ti)

        shopping_list["latestChange"] = (
            datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        )
        await self.coordinator.api.sync_shopping_list(shopping_list)
        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a To-do item."""
        # shopping_list = self.coordinator.get_shopping_list(self._project_id)
        shopping_list = await self.coordinator.async_get_shopping_list(
            self._project_id,
            invalidate_cache=True
        )

        if "changedRows" not in shopping_list:
            shopping_list["changedRows"] = []

        shopping_list["changedRows"].append(
            {
                "offlineId": item.uid,
                "isStrikedOver": item.status == TodoItemStatus.COMPLETED,
                "sourceId": -1,
            }
        )
        # if item.status is not None:
        #    if item.status == TodoItemStatus.COMPLETED:
        #        await self.coordinator.api.close_task(task_id=uid)
        #    else:
        #        await self.coordinator.api.reopen_task(task_id=uid)

        await self.coordinator.api.sync_shopping_list(shopping_list)
        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete a To-do item."""
        # await asyncio.gather(
        #     *[self.coordinator.api.remove_from_list(task_id=uid) for uid in uids]
        # )
        # shopping_list = self.coordinator.get_shopping_list(self._project_id)
        shopping_list = await self.coordinator.async_get_shopping_list(
            self._project_id,
            invalidate_cache=True
        )

        if "deletedRows" not in shopping_list:
            shopping_list["deletedRows"] = []

        # shopping_list["DeletedRows"].extend(list(deleted_ids))
        shopping_list["deletedRows"].extend(uids)

        await self.coordinator.api.sync_shopping_list(shopping_list)
        await self.coordinator.async_refresh()

    # async def async_move_todo_item(self, uid: str, previous_uid: str | None) -> None:
    #     """Move a To-do item."""
    #     # await asyncio.gather(
    #     #     *[self.coordinator.api.remove_from_list(task_id=uid) for uid in uids]
    #     # )
    #     shopping_list = self.coordinator.get_shopping_list(self._project_id)
    #     await self.coordinator.api.sync_shopping_list(shopping_list)
    #     await self.coordinator.async_refresh()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass update state from existing coordinator data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
