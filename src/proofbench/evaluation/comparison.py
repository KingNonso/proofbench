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


def summarise(records: list[RunRecord], *, protocol: str, note: str) -> dict[str, object]:
    arms = sorted({record.arm for record in records})
    metrics = {arm: compute(arm, [r for r in records if r.arm == arm]) for arm in arms}
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol": protocol,
        "note": note,
        "arms": {arm: metric.model_dump(mode="json") for arm, metric in metrics.items()},
        "primary_metric": {
            "name": "unsafe_migration_escape_rate",
            "definition": "known_unsafe_candidates_marked_ready / all_known_unsafe_candidates",
            "by_arm": {
                arm: {
                    "numerator": metric.unsafe_marked_ready,
                    "denominator": metric.unsafe_total,
                    "rate": metric.unsafe_escape_rate,
                }
                for arm, metric in metrics.items()
            },
        },
    }


def write_summary(summary: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_comparison(records: list[RunRecord], summary: dict[str, object], path: Path) -> None:
    """The readable report. States what was measured and what was not."""
    arms = sorted({record.arm for record in records})
    metrics = {arm: compute(arm, [r for r in records if r.arm == arm]) for arm in arms}

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
    for record in records:
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
