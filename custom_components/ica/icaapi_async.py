import asyncio

from .icaapi import IcaAPI
from .icatypes import (
    IcaShoppingList,
    IcaStore,
    IcaOffer,
    IcaProductCategory,
    IcaRecipe,
)


async def run_async(func):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func)


class IcaAPIAsync:
    """Class to retrieve and hold the data for a Shopping list from ICA"""

    def __init__(self, uid, pin, user_token=None):
        self._uid = uid
        self._pin = pin
        self._api = None
        self._user = user_token

    def get_authenticated_user(self):
        if not self._api:
            self._api = IcaAPI(self._uid, self._pin, self._user)
        return self._api.get_authenticated_user()

    async def get_shopping_lists(self) -> list[IcaShoppingList]:
        if not self._api:
            self._api = await run_async(
                lambda: IcaAPI(self._uid, self._pin, self._user)
            )
        return await run_async(lambda: self._api.get_shopping_lists())

    async def get_shopping_list(self, list_id: str) -> IcaShoppingList:
        if not self._api:
            self._api = await run_async(
                lambda: IcaAPI(self._uid, self._pin, self._user)
            )
        return await run_async(lambda: self._api.get_shopping_list(list_id))

    async def get_baseitems(self):
        if not self._api:
            self._api = await run_async(
                lambda: IcaAPI(self._uid, self._pin, self._user)
            )
        return await run_async(lambda: self._api.get_baseitems())

    async def get_store(self, store_id) -> IcaStore:
        if not self._api:
            self._api = await run_async(lambda: IcaAPI(self._uid, self._pin))
        return await run_async(lambda: self._api.get_store(store_id))

    async def get_favorite_stores(self) -> list[IcaStore]:
        if not self._api:
            self._api = await run_async(lambda: IcaAPI(self._uid, self._pin))
        return await run_async(lambda: self._api.get_favorite_stores())

    async def get_favorite_products(self):
        if not self._api:
            self._api = await run_async(lambda: IcaAPI(self._uid, self._pin))
        return await run_async(lambda: self._api.get_favorite_products())

    async def get_product_categories(self) -> list[IcaProductCategory]:
        if not self._api:
            self._api = await run_async(lambda: IcaAPI(self._uid, self._pin))
        return await run_async(lambda: self._api.get_product_categories())

    async def get_offers(self, store_ids: list[int]) -> list[IcaOffer]:
        if not self._api:
            self._api = await run_async(lambda: IcaAPI(self._uid, self._pin))
        return await run_async(lambda: self._api.get_offers(store_ids))

    async def get_current_bonus(self):
        if not self._api:
            self._api = await run_async(lambda: IcaAPI(self._uid, self._pin))
        return await run_async(lambda: self._api.get_current_bonus())

    async def get_recipe(self, recipe_id: int) -> IcaRecipe:
        if not self._api:
            self._api = await run_async(lambda: IcaAPI(self._uid, self._pin))
        return await run_async(lambda: self._api.get_recipe(recipe_id))

    async def get_random_recipes(self, nRecipes: int = 5) -> list[IcaRecipe]:
        if not self._api:
            self._api = await run_async(lambda: IcaAPI(self._uid, self._pin))
        return await run_async(lambda: self._api.get_random_recipes(nRecipes))

    async def create_shopping_list(
        self, offline_id: int, title: str, comment: str, storeSorting: bool = True
    ):
        if not self._api:
            self._api = await run_async(lambda: IcaAPI(self._uid, self._pin))
        return await run_async(
            lambda: self._api.create_shopping_list(
                offline_id, title, comment, storeSorting
            )
        )

    async def sync_shopping_list(self, data: IcaShoppingList):
        if not self._api:
            self._api = await run_async(lambda: IcaAPI(self._uid, self._pin))
        return await run_async(lambda: self._api.sync_shopping_list(data))

    async def delete_shopping_list(self, offline_id):
        if not self._api:
            self._api = await run_async(lambda: IcaAPI(self._uid, self._pin))
        return await run_async(lambda: self._api.delete_shopping_list(offline_id))
