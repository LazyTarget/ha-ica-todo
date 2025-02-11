"""A todo platform for ICA shopping lists."""

import asyncio
import datetime
import json
from typing import Any, cast

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (DOMAIN, CONF_JSON_DATA_IN_DESC)
from .coordinator import IcaCoordinator
from .icatypes import IcaShoppingList

import logging
_LOGGER = logging.getLogger(__name__)

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
        #| TodoListEntityFeature.MOVE_TODO_ITEM     # todo: implement
    )

    def __init__(
        self,
        coordinator: IcaCoordinator,
        config_entry: ConfigEntry,
        shopping_list_id: str,
        shopping_list_name: str,
    ) -> None:
        """Initialize IcaShoppingListEntity."""
        super().__init__(coordinator=coordinator)
        self._config_entry = config_entry
        self._project_id = shopping_list_id
        self._attr_unique_id = f"{config_entry.entry_id}-{shopping_list_id}"
        self._attr_name = shopping_list_name
        #self._attr_icon = "icon.png"
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
                items.append(
                    TodoItem(
                        summary=task["productName"],
                        uid=task["offlineId"],
                        status=TodoItemStatus.COMPLETED
                        if task["isStrikedOver"]
                        else TodoItemStatus.NEEDS_ACTION,
                        description=self.generate_item_description(task)
                        if self._config_entry.data.get(CONF_JSON_DATA_IN_DESC, False) else None,
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

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a To-do item."""
        if item.status != TodoItemStatus.NEEDS_ACTION:
            raise ValueError("Only active tasks may be created.")
        shopping_list = self.coordinator.get_shopping_list(self._project_id)

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
        shopping_list = self.coordinator.get_shopping_list(self._project_id)

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
        shopping_list = self.coordinator.get_shopping_list(self._project_id)

        if "deletedRows" not in shopping_list:
            shopping_list["deletedRows"] = []

        # shopping_list["DeletedRows"].extend(list(deleted_ids))
        shopping_list["deletedRows"].extend(uids)

        await self.coordinator.api.sync_shopping_list(shopping_list)
        await self.coordinator.async_refresh()

    async def async_move_todo_item(self, uid: str, previous_uid: str | None) -> None:
        """Move a To-do item."""
        # await asyncio.gather(
        #     *[self.coordinator.api.remove_from_list(task_id=uid) for uid in uids]
        # )
        shopping_list = self.coordinator.get_shopping_list(self._project_id)
        await self.coordinator.api.sync_shopping_list(shopping_list)
        await self.coordinator.async_refresh()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass update state from existing coordinator data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
