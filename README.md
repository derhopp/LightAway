# LightAway

LightAway is a Home Assistant custom integration that computes and optionally replays
the **binary on/off** behavior of individual lights from historical Recorder states
on matching weekdays near last year, with an optional recent-weeks fallback.

> **History prerequisite:** Home Assistant normally purges detailed Recorder state
> history after about ten days. The anniversary search needs about a year of
> detailed state history; recent-weeks fallback can work with shorter retention. Configure
> your own Recorder retention *before* you need that history. LightAway never
> changes Recorder settings or the database itself.

## Features

- Prioritized anniversary and recent-week copy-day search, with optional shared date
- 23 **elapsed** hours of proven presence and proven light state per reference day
- Read-only calculated binary sensors, even when replay is switched off
- Per-light diagnostic sensors for **Copy day** (date) and **Status** (text), accessible in Home Assistant history and automations
- Persistent enable, inversion, light selection, and weekly date-window options
- Strict fail-closed replay when presence or light state is unknown
- Lovelace dashboard configuration and monitoring, desktop and mobile
- Independent Home Assistant switches for simulation, presence inversion, recent weeks, and shared copy day
- English and German user interface, automatically selected by user language
- No fixed limit on configured lights
- Diagnostics download covering the full configured copy-day search with proven Recorder coverage
- Recalculation after a Home Assistant time zone change
- Optional, verified entity-scoped CCU-Historian provenance from MoreRecords
- Stable releases v0.1.0, v0.2.0, v0.3.0 and v0.4.0; opt-in test pre-release v0.4.1b1, v0.4.1b2, v0.4.1b3 and v0.4.1b4 (not marked latest). Further releases require explicit authorization

## Requirements

- Home Assistant 2026.10 or newer, with the Recorder integration enabled
- Recorder retaining enough **detailed state history** for eligible windows, not just
  aggregated long-term statistics
- Presence entity in `binary_sensor`, `switch`, or `input_boolean`
- Available `light.*` entities
- A HACS installation (or manual custom component installation)

SQLite and external Recorder databases are both supported via Home Assistant's
Recorder API and SQLAlchemy abstractions, not direct SQLite connections.

## HACS installation

1. In HACS, open the integration repositories list and add
   `https://github.com/derhopp/LightAway` as a **custom integration repository**.
2. Install the latest **stable** LightAway release (`v0.4.0`). The `main` branch is for development. For opt-in testing only, enable the repository's **Pre-release** switch in HACS / Marketplace and choose the pre-release `v0.4.1b5`.
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
provides searchable entity fields, presence inversion, a simulation switch,
and the four week-window and copy-day selection options. Find entities by friendly
name or entity ID. To add a light, choose it in the single light entity picker
and press **Add** below the picker. Each selected light appears once in a
combined **Lights & monitoring** list with its entity name/ID, copy day,
actual state, calculated desired state, diagnostic status, and trash icon
for removal. Both Add and Delete persist automatically.
Persistent toggle controls (simulation, invert presence, recent weeks, same
copy day) are also available as dedicated LightAway switch entities for
automations. Add/Delete are momentary UI actions rather than switch entities.

The card fits the available dashboard column width without extending outside
it or requiring horizontal scrolling. Each light is displayed as a responsive
row: on desktop four monitoring metrics appear side by side; on narrower
screens they wrap into two columns (or one on very small screens). Dashboard
column sizing remains controlled by Home Assistant.
The combined list displays the copy day, actual state, computed desired
state and diagnostic status for every light. A live progress indicator shows
when the integration is recalculating copy days, including after settings
changes or a daily refresh. Each calculated binary sensor
exposes the selected copy date as its `copy_day` attribute. All settings persist across
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

Add any number of `light.*` entries via the single native entity picker
and the Add button below it. Delete a configured light with its trash icon.
Each light gets a
read-only LightAway binary sensor and two diagnostic sensors grouped with the
global switch under the LightAway integration device. Removing a light from
the configuration removes all three entities from Home Assistant's entity registry.
A missing original light is shown as missing and is never operated.
Registry renames are tracked to preserve existing selections where possible.

## Per-light debugging sensors

LightAway creates **three entities per selected light** under the LightAway
integration device:

