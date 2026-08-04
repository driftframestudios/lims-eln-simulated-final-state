# Simulated deployment model

The final-state forecast uses a versioned canonical service, durable inbox and outbox,
adapter workers, relational state, artifact storage, workload identity, and
OpenTelemetry-compatible signals. This repository supplies an in-memory deterministic
realization of those contracts so every collaborator can run the full journey with
Python's standard library.

## Projected production responsibilities

| Capability | Projected responsibility | Qualification evidence |
|---|---|---|
| Canonical state | relational store with revision and tenant keys | persistence, concurrency, backup, restore |
| Artifacts | content-addressed object storage | byte parity, retention, recovery, data exit |
| Vendor adapters | bounded workers with inbox/outbox and reconciliation | configured-tenant conformance |
| Identity | workload and user identity with short-lived credentials | access review, rotation, revocation |
| Telemetry | traces, metrics, logs, dashboards, alerts | denominator-rich SLO and incident exercise |
| Evidence | governed raw store plus redacted manifests | digest, locator, and observed outcome |

Actual delivery selects concrete infrastructure through the implementation
repository and its established platform processes.
