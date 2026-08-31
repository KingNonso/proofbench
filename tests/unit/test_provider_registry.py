"""Provider selection: known kinds construct, unknown kinds refuse loudly."""

from __future__ import annotations

import pytest

from proofbench.errors import ExitCode, ProviderSelectionError
from proofbench.providers.cli import ClaudeCliProvider, CodexCliProvider
from proofbench.providers.fake import FakeProvider
from proofbench.providers.registry import PROVIDER_FACTORIES, create_provider, provider_kinds


def test_registry_lists_the_three_live_kinds() -> None:
    assert provider_kinds() == ("anthropic_api", "claude_cli", "codex_cli")


def test_cli_kinds_construct_with_their_default_models() -> None:
    claude = create_provider("claude_cli")
    codex = create_provider("codex_cli")

    assert isinstance(claude, ClaudeCliProvider)
    assert claude.model == "claude-opus-5"
    assert isinstance(codex, CodexCliProvider)
    assert codex.model == "gpt-5.5"


def test_model_override_reaches_the_provider() -> None:
    provider = create_provider("codex_cli", model="gpt-5.5-turbo")

    assert isinstance(provider, CodexCliProvider)
    assert provider.model == "gpt-5.5-turbo"


def test_unknown_kind_is_a_usage_error_naming_the_known_kinds() -> None:
    with pytest.raises(ProviderSelectionError) as excinfo:
        create_provider("gemini_cli")

    assert excinfo.value.exit_code == ExitCode.USAGE
    assert "anthropic_api" in excinfo.value.detail["known"]


def test_a_new_provider_needs_only_a_registry_entry(monkeypatch) -> None:
    monkeypatch.setitem(PROVIDER_FACTORIES, "recorded_test", lambda model: FakeProvider({}))

    provider = create_provider("recorded_test")

    assert provider.name == "fake"
