"""The authority gate.

Triggered by a *typed field* on the contract, not by an agent deciding it would
like a human. An authority question is a business fact code cannot derive; if the
answer is in the repository, the agent was supposed to go and read it.

The gate also enforces the two limits that keep it from becoming approval
theatre: a ruling must be scoped and executable, and it must answer a question
that was actually asked.
"""

from __future__ import annotations

from pathlib import Path

from psycopg import sql

from proofbench.domain.contract import AuthorityQuestion, MigrationContract
from proofbench.domain.ruling import (
    AffectedRows,
    CompiledRuling,
    Interpretation,
    Ruling,
    RulingPacket,
)
from proofbench.errors import CaseValidationError
from proofbench.sandbox.postgres import PostgresSandbox

# The question this benchmark's C04 asks. Interpretations and consequences are
# case material, not agent output: a reviewer must be shown the same options
# every time, or the gate is not reproducible.
CURRENCY_QUESTION_ID = "AQ-001"
CURRENCY_INVARIANT = "INV-MONEY-002"
CURRENCY_TABLE = "payments"
CURRENCY_PREDICATE = "currency_code IS NULL"


def has_unresolved_authority(contract: MigrationContract, ruling: Ruling | None) -> bool:
    """Whether the workflow must stop and ask."""
    questions = contract.unresolved_authority()
    if not questions:
        return False
    if ruling is None:
        return True
    return not any(question.question_id == ruling.question_id for question in questions)


def build_packet(
    *,
    contract: MigrationContract,
    question: AuthorityQuestion,
    sandbox: PostgresSandbox,
    database: str,
) -> RulingPacket:
    """Measure the affected rows and assemble what the reviewer needs.

    The counts are read from the database rather than described, so the reviewer
    is ruling on the rows that exist rather than on a summary of them.
    """
    statement = sql.SQL("SELECT payment_id, org_id FROM {table} WHERE {pred} ORDER BY 1").format(
        table=sql.Identifier(CURRENCY_TABLE),
        pred=sql.SQL(CURRENCY_PREDICATE),  # noqa: S608 - fixed case predicate, not agent input
    )
    with sandbox.connect(database) as conn:
        rows = conn.execute(statement).fetchall()

    by_tenant: dict[str, int] = {}
    for _, org_id in rows:
        by_tenant[str(org_id)] = by_tenant.get(str(org_id), 0) + 1

    return RulingPacket(
        case_id=contract.case_id,
        question_id=question.question_id,
        question=question.question,
        reviewer_qualification=question.reviewer_qualification,
        affected_rows=AffectedRows(
            table=CURRENCY_TABLE,
            predicate=CURRENCY_PREDICATE,
            row_count=len(rows),
            sample_keys=[str(row[0]) for row in rows[:10]],
            by_tenant=by_tenant,
        ),
        interpretations=[
            Interpretation(
                label="All historical payments were denominated in USD",
                description=(
                    "Every payment recorded before the currency field existed was in "
                    "US dollars, so backfilling USD restores information that was "
                    "always true but never stored."
                ),
                consequence_if_wrong=(
                    "Payments made in another currency are relabelled as USD. Amounts "
                    "are unchanged, so nothing fails a constraint, and every later "
                    "reconciliation, report, and audit silently uses the wrong "
                    "currency for those rows."
                ),
            ),
            Interpretation(
                label="Currency varied by organisation and cannot be assumed",
                description=(
                    "Organisations operating in different regions recorded payments "
                    "in local currency. The absent field means unknown, not USD, and "
                    "the correct value must come from an external record."
                ),
                consequence_if_wrong=(
                    "The migration is blocked and the field stays nullable for longer "
                    "than necessary. Reporting remains incomplete until the true "
                    "currency is sourced, but nothing is misstated."
                ),
            ),
        ],
        evidence_already_checked=[
            "payments.currency_code has no default and no check constraint",
            "no audit_events row records a currency for the affected payments",
            "the currencies table lists USD, KES and JPY, so more than one was in use",
            "at least one affected organisation has other payments denominated in KES",
        ],
        affected_invariants=question.affected_invariants or [CURRENCY_INVARIANT],
        why_code_cannot_settle_this=(
            "The value was never recorded. No table, constraint, or audit event "
            "distinguishes a payment that was USD from one whose currency was simply "
            "not captured. Any answer the system produced would be a guess wearing "
            "the costume of a migration."
        ),
    )


def compile_ruling(ruling: Ruling, contract: MigrationContract) -> CompiledRuling:
    """Turn a recorded ruling into an executable constraint.

    Rejects a ruling that answers a question nobody asked, or that reaches
    outside the scope the question was about. Either would let a reviewer settle
    something they were never shown.
    """
    asked = {question.question_id for question in contract.authority_questions}
    if ruling.question_id not in asked:
        raise CaseValidationError(
            "ruling answers a question that was not asked",
            location=f"ruling {ruling.ruling_id}",
            detail={"question_id": ruling.question_id, "asked": ", ".join(sorted(asked)) or "none"},
        )
    if ruling.case_id != contract.case_id:
        raise CaseValidationError(
            "ruling is for a different case",
            detail={"ruling": ruling.case_id, "contract": contract.case_id},
        )
    if ruling.scope_table != CURRENCY_TABLE or ruling.determination_column != "currency_code":
        raise CaseValidationError(
            "ruling is out of scope for the question it answers",
            location=f"ruling {ruling.ruling_id}",
            detail={
                "scope_table": ruling.scope_table,
                "determination_column": ruling.determination_column,
            },
        )

    return CompiledRuling(
        ruling_id=ruling.ruling_id,
        invariant_id=CURRENCY_INVARIANT,
        table=ruling.scope_table,
        predicate=ruling.scope_predicate,
        column=ruling.determination_column,
        expected_value=ruling.determination_value,
        description=(
            f"Rows of {ruling.scope_table} where {ruling.scope_predicate} must have "
            f"{ruling.determination_column} = {ruling.determination_value!r}, "
            f"per ruling {ruling.ruling_id} by {ruling.reviewer_role}."
        ),
    )


def load_ruling(path: Path) -> Ruling:
    """Read a ruling file, rejecting anything that is not one."""
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise CaseValidationError("ruling file must be a mapping", location=str(path))
    return Ruling.model_validate(raw)
