# Slipstream-Lab

Research project on 2026 Formula 1 vehicle dynamics and energy-management analysis.

> **Current stage: Checkpoint 2 — first event fetched and processed successfully.** Australian Grand Prix data has been audited and the end-to-end pipeline has produced five session datasets. Work packages will be defined after this common pipeline and schema are accepted.

## Start here

1. Read [PROJECT_STANDARDIZATION.md](PROJECT_STANDARDIZATION.md).
2. Read [DATA_FETCH_AND_PREPROCESS.txt](DATA_FETCH_AND_PREPROCESS.txt).
3. Review [docs/data_pipeline/RAW_DATA_AUDIT.md](docs/data_pipeline/RAW_DATA_AUDIT.md), [OUTPUT_SCHEMA.md](docs/data_pipeline/OUTPUT_SCHEMA.md), and [PIPELINE_VALIDATION.md](docs/data_pipeline/PIPELINE_VALIDATION.md).
4. Run the automated tests as described below.
5. Keep the fetch manifest with any copied or shared processed datasets.

## Repository structure

```text
Slipstream-Lab/
├── README.md
├── PROJECT_STANDARDIZATION.md
├── DATA_FETCH_AND_PREPROCESS.txt
├── requirements.txt
├── fetch_data.py
├── preprocess_data.py
├── .gitignore
├── data/
│   ├── raw/                       # Downloaded source data; never edit
│   │   └── local_reference_maps/  # Optional local SVG/WebP references
│   └── processed/                 # Standardized CSV outputs
├── docs/
│   └── data_pipeline/
│       ├── OUTPUT_SCHEMA.md
│       ├── SOURCE_AUDIT.md
│       ├── RAW_DATA_AUDIT.md
│       └── PIPELINE_VALIDATION.md
├── reports/                       # Fetch manifests and processing diagnostics
├── tests/
│   ├── test_fetch.py
│   └── test_preprocess.py
└── work_packages/                 # Four assignments, added after pipeline approval
```

## Requirements

- Python 3.10 or newer.
- The current fetch and preprocessing scripts use only the Python standard library; no third-party package installation is currently required.

Check Python:

```powershell
python --version
```

## Run tests (safe; no data download)

Run these commands from the repository root, the directory containing `README.md`:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected result for the current version: **15 tests pass**. If the output says `Ran 0 tests`, the test files are missing from that checkout or the command was run from the wrong directory. Check that both `tests/test_fetch.py` and `tests/test_preprocess.py` exist.

## Fetching and preprocessing

Fetch exactly one event per run. The fetcher downloads **all available sessions** for that event and the selected driver's per-lap telemetry. Use the event's Grand Prix name; date-prefixed source folders are resolved automatically.

```powershell
python fetch_data.py --event "Australian Grand Prix"
```

To refresh the selected event after the upstream source changes:

```powershell
python fetch_data.py --event "Australian Grand Prix" --force
```

`--force` refreshes only the selected event and shared reference files. It does **not** delete other event folders or the entire raw-data directory. The manifest records source revisions at file level and indicates when data from multiple source commits may coexist.

After reviewing the fetch manifest, preprocess the same event:

```powershell
python preprocess_data.py --event "Australian Grand Prix"
```

Raw JSON is preserved unchanged. Separate CSVs are produced by data category. Missing values remain blank; the initial pipeline does not interpolate or delete incomplete rows. Throttle values are preserved exactly without clamping or extra per-sample range flags. All laps are retained with the source `iacc` indicator.

## Pipeline files

- `fetch_data.py` — downloads raw Kimi telemetry and available session context from TracingInsights/2026.
- `preprocess_data.py` — creates standardized per-session CSVs without modifying raw source files.
- `DATA_FETCH_AND_PREPROCESS.txt` — detailed fetching, time alignment, output and limitation documentation.
- `docs/data_pipeline/OUTPUT_SCHEMA.md` — output column definitions and integration contract.
- `docs/data_pipeline/SOURCE_AUDIT.md` — initial sample-file audit used while rebuilding the pipeline.
- `docs/data_pipeline/RAW_DATA_AUDIT.md` — full Australian GP archive audit and live preprocessing results.
- `docs/data_pipeline/PIPELINE_VALIDATION.md` — automated tests and live end-to-end validation.

## Current limitations / pending validation

- The fetcher downloads team-radio metadata, not MP3 audio files or transcripts.
- Video synchronization is not implemented.
- Car telemetry includes XYZ; the supplied track geometry sample exposes TrackX/TrackY but no TrackZ. Track-relative 3D alignment is not implemented.
- Brake telemetry is binary, not continuous brake pressure.
- Actual 2026 ERS deployment and battery SoC are not available in the public telemetry sources currently used.
- No model training or SoC estimation is included at this stage.
- The pipeline has passed 15 unit tests and completed live preprocessing of all five Australian GP sessions with zero session errors.
- No model training, energy inference, SoC estimation, video synchronization, or active-aero detection is implemented yet.

## Data handling

Raw data is excluded from Git by default. Do not commit large raw datasets without team agreement. Processed CSVs may be committed after checking file size and source terms. Keep generated reports and manifests so each dataset can be traced to its source revision and processing run.
