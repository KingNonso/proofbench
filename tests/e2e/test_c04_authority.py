"""The human authority boundary.

The gate has to be a question rather than a veto. If it blocked whatever the
reviewer said, it would not be asking anything -- so both determinations are
exercised here, and they reach opposite states on the same candidate.
"""

import shutil

import pytest
from pydantic import ValidationError

from proofbench.domain.decision import ExternalState
from proofbench.errors import CaseValidationError
from proofbench.workflow.authority import load_ruling
from proofbench.workflow.review import review_case

pytestmark = [pytest.mark.e2e, pytest.mark.integration]

CASE = "benchmark/aidledger/cases/C04/case.yaml"
RULINGS = "benchmark/aidledger/cases/C04/rulings"


@pytest.fixture
def case_path(repo_root):
    return repo_root / CASE


@pytest.fixture
def rulings(repo_root):
    return repo_root / RULINGS


def test_without_a_ruling_c04_asks_rather_than_guesses(case_path, tmp_path):
    cert, run_dir = review_case(case_path, runs_root=tmp_path)

    assert cert.first_screen.external_state == ExternalState.DOMAIN_RULING_REQUIRED.value
    # Deferring worlds pending a ruling is correct behaviour, not missing evidence.
    assert cert.decision.evidence_complete
    assert cert.first_screen.confirmed_blast_radius == []

    packet = (run_dir / "ruling-packet.md").read_text()
    assert "AQ-001" in packet
    assert "Finance operations owner" in packet
    # The reviewer is shown the rows, both readings, and what each costs.
    assert "2 row(s)" in packet
    assert packet.count("If this is wrong:") >= 2
    assert "already checked" in packet


def test_a_ruling_that_contradicts_the_candidate_blocks_it(case_path, rulings, tmp_path):
    cert, _ = review_case(
        case_path,
        runs_root=tmp_path,
        ruling=load_ruling(rulings / "currency-per-organisation.yaml"),
    )

    assert cert.first_screen.external_state == ExternalState.BLOCKED.value
    assert "INV-MONEY-002" in cert.first_screen.decisive_invariant


def test_a_ruling_that_agrees_with_the_candidate_lets_it_through(case_path, rulings, tmp_path):
    cert, _ = review_case(
        case_path, runs_root=tmp_path, ruling=load_ruling(rulings / "currency-uniformly-usd.yaml")
    )

    assert cert.first_screen.external_state == ExternalState.READY_FOR_REVIEW.value
    assert "not an automatic approval" in cert.first_screen.required_action


def test_a_ruling_changes_the_bundle(case_path, rulings, tmp_path):
    without, dir_a = review_case(case_path, runs_root=tmp_path / "a")
    with_ruling, dir_b = review_case(
        case_path,
        runs_root=tmp_path / "b",
        ruling=load_ruling(rulings / "currency-uniformly-usd.yaml"),
    )

    assert without.semantic_projection() != with_ruling.semantic_projection()
    assert not (dir_a / "ruling.json").exists()
    assert (dir_b / "ruling.json").is_file()


def test_a_free_form_approval_cannot_be_recorded_as_a_ruling(rulings, tmp_path):
    # Not a filter on wording. A signature is rejected because it has no scope
    # and determines nothing, so there is nowhere in the model to put it.
    source = (rulings / "currency-uniformly-usd.yaml").read_text()
    for required in ("scope_predicate:", "determination_column:", "determination_value:"):
        line = next(line for line in source.splitlines() if line.startswith(required))
        bad = tmp_path / f"missing-{required.rstrip(':')}.yaml"
        bad.write_text(source.replace(line + "\n", ""))
        with pytest.raises(ValidationError):
            load_ruling(bad)


def test_an_out_of_scope_ruling_is_rejected(case_path, rulings, tmp_path):
    source = (rulings / "currency-uniformly-usd.yaml").read_text()
    bad = tmp_path / "out-of-scope.yaml"
    bad.write_text(source.replace("scope_table: payments", "scope_table: disbursements"))

    with pytest.raises(CaseValidationError, match="out of scope"):
        review_case(case_path, runs_root=tmp_path / "runs", ruling=load_ruling(bad))


def test_a_ruling_for_a_question_nobody_asked_is_rejected(case_path, rulings, tmp_path):
    source = (rulings / "currency-uniformly-usd.yaml").read_text()
    bad = tmp_path / "unasked.yaml"
    bad.write_text(source.replace("question_id: AQ-001", "question_id: AQ-099"))

    with pytest.raises(CaseValidationError, match="was not asked"):
        review_case(case_path, runs_root=tmp_path / "runs", ruling=load_ruling(bad))


def test_a_ruling_cannot_rescue_a_candidate_that_failed_a_check(
    case_path, rulings, tmp_path, repo_root
):
    # The reviewer settles what the data cannot say. They do not overrule what
    # the database demonstrated: the money world still finds the contradiction.
    working = tmp_path / "aidledger"
    shutil.copytree(repo_root / "benchmark" / "aidledger", working, symlinks=True)

    cert, _ = review_case(
        working / "cases" / "C04" / "case.yaml",
        runs_root=tmp_path / "runs",
        ruling=load_ruling(rulings / "currency-per-organisation.yaml"),
    )

    assert cert.first_screen.external_state == ExternalState.BLOCKED.value
    assert cert.decision.evidence_complete
