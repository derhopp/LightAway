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
    assert first["lights"]["light.a"]["seconds"] == 0
    assert first["lights"]["light.a"]["valid"] is False
    assert first["lights"]["light.a"]["in_day_records"] == 0
    assert first["lights"]["light.a"]["carried_state_recorded_at"] is None
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
    from custom_components.lightaway.model import candidate_days

    expected = len(list(candidate_days(TODAY)))
    assert expected > 12
    assert len(payload["candidates"]) == expected
    assert payload["candidates_examined"] == expected
    assert payload["candidates_omitted"] == 0
    assert MAX_CANDIDATES >= expected
    assert payload["candidates"][-1]["search_window"] == "recent"
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


@pytest.mark.asyncio
async def test_maximum_week_window_keeps_anniversary_and_recent_evidence():
    """The largest allowed interval must retain every examined candidate."""
    from custom_components.lightaway.model import candidate_days

    instance = runtime()
    instance.settings.update({"min_weeks_from_today": 1, "max_weeks_away": 52})
    instance.history.async_day = AsyncMock(return_value=({}, []))
    with patch(
        "custom_components.lightaway.runtime.dt_util.now",
        return_value=datetime(2026, 11, 13, 18, tzinfo=ZONE),
    ):
        await instance._rebuild(instance._generation)
    report = instance.diagnostics()
    expected = len(list(candidate_days(TODAY, max_weeks_away=52)))
    assert len(report["candidates"]) == expected
    assert report["candidates_examined"] == expected
    assert report["candidates_omitted"] == 0
    assert expected <= MAX_CANDIDATES
    assert report["candidates"][0]["search_window"] == "anniversary"
    # At 52 weeks, recent days overlap the annual window and are deduplicated.
    assert report["candidates"][-1]["search_window"] == "anniversary"
    assert len({candidate["day"] for candidate in report["candidates"]}) == expected
    json.dumps(report)
