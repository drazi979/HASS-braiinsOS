"""Braiins OS integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL, CONF_USERNAME, Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BraiinsApiError, BraiinsAuthError, BraiinsClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.SWITCH, Platform.BUTTON]
_LOGGER = logging.getLogger(__name__)

type BraiinsConfigEntry = ConfigEntry[BraiinsCoordinator]


class BraiinsCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry: BraiinsConfigEntry) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.client = BraiinsClient(
            async_get_clientsession(hass),
            entry.data[CONF_HOST], entry.data[CONF_PORT],
            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD],
        )

    async def _optional(self, path: str):
        """Fetch a secondary endpoint; a failure (e.g. 412 while paused) is not fatal."""
        try:
            return await self.client.request("GET", path)
        except BraiinsAuthError:
            raise
        except BraiinsApiError as err:
            _LOGGER.debug("Optional endpoint %s failed: %s", path, err)
            return None

    async def _async_update_data(self) -> dict:
        try:
            # miner/details must work: if it fails the miner is unreachable.
            details = await self.client.request("GET", "miner/details")
            stats, boards, tuner, pools = await asyncio.gather(
                self._optional("miner/stats"),
                self._optional("miner/hw/hashboards"),
                self._optional("performance/tuner-state"),
                self._optional("pools/"),
            )
        except BraiinsAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except BraiinsApiError as err:
            raise UpdateFailed(str(err)) from err
        return {
            "details": details or {},
            "stats": stats or {},
            "boards": (boards or {}).get("hashboards", []),
            "tuner": tuner or {},
            "pools": pools if isinstance(pools, list) else [],
        }


async def async_setup_entry(hass: HomeAssistant, entry: BraiinsConfigEntry) -> bool:
    coordinator = BraiinsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def _options_updated(hass: HomeAssistant, entry: BraiinsConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BraiinsConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
