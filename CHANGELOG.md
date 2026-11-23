# LightAway 0.4.1 Beta 4

**Opt-in pre-release.** Last known real Recorder states now carry across
Home Assistant restarts for both presence signals and lights, even if the
last change occurred months earlier. Recorder-offline intervals still
count as zero coverage, and the existing 23-hour qualifying threshold
remains unchanged. Historical transitions are replayed only on the
selected copy day.

- Fetch the last actual state before each run rather than limiting
  the query to the current Recorder run.
- Keep `unknown` and `unavailable` invalid and reject excessive
  within-day Recorder gaps.
- Regression tests cover 100+ day state intervals, multiple restarts,
  recorded light transitions and missing source states.
- MoreRecords 0.1.0b3 can certify complete CCU-Historian history even when
  Recorder contains additional identical samples; source changes and
  contradictions are still rejected.

No unrecorded changes can be inferred from an outage. Keep simulation
disabled for first-run verification.

---

# LightAway 0.4.1 Beta 3

**Pre-release / opt-in testing only.** This release is explicitly marked as a GitHub pre-release and is not Latest. Users who have excluded pre-releases in HACS / Home Assistant Marketplace continue to receive stable **v0.4.0**.

## Verified CCU-Historian continuity via MoreRecords

This beta adds support for source-backed historical intervals from the updated [MoreRecords](https://github.com/derhopp/MoreRecords) integration, without inventing Home Assistant Recorder runs. When a presence sensor stays `on` for weeks and CCU-Historian captured every state change, the absence of new HA Recorder samples need not invalidate the entire copy date.

- **MoreRecords** (updated code on `main`, **no MoreRecords release**) offers an explicit operator confirmation of *complete CCU-Historian event coverage*. It compares every returned source sample to the actual Recorder rows, then stores a local, entity-scoped interval with a SHA-256 content fingerprint. CSV and unverified imports are excluded.
- **LightAway** reads that optional evidence and verifies the fingerprint against the current Recorder database before treating the interval as continuous. Fingerprints are refreshed during each daily/configuration rebuild; edited or purged data fail closed.
- Certifications apply **per entity**, including the presence sensor and each light independently. Native RecorderRuns continue to apply outside verified intervals. The existing **23-hour** quality thresholds remain intact.
- Expanded synthetic tests cover silent multiweek presence, fingerprint mismatches, entity isolation and mixed native/imported intervals.
- The dashboard and existing diagnostic sensors remain unchanged.

## Install and test

1. Update MoreRecords from its latest `main` source (there is deliberately **no new MoreRecords release**) and restart Home Assistant.
2. In MoreRecords, open a **CCU-Historian** import or re-verification flow for each affected source entity. Select its original datapoint and complete time range. Previously imported observations can be verified even when there is nothing new to insert.
3. **Only confirm completeness if CCU-Historian captured every state change during that interval.** The first actual historian sample defines the beginning of coverage; missing initial states are not assumed. Recorder/source mismatch prevents certification.
4. Enable LightAway **Pre-release** in HACS / Marketplace; install **v0.4.1b3** and restart Home Assistant.
5. Keep simulation **off** initially. Trigger a copy-day recalculation, then inspect each light's **Copy day** and **Status** sensors.

This feature cannot retroactively prove that CCU-Historian never missed events. Existing MoreRecords imports are **not** automatically certified and must be verified explicitly. Invalid or stale evidence never qualifies a day. MoreRecords uses private, version-sensitive HA Recorder APIs: make a restorable Home Assistant backup first.

**Requirements:** HA 2026.10+, Recorder enabled and enough retained detailed states. Pre-release beta versions are intended for controlled testing. No user-provided CSV files, diagnostics, screenshots or real occupancy/activity data have been included.

[Stable v0.4.0](https://github.com/derhopp/LightAway/releases/tag/v0.4.0) remains unchanged.

---

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

---

# LightAway 0.4.1 Beta 1

**Pre-release – opt-in testing only.** This GitHub release is deliberately marked as a **pre-release**, not a stable or latest release. Users who do not enable pre-releases in HACS / the Home Assistant Marketplace continue to receive **v0.4.0**.

## What to test

This beta builds on LightAway 0.4.0 and focuses on the behavior of recent copy dates and Recorder history.

- **Local date consistency:** date selection, daily rebuild context and replay time use Home Assistant's configured local time zone explicitly, including near midnight.
- **Weekly search regression coverage:** with `Min. Weeks from today = 1` and no valid anniversary history, Monday **16 November 2026** uses **Monday 9 November 2026** before 2 November; Tuesday **17 November 2026** uses **Tuesday 10 November 2026** before 3 November, provided the target date qualifies.
- **Recorder state provenance:** diagnostics now show `in_day_records` and `carried_state_recorded_at` for presence and lights. A state recorded on 2/3 November can legitimately establish the *starting state* of 9/10 November if Recorder proves uninterrupted coverage; that does **not** replay older on/off transitions.
- **Coverage safety:** new regression tests verify that a gap on the candidate day is not concealed by an older starting state, and that only transitions from the selected day are used for replay.
- Updated README documentation explaining selected copy dates versus carried-forward Recorder states.

**Important:** Investigation did not establish a general one-week offset in the candidate-date algorithm. These changes improve time-zone handling, make the data origin auditable, and add targeted tests. Please verify the results on your own Recorder history before enabling automatic switching.

## Install through HACS / Marketplace

1. Open the LightAway repository in HACS / Marketplace.
2. Enable its **Pre-release** switch (it may initially be disabled or hidden among the repository's entities).
3. Refresh the repository information and select version **v0.4.1b1**.
4. Install, restart Home Assistant, and refresh the dashboard.
5. Test with **LightAway Simulation OFF** first. Compare copy dates, actual and desired states, and download diagnostics from **Settings → Devices & services → LightAway → Download diagnostics**.

If the beta is not offered immediately, refresh/reload the repository; catalog and update checks may be delayed.

To return to the stable channel, disable the **Pre-release** option and choose **v0.4.0** when reinstalling or selecting a version. Make a Home Assistant backup before changing versions.

**Privacy:** diagnostic exports contain entity IDs and potentially sensitive presence history. Review before sharing.

## Requirements and compatibility

Home Assistant 2026.10+ with Recorder and enough detailed history. Existing configuration is retained; this pre-release does not change the core eligibility rule that the recent fallback is skipped when `Max. Weeks away <= Min. Weeks from today`.

Stable release: [v0.4.0](https://github.com/derhopp/LightAway/releases/tag/v0.4.0). Its tag and manifest are not modified by this beta.

---

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

---

# LightAway 0.3.0

This release unifies the selected-light list and monitoring panel into one responsive view, and prevents the dashboard card from extending beyond its allotted width.

## Changes since v0.2.0

- **Unified lights and monitoring:** each configured light appears in exactly one row with its friendly name, entity ID, copy day, actual on/off state, calculated desired state, and diagnostic status.
- **Delete in place:** remove a light directly from its monitoring row using the trash icon. The single searchable light picker and Add button remain available above the list.
- **No horizontal overflow:** card width now stays within the Home Assistant dashboard column. Long names and entity IDs wrap instead of causing sideways scrolling.
- **Responsive monitoring:** metrics use four columns where space permits, two on narrower screens, and one on very narrow screens.
- **Live recalculation states:** the combined list continues to show progress and avoids displaying stale copy-day and desired-state values while history is rebuilding.
- Updated English documentation and added frontend regression tests for the combined layout, responsive sizing, values, and removal.

## Installation

Install or update the custom HACS integration `https://github.com/derhopp/LightAway` to **v0.3.0**, restart Home Assistant, and reload the dashboard. If the previous UI persists, perform a hard refresh to clear the cached card JavaScript.

To add the card manually:

```yaml
type: custom:lightaway-card
```

## Compatibility

- Requires Home Assistant 2026.10+ with Recorder enabled and sufficient detailed history.
- Existing configured lights, presence sensor, copy-day settings, and simulation preferences are preserved.
- No backend history-selection or light switching changes in this release.
- Initial simulation settings remain unchanged during upgrade; verify desired states before enabling actual light control.

---

# LightAway 0.2.0

LightAway 0.2 improves the dashboard configuration workflow and exposes the persistent toggle options as Home Assistant entities. This release contains all functionality of 0.1.0.

## What's new since 0.1.0

- **One light picker with an Add button.** Find a light by friendly name or entity ID, select it, then click **Add** below the picker. Selected lights appear in a separate list with a **trash icon** for removal. Changes persist automatically.
- **Wider, responsive dashboard card.** Up to 150% of the previous desktop column width where the dashboard layout permits; the card requests full section width in Sections dashboards. Mobile layouts remain responsive. Home Assistant controls Masonry column sizing.
- **Four persistent switches as integration entities**, all assigned to LightAway's device:
  - `switch.lightaway_simulation` — enable simulation
  - `switch.lightaway_invert_presence` — invert presence
  - `switch.lightaway_use_recent_weeks` — enable recent-week fallback
  - `switch.lightaway_just_same_copy_day` — require a common copy day for all lights
- Additional automated tests for the card's Add/Delete layout and persistent option switches, plus documentation updates.

## Installation / upgrade

1. Add `https://github.com/derhopp/LightAway` to HACS as a **custom integration repository**, or update your existing installation.
2. Select release **v0.2.0** and restart Home Assistant.
3. Reload the dashboard (clear browser cache if the old JavaScript card remains visible).

Manual Lovelace card YAML:

```yaml
type: custom:lightaway-card
```

**Requirements:** Home Assistant 2026.10+ with Recorder enabled. Copy-day calculations require enough retained detailed Recorder state history for the configured date windows.

**Compatibility:** Saved presence/light selections and simulation settings are retained. There are no changes to the historical eligibility or light service-call safety logic in this release. Add/Delete are one-shot UI actions and do not create entities. No new release automation is retained after publishing.

---

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
