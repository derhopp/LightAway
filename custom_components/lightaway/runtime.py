"""Runtime controller: persistent configuration, cached day histories, safe reconciliation."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DEFAULT_OPTIONS, STORE_KEY, STORE_VERSION, UPDATE_SIGNAL
from .model import candidate_days, desired_state, normalize_presence, reconstruct
from .recorder_history import RecorderHistory

_LOGGER = logging.getLogger(__name__)


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
        self._day = None
        self._callbacks: list = []
        self._add_sensors = None
        self._ready = False
        self._rebuild_task: asyncio.Task | None = None

    async def async_load(self) -> None:
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.settings = {**DEFAULT_OPTIONS, **saved}
        self.settings["lights"] = list(dict.fromkeys(self.settings.get("lights") or []))
        self._callbacks.append(async_track_time_interval(self.hass, self._tick, timedelta(seconds=30)))
        self._callbacks.append(self.hass.bus.async_listen("entity_registry_updated", self._registry_changed))
        self._callbacks.append(self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STARTED, self._started))
        self._track_entities()
        # Startup rebuilds without ever using stale or incomplete sequences.
        self.request_rebuild()

    async def async_unload(self) -> None:
        self._generation += 1
        self._ready = False
        if self._rebuild_task and not self._rebuild_task.done():
            self._rebuild_task.cancel()
        for cancel in self._callbacks:
            cancel()
        self._callbacks.clear()

    def _track_entities(self) -> None:
        if hasattr(self, "_cancel_entities") and self._cancel_entities:
            self._cancel_entities()
        entities = [*self.settings["lights"]]
        if self.settings["presence"]:
            entities.append(self.settings["presence"])
        self._cancel_entities = async_track_state_change_event(
            self.hass, entities, self._state_changed
        ) if entities else None

    @callback
    def _started(self, _event) -> None:
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
        today = dt_util.now().date()
        if self._day != today:
            if self._rebuild_task is None or self._rebuild_task.done():
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
        """Persist only validated user settings; update state without restart."""
        new_settings = {**self.settings, **changes}
        new_settings["lights"] = list(dict.fromkeys(new_settings["lights"]))
        affected = any(
            new_settings[key] != self.settings[key] for key in ("presence", "invert", "lights")
        )
        self.settings = new_settings
        await self.store.async_save(self.settings)
        self._track_entities()
        if affected:
            self.request_rebuild()
        else:
            await self.async_update()
        self._notify()

    async def _rebuild(self, generation: int) -> None:
        """Recompute independently per light; never publish partial results."""
        async with self._rebuild_lock:
            today = dt_util.now().date()
            zone = dt_util.get_time_zone(self.hass.config.time_zone)
            presence_entity = self.settings["presence"]
            lights = list(self.settings["lights"])
            invert = self.settings["invert"]
            new_results: dict[str, dict[str, Any]] = {}
            had_presence_match = False
            if not presence_entity:
                for light in lights:
                    new_results[light] = self._error("presence_not_configured")
            else:
                presence_cache = {}
                try:
                    for day in candidate_days(today):
                        if generation != self._generation:
                            return
                        pending = [light for light in lights if light not in new_results]
                        if not pending:
                            break
                        # Query each candidate day once for the remaining lights.
                        try:
                            events, runs = await self.history.async_day(day, zone, [presence_entity, *pending])
                        except Exception:
                            _LOGGER.exception("Recorder history unavailable on %s", day)
                            for light in pending:
                                new_results[light] = self._error("recorder_unavailable")
                            break
                        presence = presence_cache.get(day)
                        if presence is None:
                            presence = reconstruct(
                                day, zone, events.get(presence_entity, ()), runs,
                                lambda value: normalize_presence(value, invert) is True,
                            )
                            presence_cache[day] = presence
                        if not presence.valid:
                            continue
                        had_presence_match = True
                        for light in pending:
                            try:
                                timeline = reconstruct(
                                    day, zone, events.get(light, ()), runs,
                                    lambda value: value in ("on", "off"),
                                )
                                if timeline.valid:
                                    new_results[light] = {
                                        "original_day": day.isoformat(),
                                        "timeline": timeline,
                                        "desired": None,
                                        "status": "ok",
                                    }
                            except Exception:
                                _LOGGER.exception("History calculation failed for %s", light)
                                new_results[light] = self._error("calculation_error")
                except Exception:
                    _LOGGER.exception("Unexpected LightAway rebuild failure")
                    for light in lights:
                        new_results.setdefault(light, self._error("calculation_error"))
            for light in lights:
                new_results.setdefault(light, self._error(
                    "insufficient_history" if had_presence_match else "no_original_day"
                ))
            if generation != self._generation:
                return
            self.results = new_results
            self._day = today
            self._ready = True
            await self.async_update()

    @staticmethod
    def _error(reason: str) -> dict[str, Any]:
        return {"original_day": None, "desired": None, "status": reason, "timeline": None}

    def presence(self) -> bool | None:
        entity = self.settings["presence"]
        state = self.hass.states.get(entity) if entity else None
        return normalize_presence(state.state if state else None, self.settings["invert"])

    async def async_update(self) -> None:
        """Update cached desired states then reconcile only while safe."""
        zone = dt_util.get_time_zone(self.hass.config.time_zone)
        now = dt_util.now()
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
            items.append({
                "entity_id": entity,
                "original_day": result.get("original_day"),
                "actual": state.state if state else None,
                "desired": result.get("desired"),
                "status": (
                    "light_missing" if state is None else
                    "light_unavailable" if state.state not in ("on", "off") else
                    result.get("status")
                ),
            })
        return {
            "settings": self.settings,
            "presence_status": self.presence(),
            "presence_available": presence_available,
            "ready": self._ready,
            "lights": items,
        }
