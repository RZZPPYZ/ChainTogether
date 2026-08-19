from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContextSealDecision:
    action: str
    reason: str
    used_ratio: float | None = None
    projected_used_ratio: float | None = None


@dataclass(frozen=True)
class ContextSealPolicy:
    """Provider-neutral warning/action policy for group session rotation."""

    enabled: bool
    warn_ratio: float
    action_ratio: float
    reserve_tokens: int

    def __post_init__(self) -> None:
        if not 0 <= self.warn_ratio < self.action_ratio <= 1:
            raise ValueError("context ratios must satisfy 0 <= warn < action <= 1")
        if self.reserve_tokens < 0:
            raise ValueError("reserve_tokens must be non-negative")

    def evaluate(
        self,
        context_usage: dict[str, Any] | None,
        *,
        projected_prompt_tokens: int = 0,
    ) -> ContextSealDecision:
        if not self.enabled:
            return ContextSealDecision("disabled", "policy_disabled")
        if not isinstance(context_usage, dict):
            return ContextSealDecision("unknown", "context_health_unavailable")

        window = _positive_int(context_usage.get("context_window"))
        total = _non_negative_int(context_usage.get("total_tokens"))
        remaining_ratio = _ratio(context_usage.get("remaining_ratio"))
        if window is None:
            return ContextSealDecision("unknown", "context_health_unavailable")
        if total is None and remaining_ratio is not None:
            total = round(window * (1 - remaining_ratio))
        if total is None:
            remaining = _non_negative_int(context_usage.get("remaining_tokens"))
            if remaining is not None:
                total = max(0, window - remaining)
        if total is None:
            return ContextSealDecision("unknown", "context_health_unavailable")

        used = max(0.0, min(1.0, total / window))
        projected_tokens = max(0, projected_prompt_tokens) + self.reserve_tokens
        projected = max(0.0, min(1.0, (total + projected_tokens) / window))
        if used >= self.action_ratio:
            return ContextSealDecision(
                "seal", "context_limit", used, projected
            )
        if projected >= self.action_ratio:
            return ContextSealDecision(
                "seal", "projected_context_limit", used, projected
            )
        if used >= self.warn_ratio or projected >= self.warn_ratio:
            return ContextSealDecision(
                "warning", "context_warning", used, projected
            )
        return ContextSealDecision("healthy", "below_threshold", used, projected)


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _positive_int(value: Any) -> int | None:
    parsed = _non_negative_int(value)
    return parsed if parsed and parsed > 0 else None


def _ratio(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if 0 <= parsed <= 1 else None
