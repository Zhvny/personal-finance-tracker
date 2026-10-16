from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.widgets import RichLog


class LogPanel(RichLog):
    def __init__(self, log_path: str, **kwargs):
        super().__init__(highlight=True, markup=True, **kwargs)
        self.log_path = Path(log_path)
        self._last_size = 0

    def on_mount(self) -> None:
        self.update_logs()
        self.set_interval(1.0, self.update_logs)

    def update_logs(self) -> None:
        if not self.log_path.exists():
            return

        try:
            current_size = self.log_path.stat().st_size
        except FileNotFoundError:
            return

        if current_size < self._last_size: # Log rotated
            self._last_size = 0
            self.clear()

        if current_size > self._last_size:
            with open(self.log_path, "r") as f:
                f.seek(self._last_size)
                lines = f.readlines()
                for line in lines:
                    self.write(self._format_line(line.strip()))
                self._last_size = current_size

    def _format_line(self, line: str) -> Text:
        levels = {
            "DEBUG": "grey50",
            "INFO": "white",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold red",
        }
        text = Text(line)
        for level, style in levels.items():
            if level in line:
                text.stylize(style)
                break
        return text
