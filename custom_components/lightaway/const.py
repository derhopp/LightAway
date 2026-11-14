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
    "min_weeks_from_today": 1,
    "max_weeks_away": 8,
    "use_recent_weeks": True,
    "just_same_copy_day": False,
}
MIN_SECONDS = 23 * 3600
