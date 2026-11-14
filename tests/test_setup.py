"""Integration smoke test through Home Assistant's config flow and entity registry."""

import pytest

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.lightaway.const import DOMAIN


@pytest.mark.asyncio
async def test_config_flow_and_global_switch(recorder_db_url, hass, recorder_mock):
    """A configured integration exposes its simulation switch immediately."""
    assert await async_setup_component(hass, DOMAIN, {})
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert flow["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert hass.states.get("switch.lightaway_simulation") is not None
    assert hass.states.get("switch.lightaway_simulation").state == "off"
    entity = er.async_get(hass).async_get("switch.lightaway_simulation")
    assert entity is not None and entity.device_id is not None
    device = dr.async_get(hass).async_get(entity.device_id)
    assert device is not None
    assert (
        "lightaway",
        hass.config_entries.async_entries(DOMAIN)[0].entry_id,
    ) in device.identifiers

@pytest.mark.asyncio
async def test_calculated_entities_update_from_recorder_result(recorder_db_url, hass, recorder_mock):
    """Regression: dashboard data and HA binary sensor must agree after a rebuild."""
    assert await async_setup_component(hass, DOMAIN, {})
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    runtime = hass.data[DOMAIN][entry.entry_id]
    runtime.request_rebuild = lambda: None
    await runtime.async_configure({"lights": ["light.test"]})
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    sensors = [
        entity for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        if entity.domain == "binary_sensor"
    ]
    assert len(sensors) == 1
    sensor_id = sensors[0].entity_id
    assert hass.states.get(sensor_id) is not None
    assert hass.states.get(sensor_id).state == "unavailable"

    runtime._ready = True
    runtime.results["light.test"] = {
        "copy_day": "2026-11-07",
        "desired": "on",
        "status": "ok",
        "timeline": None,
    }
    runtime._notify()
    await hass.async_block_till_done()
    assert hass.states.get(sensor_id).state == "on"
    assert hass.states.get(sensor_id).attributes["copy_day"] == "2026-11-07"

    runtime.results["light.test"]["desired"] = "off"
    runtime._notify()
    await hass.async_block_till_done()
    assert hass.states.get(sensor_id).state == "off"

    runtime._ready = False
    runtime.results["light.test"]["desired"] = None
    runtime._notify()
    await hass.async_block_till_done()
    assert hass.states.get(sensor_id).state == "unavailable"
