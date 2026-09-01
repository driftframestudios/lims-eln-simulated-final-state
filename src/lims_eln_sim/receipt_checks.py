from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .contract_v1 import ContractBoundaryError, strict_json_loads
from .open_receipts import RECEIPT_FAMILIES
from .safety import synthetic_redaction_key
from .simulation import run


ROOT = Path(__file__).resolve().parents[2]


def verify_family(family: str) -> dict:
    """Regenerate one family and return its verified simulated receipt."""

    if family not in RECEIPT_FAMILIES:
        raise ValueError(f"receipt family {family!r} is outside the released set")
    fixture = _load_repository_object(
        ROOT / "fixtures" / "golden-specimen.json"
    )
    migration_corpus = _load_repository_object(
        ROOT / "fixtures" / "representative-migration-corpus.json"
    )
    intended_use_profile = _load_repository_object(
        ROOT
        / "specification"
        / "intended-use-and-applicability-profile.json"
    )
    result = run(
        fixture,
        intended_use_profile=intended_use_profile,
        migration_corpus=migration_corpus,
        redaction_key=synthetic_redaction_key(fixture["redaction_key_id"]),
    )
    receipt = next(
        item for item in result["receipts"] if item["receipt_family"] == family
    )
    if (
        receipt["outcome"] != "passed"
        or receipt["closure_status"] != "closed_in_simulation"
    ):
        raise ValueError(f"receipt family {family!r} requires a passing closure")
    return receipt


def _load_repository_object(path: Path) -> dict[str, Any]:
    value = strict_json_loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ContractBoundaryError(
            f"repository input {path.name!r} requires one JSON object"
        )
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate one selected-future receipt family."
    )
    parser.add_argument("family", choices=RECEIPT_FAMILIES)
    args = parser.parse_args(argv)
    receipt = verify_family(args.family)
    print(
        json.dumps(
            {
                "receipt_family": receipt["receipt_family"],
                "closure_digest": receipt["closure_digest"],
                "outcome": receipt["outcome"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
