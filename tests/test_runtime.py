"""Safety and persistence tests with mocked Home Assistant service calls."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.lightaway.const import DEFAULT_OPTIONS
from custom_components.lightaway.runtime import LightAwayRuntime


@pytest.fixture
def runtime():
    hass = MagicMock()
    hass.states.get.return_value = SimpleNamespace(state="off")
    hass.services.async_call = AsyncMock()
    hass.config.time_zone = "Europe/Berlin"
    instance = LightAwayRuntime(hass, "test")
    instance._ready = True
    instance.settings = {
        **DEFAULT_OPTIONS,
        "presence": "input_boolean.present",
        "invert": False,
        "lights": ["light.one", "light.two"],
        "enabled": True,
    }
    instance.results = {
        light: {"desired": "on", "timeline": None, "status": "ok", "copy_day": "2025-11-14"}
        for light in instance.settings["lights"]
    }
    instance._notify = lambda: None
    return instance


@pytest.mark.asyncio
async def test_simulation_off_never_switches(runtime):
    runtime.settings["enabled"] = False
    await runtime.async_update()
    runtime.hass.services.async_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_present_never_switches(runtime):
    runtime.hass.states.get.side_effect = lambda id: SimpleNamespace(
        state="on" if id == "input_boolean.present" else "off"
    )
    await runtime.async_update()
    runtime.hass.services.async_call.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["unknown", "unavailable", None, "invalid"])
async def test_invalid_presence_blocks_switches(runtime, state):
    runtime.hass.states.get.side_effect = lambda id: (
        None
        if state is None and id == "input_boolean.present"
        else SimpleNamespace(state=state if id == "input_boolean.present" else "off")
    )
    await runtime.async_update()
    runtime.hass.services.async_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_absent_reconciles_independently(runtime):
    runtime.results["light.two"]["status"] = "light_unavailable"
    await runtime.async_update()
    runtime.hass.services.async_call.assert_awaited_once_with(
        "light", "turn_on", {"entity_id": "light.one"}, blocking=True
    )


@pytest.mark.asyncio
async def test_switch_failure_does_not_stop_other_lights(runtime):
    runtime.hass.services.async_call.side_effect = [Exception("network error"), None]
    await runtime.async_update()
    assert runtime.hass.services.async_call.await_count == 2
    assert runtime.results["light.one"]["status"] == "switch_error"


@pytest.mark.asyncio
async def test_no_redundant_commands(runtime):
    runtime.hass.states.get.side_effect = lambda id: SimpleNamespace(
        state="off" if id == "input_boolean.present" else "on"
    )
    await runtime.async_update()
    runtime.hass.services.async_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_configuration_persists(runtime):
    runtime.store.async_save = AsyncMock()
    runtime._track_entities = lambda: None
    runtime.request_rebuild = lambda: None
    runtime.settings["enabled"] = False
    await runtime.async_configure({"enabled": True})
    runtime.store.async_save.assert_awaited_once()
    assert runtime.settings["enabled"]


def test_snapshot_read_only(runtime):
    assert len(runtime.snapshot()["lights"]) == 2
    assert runtime.snapshot()["settings"]["enabled"] is True


def test_snapshot_uses_copy_day(runtime):
    result = runtime.snapshot()["lights"][0]
    assert result["copy_day"] == "2025-11-14"
    assert "original_day" not in result


def test_calculated_sensor_exposes_copy_day(runtime):
    from custom_components.lightaway.binary_sensor import LightAwayCalculated

    sensor = LightAwayCalculated(runtime, "light.one", "test_light")
    assert sensor.extra_state_attributes["copy_day"] == "2025-11-14"
    assert "original_day" not in sensor.extra_state_attributes
