# LightAway 0.4.1 Beta 2

**Pre-release for opt-in testing.** This is a GitHub pre-release, not a stable or latest release. Users who do not enable pre-releases in HACS / Home Assistant Marketplace continue to receive the stable **v0.4.0**.

## What changed since v0.4.1b1

- Added two Home Assistant **diagnostic sensor entities for every selected light**, alongside the existing calculated binary sensor:
  - **Copy day**: a sensor with the Home Assistant `date` device class; shows the selected source date as YYYY-MM-DD or an unknown value if no date is available / the calculation is in progress.
  - **Status**: a text sensor exposing the current diagnostic status, such as `ok`, `recalculating`, `pending`, `no_copy_day`, `insufficient_history`, or `light_unavailable`.
- Both sensors belong to the integration's LightAway device, have stable unique IDs derived from the source light's registry identity and include the `source_entity` attribute.
- The two sensor entities are added and removed automatically when selected lights change. Their values follow the underlying runtime whenever calculations update and are available in Home Assistant's history/automation tools.
- Added tests for creation, updates, re-calculation, errors, removal, and device registration. Documented how to chart the new debug entities.

## Debugging nighttime playback

Track the **Copy day** and **Status** entities beside the calculated binary LightAway sensor. If the date and status remain consistent while the binary sensor stops following expected transitions, the failure is likely in desired-state updates or event delivery, rather than source-date selection. Status `ok` means the calculation is considered valid, not that all expected transitions were actually seen in the Home Assistant history chart.

The original replay engine is **not modified** in this beta. Keep simulation disabled when first checking the new telemetry.

## Installation

1. Open LightAway in HACS / Marketplace and enable **Pre-release** for this repository.
2. Choose version **v0.4.1b2**, install it, and restart Home Assistant.
3. Check the LightAway device's diagnostic entities in **Settings → Devices & services → LightAway**. If diagnostic entities are initially collapsed, expand them.
4. Add these sensors to a History graph to compare with the existing calculated light state sensors.

Disable Pre-release and explicitly select stable v0.4.0 if you need to return to the stable track. Existing settings and selected entities remain intact.

**Privacy:** Please do not share unredacted diagnostics or history exports publicly. No private historical observations or user-provided diagnostic data are included in this release.

**Requirements:** Home Assistant 2026.10+ with Recorder and adequate detailed history retention.
