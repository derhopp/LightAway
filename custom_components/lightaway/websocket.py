"""Authenticated dashboard configuration and status API."""

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DOMAIN


def _week_count(minimum: int):
    """Accept only whole weeks in the configured range."""

    def validate(value):
        if type(value) is not int or not minimum <= value <= 52:
            raise vol.Invalid(f"Expected integer between {minimum} and 52")
        return value

    return validate


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
            vol.Optional("min_weeks_from_today"): _week_count(1),
            vol.Optional("max_weeks_away"): _week_count(2),
            vol.Optional("use_recent_weeks"): bool,
            vol.Optional("just_same_copy_day"): bool,
        }
    )
    @websocket_api.async_response
    async def configure(hass, connection, msg):
        runtime = next(iter(hass.data[DOMAIN].values()), None)
        if runtime is None:
            connection.send_error(msg["id"], "not_ready", "LightAway is not configured")
            return
        changes = {
            key: msg[key]
            for key in (
                "presence",
                "invert",
                "lights",
                "enabled",
                "min_weeks_from_today",
                "max_weeks_away",
                "use_recent_weeks",
                "just_same_copy_day",
            )
            if key in msg
        }
        try:
            await runtime.async_configure(changes)
        except ValueError as error:
            # Rejected input is a user error, not a broken command: report it so
            # the card can show the reason instead of a generic websocket error.
            connection.send_error(msg["id"], "invalid_config", str(error))
            return
        connection.send_result(msg["id"], runtime.snapshot())

    websocket_api.async_register_command(hass, status)
    websocket_api.async_register_command(hass, configure)
