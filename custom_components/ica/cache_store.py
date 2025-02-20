"""Local storage for cached ICA data."""

import asyncio
from pathlib import Path

from homeassistant.core import HomeAssistant


class LocalFile:
    """Local storage for a single To-do list."""

    def __init__(self, hass: HomeAssistant, path: Path) -> None:
        """Initialize LocalFile."""
        self._hass = hass
        self._path = path
        self._lock = asyncio.Lock()

    async def async_load(self) -> str:
        """Load the json-file from disk."""
        async with self._lock:
            return await self._hass.async_add_executor_job(self._load)

    def _load(self) -> str:
        """Load the json-file from disk."""
        if not self._path.exists():
            return ""
        return self._path.read_text()

    async def async_store(self, content: str) -> None:
        """Persist string content to file on disk."""
        async with self._lock:
            await self._hass.async_add_executor_job(self._store, content)

    def _store(self, content: str) -> None:
        """Persist string to file on disk."""
        self._path.write_text(content)
