#!/usr/bin/env python3
"""Verify the observed Simulation release against its signed Git coordinate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lims_eln_sim.cli import load_json  # noqa: E402
from lims_eln_sim.release_coordinate import (  # noqa: E402
    EXPECTED_SIGNING_FINGERPRINT,
    ReleaseCoordinateError,
    verify_release_coordinate,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=ROOT)
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path("receipts/promotion-receipt.json"),
    )
    parser.add_argument(
        "--expected-signing-fingerprint",
        default=EXPECTED_SIGNING_FINGERPRINT,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repository = args.repository.resolve()
    receipt_path = (
        args.receipt
        if args.receipt.is_absolute()
        else repository / args.receipt
    )
    try:
        receipt = load_json(receipt_path)
        verify_release_coordinate(
            repository,
            receipt,
            expected_signing_fingerprint=args.expected_signing_fingerprint,
        )
    except (OSError, ValueError, ReleaseCoordinateError) as error:
        print(
            f"Release-coordinate verification requires attention: {error}",
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {"status": "passed", "tag": receipt["target_release"]},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
