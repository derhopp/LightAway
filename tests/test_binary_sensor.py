"""Calculated binary sensors: creation, live updates and removal."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.lightaway.const import DOMAIN

pytestmark = pytest.mark.recorder_db


def sensors(hass):
    """Entity IDs of the calculated sensors, in registry order."""
    return sorted(
        state.entity_id
        for state in hass.states.async_all()
        if state.entity_id.startswith("binary_sensor.") and state.entity_id.endswith("_lightaway")
    )


async def start(hass):
    """Set up the integration and return a runtime with empty history."""
    hass.states.async_set("binary_sensor.present", "off")
    hass.states.async_set("light.a", "off")
    hass.states.async_set("light.b", "off")
    assert await async_setup_component(hass, DOMAIN, {})
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    runtime = hass.data[DOMAIN][entry.entry_id]
    runtime.history.async_day = AsyncMock(return_value=({}, []))
    return runtime


@pytest.mark.asyncio
async def test_sensors_follow_the_configured_lights(hass):
    """A light configured in the card gets a sensor without a restart."""
    runtime = await start(hass)
    await runtime.async_configure(
        {"presence": "binary_sensor.present", "lights": ["light.a", "light.b"]}
    )
    await hass.async_block_till_done()
    assert len(sensors(hass)) == 2

    await runtime.async_configure({"lights": ["light.a"]})
    await hass.async_block_till_done()
    assert len(sensors(hass)) == 1

    await runtime.async_configure({"lights": ["light.a", "light.b"]})
    await hass.async_block_till_done()
    assert len(sensors(hass)) == 2
    registered = er.async_get(hass)
    assert all(registered.async_get(entity_id) is not None for entity_id in sensors(hass))


@pytest.mark.asyncio
async def test_sensor_state_writes_land_on_the_event_loop(hass):
    """Updates must be callbacks, not executor jobs, and reach the sensor."""
    runtime = await start(hass)
    await runtime.async_configure({"presence": "binary_sensor.present", "lights": ["light.a"]})
    await hass.async_block_till_done()
    entity_id = sensors(hass)[0]
    assert hass.states.get(entity_id).state == "unavailable"

    runtime.results["light.a"]["desired"] = "on"
    runtime._notify()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"
    assert hass.states.get(entity_id).attributes["copy_day"] is None

    runtime.results["light.a"]["desired"] = "off"
    runtime._notify()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "off"


@pytest.mark.asyncio
async def test_updates_never_touch_home_assistant_state_off_loop(hass, caplog):
    """The dispatcher must not run these listeners in an executor thread."""
    runtime = await start(hass)
    caplog.clear()
    await runtime.async_configure({"presence": "binary_sensor.present", "lights": ["light.a"]})
    runtime.results["light.a"]["desired"] = "on"
    runtime._notify()
    await hass.async_block_till_done()
    assert "thread other than the event loop" not in caplog.text
    assert "no running event loop" not in caplog.text
