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
