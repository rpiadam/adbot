"""Tests for utility functions."""

import pytest
from datetime import timedelta

from src.utils import (
    format_uptime,
    format_bytes,
    sanitize_filename,
    truncate_text,
    parse_duration,
    format_duration,
    safe_int,
    safe_float,
    validate_url,
    escape_markdown,
    chunk_text,
)


def test_format_uptime():
    """Test uptime formatting."""
    assert format_uptime(0) == "0s"
    assert format_uptime(30) == "30s"
    assert format_uptime(90) == "1m"
    assert format_uptime(3661) == "1h 1m"
    assert format_uptime(90061) == "1d 1h 1m"
    assert format_uptime(-10) == "0s"


def test_format_bytes():
    """Test bytes formatting."""
    assert format_bytes(0) == "0.00 B"
    assert format_bytes(1024) == "1.00 KB"
    assert format_bytes(1048576) == "1.00 MB"
    assert format_bytes(1073741824) == "1.00 GB"


def test_sanitize_filename():
    """Test filename sanitization."""
    assert sanitize_filename("test.txt") == "test.txt"
    assert sanitize_filename("test<>file.txt") == "test__file.txt"
    assert sanitize_filename("  test.txt  ") == "test.txt"
    assert sanitize_filename(".") == "unnamed"
    assert len(sanitize_filename("a" * 300)) == 255


def test_truncate_text():
    """Test text truncation."""
    assert truncate_text("short") == "short"
    assert truncate_text("a" * 100) == "a" * 100
    assert truncate_text("a" * 150, max_length=100) == "a" * 97 + "..."
    assert truncate_text("test", max_length=10) == "test"


def test_parse_duration():
    """Test duration parsing."""
    assert parse_duration("5m") == timedelta(minutes=5)
    assert parse_duration("2h") == timedelta(hours=2)
    assert parse_duration("3d") == timedelta(days=3)
    assert parse_duration("1h 30m") == timedelta(hours=1, minutes=30)
    assert parse_duration("") is None
    assert parse_duration("invalid") is None


def test_format_duration():
    """Test duration formatting."""
    assert format_duration(timedelta(minutes=5)) == "5m"
    assert format_duration(timedelta(hours=2)) == "2h"
    assert format_duration(timedelta(days=1, hours=2, minutes=30)) == "1d 2h 30m"


def test_safe_int():
    """Test safe integer conversion."""
    assert safe_int("123") == 123
    assert safe_int(123) == 123
    assert safe_int("invalid", default=42) == 42
    assert safe_int(None, default=0) == 0


def test_safe_float():
    """Test safe float conversion."""
    assert safe_float("123.45") == 123.45
    assert safe_float(123.45) == 123.45
    assert safe_float("invalid", default=42.0) == 42.0
    assert safe_float(None, default=0.0) == 0.0


def test_validate_url():
    """Test URL validation."""
    assert validate_url("http://example.com") is True
    assert validate_url("https://example.com") is True
    assert validate_url("http://localhost:8000") is True
    assert validate_url("not a url") is False
    assert validate_url("ftp://example.com") is False
    assert validate_url("example.com") is False


def test_escape_markdown():
    """Test markdown escaping."""
    assert escape_markdown("test") == "test"
    assert escape_markdown("**bold**") == "\\*\\*bold\\*\\*"
    assert escape_markdown("_italic_") == "\\_italic\\_"
    assert escape_markdown("`code`") == "\\`code\\`"


def test_chunk_text():
    """Test text chunking."""
    assert chunk_text("short") == ["short"]
    assert len(chunk_text("a" * 5000, max_length=2000)) == 3
    assert chunk_text("line1\nline2\nline3", max_length=10) == ["line1", "line2", "line3"]

