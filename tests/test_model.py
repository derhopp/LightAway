"""Time-zone, reconstruction, selection and replay unit tests."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.lightaway.model import (
    Coverage,
    TimedState,
    candidate_days,
    desired_state,
    first_qualified,
    local_day_bounds,
    normalize_presence,
    previous_month,
    reconstruct,
    shift_year,
)

BERLIN = ZoneInfo("Europe/Berlin")


def row(day, hour, value, zone=BERLIN, fold=0):
    return TimedState(
        datetime.combine(day, datetime.min.time(), zone)
        .replace(hour=hour, fold=fold)
        .astimezone(UTC),
        value,
    )


@pytest.mark.parametrize(
    ("value", "normal", "inverted"),
    [
        ("on", True, False),
        ("true", True, False),
        ("1", True, False),
        ("off", False, True),
        ("false", False, True),
        ("0", False, True),
        ("unknown", None, None),
        ("unavailable", None, None),
        ("bogus", None, None),
        (None, None, None),
    ],
)
def test_presence(value, normal, inverted):
    assert normalize_presence(value) is normal
    assert normalize_presence(value, True) is inverted


def test_ideal_day_and_search_steps():
    assert shift_year(date(2024, 2, 29)) == date(2023, 2, 28)
    assert shift_year(date(2026, 1, 1)) == date(2025, 1, 1)
    assert previous_month(date(2026, 3, 31)) == date(2026, 2, 28)
    today = date(2026, 11, 13)
    ideal = shift_year(today)
    days = list(candidate_days(today))
    yearly = [day for day in days if abs((day - ideal).days) <= 56]
    assert yearly
    assert all(day.weekday() == today.weekday() for day in days)
    assert all(day < today for day in days)
    assert yearly[0] == min(yearly, key=lambda day: (abs((day - ideal).days), day))
    assert days[-1] == today - timedelta(weeks=8)
    assert len(days) == len(set(days))


def test_day_lengths():
    for day, hours in [(date(2026, 3, 29), 23), (date(2026, 10, 25), 25), (date(2026, 3, 28), 24)]:
        start, end = local_day_bounds(day, BERLIN)
        assert (end - start).total_seconds() == hours * 3600


def test_fully_evidenced_silent_day():
    day = date(2025, 11, 14)
    start, end = local_day_bounds(day, BERLIN)
    events = [TimedState(start - timedelta(minutes=30), "on")]
    runs = [Coverage(start - timedelta(hours=3), end + timedelta(hours=1))]
    result = reconstruct(day, BERLIN, events, runs, lambda state: state == "on")
    assert result.seconds == 86400
    assert result.valid


def test_without_seed_is_not_proven():
    day = date(2025, 11, 14)
    start, end = local_day_bounds(day, BERLIN)
    result = reconstruct(day, BERLIN, [], [Coverage(start, end)], lambda s: True)
    assert result.seconds == 0
    assert not result.valid


def test_invalid_not_reclassified_as_valid():
    day = date(2025, 11, 14)
    start, end = local_day_bounds(day, BERLIN)
    events = [
        TimedState(start, "on"),
        TimedState(start + timedelta(hours=22), "unavailable"),
        TimedState(start + timedelta(hours=23), "on"),
    ]
    timeline = reconstruct(
        day, BERLIN, events, [Coverage(start, end)], lambda state: state in ("on", "off")
    )
    assert timeline.seconds == 23 * 3600
    assert timeline.valid
    events[1] = TimedState(start + timedelta(hours=21), "unknown")
    timeline = reconstruct(
        day, BERLIN, events, [Coverage(start, end)], lambda state: state in ("on", "off")
    )
    assert timeline.seconds == 22 * 3600
    assert not timeline.valid


def test_gaps_between_runs_are_not_counted():
    day = date(2025, 11, 14)
    start, end = local_day_bounds(day, BERLIN)
    runs = [
        Coverage(start, start + timedelta(hours=10)),
        Coverage(start + timedelta(hours=12), end),
    ]
    events = [TimedState(start, "on"), TimedState(start + timedelta(hours=12), "on")]
    result = reconstruct(day, BERLIN, events, runs, lambda value: value == "on")
    assert result.seconds == 22 * 3600
    assert not result.valid


def test_presence_exact_23_hours():
    day = date(2025, 11, 14)
    start, end = local_day_bounds(day, BERLIN)
    events = [TimedState(start, "on"), TimedState(start + timedelta(hours=23), "off")]
    timeline = reconstruct(
        day, BERLIN, events, [Coverage(start, end)], lambda x: normalize_presence(x) is True
    )
    assert timeline.valid
    events[1] = TimedState(start + timedelta(hours=22, minutes=59), "off")
    timeline = reconstruct(
        day, BERLIN, events, [Coverage(start, end)], lambda x: normalize_presence(x) is True
    )
    assert not timeline.valid


def test_first_valid_day_per_light():
    today = date(2026, 11, 13)
    days = list(candidate_days(today))
    start, end = local_day_bounds(days[0], BERLIN)
    ok = reconstruct(
        days[0], BERLIN, [TimedState(start, "on")], [Coverage(start, end)], lambda x: x == "on"
    )
    no = reconstruct(days[0], BERLIN, [], [Coverage(start, end)], lambda x: x == "on")

    def presence(day):
        return ok

    def a(day):
        return ok

    def b(day):
        return no if day == days[0] else ok

    assert first_qualified(today, BERLIN, presence, a)[0] == days[0]
    assert first_qualified(today, BERLIN, presence, b)[0] == days[1]
    assert first_qualified(today, BERLIN, lambda day: no, a) is None


def test_playback_invalid_state_keeps_previous_valid():
    day = date(2025, 11, 14)
    events = [row(day, 0, "off"), row(day, 6, "on"), row(day, 8, "unknown"), row(day, 17, "off")]
    timeline = reconstruct(
        day,
        BERLIN,
        events,
        [Coverage(*local_day_bounds(day, BERLIN))],
        lambda v: v in ("on", "off"),
    )
    assert desired_state(timeline, datetime(2026, 11, 14, 7, tzinfo=BERLIN), BERLIN) == "on"
    assert desired_state(timeline, datetime(2026, 11, 14, 9, tzinfo=BERLIN), BERLIN) == "on"
    assert desired_state(timeline, datetime(2026, 11, 14, 18, tzinfo=BERLIN), BERLIN) == "off"


def test_playback_without_prior_valid_falls_back_off():
    day = date(2025, 11, 14)
    start, end = local_day_bounds(day, BERLIN)
    timeline = reconstruct(
        day,
        BERLIN,
        [TimedState(start + timedelta(hours=1), "on")],
        [Coverage(start, end)],
        lambda v: v in ("on", "off"),
    )
    assert desired_state(timeline, datetime(2026, 11, 14, 0, tzinfo=BERLIN), BERLIN) == "off"


def test_dst_coverage_uses_actual_elapsed_hours():
    for day, expected in [(date(2026, 3, 29), 23), (date(2026, 10, 25), 25)]:
        start, end = local_day_bounds(day, BERLIN)
        result = reconstruct(
            day, BERLIN, [TimedState(start, "on")], [Coverage(start, end)], lambda x: x == "on"
        )
        assert result.seconds == expected * 3600
        assert result.valid


def test_fallback_repeated_hour():
    day = date(2026, 10, 25)
    start, end = local_day_bounds(day, BERLIN)
    one = row(day, 2, "on", fold=0)
    two = row(day, 2, "off", fold=1)
    timeline = reconstruct(
        day,
        BERLIN,
        [TimedState(start, "off"), one, two],
        [Coverage(start, end)],
        lambda x: x in ("on", "off"),
    )
    current = datetime(2026, 10, 25, 2, 30, tzinfo=BERLIN)
    assert desired_state(timeline, current.replace(fold=0), BERLIN) == "on"
    assert desired_state(timeline, current.replace(fold=1), BERLIN) == "off"
