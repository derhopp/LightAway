"""Integration smoke test through Home Assistant's config flow and entity registry."""

import pytest

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

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
