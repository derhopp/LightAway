# LightAway 0.4.1 Beta 4

**Opt-in pre-release only.** The stable release v0.4.0 is unchanged.

## Sparse-state history repair

- Look up the last **real** Recorder state before each candidate-day Recorder interval even when that state is months old or predates several Home Assistant restarts.
- Carry the last known value into subsequent recorded intervals for **both presence and every light**, without relying on frequent repeated `on`/`off` entries.
- Continue excluding Recorder downtime from the 23-hour daily coverage checks, preserve `unknown`/`unavailable` rejection and real in-day transitions, and prevent replaying months-old transitions as new events.
- Keep verified MoreRecords CCU-Historian coverage entity-specific and fingerprint-checked.
- Add regression tests for 103/150-day-old samples, repeated Recorder restarts, light transitions, long gaps and invalid states.

**Limit:** A state change during missing Recorder time cannot be reconstructed from Recorder data alone. A complete CCU-Historian series verified through MoreRecords is needed to establish independent historical continuity. LightAway will not count offline time as recorded time.

## Testing and safety

After installation, keep simulation **off**, recalculate and inspect Copy day / Status sensors and Home Assistant diagnostics. Only enable simulation when the calculated light states are correct. Home Assistant 2026.10+ and retained detailed Recorder history are required.

For CCU-Historian certifications with additional identical Home Assistant Recorder samples, use MoreRecords 0.1.0b3 and re-verify each affected entity, including lights. No CSV data has been committed to the repository.
