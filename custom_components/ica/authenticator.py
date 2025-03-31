import base64
import hashlib
import datetime
import logging
import re
from typing import Dict
from os import urandom

import homeassistant.util.dt as dt_util
import jwt
import requests

from .const import API
from .icatypes import AuthCredentials, AuthState, JwtUserInfo, OAuthClient, OAuthToken

_LOGGER = logging.getLogger(__name__)


class IcaAuthenticator:
    """Class to handle authentications"""

    _credentials: AuthCredentials
    _auth_state: AuthState | None = None

    def __init__(
        self,
        credentials: AuthCredentials,
        state: AuthState | None,
        session: requests.Session | None = None,
    ) -> None:
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

    def register_app(self) -> OAuthClient:
        app_registration_api_access_token = self.get_token_for_app_registration()
        url = self.get_rest_url(API.AppRegistration.APP_REGISTRATION_ENDPOINT)
        j = {"software_id": "dcr-ica-app-template"}
        h = {"Authorization": f"Bearer {app_registration_api_access_token}"}
        response = self.invoke_post(url, json_data=j, headers=h)
        if response and response.status_code in [200, 201]:
            return OAuthClient(response.json())
        return None

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
        # POST /oauth/v2/authorize
        response = self.invoke_get(url, params=p, allow_redirects=False)
        response.raise_for_status()

        location = response.headers["Location"]
        if location is None:
            raise ValueError("Expected a Location redirect")

        state = re.search(r"&state=(\w*)", location)[1]
        _LOGGER.debug("State (Client): %s", state)

        # GET /authn/authenticate
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
        }
        d = {
            "token": token,
            "state": state,
        }
        # POST /oauth/v2/authorize
        response = self.invoke_post(url, params=p, data=d, allow_redirects=False)
        response.raise_for_status()

        location = response.headers["Location"]
        if location is None:
            raise ValueError("Expected a Location redirect")

        code = re.search(r"&code=(\w*)", location)[1]
        _LOGGER.debug("Code: %s", code)

        # GET /authn/authenticate
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
        return OAuthToken(tkn)

    def get_refresh_token(
        self, registered_app: OAuthClient, auth_token: OAuthToken
    ) -> OAuthToken:
        # Invokes /oauth/v2/token
        url = self.get_rest_url(API.URLs.OAUTH2_TOKEN_ENDPOINT)

        basic_auth = IcaAuthenticator.generate_basic_auth(registered_app)
        h: Dict[str, str] = {"Authorization": f"Basic {basic_auth}"}
        d = {
            "grant_type": "refresh_token",
            "refresh_token": auth_token["refresh_token"],
        }
        response = self.invoke_post(url, data=d, headers=h)
        response.raise_for_status()
        tkn = response.json()
        return OAuthToken(tkn)

    @staticmethod
    def generate_basic_auth(registered_app: OAuthClient) -> str:
        """Generates the value for a Basic Auth header"""
        client_id = registered_app["client_id"]
        client_secret = registered_app["client_secret"]
        return base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode(
            "ascii"
        )

    @staticmethod
    def generate_code_challenge():
        """Generates a code_challenge and code_verifier"""
        code_verifier = base64.urlsafe_b64encode(urandom(40)).decode("utf-8")
        re.sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)

        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")

        _LOGGER.debug("code_challenge: %s", code_challenge)
        _LOGGER.debug("code_verifier: %s", code_verifier)
        return (code_challenge, code_verifier)

    def get_auth_state(self) -> AuthState | None:
        """This will get the current auth statee"""
        return self._auth_state

    def ensure_login(self, refresh: bool | None = None) -> AuthState:
        """This will ensure that a valid auth state is loaded"""
        state = self._auth_state.copy() or AuthState()
        self._auth_state = self._handle_login(self._credentials, state, refresh=refresh)
        return self._auth_state

    def _handle_login(
        self,
        credentials: AuthCredentials,
        auth_state: AuthState,
        refresh: bool | None = None,
        retry: int = 0,
    ) -> AuthState:
        """This will initiate an new login based on the current state and token expiration"""
        _LOGGER.debug("Handle login :: Starting state: %s", auth_state)
        now = dt_util.utcnow()

        if new_client := not auth_state.get("client", None):
            # Initialize new client app to get a client_id/client_secret
            auth_state["client"] = self.register_app()
            _LOGGER.debug(
                "Handle login :: Initialized client: %s", auth_state["client"]
            )

        current_token = auth_state.get("token", None)
        current_token_expiry = (
            dt_util.parse_datetime(current_token["expiry"])
            if current_token and current_token.get("expiry", None)
            else None
        )
        # todo: set earlier expiry, to ensure refresh before token gets killed

        if new_client or not current_token:
            auth_state = self._handle_new_login(credentials, auth_state)

        try:
            if current_token_expiry and current_token_expiry < now:
                _LOGGER.info(
                    "Handle login :: Token expired, will refresh... %s < %s",
                    current_token_expiry,
                    now,
                )
                auth_state = self._handle_refresh_login(auth_state)
            elif bool(refresh):
                _LOGGER.info(
                    "Handle login :: Refreshing... %s < %s",
                    current_token_expiry,
                    now,
                )
                auth_state = self._handle_refresh_login(auth_state)
        except requests.exceptions.HTTPError as err:
            _LOGGER.debug(
                "HTTPError-block for Refresh attempt #%s. %s", retry, auth_state
            )
            if retry > 2:
                _LOGGER.fatal("Could not refresh a new token")
                raise
            if err.response.status_code == 400:
                _LOGGER.warning("Got 400 response during token refresh. Err: %s", err)

                # Initiate a new login
                _LOGGER.info("Doing a new login instead...")

                del auth_state["token"]
                return self._handle_login(
                    credentials, auth_state, refresh=False, retry=retry + 1
                )
            raise

        _LOGGER.debug("Handle login :: final Auth_State: %s", auth_state)
        return auth_state

    def _handle_new_login(self, credentials: AuthCredentials, auth_state: AuthState):
        """This will run the complete login chain"""
        _LOGGER.info("Handle login :: Full login initiated")
        now = dt_util.utcnow()

        # Generate code_challenge & code_verifier
        (code_challenge, code_verifier) = IcaAuthenticator.generate_code_challenge()

        # Initiate OAuth login with Authorization-code with PKCE
        state = self.init_oauth(auth_state["client"], code_challenge)

        token = self.init_login(credentials, state)

        access_token = self.get_access_token(
            auth_state["client"], state, token, code_verifier
        )

        auth_state["token"] = access_token
        auth_state["token"]["expiry"] = str(
            now
            + datetime.timedelta(seconds=auth_state["token"].get("expires_in", 2592000))
        )
        _LOGGER.debug("Handle login :: Access Token: %s", access_token)

        # Parse and append the Person Name
        decoded = jwt.decode(
            access_token["id_token"], options={"verify_signature": False}
        )
        auth_state["user"] = JwtUserInfo(decoded)
        _LOGGER.debug("Handle login :: Jwt user info: %s", auth_state["user"])
        return auth_state

    def _handle_refresh_login(self, auth_state: AuthState):
        """This will request a new access_token by sending the refresh_token"""
        now = dt_util.utcnow()

        if refresh_token := self.get_refresh_token(
            auth_state["client"], auth_state["token"]
        ):
            auth_state["token"].update(refresh_token)
            auth_state["token"]["expiry"] = str(
                now
                + datetime.timedelta(
                    seconds=auth_state["token"].get("expires_in", 2592000)
                )
            )
            _LOGGER.debug("Handle login :: Refresh Token: %s", auth_state["token"])
        else:
            _LOGGER.warning(
                "Handle login :: Failed to refresh token. Access token: %s",
                auth_state["token"],
            )
            raise RuntimeError("Failed to retrieve a refresh token")
        return auth_state
