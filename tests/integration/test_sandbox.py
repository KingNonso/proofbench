"""The sandbox is the substrate every finding rests on. If its isolation
contract is wrong, every world above it is measuring something else."""

import psycopg
import pytest

from proofbench.errors import EvidenceIncompleteError
from proofbench.sandbox import docker
from proofbench.sandbox.postgres import APPLICATION_ROLES, BASE_DATABASE, MIGRATION_ROLE

pytestmark = pytest.mark.integration


def test_roles_connect_as_themselves_not_via_set_role(sandbox):
    # SET ROLE is not a boundary: RESET ROLE restores the connection-time
    # identity, so anything inside such a session could step back up to admin.
    for role in APPLICATION_ROLES:
        with sandbox.connect(BASE_DATABASE, user=role) as conn:
            observed = conn.execute("SELECT current_user, session_user").fetchone()
        assert observed == (role, role)


def test_reset_role_cannot_escalate(sandbox):
    with sandbox.connect(BASE_DATABASE, user=MIGRATION_ROLE) as conn:
        conn.execute("RESET ROLE")
        assert conn.execute("SELECT session_user").fetchone()[0] == MIGRATION_ROLE
        assert conn.execute("SELECT current_setting('is_superuser')").fetchone()[0] == "off"


def test_migration_role_holds_no_escalation_attribute(sandbox):
    with sandbox.connect(BASE_DATABASE) as conn:
        row = conn.execute(
            """
            SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls
            FROM pg_roles WHERE rolname = %s
            """,
            (MIGRATION_ROLE,),
        ).fetchone()
    assert row == (False, False, False, False, False)


def test_published_port_is_loopback_only(sandbox):
    bindings = docker.port_bindings(sandbox.container)
    assert "127.0.0.1" in bindings
    assert "0.0.0.0" not in bindings  # noqa: S104 - asserting the absence of a wildcard bind


def test_network_is_dedicated_to_this_run(sandbox):
    # Not --internal: on Docker 27.4 that silently drops the published port and
    # the host cannot reach the database at all. See create_network.
    assert not docker.network_is_internal(sandbox.network)
    assert sandbox.network.startswith("proofbench-net-")


def test_resolved_image_id_is_platform_specific(sandbox):
    # The pinned digest is a multi-architecture index, so the id it resolves to
    # is what makes an environment record reproducible in fact.
    assert sandbox.resolved_image is not None
    assert sandbox.resolved_image.startswith("sha256:")


def test_clone_produces_an_independent_database(sandbox):
    first = sandbox.clone("iso-a")
    second = sandbox.clone("iso-b")
    assert first != second

    with sandbox.connect(first) as conn:
        conn.execute("DELETE FROM audit_events")
        conn.commit()
        assert conn.execute("SELECT count(*) FROM audit_events").fetchone()[0] == 0

    with sandbox.connect(second) as conn:
        assert conn.execute("SELECT count(*) FROM audit_events").fetchone()[0] == 4


def test_clone_refuses_while_a_session_is_attached_to_the_template(sandbox):
    # Not retried: a retry loop here would be waiting on a connection leak we
    # would rather see reported.
    with sandbox.connect(BASE_DATABASE) as holder:
        holder.execute("SELECT 1")
        with pytest.raises(EvidenceIncompleteError, match="could not clone"):
            sandbox.clone("blocked-clone")


def test_cluster_fingerprint_is_stable_across_clones(sandbox):
    before = sandbox.cluster_fingerprint()
    sandbox.clone("fingerprint-check")
    sandbox.assert_cluster_unchanged(stage="test")
    assert sandbox.cluster_fingerprint() == before


def test_cluster_fingerprint_drift_is_detected(sandbox):
    original = sandbox._cluster_fingerprint  # noqa: SLF001
    try:
        sandbox._cluster_fingerprint = "0" * 64  # noqa: SLF001
        with pytest.raises(EvidenceIncompleteError, match="cluster roles or settings changed"):
            sandbox.assert_cluster_unchanged(stage="test")
    finally:
        sandbox._cluster_fingerprint = original  # noqa: SLF001


def test_base_fixture_enforces_tenant_isolation(sandbox):
    # The known-passing half. Without it, a world that always failed would look
    # like a world that detects things.
    database = sandbox.clone("base-isolation")
    with sandbox.connect(database, user="aidledger_app") as conn:
        conn.execute("SET LOCAL aidledger.org_id = '11111111-1111-4111-8111-111111111111'")
        own = conn.execute(
            "SELECT count(*) FROM payments WHERE org_id = '11111111-1111-4111-8111-111111111111'"
        ).fetchone()[0]
        other = conn.execute(
            "SELECT count(*) FROM payments WHERE org_id = '22222222-2222-4222-8222-222222222222'"
        ).fetchone()[0]
    assert (own, other) == (3, 0)


def test_unknown_container_reports_a_docker_failure():
    with pytest.raises(EvidenceIncompleteError, match="docker command failed"):
        docker.published_port("proofbench-does-not-exist")


def test_a_wrong_password_is_refused(sandbox):
    dsn = sandbox.dsn(BASE_DATABASE, user=MIGRATION_ROLE).replace(
        sandbox.credentials.role_passwords[MIGRATION_ROLE], "not-the-password"
    )
    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(dsn)
