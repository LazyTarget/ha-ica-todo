import requests
import jwt
import re
from .const import API

import logging
_LOGGER = logging.getLogger(__name__)


class IcaAuthenticator:
    """Class to handle authentications"""
    cookie_jar = None
    _auth_key = None

    def __init__(self, user, psw, session: requests.Session | None = None) -> None:
        # self._auth_key = get_auth_key(user, psw)
        self._session = session or requests.Session()

    def get_rest_url(self, endpoint: str):
        return "/".join([API.URLs.BASE_URL, endpoint])

    def invoke_get(self, url, params=None, data=None, headers=None, timeout=30, allow_redirects=True):
        if data is not None:
            _LOGGER.debug('[GET] %s Request Data: %s', url, data)

        response = self._session.get(url,
                                     params=params,
                                     data=data,
                                     headers=headers,
                                     timeout=timeout,
                                     allow_redirects=allow_redirects)

        s = response.status_code not in [200, 201, 302, 303]
        if not s:
            _LOGGER.warning('[GET] %s Response Code: %s', url, response.status_code)
            if "json" in response.headers.get("Content-Type", 'application/json') or response.status_code not in [200, 201]:
                _LOGGER.debug('[GET] %s Response Text: %s', url, response.text)

        response.raise_for_status()
        return response

    def invoke_post(self, url, params=None, data=None, json_data=None, headers=None, timeout=30, allow_redirects=True):
        if data is not None:
            _LOGGER.debug('[POST] %s Request Data: %s', url, data)
        if json_data is not None:
            _LOGGER.debug('[POST] %s Request Json: %s', url, json_data)

        response = self._session.post(url, params=params, data=data, json=json_data,
                                      headers=headers, timeout=timeout,
                                      allow_redirects=allow_redirects)

        s = response.status_code not in [200, 201, 302, 303]
        if not s:
            _LOGGER.warning('[POST] %s Response Code: %s', url, response.status_code)
            if "json" in response.headers.get("Content-Type", 'application/json') or response.status_code not in [200, 201]:
                _LOGGER.debug('[POST] %s Response Text: %s', url, response.text)

        response.raise_for_status()
        return response

    def get_token_for_app_registration(self):
        url = self.get_rest_url(API.URLs.OAUTH2_TOKEN_ENDPOINT)
        d = {
            "client_id": API.AppRegistration.CLIENT_ID,
            "client_secret": API.AppRegistration.CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": "dcr",
            "response_type": "token"
        }
        response = self.invoke_post(url, data=d)
        if response and response.status_code in [200, 201]:
            return response.json()["access_token"]
        response.raise_for_status()
        return None

    def register_app(self, app_registration_api_access_token):
        url = self.get_rest_url(API.AppRegistration.APP_REGISTRATION_ENDPOINT)
        j = {
            "software_id": "dcr-ica-app-template"
        }
        h = {
            'Authorization': f"Bearer {app_registration_api_access_token}"
        }
        response = self.invoke_post(url, json_data=j, headers=h)
        if response and response.status_code in [200, 201]:
            return response.json()
        return None

    def init_app(self):
        app_registration_api_access_token = self.get_token_for_app_registration()
        registered_app = self.register_app(app_registration_api_access_token)
        return registered_app

    def init_oauth(self, registered_app, code_challenge):
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

    def init_login(self, user, pwd, state):
        url = self.get_rest_url(API.URLs.LOGIN_ENDPOINT)
        d = {
            "userName": user,
            "password": pwd,
        }
        # Posts login form...
        response = self.invoke_post(url, data=d)
        if response.status_code == 400:
            raise RuntimeError("Got 404 on Login request, might be incorrect credentials?")

        response.raise_for_status()

        api_state = re.search(r'<input type="hidden" name="state" value="(\w*)', response.text)[1]
        token = re.search(r'<input type="hidden" name="token" value="(\w*)', response.text)[1]

        if api_state != state:
            _LOGGER.warning("States are different! Client: %s, Server: %s", state, api_state)
        else:
            _LOGGER.debug("State (Server): %s", api_state)

        return token

    def get_access_token(self, registered_app, state, token, code_verifier):
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
        
        # Parse and append the Person Name
        decoded = jwt.decode(tkn["id_token"], options={"verify_signature": False})
        tkn["person_name"] = f"{decoded["given_name"]} {decoded["family_name"]}"
        return tkn

    def generate_code_challenge(self):
        import base64
        import os
        import hashlib

        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8')
        re.sub('[^a-zA-Z0-9]+', '', code_verifier)
        code_verifier = re.sub('[^a-zA-Z0-9]+', '', code_verifier)
        code_verifier, len(code_verifier)
        # ('KTZVMl6OrcoTIej5c9QUaQ5x2p95P46D5hd2yb7kuAIBCVM9j0P1lA', 54)
        
        code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
        code_challenge = code_challenge.replace('=', '')
        code_challenge, len(code_challenge)
        # ('81R8C6QhI5He4enPDCr7KgRqP6fQZ37FNQAP5NkaOBg', 43)

        _LOGGER.debug("code_challenge: %s", code_challenge)
        _LOGGER.debug("code_verifier: %s", code_verifier)
        return (code_challenge, code_verifier)

    def do_full_login(self, user, psw):
        """This will run the complete chain"""

        # Register an App to get a client_id
        registered_app = self.init_app()

        # Generate code_challenge & code_verifier
        (code_challenge, code_verifier) = self.generate_code_challenge()

        # Initiate OAuth login with Authorization-code with PKCE
        state = self.init_oauth(registered_app, code_challenge)

        token = self.init_login(user, psw, state)

        result = self.get_access_token(registered_app, state, token, code_verifier)
        _LOGGER.debug("Full login completed :: Token: %s", result)

        self._user = result
        self._auth_key = result["access_token"]
        return result
