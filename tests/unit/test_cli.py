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
    assert "case" in result.stdout
    # A judge-facing CLI must not advertise dead paths.
    for unbuilt in ("review", "replay", "certificate", "trace"):
        assert unbuilt not in result.stdout


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


def test_version_flag_needs_no_subcommand(repo_root):
    result = run("--version", cwd=repo_root)
    assert result.returncode == ExitCode.OK
    assert result.stdout.strip() == "0.1.0"


def test_bare_invocation_prints_help(repo_root):
    result = run(cwd=repo_root)
    assert result.returncode == ExitCode.OK
    assert "Usage" in result.stdout
