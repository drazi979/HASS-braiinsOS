"""Power target ("mining intensity") control."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BraiinsConfigEntry
from .api import BraiinsApiError, dig
from .entity import BraiinsEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: BraiinsConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    lo, hi = 500, 7000  # fallback range; the miner enforces its own limits
    try:  # try to read the real range from the miner
        c = await coordinator.client.request("GET", "configuration/constraints")
        pt = dig(c, "tuner_constraints", "power_target")
        lo = dig(pt, "min", "watt") or lo
        hi = dig(pt, "max", "watt") or hi
    except BraiinsApiError:
        _LOGGER.debug("Could not read tuner constraints, using fallback range")
    lo = -(-int(lo) // 100) * 100  # round the minimum up to a multiple of 100
    hi = int(hi) // 100 * 100  # round the maximum down to a multiple of 100
    async_add_entities([BraiinsPowerTarget(coordinator, entry, float(lo), float(hi))])


class BraiinsPowerTarget(BraiinsEntity, NumberEntity):
    _attr_name = "Power target"
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_step = 100
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, entry, lo: float, hi: float) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_power_target"
        self._attr_native_min_value = lo
        self._attr_native_max_value = hi

    @property
    def native_value(self) -> float | None:
        return dig(self.coordinator.data["tuner"], "mode_state", "powertargetmodestate",
                   "current_target", "watt")

    async def async_set_native_value(self, value: float) -> None:
        await self.async_api("PUT", "performance/power-target", {"watt": int(value)})
        await self.coordinator.async_request_refresh()
