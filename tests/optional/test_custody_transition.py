"""Exercise custody admission from an accessioned synthetic specimen."""

import pytest

from lims_eln_sim.domain import DomainRuleError, Specimen


@pytest.mark.parametrize(
    ("target", "detail", "reason"),
    [
        pytest.param("released", {}, "requires a released rule", id="skipped-custody"),
        pytest.param("in_custody", {"location": "  "}, "concrete location", id="blank-location"),
    ],
)
def test_rejected_transition_retains_accessioned_specimen(target, detail, reason):
    specimen = Specimen("SPM-SYN-001", "TENANT-SYN-001", "source-sim")
    actor = "simulated-operator"
    specimen.transition("accessioned", actor, {}, "2028-06-30T14:00:00Z")
    before = specimen.view()

    with pytest.raises(DomainRuleError, match=reason):
        specimen.transition(target, actor, detail, "2028-06-30T14:00:01Z")

    assert specimen.view() == before
