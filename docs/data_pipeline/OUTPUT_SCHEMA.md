# Shared Data Output Schema — Draft 0.2

This is the interface contract produced by `preprocess_data.py`. CSV files are
UTF-8 with a header row, comma delimiters, and blank cells for unavailable data.
Raw JSON remains unchanged under `data/raw/tracinginsights_2026/`.

## `kimi_telemetry.csv`

One row per Kimi telemetry sample. Original sample order is retained within each
lap; files are concatenated in lap-number order.

| Column | Meaning | Unit / representation |
|---|---|---|
| `event_name`, `session_name` | Event and session identifiers | Text |
| `driver_code`, `driver_number` | Driver identity | Text / source value |
| `lap_number` | Lap number from telemetry filename | Integer |
| `sample_index_in_lap` | Zero-based sample number within lap file | Integer |
| `lap_time_s` | Sample time from lap start | Seconds |
| `lap_start_time_s` | Lap start on session clock (`lST`) | Seconds |
| `session_time_s` | `lST + lap_time_s` for a unique timing match | Seconds |
| `timestamp_utc` | `t0_date + session_time_s` | ISO 8601 UTC |
| `time_alignment_status` | Availability/uniqueness of the timing join | Diagnostic text |
| `lap_timing_alignment_accurate` | Source `iacc` flag | 0/1/blank |
| `engine_rpm` | Engine speed | RPM |
| `speed_kmh` | Vehicle speed | km/h |
| `gear` | Selected gear | Integer/source encoding |
| `throttle_source_pct` | Unmodified throttle source value | Source describes percent; out-of-range values retained |
| `brake_applied` | Binary brake state | 0/1 |
| `lap_distance_m` | Distance within lap | Metres |
| `lap_relative_distance` | Normalized distance along lap | Unitless, usually 0–1 |
| `distance_to_driver_ahead_m` | Gap to the car ahead | Metres |
| `driver_ahead_code` | Driver ahead identifier | Text/source value |
| `acc_x_mps2`, `acc_y_mps2`, `acc_z_mps2` | Derived/processed acceleration fields | m/s² |
| `car_x_m`, `car_y_m`, `car_z_m` | Car position | Metres |
| `drs_status` | DRS state where supplied | Source encoding |
| `data_key` | Source data identifier | Text |
| `quality_flags` | Row-level warnings | Semicolon-separated text |

Unknown telemetry channels are retained as `source_<field_name>` columns. Any
new shared field must be documented before another module depends on it.

## `lap_timing_audit.csv`

One row per discovered Kimi lap telemetry file. This is a diagnostic table, not
an ML feature table. It contains:

- `timing_match_count` — number of laptime records matched by driver/lap
- `lap_start_time_s` — source `lST`
- `lap_start_utc_source` — source `lSD`
- `lap_start_utc_derived` — `t0_date + lST`
- `derived_minus_source_lap_start_s` — timestamp cross-check difference
- `lap_timing_alignment_accurate` — source `iacc` flag
- `reference_lap_time_s`, `reference_session_end_time_s` — source lap time and `sesT`
- `lap_deleted`, `fastf1_generated` — source lap-quality indicators
- `first_telemetry_lap_time_s`, `last_telemetry_lap_time_s` — observed sample bounds
- `last_sample_minus_reference_session_end_s` — diagnostic endpoint difference
- `timing_audit_status` — unique/missing/ambiguous match and iacc summary

A computed session timestamp is retained when a unique row and `lST` exist, even
when `iacc=false`. The source indicator remains in the telemetry and audit table;
it is not duplicated as a per-sample quality flag. Downstream work must consider
it when evaluating timing-sensitive features.

## `session_laptimes.csv`

One row per session laptime record, across all drivers. Known source fields are
renamed to descriptive `snake_case` names; unmapped fields receive a `source_`
prefix. Important fields include driver/lap identity, `lap_time_s`,
`lap_start_time_s`, `session_end_time_s`, `lap_start_utc`, sector times, tyre
compound/stint/life, qualifying segment, lap-deletion flags, `iacc`, `ff1G`, pit
in/out times, speed-trap measurements and per-lap weather where present.

The untouched source JSON remains available for audit.

## Other outputs

| File | Row meaning | Important contents |
|---|---|---|
| `weather.csv` | One weather sample | Session time, UTC, temperatures, humidity, pressure, rainfall, wind |
| `race_control.csv` | One race-control message | Original timestamp, normalized UTC/session time, category, message, flag, scope, sector, driver, lap |
| `track_status.csv` | One track-status transition | Session-relative time, status code, message |
| `session_status.csv` | One session-status transition | Session-relative time, status |
| `track_outline.csv` | One source track-outline point | X/Y, optional Z, source reference-lap time |
| `track_corners.csv` | One corner marker | Number/label, XY, angle, distance, section classifications |
| `track_markers.csv` | One legacy corner/marshal marker | Marker family, number/letter, XY, angle, distance |
| `track_minisectors.csv` | One mini-sector end index | Source index into TrackX/TrackY |
| `track_sections.csv` | One mapped track section | Type, start/end percentage |
| `track_section_reference.csv` | One section band from `corners.json` | Type, percentage and source start/end distance |
| `drivers.csv` | One driver entry in the session | Driver code/number, team, names, team colour, headshot URL |
| `team_radio.csv` | One indexed broadcast radio clip | Driver, source timestamp, normalized UTC/session time, relative MP3 path and recording URL; no transcript is supplied by this file |
| `session_summary.json` | One session summary | Metadata, source layout reference, row counts, quality metrics, warnings |

`drivers.csv` and `team_radio.csv` are included when their corresponding raw
JSON files exist. `team_radio.csv` is clip-index metadata only; the current
fetcher does not download MP3 audio or generate transcripts.

Outputs are grouped by event and session. Do not merge different events, sessions,
or track-layout references until their equivalence is explicitly validated.

## Time and coordinate rules

- The source telemetry `time` is lap-relative.
- `session_time_s = lST + lap_time_s` only when there is exactly one driver/lap
  timing record and a valid `lST`.
- `timestamp_utc = t0_date + session_time_s` only when `t0_date` is available.
- Source `iacc` is retained; `iacc=false` creates a row warning, not automatic
  deletion or silent acceptance.
- Race-control source timestamps are preserved. ISO times are normalized and
  converted to session time; numeric source times are treated as session-relative.
- Weather and status-stream times are already session-relative.
- Car XYZ and track geometry are exported separately. No transform is applied.
- Track outline X/Y uses the same units as corner X/Y; the source reference defines
  corner X/Y as metres. TrackZ is not documented in the current upstream field
  reference and is absent from the supplied sample. The parser preserves an
  optional TrackZ array if a future source file contains one.
- `TrackTime` belongs to the layout's reference lap, not the current driver's lap.
- The upstream reference documents car XYZ as interpolated GPS positions in metres;
  track X/Y use the same units as corner X/Y. Units alone do not prove a shared
  coordinate frame. See the [upstream data reference](https://github.com/TracingInsights/2026/blob/main/DATA_REFERENCE.md).
- Track layout metadata is stored in `session_summary.json`.

## Quality handling

The pipeline records missing required sample values, invalid numeric values,
missing/ambiguous lap timing matches, parallel-array length mismatches, and other
parsing warnings. Throttle source values are preserved exactly and are not given
additional per-sample out-of-range flags. The source `iacc` indicator is retained
but is not duplicated as a quality flag. Missing values remain blank; no rows are
deleted and no interpolation or imputation is performed in the initial pipeline.
