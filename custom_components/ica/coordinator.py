"""DataUpdateCoordinator for the Todoist component."""

from datetime import timedelta
import re
import logging
import json
import uuid
from functools import partial
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .icaapi_async import IcaAPIAsync
from .icatypes import (
    IcaStore,
    IcaProductCategory,
    IcaRecipe,
    IcaShoppingListEntry,
    IcaOffer,
    IcaShoppingList,
)
from .caching import CacheEntry
from .const import DOMAIN, CONF_ICA_ID, CONF_SHOPPING_LISTS
from .utils import get_diffs

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
        self.api = api
        self._hass = hass
        self._nRecipes: int = nRecipes
        self._stores: list[IcaStore] | None = None
        self._productCategories: list[IcaProductCategory] | None = None
        self._icaBaseItems: list | None = None
        self._icaRecipes: list[IcaRecipe] | None = None

        config_entry_key = self._config_entry.data[CONF_ICA_ID]

        self._ica_articles = CacheEntry(
            hass, "articles", partial(self.api.get_articles)
        )
        self._ica_baseitems = CacheEntry(
            hass, f"{config_entry_key}.baseitems", partial(self.api.get_baseitems)
        )
        self._ica_current_bonus = CacheEntry(
            hass, f"{config_entry_key}.current_bonus", partial(self._get_current_bonus)
        )
        self._ica_favorite_stores = CacheEntry(
            hass,
            f"{config_entry_key}.favorite_stores",
            partial(self.api.get_favorite_stores),
        )
        self._ica_shopping_lists = CacheEntry(
            hass,
            f"{config_entry_key}.shopping_lists",
            partial(self.async_get_shopping_lists),
        )
        self._ica_favorite_stores_offers = CacheEntry(
            hass,
            f"{config_entry_key}.favorite_stores_offers",
            partial(self._get_offers),
        )
        self._ica_favorite_stores_offers_full = CacheEntry(
            hass,
            f"{config_entry_key}.favorite_stores_offers_full",
            partial(self._search_offers),
        )

    async def _get_shopping_lists(self) -> list[IcaShoppingList]:
        api_data = await self.api.get_shopping_lists()
        if "shoppingLists" in api_data:
            y = api_data["shoppingLists"]
            selected_lists = [
                await self.api.get_shopping_list(z["offlineId"])
                for z in y
                if z["offlineId"]
                in self._config_entry.data.get(CONF_SHOPPING_LISTS, [])
            ]
            return selected_lists
        return None

    def get_shopping_list(self, list_id) -> IcaShoppingList:
        selected_lists = self._ica_shopping_lists.current_value() or []
        for x in filter(lambda x: x["offlineId"] == list_id, selected_lists):
            return x
        return None

    async def async_get_shopping_list(
        self, list_id, invalidate_cache: bool = False
    ) -> IcaShoppingList:
        selected_lists = (
            await self._ica_shopping_lists.get_value(invalidate_cache) or []
        )
        for x in filter(lambda x: x["offlineId"] == list_id, selected_lists):
            return x
        return None

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

        if ti.get("quantity", None) and ti.get("unit", None):
            ti["summary"] = f"{ti['quantity']} {ti['unit']} {productName}"
        elif ti.get("quantity", None):
            ti["summary"] = f"{ti['quantity']} {productName}"

        _LOGGER.info("Parsed info from '%s' to %s", summary, ti)
        return ti

    def get_offer_info(self, offerId):
        offers_per_store = self._ica_favorite_stores_offers.current_value()
        if not offers_per_store:
            return None
        for store_id in offers_per_store:
            store = offers_per_store[store_id]
            matches = [o for o in store["offers"] if o["id"] == offerId]
            if matches:
                # _LOGGER.info("Matched offer: %s", matches)
                return matches[0]
        return None

    def get_offer_info_full(self, offerId):
        offers = self._ica_favorite_stores_offers_full.current_value()
        if not offers:
            return None
        matches = [o for o in offers if o["id"] == offerId]
        if matches:
            # _LOGGER.info("Matched offer full: %s", matches)
            return matches[0]
        return None

    async def _search_offers(self):
        offers_per_store = self._ica_favorite_stores_offers.current_value()
        if not offers_per_store:
            return None

        store_ids = list(offers_per_store.keys())
        offer_ids = []

        for store_id in offers_per_store:
            if store_id != 12226 and store_id != 12045:
                # Limit to these 2 for now...
                continue
            store = offers_per_store[store_id]
            oids = [
                o["id"]
                for o in store["offers"]
                # if o and o.get("isUsed", None) is not True
            ]
            offer_ids = sorted(list(set(offer_ids)) + list(set(oids)))
        # _LOGGER.warning("StoreIds: %s :: %s", type(store_ids), store_ids)
        # _LOGGER.warning("OfferIds: %s :: %s", type(offer_ids), offer_ids)

        full_offers = await self.api.search_offers(store_ids, offer_ids)

        # # Fire event(s)
        # self._hass.bus.async_fire(
        #     f"{DOMAIN}_event",
        #     {
        #         "type": "active_offers",
        #         "uid": self._config_entry.data[CONF_ICA_ID],
        #         "data": full_offers,
        #     },
        # )

        baseitems = self._ica_baseitems.current_value()
        bi_eans = [
            i["articleEan"] for i in baseitems if i and i.get("articleEan", None)
        ]
        _LOGGER.warning("Favorite eans: %s", bi_eans)

        for offer in full_offers:
            eans = offer.get("eans", None)
            if eans:
                for ean in eans:
                    id = ean["id"]
                    if id in bi_eans or f"0{id}" in bi_eans:
                        _LOGGER.fatal(
                            "Offer on Favorite! EAN=%s, Name=%s, OfferId=%s",
                            id,
                            offer.get("name", None),
                            offer.get("id", None),
                        )

                        self._hass.bus.async_fire(
                            f"{DOMAIN}_event",
                            {
                                "type": "baseitem_offer_found",
                                "uid": self._config_entry.data[CONF_ICA_ID],
                                "data": {
                                    "bi_ean": id,
                                    "offer": offer,
                                },
                            },
                        )
                        # todo: Add service that takes offerId and adds to a target todo-list

        return full_offers

    async def _async_update_data(
        self, refresh=False
    ) -> None:  # list[IcaShoppingListEntry]:
        """Fetch data from the ICA API."""
        self._icaRecipes = None
        try:
            # Get common ICA data first
            await self._ica_articles.get_value(invalidate_cache=refresh)
            await self._ica_baseitems.get_value(invalidate_cache=refresh)

            # Get user specific data
            await self._ica_current_bonus.get_value(invalidate_cache=refresh)
            await self._ica_shopping_lists.get_value(invalidate_cache=True)

            await self._ica_favorite_stores.get_value(invalidate_cache=refresh)
            await self._ica_favorite_stores_offers.get_value(invalidate_cache=refresh)
            await self._ica_favorite_stores_offers_full.get_value(
                invalidate_cache=refresh
            )
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_get_shopping_lists(self, refresh=False) -> list[IcaShoppingList]:
        """Return ICA shopping lists fetched at most once."""

        current = self._ica_shopping_lists.current_value()
        # updated = await self._ica_shopping_lists.get_value(invalidate_cache=refresh)
        updated = await self._get_shopping_lists()
        self._hass.bus.async_fire(
            f"{DOMAIN}_event",
            {
                "type": "shopping_lists_loaded",
                "uid": self._config_entry.data[CONF_ICA_ID],
                "data": updated,
            },
        )

        for shopping_list in (updated or []):
            old_rows = [
                l["rows"]
                for l in (current or [])
                if current and l["id"] == shopping_list["id"]
            ]
            if not old_rows or len(old_rows) < 1:
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

    async def async_get_baseitems(self):
        """Return ICA favorite items (baseitems) fetched at most once."""
        return await self._ica_baseitems.get_value()

    async def async_add_baseitem(self, identifier: str) -> IcaRecipe:
        """Return a specific ICA recipe."""

        product = await self.api.lookup_barcode(identifier)
        if not product:
            raise ValueError(f"Product ean '{identifier}' was not found")

        baseitems = self._ica_baseitems.current_value()

        current_sort_order = int(
            baseitems[-1]["sortOrder"] if len(baseitems) > 0 else -1
        )
        item = {
            "id": str(uuid.uuid4()),
            "text": product["name"],
            "articleId": product["articleId"],
            "articleGroupId": product["articleGroupId"],
            "articleGroupIdExtended": product["expandedArticleGroupId"],
            "articleEan": product["gtin"],
            "sortOrder": current_sort_order + 1,
        }
        baseitems.append(item)
        _LOGGER.info("ITEM: %s", item)
        response = await self.api.sync_baseitems(baseitems)

        # todo: Manually update cache with the 'response' variable
        await self._ica_baseitems.refresh()

        return response

    async def async_get_articles(self):
        """Return pre-canned articles to add to shopping list (with article group)."""
        return await self._ica_articles.get_value()

    async def async_get_product_categories(self) -> list[IcaProductCategory]:
        """Return ICA product categories fetched at most once."""
        if self._productCategories is None:
            self._productCategories = await self.api.get_product_categories()
        return self._productCategories

    async def async_get_stores(self) -> list[IcaStore]:
        """Return ICA favorite stores."""
        return await self._ica_favorite_stores.get_value()

    async def _get_offers(self):
        """Return ICA offers at favorite stores."""
        # Get dependency
        stores = await self.async_get_stores()

        # Get offers
        offers_per_store = await self.api.get_offers([s["id"] for s in stores])

        # Fire event(s)
        # self._hass.bus.async_fire(
        #     f"{DOMAIN}_event",
        #     {
        #         "type": "offers_loaded",
        #         "uid": self._config_entry.data[CONF_ICA_ID],
        #         "data": offers_per_store,
        #     },
        # )

        # self._lookup_baseitems_on_offer()

        return offers_per_store

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
