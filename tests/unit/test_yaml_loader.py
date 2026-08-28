import pytest

from proofbench.config import MAX_YAML_BYTES
from proofbench.errors import CaseValidationError
from proofbench.intake.yaml import load_yaml_mapping


def test_loads_a_plain_mapping():
    assert load_yaml_mapping(b"a: 1\nb: two\n", source="t.yaml") == {"a": 1, "b": "two"}


def test_duplicate_keys_are_rejected_with_a_location():
    # A safe loader silently keeps the last value. For a policy file deciding
    # blocking classes, that is a wrong decision with no error anywhere.
    with pytest.raises(CaseValidationError) as caught:
        load_yaml_mapping(b"budget_ms: 250\nbudget_ms: 90000\n", source="policy.yaml")
    assert "duplicate key" in caught.value.message
    assert caught.value.location == "line 2, column 1"


def test_aliases_are_rejected():
    document = b"base: &anchor\n  a: 1\ncopy: *anchor\n"
    with pytest.raises(CaseValidationError, match="aliases are not permitted"):
        load_yaml_mapping(document, source="t.yaml")


def test_oversized_document_is_rejected():
    with pytest.raises(CaseValidationError, match="exceeds the size limit"):
        load_yaml_mapping(b"a: " + b"x" * MAX_YAML_BYTES, source="t.yaml")


def test_non_mapping_root_is_rejected():
    with pytest.raises(CaseValidationError, match="must be a mapping"):
        load_yaml_mapping(b"- one\n- two\n", source="t.yaml")


def test_empty_document_is_rejected():
    with pytest.raises(CaseValidationError, match="is empty"):
        load_yaml_mapping(b"\n", source="t.yaml")


def test_invalid_utf8_is_rejected():
    with pytest.raises(CaseValidationError, match="not valid UTF-8"):
        load_yaml_mapping(b"a: \xff\xfe", source="t.yaml")


def test_malformed_yaml_reports_a_position():
    with pytest.raises(CaseValidationError) as caught:
        load_yaml_mapping(b"a: [1, 2\nb: 3\n", source="t.yaml")
    assert "line" in (caught.value.location or "")
