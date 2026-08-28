"""The typed tool router (PRD-FR-051).

Every action an agent takes becomes a ``ToolRequest`` and passes through here.
The router decides, before anything executes, whether *this* actor may call
*this* tool at *this* stage, and it caps what comes back.

Two properties are load-bearing:

**Capability is per actor, not global.** The Contract Analyst cannot execute SQL
and the Test Designer cannot read arbitrary files, because the point of splitting
the agents is lost if they all share one capability set.

**A denial is recorded, not silently empty.** A tool call that returned nothing
because it was refused, and a tool call that returned nothing because there was
nothing to find, are different facts. Collapsing them would let an agent build a
contract on an absence it never knew about.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Final, Literal

from pydantic import Field

from proofbench.config import ORACLE_DIR_NAME
from proofbench.domain.base import StrictModel
from proofbench.errors import OracleBoundaryError, PathContainmentError
from proofbench.intake.paths import resolve_contained
from proofbench.tracing.redaction import redact_text

TOOL_SCHEMA_VERSION: Final[Literal["1.0"]] = "1.0"

MAX_OUTPUT_CHARS = 20_000
MAX_MATCHES = 50


class ToolName:
    """The complete tool vocabulary. Nothing outside this list is callable."""

    READ_FILE = "read_file"
    SEARCH_TREE = "search_tree"
    INSPECT_SCHEMA = "inspect_schema"
    INSPECT_ROLES = "inspect_roles"
    LIST_WORLDS = "list_worlds"
    READ_EVIDENCE = "read_evidence"


# Actor to permitted tools. Deliberately narrow: an agent that could do
# everything would make the separation between the three agents decorative.
CAPABILITIES: Final[dict[str, frozenset[str]]] = {
    "contract_analyst": frozenset(
        {ToolName.READ_FILE, ToolName.SEARCH_TREE, ToolName.INSPECT_SCHEMA, ToolName.INSPECT_ROLES}
    ),
    "test_designer": frozenset(
        {ToolName.LIST_WORLDS, ToolName.INSPECT_SCHEMA, ToolName.INSPECT_ROLES}
    ),
    "remediation_engineer": frozenset(
        {ToolName.READ_FILE, ToolName.READ_EVIDENCE, ToolName.INSPECT_SCHEMA}
    ),
}


class ToolRequest(StrictModel):
    """One mediated action."""

    schema_version: Literal["1.0"] = TOOL_SCHEMA_VERSION
    actor: str
    tool: str
    arguments: dict[str, str] = Field(default_factory=dict)


class ToolResult(StrictModel):
    """What the router returned, including a refusal."""

    schema_version: Literal["1.0"] = TOOL_SCHEMA_VERSION
    actor: str
    tool: str
    allowed: bool
    output: str = ""
    truncated: bool = False
    denial_reason: str | None = None
    duration_ms: int = Field(default=0, ge=0)


class ToolContext(StrictModel):
    """What the router is allowed to reach on the agents' behalf."""

    benchmark_root: Path
    run_dir: Path
    schema_summary: str = ""
    roles_summary: str = ""
    world_catalog: str = ""


class ToolRouter:
    """Validates, executes, and caps every agent action."""

    def __init__(self, context: ToolContext, *, secrets: tuple[str, ...] = ()) -> None:
        self.context = context
        self._secrets = tuple(s for s in secrets if s)
        self.calls: list[ToolResult] = []

    def call(self, request: ToolRequest) -> ToolResult:
        """Run one tool request, or refuse it with a reason."""
        clock = time.monotonic()

        permitted = CAPABILITIES.get(request.actor)
        if permitted is None:
            return self._deny(request, f"unknown actor {request.actor!r}", clock)
        if request.tool not in permitted:
            return self._deny(
                request,
                f"{request.actor} may not call {request.tool!r}; "
                f"permitted: {', '.join(sorted(permitted))}",
                clock,
            )

        handler: Callable[[ToolRequest], str] | None = {
            ToolName.READ_FILE: self._read_file,
            ToolName.SEARCH_TREE: self._search_tree,
            ToolName.INSPECT_SCHEMA: lambda _r: self.context.schema_summary,
            ToolName.INSPECT_ROLES: lambda _r: self.context.roles_summary,
            ToolName.LIST_WORLDS: lambda _r: self.context.world_catalog,
            ToolName.READ_EVIDENCE: self._read_evidence,
        }.get(request.tool)

        if handler is None:
            return self._deny(request, f"no handler for {request.tool!r}", clock)

        try:
            raw = handler(request)
        except (PathContainmentError, OracleBoundaryError) as exc:
            return self._deny(request, exc.message, clock)
        except OSError as exc:
            return self._deny(request, f"tool failed: {exc}", clock)

        cleaned, _ = redact_text(raw, extra_secrets=self._secrets)
        truncated = len(cleaned) > MAX_OUTPUT_CHARS
        result = ToolResult(
            actor=request.actor,
            tool=request.tool,
            allowed=True,
            output=cleaned[:MAX_OUTPUT_CHARS],
            truncated=truncated,
            duration_ms=int((time.monotonic() - clock) * 1000),
        )
        self.calls.append(result)
        return result

    def _deny(self, request: ToolRequest, reason: str, clock: float) -> ToolResult:
        result = ToolResult(
            actor=request.actor,
            tool=request.tool,
            allowed=False,
            denial_reason=reason,
            duration_ms=int((time.monotonic() - clock) * 1000),
        )
        self.calls.append(result)
        return result

    # -- handlers -----------------------------------------------------------

    def _read_file(self, request: ToolRequest) -> str:
        declared = request.arguments.get("path", "")
        # Containment and the oracle refusal both live in resolve_contained, so
        # an agent gets exactly the same boundary the loader enforces.
        target = resolve_contained(self.context.benchmark_root, declared, field="path")
        return target.read_text(encoding="utf-8")

    def _search_tree(self, request: ToolRequest) -> str:
        needle = request.arguments.get("pattern", "")
        if not needle:
            raise OSError("search_tree requires a pattern")

        matches: list[str] = []
        for path in sorted(self.context.benchmark_root.rglob("*")):
            if not path.is_file() or ORACLE_DIR_NAME in path.parts:
                continue
            if path.suffix not in {".sql", ".yaml", ".yml", ".md"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for number, line in enumerate(text.splitlines(), start=1):
                if needle in line:
                    relative = path.relative_to(self.context.benchmark_root).as_posix()
                    matches.append(f"{relative}:{number}: {line.strip()}")
                    if len(matches) >= MAX_MATCHES:
                        return "\n".join(matches) + f"\n... capped at {MAX_MATCHES} matches"
        return "\n".join(matches) or "no matches"

    def _read_evidence(self, request: ToolRequest) -> str:
        name = request.arguments.get("artifact", "")
        if name not in {"checks.json", "decision.json"}:
            raise OSError(f"evidence artifact {name!r} is not readable")
        return (self.context.run_dir / name).read_text(encoding="utf-8")
