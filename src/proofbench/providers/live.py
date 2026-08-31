"""Live Anthropic provider.

The one place in the system that reaches the network. It is deliberately thin:
it sends messages and returns text, and every decision about what that text means
belongs to the agent runner and, after that, to deterministic code.

Requires the optional dependency group: ``uv sync --extra live``. Nothing on the
offline judge path imports this module, so a judge with no key and no
``anthropic`` package installed can still run every one of the five commands.
"""

from __future__ import annotations

import importlib

from proofbench.errors import EvidenceIncompleteError
from proofbench.providers.base import ModelRequest, ModelResponse, Usage

DEFAULT_MODEL = "claude-opus-5"

# Anthropic list prices per million tokens, recorded so a cost estimate can say
# where its numbers came from. Reported as an estimate, never as a measurement.
PRICE_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


# The API's max_tokens covers thinking and answer together. The request's
# max_output_tokens is the caller's answer budget; the headroom is a declared
# allowance for adaptive thinking on top of it. Actual consumption is recorded
# per call and enforced by the budget ledger, never assumed from this cap.
THINKING_HEADROOM_TOKENS = 12_000


class LiveProvider:
    """Anthropic Messages API adapter."""

    name = "anthropic"
    mode = "live"

    def __init__(self, model: str = DEFAULT_MODEL, *, effort: str = "high") -> None:
        try:
            anthropic = importlib.import_module("anthropic")
        except ImportError as exc:
            raise EvidenceIncompleteError(
                "the live provider needs the optional anthropic package",
                detail={"install": "uv sync --extra live"},
            ) from exc

        self._anthropic = anthropic
        # Credentials resolve from the environment or an `ant auth login`
        # profile. No key is read, stored, or logged here.
        self._client = anthropic.Anthropic()
        self.model = model
        self.effort = effort

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Send one request. Raises EvidenceIncompleteError on any API failure."""
        system = "\n\n".join(m.content for m in request.messages if m.role == "system")
        turns = [
            {"role": m.role, "content": m.content} for m in request.messages if m.role != "system"
        ]

        try:
            # Streaming: max_tokens is large enough that a non-streaming request
            # risks an HTTP timeout on a long answer.
            with self._client.messages.stream(
                model=self.model,
                max_tokens=request.max_output_tokens + THINKING_HEADROOM_TOKENS,
                system=system,
                messages=turns,
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort},
            ) as stream:
                message = stream.get_final_message()
        except self._anthropic.APIStatusError as exc:
            raise EvidenceIncompleteError(
                "the provider returned an error",
                detail={"status": exc.status_code, "agent": request.agent},
            ) from exc
        except self._anthropic.APIConnectionError as exc:
            raise EvidenceIncompleteError(
                "could not reach the provider", detail={"agent": request.agent}
            ) from exc

        if message.stop_reason == "refusal":
            raise EvidenceIncompleteError(
                "the provider declined the request",
                detail={"agent": request.agent, "stop_reason": message.stop_reason},
            )

        text = "".join(block.text for block in message.content if block.type == "text")
        usage = message.usage
        return ModelResponse(
            text=text,
            model=message.model,
            usage=Usage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd_micros=self._estimate_micros(usage.input_tokens, usage.output_tokens),
            ),
            stop_reason=message.stop_reason or "end_turn",
        )

    def _estimate_micros(self, input_tokens: int, output_tokens: int) -> int:
        """List-price estimate in USD micros. An estimate, and labelled as one."""
        rates = PRICE_USD_PER_MTOK.get(self.model)
        if rates is None:
            return 0
        dollars = (input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000
        return int(round(dollars * 1_000_000))
