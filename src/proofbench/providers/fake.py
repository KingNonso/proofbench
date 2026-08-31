"""Deterministic provider for tests and offline golden replay.

Returns recorded responses keyed by agent and case. It is not a mock of a model's
judgement: it is a fixture that lets every deterministic path -- tool mediation,
schema validation, repair, budget exhaustion -- be exercised without a network
call or a key.

Usage is reported as zero rather than invented. A fabricated token count would
end up in a cost table that someone reads as measurement.
"""

from __future__ import annotations

from proofbench.errors import EvidenceIncompleteError
from proofbench.providers.base import ModelRequest, ModelResponse, Usage

FAKE_MODEL = "fake-deterministic-1"


class FakeProvider:
    """Serves canned responses; raises when asked for one it does not have."""

    name = "fake"
    mode = "fake"
    cost_basis = "zero-by-design"

    def __init__(self, responses: dict[str, list[str]]) -> None:
        # agent name -> ordered responses. A list so a schema repair can be
        # given a different second answer than its first.
        self._responses = {agent: list(items) for agent, items in responses.items()}
        self.calls: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        queue = self._responses.get(request.agent)
        if not queue:
            raise EvidenceIncompleteError(
                "fake provider has no response left for this agent",
                detail={"agent": request.agent, "calls": len(self.calls)},
            )
        return ModelResponse(
            text=queue.pop(0),
            model=FAKE_MODEL,
            usage=Usage(),
            stop_reason="end_turn",
        )

    def remaining(self, agent: str) -> int:
        return len(self._responses.get(agent, []))
