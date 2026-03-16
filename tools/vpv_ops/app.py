"""VPV Ops — TUI for production database operations."""

from __future__ import annotations

from pathlib import Path

from textual.app import App

from vpv_ops.screens.main_menu import MainMenuScreen

CSS_PATH = Path(__file__).parent / "css" / "app.tcss"


class VPVOpsApp(App):
    """Main application."""

    TITLE = "VPV Ops"
    SUB_TITLE = "Gestión de producción"
    CSS_PATH = CSS_PATH

    SCREENS = {
        "main": MainMenuScreen,
    }

    def on_mount(self) -> None:
        self.push_screen("main")


def main() -> None:
    app = VPVOpsApp()
    app.run()


if __name__ == "__main__":
    main()
