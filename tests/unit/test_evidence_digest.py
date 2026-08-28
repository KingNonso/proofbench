"""The semantic digest decides whether a replay matched. What it ignores is as
important as what it covers."""

from datetime import UTC, datetime

from tests.unit import factories


def test_timing_does_not_change_the_digest():
    fast = factories.blocked_world(duration_ms=5)
    slow = factories.blocked_world(duration_ms=5000, ended_at=datetime(2027, 1, 1, tzinfo=UTC))
    assert fast.semantic_digest == slow.semantic_digest


def test_row_counts_do_change_the_digest():
    two = factories.blocked_world(observations=[factories.observation(rows_seen=2)])
    three = factories.blocked_world(observations=[factories.observation(rows_seen=3)])
    assert two.semantic_digest != three.semantic_digest


def test_row_keys_change_the_digest():
    a = factories.blocked_world(observations=[factories.observation(row_keys=["p1"])])
    b = factories.blocked_world(observations=[factories.observation(row_keys=["p9"])])
    assert a.semantic_digest != b.semantic_digest


def test_sqlstate_changes_the_digest():
    denied = factories.blocked_world(checks=[factories.check(sqlstate="42501")])
    other = factories.blocked_world(checks=[factories.check(sqlstate="42P01")])
    assert denied.semantic_digest != other.semantic_digest


def test_status_changes_the_digest():
    assert factories.world_result().semantic_digest != factories.blocked_world().semantic_digest


def test_digest_excludes_itself():
    result = factories.blocked_world()
    assert "semantic_digest" not in result.semantic_projection()
    assert result.with_digest().semantic_digest == result.semantic_digest
