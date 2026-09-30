"""Pause / resume mining."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BraiinsConfigEntry
from .entity import BraiinsEntity
from .sensor import miner_status


async def async_setup_entry(
    hass: HomeAssistant, entry: BraiinsConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([BraiinsMiningSwitch(entry.runtime_data, entry)])


class BraiinsMiningSwitch(BraiinsEntity, SwitchEntity):
    _attr_name = "Mining"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_mining"

    @property
    def is_on(self) -> bool | None:
        status = miner_status(self.coordinator.data["details"])
        return None if status is None else status == "normal"

    async def async_turn_on(self, **kwargs) -> None:
        await self.async_api("PUT", "actions/resume")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.async_api("PUT", "actions/pause")
        await self.coordinator.async_request_refresh()