- A binary sensor for the calculated desired on/off state (unchanged).
- A **Copy day** sensor with Home Assistant's `date` device class. It exposes
  the actual historical date (for example `2026-11-13`) or `unknown`
  when no qualifying date exists or recalculation is underway.
- A **Status** diagnostic sensor with values such as `ok`,
  `recalculating`, `no_copy_day`, `insufficient_history`,
  `recorder_unavailable` and `light_unavailable`. It remains readable
  during recalculation, even when the copy date becomes unknown.

Both diagnostic sensors are assigned to the integration's LightAway device and
include a `source_entity` attribute. They update whenever LightAway sends a
state change, including when configuration changes and after day-boundary
rebuilds. Their unique IDs follow the same source entity-registry identity
strategy as the calculated binary sensor; deleting a configured light removes
its associated diagnostic entities. The sensors' names are based on the source
light ID; the exact generated entity IDs may differ when Home Assistant's
entity registry assigns a suffix.

To investigate a night-time replay gap, chart the **Copy day**, **Status**
and existing calculated binary sensor alongside the original light.
`Status=ok` indicates a valid current calculation, not proof that every
historical on/off transition has already been emitted. The global simulation
switch can remain off during diagnosis.

## Copy-day selection and settings

The dashboard exposes the following persistent options:

| Setting | Allowed values | Default |
| --- | --- | --- |
| Min. Weeks from today | Integer 1–52 | 1 |
| Max. Weeks away | Integer 2–52 | 8 |
| Use recent Weeks | Boolean | true |
| Just same copy day | Boolean | false |

**Priority 1 – anniversary window.** Search completed past local dates within
one calendar year ago ± **Max. Weeks away** weeks (inclusive). Feb 29 maps to
Feb 28 in non-leap years. Only dates with the same weekday as today are used.
Test the closest matching weekday to the anniversary first, proceeding outward;
equal-distance candidates prefer the earlier date.

**Priority 2 – recent weeks.** If the first window has no qualified date,
and **Use recent Weeks** is enabled and **Max. Weeks away** is greater than
**Min. Weeks from today**, search exactly 1-week-spaced dates from
today minus **Min. Weeks from today** through today minus **Max. Weeks away**
weeks (both endpoints inclusive), nearest first. Otherwise skip this priority.
If Min is equal to or greater than Max, only the recent fallback is omitted;
the annual search still applies and these settings are valid.

**Priority 3 – no eligible day.** If no candidate qualifies, LightAway
reports no copy day and does not switch the affected lights.

**Just same copy day = false**: each light independently takes its first
eligible candidate. **Just same copy day = true**: accept a date only if
the presence entity and *all* selected lights pass their independent
23-hour recording-quality checks on that *same date*. No partial copy
day is published if no shared day exists.

Every changed option triggers a fresh calculation. Existing installations
retain their previously selected presence and light entities; new options
receive the defaults above.

### Qualifications

A candidate passes only if at least 23 elapsed hours of the recorded day
show valid **present** presence and at least 23 elapsed hours show valid
`on` or `off` state for the light. Recording gaps and invalid states
never count toward qualification. Today and future dates are excluded.

## Recorder history reconstruction and data quality

**What a copy day means:** With a minimum distance of one week, Monday
16 November 2026 checks Monday **9 November 2026** before Monday 2 November;
Tuesday 17 November checks Tuesday **10 November 2026** before Tuesday
3 November. The annual candidate window has higher priority only if its
history qualifies. Day boundaries and local weekdays are always calculated in
the configured Home Assistant time zone.

A Recorder state last changed weeks or months before a candidate day
can still establish the **last known starting state**, for both presence
and each light, even across multiple Home Assistant Recorder restarts.
Only changes within the selected copy day are replayed; old events are
never replayed at their original dates. Diagnostics include
`in_day_records` and `carried_state_recorded_at` for both presence and
lights. A Recorder outage is not counted as observed time; a candidate day
still requires at least 23 eligible recorded hours.

Recorder stores state changes, not periodic samples. An entire day can be
valid without any changes when sufficient actual Recorder-run coverage
(or separately verified CCU-Historian coverage for that entity) exists
and there is a preceding genuine state sample. The last-known value is
carried into subsequent recorded intervals. An unrecorded state change
during an outage cannot be recovered or proven; for exact historical
continuity across downtime, certify a complete original CCU-Historian
source via MoreRecords.

