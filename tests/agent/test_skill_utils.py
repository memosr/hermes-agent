"""Tests for agent.skill_utils — frontmatter parsing, platform matching,
description extraction, condition extraction, and helper utilities.

skill_utils is intentionally dependency-light (no tool registry, no CLI config)
so these tests run without any external fixtures or mocking of Hermes internals.
"""

import sys
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Minimal stub for hermes_constants so skill_utils can be imported standalone
# ---------------------------------------------------------------------------

_mock_hermes_constants = types.ModuleType("hermes_constants")
_mock_hermes_constants.get_hermes_home = lambda: Path("/tmp/fake_hermes_home")
sys.modules.setdefault("hermes_constants", _mock_hermes_constants)

from agent.skill_utils import (
    PLATFORM_MAP,
    _normalize_string_set,
    extract_skill_conditions,
    extract_skill_description,
    parse_frontmatter,
    skill_matches_platform,
)


# ===========================================================================
# parse_frontmatter
# ===========================================================================


class TestParseFrontmatter:
    """Tests for YAML frontmatter extraction from skill markdown files."""

    def test_full_frontmatter_parsed(self):
        content = "---\nname: my-skill\nversion: 1.0.0\n---\n# Body\n"
        fm, body = parse_frontmatter(content)
        assert fm["name"] == "my-skill"
        assert fm["version"] == "1.0.0"
        assert "# Body" in body

    def test_no_frontmatter_returns_empty_dict(self):
        content = "# Just a heading\n\nSome body text."
        fm, body = parse_frontmatter(content)
        assert fm == {}
        assert body == content

    def test_empty_string_returns_empty(self):
        fm, body = parse_frontmatter("")
        assert fm == {}
        assert body == ""

    def test_platforms_list_parsed(self):
        content = "---\nname: test\nplatforms: [macos, linux]\n---\nbody"
        fm, _ = parse_frontmatter(content)
        assert fm["platforms"] == ["macos", "linux"]

    def test_nested_metadata_parsed(self):
        content = (
            "---\n"
            "name: skill\n"
            "metadata:\n"
            "  hermes:\n"
            "    tags: [GitHub, CI]\n"
            "    requires_toolsets: [terminal]\n"
            "---\nbody\n"
        )
        fm, _ = parse_frontmatter(content)
        hermes = fm["metadata"]["hermes"]
        assert hermes["tags"] == ["GitHub", "CI"]
        assert hermes["requires_toolsets"] == ["terminal"]

    def test_body_separated_correctly(self):
        content = "---\nname: x\n---\n\n# Section\n\nParagraph."
        _, body = parse_frontmatter(content)
        assert "# Section" in body
        assert "Paragraph." in body

    def test_description_string_value(self):
        content = "---\ndescription: Does something useful.\n---\nbody"
        fm, _ = parse_frontmatter(content)
        assert fm["description"] == "Does something useful."

    def test_missing_closing_delimiter_returns_empty(self):
        """If the closing --- is absent, treat the whole content as body."""
        content = "---\nname: broken\n# body without closing fence"
        fm, body = parse_frontmatter(content)
        assert fm == {}
        assert body == content

    def test_frontmatter_with_quoted_strings(self):
        content = "---\nname: 'my skill'\ndescription: \"quoted value\"\n---\nbody"
        fm, _ = parse_frontmatter(content)
        assert fm["name"] == "my skill"
        assert fm["description"] == "quoted value"


# ===========================================================================
# skill_matches_platform
# ===========================================================================


class TestSkillMatchesPlatform:
    """Tests for OS-based skill filtering."""

    def test_no_platforms_field_matches_all(self):
        """Skills without a platforms key run on every OS."""
        assert skill_matches_platform({}) is True

    def test_empty_platforms_list_matches_all(self):
        assert skill_matches_platform({"platforms": []}) is True

    def test_none_platforms_matches_all(self):
        assert skill_matches_platform({"platforms": None}) is True

    def test_current_platform_matches(self):
        """The current platform should always match a skill declaring it."""
        import sys
        current = sys.platform
        # Determine which Hermes platform key maps to the current sys.platform
        reverse_map = {v: k for k, v in PLATFORM_MAP.items()}
        # sys.platform can be "darwin", "linux", "win32" etc.
        for hermes_key, sys_key in PLATFORM_MAP.items():
            if current.startswith(sys_key):
                assert skill_matches_platform({"platforms": [hermes_key]}) is True
                break

    def test_windows_only_skill_fails_on_non_windows(self):
        """A windows-only skill should not load on Linux/macOS."""
        import sys
        if sys.platform == "win32":
            pytest.skip("Running on Windows — skip non-Windows assertion")
        assert skill_matches_platform({"platforms": ["windows"]}) is False

    def test_macos_only_skill_fails_on_linux(self):
        import sys
        if sys.platform == "darwin":
            pytest.skip("Running on macOS — skip non-macOS assertion")
        assert skill_matches_platform({"platforms": ["macos"]}) is False

    def test_multiple_platforms_one_matches(self):
        """If any declared platform matches, the skill is compatible."""
        import sys
        # Both linux and macos declared — one of them must match on CI
        result = skill_matches_platform({"platforms": ["linux", "macos"]})
        if sys.platform in ("linux", "darwin"):
            assert result is True
        else:
            # On Windows neither matches
            assert result is False

    def test_string_instead_of_list_accepted(self):
        """Single platform as a string (not a list) is also valid."""
        import sys
        if sys.platform.startswith("linux"):
            assert skill_matches_platform({"platforms": "linux"}) is True
        elif sys.platform == "darwin":
            assert skill_matches_platform({"platforms": "macos"}) is True

    def test_unknown_platform_key_does_not_crash(self):
        """An unrecognised platform string fails gracefully (no match)."""
        result = skill_matches_platform({"platforms": ["haiku-os"]})
        assert result is False


