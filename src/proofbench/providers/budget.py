"""Token accounting and the condition-level budget.

Neither CLI provider can enforce a token ceiling before a call — Claude caps
dollars, Codex caps nothing — so post-call validation against this ledger is
the *primary* budget mechanism, not a fallback. The sequence is:

1. Before each call, the gate refuses to start a call once the ledger is
   already over its ceiling.
2. After each call, reported usage is recorded verbatim.
3. After the run, the caller checks ``exceeded``: a run that crossed the
   ceiling is invalidated as ``EVIDENCE_INCOMPLETE`` rather than kept because
   its answer happened to be convenient.

Both arms of a condition get the same ceiling (PRD-FR-002 "same budget"): the
final arm spends it across its agents, the direct reviewer gets all of it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from proofbench.domain.base import StrictModel
from proofbench.errors import EvidenceIncompleteError
from proofbench.providers.base import ModelProvider, ModelRequest, ModelResponse

BUDGET_SCHEMA_VERSION: Literal["1.0"] = "1.0"


class CallUsage(StrictModel):
    """What one model call consumed, as reported by the provider."""

    schema_version: Literal["1.0"] = BUDGET_SCHEMA_VERSION
    agent: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd_micros: int = Field(ge=0)


class BudgetLedger:
    """Cumulative usage for one run, with an optional token ceiling."""

    def __init__(self, *, max_total_tokens: int | None = None) -> None:
        self.max_total_tokens = max_total_tokens
        self.calls: list[CallUsage] = []

    @property
    def total_input_tokens(self) -> int:
        return sum(call.input_tokens for call in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(call.output_tokens for call in self.calls)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost_usd_micros(self) -> int:
        return sum(call.cost_usd_micros for call in self.calls)

    @property
    def exceeded(self) -> bool:
        return self.max_total_tokens is not None and self.total_tokens > self.max_total_tokens

    def gate(self, agent: str) -> None:
        """Refuse to start a call once the ceiling is already crossed."""
        if self.exceeded:
            raise EvidenceIncompleteError(
                "model token budget exhausted",
                detail={
                    "agent": agent,
                    "total_tokens": self.total_tokens,
                    "max_total_tokens": self.max_total_tokens,
                },
            )

    def record(self, agent: str, response: ModelResponse) -> None:
        self.calls.append(
            CallUsage(
                agent=agent,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cost_usd_micros=response.usage.cost_usd_micros,
            )
        )


class MeteredProvider:
    """A provider wrapped with a ledger. Same protocol, plus accounting."""

    def __init__(self, inner: ModelProvider, ledger: BudgetLedger) -> None:
        self._inner = inner
        self.ledger = ledger
        self.name = inner.name
        self.mode = inner.mode

    @property
    def calls(self) -> list[CallUsage]:
        return self.ledger.calls

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.ledger.gate(request.agent)
        response = await self._inner.complete(request)
        self.ledger.record(request.agent, response)
        return response
