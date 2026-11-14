"""Downloadable diagnostics: JSON-safe, bounded and explaining rejections."""

import json
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.lightaway.const import DEFAULT_OPTIONS, DOMAIN
from custom_components.lightaway.diagnostics import async_get_config_entry_diagnostics
from custom_components.lightaway.model import Coverage, TimedState, local_day_bounds
from custom_components.lightaway.runtime import MAX_CANDIDATES, LightAwayRuntime

TODAY = date(2026, 11, 13)
ZONE = ZoneInfo("Europe/Berlin")
BERLIN = "Europe/Berlin"


def runtime():
    hass = MagicMock()
    hass.config.time_zone = BERLIN
    hass.states.get.side_effect = lambda entity: SimpleNamespace(
        state="on" if entity == "binary_sensor.present" else "off"
    )
    hass.services.async_call = AsyncMock()
    instance = LightAwayRuntime(hass, "my_entry")
    instance.settings = {
        **DEFAULT_OPTIONS,
        "presence": "binary_sensor.present",
        "lights": ["light.a"],
    }
    instance._notify = lambda: None
    instance._generation = 1
    return instance


def history_without_lights():
    """Presence is fully evidenced on every day; the light has no data."""

    async def day_history(day, zone, entities):
        start, end = local_day_bounds(day, zone)
        events = {
            entity: [TimedState(start, "on" if entity == "binary_sensor.present" else "off")]
            if entity == "binary_sensor.present"
            else []
            for entity in entities
        }
        return events, [Coverage(start, end)]

    return AsyncMock(side_effect=day_history)


@pytest.mark.asyncio
async def test_diagnostics_explain_every_rejected_candidate():
    instance = runtime()
    instance.history.async_day = history_without_lights()
    with patch(
        "custom_components.lightaway.runtime.dt_util.now",
        return_value=datetime(2026, 11, 13, 18, tzinfo=ZONE),
    ):
        await instance._rebuild(instance._generation)

    payload = instance.diagnostics()
    assert payload["ready"] is True
    assert payload["computed_for"] == {"day": "2026-11-13", "time_zone": BERLIN}
    assert payload["lights"][0]["status"] == "insufficient_history"
    first = payload["candidates"][0]
    assert first["presence_seconds"] == 23 * 3600 or first["presence_seconds"] == 24 * 3600
    assert first["lights"]["light.a"] == {"seconds": 0, "valid": False}
    json.dumps(payload)


@pytest.mark.asyncio
async def test_candidate_evidence_is_bounded():
    instance = runtime()
    instance.history.async_day = AsyncMock(return_value=({}, []))
    with patch(
        "custom_components.lightaway.runtime.dt_util.now",
        return_value=datetime(2026, 11, 13, 18, tzinfo=ZONE),
    ):
        await instance._rebuild(instance._generation)
    payload = instance.diagnostics()
    assert len(payload["candidates"]) == MAX_CANDIDATES
    assert all(candidate["presence_seconds"] == 0 for candidate in payload["candidates"])
    json.dumps(payload)


@pytest.mark.asyncio
async def test_diagnostics_command_returns_the_runtime_report():
    instance = runtime()
    hass = SimpleNamespace(data={DOMAIN: {"entry": instance}})
    entry = SimpleNamespace(entry_id="entry")

    payload = await async_get_config_entry_diagnostics(hass, entry)

    assert payload["loaded"] is True
    assert payload["settings"]["presence"] == "binary_sensor.present"
    json.dumps(payload)


@pytest.mark.asyncio
async def test_diagnostics_of_an_unloaded_entry():
    hass = SimpleNamespace(data={DOMAIN: {}})
    payload = await async_get_config_entry_diagnostics(hass, SimpleNamespace(entry_id="missing"))
    assert payload == {"loaded": False}
