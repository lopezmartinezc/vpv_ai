"""Operation detail screen — parameters, execution, and log output."""

from __future__ import annotations

import queue
import subprocess
import threading

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static, Input, Checkbox, RichLog, Header, Footer

from vpv_ops.executor import build_command
from vpv_ops.models.registry import Operation
from vpv_ops.screens.confirm import ConfirmScreen

_SENTINEL = object()


class OperationScreen(Screen):
    """Shows operation details, parameter inputs, and execution log."""

    def __init__(self, operation: Operation) -> None:
        super().__init__()
        self.operation = operation
        self._running = False
        self._queue: queue.Queue = queue.Queue()
        self._poll_timer = None
        self._thread: threading.Thread | None = None

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

    def on_key(self, event: Key) -> None:
        if event.key == "f5":
            event.prevent_default()
            self._try_run()
        elif event.key in ("escape", "ctrl+q"):
            event.prevent_default()
            if self._running:
                return
            self.app.pop_screen()

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

    def _try_run(self) -> None:
        if self._running:
            return
        dry_run = self._get_dry_run()
        if self.operation.destructive and not dry_run:
            self.app.push_screen(
                ConfirmScreen(self.operation.name, self.operation.description),
                callback=self._on_confirm,
            )
        else:
            self._execute()

    def _poll_queue(self) -> None:
        """Called by timer on the main thread — drain the queue into RichLog."""
        log = self.query_one("#log-panel", RichLog)
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is _SENTINEL:
                self._running = False
                if self._poll_timer is not None:
                    self._poll_timer.stop()
                    self._poll_timer = None
                break
            log.write(item)

    def _execute(self) -> None:
        self._running = True
        log = self.query_one("#log-panel", RichLog)
        log.clear()
        log.write("[dim]Ejecutando...[/dim]")

        args = self._get_args()
        dry_run = self._get_dry_run()
        op = self.operation
        cmd = build_command(op, args, dry_run)

        # Clear queue and start polling timer
        while not self._queue.empty():
            self._queue.get_nowait()
        self._poll_timer = self.set_interval(0.1, self._poll_queue)

        def _run_subprocess() -> None:
            q = self._queue
            q.put(f"$ {' '.join(cmd)}")
            q.put(f"  cwd: {op.abs_cwd}")
            q.put("")

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
                    q.put(line.rstrip())
                proc.wait()

                q.put("")
                if proc.returncode == 0:
                    q.put("[green]Completado exitosamente[/green]")
                else:
                    q.put(f"[red]Error: código de salida {proc.returncode}[/red]")

            except FileNotFoundError as exc:
                q.put(f"[red]Error: comando no encontrado — {exc}[/red]")
            except PermissionError as exc:
                q.put(f"[red]Error: permiso denegado — {exc}[/red]")
            finally:
                q.put(_SENTINEL)

        self._thread = threading.Thread(target=_run_subprocess, daemon=True)
        self._thread.start()
