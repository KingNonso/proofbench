"""C01 from case file to decision, with no model in the loop.

This is the claim the product makes, end to end: a migration that passes the
check a reviewer would run is blocked by evidence from the deployment timeline,
and the blast radius names rows that were actually observed.
"""

import os

import pytest

from proofbench.decision.policy import decide
from proofbench.domain.decision import ExternalState
from proofbench.domain.evidence import WorldStatus
from proofbench.domain.trace import EventType
from proofbench.sandbox import docker
from proofbench.tracing.validator import validate_trace
from proofbench.tracing.writer import TraceWriter
from proofbench.worlds.runner import (
    prepare_world_database,
    run_required_worlds,
    run_visible_tests,
)

pytestmark = [pytest.mark.e2e, pytest.mark.integration]

SOUTHGATE = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def no_provider_keys(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "PROOFBENCH_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    return


def test_c01_reaches_blocked_with_confirmed_evidence(
    sandbox, loaded_c01, tmp_path, no_provider_keys
):
    assert not any(key.endswith("_API_KEY") for key in os.environ)

    trace_path = tmp_path / "trajectory.jsonl"
    writer = TraceWriter(trace_path, "e2e-c01", secrets=sandbox.credentials.secrets())
    writer.emit(
        EventType.RUN_STARTED,
        actor="test",
        stage="ingest",
        summary=f"case {loaded_c01.case.case_id}",
        payload={
            "inputs_digest": loaded_c01.inputs_digest,
            # Deliberately included: the trace must survive being handed a secret.
            "dsn": sandbox.dsn("postgres"),
        },
    )

    database = prepare_world_database(sandbox, loaded_c01, "rls")

    visible = run_visible_tests(sandbox, database, loaded_c01)
    assert [check.status.value for check in visible] == ["passed"]

    results = run_required_worlds(
        sandbox, loaded_c01, run_id="e2e-c01", trace=writer, database_by_world={"rls": database}
    )
    assert results[0].status is WorldStatus.FAILED

    decision = decide(results)
    writer.emit(
        EventType.DECISION_RECORDED,
        actor="decision",
        stage="decide",
        summary=decision.external_state.value,
        payload={"state": decision.external_state.value},
    )
    writer.emit(EventType.RUN_COMPLETED, actor="test", stage="complete", summary="done")
    root_hash = writer.close()

    assert decision.external_state is ExternalState.BLOCKED
    assert decision.evidence_complete
    assert "INV-RLS-001" in " ".join(decision.reasons)
    assert decision.decisive_check_ids

    confirmed = decision.confirmed
    assert confirmed, "a blocked decision must name what it confirmed"
    leak = next(item for item in confirmed if item.affected_tenant == SOUTHGATE)
    assert leak.role == "aidledger_app"
    assert leak.rows_affected == 2
    assert leak.row_keys
    assert leak.check_ids
    assert decision.possible == []

    validation = validate_trace(trace_path)
    assert validation.valid, validation.problems
    assert validation.root_hash == root_hash
    assert validation.events >= 5

    raw = trace_path.read_text()
    for secret in sandbox.credentials.secrets():
        assert secret not in raw


def test_no_labelled_container_or_network_leaks(sandbox):
    # The session sandbox is deliberately still up; nothing from any other run
    # should be.
    assert docker.list_labelled("container", "e2e-c01") == []
    assert docker.list_labelled("network", "e2e-c01") == []
