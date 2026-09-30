"""Shared base entity."""
from __future__ import annotations

from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BraiinsConfigEntry, BraiinsCoordinator
from .api import BraiinsApiError
from .const import DOMAIN


class BraiinsEntity(CoordinatorEntity[BraiinsCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: BraiinsCoordinator, entry: BraiinsConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title, manufacturer="Braiins", model="Braiins OS miner",
            serial_number=coordinator.data["details"].get("serial_number"),
        )

    async def async_api(self, method: str, path: str, json: Any = None) -> Any:
        """Call the miner API, turning failures into user-visible HA errors."""
        try:
            return await self.coordinator.client.request(method, path, json)
        except BraiinsApiError as err:
            raise HomeAssistantError(str(err)) from err
