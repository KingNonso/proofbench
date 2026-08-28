"""Case loading: validate, contain, freeze.

The pipeline is deliberately one-way:

    YAML bytes -> strict loader -> CaseSpec / PolicySpec
               -> contained path resolution -> frozen input hashes

Every file is read exactly once and hashed over the same bytes that were parsed,
so there is no window in which an input can change between being validated and
being frozen (PRD-FR-001).

Containment is rooted at the **benchmark root** — the directory holding
``manifest.yaml`` — not at the case directory, because fixtures are shared across
all twelve cases. The evaluator-only subtree lives inside that root, so the
oracle check in ``paths`` is doing real work rather than restating containment.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from proofbench.domain.case import CaseSpec, PolicySpec
from proofbench.errors import CaseValidationError
from proofbench.intake.paths import resolve_contained
from proofbench.intake.yaml import load_yaml_mapping
from proofbench.tracing.hashes import digest_json, sha256_hex


class FrozenInput(BaseModel):
    """One declared input, resolved and hashed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    declared_path: str
    sha256: str
    bytes: int


class LoadedCase(BaseModel):
    """A validated case with every declared input frozen by content hash.

    ``inputs_digest`` covers the whole frozen set, so changing any candidate,
    policy, fixture, or visible test changes the run hash (PRD-FR-001).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    case: CaseSpec
    policy: PolicySpec
    benchmark_root: Path
    inputs: list[FrozenInput]
    inputs_digest: str


BENCHMARK_MARKER = "manifest.yaml"


def find_benchmark_root(case_file: Path) -> Path:
    """Walk upward for the directory holding the frozen case manifest.

    That directory is the agent-visible root: fixtures, policies, and every case
    live under it, and nothing outside it may be resolved.
    """
    for candidate in case_file.parents:
        if (candidate / BENCHMARK_MARKER).is_file():
            return candidate
    raise CaseValidationError(
        f"no benchmark root found: no {BENCHMARK_MARKER} in any parent directory",
        location=str(case_file),
    )


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CaseValidationError(f"cannot read {path}: {exc}") from exc


def _located(exc: ValidationError, source: str) -> CaseValidationError:
    """Turn a pydantic error into a located, single-block failure."""
    problems = []
    for error in exc.errors():
        where = ".".join(str(part) for part in error["loc"]) or "<root>"
        problems.append(f"{where}: {error['msg']}")
    return CaseValidationError(
        f"{len(problems)} schema problem(s)",
        location=source,
        detail={f"problem[{i}]": text for i, text in enumerate(problems)},
    )


def load_case(case_path: Path) -> LoadedCase:
    """Validate a case file, contain every path it declares, and freeze the inputs."""
    case_file = case_path.resolve()
    if not case_file.is_file():
        raise CaseValidationError("case file does not exist", location=str(case_path))

    benchmark_root = find_benchmark_root(case_file)
    raw_case = _read(case_file)
    try:
        case = CaseSpec.model_validate(load_yaml_mapping(raw_case, source=case_file.name))
    except ValidationError as exc:
        raise _located(exc, case_file.name) from exc

    policy_file = resolve_contained(benchmark_root, case.policy_path, field="policy_path")
    raw_policy = _read(policy_file)
    try:
        policy = PolicySpec.model_validate(load_yaml_mapping(raw_policy, source=policy_file.name))
    except ValidationError as exc:
        raise _located(exc, policy_file.name) from exc

    _check_policy_agrees_with_itself(policy, source=policy_file.name)

    declared: list[tuple[str, str]] = [
        ("policy_path", case.policy_path),
        ("candidate.migration_path", case.candidate.migration_path),
        *(
            (f"fixture.schema_paths[{i}]", value)
            for i, value in enumerate(case.fixture.schema_paths)
        ),
        ("fixture.roles_path", case.fixture.roles_path),
        ("fixture.policies_path", case.fixture.policies_path),
        ("fixture.fixtures_path", case.fixture.fixtures_path),
        *((f"visible_tests[{i}]", value) for i, value in enumerate(case.visible_tests)),
    ]
    if case.candidate.rollback_path is not None:
        declared.append(("candidate.rollback_path", case.candidate.rollback_path))

    frozen: list[FrozenInput] = []
    for field, declared_path in declared:
        target = resolve_contained(benchmark_root, declared_path, field=field)
        payload = _read(target)
        frozen.append(
            FrozenInput(
                field=field,
                declared_path=declared_path,
                sha256=sha256_hex(payload),
                bytes=len(payload),
            )
        )

    digest = digest_json(
        [{"field": item.field, "sha256": item.sha256} for item in frozen],
        reject_floats=True,
    )
    return LoadedCase(
        case=case,
        policy=policy,
        benchmark_root=benchmark_root,
        inputs=frozen,
        inputs_digest=digest,
    )


def _check_policy_agrees_with_itself(policy: PolicySpec, *, source: str) -> None:
    """Cross-field checks a per-field schema cannot express.

    An access expectation naming a role that does not exist would otherwise
    silently never be tested, which is the quietest possible way for a tenant
    isolation check to pass.
    """
    declared = {role.name for role in policy.roles}
    unknown = sorted({row.role for row in policy.tenant_access} - declared)
    if unknown:
        raise CaseValidationError(
            "tenant_access references roles that are not declared",
            location=source,
            detail={"unknown_roles": ", ".join(unknown)},
        )

    counts = Counter(item.id for item in policy.invariants)
    duplicated = sorted(name for name, count in counts.items() if count > 1)
    if duplicated:
        raise CaseValidationError(
            "invariant ids must be unique",
            location=source,
            detail={"duplicated": ", ".join(duplicated)},
        )
