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

## Shared contract boundary

The simulator reads the contract-v1 golden specimen journey from its bound package
resource and uses that five-command sequence to drive the existing accession-through-
release slice. Each run emits `scenario-execution.json` with source command, actor,
time, payload digest, and projected legacy state, plus `observation-envelope.json`
with the shared `ObservationEnvelope` shape and canonical contract digest.

The repository stays runnable while the sibling distribution remains private. It
packages byte-identical scenario and schema snapshots with their raw and canonical
digests. A focused conformance command compares those snapshots and emitted values
with the authoritative Pydantic models whenever the private package or sibling source
is available:

```bash
python tools/check_contract_conformance.py \
  --contract-source ../lims-eln-program-specification/src
```

Once the private distribution is available to Python 3.12+ installers, the optional
`contract-conformance` extra becomes the direct version-pinned path. The snapshot
remains a bounded fallback for standalone forecast execution on the repository's
current Python 3.11+ runtime.

## Run it

```bash
python -m unittest discover -s tests -v
PYTHONPATH=src python -m lims_eln_sim.cli \
  --fixture fixtures/golden-specimen.json \
  --intended-use-profile specification/intended-use-and-applicability-profile.json \
  --migration-corpus fixtures/representative-migration-corpus.json \
  --output build/simulation
```

The command validates the synthetic-data contract and writes a deterministic
`result.json`, contract-v1 `scenario-execution.json` and
`observation-envelope.json`, closed receipt bundle, migration report, restore
manifest, security exercise, bounded-caller evidence, telemetry summary, acceptance
decisions, and a governance-2.0-conformant `simulated-receipt-closure.json`. It also
writes a 2.0.1 closure bundle whose source-result digest allows an independent
comparator to reproduce the aggregate artifact. The byte-identical promoted candidate
is retained at `release/future-reality-2028-06-30-v1.json`; the aggregate validation
gate regenerates and compares it after the complete Python test matrix. Generated
build output remains a transient workflow artifact.

The retained database oracle lives at
[`database/final-state-database-oracle-v1.json`](database/final-state-database-oracle-v1.json).
Its validator recomputes the data-contract, migration-manifest, migration-receipt,
release-receipt, and complete-bundle digests. This provides the comparative system
with one deterministic final-state coordinate while preserving the boundary between
simulated acceptance and accountable environment observation.

The selected future assigns repository-owned PostgreSQL schema evolution to Flyway
Community 13.0.0. Vendor-owned LIMS and ELN schemas continue through their supported
upgrade paths and APIs. Cross-platform scientific data movement remains a separately
checkpointed and reconciled program concern, so the simulation evaluates semantic
parity without modeling a second schema-migration runner.

## Coordination Horizon

[`COORDINATION-HORIZON.json`](COORDINATION-HORIZON.json) describes the current focus,
approaching promotion candidates, retained possibilities, and re-entry path without
binding the collaboration to a particular planning vocabulary.

[`machine-node.json`](machine-node.json) and [`first-receipt.json`](first-receipt.json)
provide an orientation-only re-entry surface with contract digests, evidence posture,
source permissions, invalidation conditions, and the independent observed-comparison
path.

[`constellation.lock.json`](constellation.lock.json) records the 0.3 candidate
coordinates with explicit promotion placeholders and preserved seed lineage.
[`ledgers/assumptions.json`](ledgers/assumptions.json) resolves every assumption
identifier cited by the selected-future closure and names its recalculation trigger.

## Branching

This repository uses a GitFlow-like pattern:

- `main` contains released forecast baselines.
- `develop` integrates the next forecast.
- `feature/*` carries bounded scenario or model work.
- `release/*` freezes comparison inputs and accepts stabilization changes.
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
