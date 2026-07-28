from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .open_receipts import RECEIPT_FAMILIES
from .safety import synthetic_redaction_key
from .simulation import run


ROOT = Path(__file__).resolve().parents[2]


def verify_family(family: str) -> dict:
    """Regenerate one family and return its verified simulated receipt."""

    if family not in RECEIPT_FAMILIES:
        raise ValueError(f"receipt family {family!r} is outside the released set")
    fixture = json.loads(
        (ROOT / "fixtures" / "golden-specimen.json").read_text(encoding="utf-8")
    )
    migration_corpus = json.loads(
        (ROOT / "fixtures" / "representative-migration-corpus.json").read_text(
            encoding="utf-8"
        )
    )
    intended_use_profile = json.loads(
        (
            ROOT
            / "specification"
            / "intended-use-and-applicability-profile.json"
        ).read_text(encoding="utf-8")
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
