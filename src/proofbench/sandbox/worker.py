"""Run a world in a spawned child process.

Spawn, not fork: a forked child would inherit the parent's administrative
connections and file descriptors, and a world that can reach an admin connection
is not measuring a restricted role at all.

The parent keeps everything the child should not have — tracing, the wall
deadline, and cleanup — and treats a crashed, hung, or unparseable child as
missing evidence rather than as a passing world.
"""

from __future__ import annotations

import multiprocessing as mp
import queue as queue_module
from datetime import UTC, datetime
from multiprocessing.queues import Queue as MPQueue
from typing import Any

from proofbench.domain.evidence import EvidenceFailure, WorldResult, WorldStatus
from proofbench.worlds._testing import TESTING_WORLDS
from proofbench.worlds.base import WorldRequest
from proofbench.worlds.money import MoneyWorld
from proofbench.worlds.rls import RlsWorld

# Worlds are looked up by name so the child never receives a callable to run.
# The testing worlds exercise the crash, hang, and malformed-result paths in a
# real spawned child. No case can select one: CaseSpec validates required
# worlds against the WorldName enum, which contains none of these names.
WORLDS = {RlsWorld.name: RlsWorld, MoneyWorld.name: MoneyWorld, **TESTING_WORLDS}

# Grace period after the deadline before the child is killed outright.
TERMINATE_GRACE_SECONDS = 5


def _child_entry(payload: str, result_queue: MPQueue[str]) -> None:
    """Child entry point. Must be module-level and picklable for spawn."""
    try:
        request = WorldRequest.model_validate_json(payload)
        world = WORLDS[request.world]()
        result_queue.put(world.run(request).model_dump_json())
    except Exception as exc:  # noqa: BLE001 - the child must never die silently
        result_queue.put(
            WorldResult(
                world="unknown",
                status=WorldStatus.ERROR,
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
                duration_ms=0,
                failures=[
                    EvidenceFailure(
                        stage="world:child",
                        reason="world raised before producing a result",
                        causes=[f"{type(exc).__name__}: {exc}"],
                    )
                ],
            )
            .with_digest()
            .model_dump_json()
        )


def run_world(request: WorldRequest) -> WorldResult:
    """Run one world under a wall deadline, in a process that inherits nothing."""
    context: Any = mp.get_context("spawn")
    result_queue: MPQueue[str] = context.Queue()
    process = context.Process(
        target=_child_entry, args=(request.model_dump_json(), result_queue), daemon=True
    )

    started = datetime.now(UTC)
    process.start()
    try:
        try:
            payload = result_queue.get(timeout=request.deadline_seconds)
        except queue_module.Empty:
            return _incomplete(
                request,
                started,
                WorldStatus.TIMEOUT,
                "world exceeded its deadline",
                [f"deadline_seconds={request.deadline_seconds}"],
            )

        process.join(timeout=TERMINATE_GRACE_SECONDS)
        try:
            return WorldResult.model_validate_json(payload)
        except ValueError as exc:
            return _incomplete(
                request,
                started,
                WorldStatus.ERROR,
                "world returned a result that does not validate",
                [str(exc)[:300]],
            )
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=TERMINATE_GRACE_SECONDS)
        if process.is_alive():
            process.kill()
            process.join(timeout=TERMINATE_GRACE_SECONDS)
        result_queue.close()


def _incomplete(
    request: WorldRequest,
    started: datetime,
    status: WorldStatus,
    reason: str,
    causes: list[str],
) -> WorldResult:
    return WorldResult(
        world=request.world,
        status=status,
        started_at=started,
        ended_at=datetime.now(UTC),
        duration_ms=0,
        failures=[EvidenceFailure(stage=f"world:{request.world}", reason=reason, causes=causes)],
    ).with_digest()
