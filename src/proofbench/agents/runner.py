"""Invoke an agent and turn its text into a typed object, or fail the stage.

One schema repair attempt, then stop. The second failure ends the stage as
``EVIDENCE_INCOMPLETE`` rather than retrying until something parses: a loop that
runs until the output validates is selecting for parseability, not correctness,
and would quietly turn a confused agent into a confident one.

Both responses are preserved either way. A reviewer needs to see what the model
actually said, not just that it eventually said something well-formed.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from proofbench.domain.trace import EventType
from proofbench.errors import EvidenceIncompleteError
from proofbench.providers.base import Message, ModelProvider, ModelRequest, run_sync
from proofbench.tracing.writer import TraceWriter

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

REPAIR_INSTRUCTION = (
    "Your previous reply did not validate against the required schema.\n"
    "Validation errors:\n{errors}\n\n"
    "Reply again with a single JSON object that satisfies the schema. "
    "Output JSON only, with no prose and no code fence."
)


def extract_json(text: str) -> str:
    """Pull the JSON body out of a reply that may be fenced or padded."""
    fenced = _FENCE.search(text)
    if fenced:
        return fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text.strip()


def invoke_agent[ModelT: BaseModel](
    *,
    provider: ModelProvider,
    model_cls: type[ModelT],
    agent: str,
    prompt_version: str,
    system_prompt: str,
    user_prompt: str,
    max_output_tokens: int,
    trace: TraceWriter | None = None,
    seed: int | None = None,
) -> ModelT:
    """Call the provider and return a validated object, or raise."""
    messages = [
        Message(role="system", content=system_prompt),
        Message(role="user", content=user_prompt),
    ]
    attempts: list[str] = []

    for attempt in range(2):
        request = ModelRequest(
            agent=agent,
            prompt_version=prompt_version,
            messages=messages,
            max_output_tokens=max_output_tokens,
            seed=seed,
        )
        if trace is not None:
            trace.emit(
                EventType.MODEL_REQUESTED,
                actor=agent,
                stage=f"agent:{agent}",
                summary=f"{agent} request, attempt {attempt + 1}",
                payload={"prompt_version": prompt_version, "messages": len(messages)},
            )

        response = run_sync(provider.complete(request))
        attempts.append(response.text)

        if trace is not None:
            trace.emit(
                EventType.MODEL_RESPONDED,
                actor=agent,
                stage=f"agent:{agent}",
                summary=f"{agent} responded, {len(response.text)} chars",
                payload={
                    "model": response.model,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )

        try:
            return model_cls.model_validate(json.loads(extract_json(response.text)))
        except (json.JSONDecodeError, ValidationError) as exc:
            errors = _describe(exc)
            if attempt == 1:
                raise EvidenceIncompleteError(
                    f"{agent} output failed schema validation twice",
                    detail={
                        "agent": agent,
                        "errors": errors,
                        "attempt_1": attempts[0][:1000],
                        "attempt_2": attempts[1][:1000],
                    },
                ) from exc

            if trace is not None:
                trace.emit(
                    EventType.MODEL_SCHEMA_REPAIR,
                    actor=agent,
                    stage=f"agent:{agent}",
                    summary=f"{agent} output did not validate; requesting one repair",
                    payload={"errors": errors},
                )
            messages = [
                *messages,
                Message(role="assistant", content=response.text),
                Message(role="user", content=REPAIR_INSTRUCTION.format(errors=errors)),
            ]

    raise EvidenceIncompleteError(f"{agent} produced no valid output")


def _describe(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()[:10]
        )
    return str(exc)
