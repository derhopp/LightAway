"""Per-light diagnostic entities for selected copy date and calculation status."""

from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_registry import async_get as async_get_registry

from .const import DOMAIN, UPDATE_SIGNAL


async def async_setup_entry(hass, entry, async_add_entities):
    """Track selected lights and create or remove both diagnostics per light."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    existing: dict[str, LightAwayDebugSensor] = {}

    @callback
    def sync_sensors():
        registry = async_get_registry(hass)
        desired: set[str] = set()
        new: list[LightAwayDebugSensor] = []

        for light in runtime.settings["lights"]:
            source = registry.async_get(light)
            stable = source.id if source else light
            for field in ("copy_day", "status"):
                unique = f"{entry.entry_id}_{stable}_{field}"
                desired.add(unique)
                if unique not in existing:
                    entity = LightAwayDebugSensor(runtime, light, field, unique)
                    existing[unique] = entity
                    new.append(entity)
                else:
                    existing[unique].light = light

        for unique, entity in list(existing.items()):
            if unique not in desired:
                if entity.entity_id and registry.async_get(entity.entity_id):
                    registry.async_remove(entity.entity_id)
                existing.pop(unique)

        if new:
            async_add_entities(new)

    sync_sensors()
    entry.async_on_unload(async_dispatcher_connect(hass, UPDATE_SIGNAL, sync_sensors))


class LightAwayDebugSensor(SensorEntity):
    """Expose the same copy-day and status fields used in the LightAway monitor."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime, light: str, field: str, unique_id: str):
        self.runtime = runtime
        self.light = light
        self.field = field
        self._attr_unique_id = unique_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, runtime.entry_id)},
            "name": "LightAway",
            "manufacturer": "LightAway",
        }
        self._attr_name = (
            f"{light.split('.', 1)[-1]} {'Copy day' if field == 'copy_day' else 'Status'}"
        )
        if field == "copy_day":
            self._attr_device_class = SensorDeviceClass.DATE

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(self.hass, UPDATE_SIGNAL, self._changed))

    @callback
    def _changed(self):
        if self.light not in self.runtime.settings["lights"]:
            registry = async_get_registry(self.hass)
            if self.entity_id and registry.async_get(self.entity_id):
                registry.async_remove(self.entity_id)
            return
        self.async_write_ha_state()

    @property
    def native_value(self):
        """Dates stay unknown during a rebuild; status stays observable."""
        if self.field == "status":
            if not self.runtime._ready:
                return "recalculating"
            return self.runtime.results.get(self.light, {}).get("status") or "pending"

        if not self.runtime._ready:
            return None
        value = self.runtime.results.get(self.light, {}).get("copy_day")
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except TypeError, ValueError:
            return None

    @property
    def extra_state_attributes(self):
        return {"source_entity": self.light}
