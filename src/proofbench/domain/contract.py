"""The Migration Contract (PRD-FR-010) and the world plan (PRD-FR-011).

What the Contract Analyst produces is a *separation*, not a verdict. Facts must
cite evidence; anything uncited stays an assumption. There is deliberately no
decision field anywhere in this module: an agent that could write one would make
the deterministic decision policy advisory.

The distinction the whole product turns on lives here. An assumption the agent
could not check, that is safety-relevant, either blocks world selection or
becomes an authority question. It never quietly becomes a fact.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal

from pydantic import Field, model_validator

from proofbench.domain.base import StrictModel
from proofbench.domain.case import WorldName

CONTRACT_SCHEMA_VERSION: Final[Literal["1.0"]] = "1.0"


class Materiality(StrEnum):
    """How much an open question matters."""

    BLOCKING = "blocking"
    MATERIAL = "material"
    MINOR = "minor"


class Fact(StrictModel):
    """A statement the agent could support from allowed evidence."""

    statement: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)


class Assumption(StrictModel):
    """A statement the agent could not support.

    ``safety_relevance`` is what turns an assumption into work: a safety-relevant
    assumption with no evidence behind it is precisely the thing a reviewer is
    being asked to trust, and the product exists to stop that being implicit.
    """

    statement: str = Field(min_length=1)
    safety_relevance: Materiality
    evidence_checked: list[str] = Field(default_factory=list)


class ContractInvariant(StrictModel):
    """An invariant the candidate must preserve, named by policy id."""

    id: str = Field(pattern=r"^INV-[A-Z]+-\d{3}$")
    description: str = Field(min_length=1)
    blocking_class: Materiality
    executable_check: str = Field(min_length=1)


class Unknown(StrictModel):
    """Something the agent could not determine and who would know."""

    question: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    materiality: Materiality


class AuthorityQuestion(StrictModel):
    """A business fact code cannot derive (PRD-FR-020).

    Not a general "ask a human" branch. It names the qualification the answer
    requires, so the question reaches someone entitled to answer it.
    """

    question_id: str = Field(pattern=r"^AQ-\d{3}$")
    question: str = Field(min_length=1)
    reviewer_qualification: str = Field(min_length=1)
    affected_invariants: list[str] = Field(default_factory=list)
    materiality: Materiality


class MigrationContract(StrictModel):
    """What the Contract Analyst emits. No decision field, by construction."""

    schema_version: Literal["1.0"] = CONTRACT_SCHEMA_VERSION
    case_id: str = Field(pattern=r"^C\d{2}$")
    summary: str = Field(min_length=1)
    facts: list[Fact] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    invariants: list[ContractInvariant] = Field(min_length=1)
    unknowns: list[Unknown] = Field(default_factory=list)
    authority_questions: list[AuthorityQuestion] = Field(default_factory=list)

    def unresolved_authority(self) -> list[AuthorityQuestion]:
        """Authority questions material enough to stop the workflow."""
        return [
            question
            for question in self.authority_questions
            if question.materiality in (Materiality.BLOCKING, Materiality.MATERIAL)
        ]


class WorldPlanEntry(StrictModel):
    """One selected world and why (PRD-FR-011).

    Parameters are schema-defined values, never commands. There is no field here
    that could carry shell, Docker, or arbitrary SQL, so an agent cannot smuggle
    execution through a plan.
    """

    world: WorldName
    threatened_invariants: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)
    parameters: dict[str, int | str | bool] = Field(default_factory=dict)
    expected_evidence: str = Field(min_length=1)
    timeout_seconds: int = Field(gt=0, le=900)

    @model_validator(mode="after")
    def _invariants_look_like_ids(self) -> WorldPlanEntry:
        for invariant in self.threatened_invariants:
            if not invariant.startswith("INV-"):
                raise ValueError(f"{invariant!r} is not an invariant id")
        return self


class WorldPlan(StrictModel):
    """The Test Designer's output."""

    schema_version: Literal["1.0"] = CONTRACT_SCHEMA_VERSION
    case_id: str = Field(pattern=r"^C\d{2}$")
    entries: list[WorldPlanEntry] = Field(min_length=1)
    rationale: str = Field(min_length=1)


class RemediationPlan(StrictModel):
    """The Remediation Engineer's proposal (PRD-FR-012).

    A proposal only. Whether it worked is decided by a clean rerun, never by the
    agent's own account of it, so there is no success field here either.
    """

    schema_version: Literal["1.0"] = CONTRACT_SCHEMA_VERSION
    case_id: str = Field(pattern=r"^C\d{2}$")
    addresses_invariants: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)
    corrected_sql: str = Field(min_length=1)
    regression_check: str = Field(min_length=1)
