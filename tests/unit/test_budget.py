"""The budget ledger: recording is verbatim, the ceiling is enforced, and an
over-budget run is refused before its next call rather than trimmed after."""

from __future__ import annotations

import pytest

from proofbench.errors import EvidenceIncompleteError
from proofbench.providers.base import Message, ModelRequest, run_sync
from proofbench.providers.budget import BudgetLedger, MeteredProvider
from proofbench.providers.fake import FakeProvider


def request_for(agent: str) -> ModelRequest:
    return ModelRequest(
        agent=agent,
        prompt_version="v1",
        messages=[Message(role="user", content="go")],
        max_output_tokens=100,
    )


def test_ledger_sums_reported_usage() -> None:
    provider = MeteredProvider(
        FakeProvider({"a": ["one"], "b": ["two"]}), BudgetLedger(max_total_tokens=None)
    )

    run_sync(provider.complete(request_for("a")))
    run_sync(provider.complete(request_for("b")))

    assert len(provider.calls) == 2
    assert provider.ledger.total_tokens == 0  # the fake reports zero, honestly
    assert [call.agent for call in provider.calls] == ["a", "b"]


def test_metered_provider_delegates_identity() -> None:
    inner = FakeProvider({})
    provider = MeteredProvider(inner, BudgetLedger())

    assert provider.name == "fake"
    assert provider.mode == "fake"


def test_gate_refuses_the_next_call_once_the_ceiling_is_crossed() -> None:
    ledger = BudgetLedger(max_total_tokens=10)

    class Chatty:
        name = "chatty"
        mode = "live"

        async def complete(self, request: ModelRequest):  # noqa: ANN202
            from proofbench.providers.base import ModelResponse, Usage

            return ModelResponse(
                text="x",
                model="m",
                usage=Usage(input_tokens=8, output_tokens=8),
            )

    provider = MeteredProvider(Chatty(), ledger)

    run_sync(provider.complete(request_for("a")))  # 16 tokens, ceiling crossed
    assert ledger.exceeded

    with pytest.raises(EvidenceIncompleteError, match="budget exhausted"):
        run_sync(provider.complete(request_for("b")))

    assert len(ledger.calls) == 1  # the refused call never reached the model


def test_no_ceiling_means_no_gate() -> None:
    ledger = BudgetLedger(max_total_tokens=None)

    assert not ledger.exceeded
    ledger.gate("a")  # does not raise
