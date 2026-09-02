# LIMS/ELN Simulated Final State

This repository is an independently runnable counterfactual for a mature laboratory
integration platform. It lets a hybrid team inspect a complete forecast before the
delivery system reaches the same decisions.

The runtime resolves entirely from this repository, Python's standard library, and
synthetic fixtures. The actual implementation remains an independent system. Ideas
move from this simulation into delivery through reviewed decisions and released
specifications.

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
python tools/check_contract_conformance.py \
  --contract-source ../lims-eln-program-specification/src
```

In an authenticated Python 3.12+ environment, the optional `contract-conformance`
extra installs that exact source commit. The snapshot remains the standalone forecast
path on the repository's current Python 3.11+ runtime; a later reviewed full commit
can replace the pin without changing the shared projection identity.

## Run it

```bash
python -m unittest discover -s tests -v
PYTHONPATH=src python -m lims_eln_sim.cli \
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
Governance 2.1.0 release. The First Receipt adds repository-owned selected-future
authority fields beyond the shared orientation schema; the local release-boundary
checks validate those fields and keep their simulated meaning explicit.

[`receipts/promotion-receipt.json`](receipts/promotion-receipt.json) records the
observed signed release event, accepted source objects, reproducible archive,
hosted checks, and local verification while preserving simulated forecast authority.
`python tools/verify_release_coordinate.py` verifies the annotated tag, accepted
history, source tree, archive bytes, receipt carrier, and repository-trusted signer.

[`constellation.lock.json`](constellation.lock.json) records distinct observed
Simulation and Comparative coordinates for the same canonical selected-future
closure, together with preserved seed lineage. Evidence-led extensions remain
available when a documented material benefit earns their qualification cost.
[`ledgers/assumptions.json`](ledgers/assumptions.json) resolves every assumption
identifier cited by the selected-future closure and names its recalculation trigger.

## Branching

This repository uses a GitFlow-like pattern:

- `main` contains released forecast baselines and carries protected promotion.
- `develop` is the lean integration branch for the next forecast.
- `feature/*` carries bounded scenario or model work.
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
