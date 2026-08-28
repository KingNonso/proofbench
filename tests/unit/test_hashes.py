from datetime import UTC, datetime, timedelta, timezone

import pytest

from proofbench.tracing.hashes import canonical_json, digest_json, hash_file, sha256_hex


def test_key_order_does_not_change_the_digest():
    assert digest_json({"b": 1, "a": 2}) == digest_json({"a": 2, "b": 1})


def test_canonical_json_is_compact_utf8():
    assert canonical_json({"name": "Ana Lúcia", "n": 1}) == b'{"n":1,"name":"Ana L\xc3\xbacia"}'


def test_nan_and_infinity_are_rejected():
    for value in (float("nan"), float("inf")):
        with pytest.raises(ValueError):
            canonical_json({"amount": value})


def test_datetimes_normalise_to_utc():
    east = timezone(timedelta(hours=2))
    same_instant_east = datetime(2026, 8, 28, 18, 0, 0, tzinfo=east)
    same_instant_utc = datetime(2026, 8, 28, 16, 0, 0, tzinfo=UTC)
    assert digest_json({"at": same_instant_east}) == digest_json({"at": same_instant_utc})


def test_floats_are_rejected_in_safety_critical_evidence():
    # Money is integer minor units end to end. A float reaching an evidence
    # comparison is a correctness bug, not a formatting preference.
    with pytest.raises(ValueError, match="float is not permitted"):
        canonical_json({"amount_minor": 125.0}, reject_floats=True)


def test_bool_is_not_mistaken_for_a_float():
    canonical_json({"blocking": True}, reject_floats=True)


def test_nested_float_is_found():
    with pytest.raises(ValueError, match=r"\$\.rows\[1\]\.amount"):
        canonical_json({"rows": [{"amount": 1}, {"amount": 2.5}]}, reject_floats=True)


def test_hash_file_matches_sha256_of_its_bytes(tmp_path):
    target = tmp_path / "candidate.sql"
    target.write_bytes(b"SELECT 1;\n")
    assert hash_file(target) == sha256_hex(b"SELECT 1;\n")
