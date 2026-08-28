"""The oracle boundary.

A path denylist is defence in depth. The boundary that matters is structural:
only ``proofbench.evaluation`` may import the oracle loader, and it may read only
after a review subprocess has exited. These tests walk the import graph rather
than grepping, so a re-export or an aliased import cannot slip past.
"""

import ast
from pathlib import Path

import pytest

from proofbench.errors import OracleBoundaryError
from proofbench.evaluation.oracle import ClosedReview, product_view, read_oracle
from proofbench.intake.paths import resolve_contained

pytestmark = pytest.mark.security

FORBIDDEN_MODULES = {"proofbench.evaluation.oracle", "proofbench.domain.oracle"}
ALLOWED_PACKAGE = "proofbench.evaluation"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def test_no_product_module_imports_the_oracle(repo_root):
    offenders = []
    for path in sorted((repo_root / "src" / "proofbench").rglob("*.py")):
        module = ".".join(path.relative_to(repo_root / "src").with_suffix("").parts)
        if module.startswith(ALLOWED_PACKAGE):
            continue
        if imported_modules(path) & FORBIDDEN_MODULES:
            offenders.append(module)
    assert offenders == [], f"product modules importing oracle material: {offenders}"


def test_string_grep_backs_up_the_ast_check(repo_root):
    # Defence in depth for what the AST cannot see: a dynamic import, or a path
    # assembled at runtime.
    offenders = []
    for path in sorted((repo_root / "src" / "proofbench").rglob("*.py")):
        module = ".".join(path.relative_to(repo_root / "src").with_suffix("").parts)
        if module.startswith(ALLOWED_PACKAGE):
            continue
        text = path.read_text(encoding="utf-8")
        if "evaluator_only" in text and "ORACLE_DIR_NAME" not in text:
            offenders.append(module)
    assert offenders == [], f"product modules naming the oracle directory: {offenders}"


def test_declared_oracle_path_is_refused_by_the_product_resolver(benchmark_root):
    with pytest.raises(OracleBoundaryError):
        resolve_contained(benchmark_root, "evaluator_only/C01.oracle.yaml", field="policy_path")


def test_product_view_physically_excludes_the_oracle(benchmark_root, tmp_path):
    view = product_view(benchmark_root, tmp_path)
    assert (view / "cases" / "C01" / "case.yaml").is_file()
    assert not (view / "evaluator_only").exists()
    assert list(view.rglob("*.oracle.yaml")) == []


def test_reading_the_oracle_requires_a_closed_review(benchmark_root, tmp_path):
    # A decision file that does not exist means the review never closed. The
    # oracle stays shut regardless of what the caller claims.
    closed = ClosedReview(
        case_id="C01", run_dir=tmp_path, returncode=0, decision_path=tmp_path / "decision.json"
    )
    with pytest.raises(OracleBoundaryError, match="produced no decision"):
        read_oracle(benchmark_root, closed)


def test_reading_the_oracle_after_a_closed_review_is_logged(benchmark_root, tmp_path):
    (tmp_path / "decision.json").write_text('{"external_state": "BLOCKED"}')
    closed = ClosedReview(
        case_id="C01", run_dir=tmp_path, returncode=0, decision_path=tmp_path / "decision.json"
    )

    spec = read_oracle(benchmark_root, closed)

    assert spec.case_id == "C01"
    assert spec.expected_blocking_invariant_ids == ["INV-RLS-001"]
    log = (tmp_path / "oracle-access.jsonl").read_text()
    assert "C01.oracle.yaml" in log
