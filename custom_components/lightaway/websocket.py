"""Authenticated dashboard configuration and status API."""

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DOMAIN


def async_register(hass: HomeAssistant) -> None:
    @websocket_api.websocket_command({vol.Required("type"): "lightaway/status"})
    @websocket_api.async_response
    async def status(hass, connection, msg):
        runtime = next(iter(hass.data[DOMAIN].values()), None)
        if runtime is None:
            connection.send_error(msg["id"], "not_ready", "LightAway is not configured")
            return
        connection.send_result(msg["id"], runtime.snapshot())

    @websocket_api.require_admin
    @websocket_api.websocket_command(
        {
            vol.Required("type"): "lightaway/configure",
            vol.Optional("presence"): vol.Any(
                None, vol.Match(r"^(binary_sensor|switch|input_boolean)\.[a-z0-9_]+$")
            ),
            vol.Optional("invert"): bool,
            vol.Optional("lights"): [vol.Match(r"^light\.[a-z0-9_]+$")],
            vol.Optional("enabled"): bool,
        }
    )
    @websocket_api.async_response
    async def configure(hass, connection, msg):
        runtime = next(iter(hass.data[DOMAIN].values()), None)
        if runtime is None:
            connection.send_error(msg["id"], "not_ready", "LightAway is not configured")
            return
        changes = {
            key: msg[key] for key in ("presence", "invert", "lights", "enabled") if key in msg
        }
        await runtime.async_configure(changes)
        connection.send_result(msg["id"], runtime.snapshot())

    websocket_api.async_register_command(hass, status)
    websocket_api.async_register_command(hass, configure)
