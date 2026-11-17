"""Regression tests for weekly copy dates and Recorder seed provenance.

A real state recorded a week before the copy date can establish the initial
state, but it must not replace the selected day's light transitions.
"""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.lightaway.const import DEFAULT_OPTIONS
from custom_components.lightaway.model import (
    Coverage,
    TimedState,
    candidate_days,
    desired_state,
    local_day_bounds,
    reconstruct,
)
from custom_components.lightaway.runtime import LightAwayRuntime, _record_provenance

ZONE = ZoneInfo("Europe/Berlin")


def make_runtime():
    hass = MagicMock()
    hass.config.time_zone = "Europe/Berlin"
    hass.states.get.side_effect = lambda entity: SimpleNamespace(
        state="on" if entity == "binary_sensor.present" else "off"
    )
    hass.services.async_call = AsyncMock()
    instance = LightAwayRuntime(hass, "weekly")
    instance._notify = lambda: None
    instance.settings = {
        **DEFAULT_OPTIONS,
        "presence": "binary_sensor.present",
        "lights": ["light.a", "light.b"],
        "use_recent_weeks": True,
        "min_weeks_from_today": 1,
        "max_weeks_away": 8,
        "enabled": False,
    }
    instance._generation = 1
    return instance


@pytest.mark.parametrize(
    ("today", "copy_date", "older"),
    [
        (date(2026, 11, 16), date(2026, 11, 9), date(2026, 11, 2)),
        (date(2026, 11, 17), date(2026, 11, 10), date(2026, 11, 3)),
    ],
)
def test_one_week_is_exactly_seven_days(today, copy_date, older):
    dates = list(candidate_days(today))
    assert copy_date in dates
    assert dates.index(copy_date) < dates.index(older)
    assert today - copy_date == timedelta(days=7)
    assert copy_date.weekday() == today.weekday()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("today", "copy_date", "older"),
    [
        (date(2026, 11, 16), date(2026, 11, 9), date(2026, 11, 2)),
        (date(2026, 11, 17), date(2026, 11, 10), date(2026, 11, 3)),
    ],
)
@pytest.mark.parametrize("shared", [False, True])
async def test_week_one_selected_and_replayed_even_if_week_two_has_gap(
    today, copy_date, older, shared
):
    """The prior week's seed may carry into the selected day, not its events."""
    runtime = make_runtime()
    runtime.settings["just_same_copy_day"] = shared
    requested = []

    async def history(day, zone, entities):
        requested.append(day)
        start, end = local_day_bounds(day, zone)
        if day != copy_date:
            # No usable year-old history and a gap on the older recent day.
            return {entity: [] for entity in entities}, []

        # The last true state sample is one week older; the Recorder run is
        # continuous and a valid local-day start can be reconstructed.
        seed_time = start - timedelta(days=7)
        morning = start + timedelta(hours=8)
        evening = start + timedelta(hours=18)
        events = {
            "binary_sensor.present": [TimedState(seed_time, "on")],
            "light.a": [
                TimedState(seed_time, "off"),
                TimedState(morning, "on"),
                TimedState(evening, "off"),
            ],
            "light.b": [
                TimedState(seed_time, "on"),
                TimedState(morning, "off"),
                TimedState(evening, "on"),
            ],
        }
        return (
            {entity: events.get(entity, []) for entity in entities},
            [Coverage(seed_time - timedelta(hours=1), end)],
        )

    runtime.history.async_day = AsyncMock(side_effect=history)
    now = datetime.combine(today, datetime.min.time(), ZONE).replace(hour=9)
    with patch("custom_components.lightaway.runtime.dt_util.now", return_value=now):
        await runtime._rebuild(runtime._generation)

    assert older not in requested
    assert runtime._ready
    assert all(result["copy_day"] == copy_date.isoformat() for result in runtime.results.values())
    assert runtime.results["light.a"]["desired"] == "on"
    assert runtime.results["light.b"]["desired"] == "off"
    runtime.hass.services.async_call.assert_not_awaited()

    for light in ("light.a", "light.b"):
        result = runtime.results[light]
        assert result["status"] == "ok"
        assert result["in_day_records"] == 2
        assert result["carried_state_recorded_at"] is not None
        start, end = local_day_bounds(copy_date, ZONE)
        # The seed is represented at copy-day midnight, never at the
        # week-old timestamp and never as a week-old state transition.
        assert all(start <= event.at < end for event in result["timeline"].transitions)
        assert result["timeline"].transitions[0].at == start

    diagnostics = runtime.diagnostics()
    winner = next(candidate for candidate in diagnostics["candidates"] if candidate["day"] == copy_date.isoformat())
    assert winner["lights"]["light.a"]["in_day_records"] == 2
    assert winner["lights"]["light.a"]["carried_state_recorded_at"] is not None


@pytest.mark.parametrize(
    ("utc_now", "expected_date"),
    [
        (datetime(2026, 11, 16, 22, 30, tzinfo=UTC), date(2026, 11, 16)),
        (datetime(2026, 11, 16, 23, 30, tzinfo=UTC), date(2026, 11, 17)),
    ],
)
def test_configured_timezone_controls_current_day(utc_now, expected_date):
    runtime = make_runtime()
    with patch("custom_components.lightaway.runtime.dt_util.now", return_value=utc_now):
        assert runtime._context_of()[0] == expected_date


def test_prior_week_sample_only_seeds_target_day():
    copy_date = date(2026, 11, 10)
    start, end = local_day_bounds(copy_date, ZONE)
    seed = start - timedelta(days=7)
    morning = start + timedelta(hours=8)
    evening = start + timedelta(hours=18)
    samples = [
        TimedState(seed, "off"),
        TimedState(morning, "on"),
        TimedState(evening, "off"),
    ]
    timeline = reconstruct(
        copy_date,
        ZONE,
        samples,
        [Coverage(seed - timedelta(hours=1), end)],
        lambda state: state in ("on", "off"),
    )
    assert timeline.valid
    assert timeline.seconds == 24 * 3600
    assert [sample.at for sample in timeline.transitions] == [start, morning, evening]
    assert desired_state(timeline, datetime(2026, 11, 17, 9, tzinfo=ZONE), ZONE) == "on"
    assert desired_state(timeline, datetime(2026, 11, 17, 19, tzinfo=ZONE), ZONE) == "off"
    provenance = _record_provenance(copy_date, ZONE, samples)
    assert provenance["in_day_records"] == 2
    assert provenance["carried_state_recorded_at"] == seed.isoformat()


def test_a_gap_on_target_day_is_not_rescued_by_last_week_seed():
    copy_date = date(2026, 11, 9)
    start, end = local_day_bounds(copy_date, ZONE)
    seed = start - timedelta(days=7)
    result = reconstruct(
        copy_date,
        ZONE,
        [TimedState(seed, "on")],
        [
            Coverage(seed, start + timedelta(hours=10)),
            Coverage(start + timedelta(hours=12), end),
        ],
        lambda state: state == "on",
    )
    assert result.seconds == 10 * 3600
    assert not result.valid
