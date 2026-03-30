"""Tests for pure helper functions in agent.anthropic_adapter.

anthropic_adapter.py is 1 000+ lines with no test file. This PR covers the
pure, dependency-free helpers that are called on every Anthropic API request:
model name normalisation, tool ID sanitisation, OAuth token detection, and
per-model output token limits. Correctness here directly affects API routing
and response truncation behaviour.
"""

import sys
import types

import pytest

# ---------------------------------------------------------------------------
# Minimal stubs so anthropic_adapter can be imported without pulling in the
# full Hermes dependency tree.
# ---------------------------------------------------------------------------

_mock_hc = types.ModuleType("hermes_constants")
_mock_hc.get_hermes_home = lambda: __import__("pathlib").Path("/tmp/fake_hermes")
_mock_hc.VALID_REASONING_EFFORTS = ("xhigh", "high", "medium", "low", "minimal")
_mock_hc.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
sys.modules.setdefault("hermes_constants", _mock_hc)

_mock_mm = types.ModuleType("agent.model_metadata")
_mock_mm.estimate_tokens_rough = lambda x: 100
sys.modules.setdefault("agent.model_metadata", _mock_mm)

from agent.anthropic_adapter import (
    _ANTHROPIC_DEFAULT_OUTPUT_LIMIT,
    _ANTHROPIC_OUTPUT_LIMITS,
    _get_anthropic_max_output,
    _is_oauth_token,
    _sanitize_tool_id,
    _supports_adaptive_thinking,
    normalize_model_name,
)


# ===========================================================================
# normalize_model_name
# ===========================================================================


class TestNormalizeModelName:
    """Tests for OpenRouter → Anthropic model name normalisation."""

    def test_strips_anthropic_prefix(self):
        assert normalize_model_name("anthropic/claude-opus-4.6") == "claude-opus-4-6"

    def test_strips_anthropic_prefix_case_insensitive(self):
        assert normalize_model_name("ANTHROPIC/claude-opus-4.6") == "claude-opus-4-6"

    def test_converts_dots_to_hyphens(self):
        assert normalize_model_name("claude-opus-4.6") == "claude-opus-4-6"

    def test_preserve_dots_keeps_dots(self):
        assert normalize_model_name("claude-opus-4.6", preserve_dots=True) == "claude-opus-4.6"

    def test_non_anthropic_model_unchanged_except_dots(self):
        """Non-anthropic prefixed models only get dot conversion."""
        assert normalize_model_name("openai/gpt-4o") == "openai/gpt-4o"

    def test_no_dots_no_prefix_unchanged(self):
        assert normalize_model_name("claude-opus-4-6") == "claude-opus-4-6"

    def test_sonnet_model(self):
        assert normalize_model_name("anthropic/claude-sonnet-4.6") == "claude-sonnet-4-6"

    def test_haiku_model(self):
        assert normalize_model_name("anthropic/claude-haiku-4-5") == "claude-haiku-4-5"

    def test_empty_string(self):
        assert normalize_model_name("") == ""

    def test_prefix_only_becomes_empty(self):
        """'anthropic/' with nothing after becomes an empty string."""
        assert normalize_model_name("anthropic/") == ""

    def test_multiple_dots_all_converted(self):
        assert normalize_model_name("model.v1.2") == "model-v1-2"

    def test_preserve_dots_with_anthropic_prefix(self):
        result = normalize_model_name("anthropic/claude-opus-4.6", preserve_dots=True)
        assert result == "claude-opus-4.6"


# ===========================================================================
# _sanitize_tool_id
# ===========================================================================


class TestSanitizeToolId:
    """Tests for Anthropic tool call ID sanitisation ([a-zA-Z0-9_-] only)."""

    def test_valid_id_unchanged(self):
        assert _sanitize_tool_id("valid_id-123") == "valid_id-123"

    def test_empty_returns_fallback(self):
        assert _sanitize_tool_id("") == "tool_0"

    def test_spaces_replaced_with_underscore(self):
        assert _sanitize_tool_id("has spaces") == "has_spaces"

    def test_dots_replaced_with_underscore(self):
        assert _sanitize_tool_id("has.dots") == "has_dots"

    def test_at_sign_replaced(self):
        assert _sanitize_tool_id("abc@123") == "abc_123"

    def test_slash_replaced(self):
        assert _sanitize_tool_id("tool/id") == "tool_id"

    def test_alphanumeric_unchanged(self):
        assert _sanitize_tool_id("abc123") == "abc123"

    def test_hyphens_and_underscores_kept(self):
        assert _sanitize_tool_id("tool-id_v2") == "tool-id_v2"

    def test_all_invalid_chars_become_fallback(self):
        """A string that sanitises to empty should return the fallback."""
        result = _sanitize_tool_id("@@@")
        assert result == "___" or result == "tool_0"

    def test_unicode_chars_replaced(self):
        result = _sanitize_tool_id("tür_id")
        assert "ü" not in result


