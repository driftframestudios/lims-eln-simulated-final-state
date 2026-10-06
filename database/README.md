# Final-state database comparison oracle

## Reader job

Use this directory when you need to inspect or verify the database coordinate
that the selected future contributes to cross-system comparison. Begin with
[`final-state-database-oracle-v1.json`](final-state-database-oracle-v1.json), then
use the focused proof below to confirm that its derived coordinates match the
repository role manifest.

## Authority

[`final-state-database-oracle-v1.json`](final-state-database-oracle-v1.json) is
the canonical selected-future database projection. The
[`repository role manifest`](../release/repository-role.json) owns the repository
identity, release identity, oracle path, and content-addressed binding. Executable
validation in [`database_oracle.py`](../src/lims_eln_sim/database_oracle.py) and
the source-owned tests define how the coordinate is checked.

The oracle binds four layers into one reproducible coordinate:

1. a semantic data contract with native PostgreSQL primitives;
2. an expand/backfill/validate/cutover/contract migration manifest;
3. a typed qualification-rehearsal receipt with reconciliation and recovery
   evidence; and
4. a release receipt binding Scientific, Quality, Regulatory, Security and
   Privacy, and Operations acceptance projections.

The repository validator recomputes the data-contract, migration-manifest,
migration-receipt, release-receipt, evidence-bundle, and complete-oracle
digests and compares the resulting coordinate with
[`release/repository-role.json`](../release/repository-role.json). Leaf settings,
tool, script, schema, checkpoint, and decision digests are declared
selected-future values whose shape and cross-reference consistency are validated.

## Quickest proof

From the repository root, run:

```sh
python3 -m unittest \
  tests.test_simulation.SimulationTests.test_database_oracle_binds_contract_manifest_and_release_receipts \
  -v
```

A passing result establishes that the oracle validates, its derived release
coordinates match the role manifest, and its canonical digest matches the
manifest binding. Run `python3 tools/validate_repository.py` when the receiving
decision also needs deterministic replay, retained-bundle agreement, living
coordination checks, and the repository's credential-shape scan.

## Evidence ceiling

This proof establishes the declared selected-future coordinate for synthetic
inputs. Its evidence is explicitly simulated and has no production
authorization effect. Live PostgreSQL execution, Flyway execution against a
receiving environment, vendor-owned schema behavior, production qualification,
and observed semantic equivalence each remain available through their own
accountable evidence routes.

## Return path

- Return to the [root README](../README.md#current-accepted-coordinate) for the
  current release, 10/4/3 result, and scientific mapping receiver.
- Use the [Coordination Horizon](../COORDINATION-HORIZON.json) and
  [First Receipt](../first-receipt.json) when the oracle comparison changes a
  receiving decision.
- Use the [repository collaboration ground](../AGENTS.md) before changing the
  oracle, its validator, or its release binding.
