"""Process control.

Every path here runs in a genuinely spawned child. Mocking these in the parent
would test nothing, because the whole point is that the child inherits no
administrative connection and can be killed without the parent's cooperation.
"""

import pytest

from proofbench.domain.evidence import WorldStatus
from proofbench.sandbox.worker import run_world
from proofbench.worlds.base import WorldRequest

pytestmark = pytest.mark.integration


def request_for(world: str, *, deadline: int = 30) -> WorldRequest:
    return WorldRequest(
        world=world,
        run_id="worker-test",
        host="127.0.0.1",
        port=1,
        database="unused",
        credentials={},
        targets=[],
        deadline_seconds=deadline,
    )


def test_a_successful_child_returns_its_result():
    result = run_world(request_for("_quick"))
    assert result.status is WorldStatus.PASSED
    assert result.semantic_digest


def test_a_crashing_child_is_an_evidence_error_not_a_pass():
    result = run_world(request_for("_crash"))
    assert result.status is WorldStatus.ERROR
    assert result.failures
    assert "crashed on purpose" in result.failures[0].causes[0]


def test_a_hanging_child_times_out_and_is_terminated():
    result = run_world(request_for("_slow", deadline=2))
    assert result.status is WorldStatus.TIMEOUT
    assert "deadline" in result.failures[0].reason
    # A timeout is never a pass: the decision policy maps it to
    # EVIDENCE_INCOMPLETE rather than letting the run look clean.
    assert result.status is not WorldStatus.PASSED


def test_an_unparseable_child_result_is_an_evidence_error():
    result = run_world(request_for("_bad_payload"))
    assert result.status is WorldStatus.ERROR
    assert "does not validate" in result.failures[0].reason


def test_an_unknown_world_name_is_an_evidence_error():
    result = run_world(request_for("_no_such_world"))
    assert result.status is WorldStatus.ERROR
    assert result.failures


def test_the_child_receives_no_administrative_credential(loaded_c01):
    # The request is the child's entire world. If an admin password is not in
    # it, the child cannot obtain one.
    request = request_for("_quick")
    assert "aidledger_admin" not in request.credentials
    assert request.model_dump_json().count("aidledger_admin") == 0
