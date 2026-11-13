"""Pure, time-zone-aware state reconstruction and day selection.

All intervals are half open and all measured durations use UTC elapsed seconds.
Recorder run boundaries are authoritative: no event propagates across a run
unless a new event in that run establishes continuity.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import Callable, Iterable

MIN_SECONDS = 23 * 3600
TRUE = frozenset({"on", "true", "1"})
FALSE = frozenset({"off", "false", "0"})
LIGHT_STATES = frozenset({"on", "off"})


@dataclass(frozen=True)
class TimedState:
    at: datetime
    value: str


@dataclass(frozen=True)
class Coverage:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Timeline:
    transitions: tuple[TimedState, ...]
    seconds: float
    observed_seconds: float

    @property
    def valid(self) -> bool:
        return self.seconds >= MIN_SECONDS


def normalize_presence(value: str | None, invert: bool = False) -> bool | None:
    """Return presence, absence or invalid (including unknown/unavailable)."""
    if not isinstance(value, str):
        return None
    normalized = value.lower().strip()
    if normalized in TRUE:
        return not invert
    if normalized in FALSE:
        return invert
    return None


def local_day_bounds(day: date, zone: tzinfo) -> tuple[datetime, datetime]:
    """Return UTC instants of consecutive local midnights (23/24/25 hours)."""
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    return start, end


def shift_year(day: date) -> date:
    """Feb 29 maps to Feb 28 in the preceding non-leap year."""
    year = day.year - 1
    return date(year, day.month, min(day.day, calendar.monthrange(year, day.month)[1]))


def previous_month(day: date) -> date:
    """Subtract one calendar month, clamping the day to the destination month."""
    year, month = (day.year - 1, 12) if day.month == 1 else (day.year, day.month - 1)
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def candidate_days(today: date) -> Iterable[date]:
    """Forward search, same weekday as today, through one-month cutoff."""
    ideal = shift_year(today)
    offset = (today.weekday() - ideal.weekday()) % 7
    candidate = ideal + timedelta(days=offset)
    limit = previous_month(today)
    while candidate <= limit:
        yield candidate
        candidate += timedelta(days=7)


def seconds_between(start: datetime, end: datetime) -> float:
    return (end.astimezone(UTC) - start.astimezone(UTC)).total_seconds()


def reconstruct(
    day: date,
    zone: tzinfo,
    events: Iterable[TimedState],
    runs: Iterable[Coverage],
    acceptable: Callable[[str], bool],
) -> Timeline:
    """Sum only corroborated intervals during recorded runs.

    The event list must contain genuine timestamped recorder samples, including
    the latest sample before midnight *from within the same recorder run*.
    A silent day counts if this evidence and run coverage exist. Unobserved
    intervals, invalid states and all intervals outside runs count as zero.
    """
    start, end = local_day_bounds(day, zone)
    ordered = sorted(events, key=lambda row: row.at.astimezone(UTC))
    coverage = sorted(runs, key=lambda run: run.start.astimezone(UTC))
    valid_seconds = 0.0
    observed_seconds = 0.0
    replay: list[TimedState] = []

    for run in coverage:
        begin = max(start, run.start.astimezone(UTC))
        finish = min(end, run.end.astimezone(UTC))
        if begin >= finish:
            continue
        # Only events *within this run* establish a trustworthy initial state.
        applicable = [
            event
            for event in ordered
            if run.start.astimezone(UTC) <= event.at.astimezone(UTC) < finish
        ]
        state: str | None = None
        cursor = begin
        for event in applicable:
            at = event.at.astimezone(UTC)
            if at <= begin:
                state = event.value
                continue
            if state is not None:
                observed_seconds += seconds_between(cursor, at)
                if acceptable(state):
                    valid_seconds += seconds_between(cursor, at)
            cursor = at
            state = event.value
        if state is not None:
            observed_seconds += seconds_between(cursor, finish)
            if acceptable(state):
                valid_seconds += seconds_between(cursor, finish)

        # Playback includes the last proven sample before the day's start.
        if begin == start:
            prior = [sample for sample in applicable if sample.at.astimezone(UTC) <= start]
            if prior:
                replay.append(TimedState(start, prior[-1].value))
        for sample in applicable:
            if begin < sample.at.astimezone(UTC) < finish:
                replay.append(sample)

    # A physical instant can occur in multiple runs with malformed metadata.
    # Bound counted durations by rejecting overlaps before this function.
    replay.sort(key=lambda row: row.at.astimezone(UTC))
    return Timeline(tuple(replay), valid_seconds, observed_seconds)


def desired_state(timeline: Timeline, current: datetime, zone: tzinfo) -> str:
    """Replay historical wall time; never upgrade invalid data for qualification.

    In a repeated fall-back hour the target's fold selects the same historic
    fold. On an ordinary target day, only the first occurrence is used until
    the clock leaves that hour. Outside that hour all prior events, including
    the historic second occurrence, are eligible. Nonexistent historic hours
    simply have no matching event.
    """
    now = current.astimezone(zone)
    wall = (now.hour, now.minute, now.second, now.microsecond)
    value = "off"
    ordered = sorted(timeline.transitions, key=lambda row: row.at.astimezone(UTC))
    for item in ordered:
        local = item.at.astimezone(zone)
        item_wall = (local.hour, local.minute, local.second, local.microsecond)
        if item_wall > wall:
            continue
        # Compare folds only within the same repeated wall-hour. An ordinary
        # hour has fold=0 and never uses second-occurrence events in that hour.
        if local.hour == now.hour and local.fold > now.fold:
            continue
        if item.value in LIGHT_STATES:
            value = item.value
    return value


def first_qualified(
    today: date,
    zone: tzinfo,
    presence: Callable[[date], Timeline],
    light: Callable[[date], Timeline],
) -> tuple[date, Timeline] | None:
    """Select the first day meeting both independent 23-hour thresholds."""
    for candidate in candidate_days(today):
        if presence(candidate).valid:
            light_timeline = light(candidate)
            if light_timeline.valid:
                return candidate, light_timeline
    return None
