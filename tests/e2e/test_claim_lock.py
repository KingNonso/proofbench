"""Every claim the presentation may make is backed by an artifact.

`5-min-presentation.md` §2 is a claim-lock table: a spoken claim is permitted
only when its evidence exists. These tests are that table, executed. A row that
fails here is a sentence that must be cut from the video, not softened.

The point is to catch the failure that matters most in a submission: a claim that
was true when it was written and quietly stopped being true.
"""

import json

import pytest

pytestmark = pytest.mark.e2e

TIMELINE_WORLDS = {"rolling", "interruption", "rollback"}


def certificate(repo_root, case_id):
    return json.loads((repo_root / "tests" / "golden" / case_id / "certificate.json").read_text())


def test_three_agents_have_separate_jobs(repo_root):
    bundle = repo_root / "tests" / "golden" / "C01"
    for artifact in ("contract.json", "world-plan.json", "remediation.json"):
        assert (bundle / artifact).is_file(), f"no {artifact} to show"
    assert (repo_root / "submission" / "trace-index.md").is_file()


def test_deterministic_checks_make_the_decision(repo_root):
    bundle = repo_root / "tests" / "golden" / "C01"
    assert (bundle / "checks.json").is_file()
    decision = json.loads((bundle / "decision.json").read_text())
    assert decision["decisive_check_ids"], "a decision with no decisive check names nothing"


def test_the_c01_failure_and_its_confirmed_blast_radius(repo_root):
    cert = certificate(repo_root, "C01")
    assert cert["first_screen"]["decisive_invariant"] == "INV-RLS-001"

    blast = cert["first_screen"]["confirmed_blast_radius"]
    assert blast, "BLOCKED with nothing confirmed is an assertion, not evidence"
    for item in blast:
        # "Confirmed" means traceable to an executed check and to real rows.
        assert item["check_ids"], f"{item['invariant_id']} cites no check"
        assert item["row_keys"], f"{item['invariant_id']} names no rows"
    assert cert["decision"]["possible"] == [], "possible and confirmed must not merge"


def test_the_human_is_asked_only_for_domain_authority(repo_root):
    cert = certificate(repo_root, "C04")
    assert cert["first_screen"]["external_state"] == "DOMAIN_RULING_REQUIRED"
    packet = (repo_root / "tests" / "golden" / "C04" / "ruling-packet.md").read_text()
    assert "AQ-001" in packet
    assert packet.count("If this is wrong:") >= 2, "a packet with one reading is not a question"


def test_the_correction_passes_without_changing_the_verdict(repo_root):
    cert = certificate(repo_root, "C01")
    assert cert["correction"] is not None
    assert cert["correction"]["verified"] is True
    # The decision is about the candidate as submitted.
    assert cert["first_screen"]["external_state"] == "BLOCKED"


def test_every_certificate_can_be_replayed(repo_root):
    for number in range(1, 13):
        bundle = repo_root / "tests" / "golden" / f"C{number:02d}"
        for artifact in ("manifest.json", "bundle-root.txt", "certificate.json"):
            assert (bundle / artifact).is_file(), f"C{number:02d} cannot be replayed: no {artifact}"


def test_the_final_arm_improves_the_primary_metric(repo_root):
    summary = json.loads((repo_root / "results" / "summary.json").read_text())
    arms = summary["primary_metric"]["by_arm"]
    baseline = arms["baseline_visible_tests"]
    final = arms["migration_court"]
    assert baseline["denominator"] == final["denominator"] == 9
    assert final["numerator"] < baseline["numerator"]


def test_the_changelog_names_a_contribution_and_a_removal(repo_root):
    changelog = (repo_root / "results" / "improvement-changelog.md").read_text()
    assert "contributed most" in changelog
    assert "Removed, and why" in changelog
    assert changelog.count("**Evidence.**") >= 1, "a removal with no evidence is taste"


def test_timeline_correctness_is_a_finding_not_a_hypothesis(repo_root):
    """PRD section 16 unlocks the hot take only with a recorded case."""
    qualifying = []
    for number in range(1, 13):
        case_id = f"C{number:02d}"
        cert = certificate(repo_root, case_id)
        if not all(check["status"] == "passed" for check in cert["visible_tests"]):
            continue
        for result in cert["world_results"]:
            if result["world"] in TIMELINE_WORLDS and result["status"] == "failed":
                qualifying.append(case_id)
                break

    assert qualifying, (
        "no case passes its visible check and fails a timeline world; "
        "the hot take must be stated as a hypothesis"
    )
    readme = (repo_root / "README.md").read_text()
    for case_id in qualifying:
        assert case_id in readme, f"{case_id} unlocks the hot take but the README does not cite it"
