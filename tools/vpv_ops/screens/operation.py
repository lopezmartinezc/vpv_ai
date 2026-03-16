"""Operation detail screen — parameters, execution, and log output."""

from __future__ import annotations

import logging
import subprocess

logging.basicConfig(
    filename="/tmp/vpv_ops_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
)
_log = logging.getLogger("vpv_ops")

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Static, Button, Input, Checkbox, RichLog, Header, Footer
from textual.worker import Worker, get_current_worker

from vpv_ops.executor import build_command
from vpv_ops.models.registry import Operation
from vpv_ops.screens.confirm import ConfirmScreen


class OperationScreen(Screen):
    """Shows operation details, parameter inputs, and execution log."""

    BINDINGS = [
        ("escape", "go_back", "Volver"),
        ("r", "run_op", "Ejecutar"),
    ]

    class LogLine(Message):
        """Thread-safe message to append a line to the log."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class RunFinished(Message):
        """Thread-safe message indicating the run completed."""

        def __init__(self, return_code: int) -> None:
            super().__init__()
            self.return_code = return_code

    def __init__(self, operation: Operation) -> None:
        super().__init__()
        self.operation = operation
        self._running = False
        self._worker: Worker | None = None

    def compose(self) -> ComposeResult:
        op = self.operation
        yield Header()

        # Operation header
        with Vertical(id="op-header"):
            yield Static(f"[bold]{op.name}[/bold]")
            yield Static(op.description)

        # Badges
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

        # Parameters
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

            # Dry-run checkbox
            if op.dry_run_flag:
                if op.dry_run_flag == "--apply":
                    yield Checkbox("Dry-run (no aplicar cambios)", value=True, id="chk-dry-run")
                else:
                    yield Checkbox("Dry-run", value=False, id="chk-dry-run")

        # Buttons
        with Horizontal(id="buttons-bar"):
            yield Button("Ejecutar", variant="success", id="btn-run")
            yield Button("Volver", variant="default", id="btn-back")

        # Log output
        yield RichLog(id="log-panel", highlight=True, markup=True, wrap=True)

        yield Footer()

    def on_mount(self) -> None:
        """Focus the run button when screen mounts."""
        self.query_one("#btn-run", Button).focus()

    def _get_args(self) -> dict[str, str]:
        """Collect parameter values from Input widgets."""
        args: dict[str, str] = {}
        for param in self.operation.parameters:
            widget = self.query_one(f"#param-{param.name}", Input)
            if widget.value.strip():
                args[param.name] = widget.value.strip()
        return args

    def _get_dry_run(self) -> bool:
        """Check if dry-run is enabled."""
        try:
            chk = self.query_one("#chk-dry-run", Checkbox)
            return chk.value
        except Exception:
            return False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
            return

        if event.button.id == "btn-run":
            if self._running:
                return

            dry_run = self._get_dry_run()

            # If destructive and not dry-run, ask confirmation
            if self.operation.destructive and not dry_run:
                self.app.push_screen(
                    ConfirmScreen(self.operation.name, self.operation.description),
                    callback=self._on_confirm,
                )
            else:
                self._execute()

    def _on_confirm(self, confirmed: bool) -> None:
        if confirmed:
            self._execute()

    def on_operation_screen_log_line(self, message: LogLine) -> None:
        """Handle log line messages from the worker thread."""
        log = self.query_one("#log-panel", RichLog)
        log.write(message.text)

    def on_operation_screen_run_finished(self, message: RunFinished) -> None:
        """Handle run completion from the worker thread."""
        self._running = False
        btn = self.query_one("#btn-run", Button)
        btn.disabled = False
        btn.label = "Ejecutar"

    def _execute(self) -> None:
        _log.debug("_execute called for %s", self.operation.id)
        try:
            self._do_execute()
        except Exception:
            _log.exception("_execute crashed")

    def _do_execute(self) -> None:
        self._running = True
        log = self.query_one("#log-panel", RichLog)
        log.clear()
        log.write("[yellow]Iniciando...[/yellow]")
        _log.debug("wrote Iniciando to log")

        btn = self.query_one("#btn-run", Button)
        btn.disabled = True
        btn.label = "Ejecutando..."

        args = self._get_args()
        dry_run = self._get_dry_run()
        op = self.operation
        cmd = build_command(op, args, dry_run)

        def _thread_run() -> None:
            worker = get_current_worker()

            self.post_message(self.LogLine(f"$ {' '.join(cmd)}"))
            self.post_message(self.LogLine(f"  cwd: {op.abs_cwd}"))
            self.post_message(self.LogLine(""))

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=op.abs_cwd,
                    env=op.resolved_env,
                    text=True,
                    bufsize=1,
                )
                assert proc.stdout is not None
                for line in proc.stdout:
                    if worker.is_cancelled:
                        proc.kill()
                        break
                    self.post_message(self.LogLine(line.rstrip()))
                proc.wait()

                self.post_message(self.LogLine(""))
                if proc.returncode == 0:
                    self.post_message(self.LogLine("[green]Completado exitosamente[/green]"))
                else:
                    self.post_message(
                        self.LogLine(f"[red]Error: código de salida {proc.returncode}[/red]")
                    )
                self.post_message(self.RunFinished(proc.returncode))

            except FileNotFoundError as exc:
                self.post_message(self.LogLine(f"[red]Error: comando no encontrado — {exc}[/red]"))
                self.post_message(self.RunFinished(127))
            except PermissionError as exc:
                self.post_message(self.LogLine(f"[red]Error: permiso denegado — {exc}[/red]"))
                self.post_message(self.RunFinished(126))

        self._worker = self.run_worker(_thread_run, thread=True)

    def action_run_op(self) -> None:
        """Keybinding 'r' to execute the operation."""
        _log.debug("action_run_op called, _running=%s", self._running)
        if self._running:
            return
        dry_run = self._get_dry_run()
        _log.debug("dry_run=%s, destructive=%s", dry_run, self.operation.destructive)
        if self.operation.destructive and not dry_run:
            self.app.push_screen(
                ConfirmScreen(self.operation.name, self.operation.description),
                callback=self._on_confirm,
            )
        else:
            self._execute()

    def action_go_back(self) -> None:
        self.app.pop_screen()
