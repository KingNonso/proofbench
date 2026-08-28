"""Pinned environment constants.

Every value here is part of the reproducibility contract (PRD-NFR-003) and is
recorded into each run's environment.json.
"""

from __future__ import annotations

from typing import Final

# Pinned by OCI *index* digest so it resolves on both arm64 and amd64. The
# resolved per-platform image id is recorded per run, not pinned here.
# Kept identical to compose.yaml and the Makefile; a unit test asserts that.
POSTGRES_IMAGE: Final = (
    "postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94"
)

PYTHON_VERSION: Final = "3.12"

# Intake limits. A case file is configuration, not a data feed.
MAX_YAML_BYTES: Final = 1 << 20  # 1 MiB
MAX_INPUT_BYTES: Final = 8 << 20  # 8 MiB per declared input file

# The evaluator-only subtree. Product code must never resolve a path inside it.
ORACLE_DIR_NAME: Final = "evaluator_only"

# Determinism.
TIMEZONE: Final = "UTC"
