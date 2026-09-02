from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Protocol

from .domain import digest


ROLE_ARN = re.compile(
    r"^arn:aws:iam::111122223333:role/lims-eln-simulated-[A-Za-z0-9+=,.@_/-]{1,96}$"
)
KMS_ARN = re.compile(
    r"^arn:aws:kms:[a-z0-9-]+:111122223333:key/"
    r"00000000-0000-4000-8000-[0-9a-f]{12}$"
)
PARAMETER_NAME = re.compile(r"^/lims-eln/simulated/[a-z0-9/-]{1,180}$")
SECRET_ID = re.compile(r"^lims-eln/simulated/[a-z0-9/-]{1,180}$")


class ConfigurationBoundary(ValueError):
    """Runtime configuration receives an explicit simulated-provider contract."""


@dataclass(frozen=True)
class ResolvedValue:
    value: str = field(repr=False)
    version: str


class AwsConfigurationProvider(Protocol):
    def parameter(self, name: str) -> ResolvedValue: ...

    def secret(self, secret_id: str, stage: str) -> ResolvedValue: ...


@dataclass(frozen=True)
class AwsRuntimeReference:
    workload_role_arn: str
    kms_key_arn: str
    parameter_names: tuple[str, ...]
    secret_ids: tuple[str, ...]
    secret_stage: str
    cache_ttl_seconds: int

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AwsRuntimeReference":
        required = {
            "workload_role_arn",
            "kms_key_arn",
            "parameter_names",
            "secret_ids",
            "secret_stage",
            "cache_ttl_seconds",
        }
        if set(value) != required:
            raise ConfigurationBoundary("runtime configuration requires the released AWS reference fields")
        reference = cls(
            workload_role_arn=value["workload_role_arn"],
            kms_key_arn=value["kms_key_arn"],
            parameter_names=tuple(value["parameter_names"]),
            secret_ids=tuple(value["secret_ids"]),
            secret_stage=value["secret_stage"],
            cache_ttl_seconds=value["cache_ttl_seconds"],
        )
        reference.validate()
        return reference

    def validate(self) -> None:
        if not ROLE_ARN.fullmatch(self.workload_role_arn):
            raise ConfigurationBoundary("workload_role_arn requires a bounded AWS IAM role ARN")
        if not KMS_ARN.fullmatch(self.kms_key_arn):
            raise ConfigurationBoundary("kms_key_arn requires a bounded AWS KMS key ARN")
        if not self.parameter_names or not all(
            PARAMETER_NAME.fullmatch(name) for name in self.parameter_names
        ):
            raise ConfigurationBoundary(
                "parameter_names require generated Parameter Store paths in the simulated namespace"
            )
        if not self.secret_ids or not all(SECRET_ID.fullmatch(name) for name in self.secret_ids):
            raise ConfigurationBoundary(
                "secret_ids require generated Secrets Manager identities in the simulated namespace"
            )
        if len(set(self.parameter_names)) != len(self.parameter_names) or len(
            set(self.secret_ids)
        ) != len(self.secret_ids):
            raise ConfigurationBoundary("runtime configuration references require unique identities")
        if self.secret_stage not in {"AWSCURRENT", "AWSPREVIOUS"}:
            raise ConfigurationBoundary("secret_stage requires an AWS rotation stage")
        if type(self.cache_ttl_seconds) is not int or not 30 <= self.cache_ttl_seconds <= 900:
            raise ConfigurationBoundary("cache_ttl_seconds requires a bounded 30-900 second policy")


@dataclass(frozen=True)
class RuntimeConfiguration:
    parameters: dict[str, str] = field(repr=False)
    secrets: dict[str, str] = field(repr=False)
    receipt: dict[str, Any]


class SyntheticAwsProvider:
    """Deterministic Parameter Store and Secrets Manager behavior for this forecast."""

    def parameter(self, name: str) -> ResolvedValue:
        return ResolvedValue(
            value=f"synthetic-parameter/{digest(name)}",
            version=f"ssm-{digest({'name': name})[-12:]}",
        )

    def secret(self, secret_id: str, stage: str) -> ResolvedValue:
        return ResolvedValue(
            value=f"synthetic-material/{digest({'secret_id': secret_id, 'stage': stage})}",
            version=f"sm-{digest({'secret_id': secret_id, 'stage': stage})[-12:]}",
        )


def resolve_runtime_configuration(
    reference: AwsRuntimeReference,
    provider: AwsConfigurationProvider,
) -> RuntimeConfiguration:
    reference.validate()
    parameters = {name: provider.parameter(name) for name in reference.parameter_names}
    secrets = {
        secret_id: provider.secret(secret_id, reference.secret_stage)
        for secret_id in reference.secret_ids
    }
    if any(not item.value or not item.version for item in (*parameters.values(), *secrets.values())):
        raise ConfigurationBoundary(
            "resolved settings require values and versions from the workload-role provider"
        )
    receipt = {
        "evidence_mode": "simulated",
        "provider_contract": "aws-ssm-and-secrets-manager",
        "workload_role_arn": reference.workload_role_arn,
        "kms_key_arn": reference.kms_key_arn,
        "parameter_versions": {
            name: item.version for name, item in sorted(parameters.items())
        },
        "secret_reference_digests": {
            digest(secret_id): item.version for secret_id, item in sorted(secrets.items())
        },
        "secret_stage": reference.secret_stage,
        "cache_ttl_seconds": reference.cache_ttl_seconds,
        "rotation_behavior": "refresh by version stage within the bounded cache window",
        "receipt_projection": "references, versions, role, key, and cache policy",
    }
    return RuntimeConfiguration(
        parameters={name: item.value for name, item in parameters.items()},
        secrets={name: item.value for name, item in secrets.items()},
        receipt=receipt,
    )
