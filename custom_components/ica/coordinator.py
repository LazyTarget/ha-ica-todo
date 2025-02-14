"""DataUpdateCoordinator for the Todoist component."""
from datetime import timedelta
import re
import logging

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
from .const import DOMAIN, CONF_ICA_ID, CONF_SHOPPING_LISTS

import logging
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
        self._icaOffers: list[IcaOffer] | None = None
        self._icaCurrentBonus: list | None = None
        self._icaShoppingLists: list[IcaShoppingList] | None = None
        self._icaRecipes: list[IcaRecipe] | None = None

    def get_shopping_list(self, list_id) -> IcaShoppingList:
        # await self.async_get_shopping_lists()
        for x in filter(lambda x: x["offlineId"] == list_id, self._icaShoppingLists):
            return x
        return None

    def get_article_group(self, productName) -> int:
        # await self.async_get_product_categories()
        # for x in filter(lambda x: x["Id"] == list_id, self._icaShoppingLists):
        #    return x
        articleGroups = {
            "välling": 9,
            "kaffe": 9,
            "maskindiskmedel": 11,
            "hushållspapper": 11,
            "toapapper": 11,
            "blöjor": 11,
        }
        return articleGroups.get(str.lower(productName), 12)

    def parse_summary(self, summary):
        r = re.search(r"^(?P<min_quantity>\d-)?(?P<quantity>[0-9,.]*)? ?(?P<unit>st|förp|kg|hg|g|l|dl|cl|ml|msk|tsk|krm)? ?(?P<name>.+)$", summary)
        quantity = r['quantity']
        unit = r['unit']
        productName = r['name'] or summary
        articleGroupId = self.get_article_group(productName)

        ti = {
            "summary": summary,
            "productName": productName
        }
        if unit:
            ti["unit"] = unit
        if quantity:
            ti["quantity"] = quantity
        if unit:
            ti["unit"] = unit
        if articleGroupId:
            ti["articleGroupId"] = articleGroupId

        if ti.get('quantity', None) and ti.get('unit', None):
            ti['summary'] = f"{ti['quantity']} {ti['unit']} {productName}"
        elif ti.get('quantity', None):
            ti['summary'] = f"{ti['quantity']} {productName}"

        _LOGGER.info("Parsed info from '%s' to %s", summary, ti)
        return ti

    def get_offer_info(self, offerId):
        if not self._icaOffers:
            _LOGGER.warning("No offers where loaded!")
            return None

        all_store_offers = self._icaOffers
        for store_id in all_store_offers:
            store = all_store_offers[store_id]
            matches = [o for o in store["offers"] if o["id"] == offerId]
            if matches:
                _LOGGER.info("Matched offer: %s", matches)
                return matches[0]
        return None

    async def _async_update_data(self) -> None:  # list[IcaShoppingListEntry]:
        """Fetch data from the ICA API."""
        self._icaShoppingLists = None
        self._icaRecipes = None
        self._icaOffers = None
        self._icaCurrentBonus = None
        self._icaBaseItems = None
        try:
            self._icaShoppingLists = await self.async_get_shopping_lists()
            self._icaOffers = await self.async_get_offers()
            self._icaCurrentBonus = await self.async_get_current_bonus()
            self._icaBaseItems = await self.async_get_baseitems()
            #if self._nRecipes:
            #    self._icaRecipes = await self.async_get_recipes(self._nRecipes)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_get_shopping_lists(self) -> list[IcaShoppingList]:
        """Return ICA shopping lists fetched at most once."""
        if self._icaShoppingLists is None:
            x = await self.api.get_shopping_lists()
            if "shoppingLists" in x:
                y = x["shoppingLists"]
                self._icaShoppingLists = [
                    await self.api.get_shopping_list(z["offlineId"]) 
                    for z in y if z["offlineId"] in self._config_entry.data.get(CONF_SHOPPING_LISTS, [])
                ]

        self._hass.bus.async_fire(f"{DOMAIN}_event", {
            "type": "shopping_lists_loaded",
            "uid": self._config_entry.data[CONF_ICA_ID],
            "data": self._icaShoppingLists
        })
        return self._icaShoppingLists

    async def async_get_baseitems(self):
        """Return ICA favorite items (baseitems) fetched at most once."""
        if self._icaBaseItems is None:
            self._icaBaseItems = await self.api.get_baseitems()
        return self._icaBaseItems

    async def async_get_product_categories(self) -> list[IcaProductCategory]:
        """Return ICA product categories fetched at most once."""
        if self._productCategories is None:
            self._productCategories = await self.api.get_product_categories()
        return self._productCategories

    async def async_get_stores(self) -> list[IcaStore]:
        """Return ICA favorite stores fetched at most once."""
        if self._stores is None:
            self._stores = await self.api.get_favorite_stores()
        return self._stores

    async def async_get_offers(self):
        """Return ICA offers at favorite stores fetched at most once."""
        stores = await self.async_get_stores()

        # todo: Cache offers, but invalidate cache once in a while...
        if self._icaOffers is None:
            self._icaOffers = await self.api.get_offers([s["id"] for s in stores])
            self._hass.bus.async_fire(f"{DOMAIN}_event", {
                "type": "offers_loaded",
                "uid": self._config_entry.data[CONF_ICA_ID],
                "data": self._icaOffers
            })
        return self._icaOffers

    async def async_get_current_bonus(self):
        # todo: Cache offers, but invalidate cache once in a while...
        if self._icaCurrentBonus is None:
            self._icaCurrentBonus = await self.api.get_current_bonus()
            self._hass.bus.async_fire(f"{DOMAIN}_event", {
                "type": "current_bonus_loaded",
                "uid": self._config_entry.data[CONF_ICA_ID],
                "data": self._icaCurrentBonus
            })
        return self._icaCurrentBonus

    async def async_get_recipe(self, recipe_id: int) -> IcaRecipe:
        """Return a specific ICA recipe."""
        return await self.api.get_recipe(recipe_id)

    async def async_get_recipes(self, nRecipes: int) -> list[IcaRecipe]:
        """Return ICA recipes."""
        if self._icaRecipes is None and self._nRecipes:
            self._icaRecipes = await self.api.get_random_recipes(nRecipes)
        return self._icaRecipes
