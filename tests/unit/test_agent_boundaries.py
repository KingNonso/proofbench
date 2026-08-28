"""What the agents cannot do.

Splitting one agent into three buys nothing if they all share one capability set,
so these tests are about the walls rather than the work: the Contract Analyst
cannot execute SQL, the Test Designer cannot express a command, and the
Remediation Engineer cannot reach a policy or a trace.
"""

import json

import pytest
from pydantic import ValidationError

from proofbench.agents.remediation_engineer import run_remediation_engineer
from proofbench.agents.runner import extract_json, invoke_agent
from proofbench.domain.contract import MigrationContract, RemediationPlan, WorldPlan
from proofbench.errors import EvidenceIncompleteError
from proofbench.providers.fake import FakeProvider
from proofbench.tools.router import CAPABILITIES, ToolContext, ToolName, ToolRequest, ToolRouter
from tests.unit import factories


@pytest.fixture
def router(benchmark_root, tmp_path):
    return ToolRouter(ToolContext(benchmark_root=benchmark_root, run_dir=tmp_path))


# -- capability walls -------------------------------------------------------


def test_contract_analyst_cannot_execute_sql_or_write():
    permitted = CAPABILITIES["contract_analyst"]
    assert ToolName.READ_FILE in permitted
    # There is no execute or write tool at all, for any actor.
    every_tool = set().union(*CAPABILITIES.values())
    assert not {name for name in every_tool if "exec" in name or "write" in name}


def test_test_designer_cannot_read_arbitrary_files(router):
    result = router.call(
        ToolRequest(
            actor="test_designer",
            tool=ToolName.READ_FILE,
            arguments={"path": "cases/C01/candidate.sql"},
        )
    )
    assert not result.allowed
    assert "may not call" in (result.denial_reason or "")


def test_remediation_engineer_cannot_search_the_tree(router):
    result = router.call(
        ToolRequest(
            actor="remediation_engineer",
            tool=ToolName.SEARCH_TREE,
            arguments={"pattern": "POLICY"},
        )
    )
    assert not result.allowed


def test_an_unknown_actor_is_refused(router):
    result = router.call(ToolRequest(actor="rogue", tool=ToolName.READ_FILE))
    assert not result.allowed
    assert "unknown actor" in (result.denial_reason or "")


def test_no_agent_can_read_the_oracle(router):
    for actor in CAPABILITIES:
        result = router.call(
            ToolRequest(
                actor=actor,
                tool=ToolName.READ_FILE,
                arguments={"path": "evaluator_only/C01.oracle.yaml"},
            )
        )
        assert not result.allowed


def test_path_traversal_through_a_tool_is_refused(router):
    result = router.call(
        ToolRequest(
            actor="contract_analyst",
            tool=ToolName.READ_FILE,
            arguments={"path": "../../etc/passwd"},
        )
    )
    assert not result.allowed


def test_search_skips_the_oracle_directory(router):
    result = router.call(
        ToolRequest(
            actor="contract_analyst", tool=ToolName.SEARCH_TREE, arguments={"pattern": "expected"}
        )
    )
    assert result.allowed
    assert "evaluator_only" not in result.output


def test_a_denial_is_recorded_rather_than_returned_as_empty(router):
    result = router.call(ToolRequest(actor="test_designer", tool=ToolName.READ_FILE))
    # "denied" and "found nothing" must not look the same to a caller.
    assert result.output == ""
    assert result.allowed is False
    assert result.denial_reason
    assert router.calls[-1].denial_reason


def test_tool_output_is_capped(benchmark_root, tmp_path, monkeypatch):
    monkeypatch.setattr("proofbench.tools.router.MAX_OUTPUT_CHARS", 40)
    router = ToolRouter(ToolContext(benchmark_root=benchmark_root, run_dir=tmp_path))
    result = router.call(
        ToolRequest(
            actor="contract_analyst",
            tool=ToolName.READ_FILE,
            arguments={"path": "cases/C01/candidate.sql"},
        )
    )
    assert result.truncated
    assert len(result.output) == 40


def test_router_redacts_secrets_from_tool_output(benchmark_root, tmp_path):
    router = ToolRouter(
        ToolContext(benchmark_root=benchmark_root, run_dir=tmp_path, schema_summary="pw=hunter2"),
        secrets=("hunter2",),
    )
    result = router.call(ToolRequest(actor="contract_analyst", tool=ToolName.INSPECT_SCHEMA))
    assert "hunter2" not in result.output


# -- schema walls -----------------------------------------------------------


def test_a_world_plan_cannot_express_a_command():
    # Parameters are simple values. There is no field a shell string could
    # occupy, so a selection cannot become execution.
    with pytest.raises(ValidationError):
        WorldPlan.model_validate(
            {
                "schema_version": "1.0",
                "case_id": "C01",
                "rationale": "r",
                "entries": [
                    {
                        "world": "rls",
                        "threatened_invariants": ["INV-RLS-001"],
                        "rationale": "r",
                        "parameters": {"cmd": ["docker", "run", "--privileged"]},
                        "expected_evidence": "e",
                        "timeout_seconds": 30,
                    }
                ],
            }
        )


def test_a_contract_has_no_field_for_a_verdict():
    assert "decision" not in MigrationContract.model_fields
    assert "external_state" not in MigrationContract.model_fields
    assert "safe" not in MigrationContract.model_fields


