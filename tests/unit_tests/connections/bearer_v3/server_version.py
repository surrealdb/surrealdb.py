"""What the server under test does with bearer access, by version."""

import re


def bearer_jwts_authenticate(version_str: str) -> bool:
    """Whether the server accepts a bearer-issued JWT in ``authenticate`` (3.4 on)."""
    match = re.search(r"(\d+)\.(\d+)", version_str or "")
    return match is not None and (int(match[1]), int(match[2])) >= (3, 4)
