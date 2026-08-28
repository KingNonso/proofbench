import pytest

from proofbench.errors import OracleBoundaryError, PathContainmentError
from proofbench.intake.paths import resolve_contained, validate_relative_posix


@pytest.fixture
def root(tmp_path):
    (tmp_path / "cases" / "C01").mkdir(parents=True)
    (tmp_path / "cases" / "C01" / "candidate.sql").write_text("SELECT 1;\n")
    (tmp_path / "evaluator_only").mkdir()
    (tmp_path / "evaluator_only" / "oracle.yaml").write_text("expected_state: BLOCKED\n")
    return tmp_path


def test_resolves_a_contained_file(root):
    assert resolve_contained(root, "cases/C01/candidate.sql", field="f").is_file()


@pytest.mark.parametrize(
    "bad", ["/etc/passwd", "../outside.sql", "cases/../../outside.sql", "a\\b.sql", ""]
)
def test_shape_escapes_are_rejected(bad):
    with pytest.raises(PathContainmentError):
        validate_relative_posix(bad, field="f")


def test_declared_oracle_path_is_rejected():
    with pytest.raises(OracleBoundaryError):
        validate_relative_posix("evaluator_only/oracle.yaml", field="f")


def test_symlink_escaping_the_root_is_rejected(root, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    (outside / "secret.sql").write_text("SELECT 'leaked';\n")
    (root / "cases" / "C01" / "link.sql").symlink_to(outside / "secret.sql")
    with pytest.raises(PathContainmentError, match="escapes the case root"):
        resolve_contained(root, "cases/C01/link.sql", field="f")


def test_symlink_into_the_oracle_is_rejected(root):
    # The declared path looks innocent. Only the resolved path shows the breach.
    (root / "cases" / "C01" / "notes.yaml").symlink_to(root / "evaluator_only" / "oracle.yaml")
    with pytest.raises(OracleBoundaryError, match="resolves into the evaluator-only tree"):
        resolve_contained(root, "cases/C01/notes.yaml", field="f")


def test_missing_file_is_rejected(root):
    with pytest.raises(PathContainmentError, match="does not exist"):
        resolve_contained(root, "cases/C01/absent.sql", field="f")


def test_directory_is_not_a_valid_input(root):
    with pytest.raises(PathContainmentError, match="not a regular file"):
        resolve_contained(root, "cases/C01", field="f")


def test_oversized_input_is_rejected(root, monkeypatch):
    monkeypatch.setattr("proofbench.intake.paths.MAX_INPUT_BYTES", 4)
    with pytest.raises(PathContainmentError, match="exceeds the size limit"):
        resolve_contained(root, "cases/C01/candidate.sql", field="f")
