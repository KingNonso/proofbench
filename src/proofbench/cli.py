"""ProofBench command line interface.

Only implemented commands are registered. A judge-facing CLI that advertises a
command which exits "not implemented" is worse than one that is honestly small
(AGENTS.md section 5). Commands are added as their slice lands.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from proofbench import __version__
from proofbench.errors import ExitCode, ProofBenchError
from proofbench.intake.loader import load_case

app = typer.Typer(
    name="proofbench",
    help="Migration Court: the pre-merge trial for AI-written database migrations.",
    add_completion=False,
)
case_app = typer.Typer(help="Inspect and validate case definitions.", no_args_is_help=True)
app.add_typer(case_app, name="case")


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


def main() -> None:
    """Entry point that turns typed errors into stable exit codes."""
    try:
        app()
    except ProofBenchError as exc:
        typer.secho(exc.render(), fg=typer.colors.RED, err=True)
        raise SystemExit(exc.exit_code) from exc


if __name__ == "__main__":
    main()
