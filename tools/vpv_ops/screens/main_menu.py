"""Main menu screen — category sidebar + operation list."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, OptionList, Static, ListView, ListItem
from textual.widgets.option_list import Option

from vpv_ops.models.registry import (
    get_categories,
    get_operations_by_category,
    Operation,
)
from vpv_ops.screens.operation import OperationScreen


class OperationItem(ListItem):
    """A list item that carries an Operation reference."""

    def __init__(self, operation: Operation) -> None:
        super().__init__()
        self.operation = operation

    def compose(self):
        badges: list[str] = []
        for c in self.operation.connections:
            tag = "MySQL" if c == "mysql" else "PG"
            color = "yellow" if c == "mysql" else "cyan"
            badges.append(f"[{color}]{tag}[/{color}]")
        if self.operation.destructive:
            badges.append("[red]✗[/red]")
        else:
            badges.append("[green]✓[/green]")

        badge_str = " ".join(badges)
        yield Static(f"  {badge_str}  [bold]{self.operation.name}[/bold]")
        yield Static(f"      [dim]{self.operation.description}[/dim]")


class MainMenuScreen(Screen):
    """Two-pane menu: categories on the left, operations on the right."""

    BINDINGS = [
        ("q", "quit", "Salir"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        categories = get_categories()
        cat_options = [Option(cat) for cat in categories]

        yield OptionList(*cat_options, id="category-list")
        yield ListView(id="operation-list")

        yield Footer()

    def on_mount(self) -> None:
        """Select first category on mount."""
        cat_list = self.query_one("#category-list", OptionList)
        if cat_list.option_count > 0:
            cat_list.highlighted = 0
            self._update_operations(get_categories()[0])

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "category-list":
            category = str(event.option.prompt)
            self._update_operations(category)

    def _update_operations(self, category: str) -> None:
        """Refresh the operation list for the selected category."""
        list_view = self.query_one("#operation-list", ListView)
        list_view.clear()
        for op in get_operations_by_category(category):
            list_view.append(OperationItem(op))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, OperationItem):
            self.app.push_screen(OperationScreen(event.item.operation))

    def action_quit(self) -> None:
        self.app.exit()
