import asyncio

from .icaapi import IcaAPI
from .icatypes import (
    IcaArticleOffer,
    IcaBaseItem,
    IcaShoppingList,
    IcaStore,
    IcaProductCategory,
    IcaRecipe,
    OffersAndDiscountsForStore,
)
from .icatypes import AuthCredentials, AuthState


async def run_async(func):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func)


class IcaAPIAsync:
    """Class to retrieve and hold the data for a Shopping list from ICA"""

    def __init__(
        self, credentials: AuthCredentials, auth_state: AuthState | None
    ) -> None:
        self._credentials = credentials
        self._auth_state = auth_state
        self._api = None

    async def ensure_login(self):
        if not self._api:
            self._api = await run_async(
                lambda: IcaAPI(self._credentials, self._auth_state)
            )
        return await run_async(lambda: self._api.ensure_login())

    def get_authenticated_user(self):
        if not self._api:
            self._api = IcaAPI(self._credentials, self._auth_state)
        return self._api.get_authenticated_user()

    async def get_shopping_lists(self) -> list[IcaShoppingList]:
        if not self._api:
            self._api = await run_async(
                lambda: IcaAPI(self._credentials, self._auth_state)
            )
        return await run_async(lambda: self._api.get_shopping_lists())

    async def get_shopping_list(self, list_id: str) -> IcaShoppingList:
        if not self._api:
            self._api = await run_async(
                lambda: IcaAPI(self._credentials, self._auth_state)
            )
        return await run_async(lambda: self._api.get_shopping_list(list_id))

    async def get_baseitems(self) -> list[IcaBaseItem]:
        if not self._api:
            self._api = await run_async(
                lambda: IcaAPI(self._credentials, self._auth_state)
            )
        return await run_async(lambda: self._api.get_baseitems())

    async def sync_baseitems(self, items: list[IcaBaseItem]) -> list[IcaBaseItem]:
        if not self._api:
            self._api = await run_async(
                lambda: IcaAPI(self._credentials, self._auth_state)
            )
        return await run_async(lambda: self._api.sync_baseitems(items))

    async def lookup_barcode(self, identifier):
        if not self._api:
            self._api = await run_async(
                lambda: IcaAPI(self._credentials, self._auth_state)
            )
        return await run_async(lambda: self._api.lookup_barcode(identifier))

    async def get_articles(self):
        if not self._api:
            self._api = await run_async(
                lambda: IcaAPI(self._credentials, self._auth_state)
            )
        return await run_async(lambda: self._api.get_articles())

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

    async def get_offers(
        self, store_ids: list[int]
    ) -> dict[str, OffersAndDiscountsForStore]:
        if not self._api:
            self._api = await run_async(lambda: IcaAPI(self._uid, self._pin))
        return await run_async(lambda: self._api.get_offers(store_ids))

    async def search_offers(
        self, store_ids: list[int], offer_ids: list[str]
    ) -> list[IcaArticleOffer]:
        if not self._api:
            self._api = await run_async(lambda: IcaAPI(self._uid, self._pin))
        return await run_async(lambda: self._api.search_offers(store_ids, offer_ids))

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
