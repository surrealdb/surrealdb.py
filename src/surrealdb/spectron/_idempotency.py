from __future__ import annotations

import hashlib
import time

DEFAULT_BUCKET_SECONDS = 30


def idempotency_key(
    method: str,
    path: str,
    body: bytes,
    *,
    bucket_seconds: int = DEFAULT_BUCKET_SECONDS,
) -> str:
    bucket = int(time.time() // bucket_seconds)
    h = hashlib.sha256()
    h.update(method.upper().encode("ascii"))
    h.update(b"\0")
    h.update(path.encode("utf-8"))
    h.update(b"\0")
    h.update(body)
    h.update(b"\0")
    h.update(str(bucket).encode("ascii"))
    return h.hexdigest()


__all__ = ["idempotency_key", "DEFAULT_BUCKET_SECONDS"]
