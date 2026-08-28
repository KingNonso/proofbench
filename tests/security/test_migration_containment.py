"""What the migration role must not be able to do.

The candidate migration is untrusted input that runs inside PostgreSQL, so the
database is where containment has to hold. Every assertion here is on SQLSTATE,
never on message text: messages are localised and change between releases, and a
containment test that greps English is not a containment test.

42501 is insufficient_privilege. 0A000 is feature_not_supported, which is how a
server refuses some operations outright.
"""

import psycopg
import pytest

from proofbench.sandbox.postgres import BASE_DATABASE, MIGRATION_ROLE

pytestmark = [pytest.mark.security, pytest.mark.integration]

INSUFFICIENT_PRIVILEGE = "42501"


@pytest.fixture
def scratch_db(sandbox, request):
    """A fresh database per test, so a surprising success cannot pollute others."""
    return sandbox.clone(f"sec{abs(hash(request.node.name)) % 100000}")


def sqlstate_of(sandbox, database: str, statement: str) -> str | None:
    """Run one statement as the migration role in autocommit.

    Autocommit matters: ALTER SYSTEM, CREATE DATABASE, and CREATE TABLESPACE
    cannot run inside a transaction block and would fail with 25001 before the
    privilege check was ever reached. A containment test that passed on 25001
    would be asserting nothing at all.
    """
    with sandbox.connect(database, user=MIGRATION_ROLE, autocommit=True) as conn:
        try:
            conn.execute(statement)
        except psycopg.Error as exc:
            return exc.sqlstate
    return None


@pytest.mark.parametrize(
    ("label", "statement"),
    [
        ("create role", "CREATE ROLE intruder LOGIN"),
        ("alter system", "ALTER SYSTEM SET log_statement = 'none'"),
        ("create tablespace", "CREATE TABLESPACE evil LOCATION '/tmp/evil'"),
        ("copy from program", "COPY payments FROM PROGRAM 'echo hi'"),
        ("read server file", "SELECT pg_read_file('/etc/passwd')"),
        ("create database", "CREATE DATABASE sneaky"),
        ("create untrusted language", "CREATE LANGUAGE plpython3u"),
        ("install extension", "CREATE EXTENSION dblink"),
    ],
)
def test_migration_role_cannot_escalate(sandbox, scratch_db, label, statement):
    state = sqlstate_of(sandbox, scratch_db, statement)
    assert state is not None, f"{label} unexpectedly succeeded"
    # 25001 would mean the statement was refused for being in a transaction
    # block, not for lack of privilege -- that is not containment.
    assert state != "25001", f"{label} never reached the privilege check"
    assert state in {INSUFFICIENT_PRIVILEGE, "0A000", "42704", "58P01"}, (
        f"{label} failed with an unexpected SQLSTATE {state}"
    )


def test_migration_role_cannot_bypass_row_level_security(sandbox):
    database = sandbox.clone("sec-bypassrls")
    with sandbox.connect(database) as admin:
        assert admin.execute(
            "SELECT rolbypassrls FROM pg_roles WHERE rolname = %s", (MIGRATION_ROLE,)
        ).fetchone() == (False,)


def test_migration_role_cannot_grant_itself_superuser(sandbox, scratch_db):
    state = sqlstate_of(sandbox, scratch_db, f"ALTER ROLE {MIGRATION_ROLE} SUPERUSER")
    assert state == INSUFFICIENT_PRIVILEGE


def test_migration_role_is_not_a_superuser(sandbox, scratch_db):
    with sandbox.connect(scratch_db, user=MIGRATION_ROLE) as conn:
        assert conn.execute("SELECT current_setting('is_superuser')").fetchone()[0] == "off"


def test_migration_role_cannot_read_another_database(sandbox, scratch_db):
    # There is no in-database path to another database's contents without an
    # extension, and the extension itself is refused above.
    state = sqlstate_of(sandbox, scratch_db, f"SELECT dblink_connect('dbname={BASE_DATABASE}')")
    assert state is not None


def test_ordinary_migration_work_still_succeeds(sandbox, scratch_db):
    # Containment that also blocked legitimate work would make every case fail
    # for the wrong reason, which is worse than no containment at all.
    with sandbox.connect(scratch_db, user=MIGRATION_ROLE) as conn:
        conn.execute("CREATE TABLE probe_scratch (id integer PRIMARY KEY)")
        conn.execute("INSERT INTO probe_scratch VALUES (1)")
        assert conn.execute("SELECT count(*) FROM probe_scratch").fetchone()[0] == 1
        conn.rollback()
