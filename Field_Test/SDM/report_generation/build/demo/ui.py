"""Terminal presentation for the live demo: step headers, check marks, progress, verdict.

Only presentation lives here. On a terminal it draws live bars and panels; piped or
redirected (logs, CI), rich falls back to plain text, so the evidence files stay readable.
"""
from __future__ import annotations

import sys

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (BarColumn, MofNCompleteColumn, Progress, SpinnerColumn,
                           TaskProgressColumn, TextColumn, TimeElapsedColumn,
                           TimeRemainingColumn)
from rich.table import Table
from rich.text import Text

# Bound to the real stdout at import, so a caller can redirect sys.stdout (generate.py
# sends the bundle's own prints to the log) without the bars following it there.
console = Console(file=sys.stdout, highlight=False)


def step(n: str, title: str, subtitle: str = "") -> None:
    body = Text(title, style="bold white")
    if subtitle:
        body.append(f"\n{subtitle}", style="dim")
    console.print()
    console.print(Panel(body, title=f"[bold cyan]STEP {n}[/]", title_align="left",
                        border_style="cyan", box=box.ROUNDED, padding=(0, 2)))


def check(ok: bool, msg: str) -> bool:
    mark = "[bold green]✓[/]" if ok else "[bold red]✗[/]"
    console.print(f"  {mark} {msg}")
    return ok


def kv_table(rows, title: str | None = None) -> Table:
    t = Table(box=box.SIMPLE_HEAD, title=title, title_style="bold", show_header=False,
              padding=(0, 1))
    t.add_column(style="dim", no_wrap=True)
    t.add_column()
    for k, v in rows:
        t.add_row(k, str(v))
    return t


def progress(unit: str = "cases") -> Progress:
    return Progress(
        SpinnerColumn("dots", style="cyan"),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=None, complete_style="green", finished_style="bold green"),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TextColumn("•"), TimeElapsedColumn(),
        TextColumn("• ETA"), TimeRemainingColumn(),
        TextColumn("• {task.fields[rate]}"),
        console=console, expand=True, transient=False,
        redirect_stdout=False, redirect_stderr=False,
        # Inference advances one batch (~30 s) at a time; the default 30 s window
        # leaves the ETA blank between updates.
        speed_estimate_period=600,
    )


def verdict(passed: bool, headline: str, detail: str = "") -> None:
    word = "PASS" if passed else "FAIL"
    style = "bold white on green" if passed else "bold white on red"
    body = Text.assemble((f"  {word}  ", style), "   ", (headline, "bold"))
    if detail:
        body.append(f"\n\n{detail}", style="dim")
    console.print()
    console.print(Panel(body, border_style="green" if passed else "red",
                        box=box.HEAVY, padding=(1, 3)))
