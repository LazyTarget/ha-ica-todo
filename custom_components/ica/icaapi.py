import requests
from datetime import datetime
from .http_requests import get, post, delete
from .const import (
    AUTH_TICKET,
    LIST_NAME,
    ITEM_LIST,
    ITEM_NAME,
    IS_CHECKED,
    
    MY_LIST_ENDPOINT,
    MY_BONUS_ENDPOINT,
    MY_CARDS_ENDPOINT,
    MY_LISTS_ENDPOINT,
    STORE_ENDPOINT,
    OFFERS_ENDPOINT,
    RECIPE_ENDPOINT,
    MY_RECIPES_ENDPOINT,
    MY_STORES_ENDPOINT,
    MY_LIST_SYNC_ENDPOINT,
    STORE_SEARCH_ENDPOINT,
    STORE_OFFERS_ENDPOINT,
    ARTICLEGROUPS_ENDPOINT,
    RANDOM_RECIPES_ENDPOINT,
    MY_COMMON_ARTICLES_ENDPOINT,
    API,
)
from .icatypes import IcaStore, IcaOffer, IcaShoppingList, IcaProductCategory, IcaRecipe
from .authenticator import IcaAuthenticator

import logging
_LOGGER = logging.getLogger(__name__)

def get_rest_url(endpoint: str):
    # return "/".join([API.URLs.BASE_URL, endpoint])
    return "/".join([API.URLs.QUERY_BASE, endpoint])

class IcaAPI:
    """Class to retrieve and manipulate ICA Shopping lists"""
    
    def __init__(self, user, psw, user_token=None, session: requests.Session | None = None) -> None:
        if user_token is None:
            authenticator = IcaAuthenticator(user, psw, session)
            authenticator.do_full_login(user, psw)
            self._user = authenticator._user
        else:
            self._user = user_token
        
        self._auth_key = self._user["access_token"]
        self._session = session or requests.Session()
        
    def get_authenticated_user(self):
        return self._user

    def get_shopping_lists(self) -> list[IcaShoppingList]:
        url = get_rest_url(MY_LISTS_ENDPOINT)
        return get(self._session, url, self._auth_key)

    def get_shopping_list(self, list_id: str) -> IcaShoppingList:
        url = str.format(get_rest_url(MY_LIST_ENDPOINT), list_id)
        return get(self._session, url, self._auth_key)

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
        all_store_offers = {}
        for store_id in store_ids:
            all_store_offers[store_id] = self.get_offers_for_store(store_id)
        _LOGGER.info("Fetched offers for stores: %s", store_ids)
        return all_store_offers

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
            "latestChange": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        response = post(self._session, url, self._auth_key, data)
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

        data2 = post(self._session, url, self._auth_key, sync_data)
        # if data is not None and "Rows" in data:
        #    for row in data["Rows"]:
        #        name = row["ProductName"]
        #        uuid = row["OfflineId"]
        #        status = row["IsStrikedOver"]
        #        source = row["SourceId"]

        return data2

    def delete_shopping_list(self, offline_id: int):
        url = str.format(get_rest_url(MY_LIST_ENDPOINT), offline_id)
        return delete(self._session, url, self._auth_key)
