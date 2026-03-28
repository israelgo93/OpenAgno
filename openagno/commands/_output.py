"""Shared output helpers for the OpenAgno CLI."""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

console = Console()


def header(message: str) -> None:
    console.print(Text(message, style="bold"))


def step_info(message: str) -> None:
    console.print(f"    {message}", markup=False)


def step_ok(message: str) -> None:
    console.print("    [green]✔[/green] ", end="")
    console.print(message, markup=False)


def step_warn(message: str) -> None:
    console.print("    [yellow]![/yellow] ", end="")
    console.print(message, markup=False)


def step_error(message: str) -> None:
    console.print("    [red]✘[/red] ", end="")
    console.print(message, markup=False)


def next_step(message: str) -> None:
    console.print("    [dim]→ Next: [/dim]", end="")
    console.print(Text(message, style="dim"))
