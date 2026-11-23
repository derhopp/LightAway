"""Recorder-backed history with explicit recording-run continuity evidence.

Queries use Home Assistant's recorder session, history API, and portable
SQLAlchemy models; never connect directly to SQLite or any database URL.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
import hashlib
import json
import math
from typing import Any, Iterable

from sqlalchemy import or_, select
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.db_schema import RecorderRuns, States, StatesMeta
from homeassistant.components.recorder.history import get_significant_states_with_session
from homeassistant.core import HomeAssistant
from homeassistant.helpers.recorder import session_scope
from homeassistant.helpers.storage import Store

from .model import Coverage, TimedState, local_day_bounds

COVERAGE_STORE_KEY = "more_records_verified_history_v1"
COVERAGE_STORE_VERSION = 1


def _as_utc(value: datetime) -> datetime:
    """Recorder run timestamps are UTC; normalize legacy naive UTC values."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class RecorderHistory:
    """Load a day and genuine entity state anchors across Recorder runs."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._certificates: list[dict[str, Any]] | None = None
        self._verified_ranges: dict[tuple, bool] = {}

    def reset_verification_cache(self) -> None:
        """Reread all provenance after settings/day changes or a new rebuild."""
        self._certificates = None
        self._verified_ranges.clear()

    async def _load_claims(self) -> list[dict[str, Any]]:
        if self._certificates is not None:
            return self._certificates
        # The other integration is optional. Only explicit, confirmed CCU
        # coverage is eligible; an absent or corrupt store cannot grant trust.
        try:
            loaded = await Store(
                self.hass, COVERAGE_STORE_VERSION, COVERAGE_STORE_KEY, read_only=True
            ).async_load()
        except OSError, ValueError, TypeError:
            loaded = None
        valid: list[dict[str, Any]] = []
        if isinstance(loaded, dict) and loaded.get("schema") == 1:
            entries = loaded.get("intervals", [])
            if not isinstance(entries, list):
                entries = []
            for item in entries:
                if not isinstance(item, dict):
                    continue
                try:
                    entity = item["entity_id"]
                    start = float(item["start"])
                    end = float(item["end"])
                    fingerprint = item["fingerprint"]
                except KeyError, ValueError, TypeError:
                    continue
                if (
                    isinstance(entity, str)
                    and math.isfinite(start)
                    and math.isfinite(end)
                    and end > start
                    and item.get("source") == "ccu_historian"
                    and item.get("evidence") == "confirmed_query_and_recorder_match"
                    and isinstance(fingerprint, str)
                    and len(fingerprint) == 64
                    and all(c in "0123456789abcdef" for c in fingerprint)
                ):
                    valid.append(
                        {
                            "entity_id": entity,
                            "start": start,
                            "end": end,
                            "fingerprint": fingerprint,
                        }
                    )
        self._certificates = valid
        return valid

    async def async_day(
        self, day: date, zone, entity_ids: Iterable[str]
    ) -> tuple[dict[str, list[TimedState]], list[Coverage]]:
        """Batch state-history reads in recorder's dedicated DB executor."""
        entities = list(dict.fromkeys(entity_ids))
        if not entities:
            return {}, []
        # The recorder's executor is separate from Home Assistant's event loop.
        claims = await self._load_claims()
        instance = get_instance(self.hass)
        return await instance.async_add_executor_job(self._read_day, day, zone, entities, claims)

    def _read_day(
        self,
        day: date,
        zone,
        entity_ids: list[str],
        claims: list[dict[str, Any]] | None = None,
    ) -> tuple[dict[str, list[TimedState]], list[Coverage]]:
        """Read real transitions, recorded-run coverage and last known states."""
        start, end = local_day_bounds(day, zone)
        events: dict[str, list[TimedState]] = {entity: [] for entity in entity_ids}
        manager = get_instance(self.hass).recorder_runs_manager
        active_start = _as_utc(manager.current.start) if manager.active else None

        with session_scope(hass=self.hass, read_only=True) as session:
            db_runs = session.scalars(
                select(RecorderRuns)
                .where(
                    RecorderRuns.start < end,
                    or_(RecorderRuns.end > start, RecorderRuns.end.is_(None)),
                )
                .order_by(RecorderRuns.start)
            ).all()
            runs: list[Coverage] = []
            last_end = None
            for run in db_runs:
                # Only the currently active run may have a NULL end.
                # Historical, incorrectly closed runs cannot prove continuity.
                if run.closed_incorrect:
                    continue
                run_start = _as_utc(run.start)
                if run.end is None:
                    if active_start is None or run_start != active_start:
                        continue
                    run_end = datetime.now(UTC)
                else:
                    run_end = _as_utc(run.end)
                if last_end is not None and run_start < last_end:
                    # Treat overlapping or inconsistent metadata as a gap.
                    continue
                if run_end > run_start:
                    runs.append(Coverage(run_start, run_end))
                    last_end = run_end
            # Verify the COMPLETE certified interval against the CURRENT
            # persisted Recorder samples. Purged or edited history invalidates
            # the attestation. Never infer evidence from metadata alone.
            meta_ids = dict(
                session.execute(
                    select(StatesMeta.entity_id, StatesMeta.metadata_id).where(
                        StatesMeta.entity_id.in_(entity_ids)
                    )
                ).all()
            )
            claimed_entities: set[str] = set()
            for claim in claims or []:
                entity = claim["entity_id"]
                if entity not in events or entity not in meta_ids:
                    continue
                beginning = claim["start"]
                ending = claim["end"]
                if beginning >= end.timestamp() or ending <= start.timestamp():
                    continue
                # A stale or conflicting certificate must fail closed rather
                # than silently falling back to a weaker evidence source.
                claimed_entities.add(entity)
                cache_key = (meta_ids[entity], beginning, ending, claim["fingerprint"])
                verified = self._verified_ranges.get(cache_key)
                if verified is None:
                    data = session.execute(
                        select(States.last_updated_ts, States.state)
                        .where(
                            States.metadata_id == meta_ids[entity],
                            States.last_updated_ts >= beginning,
                            States.last_updated_ts < ending,
                        )
                        .order_by(States.last_updated_ts, States.state_id)
                    ).all()
                    digest = hashlib.sha256()
                    for timestamp, value in data:
                        digest.update(
                            json.dumps(
                                [float(timestamp).hex(), str(value)],
                                separators=(",", ":"),
                            ).encode()
                        )
                        digest.update(b"\n")
                    verified = bool(data) and digest.hexdigest() == claim["fingerprint"]
                    self._verified_ranges[cache_key] = verified
                if verified:
                    runs.append(
                        Coverage(
                            datetime.fromtimestamp(beginning, UTC),
                            datetime.fromtimestamp(ending, UTC),
                            entity_id=entity,
                            source="ccu_historian_verified",
                        )
                    )

            # Histories imported into Recorder before Home Assistant was
            # running have real state-change rows but no historical
            # RecorderRuns. For those older days, a genuine state at/before
            # midnight AND a subsequent observation after the day bracket
            # a bounded state-change series. Reconstruct its in-day events
            # exactly as for native Recorder data, never inventing samples.
            #
            # This is state-history inference, NOT proof of uninterrupted
            # Recorder operation or CCU-Historian source completeness. Never
            # override a known native Recorder run/gap or a failed certificate.
            has_native_runs = any(run.entity_id is None for run in runs)
            if not has_native_runs:
                for entity, meta_id in meta_ids.items():
                    if entity in claimed_entities or any(
                        run.entity_id == entity for run in runs
                    ):
                        continue
                    before = session.execute(
                        select(States.last_updated_ts)
                        .where(
                            States.metadata_id == meta_id,
                            States.last_updated_ts <= start.timestamp(),
                        )
                        .order_by(States.last_updated_ts.desc(), States.state_id.desc())
                        .limit(1)
                    ).scalar_one_or_none()
                    if before is None:
                        continue
                    after = session.execute(
                        select(States.last_updated_ts)
                        .where(
                            States.metadata_id == meta_id,
                            States.last_updated_ts >= end.timestamp(),
                        )
                        .order_by(States.last_updated_ts.asc(), States.state_id.asc())
                        .limit(1)
                    ).scalar_one_or_none()
                    if after is not None:
                        runs.append(
                            Coverage(
                                start,
                                end,
                                entity_id=entity,
                                source="bounded_state_history",
                            )
                        )
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

            # Find the last REAL Recorder state even if it precedes a restart
            # by months. A state remains the last known value until superseded.
            # The preceding recording gaps are not credited as coverage:
            # reconstruct() counts only actual runs or verified imports.
            for run in runs:
                begin = max(start, run.start)
                if begin >= end:
                    continue
                for entity in entity_ids:
                    if run.entity_id is not None and run.entity_id != entity:
                        continue
                    meta_id = meta_ids.get(entity)
                    if meta_id is None:
                        continue
                    row = session.execute(
                        select(States.state, States.last_updated_ts)
                        .where(
                            States.metadata_id == meta_id,
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
