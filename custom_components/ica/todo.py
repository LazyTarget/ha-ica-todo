"""A todo platform for ICA shopping lists."""

import datetime
import json
from typing import Any
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
    HomeAssistant,
    ServiceCall,
    callback,
    SupportsResponse,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_JSON_DATA_IN_DESC, IcaServices, CONFLICT_MODES
from .coordinator import IcaCoordinator
from .icatypes import IcaShoppingList, IcaShoppingListEntry, IcaShoppingListSync

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
    shopping_list_entities = [
        IcaShoppingListEntity(
            coordinator,
            entry,
            shopping_list["offlineId"],
            shopping_list["title"],
        )
        for shopping_list in shopping_lists
    ]
    baseitem_list_entity = IcaBaseItemListEntity(coordinator, entry)
    async_add_entities([baseitem_list_entity, *shopping_list_entities])
    async_register_services(hass, coordinator)


def async_register_services(hass: HomeAssistant, coordinator: IcaCoordinator) -> None:
    """Register services."""

    async def handle_add_offer_to_shopping_list(
        entity: IcaShoppingListEntity, call: ServiceCall
    ) -> None:
        """Call will add an existing Offer to a ICA shopping list"""
        offer_id = call.data["offer_id"]
        conflict_mode = call.data.get("conflict_mode", CONFLICT_MODES[0])
        offer = coordinator.get_offer_info_full(offer_id)
        if not offer:
            return
        item = {
            "internalOrder": 999,
            "productName": offer["name"],
            "isStrikedOver": False,
            "sourceId": -1,
            "articleGroupId": offer.get("category", {}).get("articleGroupId", 12),
            "articleGroupIdExtended": offer.get("category", {}).get(
                "expandedArticleGroupId", 12
            ),
            "offerId": offer_id,
            "lastChange": (
                datetime.datetime.now(datetime.timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                + "Z"
            ),
            "offlineId": str(uuid.uuid4()),
        }
        # _LOGGER.fatal("Item to add: %s", item)
        result = await entity._async_create_todo_item_from_ica_shopping_list_item(
            item, conflict_mode
        )
        return {"result": result, "item": item}

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        IcaServices.Add_OFFER_TO_SHOPPING_LIST,
        {
            vol.Required("offer_id"): cv.string,
            vol.Optional("conflict_mode"): vol.In(CONFLICT_MODES),
        },
        handle_add_offer_to_shopping_list,
        supports_response=SupportsResponse.OPTIONAL,
    )

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
        # todo: Implement MOVE_TODO_ITEM? (ordering within the list)
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
            # Allow for setting description
            self._attr_supported_features = (
                self._attr_supported_features
                | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
            )

        super().__init__(coordinator=coordinator)
        # sourcery skip: remove-redundant-condition, swap-if-expression
        self.coordinator = coordinator if not self.coordinator else coordinator
        self._config_entry = config_entry
        self._project_id = shopping_list_id
        self._attr_unique_id = f"{config_entry.entry_id}-{shopping_list_id}"
        self._attr_name = shopping_list_name
        self._attr_icon = "mdi:cart"
        self._attr_todo_items: list[TodoItem] | None = None

    @property
    def name(self):
        return f"ICA {self._attr_name}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        items = []
        if shopping_list := self.coordinator.get_shopping_list(self._project_id):
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

        if item.get("recipes", None):
            result["recipes"] = item.get("recipes")

        if not result.keys():
            return None
        result = json.dumps(result)
        return result

    async def _async_create_todo_item_from_ica_shopping_list_item(
        self, row_item, conflict_mode
    ):
        """Create a To-do item."""
        shopping_list = await self.coordinator.async_get_shopping_list(
            self._project_id, invalidate_cache=True
        )

        offer_id = row_item.get("offerId", None)
        matches_by_offer_id = [
            r
            for r in shopping_list["rows"]
            if offer_id and r.get("offerId", None) == offer_id
        ]
        # _LOGGER.fatal("MATCHES_OFFER: %s", matches_by_offer_id)

        has_conflict = matches_by_offer_id
        if has_conflict and conflict_mode == "ignore":
            _LOGGER.warning("Ignored add due to conflict mode 'ignore': %s", row_item)
            return False
        # elif has_conflict and conflict_mode == "merge":
        #     # todo: implement...

        # ti = self.coordinator.parse_summary(item.summary)
        # ti["sourceId"] = -1
        # ti["isStrikedOver"] = False
        if "createdRows" not in shopping_list:
            shopping_list["createdRows"] = []
        shopping_list["createdRows"].append(row_item)

        shopping_list["latestChange"] = (
            f"{datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()}Z",
        )
        await self.coordinator.sync_shopping_list(shopping_list)

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a To-do item."""
        ti = self.coordinator.parse_summary(item.summary)
        ti["sourceId"] = -1
        ti["isStrikedOver"] = False
        ti["offlineId"] = str(uuid.uuid4())

        sync = IcaShoppingListSync(
            offlineId=self._project_id,
            createdRows=[IcaShoppingListEntry(ti)],
        )
        sync["latestChange"] = (
            f"{datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()}Z",
        )
        await self.coordinator.sync_shopping_list(sync)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a To-do item."""
        sync = IcaShoppingListSync(
            offlineId=self._project_id,
            changedRows=[
                IcaShoppingListEntry(
                    offlineId=item.uid,
                    isStrikedOver=item.status == TodoItemStatus.COMPLETED,
                    productName=item.summary,
                )
            ],
        )

        sync["latestChange"] = (
            f"{datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()}Z",
        )
        await self.coordinator.sync_shopping_list(sync)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete a To-do item."""
        sync = IcaShoppingListSync(
            offlineId=self._project_id,
            deletedRows=uids,
        )
        await self.coordinator.sync_shopping_list(sync)

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


class IcaBaseItemListEntity(CoordinatorEntity[IcaCoordinator], TodoListEntity):
    """A list of Favorite Items in the ICA account."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        # | TodoListEntityFeature.UPDATE_TODO_ITEM
        # | TodoListEntityFeature.DELETE_TODO_ITEM
        # todo: Implement MOVE_TODO_ITEM? (ordering within the list)
    )

    def __init__(self, coordinator: IcaCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize IcaBaseItemListEntity."""
        super().__init__(coordinator=coordinator)
        # sourcery skip: remove-redundant-condition, swap-if-expression
        self.coordinator = coordinator if not self.coordinator else coordinator
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}-baseitems"
        self._attr_name = f"{config_entry.title} Favorite Items"
        self._attr_icon = "mdi:cart"
        self._attr_todo_items: list[TodoItem] | None = None

    @property
    def name(self):
        return self._attr_name

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        items = []
        if baseitems := self.coordinator._ica_baseitems.current_value():
            for baseitem in baseitems:
                items.append(
                    TodoItem(
                        summary=baseitem["text"],
                        uid=baseitem["id"],
                        status=TodoItemStatus.NEEDS_ACTION,
                        description=baseitem.get("articleEan"),
                    )
                )
        self._attr_todo_items = items
        super()._handle_coordinator_update()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a To-do item."""
        await self.coordinator.async_lookup_and_add_baseitem(item.summary)

    # async def async_update_todo_item(self, item: TodoItem) -> None:
    #     """Update a To-do item."""
    #     sync = IcaShoppingListSync(
    #         offlineId=self._project_id,
    #         changedRows=[
    #             IcaShoppingListEntry(
    #                 offlineId=item.uid,
    #                 isStrikedOver=item.status == TodoItemStatus.COMPLETED,
    #                 productName=item.summary,
    #             )
    #         ],
    #     )

    #     sync["latestChange"] = (
    #         f"{datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()}Z",
    #     )
    #     await self.coordinator.sync_shopping_list(sync)

    # async def async_delete_todo_items(self, uids: list[str]) -> None:
    #     """Delete a To-do item."""
    #     sync = IcaShoppingListSync(
    #         offlineId=self._project_id,
    #         deletedRows=uids,
    #     )
    #     await self.coordinator.sync_shopping_list(sync)

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
