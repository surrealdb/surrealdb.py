from __future__ import annotations

_BACKOFF_SECONDS: tuple[float, ...] = (0.25, 0.5, 1.0)


def backoff_schedule(max_retries: int = 3) -> tuple[float, ...]:
    capped = max(0, min(max_retries, len(_BACKOFF_SECONDS)))
    return _BACKOFF_SECONDS[:capped]


def should_retry(
    method: str, status: int | None, attempt: int, max_retries: int
) -> bool:
    if attempt >= max_retries:
        return False
    if method.upper() != "GET":
        return False
    if status is None:
        return True
    return status >= 500


__all__ = ["backoff_schedule", "should_retry"]
