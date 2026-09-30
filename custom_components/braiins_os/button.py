"""Reboot button."""
from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BraiinsConfigEntry
from .entity import BraiinsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: BraiinsConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([BraiinsRebootButton(entry.runtime_data, entry)])


class BraiinsRebootButton(BraiinsEntity, ButtonEntity):
    _attr_name = "Reboot"
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_reboot"

    async def async_press(self) -> None:
        await self.async_api("PUT", "actions/reboot")
