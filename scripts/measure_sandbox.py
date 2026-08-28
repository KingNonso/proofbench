"""Measure sandbox timings. Run explicitly; never during pytest.

Timings are environment-dependent and would make a test suite flaky and slow for
no gain. They are recorded here so the numbers in the changelog come from a real
measurement rather than an estimate.

Note on naming: these are *cached-image* starts. The image is already local, so
nothing here measures an image pull, and calling it a cold start would overstate
what was observed.

    uv run python scripts/measure_sandbox.py
"""

from __future__ import annotations

import json
import platform
import statistics
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from proofbench.config import POSTGRES_IMAGE  # noqa: E402
from proofbench.intake.loader import load_case  # noqa: E402
from proofbench.sandbox.postgres import FixturePaths, PostgresSandbox  # noqa: E402
from proofbench.worlds.runner import (  # noqa: E402
    build_targets,
    run_required_worlds,
)

SCHEMA_VERSION = "1.0"
WARM_SAMPLES = 5
OUTPUT = REPO_ROOT / "results" / "sandbox-timings.json"


def ms(started: float) -> int:
    """Integer milliseconds. Sub-millisecond precision would be noise."""
    return int((time.monotonic() - started) * 1000)


def measure() -> dict[str, object]:
    benchmark_root = REPO_ROOT / "benchmark" / "aidledger"
    loaded = load_case(benchmark_root / "cases" / "C01" / "case.yaml")
    fixtures = FixturePaths(
        schema=tuple(benchmark_root / path for path in loaded.case.fixture.schema_paths),
        roles=benchmark_root / loaded.case.fixture.roles_path,
        policies=benchmark_root / loaded.case.fixture.policies_path,
        fixtures=benchmark_root / loaded.case.fixture.fixtures_path,
    )

    starts: list[int] = []
    clone_ms: list[int] = []
    world_ms: list[int] = []
    candidate_ms: list[int] = []
    cleanup_ms: list[int] = []

    for index in range(WARM_SAMPLES + 1):
        run_id = f"m{uuid.uuid4().hex[:8]}"
        box = PostgresSandbox(run_id, fixtures)

        clock = time.monotonic()
        box.start()
        starts.append(ms(clock))

        try:
            clock = time.monotonic()
            database = box.clone(f"measure{index}")
            clone_ms.append(ms(clock))

            clock = time.monotonic()
            box.apply_sql_file(
                database,
                benchmark_root / loaded.case.candidate.migration_path,
                user="aidledger_migration",
            )
            candidate_ms.append(ms(clock))

            build_targets(box, database, list(loaded.policy.rls_probes))

            clock = time.monotonic()
            run_required_worlds(box, loaded, run_id=run_id, database_by_world={"rls": database})
            world_ms.append(ms(clock))
        finally:
            clock = time.monotonic()
            box.stop()
            cleanup_ms.append(ms(clock))

    def summarise(values: list[int]) -> dict[str, int]:
        return {
            "median_ms": int(statistics.median(values)),
            "max_ms": max(values),
            "samples": len(values),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "recorded_at": datetime.now(UTC).isoformat(),
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "image": POSTGRES_IMAGE,
            "note": "image already present locally; no pull is measured here",
        },
        "first_cached_image_start_ms": starts[0],
        "warm_container_start": summarise(starts[1:]),
        "template_clone": summarise(clone_ms),
        "candidate_apply": summarise(candidate_ms),
        "rls_world": summarise(world_ms),
        "cleanup": summarise(cleanup_ms),
    }


def main() -> int:
    payload = measure()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"\nwrote {OUTPUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
