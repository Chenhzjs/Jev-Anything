"""Small, provider-focused client for the Jev decisions endpoint."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

import requests


class JevError(RuntimeError):
    """Raised when Jev cannot return a valid decision response."""


@dataclass(frozen=True)
class JevConfig:
    api_key: str
    api_url: str = "https://miyang.cn/api/v1/decisions"
    model: str = "miyang/jev-1.13"
    timeout: float = 60.0

    @classmethod
    def from_env(cls) -> "JevConfig":
        api_key = os.environ.get("JEV_API_KEY", "").strip()
        if not api_key:
            raise JevError("JEV_API_KEY is not configured")
        return cls(
            api_key=api_key,
            api_url=os.environ.get("JEV_API_URL", cls.api_url),
            model=os.environ.get("JEV_MODEL", cls.model),
            timeout=float(os.environ.get("JEV_TIMEOUT_SECONDS", cls.timeout)),
        )


class JevClient:
    """Call Jev without exposing provider details to the rest of the app."""

    def __init__(self, config: JevConfig | None = None) -> None:
        self.config = config or JevConfig.from_env()
        self.model = self.config.model
        self.metadata = {}

    def decide(
        self,
        *,
        state: Mapping[str, Any],
        questions: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        payload = {
            "model": self.config.model,
            "state": dict(state),
            "questions": dict(questions),
        }
        try:
            response = requests.post(
                self.config.api_url,
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                json=payload,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise JevError(f"Jev request failed: {exc}") from exc

        if not isinstance(body, Mapping):
            raise JevError("Jev response is not an object")
        answers = body.get("answers")
        if not isinstance(answers, Mapping):
            raise JevError("Jev response does not contain an answers object")
        self.metadata = {"request_id": body.get("id"), "usage": body.get("usage", {})}
        return answers
