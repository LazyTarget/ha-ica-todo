import requests
from datetime import datetime
from .http_requests import get, post, delete
from .const import (
    MY_LIST_ENDPOINT,
    MY_BONUS_ENDPOINT,
    MY_LISTS_ENDPOINT,
    STORE_ENDPOINT,
    RECIPE_ENDPOINT,
    MY_STORES_ENDPOINT,
    MY_LIST_SYNC_ENDPOINT,
    STORE_OFFERS_ENDPOINT,
    ARTICLEGROUPS_ENDPOINT,
    RANDOM_RECIPES_ENDPOINT,
    MY_COMMON_ARTICLES_ENDPOINT,
    API,
)
from .icatypes import IcaStore, IcaOffer, IcaShoppingList, IcaProductCategory, IcaRecipe
from .icatypes import AuthCredentials, AuthState
from .authenticator import IcaAuthenticator

import logging

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

        # _LOGGER.warning("IcaAPI ensure_login pre: %s", auth_state)
        self._authenticator = IcaAuthenticator(credentials, auth_state, session)
        # auth_state = authenticator.ensure_login()
        # _LOGGER.warning("IcaAPI ensure_login post: %s", auth_state)
        # self._user = auth_state["token"]
        # self._auth_key = auth_state["token"]["access_token"]

        # if user_token is None:
        #     authenticator = IcaAuthenticator(user, psw, session)
        #     _LOGGER.warning("Invoking full login: %s=%s", user, psw)
        #     authenticator.do_full_login(user, psw)
        #     self._user = authenticator._user
        #     _LOGGER.warning("Caching user to API: %s", self._user)
        # else:
        #     self._user = user_token
        #     _LOGGER.warning("Reusing user: %s", self._user)
        # self._auth_key = self._user["access_token"]

    def ensure_login(self):
        auth_state = self._authenticator.ensure_login()
        self._auth_state = auth_state
        self._user = auth_state["token"]
        self._auth_key = auth_state["token"]["access_token"]

    def get_authenticated_user(self):
        # return self._user
        return self._auth_state

    def get_shopping_lists(self) -> list[IcaShoppingList]:
        url = get_rest_url(MY_LISTS_ENDPOINT)
        return get(self._session, url, self._auth_key)

    def get_shopping_list(self, list_id: str) -> IcaShoppingList:
        url = str.format(get_rest_url(MY_LIST_ENDPOINT), list_id)
        return get(self._session, url, self._auth_key)

    def get_baseitems(self):
        url = get_rest_url(API.URLs.MY_BASEITEMS_ENDPOINT)
        return get(self._session, url, self._auth_key)

    def sync_baseitems(self, items: list):
        url = get_rest_url(API.URLs.SYNC_MY_BASEITEMS_ENDPOINT)
        j = items
        return post(self._session, url, self._auth_key, json_data=j)

    def lookup_barcode(self, identifier: str):
        url = str.format(
            get_rest_url(API.URLs.PRODUCT_BARCODE_LOOKUP_ENDPOINT), identifier
        )
        return get(self._session, url, self._auth_key)

    def get_articles(self):
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

    def get_offers_for_store(self, store_id: int) -> list[IcaOffer]:
        url = str.format(get_rest_url(STORE_OFFERS_ENDPOINT), store_id)
        return get(self._session, url, self._auth_key)

    def get_offers(self, store_ids: list[int]) -> list[IcaOffer]:
        all_store_offers = {
            store_id: self.get_offers_for_store(store_id) for store_id in store_ids
        }
        _LOGGER.info("Fetched offers for stores: %s", store_ids)
        return all_store_offers

    def search_offers(
        self, store_ids: list[int], offer_ids: list[str]
    ) -> list[IcaOffer]:
        url = get_rest_url(API.URLs.OFFERS_SEARCH_ENDPOINT)
        j = {"offerIds": offer_ids, "storeIds": store_ids}
        return post(self._session, url, self._auth_key, json_data=j)

    def get_current_bonus(self):
        url = get_rest_url(MY_BONUS_ENDPOINT)
        return get(self._session, url, self._auth_key)

    def get_recipe(self, recipe_id: int) -> IcaRecipe:
        url = str.format(get_rest_url(RECIPE_ENDPOINT), recipe_id)
        return get(self._session, url, self._auth_key)

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
        self, offline_id: int, title: str, comment: str, storeSorting: bool = True
    ) -> IcaShoppingList:
        url = get_rest_url(MY_LISTS_ENDPOINT)
        data = {
            "offlineId": str(offline_id),
            "title": title,
            "commentText": comment,
            "sortingStore": 1 if storeSorting else 0,
            "rows": [],
            "latestChange": f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
        }
        post(self._session, url, self._auth_key, data)
        # list_id = response["id"]
        return self.get_shopping_list(offline_id)

    def sync_shopping_list(self, data: IcaShoppingList):
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
