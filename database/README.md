# Advisory Database Design Reference

`vendor-evaluation-database-reference-v1.json` gives the synthetic vendor
comparison a concrete PostgreSQL design surface. The executable check reads:

- engine family and supported version context;
- tenant-leading composite keys and forced row-level security;
- native temporal, boolean, exact numeric, identifier, and digest types; and
- the selected Flyway migration tool coordinate.

Flyway owns migration discovery, ordering, checksums, history, locking, and
execution. The application uses expand-and-contract changes for compatibility
across releases. Vendor-owned databases use vendor-supported lifecycle tooling.

Earlier oracle, migration-receipt, release, digest-binding, and acceptance
models are preserved under `reference/quarantine/database/` as design history.
