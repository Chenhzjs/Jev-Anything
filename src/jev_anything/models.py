"""Versioned, JSON-friendly objects shared by the live loop and workbench."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class Candidate:
    id: str
    label: str
    operation: str
    target: str
    risk: str
    expected_effect: str
    preconditions: list[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class Observation:
    application: str
    window: str
    scene: str
    generation: int
    interaction_scope: str
    controls: list[dict[str, Any]]
    candidates: list[Candidate]
    observed_at: str = field(default_factory=now)
    version: str = "observation.v1"


@dataclass
class Decision:
    status: str
    selected_candidate_id: str | None
    confidence: float | None
    model: str
    latency_ms: int
    request_id: str | None = None
    reason: str | None = None
    version: str = "decision.v1"


@dataclass
class Outcome:
    status: str
    delivery: str
    effect: str
    generation_before: int
    generation_after: int
    readback: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None
    version: str = "outcome.v1"


def as_json(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value


def trace_id() -> str:
    return f"trace-{uuid4().hex[:12]}"

