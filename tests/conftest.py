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
