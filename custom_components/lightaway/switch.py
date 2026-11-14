"""Persistent LightAway configuration switches exposed as HA entities."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, UPDATE_SIGNAL


# Entity IDs / unique IDs must remain stable across integration updates.
_OPTION_SWITCHES = (
    ("invert", "Invert Presence", "invert_presence"),
    ("use_recent_weeks", "Use Recent Weeks", "use_recent_weeks"),
    ("just_same_copy_day", "Just Same Copy Day", "just_same_copy_day"),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Register the global simulation switch and every persistent toggle."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            LightAwaySwitch(runtime),
            *(
                LightAwayOptionSwitch(runtime, key, label, unique_suffix)
                for key, label, unique_suffix in _OPTION_SWITCHES
            ),
        ]
    )


class LightAwaySwitch(SwitchEntity):
    """The simulation preference persists, and safety gates are reevaluated."""

    _attr_name = "LightAway Simulation"
    _attr_should_poll = False

    def __init__(self, runtime):
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry_id}_simulation"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, runtime.entry_id)},
            "name": "LightAway",
            "manufacturer": "LightAway",
        }

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(self.hass, UPDATE_SIGNAL, self._changed))

    @callback
    def _changed(self):
        self.async_write_ha_state()

    @property
    def is_on(self):
        return self.runtime.settings["enabled"]

    async def async_turn_on(self, **kwargs):
        await self.runtime.async_configure({"enabled": True})

    async def async_turn_off(self, **kwargs):
        await self.runtime.async_configure({"enabled": False})


class LightAwayOptionSwitch(LightAwaySwitch):
    """A persistent configuration toggle, independently usable in automations."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime, key: str, label: str, unique_suffix: str):
        super().__init__(runtime)
        self._setting_key = key
        self._attr_name = f"LightAway {label}"
        self._attr_unique_id = f"{runtime.entry_id}_{unique_suffix}"

    @property
    def is_on(self):
        return bool(self.runtime.settings[self._setting_key])

    async def async_turn_on(self, **kwargs):
        await self.runtime.async_configure({self._setting_key: True})

    async def async_turn_off(self, **kwargs):
        await self.runtime.async_configure({self._setting_key: False})
