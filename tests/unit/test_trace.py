"""A trace is only evidence if it is intact, and only safe if it never committed
to a secret in the first place."""

import json

import pytest

from proofbench.domain.trace import EventType
from proofbench.errors import EvidenceIncompleteError
from proofbench.tracing.validator import validate_trace
from proofbench.tracing.writer import TRACE_WRITE_FAILED, TraceWriter


def write_basic(path, *, secrets=()):
    writer = TraceWriter(path, "run-1", secrets=secrets)
    writer.emit(EventType.RUN_STARTED, actor="cli", stage="ingest", summary="start")
    writer.emit(EventType.CHECK_COMPLETED, actor="world", stage="world:rls", summary="done")
    writer.emit(EventType.RUN_COMPLETED, actor="cli", stage="complete", summary="end")
    return writer


def test_a_written_trace_validates(tmp_path):
    path = tmp_path / "trajectory.jsonl"
    writer = write_basic(path)
    root = writer.close()
    result = validate_trace(path)
    assert result.valid, result.problems
    assert result.events == 3
    assert result.root_hash == root


def test_sequence_numbers_are_monotonic_from_zero(tmp_path):
    path = tmp_path / "t.jsonl"
    write_basic(path).close()
    seqs = [json.loads(line)["seq"] for line in path.read_text().splitlines()]
    assert seqs == [0, 1, 2]


def test_altering_a_payload_breaks_validation(tmp_path):
    path = tmp_path / "t.jsonl"
    write_basic(path).close()
    lines = path.read_text().splitlines()
    event = json.loads(lines[1])
    event["summary"] = "tampered"
    lines[1] = json.dumps(event, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n")

    result = validate_trace(path)
    assert not result.valid
    assert any("altered after it was hashed" in problem for problem in result.problems)


def test_removing_an_event_breaks_the_chain(tmp_path):
    path = tmp_path / "t.jsonl"
    write_basic(path).close()
    lines = path.read_text().splitlines()
    path.write_text(lines[0] + "\n" + lines[2] + "\n")

    result = validate_trace(path)
    assert not result.valid
    assert any("previous hash" in problem for problem in result.problems)


def test_truncated_final_line_is_detected(tmp_path):
    path = tmp_path / "t.jsonl"
    write_basic(path).close()
    raw = path.read_text()
    path.write_text(raw[: len(raw) - 20])

    result = validate_trace(path)
    assert not result.valid
    assert any("truncated" in problem for problem in result.problems)


def test_duplicate_sequence_is_detected(tmp_path):
    path = tmp_path / "t.jsonl"
    write_basic(path).close()
    lines = path.read_text().splitlines()
    path.write_text("\n".join([lines[0], lines[0], lines[1], lines[2]]) + "\n")

    result = validate_trace(path)
    assert not result.valid
    assert any("duplicate sequence" in problem for problem in result.problems)


def test_unsupported_schema_version_reports_itself(tmp_path):
    path = tmp_path / "t.jsonl"
    write_basic(path).close()
    lines = path.read_text().splitlines()
    event = json.loads(lines[0])
    event["schema_version"] = "9.9"
    path.write_text(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")

    result = validate_trace(path)
    assert not result.valid
    assert any("unsupported schema version" in problem for problem in result.problems)


def test_writing_after_the_terminal_event_is_refused(tmp_path):
    path = tmp_path / "t.jsonl"
    writer = write_basic(path)
    # A run that already reported its outcome must not gain new history.
    with pytest.raises(EvidenceIncompleteError, match="terminal event"):
        writer.emit(EventType.CHECK_STARTED, actor="world", stage="late")
    writer.close()


def test_events_after_the_terminal_event_fail_validation(tmp_path):
    path = tmp_path / "t.jsonl"
    writer = write_basic(path)
    writer.close()
    lines = path.read_text().splitlines()
    path.write_text("\n".join([*lines, lines[1]]) + "\n")

    result = validate_trace(path)
    assert not result.valid
    assert any("after the terminal event" in problem for problem in result.problems)


def test_missing_file_is_reported(tmp_path):
    result = validate_trace(tmp_path / "absent.jsonl")
    assert not result.valid
    assert "not found" in result.problems[0]


def test_secrets_are_redacted_before_they_are_hashed(tmp_path):
    path = tmp_path / "t.jsonl"
    writer = TraceWriter(path, "run-1", secrets=("hunter2",))
    writer.emit(
        EventType.RUN_STARTED,
        actor="cli",
        stage="ingest",
        summary="connecting with hunter2",
        payload={"password": "hunter2", "dsn": "postgresql://u:hunter2@h/db"},
    )
    writer.close()

    raw = path.read_text()
    # Order matters: hashing a secret and removing it afterwards would still
    # commit the chain to its value.
    assert "hunter2" not in raw
    assert validate_trace(path).valid


def test_write_failure_produces_a_failure_sink_and_raises(tmp_path, capsys):
    path = tmp_path / "t.jsonl"
    writer = TraceWriter(path, "run-1")

    def boom(_text):
        raise OSError("disk full")

    # Fail the trace append only. The sink must still be able to write.
    writer._handle.write = boom  # noqa: SLF001

    with pytest.raises(EvidenceIncompleteError, match="TRACE_WRITE_FAILED"):
        writer.emit(EventType.RUN_STARTED, actor="cli", stage="ingest")

    assert TRACE_WRITE_FAILED in capsys.readouterr().err
    sink = json.loads((tmp_path / "failure.json").read_text())
    assert sink["run_id"] == "run-1"
    assert sink["last_valid_seq"] == -1


def test_a_failing_failure_sink_does_not_mask_the_original_error(tmp_path, monkeypatch, capsys):
    import tempfile

    path = tmp_path / "t.jsonl"
    writer = TraceWriter(path, "run-1")

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    writer._handle.write = boom  # noqa: SLF001
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", boom)

    # The sink is a courtesy. The reportable fact is the trace failure.
    with pytest.raises(EvidenceIncompleteError, match="TRACE_WRITE_FAILED"):
        writer.emit(EventType.RUN_STARTED, actor="cli", stage="ingest")
    assert TRACE_WRITE_FAILED in capsys.readouterr().err
    assert not (tmp_path / "failure.json").exists()
