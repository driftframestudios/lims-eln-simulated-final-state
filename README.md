# LIMS/ELN Simulated Final State

This repository is an independently runnable model of one possible mature laboratory
integration platform. The model is a counterfactual: a deliberately selected future
that lets a hybrid team inspect a complete forecast before the delivery system
reaches the same decisions.

The runtime resolves entirely from this repository, Python's standard library, and
synthetic fixtures. The actual implementation remains an independent system. Ideas
move from this simulation into delivery through reviewed decisions and released
specifications.

## Start with one scenario

**Quick start, from this checkout with Python 3.12 or newer:**

```bash
PYTHONPATH=src python3 -m lims_eln_sim.cli \
  --fixture fixtures/golden-specimen.json \
  --intended-use-profile specification/intended-use-and-applicability-profile.json \
  --migration-corpus fixtures/representative-migration-corpus.json \
  --database-oracle database/final-state-database-oracle-v1.json \
  --output build/first-scenario
```

Read `build/first-scenario/result.json` for the result and
`observation-envelope.json` for its source-bound comparison input. The command
uses the standard library and repository-owned synthetic fixtures. Choose a
fresh output directory for a separate experiment.

Run a selected future laboratory workflow and inspect the result it produces.
The core simulator uses Python's standard library. The [run example](#run-it)
writes scenario results and observation artifacts to a chosen output directory.
For a first experiment, retain the Golden Specimen fixture and inspect the
result before changing one declared input.

