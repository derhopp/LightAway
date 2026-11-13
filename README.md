# LightAway

LightAway is a Home Assistant custom integration that computes and optionally replays
the **binary on/off** behavior of individual lights from historical Recorder states
on comparable weekdays roughly one year earlier.

> **History prerequisite:** Home Assistant normally purges detailed Recorder state
> history after about ten days. LightAway needs at least **one year of retained
> state history** for both the selected presence entity and each light. Configure
> your own Recorder retention *before* you need that history. LightAway never
> changes Recorder settings or the database itself.

## Features

- Independent original-day selection per light, forward in seven-day increments
- 23 **elapsed** hours of proven presence and proven light state per reference day
- Read-only calculated binary sensors, even when replay is switched off
- Persistent enable preference, presence inversion, and light selection
- Strict fail-closed replay when presence or light state is unknown
- Lovelace dashboard configuration and monitoring, desktop and mobile
- English and German user interface, automatically selected by user language
- No fixed limit on configured lights
- No releases, tags or automated publishing workflows

## Requirements

- Home Assistant 2026.10 or newer, with the Recorder integration enabled
- Recorder retaining a year or more of **detailed state history**, not just
  aggregated long-term statistics
- Presence entity in `binary_sensor`, `switch`, or `input_boolean`
- Available `light.*` entities
- A HACS installation (or manual custom component installation)

SQLite and external Recorder databases are both supported via Home Assistant's
Recorder API and SQLAlchemy abstractions, not direct SQLite connections.

## HACS installation

1. In HACS, open the integration repositories list and add
   `https://github.com/derhopp/LightAway` as a **custom integration repository**.
2. Install LightAway from the `main` branch. Releases are not required.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → LightAway**.
5. In your dashboard, add a **Manual** card:

   ```yaml
   type: custom:lightaway-card
   ```

In storage-mode dashboards, LightAway attempts to register its JavaScript
module automatically at `/lightaway/lightaway-card.js`. In YAML-mode
dashboards or if registration fails, add a dashboard JavaScript module
resource with that URL manually.

## Initial setup and dashboard configuration

Integration setup creates a single LightAway instance. The dashboard card
provides native Home Assistant searchable entity fields for one presence entity
and any number of lights, an adjacent presence inversion switch, and a global
simulation switch. Find entities by friendly name or entity ID. To add a light,
use the empty search field; to remove one, clear its populated field. Settings
are saved automatically, without a Save button.
The status table displays the original day, actual state, computed desired
state and diagnostic status for every light. All settings persist across
Home Assistant restarts. The global simulation setting defaults to off.

On restart, a previously enabled simulation **never** switches anything
until the fresh reference days and current safety conditions have been verified.

## Presence configuration and inversion

A presence state of `on`, `true` or `1` means present; `off`,
`false` or `0` means absent. Inversion swaps only valid binary states.
Missing, `unknown`, `unavailable` and other values remain invalid.
Historically invalid presence does not count as present. Currently invalid
presence blocks **all** light service calls.

## Managing light entities

Search for any number of `light.*` entries using the native entity pickers.
Each light gets a
read-only LightAway binary sensor. Removing a light from the configuration
removes its calculated sensor from Home Assistant's entity registry.
A missing original light is shown as missing and is never operated.
Registry renames are tracked to preserve existing selections where possible.

## Original-day selection

For each light separately, the ideal reference date is today's local date
minus one calendar year (Feb 29 maps to Feb 28). The first candidate is the
first date on or after that ideal date with the **same weekday** as today.
Further candidates are seven calendar days apart. The final allowed candidate
is one calendar month before today (month subtraction clamps the day).

A candidate passes only if at least 23 elapsed hours of the recorded day
show valid, **present** presence *and* at least 23 elapsed hours show valid
`on` or `off` state for that light. The first passing day wins.
Different lights may therefore choose different dates. A light without a
passing reference day is unavailable, not falsely reported off.

## Recorder history reconstruction and data quality

Recorder stores state changes, not periodic samples. An entire day can be
valid without any changes **when recording coverage and a preceding real
state within the same Recorder run establish continuity**. The algorithm
loads real Recorder states and the boundaries of completed Recorder runs,
uses a genuine pre-day sample only if it is within that same run, and
counts only the time where both a state and recording continuity are proven.

Missing runs, uncovered periods, invalid state intervals and unverified
continuity count as zero. Neither an empty list of state changes nor a
synthetic starting point proves uninterrupted recording. Invalid historical
states are **never** made valid by the replay fallback.

An interrupted Recorder history may be too sparse to find an eligible day.
Extending retention now does not recreate already purged records.

## Playback and simulation

Desired states are recalculated at least every 30 seconds from cached
historical transitions, and calculated sensors remain visible whether the
global switch is enabled or disabled. Invalid historical playback values
reuse the preceding valid state. If none exists at the target time,
playback defaults to off **only after a reference day passed validation**.

Wall-clock time in the Home Assistant local timezone is used. Recorded
interval durations are computed using UTC timestamps, including for 23- and
25-hour days. On repeated fall-back clock hours, matching fold occurrences
are selected when present; on a normal day the first matching occurrence
is used in that hour. A skipped spring-forward clock time simply never
appears in the historic event sequence.

A light receives a regular `light.turn_on` or `light.turn_off` service call
only when **all** gates pass: global enable, definitely absent presence,
available source light with known binary state, eligible reference day,
valid computed desired state and no active safety error. No brightness,
color, transition or effect information is replayed. Divergent lights are
corrected during the next reconciliation. When the user comes home, is
unknown, or disables simulation, LightAway stops sending commands but never
restores earlier physical states.

## Errors and troubleshooting

The table distinguishes absent reference days, unavailable Recorder data,
deleted or unavailable lights, calculation errors and service call failures.
Every light is assessed independently. Check **Settings → System → Logs**
for detailed tracebacks.

For missing reference days, verify the full year of detailed Recorder state
retention for both the presence entity and the light. A Recorder restart
without a reconfirming state may leave an unverifiable interval.
A missing presence sensor must be restored or replaced before any switching
can occur. Transient Recorder failures are retried on the next daily
rebuild or after an applicable configuration change.

## Performance

Historical queries are grouped by reference date, with the presence entity
shared across remaining candidates. Once reference days are determined,
the 30-second tick uses cached transitions and performs **no** historical
database reads. The algorithm stops searching individually for each light
once its first eligible day is found. Large installations can have expensive
initial history scans; keep an eye on Recorder database size and performance.

## Development and testing

Run locally in a virtual environment with a compatible Home Assistant:

```sh
python -m pip install -r requirements_test.txt
pytest -q
ruff check .
ruff format --check .
```

GitHub Actions runs tests, style validation, HACS validation and hassfest
validation. No workflow publishes releases or Git tags.

## Known limitations

- Only on/off behavior is simulated. Brightness, color and effects are ignored.
- Historical availability depends on retained Recorder state and run metadata;
  unsupported/incomplete coverage fails closed rather than guessing.
- No user-triggered arbitrary reference date overrides in version 0.1.
- Automatic Lovelace resource registration is available only in storage mode.
- Daily historical scans can take time with many lights and a year of history.
