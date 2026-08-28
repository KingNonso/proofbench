"""Strict YAML loading for case and policy files.

A plain safe-loader silently keeps the last of a duplicated key. For a policy
file that decides blocking classes and lock budgets, a silently dropped key is a
wrong decision with no error anywhere, so this loader refuses the document.

Aliases are rejected outright. Case files are configuration; nothing in them
needs an anchor, and allowing expansion invites a decompression bomb.
"""

from __future__ import annotations

from typing import Any

import yaml

from proofbench.config import MAX_YAML_BYTES
from proofbench.errors import CaseValidationError


class StrictYAMLLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate keys and aliases."""

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(yaml.events.AliasEvent):
            event = self.peek_event()  # type: ignore[no-untyped-call]  # PyYAML stubs omit it
            raise CaseValidationError(
                "YAML aliases are not permitted in case or policy files",
                location=_mark(event.start_mark),
            )
        return super().compose_node(parent, index)

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise CaseValidationError(
                    f"duplicate key {key!r}",
                    location=_mark(key_node.start_mark),
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _mark(mark: Any) -> str:
    """Render a YAML position as line and column, both one-based."""
    return f"line {mark.line + 1}, column {mark.column + 1}"


def load_yaml_mapping(raw: bytes, *, source: str) -> dict[str, Any]:
    """Parse a YAML document that must be a single mapping.

    Takes bytes rather than a path so the caller hashes exactly the bytes it
    validated: there is then no window in which the file can change between
    being checked and being frozen.
    """
    if len(raw) > MAX_YAML_BYTES:
        raise CaseValidationError(
            "document exceeds the size limit",
            location=source,
            detail={"bytes": len(raw), "limit": MAX_YAML_BYTES},
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CaseValidationError("document is not valid UTF-8", location=source) from exc

    try:
        document = yaml.load(text, Loader=StrictYAMLLoader)  # noqa: S506 - StrictYAMLLoader subclasses SafeLoader
    except CaseValidationError:
        raise
    except yaml.YAMLError as exc:
        location = source
        problem_mark = getattr(exc, "problem_mark", None)
        if problem_mark is not None:
            location = f"{source} ({_mark(problem_mark)})"
        raise CaseValidationError(f"document is not valid YAML: {exc}", location=location) from exc

    if document is None:
        raise CaseValidationError("document is empty", location=source)
    if not isinstance(document, dict):
        raise CaseValidationError(
            f"document root must be a mapping, found {type(document).__name__}",
            location=source,
        )
    return document
