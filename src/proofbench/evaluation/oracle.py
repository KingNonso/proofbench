"""The only loader for evaluator-only material.

The real boundary is a process boundary: ``proofbench review`` runs as a
subprocess that is never given an oracle path, and the evaluator reads the answer
key only after that subprocess has exited. This module is what the evaluator uses
afterwards, plus an access log so a breach is visible rather than inferred.

The existence of a decision file is *not* authorisation. Product code could write
one itself, so ``read_oracle`` requires the caller to hand over the completed
subprocess result — something only the parent that waited for it can hold.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from proofbench.domain.oracle import OracleSpec
from proofbench.errors import OracleBoundaryError

ORACLE_DIR_NAME = "evaluator_only"
ACCESS_LOG_NAME = "oracle-access.jsonl"


@dataclass(frozen=True)
class ClosedReview:
    """Proof that a review subprocess finished before the oracle was opened.

    Constructed only by the evaluator after ``wait()`` returns, so possessing one
    means the decision is already on disk and immutable.
    """

    case_id: str
    run_dir: Path
    returncode: int
    decision_path: Path

    def validate(self) -> None:
        if not self.decision_path.is_file():
            raise OracleBoundaryError(
                "review subprocess produced no decision; the oracle stays closed",
                detail={"case_id": self.case_id, "expected": str(self.decision_path)},
            )


def oracle_path(benchmark_root: Path, case_id: str) -> Path:
    return benchmark_root / ORACLE_DIR_NAME / f"{case_id}.oracle.yaml"


def read_oracle(
    benchmark_root: Path,
    closed: ClosedReview,
    *,
    access_log_dir: Path | None = None,
) -> OracleSpec:
    """Read one case's oracle after its review has closed. Logs every access."""
    closed.validate()

    path = oracle_path(benchmark_root, closed.case_id)
    if not path.is_file():
        raise OracleBoundaryError(
            "no oracle for this case", detail={"case_id": closed.case_id, "path": str(path)}
        )

    spec = OracleSpec.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    if spec.case_id != closed.case_id:
        raise OracleBoundaryError(
            "oracle case id does not match the run",
            detail={"oracle": spec.case_id, "run": closed.case_id},
        )

    _log_access(access_log_dir or closed.run_dir, closed, path)
    return spec


def _log_access(directory: Path, closed: ClosedReview, path: Path) -> None:
    """Append to the evaluator's log, never to the product trajectory."""
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "accessed_at": datetime.now(UTC).isoformat(),
        "case_id": closed.case_id,
        "oracle": path.name,
        "run_dir": str(closed.run_dir),
        "review_returncode": closed.returncode,
        "pid": os.getpid(),
    }
    with (directory / ACCESS_LOG_NAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def product_view(benchmark_root: Path, destination: Path) -> Path:
    """Build a benchmark view with the oracle removed.

    Used to launch a review subprocess with a root that physically cannot reach
    the answer key, so containment does not depend on the subprocess behaving.
    """
    import shutil

    destination.mkdir(parents=True, exist_ok=True)
    view = Path(tempfile.mkdtemp(dir=destination, prefix="product-view-"))
    shutil.copytree(
        benchmark_root,
        view / benchmark_root.name,
        ignore=shutil.ignore_patterns(ORACLE_DIR_NAME),
    )
    return view / benchmark_root.name
