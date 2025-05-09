import logging
from datetime import datetime

import requests

from .authenticator import IcaAuthenticator
from .const import (
    API,
    ARTICLEGROUPS_ENDPOINT,
    MY_BONUS_ENDPOINT,
    MY_COMMON_ARTICLES_ENDPOINT,
    MY_LIST_ENDPOINT,
    MY_LIST_SYNC_ENDPOINT,
    MY_LISTS_ENDPOINT,
    MY_STORES_ENDPOINT,
    RANDOM_RECIPES_ENDPOINT,
    RECIPE_ENDPOINT,
    STORE_ENDPOINT,
    STORE_OFFERS_ENDPOINT,
)
from .http_requests import delete, get, post
from .icatypes import (
    AuthCredentials,
    AuthState,
    IcaAccountCurrentBonus,
    IcaArticle,
    IcaArticleOffer,
    IcaBaseItem,
    IcaProductCategory,
    IcaRecipe,
    IcaShoppingList,
    IcaShoppingListSync,
    IcaStore,
    OffersAndDiscountsForStore,
    ProductLookup,
)

_LOGGER = logging.getLogger(__name__)


def get_rest_url(endpoint: str):
    # return "/".join([API.URLs.BASE_URL, endpoint])
    return "/".join([API.URLs.QUERY_BASE, endpoint])


