# Slipstream-Lab — Project Standardization

**Document:** Project-Wide Standardization (PSD)  
**Version:** 0.2 — Draft for team use  
**Status:** Approved baseline; data pipeline specification pending  
**Repository:** `Slipstream-Lab`

---

## 1. Purpose

This document defines the shared technical and documentation standards for the project. All four work packages must follow these standards so their outputs can be integrated without inconsistent data formats, units, naming, assumptions, or evaluation methods.

The project will use separate algorithms or models where appropriate, connected through documented inputs and outputs. Traditional machine learning and physics-based methods are permitted. Deep learning and neural networks are out of scope.

## 2. Technical standards

| Item | Standard |
|---|---|
| Primary language | Python |
| Machine learning | Traditional ML only; no deep learning or neural networks |
| Physics-based methods | Permitted and encouraged where relevant |
| Core libraries | NumPy, Pandas, Scikit-learn, SciPy, Matplotlib |
| Additional libraries | XGBoost may be used when justified and documented |
| Explainability | Model decisions and important limitations must be documented |
| Reproducibility | Every result must be reproducible from documented inputs and steps |

A library or algorithm outside this list may be used when there is a clear reason. Record the package, version, purpose, and installation method in the relevant module documentation.

## 3. Data handling standards

1. Original source files are immutable. Never overwrite or modify downloaded raw data.
2. Store fetched raw data separately from cleaned and processed data.
3. Use CSV as the default format for data exchanged between modules.
4. If a dataset becomes too large or CSV causes a practical performance or storage problem, document the issue and propose an alternative before changing the shared format.
5. Preserve original source fields wherever practical. Derived or transformed fields must be identifiable and documented.
6. Do not silently drop, replace, interpolate, or fabricate missing values.
7. Record cleaning, filtering, interpolation, resampling, coordinate transformations, and unit conversions.
8. Keep a traceable relationship between processed records and their source data.

**Data fetching and preprocessing are not specified by this document.** They will be rebuilt and documented separately before the four work packages begin. The resulting pipeline documentation and dataset schema will become a shared project contract.

## 4. Units and naming conventions

### 4.1 Units

- Speed: **km/h throughout**, including calculations and exported datasets, unless a specific external equation or library requires another unit. Any temporary conversion must be explicit and reversible.
- Time: seconds for the common session time field.
- Other physical quantities: use SI units where practical and state the unit in the field definition.
- Percentages: represent consistently as percentage values from 0 to 100; document any exception.

### 4.2 Time reference

The intended common time field is:

`session_time_s`

It represents seconds from the agreed session reference point. The exact reference point, timestamp source, precision, and synchronization procedure must be defined in the data-pipeline documentation before module development.

Preserve original timestamps alongside normalized time fields. Video annotations, radio messages, and race events must reference the common timebase and record any synchronization offset or uncertainty.

### 4.3 Field names

Use lowercase `snake_case` for filenames, variables, columns, and functions.

Examples:

- `session_time_s`
- `throttle_pct`
- `speed_kmh`
- `brake_status`
- `track_x`
- `track_y`
- `track_z`
- `estimated_soc_pct`

Include units in field names where useful. Every field must have a documented definition, unit, source, and status (raw, transformed, or derived).

## 5. Model and algorithm standards

Every model or algorithm must document:

- Objective and intended use.
- Input features and their definitions.
- Target variable, where applicable.
- Data sources and selection criteria.
- Cleaning and feature-engineering steps.
- Algorithm, parameters, and rationale.
- Training, validation, and test methodology, where applicable.
- Evaluation metrics and results.
- Known limitations and uncertainty.

Avoid data leakage. Randomly splitting neighbouring telemetry rows can place nearly identical observations in training and test sets. Choose a split appropriate to the problem; where possible, separate by lap, session, or another meaningful independent group. Explain the choice.

Establish a simple baseline before tuning a more complex traditional ML method. Do not use ML where a transparent calculation or established physical relationship is sufficient. Do not describe an inferred event as confirmed unless independent evidence supports it.

## 6. Assumptions and human decisions

AI-assisted work must not silently make research or physical assumptions. The following require explicit documentation and human review:

- Missing or unavailable telemetry channels.
- Assumed vehicle, battery, aerodynamic, or powertrain parameters.
- Interpretation of ambiguous speed or energy-management events.
- Outlier removal or manual correction.
- Event labels derived from video, radio, flags, or other context.
- Whether model predictions are physically and scientifically plausible.
- Any change to a shared data definition or interface.

