"""Builders for typed evidence, so tests state only what they are about."""

from datetime import UTC, datetime

from proofbench.domain.evidence import (
    AccessObservation,
    CheckResult,
    CheckStatus,
    EvidenceFailure,
    Finding,
    WorldResult,
    WorldStatus,
)

NORTHWIND = "11111111-1111-4111-8111-111111111111"
SOUTHGATE = "22222222-2222-4222-8222-222222222222"
MOMENT = datetime(2026, 8, 28, 12, 0, 0, tzinfo=UTC)


def observation(**overrides):
    payload = {
        "probe_id": "app-select-other",
        "role": "aidledger_app",
        "table": "payments",
        "operation": "SELECT",
        "scope": "other",
        "session_tenant": NORTHWIND,
        "target_tenant": SOUTHGATE,
        "permitted_by_policy": False,
        "observed_allowed": True,
        "rows_seen": 2,
        "row_keys": ["p1", "p2"],
    }
    payload.update(overrides)
    return AccessObservation(**payload)


def check(**overrides):
    payload = {
        "check_id": "rls:app-select-other",
        "command": "SELECT payment_id FROM payments WHERE org_id = %(t)s",
        "status": CheckStatus.FAILED,
        "duration_ms": 12,
    }
    payload.update(overrides)
    return CheckResult(**payload)


def finding(**overrides):
    payload = {
        "invariant_id": "INV-RLS-001",
        "blocking": True,
        "summary": "cross-tenant rows visible",
        "expected": "deny_empty",
        "observed": "2 rows",
        "check_ids": ["rls:app-select-other"],
        "observations": [observation()],
    }
    payload.update(overrides)
    return Finding(**payload)


def world_result(**overrides):
    payload = {
        "world": "rls",
        "status": WorldStatus.PASSED,
        "threatened_invariants": ["INV-RLS-001"],
        "checks": [check(status=CheckStatus.PASSED)],
        "findings": [],
        "observations": [],
        "failures": [],
        "started_at": MOMENT,
        "ended_at": MOMENT,
        "duration_ms": 10,
    }
    payload.update(overrides)
    return WorldResult(**payload).with_digest()


def blocked_world(**overrides):
    payload = {
        "status": WorldStatus.FAILED,
        "findings": [finding()],
        "observations": [observation()],
        "checks": [check()],
    }
    payload.update(overrides)
    return world_result(**payload)


def failure(**overrides):
    payload = {"stage": "world:rls", "reason": "probe hit an unexpected SQLSTATE"}
    payload.update(overrides)
    return EvidenceFailure(**payload)
