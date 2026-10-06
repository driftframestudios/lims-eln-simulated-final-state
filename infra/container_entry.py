"""Run the existing selected-future generator with its declared fixtures."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from container_runtime import run as run_job
from lims_eln_sim.simulation import run, write_bundle
from lims_eln_sim.safety import synthetic_redaction_key


def load(path): return json.loads(Path(path).read_bytes())

def produce(output):
    fixture=load("fixtures/golden-specimen.json")
    bundle=run(fixture,intended_use_profile=load("specification/intended-use-and-applicability-profile.json"),migration_corpus=load("fixtures/representative-migration-corpus.json"),database_oracle=load("database/final-state-database-oracle-v1.json"),redaction_key=synthetic_redaction_key(fixture.get("redaction_key_id","")))
    write_bundle(bundle,output)

if __name__=="__main__": run_job(produce)
