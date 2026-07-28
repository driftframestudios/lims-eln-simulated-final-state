# Simulated AWS runtime-configuration boundary

This counterfactual models the production retrieval contract with a deterministic,
repository-local provider. It makes the placement, authority, rotation, caching, and
receipt rules executable while keeping live AWS calls and credential values outside
the simulation.

## Placement

| Material | AWS responsibility | Runtime use |
|---|---|---|
| Vendor base URL, timeout, feature posture, resource identifiers | Systems Manager Parameter Store | resolved by exact parameter path and version |
| Vendor credential, webhook signing material, trace pseudonymization key | Secrets Manager | resolved by exact secret identity and rotation stage |
| Service authorization | workload IAM role | short-lived SDK credential chain supplies request authority |
| Encryption | named KMS key | Parameter Store and Secrets Manager policies bind protected material to the approved key |

## Least-privilege policy shape

The workload role receives `ssm:GetParameter` for the named application paths,
`secretsmanager:GetSecretValue` for the named secret resources, and `kms:Decrypt`
through the approved services for the named key. Resource ARNs bind each permission to
the environment and application namespace. Repository workflows carry zero live
provider authority.

## Runtime behavior

1. Resolve typed Parameter Store values by exact path.
2. Resolve Secrets Manager values by exact identity and `AWSCURRENT` or
   `AWSPREVIOUS` stage.
3. Retain values in process memory for the bounded 30-900 second cache window.
4. Refresh by version stage so rotation becomes visible within the declared window.
5. Return retrieval failures to the bounded readiness and retry path.
6. Emit a value-free receipt containing references, versions, workload role, KMS key,
   cache policy, and rotation behavior.

The executable fake provider produces deterministic synthetic material. Tests verify
that resolved values stay outside receipts and generated artifacts.
