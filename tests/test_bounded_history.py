"""Historical state-change streams predating HA Recorder runs.

These tests distinguish a bounded state-history inference from verified
source completeness and genuine Home Assistant Recorder uptime.
"""

from contextlib import nullcontext
from datetime import date, datetime
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


def read_day(entity, before=ON_ANCHOR, after=OFF_ANCHOR, native_runs=()):
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
            return_value={},
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
        start=start, end=start.replace(hour=12), closed_incorrect=False
    )
    events, runs = read_day(
        "binary_sensor.test_anwesenheit_2", native_runs=[native]
    )
    assert len(runs) == 1
    assert runs[0] == Coverage(start, start.replace(hour=12))
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
