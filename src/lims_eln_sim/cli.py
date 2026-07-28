from __future__ import annotations

import argparse
import json
from pathlib import Path

from .simulation import run, write_bundle


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Run the independent LIMS/ELN final-state forecast")
    command.add_argument("--fixture", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    return command


def main() -> None:
    args = parser().parse_args()
    fixture = json.loads(args.fixture.read_text())
    bundle = run(fixture)
    write_bundle(bundle, args.output)
    print(json.dumps({"simulation_id": bundle["simulation_id"], "content_digest": bundle["content_digest"]}))


if __name__ == "__main__":
    main()

