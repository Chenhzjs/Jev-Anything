"""GUI2TUI public-terminal adapter; upstream binaries are never modified."""
from dataclasses import asdict
import os
import subprocess
import time
import pexpect
import pyte
from .jev import JevClient
from .models import trace_id
from .adapter import ActionSpec, Gui2TuiSceneAdapter
from .plugin import Observation, CapabilityUnavailable, DecisionPlugin, RuleProvider
from .scenarios import SCENARIOS


class LiveSession:
    def __init__(self):
        self.fixture = None
        self.terminal = None
        self.frame = ""
        self.plugin = DecisionPlugin(self)
        self.reset()

    def reset(self, scenario="preferences", context=None):
        if scenario not in SCENARIOS:
            raise ValueError("Unknown GUI scenario")
        if self.terminal:
            self.terminal.close(force=True)
        if self.fixture:
            self.fixture.terminate()
            self.fixture.wait(timeout=5)
        env = os.environ.copy()
        env["JEV_SCENARIO"] = scenario
        env["JEV_APP"] = SCENARIOS[scenario]["app"]
        if context is not None:
            env["JEV_CONTEXT"] = context
        else:
            env.pop("JEV_CONTEXT", None)
        self.scenario = scenario
        if SCENARIOS[scenario].get("kind") == "browser":
            subprocess.run(["python3", "/opt/jev-anything/browser_fixture.py", scenario], env=env,
                           check=True, timeout=15)
            self.fixture = None
        else:
            self.fixture = subprocess.Popen(["python3", "/opt/jev-anything/fixture.py"], env=env)
        subprocess.run(["python3", "/opt/jev-anything/atspi_probe.py"], check=True, capture_output=True, timeout=20, env=env)
        self.screen = pyte.Screen(180, 40)
        self.stream = pyte.Stream(self.screen)
        config = SCENARIOS[scenario]
        self.terminal = pexpect.spawn("gui2tui", ["--session", "desktop", "--layout", "flat", "--app", SCENARIOS[scenario]["app"]], encoding="utf-8", dimensions=(40, 180), timeout=1)
        self.wait("? Help")
        self.session_id = trace_id()
        self.scene_adapter = Gui2TuiSceneAdapter(
            application=config["app"], window_title=config["window_title"],
            scope=self.session_id,
            actions=tuple(ActionSpec(identity, label, effect)
                          for identity, label, effect in config["actions"]),
        )

    def pump(self, duration=0.15):
        end = time.monotonic() + duration
        while time.monotonic() < end:
            try:
                self.stream.feed(self.terminal.read_nonblocking(65536, timeout=0.05))
            except pexpect.TIMEOUT:
                pass
        self.frame = "\n".join(line.rstrip() for line in self.screen.display)
        return self.frame

    def wait(self, text):
        end = time.monotonic() + 25
        while time.monotonic() < end:
            if text in self.pump():
                return self.frame
        raise CapabilityUnavailable("GUI2TUI did not display " + repr(text))

    def snapshot(self):
        app = SCENARIOS[self.scenario]["app"]
        result = subprocess.run(["gui2tui", "inspect", "--", "--app", app, "--dump-scene"], capture_output=True, text=True, timeout=20, check=True)
        scene = result.stdout
        if not hasattr(self, "scene_adapter"):
            config = SCENARIOS[self.scenario]
            self.scene_adapter = Gui2TuiSceneAdapter(
                application=config["app"], window_title=config["window_title"],
                scope=self.session_id,
                actions=tuple(ActionSpec(identity, label, effect)
                              for identity, label, effect in config["actions"]),
            )
        return self.scene_adapter.observe(scene)

    def observe(self):
        return asdict(self.snapshot())

    def select(self, candidate, invoke=False):
        self.terminal.send("\x1bOR")
        submitted = False
        try:
            self.wait("Command palette")
            self.terminal.send(candidate.label)
            self.wait(candidate.operation)
            for _ in range(30):
                frame = self.pump()
                if any("> " in line and candidate.label in line and candidate.operation in line for line in frame.splitlines()):
                    if invoke:
                        self.terminal.send("\r")
                        submitted = True
                        self.pump(0.5)
                    return
                self.terminal.send("\x1b[B")
            raise CapabilityUnavailable("Exact public operation unavailable")
        finally:
            if not submitted:
                self.terminal.send("\x1b")
                self.pump()

    def validate(self, candidate):
        self.select(candidate)

    def execute(self, candidate):
        self.select(candidate, invoke=True)

    def verify(self, candidate, before, after):
        if candidate.expected_effect is None:
            return None
        if candidate.id == "c-theme":
            return 'label: "Enable dark mode", checked: true' in after.scene
        return (f'text: "{candidate.expected_effect}"' in after.scene
                or f'label: "{candidate.expected_effect}"' in after.scene)

    def run(self, goal, emit, provider="jev", scenario="normal", cancelled=lambda: False,
            request_id=None, reverse_options=False):
        def change():
            if scenario == "stale" and not cancelled():
                self.execute(self.snapshot().candidates[0])
        client = JevClient() if provider == "jev" else RuleProvider() if provider == "rule" else None
        if client is None:
            raise ValueError("Unknown provider")
        return self.plugin.run(goal, client, request_id=request_id or trace_id(), emit=emit,
                               cancelled=cancelled, before_validation=change, reverse_options=reverse_options)
