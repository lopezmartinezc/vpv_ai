"""Confirmation modal for destructive operations."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Static


class ConfirmScreen(ModalScreen[bool]):
    """Modal that asks for confirmation before running a destructive operation."""

    def __init__(self, operation_name: str, description: str) -> None:
        super().__init__()
        self.operation_name = operation_name
        self.op_description = description

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static("[bold red]⚠ Operación destructiva[/bold red]")
            yield Static(f"[bold]{self.operation_name}[/bold]")
            yield Static(self.op_description)
            yield Static("")
            yield Static("¿Estás seguro de que quieres continuar?")
            yield Static("[yellow]y = confirmar, n/escape = cancelar[/yellow]")

    def on_key(self, event: Key) -> None:
        if event.key == "y":
            event.prevent_default()
            self.dismiss(True)
        elif event.key in ("n", "escape"):
            event.prevent_default()
            self.dismiss(False)
