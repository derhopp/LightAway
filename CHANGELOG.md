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
