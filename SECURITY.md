# Security policy

## Reporting

Use GitHub private vulnerability reporting for credential exposure,
synthetic-boundary escape, cross-tenant behavior, trace pseudonymization,
migration, restore, or artifact-disclosure findings. Include a minimal generated
fixture and the affected reference version.

## Repository boundary

Generated fixtures enter through the synthetic-data checks. Live laboratory
records, vendor exports, credential values, signing material, and regulated
evidence stay in their approved systems.

The implementation repository uses workload IAM roles, Parameter Store, Secrets
Manager, KMS, and provider-native logging. This repository uses a deterministic
provider that exposes reference metadata while keeping resolved values private.

GitHub secret scanning and push protection provide repository-level prevention.
Provider-side monitoring and credential rotation provide defense in depth.
