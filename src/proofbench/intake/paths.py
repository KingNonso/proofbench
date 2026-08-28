"""Contained path resolution.

Schemas validate data; they never touch the filesystem. This module owns the
filesystem half of the boundary: given a root and a repository-relative POSIX
path, it either returns a resolved file inside that root or raises.

The oracle check here is defence in depth, not the primary boundary. The primary
boundary is that a `proofbench review` subprocess is never given the oracle path
at all (PRD section 8.3).
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from proofbench.config import MAX_INPUT_BYTES, ORACLE_DIR_NAME
from proofbench.errors import OracleBoundaryError, PathContainmentError


def validate_relative_posix(raw: str, *, field: str) -> PurePosixPath:
    """Check the *shape* of a declared path without touching the filesystem.

    Rejects absolute paths, parent traversal, Windows separators, and any
    reference to the evaluator-only subtree.
    """
    if not raw or raw.strip() != raw:
        raise PathContainmentError("path is empty or has surrounding whitespace", location=field)
    if "\\" in raw:
        raise PathContainmentError("path must use POSIX separators", location=field)

    candidate = PurePosixPath(raw)
    if candidate.is_absolute():
        raise PathContainmentError("path must be relative to the case root", location=field)
    if ".." in candidate.parts:
        raise PathContainmentError("path must not traverse upward", location=field)
    if ORACLE_DIR_NAME in candidate.parts:
        raise OracleBoundaryError(
            "product code may not reference the evaluator-only tree",
            location=field,
            detail={"path": raw},
        )
    return candidate


def resolve_contained(root: Path, raw: str, *, field: str) -> Path:
    """Resolve a declared path to a real file inside ``root``.

    Catches the four escapes that matter: absolute paths, ``..`` traversal,
    symlinks pointing outside the root, and symlinks pointing into the oracle.
    """
    relative = validate_relative_posix(raw, field=field)

    resolved_root = root.resolve(strict=True)
    target = (resolved_root / relative).resolve()

    if not target.is_relative_to(resolved_root):
        raise PathContainmentError(
            "path escapes the case root",
            location=field,
            detail={"declared": raw, "resolved": str(target)},
        )
    if ORACLE_DIR_NAME in target.parts:
        raise OracleBoundaryError(
            "path resolves into the evaluator-only tree",
            location=field,
            detail={"declared": raw, "resolved": str(target)},
        )
    if not target.exists():
        raise PathContainmentError(
            "declared input does not exist", location=field, detail={"path": raw}
        )
    if not target.is_file():
        raise PathContainmentError(
            "declared input is not a regular file", location=field, detail={"path": raw}
        )

    size = target.stat().st_size
    if size > MAX_INPUT_BYTES:
        raise PathContainmentError(
            "declared input exceeds the size limit",
            location=field,
            detail={"path": raw, "bytes": size, "limit": MAX_INPUT_BYTES},
        )
    return target
