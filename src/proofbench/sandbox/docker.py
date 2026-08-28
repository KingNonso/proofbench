"""Audited Docker control.

A thin wrapper, not an abstraction layer. Every invocation is a fixed argument
array against the ``docker`` executable: no shell, no caller-supplied subcommand,
and a timeout on every call. A timeout raises rather than returning a default,
because a container command that silently "returned nothing" is exactly how a
sandbox failure becomes a false pass.

Containers and networks are labelled with the run id so an orphan is findable
after a crash.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from proofbench.errors import EvidenceIncompleteError

DOCKER = "docker"
RUN_LABEL = "proofbench.run_id"
DEFAULT_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class CommandOutput:
    """Result of one docker invocation."""

    args: list[str]
    returncode: int
    stdout: str
    stderr: str


def _run(args: list[str], *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> CommandOutput:
    """Run one docker command with a fixed argv."""
    full = [DOCKER, *args]
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, no caller-supplied binary
            full,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise EvidenceIncompleteError(
            "docker is not available on PATH", detail={"command": " ".join(full)}
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise EvidenceIncompleteError(
            "docker command timed out",
            detail={"command": " ".join(full), "timeout_seconds": timeout},
        ) from exc
    return CommandOutput(
        args=full, returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr
    )


def _checked(args: list[str], *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    result = _run(args, timeout=timeout)
    if result.returncode != 0:
        raise EvidenceIncompleteError(
            "docker command failed",
            detail={
                "command": " ".join(result.args),
                "returncode": result.returncode,
                "stderr": result.stderr.strip()[:2000],
            },
        )
    return result.stdout.strip()


def create_network(name: str, run_id: str) -> str:
    """Create a dedicated bridge network for one run.

    Not ``--internal``, and that is a measured decision rather than an oversight.
    On Docker 27.4 an internal network silently drops published port mappings:
    the container starts, ``NetworkSettings.Ports`` comes back empty, and the
    host cannot reach PostgreSQL at all. Verified, not assumed.

    What is kept: a dedicated network per run, so the sandbox shares no bridge
    with anything else, and a loopback-only published port, so nothing off this
    host can reach it.

    What is lost: network-level egress blocking. That was defence in depth, not
    the primary control. The untrusted artifact is SQL running inside PostgreSQL,
    and for it to reach the network at all it would need ``COPY ... FROM PROGRAM``,
    an untrusted language, or an extension such as dblink -- each of which the
    restricted migration role cannot use, and each of which has its own test in
    tests/security. See CHANGELOG.md.
    """
    return _checked(
        ["network", "create", "--driver", "bridge", "--label", f"{RUN_LABEL}={run_id}", name]
    )


def remove_network(name: str) -> None:
    _checked(["network", "rm", name])


def network_is_internal(name: str) -> bool:
    """Whether the network blocks external routing. See create_network for why
    this is False here and what replaces it."""
    out = _checked(["network", "inspect", "--format", "{{.Internal}}", name])
    return out.strip().lower() == "true"


def port_bindings(name: str) -> str:
    """Raw published port map, so a test can assert loopback-only binding."""
    return _checked(["inspect", "--format", "{{json .NetworkSettings.Ports}}", name])


def run_detached(
    *,
    name: str,
    image: str,
    run_id: str,
    network: str,
    env: dict[str, str],
    memory: str = "512m",
    cpus: str = "1.0",
    pids_limit: int = 256,
) -> str:
    """Start the database container, published to an ephemeral loopback port only."""
    args = [
        "run",
        "--detach",
        "--name",
        name,
        "--label",
        f"{RUN_LABEL}={run_id}",
        "--network",
        network,
        # Loopback only: never reachable from another host on the network.
        "--publish",
        "127.0.0.1::5432",
        "--memory",
        memory,
        "--cpus",
        cpus,
        "--pids-limit",
        str(pids_limit),
        # The data directory is disposable by construction.
        "--tmpfs",
        "/var/lib/postgresql/data:rw,size=512m",
    ]
    for key, value in sorted(env.items()):
        args += ["--env", f"{key}={value}"]
    args += [
        image,
        "postgres",
        "-c",
        "timezone=UTC",
        "-c",
        "lc_messages=C",
        "-c",
        "log_lock_waits=on",
    ]
    return _checked(args)


def published_port(name: str) -> int:
    """The host port PostgreSQL was published on."""
    out = _checked(["port", name, "5432/tcp"])
    line = out.splitlines()[0].strip() if out else ""
    _, _, port = line.rpartition(":")
    if not port.isdigit():
        raise EvidenceIncompleteError(
            "could not parse the published port from docker output",
            detail={"container": name, "output": out[:500]},
        )
    return int(port)


def resolved_image_id(image: str) -> str:
    """The platform-specific image id behind a multi-architecture index digest.

    The pinned digest is an index, so it resolves differently on arm64 and amd64.
    Recording the resolved id is what makes an environment reproducible in fact
    rather than in intention.
    """
    return _checked(["image", "inspect", "--format", "{{.Id}}", image])


def exec_(name: str, args: list[str], *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> CommandOutput:
    """Run a command inside the container. Returns the result without raising."""
    return _run(["exec", name, *args], timeout=timeout)


def logs(name: str, *, tail: int = 200) -> str:
    result = _run(["logs", "--tail", str(tail), name])
    return f"{result.stdout}\n{result.stderr}".strip()


def stop_and_remove(name: str) -> None:
    """Remove the container. Raises if it could not be removed."""
    _checked(["rm", "--force", "--volumes", name], timeout=90)


def list_labelled(kind: str, run_id: str) -> list[str]:
    """Names of containers or networks still carrying a run label."""
    out = _checked(
        [kind, "ls", "--filter", f"label={RUN_LABEL}={run_id}", "--format", "{{.Names}}"]
        if kind == "container"
        else [kind, "ls", "--filter", f"label={RUN_LABEL}={run_id}", "--format", "{{.Name}}"]
    )
    return [line.strip() for line in out.splitlines() if line.strip()]
