from __future__ import annotations

from enum import StrEnum


class OutboxStatus(StrEnum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    DEAD = "DEAD"


def calculate_backoff(
    attempts: int,
    base_seconds: int = 5,
    cap_seconds: int = 300,
) -> float:
    if attempts < 1:
        raise ValueError("Attempts must be at least 1")
    val = base_seconds * (2 ** (attempts - 1))
    return float(min(cap_seconds, val))
