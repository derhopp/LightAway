"""Read-only calculated light states."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_registry import async_get as async_get_registry

from .const import DOMAIN, UPDATE_SIGNAL


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = hass.data[DOMAIN][entry.entry_id]
    existing = {}

    def add_missing():
        new = []
        registry = async_get_registry(hass)
        allowed = set(runtime.settings["lights"])
        for uid, sensor in list(existing.items()):
            if sensor.light not in allowed:
                if sensor.entity_id and registry.async_get(sensor.entity_id):
                    registry.async_remove(sensor.entity_id)
                existing.pop(uid)
        for light in runtime.settings["lights"]:
            registry_entry = registry.async_get(light)
            stable = registry_entry.id if registry_entry else light
            unique = f"{entry.entry_id}_{stable}"
            if unique not in existing:
                sensor = LightAwayCalculated(runtime, light, unique)
                existing[unique] = sensor
                new.append(sensor)
            else:
                existing[unique].light = light
        if new:
            async_add_entities(new)

    add_missing()
    entry.async_on_unload(async_dispatcher_connect(hass, UPDATE_SIGNAL, add_missing))


class LightAwayCalculated(BinarySensorEntity):
    """Cached state is available even when the simulation is disabled."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runtime, light, unique_id):
        self.runtime = runtime
        self.light = light
        self._attr_unique_id = unique_id
        self._attr_name = f"{light.split('.', 1)[-1]} LightAway"

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(self.hass, UPDATE_SIGNAL, self._changed))

    def _changed(self):
        if self.light not in self.runtime.settings["lights"]:
            registry = async_get_registry(self.hass)
            if self.entity_id and (entry := registry.async_get(self.entity_id)):
                registry.async_remove(entry.entity_id)
            return
        self.async_write_ha_state()

    @property
    def available(self):
        return self.runtime.results.get(self.light, {}).get("desired") in ("on", "off")

    @property
    def is_on(self):
        return self.runtime.results.get(self.light, {}).get("desired") == "on"

    @property
    def extra_state_attributes(self):
        result = self.runtime.results.get(self.light, {})
        return {
            "source_entity": self.light,
            "original_day": result.get("original_day"),
            "diagnostic": result.get("status"),
        }
