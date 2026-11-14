"""Backend rebuild integration tests with a deterministic, mocked recorder."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.lightaway.model import Coverage, TimedState, candidate_days, local_day_bounds
from custom_components.lightaway.runtime import LightAwayRuntime


def fake_runtime():
    hass = MagicMock()
    hass.config.time_zone = "Europe/Berlin"
    hass.states.get.side_effect = lambda name: SimpleNamespace(
        state="on" if name == "binary_sensor.present" else "off"
    )
    hass.services.async_call = AsyncMock()
    rt = LightAwayRuntime(hass, "test")
    rt._notify = lambda: None
    rt.settings = {
        "presence": "binary_sensor.present",
        "invert": False,
        "lights": ["light.a", "light.b"],
        "enabled": False,
    }
    rt._generation = 1
    return rt


@pytest.mark.asyncio
async def test_independent_reference_days_and_calculated_states():
    today = date(2026, 11, 13)
    candidates = list(candidate_days(today))
    rt = fake_runtime()

    async def history(day, zone, entities):
        start, end = local_day_bounds(day, zone)
        events = {
            "binary_sensor.present": [TimedState(start, "on")],
            "light.a": [TimedState(start, "off")],
            "light.b": ([] if day == candidates[0] else [TimedState(start, "on")]),
        }
        return {key: events.get(key, []) for key in entities}, [Coverage(start, end)]

    rt.history.async_day = AsyncMock(side_effect=history)
    with patch(
        "custom_components.lightaway.runtime.dt_util.now",
        return_value=datetime(2026, 11, 13, 18, tzinfo=ZoneInfo("Europe/Berlin")),
    ):
        await rt._rebuild(1)
    assert rt._ready
    assert rt.results["light.a"]["copy_day"] == candidates[0].isoformat()
    assert rt.results["light.b"]["copy_day"] == candidates[1].isoformat()
    assert rt.results["light.a"]["desired"] == "off"
    assert rt.results["light.b"]["desired"] == "on"
    rt.hass.services.async_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_recorder_cannot_produce_control_requests():
    rt = fake_runtime()
    rt.settings["enabled"] = True
    rt.history.async_day = AsyncMock(side_effect=RuntimeError("offline"))
    with patch(
        "custom_components.lightaway.runtime.dt_util.now",
        return_value=datetime(2026, 11, 13, 18, tzinfo=ZoneInfo("Europe/Berlin")),
    ):
        await rt._rebuild(1)
    assert all(item["desired"] is None for item in rt.results.values())
    assert all(item["status"] == "recorder_unavailable" for item in rt.results.values())
    rt.hass.services.async_call.assert_not_awaited()
