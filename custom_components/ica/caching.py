"""Local storage for cached ICA data."""

from pathlib import Path
import asyncio
import json
import logging
import datetime as dt
from typing import Generic, Any, TypeVar, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .utils import EmptyLogger
from .const import CACHING_SECONDS_LONG_TERM

STORAGE_PATH = ".storage/ica.{key}.json"

_DataT = TypeVar("_DataT", default=dict[str, Any])


class CacheEntry(Generic[_DataT]):
    """Handles automatic caching for a data provider."""

    def __init__(
        self,
        hass: HomeAssistant,
        key: str,
        value_factory,
        expiry_seconds: int = CACHING_SECONDS_LONG_TERM,
        persist_to_file: bool = True,
        logger: logging.Logger = None,
    ) -> None:
        # Example: CacheEntry(hass, f"{self._config_entry.data[CONF_ICA_ID]}.baseitems")
        self._hass = hass
        self._key = key
        self._path = Path(self._hass.config.path(STORAGE_PATH.format(key=slugify(key))))
        self._file: LocalFile | None = None
        self._value: _DataT = None
        self._value_factory = value_factory
        self._logger: logging.Logger = logger or EmptyLogger()
        self._timestamp: dt.datetime | None = None
        self._expiry_seconds: int = expiry_seconds

        if persist_to_file:
            self._file = LocalFile(self._hass, self._path)

    def current_value(self) -> _DataT:
        """Gets the current value from state. Without checking file or API.
        This can be used where async/await is not possible"""
        return self._value

    async def get_value(self, invalidate_cache: bool | None = None) -> _DataT:
        """Gets value from state, file or API"""
        now = dt.datetime.now(dt.timezone.utc)

        if self._value is not None and self._file:
            # Load persisted file (if initial load)
            content = await self._file.async_load_json()
            self._logger.debug(
                "Loaded from file: %s = %s", self._path, str(content)[:100]
            )
            if (
                content
                and isinstance(content, dict)
                and content.get("timestamp")
                and content.get("key")
            ):
                # Is wrapped in CacheEntryInfo
                info: CacheEntryInfo = content
                value = info.get("value")
                if value is None or value == str(None):
                    value = None
                self._value = value
                self._timestamp = dt.datetime.fromisoformat(
                    info.get("timestamp")
                ).replace(tzinfo=dt.timezone.utc)
                self._logger.debug(
                    "Loaded cache entry: %s = %s", self._path, str(self._value)[:100]
                )
            else:
                self._value = content
                self._logger.debug(
                    "Loaded raw content: %s = %s", self._path, str(self._value)[:100]
                )

        # Auto invalidate if passed expiry
        invalidate_cache = (
            not self._timestamp
            or now > (self._timestamp + dt.timedelta(seconds=self._expiry_seconds))
            if invalidate_cache is None
            else invalidate_cache
        )

        if invalidate_cache or self._value is None:
            return await self.refresh()
        return self._value

    async def refresh(self) -> _DataT:
        """Refreshes state using the value_factory"""
        # Invoke value factory (example: API)
        value: _DataT = None
        try:
            value = await self._value_factory()
        except Exception as err:
            self._logger.error("Exception when refreshing data. Err: %s", err)
            raise
        else:
            return await self.set_value(value)

    async def set_value(self, value: _DataT) -> _DataT:
        """Sets the cached value (and persists to file)"""
        self._value = value
        self._timestamp = dt.datetime.now(dt.timezone.utc)
        self._logger.debug(
            "Persisting value in cache entry: %s = %s", self._key, str(value)[:100]
        )

        if self._file:
            # Persist new value to file
            # info = CacheEntryInfo(self._value, self._timestamp)
            info: CacheEntryInfo = {
                "timestamp": self._timestamp.isoformat(),
                "key": self._key,
                "value": self._value,
            }
            await self._file.async_store_json(info)
            self._logger.debug("Saved to file: %s = %s", self._path, str(info)[:100])
        return self._value


class CacheEntryInfo(TypedDict):
    """Cache entry metadata wrapper"""

    timestamp: str
    key: str
    value: list | dict


class LocalFile:
    """Local storage for a single To-do list."""

    def __init__(
        self, hass: HomeAssistant, path: Path, logger: logging.Logger = None
    ) -> None:
        """Initialize LocalFile."""
        self._hass = hass
        self._path = path
        self._lock = asyncio.Lock()
        self._logger: logging.Logger = logger or EmptyLogger()

    async def async_load(self) -> str:
        """Load the file from disk."""
        try:
            async with self._lock:
                return await self._hass.async_add_executor_job(self._load)
        except OSError as err:
            self._logger.warning("Failed to load cache file '%s': %s", self._path, err)
            return None

    async def async_load_json(self) -> object:
        """Loads the json-file as JSON object"""
        content = await self.async_load()
        return json.loads(content) if content else None

    def _load(self) -> str:
        """Load the json-file from disk."""
        return self._path.read_text() if self._path.exists() else ""

    async def async_store(self, content: str) -> None:
        """Persist string content to file on disk."""
        async with self._lock:
            await self._hass.async_add_executor_job(self._store, content)

    async def async_store_json(self, obj: object) -> None:
        """Persist JSON object as string content to file on disk."""
        content = json.dumps(obj) if obj else ""
        await self.async_store(content)

    def _store(self, content: str) -> None:
        """Persist string to file on disk."""
        self._path.write_text(content)
