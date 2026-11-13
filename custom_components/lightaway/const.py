"""LightAway constants."""

DOMAIN = "lightaway"
PLATFORMS = ["binary_sensor", "switch"]
STORE_VERSION = 1
STORE_KEY = "lightaway.settings"
UPDATE_SIGNAL = "lightaway_update"
DEFAULT_OPTIONS = {
    "presence": None,
    "invert": False,
    "lights": [],
    "enabled": False,
}
MIN_SECONDS = 23 * 3600
