"""DataUpdateCoordinator for the Todoist component."""

from datetime import timedelta
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
    IcaArticleOffer,
    IcaBaseItem,
    IcaOfferDetails,
    IcaShoppingListSync,
    IcaStore,
    IcaProductCategory,
    IcaRecipe,
    IcaShoppingListEntry,
    IcaShoppingList,
    IcaStoreOffer,
    OffersAndDiscountsForStore,
)
from .caching import CacheEntry
from .const import (
    DOMAIN,
    CONF_ICA_ID,
    CONF_SHOPPING_LISTS,
    CACHING_SECONDS_SHORT_TERM,
    ConflictMode,
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

        config_entry_key = self._config_entry.data[CONF_ICA_ID]

        self._ica_articles = CacheEntry[list[IcaArticle]](
            hass, "articles", partial(self.api.get_articles)
        )
        self._ica_baseitems = CacheEntry[list[IcaBaseItem]](
            hass, f"{config_entry_key}.baseitems", partial(self.api.get_baseitems)
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
        self._ica_favorite_stores_offers = CacheEntry[
            dict[str, OffersAndDiscountsForStore]
        ](
            hass,
            f"{config_entry_key}.favorite_stores_offers",
            partial(self._get_offers),
        )
        self._ica_favorite_stores_offers_full = CacheEntry[list[IcaArticleOffer]](
            hass,
            f"{config_entry_key}.favorite_stores_offers_full",
            partial(self._search_offers),
        )
        self._ica_offers = CacheEntry[dict[str, IcaOfferDetails]](
            hass,
            f"{config_entry_key}.offers",
            partial(self._update_offer_details),
            expiry_seconds=CACHING_SECONDS_SHORT_TERM,
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
            return 12  # Unspecified

        product_name = product_name.casefold()
        for x in filter(
            lambda x: x.get("name", "").casefold() == product_name, articles
        ):
            return x.get("parentId") or 12
        return 12  # Unspecified

        # articleGroups = {
        #     "välling": 9,
        #     "kaffe": 9,
        #     "maskindiskmedel": 11,
        #     "hushållspapper": 11,
        #     "toapapper": 11,
        #     "blöjor": 11,
        # }
        # return articleGroups.get(str.lower(productName), 12)

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

    def get_offer_info(self, offerId) -> IcaStoreOffer:
        offers_per_store = self._ica_favorite_stores_offers.current_value()
        if not offers_per_store:
            return None
        for store_id in offers_per_store:
            store = offers_per_store[store_id]
            if matches := [o for o in store["offers"] if o["id"] == offerId]:
                return matches[0]
        return None

    def get_offer_info_full(self, offerId) -> IcaArticleOffer:
        if offers := self._ica_favorite_stores_offers_full.current_value():
            return (
                matches[0]
                if (matches := [o for o in offers if o["id"] == offerId])
                else None
            )
        else:
            return None

    async def _update_offer_details(
        self, invalidate_cache: bool = True, store_ids: list[str] = None
    ) -> dict[str, IcaOfferDetails]:
        current = (
            self._ica_offers.current_value() or {}
        )  # Get current value without refreshing. Possible infinite loop
        pre_count = len(current)
        _LOGGER.warning(
            "Updating offer details! :) current length: %s, invalidate:%s",
            len(current),
            invalidate_cache,
        )

        if store_ids is None:
            offers_per_store = await self._ica_favorite_stores_offers.get_value(
                invalidate_cache
            )
            if not offers_per_store:
                _LOGGER.warning("Failed to get offers from favorite stores!")
                return current
        else:
            offers_per_store = await self.api.get_offers(store_ids)
            _LOGGER.debug("Fetched offers for stores: %s", store_ids)

        # todo: Remove obsolete offers... (+30 days from expiration?)

        # Look up the "active" offers that was retrieved
        store_ids = list(offers_per_store.keys())
        offer_ids = []
        store_offers: dict[str, IcaStoreOffer] = {}
        for store_id in offers_per_store:
            if store_id in ["12226", "12045"]:
                # Limit to these 2 for now...
                # todo: remove / or set as config
                _LOGGER.warning("Ignoring offers from store: %s", store_id)
                continue
            store = offers_per_store[store_id]
            oids = [
                o["id"]
                for o in store["offers"]
                # if o and o.get("isUsed", None) is not True
            ]
            offer_ids = sorted(list(set(offer_ids)) + list(set(oids)))
            for o in store["offers"]:
                store_offers[o["id"]] = o

        if not offer_ids:
            _LOGGER.warning("No offers to lookup, then avoid querying API")
            return []

        full_offers = await self.api.search_offers(store_ids, offer_ids)
        if not full_offers:
            _LOGGER.warning("No existing offers found. Is this true??")
            return []

        target = current.copy()
        new_offers: list[IcaOfferDetails] = []
        for f in full_offers:
            current_offer = target.get(f["id"]) or IcaOfferDetails()
            store_offer = store_offers.get(f["id"]) or IcaStoreOffer()

            offer = current_offer.copy()
            offer.update(store_offer)
            offer.update(f)
            target[offer["id"]] = offer
            if not current_offer:
                new_offers.append(offer)

        if new_offers:
            # Got new offers, prepare for publish of change event
            # old = {k: v for k, v in target.items()}
            # new = {o["id"]: o for o in new_offers}
            old = current
            new = target

            ce2 = CacheEntry(
                self._hass, "offers-event-data-diff-base2", partial(lambda i: None)
            )
            await ce2.set_value({"old": old, "new": new})

            diffs = get_diffs(old, new)
            _LOGGER.info("OFFER DIFFS: %s", diffs)
            event_data = {
                "type": "offers_changed",
                "uid": self._config_entry.data[CONF_ICA_ID],
                "pre_count": pre_count,
                "post_count": len(target),
                "new_offers": new_offers,
                "diffs": diffs,
            }

            ce = CacheEntry(self._hass, "offers-event-data", partial(lambda i: None))
            await ce.set_value(event_data)

            self._hass.bus.async_fire(
                f"{DOMAIN}_event",
                event_data,
            )
        return target

    async def _search_offers(self):
        offers_per_store = self._ica_favorite_stores_offers.current_value()
        if not offers_per_store:
            return None

        store_ids = list(offers_per_store.keys())
        offer_ids = []

        for store_id in offers_per_store:
            if store_id in ["12226", "12045"]:
                # Limit to these 2 for now...
                # todo: remove / or set as config
                _LOGGER.warning("Ignoring offers from store: %s", store_id)
                continue
            store = offers_per_store[store_id]
            oids = [
                o["id"]
                for o in store["offers"]
                # if o and o.get("isUsed", None) is not True
            ]
            offer_ids = sorted(list(set(offer_ids)) + list(set(oids)))

        if not offer_ids:
            _LOGGER.warning("No offers to lookup, then avoid querying API")
            return []

        full_offers = await self.api.search_offers(store_ids, offer_ids)
        if not full_offers:
            _LOGGER.warning("No existing offers found. Is this true??")
            return []

        baseitems = self._ica_baseitems.current_value()
        bi_eans = [
            i["articleEan"] for i in baseitems if i and i.get("articleEan", None)
        ]
        _LOGGER.warning("Favorite eans: %s", bi_eans)

        for offer in full_offers:
            if eans := offer.get("eans", None):
                for ean in eans:
                    ean_id = ean["id"]
                    if ean_id in bi_eans or f"0{ean_id}" in bi_eans:
                        _LOGGER.fatal(
                            "Offer on Favorite! EAN=%s, Name=%s, OfferId=%s",
                            ean_id,
                            offer.get("name", None),
                            offer.get("id", None),
                        )

                        self._hass.bus.async_fire(
                            f"{DOMAIN}_event",
                            {
                                "type": "baseitem_offer_found",
                                "uid": self._config_entry.data[CONF_ICA_ID],
                                "data": {
                                    "bi_ean": ean_id,
                                    "offer": offer,
                                },
                            },
                        )
                        # todo: Add service that takes offerId and adds to a target todo-list. UPDATE: Done!
                        # todo: Do this lookup also outside of this CacheEntry

        return full_offers

    async def _async_update_data(
        self, refresh: bool | None = None
    ) -> None:  # list[IcaShoppingListEntry]:
        """Fetch data from the ICA API."""
        self._icaRecipes = None
        try:
            # Get common ICA data first
            await self._ica_articles.get_value(invalidate_cache=refresh)
            await self._ica_baseitems.get_value(invalidate_cache=refresh)

            # Get user specific data
            await self._ica_current_bonus.get_value(invalidate_cache=refresh)
            await self._ica_shopping_lists.get_value(invalidate_cache=refresh)

            # Get store offers
            await self._ica_favorite_stores.get_value(invalidate_cache=refresh)

            await (
                self._ica_offers.get_value()
            )  # to replace other _ica_favorite_stores_offers_full

            await self._ica_favorite_stores_offers.get_value(invalidate_cache=refresh)
            await self._ica_favorite_stores_offers_full.get_value(
                invalidate_cache=refresh
            )

        except Exception as err:
            _LOGGER.fatal("Exception when getting data. Err: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

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
            if not old_rows:
                continue
            old_rows = old_rows[0]
            new_rows = shopping_list["rows"]

            diffs = get_diffs(old_rows, new_rows)
            self._hass.bus.async_fire(
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

    async def async_get_baseitems(self):
        """Return ICA favorite items (baseitems) fetched at most once."""
        return await self._ica_baseitems.get_value()

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
            articleGroupId=product["articleGroupId"],
            articleGroupIdExtended=product["expandedArticleGroupId"],
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
            # Not a valid Barcode was passed. Treat as a free text instead...
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

    async def _get_offers(self):
        """Return ICA offers at favorite stores."""
        # Get dependency
        stores = await self.async_get_favorite_stores()

        return await self.api.get_offers([s["id"] for s in stores])

    async def _get_current_bonus(self):
        """Returns ICA bonus information"""
        current_bonus = await self.api.get_current_bonus()

        # Fire event
        self._hass.bus.async_fire(
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
