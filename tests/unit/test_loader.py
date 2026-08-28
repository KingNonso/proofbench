import shutil

import pytest

from proofbench.errors import CaseValidationError, OracleBoundaryError
from proofbench.intake.loader import load_case


def test_c01_validates_and_freezes_every_declared_input(c01_case):
    loaded = load_case(c01_case)

    assert loaded.case.case_id == "C01"
    assert loaded.policy.policy_id == "aidledger-default"
    # policy, candidate, one schema file, roles, policies, fixtures, one visible test
    assert len(loaded.inputs) == 7
    assert {item.field for item in loaded.inputs} >= {
        "policy_path",
        "candidate.migration_path",
        "fixture.roles_path",
        "visible_tests[0]",
    }
    assert len(loaded.inputs_digest) == 64


def test_inputs_digest_changes_when_a_candidate_changes(c01_case, tmp_path):
    before = load_case(c01_case).inputs_digest

    copy = tmp_path / "aidledger"
    shutil.copytree(c01_case.parents[2], copy, symlinks=True)
    candidate = copy / "cases" / "C01" / "candidate.sql"
    candidate.write_text(candidate.read_text() + "\n-- one more comment\n")

    after = load_case(copy / "cases" / "C01" / "case.yaml").inputs_digest
    assert after != before


def test_missing_case_file_is_reported(tmp_path):
    with pytest.raises(CaseValidationError, match="does not exist"):
        load_case(tmp_path / "absent.yaml")


def test_case_outside_a_benchmark_root_is_reported(tmp_path):
    stray = tmp_path / "case.yaml"
    stray.write_text("schema_version: '1.0'\n")
    with pytest.raises(CaseValidationError, match="no benchmark root found"):
        load_case(stray)


def test_case_pointing_into_the_oracle_is_rejected(c01_case, tmp_path):
    copy = tmp_path / "aidledger"
    shutil.copytree(c01_case.parents[2], copy, symlinks=True)
    case_file = copy / "cases" / "C01" / "case.yaml"
    case_file.write_text(
        case_file.read_text().replace(
            "policy_path: policies/base-policy.yaml",
            "policy_path: evaluator_only/C01.oracle.yaml",
        )
    )
    with pytest.raises(OracleBoundaryError):
        load_case(case_file)


def test_policy_referencing_an_undeclared_role_is_rejected(c01_case, tmp_path):
    # A probe naming a role that does not exist would never be executed,
    # which is the quietest way for a tenant isolation check to pass.
    copy = tmp_path / "aidledger"
    shutil.copytree(c01_case.parents[2], copy, symlinks=True)
    policy = copy / "policies" / "base-policy.yaml"
    policy.write_text(policy.read_text().replace("role: aidledger_app", "role: ghost_role", 1))
    with pytest.raises(CaseValidationError, match="not declared"):
        load_case(copy / "cases" / "C01" / "case.yaml")


def test_schema_problems_are_located(c01_case, tmp_path):
    copy = tmp_path / "aidledger"
    shutil.copytree(c01_case.parents[2], copy, symlinks=True)
    case_file = copy / "cases" / "C01" / "case.yaml"
    case_file.write_text(case_file.read_text().replace("seed: 20260828", "seed: -1"))
    with pytest.raises(CaseValidationError) as caught:
        load_case(case_file)
    assert "seed" in " ".join(str(v) for v in caught.value.detail.values())
