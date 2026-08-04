from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from .domain import digest, parse_instant


SHA256_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
IDENTIFIER_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$")
SEMVER_PATTERN = re.compile(r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$")
PHASE_TYPES = ("expand", "backfill", "validate", "cutover", "contract")
ACCEPTANCE_TYPES = {
    "scientific",
    "quality",
    "regulatory",
    "security_privacy",
    "operations",
}


class DatabaseOracleError(ValueError):
    """The database oracle receives a precise contract-completion path."""


@dataclass(frozen=True)
class DatabaseReleaseCoordinates:
    oracle_id: str
    oracle_version: str
    database_release: str
    data_contract_id: str
    data_contract_version: str
    data_contract_digest: str
    migration_manifest_id: str
    migration_manifest_version: str
    migration_manifest_digest: str
    migration_receipt_id: str
    migration_receipt_digest: str
    release_receipt_id: str
    release_receipt_digest: str
    schema_digest: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def validate_database_oracle(value: dict[str, Any]) -> DatabaseReleaseCoordinates:
    """Validate one self-contained selected-future database comparison oracle."""

    root_fields = {
        "oracle_version",
        "oracle_id",
        "evidence_mode",
        "authority",
        "actual_acceptance_required",
        "data_contract",
        "migration_manifest",
        "migration_receipt",
        "release_receipt",
        "coordinates",
    }
    _exact_fields(value, root_fields, "database oracle")
    if value["oracle_version"] != "1.0.0":
        raise DatabaseOracleError("database oracle requires version 1.0.0")
    _identifier(value["oracle_id"], "oracle_id")
    expected_posture = {
        "evidence_mode": "simulated",
        "authority": "simulation_only",
        "actual_acceptance_required": True,
    }
    for field, expected in expected_posture.items():
        if type(value[field]) is not type(expected) or value[field] != expected:
            raise DatabaseOracleError(
                f"database oracle requires {field}={expected!r}"
            )

    contract = _mapping(value["data_contract"], "data_contract")
    _validate_data_contract(contract)
    contract_digest = digest(contract)

    manifest = _mapping(value["migration_manifest"], "migration_manifest")
    _validate_migration_manifest(manifest, contract, contract_digest)
    manifest_digest = digest(manifest)

    migration_receipt = _mapping(value["migration_receipt"], "migration_receipt")
    _validate_migration_receipt(
        migration_receipt,
        contract,
        contract_digest,
        manifest,
        manifest_digest,
    )
    migration_receipt_digest = digest(migration_receipt)

    release_receipt = _mapping(value["release_receipt"], "release_receipt")
    _validate_release_receipt(
        release_receipt,
        contract,
        contract_digest,
        manifest,
        manifest_digest,
        migration_receipt,
        migration_receipt_digest,
    )
    release_receipt_digest = digest(release_receipt)

    expected_coordinates = DatabaseReleaseCoordinates(
        oracle_id=value["oracle_id"],
        oracle_version=value["oracle_version"],
        database_release=release_receipt["database_release"],
        data_contract_id=contract["data_contract_id"],
        data_contract_version=contract["version"],
        data_contract_digest=contract_digest,
        migration_manifest_id=manifest["migration_manifest_id"],
        migration_manifest_version=manifest["version"],
        migration_manifest_digest=manifest_digest,
        migration_receipt_id=migration_receipt["migration_receipt_id"],
        migration_receipt_digest=migration_receipt_digest,
        release_receipt_id=release_receipt["release_receipt_id"],
        release_receipt_digest=release_receipt_digest,
        schema_digest=manifest["target_schema_digest"],
    )
    coordinates = _mapping(value["coordinates"], "coordinates")
    if coordinates != expected_coordinates.as_dict():
        raise DatabaseOracleError(
            "database oracle coordinates require the canonical nested record digests"
        )
    return expected_coordinates


def _validate_data_contract(contract: dict[str, Any]) -> None:
    _exact_fields(
        contract,
        {
            "data_contract_id",
            "version",
            "status",
            "purpose",
            "database",
            "entities",
            "invariants",
        },
        "data_contract",
    )
    _identifier(contract["data_contract_id"], "data_contract_id")
    _semver(contract["version"], "data contract version")
    if contract["status"] != "approved_in_selected_future":
        raise DatabaseOracleError(
            "data contract status requires approved_in_selected_future"
        )
    _text(contract["purpose"], "data contract purpose", minimum=20)
    database = _mapping(contract["database"], "data_contract.database")
    _exact_fields(
        database,
        {
            "engine_family",
            "engine_version",
            "collation",
            "database_timezone",
            "settings_digest",
            "migration_history_table",
        },
        "data_contract.database",
    )
    if database["engine_family"] != "postgresql":
        raise DatabaseOracleError("selected-future database engine requires postgresql")
    for field in ("engine_version", "collation", "database_timezone", "migration_history_table"):
        _text(database[field], f"data_contract.database.{field}")
    if database["database_timezone"] != "UTC":
        raise DatabaseOracleError("selected-future database timezone requires UTC")
    _digest(database["settings_digest"], "database settings digest")

    entities = contract["entities"]
    if not isinstance(entities, list) or not entities:
        raise DatabaseOracleError("data contract requires at least one entity")
    entity_ids: set[str] = set()
    for entity_index, entity_value in enumerate(entities):
        entity = _mapping(entity_value, f"entities[{entity_index}]")
        _exact_fields(
            entity,
            {"entity_id", "table_name", "purpose", "fields", "primary_key_field_ids"},
            f"entities[{entity_index}]",
        )
        entity_id = _identifier(entity["entity_id"], f"entities[{entity_index}].entity_id")
        if entity_id in entity_ids:
            raise DatabaseOracleError("data contract entity identities require uniqueness")
        entity_ids.add(entity_id)
        _text(entity["table_name"], f"entities[{entity_index}].table_name")
        _text(entity["purpose"], f"entities[{entity_index}].purpose", minimum=10)
        fields = entity["fields"]
        if not isinstance(fields, list) or not fields:
            raise DatabaseOracleError("data contract entity requires fields")
        field_ids: set[str] = set()
        for field_index, field_value in enumerate(fields):
            field = _mapping(
                field_value,
                f"entities[{entity_index}].fields[{field_index}]",
            )
            required = {
                "field_id",
                "column_name",
                "semantic_type",
                "physical_type",
                "nullable",
            }
            allowed = required | {
                "temporal_semantics",
                "precision",
                "scale",
                "unit",
            }
            _bounded_fields(
                field,
                required,
                allowed,
                f"entities[{entity_index}].fields[{field_index}]",
            )
            field_id = _identifier(
                field["field_id"],
                f"entities[{entity_index}].fields[{field_index}].field_id",
            )
            if field_id in field_ids:
                raise DatabaseOracleError(
                    "data contract field identities require entity-local uniqueness"
                )
            field_ids.add(field_id)
            _text(field["column_name"], "data contract column name")
            if type(field["nullable"]) is not bool:
                raise DatabaseOracleError("data contract nullable requires a boolean")
            semantic_type = _text(
                field["semantic_type"], "data contract semantic type"
            )
            physical_type = _text(
                field["physical_type"], "data contract physical type"
            ).lower()
            native_types = {
                "instant": "timestamptz",
                "civil_date": "date",
                "boolean": "boolean",
                "integer": "bigint",
                "identifier": "uuid",
                "text": "text",
            }
            if semantic_type not in {*native_types, "exact_decimal"}:
                raise DatabaseOracleError(
                    "data contract semantic type requires the released primitive vocabulary"
                )
            expected_physical = native_types.get(semantic_type)
            if expected_physical is not None and physical_type != expected_physical:
                raise DatabaseOracleError(
                    f"PostgreSQL {semantic_type} uses {expected_physical} in the selected future"
                )
            if semantic_type == "instant" and field.get("temporal_semantics") != "absolute_instant":
                raise DatabaseOracleError(
                    "instant field requires absolute_instant temporal semantics"
                )
            if semantic_type == "civil_date" and field.get("temporal_semantics") != "civil_date":
                raise DatabaseOracleError(
                    "civil date field requires civil_date temporal semantics"
                )
            if semantic_type == "exact_decimal":
                precision = field.get("precision")
                scale = field.get("scale")
                if (
                    type(precision) is not int
                    or type(scale) is not int
                    or precision < 1
                    or scale < 0
                    or scale > precision
                ):
                    raise DatabaseOracleError(
                        "exact decimal requires coherent integer precision and scale"
                    )
                if not re.fullmatch(
                    rf"(?:numeric|decimal)\({precision},{scale}\)",
                    physical_type,
                ):
                    raise DatabaseOracleError(
                        "exact decimal physical type requires its declared precision and scale"
                    )
                _text(field.get("unit"), "exact decimal unit")
        primary_keys = entity["primary_key_field_ids"]
        if (
            not isinstance(primary_keys, list)
            or not primary_keys
            or not all(isinstance(item, str) for item in primary_keys)
            or not all(item in field_ids for item in primary_keys)
            or len(primary_keys) != len(set(primary_keys))
        ):
            raise DatabaseOracleError(
                "data contract primary keys require unique entity field identities"
            )
    invariants = contract["invariants"]
    if (
        not isinstance(invariants, list)
        or len(invariants) < 4
        or not all(isinstance(item, str) and item.strip() for item in invariants)
    ):
        raise DatabaseOracleError(
            "data contract requires at least four affirmative database invariants"
        )


def _validate_migration_manifest(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    contract_digest: str,
) -> None:
    _exact_fields(
        manifest,
        {
            "migration_manifest_id",
            "version",
            "data_contract",
            "tool",
            "script_digest",
            "source_schema_digest",
            "target_schema_digest",
            "phases",
            "compatibility_window",
            "recovery",
        },
        "migration_manifest",
    )
    _identifier(manifest["migration_manifest_id"], "migration_manifest_id")
    _semver(manifest["version"], "migration manifest version")
    _coordinate(
        manifest["data_contract"],
        contract["data_contract_id"],
        contract["version"],
        contract_digest,
        "migration_manifest.data_contract",
    )
    tool = _mapping(manifest["tool"], "migration_manifest.tool")
    _exact_fields(tool, {"name", "version", "implementation_digest"}, "migration_manifest.tool")
    _text(tool["name"], "migration tool name")
    _text(tool["version"], "migration tool version")
    _digest(tool["implementation_digest"], "migration tool digest")
    for field in ("script_digest", "source_schema_digest", "target_schema_digest"):
        _digest(manifest[field], f"migration manifest {field}")
    if manifest["source_schema_digest"] == manifest["target_schema_digest"]:
        raise DatabaseOracleError("migration manifest requires a distinct target schema")
    phases = manifest["phases"]
    if not isinstance(phases, list) or len(phases) != len(PHASE_TYPES):
        raise DatabaseOracleError("migration manifest requires five lifecycle phases")
    for index, (phase_value, expected_type) in enumerate(
        zip(phases, PHASE_TYPES), start=1
    ):
        phase = _mapping(phase_value, f"migration phase {index}")
        _exact_fields(
            phase,
            {
                "phase_id",
                "phase_type",
                "sequence",
                "lock_budget_milliseconds",
                "statement_budget_milliseconds",
                "checkpoint_strategy",
            },
            f"migration phase {index}",
        )
        _identifier(phase["phase_id"], f"migration phase {index} identity")
        _positive_integer(phase["sequence"], f"migration phase {index} sequence")
        if phase["phase_type"] != expected_type or phase["sequence"] != index:
            raise DatabaseOracleError(
                "migration manifest phases require expand-through-contract order"
            )
        for field in ("lock_budget_milliseconds", "statement_budget_milliseconds"):
            _positive_integer(phase[field], f"migration phase {index} {field}")
        _text(phase["checkpoint_strategy"], "migration checkpoint strategy")
    compatibility = _mapping(manifest["compatibility_window"], "compatibility_window")
    _exact_fields(
        compatibility,
        {"supported_application_releases", "minimum_observation_seconds"},
        "compatibility_window",
    )
    releases = compatibility["supported_application_releases"]
    if (
        not isinstance(releases, list)
        or len(releases) < 2
        or not all(isinstance(item, str) and item.strip() for item in releases)
        or len(releases) != len(set(releases))
    ):
        raise DatabaseOracleError(
            "compatibility window requires distinct predecessor and target releases"
        )
    _positive_integer(
        compatibility["minimum_observation_seconds"],
        "compatibility observation seconds",
    )
    recovery = _mapping(manifest["recovery"], "migration recovery")
    _exact_fields(
        recovery,
        {"strategy", "rollback_boundary_phase_id", "backup_receipt_id", "restore_receipt_id"},
        "migration recovery",
    )
    if recovery["strategy"] != "roll_forward_preferred":
        raise DatabaseOracleError("migration recovery requires roll_forward_preferred")
    for field in ("rollback_boundary_phase_id", "backup_receipt_id", "restore_receipt_id"):
        _identifier(recovery[field], f"migration recovery {field}")
    if recovery["rollback_boundary_phase_id"] not in {
        phase["phase_id"] for phase in phases
    }:
        raise DatabaseOracleError(
            "migration recovery boundary requires a released manifest phase"
        )


def _validate_migration_receipt(
    receipt: dict[str, Any],
    contract: dict[str, Any],
    contract_digest: str,
    manifest: dict[str, Any],
    manifest_digest: str,
) -> None:
    _exact_fields(
        receipt,
        {
            "migration_receipt_id",
            "evidence_mode",
            "assurance_stage",
            "authority",
            "actual_acceptance_required",
            "outcome",
            "data_contract",
            "migration_manifest",
            "script_digest",
            "source_schema_digest",
            "target_schema_digest",
            "environment",
            "phase_results",
            "reconciliation",
            "recovery",
            "performed_at",
        },
        "migration_receipt",
    )
    _identifier(receipt["migration_receipt_id"], "migration_receipt_id")
    expected = {
        "evidence_mode": "simulated",
        "assurance_stage": "qualified",
        "authority": "simulation_only",
        "actual_acceptance_required": True,
        "outcome": "passed",
    }
    for field, expected_value in expected.items():
        if (
            type(receipt[field]) is not type(expected_value)
            or receipt[field] != expected_value
        ):
            raise DatabaseOracleError(
                f"migration receipt requires {field}={expected_value!r}"
            )
    _coordinate(
        receipt["data_contract"],
        contract["data_contract_id"],
        contract["version"],
        contract_digest,
        "migration_receipt.data_contract",
    )
    _coordinate(
        receipt["migration_manifest"],
        manifest["migration_manifest_id"],
        manifest["version"],
        manifest_digest,
        "migration_receipt.migration_manifest",
    )
    for field in ("script_digest", "source_schema_digest", "target_schema_digest"):
        if receipt[field] != manifest[field]:
            raise DatabaseOracleError(
                f"migration receipt {field} requires the migration manifest value"
            )
    environment = _mapping(receipt["environment"], "migration receipt environment")
    _exact_fields(
        environment,
        {"environment_id", "engine_family", "engine_version", "database_timezone", "settings_digest"},
        "migration receipt environment",
    )
    _identifier(environment["environment_id"], "migration environment identity")
    database = contract["database"]
    for field in ("engine_family", "engine_version", "database_timezone", "settings_digest"):
        if environment[field] != database[field]:
            raise DatabaseOracleError(
                f"migration environment {field} requires the data contract value"
            )
    results = receipt["phase_results"]
    if not isinstance(results, list) or len(results) != len(PHASE_TYPES):
        raise DatabaseOracleError("migration receipt requires every phase result")
    for index, (result_value, plan_phase) in enumerate(
        zip(results, manifest["phases"]),
        start=1,
    ):
        result = _mapping(result_value, f"migration phase result {index}")
        _exact_fields(
            result,
            {"phase_id", "sequence", "outcome", "checkpoint_digest"},
            f"migration phase result {index}",
        )
        _positive_integer(
            result["sequence"], f"migration phase result {index} sequence"
        )
        if (
            result["phase_id"] != plan_phase["phase_id"]
            or result["sequence"] != index
            or result["outcome"] != "passed"
        ):
            raise DatabaseOracleError(
                "migration receipt phase results require plan-ordered passing outcomes"
            )
        _digest(result["checkpoint_digest"], "migration phase checkpoint digest")
    reconciliation = _mapping(receipt["reconciliation"], "migration reconciliation")
    _exact_fields(
        reconciliation,
        {
            "expected_record_count",
            "observed_record_count",
            "expected_checksum",
            "observed_checksum",
            "temporal_invariant_count",
            "temporal_invariant_passed",
            "maximum_lock_held_milliseconds",
        },
        "migration reconciliation",
    )
    for field in (
        "expected_record_count",
        "observed_record_count",
        "temporal_invariant_count",
        "maximum_lock_held_milliseconds",
    ):
        _nonnegative_integer(reconciliation[field], f"migration reconciliation {field}")
    if reconciliation["expected_record_count"] != reconciliation["observed_record_count"]:
        raise DatabaseOracleError("migration reconciliation requires exact record parity")
    for field in ("expected_checksum", "observed_checksum"):
        _digest(reconciliation[field], f"migration reconciliation {field}")
    if reconciliation["expected_checksum"] != reconciliation["observed_checksum"]:
        raise DatabaseOracleError("migration reconciliation requires exact checksum parity")
    if reconciliation["temporal_invariant_passed"] is not True:
        raise DatabaseOracleError("migration reconciliation requires temporal invariant parity")
    maximum_lock_budget = max(
        phase["lock_budget_milliseconds"] for phase in manifest["phases"]
    )
    if reconciliation["maximum_lock_held_milliseconds"] > maximum_lock_budget:
        raise DatabaseOracleError(
            "migration reconciliation lock duration requires the planned budget"
        )
    recovery = _mapping(receipt["recovery"], "migration receipt recovery")
    _exact_fields(
        recovery,
        {"backup_receipt_id", "restore_receipt_id", "rto_seconds", "rpo_seconds", "disposition"},
        "migration receipt recovery",
    )
    if (
        recovery["backup_receipt_id"] != manifest["recovery"]["backup_receipt_id"]
        or recovery["restore_receipt_id"] != manifest["recovery"]["restore_receipt_id"]
    ):
        raise DatabaseOracleError(
            "migration receipt recovery requires the manifest receipt identities"
        )
    for field in ("rto_seconds", "rpo_seconds"):
        _nonnegative_integer(recovery[field], f"migration recovery {field}")
    if recovery["disposition"] != "roll_forward_verified":
        raise DatabaseOracleError(
            "migration receipt recovery requires roll_forward_verified"
        )
    _canonical_utc(receipt["performed_at"], "migration receipt performed_at")


def _validate_release_receipt(
    receipt: dict[str, Any],
    contract: dict[str, Any],
    contract_digest: str,
    manifest: dict[str, Any],
    manifest_digest: str,
    migration_receipt: dict[str, Any],
    migration_receipt_digest: str,
) -> None:
    _exact_fields(
        receipt,
        {
            "release_receipt_id",
            "database_release",
            "release_state",
            "evidence_mode",
            "assurance_stage",
            "authority",
            "actual_acceptance_required",
            "production_authorization_effect",
            "data_contract",
            "migration_manifest",
            "migration_receipt",
            "schema_digest",
            "acceptance_bindings",
            "evidence_bundle_digest",
            "performed_at",
        },
        "release_receipt",
    )
    _identifier(receipt["release_receipt_id"], "release_receipt_id")
    _text(receipt["database_release"], "database release")
    expected = {
        "release_state": "closed_in_simulation",
        "evidence_mode": "simulated",
        "assurance_stage": "qualified",
        "authority": "simulation_only",
        "actual_acceptance_required": True,
        "production_authorization_effect": "none",
    }
    for field, expected_value in expected.items():
        if (
            type(receipt[field]) is not type(expected_value)
            or receipt[field] != expected_value
        ):
            raise DatabaseOracleError(
                f"release receipt requires {field}={expected_value!r}"
            )
    _coordinate(
        receipt["data_contract"],
        contract["data_contract_id"],
        contract["version"],
        contract_digest,
        "release_receipt.data_contract",
    )
    _coordinate(
        receipt["migration_manifest"],
        manifest["migration_manifest_id"],
        manifest["version"],
        manifest_digest,
        "release_receipt.migration_manifest",
    )
    migration_coordinate = _mapping(
        receipt["migration_receipt"],
        "release_receipt.migration_receipt",
    )
    _exact_fields(
        migration_coordinate,
        {"migration_receipt_id", "digest"},
        "release_receipt.migration_receipt",
    )
    if migration_coordinate != {
        "migration_receipt_id": migration_receipt["migration_receipt_id"],
        "digest": migration_receipt_digest,
    }:
        raise DatabaseOracleError(
            "release receipt migration coordinate requires the canonical migration receipt"
        )
    if receipt["schema_digest"] != manifest["target_schema_digest"]:
        raise DatabaseOracleError(
            "release receipt schema digest requires the migration target schema"
        )
    bindings = receipt["acceptance_bindings"]
    if not isinstance(bindings, list):
        raise DatabaseOracleError("release receipt acceptance bindings require an array")
    acceptance_types = []
    for index, binding_value in enumerate(bindings):
        binding = _mapping(binding_value, f"acceptance binding {index}")
        _exact_fields(
            binding,
            {"acceptance_id", "acceptance_type", "status", "evidence_mode", "decision_digest"},
            f"acceptance binding {index}",
        )
        _identifier(binding["acceptance_id"], "acceptance identity")
        acceptance_types.append(
            _text(binding["acceptance_type"], "acceptance type")
        )
        if binding["status"] != "projected" or binding["evidence_mode"] != "simulated":
            raise DatabaseOracleError(
                "selected-future acceptance remains projected with simulated evidence"
            )
        _digest(binding["decision_digest"], "acceptance decision digest")
    if set(acceptance_types) != ACCEPTANCE_TYPES or len(acceptance_types) != len(
        set(acceptance_types)
    ):
        raise DatabaseOracleError(
            "release receipt requires distinct Scientific, Quality, Regulatory, Security, and Operations acceptance"
        )
    _digest(receipt["evidence_bundle_digest"], "release evidence bundle digest")
    expected_bundle_digest = digest(
        {
            "data_contract_digest": contract_digest,
            "migration_manifest_digest": manifest_digest,
            "migration_receipt_digest": migration_receipt_digest,
            "schema_digest": manifest["target_schema_digest"],
            "acceptance_decision_digests": [
                item["decision_digest"] for item in bindings
            ],
        }
    )
    if receipt["evidence_bundle_digest"] != expected_bundle_digest:
        raise DatabaseOracleError(
            "release evidence bundle digest requires every database release coordinate"
        )
    _canonical_utc(receipt["performed_at"], "release receipt performed_at")


def _coordinate(
    value: Any,
    expected_id: str,
    expected_version: str,
    expected_digest: str,
    label: str,
) -> None:
    coordinate = _mapping(value, label)
    _exact_fields(coordinate, {"id", "version", "digest"}, label)
    if coordinate != {
        "id": expected_id,
        "version": expected_version,
        "digest": expected_digest,
    }:
        raise DatabaseOracleError(f"{label} requires the canonical coordinate")


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DatabaseOracleError(f"{label} requires an object")
    return value


def _exact_fields(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise DatabaseOracleError(f"{label} requires the released field set")


def _bounded_fields(
    value: dict[str, Any],
    required: set[str],
    allowed: set[str],
    label: str,
) -> None:
    if not required.issubset(value) or not set(value).issubset(allowed):
        raise DatabaseOracleError(f"{label} requires the released field set")


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise DatabaseOracleError(f"{label} requires an uppercase governed identity")
    return value


def _semver(value: Any, label: str) -> str:
    if not isinstance(value, str) or SEMVER_PATTERN.fullmatch(value) is None:
        raise DatabaseOracleError(f"{label} requires semantic versioning")
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise DatabaseOracleError(f"{label} requires a canonical sha256 digest")
    return value


def _text(value: Any, label: str, *, minimum: int = 1) -> str:
    if not isinstance(value, str) or len(value.strip()) < minimum:
        raise DatabaseOracleError(f"{label} requires bounded text")
    return value


def _nonnegative_integer(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise DatabaseOracleError(f"{label} requires a nonnegative integer")
    return value


def _positive_integer(value: Any, label: str) -> int:
    if type(value) is not int or value < 1:
        raise DatabaseOracleError(f"{label} requires a positive integer")
    return value


def _canonical_utc(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise DatabaseOracleError(f"{label} requires canonical UTC interchange")
    try:
        instant = parse_instant(value, label=label)
    except ValueError as error:
        raise DatabaseOracleError(str(error)) from error
    if instant.isoformat(timespec="milliseconds").replace("+00:00", "Z") != value:
        raise DatabaseOracleError(f"{label} requires millisecond canonical UTC interchange")
    return value
