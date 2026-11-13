"""Further regression tests around Recorder overlap and DST time mapping."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from custom_components.lightaway.model import (
    Coverage,
    TimedState,
    desired_state,
    local_day_bounds,
    reconstruct,
)


ZONE = ZoneInfo("Europe/Berlin")


def test_overlapping_recorder_runs_cannot_overcount_coverage():
    day = date(2025, 11, 13)
    start, end = local_day_bounds(day, ZONE)
    events = [TimedState(start, "on")]
    runs = [
        Coverage(start, start + timedelta(hours=12)),
        Coverage(start + timedelta(hours=11), end),
    ]
    result = reconstruct(day, ZONE, events, runs, lambda value: value == "on")
    assert result.seconds == 12 * 3600
    assert not result.valid


def test_spring_forward_missing_hour_does_not_create_spurious_transition():
    day = date(2026, 3, 29)
    start, end = local_day_bounds(day, ZONE)
    before = datetime(2026, 3, 29, 1, 30, tzinfo=ZONE).astimezone(UTC)
    after = datetime(2026, 3, 29, 3, 30, tzinfo=ZONE).astimezone(UTC)
    timeline = reconstruct(
        day,
        ZONE,
        [TimedState(start, "off"), TimedState(before, "on"), TimedState(after, "off")],
        [Coverage(start, end)],
        lambda value: value in ("on", "off"),
    )
    assert desired_state(timeline, datetime(2027, 3, 29, 3, 0, tzinfo=ZONE), ZONE) == "on"
    assert desired_state(timeline, datetime(2027, 3, 29, 4, 0, tzinfo=ZONE), ZONE) == "off"
