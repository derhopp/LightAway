"""WebSocket status and admin-only configuration contract tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.lightaway.const import DOMAIN
from custom_components.lightaway.websocket import async_register


@pytest.mark.asyncio
async def test_status_and_configuration_are_exposed():
    runtime = MagicMock()
    runtime.snapshot.return_value = {
        "settings": {"enabled": False, "lights": []},
        "lights": [],
        "presence_status": None,
        "ready": False,
    }
    runtime.async_configure = AsyncMock()
    hass = MagicMock()
    hass.data = {DOMAIN: {"instance": runtime}}
    connection = MagicMock()
    with patch(
        "custom_components.lightaway.websocket.websocket_api.async_register_command"
    ) as add_command:
        async_register(hass)
    assert add_command.call_count == 2
    status = add_command.call_args_list[0].args[1]
    configure = add_command.call_args_list[1].args[1]
    await status.__wrapped__(hass, connection, {"id": 1, "type": "lightaway/status"})
    connection.send_result.assert_called_with(1, runtime.snapshot.return_value)
    await configure.__wrapped__(
        hass,
        connection,
        {"id": 2, "type": "lightaway/configure", "enabled": True},
    )
    connection.require_admin.assert_called_once()
    runtime.async_configure.assert_awaited_once_with({"enabled": True})
    connection.send_result.assert_called_with(2, runtime.snapshot.return_value)
