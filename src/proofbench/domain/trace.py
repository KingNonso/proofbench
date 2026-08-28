"""Trace events.

The vocabulary is defined whole because it is a stable contract (PRD section
11.1) and a partial one would churn every committed artifact. This slice emits
only the run, check, decision, error, and completion events, which are the ones
that have callers.

Traces record observable actions: messages, tool calls, results, timings. They
never record hidden chain-of-thought (PRD-FR-050).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import Field

from proofbench.domain.base import StrictModel

TRACE_SCHEMA_VERSION: Final[Literal["1.0"]] = "1.0"


class EventType(StrEnum):
    """The complete stable event vocabulary."""

    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    STATE_ENTERED = "state.entered"
    STATE_EXITED = "state.exited"
    MODEL_REQUESTED = "model.requested"
    MODEL_RESPONDED = "model.responded"
    MODEL_SCHEMA_REPAIR = "model.schema_repair"
    TOOL_REQUESTED = "tool.requested"
    TOOL_COMPLETED = "tool.completed"
    TOOL_DENIED = "tool.denied"
    CHECK_STARTED = "check.started"
    CHECK_COMPLETED = "check.completed"
    ASSUMPTION_RECORDED = "assumption.recorded"
    RULING_REQUESTED = "ruling.requested"
    RULING_RECORDED = "ruling.recorded"
    REMEDIATION_PROPOSED = "remediation.proposed"
    DECISION_RECORDED = "decision.recorded"
    ARTIFACT_WRITTEN = "artifact.written"
    ERROR_RECORDED = "error.recorded"


TERMINAL_EVENTS = frozenset({EventType.RUN_COMPLETED})


class TraceEvent(StrictModel):
    """One append-only trace record.

    ``current_hash`` covers the canonical encoding of this event with
    ``current_hash`` itself omitted and ``previous_hash`` included, which is what
    chains the file: altering any earlier event invalidates every hash after it.
    """

    schema_version: Literal["1.0"] = TRACE_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    seq: int = Field(ge=0)
    event_type: EventType
    actor: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    timestamp: datetime
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    refs: list[str] = Field(default_factory=list)
    redactions: list[str] = Field(default_factory=list)
    previous_hash: str
    current_hash: str = ""

    def hashable(self) -> dict[str, Any]:
        """The projection that ``current_hash`` is computed over."""
        data = self.model_dump(mode="json")
        data.pop("current_hash", None)
        return data
