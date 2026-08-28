"""Compile raw trace events into something a person will actually read.

Works only from explicit event fields. It never infers what an agent was
thinking, and there is nothing here that could: hidden reasoning is not recorded,
so it cannot be reconstructed (PRD-FR-050).

The shape it aims for is the one a reviewer needs:
``expectation -> executed check -> observed result -> decision``.
"""

from __future__ import annotations

import json
from pathlib import Path

from proofbench.domain.certificate import TrajectorySummary
from proofbench.domain.trace import EventType


def compile_trajectory(trace_path: Path) -> TrajectorySummary:
    """Summarise a trace file into stages and a readable narrative."""
    stages: list[str] = []
    narrative: list[str] = []
    root_hash = ""
    count = 0

    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        count += 1
        root_hash = event.get("current_hash", root_hash)

        stage = event.get("stage", "")
        if stage and stage not in stages:
            stages.append(stage)

        narrative.append(_line_for(event))

    return TrajectorySummary(
        events=count, trace_root_hash=root_hash, stages=stages, narrative=narrative
    )


def _line_for(event: dict[str, object]) -> str:
    kind = str(event.get("event_type", ""))
    stage = str(event.get("stage", ""))
    summary = str(event.get("summary", ""))
    payload = event.get("payload") or {}

    if kind == EventType.CHECK_COMPLETED.value and isinstance(payload, dict):
        findings = payload.get("findings") or []
        detail = f" findings={','.join(str(f) for f in findings)}" if findings else ""
        return f"[{stage}] {summary}{detail}"
    if kind == EventType.DECISION_RECORDED.value:
        return f"[{stage}] decision: {summary}"
    return f"[{stage}] {summary}" if summary else f"[{stage}] {kind}"


def render_markdown(summary: TrajectorySummary, *, run_id: str, case_id: str) -> str:
    """Render ``trajectory.md``."""
    lines = [
        f"# Trajectory — {case_id}",
        "",
        f"Run `{run_id}`. {summary.events} events. Trace root `{summary.trace_root_hash[:16]}`.",
        "",
        "Observable actions only. No hidden reasoning is recorded, and none is",
        "reconstructed here.",
        "",
        "## Stages",
        "",
    ]
    lines += [f"- `{stage}`" for stage in summary.stages] or ["- none"]
    lines += ["", "## Timeline", ""]
    lines += [f"{index + 1}. {entry}" for index, entry in enumerate(summary.narrative)]
    lines.append("")
    return "\n".join(lines)
