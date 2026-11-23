# LightAway 0.4.1 Beta 5

**Opt-in pre-release.** Stable LightAway v0.4.0 remains unchanged.

## Fix: genuine imported histories older than RecorderRuns

On Monday 23 November 2026, the most relevant same-weekday anniversary candidate is Monday 24 November 2025. A genuine `binary_sensor.test_anwesenheit_2` observation on 12 November 2025 (`on`) and a later observation on 24 March 2026 (`off`) bracket that candidate; the old algorithm rejected it with **0 eligible seconds** because historical Home Assistant RecorderRuns did not exist.

- If a candidate day has **no native RecorderRun**, each entity can now independently use its existing state-change history when a genuine Recorder row exists **at/before the day's start** and another row **after the day's end**.
- Applies to **both presence and light entities**. All recorded transitions on the selected day are replayed; values last changed many weeks earlier are carried forward.
- An entity with missing preceding or later evidence is not accepted. A known native Recorder gap is not replaced with inferred all-day coverage. Invalid `unknown`/`unavailable` states remain invalid.
- Entity-specific verified CCU-Historian coverage still takes priority. A failed/intersecting certificate is not circumvented with a weaker inference.
- Diagnostics now show `presence_coverage_sources` and `coverage_sources` per light, distinguishing `recorder`, `ccu_historian_verified`, and `bounded_state_history`.
- Regression tests cover the November 2025 → March 2026 sparse-history example, historical lights, missing boundaries, native Recorder interruptions and entity isolation.

### Important limitation

**`bounded_state_history` means last-known-state reconstruction, not proof of complete historian recording.** It assumes that the persisted state-change series contains all material changes between its two bounding samples; unseen intermediate changes cannot be ruled out from the available rows. For source-backed completeness, use MoreRecords' explicit CCU-Historian verification. This update never inserts or modifies Recorder records.

Keep LightAway simulation **disabled** while examining the recalculated Copy day, Status, and diagnostics for every test light before activating control. Home Assistant 2026.10+ remains required. Imported history is read-only; preserve a database backup.
