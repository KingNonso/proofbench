"""Summaries: provider-stratified, hashed, and impossible to pool by accident."""

from __future__ import annotations

import pytest

from proofbench.errors import EvidenceIncompleteError
from proofbench.evaluation.comparison import (
    experiment_hash,
    providers_block,
    summarise,
    verify,
)
from proofbench.evaluation.records import RunRecord


def record_for(
    arm: str,
    case_id: str = "C01",
    *,
    provider: str = "",
    model: str = "",
    repeat: int = 1,
    outcome: str = "BLOCKED",
) -> RunRecord:
    return RunRecord(
        arm=arm,
        case_id=case_id,
        repeat=repeat,
        outcome=outcome,
        marked_ready=False,
        evidence_incomplete=False,
        asked_for_authority=False,
        provider=provider,
        model=model,
        duration_ms=1,
        case_class="unsafe",
        expected_state="BLOCKED",
    )


def test_providers_block_reports_provider_and_models_per_arm():
    records = [
        record_for("baseline_direct_review", provider="claude_cli", model="claude-opus-5"),
        record_for("migration_court", provider="claude_cli", model="claude-opus-5"),
        record_for("baseline_visible_tests"),
    ]

    block = providers_block(records)

    assert block["baseline_direct_review"] == {
        "provider": "claude_cli",
        "models": ["claude-opus-5"],
    }
    assert block["baseline_visible_tests"] == {"provider": "", "models": []}


def test_mixed_live_providers_are_refused():
    records = [
        record_for("baseline_direct_review", provider="claude_cli"),
        record_for("migration_court", provider="codex_cli"),
    ]

    with pytest.raises(EvidenceIncompleteError, match="cannot be pooled"):
        providers_block(records)


def test_a_live_baseline_against_a_fixture_final_arm_is_refused():
    # The exact shape of the bug that reopened R4: live on one side, recorded
    # fixtures on the other, presented as one comparison.
    records = [
        record_for("baseline_direct_review", provider="claude_cli"),
        record_for("migration_court", provider="fake"),
    ]

    with pytest.raises(EvidenceIncompleteError, match="cannot be pooled"):
        providers_block(records)


def test_summary_carries_providers_and_experiment_hash():
    records = [record_for("migration_court", provider="fake", model="fake-deterministic-1")]

    summary = summarise(records, protocol="p", note="n", experiment_hash_value="abc123")

    assert summary["experiment_hash"] == "abc123"
    assert summary["providers"]["migration_court"]["provider"] == "fake"


def test_experiment_hash_ignores_its_own_field_and_tracks_content():
    record = {"protocol": "p", "cases": ["C01"], "commit": "deadbeef"}

    digest = experiment_hash(record)

    assert experiment_hash({**record, "experiment_hash": digest}) == digest
    assert experiment_hash({**record, "protocol": "q"}) != digest


def test_verify_flags_a_summary_with_no_experiment_hash():
    records = [record_for("migration_court", provider="fake")]
    summary = summarise(records, protocol="p", note="n", clean_replay=(12, 12))

    problems = verify(records, summary)

    assert any("experiment hash" in problem for problem in problems)


def test_verify_flags_a_providers_block_that_does_not_recompute():
    records = [record_for("migration_court", provider="fake")]
    summary = summarise(
        records, protocol="p", note="n", clean_replay=(12, 12), experiment_hash_value="x"
    )
    summary["providers"]["migration_court"]["provider"] = "claude_cli"  # type: ignore[index]

    problems = verify(records, summary)

    assert any("providers block" in problem for problem in problems)


def test_a_clean_summary_verifies_without_problems():
    records = [
        record_for("migration_court", provider="fake", model="fake-deterministic-1"),
        record_for("baseline_visible_tests"),
    ]
    summary = summarise(
        records, protocol="p", note="n", clean_replay=(12, 12), experiment_hash_value="x"
    )

    assert verify(records, summary) == []
