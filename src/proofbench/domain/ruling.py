"""Human authority: the packet, the ruling, and the constraint it compiles to.

The gate exists for one narrow thing — a business fact that no amount of code or
data can settle. It is not a general "ask a human" branch, and it is emphatically
not an approval step. PRD-FR-021 puts two limits on it that this module enforces
in the type system:

**A free-form approval is not a ruling.** There is nowhere in this model to put
one. A ruling requires the rows it covers, the column it determines, the value it
determines, and a justification -- all of them, or it does not validate. That is
a structural guarantee rather than a filter on wording: "approved" is rejected
not because the text was recognised but because a signature has no scope and
determines nothing.

**A ruling cannot suppress a deterministic failure.** Nothing here can reach the
decision policy, whose precedence puts a confirmed blocking finding above any
authority question. A domain owner may settle what the data cannot say. They may
not overrule what the database demonstrated.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal

from pydantic import Field

from proofbench.domain.base import SqlIdentifier, StrictModel

RULING_SCHEMA_VERSION: Final[Literal["1.0"]] = "1.0"


class Interpretation(StrictModel):
    """One reading of an ambiguous fact, and what follows from it."""

    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    consequence_if_wrong: str = Field(min_length=1)


class AffectedRows(StrictModel):
    """Exactly which rows the question is about."""

    table: SqlIdentifier
    predicate: str = Field(min_length=1)
    row_count: int = Field(ge=0)
    sample_keys: list[str] = Field(default_factory=list)
    by_tenant: dict[str, int] = Field(default_factory=dict)


class RulingPacket(StrictModel):
    """What a qualified reviewer is shown (PRD-FR-020).

    Everything needed to rule and nothing that presumes an answer: the exact
    question, the rows it touches, the readings available, what each costs if
    wrong, and what was already checked so the reviewer is not asked to redo it.
    """

    schema_version: Literal["1.0"] = RULING_SCHEMA_VERSION
    case_id: str = Field(pattern=r"^C\d{2}$")
    question_id: str = Field(pattern=r"^AQ-\d{3}$")
    question: str = Field(min_length=1)
    reviewer_qualification: str = Field(min_length=1)
    affected_rows: AffectedRows
    interpretations: list[Interpretation] = Field(min_length=2)
    evidence_already_checked: list[str] = Field(default_factory=list)
    affected_invariants: list[str] = Field(default_factory=list)
    why_code_cannot_settle_this: str = Field(min_length=1)

    def render(self) -> str:
        """A packet a person can read without opening the JSON."""
        lines = [
            f"# Domain ruling required — {self.case_id} / {self.question_id}",
            "",
            f"**{self.question}**",
            "",
            f"Requires: {self.reviewer_qualification}",
            "",
            "## Why this cannot be settled from the data",
            "",
            self.why_code_cannot_settle_this,
            "",
            "## Affected rows",
            "",
            f"`{self.affected_rows.table}` where `{self.affected_rows.predicate}` — "
            f"{self.affected_rows.row_count} row(s)",
            "",
        ]
        for tenant, count in sorted(self.affected_rows.by_tenant.items()):
            lines.append(f"- organisation `{tenant}`: {count} row(s)")
        lines += ["", "## Interpretations", ""]
        for option in self.interpretations:
            lines += [
                f"### {option.label}",
                "",
                option.description,
                "",
                f"If this is wrong: {option.consequence_if_wrong}",
                "",
            ]
        lines += ["## Evidence already checked", ""]
        lines += [f"- {item}" for item in self.evidence_already_checked] or ["- none recorded"]
        lines += [
            "",
            "## Affected invariants",
            "",
            ", ".join(self.affected_invariants) or "none",
            "",
            "## To rule",
            "",
            "Record a scoped ruling with a determination and a justification. A",
            "free-form approval is not a ruling and will be rejected: the answer has",
            "to compile into a check. A ruling cannot override a failure the",
            "database already demonstrated.",
            "",
        ]
        return "\n".join(lines)


class Ruling(StrictModel):
    """A recorded human determination (PRD-FR-021)."""

    schema_version: Literal["1.0"] = RULING_SCHEMA_VERSION
    ruling_id: str = Field(pattern=r"^R-\d{3}$")
    case_id: str = Field(pattern=r"^C\d{2}$")
    question_id: str = Field(pattern=r"^AQ-\d{3}$")

    reviewer_role: str = Field(min_length=1)
    reviewer_qualification: str = Field(min_length=1)
    ruling_text: str = Field(min_length=20)

    # The scope and the determination are what make this executable. Without
    # them there is nothing to check, and an unverifiable ruling is a signature.
    scope_table: SqlIdentifier
    scope_predicate: str = Field(min_length=1)
    determination_column: SqlIdentifier
    determination_value: str = Field(min_length=1)

    justification: str = Field(min_length=20)
    recorded_at: datetime
    version: int = Field(ge=1)


class CompiledRuling(StrictModel):
    """The executable constraint a ruling becomes.

    The money world checks this and nothing else about the ruling. The reviewer's
    prose is preserved for the reader; only this is executed.
    """

    schema_version: Literal["1.0"] = RULING_SCHEMA_VERSION
    ruling_id: str
    invariant_id: str = Field(pattern=r"^INV-[A-Z]+-\d{3}$")
    table: SqlIdentifier
    predicate: str
    column: SqlIdentifier
    expected_value: str
    description: str
