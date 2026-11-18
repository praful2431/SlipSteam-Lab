# Slipstream-Lab — Team Working Protocol

**Status:** Approved team process  
**Applies to:** All four team members and all research work packages  
**Project:** Slipstream-Lab — 2026 Formula 1 vehicle dynamics and energy-management research, with battery State of Charge (SoC) estimation as the central research challenge.

---

## 1. Purpose

This protocol defines how the four team members plan, develop, review and report their work. The project will use **parallel, independently owned research workstreams** supported by one shared data foundation and a coordinated final integration process.

The objective is to let every member begin useful work without waiting for another member's code, features or results, while maintaining scientific consistency across the final project.

This document defines **how the team works**. The separate Work Package (WP) documents will define **what each member investigates and delivers**.

## 2. Team structure and independence

- The project will have four independently owned research workstreams, one per team member.
- Each member owns their research question, methodology, implementation, validation, results, limitations and documentation.
- All members start from the approved shared raw/processed data and project standards.
- A member must not require another WP's implementation or output in order to begin their own research.
- A member may optionally use another WP's output during final integration, but the member's core analysis must remain independently reproducible from the shared data and documented methods.
- Similar calculations may be implemented independently when required by different research questions. If a quantity is shared across packages, its meaning, unit and definition must remain consistent and be documented.
- The team will define input/output contracts early. Actual outputs will be integrated after each workstream has produced independently testable results.

**Important distinction:** the work-package split is for parallel team ownership. The final system architecture may still connect the research findings in a logical workflow. A workflow dependency in the final system must not become a development dependency between team members.

## 3. Four-stage working process

### Stage 1 — Prerequisites and planning

Before substantial implementation, each member prepares a plan covering:

1. Research objective and specific research questions.
2. Hypothesis or questions to investigate, where appropriate.
3. Required source files, variables and data coverage.
4. Relevant physics, mathematics and literature.
5. Proposed methodology, equations, features and algorithms.
6. Software, libraries and computational requirements.
7. Expected outputs and how they will be evaluated.
8. Known data limitations, assumptions and risks.
9. Decisions or approvals required from the team/supervisor.
10. A realistic implementation sequence and initial milestones.

**Stage 1 deliverable:** a written research and implementation plan in the member's living README. The team reviews shared definitions, cross-package interfaces and any assumptions that could affect more than one workstream before implementation proceeds.

### Stage 2 — Independent development

After the plan is reviewed, the member develops their work independently.

- Use the shared pipeline and approved data schema; do not recreate the common fetching/preprocessing pipeline inside a WP.
- Build and test methods in small, reproducible steps.
- Keep raw source data unchanged. Store derived data and results separately.
- Document equations, units, feature definitions, model inputs/targets, algorithm choices and parameters.
- Produce preliminary results and visualizations as soon as useful.
- Continue until a genuine external input, approval or unresolved dependency is required.
- Do not wait for another WP merely because its research might eventually be useful.

**Stage 2 deliverable:** a working, independently testable implementation with preliminary results and updated documentation.

### Stage 3 — Review, improvement and blocker handling

When waiting for a decision, external input or missing prerequisite, the member should use the time productively where possible:

1. Review and proofread the current code, calculations and documentation.
2. Recheck equations, units, assumptions, data joins and edge cases.
3. Reproduce results and add or improve tests.
4. Check whether the blocker can be resolved using already available evidence.
5. Investigate alternative methods that preserve the research objective.
6. Record the alternatives, trade-offs and evidence needed to choose between them.
7. Ask the team/supervisor for input when the decision exceeds the member's authority or cannot be resolved responsibly.

If no valid workaround exists, document the blocker and wait for the required input. **Do not fabricate data, silently change the research question, conceal uncertainty or present an unapproved assumption as fact.**

**Stage 3 deliverable:** reviewed work, documented improvements and, when applicable, a clear blocker report with the exact decision/input required.

### Stage 4 — Continuous team updates

Stage 4 is continuous. It runs throughout Stages 1, 2 and 3; it is not a final stage that begins after development.

Each member shares updates at the team's agreed check-ins and whenever a significant milestone, blocker or decision request occurs. Every update should state:

- **Completed:** work finished and whether it has been validated.
- **In progress:** current activity.
- **Pending:** remaining work.
- **Blocked:** what is preventing progress, if anything.
- **Required input:** the specific question, decision or item needed, and from whom.
- **Next steps:** the next planned actions.

**Stage 4 deliverable:** a current progress record that allows every team member to understand the state of all workstreams without needing to inspect every commit or notebook.

## 4. Living README requirement

Every work package must maintain a README from Stage 1 onward. It is a living project record, not a report written only at the end.

Each WP README must contain:

