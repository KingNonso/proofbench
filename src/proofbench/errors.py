"""Typed errors and the stable CLI exit codes they map to.

Exit codes are a public interface. A judge and a CI job both branch on them, so
changing one is a breaking change (AGENTS.md section 2).
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any


class ExitCode(IntEnum):
    """Process exit codes. Stable across releases."""

    OK = 0
    USAGE = 2
    EVIDENCE_NOT_BUILT = 3
    VALIDATION = 4
    CONTAINMENT = 5
    EVIDENCE_INCOMPLETE = 6
    INTEGRITY = 7


class ProofBenchError(Exception):
    """Base class for every error this system raises deliberately.

    Carries the exit code and a machine-readable detail payload so the CLI can
    report a located failure rather than a traceback.
    """

    exit_code: ExitCode = ExitCode.VALIDATION

    def __init__(
        self,
        message: str,
        *,
        location: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.location = location
        self.detail = detail or {}

    def render(self) -> str:
        """Human-readable one-block report, used by the CLI."""
        head = f"{type(self).__name__}: {self.message}"
        if self.location:
            head = f"{head}\n  at: {self.location}"
        for key, value in sorted(self.detail.items()):
            head = f"{head}\n  {key}: {value}"
        return head


class CaseValidationError(ProofBenchError):
    """A case, policy, or YAML document is malformed or violates its schema."""

    exit_code = ExitCode.VALIDATION


class PathContainmentError(ProofBenchError):
    """A declared path escapes its allowed root, or is not a plain file."""

    exit_code = ExitCode.CONTAINMENT


class OracleBoundaryError(ProofBenchError):
    """Product code attempted to resolve a path inside the evaluator-only tree.

    This is never a recoverable condition. A run that touches the oracle before
    its decision closes is an integrity failure and stays visible in results
    (PRD section 8.3).
    """

    exit_code = ExitCode.CONTAINMENT


class InputIntegrityError(ProofBenchError):
    """A declared input changed between validation and hashing."""

    exit_code = ExitCode.INTEGRITY


class EvidenceIncompleteError(ProofBenchError):
    """Trustworthy evidence could not be produced.

    Never downgrade this to a pass. A timeout, a trace write failure, and a
    replay mismatch are all product states (PRD section 13).
    """

    exit_code = ExitCode.EVIDENCE_INCOMPLETE


class ProviderSelectionError(ProofBenchError):
    """An unknown or unusable provider kind was requested.

    A usage error, not an evidence state: nothing ran, so nothing is
    incomplete. Reuses the existing USAGE exit code rather than minting a new
    one, because exit codes are a public interface.
    """

    exit_code = ExitCode.USAGE
