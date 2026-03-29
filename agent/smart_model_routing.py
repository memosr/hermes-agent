"""Helpers for optional cheap-vs-strong model routing."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

# English keywords that signal a complex, tool-heavy, or long-form task.
# When any of these appear in a short user message the cheap-model route is
# skipped and the primary model handles the turn instead.
_COMPLEX_KEYWORDS = {
    "debug",
    "debugging",
    "implement",
    "implementation",
    "refactor",
    "patch",
    "traceback",
    "stacktrace",
    "exception",
    "error",
    "analyze",
    "analysis",
    "investigate",
    "architecture",
    "design",
    "compare",
    "benchmark",
    "optimize",
    "optimise",
    "review",
    "terminal",
    "shell",
    "tool",
    "tools",
    "pytest",
    "test",
    "tests",
    "plan",
    "planning",
    "delegate",
    "subagent",
    "cron",
    "docker",
    "kubernetes",
}

# Multilingual equivalents of the English complex-task keywords above.
# Each entry is a single whitespace-free token as it would appear after
# splitting on spaces -- matching the tokenisation used in
# choose_cheap_model_route().  Only high-confidence, unambiguous terms are
# included to keep the false-positive rate (routing simple messages to the
# primary model) low.
#
# Languages covered: Turkish (TR), German (DE), French (FR), Spanish (ES),
# Portuguese (PT/BR), Russian (RU), Chinese Simplified (ZH),
# Japanese (JA), Korean (KO).
_COMPLEX_KEYWORDS_MULTILINGUAL: frozenset = frozenset({
    # Turkish (TR)
    "hata",         # error / bug
    "hatali",       # erroneous / buggy (ASCII fallback without diacritic)
    "hatalı",       # erroneous / buggy
    "ayikla",       # debug (ASCII fallback)
    "ayıkla",       # debug (verb stem)
    "ayiklama",     # debugging (ASCII fallback)
    "ayıklama",     # debugging (noun)
    "analiz",       # analysis / analyze
    "mimari",       # architecture
    "tasarim",      # design (ASCII fallback)
    "tasarım",      # design
    "refaktor",     # refactor (ASCII fallback)
    "refaktör",     # refactor (loanword)
    "yeniden",      # "yeniden duzenle" = refactor; strong signal when alone
    "incele",       # review / investigate
    "karsilastir",  # compare (ASCII fallback)
    "karşılaştır",  # compare
    "uygula",       # implement (verb)
    "gelistir",     # develop / implement (ASCII fallback)
    "geliştir",     # develop / implement
    "sorun",        # problem / issue
    "istisna",      # exception
    # "optimize" already in _COMPLEX_KEYWORDS (loanword used as-is in TR)

    # German (DE)
    "fehler",         # error
    "debuggen",       # to debug
    "debugge",        # debug (imperative)
    "analysieren",    # to analyze
    "analysiere",     # analyze (imperative)
    "analyse",        # analysis
    "architektur",    # architecture
    "refactorn",      # to refactor
    "optimieren",     # to optimize
    "optimiere",      # optimize (imperative)
    "implementieren", # to implement
    "vergleichen",    # to compare
    "uberprufen",     # to review / check (ASCII fallback)
    "überprüfen",     # to review / check
    "ausnahme",       # exception

    # French (FR)
    "deboguer",     # to debug (ASCII fallback)
    "déboguer",     # to debug
    "debogue",      # debug (ASCII fallback)
    "débogue",      # debug (imperative)
    "erreur",       # error
    "analyser",     # to analyze
    "implementer",  # to implement (ASCII fallback)
    "implémenter",  # to implement
    "refactoriser", # to refactor
    "optimiser",    # to optimize
    "comparer",     # to compare
    "reviser",      # to review (ASCII fallback)
    "réviser",      # to review
    "conception",   # design (technical sense)
    "probleme",     # problem (ASCII fallback)
    "problème",     # problem

    # Spanish (ES)
    "depurar",      # to debug
    "depura",       # debug (imperative)
    "fallo",        # failure / error
    "analizar",     # to analyze
    "implementar",  # to implement
    "refactorizar", # to refactor
    "optimizar",    # to optimize
    "arquitectura", # architecture
    "comparar",     # to compare
    "revisar",      # to review
    "diseno",       # design (ASCII fallback)
    "diseño",       # design

    # Portuguese / Brazilian Portuguese (PT/BR)
    "debugar",      # to debug (BR)
    "depurar",      # to debug (PT) -- also in ES, no conflict
    "erro",         # error
    "analisar",     # to analyze
    "refatorar",    # to refactor
    "otimizar",     # to optimize
    "arquitetura",  # architecture

    # Russian (RU)
    "ошибка",          # error
    "отладка",         # debugging (noun)
    "отладить",        # to debug
    "дебажить",        # to debug (colloquial)
    "анализ",          # analysis
    "анализировать",   # to analyze
    "рефакторинг",     # refactoring
    "архитектура",     # architecture
    "оптимизировать",  # to optimize
    "проверить",       # to review / check
    "тест",            # test
    "тесты",           # tests
})

# CJK scripts (Chinese, Japanese, Korean) do not separate words with spaces,
# so they need a separate substring-scan strategy.  Only tokens that are
# unambiguously complex-task signals are included here.
_COMPLEX_KEYWORDS_CJK: frozenset = frozenset({
    # Chinese Simplified (ZH)
    "调试",  # debug
    "错误",  # error
    "分析",  # analyze / analysis
    "重构",  # refactor
    "架构",  # architecture
    "优化",  # optimize
    "审查",  # review
    "测试",  # test
    "异常",  # exception
    "实现",  # implement
    "设计",  # design

    # Japanese (JA)
    "デバッグ",         # debug
    "エラー",           # error
    "リファクタリング", # refactoring
    "アーキテクチャ",   # architecture
    "最適化",           # optimize
    "レビュー",         # review
    "テスト",           # test
    "実装",             # implement
    "設計",             # design (shared with ZH)

    # Korean (KO)
    "디버그",   # debug
    "디버깅",   # debugging
    "오류",     # error
    "분석",     # analysis
    "리팩터링", # refactoring
    "아키텍처", # architecture
    "최적화",   # optimize
    "리뷰",     # review
    "테스트",   # test
    "구현",     # implement
})

# Combined space-delimited lookup -- O(1) membership test.
_ALL_COMPLEX_KEYWORDS: frozenset = frozenset(_COMPLEX_KEYWORDS) | _COMPLEX_KEYWORDS_MULTILINGUAL

_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)

# Unicode ranges that indicate CJK / kana script presence.
_CJK_RANGES = (
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3400, 0x4DBF),   # CJK Extension A
    (0x3040, 0x309F),   # Hiragana
    (0x30A0, 0x30FF),   # Katakana
    (0xAC00, 0xD7AF),   # Hangul syllables
    (0x1100, 0x11FF),   # Hangul jamo
)


def _contains_cjk(text: str) -> bool:
    """Return True if *text* contains at least one CJK / kana character."""
    return any(
        lo <= ord(c) <= hi
        for c in text
        for lo, hi in _CJK_RANGES
    )


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def choose_cheap_model_route(user_message: str, routing_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the configured cheap-model route when a message looks simple.

    Conservative by design: if the message has signs of code/tool/debugging/
    long-form work -- in any supported language -- keep the primary model.

    Supported languages for complex-task detection: English, Turkish, German,
    French, Spanish, Portuguese/Brazilian, Russian, Chinese (Simplified),
    Japanese, and Korean.
    """
    cfg = routing_config or {}
    if not _coerce_bool(cfg.get("enabled"), False):
        return None

    cheap_model = cfg.get("cheap_model") or {}
    if not isinstance(cheap_model, dict):
        return None
    provider = str(cheap_model.get("provider") or "").strip().lower()
    model = str(cheap_model.get("model") or "").strip()
    if not provider or not model:
        return None

    text = (user_message or "").strip()
    if not text:
        return None

    max_chars = _coerce_int(cfg.get("max_simple_chars"), 160)
    max_words = _coerce_int(cfg.get("max_simple_words"), 28)

    if len(text) > max_chars:
        return None
    if len(text.split()) > max_words:
        return None
    if text.count("\n") > 1:
        return None
    if "```" in text or "`" in text:
        return None
    if _URL_RE.search(text):
        return None

    # Space-delimited keyword check (covers Latin-script and Cyrillic languages).
    lowered = text.lower()
    words = {token.strip(".,:;!?()[]{}\"'`") for token in lowered.split()}
    if words & _ALL_COMPLEX_KEYWORDS:
        return None

    # Substring scan for CJK scripts which don't use spaces between words.
    if _contains_cjk(text) and any(kw in text for kw in _COMPLEX_KEYWORDS_CJK):
        return None

    route = dict(cheap_model)
    route["provider"] = provider
    route["model"] = model
    route["routing_reason"] = "simple_turn"
    return route


