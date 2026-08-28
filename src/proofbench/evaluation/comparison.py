"""Write the experiment's evidence files.

``summary.json`` is the only source a submission may quote a metric from
(PRD §16), so it carries numerator and denominator for every rate and never a
bare percentage.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from proofbench.evaluation.records import ArmMetrics, RunRecord, compute
from proofbench.tracing.hashes import canonical_json

RESULTS = Path("results")

CHALLENGING_CASE = "C12"

# The brief asks for one challenging case and what it revealed. What C12 revealed
# is not about the migration -- it is about the checker.
CHALLENGING_CASE_NOTE = """\
C12 is the challenging case. It is a *correct* migration that is correct in seven
independent ways at once: a metadata-only column add, nothing dropped so both
live application versions keep working, a deterministic backfill that is safe to
resume, a rollback that drops rather than restores, untouched audit history, no
amount moved, and an intact tenant boundary. Each of those is checked by a
different world, and all seven must pass.

**What it revealed was a bug in our own checker.** The lock world originally
worked by holding a conflicting lock and asserting SQLSTATE 55P03 when the
candidate statement could not acquire its own. C12 failed it. That was correct
behaviour from the world and wrong behaviour from the design: every `ALTER TABLE`
takes ACCESS EXCLUSIVE and therefore blocks behind any open reader, so the check
fired on the safe migration exactly as it fired on the reckless one. A check that
cannot distinguish them is not a check.

The fix was to stop timing and start reading a fact: a table rewrite changes the
relation's filenode and a metadata-only change does not. That distinguishes C07
from C12 exactly, and it is identical on every machine and independent of how
large the fixture happens to be.

