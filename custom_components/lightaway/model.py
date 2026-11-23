"""Pure, time-zone-aware state reconstruction and day selection.

All intervals are half open and all measured durations use UTC elapsed seconds.
Recorder runs prove recorded time, not state transitions. A last known real
entity value may carry across restarts, but offline gaps are never counted.
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
    # None is an ordinary HA Recorder run; an ID scopes verified imported
    # coverage to the source entity only.
    entity_id: str | None = None


def coverage_for_entity(runs: Iterable[Coverage], entity_id: str) -> list[Coverage]:
    """Prefer verified entity history over intersecting native-run intervals.

    Native RecorderRuns remain authoritative outside entity-specific imported
    coverage. Never borrow one light's imported coverage for another entity.
    """
    all_runs = list(runs)
    imported = sorted(
        (run for run in all_runs if run.entity_id == entity_id),
        key=lambda run: run.start.astimezone(UTC),
    )
    native = [run for run in all_runs if run.entity_id is None]
    result = list(imported)
    for run in native:
        pieces = [(run.start.astimezone(UTC), run.end.astimezone(UTC))]
        for claim in imported:
            claimed_start, claimed_end = claim.start.astimezone(UTC), claim.end.astimezone(UTC)
            remaining = []
            for left, right in pieces:
                if claimed_start >= right or claimed_end <= left:
                    remaining.append((left, right))
                else:
                    if left < claimed_start:
                        remaining.append((left, claimed_start))
                    if claimed_end < right:
                        remaining.append((claimed_end, right))
            pieces = remaining
        result.extend(Coverage(left, right) for left, right in pieces if right > left)
    return sorted(result, key=lambda run: run.start.astimezone(UTC))


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


def candidate_days(
    today: date,
    *,
    max_weeks_away: int = 8,
    min_weeks_from_today: int = 1,
    use_recent_weeks: bool = True,
) -> Iterable[date]:
    """Yield eligible same-weekday dates in strict priority order.

    Priority 1 is the closest matching weekdays in the inclusive calendar
    interval [one year ago - max weeks, one year ago + max weeks].
    Priority 2 is recent weekdays 1..N weeks ago, starting with the closest.
    Only *completed past days* are considered. Duplicate dates are skipped.
    """
    ideal = shift_year(today)
    earliest = ideal - timedelta(weeks=max_weeks_away)
    latest = ideal + timedelta(weeks=max_weeks_away)
    first = earliest + timedelta(days=(today.weekday() - earliest.weekday()) % 7)
    yearly = []
    candidate = first
    while candidate <= latest:
        if candidate < today:
            yearly.append(candidate)
        candidate += timedelta(days=7)

    seen: set[date] = set()
    for candidate in sorted(yearly, key=lambda item: (abs((item - ideal).days), item)):
        seen.add(candidate)
        yield candidate

    if use_recent_weeks and max_weeks_away > min_weeks_from_today:
        for weeks_ago in range(min_weeks_from_today, max_weeks_away + 1):
            candidate = today - timedelta(weeks=weeks_ago)
            if candidate not in seen:
                seen.add(candidate)
                yield candidate


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

    The event list contains genuine timestamped Recorder samples and the last
    available sample before each run slice. Stable states can carry forward
    across restarts, but time without Recorder coverage remains unqualified.
    Unknown/unavailable states never qualify.
    """
    start, end = local_day_bounds(day, zone)
    ordered = sorted(events, key=lambda row: row.at.astimezone(UTC))
    coverage = sorted(runs, key=lambda run: run.start.astimezone(UTC))
    valid_seconds = 0.0
    observed_seconds = 0.0
    replay: list[TimedState] = []

    previous_run_end = None
    for run in coverage:
        if previous_run_end is not None and run.start.astimezone(UTC) < previous_run_end:
            continue
        previous_run_end = run.end.astimezone(UTC)
        begin = max(start, run.start.astimezone(UTC))
        finish = min(end, run.end.astimezone(UTC))
        if begin >= finish:
            continue
        # The latest genuine sample is the last known value in each later
        # run, even if it is months old. Carry its state, not the missing
        # Recorder coverage, across restart gaps.
        seed: TimedState | None = None
        within: list[TimedState] = []
        for event in ordered:
            at = event.at.astimezone(UTC)
            if at <= begin:
                seed = event
            elif at < finish:
                within.append(event)
            else:
                break

        state = seed.value if seed is not None else None
        initial_state = state
        cursor = begin
        for event in within:
            at = event.at.astimezone(UTC)
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

        # Playback uses the selected day's slice, not old event times. A
        # later Recorder run must re-establish its carried initial state.
        if initial_state is not None:
            replay.append(TimedState(begin, initial_state))
        replay.extend(within)

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
    *,
    max_weeks_away: int = 8,
    min_weeks_from_today: int = 1,
    use_recent_weeks: bool = True,
) -> tuple[date, Timeline] | None:
    """Select the first day meeting both independent 23-hour thresholds."""
    for candidate in candidate_days(
        today,
        max_weeks_away=max_weeks_away,
        min_weeks_from_today=min_weeks_from_today,
        use_recent_weeks=use_recent_weeks,
    ):
        if presence(candidate).valid:
            light_timeline = light(candidate)
            if light_timeline.valid:
                return candidate, light_timeline
    return None
