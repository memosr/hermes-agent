"""Tests for pure helper functions in agent.display.

agent/display.py is the module responsible for all CLI tool output formatting.
build_tool_preview() is called on every tool invocation to generate the
one-line status shown to the user — but had no test coverage.
"""

import sys
import types

import pytest

# ---------------------------------------------------------------------------
# Minimal stubs so display.py can be imported standalone
# ---------------------------------------------------------------------------
_mock_hc = types.ModuleType("hermes_constants")
_mock_hc.get_hermes_home = lambda: __import__("pathlib").Path("/tmp/fake")
sys.modules.setdefault("hermes_constants", _mock_hc)

_mock_skin = types.ModuleType("hermes_cli.skin_engine")
_mock_skin.get_active_skin = lambda: None
_mock_skin.get_active_prompt_symbol = lambda: "❯ "
sys.modules.setdefault("hermes_cli.skin_engine", _mock_skin)
sys.modules.setdefault("hermes_cli", types.ModuleType("hermes_cli"))

from agent.display import _oneline, build_tool_preview, _detect_tool_failure


# ===========================================================================
# _oneline
# ===========================================================================


class TestOneline:
    """Tests for the whitespace-collapsing helper."""

    def test_single_line_unchanged(self):
        assert _oneline("hello world") == "hello world"

    def test_newlines_collapsed(self):
        assert _oneline("line one\nline two") == "line one line two"

    def test_multiple_spaces_collapsed(self):
        assert _oneline("too   many   spaces") == "too many spaces"

    def test_tabs_collapsed(self):
        assert _oneline("a\tb\tc") == "a b c"

    def test_mixed_whitespace(self):
        assert _oneline("  a  \n  b  \t  c  ") == "a b c"

    def test_empty_string(self):
        assert _oneline("") == ""

    def test_only_whitespace(self):
        assert _oneline("   \n\t  ") == ""


# ===========================================================================
# build_tool_preview
# ===========================================================================


class TestBuildToolPreview:
    """Tests for tool call one-line preview generation."""

    # --- Empty / missing args ---

    def test_none_args_returns_none(self):
        assert build_tool_preview("terminal", {}) is None

    def test_empty_dict_returns_none(self):
        assert build_tool_preview("web_search", {}) is None

    # --- Primary-arg tools ---

    def test_terminal_command(self):
        result = build_tool_preview("terminal", {"command": "ls -la"})
        assert result == "ls -la"

    def test_web_search_query(self):
        result = build_tool_preview("web_search", {"query": "python asyncio"})
        assert result == "python asyncio"

    def test_read_file_path(self):
        result = build_tool_preview("read_file", {"path": "README.md"})
        assert result == "README.md"

    def test_write_file_path(self):
        result = build_tool_preview("write_file", {"path": "output.txt", "content": "x"})
        assert result == "output.txt"

    def test_execute_code_preview(self):
        result = build_tool_preview("execute_code", {"code": "print('hi')"})
        assert result == "print('hi')"

    def test_delegate_task_goal(self):
        result = build_tool_preview("delegate_task", {"goal": "build the feature"})
        assert result == "build the feature"

    # --- todo tool ---

    def test_todo_read(self):
        assert build_tool_preview("todo", {"todos": None}) == "reading task list"

    def test_todo_plan(self):
        result = build_tool_preview("todo", {"todos": [1, 2, 3], "merge": False})
        assert result == "planning 3 task(s)"

    def test_todo_update(self):
        result = build_tool_preview("todo", {"todos": [1, 2], "merge": True})
        assert result == "updating 2 task(s)"

    def test_todo_empty_list(self):
        result = build_tool_preview("todo", {"todos": [], "merge": False})
        assert result == "planning 0 task(s)"

    # --- memory tool ---

    def test_memory_add(self):
        result = build_tool_preview("memory", {
            "action": "add", "target": "user", "content": "likes Python"
        })
        assert result is not None
        assert "+user" in result
        assert "likes Python" in result

    def test_memory_replace(self):
        result = build_tool_preview("memory", {
            "action": "replace", "target": "user", "old_text": "likes Java"
        })
        assert result is not None
        assert "~user" in result

    def test_memory_remove(self):
        result = build_tool_preview("memory", {
            "action": "remove", "target": "user", "old_text": "likes Java"
        })
        assert result is not None
        assert "-user" in result

    def test_memory_unknown_action(self):
        result = build_tool_preview("memory", {"action": "list", "target": "user"})
        assert result == "list"

    # --- session_search tool ---

    def test_session_search_short_query(self):
        result = build_tool_preview("session_search", {"query": "oauth setup"})
        assert result is not None
        assert "oauth setup" in result

    def test_session_search_long_query_truncated(self):
        result = build_tool_preview("session_search", {"query": "A" * 50})
        assert result is not None
        assert "..." in result

    # --- send_message tool ---

    def test_send_message(self):
        result = build_tool_preview("send_message", {
            "target": "telegram", "message": "Hello!"
        })
        assert result is not None
        assert "telegram" in result
        assert "Hello!" in result

    def test_send_message_long_truncated(self):
        result = build_tool_preview("send_message", {
            "target": "slack", "message": "A" * 50
        })
        assert result is not None
        assert "..." in result

    # --- process tool ---

    def test_process_start(self):
        result = build_tool_preview("process", {"action": "start", "session_id": "abc123"})
        assert result is not None
        assert "start" in result

    def test_process_wait_with_timeout(self):
        result = build_tool_preview("process", {
            "action": "wait", "session_id": "abc", "timeout": 30
        })
        assert result is not None
        assert "30s" in result

    def test_process_no_timeout_for_non_wait(self):
        result = build_tool_preview("process", {
            "action": "read", "session_id": "abc", "timeout": 30
        })
        assert result is not None
        assert "30s" not in result

    # --- Truncation ---

    def test_long_value_truncated_at_max_len(self):
        long_cmd = "echo " + "x" * 100
        result = build_tool_preview("terminal", {"command": long_cmd}, max_len=40)
        assert result is not None
        assert len(result) <= 40
        assert result.endswith("...")

    def test_short_value_not_truncated(self):
        result = build_tool_preview("terminal", {"command": "ls"}, max_len=40)
        assert result == "ls"
        assert "..." not in result

    # --- Fallback for unknown tools ---

    def test_unknown_tool_uses_query_fallback(self):
        result = build_tool_preview("unknown_tool", {"query": "fallback test"})
        assert result == "fallback test"

    def test_unknown_tool_no_known_key_returns_none(self):
        result = build_tool_preview("completely_unknown", {"foo": "bar"})
        assert result is None

    # --- List values ---

    def test_list_value_uses_first_element(self):
        result = build_tool_preview("web_extract", {"urls": ["https://example.com", "https://other.com"]})
        assert result == "https://example.com"

    def test_empty_list_value_returns_none(self):
        result = build_tool_preview("web_extract", {"urls": []})
        assert result is None


