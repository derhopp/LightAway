"""LightAway integration initialization and one-time dashboard resource setup."""

from pathlib import Path
import logging

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS
from .runtime import LightAwayRuntime
from .websocket import async_register

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)
CARD_URL = "/lightaway/lightaway-card.js"
CARD_PATH = Path(__file__).parent / "frontend" / "lightaway-card.js"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    async_register(hass)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_PATH), cache_headers=False)]
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    runtime = LightAwayRuntime(hass, entry.entry_id)
    hass.data[DOMAIN][entry.entry_id] = runtime
    await runtime.async_load()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Register the card automatically when Lovelace is in storage mode.
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA

        lovelace = hass.data.get(LOVELACE_DATA)
        if lovelace and lovelace.resource_mode == "storage":
            collection = lovelace.resources
            await collection.async_get_info()
            if not any(
                r.get("url", "").split("?")[0] == CARD_URL for r in collection.async_items()
            ):
                await collection.async_create_item({"res_type": "module", "url": CARD_URL})
    except Exception:
        _LOGGER.warning(
            "Could not register LightAway dashboard resource automatically; "
            "add %s as a JavaScript module in Dashboard resources",
            CARD_URL,
            exc_info=True,
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    runtime = hass.data[DOMAIN].pop(entry.entry_id)
    await runtime.async_unload()
    return True
