from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .safety import synthetic_redaction_key
from .simulation import run, write_bundle


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Run the independent LIMS/ELN final-state forecast")
    command.add_argument("--fixture", type=Path, required=True)
    command.add_argument("--intended-use-profile", type=Path, required=True)
    command.add_argument("--migration-corpus", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    return command


def main() -> None:
    args = parser().parse_args()
    fixture = load_json(args.fixture)
    intended_use_profile = load_json(args.intended_use_profile)
    migration_corpus = load_json(args.migration_corpus)
    bundle = run(
        fixture,
        intended_use_profile=intended_use_profile,
        migration_corpus=migration_corpus,
        redaction_key=synthetic_redaction_key(fixture.get("redaction_key_id", "")),
    )
    write_bundle(bundle, args.output)
    print(
        json.dumps(
            {"simulation_id": bundle["simulation_id"], "content_digest": bundle["content_digest"]},
            allow_nan=False,
        )
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_nonfinite,
        object_pairs_hook=_unique_object,
    )
    if not isinstance(value, dict):
        raise ValueError("JSON document requires an object at the repository boundary")
    return value


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"JSON numeric value {value} requires a finite representation")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON object key {key!r} requires a single definition")
        result[key] = value
    return result


if __name__ == "__main__":
    main()
