"""WebSocket status and admin-only configuration contract tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.exceptions import Unauthorized

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
    await configure.__wrapped__.__wrapped__(
        hass,
        connection,
        {"id": 2, "type": "lightaway/configure", "enabled": True},
    )
    # The former connection.require_admin() call did not exist on HA connections.
    assert not hasattr(type(connection), "require_admin")
    runtime.async_configure.assert_awaited_once_with({"enabled": True})
    connection.send_result.assert_called_with(2, runtime.snapshot.return_value)


@pytest.mark.asyncio
async def test_configure_requires_actual_websocket_admin_before_saving():
    """Use the registered HA decorator, not a non-existent connection method."""
    runtime = MagicMock()
    runtime.snapshot.return_value = {"settings": {"presence": "binary_sensor.holiday"}}
    runtime.async_configure = AsyncMock()
    hass = MagicMock()
    hass.data = {DOMAIN: {"instance": runtime}}
    connection = MagicMock()
    msg = {
        "id": 5,
        "type": "lightaway/configure",
        "presence": "binary_sensor.holiday",
    }
    with patch(
        "custom_components.lightaway.websocket.websocket_api.async_register_command"
    ) as add_command:
        async_register(hass)
    configure = add_command.call_args_list[1].args[1]
    connection.user = SimpleNamespace(is_admin=False)
    with pytest.raises(Unauthorized):
        configure(hass, connection, msg)
    runtime.async_configure.assert_not_awaited()
    hass.async_create_background_task.assert_not_called()

    connection.user = SimpleNamespace(is_admin=True)
    tasks = []
    hass.async_create_background_task.side_effect = lambda coro, _name, **_kwargs: tasks.append(
        coro
    )
    configure(hass, connection, msg)
    assert len(tasks) == 1
    await tasks.pop()
    runtime.async_configure.assert_awaited_once_with({"presence": "binary_sensor.holiday"})
    connection.send_result.assert_called_once_with(5, runtime.snapshot.return_value)


@pytest.mark.asyncio
async def test_rejected_configuration_is_reported_to_the_card():
    """An invalid range must surface as a user error, not a connection failure."""
    runtime = MagicMock()
    runtime.async_configure = AsyncMock(
        side_effect=ValueError("min_weeks_from_today must not be greater than max_weeks_away")
    )
    hass = MagicMock()
    hass.data = {DOMAIN: {"instance": runtime}}
    connection = MagicMock()
    connection.user = SimpleNamespace(is_admin=True)
    with patch(
        "custom_components.lightaway.websocket.websocket_api.async_register_command"
    ) as add_command:
        async_register(hass)
    configure = add_command.call_args_list[1].args[1]
    hass.async_create_background_task.side_effect = lambda coro, _name, **_kwargs: coro
    tasks = []

    def schedule(coro, _name, **kwargs):
        tasks.append(coro)

    hass.async_create_background_task.side_effect = schedule
    configure(hass, connection, {"id": 9, "type": "lightaway/configure", "max_weeks_away": 2})
    await tasks.pop()

    connection.send_error.assert_called_once_with(
        9, "invalid_config", "min_weeks_from_today must not be greater than max_weeks_away"
    )
    connection.send_result.assert_not_called()
