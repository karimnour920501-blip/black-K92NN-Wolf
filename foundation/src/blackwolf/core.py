"""Minimal deterministic domain primitives."""
import hashlib
import json
from typing import Any


def canonical_event(event: dict[str, Any]) -> bytes:
    if not isinstance(event, dict):
        raise TypeError("event must be a dictionary")
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def event_digest(event: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_event(event)).hexdigest()