# ===========================================================================
# _detect_tool_failure
# ===========================================================================


class TestDetectToolFailure:
    """Tests for tool result failure detection."""

    def test_none_result_is_not_failure(self):
        is_fail, suffix = _detect_tool_failure("terminal", None)
        assert is_fail is False
        assert suffix == ""

    def test_terminal_exit_zero_is_success(self):
        import json
        result = json.dumps({"exit_code": 0, "output": "ok"})
        is_fail, suffix = _detect_tool_failure("terminal", result)
        assert is_fail is False

    def test_terminal_nonzero_exit_is_failure(self):
        import json
        result = json.dumps({"exit_code": 1, "output": "error"})
        is_fail, suffix = _detect_tool_failure("terminal", result)
        assert is_fail is True
        assert "[exit 1]" in suffix

    def test_terminal_exit_127_shows_code(self):
        import json
        result = json.dumps({"exit_code": 127})
        is_fail, suffix = _detect_tool_failure("terminal", result)
        assert is_fail is True
        assert "127" in suffix

    def test_memory_full_is_failure(self):
        import json
        result = json.dumps({"success": False, "error": "would exceed the limit"})
        is_fail, suffix = _detect_tool_failure("memory", result)
        assert is_fail is True
        assert "[full]" in suffix

    def test_memory_success_is_not_failure(self):
        import json
        result = json.dumps({"success": True})
        is_fail, suffix = _detect_tool_failure("memory", result)
        assert is_fail is False

    def test_generic_error_key_detected(self):
        is_fail, suffix = _detect_tool_failure("web_search", '{"error": "timeout"}')
        assert is_fail is True
        assert "[error]" in suffix

    def test_generic_error_prefix_detected(self):
        is_fail, suffix = _detect_tool_failure("read_file", "Error: file not found")
        assert is_fail is True

    def test_success_result_not_failure(self):
        is_fail, suffix = _detect_tool_failure("web_search", '{"results": []}')
        assert is_fail is False
        assert suffix == ""
