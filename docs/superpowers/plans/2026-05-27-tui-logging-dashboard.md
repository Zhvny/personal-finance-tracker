Last Updated: 29-05-2026 (14:30)

# TUI Logging Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a centralized logging dashboard in the TUI to view system logs with syntax highlighting and live updates.

**Architecture:** 
- Create a `LogPanel` widget inheriting from Textual's `RichLog` for efficient display.
- Implement a `LogScreen` to host the panel and provide a focused view.
- Integrate into the `DesktopTUI` menu system.
- Use a background timer for log tailing.

**Tech Stack:** Textual, Rich, Python.

---

### Task 1: Create LogPanel Widget

**Files:**
- Create: `apps/cli/widgets/log_panel.py`

- [ ] **Step 1: Implement LogPanel class**

```python
from __future__ import annotations
import os
from pathlib import Path
from textual.widgets import RichLog
from rich.text import Text

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

        current_size = self.log_path.stat().st_size
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
```

- [ ] **Step 2: Commit**

```bash
git add apps/cli/widgets/log_panel.py
git commit -m "feat(cli): add LogPanel widget for TUI"
```

---

### Task 2: Implement LogScreen and Integrate into TUI

**Files:**
- Modify: `apps/cli/tui.py`

- [ ] **Step 1: Import LogPanel and Screen**

```python
# Add to imports in apps/cli/tui.py
from textual.screen import Screen
from widgets.log_panel import LogPanel
```

- [ ] **Step 2: Define LogScreen class**

```python
# Add before DesktopTUI in apps/cli/tui.py
class LogScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        log_path = os.path.join("logs", "app.log")
        yield LogPanel(log_path=log_path, id="log-panel")
        yield Footer()
```

- [ ] **Step 3: Update DesktopTUI menu and handler**

```python
# In DesktopTUI.on_mount, add the row:
        for num, label, desc in [
            ("1", "INVEST",  "Portfolio Assets"),
            ("2", "EXPENSE", "Spending Tracker"),
            ("3", "INCOME",  "Earning Tracker"),
            ("4", "SCAN",    "Receipt OCR"),
            ("5", "REOPT",   "Portfolio Optimizer"),
            ("6", "LOGS",    "System Logs"), # Added
        ]:
            table.add_row(num, label, desc)

# In DesktopTUI.handle_selection, add handling for "6":
    @on(DataTable.RowSelected)
    def handle_selection(self, event: DataTable.RowSelected) -> None:
        row = self.query_one(DataTable).get_row_at(event.cursor_row)
        key = str(row[0])
        if key == "6":
            self.push_screen(LogScreen())
        elif key == "5":
            self.run_worker(self.run_portfolio_optimization())
        elif key in cli_main.DISPATCH:
            self.run_worker(self.launch_module(key))
```

- [ ] **Step 4: Verify implementation**
- Ensure `apps/cli/widgets/__init__.py` exists.
- Run `python apps/cli/tui.py` and select option 6.

- [ ] **Step 5: Commit**

```bash
git add apps/cli/tui.py
git commit -m "feat(cli): integrate logging dashboard into TUI"
```
