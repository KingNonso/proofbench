import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = REPO_ROOT / "benchmark" / "aidledger"
C01_CASE = BENCHMARK_ROOT / "cases" / "C01" / "case.yaml"


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def benchmark_root() -> Path:
    return BENCHMARK_ROOT


@pytest.fixture
def c01_case() -> Path:
    return C01_CASE


@pytest.fixture(scope="session")
def loaded_c01():
    from proofbench.intake.loader import load_case

    return load_case(C01_CASE)


@pytest.fixture(scope="session")
def fixture_paths(loaded_c01):
    from proofbench.sandbox.postgres import FixturePaths

    case = loaded_c01.case
    return FixturePaths(
        schema=tuple(BENCHMARK_ROOT / path for path in case.fixture.schema_paths),
        roles=BENCHMARK_ROOT / case.fixture.roles_path,
        policies=BENCHMARK_ROOT / case.fixture.policies_path,
        fixtures=BENCHMARK_ROOT / case.fixture.fixtures_path,
    )


@pytest.fixture(scope="session")
def sandbox(fixture_paths):
    """One container for the session; each world gets its own cloned database.

    That is the production arrangement, not a test shortcut: cluster roles are
    bootstrapped once and are then immutable, which is exactly the isolation
    contract database-per-world depends on.
    """
    from proofbench.sandbox.postgres import PostgresSandbox

    box = PostgresSandbox(f"t{uuid.uuid4().hex[:8]}", fixture_paths)
    box.start()
    try:
        yield box
    finally:
        box.stop()
