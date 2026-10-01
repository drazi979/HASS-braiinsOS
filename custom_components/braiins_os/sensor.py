"""Sensors for Braiins OS."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass,
)
from homeassistant.const import UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BraiinsConfigEntry
from .api import dig
from .entity import BraiinsEntity

STATUSES = ["unspecified", "not_started", "normal", "paused", "suspended", "restricted"]


def miner_status(details: dict) -> str | None:
    """Normalise the `status` field (enum int or string) to a name in STATUSES."""
    raw = details.get("status")
    if isinstance(raw, int) and 0 <= raw < len(STATUSES):
        return STATUSES[raw]
    if isinstance(raw, str):
        name = raw.lower().removeprefix("miner_status_")
        return name if name in STATUSES else None
    return None


# overall_tuner_state. Names per Braiins Public API docs; 2 = stable is confirmed on a
# live miner. 5/6 (continuous, preheat) are assumed from the order they were added to the
# API (1.9.0, 1.11.0); the raw_value attribute on the sensor lets you verify them.
TUNER_STATES = {
    0: "unspecified", 1: "disabled", 2: "stable", 3: "tuning", 4: "error",
    5: "continuous", 6: "preheat",
}


def _tuner_state(data: dict) -> str | None:
    raw = data["tuner"].get("overall_tuner_state")
    if isinstance(raw, int):
        return TUNER_STATES.get(raw, f"state_{raw}")
    if isinstance(raw, str):
        return raw.lower().removeprefix("tuner_state_")
    return None


def _hashrate(data: dict) -> float | None:
    gh = dig(data["stats"], "miner_stats", "real_hashrate", "last_1m", "gigahash_per_second")
    return round(gh / 1000, 2) if isinstance(gh, (int, float)) else None


def _power(data: dict) -> float | None:
    return dig(data["stats"], "power_stats", "approximated_consumption", "watt")


def _efficiency(data: dict) -> float | None:
    hr, pw = _hashrate(data), _power(data)
    if isinstance(hr, (int, float)) and isinstance(pw, (int, float)) and hr > 0:
        return round(pw / hr, 1)
    return None


def _temp(obj: Any) -> float | None:
    """Read a temperature object; chip temps nest the value under 'temperature'."""
    v = dig(obj, "degree_c")
    if v is None:
        v = dig(obj, "temperature", "degree_c")
    return v if isinstance(v, (int, float)) else None


def _board_temp(field: str, agg: Callable) -> Callable[[dict], float | None]:
    def fn(data: dict) -> float | None:
        vals = [v for b in data["boards"] if (v := _temp(b.get(field))) is not None]
        return round(agg(vals), 1) if vals else None
    return fn


def _pool_sum(field: str) -> Callable[[dict], int | None]:
    def fn(data: dict) -> int | None:
        vals = [
            v for g in data["pools"] if isinstance(g, dict)
            for p in g.get("pools", []) if isinstance(v := dig(p, "stats", field), (int, float))
        ]
        return int(sum(vals)) if vals else None
    return fn


@dataclass(frozen=True, kw_only=True)
class BraiinsSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]
    raw_fn: Callable[[dict], Any] | None = None


TEMP = dict(
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
)
POWER = dict(
    device_class=SensorDeviceClass.POWER,
    native_unit_of_measurement=UnitOfPower.WATT,
    state_class=SensorStateClass.MEASUREMENT,
)

SENSORS = (
    BraiinsSensorDescription(
        key="status", name="Status", device_class=SensorDeviceClass.ENUM, options=STATUSES,
        value_fn=lambda d: miner_status(d["details"]),
        raw_fn=lambda d: d["details"].get("status")),
    BraiinsSensorDescription(
        key="tuner_status", name="Tuner status", value_fn=_tuner_state,
        raw_fn=lambda d: d["tuner"].get("overall_tuner_state")),
    BraiinsSensorDescription(
        key="hashrate", name="Hashrate", native_unit_of_measurement="TH/s",
        state_class=SensorStateClass.MEASUREMENT, value_fn=_hashrate),
    BraiinsSensorDescription(key="power", name="Power", value_fn=_power, **POWER),
    BraiinsSensorDescription(
        key="power_limit", name="Power limit",
        value_fn=lambda d: dig(d["tuner"], "mode_state", "powertargetmodestate", "current_target", "watt"),
        **POWER),
    BraiinsSensorDescription(
        key="efficiency", name="Efficiency", native_unit_of_measurement="J/TH",
        state_class=SensorStateClass.MEASUREMENT, value_fn=_efficiency),
    BraiinsSensorDescription(
        key="water_in", name="Water inlet temperature",
        value_fn=_board_temp("lowest_water_inlet_temp", min), **TEMP),
    BraiinsSensorDescription(
        key="water_out", name="Water outlet temperature",
        value_fn=_board_temp("highest_water_outlet_temp", max), **TEMP),
    BraiinsSensorDescription(
        key="chip_temp", name="Chip temperature",
        value_fn=_board_temp("highest_chip_temp", max), **TEMP),
    BraiinsSensorDescription(
        key="accepted_shares", name="Accepted shares",
        state_class=SensorStateClass.TOTAL_INCREASING, value_fn=_pool_sum("accepted_shares")),
    BraiinsSensorDescription(
        key="rejected_shares", name="Rejected shares",
        state_class=SensorStateClass.TOTAL_INCREASING, value_fn=_pool_sum("rejected_shares")),
)

BOARD_SENSORS = (
    ("chip", "chip temperature", "highest_chip_temp"),
    ("water_in", "water inlet temperature", "lowest_water_inlet_temp"),
    ("water_out", "water outlet temperature", "highest_water_outlet_temp"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: BraiinsConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(BraiinsSensor(coordinator, entry, d) for d in SENSORS)

    known: set[str] = set()

    @callback
    def _add_boards() -> None:
        new = []
        for board in coordinator.data["boards"]:
            board_id = str(board.get("id"))
            if board_id in known:
                continue
            known.add(board_id)
            new += [BraiinsBoardSensor(coordinator, entry, board_id, *spec) for spec in BOARD_SENSORS]
        if new:
            async_add_entities(new)

    _add_boards()
    entry.async_on_unload(coordinator.async_add_listener(_add_boards))


class BraiinsSensor(BraiinsEntity, SensorEntity):
    entity_description: BraiinsSensorDescription

    def __init__(self, coordinator, entry, description) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        fn = self.entity_description.raw_fn
        return {"raw_value": fn(self.coordinator.data)} if fn else None


class BraiinsBoardSensor(BraiinsEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry, board_id: str, key: str, label: str, field: str) -> None:
        super().__init__(coordinator, entry)
        self._board_id = board_id
        self._field = field
        self._attr_name = f"Board {board_id} {label}"
        self._attr_unique_id = f"{entry.entry_id}_board_{board_id}_{key}"

    @property
    def native_value(self):
        for board in self.coordinator.data["boards"]:
            if str(board.get("id")) == self._board_id:
                return _temp(board.get(self._field))
        return None