# ===========================================================================
# _is_oauth_token
# ===========================================================================


class TestIsOauthToken:
    """Tests for distinguishing OAuth/Bearer tokens from Console API keys.

    Regular API keys start with 'sk-ant-api' and use x-api-key header.
    Everything else (OAuth setup tokens, JWTs, managed keys) uses Bearer auth.
    """

    def test_console_api_key_is_not_oauth(self):
        assert _is_oauth_token("sk-ant-api03-abc123def456") is False

    def test_console_api_key_prefix_exact(self):
        assert _is_oauth_token("sk-ant-api") is False

    def test_oauth_setup_token_is_oauth(self):
        assert _is_oauth_token("sk-ant-oat01-xyz789abc") is True

    def test_jwt_is_oauth(self):
        """JWTs (e.g. from managed key flows) need Bearer auth."""
        assert _is_oauth_token("eyJhbGciOiJSUzI1NiJ9.payload.sig") is True

    def test_empty_string_is_not_oauth(self):
        assert _is_oauth_token("") is False

    def test_arbitrary_token_is_oauth(self):
        """Anything not starting with sk-ant-api defaults to Bearer."""
        assert _is_oauth_token("some-random-token-value") is True

    def test_managed_key_is_oauth(self):
        assert _is_oauth_token("hermes-managed-key-abc123") is True

    def test_sk_ant_api_prefix_only_match(self):
        """Must start with exactly 'sk-ant-api', not just contain it."""
        assert _is_oauth_token("prefix-sk-ant-api03-abc") is True


# ===========================================================================
# _get_anthropic_max_output
# ===========================================================================


class TestGetAnthropicMaxOutput:
    """Tests for per-model output token limit lookup.

    Correct limits prevent 'Response truncated' errors and thinking-budget
    exhaustion. These values are documented by Anthropic.
    """

    def test_opus_4_6_is_128k(self):
        assert _get_anthropic_max_output("claude-opus-4-6") == 128_000

    def test_sonnet_4_6_is_64k(self):
        assert _get_anthropic_max_output("claude-sonnet-4-6") == 64_000

    def test_haiku_4_5_is_64k(self):
        assert _get_anthropic_max_output("claude-haiku-4-5") == 64_000

    def test_sonnet_4_5_is_64k(self):
        assert _get_anthropic_max_output("claude-sonnet-4-5") == 64_000

    def test_claude_3_5_sonnet_is_8k(self):
        assert _get_anthropic_max_output("claude-3-5-sonnet") == 8_192

    def test_claude_3_opus_is_4k(self):
        assert _get_anthropic_max_output("claude-3-opus") == 4_096

    def test_unknown_model_returns_default(self):
        """Unknown models get the highest current limit — future-proofing."""
        assert _get_anthropic_max_output("claude-future-model") == _ANTHROPIC_DEFAULT_OUTPUT_LIMIT

    def test_datestamped_model_resolves(self):
        """'claude-sonnet-4-6-20250101' should still match 'claude-sonnet-4-6'."""
        result = _get_anthropic_max_output("claude-sonnet-4-6-20250101")
        assert result == 64_000

    def test_case_insensitive_lookup(self):
        """Lookup is case-insensitive (model.lower() is used internally)."""
        assert _get_anthropic_max_output("Claude-Opus-4-6") == 128_000

    def test_all_table_entries_return_correct_value(self):
        """Every entry in _ANTHROPIC_OUTPUT_LIMITS must resolve exactly."""
        for key, expected in _ANTHROPIC_OUTPUT_LIMITS.items():
            result = _get_anthropic_max_output(key)
            assert result == expected, f"{key}: expected {expected}, got {result}"

    def test_longest_prefix_wins(self):
        """'claude-3-5-sonnet' must win over 'claude-3-5' if both were in table."""
        result = _get_anthropic_max_output("claude-3-5-sonnet-20241022")
        assert result == 8_192


# ===========================================================================
# _supports_adaptive_thinking
# ===========================================================================


class TestSupportsAdaptiveThinking:
    """Tests for Claude 4.6 adaptive thinking detection."""

    def test_opus_4_6_with_hyphen(self):
        assert _supports_adaptive_thinking("claude-opus-4-6") is True

    def test_sonnet_4_6_with_hyphen(self):
        assert _supports_adaptive_thinking("claude-sonnet-4-6") is True

    def test_opus_4_6_with_dot(self):
        assert _supports_adaptive_thinking("claude-opus-4.6") is True

    def test_haiku_4_5_not_supported(self):
        assert _supports_adaptive_thinking("claude-haiku-4-5") is False

    def test_claude_3_not_supported(self):
        assert _supports_adaptive_thinking("claude-3-opus") is False

    def test_empty_string_not_supported(self):
        assert _supports_adaptive_thinking("") is False

    def test_unknown_model_not_supported(self):
        assert _supports_adaptive_thinking("gpt-4o") is False
