import logging
import re
import datetime
from typing import Dict

import jwt
import requests
import homeassistant.util.dt as dt_util

from .const import API
from .icatypes import AuthCredentials, OAuthClient, OAuthToken, JwtUserInfo, AuthState

_LOGGER = logging.getLogger(__name__)


class IcaAuthenticator:
    """Class to handle authentications"""

    _credentials: AuthCredentials
    _auth_state: AuthState | None = None
    _auth_key = None

    def __init__(
        self,
        credentials: AuthCredentials,
        state: AuthState | None,
        session: requests.Session | None = None,
    ) -> None:
        # self._auth_key = get_auth_key(user, psw)
        self._session = session or requests.Session()
        self._auth_state = state
        self._credentials = credentials

    def get_rest_url(self, endpoint: str):
        return "/".join([API.URLs.BASE_URL, endpoint])

    def invoke_get(
        self,
        url,
        params=None,
        data=None,
        headers=None,
        timeout=30,
        allow_redirects=True,
    ):
        if data is not None:
            _LOGGER.debug("[GET] %s Request Data: %s", url, data)

        response = self._session.get(
            url,
            params=params,
            data=data,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
        )

        s = response.status_code not in [200, 201, 302, 303]
        if not s:
            _LOGGER.warning("[GET] %s Response Code: %s", url, response.status_code)
            if "json" in response.headers.get(
                "Content-Type", "application/json"
            ) or response.status_code not in [200, 201]:
                _LOGGER.debug("[GET] %s Response Text: %s", url, response.text)

        response.raise_for_status()
        return response

    def invoke_post(
        self,
        url,
        params=None,
        data=None,
        json_data=None,
        headers=None,
        timeout=30,
        allow_redirects=True,
    ):
        if data is not None:
            _LOGGER.debug("[POST] %s Request Data: %s", url, data)
        if json_data is not None:
            _LOGGER.debug("[POST] %s Request Json: %s", url, json_data)

        response = self._session.post(
            url,
            params=params,
            data=data,
            json=json_data,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
        )

        s = response.status_code not in [200, 201, 302, 303]
        if not s:
            _LOGGER.warning("[POST] %s Response Code: %s", url, response.status_code)
            if "json" in response.headers.get(
                "Content-Type", "application/json"
            ) or response.status_code not in [200, 201]:
                _LOGGER.debug("[POST] %s Response Text: %s", url, response.text)

        response.raise_for_status()
        return response

    def get_token_for_app_registration(self):
        url = self.get_rest_url(API.URLs.OAUTH2_TOKEN_ENDPOINT)
        d = {
            "client_id": API.AppRegistration.CLIENT_ID,
            "client_secret": API.AppRegistration.CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": "dcr",
            "response_type": "token",
        }
        response = self.invoke_post(url, data=d)
        if response and response.status_code in [200, 201]:
            return response.json()["access_token"]
        response.raise_for_status()
        return None

    def register_app(self, app_registration_api_access_token) -> OAuthClient:
        url = self.get_rest_url(API.AppRegistration.APP_REGISTRATION_ENDPOINT)
        j = {"software_id": "dcr-ica-app-template"}
        h = {"Authorization": f"Bearer {app_registration_api_access_token}"}
        response = self.invoke_post(url, json_data=j, headers=h)
        if response and response.status_code in [200, 201]:
            return OAuthClient(response.json())
        return None

    def init_app(self):
        app_registration_api_access_token = self.get_token_for_app_registration()
        return self.register_app(app_registration_api_access_token)

    def init_oauth(self, registered_app: OAuthClient, code_challenge):
        url = self.get_rest_url(API.URLs.OAUTH2_AUTHORIZE_ENDPOINT)
        p = {
            "client_id": registered_app["client_id"],
            "scope": registered_app["scope"],
            "redirect_uri": "icacurity://app",
            "response_type": "code",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "prompt": "login",
            "acr": "urn:se:curity:authentication:html-form:IcaCustomers",
        }
        # Invokes /oauth/v2/authorize
        response = self.invoke_get(url, params=p, allow_redirects=False)
        response.raise_for_status()

        location = response.headers["Location"]
        if location is None:
            raise ValueError("Expected a Location redirect")

        state = re.search(r"&state=(\w*)", location)[1]
        _LOGGER.debug("State (Client): %s", state)

        # Invokes /authn/authenticate
        response = self.invoke_get(location)
        response.raise_for_status()

        return state

    def init_login(self, credentials: AuthCredentials, state):
        url = self.get_rest_url(API.URLs.LOGIN_ENDPOINT)
        d = {
            "userName": credentials["username"],
            "password": credentials["password"],
        }
        # Posts login form...
        response = self.invoke_post(url, data=d)
        if response.status_code == 400:
            raise RuntimeError(
                "Got 404 on Login request, might be incorrect credentials?"
            )

        response.raise_for_status()

        api_state = re.search(
            r'<input type="hidden" name="state" value="(\w*)', response.text
        )[1]
        token = re.search(
            r'<input type="hidden" name="token" value="(\w*)', response.text
        )[1]

        if api_state != state:
            _LOGGER.warning(
                "States are different! Client: %s, Server: %s", state, api_state
            )
        else:
            _LOGGER.debug("State (Server): %s", api_state)

        return token

    def get_access_token(
        self, registered_app: OAuthClient, state, token, code_verifier
    ) -> OAuthToken:
        url = self.get_rest_url(API.URLs.OAUTH2_AUTHORIZE_ENDPOINT)
        p = {
            "client_id": registered_app["client_id"],
            "forceAuthN": "true",
            "acr": "urn:se:curity:authentication:html-form:IcaCustomers",
            # urn%3Ase%3Acurity%3Aauthentication%3Ahtml-form%3AIcaCustomers
        }
        d = {
            "token": token,
            "state": state,
        }
        # Authorize
        response = self.invoke_post(url, params=p, data=d, allow_redirects=False)
        response.raise_for_status()

        location = response.headers["Location"]
        if location is None:
            raise ValueError("Expected a Location redirect")

        code = re.search(r"&code=(\w*)", location)[1]
        _LOGGER.debug("Code: %s", code)

        # Invokes /authn/authenticate
        url = self.get_rest_url(API.URLs.OAUTH2_TOKEN_ENDPOINT)
        d = {
            "code": code,
            "client_id": registered_app["client_id"],
            "client_secret": registered_app["client_secret"],
            "grant_type": "authorization_code",
            "scope": registered_app["scope"],
            "response_type": "token",
            "code_verifier": code_verifier,
            "redirect_uri": "icacurity://app",
        }
        response = self.invoke_post(url, data=d)
        response.raise_for_status()
        tkn = response.json()

        # # Parse and append the Person Name
        # decoded = jwt.decode(tkn["id_token"], options={"verify_signature": False})
        # # tkn["person_name"] = f"{decoded['given_name']} {decoded['family_name']}"
        # user_info = JwtUserInfo(decoded)
        # tkn["person_name"] = user_info.person_name
        # tkn["jwt_info"] = user_info
        return OAuthToken(tkn)

    def get_refresh_token(
        self, registered_app: OAuthClient, auth_token: OAuthToken
    ) -> OAuthToken:
        # Invokes /oauth/v2/token
        url = self.get_rest_url(API.URLs.OAUTH2_TOKEN_ENDPOINT)
        import base64

        basic_auth = base64.b64encode(
            f"{registered_app['client_id']}:{registered_app['client_secret']}".encode("utf-8")
        ).decode("ascii")
        h: Dict[str, str] = {"Authorization": f"Basic {basic_auth}"}
        d = {"grant_type": "refresh_token", "refresh_token": auth_token["refresh_token"]}
        response = self.invoke_post(url, data=d, headers=h)
        response.raise_for_status()
        tkn = response.json()
        return OAuthToken(tkn)

    def generate_code_challenge(self):
        import base64
        import hashlib
        import os

        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        re.sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)
        # code_verifier, len(code_verifier)
        # ('KTZVMl6OrcoTIej5c9QUaQ5x2p95P46D5hd2yb7kuAIBCVM9j0P1lA', 54)

        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        # code_challenge, len(code_challenge)
        # ('81R8C6QhI5He4enPDCr7KgRqP6fQZ37FNQAP5NkaOBg', 43)

        _LOGGER.debug("code_challenge: %s", code_challenge)
        _LOGGER.debug("code_verifier: %s", code_verifier)
        return (code_challenge, code_verifier)

    def ensure_login(self):
        """This will run the complete chain"""

        state = self._auth_state or AuthState()
        state = self._handle_login(self._credentials, state)
        self._auth_state = state
        self._auth_key = state["token"]["access_token"]
        return self._auth_state

        # # Register an App to get a client_id
        # registered_app = self.init_app()

        # # Generate code_challenge & code_verifier
        # (code_challenge, code_verifier) = self.generate_code_challenge()

        # # Initiate OAuth login with Authorization-code with PKCE
        # state = self.init_oauth(registered_app, code_challenge)

        # token = self.init_login(credentials, state)

        # result = self.get_access_token(registered_app, state, token, code_verifier)
        # _LOGGER.fatal("Full login completed :: Token: %s", result)

        # self._user = result
        # self._auth_key = result["access_token"]
        # return result

    def _handle_login(self, credentials: AuthCredentials, auth_state: AuthState):
        # todo: make into staticmethod

        _LOGGER.info(
            "Handle login :: Starting state: %s", auth_state
        )
        # now = datetime.datetime.now()
        now = dt_util.utcnow()

        if new_client := not auth_state.get("client", None):
            # Initialize new client app to get a client_id/client_secret
            auth_state["client"] = self.init_app()
            _LOGGER.info(
                "Handle login :: Initialized client: %s", auth_state["client"]["client_id"]
            )

        current_token = auth_state.get("token", None)
        if current_token:
            current_token_expiry = current_token.get("expiry", str(now))
            _LOGGER.fatal("Current token expiry: %s", current_token_expiry)
            current_token_expiry_parse = datetime.datetime.fromisoformat(current_token_expiry)
            _LOGGER.fatal("Current token expiry fromisoformat: %s", current_token_expiry_parse)
            current_token_expiry = dt_util.parse_datetime(current_token_expiry)
            _LOGGER.fatal("Current token expiry parse_datetime: %s", current_token_expiry)

        if new_client or not current_token:
            # Has no token or is a new client, then init a new login
            _LOGGER.fatal("Handle login :: Full login initiated")

            # Generate code_challenge & code_verifier
            (code_challenge, code_verifier) = self.generate_code_challenge()

            # Initiate OAuth login with Authorization-code with PKCE
            state = self.init_oauth(auth_state["client"], code_challenge)

            token = self.init_login(credentials, state)

            access_token = self.get_access_token(
                auth_state["client"], state, token, code_verifier
            )

            auth_state["token"] = access_token
            auth_state["token"]["expiry"] = str(now + datetime.timedelta(
                seconds=state.token.get("expires_in", 2592000)
            ))
            _LOGGER.info("Handle login :: Access Token: %s", state.token)

            # Parse and append the Person Name
            decoded = jwt.decode(
                access_token["id_token"], options={"verify_signature": False}
            )
            auth_state["userInfo"] = JwtUserInfo(decoded)
            _LOGGER.info("Handle login :: Jwt user info: %s", auth_state["userInfo"])
        elif current_token and current_token_expiry < now:
            _LOGGER.fatal("Need to refresh login: %s < %s", current_token_expiry, now)
            # Refresh login
            if refresh_token := self.get_refresh_token(auth_state["client"], auth_state["token"]):
                auth_state["token"].update(refresh_token)
                auth_state["token"]["expiry"] = str(now + datetime.timedelta(
                    seconds=auth_state["token"].get("expires_in", 2592000)
                ))
                _LOGGER.info("Handle login :: Refresh Token: %s", state.token)
            else:
                _LOGGER.warning(
                    "Handle login :: Failed to refresh token. Access token: %s",
                    auth_state["token"]
                )
                raise RuntimeError("Failed to retrieve a refresh token")

        _LOGGER.info("Handle login :: Auth_State: %s", auth_state)
        return auth_state
