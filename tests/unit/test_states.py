"""The product's public vocabulary.

These strings appear in every committed artifact. Renaming one silently would
invalidate every golden bundle, so the wire values are pinned here rather than
inferred from the enum.
"""

from proofbench.domain.decision import ExternalState, ProviderMode, RunKind


def test_external_states_are_exactly_the_four_prd_states():
    assert {state.value for state in ExternalState} == {
        "READY_FOR_REVIEW",
        "BLOCKED",
        "DOMAIN_RULING_REQUIRED",
        "EVIDENCE_INCOMPLETE",
    }


def test_external_state_serialises_as_its_wire_string():
    assert f"{ExternalState.BLOCKED}" == "BLOCKED"
    assert ExternalState("DOMAIN_RULING_REQUIRED") is ExternalState.DOMAIN_RULING_REQUIRED


def test_run_kind_and_provider_mode_are_separate_concerns():
    # A deterministic migration_court run makes no model call at all; conflating
    # the two would make that unrepresentable.
    assert {kind.value for kind in RunKind} == {"baseline", "migration_court", "replay"}
    assert {mode.value for mode in ProviderMode} == {"live", "fake", "recorded", "none"}
