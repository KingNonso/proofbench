"""The tenant isolation world.

A world is only trustworthy if it has been shown to pass on safe input and fail
on unsafe input. Both halves are here; either alone proves nothing.
"""

import pytest

from proofbench.domain.evidence import WorldStatus
from proofbench.sandbox.postgres import MIGRATION_ROLE
from proofbench.sandbox.worker import run_world
from proofbench.worlds.base import WorldRequest
from proofbench.worlds.runner import build_targets, run_visible_tests

pytestmark = pytest.mark.integration

NORTHWIND = "11111111-1111-4111-8111-111111111111"
SOUTHGATE = "22222222-2222-4222-8222-222222222222"


def run_rls(sandbox, loaded, database, *, deadline=60):
    targets = build_targets(sandbox, database, list(loaded.policy.rls_probes))
    request = WorldRequest(
        world="rls",
        run_id="rls-test",
        host="127.0.0.1",
        port=sandbox.port,
        database=database,
        credentials={
            role: sandbox.credentials.role_passwords[role]
            for role in sorted({target.probe.role for target in targets})
        },
        targets=targets,
        deadline_seconds=deadline,
    )
    return run_world(request)


def apply_candidate(sandbox, loaded, database, filename):
    sandbox.apply_sql_file(
        database,
        loaded.benchmark_root / "cases" / "C01" / filename,
        user=MIGRATION_ROLE,
    )


def test_the_base_fixture_passes(sandbox, loaded_c01):
    # The known-passing half. A world that has only ever seen a failure is not
    # known to detect anything.
    database = sandbox.clone("rls-base")
    result = run_rls(sandbox, loaded_c01, database)
    assert result.status is WorldStatus.PASSED, [f.summary for f in result.findings]
    assert result.findings == []
    assert len(result.checks) == len(loaded_c01.policy.rls_probes)


def test_c01_fails_with_the_registered_invariant(sandbox, loaded_c01):
    database = sandbox.clone("rls-c01")
    apply_candidate(sandbox, loaded_c01, database, "candidate.sql")

    result = run_rls(sandbox, loaded_c01, database)

    assert result.status is WorldStatus.FAILED
    assert [finding.invariant_id for finding in result.findings] == ["INV-RLS-001"]
    finding = result.findings[0]
    assert finding.blocking

    # The evidence has to name the tenant, the role, and the actual rows, or the
    # blast radius is an assertion rather than an observation.
    leaked = [item for item in finding.observations if item.observed_allowed]
    assert any(item.role == "aidledger_app" for item in leaked)
    assert any(item.target_tenant == SOUTHGATE for item in leaked)
    southgate = next(item for item in leaked if item.target_tenant == SOUTHGATE)
    assert southgate.rows_seen == 2
    assert all("ddddddd4" in key for key in southgate.row_keys)


def test_the_corrected_candidate_passes_the_identical_world(sandbox, loaded_c01):
    database = sandbox.clone("rls-c01-fixed")
    apply_candidate(sandbox, loaded_c01, database, "corrected.sql")

    result = run_rls(sandbox, loaded_c01, database)

    assert result.status is WorldStatus.PASSED, [f.summary for f in result.findings]


def test_c01_still_passes_its_visible_test(sandbox, loaded_c01):
    # The case only tests anything if the obvious check is fooled. If the
    # visible test caught this, a reviewer would not need the world.
    database = sandbox.clone("rls-visible")
    apply_candidate(sandbox, loaded_c01, database, "candidate.sql")

    results = run_visible_tests(sandbox, database, loaded_c01)

    assert [check.status.value for check in results] == ["passed"]


def test_probes_leave_the_database_unchanged(sandbox, loaded_c01):
    # Every probe rolls back. A world that mutated what it measured would make
    # the next world's evidence worthless.
    database = sandbox.clone("rls-rollback")
    with sandbox.connect(database) as conn:
        before = conn.execute("SELECT count(*) FROM payments").fetchone()[0]

    run_rls(sandbox, loaded_c01, database)

    with sandbox.connect(database) as conn:
        after = conn.execute("SELECT count(*) FROM payments").fetchone()[0]
        southgate = conn.execute(
            "SELECT count(*) FROM payments WHERE org_id = %s", (SOUTHGATE,)
        ).fetchone()[0]
    assert (before, after, southgate) == (5, 5, 2)


def test_a_deny_probe_with_no_target_rows_is_an_evidence_error(sandbox, loaded_c01):
    # Zero rows returned proves the boundary held only if there were rows on the
    # other side to withhold. Otherwise the probe is vacuous and must say so.
    database = sandbox.clone("rls-empty-target")
    with sandbox.connect(database) as conn:
        conn.execute("DELETE FROM disbursements")
        conn.execute("DELETE FROM audit_events")
        conn.execute("DELETE FROM payments")
        conn.commit()

    result = run_rls(sandbox, loaded_c01, database)

    assert result.status is WorldStatus.ERROR
    assert any("no target rows" in failure.reason for failure in result.failures)


def test_the_world_is_deterministic_across_runs(sandbox, loaded_c01):
    digests = set()
    for index in range(3):
        database = sandbox.clone(f"rls-determinism-{index}")
        apply_candidate(sandbox, loaded_c01, database, "candidate.sql")
        digests.add(run_rls(sandbox, loaded_c01, database).semantic_digest)
    assert len(digests) == 1
