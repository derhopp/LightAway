"""Integration-level diagnostics: date/status lifecycle for configured lights."""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.lightaway.const import DOMAIN
from custom_components.lightaway.sensor import LightAwayDebugSensor

pytestmark = pytest.mark.recorder_db


async def setup_runtime(hass):
    hass.states.async_set("light.test_a", "off")
    hass.states.async_set("light.test_b", "off")
    assert await async_setup_component(hass, DOMAIN, {})
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    runtime = hass.data[DOMAIN][entry.entry_id]
    runtime.request_rebuild = lambda: None
    runtime.store.async_save = AsyncMock()
    return entry, runtime


def debug_entities(hass, entry):
    registry = er.async_get(hass)
    return {
        item.unique_id: item
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        if item.domain == "sensor"
    }


@pytest.mark.asyncio
async def test_copy_day_and_status_entities_add_change_and_remove(hass):
    entry, runtime = await setup_runtime(hass)
    await runtime.async_configure({"lights": ["light.test_a", "light.test_b"]})
    await hass.async_block_till_done()

    entities = debug_entities(hass, entry)
    assert len(entities) == 4
    assert len({item.unique_id for item in entities.values()}) == 4
    assert all(item.device_id for item in entities.values())
    device = dr.async_get(hass).async_get(next(iter(entities.values())).device_id)
    assert (DOMAIN, entry.entry_id) in device.identifiers
    assert all(item.device_id == device.id for item in entities.values())

    a_date = entities[f"{entry.entry_id}_light.test_a_copy_day"].entity_id
    a_status = entities[f"{entry.entry_id}_light.test_a_status"].entity_id
    assert hass.states.get(a_date).state == "unknown"
    assert hass.states.get(a_status).state == "pending"

    runtime.results = {
        "light.test_a": {"copy_day": "2026-11-13", "status": "ok", "desired": "on"},
        "light.test_b": {
            "copy_day": None,
            "status": "insufficient_history",
            "desired": None,
        },
    }
    runtime._ready = True
    runtime._notify()
    await hass.async_block_till_done()
    assert hass.states.get(a_date).state == "2026-11-13"
    assert hass.states.get(a_status).state == "ok"
    assert hass.states.get(a_date).attributes["source_entity"] == "light.test_a"
    b_status = entities[f"{entry.entry_id}_light.test_b_status"].entity_id
    b_date = entities[f"{entry.entry_id}_light.test_b_copy_day"].entity_id
    assert hass.states.get(b_status).state == "insufficient_history"
    assert hass.states.get(b_date).state == "unknown"

    runtime._ready = False
    runtime._notify()
    await hass.async_block_till_done()
    assert hass.states.get(a_status).state == "recalculating"
    assert hass.states.get(a_date).state == "unknown"

    runtime._ready = True
    runtime.results["light.test_a"].update(
        {"copy_day": "2026-11-06", "status": "light_unavailable"}
    )
    runtime._notify()
    await hass.async_block_till_done()
    assert hass.states.get(a_date).state == "2026-11-06"
    assert hass.states.get(a_status).state == "light_unavailable"

    await runtime.async_configure({"lights": ["light.test_a"]})
    await hass.async_block_till_done()
    assert len(debug_entities(hass, entry)) == 2
    assert er.async_get(hass).async_get(b_date) is None
    assert er.async_get(hass).async_get(b_status) is None

    await runtime.async_configure({"lights": ["light.test_a", "light.test_b"]})
    await hass.async_block_till_done()
    assert len(debug_entities(hass, entry)) == 4
    assert f"{entry.entry_id}_light.test_b_copy_day" in debug_entities(hass, entry)


def test_native_date_and_status_values_are_safe_during_recalculation():
    class Runtime:
        entry_id = "test"
        _ready = True
        settings = {"lights": ["light.a"]}
        results = {"light.a": {"copy_day": "2026-11-13", "status": "ok"}}

    runtime = Runtime()
    copy = LightAwayDebugSensor(runtime, "light.a", "copy_day", "copy")
    status = LightAwayDebugSensor(runtime, "light.a", "status", "status")
    assert copy.device_class == SensorDeviceClass.DATE
    assert copy.native_value == date(2026, 11, 13)
    assert status.native_value == "ok"

    runtime._ready = False
    assert copy.native_value is None
    assert status.native_value == "recalculating"

    runtime._ready = True
    runtime.results["light.a"] = {"copy_day": "invalid-date", "status": "no_copy_day"}
    assert copy.native_value is None
    assert status.native_value == "no_copy_day"
