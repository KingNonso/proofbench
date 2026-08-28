"""The decision policy is the product's whole claim: code decides, not prose."""

import pytest

from proofbench.decision.policy import decide
from proofbench.domain.decision import ExternalState
from proofbench.domain.evidence import WorldStatus
from tests.unit import factories


def test_clean_evidence_is_ready_for_review():
    decision = decide([factories.world_result()])
    assert decision.external_state is ExternalState.READY_FOR_REVIEW
    assert decision.evidence_complete
    # Not an approval. The required action must say so.
    assert "not an automatic approval" in decision.required_action


def test_blocking_finding_blocks():
    decision = decide([factories.blocked_world()])
    assert decision.external_state is ExternalState.BLOCKED
    assert "rls:app-select-other" in decision.decisive_check_ids
    assert decision.confirmed and decision.confirmed[0].invariant_id == "INV-RLS-001"


def test_authority_question_escalates_when_evidence_is_clean():
    decision = decide([factories.world_result()], authority_questions=["is it USD?"])
    assert decision.external_state is ExternalState.DOMAIN_RULING_REQUIRED


def test_evidence_failure_outranks_a_blocking_finding():
    # If the run could not produce trustworthy evidence, its blocking findings
    # are not trustworthy either. Reporting BLOCKED would claim more than the
    # run knows.
    decision = decide([factories.blocked_world()], evidence_failures=[factories.failure()])
    assert decision.external_state is ExternalState.EVIDENCE_INCOMPLETE
    assert not decision.evidence_complete


def test_blocking_finding_outranks_an_authority_question():
    decision = decide([factories.blocked_world()], authority_questions=["is it USD?"])
    assert decision.external_state is ExternalState.BLOCKED


@pytest.mark.parametrize("status", [WorldStatus.ERROR, WorldStatus.TIMEOUT])
def test_world_error_or_timeout_is_never_a_pass(status):
    decision = decide([factories.world_result(status=status)])
    assert decision.external_state is ExternalState.EVIDENCE_INCOMPLETE


def test_no_worlds_at_all_is_incomplete_not_ready():
    decision = decide([])
    assert decision.external_state is ExternalState.EVIDENCE_INCOMPLETE
    assert "no world produced a result" in decision.reasons


def test_world_carried_failures_are_treated_as_evidence_failures():
    decision = decide([factories.world_result(failures=[factories.failure()])])
    assert decision.external_state is ExternalState.EVIDENCE_INCOMPLETE


def test_non_blocking_finding_does_not_block():
    result = factories.world_result(
        status=WorldStatus.FAILED, findings=[factories.finding(blocking=False)]
    )
    assert decide([result]).external_state is ExternalState.READY_FOR_REVIEW


def test_possible_impact_is_never_populated_from_executed_evidence():
    # confirmed and possible must never merge (PRD-FR-041). possible comes from
    # contract analysis, which does not exist yet, so it is honestly empty.
    decision = decide([factories.blocked_world()])
    assert decision.possible == []


def test_confirmed_requires_an_observation_that_actually_saw_something():
    permitted = factories.observation(permitted_by_policy=True, observed_allowed=True)
    result = factories.world_result(
        status=WorldStatus.FAILED,
        findings=[factories.finding(observations=[permitted])],
    )
    # A role that used access it was entitled to is evidence, not harm.
    assert decide([result]).confirmed == []


def test_a_confirmed_impact_cites_only_the_check_that_observed_it():
    # A blast-radius row citing every check in the finding is a bibliography,
    # not traceable evidence.
    result = factories.world_result(
        status=factories.WorldStatus.FAILED,
        findings=[
            factories.finding(
                check_ids=["rls:a", "rls:b", "rls:c"],
                observations=[factories.observation(probe_id="app-select-other")],
            )
        ],
    )
    confirmed = decide([result]).confirmed
    assert [item.check_ids for item in confirmed] == [["rls:app-select-other"]]


def test_deferred_worlds_pending_a_ruling_are_not_missing_evidence():
    # Worlds are deliberately not run while an authority question is open.
    # Reading that as an evidence failure would hide the human gate behind a
    # generic "something went wrong".
    decision = decide([], authority_questions=["were these payments USD?"])
    assert decision.external_state is ExternalState.DOMAIN_RULING_REQUIRED
    assert decision.evidence_complete


def test_an_evidence_failure_still_outranks_an_authority_question():
    decision = decide(
        [],
        authority_questions=["were these payments USD?"],
        evidence_failures=[factories.failure()],
    )
    assert decision.external_state is ExternalState.EVIDENCE_INCOMPLETE
