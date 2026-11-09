from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# CLI streams do not consistently report the model's context window. These
# defaults are deliberately marked as estimated in the returned payload.
_BACKEND_DEFAULT_CONTEXT_WINDOWS = {
    "claude-code": 200_000,
    "codex": 400_000,
}


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 else None
    if isinstance(value, str):
        try:
            parsed = int(float(value.strip()))
        except ValueError:
            return None
        return parsed if parsed >= 0 else None
    return None


def _pick_int(data: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = _as_int(data.get(key))
        if value is not None:
            return value
    return None


def _usage_payload(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    for key in ("context_usage", "usage", "token_usage"):
        value = raw.get(key)
        if isinstance(value, dict):
            return value
    return raw


def _infer_context_window(backend: str, model: str | None) -> int | None:
    normalized_model = (model or "").casefold()
    if normalized_model.startswith("claude-"):
        return 200_000
    if normalized_model.startswith("gpt-5") or "codex" in normalized_model:
        return 400_000
    return _BACKEND_DEFAULT_CONTEXT_WINDOWS.get(backend)


def normalize_context_usage(
    *,
    backend: str,
    model: str | None,
    raw: dict[str, Any] | None,
) -> dict[str, Any] | None:
    usage = _usage_payload(raw)
    if not usage:
        return None

    input_tokens = _pick_int(
        usage, "input_tokens", "prompt_tokens", "input_token_count"
    )
    output_tokens = _pick_int(
        usage, "output_tokens", "completion_tokens", "output_token_count"
    )
    cached_input_tokens = _pick_int(
        usage, "cached_input_tokens", "cache_read_input_tokens"
    )
    cache_creation_input_tokens = _pick_int(usage, "cache_creation_input_tokens")
    total_tokens = _pick_int(usage, "total_tokens", "total_token_count")
    if total_tokens is None:
        parts = [value for value in (input_tokens, output_tokens) if value is not None]
        if parts:
            total_tokens = sum(parts)

    # Tokens consumed by this turn (summed over every API request the CLI
    # made), used by the UI to replace the old per-turn USD readout.
    # Claude reports uncached input separately from cache reads/writes, so
    # the cache counters must be added; Codex's `input_tokens` already
    # includes `cached_input_tokens` (OpenAI usage semantics), so adding
    # them would double-count.
    if backend == "claude-code":
        turn_parts = (
            input_tokens,
            cached_input_tokens,
            cache_creation_input_tokens,
            output_tokens,
        )
    else:
        turn_parts = (input_tokens, output_tokens)
    turn_tokens: int | None
    if any(value is not None for value in turn_parts):
        turn_tokens = sum(value or 0 for value in turn_parts)
    else:
        turn_tokens = total_tokens

    reported_window = _pick_int(
        usage,
        "context_window",
        "context_window_tokens",
        "max_context_tokens",
        "input_tokens_limit",
    )
    reported_remaining = _pick_int(
        usage,
        "remaining_tokens",
        "remaining_context_tokens",
        "remaining_context_window",
        "context_remaining_tokens",
    )
    context_window = reported_window or _infer_context_window(backend, model)
    remaining_tokens = reported_remaining
    if remaining_tokens is None and context_window is not None and total_tokens is not None:
        remaining_tokens = max(0, context_window - total_tokens)

    remaining_ratio = None
    if context_window and remaining_tokens is not None:
        remaining_ratio = max(0.0, min(1.0, remaining_tokens / context_window))

    if (
        input_tokens is None
        and output_tokens is None
        and total_tokens is None
        and remaining_tokens is None
    ):
        return None

    source = (
        "reported"
        if reported_window is not None or reported_remaining is not None
        else "estimated"
        if context_window is not None
        else "reported"
    )
    out: dict[str, Any] = {
        "backend": backend,
        "source": source,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    if model:
        out["model"] = model
    for key, value in (
        ("input_tokens", input_tokens),
        ("output_tokens", output_tokens),
        ("cached_input_tokens", cached_input_tokens),
        ("cache_creation_input_tokens", cache_creation_input_tokens),
        ("total_tokens", total_tokens),
        ("turn_tokens", turn_tokens),
        ("context_window", context_window),
        ("remaining_tokens", remaining_tokens),
        ("remaining_ratio", remaining_ratio),
    ):
        if value is not None:
            out[key] = value
    return out
