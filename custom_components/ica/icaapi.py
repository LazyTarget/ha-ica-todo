import requests
import json
from datetime import datetime
from .http_requests import get, post, delete
from .const import (
    AUTH_TICKET,
    LIST_NAME,
    ITEM_LIST,
    ITEM_NAME,
    IS_CHECKED,
    
    AUTH_ENDPOINT,
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
    ARTICLEGROUPS_ENDPOINT,
    RANDOM_RECIPES_ENDPOINT,
    MY_COMMON_ARTICLES_ENDPOINT,
    API,
)
from .icatypes import IcaStore, IcaOffer, IcaShoppingList, IcaProductCategory, IcaRecipe

import logging
_LOGGER = logging.getLogger(__name__)

from homeassistant.util.json import load_json
from homeassistant.helpers.json import save_json


cookie_jar = {}

def get_rest_url(endpoint: str):
    return "/".join([API.URLs.BASE_URL, endpoint])


def invoke_get(url, data=None, headers=None, cookies=None, timeout=30):
    _LOGGER.debug('[GET] %s Request', url)
    if data is not None:
        _LOGGER.debug('[GET] %s Request Data: %s', url, data)
    if cookies is not None:
        _LOGGER.warning("Cookies: %s", cookies)
    response = requests.get(url, data=data, headers=headers, timeout=timeout, cookies=cookies)
    _LOGGER.debug('[GET] %s Response Code: %s', url, response.status_code)
    _LOGGER.debug('[GET] %s Response Text: %s', url, response.text)
    if response.cookies is not None:
        cookies = response.cookies
    response.raise_for_status()
    return response


def invoke_post(url, data=None, json=None, headers=None, cookies=None, timeout=30):
    _LOGGER.debug('[POST] %s Request', url)
    if data is not None:
        _LOGGER.debug('[POST] %s Request Data: %s', url, data)
    if json is not None:
        _LOGGER.debug('[POST] %s Request Json: %s', url, json)
    if cookies is not None:
        _LOGGER.warning("Cookies: %s", cookies)
    response = requests.post(url, data=data, json=json, headers=headers, timeout=timeout, cookies=cookies)
    _LOGGER.debug('[POST] %s Response Code: %s', url, response.status_code)
    _LOGGER.debug('[POST] %s Response Text: %s', url, response.text)
    if response.cookies is not None:
        cookies = response.cookies
    response.raise_for_status()
    return response


def get_token_for_app_registration():
    url = get_rest_url(API.URLs.OAUTH2_TOKEN_ENDPOINT)
    d = {
        "client_id": API.AppRegistration.CLIENT_ID,
        "client_secret": API.AppRegistration.CLIENT_SECRET,
        "grant_type": "client_credentials",
        "scope": "dcr",
        "response_type": "token"
    }
    response = invoke_post(url, data=d)
    if response and response.status_code in [200, 201]:
        return response.json()["access_token"]
    response.raise_for_status()
    return None


def register_app(app_registration_api_access_token):
    url = get_rest_url(API.AppRegistration.APP_REGISTRATION_ENDPOINT)
    j = {
        "software_id": "dcr-ica-app-template"
    }
    h = {
        'Authorization': f"Bearer {app_registration_api_access_token}"
    }
    response = invoke_post(url, json=j, headers=h)
    if response and response.status_code in [200, 201]:
        return response.json()
    return None


def init_app():
    app_registration_api_access_token = get_token_for_app_registration()
    registered_app = register_app(app_registration_api_access_token)
    return registered_app


def init_oauth(registered_app, code_challenge):
    url = get_rest_url(API.URLs.OAUTH2_AUTHORIZE_ENDPOINT)
    d = {
        "client_id": registered_app["client_id"],
        "scope": registered_app["scope"],
        "redirect_uri": "icacurity://app",
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "login",
        "acr": "urn:se:curity:authentication:html-form:IcaCustomers",
    }
    response = invoke_get(url, data=d)
    _LOGGER.info('Headers %s', response.headers.get("Location"))
    if response:
        return response.headers["Location"]
    return None


