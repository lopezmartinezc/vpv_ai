"""Operation detail screen — parameters, execution, and log output."""

from __future__ import annotations

import subprocess

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static, Input, Checkbox, RichLog, Header, Footer

from vpv_ops.executor import build_command
from vpv_ops.models.registry import Operation
from vpv_ops.screens.confirm import ConfirmScreen


class OperationScreen(Screen):
    """Shows operation details, parameter inputs, and execution log."""

    BINDINGS = [
        ("escape", "go_back", "Volver"),
        ("f5", "run_op", "Ejecutar"),
    ]

    def on_key(self, event: Key) -> None:
        if event.key == "f5":
            event.prevent_default()
            self._run()
        elif event.key in ("escape", "ctrl+q"):
            event.prevent_default()
            self.app.pop_screen()

    def __init__(self, operation: Operation) -> None:
        super().__init__()
        self.operation = operation

    def compose(self) -> ComposeResult:
        op = self.operation
        yield Header()

        with Vertical(id="op-header"):
            yield Static(f"[bold]{op.name}[/bold]")
            yield Static(op.description)

        badges: list[str] = []
        for conn in op.connections:
            cls = "badge-mysql" if conn == "mysql" else "badge-pg"
            badges.append(f"[{cls}]{conn.upper()}[/{cls}]")
        if op.destructive:
            badges.append("[badge-destructive]DESTRUCTIVA[/badge-destructive]")
        else:
            badges.append("[badge-safe]SEGURA[/badge-safe]")

        with Horizontal(id="op-badges"):
            yield Static("  ".join(badges) if badges else "")

        with Vertical(id="params-container"):
            for param in op.parameters:
                placeholder = f"{param.label}"
                if param.default:
                    placeholder += f" (default: {param.default})"
                if not param.required:
                    placeholder += " [opcional]"
                yield Input(
                    placeholder=placeholder,
                    value=param.default,
                    id=f"param-{param.name}",
                )

            if op.dry_run_flag:
                if op.dry_run_flag == "--apply":
                    yield Checkbox("Dry-run (no aplicar cambios)", value=True, id="chk-dry-run")
                else:
                    yield Checkbox("Dry-run", value=False, id="chk-dry-run")

        yield RichLog(id="log-panel", highlight=True, markup=True, wrap=True)

        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log-panel", RichLog)
        log.write("[yellow]F5 = ejecutar | escape/ctrl+q = volver[/yellow]")

    def _get_args(self) -> dict[str, str]:
        args: dict[str, str] = {}
        for param in self.operation.parameters:
            widget = self.query_one(f"#param-{param.name}", Input)
            if widget.value.strip():
                args[param.name] = widget.value.strip()
        return args

    def _get_dry_run(self) -> bool:
        try:
            chk = self.query_one("#chk-dry-run", Checkbox)
            return chk.value
        except Exception:
            return False

    def _on_confirm(self, confirmed: bool) -> None:
        if confirmed:
            self._execute()

    def _execute(self) -> None:
        log = self.query_one("#log-panel", RichLog)
        log.clear()

        args = self._get_args()
        dry_run = self._get_dry_run()
        op = self.operation
        cmd = build_command(op, args, dry_run)

        log.write(f"$ {' '.join(cmd)}")
        log.write(f"  cwd: {op.abs_cwd}")
        log.write("")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=op.abs_cwd,
                env=op.resolved_env,
                timeout=300,
            )
            output = result.stdout + result.stderr
            for line in output.splitlines():
                log.write(line)

            log.write("")
            if result.returncode == 0:
                log.write("[green]Completado exitosamente[/green]")
            else:
                log.write(f"[red]Error: código de salida {result.returncode}[/red]")

        except subprocess.TimeoutExpired:
            log.write("[red]Error: timeout (5 min)[/red]")
        except FileNotFoundError as exc:
            log.write(f"[red]Error: comando no encontrado — {exc}[/red]")
        except PermissionError as exc:
            log.write(f"[red]Error: permiso denegado — {exc}[/red]")

    def _run(self) -> None:
        dry_run = self._get_dry_run()
        if self.operation.destructive and not dry_run:
            self.app.push_screen(
                ConfirmScreen(self.operation.name, self.operation.description),
                callback=self._on_confirm,
            )
        else:
            self._execute()
