# Source File Audit — Supplied Australian GP Samples

**Purpose:** Record what was present in the supplied files before the new fetcher
and preprocessor were written. This is a source audit, not an interpretation of
vehicle energy behaviour.

## Files inspected

- `australiaq.csv` — existing combined Kimi Australian GP Qualifying export
- `Pasted text(20261117-142942).txt` — session-wide laptimes JSON
- User-pasted `session_info.json` content
- `corners.json`, `cor.json`, `weather.json`, `rcm.json`
- `albert-park-circuit.json`
- Existing `fetchKimi.py`, `preprocess.py`, `fetchTracks.py`, `processTracks.py`
- Australian GP SVG/WebP map and event map
- Upstream `DATA_REFERENCE.md` for documented `drivers.json` and `team_radio.json` schemas

## Observations

### 1. Existing Kimi telemetry CSV

`australiaq.csv` contains 26,815 rows and 15 columns:

`time, rpm, speed, gear, throttle, brake, distance, rel_distance, DistanceToDriverAhead, acc_x, acc_y, acc_z, x, y, z`

In this sample:
- No null cells were present.
- Speed ranged from 0 to 327 km/h.
- Throttle ranged from 0 to 104.
- Brake values were 0/1.
- X, Y and Z were populated; Z had 6,254 distinct values.
- Car Z ranged approximately from -20.935 to 100.306.

This file is an older combined export, not a raw per-lap JSON set. It has no lap
number. Its time was formed by concatenating lap-local times with the previous
lap's final sample time, so it does not preserve actual between-lap session gaps.
It is not the source of truth for the rebuilt pipeline.

The upstream reference describes throttle as 0–100%, but this sample contains
9,865 values above 100 and a maximum of 104. The new pipeline preserves and flags
these values; it does not clamp or rescale them. The cause remains unresolved.

### 2. Session laptimes and time-quality metadata

The supplied session-wide laptimes JSON contains 355 rows and 43 source fields.
It includes 18 Kimi (`ANT`) records for laps 1–18. Fields include `lST`, `sesT`,
`lSD`, `iacc`, lap/sector times, tyre information, qualifying segment and speed
traps.

For all 18 Kimi lap records in this sample, `t0_date + lST` matches `lSD` at the
precision of the supplied values. However:
- 13 of the 18 Kimi records have `iacc=false`.
- 5 of the 18 have `iacc=true`.
- Several qualifying lap-time fields are null even though the row has `lST`,
  `sesT`, and `lSD`.

The new pipeline therefore retains the source `iacc` flag and exports a
`lap_timing_audit.csv`. It still computes session timestamps when a unique row
and `lST` exist, but flags iacc=false laps for downstream review. The team must
decide later whether those laps can support each specific analysis.

### 3. Session information

The user-pasted session info includes:
- `t0_date` = `2026-03-07T04:47:18.712000` (UTC)
- `session_start_time` = 761.484 seconds
- `total_laps` = null for this Qualifying session
- track-status transitions with time/status/message arrays
- session-status transitions with time/status arrays
- meeting, event, circuit and session metadata

`t0_date` is the session clock origin. `session_start_time` is the time of the
first Started status; these fields are not interchangeable.

### 4. Track geometry

The supplied `corners.json` contains:
- 618 `TrackX` entries and 618 `TrackY` entries
- No `TrackZ` array
- An empty `TrackTime` array in this file
- 22 `MiniSectorIndex` values
- 14 corner records
- `Rotation` = 44 degrees
- `LayoutYear` = 2022 and layout-reference metadata
- 14 section bands in the `SectionType` / start/end percentage/distance arrays

The source layout is therefore an earlier reference layout (2022) for this 2026
session. Confirm layout equivalence before using its geometry for alignment.

The upstream reference says TrackX/TrackY use the same units as corner X/Y, and
corner X/Y are metres. Car XYZ are also documented as metres. Matching units do
not prove a matching coordinate frame. `Rotation` is documented as a possible
alignment parameter, but the new pipeline does not apply it automatically.

The supplied `cor.json` contains 14 corner markers, 20 marshal lights and 20
marshal sectors, 54 marker records total.

The supplied `albert-park-circuit.json` contains 14 track-section bands with
category and start/end percentage. The separate `corners.json` also has source
start/end distances in metres for its section bands. Straight/Low/Medium/High
categories are not automatically active-aero activation zones.

### 5. Session context

The supplied files contain:
- `weather.json`: 95 weather records
- `rcm.json`: 99 race-control messages
- `session_info.json`: 15 track-status transitions and 17 session-status changes

`drivers.json` and `team_radio.json` were not included in this supplied raw batch.
The rebuilt fetcher requests them when present. Their field definitions are taken
from the upstream data reference; output handling is covered by synthetic tests.

In the supplied RCM file, `time` values are ISO timestamps. The new preprocessor
preserves the original timestamp and derives a session-relative value using
`t0_date`. It also handles numeric session-relative timestamps if encountered in
other sessions.

### 6. Preprocessor dry-run against the supplied metadata

A temporary fixture assembled from the supplied Australian Qualifying raw JSON
and session metadata was processed successfully. It produced:
- `session_laptimes.csv`: 355 rows
- `weather.csv`: 95 rows
- `race_control.csv`: 99 rows
- `track_status.csv`: 15 rows
- `session_status.csv`: 17 rows
- `track_outline.csv`: 618 rows
- `track_corners.csv`: 14 rows
- `track_markers.csv`: 54 rows
- `track_minisectors.csv`: 22 rows
- `track_sections.csv`: 14 rows
- `track_section_reference.csv`: 14 rows

It produced zero Kimi telemetry rows because the raw per-lap `ANT/<lap>_tel.json`
files were not part of the uploaded sample batch. The old combined `australiaq.csv`
was deliberately not used as a substitute. The live fetch step must retrieve the
per-lap JSONs before the common telemetry CSV can be populated.

## Existing code limitations addressed

- The old telemetry fetcher created one combined CSV and omitted a lap-number
  column from that export.
- It did not preserve the per-lap JSON files as the raw source of truth.
- Its accumulated lap-local time should not replace the upstream `lST` time join.
- The old track fetcher did not request `session_info.json` or
  `session_laptimes.json`.
- The rebuilt fetcher also requests `team_radio.json` metadata and source data
  dictionary/reference files.
- The rebuilt preprocessor records `iacc`, timing audit differences, missing
  sample values, track reference metadata and mini-sector indices.

## Not confirmed by this audit

- Why throttle exceeds 100 in some samples.
- Whether car XYZ and track XY share the same origin/orientation/frame.
- Whether the 2022 track reference layout is equivalent to the 2026 session layout.
- A 3D track elevation profile for the supplied circuit.
- Actual ERS harvesting/deployment or actual battery SoC.
- Whether any speed drop was caused by super clipping, regen, lift/coast,
  partial throttle, or another vehicle/powertrain effect.

These remain open research questions and require separate evidence and human review.
