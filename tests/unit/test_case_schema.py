import pytest
from pydantic import ValidationError

from proofbench.domain.case import CaseSpec, PolicySpec, WorldName


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


def test_money_policy_cannot_permit_float_conversion():
    # Not a configurable trade-off: the literal type makes the unsafe value
    # unrepresentable rather than merely discouraged.
    with pytest.raises(ValidationError):
        PolicySpec.model_validate(
            {
                "schema_version": "1.0",
                "policy_id": "p",
                "version": 1,
                "roles": [{"name": "r", "description": "d", "tenant_scoped": True}],
                "tenant_access": [
                    {
                        "role": "r",
                        "table": "payments",
                        "read_own": True,
                        "read_other": False,
                        "write_own": False,
                        "write_other": False,
                    }
                ],
                "invariants": [{"id": "INV-RLS-001", "description": "d", "blocking": True}],
                "lock": {"budget_ms": 250},
                "money": {"minor_units_only": True, "allow_float_conversion": True},
            }
        )