Maintain a **Human Decisions Required** section in each module README. For each item, state the question, available evidence, options, recommendation (if any), and decision status. Do not proceed past a blocking decision by inventing an answer.

Where the evidence is incomplete, distinguish clearly between:

- **Observed:** directly present in a source dataset or annotation.
- **Derived:** calculated from observed values using a documented method.
- **Estimated:** inferred by a model or estimation method.
- **Assumed:** selected for analysis but not directly verified.

## 7. Module deliverables

Each of the four work packages must provide:

1. Source code required to reproduce the work.
2. Input data requirements and expected schema.
3. Processed or derived CSV outputs, where applicable.
4. Model or algorithm artifacts, where applicable.
5. Evaluation results and relevant visualizations.
6. A module README following Section 8.
7. A clear statement of what is ready for integration and what still requires human review.

Do not make another module depend on an undocumented notebook state, a local file path, or a manually edited file that is not included in the repository.

## 8. Mandatory module README format

Each module must contain a `README.md` with these sections:

1. **Objective** — what the module does and does not do.
2. **Data sources** — source files, channels, provenance, and access method.
3. **Inputs and schema** — required filenames, columns, types, units, and missing-value behaviour.
4. **Data preparation** — cleaning, filtering, transformations, and feature engineering.
5. **Methodology** — algorithms, equations, parameters, and rationale.
6. **Implementation** — code entry points and execution steps.
7. **Results and evaluation** — outputs, metrics, plots, and interpretation.
8. **Output contract** — exact output filenames, columns, units, types, and record meaning.
9. **Integration** — how another module should consume the outputs and any dependencies.
10. **Limitations and uncertainty** — known weaknesses and unsupported conclusions.
11. **Human decisions required** — unresolved questions and decisions needed from the team.
12. **Reproduction** — environment setup, package versions, commands, and random seeds where relevant.

If a section does not apply, write `Not applicable` and briefly state why. Do not silently omit required sections.

## 9. Shared repository structure

The following is the proposed starting structure. Directory names can be adjusted by the team, but the separation between shared standards, shared data, and independent work packages should be retained.

```text
Slipstream-Lab/
├── README.md
├── PROJECT_STANDARDIZATION.md
├── requirements.txt
├── docs/
│   ├── data_pipeline/          # Fetching and preprocessing documentation
│   └── decisions/              # Approved assumptions and team decisions
├── data/
│   ├── raw/                    # Original, unmodified source data
│   ├── processed/              # Shared standardized datasets
│   └── external/               # Supporting files and annotations
├── shared/
│   ├── schemas/                # Approved column and interface definitions
│   └── utilities/              # Reusable shared code
├── work_packages/
│   ├── part_1/
│   │   └── README.md
│   ├── part_2/
│   │   └── README.md
│   ├── part_3/
│   │   └── README.md
│   └── part_4/
│       └── README.md
└── results/
    ├── figures/
    └── reports/
```

Large raw datasets should not automatically be committed to Git. The team must decide how datasets will be stored and referenced once their size and licensing conditions are known. Keep credentials, tokens, and private data out of the repository.

## 10. Integration and change control

- The shared data schema and output contracts are the integration boundaries between work packages.
- A module must not unilaterally rename a shared field, change a unit, or alter the meaning of an output.
- Proposed changes must be documented and approved before dependent modules adopt them.
- Each module must state its version or commit reference when reporting results.
- Keep code, configuration, and documentation in version control. Do not rely on chat history as the only record of a decision.

## 11. Work sequence

1. Create the shared GitHub repository and add this document.
2. Rebuild the GitHub data-fetching process.
3. Rebuild and validate the preprocessing process.
4. Document both processes and finalize the shared dataset schema.
5. Approve the four work-package scopes and interfaces.
6. Assign the work packages independently.
7. Integrate using each module's documented output contract.

**No work package should finalize its data assumptions or interface before Steps 2–4 are complete.**

---

## Change log

| Version | Change |
|---|---|
| 0.1 | Initial standardization proposal |
| 0.2 | Confirmed speed in km/h, CSV as default exchange format, and shared GitHub repository; added explicit data-pipeline prerequisite and integration rules |
