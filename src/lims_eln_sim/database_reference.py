from __future__ import annotations

from typing import Any


class DatabaseReferenceError(ValueError):
    """The comparison reference omits a required database design coordinate."""


def inspect_database_reference(document: dict[str, Any]) -> dict[str, Any]:
    """Return vendor-comparison coordinates from a database design reference.

    The comparison focuses on data representation and the selected migration
    tool. Runtime and organizational systems retain their existing functions.
    """

    contract = _mapping(document.get("data_contract"), "data_contract")
    database = _mapping(contract.get("database"), "data_contract.database")
    if database.get("engine_family") != "postgresql":
        raise DatabaseReferenceError("database reference requires PostgreSQL")

    entities = contract.get("entities")
    if not isinstance(entities, list) or not entities:
        raise DatabaseReferenceError("database reference requires entities")
    entity_map = {
        entity.get("entity_id"): entity
        for entity in entities
        if isinstance(entity, dict)
    }
    required_entities = {
        "ENTITY-TENANT",
        "ENTITY-ASSAY-SPECIFICATION",
        "ENTITY-SPECIMEN",
        "ENTITY-RESULT-OBSERVATION",
    }
    if not required_entities.issubset(entity_map):
        raise DatabaseReferenceError(
            "database reference requires tenant, assay, specimen, and result entities"
        )

    for entity in entities:
        if not isinstance(entity, dict) or not entity.get("tenant_scoped"):
            continue
        primary_key = entity.get("primary_key_field_ids")
        if not isinstance(primary_key, list) or primary_key[:1] != ["TENANT-ID"]:
            raise DatabaseReferenceError(
                "tenant-scoped primary keys require leading TENANT-ID"
            )
        row_policy = _mapping(
            entity.get("row_level_security"),
            f"{entity.get('entity_id')}.row_level_security",
        )
        if row_policy.get("enabled") is not True or row_policy.get("forced") is not True:
            raise DatabaseReferenceError(
                "tenant-scoped entities require enabled and forced row-level security"
            )

    specimen_fields = _field_types(entity_map["ENTITY-SPECIMEN"])
    result_fields = _field_types(entity_map["ENTITY-RESULT-OBSERVATION"])
    expected = {
        "UPDATED-AT": (specimen_fields, "timestamptz"),
        "IS-RELEASED": (specimen_fields, "boolean"),
        "RAW-VALUE": (result_fields, "numeric(38,12)"),
        "CANONICAL-VALUE": (result_fields, "numeric(38,12)"),
        "CONTENT-DIGEST": (result_fields, "bytea"),
        "OBSERVED-AT": (result_fields, "timestamptz"),
    }
    for field_id, (fields, physical_type) in expected.items():
        if fields.get(field_id) != physical_type:
            raise DatabaseReferenceError(
                f"{field_id} requires physical type {physical_type}"
            )

    manifest = _mapping(document.get("migration_manifest"), "migration_manifest")
    tool = _mapping(manifest.get("tool"), "migration_manifest.tool")
    if tool.get("name") != "Flyway Community":
        raise DatabaseReferenceError("schema evolution requires Flyway Community")

    return {
        "engine": database["engine_family"],
        "supported_major_versions": database.get("supported_major_versions", []),
        "migration_tool": tool["name"],
        "entity_count": len(entities),
        "tenant_isolation": "tenant-leading keys and forced row-level security",
        "scientific_quantity_type": result_fields["CANONICAL-VALUE"],
        "event_delivery_pattern": "thin transactional outbox evaluated separately",
    }


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DatabaseReferenceError(f"{label} requires an object")
    return value


def _field_types(entity: dict[str, Any]) -> dict[str, str]:
    fields = entity.get("fields")
    if not isinstance(fields, list):
        raise DatabaseReferenceError(f"{entity.get('entity_id')} requires fields")
    return {
        field["field_id"]: field["physical_type"]
        for field in fields
        if isinstance(field, dict)
        and isinstance(field.get("field_id"), str)
        and isinstance(field.get("physical_type"), str)
    }
