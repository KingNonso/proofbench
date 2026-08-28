"""Trace validation.

A trace is only evidence if it is intact. This rejects the ways a JSONL chain can
be wrong: a truncated final line from a crash, a resequenced or duplicated event,
a broken link, an edited payload, an unexpected schema version, and history
appended after the run already reported its outcome.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from proofbench.domain.base import StrictModel
from proofbench.domain.trace import TERMINAL_EVENTS, TRACE_SCHEMA_VERSION, TraceEvent
from proofbench.tracing.hashes import digest_json
from proofbench.tracing.writer import GENESIS_HASH


class TraceValidation(StrictModel):
    """The outcome of validating one trace file."""

    valid: bool
    events: int
    root_hash: str
    problems: list[str]


def validate_trace(path: Path) -> TraceValidation:
    """Validate a trace file without raising, so callers can report every problem."""
    problems: list[str] = []

    if not path.is_file():
        return TraceValidation(
            valid=False, events=0, root_hash="", problems=[f"trace file not found: {path}"]
        )

    raw = path.read_text(encoding="utf-8")
    if raw and not raw.endswith("\n"):
        problems.append("final line is truncated: file does not end with a newline")

    lines = [line for line in raw.splitlines() if line.strip()]
    previous_hash = GENESIS_HASH
    expected_seq = 0
    seen_seq: set[int] = set()
    terminated_at: int | None = None
    root_hash = ""

    for index, line in enumerate(lines):
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"line {index + 1}: not valid JSON ({exc.msg})")
            break

        # Checked before validation so an unsupported version reports itself
        # rather than arriving as a generic schema error.
        version = data.get("schema_version") if isinstance(data, dict) else None
        if version != TRACE_SCHEMA_VERSION:
            problems.append(f"line {index + 1}: unsupported schema version {version!r}")
            break

        try:
            event = TraceEvent.model_validate(data)
        except ValidationError as exc:
            problems.append(f"line {index + 1}: does not validate ({exc.error_count()} problems)")
            break

        if terminated_at is not None:
            problems.append(
                f"line {index + 1}: event after the terminal event at line {terminated_at}"
            )

        if event.seq in seen_seq:
            problems.append(f"line {index + 1}: duplicate sequence number {event.seq}")
        elif event.seq != expected_seq:
            problems.append(
                f"line {index + 1}: sequence number {event.seq} is not monotonic, "
                f"expected {expected_seq}"
            )
        seen_seq.add(event.seq)
        expected_seq = event.seq + 1

        if event.previous_hash != previous_hash:
            problems.append(f"line {index + 1}: previous hash does not match the preceding event")

        recomputed = digest_json(event.hashable())
        if recomputed != event.current_hash:
            problems.append(f"line {index + 1}: payload was altered after it was hashed")

        previous_hash = event.current_hash
        root_hash = event.current_hash
        if event.event_type in TERMINAL_EVENTS:
            terminated_at = index + 1

    return TraceValidation(
        valid=not problems, events=len(lines), root_hash=root_hash, problems=problems
    )
