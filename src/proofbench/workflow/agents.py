"""Assemble the agent stage: provider, router, and the three agents.

Kept apart from ``review`` so the deterministic path stays runnable with no
provider at all. A run with ``--no-agents`` executes exactly the same worlds and
reaches exactly the same decision; the agents add the contract, the plan, and the
correction, and they never add a verdict.
"""

from __future__ import annotations

from pathlib import Path

from proofbench.domain.case import WorldName
from proofbench.providers.base import ModelProvider
from proofbench.providers.fake import FakeProvider
from proofbench.sandbox.postgres import APPLICATION_ROLES
from proofbench.tools.router import ToolContext, ToolRouter

# Worlds with an executable implementation. All seven of the catalog are now
# executable; the check stays because a plan naming a world that cannot run
# would produce silence, and silence reads as a pass.
IMPLEMENTED_WORLDS = frozenset(WorldName)

SCHEMA_SUMMARY = """\
Tables (all amounts are integer minor units; there is no numeric or float column):
  organizations(org_id uuid pk, name text, created_at timestamptz)
  currencies(code char(3) pk, name text, minor_unit_scale smallint)
  beneficiaries(beneficiary_id uuid pk, org_id uuid fk, external_ref text, full_name text,
                created_at timestamptz)
  payments(payment_id uuid pk, org_id uuid fk, beneficiary_id uuid fk, amount_minor bigint,
           currency_code char(3) null fk, status text, created_at timestamptz)
  disbursements(disbursement_id uuid pk, org_id uuid fk, payment_id uuid fk,
                amount_minor bigint, currency_code char(3) fk, idempotency_key text,
                settled_at timestamptz, unique(org_id, idempotency_key))
  audit_events(event_id bigint identity pk, org_id uuid fk, actor_role text, action text,
               entity_type text, entity_id text, occurred_at timestamptz, payload jsonb)

Row-level security is enabled and forced on organizations, beneficiaries, payments,
disbursements and audit_events. Tenancy is carried in current_setting('aidledger.org_id').

payments.currency_code is nullable: historical rows predate the currency field.
"""


def roles_summary() -> str:
    return "Declared roles:\n" + "\n".join(f"  {role}" for role in APPLICATION_ROLES)


def build_router(
    *, benchmark_root: Path, run_dir: Path, world_catalog: str, secrets: tuple[str, ...] = ()
) -> ToolRouter:
    return ToolRouter(
        ToolContext(
            benchmark_root=benchmark_root,
            run_dir=run_dir,
            schema_summary=SCHEMA_SUMMARY,
            roles_summary=roles_summary(),
            world_catalog=world_catalog,
        ),
        secrets=secrets,
    )


def fake_provider_for(case_dir: Path) -> ModelProvider:
    """Load a case's recorded agent responses.

    Recorded, not generated: the offline judge path must produce identical agent
    artifacts on every machine, and a provider that improvised would break replay
    before it broke anything else.
    """
    fixtures = case_dir / "agent_fixtures"
    responses: dict[str, list[str]] = {}
    for agent in ("contract_analyst", "test_designer", "remediation_engineer"):
        path = fixtures / f"{agent}.json"
        if path.is_file():
            responses[agent] = [path.read_text(encoding="utf-8")]
    return FakeProvider(responses)
