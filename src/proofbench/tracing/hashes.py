"""Canonical JSON and content hashing.

Two digests, never one (AGENTS.md section 3):

* a **raw** digest over the exact stored bytes, which detects any change at all;
* a **semantic** digest over a declared projection, which ignores fields a model
  has explicitly named as volatile.

Volatile fields belong to the model that owns them. There is deliberately no
global volatile-field set here: a shared set only ever grows until replay stops
detecting real differences.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_READ_CHUNK = 1 << 20


def _encode_default(value: object) -> str:
    """Encode the few non-JSON types allowed in artifacts.

    Datetimes normalise to UTC with a trailing Z so the same instant always
    produces the same bytes regardless of the machine that wrote it.
    """
    if isinstance(value, datetime):
        moment = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        return moment.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"{type(value).__name__} is not serialisable in a ProofBench artifact")


def _assert_no_floats(value: object, path: str = "$") -> None:
    """Reject float anywhere in a safety-critical structure.

    Money is integer minor units end to end. A float that reaches an evidence
    comparison is a correctness bug, not a formatting preference.
    """
    if isinstance(value, bool):
        return
    if isinstance(value, float):
        raise ValueError(f"float is not permitted in safety-critical evidence at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_no_floats(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_no_floats(item, f"{path}[{index}]")


def canonical_json(value: Any, *, reject_floats: bool = False) -> bytes:
    """Serialise to the one byte representation this project hashes.

    UTF-8, sorted keys, compact separators, NaN and Infinity rejected.
    """
    if reject_floats:
        _assert_no_floats(value)
    text = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_encode_default,
    )
    return text.encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Hex SHA-256 of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def digest_json(value: Any, *, reject_floats: bool = False) -> str:
    """Hex SHA-256 of the canonical JSON encoding of a value."""
    return sha256_hex(canonical_json(value, reject_floats=reject_floats))


def hash_file(path: Path) -> str:
    """Hex SHA-256 of a file, read in chunks so large fixtures stay cheap."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_READ_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()
