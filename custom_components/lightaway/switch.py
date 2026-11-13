"""Global persistent simulation enable control."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, UPDATE_SIGNAL


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([LightAwaySwitch(hass.data[DOMAIN][entry.entry_id])])


class LightAwaySwitch(SwitchEntity):
    """The enable preference persists, but safety gates are always reevaluated."""

    _attr_name = "LightAway Simulation"
    _attr_should_poll = False

    def __init__(self, runtime):
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry_id}_simulation"

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(self.hass, UPDATE_SIGNAL, self.async_write_ha_state)
        )

    @property
    def is_on(self):
        return self.runtime.settings["enabled"]

    async def async_turn_on(self, **kwargs):
        await self.runtime.async_configure({"enabled": True})

    async def async_turn_off(self, **kwargs):
        await self.runtime.async_configure({"enabled": False})
