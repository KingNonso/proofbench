"""PostgreSQL sandbox lifecycle.

Three properties this module exists to guarantee:

**Real identities.** Every probe connects as the actual role under its own
credentials. A superuser session with ``SET ROLE`` would not be a boundary at
all, because ``RESET ROLE`` restores the connection-time identity — anything
running in that session could simply step back up.

**A cluster tier that never moves.** Roles and server settings are cluster-wide,
and ``CREATE DATABASE ... TEMPLATE`` copies database-local state only. So roles
are created once at bootstrap and then fingerprinted; a change means a case
escaped its tier and its evidence is void.

**Disposability.** The container and network are removed in ``finally``. A
cleanup failure is recorded alongside the original failure, never instead of it.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType

import psycopg
from psycopg import sql

from proofbench.config import POSTGRES_IMAGE
from proofbench.errors import EvidenceIncompleteError
from proofbench.sandbox import docker
from proofbench.tracing.hashes import digest_json

ADMIN_ROLE = "aidledger_admin"
MIGRATION_ROLE = "aidledger_migration"
BASE_DATABASE = "aidledger_base"
MAINTENANCE_DATABASE = "postgres"

APPLICATION_ROLES = (
    MIGRATION_ROLE,
    "aidledger_app",
    "aidledger_org_admin",
    "aidledger_auditor",
    "aidledger_service",
)

READY_TIMEOUT_SECONDS = 60
CONNECT_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class FixturePaths:
    """The ordered SQL that builds the base cluster.

    Order is not cosmetic: the roles file reassigns table ownership, and the
    policy file grants to roles that must already exist.
    """

    schema: tuple[Path, ...]
    roles: Path
    policies: Path
    fixtures: Path


@dataclass
class SandboxCredentials:
    """Ephemeral, generated per run, never persisted or logged."""

    admin_password: str
    role_passwords: dict[str, str] = field(default_factory=dict)

    def secrets(self) -> tuple[str, ...]:
        return (self.admin_password, *self.role_passwords.values())


class PostgresSandbox:
    """A disposable PostgreSQL cluster for one run."""

    def __init__(self, run_id: str, fixtures: FixturePaths, *, image: str = POSTGRES_IMAGE) -> None:
        self.run_id = run_id
        self.fixtures = fixtures
        self.image = image
        self.container = f"proofbench-{run_id}"
        self.network = f"proofbench-net-{run_id}"
        self.credentials = SandboxCredentials(
            admin_password=secrets.token_urlsafe(24),
            role_passwords={role: secrets.token_urlsafe(24) for role in APPLICATION_ROLES},
        )
        self.port: int | None = None
        self.resolved_image: str | None = None
        self._started = False
        self._cluster_fingerprint: str | None = None

    # -- connection helpers -------------------------------------------------

    def dsn(self, database: str, *, user: str = ADMIN_ROLE) -> str:
        if self.port is None:
            raise EvidenceIncompleteError("sandbox is not started")
        password = (
            self.credentials.admin_password
            if user == ADMIN_ROLE
            else self.credentials.role_passwords[user]
        )
        return (
            f"host=127.0.0.1 port={self.port} dbname={database} user={user} "
            f"password={password} connect_timeout={CONNECT_TIMEOUT_SECONDS}"
        )

    def connect(
        self, database: str, *, user: str = ADMIN_ROLE, autocommit: bool = False
    ) -> psycopg.Connection[tuple[object, ...]]:
        """Open a direct connection as ``user``. Never a superuser plus SET ROLE."""
        return psycopg.connect(self.dsn(database, user=user), autocommit=autocommit)

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        docker.create_network(self.network, self.run_id)
        docker.run_detached(
            name=self.container,
            image=self.image,
            run_id=self.run_id,
            network=self.network,
            env={
                "POSTGRES_USER": ADMIN_ROLE,
                "POSTGRES_PASSWORD": self.credentials.admin_password,
                "POSTGRES_DB": BASE_DATABASE,
                # scram, not trust: a role must prove it is that role.
                "POSTGRES_HOST_AUTH_METHOD": "scram-sha-256",
                "POSTGRES_INITDB_ARGS": "--auth-host=scram-sha-256",
                "TZ": "UTC",
                "PGTZ": "UTC",
            },
        )
        self.port = docker.published_port(self.container)
        self.resolved_image = docker.resolved_image_id(self.image)
        self._started = True
        self._wait_ready()
        self._bootstrap()
        self._cluster_fingerprint = self.cluster_fingerprint()

    def _wait_ready(self) -> None:
        deadline = time.monotonic() + READY_TIMEOUT_SECONDS
        last = ""
        while time.monotonic() < deadline:
            result = docker.exec_(
                self.container, ["pg_isready", "-U", ADMIN_ROLE, "-d", BASE_DATABASE], timeout=10
            )
            if result.returncode == 0:
                # pg_isready can pass while initdb is still restarting the
                # server, so confirm with a real authenticated connection.
                try:
                    with self.connect(BASE_DATABASE) as conn:
                        conn.execute("SELECT 1")
                    return
                except psycopg.Error as exc:  # noqa: PERF203 - retry loop, not a hot path
                    last = str(exc)
            else:
                last = result.stderr.strip()
            time.sleep(0.25)
        raise EvidenceIncompleteError(
            "database did not become ready",
            detail={
                "container": self.container,
                "timeout_seconds": READY_TIMEOUT_SECONDS,
                "last_error": last[:500],
                "logs": docker.logs(self.container)[-2000:],
            },
        )

    def _bootstrap(self) -> None:
        """Build the base cluster, then set ephemeral role passwords."""
        ordered = [
            *self.fixtures.schema,
            self.fixtures.roles,
            self.fixtures.policies,
            self.fixtures.fixtures,
        ]
        with self.connect(BASE_DATABASE) as conn:
            for path in ordered:
                conn.execute(path.read_text(encoding="utf-8"))
            conn.commit()

            for role, password in sorted(self.credentials.role_passwords.items()):
                conn.execute(
                    sql.SQL("ALTER ROLE {} WITH PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(password)
                    )
                )
            # Defence in depth. PUBLIC is not granted CREATE on a database by
            # default; revoking makes that explicit and survives a fixture edit.
            conn.execute(
                sql.SQL("REVOKE CREATE ON DATABASE {} FROM PUBLIC").format(
                    sql.Identifier(BASE_DATABASE)
                )
            )
            conn.commit()

    def cluster_fingerprint(self) -> str:
        """Digest of role security attributes and a declared settings projection."""
        with self.connect(MAINTENANCE_DATABASE) as conn:
            roles = conn.execute(
                """
                SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb,
                       rolcanlogin, rolreplication, rolbypassrls
                FROM pg_roles
                WHERE rolname NOT LIKE 'pg\\_%'
                ORDER BY rolname
                """
            ).fetchall()
            settings = conn.execute(
                """
                SELECT name, setting
                FROM pg_settings
                WHERE name IN (
                    'row_security', 'timezone', 'lc_messages',
                    'default_transaction_read_only', 'session_replication_role'
                )
                ORDER BY name
                """
            ).fetchall()
        return digest_json(
            {
                "roles": [list(map(_stringify, row)) for row in roles],
                "settings": [list(map(_stringify, row)) for row in settings],
            },
            reject_floats=True,
        )

    def assert_cluster_unchanged(self, stage: str) -> None:
        """Raise if the cluster tier moved. A moved tier voids the evidence."""
        if self._cluster_fingerprint is None:
            return
        current = self.cluster_fingerprint()
        if current != self._cluster_fingerprint:
            raise EvidenceIncompleteError(
                "cluster roles or settings changed during the run",
                detail={"stage": stage, "expected": self._cluster_fingerprint, "observed": current},
            )

    def clone(self, world_id: str) -> str:
        """Clone the base database for one world.

        ``CREATE DATABASE ... TEMPLATE`` runs outside a transaction and refuses
        while any session is attached to the template. That refusal is
        EVIDENCE_INCOMPLETE and is not retried: a retry loop here would be
        waiting on a connection leak we would rather see.
        """
        name = f"w_{self.run_id}_{world_id}".lower()[:63]
        with self.connect(MAINTENANCE_DATABASE, autocommit=True) as conn:
            try:
                conn.execute(
                    sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                        sql.Identifier(name), sql.Identifier(BASE_DATABASE)
                    )
                )
            except psycopg.Error as exc:
                raise EvidenceIncompleteError(
                    "could not clone the template database",
                    detail={
                        "world": world_id,
                        "sqlstate": getattr(exc, "sqlstate", None),
                        "error": str(exc)[:500],
                    },
                ) from exc
        return name

    def apply_sql_file(self, database: str, path: Path, *, user: str) -> None:
        """Apply a SQL file as a named role."""
        with self.connect(database, user=user) as conn:
            conn.execute(path.read_text(encoding="utf-8"))
            conn.commit()

    def stop(self) -> list[str]:
        """Remove the container and network. Returns the problems it hit."""
        problems: list[str] = []
        try:
            docker.stop_and_remove(self.container)
        except EvidenceIncompleteError as exc:
            problems.append(f"container cleanup failed: {exc.message}")
        try:
            docker.remove_network(self.network)
        except EvidenceIncompleteError as exc:
            problems.append(f"network cleanup failed: {exc.message}")
        self._started = False
        return problems

    def __enter__(self) -> PostgresSandbox:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        problems = self.stop()
        if problems and exc is None:
            raise EvidenceIncompleteError("sandbox cleanup failed", detail={"problems": problems})
        if problems and exc is not None and isinstance(exc, EvidenceIncompleteError):
            # Keep both facts. A cleanup failure never replaces the failure that
            # caused it; a reviewer needs the original cause and the leak.
            exc.detail.setdefault("cleanup_problems", "; ".join(problems))


def _stringify(value: object) -> str:
    return "" if value is None else str(value)


def iter_application_roles() -> Iterator[str]:
    yield from APPLICATION_ROLES
