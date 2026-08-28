"""The provider interface and its accounting.

One narrow seam between the agents and any model. It is asynchronous because a
live adapter is network-bound and widening the signature later would ripple
through every agent; the workflow itself is sequential and calls it through a
single synchronous helper.

A provider returns text. Turning that text into a typed object, and refusing it
when it will not become one, is the agent runner's job — never the provider's.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, Final, Literal, Protocol

from pydantic import Field

from proofbench.domain.base import StrictModel

PROVIDER_SCHEMA_VERSION: Final[Literal["1.0"]] = "1.0"


class Message(StrictModel):
    """One message sent to or received from a model."""

    role: Literal["system", "user", "assistant"]
    content: str


class ModelRequest(StrictModel):
    """Everything sent to a model, recorded verbatim in the trace."""

    schema_version: Literal["1.0"] = PROVIDER_SCHEMA_VERSION
    agent: str
    prompt_version: str
    messages: list[Message] = Field(min_length=1)
    max_output_tokens: int = Field(gt=0, le=32_000)
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    seed: int | None = None


class Usage(StrictModel):
    """What a call consumed. Zero for the fake provider, and honestly so."""

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd_micros: int = Field(default=0, ge=0)


class ModelResponse(StrictModel):
    """What came back. ``text`` is raw; parsing happens in the agent runner."""

    schema_version: Literal["1.0"] = PROVIDER_SCHEMA_VERSION
    text: str
    model: str
    usage: Usage = Field(default_factory=Usage)
    stop_reason: str = "end_turn"


class ModelProvider(Protocol):
    """The only way to reach a model."""

    name: str

    async def complete(self, request: ModelRequest) -> ModelResponse: ...


def run_sync[T](coro: Coroutine[Any, Any, T]) -> T:
    """Call an async provider from the sequential workflow.

    The workflow has no concurrency to exploit — contract, then design, then run,
    then remediate — so a loop per call is the honest cost of keeping the
    interface shaped for the adapter that will need it.
    """
    return asyncio.run(coro)
