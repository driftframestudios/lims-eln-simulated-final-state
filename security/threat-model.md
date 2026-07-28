# Simulated production security and privacy model

## Protected assets

- specimen identity and scientific meaning;
- raw and derived artifacts;
- audit chronology and signature meaning;
- tenant, site, and project boundaries;
- credentials, configuration, and recovery material.

## Exercised boundaries and replacement behavior

| Exercise | Applied boundary | Replacement behavior |
|---|---|---|
| Cross-tenant read | tenant authorization gate | governed transfer request with accountable approval |
| Missing release role | role gate | explicit role-assignment workflow |
| Sensitive trace value | classification filter | classification label plus stable digest |
| Revoked token | credential gate | fresh workload identity through approved rotation |
| Webhook replay | signed request identity | idempotent readback and recorded reconciliation |
| Break-glass access | time-bound elevated role | review, expiry, and closure receipt |

Production exercises use approved synthetic probes and governed evidence storage.
The simulation stores representative results with `evidence_mode: simulated`.

