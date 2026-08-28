import pytest
from pydantic import ValidationError

from proofbench.domain.case import CaseSpec, PolicySpec, ProbeOutcome, WorldName


def minimal_case(**overrides):
    payload = {
        "schema_version": "1.0",
        "case_id": "C01",
        "title": "t",
        "description": "d",
        "fixture": {
            "schema_paths": ["schema/001_core.sql"],
            "roles_path": "roles/001_roles.sql",
            "policies_path": "policies/001_rls.sql",
            "fixtures_path": "fixtures/001_seed.sql",
        },
        "candidate": {"migration_path": "cases/C01/candidate.sql"},
        "policy_path": "cases/C01/policy.yaml",
        "worlds": {"required": ["rls"]},
        "seed": 1,
        "budgets": {
            "world_timeout_seconds": 120,
            "stage_timeout_seconds": 180,
            "max_model_tokens": 1000,
        },
    }
    payload.update(overrides)
    return payload


def test_minimal_valid_case_is_accepted():
    case = CaseSpec.model_validate(minimal_case())
    assert case.case_id == "C01"
    assert case.worlds.required == [WorldName.RLS]


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CaseSpec.model_validate(minimal_case(expected_state="BLOCKED"))


def test_unknown_world_is_rejected():
    # An agent may select from the catalog; it may never extend it.
    with pytest.raises(ValidationError):
        CaseSpec.model_validate(minimal_case(worlds={"required": ["telepathy"]}))


def test_required_worlds_cannot_be_empty():
    with pytest.raises(ValidationError):
        CaseSpec.model_validate(minimal_case(worlds={"required": []}))


def test_bad_case_id_is_rejected():
    with pytest.raises(ValidationError):
        CaseSpec.model_validate(minimal_case(case_id="case-one"))


@pytest.mark.parametrize(
    "bad_path",
    ["/etc/passwd", "../../etc/passwd", "cases\\C01\\candidate.sql", "", "  x  "],
)
def test_path_shape_is_validated(bad_path):
    with pytest.raises(ValidationError) as caught:
        CaseSpec.model_validate(minimal_case(candidate={"migration_path": bad_path}))
    assert "candidate" in str(caught.value)


def test_missing_field_names_its_location():
    payload = minimal_case()
    del payload["policy_path"]
    with pytest.raises(ValidationError) as caught:
        CaseSpec.model_validate(payload)
    assert "policy_path" in str(caught.value)


NORTHWIND = "11111111-1111-4111-8111-111111111111"
SOUTHGATE = "22222222-2222-4222-8222-222222222222"


def minimal_probe(**overrides):
    payload = {
        "probe_id": "app-select-other",
        "invariant_id": "INV-RLS-001",
        "description": "d",
        "role": "aidledger_app",
        "table": "payments",
        "operation": "SELECT",
        "scope": "other",
        "session_tenant": NORTHWIND,
        "target_tenant": SOUTHGATE,
        "predicate": "org_id = %(target_tenant)s",
        "values": {"target_tenant": SOUTHGATE},
        "evidence_columns": ["payment_id"],
        "expected_outcome": "deny_empty",
        "expected_row_count": 0,
    }
    payload.update(overrides)
    return payload


def minimal_policy(**overrides):
    payload = {
        "schema_version": "1.1",
        "policy_id": "p",
        "version": 1,
        "roles": [{"name": "aidledger_app", "description": "d", "tenant_scoped": True}],
        "rls_probes": [minimal_probe()],
        "invariants": [{"id": "INV-RLS-001", "description": "d", "blocking": True}],
        "lock": {"budget_ms": 250},
    }
    payload.update(overrides)
    return payload


def test_minimal_valid_policy_is_accepted():
    policy = PolicySpec.model_validate(minimal_policy())
    assert policy.rls_probes[0].expected_outcome is ProbeOutcome.DENY_EMPTY


def test_policy_schema_1_0_is_rejected():
    # 1.0 declared access as read/write booleans, which could not say what a
    # denial should look like. Loading one silently would measure the wrong thing.
    with pytest.raises(ValidationError, match="schema_version"):
        PolicySpec.model_validate(minimal_policy(schema_version="1.0"))


def test_money_policy_cannot_permit_float_conversion():
    # Not a configurable trade-off: the literal type makes the unsafe value
    # unrepresentable rather than merely discouraged.
    with pytest.raises(ValidationError):
        PolicySpec.model_validate(
            minimal_policy(money={"minor_units_only": True, "allow_float_conversion": True})
        )


def test_deny_error_requires_an_expected_sqlstate():
    with pytest.raises(ValidationError, match="requires expected_sqlstate"):
        PolicySpec.model_validate(
            minimal_policy(
                rls_probes=[minimal_probe(expected_outcome="deny_error", expected_row_count=None)]
            )
        )


def test_expected_sqlstate_is_rejected_on_a_non_error_outcome():
    with pytest.raises(ValidationError, match="only meaningful for deny_error"):
        PolicySpec.model_validate(
            minimal_policy(rls_probes=[minimal_probe(expected_sqlstate="42501")])
        )


def test_allow_requires_expected_rows():
    with pytest.raises(ValidationError, match="expected_row_count or expected_row_keys"):
        PolicySpec.model_validate(
            minimal_policy(
                rls_probes=[
                    minimal_probe(
                        probe_id="app-select-own",
                        scope="own",
                        target_tenant=NORTHWIND,
                        expected_outcome="allow",
                        expected_row_count=None,
                    )
                ]
            )
        )


def test_scope_must_agree_with_the_tenants():
    with pytest.raises(ValidationError, match="requires a different target_tenant"):
        PolicySpec.model_validate(
            minimal_policy(rls_probes=[minimal_probe(target_tenant=NORTHWIND)])
        )
    with pytest.raises(ValidationError, match="session_tenant == target_tenant"):
        PolicySpec.model_validate(minimal_policy(rls_probes=[minimal_probe(scope="own")]))


def test_float_probe_value_is_rejected():
    with pytest.raises(ValidationError):
        PolicySpec.model_validate(
            minimal_policy(rls_probes=[minimal_probe(values={"amount": 12.5})])
        )


@pytest.mark.parametrize("bad", ["payments; DROP TABLE x", "Payments", "1payments", ""])
def test_sql_identifiers_are_validated_before_they_reach_psycopg(bad):
    with pytest.raises(ValidationError):
        PolicySpec.model_validate(minimal_policy(rls_probes=[minimal_probe(table=bad)]))
