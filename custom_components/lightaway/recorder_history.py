"""Recorder-backed history with explicit recording-run continuity evidence.

Queries use Home Assistant's recorder session, history API, and portable
SQLAlchemy models; never connect directly to SQLite or any database URL.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Iterable

from sqlalchemy import select
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.db_schema import RecorderRuns, States, StatesMeta
from homeassistant.components.recorder.history import get_significant_states_with_session
from homeassistant.core import HomeAssistant
from homeassistant.helpers.recorder import session_scope

from .model import Coverage, TimedState, local_day_bounds


def _as_utc(value: datetime) -> datetime:
    """Recorder run timestamps are UTC; normalize legacy naive UTC values."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class RecorderHistory:
    """Load one historical day, including verified pre-midnight seed states."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def async_day(
        self, day: date, zone, entity_ids: Iterable[str]
    ) -> tuple[dict[str, list[TimedState]], list[Coverage]]:
        """Batch state-history reads in recorder's dedicated DB executor."""
        entities = list(dict.fromkeys(entity_ids))
        if not entities:
            return {}, []
        # The recorder's executor is separate from Home Assistant's event loop.
        instance = get_instance(self.hass)
        return await instance.async_add_executor_job(self._read_day, day, zone, entities)

    def _read_day(
        self, day: date, zone, entity_ids: list[str]
    ) -> tuple[dict[str, list[TimedState]], list[Coverage]]:
        """Read recorded runs, real transitions, and corroborated initial states."""
        start, end = local_day_bounds(day, zone)
        events: dict[str, list[TimedState]] = {entity: [] for entity in entity_ids}

        with session_scope(hass=self.hass, read_only=True) as session:
            db_runs = session.scalars(
                select(RecorderRuns)
                .where(RecorderRuns.start < end, RecorderRuns.end > start)
                .order_by(RecorderRuns.start)
            ).all()
            runs: list[Coverage] = []
            last_end = None
            for run in db_runs:
                # Unclean shutdowns cannot certify unobserved continuity.
                if run.closed_incorrect or run.end is None:
                    continue
                run_start, run_end = _as_utc(run.start), _as_utc(run.end)
                if last_end is not None and run_start < last_end:
                    # Treat overlapping or inconsistent metadata as a gap.
                    continue
                if run_end > run_start:
                    runs.append(Coverage(run_start, run_end))
                    last_end = run_end
            if not runs:
                return events, []

            # Official HA history API for changes inside the day. Never use
            # synthetic start-time states: those can mask recorder outages.
            for index in range(0, len(entity_ids), 64):
                subset = entity_ids[index : index + 64]
                history = get_significant_states_with_session(
                    self.hass,
                    session,
                    start,
                    end,
                    entity_ids=subset,
                    include_start_time_state=False,
                    significant_changes_only=False,
                    no_attributes=True,
                )
                for entity in subset:
                    for state in history.get(entity, ()):
                        timestamp = _as_utc(state.last_updated)
                        if start <= timestamp < end:
                            events[entity].append(TimedState(timestamp, state.state))

            # For a state carried into the day (or across a later recorder
            # restart), demand a REAL recorded sample from *the same run*.
            # This also permits completely silent days when evidenced.
            meta_ids = dict(
                session.execute(
                    select(StatesMeta.entity_id, StatesMeta.metadata_id).where(
                        StatesMeta.entity_id.in_(entity_ids)
                    )
                ).all()
            )
            for run in runs:
                begin = max(start, run.start)
                if begin >= end:
                    continue
                for entity in entity_ids:
                    meta_id = meta_ids.get(entity)
                    if meta_id is None:
                        continue
                    row = session.execute(
                        select(States.state, States.last_updated_ts)
                        .where(
                            States.metadata_id == meta_id,
                            States.last_updated_ts >= run.start.timestamp(),
                            States.last_updated_ts <= begin.timestamp(),
                        )
                        .order_by(States.last_updated_ts.desc())
                        .limit(1)
                    ).first()
                    if row is not None:
                        value, timestamp = row
                        events[entity].append(
                            TimedState(datetime.fromtimestamp(timestamp, UTC), value)
                        )
        return events, runs
