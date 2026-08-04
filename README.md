# LIMS/ELN Vendor-Evaluation Reference

This repository is an advisory, synthetic comparison of LIMS and ELN integration
behaviors. It helps collaborators inspect vendor API semantics, ambiguous-write
reconciliation, event delivery, data portability, restore behavior, configuration
references, and observable outcomes before selecting or changing a platform.

Scientific, Quality, Regulatory, security, operational, and purchasing decisions
remain in their established systems of record. This repository supplies advisory
technical comparison material with `runtime_effect: none`.

## What runs

The Python reference evaluates:

- deterministic Sapio, Benchling, and LabKey adapter behavior;
- idempotent replay and authoritative readback after ambiguous writes;
- a thin transactional-outbox-style event envelope and readback outcome;
- representative data migration, restore, failure-twin, and data-exit comparisons;
- AWS Parameter Store and Secrets Manager reference handling without emitted values;
- synthetic fixture boundaries, trace redaction, and bounded telemetry summaries.

The runtime emits one portable `result.json` containing vendor behavior,
migration and restore comparison, event delivery, trace summary, and synthetic
limitations.

## Run it

```bash
python -m unittest discover -s tests -v
PYTHONPATH=src python -m lims_eln_sim.cli \
  --fixture fixtures/golden-specimen.json \
  --intended-use-profile specification/intended-use-and-applicability-profile.json \
  --migration-corpus fixtures/representative-migration-corpus.json \
  --database-reference database/vendor-evaluation-database-reference-v1.json \
  --output build/evaluation
```

The result names its synthetic limits and has `runtime_effect: none`.

## Database and migration references

The JSON documents under `database/` are detailed design references for native
PostgreSQL primitives, tenant-leading keys, exact scientific quantities, temporal
semantics, Flyway-managed evolution, and migration comparison. Flyway remains the
migration engine and delivery systems retain their existing release records.

Repository-owned PostgreSQL schema evolution belongs to Flyway. Vendor-owned LIMS
and ELN schemas follow vendor-supported lifecycle paths. Cross-platform data
movement remains a separately checkpointed and reconciled activity.

## Durable collaboration context

[`machine-node.json`](machine-node.json) is a flat documentation index with
`runtime_effect: none`. It points to the active evaluation surfaces and the
quarantine location.

Earlier control-plane prototypes, acceptance drafts, release manifests, receipt
logic, Coordination Horizon, first-receipt record, and detailed database oracle
validator are retained under [`reference/quarantine/`](reference/quarantine/) for
historical study. The installed package and CI suite exclude this material.

## Safety and privacy

Only synthetic fixtures belong in this repository. Runtime traces replace protected
values with classifications and keyed pseudonyms. Configuration output retains
parameter and secret references, versions, role identifiers, KMS identifiers, and
rotation behavior while resolved values remain in process memory.

## Branching

Use repository-hosted branch protection and required checks for delivery policy.
GitHub remains the branch-policy implementation.
