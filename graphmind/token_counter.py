"""Token counting and cost estimation utilities.

Uses tiktoken when available for accurate GPT-family counts.
Falls back to the standard 4-chars-per-token approximation otherwise.

Pricing table is based on public list prices (input tokens) as of 2025.
These can be overridden via the MODEL_PRICING dict if your team uses different
models or negotiated rates.
"""
from __future__ import annotations

# Input token prices in USD per 1 000 tokens (as of 2025 public list prices).
MODEL_PRICING: dict[str, float] = {
    "gpt-4o": 0.0025,        # $2.50 / 1M
    "gpt-4o-mini": 0.00015,  # $0.15 / 1M
    "gpt-4-turbo": 0.010,    # $10   / 1M
    "gpt-4": 0.030,          # $30   / 1M
    "claude-3-5-sonnet": 0.003,  # $3 / 1M
    "claude-3-opus": 0.015,      # $15 / 1M
    "gemini-1.5-pro": 0.00125,   # $1.25 / 1M
}

_DEFAULT_MODEL = "gpt-4o"

# Try to load tiktoken once at import time.
try:
    import tiktoken as _tiktoken  # type: ignore

    _enc = _tiktoken.get_encoding("cl100k_base")  # works for GPT-4, GPT-3.5, Claude
    _HAS_TIKTOKEN = True
except Exception:
    _tiktoken = None  # type: ignore
    _enc = None
    _HAS_TIKTOKEN = False


def count_tokens(text: str) -> int:
    """Return the estimated token count for *text*.

    Uses tiktoken (cl100k_base) when available; otherwise approximates with
    the well-known rule of thumb ``len(text) // 4``.
    """
    if not text:
        return 0
    if _HAS_TIKTOKEN and _enc is not None:
        try:
            return len(_enc.encode(text))
        except Exception:
            pass
    # Fallback: ~4 characters per token (conservative, slightly over-estimates).
    return max(1, len(text) // 4)


def estimate_cost(tokens: int, model: str = _DEFAULT_MODEL) -> float:
    """Return the estimated USD cost for *tokens* input tokens with *model*."""
    price_per_1k = MODEL_PRICING.get(model, MODEL_PRICING[_DEFAULT_MODEL])
    return round(tokens * price_per_1k / 1000, 6)


def compute_savings(
    full_text_map: dict[str, str],
    pack_text: str,
    model: str = _DEFAULT_MODEL,
) -> dict:
    """Compute token savings between a naïve full-file dump and a context pack.

    Args:
        full_text_map: Dict of {relative_path: file_content} — every file that
                       would have been sent without mindretriever.
        pack_text:     The complete text content actually returned in the pack
                       (snippets + graph summary serialised as a string).
        model:         Model name used for cost estimation.

    Returns a dict with counts, percentages, and dollar figures suitable for
    direct JSON serialisation and DB storage.
    """
    full_tokens = sum(count_tokens(v) for v in full_text_map.values())
    pack_tokens = count_tokens(pack_text)

    saved_tokens = max(0, full_tokens - pack_tokens)
    savings_pct = round(saved_tokens / full_tokens * 100, 1) if full_tokens > 0 else 0.0

    cost_full = estimate_cost(full_tokens, model)
    cost_pack = estimate_cost(pack_tokens, model)
    cost_saved = round(cost_full - cost_pack, 6)

    return {
        "model": model,
        "full_tokens": full_tokens,
        "pack_tokens": pack_tokens,
        "saved_tokens": saved_tokens,
        "savings_pct": savings_pct,
        "cost_full_usd": cost_full,
        "cost_pack_usd": cost_pack,
        "cost_saved_usd": cost_saved,
        "tiktoken_used": _HAS_TIKTOKEN,
    }
