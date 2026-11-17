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
