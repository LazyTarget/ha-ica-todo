from __future__ import annotations
from typing import Any, Dict
from requests import Session
import json
import logging

_LOGGER = logging.getLogger(__name__)

CONTENT_TYPE = ("Content-Type", "application/json; charset=utf-8")
AUTHORIZATION = ("Authorization", "Bearer %s")
X_REQUEST_ID = ("X-Request-Id", "%s")


def create_headers(
    auth_key: str | None = None,
    with_content: bool = False,
    request_id: str | None = None,
) -> Dict[str, str]:
    headers: Dict[str, str] = {}

    if auth_key:
        headers |= [(AUTHORIZATION[0], AUTHORIZATION[1] % auth_key)]
    if with_content:
        headers.update([CONTENT_TYPE])
    if request_id:
        headers.update([(X_REQUEST_ID[0], X_REQUEST_ID[1] % request_id)])
    return headers


def get(
    session: Session,
    url: str,
    auth_key: str | None = None,
    params: Dict[str, Any] | None = None,
    return_none_when_404: bool = False,
):
    _LOGGER.info(
        "HTTP [GET] Req: %s%s", url, f" | Params: {str(params)}" if params else ""
    )
    response = session.get(
        url, params=params, headers=create_headers(auth_key=auth_key)
    )

    if response.status_code == 200:
        _LOGGER.debug("HTTP [GET] Resp: %s", json.dumps(response.json()))
        return response.json()
    elif response.status_code == 404 and return_none_when_404:
        return None

    try:
        response.raise_for_status()
    except BaseException as ex:
        _LOGGER.error("HTTP [GET] Resp: %s -> %s", response.status_code, response.text)
        raise ex

    return response.ok


def post(
    session: Session,
    url: str,
    auth_key: str | None = None,
    data: Dict[str, Any] | None = None,
    json_data: Any | None = None,
):
    request_id = data.pop("request_id", None) if data else None

    headers = create_headers(
        auth_key=auth_key, with_content=bool(data), request_id=request_id
    )

    _LOGGER.info("HTTP [POST] Req: %s", url)
    response = session.post(
        url,
        headers=headers,
        data=json.dumps(data) if data else None,
        json=json_data,
    )

    if response.status_code == 200:
        _LOGGER.debug("HTTP [POST] Resp: %s", json.dumps(response.json()))
        return response.json()

    try:
        response.raise_for_status()
    except BaseException as ex:
        _LOGGER.error("HTTP [POST] Resp: %s -> %s", response.status_code, response.text)
        raise ex

    return response.ok


def delete(
    session: Session,
    url: str,
    auth_key: str | None = None,
    args: Dict[str, Any] | None = None,
):
    request_id = args.pop("request_id", None) if args else None

    headers = create_headers(auth_key=auth_key, request_id=request_id)

    _LOGGER.info("HTTP [DELETE] Req: %s", url)
    response = session.delete(
        url,
        headers=headers,
    )

    try:
        response.raise_for_status()
    except BaseException as ex:
        _LOGGER.error(
            "HTTP [DELETE] Resp: %s -> %s", response.status_code, response.text
        )
        raise ex

    return response.ok