def test_a_remediation_plan_has_no_field_claiming_success():
    assert "verified" not in RemediationPlan.model_fields
    assert "passed" not in RemediationPlan.model_fields


def test_an_invented_world_is_rejected():
    with pytest.raises(ValidationError):
        WorldPlan.model_validate(
            {
                "schema_version": "1.0",
                "case_id": "C01",
                "rationale": "r",
                "entries": [
                    {
                        "world": "telepathy",
                        "threatened_invariants": ["INV-RLS-001"],
                        "rationale": "r",
                        "expected_evidence": "e",
                        "timeout_seconds": 30,
                    }
                ],
            }
        )


# -- schema repair ----------------------------------------------------------


def valid_contract_json():
    return json.dumps(
        {
            "schema_version": "1.0",
            "case_id": "C01",
            "summary": "s",
            "invariants": [
                {
                    "id": "INV-RLS-001",
                    "description": "d",
                    "blocking_class": "blocking",
                    "executable_check": "c",
                }
            ],
        }
    )


def invoke(provider):
    return invoke_agent(
        provider=provider,
        model_cls=MigrationContract,
        agent="contract_analyst",
        prompt_version="v1",
        system_prompt="sys",
        user_prompt="user",
        max_output_tokens=100,
    )


def test_valid_output_needs_no_repair():
    provider = FakeProvider({"contract_analyst": [valid_contract_json()]})
    assert invoke(provider).case_id == "C01"
    assert len(provider.calls) == 1


def test_invalid_output_gets_exactly_one_repair_attempt():
    provider = FakeProvider({"contract_analyst": ["not json at all", valid_contract_json()]})
    assert invoke(provider).case_id == "C01"
    assert len(provider.calls) == 2
    # The repair carries the validation errors back, not just "try again".
    assert "did not validate" in provider.calls[1].messages[-1].content


def test_a_second_invalid_output_ends_the_stage():
    # Retrying until something parses selects for parseability, not correctness.
    provider = FakeProvider({"contract_analyst": ["nope", "still nope"]})
    with pytest.raises(EvidenceIncompleteError, match="failed schema validation twice"):
        invoke(provider)
    assert len(provider.calls) == 2


def test_both_attempts_are_preserved_in_the_error():
    provider = FakeProvider({"contract_analyst": ["first bad", "second bad"]})
    with pytest.raises(EvidenceIncompleteError) as caught:
        invoke(provider)
    assert caught.value.detail["attempt_1"] == "first bad"
    assert caught.value.detail["attempt_2"] == "second bad"


def test_an_exhausted_provider_is_evidence_incomplete():
    with pytest.raises(EvidenceIncompleteError, match="no response left"):
        invoke(FakeProvider({}))


@pytest.mark.parametrize(
    "text",
    ['```json\n{"a": 1}\n```', 'prose before {"a": 1} prose after', '{"a": 1}'],
)
def test_json_is_extracted_from_padded_replies(text):
    assert json.loads(extract_json(text)) == {"a": 1}


# -- remediation walls ------------------------------------------------------


def remediation_json(**overrides):
    payload = {
        "schema_version": "1.0",
        "case_id": "C01",
        "addresses_invariants": ["INV-RLS-001"],
        "rationale": "r",
        "corrected_sql": "BEGIN; COMMIT;",
        "regression_check": "c",
    }
    payload.update(overrides)
    return json.dumps(payload)


def remediate(router, loaded_c01, text):
    return run_remediation_engineer(
        provider=FakeProvider({"remediation_engineer": [text]}),
        router=router,
        loaded=loaded_c01,
        contract=MigrationContract.model_validate(json.loads(valid_contract_json())),
        world_results=[factories.blocked_world()],
    )


def test_a_correction_touching_a_policy_file_is_refused(router, loaded_c01, tmp_path):
    (tmp_path / "checks.json").write_text("{}")
    with pytest.raises(EvidenceIncompleteError, match="may not touch"):
        remediate(router, loaded_c01, remediation_json(corrected_sql="-- edit policy.yaml\nBEGIN;"))


def test_a_correction_disabling_the_control_is_refused(router, loaded_c01, tmp_path):
    (tmp_path / "checks.json").write_text("{}")
    with pytest.raises(EvidenceIncompleteError, match="weakens the control"):
        remediate(
            router,
            loaded_c01,
            remediation_json(corrected_sql="ALTER TABLE payments DISABLE ROW LEVEL SECURITY;"),
        )


def test_a_correction_addressing_nothing_that_failed_is_refused(router, loaded_c01, tmp_path):
    (tmp_path / "checks.json").write_text("{}")
    with pytest.raises(EvidenceIncompleteError, match="does not claim to address"):
        remediate(router, loaded_c01, remediation_json(addresses_invariants=["INV-MONEY-001"]))


def test_remediation_without_a_blocking_finding_is_refused(router, loaded_c01, tmp_path):
    (tmp_path / "checks.json").write_text("{}")
    with pytest.raises(EvidenceIncompleteError, match="no blocking finding"):
        run_remediation_engineer(
            provider=FakeProvider({"remediation_engineer": [remediation_json()]}),
            router=router,
            loaded=loaded_c01,
            contract=MigrationContract.model_validate(json.loads(valid_contract_json())),
            world_results=[factories.world_result()],
        )
