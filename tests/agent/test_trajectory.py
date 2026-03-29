"""Tests for agent.trajectory — scratchpad conversion, completeness check,
and JSONL trajectory file writing.

trajectory.py is used by the RL training pipeline (batch_runner) and the
agent loop to save conversation trajectories for fine-tuning. These are
pure-function tests with no AIAgent dependency.
"""

import json
import os
import tempfile

import pytest

from agent.trajectory import (
    convert_scratchpad_to_think,
    has_incomplete_scratchpad,
    save_trajectory,
)


# ===========================================================================
# convert_scratchpad_to_think
# ===========================================================================


class TestConvertScratchpadToThink:
    """Tests for <REASONING_SCRATCHPAD> → <think> tag conversion."""

    def test_no_tags_unchanged(self):
        assert convert_scratchpad_to_think("Hello world") == "Hello world"

    def test_empty_string_unchanged(self):
        assert convert_scratchpad_to_think("") == ""

    def test_none_returns_none(self):
        assert convert_scratchpad_to_think(None) is None

    def test_full_tag_pair_converted(self):
        result = convert_scratchpad_to_think(
            "<REASONING_SCRATCHPAD>some thought</REASONING_SCRATCHPAD>"
        )
        assert result == "<think>some thought</think>"

    def test_opening_tag_converted(self):
        text = "<REASONING_SCRATCHPAD>thinking..."
        result = convert_scratchpad_to_think(text)
        assert "<REASONING_SCRATCHPAD>" not in result
        assert "<think>" in result

    def test_closing_tag_converted(self):
        text = "...done</REASONING_SCRATCHPAD>"
        result = convert_scratchpad_to_think(text)
        assert "</REASONING_SCRATCHPAD>" not in result
        assert "</think>" in result

    def test_multiple_pairs_all_converted(self):
        text = (
            "<REASONING_SCRATCHPAD>first</REASONING_SCRATCHPAD>"
            "<REASONING_SCRATCHPAD>second</REASONING_SCRATCHPAD>"
        )
        result = convert_scratchpad_to_think(text)
        assert result == "<think>first</think><think>second</think>"
        assert "<REASONING_SCRATCHPAD>" not in result

    def test_mixed_content_preserved(self):
        text = "prefix <REASONING_SCRATCHPAD>thought</REASONING_SCRATCHPAD> suffix"
        result = convert_scratchpad_to_think(text)
        assert result == "prefix <think>thought</think> suffix"

    def test_no_scratchpad_tag_returns_original(self):
        text = "<think>already think tags</think>"
        assert convert_scratchpad_to_think(text) == text

    def test_multiline_content_converted(self):
        text = "<REASONING_SCRATCHPAD>\nline one\nline two\n</REASONING_SCRATCHPAD>"
        result = convert_scratchpad_to_think(text)
        assert "<think>" in result
        assert "line one" in result
        assert "<REASONING_SCRATCHPAD>" not in result


# ===========================================================================
# has_incomplete_scratchpad
# ===========================================================================


class TestHasIncompleteScratchpad:
    """Tests for detecting unclosed <REASONING_SCRATCHPAD> tags."""

    def test_empty_string_is_complete(self):
        assert has_incomplete_scratchpad("") is False

    def test_none_is_complete(self):
        assert has_incomplete_scratchpad(None) is False

    def test_no_tags_is_complete(self):
        assert has_incomplete_scratchpad("Just regular text.") is False

    def test_complete_tag_pair_is_complete(self):
        text = "<REASONING_SCRATCHPAD>thought</REASONING_SCRATCHPAD>"
        assert has_incomplete_scratchpad(text) is False

    def test_open_tag_only_is_incomplete(self):
        text = "<REASONING_SCRATCHPAD>no closing tag here"
        assert has_incomplete_scratchpad(text) is True

    def test_close_tag_only_is_complete(self):
        """A closing tag without an opening tag is treated as complete
        (the opening was already processed)."""
        text = "some content</REASONING_SCRATCHPAD>"
        assert has_incomplete_scratchpad(text) is False

    def test_multiple_complete_pairs_is_complete(self):
        text = (
            "<REASONING_SCRATCHPAD>a</REASONING_SCRATCHPAD>"
            "<REASONING_SCRATCHPAD>b</REASONING_SCRATCHPAD>"
        )
        assert has_incomplete_scratchpad(text) is False

    def test_last_pair_incomplete(self):
        text = (
            "<REASONING_SCRATCHPAD>a</REASONING_SCRATCHPAD>"
            "<REASONING_SCRATCHPAD>b still open"
        )
        assert has_incomplete_scratchpad(text) is True

    def test_whitespace_only_is_complete(self):
        assert has_incomplete_scratchpad("   \n\t  ") is False