Without a known-good case that is *hard* to get right, the lock world would have
shipped looking perfect -- it caught C07, which is what it was written for. Nine
unsafe cases can only tell you a checker fires. It takes a difficult safe case to
tell you it fires for the right reason.
"""


def write_raw_runs(records: list[RunRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(canonical_json(record.model_dump(mode="json")).decode("utf-8") + "\n")


def read_raw_runs(path: Path) -> list[RunRecord]:
    return [
        RunRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_per_case(records: list[RunRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "case_id",
        "case_class",
        "expected_state",
        "arm",
        "repeat",
        "outcome",
        "marked_ready",
        "evidence_incomplete",
        "asked_for_authority",
        "duration_ms",
        "note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in sorted(records, key=lambda r: (r.case_id, r.arm, r.repeat)):
            writer.writerow({column: getattr(record, column) for column in columns})


def repeat_stability(records: list[RunRecord]) -> dict[str, object]:
    """Whether repeated runs of the same case agreed, per arm.

    The PRD-FR-070 fallback repeats C01, C04, C08 and C12 three times. For a
    deterministic arm the repeats must be identical, and this block says whether
    they were rather than assuming it.
    """
    arms = sorted({record.arm for record in records})
    by_arm: dict[str, object] = {}
    for arm in arms:
        outcomes: dict[str, list[str]] = {}
        for record in records:
            if record.arm == arm:
                outcomes.setdefault(record.case_id, []).append(record.outcome)
        repeated = {case: sorted(runs) for case, runs in outcomes.items() if len(runs) > 1}
        disagreements = {case: runs for case, runs in repeated.items() if len(set(runs)) > 1}
        by_arm[arm] = {
            "repeated_cases": sorted(repeated),
            "repeats_per_case": {case: len(runs) for case, runs in sorted(repeated.items())},
            "all_identical": not disagreements,
            "disagreements": disagreements,
        }
    return by_arm


def summarise(
    records: list[RunRecord],
    *,
    protocol: str,
    note: str,
    clean_replay: tuple[int, int] | None = None,
) -> dict[str, object]:
    """Aggregate the experiment.

    The primary metric is computed from first-pass records only, keeping the
    unsafe denominator at nine per complete pass; the extra repeats feed the
    stability block instead of inflating a denominator that was pre-registered
    as nine.
    """
    first_pass = [record for record in records if record.repeat == 1]
    arms = sorted({record.arm for record in records})
    metrics = {arm: compute(arm, [r for r in first_pass if r.arm == arm]) for arm in arms}
    summary: dict[str, object] = {
        "schema_version": "1.1",
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol": protocol,
        "note": note,
        "records_total": len(records),
        "arms": {arm: metric.model_dump(mode="json") for arm, metric in metrics.items()},
        "primary_metric": {
            "name": "unsafe_migration_escape_rate",
            "definition": "known_unsafe_candidates_marked_ready / all_known_unsafe_candidates",
            "basis": "first pass of each arm; repeats are reported under repeat_stability",
            "by_arm": {
                arm: {
                    "numerator": metric.unsafe_marked_ready,
                    "denominator": metric.unsafe_total,
                    "rate": metric.unsafe_escape_rate,
                }
                for arm, metric in metrics.items()
            },
        },
        "repeat_stability": repeat_stability(records),
    }
    if clean_replay is not None:
        summary["clean_replay"] = {
            "numerator": clean_replay[0],
            "denominator": clean_replay[1],
            "definition": "golden certificates that reproduced offline / certificates replayed",
        }
    return summary


def write_summary(summary: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_comparison(records: list[RunRecord], summary: dict[str, object], path: Path) -> None:
    """The readable report. States what was measured and what was not."""
    arms = sorted({record.arm for record in records})
    first_pass = [record for record in records if record.repeat == 1]
    metrics = {arm: compute(arm, [r for r in first_pass if r.arm == arm]) for arm in arms}

    lines = [
        "# Paired comparison",
        "",
        f"Generated {summary['generated_at']}. Protocol: {summary['protocol']}.",
        "",
        str(summary["note"]),
        "",
        "## Primary metric and guardrails",
        "",
        "Counts before rates. A rate without its denominator says nothing.",
        "",
        "| Arm | Unsafe escape rate | Safe accepted | Authority asked | Evidence incomplete |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines += [metrics[arm].render_row(arm) for arm in arms]

    replay = summary.get("clean_replay")
    if isinstance(replay, dict):
        lines += [
            "",
            f"Clean replay rate: **{replay['numerator']}/{replay['denominator']}** golden "
            "certificates reproduced offline (`make replay`).",
        ]

    stability = summary.get("repeat_stability")
    if isinstance(stability, dict) and any(
        entry.get("repeated_cases") for entry in stability.values() if isinstance(entry, dict)
    ):
        lines += ["", "### Repeat stability", ""]
        for arm in arms:
            entry = stability.get(arm)
            if not isinstance(entry, dict) or not entry.get("repeated_cases"):
                continue
            verdict = (
                "all repeats identical"
                if entry["all_identical"]
                else f"DISAGREEMENTS: {entry['disagreements']}"
            )
            lines.append(
                f"- `{arm}`: {', '.join(entry['repeated_cases'])} ran "
                f"{max(entry['repeats_per_case'].values())}x — {verdict}"
            )
        lines += [
            "",
            "The primary metric uses the first pass only, keeping the unsafe",
            "denominator at the pre-registered nine; repeats are a stability check,",
            "not extra chances.",
        ]

    lines += [
        "",
        "`EVIDENCE_INCOMPLETE` is reported in its own column and is never counted as",
        "safe: a run that could not produce evidence has not shown a candidate to be",
        "acceptable.",
        "",
        "## Per case",
        "",
        "| Case | Class | Expected | " + " | ".join(arms) + " |",
        "| --- | --- | --- | " + " | ".join("---" for _ in arms) + " |",
    ]

    by_case: dict[str, dict[str, RunRecord]] = {}
    for record in first_pass:
        by_case.setdefault(record.case_id, {})[record.arm] = record
    for case_id in sorted(by_case):
        row = by_case[case_id]
        first = next(iter(row.values()))
        cells = [row[arm].outcome if arm in row else "—" for arm in arms]
        lines.append(
            f"| {case_id} | {first.case_class} | {first.expected_state} | "
            + " | ".join(cells)
            + " |"
        )

    challenging = [r for r in records if r.case_id == CHALLENGING_CASE]
    lines += ["", f"## The challenging case: {CHALLENGING_CASE}", ""]
    for record in sorted(challenging, key=lambda r: r.arm):
        lines.append(f"- `{record.arm}`: **{record.outcome}** (expected {record.expected_state})")
    lines += ["", CHALLENGING_CASE_NOTE]

    lines += [
        "",
        "## Cost and time",
        "",
        "| Arm | Wall time | Model calls | Input tokens | Output tokens | Est. cost USD |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in arms:
        m = metrics[arm]
        lines.append(
            f"| {arm} | {m.total_duration_ms / 1000:.1f}s | {m.total_model_calls} | "
            f"{m.total_input_tokens} | {m.total_output_tokens} | "
            f"{m.total_cost_usd_micros / 1_000_000:.4f} |"
        )
    lines += [
        "",
        "Cost is a list-price estimate from recorded token counts, not a billed",
        "figure. Human time per task is not measured here and is discussed in the",
        "changelog rather than reported as a number nobody timed.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def verify(records: list[RunRecord], summary: dict[str, object]) -> list[str]:
    """Recompute the summary from raw records and report any disagreement."""
    problems: list[str] = []
    recomputed = summarise(records, protocol=str(summary["protocol"]), note=str(summary["note"]))

    if "clean_replay" not in summary:
        problems.append("summary carries no clean replay rate (PRD-FR-072)")

    recomputed_stability = recomputed["repeat_stability"]
    recorded_stability = summary.get("repeat_stability")
    if recorded_stability != recomputed_stability:
        problems.append("repeat_stability does not recompute from the raw runs")

    for arm, values in recomputed["primary_metric"]["by_arm"].items():  # type: ignore[index]
        recorded = summary["primary_metric"]["by_arm"].get(arm)  # type: ignore[index]
        if recorded is None:
            problems.append(f"{arm}: present in raw runs but missing from summary")
        elif (recorded["numerator"], recorded["denominator"]) != (
            values["numerator"],
            values["denominator"],
        ):
            problems.append(
                f"{arm}: summary says {recorded['numerator']}/{recorded['denominator']}, "
                f"raw runs give {values['numerator']}/{values['denominator']}"
            )
    return problems


def arm_metrics(records: list[RunRecord], arm: str) -> ArmMetrics:
    return compute(arm, [r for r in records if r.arm == arm])
