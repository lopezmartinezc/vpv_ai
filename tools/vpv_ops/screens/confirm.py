"""Confirmation modal for destructive operations."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class ConfirmScreen(ModalScreen[bool]):
    """Modal that asks for confirmation before running a destructive operation."""

    BINDINGS = [
        ("y", "confirm", "Confirmar"),
        ("n", "cancel", "Cancelar"),
        ("escape", "cancel", "Cancelar"),
    ]

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

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
