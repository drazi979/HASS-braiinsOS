"""Power target ("mining intensity") slider."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BraiinsConfigEntry
from .api import BraiinsApiError, dig, target_power
from .const import CONF_POWER_MAX, CONF_POWER_MIN
from .entity import BraiinsEntity

_LOGGER = logging.getLogger(__name__)
STEP = 100


def _round_range(lo: float, hi: float) -> tuple[int, int]:
    """Min rounded up / max rounded down to multiples of STEP."""
    return -(-int(lo) // STEP) * STEP, int(hi) // STEP * STEP


async def async_setup_entry(
    hass: HomeAssistant, entry: BraiinsConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    lo, hi, known = 500, 7000, False  # fallback range if the miner does not report one
    try:  # the miner's own limits
        c = await coordinator.client.request("GET", "configuration/constraints")
        pt = dig(c, "tuner_constraints", "power_target")
        m_lo, m_hi = dig(pt, "min", "watt"), dig(pt, "max", "watt")
        lo, hi = m_lo or lo, m_hi or hi
        known = bool(m_lo and m_hi)
    except BraiinsApiError:
        _LOGGER.debug("Could not read tuner constraints, using fallback range")
    base = _round_range(lo, hi)

    # Optional user-configured slider range (Configure button), kept inside the miner limits
    u_lo = entry.options.get(CONF_POWER_MIN)
    u_hi = entry.options.get(CONF_POWER_MAX)
    if u_lo is not None:
        lo = max(u_lo, lo) if known else u_lo
    if u_hi is not None:
        hi = min(u_hi, hi) if known else u_hi
    lo, hi = _round_range(lo, hi)
    if hi <= lo:
        _LOGGER.warning("Configured power range %s-%s W is unusable, using %s-%s W", lo, hi, *base)
        lo, hi = base
    async_add_entities([BraiinsPowerTarget(coordinator, entry, float(lo), float(hi))])


class BraiinsPowerTarget(BraiinsEntity, NumberEntity):
    _attr_name = "Power target"
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_step = STEP
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry, lo: float, hi: float) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_power_target"
        self._attr_native_min_value = lo
        self._attr_native_max_value = hi

    @property
    def native_value(self) -> float | None:
        return target_power(self.coordinator.data["tuner"])

    async def async_set_native_value(self, value: float) -> None:
        await self.async_api("PUT", "performance/power-target", {"watt": int(value)})
        await self.coordinator.async_request_refresh()
