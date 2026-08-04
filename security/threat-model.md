# Synthetic security and privacy checks

## Protected assets

- specimen identity and scientific meaning;
- raw and derived artifacts;
- tenant, site, and project boundaries;
- credentials, configuration, and recovery material.

## Exercised behavior

| Exercise | Established control | Observable outcome |
| --- | --- | --- |
| Cross-tenant request | application tenant policy and PostgreSQL RLS | request stays within the selected tenant |
| Sensitive trace value | OpenTelemetry redaction processor | trace retains class and pseudonym |
| Rotated credential | workload IAM and Secrets Manager stage | next cache refresh uses the new version |
| Webhook replay | signature verification and idempotency key | one durable effect and convergent readback |
| Telemetry interruption | selected telemetry platform buffering | delivery resumes with measurable continuity |

The repository exercises these behaviors with generated inputs. Implementation
environments use their selected identity, policy, database, AWS, and observability
platforms.
