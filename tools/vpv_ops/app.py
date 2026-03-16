"""VPV Ops — CLI for production database operations."""

from __future__ import annotations

import subprocess
import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from simple_term_menu import TerminalMenu

from vpv_ops.executor import build_command
from vpv_ops.models.registry import (
    Operation,
    get_categories,
    get_operations_by_category,
)

console = Console()

# ── helpers ──────────────────────────────────────────────────────────────────


def _badge(op: Operation) -> str:
    """Return the badge prefix for an operation menu entry."""
    parts: list[str] = []
    for conn in op.connections:
        parts.append(f"[{conn.upper()}]")
    if op.destructive:
        parts.append("[DESTRUCTIVA]")
    badge = " ".join(parts)
    return f"{badge} {op.name}" if badge else op.name


def _print_header() -> None:
    console.print()
    console.print(
        Panel(
            "[bold cyan]VPV Ops[/bold cyan]  [dim]Gestión de producción[/dim]",
            expand=False,
            border_style="cyan",
        )
    )
    console.print()


def _pick(title: str, entries: list[str]) -> int | None:
    """
    Show a TerminalMenu and return the chosen index.

    Returns None if the user presses Escape / Ctrl-C (no selection).
    """
    menu = TerminalMenu(
        entries,
        title=title,
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("fg_cyan", "bold"),
    )
    idx = menu.show()
    return idx  # None when nothing selected


# ── parameter collection ──────────────────────────────────────────────────────


def _collect_args(op: Operation) -> dict[str, str] | None:
    """Prompt for each parameter.  Returns None if user cancels."""
    collected: dict[str, str] = {}
    for param in op.parameters:
        required_marker = "" if param.required else " [dim](opcional)[/dim]"
        default_hint = f" [dim][{param.default}][/dim]" if param.default else ""
        prompt_label = (
            f"  [cyan]{param.label}[/cyan]{required_marker}{default_hint}: "
        )
        console.print(prompt_label, end="")
        try:
            value = input()
        except (EOFError, KeyboardInterrupt):
            return None
        value = value.strip()
        if not value and param.default:
            value = param.default
        if not value and param.required:
            console.print(f"  [red]El parámetro '{param.label}' es obligatorio.[/red]")
            return None
        if value:
            collected[param.name] = value
    return collected


def _ask_dry_run(op: Operation) -> bool | None:
    """
    Ask whether to run in dry-run mode.

    Returns True  → dry run
            False → live run
            None  → cancel
    """
    # Special case: --apply flag means dry-run is the default behavior.
    if op.dry_run_flag == "--apply":
        label = "¿Ejecutar en modo DRY-RUN (sin --apply)?"
    else:
        label = "¿Ejecutar en modo DRY-RUN (sin cambios reales)?"

    idx = _pick(label, ["Si — dry run", "No — ejecutar real", "← Cancelar"])
    if idx is None or idx == 2:
        return None
    return idx == 0


def _ask_confirm(op: Operation) -> bool:
    """Ask the user to confirm a destructive operation.  Returns True to proceed."""
    console.print()
    console.print(
        f"  [bold red]ATENCION:[/bold red] '[bold]{op.name}[/bold]' es una operacion [red]DESTRUCTIVA[/red]."
    )
    console.print("  Esta accion puede modificar o eliminar datos en produccion.")
    console.print()
    idx = _pick("¿Confirmar ejecucion?", ["Si — ejecutar", "No — cancelar"])
    if idx is None or idx == 1:
        return False
    return True


# ── execution ─────────────────────────────────────────────────────────────────


def _run_operation(op: Operation, args: dict[str, str], dry_run: bool) -> None:
    """Build the command and stream its output to the console."""
    cmd = build_command(op, args, dry_run)

    console.print()
    console.rule("[bold cyan]Ejecutando[/bold cyan]")
    console.print(f"  [dim]$ {' '.join(cmd)}[/dim]")
    console.print(f"  [dim]  cwd: {op.abs_cwd}[/dim]")
    console.print()

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=op.abs_cwd,
            env=op.resolved_env,
        )
        assert process.stdout is not None
        for line in process.stdout:
            console.print(line.rstrip())
        return_code = process.wait()
    except FileNotFoundError as exc:
        console.print(f"[red]Error: comando no encontrado — {exc}[/red]")
        return_code = 127
    except PermissionError as exc:
        console.print(f"[red]Error: permiso denegado — {exc}[/red]")
        return_code = 126
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Interrumpido por el usuario.[/yellow]")
        return_code = 130

    console.print()
    if return_code == 0:
        console.print("[bold green]Completado exitosamente.[/bold green]")
    elif return_code == 130:
        pass  # already printed above
    else:
        console.print(f"[bold red]Error: codigo de salida {return_code}.[/bold red]")

    console.rule()
    console.print()
    try:
        input("  Pulsa Enter para continuar...")
    except (EOFError, KeyboardInterrupt):
        pass


# ── screens ───────────────────────────────────────────────────────────────────


def _operation_detail(op: Operation) -> None:
    """Show operation info, collect parameters, confirm, and execute."""
    console.print()

    # Info panel
    conn_str = ", ".join(op.connections) if op.connections else "ninguna"
    destructive_str = (
        "[red]Si[/red]" if op.destructive else "[green]No[/green]"
    )
    dry_run_str = (
        f"[yellow]{op.dry_run_flag}[/yellow]" if op.dry_run_flag else "[dim]No[/dim]"
    )
    info = Text.assemble(
        ("Descripcion: ", "bold"),
        (op.description + "\n", ""),
        ("Conexiones:  ", "bold"),
        (conn_str + "\n", "cyan"),
        ("Destructiva: ", "bold"),
    )
    console.print(Panel(info, title=f"[bold]{op.name}[/bold]", border_style="cyan"))

    # Parameters
    param_args: dict[str, str] = {}
    if op.parameters:
        console.print("  [bold]Parametros:[/bold]")
        result = _collect_args(op)
        if result is None:
            console.print("  [yellow]Cancelado.[/yellow]")
            return
        param_args = result

    # Dry-run
    dry_run = False
    if op.dry_run_flag:
        answer = _ask_dry_run(op)
        if answer is None:
            console.print("  [yellow]Cancelado.[/yellow]")
            return
        dry_run = answer

    # Confirmation for destructive non-dry-run operations
    if op.destructive and not dry_run:
        if not _ask_confirm(op):
            console.print("  [yellow]Cancelado.[/yellow]")
            return

    _run_operation(op, param_args, dry_run)


def _operations_menu(category: str) -> None:
    """Show operations for a category and dispatch to detail."""
    operations = get_operations_by_category(category)
    entries = [_badge(op) for op in operations] + ["← Volver"]

    while True:
        _print_header()
        console.print(f"  [bold]Categoria:[/bold] [cyan]{category}[/cyan]")
        console.print()

        idx = _pick("Selecciona una operacion:", entries)
        if idx is None or idx == len(operations):
            return  # back to category menu

        _operation_detail(operations[idx])


def _main_menu() -> None:
    """Show the category menu and dispatch to operations."""
    categories = get_categories()
    entries = categories + ["Salir"]

    while True:
        _print_header()
        idx = _pick("Selecciona una categoria:", entries)

        if idx is None or idx == len(categories):
            console.print("[dim]Hasta luego.[/dim]")
            console.print()
            sys.exit(0)

        _operations_menu(categories[idx])


# ── entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    try:
        _main_menu()
    except KeyboardInterrupt:
        console.print()
        console.print("[dim]Hasta luego.[/dim]")
        console.print()
        sys.exit(0)


if __name__ == "__main__":
    main()
