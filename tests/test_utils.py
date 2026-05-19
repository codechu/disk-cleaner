"""``human``, ``parse_size`` saf logic testleri."""

from __future__ import annotations

import pytest

from disk_cleaner.utils import human, parse_size


@pytest.mark.parametrize(
    "n,expected_prefix",
    [
        (0, "0 B"),
        (1, "1 B"),
        (1023, "1023 B"),
        (1024, "1.0 KB"),
        (1024 * 1024, "1.0 MB"),
        (1024**3, "1.0 GB"),
    ],
)
def test_human_basic(n, expected_prefix):
    assert human(n) == expected_prefix


def test_human_none_returns_qmark():
    assert human(None) == "?"


@pytest.mark.parametrize(
    "s,expected",
    [
        ("0", 0),
        ("100", 100),
        ("1KB", 1024),
        ("1MB", 1024**2),
        ("2.5GB", int(2.5 * 1024**3)),
        ("", 0),
        ("not-a-size", 0),
    ],
)
def test_parse_size(s, expected):
    assert parse_size(s) == expected
