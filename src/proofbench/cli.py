"""ProofBench command line interface.

Only implemented commands are registered. A judge-facing CLI that advertises a
command which exits "not implemented" is worse than one that is honestly small
(AGENTS.md section 5). Commands are added as their slice lands.

None of these commands calls a model. ``review`` and ``replay`` both run to
completion with no provider variable set, which is what the judge path depends on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from proofbench import __version__
from proofbench.certificate.replay import load_manifest, verify_bundle
from proofbench.certificate.replay import replay as replay_bundle
from proofbench.domain.decision import ExternalState
from proofbench.errors import ExitCode, ProofBenchError
from proofbench.intake.loader import load_case
from proofbench.tracing.validator import validate_trace
from proofbench.workflow.authority import load_ruling
from proofbench.workflow.review import load_certificate, review_case

app = typer.Typer(
    name="proofbench",
    help="Migration Court: the pre-merge trial for AI-written database migrations.",
    add_completion=False,
)
case_app = typer.Typer(help="Inspect and validate case definitions.", no_args_is_help=True)
trace_app = typer.Typer(help="Inspect run trajectories.", no_args_is_help=True)
certificate_app = typer.Typer(help="Inspect Migration Change Certificates.", no_args_is_help=True)
app.add_typer(case_app, name="case")
app.add_typer(trace_app, name="trace")
app.add_typer(certificate_app, name="certificate")

DEFAULT_RUNS_ROOT = Path("runs")


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: Annotated[bool, typer.Option("--version", help="Print the version and exit.")] = False,
) -> None:
    """ProofBench Migration Court."""
    if version:
        typer.echo(__version__)
        raise typer.Exit(ExitCode.OK)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(ExitCode.OK)


@case_app.command("validate")
def case_validate(
    case_path: Annotated[
        Path,
        typer.Argument(help="Path to a case.yaml file.", show_default=False),
    ],
) -> None:
    """Validate a case file, contain every path it declares, and freeze its inputs.

    Prints the frozen input digest, which is the value that changes when any
    candidate, policy, fixture, or visible test changes.
    """
    loaded = load_case(case_path)

    typer.secho(f"valid  {loaded.case.case_id}  {loaded.case.title}", fg=typer.colors.GREEN)
    typer.echo(f"  policy         {loaded.policy.policy_id} v{loaded.policy.version}")
    typer.echo(f"  roles          {len(loaded.policy.roles)}")
    typer.echo(f"  invariants     {len(loaded.policy.invariants)}")
    typer.echo(
        "  worlds         "
        f"required={','.join(w.value for w in loaded.case.worlds.required) or '-'} "
        f"optional={','.join(w.value for w in loaded.case.worlds.optional) or '-'}"
    )
    typer.echo(f"  frozen inputs  {len(loaded.inputs)}")
    for item in loaded.inputs:
        typer.echo(f"    {item.sha256[:12]}  {item.bytes:>8}  {item.declared_path}")
    typer.echo(f"  inputs digest  {loaded.inputs_digest}")


@app.command("review")
def review(
    case_path: Annotated[
        Path, typer.Argument(help="Path to a case.yaml file.", show_default=False)
    ],
    runs_root: Annotated[
        Path, typer.Option("--runs-root", help="Where to write the run bundle.")
    ] = DEFAULT_RUNS_ROOT,
    agents: Annotated[
        bool,
        typer.Option(
            "--agents/--no-agents",
            help="Run the three agents. Off leaves the deterministic path unchanged.",
        ),
    ] = True,
    remediate: Annotated[
        bool,
        typer.Option("--remediate/--no-remediate", help="Attempt a bounded correction."),
    ] = True,
    remediation_attempts: Annotated[
        int,
        typer.Option(
            "--remediation-attempts",
            min=1,
            max=5,
            help="Bounded correction budget (PRD-FR-042). The demo default is one.",
        ),
    ] = 1,
    ruling_path: Annotated[
        Path | None,
        typer.Option("--ruling", help="A recorded domain ruling to apply to this run."),
    ] = None,
) -> None:
    """Review a candidate migration and write its Migration Change Certificate.

    Uses the recorded fake provider, so it makes no network call. The decision
    comes from deterministic checks; the exit code reflects the product state, so
    a blocked candidate fails the command.
    """
    ruling = load_ruling(ruling_path) if ruling_path is not None else None
    cert, run_dir = review_case(
        case_path,
        runs_root=runs_root,
        use_agents=agents,
        remediation_attempts=remediation_attempts if remediate else 0,
        ruling=ruling,
    )
    state = cert.first_screen.external_state

    colour = {
        ExternalState.READY_FOR_REVIEW.value: typer.colors.GREEN,
        ExternalState.BLOCKED.value: typer.colors.RED,
        ExternalState.DOMAIN_RULING_REQUIRED.value: typer.colors.YELLOW,
        ExternalState.EVIDENCE_INCOMPLETE.value: typer.colors.MAGENTA,
    }[state]

    typer.secho(f"{state}  {cert.case_id}  {cert.case_title}", fg=colour, bold=True)
    typer.echo(f"  decisive invariant  {cert.first_screen.decisive_invariant}")
    for item in cert.first_screen.confirmed_blast_radius:
        typer.echo(
            f"  confirmed           {item.role} {item.operation} "
            f"{item.rows_affected} row(s) of tenant {item.affected_tenant}"
        )
    if cert.correction is not None:
        verified = "verified by clean rerun" if cert.correction.verified else "did not verify"
        typer.echo(
            f"  correction          addresses "
            f"{', '.join(cert.correction.addresses_invariants)}, {verified}"
        )
    typer.echo(f"  next action         {cert.first_screen.required_action}")
    typer.echo(f"  bundle              {run_dir}")
    # The certificate's own replay_command is portable from inside the bundle;
    # this hint must work from where the user is actually standing.
    typer.echo(f"  replay              uv run proofbench replay {run_dir / 'certificate.json'}")

    if state == ExternalState.DOMAIN_RULING_REQUIRED.value:
        typer.echo(f"  ruling packet       {run_dir}/ruling-packet.md")
    if state != ExternalState.READY_FOR_REVIEW.value:
        raise typer.Exit(
            ExitCode.EVIDENCE_INCOMPLETE
            if state == ExternalState.EVIDENCE_INCOMPLETE.value
            else ExitCode.VALIDATION
        )


@app.command("replay")
def replay(
    certificate_path: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, help="Path to a certificate.json.", show_default=False
        ),
    ],
    benchmark_root: Annotated[
        Path | None,
        typer.Option("--benchmark-root", help="Benchmark root the inputs are resolved against."),
    ] = None,
) -> None:
    """Re-run the deterministic evidence behind a certificate and compare.

    Never calls a model. Exits non-zero on any mismatch.
    """
    root = benchmark_root or Path("benchmark/aidledger")
    report = replay_bundle(certificate_path, benchmark_root=root)

    for step in report.steps:
        mark = "PASS" if step.ok else "FAIL"
        colour = typer.colors.GREEN if step.ok else typer.colors.RED
        typer.secho(f"[{mark}] {step.name}", fg=colour)
        if step.detail:
            typer.echo(f"       {step.detail}")

    log = certificate_path.resolve().parent / "replay.log"
    typer.echo(f"\nwrote {log}")
    if not report.ok:
        typer.secho("REPLAY MISMATCH", fg=typer.colors.RED, bold=True, err=True)
        raise typer.Exit(ExitCode.INTEGRITY)
    typer.secho("replay matched", fg=typer.colors.GREEN, bold=True)


@trace_app.command("validate")
def trace_validate(
    trace_path: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, help="Path to a trajectory.jsonl.", show_default=False
        ),
    ],
) -> None:
    """Verify a trajectory's hash chain, ordering, and terminal event."""
    result = validate_trace(trace_path)
    typer.echo(f"events      {result.events}")
    typer.echo(f"root hash   {result.root_hash or '(none)'}")
    if result.valid:
        typer.secho("trace is intact", fg=typer.colors.GREEN)
        return
    for problem in result.problems:
        typer.secho(f"  {problem}", fg=typer.colors.RED, err=True)
    raise typer.Exit(ExitCode.INTEGRITY)


@certificate_app.command("verify")
def certificate_verify(
    certificate_path: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, help="Path to a certificate.json.", show_default=False
        ),
    ],
) -> None:
    """Check a certificate against its bundle without running anything.

    Verification only: no database is started and no world is re-executed. Use
    `proofbench replay` for that.
    """
    cert = load_certificate(certificate_path)
    bundle = certificate_path.resolve().parent
    manifest = load_manifest(bundle)
    steps = verify_bundle(bundle, manifest)

    typer.echo(f"{cert.case_id}  {cert.first_screen.external_state}  run {cert.run_id}")
    for step in steps:
        mark = "PASS" if step.ok else "FAIL"
        typer.secho(f"[{mark}] {step.name}", fg=typer.colors.GREEN if step.ok else typer.colors.RED)
        if step.detail:
            typer.echo(f"       {step.detail}")
    if not all(step.ok for step in steps):
        raise typer.Exit(ExitCode.INTEGRITY)


def main() -> None:
    """Entry point that turns typed errors into stable exit codes."""
    try:
        app()
    except ProofBenchError as exc:
        typer.secho(exc.render(), fg=typer.colors.RED, err=True)
        raise SystemExit(exc.exit_code) from exc


if __name__ == "__main__":
    main()
