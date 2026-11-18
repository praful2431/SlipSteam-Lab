# Pipeline Validation — 0.5

## Automated checks

The Checkpoint 2 pipeline has been run against the first live event archive.
The fetch manifest records source commit `f496d06e7fcef8d7c854710b709544d1f8462aa1`.

- Fetch: 192 manifest file records, zero failures.
- Raw archive: 194 JSON files parsed successfully.
- Sessions: Practice 1, Practice 2, Practice 3, Qualifying, and Race.
- Kimi telemetry: 149 lap files and 143,420 samples.
- Timing join: 149 unique matches, zero missing matches, zero ambiguous matches.
- Preprocessing: five sessions completed, zero session errors.
- Automated tests: 15 passed.

Run the checks from the repository root:

```powershell
python -m py_compile fetch_data.py preprocess_data.py tests/test_fetch.py tests/test_preprocess.py
python -m unittest discover -s tests -p "test_*.py" -v
```

## Live output counts

| Session | Kimi telemetry samples | Laptime records (all drivers) | Weather | Race control | Lap timing audit rows |
|---|---:|---:|---:|---:|---:|
| Practice 1 | 29,360 | 487 | 82 | 43 | 24 |
| Practice 2 | 28,809 | 544 | 79 | 46 | 31 |
| Practice 3 | 20,867 | 377 | 90 | 60 | 18 |
| Qualifying | 26,815 | 355 | 95 | 99 | 18 |
| Race | 37,569 | 1,008 | 148 | 167 | 58 |
| **Total** | **143,420** | **2,771** | **494** | **415** | **149** |

The preprocessor produced separate CSVs for telemetry, lap timing, weather,
race control, track/session status, drivers, track geometry, corners, markers,
mini-sectors, track sections, and available team-radio clip metadata. There are
78 processed output files including session summaries and audits.

## Raw-data and timing validation

See [RAW_DATA_AUDIT.md](RAW_DATA_AUDIT.md) for the full archive audit. Key checks:

- All 194 JSON files parse; all telemetry parallel arrays have matching lengths.
- All 149 telemetry files have monotonically increasing sample time. Sampling is
  irregular; fixed-rate assumptions are not valid.
- Every telemetry lap has exactly one driver/lap timing join. For all 149 laps,
  `t0_date + lST` matches source `lSD`; the final sample aligns with `sesT - lST`
  within floating-point precision.
- The correct telemetry time formula is
  `session_time_s = lST + lap_elapsed_s`, where `lap_elapsed_s` is the sample's
  time from the start of that lap. The `lap_time_s` in `session_laptimes.csv`
  means completed-lap duration and must not be used as the per-sample offset.
- There are zero missing values in the required telemetry arrays `time`, `speed`,
  `throttle`, `brake`, `x`, `y`, and `z` and zero invalid conversions in these
  fields in this event archive. This does not imply every optional field is
  complete.
- Source `iacc` is false for 55 of 149 laps; all are retained with the source indicator.
- 24,643 of 143,420 throttle samples (17.18%) exceed the documented 0–100 range;
  values are retained unchanged, not clipped or given additional per-sample flags.
- Brake is binary. DRS is zero in every sample. Car XYZ is available, but the
  supplied track reference is 2D and coordinate alignment is not implemented.
- The source acceleration fields are derived/processed from speed and position,
  not independent raw IMU readings.
- No direct SoC, ERS power/deployment/harvest, or active-aero status signal was
  found. Team-radio files are clip-index metadata only; audio and transcripts
  were not downloaded.
- Practice 2 race-control source ordering is non-monotonic; duplicate timestamps
  occur in other sessions. Source order and duplicate messages are preserved.

## Important source-data limitations

- The upstream telemetry has no direct battery SoC or ERS electrical power
  measurement. SoC cannot be supervised or directly validated from this archive
  alone.
- `iacc=false` and throttle values above 100 need explicit review before these
  samples are used as trusted labels or physical pedal percentages.
- Car Z has session-dependent baselines; track geometry has no TrackZ. Do not
  interpret car Z as validated road-relative elevation or heave.
- The circuit reference metadata is from layout year 2022; equivalence to the
  2026 layout must be reviewed before track-relative feature generation.
- `acc_x/y/z` are source-derived estimates and should not be treated as
  independent IMU ground truth.
- DRS is zero throughout this archive and is not a substitute for active-aero
  state on the 2026 car.
- Race-control and radio information is incomplete context, not a full record of
  all driver/team communication.

## Acceptance workflow for future events

1. Fetch one event at a time and preserve the original `reports/fetch_manifest.json`.
2. Confirm the manifest source commit, selected event, session coverage, and
   failure count.
3. Inspect source JSON integrity and session file coverage.
4. Run preprocessing for that event.
5. Review `reports/preprocessing_report.json`, each `session_summary.json`, and
   each `lap_timing_audit.csv`.
6. Compare timing quality, missing data, channel ranges, coordinate references,
   and source revisions before combining data across events.

## Approved pipeline decisions

- Fetch one event per run, including all available sessions in that event.
- Retain all original source JSON unchanged.
- Export separate CSVs by data category.
- Preserve missing values as blanks; do not interpolate or delete incomplete records in the initial pipeline.
- `--force` refreshes only the chosen event and shared references. It never
  clears other event folders. Check per-file source revisions before combining
  datasets fetched at different upstream commits.
