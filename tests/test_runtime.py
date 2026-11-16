"""Safety and persistence tests with mocked Home Assistant service calls."""

from datetime import date, datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
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


@pytest.mark.asyncio
async def test_unload_cancels_every_listener(runtime):
    cancelled = []
    runtime._callbacks = [lambda: cancelled.append("tick"), lambda: cancelled.append("bus")]
    runtime._cancel_entities = lambda: cancelled.append("entities")
    runtime._rebuild_task = None

    await runtime.async_unload()

    assert sorted(cancelled) == ["bus", "entities", "tick"]
    assert runtime._cancel_entities is None
    assert runtime._callbacks == []
    assert runtime._ready is False
    # A second unload (config entry reload, shutdown race) must stay harmless.
    await runtime.async_unload()
    assert sorted(cancelled) == ["bus", "entities", "tick"]



@pytest.mark.asyncio
async def test_unload_cancels_a_running_rebuild(runtime):
    task = AsyncMock()
    task.done = lambda: False
    runtime._rebuild_task = task
    runtime._cancel_entities = None
    runtime._callbacks = []
    await runtime.async_unload()
    task.cancel.assert_called_once()
    assert runtime._rebuild_task is None



@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"lights": ["switch.a"]}, "lights"),
        ({"lights": "light.one"}, "lights"),
        ({"presence": "sensor.temperature"}, "presence"),
        ({"presence": "binary_sensor"}, "presence"),
    ],
)
async def test_configure_rejects_foreign_entities(runtime, changes, message):
    runtime.store.async_save = AsyncMock()
    runtime.request_rebuild = lambda: None
    with pytest.raises(ValueError, match=message):
        await runtime.async_configure(changes)
    runtime.store.async_save.assert_not_awaited()



def test_tick_rebuilds_after_a_time_zone_change(runtime):
    runtime.request_rebuild = MagicMock()
    runtime.request_update = MagicMock()
    runtime._context = (date(2026, 11, 13), "Europe/Berlin")
    runtime.hass.config.time_zone = "Europe/Warsaw"
    with patch(
        "custom_components.lightaway.runtime.dt_util.now",
        return_value=datetime(2026, 11, 13, 12, tzinfo=ZoneInfo("Europe/Warsaw")),
    ):
        runtime._tick(None)
    runtime.request_rebuild.assert_called_once()
    runtime.request_update.assert_not_called()



def test_tick_only_updates_when_the_context_matches(runtime):
    runtime.request_rebuild = MagicMock()
    runtime.request_update = MagicMock()
    runtime.hass.config.time_zone = "Europe/Berlin"
    runtime._context = (date(2026, 11, 13), "Europe/Berlin")
    with patch(
        "custom_components.lightaway.runtime.dt_util.now",
        return_value=datetime(2026, 11, 13, 12, tzinfo=ZoneInfo("Europe/Berlin")),
    ):
        runtime._tick(None)
    runtime.request_update.assert_called_once()
    runtime.request_rebuild.assert_not_called()



@pytest.mark.asyncio
async def test_update_never_replays_a_stale_context(runtime):
    runtime.request_rebuild = MagicMock()
    runtime._context = (date(2026, 11, 12), "Europe/Berlin")
    with patch(
        "custom_components.lightaway.runtime.dt_util.now",
        return_value=datetime(2026, 11, 13, 12, tzinfo=ZoneInfo("Europe/Berlin")),
    ):
        await runtime.async_update()
    runtime.request_rebuild.assert_called_once()
    runtime.hass.services.async_call.assert_not_awaited()



def test_registry_rename_migrates_the_selection(runtime):
    runtime.store.async_save = AsyncMock()
    runtime.hass.async_create_task = MagicMock()
    runtime._track_entities = MagicMock()
    runtime.request_rebuild = MagicMock()
    runtime.settings["lights"] = ["light.one"]
    runtime._registry_changed(
        SimpleNamespace(
            data={"action": "update", "old_entity_id": "light.one", "entity_id": "light.desk"}
        )
    )
    assert runtime.settings["lights"] == ["light.desk"]
    runtime._track_entities.assert_called_once()
    runtime.request_rebuild.assert_called_once()


@pytest.mark.asyncio
async def test_inverted_week_window_is_valid_and_persists(runtime):
    """An inverted window deliberately disables only the recent fallback."""
    runtime.store.async_save = AsyncMock()
    runtime.request_rebuild = MagicMock()
    await runtime.async_configure({"min_weeks_from_today": 9, "max_weeks_away": 2})
    assert runtime.settings["min_weeks_from_today"] == 9
    assert runtime.settings["max_weeks_away"] == 2
    runtime.store.async_save.assert_awaited_once()
    runtime.request_rebuild.assert_called_once()


@pytest.mark.asyncio
async def test_load_repairs_invalid_values_and_persists_migration(monkeypatch):
    hass = MagicMock()
    hass.config.time_zone = "Europe/Berlin"
    instance = LightAwayRuntime(hass, "migration")
    instance.store.async_load = AsyncMock(
        return_value={
            **DEFAULT_OPTIONS,
            "enabled": "off",
            "min_weeks_from_today": 53,
            "max_weeks_away": 3,
        }
    )
    instance.store.async_save = AsyncMock()
    instance.request_rebuild = lambda: None
    monkeypatch.setattr(
        "custom_components.lightaway.runtime.async_track_time_interval",
        lambda *args: lambda: None,
    )
    monkeypatch.setattr(instance, "_track_entities", lambda: None)
    await instance.async_load()
    assert instance.settings["enabled"] is False
    assert instance.settings["min_weeks_from_today"] == 1
    assert instance._repaired_settings == ["min_weeks_from_today", "enabled"]
    instance.store.async_save.assert_awaited_once_with(instance.settings)


@pytest.mark.asyncio
async def test_equal_weeks_do_not_enable_recent_history(runtime):
    from custom_components.lightaway.model import candidate_days

    from datetime import timedelta
    today = date(2026, 11, 13)
    only_year = list(candidate_days(today, max_weeks_away=4, use_recent_weeks=False))
    equal = list(candidate_days(today, max_weeks_away=4, min_weeks_from_today=4))
    assert equal == only_year
    assert today - timedelta(weeks=4) not in equal


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("setting", "value"),
    [("enabled", "yes"), ("invert", 1), ("use_recent_weeks", "false")],
)
async def test_non_boolean_config_rejected(runtime, setting, value):
    runtime.store.async_save = AsyncMock()
    with pytest.raises(ValueError):
        await runtime.async_configure({setting: value})
    runtime.store.async_save.assert_not_awaited()
