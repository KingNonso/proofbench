import subprocess
import sys

from proofbench.errors import ExitCode


def run(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "proofbench.cli", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_help_lists_only_implemented_commands(repo_root):
    result = run("--help", cwd=repo_root)
    assert result.returncode == ExitCode.OK
    # Every command listed here runs. A judge-facing CLI must not advertise a
    # path that exits "not implemented".
    for built in ("case", "review", "replay", "trace", "certificate"):
        assert built in result.stdout
    for unbuilt in ("evaluate", "baseline", "remediate"):
        assert unbuilt not in result.stdout


def test_certificate_verify_accepts_the_golden_bundle(repo_root):
    result = run("certificate", "verify", "tests/golden/C01/certificate.json", cwd=repo_root)
    assert result.returncode == ExitCode.OK, result.stderr
    assert "BLOCKED" in result.stdout
    assert "FAIL" not in result.stdout


def test_certificate_verify_rejects_a_tampered_bundle(repo_root, tmp_path):
    import shutil

    bundle = tmp_path / "C01"
    shutil.copytree(repo_root / "tests" / "golden" / "C01", bundle)
    (bundle / "decision.json").write_text('{"tampered": true}')

    result = run("certificate", "verify", str(bundle / "certificate.json"), cwd=repo_root)

    assert result.returncode == ExitCode.INTEGRITY
    assert "FAIL" in result.stdout


def test_trace_validate_accepts_the_golden_trace(repo_root):
    result = run("trace", "validate", "tests/golden/C01/trajectory.jsonl", cwd=repo_root)
    assert result.returncode == ExitCode.OK, result.stderr
    assert "trace is intact" in result.stdout


def test_trace_validate_rejects_a_broken_chain(repo_root, tmp_path):
    source = (repo_root / "tests" / "golden" / "C01" / "trajectory.jsonl").read_text()
    broken = tmp_path / "trajectory.jsonl"
    broken.write_text("\n".join(source.splitlines()[:1] + source.splitlines()[2:]) + "\n")

    result = run("trace", "validate", str(broken), cwd=repo_root)

    assert result.returncode == ExitCode.INTEGRITY
    assert "previous hash" in result.stderr


def test_case_validate_accepts_c01(repo_root, c01_case):
    result = run("case", "validate", str(c01_case), cwd=repo_root)
    assert result.returncode == ExitCode.OK, result.stderr
    assert "valid  C01" in result.stdout
    assert "inputs digest" in result.stdout


def test_case_validate_reports_a_missing_file_with_the_validation_exit_code(repo_root, tmp_path):
    result = run("case", "validate", str(tmp_path / "absent.yaml"), cwd=repo_root)
    assert result.returncode == ExitCode.VALIDATION
    assert "CaseValidationError" in result.stderr


def test_unknown_command_is_a_usage_error(repo_root):
    assert run("nonsense", cwd=repo_root).returncode == ExitCode.USAGE


def test_replay_of_a_missing_certificate_is_a_usage_error_not_a_traceback(repo_root, tmp_path):
    # The replay hint inside a certificate is relative to its bundle directory;
    # a judge running it from the repo root must get a located refusal, not a
    # pathlib stack trace.
    result = run("replay", str(tmp_path / "certificate.json"), cwd=repo_root)

    assert result.returncode == ExitCode.USAGE
    assert "does not exist" in result.stderr
    assert "Traceback" not in result.stderr


def test_trace_validate_of_a_missing_file_is_a_usage_error(repo_root, tmp_path):
    result = run("trace", "validate", str(tmp_path / "trajectory.jsonl"), cwd=repo_root)

    assert result.returncode == ExitCode.USAGE
    assert "Traceback" not in result.stderr


def test_certificate_verify_of_a_missing_file_is_a_usage_error(repo_root, tmp_path):
    result = run("certificate", "verify", str(tmp_path / "certificate.json"), cwd=repo_root)

    assert result.returncode == ExitCode.USAGE
    assert "Traceback" not in result.stderr


def test_certificate_without_its_manifest_is_an_integrity_error(repo_root, tmp_path):
    import shutil

    bundle = tmp_path / "C01"
    shutil.copytree(repo_root / "tests" / "golden" / "C01", bundle)
    (bundle / "manifest.json").unlink()

    result = run("certificate", "verify", str(bundle / "certificate.json"), cwd=repo_root)

    assert result.returncode == ExitCode.INTEGRITY
    assert "no manifest.json" in result.stderr
    assert "Traceback" not in result.stderr


def test_version_flag_needs_no_subcommand(repo_root):
    result = run("--version", cwd=repo_root)
    assert result.returncode == ExitCode.OK
    assert result.stdout.strip() == "0.1.0"


def test_bare_invocation_prints_help(repo_root):
    result = run(cwd=repo_root)
    assert result.returncode == ExitCode.OK
    assert "Usage" in result.stdout
