"""Sparse presence and light Recorder histories survive multiple restarts."""

from contextlib import nullcontext
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.lightaway.model import (
    Coverage,
    TimedState,
    desired_state,
    local_day_bounds,
    reconstruct,
)
from custom_components.lightaway.recorder_history import RecorderHistory

ZONE = ZoneInfo("Europe/Berlin")
DAY = date(2026, 11, 9)


@pytest.mark.parametrize("entity", ["binary_sensor.present", "light.a"])
def test_months_old_state_qualifies_day_across_restart(entity):
    """A last recorded on/off state survives restart gaps, not as new events."""
    start, end = local_day_bounds(DAY, ZONE)
    old = start - timedelta(days=103)
    runs = [
        Coverage(start - timedelta(minutes=1), start + timedelta(hours=8)),
        Coverage(start + timedelta(hours=8, minutes=5), start + timedelta(hours=16)),
        Coverage(start + timedelta(hours=16, minutes=5), end),
    ]
    timeline = reconstruct(
        DAY,
        ZONE,
        [TimedState(old, "on")],
        runs,
        lambda value: (
            value == "on"
            if entity.startswith("binary_sensor")
            else value in ("on", "off")
        ),
    )
    assert timeline.valid
    assert timeline.seconds == 24 * 3600 - 10 * 60
    assert timeline.observed_seconds == timeline.seconds
    assert [event.at for event in timeline.transitions] == [
        start,
        start + timedelta(hours=8, minutes=5),
        start + timedelta(hours=16, minutes=5),
    ]
    assert (
        desired_state(timeline, datetime(2026, 11, 23, 18, tzinfo=ZONE), ZONE)
        == "on"
    )


def test_old_off_light_state_and_midday_switch_are_replayed():
    start, end = local_day_bounds(DAY, ZONE)
    morning = start + timedelta(hours=9)
    runs = [
        Coverage(start, start + timedelta(hours=4)),
        Coverage(start + timedelta(hours=4, minutes=5), end),
    ]
    timeline = reconstruct(
        DAY,
        ZONE,
        [TimedState(start - timedelta(days=150), "off"), TimedState(morning, "on")],
        runs,
        lambda value: value in ("on", "off"),
    )
    assert timeline.valid
    assert [row.value for row in timeline.transitions] == ["off", "off", "on"]
    assert (
        desired_state(timeline, datetime(2026, 11, 23, 8, tzinfo=ZONE), ZONE)
        == "off"
    )
    assert (
        desired_state(timeline, datetime(2026, 11, 23, 18, tzinfo=ZONE), ZONE)
        == "on"
    )


def test_long_recording_outage_does_not_qualify_a_day():
    start, end = local_day_bounds(DAY, ZONE)
    timeline = reconstruct(
        DAY,
        ZONE,
        [TimedState(start - timedelta(days=150), "on")],
        [
            Coverage(start, start + timedelta(hours=11)),
            Coverage(start + timedelta(hours=14), end),
        ],
        lambda value: value == "on",
    )
    assert timeline.seconds == 21 * 3600
    assert not timeline.valid


def test_unavailable_is_not_promoted_to_valid_by_restart():
    start, end = local_day_bounds(DAY, ZONE)
    timeline = reconstruct(
        DAY,
        ZONE,
        [TimedState(start - timedelta(days=90), "unavailable")],
        [
            Coverage(start, start + timedelta(hours=8)),
            Coverage(start + timedelta(hours=8), end),
        ],
        lambda value: value in ("on", "off"),
    )
    assert timeline.seconds == 0
    assert not timeline.valid


def test_absent_state_anchor_does_not_invent_entity_history():
    start, end = local_day_bounds(DAY, ZONE)
    timeline = reconstruct(
        DAY,
        ZONE,
        [],
        [Coverage(start, end)],
        lambda value: value in ("on", "off"),
    )
    assert timeline.seconds == 0
    assert timeline.transitions == ()


@pytest.mark.parametrize("entity", ["binary_sensor.present", "light.a"])
def test_recorder_reader_fetches_pre_restart_anchor_for_both_types(entity):
    """Regression: no run.start lower bound in the last-state SQL query."""
    start, end = local_day_bounds(DAY, ZONE)
    old = start - timedelta(days=103)

    class FakeSession:
        def scalars(self, statement):
            return SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        start=start - timedelta(minutes=1),
                        end=end,
                        closed_incorrect=False,
                    )
                ]
            )

        def execute(self, statement):
            sql = str(statement)
            if "FROM states_meta" in sql:
                return SimpleNamespace(all=lambda: [(entity, 1)])
            if "states.state, states.last_updated_ts" in sql:
                # The key regression: the query must allow states older
                # than the current Recorder run.
                assert "states.last_updated_ts >=" not in sql
                return SimpleNamespace(first=lambda: ("on", old.timestamp()))
            raise AssertionError(f"Unexpected SQL: {sql}")

    hass = MagicMock()
    recorder = MagicMock()
    recorder.recorder_runs_manager.active = False
    reader = RecorderHistory(hass)
    with (
        patch(
            "custom_components.lightaway.recorder_history.get_instance",
            return_value=recorder,
        ),
        patch(
            "custom_components.lightaway.recorder_history.session_scope",
            return_value=nullcontext(FakeSession()),
        ),
        patch(
            "custom_components.lightaway.recorder_history.get_significant_states_with_session",
            return_value={},
        ),
    ):
        events, runs = reader._read_day(DAY, ZONE, [entity])
    assert events[entity] == [TimedState(old, "on")]
    assert len(runs) == 1
    assert reconstruct(
        DAY, ZONE, events[entity], runs, lambda value: value == "on"
    ).valid
