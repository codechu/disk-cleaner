"""Tests for the stdlib-only cli_helpers module.

These tests use ``io.StringIO`` with a monkey-patched ``isatty`` to
simulate both interactive and piped streams without touching real
terminals.
"""

from __future__ import annotations

import io

import pytest

from disk_cleaner.cli_helpers import (
    Color,
    ProgressLine,
    banner,
    confirm,
    format_examples,
    resolve_format,
)


def _tty_stream(initial: str = "") -> io.StringIO:
    s = io.StringIO(initial)
    s.isatty = lambda: True  # type: ignore[assignment]
    return s


def _pipe_stream(initial: str = "") -> io.StringIO:
    s = io.StringIO(initial)
    s.isatty = lambda: False  # type: ignore[assignment]
    return s


# ---------- Color ----------


def test_color_tty_emits_ansi(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    c = Color(_tty_stream())
    assert c.enabled is True
    out = c("low", "ok")
    assert out == "\033[32mok\033[0m"


def test_color_non_tty_passthrough(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    c = Color(_pipe_stream())
    assert c.enabled is False
    assert c("high", "danger") == "danger"


def test_color_respects_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    c = Color(_tty_stream())
    assert c.enabled is False
    assert c("low", "x") == "x"


def test_color_unknown_code_passthrough(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    c = Color(_tty_stream())
    assert c("does-not-exist", "x") == "x"


# ---------- ProgressLine ----------


def test_progress_line_tty_writes_and_clears():
    s = _tty_stream()
    pl = ProgressLine(stream=s)
    assert pl.enabled is True
    pl.update("hello")
    pl.update("hi")  # shorter — should pad
    val = s.getvalue()
    assert "hello" in val
    assert "\r" in val
    pl.clear()
    assert s.getvalue().endswith("\r")


def test_progress_line_non_tty_is_noop():
    s = _pipe_stream()
    pl = ProgressLine(stream=s)
    assert pl.enabled is False
    pl.update("x")
    pl.clear()
    assert s.getvalue() == ""


def test_progress_line_enabled_override():
    s = _pipe_stream()
    pl = ProgressLine(stream=s, enabled=True)
    pl.update("forced")
    assert "forced" in s.getvalue()


# ---------- banner ----------


def test_banner_tty_emits():
    s = _tty_stream()
    banner("Disk Cleaner", "v0.1.0", mode="scan", stream=s)
    out = s.getvalue()
    assert "Disk Cleaner" in out and "v0.1.0" in out and "scan" in out


def test_banner_non_tty_silent():
    s = _pipe_stream()
    banner("Disk Cleaner", "v0.1.0", stream=s)
    assert s.getvalue() == ""


# ---------- confirm ----------


def test_confirm_assume_yes_short_circuits():
    s = _tty_stream()
    inp = io.StringIO("")
    assert confirm("ok?", default=False, stream=s, in_stream=inp, assume_yes=True) is True


def test_confirm_non_tty_returns_default():
    s = _pipe_stream()
    inp = io.StringIO("y\n")  # would normally say yes but we're not interactive
    assert confirm("ok?", default=False, stream=s, in_stream=inp) is False
    assert confirm("ok?", default=True, stream=s, in_stream=inp) is True


@pytest.mark.parametrize(
    "answer,default,expected",
    [
        ("y\n", False, True),
        ("yes\n", False, True),
        ("n\n", True, False),
        ("\n", True, True),
        ("\n", False, False),
        ("garbage\n", True, False),
    ],
)
def test_confirm_tty_reads_input(answer, default, expected):
    s = _tty_stream()
    inp = io.StringIO(answer)
    assert confirm("ok?", default=default, stream=s, in_stream=inp) is expected


# ---------- resolve_format ----------


def test_resolve_format_tty_default():
    assert resolve_format(_tty_stream()) == "table"


def test_resolve_format_pipe_default():
    assert resolve_format(_pipe_stream()) == "json"


def test_resolve_format_custom():
    assert resolve_format(_tty_stream(), tty_default="csv", pipe_default="json") == "csv"
    assert resolve_format(_pipe_stream(), tty_default="csv", pipe_default="ndjson") == "ndjson"


# ---------- format_examples ----------


def test_format_examples_empty():
    assert format_examples([]) == ""


def test_format_examples_aligned():
    out = format_examples(
        [
            ("disk-cleaner --scan", "Run a scan"),
            ("disk-cleaner --clean --dry-run", "Preview clean"),
        ]
    )
    assert out.startswith("Examples:")
    assert "Run a scan" in out
    assert "Preview clean" in out
