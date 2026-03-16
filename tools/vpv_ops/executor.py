"""Async subprocess executor with streaming output."""

from __future__ import annotations

import asyncio
import shlex
from collections.abc import Callable

from vpv_ops.models.registry import Operation


def build_command(op: Operation, args: dict[str, str], dry_run: bool) -> list[str]:
    """Build the command list for an operation."""
    if op.shell:
        return ["bash", "-c", op.command_template]

    # Build args string from parameters
    arg_parts: list[str] = []

    # Handle dry-run flag
    if dry_run and op.dry_run_flag:
        # Special case: --apply means "dry-run is default, --apply is destructive"
        # So when dry_run=False, we add --apply; when dry_run=True, we don't.
        if op.dry_run_flag != "--apply":
            arg_parts.append(op.dry_run_flag)
    elif not dry_run and op.dry_run_flag == "--apply":
        arg_parts.append("--apply")

    for param in op.parameters:
        value = args.get(param.name, param.default)
        if not value:
            continue
        if param.name.startswith("--"):
            arg_parts.extend([param.name, value])
        else:
            # positional
            arg_parts.append(value)

    args_str = " ".join(arg_parts)

    # Replace template placeholders
    cmd_str = op.command_template.replace("{python}", op.python).replace("{args}", args_str).strip()
    return shlex.split(cmd_str)


async def run_operation(
    op: Operation,
    args: dict[str, str],
    dry_run: bool,
    on_output: Callable[[str], None],
    on_complete: Callable[[int], None],
) -> None:
    """Execute an operation as a subprocess, streaming output line by line."""
    cmd = build_command(op, args, dry_run)

    on_output(f"$ {' '.join(cmd)}")
    on_output(f"  cwd: {op.abs_cwd}")
    on_output("")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=op.abs_cwd,
            env=op.resolved_env,
        )

        assert process.stdout is not None
        async for line in process.stdout:
            on_output(line.decode("utf-8", errors="replace").rstrip())

        return_code = await process.wait()
        on_output("")
        if return_code == 0:
            on_output("[green]Completado exitosamente[/green]")
        else:
            on_output(f"[red]Error: código de salida {return_code}[/red]")
        on_complete(return_code)

    except FileNotFoundError as exc:
        on_output(f"[red]Error: comando no encontrado — {exc}[/red]")
        on_complete(127)
    except PermissionError as exc:
        on_output(f"[red]Error: permiso denegado — {exc}[/red]")
        on_complete(126)
