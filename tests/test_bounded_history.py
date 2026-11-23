"""Historical state-change streams predating HA Recorder runs.

These tests distinguish a bounded state-history inference from verified
source completeness and genuine Home Assistant Recorder uptime.
"""

from contextlib import nullcontext
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.lightaway.model import (
    Coverage,
    coverage_for_entity,
    local_day_bounds,
    reconstruct,
)
from custom_components.lightaway.recorder_history import RecorderHistory

ZONE = ZoneInfo("Europe/Berlin")
DAY = date(2025, 11, 24)
ON_ANCHOR = datetime(2025, 11, 12, tzinfo=ZONE)
OFF_ANCHOR = datetime(2026, 3, 24, 14, 1, 16, tzinfo=ZONE)


class FakeSession:
    def __init__(self, entity, before, after, native_runs=()):
        self.entity = entity
        self.before = before
        self.after = after
        self.native_runs = native_runs

    def scalars(self, query):
        return SimpleNamespace(all=lambda: list(self.native_runs))

    def execute(self, query):
        sql = str(query)
        if "FROM states_meta" in sql:
            return SimpleNamespace(all=lambda: [(self.entity, 1)])
        if "states.state, states.last_updated_ts" in sql:
            return SimpleNamespace(
                first=lambda: ("on", self.before.timestamp())
                if self.before is not None
                else None
            )
        if "states.last_updated_ts" in sql and "states.state" not in sql:
            timestamp = self.before if " DESC" in sql else self.after
            return SimpleNamespace(
                scalar_one_or_none=lambda: timestamp.timestamp()
                if timestamp is not None
                else None
            )
        raise AssertionError(f"Unexpected SQL statement: {sql}")


def read_day(entity, before=ON_ANCHOR, after=OFF_ANCHOR, native_runs=(), in_day=()):
    session = FakeSession(entity, before, after, native_runs)
    recorder = MagicMock()
    recorder.recorder_runs_manager.active = False
    reader = RecorderHistory(MagicMock())
    with (
        patch(
            "custom_components.lightaway.recorder_history.get_instance",
            return_value=recorder,
        ),
        patch(
            "custom_components.lightaway.recorder_history.session_scope",
            return_value=nullcontext(session),
        ),
        patch(
            "custom_components.lightaway.recorder_history.get_significant_states_with_session",
            return_value={
                entity: [
                    SimpleNamespace(last_updated=when, state=value)
                    for when, value in in_day
                ]
            },
        ),
    ):
        return reader._read_day(DAY, ZONE, [entity])


@pytest.mark.parametrize(
    "entity", ["binary_sensor.test_anwesenheit_2", "light.testlicht_gaste_wc_spots"]
)
def test_year_old_state_history_qualifies_same_weekday(entity):
    events, runs = read_day(entity)
    assert len(runs) == 1
    assert runs[0].entity_id == entity
    assert runs[0].source == "bounded_state_history"
    assert events[entity][0].value == "on"
    result = reconstruct(
        DAY,
        ZONE,
        events[entity],
        coverage_for_entity(runs, entity),
        lambda value: value == "on",
    )
    assert result.valid
    assert result.seconds == 24 * 3600


@pytest.mark.parametrize(
    "before,after",
    [
        (None, OFF_ANCHOR),
        (ON_ANCHOR, None),
        (None, None),
    ],
)
def test_missing_first_or_later_boundary_is_not_inferred(before, after):
    events, runs = read_day(
        "binary_sensor.test_anwesenheit_2", before=before, after=after
    )
    assert not runs
    assert not events["binary_sensor.test_anwesenheit_2"]


def test_existing_recorder_gap_is_not_replaced_with_inferred_whole_day():
    start, end = local_day_bounds(DAY, ZONE)
    native = SimpleNamespace(
        start=start, end=start + timedelta(hours=12), closed_incorrect=False
    )
    events, runs = read_day(
        "binary_sensor.test_anwesenheit_2", native_runs=[native]
    )
    assert len(runs) == 1
    assert runs[0] == Coverage(start, start + timedelta(hours=12))
    result = reconstruct(
        DAY, ZONE, events["binary_sensor.test_anwesenheit_2"], runs,
        lambda value: value == "on",
    )
    assert not result.valid
    assert result.seconds == 12 * 3600


def test_no_borrowed_coverage_across_entities():
    start, end = local_day_bounds(DAY, ZONE)
    light = Coverage(start, end, entity_id="light.testlicht_a", source="bounded_state_history")
    assert coverage_for_entity([light], "binary_sensor.test_anwesenheit_2") == []


def test_invalid_inferred_state_does_not_qualify():
    start, end = local_day_bounds(DAY, ZONE)
    runs = [Coverage(start, end, entity_id="binary_sensor.test_anwesenheit_2",
                     source="bounded_state_history")]
    result = reconstruct(
        DAY, ZONE, [],
        coverage_for_entity(runs, "binary_sensor.test_anwesenheit_2"),
        lambda value: value == "on",
    )
    assert not result.valid
    assert result.seconds == 0


@pytest.mark.parametrize(
    "entity,changes",
    [
        (
            "light.testlicht_gaste_wc_spots",
            [(7, 56, "on"), (7, 59, "off"), (17, 7, "on"), (17, 12, "off")],
        ),
        (
            "light.testlicht_bad_spots",
            [(6, 45, "on"), (7, 16, "off"), (8, 50, "on"), (8, 54, "off")],
        ),
    ],
)
def test_old_light_switches_are_replayed_on_2025_11_24(entity, changes):
    """Actual in-day transitions are retained, not merely constant states."""
    source_events = [
        (datetime(2025, 11, 24, hour, minute, tzinfo=ZONE), value)
        for hour, minute, value in changes
    ]
    events, runs = read_day(
        entity,
        before=datetime(2025, 11, 8, 6, tzinfo=ZONE),
        after=datetime(2025, 12, 1, 6, tzinfo=ZONE),
        in_day=source_events,
    )
    result = reconstruct(
        DAY, ZONE, events[entity], coverage_for_entity(runs, entity),
        lambda value: value in ("on", "off"),
    )
    assert result.valid
    assert [item.value for item in result.transitions] == [
        "on", "on", "off", "on", "off"
    ]
