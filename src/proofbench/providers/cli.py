"""Subscription-CLI providers: Codex and Claude Code driven headless.

Each adapter runs a locally authenticated agent CLI as a single-turn,
no-tools completion engine. Every invocation is a fixed argument array against
a module-level executable name — no shell, no caller-supplied binary, a timeout
on every call — the same shape as ``sandbox.docker``.

What these adapters are, honestly: the measured unit is *model plus CLI
harness*. The harness wraps the prompt in its own system prompt, which is
unversioned here beyond the recorded CLI version. Within one experiment both
arms share the harness, so the comparison holds; across harnesses it does not,
and results from different providers are never pooled.

What they refuse to hide:
- Missing token accounting is ``EVIDENCE_INCOMPLETE``, never a zero that reads
  as a measurement.
- A resolved model other than the one requested is ``EVIDENCE_INCOMPLETE``;
  silent fallback is forbidden.
- Tool or multi-turn activity in a no-tools configuration is
  ``EVIDENCE_INCOMPLETE``; a completion that ran commands answered a different
  question than the one asked.

Credentials are never read, copied, or exported here. ``*_API_KEY`` variables
are stripped from the child environment so the invocation cannot silently
switch from subscription auth to key auth; the CLIs resolve their own stored
logins (``CODEX_HOME``, Claude's OAuth profile).

Sampling seeds and temperature are not accepted by either CLI. The request's
``seed`` is recorded in the trace as always, and the certificate carries the
non-support as a known limit rather than pretending the seed reached the model.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any

from proofbench.errors import EvidenceIncompleteError
from proofbench.providers.base import Message, ModelRequest, ModelResponse, Usage

CODEX_EXECUTABLE = "codex"
CLAUDE_EXECUTABLE = "claude"

CODEX_DEFAULT_MODEL = "gpt-5.5"
CLAUDE_DEFAULT_MODEL = "claude-opus-5"

# A reasoning model on a long contract prompt is slow. The timeout is evidence
# (the run reports EVIDENCE_INCOMPLETE), never a decision input.
DEFAULT_TIMEOUT_SECONDS = 600
VERSION_TIMEOUT_SECONDS = 30

_STDERR_TAIL = 500

# Codex item types that mean the model did something other than answer.
_CODEX_TOOL_ITEM_TYPES = frozenset(
    {
        "command_execution",
        "local_shell_call",
        "mcp_tool_call",
        "web_search",
        "file_change",
        "patch_apply",
        "collab_tool_call",
    }
)


def _child_env() -> dict[str, str]:
    """The inherited environment minus every ``*_API_KEY``.

    Stripping the keys is what makes "authentication mode: subscription" a
    recorded fact rather than a hope: with a key present, either CLI would
    quietly prefer it and the manifest would be wrong.
    """
    return {key: value for key, value in os.environ.items() if not key.endswith("_API_KEY")}


def _run_cli(
    argv: list[str],
    *,
    stdin_text: str,
    timeout: int,
    cwd: str,
) -> tuple[str, str, int]:
    """Run one CLI invocation. Returns (stdout, stderr, returncode)."""
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, module-level binary
            argv,
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=_child_env(),
            check=False,
        )
    except FileNotFoundError as exc:
        raise EvidenceIncompleteError(
            f"{argv[0]} is not available on PATH",
            detail={"executable": argv[0]},
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise EvidenceIncompleteError(
            f"{argv[0]} timed out",
            detail={"executable": argv[0], "timeout_seconds": timeout},
        ) from exc
    return completed.stdout, completed.stderr, completed.returncode


def executable_version(executable: str) -> str:
    """Report a CLI's version string for the experiment manifest."""
    stdout, stderr, returncode = _run_cli(
        [executable, "--version"], stdin_text="", timeout=VERSION_TIMEOUT_SECONDS, cwd="."
    )
    if returncode != 0 or not stdout.strip():
        raise EvidenceIncompleteError(
            f"{executable} --version failed",
            detail={"returncode": returncode, "stderr": stderr[-_STDERR_TAIL:]},
        )
    return stdout.strip()


def _split_messages(messages: list[Message]) -> tuple[str, str]:
    """Fold typed messages into (system_text, user_text) for a one-shot CLI.

    Neither CLI accepts a structured multi-turn conversation in a single
    non-interactive call, so the schema-repair round is serialised as a
    labelled transcript. That serialisation is part of the harness, recorded
    by the CLI version in the manifest.
    """
    system = "\n\n".join(m.content for m in messages if m.role == "system")
    turns = [m for m in messages if m.role != "system"]
    if len(turns) == 1:
        return system, turns[0].content
    parts = [
        f"[{'ASSISTANT (previous reply)' if m.role == 'assistant' else 'USER'}]\n{m.content}"
        for m in turns
    ]
    return system, "\n\n".join(parts)


