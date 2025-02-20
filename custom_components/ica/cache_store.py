"""Local storage for cached ICA data."""

from pathlib import Path
import asyncio
import json
import logging
_LOGGER = logging.getLogger(__name__)

from homeassistant.core import HomeAssistant


class LocalFile:
    """Local storage for a single To-do list."""

    def __init__(self, hass: HomeAssistant, path: Path) -> None:
        """Initialize LocalFile."""
        self._hass = hass
        self._path = path
        self._lock = asyncio.Lock()

    async def async_load(self) -> str:
        """Load the file from disk."""
        try:
            async with self._lock:
                return await self._hass.async_add_executor_job(self._load)
        except OSError as err:
            _LOGGER.warning("Failed to load cache file '%s': %s", self._path, err)
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
        content = json.dumps(obj) if obj else ''
        await self.async_store(content)

    def _store(self, content: str) -> None:
        """Persist string to file on disk."""
        self._path.write_text(content)
