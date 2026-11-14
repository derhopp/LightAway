"""Diagnostics support: why a copy day was selected or rejected."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry) -> dict[str, Any]:
    """Return a JSON-safe report for Settings > Devices > Download diagnostics.

    Besides the stored preferences this lists, per configured light, which copy
    day was used, its status, and how many seconds of evidence each rejected
    candidate day carried. That is what turns "no suitable copy day" into an
    actionable Recorder-retention question.
    """
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if runtime is None:
        return {"loaded": False}
    return {"loaded": True, **runtime.diagnostics()}