class IcaAPI:
    """Class to retrieve and manipulate ICA Shopping lists"""

    def __init__(
        self,
        credentials: AuthCredentials,
        auth_state: AuthState | None,
        session: requests.Session | None = None,
    ) -> None:
        self._session = session or requests.Session()
        self._auth_state = auth_state
        self._auth_key: str = (
            auth_state["token"].get("access_token")
            if auth_state and auth_state.get("token")
            else None
        )
        self._authenticator = IcaAuthenticator(credentials, auth_state, session)

    def ensure_login(self, refresh: bool | None = None) -> AuthState:
        auth_state = self._authenticator.ensure_login(refresh=refresh)
        self._auth_state = auth_state
        self._auth_key = auth_state["token"]["access_token"]
        return self._auth_state

    def get_authenticated_user(self):
        # return self._user
        return self._auth_state

    def get_shopping_lists(self) -> list[IcaShoppingList]:
        url = get_rest_url(MY_LISTS_ENDPOINT)
        return get(self._session, url, self._auth_key)

    def get_shopping_list(self, list_id: str) -> IcaShoppingList:
        url = str.format(get_rest_url(MY_LIST_ENDPOINT), list_id)
        return get(self._session, url, self._auth_key)

    def get_baseitems(self) -> list[IcaBaseItem]:
        url = get_rest_url(API.URLs.MY_BASEITEMS_ENDPOINT)
        return get(self._session, url, self._auth_key)

    def sync_baseitems(self, items: list[IcaBaseItem]) -> list[IcaBaseItem]:
        url = get_rest_url(API.URLs.SYNC_MY_BASEITEMS_ENDPOINT)
        return post(self._session, url, self._auth_key, json_data=items)

    def lookup_barcode(self, identifier: str) -> ProductLookup | None:
        url = str.format(
            get_rest_url(API.URLs.PRODUCT_BARCODE_LOOKUP_ENDPOINT), identifier
        )
        try:
            result = get(self._session, url, self._auth_key, return_none_when_404=True)
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 404:
                return None
            raise
        return result

    def get_articles(self) -> list[IcaArticle]:
        url = get_rest_url(API.URLs.ARTICLES_ENDPOINT)
        data = get(self._session, url, self._auth_key)
        return data["articles"] if data and "articles" in data else None

    def get_store(self, store_id) -> IcaStore:
        url = str.format(get_rest_url(STORE_ENDPOINT), store_id)
        return get(self._session, url, self._auth_key)

    def get_favorite_stores(self) -> list[IcaStore]:
        url = get_rest_url(MY_STORES_ENDPOINT)
        fav_stores = get(self._session, url, self._auth_key)
        return [self.get_store(store_id) for store_id in fav_stores["favoriteStores"]]

    def get_favorite_products(self):
        url = get_rest_url(MY_COMMON_ARTICLES_ENDPOINT)
        fav_products = get(self._session, url, self._auth_key)
        return (
            fav_products["commonArticles"] if "commonArticles" in fav_products else None
        )

    def get_offers_for_store(self, store_id: int) -> OffersAndDiscountsForStore:
        url = str.format(get_rest_url(STORE_OFFERS_ENDPOINT), store_id)
        return get(self._session, url, self._auth_key)

    def get_offers(self, store_ids: list[int]) -> dict[str, OffersAndDiscountsForStore]:
        all_store_offers = {
            str(store_id): self.get_offers_for_store(store_id) for store_id in store_ids
        }
        _LOGGER.info("Fetched offers for stores: %s", store_ids)
        return all_store_offers

    def search_offers(
        self, store_ids: list[int], offer_ids: list[str]
    ) -> list[IcaArticleOffer]:
        url = get_rest_url(API.URLs.OFFERS_SEARCH_ENDPOINT)
        j = {"offerIds": offer_ids, "storeIds": store_ids}
        return post(self._session, url, self._auth_key, json_data=j)

    def get_current_bonus(self) -> IcaAccountCurrentBonus:
        url = get_rest_url(MY_BONUS_ENDPOINT)
        return get(self._session, url, self._auth_key)

    def get_recipe(self, recipe_id: int) -> IcaRecipe | None:
        url = str.format(get_rest_url(RECIPE_ENDPOINT), recipe_id)
        try:
            result = get(self._session, url, self._auth_key, return_none_when_404=True)
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 404:
                return None
            raise
        return result

    def get_random_recipes(self, nRecipes: int = 5) -> list[IcaRecipe]:
        if nRecipes < 1:
            return []
        url = str.format(get_rest_url(RANDOM_RECIPES_ENDPOINT), nRecipes)
        return get(self._session, url, self._auth_key)

    def get_product_categories(self) -> list[IcaProductCategory]:
        url = get_rest_url(
            # str.format(ARTICLEGROUPS_ENDPOINT, datetime.date(datetime.now()))
            str.format(ARTICLEGROUPS_ENDPOINT, "2001-01-01")
        )
        return get(self._session, url, self._auth_key)

    def create_shopping_list(
        self, offline_id: int, title: str, comment: str, store_sorting: bool = True
    ) -> IcaShoppingList:
        url = get_rest_url(MY_LISTS_ENDPOINT)
        data = {
            "offlineId": str(offline_id),
            "title": title,
            "commentText": comment,
            "sortingStore": 1 if store_sorting else 0,
            "rows": [],
            "latestChange": f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
        }
        post(self._session, url, self._auth_key, data)
        # list_id = response["id"]
        return self.get_shopping_list(offline_id)

    def sync_shopping_list(self, data: IcaShoppingListSync) -> IcaShoppingList:
        url = str.format(get_rest_url(MY_LIST_SYNC_ENDPOINT), data["offlineId"])
        # new_rows = [x for x in data["rows"] if "sourceId" in x and x["sourceId"] == -1]
        # data = {"changedRows": new_rows}

        if "deletedRows" in data:
            sync_data = {"deletedRows": data["deletedRows"]}
        elif "changedRows" in data:
            sync_data = {"changedRows": data["changedRows"]}
        elif "createdRows" in data:
            sync_data = {"createdRows": data["createdRows"]}
        else:
            sync_data = data

        return post(self._session, url, self._auth_key, sync_data)

    def delete_shopping_list(self, offline_id: int):
        url = str.format(get_rest_url(MY_LIST_ENDPOINT), offline_id)
        return delete(self._session, url, self._auth_key)