def resolve_turn_route(user_message: str, routing_config: Optional[Dict[str, Any]], primary: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the effective model/runtime for one turn.

    Returns a dict with model/runtime/signature/label fields.
    """
    route = choose_cheap_model_route(user_message, routing_config)
    if not route:
        return {
            "model": primary.get("model"),
            "runtime": {
                "api_key": primary.get("api_key"),
                "base_url": primary.get("base_url"),
                "provider": primary.get("provider"),
                "api_mode": primary.get("api_mode"),
                "command": primary.get("command"),
                "args": list(primary.get("args") or []),
            },
            "label": None,
            "signature": (
                primary.get("model"),
                primary.get("provider"),
                primary.get("base_url"),
                primary.get("api_mode"),
                primary.get("command"),
                tuple(primary.get("args") or ()),
            ),
        }

    from hermes_cli.runtime_provider import resolve_runtime_provider

    explicit_api_key = None
    api_key_env = str(route.get("api_key_env") or "").strip()
    if api_key_env:
        explicit_api_key = os.getenv(api_key_env) or None

    try:
        runtime = resolve_runtime_provider(
            requested=route.get("provider"),
            explicit_api_key=explicit_api_key,
            explicit_base_url=route.get("base_url"),
        )
    except Exception:
        return {
            "model": primary.get("model"),
            "runtime": {
                "api_key": primary.get("api_key"),
                "base_url": primary.get("base_url"),
                "provider": primary.get("provider"),
                "api_mode": primary.get("api_mode"),
                "command": primary.get("command"),
                "args": list(primary.get("args") or []),
            },
            "label": None,
            "signature": (
                primary.get("model"),
                primary.get("provider"),
                primary.get("base_url"),
                primary.get("api_mode"),
                primary.get("command"),
                tuple(primary.get("args") or ()),
            ),
        }

    return {
        "model": route.get("model"),
        "runtime": {
            "api_key": runtime.get("api_key"),
            "base_url": runtime.get("base_url"),
            "provider": runtime.get("provider"),
            "api_mode": runtime.get("api_mode"),
            "command": runtime.get("command"),
            "args": list(runtime.get("args") or []),
        },
        "label": f"smart route -> {route.get('model')} ({runtime.get('provider')})",
        "signature": (
            route.get("model"),
            runtime.get("provider"),
            runtime.get("base_url"),
            runtime.get("api_mode"),
            runtime.get("command"),
            tuple(runtime.get("args") or ()),
        ),
    }
