# Australian Grand Prix — Raw Data Audit

**Audit date:** 2026-11-17  
**Project:** Slipstream-Lab  
**Driver requested:** ANT (Kimi Antonelli)  
**Upstream source commit:** `f496d06e7fcef8d7c854710b709544d1f8462aa1`

This audit was performed on the uploaded `tracinginsights_2026.zip` after the
first successful event fetch. It records what is present in the downloaded
source files and what can safely be validated before modelling. Raw source files
were not edited.

## 1. Archive and session coverage

- The ZIP contains 196 files: 194 JSON files plus `DATA_REFERENCE.md` and `SQ.py`.
- All 194 JSON files parse successfully.
- Five Australian Grand Prix sessions are present.
- The 149 ANT per-lap telemetry files match the 149 ANT records in the corresponding
  session-wide laptime tables one-to-one. There are no missing or duplicate lap
  numbers in this join.

| Session | ANT telemetry laps | Telemetry samples | Session laptime rows (all drivers) | Weather rows | Race-control messages |
|---|---:|---:|---:|---:|---:|
| Practice 1 | 24 | 29,360 | 487 | 82 | 43 |
| Practice 2 | 31 | 28,809 | 544 | 79 | 46 |
| Practice 3 | 18 | 20,867 | 377 | 90 | 60 |
| Qualifying | 18 | 26,815 | 355 | 95 | 99 |
| Race | 58 | 37,569 | 1,008 | 148 | 167 |
| **Total** | **149** | **143,420** | **2,771** | **494** | **415** |

Each telemetry sample contains the same 18 source keys. All list-valued telemetry
channels have equal lengths within each lap file. Sample `time` is strictly
increasing in all 149 files, with no duplicate or decreasing sample timestamps.
Sampling is irregular: median spacing is approximately 0.13 seconds, while gaps
vary by session and can exceed one second. Do not assume a fixed sampling rate.

## 2. Telemetry channels and source-quality observations

The per-lap telemetry contains:

`time, rpm, speed, gear, throttle, brake, drs, distance, rel_distance,
DriverAhead, DistanceToDriverAhead, acc_x, acc_y, acc_z, x, y, z, dataKey`.

Key observed ranges across the event:

| Field | Observed range / values | Notes |
|---|---|---|
| Speed | 0–332 km/h | Source unit is km/h; retain that unit |
| Throttle | 0–104 | 24,643 of 143,420 samples (17.18%) exceed the documented 0–100 range |
| Brake | 0 or 1 | Binary state; no continuous brake-pressure channel |
| DRS | 0 only | No variation in these five sessions; it cannot explain active-aero state |
| Gear | 0–8 | Source gear encoding |
| X/Y/Z | Present in every telemetry file | Source documents metres; no coordinate transform is applied |
| Acceleration X/Y/Z | Present in every telemetry file | Source documents these as computed/processed values, not raw IMU readings |

**Throttle:** The source reference documents 0–100%, but actual values reach 104.
The pipeline preserves the original values and flags out-of-range samples. Do not
clamp, rescale, or treat 104 as a verified physical pedal angle without further
investigation.

**Acceleration provenance:** The upstream `DATA_REFERENCE.md` states that
`acc_x`, `acc_y`, and `acc_z` are calculated by the extraction script from speed,
position, and distance, with outlier handling and smoothing. They are not raw
on-car IMU channels. Keep that provenance attached to any analysis; do not use
these as independent ground-truth sensor measurements.

**Position Z:** Car Z exists, but the track reference only supplies 2D `TrackX`
and `TrackY` (no `TrackZ`). Car Z values use a different baseline between
sessions, so do not interpret them as validated height above the local track
surface or derive vehicle heave from them without further validation.

No direct battery SoC, ERS deployment/harvest power, or active-aero mode channel
was found in the downloaded telemetry/session files. DRS is zero for all samples
and is not a substitute for a 2026 active-aero status signal.

## 3. Lap timing and UTC alignment validation

The following are distinct source fields:

- `time` in each `{lap}_tel.json`: sample elapsed time from the beginning of that
  lap's telemetry file.
- `time` in `session_laptimes.json`: the lap's recorded lap-time value.
- `lST`: lap start time relative to the session clock.
- `sesT`: lap end time relative to the session clock.
- `lSD`: timestamp of the lap start.
- `t0_date`: session clock origin timestamp.

