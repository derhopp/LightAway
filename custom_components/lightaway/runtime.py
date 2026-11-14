"""Runtime controller: persistent configuration, cached day histories, safe reconciliation."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    BOOLEAN_OPTIONS,
    DEFAULT_OPTIONS,
    PRESENCE_DOMAINS,
    STORE_KEY,
    STORE_VERSION,
    UPDATE_SIGNAL,
)
from .model import candidate_days, desired_state, normalize_presence, reconstruct
from .recorder_history import RecorderHistory

_LOGGER = logging.getLogger(__name__)

# Bounded number of rejected candidate days kept for the diagnostics payload.
MAX_CANDIDATES = 12
LIGHT_DOMAINS = frozenset({"light"})


def _is_entity(value: object, domains: frozenset[str]) -> bool:
    """Return True for a syntactically valid ``domain.object_id`` entity ID."""
    if not isinstance(value, str) or value.count(".") != 1:
        return False
    domain, object_id = value.split(".")
    return domain in domains and bool(object_id)


class LightAwayRuntime:
    """State machine. Desired state never depends on enabled or presence."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.store = Store(hass, STORE_VERSION, STORE_KEY)
        self.settings: dict[str, Any] = dict(DEFAULT_OPTIONS)
        self.history = RecorderHistory(hass)
        self.results: dict[str, dict[str, Any]] = {}
        self._rebuild_lock = asyncio.Lock()
        self._control_lock = asyncio.Lock()
        self._generation = 0
        # Day and time zone the cached results were computed for. A time zone
        # change moves every local midnight, so the cache is invalid then too.
        self._context: tuple[date, str] | None = None
        self._last_rebuild_at = None
        self._callbacks: list = []
        self._cancel_entities = None
        self._ready = False
        self._rebuild_task: asyncio.Task | None = None
        self._candidates: list[dict[str, Any]] = []
        self._repaired_settings: list[str] = []

    def _context_of(self) -> tuple[date, str]:
        """Return the day and time zone the cached results depend on."""
        return (dt_util.now().date(), self.hass.config.time_zone)

    async def async_load(self) -> None:
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.settings = {**DEFAULT_OPTIONS, **saved}
        # Existing installations retain their choices and receive safe new defaults.
        self.settings["lights"] = list(dict.fromkeys(self.settings.get("lights") or []))
        for key, minimum in (("min_weeks_from_today", 1), ("max_weeks_away", 2)):
            value = self.settings.get(key)
            if type(value) is not int or not minimum <= value <= 52:
                self.settings[key] = DEFAULT_OPTIONS[key]
                self._repaired_settings.append(key)
        for key in BOOLEAN_OPTIONS:
            if type(self.settings.get(key)) is not bool:
                self.settings[key] = DEFAULT_OPTIONS[key]
                self._repaired_settings.append(key)
        # A stored range that excludes every recent week would silently disable
        # the fallback the user configured, so reset both bounds to the defaults.
        if self.settings["min_weeks_from_today"] > self.settings["max_weeks_away"]:
            self.settings["min_weeks_from_today"] = DEFAULT_OPTIONS["min_weeks_from_today"]
            self.settings["max_weeks_away"] = DEFAULT_OPTIONS["max_weeks_away"]
            self._repaired_settings.extend(("min_weeks_from_today", "max_weeks_away"))
        self._callbacks.append(
            async_track_time_interval(self.hass, self._tick, timedelta(seconds=30))
        )
        self._callbacks.append(
            self.hass.bus.async_listen("entity_registry_updated", self._registry_changed)
        )
        self._callbacks.append(
            self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STARTED, self._started)
        )
        self._track_entities()
        # Startup rebuilds without ever using stale or incomplete sequences.
        self.request_rebuild()

    async def async_unload(self) -> None:
        self._generation += 1
        self._ready = False
        task = self._rebuild_task
        self._rebuild_task = None
        if task is not None and not task.done():
            task.cancel()
        # The per-entity state listener is not in _callbacks: without this the
        # unloaded runtime keeps receiving light events and schedules work.
        if self._cancel_entities is not None:
            self._cancel_entities()
            self._cancel_entities = None
        for cancel in self._callbacks:
            cancel()
        self._callbacks.clear()

    def _track_entities(self) -> None:
        if self._cancel_entities is not None:
            self._cancel_entities()
            self._cancel_entities = None
        entities = [*self.settings["lights"]]
        if self.settings["presence"]:
            entities.append(self.settings["presence"])
        self._cancel_entities = (
            async_track_state_change_event(self.hass, entities, self._state_changed)
            if entities
            else None
        )

    @callback
    def _started(self, _event) -> None:
        if self._rebuild_task is None or self._rebuild_task.done():
            self.request_rebuild()

    @callback
    def _registry_changed(self, event) -> None:
        """Migrate entity IDs on registry rename without losing sensor identity."""
        data = event.data
        old = data.get("old_entity_id")
        new = data.get("entity_id")
        if not old or not new:
            if data.get("action") == "remove":
                self.request_update()
            return
        if old in self.settings["lights"] or old == self.settings["presence"]:
            lights = [new if value == old else value for value in self.settings["lights"]]
            self.settings["lights"] = lights
            if self.settings["presence"] == old:
                self.settings["presence"] = new
            self.hass.async_create_task(self.store.async_save(self.settings))
            self._track_entities()
            self.request_rebuild()

    @callback
    def _state_changed(self, _event) -> None:
        self.request_update()

    @callback
    def _tick(self, _now: datetime) -> None:
        # Rebuild when the local day *or* the configured time zone changed: a
        # zone change moves every copy-day boundary, so cached results computed
        # in the previous zone must not be replayed.
        if self._context != self._context_of():
            if self._rebuild_task is None or self._rebuild_task.done():
                self.request_rebuild()
        elif (
            any(r.get("status") == "recorder_unavailable" for r in self.results.values())
            and self._last_rebuild_at is not None
            and (dt_util.utcnow() - self._last_rebuild_at).total_seconds() >= 600
            and (self._rebuild_task is None or self._rebuild_task.done())
        ):
            self.request_rebuild()
        else:
            self.request_update()

    def request_update(self) -> None:
        self.hass.async_create_task(self.async_update())

    def request_rebuild(self) -> None:
        self._generation += 1
        generation = self._generation
        self._ready = False
        for result in self.results.values():
            result["desired"] = None
            result["status"] = "recalculating"
        self._notify()
        self._rebuild_task = self.hass.async_create_task(self._rebuild(generation))

    def _notify(self) -> None:
        async_dispatcher_send(self.hass, UPDATE_SIGNAL)
        self.hass.bus.async_fire("lightaway_updated")

    async def async_configure(self, changes: dict[str, Any]) -> None:
        """Persist settings and recompute all dates after every effective change."""
        new_settings = {**self.settings, **changes}
        for key, minimum in (("min_weeks_from_today", 1), ("max_weeks_away", 2)):
            value = new_settings[key]
            if type(value) is not int or not minimum <= value <= 52:
                raise ValueError(f"{key} must be an integer from {minimum} to 52")
        for key in BOOLEAN_OPTIONS:
            if type(new_settings[key]) is not bool:
                raise ValueError(f"{key} must be a boolean")
        presence = new_settings["presence"]
        if presence is not None and not _is_entity(presence, PRESENCE_DOMAINS):
            raise ValueError("presence must be a binary_sensor, switch or input_boolean entity")
        lights = new_settings["lights"]
        if not isinstance(lights, list) or any(
            not _is_entity(light, LIGHT_DOMAINS) for light in lights
        ):
            raise ValueError("lights must be a list of light entities")
        new_settings["lights"] = list(dict.fromkeys(lights))
        # Bounds that exclude every recent week would silently disable the
        # fallback; equal bounds are valid and select exactly that week.
        if new_settings["min_weeks_from_today"] > new_settings["max_weeks_away"]:
            raise ValueError("min_weeks_from_today must not be greater than max_weeks_away")
        if new_settings == self.settings:
            return
        changed_entities = any(
            new_settings[key] != self.settings[key] for key in ("presence", "lights")
        )
        self.settings = new_settings
        await self.store.async_save(self.settings)
        if changed_entities:
            self._track_entities()
        self.request_rebuild()
        self._notify()

    async def _rebuild(self, generation: int) -> None:
        """Select valid source dates in priority order, independently or jointly."""
        async with self._rebuild_lock:
            today = dt_util.now().date()
            zone_name = self.hass.config.time_zone
            zone = dt_util.get_time_zone(zone_name)
            presence_entity = self.settings["presence"]
            lights = list(self.settings["lights"])
            invert = self.settings["invert"]
            same_day = self.settings.get("just_same_copy_day", False)
            new_results: dict[str, dict[str, Any]] = {}
            evidence: list[dict[str, Any]] = []
            had_presence_match = False
            failed_status = None

            if not presence_entity:
                for light in lights:
                    new_results[light] = self._error("presence_not_configured")
            else:
                try:
                    for day in candidate_days(
                        today,
                        max_weeks_away=self.settings["max_weeks_away"],
                        min_weeks_from_today=self.settings["min_weeks_from_today"],
                        use_recent_weeks=self.settings["use_recent_weeks"],
                    ):
                        if generation != self._generation:
                            return
                        pending = (
                            lights
                            if same_day
                            else [light for light in lights if light not in new_results]
                        )
                        if not pending:
                            break
                        try:
                            events, runs = await self.history.async_day(
                                day, zone, [presence_entity, *pending]
                            )
                        except Exception:
                            _LOGGER.exception("Recorder history unavailable on %s", day)
                            failed_status = "recorder_unavailable"
                            break
                        presence = reconstruct(
                            day,
                            zone,
                            events.get(presence_entity, ()),
                            runs,
                            lambda value: normalize_presence(value, invert) is True,
                        )
                        # Keep bounded evidence so a rejected candidate can be
                        # explained in the downloadable diagnostics.
                        candidate: dict[str, Any] = {
                            "day": day.isoformat(),
                            "presence_seconds": round(presence.seconds),
                            "presence_observed_seconds": round(presence.observed_seconds),
                            "lights": {},
                        }
                        if len(evidence) < MAX_CANDIDATES:
                            evidence.append(candidate)
                        if not presence.valid:
                            continue
                        had_presence_match = True
                        candidate_results: dict[str, dict[str, Any]] = {}
                        for light in pending:
                            try:
                                timeline = reconstruct(
                                    day,
                                    zone,
                                    events.get(light, ()),
                                    runs,
                                    lambda value: value in ("on", "off"),
                                )
                                candidate["lights"][light] = {
                                    "seconds": round(timeline.seconds),
                                    "valid": timeline.valid,
                                }
                                if timeline.valid:
                                    candidate_results[light] = {
                                        "copy_day": day.isoformat(),
                                        "timeline": timeline,
                                        "desired": None,
                                        "status": "ok",
                                    }
                            except Exception:
                                _LOGGER.exception("History calculation failed for %s", light)
                                if same_day:
                                    candidate_results = {}
                                    break
                                new_results[light] = self._error("calculation_error")
                        if same_day:
                            if len(candidate_results) == len(lights):
                                new_results = candidate_results
                                break
                        else:
                            new_results.update(candidate_results)
                except Exception:
                    _LOGGER.exception("Unexpected LightAway rebuild failure")
                    failed_status = "calculation_error"

            for light in lights:
                new_results.setdefault(
                    light,
                    self._error(
                        failed_status
                        or ("insufficient_history" if had_presence_match else "no_copy_day")
                    ),
                )
            if generation != self._generation:
                return
            self.results = new_results
            self._candidates = evidence
            self._context = (today, zone_name)
            self._last_rebuild_at = dt_util.utcnow()
            self._ready = True
            await self.async_update()

    @staticmethod
    def _error(reason: str) -> dict[str, Any]:
        return {"copy_day": None, "desired": None, "status": reason, "timeline": None}

    def presence(self) -> bool | None:
        entity = self.settings["presence"]
        state = self.hass.states.get(entity) if entity else None
        return normalize_presence(state.state if state else None, self.settings["invert"])

    async def async_update(self) -> None:
        """Update cached desired states then reconcile only while safe."""
        zone = dt_util.get_time_zone(self.hass.config.time_zone)
        now = dt_util.now()
        if (
            self._ready
            and self._context is not None
            and self._context != (now.date(), self.hass.config.time_zone)
        ):
            # Copy days were computed for another day or time zone, so the cached
            # timeline no longer matches the local wall clock. Rebuild instead of
            # replaying it; request_rebuild() marks the results unsafe meanwhile.
            self.request_rebuild()
            return
        if self._ready:
            for light, result in self.results.items():
                timeline = result.get("timeline")
                if timeline is None:
                    continue
                try:
                    result["desired"] = desired_state(timeline, now, zone)
                    actual = self.hass.states.get(light)
                    if actual is None:
                        result["status"] = "light_missing"
                    elif actual.state not in ("on", "off"):
                        result["status"] = "light_unavailable"
                    else:
                        result["status"] = "ok"
                except Exception:
                    _LOGGER.exception("Failed to calculate desired state for %s", light)
                    result["desired"] = None
                    result["status"] = "calculation_error"
        self._notify()
        async with self._control_lock:
            # Repeat safety checks on each light, including after awaits.
            if not self._ready or not self.settings["enabled"] or self.presence() is not False:
                return
            for light, result in list(self.results.items()):
                if not self._ready or not self.settings["enabled"] or self.presence() is not False:
                    return
                if result.get("status") != "ok" or result.get("desired") not in ("on", "off"):
                    continue
                actual = self.hass.states.get(light)
                if actual is None or actual.state not in ("on", "off"):
                    continue
                desired = result["desired"]
                if actual.state == desired:
                    continue
                service = "turn_on" if desired == "on" else "turn_off"
                try:
                    await self.hass.services.async_call(
                        "light", service, {"entity_id": light}, blocking=True
                    )
                except Exception:
                    _LOGGER.exception("LightAway could not switch %s", light)
                    result["status"] = "switch_error"
                    self._notify()

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-safe model for the dashboard."""
        items = []
        presence_available = self.presence() is not None
        for entity in self.settings["lights"]:
            result = self.results.get(entity, self._error("recalculating"))
            state = self.hass.states.get(entity)
            items.append(
                {
                    "entity_id": entity,
                    "copy_day": result.get("copy_day"),
                    "actual": state.state if state else None,
                    "desired": result.get("desired"),
                    "status": (
                        "light_missing"
                        if state is None
                        else "light_unavailable"
                        if state.state not in ("on", "off")
                        else result.get("status")
                    ),
                }
            )
        return {
            "settings": self.settings,
            "presence_status": self.presence(),
            "presence_available": presence_available,
            "ready": self._ready,
            "lights": items,
        }

    def diagnostics(self) -> dict[str, Any]:
        """Return a JSON-safe report for Home Assistant diagnostics downloads."""
        context = (
            {"day": self._context[0].isoformat(), "time_zone": self._context[1]}
            if self._context
            else None
        )
        results = []
        for entity in self.settings["lights"]:
            result = self.results.get(entity, self._error("recalculating"))
            timeline = result.get("timeline")
            results.append(
                {
                    "entity_id": entity,
                    "copy_day": result.get("copy_day"),
                    "status": result.get("status"),
                    "desired": result.get("desired"),
                    "transitions": len(timeline.transitions) if timeline else 0,
                    "qualified_seconds": round(timeline.seconds) if timeline else None,
                    "observed_seconds": round(timeline.observed_seconds) if timeline else None,
                }
            )
        return {
            "ready": self._ready,
            "generation": self._generation,
            "computed_for": context,
            "settings": dict(self.settings),
            "presence": self.presence(),
            "repaired_settings": list(dict.fromkeys(self._repaired_settings)),
            "lights": results,
            "candidates": [dict(candidate) for candidate in self._candidates],
        }
