"""Local storage for cached ICA data."""

from pathlib import Path
import asyncio
import json
import logging

from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .utils import EmptyLogger

STORAGE_PATH = ".storage/ica.{key}.json"


class CacheEntry:
    def __init__(
        self,
        hass: HomeAssistant,
        key: str,
        value_factory,
        persistToFile: bool = True,
        logger: logging.Logger = None
    ) -> None:
        # Example: CacheEntry(hass, f"{self._config_entry.data[CONF_ICA_ID]}.baseitems")
        self._hass = hass
        self._key = key
        self._path = Path(self._hass.config.path(STORAGE_PATH.format(key=slugify(key))))
        self._file: LocalFile | None = None
        self._value = None
        self._value_factory = value_factory
        self._logger: logging.Logger = logger or EmptyLogger()

        if persistToFile:
            self._file = LocalFile(self._hass, self._path)

    async def get_value(self, invalidate_cache: bool = False) -> object:
        """Gets value from state, file or API"""

        if (invalidate_cache or not self._value) and self._file:
            # Load persisted file
            self._value = await self._file.async_load_json()
            self._logger.debug(
                "Loaded from file: %s = %s", self._path, self._value
            )

        if invalidate_cache or not self._value:
            # Invoke value factory (example: API)
            self._value = await self._value_factory()
            self._logger.debug("Loaded from factory: %s", self._value)

            if self._file:
                # Persist new value to file
                await self._file.async_store_json(self._value)
                self._logger.debug(
                    "Saved to file: %s = %s", self._path, self._value
                )

        return self._value


class LocalFile:
    """Local storage for a single To-do list."""

    def __init__(self, hass: HomeAssistant, path: Path,
                 logger: logging.Logger = None) -> None:
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
            self._logger.warning(
                "Failed to load cache file '%s': %s", self._path, err
            )
            return None

    async def async_load_json(self) -> object:
        """Loads the json-file as JSON object"""
        content = await self.async_load()
        result = json.loads(content) if content else None
        return result

    def _load(self) -> str:
        """Load the json-file from disk."""
        if not self._path.exists():
            return ""
        return self._path.read_text()

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
