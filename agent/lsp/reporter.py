"""Format LSP diagnostics for inclusion in tool output.

The model sees a compact, severity-filtered, line-bounded summary of
diagnostics introduced by the latest edit.  Format matches what
OpenCode's ``lsp/diagnostic.ts`` and Claude Code's
``formatDiagnosticsSummary`` produce — ``<diagnostics>`` blocks with
1-indexed line/column, capped at ``MAX_PER_FILE`` errors.

Sanitization note
-----------------
Diagnostic ``message``, ``code``, and ``source`` fields originate from
language servers running over user-controlled source code.  A hostile
repository can place instruction-like text inside identifier names,
type aliases, or import paths so the language server's resulting error
message contains "ignore previous instructions" or fake tool-result
delimiters.  Once that string is included verbatim in the model's tool
output, the model can treat it as a directive.  We strip control
characters, collapse newlines, cap per-field length, and HTML-escape
angle brackets / ampersands so injected payloads can't synthesize new
tags, additional <diagnostics> blocks, or multi-line instructions.
"""
from __future__ import annotations

import html
from typing import Any, Dict, List

# Severity-1 only by default — warnings/info/hints would flood the
# agent.  Lift this in config under ``lsp.severities`` if needed.
SEVERITY_NAMES = {1: "ERROR", 2: "WARN", 3: "INFO", 4: "HINT"}
DEFAULT_SEVERITIES = frozenset({1})  # ERROR only

MAX_PER_FILE = 20
MAX_TOTAL_CHARS = 4000

# Per-field caps for sanitization.  Diagnostic messages are normally
# under 200 chars; capping at 300 leaves headroom for legitimate
# multi-clause type errors without giving an attacker room to fit an
# instruction-shaped payload.
_MAX_MSG_CHARS = 300
_MAX_CODE_CHARS = 80
_MAX_SOURCE_CHARS = 80


def _sanitize_field(value: Any, *, limit: int) -> str:
    """Strip control characters, collapse whitespace, cap length, and
    HTML-escape the result so it can't break out of the diagnostic
    block or simulate tool output."""
    if value is None:
        return ""
    raw = str(value)
    # Collapse newlines and carriage returns so a malicious identifier
    # can't fake additional output lines.
    raw = raw.replace("\r", " ").replace("\n", " ")
    # Drop other ASCII control chars (tab, etc.) that have no business
    # in a single-line summary.
    raw = "".join(ch for ch in raw if ch == " " or ch.isprintable())
    raw = raw.strip()[:limit]
    # quote=False keeps quotes readable in the inline message; only < >
    # & need escaping here because the field is rendered as text, not
    # inside an attribute.
    return html.escape(raw, quote=False)


def format_diagnostic(d: Dict[str, Any]) -> str:
    """One-line representation of a single diagnostic."""
    sev = SEVERITY_NAMES.get(d.get("severity") or 1, "ERROR")
    rng = d.get("range") or {}
    start = rng.get("start") or {}
    line = int(start.get("line", 0)) + 1
    col = int(start.get("character", 0)) + 1
    msg = _sanitize_field(d.get("message"), limit=_MAX_MSG_CHARS)
    code = _sanitize_field(d.get("code"), limit=_MAX_CODE_CHARS)
    code_part = f" [{code}]" if code else ""
    source = _sanitize_field(d.get("source"), limit=_MAX_SOURCE_CHARS)
    source_part = f" ({source})" if source else ""
    return f"{sev} [{line}:{col}] {msg}{code_part}{source_part}"


def report_for_file(
    file_path: str,
    diagnostics: List[Dict[str, Any]],
    *,
    severities: frozenset = DEFAULT_SEVERITIES,
    max_per_file: int = MAX_PER_FILE,
) -> str:
    """Build a ``<diagnostics file=...>`` block for one file.

    Returns an empty string when no diagnostics pass the severity
    filter, so callers can do ``if block:`` to skip empty cases.
    """
    if not diagnostics:
        return ""
    filtered = [d for d in diagnostics if (d.get("severity") or 1) in severities]
    if not filtered:
        return ""
    limited = filtered[:max_per_file]
    extra = len(filtered) - len(limited)
    lines = [format_diagnostic(d) for d in limited]
    body = "\n".join(lines)
    if extra > 0:
        body += f"\n... and {extra} more"
    # file_path can contain quotes on Unix; escape it inside the
    # attribute so a crafted filename can't break the XML-ish wrapper.
    safe_path = html.escape(str(file_path), quote=True)
    return f"<diagnostics file=\"{safe_path}\">\n{body}\n</diagnostics>"


def truncate(s: str, *, limit: int = MAX_TOTAL_CHARS) -> str:
    """Hard-cap a formatted summary string."""
    if len(s) <= limit:
        return s
    marker = "\n…[truncated]"
    return s[: limit - len(marker)] + marker


__all__ = [
    "SEVERITY_NAMES",
    "DEFAULT_SEVERITIES",
    "MAX_PER_FILE",
    "format_diagnostic",
    "report_for_file",
    "truncate",
]
