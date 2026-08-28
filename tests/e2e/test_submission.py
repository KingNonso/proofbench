"""The submission holds together.

Two failure modes this exists to catch: a required document that quietly went
missing, and a claim in a document pointing at a file that no longer exists. Both
are the kind of thing nobody notices until a judge clicks the link.
"""

import re

import pytest

pytestmark = pytest.mark.e2e

REQUIRED_DOCS = [
    "README.md",
    "REPRODUCTION.md",
    "CHANGELOG.md",
    "AGENTS.md",
    "AGENT_DISCLOSURE.md",
    "results/improvement-changelog.md",
    "results/comparison.md",
    "results/summary.json",
    "results/raw-runs.jsonl",
    "results/experiment.json",
    "submission/trace-index.md",
    "submission/artifact-index.md",
    "docs/kickoff-delta.md",
    "docs/provenance.md",
    "docs/aidledger-case-map.md",
]

LINK = re.compile(r"\[[^\]]+\]\(([^)#]+)\)")


@pytest.mark.parametrize("relative", REQUIRED_DOCS)
def test_required_document_exists_and_says_something(relative, repo_root):
    path = repo_root / relative
    assert path.is_file(), f"{relative} is missing"
    assert path.stat().st_size > 200, f"{relative} is a stub"


@pytest.mark.parametrize(
    "relative",
    [
        "README.md",
        "REPRODUCTION.md",
        "AGENT_DISCLOSURE.md",
        "submission/trace-index.md",
        "submission/artifact-index.md",
    ],
)
def test_every_local_link_resolves(relative, repo_root):
    source = repo_root / relative
    broken = []
    for target in LINK.findall(source.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        if not (source.parent / target).resolve().exists():
            broken.append(target)
    assert broken == [], f"{relative} links to missing files: {broken}"


def test_every_agent_prompt_ships(repo_root):
    # Brief deliverable 01 requires "the instructions that shape each agent".
    prompts = repo_root / "src" / "proofbench" / "agents" / "prompts"
    names = {path.name for path in prompts.glob("*.md")}
    assert names == {
        "contract_analyst_v1.md",
        "test_designer_v1.md",
        "remediation_engineer_v1.md",
        "direct_reviewer_v1.md",
    }


def test_every_golden_case_has_a_trajectory(repo_root):
    for number in range(1, 13):
        bundle = repo_root / "tests" / "golden" / f"C{number:02d}"
        assert (bundle / "trajectory.jsonl").is_file()
        assert (bundle / "trajectory.md").is_file()
        assert (bundle / "certificate.html").is_file()


def test_no_credential_reaches_a_committed_artifact(repo_root):
    # Brief ground rule 08. Checks the artifacts a judge actually receives.
    patterns = re.compile(r"sk-ant-|ANTHROPIC_API_KEY\s*=\s*\S|password=\S")
    offenders = []
    for directory in ("results", "tests/golden", "submission"):
        for path in (repo_root / directory).rglob("*"):
            if path.is_file() and patterns.search(
                path.read_text(encoding="utf-8", errors="ignore")
            ):
                offenders.append(str(path.relative_to(repo_root)))
    assert offenders == [], f"credential-shaped text in committed artifacts: {offenders}"


def test_no_oracle_content_reaches_a_committed_run_artifact(repo_root):
    # A run bundle that carried its own answer key would not be evidence of
    # anything. The oracle lives only under evaluator_only/.
    offenders = []
    for path in (repo_root / "tests" / "golden").rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "expected_initial_state" in text or "expected_blocking_invariant_ids" in text:
                offenders.append(str(path.relative_to(repo_root)))
    assert offenders == [], f"oracle content in run artifacts: {offenders}"


def test_the_summary_is_the_only_place_metrics_are_quoted_from(repo_root):
    # PRD section 16. If the README states the headline counts, they must match
    # summary.json exactly.
    import json

    summary = json.loads((repo_root / "results" / "summary.json").read_text())
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    for arm, values in summary["primary_metric"]["by_arm"].items():
        cell = f"**{values['numerator']}/{values['denominator']}**"
        assert cell in readme, f"README does not carry {arm}'s counts as {cell}"
