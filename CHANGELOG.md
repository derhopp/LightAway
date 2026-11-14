# LightAway 0.1.0 — Initial release

First public release of the **LightAway** Home Assistant custom integration.

## Features
- Automatic copy-day selection from matching weekdays around the date one year ago; configurable recent-week fallback
- Configurable `Min. Weeks from today` (1–52), `Max. Weeks away` (2–52), `Use recent Weeks`, and `Just same copy day`
- Independent copy days for individual lights, or an optional single day qualified for all selected lights
- Recorder-backed verification of at least 23 hours of reliable historical presence and light states per candidate day
- Read-only calculated binary sensors for the desired on/off state, assigned to the LightAway integration device
- Persistent global simulation switch with strict safety checks; no light calls while the source state or current presence is unknown
- Lovelace dashboard card with searchable Home Assistant entity pickers, automatic saving, live monitoring and rebuild progress
- English and German interface
- Automated validation with Python, frontend tests, hassfest, and HACS checks

## Installation
Add `https://github.com/derhopp/LightAway` in HACS as a **custom integration repository**, install release **v0.1.0**, and restart Home Assistant. Add a manual dashboard card using:

```yaml
type: custom:lightaway-card
```

## Requirements and notes
- Home Assistant 2026.10 or later, with Recorder enabled
- Enough **detailed state history** retained for candidate copy days; Home Assistant's default short Recorder retention generally does not cover the anniversary window
- This release re-labels the initial codebase version as **0.1.0** for the first published version. Previous development builds used an internal manifest version of 0.2.1; the source code incorporates those changes.
- The simulated states are **on/off only**; brightness, color and effects are not replayed
- Initial simulation is disabled for safety. Always verify copy-day calculations and desired values before enabling automation

Full configuration and troubleshooting instructions: [README](https://github.com/derhopp/LightAway/blob/main/README.md).
