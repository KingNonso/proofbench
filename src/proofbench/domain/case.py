"""Case and policy schemas.

These models validate *data only*. They never resolve a path, open a file, or
hash anything: that is the loader's job (AGENTS.md section 2). Keeping the split
means a malformed case fails with a field path, and a hostile case fails at a
filesystem boundary that knows what a root is.

Ownership is split deliberately so the two files cannot disagree:

* ``CaseSpec``   owns inputs, visible tests, world selection, seed, and budgets.
* ``PolicySpec`` owns roles, access expectations, invariants, lock and money
  rules, and the capabilities a candidate migration may use.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"


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


class StrictModel(BaseModel):
    """Base for every persisted model: unknown fields are rejected, not ignored."""

    model_config = ConfigDict(extra="forbid", frozen=True)


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

    name: str = Field(min_length=1, max_length=63)
    description: str = Field(min_length=1)
    tenant_scoped: bool


class AccessExpectation(StrictModel):
    """One cell of the role-by-tenant access matrix.

    Both directions are declared. A world that only checks that permitted access
    still works would pass a migration that grants the world to everyone.
    """

    role: str = Field(min_length=1)
    table: str = Field(min_length=1)
    read_own: bool
    read_other: bool
    write_own: bool
    write_other: bool


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

    schema_version: Literal["1.0"]
    policy_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    roles: list[RoleSpec] = Field(min_length=1)
    tenant_access: list[AccessExpectation] = Field(min_length=1)
    invariants: list[InvariantPolicy] = Field(min_length=1)
    lock: LockPolicy
    money: MoneyPolicy = Field(default_factory=MoneyPolicy)
    migration_capabilities: MigrationCapabilities = Field(default_factory=MigrationCapabilities)
