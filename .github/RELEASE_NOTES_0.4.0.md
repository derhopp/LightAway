# LightAway 0.4.0

Version 0.4.0 focuses on reliability, safer configuration, and more transparent history diagnostics. It includes the selectively integrated improvements from [PR #1](https://github.com/derhopp/LightAway/pull/1) via the reviewed and tested [PR #2](https://github.com/derhopp/LightAway/pull/2), on top of the responsive dashboard from 0.3.0.

## Changes since 0.3.0

- **Correct listener cleanup:** release the entity state listener and other callbacks when the LightAway configuration entry is unloaded, including repeated unloads. This avoids stale subscriptions after reloads.
- **Time-zone-safe copy days:** a Home Assistant time-zone change invalidates the cached historical context and triggers recalculation. LightAway does not replay data from a stale day/time-zone combination.
- **Stronger settings validation:** validate light and presence entity IDs, expected entity domains, boolean options, and week-range types. Invalid configuration requests return useful WebSocket errors; automatically repaired invalid stored values are saved.
- **Downloadable diagnostics:** Home Assistant's standard integration diagnostics include the configuration, computed local day and time zone, light statuses and selected copy dates, as well as observed presence/light coverage for candidates in the anniversary and recent windows.
- **Complete candidate evidence:** a capacity of up to 160 candidates and examined/omitted counts covers the entire supported 52-week search range, including overlapping annual/recent windows.
- **More regression coverage:** listener lifecycle, diagnostics, settings, time-zone safety and sensor behavior are covered by additional automated tests.

**Preserved behaviors:** the unified, compact 0.3.0 dashboard remains unchanged. The established rule that the *recent* fallback is skipped when `Max. Weeks away <= Min. Weeks from today` remains in place; the anniversary search is still evaluated. There is no new light replay logic in this release.

## Thanks to the contributor

A special thank-you to **[@ghostfix-pm](https://github.com/ghostfix-pm)**, the author of [PR #1](https://github.com/derhopp/LightAway/pull/1), for thoughtfully investigating the calculated-sensor update issues, listener lifecycle, time-zone handling, input validation, and the need for better diagnostics. The detailed analysis, proposed fixes, and tests were valuable groundwork for this release. We adapted the applicable changes in [PR #2](https://github.com/derhopp/LightAway/pull/2) to fit the current codebase and retain LightAway's intended copy-day rules. Thank you for helping make LightAway more reliable!

## Installation and upgrade

Install or update the HACS custom integration `https://github.com/derhopp/LightAway` to **v0.4.0**, restart Home Assistant, and refresh the dashboard. To add the card manually:

```yaml
type: custom:lightaway-card
```

**Requirements:** Home Assistant 2026.10 or newer with Recorder and adequate detailed state-history retention for the selected copy-day windows.

**Diagnostics privacy:** diagnostic exports can contain entity IDs and information about presence history. Review them before sharing publicly.

Saved preferences and entity selections are preserved. No automatic release/tag publishing remains active after this version is published.
