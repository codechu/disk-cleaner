"""Reusable CLI helpers (stdlib-only, extraction-ready).

This module is intentionally free of project-specific imports so it can
be lifted as-is into a future ``codechu-cli`` library. Stdlib only.

Public surface:

- :class:`Color` — ANSI palette with ``NO_COLOR`` + TTY detection
- :class:`ProgressLine` — single-line overwriting stderr progress
- :func:`banner` — single-line interactive header
- :func:`confirm` — yes/no prompt with TTY/assume-yes short-circuit
- :func:`resolve_format` — tty vs pipe default chooser
- :func:`format_examples` — argparse epilog formatter
"""

from __future__ import annotations

import os
import sys
from typing import IO


class Color:
    """ANSI color helper with ``NO_COLOR`` and TTY detection.

    Usage::

        c = Color(sys.stdout)
        c("low", "ok")   # → "\x1b[32mok\x1b[0m" if color enabled, else "ok"
    """

    PALETTE: dict[str, str] = {
        "reset": "\033[0m",
        "dim": "\033[2m",
        "bold": "\033[1m",
        "low": "\033[32m",      # green
        "medium": "\033[33m",   # yellow
        "high": "\033[31m",     # red
        "info": "\033[36m",     # cyan
    }

    def __init__(self, stream: IO[str]) -> None:
        self._stream = stream

    @property
    def enabled(self) -> bool:
        if os.environ.get("NO_COLOR"):
            return False
        isatty = getattr(self._stream, "isatty", None)
        try:
            return bool(isatty and isatty())
        except Exception:
            return False

    def __call__(self, code: str, text: str) -> str:
        if not self.enabled:
            return text
        seq = self.PALETTE.get(code)
        if seq is None:
            return text
        return f"{seq}{text}{self.PALETTE['reset']}"


class ProgressLine:
    """Single-line overwriting stderr progress with optional state.

    ``enabled`` defaults to ``stream.isatty()``. When disabled, all
    methods are no-ops so callers don't need to branch.
    """

    def __init__(self, stream: IO[str] | None = None, enabled: bool | None = None) -> None:
        self._stream = stream if stream is not None else sys.stderr
        if enabled is None:
            isatty = getattr(self._stream, "isatty", None)
            try:
                enabled = bool(isatty and isatty())
            except Exception:
                enabled = False
        self.enabled = enabled
        self._last_width = 0

    def update(self, msg: str) -> None:
        if not self.enabled:
            return
        pad = " " * max(0, self._last_width - len(msg))
        try:
            self._stream.write(f"\r{msg}{pad}")
            self._stream.flush()
        except Exception:
            return
        self._last_width = len(msg)

    def clear(self) -> None:
        if not self.enabled or self._last_width == 0:
            return
        try:
            self._stream.write("\r" + " " * self._last_width + "\r")
            self._stream.flush()
        except Exception:
            pass
        self._last_width = 0


def banner(
    title: str,
    version: str,
    *,
    mode: str | None = None,
    stream: IO[str] | None = None,
) -> None:
    """Emit a single-line banner to ``stream`` when it's a TTY."""
    if stream is None:
        stream = sys.stderr
    isatty = getattr(stream, "isatty", None)
    try:
        if not (isatty and isatty()):
            return
    except Exception:
        return
    c = Color(stream)
    parts = [c("bold", f"{title} {version}")]
    if mode:
        parts.append(c("dim", f"[{mode}]"))
    try:
        stream.write("  ".join(parts) + "\n")
        stream.flush()
    except Exception:
        pass


def confirm(
    prompt: str,
    *,
    default: bool = False,
    stream: IO[str] | None = None,
    in_stream: IO[str] | None = None,
    assume_yes: bool = False,
) -> bool:
    """Yes/no prompt.

    - ``assume_yes`` short-circuits to ``True`` without prompting.
    - When ``stream`` is not a TTY, returns ``default`` without prompting
      (no way to interact, so honor the caller's policy).
    """
    if assume_yes:
        return True
    if stream is None:
        stream = sys.stderr
    if in_stream is None:
        in_stream = sys.stdin
    isatty = getattr(stream, "isatty", None)
    try:
        is_tty = bool(isatty and isatty())
    except Exception:
        is_tty = False
    if not is_tty:
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        stream.write(prompt + suffix)
        stream.flush()
        line = in_stream.readline()
    except Exception:
        return default
    if not line:
        return default
    ans = line.strip().lower()
    if not ans:
        return default
    return ans in ("y", "yes")


def resolve_format(
    stream: IO[str],
    *,
    tty_default: str = "table",
    pipe_default: str = "json",
) -> str:
    """Pick a default output format based on whether ``stream`` is a TTY."""
    isatty = getattr(stream, "isatty", None)
    try:
        return tty_default if isatty and isatty() else pipe_default
    except Exception:
        return pipe_default


def format_examples(examples: list[tuple[str, str]]) -> str:
    """Format a list of ``(command, description)`` for argparse ``epilog``.

    Renders an aligned ``Examples:`` block. Width of the command column
    is the longest command + 2 spaces, capped at 60 to keep wrapping
    sane on narrow terminals.
    """
    if not examples:
        return ""
    longest = min(60, max(len(cmd) for cmd, _ in examples))
    lines = ["Examples:"]
    for cmd, desc in examples:
        if len(cmd) <= longest:
            lines.append(f"  {cmd.ljust(longest)}  {desc}")
        else:
            lines.append(f"  {cmd}")
            lines.append(f"  {' ' * longest}  {desc}")
    return "\n".join(lines)


__all__ = [
    "Color",
    "ProgressLine",
    "banner",
    "confirm",
    "format_examples",
    "resolve_format",
]
