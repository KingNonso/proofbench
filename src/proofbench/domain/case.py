"""Case and policy schemas.

These models validate *data only*. They never resolve a path, open a file, or
hash anything: that is the loader's job (AGENTS.md section 2). Keeping the split
means a malformed case fails with a field path, and a hostile case fails at a
filesystem boundary that knows what a root is.

Ownership is split deliberately so the two files cannot disagree:

* ``CaseSpec``   owns inputs, visible tests, world selection, seed, and budgets.
* ``PolicySpec`` owns roles, executable access probes, invariants, lock and
  money rules, and the capabilities a candidate migration may use.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, Field, model_validator

from proofbench.domain.base import SqlIdentifier, StrictModel

CASE_SCHEMA_VERSION = "1.0"
# Bumped to 1.1 when ambiguous read/write booleans became executable probes.
POLICY_SCHEMA_VERSION = "1.1"


def _check_relative_posix(raw: str) -> str:
    """Shape check for a declared path. Filesystem containment is the loader's job."""
    if not raw or raw.strip() != raw:
        raise ValueError("path is empty or has surrounding whitespace")
    if "\\" in raw:
        raise ValueError("path must use POSIX separators")
    if raw.startswith("/"):
        raise ValueError("path must be relative to the case root")
    if ".." in raw.split("/"):
        raise ValueError("path must not traverse upward")
    return raw


RelPath = Annotated[str, AfterValidator(_check_relative_posix)]


class WorldName(StrEnum):
    """The fixed world catalog. An agent may select from it but never extend it."""

    RLS = "rls"
    MONEY = "money"
    ROLLING = "rolling"
    INTERRUPTION = "interruption"
    ROLLBACK = "rollback"
    LOCKS = "locks"
    AUDIT = "audit"


# ---------------------------------------------------------------------------
# CaseSpec
# ---------------------------------------------------------------------------


class FixtureSpec(StrictModel):
    """The starting state a world is built from, before the candidate applies."""

    schema_paths: list[RelPath] = Field(min_length=1)
    roles_path: RelPath
    policies_path: RelPath
    fixtures_path: RelPath


class CandidateSpec(StrictModel):
    """The migration under review. Never mutated by any agent."""

    migration_path: RelPath
    rollback_path: RelPath | None = None


class WorldSelection(StrictModel):
    """Which worlds must run, and which may."""

    required: list[WorldName] = Field(min_length=1)
    optional: list[WorldName] = Field(default_factory=list)


class BudgetSpec(StrictModel):
    """Hard limits. An exhausted budget is EVIDENCE_INCOMPLETE, never a pass."""

    world_timeout_seconds: int = Field(gt=0, le=900)
    stage_timeout_seconds: int = Field(gt=0, le=900)
    max_model_tokens: int = Field(ge=0, le=1_000_000)


class CaseSpec(StrictModel):
    """One reviewable case. Evaluator labels live in a separate OracleSpec file."""

    schema_version: Literal["1.0"]
    case_id: str = Field(pattern=r"^C\d{2}$")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    fixture: FixtureSpec
    candidate: CandidateSpec
    visible_tests: list[RelPath] = Field(default_factory=list)
    policy_path: RelPath
    allowed_agent_tools: list[str] = Field(default_factory=list)
    worlds: WorldSelection
    seed: int = Field(ge=0)
    budgets: BudgetSpec


# ---------------------------------------------------------------------------
# PolicySpec
# ---------------------------------------------------------------------------


class RoleSpec(StrictModel):
    """A declared database role the worlds must exercise."""

    name: SqlIdentifier
    description: str = Field(min_length=1)
    tenant_scoped: bool


class Operation(StrEnum):
    """The SQL operation a probe performs."""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class ProbeScope(StrEnum):
    """Whether the probe targets the session's own tenant or another one."""

    OWN = "own"
    OTHER = "other"


class ProbeOutcome(StrEnum):
    """What the policy says should happen.

    Row-level security denies by *filtering*, not by raising, so a denial that
    yields zero rows and a denial that raises are different observable facts and
    must be declared separately. Collapsing them would let a migration that
    dropped a policy entirely look the same as one that kept it.
    """

    ALLOW = "allow"
    DENY_EMPTY = "deny_empty"
    DENY_ERROR = "deny_error"


ProbeValue = str | int | bool | UUID


