"""Small, provider-focused client for the Jev decisions endpoint."""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import Any, Mapping

import requests


class JevError(RuntimeError):
    """Raised when Jev cannot return a valid decision response."""


def encode_request(model, state, questions):
    """The actual wire encoding, also used by explicit chunk-mode planning."""
    return json.dumps({"model": model, "state": dict(state), "questions": dict(questions)},
                      ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class JevConfig:
    api_key: str
    api_url: str = "https://miyang.cn/api/v1/decisions"
    model: str = "miyang/jev-1.13"
    timeout: float = 60.0
    decision_retries: int = 0

    def __post_init__(self):
        if type(self.decision_retries) is not int or not 0 <= self.decision_retries <= 1:
            raise ValueError('decision_retries must be zero or one')

    @classmethod
    def from_env(cls) -> "JevConfig":
        api_key = (os.environ.get("MIYANG_API_KEY", "") or os.environ.get("JEV_API_KEY", "")).strip()
        if not api_key:
            raise JevError("MIYANG_API_KEY (or JEV_API_KEY) is not configured")
        return cls(
            api_key=api_key,
            api_url=os.environ.get("JEV_API_URL", cls.api_url),
            model=os.environ.get("JEV_MODEL", cls.model),
            timeout=float(os.environ.get("JEV_TIMEOUT_SECONDS", cls.timeout)),
            decision_retries=int(os.environ.get("JEV_DECISION_RETRIES", "0")),
        )


class JevClient:
    """Call Jev without exposing provider details to the rest of the app."""

    def __init__(self, config: JevConfig | None = None, *, session=None) -> None:
        self.config = config or JevConfig.from_env()
        self.model = self.config.model
        self.metadata = {}
        self._http = session if session is not None else requests

    def decide(
        self,
        *,
        state: Mapping[str, Any],
        questions: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        # A failed request must never inherit the preceding decision's receipt.
        self.metadata = {}
        attempts = []
        try:
            raw = encode_request(self.config.model, state, questions)
            for attempt in range(self.config.decision_retries + 1):
                self.metadata = {"read_only_attempts": attempts} if self.config.decision_retries else {}
                response = self._http.post(
                    self.config.api_url,
                    headers={"Authorization": f"Bearer {self.config.api_key}",
                             "Content-Type": "application/json"},
                    data=raw,
                    timeout=self.config.timeout,
                )
                receipt = {"http_status": response.status_code,
                           "request_id": response.headers.get("X-Request-ID")}
                self.metadata.update(receipt)
                if self.config.decision_retries:
                    attempts.append(receipt)
                retry = False
                if response.status_code == 400 and attempt < self.config.decision_retries:
                    try:
                        rejected = response.json()
                    except ValueError:
                        rejected = None
                    retry = (isinstance(rejected, Mapping) and isinstance(rejected.get('error'), Mapping)
                             and rejected['error'].get('code') == 1004)
                if not retry:
                    break
                # Repeat only a rejected read-only decision request, with
                # identical bytes. Never retry a GUI operation or a valid answer.
                response.close()
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise JevError(f"Jev request failed: {exc}") from exc

        if not isinstance(body, Mapping):
            raise JevError("Jev response is not an object")
        answers = body.get("answers")
        if not isinstance(answers, Mapping):
            raise JevError("Jev response does not contain an answers object")
        self.metadata.update(request_id=body.get("id") or self.metadata.get("request_id"),
                             usage=body.get("usage", {}))
        return answers
