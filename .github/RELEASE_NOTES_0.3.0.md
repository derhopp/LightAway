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