class RlsProbeSpec(StrictModel):
    """One executable tenant-isolation probe.

    Replaces the read/write booleans of policy 1.0, which could not express what
    a denial should look like, nor which rows count as evidence.
    """

    probe_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    invariant_id: str = Field(pattern=r"^INV-[A-Z]+-\d{3}$")
    description: str = Field(min_length=1)

    role: SqlIdentifier
    table: SqlIdentifier
    operation: Operation
    scope: ProbeScope

    session_tenant: UUID
    target_tenant: UUID

    # Parameterized fragment with named placeholders, e.g. "org_id = %(target)s".
    # Never interpolated; psycopg binds the values below.
    predicate: str = Field(min_length=1)
    values: dict[str, ProbeValue] = Field(default_factory=dict)

    # Columns captured from matched rows so a finding can name real evidence.
    evidence_columns: list[SqlIdentifier] = Field(min_length=1)

    expected_outcome: ProbeOutcome
    expected_row_count: int | None = Field(default=None, ge=0)
    expected_row_keys: list[str] = Field(default_factory=list)
    expected_sqlstate: str | None = Field(default=None, pattern=r"^[0-9A-Z]{5}$")

    @model_validator(mode="after")
    def _outcome_carries_its_evidence(self) -> RlsProbeSpec:
        if self.expected_outcome is ProbeOutcome.DENY_ERROR and self.expected_sqlstate is None:
            raise ValueError("deny_error requires expected_sqlstate")
        if self.expected_outcome is not ProbeOutcome.DENY_ERROR and self.expected_sqlstate:
            raise ValueError("expected_sqlstate is only meaningful for deny_error")
        if self.expected_outcome is ProbeOutcome.DENY_EMPTY and self.expected_row_count not in (
            None,
            0,
        ):
            raise ValueError("deny_empty implies zero rows")
        if self.expected_outcome is ProbeOutcome.ALLOW and (
            self.expected_row_count is None and not self.expected_row_keys
        ):
            raise ValueError("allow requires expected_row_count or expected_row_keys")
        if self.scope is ProbeScope.OWN and self.session_tenant != self.target_tenant:
            raise ValueError("scope 'own' requires session_tenant == target_tenant")
        if self.scope is ProbeScope.OTHER and self.session_tenant == self.target_tenant:
            raise ValueError("scope 'other' requires a different target_tenant")
        return self

    @model_validator(mode="after")
    def _values_are_exact(self) -> RlsProbeSpec:
        # Floats have no place in evidence, and a float bound into a predicate
        # would make a probe non-reproducible across platforms.
        for key, value in self.values.items():
            if isinstance(value, float):
                raise ValueError(f"value {key!r} must not be a float")
        return self


class InvariantPolicy(StrictModel):
    """A named invariant and whether failing it blocks."""

    id: str = Field(pattern=r"^INV-[A-Z]+-\d{3}$")
    description: str = Field(min_length=1)
    blocking: bool


class LockPolicy(StrictModel):
    """The lock budget.

    ``budget_ms`` configures a session ``lock_timeout``, so PostgreSQL itself
    produces the verdict as SQLSTATE 55P03. Measured wall time is evidence, never
    the decision input (AGENTS.md section 3).
    """

    budget_ms: int = Field(gt=0, le=60_000)
    disallowed_modes: list[str] = Field(default_factory=list)


class MoneyPolicy(StrictModel):
    """Money handling rules. Floating point conversion is not configurable."""

    minor_units_only: Literal[True] = True
    allow_float_conversion: Literal[False] = False


class MigrationCapabilities(StrictModel):
    """What a candidate migration is permitted to do.

    Defaults deny. These are asserted against a restricted migration role, so a
    candidate that tries anything here fails at the database, not at a lint rule.
    """

    allow_create_role: bool = False
    allow_alter_system: bool = False
    allow_create_tablespace: bool = False
    allow_copy_program: bool = False
    allow_untrusted_languages: bool = False
    allowed_extensions: list[str] = Field(default_factory=list)


class PolicySpec(StrictModel):
    """The team policy a candidate is judged against."""

    schema_version: Literal["1.1"]
    policy_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    roles: list[RoleSpec] = Field(min_length=1)
    rls_probes: list[RlsProbeSpec] = Field(min_length=1)
    invariants: list[InvariantPolicy] = Field(min_length=1)
    lock: LockPolicy
    money: MoneyPolicy = Field(default_factory=MoneyPolicy)
    migration_capabilities: MigrationCapabilities = Field(default_factory=MigrationCapabilities)