- **Read first:** the [published comparison](https://cometspectrum.io/reports/golden-specimen/comparison.html) shows where the two modeled paths agree and differ.
- **Run a local scenario:** use [Run it](#run-it), then inspect the files in the selected output directory.
- **Understand the storage model:** the [database guide](database/README.md) connects the oracle, its assumptions, and the fitting checks.

For insurance and administrative questions, begin with Program's
[contract examples](https://github.com/driftframestudios/lims-eln-program-specification/blob/main/docs/README.md#try-the-administrative-contract-kit).
The [administrative scenario guide](docs/administrative-scenarios.md) provides
the integration branch's versioned pack, independent expected outcomes, and
an isolated quick start. Program owns its study representation; Simulation
owns the authored inputs and expected behavior. The signed forecast remains
the accepted release baseline while this source extension receives review.

Choose an environment through [Program's researcher-entry guide](https://github.com/driftframestudios/lims-eln-program-specification/issues/54).
Continue scenario and recovery procedures through [#39](https://github.com/driftframestudios/lims-eln-simulated-final-state/issues/39).

## Current accepted coordinate

The [`repository role manifest`](release/repository-role.json) identifies this
repository as the `simulated_final_state`, with repository release `0.3.1` and
selected-future release `forecast-2028-FR-v1`. The
[`constellation lock`](constellation.lock.json) keeps that signed Simulation
baseline distinct from the accepted Enterprise and Comparative coordinates.

The current comparison classifies all 17 Golden Specimen leaves: **10 agree, 4
vary in explained ways, and 3 carry materially different measurement meanings**.
The Enterprise result expresses DNA concentration while the selected future
expresses copy number.

**Current receiver:** accountable scientific mapping for the analyte, value, and
unit relationship in [Comparative #44](https://github.com/driftframestudios/lims-eln-comparative-evidence/issues/44). The
[`Coordination Horizon`](COORDINATION-HORIZON.json) owns the next action: record
the supported measurement relationship, then assign any resulting change to its
owning source or to a successor selected-future release. The signed release stays
available as the recoverable baseline for that decision.

## Choose a route

| Reader job | Start here | What this route establishes |
| --- | --- | --- |
| Evaluate the repository's role and current result | [`release/repository-role.json`](release/repository-role.json) and [`constellation.lock.json`](constellation.lock.json) | Accepted Simulation identity, exact sibling coordinates, and the current 10/4/3 comparison |
| Run the selected future | [Run it](#run-it) | Deterministic behavior from synthetic inputs and the retained database oracle |
| Inspect the database comparison target | [`database/README.md`](database/README.md) | Oracle authority, focused proof, evidence ceiling, and return path |
| Continue the current scientific mapping | [`COORDINATION-HORIZON.json`](COORDINATION-HORIZON.json) and [`first-receipt.json`](first-receipt.json) | Accountable mapping action, acceptance signal, and safe re-entry |
| Re-enter repository work | [`AGENTS.md`](AGENTS.md) and the [skill catalog](.agents/skills/README.md) | Branch, source, validation, and bounded workflow routes |

Read [`AGENTS.md`](AGENTS.md) for the current source, branch, evidence, writing,
and validation route. The [repository-local skill catalog](.agents/skills/README.md)
helps choose among four bounded workflows:

- [`repository-reentry`](.agents/skills/repository-reentry/SKILL.md) reconstructs
  current source, accepted release, living orientation, and comparison state;
- [`source-authority-mapping`](.agents/skills/source-authority-mapping/SKILL.md)
  traces assumptions, executable behavior, artifacts, release evidence, and
  receiving use while each retains its authority;
- [`constellation-coherence-reconciliation`](.agents/skills/constellation-coherence-reconciliation/SKILL.md)
  reconciles accepted sibling coordinates with living Simulation carriers; and
- [`contextual-jargon-scan`](.agents/skills/contextual-jargon-scan/SKILL.md)
  reviews shorthand in stride while preserving exact technical and governed
  terms.

These skills are self-contained and carry `source_band: public_possible` while
natural use tests their local fit. A separate public-ready review is the event
that can promote one into a public projection.

## Selected future reality

Every generated record declares:

```json
{
  "evidence_mode": "simulated",
  "assurance_stage": "verified",
  "simulation_authority": "definitive_within_selected_future_reality",
  "accountable_observation_required": false,
  "environment_observed_closure": "separate_unasserted_state",
  "production_authorization_effect": "none",
  "future_reality_version": "future-reality-2028-06-30-v1"
}
```

The simulation selects one complete future version of reality and treats that version
as the comparison baseline. Configured vendor environments, migration and restore,
production-shape security and observability, and independent Scientific, Quality, and
Regulatory acceptance all close inside that declared future. Each closure retains its
simulation basis, reality version, checks, decisions, and digest.

This posture makes the simulated program complete on its own terms. A later
environment encounter remains available as a separate comparison surface and does
not reopen the simulated closures.

## What the simulation covers

- accession, custody, instrument ingestion, review, release, and correction;
- Sapio, Benchling, and LabKey behavior through deterministic emulators;
- stable-request reconciliation after ambiguous vendor writes;
- representative migration, rollback, clean restore, and data exit;
- a canonical database oracle binding native PostgreSQL primitives, an
  expand-through-contract migration manifest, rehearsal evidence, recovery
  objectives, and five acceptance projections into one comparison coordinate;
- tenant authorization, recursive keyed trace pseudonymization, telemetry, and incident exercises;
- an executable AWS Parameter Store and Secrets Manager provider boundary with
  value-free receipts;
- draft scientific, Quality, Regulatory, security, and operations acceptance packets;
- a bounded-caller control plane with read, narrow-write, and approval-gated
  broad-write operations;
- failure twins for missing approval, cross-tenant scope, and unreleased operations;
- assumptions, forecasts, decisions, falsifiers, and four fully closed simulated
  receipt manifests.

The aggregate repository check runs the simulation twice in isolated directories,
parses every generated document through the strict JSON boundary, and compares the
complete set of output paths and their exact bytes. It also derives the observation
and scenario execution digests named by the release manifest. A successful check
therefore binds the retained oracle and assumptions to one repeatable artifact set;
configured environment evidence remains a separate comparison input.

Repository validation supplies fresh, caller-controlled temporary directories for
the complete artifact comparison. Within those directories, each final artifact is
opened with the platform's `O_NOFOLLOW` support and verified as a regular file.
Artifact verification completes on platforms that supply this final-path protection;
other platforms receive a boundary error before artifact bytes enter comparison.
Concurrent replacement of parent-directory components remains outside this
repository-local verifier's claim. A caller sharing parent paths with an untrusted
actor needs a directory-descriptor traversal or an equivalently isolated execution
boundary.

## Shared contract boundary

The simulator reads the contract-v1 golden specimen journey from its bound package
resource and uses that five-command sequence to drive the existing accession-through-
release slice. Each run emits `scenario-execution.json` with source command, actor,
time, payload digest, and projected legacy state, plus `observation-envelope.json`
with the shared `ObservationEnvelope` shape and canonical contract digest.

The repository stays runnable without fetching its sibling package. It packages
byte-identical scenario and schema snapshots with their raw and canonical digests.
The accepted Program 0.3.1 package is also available to authenticated readers through
one full-commit Git requirement, pinned at
`4d06eeb7f96910311fbcb7f51547c978b6a07290`. A focused conformance command compares
the snapshots and emitted values with the authoritative Pydantic models whenever the
installed package or a sibling source checkout is available:

```bash
python3 tools/check_contract_conformance.py \
  --contract-source ../lims-eln-program-specification/src
```

In an authenticated Python 3.12+ environment, the optional `contract-conformance`
extra installs that exact source commit. The snapshot remains the standalone forecast
path on the repository's current Python 3.11+ runtime; a later reviewed full commit
can replace the pin without changing the shared projection identity.

## Run it

```bash
python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m lims_eln_sim.cli \
  --fixture fixtures/golden-specimen.json \
  --intended-use-profile specification/intended-use-and-applicability-profile.json \
  --migration-corpus fixtures/representative-migration-corpus.json \
  --database-oracle database/final-state-database-oracle-v1.json \
  --output build/simulation
```

The command validates the synthetic-data contract and writes a deterministic
`result.json`, contract-v1 `scenario-execution.json` and
`observation-envelope.json`, closed receipt bundle, migration report, restore
manifest, security exercise, bounded-caller evidence, telemetry summary, acceptance
decisions, and a governance-2.0-conformant `simulated-receipt-closure.json`. It also
writes a 2.0.1 closure bundle whose source-result digest allows an independent
comparator to reproduce the aggregate artifact. The tagged selected-future release
is retained at `release/future-reality-2028-06-30-v1.json`; the aggregate validation
gate regenerates and compares it after the complete Python test matrix. Generated
build output remains a transient workflow artifact.

The retained database oracle lives at
[`database/final-state-database-oracle-v1.json`](database/final-state-database-oracle-v1.json).
Each run receives this oracle explicitly. Its validator recomputes the data-contract,
migration-manifest, migration-receipt, release-receipt, and complete-bundle digests
before the shared Golden Specimen projection is emitted. The observation carries a
content-addressed oracle binding in `result.producer_detail`; its shared lifecycle,
custody, measurement, review, and release fields remain derived from the released
scenario and executed simulated state. This provides the comparative system with one
deterministic final-state coordinate while preserving the boundary between simulated
acceptance and accountable environment observation.

The selected future assigns repository-owned PostgreSQL schema evolution to Flyway
Community 13.0.0. Vendor-owned LIMS and ELN schemas continue through their supported
upgrade paths and APIs. Cross-platform scientific data movement remains a separately
checkpointed and reconciled program concern, so the simulation evaluates semantic
parity without modeling a second schema-migration runner.

## Coordination Horizon

[`COORDINATION-HORIZON.json`](COORDINATION-HORIZON.json) describes the current focus,
receiving work, retained possibilities, and re-entry path without
binding the collaboration to a particular planning vocabulary.

[`machine-node.json`](machine-node.json) and [`first-receipt.json`](first-receipt.json)
provide an orientation-only re-entry surface with contract digests, evidence posture,
source permissions, invalidation conditions, and the independent observed-comparison
path.

The Machine Node and Coordination Horizon validate directly against the accepted
Governance 2.2.0 release. The First Receipt retains six repository-owned
selected-future extensions beside the shared orientation schema; focused checks
keep their simulated meaning and exact extension boundary explicit.

[`receipts/promotion-receipt.json`](receipts/promotion-receipt.json) records the
observed signed release event, accepted source objects, reproducible archive,
hosted checks, and local verification while preserving simulated forecast authority.
`python3 tools/verify_release_coordinate.py` verifies the annotated tag, accepted
history, source tree, archive bytes, receipt carrier, and repository-trusted signer.

[`constellation.lock.json`](constellation.lock.json) records the signed Simulation
baseline alongside the accepted Enterprise `v0.3.2` and Comparative
`comparison-v0.3.2` releases. It keeps each release separate from the later commit
that records its observation. For Comparative Evidence, it also records the `docs`
revision and manifest digest that publish the 0.3.2 report at
`https://cometspectrum.io/`.
The lock's `constellation_version` therefore advances to `0.3.2`; the Simulation
repository remains `0.3.1`, and its signed forecast remains
`forecast-2028-FR-v1`.
`python tools/check_living_constellation.py` checks these accepted sibling
coordinates and the current receiving work; the aggregate repository validator
also runs this check.

The [current accepted coordinate](#current-accepted-coordinate) summarizes the
report's 10/4/3 classification and accountable scientific mapping receiver. The
lock owns the exact accepted identities; the Coordination Horizon and First
Receipt own the living action and return signal. A mapping decision can retain
the two measurements as distinct, define a supported transformation, assign a
source correction, or form a successor selected-future release.

Evidence-led extensions remain available when a documented material benefit earns
their qualification cost.
[`ledgers/assumptions.json`](ledgers/assumptions.json) resolves every assumption
identifier cited by the selected-future closure and names its recalculation trigger.

## Branching

This repository uses a GitFlow-like pattern:

- `main` contains released forecast baselines and carries protected promotion.
- `develop` is the lean integration branch for the next forecast.
- `feature/*` carries bounded scenario or model work; `fix/*` and `chore/*`
  carry focused corrections and upkeep into `develop`.
- `release/*` is a short-lived branch that freezes comparison inputs and
  accepts stabilization changes for one promotion.
- `hotfix/*` repairs a released simulation defect and returns the correction to
  `develop`.

Historical calibration tags use `forecast-YYYY-QN-rN`; selected-future releases
use `forecast-YYYY-FR-vN`. Published baselines remain immutable so later
comparisons preserve what the team believed at the time. The
[`ledgers/forecasts.json`](ledgers/forecasts.json) ledger is explicitly marked
as historical seed calibration for `forecast-2028-FR-v1`.

## Safety and privacy posture

Synthetic fixtures are the only permitted data class in this repository. A fixture
that resembles an external record is replaced with a generated identity, generated
timestamps, and generated artifacts before it enters version control. Secrets are
represented by stable placeholders. Runtime traces retain correlation and outcome
fields while sensitive values are replaced with classification labels and keyed
pseudonyms. Runtime-configuration receipts retain references, versions, workload role,
KMS key, cache policy, and rotation behavior while resolved values remain in process
memory.

Repository-wide provenance is recorded in [`AUTHORS`](AUTHORS). Package metadata
provides the corresponding author and license coordinates for built distributions.

## Confined container job

The [finite container entry](infra/README.container-job.md) reuses the constellation's
prepared-input and confined-runtime safeguards. Its source profile, focused
checks, output ownership, and release-evidence boundary remain inspectable.
