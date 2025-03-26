"""DataUpdateCoordinator for the Todoist component."""

from datetime import timedelta, datetime, timezone
import re
import logging
import uuid
from functools import partial

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .icaapi_async import IcaAPIAsync
from .icatypes import (
    IcaAccountCurrentBonus,
    IcaArticle,
    IcaBaseItem,
    IcaOfferDetails,
    IcaShoppingListSync,
    IcaStore,
    IcaProductCategory,
    IcaRecipe,
    IcaShoppingListEntry,
    IcaShoppingList,
    IcaStoreOffer,
)
from .background_worker import BackgroundWorker
from .caching import CacheEntry
from .const import (
    DOMAIN,
    CONF_ICA_ID,
    CONF_SHOPPING_LISTS,
    CACHING_SECONDS_SHORT_TERM,
    ConflictMode,
    IcaEvents,
    DEFAULT_ARTICLE_GROUP_ID,
)
from .utils import get_diffs, index_of, try_parse_int

_LOGGER = logging.getLogger(__name__)


class IcaCoordinator(DataUpdateCoordinator[list[IcaShoppingListEntry]]):
    """Coordinator for updating task data from ICA."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        logger: logging.Logger,
        update_interval: timedelta,
        api: IcaAPIAsync,
        background_worker: BackgroundWorker,
        nRecipes: int = 0,
    ) -> None:
        """Initialize the ICA coordinator."""
        super().__init__(hass, logger, name="ICA", update_interval=update_interval)
        self.SCAN_INTERVAL = update_interval
        self._config_entry = config_entry
        self.api: IcaAPIAsync = api
        self._hass = hass
        self._nRecipes: int = nRecipes
        self._stores: list[IcaStore] | None = None
        self._productCategories: list[IcaProductCategory] | None = None
        self._icaBaseItems: list | None = None
        self._icaRecipes: list[IcaRecipe] | None = None
        self._worker: BackgroundWorker = background_worker

        config_entry_key = self._config_entry.data[CONF_ICA_ID]

        self._ica_articles = CacheEntry[list[IcaArticle]](
            hass, "articles", partial(self.api.get_articles)
        )
        self._ica_baseitems = CacheEntry[list[IcaBaseItem]](
            hass,
            f"{config_entry_key}.baseitems",
            partial(self.api.get_baseitems),
            expiry_seconds=CACHING_SECONDS_SHORT_TERM,
        )
        self._ica_current_bonus = CacheEntry[IcaAccountCurrentBonus](
            hass, f"{config_entry_key}.current_bonus", partial(self._get_current_bonus)
        )
        self._ica_favorite_stores = CacheEntry[list[IcaStore]](
            hass,
            f"{config_entry_key}.favorite_stores",
            partial(self.api.get_favorite_stores),
        )
        self._ica_shopping_lists = CacheEntry[list[IcaShoppingList]](
            hass,
            f"{config_entry_key}.shopping_lists",
            partial(self._async_update_tracked_shopping_lists),
            expiry_seconds=CACHING_SECONDS_SHORT_TERM,
        )
        self._ica_offers = CacheEntry[dict[str, IcaOfferDetails]](
            hass,
            f"{config_entry_key}.offers",
            partial(self._update_offer_details),
            # FOR-DEBUGGING: expiry_seconds=CACHING_SECONDS_SHORT_TERM,
        )

    async def _get_tracked_shopping_lists(self) -> list[IcaShoppingList]:
        api_data = await self.api.get_shopping_lists()
        if "shoppingLists" in api_data:
            y = api_data["shoppingLists"]
            return [
                await self.api.get_shopping_list(z["offlineId"])
                for z in y
                if z["offlineId"]
                in self._config_entry.data.get(CONF_SHOPPING_LISTS, [])
            ]
        return None

    def get_shopping_list(self, list_id) -> IcaShoppingList:
        selected_lists = self._ica_shopping_lists.current_value() or []
        for x in filter(lambda x: x["offlineId"] == list_id, selected_lists):
            return x
        return None

    async def async_get_shopping_list(
        self, list_id, invalidate_cache: bool = False
    ) -> IcaShoppingList:
        selected_lists = await self.async_get_shopping_lists(invalidate_cache) or []
        for x in filter(lambda x: x["offlineId"] == list_id, selected_lists):
            return x
        return None

    async def async_get_shopping_lists(
        self, invalidate_cache: bool = False
    ) -> list[IcaShoppingList]:
        selected_lists = (
            await self._ica_shopping_lists.get_value(invalidate_cache) or []
        )
        if invalidate_cache:
            # Updated Shopping list cache outside of regular `_async_update_data-loop`, inform listeners...
            self.async_update_listeners()
        return selected_lists

    def get_article_group(self, product_name) -> int:
        articles = self._ica_articles.current_value() or []
        if not articles:
            return DEFAULT_ARTICLE_GROUP_ID  # Unspecified

        product_name = product_name.casefold()
        for x in filter(
            lambda x: x.get("name", "").casefold() == product_name, articles
        ):
            return x.get("parentId") or DEFAULT_ARTICLE_GROUP_ID
        return DEFAULT_ARTICLE_GROUP_ID  # Unspecified

        # articleGroups = {
        #     "välling": 9,
        #     "kaffe": 9,
        #     "maskindiskmedel": 11,
        #     "hushållspapper": 11,
        #     "toapapper": 11,
        #     "blöjor": 11,
        # }
        # return articleGroups.get(str.lower(productName), DEFAULT_ARTICLE_GROUP_ID)

    def parse_summary(self, summary):
        r = re.search(
            # r"^(?P<min_quantity>\d-)?(?P<quantity>[0-9,.]*)? ?(?P<unit>st|förp|kg|hg|g|l|dl|cl|ml|msk|tsk|krm)? ?(?P<name>.+)$",       v2
            r"^(?P<a>((?P<min_quantity>\d-)?(?P<quantity>[0-9,.]*)? )|(?P<b>))(?P<unit>st|förp|kg|hg|g|l|dl|cl|ml|msk|tsk|krm)? ?(?P<name>.+)$",
            summary,
        )
        quantity = r["quantity"]
        unit = r["unit"]
        productName = r["name"] or summary
        articleGroupId = self.get_article_group(productName)

        ti = {"summary": summary, "productName": productName}
        if unit:
            ti["unit"] = unit
        if quantity:
            ti["quantity"] = quantity
        if unit:
            ti["unit"] = unit
        if articleGroupId:
            ti["articleGroupId"] = articleGroupId

        if ti.get("quantity"):
            if ti.get("unit"):
                ti["summary"] = f"{ti['quantity']} {ti['unit']} {productName}"
            else:
                ti["summary"] = f"{ti['quantity']} {productName}"

        _LOGGER.info("Parsed info from '%s' to %s", summary, ti)
        return ti

    def get_offer_info(self, offer_id) -> IcaOfferDetails | None:
        offers = self._ica_offers.current_value() or {}
        return offers.get(offer_id, None)

    async def _update_offer_details(
        self, store_ids: list[str] = None
    ) -> dict[str, IcaOfferDetails]:
        now = datetime.now()
        current = (
            self._ica_offers.current_value() or {}
        )  # Get current value without refreshing. Possible infinite loop
        target = current.copy()
        pre_count = len(current)

        if not store_ids:
            # No passed store_ids then use the favorite stores
            stores = await self.async_get_favorite_stores()
            store_ids = [s["id"] for s in stores]

        offers_per_store = await self.api.get_offers(store_ids)
        _LOGGER.debug("Fetched offers for stores: %s", store_ids)

        if not offers_per_store:
            _LOGGER.warning("Failed to get offers from stores!")
            return current

        # Remove obsolete offers... (+30 days from expiration)
        for offer_id in current:
            offer = current[offer_id]
            offer_due = (
                datetime.fromisoformat(offer["validTo"]) + timedelta(days=30)
                if offer.get("validTo")
                else datetime.max
            )
            if offer_due < now:
                _LOGGER.info("Removing obsolete offer: %s", offer)
                del target[offer_id]

        # Look up the "active" offers that was retrieved
        store_ids = list(offers_per_store.keys())
        offer_ids = []
        store_offers: dict[str, IcaStoreOffer] = {}
        for store_id in offers_per_store:
            store = offers_per_store[store_id]
            oids = [
                o["id"]
                for o in store["offers"]
                # if o and o.get("isUsed", None) is not True
            ]
            offer_ids = sorted(list(set(offer_ids)) + list(set(oids)))
            for o in store["offers"]:
                c = store_offers.get(o["id"]) or IcaStoreOffer()
                c.update(o)
                store_offers[o["id"]] = c

        if not offer_ids:
            _LOGGER.warning("No offers to lookup, then avoid querying API")
            return []

        full_offers = await self.api.search_offers(store_ids, offer_ids)
        if not full_offers:
            _LOGGER.warning("No existing offers found. Is this true??")
            return []

        new_offers: list[IcaOfferDetails] = []
        limited: list[IcaOfferDetails] = []
        for f in full_offers:
            current_offer = target.get(f["id"]) or IcaOfferDetails()
            store_offer = store_offers.get(f["id"]) or IcaStoreOffer()

            offer = current_offer.copy()
            offer.update(store_offer)
            offer.update(f)
            target[offer["id"]] = offer
            if not current_offer:
                new_offers.append(offer)
            if len(limited) < 5:
                limited.append(offer)

        # Prepare for publish of change event
        await CacheEntry(
            self._hass, "offers_changed--base-data", partial(lambda _: None)
        ).set_value(
            {
                "timestamp": str(datetime.now(timezone.utc)),
                "old": current,
                "new": target,
            }
        )

        diffs = get_diffs(current, target, include_values=False)
        _LOGGER.debug("OFFERS DIFFS: %s", diffs)
        if diffs:
            event_data = {
                "type": "offers_changed",
                "uid": self._config_entry.data[CONF_ICA_ID],
                "timestamp": str(datetime.now(timezone.utc)),
                "pre_count": pre_count,
                "post_count": len(target),
                # "new_offers": new_offers,
                "diffs": diffs,
            }
            await CacheEntry(
                self._hass, "offers_changed--diffs", partial(lambda _: None)
            ).set_value(event_data)
            await self._worker.fire_or_queue_event(f"{DOMAIN}_event", event_data)

        # Notify new offers
        if new_offers:
            event_data = {
                "type": "new_offers",
                "uid": self._config_entry.data[CONF_ICA_ID],
                "timestamp": str(datetime.now(timezone.utc)),
                "pre_count": pre_count,
                "post_count": len(target),
                "new_offers": new_offers,
            }
            # todo: notify: Auto add automation if new ean's have been added to an offer?
            # todo: ...and remove if no longer exists?
            await self._worker.fire_or_queue_event(IcaEvents.NEW_OFFERS, event_data)
            # print to file for debugging purposes
            await CacheEntry(
                self._hass, "offers_changed--new-offers", partial(lambda _: None)
            ).set_value(event_data)

        _LOGGER.warning(
            "Updated offer details! pre_count: %s, post_count: %s",
            pre_count,
            len(target),
        )
        return target

    async def refresh_data(self, invalidate_cache: bool | None = None) -> None:
        """Fetch data from the ICA API (if necessary)."""
        self._icaRecipes = None
        try:
            # Get common ICA data first
            await self._ica_articles.get_value(invalidate_cache)
            await self._ica_baseitems.get_value(invalidate_cache)

            # Get user specific data
            await self._ica_current_bonus.get_value(invalidate_cache)
            await self._ica_shopping_lists.get_value(invalidate_cache)

            # Get store offers
            await self._ica_favorite_stores.get_value(invalidate_cache)
            await self._ica_offers.get_value(invalidate_cache)
        except Exception as err:
            _LOGGER.fatal("Exception when getting data. Err: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def _async_update_data(self) -> None:
        """Fetch data from the ICA API."""
        await self.refresh_data()

    async def _async_update_tracked_shopping_lists(self) -> list[IcaShoppingList]:
        """Return ICA shopping lists fetched at most once."""
        current = self._ica_shopping_lists.current_value() or []
        updated = await self._get_tracked_shopping_lists()
        if not updated:
            raise ValueError("Failed to get a valid shopping list from the API")

        for shopping_list in updated or []:
            old_rows = next(
                (lst["rows"] for lst in current if lst["id"] == shopping_list["id"]),
                [],
            )
            new_rows = shopping_list["rows"]
            if diffs := get_diffs(old_rows, new_rows):
                await self._worker.fire_or_queue_event(
                    f"{DOMAIN}_event",
                    {
                        "type": "shopping_list_updated",
                        "uid": self._config_entry.data[CONF_ICA_ID],
                        "shopping_list_id": shopping_list["id"],
                        "shopping_list_name": shopping_list["title"],
                        "diffs": diffs,
                    },
                )
        return updated

    async def sync_shopping_list(
        self,
        sync: IcaShoppingListSync,
        conflict_mode: ConflictMode = ConflictMode.APPEND,
        instant_submit: bool = True,
    ) -> IcaShoppingList:
        """Pushes the specified changes to ICA. Might apply some conflict logic on the before. In the future changes could be batched together before being sumbmitted."""
        # todo: Apply conflict_mode logic
        # todo: Batch changes before submitting after X seconds
        # todo: Apply ordering

        # Push sync to API
        updated_list = await self.api.sync_shopping_list(sync)

        # todo: no need to await?, just queue it in background...
        await self._dynamically_update_shopping_list_cache(updated_list)
        return updated_list

    async def _dynamically_update_shopping_list_cache(
        self, updated_list: IcaShoppingList
    ) -> IcaShoppingList:
        state = self._ica_shopping_lists.current_value().copy()
        index = index_of(state, "offlineId", updated_list["offlineId"])
        if index >= 0:
            state[index] = updated_list
            await self._ica_shopping_lists.set_value(state)
            _LOGGER.info("Dynamically updated Shopping list cache")
            self.async_update_listeners()
        else:
            # Could not dynamically update state, invoke API request to get the new state...
            updated_list = await self.async_get_shopping_list(
                updated_list["offlineId"], invalidate_cache=True
            )
            _LOGGER.warning(
                "Could not dynamically update Shopping List cache. Updated via API instead..."
            )
        return updated_list

    def get_baseitems(self):
        """Return ICA favorite items (baseitems) fetched at most once."""
        return self._ica_baseitems.current_value()

    async def async_get_baseitems(self, invalidate_cache: bool = False):
        """Return ICA favorite items (baseitems) fetched at most once."""
        return await self._ica_baseitems.get_value(invalidate_cache)

    async def lookup_baseitem_per_identifier(
        self, identifier: str
    ) -> IcaBaseItem | None:
        """Return a specific ICA recipe."""
        product = await self.api.lookup_barcode(identifier)
        if not product:
            return None
        return IcaBaseItem(
            id=str(uuid.uuid4()),
            text=product["name"],
            articleId=product["articleId"],
            articleGroupId=product.get("articleGroupId", DEFAULT_ARTICLE_GROUP_ID),
            articleGroupIdExtended=product.get(
                "expandedArticleGroupId", DEFAULT_ARTICLE_GROUP_ID
            ),
            articleEan=product["gtin"],
        )

    async def async_lookup_and_add_baseitem(self, identifier: str) -> list[IcaBaseItem]:
        """Return a specific ICA recipe."""
        (r, i) = try_parse_int(identifier)
        if r and i:
            # Successful parse
            item = await self.lookup_baseitem_per_identifier(identifier)
            if not item:
                raise ValueError(f"Product with ean '{identifier}' was not found")
        else:
            # Not a valid Barcode was passed. Treat as a free-text instead...
            item = IcaBaseItem(
                id=str(uuid.uuid4()),
                text=identifier,
            )

        sync = self._ica_baseitems.current_value().copy()
        current_sort_order = int(sync[-1]["sortOrder"] if len(sync) > 0 else -1)
        item["sortOrder"] = current_sort_order + 1
        sync.append(item)
        _LOGGER.info("ITEM: %s", item)
        return await self.sync_baseitems(sync)

    async def sync_baseitems(self, items: list[IcaBaseItem]) -> list[IcaBaseItem]:
        """Updates the account baseitems."""
        response = await self.api.sync_baseitems(items)
        if response:
            await self._ica_baseitems.set_value(response)
            _LOGGER.info("Dynamically updated BaseItems cache")
            self.async_update_listeners()
        return response

    async def async_get_articles(self):
        """Return pre-canned articles to add to shopping list (with article group)."""
        return await self._ica_articles.get_value()

    async def async_get_product_categories(self) -> list[IcaProductCategory]:
        """Return ICA product categories fetched at most once."""
        if self._productCategories is None:
            self._productCategories = await self.api.get_product_categories()
        return self._productCategories

    async def async_get_favorite_stores(self) -> list[IcaStore]:
        """Return ICA favorite stores."""
        return await self._ica_favorite_stores.get_value()

    async def _get_current_bonus(self):
        """Returns ICA bonus information"""
        current_bonus = await self.api.get_current_bonus()

        # Fire event
        await self._worker.fire_or_queue_event(
            f"{DOMAIN}_event",
            {
                "type": "current_bonus_loaded",
                "uid": self._config_entry.data[CONF_ICA_ID],
                "data": current_bonus,
            },
        )
        return current_bonus

    async def async_get_recipe(self, recipe_id: int) -> IcaRecipe:
        """Return a specific ICA recipe."""
        return await self.api.get_recipe(recipe_id)

    # async def async_get_recipes(self, nRecipes: int) -> list[IcaRecipe]:
    #     """Return ICA recipes."""
    #     if self._icaRecipes is None and self._nRecipes:
    #         self._icaRecipes = await self.api.get_random_recipes(nRecipes)
    #     return self._icaRecipes