For every one of the 149 ANT lap records:

1. `t0_date + lST` equals source `lSD` exactly at the precision supplied.
2. The final telemetry sample time equals `sesT - lST` within floating-point
   precision (maximum absolute difference below 0.000000000002 seconds).
3. There is exactly one driver/lap timing row for each telemetry file.

Therefore the validated sample-level mapping is:

```text
session_time_s = lST + telemetry_sample_time_s
timestamp_utc  = t0_date + session_time_s
```

Do **not** add the `session_laptimes.json` lap-duration `time` field to `lST`
for every telemetry sample. Use the per-sample `time` array from the telemetry
file. The actual lap duration remains a separate source field.

The `iacc` timing-alignment flag is `true` for 94 laps and `false` for 55 laps.
The source says `iacc=false` laps require caution; it is not a guarantee of
failure, nor does `iacc=true` guarantee overall data quality. The audit also
found 20 ANT rows where the source lap-duration `time` is blank, and two deleted
laps (Practice 1 lap 8 and Practice 2 lap 2). No ANT row in this archive has
`ff1G=true`. The pipeline retains all telemetry and preserves the source indicators; it
does not filter laps based on them.

## 4. Track geometry and position cross-check

Each session's `corners.json` provides:

- 618 `TrackX` and 618 `TrackY` points;
- 14 corner markers and 14 section bands;
- 22 mini-sector boundary indices;
- `Rotation = 44` degrees;
- `LayoutYear = 2022`;
- an empty `TrackTime` array and no `TrackZ` array.

The reference is therefore a 2022 2D layout for a 2026 session. A diagnostic
point-to-polyline check shows that normal on-circuit telemetry laps generally
lie close to the supplied track outline (often within a few metres). Some files
contain pit-lane, out-lap, in-lap, or partial/off-track sections whose XY points
are roughly 140 metres from the circuit line. Those samples should not be
blanket-deleted; classify the operating context first. No rotation or coordinate
transform was applied by the preprocessor.

The `Straight`, `Low`, `Medium`, and `High` section labels describe track-speed
sections. They are not proof of active-aero activation zones.

## 5. Session context and ordering

- Weather samples are present in all five sessions (82–148 samples per session)
  and their source session-time arrays are monotonic, at roughly one-minute
  spacing.
- Race-control messages are present in all five sessions.
- Practice 2 race-control timestamps are not in source order: the first few
  records move backward in time. Practice 3, Qualifying, and Race also contain
  multiple messages with identical timestamps.
- The preprocessing export retains source order and `message_index`. For
  time-based analysis, create a separate stable time-sorted view ordered by
  `timestamp_utc` and then `message_index`; do not deduplicate simultaneous
  messages or overwrite the source-order export.
- Session-status streams show aborted/restarted periods in Practice 3 and
  Qualifying. Preserve those state changes when interpreting lap context.
- `team_radio.json` is present only for Practice 2 and Practice 3, with one clip
  index record in each. No MP3 audio or transcript is included in this fetch.

## 6. Live preprocessing result

The preprocessor was run against all five sessions after the raw-file checks.
It completed in 15.31 seconds in the audit environment, with zero session errors.
It produced **143,420 telemetry CSV rows**, 149 lap-timing audit rows, 2,771
all-driver session-laptime rows, and separate weather, race-control, driver,
status, geometry, marker, and section CSVs.

The generated telemetry quality summaries report:

- 149 unique timing matches, zero missing matches, and zero ambiguous matches;
- zero missing values in required numeric telemetry fields (`time`, `speed`,
  `throttle`, `brake`, `x`, `y`, `z`);
- zero invalid numeric conversions in those telemetry rows;
- 24,643 throttle values outside the documented 0–100 range, retained unchanged;
- 55 laps with `iacc=false`, retained with the source indicator.

The preprocessing script now normalizes source keys once per sample instead of
re-scanning the full source dictionary for every mapped field. All 15 unit tests
pass after this optimization.

## 7. Analysis boundaries

This audit validates file integrity, coverage, channel presence, timing joins,
and baseline geometry consistency. It does not prove why a speed drop occurs,
measure actual ERS energy flow, reveal SoC, or establish active-aero deployment.
Those remain inference/research questions requiring additional sources and
human review. Preserve the raw files and use the manifest's pinned source commit
when reproducing results.
