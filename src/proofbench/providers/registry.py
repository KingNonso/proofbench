"""Provider selection by name.

The seam the experiment scripts use to choose a live provider. Adding a
provider means registering a factory here and implementing the protocol;
nothing in the agents or the workflow changes.

The fake provider is deliberately absent: it is constructed from a case's
recorded fixtures (``workflow.agents.fake_provider_for``), not from a name, and
listing it here would invite selecting it where a live result was expected.
"""

from __future__ import annotations

from collections.abc import Callable

from proofbench.errors import ProviderSelectionError
from proofbench.providers.base import ModelProvider
from proofbench.providers.cli import (
    CLAUDE_DEFAULT_MODEL,
    CODEX_DEFAULT_MODEL,
    ClaudeCliProvider,
    CodexCliProvider,
)

ProviderFactory = Callable[[str | None], ModelProvider]


def _anthropic_api(model: str | None) -> ModelProvider:
    from proofbench.providers.live import LiveProvider  # noqa: PLC0415 - optional dependency

    return LiveProvider(model) if model else LiveProvider()


def _claude_cli(model: str | None) -> ModelProvider:
    return ClaudeCliProvider(model or CLAUDE_DEFAULT_MODEL)


def _codex_cli(model: str | None) -> ModelProvider:
    return CodexCliProvider(model or CODEX_DEFAULT_MODEL)


PROVIDER_FACTORIES: dict[str, ProviderFactory] = {
    "anthropic_api": _anthropic_api,
    "claude_cli": _claude_cli,
    "codex_cli": _codex_cli,
}


def provider_kinds() -> tuple[str, ...]:
    return tuple(sorted(PROVIDER_FACTORIES))


def create_provider(kind: str, *, model: str | None = None) -> ModelProvider:
    """Build the named provider, or refuse with the names that exist."""
    factory = PROVIDER_FACTORIES.get(kind)
    if factory is None:
        raise ProviderSelectionError(
            f"unknown provider kind: {kind!r}",
            detail={"known": ", ".join(provider_kinds())},
        )
    return factory(model)
