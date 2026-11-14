"""Priority windows, shared copy dates, settings validation, and entity ownership."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.lightaway.binary_sensor import LightAwayCalculated
from custom_components.lightaway.const import DEFAULT_OPTIONS, DOMAIN
from custom_components.lightaway.model import (
    Coverage,
    TimedState,
    candidate_days,
    shift_year,
    local_day_bounds,
)
from custom_components.lightaway.runtime import LightAwayRuntime
from custom_components.lightaway.switch import LightAwaySwitch


TODAY = date(2026, 11, 13)
ZONE = ZoneInfo("Europe/Berlin")


def runtime():
    hass = MagicMock()
    hass.config.time_zone = "Europe/Berlin"
    hass.states.get.side_effect = lambda entity: SimpleNamespace(
        state="on" if entity == "binary_sensor.present" else "off"
    )
    hass.services.async_call = AsyncMock()
    instance = LightAwayRuntime(hass, "my_entry")
    instance.settings = {
        **DEFAULT_OPTIONS,
        "presence": "binary_sensor.present",
        "lights": ["light.a", "light.b"],
    }
    instance._notify = lambda: None
    instance._generation = 1
    return instance


def fake_history(valid):
    """Map dates to per-entity trustworthy 24-hour states."""
    async def day_history(day, zone, entities):
        start, end = local_day_bounds(day, zone)
        enabled = valid.get(day, ())
        events = {
            key: [TimedState(start, "on" if key == "binary_sensor.present" else "off")]
            if key in enabled else []
            for key in entities
        }
        return events, [Coverage(start, end)]

    return AsyncMock(side_effect=day_history)


async def rebuild(instance):
    with patch(
        "custom_components.lightaway.runtime.dt_util.now",
        return_value=datetime(2026, 11, 13, 18, tzinfo=ZONE),
    ):
        await instance._rebuild(instance._generation)


def test_window_bounds_and_priority():
    annual = shift_year(TODAY)
    days = list(
        candidate_days(
            TODAY, min_weeks_from_today=1, max_weeks_away=3,
            use_recent_weeks=True,
        )
    )
    yearly = [d for d in days if abs((d - annual).days) <= 21]
    assert len(yearly) >= 6
    assert all(abs((day - annual).days) <= 21 for day in yearly)
    assert days[:len(yearly)] == sorted(
        yearly, key=lambda day: (abs((day - annual).days), day)
    )
    assert days[-3:] == [TODAY - timedelta(weeks=n) for n in (1, 2, 3)]
    assert all(d.weekday() == TODAY.weekday() and d < TODAY for d in days)
    assert len(days) == len(set(days))


def test_recent_window_disabled_or_invalid_range():
    with_recent = list(candidate_days(TODAY, max_weeks_away=8))
    no_recent = list(candidate_days(TODAY, max_weeks_away=8, use_recent_weeks=False))
    invalid_range = list(
        candidate_days(TODAY, max_weeks_away=4, min_weeks_from_today=4)
    )
    assert len(with_recent) == len(no_recent) + 8
    assert len(invalid_range) == len(
        list(candidate_days(TODAY, max_weeks_away=4, use_recent_weeks=False))
    )


@pytest.mark.asyncio
async def test_anniversary_wins_over_recent_history():
    instance = runtime()
    anniversary = next(iter(candidate_days(TODAY)))
    recent = TODAY - timedelta(weeks=1)
    instance.history.async_day = fake_history({
        anniversary: {"binary_sensor.present", "light.a", "light.b"},
        recent: {"binary_sensor.present", "light.a", "light.b"},
    })
    await rebuild(instance)
    assert all(
        result["copy_day"] == anniversary.isoformat()
        for result in instance.results.values()
    )
    assert instance.history.async_day.await_count == 1


@pytest.mark.asyncio
async def test_recent_history_used_after_anniversary_window_fails():
    instance = runtime()
    recent = TODAY - timedelta(weeks=1)
    instance.history.async_day = fake_history({
        recent: {"binary_sensor.present", "light.a", "light.b"},
    })
    await rebuild(instance)
    assert all(
        result["copy_day"] == recent.isoformat()
        for result in instance.results.values()
    )
    assert instance.history.async_day.await_count > 1


@pytest.mark.asyncio
@pytest.mark.parametrize("same_day", [True, False])
async def test_shared_and_independent_dates(same_day):
    instance = runtime()
    first, second = list(candidate_days(TODAY))[:2]
    instance.settings["just_same_copy_day"] = same_day
    instance.history.async_day = fake_history({
        first: {"binary_sensor.present", "light.a"},
        second: {"binary_sensor.present", "light.a", "light.b"},
    })
    await rebuild(instance)
    assert instance.results["light.a"]["copy_day"] == (
        second if same_day else first
    ).isoformat()
    assert instance.results["light.b"]["copy_day"] == second.isoformat()


@pytest.mark.asyncio
async def test_shared_date_never_publishes_partial_matches():
    instance = runtime()
    instance.settings["just_same_copy_day"] = True
    instance.settings["use_recent_weeks"] = False
    first, second = list(candidate_days(TODAY))[:2]
    instance.history.async_day = fake_history({
        first: {"binary_sensor.present", "light.a"},
        second: {"binary_sensor.present", "light.b"},
    })
    await rebuild(instance)
    assert all(result["copy_day"] is None for result in instance.results.values())
    instance.hass.services.async_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_every_changed_option_triggers_rebuild_and_is_saved():
    instance = runtime()
    instance.store.async_save = AsyncMock()
    instance._track_entities = MagicMock()
    instance.request_rebuild = MagicMock()
    for key, value in (
        ("min_weeks_from_today", 2),
        ("max_weeks_away", 5),
        ("use_recent_weeks", False),
        ("just_same_copy_day", True),
        ("invert", True),
        ("enabled", True),
    ):
        await instance.async_configure({key: value})
    assert instance.request_rebuild.call_count == 6
    assert instance.store.async_save.await_count == 6
    instance._track_entities.assert_not_called()
    await instance.async_configure({"max_weeks_away": 5})
    assert instance.request_rebuild.call_count == 6


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("min_weeks_from_today", 0),
        ("min_weeks_from_today", 53),
        ("min_weeks_from_today", 1.5),
        ("max_weeks_away", 1),
        ("max_weeks_away", 53),
        ("max_weeks_away", True),
        ("use_recent_weeks", "false"),
        ("just_same_copy_day", 1),
    ],
)
async def test_invalid_settings_rejected(key, value):
    instance = runtime()
    instance.store.async_save = AsyncMock()
    with pytest.raises(ValueError):
        await instance.async_configure({key: value})
    instance.store.async_save.assert_not_awaited()


def test_created_entities_share_one_integration_device():
    instance = runtime()
    binary = LightAwayCalculated(instance, "light.a", "copy_a")
    switch = LightAwaySwitch(instance)
    expected = {(DOMAIN, "my_entry")}
    assert binary.device_info["identifiers"] == expected
    assert switch.device_info["identifiers"] == expected
    assert binary.unique_id == "copy_a"
    assert switch.unique_id == "my_entry_simulation"
