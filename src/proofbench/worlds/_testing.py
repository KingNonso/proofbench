"""Controllable worlds for exercising process control.

These exist so the crash, hang, and malformed-result paths can be tested for
real, in a genuinely spawned child, rather than mocked in the parent where the
process boundary would not be involved at all.

They are unreachable from any case by construction: ``CaseSpec`` validates
required worlds against the ``WorldName`` enum, and none of these names is in it.
A case file cannot select one no matter what it declares.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from proofbench.domain.evidence import WorldResult, WorldStatus
from proofbench.worlds.base import World, WorldRequest


class SlowWorld(World):
    """Sleeps past any deadline, so the parent must time it out and kill it."""

    name = "_slow"
    threatened_invariants = ()

    def run(self, request: WorldRequest) -> WorldResult:
        time.sleep(request.deadline_seconds + 30)
        raise AssertionError("unreachable: the parent should have terminated this child")


class CrashWorld(World):
    """Raises before producing a result."""

    name = "_crash"
    threatened_invariants = ()

    def run(self, request: WorldRequest) -> WorldResult:
        raise RuntimeError("world crashed on purpose")


class _NotAResult:
    def model_dump_json(self) -> str:
        return "this is not a world result"


class BadPayloadWorld(World):
    """Returns something that will not deserialise in the parent."""

    name = "_bad_payload"
    threatened_invariants = ()

    def run(self, request: WorldRequest) -> Any:
        return _NotAResult()


class QuickWorld(World):
    """Succeeds immediately, for the happy path of process control."""

    name = "_quick"
    threatened_invariants = ()

    def run(self, request: WorldRequest) -> WorldResult:
        now = datetime.now(UTC)
        return WorldResult(
            world=self.name,
            status=WorldStatus.PASSED,
            started_at=now,
            ended_at=now,
            duration_ms=0,
        ).with_digest()


TESTING_WORLDS = {
    world.name: world for world in (SlowWorld, CrashWorld, BadPayloadWorld, QuickWorld)
}
