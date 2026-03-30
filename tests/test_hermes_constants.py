"""Tests for hermes_constants — shared constants and utility functions.

hermes_constants is the single import-safe root module used across the entire
codebase. parse_reasoning_effort is called in the agent loop, CLI, and gateway
on every turn that involves thinking/reasoning configuration — but had no tests.
"""

import os
from pathlib import Path

import pytest

from hermes_constants import (
    OPENROUTER_BASE_URL,
    OPENROUTER_CHAT_URL,
    OPENROUTER_MODELS_URL,
    VALID_REASONING_EFFORTS,
    display_hermes_home,
    get_hermes_dir,
    get_hermes_home,
    parse_reasoning_effort,
)


# ===========================================================================
# parse_reasoning_effort
# ===========================================================================


class TestParseReasoningEffort:
    """Tests for reasoning effort level parsing.

    parse_reasoning_effort is called in the agent loop and CLI on every turn
    that configures thinking budget — correctness here affects all model calls.
    """

    # --- Valid effort levels ---

    def test_xhigh(self):
        result = parse_reasoning_effort("xhigh")
        assert result == {"enabled": True, "effort": "xhigh"}

    def test_high(self):
        result = parse_reasoning_effort("high")
        assert result == {"enabled": True, "effort": "high"}

    def test_medium(self):
        result = parse_reasoning_effort("medium")
        assert result == {"enabled": True, "effort": "medium"}

    def test_low(self):
        result = parse_reasoning_effort("low")
        assert result == {"enabled": True, "effort": "low"}

    def test_minimal(self):
        result = parse_reasoning_effort("minimal")
        assert result == {"enabled": True, "effort": "minimal"}

    def test_all_valid_levels_covered(self):
        """Every value in VALID_REASONING_EFFORTS must parse successfully."""
        for level in VALID_REASONING_EFFORTS:
            result = parse_reasoning_effort(level)
            assert result is not None, f"{level!r} should be valid"
            assert result["enabled"] is True
            assert result["effort"] == level

    # --- none (disabled) ---

    def test_none_returns_disabled(self):
        result = parse_reasoning_effort("none")
        assert result == {"enabled": False}

    def test_none_uppercase(self):
        result = parse_reasoning_effort("NONE")
        assert result == {"enabled": False}

    # --- Empty / whitespace → None ---

    def test_empty_string_returns_none(self):
        assert parse_reasoning_effort("") is None

    def test_whitespace_only_returns_none(self):
        assert parse_reasoning_effort("   ") is None

    def test_tab_only_returns_none(self):
        assert parse_reasoning_effort("\t") is None

    # --- Unrecognised values → None ---

    def test_invalid_string_returns_none(self):
        assert parse_reasoning_effort("ultra") is None

    def test_numeric_string_returns_none(self):
        assert parse_reasoning_effort("5") is None

    def test_partial_match_returns_none(self):
        """'hig' is not a valid level — must be an exact match."""
        assert parse_reasoning_effort("hig") is None

    # --- Case insensitivity ---

    def test_uppercase_high(self):
        result = parse_reasoning_effort("HIGH")
        assert result == {"enabled": True, "effort": "high"}

    def test_mixed_case_medium(self):
        result = parse_reasoning_effort("MeDiUm")
        assert result == {"enabled": True, "effort": "medium"}

    def test_uppercase_minimal(self):
        result = parse_reasoning_effort("MINIMAL")
        assert result == {"enabled": True, "effort": "minimal"}

    # --- Whitespace stripping ---

    def test_leading_whitespace_stripped(self):
        result = parse_reasoning_effort("  high")
        assert result == {"enabled": True, "effort": "high"}

    def test_trailing_whitespace_stripped(self):
        result = parse_reasoning_effort("medium  ")
        assert result == {"enabled": True, "effort": "medium"}

    def test_both_sides_stripped(self):
        result = parse_reasoning_effort("  low  ")
        assert result == {"enabled": True, "effort": "low"}


# ===========================================================================
# get_hermes_home
# ===========================================================================


class TestGetHermesHome:
    """Tests for HERMES_HOME resolution."""

    def test_default_is_dot_hermes(self, monkeypatch):
        monkeypatch.delenv("HERMES_HOME", raising=False)
        result = get_hermes_home()
        assert result == Path.home() / ".hermes"

    def test_env_var_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "custom_home"))
        result = get_hermes_home()
        assert result == tmp_path / "custom_home"

    def test_returns_path_object(self, monkeypatch):
        monkeypatch.delenv("HERMES_HOME", raising=False)
        result = get_hermes_home()
        assert isinstance(result, Path)

    def test_env_var_used_verbatim(self, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", "/opt/hermes")
        result = get_hermes_home()
        assert str(result) == "/opt/hermes"


# ===========================================================================
# display_hermes_home
# ===========================================================================


class TestDisplayHermesHome:
    """Tests for the user-facing HERMES_HOME display string."""

    def test_default_shows_tilde(self, monkeypatch):
        monkeypatch.delenv("HERMES_HOME", raising=False)
        result = display_hermes_home()
        assert result.startswith("~/")
        assert ".hermes" in result

    def test_absolute_path_outside_home_shown_as_is(self, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", "/opt/hermes-custom")
        result = display_hermes_home()
        assert result == "/opt/hermes-custom"

    def test_returns_string(self, monkeypatch):
        monkeypatch.delenv("HERMES_HOME", raising=False)
        assert isinstance(display_hermes_home(), str)


# ===========================================================================
# URL constants
# ===========================================================================


class TestUrlConstants:
    """Sanity checks on the OpenRouter URL constants."""

    def test_base_url_is_openrouter(self):
        assert "openrouter.ai" in OPENROUTER_BASE_URL

    def test_models_url_extends_base(self):
        assert OPENROUTER_MODELS_URL.startswith(OPENROUTER_BASE_URL)
        assert OPENROUTER_MODELS_URL.endswith("/models")

    def test_chat_url_extends_base(self):
        assert OPENROUTER_CHAT_URL.startswith(OPENROUTER_BASE_URL)
        assert "completions" in OPENROUTER_CHAT_URL

    def test_all_urls_are_https(self):
        for url in (OPENROUTER_BASE_URL, OPENROUTER_MODELS_URL, OPENROUTER_CHAT_URL):
            assert url.startswith("https://"), f"{url} should use HTTPS"


# ===========================================================================
# VALID_REASONING_EFFORTS constant
# ===========================================================================


class TestValidReasoningEfforts:
    """Tests for the VALID_REASONING_EFFORTS tuple."""

    def test_is_tuple(self):
        assert isinstance(VALID_REASONING_EFFORTS, tuple)

    def test_contains_expected_levels(self):
        for level in ("xhigh", "high", "medium", "low", "minimal"):
            assert level in VALID_REASONING_EFFORTS

    def test_no_none_in_valid_efforts(self):
        """'none' is a special case handled separately — not a valid effort."""
        assert "none" not in VALID_REASONING_EFFORTS

    def test_all_lowercase(self):
        for level in VALID_REASONING_EFFORTS:
            assert level == level.lower(), f"{level!r} should be lowercase"
