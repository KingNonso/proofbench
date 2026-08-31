"""The paired-run plumbing: one provider for both arms, accounted and bounded.

The provider-asymmetry these tests pin down is the bug that reopened gates
R4-R6: a live baseline compared against a fixture-replay final arm. The final
arm must receive the same (metered) provider the baseline does.
"""

from __future__ import annotations

from types import SimpleNamespace

from proofbench.evaluation.records import RunRecord
from proofbench.evaluation.runner import ARM_DIRECT_REVIEW, ARM_FINAL, _account, run_arm
from proofbench.providers.base import ModelResponse, Usage
from proofbench.providers.budget import BudgetLedger, MeteredProvider
from proofbench.providers.fake import FakeProvider


def stub_oracle(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
    return SimpleNamespace(
        case_class=SimpleNamespace(value="unsafe"),
        expected_initial_state=SimpleNamespace(value="BLOCKED"),
    )


def stub_certificate() -> SimpleNamespace:
    return SimpleNamespace(
        first_screen=SimpleNamespace(external_state="BLOCKED", decisive_invariant="inv")
    )


def base_record(**overrides) -> RunRecord:  # noqa: ANN003
    fields: dict[str, object] = {
        "arm": ARM_FINAL,
        "case_id": "C01",
        "repeat": 1,
        "outcome": "BLOCKED",
        "marked_ready": False,
        "evidence_incomplete": False,
        "asked_for_authority": False,
        "duration_ms": 10,
    }
    fields.update(overrides)
    return RunRecord.model_validate(fields)


def test_final_arm_receives_the_same_metered_provider(monkeypatch, benchmark_root, tmp_path):
    import proofbench.evaluation.runner as runner_mod

    seen: dict[str, object] = {}

    def capture_review_case(case_path, *, runs_root, run_id, provider, remediation_attempts):
        seen["provider"] = provider
        run_dir = runs_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "decision.json").write_bytes(b"{}")
        return stub_certificate(), run_dir

    monkeypatch.setattr(runner_mod, "review_case", capture_review_case)
    monkeypatch.setattr(runner_mod, "read_oracle", stub_oracle)
    provider = FakeProvider({})

    records = run_arm(
        ARM_FINAL,
        benchmark_root=benchmark_root,
        runs_root=tmp_path,
        case_ids=["C01"],
        provider=provider,
    )

    assert isinstance(seen["provider"], MeteredProvider)
    assert seen["provider"].name == "fake"
    assert records[0].provider == "fake"


def test_final_arm_without_a_provider_stays_on_fixtures(monkeypatch, benchmark_root, tmp_path):
    import json

    import proofbench.evaluation.runner as runner_mod

    seen: dict[str, object] = {}

    def capture_review_case(case_path, *, runs_root, run_id, provider, remediation_attempts):
        seen["provider"] = provider
        run_dir = runs_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "decision.json").write_bytes(b"{}")
        (run_dir / "run.json").write_text(json.dumps({"provider_mode": "fake"}))
        return stub_certificate(), run_dir

    monkeypatch.setattr(runner_mod, "review_case", capture_review_case)
    monkeypatch.setattr(runner_mod, "read_oracle", stub_oracle)

    records = run_arm(
        ARM_FINAL,
        benchmark_root=benchmark_root,
        runs_root=tmp_path,
        case_ids=["C01"],
        provider=None,
    )

    assert seen["provider"] is None
    assert records[0].provider == "fake"  # read from the run's own record


def test_direct_review_arm_is_metered_too(monkeypatch, benchmark_root, tmp_path):
    import proofbench.evaluation.runner as runner_mod
    from proofbench.evaluation.baseline import BaselineDecision

    seen: dict[str, object] = {}

    def capture_review_by_agent(loaded, *, provider, candidate_sql):
        seen["provider"] = provider
        return BaselineDecision(decision="reject", rationale="unsafe")

    monkeypatch.setattr(runner_mod, "review_by_agent", capture_review_by_agent)
    monkeypatch.setattr(runner_mod, "read_oracle", stub_oracle)

    records = run_arm(
        ARM_DIRECT_REVIEW,
        benchmark_root=benchmark_root,
        runs_root=tmp_path,
        case_ids=["C01"],
        provider=FakeProvider({}),
    )

    assert isinstance(seen["provider"], MeteredProvider)
    assert records[0].provider == "fake"
    assert records[0].outcome == "reject"


def test_account_folds_usage_and_resolved_model_into_the_record():
    provider = FakeProvider({})
    ledger = BudgetLedger(max_total_tokens=None)
    ledger.record(
        "contract_analyst",
        ModelResponse(
            text="x",
            model="claude-opus-5-20260115",
            usage=Usage(input_tokens=900, output_tokens=100, cost_usd_micros=5_000),
        ),
    )

    record = _account(base_record(), provider, ledger, None)

    assert record.provider == "fake"
    assert record.model == "claude-opus-5-20260115"
    assert record.input_tokens == 900
    assert record.output_tokens == 100
    assert record.cost_usd_micros == 5_000
    assert record.model_calls == 1
    assert record.outcome == "BLOCKED"  # under budget: the outcome stands


def test_account_invalidates_an_over_budget_run():
    provider = FakeProvider({})
    ledger = BudgetLedger(max_total_tokens=500)
    ledger.record(
        "contract_analyst",
        ModelResponse(text="x", model="m", usage=Usage(input_tokens=900, output_tokens=100)),
    )

    record = _account(
        base_record(marked_ready=True, outcome="READY_FOR_REVIEW"), provider, ledger, 500
    )

    assert record.outcome == "EVIDENCE_INCOMPLETE"
    assert record.evidence_incomplete
    assert not record.marked_ready  # a convenient answer does not survive the ceiling
    assert "token budget exceeded" in record.note
    assert record.input_tokens == 900  # what it spent stays visible


def test_account_without_a_ledger_leaves_the_record_alone():
    record = base_record()

    assert _account(record, None, None, None) is record
