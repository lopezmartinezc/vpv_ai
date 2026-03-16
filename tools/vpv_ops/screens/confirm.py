"""Confirmation modal for destructive operations."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Button


class ConfirmScreen(ModalScreen[bool]):
    """Modal that asks for confirmation before running a destructive operation."""

    def __init__(self, operation_name: str, description: str) -> None:
        super().__init__()
        self.operation_name = operation_name
        self.op_description = description

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static(f"[bold red]⚠ Operación destructiva[/bold red]")
            yield Static(f"[bold]{self.operation_name}[/bold]")
            yield Static(self.op_description)
            yield Static("")
            yield Static("¿Estás seguro de que quieres continuar?")
            with Horizontal(id="confirm-buttons"):
                yield Button("Confirmar", variant="error", id="btn-confirm")
                yield Button("Cancelar", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-confirm")