def _fallback_guard(requested: str, resolved: str, *, agent: str) -> None:
    """A resolved model must be the requested one, allowing a date suffix."""
    if resolved != requested and not resolved.startswith(f"{requested}-"):
        raise EvidenceIncompleteError(
            "model fallback detected: the CLI answered with a different model",
            detail={"agent": agent, "requested": requested, "resolved": resolved},
        )


class CodexCliProvider:
    """``codex exec`` in ephemeral, read-only, JSONL mode."""

    name = "codex_cli"
    mode = "live"
    executable = CODEX_EXECUTABLE
    # No list-price table is bundled for this model family, so no cost figure
    # is invented; token counts are recorded and cost is reported as absent.
    cost_basis = "unavailable"

    def __init__(
        self, model: str = CODEX_DEFAULT_MODEL, *, timeout: int = DEFAULT_TIMEOUT_SECONDS
    ) -> None:
        self.model = model
        self.timeout = timeout

    def preflight(self) -> dict[str, str]:
        return {"executable": self.executable, "version": executable_version(self.executable)}

    def argv_template(self) -> list[str]:
        """The exact invocation, with the per-call working directory templated.

        Secret-free by construction: nothing in the argv is caller-supplied and
        credentials never appear on the command line.
        """
        return self._argv("<workdir>")

    def _argv(self, workdir: str) -> list[str]:
        return [
            self.executable,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--color",
            "never",
            "--json",
            "-s",
            "read-only",
            "-c",
            "tools.web_search=false",
            "-m",
            self.model,
            "-C",
            workdir,
            "-",
        ]

    async def complete(self, request: ModelRequest) -> ModelResponse:
        system, user = _split_messages(request.messages)
        prompt = f"{system}\n\n{user}" if system else user
        with tempfile.TemporaryDirectory(prefix="proofbench-codex-") as workdir:
            stdout, stderr, returncode = _run_cli(
                self._argv(workdir), stdin_text=prompt, timeout=self.timeout, cwd=workdir
            )
        text, usage, resolved = _parse_codex_events(
            stdout, agent=request.agent, stderr=stderr, returncode=returncode
        )
        _fallback_guard(self.model, resolved, agent=request.agent)
        return ModelResponse(text=text, model=resolved, usage=usage, stop_reason="end_turn")


def _parse_codex_events(
    stdout: str, *, agent: str, stderr: str, returncode: int
) -> tuple[str, Usage, str]:
    """Extract the final agent message, token usage, and resolved model.

    Reasoning items are discarded: they are not the observable answer, and
    grading them would grade prose. Tool items are refused outright.
    """
    detail = {"agent": agent, "returncode": returncode, "stderr": stderr[-_STDERR_TAIL:]}

    events: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    if not events:
        raise EvidenceIncompleteError("codex produced no JSONL events", detail=detail)

    text: str | None = None
    input_tokens = 0
    output_tokens = 0
    saw_usage = False
    resolved: str | None = None
    tool_items: list[str] = []

    for event in events:
        item = event.get("item")
        if isinstance(item, dict):
            item_type = str(item.get("type") or item.get("item_type") or "")
            if item_type == "agent_message" and isinstance(item.get("text"), str):
                text = item["text"]
            elif item_type in _CODEX_TOOL_ITEM_TYPES:
                tool_items.append(item_type)
        usage = event.get("usage")
        if isinstance(usage, dict):
            saw_usage = True
            input_tokens += int(usage.get("input_tokens", 0)) + int(
                usage.get("cached_input_tokens", 0)
            )
            output_tokens += int(usage.get("output_tokens", 0))
        for candidate in (event, event.get("session"), event.get("payload")):
            if isinstance(candidate, dict) and isinstance(candidate.get("model"), str):
                resolved = candidate["model"]

    if tool_items:
        raise EvidenceIncompleteError(
            "codex performed tool activity in a no-tools configuration",
            detail={**detail, "tool_items": tool_items},
        )
    if text is None:
        raise EvidenceIncompleteError("codex returned no agent message", detail=detail)
    if not saw_usage:
        raise EvidenceIncompleteError("codex reported no token usage", detail=detail)
    if resolved is None:
        raise EvidenceIncompleteError("codex did not report which model answered", detail=detail)
    return text, Usage(input_tokens=input_tokens, output_tokens=output_tokens), resolved


