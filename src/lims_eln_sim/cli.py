from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .contract_v1 import strict_json_loads
from .safety import synthetic_redaction_key
from .simulation import run, write_bundle


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Run the independent LIMS/ELN final-state forecast")
    command.add_argument("--fixture", type=Path, required=True)
    command.add_argument("--intended-use-profile", type=Path, required=True)
    command.add_argument("--migration-corpus", type=Path, required=True)
    command.add_argument("--database-oracle", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    return command


def main() -> None:
    args = parser().parse_args()
    fixture = load_json(args.fixture)
    intended_use_profile = load_json(args.intended_use_profile)
    migration_corpus = load_json(args.migration_corpus)
    database_oracle = load_json(args.database_oracle)
    bundle = run(
        fixture,
        intended_use_profile=intended_use_profile,
        migration_corpus=migration_corpus,
        database_oracle=database_oracle,
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
    value = strict_json_loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("JSON document requires an object at the repository boundary")
    return value


if __name__ == "__main__":
    main()
