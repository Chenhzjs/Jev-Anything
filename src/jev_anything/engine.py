"""A deterministic replay engine used by the localhost demo."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import Any

from .jev import JevClient, JevError
from .models import Candidate, Decision, Observation, Outcome, as_json, trace_id


class MockProvider:
    model = "mock/jev-replay"

    def decide(self, *, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
        candidates = state.get("candidates", [])
        goal = str(state.get("goal", "")).lower()
        for candidate in candidates:
            if any(word in candidate["label"].lower() for word in goal.split()):
                return {"action": {"type": "choice", "choice": candidate["id"]}}
        return {"action": {"type": "choice", "choice": "abstain"}}


class DemoEngine:
    def __init__(self, live: bool = False) -> None:
        self.live = live
        self.generation = 12
        self.scene = "preferences"
        self.dark_mode = False
        self._provider: Any = None

    def provider(self) -> Any:
        if self._provider is None:
            self._provider = JevClient() if self.live else MockProvider()
        return self._provider

    def observe(self) -> Observation:
        candidates = [
            Candidate("c-theme", "启用深色模式", "toggle", "appearance.dark_mode", "local_mutation", "dark_mode=true"),
            Candidate("c-notify", "打开通知设置", "navigate", "settings.notifications", "reversible_navigation", "scene=notifications"),
            Candidate("c-close", "关闭设置窗口", "close", "settings.window", "reversible_navigation", "window=closed"),
        ]
        return Observation(
            application="Jev Settings Fixture",
            window="Preferences",
            scene=self.scene,
            generation=self.generation,
            interaction_scope="preferences.modal",
            controls=[
                {"id": "appearance.dark_mode", "role": "switch", "name": "深色模式", "state": "on" if self.dark_mode else "off"},
                {"id": "settings.notifications", "role": "tab", "name": "通知", "state": "available"},
                {"id": "settings.window", "role": "window", "name": "设置窗口", "state": "open"},
            ],
            candidates=candidates,
        )

    def run(self, goal: str, *, force_stale: bool = False) -> Iterator[dict[str, Any]]:
        trace = trace_id()
        observation = self.observe()
        yield self.event(trace, "observe", "读取当前 GUI 语义", observation=as_json(observation))
        yield self.event(trace, "candidates", "生成 3 个经过 GUI2TUI 约束的候选", candidates=[as_json(c) for c in observation.candidates])
        if force_stale:
            self.generation += 1
            yield self.event(trace, "stale", "GUI 在决策前发生变化，旧 generation 已失效")
        question = {"action": {"type": "choice", "instructions": f"选择完成目标“{goal}”所需的下一步操作", "criteria": {c.id: c.label for c in observation.candidates} | {"abstain": "证据不足时不执行"}}}
        state = {"goal": goal, "scene": observation.scene, "candidates": [as_json(c) for c in observation.candidates]}
        yield self.event(trace, "jev_request", "发送结构化决策请求", question=question)
        start = time.perf_counter()
        try:
            answers = self.provider().decide(state=state, questions=question)
            selected = self.extract_choice(answers)
            reason = None
        except JevError as exc:
            selected = "abstain"
            reason = str(exc)
        latency = int((time.perf_counter() - start) * 1000)
        decision = Decision("abstained" if selected == "abstain" else "selected", None if selected == "abstain" else selected, None, getattr(self.provider(), "model", "miyang/jev-1.13"), latency, reason=reason)
        yield self.event(trace, "decision", "Jev 返回选择" if selected != "abstain" else "Jev 选择 abstain", decision=as_json(decision))
        if selected == "abstain":
            yield self.event(trace, "outcome", "没有执行操作", outcome=as_json(Outcome("abstained", "not_attempted", "none", observation.generation, self.generation, reason="model_abstain")))
            return
        candidate = next((c for c in observation.candidates if c.id == selected), None)
        if candidate is None or observation.generation != self.generation:
            outcome = Outcome("rejected", "blocked", "none", observation.generation, self.generation, reason="stale_or_unknown_candidate")
            yield self.event(trace, "validation", "候选未通过 generation 或 membership 校验")
            yield self.event(trace, "outcome", "拒绝执行过期候选", outcome=as_json(outcome))
            return
        yield self.event(trace, "validation", "候选通过 membership、scope 和风险校验", candidate_id=selected)
        yield self.event(trace, "dispatch", f"GUI2TUI 执行：{candidate.label}", candidate_id=selected)
        before = self.generation
        self.apply(candidate)
        after = self.generation
        readback = self.observe()
        outcome = Outcome("confirmed", "accepted", "confirmed", before, after, {"scene": readback.scene, "dark_mode": self.dark_mode})
        yield self.event(trace, "readback", "重新读取 GUI 权威状态", observation=as_json(readback))
        yield self.event(trace, "outcome", "操作已执行并由 readback 确认", outcome=as_json(outcome))

    def apply(self, candidate: Candidate) -> None:
        if candidate.id == "c-theme":
            self.dark_mode = True
        elif candidate.id == "c-notify":
            self.scene = "notifications"
        self.generation += 1

    @staticmethod
    def extract_choice(answers: dict[str, Any]) -> str:
        answer = answers.get("action", answers.get("choice", answers))
        if isinstance(answer, dict):
            for key in ("choice", "value", "answer", "selected"):
                if isinstance(answer.get(key), str):
                    return answer[key]
        if isinstance(answer, str):
            return answer
        return "abstain"

    @staticmethod
    def event(trace: str, kind: str, message: str, **data: Any) -> dict[str, Any]:
        return {"trace_id": trace, "kind": kind, "message": message, "timestamp": time.time(), **data}

