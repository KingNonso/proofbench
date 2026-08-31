"""The CLI providers: command construction, isolation, parsing, refusal paths.

Every test here runs without the real binaries: subprocess execution is
replaced at the module seam (``_run_cli``), and the parsers are exercised as
pure functions on canned output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofbench.errors import EvidenceIncompleteError
from proofbench.providers import cli
from proofbench.providers.base import Message, ModelRequest, run_sync
from proofbench.providers.cli import ClaudeCliProvider, CodexCliProvider, _child_env


def request_for(agent: str = "contract_analyst") -> ModelRequest:
    return ModelRequest(
        agent=agent,
        prompt_version="v1",
        messages=[
            Message(role="system", content="You are a reviewer."),
            Message(role="user", content="Review this migration."),
        ],
        max_output_tokens=4000,
    )


def codex_events(
    *,
    model: str = "gpt-5.5",
    text: str | None = '{"ok": true}',
    usage: bool = True,
    tool_item: str | None = None,
) -> str:
    lines: list[str] = [json.dumps({"type": "session.created", "session": {"model": model}})]
    if tool_item:
        lines.append(json.dumps({"type": "item.completed", "item": {"type": tool_item}}))
    if text is not None:
        lines.append(
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": text}})
        )
    if usage:
        lines.append(
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 120, "cached_input_tokens": 30, "output_tokens": 45},
                }
            )
        )
    return "\n".join(lines) + "\n"


def claude_payload(
    *,
    model: str = "claude-opus-5",
    result: str = '{"ok": true}',
    is_error: bool = False,
    num_turns: int = 1,
    usage: dict[str, int] | None = None,
    cost: float = 0.0421,
) -> str:
    payload: dict[str, object] = {
        "type": "result",
        "subtype": "success" if not is_error else "error_during_execution",
        "is_error": is_error,
        "num_turns": num_turns,
        "result": result,
        "total_cost_usd": cost,
        "modelUsage": {model: {"inputTokens": 100, "outputTokens": 40}},
        "usage": usage
        if usage is not None
        else {
            "input_tokens": 80,
            "cache_creation_input_tokens": 15,
            "cache_read_input_tokens": 5,
            "output_tokens": 40,
        },
    }
    return json.dumps(payload)


class RunCapture:
    """Stand-in for ``_run_cli`` that records the invocation."""

    def __init__(self, stdout: str, *, stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.argv: list[str] = []
        self.stdin_text = ""
        self.cwd = ""

    def __call__(self, argv, *, stdin_text, timeout, cwd):  # noqa: ANN001, ANN202
        self.argv = list(argv)
        self.stdin_text = stdin_text
        self.cwd = cwd
        return self.stdout, self.stderr, self.returncode


# --- environment and isolation ---


def test_child_env_strips_every_api_key(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SOME_VENDOR_API_KEY", "x")
    monkeypatch.setenv("PATH", "/usr/bin")

    env = _child_env()

    assert not any(key.endswith("_API_KEY") for key in env)
    assert env["PATH"] == "/usr/bin"


def test_codex_runs_in_a_temporary_workdir_that_is_removed(monkeypatch) -> None:
    capture = RunCapture(codex_events())
    monkeypatch.setattr(cli, "_run_cli", capture)

    run_sync(CodexCliProvider().complete(request_for()))

    assert capture.cwd.startswith("/") and "proofbench-codex-" in capture.cwd
    assert not Path(capture.cwd).exists()


# --- command construction ---


def test_codex_argv_is_locked_down(monkeypatch) -> None:
    capture = RunCapture(codex_events())
    monkeypatch.setattr(cli, "_run_cli", capture)

    run_sync(CodexCliProvider().complete(request_for()))

    assert capture.argv[0] == "codex"
    assert capture.argv[1] == "exec"
    for flag in ("--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check"):
        assert flag in capture.argv
    assert capture.argv[capture.argv.index("-s") + 1] == "read-only"
    assert capture.argv[capture.argv.index("-m") + 1] == "gpt-5.5"
    assert "tools.web_search=false" in capture.argv
    assert capture.argv[-1] == "-"
    assert "Review this migration." in capture.stdin_text
    assert capture.stdin_text.startswith("You are a reviewer.")


def test_claude_argv_is_locked_down(monkeypatch) -> None:
    capture = RunCapture(claude_payload())
    monkeypatch.setattr(cli, "_run_cli", capture)

    run_sync(ClaudeCliProvider().complete(request_for()))

    assert capture.argv[0] == "claude"
    for flag in (
        "-p",
        "--restricted",
        "--safe-mode",
        "--strict-mcp-config",
        "--no-session-persistence",
    ):
        assert flag in capture.argv
    assert capture.argv[capture.argv.index("--tools") + 1] == ""
    assert capture.argv[capture.argv.index("--max-turns") + 1] == "1"
    assert capture.argv[capture.argv.index("--model") + 1] == "claude-opus-5"
    assert capture.argv[capture.argv.index("--system-prompt") + 1] == "You are a reviewer."
    assert "--fallback-model" not in capture.argv
    assert capture.stdin_text == "Review this migration."


def test_claude_budget_flag_appears_only_when_set(monkeypatch) -> None:
    capture = RunCapture(claude_payload())
    monkeypatch.setattr(cli, "_run_cli", capture)

    run_sync(ClaudeCliProvider(max_budget_usd=5.0).complete(request_for()))

    assert capture.argv[capture.argv.index("--max-budget-usd") + 1] == "5.00"


def test_repair_round_is_serialised_as_a_labelled_transcript(monkeypatch) -> None:
    capture = RunCapture(claude_payload())
    monkeypatch.setattr(cli, "_run_cli", capture)
    request = ModelRequest(
        agent="contract_analyst",
        prompt_version="v1",
        messages=[
            Message(role="system", content="sys"),
            Message(role="user", content="first ask"),
            Message(role="assistant", content="bad json"),
            Message(role="user", content="repair instruction"),
        ],
        max_output_tokens=4000,
    )

    run_sync(ClaudeCliProvider().complete(request))

    assert "[USER]\nfirst ask" in capture.stdin_text
    assert "[ASSISTANT (previous reply)]\nbad json" in capture.stdin_text
    assert capture.stdin_text.index("first ask") < capture.stdin_text.index("repair instruction")


# --- codex parsing ---


def test_codex_happy_path_reports_text_usage_and_model(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_run_cli", RunCapture(codex_events()))

    response = run_sync(CodexCliProvider().complete(request_for()))

    assert response.text == '{"ok": true}'
    assert response.model == "gpt-5.5"
    assert response.usage.input_tokens == 150  # fresh plus cached input
    assert response.usage.output_tokens == 45
    assert response.usage.cost_usd_micros == 0  # no invented cost figure


def test_codex_missing_usage_is_evidence_incomplete(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_run_cli", RunCapture(codex_events(usage=False)))

    with pytest.raises(EvidenceIncompleteError, match="no token usage"):
        run_sync(CodexCliProvider().complete(request_for()))


def test_codex_missing_message_is_evidence_incomplete(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_run_cli", RunCapture(codex_events(text=None)))

    with pytest.raises(EvidenceIncompleteError, match="no agent message"):
        run_sync(CodexCliProvider().complete(request_for()))


def test_codex_tool_activity_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_run_cli", RunCapture(codex_events(tool_item="command_execution")))

    with pytest.raises(EvidenceIncompleteError, match="tool activity"):
        run_sync(CodexCliProvider().complete(request_for()))


def test_codex_model_fallback_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_run_cli", RunCapture(codex_events(model="gpt-5-mini")))

    with pytest.raises(EvidenceIncompleteError, match="fallback"):
        run_sync(CodexCliProvider().complete(request_for()))


def test_codex_tolerates_non_json_noise_lines(monkeypatch) -> None:
    noisy = "warming up...\n" + codex_events()
    monkeypatch.setattr(cli, "_run_cli", RunCapture(noisy))

    response = run_sync(CodexCliProvider().complete(request_for()))

    assert response.text == '{"ok": true}'


def test_codex_empty_output_is_evidence_incomplete(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_run_cli", RunCapture("", stderr="auth required", returncode=1))

    with pytest.raises(EvidenceIncompleteError, match="no JSONL events"):
        run_sync(CodexCliProvider().complete(request_for()))


# --- claude parsing ---


def test_claude_happy_path_reports_text_usage_model_and_cost(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_run_cli", RunCapture(claude_payload()))

    response = run_sync(ClaudeCliProvider().complete(request_for()))

    assert response.text == '{"ok": true}'
    assert response.model == "claude-opus-5"
    assert response.usage.input_tokens == 100  # fresh + cache write + cache read
    assert response.usage.output_tokens == 40
    assert response.usage.cost_usd_micros == 42_100


def test_claude_versioned_model_id_satisfies_the_pin(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_run_cli", RunCapture(claude_payload(model="claude-opus-5-20260115")))

    response = run_sync(ClaudeCliProvider().complete(request_for()))

    assert response.model == "claude-opus-5-20260115"


def test_claude_different_model_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_run_cli", RunCapture(claude_payload(model="claude-sonnet-5")))

    with pytest.raises(EvidenceIncompleteError, match="fallback"):
        run_sync(ClaudeCliProvider().complete(request_for()))


def test_claude_error_result_is_evidence_incomplete(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_run_cli", RunCapture(claude_payload(is_error=True)))

    with pytest.raises(EvidenceIncompleteError, match="error result"):
        run_sync(ClaudeCliProvider().complete(request_for()))


def test_claude_multiple_turns_are_refused(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_run_cli", RunCapture(claude_payload(num_turns=3)))

    with pytest.raises(EvidenceIncompleteError, match="multiple turns"):
        run_sync(ClaudeCliProvider().complete(request_for()))


def test_claude_missing_usage_is_evidence_incomplete(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_run_cli", RunCapture(claude_payload(usage={})))

    with pytest.raises(EvidenceIncompleteError, match="no token usage"):
        run_sync(ClaudeCliProvider().complete(request_for()))


def test_claude_unparseable_output_is_evidence_incomplete(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_run_cli", RunCapture("not json", stderr="boom", returncode=1))

    with pytest.raises(EvidenceIncompleteError, match="no parseable JSON"):
        run_sync(ClaudeCliProvider().complete(request_for()))


# --- process failure shapes ---


def test_missing_executable_is_evidence_incomplete(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))  # a PATH with no codex on it

    with pytest.raises(EvidenceIncompleteError, match="not available on PATH"):
        run_sync(CodexCliProvider().complete(request_for()))


def test_timeout_is_evidence_incomplete(monkeypatch) -> None:
    import subprocess

    def raise_timeout(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr(cli.subprocess, "run", raise_timeout)

    with pytest.raises(EvidenceIncompleteError, match="timed out"):
        run_sync(ClaudeCliProvider(timeout=1).complete(request_for()))


def test_providers_declare_live_mode_and_cost_basis() -> None:
    assert CodexCliProvider.mode == "live"
    assert ClaudeCliProvider.mode == "live"
    assert CodexCliProvider.cost_basis == "unavailable"
    assert ClaudeCliProvider.cost_basis == "cli-reported-estimate"
