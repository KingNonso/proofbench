"""Append-only trace writer with a hash chain.

Every append is flushed and fsynced before the writer returns, so a crash cannot
leave a trace that claims more than reached disk. Writes after the terminal event
are refused: a run that has already reported its outcome must not gain new
history.

If writing fails, the writer attempts an independent ``failure.json`` sink. That
sink is best-effort by design — a failure to write it must not mask the original
error, which is the thing worth reporting.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from proofbench.domain.trace import TERMINAL_EVENTS, EventType, TraceEvent
from proofbench.errors import EvidenceIncompleteError
from proofbench.tracing.hashes import canonical_json, digest_json
from proofbench.tracing.redaction import redact_payload, redact_text

GENESIS_HASH = "0" * 64
TRACE_WRITE_FAILED = "TRACE_WRITE_FAILED: trace could not be appended; evidence is incomplete"


class TraceWriter:
    """Writes ``trajectory.jsonl`` and returns its root hash."""

    def __init__(
        self,
        path: Path,
        run_id: str,
        *,
        secrets: tuple[str, ...] = (),
    ) -> None:
        self.path = path
        self.run_id = run_id
        self._secrets = tuple(s for s in secrets if s)
        self._seq = 0
        self._previous_hash = GENESIS_HASH
        self._terminated = False
        self._closed = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")

    @property
    def root_hash(self) -> str:
        """Hash of the last event written. Becomes ``manifest.trace_root_hash``."""
        return self._previous_hash

    @property
    def sealed(self) -> bool:
        return self._terminated

    def emit(
        self,
        event_type: EventType,
        *,
        actor: str,
        stage: str,
        summary: str = "",
        payload: dict[str, Any] | None = None,
        refs: list[str] | None = None,
    ) -> TraceEvent:
        """Append one event. Raises ``EvidenceIncompleteError`` if it cannot."""
        if self._terminated:
            raise EvidenceIncompleteError(
                "trace already reached its terminal event",
                detail={"run_id": self.run_id, "event_type": event_type.value},
            )

        clean_payload, payload_marks = redact_payload(payload or {}, extra_secrets=self._secrets)
        clean_summary, summary_marks = redact_text(summary, extra_secrets=self._secrets)

        event = TraceEvent(
            run_id=self.run_id,
            seq=self._seq,
            event_type=event_type,
            actor=actor,
            stage=stage,
            timestamp=datetime.now(UTC),
            summary=clean_summary,
            payload=clean_payload,
            refs=refs or [],
            redactions=sorted(set(payload_marks) | set(summary_marks)),
            previous_hash=self._previous_hash,
        )
        event = event.model_copy(update={"current_hash": digest_json(event.hashable())})

        try:
            self._handle.write(canonical_json(event.model_dump(mode="json")).decode("utf-8") + "\n")
            self._handle.flush()
            os.fsync(self._handle.fileno())
        except OSError as exc:
            self._write_failure_sink(exc, event_type)
            raise EvidenceIncompleteError(
                TRACE_WRITE_FAILED,
                detail={"run_id": self.run_id, "last_valid_seq": self._seq - 1, "error": str(exc)},
            ) from exc

        self._seq += 1
        self._previous_hash = event.current_hash
        if event_type in TERMINAL_EVENTS:
            self._terminated = True
        return event

    def _write_failure_sink(self, error: Exception, event_type: EventType) -> None:
        """Best effort. Never raises, never masks the original error."""
        print(TRACE_WRITE_FAILED, file=sys.stderr)
        try:
            payload = {
                "run_id": self.run_id,
                "reason": TRACE_WRITE_FAILED,
                "failed_event_type": event_type.value,
                "last_valid_seq": self._seq - 1,
                "error": str(error),
                "recorded_at": datetime.now(UTC).isoformat(),
            }
            target = self.path.parent / "failure.json"
            with tempfile.NamedTemporaryFile(
                "w", dir=target.parent, delete=False, encoding="utf-8"
            ) as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
                temp_name = handle.name
            Path(temp_name).replace(target)
        except OSError:
            # The sink is a courtesy. The original failure is already raised by
            # the caller and the stable message is already on stderr.
            return

    def close(self) -> str:
        """Close the file and return the trace root hash."""
        if not self._closed:
            self._handle.close()
            self._closed = True
        return self._previous_hash

    def __enter__(self) -> TraceWriter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
