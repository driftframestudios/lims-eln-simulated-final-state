"""Run the native selected-future generator and preserve its artifact contract."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from container_runtime import run as run_job
from lims_eln_sim.artifact_boundary import artifact_inventory
from lims_eln_sim.cli import load_json as native_load
from lims_eln_sim.safety import synthetic_redaction_key
from lims_eln_sim.simulation import run, write_bundle


def load(path: str | Path) -> dict:
    return native_load(Path(path))


def produce(output: Path) -> None:
    fixture = load(ROOT / "fixtures/golden-specimen.json")
    bundle = run(
        fixture,
        intended_use_profile=load(ROOT / "specification/intended-use-and-applicability-profile.json"),
        migration_corpus=load(ROOT / "fixtures/representative-migration-corpus.json"),
        database_oracle=load(ROOT / "database/final-state-database-oracle-v1.json"),
        redaction_key=synthetic_redaction_key(fixture.get("redaction_key_id", "")),
    )
    write_bundle(bundle, output)


if __name__ == "__main__":
    run_job(produce, validate=artifact_inventory)