# ===========================================================================
# extract_skill_description
# ===========================================================================


class TestExtractSkillDescription:
    """Tests for description truncation and normalisation."""

    def test_short_description_unchanged(self):
        result = extract_skill_description({"description": "Short."})
        assert result == "Short."

    def test_long_description_truncated_to_60(self):
        long = "A" * 100
        result = extract_skill_description({"description": long})
        assert len(result) <= 60
        assert result.endswith("...")

    def test_exactly_60_chars_not_truncated(self):
        exact = "B" * 60
        result = extract_skill_description({"description": exact})
        assert result == exact
        assert "..." not in result

    def test_61_chars_truncated(self):
        over = "C" * 61
        result = extract_skill_description({"description": over})
        assert result.endswith("...")
        assert len(result) == 60

    def test_missing_description_returns_empty(self):
        assert extract_skill_description({}) == ""

    def test_empty_description_returns_empty(self):
        assert extract_skill_description({"description": ""}) == ""

    def test_quoted_description_stripped(self):
        result = extract_skill_description({"description": "'quoted value'"})
        assert result == "quoted value"

    def test_double_quoted_description_stripped(self):
        result = extract_skill_description({"description": '"double quoted"'})
        assert result == "double quoted"

    def test_whitespace_stripped(self):
        result = extract_skill_description({"description": "  trimmed  "})
        assert result == "trimmed"


# ===========================================================================
# extract_skill_conditions
# ===========================================================================


class TestExtractSkillConditions:
    """Tests for conditional activation metadata extraction."""

    def test_all_conditions_present(self):
        fm = {
            "metadata": {
                "hermes": {
                    "fallback_for_toolsets": ["web"],
                    "requires_toolsets": ["terminal"],
                    "fallback_for_tools": ["web_search"],
                    "requires_tools": ["terminal"],
                }
            }
        }
        result = extract_skill_conditions(fm)
        assert result["fallback_for_toolsets"] == ["web"]
        assert result["requires_toolsets"] == ["terminal"]
        assert result["fallback_for_tools"] == ["web_search"]
        assert result["requires_tools"] == ["terminal"]

    def test_empty_frontmatter_returns_empty_lists(self):
        result = extract_skill_conditions({})
        assert result["fallback_for_toolsets"] == []
        assert result["requires_toolsets"] == []
        assert result["fallback_for_tools"] == []
        assert result["requires_tools"] == []

    def test_missing_hermes_key_returns_empty_lists(self):
        fm = {"metadata": {"other": {}}}
        result = extract_skill_conditions(fm)
        assert result["requires_toolsets"] == []

    def test_missing_metadata_key_returns_empty_lists(self):
        fm = {"name": "skill"}
        result = extract_skill_conditions(fm)
        assert result["fallback_for_toolsets"] == []

    def test_partial_conditions(self):
        fm = {
            "metadata": {
                "hermes": {
                    "requires_toolsets": ["terminal"],
                }
            }
        }
        result = extract_skill_conditions(fm)
        assert result["requires_toolsets"] == ["terminal"]
        assert result["fallback_for_toolsets"] == []


# ===========================================================================
# _normalize_string_set (internal helper)
# ===========================================================================


class TestNormalizeStringSet:
    """Tests for the internal set normalisation helper."""

    def test_none_returns_empty_set(self):
        assert _normalize_string_set(None) == set()

    def test_empty_list_returns_empty_set(self):
        assert _normalize_string_set([]) == set()

    def test_list_of_strings(self):
        assert _normalize_string_set(["a", "b", "c"]) == {"a", "b", "c"}

    def test_single_string_wrapped(self):
        assert _normalize_string_set("solo") == {"solo"}

    def test_whitespace_stripped(self):
        assert _normalize_string_set(["  foo  ", " bar"]) == {"foo", "bar"}

    def test_empty_strings_excluded(self):
        result = _normalize_string_set(["a", "", "  "])
        assert "" not in result
        assert "a" in result

    def test_duplicates_collapsed(self):
        assert _normalize_string_set(["x", "x", "x"]) == {"x"}


# ===========================================================================
# PLATFORM_MAP constant
# ===========================================================================


class TestPlatformMap:
    """Sanity checks on the PLATFORM_MAP constant."""

    def test_contains_expected_keys(self):
        assert "macos" in PLATFORM_MAP
        assert "linux" in PLATFORM_MAP
        assert "windows" in PLATFORM_MAP

    def test_macos_maps_to_darwin(self):
        assert PLATFORM_MAP["macos"] == "darwin"

    def test_linux_maps_to_linux(self):
        assert PLATFORM_MAP["linux"] == "linux"

    def test_windows_maps_to_win32(self):
        assert PLATFORM_MAP["windows"] == "win32"
