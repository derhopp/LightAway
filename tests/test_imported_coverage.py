"""Verified imported history may cross HA Recorder runs only for its own entity."""

from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo
import hashlib
import json

from custom_components.lightaway.model import (
    Coverage,
    coverage_for_entity,
    local_day_bounds,
    reconstruct,
)
from custom_components.lightaway.recorder_history import RecorderHistory

ZONE = ZoneInfo("Europe/Berlin")
DAY = date(2026, 11, 15)


def fingerprint(rows):
    digest = hashlib.sha256()
    for timestamp, state in rows:
        digest.update(
            json.dumps([float(timestamp).hex(), str(state)], separators=(",", ":")).encode()
        )
        digest.update(b"\n")
    return digest.hexdigest()


def test_certified_history_only_belongs_to_the_selected_entity():
    start, end = local_day_bounds(DAY, ZONE)
    native = Coverage(start, start + timedelta(hours=5))
    imported = Coverage(
        start - timedelta(days=45),
        end + timedelta(days=1),
        entity_id="binary_sensor.present",
    )
    one = coverage_for_entity([native, imported], "binary_sensor.present")
    other = coverage_for_entity([native, imported], "binary_sensor.other")
    assert one == [imported]
    assert other == [native]
    assert coverage_for_entity([native], "binary_sensor.present") == [native]


def test_native_runs_outside_imported_range_are_preserved_without_overlap():
    start, end = local_day_bounds(DAY, ZONE)
    native = Coverage(start - timedelta(days=2), end + timedelta(days=2))
    imported = Coverage(start, end, entity_id="light.a")
    selected = coverage_for_entity([native, imported], "light.a")
    assert len(selected) == 3
    assert selected[0].end == start
    assert selected[1] == imported
    assert selected[2].start == end


class Session:
    def __init__(self, recorded):
        self.recorded = recorded

    def scalars(self, statement):
        return SimpleNamespace(all=lambda: [])

    def execute(self, statement):
        sql = str(statement)
        if "FROM states_meta" in sql:
            return SimpleNamespace(all=lambda: [("binary_sensor.present", 1)])
        if "states.last_updated_ts, states.state" in sql:
            return SimpleNamespace(all=lambda: self.recorded)
        if "states.state, states.last_updated_ts" in sql:
            return SimpleNamespace(
                first=lambda: (
                    (self.recorded[-1][1], self.recorded[-1][0]) if self.recorded else None
                )
            )
        raise AssertionError("Unexpected SQL query")


def read_with_certificate(recorded, signed_hash):
    hass = MagicMock()
    recorder = MagicMock()
    recorder.recorder_runs_manager.active = False
    history = RecorderHistory(hass)
    first, last = datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 11, 21, tzinfo=UTC)
    claim = {
        "entity_id": "binary_sensor.present",
        "start": first.timestamp(),
        "end": last.timestamp(),
        "fingerprint": signed_hash,
    }
    session = Session(recorded)
    with (
        patch("custom_components.lightaway.recorder_history.get_instance", return_value=recorder),
        patch(
            "custom_components.lightaway.recorder_history.session_scope",
            return_value=nullcontext(session),
        ),
        patch(
            "custom_components.lightaway.recorder_history.get_significant_states_with_session",
            return_value={},
        ),
    ):
        return history._read_day(DAY, ZONE, ["binary_sensor.present"], [claim])


def test_long_constant_on_is_qualified_only_with_verified_source():
    recorded = [(datetime(2026, 10, 1, tzinfo=UTC).timestamp(), "on")]
    events, runs = read_with_certificate(recorded, fingerprint(recorded))
    assert len(runs) == 1
    assert runs[0].entity_id == "binary_sensor.present"
    assert len(events["binary_sensor.present"]) == 1
    result = reconstruct(
        DAY,
        ZONE,
        events["binary_sensor.present"],
        coverage_for_entity(runs, "binary_sensor.present"),
        lambda value: value == "on",
    )
    assert result.valid
    assert result.seconds == 24 * 3600


def test_stale_certificate_fails_closed_after_purge_or_edit():
    recorded = [(datetime(2026, 10, 1, tzinfo=UTC).timestamp(), "on")]
    events, runs = read_with_certificate(recorded, fingerprint([(recorded[0][0], "off")]))
    assert not runs
    result = reconstruct(
        DAY, ZONE, events["binary_sensor.present"],
        coverage_for_entity(runs, "binary_sensor.present"),
        lambda value: value == "on",
    )
    assert not result.valid


def test_uncertified_silent_time_is_not_proved_by_a_different_entity():
    start, end = local_day_bounds(DAY, ZONE)
    only_light_cert = [Coverage(start - timedelta(days=30), end, entity_id="light.a")]
    assert coverage_for_entity(only_light_cert, "binary_sensor.present") == []
    assert not reconstruct(
        DAY,
        ZONE,
        [],
        coverage_for_entity(only_light_cert, "binary_sensor.present"),
        lambda value: value == "on",
    ).valid