class ClaudeCliProvider:
    """``claude -p`` in restricted, safe-mode, no-tools, single-turn JSON mode."""

    name = "claude_cli"
    mode = "live"
    executable = CLAUDE_EXECUTABLE
    # The CLI reports total_cost_usd itself; recorded as a CLI-reported
    # estimate, never as a billed figure.
    cost_basis = "cli-reported-estimate"

    def __init__(
        self,
        model: str = CLAUDE_DEFAULT_MODEL,
        *,
        effort: str = "high",
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_budget_usd: float | None = None,
    ) -> None:
        self.model = model
        self.effort = effort
        self.timeout = timeout
        self.max_budget_usd = max_budget_usd

    def preflight(self) -> dict[str, str]:
        return {"executable": self.executable, "version": executable_version(self.executable)}

    def argv_template(self) -> list[str]:
        """The exact invocation, with the per-call system prompt templated."""
        return self._argv("<system-prompt>")

    def _argv(self, system: str) -> list[str]:
        argv = [
            self.executable,
            "-p",
            "--output-format",
            "json",
            "--restricted",
            "--safe-mode",
            "--tools",
            "",
            # With no --mcp-config given, strict mode leaves zero MCP servers.
            "--strict-mcp-config",
            "--max-turns",
            "1",
            "--no-session-persistence",
            "--model",
            self.model,
            "--effort",
            self.effort,
        ]
        if system:
            argv += ["--system-prompt", system]
        if self.max_budget_usd is not None:
            argv += ["--max-budget-usd", f"{self.max_budget_usd:.2f}"]
        return argv

    async def complete(self, request: ModelRequest) -> ModelResponse:
        system, user = _split_messages(request.messages)
        with tempfile.TemporaryDirectory(prefix="proofbench-claude-") as workdir:
            stdout, stderr, returncode = _run_cli(
                self._argv(system), stdin_text=user, timeout=self.timeout, cwd=workdir
            )
        text, usage, resolved = _parse_claude_result(
            stdout, agent=request.agent, stderr=stderr, returncode=returncode
        )
        _fallback_guard(self.model, resolved, agent=request.agent)
        return ModelResponse(text=text, model=resolved, usage=usage, stop_reason="end_turn")


def _parse_claude_result(
    stdout: str, *, agent: str, stderr: str, returncode: int
) -> tuple[str, Usage, str]:
    """Extract the result text, token usage, and resolved model from JSON output."""
    detail = {"agent": agent, "returncode": returncode, "stderr": stderr[-_STDERR_TAIL:]}
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise EvidenceIncompleteError(
            "claude produced no parseable JSON result", detail=detail
        ) from exc
    if not isinstance(payload, dict):
        raise EvidenceIncompleteError("claude result was not a JSON object", detail=detail)

    if payload.get("is_error"):
        raise EvidenceIncompleteError(
            "claude reported an error result",
            detail={**detail, "subtype": str(payload.get("subtype", ""))},
        )

    num_turns = int(payload.get("num_turns", 1))
    if num_turns > 1:
        raise EvidenceIncompleteError(
            "claude took multiple turns in a single-turn configuration",
            detail={**detail, "num_turns": num_turns},
        )

    text = payload.get("result")
    if not isinstance(text, str) or not text:
        raise EvidenceIncompleteError("claude returned no result text", detail=detail)

    usage = payload.get("usage")
    if not isinstance(usage, dict) or "output_tokens" not in usage:
        raise EvidenceIncompleteError("claude reported no token usage", detail=detail)
    # Billed input is the sum of fresh, cache-write, and cache-read tokens.
    input_tokens = (
        int(usage.get("input_tokens", 0))
        + int(usage.get("cache_creation_input_tokens", 0))
        + int(usage.get("cache_read_input_tokens", 0))
    )
    output_tokens = int(usage.get("output_tokens", 0))

    model_usage = payload.get("modelUsage")
    if not isinstance(model_usage, dict) or not model_usage:
        raise EvidenceIncompleteError("claude did not report which model answered", detail=detail)
    resolved = max(
        model_usage,
        key=lambda name: _model_usage_tokens(model_usage[name]),
    )

    # Float-to-integer conversion happens once, here, at the boundary — the
    # same pattern as the live adapter's estimate. Micros from then on.
    cost_micros = int(round(float(payload.get("total_cost_usd", 0.0)) * 1_000_000))

    return (
        text,
        Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd_micros=max(cost_micros, 0),
        ),
        resolved,
    )


def _model_usage_tokens(stats: Any) -> int:
    if not isinstance(stats, dict):
        return 0
    return int(stats.get("inputTokens", 0)) + int(stats.get("outputTokens", 0))
