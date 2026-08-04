# Final-state database comparison oracle

`final-state-database-oracle-v1.json` is the canonical selected-future database
projection. It binds four layers into one reproducible coordinate:

1. a semantic data contract with native PostgreSQL primitives;
2. an expand/backfill/validate/cutover/contract migration manifest;
3. a typed qualification-rehearsal receipt with reconciliation and recovery
   evidence; and
4. a release receipt binding Scientific, Quality, Regulatory, Security and
   Privacy, and Operations acceptance projections.

The repository validator recomputes every nested digest and compares the
resulting coordinate with `release/repository-role.json`. The evidence remains
explicitly simulated and carries no production authorization effect. An
environment-observed implementation can reference the coordinate as its
comparison target while retaining separately accountable decisions.