def generate_code_challenge():
    import base64
    import os
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8')
    print(code_verifier)
    #KTZVMl6OrcoTIej5c9QUaQ5x2p95P46D5hd2yb7kuAIBCVM9j0P1lA==
    import re
    re.sub('[^a-zA-Z0-9]+', '', code_verifier)
    #'KTZVMl6OrcoTIej5c9QUaQ5x2p95P46D5hd2yb7kuAIBCVM9j0P1lA'
    code_verifier = re.sub('[^a-zA-Z0-9]+', '', code_verifier)
    code_verifier, len(code_verifier)
    #('KTZVMl6OrcoTIej5c9QUaQ5x2p95P46D5hd2yb7kuAIBCVM9j0P1lA', 54)
    import hashlib
    code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    print(code_challenge)
    #b'\xf3T|\x0b\xa4!#\x91\xde\xe1\xe9\xcf\x0c*\xfb*\x04j?\xa7\xd0g~\xc55\x00\x0f\xe4\xd9\x1a8\x18'
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
    print(code_challenge)
    #81R8C6QhI5He4enPDCr7KgRqP6fQZ37FNQAP5NkaOBg=
    code_challenge = code_challenge.replace('=', '')
    print(code_challenge)
    #81R8C6QhI5He4enPDCr7KgRqP6fQZ37FNQAP5NkaOBg
    code_challenge, len(code_challenge)
    #('81R8C6QhI5He4enPDCr7KgRqP6fQZ37FNQAP5NkaOBg', 43)
    return (code_challenge, code_verifier)


def get_auth_key(user, psw):
    url = get_rest_url(AUTH_ENDPOINT)
    auth = (user, psw)
    response = invoke_get(url, auth=auth, timeout=15)
    if response:
        return response.headers[AUTH_TICKET]
    return None


class IcaAPI:
    ### Class to retrieve and manipulate ICA Shopping lists ###
    def __init__(self, user, psw, session: requests.Session | None = None) -> None:
        registered_app = init_app()
        (code_challenge, code_verifier) = generate_code_challenge()
        init_oauth(registered_app, code_challenge)
        raise ValueError("Stopping setup as the rest is not implemented")
        
        self._auth_key = get_auth_key(user, psw)
        self._session = session or requests.Session()

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
        return [self.get_store(store_id) for store_id in fav_stores["FavoriteStores"]]

    def get_favorite_products(self):
        url = get_rest_url(MY_COMMON_ARTICLES_ENDPOINT)
        fav_products = get(self._session, url, self._auth_key)
        return (
            fav_products["CommonArticles"] if "CommonArticles" in fav_products else None
        )

    def get_offers(self, store_ids: list[int]) -> list[IcaOffer]:
        url = str.format(
            get_rest_url(OFFERS_ENDPOINT), ",".join(map(lambda x: str(x), store_ids))
        )
        return get(self._session, url, self._auth_key)

    def get_random_recipes(self, nRecipes: int = 5) -> list[IcaRecipe]:
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
            "OfflineId": str(offline_id),
            "Title": title,
            "CommentText": comment,
            "SortingStore": 1 if storeSorting else 0,
            "Rows": [],
            "LatestChange": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        response = post(self._session, url, self._auth_key, data)
        # list_id = response["id"]
        return self.get_shopping_list(offline_id)

    def sync_shopping_list(self, data: IcaShoppingList):
        url = str.format(get_rest_url(MY_LIST_SYNC_ENDPOINT), data["OfflineId"])
        # new_rows = [x for x in data["Rows"] if "SourceId" in x and x["SourceId"] == -1]
        # data = {"ChangedRows": new_rows}

        if "DeletedRows" in data:
            sync_data = {"DeletedRows": data["DeletedRows"]}
        elif "ChangedRows" in data:
            sync_data = {"ChangedRows": data["ChangedRows"]}
        elif "CreatedRows" in data:
            sync_data = {"CreatedRows": data["CreatedRows"]}
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