Missing runs, uncovered periods, invalid state intervals and unverified
continuity count as zero. Neither an empty list of state changes nor a
synthetic starting point proves uninterrupted recording. Invalid historical
states are **never** made valid by the replay fallback.

An interrupted Recorder history may be too sparse to find an eligible day.
Extending retention now does not recreate already purged records.

## CCU-Historian verified coverage (MoreRecords)

LightAway normally requires genuine Home Assistant Recorder runs. For historical
states imported from CCU-Historian through **MoreRecords**, an entity may have
complete original source history even though HA itself was not running then.
An unchanged binary presence state might therefore be valid for weeks with
zero new transitions.

After an **explicit completeness confirmation** in an updated MoreRecords
CCU-Historian import/verification workflow, MoreRecords stores a local,
entity-scoped certificate in
`.storage/more_records_verified_history_v1`. It covers only the interval
from the **first real source sample** to the end of the successfully queried
range; CSVs are never certified. The user must be able to confirm that
CCU-Historian retained **all changes** throughout this interval.

LightAway accepts this alternative continuity proof only when it can recompute
and match the certificate's SHA-256 fingerprint against all Recorder rows in
the certified interval. A purged, modified, missing, incomplete or otherwise
unverified series is refused. The same certificate cannot qualify another
entity. Outside verified historical intervals, native Recorder run boundaries
and the established 23-hour thresholds apply. No artificial Recorder runs
are inserted. These checks can increase the cost of the first daily rebuild
for large imported histories.

**Existing MoreRecords imports are not automatically certified.** Reopen
MoreRecords' CCU-Historian import workflow for the same original datapoint,
select the verified period, and confirm completeness. If nothing needs to be
imported, the workflow can perform verification only after the source and
Recorder entries match exactly. Keep the simulation switch disabled while
testing; the provenance feature changes day *eligibility*, not replay safety.

## Playback and simulation

Desired states are recalculated at least every 30 seconds from cached
historical transitions, and calculated sensors remain visible whether the
global switch is enabled or disabled. Invalid historical playback values
reuse the preceding valid state. If none exists at the target time,
playback defaults to off **only after a reference day passed validation**.

Wall-clock time in the Home Assistant local timezone is used. Changing the
configured time zone invalidates cached copy days and triggers a rebuild;
previously calculated source days are never replayed against the new zone.
Recorded
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

For missing reference days, use **Settings → Devices & services → LightAway →
Download diagnostics**. The JSON report lists examined copy dates, the
search window (anniversary or recent), verified presence and light-state
coverage, and the number of candidates examined or omitted. The report
records at most 160 candidates, enough for the full supported search range.
It contains presence details and entity IDs: review before sharing publicly.
Also verify detailed Recorder retention for the presence entity and each light. A Recorder restart
without a reconfirming state may leave an unverifiable interval.
A missing presence sensor must be restored or replaced before any switching
can occur. Transient Recorder failures are retried on the next daily
rebuild or after an applicable configuration change.

## Performance

Historical queries are grouped by candidate date, with the presence entity
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

## Historical state-change histories predating Home Assistant Recorder

LightAway can use old state-change records already stored in Home Assistant
Recorder even if there were no actual Home Assistant `RecorderRuns` on that
historical date. When a real, entity-specific observation at or before the
candidate day's start and another observation **after** the candidate day's
end bound that date, LightAway can reconstruct the intervening states from
the stored changes. This applies independently to the presence sensor and
every chosen light.

This **bounded_state_history** mode is an *inference from last-known
states*, not evidence that the original CCU-Historian or Home Assistant
Recorder continuously captured all changes. Unknown intermediate changes
cannot be detected. It does **not** override known native Recorder gaps or
failed overlapping MoreRecords completeness certificates. Verifiably
complete CCU-Historian intervals still require explicit certification.

In downloaded diagnostics, `presence_coverage_sources` and per-light
`coverage_sources` distinguish `bounded_state_history` from `recorder`
and `ccu_historian_verified`. Review the results with simulation off before
allowing LightAway to operate lights.

