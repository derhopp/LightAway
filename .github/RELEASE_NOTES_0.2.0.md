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