1. **Identity and ownership** — WP title, member/owner, status and last updated date.
2. **Objective and research questions** — what is being investigated and why.
3. **Scope** — what is included and explicitly excluded.
4. **Prerequisites** — relevant concepts, literature, tools and required data.
5. **Data and variables** — exact input files, columns, units, filters and known limitations.
6. **Methodology** — equations, assumptions, features, algorithms and rationale.
7. **Implementation** — code structure, environment and reproduction instructions.
8. **Progress** — completed, in progress, pending and next steps.
9. **Results and validation** — experiments, metrics, plots, tests and interpretation.
10. **Limitations and uncertainty** — what the method cannot establish.
11. **Human decisions and approvals** — decisions requested, decisions received and who approved them.
12. **Blockers and alternatives** — current blockers and investigated workarounds.
13. **Integration contract** — proposed input/output files, schemas, units and meaning of outputs.
14. **References** — papers, documentation, data sources and other evidence.

Every material change to the method, assumptions, data handling or output schema must be reflected in the README.

## 5. Shared project rules

These rules apply to all work packages unless the team explicitly approves a documented change.

### Technical approach

- Python is the common implementation language.
- Use physics-informed calculations and established vehicle/energy equations as the foundation.
- Traditional machine learning may be used where it provides a defensible benefit.
- Deep learning and neural networks are outside the current project scope.
- Each model or algorithm must document its inputs, target (if applicable), training/validation design, parameters, evaluation and limitations.
- Prefer session/lap-aware validation over random row splits when adjacent telemetry samples could leak information across train/test sets.

### Data and units

- The shared data pipeline is the common starting point. Work packages must not independently redefine the source data.
- Raw source files are immutable. Derived files must be stored separately and traceably.
- Use snake_case for new column and file names.
- Use SI units where appropriate; **vehicle speed remains in km/h** throughout the project unless a specific calculation requires a documented conversion.
- Preserve source timestamps and documented time references. Do not silently join data using assumed timing offsets.
- Document every derived feature and its formula, unit and source columns.

### Approved data-handling decisions

1. **`iacc`:** retain all laps, including those with `iacc=false`, and retain the source indicator. Do not automatically exclude these laps. Timing-sensitive analysis must consider the indicator and disclose its handling.
2. **Throttle:** preserve the source values exactly as received. Do not clamp, modify or add additional per-sample flags for values outside the documented range. The observed range may be described in an audit without modifying the data.
3. **Missing values:** preserve missing values as blanks in the initial pipeline. Do not interpolate or delete rows in the common initial dataset. A work package may test a justified missing-data treatment for a particular algorithm, but it must be a separate derived version, clearly documented and never overwrite the common data.
4. **No silent fabrication:** do not invent missing measurements, physical parameters, event labels or ground truth.
5. **No unapproved cleaning:** do not silently smooth, resample, clip, impute, remove outliers or change source values.

### Scientific integrity

Clearly distinguish:

- **Observed:** directly present in the source data.
- **Calculated:** derived using a documented equation or transformation.
- **Inferred:** a possible explanation supported by evidence, with uncertainty stated.
- **Assumed:** a value or condition introduced for modelling and requiring justification/approval.
- **Confirmed:** supported by sufficiently strong evidence for the specific claim.

No member should claim a phenomenon occurred merely because telemetry is consistent with it. For example, a speed drop may be consistent with clipping, regeneration or lift-and-coast, but telemetry alone may not prove which mechanism caused it.

## 6. Decisions, approvals and escalation

A member can make routine implementation choices within the approved scope and document them. Team review is required before:

- changing a shared data schema or common preprocessing rule;
- introducing a shared physical assumption or parameter that affects other WPs;
- changing a research objective or materially narrowing its scope;
- treating an inferred event as confirmed ground truth;
- adopting a method that changes the interpretation of shared results;
- changing another WP's output contract.

When requesting a decision, provide the question, why it matters, available options, evidence, recommendation and impact of delaying the decision.

## 7. Progress update template

Use this format for team updates:

```text
WORK PACKAGE:
OWNER:
UPDATED:

COMPLETED:
- ...

IN PROGRESS:
- ...

PENDING:
- ...

BLOCKERS:
- ... / None

REQUIRED INPUT / DECISION:
- ... / None

NEXT STEPS:
- ...

FILES / RESULTS UPDATED:
- ...
```

A blocker report should additionally identify what has already been tried, what alternatives were considered, why they were rejected (if applicable), and the exact input needed to resume.

## 8. Definition of ready for final integration

A work package is ready for integration when:

- its objective and scope are clear;
- its implementation can be reproduced from documented inputs;
- its outputs have stable names, schemas, units and meanings;
- key calculations and results have been tested or otherwise validated;
- assumptions and limitations are explicit;
- the README and progress record are current;
- unresolved issues are disclosed rather than hidden.

Integration will connect and compare independently produced results. It must not erase differences in methodology or uncertainty. Conflicts between work packages should be investigated and resolved with evidence, not forced into agreement.

## 9. Team agreement

By working under this protocol, each member agrees to maintain independent ownership, communicate progress, document decisions, preserve data provenance and raise blockers early. Changes to this protocol require team agreement and a recorded update to this file.
