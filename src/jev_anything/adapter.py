"""Generic adapter for GUI2TUI's structured scene export.

The adapter owns GUI2TUI-specific scene parsing. The decision plugin only sees
Observation and Candidate records, so applications can replace this layer
without changing Jev or the execution lifecycle.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time
from typing import Iterable

from .plugin import Candidate, CapabilityUnavailable, Observation


@dataclass(frozen=True)
class ActionSpec:
    id: str
    label: str
    expected_effect: str | None
    operation: str = "Action: click"
    risk: str = "local_fixture_only"


class Gui2TuiSceneAdapter:
    """Turn one GUI2TUI ``--dump-scene`` result into a Jev observation."""

    def __init__(self, *, application: str, window_title: str,
                 scope: str, actions: Iterable[ActionSpec]):
        self.application = application
        self.window_title = window_title
        self.scope = scope
        self.actions = tuple(actions)

    def observe(self, scene: str, *, observed_at: float | None = None) -> Observation:
        if not scene or f'Scene title="{self.window_title}"' not in scene:
            raise CapabilityUnavailable("GUI2TUI scene title is unavailable")
        generation = hashlib.sha256(scene.encode()).hexdigest()[:16]
        candidates = []
        matched = 0
        for action in self.actions:
            matches = [line for line in scene.splitlines()
                       if f'label: "{action.label}"' in line and "binding=" in line]
            if len(matches) > 1:
                raise CapabilityUnavailable("Ambiguous GUI2TUI binding: " + action.label)
            if not matches:
                continue
            matched += 1
            if "checked: true" in matches[0]:
                continue
            candidates.append(Candidate(
                action.id, action.label, action.operation, self.scope,
                generation, action.expected_effect, action.risk,
            ))
        if self.actions and matched == 0:
            raise CapabilityUnavailable("GUI2TUI exposed no configured executable actions")
        return Observation(
            self.application, scene, generation, self.scope, tuple(candidates),
            observed_at=time.time() if observed_at is None else observed_at,
        )

    def require_candidates(self, observation: Observation) -> None:
        """Reject a scene when a configured action disappeared unexpectedly."""
        configured = {action.label for action in self.actions}
        visible = {candidate.label for candidate in observation.candidates}
        unknown = visible - configured
        if unknown:
            raise CapabilityUnavailable("Unconfigured GUI2TUI candidates: " + ", ".join(sorted(unknown)))