# ===========================================================================
# save_trajectory
# ===========================================================================


class TestSaveTrajectory:
    """Tests for JSONL trajectory file writing."""

    def test_saves_entry_to_file(self, tmp_path):
        filepath = str(tmp_path / "out.jsonl")
        traj = [{"from": "human", "value": "hello"}]
        save_trajectory(traj, "test-model", True, filename=filepath)

        with open(filepath) as f:
            entry = json.loads(f.readline())

        assert entry["model"] == "test-model"
        assert entry["completed"] is True
        assert entry["conversations"] == traj

    def test_entry_has_timestamp(self, tmp_path):
        filepath = str(tmp_path / "out.jsonl")
        save_trajectory([], "m", True, filename=filepath)
        with open(filepath) as f:
            entry = json.loads(f.read())
        assert "timestamp" in entry
        assert len(entry["timestamp"]) > 10

    def test_appends_multiple_entries(self, tmp_path):
        filepath = str(tmp_path / "out.jsonl")
        traj = [{"from": "human", "value": "x"}]
        save_trajectory(traj, "model-a", True, filename=filepath)
        save_trajectory(traj, "model-b", False, filename=filepath)

        with open(filepath) as f:
            lines = f.readlines()

        assert len(lines) == 2
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        assert first["model"] == "model-a"
        assert second["model"] == "model-b"

    def test_completed_false_recorded(self, tmp_path):
        filepath = str(tmp_path / "out.jsonl")
        save_trajectory([], "m", False, filename=filepath)
        with open(filepath) as f:
            entry = json.loads(f.read())
        assert entry["completed"] is False

    def test_default_filename_completed(self, tmp_path, monkeypatch):
        """When filename is None and completed=True, writes to trajectory_samples.jsonl."""
        monkeypatch.chdir(tmp_path)
        save_trajectory([], "m", True)
        assert (tmp_path / "trajectory_samples.jsonl").exists()

    def test_default_filename_failed(self, tmp_path, monkeypatch):
        """When filename is None and completed=False, writes to failed_trajectories.jsonl."""
        monkeypatch.chdir(tmp_path)
        save_trajectory([], "m", False)
        assert (tmp_path / "failed_trajectories.jsonl").exists()

    def test_empty_trajectory_saved(self, tmp_path):
        filepath = str(tmp_path / "out.jsonl")
        save_trajectory([], "m", True, filename=filepath)
        with open(filepath) as f:
            entry = json.loads(f.read())
        assert entry["conversations"] == []

    def test_unicode_content_preserved(self, tmp_path):
        filepath = str(tmp_path / "out.jsonl")
        traj = [{"from": "human", "value": "Merhaba dünya 🌍"}]
        save_trajectory(traj, "m", True, filename=filepath)
        with open(filepath, encoding="utf-8") as f:
            entry = json.loads(f.read())
        assert entry["conversations"][0]["value"] == "Merhaba dünya 🌍"

    def test_invalid_path_does_not_raise(self):
        """save_trajectory must silently swallow write errors (logger.warning only)."""
        save_trajectory([], "m", True, filename="/nonexistent/path/out.jsonl")
